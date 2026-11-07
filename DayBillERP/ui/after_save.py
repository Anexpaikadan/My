# ============================================================
# DayBill ERP - what an entry window does after Save (v6.9.3)
# ------------------------------------------------------------
# Settings ▸ General ▸ "After saving an entry"  (after_save_mode)
#   new    the window STAYS where it is and starts a new blank entry —
#          the number just saved shows in it (default). When a SAVED entry
#          was changed (edit) it stays showing that entry, like Tally.
#   keep   the window stays showing the saved entry (print it, check it,
#          change it again)
#   close  the window closes (the old way)
#
#   after_save.finish(form, number, new=lambda: Form(parent, …),
#                     keep=lambda: Form(parent, …, doc_id=saved_id),
#                     edited=<the window was editing a saved entry>)
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


def finish(form, number="", new=None, keep=None, edited=False):
    """Call at the very end of a successful save. Returns the new form
    (or None when the window was closed)."""
    m = mode()
    if m == "new" and edited and keep:
        m = "keep"
    win = getattr(form, "win", None)
    build = None
    if m == "new":
        build, text = (new or keep), ("✔ Saved %s — ready for the next entry" % number
                                      if new else "✔ Saved %s" % number)
    elif m == "keep":
        build, text = (keep or new), ("✔ Saved %s" % number if keep
                                      else "✔ Saved %s — ready for the next entry" % number)
    # v7.18.1: no flicker — the new window is built hidden BEHIND the old
    # one, takes its place and size, shows, and only then the old one goes
    # (before, the old one closed first and the desktop flashed through)
    geo = None
    try:
        if win is not None and win.winfo_exists():
            geo = win.geometry()
    except Exception:
        pass

    def drop_old():
        try:
            if win is not None and win.winfo_exists():
                win.destroy()
        except Exception:
            pass
    if build is None:
        drop_old()
        return None
    try:
        nf = build()
    except Exception:
        drop_old()
        return None
    nwin = getattr(nf, "win", None)
    try:
        if nwin is not None:
            try:                             # a modal window (vouchers) stays modal
                had_grab = nwin.grab_current() is nwin
            except Exception:
                had_grab = False
            nwin.withdraw()
            nwin._keep_place = True          # ui/winplace: keep this place
            nwin._daybill_placed = True      # ui/ui_polish: keep this place
            if geo:
                nwin.geometry(geo)
            nwin.update_idletasks()
            nwin.deiconify()
            nwin.lift()
            if had_grab:
                nwin.after(30, lambda: _regrab(nwin))
    except Exception:
        pass
    drop_old()
    try:
        if nwin is not None:
            nwin.after(60, nwin.focus_force)
    except Exception:
        pass
    _say(nf, text.replace("Saved  —", "Saved —").strip())
    return nf


def _regrab(w):
    try:
        if w.winfo_exists() and w.winfo_viewable():
            w.grab_set()
    except Exception:
        pass


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
