# ============================================================
# DayBill ERP - safe windows (app-wide, installed once)
# ------------------------------------------------------------
# 1. Message boxes open ON TOP OF the window you are working in.
#    Without a parent, Windows puts the box over the main window
#    and the POS / form you were in drops behind it ("the window
#    closed / hid after an error"). Now the window stays where it is.
# 2. Closing a window with its title-bar ✕ asks first — but only when
#    it matters:
#      - a form that can tell (win._is_dirty() or win._form._is_dirty())
#        asks "unsaved changes — close?" only when something is not
#        saved, and closes at once when everything is saved;
#      - other big windows ask the general "Close this window?" (small
#        pickers close at once). Settings key confirm_close_windows =
#        False turns this general question off.
#    A close function that asks by itself is marked  fn._own_prompt =
#    True  and is never asked twice. Windows closed by the program
#    itself (after Save, etc.) don't ask.
# 3. request_close(win): close a window exactly like its ✕ (used for
#    Esc and Cancel buttons). bind_escape(win): Esc = request_close,
#    except while a cell editor / dropdown / search box handles Esc.
#    on_map(win) (called by ui_polish when a window appears) gives
#    every titled window without an Esc of its own the same Esc.
# 4. Modal windows (grab_set) stay over the window that opened them
#    (transient) and, when they close, the window that was modal
#    before gets its grab back (nested dialogs).
# 5. When a window closes, the field you were in before it opened
#    gets the focus back.
# 6. single(key, factory): one window per key — opening it again
#    brings the open one to the front.
# Not touched: the main window, the POS (own Esc + own question),
# the login window, the setup wizard, the calculator, popups without a
# title bar (dropdowns, calendars, tooltips, toasts).
# ============================================================

import tkinter as tk
from tkinter import messagebox as _mb

MSG_CLOSE = "Close this window?\nهل تريد إغلاق هذه النافذة؟"
MSG_UNSAVED = ("This document has changes that are not saved.\n"
               "Close without saving?\n\n"
               "يوجد تغييرات غير محفوظة. هل تريد الإغلاق بدون حفظ؟")

# windows that keep their own close / Esc / modal behaviour
_EXEMPT = ("POSWindow", "LoginWindow", "SetupWizard", "Calculator")


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


# ── which windows are left alone ─────────────────────────────
def _owners(win):
    """Class names that own this window: the Toplevel class itself, the
    object whose method is its ✕ handler, and its form."""
    names = {type(win).__name__, getattr(win, "_daybill_owner", "")}
    form = getattr(win, "_form", None)
    if form is not None:
        names.add(type(form).__name__)
    return names


def _exempt(win):
    """Main window, POS, login, setup wizard, calculator, untitled popups."""
    try:
        if not isinstance(win, tk.Toplevel) or win.overrideredirect():
            return True
    except Exception:
        return True
    if getattr(win, "_no_esc_close", False):
        return True
    return any(n in _EXEMPT for n in _owners(win))


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


def _dirty(win):
    """True / False from the window's (or its form's) _is_dirty();
    None when the window can't tell."""
    for obj in (win, getattr(win, "_form", None)):
        fn = getattr(obj, "_is_dirty", None) if obj is not None else None
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                return None
    return None


def lines_sig(lines):
    """Short fingerprint of document lines (item / unit / qty / price /
    discount). Forms keep the one from the last load / save and compare
    it in their _is_dirty()."""
    out = []
    for ln in lines or []:
        try:
            out.append((ln.get("product_id"),
                        str(ln.get("unit_id") or ln.get("unit_of_measure_en") or ""),
                        round(float(ln.get("quantity") or 0), 4),
                        round(float(ln.get("unit_price") or 0), 4),
                        round(float(ln.get("discount_amount") or 0), 4)))
        except (TypeError, ValueError, AttributeError):
            out.append(repr(ln))
    return tuple(out)


def ask_close(win, text=MSG_CLOSE):
    try:
        return _mb.askyesno("Close", text, parent=win)
    except Exception:
        return True


def ask_unsaved(win):
    """Unsaved changes: Yes closes, No (the default) keeps the window."""
    try:
        return _mb.askyesno("Close", MSG_UNSAVED, parent=win, icon="warning",
                            default="no")
    except Exception:
        return True


def _may_close(win, func, quiet=False):
    if getattr(func, "_own_prompt", False) or getattr(win, "_no_close_confirm", False):
        return True                      # asks by itself / never asks
    if _exempt(win):
        return True                      # login, wizard … keep their own ✕
    d = _dirty(win)
    if d is True:
        return ask_unsaved(win)
    if d is False or quiet:
        return True                      # all saved → no question
    if _should_ask(win):
        return ask_close(win)
    return True


def _guard(win, func):
    def on_close(quiet=False):
        if not _may_close(win, func, quiet):
            return
        try:
            func()
        except tk.TclError:
            pass
    on_close._daybill_guard = True
    return on_close


