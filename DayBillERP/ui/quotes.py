# ============================================================
# DayBill ERP - Sales Quotations & Purchase Orders
# ------------------------------------------------------------
# Quotation      : price offer to a customer → convert to Sales Invoice
# Purchase Order : order to a supplier        → convert to Purchase Invoice
# Neither moves stock nor posts to accounts; the invoice made from
# them does. One form + one list serve both (CONF below).
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from ui import close_guard

CONF = {
    "quotation": {
        "title": "Sales Quotation", "plural": "Quotations", "icon": "📝",
        "prefix": "QT", "table": "quotations", "lines": "quotation_lines",
        "id": "quote_id", "number": "quote_number", "date": "quote_date",
        "date2": "valid_until", "date2_label": "Valid Until", "days2": 15,
        "party": "customer", "party_label": "Customer",
        "party_id": "customer_id", "party_name": "customer_name_en",
        "party_name_ar": "customer_name_ar", "party_vat": "customer_vat_no",
        "perm": "quotation", "grid_doc": "sales",
        "tax_key": "sales_price_tax_mode", "tax_default": "inclusive",
        "convert": "Sales Invoice", "done": "converted",
        "conv_col": "converted_invoice_id",
        "statuses": ["open", "sent", "accepted", "cancelled"],
        "pdf": "quotation",
    },
    "purchase_order": {
        "title": "Purchase Order", "plural": "Purchase Orders", "icon": "📋",
        "prefix": "PO", "table": "purchase_orders", "lines": "purchase_order_lines",
        "id": "po_id", "number": "po_number", "date": "po_date",
        "date2": "expected_date", "date2_label": "Expected Delivery", "days2": 7,
        "party": "supplier", "party_label": "Supplier",
        "party_id": "supplier_id", "party_name": "supplier_name_en",
        "party_name_ar": "supplier_name_ar", "party_vat": "supplier_vat_no",
        "perm": "purchase_order", "grid_doc": "purchase",
        "tax_key": "purchase_cost_tax_mode", "tax_default": "exclusive",
        "convert": "Purchase Invoice", "done": "received",
        "conv_col": "converted_purchase_id",
        "statuses": ["open", "sent", "cancelled"],
        "pdf": "purchase_order",
    },
}

STATUS_ICON = {"open": "📝", "sent": "📤", "accepted": "👍", "converted": "✅",
               "received": "📦", "cancelled": "❌"}


def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _allowed(kind, action):
    try:
        from modules import permissions as _pm
        return _pm.allowed(CONF[kind]["perm"], action)
    except Exception:
        return True


def _iso(v):
    if v is None or v == "":
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v)[:10]


def load_doc(kind, doc_id):
    k = CONF[kind]
    h = db.fetchone(f"SELECT * FROM {k['table']} WHERE {k['id']}=?", (doc_id,))
    lines = db.fetchall(f"SELECT * FROM {k['lines']} WHERE {k['id']}=? "
                        f"ORDER BY line_number", (doc_id,)) or []
    return h, [dict(x) for x in lines]


def make_pdf(kind, doc_id, path=None):
    """Printable A4 PDF of a quotation / purchase order (the ★ default
    Invoice-Designer template when there is one). Returns the path."""
    import shutil
    from modules import doc_print as DP
    doc = DP.load(kind, doc_id)
    if not doc:
        raise ValueError("Document not found")
    made = DP.render_pdf(doc, folder=tempfile.gettempdir())
    if path and os.path.abspath(path) != os.path.abspath(made):
        shutil.copyfile(made, path)
        return path
    return made


