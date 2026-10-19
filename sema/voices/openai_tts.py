"""OpenAI speech (gpt-4o-mini-tts): steerable delivery via natural-language instructions."""
from __future__ import annotations

import os

import aiohttp

from .base import Backend, SynthRequest, SynthResult, Voice, VoiceError

VOICES = ["marin", "cedar", "coral", "sage", "alloy", "ash", "ballad", "echo", "fable", "nova",
          "onyx", "shimmer", "verse"]


class OpenAIBackend(Backend):
    name = "openai"
    label = "OpenAI"
    needs_key = True

    @property
    def key(self):
        return self.settings.get("api_key") or os.environ.get("OPENAI_API_KEY", "")

    @property
    def model(self):
        return self.settings.get("model", "gpt-4o-mini-tts")

    @property
    def speed_range(self):
        # the expressive model ignores `speed`; tts-1 / tts-1-hd honour it
        return None if self.model.startswith("gpt-") else (0.25, 4.0)

    def available(self):
        return (True, "") if self.key else (False, "Add your OpenAI API key in settings")

    def default_voice(self):
        return "marin"

    def curated_voices(self):
        best = {"marin", "cedar"}
        return [Voice(v, v.title(), "multi", "", ["best"] if v in best else []) for v in VOICES]

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        if not self.key:
            raise VoiceError("OpenAI API key missing")
        body = {"model": self.model, "voice": req.voice or self.default_voice(), "input": req.text,
                "response_format": "mp3"}
        applied = 1.0
        if self.speed_range:
            applied = self.native_speed(req.speed)
            body["speed"] = applied
        else:
            body["instructions"] = (self.settings.get("instructions") or req.instructions or "").strip()
        async with aiohttp.ClientSession(trust_env=True) as s:
            async with s.post("https://api.openai.com/v1/audio/speech", json=body,
                              headers={"Authorization": f"Bearer {self.key}"},
                              timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status != 200:
                    raise VoiceError(f"OpenAI {r.status}: {(await r.text())[:300]}")
                return SynthResult(await r.read(), applied, "mp3")
