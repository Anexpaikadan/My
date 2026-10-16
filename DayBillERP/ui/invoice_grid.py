# ============================================================
# DayBill ERP - Polosys-style editable invoice line grid
# Columns: # · Barcode · Product · Qty · Unit · Rate · Gross ·
#          VAT · Total · Stock · Purchase · Profit · Box Qty
#
# Interaction:
#   - Click/type in Product cell -> live dropdown (name/stock/SP/PP)
#   - Enter on product -> fill line, move to Qty
#   - Enter: Qty -> Rate (Unit chosen via SPACE)
#   - SPACE on a row cycles the unit (Piece/Box/Carton) + price
#   - New blank row auto-appended after a product is chosen
#   - Delete removes the focused row
# ============================================================

import tkinter as tk
from tkinter import ttk

try:
    from config.database import db
except Exception:
    db = None

try:
    from modules.smart_search import filter_products
except Exception:
    filter_products = None

try:
    from config import settings as cfg
except Exception:
    cfg = None


COLUMNS = [
    ("idx",     "#",            36,  "center"),
    ("barcode", "Bar Code",     95,  "center"),
    ("product", "Product",      230, "w"),
    ("qty",     "Qty",          60,  "center"),
    ("unit",    "Unit",         70,  "center"),
    ("rate",    "Rate",         75,  "e"),
    ("uprice",  "Unit Price",   85,  "e"),
    ("gross",   "Gross",        90,  "e"),
    ("vat",     "VAT",          75,  "e"),
    ("total",   "Total",        95,  "e"),
    ("stock",   "Stock Details",90,  "center"),
    ("purchase","Purchase",     80,  "e"),
    ("x",       "X",            30,  "center"),
    ("profit",  "Profit",       70,  "e"),
    ("boxqty",  "Box Qty",      60,  "center"),
]


def filter_exact_code(q, products):
    """True when q is exactly a product code (the dropdown handles those)."""
    ql = q.strip().lower()
    return any(str(p.get("product_code") or "").strip().lower() == ql for p in products)


