"""Context engine: understand what kind of text this is and how it should sound.

Text grabbed off a screen is messy: OCR breaks lines mid-sentence, PDFs hyphenate
words across lines, emails drag along quoted replies and legal disclaimers, lists
lose their structure. This module repairs the layout, decides what the text *is*
(email, news, story, technical, list, code, dialogue) and produces a delivery
direction that expressive voices (OpenAI, ElevenLabs, Azure styles) can follow.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

KINDS = ("email", "news", "narrative", "technical", "list", "code", "dialogue", "general")

STYLE_DIRECTIONS = {
    "email": "Read like a thoughtful colleague reading a message aloud: warm, conversational, "
             "clear. Pause briefly after the greeting and before the sign-off.",
    "news": "Read like an experienced news presenter: confident, well-paced, authoritative, "
            "with natural emphasis on names, numbers and key facts.",
    "narrative": "Read like an audiobook narrator: warm, immersive and expressive, following the "
                 "emotional arc of the story. Give dialogue a natural, lightly acted delivery.",
    "technical": "Read like a patient expert explaining: clear, measured and precise. Slow down "
                 "slightly on terms, numbers and steps so they are easy to follow.",
    "list": "Read each item as a distinct point with a short pause between items, keeping a "
            "clear, even rhythm.",
    "code": "Read calmly and literally, pausing between statements.",
    "dialogue": "Read expressively, giving each speaker's lines natural emotion and rhythm.",
    "general": "Read naturally and clearly, like a skilled human reader who understands the text, "
               "with sensible pacing and emphasis.",
}

# Azure neural "express-as" styles (only used for voices that support them)
AZURE_STYLES = {"email": "chat", "news": "newscast", "narrative": None, "technical": None,
                "list": None, "code": None, "dialogue": None, "general": None}


@dataclass
class Prepared:
    text: str
    kind: str
    direction: str
    mood: str = "neutral"
    azure_style: str | None = None
    meta: dict = field(default_factory=dict)

    @property
    def instructions(self) -> str:
        extra = {"excited": " The tone is upbeat and energetic; let that come through.",
                 "serious": " The tone is serious and sensitive; keep the delivery calm and respectful.",
                 "urgent": " The message is urgent; sound focused and direct without shouting."}
        return self.direction + extra.get(self.mood, "")


# --------------------------------------------------------------------------- layout repair

_BULLET = re.compile(r"^\s*(?:[-*•▪●◦‣∙·]|\(?\d{1,3}[.)]|\(?[a-zA-Z][.)])\s+")
_SENT_END = re.compile(r"[.!?:;\"'”)\]]$")


def repair_layout(text: str) -> str:
    """Re-flow hard-wrapped/OCR text while keeping paragraphs, headings and list items."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n\s*([a-z])", r"\1\2", text)          # de-hyphenate line breaks
    lines = [ln.rstrip() for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue
        if re.fullmatch(r"(?:page\s*)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?", stripped, re.I):
            continue                                              # page numbers
        if _BULLET.match(stripped):
            num = re.match(r"^\s*\(?(\d{1,3})[.)]\s+", stripped)
            item = _BULLET.sub("", stripped)
            if out and out[-1] != "":
                if not _SENT_END.search(out[-1]) and not out[-1].endswith(","):
                    out[-1] += "."
                out.append("")
            out.append((f"\ue000{num.group(1)}\ue001" if num else "") + item)
            continue
        if out and out[-1] != "":
            prev = out[-1]
            short_heading = len(prev) < 60 and not _SENT_END.search(prev) and stripped[:1].isupper() \
                and len(prev.split()) <= 8 and prev[:1].isupper()
            if short_heading and _looks_heading(prev) and not prev.endswith(","):
                out[-1] = prev + "."
                out.append("")
                out.append(stripped)
                continue
            if not _SENT_END.search(prev) or stripped[:1].islower():
                out[-1] = prev + " " + stripped                    # wrapped line: join
                continue
            if len(prev) < 45 and _SENT_END.search(prev):
                out.append("")                                     # short line ending a sentence
        out.append(stripped)
    text = "\n".join(out)
    text = re.sub(r"\n{2,}", "\n\n", text)
    paragraphs = [re.sub(r"\n", " ", p).strip() for p in text.split("\n\n")]
    paragraphs = [p if _SENT_END.search(p) else p + "." for p in paragraphs if p]
    return _number_lists("\n\n".join(paragraphs))


_IMPERATIVE = set("""get install open click double-click right-click try run select go add copy paste choose
download enable disable turn press type enter set create sign log make use restart check save connect
unzip extract launch start close tick untick remove delete find look visit follow drag drop load
update upgrade wait confirm review read write send call email fill submit pick switch keep""".split())


_COUNT_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
                10: "Ten", 11: "Eleven", 12: "Twelve"}


