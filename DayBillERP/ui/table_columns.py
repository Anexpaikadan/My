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
#
# v6.9.4:
#   • tree._ct_optional = {...}  "More columns" — there but hidden until
#     the user ticks them (Profit, Profit %, Cost, PLU, Stock, Unit 1-3,
#     Multi barcode …); tree._ct_forbid = {...} never shown (no right)
#   • Font ▸ size, font design, bold — per table, or for every table
#   • product_columns(tree, ref="code", qty=…, net=…) gives any list of
#     products the extra product columns (modules/product_info.py); they
#     are filled in by themselves and go into Excel / PDF with the rest
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
FONT_FAMILIES = ["Segoe UI", "Tahoma", "Arial", "Calibri", "Verdana", "Cambria",
                 "Consolas", "Courier New", "Times New Roman"]
FONT_SIZES = [8, 9, 10, 11, 12, 13, 14, 16, 18]
_SEQ = [0]


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


def _optional(t):
    return set(getattr(t, "_ct_optional", ()) or ())


def _forbid(t):
    return set(getattr(t, "_ct_forbid", ()) or ())


def _prog(t):
    """The PROGRAM's own column positions ("#3" = its 3rd): its
    displaycolumns, then the optional "More columns"."""
    cols = _all_cols(t)
    b = getattr(t, "_ct_base", "#all")
    out = cols if (b == "#all" or not b) else (_norm(t, b, cols) or cols)
    return out + [c for c in cols if c in _optional(t) and c not in out]


def _base(t):
    """The columns the user may show: the program's, with the optional
    "More columns"; never the forbidden ones (no right)."""
    prog = _prog(t)
    no = _forbid(t)
    return [c for c in prog if c not in no] or prog[:1]


# ── v7.8: read-only columns ──────────────────────────────────
# A table lists the columns you may type in:  tree._ct_editable = {...}
# (item grid: Bar Code, Product, Qty, Rate). Each of them gets
# "🔒 Read only" in the right-click menu and the Columns… window: a
# locked column shows its value but cannot be typed in (e.g. the sales
# Rate always comes from the product). Kept per table on this PC, and
# kept when the columns are reset.
LOCK_EVENT = "<<ColumnsLocked>>"


def editable(t):
    return set(getattr(t, "_ct_editable", ()) or ())


def _locks():
    _tables()
    return _STORE["data"].setdefault("locks", {})


def _lock_key(t):
    return getattr(t, "_ct_lock_key", None) or getattr(t, "_ct_from", None) or _key(t)


def locked(t):
    """The columns of this table that are read only."""
    ed = editable(t)
    if not ed:
        return set()
    k = _lock_key(t)
    return (set(_locks().get(k) or []) & ed) if k else set()


def is_locked(t, c):
    return c in locked(t)


def set_locked(t, c, on=True):
    k = _lock_key(t)
    if not k or c not in editable(t):
        return False
    cur = set(_locks().get(k) or [])
    cur = (cur | {c}) if on else (cur - {c})
    if cur:
        _locks()[k] = sorted(cur)
    else:
        _locks().pop(k, None)
    _write()
    try:
        t.event_generate(LOCK_EVENT)
    except Exception:
        pass
    return True


def _default(t):
    """What shows before the user changes anything (no optional ones)."""
    base = _base(t)
    return [c for c in base if c not in _optional(t)] or base[:1]


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
    opt = _optional(t)
    cols = [c for c in _all_cols(t) if c not in opt]     # "More columns" don't change it
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
    opt = _optional(t)
    for i, c in enumerate(base):        # columns the saved layout doesn't know
        if c in hidden or c in seen or c in opt:     # a new "More column" stays off
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
    if eff == _all_cols(t) and getattr(t, "_ct_base", "#all") == "#all":
        val = "#all"
    else:
        val = list(eff)
    _O["configure"](t, None, displaycolumns=val)


