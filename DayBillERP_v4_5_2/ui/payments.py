# ============================================================
# DayBill ERP - Payments Module
# Receipts (from customers) & Disbursements (to suppliers)
# Allocate payments to invoices | Bilingual
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db
from modules import permissions as perm


def _pay_kind(pay_id):
    try:
        r = db.fetchone("SELECT payment_type FROM payments WHERE payment_id=?", (pay_id,)) or {}
    except Exception:
        r = {}
    return "payment" if r.get("payment_type") == "disbursement" else "receipt"


def print_receipt(pay_id, send_to_printer=True):
    """Print the receipt / payment voucher with its default layout.
    Returns the PDF path (None on failure)."""
    try:
        from modules import doc_print as DP
        doc = DP.load(_pay_kind(pay_id), pay_id)
        if not doc:
            return None
        path, _src = DP.render_default(doc)
    except Exception as e:
        print("[DayBill] receipt PDF failed:", e)
        return None
    if send_to_printer and path:
        try:
            from modules import printer_service as PS
            PS.print_pdf(path, DP.default_printer_for(doc), copies=DP.copies_for(doc))
        except Exception as e:
            print("[DayBill] receipt print failed:", e)
    return path


class PaymentsView:
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
        tk.Label(bar, text=f"💳  {t('nav.payments')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        btns = tk.Frame(bar, bg=C["content_bg"])
        btns.pack(side="right")
        tk.Button(btns, text="📊 Report", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._report).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="📥 Export", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: self._export("excel")).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="🖨 Print ▾", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._print).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="🟢 WhatsApp", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._whatsapp).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="✏ Edit", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._edit).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="🗑 Delete", font=("Segoe UI", 9), bg="#FEF2F2",
                  fg=C["danger"], relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._delete).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="➖  Disbursement", font=("Segoe UI", 9, "bold"),
                  bg="#FEF2F2", fg=C["danger"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  command=lambda: self._new("disbursement")).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="➕  Receipt", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat",
                  padx=16, pady=7, cursor="hand2",
                  activebackground=C["primary_dark"],
                  command=lambda: self._new("receipt")).pack(side="left")

    def _stats(self, C):
        self.stats = tk.Frame(self.frame, bg=C["content_bg"])
        self.stats.pack(fill="x", padx=24, pady=(14, 0))

    def _refresh_stats(self, data):
        C = cfg.theme()
        for w in self.stats.winfo_children():
            w.destroy()
        rec = sum(float(r.get("amount", 0)) for r in data if r.get("payment_type") == "receipt")
        dis = sum(float(r.get("amount", 0)) for r in data if r.get("payment_type") == "disbursement")
        items = [("➕", "Total Receipts", f"{rec:,.0f}", C["success"]),
                 ("➖", "Total Disbursements", f"{dis:,.0f}", C["danger"]),
                 ("💰", "Net Cash Flow", f"{rec-dis:,.0f}", C["primary"]),
                 ("🧾", "Transactions", str(len(data)), C["info"])]
        for icon, label, val, color in items:
            card = tk.Frame(self.stats, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 10), ipadx=12, ipady=4)
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
                 relief="flat", width=26, fg=C["text_primary"]).pack(side="left", ipady=7, padx=(0, 10))
        self.type_var = tk.StringVar(value="All")
        tf = tk.Frame(bar, bg=C["content_bg"])
        tf.pack(side="left", padx=12)
        for v in ["All", "Receipt", "Disbursement"]:
            tk.Radiobutton(tf, text=v, variable=self.type_var, value=v,
                           font=("Segoe UI", 9), bg=C["content_bg"],
                           activebackground=C["content_bg"],
                           command=self._filter).pack(side="left", padx=3)
        self.count_var = tk.StringVar()
        tk.Label(bar, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right")

    def _table(self, C):
        wrapper = tk.Frame(self.frame, bg=C["content_bg"])
        wrapper.pack(fill="both", expand=True, padx=24, pady=(10, 24))
        card = tk.Frame(wrapper, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("number", "date", "type", "party", "method", "ref", "amount")
        headers = {"number": ("Payment #", 120, "center"), "date": ("Date", 100, "center"),
                   "type": ("Type", 110, "center"), "party": ("Party", 200, "w"),
                   "method": ("Method", 110, "center"), "ref": ("Reference", 120, "center"),
                   "amount": ("Amount SAR", 120, "e")}
        style = ttk.Style()
        style.configure("Pay.Treeview", background="white", rowheight=32, font=("Segoe UI", 9))
        style.configure("Pay.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 style="Pay.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for col in cols:
            h, w, a = headers[col]
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor=a)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("receipt", background="#F0FDF4")
        self.tree.tag_configure("disbursement", background="#FEF2F2")
        self.tree.bind("<Double-1>", lambda e: self._edit())

        bbar = tk.Frame(wrapper, bg=C["content_bg"])
        bbar.pack(fill="x", pady=(6, 0))
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
                "SELECT payment_id, payment_number, payment_date, payment_type, "
                "party_name_en, payment_method, reference_number, amount "
                "FROM payments ORDER BY payment_date DESC, payment_id DESC")
        except Exception as e:
            self._all = []
            messagebox.showerror("DB Error", str(e))
        self._filter()

    def _filter(self):
        q = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        ft = self.type_var.get() if hasattr(self, "type_var") else "All"
        rows = []
        for r in self._all:
            if ft != "All" and r.get("payment_type", "").lower() != ft.lower():
                continue
            if q:
                s = (str(r.get("payment_number", "")) + str(r.get("party_name_en", ""))).lower()
                if q not in s:
                    continue
            rows.append(r)
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            pt = r.get("payment_type", "receipt")
            self.tree.insert("", "end", iid=str(r["payment_id"]), values=(
                r.get("payment_number", ""), str(r.get("payment_date", "")),
                "➕ Receipt" if pt == "receipt" else "➖ Disbursement",
                r.get("party_name_en", ""), r.get("payment_method", ""),
                r.get("reference_number", "") or "—",
                f"{float(r.get('amount', 0)):,.2f}"), tags=(pt,))
        self._refresh_stats(self._all)
        self.count_var.set(f"{len(rows)} payment(s)")

    @perm.guard("payment", "add")
    def _new(self, ptype):
        PaymentForm(self.frame, ptype, self._load)

    @perm.guard("payment", "edit")
    def _edit(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", "Select a payment to edit.")
            return
        pid = int(s[0])
        row = db.fetchone("SELECT payment_type FROM payments WHERE payment_id=?",
                          (pid,))
        ptype = (row or {}).get("payment_type", "receipt")
        PaymentForm(self.frame, ptype, self._load, payment_id=pid)

    def _print(self, widget=None):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", "Select a receipt or payment.")
            return
        from ui import print_menu
        pid = int(s[0])
        print_menu.show_menu(self.frame, _pay_kind(pid), lambda: pid, widget=widget)

    def _whatsapp(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", "Select a receipt or payment.")
            return
        try:
            from ui.whatsapp_send import send_document
            send_document(self.frame, "receipt", int(s[0]))
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:300])

    @perm.guard("payment", "reports")
    def _report(self):
        rows = [list(self.tree.item(i)["values"])
                for i in self.tree.get_children()]
        if not rows:
            messagebox.showinfo("Report", "No payments to report.")
            return
        headers = ["Payment #", "Date", "Type", "Party", "Method",
                   "Reference", "Amount SAR"]
        try:
            from modules.report_export import export_pdf
            total = 0.0
            for r in rows:
                try:
                    total += float(str(r[-1]).replace(",", ""))
                except Exception:
                    pass
            export_pdf(self.frame, "Payments_Report", headers, rows,
                       title="Payments / Receipts Report",
                       subtitle=f"{len(rows)} entries",
                       summary=[("Total", f"{total:,.2f} SAR")],
                       col_align=["left", "center", "center", "left",
                                  "center", "left", "right"])
        except ImportError:
            messagebox.showerror("Report", "pip install reportlab")
        except Exception as e:
            messagebox.showerror("Report", str(e)[:200])

    @perm.guard("payment", "export")
    def _export(self, mode="excel"):
        rows = [list(self.tree.item(i)["values"])
                for i in self.tree.get_children()]
        if not rows:
            messagebox.showinfo("Nothing to export", "No payments to export.")
            return
        headers = ["Payment #", "Date", "Type", "Party", "Method", "Reference", "Amount SAR"]
        try:
            if mode == "pdf":
                from modules.report_export import export_pdf
                export_pdf(self.frame, "Payments", headers, rows, title="Payments")
            else:
                from modules.report_export import export_excel
                export_excel(self.frame, "Payments", headers, rows, title="Payments")
        except ImportError:
            messagebox.showerror("Missing Library", "pip install openpyxl reportlab")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    @perm.guard("payment", "delete")
    def _delete(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", "Select a payment.")
            return
        pid = int(s[0])
        num = self.tree.item(s[0])["values"][0]
        if messagebox.askyesno(t("common.warning"), f"Delete payment {num}?"):
            try:
                row = db.fetchone("SELECT payment_type FROM payments "
                                  "WHERE payment_id=?", (pid,))
                ptype = (row or {}).get("payment_type", "receipt")
                with db.transaction():       # journal, links and payment go together
                    try:
                        from modules.doc_actions import delete_linked_journals, audit
                        delete_linked_journals(
                            "receipt" if ptype == "receipt" else "payment", pid)
                        audit("delete", "payment", pid, str(num))
                    except Exception:
                        pass
                    from modules import allocation
                    allocation.release(pid)          # invoices get their balance back
                    db.execute("DELETE FROM payments WHERE payment_id=?", (pid,))
                self._load()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))