def _number_lists(text: str) -> str:
    """Numbered items read as "Step 1." when the list is a set of instructions, else "1."."""
    paras = text.split("\n\n")
    out, i = [], 0
    while i < len(paras):
        if not paras[i].startswith("\ue000"):
            out.append(paras[i])
            i += 1
            continue
        j = i
        while j < len(paras) and paras[j].startswith("\ue000"):
            j += 1
        items = paras[i:j]
        firsts = [re.sub(r"^\ue000\d+\ue001\W*", "", p).split(" ")[0].lower().strip(".:,") for p in items]
        steps = sum(f in _IMPERATIVE for f in firsts) * 2 >= len(items)
        if steps and len(items) >= 2:
            out.append(f"{_COUNT_WORDS.get(len(items), len(items))} steps.")
        for p in items:
            out.append(re.sub(r"^\ue000(\d+)\ue001", (r"Step \1. " if steps else r"\1. "), p))
        i = j
    return "\n\n".join(out)


# Interface text that appears around content in apps and chats, never worth reading aloud
_UI_CHROME = re.compile(r"""^(?:
      sent\ to\ ?(?:a|\d+)\ threads?|forwarded\ by\ \w+|edited|copied|copy(?:\ link|\ code)?|reply|
      replies|share|like|react|more|show\ (?:more|less)|see\ more|read\ more|load\ more|view\ \d*\ ?(?:more\ )?replies|
      \d+\s?(?:s|m|h|d|w|min|mins|hr|hrs)\ ago|(?:a\ few\ |\d+\ )?(?:seconds?|minutes?|hours?|days?|weeks?)\ ago|
      just\ now|yesterday|today|seen|delivered|typing…?|
      (?:zip|pdf|docx?|xlsx?|pptx?|png|jpe?g|csv|txt|md)|
      [\w\-. ]{1,60}\.(?:zip|pdf|docx?|xlsx?|pptx?|png|jpe?g|csv|txt|md|exe)
    )$""", re.I | re.X)


def strip_ui_chrome(text: str) -> str:
    """Drop lines that are app interface rather than content: "Sent to a thread", "19m ago",
    attachment chips, button labels. Only whole lines are removed, never words inside sentences.
    A removed line also separates what came before from what follows (two chat messages)."""
    keep = []
    for ln in text.split("\n"):
        core = re.sub(r"^[\W_]+|[\W_]+$", "", ln.strip())
        # icons in front of the label often OCR as 1-3 junk characters: "3 Sent to a thread"
        core2 = re.sub(r"^(?:\S{1,3}\s+)(?=[A-Za-z\d])", "", core)
        if core and (_UI_CHROME.match(core) or _UI_CHROME.match(core2)):
            keep.append("")
            continue
        keep.append(ln)
    return "\n".join(keep)


