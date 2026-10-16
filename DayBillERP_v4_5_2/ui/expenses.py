# ============================================================
# DayBill ERP - Expenses
# ------------------------------------------------------------
# Record day-to-day expenses (rent, electricity, fuel, office…).
# Each saved expense writes the `expenses` row AND posts a journal
# via modules.posting.post_expense:
#     Dr Expense (+ Dr VAT input) | Cr Cash/Bank  (or Cr Supplier)
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import posting
from modules import account_defaults as ad
from modules import permissions as perm


def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


class ExpensesView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._topbar(C)
        self._table(C)
        self._load()

    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="💸  Expenses & Assets", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="➕  New Expense", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._new).pack(side="right")
        tk.Button(bar, text="🪑  New Asset (furniture…)", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["primary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=self._new_asset).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="✏  Edit", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=self._edit).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="🗑  Delete", font=("Segoe UI", 9, "bold"),
                  bg="#FEF2F2", fg=C["danger"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._delete).pack(
                      side="right", padx=(0, 8))
        tk.Button(bar, text="📥  Export", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export_excel).pack(side="right", padx=(0, 8))

        f = tk.Frame(self.frame, bg=C["content_bg"])
        f.pack(fill="x", padx=24, pady=(12, 0))
        today = date.today()
        self.from_var = tk.StringVar(value=today.replace(day=1).strftime("%Y-%m-%d"))
        self.to_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        for lbl, var in [("From", self.from_var), ("To", self.to_var)]:
            tk.Label(f, text=lbl, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            tk.Entry(f, textvariable=var, width=11, font=("Segoe UI", 10),
                     relief="solid", bd=1).pack(side="left", padx=(0, 10))
        tk.Button(f, text="🔍 Filter", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self._load).pack(side="left")
        self.total_var = tk.StringVar()
        tk.Label(f, textvariable=self.total_var, font=("Segoe UI", 11, "bold"),
                 bg=C["content_bg"], fg=C["danger"]).pack(side="right")

    def _table(self, C):
        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=12)
        cols = ("date", "kind", "account", "amount", "vat", "total", "method",
                "supplier", "ref", "desc")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for cid, txt, w, a in [("date", "Date", 84, "center"),
                               ("kind", "Type", 70, "center"),
                               ("account", "Account", 170, "w"),
                               ("amount", "Net", 90, "e"),
                               ("vat", "VAT", 76, "e"),
                               ("total", "Total", 96, "e"),
                               ("method", "Paid By", 74, "center"),
                               ("supplier", "Supplier", 130, "w"),
                               ("ref", "Reference", 100, "w"),
                               ("desc", "Description", 180, "w")]:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=a)
        self.tree.bind("<Double-1>", lambda e: self._edit())
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

    def _load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._journals = {}
        try:
            try:
                rows = db.fetchall(
                    "SELECT e.expense_id, e.journal_id, e.expense_date, e.amount, "
                    "e.vat_amount, e.payment_method, e.reference, e.description, "
                    "e.expense_kind, s.supplier_name_en, a.account_name_en, a.account_type "
                    "FROM expenses e LEFT JOIN accounts a ON a.account_id=e.expense_account_id "
                    "LEFT JOIN suppliers s ON s.supplier_id=e.supplier_id "
                    "WHERE e.expense_date BETWEEN ? AND ? ORDER BY e.expense_id DESC",
                    (self.from_var.get(), self.to_var.get())) or []
            except Exception:                       # before expense_vat_patch.sql
                rows = db.fetchall(
                    "SELECT e.expense_id, e.journal_id, e.expense_date, e.amount, "
                    "e.vat_amount, e.payment_method, e.reference, e.description, "
                    "a.account_name_en, a.account_type "
                    "FROM expenses e LEFT JOIN accounts a ON a.account_id=e.expense_account_id "
                    "WHERE e.expense_date BETWEEN ? AND ? ORDER BY e.expense_id DESC",
                    (self.from_var.get(), self.to_var.get())) or []
        except Exception as e:
            messagebox.showerror("Expenses",
                                 "Could not read expenses. Run default_accounts_patch.sql "
                                 "(it creates the expenses table).\n\n" + str(e)[:150])
            return
        total = tvat = 0.0
        for r in rows:
            d = r["expense_date"]
            dtxt = d.strftime("%d/%m/%y") if hasattr(d, "strftime") else str(d)[:10]
            net = float(r["amount"] or 0); vat = float(r["vat_amount"] or 0)
            total += net + vat; tvat += vat
            kind = r.get("expense_kind") or ("asset" if r.get("account_type") == "asset"
                                             else "expense")
            self._journals[r["expense_id"]] = r.get("journal_id")
            self.tree.insert("", "end", iid=str(r["expense_id"]), values=(
                dtxt, "🪑 Asset" if kind == "asset" else "Expense",
                r["account_name_en"] or "—", money(net), money(vat), money(net + vat),
                r["payment_method"] or "cash", r.get("supplier_name_en") or "",
                r["reference"] or "", r["description"] or ""))
        self.total_var.set(f"Total: {money(total)} SAR  ·  VAT {money(tvat)}  ({len(rows)})")

    @perm.guard("accounts", "edit")
    def _edit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an expense first.")
            return
        ExpenseForm(self.frame, on_saved=self._load, expense_id=int(sel[0]))

    @perm.guard("accounts", "add")
    def _new_asset(self):
        ExpenseForm(self.frame, on_saved=self._load, kind="asset")

    @perm.guard("accounts", "delete")
    def _delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an expense first.")
            return
        eid = int(sel[0])
        vals = self.tree.item(sel[0])["values"]
        if not messagebox.askyesno(
                "Delete Expense",
                f"Delete {vals[1].lower()} of {vals[5]} on {vals[0]}?\n"
                "Its posted journal entry will also be removed."):
            return
        try:
            from modules.doc_actions import audit
            jid = self._journals.get(eid)
            with db.transaction():          # expense + its journal go together
                # the expense row points at its journal (FK) -> delete it first
                db.execute("DELETE FROM expenses WHERE expense_id=?", (eid,))
                _delete_expense_journals(eid, jid)
                audit("delete", "expense", eid, str(vals[5]))
            self._load()
        except Exception as e:
            messagebox.showerror("Delete Expense", str(e)[:300])

    @perm.guard("accounts", "export")
    def _export_excel(self):
        try:
            from modules.doc_actions import export_tree_excel
            headers = ["Date", "Type", "Account", "Net", "VAT", "Total",
                       "Paid By", "Supplier", "Reference", "Description"]
            export_tree_excel(self.frame, self.tree, "Expenses", headers,
                              title="Expenses",
                              summary=[("Period",
                                        f"{self.from_var.get()} → {self.to_var.get()}")])
        except Exception as e:
            messagebox.showerror("Export", str(e)[:300])

    @perm.guard("accounts", "add")
    def _new(self):
        ExpenseForm(self.frame, on_saved=self._load)


class ExpenseForm:
    """New / edit an expense or an ASSET purchase (shop furniture,
    equipment, computers, vehicles) with input VAT.

        Dr Expense or Fixed-asset account (net)
        Dr VAT Input (15 %)
        Cr Cash / Bank / Card   — or —   Cr Supplier (on credit)

    The VAT goes into the VAT Return (box: purchases / expenses) and the
    asset shows under Fixed Assets in the Balance Sheet (not in P&L)."""

    def __init__(self, parent, on_saved=None, expense_id=None, kind="expense"):
        C = cfg.theme()
        self.C = C
        self.on_saved = on_saved
        self.expense_id = expense_id
        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("Edit Expense" if expense_id else "New Expense / Asset Purchase")
        self.win.configure(bg=C["card_bg"])
        self.win.geometry("520x640")
        self.win.transient(parent.winfo_toplevel())
        self.win.grab_set()
        self._load_accounts()
        self._build(C, kind)
        if expense_id:
            self._load_existing()
        self._recalc()

    # ── data ──────────────────────────────────────────────────
    def _load_accounts(self):
        try:
            self.expense_accts = db.fetchall(
                "SELECT account_id, account_code, account_name_en FROM accounts "
                "WHERE is_active=1 AND account_type='expense' ORDER BY account_code") or []
        except Exception:
            self.expense_accts = []
        try:
            # fixed assets: 15xx (furniture, equipment, vehicles …) except the
            # 1500 group itself and accumulated depreciation
            self.asset_accts = [a for a in (db.fetchall(
                "SELECT account_id, account_code, account_name_en FROM accounts "
                "WHERE is_active=1 AND account_type='asset' ORDER BY account_code") or [])
                if str(a["account_code"]).startswith("15")
                and str(a["account_code"]) not in ("1500", "1590")]
        except Exception:
            self.asset_accts = []
        try:
            self.suppliers = db.fetchall(
                "SELECT supplier_id, supplier_name_en, "
                "ISNULL(vat_registration_no,'') AS vat_no FROM suppliers "
                "WHERE is_active=1 ORDER BY supplier_name_en") or []
        except Exception:
            try:
                self.suppliers = db.fetchall(
                    "SELECT supplier_id, supplier_name_en FROM suppliers "
                    "WHERE is_active=1 ORDER BY supplier_name_en") or []
            except Exception:
                self.suppliers = []

    def _acct_values(self):
        rows = self.asset_accts if self.kind_var.get() == "asset" else self.expense_accts
        return [f"{a['account_code']} · {a['account_name_en']}" for a in rows]

    # ── UI ────────────────────────────────────────────────────
    def _build(self, C, kind):
        head = tk.Frame(self.win, bg=C["primary"])
        head.pack(fill="x")
        tk.Label(head, text=("✏  Edit Expense" if self.expense_id else "💸  New Expense / Asset"),
                 font=("Segoe UI", 13, "bold"), bg=C["primary"], fg="white").pack(
                     side="left", padx=14, pady=8)
        body = tk.Frame(self.win, bg=C["card_bg"])
        body.pack(fill="both", expand=True, padx=18, pady=10)
        self.body = body

        def label(parent, t):
            tk.Label(parent, text=t, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", pady=(8, 2))

        # type
        self.kind_var = tk.StringVar(value=kind if kind in ("expense", "asset") else "expense")
        kr = tk.Frame(body, bg=C["card_bg"]); kr.pack(fill="x")
        for val, txt in (("expense", "💸 Expense  (rent, electricity, fuel …)"),
                         ("asset", "🪑 Asset purchase  (furniture, equipment …)")):
            tk.Radiobutton(kr, text=txt, value=val, variable=self.kind_var,
                           font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                           fg=C["text_primary"], activebackground=C["card_bg"],
                           selectcolor="white", command=self._kind_changed).pack(anchor="w")

        r1 = tk.Frame(body, bg=C["card_bg"]); r1.pack(fill="x")
        c1 = tk.Frame(r1, bg=C["card_bg"]); c1.pack(side="left", fill="x", expand=True, padx=(0, 6))
        label(c1, "Date")
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        de = tk.Entry(c1, textvariable=self.date_var, font=("Segoe UI", 10))
        de.pack(fill="x", ipady=2)
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(de, self.date_var)
        except Exception:
            pass
        c2 = tk.Frame(r1, bg=C["card_bg"]); c2.pack(side="left", fill="x", expand=True)
        label(c2, "Supplier invoice no. / Reference")
        self.ref_var = tk.StringVar()
        tk.Entry(c2, textvariable=self.ref_var, font=("Segoe UI", 10)).pack(fill="x", ipady=2)

        self.acct_label = tk.Label(body, text="Expense account *", font=("Segoe UI", 9),
                                   bg=C["card_bg"], fg=C["text_secondary"])
        self.acct_label.pack(anchor="w", pady=(8, 2))
        self.acct_var = tk.StringVar()
        self.acct_cb = ttk.Combobox(body, textvariable=self.acct_var, state="readonly",
                                    values=self._acct_values())
        self.acct_cb.pack(fill="x")

        # amount + VAT
        r2 = tk.Frame(body, bg=C["card_bg"]); r2.pack(fill="x")
        a1 = tk.Frame(r2, bg=C["card_bg"]); a1.pack(side="left", fill="x", expand=True, padx=(0, 6))
        label(a1, "Amount *")
        self.amount_var = tk.StringVar()
        tk.Entry(a1, textvariable=self.amount_var, font=("Segoe UI", 11, "bold"),
                 justify="right").pack(fill="x", ipady=2)
        a2 = tk.Frame(r2, bg=C["card_bg"]); a2.pack(side="left", fill="x", expand=True, padx=(0, 6))
        label(a2, "VAT rate")
        self.rate_var = tk.StringVar(value="15%")
        ttk.Combobox(a2, textvariable=self.rate_var, state="readonly", width=10,
                     values=["15%", "5%", "0%", "No VAT"]).pack(fill="x")
        a3 = tk.Frame(r2, bg=C["card_bg"]); a3.pack(side="left", fill="x", expand=True)
        label(a3, "VAT amount")
        self.vat_var = tk.StringVar(value="0.00")
        self.vat_entry = tk.Entry(a3, textvariable=self.vat_var, font=("Segoe UI", 10),
                                  justify="right")
        self.vat_entry.pack(fill="x", ipady=2)
        self.incl_var = tk.BooleanVar(value=True)
        tk.Checkbutton(body, text="Amount includes VAT (as on the supplier's bill)",
                       variable=self.incl_var, font=("Segoe UI", 9), bg=C["card_bg"],
                       fg=C["text_primary"], activebackground=C["card_bg"],
                       command=self._recalc).pack(anchor="w", pady=(4, 0))
        self.sum_var = tk.StringVar()
        tk.Label(body, textvariable=self.sum_var, font=("Segoe UI", 10, "bold"),
                 bg=C["primary_light"], fg=C["primary"], anchor="w", padx=10,
                 pady=6).pack(fill="x", pady=(6, 0))
        self._manual_vat = False
        self.amount_var.trace_add("write", lambda *a: self._recalc())
        self.rate_var.trace_add("write", lambda *a: self._recalc(reset=True))
        self.vat_entry.bind("<KeyRelease>", lambda e: self._vat_typed())

        # payment
        label(body, "Paid by")
        self.method_var = tk.StringVar(value="cash")
        mrow = tk.Frame(body, bg=C["card_bg"]); mrow.pack(fill="x")
        for val in ("cash", "bank", "card"):
            tk.Radiobutton(mrow, text=val.title(), value=val, variable=self.method_var,
                           font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                           activebackground=C["card_bg"], selectcolor="white",
                           command=self._toggle_credit).pack(side="left", padx=(0, 10))
        self.on_credit = tk.BooleanVar(value=False)
        tk.Checkbutton(mrow, text="On credit (pay the supplier later)",
                       variable=self.on_credit, font=("Segoe UI", 9), bg=C["card_bg"],
                       fg=C["text_secondary"], activebackground=C["card_bg"],
                       command=self._toggle_credit).pack(side="left", padx=(8, 0))

        label(body, "Supplier  (needed for 'on credit'; shown on the VAT detail)")
        self.sup_var = tk.StringVar()
        self.sup_cb = ttk.Combobox(body, textvariable=self.sup_var, state="readonly",
                                   values=["—"] + [x["supplier_name_en"] for x in self.suppliers])
        self.sup_cb.pack(fill="x")
        label(body, "Description")
        self.desc_var = tk.StringVar()
        tk.Entry(body, textvariable=self.desc_var, font=("Segoe UI", 10)).pack(fill="x", ipady=2)

        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", padx=18, pady=12)
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#EEF1F6",
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self.win.destroy).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(btns, text="✓  Save  [F9]", font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg="white", relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self._save).pack(side="left", expand=True,
                                                           fill="x", padx=(4, 0))
        self.win.bind("<F9>", lambda e: self._save())
        self._kind_changed(first=True)

    def _kind_changed(self, first=False):
        asset = self.kind_var.get() == "asset"
        self.acct_label.config(text="Asset account *  (Furniture, Equipment, Vehicles …)"
                               if asset else "Expense account *")
        vals = self._acct_values()
        self.acct_cb.config(values=vals)
        if self.acct_var.get() not in vals:
            self.acct_var.set(vals[0] if (asset and vals) else "")

    def _num(self, v):
        try:
            return float(str(v).replace(",", "") or 0)
        except Exception:
            return 0.0

    def _rate(self):
        r = self.rate_var.get()
        return 0.0 if r.startswith("No") else self._num(r.rstrip("%"))

    def _vat_typed(self):
        self._manual_vat = True
        self._recalc()

    def _split(self):
        """(net, vat, total) from the boxes."""
        amt = self._num(self.amount_var.get())
        vat = self._num(self.vat_var.get())
        if self.incl_var.get():
            return round(amt - vat, 2), round(vat, 2), round(amt, 2)
        return round(amt, 2), round(vat, 2), round(amt + vat, 2)

    def _recalc(self, reset=False):
        if reset:
            self._manual_vat = False
        if not self._manual_vat:
            amt = self._num(self.amount_var.get())
            r = self._rate() / 100.0
            vat = (amt * r / (1 + r)) if self.incl_var.get() else amt * r
            self.vat_var.set(f"{vat:.2f}")
        net, vat, total = self._split()
        self.sum_var.set(f"Net {money(net)}   +   VAT {money(vat)}   =   Total {money(total)} SAR")

    def _toggle_credit(self):
        pass                                   # supplier box is always visible

    def _load_existing(self):
        try:
            r = db.fetchone("SELECT e.*, a.account_code, a.account_name_en, "
                            "a.account_type FROM expenses e LEFT JOIN accounts a "
                            "ON a.account_id=e.expense_account_id WHERE e.expense_id=?",
                            (self.expense_id,)) or {}
        except Exception:
            r = {}
        if not r:
            return
        kind = r.get("expense_kind") or ("asset" if r.get("account_type") == "asset" else "expense")
        self.kind_var.set(kind)
        self._kind_changed()
        d = r.get("expense_date")
        self.date_var.set(d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")[:10])
        self.acct_var.set(f"{r.get('account_code')} · {r.get('account_name_en')}")
        net = float(r.get("amount") or 0); vat = float(r.get("vat_amount") or 0)
        incl = bool(r.get("price_incl_vat")) if r.get("price_incl_vat") is not None else False
        self.incl_var.set(incl)
        rate = r.get("vat_rate")
        if rate is None:
            rate = round(vat / net * 100) if net else 0
        rate = float(rate or 0)
        self.rate_var.set("No VAT" if (rate == 0 and vat == 0) else f"{rate:g}%")
        self.amount_var.set(f"{(net + vat) if incl else net:.2f}")
        self._manual_vat = True
        self.vat_var.set(f"{vat:.2f}")
        m = str(r.get("payment_method") or "cash")
        self.on_credit.set(m == "credit")
        self.method_var.set(m if m in ("cash", "bank", "card") else "cash")
        sid = r.get("supplier_id")
        name = next((x["supplier_name_en"] for x in self.suppliers
                     if x["supplier_id"] == sid), "") if sid else ""
        if not name and m == "credit":
            name = self._supplier_from_journal(r.get("journal_id")) or ""
        self.sup_var.set(name or "—")
        self.ref_var.set(r.get("reference") or "")
        self.desc_var.set(r.get("description") or "")
        self._recalc()

    def _supplier_from_journal(self, jid):
        """Older credit expenses didn't store the supplier: find it from
        the supplier ledger account the journal credited."""
        if not jid:
            return None
        try:
            rows = db.fetchall("SELECT a.account_name_en FROM journal_lines jl JOIN accounts a "
                               "ON a.account_id=jl.account_id WHERE jl.journal_id=? "
                               "AND jl.credit>0", (jid,)) or []
            names = {x["supplier_name_en"] for x in self.suppliers}
            for r in rows:
                n = str(r.get("account_name_en") or "")
                for nm in names:
                    if nm and nm in n:
                        return nm
        except Exception:
            pass
        return None

    # ── save ──────────────────────────────────────────────────
    def _save(self):
        net, vat, total = self._split()
        asset = self.kind_var.get() == "asset"
        what = "Asset purchase" if asset else "Expense"
        if not self.acct_var.get():
            messagebox.showwarning(what, "Pick an account.", parent=self.win)
            return
        if net <= 0:
            messagebox.showwarning(what, "Enter an amount.", parent=self.win)
            return
        if vat < 0 or vat > net:
            messagebox.showwarning(what, "Check the VAT amount.", parent=self.win)
            return
        from modules.date_utils import validate_invoice_date
        ok, vdate, err = validate_invoice_date(self.date_var.get().strip()
                                               or date.today().strftime("%Y-%m-%d"))
        if not ok:
            messagebox.showwarning(what, err, parent=self.win)
            return
        try:
            from modules import financial_year as fy
            msg = fy.guard_active(vdate)
            if not msg and self.expense_id:          # the saved entry's own date
                old = db.fetchone("SELECT expense_date FROM expenses WHERE expense_id=?",
                                  (self.expense_id,)) or {}
                if old.get("expense_date"):
                    msg = fy.guard_active(str(old["expense_date"])[:10])
            if msg:
                messagebox.showwarning(what, msg, parent=self.win)
                return
        except Exception:
            pass
        code = self.acct_var.get().split(" · ")[0]
        acc_id = ad._id_from_code(code)
        on_credit = self.on_credit.get()
        sname = self.sup_var.get()
        sup = next((x for x in self.suppliers if x["supplier_name_en"] == sname), None)
        sup_id = sup["supplier_id"] if sup else None
        if on_credit and not sup_id:
            messagebox.showwarning(what, "Pick the supplier for an 'on credit' entry.",
                                   parent=self.win)
            return
        if on_credit:
            posting.ensure_party_account("supplier", sup_id)
            paid_from = None
        else:
            paid_from = ad.method_account(self.method_var.get())
        method = "credit" if on_credit else self.method_var.get()
        rate = self._rate()
        ref = self.ref_var.get().strip()
        desc = self.desc_var.get().strip()
        extra = {"expense_kind": "asset" if asset else "expense", "supplier_id": sup_id,
                 "vat_rate": rate, "price_incl_vat": 1 if self.incl_var.get() else 0,
                 "supplier_vat_no": (sup or {}).get("vat_no") or None}
        _tx = None
        try:
            _tx = db.begin()           # v5.27: expense + journal are ONE transaction
            if self.expense_id:
                eid = self.expense_id
                old = db.fetchone("SELECT journal_id FROM expenses WHERE expense_id=?",
                                  (eid,)) or {}
                db.execute("UPDATE expenses SET expense_date=?, expense_account_id=?, "
                           "amount=?, vat_amount=?, payment_method=?, paid_from_account_id=?, "
                           "reference=?, description=?, journal_id=NULL WHERE expense_id=?",
                           (vdate, acc_id, net, vat, method, paid_from, ref, desc, eid))
                _delete_expense_journals(eid, old.get("journal_id"))
            else:
                db.execute(
                    "INSERT INTO expenses (expense_date, expense_account_id, amount, "
                    "vat_amount, payment_method, paid_from_account_id, reference, "
                    "description) VALUES (?,?,?,?,?,?,?,?)",
                    (vdate, acc_id, net, vat, method, paid_from, ref, desc))
                eid = db.last_identity("expenses", "expense_id")
            for col, val in extra.items():          # newer columns (patch)
                try:
                    db.execute(f"UPDATE expenses SET {col}=? WHERE expense_id=?", (val, eid))
                except Exception:
                    pass
            try:
                from modules import branches as _br
                _br.stamp("expenses", eid)
            except Exception:
                pass
            jid = posting.post_expense(eid, vdate, acc_id, net, vat=vat,
                                       method=self.method_var.get(),
                                       on_credit=on_credit, reference=ref,
                                       description=desc or what, supplier_id=sup_id)
            if jid:
                db.execute("UPDATE expenses SET journal_id=? WHERE expense_id=?",
                           (jid, eid))
            try:
                from modules import audit
                audit.log("edit" if self.expense_id else "create", "expenses", eid,
                          f"{code} {money(total)} {desc}")
            except Exception:
                pass
            _tx.commit()
            if not jid:
                messagebox.showwarning(
                    what, "Saved, but the journal could not be posted: "
                    + (posting.last_error or "check Default Accounts"), parent=self.win)
            messagebox.showinfo(what, f"{what} saved & posted.\n"
                                f"Net {money(net)} + VAT {money(vat)} = {money(total)} SAR",
                                parent=self.win)
            if self.on_saved:
                self.on_saved()
            self.win.destroy()
        except Exception as e:
            if _tx is not None and not _tx.kept:
                _tx.rollback()                # nothing of a failed save is kept
                e = "Not saved — nothing was kept.\n" + str(e)
            messagebox.showerror(what, str(e)[:300], parent=self.win)


def _delete_expense_journals(eid, jid=None):
    """Remove the journal(s) an expense posted (before re-posting / delete)."""
    if jid:
        db.execute("DELETE FROM journal_lines WHERE journal_id=?", (jid,))
        db.execute("DELETE FROM journal_entries WHERE journal_id=?", (jid,))
    db.execute("DELETE FROM journal_lines WHERE journal_id IN (SELECT "
               "journal_id FROM journal_entries WHERE source_type='expense' "
               "AND source_id=?)", (eid,))
    db.execute("DELETE FROM journal_entries WHERE source_type='expense' "
               "AND source_id=?", (eid,))