def _fire(t):
    if getattr(t, "_ct_prod", None):
        _fill_soon(t)
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
    _set_dc(t, _effective(t, base, lay) if lay else _default(t), base)
    _apply_font(t)
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
    old = _tables().get(k) or {}
    _tables()[k] = {"order": shown, "hidden": [c for c in base if c not in shown],
                    "widths": widths}
    if old.get("font"):                     # the table's font stays
        _tables()[k]["font"] = old["font"]
    t._ct_key = k
    _write()
    _fire(t)


def reset(t):
    """Back to the program's own columns and widths (and font)."""
    k = _key(t)
    if k and k in _tables():
        _tables().pop(k, None)
        _write()
    base = _base(t)
    _set_dc(t, _default(t), base)
    _apply_font(t)
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


# ── font: size, design, bold (v6.9.4) ─────────────────────────
def font_of(t):
    """{"family", "size", "bold"} for this table: its own, else the one set
    for every table, else None (the program's font)."""
    lay = _layout(t) if getattr(t, "_ct_key", None) else None
    f = (lay or {}).get("font")
    if not f:
        _tables()
        f = (_STORE["data"] or {}).get("default_font")
    return f if isinstance(f, dict) and f else None


def _font_parts(t, font):
    try:
        a = tkfont.Font(t, font=font).actual()
        return a.get("family") or "Segoe UI", abs(int(a.get("size") or 9)) or 9, \
            a.get("weight") or "normal", a.get("slant") or "roman"
    except Exception:
        return "Segoe UI", 9, "normal", "roman"


def _base_font(t):
    st = ttk.Style(t)
    style = getattr(t, "_ct_style0", None) or str(t.cget("style") or "") or "Treeview"
    for n in (style, "Treeview"):
        try:
            f = st.lookup(n, "font")
        except Exception:
            f = ""
        if f:
            return _font_parts(t, f)
    return _font_parts(t, "TkDefaultFont")


def _scaled(t, font, spec, base_size):
    fam, size, weight, slant = _font_parts(t, font)
    if spec.get("family"):
        fam = spec["family"]
    if spec.get("size"):
        size = max(6, size + int(spec["size"]) - base_size)
    if spec.get("bold"):
        weight = "bold"
    return (fam, size, weight) + (("italic",) if slant == "italic" else ())


def _apply_font(t):
    """Put the table's font on it (its own ttk style, so other tables keep
    theirs); tag fonts (bold totals …) follow the new size."""
    try:
        if _off(t):
            return
        if getattr(t, "_ct_style0", None) is None:
            t._ct_style0 = str(t.cget("style") or "") or "Treeview"
        spec = font_of(t)
        base = t._ct_style0
        mine = getattr(t, "_ct_style", None)
        if not spec:
            if mine and str(t.cget("style")) == mine:
                _O["configure"](t, None, style=base)
                for tag, f in dict(getattr(t, "_ct_tagfonts", {}) or {}).items():
                    _O["tag_configure"](t, tag, font=f)
            return
        if not mine:
            _SEQ[0] += 1
            mine = t._ct_style = "DBF%d.%s" % (_SEQ[0], base if base.endswith("Treeview")
                                               else "Treeview")
        fam, bsize, bweight, _sl = _base_font(t)
        fam = spec.get("family") or fam
        size = int(spec.get("size") or bsize)
        weight = "bold" if spec.get("bold") else "normal"
        st = ttk.Style(t)
        f = tkfont.Font(t, family=fam, size=size, weight=weight)
        try:
            rh0 = int(st.lookup(base, "rowheight") or 0)
        except Exception:
            rh0 = 0
        rh = max(18, f.metrics("linespace") + (12 if rh0 >= 28 else 9))
        st.configure(mine, font=(fam, size, weight), rowheight=rh)
        st.configure(mine + ".Heading", font=(fam, size, "bold"))
        if str(t.cget("style")) != mine:
            _O["configure"](t, None, style=mine)
        for tag, tf in dict(getattr(t, "_ct_tagfonts", {}) or {}).items():
            _O["tag_configure"](t, tag, font=_scaled(t, tf, spec, bsize))
    except Exception:
        pass


