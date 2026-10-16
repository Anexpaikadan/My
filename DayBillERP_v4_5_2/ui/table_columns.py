# ============================================================
# DayBill ERP - Columns tool for EVERY table (v6.2, app-wide)
# ------------------------------------------------------------
# Every list, register, report and entry grid (a ttk.Treeview with
# headings) gets the same column tool — nothing to add per screen:
#   • right-click a column heading → hide this column, set its width,
#     fit the width to the text, move it left / right, show / hide any
#     column, "Columns…" window, reset to default
#   • ☰ appears at the top-right corner when the mouse is on the
#     headings → the same menu
#   • drag a column edge = new width; double-click the edge = fit
#   • drag a heading onto another heading = move the column there
# The layout is remembered per table on this PC
# (config/table_layouts.json; kept by updates).
#
# Code that works with column POSITIONS keeps working: "#3",
# identify_column(), bbox(row, "#3"), column("#3"), heading("#3"),
# set(row, "#3") are translated to the program's own column order, so
# hiding / moving a column never makes a click land on the wrong column.
#
# A table can opt out with  tree._own_columns = True  (the POS cart has
# its own column setting) and keep columns always shown with
# tree._keep_columns = {"product"}.  After any change the table gets the
# virtual event <<ColumnsChanged>>.
# ============================================================

import json
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

T = ttk.Treeview
TAG = "DayBillColumns"
EVENT = "<<ColumnsChanged>>"
FILE = "table_layouts.json"
_O = {}                      # the original Treeview methods
_STORE = {"data": None, "path": None}
_BOUND = set()
_DRAG = {}
MIN_W, MAX_W = 20, 1500


# ── the saved layouts ────────────────────────────────────────
def _path():
    if _STORE["path"]:
        return _STORE["path"]
    try:
        from config.paths import config_file
        return config_file(FILE)
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", FILE)


