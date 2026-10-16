# ============================================================
# DayBill ERP - Account Ledger Browser
# (Converted from BillPOS PHP: ledger.php)
# ------------------------------------------------------------
# Pick any account (party sub-accounts 1200-xxxx / 2100-xxxx
# included, so customer & supplier ledgers work too), set a date
# range, and see: opening balance, every posted journal line with
# a running balance, and the closing balance marked Dr/Cr.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


class LedgerView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._accounts = self._load_accounts()
        self._topbar(C)
        self._summary(C)
        self._table(C)
        if self._accounts:
            # default to the Cash account if present
            cash = next((a for a in self._accounts
                         if a["account_code"] in ("1100", "100001", "1001")),
                        self._accounts[0])
            self.acct_var.set(self._label(cash))
            self._load()

    # ── data helpers ──────────────────────────────────────────
    def _load_accounts(self):
        try:
            return db.fetchall(
                "SELECT account_id, account_code, account_name_en FROM accounts "
                "WHERE is_active=1 ORDER BY account_code") or []
        except Exception:
            return []

    def _label(self, a):
        return f"{a['account_code']} · {a['account_name_en']}"

    def _selected_code(self):
        return (self.acct_var.get() or "").split(" · ")[0]

    # ── UI ────────────────────────────────────────────────────
    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="📒  Account Ledger", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        f = tk.Frame(self.frame, bg=C["content_bg"])
        f.pack(fill="x", padx=24, pady=(12, 0))
        tk.Label(f, text="Account", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.acct_var = tk.StringVar()
        vals = [self._label(a) for a in self._accounts]
        self.acct_combo = ttk.Combobox(f, textvariable=self.acct_var, values=vals,
                                       width=38)
        self.acct_combo.pack(side="left", padx=(0, 10))
        # type-to-filter: narrow the list as the user types
        self.acct_combo.bind("<KeyRelease>", self._filter_accounts)
        self.acct_combo.bind("<<ComboboxSelected>>", lambda e: self._load())

        today = date.today()
        self.from_var = tk.StringVar(value=today.replace(day=1).strftime("%Y-%m-%d"))
        self.to_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        tk.Label(f, text="From", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        tk.Entry(f, textvariable=self.from_var, width=11, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 10))
        tk.Label(f, text="To", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        tk.Entry(f, textvariable=self.to_var, width=11, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 10))
        tk.Button(f, text="🔍 View", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  command=self._load).pack(side="left")
        tk.Button(f, text="🖨  Print", font=("Segoe UI", 9, "bold"),
                  bg="#16A085", fg="white", relief="flat", padx=14, pady=5,
                  cursor="hand2", command=self._export_pdf).pack(side="right")
        tk.Button(f, text="📥  Excel", font=("Segoe UI", 9, "bold"),
                  bg="#2E86AB", fg="white", relief="flat", padx=14, pady=5,
                  cursor="hand2",
                  command=self._export_excel).pack(side="right", padx=(0, 8))

    def _ledger_headers(self):
        return ["Date", "Voucher", "Type", "Narration", "Debit", "Credit", "Balance"]

    def _ledger_meta(self):
        title = self.title_var.get() if hasattr(self, "title_var") else "Account Ledger"
        subtitle = "From %s to %s" % (self.from_var.get(), self.to_var.get())
        summary = None
        try:
            summary = [("Opening", self.opening_var.get()),
                       ("Debits / Credits", self.drcr_var.get()),
                       ("Closing", self.closing_var.get())]
        except Exception:
            pass
        return title, subtitle, summary

    def _export_excel(self):
        if not self.tree.get_children():
            messagebox.showinfo("Ledger", "Load a ledger first (pick an account, View).")
            return
        title, subtitle, summary = self._ledger_meta()
        from modules.doc_actions import export_tree_excel
        export_tree_excel(self.frame, self.tree, "Ledger", self._ledger_headers(),
                          title=title, summary=summary)

    def _export_pdf(self):
        if not self.tree.get_children():
            messagebox.showinfo("Ledger", "Load a ledger first (pick an account, View).")
            return
        title, subtitle, summary = self._ledger_meta()
        from modules.doc_actions import export_tree_pdf
        export_tree_pdf(self.frame, self.tree, "Ledger", self._ledger_headers(),
                        title=title, subtitle=subtitle, summary=summary,
                        col_align=["center", "center", "center", "left",
                                   "right", "right", "right"])

    def _filter_accounts(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        txt = self.acct_var.get().lower()
        vals = [self._label(a) for a in self._accounts
                if txt in self._label(a).lower()] if txt else \
               [self._label(a) for a in self._accounts]
        self.acct_combo["values"] = vals

    def _summary(self, C):
        card = tk.Frame(self.frame, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="x", padx=24, pady=12)
        inner = tk.Frame(card, bg=C["card_bg"])
        inner.pack(fill="x", padx=16, pady=10)
        self.title_var = tk.StringVar(value="—")
        tk.Label(inner, textvariable=self.title_var, font=("Segoe UI", 12, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w")
        row = tk.Frame(inner, bg=C["card_bg"]); row.pack(fill="x", pady=(6, 0))

        def cell(label, var, color):
            f = tk.Frame(row, bg=C["card_bg"])
            f.pack(side="left", padx=(0, 28))
            tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
            tk.Label(f, textvariable=var, font=("Segoe UI", 13, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w")

        self.opening_var = tk.StringVar(value="0.00")
        self.drcr_var = tk.StringVar(value="0.00 / 0.00")
        self.closing_var = tk.StringVar(value="0.00")
        cell("Opening", self.opening_var, C["text_primary"])
        cell("Debits / Credits", self.drcr_var, C["info"])
        cell("Closing balance", self.closing_var, C["primary"])

    def _table(self, C):
        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        cols = ("date", "voucher", "type", "narration", "debit", "credit", "balance")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        heads = [("date", "Date", 85, "center"),
                 ("voucher", "Voucher", 100, "center"),
                 ("type", "Type", 100, "center"),
                 ("narration", "Narration", 280, "w"),
                 ("debit", "Debit", 100, "e"),
                 ("credit", "Credit", 100, "e"),
                 ("balance", "Balance", 110, "e")]
        for cid, txt, w, anc in heads:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=anc)
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

    # ── load ledger (ported queries, SQL Server) ──────────────
    def _load(self):
        code = self._selected_code()
        if not code:
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        frm, to = self.from_var.get(), self.to_var.get()
        try:
            opening = db.execute_scalar(
                "SELECT COALESCE(SUM(jl.debit - jl.credit), 0) "
                "FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id = jl.journal_id "
                "JOIN accounts a ON a.account_id = jl.account_id "
                "WHERE a.account_code = ? AND je.entry_date < ? AND je.is_posted = 1",
                (code, frm)) or 0
            rows = db.fetchall(
                "SELECT je.entry_date, je.journal_number, je.source_type, "
                "je.description_en, jl.debit, jl.credit "
                "FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id = jl.journal_id "
                "JOIN accounts a ON a.account_id = jl.account_id "
                "WHERE a.account_code = ? AND je.entry_date BETWEEN ? AND ? "
                "AND je.is_posted = 1 "
                "ORDER BY je.entry_date, je.journal_id",
                (code, frm, to)) or []
        except Exception as e:
            messagebox.showerror("Ledger", str(e)[:200])
            return

        opening = float(opening)
        dr_t = sum(float(r["debit"] or 0) for r in rows)
        cr_t = sum(float(r["credit"] or 0) for r in rows)
        closing = opening + dr_t - cr_t

        self.title_var.set(self.acct_var.get())
        self.opening_var.set(money(opening))
        self.drcr_var.set(f"{money(dr_t)} / {money(cr_t)}")
        self.closing_var.set(f"{money(abs(closing))} {'Dr' if closing >= 0 else 'Cr'}")

        self.tree.insert("", "end", values=("", "", "", "Opening balance",
                                            "", "", money(opening)))
        run = opening
        for r in rows:
            run += float(r["debit"] or 0) - float(r["credit"] or 0)
            d = r["entry_date"]
            dtxt = d.strftime("%d/%m/%y") if hasattr(d, "strftime") else str(d)[:10]
            self.tree.insert("", "end", values=(
                dtxt, r["journal_number"],
                (r["source_type"] or "").replace("_", " "),
                r["description_en"] or "",
                money(r["debit"]) if float(r["debit"] or 0) else "",
                money(r["credit"]) if float(r["credit"] or 0) else "",
                money(run)))
        if not rows:
            self.tree.insert("", "end", values=("", "", "",
                                                "No entries in this range.",
                                                "", "", ""))
