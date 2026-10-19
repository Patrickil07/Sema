"""Screen capture + OCR for text that has no accessible text layer
(images, PDFs, video, canvas apps like Google Docs, remote desktops...)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class Line:
    text: str
    x: int
    y: int
    w: int
    h: int


def grab(left: int, top: int, width: int, height: int):
    """Return a PIL image of a screen region (physical pixels)."""
    import mss
    from PIL import Image
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _prep(img, min_height: int = 900):
    # Windows OCR is far more accurate on larger glyphs; upscale small captures
    scale = 1
    while img.height * scale < min_height and scale < 3:
        scale += 1
    if scale > 1:
        from PIL import Image
        img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    return img, scale


async def _windows_ocr(img) -> list[Line]:
    try:
        from winsdk.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.storage.streams import DataWriter
    except ImportError:
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("No Windows OCR language installed (Settings > Time & language > Language)")
    rgba = img.convert("RGBA")
    r, g, b, a = rgba.split()
    from PIL import Image
    bgra = Image.merge("RGBA", (b, g, r, a)).tobytes()
    writer = DataWriter()
    writer.write_bytes(bgra)
    bmp = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8,
                                                 img.width, img.height, BitmapAlphaMode.PREMULTIPLIED)
    result = await engine.recognize_async(bmp)
    lines = []
    for ln in result.lines:
        rects = [w.bounding_rect for w in ln.words]
        x0 = min(r.x for r in rects)
        y0 = min(r.y for r in rects)
        x1 = max(r.x + r.width for r in rects)
        y1 = max(r.y + r.height for r in rects)
        lines.append(Line(ln.text, int(x0), int(y0), int(x1 - x0), int(y1 - y0)))
    return lines


def _tesseract_ocr(img) -> list[Line]:
    import pytesseract
    d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    groups: dict = {}
    for i, word in enumerate(d["text"]):
        if not word.strip():
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        groups.setdefault(key, []).append(i)
    lines = []
    for idx in groups.values():
        x0 = min(d["left"][i] for i in idx)
        y0 = min(d["top"][i] for i in idx)
        x1 = max(d["left"][i] + d["width"][i] for i in idx)
        y1 = max(d["top"][i] + d["height"][i] for i in idx)
        lines.append(Line(" ".join(d["text"][i] for i in idx), x0, y0, x1 - x0, y1 - y0))
    return sorted(lines, key=lambda ln: (ln.y, ln.x))


def recognize(img) -> list[Line]:
    """OCR lines in image coordinates."""
    big, scale = _prep(img)
    try:
        lines = asyncio.run(_windows_ocr(big))
    except Exception:
        lines = _tesseract_ocr(big)
    for ln in lines:
        ln.x, ln.y, ln.w, ln.h = ln.x // scale, ln.y // scale, ln.w // scale, ln.h // scale
    return lines


def split_columns(lines: list[Line]) -> list[list[Line]]:
    """Split side-by-side panels (a chat next to a side panel, newspaper columns) so each is
    read top to bottom in turn, instead of reading across both on every line."""
    if len(lines) < 6:
        return [lines]
    right = max(ln.x + ln.w for ln in lines)
    covered = bytearray(right + 1)
    for ln in lines:
        covered[ln.x: ln.x + ln.w] = b"\x01" * ln.w
    min_gap = max(18, right // 50)
    cuts, run_start = [], None
    for x in range(right + 1):
        if not covered[x]:
            run_start = x if run_start is None else run_start
        elif run_start is not None:
            if x - run_start >= min_gap:
                cuts.append((run_start + x) // 2)
            run_start = None
    groups = []
    edges = [0, *cuts, right + 1]
    for a, b in zip(edges, edges[1:]):
        col = [ln for ln in lines if a <= ln.x + ln.w / 2 < b]
        if col:
            groups.append(col)
    # stray labels (a lone number, an icon caption) don't make a column: fold them into a neighbour
    merged: list[list[Line]] = []
    for col in groups:
        if merged and (len(col) < 3 or len(merged[-1]) < 3):
            merged[-1] = merged[-1] + col
        else:
            merged.append(col)
    return merged


def lines_to_text(lines: list[Line]) -> str:
    """Rebuild paragraphs from OCR lines using vertical gaps, column by column."""
    if not lines:
        return ""
    columns = split_columns(lines)
    if len(columns) > 1:
        return "\n\n".join(_column_text(c) for c in columns)
    return _column_text(lines)


def _column_text(lines: list[Line]) -> str:
    if not lines:
        return ""
    lines = sorted(lines, key=lambda ln: (ln.y, ln.x))
    heights = sorted(ln.h for ln in lines)
    typical = heights[len(heights) // 2] or 10
    out = [lines[0].text]
    for prev, ln in zip(lines, lines[1:]):
        gap = ln.y - (prev.y + prev.h)
        out.append("\n\n" if gap > typical * 0.9 else "\n")
        out.append(ln.text)
    return "".join(out)


def paragraph_at(lines: list[Line], px: int, py: int) -> str:
    """The paragraph under (or nearest to) a point, for read-under-mouse via OCR."""
    if not lines:
        return ""
    lines = sorted(lines, key=lambda ln: (ln.y, ln.x))
    dist = lambda ln: abs((ln.y + ln.h / 2) - py) + (0 if ln.x <= px <= ln.x + ln.w else 40)  # noqa: E731
    i = min(range(len(lines)), key=lambda k: dist(lines[k]))
    typical = sorted(ln.h for ln in lines)[len(lines) // 2] or 10
    lo = hi = i
    while lo > 0 and lines[lo].y - (lines[lo - 1].y + lines[lo - 1].h) < typical * 0.9:
        lo -= 1
    while hi + 1 < len(lines) and lines[hi + 1].y - (lines[hi].y + lines[hi].h) < typical * 0.9:
        hi += 1
    return lines_to_text(lines[lo:hi + 1])


def read_region(left: int, top: int, width: int, height: int) -> str:
    return lines_to_text(recognize(grab(left, top, width, height)))


def read_around(px: int, py: int, width: int = 1100, height: int = 360) -> str:
    left, top = px - width // 2, py - height // 2
    try:
        import mss
        with mss.mss() as sct:
            v = sct.monitors[0]
        left = max(v["left"], min(left, v["left"] + v["width"] - width))
        top = max(v["top"], min(top, v["top"] + v["height"] - height))
    except Exception:
        pass
    lines = recognize(grab(left, top, width, height))
    return paragraph_at(lines, px - left, py - top)
