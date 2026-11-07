# ============================================================
# DayBill ERP - bank reconciliation (v6.0)
# ------------------------------------------------------------
# Match the books with the bank statement:
#   1. pick the bank (or card) account, the statement date and the
#      closing balance printed on the statement
#   2. tick every book line that appears on the statement
#   3. when  last reconciled balance + ticked lines = statement balance
#      (difference 0.00) → Finish. The ticked lines are marked as
#      cleared (journal_lines.rec_id) and never show again.
# What is left unticked = cheques not yet cashed, deposits in transit,
# or a missing entry (bank charges …) to post with a journal voucher.
# ============================================================
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        db.fetchone("SELECT TOP 1 rec_id FROM bank_reconciliations")
        db.fetchone("SELECT TOP 1 rec_id FROM journal_lines")
        return True
    except Exception:
        return False


def bank_accounts():
    """[(account_id, label)] — Bank, Card, Savings, Gateway + any asset
    account with 'bank' in its name."""
    ids = []
    try:
        from modules import account_defaults as ad
        for fn in (ad.bank, ad.card, ad.savings, ad.gateway):
            try:
                a = fn()
                if a and a not in ids:
                    ids.append(a)
            except Exception:
                pass
    except Exception:
        pass
    try:
        for r in db.fetchall("SELECT account_id FROM accounts WHERE account_type='asset' AND "
                             "ISNULL(is_active,1)=1 AND (account_name_en LIKE '%Bank%' OR "
                             "account_name_en LIKE '%bank%') ORDER BY account_code") or []:
            if r["account_id"] not in ids:
                ids.append(r["account_id"])
    except Exception:
        pass
    out = []
    for a in ids:
        r = db.fetchone("SELECT account_code, account_name_en FROM accounts WHERE account_id=?", (a,))
        if r:
            out.append((a, "%s — %s" % (r["account_code"], r["account_name_en"])))
    return out


def last_done(account_id):
    try:
        r = db.fetchone("SELECT TOP 1 * FROM bank_reconciliations WHERE account_id=? AND status='done' "
                        "ORDER BY statement_date DESC, rec_id DESC", (int(account_id),))
        return dict(r) if r else None
    except Exception:
        return None


def opening(account_id):
    """The balance already agreed with the bank (last finished statement)."""
    d = last_done(account_id)
    return round(_f(d.get("statement_balance")), 2) if d else 0.0


def draft(account_id):
    try:
        r = db.fetchone("SELECT TOP 1 * FROM bank_reconciliations WHERE account_id=? AND status='draft' "
                        "ORDER BY rec_id DESC", (int(account_id),))
        return dict(r) if r else None
    except Exception:
        return None


def start(account_id, statement_date, statement_balance):
    """Open (or update) the draft reconciliation of this account."""
    d = draft(account_id)
    sd = str(statement_date)[:10]
    bal = round(_f(statement_balance), 2)
    if d:
        db.execute("UPDATE bank_reconciliations SET statement_date=?, statement_balance=? WHERE rec_id=?",
                   (sd, bal, d["rec_id"]))
        return d["rec_id"]
    try:
        from modules import permissions as p
        uid = (p.session_user() or {}).get("user_id")
    except Exception:
        uid = None
    db.execute("INSERT INTO bank_reconciliations (account_id, statement_date, statement_balance, status, "
               "created_by) VALUES (?,?,?, 'draft', ?)", (int(account_id), sd, bal, uid))
    return db.last_identity("bank_reconciliations", "rec_id")


def lines(account_id, statement_date, rec_id=None):
    """Book lines of the account up to the statement date that are not
    cleared by a FINISHED reconciliation (ticked = in this draft)."""
    rows = db.fetchall(
        "SELECT jl.line_id, jl.debit, jl.credit, jl.description, jl.rec_id, je.entry_date, "
        "je.journal_number, je.reference, je.description_en, je.source_type FROM journal_lines jl "
        "JOIN journal_entries je ON je.journal_id=jl.journal_id WHERE jl.account_id=? AND "
        "je.is_posted=1 AND je.entry_date <= ? AND (jl.rec_id IS NULL OR jl.rec_id=?) "
        "ORDER BY je.entry_date, jl.line_id", (int(account_id), str(statement_date)[:10],
                                               int(rec_id or 0))) or []
    out = []
    for r in rows:
        r = dict(r)
        r["amount"] = round(_f(r["debit"]) - _f(r["credit"]), 2)
        r["ticked"] = bool(rec_id) and r.get("rec_id") == rec_id
        out.append(r)
    return out


