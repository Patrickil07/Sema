"""Settings window: pick the voice engine and voice, paste API keys, tune reading."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .voices import BACKENDS

PAD = {"padx": 10, "pady": 4}


class SettingsWindow:
    def __init__(self, root: tk.Tk, engine, on_saved=None):
        self.engine = engine
        self.cfg = engine.config
        self.on_saved = on_saved
        w = self.win = tk.Toplevel(root)
        w.title("Sema settings")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        body = ttk.Frame(w, padding=12)
        body.pack(fill="both", expand=True)

        self.backend = tk.StringVar(value=self.cfg["backend"])
        self.voice = tk.StringVar()
        self.speed = tk.DoubleVar(value=self.cfg["speed"])
        self.date_order = tk.StringVar(value=self.cfg["date_order"])
        self.quoted = tk.BooleanVar(value=self.cfg["read_quoted_email"])
        self.keys = {
            "openai": tk.StringVar(value=self.cfg["openai"].get("api_key", "")),
            "elevenlabs": tk.StringVar(value=self.cfg["elevenlabs"].get("api_key", "")),
            "azure": tk.StringVar(value=self.cfg["azure"].get("api_key", "")),
        }
        self.region = tk.StringVar(value=self.cfg["azure"].get("region", "eastus"))
        self.piper = tk.StringVar(value=self.cfg["piper"].get("model_path", ""))

        r = 0
        ttk.Label(body, text="Voice engine").grid(row=r, column=0, sticky="w", **PAD)
        labels = {name: cls.label for name, cls in BACKENDS.items()}
        self._label_to_name = {v: k for k, v in labels.items()}
        self.backend_box = ttk.Combobox(body, state="readonly", width=38, values=list(labels.values()))
        self.backend_box.set(labels[self.cfg["backend"]])
        self.backend_box.grid(row=r, column=1, sticky="we", **PAD)
        self.backend_box.bind("<<ComboboxSelected>>", lambda e: self._load_voices())
        r += 1
        ttk.Label(body, text="Voice").grid(row=r, column=0, sticky="w", **PAD)
        self.voice_box = ttk.Combobox(body, width=38, textvariable=self.voice)
        self.voice_box.grid(row=r, column=1, sticky="we", **PAD)
        r += 1
        self.status = ttk.Label(body, text="", foreground="#a04000")
        self.status.grid(row=r, column=1, sticky="w", padx=10)
        r += 1
        ttk.Label(body, text="Speed").grid(row=r, column=0, sticky="w", **PAD)
        sp = ttk.Frame(body)
        sp.grid(row=r, column=1, sticky="we", **PAD)
        self.speed_lbl = ttk.Label(sp, width=5)
        ttk.Scale(sp, from_=0.5, to=3.0, variable=self.speed, length=260,
                  command=lambda v: self.speed_lbl.configure(text=f"{float(v):.1f}×")).pack(side="left")
        self.speed_lbl.pack(side="left", padx=6)
        self.speed_lbl.configure(text=f"{self.speed.get():.1f}×")
        r += 1

        ttk.Separator(body).grid(row=r, column=0, columnspan=2, sticky="we", pady=8)
        r += 1
        ttk.Label(body, text="API keys are stored only on this PC.", foreground="#666").grid(
            row=r, column=0, columnspan=2, sticky="w", padx=10)
        r += 1
        for name, title in (("openai", "OpenAI key"), ("elevenlabs", "ElevenLabs key"), ("azure", "Azure Speech key")):
            ttk.Label(body, text=title).grid(row=r, column=0, sticky="w", **PAD)
            ttk.Entry(body, textvariable=self.keys[name], show="•", width=40).grid(row=r, column=1, sticky="we", **PAD)
            r += 1
        ttk.Label(body, text="Azure region").grid(row=r, column=0, sticky="w", **PAD)
        ttk.Entry(body, textvariable=self.region, width=40).grid(row=r, column=1, sticky="we", **PAD)
        r += 1
        ttk.Label(body, text="Piper voice (.onnx)").grid(row=r, column=0, sticky="w", **PAD)
        ttk.Entry(body, textvariable=self.piper, width=40).grid(row=r, column=1, sticky="we", **PAD)
        r += 1

        ttk.Separator(body).grid(row=r, column=0, columnspan=2, sticky="we", pady=8)
        r += 1
        ttk.Label(body, text="Numeric dates").grid(row=r, column=0, sticky="w", **PAD)
        df = ttk.Frame(body)
        df.grid(row=r, column=1, sticky="w", **PAD)
        ttk.Radiobutton(df, text="10/18/2026 (US)", value="MDY", variable=self.date_order).pack(side="left")
        ttk.Radiobutton(df, text="18/10/2026", value="DMY", variable=self.date_order).pack(side="left", padx=8)
        r += 1
        ttk.Checkbutton(body, text="Also read quoted earlier messages in emails", variable=self.quoted).grid(
            row=r, column=1, sticky="w", **PAD)
        r += 1
        token = self.cfg["server"]["token"]
        ttk.Label(body, text="Browser pairing code").grid(row=r, column=0, sticky="w", **PAD)
        e = ttk.Entry(body, width=40)
        e.insert(0, token)
        e.configure(state="readonly")
        e.grid(row=r, column=1, sticky="we", **PAD)
        r += 1

        btns = ttk.Frame(body)
        btns.grid(row=r, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Test voice", command=self._test).pack(side="left", padx=4)
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=w.destroy).pack(side="left", padx=4)
        self._load_voices()

    def _name(self):
        return self._label_to_name[self.backend_box.get()]

    def _load_voices(self):
        name = self._name()
        backend = BACKENDS[name](self.cfg.get(name, {}))
        self._voices = backend.curated_voices()
        self.voice_box["values"] = [f"{v.name}  [{v.id}]" for v in self._voices]
        current = self.cfg["voices"].get(name) or backend.default_voice()
        match = next((f"{v.name}  [{v.id}]" for v in self._voices if v.id == current), current)
        self.voice.set(match)
        ok, why = backend.available()
        self.status.configure(text="" if ok else why)

    def _voice_id(self):
        v = self.voice.get().strip()
        return v[v.rfind("[") + 1:-1] if v.endswith("]") and "[" in v else v

    def _save(self):
        c = self.cfg.data
        name = self._name()
        c["backend"] = name
        c["voices"][name] = self._voice_id()
        c["speed"] = round(self.speed.get(), 1)
        c["date_order"] = self.date_order.get()
        c["read_quoted_email"] = self.quoted.get()
        for k, var in self.keys.items():
            c[k]["api_key"] = var.get().strip()
        c["azure"]["region"] = self.region.get().strip() or "eastus"
        c["piper"]["model_path"] = self.piper.get().strip().strip('"')
        self.cfg.save()
        self.engine.reset_backends()
        self._load_voices()
        if self.on_saved:
            self.on_saved()

    def _test(self):
        self._save()
        self.engine.speak("Hi, I'm your Sema voice. On Oct. 18th, Dr. Adams paid $1,250.75 for 3 tickets, "
                          "about 12% more than last year!")
