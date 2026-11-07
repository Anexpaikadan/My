# ============================================================
# DayBill ERP - readable colours and small help tips (v7.9.4)
# ------------------------------------------------------------
# Every theme (light, dark, coloured) must keep text readable: WCAG
# asks 4.5 : 1 for normal text, 3 : 1 for large bold figures.
#
#   readable(fg, bg, ratio=4.5)  fg made darker / lighter until it is
#                                readable on bg (same hue)
#   button_bg(bg)                a button colour dark enough for white text
#   contrast(a, b)               the ratio, 1 … 21
#   tip(widget, text)            a short help text on mouse-over AND on
#                                keyboard focus (never mouse-only)
# ============================================================
import tkinter as tk


def _rgb(h):
    h = str(h or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _lum(h):
    def f(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return _hex([x + (y - x) * t for x, y in zip(ra, rb)])


def readable(fg, bg, ratio=4.5):
    """fg, darkened on a light background (lightened on a dark one) just
    enough to reach the ratio."""
    if contrast(fg, bg) >= ratio:
        return _hex(_rgb(fg))
    target = "#000000" if _lum(bg) > 0.18 else "#FFFFFF"
    for i in range(1, 21):
        c = _mix(fg, target, i / 20.0)
        if contrast(c, bg) >= ratio:
            return c
    return target


def button_bg(bg, text="#FFFFFF", ratio=4.5):
    """A button colour (same hue) on which white text is readable."""
    if contrast(text, bg) >= ratio:
        return _hex(_rgb(bg))
    for i in range(1, 21):
        c = _mix(bg, "#000000", i / 20.0)
        if contrast(text, c) >= ratio:
            return c
    return "#000000"


class _Tip:
    def __init__(self, widget, text):
        self.w, self.text, self.win = widget, text, None
        for ev in ("<Enter>", "<FocusIn>"):
            widget.bind(ev, self.show, add="+")
        for ev in ("<Leave>", "<FocusOut>", "<ButtonPress>", "<Destroy>"):
            widget.bind(ev, self.hide, add="+")

    def show(self, _e=None):
        if self.win or not self.text:
            return
        try:
            x = self.w.winfo_rootx() + 8
            y = self.w.winfo_rooty() + self.w.winfo_height() + 4
            self.win = tk.Toplevel(self.w)
            self.win.wm_overrideredirect(True)
            self.win.wm_geometry("+%d+%d" % (x, y))
            tk.Label(self.win, text=self.text, font=("Segoe UI", 9), bg="#0F172A", fg="#FFFFFF",
                     padx=8, pady=3, justify="left").pack()
        except tk.TclError:
            self.win = None

    def hide(self, _e=None):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None


def tip(widget, text):
    """Help text for a small or icon-only control (mouse and keyboard)."""
    t = _Tip(widget, text)
    widget._ink_tip = t
    return t
