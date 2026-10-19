"""Sema desktop app: tray icon, global hotkeys, mini player, browser bridge."""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor

from . import capture, ocr, server
from .config import Config, config_dir
from .engine import Engine
from .ui import MiniPlayer, RegionPicker, UiBridge
from .voices import BACKENDS

log = logging.getLogger("sema")


def _init_worker():
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        pass
    try:
        import uiautomation as auto
        if hasattr(auto, "InitializeUIAutomationInCurrentThread"):
            auto.InitializeUIAutomationInCurrentThread()
    except ImportError:
        pass


def _icon_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=(124, 140, 255, 255))
    for i, h in enumerate((14, 26, 36, 26, 14)):
        x = 15 + i * 8
        d.rounded_rectangle((x, 32 - h // 2, x + 4, 32 + h // 2), radius=2, fill="white")
    return img


class SemaApp:
    def __init__(self):
        self.cfg = Config()
        self.root = tk.Tk()
        self.root.withdraw()
        self.bridge = UiBridge(self.root)
        self.engine = Engine(self.cfg, on_event=lambda ev: self.bridge.call(self.player.handle, ev))
        self.player = MiniPlayer(self.root, self.engine)
        self.worker = ThreadPoolExecutor(1, initializer=_init_worker, thread_name_prefix="sema-capture")
        self.icon = None

    # ------------------------------------------------------------------ actions
    def _say(self, text: str, source: str, empty_msg: str):
        text = (text or "").strip()
        if not text:
            self.bridge.call(self.player.handle, {"type": "notice", "message": empty_msg})
            return
        log.info("reading %d chars from %s", len(text), source)
        self.engine.speak(text, source=source)

    def _bg(self, fn):
        def run():
            try:
                fn()
            except Exception as e:
                log.exception("action failed")
                self.bridge.call(self.player.handle, {"type": "error", "message": f"Couldn't read that: {e}"})
        self.worker.submit(run)

    def read(self):
        def go():
            text, src = capture.get_selection()
            if not text:
                text, src = capture.get_text_under_mouse()
            self._say(text, src, "Select some text, or point at it, then press the hotkey.")
        self._bg(go)

    def read_document(self):
        def go():
            text, src = capture.get_document()
            self._say(text, src, "No readable document here. Try selecting text or the OCR hotkey.")
        self._bg(go)

    def read_hover(self):
        def go():
            text, src = capture.get_text_under_mouse()
            self._say(text, src, "Nothing readable under the mouse.")
        self._bg(go)

    def read_clipboard(self):
        self._bg(lambda: self._say(capture.clipboard_text(), "clipboard", "The clipboard has no text."))

    def ocr_region(self):
        def done(region):
            if region:
                self._bg(lambda: self._say(ocr.read_region(*region), "ocr", "No text found in that area."))
        self.bridge.call(lambda: RegionPicker(self.root, done))

    # ------------------------------------------------------------------ hotkeys
    def register_hotkeys(self):
        import keyboard
        e = self.engine
        actions = {
            "read": self.read, "read_document": self.read_document, "read_hover": self.read_hover,
            "ocr_region": self.ocr_region, "read_clipboard": self.read_clipboard,
            "pause": e.toggle, "stop": e.stop,
            "faster": lambda: e.set_speed(self.cfg["speed"] + 0.1),
            "slower": lambda: e.set_speed(self.cfg["speed"] - 0.1),
            "next": lambda: e.skip(1), "previous": lambda: e.skip(-1),
        }
        for name, combo in self.cfg["hotkeys"].items():
            if combo and name in actions:
                try:
                    keyboard.add_hotkey(combo, actions[name], suppress=False, trigger_on_release=False)
                except Exception as ex:
                    log.warning("hotkey %s (%s) failed: %s", name, combo, ex)

    # ------------------------------------------------------------------ tray
    def _set_backend(self, name):
        self.cfg.set("backend", name)
        self.engine.reset_backends()
        ok, why = self.engine.backend().available()
        self.bridge.call(self.player.handle, {"type": "notice" if ok else "warning",
                                              "message": BACKENDS[name].label + ("" if ok else f": {why}")})

    def _set_voice(self, vid):
        voices = dict(self.cfg["voices"])
        voices[self.cfg["backend"]] = vid
        self.cfg.set("voices", voices)

    def _copy_token(self):
        def do():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.cfg["server"]["token"])
            self.player.handle({"type": "notice", "message": f"Pairing code {self.cfg['server']['token']} copied"})
        self.bridge.call(do)

    def _open_settings(self):
        from .settings_ui import SettingsWindow
        self.bridge.call(lambda: SettingsWindow(self.root, self.engine))

    def build_tray(self):
        import pystray
        from pystray import Menu, MenuItem as Item

        def backend_items():
            return [Item(cls.label, (lambda n: lambda: self._set_backend(n))(name),
                         checked=(lambda n: lambda _: self.cfg["backend"] == n)(name), radio=True)
                    for name, cls in BACKENDS.items()]

        def voice_items():
            b = self.engine.backend()
            cur = self.cfg.voice_for(b)
            return [Item(v.name, (lambda i: lambda: self._set_voice(i))(v.id),
                         checked=(lambda i: lambda _: self.cfg.voice_for(self.engine.backend()) == i)(v.id),
                         radio=True)
                    for v in b.curated_voices()] or [Item(cur or "Default", None, enabled=False)]

        def speed_items():
            return [Item(f"{s:.2g}×", (lambda s: lambda: self.engine.set_speed(s))(s),
                         checked=(lambda s: lambda _: abs(self.cfg["speed"] - s) < 0.05)(s), radio=True)
                    for s in (0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0)]

        hk = self.cfg["hotkeys"]
        menu = Menu(
            Item(f"Read selection / under mouse   {hk['read']}", lambda: self.read(), default=True),
            Item(f"Read whole document   {hk['read_document']}", lambda: self.read_document()),
            Item(f"Read area of screen (OCR)   {hk['ocr_region']}", lambda: self.ocr_region()),
            Item(f"Read clipboard   {hk['read_clipboard']}", lambda: self.read_clipboard()),
            Item("Pause / resume", lambda: self.engine.toggle()),
            Item("Stop", lambda: self.engine.stop()),
            Menu.SEPARATOR,
            Item("Voice engine", Menu(backend_items)),
            Item("Voice", Menu(voice_items)),
            Item("Speed", Menu(speed_items)),
            Item("Show mini player", lambda: self.cfg.set("show_player", not self.cfg["show_player"]),
                 checked=lambda _: self.cfg["show_player"]),
            Menu.SEPARATOR,
            Item("Settings…", lambda: self._open_settings()),
            Item("Copy browser pairing code", lambda: self._copy_token()),
            Item("Open config folder", lambda: os.startfile(config_dir()) if os.name == "nt" else None),
            Item("Quit Sema", lambda: self.quit()),
        )
        self.icon = pystray.Icon("Sema", _icon_image(), "Sema – press " + hk["read"] + " to read", menu)
        self.icon.run_detached()

    def quit(self):
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        if self.icon:
            self.icon.stop()
        self.engine.shutdown()
        self.bridge.call(self.root.quit)

    def run(self):
        if self.cfg["server"]["enabled"]:
            server.start(self.engine)
        self.register_hotkeys()
        self.build_tray()
        hk = self.cfg["hotkeys"]["read"].upper()
        self.bridge.call(self.player.handle, {"type": "notice", "message": f"Sema is ready. Select text and press {hk}."})
        self.root.mainloop()


def _single_instance() -> bool:
    if os.name != "nt":
        return True
    ctypes.windll.kernel32.CreateMutexW(None, False, "Sema.SingleInstance")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main():
    config_dir().mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(config_dir() / "sema.log", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    if not _single_instance():
        print("Sema is already running (look for the tray icon).")
        return
    capture.enable_dpi_awareness()
    SemaApp().run()
