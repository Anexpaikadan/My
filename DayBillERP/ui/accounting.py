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

    def _add_default_groups(self):
        """v7.7: Cash-in-Hand, Bank Accounts, Sundry Debtors / Creditors,
        Duties & Taxes, Direct / Indirect Income and Expenses …"""
        try:
            from modules import permissions as _perm
            if not _perm.can("accounts", "edit"):
                messagebox.showwarning("Chart of Accounts", "Your user type can't change accounts.")
                return
        except Exception:
            pass
        if not messagebox.askyesno(
                "Add default groups",
                "Add the standard account groups?\n\n"
                "Assets › Cash-in-Hand · Bank Accounts · Sundry Debtors · Stock-in-Hand · "
                "Loans & Advances · Deposits · Investments\n"
                "Liabilities › Sundry Creditors · Duties & Taxes · Provisions & Payroll · Loans\n"
                "Equity › Capital Account · Reserves & Surplus\n"
                "Revenue › Sales Accounts · Direct Income · Indirect Income\n"
                "Expenses › Direct Expenses · Employee Costs · Administrative · "
                "Selling & Distribution · Financial Charges\n\n"
                "DayBill's own ledgers go into their group; ledgers you moved stay "
                "where they are. Account codes do not change."):
            return
        try:
            from modules import account_tree as _AT
            n = _AT.add_default_groups()
        except Exception as e:
            messagebox.showerror("Add default groups", str(e)[:300])
            return
        self._load_coa()
        try:
            self._coa_open_all(True)
        except Exception:
            pass
        messagebox.showinfo("Add default groups", "Done — %d groups in the chart of accounts." % n)

    # ── Chart of Accounts ─────────────────────────────────────
    def _build_coa(self, parent, C):
        """v7.0: the chart of accounts as a TREE — every ledger under its
        group (master), groups bold; search box; new group / new ledger
        under the selected group."""
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(10, 8))
        tk.Button(bar, text="＋ New Ledger", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=7,
                  cursor="hand2", command=self._new_account).pack(side="right")
        tk.Button(bar, text="＋ New Group", font=("Segoe UI", 10),
                  bg=C["card_bg"], fg=C["primary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=self._new_group).pack(side="right", padx=(0, 8))
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
        tk.Label(bar, text="🔍", font=("Segoe UI", 10), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.coa_find = tk.StringVar()
        fe = tk.Entry(bar, textvariable=self.coa_find, width=26, font=("Segoe UI", 10),
                      relief="solid", bd=1)
        fe.pack(side="left", ipady=4, padx=(4, 8))
        self.coa_find.trace_add("write", lambda *a: self._load_coa())
        for txt, opn in (("⊞ Open all", True), ("⊟ Close all", False)):
            tk.Button(bar, text=txt, font=("Segoe UI", 9), bg=C["content_bg"], fg=C["primary"],
                      relief="flat", cursor="hand2", bd=0,
                      command=lambda o=opn: self._coa_open_all(o)).pack(side="left", padx=(0, 6))
        tk.Button(bar, text="⊕ Add default groups", font=("Segoe UI", 9), bg=C["content_bg"],
                  fg=C["primary"], relief="flat", cursor="hand2", bd=0,
                  command=self._add_default_groups).pack(side="left", padx=(6, 6))
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("name_ar", "type", "kind")
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.coa_tree = ttk.Treeview(card, columns=cols, show="tree headings", yscrollcommand=vsb.set)
        vsb.config(command=self.coa_tree.yview)
        self.coa_tree.heading("#0", text="Account (code · name)", anchor="w")
        self.coa_tree.column("#0", width=380, anchor="w", stretch=True)
        for col, (lbl, w, an) in {"name_ar": ("الاسم", 220, "e"), "type": ("Type", 110, "center"),
                                  "kind": ("Group / Ledger", 110, "center")}.items():
            self.coa_tree.heading(col, text=lbl); self.coa_tree.column(col, width=w, anchor=an, stretch=False)
        self.coa_tree.tag_configure("grp", font=("Segoe UI", 10, "bold"))
        self.coa_tree.tag_configure("off", foreground="#9CA3AF")
        self.coa_tree.pack(fill="both", expand=True)
        self.coa_tree.bind("<Double-1>", lambda e: self._edit_account())
        self._load_coa()

    def _load_coa(self):
        from modules import account_tree as AT
        tv = self.coa_tree
        opened = {i for i in self._all_iids(tv) if tv.item(i, "open")} if tv.get_children() else None
        tv.delete(*tv.get_children())
        try:
            by = AT.rows()
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return
        q = [w for w in (self.coa_find.get() if hasattr(self, "coa_find") else "").lower().split() if w]
        keep = None
        if q:                          # matching accounts + the groups above them
            keep = set()
            for a in by.values():
                hay = ("%s %s %s %s" % (a["code"], a["name"], a["name_ar"], a["type"])).lower()
                if all(w in hay for w in q):
                    cur = a
                    while cur is not None and cur["account_id"] not in keep:
                        keep.add(cur["account_id"])
                        cur = by.get(cur["parent_id"])
        for a in AT.ordered(by):
            if keep is not None and a["account_id"] not in keep:
                continue
            parent = str(a["parent_id"]) if a["parent_id"] and tv.exists(str(a["parent_id"])) else ""
            tv.insert(parent, "end", iid=str(a["account_id"]), text="%s · %s" % (a["code"], a["name"]),
                      values=(a["name_ar"], a["type"].title(), "Group" if a["is_group"] else "Ledger"),
                      tags=("grp",) if a["is_group"] else (),
                      open=bool(q) or (opened is None and a["depth"] < 1) or
                      (opened is not None and str(a["account_id"]) in opened))

    @staticmethod
    def _all_iids(tv, parent=""):
        out = []
        for i in tv.get_children(parent):
            out.append(i)
            out += AccountingView._all_iids(tv, i)
        return out

    def _coa_open_all(self, opn):
        for i in self._all_iids(self.coa_tree):
            self.coa_tree.item(i, open=opn)

    def _coa_group(self):
        """The group a new account goes under: the selected group, or the
        group of the selected ledger."""
        sel = self.coa_tree.selection() if hasattr(self, "coa_tree") else ()
        if not sel:
            return None
        aid = int(sel[0])
        if "grp" in self.coa_tree.item(sel[0], "tags"):
            return aid
        p = self.coa_tree.parent(sel[0])
        return int(p) if p else None

    @perm.guard("accounts", "add")
    def _new_account(self):
        AccountForm(self.frame, self._load_coa, parent_id=self._coa_group())

    @perm.guard("accounts", "add")
    def _new_group(self):
        AccountForm(self.frame, self._load_coa, parent_id=self._coa_group(), group=True)

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
        _code, _, _name = str(self.coa_tree.item(str(aid))["text"]).partition(" · ")
        vals = [_code, _name]
        if self.coa_tree.get_children(str(aid)):
            messagebox.showwarning("Deactivate Account", "%s — %s is a group with ledgers under it. Move or "
                                   "deactivate those ledgers first." % (_code, _name))
            return
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
            from modules import voucher_types as _vt
            rows = db.fetchall("SELECT journal_id, journal_number, entry_date, "
                               "description_en, source_type, "
                               "total_debit, total_credit, is_posted, %s AS voucher_type "
                               "FROM journal_entries je "
                               "ORDER BY entry_date DESC, journal_id DESC" % _vt.col())
        except Exception:
            rows = []
        from modules import voucher_types as _vt
        for r in rows:
            self.jrn_tree.insert("", "end", iid=str(r["journal_id"]), values=(
                r["journal_number"], str(r.get("entry_date", "")),
                r.get("description_en", "") or "", _vt.label(_vt.of_journal(r)),
                f"{float(r['total_debit']):,.2f}", f"{float(r['total_credit']):,.2f}",
                "✅ Posted" if r.get("is_posted") else "📝 Draft"))

    @perm.guard("journal", "add")
    def _new_journal(self):
        JournalForm(self.frame, self._load_journals)

    @perm.guard("journal", "delete")
    def _delete_journal(self):
        """Delete a manual journal entry (lines cascade). Journals that a
        document or payroll / stock / year-end posted are protected —
        delete the source instead, and its journal goes with it."""
        sel = self.jrn_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a journal entry first.")
            return
        jid = int(sel[0])
        vals = self.jrn_tree.item(sel[0])["values"]
        # the Source column shows the voucher type, so ask the connector
        from ui.vouchers import voucher_owner
        txn, why = voucher_owner(jid)
        if not txn:
            messagebox.showinfo("Delete Journal Entry", why, parent=self.frame)
            self._load_journals()
            return
        if why:
            messagebox.showwarning("Delete Journal Entry", why, parent=self.frame)
            return
        from ui import txn_connector as tc
        if tc._locked(txn, self.frame, "Delete Journal Entry"):   # closed year
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
        try:                       # v7.0: type to search, the accounts as a tree
            from ui import search_drop as _SD
            from modules import account_tree as _AT
            _SD.attach(self.led_cb, self.led_acct_var,
                       lambda: _AT.items(value_fmt=lambda a: f"{a['code']} — {a['name']}"), tree=True,
                       width=420)
        except Exception:
            pass
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


def _on_top_of(win, parent):
    """Keep a modal form above the window that opened it — without this a
    grabbed form can drop behind the main window and the app looks frozen."""
    try:
        if parent is not None:
            win.transient(parent.winfo_toplevel())
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# ACCOUNT FORM
# ─────────────────────────────────────────────────────────────
class AccountForm:
    """New / edit a ledger or a group. v7.0: every account goes UNDER a
    group (the tree dropdown lists every group); the type comes from the
    group and the next free code is filled in."""

    def __init__(self, parent, on_save=None, account_id=None, parent_id=None, group=False):
        from modules import account_tree as AT
        self.AT = AT
        self.on_save = on_save
        self.account_id = account_id
        self._by = AT.rows(active_only=False)
        existing = self._by.get(account_id) if account_id else None
        self._is_group_now = bool(existing and existing["is_group"])
        if existing:
            parent_id = existing["parent_id"]
            group = existing["is_group"]
        kind = "Group" if group else "Ledger"
        title = ("Edit %s" % kind) if account_id else ("New %s" % kind)
        C = cfg.theme()
        self.C = C
        self.win = tk.Toplevel(parent); self.win.bind("<Escape>", lambda e: self._esc()); self.win.title(title)
        self.win.geometry("480x560"); self.win.configure(bg=C["content_bg"])
        _on_top_of(self.win, parent)          # stays above the main window
        self.win.grab_set(); self._center(480, 560)
        hdr = tk.Frame(self.win, bg=C["primary"], height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=("✏️  " if account_id else ("🗂  " if group else "📋  ")) + title,
                 font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=20, pady=12)

        def lab(text, req=False):
            tk.Label(body, text=text + (" *" if req else ""), font=("Segoe UI", 9, "bold" if req else "normal"),
                     bg=C["content_bg"], fg=C["primary"] if req else C["text_secondary"]).pack(anchor="w")

        lab("Under group", True)
        prow = tk.Frame(body, bg=C["content_bg"]); prow.pack(fill="x", pady=(0, 2))
        self.parent_var = tk.StringVar()
        self.parent_entry = tk.Entry(prow, textvariable=self.parent_var, font=("Segoe UI", 10), bg="white",
                                     relief="solid", bd=1)
        self.parent_entry.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Button(prow, text="▾", font=("Segoe UI", 9), bg=C["card_bg"], relief="flat", cursor="hand2",
                  command=lambda: (self.parent_entry.focus_set(), self._drop.open(""))).pack(side="left", padx=(2, 0))
        from ui import search_drop as SD
        self._drop = SD.attach(self.parent_entry, self.parent_var, self._group_items, tree=True,
                               on_pick=self._on_parent, width=420)
        self.path_var = tk.StringVar()
        tk.Label(body, textvariable=self.path_var, font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"], wraplength=430, justify="left").pack(anchor="w", pady=(0, 8))

        lab("Account Code", True)
        self.code_var = tk.StringVar()
        ce = tk.Entry(body, textvariable=self.code_var, font=("Segoe UI", 10), bg="white",
                      relief="solid", bd=1)
        ce.pack(fill="x", ipady=5, pady=(0, 8))
        ce.bind("<Key>", lambda e: setattr(self, "_code_typed", True))
        self._code_typed = bool(account_id)
        lab("Name (EN)", True)
        self.en_var = tk.StringVar()
        self.en_entry = tk.Entry(body, textvariable=self.en_var, font=("Segoe UI", 10), bg="white",
                                 relief="solid", bd=1)
        self.en_entry.pack(fill="x", ipady=5, pady=(0, 8))
        lab("الاسم (AR)")
        self.ar_var = tk.StringVar()
        tk.Entry(body, textvariable=self.ar_var, font=("Segoe UI", 10), bg="white",
                 relief="solid", bd=1, justify="right").pack(fill="x", ipady=5, pady=(0, 8))
        lab("Type", True)
        self.type_var = tk.StringVar(value="asset")
        self.type_cb = ttk.Combobox(body, textvariable=self.type_var,
                                    values=["asset", "liability", "equity", "revenue", "expense"],
                                    state="readonly", font=("Segoe UI", 10))
        self.type_cb.pack(fill="x", ipady=4)
        self.type_note = tk.Label(body, text="", font=("Segoe UI", 8), bg=C["content_bg"],
                                  fg=C["text_secondary"])
        self.type_note.pack(anchor="w")
        self.group_var = tk.BooleanVar(value=bool(group))
        tk.Checkbutton(body, text="This is a group (other ledgers go under it)", variable=self.group_var,
                       font=("Segoe UI", 9), bg=C["content_bg"], activebackground=C["content_bg"],
                       state="disabled" if self._is_group_now and existing and existing["children"] else "normal"
                       ).pack(anchor="w", pady=(6, 0))

        if existing:
            self.code_var.set(existing["code"])
            self.en_var.set(existing["name"])
            self.ar_var.set(existing["name_ar"])
            self.type_var.set(existing["type"] or "asset")
        self._set_parent(parent_id, fill_code=not account_id)

        self.status_var = tk.StringVar()
        tk.Label(body, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["danger"], wraplength=430, justify="left").pack(anchor="w", pady=4)
        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", side="bottom")
        bi = tk.Frame(btns, bg=C["card_bg"]); bi.pack(fill="x", padx=20, pady=10)
        tk.Button(bi, text=t("common.cancel"), font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(bi, text="💾 Save", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=16, pady=6, cursor="hand2",
                  command=self._save).pack(side="right")
        (self.en_entry if parent_id or account_id else self.parent_entry).focus_set()

    def _esc(self):
        if self._drop.is_open():
            self._drop.close()
            return
        self.win.destroy()

    TOP = "(top level — a main head)"

    def _group_items(self):
        """Every group (and, for a ledger with nothing yet under it, any
        account) as a tree; never the account itself or what is under it."""
        out = [{"label": self.TOP, "value": self.TOP, "depth": 0, "search": "main top head root"}]
        for it in self.AT.items(groups_only=True, by=self._by):
            aid = it["account_id"]
            if self.account_id and not self.AT.can_move(self.account_id, aid, self._by)[0]:
                continue
            out.append(it)
        return out

    def _set_parent(self, parent_id, fill_code=True):
        self._parent_id = parent_id
        a = self._by.get(parent_id) if parent_id else None
        if a is None:
            self.parent_var.set(self.TOP if (self.account_id or self.group_var.get()) else "")
            self.path_var.set("A main head of the chart (Assets, Liabilities …)." if self.parent_var.get() else
                              "Pick the group this account goes under (type to search).")
            self.type_cb.configure(state="readonly")
            self.type_note.configure(text="")
            return
        self.parent_var.set(self.AT.label(a))
        self.path_var.set("Goes under:  " + self.AT.SEP.join(x for x in (a["path"], a["name"]) if x))
        tp = self.AT.type_of(parent_id, self._by)
        if tp:
            self.type_var.set(tp)
            self.type_cb.configure(state="disabled")
            self.type_note.configure(text="Same type as its group.")
        if fill_code and not self._code_typed:
            self.code_var.set(self.AT.next_code(parent_id, self._by))

    def _on_parent(self, it):
        if it.get("value") == self.TOP:
            self._set_parent(None, fill_code=False)
            self.parent_var.set(self.TOP)
            return
        self._set_parent(it.get("account_id"))

    def _save(self):
        if not perm.allowed("accounts", "edit" if self.account_id else "add",
                            parent=self.win):
            return
        if not self.code_var.get().strip() or not self.en_var.get().strip():
            self.status_var.set("⚠️ Code and Name required."); return
        ptxt = self.parent_var.get().strip()
        if ptxt == self.TOP:
            parent_id = None
            if not self.group_var.get():
                self.status_var.set("⚠️ A ledger must be under a group. Pick its group "
                                    "(Current Assets, Expenses …)."); return
        else:
            parent_id = self.AT.id_of(ptxt, self._by)
            if not parent_id:
                self.status_var.set("⚠️ Pick the group from the list (type a few letters, then pick)."); return
        ok, why = self.AT.can_move(self.account_id, parent_id, self._by)
        if not ok:
            self.status_var.set("⚠️ " + why); return
        if self._is_group_now and not self.group_var.get() and self.account_id and \
                self._by[self.account_id]["children"]:
            self.status_var.set("⚠️ This group has ledgers under it, so it stays a group."); return
        typ = self.AT.type_of(parent_id, self._by) or self.type_var.get()
        cols = {"account_code": self.code_var.get().strip(), "account_name_en": self.en_var.get().strip(),
                "account_name_ar": self.ar_var.get().strip() or self.en_var.get().strip(),
                "account_type": typ, "parent_account_id": parent_id}
        if self.AT.has_group_col():
            cols["is_group"] = 1 if self.group_var.get() else 0
        try:
            if self.account_id:
                old = self._by.get(self.account_id) or {}
                if old.get("type") and old["type"] != typ:
                    n = db.execute_scalar("SELECT COUNT(*) FROM journal_lines WHERE account_id=?",
                                          (self.account_id,)) or 0
                    if n and not messagebox.askyesno(
                            "Move account", "This account has %d entries. Moving it to a %s group changes "
                            "where it shows in the reports (Balance Sheet / Profit & Loss).\n\nMove it?"
                            % (n, typ), parent=self.win):
                        return
                db.execute("UPDATE accounts SET %s WHERE account_id=?" % ", ".join("%s=?" % k for k in cols),
                           tuple(cols.values()) + (self.account_id,))
            else:
                db.execute("INSERT INTO accounts (%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" for _ in cols)),
                           tuple(cols.values()))
            if parent_id and self.AT.has_group_col():       # its group is a group
                db.execute("UPDATE accounts SET is_group=1 WHERE account_id=?", (parent_id,))
            try:
                from modules import account_defaults as _ad
                _ad.invalidate()
            except Exception:
                pass
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


# v7.1: the Journal window is the multi-line voucher window (ui/multi_voucher.py)
from ui.multi_voucher import JournalForm  # noqa: E402,F401
