# ============================================================
# DayBill ERP - Textiles & Garments screens (v7.0)
# ------------------------------------------------------------
#   VariantsView      Textiles ▸ Size & Colour Variants: pick or make a
#                     style, tick sizes and colours, Create → one product
#                     per size × colour (own code + 5-digit barcode, stock
#                     0), change prices, print labels for all of them
#   VariantStockView  Textiles ▸ Stock by Size & Colour: colours (rows) ×
#                     sizes (columns) of stock with totals and value,
#                     Excel / CSV
#   MatrixEntry       the size × colour grid of Sales / Purchase / POS
#                     (Ctrl+G): type how many of each → one line per
#                     size / colour on the bill
#   attach_matrix(win, grid, parent)   button + Ctrl+G on a Sales /
#                                      Purchase window (textiles shops)
#   attach_pos(pos)                    the same in the POS
#   product_form_hook(form)            Metre / Yard units; a NEW product's
#                                      base unit follows the unit picked
# Keys (grid): arrows move · Enter next box · Ctrl+Enter / F9 add ·
#              Esc close
# ============================================================

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config import settings as cfg
from modules import textiles as TX


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _money(v, sym=False):
    try:
        from modules import country
        return country.money(v, sym=sym)
    except Exception:
        return "{:,.2f}".format(_f(v))


def _qty(v):
    v = round(_f(v), 3)
    return "%g" % v


def _number(text):
    """Quantity / price typed in a box: '2.75', '2,75', Arabic digits."""
    from ui.invoice_grid import _loose_number
    s = str(text or "").strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return _loose_number(s)


def _center(win, w, h):
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 3)))
    except Exception:
        pass


def _style_label(r):
    return "%s — %s" % (r.get("product_code") or "", r.get("product_name_en") or "")


def find_style(text):
    """A style from what was typed or scanned: its code / name, or the code
    / barcode of one of its sizes. Returns a product_id or None."""
    text = str(text or "").strip()
    if not text:
        return None
    code = text.split(" — ")[0].strip()
    for r in TX.styles():
        if str(r.get("product_code") or "").lower() == code.lower():
            return int(r["product_id"])
    try:
        from modules.barcode_resolver import resolve
        hit = resolve(text, scale=False)
        if hit:
            return TX.style_of(hit["product_id"])
    except Exception:
        pass
    rows = TX.styles(search=text)
    return int(rows[0]["product_id"]) if len(rows) == 1 else None


