# ============================================================
# DayBill ERP - Settle receipts / payments against invoices
# ------------------------------------------------------------
# A customer receipt (or a supplier payment) can pay one or more
# open invoices. Each link is a row in payment_allocations and the
# invoice's paid_amount / payment_status move with it, so:
#   * invoice lists show Paid / Partial / Unpaid correctly
#   * vw_customer_balance, credit limit checks and aging are right
#   * editing or deleting the receipt gives the invoices back
#
#   open_documents(kind, party_id, payment_id=None)
#   auto_allocate(docs, amount)            -> {doc_id: amount}
#   apply(payment_id, kind, {doc_id: amt}) -> total allocated
#   release(payment_id)                    -> undo all its links
#   allocations(payment_id)                -> {doc_id: amount}
#   allocated_total(kind, doc_id)          -> money settled later
#   apply_return / release_return(kind, return_id)
#       (v6.9.1) a return put on the party's account — not refunded —
#       settles the bill it was made from, so that bill stops showing a
#       balance the customer / supplier no longer owes
# kind: "receipt" (sales invoices) | "disbursement" (purchases)
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _spec(kind):
    if kind == "receipt":
        return dict(table="sales_invoices", id="invoice_id", col="invoice_id",
                    party="customer_id")
    return dict(table="purchase_invoices", id="purchase_id", col="purchase_id",
                party="supplier_id")


def _status(paid, total):
    if paid >= total - 0.005:
        return "paid"
    return "partial" if paid > 0.005 else "unpaid"


def _bump(kind, doc_id, delta):
    """Add delta to a document's paid_amount and refresh its status."""
    s = _spec(kind)
    row = db.fetchone(f"SELECT ISNULL(total_amount,0) AS t, ISNULL(paid_amount,0) AS p "
                      f"FROM {s['table']} WHERE {s['id']}=?", (doc_id,))
    if not row:
        return
    total = _f(row["t"])
    paid = round(min(max(_f(row["p"]) + delta, 0.0), total), 2)
    db.execute(f"UPDATE {s['table']} SET paid_amount=?, payment_status=? "
               f"WHERE {s['id']}=?", (paid, _status(paid, total), doc_id))


def allocations(payment_id):
    """{doc_id: amount} already linked to this receipt/payment."""
    if not payment_id:
        return {}
    out = {}
    try:
        for r in db.fetchall("SELECT invoice_id, purchase_id, allocated_amount "
                             "FROM payment_allocations WHERE payment_id=?",
                             (payment_id,)) or []:
            k = r.get("invoice_id") or r.get("purchase_id")
            if k:
                out[k] = out.get(k, 0.0) + _f(r["allocated_amount"])
    except Exception:
        pass
    return out


def _payments_total(kind, doc_id):
    """Money settled on this document by later receipts/payments."""
    s = _spec(kind)
    try:
        return _f(db.execute_scalar(
            f"SELECT ISNULL(SUM(allocated_amount),0) FROM payment_allocations "
            f"WHERE {s['col']}=?", (doc_id,)))
    except Exception:
        return 0.0


def return_credit(kind, doc_id):
    """Returns put on the party's account that settle this document."""
    table = "sales_returns" if kind == "receipt" else "purchase_returns"
    try:
        return _f(db.execute_scalar(
            f"SELECT ISNULL(SUM(applied_amount),0) FROM {table} WHERE applied_bill_id=?",
            (doc_id,)))
    except Exception:
        return 0.0                                     # columns not there yet


def allocated_total(kind, doc_id):
    """Settled on this document after it was saved: receipts / payments
    and returns put on the party's account."""
    return round(_payments_total(kind, doc_id) + return_credit(kind, doc_id), 2)