def clean_ocr(text: str) -> str:
    """Repair what screen OCR adds: icon glyphs read as letters, lost list numbers, stray marks."""
    out = []
    last_num = None
    for ln in text.split("\n"):
        s = ln.strip()
        letters = len(re.findall(r"[A-Za-z]", s))
        if s and (not re.search(r"[A-Za-z]{3,}", s) or letters < len(s) * 0.4) and not re.search(r"\d", s):
            continue                                       # "G@oa-", "EY": icons, not text
        if last_num is not None and re.match(r"^[.,·]\s+[A-Z]", s):
            last_num += 1                                  # "1." survived but "2." became "."
            s = re.sub(r"^[.,·]\s+", f"{last_num}. ", s)
        s = re.sub(r"^[^\w\s\"'(]{1,2}\s+", "", s)            # leading icon glyph
        s = re.sub(r"^[a-z]\s+(?=[A-Z])", "", s)              # "e Language learning mode"
        s = re.sub(r"(?<=\w)\s+(?:[®©#•]|e)\s+(?=[A-Z\w])", " ", s)  # inline link/file icons
        s = re.sub(r"(?<=[A-Za-z])\s>\s(?=[A-Z])", " → ", s)   # menu paths: Code > Download ZIP
        s = re.sub(r"\b(chrome|edge)\s?:\s?//", r"\1://", s)
        s = re.sub(r"\s&\s(?=[\w-]+\.\w)", " ", s)              # file icon before a file name
        s = re.sub(r"(\w)(?:\s\.|\.\s)(bat|exe|zip|md|log|txt|pdf|docx|xlsx|pptx)\b", r"\1.\2", s)
        m = re.match(r"^(\d{1,2})[.)]\s", s)
        if m:
            last_num = int(m.group(1))
        out.append(s)
    return "\n".join(out)


def _looks_heading(line: str) -> bool:
    words = line.split()
    caps = sum(w[:1].isupper() for w in words)
    return line.isupper() or caps >= max(1, len(words) - 1)


# --------------------------------------------------------------------------- email

_QUOTE_STARTS = [
    re.compile(r"^On .{5,200}wrote:\s*$", re.M | re.S),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.M | re.I),
    re.compile(r"^_{5,}\s*$", re.M),
    re.compile(r"^From:\s.+\n(?:Sent|Date):\s.+\n", re.M),
    re.compile(r"^Le .{5,200}a écrit\s*:", re.M),
    re.compile(r"^Am .{5,200}schrieb", re.M),
]
_SIGNOFF_NOISE = [
    re.compile(r"^Sent from my (?:iPhone|iPad|Android|Galaxy|Samsung|mobile).*$", re.M | re.I),
    re.compile(r"^Get Outlook for (?:iOS|Android).*$", re.M | re.I),
    re.compile(r"(?:^|\n)(?:CONFIDENTIALITY|DISCLAIMER|This (?:e-?mail|message) (?:and any attachments )?"
               r"(?:is|are|may be|contains) (?:confidential|intended)).*", re.I | re.S),
    re.compile(r"\n-- ?\n.*", re.S),                                # RFC signature separator
]


def prepare_email(text: str, read_quoted: bool = False) -> tuple[str, dict]:
    meta: dict = {}
    head, body = _split_headers(text)
    meta.update(head)
    if not read_quoted:
        cut = min((m.start() for p in _QUOTE_STARTS if (m := p.search(body))), default=None)
        if cut is not None and cut > 0:
            body = body[:cut]
            meta["quoted_history_skipped"] = True
        body = "\n".join(ln for ln in body.split("\n") if not ln.lstrip().startswith(">"))
    for p in _SIGNOFF_NOISE:
        body = p.sub("", body)
    intro = []
    if head.get("from"):
        intro.append(f"Message from {head['from']}.")
    if head.get("subject"):
        intro.append(f"Subject: {head['subject'].rstrip('.')}.")
    body = repair_layout(body)
    # greeting gets its own beat: "Hi Sam," -> "Hi Sam."
    body = re.sub(r"^((?:Hi|Hello|Hey|Dear|Good (?:morning|afternoon|evening))\b[^\n,.!]{0,40}),\s*",
                  r"\1. ", body, flags=re.I)
    text = "\n\n".join(intro + [body]) if intro else body
    return text, meta


def _split_headers(text: str) -> tuple[dict, str]:
    head: dict = {}
    lines = text.strip("\n").split("\n")
    i = 0
    for i, ln in enumerate(lines[:12]):
        m = re.match(r"^(From|To|Cc|Subject|Date|Sent):\s*(.*)$", ln.strip(), re.I)
        if not m:
            break
        key = m.group(1).lower()
        val = m.group(2).strip()
        if key == "from":
            val = re.sub(r"\s*<[^>]+>", "", val).strip().strip('"')
        head[key] = val
    else:
        i += 1
    if not head:
        return {}, text
    return head, "\n".join(lines[i:])


