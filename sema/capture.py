"""Getting text from whatever is on screen (Windows).

Order of attempts, best first:
  1. App-specific: Word and Outlook through their COM object models (exact text,
     whole documents/messages, knows where the cursor is).
  2. UI Automation: the accessibility tree that Chrome, Edge, Office, PDF readers
     and most Windows apps expose (selection, text under the mouse, documents).
  3. Clipboard: simulate Ctrl+C for the selection, then restore the clipboard.
  4. OCR: for pixels with no text behind them (images, video, canvas, RDP).
"""
from __future__ import annotations

import ctypes
import logging
import os
import time

log = logging.getLogger("sema")

BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "arc.exe"}


def foreground_process() -> str:
    try:
        import psutil
        import win32gui
        import win32process
        _, pid = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


def cursor_pos() -> tuple[int, int]:
    import ctypes.wintypes
    pt = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def source_for(proc: str) -> str:
    if proc == "outlook.exe" or proc == "olk.exe":
        return "outlook"
    if proc == "winword.exe":
        return "word"
    if proc in BROWSERS:
        return "browser"
    return proc.removesuffix(".exe")


# --------------------------------------------------------------------------- Office COM

def _office(prog_id: str):
    import win32com.client
    return win32com.client.GetActiveObject(prog_id)


def word_selection_or_rest() -> str:
    """Selected text in Word; with no selection, from the cursor to the end of the document."""
    word = _office("Word.Application")
    sel = word.Selection
    if sel.Start != sel.End:
        return sel.Text
    doc = word.ActiveDocument
    return doc.Range(sel.Start, doc.Content.End).Text


def word_paragraph_at_cursor() -> str:
    word = _office("Word.Application")
    return word.Selection.Paragraphs(1).Range.Text


def outlook_message() -> str:
    """The open or selected email, with sender and subject."""
    ol = _office("Outlook.Application")
    item = None
    insp = ol.ActiveInspector()
    if insp is not None:
        item = insp.CurrentItem
    else:
        sel = ol.ActiveExplorer().Selection
        if sel.Count:
            item = sel.Item(1)
    if item is None:
        return ""
    sender = getattr(item, "SenderName", "") or ""
    subject = getattr(item, "Subject", "") or ""
    body = getattr(item, "Body", "") or ""
    return f"From: {sender}\nSubject: {subject}\n\n{body}"


# --------------------------------------------------------------------------- UI Automation

def _uia():
    import uiautomation as auto
    return auto


def _text_pattern(ctrl, depth: int = 6):
    auto = _uia()
    while ctrl is not None and depth:
        try:
            if ctrl.GetPattern(auto.PatternId.TextPattern):
                return ctrl.GetTextPattern(), ctrl
        except Exception:
            pass
        ctrl = ctrl.GetParentControl()
        depth -= 1
    return None, None


def uia_selection() -> str:
    auto = _uia()
    tp, _ = _text_pattern(auto.GetFocusedControl())
    if not tp:
        return ""
    try:
        return "\n".join(r.GetText(-1) for r in tp.GetSelection()).strip()
    except Exception:
        return ""


def uia_document_from_cursor() -> str:
    """Focused document text from the caret/selection start to the end."""
    auto = _uia()
    tp, _ = _text_pattern(auto.GetFocusedControl())
    if not tp:
        return ""
    doc = tp.DocumentRange
    try:
        sel = tp.GetSelection()
        if sel:
            rng = sel[0].Clone()
            rng.MoveEndpointByRange(auto.TextPatternRangeEndpoint.End, doc, auto.TextPatternRangeEndpoint.End)
            text = rng.GetText(-1)
            if text.strip():
                return text
    except Exception:
        pass
    return doc.GetText(-1)


def uia_text_at(x: int, y: int) -> str:
    """Paragraph under the mouse via UI Automation, or the element's own label."""
    auto = _uia()
    ctrl = auto.ControlFromPoint(x, y)
    if ctrl is None:
        return ""
    tp, _ = _text_pattern(ctrl, depth=8)
    if tp:
        try:
            rng = tp.RangeFromPoint(x, y)
            rng.ExpandToEnclosingUnit(auto.TextUnit.Paragraph)
            text = rng.GetText(-1).strip()
            if len(text) > 1:
                return text
        except Exception:
            pass
    name = (ctrl.Name or "").strip()
    return name if len(name) > 2 else ""


# --------------------------------------------------------------------------- clipboard

def _wait_modifiers_released(timeout: float = 1.0):
    import keyboard
    end = time.time() + timeout
    while time.time() < end and any(keyboard.is_pressed(k) for k in ("alt", "shift", "ctrl", "windows")):
        time.sleep(0.02)


def clipboard_text() -> str:
    import win32clipboard as cb
    for _ in range(10):
        try:
            cb.OpenClipboard()
            break
        except Exception:
            time.sleep(0.03)
    else:
        return ""
    try:
        if cb.IsClipboardFormatAvailable(cb.CF_UNICODETEXT):
            return cb.GetClipboardData(cb.CF_UNICODETEXT)
        return ""
    finally:
        cb.CloseClipboard()


def _set_clipboard(text: str | None):
    import win32clipboard as cb
    try:
        cb.OpenClipboard()
        cb.EmptyClipboard()
        if text:
            cb.SetClipboardData(cb.CF_UNICODETEXT, text)
    except Exception:
        pass
    finally:
        try:
            cb.CloseClipboard()
        except Exception:
            pass


def copy_selection() -> str:
    """Press Ctrl+C in the foreground app and read the result, restoring the old clipboard text."""
    import keyboard
    _wait_modifiers_released()
    before = clipboard_text()
    seq = ctypes.windll.user32.GetClipboardSequenceNumber()
    keyboard.send("ctrl+c")
    end = time.time() + 0.6
    while time.time() < end and ctypes.windll.user32.GetClipboardSequenceNumber() == seq:
        time.sleep(0.02)
    if ctypes.windll.user32.GetClipboardSequenceNumber() == seq:
        return ""
    text = clipboard_text()
    _set_clipboard(before)
    return text.strip()


# --------------------------------------------------------------------------- high level

def get_selection() -> tuple[str, str]:
    """(text, source) for the current selection in the foreground app."""
    proc = foreground_process()
    src = source_for(proc)
    try:
        if src == "word":
            sel = _office("Word.Application").Selection
            if sel.Start != sel.End:
                return sel.Text, src
    except Exception as e:
        log.debug("word selection: %s", e)
    text = ""
    try:
        text = uia_selection()
    except Exception as e:
        log.debug("uia selection: %s", e)
    if not text:
        text = copy_selection()
    return text, src


def get_document() -> tuple[str, str]:
    """Whole document/message from the cursor."""
    proc = foreground_process()
    src = source_for(proc)
    try:
        if src == "word":
            return word_selection_or_rest(), src
        if src == "outlook":
            text = outlook_message()
            if text:
                return text, src
    except Exception as e:
        log.debug("office document: %s", e)
    try:
        return uia_document_from_cursor(), src
    except Exception as e:
        log.debug("uia document: %s", e)
    return "", src


def get_text_under_mouse() -> tuple[str, str]:
    x, y = cursor_pos()
    src = source_for(foreground_process())
    text = ""
    try:
        text = uia_text_at(x, y)
    except Exception as e:
        log.debug("uia point: %s", e)
    if len(text) < 3:
        from . import ocr
        try:
            text = ocr.read_around(x, y)
            src = "ocr"
        except Exception as e:
            log.warning("ocr failed: %s", e)
    return text, src


def enable_dpi_awareness():
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