# ════════════════════════════════════════════════════════════
#  FORM
# ════════════════════════════════════════════════════════════
class DocForm:
    def __init__(self, parent, kind="quotation", doc_id=None, on_save=None):
        self.kind = kind
        self.k = CONF[kind]
        self.doc_id = doc_id
        self.on_save = on_save
        self.parent = parent
        self._lines = []
        self._load_lookups()
        self._build_window()
        if doc_id:
            self._load()
        else:
            self._set_defaults()

    # ── lookups ───────────────────────────────────────────────
    def _load_lookups(self):
        # a purchase order is priced at COST (like the Purchase form); a
        # quotation at the selling price (v6.0 fix: POs showed selling prices)
        price_col = ("ISNULL(NULLIF(p.purchase_price,0), p.unit_price)"
                     if self.k["party"] == "supplier" else "p.unit_price")
        try:
            self._products = db.fetchall(
                "SELECT p.product_id, p.product_code, p.product_name_en, "
                "p.product_name_ar, " + price_col + " AS unit_price, p.unit_of_measure_en, "
                "p.vat_category_id, ISNULL(p.alias_name,'') AS alias_name, "
                "ISNULL(p.purchase_price,0) AS purchase_price, "
                "ISNULL(p.stock_quantity,0) AS stock_quantity, "
                "ISNULL(p.barcode,'') AS barcode, "
                "vc.category_code AS vat_code, vc.vat_rate "
                "FROM products p LEFT JOIN vat_categories vc "
                "ON p.vat_category_id=vc.vat_category_id "
                "WHERE p.is_active=1 ORDER BY p.product_name_en") or []
        except Exception:
            self._products = []
        self._units = {}
        try:
            for u in db.fetchall("SELECT * FROM product_units WHERE is_active=1") or []:
                self._units.setdefault(u["product_id"], []).append(u)
        except Exception:
            pass
        try:
            if self.k["party"] == "customer":
                self._parties = db.fetchall(
                    "SELECT customer_id AS id, customer_code AS code, customer_name_en AS name, "
                    "ISNULL(customer_name_ar,'') AS name_ar, "
                    "ISNULL(vat_registration_no,'') AS vat, ISNULL(phone,'') AS phone "
                    "FROM customers WHERE is_active=1 ORDER BY customer_name_en") or []
            else:
                self._parties = db.fetchall(
                    "SELECT supplier_id AS id, supplier_code AS code, supplier_name_en AS name, "
                    "ISNULL(supplier_name_ar,'') AS name_ar, "
                    "ISNULL(vat_registration_no,'') AS vat, ISNULL(phone,'') AS phone "
                    "FROM suppliers WHERE is_active=1 ORDER BY supplier_name_en") or []
        except Exception:
            self._parties = []
        self._party_opts = [f"{p['code']} — {p['name']}" for p in self._parties]

    # ── window ────────────────────────────────────────────────
    def _build_window(self):
        C = self.C = cfg.theme()
        k = self.k
        self.win = tk.Toplevel()
        self.win._doc_window = True     # item grid: may fill the screen
        self.win._form = self           # v6.7: compact header (ui/compact.py)
        self.win.title(k["title"])
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = min(1280, int(sw * 0.88)), min(800, int(sh * 0.9))
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        self.win.minsize(980, 600)
        self.win.configure(bg=C["content_bg"])
        close_guard.bind_escape(self.win)     # Esc = ✕ (asks if lines are unsaved)
        self.win.bind("<F9>", lambda e: self._save())
        self.win.bind("<Control-s>", lambda e: self._save())
        self.win.bind("<Control-p>", lambda e: self._print())
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        hdr = tk.Frame(self.win, bg=C["primary"], height=42)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        self.title_var = tk.StringVar(value=f"{k['icon']}  New {k['title']}")
        tk.Label(hdr, textvariable=self.title_var, font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)
        self.status_badge = tk.StringVar()
        tk.Label(hdr, textvariable=self.status_badge, font=("Segoe UI", 10, "bold"),
                 bg=C["primary"], fg="white").pack(side="right", padx=16)

        form = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        form.pack(fill="x")
        self.form_body = form
        g = tk.Frame(form, bg=C["card_bg"]); g.pack(fill="x", padx=12, pady=(4, 5))

        def lbl(r, c, t):                     # v6.9: two slim rows (was three)
            tk.Label(g, text=t, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=c, sticky="w",
                                                   padx=(0 if c == 0 else 14, 4), pady=2)

        self.v = {x: tk.StringVar() for x in ("number", "date", "date2", "status",
                                              "party", "ref", "notes")}
        lbl(0, 0, "Number")
        nf = tk.Frame(g, bg=C["card_bg"]); nf.grid(row=0, column=1, sticky="w")
        tk.Entry(nf, textvariable=self.v["number"], width=20, font=("Segoe UI", 10),
                 relief="solid", bd=1, state="readonly").pack(side="left", ipady=1)
        for txt, cmd in (("▲", self._prev), ("▼", self._next)):
            tk.Button(nf, text=txt, font=("Segoe UI", 7), width=2, relief="flat",
                      bg=C["content_bg"], cursor="hand2", command=cmd).pack(side="left", padx=(2, 0))
        lbl(0, 2, "Date *")
        self._date_entry(g, self.v["date"]).grid(row=0, column=3, sticky="w")
        lbl(0, 4, k["date2_label"])
        self._date_entry(g, self.v["date2"]).grid(row=0, column=5, sticky="w")

        lbl(1, 0, k["party_label"] + " *")
        self.party_cb = ttk.Combobox(g, textvariable=self.v["party"], width=40,
                                     values=self._party_opts, font=("Segoe UI", 10))
        self.party_cb.grid(row=1, column=1, sticky="w", pady=2)
        self.party_cb.bind("<KeyRelease>", self._filter_party)
        lbl(1, 2, "Reference")
        tk.Entry(g, textvariable=self.v["ref"], width=16, font=("Segoe UI", 10),
                 relief="solid", bd=1).grid(row=1, column=3, sticky="w", ipady=1)
        lbl(0, 6, "Status")
        self.status_cb = ttk.Combobox(g, textvariable=self.v["status"], width=12,
                                      values=k["statuses"], state="readonly",
                                      font=("Segoe UI", 10))
        self.status_cb.grid(row=0, column=7, sticky="w")
        lbl(1, 4, "Notes / Terms")
        tk.Entry(g, textvariable=self.v["notes"], width=40, font=("Segoe UI", 10),
                 relief="solid", bd=1).grid(row=1, column=5, columnspan=3, sticky="ew",
                                           pady=2, ipady=1)
        g.columnconfigure(5, weight=1)

        items = tk.Frame(self.win, bg=C["content_bg"])      # packed last (v6.9)
        from ui.invoice_grid import InvoiceGrid
        self.grid = InvoiceGrid(items, C, self._products, self._units,
                                on_change=self._on_change,
                                tax_mode=cfg.get(k["tax_key"], k["tax_default"]),
                                doc_type=k["grid_doc"], last_kind=None)
        self.grid.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        footer = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                          highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        fi = tk.Frame(footer, bg=C["card_bg"]); fi.pack(fill="x", padx=10, pady=3)
        self.msg = tk.StringVar()
        tk.Label(fi, textvariable=self.msg, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["danger"]).pack(side="left")
        tk.Button(fi, text="Close", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=3, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: close_guard.request_close(self.win)).pack(side="right", padx=(8, 0))
        self.btn_convert = tk.Button(
            fi, text=f"➡  Make {k['convert']}", font=("Segoe UI", 10, "bold"),
            bg=C["success"], fg="white", relief="flat", padx=14, pady=3, cursor="hand2",
            command=self.convert)
        self.btn_convert.pack(side="right", padx=(8, 0))
        self.btn_wa = tk.Button(fi, text="🟢  WhatsApp", font=("Segoe UI", 10),
                                bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                                padx=12, pady=3, cursor="hand2",
                                highlightbackground=C["border"], highlightthickness=1,
                                command=self._whatsapp)
        self.btn_wa.pack(side="right", padx=(8, 0))
        from ui import print_menu
        from ui.ui_kit import slim_key_style as key_style        # v6.9: one-line buttons
        _ps = key_style(C.get("tile_purple", C["info"]), "Ctrl+P ▾", "Print")
        _pt = _ps.pop("text")
        print_menu.print_button(fi, self.kind, lambda: self.doc_id,
                                before=self._ensure_saved, status=self.msg,
                                text=_pt, **_ps).pack(side="right", padx=(8, 0))
        self.btn_save = tk.Button(fi, command=self._save,
                                  **key_style(C.get("tile_blue", C["primary"]), "F9", "Save"))
        self.btn_save.pack(side="right")
        if self.kind == "purchase_order":       # v6.0: what to order (low stock)
            tk.Button(fi, text="💡 Suggest (low stock)", font=("Segoe UI", 10), bg=C["card_bg"],
                      relief="flat", padx=12, pady=3, cursor="hand2", highlightthickness=1,
                      highlightbackground=C["border"], command=self._suggest).pack(side="right", padx=(0, 8))

        tot = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        tot.pack(fill="x", side="bottom")
        from ui.ui_kit import total_strip               # v6.9: totals on one slim line
        self.tv = total_strip(tot, [("Items", "count", None), ("Qty", "qty", None),
                                    ("Taxable", "taxable", None), ("VAT", "vat", C["info"])],
                              ("TOTAL (SAR)", "total"), C)
        items.pack(side="top", fill="both", expand=True)
        self._on_change()
        try:
            self.grid.focus_first_product()
        except Exception:
            pass

    def _suggest(self):
        """Fill the order with the products at / below their reorder level
        (only the chosen supplier's products when a supplier is picked)."""
        from modules import purchase_suggest as PS
        try:
            party = self._party()
            sid = party.get("id") if party else None
        except Exception:
            sid = None
        rows = PS.suggest(sid)
        if not rows:
            self.msg.set("Nothing is below its reorder level%s." % (" for this supplier" if sid else ""))
            return 0
        have = {l.get("product_id") for l in self.grid.data_lines()}
        n = 0
        for r in rows:
            if r["product_id"] in have:
                continue
            p = next((x for x in self._products if x.get("product_id") == r["product_id"]), None)
            if not p:
                continue
            idx = next((i for i, l in enumerate(self.grid.lines) if not l.get("product_id")), None)
            if idx is None:
                self.grid.add_blank_row()
                idx = len(self.grid.lines) - 1
            self.grid._apply_product(idx, p, merge=False)
            ln = self.grid.lines[idx]
            ln["quantity"] = float(r["qty"])
            self.grid._recalc(ln)
            n += 1
        self.grid._refresh()
        self._on_change()
        self.msg.set("💡 %d product(s) added from low stock — check the quantities." % n)
        return n

    def _date_entry(self, parent, var):
        e = tk.Entry(parent, textvariable=var, width=12, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(e, var)
        except Exception:
            pass
        return e

    def _filter_party(self, e=None):
        if e is not None and getattr(e, "keysym", "") in ("Return", "Tab", "Down", "Up"):
            return
        q = self.v["party"].get().strip().lower()
        self.party_cb["values"] = ([o for o in self._party_opts if q in o.lower()]
                                   if q else self._party_opts)[:300]

    # ── state ─────────────────────────────────────────────────
    def _on_change(self):
        try:
            self._lines = self.grid.data_lines()
        except Exception:
            self._lines = []
        L = self._lines
        if not hasattr(self, "tv"):
            return
        self.tv["count"].set(str(len(L)))
        self.tv["qty"].set(f"{sum(_f(x.get('quantity')) for x in L):g}")
        from modules.doc_math import doc_totals
        T = doc_totals(L, (getattr(getattr(self, "grid", None), "tax_mode", "exclusive") == "inclusive"))          # v6.9.2: VAT once per rate
        self.tv["taxable"].set(f"{T['taxable']:,.2f}")
        self.tv["vat"].set(f"{T['vat']:,.2f}")
        self.tv["total"].set(f"{T['total']:,.2f}")

    def _next_number(self):
        try:
            from modules.doc_numbering import next_number
            return next_number(self.k["table"], self.k["number"], self.k["prefix"])
        except Exception:
            return f"{self.k['prefix']}-{date.today():%Y%m}-000001"

    def _set_defaults(self):
        self.v["number"].set(self._next_number())
        self.v["date"].set(date.today().isoformat())
        self.v["date2"].set((date.today() + timedelta(days=self.k["days2"])).isoformat())
        self.v["status"].set("open")
        self.title_var.set(f"{self.k['icon']}  New {self.k['title']}")
        self.status_badge.set("")
        self._lock(False)

    def _lock(self, locked):
        st = "disabled" if locked else "normal"
        try:
            self.btn_save.config(state=st)
            self.btn_convert.config(state=st)
        except Exception:
            pass

    def _load(self):
        k = self.k
        h, lines = load_doc(self.kind, self.doc_id)
        if not h:
            return
        self.v["number"].set(h[k["number"]])
        self.v["date"].set(_iso(h.get(k["date"])))
        self.v["date2"].set(_iso(h.get(k["date2"])))
        self.v["ref"].set(h.get("reference") or "")
        self.v["notes"].set(h.get("notes_en") or "")
        st = (h.get("status") or "open").lower()
        self.v["status"].set(st)
        pid = h.get(k["party_id"])
        p = next((x for x in self._parties if x["id"] == pid), None)
        self.v["party"].set(f"{p['code']} — {p['name']}" if p else (h.get(k["party_name"]) or ""))
        self.grid.set_lines(lines)
        self._on_change()
        self._mark_clean()
        self.title_var.set(f"{k['icon']}  {k['title']}  {h[k['number']]}")
        done = st in (k["done"], "cancelled")
        self.status_badge.set(f"{STATUS_ICON.get(st, '')} {st.title()}")
        self._lock(done)
        if done:
            self.msg.set(f"This {k['title'].lower()} is {st} — view only.")
        else:
            self.msg.set("")

    def _goto(self, doc_id):
        self.doc_id = doc_id
        self.grid.set_lines([])
        self._load()

    def _prev(self):
        k = self.k
        if self.doc_id:
            r = db.fetchone(f"SELECT TOP 1 {k['id']} AS i FROM {k['table']} WHERE {k['id']}<? "
                            f"ORDER BY {k['id']} DESC", (self.doc_id,))
        else:
            r = db.fetchone(f"SELECT TOP 1 {k['id']} AS i FROM {k['table']} ORDER BY {k['id']} DESC")
        if r:
            self._goto(r["i"])

    def _next(self):
        k = self.k
        if not self.doc_id:
            return
        r = db.fetchone(f"SELECT TOP 1 {k['id']} AS i FROM {k['table']} WHERE {k['id']}>? "
                        f"ORDER BY {k['id']} ASC", (self.doc_id,))
        if r:
            self._goto(r["i"])
        else:
            self.doc_id = None
            self.grid.set_lines([])
            self._set_defaults()
            self.v["party"].set(""); self.v["ref"].set(""); self.v["notes"].set("")
            self._on_change()

    # ── save ──────────────────────────────────────────────────
    def _party(self):
        code = self.v["party"].get().split(" — ")[0].strip()
        return next((p for p in self._parties if p["code"] == code), None)

    def _save(self, quiet=False):
        k = self.k
        if not _allowed(self.kind, "edit" if self.doc_id else "add"):
            return False
        if str(self.btn_save.cget("state")) == "disabled":
            return False
        self._on_change()
        if not self._lines:
            self.msg.set("⚠️  Add at least one item.")
            return False
        party = self._party()
        if not party:
            self.msg.set(f"⚠️  Select a {k['party_label'].lower()}.")
            return False
        from modules.date_utils import validate_invoice_date
        ok, d1, err = validate_invoice_date(self.v["date"].get())
        if not ok:
            self.msg.set("⚠️  " + err)
            return False
        d2 = self.v["date2"].get().strip() or None
        if d2:
            ok2, d2, err2 = validate_invoice_date(d2)
            if not ok2:
                self.msg.set(f"⚠️  {k['date2_label']}: {err2}")
                return False
        from modules.doc_math import doc_totals, round_lines
        L = self._lines = round_lines(self._lines)
        T = doc_totals(L, (getattr(getattr(self, "grid", None), "tax_mode", "exclusive") == "inclusive"))          # v6.9.2: the ZATCA way
        taxable, vat, total = T["taxable"], T["vat"], T["total"]
        disc = round(sum(_f(x.get("discount_amount")) for x in L), 2)
        status = self.v["status"].get() or "open"
        _tx, _was = None, self.doc_id
        try:
            _tx = db.begin()              # header + lines together (v5.27)
            if self.doc_id:
                db.execute(
                    f"UPDATE {k['table']} SET {k['date']}=?, {k['date2']}=?, {k['party_id']}=?, "
                    f"{k['party_name']}=?, {k['party_name_ar']}=?, {k['party_vat']}=?, "
                    f"reference=?, subtotal_amount=?, discount_amount=?, taxable_amount=?, "
                    f"vat_amount=?, total_amount=?, status=?, notes_en=?, updated_at=GETDATE() "
                    f"WHERE {k['id']}=?",
                    (d1, d2, party["id"], party["name"], party.get("name_ar", ""),
                     party.get("vat", ""), self.v["ref"].get() or None, taxable, disc,
                     taxable, vat, total, status, self.v["notes"].get() or None, self.doc_id))
                db.execute(f"DELETE FROM {k['lines']} WHERE {k['id']}=?", (self.doc_id,))
            else:
                num = self.v["number"].get() or self._next_number()
                if db.execute_scalar(f"SELECT COUNT(*) FROM {k['table']} WHERE {k['number']}=?",
                                     (num,)):
                    num = self._next_number()
                    self.v["number"].set(num)
                try:
                    from modules import permissions as _p
                    uid = (_p.session_user() or {}).get("user_id")
                except Exception:
                    uid = None
                db.execute(
                    f"INSERT INTO {k['table']} ({k['number']}, {k['date']}, {k['date2']}, "
                    f"{k['party_id']}, {k['party_name']}, {k['party_name_ar']}, {k['party_vat']}, "
                    f"reference, subtotal_amount, discount_amount, taxable_amount, vat_amount, "
                    f"total_amount, status, notes_en, created_by) "
                    f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (num, d1, d2, party["id"], party["name"], party.get("name_ar", ""),
                     party.get("vat", ""), self.v["ref"].get() or None, taxable, disc,
                     taxable, vat, total, status, self.v["notes"].get() or None, uid))
                self.doc_id = db.execute_scalar(
                    f"SELECT {k['id']} FROM {k['table']} WHERE {k['number']}=?", (num,))
            for i, ln in enumerate(L, 1):
                db.execute(
                    f"INSERT INTO {k['lines']} ({k['id']}, line_number, product_id, "
                    f"product_code, product_name_en, product_name_ar, quantity, "
                    f"unit_of_measure_en, unit_price, discount_amount, line_amount, "
                    f"vat_category_id, vat_category_code, vat_rate, vat_amount, line_total) "
                    f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (self.doc_id, i, ln.get("product_id"), ln.get("product_code", ""),
                     ln.get("product_name_en", ""), ln.get("product_name_ar", ""),
                     ln.get("quantity", 1), ln.get("unit_of_measure_en", "Unit"),
                     ln.get("unit_price", 0), ln.get("discount_amount", 0),
                     ln.get("line_amount", 0), ln.get("vat_category_id"),
                     ln.get("vat_category_code", "S"), ln.get("vat_rate", 15),
                     ln.get("vat_amount", 0), ln.get("line_total", 0)))
            try:
                from modules import audit
                audit.log("save", self.kind, self.doc_id,
                          f"{self.v['number'].get()} {total:,.2f}")
            except Exception:
                pass
            _tx.commit()
            self._mark_clean()            # close guard: nothing unsaved now
            self.title_var.set(f"{k['icon']}  {k['title']}  {self.v['number'].get()}")
            self.status_badge.set(f"{STATUS_ICON.get(status, '')} {status.title()}")
            self.msg.set(f"✔ Saved {self.v['number'].get()}  ·  {total:,.2f} SAR")
            if self.on_save:
                try:
                    self.on_save()
                except Exception:
                    pass
            return True
        except Exception as e:
            if _tx is not None and not _tx.kept:
                _tx.rollback()
                self.doc_id = _was
                e = "Not saved — " + str(e)
            self.msg.set(f"❌ {str(e)[:120]}")
            return False

    def _close(self):
        """✕ handler (asks first through ui/close_guard.py); Esc and the
        Close button go through close_guard.request_close."""
        try:
            self.win.destroy()
        except Exception:
            pass

    # ── close guard: ask only when lines are not saved ────────
    def _lines_sig(self):
        try:
            return close_guard.lines_sig(self.grid.data_lines())
        except Exception:
            return ()

    def _mark_clean(self):
        """The grid now matches the saved / loaded document."""
        self._clean_sig = self._lines_sig()

    def _is_dirty(self):
        """✕ / Esc / Close ask first only while the grid has lines that
        are not saved: a new document, or lines changed since load / save.
        A converted / cancelled one (Save greyed out) never asks."""
        try:
            if str(self.btn_save.cget("state")) == "disabled":
                return False
        except Exception:
            pass
        sig = self._lines_sig()
        if not sig:
            return False
        return not self.doc_id or sig != getattr(self, "_clean_sig", None)

    # ── print / whatsapp / convert ────────────────────────────
    def _ensure_saved(self):
        if str(self.btn_save.cget("state")) == "disabled":
            return bool(self.doc_id)
        return self._save()

    def _print(self, option="default"):
        if not self._ensure_saved():
            return
        from ui import print_menu
        print_menu.run(self.win, self.kind, self.doc_id, option, status=self.msg)

    def _whatsapp(self):
        if not self._ensure_saved():
            return
        try:
            from ui.whatsapp_send import send_document
            send_document(self.win, self.kind, self.doc_id)
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:300], parent=self.win)

    def convert(self):
        if not self._ensure_saved():
            return
        open_conversion(self.win, self.kind, self.doc_id, self.on_save)
        self._close()