def request_close(win, quiet=False):
    """Close `win` exactly like its ✕: the window's own close handler
    (with the unsaved-changes question), or destroy when it has none.
    quiet=True skips the general "Close this window?" (unsaved changes
    still ask). Returns True when the window is gone."""
    try:
        if win is None or not win.winfo_exists():
            return True
    except Exception:
        return True
    try:
        fn = getattr(win, "_daybill_close_fn", None)
        if callable(fn) and getattr(fn, "_daybill_guard", False):
            fn(quiet=quiet)
        elif callable(fn):
            fn()
        else:
            h = str(win.protocol("WM_DELETE_WINDOW") or "")
            if h:
                win.tk.call(h)
            else:
                win.destroy()
    except tk.TclError:
        pass
    try:
        return not win.winfo_exists()
    except Exception:
        return True


_orig_protocol = tk.Wm.wm_protocol


def _protocol(self, name=None, func=None):
    if name == "WM_DELETE_WINDOW" and isinstance(self, tk.Toplevel) and func is not None:
        if callable(func):
            if not getattr(func, "_daybill_guard", False):
                owner = getattr(func, "__self__", None)
                if owner is not None and owner is not self:
                    self._daybill_owner = type(owner).__name__   # e.g. LoginWindow
                func = _guard(self, func)
            self._daybill_close_fn = func
        else:
            self._daybill_close_fn = None    # a Tcl script: run it as it is
    return _orig_protocol(self, name, func)


# ── 3. Esc closes the window (the safe way) ──────────────────
def _popdown_open(w):
    try:
        return bool(int(w.tk.call("winfo", "ismapped", str(w) + ".popdown")))
    except Exception:
        return False


def _own_escape(w, win):
    """The focused widget handles Esc itself: a cell editor, a search
    box, an open dropdown. Tk's empty class bindings ('# nothing') and
    the combobox / listbox defaults don't count."""
    for tag in w.bindtags():
        if tag in (str(win), "all"):
            continue
        try:
            script = str(w.tk.call("bind", tag, "<Escape>") or "").strip()
        except Exception:
            continue
        if not script or script.startswith("#"):
            continue
        if tag == "TCombobox":
            if _popdown_open(w):
                return True
            continue
        if tag == "Listbox":
            continue
        return True
    return False


def _esc(event, win):
    w = event.widget
    if isinstance(w, str):
        return None                      # Tk's own widget (combobox list …)
    try:
        if w is not win and _own_escape(w, win):
            return None                  # the editor / dropdown closes itself
    except Exception:
        return None
    request_close(win)
    return "break"


def bind_escape(win):
    """Esc closes `win` like its ✕ — use instead of
    win.bind("<Escape>", lambda e: win.destroy())."""
    try:
        win.bind("<Escape>", lambda e, w=win: _esc(e, w))
        win._daybill_esc = True
    except Exception:
        pass


def on_map(win):
    """A window just appeared (ui_polish <Map> hook): a titled window
    with no Esc of its own gets the safe Esc."""
    try:
        if not isinstance(win, tk.Toplevel) or getattr(win, "_daybill_esc", False):
            return
        win._daybill_esc = True
        if _exempt(win) or not str(win.title()).strip():
            return
        if win.bind("<Escape>"):
            return                       # its own Esc (pay dialog, number pad …)
        bind_escape(win)
    except Exception:
        pass


# ── 4. modal windows: over their window, grab handed back ────
_orig_grab_set = tk.Misc.grab_set


def _grab_holder(win):
    try:
        name = str(win.tk.call("grab", "current", str(win)) or "")
        return win.nametowidget(name) if name else None
    except Exception:
        return None


def _modal_prep(top):
    if any(n in _EXEMPT for n in _owners(top)):
        return
    try:
        if not top.overrideredirect() and not str(top.transient() or ""):
            m = top.master.winfo_toplevel() if top.master is not None else None
            if m is not None and m is not top and m.winfo_viewable():
                top.transient(m)          # never drops behind its window
    except Exception:
        pass
    if getattr(top, "_daybill_prev_grab", None) is None:
        cur = _grab_holder(top)
        if cur is not None and cur is not top:
            top._daybill_prev_grab = cur  # the modal before this one


def _grab_later(top, tries=25):
    """Grab as soon as the window is on screen (Linux refuses before)."""
    def go(n=tries):
        try:
            if not top.winfo_exists():
                return
            if top.winfo_viewable():
                _orig_grab_set(top)
                return
        except tk.TclError:
            pass
        if n > 0:
            top.after(40, lambda: go(n - 1))
    try:
        top.after(40, go)
    except Exception:
        pass


def _grab_set(self):
    top = self if isinstance(self, tk.Toplevel) else None
    if top is not None:
        try:
            _modal_prep(top)
        except Exception:
            pass
    try:
        return _orig_grab_set(self)
    except tk.TclError:
        if top is None:
            raise
        _grab_later(top)                 # never breaks the window
        return None


def _give_back_grab(win):
    prev = getattr(win, "_daybill_prev_grab", None)
    if prev is None:
        return
    win._daybill_prev_grab = None
    try:
        cur = str(win.tk.call("grab", "current", str(win)) or "")
        if cur and cur != str(win):
            return                       # another window took it meanwhile
        if prev.winfo_exists() and prev.winfo_viewable():
            _orig_grab_set(prev)
        elif cur:
            win.grab_release()
    except Exception:
        pass


