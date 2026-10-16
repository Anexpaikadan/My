# ============================================================
# DayBill ERP - Accounting Module UI
# Chart of Accounts | Journal Entries | Trial Balance | P&L | Balance Sheet
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db
from modules import accounting_engine as acc
from modules import permissions as perm


class AccountingView:
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
        tk.Label(bar, text="📒  Accounting", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

    # ── Shared Export / Print helpers ─────────────────────────
    def _exp_btns(self, bar, C, get_data_fn):
        """Add Excel + Print buttons to a report's toolbar."""
        tk.Button(bar, text="🖨 Print", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: get_data_fn(mode="pdf")).pack(side="right")
        tk.Button(bar, text="📥 Export Excel", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: get_data_fn(mode="excel")).pack(side="right", padx=(0, 8))

    @perm.guard("accounts", "export")
    def _export_report(self, name, title, headers, rows, mode="excel", summary=None):
        if not rows:
            messagebox.showinfo("Nothing to export", "Generate the report first.")
            return
        try:
            if mode == "pdf":
                from modules.report_export import export_pdf
                export_pdf(self.frame, name, headers, rows, title=title, summary=summary)
            else:
                from modules.report_export import export_excel
                export_excel(self.frame, name, headers, rows, title=title, summary=summary)
        except ImportError:
            messagebox.showerror("Missing Library",
                "pip install openpyxl reportlab")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _tabs(self, C):
        style = ttk.Style()
        style.configure("AC.TNotebook", background=C["content_bg"], borderwidth=0)
        style.configure("AC.TNotebook.Tab", font=("Segoe UI", 10), padding=(14, 8))
        nb = ttk.Notebook(self.frame, style="AC.TNotebook")
        nb.pack(fill="both", expand=True, padx=24, pady=14)

        self.t_coa = tk.Frame(nb, bg=C["content_bg"])
        self.t_jrn = tk.Frame(nb, bg=C["content_bg"])
        self.t_led = tk.Frame(nb, bg=C["content_bg"])
        self.t_tb = tk.Frame(nb, bg=C["content_bg"])
        self.t_pl = tk.Frame(nb, bg=C["content_bg"])
        self.t_bs = tk.Frame(nb, bg=C["content_bg"])
        nb.add(self.t_coa, text="  📋  Chart of Accounts  ")
        nb.add(self.t_jrn, text="  📝  Journal Entries  ")
        nb.add(self.t_led, text="  📖  Ledger  ")
        nb.add(self.t_tb, text="  ⚖️  Trial Balance  ")
        nb.add(self.t_pl, text="  📈  Profit & Loss  ")
        nb.add(self.t_bs, text="  🏦  Balance Sheet  ")

        self._build_coa(self.t_coa, C)
        self._build_journals(self.t_jrn, C)
        self._build_ledger(self.t_led, C)
        self._build_tb(self.t_tb, C)
        self._build_pl(self.t_pl, C)
        self._build_bs(self.t_bs, C)

    # ── Chart of Accounts ─────────────────────────────────────
    def _build_coa(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(10, 8))
        tk.Button(bar, text="＋ New Account", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=7,
                  cursor="hand2", command=self._new_account).pack(side="right")
        tk.Button(bar, text="✏ Edit", font=("Segoe UI", 10),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._edit_account).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="🗑 Deactivate", font=("Segoe UI", 10),
                  bg="#FEF2F2", fg=C["danger"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._deactivate_account).pack(side="right", padx=(0, 8))
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("code", "name_en", "name_ar", "type")
        h = {"code": ("Code", 90, "center"), "name_en": ("Name (EN)", 240, "w"),
             "name_ar": ("الاسم", 220, "e"), "type": ("Type", 120, "center")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.coa_tree = ttk.Treeview(card, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=self.coa_tree.yview)
        for col in cols:
            lbl, w, a = h[col]; self.coa_tree.heading(col, text=lbl); self.coa_tree.column(col, width=w, anchor=a)
        self.coa_tree.pack(fill="both", expand=True)
        self.coa_tree.bind("<Double-1>", lambda e: self._edit_account())
        self._load_coa()

    def _load_coa(self):
        self.coa_tree.delete(*self.coa_tree.get_children())
        try:
            rows = db.fetchall("SELECT account_id, account_code, account_name_en, "
                               "account_name_ar, "
                               "account_type FROM accounts WHERE is_active=1 ORDER BY account_code")
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return
        for r in rows:
            self.coa_tree.insert("", "end", iid=str(r["account_id"]), values=(
                r["account_code"], r["account_name_en"], r.get("account_name_ar", ""),
                r["account_type"].title()))

    @perm.guard("accounts", "add")
    def _new_account(self):
        AccountForm(self.frame, self._load_coa)

    def _sel_account(self):
        sel = self.coa_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an account first.")
            return None
        return int(sel[0])

    @perm.guard("accounts", "edit")
    def _edit_account(self):
        aid = self._sel_account()
        if aid:
            AccountForm(self.frame, self._load_coa, account_id=aid)

    @perm.guard("accounts", "delete")
    def _deactivate_account(self):
        """Accounts with ledger history can't be hard-deleted (journal_lines
        reference them) — deactivating hides them everywhere instead."""
        aid = self._sel_account()
        if not aid:
            return
        vals = self.coa_tree.item(str(aid))["values"]
        used = 0
        try:
            row = db.fetchone("SELECT COUNT(*) AS n FROM journal_lines "
                              "WHERE account_id=?", (aid,))
            used = int((row or {}).get("n", 0) or 0)
        except Exception:
            pass
        msg = (f"Deactivate account {vals[0]} — {vals[1]}?"
               if not used else
               f"Account {vals[0]} — {vals[1]} has {used} ledger line(s), "
               f"so it will be deactivated (hidden), not deleted, to keep "
               f"the books intact.\n\nContinue?")
        if not messagebox.askyesno("Deactivate Account", msg):
            return
        try:
            from modules.doc_actions import audit
            db.execute("UPDATE accounts SET is_active=0 WHERE account_id=?", (aid,))
            audit("deactivate", "account", aid, str(vals[0]))
            self._load_coa()
        except Exception as e:
            messagebox.showerror("Deactivate", str(e)[:300])

    # ── Journal Entries ───────────────────────────────────────
    def _build_journals(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(10, 8))
        tk.Button(bar, text="＋ New Journal Entry", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=7,
                  cursor="hand2", command=self._new_journal).pack(side="right")
        tk.Button(bar, text="🗑 Delete", font=("Segoe UI", 10),
                  bg="#FEF2F2", fg=C["danger"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=self._delete_journal).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="🔄 Refresh", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=12, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load_journals).pack(side="right", padx=8)
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("num", "date", "desc", "source", "debit", "credit", "status")
        h = {"num": ("Journal #", 120, "center"), "date": ("Date", 100, "center"),
             "desc": ("Description", 240, "w"), "source": ("Source", 90, "center"),
             "debit": ("Debit", 110, "e"), "credit": ("Credit", 110, "e"),
             "status": ("Status", 80, "center")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.jrn_tree = ttk.Treeview(card, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=self.jrn_tree.yview)
        for col in cols:
            lbl, w, a = h[col]; self.jrn_tree.heading(col, text=lbl); self.jrn_tree.column(col, width=w, anchor=a)
        self.jrn_tree.pack(fill="both", expand=True)
        self._load_journals()

    def _load_journals(self):
        self.jrn_tree.delete(*self.jrn_tree.get_children())
        try:
            rows = db.fetchall("SELECT journal_id, journal_number, entry_date, "
                               "description_en, source_type, "
                               "total_debit, total_credit, is_posted FROM journal_entries "
                               "ORDER BY entry_date DESC, journal_id DESC")
        except Exception:
            rows = []
        for r in rows:
            self.jrn_tree.insert("", "end", iid=str(r["journal_id"]), values=(
                r["journal_number"], str(r.get("entry_date", "")),
                r.get("description_en", "") or "", r.get("source_type", ""),
                f"{float(r['total_debit']):,.2f}", f"{float(r['total_credit']):,.2f}",
                "✅ Posted" if r.get("is_posted") else "📝 Draft"))

    @perm.guard("journal", "add")
    def _new_journal(self):
        JournalForm(self.frame, self._load_journals)

    @perm.guard("journal", "delete")
    def _delete_journal(self):
        """Delete a manual journal entry (lines cascade). Journals that a
        document posted automatically are protected — delete the source
        document instead, and its journal goes with it."""
        sel = self.jrn_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a journal entry first.")
            return
        jid = int(sel[0])
        vals = self.jrn_tree.item(sel[0])["values"]
        src = str(vals[3] or "").lower()
        if src and src != "manual":
            messagebox.showwarning(
                "Delete Journal Entry",
                f"{vals[0]} was posted automatically by a "
                f"{src.replace('_', ' ')} document.\n\nDelete the source "
                "document instead — its journal will be removed with it.")
            return
        warn = f"Delete journal entry {vals[0]}?"
        if "Posted" in str(vals[6]):
            warn = (f"{vals[0]} is POSTED — deleting it changes account "
                    f"balances (Trial Balance, P&L, Balance Sheet).\n\n"
                    f"Delete anyway?")
        if not messagebox.askyesno("Delete Journal Entry", warn):
            return
        try:
            from modules.doc_actions import audit
            db.execute("DELETE FROM journal_entries WHERE journal_id=?", (jid,))
            audit("delete", "journal_entry", jid, str(vals[0]))
            self._load_journals()
        except Exception as e:
            messagebox.showerror("Delete Journal Entry", str(e)[:300])

    # ── Ledger ────────────────────────────────────────────────
    def _build_ledger(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"]); bar.pack(fill="x", pady=(10, 8))
        tk.Label(bar, text="Account:", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        try:
            self._led_accounts = db.fetchall(
                "SELECT account_id, account_code, account_name_en FROM accounts "
                "WHERE is_active=1 ORDER BY account_code")
        except Exception:
            self._led_accounts = []
        self.led_acct_var = tk.StringVar()
        self.led_cb = ttk.Combobox(bar, textvariable=self.led_acct_var,
                                   values=[f"{a['account_code']} — {a['account_name_en']}"
                                           for a in self._led_accounts],
                                   font=("Segoe UI", 9), width=32, state="readonly")
        self.led_cb.pack(side="left", padx=6)
        tk.Label(bar, text="From:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(10, 0))
        self.led_from = tk.StringVar(value=cfg.fiscal_year_bounds()[0].strftime("%Y-%m-%d"))
        _lf = tk.Entry(bar, textvariable=self.led_from, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1)
        _lf.pack(side="left", padx=4)
        tk.Label(bar, text="To:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.led_to = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        _lt = tk.Entry(bar, textvariable=self.led_to, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1)
        _lt.pack(side="left", padx=4)
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(_lf, self.led_from)
            attach_datepicker(_lt, self.led_to)
        except Exception:
            pass
        tk.Button(bar, text="🔍 Generate", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._run_ledger).pack(side="left", padx=6)
        self._exp_btns(bar, C,
            lambda mode="excel": self._export_report("Ledger", "General Ledger",
                ["Date", "Journal #", "Description", "Debit", "Credit", "Balance"],
                getattr(self, "_led_rows", []), mode=mode))

        # Summary bar
        self.led_summary = tk.Frame(parent, bg=C["content_bg"])
        self.led_summary.pack(fill="x", pady=(0, 8))

        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("date", "journal", "desc", "debit", "credit", "balance")
        h = {"date": ("Date", 100, "center"), "journal": ("Journal #", 120, "center"),
             "desc": ("Description", 260, "w"), "debit": ("Debit", 110, "e"),
             "credit": ("Credit", 110, "e"), "balance": ("Balance", 120, "e")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.led_tree = ttk.Treeview(card, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=self.led_tree.yview)
        for col in cols:
            lbl, w, a = h[col]
            self.led_tree.heading(col, text=lbl); self.led_tree.column(col, width=w, anchor=a)
        self.led_tree.pack(fill="both", expand=True)
        self.led_tree.tag_configure("opening", background="#FEF9E7")
        self.led_tree.tag_configure("closing", background="#E8F5EE")

    def _run_ledger(self):
        C = cfg.theme()
        idx = self.led_cb.current()
        if idx < 0:
            messagebox.showwarning("Select", "Choose an account."); return
        acct = self._led_accounts[idx]
        try:
            gl = acc.general_ledger(db, acct["account_id"],
                                    self.led_from.get(), self.led_to.get())
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return
        if not gl:
            return

        # summary cards
        for w in self.led_summary.winfo_children():
            w.destroy()
        for icon, label, val, color in [
            ("📥", "Opening Balance", gl["opening"], C["info"]),
            ("➕", "Total Debit", gl["total_debit"], C["primary"]),
            ("➖", "Total Credit", gl["total_credit"], C["warning"]),
            ("💰", "Closing Balance", gl["closing"], C["success"])]:
            cd = tk.Frame(self.led_summary, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1)
            cd.pack(side="left", padx=(0, 10), ipadx=12, ipady=4)
            tk.Label(cd, text=f"{icon} {label}", font=("Segoe UI", 8),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(cd, text=f"{val:,.2f}", font=("Segoe UI", 14, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w", padx=8, pady=(0, 6))

        # rows
        self.led_tree.delete(*self.led_tree.get_children())
        self._led_rows = []
        self.led_tree.insert("", "end", values=(
            "", "", "Opening Balance", "", "", f"{gl['opening']:,.2f}"), tags=("opening",))
        self._led_rows.append(["", "", "Opening Balance", "", "", f"{gl['opening']:,.2f}"])
        for e in gl["entries"]:
            vals = (e["date"], e["journal_number"], e["description"],
                    f"{e['debit']:,.2f}" if e["debit"] else "",
                    f"{e['credit']:,.2f}" if e["credit"] else "",
                    f"{e['balance']:,.2f}")
            self.led_tree.insert("", "end", values=vals)
            self._led_rows.append(list(vals))
        self.led_tree.insert("", "end", values=(
            "", "", "Closing Balance",
            f"{gl['total_debit']:,.2f}", f"{gl['total_credit']:,.2f}",
            f"{gl['closing']:,.2f}"), tags=("closing",))
        self._led_rows.append(["", "", "Closing Balance",
            f"{gl['total_debit']:,.2f}", f"{gl['total_credit']:,.2f}",
            f"{gl['closing']:,.2f}"])

    # ── Trial Balance ─────────────────────────────────────────
    def _build_tb(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"]); bar.pack(fill="x", pady=(10, 8))
        tk.Label(bar, text="As of:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.tb_date = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        _tbd = tk.Entry(bar, textvariable=self.tb_date, font=("Segoe UI", 9), width=12,
                 relief="solid", bd=1)
        _tbd.pack(side="left", padx=6)
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(_tbd, self.tb_date)
        except Exception:
            pass
        tk.Button(bar, text="🔍 Generate", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._run_tb).pack(side="left")
        self._exp_btns(bar, C,
            lambda mode="excel": self._export_report("Trial_Balance", "Trial Balance",
                ["Code", "Account", "Debit", "Credit"],
                getattr(self, "_tb_rows", []), mode=mode))
        h = {"code": ("Code", 90, "center"), "name": ("Account", 320, "w"),
             "debit": ("Debit", 150, "e"), "credit": ("Credit", 150, "e")}
        # FIX: `card` and `cols` were referenced but never created, which
        # crashed the Trial Balance tab and with it the entire Accounting
        # screen on open.
        cols = ("code", "name", "debit", "credit")
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.tb_tree = ttk.Treeview(card, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=self.tb_tree.yview)
        for col in cols:
            lbl, w, a = h[col]; self.tb_tree.heading(col, text=lbl); self.tb_tree.column(col, width=w, anchor=a)
        self.tb_tree.pack(fill="both", expand=True)
        self.tb_tree.tag_configure("total", background="#E8F5EE")
        self._run_tb()

    def _run_tb(self):
        self.tb_tree.delete(*self.tb_tree.get_children())
        try:
            rows = acc.trial_balance(db, self.tb_date.get())
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return
        td = tc = 0.0
        self._tb_rows = []
        for r in rows:
            td += r["debit"]; tc += r["credit"]
            vals = (r["account_code"], r["account_name_en"],
                    f"{r['debit']:,.2f}" if r["debit"] else "",
                    f"{r['credit']:,.2f}" if r["credit"] else "")
            self.tb_tree.insert("", "end", values=vals)
            self._tb_rows.append(list(vals))
        self.tb_tree.insert("", "end", values=("", "TOTAL", f"{td:,.2f}", f"{tc:,.2f}"), tags=("total",))
        self._tb_rows.append(["", "TOTAL", f"{td:,.2f}", f"{tc:,.2f}"])

    # ── P&L ───────────────────────────────────────────────────
    def _build_pl(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"]); bar.pack(fill="x", pady=(10, 8))
        tk.Label(bar, text="From:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.pl_from = tk.StringVar(value=cfg.fiscal_year_bounds()[0].strftime("%Y-%m-%d"))
        _plf = tk.Entry(bar, textvariable=self.pl_from, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1)
        _plf.pack(side="left", padx=6)
        tk.Label(bar, text="To:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.pl_to = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        _plt = tk.Entry(bar, textvariable=self.pl_to, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1)
        _plt.pack(side="left", padx=6)
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(_plf, self.pl_from); attach_datepicker(_plt, self.pl_to)
        except Exception:
            pass
        tk.Button(bar, text="🔍 Generate", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._run_pl).pack(side="left")
        self._exp_btns(bar, C,
            lambda mode="excel": self._export_report("Profit_and_Loss", "Profit & Loss",
                ["Type", "Code", "Account", "Amount"],
                getattr(self, "_pl_rows", []), mode=mode))
        self.pl_body = tk.Frame(parent, bg=C["content_bg"]); self.pl_body.pack(fill="both", expand=True)
        self._run_pl()

    def _run_pl(self):
        C = cfg.theme()
        for w in self.pl_body.winfo_children():
            w.destroy()
        try:
            data = acc.profit_and_loss(db, self.pl_from.get(), self.pl_to.get())
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return

        # build export rows
        self._pl_rows = []
        for r in data["revenue"]:
            self._pl_rows.append(["Revenue", r["code"], r["name"], f"{r['amount']:,.2f}"])
        self._pl_rows.append(["", "", "Total Revenue", f"{data['total_revenue']:,.2f}"])
        for r in data["expenses"]:
            self._pl_rows.append(["Expense", r["code"], r["name"], f"{r['amount']:,.2f}"])
        self._pl_rows.append(["", "", "Total Expenses", f"{data['total_expenses']:,.2f}"])
        self._pl_rows.append(["", "", "NET PROFIT/LOSS", f"{data['net_profit']:,.2f}"])

        def section(title, rows, total, color):
            card = tk.Frame(self.pl_body, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(fill="x", pady=(0, 10))
            tk.Label(card, text=title, font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                     fg=color).pack(anchor="w", padx=14, pady=(10, 4))
            for r in rows:
                row = tk.Frame(card, bg=C["card_bg"]); row.pack(fill="x", padx=20, pady=2)
                tk.Label(row, text=f"{r['code']}  {r['name']}", font=("Segoe UI", 9),
                         bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
                tk.Label(row, text=f"{r['amount']:,.2f}", font=("Segoe UI", 9),
                         bg=C["card_bg"], fg=C["text_primary"]).pack(side="right")
            if not rows:
                tk.Label(card, text="(none)", font=("Segoe UI", 9), bg=C["card_bg"],
                         fg=C["text_secondary"]).pack(anchor="w", padx=20)
            tot = tk.Frame(card, bg=C["primary_light"]); tot.pack(fill="x", padx=2, pady=(4, 2))
            ti = tk.Frame(tot, bg=C["primary_light"]); ti.pack(fill="x", padx=16, pady=6)
            tk.Label(ti, text=f"Total {title}", font=("Segoe UI", 10, "bold"),
                     bg=C["primary_light"], fg=color).pack(side="left")
            tk.Label(ti, text=f"{total:,.2f} SAR", font=("Segoe UI", 11, "bold"),
                     bg=C["primary_light"], fg=color).pack(side="right")

        section("Revenue", data["revenue"], data["total_revenue"], C["success"])
        section("Expenses", data["expenses"], data["total_expenses"], C["danger"])

        net = data["net_profit"]
        net_color = C["success"] if net >= 0 else C["danger"]
        nb = tk.Frame(self.pl_body, bg=GREEN_OR(C)); nb.pack(fill="x")
        ni = tk.Frame(nb, bg=GREEN_OR(C)); ni.pack(fill="x", padx=16, pady=12)
        tk.Label(ni, text="NET " + ("PROFIT" if net >= 0 else "LOSS"),
                 font=("Segoe UI", 13, "bold"), bg=GREEN_OR(C), fg="white").pack(side="left")
        tk.Label(ni, text=f"{abs(net):,.2f} SAR", font=("Segoe UI", 16, "bold"),
                 bg=GREEN_OR(C), fg="white").pack(side="right")

    # ── Balance Sheet ─────────────────────────────────────────
    def _build_bs(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"]); bar.pack(fill="x", pady=(10, 8))
        tk.Label(bar, text="As of:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.bs_date = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        _bsd = tk.Entry(bar, textvariable=self.bs_date, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1)
        _bsd.pack(side="left", padx=6)
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(_bsd, self.bs_date)
        except Exception:
            pass
        tk.Button(bar, text="🔍 Generate", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._run_bs).pack(side="left")
        self._exp_btns(bar, C,
            lambda mode="excel": self._export_report("Balance_Sheet", "Balance Sheet",
                ["Code", "Particulars", "", "Amount"],
                getattr(self, "_bs_rows", []), mode=mode))
        self.bs_body = tk.Frame(parent, bg=C["content_bg"]); self.bs_body.pack(fill="both", expand=True)
        self._run_bs()

    def _run_bs(self):
        """Same statement as Reports Center ▸ Balance Sheet (current / fixed
        assets, liabilities with VAT netted, equity + profit to date)."""
        C = cfg.theme()
        for w in self.bs_body.winfo_children():
            w.destroy()
        try:
            from modules import report_center as _RC
            res = _RC.run("balance_sheet", date_to=self.bs_date.get())
        except Exception as e:
            messagebox.showerror("Balance Sheet", str(e)[:300]); return
        self._bs_rows = [[r.get("code") or "", (r.get("name") or "").strip(), "",
                          "" if r.get("amount") is None else f"{r['amount']:,.2f}"]
                         for r in res["rows"]]
        card = tk.Frame(self.bs_body, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        tree = ttk.Treeview(card, columns=("code", "name", "amount"), show="headings",
                            yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        for cid, txt, w, an in (("code", "Code", 110, "w"), ("name", "Particulars", 460, "w"),
                                ("amount", "Amount (SAR)", 170, "e")):
            tree.heading(cid, text=txt); tree.column(cid, width=w, anchor=an)
        tree.tag_configure("head", font=("Segoe UI", 9, "bold"), background="#EEF2F8")
        tree.tag_configure("total", font=("Segoe UI", 9, "bold"))
        tree.tag_configure("grand", font=("Segoe UI", 10, "bold"), background=C["primary_light"])
        for r in res["rows"]:
            amt = r.get("amount")
            tree.insert("", "end", values=(r.get("code") or "", r.get("name") or "",
                                           "" if amt is None else f"{amt:,.2f}"),
                        tags=(r.get("_style"),) if r.get("_style") else ())
        tree.pack(fill="both", expand=True)
        summ = dict((x[0], x[1]) for x in res.get("summary", []))
        ok = str(summ.get("Balanced", "")).startswith("Yes")
        tk.Label(self.bs_body,
                 text=("✅ Balanced" if ok else "⚠️ NOT balanced — " + str(summ.get("Balanced")))
                 + f"   |   Assets {float(summ.get('Total assets', 0)):,.2f}  =  "
                   f"Liabilities {float(summ.get('Liabilities', 0)):,.2f}  +  "
                   f"Equity {float(summ.get('Equity', 0)):,.2f}",
                 font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg=C["success"] if ok else C["danger"]).pack(anchor="w", pady=6)


def GREEN_OR(C):
    return C.get("primary", "#006C35")


# ─────────────────────────────────────────────────────────────
# ACCOUNT FORM
# ─────────────────────────────────────────────────────────────
class AccountForm:
    def __init__(self, parent, on_save=None, account_id=None):
        self.on_save = on_save
        self.account_id = account_id
        existing = None
        if account_id:
            try:
                existing = db.fetchone(
                    "SELECT account_code, account_name_en, account_name_ar, "
                    "account_type FROM accounts WHERE account_id=?", (account_id,))
            except Exception:
                existing = None
        title = "Edit Account" if account_id else "New Account"
        C = cfg.theme()
        self.win = tk.Toplevel(); self.win.bind("<Escape>", lambda e: self.win.destroy()); self.win.title(title)
        self.win.geometry("440x400"); self.win.configure(bg=C["content_bg"])
        self.win.grab_set(); self._center(440, 400)
        hdr = tk.Frame(self.win, bg=C["primary"], height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=("✏️  " if account_id else "📋  ") + title,
                 font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=20, pady=12)

        tk.Label(body, text="Account Code *", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        self.code_var = tk.StringVar()
        tk.Entry(body, textvariable=self.code_var, font=("Segoe UI", 10), bg="white",
                 relief="solid", bd=1).pack(fill="x", ipady=5, pady=(0, 8))
        tk.Label(body, text="Name (EN) *", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        self.en_var = tk.StringVar()
        tk.Entry(body, textvariable=self.en_var, font=("Segoe UI", 10), bg="white",
                 relief="solid", bd=1).pack(fill="x", ipady=5, pady=(0, 8))
        tk.Label(body, text="الاسم (AR)", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.ar_var = tk.StringVar()
        tk.Entry(body, textvariable=self.ar_var, font=("Segoe UI", 10), bg="white",
                 relief="solid", bd=1, justify="right").pack(fill="x", ipady=5, pady=(0, 8))
        tk.Label(body, text="Type *", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        self.type_var = tk.StringVar(value="asset")
        ttk.Combobox(body, textvariable=self.type_var,
                     values=["asset", "liability", "equity", "revenue", "expense"],
                     state="readonly", font=("Segoe UI", 10)).pack(fill="x", ipady=4)

        if existing:
            self.code_var.set(existing.get("account_code", "") or "")
            self.en_var.set(existing.get("account_name_en", "") or "")
            self.ar_var.set(existing.get("account_name_ar", "") or "")
            self.type_var.set(existing.get("account_type", "asset") or "asset")

        self.status_var = tk.StringVar()
        tk.Label(body, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["danger"]).pack(anchor="w", pady=4)
        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", side="bottom")
        bi = tk.Frame(btns, bg=C["card_bg"]); bi.pack(fill="x", padx=20, pady=10)
        tk.Button(bi, text=t("common.cancel"), font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(bi, text="💾 Save", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=16, pady=6, cursor="hand2",
                  command=self._save).pack(side="right")

    def _save(self):
        if not self.code_var.get().strip() or not self.en_var.get().strip():
            self.status_var.set("⚠️ Code and Name required."); return
        try:
            if self.account_id:
                db.execute("UPDATE accounts SET account_code=?, account_name_en=?, "
                           "account_name_ar=?, account_type=? WHERE account_id=?",
                           (self.code_var.get().strip(), self.en_var.get().strip(),
                            self.ar_var.get().strip() or self.en_var.get().strip(),
                            self.type_var.get(), self.account_id))
            else:
                db.execute("INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
                           "account_type) VALUES (?,?,?,?)",
                           (self.code_var.get().strip(), self.en_var.get().strip(),
                            self.ar_var.get().strip() or self.en_var.get().strip(),
                            self.type_var.get()))
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except Exception as e:
            err = str(e)
            self.status_var.set("❌ Code exists." if "UNIQUE" in err or "duplicate" in err.lower()
                                else f"❌ {err[:60]}")

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ─────────────────────────────────────────────────────────────
# JOURNAL ENTRY FORM
# ─────────────────────────────────────────────────────────────
class JournalForm:
    def __init__(self, parent, on_save=None, journal_id=None):
        self.on_save = on_save
        self.journal_id = journal_id          # set = edit a saved voucher
        self.accounts = []
        self.lines = []
        C = cfg.theme()
        self.win = tk.Toplevel(); self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("Edit Journal Entry" if journal_id else "New Journal Entry")
        self.win.geometry("720x560"); self.win.configure(bg=C["content_bg"])
        self.win.grab_set(); self._center(720, 560)
        hdr = tk.Frame(self.win, bg=C["primary"], height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=("✏  Edit Journal Entry" if journal_id else "📝  New Journal Entry"),
                 font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=20)

        try:
            self.accounts = db.fetchall("SELECT account_id, account_code, account_name_en "
                                        "FROM accounts WHERE is_active=1 ORDER BY account_code")
        except Exception:
            self.accounts = []

        top = tk.Frame(self.win, bg=C["content_bg"]); top.pack(fill="x", padx=20, pady=10)
        tk.Label(top, text="Date:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        tk.Entry(top, textvariable=self.date_var, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1).pack(side="left", padx=6)
        tk.Label(top, text="Description:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(10, 0))
        self.desc_var = tk.StringVar()
        tk.Entry(top, textvariable=self.desc_var, font=("Segoe UI", 9),
                 relief="solid", bd=1).pack(side="left", fill="x", expand=True, padx=6)

        # Add line row
        add = tk.Frame(self.win, bg=C["primary_light"]); add.pack(fill="x", padx=20)
        ai = tk.Frame(add, bg=C["primary_light"]); ai.pack(fill="x", padx=10, pady=8)
        self.acct_var = tk.StringVar()
        self.acct_cb = ttk.Combobox(ai, textvariable=self.acct_var,
                                    values=[f"{a['account_code']} {a['account_name_en']}" for a in self.accounts],
                                    font=("Segoe UI", 9), width=38)
        self.acct_cb.pack(side="left", padx=(0, 6))
        tk.Label(ai, text="Dr:", font=("Segoe UI", 9), bg=C["primary_light"],
                 fg=C["primary"]).pack(side="left")
        self.dr_var = tk.StringVar(value="0")
        tk.Entry(ai, textvariable=self.dr_var, width=10, font=("Segoe UI", 9),
                 relief="solid", bd=1).pack(side="left", padx=(2, 8), ipady=2)
        tk.Label(ai, text="Cr:", font=("Segoe UI", 9), bg=C["primary_light"],
                 fg=C["primary"]).pack(side="left")
        self.cr_var = tk.StringVar(value="0")
        tk.Entry(ai, textvariable=self.cr_var, width=10, font=("Segoe UI", 9),
                 relief="solid", bd=1).pack(side="left", padx=(2, 8), ipady=2)
        tk.Button(ai, text="Add Line", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=12, pady=4, cursor="hand2",
                  command=self._add_line).pack(side="left")

        wrap = tk.Frame(self.win, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=20, pady=(10, 0))
        cols = ("acct", "debit", "credit")
        vsb = ttk.Scrollbar(wrap, orient="vertical"); vsb.pack(side="right", fill="y")
        self.line_tree = ttk.Treeview(wrap, columns=cols, show="headings", height=8, yscrollcommand=vsb.set)
        vsb.config(command=self.line_tree.yview)
        self.line_tree.heading("acct", text="Account"); self.line_tree.column("acct", width=360, anchor="w")
        self.line_tree.heading("debit", text="Debit"); self.line_tree.column("debit", width=140, anchor="e")
        self.line_tree.heading("credit", text="Credit"); self.line_tree.column("credit", width=140, anchor="e")
        self.line_tree.pack(fill="both", expand=True)
        try:
            from ui.grid_lines import excel_grid
            excel_grid(self.line_tree)
        except Exception:
            pass
        self.line_tree.bind("<Double-1>", lambda e: self._remove_line())

        # Totals + save
        footer = tk.Frame(self.win, bg=C["card_bg"]); footer.pack(fill="x", side="bottom")
        fi = tk.Frame(footer, bg=C["card_bg"]); fi.pack(fill="x", padx=20, pady=10)
        self.balance_var = tk.StringVar(value="Dr 0.00  |  Cr 0.00")
        tk.Label(fi, textvariable=self.balance_var, font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
        self.status_var = tk.StringVar()
        tk.Label(fi, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["danger"]).pack(side="left", padx=12)
        tk.Button(fi, text=t("common.cancel"), font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(fi, text=("💾 Save Changes" if journal_id else "💾 Post Entry"),
                  font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=16, pady=6, cursor="hand2",
                  command=self._save).pack(side="right")
        if journal_id:
            self._load_existing()

    def _load_existing(self):
        """Fill the form with a saved voucher (edit mode)."""
        try:
            h = db.fetchone("SELECT * FROM journal_entries WHERE journal_id=?",
                            (self.journal_id,)) or {}
            d = h.get("entry_date")
            self.date_var.set(d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")[:10])
            self.desc_var.set(h.get("description_en") or "")
            self._ref = h.get("reference")
            for r in db.fetchall(
                    "SELECT jl.account_id, jl.debit, jl.credit, jl.description, "
                    "a.account_code, a.account_name_en FROM journal_lines jl "
                    "LEFT JOIN accounts a ON a.account_id=jl.account_id "
                    "WHERE jl.journal_id=? ORDER BY jl.line_number",
                    (self.journal_id,)) or []:
                self.lines.append({
                    "account_id": r["account_id"],
                    "label": f"{r.get('account_code') or ''} {r.get('account_name_en') or ''}",
                    "debit": float(r.get("debit") or 0),
                    "credit": float(r.get("credit") or 0),
                    "description": r.get("description") or ""})
            self._refresh()
        except Exception as e:
            self.status_var.set(f"❌ {str(e)[:70]}")

    def _update_existing(self):
        """Save an edited voucher: same number, new date / text / lines.
        One transaction: the old lines are never lost without the new (v5.27)."""
        with db.transaction():
            return self._update_existing_tx()

    def _update_existing_tx(self):
        td = round(sum(float(l.get("debit") or 0) for l in self.lines), 2)
        tc = round(sum(float(l.get("credit") or 0) for l in self.lines), 2)
        if abs(td - tc) > 0.01:
            raise ValueError(f"Unbalanced entry: debit {td} != credit {tc}")
        if td == 0:
            raise ValueError("Journal entry has no amounts.")
        try:
            from modules import financial_year as fy
            msg = fy.guard_active(self.date_var.get())
            if msg:
                raise ValueError(msg)
        except ValueError:
            raise
        except Exception:
            pass
        db.execute("UPDATE journal_entries SET entry_date=?, description_en=?, "
                   "total_debit=?, total_credit=? WHERE journal_id=?",
                   (self.date_var.get(), self.desc_var.get(), td, tc, self.journal_id))
        db.execute("DELETE FROM journal_lines WHERE journal_id=?", (self.journal_id,))
        for i, l in enumerate(self.lines, 1):
            db.execute("INSERT INTO journal_lines (journal_id, line_number, account_id, "
                       "debit, credit, description) VALUES (?,?,?,?,?,?)",
                       (self.journal_id, i, l["account_id"],
                        round(float(l.get("debit") or 0), 2),
                        round(float(l.get("credit") or 0), 2), l.get("description", "")))
        try:
            from modules.doc_actions import audit
            audit("edit", "journal", self.journal_id, f"Dr {td:,.2f} Cr {tc:,.2f}")
        except Exception:
            pass

    def _add_line(self):
        idx = self.acct_cb.current()
        if idx < 0:
            self.status_var.set("⚠️ Select account."); return
        try:
            dr = float(self.dr_var.get() or 0); cr = float(self.cr_var.get() or 0)
        except ValueError:
            self.status_var.set("⚠️ Invalid amount."); return
        if dr == 0 and cr == 0:
            self.status_var.set("⚠️ Enter a debit or credit."); return
        a = self.accounts[idx]
        self.lines.append({"account_id": a["account_id"],
                           "label": f"{a['account_code']} {a['account_name_en']}",
                           "debit": dr, "credit": cr})
        self._refresh()
        self.dr_var.set("0"); self.cr_var.set("0"); self.acct_var.set("")
        self.status_var.set("")

    def _remove_line(self):
        s = self.line_tree.selection()
        if s:
            idx = self.line_tree.index(s[0])
            if 0 <= idx < len(self.lines):
                del self.lines[idx]; self._refresh()

    def _refresh(self):
        self.line_tree.delete(*self.line_tree.get_children())
        td = tc = 0.0
        for ln in self.lines:
            td += ln["debit"]; tc += ln["credit"]
            self.line_tree.insert("", "end", values=(
                ln["label"], f"{ln['debit']:,.2f}" if ln["debit"] else "",
                f"{ln['credit']:,.2f}" if ln["credit"] else ""))
        bal = "✅" if abs(td - tc) < 0.01 and td > 0 else "⚠️"
        self.balance_var.set(f"{bal}  Dr {td:,.2f}  |  Cr {tc:,.2f}")

    def _save(self):
        if not self.lines:
            self.status_var.set("⚠️ Add lines first."); return
        try:
            if self.journal_id:
                self._update_existing()
                messagebox.showinfo(t("common.success"), "Journal entry updated.")
            else:
                acc.post_journal(db, self.date_var.get(), self.lines,
                                 description_en=self.desc_var.get(), source_type="manual")
                messagebox.showinfo(t("common.success"), "Journal entry posted.")
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except ValueError as e:
            self.status_var.set(f"❌ {e}")
        except Exception as e:
            self.status_var.set(f"❌ {str(e)[:70]}")

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