def set_font(t, family=None, size=None, bold=None, everywhere=False, clear=False):
    """Change the font of this table (everywhere=True: of every table that
    has no font of its own). clear=True goes back to the program's font."""
    if _off(t):
        return False
    cur = dict(font_of(t) or {})
    if clear:
        cur = {}
    if family is not None:
        cur["family"] = family
    if size is not None:
        cur["size"] = int(size)
    if bold is not None:
        cur["bold"] = bool(bold)
    if everywhere:
        _tables()
        _STORE["data"]["default_font"] = cur or None
        lay = _layout(t)
        if lay is not None:
            lay.pop("font", None)
        _write()
        _refont_all(t)
        return True
    k = _key(t)
    if not k:
        return False
    if k not in _tables():
        remember(t)
    lay = _tables().get(k)
    if cur:
        lay["font"] = cur
    else:
        lay.pop("font", None)
    t._ct_key = k
    _write()
    _apply_font(t)
    _fire(t)
    return True


def _refont_all(t):
    """After 'for every table': every table on screen takes it."""
    try:
        stack = [t.winfo_toplevel()._root()]
    except Exception:
        stack = [t]
    seen = 0
    while stack and seen < 20000:
        w = stack.pop()
        seen += 1
        try:
            stack.extend(w.winfo_children())
        except Exception:
            continue
        if isinstance(w, T) and not _off(w):
            _apply_font(w)


def font_menu(t, master):
    m = tk.Menu(master, tearoff=0)
    cur = font_of(t) or {}
    fam0, size0, _w, _s = _base_font(t)
    size_now = int(cur.get("size") or size0)
    fam_now = cur.get("family") or fam0
    sm = tk.Menu(m, tearoff=0)
    for z in FONT_SIZES:
        sm.add_radiobutton(label="%d%s" % (z, "   (now)" if z == size_now else ""),
                           command=lambda z=z: set_font(t, size=z))
    m.add_cascade(label="Size  (%d)" % size_now, menu=sm)
    m.add_command(label="Bigger  A+", command=lambda: set_font(t, size=min(24, size_now + 1)))
    m.add_command(label="Smaller  A−", command=lambda: set_font(t, size=max(7, size_now - 1)))
    fm = tk.Menu(m, tearoff=0)
    for f in FONT_FAMILIES:
        fm.add_radiobutton(label=f + ("   (now)" if f == fam_now else ""),
                           command=lambda f=f: set_font(t, family=f))
    m.add_cascade(label="Design  (%s)" % fam_now, menu=fm)
    m.add_command(label=("✔ " if cur.get("bold") else "") + "Bold rows",
                  command=lambda: set_font(t, bold=not cur.get("bold")))
    m.add_separator()
    m.add_command(label="Use this font for every table",
                  command=lambda: set_font(t, everywhere=True, **{k: cur.get(k) for k in
                                                                  ("family", "size", "bold")}))
    m.add_command(label="Program font for this table", command=lambda: set_font(t, clear=True),
                  state="normal" if (_layout(t) or {}).get("font") else "disabled")
    return m


