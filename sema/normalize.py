"""Text normalization: turn written text into what a careful human reader would say.

Neural voices are good, but they still stumble on "$1.5M", "10/18/2026",
"Dr. Smith on Main St.", "Henry VIII", "3:05pm" or "e.g.". Every voice backend
gets the same normalized text, so delivery is consistent whichever voice is used.

Only English text gets number/abbreviation expansion. Other languages pass through
with light cleanup, and multilingual neural voices handle them natively.
"""
from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------- numbers

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand")]


def int_to_words(n: int) -> str:
    if n < 0:
        return "minus " + int_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return _ONES[hundreds] + " hundred" + (" " + int_to_words(rest) if rest else "")
    for value, name in _SCALES:
        if n >= value:
            head, rest = divmod(n, value)
            return int_to_words(head) + " " + name + (" " + int_to_words(rest) if rest else "")
    raise AssertionError(n)


_ORDINAL_IRREGULAR = {"one": "first", "two": "second", "three": "third", "five": "fifth",
                      "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}


def ordinal_words(n: int) -> str:
    words = int_to_words(n)
    m = re.search(r"([a-z]+)$", words)
    last = m.group(1)
    if last in _ORDINAL_IRREGULAR:
        new = _ORDINAL_IRREGULAR[last]
    elif last.endswith("y"):
        new = last[:-1] + "ieth"
    else:
        new = last + "th"
    return words[: m.start(1)] + new


def year_words(n: int) -> str:
    if 2000 <= n <= 2009:
        return int_to_words(n)
    if 1000 <= n <= 9999:
        hi, lo = divmod(n, 100)
        if lo == 0:
            return int_to_words(hi) + " hundred"
        if lo < 10:
            return int_to_words(hi) + " oh " + int_to_words(lo)
        return int_to_words(hi) + " " + int_to_words(lo)
    return int_to_words(n)


def digits_words(s: str) -> str:
    return " ".join(_ONES[int(d)] for d in s if d.isdigit())


def number_words(s: str) -> str:
    """'1,234.56' -> 'one thousand two hundred thirty-four point five six'."""
    s = s.replace(",", "")
    neg = s.startswith("-")
    s = s.lstrip("-+")
    if "." in s:
        whole, frac = s.split(".", 1)
        out = (int_to_words(int(whole)) if whole else "zero") + " point " + digits_words(frac)
    else:
        out = int_to_words(int(s))
    return ("minus " + out) if neg else out


def _plural(word: str, amount_is_one: bool) -> str:
    if amount_is_one:
        return word
    irregular = {"foot": "feet", "inch": "inches", "Celsius": "Celsius", "Fahrenheit": "Fahrenheit",
                 "hertz": "hertz", "kilohertz": "kilohertz", "megahertz": "megahertz",
                 "gigahertz": "gigahertz", "penny": "pence", "yen": "yen", "yuan": "yuan",
                 "won": "won", "rand": "rand", "baht": "baht"}
    if word in irregular:
        return irregular[word]
    parts = word.split(" ")
    if parts[-1].endswith(("s", "x", "ch", "sh")):
        parts[-1] += "es"
    elif parts[-1].endswith("y") and parts[-1][-2:-1] not in "aeiou":
        parts[-1] = parts[-1][:-1] + "ies"
    else:
        parts[-1] += "s"
    return " ".join(parts)


# --------------------------------------------------------------------------- tables

_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]
_MONTH_ABBR = {m[:3].lower(): m for m in _MONTHS}
_MONTH_ABBR["sept"] = "September"
_MONTH_RE = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|"
             r"Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")

_CURRENCY_SYMBOLS = {"$": ("dollar", "cent"), "€": ("euro", "cent"), "£": ("pound", "penny"),
                     "¥": ("yen", None), "₹": ("rupee", "paisa"), "₩": ("won", None),
                     "₽": ("ruble", "kopek"), "₦": ("naira", "kobo"), "₱": ("peso", "centavo"),
                     "₺": ("lira", "kurus"), "₪": ("shekel", "agora"), "₫": ("dong", None)}
