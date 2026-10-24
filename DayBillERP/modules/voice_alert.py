# ============================================================
# DayBill ERP - Voice / Sound Alert (output side)
# Speaks a short phrase (offline TTS) when available, otherwise
# falls back to a system beep so the cashier still gets an
# audible cue. Everything degrades gracefully with no hard deps.
#
#   speak("Product not found")   -> voice if pyttsx3 present,
#                                   else winsound.Beep, else bell.
# ============================================================

import threading


def _beep():
    """Last-resort audible cue with zero dependencies."""
    try:
        import winsound
        # two short high beeps = "not found"
        winsound.Beep(880, 140)
        winsound.Beep(660, 180)
        return True
    except Exception:
        try:
            import sys
            sys.stdout.write("\a")
            sys.stdout.flush()
            return True
        except Exception:
            return False


def _speak_blocking(text):
    try:
        import pyttsx3
        eng = pyttsx3.init()
        eng.setProperty("rate", 165)
        eng.say(text)
        eng.runAndWait()
        try:
            eng.stop()
        except Exception:
            pass
        return True
    except Exception:
        return False


def speak(text="Product not found", fallback_widget=None):
    """Speak `text` on a background thread (non-blocking so the POS
    UI never freezes). Falls back to a beep, then to the Tk bell."""
    def worker():
        if _speak_blocking(text):
            return
        if _beep():
            return
        if fallback_widget is not None:
            try:
                fallback_widget.bell()
            except Exception:
                pass
    try:
        threading.Thread(target=worker, daemon=True).start()
    except Exception:
        # if threads are unavailable, at least try a bell
        if fallback_widget is not None:
            try:
                fallback_widget.bell()
            except Exception:
                pass


def not_found(widget=None):
    """Convenience wrapper for the common POS case."""
    speak("Product not found", fallback_widget=widget)


# ── Cash drawer kick (ESC/POS) ─────────────────────────────────
def open_cash_drawer(printer_name=None):
    """Send the standard drawer-kick pulse to the receipt printer.
    ESC p m t1 t2  (0x1B 0x70 0x00 0x19 0xFA) — pin 2, ~50/250ms.
    Silent no-op if the printer service / win32print is missing."""
    try:
        from modules import printer_service as ps
        kick = b"\x1b\x70\x00\x19\xfa"
        return bool(ps.print_raw(kick, printer_name))
    except Exception:
        return False


if __name__ == "__main__":
    print("Testing voice alert…")
    speak("Product not found")
    import time
    time.sleep(2)