def open_documents(kind, party_id, payment_id=None):
    """Confirmed invoices of the party that still have a balance —
    plus any this payment already settles (so an edit can change them).
    Oldest first."""
    if not party_id:
        return []
    s = _spec(kind)
    mine = allocations(payment_id)
    extra = ", ISNULL(invoice_type_code,'388') AS tcode" if kind == "receipt" else ""
    rows = db.fetchall(
        f"SELECT {s['id']} AS doc_id, invoice_number AS number, invoice_date AS doc_date, "
        f"due_date, ISNULL(total_amount,0) AS total, ISNULL(paid_amount,0) AS paid{extra} "
        f"FROM {s['table']} WHERE {s['party']}=? AND invoice_status='confirmed' "
        f"ORDER BY invoice_date, {s['id']}", (party_id,)) or []
    out = []
    for r in rows:
        if str(r.get("tcode") or "388") == "381":
            continue                                    # credit notes aren't paid
        total = _f(r["total"])
        mine_amt = mine.get(r["doc_id"], 0.0)
        paid_other = _f(r["paid"]) - mine_amt          # paid excluding this payment
        bal = round(total - paid_other, 2)
        if bal <= 0.005 and not mine_amt:
            continue
        out.append({"doc_id": r["doc_id"], "number": r["number"],
                    "date": str(r["doc_date"])[:10],
                    "due": str(r.get("due_date") or "")[:10],
                    "total": round(total, 2), "paid": round(paid_other, 2),
                    "balance": bal, "allocated": round(mine_amt, 2)})
    return out


def auto_allocate(docs, amount):
    """Spread an amount over the documents, oldest first."""
    left = round(_f(amount), 2)
    out = {}
    for d in docs:
        if left <= 0.005:
            break
        a = round(min(d["balance"], left), 2)
        if a > 0:
            out[d["doc_id"]] = a
            left = round(left - a, 2)
    return out


def release(payment_id):
    """Undo every link of this receipt/payment (before edit / delete)."""
    if not payment_id:
        return
    try:
        rows = db.fetchall("SELECT invoice_id, purchase_id, allocated_amount FROM "
                           "payment_allocations WHERE payment_id=?", (payment_id,)) or []
    except Exception:
        return
    for r in rows:
        amt = _f(r["allocated_amount"])
        if r.get("invoice_id"):
            _bump("receipt", r["invoice_id"], -amt)
        elif r.get("purchase_id"):
            _bump("disbursement", r["purchase_id"], -amt)
    db.execute("DELETE FROM payment_allocations WHERE payment_id=?", (payment_id,))


def apply(payment_id, kind, alloc):
    """Link the receipt/payment to documents: {doc_id: amount}."""
    s = _spec(kind)
    total = 0.0
    for doc_id, amt in (alloc or {}).items():
        amt = round(_f(amt), 2)
        if amt <= 0:
            continue
        db.execute(f"INSERT INTO payment_allocations (payment_id, {s['col']}, "
                   f"allocated_amount) VALUES (?,?,?)", (payment_id, doc_id, amt))
        _bump(kind, doc_id, amt)
        total += amt
    return round(total, 2)


def party_moved(kind, doc_id, party_id):
    """v6.9.5: True when a saved bill is being moved to another customer /
    supplier — then unlink_document() gives what the old party paid or
    returned on it back to the old party's account (an advance)."""
    s = _spec(kind)
    try:
        old = db.execute_scalar(f"SELECT {s['party']} FROM {s['table']} WHERE {s['id']}=?",
                                (doc_id,))
    except Exception:
        return False
    return bool(old and party_id and int(old) != int(party_id))


def unlink_document(kind, doc_id):
    """A cancelled / deleted invoice drops its links: the receipts that
    paid it become advances on the party's account again."""
    s = _spec(kind)
    try:
        amt = _payments_total(kind, doc_id)
        if amt:
            db.execute(f"DELETE FROM payment_allocations WHERE {s['col']}=?", (doc_id,))
        rc = return_credit(kind, doc_id)
        if rc:
            table = "sales_returns" if kind == "receipt" else "purchase_returns"
            db.execute(f"UPDATE {table} SET applied_bill_id=NULL, applied_amount=0 "
                       f"WHERE applied_bill_id=?", (doc_id,))
        if amt or rc:
            _bump(kind, doc_id, -(amt + rc))
        return amt
    except Exception:
        return 0.0