_CURRENCY_CODES = {"USD": ("US dollar", "cent"), "EUR": ("euro", "cent"), "GBP": ("pound", "penny"),
                   "CAD": ("Canadian dollar", "cent"), "AUD": ("Australian dollar", "cent"),
                   "JPY": ("yen", None), "INR": ("rupee", "paisa"), "CHF": ("Swiss franc", "centime"),
                   "CNY": ("yuan", None), "NGN": ("naira", "kobo"), "ZAR": ("rand", "cent"),
                   "KES": ("Kenyan shilling", "cent"), "GHS": ("Ghanaian cedi", "pesewa"),
                   "XOF": ("CFA franc", None), "XAF": ("CFA franc", None)}
_MAGNITUDES = {"k": "thousand", "K": "thousand", "thousand": "thousand", "m": "million",
               "M": "million", "mm": "million", "MM": "million", "mn": "million",
               "million": "million", "b": "billion", "B": "billion", "bn": "billion",
               "billion": "billion", "t": "trillion", "T": "trillion", "tn": "trillion",
               "trillion": "trillion"}

_UNITS = {
    "km": "kilometer", "cm": "centimeter", "mm": "millimeter", "nm": "nanometer",
    "kg": "kilogram", "mg": "milligram", "lb": "pound", "lbs": "pound", "oz": "ounce",
    "mph": "miles per hour", "km/h": "kilometers per hour", "kph": "kilometers per hour",
    "ft": "foot", "sq ft": "square foot", "mi": "mile",
    "ml": "milliliter", "mL": "milliliter",
    "KB": "kilobyte", "MB": "megabyte", "GB": "gigabyte", "TB": "terabyte", "PB": "petabyte",
    "kb": "kilobit", "Mb": "megabit", "Gb": "gigabit", "Mbps": "megabits per second",
    "Gbps": "gigabits per second", "kbps": "kilobits per second",
    "Hz": "hertz", "kHz": "kilohertz", "MHz": "megahertz", "GHz": "gigahertz",
    "W": "watt", "kW": "kilowatt", "MW": "megawatt", "kWh": "kilowatt hour", "mAh": "milliamp hour",
    "V": "volt", "mA": "milliamp",
    "ms": "millisecond", "hrs": "hour", "hr": "hour", "mins": "minute", "min": "minute",
    "sec": "second", "secs": "second",
}
# per-unit plurals for compound units are pre-pluralised; keep them invariant
_INVARIANT_UNITS = {"miles per hour", "kilometers per hour", "megabits per second",
                    "gigabits per second", "kilobits per second"}

_TITLES = {"Dr": "Doctor", "Mr": "Mister", "Mrs": "Missus", "Ms": "Miz", "Prof": "Professor",
           "Gen": "General", "Col": "Colonel", "Lt": "Lieutenant", "Capt": "Captain",
           "Sgt": "Sergeant", "Rev": "Reverend", "Hon": "Honorable", "Gov": "Governor",
           "Sen": "Senator", "Rep": "Representative", "Pres": "President", "Fr": "Father",
           "Supt": "Superintendent", "Insp": "Inspector", "Cmdr": "Commander", "Adm": "Admiral"}
