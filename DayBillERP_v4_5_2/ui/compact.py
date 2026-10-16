# ============================================================
# DayBill ERP - compact windows + visible edges  (v6.7)
# ------------------------------------------------------------
# Design: Figma "DayBill ERP — UI 6.7 (compact headers, elevation)".
#
#   strip(win)        the coloured title strip of a window: 40–56 px → ~30
#   tighten(frame)    less padding around header fields (ipady 6 → 2 …)
#   one_row(grid)     header fields of a document on ONE row (wide screens)
#   doc_form(form)    all of it for Sales / Purchase / Return / Quotation:
#                     ~250 px above the item grid → ~110 px
#   edges(win)        every pop-up gets a clear 1 px border; Windows also
#                     draws a shadow (DWM for framed windows, CS_DROPSHADOW
#                     for frameless lists / calendars / toasts)
#   page_shadow(...)  soft shadow under the page windows inside DayBill
# Nothing here changes what a window does — only how much room it takes
# and how its edge looks. Turn it off: Settings ▸ System ▸ compact.
# ============================================================
import sys
import tkinter as tk
from tkinter import ttk

try:
    from config import settings as cfg
except Exception:                                       # pragma: no cover
    cfg = None


def on():
    try:
        return bool(cfg.flag("ui_compact", True))
    except Exception:
        return True


def _px(n):
    try:
        from ui.zoom import px
        return px(n)
    except Exception:
        return int(n)


def strong_border(C=None):
    """The edge colour of pages / dialogs / pop-ups (clearly visible on
    white and on the grey page background, in every theme)."""
    C = C or (cfg.theme() if cfg else {})
    try:
        return cfg.mix(C.get("border", "#E2E6EE"), C.get("text_secondary", "#4B5563"), 0.45)
    except Exception:
        return "#94A3B8"


# ── title strip ───────────────────────────────────────────────
_STRIP_COLOURS = None


def _strip_colours(C):
    cols = {str(C.get(k, "")).upper() for k in ("primary", "primary_dark", "danger", "success", "info",
                                                 "sidebar_bg", "warning")}
    return cols | {"#3A1FD6", "#2A14A8", "#128C7E", "#075E54", "#FFFFFF"}


def _font_size(w):
    try:
        f = w.cget("font")
        if isinstance(f, (tuple, list)) and len(f) >= 2:
            return f[0], int(f[1]), tuple(f[2:])
        if isinstance(f, str) and f:
            import tkinter.font as tkf
            a = tkf.Font(root=w, font=f).actual()
            return a["family"], int(a["size"]), (("bold",) if a.get("weight") == "bold" else ())
    except Exception:
        pass
    return None


def strip(win, height=None):
    """The coloured band at the top of a window → slim. Returns the strip."""
    if getattr(win, "_strip_done", False) or getattr(win, "_keep_header", False):
        return None
    C = cfg.theme() if cfg else {}
    cols = _strip_colours(C)
    try:
        slaves = list(win.pack_slaves()[:3])
        if len(win.pack_slaves()) == 1:
            slaves += list(win.pack_slaves()[0].pack_slaves()[:2])
    except Exception:
        return None
    for fr in slaves:
        try:
            if fr.winfo_class() != "Frame" or str(fr.cget("bg")).upper() not in cols:
                continue
            h = int(float(fr.cget("height") or 0))
            if h < 34 or h > 64:
                continue
            info = fr.pack_info()
            if info.get("fill") not in ("x", "both"):
                continue
            win._strip_done = True
            fr.configure(height=max(28, height or _px(26)))
            for k in fr.winfo_children():
                if k.winfo_class() in ("Label", "Button"):
                    fs = _font_size(k)
                    if fs and fs[1] > 11:
                        k.configure(font=(fs[0], 11) + fs[2])
                    try:
                        pi = k.pack_info()
                        if int(str(pi.get("padx", 0)).split()[0]) > 12:
                            k.pack_configure(padx=12)
                    except Exception:
                        pass
            return fr
        except Exception:
            continue
    return None


# ── less padding ──────────────────────────────────────────────
def _pads(v):
    if isinstance(v, (tuple, list)):
        return tuple(int(float(x)) for x in v)
    s = str(v).split()
    return tuple(int(float(x)) for x in s) if s else (0,)


def _shrink(v, big, to):
    p = _pads(v)
    q = tuple(to if x >= big else x for x in p)
    return q[0] if len(q) == 1 else q


def _compact_style(w):
    """A ttk Combobox / Entry style with less inner padding (made once)."""
    try:
        st = ttk.Style(w)
        if "Compact.TCombobox" not in st.element_names() and not getattr(_compact_style, "done", False):
            st.configure("Compact.TCombobox", padding=(4, 0, 2, 0))
            _compact_style.done = True
        return "Compact.TCombobox"
    except Exception:
        return None