# ── extra product columns on any list (v6.9.4) ───────────────
def product_columns(t, ref, qty=None, net=None, unit=None, mode="sale", keys=None):
    """Offer Profit, Profit %, Cost, PLU, Stock, Unit 1-3, Multi barcode …
    on a table of products. ref / qty / net / unit: the column id holding
    the product code (or id / barcode), quantity, net amount (no VAT) and
    unit — or a function(row dict) → value. The new columns start hidden
    ("➕ More columns"); cost and profit only for users who may see cost."""
    try:
        from modules import product_info as PI
    except Exception:
        return False
    flds = [f for f in PI.fields() if keys is None or f[0] in keys]
    have = _all_cols(t)
    add = [f for f in flds if f[0] not in have]
    t._ct_prod = {"ref": ref, "qty": qty, "net": net, "unit": unit, "mode": mode,
                  "keys": [f[0] for f in flds]}
    t._ct_optional = _optional(t) | {f[0] for f in flds}
    if add:
        keep = {}
        for c in have:                       # changing the columns forgets headings
            try:
                h = _O["heading"](t, c)
                keep[c] = ({k: h.get(k) for k in ("text", "anchor") if h.get(k) not in (None, "")},
                           {k: _O["column"](t, c, k) for k in ("width", "minwidth", "stretch", "anchor")})
            except Exception:
                pass
        t.configure(columns=have + [f[0] for f in add])
        for c, (h, col) in keep.items():
            try:
                _O["heading"](t, c, **h)
                _O["column"](t, c, **col)
            except Exception:
                pass
        for key, label, kind, width, _s in add:
            _O["heading"](t, key, text=label, anchor="e" if kind != "text" else "w")
            _O["column"](t, key, width=int(round(width * _zf())), minwidth=40, stretch=False,
                         anchor="e" if kind != "text" else "w")
        _apply(t)
    _fill_soon(t)
    return True


def _fill_soon(t):
    if getattr(t, "_ct_fill_id", None):
        return
    try:
        t._ct_fill_id = t.after_idle(lambda: _fill(t))
    except Exception:
        t._ct_fill_id = None


def _pick(spec, row):
    if spec is None:
        return None
    if callable(spec):
        try:
            return spec(row)
        except Exception:
            return None
    return row.get(spec)


def _num(v):
    if v in (None, ""):
        return None
    try:
        s = str(v).replace(",", "").strip()
        neg = s.startswith("(") and s.endswith(")")
        x = float(s.strip("()").replace("SAR", "").strip())
        return -x if neg else x
    except Exception:
        return None


def _fill(t):
    """Write the shown product columns of every row (others stay empty)."""
    t._ct_fill_id = None
    p = getattr(t, "_ct_prod", None)
    if not p:
        return
    try:
        if not t.winfo_exists():
            return
        from modules import product_info as PI
        shown = [c for c in shown_columns(t) if c in p["keys"]]
        if not shown:
            return
        cols = _all_cols(t)
        for iid in _rows_of(t):
            vals = list(_O["item"](t, iid, "values") or ())
            row = {c: (vals[i] if i < len(vals) else "") for i, c in enumerate(cols)}
            ref = _pick(p["ref"], row)
            if ref in (None, ""):
                continue
            q, n = _num(_pick(p["qty"], row)), _num(_pick(p["net"], row))
            v = PI.values(ref, qty=q, net=n, unit=_pick(p["unit"], row), mode=p["mode"])
            for c in shown:
                _O["set"](t, iid, c, PI.text(c, v.get(c)))
    except Exception:
        pass