_ABBREVIATIONS = [
    (r"\be\.g\.,?", "for example,"), (r"\bi\.e\.,?", "that is,"), (r"\betc\.", "et cetera."),
    (r"\bvs\.?(?=\s)", "versus"), (r"\bapprox\.", "approximately"), (r"\bca\.(?=\s*\d)", "circa"),
    (r"\bc\.(?=\s*\d{3,4}\b)", "circa"), (r"\bcf\.", "compare"), (r"\bet al\.", "and colleagues"),
    (r"\bNo\.(?=\s*\d)", "number"), (r"\bno\.(?=\s*\d)", "number"), (r"\bNos\.(?=\s*\d)", "numbers"),
    (r"\bFig\.(?=\s*\d)", "figure"), (r"\bfig\.(?=\s*\d)", "figure"), (r"\bEq\.(?=\s*\d)", "equation"),
    (r"\bVol\.(?=\s*\d)", "volume"), (r"\bvol\.(?=\s*\d)", "volume"), (r"\bCh\.(?=\s*\d)", "chapter"),
    (r"\bch\.(?=\s*\d)", "chapter"), (r"\bpp\.(?=\s*\d)", "pages"), (r"\bp\.(?=\s*\d)", "page"),
    (r"\bSec\.(?=\s*\d)", "section"), (r"\bsec\.(?=\s*\d)", "section"), (r"\bArt\.(?=\s*\d)", "article"),
    (r"\bdept\.", "department"), (r"\bDept\.", "Department"), (r"\bestd?\.", "established"),
    (r"\bmin\.(?=\s+[a-z])", "minimum"), (r"\bmax\.(?=\s+[a-z])", "maximum"),
    (r"\bw/o\b", "without"), (r"\bw/(?=\s)", "with"), (r"\ba\.k\.a\.?", "also known as"),
    (r"\bAKA\b", "also known as"), (r"\bFYI\b", "F Y I"), (r"\bASAP\b", "A sap"),
    (r"\bQ([1-4])\b", lambda m: "Q " + _ONES[int(m.group(1))]),
    (r"\bYoY\b", "year over year"), (r"\bQoQ\b", "quarter over quarter"), (r"\bYTD\b", "year to date"),
    (r"\bEOD\b", "end of day"), (r"\bEOW\b", "end of week"), (r"\bw/e\b", "week ending"),
    (r"\bRm\.(?=\s*\d)", "room"), (r"\bApt\.(?=\s*\w)", "apartment"), (r"\bSte\.(?=\s*\d)", "suite"),
    (r"\bMon\.(?=\s)", "Monday"), (r"\bTues?\.(?=\s)", "Tuesday"), (r"\bWed\.(?=\s)", "Wednesday"),
    (r"\bThu(?:rs?)?\.(?=\s)", "Thursday"), (r"\bFri\.(?=\s)", "Friday"), (r"\bSat\.(?=\s)", "Saturday"),
    (r"\bAve\.", "Avenue"), (r"\bBlvd\.", "Boulevard"), (r"\bRd\.", "Road"),
    (r"\bMt\.(?=\s+[A-Z])", "Mount"), (r"\bFt\.(?=\s+[A-Z])", "Fort"),
]
_REGNAL_NAMES = ("Henry|Elizabeth|Louis|George|Edward|Charles|William|James|Richard|John|"
                 "Benedict|Pius|Leo|Gregory|Alexander|Peter|Catherine|Mary|Philip|Frederick|"
                 "Napoleon|Ramesses|Ramses|Constantine|Nicholas|Francis|Paul|Felipe|Carlos|Gustav|"
                 "Willem|Harald|Olav|Haakon|Christian|Ferdinand|Wilhelm|Mohammed|Hussein|Ivan|"
                 "Innocent|Clement|Urban|Boniface|Sixtus|Victor|Otto|Rudolf|Ludwig|Amenhotep|"
                 "Thutmose|Tutankhamun|David|Robert|Malcolm|Duncan|Juan|Sobhuza|Mswati|Letsie")
_ROMAN_KEYWORDS = ("Chapter|Part|Volume|Book|Act|Scene|Article|Title|Phase|Stage|Section|"
                   "World War|Super Bowl|Grade|Level|Class|Type|Category|Round|Season|Episode|"
                   "Appendix|Schedule|Tier|Mark|Mk\\.?|Apollo|Vatican|Final Fantasy|Rocky")


def roman_to_int(s: str) -> int | None:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals.get(ch)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    return total if total > 0 else None


# --------------------------------------------------------------------------- helpers

_ENGLISH_HINTS = set("the and of to a in is that for it with as was on be are this by not you or "
                     "at from have an they your we his her but can will has which our all their "
                     "please thanks thank hi hello dear regards said says new more about after into than "
                     "were been would could should there what when who it's its i my me he she".split())


def looks_english(text: str) -> bool:
    words = re.findall(r"[A-Za-zÀ-ɏ']+", text.lower())
    if len(words) < 4:
        letters = re.findall(r"[^\W\d_]", text)
        return all(ord(c) < 0x250 for c in letters)
    hits = sum(w in _ENGLISH_HINTS for w in words)
    return hits / len(words) >= 0.08


