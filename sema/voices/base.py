"""Common interface for every voice backend."""
from __future__ import annotations

from dataclasses import dataclass, field


class VoiceError(RuntimeError):
    """A backend could not synthesize (missing key, quota, network...)."""


@dataclass
class SynthRequest:
    text: str
    voice: str
    speed: float = 1.0
    kind: str = "general"
    instructions: str = ""          # delivery direction from the context engine
    azure_style: str | None = None
    previous_text: str = ""         # neighbouring text so prosody flows across chunks
    next_text: str = ""
    language: str | None = None


@dataclass
class SynthResult:
    audio: bytes                    # encoded audio (mp3 or wav); the player decodes it
    applied_speed: float = 1.0      # speed the backend already applied natively
    fmt: str = "mp3"


@dataclass
class Voice:
    id: str
    name: str
    language: str = ""
    gender: str = ""
    tags: list[str] = field(default_factory=list)


class Backend:
    name = "base"
    label = "Base"
    needs_key = False
    speed_range: tuple[float, float] | None = None   # native speed support, None = none

    def __init__(self, settings: dict):
        self.settings = settings or {}

    def available(self) -> tuple[bool, str]:
        return True, ""

    def default_voice(self) -> str:
        raise NotImplementedError

    def curated_voices(self) -> list[Voice]:
        return []

    async def list_voices(self) -> list[Voice]:
        return self.curated_voices()

    async def synthesize(self, req: SynthRequest) -> SynthResult:
        raise NotImplementedError

    def native_speed(self, speed: float) -> float:
        """Portion of `speed` this backend can apply itself; the rest is time-stretched."""
        if not self.speed_range:
            return 1.0
        lo, hi = self.speed_range
        return min(hi, max(lo, speed))