class PaymentForm:
    """Receipt (customer) / Disbursement (supplier) with invoice
    settlement: pick the invoices this money pays; the rest stays on
    the party's account as an advance."""

    def __init__(self, parent, ptype, on_save=None, payment_id=None,
                 party_id=None, doc_id=None):
        self.ptype = ptype  # receipt / disbursement
        self.on_save = on_save
        self.payment_id = payment_id
        self.parties = []
        self.docs = []
        self._party_id = None
        self._amount_typed = bool(payment_id)
        C = self.C = cfg.theme()
        is_receipt = ptype == "receipt"
        verb = "Edit" if payment_id else "New"
        title = f"{verb} Receipt" if is_receipt else f"{verb} Payment to Supplier"

        self.win = tk.Toplevel()
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.bind("<Control-s>", lambda e: self._save())
        self.win.bind("<F9>", lambda e: self._save())
        self.win.title(title)
        self.win.configure(bg=C["content_bg"])
        self.win.minsize(820, 560)
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self._center(900, 640)
        self.win.grab_set()

        hcolor = C["primary"] if is_receipt else C["danger"]
        hdr = tk.Frame(self.win, bg=hcolor, height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"{'➕' if is_receipt else '➖'}  {title}",
                 font=("Segoe UI", 13, "bold"), bg=hcolor, fg="white").pack(
                     side="left", padx=18)
        self.bal_var = tk.StringVar()
        tk.Label(hdr, textvariable=self.bal_var, font=("Segoe UI", 10, "bold"),
                 bg=hcolor, fg="white").pack(side="right", padx=18)

        # Load parties (customers for receipt, suppliers for disbursement)
        try:
            if is_receipt:
                self.parties = db.fetchall(
                    "SELECT customer_id AS id, customer_code AS code, "
                    "customer_name_en AS name FROM customers WHERE is_active=1 "
                    "ORDER BY customer_name_en")
            else:
                self.parties = db.fetchall(
                    "SELECT supplier_id AS id, supplier_code AS code, "
                    "supplier_name_en AS name FROM suppliers WHERE is_active=1 "
                    "ORDER BY supplier_name_en")
        except Exception:
            self.parties = []

        # ── fields: two columns, sized to their content ──────────
        form = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        form.pack(fill="x", padx=16, pady=(12, 8))
        g = tk.Frame(form, bg=C["card_bg"]); g.pack(fill="x", padx=14, pady=10)

        def lbl(r, c, txt, req=False):
            tk.Label(g, text=txt + (" *" if req else ""), font=("Segoe UI", 9),
                     bg=C["card_bg"], fg=C["text_secondary"]).grid(
                         row=r, column=c, sticky="w", padx=(0 if c == 0 else 18, 8), pady=4)

        lbl(0, 0, "Customer" if is_receipt else "Supplier", True)
        self.party_var = tk.StringVar()
        self._party_names = [p["name"] for p in self.parties]
        self.party_cb = ttk.Combobox(g, textvariable=self.party_var, width=34,
                                     values=self._party_names, font=("Segoe UI", 10))
        self.party_cb.grid(row=0, column=1, sticky="w", pady=4, ipady=2)
        self.party_cb.bind("<<ComboboxSelected>>", lambda e: self._party_changed())
        self.party_cb.bind("<Return>", lambda e: self._party_changed())
        self.party_cb.bind("<FocusOut>", lambda e: self._party_changed())
        self.party_cb.bind("<KeyRelease>", self._filter_parties)

        lbl(0, 2, "Date", True)
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        _pd = tk.Entry(g, textvariable=self.date_var, font=("Segoe UI", 10), width=12,
                       bg="white", relief="solid", bd=1)
        _pd.grid(row=0, column=3, sticky="w", pady=4, ipady=3)
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(_pd, self.date_var)
        except Exception:
            pass

        lbl(1, 0, "Amount (SAR)", True)
        self.amount_var = tk.StringVar()
        self.amount_entry = tk.Entry(g, textvariable=self.amount_var, width=14,
                                     font=("Segoe UI", 13, "bold"), bg="white",
                                     relief="solid", bd=1, justify="right")
        self.amount_entry.grid(row=1, column=1, sticky="w", pady=4, ipady=3)
        self.amount_entry.bind("<KeyRelease>", lambda e: self._amount_typed_now())

        lbl(1, 2, "Method", True)
        self.method_var = tk.StringVar(value="cash")
        ttk.Combobox(g, textvariable=self.method_var, width=16,
                     values=cfg.payment_methods(["cash", "card", "bank_transfer", "cheque"]),
                     state="readonly", font=("Segoe UI", 10)).grid(
                         row=1, column=3, sticky="w", pady=4, ipady=2)

        lbl(2, 0, "Reference / Cheque No")
        self.ref_var = tk.StringVar()
        tk.Entry(g, textvariable=self.ref_var, font=("Segoe UI", 10), width=22,
                 bg="white", relief="solid", bd=1).grid(row=2, column=1, sticky="w",
                                                       pady=4, ipady=3)
        lbl(2, 2, "Notes")
        self.notes_var = tk.StringVar()
        tk.Entry(g, textvariable=self.notes_var, font=("Segoe UI", 10), width=24,
                 bg="white", relief="solid", bd=1).grid(row=2, column=3, sticky="w",
                                                       pady=4, ipady=3)

        # ── settle against invoices ───────────────────────────────
        sec = tk.Frame(self.win, bg=C["content_bg"]); sec.pack(fill="x", padx=16)
        tk.Label(sec, text="Settle against " + ("sales invoices" if is_receipt
                                                 else "purchase invoices"),
                 font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        for txt, cmd in (("✖  Clear", self._clear_alloc),
                         ("⚡  Auto (oldest first)", self._auto_alloc)):
            tk.Button(sec, text=txt, font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", padx=10, pady=3,
                      cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1, command=cmd).pack(side="right", padx=(6, 0))

        box = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        box.pack(fill="both", expand=True, padx=16, pady=(6, 6))
        cols = [("sel", "✓", 40, "center"), ("number", "Invoice #", 110, "w"),
                ("date", "Date", 100, "center"), ("due", "Due", 100, "center"),
                ("total", "Total", 110, "e"), ("paid", "Paid", 110, "e"),
                ("balance", "Balance", 110, "e"), ("pay", "Pay now ✎", 120, "e")]
        st = ttk.Style()
        st.configure("Alloc.Treeview", rowheight=28, font=("Segoe UI", 10))
        st.configure("Alloc.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                 style="Alloc.Treeview", selectmode="browse")
        for key, head, w, anc in cols:
            self.tree.heading(key, text=head, anchor=anc if anc != "e" else "e")
            self.tree.column(key, width=w, anchor=anc, stretch=key == "number")
        vs = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("on", background="#ECFDF3")
        self.tree.tag_configure("empty", foreground=C["text_secondary"])
        self.tree.bind("<Button-1>", self._tree_click, add="+")
        self.tree.bind("<Double-1>", self._tree_double)
        self.tree.bind("<space>", lambda e: self._toggle_focused())
        self.tree.bind("<Return>", lambda e: self._edit_focused())
        self.tree.bind("<F2>", lambda e: self._edit_focused())
        self.alloc = {}
        self._editor = None
        tk.Label(self.win, text="Tick an invoice (click ✓ or Space) to pay it; double-click "
                                "'Pay now' (or Enter) to type a part amount.",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=18)

        footer = tk.Frame(self.win, bg=C["card_bg"])
        footer.pack(fill="x", side="bottom")
        inner = tk.Frame(footer, bg=C["card_bg"])
        inner.pack(fill="x", padx=16, pady=10)
        self.sum_var = tk.StringVar()
        tk.Label(inner, textvariable=self.sum_var, font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
        self.status_var = tk.StringVar()
        tk.Label(inner, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["danger"]).pack(side="left", padx=(16, 0))
        tk.Button(inner, text=t("common.cancel"), font=("Segoe UI", 10),
                  bg=C["card_bg"], fg=C["text_secondary"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(inner, text="💾  Save  [F9]", font=("Segoe UI", 10, "bold"),
                  bg=hcolor, fg="white", relief="flat", padx=18, pady=7,
                  cursor="hand2", command=self._save).pack(side="right")

        if self.payment_id:
            self._load_existing()
        else:
            self._render_docs()
            if party_id:                      # opened from an invoice
                self._preselect(party_id, doc_id)
        self.party_cb.focus_set()

    def _preselect(self, party_id, doc_id=None):
        p = next((x for x in self.parties if x["id"] == party_id), None)
        if not p:
            return
        self.party_var.set(p["name"])
        self._party_changed()
        if doc_id and self._doc(doc_id):
            self._toggle(doc_id)
        self.amount_entry.focus_set()
        self.amount_entry.select_range(0, "end")

    # ── party ─────────────────────────────────────────────────
    def _filter_parties(self, e=None):
        if e is not None and getattr(e, "keysym", "") in ("Return", "Tab", "Down", "Up"):
            return
        q = self.party_var.get().strip().lower()
        vals = [n for n in self._party_names if q in n.lower()] if q else self._party_names
        self.party_cb["values"] = vals[:300]

    def _current_party(self):
        name = self.party_var.get().strip()
        return next((p for p in self.parties if p["name"] == name), None)

    def _party_changed(self):
        p = self._current_party()
        pid = p["id"] if p else None
        if pid == self._party_id:
            return
        self._party_id = pid
        self._load_docs()

    def _party_balance(self):
        """Ledger balance of the party (what they owe / you owe)."""
        if not self._party_id:
            return None
        try:
            col = "customers" if self.ptype == "receipt" else "suppliers"
            key = "customer_id" if self.ptype == "receipt" else "supplier_id"
            acc = db.execute_scalar(f"SELECT account_id FROM {col} WHERE {key}=?",
                                    (self._party_id,))
            if not acc:
                return None
            b = float(db.execute_scalar(
                "SELECT ISNULL(SUM(jl.debit),0) - ISNULL(SUM(jl.credit),0) "
                "FROM journal_lines jl JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE je.is_posted=1 AND jl.account_id=?", (acc,)) or 0)
            return b if self.ptype == "receipt" else -b
        except Exception:
            return None

    # ── invoice list ──────────────────────────────────────────
    def _load_docs(self, keep=None):
        from modules import allocation
        try:
            self.docs = allocation.open_documents(self.ptype, self._party_id,
                                                  self.payment_id)
        except Exception:
            self.docs = []
        self.alloc = {d["doc_id"]: round(float(keep.get(d["doc_id"], 0.0)), 2)
                      for d in self.docs if keep and keep.get(d["doc_id"])}
        self._render_docs()
        b = self._party_balance()
        if b is None:
            self.bal_var.set("")
        elif self.ptype == "receipt":
            self.bal_var.set(f"Customer owes: {b:,.2f} SAR" if b >= 0
                             else f"Advance with us: {-b:,.2f} SAR")
        else:
            self.bal_var.set(f"You owe: {b:,.2f} SAR" if b >= 0
                             else f"Advance paid: {-b:,.2f} SAR")

    def _doc(self, doc_id):
        return next((d for d in self.docs if d["doc_id"] == doc_id), None)

    def _row_values(self, d):
        a = self.alloc.get(d["doc_id"], 0.0)
        return ("☑" if a > 0 else "☐", d["number"], d["date"], d["due"] or "—",
                f"{d['total']:,.2f}", f"{d['paid']:,.2f}", f"{d['balance']:,.2f}",
                f"{a:,.2f}" if a else "")

    def _render_docs(self):
        self.tree.delete(*self.tree.get_children())
        if not self.docs:
            msg = ("Pick a customer to see unpaid invoices." if self.ptype == "receipt"
                   else "Pick a supplier to see unpaid purchase invoices.")
            if self._party_id:
                msg = "No unpaid invoices — the amount stays on the account as an advance."
            if getattr(self, "_empty_lbl", None) is None:
                self._empty_lbl = tk.Label(self.tree, bg="white", fg="#6B6B80",
                                           font=("Segoe UI", 10, "italic"))
            self._empty_lbl.config(text=msg)
            self._empty_lbl.place(relx=0.5, y=60, anchor="n")
        elif getattr(self, "_empty_lbl", None) is not None:
            self._empty_lbl.place_forget()
        for d in self.docs:
            self.tree.insert("", "end", iid=str(d["doc_id"]), values=self._row_values(d),
                             tags=("on",) if self.alloc.get(d["doc_id"]) else ())
        self._update_sum()

    def _refresh_row(self, doc_id):
        d = self._doc(doc_id)
        if d and self.tree.exists(str(doc_id)):
            self.tree.item(str(doc_id), values=self._row_values(d),
                           tags=("on",) if self.alloc.get(doc_id) else ())

    def _num(self, v):
        try:
            return round(float(str(v).replace(",", "").strip() or 0), 2)
        except ValueError:
            return 0.0

    def _amount_typed_now(self):
        self._amount_typed = self._num(self.amount_var.get()) > 0
        self._update_sum()

    def _allocated(self):
        return round(sum(self.alloc.values()), 2)

    def _set_pay(self, doc_id, amt):
        d = self._doc(doc_id)
        if not d:
            return
        amt = round(max(0.0, min(float(amt or 0), d["balance"])), 2)
        if amt > 0:
            self.alloc[doc_id] = amt
        else:
            self.alloc.pop(doc_id, None)
        self._refresh_row(doc_id)
        if not self._amount_typed:
            tot = self._allocated()
            self.amount_var.set(f"{tot:.2f}" if tot else "")
        self._update_sum()

    def set_pay(self, number, amt):
        """Set 'Pay now' for an invoice number (keyboard / tests)."""
        d = next((x for x in self.docs if str(x["number"]) == str(number)), None)
        if d:
            self._set_pay(d["doc_id"], amt)

    def _toggle(self, doc_id):
        d = self._doc(doc_id)
        if not d:
            return
        if self.alloc.get(doc_id):
            self._set_pay(doc_id, 0)
            return
        if self._amount_typed:
            left = self._num(self.amount_var.get()) - self._allocated()
            a = min(d["balance"], left)
            if a <= 0.005:
                self.status_var.set("⚠️ The amount is fully used — raise the amount "
                                    "or untick another invoice.")
                return
        else:
            a = d["balance"]
        self.status_var.set("")
        self._set_pay(doc_id, a)

    def _tree_click(self, e):
        if self.tree.identify_region(e.x, e.y) != "cell":
            return
        iid = self.tree.identify_row(e.y)
        if iid and iid != "_empty" and self.tree.identify_column(e.x) == "#1":
            self._toggle(int(iid))
            return "break"

    def _tree_double(self, e):
        iid = self.tree.identify_row(e.y)
        if iid and iid != "_empty":
            if self.tree.identify_column(e.x) == "#1":
                return "break"
            self._edit_cell(int(iid))
            return "break"

    def _focused(self):
        iid = self.tree.focus() or (self.tree.selection() or [None])[0]
        return int(iid) if iid and iid != "_empty" else None

    def _toggle_focused(self):
        k = self._focused()
        if k:
            self._toggle(k)
        return "break"

    def _edit_focused(self):
        k = self._focused()
        if k:
            self._edit_cell(k)
        return "break"

    def _edit_cell(self, doc_id):
        """Small editor over the 'Pay now' cell (Enter = keep, Esc = cancel)."""
        if self._editor is not None:
            try:
                self._editor.destroy()
            except Exception:
                pass
        self.tree.see(str(doc_id))
        self.tree.update_idletasks()
        bbox = self.tree.bbox(str(doc_id), "pay")
        if not bbox:
            return
        x, y, w, h = bbox
        var = tk.StringVar(value=f"{self.alloc.get(doc_id, 0):.2f}"
                           if self.alloc.get(doc_id) else "")
        ed = tk.Entry(self.tree, textvariable=var, justify="right",
                      font=("Segoe UI", 10), relief="solid", bd=1)
        ed.place(x=x, y=y, width=w, height=h)
        ed.focus_set(); ed.select_range(0, "end")
        self._editor = ed

        def commit(_e=None):
            if self._editor is not ed:
                return
            val = self._num(var.get())
            self._editor = None
            ed.destroy()
            self._set_pay(doc_id, val)
            self.tree.focus_set(); self.tree.focus(str(doc_id))
            self.tree.selection_set(str(doc_id))

        def cancel(_e=None):
            self._editor = None
            ed.destroy()
            self.tree.focus_set()
            return "break"
        ed.bind("<Return>", commit)
        ed.bind("<KP_Enter>", commit)
        ed.bind("<Tab>", commit)
        ed.bind("<FocusOut>", commit)
        ed.bind("<Escape>", cancel)

    def _auto_alloc(self):
        from modules import allocation
        amount = self._num(self.amount_var.get())
        if amount <= 0:
            amount = sum(d["balance"] for d in self.docs)
            self._amount_typed = False
        self.alloc = {k: v for k, v in allocation.auto_allocate(self.docs, amount).items()}
        for d in self.docs:
            self._refresh_row(d["doc_id"])
        if not self._amount_typed:
            tot = self._allocated()
            self.amount_var.set(f"{tot:.2f}" if tot else "")
        self._update_sum()

    def _clear_alloc(self):
        self.alloc = {}
        for d in self.docs:
            self._refresh_row(d["doc_id"])
        self._update_sum()

    def _update_sum(self):
        amount = self._num(self.amount_var.get())
        alloc = self._allocated()
        adv = round(amount - alloc, 2)
        txt = f"Amount {amount:,.2f}   ·   Against invoices {alloc:,.2f}"
        if adv > 0.005:
            txt += f"   ·   On account (advance) {adv:,.2f}"
        elif adv < -0.005:
            txt += f"   ·   ⚠ {-adv:,.2f} more than the amount"
        self.sum_var.set(txt)

    # ── load / save ───────────────────────────────────────────
    def _load_existing(self):
        try:
            p = db.fetchone("SELECT * FROM payments WHERE payment_id=?",
                            (self.payment_id,))
        except Exception:
            p = None
        if not p:
            return
        pid = p.get("customer_id") or p.get("supplier_id")
        party = next((x for x in self.parties if x["id"] == pid), None)
        self.party_var.set(party["name"] if party else (p.get("party_name_en") or ""))
        d = p.get("payment_date")
        self.date_var.set(d.strftime("%Y-%m-%d") if hasattr(d, "strftime")
                          else str(d)[:10])
        self.amount_var.set(f"{float(p.get('amount', 0) or 0):.2f}")
        self.method_var.set(p.get("payment_method", "cash") or "cash")
        self.ref_var.set(p.get("reference_number", "") or "")
        self.notes_var.set(p.get("notes_en", "") or "")
        from modules import allocation
        self._party_id = party["id"] if party else None
        self._load_docs(keep=allocation.allocations(self.payment_id))

    def _next_number(self, prefix):
        year = date.today().year
        base = f"{prefix}-{year}-"
        try:
            rows = db.fetchall("SELECT payment_number FROM payments "
                               "WHERE payment_number LIKE ?", (base + "%",)) or []
            n = max([int(str(r["payment_number"]).rsplit("-", 1)[-1])
                     for r in rows if str(r["payment_number"]).rsplit("-", 1)[-1].isdigit()]
                    or [0])
        except Exception:
            n = 0
        while True:
            n += 1
            num = f"{base}{n:05d}"
            if not db.execute_scalar("SELECT COUNT(*) FROM payments WHERE payment_number=?",
                                     (num,)):
                return num

    def _save(self):
        party = self._current_party()
        if not party:
            self.status_var.set("⚠️ Select a " + ("customer." if self.ptype == "receipt"
                                                  else "supplier."))
            return
        amount = self._num(self.amount_var.get())
        if amount <= 0:
            self.status_var.set("⚠️ Enter a valid amount.")
            return
        from modules.date_utils import validate_invoice_date
        ok, iso_date, err = validate_invoice_date(self.date_var.get())
        if not ok:
            self.status_var.set("⚠️ " + err)
            return
        self.date_var.set(iso_date)
        alloc = {}
        for doc_id, a in self.alloc.items():
            d = self._doc(doc_id)
            if not d or a <= 0:
                continue
            if a > d["balance"] + 0.005:
                self.status_var.set(f"⚠️ {d['number']}: pay now is more than "
                                    f"its balance {d['balance']:,.2f}.")
                return
            alloc[doc_id] = a
        if sum(alloc.values()) > amount + 0.005:
            self.status_var.set("⚠️ Invoices ticked add up to more than the amount.")
            return
        is_receipt = self.ptype == "receipt"

        # financial-year guard: only dates inside the login-selected FY
        try:
            from modules import financial_year as fy
            fy_msg = fy.guard_active(iso_date)
            if fy_msg:
                self.status_var.set("⚠️ " + fy_msg)
                return
        except Exception:
            pass

        from modules import allocation, posting
        _tx = None
        try:
            # v5.27: payment, journal and invoice links are ONE transaction
            _tx = db.begin()
            try:
                posting.ensure_party_account("customer" if is_receipt else "supplier",
                                             party["id"])
            except Exception:
                pass
            if self.payment_id:
                # ── EDIT: update in place, re-post journal + links ──
                db.execute(
                    "UPDATE payments SET payment_date=?, customer_id=?, "
                    "supplier_id=?, party_name_en=?, amount=?, payment_method=?, "
                    "reference_number=?, notes_en=? WHERE payment_id=?",
                    (iso_date, party["id"] if is_receipt else None,
                     None if is_receipt else party["id"],
                     party["name"], amount, self.method_var.get(),
                     self.ref_var.get() or None, self.notes_var.get() or None,
                     self.payment_id))
                pay_id = self.payment_id
                pnum = db.execute_scalar(
                    "SELECT payment_number FROM payments WHERE payment_id=?",
                    (pay_id,)) or "?"
                from modules.doc_actions import delete_linked_journals
                delete_linked_journals("receipt" if is_receipt else "payment", pay_id)
                allocation.release(pay_id)
                action = "updated"
            else:
                pnum = self._next_number("RCP" if is_receipt else "PAY")
                db.execute(
                    "INSERT INTO payments (payment_number, payment_type, payment_date, "
                    "customer_id, supplier_id, party_name_en, amount, payment_method, "
                    "reference_number, notes_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (pnum, self.ptype, iso_date,
                     party["id"] if is_receipt else None,
                     None if is_receipt else party["id"],
                     party["name"], amount, self.method_var.get(),
                     self.ref_var.get() or None, self.notes_var.get() or None))
                pay_id = db.execute_scalar(
                    "SELECT payment_id FROM payments WHERE payment_number=?", (pnum,))
                action = "saved"
                try:
                    from modules import branches as _br
                    _br.stamp("payments", pay_id)
                except Exception:
                    pass

            # journal (money in/out ⇄ party ledger)
            if is_receipt:
                jid = posting.post_receipt(pay_id, iso_date, party["id"], amount,
                                           method=self.method_var.get(), reference=pnum)
            else:
                jid = posting.post_payment(pay_id, iso_date, party["id"], amount,
                                           method=self.method_var.get(), reference=pnum)
            # invoices it settles
            done = allocation.apply(pay_id, self.ptype, alloc)
            try:
                from modules import audit
                audit.log("update" if self.payment_id else "create", "payment",
                          pay_id, f"{pnum} {amount:,.2f} (invoices {done:,.2f})")
            except Exception:
                pass
            _tx.commit()
            msg = (f"{'Receipt' if is_receipt else 'Payment'} {pnum} {action}.\n"
                   f"Amount: {amount:,.2f} SAR")
            if done:
                msg += f"\nSettled on invoices: {done:,.2f}"
            if amount - done > 0.005:
                msg += f"\nOn account (advance): {amount - done:,.2f}"
            if not jid and posting.enabled():
                msg += "\n\n⚠ Journal not posted: " + (posting.last_error or "check accounts")
            messagebox.showinfo(t("common.success"), msg, parent=self.win)
            if self.on_save:
                self.on_save()
            parent = self.win.master
            self.win.destroy()
            # Settings ▸ Payment ▸ print a receipt automatically
            if cfg.flag("pay_auto_receipt", False):
                self.receipt_pdf = print_receipt(pay_id)
            # Settings ▸ WhatsApp: receipt + new balance to the customer
            if is_receipt and cfg.flag("wa_enabled") and cfg.flag("wa_auto_statement"):
                try:
                    from ui.whatsapp_send import send_document
                    send_document(parent, "receipt", pay_id, auto=True)
                except Exception:
                    pass
        except Exception as e:
            if _tx is not None and not _tx.kept:
                _tx.rollback()                 # nothing of a failed save is kept
                e = "Not saved — " + str(e)
            self.status_var.set(f"❌ {str(e)[:120]}")

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth(); sh = self.win.winfo_screenheight()
        w = min(w, sw - 40); h = min(h, sh - 80)
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{max(0, (sh-h)//2 - 20)}")
