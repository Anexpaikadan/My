# ============================================================
# DayBill ERP - Text size for the whole app
# ------------------------------------------------------------
# Settings ▸ System ▸ Text size (or the "Aa" button in the top bar).
#
# The screens were laid out at 1 pixel per font point, so a "9" font
# was only 9 px tall — too small on most monitors. apply(root) makes
# every font bigger by one factor (Tk scaling) and grows the things that
# are set in pixels with it, so nothing gets cut off:
#   • table rows (ttk rowheight) and table columns (Treeview widths)
#   • dialog windows (Toplevel sizes, kept centred and on the screen)
# 100 % = the old look. The POS screen keeps its own size setting
# (Settings ▸ POS ▸ Screen size) and is not changed by this.
#
# v5.25: pop-up windows open at a normal size (like the Product window):
# never more than 86 % × 91 % of the desktop, centred. Only the big
# document windows (sales / purchase / return / quotation) may fill the
# screen — they mark themselves with  win._doc_window = True.
# ============================================================
import re
import tkinter as tk
from tkinter import ttk

CHOICES = ["100%", "112%", "125%", "140%", "160%"]
DEFAULT = 125
_F = [1.0]                 # the factor in use (set by apply)
_patched = [False]
_RAW = {}


def percent(value=None):
    """Text size from the settings (or a given value) → 90..175."""
    if value is None:
        try:
            from config import settings as cfg
            value = cfg.get("ui_text_size", DEFAULT)
        except Exception:
            value = DEFAULT
    try:
        p = int(float(str(value).strip().rstrip("%")))
    except (TypeError, ValueError):
        p = DEFAULT
    return max(90, min(175, p))


def factor():
    return _F[0]


def px(n):
    """A pixel size made for 100 % → the size for the current text size."""
    return int(round(n * _F[0]))


def unscaled(size):
    """A font size that stays the same on screen whatever the text size
    (for screens with their own size setting, like the POS)."""
    return max(6, int(round(size / _F[0])))


def raw_column(tree, col, **kw):
    """Set a column width that is already in screen pixels (copied from
    another table) — not grown again."""
    return (_RAW.get("column") or ttk.Treeview.column)(tree, col, None, **kw)


def raw_geometry(win, geo):
    """Set a window size that is already in real screen pixels (worked
    out from winfo_… sizes) — not grown again by the text size."""
    return (_RAW.get("geometry") or tk.Wm.wm_geometry)(win, geo)


CAPTION = 32               # Windows title bar + frame (px)
POPUP_W, POPUP_H = 0.86, 0.91


def work_area(win):
    """(x0, y0, x1, y1) of the desktop without the Windows taskbar."""
    try:
        from ui.ui_polish import _work_area
        return _work_area(win)
    except Exception:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        return 0, 0, sw, sh - 40


def popup_cap(win):
    """Largest size (client area) a pop-up window opens at — a normal
    window in the middle of the screen, never full screen."""
    x0, y0, x1, y1 = work_area(win)
    return int((x1 - x0) * POPUP_W), int(((y1 - y0) - CAPTION) * POPUP_H)


def max_client(win):
    """Largest client size that still fits on the desktop with its title bar."""
    x0, y0, x1, y1 = work_area(win)
    return (x1 - x0) - 16, (y1 - y0) - CAPTION - 8


def apply(root, value=None):
    """Call once after tk.Tk() (before the login window)."""
    _F[0] = percent(value) / 100.0
    try:
        root.tk.call("tk", "scaling", _F[0])
    except Exception:
        pass
    if not _patched[0]:
        _patched[0] = True
        _patch()
    return _F[0]


# ── pixel things that must grow with the text ─────────────────
_GEO = re.compile(r"^(\d+)x(\d+)(([+-]-?\d+)([+-]-?\d+))?$")


def _skip(widget):
    try:
        if getattr(widget, "_no_zoom", False):
            return True
        return bool(widget.wm_overrideredirect())       # dropdowns sit on a field
    except Exception:
        return False


def _patch():
    # 1) table rows
    orig_conf = ttk.Style.configure

    def configure(self, style, query_opt=None, **kw):
        rh = kw.get("rowheight")
        if (isinstance(rh, (int, float)) and _F[0] != 1.0
                and not str(style).startswith(("POS", "Pos", "Dropdown"))):
            kw["rowheight"] = int(round(rh * _F[0]))
        return orig_conf(self, style, query_opt, **kw)
    ttk.Style.configure = configure

    # 2) table columns
    orig_col = ttk.Treeview.column

    def column(self, col, option=None, **kw):
        if _F[0] != 1.0 and not getattr(self, "_no_zoom", False):
            for k in ("width", "minwidth"):
                v = kw.get(k)
                if isinstance(v, (int, float)) and v > 0:
                    kw[k] = int(round(v * _F[0]))
        return orig_col(self, col, option, **kw)
    ttk.Treeview.column = column
    _RAW["column"] = orig_col

    # 3) dialog windows: W×H grows; a centred window stays centred;
    #    a pop-up never opens bigger than popup_cap (normal size)
    orig_geo = tk.Wm.wm_geometry

    def wm_geometry(self, newGeometry=None):
        if newGeometry is None or not isinstance(self, tk.Toplevel) or _skip(self):
            return orig_geo(self, newGeometry)
        m = _GEO.match(str(newGeometry).strip())
        if not m:
            return orig_geo(self, newGeometry)
        w, h = int(m.group(1)), int(m.group(2))
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if getattr(self, "_doc_window", False):
                limw, limh = sw - 20, sh - 60
            else:
                limw, limh = popup_cap(self)
        except Exception:
            return orig_geo(self, newGeometry)
        nw = min(int(round(w * _F[0])), limw)
        nh = min(int(round(h * _F[0])), limh)
        if getattr(self, "_doc_window", False):
            nw, nh = max(nw, min(w, sw)), max(nh, min(h, sh))
        if (nw, nh) == (w, h):
            return orig_geo(self, newGeometry)
        if not m.group(3):
            return orig_geo(self, "%dx%d" % (nw, nh))
        x, y = int(m.group(4).replace("+", "")), int(m.group(5).replace("+", ""))
        if abs(x - (sw - w) // 2) <= 3 and abs(y - (sh - h) // 2) <= 40:
            x, y = (sw - nw) // 2, max(0, (sh - nh) // 2 - 20)      # was centred → centre again
        x = max(0, min(x, sw - nw))
        y = max(0, min(y, sh - nh - 40))
        return orig_geo(self, "%dx%d+%d+%d" % (nw, nh, x, y))
    tk.Wm.wm_geometry = wm_geometry
    tk.Wm.geometry = wm_geometry
    _RAW["geometry"] = orig_geo

    orig_min = tk.Wm.wm_minsize

    def wm_minsize(self, width=None, height=None):
        if (width is not None and height is not None
                and isinstance(self, tk.Toplevel) and not _skip(self)):
            try:
                if getattr(self, "_doc_window", False):
                    sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                    limw, limh = sw - 40, sh - 80
                else:
                    limw, limh = popup_cap(self)     # never forces a pop-up full size
                width = min(int(round(width * _F[0])), limw)
                height = min(int(round(height * _F[0])), limh)
            except Exception:
                pass
        return orig_min(self, width, height)
    tk.Wm.wm_minsize = wm_minsize
    tk.Wm.minsize = wm_minsize