_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"


def _amount_words(num: str, magnitude: str | None) -> tuple[str, bool]:
    words = number_words(num)
    if magnitude:
        return words + " " + _MAGNITUDES[magnitude], False
    return words, num.replace(",", "") in ("1", "1.0", "1.00")


def _money(num: str, magnitude: str | None, unit: str, sub: str | None) -> str:
    clean = num.replace(",", "")
    if not magnitude and "." in clean and sub:
        whole, frac = clean.split(".", 1)
        if len(frac) == 2:
            whole_i, cents = int(whole or 0), int(frac)
            parts = []
            if whole_i or not cents:
                parts.append(int_to_words(whole_i) + " " + _plural(unit, whole_i == 1))
            if cents:
                parts.append(int_to_words(cents) + " " + _plural(sub, cents == 1))
            return " and ".join(parts)
    words, is_one = _amount_words(num, magnitude)
    if magnitude:
        return words + " " + _plural(unit, False)
    return words + " " + _plural(unit, is_one)


def _time_words(h: int, m: int, ampm: str | None) -> str:
    suffix = ""
    if ampm:
        a = ampm.lower().replace(".", "").replace(" ", "")
        suffix = " AM" if a.startswith("a") else " PM"
    if m == 0:
        if ampm:
            return int_to_words(h) + suffix
        if h == 12:
            return "twelve o'clock"
        if h == 0:
            return "midnight"
        return int_to_words(h) + (" hundred" if h > 12 else " o'clock")
    mins = ("oh " + int_to_words(m)) if m < 10 else int_to_words(m)
    if not ampm and h == 0:
        return "zero " + mins
    return int_to_words(h) + " " + mins + suffix


def _date_words(month: int, day: int, year: int | None) -> str:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError
    out = f"{_MONTHS[month - 1]} {ordinal_words(day)}"
    if year is not None:
        if year < 100:
            year += 2000 if year < 50 else 1900
        out += ", " + year_words(year)
    return out


def _month_from_text(s: str) -> str:
    key = s.rstrip(".").lower()
    return _MONTH_ABBR.get(key[:4] if key.startswith("sept") else key[:3], s)


# --------------------------------------------------------------------------- passes

def _clean_unicode(t: str) -> str:
    t = unicodedata.normalize("NFKC", t.replace("­", ""))
    t = re.sub(r"[​-‏⁠﻿]", "", t)
    t = t.replace(" ", " ").replace("…", "...")
    t = t.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    t = t.replace("−", "-")
    return t


def _strip_markup(t: str) -> str:
    t = re.sub(r"```.*?```", " ", t, flags=re.S)                 # fenced code
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", t)              # images
    t = re.sub(r"\[([^\]]+)\]\((?:https?://|/)[^)]*\)", r"\1", t)  # links
    t = re.sub(r"(\*\*|__)(.+?)\1", r"\2", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)\*(?!\w)", r"\1", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s+(.*)$", r"\1.", t, flags=re.M)  # headings get a pause
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)
    t = re.sub(r"<[^>\n]{1,200}>", " ", t) if re.search(r"</?[a-z][^>]*>", t) else t
    return t


def _drop_emoji(t: str) -> str:
    out = []
    for ch in t:
        cat = unicodedata.category(ch)
        if cat == "So" and ord(ch) > 0x2000 and ch not in "©®™°":
            continue
        if 0xFE00 <= ord(ch) <= 0xFE0F or 0x1F3FB <= ord(ch) <= 0x1F3FF:
            continue
        out.append(ch)
    return "".join(out)


