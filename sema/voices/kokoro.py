"""Kokoro: a natural-sounding neural voice that runs entirely on this PC (no key, no internet
after a one-time model download). Much closer to modern AI voices than the built-in Windows ones."""
from __future__ import annotations

import asyncio
import io
import logging
import threading
import urllib.request
import wave
from pathlib import Path

from .base import Backend, SynthRequest, SynthResult, Voice, VoiceError

log = logging.getLogger("sema")
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = {"full": "kokoro-v1.0.onnx", "small": "kokoro-v1.0.int8.onnx"}
VOICES_FILE = "voices-v1.0.bin"


def models_dir() -> Path:
    from ..config import config_dir
    return config_dir() / "models"


class KokoroBackend(Backend):
    name = "kokoro"
    label = "Kokoro (natural, offline)"
    speed_range = (0.5, 2.0)
    _model = None
    _lock = threading.Lock()

    def available(self):
        try:
            import kokoro_onnx  # noqa: F401
        except ImportError:
            return False, "pip install kokoro-onnx"
        return True, ""

    def default_voice(self):
        return "af_heart"

    def curated_voices(self):
        return [
            Voice("af_heart", "Heart (US, warm)", "en-US", "Female", ["best"]),
            Voice("af_bella", "Bella (US, expressive)", "en-US", "Female", ["best"]),
            Voice("am_michael", "Michael (US, calm)", "en-US", "Male", ["best"]),
            Voice("am_fenrir", "Fenrir (US, deep)", "en-US", "Male"),
            Voice("af_nicole", "Nicole (US, soft)", "en-US", "Female"),
            Voice("bf_emma", "Emma (UK)", "en-GB", "Female"),
            Voice("bm_george", "George (UK, narrator)", "en-GB", "Male"),
            Voice("bm_fable", "Fable (UK, storyteller)", "en-GB", "Male"),
            Voice("ff_siwis", "Siwis (French)", "fr-FR", "Female"),
            Voice("ef_dora", "Dora (Spanish)", "es-ES", "Female"),
        ]

    def _paths(self) -> tuple[Path, Path]:
        d = Path(self.settings.get("model_dir") or models_dir())
        return d / FILES[self.settings.get("model_size", "full")], d / VOICES_FILE

    def _ensure_files(self):
        for path in self._paths():
            if path.exists() and path.stat().st_size > 1_000_000:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            log.info("downloading %s (one time)", path.name)
            tmp = path.with_suffix(".part")
            try:
                urllib.request.urlretrieve(RELEASE + path.name, tmp)
            except OSError as e:
                raise VoiceError(f"Couldn't download the Kokoro voice model: {e}") from e
            tmp.replace(path)

    def _load(self):
        with KokoroBackend._lock:
            if KokoroBackend._model is None:
                from kokoro_onnx import Kokoro
                self._ensure_files()
                model, voices = self._paths()
                KokoroBackend._model = Kokoro(str(model), str(voices))
            return KokoroBackend._model

    def _synth(self, text: str, voice: str, speed: float) -> bytes:
        model = self._load()
        lang = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "i": "it", "p": "pt-br",
                "h": "hi", "j": "ja", "z": "cmn"}.get(voice[:1], "en-us")
        samples, sr = model.create(text, voice=voice, speed=speed, lang=lang)
        pcm = (samples.clip(-1, 1) * 32767).astype("<i2").tobytes()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm)
        return buf.getvalue()

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        ok, why = self.available()
        if not ok:
            raise VoiceError(why)
        speed = self.native_speed(req.speed)
        voice = req.voice or self.default_voice()
        try:
            audio = await asyncio.get_running_loop().run_in_executor(None, self._synth, req.text, voice, speed)
        except VoiceError:
            raise
        except Exception as e:
            raise VoiceError(f"Kokoro failed: {e}") from e
        return SynthResult(audio, speed, "wav")
