"""Structured reading of app screens (chat panes, numbered instructions, UI clutter)."""
from pathlib import Path

from sema.chunker import chunk_text
from sema.context import prepare
from sema.normalize import normalize
from sema.ocr import Line, lines_to_text

FIXTURE = Path(__file__).parent / "fixtures" / "chat_app_ocr.txt"


def spoken(text, source=""):
    return [c.text for c in chunk_text(normalize(prepare(text, source).text), sentence_chunks=True)]


def test_side_by_side_panels_are_read_one_after_the_other():
    lines = [Line("Left one is here", 10, 10, 300, 20), Line("Right A", 500, 12, 200, 20),
             Line("left two", 10, 40, 280, 20), Line("Right B", 500, 42, 220, 20),
             Line("left three", 10, 70, 250, 20), Line("Right C", 500, 72, 180, 20)]
    assert lines_to_text(lines) == "Left one is here\nleft two\nleft three\n\nRight A\nRight B\nRight C"


def test_chat_screenshot_reads_like_a_person():
    out = spoken(FIXTURE.read_text(encoding="utf-8"), "ocr")
    text = " ".join(out)
    for clutter in ("Sent to", "Forwarded by", "ago", "G@oa", "EY"):
        assert clutter not in text
    assert "Five steps." in out
    assert [s for s in out if s.startswith("Step ")] == [f"Step {w}." for w in ("one", "two", "three", "four", "five")]
    assert "Install Python three point twelve from python dot org." in out
    assert "Unzip it somewhere like C drive, Sema." in out
    assert "press Alt Shift S" in text and "Code, then Download ZIP" in text
    assert "App Data, Sema, sema dot log" in text
    # the two chat messages stay separate instead of running together
    assert not any("aspect" in s and "taking" in s for s in out)


def test_numbered_lists_only_become_steps_for_instructions():
    steps = spoken("To start:\n1. Open the app\n2. Click Settings\n3. Choose a voice")
    assert steps[:3] == ["To start:", "Three steps.", "Step one."]
    cities = spoken("The best cities to visit this year are:\n1. Paris\n2. Lagos\n3. Tokyo")
    assert "Step" not in " ".join(cities) and "one. Paris. two. Lagos." in " ".join(cities)
