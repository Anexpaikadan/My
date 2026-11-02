# ============================================================
# Saudi Arabia ERP - Customer Module
# Full CRUD: List + Add + Edit + Delete
# B2B / B2C | VAT Number Validation | Bilingual Arabic/English
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t, is_rtl
from config.database import db
from modules import permissions as perm


# ─────────────────────────────────────────────────────────────
# CUSTOMER LIST VIEW
# ─────────────────────────────────────────────────────────────
class CustomersView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()

        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        self._build_topbar(C)
        self._build_stats(C)
        self._build_table(C)
        self._load_customers()

    # ── Top action bar ────────────────────────────────────────
    def _build_topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))

        # Title
        tk.Label(bar, text=f"👥  {t('nav.customers')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        # Right-side buttons
        btn_frame = tk.Frame(bar, bg=C["content_bg"])
        btn_frame.pack(side="right")

        # v6.8: answers from the Tally web forms (customers fill them on their phone)
        try:
            from modules import online_forms as _OF
            _n = _OF.counts().get("customer", 0)
        except Exception:
            _n = 0
        self.online_btn = tk.Button(btn_frame, text="🌐  Online forms" + ("  (%d new)" % _n if _n else ""),
                  font=("Segoe UI", 9, "bold" if _n else "normal"),
                  bg=C["card_bg"], fg=C["primary"] if _n else C["text_primary"],
                  relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["primary"] if _n else C["border"], highlightthickness=1,
                  command=lambda: __import__("ui.online_forms_view", fromlist=["x"]).open_window(
                      self.frame, "customer"))
        self.online_btn.pack(side="left", padx=(0, 8))
        # Export button
        tk.Button(btn_frame, text=f"📥  {t('common.export')}",
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                  relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export_excel).pack(side="left", padx=(0, 8))

        # Print (PDF list) button
        tk.Button(btn_frame, text="🖨  Print",
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                  relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export_pdf).pack(side="left", padx=(0, 8))

        # New Customer button
        tk.Button(btn_frame, text=f"＋  {t('customer.new')}",
                  font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white",
                  relief="flat", padx=16, pady=7, cursor="hand2",
                  activebackground=C["primary_dark"],
                  command=self._open_add_form).pack(side="left")

    # ── Stats row ─────────────────────────────────────────────
    def _build_stats(self, C):
        self.stats_frame = tk.Frame(self.frame, bg=C["content_bg"])
        self.stats_frame.pack(fill="x", padx=24, pady=(14, 0))

    def _refresh_stats(self, data):
        C = cfg.theme()
        for w in self.stats_frame.winfo_children():
            w.destroy()

        total   = len(data)
        b2b     = sum(1 for r in data if r.get("customer_type") == "B2B")
        b2c     = total - b2b
        active  = sum(1 for r in data if r.get("is_active"))

        stats = [
            ("👥", "Total",   str(total),  C["primary"]),
            ("🏢", "B2B",     str(b2b),    C["info"]),
            ("👤", "B2C",     str(b2c),    C["success"]),
            ("✅", "Active",  str(active), C["success"]),
        ]
        for icon, label, val, color in stats:
            card = tk.Frame(self.stats_frame, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 10), ipadx=12, ipady=6)
            tk.Label(card, text=f"{icon}  {label}",
                     font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=val,
                     font=("Segoe UI", 16, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w", padx=8, pady=(0, 6))

    # ── Search + Filter bar ───────────────────────────────────
    def _build_search(self, C, parent):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(14, 0))

        # Search box
        search_frame = tk.Frame(bar, bg="white",
                                highlightbackground=C["border"], highlightthickness=1)
        search_frame.pack(side="left")
        tk.Label(search_frame, text="🔍", font=("Segoe UI Emoji", 11),
                 bg="white", fg=C["text_secondary"]).pack(side="left", padx=(10, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._filter_table())
        tk.Entry(search_frame, textvariable=self.search_var,
                 font=("Segoe UI", 10), bg="white", relief="flat",
                 width=28, fg=C["text_primary"]).pack(
                     side="left", ipady=7, padx=(0, 10))

        # Type filter
        self.type_var = tk.StringVar(value="All")
        type_frame = tk.Frame(bar, bg=C["content_bg"])
        type_frame.pack(side="left", padx=12)
        tk.Label(type_frame, text="Type:", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        for val in ["All", "B2B", "B2C"]:
            tk.Radiobutton(type_frame, text=val, variable=self.type_var, value=val,
                           font=("Segoe UI", 9), bg=C["content_bg"],
                           fg=C["text_primary"], activebackground=C["content_bg"],
                           command=self._filter_table).pack(side="left", padx=4)

        # Active filter
        self.active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="Active only",
                       variable=self.active_var, command=self._filter_table,
                       font=("Segoe UI", 9), bg=C["content_bg"],
                       fg=C["text_secondary"]).pack(side="left", padx=8)

        # Record count label
        self.count_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.count_var,
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="right")

    # ── Data Table ────────────────────────────────────────────
    def _build_table(self, C):
        # Search bar above table
        self._build_search(C, self.frame)

        wrapper = tk.Frame(self.frame, bg=C["content_bg"])
        wrapper.pack(fill="both", expand=True, padx=24, pady=(10, 24))

        # Card wrapper
        card = tk.Frame(wrapper, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)

        # Column definitions
        cols = ("code", "name_en", "name_ar", "type", "vat_no", "phone", "city", "balance", "status")
        headers = {
            "code":    ("Code",         70,  "center"),
            "name_en": ("Name (EN)",    160, "w"),
            "name_ar": ("الاسم (AR)",   160, "e"),
            "type":    ("Type",         60,  "center"),
            "vat_no":  ("VAT Number",   130, "center"),
            "phone":   ("Phone",        110, "center"),
            "city":    ("City",         100, "center"),
            "balance": ("Balance SAR",  110, "e"),
            "status":  ("Status",       70,  "center"),
        }

        # Style
        style = ttk.Style()
        style.configure("Cust.Treeview",
                         background="white", foreground=C["text_primary"],
                         fieldbackground="white", rowheight=34,
                         font=("Segoe UI", 9))
        style.configure("Cust.Treeview.Heading",
                         background=C["content_bg"], foreground=C["text_secondary"],
                         font=("Segoe UI", 9, "bold"), relief="flat", padding=(8, 6))
        style.map("Cust.Treeview",
                  background=[("selected", C.get("select_bg", C["primary"]))],
                  foreground=[("selected", C.get("select_fg", "white"))])

        # Scrollbar
        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(card, orient="horizontal")
        hsb.pack(side="bottom", fill="x")

        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                  style="Cust.Treeview",
                                  yscrollcommand=vsb.set,
                                  xscrollcommand=hsb.set)
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        for col in cols:
            h, w, anchor = headers[col]
            self.tree.heading(col, text=h,
                              command=lambda c=col: self._sort_column(c))
            self.tree.column(col, width=w, anchor=anchor, minwidth=50)

        self.tree.pack(fill="both", expand=True)

        # Row color tags
        self.tree.tag_configure("b2b",    background="#EFF6FF")
        self.tree.tag_configure("b2c",    background="#F0FDF4")
        self.tree.tag_configure("inactive", foreground="#9CA3AF")
        self.tree.tag_configure("even",   background="#FAFAFA")

        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self._open_edit_form())
        self.tree.bind("<Delete>",   lambda e: self._delete_customer())

        # Right-click menu
        self._build_context_menu()

        # Bottom action bar
        self._build_bottom_bar(C, wrapper)

    def _build_bottom_bar(self, C, parent):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(6, 0))

        tk.Button(bar, text=f"✏️  {t('customer.edit')}",
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._open_edit_form).pack(side="left", padx=(0, 6))

        tk.Button(bar, text="🧾  Statement",
                  font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._statement).pack(side="left", padx=(0, 6))

        tk.Button(bar, text="⭐  Points",                    # v6.9.2 loyalty
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._points).pack(side="left", padx=(0, 6))

        tk.Button(bar, text="💳  Loyalty QR card",            # v7.5
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._loyalty_card).pack(side="left", padx=(0, 6))

        tk.Button(bar, text=f"🗑  {t('customer.delete')}",
                  font=("Segoe UI", 9), bg="#FEF2F2", fg=C["danger"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._delete_customer).pack(side="left")

        tk.Button(bar, text="🔄  Refresh",
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load_customers).pack(side="right")

    def _build_context_menu(self):
        C = cfg.theme()
        self.ctx_menu = tk.Menu(self.tree, tearoff=0,
                                 bg="white", fg=C["text_primary"],
                                 font=("Segoe UI", 9), relief="flat")
        self.ctx_menu.add_command(label="✏️  Edit Customer",   command=self._open_edit_form)
        self.ctx_menu.add_command(label="👁  View Details",    command=self._view_customer)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🧾  Account Statement", command=self._statement)
        self.ctx_menu.add_command(label="⭐  Loyalty points", command=self._points)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🗑  Delete",          command=self._delete_customer,
                                   foreground=C["danger"])
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.ctx_menu.post(event.x_root, event.y_root)

    # ── Load / Filter Data ────────────────────────────────────
    def _load_customers(self):
        try:
            self._all_data = db.fetchall(
                "SELECT c.customer_id, c.customer_code, c.customer_name_en, "
                "c.customer_name_ar, c.customer_type, c.vat_registration_no, "
                "c.phone, c.city_en, c.is_active, c.credit_limit, "
                "ISNULL(v.balance_due, 0) AS balance_due "
                "FROM customers c "
                "LEFT JOIN vw_customer_balance v ON c.customer_id = v.customer_id "
                "ORDER BY c.customer_name_en"
            )
        except Exception as e:
            self._all_data = []
            messagebox.showerror("DB Error", str(e))
        self._filter_table()

    def _filter_table(self):
        query   = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        ctype   = self.type_var.get()           if hasattr(self, "type_var") else "All"
        active  = self.active_var.get()          if hasattr(self, "active_var") else True

        filtered = []
        for row in self._all_data:
            if active and not row.get("is_active"):
                continue
            if ctype != "All" and row.get("customer_type") != ctype:
                continue
            if query:
                searchable = (
                    str(row.get("customer_code", "")) +
                    str(row.get("customer_name_en", "")) +
                    str(row.get("customer_name_ar", "")) +
                    str(row.get("vat_registration_no", "")) +
                    str(row.get("phone", ""))
                ).lower()
                if query not in searchable:
                    continue
            filtered.append(row)

        self._populate_table(filtered)
        self._refresh_stats(self._all_data)

        if hasattr(self, "count_var"):
            self.count_var.set(f"{len(filtered)} record(s)")

    def _populate_table(self, data):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(data):
            status = "✅ Active" if row.get("is_active") else "⛔ Inactive"
            ctype  = row.get("customer_type", "B2C")
            bal    = row.get("balance_due", 0)
            tags   = []
            if ctype == "B2B":
                tags.append("b2b")
            else:
                tags.append("b2c")
            if not row.get("is_active"):
                tags.append("inactive")
            elif i % 2 == 0:
                tags.append("even")

            self.tree.insert("", "end",
                iid=str(row["customer_id"]),
                values=(
                    row.get("customer_code", ""),
                    row.get("customer_name_en", ""),
                    row.get("customer_name_ar", ""),
                    ctype,
                    row.get("vat_registration_no", "") or "—",
                    row.get("phone", "") or "—",
                    row.get("city_en", "") or "—",
                    f"{bal:,.2f}" if bal else "0.00",
                    status
                ),
                tags=tuple(tags)
            )

    def _sort_column(self, col):
        data = [(self.tree.set(child, col), child)
                for child in self.tree.get_children("")]
        data.sort(key=lambda x: x[0].lower())
        for i, (_, child) in enumerate(data):
            self.tree.move(child, "", i)

    # ── CRUD Actions ──────────────────────────────────────────
    def _get_selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a customer first.")
            return None
        return int(sel[0])

    def _open_add_form(self):
        if not perm.allowed("customers", "add", parent=self.frame):
            return
        CustomerForm(self.frame, customer_id=None, on_save=self._load_customers)

    def _open_edit_form(self):
        cid = self._get_selected_id()
        if cid:
            # no edit right = the form opens read-only
            CustomerForm(self.frame, customer_id=cid, on_save=self._load_customers,
                         view_only=not perm.can("customers", "edit"))

    def _view_customer(self):
        cid = self._get_selected_id()
        if cid:
            CustomerForm(self.frame, customer_id=cid, on_save=self._load_customers,
                         view_only=True)

    def _view_invoices(self):
        cid = self._get_selected_id()
        if not cid:
            messagebox.showinfo("Select", "Select a customer first.")
            return
        try:
            from ui.party_statement import open_customer_statement
            open_customer_statement(self.frame, cid)
        except Exception as e:
            messagebox.showerror("Statement", str(e)[:200])

    @perm.guard("customers", "reports")
    def _statement(self):
        self._view_invoices()

    def _points(self):
        """⭐ the customer's loyalty points (v6.9.2)."""
        cid = self._get_selected_id()
        if not cid:
            messagebox.showinfo("Select", "Select a customer first.")
            return
        from ui.loyalty_view import LoyaltyDialog
        LoyaltyDialog(self.frame, cid)

    def _loyalty_card(self):
        """💳 the customer's QR card: make, send on WhatsApp, print (v7.5)."""
        cid = self._get_selected_id()
        if not cid:
            messagebox.showinfo("Select", "Select a customer first.")
            return None
        if not perm.allowed("customers", "edit", parent=self.frame):
            return None
        return LoyaltyCardDialog(self.frame, cid)

    @perm.guard("customers", "delete")
    def _delete_customer(self):
        cid = self._get_selected_id()
        if not cid:
            return
        sel = self.tree.item(str(cid))["values"]
        name = sel[1]
        if not messagebox.askyesno(
            t("common.warning"),
            f"{t('common.confirm_delete')}\n\n{name}"
        ):
            return
        try:
            # Check if customer has invoices
            count = db.execute_scalar(
                "SELECT COUNT(*) FROM sales_invoices WHERE customer_id = ?", (cid,))
            if count and count > 0:
                messagebox.showerror(
                    t("common.error"),
                    f"Cannot delete. Customer has {count} invoice(s).\n"
                    "Deactivate the customer instead."
                )
                return
            db.execute("DELETE FROM customers WHERE customer_id = ?", (cid,))
            try:
                from modules.doc_actions import audit
                audit("delete", "customer", cid, name)
            except Exception:
                pass
            messagebox.showinfo(t("common.success"), f"Customer '{name}' deleted.")
            self._load_customers()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_pdf(self):
        """Printable PDF of the customer list (respects current filter/sort)."""
        if not self.tree.get_children():
            messagebox.showinfo("Customers", "No customers to print.")
            return
        headers = ["Code", "Name (EN)", "Name (AR)", "Type", "VAT Number",
                   "Phone", "City", "Balance SAR", "Status"]
        try:
            from modules.doc_actions import export_tree_pdf
            export_tree_pdf(self.frame, self.tree, "Customers", headers,
                            title="Customer List",
                            col_align=["center", "left", "right", "center",
                                       "center", "center", "center", "right",
                                       "center"])
        except Exception as e:
            messagebox.showerror("Print", str(e)[:200])

    @perm.guard("customers", "export")
    def _export_excel(self):
        try:
            import openpyxl
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="Customers.xlsx"
            )
            if not path:
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Customers"
            headers = ["Code", "Name (EN)", "Name (AR)", "Type",
                       "VAT Number", "Phone", "City", "Balance SAR", "Status"]
            ws.append(headers)
            for child in self.tree.get_children():
                ws.append(list(self.tree.item(child)["values"]))
            wb.save(path)
            messagebox.showinfo(t("common.success"), f"Exported to:\n{path}")
        except ImportError:
            messagebox.showerror("Error", "openpyxl not installed.\npip install openpyxl")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))