def _urls_emails(t: str, url_mode: str) -> str:
    def email(m):
        user, domain = m.group(1), m.group(2)
        user = re.sub(r"[._]", lambda x: " dot " if x.group() == "." else " underscore ", user)
        return f"{user} at {domain.replace('.', ' dot ')}"
    t = re.sub(r"\b([\w.+-]+)@([\w-]+(?:\.[\w-]+)+)\b", email, t)

    def url(m):
        raw = m.group(0)
        trail = ""
        while raw and raw[-1] in ".,;:!?)'\"":
            trail = raw[-1] + trail
            raw = raw[:-1]
        if url_mode == "skip":
            return "link" + trail
        host = re.sub(r"^(?:https?://)?(?:www\.)?", "", raw, flags=re.I)
        domain, _, path = host.partition("/")
        spoken = domain.replace(".", " dot ")
        if url_mode == "full" and path:
            spoken += " slash " + re.sub(r"[/?=&#_-]+", " ", path).strip()
        return spoken + trail
    t = re.sub(r"\b(?:https?://|www\.)[^\s<>\"]+", url, t, flags=re.I)
    # bare domains like example.com or docs.python.org (only well-known TLDs)
    t = re.sub(r"\b((?:[a-z0-9-]+\.)+(?:com|org|net|io|ai|dev|edu|gov|co|uk|app|me|info))\b(?![.\w])",
               lambda m: m.group(1).replace(".", " dot "), t)
    return t


def _kept_period(m: re.Match) -> str:
    """'p.m.' at the end of a sentence also ends the sentence; keep that period."""
    if not m.group(0).endswith("."):
        return ""
    rest = m.string[m.end():]
    return "." if not rest.strip() or re.match(r"\s+[A-Z\"']", rest) else ""


def _dates_times(t: str, date_order: str) -> str:
    # ISO 2026-10-18 (optionally with time)
    def iso(m):
        try:
            return _date_words(int(m.group(2)), int(m.group(3)), int(m.group(1)))
        except ValueError:
            return m.group(0)
    t = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", iso, t)

    # numeric 10/18/2026 or 18.10.2026
    def numeric(m):
        a, b, y = int(m.group(1)), int(m.group(3)), int(m.group(4))
        month, day = (a, b) if date_order == "MDY" else (b, a)
        if month > 12 and day <= 12:
            month, day = day, month
        try:
            return _date_words(month, day, y)
        except ValueError:
            return m.group(0)
    t = re.sub(r"\b(\d{1,2})([/.])(\d{1,2})\2(\d{4}|\d{2})\b", numeric, t)

    # "October 18, 2026", "Oct. 18th", "Oct 18"
    def month_day(m):
        year = m.group(3)
        out = f"{_month_from_text(m.group(1))} {ordinal_words(int(m.group(2)))}"
        return out + (", " + year_words(int(year)) if year else "")
    t = re.sub(rf"\b({_MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}})\b)?", month_day, t)

    # "18 October 2026", "18th of October"
    def day_month(m):
        out = f"the {ordinal_words(int(m.group(1)))} of {_month_from_text(m.group(2))}"
        return out + (", " + year_words(int(m.group(3))) if m.group(3) else "")
    t = re.sub(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})(?:,?\s+(\d{{4}})\b)?", day_month, t)

    # "October 2026"
    t = re.sub(rf"\b({_MONTH_RE})\s+(\d{{4}})\b",
               lambda m: f"{_month_from_text(m.group(1))} {year_words(int(m.group(2)))}", t)

    # times 3:30 PM, 15:45, 9:05am
    def clock(m):
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 24 or mi > 59:
            return m.group(0)
        out = _time_words(h, mi, m.group(3))
        return out + _kept_period(m)
    t = re.sub(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp]\.?\s?[Mm]\.?)?(?![\w:])", clock, t)
    t = re.sub(r"\b(\d{1,2})\s*([AaPp]\.?[Mm]\.?)(?=\W|$)",
               lambda m: (_time_words(int(m.group(1)), 0, m.group(2)) + _kept_period(m))
               if int(m.group(1)) <= 12 else m.group(0), t)
    return t


def _phones(t: str) -> str:
    def group_digits(s: str) -> str:
        groups = re.findall(r"\d+", s)
        return ", ".join(" ".join(_ONES[int(d)] for d in g) for g in groups)

    def phone(m):
        plus = "plus " if m.group(0).lstrip().startswith("+") else ""
        return plus + group_digits(m.group(0))
    t = re.sub(r"(?<![\w.])\+\d{1,3}[\s.-]?(?:\(?\d{1,4}\)?[\s.-]?){2,4}\d{2,4}\b", phone, t)
    t = re.sub(r"(?<![\w.])\(\d{3}\)\s?\d{3}[\s.-]\d{4}\b", phone, t)
    t = re.sub(r"(?<![\w.-])\d{3}[.-]\d{3}[.-]\d{4}\b", phone, t)
    return t


