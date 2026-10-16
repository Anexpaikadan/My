# ============================================================
# DayBill ERP - Voice Search (optional)
# Captures microphone audio and returns recognized text so it
# can be typed into a product search box.
#
# Requires (optional): SpeechRecognition + pyaudio + internet.
# If anything is missing it degrades gracefully — the caller
# gets a clear (False, message) and the app keeps working.
# ============================================================


def is_available() -> bool:
    """True only if the speech libraries AND a microphone import succeed."""
    try:
        import speech_recognition  # noqa: F401
        import pyaudio  # noqa: F401
        return True
    except Exception:
        return False


def unavailable_reason() -> str:
    """Human-readable reason voice isn't available (for the UI)."""
    try:
        import speech_recognition  # noqa: F401
    except Exception:
        return ("Speech library not installed.\n"
                "Install with:  pip install SpeechRecognition")
    try:
        import pyaudio  # noqa: F401
    except Exception:
        return ("Microphone library not installed.\n"
                "Install with:  pip install pyaudio")
    return ""


def listen(language: str = "en-US", timeout: int = 5,
           phrase_limit: int = 6) -> tuple:
    """
    Listen on the default microphone and transcribe.
    language: 'en-US' for English, 'ar-SA' for Arabic.
    Returns (text, "") on success or ("", error_message) on failure.
    """
    if not is_available():
        return "", unavailable_reason()

    try:
        import speech_recognition as sr
    except Exception as e:
        return "", f"Speech library error: {e}"

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=timeout,
                                      phrase_time_limit=phrase_limit)
    except sr.WaitTimeoutError:
        return "", "No speech detected — try again."
    except Exception as e:
        return "", f"Microphone error: {e}"

    # Try the requested language; fall back to the other if it fails
    langs = [language, "ar-SA" if language.startswith("en") else "en-US"]
    for lang in langs:
        try:
            text = recognizer.recognize_google(audio, language=lang)
            if text:
                return text, ""
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            return "", f"Speech service unreachable (needs internet): {e}"
        except Exception:
            continue
    return "", "Could not understand the audio — please try again."


# ── Self-test ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("Voice available:", is_available())
    if not is_available():
        print("Reason:", unavailable_reason())
    else:
        print("Say a product name…")
        txt, err = listen("en-US")
        print("Heard:", txt or f"(error: {err})")


# ── New: background (non-blocking) listen ─────────────────────
def listen_async(callback, language: str = "en-US", timeout: int = 5,
                 phrase_limit: int = 6):
    """Run listen() on a background thread so the UI never freezes.
    callback(text, err) fires from the worker thread — marshal back to
    Tk with widget.after(0, ...) in the caller."""
    import threading

    def worker():
        try:
            text, err = listen(language, timeout, phrase_limit)
        except Exception as e:
            text, err = "", str(e)
        try:
            callback(text, err)
        except Exception:
            pass
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


# ── New: spoken quantity parsing ("3 pepsi" -> (3, "pepsi")) ──
_NUM_WORDS = {
    "one": 1, "two": 2, "to": 2, "too": 2, "three": 3, "four": 4, "for": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "dozen": 12, "half": 0.5,
    # Arabic number words (common forms)
    "واحد": 1, "اثنين": 2, "اثنان": 2, "ثلاثة": 3, "اربعة": 4, "أربعة": 4,
    "خمسة": 5, "ستة": 6, "سبعة": 7, "ثمانية": 8, "تسعة": 9, "عشرة": 10,
}
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def parse_qty_and_name(text: str):
    """Split a spoken phrase into (quantity, product name).
    '3 pepsi'   -> (3.0, 'pepsi')      'pepsi'      -> (None, 'pepsi')
    'two cola'  -> (2.0, 'cola')       'ثلاثة بيبسي' -> (3.0, 'بيبسي')
    Quantity may lead or trail ('pepsi 3'). Returns (None, text) when
    no quantity is recognized."""
    if not text:
        return None, ""
    words = str(text).translate(_AR_DIGITS).strip().split()
    if not words:
        return None, ""

    def as_num(w):
        w2 = w.strip().lower().rstrip("x×")
        try:
            return float(w2)
        except ValueError:
            return _NUM_WORDS.get(w2)

    q = as_num(words[0])
    if q is not None and len(words) > 1:
        return float(q), " ".join(words[1:])
    q = as_num(words[-1])
    if q is not None and len(words) > 1:
        return float(q), " ".join(words[:-1])
    return None, " ".join(words)


if __name__ == "__main__" and True:
    for s in ("3 pepsi", "two cola 250ml", "pepsi 3", "pepsi",
              "ثلاثة بيبسي", "٣ بيبسي", "dozen eggs"):
        print(repr(s), "->", parse_qty_and_name(s))
