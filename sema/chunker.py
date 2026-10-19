"""Split prepared text into speakable chunks.

The first chunk is kept short so speech starts almost instantly; later chunks are
larger so expressive voices get enough context for natural prosody. Paragraph
breaks become real pauses in playback instead of relying on the voice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# words that end in a period but don't end a sentence (left over after normalization)
_NO_BREAK = re.compile(r"(?:\b[A-Z]|\b(?:Inc|Ltd|Co|Corp|vs|Mt|al|U\.S|U\.K|e\.g|i\.e))\.$")


@dataclass
class Chunk:
    text: str
    segment: int | str = 0      # id of the source segment (sentence/paragraph) for highlighting
    pause_after_ms: int = 0


def split_sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])([\"')\]]*)\s+(?=[\"'(\[]?[A-Z0-9¿¡À-ɏЀ-ӿ])", paragraph)
    sentences: list[str] = []
    buf = ""
    # re.split with a capture group yields [text, closer, text, closer, ...]
    for i in range(0, len(parts), 2):
        piece = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
        buf = (buf + " " + piece).strip() if buf else piece.strip()
        if not _NO_BREAK.search(buf):
            sentences.append(buf)
            buf = ""
    if buf:
        sentences.append(buf)
    return [s for s in sentences if s.strip()]


def _split_long(sentence: str, limit: int) -> list[str]:
    if len(sentence) <= limit:
        return [sentence]
    out, cur = [], ""
    for piece in re.split(r"(?<=[,;:])\s+", sentence):
        if cur and len(cur) + len(piece) + 1 > limit:
            out.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip()
    if cur:
        out.append(cur)
    final = []
    for p in out:  # still too long (no punctuation): hard wrap on words
        while len(p) > limit:
            cut = p.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            final.append(p[:cut])
            p = p[cut:].strip()
        final.append(p)
    return final


def chunk_text(text: str, first_limit: int = 180, limit: int = 520,
               paragraph_pause_ms: int = 380, sentence_chunks: bool = False) -> list[Chunk]:
    """Chunks for free-form text. Segment ids are sentence indexes."""
    chunks: list[Chunk] = []
    seg = 0
    for paragraph in [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]:
        sentences = []
        for s in split_sentences(paragraph.replace("\n", " ")):
            sentences.extend(_split_long(s, limit))
        cur, cur_seg = "", seg
        for s in sentences:
            cap = first_limit if not chunks else limit
            if cur and (sentence_chunks or len(cur) + len(s) + 1 > cap):
                chunks.append(Chunk(cur, cur_seg))
                cur = ""
            if not cur:
                cur_seg = seg
            cur = f"{cur} {s}".strip()
            seg += 1
        if cur:
            chunks.append(Chunk(cur, cur_seg))
        if chunks:
            chunks[-1].pause_after_ms = paragraph_pause_ms
    if chunks:
        chunks[-1].pause_after_ms = 0
    return chunks