def tighten(frame, ipady=2, skip=()):
    """Inputs with a lot of inner padding → ipady 2; gaps of 6+ px → 2;
    combo boxes and small buttons a little lower too."""
    stack = [frame]
    while stack:
        w = stack.pop()
        if w in skip:
            continue
        try:
            kids = w.winfo_children()
        except Exception:
            kids = []
        stack.extend(kids)
        try:
            cls = w.winfo_class()
            if cls == "TCombobox" and str(w.cget("style")) in ("", "TCombobox"):
                sty = _compact_style(w)
                if sty:
                    w.configure(style=sty)
            elif cls == "Button" and int(float(w.cget("pady"))) >= 3:
                w.configure(pady=1)
            elif cls in ("Checkbutton", "Radiobutton") and int(float(w.cget("pady"))) >= 1:
                w.configure(pady=0)
        except Exception:
            pass
        try:
            mgr = w.winfo_manager()
        except Exception:
            continue
        try:
            if mgr == "pack":
                info = w.pack_info()
                kw = {}
                if _pads(info.get("ipady", 0))[0] >= 4:
                    kw["ipady"] = 0 if w.winfo_class() == "TCombobox" else ipady
                if max(_pads(info.get("pady", 0))) >= 5:
                    kw["pady"] = _shrink(info.get("pady", 0), 5, 2)
                if kw:
                    w.pack_configure(**kw)
            elif mgr == "grid":
                info = w.grid_info()
                kw = {}
                if max(_pads(info.get("pady", 0))) >= 4:
                    kw["pady"] = _shrink(info.get("pady", 0), 4, 1)
                if _pads(info.get("ipady", 0))[0] >= 4:
                    kw["ipady"] = ipady
                if kw:
                    w.grid_configure(**kw)
        except Exception:
            continue


def one_row(grid, min_width=1150):
    """Header cells laid out in rows of 4 → one row (when the window is wide
    enough). The cells keep their order; a wide cell (Notes) gets more room."""
    try:
        cells = sorted(grid.grid_slaves(), key=lambda w: (int(w.grid_info()["row"]),
                                                          int(w.grid_info()["column"])))
    except Exception:
        return False
    if not cells or len(cells) > 8:
        return False
    try:
        top = grid.winfo_toplevel()
        if top.winfo_screenwidth() < min_width:
            return False
    except Exception:
        pass
    col = 0
    for i in range(16):
        grid.columnconfigure(i, weight=0, uniform="")
    for w in cells:
        span = int(w.grid_info().get("columnspan", 1) or 1)
        w.grid_configure(row=0, column=col, columnspan=1, sticky="new")
        grid.columnconfigure(col, weight=2 if span > 1 else 1, uniform="one" if col else "",
                             minsize=_px(200) if col == 0 else 0)   # number + ▲▼🔍
        col += 1
    grid._one_row = True
    return True


def buttons_first(frame):
    """Entry + small buttons on one line ([number] ▲ ▼ 🔍, [invoice #] Load):
    pack the buttons first so a narrow cell squeezes the entry, never the
    buttons."""
    for line in [frame] + [w for w in _all(frame) if w.winfo_class() == "Frame"]:
        try:
            sl = line.pack_slaves()
        except Exception:
            continue
        ents = [w for w in sl if w.winfo_class() in ("Entry", "TEntry", "TCombobox")
                and str(w.pack_info().get("expand")) in ("1", "True", "true")]
        if len(ents) != 1:
            continue
        e = ents[0]
        after = sl[sl.index(e) + 1:]
        if not after or not all(w.winfo_class() == "Button" for w in after):
            continue
        einfo = {k: v for k, v in e.pack_info().items() if k not in ("in", "side")}
        binfo = [(b, {k: v for k, v in b.pack_info().items() if k not in ("in", "side")}) for b in after]
        e.pack_forget()
        for b, _i in binfo:
            b.pack_forget()
        for b, i in reversed(binfo):
            b.pack(side="right", **i)
        e.pack(side="left", **einfo)


def merge_find(form):
    """'☐ Find [   ]' under the document number takes a whole extra line →
    a 🔍 button next to ▲▼; the find box shows only while it is on."""
    fe = getattr(form, "find_entry", None)
    var = getattr(form, "find_on", None) or getattr(form, "find_enabled", None)
    if fe is None or var is None:
        return False
    row = fe.master
    try:
        sibs = row.master.pack_slaves()
        if row.winfo_manager() != "pack" or row not in sibs or sibs.index(row) == 0:
            return False                  # find is already on the number line (sales invoice)
        num_line = sibs[sibs.index(row) - 1]
        if num_line.winfo_class() != "Frame":
            return False
    except Exception:
        return False
    C = cfg.theme() if cfg else {}
    toggle = getattr(form, "_toggle_find", None)

    def flip():
        var.set(not var.get())
        if var.get():
            row.pack(fill="x", pady=(1, 0))
        else:
            row.pack_forget()
        if toggle:
            toggle()
    b = tk.Button(num_line, text="🔍", font=("Segoe UI Emoji", 8), width=2, relief="flat",
                  bg=C.get("content_bg", "#F3F5F9"), cursor="hand2", command=flip)
    b.pack(side="left")
    row.pack_forget()
    # the checkbox itself still works when the row is shown
    form._find_btn = b
    return True


