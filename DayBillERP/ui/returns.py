# ============================================================
# DayBill ERP - Sales Return & Purchase Return
# One reusable ReturnForm (mode="sales"|"purchase") that mirrors
# the Sales Invoice layout: minimal header, big Polosys grid,
# bottom totals + payment, prev/next nav, find-by-number.
# Plus simple list views for each.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


CONF = {
    "sales": {
        "title": "Sales Return", "prefix": "SR",
        "table": "sales_returns", "lines": "sales_return_lines",
        "party": "customer", "party_id": "customer_id",
        "party_name": "customer_name_en", "ref_col": "original_invoice_no",
        "ref_label": "Original Invoice #", "src_table": "sales_invoices",
        "src_lines": "sales_invoice_lines", "stock_sign": +1, "src_id": "invoice_id",
    },
    "purchase": {
        "title": "Purchase Return", "prefix": "PR",
        "table": "purchase_returns", "lines": "purchase_return_lines",
        "party": "supplier", "party_id": "supplier_id",
        "party_name": "supplier_name_en", "ref_col": "original_purchase_no",
        "ref_label": "Original Purchase #", "src_table": "purchase_invoices",
        "src_lines": "purchase_invoice_lines", "stock_sign": -1, "src_id": "purchase_id",
    },
}


class ReturnForm:
    def __init__(self, parent, mode="sales", return_id=None, view_only=False):
        self.mode = mode
        self.cfg = CONF[mode]
        self.return_id = return_id
        self.view_only = view_only
        self._lines = []
        self._parties = []
        self._products = []
        self._product_units = {}
        self._load_lookups()
        self._build_window()
        if return_id:
            self._load_return()
        else:
            self._set_defaults()
        try:      # v6.9 connector bar: New · Edit · Save · Delete (user rights)
            from ui import txn_connector as _tc
            _tc.attach(self, f"{mode}_return")
        except Exception:
            pass

    # ── lookups ───────────────────────────────────────────────
    def _load_lookups(self):
        try:
            self._products = db.fetchall(
                "SELECT p.product_id, p.product_code, p.product_name_en, "
                "p.product_name_ar, p.unit_price, p.unit_of_measure_en, "
                "p.vat_category_id, ISNULL(p.alias_name,'') AS alias_name, "
                "ISNULL(p.purchase_price,0) AS purchase_price, "
                "ISNULL(p.stock_quantity,0) AS stock_quantity, "
                "ISNULL(p.barcode,'') AS barcode, "
                "vc.category_code AS vat_code, vc.vat_rate "
                "FROM products p LEFT JOIN vat_categories vc "
                "ON p.vat_category_id=vc.vat_category_id "
                "WHERE p.is_active=1 ORDER BY p.product_name_en") or []
            self._product_units = {}
            try:
                for u in db.fetchall("SELECT * FROM product_units WHERE is_active=1"):
                    self._product_units.setdefault(u["product_id"], []).append(u)
            except Exception:
                self._product_units = {}
        except Exception:
            self._products = []

        if self.mode == "sales":
            try:
                self._parties = db.fetchall(
                    "SELECT customer_id AS id, customer_code AS code, "
                    "customer_name_en AS name, customer_name_ar AS name_ar, "
                    "ISNULL(vat_registration_no,'') AS vat FROM customers "
                    "WHERE is_active=1 ORDER BY customer_name_en") or []
            except Exception:
                self._parties = []
        else:
            try:
                self._parties = db.fetchall(
                    "SELECT supplier_id AS id, supplier_code AS code, "
                    "supplier_name_en AS name, ISNULL(supplier_name_ar,'') AS name_ar, "
                    "ISNULL(vat_registration_no,'') AS vat FROM suppliers "
                    "WHERE is_active=1 ORDER BY supplier_name_en") or []
            except Exception:
                self._parties = []
        self._company = {}
        try:
            self._company = db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
        except Exception:
            self._company = {}

    # ── window ────────────────────────────────────────────────
    def _build_window(self):
        C = cfg.theme()
        self.win = tk.Toplevel()
        self.win._doc_window = True     # item grid: may fill the screen
        self.win._form = self           # v6.7: compact header (ui/compact.py)
        self.win.title(self.cfg["title"])
        w = min(1360, int(self.win.winfo_screenwidth() * 0.90))
        h = min(840, int(self.win.winfo_screenheight() * 0.92))
        self.win.geometry(f"{w}x{h}")
        self.win.configure(bg=C["content_bg"])
        self._center(w, h)
        if not self.view_only:
            self.win.bind("<F9>",  lambda e: self._save(confirm=False))
            self.win.bind("<F10>", lambda e: self._save(confirm=True))
            self.win.bind("<F6>",  lambda e: self._focus_barcode())
        self.win.bind("<Escape>", lambda e: self.win.destroy())

        hdr = tk.Frame(self.win, bg=C["primary"], height=40)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"↩  {self.cfg['title']}", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)

        self.form_body = tk.Frame(self.win, bg=C["card_bg"],
                                  highlightbackground=C["border"], highlightthickness=1)
        self.form_body.pack(side="top", fill="x")
        self.items_area = tk.Frame(self.win, bg=C["content_bg"])    # packed last (v6.9)

        self._build_header(C)
        self._build_grid(C)
        self._build_footer(C)
        self.bottom_bar = tk.Frame(self.win, bg=C["card_bg"],
                                   highlightbackground=C["border"], highlightthickness=1)
        self.bottom_bar.pack(side="bottom", fill="x")
        self._build_totals(C)
        self.items_area.pack(side="top", fill="both", expand=True)

    def _center(self, w, h):
        self.win.update_idletasks()
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{max(0, y-20)}")

    def _build_header(self, C):
        state = "disabled" if self.view_only else "normal"
        self.hdr = {}
        grid = tk.Frame(self.form_body, bg=C["card_bg"])
        grid.pack(fill="x", padx=12, pady=(4, 5))          # v6.9: tighter
        for i in range(4):
            grid.columnconfigure(i, weight=1, uniform="h")

        def cell(r, c, label):
            f = tk.Frame(grid, bg=C["card_bg"])
            f.grid(row=r, column=c, sticky="ew", padx=(0, 10), pady=(0, 6))
            tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
            return f

        # Return number + nav + find
        rc = cell(0, 0, "Return Number")
        line = tk.Frame(rc, bg=C["card_bg"]); line.pack(fill="x", pady=(2, 0))
        self.hdr["number"] = tk.StringVar()
        tk.Entry(line, textvariable=self.hdr["number"], font=("Segoe UI", 10),
                 relief="solid", bd=1, state="disabled").pack(
                     side="left", fill="x", expand=True, ipady=6)
        if not self.view_only:
            tk.Button(line, text="▲", font=("Segoe UI", 7), width=2,
                      bg=C["content_bg"], relief="flat", cursor="hand2",
                      command=self._nav_prev).pack(side="left", padx=(2, 0))
            tk.Button(line, text="▼", font=("Segoe UI", 7), width=2,
                      bg=C["content_bg"], relief="flat", cursor="hand2",
                      command=self._nav_next).pack(side="left")
            fl = tk.Frame(rc, bg=C["card_bg"]); fl.pack(fill="x", pady=(3, 0))
            self.find_on = tk.BooleanVar(value=False)
            tk.Checkbutton(fl, text="Find", variable=self.find_on,
                           font=("Segoe UI", 8), bg=C["card_bg"],
                           fg=C["text_secondary"], activebackground=C["card_bg"],
                           command=self._toggle_find).pack(side="left")
            self.find_var = tk.StringVar()
            self.find_entry = tk.Entry(fl, textvariable=self.find_var,
                                       font=("Segoe UI", 9), relief="solid", bd=1,
                                       state="disabled")
            self.find_entry.pack(side="left", padx=(4, 0), ipady=6, fill="x", expand=True)
            self.find_entry.bind("<Return>", lambda e: self._find())

        # Return date
        dc = cell(0, 1, "Return Date *")
        self.hdr["date"] = tk.StringVar()
        de = tk.Entry(dc, textvariable=self.hdr["date"], font=("Segoe UI", 10),
                      relief="solid", bd=1, state=state)
        de.pack(fill="x", ipady=6, pady=(2, 0))
        if state == "normal":
            try:
                from ui.datepicker import attach_datepicker
                attach_datepicker(de, self.hdr["date"])
            except Exception:
                pass

        # Original reference + Load button
        ref = cell(0, 2, self.cfg["ref_label"])
        rline = tk.Frame(ref, bg=C["card_bg"]); rline.pack(fill="x", pady=(2, 0))
        self.hdr["ref"] = tk.StringVar()
        tk.Entry(rline, textvariable=self.hdr["ref"], font=("Segoe UI", 10),
                 relief="solid", bd=1, state=state).pack(
                     side="left", fill="x", expand=True, ipady=6)
        if not self.view_only:
            tk.Button(rline, text="Load", font=("Segoe UI", 8, "bold"),
                      bg=C["primary"], fg="white", relief="flat", padx=8,
                      cursor="hand2", command=self._load_original).pack(
                          side="left", padx=(4, 0))

        # Payment type
        pc = cell(0, 3, "Payment Type")
        self.hdr["payment"] = tk.StringVar(value="cash")
        ttk.Combobox(pc, textvariable=self.hdr["payment"],
                     values=["cash", "credit", "card", "bank_transfer"],
                     state="readonly" if state == "normal" else "disabled",
                     font=("Segoe UI", 10)).pack(fill="x", ipady=6, pady=(2, 0))

        # Party (customer/supplier)
        party_label = "Customer *" if self.mode == "sales" else "Supplier *"
        pcell = cell(1, 0, party_label)
        self.party_var = tk.StringVar()
        opts = [f"{p['code']} — {p['name']}" for p in self._parties]
        self.party_combo = ttk.Combobox(pcell, textvariable=self.party_var,
                                         values=opts, state="readonly",
                                         font=("Segoe UI", 10))
        self.party_combo.pack(fill="x", ipady=6, pady=(2, 0))

        # Notes (spans remaining)
        ncell = tk.Frame(grid, bg=C["card_bg"])
        ncell.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(0, 6))
        tk.Label(ncell, text="Notes", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.hdr["notes"] = tk.StringVar()
        tk.Entry(ncell, textvariable=self.hdr["notes"], font=("Segoe UI", 10),
                 relief="solid", bd=1, state=state).pack(fill="x", ipady=6, pady=(2, 0))

    def _build_grid(self, C):
        # v6.9: no title line above the grid — more rows for the items
        try:
            from ui.invoice_grid import InvoiceGrid
            mode = (cfg.get("sales_price_tax_mode", "inclusive") if self.mode == "sales"
                    else cfg.get("purchase_cost_tax_mode", "exclusive"))
            self.grid = InvoiceGrid(self.items_area, C, self._products,
                                    self._product_units, on_change=self._on_change,
                                    tax_mode=mode,
                                    doc_type=("sales_return" if self.mode == "sales"
                                              else "purchase_return"))
            self.grid.pack(fill="both", expand=True, padx=8, pady=(4, 0))
            self._on_change()
            if not self.view_only:
                self.grid.focus_first_product()
        except Exception as e:
            import traceback; traceback.print_exc()
            tk.Label(self.items_area, text=f"⚠ Grid load error:\n{e}",
                     bg=C["content_bg"], fg=C["danger"]).pack(padx=16, pady=20)

    def _build_totals(self, C):
        """v6.9: totals on one slim line (was a tall block)."""
        from ui.ui_kit import total_strip
        self.tvars = total_strip(self.bottom_bar,
                                 [("Total Qty", "qty", None), ("Gross", "gross", None),
                                  ("Discount", "disc", C["danger"]), ("Taxable", "taxable", None),
                                  ("VAT", "vat", C["info"])],
                                 ("NET TOTAL (SAR)", "total"), C)

    def _build_footer(self, C):
        footer = tk.Frame(self.win, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        inner = tk.Frame(footer, bg=C["card_bg"]); inner.pack(fill="x", padx=10, pady=3)
        self.status = tk.StringVar()
        tk.Label(inner, textvariable=self.status, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["danger"]).pack(side="left")
        tk.Button(inner, command=self.win.destroy,
                  **__import__("ui.ui_kit", fromlist=["x"]).slim_ghost_key_style("Esc", "Cancel")).pack(
                      side="right", padx=(8, 0))
        from ui import print_menu
        print_menu.print_button(inner, f"{self.mode}_return", lambda: self.return_id,
                                before=self._save_for_print, status=self.status,
                                **__import__("ui.ui_kit", fromlist=["x"]).slim_key_style(
                                    C.get("tile_purple", C["info"]), "🖨 ▾", "Print")).pack(side="right", padx=(8, 0))
        if not self.view_only:
            tk.Button(inner, command=lambda: self._save(confirm=True),
                      **__import__("ui.ui_kit", fromlist=["x"]).slim_key_style(
                          C.get("tile_green", C["success"]), "F10", "Save & Confirm")).pack(
                          side="right", padx=(8, 0))
            tk.Button(inner, command=lambda: self._save(confirm=False),
                      **__import__("ui.ui_kit", fromlist=["x"]).slim_key_style(
                          C.get("tile_blue", C["primary"]), "F9", "Save Draft")).pack(
                          side="right")

    # ── helpers ───────────────────────────────────────────────
    def _focus_barcode(self):
        try:
            self.grid.focus_barcode()
        except Exception:
            pass

    def _on_change(self):
        grid = getattr(self, "grid", None)
        if grid is None:
            return
        from modules.doc_math import doc_totals, round_lines
        self._lines = round_lines(grid.data_lines())        # halalas (v6.9.2)
        if not hasattr(self, "tvars"):
            return
        gross = sum(l.get("line_amount", 0) for l in self._lines)
        disc = sum(l.get("discount_amount", 0) for l in self._lines)
        T = doc_totals(self._lines, (getattr(getattr(self, "grid", None), "tax_mode", "exclusive") == "inclusive"))               # VAT once per rate
        vat, total = T["vat"], T["total"]
        qty = sum(l.get("quantity", 0) for l in self._lines)
        self.tvars["qty"].set(f"{qty:g}")
        self.tvars["gross"].set(f"{gross:,.2f}")
        self.tvars["disc"].set(f"−{disc:,.2f}")
        self.tvars["taxable"].set(f"{T['taxable']:,.2f}")
        self.tvars["vat"].set(f"{vat:,.2f}")
        self.tvars["total"].set(f"{total:,.2f}")

    def _set_defaults(self):
        self.hdr["date"].set(date.today().isoformat())
        self.hdr["number"].set(self._next_number())
        # Default party = Cash customer/supplier, so a cash return
        # doesn't require picking a party first (mirrors Sales Invoice
        # and Purchase Invoice).
        cash = next((p for p in self._parties
                     if str(p.get("code", "")).upper() in
                     ("CASH", "WALKIN", "CASH-001", "WALK-IN")
                     or "cash" in str(p.get("name", "")).lower()
                     or "walk" in str(p.get("name", "")).lower()), None)
        if cash:
            self.party_var.set(f"{cash['code']} — {cash['name']}")

    def _save_for_print(self):
        """Print needs a saved return: save it (as draft) if new."""
        if self.return_id or self.view_only:
            return True
        return self._save(confirm=False, keep_open=True) is True

    def _next_number(self):
        try:
            from modules.doc_numbering import next_number
            return next_number(self.cfg["table"], "return_number",
                               self.cfg["prefix"])
        except Exception:
            ym = datetime.now().strftime("%Y%m")
            return f"{self.cfg['prefix']}-{ym}-000001"

    # ── load original source invoice/purchase ─────────────────
    def _load_original(self):
        ref = self.hdr["ref"].get().strip()
        if not ref:
            messagebox.showinfo("Reference", "Type the original number first.")
            return
        try:
            src = db.fetchone(
                f"SELECT * FROM {self.cfg['src_table']} WHERE invoice_number=?", (ref,))
            if not src:
                messagebox.showinfo("Not found", f"No record '{ref}'.")
                return
            sid = self.cfg.get("src_id", "invoice_id")
            lines = db.fetchall(
                f"SELECT * FROM {self.cfg['src_lines']} WHERE {sid}=? "
                f"ORDER BY line_number", (src[sid],))
            self.grid.set_lines([dict(l) for l in lines])
            self._on_change()
            # set party
            pid = src.get(self.cfg["party_id"])
            if pid:
                p = next((x for x in self._parties if x["id"] == pid), None)
                if p:
                    self.party_combo.set(f"{p['code']} — {p['name']}")
            # v6.9.1: a bill that is still open → the return goes on the
            # party's account (and settles that bill); a paid bill →
            # money back the way it was paid
            how = ""
            try:
                left = float(src.get("total_amount") or 0) - float(src.get("paid_amount") or 0)
                if str(src.get("payment_status") or "").lower() == "paid":
                    left = 0.0
                paid_by = str(src.get("payment_method") or "").lower()
                pick = ("credit" if left > 0.005 else
                        paid_by if paid_by in ("cash", "card", "bank_transfer") else "cash")
                self.hdr["payment"].set(pick)
                how = ("\nPayment Type: credit — the bill still has %.2f open, the return "
                       "comes off it." % left) if pick == "credit" else ""
            except Exception:
                pass
            messagebox.showinfo("Loaded",
                                f"Imported {len(lines)} line(s). Edit quantities to "
                                f"do a partial return.{how}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    # ── navigation / find ─────────────────────────────────────
    def _toggle_find(self):
        on = self.find_on.get()
        self.find_entry.configure(state="normal" if on else "disabled")
        if on:
            self.find_entry.focus_set()

    def _find(self):
        num = self.find_var.get().strip()
        if not num:
            return
        row = db.fetchone(
            f"SELECT return_id FROM {self.cfg['table']} WHERE return_number=?", (num,))
        if not row:
            row = db.fetchone(
                f"SELECT TOP 1 return_id FROM {self.cfg['table']} "
                f"WHERE return_number LIKE ? ORDER BY return_id DESC", ("%" + num + "%",))
        if row:
            self._goto(row["return_id"])
        else:
            messagebox.showinfo("Not found", f"No return matching '{num}'.")

    def _nav_prev(self):
        cur = self.return_id
        if cur:
            row = db.fetchone(f"SELECT TOP 1 return_id FROM {self.cfg['table']} "
                              f"WHERE return_id<? ORDER BY return_id DESC", (cur,))
        else:
            row = db.fetchone(f"SELECT TOP 1 return_id FROM {self.cfg['table']} "
                              f"ORDER BY return_id DESC")
        if row:
            self._goto(row["return_id"])
        else:
            messagebox.showinfo("Navigation", "No earlier return.")

    def _nav_next(self):
        cur = self.return_id
        if not cur:
            messagebox.showinfo("Navigation", "Already on a new return.")
            return
        row = db.fetchone(f"SELECT TOP 1 return_id FROM {self.cfg['table']} "
                          f"WHERE return_id>? ORDER BY return_id ASC", (cur,))
        if row:
            self._goto(row["return_id"])
        else:
            messagebox.showinfo("Navigation", "This is the latest return.")

    def _goto(self, rid):
        self.return_id = rid
        try:
            self.grid.set_lines([])
        except Exception:
            pass
        self._load_return()

    def _load_return(self):
        r = db.fetchone(f"SELECT * FROM {self.cfg['table']} WHERE return_id=?",
                        (self.return_id,))
        if not r:
            return
        self.hdr["number"].set(r.get("return_number", ""))
        self.hdr["date"].set(str(r.get("return_date", "")))
        self.hdr["ref"].set(r.get(self.cfg["ref_col"], "") or "")
        self.hdr["payment"].set(r.get("payment_method", "cash") or "cash")
        self.hdr["notes"].set(r.get("notes_en", "") or "")
        pid = r.get(self.cfg["party_id"])
        if pid:
            p = next((x for x in self._parties if x["id"] == pid), None)
            if p:
                self.party_combo.set(f"{p['code']} — {p['name']}")
        lines = db.fetchall(f"SELECT * FROM {self.cfg['lines']} WHERE return_id=? "
                            f"ORDER BY line_number", (self.return_id,))
        try:
            self.grid.set_lines([dict(l) for l in lines])
        except Exception:
            pass
        self._on_change()

    # ── save ──────────────────────────────────────────────────
    def _save(self, confirm=False, keep_open=False):
        from modules import permissions as _pm
        if not _pm.allowed(("sales_return" if self.mode == "sales" else "purchase_return"), ("edit" if self.return_id else "add")):
            return False
        try:
            self._lines = self.grid.data_lines()
        except Exception:
            pass
        if not self._lines:
            self.status.set("⚠️  Add at least one item.")
            return
        if not self.party_var.get() or "—" not in self.party_var.get():
            self.status.set("⚠️  Select a " + self.cfg["party"] + ".")
            return
        rdate = self.hdr["date"].get().strip()
        from modules.date_utils import validate_invoice_date
        ok, iso_date, err = validate_invoice_date(rdate)
        if not ok:
            self.status.set(f"⚠️  {err}")
            return
        self.hdr["date"].set(iso_date)
        try:
            from modules import financial_year as fy
            lock_msg = fy.guard_active(iso_date)
            if lock_msg:
                self.status.set(f"⚠️  {lock_msg}")
                return
        except Exception:
            pass
        if self.return_id:
            try:
                from modules import doc_edit
                why = doc_edit.block_reason(f"{self.mode}_return", self.return_id, "edit")
            except Exception:
                why = ""
            if why:
                self.status.set(f"⚠️  {why}")
                return
        self.status.set("")

        code = self.party_var.get().split(" — ")[0]
        party = next((p for p in self._parties if p["code"] == code), None)
        from modules.doc_math import doc_totals, round_lines
        self._lines = round_lines(self._lines)
        T = doc_totals(self._lines, (getattr(getattr(self, "grid", None), "tax_mode", "exclusive") == "inclusive"))     # v6.9.2: the ZATCA way
        gross, vat, total = T["taxable"], T["vat"], T["total"]
        disc = sum(l.get("discount_amount", 0) for l in self._lines)
        cf = self.cfg
        editing = bool(self.return_id)
        number = self.hdr["number"].get() if editing else self._next_number()

        # v5.27: header, lines, stock, journal and ZATCA are ONE transaction
        _tx = None
        try:
            _tx = db.begin()
            if editing:
                # edit a saved return: same number, new header + lines;
                # doc_posting.sync below reverses the old stock + journal
                pcols = ("customer_id, customer_name_en, customer_name_ar, customer_vat_no"
                         if self.mode == "sales" else
                         "supplier_id, supplier_name_en, supplier_name_ar, supplier_vat_no")
                sets = ", ".join(f"{c.strip()}=?" for c in pcols.split(","))
                db.execute(
                    f"UPDATE {cf['table']} SET return_date=?, {cf['ref_col']}=?, {sets}, "
                    f"subtotal_amount=?, discount_amount=?, taxable_amount=?, vat_amount=?, "
                    f"total_amount=?, payment_method=?, notes_en=?, return_status=? "
                    f"WHERE return_id=?",
                    (self.hdr["date"].get(), self.hdr["ref"].get(),
                     party["id"], party["name"], party.get("name_ar", ""),
                     party.get("vat", ""), gross, disc, gross, vat, total,
                     self.hdr["payment"].get(), self.hdr["notes"].get(),
                     "confirmed" if confirm else "draft", self.return_id))
                db.execute(f"DELETE FROM {cf['lines']} WHERE return_id=?",
                           (self.return_id,))
            elif self.mode == "sales":
                db.execute(
                    f"INSERT INTO {cf['table']} (return_number, return_date, "
                    f"{cf['ref_col']}, customer_id, customer_name_en, customer_name_ar, "
                    f"customer_vat_no, subtotal_amount, discount_amount, taxable_amount, "
                    f"vat_amount, total_amount, payment_method, notes_en, return_status) "
                    f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (number, self.hdr["date"].get(), self.hdr["ref"].get(),
                     party["id"], party["name"], party.get("name_ar", ""),
                     party.get("vat", ""), gross, disc, gross, vat, total,
                     self.hdr["payment"].get(), self.hdr["notes"].get(),
                     "confirmed" if confirm else "draft"))
            else:
                db.execute(
                    f"INSERT INTO {cf['table']} (return_number, return_date, "
                    f"{cf['ref_col']}, supplier_id, supplier_name_en, supplier_name_ar, "
                    f"supplier_vat_no, subtotal_amount, discount_amount, taxable_amount, "
                    f"vat_amount, total_amount, payment_method, notes_en, return_status) "
                    f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (number, self.hdr["date"].get(), self.hdr["ref"].get(),
                     party["id"], party["name"], party.get("name_ar", ""),
                     party.get("vat", ""), gross, disc, gross, vat, total,
                     self.hdr["payment"].get(), self.hdr["notes"].get(),
                     "confirmed" if confirm else "draft"))
            rid = self.return_id if editing else db.last_identity(cf["table"], "return_id")
            for i, ln in enumerate(self._lines, 1):
                db.execute(
                    f"INSERT INTO {cf['lines']} (return_id, line_number, product_id, "
                    f"product_code, product_name_en, product_name_ar, quantity, "
                    f"unit_of_measure_en, unit_price, discount_amount, line_amount, "
                    f"vat_category_code, vat_rate, vat_amount, line_total) "
                    f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, i, ln.get("product_id"), ln.get("product_code", ""),
                     ln.get("product_name_en", ""), ln.get("product_name_ar", ""),
                     ln.get("quantity", 0), ln.get("unit_of_measure_en", "Unit"),
                     ln.get("unit_price", 0), ln.get("discount_amount", 0),
                     ln.get("line_amount", 0), ln.get("vat_category_code", "S"),
                     ln.get("vat_rate", 15), ln.get("vat_amount", 0),
                     ln.get("line_total", 0)))
            # ── Stock + accounts (one engine for every document) ──
            # Draft → nothing moves. Confirmed → stock back in (sales
            # return) / out (purchase return) in BASE units, the return
            # journal, and for sales returns the cost-of-sales reversal.
            from modules import doc_posting
            try:
                doc_posting.sync(f"{self.mode}_return", rid)
            except Exception as e:
                doc_posting.last_warning = str(e)[:200]
            if confirm and self.mode == "sales":    # ZATCA Phase 2: credit note signed
                try:
                    from modules.zatca import egs as _zegs
                    _zegs.after_save("sales_return", rid)
                except Exception:
                    pass
            _tx.commit()                # all kept together — or the except undoes it all
            self.return_id = rid
            if keep_open:                          # saved on the way to printing
                self.status.set(f"💾 Saved {number} ({'confirmed' if confirm else 'draft'}).")
                return True
            if confirm:
                messagebox.showinfo("Saved", f"{cf['title']} {number} confirmed.\n"
                                    f"Stock and accounts updated.")
                doc_posting.notify(self.win)
            else:
                messagebox.showinfo("Saved", f"{cf['title']} {number} saved as DRAFT.\n"
                                    f"Stock and accounts update when you confirm it "
                                    f"(✅ Confirm in the list).")
            self.win.destroy()
            return True
        except Exception as e:
            if _tx is not None and not _tx.kept:
                _tx.rollback()                     # nothing of a failed save is kept
                messagebox.showerror("Not saved", "The return was NOT saved — nothing was "
                                     "kept. Please try again.\n\n" + str(e)[:400])
                return False
            messagebox.showerror("Save Error", str(e))


# ── List views ────────────────────────────────────────────────
class _ReturnListView:
    mode = "sales"

    def __init__(self, parent):
        C = cfg.theme()
        for w in parent.winfo_children():
            w.destroy()
        self.parent = parent
        self.cfg = CONF[self.mode]
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        head = tk.Frame(self.frame, bg=C["content_bg"])
        head.pack(fill="x", padx=16, pady=12)
        tk.Label(head, text=f"↩  {self.cfg['title']}s", font=("Segoe UI", 16, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        self.search_var = tk.StringVar()
        se = tk.Entry(head, textvariable=self.search_var, font=("Segoe UI", 10),
                      width=26, relief="solid", bd=1, bg="white")
        se.pack(side="left", padx=(16, 0), ipady=3)
        se.insert(0, "")
        tk.Label(head, text="🔍", font=("Segoe UI Emoji", 11),
                 bg=C["content_bg"]).pack(side="left", padx=(4, 0))
        self.search_var.trace("w", lambda *a: self._load())
        tk.Button(head, text=f"＋ New {self.cfg['title']}", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=8,
                  cursor="hand2", command=self._new).pack(side="right")
        tk.Button(head, text="🔄 Refresh", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=8, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load).pack(side="right", padx=8)

        cols = ("number", "date", "party", "total", "status")
        heads = {"number": ("Return #", 160), "date": ("Date", 110),
                 "party": (self.cfg["party"].title(), 240),
                 "total": ("Total", 110), "status": ("Status", 100)}
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Ret.Treeview", rowheight=30, font=("Segoe UI", 10))
        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", style="Ret.Treeview")
        for c in cols:
            txt, w = heads[c]
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w,
                             anchor="e" if c == "total" else "w")
        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<Double-1>", self._open)

        # ── Action bar: Open · Delete · Export · Report ───────
        bbar = tk.Frame(self.frame, bg=C["content_bg"])
        bbar.pack(fill="x", padx=16, pady=(0, 14))
        for txt, bg, fg, cmd in [
            ("👁  Open", C["card_bg"], C["text_primary"], self._open),
            ("✏  Edit", C["card_bg"], C["text_primary"], self._edit),
            ("✅  Confirm", "#F0FDF4", C["success"], self._confirm),
            ("🖨  Print ▾", C["card_bg"], C["text_primary"], None),
            ("🗑  Delete", "#FEF2F2", C["danger"], self._delete),
            ("📥  Export", C["card_bg"], C["text_primary"], self._export_excel),
            ("📊  Report", C["card_bg"], C["text_primary"], self._report_pdf),
        ]:
            b_ = tk.Button(bbar, text=txt, font=("Segoe UI", 9), bg=bg, fg=fg,
                           relief="flat", padx=12, pady=6, cursor="hand2",
                           highlightbackground=C["border"], highlightthickness=1,
                           command=cmd)
            if cmd is None:
                from ui import print_menu
                b_.configure(command=lambda b__=b_: print_menu.show_menu(
                    self.frame, f"{self.mode}_return",
                    lambda: int(self.tree.selection()[0]) if self.tree.selection() else None,
                    widget=b__))
            b_.pack(side="left", padx=(0, 6))
        self._load()

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        pname = "customer_name_en" if self.mode == "sales" else "supplier_name_en"
        try:
            rows = db.fetchall(
                f"SELECT return_id, return_number, return_date, {pname} AS party, "
                f"total_amount, return_status FROM {self.cfg['table']} "
                f"ORDER BY return_id DESC") or []
            self._rows = rows
            q = (self.search_var.get() or "").strip().lower()
            if q:
                rows = [r for r in rows if q in " ".join(
                    str(r.get(k) or "") for k in
                    ("return_number", "return_date", "party", "return_status")).lower()]
            for r in rows:
                self.tree.insert("", "end", iid=str(r["return_id"]), values=(
                    r["return_number"], r["return_date"], r.get("party", ""),
                    f"{float(r.get('total_amount', 0)):,.2f}",
                    r.get("return_status", "")))
        except Exception as e:
            self.tree.insert("", "end", values=(f"(load error: {e})", "", "", "", ""))

    def _new(self):
        from modules import permissions as _pm
        if not _pm.allowed(("sales_return" if self.mode == "sales" else "purchase_return"), "add"):
            return False
        key = "allow_sales_return" if self.mode == "sales" else "allow_purchase_return"
        if not cfg.flag(key, True):
            messagebox.showwarning(
                "Returns disabled",
                f"New {self.cfg['title'].lower()}s are turned off.\n\n"
                f"Turn on 'Allow {self.mode.title()} Return' in Settings ▸ "
                f"{'Sales' if self.mode == 'sales' else 'Purchase'}.")
            return
        ReturnForm(self.parent, mode=self.mode)

    def _open(self, event=None):
        sel = self.tree.selection()
        if sel:
            ReturnForm(self.parent, mode=self.mode,
                       return_id=int(sel[0]), view_only=True)

    def _edit(self):
        """Edit a saved return (draft or confirmed). Confirmed: on save the
        old stock + journal are reversed and the new ones posted."""
        from modules import permissions as _pm
        if not _pm.allowed(("sales_return" if self.mode == "sales" else "purchase_return"), "edit"):
            return False
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a return first.")
            return
        rid = int(sel[0])
        from modules import doc_edit
        kind = f"{self.mode}_return"
        why = doc_edit.block_reason(kind, rid, "edit")
        if why:
            messagebox.showwarning("Edit Return", why)
            return
        q = doc_edit.ask_text(kind, rid, "edit")
        if q and not messagebox.askyesno("Edit Return", q):
            return
        f = ReturnForm(self.parent, mode=self.mode, return_id=rid)
        try:
            f.win.bind("<Destroy>", lambda e, w=f.win: self._load()
                       if e.widget is w else None, add="+")
        except Exception:
            pass

    def _confirm(self):
        """Confirm a DRAFT return → stock moves and the journal posts."""
        from modules import permissions as _pm
        if not _pm.allowed(("sales_return" if self.mode == "sales" else "purchase_return"), "edit"):
            return False
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a return first.")
            return
        rid = int(sel[0])
        row = db.fetchone(f"SELECT return_number, return_status FROM {self.cfg['table']} "
                          f"WHERE return_id=?", (rid,)) or {}
        if (row.get("return_status") or "").lower() == "confirmed":
            messagebox.showinfo("Confirm", "This return is already confirmed.")
            return
        if not messagebox.askyesno("Confirm", f"Confirm {row.get('return_number', '')}?\n"
                                   "Stock and accounts will be updated."):
            return
        try:
            from modules import doc_posting
            with db.transaction():        # status, stock, journal, ZATCA together (v5.27)
                db.execute(f"UPDATE {self.cfg['table']} SET return_status='confirmed' "
                           f"WHERE return_id=?", (rid,))
                try:
                    doc_posting.sync(f"{self.mode}_return", rid)
                except Exception as e:
                    doc_posting.last_warning = str(e)[:200]
                if self.mode == "sales":            # ZATCA Phase 2: credit note signed
                    try:
                        from modules.zatca import egs as _zegs
                        _zegs.after_save("sales_return", rid)
                    except Exception:
                        pass
            self._load()
            doc_posting.notify(self.frame)
        except Exception as e:
            messagebox.showerror("Confirm", str(e)[:300])

    def _delete(self):
        from modules import permissions as _pm
        if not _pm.allowed(("sales_return" if self.mode == "sales" else "purchase_return"), "delete"):
            return False
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a return first.")
            return
        rid = int(sel[0])
        from modules import doc_edit
        kind = f"{self.mode}_return"
        number, status, _d = doc_edit.info(kind, rid)
        why = doc_edit.block_reason(kind, rid, "delete")
        if why:
            messagebox.showwarning("Delete", why)
            return
        q = (doc_edit.ask_text(kind, rid, "delete") or
             f"Delete {self.cfg['title'].lower()} {number}?")
        if not messagebox.askyesno("Delete", q):
            return
        ok, msg = doc_edit.delete_document(kind, rid)
        if not ok:
            messagebox.showerror("Delete", msg)
        self._load()

    def _export_excel(self):
        from modules import permissions as _pm
        if not _pm.allowed(("sales_return" if self.mode == "sales" else "purchase_return"), "export"):
            return False
        try:
            from modules.doc_actions import export_tree_excel
            headers = ["Return #", "Date", self.cfg["party"].title(),
                       "Total", "Status"]
            export_tree_excel(self.frame, self.tree,
                              f"{self.cfg['title']}s", headers,
                              title=f"{self.cfg['title']}s")
        except Exception as e:
            messagebox.showerror("Export", str(e)[:300])

    def _report_pdf(self):
        from modules import permissions as _pm
        if not _pm.allowed(("sales_return" if self.mode == "sales" else "purchase_return"), "print"):
            return False
        try:
            from modules.doc_actions import export_tree_pdf
            headers = ["Return #", "Date", self.cfg["party"].title(),
                       "Total", "Status"]
            export_tree_pdf(self.frame, self.tree,
                            f"{self.cfg['title']}_Register", headers,
                            title=f"{self.cfg['title']} Register",
                            subtitle=f"{len(self.tree.get_children())} returns")
        except Exception as e:
            messagebox.showerror("Report", str(e)[:300])


class SalesReturnView(_ReturnListView):
    mode = "sales"


class PurchaseReturnView(_ReturnListView):
    mode = "purchase"
