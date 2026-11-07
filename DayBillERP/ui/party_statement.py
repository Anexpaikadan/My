# ============================================================
# DayBill ERP — Party Statement (Customer / Supplier)
# ------------------------------------------------------------
# A ledger-style account statement for one customer or supplier:
#   Opening balance  →  every invoice (debit) and receipt/return
#   (credit)  →  running balance  →  closing balance, over a date
#   range, plus an aging summary (Current / 1-30 / 31-60 / 61-90 /
#   90+).  Exports to PDF and Excel.
#
# One engine, two entry points:
#   open_customer_statement(parent, customer_id)
#   open_supplier_statement(parent, supplier_id)
#
# "Customer" convention: invoices INCREASE what they owe (debit),
# receipts and sales-returns DECREASE it (credit). For a supplier
# it's the mirror: purchases increase what WE owe (credit to them),
# our payments and purchase-returns decrease it.
# ============================================================

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


# ── low-level helpers ───────────────────────────────────────
def _d(v):
    """Coerce a DB date/datetime/str to a date object (or None)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v)[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _money(x):
    try:
        return f"{float(x or 0):,.2f}"
    except Exception:
        return "0.00"


def _fetch(sql, params):
    try:
        return db.fetchall(sql, params) or []
    except Exception:
        return []


def _scalar(sql, params, default=0.0):
    try:
        v = db.execute_scalar(sql, params)
        return float(v) if v is not None else default
    except Exception:
        return default


# ============================================================
#  Build the statement data (party-agnostic)
# ============================================================
def build_statement(party_type, party_id, date_from=None, date_to=None):
    """Return a dict:
        {name, code, opening, rows[], debit_total, credit_total,
         closing, aging{...}}
    rows are dicts: {date, doc, ref, debit, credit, balance}

    v5.26: built from the party's own LEDGER account (the same numbers as
    the Trial Balance, Customer / Supplier Balances and Aging): opening
    balance, invoices, POS bills on account, receipts / payments,
    returns, expenses on credit and journal vouchers. "debit" = what
    increases the balance owed, "credit" = what reduces it.
    """
    is_cust = (party_type == "customer")
    tbl, col = ("customers", "customer") if is_cust else ("suppliers", "supplier")
    p = db.fetchone(
        f"SELECT {col}_code AS code, {col}_name_en AS name, account_id, "
        f"ISNULL(opening_balance,0) AS opening FROM {tbl} WHERE {col}_id=?",
        (party_id,)) or {}
    if not p.get("account_id"):
        return _build_from_documents(party_type, party_id, p, date_from, date_to)
    sign = 1 if is_cust else -1
    df, dt_to = _d(date_from), _d(date_to)
    lines = _fetch(
        "SELECT je.journal_id, je.entry_date AS dt, je.journal_number, je.source_type, "
        "je.reference, "
        "je.description_en, jl.description AS line_desc, jl.debit, jl.credit "
        "FROM journal_lines jl JOIN journal_entries je ON je.journal_id=jl.journal_id "
        "WHERE je.is_posted=1 AND jl.account_id=? ORDER BY je.entry_date, je.journal_id",
        (p["account_id"],))
    carried, rows = 0.0, []
    bal = None
    deb_total = cred_total = 0.0
    for r in lines:
        d = _d(r["dt"])
        amt = sign * (float(r["debit"] or 0) - float(r["credit"] or 0))
        if df and d and d < df:
            carried += amt
            continue
        if dt_to and d and d > dt_to:
            continue
        if bal is None:
            bal = carried
        deb, cred = (amt, 0.0) if amt >= 0 else (0.0, -amt)
        bal += deb - cred
        deb_total += deb
        cred_total += cred
        st = str(r.get("source_type") or "")
        doc = _DOC_LABEL.get(st, st.replace("_", " ").title() or "Entry")
        rows.append({"date": d.strftime("%Y-%m-%d") if d else "—",
                     "doc": doc, "ref": r.get("reference") or r.get("journal_number") or "",
                     "debit": deb, "credit": cred, "balance": bal,
                     "journal_id": r.get("journal_id")})
    if bal is None:
        bal = carried
    return {
        "name": p.get("name", ""), "code": p.get("code", ""),
        "opening": carried, "rows": rows,
        "debit_total": deb_total, "credit_total": cred_total,
        "closing": bal,
        "aging": _aging(party_type, party_id, dt_to or date.today()),
    }


_DOC_LABEL = {"sales": "Sales Invoice", "pos": "POS Bill", "purchase": "Purchase Invoice",
              "sales_return": "Sales Return", "purchase_return": "Purchase Return",
              "receipt": "Receipt", "payment": "Payment", "expense": "Expense",
              "opening_customer": "Opening Balance", "opening_supplier": "Opening Balance",
              "adjustment": "Journal", "journal": "Journal Voucher", "voucher": "Voucher"}


def _build_from_documents(party_type, party_id, p, date_from=None, date_to=None):
    """Older data (party without its own ledger account): build from the
    confirmed documents."""
    is_cust = (party_type == "customer")
    opening = float(p.get("opening", 0) or 0)

    events = []   # (date, doc_label, ref, debit, credit)

    if is_cust:
        # Debits: confirmed sales invoices — only what was left on account
        for r in _fetch(
                "SELECT invoice_number AS ref, invoice_date AS dt, "
                "ISNULL(total_amount,0) AS amt, ISNULL(paid_amount,0) AS paid "
                "FROM sales_invoices WHERE customer_id=? "
                "AND ISNULL(invoice_status,'')='confirmed'",
                (party_id,)):
            events.append((_d(r["dt"]), "Sales Invoice", r["ref"],
                           float(r["amt"] or 0), 0.0))
        # Credits: receipts
        for r in _fetch(
                "SELECT payment_number AS ref, payment_date AS dt, "
                "ISNULL(amount,0) AS amt FROM payments "
                "WHERE customer_id=? AND payment_type='receipt'", (party_id,)):
            events.append((_d(r["dt"]), "Receipt", r["ref"],
                           0.0, float(r["amt"] or 0)))
        # Credits: sales returns
        for r in _fetch(
                "SELECT return_number AS ref, return_date AS dt, "
                "ISNULL(total_amount,0) AS amt FROM sales_returns "
                "WHERE customer_id=? AND ISNULL(return_status,'confirmed')='confirmed'",
                (party_id,)):
            events.append((_d(r["dt"]), "Sales Return", r["ref"],
                           0.0, float(r["amt"] or 0)))
    else:
        # Supplier: debits = purchases (what we owe them)
        for r in _fetch(
                "SELECT invoice_number AS ref, invoice_date AS dt, "
                "ISNULL(total_amount,0) AS amt FROM purchase_invoices "
                "WHERE supplier_id=? AND ISNULL(invoice_status,'')='confirmed'",
                (party_id,)):
            events.append((_d(r["dt"]), "Purchase Invoice", r["ref"],
                           float(r["amt"] or 0), 0.0))
        # Credits: payments we made
        for r in _fetch(
                "SELECT payment_number AS ref, payment_date AS dt, "
                "ISNULL(amount,0) AS amt FROM payments "
                "WHERE supplier_id=? AND payment_type='disbursement'",
                (party_id,)):
            events.append((_d(r["dt"]), "Payment", r["ref"],
                           0.0, float(r["amt"] or 0)))
        # Credits: purchase returns
        for r in _fetch(
                "SELECT return_number AS ref, return_date AS dt, "
                "ISNULL(total_amount,0) AS amt FROM purchase_returns "
                "WHERE supplier_id=? AND ISNULL(return_status,'confirmed')='confirmed'",
                (party_id,)):
            events.append((_d(r["dt"]), "Purchase Return", r["ref"],
                           0.0, float(r["amt"] or 0)))

    # sort by date (undated events sort last within their bucket)
    far = date(2099, 12, 31)
    events.sort(key=lambda e: e[0] or far)

    df = _d(date_from)
    dt_to = _d(date_to)

    carried = opening
    in_range = []
    for ev_date, doc, ref, deb, cred in events:
        if df and ev_date and ev_date < df:
            carried += deb - cred
            continue
        if dt_to and ev_date and ev_date > dt_to:
            continue
        in_range.append((ev_date, doc, ref, deb, cred))

    rows = []
    bal = carried
    deb_total = cred_total = 0.0
    for ev_date, doc, ref, deb, cred in in_range:
        bal += deb - cred
        deb_total += deb
        cred_total += cred
        rows.append({
            "date": ev_date.strftime("%Y-%m-%d") if ev_date else "—",
            "doc": doc, "ref": ref,
            "debit": deb, "credit": cred, "balance": bal,
        })
    return {
        "name": p.get("name", ""), "code": p.get("code", ""),
        "opening": carried,
        "rows": rows,
        "debit_total": deb_total, "credit_total": cred_total,
        "closing": bal,
        "aging": _aging(party_type, party_id, dt_to or date.today()),
    }


def _aging(party_type, party_id, as_of):
    """Age of what is still owed (Receivable / Payable aging, first in
    first out): current = not yet due, then days overdue."""
    buckets = {"current": 0.0, "b30": 0.0, "b60": 0.0, "b90": 0.0, "b90p": 0.0,
               "advance": 0.0}
    try:
        from modules import aging as AG
        asof = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)
        for r in AG.party_aging(party_type, asof):
            if r["id"] == party_id:
                buckets.update(current=r["not_due"], b30=r["b30"], b60=r["b60"],
                               b90=r["b90"], b90p=r["b90p"], advance=r["advance"])
                break
    except Exception:
        pass
    return buckets


# ============================================================
#  Statement dialog (shared UI)
# ============================================================
class StatementDialog:
    def __init__(self, parent, party_type, party_id):
        self.party_type = party_type
        self.party_id = party_id
        C = cfg.theme()
        self.C = C
        title = "Customer Statement" if party_type == "customer" \
            else "Supplier Statement"

        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title(title)
        self.win.configure(bg=C["content_bg"])
        self.win.grab_set()
        self._center(900, 680)

        icon = "🧾" if party_type == "customer" else "📦"
        head = tk.Frame(self.win, bg=C["primary"], height=48)
        head.pack(fill="x"); head.pack_propagate(False)
        self.title_var = tk.StringVar(value=f"{icon}  {title}")
        tk.Label(head, textvariable=self.title_var, font=("Segoe UI", 14, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=18)

        # date range bar
        bar = tk.Frame(self.win, bg=C["content_bg"])
        bar.pack(fill="x", padx=16, pady=(10, 6))
        today = date.today()
        self.from_var = tk.StringVar(value=cfg.fiscal_year_bounds(today)[0].isoformat())
        self.to_var = tk.StringVar(value=today.isoformat())
        tk.Label(bar, text="From", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        f_e = tk.Entry(bar, textvariable=self.from_var, font=("Segoe UI", 10),
                       width=12, relief="solid", bd=1)
        f_e.pack(side="left", padx=(4, 12), ipady=3)
        tk.Label(bar, text="To", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        t_e = tk.Entry(bar, textvariable=self.to_var, font=("Segoe UI", 10),
                       width=12, relief="solid", bd=1)
        t_e.pack(side="left", padx=(4, 12), ipady=3)
        for e, v in ((f_e, self.from_var), (t_e, self.to_var)):
            try:
                from ui.datepicker import attach_datepicker
                attach_datepicker(e, v)
            except Exception:
                pass
        # quick ranges
        tk.Button(bar, text="This Month", font=("Segoe UI", 8), bg=C["card_bg"],
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: self._quick("month")).pack(side="left", padx=2)
        tk.Button(bar, text="This Year", font=("Segoe UI", 8), bg=C["card_bg"],
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: self._quick("year")).pack(side="left", padx=2)
        tk.Button(bar, text="🔄 Show", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=4,
                  cursor="hand2", command=self._run).pack(side="left", padx=(10, 0))
        tk.Button(bar, text="📄 PDF", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=4,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=lambda: self._export("pdf")).pack(side="right")
        tk.Button(bar, text="📥 Excel", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=4,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=lambda: self._export("excel")).pack(side="right", padx=(0, 8))

        # ledger table
        card = tk.Frame(self.win, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        cols = ("date", "doc", "ref", "debit", "credit", "balance")
        heads = {"date": ("Date", 90), "doc": ("Document", 130),
                 "ref": ("Reference", 130), "debit": ("Debit", 110),
                 "credit": ("Credit", 110), "balance": ("Balance", 120)}
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Stmt.Treeview", rowheight=26, font=("Segoe UI", 10))
        style.configure("Stmt.Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background=C.get("heading_bg", C["content_bg"]), foreground="#374151")
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 style="Stmt.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for c in cols:
            txt, w = heads[c]
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w,
                             anchor="e" if c in ("debit", "credit", "balance")
                             else ("center" if c == "date" else "w"))
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        # v6.9: double-click a line → its transaction (ui/txn_connector)
        self._row_journal = {}
        try:
            from ui import txn_connector as tc
            tc.bind_tree(self.tree, self._row_journal.get, self._run)
        except Exception:
            pass
        self.tree.tag_configure("open", font=("Segoe UI", 10, "italic"),
                                foreground="#6B7280")
        self.tree.tag_configure("close", font=("Segoe UI", 10, "bold"),
                                background="#EEF2FF")

        # summary + aging strip
        self.summary = tk.Frame(self.win, bg=C["content_bg"])
        self.summary.pack(fill="x", padx=16, pady=(0, 12))

        self._data = None
        self._run()

    # ── date helpers ───────────────────────────────────────
    def _quick(self, which):
        today = date.today()
        if which == "month":
            self.from_var.set(today.replace(day=1).isoformat())
        else:
            try:
                from config import settings as _cf
                self.from_var.set(_cf.fiscal_year_bounds(today)[0].isoformat())
            except Exception:
                self.from_var.set(today.replace(month=1, day=1).isoformat())
        self.to_var.set(today.isoformat())
        self._run()

    # ── run + render ───────────────────────────────────────
    def _run(self):
        try:
            data = build_statement(self.party_type, self.party_id,
                                   self.from_var.get(), self.to_var.get())
        except Exception as e:
            messagebox.showerror("Statement", str(e)[:200]); return
        self._data = data
        self.title_var.set(
            ("🧾  " if self.party_type == "customer" else "📦  ") +
            f"{data['name']}  ({data['code']})")

        self.tree.delete(*self.tree.get_children())
        self._row_journal.clear()
        # opening row
        self.tree.insert("", "end", tags=("open",), values=(
            self.from_var.get(), "Opening Balance", "", "", "",
            _money(data["opening"])))
        for r in data["rows"]:
            iid = self.tree.insert("", "end", values=(
                r["date"], r["doc"], r["ref"],
                _money(r["debit"]) if r["debit"] else "",
                _money(r["credit"]) if r["credit"] else "",
                _money(r["balance"])))
            if r.get("journal_id"):
                self._row_journal[iid] = r["journal_id"]
        # closing row
        self.tree.insert("", "end", tags=("close",), values=(
            self.to_var.get(), "Closing Balance", "",
            _money(data["debit_total"]), _money(data["credit_total"]),
            _money(data["closing"])))

        self._render_summary(data)

    def _render_summary(self, data):
        C = self.C
        for w in self.summary.winfo_children():
            w.destroy()
        owe = "owes you" if self.party_type == "customer" else "you owe"
        bal = data["closing"]
        bal_txt = f"{_money(abs(bal))} SAR " + (
            owe if bal > 0 else ("in credit" if bal < 0 else "settled"))
        tk.Label(self.summary, text="Closing balance: " + bal_txt,
                 font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left")

        ag = data["aging"]
        ag_frame = tk.Frame(self.summary, bg=C["content_bg"])
        ag_frame.pack(side="right")
        tk.Label(ag_frame, text="Aging:", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left",
                 padx=(0, 6))
        for label, key, col in [("Current", "current", "#16A34A"),
                                ("1-30", "b30", "#65A30D"),
                                ("31-60", "b60", "#CA8A04"),
                                ("61-90", "b90", "#EA580C"),
                                ("90+", "b90p", "#DC2626")]:
            v = ag.get(key, 0)
            cell = tk.Frame(ag_frame, bg=C["content_bg"])
            cell.pack(side="left", padx=6)
            tk.Label(cell, text=label, font=("Segoe UI", 8),
                     bg=C["content_bg"], fg=C["text_secondary"]).pack()
            tk.Label(cell, text=_money(v), font=("Segoe UI", 9, "bold"),
                     bg=C["content_bg"],
                     fg=col if v > 0.005 else C["text_secondary"]).pack()

    # ── export ─────────────────────────────────────────────
    def _export(self, kind):
        if not self._data:
            return
        d = self._data
        headers = ["Date", "Document", "Reference", "Debit", "Credit", "Balance"]
        body = [[self.from_var.get(), "Opening Balance", "", "", "",
                 _money(d["opening"])]]
        for r in d["rows"]:
            body.append([r["date"], r["doc"], r["ref"],
                         _money(r["debit"]) if r["debit"] else "",
                         _money(r["credit"]) if r["credit"] else "",
                         _money(r["balance"])])
        body.append([self.to_var.get(), "Closing Balance", "",
                     _money(d["debit_total"]), _money(d["credit_total"]),
                     _money(d["closing"])])
        ptype = "Customer" if self.party_type == "customer" else "Supplier"
        name = f"{ptype}_Statement_{d['code'] or d['name']}".replace(" ", "_")
        title = f"{ptype} Statement — {d['name']} ({d['code']})"
        ag = d["aging"]
        summary = [
            ("Period", f"{self.from_var.get()} to {self.to_var.get()}"),
            ("Opening", _money(d["opening"])),
            ("Total Debit", _money(d["debit_total"])),
            ("Total Credit", _money(d["credit_total"])),
            ("Closing", _money(d["closing"])),
            ("Aging",
             f"Current {_money(ag['current'])} · 1-30 {_money(ag['b30'])} · "
             f"31-60 {_money(ag['b60'])} · 61-90 {_money(ag['b90'])} · "
             f"90+ {_money(ag['b90p'])}"),
        ]
        try:
            if kind == "pdf":
                from modules.report_export import export_pdf
                export_pdf(self.win, name, headers, body, title=title,
                           subtitle=f"{self.from_var.get()} to {self.to_var.get()}",
                           summary=summary,
                           col_align=["center","left","left","right","right","right"])
            else:
                from modules.report_export import export_excel
                export_excel(self.win, name, headers, body, title=title,
                             summary=summary)
        except ImportError:
            messagebox.showerror("Export",
                                 "Install reportlab / openpyxl to export.")
        except Exception as e:
            messagebox.showerror("Export", str(e)[:200])

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ── public entry points ─────────────────────────────────────
def open_customer_statement(parent, customer_id):
    if not customer_id:
        messagebox.showinfo("Statement", "Select a customer first.")
        return
    StatementDialog(parent, "customer", customer_id)


def open_supplier_statement(parent, supplier_id):
    if not supplier_id:
        messagebox.showinfo("Statement", "Select a supplier first.")
        return
    StatementDialog(parent, "supplier", supplier_id)