# ════════════════════════════════════════════════════════════
#  size × colour grid (Sales / Purchase / POS)
# ════════════════════════════════════════════════════════════
class MatrixEntry:
    """Type quantities per size and colour of one style; Add gives
    on_add([(product_id, qty)])."""

    def __init__(self, parent, on_add, doc="sales", style_id=None):
        self.C = C = cfg.theme()
        self.on_add, self.doc = on_add, doc
        self.style_id = None
        self.boxes = {}                     # (size, colour) → (StringVar, Entry, row)
        w = self.win = tk.Toplevel(parent)
        w.title("Sizes & Colours")
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass
        _center(w, 900, 540)
        w.minsize(640, 400)
        band = tk.Frame(w, bg=C["primary"])
        band.pack(fill="x")
        tk.Label(band, text="🧵  Sizes & Colours — type how many of each, then Add",
                 font=("Segoe UI", 11, "bold"), bg=C["primary"], fg="white").pack(
                     side="left", padx=12, pady=6)

        top = tk.Frame(w, bg=C["card_bg"])
        top.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(top, text="Style (name, code or scan a barcode)", font=("Segoe UI", 8, "bold"),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
        row = tk.Frame(top, bg=C["card_bg"])
        row.pack(fill="x", padx=8, pady=(2, 8))
        self._styles = TX.styles()
        self.style_var = tk.StringVar()
        self.style_cb = ttk.Combobox(row, textvariable=self.style_var, width=48,
                                     values=[_style_label(r) for r in self._styles],
                                     font=("Segoe UI", 10))
        self.style_cb.pack(side="left", ipady=2)
        self.style_cb.bind("<<ComboboxSelected>>", lambda e: self._pick())
        self.style_cb.bind("<Return>", lambda e: (self._pick(), "break")[1])
        self.style_cb.bind("<KeyRelease>", self._filter)
        self.info_var = tk.StringVar()
        tk.Label(row, textvariable=self.info_var, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=12)

        foot = tk.Frame(w, bg=C["content_bg"])
        foot.pack(fill="x", side="bottom", padx=10, pady=8)
        self.total_var = tk.StringVar(value="")
        tk.Label(foot, textvariable=self.total_var, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="left")
        tk.Button(foot, text="Close  Esc", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=w.destroy).pack(side="right", padx=(6, 0))
        tk.Button(foot, text="Clear", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=self._clear).pack(side="right", padx=(6, 0))
        tk.Button(foot, text="✔  Add to bill   Ctrl+Enter", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=5,
                  cursor="hand2", command=self.add).pack(side="right")

        wrap = tk.Frame(w, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 2))
        self.canvas = tk.Canvas(wrap, bg=C["card_bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=C["card_bg"])
        self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        w.bind("<Escape>", lambda e: w.destroy())
        w.bind("<Control-Return>", lambda e: (self.add(), "break")[1])
        w.bind("<Control-KP_Enter>", lambda e: (self.add(), "break")[1])
        w.bind("<F9>", lambda e: (self.add(), "break")[1])
        if not self._styles:
            self._message("No styles with sizes or colours yet.\n\n"
                          "Make them in Textiles ▸ Size & Colour Variants.")
        if style_id:
            self.load(style_id)
        else:
            self.style_cb.focus_set()

    # ── style ─────────────────────────────────────────────────
    def _filter(self, e=None):
        if e is not None and e.keysym in ("Return", "KP_Enter", "Up", "Down", "Escape", "Tab"):
            return
        q = self.style_var.get().strip().lower()
        vals = [_style_label(r) for r in self._styles
                if not q or q in _style_label(r).lower()
                or q in str(r.get("product_name_ar") or "").lower()]
        self.style_cb.configure(values=vals)

    def _pick(self):
        sid = find_style(self.style_var.get())
        if not sid:
            self.info_var.set("Style not found — type part of the name and pick it from the list.")
            self.win.bell()
            return
        self.load(sid)

    def _message(self, text):
        for wd in self.body.winfo_children():
            wd.destroy()
        tk.Label(self.body, text=text, font=("Segoe UI", 10), bg=self.C["card_bg"],
                 fg=self.C["text_secondary"], justify="left").grid(row=0, column=0, padx=20, pady=20)

    def load(self, style_id):
        C = self.C
        self.style_id = int(style_id)
        m = TX.matrix(self.style_id)
        style = next((r for r in TX.styles() if int(r["product_id"]) == self.style_id), None)
        if style:
            self.style_var.set(_style_label(style))
        self.boxes = {}
        for wd in self.body.winfo_children():
            wd.destroy()
        if not m["cells"]:
            self._message("This style has no sizes or colours yet.")
            return
        sizes_, colours_ = m["sizes"], m["colours"]
        F = ("Segoe UI", 9, "bold")
        tk.Label(self.body, text="Colour  \\  Size", font=F, bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")
        for ci, s in enumerate(sizes_, 1):
            tk.Label(self.body, text=s or "—", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                     fg=C["primary"]).grid(row=0, column=ci, padx=4, pady=(8, 2))
        tk.Label(self.body, text="Total", font=F, bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=0, column=len(sizes_) + 1, padx=8, pady=(8, 2))
        self._row_tot, self._col_tot = {}, {}
        show_stock = cfg.flag("show_stock_during_sales", True) or self.doc not in ("sales", "pos")
        for ri, c in enumerate(colours_, 1):
            tk.Label(self.body, text=c or "—", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                     fg=C["text_primary"]).grid(row=ri, column=0, padx=8, pady=3, sticky="w")
            for ci, s in enumerate(sizes_, 1):
                v = m["cells"].get((s, c))
                cell = tk.Frame(self.body, bg=C["card_bg"])
                cell.grid(row=ri, column=ci, padx=4, pady=3)
                if v is None:
                    tk.Label(cell, text="—", width=7, font=("Segoe UI", 10), bg=C["card_bg"],
                             fg=C["border"]).pack()
                    continue
                var = tk.StringVar()
                e = tk.Entry(cell, textvariable=var, width=7, font=("Segoe UI", 11),
                             justify="center", relief="solid", bd=1)
                e.pack(ipady=2)
                if show_stock:
                    tk.Label(cell, text="stock %s" % _qty(v["stock"]), font=("Segoe UI", 7),
                             bg=C["card_bg"], fg=C["danger"] if v["stock"] <= 0
                             else C["text_secondary"]).pack()
                self.boxes[(s, c)] = (var, e, v)
                var.trace_add("write", lambda *_a: self._totals())
                for key, d in (("Up", (-1, 0)), ("Down", (1, 0)), ("Left", (0, -1)),
                               ("Right", (0, 1))):
                    e.bind("<%s>" % key, lambda ev, k=(s, c), d=d: self._move(k, d))
                e.bind("<Return>", lambda ev, k=(s, c): self._move(k, (0, 1), wrap=True))
                e.bind("<KP_Enter>", lambda ev, k=(s, c): self._move(k, (0, 1), wrap=True))
            lt = tk.Label(self.body, text="", font=F, bg=C["card_bg"], fg=C["primary"])
            lt.grid(row=ri, column=len(sizes_) + 1, padx=8)
            self._row_tot[c] = lt
        tr = len(colours_) + 1
        tk.Label(self.body, text="Total", font=F, bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=tr, column=0, padx=8, pady=(4, 8), sticky="w")
        for ci, s in enumerate(sizes_, 1):
            lt = tk.Label(self.body, text="", font=F, bg=C["card_bg"], fg=C["primary"])
            lt.grid(row=tr, column=ci, pady=(4, 8))
            self._col_tot[s] = lt
        self._grand = tk.Label(self.body, text="", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                               fg=C["primary"])
        self._grand.grid(row=tr, column=len(sizes_) + 1, padx=8, pady=(4, 8))
        self._order = [(s, c) for c in colours_ for s in sizes_ if (s, c) in self.boxes]
        self._sizes, self._colours = sizes_, colours_
        prices = sorted({_f(v[2].get("unit_price")) for v in self.boxes.values()})
        ptxt = (_money(prices[0]) if len(prices) == 1 else
                "%s – %s" % (_money(prices[0]), _money(prices[-1]))) if prices else ""
        self.info_var.set("%d sizes / colours · price %s" % (len(self.boxes), ptxt))
        self._totals()
        if self._order:
            first = self.boxes[self._order[0]][1]
            self.win.after(30, lambda: (first.focus_set(), first.select_range(0, "end")))

    def _move(self, key, d, wrap=False):
        if wrap:
            i = self._order.index(key) if key in self._order else -1
            if i + 1 < len(self._order):
                nxt = self.boxes[self._order[i + 1]][1]
                nxt.focus_set(); nxt.select_range(0, "end")
            return "break"
        s, c = key
        si, ci = self._sizes.index(s), self._colours.index(c)
        while True:
            ci, si = ci + d[0], si + d[1]
            if not (0 <= si < len(self._sizes) and 0 <= ci < len(self._colours)):
                return "break"
            k = (self._sizes[si], self._colours[ci])
            if k in self.boxes:
                e = self.boxes[k][1]
                e.focus_set(); e.select_range(0, "end")
                return "break"

    def _totals(self):
        rows, cols, tot, n = {}, {}, 0.0, 0
        for (s, c), (var, _e, _v) in self.boxes.items():
            q = _number(var.get())
            if q:
                rows[c] = rows.get(c, 0.0) + q
                cols[s] = cols.get(s, 0.0) + q
                tot += q
                n += 1
        for c, lbl in getattr(self, "_row_tot", {}).items():
            lbl.configure(text=_qty(rows[c]) if c in rows else "")
        for s, lbl in getattr(self, "_col_tot", {}).items():
            lbl.configure(text=_qty(cols[s]) if s in cols else "")
        if getattr(self, "_grand", None) is not None:
            self._grand.configure(text=_qty(tot) if tot else "")
        self.total_var.set(("Total %s  ·  %d line%s" % (_qty(tot), n, "" if n == 1 else "s"))
                           if n else "")

    def _clear(self):
        for var, _e, _v in self.boxes.values():
            var.set("")

    def items(self):
        """[(product_id, qty)] typed, in grid order. Raises ValueError for a
        wrong number."""
        out = []
        for key in getattr(self, "_order", []):
            var, _e, v = self.boxes[key]
            txt = var.get().strip()
            if not txt:
                continue
            q = _number(txt)
            if q < 0 or (q == 0 and txt not in ("0", "0.0", "0.00")):
                raise ValueError("%s: type a number (e.g. 2 or 2.75)." % v["product_name_en"])
            if q > 0:
                out.append((int(v["product_id"]), round(q, 3)))
        return out

    def add(self):
        try:
            items = self.items()
        except ValueError as e:
            messagebox.showwarning("Sizes & Colours", str(e), parent=self.win)
            return False
        if not items:
            messagebox.showinfo("Sizes & Colours", "Type a quantity in at least one box.",
                                parent=self.win)
            return False
        try:
            self.on_add(items)
        except Exception as e:
            messagebox.showerror("Sizes & Colours", str(e)[:300], parent=self.win)
            return False
        self.win.destroy()
        return True


def _grid_rows(pids, cost_price=False, sales_list=True):
    """Product rows the entry grids use (same columns as the windows)."""
    from config.database import db
    from modules.barcode_gen import sys_select
    q = ",".join("?" * len(pids))
    price = "ISNULL(p.purchase_price,0)" if cost_price else "p.unit_price"
    return db.fetchall(
        "SELECT p.product_id, p.product_code, p.product_name_en, p.product_name_ar, "
        "%s AS unit_price, p.unit_of_measure_en, p.unit_of_measure_ar, p.vat_category_id, "
        "ISNULL(p.alias_name,'') AS alias_name, ISNULL(p.purchase_price,0) AS purchase_price, "
        "ISNULL(p.stock_quantity,0) AS stock_quantity, ISNULL(p.reorder_level,0) AS reorder_level, "
        "ISNULL(p.barcode,'') AS barcode, %s, ISNULL(pc.category_name_en,'Other') AS category_name, "
        "ISNULL(vc.category_code,'S') AS vat_code, ISNULL(vc.vat_rate,15) AS vat_rate "
        "FROM products p LEFT JOIN vat_categories vc ON p.vat_category_id=vc.vat_category_id "
        "LEFT JOIN product_categories pc ON p.category_id=pc.category_id "
        "WHERE p.is_active=1 AND p.product_id IN (%s)" % (price, sys_select("p"), q),
        tuple(int(x) for x in pids)) or []


def add_to_grid(grid, items):
    """Quantities from the size grid → lines of an InvoiceGrid. Sizes made
    after the window opened are read first."""
    from config.database import db
    have = {p.get("product_id") for p in grid.products}
    missing = sorted({pid for pid, _q in items if pid not in have})
    if missing:
        purchase = getattr(grid, "doc_type", "sales") in ("purchase", "purchase_return")
        grid.products.extend(_grid_rows(missing, cost_price=purchase))
        q = ",".join("?" * len(missing))
        sql = ("SELECT * FROM product_units WHERE is_active=1 AND product_id IN (%s)" % q +
               ("" if purchase else " AND is_sales_unit=1") + " ORDER BY is_default DESC, unit_id")
        for u in db.fetchall(sql, tuple(missing)) or []:
            grid.product_units.setdefault(u["product_id"], []).append(u)
    return grid.add_product_lines(items)


def attach_matrix(win, grid, parent=None, side="right"):
    """Sales / Purchase window (textiles shops only): a '🧵 Sizes' button in
    `parent` and Ctrl+G open the size × colour grid; its quantities become
    lines of `grid` (an InvoiceGrid, or a function that returns it)."""
    if not TX.on():
        return None
    get = grid if not hasattr(grid, "add_product_lines") else (lambda: grid)
    C = cfg.theme()

    def open_grid(_e=None):
        g = get()
        if g is None or not hasattr(g, "add_product_lines"):
            return "break"
        MatrixEntry(win, lambda items: add_to_grid(g, items),
                    doc="purchase" if getattr(g, "doc_type", "") == "purchase" else "sales")
        return "break"

    btn = None
    if parent is not None:
        btn = tk.Button(parent, text="🧵 Sizes / Colours  Ctrl+G", font=("Segoe UI", 8, "bold"),
                        bg=C.get("primary_light", C["card_bg"]), fg=C["primary"], relief="flat",
                        padx=8, pady=2, cursor="hand2", command=open_grid)
        btn.pack(side=side, padx=(0, 8))
    win.bind("<Control-g>", open_grid)
    win.bind("<Control-G>", open_grid)
    win._textile_grid = open_grid
    return btn


def add_to_pos(pos, items):
    """Quantities from the size grid → lines of the POS bill."""
    from config.database import db
    if getattr(pos, "_minus", False):
        pos._set_minus(False)
    have = {p.get("product_id") for p in pos.products}
    missing = sorted({pid for pid, _q in items if pid not in have})
    if missing:
        pos.products.extend(_grid_rows(missing))
        q = ",".join("?" * len(missing))
        for u in db.fetchall(
                "SELECT unit_id, product_id, unit_name_en, conversion_factor, selling_price, "
                "ISNULL(purchase_price,0) AS purchase_price, is_default, barcode FROM product_units "
                "WHERE is_active=1 AND product_id IN (%s) ORDER BY conversion_factor" % q,
                tuple(missing)) or []:
            pos._units.setdefault(u["product_id"], []).append(u)
    last, n = None, 0
    for pid, qty in items:
        p = next((x for x in pos.products if x.get("product_id") == pid), None)
        if p is None or qty <= 0:
            continue
        units = pos._units_for(pid)
        uname = (next((u for u in units if u.get("is_default")), units[0])["unit_name_en"]
                 if units else "Unit")
        pos._add_to_cart(p)
        ln = next((l for l in pos.cart if l["product_id"] == pid and l["unit_name"] == uname
                   and l["quantity"] > 0), None)
        if ln is None:
            continue
        ln["quantity"] = round(ln["quantity"] - 1 + qty, 3)
        pos._recalc(ln)
        last, n = ln, n + 1
    pos._render_cart(select_line=last)
    return n


def attach_pos(pos):
    """POS (textiles shops only): '🧵 Sizes' on the +/− strip and Ctrl+G."""
    if not TX.on():
        return None

    def open_grid(_e=None):
        MatrixEntry(pos.win, lambda items: add_to_pos(pos, items), doc="pos")
        return "break"

    btn = None
    strip = getattr(getattr(pos, "minus_btn", None), "master", None)
    if strip is not None:
        btn = tk.Button(strip, text="🧵 Sizes", font=("Segoe UI", 11, "bold"), bg="#16A085",
                        fg="white", relief="flat", padx=10, cursor="hand2", command=open_grid)
        btn.pack(side="left", padx=4)
    pos.win.bind("<Control-g>", open_grid)
    pos.win.bind("<Control-G>", open_grid)
    pos._textile_grid = open_grid
    return btn


# ── product form: cloth sold by the metre ─────────────────────
def follow_unit(form):
    """A NEW product with one unit row (base, factor 1): the unit picked in
    Unit (EN) becomes that row's name — pick Metre and the cloth is sold
    and stocked by the metre (2.75 m)."""
    if getattr(form, "product_id", None) or getattr(form, "_loaded_as_edit", False):
        return
    pick = form.def_sales_unit.get().strip()
    if not pick or pick == getattr(form, "_ADD_NEW", None):
        return
    rows = [r for r in getattr(form, "unit_rows", []) or [] if r["name"].get().strip()]
    if len(rows) != 1:
        return
    r = rows[0]
    try:
        if abs(float(r["qty"].get() or 1) - 1) > 1e-9:
            return
    except (TypeError, ValueError):
        return
    old = r["name"].get().strip()
    if old != pick:
        r["name"].set(pick)
        if form.def_purch_unit.get().strip() in ("", old):
            form.def_purch_unit.set(pick)


def product_form_hook(form):
    """Product form (textiles shops only): Metre and Yard in the unit lists,
    and a new product's base unit follows the unit picked."""
    if not TX.on():
        return
    try:
        form._unit_choices[:] = TX.unit_choices(form._unit_choices)
    except Exception:
        pass
    var = getattr(form, "def_sales_unit", None)
    if var is not None:
        var.trace_add("write", lambda *_a: follow_unit(form))


# ════════════════════════════════════════════════════════════
#  Textiles ▸ Size & Colour Variants
# ════════════════════════════════════════════════════════════
def _not_ready(frame, C):
    tk.Label(frame, text="The Textiles update is not in this database yet.\n\n"
                         "Close DayBill and open it again (updates run when it starts), "
                         "or ask your administrator to update the database.",
             font=("Segoe UI", 11), bg=C["content_bg"], fg=C["danger"],
             justify="left").pack(anchor="w", padx=24, pady=24)


class VariantsView:
    def __init__(self, parent):
        from ui import v6_kit as K
        self.K = K
        self.page = K.Page(parent, "🧵  Size & Colour Variants",
                           "Make the sizes and colours of a style. Each one becomes its own product "
                           "with its own code and barcode (stock starts at 0). Sell and buy them "
                           "like any product — or use the Sizes grid (Ctrl+G) in Sales, Purchase "
                           "and POS.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.style = None
        self.plan = []
        self.size_vars, self.colour_vars = {}, {}
        if not TX.ready():
            _not_ready(self.page.body, C)
            return
        body = self.page.body

        # 1. style
        c1 = K.card(body, C, "1.  Style (the main product)", fill="x")
        r1 = tk.Frame(c1, bg=C["card_bg"])
        r1.pack(fill="x", padx=12, pady=(0, 8))
        self.finder = K.ProductFinder(r1, C, self._picked,
                                      label="Find the style: code, name or barcode, then Enter")
        self.finder.pack(side="left", padx=(0, 10))
        bb = tk.Frame(r1, bg=C["card_bg"])
        bb.pack(side="left", anchor="s", pady=(0, 2))
        K.button(bb, C, "＋  New style", self._new_style)
        K.button(bb, C, "✏  Open style", self._open_style)
        self.info_var = tk.StringVar(value="Pick a style first (e.g. Polo Shirt).")
        tk.Label(c1, textvariable=self.info_var, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"], anchor="w", justify="left").pack(fill="x", padx=12)
        self.hide_var = tk.BooleanVar(value=True)
        tk.Checkbutton(c1, text="Sell only the sizes / colours (hide the style itself from the "
                                "sales and purchase lists)", variable=self.hide_var,
                       font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                       activebackground=C["card_bg"], selectcolor=C["card_bg"]).pack(
                           anchor="w", padx=8, pady=(0, 8))

        mid = tk.Frame(body, bg=C["content_bg"])
        mid.pack(fill="x", pady=(8, 0))
        left = tk.Frame(mid, bg=C["content_bg"])
        left.pack(side="left", fill="y")
        self.size_card = K.card(left, C, "2.  Sizes", fill="x")
        self.size_box = tk.Frame(self.size_card, bg=C["card_bg"])
        self.size_box.pack(fill="x", padx=10)
        self._list_tools(self.size_card, "sizes")
        self.colour_card = K.card(left, C, "3.  Colours", fill="x", pady=(8, 0))
        self.colour_box = tk.Frame(self.colour_card, bg=C["card_bg"])
        self.colour_box.pack(fill="x", padx=10)
        self._list_tools(self.colour_card, "colours")

        right = K.card(mid, C, "4.  New sizes / colours to make  (double-click a price to change it)",
                       side="left", fill="both", expand=True, padx=(8, 0))
        self.prev = K.tree(right, [("size", "Size", 70, "center"), ("colour", "Colour", 90, "center"),
                                   ("name", "Product name", 260, "w"), ("price", "Price", 90, "e"),
                                   ("status", "Status", 150, "w")], height=7)
        self.prev.tag_configure("made", foreground="#9CA3AF")
        self.prev.bind("<Double-1>", self._edit_price)
        pr = tk.Frame(right, bg=C["card_bg"])
        pr.pack(fill="x", padx=10, pady=(0, 8))
        self.all_price_var = tk.StringVar()
        tk.Label(pr, text="Price for all new:", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        e = tk.Entry(pr, textvariable=self.all_price_var, width=10, font=("Segoe UI", 10),
                     relief="solid", bd=1, justify="right")
        e.pack(side="left", padx=4, ipady=2)
        e.bind("<Return>", lambda ev: self._price_all())
        K.button(pr, C, "Set", self._price_all)
        self.create_btn = K.button(pr, C, "✔  Create", self._create, primary=True, side="right")

        # existing variants
        c3 = K.card(body, C, "Sizes and colours of this style", fill="both", expand=True, pady=(8, 0))
        self.tree = K.tree(c3, [("code", "Code", 80, "w"), ("name", "Product", 250, "w"),
                                ("size", "Size", 60, "center"), ("colour", "Colour", 80, "center"),
                                ("barcode", "Barcode", 110, "center"), ("price", "Price", 85, "e"),
                                ("stock", "Stock", 70, "e"), ("value", "Stock value", 100, "e"),
                                ("active", "Active", 60, "center")], height=6)
        self.tree.configure(selectmode="extended")
        self.tree.bind("<Double-1>", lambda e: self._open_variant())
        self.tree.tag_configure("off", foreground="#9CA3AF")
        b3 = tk.Frame(c3, bg=C["card_bg"])
        b3.pack(fill="x", padx=10, pady=(0, 8))
        K.button(b3, C, "💲  Change price…", self._change_price)
        K.button(b3, C, "🏷  Print labels for all", self._labels)
        K.button(b3, C, "✏  Open product", self._open_variant)
        K.button(b3, C, "📊  Stock matrix", self._stock_matrix)
        self.sum_var = tk.StringVar()
        tk.Label(b3, textvariable=self.sum_var, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="right")
        self._build_ticks()
        self.frame.new_record = self._new_style        # Ctrl+N
        self.finder.entry.focus_set()

    # ── size / colour lists ───────────────────────────────────
    def _list_tools(self, card, kind):
        C = self.C
        row = tk.Frame(card, bg=C["card_bg"])
        row.pack(fill="x", padx=10, pady=(4, 8))
        var = tk.StringVar()
        e = tk.Entry(row, textvariable=var, width=12, font=("Segoe UI", 9), relief="solid", bd=1)
        e.pack(side="left", ipady=1)
        e.bind("<Return>", lambda ev: self._add_one(kind, var))
        for txt, cmd in (("＋ Add", lambda: self._add_one(kind, var)),
                         ("All", lambda: self._tick_all(kind, True)),
                         ("None", lambda: self._tick_all(kind, False)),
                         ("✏ Edit list", lambda: self._edit_list(kind))):
            tk.Button(row, text=txt, font=("Segoe UI", 8), bg=C["card_bg"], fg=C["primary"],
                      relief="flat", cursor="hand2", padx=6, command=cmd).pack(side="left", padx=(4, 0))

    def _names(self, kind):
        shop = TX.sizes() if kind == "sizes" else TX.colours()
        used = []
        for r in (TX.variants(self.style["product_id"], active_only=False) if self.style else []):
            v = r["size"] if kind == "sizes" else r["colour"]
            if v and v.lower() not in {x.lower() for x in shop + used}:
                used.append(v)
        allv = shop + used
        return TX.sort_sizes(allv) if kind == "sizes" else TX.sort_colours(allv)

    def _build_ticks(self, keep=True):
        C = self.C
        for kind, box, store in (("sizes", self.size_box, self.size_vars),
                                 ("colours", self.colour_box, self.colour_vars)):
            old = {k: v.get() for k, v in store.items()} if keep else {}
            for wd in box.winfo_children():
                wd.destroy()
            store.clear()
            for i, name in enumerate(self._names(kind)):
                v = tk.BooleanVar(value=old.get(name, False))
                store[name] = v
                tk.Checkbutton(box, text=name, variable=v, font=("Segoe UI", 9),
                               bg=C["card_bg"], activebackground=C["card_bg"],
                               selectcolor="white", command=self._preview).grid(
                                   row=i // 6, column=i % 6, sticky="w", padx=(0, 6))
        self._preview()

    def _ticked(self, kind):
        store = self.size_vars if kind == "sizes" else self.colour_vars
        return [k for k, v in store.items() if v.get()]

    def _tick_all(self, kind, on):
        for v in (self.size_vars if kind == "sizes" else self.colour_vars).values():
            v.set(on)
        self._preview()

    def _add_one(self, kind, var):
        new = TX.split_list(var.get())
        if not new:
            return
        cur = TX.sizes() if kind == "sizes" else TX.colours()
        try:
            TX.save_list(kind, cur + new)
        except ValueError as e:
            self.page.say(str(e), ok=False)
            return
        var.set("")
        self._build_ticks()
        store = self.size_vars if kind == "sizes" else self.colour_vars
        for n in new:
            for k, v in store.items():
                if k.lower() == n.lower():
                    v.set(True)
        self._preview()
        self.page.say("Added to the %s list: %s" % (kind[:-1], ", ".join(new)))

    def _edit_list(self, kind):
        C = self.C
        win = tk.Toplevel(self.frame)
        win.title("Sizes" if kind == "sizes" else "Colours")
        win.configure(bg=C["content_bg"])
        try:
            win.transient(self.frame.winfo_toplevel())
        except Exception:
            pass
        _center(win, 560, 200)
        tk.Label(win, text=("The sizes your shop uses, in order, with a comma between them\n"
                            "(e.g. XS, S, M, L, XL  or  28, 30, 32, 34)") if kind == "sizes" else
                 "The colours your shop uses, with a comma between them\n(e.g. White, Black, Navy, Red)",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"],
                 justify="left").pack(anchor="w", padx=14, pady=(12, 4))
        var = tk.StringVar(value=", ".join(TX.sizes() if kind == "sizes" else TX.colours()))
        e = tk.Entry(win, textvariable=var, font=("Segoe UI", 10), relief="solid", bd=1)
        e.pack(fill="x", padx=14, ipady=4)
        e.focus_set()

        def save(_e=None):
            try:
                TX.save_list(kind, var.get())
            except ValueError as err:
                messagebox.showwarning("List", str(err), parent=win)
                return
            win.destroy()
            self._build_ticks()
            self.page.say("✔ %s list saved." % ("Size" if kind == "sizes" else "Colour"))
        bar = tk.Frame(win, bg=C["content_bg"])
        bar.pack(fill="x", padx=14, pady=12)
        self.K.button(bar, C, "Save", save, primary=True, side="right")
        self.K.button(bar, C, "Cancel", win.destroy, side="right")
        e.bind("<Return>", save)
        win.bind("<Escape>", lambda ev: win.destroy())
        self._list_win = win
        return win

    # ── style ─────────────────────────────────────────────────
    def _picked(self, row):
        pid = int(row["product_id"])
        sid = TX.style_of(pid) or pid
        if sid != pid:
            self.page.say("That is a size / colour — showing its style.")
        self.load_style(sid)

    def load_style(self, style_id):
        from config.database import db
        st = db.fetchone("SELECT p.*, ISNULL(pc.category_name_en,'') AS category FROM products p "
                         "LEFT JOIN product_categories pc ON pc.category_id=p.category_id "
                         "WHERE p.product_id=?", (int(style_id),))
        if not st:
            self.page.say("Style not found.", ok=False)
            return
        self.style = dict(st)
        self.finder.var.set("%s — %s" % (st["product_code"], st["product_name_en"]))
        rows = TX.variants(st["product_id"], active_only=False)
        listed = st.get("list_in_sales") not in (0, False)
        self.hide_var.set((not rows and _f(st.get("stock_quantity")) == 0) or not listed)
        self.info_var.set("Code %s  ·  Price %s  ·  Cost %s  ·  Unit %s  ·  Category %s  ·  "
                          "Stock of the style itself %s  ·  %d sizes / colours made"
                          % (st["product_code"], _money(st.get("unit_price")),
                             _money(TX.cost(st)), st.get("unit_of_measure_en") or "",
                             st.get("category") or "—", _qty(st.get("stock_quantity")), len(rows)))
        # tick what the style already has
        self._build_ticks(keep=False)
        for r in rows:
            if r["size"] in self.size_vars:
                self.size_vars[r["size"]].set(True)
            if r["colour"] in self.colour_vars:
                self.colour_vars[r["colour"]].set(True)
        self._preview()
        self._load_variants()

    def _new_style(self):
        from ui.products import ProductForm
        holder = {}

        def saved():
            f = holder.get("form")
            pid = getattr(f, "product_id", None)
            if pid:
                self.frame.after(60, lambda: self.load_style(pid))
        holder["form"] = ProductForm(self.frame.winfo_toplevel(), on_save=saved)
        return holder["form"]

    def _open_style(self):
        if not self.style:
            self.page.say("Pick a style first.", ok=False)
            return None
        from ui.products import ProductForm
        sid = self.style["product_id"]
        return ProductForm(self.frame.winfo_toplevel(), product_id=sid,
                           on_save=lambda: self.frame.after(60, lambda: self.load_style(sid)))

    # ── preview + create ──────────────────────────────────────
    def _preview(self):
        self.prev.delete(*self.prev.get_children())
        if not self.style:
            self.plan = []
            return
        old = {(p["size"], p["colour"]): p["price"] for p in self.plan if p["status"] != "made"}
        self.plan = TX.plan(self.style["product_id"], self._ticked("sizes"), self._ticked("colours"))
        n = 0
        for i, p in enumerate(self.plan):
            if (p["size"], p["colour"]) in old:
                p["price"] = old[(p["size"], p["colour"])]
            st = {"new": "New — will be made", "made": "✔ Already made",
                  "inactive": "Switched off — will be switched on"}[p["status"]]
            n += p["status"] != "made"
            self.prev.insert("", "end", iid=str(i), values=(
                p["size"] or "—", p["colour"] or "—", p["name"], _money(p["price"]), st),
                tags=("made",) if p["status"] == "made" else ())
        try:
            self.create_btn.configure(text="✔  Create %d" % n if n else "✔  Create")
        except Exception:
            pass

    def _edit_price(self, e):
        iid = self.prev.identify_row(e.y)
        if not iid or self.plan[int(iid)]["status"] == "made":
            return
        bbox = self.prev.bbox(iid, "price")
        if not bbox:
            return
        x, y, w, h = bbox
        var = tk.StringVar(value="%g" % self.plan[int(iid)]["price"])
        ent = tk.Entry(self.prev, textvariable=var, font=("Segoe UI", 10), justify="right",
                       relief="solid", bd=1)
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set(); ent.select_range(0, "end")

        def done(_e=None):
            v = _number(var.get())
            ent.destroy()
            if v > 0:
                self.plan[int(iid)]["price"] = round(v, 2)
                self.prev.set(iid, "price", _money(v))
        ent.bind("<Return>", done)
        ent.bind("<KP_Enter>", done)
        ent.bind("<FocusOut>", done)
        ent.bind("<Escape>", lambda ev: ent.destroy())

    def _price_all(self):
        v = _number(self.all_price_var.get())
        if v <= 0:
            self.page.say("Type a price more than 0.", ok=False)
            return
        for i, p in enumerate(self.plan):
            if p["status"] != "made":
                p["price"] = round(v, 2)
                self.prev.set(str(i), "price", _money(v))

    def _create(self, ask=True):
        from modules import permissions as perm
        if not perm.allowed("products", "add", parent=self.frame):
            return None
        if not self.style:
            self.page.say("Pick a style first.", ok=False)
            return None
        todo = [p for p in self.plan if p["status"] != "made"]
        if not todo:
            self.page.say("Nothing new to make — tick more sizes or colours.", ok=False)
            return None
        if ask and not messagebox.askyesno(
                "Create", "Make %d new product%s for %s?\n\nEach gets its own code and barcode. "
                          "Stock starts at 0." % (len(todo), "" if len(todo) == 1 else "s",
                                                  self.style["product_name_en"]),
                parent=self.frame):
            return None
        try:
            res = TX.create(self.style["product_id"], todo)
            TX.hide_style(self.style["product_id"], self.hide_var.get())
        except Exception as e:
            messagebox.showerror("Create", str(e)[:300], parent=self.frame)
            return None
        msg = "✔ %d made" % len(res["made"])
        if res["again"]:
            msg += ", %d switched on again" % len(res["again"])
        self.load_style(self.style["product_id"])
        self.page.say(msg + ". Print their labels with 🏷 Print labels for all.")
        return res

    # ── existing variants ─────────────────────────────────────
    def _load_variants(self):
        self.tree.delete(*self.tree.get_children())
        if not self.style:
            return
        rows = TX.variants(self.style["product_id"], active_only=False)
        tq = tv = 0.0
        for r in rows:
            on = r.get("is_active") not in (0, False)
            val = r["stock"] * r["cost"]
            if on:
                tq += r["stock"]
                tv += val
            bc = r["system_barcode"] or r.get("barcode") or ""
            if r.get("barcode") and r["system_barcode"]:
                bc = "%s / %s" % (r["system_barcode"], r["barcode"])
            self.tree.insert("", "end", iid=str(r["product_id"]), values=(
                r["product_code"], r["product_name_en"], r["size"] or "—", r["colour"] or "—", bc,
                _money(r.get("unit_price")), _qty(r["stock"]), _money(val),
                "Yes" if on else "No"), tags=() if on else ("off",))
        self.sum_var.set("%d sizes / colours  ·  stock %s  ·  value at cost %s"
                         % (len(rows), _qty(tq), _money(tv, sym=True)) if rows else "")

    def _selected(self):
        return [int(i) for i in self.tree.selection()]

    def _change_price(self):
        from modules import permissions as perm
        if not self.style:
            self.page.say("Pick a style first.", ok=False)
            return None
        if not perm.allowed("products", "edit", parent=self.frame):
            return None
        rows = TX.variants(self.style["product_id"], active_only=False)
        if not rows:
            self.page.say("This style has no sizes / colours yet.", ok=False)
            return None
        return PriceDialog(self, rows, self._selected())

    def _labels(self):
        if not self.style:
            self.page.say("Pick a style first.", ok=False)
            return None
        ids = [int(r["product_id"]) for r in TX.variants(self.style["product_id"])]
        if not ids:
            self.page.say("This style has no sizes / colours yet.", ok=False)
            return None
        try:
            from ui.label_printer import open_window
            return open_window(self.frame, ids)
        except Exception as e:
            messagebox.showerror("Print labels", str(e)[:200], parent=self.frame)
            return None

    def _open_variant(self):
        sel = self._selected()
        if not sel:
            self.page.say("Select a size / colour in the list first.", ok=False)
            return None
        from ui.products import ProductForm
        return ProductForm(self.frame.winfo_toplevel(), product_id=sel[0],
                           on_save=lambda: self.frame.after(60, self._load_variants))

    def _stock_matrix(self):
        win = tk.Toplevel(self.frame)
        win.title("Stock by Size & Colour")
        win.configure(bg=self.C["content_bg"])
        _center(win, 980, 560)
        win.bind("<Escape>", lambda e: win.destroy())
        return VariantStockView(win, style_id=self.style["product_id"] if self.style else None)


class PriceDialog:
    """Change the price of all sizes / colours, one size, one colour or the
    rows selected in the list."""

    def __init__(self, view, rows, selected):
        self.view = view
        C = view.C
        self.win = w = tk.Toplevel(view.frame)
        w.title("Change price")
        w.configure(bg=C["content_bg"])
        try:
            w.transient(view.frame.winfo_toplevel())
        except Exception:
            pass
        _center(w, 460, 300)
        sizes_ = TX.sort_sizes({r["size"] for r in rows if r["size"]})
        colours_ = TX.sort_colours({r["colour"] for r in rows if r["colour"]})
        tk.Label(w, text="New selling price (%s)" % view.style["product_name_en"],
                 font=("Segoe UI", 10, "bold"), bg=C["content_bg"], fg=C["text_primary"]).pack(
                     anchor="w", padx=16, pady=(14, 4))
        self.price_var = tk.StringVar(value="%g" % _f(rows[0].get("unit_price")))
        e = tk.Entry(w, textvariable=self.price_var, width=12, font=("Segoe UI", 12),
                     relief="solid", bd=1, justify="right")
        e.pack(anchor="w", padx=16, ipady=3)
        e.focus_set(); e.select_range(0, "end")
        self.mode = tk.StringVar(value="selected" if selected else "all")
        self.size_var = tk.StringVar(value=sizes_[0] if sizes_ else "")
        self.colour_var = tk.StringVar(value=colours_[0] if colours_ else "")
        self.selected = selected
        f = tk.Frame(w, bg=C["content_bg"])
        f.pack(fill="x", padx=16, pady=8)

        def radio(r, text, val, state="normal"):
            tk.Radiobutton(f, text=text, variable=self.mode, value=val, state=state,
                           font=("Segoe UI", 9), bg=C["content_bg"],
                           activebackground=C["content_bg"]).grid(row=r, column=0, sticky="w")
        radio(0, "All sizes and colours (%d)" % len(rows), "all")
        radio(1, "Only this size:", "size", "normal" if sizes_ else "disabled")
        ttk.Combobox(f, textvariable=self.size_var, values=sizes_, width=10,
                     state="readonly").grid(row=1, column=1, sticky="w", padx=6)
        radio(2, "Only this colour:", "colour", "normal" if colours_ else "disabled")
        ttk.Combobox(f, textvariable=self.colour_var, values=colours_, width=12,
                     state="readonly").grid(row=2, column=1, sticky="w", padx=6)
        radio(3, "Only the rows I selected (%d)" % len(selected), "selected",
              "normal" if selected else "disabled")
        tk.Label(w, text="Box / carton prices change by the same amount per piece.",
                 font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"]).pack(
                     anchor="w", padx=16)
        bar = tk.Frame(w, bg=C["content_bg"])
        bar.pack(fill="x", padx=16, pady=10, side="bottom")
        view.K.button(bar, C, "Apply", self.apply, primary=True, side="right")
        view.K.button(bar, C, "Cancel", w.destroy, side="right")
        w.bind("<Return>", lambda ev: self.apply())
        w.bind("<Escape>", lambda ev: w.destroy())

    def apply(self):
        price = _number(self.price_var.get())
        if price <= 0:
            messagebox.showwarning("Change price", "Type a price more than 0.", parent=self.win)
            return 0
        m = self.mode.get()
        sid = self.view.style["product_id"]
        try:
            n = TX.set_price(sid, price,
                             size=self.size_var.get() if m == "size" else None,
                             colour=self.colour_var.get() if m == "colour" else None,
                             product_ids=self.selected if m == "selected" else None)
        except Exception as e:
            messagebox.showerror("Change price", str(e)[:300], parent=self.win)
            return 0
        self.win.destroy()
        self.view._load_variants()
        self.view.page.say("✔ New price %s on %d product%s. Print new shelf labels if needed."
                           % (_money(price), n, "" if n == 1 else "s"))
        return n


# ════════════════════════════════════════════════════════════
#  Textiles ▸ Stock by Size & Colour
# ════════════════════════════════════════════════════════════
class VariantStockView:
    def __init__(self, parent, style_id=None):
        from ui import v6_kit as K
        self.K = K
        self.page = K.Page(parent, "📊  Stock by Size & Colour",
                           "Stock of each size (columns) and colour (rows), with totals and stock "
                           "value. Pick one style, a category or all styles.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.data = None
        if not TX.ready():
            _not_ready(self.page.body, C)
            return
        bar = K.card(self.page.body, C, fill="x")
        row = tk.Frame(bar, bg=C["card_bg"])
        row.pack(fill="x", padx=10, pady=8)
        self.mode = tk.StringVar(value="style" if style_id else "all")
        mf = tk.Frame(row, bg=C["card_bg"])
        mf.pack(side="left", padx=(0, 10), anchor="n")
        tk.Label(mf, text="Show", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        for txt, val in (("One style", "style"), ("A category", "category"), ("All styles", "all")):
            tk.Radiobutton(mf, text=txt, variable=self.mode, value=val, font=("Segoe UI", 9),
                           bg=C["card_bg"], activebackground=C["card_bg"],
                           command=self.load).pack(side="left")
        self._styles = TX.styles()
        self.style_var = tk.StringVar()
        if style_id:
            st = next((r for r in self._styles if int(r["product_id"]) == int(style_id)), None)
            if st:
                self.style_var.set(_style_label(st))
        f = tk.Frame(row, bg=C["card_bg"])
        f.pack(side="left", padx=(0, 10), anchor="n")
        tk.Label(f, text="Style", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.style_cb = ttk.Combobox(f, textvariable=self.style_var, width=34,
                                     values=[_style_label(r) for r in self._styles])
        self.style_cb.pack(anchor="w")
        self.style_cb.bind("<<ComboboxSelected>>", lambda e: (self.mode.set("style"), self.load()))
        self.style_cb.bind("<Return>", lambda e: (self.mode.set("style"), self.load()))
        self._cats = self._categories()
        self.cat_var = tk.StringVar(value=self._cats[0][1] if self._cats else "")
        self.cat_cb = K.combo(row, C, "Category", self.cat_var, [n for _i, n in self._cats], 18)
        self.cat_cb.bind("<<ComboboxSelected>>", lambda e: (self.mode.set("category"), self.load()))
        self.value_var = tk.StringVar(value="Cost price")
        vcb = K.combo(row, C, "Value at", self.value_var, ["Cost price", "Selling price"], 12)
        vcb.bind("<<ComboboxSelected>>", lambda e: self.load())
        bb = tk.Frame(row, bg=C["card_bg"])
        bb.pack(side="left", anchor="s")
        K.button(bb, C, "🔍  Show", self.load, primary=True)
        K.button(bb, C, "Excel", self.export_excel)
        K.button(bb, C, "CSV", self.export_csv)

        wrap = K.card(self.page.body, C, fill="both", expand=True, pady=(8, 0))
        self.tree_wrap = wrap
        self.tree = None
        self.load()

    def _categories(self):
        from config.database import db
        try:
            rows = db.fetchall("SELECT category_id, category_name_en FROM product_categories "
                               "WHERE ISNULL(is_active,1)=1 ORDER BY category_name_en") or []
        except Exception:
            rows = []
        return [(r["category_id"], r["category_name_en"]) for r in rows]

    def _query(self):
        m = self.mode.get()
        kw = {"value_at": "price" if self.value_var.get().startswith("Selling") else "cost"}
        if m == "style":
            sid = find_style(self.style_var.get())
            if not sid:
                return None, "Pick a style."
            kw["style_ids"] = [sid]
        elif m == "category":
            cid = next((i for i, n in self._cats if n == self.cat_var.get()), None)
            if not cid:
                return None, "Pick a category."
            kw["category_id"] = cid
        return kw, ""

    def load(self):
        kw, err = self._query()
        if self.tree is not None:
            self.tree._wrap.destroy()
            self.tree = None
        if kw is None:
            self.data = None
            self.page.say(err, ok=False)
            return None
        d = self.data = TX.stock_matrix(**kw)
        many = self.mode.get() != "style"
        cols = ([("style", "Style", 200, "w")] if many else []) + [("colour", "Colour", 110, "w")]
        cols += [("s%d" % i, s or "—", 64, "e") for i, s in enumerate(d["sizes"])]
        cols += [("total", "Total", 80, "e"), ("value", "Value", 110, "e")]
        self.tree = self.K.tree(self.tree_wrap, cols, height=14)
        self.tree.tag_configure("total", font=("Segoe UI", 10, "bold"), background="#F3F4F6")
        self.tree.tag_configure("neg", foreground=self.C["danger"])
        for i, (hdr, vals, tag) in enumerate(self.rows(with_header=False)):
            self.tree.insert("", "end", iid=str(i), values=vals, tags=(tag,) if tag else ())
        sym_val = _money(d["value"], sym=True)
        if d["rows"]:
            self.page.say("%d style%s  ·  %d sizes / colours  ·  %s in stock  ·  value %s"
                          % (d["styles"], "" if d["styles"] == 1 else "s", d["variants"],
                             _qty(d["total"]), sym_val))
        else:
            self.page.say("No sizes / colours here yet. Make them in Size & Colour Variants.",
                          ok=False)
        return d

    def headers(self):
        d = self.data or {"sizes": []}
        many = self.mode.get() != "style"
        return (["Style"] if many else []) + ["Colour"] + [s or "—" for s in d["sizes"]] + \
            ["Total", "Value"]

    def rows(self, with_header=False):
        """[(None, values, tag)] — the table rows + the TOTAL row."""
        d = self.data
        if not d:
            return []
        many = self.mode.get() != "style"
        out = []
        for e in d["rows"]:
            vals = ([e["style"]] if many else []) + [e["colour"] or "—"]
            vals += [(_qty(e["cells"][s]) if s in e["cells"] else "") for s in d["sizes"]]
            vals += [_qty(e["total"]), _money(e["value"])]
            out.append((None, vals, "neg" if e["total"] < 0 else ""))
        if d["rows"]:
            vals = (["TOTAL"] if many else []) + (["" if many else "TOTAL"])
            vals += [(_qty(d["col_totals"][s]) if s in d["col_totals"] else "") for s in d["sizes"]]
            vals += [_qty(d["total"]), _money(d["value"])]
            out.append((None, vals, "total"))
        return out

    def _title(self):
        m = self.mode.get()
        if m == "style":
            return "Stock by Size & Colour — %s" % self.style_var.get().split(" — ")[-1]
        if m == "category":
            return "Stock by Size & Colour — %s" % self.cat_var.get()
        return "Stock by Size & Colour"

    def export_excel(self, path=None):
        if not self.data or not self.data["rows"]:
            self.page.say("Nothing to export.", ok=False)
            return None
        from modules.report_export import export_excel
        d = self.data
        summary = [("Sizes / colours", d["variants"]), ("In stock", _qty(d["total"])),
                   ("Value (%s)" % self.value_var.get().lower(), _money(d["value"]))]
        return export_excel(self.frame, "Stock by size and colour", self.headers(),
                            [v for _h, v, _t in self.rows()], title=self._title(),
                            summary=summary, path=path)

    def export_csv(self, path=None):
        if not self.data or not self.data["rows"]:
            self.page.say("Nothing to export.", ok=False)
            return None
        if not path:
            path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                filetypes=[("CSV", "*.csv")],
                                                initialfile="Stock by size and colour.csv")
        if not path:
            return None
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(self.headers())
            for _h, vals, _t in self.rows():
                w.writerow([str(v).replace(",", "") if _is_num(v) else v for v in vals])
        self.page.say("✔ Saved: %s" % path)
        return path


def _is_num(v):
    try:
        float(str(v).replace(",", ""))
        return True
    except ValueError:
        return False
