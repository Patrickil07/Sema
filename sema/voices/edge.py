"""Microsoft Edge neural voices (free, no key). Same voices as Edge's "Read aloud"."""
from __future__ import annotations

from .base import Backend, SynthRequest, SynthResult, Voice, VoiceError


class EdgeBackend(Backend):
    name = "edge"
    label = "Microsoft Neural (free)"
    speed_range = (0.5, 2.0)

    def available(self):
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False, "pip install edge-tts"
        return True, ""

    def default_voice(self):
        return "en-US-AvaMultilingualNeural"

    def curated_voices(self):
        return [
            Voice("en-US-AvaMultilingualNeural", "Ava (US, multilingual)", "en-US", "Female", ["best"]),
            Voice("en-US-AndrewMultilingualNeural", "Andrew (US, multilingual)", "en-US", "Male", ["best"]),
            Voice("en-US-EmmaMultilingualNeural", "Emma (US, multilingual)", "en-US", "Female"),
            Voice("en-US-BrianMultilingualNeural", "Brian (US, multilingual)", "en-US", "Male"),
            Voice("en-GB-SoniaNeural", "Sonia (UK)", "en-GB", "Female"),
            Voice("en-GB-RyanNeural", "Ryan (UK)", "en-GB", "Male"),
            Voice("en-AU-NatashaNeural", "Natasha (Australia)", "en-AU", "Female"),
            Voice("en-NG-EzinneNeural", "Ezinne (Nigeria)", "en-NG", "Female"),
            Voice("en-KE-ChilembaNeural", "Chilemba (Kenya)", "en-KE", "Male"),
            Voice("fr-FR-VivienneMultilingualNeural", "Vivienne (French, multilingual)", "fr-FR", "Female"),
            Voice("de-DE-SeraphinaMultilingualNeural", "Seraphina (German, multilingual)", "de-DE", "Female"),
        ]

    async def list_voices(self):
        import edge_tts
        voices = await edge_tts.list_voices(proxy=self.settings.get("proxy"))
        return [Voice(v["ShortName"], v.get("FriendlyName", v["ShortName"]), v["Locale"], v.get("Gender", ""))
                for v in voices]

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        import edge_tts
        speed = self.native_speed(req.speed)
        rate = f"{round((speed - 1) * 100):+d}%"
        comm = edge_tts.Communicate(req.text, req.voice or self.default_voice(), rate=rate,
                                    proxy=self.settings.get("proxy"))
        audio = bytearray()
        try:
            async for part in comm.stream():
                if part["type"] == "audio":
                    audio.extend(part["data"])
        except Exception as e:  # network / service errors
            raise VoiceError(f"Edge voices unavailable: {e}") from e
        if not audio:
            raise VoiceError("Edge voices returned no audio")
        return SynthResult(bytes(audio), speed, "mp3")
