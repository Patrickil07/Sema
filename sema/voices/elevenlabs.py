"""ElevenLabs voices: the most human-sounding option, with cross-chunk context stitching."""
from __future__ import annotations

import os

import aiohttp

from .base import Backend, SynthRequest, SynthResult, Voice, VoiceError

API = "https://api.elevenlabs.io/v1"


class ElevenLabsBackend(Backend):
    name = "elevenlabs"
    label = "ElevenLabs"
    needs_key = True
    speed_range = (0.7, 1.2)

    @property
    def key(self):
        return self.settings.get("api_key") or os.environ.get("ELEVENLABS_API_KEY", "")

    def available(self):
        return (True, "") if self.key else (False, "Add your ElevenLabs API key in settings")

    def default_voice(self):
        return "JBFqnCBsd6RMkjVDRZzb"  # George

    def curated_voices(self):
        return [
            Voice("JBFqnCBsd6RMkjVDRZzb", "George (warm narrator)", "multi", "Male", ["best"]),
            Voice("EXAVITQu4vr4xnSDxMaL", "Sarah (soft, clear)", "multi", "Female", ["best"]),
            Voice("21m00Tcm4TlvDq8ikWAM", "Rachel (calm)", "multi", "Female"),
            Voice("pNInz6obpgDQGcFmaJgB", "Adam (deep)", "multi", "Male"),
            Voice("XB0fDUnXU5powFXDhCwa", "Charlotte (expressive)", "multi", "Female"),
            Voice("onwK4e9ZLuTAKqWW03F9", "Daniel (news)", "multi", "Male"),
        ]

    async def list_voices(self):
        if not self.key:
            return self.curated_voices()
        async with aiohttp.ClientSession(trust_env=True) as s:
            async with s.get(f"{API}/voices", headers={"xi-api-key": self.key}) as r:
                if r.status != 200:
                    return self.curated_voices()
                data = await r.json()
        return [Voice(v["voice_id"], v["name"], "multi", (v.get("labels") or {}).get("gender", ""))
                for v in data.get("voices", [])]

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        if not self.key:
            raise VoiceError("ElevenLabs API key missing")
        speed = self.native_speed(req.speed)
        # narrative/dialogue get more expressive (lower stability); news/technical steadier
        stability = {"narrative": 0.35, "dialogue": 0.3, "news": 0.6, "technical": 0.6}.get(req.kind, 0.5)
        body = {
            "text": req.text,
            "model_id": self.settings.get("model", "eleven_multilingual_v2"),
            "voice_settings": {"stability": stability, "similarity_boost": 0.8, "style": 0.15,
                               "use_speaker_boost": True, "speed": speed},
        }
        if req.previous_text:
            body["previous_text"] = req.previous_text[-500:]
        if req.next_text:
            body["next_text"] = req.next_text[:500]
        voice = req.voice or self.default_voice()
        async with aiohttp.ClientSession(trust_env=True) as s:
            async with s.post(f"{API}/text-to-speech/{voice}?output_format=mp3_44100_128", json=body,
                              headers={"xi-api-key": self.key}, timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status != 200:
                    raise VoiceError(f"ElevenLabs {r.status}: {(await r.text())[:300]}")
                return SynthResult(await r.read(), speed, "mp3")