def _money_pass(t: str) -> str:
    mag = r"(?:\s?(thousand|million|billion|trillion|bn|mn|tn|mm|MM|[kKmMbBtT])\b)?"
    sym = "".join(re.escape(s) for s in _CURRENCY_SYMBOLS)

    def prefix(m):
        unit, sub = _CURRENCY_SYMBOLS[m.group(2)]
        if m.group(1):  # e.g. US$ / CA$ / A$
            unit = {"US": "US dollar", "CA": "Canadian dollar", "C": "Canadian dollar",
                    "A": "Australian dollar", "AU": "Australian dollar", "NZ": "New Zealand dollar",
                    "HK": "Hong Kong dollar", "S": "Singapore dollar", "R": "real"}.get(m.group(1), unit)
        return _money(m.group(3), m.group(4), unit, sub)
    t = re.sub(rf"(?<![\w$])([A-Z]{{1,2}})?([{sym}])\s?({_NUM}){mag}", prefix, t)

    def suffix_symbol(m):
        unit, sub = _CURRENCY_SYMBOLS[m.group(3)]
        return _money(m.group(1), m.group(2), unit, sub)
    t = re.sub(rf"\b({_NUM}){mag}\s?([{sym}])(?!\w)", suffix_symbol, t)

    codes = "|".join(_CURRENCY_CODES)

    def code_first(m):
        unit, sub = _CURRENCY_CODES[m.group(1)]
        return _money(m.group(2), m.group(3), unit, sub)
    t = re.sub(rf"\b({codes})\s?({_NUM}){mag}", code_first, t)

    def code_last(m):
        unit, sub = _CURRENCY_CODES[m.group(3)]
        return _money(m.group(1), m.group(2), unit, sub)
    t = re.sub(rf"\b({_NUM}){mag}\s?({codes})\b", code_last, t)
    return t


def _measures(t: str) -> str:
    def rng(a: str, b: str) -> str:
        return number_words(a) + " to " + number_words(b)

    # percentages, incl. ranges 10-20%
    t = re.sub(rf"({_NUM})\s?[-–—]\s?({_NUM})\s?%", lambda m: rng(m.group(1), m.group(2)) + " percent", t)
    t = re.sub(rf"(?<![\w.])([-+]?(?:{_NUM}))\s?%", lambda m: number_words(m.group(1)) + " percent", t)
    t = re.sub(r"\bpct\b\.?", "percent", t)

    # temperatures and angles
    def temp(m):
        scale = {"C": " Celsius", "F": " Fahrenheit", "K": " kelvin"}.get((m.group(2) or "").upper(), "")
        n = m.group(1)
        return number_words(n) + (" degree" if n in ("1", "-1") else " degrees") + scale
    t = re.sub(rf"([-+]?(?:{_NUM}))\s?°\s?([CFK])?\b", temp, t)

    # units (longest first so "km/h" wins over "km")
    unit_alt = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))

    def unit(m):
        n, u = m.group(1), m.group(2)
        word = _UNITS[u]
        if word in _INVARIANT_UNITS:
            return number_words(n) + " " + word
        one = n.replace(",", "") in ("1", "1.0")
        return number_words(n) + " " + _plural(word, one)
    t = re.sub(rf"(?<![\w.])({_NUM})\s?({unit_alt})(?![\w/])", unit, t)
    return t


