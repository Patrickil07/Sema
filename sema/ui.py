"""On-screen pieces: the floating mini player and the OCR region picker (tkinter)."""
from __future__ import annotations

import ctypes
import os
import queue
import tkinter as tk

BG = "#14161c"
FG = "#f2f3f5"
MUTED = "#9aa0ab"
ACCENT = "#7c8cff"


def virtual_screen() -> tuple[int, int, int, int]:
    if os.name == "nt":
        u = ctypes.windll.user32
        return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
    return 0, 0, 1920, 1080


class MiniPlayer:
    """Small always-on-top bar showing what is being read, with transport controls."""

    def __init__(self, root: tk.Tk, engine):
        self.engine = engine
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.96)
        except tk.TclError:
            pass
        self.win.configure(bg=BG)
        frame = tk.Frame(self.win, bg=BG, padx=12, pady=8)
        frame.pack(fill="both", expand=True)
        top = tk.Frame(frame, bg=BG)
        top.pack(fill="x")
        self.title = tk.Label(top, text="Sema", fg=ACCENT, bg=BG, font=("Segoe UI Semibold", 10))
        self.title.pack(side="left")
        self.meta = tk.Label(top, text="", fg=MUTED, bg=BG, font=("Segoe UI", 9))
        self.meta.pack(side="left", padx=8)
        close = tk.Label(top, text="✕", fg=MUTED, bg=BG, cursor="hand2", font=("Segoe UI", 10))
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: (engine.stop(), self.hide()))
        self.text = tk.Label(frame, text="", fg=FG, bg=BG, justify="left", anchor="w",
                             wraplength=420, font=("Segoe UI", 11))
        self.text.pack(fill="x", pady=(6, 6))
        bar = tk.Frame(frame, bg=BG)
        bar.pack(fill="x")
        self.buttons = {}
        for key, label, cmd in [("prev", "⏮", lambda: engine.skip(-1)), ("play", "⏸", engine.toggle),
                                ("next", "⏭", lambda: engine.skip(1)), ("stop", "■", engine.stop),
                                ("slower", "−", lambda: engine.set_speed(engine.config["speed"] - 0.1)),
                                ("speed", "1.0×", None),
                                ("faster", "+", lambda: engine.set_speed(engine.config["speed"] + 0.1))]:
            b = tk.Label(bar, text=label, fg=FG, bg=BG, font=("Segoe UI Symbol", 13), padx=6,
                         cursor="hand2" if cmd else "")
            b.pack(side="left")
            if cmd:
                b.bind("<Button-1>", lambda e, c=cmd: c())
            self.buttons[key] = b
        for w in (frame, top, self.title, self.text):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag)
        self._placed = False
        self._hide_job = None

    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _drag(self, e):
        self.win.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")
        self._placed = True

    def show(self):
        if self._hide_job:
            self.win.after_cancel(self._hide_job)
            self._hide_job = None
        if not self._placed:
            self.win.update_idletasks()
            sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            self.win.geometry(f"460x130+{sw - 480}+{sh - 190}")
        self.win.deiconify()
        self.win.lift()

    def hide(self):
        self.win.withdraw()

    def hide_later(self, ms=3500):
        if self._hide_job:
            self.win.after_cancel(self._hide_job)
        self._hide_job = self.win.after(ms, self.hide)

    def handle(self, ev: dict):
        st = self.engine.status()
        self.meta.configure(text=f"{st['backend']} · {short_voice(st['voice'])}")
        self.buttons["speed"].configure(text=f"{self.engine.config['speed']:.1f}×")
        t = ev.get("type")
        if t == "chunk":
            text = ev["text"]
            self.text.configure(text=text if len(text) < 260 else text[:257] + "…", fg=FG)
            self.buttons["play"].configure(text="⏸")
            if self.engine.config["show_player"]:
                self.show()
        elif t == "state":
            self.buttons["play"].configure(text="▶" if ev["state"] != "speaking" else "⏸")
            if ev["state"] == "idle":
                self.hide_later()
        elif t in ("error", "warning"):
            self.text.configure(text=ev["message"][:300], fg="#ffb4a8" if t == "error" else "#ffd98a")
            self.show()
            if t == "error":
                self.hide_later(8000)
        elif t == "notice":
            self.text.configure(text=ev["message"], fg=MUTED)
            self.show()
            self.hide_later(2500)


def short_voice(v: str) -> str:
    v = v or "default"
    if v.count("-") >= 2:  # en-US-AvaMultilingualNeural -> Ava
        v = v.split("-")[2].replace("MultilingualNeural", "").replace("Neural", "")
    return v[:24]


class RegionPicker:
    """Full-screen dim overlay; drag a rectangle to OCR it. Esc cancels."""

    def __init__(self, root: tk.Tk, on_done):
        self.on_done = on_done
        x, y, w, h = virtual_screen()
        self.origin = (x, y)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.28)
        except tk.TclError:
            pass
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.rect = None
        self.start = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda e: self._finish(None))
        self.win.focus_force()

    def _press(self, e):
        self.start = (e.x, e.y)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline=ACCENT, width=3, fill="white")

    def _move(self, e):
        if self.rect:
            self.canvas.coords(self.rect, *self.start, e.x, e.y)

    def _release(self, e):
        if not self.start:
            return self._finish(None)
        x0, y0 = min(self.start[0], e.x), min(self.start[1], e.y)
        x1, y1 = max(self.start[0], e.x), max(self.start[1], e.y)
        if x1 - x0 < 8 or y1 - y0 < 8:
            return self._finish(None)
        self._finish((x0 + self.origin[0], y0 + self.origin[1], x1 - x0, y1 - y0))

    def _finish(self, region):
        self.win.destroy()
        self.on_done(region)


class UiBridge:
    """Thread-safe way for engine/hotkey threads to talk to tkinter (main thread only)."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.root.after(40, self._pump)

    def call(self, fn, *args):
        self.q.put((fn, args))

    def _pump(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                try:
                    fn(*args)
                except Exception as e:  # never let UI callbacks kill the pump
                    print("ui error:", e)
        except queue.Empty:
            pass
        self.root.after(40, self._pump)
