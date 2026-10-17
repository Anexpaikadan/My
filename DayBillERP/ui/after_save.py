# ============================================================
# DayBill ERP - what an entry window does after Save (v6.9.3)
# ------------------------------------------------------------
# Settings ▸ General ▸ "After saving an entry"  (after_save_mode)
#   new    the window STAYS where it is and starts a new blank entry —
#          the number just saved shows in it (default)
#   keep   the window stays showing the saved entry (print it, check it,
#          change it again)
#   close  the window closes (the old way)
#
#   after_save.finish(form, number, new=lambda: Form(parent, …),
#                     keep=lambda: Form(parent, …, doc_id=saved_id))
# `new` / `keep` build the window again (each entry window can already
# open itself blank or with a saved id); finish() closes the old one
# and puts the new one at the same place and size. When a builder is
# missing the other one is used; with none the window just closes.
# ============================================================

from config import settings as cfg

MODES = [("new", "Stay open — start a new entry"),
         ("keep", "Stay open — show the saved entry"),
         ("close", "Close the window")]


def mode():
    m = str(cfg.get("after_save_mode", "new") or "new").lower()
    return m if m in ("new", "keep", "close") else "new"


def finish(form, number="", new=None, keep=None):
    """Call at the very end of a successful save. Returns the new form
    (or None when the window was closed)."""
    m = mode()
    win = getattr(form, "win", None)
    build = None
    if m == "new":
        build, text = (new or keep), ("✔ Saved %s — ready for the next entry" % number
                                      if new else "✔ Saved %s" % number)
    elif m == "keep":
        build, text = (keep or new), ("✔ Saved %s" % number if keep
                                      else "✔ Saved %s — ready for the next entry" % number)
    geo = None
    try:
        if win is not None and win.winfo_exists():
            geo = win.geometry()
            win.destroy()
    except Exception:
        pass
    if build is None:
        return None
    try:
        nf = build()
    except Exception:
        return None
    nwin = getattr(nf, "win", None)
    try:
        if geo and nwin is not None:
            nwin.geometry(geo)
    except Exception:
        pass
    _say(nf, text.replace("Saved  —", "Saved —").strip())
    return nf


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
