# ============================================================
# DayBill ERP - Excel-style cell lines for ttk.Treeview
# ------------------------------------------------------------
# ttk.Treeview has no grid lines. ExcelGrid draws thin vertical lines
# between columns and horizontal lines under every row (also through the
# empty area, like a spreadsheet), and keeps them in place when rows are
# added / removed, the window is resized, columns are dragged or the
# list scrolls.  Usage:   ExcelGrid(tree)
# ============================================================

import tkinter as tk
from tkinter import ttk

LINE = "#C9D2DE"        # cell border
HEAD_LINE = "#AEB9C7"   # under the header


class ExcelGrid:
    def __init__(self, tree, color=LINE, fill_empty=True, header_line=HEAD_LINE,
                 select_bg="#D6E8FF", select_fg="#0B1B33"):
        self.tree = tree
        self.color = color
        self.fill_empty = fill_empty
        self.header_line = header_line
        self._v, self._h = [], []
        self._pending = False
        tree._excel_grid = self
        # Excel-like selection: light blue row, dark text
        try:
            st = ttk.Style()
            name = str(tree.cget("style") or "Treeview")
            st.map(name, background=[("selected", select_bg)],
                   foreground=[("selected", select_fg)])
        except Exception:
            pass
        for ev in ("<Configure>", "<ButtonRelease-1>", "<B1-Motion>", "<MouseWheel>",
                   "<Button-4>", "<Button-5>", "<KeyRelease>", "<<TreeviewSelect>>",
                   "<<TreeviewOpen>>", "<Map>"):
            tree.bind(ev, lambda e: self.schedule(), add="+")
        # redraw after rows change / the list scrolls
        for meth in ("insert", "delete", "detach", "move", "item"):
            orig = getattr(tree, meth)

            def wrapped(*a, _o=orig, **k):
                r = _o(*a, **k)
                self.schedule()
                return r
            setattr(tree, meth, wrapped)
        ysc = tree.cget("yscrollcommand")
        if ysc:
            def _ys(first, last, _cmd=ysc):
                try:
                    tree.tk.call(_cmd, first, last) if isinstance(_cmd, str) else _cmd(first, last)
                except Exception:
                    pass
                self.schedule()
            tree.configure(yscrollcommand=_ys)
        self.schedule()

    # ── drawing ──────────────────────────────────────────────
    def schedule(self):
        if self._pending:
            return
        self._pending = True
        try:
            self.tree.after_idle(self.redraw)
        except tk.TclError:
            self._pending = False

    def _line(self, pool, i, color):
        while len(pool) <= i:
            f = tk.Frame(self.tree, bg=color, bd=0, highlightthickness=0)
            pool.append(f)
        f = pool[i]
        f.configure(bg=color)
        return f

    def _row_height(self):
        kids = self.tree.get_children()
        for iid in kids:
            b = self.tree.bbox(iid)
            if b:
                return b[3]
        try:
            st = ttk.Style()
            h = st.lookup(str(self.tree.cget("style") or "Treeview"), "rowheight")
            return int(h) if h else 22
        except Exception:
            return 22

    def redraw(self):
        self._pending = False
        t = self.tree
        try:
            if not t.winfo_exists() or not t.winfo_ismapped():
                return
            W, H = t.winfo_width(), t.winfo_height()
        except tk.TclError:
            return
        cols = list(t["displaycolumns"])
        if cols == ["#all"] or not cols:
            cols = list(t["columns"])
        # column x positions (respect horizontal scroll via the first row's bbox)
        xs, x = [], 0
        first = next((i for i in t.get_children() if t.bbox(i)), None)
        for c in cols:
            try:
                w = int(t.column(c, "width"))
            except Exception:
                w = 0
            if first:
                b = t.bbox(first, c)
                if b:
                    x = b[0]
                    w = b[2]
            x += w
            xs.append(x)
        # top of the rows area = header height
        rh = self._row_height()
        top = 0
        if first:
            top = t.bbox(first)[1]
        elif "headings" in str(t.cget("show")):
            top = rh + 2
        # vertical lines (through header too)
        n = 0
        for xv in xs[:-1] if len(xs) > 1 else []:
            if 0 < xv < W:
                self._line(self._v, n, getattr(self.tree, "_ct_line_color", None) or self.color).place(
                    x=xv - 1, y=0, width=1, height=H)
                n += 1
        for f in self._v[n:]:
            f.place_forget()
        # horizontal lines under each row (and through the empty area)
        right = min(W, xs[-1]) if xs else W
        m = 0
        ys = []
        for iid in t.get_children():
            b = t.bbox(iid)
            if b:
                ys.append(b[1] + b[3])
        y = ys[-1] if ys else top
        if self.fill_empty and rh > 4:
            while y + rh <= H:
                y += rh
                ys.append(y)
        for yv in ys:
            if 0 < yv < H:
                self._line(self._h, m, getattr(self.tree, "_ct_line_color", None) or self.color).place(
                    x=0, y=yv - 1, width=right, height=1)
                m += 1
        for f in self._h[m:]:
            f.place_forget()
        if top and "headings" in str(t.cget("show")):
            hl = self._line(self._h, m, self.header_line)
            hl.place(x=0, y=top - 1, width=W, height=1)
            m += 1
        for f in self._v + self._h:
            try:
                f.lower()
            except tk.TclError:
                pass


def excel_grid(tree, **kw):
    """Attach Excel-style cell lines once (safe to call twice)."""
    if getattr(tree, "_excel_grid", None) is None:
        ExcelGrid(tree, **kw)
    return tree._excel_grid
