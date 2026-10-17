# ============================================================
# DayBill ERP - Suppliers Module
# Full CRUD: List + Add + Edit + Delete | Bilingual
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t, is_rtl
from config.database import db
from modules import permissions as perm


class SuppliersView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self._all_data = []
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build_topbar(C)
        self._build_search(C)
        self._build_table(C)
        self._load()

    def _build_topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text=f"🏭  {t('nav.suppliers')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        btns = tk.Frame(bar, bg=C["content_bg"])
        btns.pack(side="right")
        # v6.8: answers from the Tally web forms (customers fill them on their phone)
        try:
            from modules import online_forms as _OF
            _n = _OF.counts().get("supplier", 0)
        except Exception:
            _n = 0
        self.online_btn = tk.Button(btns, text="🌐  Online forms" + ("  (%d new)" % _n if _n else ""),
                  font=("Segoe UI", 9, "bold" if _n else "normal"),
                  bg=C["card_bg"], fg=C["primary"] if _n else C["text_primary"],
                  relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["primary"] if _n else C["border"], highlightthickness=1,
                  command=lambda: __import__("ui.online_forms_view", fromlist=["x"]).open_window(
                      self.frame, "supplier"))
        self.online_btn.pack(side="left", padx=(0, 8))
        tk.Button(btns, text="📥  Export", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="🖨  Print", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export_pdf).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="＋  New Supplier", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat",
                  padx=16, pady=7, cursor="hand2",
                  activebackground=C["primary_dark"],
                  command=self._add).pack(side="left")

    def _build_search(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(14, 0))
        sf = tk.Frame(bar, bg="white",
                      highlightbackground=C["border"], highlightthickness=1)
        sf.pack(side="left")
        tk.Label(sf, text="🔍", font=("Segoe UI Emoji", 11),
                 bg="white", fg=C["text_secondary"]).pack(side="left", padx=(10, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._filter())
        tk.Entry(sf, textvariable=self.search_var, font=("Segoe UI", 10),
                 bg="white", relief="flat", width=28,
                 fg=C["text_primary"]).pack(side="left", ipady=7, padx=(0, 10))
        self.active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="Active only", variable=self.active_var,
                       command=self._filter, font=("Segoe UI", 9),
                       bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left", padx=8)
        self.count_var = tk.StringVar()
        tk.Label(bar, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right")

    def _build_table(self, C):
        wrapper = tk.Frame(self.frame, bg=C["content_bg"])
        wrapper.pack(fill="both", expand=True, padx=24, pady=(10, 24))
        card = tk.Frame(wrapper, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)

        cols = ("code", "name_en", "name_ar", "vat_no", "phone", "city", "status")
        headers = {"code": ("Code", 80, "center"), "name_en": ("Name (EN)", 180, "w"),
                   "name_ar": ("الاسم (AR)", 160, "e"), "vat_no": ("VAT Number", 130, "center"),
                   "phone": ("Phone", 120, "center"), "city": ("City", 110, "center"),
                   "status": ("Status", 80, "center")}
        style = ttk.Style()
        style.configure("Sup.Treeview", background="white", foreground=C["text_primary"],
                        fieldbackground="white", rowheight=34, font=("Segoe UI", 9))
        style.configure("Sup.Treeview.Heading", background=C["content_bg"],
                        foreground=C["text_secondary"], font=("Segoe UI", 9, "bold"),
                        relief="flat", padding=(8, 6))
        style.map("Sup.Treeview", background=[("selected", C.get("select_bg", C["primary"]))],
                  foreground=[("selected", C.get("select_fg", "white"))])

        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 style="Sup.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for col in cols:
            h, w, a = headers[col]
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor=a, minwidth=50)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("even", background="#FAFAFA")
        self.tree.tag_configure("inactive", foreground="#9CA3AF")
        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.tree.bind("<Delete>", lambda e: self._delete())     # same check as the button

        bbar = tk.Frame(wrapper, bg=C["content_bg"])
        bbar.pack(fill="x", pady=(6, 0))
        tk.Button(bbar, text="✏️  Edit", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._edit).pack(side="left", padx=(0, 6))
        tk.Button(bbar, text="📦  Statement", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._statement).pack(side="left", padx=(0, 6))
        tk.Button(bbar, text="🗑  Delete", font=("Segoe UI", 9), bg="#FEF2F2",
                  fg=C["danger"], relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._delete).pack(side="left")
        tk.Button(bbar, text="🔄  Refresh", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load).pack(side="right")

    def _load(self):
        try:
            self._all_data = db.fetchall(
                "SELECT supplier_id, supplier_code, supplier_name_en, "
                "supplier_name_ar, vat_registration_no, phone, city_en, is_active "
                "FROM suppliers ORDER BY supplier_name_en")
        except Exception as e:
            self._all_data = []
            messagebox.showerror("DB Error", str(e))
        self._filter()

    def _filter(self):
        q = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        active = self.active_var.get() if hasattr(self, "active_var") else True
        rows = []
        for r in self._all_data:
            if active and not r.get("is_active"):
                continue
            if q:
                s = (str(r.get("supplier_code", "")) + str(r.get("supplier_name_en", "")) +
                     str(r.get("supplier_name_ar", "")) + str(r.get("vat_registration_no", "")) +
                     str(r.get("phone", ""))).lower()
                if q not in s:
                    continue
            rows.append(r)
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            tags = []
            if not r.get("is_active"):
                tags.append("inactive")
            elif i % 2 == 0:
                tags.append("even")
            self.tree.insert("", "end", iid=str(r["supplier_id"]), values=(
                r.get("supplier_code", ""), r.get("supplier_name_en", ""),
                r.get("supplier_name_ar", ""), r.get("vat_registration_no", "") or "—",
                r.get("phone", "") or "—", r.get("city_en", "") or "—",
                "✅ Active" if r.get("is_active") else "⛔ Inactive"), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} record(s)")

    def _sel_id(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", "Please select a supplier.")
            return None
        return int(s[0])

    @perm.guard("suppliers", "add")
    def _add(self):
        SupplierForm(self.frame, None, self._load)

    @perm.guard("suppliers", "edit")
    def _edit(self):
        sid = self._sel_id()
        if sid:
            SupplierForm(self.frame, sid, self._load)

    @perm.guard("suppliers", "reports")
    def _statement(self):
        sid = self._sel_id()
        if not sid:
            messagebox.showinfo("Select", "Select a supplier first.")
            return
        try:
            from ui.party_statement import open_supplier_statement
            open_supplier_statement(self.frame, sid)
        except Exception as e:
            messagebox.showerror("Statement", str(e)[:200])

    @perm.guard("suppliers", "delete")
    def _delete(self):
        sid = self._sel_id()
        if not sid:
            return
        name = self.tree.item(str(sid))["values"][1]
        if not messagebox.askyesno(t("common.warning"),
                                   f"{t('common.confirm_delete')}\n\n{name}"):
            return
        try:
            used = db.execute_scalar(
                "SELECT COUNT(*) FROM purchase_invoices WHERE supplier_id=?", (sid,))
            if used and used > 0:
                messagebox.showerror(t("common.error"),
                    f"Cannot delete. Supplier has {used} purchase invoice(s).")
                return
            db.execute("DELETE FROM suppliers WHERE supplier_id=?", (sid,))
            try:
                from modules.doc_actions import audit
                audit("delete", "supplier", sid, name)
            except Exception:
                pass
            messagebox.showinfo(t("common.success"), f"'{name}' deleted.")
            self._load()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_pdf(self):
        """Printable PDF of the supplier list (respects current filter/sort)."""
        if not self.tree.get_children():
            messagebox.showinfo("Suppliers", "No suppliers to print.")
            return
        headers = ["Code", "Name (EN)", "Name (AR)", "VAT Number",
                   "Phone", "City", "Status"]
        try:
            from modules.doc_actions import export_tree_pdf
            export_tree_pdf(self.frame, self.tree, "Suppliers", headers,
                            title="Supplier List",
                            col_align=["center", "left", "right", "center",
                                       "center", "center", "center"])
        except Exception as e:
            messagebox.showerror("Print", str(e)[:200])

    @perm.guard("suppliers", "export")
    def _export(self):
        try:
            import openpyxl
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")], initialfile="Suppliers.xlsx")
            if not path:
                return
            wb = openpyxl.Workbook(); ws = wb.active
            ws.append(["Code", "Name EN", "Name AR", "VAT", "Phone", "City", "Status"])
            for c in self.tree.get_children():
                ws.append(list(self.tree.item(c)["values"]))
            wb.save(path)
            messagebox.showinfo(t("common.success"), f"Exported:\n{path}")
        except ImportError:
            messagebox.showerror("Error", "pip install openpyxl")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))


