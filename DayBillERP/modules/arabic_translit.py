# ============================================================
# DayBill ERP - English → Arabic Transliteration Helper
# Phonetic (sound-based) conversion for product names.
# Produces an EDITABLE suggestion, not a perfect translation.
# e.g. "ADAS MASOOR RED DAAL" → "اداس ماسور ريد دال"
# ============================================================

# Multi-letter sounds first (order matters — longest first)
_DIGRAPHS = [
    ("sh", "ش"), ("ch", "تش"), ("th", "ث"), ("ph", "ف"), ("gh", "غ"),
    ("kh", "خ"), ("dh", "ذ"), ("oo", "و"), ("ee", "ي"), ("aa", "ا"),
    ("ou", "او"), ("ow", "او"), ("ai", "اي"), ("ay", "اي"), ("ck", "ك"),
    ("qu", "كو"),
]

_SINGLE = {
    "a": "ا", "b": "ب", "c": "ك", "d": "د", "e": "ي", "f": "ف",
    "g": "غ", "h": "ه", "i": "ي", "j": "ج", "k": "ك", "l": "ل",
    "m": "م", "n": "ن", "o": "و", "p": "ب", "q": "ق", "r": "ر",
    "s": "س", "t": "ت", "u": "و", "v": "ف", "w": "و", "x": "كس",
    "y": "ي", "z": "ز",
}

# Common whole words that have natural Arabic forms
_WORD_MAP = {
    "red": "احمر", "green": "اخضر", "blue": "ازرق", "black": "اسود",
    "white": "ابيض", "yellow": "اصفر", "small": "صغير", "large": "كبير",
    "big": "كبير", "water": "ماء", "juice": "عصير", "milk": "حليب",
    "sugar": "سكر", "salt": "ملح", "rice": "ارز", "oil": "زيت",
    "tea": "شاي", "coffee": "قهوة", "bread": "خبز", "ml": "مل",
    "kg": "كجم", "litre": "لتر", "liter": "لتر", "gram": "جرام",
    "box": "علبة", "bag": "كيس", "piece": "قطعة", "carton": "كرتون",
    "pepsi": "بيبسي", "cola": "كولا",
}


def transliterate_word(word: str) -> str:
    """Transliterate a single English word to Arabic phonetics."""
    w = word.lower().strip()
    if not w:
        return ""
    # Numbers pass through unchanged
    if w.isdigit():
        return w
    # Known word?
    if w in _WORD_MAP:
        return _WORD_MAP[w]

    result = ""
    i = 0
    while i < len(w):
        matched = False
        # try digraphs
        for pair, ar in _DIGRAPHS:
            if w[i:i + len(pair)] == pair:
                result += ar
                i += len(pair)
                matched = True
                break
        if matched:
            continue
        ch = w[i]
        result += _SINGLE.get(ch, ch)
        i += 1
    return result


def transliterate(text: str) -> str:
    """
    Transliterate an English phrase to Arabic.
    Numbers and unknown symbols are preserved.
    """
    if not text:
        return ""
    parts = text.split()
    out = [transliterate_word(p) for p in parts]
    return " ".join(out)


# ── Self-test ──────────────────────────────────────────────────
if __name__ == "__main__":
    samples = [
        "ADAS MASOOR RED DAAL",
        "Pepsi Cola 250 ml",
        "Water Bottle 500 ml",
        "Sugar 1 kg",
    ]
    for s in samples:
        print(f"  {s:28s} → {transliterate(s)}")
    print("Transliteration helper ready (results are editable suggestions).")
