"""The reading pipeline: context -> normalization -> chunks -> voice -> playback.

Synthesis runs ahead of playback (a few chunks are buffered) so long documents read
without gaps, and every control (pause, skip, speed) takes effect immediately.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import audio
from .chunker import Chunk, _split_long, chunk_text
from .context import Prepared, detect_kind, prepare
from .normalize import looks_english, normalize
from .voices import BACKENDS, Backend, SynthRequest, VoiceError

log = logging.getLogger("sema")
PREFETCH = 3


@dataclass
class Reading:
    chunks: list[Chunk]
    prepared: Prepared
    source: str = ""


class Engine:
    def __init__(self, config, player=None, on_event: Callable[[dict], None] | None = None):
        self.config = config
        self.player = player or audio.Player(volume=config["volume"])
        self.on_event = on_event or (lambda e: None)
        self.state = "idle"
        self.reading: Reading | None = None
        self.index = 0
        self.current: Chunk | None = None
        self.last_error = ""
        self._backends: dict[str, Backend] = {}
        self._cancel = threading.Event()
        self._task: asyncio.Task | None = None
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, name="sema-engine", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ backends
    def backend(self, name: str | None = None) -> Backend:
        name = name or self.config["backend"]
        if name not in self._backends:
            self._backends[name] = BACKENDS[name](self.config.get(name, {}))
        return self._backends[name]

    def reset_backends(self):
        self._backends.clear()

    # ------------------------------------------------------------------ public API (thread-safe)
    def speak(self, text: str = "", *, source: str = "", kind: str | None = None,
              segments: list[dict] | None = None):
        reading = self.build_reading(text, source=source, kind=kind, segments=segments)
        if not reading.chunks:
            return
        self._submit(self._start(reading, 0))

    def pause(self):
        if self.state == "speaking":
            self.player.pause()
            self._set_state("paused")

    def resume(self):
        if self.state == "paused":
            self.player.resume()
            self._set_state("speaking")

    def toggle(self):
        if self.state == "speaking":
            self.pause()
        elif self.state == "paused":
            self.resume()
        elif self.reading:  # finished: replay from the start
            self._submit(self._start(self.reading, 0))

    def stop(self):
        self._submit(self._halt())

    def skip(self, delta: int):
        if self.reading:
            target = max(0, min(len(self.reading.chunks) - 1, self.index + delta))
            self._submit(self._start(self.reading, target))

    def seek_segment(self, segment):
        if self.reading:
            for i, c in enumerate(self.reading.chunks):
                if c.segment == segment:
                    self._submit(self._start(self.reading, i))
                    return

    def set_speed(self, speed: float):
        speed = round(max(0.5, min(3.5, speed)), 2)
        self.config.set("speed", speed)
        self.on_event({"type": "speed", "speed": speed})
        if self.state in ("speaking", "paused") and self.reading:
            self._submit(self._start(self.reading, self.index))  # re-voice from here at the new speed

    def status(self) -> dict:
        b = self.backend()
        return {"state": self.state, "segment": self.current.segment if self.current else None,
                "index": self.index, "total": len(self.reading.chunks) if self.reading else 0,
                "text": self.current.text if self.current else "", "speed": self.config["speed"],
                "backend": b.name, "voice": self.config.voice_for(b), "error": self.last_error}

    def shutdown(self):
        self._cancel.set()
        self.player.close()
        self.loop.call_soon_threadsafe(self.loop.stop)

    # ------------------------------------------------------------------ preparation
    def build_reading(self, text: str = "", *, source: str = "", kind: str | None = None,
                      segments: list[dict] | None = None) -> Reading:
        cfg = self.config
        english = None

        def norm(t):
            return normalize(t, date_order=cfg["date_order"], url_mode=cfg["read_urls"], force_english=english)
        if segments:
            joined = "\n\n".join(s["text"] for s in segments)
            english = looks_english(joined)  # decide once; single sentences are too short to judge
            kind = kind or detect_kind(joined, source)
            prepared = prepare(joined, source, kind="general" if kind == "email" else kind)
            prepared.kind = kind
            chunks = []
            for s in segments:
                spoken = norm(s["text"])
                for piece in _split_long(spoken, 520):
                    if piece.strip():
                        chunks.append(Chunk(piece, s["id"], int(s.get("pause_after_ms", 0))))
        else:
            prepared = prepare(text, source, kind=kind, read_quoted_email=cfg["read_quoted_email"])
            chunks = chunk_text(norm(prepared.text), paragraph_pause_ms=cfg["paragraph_pause_ms"])
        return Reading(chunks, prepared, source)

    # ------------------------------------------------------------------ internals
    def _submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def _set_state(self, state: str):
        if state != self.state:
            self.state = state
            self.on_event({"type": "state", "state": state})

    async def _halt(self):
        self._cancel.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self.player.clear()
        self.player.resume()
        self.current = None
        self._set_state("idle")

    async def _start(self, reading: Reading, start: int):
        await self._halt()
        self.reading = reading
        self.index = start
        self.last_error = ""
        self._cancel = threading.Event()
        self._set_state("speaking")
        self._task = asyncio.create_task(self._run(reading, start, self._cancel))

    async def _run(self, reading: Reading, start: int, cancel: threading.Event):
        queue: asyncio.Queue = asyncio.Queue(maxsize=PREFETCH)

        async def produce():
            for i in range(start, len(reading.chunks)):
                try:
                    samples = await self._render(reading, i)
                except VoiceError as e:
                    await queue.put(e)
                    return
                await queue.put((i, samples))
            await queue.put(None)

        producer = asyncio.create_task(produce())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    self.last_error = str(item)
                    self.on_event({"type": "error", "message": str(item)})
                    break
                i, samples = item
                chunk = reading.chunks[i]
                self.index, self.current = i, chunk
                self.on_event({"type": "chunk", "index": i, "total": len(reading.chunks),
                               "segment": chunk.segment, "text": chunk.text})
                if chunk.pause_after_ms:
                    gap = np.zeros(int(audio.SAMPLE_RATE * chunk.pause_after_ms / 1000), dtype=np.float32)
                    samples = np.concatenate([samples, gap])
                done = await self.loop.run_in_executor(None, self.player.play, samples, cancel)
                if not done:
                    return
            self.current = None
            self._set_state("idle")
            self.on_event({"type": "finished"})
        finally:
            producer.cancel()

    async def _render(self, reading: Reading, i: int) -> np.ndarray:
        chunk = reading.chunks[i]
        chunks = reading.chunks
        p = reading.prepared
        speed = float(self.config["speed"])
        req = SynthRequest(
            text=chunk.text, voice="", speed=speed, kind=p.kind, instructions=p.instructions,
            azure_style=p.azure_style,
            previous_text=" ".join(c.text for c in chunks[max(0, i - 2):i]),
            next_text=chunks[i + 1].text if i + 1 < len(chunks) else "",
            language=None if looks_english(chunk.text) else "auto")
        order = [self.config["backend"]] + [b for b in self.config["fallback_order"] if b != self.config["backend"]]
        errors = []
        for name in order:
            backend = self.backend(name)
            ok, why = backend.available()
            if not ok:
                errors.append(f"{backend.label}: {why}")
                continue
            req.voice = self.config.voice_for(backend)
            try:
                result = await backend.synthesize(req)
            except VoiceError as e:
                errors.append(f"{backend.label}: {e}")
                log.warning("voice %s failed: %s", name, e)
                continue
            if name != self.config["backend"]:
                self.on_event({"type": "warning", "message": f"Using {backend.label}; " + "; ".join(errors)})
            return await self.loop.run_in_executor(None, self._post, result.audio, speed / result.applied_speed)
        raise VoiceError("No voice could read this. " + "; ".join(errors))

    @staticmethod
    def _post(data: bytes, stretch: float) -> np.ndarray:
        x = audio.trim_silence(audio.decode(data))
        return audio.time_stretch(x, stretch)
