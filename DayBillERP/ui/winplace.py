# ============================================================
# DayBill ERP - transaction windows: size, place, open list (v7.14)
# ------------------------------------------------------------
# Bills, returns, vouchers, entries … open as their own windows. They
# now behave like the windows of a desktop ERP:
#   • they open INSIDE the DayBill work area (not over the menu / sidebar),
#     centred, each next one a step down-right;
#   • a window you made bigger or smaller opens at that size next time;
#   • they stay in front of the main window and are listed in
#     Windows ▸ open windows; Windows ▸ Close All closes them too
#     (each one with unsaved lines asks first).
# A window is one of these when it is marked _doc_window, has _form or
# _is_dirty (every DayBill document form sets one of them).
#
#   install(app)          once, from the main window
#   forms()               the open transaction windows
#   focus(win) · close_all(ask=True) · cascade()
# ============================================================
import re
import tkinter as tk

_STATE = {"app": None, "forms": [], "n": 0}


def _cfg():
    try:
        from config import settings as cfg
        return cfg
    except Exception:
        return None


def is_form(w):
    return isinstance(w, tk.Toplevel) and (getattr(w, "_doc_window", False)
                                           or hasattr(w, "_form") or hasattr(w, "_is_dirty"))


def key_of(w):
    f = getattr(w, "_form", None)
    if f is not None:
        return "form:" + type(f).__name__
    try:
        t = w.title()
    except Exception:
        t = ""
    t = re.sub(r"\b(new|edit|view|editing)\b", " ", t.lower())
    t = re.sub(r"[^a-z ]+", " ", t)
    return "form:" + "_".join(t.split())[:40]


def area(app):
    """(x, y, w, h) of the work area on the screen."""
    mdi = getattr(app, "mdi", None)
    c = getattr(mdi, "desktop", None) or getattr(app, "content", None) or app.root
    try:
        c.update_idletasks()
        return c.winfo_rootx(), c.winfo_rooty(), max(500, c.winfo_width()), max(360, c.winfo_height())
    except Exception:
        r = app.root
        return 0, 0, r.winfo_screenwidth(), r.winfo_screenheight()


def place(w, app=None):
    app = app or _STATE["app"]
    if app is None:
        return
    try:
        if not w.winfo_exists() or getattr(w, "_daybill_max", False) or w.state() == "zoomed":
            return
    except Exception:
        return
    ax, ay, aw, ah = area(app)
    r = app.root
    rx, ry = r.winfo_rootx(), r.winfo_rooty()
    rw = max(aw, r.winfo_width())
    c = _cfg()
    geo = None
    try:
        geo = (c.get("form_geo", {}) or {}).get(key_of(w)) if c else None
    except Exception:
        geo = None
    try:
        w.update_idletasks()
        cw, ch = w.winfo_width(), w.winfo_height()
        if cw <= 1:
            cw, ch = w.winfo_reqwidth(), w.winfo_reqheight()
    except Exception:
        cw, ch = 900, 600
    if geo and len(geo) == 2:
        cw, ch = int(geo[0]), int(geo[1])
    n = len(forms()) - 1
    step = 26 * (max(0, n) % 6)
    # wider than the work area (a big bill): it may cover the side bar,
    # never the right edge; never over the menu / tool bar, never below
    cw = min(cw, rw)
    ch = min(ch, ah)
    if cw <= aw:
        x = ax + (aw - cw) // 2 + step
        x = min(x, ax + aw - cw)
    else:
        x = max(rx, ax + aw - cw)
    y = ay + max(0, (ah - ch) // 2) + step
    y = min(y, ay + ah - ch)
    try:
        w._daybill_placed = True        # ui_polish keeps this place from now on
        w.geometry("%dx%d+%d+%d" % (cw, ch, max(0, x), max(0, y)))
    except Exception:
        pass


def _remember(w):
    c = _cfg()
    if not c:
        return
    try:
        if str(w.state()) != "normal":
            return
        geo = dict(c.get("form_geo", {}) or {})
        geo[key_of(w)] = [w.winfo_width(), w.winfo_height()]
        c.set("form_geo", geo)
        c.save_settings()
    except Exception:
        pass


def forms():
    out = []
    for w in list(_STATE["forms"]):
        try:
            if w.winfo_exists():
                out.append(w)
        except Exception:
            pass
    _STATE["forms"] = out
    return list(out)


def _on_map(e):
    w = e.widget
    if not is_form(w) or getattr(w, "_wp_seen", False):
        return
    w._wp_seen = True
    app = _STATE["app"]
    if app is None:
        return
    _STATE["forms"].append(w)
    # v7.17.1: NOT made transient — a page opened from the menu while a bill
    # is open must come to the front (a transient bill stayed over it)
    if not getattr(w, "_keep_place", False):
        w.after(330, lambda: place(w, app))      # after ui_polish has sized it

    def gone(ev, w=w):
        if ev.widget is w:
            try:
                _STATE["forms"].remove(w)
            except ValueError:
                pass
    w.bind("<Destroy>", gone, add="+")
    w.bind("<Configure>", lambda ev, w=w: _soon_remember(w) if ev.widget is w else None, add="+")
    try:
        refresh = getattr(app, "_refresh_win_strip", None)
        if refresh:
            refresh()
    except Exception:
        pass


def _soon_remember(w):
    aid = getattr(w, "_wp_after", None)
    if aid:
        try:
            w.after_cancel(aid)
        except Exception:
            pass
    try:
        w._wp_after = w.after(900, lambda: _remember(w))
    except Exception:
        pass


def install(app):
    _STATE["app"] = app
    try:
        app.root.bind_class("Toplevel", "<Map>", _on_map, add="+")
    except Exception:
        pass


def focus(w):
    try:
        w.deiconify()
        w.lift()
        w.focus_force()
    except Exception:
        pass


def close_all(ask=True):
    n = 0
    try:
        from ui import close_guard
    except Exception:
        close_guard = None
    for w in forms():
        try:
            if close_guard is not None and ask:
                close_guard.request_close(w)
            else:
                w.destroy()
        except Exception:
            try:
                w.destroy()
            except Exception:
                pass
        try:
            if not w.winfo_exists():
                n += 1
        except Exception:
            n += 1
    return n


def cascade():
    app = _STATE["app"]
    if app is None:
        return 0
    ax, ay, aw, ah = area(app)
    fs = forms()
    for i, w in enumerate(fs):
        try:
            cw, ch = min(w.winfo_width(), aw - 160), min(w.winfo_height(), ah - 160)
            w.geometry("%dx%d+%d+%d" % (cw, ch, ax + 30 * i, ay + 30 * i))
            w.lift()
        except Exception:
            pass
    return len(fs)


def forget_sizes():
    c = _cfg()
    if c:
        c.set("form_geo", {})
        try:
            c.save_settings()
        except Exception:
            pass
