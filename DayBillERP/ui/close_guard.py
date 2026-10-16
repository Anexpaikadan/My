# ============================================================
# DayBill ERP - safe windows (app-wide, installed once)
# ------------------------------------------------------------
# 1. Message boxes open ON TOP OF the window you are working in.
#    Without a parent, Windows puts the box over the main window
#    and the POS / form you were in drops behind it ("the window
#    closed / hid after an error"). Now the window stays where it is.
# 2. Closing a window with its title-bar ✕ asks "Close this window?"
#    Yes / No first (big windows only — small pickers close at once).
#    Windows closed by the program itself (after Save, etc.) don't ask.
#    Settings key confirm_close_windows = False turns it off.
# ============================================================

import tkinter as tk
from tkinter import messagebox as _mb

MSG_CLOSE = "Close this window?\nهل تريد إغلاق هذه النافذة؟"


def _enabled():
    try:
        from config import settings as cfg
        return bool(cfg.flag("confirm_close_windows", True))
    except Exception:
        return True


def active_window():
    """The window the user is working in (the one with focus, else the
    top-most visible one)."""
    root = tk._default_root
    if root is None:
        return None
    try:
        w = root.focus_get()
        if w is not None:
            top = w.winfo_toplevel()
            if top.winfo_ismapped() and not top.overrideredirect():
                return top
    except Exception:
        pass
    try:
        order = root.tk.splitlist(root.tk.call("wm", "stackorder", "."))
        for name in reversed(order):
            try:
                top = root.nametowidget(name)
            except Exception:
                continue
            if top.winfo_ismapped() and not top.overrideredirect():
                return top
    except Exception:
        pass
    return root


# ── 1. message boxes get the active window as parent ─────────
def _wrap_box(fn):
    def box(*a, **k):
        if k.get("parent") is None:
            p = active_window()
            if p is not None:
                k["parent"] = p
        return fn(*a, **k)
    box._daybill_wrapped = True
    box.__name__ = fn.__name__
    return box


for _n in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel",
           "askyesnocancel", "askquestion", "askretrycancel"):
    _f = getattr(_mb, _n, None)
    # only the real tkinter functions (tests may have replaced them)
    if _f is not None and not getattr(_f, "_daybill_wrapped", False) \
            and getattr(_f, "__module__", "") == "tkinter.messagebox":
        setattr(_mb, _n, _wrap_box(_f))


# ── 2. ✕ on a window asks first ──────────────────────────────
def _should_ask(win):
    if not _enabled() or getattr(win, "_no_close_confirm", False):
        return False
    try:
        if win.overrideredirect():
            return False
        return win.winfo_width() >= 480 and win.winfo_height() >= 360
    except Exception:
        return False


def ask_close(win, text=MSG_CLOSE):
    try:
        return _mb.askyesno("Close", text, parent=win)
    except Exception:
        return True


def _guard(win, func):
    def on_close():
        if _should_ask(win) and not ask_close(win):
            return
        try:
            func()
        except tk.TclError:
            pass
    on_close._daybill_guard = True
    return on_close


_orig_protocol = tk.Wm.wm_protocol


def _protocol(self, name=None, func=None):
    if (name == "WM_DELETE_WINDOW" and callable(func) and isinstance(self, tk.Toplevel)
            and not getattr(func, "_daybill_guard", False)):
        func = _guard(self, func)
    return _orig_protocol(self, name, func)


_orig_top_init = tk.Toplevel.__init__


def _top_init(self, *a, **k):
    _orig_top_init(self, *a, **k)
    try:
        _orig_protocol(self, "WM_DELETE_WINDOW", _guard(self, self.destroy))
    except Exception:
        pass


if not getattr(tk.Wm, "_daybill_close_guard", False):
    tk.Wm.wm_protocol = _protocol
    tk.Wm.protocol = _protocol
    tk.Toplevel.__init__ = _top_init
    tk.Wm._daybill_close_guard = True