# ─────────────────────────────────────────────────────────────
# CUSTOMER FORM (Add / Edit / View)
# ─────────────────────────────────────────────────────────────
class LoyaltyCardDialog:
    """💳 Loyalty QR card: the QR picture, 🔄 new card, 💬 WhatsApp, 🖨 card PDF."""

    def __init__(self, parent, customer_id):
        import os, tempfile
        from modules import loyalty_qr as LQ
        self.LQ, self.cid, self.code = LQ, int(customer_id), None
        C = cfg.theme()
        c = db.fetchone("SELECT * FROM customers WHERE customer_id=?", (self.cid,)) or {}
        self.win = tk.Toplevel(parent)
        self.win.title("💳 Loyalty card — %s" % (c.get("customer_name_en") or ""))
        self.win.configure(bg=C["content_bg"]); self.win.geometry("560x420")
        self._no_close_confirm = True
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        tk.Label(self.win, text="💳  %s  (%s)" % (c.get("customer_name_en") or "", c.get("customer_code") or ""),
                 font=("Segoe UI", 12, "bold"), bg=C["content_bg"], fg=C["text_primary"]).pack(anchor="w", padx=14,
                                                                                               pady=(12, 2))
        tk.Label(self.win, text="Scanning the card at the POS / Sales Invoice picks this customer (price list and "
                                "loyalty points come with them). A new card stops the old one.",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"], wraplength=520,
                 justify="left").pack(anchor="w", padx=14)
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=14, pady=8)
        self.qr_lbl = tk.Label(body, text=("Card made — press 🔄 to print / send a new one" if LQ.has_card(self.cid)
                                           else "No card yet — press 🔄 New card"),
                               bg="white", width=30, height=12, wraplength=200)
        self.qr_lbl.pack(side="left")
        r = tk.Frame(body, bg=C["content_bg"]); r.pack(side="left", fill="both", expand=True, padx=12)
        tk.Label(r, text="Mobile (WhatsApp)", bg=C["content_bg"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.phone = tk.StringVar(value=c.get("mobile") or c.get("phone") or "")
        tk.Entry(r, textvariable=self.phone, relief="solid", bd=1, font=("Segoe UI", 11)).pack(fill="x")
        for txt, cmd in (("🔄 New card", self.new), ("💬 Send on WhatsApp", self.send), ("🖨 Card PDF", self.pdf)):
            tk.Button(r, text=txt, relief="flat", bg=C["primary"] if txt.startswith("🔄") else C["card_bg"],
                      fg="white" if txt.startswith("🔄") else C["text_primary"], padx=10, pady=5, cursor="hand2",
                      command=cmd).pack(fill="x", pady=(8, 0))
        self.msg = tk.StringVar()
        self.msg_lbl = tk.Label(self.win, textvariable=self.msg, bg=C["content_bg"], fg="#047857", wraplength=520,
                                justify="left", font=("Segoe UI", 9, "bold"))
        self.msg_lbl.pack(fill="x", padx=14, pady=(0, 10))
        # v7.6: a failure reads red, a success green (not every note in green)
        self.msg.trace_add("write", lambda *a: self.msg_lbl.config(
            fg=C["danger"] if self.msg.get().startswith(("❌", "⚠")) else "#047857"))
        self._os, self._tmp = os, tempfile

    def new(self, quiet=False):
        if self.LQ.has_card(self.cid) and not quiet and not messagebox.askyesno(
                "Loyalty card", "Make a new card? The old card stops working.", parent=self.win):
            return None
        try:
            self.code = self.LQ.make(self.cid)
        except ValueError as e:
            messagebox.showwarning("Loyalty card", str(e), parent=self.win)
            return None
        path = self._os.path.join(self._tmp.gettempdir(), "daybill_card_%d.png" % self.cid)
        self.LQ.png(self.code, path, box=6)
        try:
            self._img = tk.PhotoImage(file=path)
            self.qr_lbl.config(image=self._img, text="", width=0, height=0)
        except Exception:
            self.qr_lbl.config(text=self.code)
        self.msg.set("✅ New card made — send it or print it now.")
        return self.code

    def _need(self):
        return self.code or self.new(quiet=not self.LQ.has_card(self.cid)) if not self.code else self.code

    def send(self):
        code = self._need()
        if not code:
            return
        ok, how = self.LQ.send_whatsapp(self.cid, code, self.phone.get().strip())
        self.msg.set(("✅ " if ok else "❌ ") + how)

    def pdf(self):
        code = self._need()
        if not code:
            return None
        p = self.LQ.card_pdf(self.cid, code)
        self.msg.set("✅ Card: %s" % p)
        try:
            from modules import printer_service as ps
            ps.open_file(p)
        except Exception:
            pass
        return p


class CustomerForm:
    def __init__(self, parent, customer_id=None, on_save=None, view_only=False):
        self.parent      = parent
        self.customer_id = customer_id
        self.on_save     = on_save
        self.view_only   = view_only
        self.fields      = {}   # key -> StringVar/BooleanVar
        self._build_window()
        if customer_id:
            self._load_data()
        else:
            self._apply_new_defaults()

    def _apply_new_defaults(self):
        """Settings > Customer: auto code + default credit limit."""
        try:
            if cfg.flag("cust_auto_code", True) and "customer_code" in self.fields:
                from modules.doc_numbering import next_party_code
                self.fields["customer_code"].set(next_party_code(
                    "customers", "customer_code", cfg.get("cust_prefix", "C")))
            lim = float(cfg.get("pay_default_credit_limit", 0) or 0)
            if lim and "credit_limit" in self.fields and not str(self.fields["credit_limit"].get()).strip("0. "):
                self.fields["credit_limit"].set(("%.2f" % lim))
        except Exception:
            pass

    GEOM_KEY = "customer_form_geometry_v525"
    BASE_SIZE = (820, 470)          # at 100 % text; grows with Settings ▸ Text size
    MIN_SIZE = (700, 430)

    def _build_window(self):
        """Pop-up like the Product window: normal size, centred, three
        pages (Basic & Tax · Address · Contact & Credit) — no scrolling."""
        from ui import form_kit as FK
        from ui.fluent_widgets import PageNav
        C = cfg.theme()
        self.C = C
        is_edit = self.customer_id is not None
        is_view = self.view_only

        title = (t("customer.new") if not is_edit
                 else (t("customer.edit") if not is_view else "View Customer"))

        self.win = FK.popup(title, self.BASE_SIZE, self.MIN_SIZE, self.GEOM_KEY,
                            parent=self.parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.configure(bg=C["content_bg"])

        icon = "👁" if is_view else ("✏️" if is_edit else "➕")
        FK.header(self.win, C, f"{icon}  {title}",
                  f"ID: {self.customer_id}" if is_edit and not is_view else "")

        self._build_footer(C)          # footer first: always visible

        outer = tk.Frame(self.win, bg=C["content_bg"])
        outer.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        self._pagenav = PageNav(outer, C)
        self._pagenav.frame.pack(fill="both", expand=True)
        self.page_basic = self._pagenav.add_page("Basic & Tax", "📋")
        self.page_address = self._pagenav.add_page("Address", "📍")
        self.page_contact = self._pagenav.add_page("Contact & Credit", "📞")
        self._pagenav.show_page(self.page_basic)
        self.body = self.page_basic
        self._build_form(C)
        if not is_view:
            self.win.bind("<Control-s>", lambda e=None: self._save())
            self.win.bind("<F4>", lambda e=None: self._save())

    def _build_form(self, C):
        from ui import form_kit as FK
        from ui.fluent_widgets import labeled_toggle
        state = "disabled" if self.view_only else "normal"
        F = self.fields

        def var(key, value=""):
            F[key] = tk.StringVar(value=value)
            return F[key]

        # ── page 1: Basic & Tax ───────────────────────────────
        left, right = FK.two_cols(self.page_basic, C)
        FK.section(left, C, t("customer.type"), "🏢")
        type_row = tk.Frame(left, bg=C["content_bg"])
        type_row.pack(anchor="w", padx=14, pady=(4, 2))
        self.type_var = tk.StringVar(value="B2C")
        F["customer_type"] = self.type_var
        self.b2c_btn = tk.Radiobutton(
            type_row, text=f"👤  {t('customer.b2c')}", variable=self.type_var,
            value="B2C", font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
            fg=C["success"], activebackground=C["content_bg"], indicatoron=False,
            relief="solid", padx=14, pady=5, bd=1, state=state,
            command=self._on_type_change)
        self.b2c_btn.pack(side="left", padx=(0, 8))
        self.b2b_btn = tk.Radiobutton(
            type_row, text=f"🏢  {t('customer.b2b')}", variable=self.type_var,
            value="B2B", font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
            fg=C["info"], activebackground=C["content_bg"], indicatoron=False,
            relief="solid", padx=14, pady=5, bd=1, state=state,
            command=self._on_type_change)
        self.b2b_btn.pack(side="left")

        FK.section(left, C, "Basic Information", "📋")
        g = FK.grid(left, C)
        _c, self.code_entry = FK.field(g, C, 0, 0, "Customer Code", var("customer_code"),
                                       kind="code", required=True, maxlen=20, state=state)
        FK.field(g, C, 1, 0, t("customer.name_en"), var("customer_name_en"),
                 required=True, maxlen=200, state=state, colspan=2)
        FK.field(g, C, 2, 0, t("customer.name_ar"), var("customer_name_ar"),
                 rtl=True, maxlen=200, state=state, colspan=2)

        from modules import country as _ctry
        _p = _ctry.profile()
        FK.section(right, C, {"SA": "Tax (ZATCA)", "AE": "Tax (FTA)", "IN": "GST"}.get(_p["code"], "Tax"), "🧾")
        g2 = FK.grid(right, C, cols=1)
        _tax_label = (f"{t('customer.vat_no')}  (15 digits, starts with 3)" if _p["code"] == "SA"
                      else "%s  (%s)" % (_p["tax_no_label"], _p["tax_no_hint"]))
        vat_cell, self.vat_entry = FK.field(
            g2, C, 0, 0, _tax_label,
            var("vat_registration_no"), kind="vat", maxlen=15, state=state)
        self.vat_indicator = tk.Label(vat_cell, text="", font=("Segoe UI", 8),
                                      bg=C["content_bg"], fg=C["danger"])
        self.vat_indicator.pack(anchor="w")
        if state == "normal":
            F["vat_registration_no"].trace("w", self._validate_vat)
        cr_cell, _cr = FK.field(g2, C, 1, 0,
                                {"AE": "Trade Licence No.", "IN": "PAN"}.get(_p["code"], t("customer.cr_no")),
                                var("cr_number"), kind="vat", maxlen=20, state=state,
                                check=None if _p["code"] == "SA" else "cr")
        # v7.0: region / emirate / GST state (India: decides CGST+SGST or IGST)
        F["state_code"] = tk.StringVar()
        self.state_disp = tk.StringVar()
        _st = tk.Frame(g2, bg=C["content_bg"])
        _st.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        tk.Label(_st, text=_p["states_label"] + ("  (place of supply)" if _p["code"] == "IN" else ""),
                 font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(anchor="w")
        self.state_combo = ttk.Combobox(_st, textvariable=self.state_disp, width=34,
                                        values=["%s - %s" % (k, n) for k, n in _p["states"]],
                                        state="disabled" if state != "normal" else "readonly")
        self.state_combo.pack(anchor="w", pady=(2, 0), ipady=2)
        if state == "normal" and _p["code"] == "SA":
            _cr.pack_forget()
            row = tk.Frame(cr_cell, bg=C["content_bg"])
            row.pack(anchor="w", pady=(2, 0))
            _cr.pack(in_=row, side="left", ipady=4)
            _cr.lift(row)                 # made before the row: keep it on top
            tk.Button(row, text="⤓ Wathq", font=("Segoe UI", 8, "bold"),
                      bg=C["primary"], fg="white", relief="flat", padx=8,
                      cursor="hand2", command=self._wathq_fill).pack(side="left", padx=(6, 0))
        if state == "normal" and _p["code"] == "IN":
            F["vat_registration_no"].trace_add("write", lambda *a: self._state_from_gstin())
        FK.section(right, C, "Status", "✅")
        self.active_var = tk.BooleanVar(value=True)
        F["is_active"] = self.active_var
        if not self.view_only:
            labeled_toggle(right, "Active customer (shows in invoices)",
                           self.active_var, C, font_size=9)[0].pack(anchor="w", padx=14, pady=(4, 0))

        # ── page 2: Address (ZATCA Phase 2 needs it for B2B) ──
        pa = self.page_address
        tk.Label(pa, text="ZATCA Phase 2: B2B invoices need the full Saudi national address."
                 if _p["code"] == "SA" else "The address prints on tax invoices.",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=18, pady=(10, 2))
        ga = FK.grid(pa, C)
        FK.field(ga, C, 0, 0, "Building Number", var("building_number"),
                 kind="short", maxlen=10, state=state)
        FK.field(ga, C, 0, 1, "Postal Code", var("postal_code"),
                 kind="short", maxlen=10, state=state)
        FK.field(ga, C, 1, 0, "Street Name (EN)", var("street_name_en"), maxlen=200, state=state)
        FK.field(ga, C, 1, 1, "اسم الشارع (AR)", var("street_name_ar"), rtl=True,
                 maxlen=200, state=state)
        FK.field(ga, C, 2, 0, "District (EN)", var("district_en"), maxlen=100, state=state)
        FK.field(ga, C, 2, 1, "الحي (AR)", var("district_ar"), rtl=True,
                 maxlen=100, state=state)
        FK.field(ga, C, 3, 0, "City (EN)", var("city_en"), maxlen=100, state=state)
        FK.field(ga, C, 3, 1, "المدينة (AR)", var("city_ar"), rtl=True,
                 maxlen=100, state=state)
        FK.field(ga, C, 4, 0, "Country Code", var("country_code", _p["code"]),
                 kind="country", maxlen=3, state=state)

        # ── page 3: Contact & Credit ──────────────────────────
        lc, rc = FK.two_cols(self.page_contact, C)
        FK.section(lc, C, "Contact", "📞")
        gc = FK.grid(lc, C, cols=1)
        FK.field(gc, C, 0, 0, t("customer.phone"), var("phone"),
                 kind="phone", maxlen=20, state=state)
        FK.field(gc, C, 1, 0, t("customer.email"), var("email"), maxlen=100, state=state)
        FK.field(gc, C, 2, 0, "Contact Person (EN)", var("contact_person_en"),
                 maxlen=100, state=state)
        FK.field(gc, C, 3, 0, "Contact Person (AR)", var("contact_person_ar"), rtl=True,
                 maxlen=100, state=state)
        FK.section(rc, C, "Credit", "💰")
        gr = FK.grid(rc, C, cols=1)
        FK.field(gr, C, 0, 0, "Credit Limit (%s)" % _ctry.symbol(), var("credit_limit"),
                 kind="number", state=state)
        FK.field(gr, C, 1, 0, "Payment Terms (days)", var("payment_terms_days"),
                 kind="days", maxlen=4, state=state)
        FK.field(gr, C, 2, 0, "Opening Balance (%s)" % _ctry.symbol(), var("opening_balance"),
                 kind="number", state=state)
        # v6.0: the price list this customer buys at
        try:
            from modules import price_lists as _PL
            # (a list "based on the wholesale price" gives wholesale prices)
            _labels = [l for l, _k in _PL.choices() if _k != "wholesale"]
        except Exception:
            _PL, _labels = None, ["Standard"]
        self.price_list_var = tk.StringVar(value="Standard")
        _plc = tk.Frame(gr, bg=C["content_bg"])
        _plc.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        tk.Label(_plc, text="Price list", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.price_list_combo = ttk.Combobox(_plc, textvariable=self.price_list_var,
                                             values=_labels, width=24,
                                             state="disabled" if state != "normal" else "readonly")
        self.price_list_combo.pack(anchor="w", pady=(2, 0), ipady=2)
        tk.Label(rc, text="Opening balance is posted to the books when you save\n"
                          "(Dr customer / Cr Opening Balance Equity).",
                 font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"],
                 justify="left").pack(anchor="w", padx=14, pady=(2, 0))
        self._on_type_change()

    def _build_footer(self, C):
        from ui.fluent_widgets import RoundedButton
        footer = tk.Frame(self.win, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1)
        footer.pack(fill="x", side="bottom")

        inner = tk.Frame(footer, bg=C["card_bg"])
        inner.pack(fill="x", padx=16, pady=10)

        self.save_status = tk.StringVar()
        tk.Label(inner, textvariable=self.save_status, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["danger"], anchor="w", justify="left",
                 wraplength=420).pack(side="left", fill="x", expand=True)
        pills = tk.Frame(inner, bg=C["card_bg"])
        pills.pack(side="right")
        if not self.view_only:
            RoundedButton(pills, "Save  F4", command=self._save,
                          bg=C["primary"], width=100).pack(side="right", padx=(8, 0))
            if not self.customer_id:
                RoundedButton(pills, "Save & New", command=lambda: self._save(mode="new"),
                              bg="#2E86AB", width=110).pack(side="right", padx=(8, 0))
        RoundedButton(pills, "Cancel  Esc" if not self.view_only else "Close  Esc",
                      command=self.win.destroy, bg="#95A5A6",
                      width=132).pack(side="right", padx=(8, 0))

    # ── Type Toggle ───────────────────────────────────────────
    def _on_type_change(self):
        C = cfg.theme()
        is_b2b = self.type_var.get() == "B2B"
        # Highlight selected (selectcolor = the colour a pressed toggle shows)
        self.b2b_btn.config(
            bg=C["info"] if is_b2b else C["content_bg"],
            fg="white" if is_b2b else C["info"],
            selectcolor=C["info"], activeforeground="white" if is_b2b else C["info"],
            disabledforeground="white" if is_b2b else C["text_secondary"]
        )
        self.b2c_btn.config(
            bg=C["success"] if not is_b2b else C["content_bg"],
            fg="white" if not is_b2b else C["success"],
            selectcolor=C["success"], activeforeground="white" if not is_b2b else C["success"],
            disabledforeground="white" if not is_b2b else C["text_secondary"]
        )

    # ── VAT Validation ────────────────────────────────────────
    def _validate_vat(self, *args):
        C = cfg.theme()
        from modules import country as _ctry
        vat = self.fields["vat_registration_no"].get().strip()
        if not vat:
            self.vat_indicator.config(text="", fg=C["danger"])
            try:
                from ui import form_style as _FS
                if _FS.on():
                    self.vat_indicator.pack_forget()
            except Exception:
                pass
            return
        ok, msg = _ctry.valid_tax_no(vat)
        try:                        # v6.8: a wrong number gets the red note under the box
            from ui import form_style as _FS
            if _FS.on() and not ok:
                self.vat_indicator.config(text="")
                self.vat_indicator.pack_forget()
                return
            if not self.vat_indicator.winfo_manager():
                self.vat_indicator.pack(anchor="w")
        except Exception:
            pass
        label = _ctry.tax_no_label()
        if ok:
            self.vat_indicator.config(
                text=("✅ Valid ZATCA VAT number" if _ctry.is_sa() else "✅ Valid %s" % label),
                fg=C["success"])
        elif _ctry.is_sa() and len(vat) == 15 and vat.isdigit():
            self.vat_indicator.config(
                text="⚠️ Must start with 3", fg=C["warning"])
        else:
            self.vat_indicator.config(text="❌ " + msg, fg=C["danger"])

    def _state_from_gstin(self):
        """India: a GSTIN's first 2 digits are the customer's state."""
        from modules import country as _ctry
        g = self.fields["vat_registration_no"].get().strip().upper()
        if len(g) >= 2 and g[:2].isdigit():
            lab = _ctry.state_label(g[:2])
            if lab and lab != g[:2]:
                self.state_disp.set(lab)

    # ── Load Data ─────────────────────────────────────────────
    def _load_data(self):
        try:
            data = db.fetchone(
                "SELECT * FROM customers WHERE customer_id = ?",
                (self.customer_id,)
            )
            if not data:
                return
            for key, var in self.fields.items():
                val = data.get(key)
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(val))
                elif val is not None:
                    var.set(str(val))
            self.active_var.set(bool(data.get("is_active", 1)))
            try:
                from modules import price_lists as _PL
                _pk = data.get("price_list_id")
                self.price_list_var.set(_PL.label_for_key(int(_pk)) if _pk else _PL.STANDARD)
            except Exception:
                pass
            try:
                from modules import country as _ctry
                self.state_disp.set(_ctry.state_label(data.get("state_code")) if data.get("state_code") else "")
            except Exception:
                pass
            self._on_type_change()
            self._validate_vat()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customer: {e}")

    # ── Save ──────────────────────────────────────────────────

    def _wathq_fill(self):
        try:
            from modules import wathq
            ok, msg = wathq.fill_party_fields(self.fields,
                                              self.fields["cr_number"].get())
            (messagebox.showinfo if ok else messagebox.showwarning)("Wathq", msg)
        except Exception as e:
            messagebox.showerror("Wathq", str(e)[:200])

    def _save(self, mode="close"):
        # Enforce the right permission: adding a new customer needs
        # 'add', editing an existing one needs 'edit'.
        _need = "edit" if self.customer_id else "add"
        if not perm.can("customers", _need):
            messagebox.showwarning(
                "Access Denied",
                "You don't have permission to %s customers." % _need)
            return
        C = cfg.theme()

        # Validate required fields
        errors = []
        if not self.fields["customer_code"].get().strip():
            errors.append("Customer Code is required.")
        if not self.fields["customer_name_en"].get().strip():
            errors.append("Customer Name (EN) is required.")
        from modules import country as _ctry
        _lab = _ctry.tax_no_label()
        vat = self.fields["vat_registration_no"].get().strip()
        if self.type_var.get() == "B2B":
            if not vat:
                errors.append("%s required for B2B customers." % _lab)
            elif not _ctry.valid_tax_no(vat)[0]:
                errors.append(_ctry.valid_tax_no(vat)[1])
        elif vat and not _ctry.valid_tax_no(vat)[0]:
            errors.append(_ctry.valid_tax_no(vat)[1])
        # Settings ▸ Customer: extra mandatory fields
        try:
            if cfg.flag("cust_mandatory_mobile") and \
                    not self.fields["phone"].get().strip():
                errors.append("Mobile/Phone is required (Settings ▸ Customer).")
            if cfg.flag("cust_mandatory_vat") and \
                    not self.fields["vat_registration_no"].get().strip():
                errors.append("VAT Number is required (Settings ▸ Customer).")
        except Exception:
            pass

        try:                        # v6.8: red note under each wrong box (Tally style)
            from ui import form_style as _FS
            _fs_bad = _FS.validate(self.win, getattr(self, "_pagenav", None))
            if _fs_bad:               # the notes are under the boxes: keep the footer short
                _labs = [_l.split("  ")[0] for _l, _m in _fs_bad]
                _say = ["%s is required" % _l if _m.startswith("Please fill") else "%s: %s" % (_l, _m)
                        for _l, _m in [(_l.split("  ")[0], _m) for _l, _m in _fs_bad[:2]]]
                errors = ["; ".join(_say) + (" (+%d more)" % (len(_fs_bad) - 2) if len(_fs_bad) > 2 else "")
                          + " — see the red notes"] + [
                    e_ for e_ in errors if not any(_l in e_ or _l.split(" (")[0] in e_
                                                   for _l in _labs)]
        except Exception:
            _fs_bad = []

        if errors:
            self.save_status.set("⚠️  " + "  |  ".join(errors))
            try:                      # show the page that holds the problem
                if _fs_bad:
                    pass              # already shown + focused under its box
                elif any("Mobile" in e for e in errors) and len(errors) == 1:
                    self._pagenav.show_page(self.page_contact)
                else:
                    self._pagenav.show_page(self.page_basic)
            except Exception:
                pass
            return

        self.save_status.set("")

        # Build data dict
        def v(key, default=""):
            val = self.fields.get(key)
            if val is None:
                return default
            if isinstance(val, tk.BooleanVar):
                return 1 if val.get() else 0
            return val.get().strip() or default

        data = {
            "customer_code":        v("customer_code"),
            "customer_name_en":     v("customer_name_en"),
            "customer_name_ar":     v("customer_name_ar"),
            "customer_type":        v("customer_type", "B2C"),
            "vat_registration_no":  v("vat_registration_no") or None,
            "cr_number":            v("cr_number") or None,
            "building_number":      v("building_number") or None,
            "street_name_en":       v("street_name_en") or None,
            "street_name_ar":       v("street_name_ar") or None,
            "district_en":          v("district_en") or None,
            "district_ar":          v("district_ar") or None,
            "city_en":              v("city_en") or None,
            "city_ar":              v("city_ar") or None,
            "postal_code":          v("postal_code") or None,
            "country_code":         v("country_code", _ctry.code()),
            "phone":                v("phone") or None,
            "email":                v("email") or None,
            "contact_person_en":    v("contact_person_en") or None,
            "contact_person_ar":    v("contact_person_ar") or None,
            "credit_limit":         float(v("credit_limit", "0") or 0),
            "payment_terms_days":   int(v("payment_terms_days", "30") or 30),
            "opening_balance":      float(v("opening_balance", "0") or 0),
            "is_active":            1 if self.active_var.get() else 0,
        }

        try:                    # v7.0: region / emirate / GST state
            if db.execute_scalar("SELECT COL_LENGTH('customers','state_code')") is not None:
                data["state_code"] = _ctry.state_code_of(self.state_disp.get()) or None
        except Exception:
            pass

        _new_cid = None
        try:
            if self.customer_id:
                # UPDATE
                set_clause = ", ".join([f"{k} = ?" for k in data])
                sql = f"UPDATE customers SET {set_clause}, updated_at=GETDATE() WHERE customer_id = ?"
                db.execute(sql, (*data.values(), self.customer_id))
                msg = f"Customer '{data['customer_name_en']}' updated successfully."
            else:
                # INSERT
                cols = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))
                sql = f"INSERT INTO customers ({cols}) VALUES ({placeholders})"
                db.execute(sql, tuple(data.values()))
                _new_cid = db.last_identity("customers", "customer_id")   # this PC's row
                msg = f"Customer '{data['customer_name_en']}' added successfully."
                # Auto-create the customer's ledger account
                try:
                    from modules import posting
                    new_id = _new_cid
                    if new_id:
                        posting.ensure_party_account("customer", new_id)
                except Exception:
                    pass

            try:                       # v6.0: price list
                from modules import price_lists as _PL
                _cid = self.customer_id or _new_cid
                _key = _PL.key_for_label(self.price_list_var.get())
                if _cid and _PL.ready():
                    _PL.set_customer(_cid, _key if isinstance(_key, int) else None)
            except Exception:
                pass
            # opening balance → the books (Dr customer / Cr Opening Balance Equity)
            try:
                from modules import opening_balances as ob
                cid = self.customer_id or _new_cid
                if cid:
                    ob.post_party("customer", cid)
            except Exception:
                pass
            if mode == "new":
                try:
                    from ui.fluent_widgets import show_toast
                    show_toast(self.parent.winfo_toplevel(), "✓ " + msg)
                except Exception:
                    pass
            else:
                messagebox.showinfo(t("common.success"), msg)
            if self.on_save:
                self.on_save()
            if mode == "new":
                self.win.destroy()
                CustomerForm(self.parent, on_save=self.on_save)
            else:       # plain Save: Settings ▸ General ▸ After saving (v6.9.3)
                from ui import after_save
                parent, cb = self.parent, self.on_save
                cid = self.customer_id or _new_cid
                after_save.finish(self, "",
                                  new=lambda: CustomerForm(parent, on_save=cb),
                                  keep=(lambda: CustomerForm(parent, customer_id=cid,
                                                             on_save=cb)) if cid else None,
                                  edited=bool(self.customer_id))

        except Exception as e:
            err = str(e)
            if "UNIQUE" in err or "duplicate" in err.lower():
                self.save_status.set("❌ Customer code already exists.")
            else:
                self.save_status.set(f"❌ {err[:80]}")

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