# --------------------------------------------------------------------------- classification

def detect_kind(text: str, source: str = "") -> str:
    src = source.lower()
    if src in ("outlook", "email") or re.search(r"^(?:From|Subject):\s", text, re.M):
        return "email"
    sample = text[:4000]
    symbols = len(re.findall(r"[{}();=<>\[\]]", sample))
    lines = [ln for ln in sample.split("\n") if ln.strip()]
    if lines and symbols / max(1, len(sample)) > 0.04 and \
            sum(bool(re.search(r"[;{}]\s*$|^\s*(def|class|function|import|return|const|let|var|if|for)\b", ln))
                for ln in lines) >= max(2, len(lines) // 4):
        return "code"
    bullets = sum(bool(_BULLET.match(ln)) for ln in lines)
    if lines and bullets >= 3 and bullets >= len(lines) * 0.5:
        return "list"
    if re.search(r"^(?:Hi|Hello|Hey|Dear)\b.{0,40}[,!]\s*$", sample, re.M | re.I) and \
            re.search(r"^(?:Best|Thanks|Regards|Cheers|Sincerely|Kind regards|Best regards|Thank you)\b", sample, re.M | re.I):
        return "email"
    quotes = len(re.findall(r"[\"“”]", sample))
    said = len(re.findall(r"\b(?:said|asked|replied|whispered|shouted|muttered|cried)\b", sample, re.I))
    if quotes >= 6 and said >= 2:
        return "narrative" if len(sample) > 600 else "dialogue"
    if re.search(r"\((?:Reuters|AP|AFP|Bloomberg)\)|\b(?:reported|according to|officials said|spokesperson)\b",
                 sample, re.I):
        return "news"
    tech = len(re.findall(r"\b(?:install|configure|function|API|parameter|server|database|algorithm|"
                          r"click|select|settings|version|error|equation|theorem|figure|dataset|"
                          r"protocol|method|analysis|results)\b", sample, re.I))
    if tech >= 4 and tech / max(1, len(sample.split())) > 0.02:
        return "technical"
    if said >= 3 or re.search(r"\b(?:once upon a time|she felt|he felt|her eyes|his eyes)\b", sample, re.I):
        return "narrative"
    return "general"


def detect_mood(text: str) -> str:
    sample = text[:3000]
    words = max(1, len(sample.split()))
    if re.search(r"\b(?:urgent|asap|immediately|action required|deadline today|critical)\b", sample, re.I):
        return "urgent"
    if re.search(r"\b(?:passed away|condolences|sorry for your loss|tragic|funeral|diagnosis|"
                 r"killed|died|grief|mourning)\b", sample, re.I):
        return "serious"
    if sample.count("!") / words > 0.02 or re.search(r"\b(?:congratulations|amazing|thrilled|"
                                                      r"excited|celebrate|hooray)\b", sample, re.I):
        return "excited"
    return "neutral"


def prepare(text: str, source: str = "", kind: str | None = None, read_quoted_email: bool = False) -> Prepared:
    kind = kind or detect_kind(text, source)
    meta: dict = {}
    if kind == "email":
        text, meta = prepare_email(text, read_quoted=read_quoted_email)
    elif kind == "code":
        text = re.sub(r"\n\s*\n", "\n", text)
        text = "\n".join(ln.strip() + ("" if _SENT_END.search(ln.strip()) else ".")
                         for ln in text.split("\n") if ln.strip())
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)  # camelCase -> camel Case
        text = text.replace("_", " ")
    else:
        if source == "ocr":
            text = clean_ocr(text)
        text = repair_layout(strip_ui_chrome(text))
    mood = detect_mood(text)
    return Prepared(text=text, kind=kind, direction=STYLE_DIRECTIONS[kind], mood=mood,
                    azure_style=AZURE_STYLES.get(kind), meta=meta)
