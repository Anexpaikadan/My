# ============================================================
# Saudi Arabia ERP - VAT Return Report Module (Step 7)
# ZATCA VAT Return form layout (Boxes 1-16)
# Quarterly/Monthly period | Output vs Input | Net Payable
# Save return | Excel export | Drill-down to invoices
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t, is_rtl
from config.database import db
from modules import permissions as perm

STD_RATE = 15.0


class VatReportView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self._data = {}

        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        self._build_topbar(C)
        self._build_period_bar(C)
        self._build_body(C)
        self._set_default_period()
        self._generate()

    # ── Top bar ───────────────────────────────────────────────
    def _build_topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text=f"📋  {t('nav.vat_report')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        btns = tk.Frame(bar, bg=C["content_bg"])
        btns.pack(side="right")
        tk.Button(btns, text="📥  Export Excel", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export_excel).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="🖨  Print / PDF", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._print_pdf).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="💾  Save Return", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat",
                  padx=16, pady=7, cursor="hand2",
                  activebackground=C["primary_dark"],
                  command=self._save_return).pack(side="left")

    # ── Period selector ───────────────────────────────────────
    def _build_period_bar(self, C):
        bar = tk.Frame(self.frame, bg=C["card_bg"],
                       highlightbackground=C["border"], highlightthickness=1)
        bar.pack(fill="x", padx=24, pady=(14, 0))

        inner = tk.Frame(bar, bg=C["card_bg"])
        inner.pack(fill="x", padx=16, pady=12)

        tk.Label(inner, text="Period:", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")

        # Period mode
        self.mode_var = tk.StringVar(value="quarter")
        tk.Radiobutton(inner, text="Quarterly", variable=self.mode_var,
                       value="quarter", font=("Segoe UI", 9), bg=C["card_bg"],
                       activebackground=C["card_bg"],
                       command=self._on_mode_change).pack(side="left", padx=(10, 4))
        tk.Radiobutton(inner, text="Monthly", variable=self.mode_var,
                       value="month", font=("Segoe UI", 9), bg=C["card_bg"],
                       activebackground=C["card_bg"],
                       command=self._on_mode_change).pack(side="left", padx=4)
        tk.Radiobutton(inner, text="Custom", variable=self.mode_var,
                       value="custom", font=("Segoe UI", 9), bg=C["card_bg"],
                       activebackground=C["card_bg"],
                       command=self._on_mode_change).pack(side="left", padx=4)

        # Year
        tk.Label(inner, text="Year:", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=(16, 4))
        cur_year = date.today().year
        self.year_var = tk.StringVar(value=str(cur_year))
        ttk.Combobox(inner, textvariable=self.year_var,
                     values=[str(y) for y in range(cur_year - 5, cur_year + 1)],
                     state="readonly", width=8,
                     font=("Segoe UI", 9)).pack(side="left")

        # Quarter selector
        self.quarter_frame = tk.Frame(inner, bg=C["card_bg"])
        self.quarter_frame.pack(side="left", padx=10)
        tk.Label(self.quarter_frame, text="Quarter:", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.quarter_var = tk.StringVar(value="Q1")
        ttk.Combobox(self.quarter_frame, textvariable=self.quarter_var,
                     values=["Q1", "Q2", "Q3", "Q4"], state="readonly",
                     width=5, font=("Segoe UI", 9)).pack(side="left")

        # Month selector (hidden initially)
        self.month_frame = tk.Frame(inner, bg=C["card_bg"])
        tk.Label(self.month_frame, text="Month:", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.month_var = tk.StringVar(value="January")
        ttk.Combobox(self.month_frame, textvariable=self.month_var,
                     values=["January", "February", "March", "April", "May",
                             "June", "July", "August", "September", "October",
                             "November", "December"],
                     state="readonly", width=11, font=("Segoe UI", 9)).pack(side="left")

        # Custom date range (hidden initially)
        self.custom_frame = tk.Frame(inner, bg=C["card_bg"])
        tk.Label(self.custom_frame, text="From:", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.from_var = tk.StringVar()
        tk.Entry(self.custom_frame, textvariable=self.from_var, width=11,
                 font=("Segoe UI", 9), relief="solid", bd=1).pack(side="left")
        tk.Label(self.custom_frame, text="To:", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=(8, 4))
        self.to_var = tk.StringVar()
        tk.Entry(self.custom_frame, textvariable=self.to_var, width=11,
                 font=("Segoe UI", 9), relief="solid", bd=1).pack(side="left")

        # Generate button
        tk.Button(inner, text="🔍  Generate", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  command=self._generate).pack(side="right")

        # Period label
        self.period_lbl_var = tk.StringVar()
        tk.Label(inner, textvariable=self.period_lbl_var,
                 font=("Segoe UI", 9, "italic"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="right", padx=12)

    def _on_mode_change(self):
        mode = self.mode_var.get()
        self.quarter_frame.pack_forget()
        self.month_frame.pack_forget()
        self.custom_frame.pack_forget()
        if mode == "quarter":
            self.quarter_frame.pack(side="left", padx=10)
        elif mode == "month":
            self.month_frame.pack(side="left", padx=10)
        else:
            self.custom_frame.pack(side="left", padx=10)

    def _set_default_period(self):
        # Default to the current quarter
        m = date.today().month
        q = (m - 1) // 3 + 1
        self.quarter_var.set(f"Q{q}")

    # ── Body ──────────────────────────────────────────────────
    def _build_body(self, C):
        # Scrollable
        canvas = tk.Canvas(self.frame, bg=C["content_bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=24, pady=14)

        self.body = tk.Frame(canvas, bg=C["content_bg"])
        wid = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        self.body.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    # ── Compute period dates ──────────────────────────────────
    def _get_period_dates(self):
        year = int(self.year_var.get())
        mode = self.mode_var.get()
        if mode == "quarter":
            q = int(self.quarter_var.get()[1])
            start_month = (q - 1) * 3 + 1
            end_month = start_month + 2
            d_from = date(year, start_month, 1)
            if end_month == 12:
                d_to = date(year, 12, 31)
            else:
                d_to = date(year, end_month + 1, 1).replace(day=1)
                from datetime import timedelta
                d_to = d_to - timedelta(days=1)
            label = f"{self.quarter_var.get()} {year}"
            return d_from, d_to, label, q
        elif mode == "month":
            months = ["January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December"]
            m = months.index(self.month_var.get()) + 1
            d_from = date(year, m, 1)
            if m == 12:
                d_to = date(year, 12, 31)
            else:
                from datetime import timedelta
                d_to = date(year, m + 1, 1) - timedelta(days=1)
            q = (m - 1) // 3 + 1
            label = f"{self.month_var.get()} {year}"
            return d_from, d_to, label, q
        else:
            try:
                d_from = datetime.strptime(self.from_var.get(), "%Y-%m-%d").date()
                d_to = datetime.strptime(self.to_var.get(), "%Y-%m-%d").date()
            except ValueError:
                messagebox.showwarning("Invalid Dates",
                    "Use YYYY-MM-DD format for custom dates.")
                return None, None, None, None
            q = (d_from.month - 1) // 3 + 1
            label = f"{d_from} → {d_to}"
            return d_from, d_to, label, q

    # ── Generate report ───────────────────────────────────────
    def _generate(self):
        d_from, d_to, label, quarter = self._get_period_dates()
        if d_from is None:
            return
        self.period_lbl_var.set(f"📅 {label}")
        self._period = {"from": d_from, "to": d_to, "label": label,
                        "quarter": quarter, "year": int(self.year_var.get())}

        # One calculation for the VAT form, the Reports Center and the
        # Claude connector: sales less credit notes AND sales returns,
        # purchases + expense VAT less purchase returns.
        try:
            from modules import report_center as RC
            if not hasattr(self, "adj_vars") or getattr(self, "_adj_period", None) != (d_from, d_to):
                # v6.0: boxes 9, 14, 15 — typed in; box 15 starts from the last refund
                self.adj_vars = {k: tk.StringVar(value="0") for k in ("rc", "rc_nr", "corr", "cbf")}
                self.adj_vars["cbf"].set("%.2f" % RC.previous_credit(d_from.isoformat()))
                self._adj_period = (d_from, d_to)

            def _n(k):
                try:
                    return float(str(self.adj_vars[k].get()).replace(",", "") or 0)
                except ValueError:
                    return 0.0
            self._data = RC.vat_return_data(d_from.isoformat(), d_to.isoformat(),
                                            corrections=_n("corr"), credit_bf=_n("cbf"),
                                            reverse_charge=_n("rc"), rc_not_recoverable=_n("rc_nr"))
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            return
        self._render_report()

    # ── Render the VAT return form ────────────────────────────
    def _render_report(self):
        C = cfg.theme()
        for w in self.body.winfo_children():
            w.destroy()

        d = self._data
        output_vat, input_vat, net = d["output_vat"], d["input_vat"], d["net"]

        # ── Summary cards ─────────────────────────────────────
        cards = tk.Frame(self.body, bg=C["content_bg"])
        cards.pack(fill="x", pady=(0, 16))
        for i in range(3):
            cards.columnconfigure(i, weight=1)

        self._summary_card(cards, 0, "Output VAT (Sales)",
                           f"{output_vat:,.2f}", "📤", C["success"])
        self._summary_card(cards, 1, "Input VAT (Purchases)",
                           f"{input_vat:,.2f}", "📥", C["info"])
        net_color = C["danger"] if net >= 0 else C["success"]
        net_label = "Net VAT Payable" if net >= 0 else "Net VAT Refundable"
        self._summary_card(cards, 2, net_label,
                           f"{abs(net):,.2f}", "💰", net_color)

        # ── VAT Return form (boxes) ───────────────────────────
        form = tk.Frame(self.body, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        form.pack(fill="x")
        fh = tk.Frame(form, bg=C["primary"])
        fh.pack(fill="x")
        tk.Label(fh, text="VAT RETURN  /  الإقرار الضريبي",
                 font=("Segoe UI", 12, "bold"), bg=C["primary"], fg="white",
                 pady=10).pack()
        sections = {"1": ("VAT on Sales and All Other Outputs", "ضريبة المخرجات"),
                    "7": ("VAT on Purchases and All Other Inputs", "ضريبة المدخلات"),
                    "13": ("Net VAT Due", "صافي الضريبة المستحقة")}
        for bx in d["boxes"]:
            if bx["box"] in sections:
                self._section_title(form, C, *sections[bx["box"]])
            st = bx.get("_style") or ""
            self._box_row(form, C, bx["box"], bx["label"], bx["amount"], bx["vat"],
                          None, is_total=st in ("total", "grand"),
                          highlight=st in ("hi", "grand"), adj=bx["adjustment"])

        # v6.0: the boxes the books can't know — typed in, then Recalculate
        adj = tk.Frame(self.body, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        adj.pack(fill="x", pady=(12, 0))
        tk.Label(adj, text="Type in (then Recalculate):", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(side="left", padx=(14, 8), pady=8)
        for key, lbl in (("rc", "Box 9 reverse-charge imports"),
                         ("rc_nr", "…of which NOT recoverable"),
                         ("corr", "Box 14 corrections (±)"),
                         ("cbf", "Box 15 credit brought forward")):
            f = tk.Frame(adj, bg=C["card_bg"]); f.pack(side="left", padx=(0, 10), pady=4)
            tk.Label(f, text=lbl, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
            tk.Entry(f, textvariable=self.adj_vars[key], width=11, justify="right",
                     font=("Segoe UI", 10), relief="solid", bd=1).pack(anchor="w")
        tk.Button(adj, text="↻ Recalculate", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=10, pady=4, cursor="hand2",
                  command=self._generate).pack(side="left", padx=6)

        # Returns & expenses included (so nothing is missed)
        info = tk.Frame(self.body, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        info.pack(fill="x", pady=(12, 0))
        for txt in (
                f"Sales returns deducted (box 1 adjustment): "
                f"{d['sales_returns']['amt']:,.2f}  ·  VAT {d['sales_returns']['vat']:,.2f}",
                f"Purchase returns deducted (box 7 adjustment): "
                f"{d['purchase_returns']['amt']:,.2f}  ·  VAT {d['purchase_returns']['vat']:,.2f}",
                f"Expenses with VAT included in box 7: "
                f"{d['expenses']['amt']:,.2f}  ·  VAT {d['expenses']['vat']:,.2f}",
                f"Out-of-scope sales (not part of the return): {d.get('out_of_scope', 0):,.2f}",
                f"Purchases from suppliers outside KSA with VAT (box 8): "
                f"{d.get('imports', {}).get('amt', 0):,.2f}  ·  VAT {d.get('imports', {}).get('vat', 0):,.2f}"):
            tk.Label(info, text="•  " + txt, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=14, pady=2)

        # Note
        note = tk.Frame(self.body, bg="#FFFBEB")
        note.pack(fill="x", pady=(14, 0))
        msg = ("ℹ️  This is a system-generated summary to assist with your ZATCA VAT "
               "return. Verify figures against source documents before filing. "
               "Returns are filed via the ZATCA portal — monthly if annual turnover "
               "exceeds SAR 40 million, otherwise quarterly.")
        tk.Label(note, text=msg, font=("Segoe UI", 8), bg="#FFFBEB",
                 fg=C["warning"], wraplength=900, justify="left").pack(
                     anchor="w", padx=12, pady=10)

        tk.Frame(self.body, bg=C["content_bg"], height=20).pack()

    def _summary_card(self, parent, col, title, value, icon, color):
        C = cfg.theme()
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.grid(row=0, column=col, sticky="ew",
                  padx=(0, 12) if col < 2 else 0, ipady=4)
        tk.Frame(card, bg=color, height=4).pack(fill="x")
        inner = tk.Frame(card, bg=C["card_bg"])
        inner.pack(fill="x", padx=16, pady=12)
        top = tk.Frame(inner, bg=C["card_bg"])
        top.pack(fill="x")
        tk.Label(top, text=icon, font=("Segoe UI Emoji", 18),
                 bg=C["card_bg"], fg=color).pack(side="left")
        tk.Label(top, text=title, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="right")
        tk.Label(inner, text=f"{value} SAR", font=("Segoe UI", 18, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", pady=(6, 0))

    def _section_title(self, parent, C, title_en, title_ar):
        f = tk.Frame(parent, bg=C["content_bg"])
        f.pack(fill="x", padx=2, pady=(8, 0))
        inner = tk.Frame(f, bg=C["content_bg"])
        inner.pack(fill="x", padx=14, pady=8)
        tk.Label(inner, text=title_en, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="left")
        tk.Label(inner, text=title_ar, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="right")

    def _box_row(self, parent, C, box_no, label, amount, vat, cat_code,
                 is_total=False, highlight=False, adj=0.0):
        bg = C["primary_light"] if highlight else (
            "#F9FAFB" if is_total else C["card_bg"])
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=2, pady=1)

        inner = tk.Frame(row, bg=bg)
        inner.pack(fill="x", padx=16, pady=(8 if is_total else 6))

        # Box number
        num_bg = C["primary"] if (is_total or highlight) else C["border"]
        num_fg = "white" if (is_total or highlight) else C["text_secondary"]
        tk.Label(inner, text=box_no, font=("Segoe UI", 9, "bold"),
                 bg=num_bg, fg=num_fg, width=4).pack(side="left")

        # Label
        tk.Label(inner, text=label,
                 font=("Segoe UI", 10, "bold" if is_total else "normal"),
                 bg=bg, fg=C["text_primary"]).pack(side="left", padx=12)

        # Amount (taxable) + VAT
        vat_lbl = tk.Label(inner, text=f"VAT: {vat:,.2f}",
                          font=("Segoe UI", 9, "bold" if is_total else "normal"),
                          bg=bg, fg=C["info"] if vat else C["text_secondary"])
        vat_lbl.pack(side="right", padx=(16, 0))

        if adj:
            tk.Label(inner, text=f"Adj: {adj:,.2f}", font=("Segoe UI", 9),
                     bg=bg, fg=C["danger"]).pack(side="right", padx=(12, 0))
        amt_lbl = tk.Label(inner, text=f"{amount:,.2f}",
                          font=("Segoe UI", 10, "bold" if is_total else "normal"),
                          bg=bg, fg=C["text_primary"])
        amt_lbl.pack(side="right")

        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=16)

    # ── Save return ───────────────────────────────────────────
    @perm.guard("reports", "approve")
    def _save_return(self):
        if not self._data:
            messagebox.showwarning("Generate First", "Generate a report first.")
            return
        d = self._data
        p = self._period
        output_vat, input_vat, net = d["output_vat"], d["input_vat"], d["net"]

        try:
            existing = db.fetchone(
                "SELECT return_id FROM vat_returns "
                "WHERE period_from=? AND period_to=?",
                (p["from"], p["to"]))
            if existing:
                if not messagebox.askyesno("Overwrite?",
                    "A return for this period already exists. Overwrite it?"):
                    return
                db.execute("DELETE FROM vat_returns WHERE return_id=?",
                           (existing["return_id"],))

            db.execute(
                "INSERT INTO vat_returns "
                "(period_from, period_to, return_year, return_quarter, "
                "total_sales_standard, total_sales_zero, total_sales_exempt, "
                "total_vat_collected, total_purchases, total_vat_paid, "
                "net_vat_payable, return_status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["from"], p["to"], p["year"], p["quarter"],
                 d["standard"]["taxable"], d["zero"]["taxable"],
                 d["exempt"]["taxable"], output_vat,
                 d["purchases"]["taxable"], input_vat, net, "draft"))

            messagebox.showinfo(t("common.success"),
                f"VAT return saved for {p['label']}.\n"
                f"Net VAT {'payable' if net>=0 else 'refundable'}: "
                f"{abs(net):,.2f} SAR")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Export Excel ──────────────────────────────────────────
    @perm.guard("reports", "export")
    def _export_excel(self):
        if not self._data:
            messagebox.showwarning("Generate First", "Generate a report first.")
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from tkinter import filedialog

            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                initialfile=f"VAT_Return_{self._period['label'].replace(' ', '_')}.xlsx")
            if not path:
                return

            d = self._data
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "VAT Return"
            green = PatternFill("solid", fgColor="006C35")
            bold_white = Font(bold=True, color="FFFFFF")
            bold = Font(bold=True)
            ws["A1"] = "VAT RETURN"
            ws["A1"].font = Font(bold=True, size=14)
            ws["A2"] = f"Period: {self._period['label']}"
            ws.append([])
            ws.append(["Box", "Description", "Amount (SAR)", "Adjustment (SAR)", "VAT (SAR)"])
            for c in ws[4]:
                c.fill = green
                c.font = bold_white
            for bx in d["boxes"]:
                ws.append([bx["box"], bx["label"], bx["amount"], bx["adjustment"], bx["vat"]])
                if bx.get("_style") in ("total", "grand"):
                    for c in ws[ws.max_row]:
                        c.font = bold
            ws.append([])
            ws.append(["", "Sales returns deducted", d["sales_returns"]["amt"], "",
                       d["sales_returns"]["vat"]])
            ws.append(["", "Purchase returns deducted", d["purchase_returns"]["amt"], "",
                       d["purchase_returns"]["vat"]])
            ws.append(["", "Expenses with VAT (in box 7)", d["expenses"]["amt"], "",
                       d["expenses"]["vat"]])
            for row in ws.iter_rows(min_row=5, min_col=3, max_col=5):
                for c in row:
                    c.number_format = '#,##0.00'
            ws.column_dimensions["E"].width = 16
            ws.column_dimensions["A"].width = 6
            ws.column_dimensions["B"].width = 38
            ws.column_dimensions["C"].width = 16
            ws.column_dimensions["D"].width = 16

            wb.save(path)
            messagebox.showinfo(t("common.success"), f"Exported:\n{path}")
        except ImportError:
            messagebox.showerror("Error", "pip install openpyxl")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    @perm.guard("reports", "print")
    def _print_pdf(self):
        """Print / export the VAT return as a PDF."""
        if not self._data:
            messagebox.showwarning("Generate First", "Generate a report first.")
            return
        d = self._data
        headers = ["Box", "Description", "Amount (SAR)", "Adjustment", "VAT (SAR)"]
        rows = [[bx["box"], bx["label"], f"{bx['amount']:,.2f}",
                 f"{bx['adjustment']:,.2f}", f"{bx['vat']:,.2f}"] for bx in d["boxes"]]
        try:
            from modules.report_export import export_pdf
            company = db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
            export_pdf(self.frame, "VAT_Return", headers, rows,
                       title="VAT Return",
                       subtitle=f"Period: {self._period['label']}",
                       company=company,
                       col_align=["center", "left", "right", "right", "right"])
        except ImportError:
            messagebox.showerror("Missing Library", "pip install reportlab")
        except Exception as e:
            messagebox.showerror("Print Error", str(e))