def open_conversion(parent, kind, doc_id, after=None):
    """Open a new Sales / Purchase Invoice filled from the quotation /
    PO. When that invoice is saved, the source is marked converted."""
    k = CONF[kind]
    h, lines = load_doc(kind, doc_id)
    if not h:
        return None
    st = (h.get("status") or "").lower()
    if st in (k["done"], "cancelled"):
        messagebox.showinfo(k["title"], f"This {k['title'].lower()} is already {st}.",
                            parent=parent)
        return None
    holder = {}

    def mark_done():
        form = holder.get("form")
        new_id = getattr(form, "invoice_id", None) or getattr(form, "purchase_id", None)
        if not new_id:
            return
        try:
            db.execute(f"UPDATE {k['table']} SET status=?, {k['conv_col']}=?, "
                       f"updated_at=GETDATE() WHERE {k['id']}=?", (k["done"], new_id, doc_id))
        except Exception:
            pass
        if after:
            try:
                after()
            except Exception:
                pass

    if kind == "quotation":
        from modules import permissions as _pm
        if not _pm.allowed("sales", "add"):
            return None
        from ui.invoices import InvoiceForm
        form = InvoiceForm(parent, on_save=mark_done)
        holder["form"] = form
        try:
            cust = next((c for c in form._customers
                         if c["customer_id"] == h.get("customer_id")), None)
            if cust:
                form.cust_combo.set(f"{cust['customer_code']} — {cust['customer_name_en']}")
                form._on_customer_select()
            form.line_grid.set_lines(lines)
            form._lines = form.line_grid.data_lines()
            note = f"From quotation {h['quote_number']}"
            form.hdr_vars["notes_en"].set(
                (h.get("notes_en") + " · " if h.get("notes_en") else "") + note)
            form._update_totals()
        except Exception:
            pass
        return form
    from modules import permissions as _pm
    if not _pm.allowed("purchase", "add"):
        return None
    from ui.purchases import PurchaseForm
    form = PurchaseForm(parent, None, mark_done)
    holder["form"] = form
    try:
        s = next((x for x in form.suppliers if x["supplier_id"] == h.get("supplier_id")), None)
        if s:
            form.sup_cb.set(f"{s['supplier_code']} — {s['supplier_name_en']}")
        form.grid.set_lines(lines)
        form.hdr["supinv"].set(h.get("reference") or "")
        form._on_change()
    except Exception:
        pass
    return form


