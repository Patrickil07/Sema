"""Offline voices: Piper (local neural, if a model is configured) or Windows SAPI."""
from __future__ import annotations

import asyncio
import io
import os
import tempfile
import wave

from .base import Backend, SynthRequest, SynthResult, Voice, VoiceError


class PiperBackend(Backend):
    """Local neural voice. Download a voice (.onnx + .onnx.json) from
    https://huggingface.co/rhasspy/piper-voices and set its path in settings."""
    name = "piper"
    label = "Piper (offline neural)"

    def __init__(self, settings):
        super().__init__(settings)
        self._voice = None

    def available(self):
        try:
            import piper  # noqa: F401
        except ImportError:
            return False, "pip install piper-tts"
        model = self.settings.get("model_path", "")
        if not model or not os.path.exists(model):
            return False, "Set piper.model_path to a downloaded .onnx voice"
        return True, ""

    def default_voice(self):
        return os.path.basename(self.settings.get("model_path", "")) or "piper"

    def curated_voices(self):
        return [Voice(self.default_voice(), self.default_voice(), "", "")]

    def _synth(self, text: str) -> bytes:
        from piper import PiperVoice
        if self._voice is None:
            self._voice = PiperVoice.load(self.settings["model_path"])
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            if hasattr(self._voice, "synthesize_wav"):
                self._voice.synthesize_wav(text, wf)
            else:  # piper-tts < 1.3
                self._voice.synthesize(text, wf)
        return buf.getvalue()

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        ok, why = self.available()
        if not ok:
            raise VoiceError(why)
        audio = await asyncio.get_running_loop().run_in_executor(None, self._synth, req.text)
        return SynthResult(audio, 1.0, "wav")


class SapiBackend(Backend):
    """Built-in Windows voices. Always available on Windows; used as the last fallback."""
    name = "sapi"
    label = "Windows voices (offline)"
    speed_range = (0.5, 2.5)

    def available(self):
        if os.name != "nt":
            return False, "Windows only"
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            return False, "pip install pywin32"
        return True, ""

    def default_voice(self):
        return ""

    def curated_voices(self):
        if os.name != "nt":
            return []
        try:
            import win32com.client
            sp = win32com.client.Dispatch("SAPI.SpVoice")
            return [Voice(t.GetDescription(), t.GetDescription()) for t in sp.GetVoices()]
        except Exception:
            return []

    def _synth(self, text: str, voice: str, speed: float) -> bytes:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            sp = win32com.client.Dispatch("SAPI.SpVoice")
            if voice:
                for t in sp.GetVoices():
                    if t.GetDescription() == voice:
                        sp.Voice = t
            # SAPI rate runs -10..10 with 0 as normal speed
            sp.Rate = max(-10, min(10, round((speed - 1) * 10)))
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Open(path, 3)  # SSFMCreateForWrite; writes a proper WAV header
            sp.AudioOutputStream = stream
            sp.Speak(text)
            stream.Close()
            with open(path, "rb") as f:
                data = f.read()
            os.remove(path)
        finally:
            pythoncom.CoUninitialize()
        return data

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        ok, why = self.available()
        if not ok:
            raise VoiceError(why)
        speed = self.native_speed(req.speed)
        audio = await asyncio.get_running_loop().run_in_executor(None, self._synth, req.text, req.voice, speed)
        return SynthResult(audio, speed, "wav")