def _tables():
    if _STORE["data"] is None:
        d = None
        try:
            with open(_path(), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = None
        if not isinstance(d, dict) or not isinstance(d.get("tables"), dict):
            d = {"version": 1, "tables": {}}
        _STORE["data"] = d
    return _STORE["data"]["tables"]


def _write():
    try:
        p = _path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_STORE["data"], f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
        return True
    except Exception:
        return False


def _zf():
    """Text-size factor (Settings ▸ Text size): widths are saved at 100 %."""
    try:
        from ui import zoom
        return float(zoom.factor() or 1.0)
    except Exception:
        return 1.0


# ── column lists ─────────────────────────────────────────────
def _as_list(t, v):
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [str(x) for x in t.tk.splitlist(v)]


def _all_cols(t):
    try:
        return [str(c) for c in t.tk.splitlist(t.cget("columns"))]
    except Exception:
        return []


def _norm(t, lst, cols=None):
    """Display list → column ids (Tk also takes numbers)."""
    cols = cols if cols is not None else _all_cols(t)
    out = []
    for c in lst:
        c = str(c)
        if c not in cols and c.isdigit() and int(c) < len(cols):
            c = cols[int(c)]
        if c in cols and c not in out:
            out.append(c)
    return out


def _base(t):
    """The columns the PROGRAM shows (its own displaycolumns)."""
    cols = _all_cols(t)
    b = getattr(t, "_ct_base", "#all")
    if b == "#all" or not b:
        return cols
    return _norm(t, b, cols) or cols


def shown_columns(t):
    """Column ids exactly as on screen (order, without hidden ones)."""
    cols = _all_cols(t)
    try:
        d = [str(x) for x in t.tk.splitlist(t.cget("displaycolumns"))]
    except Exception:
        d = []
    if not d or d == ["#all"]:
        return cols
    return _norm(t, d, cols)


def _off(t):
    if getattr(t, "_own_columns", False) or not getattr(t, "_ct_on", False):
        return True
    try:
        return "headings" not in str(t.cget("show"))
    except Exception:
        return True


def _keep(t):
    return set(getattr(t, "_keep_columns", ()) or ())


def _title(t, c):
    try:
        s = str(_O["heading"](t, c, "text") or "").strip().rstrip(" ▲▼↑↓").strip()
    except Exception:
        s = ""
    return s or str(c)


def _key(t):
    cols = _all_cols(t)
    if not cols:
        return None
    return "%s|%s" % (getattr(t, "_ct_from", "?"), ",".join(cols))


def _layout(t):
    k = getattr(t, "_ct_key", None)
    return _tables().get(k) if k else None


def _effective(t, base, lay):
    hidden = (set(lay.get("hidden") or []) & set(base)) - _keep(t)
    order = [c for c in (lay.get("order") or []) if c in base and c not in hidden]
    seen = set(order)
    for i, c in enumerate(base):        # columns the saved layout doesn't know
        if c in hidden or c in seen:
            continue
        pos = 0
        for p in reversed(base[:i]):
            if p in order:
                pos = order.index(p) + 1
                break
        order.insert(pos, c)
        seen.add(c)
    for c in base:                      # columns that must stay
        if c in _keep(t) and c not in order:
            order.append(c)
    return order or base[:1]


def _set_dc(t, eff, base):
    if eff == shown_columns(t):
        return
    if eff == base:
        val = "#all" if getattr(t, "_ct_base", "#all") == "#all" else list(base)
    else:
        val = list(eff)
    _O["configure"](t, None, displaycolumns=val)


def _fire(t):
    try:
        g = getattr(t, "_excel_grid", None)
        if g is not None:
            g.schedule()
    except Exception:
        pass
    try:
        t.event_generate(EVENT)
    except Exception:
        pass


def _apply(t, fire=True):
    """Put this table's saved layout on it (hidden / order / widths)."""
    if _off(t):
        return
    k = _key(t)
    t._ct_key = k
    lay = _tables().get(k) if k else None
    base = _base(t)
    if not base:
        return
    _set_dc(t, _effective(t, base, lay) if lay else base, base)
    if lay:
        zf = _zf()
        for c, w in (lay.get("widths") or {}).items():
            if c in base:
                try:
                    _O["column"](t, c, width=max(MIN_W, int(round(float(w) * zf))))
                except Exception:
                    pass
    if fire:
        try:
            t.after_idle(lambda: _fire(t))
        except Exception:
            pass


def remember(t):
    """Save what the table shows now as its layout."""
    k = _key(t)
    if not k or _off(t):
        return
    base = _base(t)
    shown = [c for c in shown_columns(t) if c in base]
    zf = _zf()
    widths = {}
    for c in base:
        try:
            widths[c] = int(round(int(_O["column"](t, c, "width")) / zf))
        except Exception:
            pass
    _tables()[k] = {"order": shown, "hidden": [c for c in base if c not in shown],
                    "widths": widths}
    t._ct_key = k
    _write()
    _fire(t)


def reset(t):
    """Back to the program's own columns and widths."""
    k = _key(t)
    if k and k in _tables():
        _tables().pop(k, None)
        _write()
    base = _base(t)
    _set_dc(t, base, base)
    for c, w in dict(getattr(t, "_ct_code_w", {}) or {}).items():
        try:
            if c in base:
                _O["column"](t, c, width=w)
        except Exception:
            pass
    _fire(t)


def set_name(t, name):
    """Give a table its own layout name (e.g. one grid class used by the
    sales, purchase and return forms → a layout for each)."""
    try:
        t._ct_from = str(name)
        _apply(t)
    except Exception:
        pass


# ── actions ──────────────────────────────────────────────────
def set_order(t, order):
    base = _base(t)
    order = [c for c in order if c in base]
    for c in base:
        if c in _keep(t) and c not in order:
            order.append(c)
    if not order:
        return False
    _set_dc(t, order, base)
    remember(t)
    return True


def hide(t, c):
    shown = shown_columns(t)
    if c not in shown or c in _keep(t) or len(shown) <= 1:
        return False
    return set_order(t, [x for x in shown if x != c])


def show(t, c):
    base, shown = _base(t), shown_columns(t)
    if c in shown or c not in base:
        return False
    i, pos = base.index(c), 0
    for p in reversed(base[:i]):
        if p in shown:
            pos = shown.index(p) + 1
            break
    shown.insert(pos, c)
    return set_order(t, shown)


def move(t, c, step):
    shown = shown_columns(t)
    if c not in shown:
        return False
    i = shown.index(c)
    j = max(0, min(len(shown) - 1, i + step))
    if i == j:
        return False
    shown.insert(j, shown.pop(i))
    return set_order(t, shown)


def move_to(t, c, target):
    """Drag a heading onto another: it takes that column's place."""
    shown = shown_columns(t)
    if c not in shown or target not in shown or c == target:
        return False
    j = shown.index(target)
    shown.remove(c)
    shown.insert(j, c)
    return set_order(t, shown)


def set_width(t, c, width):
    """Width in pixels at 100 % text size."""
    try:
        w = max(MIN_W, min(MAX_W, int(float(width))))
    except (TypeError, ValueError):
        return False
    _O["column"](t, c, width=int(round(w * _zf())))
    remember(t)
    return True


def _fonts(t):
    st = ttk.Style(t)
    style = str(t.cget("style") or "") or "Treeview"

    def font(*names):
        for n in names:
            try:
                f = st.lookup(n, "font")
            except Exception:
                f = ""
            if f:
                try:
                    return tkfont.Font(t, font=f)
                except Exception:
                    pass
        return tkfont.nametofont("TkDefaultFont")
    return font(style, "Treeview"), font(style + ".Heading", "Treeview.Heading", "Heading")


def fit_widths(t, cols=None):
    """Widths (screen pixels) that fit the heading and the text."""
    allc = _all_cols(t)
    cols = list(cols or shown_columns(t))
    body, head = _fonts(t)
    items = list(t.get_children(""))[:1000]
    vals = []
    for i in items:
        try:
            vals.append(t.item(i, "values") or ())
        except Exception:
            pass
    out = {}
    for c in cols:
        if c not in allc:
            continue
        w = head.measure(_title(t, c)) + 26
        idx = allc.index(c)
        for v in vals:
            if idx < len(v):
                s = str(v[idx])
                if s:
                    w = max(w, body.measure(s) + 18)
        out[c] = max(40, min(int(600 * _zf()), w))
    return out


def fit(t, cols=None):
    for c, w in fit_widths(t, cols).items():
        _O["column"](t, c, width=w)
    remember(t)


def ask_width(t, c):
    from tkinter import simpledialog
    zf = _zf()
    cur = int(round(int(_O["column"](t, c, "width")) / zf))
    v = simpledialog.askinteger("Column width",
                                'Width of "%s" in pixels (%d – %d):' % (_title(t, c), MIN_W, MAX_W),
                                initialvalue=cur, minvalue=MIN_W, maxvalue=MAX_W, parent=t)
    if v:
        set_width(t, c, v)


# ── the menu (heading right-click and the ☰ corner) ──────────
def menu(t, x_root, y_root, c=None, popup=True):
    base, shown = _base(t), shown_columns(t)
    m = tk.Menu(t, tearoff=0)
    if c and c in shown:
        name = _title(t, c)
        i = shown.index(c)
        can_hide = len(shown) > 1 and c not in _keep(t)
        m.add_command(label='Hide column "%s"' % name, command=lambda: hide(t, c),
                      state="normal" if can_hide else "disabled")
        m.add_command(label='Width of "%s"…' % name, command=lambda: ask_width(t, c))
        m.add_command(label="Fit width to text", command=lambda: fit(t, [c]))
        m.add_command(label="◀  Move left", command=lambda: move(t, c, -1),
                      state="normal" if i > 0 else "disabled")
        m.add_command(label="Move right  ▶", command=lambda: move(t, c, 1),
                      state="normal" if i < len(shown) - 1 else "disabled")
        m.add_separator()
    sub = tk.Menu(m, tearoff=0)
    m._vars = []
    for col in base:
        v = tk.BooleanVar(master=t, value=col in shown)
        m._vars.append(v)
        sub.add_checkbutton(label=_title(t, col), variable=v,
                            command=lambda col=col, v=v: (show(t, col) if v.get() else hide(t, col),
                                                          v.set(col in shown_columns(t))),
                            state="disabled" if col in _keep(t) else "normal")
    m.add_cascade(label="Show / hide columns", menu=sub)
    m.add_command(label="Fit all columns to text", command=lambda: fit(t))
    m.add_command(label="Columns…   (show, order, width)", command=lambda: ColumnsDialog(t))
    m.add_separator()
    m.add_command(label="Reset columns to default", command=lambda: reset(t),
                  state="normal" if _layout(t) or shown != base else "disabled")
    t._ct_menu = m
    if popup:
        try:
            m.tk_popup(x_root, y_root)
        finally:
            try:
                m.grab_release()
            except Exception:
                pass
    return m


# ── the Columns… window ──────────────────────────────────────
class ColumnsDialog:
    ROWS = 14

    def __init__(self, tree):
        self.t = t = tree
        self.base = _base(t)
        shown = shown_columns(t)
        zf = _zf()
        order = [c for c in shown if c in self.base] + [c for c in self.base if c not in shown]
        self.rows = []
        for c in order:
            try:
                w = int(round(int(_O["column"](t, c, "width")) / zf))
            except Exception:
                w = 100
            self.rows.append([c, tk.BooleanVar(master=t, value=c in shown),
                              tk.StringVar(master=t, value=str(w))])
        self.win = win = tk.Toplevel(t)
        t._ct_dialog = self
        win.title("Columns  ·  الأعمدة")
        win.configure(bg="white")
        try:
            win.transient(t.winfo_toplevel())
        except Exception:
            pass
        tk.Label(win, text="Columns of this table", font=("Segoe UI", 12, "bold"),
                 bg="white", fg="#1F2937").pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(win, text="Tick = show.   ▲ ▼ = move.   Width in pixels.\n"
                           "Saved for this table on this PC.",
                 font=("Segoe UI", 9), bg="white", fg="#6B7280", justify="left"
                 ).pack(anchor="w", padx=14, pady=(2, 8))
        mid = tk.Frame(win, bg="white")
        mid.pack(fill="both", expand=True, padx=10)
        many = len(self.rows) > self.ROWS
        self.canvas = tk.Canvas(mid, bg="white", highlightthickness=0, bd=0)
        self.body = tk.Frame(self.canvas, bg="white")
        self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all"), width=e.width,
            height=min(e.height, 31 * self.ROWS)))
        if many:
            sb = ttk.Scrollbar(mid, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        bar = tk.Frame(win, bg="#F3F4F6")
        bar.pack(fill="x", pady=(10, 0))

        def btn(text, cmd, primary=False):
            b = tk.Button(bar, text=text, command=cmd, font=("Segoe UI", 9, "bold" if primary else "normal"),
                          bg="#2563EB" if primary else "white", fg="white" if primary else "#1F2937",
                          activebackground="#1D4ED8" if primary else "#E5E7EB", relief="flat",
                          bd=0, padx=12, pady=5, cursor="hand2",
                          highlightthickness=1, highlightbackground="#D1D5DB")
            return b
        btn("Fit widths to text", self.fit).pack(side="left", padx=(10, 4), pady=8)
        btn("Reset to default", self.reset).pack(side="left", padx=4, pady=8)
        btn("✔  OK", self.ok, True).pack(side="right", padx=(4, 10), pady=8)
        btn("Cancel", self.cancel).pack(side="right", padx=4, pady=8)
        win.bind("<Escape>", lambda e: self.cancel())
        win.bind("<Return>", lambda e: self.ok())
        self._draw()
        try:
            win.update_idletasks()
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            x = min(t.winfo_rootx() + 40, sw - win.winfo_reqwidth() - 10)
            y = min(t.winfo_rooty() + 10, sh - win.winfo_reqheight() - 60)
            win.geometry("+%d+%d" % (max(0, x), max(0, y)))
        except Exception:
            pass
        try:
            win.grab_set()
        except Exception:
            pass
        win.focus_set()

    def _draw(self):
        for w in self.body.winfo_children():
            w.destroy()
        keep = _keep(self.t)
        tk.Label(self.body, text="Show   Column", font=("Segoe UI", 9, "bold"), bg="white",
                 fg="#374151").grid(row=0, column=0, sticky="w", padx=4)
        tk.Label(self.body, text="Width", font=("Segoe UI", 9, "bold"), bg="white",
                 fg="#374151").grid(row=0, column=1, sticky="w")
        for i, (c, v, w) in enumerate(self.rows):
            r = i + 1
            cb = tk.Checkbutton(self.body, text=_title(self.t, c), variable=v, bg="white",
                                anchor="w", font=("Segoe UI", 10), width=26,
                                activebackground="white", highlightthickness=0)
            if c in keep:
                cb.configure(state="disabled")
                v.set(True)
            cb.grid(row=r, column=0, sticky="w", padx=2, pady=1)
            tk.Spinbox(self.body, from_=MIN_W, to=MAX_W, increment=10, textvariable=w, width=6,
                       font=("Segoe UI", 10), justify="right").grid(row=r, column=1, padx=6)
            tk.Button(self.body, text="▲", width=2, relief="flat", bg="#EEF2F7", bd=0,
                      state="normal" if i > 0 else "disabled",
                      command=lambda i=i: self.move(i, -1)).grid(row=r, column=2, padx=1)
            tk.Button(self.body, text="▼", width=2, relief="flat", bg="#EEF2F7", bd=0,
                      state="normal" if i < len(self.rows) - 1 else "disabled",
                      command=lambda i=i: self.move(i, 1)).grid(row=r, column=3, padx=(1, 6))

    def move(self, i, d):
        j = i + d
        if 0 <= i < len(self.rows) and 0 <= j < len(self.rows):
            self.rows[i], self.rows[j] = self.rows[j], self.rows[i]
            self._draw()

    def fit(self):
        fw = fit_widths(self.t, [r[0] for r in self.rows])
        zf = _zf()
        for c, v, w in self.rows:
            if c in fw:
                w.set(str(int(round(fw[c] / zf))))

    def reset(self):
        reset(self.t)
        self._close()

    def ok(self):
        order = [c for c, v, w in self.rows if v.get()]
        if not order:
            order = [self.rows[0][0]]
        zf = _zf()
        for c, v, w in self.rows:
            try:
                px = max(MIN_W, min(MAX_W, int(float(w.get()))))
                _O["column"](self.t, c, width=int(round(px * zf)))
            except (TypeError, ValueError, tk.TclError):
                pass
        _set_dc(self.t, [c for c in order if c in self.base] or self.base[:1], self.base)
        remember(self.t)
        self._close()

    def cancel(self):
        self._close()

    def _close(self):
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        if getattr(self.t, "_ct_dialog", None) is self:
            self.t._ct_dialog = None


# ── the ☰ corner button (shows while the mouse is on the headings) ──
def _corner(t):
    b = getattr(t, "_ct_btn", None)
    try:
        if b is not None and b.winfo_exists():
            return b
    except Exception:
        pass
    try:
        st = ttk.Style(t)
        style = str(t.cget("style") or "") or "Treeview"
        bg = (st.lookup(style + ".Heading", "background") or
              st.lookup("Treeview.Heading", "background") or "#E5E7EB")
    except Exception:
        bg = "#E5E7EB"
    b = tk.Label(t, text=" ☰ ", font=("Segoe UI", 9, "bold"), bg=bg, fg="#2563EB",
                 cursor="hand2", bd=0, padx=1, pady=0)
    b.bind("<Button-1>", lambda e: menu(t, e.x_root, e.y_root))
    b.bind("<Button-3>", lambda e: menu(t, e.x_root, e.y_root))
    t._ct_btn = b
    return b


def _corner_show(t):
    try:
        b = _corner(t)
        b.place(relx=1.0, x=-2, y=2, anchor="ne")
        b.lift()
        aid = getattr(t, "_ct_hide_id", None)
        if aid:
            t.after_cancel(aid)
            t._ct_hide_id = None
    except Exception:
        pass


def _corner_hide(t, ms=700):
    b = getattr(t, "_ct_btn", None)
    if b is None:
        return

    def go():
        t._ct_hide_id = None
        try:
            x, y = t.winfo_pointerxy()
            w = t.winfo_containing(x, y)
            if w is b:
                return
            if w is t and t.identify_region(x - t.winfo_rootx(), y - t.winfo_rooty()) in \
                    ("heading", "separator"):
                return
            b.place_forget()
        except Exception:
            pass
    try:
        if getattr(t, "_ct_hide_id", None):
            return
        t._ct_hide_id = t.after(ms, go)
    except Exception:
        pass


# ── mouse handlers (bindtag in front of every table) ─────────
def _col_at(t, x):
    try:
        r = str(_O["identify"](t, "column", x, 0) or "")
        n = int(r[1:])
    except Exception:
        return None
    shown = shown_columns(t)
    return shown[n - 1] if 1 <= n <= len(shown) else None


def _on_b3(e):
    t = e.widget
    if _off(t):
        return
    try:
        reg = t.identify_region(e.x, e.y)
    except Exception:
        return
    if reg not in ("heading", "separator"):
        return
    menu(t, e.x_root, e.y_root, _col_at(t, e.x))
    return "break"


def _widths(t):
    try:
        return {c: int(_O["column"](t, c, "width")) for c in shown_columns(t)}
    except Exception:
        return {}


def _on_press(e):
    t = e.widget
    _DRAG.clear()
    if _off(t):
        return
    try:
        reg = t.identify_region(e.x, e.y)
    except Exception:
        return
    if reg == "separator":
        _DRAG.update(mode="resize", t=t, widths=_widths(t))
    elif reg == "heading":
        c = _col_at(t, e.x)
        if c:
            _DRAG.update(mode="heading", t=t, col=c, x=e.x, moving=False)


def _marker(t):
    m = getattr(t, "_ct_marker", None)
    try:
        if m is not None and m.winfo_exists():
            return m
    except Exception:
        pass
    m = tk.Frame(t, bg="#2563EB", width=3, bd=0)
    t._ct_marker = m
    return m


def _on_motion(e):
    t = e.widget
    if _off(t):
        return
    if _DRAG.get("t") is t and _DRAG.get("mode") == "heading":
        if not _DRAG["moving"] and abs(e.x - _DRAG["x"]) > 15:
            _DRAG["moving"] = True
            try:
                _DRAG["cursor"] = t.cget("cursor")
                t.configure(cursor="sb_h_double_arrow")
            except Exception:
                pass
        if _DRAG["moving"]:
            try:
                _marker(t).place(x=max(0, e.x - 1), y=0, width=3, relheight=1.0)
            except Exception:
                pass
        return
    try:
        reg = t.identify_region(e.x, e.y)
    except Exception:
        return
    if reg in ("heading", "separator"):
        _corner_show(t)
    elif getattr(t, "_ct_btn", None) is not None:
        _corner_hide(t)


def _on_leave(e):
    t = e.widget
    if not _off(t):
        _corner_hide(t)


def _on_release(e):
    t = e.widget
    d = dict(_DRAG)
    _DRAG.clear()
    if d.get("t") is not t or _off(t):
        return
    if d["mode"] == "resize":
        def done():
            if _widths(t) != d.get("widths"):      # a click without a drag saves nothing
                remember(t)
        t.after_idle(done)
    elif d["mode"] == "heading" and d.get("moving"):
        try:
            _marker(t).place_forget()
            t.configure(cursor=d.get("cursor", ""))
        except Exception:
            pass
        tgt = _col_at(t, e.x) if 0 <= e.x <= t.winfo_width() else None
        if tgt and tgt != d["col"]:
            move_to(t, d["col"], tgt)


def _on_double(e):
    t = e.widget
    if _off(t):
        return
    try:
        if t.identify_region(e.x, e.y) != "separator":
            return
    except Exception:
        return
    c = _col_at(t, e.x - 4)
    if c:
        fit(t, [c])
    return "break"


def _bind(t):
    try:
        app = t.tk
        if id(app) in _BOUND:
            return
        _BOUND.add(id(app))
        t.bind_class(TAG, "<Button-3>", _on_b3)
        t.bind_class(TAG, "<ButtonPress-1>", _on_press)
        t.bind_class(TAG, "<B1-Motion>", _on_motion)
        t.bind_class(TAG, "<Motion>", _on_motion)
        t.bind_class(TAG, "<Leave>", _on_leave)
        t.bind_class(TAG, "<ButtonRelease-1>", _on_release)
        t.bind_class(TAG, "<Double-Button-1>", _on_double)
    except Exception:
        pass


# ── who made the table (the layout key) ──────────────────────
def _creator():
    f = sys._getframe(2)
    while f is not None:
        mod = f.f_globals.get("__name__", "") or ""
        if not (mod.startswith("tkinter") or mod == __name__):
            code = f.f_code
            return "%s.%s" % (mod, getattr(code, "co_qualname", code.co_name))
        f = f.f_back
    return "?"


# ── the Treeview methods ─────────────────────────────────────
def _tr(t, col):
    """'#n' (the program's n-th column) → that column's id."""
    if not isinstance(col, str) or not col.startswith("#") or col == "#0" or _off(t):
        return col
    try:
        n = int(col[1:])
    except ValueError:
        return col
    base = _base(t)
    return base[n - 1] if 1 <= n <= len(base) else col


def _init(self, master=None, **kw):
    _O["__init__"](self, master, **kw)
    try:
        self._ct_from = _creator()
        dc = _as_list(self, kw.get("displaycolumns"))
        self._ct_base = "#all" if not dc or dc == ["#all"] else dc
        self._ct_code_w = {}
        self._ct_key = None
        self._ct_on = True
        try:                                 # drop-down lists on a field: no tool
            if self.winfo_toplevel().wm_overrideredirect():
                self._own_columns = True
        except Exception:
            pass
        _bind(self)
        self.bindtags((TAG,) + tuple(self.bindtags()))
        if _all_cols(self):
            _apply(self)
    except Exception:
        pass


def _configure(self, cnf=None, **kw):
    if isinstance(cnf, str) or (not cnf and not kw) or not getattr(self, "_ct_on", False) \
            or getattr(self, "_own_columns", False):
        return _O["configure"](self, cnf, **kw)
    opts = dict(cnf or {})
    opts.update(kw)
    if "columns" not in opts and "displaycolumns" not in opts:
        return _O["configure"](self, cnf, **kw)
    if "displaycolumns" in opts:
        dc = _as_list(self, opts["displaycolumns"])
        self._ct_base = "#all" if not dc or dc == ["#all"] else dc
    if "columns" in opts:
        # a user layout may hide columns the new list doesn't have → the
        # program's own display list goes with the new columns
        b = getattr(self, "_ct_base", "#all")
        opts["displaycolumns"] = "#all" if b == "#all" else list(b)
    r = _O["configure"](self, opts)
    _apply(self)
    return r


def _identify(self, component, x, y):
    r = _O["identify"](self, component, x, y)
    if component != "column" or not r or str(r) == "#0" or _off(self):
        return r
    try:
        shown, base = shown_columns(self), _base(self)
        if shown == base:
            return r
        c = shown[int(str(r)[1:]) - 1]
        return "#%d" % (base.index(c) + 1) if c in base else r
    except Exception:
        return r


def _bbox(self, item, column=None):
    return _O["bbox"](self, item, _tr(self, column) if column is not None else None)


def _column(self, column, option=None, **kw):
    if not getattr(self, "_ct_on", False) or getattr(self, "_own_columns", False):
        return _O["column"](self, column, option, **kw)
    column = _tr(self, column)
    if option is None and "width" in kw:
        try:
            cw = kw["width"]
            self._ct_code_w[str(column)] = cw
            lay = _layout(self)
            if lay and float(cw) > 0 and not _off(self):
                w = (lay.get("widths") or {}).get(str(column))
                if w:                       # the user's width wins
                    kw["width"] = max(MIN_W, int(round(float(w) * _zf())))
        except Exception:
            pass
    return _O["column"](self, column, option, **kw)


def _heading(self, column, option=None, **kw):
    return _O["heading"](self, _tr(self, column), option, **kw)


def _set(self, item, column=None, value=None):
    return _O["set"](self, item, _tr(self, column) if column is not None else None, value)


def install():
    if _O:
        return
    _O.update({"__init__": T.__init__, "configure": tk.Misc.configure,
               "identify": T.identify, "bbox": T.bbox, "column": T.column,
               "heading": T.heading, "set": T.set})
    T.__init__ = _init
    T.configure = _configure
    T.config = _configure
    T.identify = _identify
    T.bbox = _bbox
    T.column = _column
    T.heading = _heading
    T.set = _set


class ShownList(list):
    """Headers already cut to the columns on screen (not cut again)."""


def find_table(parent, headers, rows):
    """The table on screen these export rows were read from — only when its
    columns were hidden / moved by the user. None otherwise."""
    if parent is None or not rows or isinstance(headers, ShownList):
        return None
    want = [[str(x) for x in r] for r in list(rows)[:3]]
    n, stack, seen = len(headers), [parent], 0
    while stack and seen < 4000:
        w = stack.pop()
        seen += 1
        try:
            stack.extend(w.winfo_children())
        except Exception:
            continue
        if not isinstance(w, T) or _off(w):
            continue
        try:
            cols = _all_cols(w)
            if len(cols) != n or shown_columns(w) == cols:
                continue
            items = w.get_children("")
            if len(items) < len(want):
                continue
            got = [[str(x) for x in (w.item(i, "values") or ())] for i in items[:len(want)]]
            if got == want:
                return w
        except Exception:
            continue
    return None


def export_view(t, headers, rows, aligns=None):
    """Headers / rows (in the program's column order) → only the columns
    on screen, in the screen order. Unchanged when they don't line up."""
    try:
        cols = _all_cols(t)
        if not cols or len(headers) != len(cols) or getattr(t, "_own_columns", False):
            return headers, rows, aligns
        shown = shown_columns(t)
        if shown == cols:
            return headers, rows, aligns
        idx = [cols.index(c) for c in shown]
        h = ShownList(headers[i] for i in idx)
        r = [[(row[i] if i < len(row) else "") for i in idx] for row in rows]
        a = [aligns[i] for i in idx] if aligns and len(aligns) == len(cols) else aligns
        return h, r, a
    except Exception:
        return headers, rows, aligns


install()