def doc_form(form):
    """Sales / Purchase / Return / Quotation: the minimum header."""
    if not on() or getattr(form, "_compacted", False):
        return False
    win = form.win
    body = getattr(form, "form_body", None)
    if body is None or not body.winfo_children():
        return False                          # not built yet — the next try does it
    form._compacted = True
    win._compact = True
    strip(win)
    if body is not None:
        grids = [g for g in _all(body) if g.winfo_class() == "Frame" and len(g.grid_slaves()) in range(5, 9)
                 and all(s.winfo_class() == "Frame" for s in g.grid_slaves())]
        merge_find(form)
        for g in grids[:1]:
            if one_row(g):
                buttons_first(g)
        tighten(body)
    items = getattr(form, "items_area", None)
    if items is not None:
        for k in items.pack_slaves()[:3]:            # the 'Items' title line, not the grid
            if k.winfo_class() == "Label":
                try:
                    k.pack_configure(pady=(2, 0))
                    fs = _font_size(k)
                    if fs and fs[1] > 9:
                        k.configure(font=(fs[0], 9) + fs[2])
                except Exception:
                    pass
            elif k.winfo_class() == "Frame" and k.winfo_reqheight() < 60:
                tighten(k)
                try:
                    pi = k.pack_info()
                    if max(_pads(pi.get("pady", 0))) >= 3:
                        k.pack_configure(pady=(2, 0) if isinstance(_pads(pi.get("pady", 0)), tuple) else 1)
                except Exception:
                    pass
    bar = getattr(form, "toolbar", None)
    if bar is not None:
        tighten(bar)
    return True


def _all(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        out.extend(_all(c))
    return out


# ── visible edges + shadow ───────────────────────────────────
GCL_STYLE = -26
CS_DROPSHADOW = 0x00020000


def _hwnd(w):
    import ctypes
    try:
        return int(w.wm_frame(), 16)
    except Exception:
        return ctypes.windll.user32.GetParent(w.winfo_id())


def edges(win):
    """A clear edge on every pop-up window (+ a Windows shadow)."""
    if getattr(win, "_edges_done", False) or not on():
        return False
    win._edges_done = True
    C = cfg.theme() if cfg else {}
    col = strong_border(C)
    frameless = False
    try:
        frameless = bool(win.overrideredirect())
    except Exception:
        pass
    try:
        if frameless and not getattr(win, "_no_edge", False):
            if int(float(win.cget("highlightthickness") or 0)) == 0:
                win.configure(highlightthickness=1, highlightbackground=col, highlightcolor=col)
        elif not frameless:
            win.configure(highlightthickness=1, highlightbackground=col, highlightcolor=col)
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            import ctypes
            win.update_idletasks()
            h = _hwnd(win)
            if h and frameless:
                u = ctypes.windll.user32
                get = getattr(u, "GetClassLongPtrW", None) or u.GetClassLongW
                put = getattr(u, "SetClassLongPtrW", None) or u.SetClassLongW
                st = get(h, GCL_STYLE)
                if not st & CS_DROPSHADOW:
                    put(h, GCL_STYLE, st | CS_DROPSHADOW)
        except Exception:
            pass
    return True


class PageShadow:
    """A soft 3-step shadow under a page window placed inside the desktop
    (Tk has no blur — three thin frames of fading grey do the job)."""

    STEPS = (("#C9D0DA", 1), ("#DCE1E8", 2), ("#E9EDF2", 3))

    def __init__(self, child):
        self.child = child
        self.frames = []
        parent = child.master
        for colr, off in self.STEPS:
            f = tk.Frame(parent, bg=colr, bd=0, highlightthickness=0)
            self.frames.append((f, off))
        child.bind("<Configure>", lambda e: self.follow(), add="+")
        child.bind("<Map>", lambda e: self.follow(), add="+")
        child.bind("<Unmap>", lambda e: self.hide(), add="+")
        child.bind("<Destroy>", lambda e: e.widget is child and self.destroy(), add="+")

    def follow(self):
        c = self.child
        try:
            if not c.winfo_ismapped():
                return self.hide()
            x, y, w, h = c.winfo_x(), c.winfo_y(), c.winfo_width(), c.winfo_height()
            for f, off in reversed(self.frames):
                f.place(x=x - off + 1, y=y + off - 1, width=w + 2 * off - 2, height=h + off)
                f.lower(c)
        except Exception:
            pass

    def hide(self):
        for f, _o in self.frames:
            try:
                f.place_forget()
            except Exception:
                pass

    def destroy(self):
        for f, _o in self.frames:
            try:
                f.destroy()
            except Exception:
                pass


def page_shadow(child):
    if not on():
        return None
    try:
        return PageShadow(child)
    except Exception:
        return None
