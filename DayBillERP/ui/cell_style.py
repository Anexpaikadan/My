# ============================================================
# DayBill ERP - per-column text style for ttk.Treeview (v7.19)
# ------------------------------------------------------------
# Grid design ▸ a column's  Bold · Colour · Size  (like the Polosys
# FontBold / FontColour / FontSize columns). ttk.Treeview can only style
# whole rows, so the styled cells of the rows on screen get a small label
# drawn over them — same text, same row colour (selected, zebra, totals),
# the column's own font and colour. Only the rows you can see are drawn,
# so a report of 50,000 rows costs the same as one of 20.
#
# Clicks, double-clicks, right-clicks and the mouse wheel on a label go to
# the table underneath, so the table works exactly as before.
#
#   paint(tree)   — after the styles changed (table_columns calls it)
# A table with no styled column has no painter at all.
# ============================================================

import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

_EVENTS = ("<Configure>", "<<TreeviewSelect>>", "<<TreeviewOpen>>", "<<TreeviewClose>>",
           "<MouseWheel>", "<Button-4>", "<Button-5>", "<KeyRelease>", "<ButtonRelease-1>",
           "<B1-Motion>", "<Map>", "<<ColumnsChanged>>")


def _cursor(t):
    """The table's cursor as a name — it can be a tuple ('size_we',) while
    the mouse is on a column edge (v7.21: that broke every redraw)."""
    try:
        c = t.cget("cursor")
    except Exception:
        return ""
    if isinstance(c, (tuple, list)):
        c = c[0] if c else ""
    c = str(c or "")
    return "" if c.startswith("(") else c


def _styles(t):
    try:
        from ui.table_columns import colstyles_of, shown_columns
        st = colstyles_of(t)
        shown = shown_columns(t)
        return {c: s for c, s in st.items() if c in shown and s}
    except Exception:
        return {}