def _ordinals_fractions_ranges(t: str) -> str:
    t = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: ordinal_words(int(m.group(1))), t)

    fractions = {"½": "one half", "⅓": "one third", "⅔": "two thirds", "¼": "one quarter",
                 "¾": "three quarters", "⅕": "one fifth", "⅛": "one eighth"}
    for k, v in fractions.items():
        t = re.sub(rf"(\d)\s?{k}", rf"\1 and {v}", t).replace(k, v)

    def frac(m):
        a, b = int(m.group(1)), int(m.group(2))
        if b == 2:
            return int_to_words(a) + (" half" if a == 1 else " halves")
        if b == 4:
            return int_to_words(a) + (" quarter" if a == 1 else " quarters")
        return int_to_words(a) + " " + (ordinal_words(b) if a == 1 else ordinal_words(b) + "s")
    t = re.sub(r"(?<![\w/.])(\d{1,2})/(\d{1,2})(?![\w/])",
               lambda m: frac(m) if 0 < int(m.group(1)) < int(m.group(2)) <= 12 else m.group(0), t)

    # ranges 10-20, 2020-2024, pages 10–12 (not within identifiers like A1-B2)
    def rng(m):
        a, b = m.group(1), m.group(2)
        if len(a) == 4 and len(b) in (2, 4) and 1100 <= int(a) <= 2099:
            if len(b) == 2:
                b = a[:2] + b
            return year_words(int(a)) + " to " + year_words(int(b))
        return number_words(a) + " to " + number_words(b)
    t = re.sub(r"(?<![\w.,-])(\d+(?:\.\d+)?)\s?[–—-]\s?(\d+(?:\.\d+)?)(?![\w-]|\.\d)", rng, t)
    return t