# ── 5. focus back to the field you were in ───────────────────
_state = {"active": "", "seq": 0, "interps": set()}


def _track_focus(e):
    try:
        _state["active"] = str(e.widget.winfo_toplevel())
    except Exception:
        pass


def _focus_now(top):
    """The widget with the focus before `top` is built."""
    try:
        name = str(top.tk.call("focus") or "")
        if name:
            return top.nametowidget(name)
    except Exception:
        pass
    return None


def _return_focus(win):
    prev = getattr(win, "_daybill_prev_focus", None)
    win._daybill_prev_focus = None
    if prev is None or _state["active"] != str(win):
        return                           # it was not the window in use
    seq = getattr(win, "_daybill_seq", 0)

    def go():
        try:
            if not prev.winfo_exists() or not prev.winfo_viewable():
                return
            top = prev.winfo_toplevel()
            cur = str(prev.tk.call("focus") or "")
            if cur:
                ct = prev.nametowidget(str(prev.tk.call("winfo", "toplevel", cur)))
                if ct is not top and getattr(ct, "_daybill_seq", 0) > seq:
                    return               # a newer window took over — leave it
            top.lift()
            if cur:
                prev.focus_set()
            else:
                prev.focus_force()       # our app just lost the active window
        except Exception:
            pass
    try:
        prev.after_idle(go)
    except Exception:
        pass


# ── 6. one window per key ────────────────────────────────────
_singles = {}


def single(key, factory, match=None):
    """Open the window for `key` once: when it is already open it comes
    to the front (and is returned), else factory() makes it (a Toplevel
    or an object with .win). Forgotten again when it closes.
    match(obj) -> False means the open window moved on to something else
    (e.g. browsed to another bill): a new one is opened then."""
    win = _singles.get(key)
    if win is not None:
        try:
            obj = getattr(win, "_daybill_single_obj", None) or win
            if match is not None and not match(obj):
                win = None
        except Exception:
            win = None
    if win is not None:
        try:
            if win.winfo_exists():
                try:
                    if win.state() in ("iconic", "withdrawn"):
                        win.deiconify()
                except Exception:
                    pass
                win.lift()
                try:
                    win.focus_force()
                except Exception:
                    pass
                return getattr(win, "_daybill_single_obj", None) or win
        except Exception:
            pass
        _singles.pop(key, None)
    obj = factory()
    if obj is None:
        return None
    win = obj if isinstance(obj, tk.Toplevel) else \
        (getattr(obj, "win", None) or getattr(obj, "window", None))
    try:
        if isinstance(win, tk.Toplevel) and win.winfo_exists():
            _singles[key] = win
            win._daybill_single = key
            win._daybill_single_obj = obj
    except Exception:
        pass
    return obj


# ── one hook when a window closes (its own <Destroy>) ────────
_TAG = "DayBillCloseGuard"


def _on_destroy(e):
    win = e.widget
    if not isinstance(win, tk.Toplevel):
        return
    try:
        _give_back_grab(win)
    except Exception:
        pass
    try:
        _return_focus(win)
    except Exception:
        pass
    key = getattr(win, "_daybill_single", None)
    if key is not None and _singles.get(key) is win:
        _singles.pop(key, None)
    win._daybill_single_obj = None


def _install(top):
    """Once per Tk interpreter: the <Destroy> class hook + focus tracker."""
    key = str(top.tk)
    if key in _state["interps"]:
        return
    _state["interps"].add(key)
    top.bind_class(_TAG, "<Destroy>", _on_destroy)
    top.bind_all("<FocusIn>", _track_focus, add="+")


_orig_top_init = tk.Toplevel.__init__


def _inside(w, top):
    p, t = str(w), str(top)
    return p == t or p.startswith(t + ".")


def _top_init(self, *a, **k):
    master = (a[0] if a else k.get("master")) or tk._default_root
    prev = None
    try:
        if master is not None:
            prev = _focus_now(master)
    except Exception:
        prev = None
    _orig_top_init(self, *a, **k)
    try:
        g = _guard(self, self.destroy)
        _orig_protocol(self, "WM_DELETE_WINDOW", g)
        self._daybill_close_fn = g
    except Exception:
        pass
    try:
        _install(self)
        _state["seq"] += 1
        self._daybill_seq = _state["seq"]
        if prev is None:
            prev = _focus_now(self)
        if prev is None and self.master is not None:
            last = self.master.winfo_toplevel().focus_lastfor()
            prev = last if isinstance(last, tk.Widget) else None
        if prev is not None and not _inside(prev, self):
            self._daybill_prev_focus = prev
        self.bindtags((_TAG,) + tuple(self.bindtags()))
    except Exception:
        pass


if not getattr(tk.Wm, "_daybill_close_guard", False):
    tk.Wm.wm_protocol = _protocol
    tk.Wm.protocol = _protocol
    tk.Toplevel.__init__ = _top_init
    tk.Misc.grab_set = _grab_set
    tk.Wm._daybill_close_guard = True