def _rows_of(t, parent=""):
    out = []
    for i in t.get_children(parent):
        out.append(i)
        out.extend(_rows_of(t, i))
    return out


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
        if c in editable(t):
            lv = tk.BooleanVar(master=t, value=is_locked(t, c))
            m._lock_var = lv
            m.add_checkbutton(label='🔒 "%s" read only (can\'t be typed in)' % name, variable=lv,
                              command=lambda: set_locked(t, c, bool(lv.get())))
        m.add_separator()
    m._vars = []
    opt = _optional(t)

    def checks(menu_, cols):
        for col in cols:
            v = tk.BooleanVar(master=t, value=col in shown)
            m._vars.append(v)
            menu_.add_checkbutton(label=_title(t, col), variable=v,
                                  command=lambda col=col, v=v: (show(t, col) if v.get() else hide(t, col),
                                                                v.set(col in shown_columns(t))),
                                  state="disabled" if col in _keep(t) else "normal")
    sub = tk.Menu(m, tearoff=0)
    checks(sub, [c for c in base if c not in opt])
    m.add_cascade(label="Show / hide columns", menu=sub)
    more = [c for c in base if c in opt]
    if more:
        sub2 = tk.Menu(m, tearoff=0)
        checks(sub2, more)
        m.add_cascade(label="➕ More columns  (profit, cost, PLU, stock, units …)", menu=sub2)
    m.add_command(label="Fit all columns to text", command=lambda: fit(t))
    m.add_command(label="Columns…   (show, order, width, font)", command=lambda: ColumnsDialog(t))
    m.add_cascade(label="Font  (size, design)", menu=font_menu(t, m))
    m.add_separator()
    m.add_command(label="Reset columns to default", command=lambda: reset(t),
                  state="normal" if _layout(t) or shown != _default(t) else "disabled")
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
        lk = locked(t)
        self.locks = {c: tk.BooleanVar(master=t, value=c in lk) for c in editable(t)}
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
        tk.Label(win, text="Tick = show.   ▲ ▼ = move.   Width in pixels.   "
                           "➕ = more columns (profit, cost, PLU, stock, units …).\n"
                           "🔒 Read only = shown, but can't be typed in (e.g. the Rate always comes "
                           "from the product).\nSaved for this table on this PC.",
                 font=("Segoe UI", 9), bg="white", fg="#6B7280", justify="left"
                 ).pack(anchor="w", padx=14, pady=(2, 8))
        # font of this table: design · size · bold (v6.9.4)
        fb = tk.Frame(win, bg="white")
        fb.pack(fill="x", padx=14, pady=(0, 6))
        cur = font_of(t) or {}
        fam0, size0, _w, _s = _base_font(t)
        self.fam_var = tk.StringVar(master=t, value=cur.get("family") or fam0)
        self.size_var = tk.StringVar(master=t, value=str(cur.get("size") or size0))
        self.bold_var = tk.BooleanVar(master=t, value=bool(cur.get("bold")))
        self.all_var = tk.BooleanVar(master=t, value=False)
        self._font0 = (self.fam_var.get(), self.size_var.get(), self.bold_var.get())
        tk.Label(fb, text="Font", font=("Segoe UI", 9, "bold"), bg="white",
                 fg="#374151").pack(side="left")
        ttk.Combobox(fb, textvariable=self.fam_var, values=FONT_FAMILIES, width=16,
                     state="readonly").pack(side="left", padx=(6, 4))
        tk.Spinbox(fb, from_=7, to=24, textvariable=self.size_var, width=4,
                   font=("Segoe UI", 10), justify="right").pack(side="left", padx=4)
        tk.Checkbutton(fb, text="Bold", variable=self.bold_var, bg="white",
                       activebackground="white", highlightthickness=0).pack(side="left", padx=4)
        tk.Checkbutton(fb, text="for every table", variable=self.all_var, bg="white",
                       activebackground="white", highlightthickness=0).pack(side="left", padx=4)
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
        if self.locks:
            tk.Label(self.body, text="🔒 Read only", font=("Segoe UI", 9, "bold"), bg="white",
                     fg="#374151").grid(row=0, column=4, sticky="w", padx=(4, 6))
        opt = _optional(self.t)
        for i, (c, v, w) in enumerate(self.rows):
            r = i + 1
            cb = tk.Checkbutton(self.body, text=("➕ " if c in opt else "") + _title(self.t, c),
                                variable=v, bg="white",
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
            if c in self.locks:
                tk.Checkbutton(self.body, variable=self.locks[c], bg="white", activebackground="white",
                               highlightthickness=0, cursor="hand2").grid(row=r, column=4, padx=(4, 6))

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
        for c, v in self.locks.items():
            if bool(v.get()) != is_locked(self.t, c):
                set_locked(self.t, c, bool(v.get()))
        try:
            f = (self.fam_var.get(), self.size_var.get(), self.bold_var.get())
            if f != self._font0 or self.all_var.get():
                set_font(self.t, family=f[0], size=int(float(f[1])), bold=bool(f[2]),
                         everywhere=bool(self.all_var.get()))
        except Exception:
            pass
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
    base = _prog(t)
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
    if "style" in opts and str(opts["style"]) != str(getattr(self, "_ct_style", "") or ""):
        self._ct_style0 = str(opts["style"] or "") or "Treeview"     # the program's own style
        if getattr(self, "_ct_key", None) and font_of(self):        # keep the user's font
            self._ct_style = None                                   # (made again on the new style)
            opts.pop("style")
            r = _O["configure"](self, opts) if opts else None
            _apply_font(self)
            return r
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
        shown, base = shown_columns(self), _prog(self)
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


def _tag_configure(self, tagname, option=None, **kw):
    if "font" in kw and getattr(self, "_ct_on", False):
        try:
            tf = getattr(self, "_ct_tagfonts", None)
            if tf is None:
                tf = self._ct_tagfonts = {}
            tf[tagname] = kw["font"]
            spec = font_of(self) if getattr(self, "_ct_key", None) else None
            if spec:
                kw["font"] = _scaled(self, kw["font"], spec, _base_font(self)[1])
        except Exception:
            pass
    return _O["tag_configure"](self, tagname, option, **kw)


def _insert(self, parent, index, iid=None, **kw):
    r = _O["insert"](self, parent, index, iid, **kw)
    if getattr(self, "_ct_prod", None):
        _fill_soon(self)
    return r


def _item(self, item, option=None, **kw):
    r = _O["item"](self, item, option, **kw)
    if "values" in kw and getattr(self, "_ct_prod", None):
        _fill_soon(self)
    return r


def install():
    if _O:
        return
    _O.update({"__init__": T.__init__, "configure": tk.Misc.configure,
               "identify": T.identify, "bbox": T.bbox, "column": T.column,
               "heading": T.heading, "set": T.set, "tag_configure": T.tag_configure,
               "insert": T.insert, "item": T.item})
    T.__init__ = _init
    T.configure = _configure
    T.config = _configure
    T.identify = _identify
    T.bbox = _bbox
    T.column = _column
    T.heading = _heading
    T.set = _set
    T.tag_configure = _tag_configure
    T.insert = _insert
    T.item = _item


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
            n_extra = len([c for c in cols if c in _optional(w) and c in
                           ((getattr(w, "_ct_prod", None) or {}).get("keys") or ())])
            if len(cols) - n_extra != n or (not n_extra and shown_columns(w) == cols):
                continue
            items = w.get_children("")
            if len(items) < len(want):
                continue
            got = [[str(x) for x in (w.item(i, "values") or ())][:len(want[k])]
                   for k, i in enumerate(items[:len(want)])]
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
        if not cols or getattr(t, "_own_columns", False):
            return headers, rows, aligns
        extra = [c for c in cols if c in _optional(t) and c in
                 ((getattr(t, "_ct_prod", None) or {}).get("keys") or ())]
        headers = list(headers)
        rows = [list(r) for r in rows]
        if extra and len(headers) == len(cols) - len(extra) and cols[-len(extra):] == extra:
            # product columns added by the tool: their titles, and their values
            # read from the rows on screen (same order as the export rows)
            headers += [_title(t, c) for c in extra]
            items = _rows_of(t)
            got = [list(_O["item"](t, i, "values") or ()) for i in items] \
                if len(items) == len(rows) else []
            n0 = len(cols) - len(extra)
            for k, r in enumerate(rows):
                r += [""] * (n0 - len(r)) if len(r) < n0 else []
                del r[n0:]
                src = got[k] if got else []
                r += [(src[n0 + j] if n0 + j < len(src) else "") for j in range(len(extra))]
            if aligns and len(aligns) == n0:
                aligns = list(aligns) + ["e" if c in ("x_profit", "x_profit_pct", "x_cost",
                                                      "x_last_cost", "x_price", "x_stock",
                                                      "x_stock_value", "x_reorder", "x_vat")
                                         else "w" for c in extra]
        if len(headers) != len(cols):
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
