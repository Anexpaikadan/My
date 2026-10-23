# ============================================================
# Saudi Arabia ERP - Sales Invoice Module (Step 5)
# List View + Full Invoice Form + ZATCA QR Code
# B2B / B2C | VAT 15% | Phase 1 QR | Line Items
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys, os, uuid
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t, is_rtl
from config.database import db
from modules.barcode_gen import sys_select     # v6.9.5: 5-digit system barcode
from ui import close_guard
from modules.zatca.qr_generator import (
    generate_zatca_qr, generate_qr_photoimage, format_zatca_datetime
)


# ─────────────────────────────────────────────────────────────
# SALES INVOICE LIST VIEW
# ─────────────────────────────────────────────────────────────
def _company_country():
    try:
        from modules import country as _ctry
        return _ctry.code()
    except Exception:
        return "SA"


def _state_col():
    """', state_code' when the customers table has it (v7.0)."""
    try:
        if db.execute_scalar("SELECT COL_LENGTH('customers','state_code')") is not None:
            return ", state_code"
    except Exception:
        pass
    return ""


class SalesInvoiceView:
    def __init__(self, parent):
        self.parent   = parent
        C             = cfg.theme()
        self._all_data = []

        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        self._build_topbar(C)
        self._build_kpis(C)
        self._build_filters(C)
        self._build_table(C)
        self._load_invoices()

    # ── Top bar ───────────────────────────────────────────────
    def _build_topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(bar, text=f"🧾  {t('nav.sales')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        btn_f = tk.Frame(bar, bg=C["content_bg"])
        btn_f.pack(side="right")

        for text, bg, fg, cmd in [
            (f"📊  Report", C["card_bg"], C["text_primary"], self._report_pdf),
            (f"📥  Export", C["card_bg"], C["text_primary"], self._export_excel),
            (f"➕  New Invoice", C["primary"], "white", self._new_invoice),
        ]:
            tk.Button(btn_f, text=text, font=("Segoe UI", 10, "bold" if bg == C["primary"] else "normal"),
                      bg=bg, fg=fg, relief="flat", padx=16, pady=7, cursor="hand2",
                      activebackground=C["primary_dark"] if bg == C["primary"] else C["border"],
                      highlightbackground=C["border"], highlightthickness=1 if bg != C["primary"] else 0,
                      command=cmd).pack(side="left", padx=(0, 8))

    # ── KPI strip ─────────────────────────────────────────────
    def _build_kpis(self, C):
        self.kpi_frame = tk.Frame(self.frame, bg=C["content_bg"])
        self.kpi_frame.pack(fill="x", padx=24, pady=(14, 0))

    def _refresh_kpis(self, data):
        C = cfg.theme()
        for w in self.kpi_frame.winfo_children():
            w.destroy()

        total_amt  = sum(float(r.get("total_amount") or 0) for r in data)
        total_vat  = sum(float(r.get("vat_amount") or 0) for r in data)
        unpaid_amt = sum(float(r.get("total_amount") or 0) - float(r.get("paid_amount") or 0)
                         for r in data if r.get("payment_status") != "paid")
        draft_cnt  = sum(1 for r in data if r.get("invoice_status") == "draft")

        kpis = [
            ("💰", "Total Revenue",    f"{total_amt:,.2f} SAR", C["success"]),
            ("📋", "Total VAT (15%)",  f"{total_vat:,.2f} SAR", C["info"]),
            ("⏳", "Outstanding",       f"{unpaid_amt:,.2f} SAR", C["warning"]),
            ("📝", "Draft Invoices",    str(draft_cnt),          C["text_secondary"]),
        ]
        for icon, label, val, color in kpis:
            card = tk.Frame(self.kpi_frame, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 10), ipadx=12, ipady=6)
            tk.Label(card, text=f"{icon}  {label}",
                     font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=val, font=("Segoe UI", 13, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w", padx=8, pady=(0, 6))

    # ── Filters ───────────────────────────────────────────────
    def _build_filters(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(14, 0))

        # Search
        sf = tk.Frame(bar, bg="white",
                      highlightbackground=C["border"], highlightthickness=1)
        sf.pack(side="left")
        tk.Label(sf, text="🔍", font=("Segoe UI Emoji", 11),
                 bg="white", fg=C["text_secondary"]).pack(side="left", padx=(10, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._filter())
        tk.Entry(sf, textvariable=self.search_var,
                 font=("Segoe UI", 10), bg="white", relief="flat",
                 width=24, fg=C["text_primary"]).pack(
                     side="left", ipady=6, padx=(0, 10))

        # Status filter
        self.status_var = tk.StringVar(value="all")
        sf2 = tk.Frame(bar, bg=C["content_bg"])
        sf2.pack(side="left", padx=12)
        tk.Label(sf2, text="Status:", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        for v, label in [("all","All"),("draft","Draft"),
                          ("confirmed","Confirmed"),("cancelled","Cancelled")]:
            tk.Radiobutton(sf2, text=label, variable=self.status_var, value=v,
                           font=("Segoe UI", 9), bg=C["content_bg"],
                           command=self._filter).pack(side="left", padx=3)

        # ZATCA filter
        self.zatca_var = tk.StringVar(value="all")
        zf = tk.Frame(bar, bg=C["content_bg"])
        zf.pack(side="left", padx=8)
        tk.Label(zf, text="ZATCA:", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        for v, label in [("all","All"),("pending","Pending"),
                          ("reported","Reported"),("cleared","Cleared")]:
            tk.Radiobutton(zf, text=label, variable=self.zatca_var, value=v,
                           font=("Segoe UI", 9), bg=C["content_bg"],
                           command=self._filter).pack(side="left", padx=2)

        self.count_var = tk.StringVar()
        tk.Label(bar, textvariable=self.count_var,
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="right")

    # ── Table ─────────────────────────────────────────────────
    def _build_table(self, C):
        wrapper = tk.Frame(self.frame, bg=C["content_bg"])
        wrapper.pack(fill="both", expand=True, padx=24, pady=(10, 0))

        card = tk.Frame(wrapper, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)

        cols = ("number", "date", "customer", "type",
                "subtotal", "vat", "total", "payment", "status", "zatca")
        hdrs = {
            "number":   ("Invoice #",     110, "center"),
            "date":     ("Date",           90, "center"),
            "customer": ("Customer",      160, "w"),
            "type":     ("Type",           55, "center"),
            "subtotal": ("Subtotal",      100, "e"),
            "vat":      ("VAT",            90, "e"),
            "total":    ("Total SAR",     110, "e"),
            "payment":  ("Payment",        85, "center"),
            "status":   ("Status",         90, "center"),
            "zatca":    ("ZATCA",          80, "center"),
        }

        style = ttk.Style()
        style.configure("Inv.Treeview",
                         background="white", foreground=C["text_primary"],
                         fieldbackground="white", rowheight=34,
                         font=("Segoe UI", 9))
        style.configure("Inv.Treeview.Heading",
                         background=C["content_bg"], foreground=C["text_secondary"],
                         font=("Segoe UI", 9, "bold"), relief="flat", padding=(8,6))
        style.map("Inv.Treeview",
                  background=[("selected", C.get("select_bg", C["primary"]))],
                  foreground=[("selected", C.get("select_fg", "white"))])

        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                  style="Inv.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for col in cols:
            h, w, anchor = hdrs[col]
            self.tree.heading(col, text=h,
                              command=lambda c=col: self._sort(c))
            self.tree.column(col, width=w, anchor=anchor, minwidth=40)
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("confirmed", background="#F0FDF4")
        self.tree.tag_configure("draft",     background="#FFFBEB")
        self.tree.tag_configure("cancelled", background="#FEF2F2",
                                foreground="#9CA3AF")

        self.tree.bind("<Double-1>", lambda e: self._open_invoice())

        # Context menu
        ctx = tk.Menu(self.tree, tearoff=0, bg="white",
                       fg=C["text_primary"], font=("Segoe UI", 9))
        ctx.add_command(label="👁  View Invoice",    command=self._open_invoice)
        ctx.add_command(label="✏️  Edit (Draft)",    command=self._edit_invoice)
        ctx.add_separator()
        ctx.add_command(label="✅  Confirm Invoice", command=self._confirm_invoice)
        ctx.add_command(label="💰  Receive Payment", command=self._receive_payment)
        ctx.add_command(label="🟢  Send on WhatsApp", command=self._whatsapp)
        ctx.add_separator()
        ctx.add_command(label="🖨️  Print Preview",  command=self._print_preview)
        ctx.add_command(label="📄  Export PDF",      command=self._export_pdf)
        ctx.add_command(label="🗂  Export XML",      command=self._export_xml)
        ctx.add_separator()
        ctx.add_command(label="❌  Cancel Invoice",  command=self._cancel_invoice,
                         foreground=C["danger"])
        ctx.add_command(label="🗑  Delete Invoice",  command=self._delete_invoice,
                         foreground=C["danger"])
        self.tree.bind("<Button-3>", lambda e: (
            self.tree.selection_set(self.tree.identify_row(e.y)),
            ctx.post(e.x_root, e.y_root)
        ) if self.tree.identify_row(e.y) else None)

        self._build_bottom_bar(C, wrapper)

    def _build_bottom_bar(self, C, parent):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(6, 24))

        btns = [
            ("👁  View",       C["card_bg"],   C["text_primary"], self._open_invoice),
            ("✏️  Edit",       C["card_bg"],   C["text_primary"], self._edit_invoice),
            ("✅  Confirm",    C["success"],   "white",           self._confirm_invoice),
            ("💰  Receive",    C["card_bg"],   C["text_primary"], self._receive_payment),
            ("🟢  WhatsApp",   C["card_bg"],   C["text_primary"], self._whatsapp),
            ("🖨️  Print",     C["card_bg"],   C["text_primary"], self._print_preview),
            ("📄  PDF",        C["card_bg"],   C["text_primary"], self._export_pdf),
            ("🗂  XML",        C["card_bg"],   C["text_primary"], self._export_xml),
            ("❌  Cancel",     "#FEF2F2",      C["danger"],       self._cancel_invoice),
            ("🗑  Delete",     "#FEF2F2",      C["danger"],       self._delete_invoice),
        ]
        for text, bg, fg, cmd in btns:
            tk.Button(bar, text=text, font=("Segoe UI", 9),
                      bg=bg, fg=fg, relief="flat", padx=10, pady=6,
                      cursor="hand2",
                      highlightbackground=C["border"],
                      highlightthickness=1 if bg == C["card_bg"] else 0,
                      command=cmd).pack(side="left", padx=(0, 5))

        tk.Button(bar, text="🔄 Refresh", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_secondary"], relief="flat",
                  padx=10, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load_invoices).pack(side="right")

    # ── Load / Filter ─────────────────────────────────────────
    def _load_invoices(self):
        try:
            self._all_data = db.fetchall(
                "SELECT invoice_id, invoice_number, invoice_date, "
                "customer_name_en, invoice_type_code, "
                "subtotal_amount, vat_amount, total_amount, "
                "payment_status, paid_amount, invoice_status, zatca_status "
                "FROM sales_invoices ORDER BY invoice_date DESC, invoice_id DESC"
            )
        except Exception as e:
            self._all_data = []
            messagebox.showerror("DB Error", str(e))
        self._filter()

    def _filter(self):
        q      = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        status = self.status_var.get()          if hasattr(self, "status_var") else "all"
        zatca  = self.zatca_var.get()            if hasattr(self, "zatca_var")  else "all"

        filtered = []
        for r in self._all_data:
            if status != "all" and r.get("invoice_status") != status:
                continue
            if zatca != "all" and r.get("zatca_status") != zatca:
                continue
            if q:
                s = (str(r.get("invoice_number","")) +
                     str(r.get("customer_name_en",""))).lower()
                if q not in s:
                    continue
            filtered.append(r)

        self._populate_table(filtered)
        self._refresh_kpis(filtered)
        if hasattr(self, "count_var"):
            self.count_var.set(f"{len(filtered)} invoice(s)")

    def _populate_table(self, data):
        self.tree.delete(*self.tree.get_children())
        status_icons = {
            "confirmed": "✅", "draft": "📝", "cancelled": "❌"}
        payment_icons = {
            "paid": "💚 Paid", "unpaid": "🔴 Unpaid", "partial": "🟡 Partial"}
        zatca_icons = {
            "pending": "⏳", "reported": "📤", "cleared": "✅", "rejected": "❌"}
        type_map = {"388": "TAX", "381": "CREDIT", "383": "DEBIT"}

        for r in data:
            inv_status = r.get("invoice_status", "draft")
            self.tree.insert("", "end",
                iid=str(r["invoice_id"]),
                values=(
                    r.get("invoice_number", ""),
                    str(r.get("invoice_date", "")),
                    r.get("customer_name_en", ""),
                    type_map.get(r.get("invoice_type_code","388"), "TAX"),
                    f"{float(r.get('subtotal_amount') or 0):,.2f}",
                    f"{float(r.get('vat_amount') or 0):,.2f}",
                    f"{float(r.get('total_amount') or 0):,.2f}",
                    payment_icons.get(r.get("payment_status","unpaid"), "—"),
                    f"{status_icons.get(inv_status,'📄')} {inv_status.title()}",
                    zatca_icons.get(r.get("zatca_status","pending"), "⏳"),
                ),
                tags=(inv_status,)
            )

    def _sort(self, col):
        data = [(self.tree.set(c, col), c)
                for c in self.tree.get_children()]
        data.sort(key=lambda x: x[0])
        for i, (_, child) in enumerate(data):
            self.tree.move(child, "", i)

    # ── CRUD actions ──────────────────────────────────────────
    def _receive_payment(self):
        """Receipt for the selected invoice (settles it, rest = advance)."""
        from modules import permissions as _pm
        if not _pm.allowed("receipt", "add"):
            return False
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        inv = db.fetchone("SELECT customer_id, invoice_status, payment_status, "
                          "invoice_number FROM sales_invoices WHERE invoice_id=?",
                          (inv_id,)) or {}
        if (inv.get("invoice_status") or "") != "confirmed":
            messagebox.showinfo("Receive Payment",
                                "Only confirmed invoices can receive a payment.")
            return
        if (inv.get("payment_status") or "") == "paid":
            messagebox.showinfo("Receive Payment",
                                f"Invoice {inv.get('invoice_number')} is already paid.")
            return
        from ui.payments import PaymentForm
        PaymentForm(self.frame, "receipt", self._load_invoices,
                    party_id=inv.get("customer_id"), doc_id=inv_id)

    def _whatsapp(self):
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        try:
            from ui.whatsapp_send import send_document
            send_document(self.frame, "sales", inv_id)
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:300])

    def _get_sel_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select an invoice.")
            return None
        return int(sel[0])

    def _new_invoice(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "add"):
            return False
        InvoiceForm(self.frame, invoice_id=None, on_save=self._load_invoices)

    def _open_invoice(self):
        inv_id = self._get_sel_id()
        if inv_id:
            InvoiceForm(self.frame, invoice_id=inv_id,
                        view_only=True, on_save=self._load_invoices)

    def _edit_invoice(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "edit"):
            return False
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        # the same invoice already open → bring that window to the front
        close_guard.single(("sales", inv_id), lambda: self._open_edit(inv_id),
                           match=lambda f: getattr(f, "invoice_id", None) == inv_id)

    def _open_edit(self, inv_id):
        # confirmed invoices can be corrected too: on save the old stock
        # and journal are reversed and the new ones posted (doc_edit)
        from modules import doc_edit
        why = doc_edit.block_reason("sales", inv_id, "edit")
        if why:
            messagebox.showwarning("Edit Invoice", why)
            return
        q = doc_edit.ask_text("sales", inv_id, "edit")
        if q and not messagebox.askyesno("Edit Invoice", q):
            return
        return InvoiceForm(self.frame, invoice_id=inv_id, on_save=self._load_invoices)

    def _confirm_invoice(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "edit"):
            return False
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        inv = db.fetchone(
            "SELECT invoice_status, total_amount, vat_amount, invoice_number, "
            "invoice_date, invoice_time, qr_code_data FROM sales_invoices "
            "WHERE invoice_id=?", (inv_id,))
        if not inv:
            return
        if inv["invoice_status"] == "confirmed":
            messagebox.showinfo("Info", "Invoice already confirmed.")
            return
        if inv["invoice_status"] == "cancelled":
            messagebox.showerror("Error", "Cancelled invoices cannot be confirmed.")
            return

        if not messagebox.askyesno("Confirm Invoice",
                                   f"Confirm invoice {inv['invoice_number']}?\n"
                                   f"Total: {float(inv['total_amount'] or 0):,.2f} SAR"):
            return

        # Stock out + sale journal + cost of sales (one engine for all docs);
        # status, ZATCA signing and posting are kept together (v5.27)
        from modules import doc_posting
        try:
            with db.transaction():
                db.execute(
                    "UPDATE sales_invoices SET invoice_status='confirmed', "
                    "updated_at=GETDATE() WHERE invoice_id=?", (inv_id,))
                try:            # a draft confirmed here joins the ZATCA chain too
                    from modules.zatca import egs as _zegs
                    _zegs.after_save("sales", inv_id)
                except Exception:
                    pass
                try:
                    doc_posting.sync("sales", inv_id)
                except Exception as e:
                    doc_posting.last_warning = str(e)[:200]
        except Exception as e:
            messagebox.showerror("Not confirmed", "Nothing was changed:\n" + str(e)[:300])
            return
        messagebox.showinfo("✅ Confirmed",
                            f"Invoice {inv['invoice_number']} confirmed!")
        doc_posting.notify(self.frame)
        self._load_invoices()

    def _cancel_invoice(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "delete"):
            return False
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        inv = db.fetchone(
            "SELECT invoice_number, invoice_status FROM sales_invoices "
            "WHERE invoice_id=?", (inv_id,))
        if not inv:
            return
        if inv["invoice_status"] == "cancelled":
            messagebox.showinfo("Info", "Already cancelled.")
            return
        from modules import doc_edit
        why = doc_edit.block_reason("sales", inv_id, "cancel")
        if why:                 # e.g. signed for ZATCA → a credit note is the way
            messagebox.showwarning("Cancel Invoice", why)
            return
        if not messagebox.askyesno("Cancel Invoice",
                                   f"Cancel {inv['invoice_number']}? "
                                   "This cannot be undone."):
            return
        # a cancelled bill gives its stock back and leaves the books —
        # status + reversal together, or neither (v5.27)
        try:
            with db.transaction():
                db.execute(
                    "UPDATE sales_invoices SET invoice_status='cancelled', "
                    "updated_at=GETDATE() WHERE invoice_id=?", (inv_id,))
                from modules import doc_posting
                doc_posting.sync("sales", inv_id)
        except Exception as e:
            messagebox.showerror("Not cancelled", "Nothing was changed:\n" + str(e)[:300])
            return
        self._load_invoices()

    def _delete_invoice(self):
        """Hard-delete an invoice. Allowed for DRAFT and CANCELLED only —
        a confirmed (posted / ZATCA-reported) invoice must be cancelled
        first so the audit trail stays intact. Removes the invoice lines,
        the header, and any GL journal it posted."""
        try:
            from modules import permissions as _perm
            if not _perm.can("sales", "delete"):
                messagebox.showwarning(
                    "Access Denied",
                    "You don't have permission to delete sales invoices.")
                return
        except Exception:
            pass
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        from modules import doc_edit
        number, status, _d = doc_edit.info("sales", inv_id)
        why = doc_edit.block_reason("sales", inv_id, "delete")
        if why:
            messagebox.showwarning("Delete Invoice", why)
            return
        # a confirmed invoice: type its number (v6.9.3); a draft: Yes / No
        if not doc_edit.confirm_delete("sales", inv_id):
            return
        ok, msg = doc_edit.delete_document("sales", inv_id)
        if not ok:
            messagebox.showerror("Delete Invoice", msg)
        self._load_invoices()

    def _report_pdf(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "print"):
            return False
        """Printable Sales Register PDF of exactly what the list shows
        (current search / status / date filters applied)."""
        try:
            from modules.doc_actions import export_tree_pdf
            headers = ["Invoice #", "Date", "Customer", "Type", "Subtotal",
                       "VAT", "Total", "Paid", "Status", "ZATCA"]
            export_tree_pdf(self.frame, self.tree, "Sales_Register", headers,
                            title="Sales Invoice Register",
                            subtitle=f"{len(self.tree.get_children())} invoices")
        except Exception as e:
            messagebox.showerror("Report", str(e)[:300])

    def _print_preview(self):
        """List 'Print' button: Default / Dot-matrix / PDF for the selected
        saved invoice, Print to…, or the previous invoice."""
        inv_id = self._get_sel_id()
        if not inv_id:
            messagebox.showinfo("Print", "Select an invoice first.")
            return
        from ui import print_menu
        print_menu.show_menu(self.frame, self._print_kind(inv_id), lambda: inv_id)

    @staticmethod
    def _print_kind(inv_id):
        try:
            r = db.fetchone("SELECT sale_channel FROM sales_invoices WHERE invoice_id=?",
                            (inv_id,)) or {}
            return "pos" if str(r.get("sale_channel") or "").upper() == "POS" else "sales"
        except Exception:
            return "sales"

    def _export_pdf(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "export"):
            return False
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        try:
            from tkinter import filedialog
            import shutil, tempfile
            from modules import doc_print as DP
            doc = DP.load(self._print_kind(inv_id), inv_id)
            if not doc:
                messagebox.showerror("Error", "Invoice not found.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                initialfile=f"{doc['number']}.pdf")
            if not path:
                return
            made = DP.render_pdf(doc, folder=tempfile.gettempdir())
            shutil.copyfile(made, path)
            messagebox.showinfo("PDF Export", f"Invoice PDF saved:\n{path}")
            from modules import printer_service as ps
            ps.open_file(path)
        except ImportError:
            messagebox.showerror("Missing Library",
                "pip install reportlab arabic-reshaper python-bidi qrcode pillow")
        except Exception as e:
            messagebox.showerror("PDF Error", str(e))

    def _export_xml(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "export"):
            return False
        inv_id = self._get_sel_id()
        if not inv_id:
            return
        try:
            inv   = db.fetchone("SELECT * FROM sales_invoices WHERE invoice_id=?",
                                (inv_id,))
            lines = db.fetchall(
                "SELECT * FROM sales_invoice_lines WHERE invoice_id=?", (inv_id,))
            company = db.fetchone("SELECT * FROM company WHERE company_id=1")
            if not inv or not company:
                messagebox.showerror("Error", "Invoice or company data missing.")
                return
            # the signed / cleared XML when it went to ZATCA (Phase 2),
            # else a preview of the UBL XML DayBill makes for it
            xml = inv.get("zatca_cleared_xml") or inv.get("zatca_signed_xml")
            if not xml:
                from modules.zatca import egs as _zegs, phase2 as _p2
                doc, _probs = _zegs.build_doc("sales", inv_id)
                doc.update(icv=0, pih=_p2.GENESIS_PIH)
                xml = _p2.build_xml(doc)
            path = filedialog.asksaveasfilename(
                defaultextension=".xml",
                filetypes=[("XML", "*.xml")],
                initialfile=f"{inv['invoice_number']}.xml"
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(xml)
                messagebox.showinfo("✅ Exported",
                                    f"ZATCA XML saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _export_excel(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "export"):
            return False
        try:
            import openpyxl
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel","*.xlsx")],
                initialfile="Invoices.xlsx"
            )
            if not path:
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sales Invoices"
            ws.append(["Invoice #","Date","Customer","Subtotal","VAT",
                        "Total","Payment","Status","ZATCA"])
            for child in self.tree.get_children():
                vals = list(self.tree.item(child)["values"])
                ws.append(vals)
            wb.save(path)
            messagebox.showinfo("✅", f"Exported:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ─────────────────────────────────────────────────────────────
# INVOICE FORM (New / Edit / View)
# ─────────────────────────────────────────────────────────────
class InvoiceForm:
    def __init__(self, parent, invoice_id=None,
                 view_only=False, on_save=None):
        self.parent     = parent
        self.invoice_id = invoice_id
        self.view_only  = view_only
        self.on_save    = on_save
        self._lines     = []          # list of line dicts
        self._customers = []
        self._products  = []
        self._vat_cats  = []
        self._company   = {}
        self._load_lookups()
        self._build_window()
        if invoice_id:
            self._load_invoice()
        else:
            self._set_defaults()
        try:      # v6.9 connector bar: New · Edit · Save · Delete (user rights)
            from ui import txn_connector as _tc
            _tc.attach(self, "sales", compact=True)   # has its own toolbar
        except Exception:
            pass

    # ── Lookups ───────────────────────────────────────────────
    def _load_lookups(self):
        try:
            self._customers = db.fetchall(
                "SELECT customer_id, customer_code, customer_name_en, "
                "customer_name_ar, customer_type, vat_registration_no, "
                "city_en, phone, building_number, street_name_en, "
                "district_en, postal_code, country_code" + _state_col() + " "
                "FROM customers WHERE is_active=1 ORDER BY customer_name_en"
            )
            self._products = db.fetchall(
                "SELECT p.product_id, p.product_code, p.product_name_en, "
                "p.product_name_ar, p.unit_price, p.unit_of_measure_en, "
                "p.unit_of_measure_ar, p.vat_category_id, "
                "ISNULL(p.alias_name,'') AS alias_name, "
                "ISNULL(p.purchase_price,0) AS purchase_price, "
                "ISNULL(p.stock_quantity,0) AS stock_quantity, "
                "ISNULL(p.barcode,'') AS barcode, " + sys_select("p") + ", "
                "vc.category_code AS vat_code, vc.vat_rate "
                "FROM products p "
                "LEFT JOIN vat_categories vc ON p.vat_category_id=vc.vat_category_id "
                "WHERE p.is_active=1 AND ISNULL(p.list_in_sales,1)=1 "
                "ORDER BY p.product_name_en"
            )
            self._vat_cats = db.fetchall(
                "SELECT * FROM vat_categories WHERE is_active=1 ORDER BY vat_rate DESC"
            )
            # Preload sales units per product: {product_id: [unit rows]}
            self._product_units = {}
            try:
                all_units = db.fetchall(
                    "SELECT * FROM product_units WHERE is_active=1 AND is_sales_unit=1 "
                    "ORDER BY is_default DESC, unit_id")
                for u in all_units:
                    self._product_units.setdefault(u["product_id"], []).append(u)
            except Exception:
                self._product_units = {}
            self._company = db.fetchone(
                "SELECT * FROM company WHERE company_id=1") or {}
        except Exception:
            pass
        # Salesmen (from users) and warehouses — both optional/guarded
        self._salesmen = []
        try:
            rows = db.fetchall("SELECT full_name_en AS full_name FROM users "
                               "WHERE is_active=1 ORDER BY full_name_en")
            self._salesmen = [r["full_name"] for r in (rows or []) if r.get("full_name")]
        except Exception:
            self._salesmen = []
        self._warehouses = []
        try:                       # optional table — ask first, no DB error
            if db.execute_scalar("SELECT OBJECT_ID('warehouses','U')"):
                rows = db.fetchall("SELECT warehouse_name_en AS n FROM warehouses "
                                   "WHERE is_active=1 ORDER BY warehouse_name_en")
                self._warehouses = [r["n"] for r in (rows or []) if r.get("n")]
        except Exception:
            self._warehouses = []
        if not self._warehouses:
            self._warehouses = ["Main Warehouse"]
    def _build_window(self):
        C = cfg.theme()
        title = ("View Invoice" if self.view_only
                 else ("Edit Invoice" if self.invoice_id else "New Invoice"))

        self.win = tk.Toplevel()
        self.win._doc_window = True     # item grid: may fill the screen
        self.win._form = self           # v6.7: compact header (ui/compact.py)
        self.win.title(title)
        w = min(1360, int(self.win.winfo_screenwidth() * 0.90))
        h = min(840, int(self.win.winfo_screenheight() * 0.92))
        self.win.geometry(f"{w}x{h}")
        self.win.resizable(True, True)
        self.win.configure(bg=C["content_bg"])
        # NOTE: no grab_set() — allow several invoice windows open at once.
        self._center(w, h)

        # Keyboard shortcuts (per the ERP transaction-window spec):
        #   F2 Product Search · F3 Customer/Supplier Search · F4 Barcode
        #   Search · F5 Refresh · F6 Discount · F7 Tax Details · F8 Payment
        #   F9 Save · F10 Print · Esc Cancel/Close
        if not self.view_only:
            self.win.bind("<F2>", lambda e: self._focus_product())
            self.win.bind("<F3>", lambda e: self._focus_customer())
            self.win.bind("<F4>", lambda e: self._focus_barcode())
            self.win.bind("<F5>", lambda e: self._update_totals())
            self.win.bind("<F6>", lambda e: self.bill_discount_entry.focus_set()
                          if hasattr(self, "bill_discount_entry") else None)
            self.win.bind("<F7>", lambda e: self._show_tax_details())
            self.win.bind("<F8>", lambda e: self.cash_var_entry.focus_set()
                          if hasattr(self, "cash_var_entry") else None)
            self.win.bind("<F9>", lambda e: self._save(confirm=False))
            self.win.bind("<F10>", lambda e: self._save_and_print("default"))
            self.win.bind("<F11>", lambda e: self._save_and_print("dotmatrix"))
            self.win.bind("<F12>", lambda e: self._save_and_print("pdf"))
        close_guard.bind_escape(self.win)     # Esc = ✕ (asks if lines are unsaved)

        # ── Minimal header band ───────────────────────────────
        hdr = tk.Frame(self.win, bg=C["primary"], height=40)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        icon = "👁" if self.view_only else ("✏️" if self.invoice_id else "🧾")
        tk.Label(hdr, text=f"{icon}  {title}",
                 font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)
        self.inv_num_label = tk.Label(hdr, text="",
                                       font=("Segoe UI", 11, "bold"),
                                       bg=C["primary"], fg="#CFC6FF")
        self.inv_num_label.pack(side="right", padx=16)

        # ── Compact form header (top) ─────────────────────────
        self.form_body = tk.Frame(self.win, bg=C["card_bg"],
                                  highlightbackground=C["border"],
                                  highlightthickness=1)
        self.form_body.pack(side="top", fill="x")

        # ── Big line-items grid (fills the middle) ────────────
        # v6.9: packed LAST (below) so the header, totals and buttons are
        # always whole and the grid takes exactly the room that is left
        self.items_area = tk.Frame(self.win, bg=C["content_bg"])

        self._build_form_header(C)
        self._build_line_items(C)
        # Footer action buttons pinned to the very bottom first…
        self._build_footer(C)
        # …then the totals + payment bar just above the footer.
        self.bottom_bar = tk.Frame(self.win, bg=C["card_bg"],
                                   highlightbackground=C["border"],
                                   highlightthickness=1)
        self.bottom_bar.pack(side="bottom", fill="x")
        self._build_totals_bar(C)
        self._build_statusbar(C)
        self.items_area.pack(side="top", fill="both", expand=True)

    def _build_statusbar(self, C):
        """Slim Polosys-style status strip at the very bottom:
        app · financial-year range + user · today's date · DB/branch ·
        live clock."""
        # v6.9: the status sits in the footer line (no extra strip)
        sb = getattr(self, "_footer_info", None)
        sbg = C["card_bg"] if sb is not None else "#EEF1F6"
        if sb is None:
            sb = tk.Frame(self.win, bg=sbg, height=22)
            sb.pack(side="bottom", fill="x")
            sb.pack_propagate(False)

        def cell(txt, side="left", bold=False):
            l = tk.Label(sb, text=txt, font=("Segoe UI", 8, "bold" if bold else "normal"),
                         bg=sbg, fg=C["text_secondary"], padx=6)
            l.pack(side=side)
            return l

        # financial year range + logged-in user
        fy_txt = ""
        try:
            from modules import financial_year as fy
            y = fy.current_year()
            if y:
                s = str(y.get("start_date", ""))[:10]
                e = str(y.get("end_date", ""))[:10]
                fy_txt = f"F.Y: {s} – {e}"
        except Exception:
            pass
        user_txt = ""
        try:
            from modules import audit as _a
            u = getattr(_a, "_user", {}) or {}
            user_txt = (u.get("full_name") or u.get("full_name_en")
                        or u.get("username") or "")
        except Exception:
            pass
        if fy_txt or user_txt:
            cell((fy_txt + ("   " + user_txt if user_txt else "")).strip())
        cell(date.today().strftime("%d/%m/%Y"))
        # DB / branch
        db_txt = ""
        try:
            comp = (self._company or {})
            db_txt = "DB: " + (comp.get("company_name_en") or "DayBill")
        except Exception:
            pass
        if db_txt:
            cell(db_txt)
        # live clock on the right
        self._clock_lbl = tk.Label(sb, text="", font=("Segoe UI", 8),
                                   bg=sbg, fg=C["text_secondary"], padx=6)
        self._clock_lbl.pack(side="left")

        def tick():
            try:
                if not self._clock_lbl.winfo_exists():
                    return
                self._clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
                self.win.after(1000, tick)
            except Exception:
                pass
        tick()

    # ── Form Header ───────────────────────────────────────────
    def _build_form_header(self, C):
        fb = self.form_body
        state = "disabled" if self.view_only else "normal"
        self.hdr_vars = {}
        self.hdr_vars["invoice_number"] = tk.StringVar()
        self.hdr_vars["invoice_date"]   = tk.StringVar()
        self.hdr_vars["due_date"]       = tk.StringVar()
        self.hdr_vars["po_number"]      = tk.StringVar()
        self.cust_info_var = tk.StringVar()

        # ── Toolbar (Polosys-style) ───────────────────────────
        tb = tk.Frame(fb, bg=C["card_bg"])
        tb.pack(fill="x", padx=6, pady=(2, 1))
        self._tools_bar = tb                 # v6.9: the voice switch sits here too
        tools = [
            ("\U0001f4be Save",        lambda: self._save(confirm=True)),
            ("\u270f Edit",            self._edit_focused_line),
            ("\U0001f5d1 Delete",      self._delete_current_invoice),
            ("\u2716 Clear",           self._clear_form),
            ("\U0001f5a8 Print",       lambda: self._save_and_print("default")),
            ("\U0001f504 Refresh",     self._update_totals),
            ("\U0001f4c2 Load &More",  lambda: self._nav("sales")),
            ("\u2699 Settings",        lambda: self._nav("settings")),
            ("\u2796 Remove Line",     self._remove_focused_line),
            ("\u274c Close",           self.win.destroy),
            ("\U0001f4e6 Prod Summary",lambda: self._nav("reports")),
            ("\U0001f465 Party Summary",lambda: self._nav("reports")),
            ("\U0001f50d Search",      self._focus_product),
            ("\U0001f4e5 Load Order",  self._load_order),          # v7.5: quotation / sales order
        ]
        for txt, cmd in tools:
            tk.Button(tb, text=txt, font=("Segoe UI", 8, "bold"),
                      bg=C["content_bg"], fg=C["text_primary"], relief="flat",
                      padx=6, pady=2, cursor="hand2", command=cmd).pack(side="left", padx=1)
        tk.Frame(fb, bg=C["border"], height=1).pack(fill="x")

        # v7.9: the header as titled blocks (Bill · Customer · Contact ·
        # Details) with the customer's balance card on the right
        from ui.doc_header import DocHeader
        F8, F10 = ("Segoe UI", 8), ("Segoe UI", 10)
        H = DocHeader(fb, C, pady=(4, 2))
        self._doc_header = H

        def ent(var, width=10, st=None, bold=False):
            return lambda p: tk.Entry(p, textvariable=var, width=width,
                                      font=("Segoe UI", 10, "bold") if bold else F10,
                                      relief="solid", bd=1, state=st or state)

        def small(parent, text, cmd, primary=False):
            return tk.Button(parent, text=text, font=("Segoe UI", 8, "bold" if primary else "normal"),
                             bg=C["primary"] if primary else C["content_bg"],
                             fg="white" if primary else C["text_primary"], relief="flat",
                             padx=6, cursor="hand2", command=cmd)

        # ── Bill: number (▲▼ browse) · date · find · draft
        self.vr_prefix_var = tk.BooleanVar(value=False)      # kept for older callers
        self.draft_mode_var = tk.BooleanVar(value=False)
        self.find_enabled = tk.BooleanVar(value=False)
        self.find_var = tk.StringVar()
        b1 = H.block("Bill", weight=2, minwidth=200)

        def nav_btns(p):
            f = tk.Frame(p, bg=C["card_bg"])
            for t_, cmd_ in (("▲", self._nav_prev), ("▼", self._nav_next)):
                tk.Button(f, text=t_, font=("Segoe UI", 7), width=2, padx=1, pady=0, bd=0,
                          bg=C["content_bg"], relief="flat", cursor="hand2",
                          command=cmd_).pack(side="left", padx=(1, 0))
            return f
        b1.row("No.", ent(self.hdr_vars["invoice_number"], 9, st="disabled", bold=True), extra=nav_btns)
        de = b1.row("Date", ent(self.hdr_vars["invoice_date"], 11))
        if state == "normal":
            try:
                from ui.datepicker import attach_datepicker
                attach_datepicker(de, self.hdr_vars["invoice_date"])
            except Exception:
                pass

        def find_box(p):
            self.find_entry = tk.Entry(p, textvariable=self.find_var, width=8, font=("Segoe UI", 9),
                                       relief="solid", bd=1, state="disabled")
            self.find_entry.bind("<Return>", lambda e: self._find_invoice())
            return self.find_entry
        b1.row("Find", find_box, extra=lambda p: tk.Checkbutton(
            p, variable=self.find_enabled, command=self._toggle_find, bg=C["card_bg"],
            activebackground=C["card_bg"], highlightthickness=0))
        b1.flags([("Draft", self.draft_mode_var, None, C["danger"])])

        # ── Customer: list · name · tax no. (a customer not in the list prints what is typed)
        self.payment_var = tk.StringVar(value="cash")
        self.credit_acct_var = tk.BooleanVar(value=False)
        self.sales_acct_var = tk.BooleanVar(value=True)
        self.cust_var = tk.StringVar()
        self.cust_name_var = tk.StringVar()
        self.cust_addr_var = tk.StringVar()
        self.cust_mobile_var = tk.StringVar()
        self.cust_vat_var = tk.StringVar()
        cust_opts = [f"{c['customer_code']} \u2014 {c['customer_name_en']}"
                     for c in self._customers]
        b2 = H.block("Customer", weight=4, minwidth=300)

        def cust_box(p):
            self.cust_combo = ttk.Combobox(p, textvariable=self.cust_var, values=cust_opts,
                                           state="readonly", font=F10, width=24)
            self.cust_combo.bind("<<ComboboxSelected>>", self._on_customer_select)
            return self.cust_combo

        def cust_btns(p):
            f = tk.Frame(p, bg=C["card_bg"])
            if not self.view_only:
                small(f, "＋", self._new_customer, primary=True).pack(side="left")
            return f
        b2.row("Customer", cust_box, extra=cust_btns, required=True)
        b2.row("Name", ent(self.cust_name_var, 18))
        try:
            from modules import country as _ctry0
            _tax_lbl = _ctry0.tax_no_label()
        except Exception:
            _tax_lbl = "VAT No."
        b2.row(_tax_lbl, ent(self.cust_vat_var, 16))

        def _credit_toggle():
            self.payment_var.set("credit" if self.credit_acct_var.get() else "cash")
        self.sales_account_var = tk.StringVar(value="Sales Account")
        b2.widget_row(lambda p: (
            tk.Checkbutton(p, text="Credit", variable=self.credit_acct_var, command=_credit_toggle,
                           font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                           activebackground=C["card_bg"], highlightthickness=0).pack(side="left"),
            tk.Checkbutton(p, text="Sales A/c", variable=self.sales_acct_var, font=("Segoe UI", 9),
                           bg=C["card_bg"], fg=C["text_secondary"], activebackground=C["card_bg"],
                           highlightthickness=0).pack(side="left", padx=(8, 0)),
            ttk.Combobox(p, textvariable=self.sales_account_var, values=["Sales Account"],
                         font=("Segoe UI", 9), state="readonly", width=13).pack(side="left", padx=(4, 0))))

        # ── Contact & reference
        self.minv_var = tk.StringVar()
        b3 = H.block("Contact & ref.", weight=2, minwidth=210)
        b3.row("Mobile", ent(self.cust_mobile_var, 12))
        b3.row("Address", ent(self.cust_addr_var, 12))
        b3.row("Ref No.", ent(self.hdr_vars["po_number"], 8),
               extra=lambda p: tk.Entry(p, textvariable=self.hdr_vars["due_date"], font=F10,
                                        relief="solid", bd=1, width=10, state=state))
        b3.row("M.Inv", ent(self.minv_var, 8))

        # ── Details: store · salesman · place of supply · send to
        self.salesman_var = tk.StringVar()
        self.warehouse_var = tk.StringVar(
            value=self._warehouses[0] if self._warehouses else "Primary")
        b4 = H.block("Details", weight=2, minwidth=200)
        b4.row("Store", lambda p: ttk.Combobox(
            p, textvariable=self.warehouse_var, values=self._warehouses or ["Primary"], font=F10,
            width=10, state="readonly" if state == "normal" else "disabled"))
        b4.row("Salesman", lambda p: ttk.Combobox(
            p, textvariable=self.salesman_var, values=self._salesmen, font=F10, width=10,
            state="normal" if state == "normal" else "disabled"))
        # v7.0 India: place of supply → CGST + SGST (same state) or IGST
        self.pos_var = tk.StringVar()
        try:
            from modules import country as _ctry
            if _ctry.is_in():
                def pos_box(p):
                    self.pos_combo = ttk.Combobox(
                        p, textvariable=self.pos_var, font=F10, width=16,
                        values=["%s - %s" % (k, n) for k, n in _ctry.states()],
                        state="readonly" if state == "normal" else "disabled")
                    self.pos_combo.bind("<<ComboboxSelected>>", lambda e: self._update_totals())
                    return self.pos_combo
                b4.row("Supply to", pos_box)
                self.pos_var.set(_ctry.state_label(_ctry.company_state()))
        except Exception:
            pass
        # v7.5: print stations — pick the tailor / picker / kitchen this sale goes to
        self.station_var = tk.StringVar(value="Auto")
        self._station_ids = {}
        try:
            from modules import print_stations as _PS
            _sts = _PS.stations(doc_kind="sales")
        except Exception:
            _sts = []
        if _sts:
            self._station_ids = {"%s" % st["name"]: st["station_id"] for st in _sts}
            b4.row("Send to", lambda p: ttk.Combobox(p, textvariable=self.station_var, state="readonly",
                                                    width=14, font=F8,
                                                    values=["Auto"] + list(self._station_ids)))
        self.in_search_var = tk.BooleanVar(value=True)
        b4.widget_row(lambda p: (
            tk.Checkbutton(p, text="In Search", variable=self.in_search_var, font=("Segoe UI", 9),
                           bg=C["card_bg"], fg=C["accent_dark"], activebackground=C["card_bg"],
                           highlightthickness=0).pack(side="left"),
            small(p, "⤓ Last row", self._goto_last_row).pack(side="left", padx=(6, 0))))

        # ── the customer's balance card (+ stock / more)
        self._bal_card = H.balance_card()
        if not self.view_only:
            small(self._bal_card.tools, "W/Stock", lambda: self._nav("inventory")).pack(side="left")
            small(self._bal_card.tools, "More", lambda: self._nav("settings")).pack(side="left", padx=(4, 0))
        self.win.bind("<Control-End>", lambda e: self._goto_last_row())

    def _build_line_items(self, C):
        fb    = self.items_area

        # v6.9: no "Line Items" title line — the grid starts right under
        # the header; the voice switch lives on the toolbar
        items_hdr = getattr(self, "_tools_bar", None) or tk.Frame(fb, bg=C["content_bg"])
        if items_hdr.master is fb:
            items_hdr.pack(fill="x", padx=16, pady=(4, 0))

        if not self.view_only:
            # 🎤 Voice search: ON/OFF toggle lives right here in the sales
            # window; the Speak button only shows while voice is active.
            self._voice_on = tk.BooleanVar(
                value=bool(cfg.get("voice_search_enabled", False)))
            self.voice_speak_btn = tk.Button(
                items_hdr, text="🎤 Speak", font=("Segoe UI", 8, "bold"),
                bg="#16A085", fg="white", relief="flat", padx=8, pady=2,
                cursor="hand2", command=self._voice_search)
            self.voice_toggle_btn = tk.Button(
                items_hdr, font=("Segoe UI", 8), relief="flat", padx=8,
                pady=2, cursor="hand2", command=self._toggle_voice)
            self.voice_toggle_btn.pack(side="right", padx=(0, 8))
            self._voice_apply_state()

        # New Polosys-style editable grid
        try:
            from ui.invoice_grid import InvoiceGrid
            self.line_grid = InvoiceGrid(fb, C, self._products, self._product_units,
                                    on_change=self._on_grid_change,
                                    tax_mode=cfg.get("sales_price_tax_mode", "inclusive"),
                                    doc_type="sales", use_offers=True)
            self.line_grid.pack(fill="both", expand=True, padx=8, pady=(4, 0))
            self.line_grid.on_customer_code = self._loyalty_card     # v7.5: scan the QR card
            if not self.view_only:       # v7.0: Textiles size / colour grid (Ctrl+G)
                try:
                    from ui import textiles as _tx
                    _tx.attach_matrix(self.win, self.line_grid, items_hdr)
                except Exception:
                    pass
            # now that the grid exists, sync totals once
            self._on_grid_change()
            # focus the first product cell for fast selling
            if not self.view_only:
                self.line_grid.focus_first_product()
        except Exception as e:
            import traceback
            traceback.print_exc()
            tk.Label(fb, text=f"⚠ Could not load line-items grid:\n{e}",
                     font=("Segoe UI", 10), bg=C["content_bg"],
                     fg=C["danger"], justify="left").pack(
                         anchor="w", padx=16, pady=20)

    # ── Invoice navigation / find ─────────────────────────────
    def _toggle_find(self):
        on = self.find_enabled.get()
        self.find_entry.configure(state="normal" if on else "disabled")
        if on:
            self.find_entry.focus_set()

    def _find_invoice(self):
        if not getattr(self, "find_enabled", None) or not self.find_enabled.get():
            return
        num = self.find_var.get().strip()
        if not num:
            return
        row = db.fetchone(
            "SELECT invoice_id FROM sales_invoices WHERE invoice_number=?", (num,))
        if not row:
            row = db.fetchone(
                "SELECT TOP 1 invoice_id FROM sales_invoices "
                "WHERE invoice_number LIKE ? ORDER BY invoice_id DESC",
                ("%" + num + "%",))
        if row:
            self._goto_invoice(row["invoice_id"])
        else:
            messagebox.showinfo("Not found", f"No invoice matching '{num}'.")

    def _nav_prev(self):
        cur = self.invoice_id
        if cur:
            row = db.fetchone("SELECT TOP 1 invoice_id FROM sales_invoices "
                              "WHERE invoice_id<? ORDER BY invoice_id DESC", (cur,))
        else:
            row = db.fetchone("SELECT TOP 1 invoice_id FROM sales_invoices "
                              "ORDER BY invoice_id DESC")
        if row:
            self._goto_invoice(row["invoice_id"])
        else:
            messagebox.showinfo("Navigation", "No earlier invoice found.")

    def _nav_next(self):
        cur = self.invoice_id
        if not cur:
            messagebox.showinfo("Navigation", "Already on a new invoice.")
            return
        row = db.fetchone("SELECT TOP 1 invoice_id FROM sales_invoices "
                          "WHERE invoice_id>? ORDER BY invoice_id ASC", (cur,))
        if row:
            self._goto_invoice(row["invoice_id"])
        else:
            messagebox.showinfo("Navigation",
                                "This is the latest invoice. Use ＋ for a new one.")

    def _goto_invoice(self, invoice_id):
        """Load an existing invoice into this same window (browse mode)."""
        self.invoice_id = invoice_id
        try:
            self.line_grid.set_lines([])
        except Exception:
            pass
        try:
            self._load_invoice()
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _delete_current_invoice(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "delete"):
            return False
        """Toolbar 🗑 Delete — removes the bill currently loaded in this
        window (after browsing to it with ▲▼ or Find). Same rules as the
        list view: DRAFT / CANCELLED delete fully (lines + posted
        journals); CONFIRMED must be cancelled first. Afterwards the
        window resets to a fresh new invoice."""
        if not self.invoice_id:
            messagebox.showinfo(
                "Delete", "No saved invoice is loaded.\nUse ▲ ▼ or Find to "
                "load a bill first — or use ➖ Remove Line for grid lines.")
            return
        from modules import doc_edit
        number, status, _d = doc_edit.info("sales", self.invoice_id)
        why = doc_edit.block_reason("sales", self.invoice_id, "delete")
        if why:
            messagebox.showwarning("Delete Invoice", why)
            return
        # a confirmed invoice: type its number (v6.9.3); a draft: Yes / No
        if not doc_edit.confirm_delete("sales", self.invoice_id, self.win):
            return
        ok, msg = doc_edit.delete_document("sales", self.invoice_id)
        if not ok:
            messagebox.showerror("Delete Invoice", msg)
            return
        # reset the window to a brand-new invoice
        self.invoice_id = None
        self._clear_form()
        self._set_defaults()
        if self.on_save:
            try:
                self.on_save()
            except Exception:
                pass

    def _new_customer(self):
        """Open the customer form; reload + auto-select the new customer."""
        try:
            from ui.customers import CustomerForm
            CustomerForm(self.win, on_save=self._after_new_customer)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _after_new_customer(self, *args):
        try:
            self._customers = db.fetchall(
                "SELECT * FROM customers WHERE is_active=1 "
                "ORDER BY customer_id DESC") or []
            opts = [f"{c['customer_code']} — {c['customer_name_en']}"
                    for c in self._customers]
            self.cust_combo.configure(values=opts)
            if self._customers:
                newest = self._customers[0]
                self.cust_combo.set(f"{newest['customer_code']} — "
                                    f"{newest['customer_name_en']}")
                self._on_customer_select()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_grid_change(self):
        """Bridge: keep self._lines in sync and refresh totals panel.
        This can fire while InvoiceGrid is still being constructed (before
        self.line_grid is assigned), so read the grid defensively."""
        grid = getattr(self, "line_grid", None)
        if grid is None:
            return
        self._lines = grid.data_lines()
        try:
            self._update_totals()
        except Exception:
            pass

    # ── F-key helpers ─────────────────────────────────────────
    def _focus_customer(self):
        try:
            self.cust_combo.focus_set()
            self.cust_combo.event_generate("<Down>")
        except Exception:
            pass

    def _loyalty_card(self, code):
        """A customer's loyalty QR card scanned into the barcode box."""
        try:
            from modules import loyalty_qr as LQ
            c = LQ.customer_for(code)
        except Exception:
            c = None
        if not c:
            messagebox.showwarning("Loyalty card", "This card is not valid (a newer card was made?).",
                                   parent=self.win)
            return False
        cust = next((x for x in self._customers if x["customer_id"] == c["customer_id"]), None)
        if cust:
            self.cust_combo.set(f"{cust['customer_code']} — {cust['customer_name_en']}")
            self._on_customer_select()
        return bool(cust)

    def _load_order(self):
        """📥 Load a quotation / sales order: pick it, pick its lines and
        quantities (what is still left) → they go on this invoice."""
        if getattr(self, "view_only", False):
            return None
        from ui.quotes import load_order_into
        return load_order_into(self, "sales")

    def _focus_product(self):
        try:
            self.line_grid.focus_first_product()
        except Exception:
            pass

    def _focus_barcode(self):
        try:
            self.line_grid.focus_barcode()
        except Exception:
            pass

    def _show_tax_details(self):
        """F7 — quick tax breakdown for the current invoice."""
        try:
            lines = self.line_grid.data_lines()
        except Exception:
            lines = []
        by_rate = {}
        for ln in lines:
            rate = float(ln.get("vat_rate", 0) or 0)
            by_rate.setdefault(rate, [0.0, 0.0])
            by_rate[rate][0] += float(ln.get("line_amount", 0) or 0)
            by_rate[rate][1] += float(ln.get("vat_amount", 0) or 0)
        if not by_rate:
            messagebox.showinfo("Tax Details", "No lines yet.")
            return
        lines_txt = "\n".join(
            f"{rate:g}% VAT  —  Taxable {net:,.2f}  →  VAT {vat:,.2f}"
            for rate, (net, vat) in sorted(by_rate.items()))
        messagebox.showinfo("Tax Details (F7)", lines_txt)

    def _add_line(self, line_data=None):
        """Add one line item row. (Legacy path — the active UI uses the grid.
        Guarded so it can never crash if the old container is absent.)"""
        if not hasattr(self, "lines_container"):
            return
        C = cfg.theme()
        idx = len(self._lines)

        line = line_data or {
            "product_id": None, "product_name_en": "", "product_name_ar": "",
            "product_code": "", "quantity": 1.0, "unit_price": 0.0,
            "discount_percent": 0.0, "discount_amount": 0.0,
            "line_amount": 0.0, "vat_category_id": None,
            "vat_category_code": "S", "vat_rate": 15.0,
            "vat_amount": 0.0, "line_total": 0.0,
            "unit_of_measure_en": "Unit",
        }
        self._lines.append(line)

        row_frame = tk.Frame(self.lines_container, bg="white",
                              highlightbackground=C["border"],
                              highlightthickness=1)
        row_frame.pack(fill="x", pady=(0,2))
        line["_row"] = row_frame

        # Line number
        tk.Label(row_frame, text=str(idx+1),
                 font=("Segoe UI", 9), bg="white",
                 fg=C["text_secondary"], width=3).pack(side="left", padx=4)

        # Product combobox
        prod_var = tk.StringVar(value=line.get("product_name_en",""))
        line["_prod_var"] = prod_var
        prod_opts = [self._prod_label(p) for p in self._products]
        prod_combo = ttk.Combobox(row_frame, textvariable=prod_var,
                                   values=prod_opts, width=26,
                                   font=("Segoe UI", 9))
        prod_combo.pack(side="left", padx=2, ipady=6)
        prod_combo.bind("<<ComboboxSelected>>",
                        lambda e, i=idx: self._on_product_select(i))
        # Live partial search: filter dropdown as the cashier types
        prod_combo.bind("<KeyRelease>",
                        lambda e, i=idx: self._rich_search(e, i))
        # Enter in the product box → auto-pick the best match, jump to Qty
        prod_combo.bind("<Return>", lambda e, i=idx: self._fast_pick_product(i))
        line["_prod_combo"] = prod_combo

        # Unit selector (multi-unit sell). Cashier can change unit per line.
        unit_var = tk.StringVar(value=line.get("unit_of_measure_en", "Unit"))
        line["_unit_var"] = unit_var
        unit_combo = ttk.Combobox(row_frame, textvariable=unit_var,
                                  values=[line.get("unit_of_measure_en", "Unit")],
                                  width=9, font=("Segoe UI", 9), state="readonly")
        unit_combo.pack(side="left", padx=2, ipady=6)
        line["_unit_combo"] = unit_combo
        unit_combo.bind("<<ComboboxSelected>>",
                        lambda e, i=idx: self._on_unit_select(i))
        # Keyboard shortcut: Space or Tab on the unit box cycles to next unit
        unit_combo.bind("<space>", lambda e, i=idx: self._cycle_unit(i))
        prod_combo.bind("<Tab>", lambda e, i=idx: self._focus_unit(i))

        def _make_num_entry(var_key, width, default):
            var = tk.StringVar(value=str(default))
            line[f"_{var_key}_var"] = var
            e = tk.Entry(row_frame, textvariable=var,
                         font=("Segoe UI", 9), bg="white",
                         relief="flat", bd=0, width=width,
                         fg=C["text_primary"], justify="right")
            e.pack(side="left", padx=2, ipady=6)
            e.bind("<FocusOut>", lambda ev, i=idx: self._recalc_line(i))
            e.bind("<Return>",   lambda ev, i=idx: self._recalc_line(i))
            line[f"_{var_key}_entry"] = e
            return var

        _make_num_entry("qty",      7,  line["quantity"])
        _make_num_entry("price",    9,  line["unit_price"])
        _make_num_entry("disc",     6,  line["discount_percent"])

        # ── Fast grocery flow keyboard wiring ─────────────────
        # Enter on Qty → confirm line and jump to a NEW line's product box
        qty_e = line.get("_qty_entry")
        price_e = line.get("_price_entry")
        if qty_e is not None:
            qty_e.bind("<Return>", lambda ev, i=idx: self._fast_next(i))
            # Down arrow also advances (familiar to cashiers)
            qty_e.bind("<Down>", lambda ev, i=idx: self._fast_next(i))
        if price_e is not None:
            # Enter on price → go to qty of same line
            price_e.bind("<Return>", lambda ev, i=idx: self._focus_qty(i))

        # Read-only computed fields
        self._make_ro_field(row_frame, "_amt_var",   f"{line['line_amount']:.2f}",  9, C)
        self._make_ro_field(row_frame, "_vat_var",   f"{line['vat_rate']:.0f}%",    5, C)
        self._make_ro_field(row_frame, "_total_var", f"{line['line_total']:.2f}",  10, C)
        line["_ro_fields_added"] = True

        # Delete button
        if not self.view_only:
            tk.Button(row_frame, text="✕",
                      font=("Segoe UI", 8), bg="white", fg=C["danger"],
                      relief="flat", padx=4, cursor="hand2",
                      command=lambda i=idx: self._remove_line(i)).pack(
                          side="left", padx=2)

        self._update_totals()

    def _make_ro_field(self, parent, key, value, width, C):
        var = tk.StringVar(value=value)
        tk.Label(parent, textvariable=var,
                 font=("Segoe UI", 9, "bold"),
                 bg="white", fg=C["text_primary"],
                 width=width, anchor="e").pack(side="left", padx=2)
        return var

    def _toggle_voice(self):
        """Activate / deactivate voice search from the sales window.
        Persists to settings so POS/other screens see the same state."""
        on = not bool(self._voice_on.get())
        self._voice_on.set(on)
        cfg.set("voice_search_enabled", on)
        try:
            cfg.save_settings()
        except Exception:
            pass
        self._voice_apply_state()
        if on:
            try:
                from modules import voice_search as vs
                if not vs.is_available():
                    self.save_status.set("🎤 Voice ON — but: " +
                                         vs.unavailable_reason().split("\n")[0])
                    return
            except Exception:
                pass
            self.save_status.set("🎤 Voice search active — press Speak "
                                 "(or Ctrl+M) and say e.g. '3 pepsi'.")
        else:
            self.save_status.set("Voice search off.")

    def _voice_apply_state(self):
        on = bool(self._voice_on.get())
        self.voice_toggle_btn.configure(
            text="🎤 Voice: ON" if on else "🎙 Voice: OFF",
            bg="#27AE60" if on else "#95A5A6", fg="white")
        if on:
            self.voice_speak_btn.pack(side="right", padx=(0, 6),
                                      before=self.voice_toggle_btn)
            try:
                self.win.bind("<Control-m>", lambda e: self._voice_search())
            except Exception:
                pass
        else:
            self.voice_speak_btn.pack_forget()
            try:
                self.win.unbind("<Control-m>")
            except Exception:
                pass

    def _voice_search(self):
        """Listen on the mic in the BACKGROUND (UI stays live), then add
        the spoken product — with quantity if spoken ('3 pepsi')."""
        if not bool(getattr(self, "_voice_on", None) and self._voice_on.get()):
            return
        try:
            from modules import voice_search as vs
        except Exception:
            messagebox.showinfo("Voice Search", "Voice module not available.")
            return
        if not vs.is_available():
            messagebox.showinfo("Voice Search Unavailable",
                                vs.unavailable_reason())
            return
        if getattr(self, "_voice_busy", False):
            return                                  # one listen at a time
        self._voice_busy = True
        lang = "ar-SA" if cfg.get("language", "en") == "ar" else "en-US"
        self.voice_speak_btn.configure(text="👂 Listening…", bg="#E67E22")
        self.save_status.set("🎤 Listening — speak the product now "
                             "(e.g. '3 pepsi')…")

        # Thread-safe handoff: the worker only writes into a plain list;
        # the Tk thread polls it (never call Tk from another thread).
        box = []
        self._voice_box = box

        def done(text, err):
            box.append((text, err))

        vs.listen_async(done, lang)
        self._voice_poll()

    def _voice_poll(self):
        box = getattr(self, "_voice_box", None)
        if box is None:
            return
        if not box:
            try:
                self.frame.after(120, self._voice_poll)
            except Exception:
                pass
            return
        text, err = box[0]
        self._voice_box = None
        self._voice_result(text, err)

    def _voice_result(self, text, err):
        self._voice_busy = False
        try:
            self.voice_speak_btn.configure(text="🎤 Speak", bg="#16A085")
        except Exception:
            pass
        if err:
            self.save_status.set("🎤 " + str(err)[:90])
            return
        from modules.voice_search import parse_qty_and_name
        qty, name = parse_qty_and_name(text)
        matches = self.line_grid._search(name or text)
        if not matches:
            self.save_status.set(f"🎤 Heard '{text}' — no match. Try again.")
            try:
                from modules import voice_alert
                voice_alert.not_found(widget=self.win)
            except Exception:
                pass
            return
        blank_idx = next((i for i, l in enumerate(self.line_grid.lines)
                          if l.get("_blank") and not l.get("product_id")), None)
        if blank_idx is None:
            self.line_grid.add_blank_row()
            blank_idx = len(self.line_grid.lines) - 1
        self.line_grid._apply_product(blank_idx, matches[0])
        if qty and qty > 0:
            try:
                self.line_grid.lines[blank_idx]["quantity"] = float(qty)
                self.line_grid._recalc(self.line_grid.lines[blank_idx])
            except Exception:
                pass
        self.line_grid._refresh()
        if qty and qty > 0:
            self.save_status.set(
                f"🎤 Heard '{text}' → {qty:g} × "
                f"{matches[0]['product_name_en']} added.")
        else:
            self.line_grid.after(
                20, lambda: self.line_grid._edit_number(blank_idx, "qty"))
            self.save_status.set(
                f"🎤 Heard '{text}' → {matches[0]['product_name_en']}. "
                f"Type quantity, press Enter.")

    def _preview_current(self):
        """Save the invoice (draft is fine) then open it as PDF."""
        if not self.invoice_id:
            ok = self._save(confirm=False, keep_open=True, silent=True)
            if ok is False:
                return
        if self.invoice_id:
            from ui import print_menu
            print_menu.run(self.win, self._kind(), self.invoice_id, "pdf",
                           status=self.save_status)

    def _kind(self):
        return SalesInvoiceView._print_kind(self.invoice_id) if self.invoice_id else "sales"

    def _save_and_print(self, fmt="default", already_saved=False, ask=None):
        """Save the invoice (confirm) then print it.
        fmt: 'default' (default layout → printer), 'dotmatrix', 'pdf'.
        Older names still work: 'a4'/'thermal' → default,
        'dotmatrix132' → dot-matrix 132 columns.
        already_saved=True skips the save step (used by auto-print)."""
        option = {"a4": "default", "thermal": "default", "designed": "default",
                  "dotmatrix132": "dotmatrix"}.get(fmt, fmt)
        if not already_saved:
            ok = self._save(confirm=True, keep_open=True, silent=True)
            if ok is False:
                return
        if not self.invoice_id:
            messagebox.showwarning("Print", "Save the invoice first.")
            return
        from ui import print_menu
        if fmt == "dotmatrix132":
            from modules import doc_print as DP
            from modules import permissions as _pm
            if not _pm.allowed("sales", "print"):
                return False
            ok, msg = DP.print_document(self._kind(), self.invoice_id, "dotmatrix",
                                        width=132, ask=ask, parent=self.win)
            self.save_status.set(msg.splitlines()[0])
            return ok
        return print_menu.run(self.win, self._kind(), self.invoice_id, option,
                              ask=ask, status=self.save_status)

    def _print_previous(self):
        """Print the last saved invoice again (reprint)."""
        from modules import doc_print as DP
        from ui import print_menu
        prev = DP.last_id(self._kind())
        if not prev:
            messagebox.showinfo("Print", "No saved invoice yet.", parent=self.win)
            return
        print_menu.run(self.win, self._kind(), prev, "default", status=self.save_status)

    def _hold_sale(self):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "add"):
            return False
        """
        Hold the current sale as a Pending (draft) invoice, then open a fresh
        blank sale so the cashier can serve the next customer. Held sales show
        as 'Draft/Pending' in the invoice list and can be reopened anytime.
        """
        if not self._lines or all(not l.get("product_id") for l in self._lines):
            messagebox.showinfo("Hold Sale", "Add at least one product first.")
            return
        if self.invoice_id:          # v6.9.5: a confirmed bill is never put back on hold
            from modules import doc_edit
            if doc_edit.info("sales", self.invoice_id)[1] == "confirmed":
                messagebox.showinfo("Hold Sale", "This bill is already confirmed — "
                                    "Save keeps your changes.", parent=self.win)
                return
        # Save as draft (pending) without closing
        ok = self._save(confirm=False, keep_open=True, silent=True)
        if ok is False:
            return
        messagebox.showinfo("⏸ Sale Held",
            "This sale is saved as Pending.\n"
            "It will appear in the invoice list (Draft) — reopen it anytime.\n\n"
            "A new blank sale is ready for the next customer.")
        # Reset the form for a new customer
        try:
            self.invoice_id = None
            self.line_grid.lines = []
            self.line_grid.add_blank_row()
            self._lines = []
            self._set_defaults()
            self._update_totals()
            self.line_grid.focus_first_product()
        except Exception:
            # If reset fails, just close so the cashier can reopen New Invoice
            self.win.destroy()

    def _resolve_barcode(self, code):
        """
        Look up a scanned barcode. Returns (product_dict, unit_id) or None.
        Checks the multi-barcode table first, then product_units, then products.
        """
        try:      # the ONE shared resolver (unit → extra → product barcode → code)
            from modules.barcode_resolver import resolve
            hit = resolve(code, scale=False, products=self._products)
            if hit:
                prod = next((p for p in self._products
                             if p["product_id"] == hit["product_id"]), None)
                return (prod, hit["unit_id"]) if prod else None
        except Exception:
            pass
        # 1) multiple-barcodes table (maps barcode -> unit -> product)
        try:
            row = db.fetchone(
                "SELECT product_id, unit_id FROM product_unit_barcodes "
                "WHERE barcode=? AND is_active=1", (code,))
            if row:
                prod = next((p for p in self._products
                             if p["product_id"] == row["product_id"]), None)
                if prod:
                    return prod, row["unit_id"]
        except Exception:
            pass
        # 2) product_units.barcode
        try:
            row = db.fetchone(
                "SELECT product_id, unit_id FROM product_units WHERE barcode=?",
                (code,))
            if row:
                prod = next((p for p in self._products
                             if p["product_id"] == row["product_id"]), None)
                if prod:
                    return prod, row["unit_id"]
        except Exception:
            pass
        # 3) products.barcode (base)
        try:
            row = db.fetchone(
                "SELECT product_id FROM products WHERE barcode=?", (code,))
            if row:
                prod = next((p for p in self._products
                             if p["product_id"] == row["product_id"]), None)
                if prod:
                    return prod, None
        except Exception:
            pass
        return None

    def _apply_unit_by_id(self, idx, unit_id):
        """Set the line's unit dropdown to the unit matching unit_id."""
        try:
            line = self._lines[idx]
            units = self._product_units.get(line.get("product_id"), [])
            u = next((x for x in units if x["unit_id"] == unit_id), None)
            if u and line.get("_unit_var"):
                line["_unit_var"].set(u["unit_name_en"])
                self._on_unit_select(idx)
        except Exception:
            pass

    def _fast_pick_product(self, idx):
        """
        Fast entry: take whatever is typed/spoken in the product box,
        auto-select the BEST matching product, then jump to Quantity.
        """
        line = self._lines[idx]
        combo = line.get("_prod_combo")
        if combo is None:
            return "break"
        typed = combo.get().strip()
        if not typed:
            return "break"

        # If the text is a barcode (all digits), resolve it to product + unit
        if typed.isdigit() and len(typed) >= 6:
            resolved = self._resolve_barcode(typed)
            if resolved:
                prod, unit_id = resolved
                combo.set(f"{prod['product_code']} — {prod['product_name_en']}")
                self._on_product_select(idx)
                # If the barcode maps to a specific unit, select it
                if unit_id:
                    self._apply_unit_by_id(idx, unit_id)
                self._focus_qty(idx)
                return "break"
            # not found as barcode → fall through to name search

        # If the text is already "CODE — Name", let normal select handle it
        match = None
        try:
            from modules.smart_search import filter_products
            results = filter_products(typed, self._products)
            if results:
                match = results[0]
        except Exception:
            match = None
        if not match:
            # fallback: exact code/name contains
            for p in self._products:
                if typed.lower() in (str(p.get("product_code","")) + " " +
                                     str(p.get("product_name_en",""))).lower():
                    match = p; break
        if not match:
            self.save_status.set(f"⚠️ No product matches '{typed}'.")
            return "break"
        # Put the canonical label in the combo and run the normal select path
        combo.set(f"{match['product_code']} — {match['product_name_en']}")
        self._on_product_select(idx)
        self._focus_qty(idx)
        return "break"

    def _focus_qty(self, idx):
        """Move keyboard focus to the quantity field of a line, select all."""
        try:
            line = self._lines[idx]
            e = line.get("_qty_entry")
            if e is not None:
                e.focus_set()
                e.select_range(0, "end")
        except Exception:
            pass
        return "break"

    def _fast_next(self, idx):
        """
        Confirm the current line (recalc), then either focus the next existing
        line's product box or create a fresh line — continuous selling loop.
        """
        self._recalc_line(idx)
        # If this is the last line, add a new one
        if idx >= len(self._lines) - 1:
            self._add_line()
        nxt = idx + 1
        if nxt < len(self._lines):
            nline = self._lines[nxt]
            combo = nline.get("_prod_combo")
            if combo is not None:
                combo.focus_set()
        return "break"

    # ── Rich inline product search (Polosys-style) ───────────
    # Shows a floating table under the Product cell:
    #   Product Name · Stock Details · SPrice · PPrice
    def _rich_search(self, event, idx):
        """
        Live partial search: as the cashier types (even one letter like 'p'),
        filter the product dropdown and open it so matches show instantly.
        """
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape",
                            "Left", "Right", "Shift_L", "Shift_R",
                            "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        line = self._lines[idx]
        combo = line.get("_prod_combo")
        if combo is None:
            return
        q = combo.get().strip()
        if not q:
            combo["values"] = [self._prod_label(p) for p in self._products]
            return
        try:
            from modules.smart_search import filter_products
            matches = filter_products(q, self._products)
        except Exception:
            ql = q.lower()
            matches = [p for p in self._products
                       if ql in (str(p.get("product_code", "")) + " " +
                                 str(p.get("product_name_en", "")) + " " +
                                 str(p.get("alias_name", ""))).lower()]
        labels = [self._prod_label(p) for p in matches[:50]]
        combo["values"] = labels
        if labels:
            try:
                combo.event_generate("<Down>")   # open the dropdown
                combo.set(q)                       # keep what was typed
                combo.icursor("end")
            except Exception:
                pass

    def _prod_label(self, p):
        """One-line label: code — name | Stock | SP price."""
        stock = float(p.get("stock_quantity", 0) or 0)
        sprice = float(p.get("unit_price", 0) or 0)
        return ("%s — %s  |  Stock %g  |  SP %.2f"
                % (p.get("product_code", ""), p.get("product_name_en", ""),
                   stock, sprice))

    # legacy no-ops (old floating panel removed)
    def _show_rich_dropdown(self, idx, combo, matches):
        return

    def _rich_focus_list(self, idx):
        return

    def _rich_pick(self):
        return

    def _rich_close(self):
        return

    def _rich_close_later(self):
        return

    def _smart_filter_combo(self, event, combo):
        """Filter the product dropdown live using smart token-prefix search."""
        # Ignore navigation keys
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape", "Left", "Right"):
            return
        try:
            from modules.smart_search import filter_products
        except Exception:
            return
        q = combo.get()
        if not q:
            combo["values"] = [f"{p['product_code']} — {p['product_name_en']}"
                               for p in self._products]
            return
        matches = filter_products(q, self._products)
        combo["values"] = [f"{p['product_code']} — {p['product_name_en']}"
                           for p in matches]
        # keep the dropdown open showing matches
        try:
            combo.event_generate("<Down>")
        except Exception:
            pass

    def _on_product_select(self, idx):
        line = self._lines[idx]
        sel  = line["_prod_var"].get()
        code = sel.split(" — ")[0] if " — " in sel else ""
        prod = next((p for p in self._products
                     if p["product_code"] == code), None)
        if not prod:
            return
        line["product_id"]        = prod["product_id"]
        line["product_name_en"]   = prod["product_name_en"]
        line["product_name_ar"]   = prod.get("product_name_ar","")
        line["product_code"]      = prod["product_code"]
        line["unit_of_measure_en"]= prod.get("unit_of_measure_en","Unit")
        line["vat_category_id"]   = prod.get("vat_category_id")
        line["vat_category_code"] = prod.get("vat_code","S")
        line["vat_rate"]          = float(prod.get("vat_rate",15))
        line["_price_var"].set(f"{float(prod.get('unit_price',0)):.2f}")
        # show a clean label in the box (drop the stock/price suffix)
        line["_prod_var"].set(f"{prod['product_code']} — {prod['product_name_en']}")

        # Load this product's sales units into the unit dropdown
        units = self._product_units.get(prod["product_id"], [])
        line["_units"] = units
        combo = line.get("_unit_combo")
        if combo is not None:
            if units:
                names = [u["unit_name_en"] for u in units]
                combo["values"] = names
                # default unit first
                default = next((u for u in units if u.get("is_default")), units[0])
                line["_unit_var"].set(default["unit_name_en"])
                line["unit_of_measure_en"] = default["unit_name_en"]
                # use the unit's selling price if set
                if float(default.get("selling_price", 0)) > 0:
                    line["_price_var"].set(f"{float(default['selling_price']):.2f}")
            else:
                combo["values"] = [prod.get("unit_of_measure_en", "Unit")]
                line["_unit_var"].set(prod.get("unit_of_measure_en", "Unit"))
        self._recalc_line(idx)

    def _on_unit_select(self, idx):
        """When the cashier picks a different selling unit, update the price."""
        line = self._lines[idx]
        units = line.get("_units", [])
        chosen = line["_unit_var"].get()
        u = next((x for x in units if x["unit_name_en"] == chosen), None)
        if u:
            line["unit_of_measure_en"] = u["unit_name_en"]
            if float(u.get("selling_price", 0)) > 0:
                line["_price_var"].set(f"{float(u['selling_price']):.2f}")
        self._recalc_line(idx)

    def _cycle_unit(self, idx):
        """Space key: jump to the next unit in the list (fast cashier entry)."""
        line = self._lines[idx]
        units = line.get("_units", [])
        if len(units) < 2:
            return "break"
        names = [u["unit_name_en"] for u in units]
        cur = line["_unit_var"].get()
        nxt = names[(names.index(cur) + 1) % len(names)] if cur in names else names[0]
        line["_unit_var"].set(nxt)
        self._on_unit_select(idx)
        return "break"

    def _focus_unit(self, idx):
        """Tab from product → focus the unit selector."""
        line = self._lines[idx]
        combo = line.get("_unit_combo")
        if combo is not None:
            combo.focus_set()
        return "break"

    # ── v6.0: price lists ────────────────────────────────────
    def _price_key(self):
        try:
            from modules import price_lists as PL
            return PL.key_for_label(self.price_category_var.get())
        except Exception:
            return None

    def _on_price_category(self, reprice=True):
        grid = getattr(self, "line_grid", None)
        if grid is None or not hasattr(grid, "set_price_key"):
            return
        n = grid.set_price_key(self._price_key(), reprice=reprice and not self.view_only)
        if n and hasattr(self, "save_status"):
            try:
                self.save_status.set("Prices: %s (%d line(s) re-priced)"
                                     % (self.price_category_var.get(), n))
            except Exception:
                pass

    def _on_customer_select(self, event=None):
        sel = self.cust_var.get()
        code = sel.split(" — ")[0] if " — " in sel else ""
        cust = next((c for c in self._customers
                     if c["customer_code"] == code), None)
        if not cust:
            return
        self._selected_customer = cust
        if not getattr(self, "_loading_doc", False):   # the customer's price list
            try:
                from modules import price_lists as PL
                key = PL.for_customer(cust.get("customer_id"))
                lbl = PL.label_for_key(key)
                if lbl != self.price_category_var.get():
                    self.price_category_var.set(lbl)
                    self._on_price_category()
            except Exception:
                pass
        if not getattr(self, "_loading_doc", False) and hasattr(self, "pos_combo"):
            self._set_pos_from_customer(cust)
        ctype = cust.get("customer_type","B2C")
        vat   = cust.get("vat_registration_no","") or ""
        city  = cust.get("city_en","") or ""
        info  = f"Type: {ctype}"
        if vat:
            info += f"  |  VAT: {vat}"
        if city:
            info += f"  |  City: {city}"
        self.cust_info_var.set(info)
        if not getattr(self, "_loading_doc", False) and hasattr(self, "cust_vat_var"):
            self._fill_party_boxes(cust)
        self._show_party_facts(cust)
        if hasattr(self, "points_info_var"):
            self._update_totals()

    def _set_pos_from_customer(self, cust):
        """India: the place of supply follows the customer's state."""
        try:
            from modules import country as _ctry
            st = _ctry.place_of_supply("sales", {"customer_id": cust.get("customer_id")})
            self.pos_var.set(_ctry.state_label(st))
            self._update_totals()
        except Exception:
            pass

    def _pos_code(self):
        try:
            from modules import country as _ctry
            return _ctry.state_code_of(self.pos_var.get()) if self.pos_var.get() else ""
        except Exception:
            return ""

    def _recalc_line(self, idx):
        line = self._lines[idx]
        try:
            qty   = float(line["_qty_var"].get()   or 0)
            price = float(line["_price_var"].get() or 0)
            disc  = float(line["_disc_var"].get()  or 0)
        except ValueError:
            return

        disc_amt  = (qty * price) * disc / 100
        line_amt  = qty * price - disc_amt
        vat_rate  = float(line.get("vat_rate", 15))
        vat_amt   = line_amt * vat_rate / 100
        line_total = line_amt + vat_amt

        line["quantity"]         = qty
        line["unit_price"]       = price
        line["discount_percent"] = disc
        line["discount_amount"]  = disc_amt
        line["line_amount"]      = line_amt
        line["vat_amount"]       = vat_amt
        line["line_total"]       = line_total

        # Update display vars
        if "_amt_var" in line:
            # Find the label widgets in the row and update
            self._update_line_display(line)
        self._update_totals()

    def _update_line_display(self, line):
        row = line.get("_row")
        if not row:
            return
        # Walk labels in the row to update computed fields
        labels = [w for w in row.winfo_children()
                  if isinstance(w, tk.Label) and
                  w.cget("font") == "Segoe UI 9 bold"]
        values = [
            f"{line['line_amount']:.2f}",
            f"{line['vat_rate']:.0f}%",
            f"{line['line_total']:.2f}",
        ]
        for lbl, val in zip(labels, values):
            lbl.config(text=val)

    def _remove_line(self, idx):
        line = self._lines[idx]
        row  = line.get("_row")
        if row:
            row.destroy()
        self._lines.pop(idx)
        # Renumber remaining lines
        for i, ln in enumerate(self._lines):
            r = ln.get("_row")
            if r:
                lbl = r.winfo_children()[0]
                if isinstance(lbl, tk.Label):
                    lbl.config(text=str(i+1))
        self._update_totals()

    # ── Right Panel (Totals + QR) ─────────────────────────────
    def _build_totals_bar(self, C):
        """v6.9: TWO slim rows (was seven) — what you type on the first,
        the figures on the second, GRAND TOTAL on the right."""
        bar = self.bottom_bar
        inner = tk.Frame(bar, bg=C["card_bg"])
        inner.pack(fill="x", padx=10, pady=3)
        ro = "disabled" if self.view_only else "normal"
        F8 = ("Segoe UI", 8)

        # hidden frames kept for compatibility with _update_totals / QR
        self.vat_breakdown_frame = tk.Frame(inner, bg=C["card_bg"])
        self.qr_frame = tk.Frame(inner, bg=C["card_bg"])
        self.qr_label = tk.Label(self.qr_frame, text="")

        # vars _update_totals / _update_balance expect
        self.subtotal_var = tk.StringVar(value="0.00")
        self.taxable_var = tk.StringVar(value="0.00")
        self.totalqty_var = tk.StringVar(value="0")
        self.discount_var = tk.StringVar(value="0.00")
        self.total_var = tk.StringVar(value="0.00")
        self.balance_var = tk.StringVar(value="0.00")
        self.vat_var = tk.StringVar(value="0.00")
        self.bank_var = tk.StringVar(value="0.00")        # kept for posting (hidden)
        self.bill_discount_var = tk.StringVar(value="0.00")

        # ── GRAND TOTAL (right, both rows high) ──────────────
        gt = tk.Frame(inner, bg=C["primary"], padx=12, pady=2)
        gt.pack(side="right", fill="y", padx=(10, 0))
        tk.Label(gt, text="GRAND TOTAL", font=("Segoe UI", 8, "bold"), bg=C["primary"],
                 fg="white").pack(anchor="e")
        tk.Label(gt, textvariable=self.total_var, font=("Segoe UI", 16, "bold"),
                 bg=C["primary"], fg="white").pack(anchor="e")

        left = tk.Frame(inner, bg=C["card_bg"])
        left.pack(side="left", fill="both", expand=True)
        r1 = tk.Frame(left, bg=C["card_bg"])
        r1.pack(fill="x")
        r2 = tk.Frame(left, bg=C["card_bg"])
        r2.pack(fill="x", pady=(3, 0))

        def lbl(parent, text, padl=10, fg=None, bold=False):
            tk.Label(parent, text=text, font=("Segoe UI", 8, "bold") if bold else F8,
                     bg=C["card_bg"], fg=fg or C["text_secondary"]).pack(side="left", padx=(padl, 3))

        def amt(label, var_name, width=8, padl=10, var=None):
            lbl(r1, label, padl=padl)
            if var is None:
                var = tk.StringVar(value="0.00")
                setattr(self, var_name, var)
            e = tk.Entry(r1, textvariable=var, font=("Segoe UI", 10), width=width,
                         relief="solid", bd=1, justify="right", state=ro)
            e.pack(side="left")
            setattr(self, var_name + "_entry", e)
            return e

        # ── row 1: remarks · price list · tenders · round / coupon / discount
        lbl(r1, "Remarks", padl=0)
        self.hdr_vars["notes_en"] = tk.StringVar()
        tk.Entry(r1, textvariable=self.hdr_vars["notes_en"], font=("Segoe UI", 9),
                 relief="solid", bd=1, width=16).pack(side="left", fill="x", expand=True)
        # v6.0: Price Category = price list; it follows the customer and
        # re-prices the lines when changed
        self.price_category_var = tk.StringVar(value="Standard")
        lbl(r1, "Price")
        try:
            from modules import price_lists as _PL
            _pc_vals = [l for l, _k in _PL.choices()]
        except Exception:
            _pc_vals = ["Standard", "Wholesale"]
        self.price_cat_combo = ttk.Combobox(r1, textvariable=self.price_category_var,
                                            values=_pc_vals, width=11,
                                            state="disabled" if self.view_only else "readonly",
                                            font=("Segoe UI", 9))
        self.price_cat_combo.pack(side="left")
        self.price_cat_combo.bind("<<ComboboxSelected>>", lambda e: self._on_price_category())
        amt("Card", "card_var")
        amt("SR", "sr_amount_var", width=7)
        self.full_pay_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r1, text="Cash Rcvd", variable=self.full_pay_var,
                       font=("Segoe UI", 8, "bold"), bg=C["card_bg"], fg=C["primary"],
                       activebackground=C["card_bg"], command=self._toggle_full_pay).pack(
                           side="left", padx=(8, 2))
        self.cash_var = tk.StringVar(value="0.00")
        self.cash_var_entry = tk.Entry(r1, textvariable=self.cash_var, font=("Segoe UI", 10),
                                       width=9, relief="solid", bd=1, justify="right", state=ro)
        self.cash_var_entry.pack(side="left")
        amt("Round", "round_var", width=6)
        # v6.9.2: ⭐ loyalty points spent on this bill (was an unused Coupon box)
        self.points_entry = amt("⭐ Pts", "points_var", width=6)
        self.points_var.set("0")
        self.coupon_var = self.points_var
        self.points_info_var = tk.StringVar(value="")
        tk.Label(r1, textvariable=self.points_info_var, font=("Segoe UI", 7, "bold"),
                 bg=C["card_bg"], fg=C["warning"] if "warning" in C else "#B45309").pack(
                     side="left", padx=(2, 0))
        try:
            from modules import loyalty as _loy
            if not _loy.enabled() or self.view_only:
                self.points_entry.configure(state="disabled")
        except Exception:
            self.points_entry.configure(state="disabled")
        self.bill_discount_entry = amt(
            "Bill Disc", "bill_discount", width=7, var=self.bill_discount_var)
        if not (not self.view_only and cfg.flag("allow_discount_edit", True)):
            self.bill_discount_entry.configure(state="disabled")   # Settings ▸ Sales ▸ Allow Discount Edit
        self.cash_var.trace("w", lambda *a: self._update_balance())
        self.card_var.trace("w", lambda *a: self._update_balance())
        self.round_var.trace("w", lambda *a: self._update_totals())
        self.bill_discount_var.trace("w", lambda *a: self._update_totals())
        self.points_var.trace("w", lambda *a: self._update_totals())

        # ── row 2: last bill · options · Net / VAT / Balance ───
        self.lbill_var = tk.StringVar(value="L.Bill: —")
        tk.Label(r2, textvariable=self.lbill_var, font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(side="left")
        self.win.after_idle(self._show_party_facts)          # v7.8: balance + last bills
        self.print_after_var = tk.BooleanVar(value=True)
        self.vatno_var = tk.BooleanVar(value=False)
        self.auto_calc_var = tk.BooleanVar(value=True)
        for text, var in (("Print After Save", self.print_after_var), ("VAT #", self.vatno_var),
                          ("Auto Calculation", self.auto_calc_var)):
            tk.Checkbutton(r2, text=text, variable=var, font=F8, bg=C["card_bg"],
                           fg=C["text_secondary"], activebackground=C["card_bg"]).pack(
                               side="left", padx=(8, 0))
        tk.Button(r2, text="Add. Amount / JV", font=("Segoe UI", 8, "underline"),
                  bg=C["card_bg"], fg=C["info"], relief="flat", cursor="hand2", bd=0,
                  command=lambda: self._nav("vouchers")).pack(side="left", padx=(10, 0))

        def figure(label, var, color):
            tk.Label(r2, textvariable=var, font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                     fg=color).pack(side="right", padx=(2, 0))
            tk.Label(r2, text=label, font=F8, bg=C["card_bg"],
                     fg=color if color == C["danger"] else C["text_secondary"]).pack(
                         side="right", padx=(14, 0))
        figure("Balance", self.balance_var, C["danger"])
        figure("Tot VAT", self.vat_var, C["info"])
        figure("Net Amount", self.total_var, C["text_primary"])
        # v7.0 India: how the GST splits (CGST + SGST, or IGST)
        self.gst_split_var = tk.StringVar(value="")
        tk.Label(r2, textvariable=self.gst_split_var, font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                 fg=C["info"]).pack(side="right", padx=(10, 0))

    def _clear_form(self):
        if self.view_only:
            return
        try:
            self.line_grid.lines = []
            self.line_grid.add_blank_row()
        except Exception:
            pass
        self._lines = []
        for v in ("cash_var", "card_var", "bank_var", "bill_discount_var", "round_var"):
            if hasattr(self, v):
                getattr(self, v).set("0.00")
        if hasattr(self, "full_pay_var"):      # v6.9.5: ticked by a loaded cash bill
            self.full_pay_var.set(False)
        self._loaded_points = self._saved_points_extra = 0
        if hasattr(self, "points_var"):
            self.points_var.set("0")
        if hasattr(self, "cust_vat_var"):          # v7.8: the next bill starts with the boxes of its customer
            self._fill_party_boxes(getattr(self, "_selected_customer", None) or {})
        self._show_party_facts()
        # a cleared form is a NEW document: back to today's system date
        today = date.today().isoformat()
        self.hdr_vars["invoice_date"].set(today)
        if "due_date" in self.hdr_vars:
            self.hdr_vars["due_date"].set(self._default_due(today))
        self._update_totals()
        try:
            self.line_grid.focus_first_product()
        except Exception:
            pass

    def _remove_focused_line(self):
        try:
            sel = self.line_grid.tree.focus()
            if sel != "":
                self.line_grid._delete_row(int(sel))
        except Exception:
            pass

    def _nav(self, module_key):
        """Open a main-window screen from the invoice window's toolbar."""
        try:
            from ui import main_window as mw
            mw.navigate(module_key)
        except Exception:
            pass

    def _edit_focused_line(self):
        """Edit (Qty of) the selected grid row."""
        try:
            sel = self.line_grid.tree.focus()
            if sel != "":
                self.line_grid._edit_number(int(sel), "qty")
            else:
                self._focus_product()
        except Exception:
            pass

    def _goto_last_row(self):
        try:
            self.line_grid.focus_first_product()
        except Exception:
            pass

    def _toolbar_todo(self, name):
        # kept for any stray callers; routes to a sensible default
        self._nav("settings")
    def _toggle_full_pay(self):
        """'Cash Rcvd' tick — was referenced by the totals bar but never
        implemented, which crashed the whole Polosys-style window on
        open. Ticked: cash received auto-fills with the grand total
        (full payment). Unticked: clears it back for manual entry."""
        try:
            if self.full_pay_var.get():
                total = str(self.total_var.get()).replace(",", "") or "0"
                self.cash_var.set(f"{float(total):,.2f}")
            else:
                self.cash_var.set("0.00")
        except Exception:
            pass
        self._update_balance()

    def _update_balance(self):
        """Balance = Grand Total − (Cash + Card + Bank). Negative = change to give."""
        if not hasattr(self, "balance_var"):
            return
        def num(v):
            try:
                return float(str(v.get()).replace(",", "") or 0)
            except Exception:
                return 0.0
        total = num(self.total_var)
        paid = num(self.cash_var) + num(self.card_var) + num(self.bank_var)
        bal = total - paid
        if bal < -0.005:
            self.balance_var.set(f"Change {abs(bal):,.2f}")
        else:
            self.balance_var.set(f"{bal:,.2f}")

    def _num_field(self, var_name):
        """Read a bottom-bar money field as a float (blank/None -> 0)."""
        v = getattr(self, var_name, None)
        if v is None:
            return 0.0
        try:
            return float(str(v.get()).replace(",", "").replace("−", "-") or 0)
        except Exception:
            return 0.0

    def _incl(self):
        """Prices typed with VAT (inclusive) or without."""
        return (getattr(getattr(self, "line_grid", None), "tax_mode", None)
                or cfg.get("sales_price_tax_mode", "inclusive")) == "inclusive"

    def _points_used(self, bill_total=None):
        """(points, SAR) newly spent on this bill — v6.9.2 loyalty. Never
        more than the customer has or than the bill is worth; nothing below
        the minimum. (Points a saved bill already spent are inside its
        lines, like its bill discount, and stay spent.)"""
        try:
            from modules import loyalty
            if not loyalty.enabled():
                return 0, 0.0
            want = int(float(str(self.points_var.get() or 0).replace(",", "") or 0))
            cust = getattr(self, "_selected_customer", None) or {}
            if want <= 0 or loyalty.is_walk_in(cust):
                return 0, 0.0
            if bill_total is None:
                bill_total = sum(ln.get("line_total", 0) for ln in self._lines) \
                    - self._num_field("bill_discount_var")
            # a bill saved from this window and kept open (Save & Print) has
            # already taken these points off the balance: they still count
            ok = min(want, loyalty.can_spend(cust.get("customer_id"), bill_total,
                                             already=getattr(self, "_saved_points_extra", 0)))
            return (ok, loyalty.value_of(ok)) if ok > 0 else (0, 0.0)
        except Exception:
            return 0, 0.0

    def _show_points(self):
        """⭐ balance next to the Points box."""
        try:
            from modules import loyalty
            cust = getattr(self, "_selected_customer", None) or {}
            if not loyalty.enabled() or loyalty.is_walk_in(cust):
                self.points_info_var.set("")
                return
            have = loyalty.balance(cust.get("customer_id")) + int(
                getattr(self, "_saved_points_extra", 0) or 0)
            used, val = self._points_used()
            want = int(float(str(self.points_var.get() or 0).replace(",", "") or 0))
            txt = "%d pts" % have
            if want and not used:
                txt += " · min %d" % loyalty.min_redeem() if have >= want else " · not enough"
            elif used:
                txt += " · −%.2f" % val
            self.points_info_var.set(txt)
        except Exception:
            pass

    def _lines_to_save(self, bill_adj=None):
        """The lines as Save stores them: bill discount / points / round box
        spread over them before VAT (v6.9)."""
        if bill_adj is None:
            bill_adj = (self._num_field("bill_discount_var") + self._points_used()[1]
                        - self._num_field("round_var"))
        if abs(bill_adj) >= 0.005 and self._lines:
            from modules.doc_math import spread_bill_adjustment
            return spread_bill_adjustment(self._lines, bill_adj, self._incl())
        return self._lines

    def _update_totals(self):
        subtotal = sum(ln.get("line_amount",0) for ln in self._lines)
        discount = sum(ln.get("discount_amount",0) for ln in self._lines)
        taxable  = subtotal
        vat      = sum(ln.get("vat_amount",0) for ln in self._lines)
        total    = sum(ln.get("line_total",0)  for ln in self._lines)
        total_qty = sum(ln.get("quantity",0) for ln in self._lines)

        # bill-level adjustments (wired): bill discount + ⭐ points + round off
        bill_disc = self._num_field("bill_discount_var")
        bill_disc += self._points_used(total - bill_disc)[1]
        round_adj = self._num_field("round_var")
        # Settings ▸ Tax: automatic round-off fills the Round field
        # (guarded: round_var has a trace that re-enters this method)
        if cfg.flag("round_off_enabled") and not getattr(self, "_auto_rounding", False):
            try:
                _, adj = cfg.round_off(total - bill_disc)
                if abs(adj - round_adj) > 0.004:
                    self._auto_rounding = True
                    try:
                        self.round_var.set(f"{adj:.2f}")
                    finally:
                        self._auto_rounding = False
                    round_adj = adj
            except Exception:
                pass
        grand = total - bill_disc + round_adj
        if grand < 0:
            grand = 0
        # v6.9.2: taxable / VAT / total exactly as Save will store them —
        # bill discount spread over the lines, VAT the ZATCA way (once per
        # rate on the bill total), so screen = print = books = e-invoice
        if self._lines:
            try:
                from modules.doc_math import doc_totals
                T = doc_totals(self._lines_to_save(bill_disc - round_adj), self._incl())
                taxable, vat, grand = T["taxable"], T["vat"], max(T["total"], 0)
            except Exception:
                pass
        self._shown = (grand, vat)
        if hasattr(self, "points_info_var"):
            self._show_points()

        if hasattr(self, "totalqty_var"):
            self.totalqty_var.set(f"{total_qty:g}")
        self.subtotal_var.set(f"{subtotal:,.2f}")
        self.discount_var.set(f"−{discount:,.2f}")
        self.taxable_var.set(f"{taxable:,.2f}")
        self.vat_var.set(f"{vat:,.2f}")
        self.total_var.set(f"{grand:,.2f}")
        if getattr(self, "gst_split_var", None) is not None:
            try:
                from modules import country as _ctry
                sp = _ctry.gst_split(vat, self._pos_code() or None)
                if sp:
                    self.gst_split_var.set(
                        ("IGST %s" % _ctry.num(sp["igst"])) if sp["igst"] else
                        ("CGST %s · %s %s" % (_ctry.num(sp["cgst"]), _ctry.tax_head_label("sgst"),
                                              _ctry.num(sp["sgst"]))))
            except Exception:
                pass
        # keep the Full Pay tender equal to the live grand total
        if getattr(self, "full_pay_var", None) and self.full_pay_var.get():
            self.cash_var.set(f"{grand:,.2f}")
        self._update_balance()

        # VAT breakdown by category (only if this layout has the panel)
        if not hasattr(self, "vat_breakdown_frame"):
            return
        C = cfg.theme()
        for w in self.vat_breakdown_frame.winfo_children():
            w.destroy()
        groups = {}
        for ln in self._lines:
            code = ln.get("vat_category_code","S")
            rate = ln.get("vat_rate",15)
            if code not in groups:
                groups[code] = {"amt":0, "vat":0, "rate":rate}
            groups[code]["amt"] += ln.get("line_amount",0)
            groups[code]["vat"] += ln.get("vat_amount",0)

        for code, g in groups.items():
            row = tk.Frame(self.vat_breakdown_frame, bg=C["card_bg"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{code} ({g['rate']:.0f}%): {g['amt']:,.2f}",
                     font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left")
            tk.Label(row, text=f"VAT: {g['vat']:,.2f}",
                     font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                     fg=C["info"]).pack(side="right")

    def _generate_qr_preview(self):
        """Generate and display QR code preview in right panel."""
        try:
            seller  = self._company.get("company_name_ar") or \
                      self._company.get("company_name_en","My Company")
            from modules.zatca.qr_generator import clean_vat_number, vat_problem
            vat_no  = clean_vat_number(self._company.get("vat_registration_no"))
            problem = vat_problem(vat_no)
            if problem:
                # the printed invoice will have NO QR — don't show a fake one here
                self.qr_label.config(
                    image="", text="No QR code\n\nSet the company VAT number\n"
                                   "(Settings ▸ Company)", fg="#DC2626",
                    font=("Segoe UI", 8, "bold"))
                self.qr_label.image = None
                self._qr_data = ""
                return
            dt_str  = format_zatca_datetime(datetime.utcnow())
            total, vat_amt = getattr(self, "_shown", None) or (
                sum(ln.get("line_total", 0) for ln in self._lines),
                sum(ln.get("vat_amount", 0) for ln in self._lines))

            qr_data = generate_zatca_qr(seller, vat_no, dt_str, total, vat_amt)

            qr_img = generate_qr_photoimage(qr_data, size=160)
            if qr_img:
                self.qr_label.config(image=qr_img, text="")
                self.qr_label.image = qr_img   # keep reference
            else:
                self.qr_label.config(
                    text=f"QR Data (Base64):\n{qr_data[:40]}...",
                    font=("Segoe UI", 7))
            self._qr_data = qr_data
        except Exception as e:
            self.qr_label.config(text=f"QR Error:\n{str(e)[:60]}")

    # ── Footer ────────────────────────────────────────────────
    def _build_footer(self, C):
        """v6.9: ONE slim line — status on the left, one-line buttons on
        the right (the separate status strip and two-line buttons are gone)."""
        footer = tk.Frame(self.win, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        inner = tk.Frame(footer, bg=C["card_bg"])
        inner.pack(fill="x", padx=10, pady=3)

        self.save_status = tk.StringVar()
        tk.Label(inner, textvariable=self.save_status,
                 font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["danger"]).pack(side="left")
        self._footer_info = tk.Frame(inner, bg=C["card_bg"])     # filled by _build_statusbar
        self._footer_info.pack(side="left")

        from ui.ui_kit import key_style, ghost_key_style

        def slim(style):
            style.update(pady=3, padx=12, justify="center", anchor="center")
            return style

        tk.Button(inner, command=lambda: close_guard.request_close(self.win),
                  **slim(ghost_key_style("", "Esc  " + t("common.cancel")))).pack(side="right", padx=(6, 0))

        if not self.view_only:
            tk.Button(inner, command=lambda: self._save(confirm=True),
                      **slim(key_style(C.get("tile_green", C["success"]), "",
                                       "✔  Save & Confirm"))).pack(side="right", padx=(6, 0))

            # 🖨 Print ▾  — Default / Dot-matrix / PDF (saves first)
            print_btn = tk.Menubutton(inner, **slim(key_style(C.get("tile_purple", C["info"]),
                                                              "", "F10  Print ▾")))
            pmenu = tk.Menu(print_btn, tearoff=0, font=("Segoe UI", 10))
            pmenu.add_command(label="🖨  Print  (default layout)      F10",
                              command=lambda: self._save_and_print("default"))
            pmenu.add_command(label="🖨  Dot-matrix                        F11",
                              command=lambda: self._save_and_print("dotmatrix"))
            pmenu.add_command(label="📄  PDF  (open / save)             F12",
                              command=lambda: self._save_and_print("pdf"))
            pmenu.add_separator()
            pmenu.add_command(label="🖨  Print to…  (choose printer)",
                              command=lambda: self._save_and_print("default", ask=True))
            pmenu.add_command(label="↺  Print previous invoice",
                              command=self._print_previous)
            print_btn.configure(menu=pmenu)
            print_btn.pack(side="right", padx=(6, 0))

            tk.Button(inner, command=lambda: self._save(confirm=False),
                      **slim(key_style(C.get("tile_blue", C["primary"]), "",
                                       "F9  Save Draft"))).pack(side="right")

            # Hold (Pending): save current sale as draft, then start a fresh one
            tk.Button(inner, command=self._hold_sale,
                      **slim(key_style(C.get("tile_orange", C["warning"]), "",
                                       "⏸  Hold"))).pack(side="right", padx=(0, 6))

            # Teller: cash-tender popup (enter cash given → shows change)
            tk.Button(inner, command=self._open_teller,
                      **slim(key_style(C.get("slate", "#5B6B82"), "",
                                       "💵  Teller"))).pack(side="right", padx=(0, 6))

    # ── Teller (cash tender) ──────────────────────────────────
    def _teller_num(self, v):
        try:
            return float(str(v).replace(",", "") or 0)
        except Exception:
            return 0.0

    def _open_teller(self):
        total = self._teller_num(self.total_var.get()) if hasattr(self, "total_var") else 0.0
        if total <= 0:
            messagebox.showinfo("Teller", "Add items to the invoice first.")
            return
        try:
            from ui.numpad import CashTenderDialog
            CashTenderDialog(self.win, total, on_confirm=self._apply_tender,
                             theme=cfg.theme(),
                             currency=__import__("modules.country", fromlist=["symbol"]).symbol())
        except Exception as e:
            messagebox.showerror("Teller", str(e)[:200])

    def _apply_tender(self, received):
        """Apply the tendered cash. Change (if any) is shown in the dialog;
        the recorded cash payment is capped at the invoice total."""
        # release Full Pay so the tendered amount stands
        if getattr(self, "full_pay_var", None) and self.full_pay_var.get():
            self.full_pay_var.set(False)
            self._toggle_full_pay()
        total = self._teller_num(self.total_var.get()) if hasattr(self, "total_var") else 0.0
        applied = min(received, total) if received > 0 else 0.0
        if hasattr(self, "cash_var"):
            self.cash_var.set(f"{applied:.2f}")
            self.card_var.set("0.00")
            self.bank_var.set("0.00")
            self._update_balance()

    # ── Defaults ──────────────────────────────────────────────
    @staticmethod
    def _default_due(today_iso):
        """Settings ▸ Payment ▸ Default Payment Terms (Net 7/15/30…)."""
        try:
            import re as _re
            from datetime import timedelta
            m = _re.search(r"(\d+)", str(cfg.get("pay_default_terms", "") or ""))
            if m:
                return (date.fromisoformat(today_iso) + timedelta(days=int(m.group(1)))).isoformat()
        except Exception:
            pass
        return today_iso

    def _set_defaults(self):
        today = date.today().isoformat()
        self.hdr_vars["invoice_date"].set(today)
        self.hdr_vars["due_date"].set(self._default_due(today))
        # show the actual next invoice number (preview)
        try:
            nxt = db.get_next_invoice_number("SALES")
        except Exception:
            nxt = "(auto-generated)"
        self.hdr_vars["invoice_number"].set(nxt or "(auto-generated)")
        self._selected_customer = None
        self._qr_data = None
        # Default customer = Cash ledger / walk-in account
        cash = next((c for c in self._customers
                     if str(c.get("customer_code", "")).upper() in
                     ("CASH", "WALKIN", "CASH-001", "WALK-IN")
                     or "cash" in str(c.get("customer_name_en", "")).lower()
                     or "walk" in str(c.get("customer_name_en", "")).lower()), None)
        if cash:
            try:
                self.cust_combo.set(
                    f"{cash['customer_code']} — {cash['customer_name_en']}")
                self._on_customer_select()
            except Exception:
                pass

    # ── Load existing invoice ─────────────────────────────────
    def _load_invoice(self):
        inv = db.fetchone("SELECT * FROM sales_invoices WHERE invoice_id=?",
                          (self.invoice_id,))
        if not inv:
            return
        self._loading_doc = True            # keep the saved prices (no re-pricing)
        try:
            from modules import price_lists as _PL
            _pk = inv.get("price_list_id")
            self.price_category_var.set(_PL.label_for_key(int(_pk)) if _pk else
                                        _PL.STANDARD)
        except Exception:
            pass
        try:
            self._load_invoice_body(inv)
        finally:
            self._loading_doc = False
        self._on_price_category(reprice=False)
        self._mark_clean()

    # ── Close guard: ask only when lines are not saved ────────
    def _lines_sig(self):
        try:
            return close_guard.lines_sig(self.line_grid.data_lines())
        except Exception:
            return ()

    def _mark_clean(self):
        """The grid now matches the saved / loaded invoice."""
        self._clean_sig = self._lines_sig()

    def _is_dirty(self):
        """✕ / Esc / Cancel ask first only while the grid has lines that
        are not saved: a new bill, or lines changed since load / save."""
        if self.view_only:
            return False
        sig = self._lines_sig()
        if not sig:
            return False
        return not self.invoice_id or sig != getattr(self, "_clean_sig", None)

    def _load_invoice_body(self, inv):
        # v6.9: a saved bill discount is already inside the lines
        for v in ("bill_discount_var", "round_var"):
            if hasattr(self, v):
                getattr(self, v).set("0.00")
        # ⭐ points this bill spent are inside its lines too and stay spent
        self._loaded_points = int(float(inv.get("loyalty_points_redeemed") or 0))
        self._saved_points_extra = 0
        if hasattr(self, "points_var"):
            self.points_var.set("0")

        self.hdr_vars["invoice_number"].set(inv.get("invoice_number",""))
        self.inv_num_label.config(text=inv.get("invoice_number",""))
        self.hdr_vars["invoice_date"].set(str(inv.get("invoice_date","")))
        self.hdr_vars["due_date"].set(str(inv.get("due_date") or "")[:10])   # v6.9: never "None"
        self.hdr_vars["po_number"].set(inv.get("po_number","") or "")
        self.hdr_vars["notes_en"].set(inv.get("notes_en","") or "")
        if hasattr(self, "pos_combo"):
            try:
                from modules import country as _ctry
                self.pos_var.set(_ctry.state_label(_ctry.place_of_supply("sales", inv)))
            except Exception:
                pass
        self.payment_var.set(inv.get("payment_method","credit"))
        # Load the paid amount into Cash Received so balance shows on edit
        if hasattr(self, "cash_var"):
            # money taken at the till only (receipts settled later stay
            # separate, so re-saving never books them twice)
            tend = None
            try:
                from modules import doc_posting as _dp
                tend = (_dp._old_tenders(self.invoice_id) or
                        _dp._tenders_from_header(inv, float(inv.get("total_amount") or 0)))
            except Exception:
                tend = None
            if tend is None:
                tend = {"cash": float(inv.get("paid_amount", 0) or 0), "bank": 0.0}
            self.cash_var.set(f"{float(tend.get('cash') or 0):,.2f}")
            self.card_var.set(f"{float(tend.get('bank') or 0):,.2f}")
            self.bank_var.set("0.00")
            # v6.9.5: a bill paid in full in cash stays paid in full when its
            # lines change (Cash Rcvd ticked → the cash follows the total);
            # before, the difference went on the customer's account
            if hasattr(self, "full_pay_var"):
                _tot = float(inv.get("total_amount") or 0)
                self.full_pay_var.set(
                    _tot > 0 and str(inv.get("invoice_status") or "").lower() == "confirmed"
                    and str(inv.get("payment_method") or "").lower() == "cash"
                    and not float(tend.get("bank") or 0)
                    and abs(float(tend.get("cash") or 0) - _tot) < 0.005)

        # Customer
        cid = inv.get("customer_id")
        if cid:
            cust = next((c for c in self._customers
                         if c["customer_id"] == cid), None)
            if cust:
                self.cust_combo.set(
                    f"{cust['customer_code']} — {cust['customer_name_en']}")
                self._on_customer_select()
                if hasattr(self, "cust_vat_var"):
                    self._fill_party_boxes(cust, inv)       # v7.8: what the bill was saved with

        # Lines → load into the new grid
        lines = db.fetchall(
            "SELECT * FROM sales_invoice_lines WHERE invoice_id=? "
            "ORDER BY line_number", (self.invoice_id,))
        try:
            self.line_grid.set_lines([dict(l) for l in lines])
            self._lines = self.line_grid.data_lines()
        except Exception:
            pass

        # QR
        qr_data = inv.get("qr_code_data","")
        if qr_data:
            self._qr_data = qr_data
            qr_img = generate_qr_photoimage(qr_data, 160)
            if qr_img:
                self.qr_label.config(image=qr_img, text="")
                self.qr_label.image = qr_img

        self._update_totals()

    # ── Save ──────────────────────────────────────────────────
    def _save(self, confirm=False, keep_open=False, silent=False):
        if self.view_only:                 # v6.9.5: a view-only window never saves
            return False
        from modules import permissions as _pm
        if not _pm.allowed("sales", "edit" if self.invoice_id else "add"):
            return False
        # v6.9.5: a CONFIRMED bill stays confirmed when it is changed — F9 /
        # Save Draft / Hold turned it back into a draft (stock, books and
        # the receipts settled on it were undone)
        if self.invoice_id and not confirm:
            from modules import doc_edit
            confirm = doc_edit.info("sales", self.invoice_id)[1] == "confirmed"
        # Pull the latest lines straight from the grid
        try:
            self._lines = self.line_grid.data_lines()
        except Exception:
            pass
        # Validate
        errors = []
        if not self._lines:
            errors.append("Add at least one line item.")
        if not self.cust_var.get() or "—" not in self.cust_var.get():
            errors.append("Select a customer.")
        inv_date = self.hdr_vars["invoice_date"].get().strip()
        if not inv_date:
            errors.append("Invoice date required.")
        else:
            from modules.date_utils import validate_invoice_date
            ok, iso_date, err = validate_invoice_date(inv_date)
            if not ok:
                errors.append(err)
            else:
                inv_date = iso_date
                self.hdr_vars["invoice_date"].set(iso_date)  # normalize
                try:
                    from modules import financial_year as fy
                    lock_msg = fy.guard_active(iso_date)
                    if lock_msg:
                        errors.append(lock_msg)
                except Exception:
                    pass

        if self.invoice_id and not errors:
            try:
                from modules import doc_edit
                why = doc_edit.block_reason("sales", self.invoice_id, "edit")
                if why:
                    errors.append(why)
            except Exception:
                pass
        if errors:
            self.save_status.set("⚠️  " + "  |  ".join(errors))
            return False
        self.save_status.set("")

        # ── Negative stock guard (Settings ▸ Sales / Inventory) ──
        # Blocks NEW invoices that would drive stock below zero unless
        # "Allow Negative Stock" is enabled in either section.
        if not self.invoice_id and not (cfg.flag("allow_negative_stock")
                                        or cfg.flag("inv_negative_stock")):
            short = []
            for ln in self._lines:
                try:
                    if not ln.get("product_id"):
                        continue
                    have = float(ln.get("stock_quantity", 0) or 0)
                    factor = float(ln.get("box_qty") or 1) or 1
                    need = float(ln.get("quantity", 0) or 0) * factor
                    if need > have + 1e-9:
                        short.append("• %s — need %g, in stock %g"
                                     % (ln.get("product_name_en", "?"),
                                        need, have))
                except Exception:
                    pass
            if short:
                messagebox.showwarning(
                    "Insufficient Stock",
                    "These items would go below zero stock:\n\n"
                    + "\n".join(short[:10])
                    + "\n\nEnable 'Allow Negative Stock' in Settings "
                      "to permit this.")
                self.save_status.set("⚠️  Insufficient stock.")
                return False

        _vat_err = self._check_typed_vat()        # v7.8: the tax number typed on the bill
        if _vat_err:
            self.save_status.set("❌ " + _vat_err)
            return False

        # Get customer id
        sel_code = self.cust_var.get().split(" — ")[0]
        cust = next((c for c in self._customers
                     if c["customer_code"] == sel_code), None)
        if not cust:
            self.save_status.set("❌ Customer not found.")
            return

        # v6.9: Bill Disc (and the Round box) are spread over the lines
        # BEFORE VAT, so the saved invoice, journal, print and ZATCA match
        # the GRAND TOTAL on the screen. The screen's own lines stay as
        # they are (Save & Print keeps the window open).
        from modules.doc_math import doc_totals, round_lines
        _pts_used = int(getattr(self, "_loaded_points", 0) or 0) + self._points_used()[0]
        save_lines = round_lines(self._lines_to_save())     # halalas, adding up

        # Totals the ZATCA way (v6.9.2): VAT once per rate on the bill —
        # the same VAT the e-invoice XML and its QR carry
        T = doc_totals(save_lines, self._incl())
        discount = sum(ln.get("discount_amount",0) for ln in save_lines)
        subtotal = taxable = T["taxable"]
        vat_amt  = T["vat"]
        total    = T["total"]

        # ── Credit limit (Settings ▸ Customer) — credit sales only ──
        try:
            is_credit = (str(self.payment_var.get()).lower() == "credit"
                         and not (getattr(self, "full_pay_var", None)
                                  and self.full_pay_var.get()))
        except Exception:
            is_credit = False
        if is_credit and not self.invoice_id and not silent:
            from modules import credit_check
            if not credit_check.confirm(cust.get("customer_id"), total):
                self.save_status.set("⚠️  Over customer credit limit.")
                return False

        # Generate QR
        try:
            seller = (self._company.get("company_name_ar") or
                      self._company.get("company_name_en","Company"))
            from modules.zatca.qr_generator import clean_vat_number
            vat_no = clean_vat_number(self._company.get("vat_registration_no"))
            dt_str = format_zatca_datetime(datetime.utcnow())
            qr_data = generate_zatca_qr(seller, vat_no, dt_str, total, vat_amt)
        except Exception:
            qr_data = ""

        inv_status = "confirmed" if confirm else "draft"
        inv_uuid   = str(uuid.uuid4())

        # ── Money taken now (Cash / Card / Bank boxes) ──────────
        # Cash→cash account, Card/Bank→bank account, the rest→customer.
        # Tendered above the total is change and is never booked.
        def _num(v):
            try:
                return float(str(v.get()).replace(",", "") or 0)
            except Exception:
                return 0.0
        t_cash = _num(self.cash_var) if hasattr(self, "cash_var") else 0.0
        t_card = _num(self.card_var) if hasattr(self, "card_var") else 0.0
        t_bank = _num(self.bank_var) if hasattr(self, "bank_var") else 0.0
        if t_cash + t_card + t_bank == 0:
            pm = str(self.payment_var.get() or "").lower()
            if pm == "cash":
                t_cash = total
            elif pm in ("card", "bank_transfer", "bank", "mada"):
                t_bank = total
            # 'credit' leaves all zero → whole bill on the customer's account
        t_bank += t_card
        paid_amt = round(min(total, t_cash + t_bank), 2)
        _moved = False
        if self.invoice_id:
            try:   # receipts settled on this invoice later stay counted
                from modules import allocation
                # v6.9.5: moved to another customer → what the old one paid or
                # returned on it goes back to the old one's account (below)
                _moved = allocation.party_moved("receipt", self.invoice_id,
                                                cust["customer_id"])
                if not _moved:
                    paid_amt = round(min(total, paid_amt + allocation.allocated_total(
                        "receipt", self.invoice_id)), 2)
            except Exception:
                pass
        pay_status = ("paid" if paid_amt >= total - 0.005
                      else ("partial" if paid_amt > 0 else "unpaid"))

        # ── v5.27: the whole save (header, lines, ZATCA, stock, journals)
        #    is ONE transaction — it is all kept, or nothing is. ──
        _was_id, _tx = self.invoice_id, None
        try:
            _tx = db.begin()
            if self.invoice_id:
                if _moved:
                    from modules import allocation
                    allocation.unlink_document("receipt", self.invoice_id)
                # Update
                db.execute(
                    "UPDATE sales_invoices SET "
                    "invoice_date=?, due_date=?, customer_id=?, "
                    "customer_name_en=?, customer_name_ar=?, customer_vat_no=?, "
                    "customer_city_en=?, payment_method=?, notes_en=?, "
                    "subtotal_amount=?, discount_amount=?, taxable_amount=?, "
                    "vat_amount=?, total_amount=?, invoice_status=?, "
                    "payment_status=?, paid_amount=?, "
                    "qr_code_data=?, updated_at=GETDATE() "
                    "WHERE invoice_id=?",
                    (inv_date, self.hdr_vars["due_date"].get() or None,
                     cust["customer_id"], cust["customer_name_en"],
                     cust.get("customer_name_ar",""), cust.get("vat_registration_no",""),
                     cust.get("city_en",""), self.payment_var.get(),
                     self.hdr_vars["notes_en"].get(),
                     subtotal, discount, taxable, vat_amt, total,
                     inv_status, pay_status, paid_amt, qr_data, self.invoice_id)
                )
                # Delete old lines
                db.execute("DELETE FROM sales_invoice_lines WHERE invoice_id=?",
                           (self.invoice_id,))
                inv_id = self.invoice_id
                inv_number = self.hdr_vars["invoice_number"].get()
            else:
                # Get invoice number (plain number, Polosys-style).
                # Two tills at the same moment: the second takes the next number.
                from config.database import is_duplicate_error
                for _n_try in range(4):
                    inv_number = db.get_next_invoice_number("SALES", plain=True)
                    try:
                        with db.savepoint():
                            self._insert_header(inv_number, inv_uuid, inv_date, cust,
                                                subtotal, discount, taxable, vat_amt, total,
                                                inv_status, pay_status, paid_amt, qr_data)
                        break
                    except Exception as _e:
                        if _n_try < 3 and is_duplicate_error(_e):
                            continue
                        raise
                inv_id = db.last_identity("sales_invoices", "invoice_id")

            # Remember the id so Save+Print (F2/F3) and Hold can use it
            self.invoice_id = inv_id
            self._save_pos(inv_id)
            self._save_party_snapshot(inv_id, cust)

            # Insert lines (bill discount already spread in — v6.9)
            for i, ln in enumerate(save_lines, 1):
                db.execute(
                    "INSERT INTO sales_invoice_lines ("
                    "invoice_id, line_number, product_id, product_code, "
                    "product_name_en, product_name_ar, quantity, "
                    "unit_of_measure_en, unit_price, discount_percent, "
                    "discount_amount, line_amount, vat_category_id, "
                    "vat_category_code, vat_rate, vat_amount, line_total"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (inv_id, i,
                     ln.get("product_id"),
                     ln.get("product_code",""),
                     ln.get("product_name_en",""),
                     ln.get("product_name_ar",""),
                     ln.get("quantity",1),
                     ln.get("unit_of_measure_en","Unit"),
                     ln.get("unit_price",0),
                     ln.get("discount_percent",0),
                     ln.get("discount_amount",0),
                     ln.get("line_amount",0),
                     ln.get("vat_category_id"),
                     ln.get("vat_category_code","S"),
                     ln.get("vat_rate",15),
                     ln.get("vat_amount",0),
                     ln.get("line_total",0))
                )
                if ln.get("offer_id"):
                    try:        # which offer gave this discount (bill + offer report)
                        db.execute("UPDATE sales_invoice_lines SET offer_id=?, offer_text=? "
                                   "WHERE invoice_id=? AND line_number=?",
                                   (ln["offer_id"], (ln.get("offer_text") or "")[:80],
                                    inv_id, i))
                    except Exception:
                        pass

            status_msg = "confirmed" if confirm else "saved as draft"

            # Invoice-window sales are tagged so the POS report can tell
            # them apart (column added by stock_posting_patch.sql).
            try:
                db.execute("UPDATE sales_invoices SET sale_channel='INV' "
                           "WHERE invoice_id=? AND sale_channel IS NULL", (inv_id,))
            except Exception:
                pass
            try:                         # v6.0: which price list the invoice used
                _pk = self._price_key()
                db.execute("UPDATE sales_invoices SET price_list_id=? WHERE invoice_id=?",
                           (_pk if isinstance(_pk, int) else None, inv_id))
            except Exception:
                pass

            try:                    # ⭐ loyalty points spent on this bill (v6.9.2)
                db.execute("UPDATE sales_invoices SET loyalty_points_redeemed=? "
                           "WHERE invoice_id=?", (_pts_used or None, inv_id))
                self._saved_points_extra = _pts_used - int(getattr(self, "_loaded_points", 0) or 0)
            except Exception:
                pass

            # ── Stock + accounts ─────────────────────────────────
            # Draft → nothing moves. Confirmed → stock out, sale journal
            # and cost of sales. Re-saving/editing re-syncs (no doubles).
            from modules import doc_posting
            try:
                if inv_status == "confirmed":       # ZATCA Phase 2: sign + queue
                    from modules.zatca import egs as _zegs
                    _zegs.after_save("sales", inv_id)
            except Exception:
                pass
            try:
                doc_posting.sync("sales", inv_id,
                                 tenders={"cash": t_cash, "bank": t_bank})
            except Exception as e:
                doc_posting.last_warning = str(e)[:200]
            _tx.commit()          # everything above is kept together (or the except undoes it)
            self._mark_clean()    # close guard: nothing unsaved now

            if not silent:
                messagebox.showinfo(
                    "✅ Success",
                    f"Invoice {inv_number} {status_msg}!\n"
                    f"Total: {total:,.2f} SAR  |  VAT: {vat_amt:,.2f} SAR"
                )
            if confirm:
                doc_posting.notify(self.win)
                # Settings ▸ WhatsApp: send the invoice when it is confirmed
                try:
                    if (not silent and cfg.flag("wa_enabled") and cfg.flag("wa_auto_invoice")
                            and str(cust.get("customer_code", "")).upper()
                            not in ("WALKIN", "CASH", "WALK-IN")):
                        from ui.whatsapp_send import send_document
                        send_document(self.parent, "sales", inv_id, auto=True)
                except Exception:
                    pass
            # Auto-print after save (Print After Save tick, or the global
            # print_auto setting). Uses the chosen paper width.
            try:
                want = bool(getattr(self, "print_after_var", None)
                            and self.print_after_var.get())
                if not want:
                    want = (cfg.flag("print_auto", False)
                            or cfg.flag("auto_print_invoice", False))
                # silent = we were called BY Save & Print, which prints
                # itself — don't print a second copy here.
                if want and not silent:
                    self._save_and_print(fmt="default", already_saved=True)
            except Exception:
                pass
            try:                         # v7.5: an order loaded into this invoice → delivered
                from modules import doc_links as _DL
                _DL.after_save(self, inv_id)
            except Exception:
                pass
            if not _was_id:              # v7.5: the items go to their print stations
                try:
                    from modules import print_stations as _PS
                    _res = _PS.send("sales", inv_id,
                                    assigned=self._station_ids.get(self.station_var.get()))
                    if _res:
                        self.last_station_print = _res
                except Exception:
                    pass
            if self.on_save:
                self.on_save()
            if keep_open:
                return True
            # v6.9.3: the window stays open (Settings ▸ General ▸ After saving)
            from ui import after_save
            parent, cb = self.parent, self.on_save
            after_save.finish(self, inv_number,
                              new=lambda: InvoiceForm(parent, on_save=cb),
                              keep=lambda: InvoiceForm(parent, invoice_id=inv_id, on_save=cb),
                              edited=bool(_was_id))
            return True

        except Exception as e:
            if _tx is not None and not _tx.kept:
                _tx.rollback()                     # nothing of a failed save is kept
                self.invoice_id = _was_id
                e = "Not saved — " + str(e)
            self.save_status.set(f"❌ {str(e)[:100]}")
            return False

    # ── v7.8: the customer typed on the bill ───────────────────
    def _typed_party(self):
        g = lambda n: (getattr(self, n).get().strip() if hasattr(self, n) else "")
        vat = "".join(g("cust_vat_var").split()).upper()
        return {"name": g("cust_name_var"), "vat": vat, "mobile": g("cust_mobile_var"),
                "address": g("cust_addr_var")}

    def _check_typed_vat(self):
        """'' when fine, else what is wrong with the typed tax number."""
        from modules import party_info as _PI
        return _PI.check_tax_no(self._typed_party()["vat"])

    def _save_party_snapshot(self, inv_id, cust):
        """Name / tax no. / mobile / address typed in the window → on the bill
        (printed). Blank boxes keep what the customer card has."""
        from modules import party_info as _PI
        _PI.save_typed(inv_id, self._typed_party(), cust)

    def _fill_party_boxes(self, cust, inv=None):
        """A customer from the list fills Name / tax no. / mobile / address
        (they can be changed for this bill); the Cash Customer leaves them
        empty to type in. A saved bill shows what it was saved with."""
        try:
            from modules import party_info as _PI
            cash = _PI.is_cash("customer", cust.get("customer_id"))
        except Exception:
            cash = False
        if inv is not None:
            nm = inv.get("customer_name_en") or ""
            same_as_card = nm == (cust.get("customer_name_en") or "")
            self.cust_name_var.set("" if (cash and same_as_card) else nm)
            self.cust_vat_var.set(inv.get("customer_vat_no") or "")
            self.cust_mobile_var.set(inv.get("customer_phone") or ("" if cash else cust.get("mobile") or cust.get("phone") or ""))
            self.cust_addr_var.set(inv.get("customer_address_en") or ("" if cash else cust.get("address_en") or cust.get("city_en") or ""))
            return
        if cash:
            for v in (self.cust_name_var, self.cust_vat_var, self.cust_mobile_var, self.cust_addr_var):
                v.set("")
            return
        self.cust_name_var.set(cust.get("customer_name_en") or "")
        self.cust_vat_var.set(cust.get("vat_registration_no") or "")
        self.cust_mobile_var.set(cust.get("mobile") or cust.get("phone") or "")
        self.cust_addr_var.set(cust.get("address_en") or cust.get("city_en") or "")

    def _show_party_facts(self, cust=None):
        """L.Bill / Bal under the grid: the customer's ledger balance and last
        bill, and the last bill of this counter."""
        cust = cust or getattr(self, "_selected_customer", None) or {}
        card = getattr(self, "_bal_card", None)
        if card is not None:                       # v7.9: the balance card in the header
            txt = card.show("customer", cust.get("customer_id"), exclude_id=self.invoice_id)
        else:
            try:
                from modules import party_info as _PI
                txt = _PI.text("customer", cust.get("customer_id"), exclude_id=self.invoice_id)
            except Exception:
                txt = "L.Bill: —"
        if hasattr(self, "lbill_var"):
            self.lbill_var.set(txt or "L.Bill: —")
        return txt

    def _save_pos(self, inv_id):
        """v7.0 India: keep the bill's place of supply (posting reads it)."""
        code = self._pos_code() if hasattr(self, "pos_combo") else ""
        if not code:
            return
        try:
            db.execute("UPDATE sales_invoices SET place_of_supply=? WHERE invoice_id=?", (code, inv_id))
        except Exception:
            pass

    def _insert_header(self, inv_number, inv_uuid, inv_date, cust, subtotal, discount,
                       taxable, vat_amt, total, inv_status, pay_status, paid_amt, qr_data):
        db.execute(
            "INSERT INTO sales_invoices ("
            "invoice_number, invoice_uuid, invoice_date, invoice_time, "
            "due_date, customer_id, customer_name_en, customer_name_ar, "
            "customer_vat_no, customer_building_no, customer_street_en, "
            "customer_district_en, customer_postal_code, customer_city_en, "
            "customer_country_code, payment_method, notes_en, "
            "subtotal_amount, discount_amount, taxable_amount, "
            "vat_amount, total_amount, invoice_status, "
            "payment_status, paid_amount, qr_code_data"
            ") VALUES (?,?,?,CONVERT(time,GETDATE()),?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (inv_number, inv_uuid, inv_date,
             self.hdr_vars["due_date"].get() or None,
             cust["customer_id"], cust["customer_name_en"],
             cust.get("customer_name_ar", ""),
             cust.get("vat_registration_no", ""),
             cust.get("building_number", ""),
             cust.get("street_name_en", ""),
             cust.get("district_en", ""),
             cust.get("postal_code", ""),
             cust.get("city_en", ""),
             cust.get("country_code") or _company_country(),
             self.payment_var.get(),
             self.hdr_vars["notes_en"].get(),
             subtotal, discount, taxable, vat_amt, total,
             inv_status, pay_status, paid_amt, qr_data))

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
