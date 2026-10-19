from .azure import AzureBackend
from .base import Backend, SynthRequest, SynthResult, Voice, VoiceError
from .edge import EdgeBackend
from .elevenlabs import ElevenLabsBackend
from .kokoro import KokoroBackend
from .offline import PiperBackend, SapiBackend
from .openai_tts import OpenAIBackend

BACKENDS = {b.name: b for b in (EdgeBackend, KokoroBackend, ElevenLabsBackend, OpenAIBackend, AzureBackend,
                                PiperBackend, SapiBackend)}

__all__ = ["BACKENDS", "Backend", "SynthRequest", "SynthResult", "Voice", "VoiceError"]