# ════════════════════════════════════════════════════════════
#  LIST
# ════════════════════════════════════════════════════════════
class _DocListView:
    kind = "quotation"

    def __init__(self, parent):
        self.k = CONF[self.kind]
        C = self.C = cfg.theme()
        self.parent = parent
        self._rows = []
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        k = self.k
        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(top, text=f"{k['icon']}  {k['plural']}", font=("Segoe UI", 17, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(top, text=f"＋  New {k['title']}", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=7,
                  cursor="hand2", command=self._new).pack(side="right")

        bar = tk.Frame(self.frame, bg=C["content_bg"]); bar.pack(fill="x", padx=20, pady=(4, 6))
        self.q = tk.StringVar()
        e = tk.Entry(bar, textvariable=self.q, width=30, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        e.pack(side="left", ipady=4)
        tk.Label(bar, text="🔍 number / name", font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(4, 16))
        self.q.trace_add("write", lambda *a: self._fill())
        self.st = tk.StringVar(value="All")
        sts = ["All"] + k["statuses"] + [k["done"]]
        ttk.Combobox(bar, textvariable=self.st, values=sts, width=12, state="readonly",
                     font=("Segoe UI", 9)).pack(side="left")
        self.st.trace_add("write", lambda *a: self._fill())
        self.count = tk.StringVar()
        tk.Label(bar, textvariable=self.count, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="right")

        wrap = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        cols = [("number", "Number", 165, "w"), ("date", "Date", 100, "center"),
                ("date2", k["date2_label"], 135, "center"),
                ("party", k["party_label"], 240, "w"), ("total", "Total (SAR)", 120, "e"),
                ("status", "Status", 115, "center"), ("conv", "Converted to", 160, "center")]
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings",
                                 selectmode="browse")
        for key, head, w, a in cols:
            self.tree.heading(key, text=head, anchor="e" if a == "e" else "w" if a == "w" else "center")
            self.tree.column(key, width=w, anchor=a, stretch=key == "party")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("cancelled", foreground="#9CA3AF")
        self.tree.tag_configure("done", foreground=C["success"])
        self.tree.bind("<Double-1>", lambda e: self._open())
        self.tree.bind("<Return>", lambda e: self._open())
        self.tree.bind("<Delete>", lambda e: self._delete())

        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label="✏  Open / Edit", command=self._open)
        menu.add_command(label=f"➡  Make {k['convert']}", command=self._convert)
        menu.add_command(label="🖨  Print", command=self._print)
        menu.add_command(label="🟢  Send on WhatsApp", command=self._whatsapp)
        menu.add_separator()
        menu.add_command(label="❌  Cancel", command=self._cancel)
        menu.add_command(label="🗑  Delete", command=self._delete)

        def popup(e):
            row = self.tree.identify_row(e.y)
            if row:
                self.tree.selection_set(row); self.tree.focus(row)
                menu.tk_popup(e.x_root, e.y_root)
        self.tree.bind("<Button-3>", popup)

        bb = tk.Frame(self.frame, bg=C["content_bg"]); bb.pack(fill="x", padx=20, pady=(0, 14))
        for txt, cmd, bg, fg in (("✏  Open", self._open, C["card_bg"], C["text_primary"]),
                                 (f"➡  Make {k['convert']}", self._convert, C["success"], "white"),
                                 ("🖨  Print ▾", self._print, C["card_bg"], C["text_primary"]),
                                 ("🟢  WhatsApp", self._whatsapp, C["card_bg"], C["text_primary"]),
                                 ("📥  Export", self._export, C["card_bg"], C["text_primary"]),
                                 ("❌  Cancel", self._cancel, "#FEF2F2", C["danger"]),
                                 ("🗑  Delete", self._delete, "#FEF2F2", C["danger"])):
            tk.Button(bb, text=txt, font=("Segoe UI", 9), bg=bg, fg=fg, relief="flat",
                      padx=12, pady=3, cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1 if bg == C["card_bg"] else 0,
                      command=cmd).pack(side="left", padx=(0, 6))
        tk.Button(bb, text="🔄  Refresh", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=12, pady=3, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.load).pack(side="right")
        if self.kind == "purchase_order":       # v6.4: goods came → scan them against the order
            tk.Button(bb, text="📦  Receive (scan)", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                      fg="white", relief="flat", padx=12, pady=3, cursor="hand2",
                      command=self._receive).pack(side="right", padx=6)
            menu.insert_command(2, label="📦  Receive (scan)", command=self._receive)
        self.load()

    def _receive(self):
        i = self._sel()
        if not i:
            return None
        k = self.k
        r = next((x for x in self._rows if x[k["id"]] == i), {})
        if (r.get("status") or "") in (k["done"], "cancelled"):
            messagebox.showinfo(k["title"], "Already " + (r.get("status") or "") + ".")
            return None
        from ui.po_receive import ReceiveDialog
        self._recv = ReceiveDialog(self.frame, i, on_done=self.load)
        return self._recv

    def load(self):
        k = self.k
        try:
            self._rows = db.fetchall(f"SELECT * FROM {k['table']} ORDER BY {k['id']} DESC") or []
        except Exception as e:
            self._rows = []
            self.count.set("⚠ " + str(e)[:80] + " — restart DayBill to install the tables.")
        self._inv_numbers = {}
        try:
            if self.kind == "quotation":
                ids = [r[k["conv_col"]] for r in self._rows if r.get(k["conv_col"])]
                for i in ids:
                    n = db.execute_scalar("SELECT invoice_number FROM sales_invoices WHERE invoice_id=?", (i,))
                    self._inv_numbers[i] = n
            else:
                ids = [r[k["conv_col"]] for r in self._rows if r.get(k["conv_col"])]
                for i in ids:
                    n = db.execute_scalar("SELECT invoice_number FROM purchase_invoices WHERE purchase_id=?", (i,))
                    self._inv_numbers[i] = n
        except Exception:
            pass
        self._fill()

    def _fill(self):
        k = self.k
        q = self.q.get().strip().lower()
        st = self.st.get()
        self.tree.delete(*self.tree.get_children())
        n = 0
        today = date.today().isoformat()
        for r in self._rows:
            s = (r.get("status") or "open").lower()
            if st != "All" and s != st:
                continue
            if q and q not in (str(r.get(k["number"])) + " " + str(r.get(k["party_name"]) or "")).lower():
                continue
            d2 = _iso(r.get(k["date2"]))
            exp = ""
            if self.kind == "quotation" and d2 and d2 < today and s in ("open", "sent", "accepted"):
                exp = "  (expired)"
            conv = self._inv_numbers.get(r.get(k["conv_col"])) or ""
            self.tree.insert("", "end", iid=str(r[k["id"]]), values=(
                r[k["number"]], _iso(r.get(k["date"])), d2 + exp,
                r.get(k["party_name"]) or "", f"{_f(r.get('total_amount')):,.2f}",
                f"{STATUS_ICON.get(s, '')} {s.title()}", conv),
                tags=("cancelled",) if s == "cancelled" else (("done",) if s == k["done"] else ()))
            n += 1
        self.count.set(f"{n} {k['plural'].lower()}")

    def _sel(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", f"Select a {self.k['title'].lower()} first.")
            return None
        return int(s[0])

    def _new(self):
        if _allowed(self.kind, "add"):
            DocForm(self.parent, self.kind, on_save=self.load)

    def _open(self):
        i = self._sel()
        if i:
            DocForm(self.parent, self.kind, i, on_save=self.load)

    def _convert(self):
        i = self._sel()
        if i:
            open_conversion(self.frame, self.kind, i, self.load)

    def _print(self, widget=None):
        from ui import print_menu
        print_menu.show_menu(self.frame, self.kind,
                             lambda: int(self.tree.selection()[0]) if self.tree.selection() else None,
                             widget=widget)

    def _whatsapp(self):
        i = self._sel()
        if not i:
            return
        try:
            from ui.whatsapp_send import send_document
            send_document(self.frame, self.kind, i)
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:300])

    def _cancel(self):
        i = self._sel()
        if not i or not _allowed(self.kind, "edit"):
            return
        k = self.k
        r = next((x for x in self._rows if x[k["id"]] == i), {})
        if (r.get("status") or "") in (k["done"], "cancelled"):
            messagebox.showinfo(k["title"], "Already " + (r.get("status") or "") + ".")
            return
        if messagebox.askyesno(k["title"], f"Cancel {r.get(k['number'])}?"):
            db.execute(f"UPDATE {k['table']} SET status='cancelled', updated_at=GETDATE() "
                       f"WHERE {k['id']}=?", (i,))
            self.load()

    def _delete(self):
        i = self._sel()
        if not i or not _allowed(self.kind, "delete"):
            return
        k = self.k
        r = next((x for x in self._rows if x[k["id"]] == i), {})
        if messagebox.askyesno(k["title"], f"Delete {r.get(k['number'])}? This cannot be undone."):
            try:
                db.execute(f"DELETE FROM {k['lines']} WHERE {k['id']}=?", (i,))
                db.execute(f"DELETE FROM {k['table']} WHERE {k['id']}=?", (i,))
                try:
                    from modules.doc_actions import audit
                    audit("delete", self.kind, i, str(r.get(k["number"])))
                except Exception:
                    pass
                self.load()
            except Exception as e:
                messagebox.showerror("Delete", str(e)[:300])

    def _export(self):
        if not _allowed(self.kind, "export"):
            return
        try:
            from modules.doc_actions import export_tree_excel
            export_tree_excel(self.frame, self.tree, self.k["plural"].replace(" ", "_"),
                              ["Number", "Date", self.k["date2_label"], self.k["party_label"],
                               "Total", "Status", "Converted to"], title=self.k["plural"])
        except Exception as e:
            messagebox.showerror("Export", str(e)[:300])


class QuotationsView(_DocListView):
    kind = "quotation"


class PurchaseOrdersView(_DocListView):
    kind = "purchase_order"