class InvoiceGrid(tk.Frame):
    def __init__(self, parent, theme, products, product_units, on_change=None,
                 tax_mode="exclusive", doc_type="sales", last_kind="auto",
                 use_offers=False):
        super().__init__(parent, bg=theme["card_bg"])
        self.use_offers = bool(use_offers)   # Offers & promotions (Sales invoice)
        self.C = theme
        self.products = products
        self.product_units = product_units or {}
        self.on_change = on_change
        self.tax_mode = tax_mode   # "inclusive" or "exclusive"
        self.doc_type = doc_type   # sales | sales_return | purchase | purchase_return
        # which "Last …" document shows under the grid (None = none)
        self._last_kind = doc_type if last_kind == "auto" else last_kind
        try:
            from config import settings as _cfg
            self.cfg = _cfg
        except Exception:
            self.cfg = None
        self.lines = []
        self.price_key = None      # v6.0 price list (None = Standard, 'wholesale', list id)
        self._editor = None
        self._dropdown = None
        self._pad = None
        self._unit_popup = None
        self._build()
        self.add_blank_row()

    def _build(self):
        C = self.C
        cols = [c[0] for c in COLUMNS]
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Inv.Treeview", rowheight=30, font=("Segoe UI", 10),
                        fieldbackground="white", background="white")
        style.configure("Inv.Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background=C.get("heading_bg", C["content_bg"]), foreground="#374151")

        wrap = tk.Frame(self, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(wrap, orient="vertical")
        vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 style="Inv.Treeview", selectmode="browse",
                                 yscrollcommand=vsb.set, height=10)
        vsb.config(command=self.tree.yview)
        for key, title, w, anchor in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=w, anchor=anchor, stretch=(key == "product"))
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("blank", background="white")
        # Excel-style cell lines (every transaction window uses this grid)
        try:
            from ui.grid_lines import excel_grid
            excel_grid(self.tree)
        except Exception:
            pass

        # ── Fixed totals footer — a SEPARATE single-row Treeview using
        # the same column widths, packed below the scrollable list so it
        # never scrolls out of view no matter how many lines are added. ──
        self.footer_tree = ttk.Treeview(wrap, columns=cols, show="",
                                        style="InvFooter.Treeview",
                                        selectmode="none", height=1)
        style.configure("InvFooter.Treeview", rowheight=28,
                        font=("Segoe UI", 10, "bold"),
                        background="#FFF6F4", fieldbackground="#FFF6F4",
                        foreground="#C0392B")
        for key, title, w, anchor in COLUMNS:
            self.footer_tree.column(key, width=w, anchor=anchor,
                                    stretch=(key == "product"))
        self.footer_tree.pack(fill="x", side="bottom")
        self.footer_tree.insert("", "end", iid="sum", values=(""))
        try:
            from ui.grid_lines import excel_grid
            excel_grid(self.footer_tree, fill_empty=False, color="#E8C3BC")
            # footer columns follow the item columns when they are dragged
            self.tree.bind("<ButtonRelease-1>", lambda e: self._sync_footer_widths(), add="+")
        except Exception:
            pass
        # v6.2 columns tool: hidden / moved / resized columns → the footer follows;
        # sales, purchase, return… forms each remember their own columns
        self.tree._keep_columns = {"product"}
        try:
            from ui.table_columns import set_name
            set_name(self.tree, "entry_grid:%s" % (self.doc_type or "sales"))
        except Exception:
            pass
        self.tree.bind("<<ColumnsChanged>>", lambda e: self._sync_footer_widths(), add="+")

        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<Return>", self._on_tree_return)
        self.tree.bind("<KP_Enter>", self._on_tree_return)
        self.tree.bind("<space>", self._on_space)
        self.tree.bind("<Delete>", self._on_delete)
        self.tree.bind("<Button-1>", self._on_click)
        # HOLD Ctrl → units, box qty, purchase price, profit, stock; let go = closed
        try:
            from ui.product_boxes import CtrlHold
            self._ctrl_hold = CtrlHold([self.tree], self._ctrl_box)
        except Exception:
            self._ctrl_hold = None

        hint = tk.Frame(self, bg=C["card_bg"]); hint.pack(fill="x", padx=4, pady=(2, 0))
        # last saved document of this kind — small, on the right
        self.last_var = tk.StringVar(value=self._last_doc_text(self._last_kind))
        tk.Label(hint, textvariable=self.last_var, font=("Segoe UI", 8, "bold"),
                 bg=C["card_bg"], fg=C.get("primary", "#2563EB")).pack(side="right")
        tk.Label(hint,
            text="Barcode + Enter loads the product.  Type in Product to search.  "
                 "SPACE cycles the unit.  HOLD Ctrl = purchase price + box qty.  "
                 "✕ or Delete removes a row.  Right-click a heading = columns.",
            font=("Segoe UI", 8), bg=C["card_bg"],
            fg=C["text_secondary"]).pack(side="left")

    LAST_DOCS = {
        "sales": ("Last invoice", "SELECT TOP 1 invoice_number AS n, total_amount AS t "
                  "FROM sales_invoices WHERE ISNULL(sale_channel,'INV')<>'POS' "
                  "ORDER BY invoice_id DESC"),
        "pos": ("Last bill", "SELECT TOP 1 invoice_number AS n, total_amount AS t "
                "FROM sales_invoices WHERE sale_channel='POS' ORDER BY invoice_id DESC"),
        "purchase": ("Last purchase", "SELECT TOP 1 invoice_number AS n, total_amount AS t "
                     "FROM purchase_invoices ORDER BY purchase_id DESC"),
        "sales_return": ("Last return", "SELECT TOP 1 return_number AS n, total_amount AS t "
                         "FROM sales_returns ORDER BY return_id DESC"),
        "purchase_return": ("Last return", "SELECT TOP 1 return_number AS n, "
                            "total_amount AS t FROM purchase_returns ORDER BY return_id DESC"),
    }

    def _last_doc_text(self, kind):
        spec = self.LAST_DOCS.get(kind or "")
        if not spec:
            return ""
        try:
            from config.database import db as _db
            r = _db.fetchone(spec[1])
            if not r or not r.get("n"):
                return ""
            return "%s  %s  =  %s" % (spec[0], r["n"], f"{float(r.get('t') or 0):,.2f}")
        except Exception:
            return ""

    def refresh_last(self, kind=None):
        try:
            self.last_var.set(self._last_doc_text(kind or getattr(self, "_last_kind", None)))
        except Exception:
            pass

    def _sync_footer_widths(self):
        try:                                    # same columns shown, same order
            from ui.table_columns import shown_columns
            shown = shown_columns(self.tree)
            if shown != shown_columns(self.footer_tree):
                self.footer_tree.configure(displaycolumns=shown)
        except Exception:
            pass
        try:
            from ui.zoom import raw_column      # widths already in screen pixels
            for key, *_r in COLUMNS:
                raw_column(self.footer_tree, key, width=self.tree.column(key, "width"))
            self.footer_tree._excel_grid.schedule()
        except Exception:
            pass

    def add_blank_row(self):
        ln = {"product_id": None, "product_code": "", "barcode": "",
              "product_name_en": "", "product_name_ar": "",
              "quantity": 1.0, "unit_of_measure_en": "", "unit_price": 0.0,
              "discount_percent": 0.0, "discount_amount": 0.0,
              "line_amount": 0.0, "vat_category_id": None,
              "vat_category_code": "S", "vat_rate": 15.0, "vat_amount": 0.0,
              "line_total": 0.0, "purchase_price": 0.0, "stock_quantity": 0.0,
              "box_qty": "", "_blank": True}
        self.lines.append(ln)
        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, ln in enumerate(self.lines):
            tag = "blank" if ln.get("_blank") else ""
            self.tree.insert("", "end", iid=str(i),
                             values=self._row_values(i, ln), tags=(tag,))
        self._insert_totals_row()
        if self.on_change:
            self.on_change()

    def _insert_totals_row(self):
        """Fixed footer (Qty · Gross · VAT · Total · Profit sums) — lives
        in self.footer_tree, a separate always-visible widget, NOT a row
        inside the scrollable line list."""
        def money(x):
            try:
                return f"{float(x):,.2f}"
            except Exception:
                return "0.00"
        real = [l for l in self.lines if l.get("product_id")]
        if not hasattr(self, "footer_tree"):
            return
        if not real:
            self.footer_tree.item("sum", values=([""] * len(COLUMNS)))
            return
        tqty = sum(float(l.get("quantity", 0) or 0) for l in real)
        tgross = sum(float(l.get("line_amount", 0) or 0) for l in real)
        tvat = sum(float(l.get("vat_amount", 0) or 0) for l in real)
        ttot = sum(float(l.get("line_total", 0) or 0) for l in real)
        tprofit = sum((float(l.get("unit_price", 0) or 0)
                       - float(l.get("purchase_price", 0) or 0))
                      * float(l.get("quantity", 0) or 0) for l in real)
        self.footer_tree.item("sum", values=(
            "", "", f"{len(real)} items", f"{tqty:g}", "", "", "",
            money(tgross), money(tvat), money(ttot), "", "", "",
            money(tprofit), ""))

    def _row_values(self, i, ln):
        def money(x):
            try:
                return f"{float(x):,.2f}"
            except Exception:
                return "0.00"
        if ln.get("_blank") and not ln.get("product_id"):
            return (i + 1, "", "", "", "", "", "", "", "", "", "", "", "", "", "")
        profit = (float(ln["unit_price"]) - float(ln["purchase_price"])) * float(ln["quantity"])
        qty = float(ln["quantity"]) or 0
        uprice = (float(ln["line_amount"]) / qty) if qty else 0.0
        return (
            i + 1,
            ln.get("barcode", ""),
            ln.get("product_name_en", "") + (("   🏷 " + ln["offer_text"])
                                             if ln.get("offer_text") else ""),
            f"{float(ln['quantity']):g}",
            ln.get("unit_of_measure_en", ""),
            money(ln["unit_price"]),
            money(uprice),
            money(ln["line_amount"]),
            money(ln["vat_amount"]),
            money(ln["line_total"]),
            f"{float(ln.get('stock_quantity', 0)):g}",
            money(ln["purchase_price"]),
            "✕",
            money(profit),
            ln.get("box_qty", ""),
        )

    def _search_limit(self):
        """Settings ▸ Performance ▸ Product Search Limit (5–500)."""
        try:
            return max(5, min(500, int(float(self.cfg.get("perf_search_limit", 50) or 50))))
        except Exception:
            return 40

    def _vat_applies(self):
        """Settings ▸ Tax: global VAT switch + per-document apply flags."""
        if self.cfg is None:
            return True
        try:
            if not self.cfg.flag("vat_enabled", True):
                return False
            key = {"sales": "apply_vat_sales",
                   "sales_return": "apply_vat_sales_return",
                   "purchase": "apply_vat_purchase",
                   "purchase_return": "apply_vat_purchase_return",
                   "pos": "apply_vat_pos"}.get(self.doc_type)
            if key is not None and not self.cfg.flag(key, True):
                return False
        except Exception:
            pass
        return True

    def _recalc(self, ln):
        qty = float(ln["quantity"]); price = float(ln["unit_price"])
        rate = float(ln["vat_rate"]) if self._vat_applies() else 0.0
        if self.use_offers and ln.get("product_id"):
            # a saved line keeps the offer it was sold with until its qty changes
            if ln.get("_frozen_qty") is not None and abs(qty - ln["_frozen_qty"]) > 1e-9:
                ln.update(offer_off=False, _frozen_qty=None)
            try:
                from modules import offers as _offers
                _offers.apply_to_line(
                    ln, "sales", unit_key="unit_of_measure_en",
                    line_incl=getattr(self, "tax_mode", "exclusive") == "inclusive",
                    rate=rate)
                if ln.get("offer_id") and qty * price:
                    ln["discount_percent"] = round(
                        float(ln.get("discount_amount") or 0) * 100.0 / (qty * price), 2)
                elif not ln.get("offer_off"):
                    ln["discount_percent"] = 0.0
            except Exception:
                pass
        disc = float(ln.get("discount_amount", 0))
        gross = qty * price - disc
        if getattr(self, "tax_mode", "exclusive") == "inclusive" and rate:
            # entered price already includes VAT → extract it
            net = gross / (1 + rate / 100.0)
            ln["line_amount"] = net
            ln["vat_amount"] = gross - net
            ln["line_total"] = gross
        else:
            # exclusive → add VAT on top
            ln["line_amount"] = gross
            ln["vat_amount"] = gross * rate / 100.0
            ln["line_total"] = gross + ln["vat_amount"]

    def _manual_price(self, ln):
        """The user set the price by hand → no offer discount on this line."""
        if ln.get("offer_id") or self.use_offers:
            ln.update(offer_off=True, discount_amount=0.0, discount_percent=0.0,
                      offer_id=None, offer_text="", _frozen_qty=None)

    def _match_saved_price(self, ln):
        """A saved line may hold its price with or without VAT (POS bills,
        older versions, the price mode changed later). Re-express it in
        this grid's mode so re-opening + saving never changes the total."""
        try:
            qty = float(ln.get("quantity") or 0)
            price = float(ln.get("unit_price") or 0)
            disc = float(ln.get("discount_amount") or 0)
            rate = float(ln.get("vat_rate") or 0) if self._vat_applies() else 0.0
            net = ln.get("line_amount"); tot = ln.get("line_total")
            if not qty or not rate or net is None or tot is None:
                return
            net, tot = float(net), float(tot)
            gross = qty * price - disc
            incl_mode = getattr(self, "tax_mode", "exclusive") == "inclusive"
            if incl_mode and abs(gross - net) < 0.011 and abs(gross - tot) >= 0.011:
                ln["unit_price"] = round((tot + disc) / qty, 4)        # excl → incl
            elif not incl_mode and abs(gross - tot) < 0.011 and abs(gross - net) >= 0.011:
                ln["unit_price"] = round((net + disc) / qty, 4)        # incl → excl
        except Exception:
            pass

    def totals(self):
        real = [l for l in self.lines if l.get("product_id")]
        return {
            "subtotal": sum(l["line_amount"] for l in real),
            "discount": sum(l.get("discount_amount", 0) for l in real),
            "vat": sum(l["vat_amount"] for l in real),
            "total": sum(l["line_total"] for l in real),
            "count": len(real),
        }

    def data_lines(self):
        return [l for l in self.lines if l.get("product_id")]

    def set_lines(self, rows):
        """Load existing invoice lines (edit mode)."""
        if not rows:                      # cleared for the next document
            self.refresh_last()
        self.lines = []
        for r in rows:
            ln = dict(r)
            ln["_blank"] = False
            ln.setdefault("box_qty", "")
            ln.setdefault("purchase_price", 0.0)
            ln.setdefault("stock_quantity", 0.0)
            self._match_saved_price(ln)
            if self.use_offers:          # keep the discount it was saved with
                ln.update(offer_off=True, _frozen_qty=float(ln.get("quantity") or 0))
            self._recalc(ln)
            self.lines.append(ln)
        self.add_blank_row()

    # ── editing ───────────────────────────────────────────────
    @staticmethod
    def _iid_idx(iid):
        """Treeview iid -> line index, or None for the totals footer row
        (iid 'sum') and anything else that isn't a data row."""
        try:
            return int(iid)
        except (TypeError, ValueError):
            return None

    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        self._begin_edit(event)

    def _begin_edit(self, event):
        self._close_editor()
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row:
            return
        idx = self._iid_idx(row)
        if idx is None:
            return
        col_no = int(col.replace("#", "")) - 1
        key = COLUMNS[col_no][0]
        if key == "product":
            self._edit_product(idx)
        elif key == "barcode":
            self._edit_barcode(idx)
        elif key in ("qty", "rate"):
            self._edit_number(idx, key)
        elif key == "x":
            self._delete_row(idx)

    def _cell_bbox(self, idx, key):
        col_index = [c[0] for c in COLUMNS].index(key)
        return self.tree.bbox(str(idx), f"#{col_index+1}")

    def _hidden(self, key):
        """True when the user hid this column (columns tool)."""
        try:
            from ui.table_columns import shown_columns
            return key not in shown_columns(self.tree)
        except Exception:
            return False

    def _edit_barcode(self, idx):
        """Scan or type a barcode; Enter resolves the product instantly."""
        if self._hidden("barcode"):             # Bar Code column hidden → Product
            return self._edit_product(idx)
        if self._editor is not None:            # never leave an old editor behind
            self._close_editor()
        try:
            self.tree.update_idletasks()        # real row positions first
        except Exception:
            pass
        bbox = self._cell_bbox(idx, "barcode")
        if not bbox:
            self.tree.see(str(idx))
            bbox = self._cell_bbox(idx, "barcode")
            if not bbox:
                return
        x, y, w, h = bbox
        var = tk.StringVar(value=self.lines[idx].get("barcode", ""))
        e = tk.Entry(self.tree, textvariable=var, font=("Segoe UI", 10),
                     relief="solid", bd=1, justify="center")
        e.place(x=x, y=y, width=max(w, 110), height=h)
        e.focus_set(); e.icursor("end")
        self._editor = e
        if getattr(self, "_ctrl_hold", None):
            self._ctrl_hold.attach(e)
        e.bind("<Return>", lambda ev: self._barcode_enter(idx, var))
        e.bind("<KP_Enter>", lambda ev: self._barcode_enter(idx, var))
        e.bind("<Escape>", lambda ev: self._close_editor())

    def _resolve_barcode(self, code):
        """
        Returns (product, matched_unit_or_None). Checks the product's own
        primary barcode/code first, then the multi-barcode-per-unit table
        (so scanning a Box or Carton barcode selects that unit, not just
        the base unit) — matches the spec: different barcodes for
        different units on the same product must resolve correctly.
        """
        code = (code or "").strip()
        if not code:
            return None, None
        if db is not None:
            try:      # the ONE shared resolver: unit → extra → product barcode → code
                from modules.barcode_resolver import resolve
                hit = resolve(code, scale=False, products=self.products)
                if hit:
                    p = next((x for x in self.products
                              if x.get("product_id") == hit["product_id"]), None)
                    if p:
                        units = self.product_units.get(hit["product_id"], [])
                        unit = next((u for u in units if hit["unit_id"]
                                     and u.get("unit_id") == hit["unit_id"]), None)
                        return p, unit
                    return None, None
            except Exception:
                pass
        for p in self.products:
            if str(p.get("barcode", "")).strip() == code:
                return p, None
        for p in self.products:
            if str(p.get("product_code", "")).strip() == code:
                return p, None
        # per-unit barcodes (Box / Carton rows of the product form) and the
        # extra Multi-Barcodes — one shared lookup (modules.product_lookup)
        if db is not None:
            try:
                from modules.product_lookup import barcode_owner
                hit = barcode_owner(code)
                if hit:
                    p = next((x for x in self.products
                              if x["product_id"] == hit["product_id"]), None)
                    if p:
                        unit = None
                        if hit.get("unit_id"):
                            units = self.product_units.get(hit["product_id"], [])
                            unit = next((u for u in units
                                         if u.get("unit_id") == hit["unit_id"]), None)
                        return p, unit
            except Exception:
                pass
        return None, None

    def _barcode_enter(self, idx, var):
        code = var.get().strip()
        p, matched_unit = self._resolve_barcode(code)
        scale_hit = None
        if not p and code:
            try:      # weighing-scale label: PLU + weight/price in the code
                from modules.scale_barcode import decode
                scale_hit = decode(code)
            except Exception:
                scale_hit = None
            if scale_hit:
                pid = scale_hit["product"].get("product_id")
                p = next((x for x in self.products if x.get("product_id") == pid), None)
        self._close_editor()
        if p and scale_hit:
            # every scale label is its own line (its own weight / amount)
            self._apply_product(idx, p, merge=False)
            ln = self.lines[idx] if idx < len(self.lines) else None
            if ln is not None and ln.get("product_id") == p.get("product_id"):
                from modules.scale_barcode import line_values
                rate = float(ln.get("vat_rate") or 0) if self._vat_applies() else 0.0
                qty, price = line_values(
                    scale_hit, getattr(self, "tax_mode", "exclusive") == "inclusive", rate)
                ln["quantity"] = qty
                if price is not None:          # price label: line = label amount
                    ln["unit_price"] = price
                    self._manual_price(ln)
                self._recalc(ln)
            self._refresh()
            try:
                if self.on_change:
                    self.on_change()
            except Exception:
                pass
            return "break"
        if p:
            self._apply_product(idx, p, matched_unit=matched_unit)
            self._refresh()
            try:      # Settings ▸ Barcode: audible confirmation on scan
                if self.cfg is not None and self.cfg.flag("barcode_sound"):
                    self.bell()
            except Exception:
                pass
            self.after(20, lambda: self._edit_number(idx, "qty"))
            self.after(40, lambda: self._auto_history_box(idx))
        elif code:
            # unknown code -> product search prefilled with what was typed
            self._refresh()
            self.after(20, lambda: self._edit_product(idx, prefill=code))
        else:
            # empty Enter: move to the next column (Excel-style), never
            # resolve or insert anything
            self._refresh()
            self.after(20, lambda: self._edit_product(idx))
        return "break"

    def _edit_product(self, idx, prefill=None):
        if self._editor is not None:            # never leave an old editor behind
            self._close_editor()
        bbox = self._cell_bbox(idx, "product")
        if not bbox:
            self.tree.see(str(idx))
            bbox = self._cell_bbox(idx, "product")
            if not bbox:
                return
        x, y, w, h = bbox
        initial = prefill if prefill is not None \
            else self.lines[idx].get("product_name_en", "")
        var = tk.StringVar(value=initial)
        e = tk.Entry(self.tree, textvariable=var, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        e.place(x=x, y=y, width=max(w, 220), height=h)
        e.focus_set(); e.icursor("end")
        self._editor = e
        if getattr(self, "_ctrl_hold", None):
            self._ctrl_hold.attach(e)
        e.bind("<KeyRelease>", lambda ev: self._product_keyrelease(ev, idx, var, x, y + h))
        e.bind("<Return>", lambda ev: self._product_enter(idx, var))
        e.bind("<KP_Enter>", lambda ev: self._product_enter(idx, var))
        e.bind("<Down>", lambda ev: self._dropdown_focus())
        e.bind("<Escape>", lambda ev: self._close_editor())
        if prefill:
            # carried over from the barcode cell — show matches right away
            self.after(10, lambda: self._show_dropdown(
                idx, self._search(prefill)[:self._search_limit()], x, y + h))

    def _product_keyrelease(self, ev, idx, var, dx, dy):
        if ev.keysym in ("Return", "KP_Enter", "Down", "Up", "Escape", "Tab"):
            return
        q = var.get().strip()
        if not q:
            self._close_dropdown(); return
        self._show_dropdown(idx, self._search(q)[:self._search_limit()], dx, dy)

    def _scale_hit(self, q):
        try:
            from modules.scale_barcode import decode
            return decode(q)
        except Exception:
            return None

    def _search(self, q):
        if filter_products:
            try:
                found = filter_products(q, self.products)
                if not found and " " not in q.strip() and len(q.strip()) >= 4 and db is not None:
                    # a Box / Carton / extra barcode: show its product
                    p, _u = self._resolve_barcode(q)
                    if p is not None:
                        found = [p]
                return found
            except Exception:
                pass
        ql = q.lower()
        return [p for p in self.products
                if ql in (str(p.get("product_code", "")) + " " +
                          str(p.get("product_name_en", "")) + " " +
                          str(p.get("alias_name", ""))).lower()]

    def _show_dropdown(self, idx, matches, dx, dy):
        self._close_dropdown()
        if not matches:
            return
        panel = tk.Toplevel(self.tree)
        panel.overrideredirect(True)
        panel.attributes("-topmost", True)
        rx = self.tree.winfo_rootx() + dx
        ry = self.tree.winfo_rooty() + dy
        cols = ("code", "name", "stock", "sp", "svat", "pp")
        style = ttk.Style()
        try:   # row height follows the real font size (Windows display scaling)
            import tkinter.font as _tkf
            _ls = _tkf.Font(family="Segoe UI", size=10).metrics("linespace")
            style.configure("Dropdown.Treeview", rowheight=max(24, _ls + 8),
                            font=("Segoe UI", 10))
            style.configure("Dropdown.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        except Exception:
            pass
        rows = min(len(matches), 8)          # show up to 8 products, scroll for more
        tv = ttk.Treeview(panel, columns=cols, show="headings",
                          height=rows, style="Dropdown.Treeview")
        for k, t, w in (("code", "Code", 80), ("name", "Product", 250), ("stock", "Stock", 60),
                        ("sp", "SPrice", 72), ("svat", "Rate+VAT", 80),
                        ("pp", "PPrice", 72)):
            tv.heading(k, text=t)
            tv.column(k, width=w, anchor=("w" if k in ("name", "code") else "e"),
                      stretch=(k == "name"))
        if len(matches) > rows:
            vsb = ttk.Scrollbar(panel, orient="vertical", command=tv.yview)
            tv.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        for i, p in enumerate(matches):
            _show_stock = True
            try:
                _show_stock = cfg.flag("show_stock_during_sales", True)
            except Exception:
                pass
            sp = float(p.get("unit_price", 0) or 0)
            vrate = float(p.get("vat_rate", 15) or 0)
            try:
                from config import settings as _c
                sp_vat = _c.price_with_vat(sp, vrate)
            except Exception:
                sp_vat = sp * (1 + vrate / 100.0)
            tv.insert("", "end", iid=str(i), values=(
                p.get("product_code", "") or "", p["product_name_en"],
                f"{float(p.get('stock_quantity',0)):g}" if _show_stock else "—",
                f"{sp:,.2f}",
                f"{sp_vat:,.2f}",
                f"{float(p.get('purchase_price',0)):,.2f}"))
        tv.bind("<Return>", lambda e: self._dropdown_pick(idx))
        tv.bind("<KP_Enter>", lambda e: self._dropdown_pick(idx))
        tv.bind("<Double-1>", lambda e: self._dropdown_pick(idx))
        tv.bind("<ButtonRelease-1>", lambda e: self._dropdown_pick(idx))
        tv.bind("<Escape>", lambda e: self._close_dropdown())
        # size the popup from what the table really needs, keep it on screen
        try:
            panel.update_idletasks()
            pw = max(640, tv.winfo_reqwidth() + 20)
            ph = tv.winfo_reqheight() + 4
            sw = panel.winfo_screenwidth()
            sh = panel.winfo_screenheight()
            if rx + pw > sw:
                rx = max(0, sw - pw)
            if ry + ph > sh - 40:            # flip above the row
                ry = max(0, self.tree.winfo_rooty() + dy - ph - 30)
            panel.geometry(f"{pw}x{ph}+{rx}+{ry}")
        except Exception:
            pass
        self._dropdown = panel
        self._dropdown_tv = tv
        self._dropdown_matches = matches
        # preselect the first row so Enter picks it immediately
        first = tv.get_children()
        if first:
            tv.selection_set(first[0]); tv.focus(first[0])

    def _dropdown_focus(self):
        tv = getattr(self, "_dropdown_tv", None)
        if tv and tv.winfo_exists():
            kids = tv.get_children()
            if kids:
                tv.focus_set(); tv.selection_set(kids[0]); tv.focus(kids[0])

    def _dropdown_pick(self, idx):
        tv = getattr(self, "_dropdown_tv", None)
        if not tv:
            return
        sel = tv.selection() or (tv.focus(),)
        if not sel or not sel[0]:
            return
        p = self._dropdown_matches[int(sel[0])]
        self._close_dropdown(); self._close_editor()
        self._pick_product(idx, p)

    def _pick_product(self, idx, p):
        """Apply a product chosen from Search. Multi-unit products no
        longer open a dialog box — the default unit is applied straight
        away and SPACE in the Qty column cycles Piece → Box → Carton
        inline (a small hint badge shows the active unit)."""
        units = self.product_units.get(p.get("product_id"), [])
        self._apply_product(idx, p)
        self._refresh()
        self.after(20, lambda: self._edit_number(idx, "qty"))
        self.after(40, lambda: self._auto_history_box(idx))
        if len(units) > 1:
            # non-blocking hint: this product has more units
            self.after(60, lambda: self._show_unit_hint(
                idx, extra="SPACE = change unit"))

    def _finish_product_pick(self, idx, p, unit_id, price_override):
        unit = next((u for u in self.product_units.get(p.get("product_id"), [])
                    if u.get("unit_id") == unit_id), None)
        self._apply_product(idx, p, matched_unit=unit)
        if price_override is not None and idx < len(self.lines):
            self.lines[idx]["unit_price"] = price_override
            self._manual_price(self.lines[idx])
            self._recalc(self.lines[idx])
        self._refresh()
        self.after(20, lambda: self._edit_number(idx, "qty"))
        self.after(40, lambda: self._auto_history_box(idx))

    def _auto_history_box(self, idx):
        """When a product is picked and the cursor lands on Quantity,
        automatically pop the last-5 purchases + sales box (date /
        invoice # / party / rate). Off if Settings disables it."""
        try:
            if self.cfg is not None and not self.cfg.flag("auto_history_box", True):
                return
        except Exception:
            pass
        if idx >= len(self.lines):
            return
        pid = self.lines[idx].get("product_id")
        if not pid:
            return
        p = next((x for x in self.products if x["product_id"] == pid), None)
        if not p:
            return
        try:
            from ui.product_boxes import ProductHistoryBox
            ProductHistoryBox.show(self.winfo_toplevel(), p, self.C)
        except Exception:
            pass

    def _product_enter(self, idx, var):
        q = var.get().strip()
        if not q:
            # Empty Enter must NEVER insert a product. Stay in the cell.
            self.bell()
            return "break"
        # If the search dropdown is showing, Enter confirms the
        # highlighted row (what the user actually sees selected).
        if " " not in q and len(q) >= 4 and not filter_exact_code(q, self.products):
            # a barcode scanned into the Product box (Box / Carton / extra /
            # scale label) → same result as the Barcode column
            p, unit = self._resolve_barcode(q)
            if p is not None or self._scale_hit(q):
                self._close_dropdown()
                var2 = tk.StringVar(value=q)
                return self._barcode_enter(idx, var2)
        tv = getattr(self, "_dropdown_tv", None)
        if tv is not None:
            try:
                if tv.winfo_exists() and tv.get_children():
                    self._dropdown_pick(idx)
                    return "break"
            except Exception:
                pass
        matches = self._search(q)
        if len(matches) == 1:
            # Unambiguous — apply (or open the unit/info dialog if the
            # product has multiple units) then flow to Qty (Excel-style)
            self._close_dropdown(); self._close_editor()
            self._pick_product(idx, matches[0])
        elif matches:
            # Several matches — show them; next Enter confirms the
            # highlighted one. No silent first-match insert.
            bbox = self._cell_bbox(idx, "product")
            if bbox:
                x, y, w, h = bbox
                self._show_dropdown(idx, matches[:self._search_limit()], x, y + h)
        else:
            self.bell()                 # nothing found — stay put
        return "break"

    def _set_unit(self, ln, unit):
        """Apply a unit record (from self.product_units) onto a line —
        the single source of truth used by product-select, barcode-scan
        unit matching, and the Smart Unit picker, so they never drift."""
        ln["unit_of_measure_en"] = unit.get("unit_name_en", ln.get("unit_of_measure_en", "Unit"))
        factor = float(unit.get("conversion_factor", 1) or 1)
        if self.doc_type in ("purchase", "purchase_return"):
            # v6.0 fix: purchases are at COST — the unit's purchase price, else
            # the product's cost × units in it (was: the unit's SELLING price)
            cost = float(unit.get("purchase_price") or 0)
            if cost <= 0:
                base_cost = float(ln.get("purchase_price") or 0)
                cost = base_cost * factor if base_cost > 0 else 0.0
            ln["unit_price"] = cost or ln.get("unit_price", 0)
        else:
            ln["unit_price"] = float(unit.get("selling_price") or 0) or ln.get("unit_price", 0)
        ln["box_qty"] = f"{factor:g}"
        self._apply_price_list(ln, factor)

    # ── v6.0: price lists (Standard / Wholesale / customer lists) ──
    def _apply_price_list(self, ln, factor=1.0):
        key = getattr(self, "price_key", None)
        if key is None or self.doc_type != "sales" or not ln.get("product_id"):
            return
        try:
            from modules import price_lists as PL
            ln["unit_price"] = round(float(PL.price_for(
                key, ln["product_id"], ln.get("unit_of_measure_en"), ln.get("unit_price"),
                factor)), 4)
        except Exception:
            pass

    def set_price_key(self, key, reprice=True):
        """Change the price list; lines already on the invoice get the new
        price (a price typed by hand is kept)."""
        self.price_key = key
        if not reprice:
            return 0
        n = 0
        for ln in self.lines:
            pid = ln.get("product_id")
            if not pid or ln.get("_price_typed"):
                continue
            p = next((x for x in self.products if x.get("product_id") == pid), None)
            units = self.product_units.get(pid, [])
            u = next((x for x in units if x.get("unit_name_en") == ln.get("unit_of_measure_en")), None)
            if u is not None:
                base = float(u.get("selling_price") or 0) or float((p or {}).get("unit_price", 0) or 0)
                factor = float(u.get("conversion_factor", 1) or 1)
            else:
                base = float((p or {}).get("unit_price", 0) or 0)
                factor = 1.0
            ln["unit_price"] = base
            self._apply_price_list(ln, factor)
            self._recalc(ln)
            n += 1
        self._refresh()
        try:
            if self.on_change:
                self.on_change()
        except Exception:
            pass
        return n

    def _barcode_required_block(self, p, matched_unit=None):
        """Settings ▸ Sales/Purchase ▸ Barcode Mandatory: refuse products
        that have no barcode at all. Returns True when blocked."""
        if self.cfg is None:
            return False
        key = ("barcode_mandatory_purchase" if self.doc_type in ("purchase", "purchase_return")
               else "barcode_mandatory_sales")
        try:
            if not self.cfg.flag(key, False):
                return False
        except Exception:
            return False
        if (matched_unit or {}).get("barcode") or p.get("barcode"):
            return False
        if any(u.get("barcode") for u in self.product_units.get(p.get("product_id"), [])):
            return False
        try:
            self.bell()
            from tkinter import messagebox
            messagebox.showwarning(
                "Barcode required",
                "%s has no barcode.\n\nAdd a barcode to the product first "
                "(Barcode Mandatory is on in Settings)." % p.get("product_name_en", "This product"),
                parent=self.winfo_toplevel())
        except Exception:
            pass
        return True

    def _apply_product(self, idx, p, matched_unit=None, merge=True):
        if self._barcode_required_block(p, matched_unit):
            return
        # Settings ▸ Sales: "Warn when product already in cart" — if the
        # SAME product + unit is already on another line, merge the
        # quantity there instead of adding a silent duplicate row, and
        # tell the cashier. Toggle: cfg key "cart_dup_check" (default on).
        try:
            dup_check = self.cfg.flag("cart_dup_check", True) if self.cfg else True
        except Exception:
            dup_check = True
        if dup_check and merge:
            want_unit = None
            if matched_unit is not None:
                want_unit = matched_unit.get("unit_name_en")
            else:
                units = self.product_units.get(p["product_id"], [])
                if units:
                    if self.doc_type in ("purchase", "purchase_return"):
                        u = next((x for x in units if x.get("is_default_purchase")),
                                 next((x for x in units if x.get("is_default")),
                                      units[0]))
                    else:
                        u = next((x for x in units if x.get("is_default")), units[0])
                    want_unit = u.get("unit_name_en")
            existing_idx = next(
                (i for i, l in enumerate(self.lines)
                 if i != idx and l.get("product_id") == p["product_id"]
                 and (want_unit is None or l.get("unit_of_measure_en") == want_unit)),
                None)
            if existing_idx is not None:
                self.lines[existing_idx]["quantity"] = \
                    float(self.lines[existing_idx].get("quantity", 0) or 0) + 1
                self._recalc(self.lines[existing_idx])
                # the row currently being edited stays blank (no duplicate)
                self._refresh()
                self.tree.selection_set(str(existing_idx))
                self.tree.focus(str(existing_idx))
                self.tree.see(str(existing_idx))
                try:
                    from ui.fluent_widgets import show_toast
                    show_toast(self.winfo_toplevel(),
                              "ℹ️  %s already in cart — quantity increased to %g"
                              % (p.get("product_name_en", ""),
                                 self.lines[existing_idx]["quantity"]),
                              kind="info")
                except Exception:
                    self.bell()
                return

        ln = self.lines[idx]
        ln["product_id"] = p["product_id"]
        ln["product_code"] = p.get("product_code", "")
        ln["barcode"] = p.get("barcode", "")
        ln["product_name_en"] = p.get("product_name_en", "")
        ln["product_name_ar"] = p.get("product_name_ar", "")
        ln["unit_price"] = float(p.get("unit_price", 0) or 0)
        ln["purchase_price"] = float(p.get("purchase_price", 0) or 0)
        ln["stock_quantity"] = float(p.get("stock_quantity", 0) or 0)
        ln["vat_category_id"] = p.get("vat_category_id")
        ln["vat_category_code"] = p.get("vat_code", "S") or "S"
        ln["vat_rate"] = float(p.get("vat_rate", 15) or 15)
        units = self.product_units.get(p["product_id"], [])
        if matched_unit is not None:
            # a specific unit was identified (e.g. by barcode scan) — use it
            self._set_unit(ln, matched_unit)
        elif units:
            # Sales docs default to the unit marked "default sales unit";
            # Purchase docs default to "default purchase unit" instead —
            # falls back to the sales default, then the first unit.
            if self.doc_type in ("purchase", "purchase_return"):
                u = next((x for x in units if x.get("is_default_purchase")),
                         next((x for x in units if x.get("is_default")),
                              units[0]))
            else:
                u = next((x for x in units if x.get("is_default")), units[0])
            self._set_unit(ln, u)
        else:
            ln["unit_of_measure_en"] = p.get("unit_of_measure_en", "Unit")
            ln["box_qty"] = ""
            self._apply_price_list(ln, 1.0)
        ln["quantity"] = 1.0
        ln["_blank"] = False
        self._recalc(ln)
        self._check_loss_warning(ln)
        if not any(l.get("_blank") and not l.get("product_id") for l in self.lines):
            self.add_blank_row()

    def _edit_number(self, idx, key):
        # Settings ▸ Sales: price editing can be locked for sales documents
        if key == "rate" and self.cfg is not None and \
                self.doc_type in ("sales", "sales_return", "pos"):
            try:
                if not self.cfg.flag("allow_price_edit", True):
                    self.bell()
                    return
            except Exception:
                pass
        self._close_editor()
        if idx >= len(self.lines):
            return
        if self._hidden(key):                   # column hidden → next step of the flow
            if key == "qty":
                return self._edit_number(idx, "rate")
            nxt = idx + 1
            if nxt >= len(self.lines):
                self.add_blank_row()
                nxt = len(self.lines) - 1
            return self.after(20, lambda: self._edit_barcode(nxt))
        self.tree.see(str(idx))
        bbox = self._cell_bbox(idx, key)
        if not bbox:
            return
        x, y, w, h = bbox
        ln = self.lines[idx]
        if key == "qty":
            cur = ln["quantity"]
        else:  # rate
            cur = ln["unit_price"]
        var = tk.StringVar(value=f"{float(cur):g}")
        e = tk.Entry(self.tree, textvariable=var, font=("Segoe UI", 10),
                     relief="solid", bd=1, justify="center")
        e.place(x=x, y=y, width=w, height=h)
        e.focus_set(); e.select_range(0, "end")
        self._editor = e
        if getattr(self, "_ctrl_hold", None):
            self._ctrl_hold.attach(e)
        e.bind("<Return>", lambda ev: self._number_enter(idx, key, var))
        e.bind("<KP_Enter>", lambda ev: self._number_enter(idx, key, var))
        e.bind("<Escape>", lambda ev: self._close_editor())
        if key == "qty":
            # Smart Multi-Unit System: Space inside Quantity CYCLES the
            # unit (Piece → Box → Carton → …) in place — no dialog box.
            # The typed quantity is preserved and a small badge shows the
            # unit that just became active.
            e.bind("<space>", lambda ev: (self._cycle_unit_inline(idx), "break")[1])

    def _check_loss_warning(self, ln):
        """Settings ▸ Sales: 'Warn when selling below cost' — flags a
        line whose rate is under the product's cost. Sales docs only;
        never blocks saving, just tells the cashier."""
        if self.doc_type not in ("sales", "pos"):
            return
        try:
            if self.cfg is not None and not self.cfg.flag("warn_sale_below_cost", True):
                return
        except Exception:
            pass
        cost = float(ln.get("purchase_price", 0) or 0)
        price = float(ln.get("unit_price", 0) or 0)
        if cost > 0 and 0 < price < cost:
            loss = (cost - price) * float(ln.get("quantity", 0) or 0)
            try:
                from ui.fluent_widgets import show_toast
                show_toast(self.winfo_toplevel(),
                          "⚠️  Selling '%s' below cost! Cost %.2f > Price %.2f "
                          "(loss %.2f)" % (ln.get("product_name_en", ""),
                                          cost, price, loss),
                          kind="error", ms=3200)
            except Exception:
                self.bell()

    def _number_enter(self, idx, key, var):
        try:
            val = float(var.get())
        except ValueError:
            val = 0.0
        ln = self.lines[idx]
        if key == "qty":
            ln["quantity"] = val
        else:  # rate
            if abs(val - float(ln.get("unit_price") or 0)) > 1e-6:
                ln["_price_typed"] = True          # kept when the price list changes
                self._manual_price(ln)      # a price typed by hand replaces the offer
            ln["unit_price"] = val
        self._recalc(ln)
        if key == "rate":
            self._check_loss_warning(ln)
        self._close_editor(); self._refresh()
        # Flow: Qty -> Rate -> next row barcode
        if key == "qty":
            self.after(20, lambda: self._edit_number(idx, "rate"))
        elif key == "rate":
            nxt = idx + 1
            if nxt >= len(self.lines):
                self.add_blank_row()
                nxt = len(self.lines) - 1
            self.after(20, lambda: self._edit_barcode(nxt))

    def _delete_row(self, idx):
        """Remove a line via the X column (or Delete key)."""
        if idx < len(self.lines) and self.lines[idx].get("product_id"):
            del self.lines[idx]
            if not any(l.get("_blank") and not l.get("product_id") for l in self.lines):
                self.add_blank_row()
            self._refresh()

    def _on_tree_return(self, event):
        sel = self.tree.focus()
        if not sel:
            return
        idx = self._iid_idx(sel)
        if idx is None or idx >= len(self.lines) or not self.lines[idx].get("product_id"):
            return
        self._edit_number(idx, "rate")

    def _ctrl_box(self):
        """Shown while Ctrl is held on a line: each unit with its box qty,
        sale / purchase price, profit and stock (the focused line, else the
        selected one, else the last product line)."""
        sel = self.tree.focus() or (self.tree.selection() or ("",))[0]
        idx = self._iid_idx(sel) if sel else None
        if idx is None or idx >= len(self.lines) or not self.lines[idx].get("product_id"):
            idx = next((i for i in range(len(self.lines) - 1, -1, -1)
                        if self.lines[i].get("product_id")), None)
            if idx is None:
                return None
        pid = self.lines[idx]["product_id"]
        p = next((x for x in self.products if x["product_id"] == pid), None)
        if not p:
            return None
        from ui.product_boxes import UnitProfitBox
        return UnitProfitBox(self.winfo_toplevel(), p, self.product_units.get(pid, []),
                             self.C, hold=True)

    def _show_product_info(self, event=None):
        """Kept for old callers / the keypad: open the box (toggle)."""
        existing = getattr(self, "_unit_box", None)
        if existing is not None and existing.winfo_exists():
            existing.destroy()
            self._unit_box = None
            return
        sel = self.tree.focus()
        idx = self._iid_idx(sel) if sel else None
        if idx is None or idx >= len(self.lines) or not self.lines[idx].get("product_id"):
            return
        pid = self.lines[idx]["product_id"]
        p = next((x for x in self.products if x["product_id"] == pid), None)
        if not p:
            return
        try:
            from ui.product_boxes import UnitProfitBox
            self._unit_box = UnitProfitBox(self.winfo_toplevel(), p,
                                           self.product_units.get(pid, []), self.C)
        except Exception:
            pass

    def _on_space(self, event):
        """Space pressed while a row is selected (not actively editing) —
        cycle the row's unit in place, exactly like pressing Space inside
        the Qty field. No dialog box."""
        sel = self.tree.focus()
        if not sel:
            return "break"
        idx = self._iid_idx(sel)
        if idx is None or idx >= len(self.lines) or not self.lines[idx].get("product_id"):
            return "break"
        self._cycle_unit_inline(idx)
        return "break"

    def cycle_unit(self, idx):
        """Kept for the on-screen keypad's Unit button (mouse-only path):
        advances to the next unit without opening the popup."""
        if idx >= len(self.lines):
            return
        ln = self.lines[idx]
        if not ln.get("product_id"):
            return
        units = self.product_units.get(ln["product_id"], [])
        if len(units) < 2:
            return
        names = [u["unit_name_en"] for u in units]
        try:
            i = names.index(ln["unit_of_measure_en"])
        except ValueError:
            i = -1
        nxt = units[(i + 1) % len(units)]
        self._set_unit(ln, nxt)
        self._recalc(ln); self._refresh()
        self.tree.selection_set(str(idx)); self.tree.focus(str(idx))

    def _update_row(self, idx):
        """Refresh a single Treeview row in place (keeps any cell editor
        that is currently open alive — unlike a full _refresh)."""
        try:
            self.tree.item(str(idx), values=self._row_values(idx, self.lines[idx]))
            self._insert_totals_row()
        except Exception:
            self._refresh()
            return
        if self.on_change:
            self.on_change()

    def _cycle_unit_inline(self, idx):
        """Space in the Qty column (or on a focused row) — advance to the
        next unit of the product (Piece → Box → Carton → back to Piece).
        No dialog box: the Unit / Rate / Box Qty columns update live, the
        quantity the user already typed stays in the editor, and a small
        floating badge confirms the unit that just became active."""
        if idx >= len(self.lines):
            return
        ln = self.lines[idx]
        pid = ln.get("product_id")
        if not pid:
            return
        units = self.product_units.get(pid, [])
        if len(units) < 2:
            self._show_unit_hint(idx, extra="only one unit")
            return

        # preserve whatever quantity the user already typed in the editor
        typed_qty = None
        if self._editor is not None:
            try:
                typed_qty = float(self._editor.get() or 0)
            except Exception:
                typed_qty = None

        names = [u.get("unit_name_en", "") for u in units]
        try:
            i = names.index(ln.get("unit_of_measure_en", ""))
        except ValueError:
            i = -1
        nxt = units[(i + 1) % len(units)]
        self._set_unit(ln, nxt)
        if typed_qty is not None and typed_qty > 0:
            ln["quantity"] = typed_qty
        self._recalc(ln)
        self._update_row(idx)          # editor (if any) stays open
        self._show_unit_hint(idx)

    def _show_unit_hint(self, idx, extra=None):
        """Tiny transient badge next to the Unit cell — shows the active
        unit, its conversion, and the current rate. Auto-hides. This is
        the feedback that replaces the old modal unit-picker box."""
        try:
            if getattr(self, "_unit_popup", None) is not None:
                self._unit_popup.destroy()
        except Exception:
            pass
        self._unit_popup = None
        if idx >= len(self.lines):
            return
        ln = self.lines[idx]
        bbox = self._cell_bbox(idx, "unit")
        if not bbox:
            return
        x, y, w, h = bbox
        unit = ln.get("unit_of_measure_en", "") or "Unit"
        conv = ln.get("box_qty", "") or "1"
        try:
            rate = f"{float(ln.get('unit_price', 0)):,.2f}"
        except Exception:
            rate = "0.00"
        txt = f"  {unit}  ×{conv}  @ {rate}  "
        if extra:
            txt += f"·  {extra}  "
        tip = tk.Toplevel(self.tree)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        C = self.C
        lbl = tk.Label(tip, text=txt, font=("Segoe UI", 9, "bold"),
                       bg=C.get("primary", "#3A1FD6"), fg="white",
                       padx=4, pady=3)
        lbl.pack()
        rx = self.tree.winfo_rootx() + x
        ry = self.tree.winfo_rooty() + y + h + 2
        tip.geometry(f"+{rx}+{ry}")
        self._unit_popup = tip
        def _hide(t=tip):
            try:
                t.destroy()
            except Exception:
                pass
            if self._unit_popup is t:
                self._unit_popup = None
        tip.after(1100, _hide)

    def _on_delete(self, event):
        sel = self.tree.focus()
        if not sel:
            return
        idx = self._iid_idx(sel)
        if idx is not None and idx < len(self.lines) and self.lines[idx].get("product_id"):
            del self.lines[idx]
            if not any(l.get("_blank") and not l.get("product_id") for l in self.lines):
                self.add_blank_row()
            self._refresh()

    def _close_editor(self):
        if self._pad is not None:
            try:
                self._pad.destroy()
            except Exception:
                pass
            self._pad = None
        if getattr(self, "_unit_popup", None) is not None:
            try:
                self._unit_popup.destroy()
            except Exception:
                pass
            self._unit_popup = None
        if self._editor is not None:
            try:
                self._editor.destroy()
            except Exception:
                pass
        self._editor = None
        self._close_dropdown()

    def _close_dropdown(self):
        if self._dropdown is not None:
            try:
                self._dropdown.destroy()
            except Exception:
                pass
        self._dropdown = None
        self._dropdown_tv = None

    def focus_first_product(self):
        """Start on the first EMPTY row (a loaded invoice keeps its lines;
        typing must not replace line 1)."""
        def go():
            idx = next((i for i, l in enumerate(self.lines)
                        if l.get("_blank") and not l.get("product_id")), None)
            if idx is None:
                self.add_blank_row()
                idx = len(self.lines) - 1
            self._edit_barcode(idx)
        self.after(60, go)

    def focus_barcode(self):
        """F6 - jump to the barcode cell of the first empty row to scan."""
        idx = next((i for i, l in enumerate(self.lines)
                    if l.get("_blank") and not l.get("product_id")), None)
        if idx is None:
            self.add_blank_row()
            idx = len(self.lines) - 1
        self.after(20, lambda: self._edit_barcode(idx))
