# ============================================================
# DayBill ERP - Purchase Invoices Module
# List + Create/Edit with line items | Input VAT tracking
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db


class PurchaseInvoiceView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self._all = []
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._topbar(C)
        self._stats(C)
        self._search(C)
        self._table(C)
        self._load()

    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text=f"🛒  {t('nav.purchases')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="＋  New Purchase", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat",
                  padx=16, pady=7, cursor="hand2",
                  activebackground=C["primary_dark"],
                  command=self._new).pack(side="right")
        tk.Button(bar, text="📥  Export", font=("Segoe UI", 10),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export_excel).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="📊  Report", font=("Segoe UI", 10),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._report_pdf).pack(side="right", padx=(0, 8))

    def _stats(self, C):
        self.stats = tk.Frame(self.frame, bg=C["content_bg"])
        self.stats.pack(fill="x", padx=24, pady=(14, 0))

    def _refresh_stats(self, data):
        C = cfg.theme()
        for w in self.stats.winfo_children():
            w.destroy()
        total = sum(float(r.get("total_amount", 0)) for r in data)
        vat = sum(float(r.get("vat_amount", 0)) for r in data)
        unpaid = sum(float(r.get("total_amount", 0)) - float(r.get("paid_amount", 0))
                     for r in data if r.get("payment_status") != "paid")
        items = [("🛒", "Purchases", str(len(data)), C["primary"]),
                 ("💰", "Total", f"{total:,.0f}", C["info"]),
                 ("📥", "Input VAT", f"{vat:,.0f}", C["success"]),
                 ("⏳", "Unpaid", f"{unpaid:,.0f}", C["warning"])]
        for icon, label, val, color in items:
            card = tk.Frame(self.stats, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 10), ipadx=12, ipady=6)
            tk.Label(card, text=f"{icon}  {label}", font=("Segoe UI", 8),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=val, font=("Segoe UI", 15, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w", padx=8, pady=(0, 6))

    def _search(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(14, 0))
        sf = tk.Frame(bar, bg="white", highlightbackground=C["border"], highlightthickness=1)
        sf.pack(side="left")
        tk.Label(sf, text="🔍", font=("Segoe UI Emoji", 11), bg="white",
                 fg=C["text_secondary"]).pack(side="left", padx=(10, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._filter())
        tk.Entry(sf, textvariable=self.search_var, font=("Segoe UI", 10), bg="white",
                 relief="flat", width=28, fg=C["text_primary"]).pack(side="left", ipady=6, padx=(0, 10))
        self.count_var = tk.StringVar()
        tk.Label(bar, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right")

    def _table(self, C):
        wrapper = tk.Frame(self.frame, bg=C["content_bg"])
        wrapper.pack(fill="both", expand=True, padx=24, pady=(10, 24))
        card = tk.Frame(wrapper, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("number", "supplier_inv", "date", "supplier", "subtotal", "vat", "total", "status")
        headers = {"number": ("Purchase #", 120, "center"),
                   "supplier_inv": ("Supplier Inv#", 120, "center"),
                   "date": ("Date", 95, "center"), "supplier": ("Supplier", 180, "w"),
                   "subtotal": ("Subtotal", 100, "e"), "vat": ("VAT", 90, "e"),
                   "total": ("Total SAR", 110, "e"), "status": ("Status", 90, "center")}
        style = ttk.Style()
        style.configure("Pur.Treeview", background="white", rowheight=32, font=("Segoe UI", 9))
        style.configure("Pur.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 style="Pur.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for col in cols:
            h, w, a = headers[col]
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor=a)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("even", background="#FAFAFA")
        self.tree.bind("<Double-1>", lambda e: self._open())

        bbar = tk.Frame(wrapper, bg=C["content_bg"])
        bbar.pack(fill="x", pady=(6, 0))
        tk.Button(bbar, text="✏  Open / Edit", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._open).pack(side="left", padx=(0, 6))
        tk.Button(bbar, text="✅  Confirm", font=("Segoe UI", 9), bg="#F0FDF4",
                  fg=C["success"], relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._confirm).pack(side="left", padx=(0, 6))
        tk.Button(bbar, text="💰  Pay Supplier", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._pay).pack(side="left", padx=(0, 6))
        from ui import print_menu
        pb = tk.Button(bbar, text="🖨  Print ▾", font=("Segoe UI", 9), bg=C["card_bg"],
                       fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                       highlightbackground=C["border"], highlightthickness=1)
        pb.configure(command=lambda: print_menu.show_menu(
            self.frame, "purchase", self._sel_quiet, widget=pb))
        pb.pack(side="left", padx=(0, 6))
        tk.Button(bbar, text="🏷  Labels", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._labels).pack(side="left", padx=(0, 6))
        tk.Button(bbar, text="🗑  Delete", font=("Segoe UI", 9), bg="#FEF2F2",
                  fg=C["danger"], relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._delete).pack(side="left")
        tk.Button(bbar, text="🔄  Refresh", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load).pack(side="right")

    def _load(self):
        try:
            self._all = db.fetchall(
                "SELECT purchase_id, invoice_number, supplier_invoice_no, invoice_date, "
                "supplier_name_en, subtotal_amount, vat_amount, total_amount, "
                "paid_amount, invoice_status, payment_status "
                "FROM purchase_invoices ORDER BY created_at DESC")
        except Exception as e:
            self._all = []
            messagebox.showerror("DB Error", str(e))
        self._filter()

    def _filter(self):
        q = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        rows = []
        for r in self._all:
            if q:
                s = (str(r.get("invoice_number", "")) + str(r.get("supplier_name_en", "")) +
                     str(r.get("supplier_invoice_no", ""))).lower()
                if q not in s:
                    continue
            rows.append(r)
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            st = r.get("invoice_status", "draft")
            self.tree.insert("", "end", iid=str(r["purchase_id"]), values=(
                r.get("invoice_number", ""), r.get("supplier_invoice_no", "") or "—",
                str(r.get("invoice_date", "")), r.get("supplier_name_en", ""),
                f"{float(r.get('subtotal_amount', 0)):,.2f}",
                f"{float(r.get('vat_amount', 0)):,.2f}",
                f"{float(r.get('total_amount', 0)):,.2f}",
                f"{'✅' if st=='confirmed' else '📝'} {st.title()}"),
                tags=("even",) if i % 2 == 0 else ())
        self._refresh_stats(self._all)
        self.count_var.set(f"{len(rows)} invoice(s)")

    def _sel(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", "Select a purchase invoice.")
            return None
        return int(s[0])

    def _sel_quiet(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _labels(self):
        """🏷 Labels: barcode labels for the goods on this purchase
        (each unit's own barcode + price, copies = quantity received)."""
        from modules import permissions as _pm
        if not _pm.allowed("products", "print"):
            return False
        pid = self._sel()
        if pid:
            try:
                from ui.label_printer import open_for_purchase
                open_for_purchase(self.frame, pid)
            except Exception as e:
                messagebox.showerror("Labels", str(e)[:200])

    def _new(self):
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "add"):
            return False
        PurchaseForm(self.frame, None, self._load)

    def _open(self):
        pid = self._sel()
        if pid:
            from modules import doc_edit
            why = doc_edit.block_reason("purchase", pid, "edit")
            if why:           # still open it to look at — saving is refused
                messagebox.showinfo("Purchase (view only)",
                                    why + "\n\nIt opens for viewing / printing only.")
            else:
                q = doc_edit.ask_text("purchase", pid, "edit")
                if q and not messagebox.askyesno("Edit Purchase", q):
                    return
            PurchaseForm(self.frame, pid, self._load)

    def _confirm(self):
        pid = self._sel()
        if not pid:
            return
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "edit"):
            return False
        row = db.fetchone("SELECT invoice_number, invoice_status FROM purchase_invoices "
                          "WHERE purchase_id=?", (pid,)) or {}
        if (row.get("invoice_status") or "").lower() == "confirmed":
            messagebox.showinfo("Confirm", "This purchase is already confirmed.")
            return
        try:
            from modules import doc_posting
            with db.transaction():       # status + stock + journal together (v5.27)
                db.execute("UPDATE purchase_invoices SET invoice_status='confirmed', "
                           "updated_at=GETDATE() WHERE purchase_id=?", (pid,))
                # stock in + cost update + purchase journal (one engine)
                try:
                    doc_posting.sync("purchase", pid)
                except Exception as e:
                    doc_posting.last_warning = str(e)[:200]
            self._load()
            doc_posting.notify(self.frame)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _pay(self):
        """Supplier payment for the selected purchase invoice."""
        from modules import permissions as _pm
        if not _pm.allowed("payment", "add"):
            return False
        pid = self._sel()
        if not pid:
            return
        row = db.fetchone("SELECT supplier_id, invoice_status, payment_status, "
                          "invoice_number FROM purchase_invoices WHERE purchase_id=?",
                          (pid,)) or {}
        if (row.get("invoice_status") or "") != "confirmed":
            messagebox.showinfo("Pay Supplier", "Confirm the purchase first.")
            return
        if (row.get("payment_status") or "") == "paid":
            messagebox.showinfo("Pay Supplier",
                                f"Purchase {row.get('invoice_number')} is already paid.")
            return
        from ui.payments import PaymentForm
        PaymentForm(self.frame, "disbursement", self._load,
                    party_id=row.get("supplier_id"), doc_id=pid)

    def _delete(self):
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "delete"):
            return False
        pid = self._sel()
        if not pid:
            return
        from modules import doc_edit
        number, status, _d = doc_edit.info("purchase", pid)
        why = doc_edit.block_reason("purchase", pid, "delete")
        if why:
            messagebox.showwarning("Delete Purchase", why)
            return
        q = doc_edit.ask_text("purchase", pid, "delete") or f"Delete purchase {number}?"
        if messagebox.askyesno(t("common.warning"), q):
            ok, msg = doc_edit.delete_document("purchase", pid)
            if not ok:
                messagebox.showerror(t("common.error"), msg)
            self._load()

    def _export_excel(self):
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "export"):
            return False
        try:
            from modules.doc_actions import export_tree_excel
            headers = ["Purchase #", "Supplier Inv#", "Date", "Supplier",
                       "Subtotal", "VAT", "Total", "Status"]
            export_tree_excel(self.frame, self.tree, "Purchases", headers,
                              title="Purchase Invoices")
        except Exception as e:
            messagebox.showerror("Export", str(e)[:300])

    def _report_pdf(self):
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "print"):
            return False
        try:
            from modules.doc_actions import export_tree_pdf
            headers = ["Purchase #", "Supplier Inv#", "Date", "Supplier",
                       "Subtotal", "VAT", "Total", "Status"]
            export_tree_pdf(self.frame, self.tree, "Purchase_Register", headers,
                            title="Purchase Invoice Register",
                            subtitle=f"{len(self.tree.get_children())} purchases")
        except Exception as e:
            messagebox.showerror("Report", str(e)[:300])


class PurchaseForm:
    """Polosys-style Purchase Invoice — minimal header, big grid,
    bottom totals, prev/next nav, find-by-number. Mirrors Sales Invoice."""

    def __init__(self, parent, purchase_id=None, on_save=None):
        self.parent = parent
        self.purchase_id = purchase_id
        self.on_save = on_save
        self._lines = []
        self.suppliers = []
        self.products = []
        self._product_units = {}
        self._warehouses = ["Main Warehouse"]
        self._load_lookups()
        self._build_window()
        if purchase_id:
            self._load_data()
        else:
            self._set_defaults()
        try:      # v6.9 connector bar: New · Edit · Save · Delete (user rights)
            from ui import txn_connector as _tc
            _tc.attach(self, "purchase")
        except Exception:
            pass

    def _load_lookups(self):
        try:
            self.suppliers = db.fetchall(
                "SELECT supplier_id, supplier_code, supplier_name_en, "
                "ISNULL(supplier_name_ar,'') AS supplier_name_ar, "
                "ISNULL(vat_registration_no,'') AS vat_registration_no "
                "FROM suppliers WHERE is_active=1 ORDER BY supplier_name_en") or []
        except Exception:
            self.suppliers = []
        try:
            # NOTE: alias purchase_price AS unit_price so the grid's Rate
            # column defaults to COST price for purchases.
            self.products = db.fetchall(
                "SELECT p.product_id, p.product_code, p.product_name_en, "
                "p.product_name_ar, ISNULL(p.purchase_price,0) AS unit_price, "
                "p.unit_of_measure_en, p.vat_category_id, "
                "ISNULL(p.alias_name,'') AS alias_name, "
                "ISNULL(p.purchase_price,0) AS purchase_price, "
                "ISNULL(p.stock_quantity,0) AS stock_quantity, "
                "ISNULL(p.barcode,'') AS barcode, "
                "vc.category_code AS vat_code, ISNULL(vc.vat_rate,15) AS vat_rate "
                "FROM products p LEFT JOIN vat_categories vc "
                "ON p.vat_category_id=vc.vat_category_id "
                "WHERE p.is_active=1 AND ISNULL(p.list_in_purchase,1)=1 "
                "ORDER BY p.product_name_en") or []
        except Exception:
            self.products = []
        self._product_units = {}
        try:
            for u in db.fetchall("SELECT * FROM product_units WHERE is_active=1"):
                self._product_units.setdefault(u["product_id"], []).append(u)
        except Exception:
            self._product_units = {}
        try:                       # optional table — ask first, no DB error
            if db.execute_scalar("SELECT OBJECT_ID('warehouses','U')"):
                rows = db.fetchall("SELECT warehouse_name_en AS n FROM warehouses "
                                   "WHERE is_active=1 ORDER BY warehouse_name_en")
                wl = [r["n"] for r in (rows or []) if r.get("n")]
                if wl:
                    self._warehouses = wl
        except Exception:
            pass

    def _build_window(self):
        C = cfg.theme()
        title = "Edit Purchase" if self.purchase_id else "New Purchase Invoice"
        self.win = tk.Toplevel()
        self.win._doc_window = True     # item grid: may fill the screen
        self.win._form = self           # v6.7: compact header (ui/compact.py)
        self.win.title(title)
        w = min(1360, int(self.win.winfo_screenwidth() * 0.90))
        h = min(840, int(self.win.winfo_screenheight() * 0.92))
        self.win.geometry(f"{w}x{h}")
        self.win.configure(bg=C["content_bg"])
        self._center(w, h)
        self.win.bind("<F9>", lambda e: self._save(confirm=False))
        self.win.bind("<F10>", lambda e: self._save(confirm=True))
        self.win.bind("<F6>", lambda e: self._focus_barcode())
        self.win.bind("<Escape>", lambda e: self.win.destroy())

        hdr = tk.Frame(self.win, bg=C["primary"], height=40)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"🛒  {title}", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)

        self.form_body = tk.Frame(self.win, bg=C["card_bg"],
                                  highlightbackground=C["border"], highlightthickness=1)
        self.form_body.pack(side="top", fill="x")
        self.items_area = tk.Frame(self.win, bg=C["content_bg"])
        self.items_area.pack(side="top", fill="both", expand=True)

        self._build_header(C)
        self._build_grid(C)
        self._build_footer(C)
        self.bottom_bar = tk.Frame(self.win, bg=C["card_bg"],
                                   highlightbackground=C["border"], highlightthickness=1)
        self.bottom_bar.pack(side="bottom", fill="x")
        self._build_totals(C)

    def _build_header(self, C):
        self.hdr = {}
        grid = tk.Frame(self.form_body, bg=C["card_bg"])
        grid.pack(fill="x", padx=14, pady=10)
        for i in range(4):
            grid.columnconfigure(i, weight=1, uniform="h")

        def cell(r, c, label):
            f = tk.Frame(grid, bg=C["card_bg"])
            f.grid(row=r, column=c, sticky="ew", padx=(0, 10), pady=(0, 6))
            tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
            return f

        # Purchase number + nav + find
        pc = cell(0, 0, "Purchase Number")
        line = tk.Frame(pc, bg=C["card_bg"]); line.pack(fill="x", pady=(2, 0))
        self.hdr["number"] = tk.StringVar()
        tk.Entry(line, textvariable=self.hdr["number"], font=("Segoe UI", 10),
                 relief="solid", bd=1, state="disabled").pack(
                     side="left", fill="x", expand=True, ipady=6)
        tk.Button(line, text="▲", font=("Segoe UI", 7), width=2, bg=C["content_bg"],
                  relief="flat", cursor="hand2", command=self._nav_prev).pack(side="left", padx=(2, 0))
        tk.Button(line, text="▼", font=("Segoe UI", 7), width=2, bg=C["content_bg"],
                  relief="flat", cursor="hand2", command=self._nav_next).pack(side="left")
        fl = tk.Frame(pc, bg=C["card_bg"]); fl.pack(fill="x", pady=(3, 0))
        self.find_on = tk.BooleanVar(value=False)
        tk.Checkbutton(fl, text="Find", variable=self.find_on, font=("Segoe UI", 8),
                       bg=C["card_bg"], fg=C["text_secondary"],
                       activebackground=C["card_bg"], command=self._toggle_find).pack(side="left")
        self.find_var = tk.StringVar()
        self.find_entry = tk.Entry(fl, textvariable=self.find_var, font=("Segoe UI", 9),
                                   relief="solid", bd=1, state="disabled")
        self.find_entry.pack(side="left", padx=(4, 0), ipady=6, fill="x", expand=True)
        self.find_entry.bind("<Return>", lambda e: self._find())

        # Date
        dc = cell(0, 1, "Purchase Date *")
        self.hdr["date"] = tk.StringVar()
        de = tk.Entry(dc, textvariable=self.hdr["date"], font=("Segoe UI", 10),
                      relief="solid", bd=1)
        de.pack(fill="x", ipady=6, pady=(2, 0))
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(de, self.hdr["date"])
        except Exception:
            pass

        # Supplier invoice #
        sc = cell(0, 2, "Supplier Invoice #")
        self.hdr["supinv"] = tk.StringVar()
        tk.Entry(sc, textvariable=self.hdr["supinv"], font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(fill="x", ipady=6, pady=(2, 0))

        # Payment type
        ptc = cell(0, 3, "Payment Method")
        self.hdr["payment"] = tk.StringVar(value="cash")
        ttk.Combobox(ptc, textvariable=self.hdr["payment"],
                     values=cfg.payment_methods(["cash", "credit", "card", "bank_transfer", "cheque"]),
                     state="readonly", font=("Segoe UI", 10)).pack(fill="x", ipady=6, pady=(2, 0))

        # Supplier
        supc = cell(1, 0, "Supplier *")
        self.sup_var = tk.StringVar()
        self.sup_cb = ttk.Combobox(supc, textvariable=self.sup_var,
                                   values=[f"{s['supplier_code']} — {s['supplier_name_en']}"
                                           for s in self.suppliers],
                                   state="readonly", font=("Segoe UI", 10))
        self.sup_cb.pack(fill="x", ipady=6, pady=(2, 0))

        # Warehouse
        whc = cell(1, 1, "Warehouse")
        self.hdr["warehouse"] = tk.StringVar(value=self._warehouses[0])
        ttk.Combobox(whc, textvariable=self.hdr["warehouse"], values=self._warehouses,
                     font=("Segoe UI", 10)).pack(fill="x", ipady=6, pady=(2, 0))

        # Notes (span 2)
        nc = tk.Frame(grid, bg=C["card_bg"])
        nc.grid(row=1, column=2, columnspan=2, sticky="ew", pady=(0, 6))
        tk.Label(nc, text="Notes", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.hdr["notes"] = tk.StringVar()
        tk.Entry(nc, textvariable=self.hdr["notes"], font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(fill="x", ipady=6, pady=(2, 0))

    def _build_grid(self, C):
        tk.Label(self.items_area, text="🛒  Purchase Items (Rate = Cost Price)",
                 font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=16, pady=(8, 0))
        try:
            from ui.invoice_grid import InvoiceGrid
            self.grid = InvoiceGrid(self.items_area, C, self.products,
                                    self._product_units, on_change=self._on_change,
                                    tax_mode=cfg.get("purchase_cost_tax_mode", "exclusive"),
                                    doc_type="purchase")
            self.grid.pack(fill="both", expand=True, padx=16, pady=(4, 0))
            self._on_change()
            self.grid.focus_first_product()
        except Exception as e:
            import traceback; traceback.print_exc()
            tk.Label(self.items_area, text=f"⚠ Grid load error:\n{e}",
                     bg=C["content_bg"], fg=C["danger"]).pack(padx=16, pady=20)

    def _build_totals(self, C):
        inner = tk.Frame(self.bottom_bar, bg=C["card_bg"])
        inner.pack(fill="x", padx=14, pady=8)
        self.tvars = {}

        def tcell(col, label, key, color=None, big=False):
            f = tk.Frame(inner, bg=C["card_bg"])
            f.grid(row=0, column=col, padx=10, sticky="w")
            tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
            v = tk.StringVar(value="0.00"); self.tvars[key] = v
            if big:                               # solid blue total box
                f.destroy()
                from ui.ui_kit import total_box
                total_box(inner, label, v).grid(row=0, column=col, padx=10, sticky="nse")
                inner.columnconfigure(col - 1, weight=1)
                return
            tk.Label(f, textvariable=v, font=("Segoe UI", 16 if big else 11, "bold"),
                     bg=C["card_bg"], fg=color or C["text_primary"]).pack(anchor="w")
        tcell(0, "Total Qty", "qty")
        tcell(1, "Gross", "gross")
        tcell(2, "Discount", "disc", color=C["danger"])
        tcell(3, "Taxable", "taxable")
        tcell(4, "VAT", "vat", color=C["info"])
        tk.Frame(inner, bg=C["border"], width=1).grid(row=0, column=5, sticky="ns", padx=6)
        tcell(6, "NET TOTAL (SAR)", "total", color=C["primary"], big=True)

    def _build_footer(self, C):
        footer = tk.Frame(self.win, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        inner = tk.Frame(footer, bg=C["card_bg"]); inner.pack(fill="x", padx=16, pady=8)
        self.status_var = tk.StringVar()
        tk.Label(inner, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["danger"]).pack(side="left")
        tk.Button(inner, command=self.win.destroy,
                  **__import__("ui.ui_kit", fromlist=["x"]).ghost_key_style("Esc", "Cancel")).pack(
                      side="right", padx=(8, 0))
        from ui import print_menu
        print_menu.print_button(inner, "purchase", lambda: self.purchase_id,
                                before=self._save_for_print, status=self.status_var,
                                **__import__("ui.ui_kit", fromlist=["x"]).key_style(
                                    C.get("tile_purple", C["info"]), "🖨 ▾", "Print")).pack(side="right", padx=(8, 0))
        tk.Button(inner, command=lambda: self._save(confirm=True),
                  **__import__("ui.ui_kit", fromlist=["x"]).key_style(
                      C.get("tile_green", C["success"]), "F10", "Save & Confirm")).pack(side="right", padx=(8, 0))
        # v6.0: batch no. + expiry date per line
        tk.Button(inner, text="⏰ Expiry dates", font=("Segoe UI", 9), bg=C["card_bg"],
                  relief="flat", padx=10, pady=4, cursor="hand2", highlightthickness=1,
                  highlightbackground=C["border"], command=self._expiry_dates).pack(side="right", padx=(8, 0))
        tk.Button(inner, command=lambda: self._save(confirm=False),
                  **__import__("ui.ui_kit", fromlist=["x"]).key_style(
                      C.get("tile_blue", C["primary"]), "F9", "Save Draft")).pack(side="right")

    def _focus_barcode(self):
        try:
            self.grid.focus_barcode()
        except Exception:
            pass

    def _expiry_dates(self):
        """v6.0: batch no. + expiry date for the lines (kept on the lines)."""
        try:
            from ui.expiry_dialog import ExpiryDialog
            lines = self.grid.data_lines()
            if not lines:
                self.status_var.set("Add products first.")
                return None
            return ExpiryDialog(self.win, lines,
                                on_done=lambda: self.status_var.set("Expiry dates kept — save the purchase."))
        except Exception as e:
            self.status_var.set("Expiry: %s" % str(e)[:80])
            return None

    def _save_for_print(self):
        """Print needs a saved purchase: save it (as draft) if new."""
        if self.purchase_id:
            return True
        return self._save(confirm=False, keep_open=True) is True

    def _on_change(self):
        grid = getattr(self, "grid", None)
        if grid is None:
            return
        self._lines = grid.data_lines()
        if not hasattr(self, "tvars"):
            return
        gross = sum(l.get("line_amount", 0) for l in self._lines)
        disc = sum(l.get("discount_amount", 0) for l in self._lines)
        vat = sum(l.get("vat_amount", 0) for l in self._lines)
        total = sum(l.get("line_total", 0) for l in self._lines)
        qty = sum(l.get("quantity", 0) for l in self._lines)
        self.tvars["qty"].set(f"{qty:g}")
        self.tvars["gross"].set(f"{gross:,.2f}")
        self.tvars["disc"].set(f"−{disc:,.2f}" if abs(disc) >= 0.005 else "0.00")
        self.tvars["taxable"].set(f"{gross:,.2f}")
        self.tvars["vat"].set(f"{vat:,.2f}")
        self.tvars["total"].set(f"{total:,.2f}")

    def _set_defaults(self):
        self.hdr["date"].set(date.today().isoformat())
        self.hdr["number"].set(self._next_number())
        # Default supplier = Cash ledger supplier, so a cash purchase
        # (walk-in / spot-buy) doesn't require picking a supplier first —
        # mirrors the Sales Invoice's default-to-Cash-customer behaviour.
        cash = next((s for s in self.suppliers
                     if str(s.get("supplier_code", "")).upper() in
                     ("CASH", "WALKIN", "CASH-001", "WALK-IN")
                     or "cash" in str(s.get("supplier_name_en", "")).lower()
                     or "walk" in str(s.get("supplier_name_en", "")).lower()), None)
        if cash:
            self.sup_cb.set(f"{cash['supplier_code']} — {cash['supplier_name_en']}")

    def _next_number(self):
        try:
            from modules.doc_numbering import next_number
            return next_number("purchase_invoices", "invoice_number",
                               str(cfg.get("purchase_prefix") or "PI").strip() or "PI")
        except Exception:
            ym = datetime.now().strftime("%Y%m")
            return f"PI-{ym}-000001"

    # ── nav / find ────────────────────────────────────────────
    def _toggle_find(self):
        on = self.find_on.get()
        self.find_entry.configure(state="normal" if on else "disabled")
        if on:
            self.find_entry.focus_set()

    def _find(self):
        num = self.find_var.get().strip()
        if not num:
            return
        row = db.fetchone("SELECT purchase_id FROM purchase_invoices "
                          "WHERE invoice_number=?", (num,))
        if not row:
            row = db.fetchone("SELECT TOP 1 purchase_id FROM purchase_invoices "
                              "WHERE invoice_number LIKE ? ORDER BY purchase_id DESC",
                              ("%" + num + "%",))
        if row:
            self._goto(row["purchase_id"])
        else:
            messagebox.showinfo("Not found", f"No purchase matching '{num}'.")

    def _nav_prev(self):
        cur = self.purchase_id
        if cur:
            row = db.fetchone("SELECT TOP 1 purchase_id FROM purchase_invoices "
                              "WHERE purchase_id<? ORDER BY purchase_id DESC", (cur,))
        else:
            row = db.fetchone("SELECT TOP 1 purchase_id FROM purchase_invoices "
                              "ORDER BY purchase_id DESC")
        if row:
            self._goto(row["purchase_id"])
        else:
            messagebox.showinfo("Navigation", "No earlier purchase.")

    def _nav_next(self):
        cur = self.purchase_id
        if not cur:
            messagebox.showinfo("Navigation", "Already on a new purchase.")
            return
        row = db.fetchone("SELECT TOP 1 purchase_id FROM purchase_invoices "
                          "WHERE purchase_id>? ORDER BY purchase_id ASC", (cur,))
        if row:
            self._goto(row["purchase_id"])
        else:
            messagebox.showinfo("Navigation", "This is the latest purchase.")

    def _goto(self, pid):
        self.purchase_id = pid
        try:
            self.grid.set_lines([])
        except Exception:
            pass
        self._load_data()

    def _load_data(self):
        inv = db.fetchone("SELECT * FROM purchase_invoices WHERE purchase_id=?",
                          (self.purchase_id,))
        if not inv:
            return
        self.hdr["number"].set(inv.get("invoice_number", ""))
        self.hdr["date"].set(str(inv.get("invoice_date", "")))
        self.hdr["supinv"].set(inv.get("supplier_invoice_no", "") or "")
        self.hdr["payment"].set(inv.get("payment_method", "credit") or "credit")
        sid = inv.get("supplier_id")
        if sid:
            s = next((x for x in self.suppliers if x["supplier_id"] == sid), None)
            if s:
                self.sup_cb.set(f"{s['supplier_code']} — {s['supplier_name_en']}")
        lines = db.fetchall("SELECT * FROM purchase_invoice_lines WHERE purchase_id=? "
                            "ORDER BY line_number", (self.purchase_id,))
        try:
            self.grid.set_lines([dict(l) for l in lines])
        except Exception:
            pass
        self._on_change()

    # ── save ──────────────────────────────────────────────────
    def _save(self, confirm=False, keep_open=False):
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "edit" if self.purchase_id else "add"):
            return False
        try:
            self._lines = self.grid.data_lines()
        except Exception:
            pass
        if self.sup_cb.current() < 0:
            self.status_var.set("⚠️  Select a supplier.")
            return
        if not self._lines:
            self.status_var.set("⚠️  Add at least one item.")
            return
        pdate = self.hdr["date"].get().strip()
        from modules.date_utils import validate_invoice_date
        ok, iso_date, err = validate_invoice_date(pdate)
        if not ok:
            self.status_var.set(f"⚠️  {err}")
            return
        self.hdr["date"].set(iso_date)
        try:
            from modules import financial_year as fy
            lock_msg = fy.guard_active(iso_date)
            if not lock_msg and self.purchase_id:
                from modules import doc_edit       # the saved document's own rules
                lock_msg = doc_edit.block_reason("purchase", self.purchase_id, "edit")
            if lock_msg:
                self.status_var.set(f"⚠️  {lock_msg}")
                return
        except Exception:
            pass
        self.status_var.set("")
        s = self.suppliers[self.sup_cb.current()]
        sub = sum(l.get("line_amount", 0) for l in self._lines)
        vat = sum(l.get("vat_amount", 0) for l in self._lines)
        total = sum(l.get("line_total", 0) for l in self._lines)
        status = "confirmed" if confirm else "draft"
        # paid now (cash / bank / card / cheque) or on the supplier's account
        method = str(self.hdr["payment"].get() or "credit").lower()
        paid = total if method in ("cash", "bank_transfer", "bank", "card", "cheque") else 0
        pay_status = "paid" if paid else "unpaid"
        if self.purchase_id:
            try:   # supplier payments settled on this purchase stay counted
                from modules import allocation
                paid = min(total, paid + allocation.allocated_total(
                    "disbursement", self.purchase_id))
                pay_status = ("paid" if paid >= total - 0.005 else
                              ("partial" if paid > 0.005 else "unpaid"))
            except Exception:
                pass
        # v5.27: header, lines, stock, cost and journal are ONE transaction
        _was_id, _tx = self.purchase_id, None
        try:
            _tx = db.begin()
            if self.purchase_id:
                db.execute("UPDATE purchase_invoices SET supplier_id=?, "
                           "supplier_invoice_no=?, invoice_date=?, payment_method=?, "
                           "subtotal_amount=?, taxable_amount=?, vat_amount=?, "
                           "total_amount=?, invoice_status=?, payment_status=?, "
                           "paid_amount=?, updated_at=GETDATE() "
                           "WHERE purchase_id=?",
                           (s["supplier_id"], self.hdr["supinv"].get() or None,
                            self.hdr["date"].get(), self.hdr["payment"].get(),
                            sub, sub, vat, total, status, pay_status, paid,
                            self.purchase_id))
                db.execute("DELETE FROM purchase_invoice_lines WHERE purchase_id=?",
                           (self.purchase_id,))
                pid = self.purchase_id
            else:
                pnum = self._next_number()
                db.execute("INSERT INTO purchase_invoices (invoice_number, "
                           "supplier_invoice_no, invoice_date, supplier_id, "
                           "supplier_name_en, supplier_name_ar, supplier_vat_no, "
                           "payment_method, subtotal_amount, taxable_amount, "
                           "vat_amount, total_amount, invoice_status, payment_status, "
                           "paid_amount) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (pnum, self.hdr["supinv"].get() or None,
                            self.hdr["date"].get(), s["supplier_id"],
                            s["supplier_name_en"], s.get("supplier_name_ar", ""),
                            s.get("vat_registration_no", ""), self.hdr["payment"].get(),
                            sub, sub, vat, total, status, pay_status, paid))
                pid = db.last_identity("purchase_invoices", "purchase_id")
            self.purchase_id = pid
            for i, ln in enumerate(self._lines, 1):
                db.execute("INSERT INTO purchase_invoice_lines (purchase_id, "
                           "line_number, product_id, product_code, product_name_en, "
                           "quantity, unit_of_measure_en, unit_price, line_amount, "
                           "vat_category_id, vat_rate, vat_amount, line_total) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (pid, i, ln.get("product_id"), ln.get("product_code", ""),
                            ln.get("product_name_en", ""), ln.get("quantity", 0),
                            ln.get("unit_of_measure_en", "Unit"), ln.get("unit_price", 0),
                            ln.get("line_amount", 0), ln.get("vat_category_id"),
                            ln.get("vat_rate", 15), ln.get("vat_amount", 0),
                            ln.get("line_total", 0)))
                if ln.get("batch_no") or ln.get("expiry_date"):     # v6.0 batches
                    try:
                        with db.savepoint():
                            db.execute("UPDATE purchase_invoice_lines SET batch_no=?, expiry_date=? "
                                       "WHERE purchase_id=? AND line_number=?",
                                       (ln.get("batch_no"), ln.get("expiry_date"), pid, i))
                    except Exception:
                        pass
            # ── Stock + cost + accounts (one engine for every document) ──
            # Draft → nothing moves. Confirmed → stock in (base units),
            # weighted-average cost, purchase journal. Editing re-syncs.
            from modules import doc_posting
            try:
                doc_posting.sync("purchase", pid)
            except Exception as e:
                doc_posting.last_warning = str(e)[:200]
            _tx.commit()            # kept together — or the except below undoes it all
            if keep_open:                         # saved on the way to printing
                self.status_var.set(f"💾 Saved {self.hdr['number'].get()} "
                                    f"({'confirmed' if confirm else 'draft'}).")
            elif confirm:
                messagebox.showinfo("Saved", f"Purchase invoice {self.hdr['number'].get()} "
                                    f"confirmed.\nStock and accounts updated.")
                doc_posting.notify(self.win)
            if confirm:
                self._cost_up_hint(pid)
            else:
                messagebox.showinfo("Saved", f"Purchase {self.hdr['number'].get()} saved "
                                    f"as DRAFT.\nStock and accounts update when you "
                                    f"confirm it (Save & Confirm or ✅ Confirm).")
            if self.on_save:
                try:
                    self.on_save()
                except Exception:
                    pass
            if not keep_open:
                self.win.destroy()
            return True
        except Exception as e:
            if _tx is not None and not _tx.kept:
                _tx.rollback()                       # nothing of a failed save is kept
                self.purchase_id = _was_id
                e = "Not saved — " + str(e)
            self.status_var.set(f"❌ {str(e)[:90]}")

    def _cost_up_hint(self, pid):
        """v6.4: this purchase made some items cost more → say so once
        (Inventory ▸ Price Updates suggests prices that keep the margin)."""
        try:
            from modules import price_update as PU
            ids = [ln.get("product_id") for ln in (self._lines or []) if ln.get("product_id")]
            rows = PU.suggestions(product_ids=ids) if ids else []
            self.cost_up = rows
            if rows:
                from ui.ui_polish import toast
                toast(self.win.winfo_toplevel() if self.win.winfo_exists() else self.win.master,
                      "📈 Cost went up on %d item(s) — Inventory ▸ Price Updates" % len(rows))
        except Exception:
            pass

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth(); sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{max(0,(sh-h)//2-20)}")