class SupplierForm:
    """Pop-up like the Product window: normal size, centred, pages
    (Basic & Tax · Address · Contact & Payment) — no scrolling."""
    GEOM_KEY = "supplier_form_geometry_v525"
    BASE_SIZE = (820, 470)          # at 100 % text; grows with Settings ▸ Text size
    MIN_SIZE = (700, 430)

    def __init__(self, parent, supplier_id=None, on_save=None):
        from ui import form_kit as FK
        from ui.fluent_widgets import PageNav, labeled_toggle, RoundedButton
        self.parent = parent
        self.supplier_id = supplier_id
        self.on_save = on_save
        self.fields = {}
        C = cfg.theme()
        self.C = C
        is_edit = supplier_id is not None
        title = "Edit Supplier" if is_edit else "New Supplier"

        self.win = FK.popup(title, self.BASE_SIZE, self.MIN_SIZE, self.GEOM_KEY,
                            parent=parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.configure(bg=C["content_bg"])
        FK.header(self.win, C, f"{'✏️' if is_edit else '➕'}  {title}",
                  f"ID: {supplier_id}" if is_edit else "")

        # footer first: always visible
        footer = tk.Frame(self.win, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        inner = tk.Frame(footer, bg=C["card_bg"])
        inner.pack(fill="x", padx=16, pady=10)
        self.status_var = tk.StringVar()
        tk.Label(inner, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["danger"], anchor="w", justify="left",
                 wraplength=420).pack(side="left", fill="x", expand=True)
        pills = tk.Frame(inner, bg=C["card_bg"])
        pills.pack(side="right")
        RoundedButton(pills, "Save  F4", command=self._save,
                      bg=C["primary"], width=100).pack(side="right", padx=(8, 0))
        if not is_edit:
            RoundedButton(pills, "Save & New", command=lambda: self._save(mode="new"),
                          bg="#2E86AB", width=110).pack(side="right", padx=(8, 0))
        RoundedButton(pills, "Cancel  Esc", command=self.win.destroy,
                      bg="#95A5A6", width=132).pack(side="right", padx=(8, 0))

        outer = tk.Frame(self.win, bg=C["content_bg"])
        outer.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        self._pagenav = PageNav(outer, C)
        self._pagenav.frame.pack(fill="both", expand=True)
        self.page_basic = self._pagenav.add_page("Basic & Tax", "📋")
        self.page_address = self._pagenav.add_page("Address", "📍")
        self.page_contact = self._pagenav.add_page("Contact & Payment", "📞")
        self._pagenav.show_page(self.page_basic)

        F = self.fields

        def var(key, value=""):
            F[key] = tk.StringVar(value=value)
            return F[key]

        # page 1 — Basic & Tax
        left, right = FK.two_cols(self.page_basic, C)
        FK.section(left, C, "Basic Information", "📋")
        g = FK.grid(left, C)
        FK.field(g, C, 0, 0, "Supplier Code", var("supplier_code"), kind="code",
                 required=True, maxlen=20)
        FK.field(g, C, 1, 0, "Name (English)", var("supplier_name_en"), required=True,
                 maxlen=200, colspan=2)
        FK.field(g, C, 2, 0, "الاسم (عربي)", var("supplier_name_ar"), rtl=True,
                 maxlen=200, colspan=2)
        FK.section(right, C, "Tax", "🧾")
        g2 = FK.grid(right, C, cols=1)
        FK.field(g2, C, 0, 0, "VAT Number  (15 digits)", var("vat_registration_no"),
                 kind="vat", maxlen=15)
        cr_cell, cr = FK.field(g2, C, 1, 0, "CR Number", var("cr_number"),
                               kind="vat", maxlen=20)
        cr.pack_forget()
        row = tk.Frame(cr_cell, bg=C["content_bg"])
        row.pack(anchor="w", pady=(2, 0))
        cr.pack(in_=row, side="left", ipady=4)
        cr.lift(row)                      # made before the row: keep it on top
        tk.Button(row, text="⤓ Wathq", font=("Segoe UI", 8, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=8,
                  cursor="hand2", command=self._wathq_fill).pack(side="left", padx=(6, 0))
        FK.section(right, C, "Status", "✅")
        self.active_var = tk.BooleanVar(value=True)
        labeled_toggle(right, "Active supplier (shows in purchases)",
                       self.active_var, C, font_size=9)[0].pack(anchor="w", padx=14, pady=(4, 0))

        # page 2 — Address
        ga = FK.grid(self.page_address, C)
        ga.pack_configure(pady=(12, 0))
        FK.field(ga, C, 0, 0, "Address (EN)", var("address_en"), maxlen=500)
        FK.field(ga, C, 0, 1, "العنوان (AR)", var("address_ar"), rtl=True, maxlen=500)
        FK.field(ga, C, 1, 0, "City (EN)", var("city_en"), maxlen=100)
        FK.field(ga, C, 1, 1, "المدينة (AR)", var("city_ar"), rtl=True, maxlen=100)
        FK.field(ga, C, 2, 0, "Country Code", var("country_code", "SA"),
                 kind="country", maxlen=3)

        # page 3 — Contact & Payment
        lc, rc = FK.two_cols(self.page_contact, C)
        FK.section(lc, C, "Contact", "📞")
        gc = FK.grid(lc, C, cols=1)
        FK.field(gc, C, 0, 0, "Phone", var("phone"), kind="phone", maxlen=20)
        FK.field(gc, C, 1, 0, "Email", var("email"), maxlen=100)
        FK.field(gc, C, 2, 0, "Contact Person (EN)", var("contact_person_en"), maxlen=100)
        FK.field(gc, C, 3, 0, "Contact Person (AR)", var("contact_person_ar"), rtl=True,
                 maxlen=100)
        FK.section(rc, C, "Payment", "💰")
        gp = FK.grid(rc, C, cols=1)
        FK.field(gp, C, 0, 0, "Payment Terms (days)", var("payment_terms_days"),
                 kind="days", maxlen=4)
        FK.field(gp, C, 1, 0, "Opening Balance (SAR)", var("opening_balance"),
                 kind="number")
        tk.Label(rc, text="Opening balance is posted to the books when you save\n"
                          "(Dr Opening Balance Equity / Cr supplier).",
                 font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"],
                 justify="left").pack(anchor="w", padx=14, pady=(2, 0))

        self.win.bind("<Control-s>", lambda e=None: self._save())
        self.win.bind("<F4>", lambda e=None: self._save())

        if supplier_id:
            self._load_data()
        else:
            try:   # Settings > Supplier: auto code
                if cfg.flag("sup_auto_code", True):
                    from modules.doc_numbering import next_party_code
                    self.fields["supplier_code"].set(next_party_code(
                        "suppliers", "supplier_code", cfg.get("sup_prefix", "S")))
            except Exception:
                pass

    def _load_data(self):
        try:
            d = db.fetchone("SELECT * FROM suppliers WHERE supplier_id=?",
                            (self.supplier_id,))
            if not d:
                return
            for k, v in self.fields.items():
                if d.get(k) is not None:
                    v.set(str(d[k]))
            self.active_var.set(bool(d.get("is_active", 1)))
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def _wathq_fill(self):
        try:
            from modules import wathq
            ok, msg = wathq.fill_party_fields(self.fields,
                                              self.fields["cr_number"].get())
            (messagebox.showinfo if ok else messagebox.showwarning)("Wathq", msg)
        except Exception as e:
            messagebox.showerror("Wathq", str(e)[:200])

    # columns added to the form in v5.25 (in the table since the first
    # install) — left out again if an old database does not have them
    _EXTRA = ("address_en", "address_ar", "city_ar", "contact_person_ar", "country_code")

    def _save(self, mode="close"):
        # a new supplier needs 'add', changing one needs 'edit'
        _need = "edit" if self.supplier_id else "add"
        if not perm.can("suppliers", _need):
            messagebox.showwarning(
                "Access Denied",
                "You don't have permission to %s suppliers." % _need, parent=self.win)
            return
        try:                        # v6.8: red note under each wrong box (Tally style)
            from ui import form_style as _FS
            _bad = _FS.validate(self.win, self._pagenav)
            if _bad:
                self.status_var.set("⚠️ " + "  |  ".join("%s: %s" % b for b in _bad[:3]))
                return
        except Exception:
            pass
        if not self.fields["supplier_code"].get().strip():
            self.status_var.set("⚠️ Supplier Code required.")
            self._pagenav.show_page(self.page_basic)
            return
        if not self.fields["supplier_name_en"].get().strip():
            self.status_var.set("⚠️ Name (EN) required.")
            self._pagenav.show_page(self.page_basic)
            return
        try:  # Settings ▸ Supplier: mandatory VAT number
            if cfg.flag("sup_mandatory_vat") and \
                    not self.fields["vat_registration_no"].get().strip():
                self.status_var.set("⚠️ VAT Number required (Settings ▸ Supplier).")
                return
        except Exception:
            pass

        def v(k, d=""):
            return self.fields.get(k).get().strip() or d if self.fields.get(k) else d

        data = {
            "supplier_code": v("supplier_code"),
            "supplier_name_en": v("supplier_name_en"),
            "supplier_name_ar": v("supplier_name_ar") or None,
            "vat_registration_no": v("vat_registration_no") or None,
            "cr_number": v("cr_number") or None,
            "phone": v("phone") or None,
            "email": v("email") or None,
            "city_en": v("city_en") or None,
            "contact_person_en": v("contact_person_en") or None,
            "payment_terms_days": int(v("payment_terms_days", "30") or 30),
            "opening_balance": float(v("opening_balance", "0") or 0),
            "is_active": 1 if self.active_var.get() else 0,
            "address_en": v("address_en") or None,
            "address_ar": v("address_ar") or None,
            "city_ar": v("city_ar") or None,
            "contact_person_ar": v("contact_person_ar") or None,
            "country_code": v("country_code", "SA") or "SA",
        }

        _ids = {"new": None}

        def write(d):
            if self.supplier_id:
                sc = ", ".join([f"{k}=?" for k in d])
                db.execute(f"UPDATE suppliers SET {sc}, updated_at=GETDATE() "
                           f"WHERE supplier_id=?", (*d.values(), self.supplier_id))
            else:
                cols = ", ".join(d.keys())
                ph = ", ".join(["?"] * len(d))
                db.execute(f"INSERT INTO suppliers ({cols}) VALUES ({ph})",
                           tuple(d.values()))
                _ids["new"] = db.last_identity("suppliers", "supplier_id")   # this PC's row
        try:
            try:
                write(data)
            except Exception as e:
                if "column" not in str(e).lower():
                    raise
                write({k: x for k, x in data.items() if k not in self._EXTRA})
            if self.supplier_id:
                msg = f"Supplier '{data['supplier_name_en']}' updated."
            else:
                msg = f"Supplier '{data['supplier_name_en']}' added."
                try:
                    from modules import posting
                    new_id = _ids["new"]
                    if new_id:
                        posting.ensure_party_account("supplier", new_id)
                except Exception:
                    pass
            # opening balance → the books (Dr Opening Balance Equity / Cr supplier)
            try:
                from modules import opening_balances as ob
                sid = self.supplier_id or _ids["new"]
                if sid:
                    ob.post_party("supplier", sid)
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
                SupplierForm(self.parent, None, self.on_save)
            else:       # plain Save: Settings ▸ General ▸ After saving (v6.9.3)
                from ui import after_save
                parent, cb = self.parent, self.on_save
                sid = self.supplier_id or _ids["new"]
                after_save.finish(self, "",
                                  new=lambda: SupplierForm(parent, None, cb),
                                  keep=(lambda: SupplierForm(parent, sid, cb)) if sid else None,
                                  edited=bool(self.supplier_id))
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err or "duplicate" in err.lower():
                self.status_var.set("❌ Supplier code already exists.")
            else:
                self.status_var.set(f"❌ {err[:80]}")

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth(); sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
