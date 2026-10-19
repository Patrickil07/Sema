"""Settings live in %APPDATA%\\Sema\\config.json (or ~/.config/sema on other systems)."""
from __future__ import annotations

import copy
import json
import os
import secrets
from pathlib import Path

DEFAULTS = {
    "backend": "edge",                 # edge | openai | elevenlabs | azure | piper | sapi
    "fallback_order": ["edge", "sapi"],
    "speed": 1.0,
    "volume": 1.0,
    "voices": {},                      # backend -> chosen voice id
    "date_order": "MDY",               # MDY (US) or DMY (UK/EU/Africa) for numeric dates
    "read_urls": "domain",             # domain | full | skip
    "read_quoted_email": False,        # read the quoted reply chain in emails
    "paragraph_pause_ms": 380,
    "show_player": True,
    "hotkeys": {
        "read": "alt+shift+s",          # selection, else the text under the mouse
        "read_document": "alt+shift+d", # whole document/message from the cursor (Word, Outlook...)
        "read_hover": "alt+shift+h",
        "ocr_region": "alt+shift+o",    # drag a box around anything on screen
        "read_clipboard": "alt+shift+c",
        "pause": "alt+shift+p",
        "stop": "alt+shift+x",
        "faster": "alt+shift+up",
        "slower": "alt+shift+down",
        "next": "alt+shift+right",
        "previous": "alt+shift+left",
    },
    "server": {"enabled": True, "port": 51789, "token": ""},
    "openai": {"api_key": "", "model": "gpt-4o-mini-tts", "instructions": ""},
    "elevenlabs": {"api_key": "", "model": "eleven_multilingual_v2"},
    "azure": {"api_key": "", "region": "eastus"},
    "piper": {"model_path": ""},
    "edge": {},
    "sapi": {},
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "Sema"


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or config_dir() / "config.json"
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data = _merge(DEFAULTS, json.loads(self.path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        if not self.data["server"]["token"]:
            self.data["server"]["token"] = secrets.token_hex(4)
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v
        self.save()

    def voice_for(self, backend) -> str:
        return self.data["voices"].get(backend.name) or backend.default_voice()