def _decades_years(t: str) -> str:
    def decade(m):
        n = int(m.group(1))
        hi, lo = divmod(n, 100)
        lo_word = ordinal_words(lo).replace("tieth", "ties") if lo else "hundreds"
        lo_word = {"tenth": "tens"}.get(lo_word, lo_word)
        if 2000 <= n <= 2009:
            return "two thousands"
        return int_to_words(hi) + " " + lo_word
    t = re.sub(r"\b(1[1-9]\d0|20[0-9]0)'?s\b", decade, t)
    t = re.sub(r"(?:\B'|\b)([2-9]0)'?s\b", lambda m: _TENS[int(m.group(1)) // 10].replace("y", "ies"), t)
    # standalone four-digit years: 1100-2099 with no comma/decimal and not part of a bigger number
    t = re.sub(r"(?<![\w.,$-])(1[1-9]\d\d|20\d\d)(?![\w.,]\d|\d|[\w%])", lambda m: year_words(int(m.group(1))), t)
    return t


def _roman(t: str) -> str:
    pat_regnal = rf"\b({_REGNAL_NAMES})\s+([IVXL]{{1,6}})\b"

    def regnal(m):
        n = roman_to_int(m.group(2))
        if not n or n > 60:
            return m.group(0)
        return f"{m.group(1)} the {ordinal_words(n)}"
    t = re.sub(pat_regnal, regnal, t)

    def keyword(m):
        n = roman_to_int(m.group(2))
        if not n or n > 100:
            return m.group(0)
        return f"{m.group(1)} {int_to_words(n)}"
    t = re.sub(rf"\b({_ROMAN_KEYWORDS})\s+([IVXLC]{{1,7}})\b", keyword, t)
    return t


def _abbreviations(t: str) -> str:
    # titles before a capitalised name: "Dr. Smith" -> "Doctor Smith"
    titles = "|".join(_TITLES)
    t = re.sub(rf"\b({titles})\.?(?=\s+[A-Z])", lambda m: _TITLES[m.group(1)], t)
    # Saint vs Street: "St. Louis" vs "Main St."
    t = re.sub(r"\bSt\.?(?=\s+[A-Z][a-z])", "Saint", t)
    t = re.sub(r"(?<=[a-z]\s)St\b\.?", "Street", t)
    t = re.sub(r"(?<=[A-Z][a-z]\s)St\b\.?", "Street", t)
    t = re.sub(r"\bJr\.?(?=[\s,]|$)", "Junior", t)
    t = re.sub(r"\bSr\.?(?=[\s,]|$)", "Senior", t)
    for pat, rep in _ABBREVIATIONS:
        t = re.sub(pat, rep, t)
    # month abbreviations not followed by a number ("in Jan." -> "in January")
    t = re.sub(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.(?=\s)",
               lambda m: _month_from_text(m.group(1)), t)
    # versions: v2.1.3 -> version two point one point three
    t = re.sub(r"\bv(\d+(?:\.\d+)+|\d+)\b",
               lambda m: "version " + " point ".join(int_to_words(int(p)) for p in m.group(1).split(".")), t)
    # semantic numbers: #1 -> number one
    t = re.sub(r"(?<![\w&])#(\d+)\b", lambda m: "number " + int_to_words(int(m.group(1))), t)
    return t


def _plain_numbers(t: str) -> str:
    mag = r"(\s(?:thousand|million|billion|trillion))?"
    # "45M users", "3.2B downloads", "10K steps"
    t = re.sub(r"(?<![\w.,$-])(\d+(?:\.\d+)?)(K|M|B|bn|mn)(?=\s+[a-zA-Z])",
               lambda m: number_words(m.group(1)) + " " + _MAGNITUDES[m.group(2)], t)

    def plain(m):
        return number_words(m.group(1)) + (m.group(2) or "")
    # negative numbers: "-5" at word start
    t = re.sub(rf"(?<![\w.,])-(?=\d)(?=(?:{_NUM})\b)", "minus ", t)
    t = re.sub(rf"(?<![\w.,-])({_NUM})(?![\w,]*\d){mag}(?![\w])", plain, t)
    return t


def _symbols(t: str) -> str:
    t = re.sub(r"\s&\s", " and ", t)
    t = re.sub(r"(?<=\w)&(?=\w)", " and ", t) if re.search(r"\b[a-z]+&[a-z]+\b", t) else t
    t = re.sub(r"(?<=\s)\+(?=\s)", "plus", t)
    t = re.sub(r"(?<=\s)=(?=\s)", "equals", t)
    t = re.sub(r"(?<=\s)×(?=\s)|(?<=\d)\s?[x×]\s?(?=\d)", " by ", t)
    t = re.sub(r"(?<=\s)~(?=\w)|^~(?=\w)", "about ", t)
    t = re.sub(r"(?<=\s)/(?=\s)", " or ", t)
    t = re.sub(r"\s[-–]>\s|\s→\s", " to ", t)
    t = re.sub(r"(?<![\w@])@(\w+)", r"at \1", t)
    t = re.sub(r"(?<![\w&])#([A-Za-z]\w+)", r"hashtag \1", t)
    t = re.sub(r"\s*[—–]\s*|\s+--?\s+", ", ", t)  # dashes become breathing pauses
    t = re.sub(r"([!?])\1+", r"\1", t)
    t = re.sub(r"\.{4,}", "...", t)
    t = re.sub(r"[_*=~^|]{3,}", " ", t)  # ascii rules/separators
    t = re.sub(r"[•▪●◦‣∙·]\s*", "", t)
    return t


def _shouting(t: str) -> str:
    """Long ALL-CAPS runs make some voices spell letters; sentence-case them."""
    def fix(m):
        s = m.group(0).lower()
        return s[0].upper() + s[1:]
    def maybe(m):
        words = re.findall(r"[A-Z]+", m.group(0))
        return fix(m) if max(map(len, words)) >= 5 and sum(map(len, words)) >= 12 else m.group(0)
    return re.sub(r"\b(?:[A-Z]+[,.!?']*\s+){3,}[A-Z]+\b", maybe, t)


def _tidy(t: str) -> str:
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" +([,.;:!?])", r"\1", t)
    t = re.sub(r",\s*,", ",", t)
    t = re.sub(r"\.\s*\.(?!\.)", ".", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def normalize(text: str, *, date_order: str = "MDY", url_mode: str = "domain",
              force_english: bool | None = None) -> str:
    """Return speakable text. `date_order` is "MDY" or "DMY" for numeric dates."""
    t = _clean_unicode(text)
    t = _strip_markup(t)
    t = _drop_emoji(t)
    t = _urls_emails(t, url_mode)
    english = looks_english(t) if force_english is None else force_english
    if english:
        t = _shouting(t)
        t = _dates_times(t, date_order)
        t = _phones(t)
        t = _money_pass(t)
        t = _measures(t)
        t = _roman(t)
        t = _abbreviations(t)
        t = _ordinals_fractions_ranges(t)
        t = _decades_years(t)
        t = _plain_numbers(t)
    t = _symbols(t)
    return _tidy(t)
