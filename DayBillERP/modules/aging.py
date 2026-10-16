# ============================================================
# DayBill ERP - Receivable / Payable aging (v5.26)
# ------------------------------------------------------------
# One source of truth: each customer's / supplier's own ledger account.
# The balance it shows is always the same as the Trial Balance and the
# party statement. Which bills are still open: a receipt / payment that
# was settled against bills on the payment screen (and a return made
# from a bill) closes those bills; money not tied to a bill settles the
# oldest bills first ("first in, first out").
#
#   Not due   — inside the payment terms (bill date + terms days)
#   1-30 / 31-60 / 61-90 / 90+  — days overdue
#   Advance   — the party paid more than they owe
#
# Used by Outstanding / Aging, the Reports Center (Receivable Aging,
# Payable Aging, Outstanding Bills) and the dashboard.
# ============================================================
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db

BUCKETS = [("not_due", "Not due"), ("b30", "1-30"), ("b60", "31-60"),
           ("b90", "61-90"), ("b90p", "90+")]

_TYPES = {"sales": "Sales invoice", "pos": "POS bill", "purchase": "Purchase invoice",
          "sales_return": "Sales return", "purchase_return": "Purchase return",
          "receipt": "Receipt", "payment": "Payment", "expense": "Expense",
          "opening_customer": "Opening balance", "opening_supplier": "Opening balance",
          "adjustment": "Journal", "journal": "Journal", "voucher": "Voucher"}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _d(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _bucket(days_over):
    if days_over <= 0:
        return "not_due"
    if days_over <= 30:
        return "b30"
    if days_over <= 60:
        return "b60"
    if days_over <= 90:
        return "b90"
    return "b90p"


def _parties(kind):
    tbl, pid, code, name = (("customers", "customer_id", "customer_code", "customer_name_en")
                            if kind == "customer" else
                            ("suppliers", "supplier_id", "supplier_code", "supplier_name_en"))
    try:
        rows = db.fetchall(f"SELECT * FROM {tbl}") or []
    except Exception:
        return []
    out = []
    for r in rows:
        out.append({"id": r.get(pid), "code": r.get(code) or "", "name": r.get(name) or "",
                    "phone": r.get("phone") or r.get("mobile") or "",
                    "account_id": r.get("account_id"),
                    "terms": int(_f(r.get("payment_terms_days"))) if r.get("payment_terms_days") is not None else 0,
                    "credit_limit": _f(r.get("credit_limit")),
                    "active": r.get("is_active", 1) in (1, True, None)})
    return out


def _control(kind):
    try:
        from modules import account_defaults as ad
        return ad.receivable() if kind == "customer" else ad.payable()
    except Exception:
        return None


def party_accounts(kind):
    """{account_id} that are real customer / supplier ledgers — sub-accounts
    of Accounts Receivable / Payable. (The 'Cash Customer' points at the
    Cash account on purpose; it is not a receivable.)"""
    ctrl = _control(kind)
    base = "1200" if kind == "customer" else "2100"
    try:
        code = db.execute_scalar("SELECT account_code FROM accounts WHERE account_id=?",
                                 (ctrl,)) if ctrl else None
        base = str(code or base)
        rows = db.fetchall("SELECT account_id, account_code, parent_account_id FROM accounts") or []
    except Exception:
        return set()
    return {r["account_id"] for r in rows
            if r["account_id"] != ctrl and (r.get("parent_account_id") == ctrl
                                            or str(r.get("account_code") or "").startswith(base + "-"))}


def _lines(account_ids, asof):
    """All posted lines of these accounts up to asof, oldest first."""
    ids = [int(a) for a in account_ids if a]
    if not ids:
        return {}
    out = defaultdict(list)
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        q = ("SELECT jl.account_id, je.entry_date, je.journal_number, je.source_type, "
             "je.source_id, je.reference, je.description_en, jl.debit, jl.credit "
             "FROM journal_lines jl JOIN journal_entries je ON je.journal_id=jl.journal_id "
             "WHERE je.is_posted=1 AND je.entry_date<=? AND jl.account_id IN (%s) "
             "ORDER BY je.entry_date, je.journal_id" % ",".join("?" * len(chunk)))
        for r in db.fetchall(q, (asof, *chunk)) or []:
            out[r["account_id"]].append(r)
    return out


def _links(kind):
    """How credits are tied to bills: (allocations, return_links).
    allocations  = {payment_id: {bill_id: amount}}  (receipts / payments
                   settled against invoices on the payment screen)
    return_links = {return_id: bill_id}  (returns made from an invoice)"""
    col, rtbl, btbl, bid = (("invoice_id", "sales_returns", "sales_invoices", "invoice_id")
                            if kind == "customer" else
                            ("purchase_id", "purchase_returns", "purchase_invoices",
                             "purchase_id"))
    alloc, rlink = defaultdict(dict), {}
    try:
        for r in db.fetchall(f"SELECT payment_id, {col} AS doc, allocated_amount FROM "
                             f"payment_allocations WHERE {col} IS NOT NULL") or []:
            d = alloc[r["payment_id"]]
            d[r["doc"]] = d.get(r["doc"], 0.0) + _f(r["allocated_amount"])
    except Exception:
        pass
    try:
        nums = {str(r["n"]).strip(): r["id"] for r in db.fetchall(
            f"SELECT {bid} AS id, invoice_number AS n FROM {btbl}") or [] if r.get("n")}
        for r in db.fetchall(f"SELECT return_id, original_invoice_no AS n FROM {rtbl} "
                             f"WHERE original_invoice_no IS NOT NULL") or []:
            b = nums.get(str(r["n"]).strip())
            if b:
                rlink[r["return_id"]] = b
    except Exception:
        pass
    return alloc, rlink


def _open_items(lines, kind, asof_d, terms, links=None):
    """(balance, [open item dicts]). Money received that was settled
    against a bill (payment screen) or a return made from a bill closes
    THAT bill first; whatever is not linked settles the oldest bills
    (first in, first out)."""
    sign = 1 if kind == "customer" else -1
    bal = round(sum(sign * (_f(r["debit"]) - _f(r["credit"])) for r in lines), 2)
    if bal <= 0.005:
        return bal, []
    alloc, rlink = links or ({}, {})
    bills = ("sales", "pos") if kind == "customer" else ("purchase",)
    pay_type = "receipt" if kind == "customer" else "payment"
    ret_type = "sales_return" if kind == "customer" else "purchase_return"
    debits, credits, by_bill = [], [], defaultdict(list)
    for r in lines:
        amt = round(sign * (_f(r["debit"]) - _f(r["credit"])), 2)
        st = str(r.get("source_type") or "")
        if amt > 0.005:
            it = {"r": r, "amount": amt, "rem": amt}
            debits.append(it)
            if st in bills and r.get("source_id"):
                by_bill[r["source_id"]].append(it)
        elif amt < -0.005:
            credits.append((st, r.get("source_id"), -amt))
    pool = 0.0
    for st, sid, amt in credits:
        left = amt
        targets = {}
        if st == pay_type and sid in alloc:
            targets = alloc[sid]
        elif st == ret_type and sid in rlink:
            targets = {rlink[sid]: amt}
        for bill, a in targets.items():
            for it in by_bill.get(bill, []):
                take = round(min(it["rem"], a, left), 2)
                if take <= 0:
                    continue
                it["rem"] = round(it["rem"] - take, 2)
                a = round(a - take, 2)
                left = round(left - take, 2)
        pool = round(pool + left, 2)
    for it in debits:                     # the rest: oldest bills first
        if pool <= 0.005:
            break
        take = round(min(it["rem"], pool), 2)
        it["rem"] = round(it["rem"] - take, 2)
        pool = round(pool - take, 2)
    items = []
    for it in debits:
        if it["rem"] <= 0.005:
            continue
        r = it["r"]
        d = _d(r["entry_date"]) or asof_d
        st = str(r.get("source_type") or "")
        due = d if st.startswith("opening") else d + timedelta(days=max(0, terms))
        items.append({"date": d.isoformat(), "due": due.isoformat(),
                      "type": _TYPES.get(st, st.replace("_", " ").title() or "Entry"),
                      "ref": r.get("reference") or r.get("journal_number") or "",
                      "jv": r.get("journal_number") or "",
                      "amount": it["amount"], "open": it["rem"],
                      "days": (asof_d - d).days, "overdue": (asof_d - due).days})
    gap = round(bal - sum(i["open"] for i in items), 2)
    if gap > 0.005:                      # rounding / history not shown
        items.insert(0, {"date": "", "due": "", "type": "Earlier balance", "ref": "", "jv": "",
                         "amount": gap, "open": gap, "days": 0, "overdue": 0})
    return bal, items


def party_aging(kind="customer", asof=None, include_zero=False):
    """Rows per party: code, name, phone, terms, not_due, b30, b60, b90,
    b90p, advance, balance, oldest (days), items [open bills]."""
    asof = asof or date.today().isoformat()
    asof_d = _d(asof) or date.today()
    ok_accounts = party_accounts(kind)
    parties = [p for p in _parties(kind) if p["account_id"] in ok_accounts]
    ctrl = _control(kind)
    lines = _lines([p["account_id"] for p in parties] + [ctrl], asof)
    links = _links(kind)
    rows = []
    for p in parties:
        bal, items = _open_items(lines.get(p["account_id"], []), kind, asof_d, p["terms"],
                                 links)
        if abs(bal) < 0.005 and not include_zero:
            continue
        row = {"id": p["id"], "code": p["code"], "name": p["name"], "phone": p["phone"],
               "terms": p["terms"], "credit_limit": p["credit_limit"],
               "advance": round(-bal, 2) if bal < 0 else 0.0,
               "balance": round(bal, 2), "items": items,
               "oldest": max([i["days"] for i in items] or [0])}
        for k, _ in BUCKETS:
            row[k] = 0.0
        for it in items:
            k = _bucket(it["overdue"])
            row[k] = round(row[k] + it["open"], 2)
        rows.append(row)
    # amounts posted to the control account itself (no party chosen)
    if ctrl and lines.get(ctrl):
        bal, items = _open_items(lines[ctrl], kind, asof_d, 0, links)
        if abs(bal) >= 0.005:
            row = {"id": None, "code": "", "name": "(No party — posted to the control account)",
                   "phone": "", "terms": 0, "credit_limit": 0.0,
                   "advance": round(-bal, 2) if bal < 0 else 0.0, "balance": round(bal, 2),
                   "items": items, "oldest": max([i["days"] for i in items] or [0])}
            for k, _ in BUCKETS:
                row[k] = 0.0
            for it in items:
                k = _bucket(it["overdue"])
                row[k] = round(row[k] + it["open"], 2)
            rows.append(row)
    rows.sort(key=lambda r: (-r["balance"], r["name"]))
    return rows


def totals(rows):
    t = {k: 0.0 for k, _ in BUCKETS}
    t.update(advance=0.0, balance=0.0)
    for r in rows:
        for k in t:
            t[k] = round(t[k] + _f(r.get(k)), 2)
    return t


def open_bills(kind="customer", asof=None):
    """Every bill still (partly) open, oldest first, with its party."""
    out = []
    for r in party_aging(kind, asof):
        for it in r["items"]:
            out.append(dict(it, party=r["name"], code=r["code"], phone=r["phone"]))
    out.sort(key=lambda x: (x["date"] or "0000", x["party"]))
    return out
