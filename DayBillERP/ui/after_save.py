# ============================================================
# DayBill ERP - what an entry window does after Save (v6.9.3)
# ------------------------------------------------------------
# Settings ▸ General ▸ "After saving an entry"  (after_save_mode)
#   new    the window STAYS OPEN and starts a new blank entry — the
#          number just saved shows in the title line (default)
#   keep   the window stays open showing the saved entry (print it,
#          check it, edit it again)
#   close  the window closes (the old way)
#
#   after_save.finish(form, number, new=form._start_new, keep=reload_fn)
# Each entry window passes its own "start a new one" and "show the saved
# one" functions; when one is missing the next mode is used, and close is
# the last fallback.
# ============================================================

from config import settings as cfg

MODES = [("new", "Stay open — start a new entry"),
         ("keep", "Stay open — show the saved entry"),
         ("close", "Close the window")]


def mode():
    m = str(cfg.get("after_save_mode", "new") or "new").lower()
    return m if m in ("new", "keep", "close") else "new"


def finish(form, number="", new=None, keep=None):
    """Call at the end of a successful save. Returns the mode used."""
    m = mode()
    win = getattr(form, "win", None)
    try:
        if m == "new" and new is not None:
            new()
            _say(form, "✔ Saved %s — ready for the next entry" % number if number
                 else "✔ Saved — ready for the next entry")
            return "new"
        if m in ("new", "keep") and keep is not None:
            keep()
            _say(form, "✔ Saved %s" % number if number else "✔ Saved")
            return "keep"
    except Exception:
        pass                       # a reset that fails → close as before
    try:
        if win is not None and win.winfo_exists():
            win.destroy()
    except Exception:
        pass
    return "close"


def _say(form, text):
    """Show the 'saved' line in the window: its status / message variable
    when it has one, else in the window title."""
    for name in ("status_var", "save_status", "msg", "status"):
        v = getattr(form, name, None)
        if v is not None and hasattr(v, "set"):
            try:
                v.set(text)
                return
            except Exception:
                pass
    win = getattr(form, "win", None)
    try:
        base = win.title().split("   ✔")[0]
        win.title("%s   %s" % (base, text))
    except Exception:
        pass
