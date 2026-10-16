# ============================================================
# DayBill ERP - Financial Reports (Cash Book · Bank Book · Cash Flow)
# ------------------------------------------------------------
# Reads the JOURNAL (the single source the posting engine writes to)
# so figures always agree with the ledgers.
#   Cash Book  : every movement on the default Cash account
#   Bank Book  : every movement on the default Bank account
#   Cash Flow  : Operating / Investing / Financing summary for cash+bank
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import account_defaults as ad


def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


class FinancialReportsView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._topbar(C)
        self.nb = ttk.Notebook(self.frame)
        self.nb.pack(fill="both", expand=True, padx=24, pady=12)
        self.cash_tab = tk.Frame(self.nb, bg=C["card_bg"])
        self.bank_tab = tk.Frame(self.nb, bg=C["card_bg"])
        self.flow_tab = tk.Frame(self.nb, bg=C["card_bg"])
        self.nb.add(self.cash_tab, text="  💵  Cash Book  ")
        self.nb.add(self.bank_tab, text="  🏦  Bank Book  ")
        self.nb.add(self.flow_tab, text="  🔄  Cash Flow  ")
        self.cash_tree = self._book_table(self.cash_tab)
        self.bank_tree = self._book_table(self.bank_tab)
        self._flow_holder = tk.Frame(self.flow_tab, bg=C["card_bg"])
        self._flow_holder.pack(fill="both", expand=True, padx=16, pady=12)
        self._load()

    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="📒  Financial Reports", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        today = date.today()
        self.from_var = tk.StringVar(value=today.replace(day=1).strftime("%Y-%m-%d"))
        self.to_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        for lbl, var in [("From", self.from_var), ("To", self.to_var)]:
            tk.Label(bar, text=lbl, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(12, 4))
            tk.Entry(bar, textvariable=var, width=11, font=("Segoe UI", 10),
                     relief="solid", bd=1).pack(side="left")
        tk.Button(bar, text="🔄 Run", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._load).pack(side="left", padx=(10, 0))
        tk.Button(bar, text="🖨  Print", font=("Segoe UI", 9, "bold"), bg="#16A085",
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._export_pdf).pack(side="right")
        tk.Button(bar, text="📥  Excel", font=("Segoe UI", 9, "bold"), bg="#2E86AB",
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._export_excel).pack(side="right", padx=(0, 8))

    def _active_book(self):
        """Return (tree, title, name) for the active Cash/Bank tab, or None
        if the Cash-Flow summary tab is showing (nothing tabular to export)."""
        try:
            idx = self.nb.index(self.nb.select())
        except Exception:
            idx = 0
        if idx == 1:
            return self.bank_tree, "Bank Book", "BankBook"
        if idx == 2:
            return None, None, None
        return self.cash_tree, "Cash Book", "CashBook"

    def _book_headers(self):
        return ["Date", "Voucher", "Narration", "Receipt (Dr)", "Payment (Cr)", "Balance"]

    def _book_subtitle(self):
        return "From %s to %s" % (self.from_var.get(), self.to_var.get())

    def _export_excel(self):
        tree, title, name = self._active_book()
        if tree is None:
            messagebox.showinfo("Reports", "Open the Cash Book or Bank Book tab to export.")
            return
        if not tree.get_children():
            messagebox.showinfo("Reports", "Run the report first.")
            return
        from modules.doc_actions import export_tree_excel
        export_tree_excel(self.frame, tree, name, self._book_headers(),
                          title=title, summary=self._book_subtitle())

    def _export_pdf(self):
        tree, title, name = self._active_book()
        if tree is None:
            messagebox.showinfo("Reports", "Open the Cash Book or Bank Book tab to print.")
            return
        if not tree.get_children():
            messagebox.showinfo("Reports", "Run the report first.")
            return
        from modules.doc_actions import export_tree_pdf
        export_tree_pdf(self.frame, tree, name, self._book_headers(),
                        title=title, subtitle=self._book_subtitle(),
                        col_align=["center", "left", "left", "right", "right", "right"])

    def _book_table(self, parent):
        C = self.C
        head = tk.Frame(parent, bg=C["card_bg"])
        head.pack(fill="x", padx=16, pady=(12, 0))
        self_open = tk.StringVar()
        setattr(self, f"_open_{id(parent)}", self_open)
        wrap = tk.Frame(parent, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=12)
        cols = ("date", "voucher", "narration", "in", "out", "balance")
        tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for cid, txt, w, a in [("date", "Date", 95, "center"),
                               ("voucher", "Voucher", 120, "w"),
                               ("narration", "Narration", 320, "w"),
                               ("in", "Receipt (Dr)", 110, "e"),
                               ("out", "Payment (Cr)", 110, "e"),
                               ("balance", "Balance", 120, "e")]:
            tree.heading(cid, text=txt)
            tree.column(cid, width=w, anchor=a)
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        return tree

    def _load(self):
        self._fill_book(self.cash_tree, ad.cash())
        self._fill_book(self.bank_tree, ad.bank())
        self._fill_flow()

    def _fill_book(self, tree, account_id):
        for i in tree.get_children():
            tree.delete(i)
        if not account_id:
            return
        try:
            opening = float(db.execute_scalar(
                "SELECT COALESCE(SUM(jl.debit - jl.credit),0) FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE jl.account_id=? AND je.entry_date < ? AND je.is_posted=1",
                (account_id, self.from_var.get())) or 0)
            rows = db.fetchall(
                "SELECT je.entry_date, je.journal_number, je.description_en, "
                "jl.debit, jl.credit FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE jl.account_id=? AND je.entry_date BETWEEN ? AND ? "
                "AND je.is_posted=1 ORDER BY je.entry_date, je.journal_id",
                (account_id, self.from_var.get(), self.to_var.get())) or []
        except Exception as e:
            messagebox.showerror("Reports", str(e)[:160])
            return
        bal = opening
        tree.insert("", "end", values=("", "", "Opening balance", "", "", money(bal)))
        for r in rows:
            bal += float(r["debit"] or 0) - float(r["credit"] or 0)
            d = r["entry_date"]
            dtxt = d.strftime("%d/%m/%y") if hasattr(d, "strftime") else str(d)[:10]
            tree.insert("", "end", values=(
                dtxt, r["journal_number"] or "", r["description_en"] or "",
                money(r["debit"]) if r["debit"] else "",
                money(r["credit"]) if r["credit"] else "", money(bal)))
        tree.insert("", "end", values=("", "", "▶ Closing balance", "", "", money(bal)))

    def _fill_flow(self):
        C = self.C
        for w in self._flow_holder.winfo_children():
            w.destroy()
        cash_ids = [a for a in (ad.cash(), ad.bank(), ad.savings(), ad.petty_cash())
                    if a]
        if not cash_ids:
            tk.Label(self._flow_holder, text="No cash/bank accounts configured.",
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(pady=20)
            return
        ph = ",".join("?" for _ in cash_ids)

        def net_for(types_):
            tph = ",".join("?" for _ in types_)
            try:
                return float(db.execute_scalar(
                    f"SELECT COALESCE(SUM(jl.debit - jl.credit),0) "
                    f"FROM journal_lines jl JOIN journal_entries je "
                    f"ON je.journal_id=jl.journal_id "
                    f"WHERE jl.account_id IN ({ph}) "
                    f"AND je.source_type IN ({tph}) "
                    f"AND je.entry_date BETWEEN ? AND ? AND je.is_posted=1",
                    (*cash_ids, *types_, self.from_var.get(), self.to_var.get())) or 0)
            except Exception:
                return 0.0

        # opening cash
        try:
            opening = float(db.execute_scalar(
                f"SELECT COALESCE(SUM(jl.debit - jl.credit),0) FROM journal_lines jl "
                f"JOIN journal_entries je ON je.journal_id=jl.journal_id "
                f"WHERE jl.account_id IN ({ph}) AND je.entry_date < ? "
                f"AND je.is_posted=1", (*cash_ids, self.from_var.get())) or 0)
        except Exception:
            opening = 0.0

        operating = net_for(["sale", "pos_sale", "receipt", "purchase", "payment",
                             "expense", "sales_return", "purchase_return"])
        investing = net_for(["asset_purchase", "asset_sale", "adjustment"])
        financing = net_for(["salary", "salary_payment", "bank_transfer",
                            "capital", "loan"])
        net = operating + investing + financing
        closing = opening + net

        def section(title, value, color):
            row = tk.Frame(self._flow_holder, bg=C["card_bg"])
            row.pack(fill="x", pady=6)
            tk.Label(row, text=title, font=("Segoe UI", 12, "bold"), bg=C["card_bg"],
                     fg=color).pack(side="left")
            tk.Label(row, text=money(value), font=("Segoe UI", 13, "bold"),
                     bg=C["card_bg"], fg=color).pack(side="right")

        tk.Label(self._flow_holder, text="Cash Flow Statement",
                 font=("Segoe UI", 14, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", pady=(0, 10))
        section("Opening cash & bank", opening, C["text_secondary"])
        tk.Frame(self._flow_holder, bg=C["border"], height=1).pack(fill="x", pady=6)
        section("Operating activities", operating, C["text_primary"])
        section("Investing activities", investing, C["text_primary"])
        section("Financing activities", financing, C["text_primary"])
        tk.Frame(self._flow_holder, bg=C["border"], height=1).pack(fill="x", pady=6)
        section("Net change in cash", net,
                C["accent"] if net >= 0 else C["danger"])
        section("Closing cash & bank", closing, C["primary"])
        tk.Label(self._flow_holder,
                 text="Activities are grouped from each journal's source type. "
                      "Verify mappings match your chart of accounts.",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                 wraplength=600, justify="left").pack(anchor="w", pady=(14, 0))
