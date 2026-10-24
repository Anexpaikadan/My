# ============================================================
# DayBill ERP - Default Accounts settings tab
# ------------------------------------------------------------
# A self-contained Tk frame. Mount it anywhere:
#
#   from ui.account_defaults_tab import DefaultAccountsTab
#   DefaultAccountsTab(parent_frame).pack(fill="both", expand=True)
#
# It edits the same default-account map the posting engine reads, so
# changes take effect on the next transaction immediately.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules import account_defaults as ad
from modules import posting
from config.database import db

# (role key, label) grouped by section
DEFAULT_FIELDS = [
    ("Cash & Bank", [
        ("default_cash",       "Default Cash Account"),
        ("default_bank",       "Default Bank Account"),
        ("default_card",       "Card / Card Clearing"),
        ("default_savings",    "Savings Account"),
        ("default_gateway",    "Online Payment Gateway"),
        ("default_petty_cash", "Petty Cash Account"),
    ]),
    ("Sales & Purchase", [
        ("default_sales",          "Sales Revenue Account"),
        ("default_purchase",       "Purchase Account"),
        ("default_inventory",      "Inventory Account"),
        ("default_cogs",           "Cost of Goods Sold"),
        ("default_sales_return",   "Sales Return Account"),
        ("default_purchase_return","Purchase Return Account"),
        ("default_stock_adjust",   "Stock Adjustment (loss / gain)"),
        ("default_discount",       "Discount Account"),
        ("default_round_off",      "Round Off Account"),
    ]),
    ("Parties & Tax", [
        ("default_receivable",     "Customer Receivable"),
        ("default_payable",        "Supplier Payable"),
        ("default_tax_payable",    "Tax Payable (Output VAT)"),
        ("default_tax_receivable", "Tax Receivable (Input VAT)"),
        ("default_salary_expense", "Salary Expense Account"),
        ("default_opening_equity", "Opening Balance Equity"),
    ]),
]

def _C():
    from config import settings as _cfg
    return _cfg.theme()


PAYMENT_METHODS = [
    ("cash",          "Cash"),
    ("card",          "Card"),
    ("bank_transfer", "Bank Transfer"),
    ("gateway",       "Online Gateway"),
]


