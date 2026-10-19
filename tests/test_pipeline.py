import io
import threading
import wave

import numpy as np
import pytest

from sema import audio
from sema.chunker import chunk_text, split_sentences
from sema.config import Config
from sema.context import detect_kind, prepare, repair_layout
from sema.engine import Engine
from sema.voices import BACKENDS, SynthResult, VoiceError
from sema.voices.azure import AzureBackend
from sema.voices.base import Backend, SynthRequest


def wav_bytes(seconds=0.2, sr=24000, freq=220.0):
    t = np.arange(int(sr * seconds)) / sr
    pcm = (np.sin(2 * np.pi * freq * t) * 12000).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm)
    return buf.getvalue()


# ---------------------------------------------------------------- context

def test_repair_layout_joins_wrapped_lines_and_dehyphenates():
    src = "The quick brown fox jumped over the beauti-\nful lazy dog and kept\nrunning.\n\n12\n\nNext paragraph here."
    assert repair_layout(src) == "The quick brown fox jumped over the beautiful lazy dog and kept running.\n\nNext paragraph here."


def test_repair_layout_lists():
    out = repair_layout("Agenda\n- Budget review\n- Hiring plan\n- Q4 goals")
    assert out == "Agenda.\n\nBudget review.\n\nHiring plan.\n\nQ4 goals."


def test_email_strips_quotes_and_noise():
    src = ("From: Jane Doe <jane@acme.com>\nSubject: Launch plan\n\nHi Sam,\nThe launch moves to Friday.\n\n"
           "Best,\nJane\nSent from my iPhone\n\nOn Mon, Oct 12, 2026 at 9:00 AM Sam wrote:\n> old stuff")
    p = prepare(src)
    assert p.kind == "email"
    assert p.text.startswith("Message from Jane Doe.\n\nSubject: Launch plan.")
    assert "Hi Sam. The launch" in p.text
    assert "old stuff" not in p.text and "iPhone" not in p.text


def test_kinds():
    assert detect_kind("def f(x):\n    return x;\nimport os\nclass A: {}\n") == "code"
    assert detect_kind("WASHINGTON (Reuters) - Officials said on Monday the bill passed.") == "news"
    p = prepare("Congratulations!!! We won the award! Amazing work everyone!")
    assert p.mood == "excited" and "upbeat" in p.instructions


# ---------------------------------------------------------------- chunking

def test_sentences_and_chunks():
    assert split_sentences('He left. "Why?" she asked. It was 9 p.m. Then rain.') == \
        ["He left.", '"Why?" she asked.', "It was 9 p.m.", "Then rain."]
    text = "First sentence is short. " + " ".join(f"Sentence number {i} goes here." for i in range(40))
    chunks = chunk_text(text + "\n\nNew paragraph.")
    assert len(chunks[0].text) <= 180
    assert all(len(c.text) <= 520 for c in chunks)
    assert chunks[-1].text == "New paragraph."
    assert chunks[-2].pause_after_ms > 0 and chunks[-1].pause_after_ms == 0


# ---------------------------------------------------------------- audio

def test_decode_and_stretch():
    x = audio.decode(wav_bytes(1.0))
    assert abs(len(x) - audio.SAMPLE_RATE) < 200
    y = audio.time_stretch(x, 1.5)
    assert abs(len(y) - len(x) / 1.5) < 50
    # pitch preserved: dominant frequency stays ~220 Hz
    spec = np.abs(np.fft.rfft(y[2000:-2000]))
    freq = np.argmax(spec) * audio.SAMPLE_RATE / len(y[2000:-2000])
    assert 200 < freq < 240


# ---------------------------------------------------------------- engine

class FakePlayer:
    def __init__(self):
        self.played = []
        self.paused = False

    def play(self, samples, cancel):
        self.played.append(len(samples))
        return not cancel.is_set()

    def clear(self): pass
    def pause(self): self.paused = True
    def resume(self): self.paused = False
    def close(self): pass


class Flaky(Backend):
    name = "flaky"
    label = "Flaky"

    def default_voice(self): return "v"

    async def synthesize(self, req):
        raise VoiceError("down")


class Good(Backend):
    name = "good"
    label = "Good"
    seen: list = []

    def default_voice(self): return "g"

    async def synthesize(self, req: SynthRequest):
        Good.seen.append(req)
        return SynthResult(wav_bytes(), 1.0, "wav")


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setitem(BACKENDS, "flaky", Flaky)
    monkeypatch.setitem(BACKENDS, "good", Good)
    cfg = Config(tmp_path / "c.json")
    cfg.data.update(backend="flaky", fallback_order=["good"])
    events = []
    done = threading.Event()

    def on(ev):
        events.append(ev)
        if ev["type"] in ("finished", "error"):
            done.set()
    eng = Engine(cfg, player=FakePlayer(), on_event=on)
    yield eng, events, done
    eng.shutdown()


def test_engine_reads_with_fallback_and_context(engine):
    eng, events, done = engine
    Good.seen.clear()
    eng.speak("From: Ana\nSubject: Hello\n\nHi Bo,\nIt costs $5. See you at 3pm.")
    assert done.wait(10)
    texts = [e["text"] for e in events if e["type"] == "chunk"]
    assert texts[0] == "Message from Ana."
    assert "five dollars" in " ".join(texts) and "three PM" in " ".join(texts)
    assert any(e["type"] == "warning" for e in events)       # fell back from flaky
    assert Good.seen[1].previous_text == "Message from Ana."
    assert Good.seen[0].kind == "email" and "colleague" in Good.seen[0].instructions
    assert eng.state == "idle"


def test_engine_segments_keep_ids(engine):
    eng, events, done = engine
    eng.speak(segments=[{"id": "s1", "text": "Hello there."}, {"id": "s2", "text": "Version 2 is out."}])
    assert done.wait(10)
    assert [e["segment"] for e in events if e["type"] == "chunk"] == ["s1", "s2"]


def test_azure_ssml_style():
    b = AzureBackend({"api_key": "x"})
    ssml = b.build_ssml(SynthRequest("Tom & Jerry <3", "en-US-AriaNeural", azure_style="newscast"), 1.2)
    assert 'style="newscast"' in ssml and "Tom &amp; Jerry &lt;3" in ssml and 'rate="+20%"' in ssml