# ── returns on account settle their bill (v6.9.1) ─────────────
_REFUND = ("cash", "card", "mada", "cheque", "bank", "bank_transfer", "gateway")
_RET = {"sales_return": dict(table="sales_returns", ref="original_invoice_no",
                             party="customer_id", bill="receipt", default="cash"),
        "purchase_return": dict(table="purchase_returns", ref="original_purchase_no",
                                party="supplier_id", bill="disbursement", default="credit")}


def release_return(kind, return_id):
    """Give back what a return settled on its bill (before edit / delete)."""
    r = _RET.get(kind)
    if not r or not return_id:
        return 0.0
    try:
        row = db.fetchone(f"SELECT applied_bill_id AS b, ISNULL(applied_amount,0) AS a "
                          f"FROM {r['table']} WHERE return_id=?", (return_id,))
    except Exception:
        return 0.0                                     # columns not there yet
    if not row or not row.get("b"):
        return 0.0
    amt = _f(row["a"])
    if amt:
        _bump(r["bill"], row["b"], -amt)
    db.execute(f"UPDATE {r['table']} SET applied_bill_id=NULL, applied_amount=0 "
               f"WHERE return_id=?", (return_id,))
    return amt


def apply_return(kind, return_id):
    """A confirmed return put on the party's account (not refunded in
    cash / card / bank) settles the bill it was made from, up to what is
    still open on that bill. Safe to call again after an edit."""
    r = _RET.get(kind)
    if not r or not return_id:
        return 0.0
    release_return(kind, return_id)
    h = db.fetchone(f"SELECT * FROM {r['table']} WHERE return_id=?", (return_id,))
    if not h or "applied_bill_id" not in h:
        return 0.0
    if str(h.get("return_status") or "confirmed").lower() != "confirmed":
        return 0.0
    on_acc = _f(h.get("total_amount"))
    try:                                   # v7.9: refunded in part (payment area rows)
        from modules import tenders as _td
        rows = _td.lines_for(kind, return_id)
    except Exception:
        rows = []
    if rows:
        on_acc = round(on_acc - sum(_f(x.get("amount")) for x in rows if x.get("method") != "on_account"), 2)
        if on_acc <= 0.005:
            return 0.0
    elif (str(h.get("payment_method") or "").strip().lower() or r["default"]) in _REFUND:
        return 0.0
    ref = str(h.get(r["ref"]) or "").strip()
    if not ref:
        return 0.0
    s = _spec(r["bill"])
    sql = (f"SELECT TOP 1 {s['id']} AS id, ISNULL(total_amount,0) AS t, "
           f"ISNULL(paid_amount,0) AS p FROM {s['table']} "
           f"WHERE invoice_number=? AND invoice_status='confirmed'")
    params = [ref]
    if h.get(r["party"]):
        sql += f" AND {s['party']}=?"
        params.append(h[r["party"]])
    bill = db.fetchone(sql + f" ORDER BY {s['id']} DESC", tuple(params))
    if not bill:
        return 0.0
    amt = round(min(on_acc, _f(bill["t"]) - _f(bill["p"])), 2)
    if amt <= 0.005:
        return 0.0
    _bump(r["bill"], bill["id"], amt)
    db.execute(f"UPDATE {r['table']} SET applied_bill_id=?, applied_amount=? "
               f"WHERE return_id=?", (bill["id"], amt, return_id))
    return amt


def doc_payments(kind, doc_id):
    """Receipts/payments that settled a document (for its history)."""
    s = _spec(kind)
    try:
        return db.fetchall(
            f"SELECT p.payment_number, p.payment_date, p.payment_method, "
            f"a.allocated_amount FROM payment_allocations a JOIN payments p "
            f"ON p.payment_id=a.payment_id WHERE a.{s['col']}=? "
            f"ORDER BY p.payment_date", (doc_id,)) or []
    except Exception:
        return []
