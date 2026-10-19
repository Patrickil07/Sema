"""Azure AI Speech neural voices via SSML (supports speaking styles like newscast/chat)."""
from __future__ import annotations

import os
from xml.sax.saxutils import escape

import aiohttp

from .base import Backend, SynthRequest, SynthResult, Voice, VoiceError

# voices that accept <mstts:express-as> styles used by the context engine
STYLE_VOICES = {"en-US-AriaNeural", "en-US-JennyNeural", "en-US-GuyNeural", "en-US-DavisNeural",
                "en-US-JaneNeural", "en-US-JasonNeural", "en-US-NancyNeural", "en-US-SaraNeural",
                "en-US-TonyNeural"}


class AzureBackend(Backend):
    name = "azure"
    label = "Azure Neural"
    needs_key = True
    speed_range = (0.5, 2.0)

    @property
    def key(self):
        return self.settings.get("api_key") or os.environ.get("AZURE_SPEECH_KEY", "")

    @property
    def region(self):
        return self.settings.get("region") or os.environ.get("AZURE_SPEECH_REGION", "eastus")

    def available(self):
        return (True, "") if self.key else (False, "Add your Azure Speech key and region in settings")

    def default_voice(self):
        return "en-US-AvaMultilingualNeural"

    def curated_voices(self):
        return [
            Voice("en-US-AvaMultilingualNeural", "Ava (multilingual)", "en-US", "Female", ["best"]),
            Voice("en-US-AndrewMultilingualNeural", "Andrew (multilingual)", "en-US", "Male", ["best"]),
            Voice("en-US-AriaNeural", "Aria (styles)", "en-US", "Female", ["styles"]),
            Voice("en-US-JennyNeural", "Jenny (styles)", "en-US", "Female", ["styles"]),
            Voice("en-US-GuyNeural", "Guy (styles)", "en-US", "Male", ["styles"]),
            Voice("en-GB-SoniaNeural", "Sonia (UK)", "en-GB", "Female"),
        ]

    def build_ssml(self, req: SynthRequest, speed: float) -> str:
        voice = req.voice or self.default_voice()
        lang = "-".join(voice.split("-")[:2])
        inner = f'<prosody rate="{round((speed - 1) * 100):+d}%">{escape(req.text)}</prosody>'
        if req.azure_style and voice in STYLE_VOICES:
            inner = f'<mstts:express-as style="{req.azure_style}">{inner}</mstts:express-as>'
        return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{lang}">'
                f'<voice name="{voice}">{inner}</voice></speak>')

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        if not self.key:
            raise VoiceError("Azure Speech key missing")
        speed = self.native_speed(req.speed)
        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {"Ocp-Apim-Subscription-Key": self.key, "Content-Type": "application/ssml+xml",
                   "X-Microsoft-OutputFormat": "audio-48khz-96kbitrate-mono-mp3", "User-Agent": "Sema"}
        async with aiohttp.ClientSession(trust_env=True) as s:
            async with s.post(url, data=self.build_ssml(req, speed).encode(), headers=headers,
                              timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status != 200:
                    raise VoiceError(f"Azure {r.status}: {(await r.text())[:300]}")
                return SynthResult(await r.read(), speed, "mp3")