def tick(rec_id, line_ids, on=True):
    ids = [int(x) for x in line_ids or []]
    if not ids:
        return 0
    with db.transaction():
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            if on:
                db.execute("UPDATE journal_lines SET rec_id=? WHERE line_id IN (%s) AND rec_id IS NULL"
                           % ",".join("?" * len(chunk)), (int(rec_id), *chunk))
            else:
                db.execute("UPDATE journal_lines SET rec_id=NULL WHERE line_id IN (%s) AND rec_id=?"
                           % ",".join("?" * len(chunk)), (*chunk, int(rec_id)))
    return len(ids)


def figures(rec_id):
    """{opening, ticked, cleared, statement, difference, book, unticked}."""
    r = dict(db.fetchone("SELECT * FROM bank_reconciliations WHERE rec_id=?", (int(rec_id),)) or {})
    if not r:
        return {}
    acc = r["account_id"]
    op = opening(acc)
    t = _f(db.execute_scalar("SELECT ISNULL(SUM(debit - credit),0) FROM journal_lines WHERE rec_id=?",
                             (int(rec_id),)))
    book = _f(db.execute_scalar(
        "SELECT ISNULL(SUM(jl.debit - jl.credit),0) FROM journal_lines jl JOIN journal_entries je ON "
        "je.journal_id=jl.journal_id WHERE jl.account_id=? AND je.is_posted=1 AND je.entry_date <= ?",
        (acc, str(r["statement_date"])[:10])))
    cleared = round(op + t, 2)
    st = round(_f(r["statement_balance"]), 2)
    return {"opening": op, "ticked": round(t, 2), "cleared": cleared, "statement": st,
            "difference": round(st - cleared, 2), "book": round(book, 2),
            "unticked": round(book - cleared, 2), "status": r.get("status")}


def finish(rec_id, notes=""):
    f = figures(rec_id)
    if not f:
        return False, "Reconciliation not found."
    if abs(f["difference"]) >= 0.005:
        return False, ("Difference %.2f — tick more lines (or post the missing bank charges / "
                       "interest with a journal voucher) until it is 0.00." % f["difference"])
    db.execute("UPDATE bank_reconciliations SET status='done', cleared_balance=?, difference=0, "
               "finished_at=GETDATE(), notes=? WHERE rec_id=?", (f["cleared"], (notes or "")[:300] or None,
                                                                 int(rec_id)))
    try:
        from modules import audit
        audit.log("add", "bank_rec", rec_id, "Bank reconciliation finished at %.2f" % f["statement"])
    except Exception:
        pass
    return True, "Reconciled ✓ — the books agree with the bank statement (%s)." % "{:,.2f}".format(
        f["statement"])


def undo_last(account_id):
    """Reopen the last finished reconciliation of the account (its lines
    become unticked again)."""
    d = last_done(account_id)
    if not d:
        return False, "Nothing to undo."
    with db.transaction():
        db.execute("UPDATE journal_lines SET rec_id=NULL WHERE rec_id=?", (d["rec_id"],))
        db.execute("DELETE FROM bank_reconciliations WHERE rec_id=?", (d["rec_id"],))
    return True, "The reconciliation of %s was undone." % str(d.get("statement_date"))[:10]


def history(account_id=None, limit=100):
    cond = "WHERE account_id=?" if account_id else ""
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT TOP %d * FROM bank_reconciliations %s ORDER BY statement_date DESC, rec_id DESC"
            % (int(limit), cond), (int(account_id),) if account_id else ()) or []]
    except Exception:
        return []
