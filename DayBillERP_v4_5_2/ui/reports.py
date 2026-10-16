# ============================================================
# DayBill ERP - Reports Module
# Sales Report | Customer Statement | Top Products
# Date range | Chart | Excel export
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db
from modules import permissions as perm


class ReportsView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._topbar(C)
        self._tabs(C)

    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text=f"📈  {t('nav.reports')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

    def _tabs(self, C):
        style = ttk.Style()
        style.configure("R.TNotebook", background=C["content_bg"], borderwidth=0)
        style.configure("R.TNotebook.Tab", font=("Segoe UI", 10), padding=(16, 8))
        nb = ttk.Notebook(self.frame, style="R.TNotebook")
        nb.pack(fill="both", expand=True, padx=24, pady=14)

        self.t_sales = tk.Frame(nb, bg=C["content_bg"])
        self.t_stmt = tk.Frame(nb, bg=C["content_bg"])
        self.t_prod = tk.Frame(nb, bg=C["content_bg"])
        nb.add(self.t_sales, text="  📊  Sales Report  ")
        nb.add(self.t_stmt, text="  👤  Customer Statement  ")
        nb.add(self.t_prod, text="  📦  Top Products  ")

        self._build_sales(self.t_sales, C)
        self._build_statement(self.t_stmt, C)
        self._build_products(self.t_prod, C)

    # ── Date range helper ─────────────────────────────────────
    def _date_bar(self, parent, C, on_run):
        bar = tk.Frame(parent, bg=C["card_bg"],
                       highlightbackground=C["border"], highlightthickness=1)
        bar.pack(fill="x", pady=(10, 10))
        inner = tk.Frame(bar, bg=C["card_bg"])
        inner.pack(fill="x", padx=14, pady=10)
        tk.Label(inner, text="From:", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        from_var = tk.StringVar(value=(date.today().replace(day=1)).strftime("%Y-%m-%d"))
        _rf = tk.Entry(inner, textvariable=from_var, font=("Segoe UI", 9), width=12,
                 relief="solid", bd=1)
        _rf.pack(side="left", padx=(4, 12))
        tk.Label(inner, text="To:", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        to_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        _rt = tk.Entry(inner, textvariable=to_var, font=("Segoe UI", 9), width=12,
                 relief="solid", bd=1)
        _rt.pack(side="left", padx=(4, 12))
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(_rf, from_var)
            attach_datepicker(_rt, to_var)
        except Exception:
            pass
        tk.Button(inner, text="🔍 Generate", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=5,
                  cursor="hand2", command=on_run).pack(side="left")
        return from_var, to_var

    # ── SALES REPORT ──────────────────────────────────────────
    def _build_sales(self, parent, C):
        self.sales_from, self.sales_to = self._date_bar(parent, C, self._run_sales)
        self.sales_body = tk.Frame(parent, bg=C["content_bg"])
        self.sales_body.pack(fill="both", expand=True)
        self._run_sales()

    def _run_sales(self):
        C = cfg.theme()
        for w in self.sales_body.winfo_children():
            w.destroy()
        try:
            rows = db.fetchall(
                "SELECT CAST(invoice_date AS DATE) AS d, "
                "COUNT(*) AS cnt, SUM(subtotal_amount) AS sub, "
                "SUM(vat_amount) AS vat, SUM(total_amount) AS total "
                "FROM sales_invoices WHERE invoice_status='confirmed' "
                "AND invoice_date BETWEEN ? AND ? "
                "GROUP BY CAST(invoice_date AS DATE) ORDER BY d",
                (self.sales_from.get(), self.sales_to.get()))
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            return

        total_sales = sum(float(r.get("total", 0)) for r in rows)
        total_vat = sum(float(r.get("vat", 0)) for r in rows)
        total_cnt = sum(int(r.get("cnt", 0)) for r in rows)

        # Summary cards
        cards = tk.Frame(self.sales_body, bg=C["content_bg"])
        cards.pack(fill="x", pady=(0, 12))
        for icon, label, val, color in [
            ("💰", "Total Sales", f"{total_sales:,.2f}", C["success"]),
            ("📋", "VAT Collected", f"{total_vat:,.2f}", C["info"]),
            ("🧾", "Invoices", str(total_cnt), C["primary"])]:
            card = tk.Frame(cards, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 10), ipadx=14, ipady=6)
            tk.Label(card, text=f"{icon} {label}", font=("Segoe UI", 8),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=val, font=("Segoe UI", 16, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w", padx=8, pady=(0, 6))

        # Table
        wrap = tk.Frame(self.sales_body, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        wrap.pack(fill="both", expand=True)
        cols = ("date", "cnt", "sub", "vat", "total")
        labels = {"date": ("Date", 140, "center"), "cnt": ("Invoices", 100, "center"),
                  "sub": ("Subtotal", 140, "e"), "vat": ("VAT", 140, "e"),
                  "total": ("Total SAR", 150, "e")}
        vsb = ttk.Scrollbar(wrap, orient="vertical")
        vsb.pack(side="right", fill="y")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        for col in cols:
            h, w, a = labels[col]
            tree.heading(col, text=h); tree.column(col, width=w, anchor=a)
        tree.pack(fill="both", expand=True)
        for r in rows:
            tree.insert("", "end", values=(
                str(r.get("d", "")), r.get("cnt", 0),
                f"{float(r.get('sub', 0)):,.2f}", f"{float(r.get('vat', 0)):,.2f}",
                f"{float(r.get('total', 0)):,.2f}"))
        if not rows:
            tree.insert("", "end", values=("No data", "", "", "", ""))

        # Export + Print
        data_rows = [[str(r.get("d", "")), r.get("cnt", 0),
                      f"{float(r.get('sub', 0)):,.2f}",
                      f"{float(r.get('vat', 0)):,.2f}",
                      f"{float(r.get('total', 0)):,.2f}"] for r in rows]
        self._export_bar(
            self.sales_body, "Sales_Report", "Sales Report",
            ["Date", "Invoices", "Subtotal", "VAT", "Total SAR"], data_rows,
            summary=[("Total Sales", f"{total_sales:,.2f}"),
                     ("VAT Collected", f"{total_vat:,.2f}"),
                     ("Invoices", str(total_cnt))],
            col_align=["center", "center", "right", "right", "right"])

    # ── CUSTOMER STATEMENT ────────────────────────────────────
    def _build_statement(self, parent, C):
        bar = tk.Frame(parent, bg=C["card_bg"],
                       highlightbackground=C["border"], highlightthickness=1)
        bar.pack(fill="x", pady=(10, 10))
        inner = tk.Frame(bar, bg=C["card_bg"])
        inner.pack(fill="x", padx=14, pady=10)
        tk.Label(inner, text="Customer:", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
        try:
            self._stmt_custs = db.fetchall(
                "SELECT customer_id, customer_name_en FROM customers "
                "WHERE is_active=1 ORDER BY customer_name_en")
        except Exception:
            self._stmt_custs = []
        self.stmt_var = tk.StringVar()
        self.stmt_cb = ttk.Combobox(inner, textvariable=self.stmt_var,
                                    values=[c["customer_name_en"] for c in self._stmt_custs],
                                    font=("Segoe UI", 9), width=30)
        self.stmt_cb.pack(side="left", padx=8)
        tk.Button(inner, text="🔍 Generate", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=5,
                  cursor="hand2", command=self._run_statement).pack(side="left")

        self.stmt_body = tk.Frame(parent, bg=C["content_bg"])
        self.stmt_body.pack(fill="both", expand=True)

    def _run_statement(self):
        C = cfg.theme()
        for w in self.stmt_body.winfo_children():
            w.destroy()
        idx = self.stmt_cb.current()
        if idx < 0:
            tk.Label(self.stmt_body, text="Select a customer above.",
                     font=("Segoe UI", 10), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(pady=40)
            return
        cust = self._stmt_custs[idx]
        try:
            invoices = db.fetchall(
                "SELECT invoice_number, invoice_date, total_amount, paid_amount, "
                "payment_status FROM sales_invoices WHERE customer_id=? "
                "AND invoice_status='confirmed' ORDER BY invoice_date",
                (cust["customer_id"],))
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            return

        total = sum(float(r.get("total_amount", 0)) for r in invoices)
        paid = sum(float(r.get("paid_amount", 0)) for r in invoices)
        balance = total - paid
        # v5.26: what the customer really owes = their ledger account (opening
        # balance, returns, receipts not linked to a bill … included)
        try:
            from ui.party_statement import build_statement
            balance = float(build_statement("customer", cust["customer_id"])["closing"])
        except Exception:
            pass

        cards = tk.Frame(self.stmt_body, bg=C["content_bg"])
        cards.pack(fill="x", pady=(0, 12))
        for icon, label, val, color in [
            ("🧾", "Total Invoiced", f"{total:,.2f}", C["primary"]),
            ("✅", "Total Paid", f"{paid:,.2f}", C["success"]),
            ("⏳", "Balance Due", f"{balance:,.2f}", C["danger"] if balance > 0 else C["success"])]:
            card = tk.Frame(cards, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 10), ipadx=14, ipady=6)
            tk.Label(card, text=f"{icon} {label}", font=("Segoe UI", 8),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=val, font=("Segoe UI", 16, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w", padx=8, pady=(0, 6))

        wrap = tk.Frame(self.stmt_body, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        wrap.pack(fill="both", expand=True)
        cols = ("number", "date", "total", "paid", "balance", "status")
        labels = {"number": ("Invoice #", 130, "center"), "date": ("Date", 100, "center"),
                  "total": ("Total", 120, "e"), "paid": ("Paid", 120, "e"),
                  "balance": ("Balance", 120, "e"), "status": ("Status", 100, "center")}
        vsb = ttk.Scrollbar(wrap, orient="vertical")
        vsb.pack(side="right", fill="y")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        for col in cols:
            h, w, a = labels[col]
            tree.heading(col, text=h); tree.column(col, width=w, anchor=a)
        tree.pack(fill="both", expand=True)
        for r in invoices:
            bal = float(r.get("total_amount", 0)) - float(r.get("paid_amount", 0))
            tree.insert("", "end", values=(
                r.get("invoice_number", ""), str(r.get("invoice_date", "")),
                f"{float(r.get('total_amount', 0)):,.2f}",
                f"{float(r.get('paid_amount', 0)):,.2f}", f"{bal:,.2f}",
                r.get("payment_status", "")))
        if not invoices:
            tree.insert("", "end", values=("No invoices", "", "", "", "", ""))

        # Export + Print
        data_rows = []
        for r in invoices:
            bal = float(r.get("total_amount", 0)) - float(r.get("paid_amount", 0))
            data_rows.append([
                r.get("invoice_number", ""), str(r.get("invoice_date", "")),
                f"{float(r.get('total_amount', 0)):,.2f}",
                f"{float(r.get('paid_amount', 0)):,.2f}", f"{bal:,.2f}",
                r.get("payment_status", "")])
        self._export_bar(
            self.stmt_body, f"Statement_{cust.get('customer_name_en','')}",
            f"Customer Statement — {cust.get('customer_name_en','')}",
            ["Invoice #", "Date", "Total", "Paid", "Balance", "Status"], data_rows,
            summary=[("Total Invoiced", f"{total:,.2f}"),
                     ("Total Paid", f"{paid:,.2f}"),
                     ("Balance Due", f"{balance:,.2f}")],
            col_align=["center", "center", "right", "right", "right", "center"])

    # ── TOP PRODUCTS ──────────────────────────────────────────
    def _build_products(self, parent, C):
        self.prod_from, self.prod_to = self._date_bar(parent, C, self._run_products)
        self.prod_body = tk.Frame(parent, bg=C["content_bg"])
        self.prod_body.pack(fill="both", expand=True)
        self._run_products()

    def _run_products(self):
        C = cfg.theme()
        for w in self.prod_body.winfo_children():
            w.destroy()
        try:
            rows = db.fetchall(
                "SELECT TOP 20 sil.product_name_en, "
                "SUM(sil.quantity) AS qty, SUM(sil.line_total) AS revenue "
                "FROM sales_invoice_lines sil "
                "JOIN sales_invoices si ON sil.invoice_id=si.invoice_id "
                "WHERE si.invoice_status='confirmed' "
                "AND si.invoice_date BETWEEN ? AND ? "
                "GROUP BY sil.product_name_en ORDER BY revenue DESC",
                (self.prod_from.get(), self.prod_to.get()))
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            return

        wrap = tk.Frame(self.prod_body, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        wrap.pack(fill="both", expand=True)
        cols = ("rank", "product", "qty", "revenue")
        labels = {"rank": ("#", 50, "center"), "product": ("Product", 320, "w"),
                  "qty": ("Qty Sold", 120, "e"), "revenue": ("Revenue SAR", 160, "e")}
        vsb = ttk.Scrollbar(wrap, orient="vertical")
        vsb.pack(side="right", fill="y")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        for col in cols:
            h, w, a = labels[col]
            tree.heading(col, text=h); tree.column(col, width=w, anchor=a)
        tree.pack(fill="both", expand=True)
        for i, r in enumerate(rows, 1):
            tree.insert("", "end", values=(
                i, r.get("product_name_en", ""), f"{float(r.get('qty', 0)):g}",
                f"{float(r.get('revenue', 0)):,.2f}"))
        if not rows:
            tree.insert("", "end", values=("", "No data", "", ""))

        # Export + Print
        data_rows = [[i, r.get("product_name_en", ""),
                      f"{float(r.get('qty', 0)):g}",
                      f"{float(r.get('revenue', 0)):,.2f}"]
                     for i, r in enumerate(rows, 1)]
        self._export_bar(
            self.prod_body, "Top_Products", "Top Products",
            ["#", "Product", "Qty Sold", "Revenue SAR"], data_rows,
            col_align=["center", "left", "right", "right"])

    # ── Export / Print toolbar (Excel + PDF) ──────────────────
    def _export_bar(self, parent, name, title, headers, data_rows,
                    summary=None, col_align=None):
        """Add an Excel + Print button row under a report table."""
        C = cfg.theme()
        bar = tk.Frame(parent, bg=C["content_bg"])
        # packed FIRST at the bottom so a long table can never push the
        # Export/Print buttons off-screen
        _first = parent.pack_slaves()
        if _first:
            bar.pack(side="bottom", anchor="w", pady=(8, 0), before=_first[0])
        else:
            bar.pack(side="bottom", anchor="w", pady=(8, 0))

        def do_excel():
            try:
                from modules.report_export import export_excel
                export_excel(self.frame, name, headers, data_rows,
                             title=title, summary=summary)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def do_pdf():
            try:
                from modules.report_export import export_pdf
                company = None
                try:
                    company = db.fetchone("SELECT * FROM company WHERE company_id=1")
                except Exception:
                    company = None
                export_pdf(self.frame, name, headers, data_rows, title=title,
                           summary=summary, company=company, col_align=col_align)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(bar, text="📥 Export Excel", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=14, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=do_excel).pack(side="left", padx=(0, 8))
        tk.Button(bar, text="🖨 Print / PDF", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat",
                  padx=14, pady=6, cursor="hand2",
                  command=do_pdf).pack(side="left")

    # ── (legacy) Excel-only export helper ─────────────────────
    @perm.guard("reports", "export")
    def _export(self, rows, name, headers, row_fn):
        try:
            from modules.report_export import export_excel
            data_rows = [row_fn(r) for r in rows]
            export_excel(self.frame, name, headers, data_rows, title=name)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
