# ============================================================
# DayBill ERP - toast: a small message that goes away by itself (v7.18.1)
# "Saved", "Confirmed" … no OK button to press any more. It sits at the
# bottom-right of the DayBill window for a few seconds; a click closes it.
#   show(text, kind="ok"|"warn"|"info", ms=2600, parent=None)
#   info(title, text, parent=None)   — drop-in for messagebox.showinfo
# ============================================================
import tkinter as tk

_LIVE = []


def _root(parent=None):
    try:
        if parent is not None:
            return parent.winfo_toplevel()
    except Exception:
        pass
    return tk._default_root


def show(text, kind="ok", ms=2600, parent=None):
    r = _root(parent)
    if r is None:
        return None
    try:
        from config import settings as cfg
        if not cfg.flag("toast_messages", True):
            from tkinter import messagebox
            messagebox.showinfo("DayBill", text, parent=parent)
            return None
        C = cfg.theme()
    except Exception:
        C = {}
    colours = {"ok": C.get("success", "#16A34A"), "warn": C.get("warning", "#D97706"),
               "info": C.get("primary", "#2563EB")}
    bg = colours.get(kind, colours["ok"])
    icon = {"ok": "✔", "warn": "⚠", "info": "ℹ"}.get(kind, "✔")
    for old in list(_LIVE):
        try:
            old.destroy()
        except Exception:
            pass
        _LIVE.remove(old)
    w = tk.Toplevel(r)
    w.overrideredirect(True)
    try:
        w.transient(r)
    except Exception:
        pass
    w.configure(bg=bg)
    lab = tk.Label(w, text="%s  %s" % (icon, text), font=("Segoe UI", 10, "bold"), bg=bg,
                   fg="white", justify="left", padx=16, pady=10, wraplength=420)
    lab.pack()
    try:
        w.update_idletasks()
        top = _root(None) or r
        x = top.winfo_rootx() + top.winfo_width() - w.winfo_reqwidth() - 24
        y = top.winfo_rooty() + top.winfo_height() - w.winfo_reqheight() - 60
        if parent is not None:
            pt = parent.winfo_toplevel()
            x = pt.winfo_rootx() + pt.winfo_width() - w.winfo_reqwidth() - 24
            y = pt.winfo_rooty() + pt.winfo_height() - w.winfo_reqheight() - 70
        w.geometry("+%d+%d" % (max(0, x), max(0, y)))
        w.lift()
    except Exception:
        pass
    for x_ in (w, lab):
        x_.bind("<Button-1>", lambda e: _close(w))
    _LIVE.append(w)
    w.after(ms, lambda: _close(w))
    return w


def _close(w):
    try:
        w.destroy()
    except Exception:
        pass
    if w in _LIVE:
        _LIVE.remove(w)


def info(title, text, parent=None):
    t = str(text or "").replace("\n", "  ·  ")
    return show(t, "ok", 2800, parent)