class CellPainter:
    def __init__(self, tree):
        self.t = tree
        self.pool = []
        self._pending = False
        self._fonts = {}
        tree._cell_painter = self
        for ev in _EVENTS:
            try:
                tree.bind(ev, lambda e: self.schedule(), add="+")
            except Exception:
                pass
        # redraw after rows change (the methods of this one table; reading a
        # value or the tags changes nothing → no redraw, else it never ends)
        for meth in ("insert", "delete", "detach", "move", "item", "set"):
            try:
                orig = getattr(tree, meth)
            except Exception:
                continue

            def wrapped(*a, _o=orig, _m=meth, **k):
                r = _o(*a, **k)
                if _m in ("insert", "delete", "detach", "move") or k \
                        or (_m == "set" and len(a) >= 3):
                    self.schedule()
                return r
            setattr(tree, meth, wrapped)
        self._hook_scroll()

    # ── when to draw ─────────────────────────────────────────
    def _hook_scroll(self):
        """The list scrolled (scroll bar, wheel, keys) → draw again."""
        for opt in ("yscrollcommand", "xscrollcommand"):
            try:
                cmd = self.t.cget(opt)
            except Exception:
                continue
            if not cmd or getattr(self.t, "_cs_hooked_" + opt, False):
                continue

            def _sc(first, last, _cmd=cmd):
                try:
                    self.t.tk.call(_cmd, first, last) if isinstance(_cmd, str) else _cmd(first, last)
                except Exception:
                    pass
                self.schedule()
            try:
                self.t.configure(**{opt: _sc})
                setattr(self.t, "_cs_hooked_" + opt, True)
            except Exception:
                pass

    def schedule(self):
        if self._pending:
            return
        self._pending = True
        try:
            self.t.after_idle(self.redraw)
        except tk.TclError:
            self._pending = False

    # ── colours and fonts ────────────────────────────────────
    def _style_name(self):
        try:
            return str(self.t.cget("style") or "") or "Treeview"
        except Exception:
            return "Treeview"

    def _look(self, name, opt, state=None):
        st = ttk.Style(self.t)
        for n in (name, "Treeview"):
            try:
                v = st.lookup(n, opt, state) if state else st.lookup(n, opt)
            except Exception:
                v = ""
            if v:
                return str(v)
        return ""

    def _row_colours(self, iid, selected, sname):
        """(background, foreground, tag font) of a row as the table shows it."""
        if selected:
            bg = self._look(sname, "background", ["selected"]) or "#D6E8FF"
            fg = self._look(sname, "foreground", ["selected"]) or "#0B1B33"
        else:
            bg, fg = "", ""
        font = ""
        try:
            tags = list(ttk.Treeview.item(self.t, iid, "tags") or ())
        except Exception:
            tags = []
        for tag in tags:              # the first tag that sets it wins (like Tk)
            try:
                if not bg:
                    bg = str(self.t.tag_configure(tag, "background") or "")
                if not fg:
                    fg = str(self.t.tag_configure(tag, "foreground") or "")
                if not font:
                    font = str(self.t.tag_configure(tag, "font") or "")
            except Exception:
                pass
        if not bg:
            bg = self._look(sname, "fieldbackground") or self._look(sname, "background") or "white"
        if not fg:
            fg = self._look(sname, "foreground") or "black"
        return bg, fg, font

    def _font(self, base, spec):
        key = (base, bool(spec.get("bold")), spec.get("size"))
        f = self._fonts.get(key)
        if f is not None:
            return f
        try:
            a = tkfont.Font(self.t, font=base or "TkDefaultFont").actual()
        except Exception:
            a = {"family": "Segoe UI", "size": 9, "weight": "normal"}
        size = int(spec.get("size") or 0) or abs(int(a.get("size") or 9)) or 9
        weight = "bold" if spec.get("bold") else (a.get("weight") or "normal")
        f = (a.get("family") or "Segoe UI", size, weight)
        self._fonts[key] = f
        return f

    # ── the labels ───────────────────────────────────────────
    def _label(self, i):
        while len(self.pool) <= i:
            lb = tk.Label(self.t, bd=0, highlightthickness=0, padx=4, pady=0)
            for seq in ("<ButtonPress-1>", "<ButtonRelease-1>", "<Motion>", "<Button-3>",
                        "<MouseWheel>", "<Button-4>", "<Button-5>"):
                lb.bind(seq, lambda e, s=seq: self._forward(e, s))
            self.pool.append(lb)
        return self.pool[i]

    def _forward(self, e, seq):
        """A click on a label is a click on the table under it."""
        t = self.t
        try:
            x = e.widget.winfo_x() + e.x
            y = e.widget.winfo_y() + e.y
            kw = {"x": x, "y": y, "rootx": e.x_root, "rooty": e.y_root, "state": e.state}
            if seq == "<MouseWheel>":
                kw["delta"] = e.delta
            if seq in ("<ButtonPress-1>", "<ButtonRelease-1>"):
                # keep the real time, so two quick clicks are still a double-click
                kw["time"] = e.time
            if seq in ("<ButtonPress-1>", "<Button-3>"):
                try:
                    t.focus_set()
                except Exception:
                    pass
            # queued ("tail"): the table sees press, release, press … in a row,
            # so a double-click on a styled cell is still a double-click
            t.event_generate(seq, when="tail", **kw)
        except Exception:
            pass
        return "break"

    def hide(self):
        for lb in self.pool:
            try:
                lb.place_forget()
            except Exception:
                pass

    def _visible_rows(self, H):
        """The rows on screen, top to bottom (no walk over every row)."""
        t = self.t
        out, seen, y = [], set(), 0
        step = 4
        while y < H and len(out) < 400:
            try:
                iid = t.identify_row(y)
            except Exception:
                iid = ""
            if iid and iid not in seen:
                seen.add(iid)
                try:
                    b = t.bbox(iid)
                except Exception:
                    b = ""
                if b:
                    out.append(iid)
                    step = max(4, int(b[3]) - 2)
                    y = int(b[1]) + int(b[3]) + 1
                    continue
            y += step
        return out

    def redraw(self):
        """Never lets an error out (a pop-up on every scroll would stop the
        cashier) — a failed draw just hides the labels."""
        try:
            self._redraw()
        except Exception:
            self._pending = False
            try:
                self.hide()
            except Exception:
                pass

    def _redraw(self):
        self._pending = False
        t = self.t
        try:
            if not t.winfo_exists():
                return
            if not t.winfo_ismapped():
                return self.hide()
            W, H = t.winfo_width(), t.winfo_height()
        except tk.TclError:
            return
        styles = _styles(t)
        if not styles:
            return self.hide()
        sname = self._style_name()
        base = self._look(sname, "font") or "TkDefaultFont"
        try:
            sel = set(t.selection())
        except Exception:
            sel = set()
        n = 0
        for iid in self._visible_rows(H):
            bg, fg, tagfont = self._row_colours(iid, iid in sel, sname)
            for c, spec in styles.items():
                try:
                    b = t.bbox(iid, c)
                except Exception:
                    b = ""
                if not b:
                    continue
                x, y, w, h = (int(v) for v in b)
                if w < 4 or x >= W:
                    continue
                try:
                    text = ttk.Treeview.set(t, iid, c)
                except Exception:
                    text = ""
                try:
                    anchor = str(t.column(c, "anchor") or "w")
                except Exception:
                    anchor = "w"
                lb = self._label(n)
                n += 1
                lb.configure(text=text, anchor=anchor, bg=bg,
                             fg=spec.get("color") or fg,
                             font=self._font(tagfont or base, spec),
                             cursor=_cursor(t))
                lb.place(x=x, y=y, width=max(1, w - 1), height=max(1, h - 1))
                lb.lower()            # an editor box typed in stays on top
        for lb in self.pool[n:]:
            try:
                lb.place_forget()
            except Exception:
                pass


def paint(tree):
    """Draw the styled columns of this table (a painter is made the first
    time a column gets a style; none for tables without styles)."""
    p = getattr(tree, "_cell_painter", None)
    if p is None:
        if not _styles(tree):
            return None
        try:
            p = CellPainter(tree)
        except Exception:
            return None
    p._fonts.clear()
    p._hook_scroll()
    p.schedule()
    return p
