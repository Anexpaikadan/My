# ============================================================
# DayBill ERP - year-end closing (v6.0)
# ------------------------------------------------------------
# Closing a financial year used to only lock its dates. Now it also
# posts the CLOSING ENTRY on the last day of the year:
#     every revenue account  → Dr its balance
#     every expense account  → Cr its balance
#     the difference (profit / loss) → Retained Earnings (3300)
# so the new year starts with income and expenses at zero and the
# year's profit inside equity. The Profit & Loss report leaves the
# closing entry out (it still shows the year's real figures).
#
# Before closing, checks() lists what should be finished first:
# ZATCA documents not yet reported, draft invoices / purchases.
# reopen() removes the closing entry and unlocks the year.
# ============================================================
import sys, os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

SOURCE = "year_close"


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _year(fy_id):
    r = db.fetchone("SELECT * FROM financial_years WHERE fy_id=?", (int(fy_id),))
    return dict(r) if r else None


def _d(v):
    return str(v)[:10] if v else ""


def retained_earnings_account():
    try:
        a = db.execute_scalar("SELECT account_id FROM accounts WHERE account_code='3300'")
        if a:
            return a
        a = db.execute_scalar("SELECT TOP 1 account_id FROM accounts WHERE account_type='equity' AND "
                              "account_name_en LIKE '%Retained%'")
        if a:
            return a
        db.execute("INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, "
                   "is_active) VALUES ('3300', 'Retained Earnings', N'الأرباح المبقاة', 'equity', 1)")
        return db.execute_scalar("SELECT account_id FROM accounts WHERE account_code='3300'")
    except Exception:
        return None


def balances(fy_id):
    """[(account_id, code, name, type, balance)] of revenue / expense
    accounts for the year (revenue balance as credit +, expense as debit +),
    leaving out an earlier closing entry."""
    y = _year(fy_id)
    if not y:
        return []
    rows = db.fetchall(
        "SELECT a.account_id, a.account_code, a.account_name_en, a.account_type, "
        "ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr FROM journal_lines jl "
        "JOIN journal_entries je ON je.journal_id=jl.journal_id JOIN accounts a ON "
        "a.account_id=jl.account_id WHERE je.is_posted=1 AND je.entry_date BETWEEN ? AND ? "
        "AND a.account_type IN ('revenue','expense') AND ISNULL(je.source_type,'')<>? "
        "GROUP BY a.account_id, a.account_code, a.account_name_en, a.account_type "
        "ORDER BY a.account_code", (_d(y["start_date"]), _d(y["end_date"]), SOURCE)) or []
    out = []
    for r in rows:
        bal = (_f(r["cr"]) - _f(r["dr"])) if r["account_type"] == "revenue" else (_f(r["dr"]) - _f(r["cr"]))
        if abs(bal) >= 0.005:
            out.append((r["account_id"], r["account_code"], r["account_name_en"], r["account_type"],
                        round(bal, 2)))
    return out


def preview(fy_id):
    b = balances(fy_id)
    rev = round(sum(x[4] for x in b if x[3] == "revenue"), 2)
    exp = round(sum(x[4] for x in b if x[3] == "expense"), 2)
    return {"lines": b, "revenue": rev, "expenses": exp, "profit": round(rev - exp, 2)}


def checks(fy_id):
    """Things to finish before closing → [text] ('' list = ready)."""
    y = _year(fy_id)
    if not y:
        return ["Financial year not found."]
    f, t = _d(y["start_date"]), _d(y["end_date"])
    out = []
    for table, dcol, label in (("sales_invoices", "invoice_date", "sales invoice / bill"),
                               ("sales_returns", "return_date", "credit note")):
        try:
            n = db.execute_scalar("SELECT COUNT(*) FROM %s WHERE %s BETWEEN ? AND ? AND zatca_status "
                                  "IN ('waiting','fix','rejected')" % (table, dcol), (f, t))
            if n:
                out.append("%d %s(s) not yet accepted by ZATCA — ZATCA ▸ Send now / fix them."
                           % (n, label))
        except Exception:
            pass
    for table, dcol, scol, label in (("sales_invoices", "invoice_date", "invoice_status", "sales invoice"),
                                     ("purchase_invoices", "invoice_date", "invoice_status", "purchase")):
        try:
            n = db.execute_scalar("SELECT COUNT(*) FROM %s WHERE %s BETWEEN ? AND ? AND %s='draft'"
                                  % (table, dcol, scol), (f, t))
            if n:
                out.append("%d draft %s(s) in this year — confirm or delete them." % (n, label))
        except Exception:
            pass
    return out