class DefaultAccountsTab(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=_C()["content_bg"], **kw)
        self._accounts = ad.all_accounts()          # (id, code, name, type)
        self._labels = [f"{c}  -  {n}" for (_id, c, n, _t) in self._accounts]
        self._code_by_label = {f"{c}  -  {n}": c for (_id, c, n, _t) in self._accounts}
        self._label_by_code = {c: f"{c}  -  {n}" for (_id, c, n, _t) in self._accounts}
        self._vars = {}
        self._method_vars = {}
        self._build()

    # ── account combobox bound to a role key ──────────────────
    def _account_combo(self, parent, key):
        var = tk.StringVar()
        cur = ad.acc(key)
        for (aid, code, name, _t) in self._accounts:
            if aid == cur:
                var.set(self._label_by_code.get(code, ""))
                break
        cb = ttk.Combobox(parent, textvariable=var, values=self._labels,
                          state="readonly", width=34)
        self._vars[key] = var
        try:                       # v7.0: type → the matching accounts drop down
            from ui import search_drop as _SD
            _SD.attach(cb, var, list(self._labels), width=380)
        except Exception:
            pass
        return cb

    def _build(self):
        head = tk.Frame(self, bg="white"); head.pack(fill="x")
        tk.Frame(self, bg=_C()["border"], height=1).pack(fill="x")
        tk.Label(head, text="🔗  Default Accounts", bg="white", fg=_C()["text_primary"],
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=16, pady=10)

        canvas = tk.Canvas(self, bg=_C()["content_bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=_C()["content_bg"])
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        scroll.pack(side="right", fill="y")

        # default-account sections
        for title, fields in DEFAULT_FIELDS:
            card = tk.LabelFrame(body, text="  " + title + "  ", bg="white",
                                 font=("Segoe UI", 10, "bold"), fg=_C()["primary_dark"],
                                 padx=14, pady=10)
            card.pack(fill="x", pady=8, padx=4)
            for r, (key, label) in enumerate(fields):
                tk.Label(card, text=label, bg="white", anchor="w",
                         font=("Segoe UI", 10)).grid(row=r, column=0,
                         sticky="w", pady=4, padx=(0, 12))
                self._account_combo(card, key).grid(row=r, column=1, sticky="w", pady=4)

        # payment-method -> ledger mapping
        pm = tk.LabelFrame(body, text="  Payment Method Ledgers  ", bg="white",
                           font=("Segoe UI", 10, "bold"), fg=_C()["primary_dark"],
                           padx=14, pady=10)
        pm.pack(fill="x", pady=8, padx=4)
        for r, (mcode, mlabel) in enumerate(PAYMENT_METHODS):
            tk.Label(pm, text=mlabel, bg="white", anchor="w",
                     font=("Segoe UI", 10)).grid(row=r, column=0, sticky="w",
                     pady=4, padx=(0, 12))
            var = tk.StringVar()
            cur = ad.method_account(mcode)
            for (aid, code, name, _t) in self._accounts:
                if aid == cur:
                    var.set(self._label_by_code.get(code, "")); break
            ttk.Combobox(pm, textvariable=var, values=self._labels,
                         state="readonly", width=34).grid(row=r, column=1,
                         sticky="w", pady=4)
            self._method_vars[mcode] = var

        tk.Button(body, text="💾  Save Default Accounts", bg=_C()["primary"], fg="white",
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=18, pady=8,
                  cursor="hand2", command=self._save).pack(anchor="w", padx=4, pady=12)

        # fund transfer mini-form
        self._build_transfer(body)

    def _build_transfer(self, body):
        ft = tk.LabelFrame(body, text="  Fund Transfer (Banking)  ", bg="white",
                           font=("Segoe UI", 10, "bold"), fg=_C()["primary_dark"],
                           padx=14, pady=10)
        ft.pack(fill="x", pady=8, padx=4)

        tk.Label(ft, text="From", bg="white").grid(row=0, column=0, sticky="w", pady=4)
        self._t_from = ttk.Combobox(ft, values=self._labels, state="readonly", width=30)
        self._t_from.grid(row=0, column=1, sticky="w", pady=4, padx=8)

        tk.Label(ft, text="To", bg="white").grid(row=1, column=0, sticky="w", pady=4)
        self._t_to = ttk.Combobox(ft, values=self._labels, state="readonly", width=30)
        self._t_to.grid(row=1, column=1, sticky="w", pady=4, padx=8)

        tk.Label(ft, text="Amount", bg="white").grid(row=2, column=0, sticky="w", pady=4)
        self._t_amt = tk.Entry(ft, width=16); self._t_amt.grid(row=2, column=1, sticky="w", pady=4, padx=8)

        tk.Label(ft, text="Reference", bg="white").grid(row=3, column=0, sticky="w", pady=4)
        self._t_ref = tk.Entry(ft, width=30); self._t_ref.grid(row=3, column=1, sticky="w", pady=4, padx=8)

        tk.Button(ft, text="Transfer", bg=_C()["success"], fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=16, pady=6, cursor="hand2",
                  command=self._do_transfer).grid(row=4, column=1, sticky="w", pady=8, padx=8)

    # ── actions ───────────────────────────────────────────────
    def _save(self):
        try:
            for key, var in self._vars.items():
                code = self._code_by_label.get(var.get())
                if code:
                    ad.set_default(key, code)
            for mcode, var in self._method_vars.items():
                code = self._code_by_label.get(var.get())
                if code:
                    ad.set_method_account(mcode, ad._id_from_code(code))
            ad.invalidate()
            messagebox.showinfo("Saved", "Default accounts updated.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _do_transfer(self):
        # a transfer posts a journal → needs the Journal 'add' right
        from modules import permissions as perm
        if not perm.allowed("journal", "add", parent=self):
            return
        try:
            from_code = self._code_by_label.get(self._t_from.get())
            to_code = self._code_by_label.get(self._t_to.get())
            amount = round(float((self._t_amt.get() or "0").replace(",", "")), 2)
            if not (from_code and to_code) or amount <= 0:
                messagebox.showwarning("Check", "Pick both accounts and an amount.")
                return
            if from_code == to_code:
                messagebox.showwarning("Check", "From and To must differ.")
                return
            from_id = ad._id_from_code(from_code)
            to_id = ad._id_from_code(to_code)
            ref = self._t_ref.get().strip()
            today = date.today().strftime("%Y-%m-%d")
            try:        # closed year / outside the login year
                from modules import financial_year as fy
                msg = fy.guard_active(today)
            except Exception:
                msg = ""
            if msg:
                messagebox.showwarning("Fund Transfer", msg, parent=self)
                return
            # money moves between accounts → ask first, showing what posts
            if not messagebox.askyesno(
                    "Fund Transfer",
                    f"Transfer {amount:,.2f} SAR?\n\n"
                    f"From:  {self._t_from.get()}\nTo:      {self._t_to.get()}\n"
                    f"Date:  {today}" + (f"\nRef:    {ref}" if ref else "") +
                    "\n\nA journal is posted (Dr To / Cr From).", parent=self):
                return
            # record the transfer, then post its journal and link them
            with db.transaction():          # transfer + journal together (v5.27)
                db.execute(
                    "INSERT INTO bank_transfers (transfer_date, from_account_id, "
                    "to_account_id, amount, reference) VALUES (?,?,?,?,?)",
                    (today, from_id, to_id, amount, ref))
                tid = db.last_identity("bank_transfers", "transfer_id")
                jid = posting.post_bank_transfer(tid, today, from_id, to_id, amount, ref)
                if not jid:
                    raise RuntimeError("journal not posted: " + (posting.last_error or
                                                                 "check the accounts"))
                db.execute("UPDATE bank_transfers SET journal_id=? WHERE transfer_id=?",
                           (jid, tid))
            try:
                from modules.doc_actions import audit
                audit("create", "bank_transfer", tid,
                      f"{amount:,.2f} SAR {from_code} → {to_code}"
                      + (f" ({ref})" if ref else ""))
            except Exception:
                pass
            messagebox.showinfo("Done", f"Transferred {amount:,.2f} SAR.")
            self._t_amt.delete(0, "end"); self._t_ref.delete(0, "end")
        except Exception as e:
            messagebox.showerror("Error", str(e))