def close(fy_id, force=False):
    """Post the closing entry and lock the year. → (ok, message)."""
    from modules import financial_year as fy, posting
    y = _year(fy_id)
    if not y:
        return False, "Financial year not found."
    if y.get("is_closed"):
        return False, "%s is already closed." % y.get("label")
    probs = checks(fy_id)
    if probs and not force:
        return False, "Finish these first:\n• " + "\n• ".join(probs)
    p = preview(fy_id)
    re_acc = retained_earnings_account()
    lines = []
    for acc, code, name, typ, bal in p["lines"]:
        if typ == "revenue":
            lines.append((acc, bal if bal > 0 else 0, -bal if bal < 0 else 0, "Close " + name))
        else:
            lines.append((acc, -bal if bal < 0 else 0, bal if bal > 0 else 0, "Close " + name))
    prof = p["profit"]
    if abs(prof) >= 0.005:
        lines.append((re_acc, -prof if prof < 0 else 0, prof if prof > 0 else 0,
                      "Profit of %s" % y.get("label") if prof > 0 else "Loss of %s" % y.get("label")))
    jid = None
    with db.transaction():
        db.execute("DELETE FROM journal_lines WHERE journal_id IN (SELECT journal_id FROM journal_entries "
                   "WHERE source_type=? AND source_id=?)", (SOURCE, int(fy_id)))
        db.execute("DELETE FROM journal_entries WHERE source_type=? AND source_id=?", (SOURCE, int(fy_id)))
        if lines:
            jid = posting.post_journal(_d(y["end_date"]), "Year-end closing %s" % y.get("label"), lines,
                                       SOURCE, int(fy_id), reference="CLOSE-%s" % y.get("label"),
                                       is_posted=True)
            if not jid:
                raise RuntimeError("The closing entry could not be posted: %s" % (posting.last_error or "?"))
        try:
            db.execute("UPDATE financial_years SET closing_journal_id=? WHERE fy_id=?", (jid, int(fy_id)))
        except Exception:
            pass
        ok, msg = fy.close_year(int(fy_id), lock_transactions=True)
        if not ok:
            raise RuntimeError(msg)
    try:
        from modules import audit
        audit.log("close", "financial_year", fy_id, "Year closed, profit %.2f to retained earnings" % prof)
    except Exception:
        pass
    return True, ("%s closed. %s of %s SAR moved to Retained Earnings; income and expense "
                  "accounts start the new year at zero." % (y.get("label"), "Profit" if prof >= 0 else "Loss",
                                                             "{:,.2f}".format(abs(prof))))


def reopen(fy_id):
    """Remove the closing entry and unlock the year."""
    from modules import financial_year as fy
    with db.transaction():
        ok, msg = fy.reopen_year(int(fy_id))
        if not ok:
            raise RuntimeError(msg)
        db.execute("DELETE FROM journal_lines WHERE journal_id IN (SELECT journal_id FROM journal_entries "
                   "WHERE source_type=? AND source_id=?)", (SOURCE, int(fy_id)))
        db.execute("DELETE FROM journal_entries WHERE source_type=? AND source_id=?", (SOURCE, int(fy_id)))
        try:
            db.execute("UPDATE financial_years SET closing_journal_id=NULL WHERE fy_id=?", (int(fy_id),))
        except Exception:
            pass
    try:
        from modules import audit
        audit.log("reopen", "financial_year", fy_id, "Year reopened, closing entry removed")
    except Exception:
        pass
    return True, "Year reopened — the closing entry was removed."
