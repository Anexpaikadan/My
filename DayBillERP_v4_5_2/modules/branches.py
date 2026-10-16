# ============================================================
# DayBill ERP - Branches & counters (tills)
# ------------------------------------------------------------
# One shared database (LAN / server), one shared stock.
#   branch  = a shop / location
#   counter = a cash counter (billing / POS PC) inside a branch
#
# Every PC remembers which counter it is (config/app_settings.json →
# branch_id, counter_id). Sales, POS bills, returns, purchases,
# receipts / payments and expenses are stamped with it, so reports and
# Day Close can be filtered per counter or per branch.
# ============================================================

import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db
from config import settings as cfg

# document tables that carry branch_id / counter_id
STAMPED = {
    "sales_invoices": "invoice_id", "sales_returns": "return_id",
    "purchase_invoices": "purchase_id", "purchase_returns": "return_id",
    "payments": "payment_id", "expenses": "expense_id",
}


def _q(sql, params=()):
    try:
        return db.fetchall(sql, params) or []
    except Exception:
        return []


def pc_name():
    try:
        return (os.environ.get("COMPUTERNAME") or socket.gethostname() or "PC")[:100]
    except Exception:
        return "PC"


def tables_ready():
    try:
        db.execute_scalar("SELECT COUNT(*) FROM counters")
        return True
    except Exception:
        return False


def list_branches(active_only=False):
    return _q("SELECT branch_id, ISNULL(code,'') AS code, name_en, ISNULL(name_ar,'') AS name_ar, "
              "ISNULL(address,'') AS address, ISNULL(phone,'') AS phone, "
              "ISNULL(is_active,1) AS is_active FROM branches "
              + ("WHERE ISNULL(is_active,1)=1 " if active_only else "")
              + "ORDER BY branch_id")


def list_counters(branch_id=None, active_only=False):
    where, params = [], []
    if branch_id:
        where.append("c.branch_id=?"); params.append(int(branch_id))
    if active_only:
        where.append("ISNULL(c.is_active,1)=1")
    return _q("SELECT c.counter_id, c.branch_id, c.code, c.name_en, "
              "ISNULL(c.workstation,'') AS workstation, ISNULL(c.is_active,1) AS is_active, "
              "b.name_en AS branch_name FROM counters c "
              "LEFT JOIN branches b ON b.branch_id=c.branch_id "
              + ("WHERE " + " AND ".join(where) + " " if where else "")
              + "ORDER BY c.branch_id, c.counter_id", tuple(params))


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def current():
    """(branch_id, counter_id) of THIS PC. When only one counter exists it
    is chosen automatically. (None, None) before the tables exist."""
    if not tables_ready():
        return None, None
    cid = _int(cfg.get("counter_id"))
    counters = list_counters(active_only=True)
    row = next((c for c in counters if c["counter_id"] == cid), None)
    if row is None and len(counters) == 1:
        row = counters[0]
        bind_this_pc(row["counter_id"])
    if row is None:
        return _int(cfg.get("branch_id")), None
    return row["branch_id"], row["counter_id"]


def needs_choice():
    """True when this PC has no (valid) counter and there are several."""
    if not tables_ready():
        return False
    b, c = current()
    return c is None and len(list_counters(active_only=True)) > 1


def labels():
    """('Main Branch', 'Counter 1') for this PC ('' when unknown)."""
    b, c = current()
    bn = next((x["name_en"] for x in list_branches() if x["branch_id"] == b), "") if b else ""
    cn = next((x["name_en"] for x in list_counters() if x["counter_id"] == c), "") if c else ""
    return bn, cn


def bind_this_pc(counter_id):
    row = next((c for c in list_counters() if c["counter_id"] == int(counter_id)), None)
    if not row:
        return False
    cfg.set("counter_id", row["counter_id"])
    cfg.set("branch_id", row["branch_id"])
    try:
        cfg.save_settings()
    except Exception:
        pass
    try:
        db.execute("UPDATE counters SET workstation=? WHERE counter_id=?",
                   (pc_name(), row["counter_id"]))
    except Exception:
        pass
    return True


def stamp(table, doc_id):
    """Mark a new document with this PC's branch + counter (once — an edit
    made at another counter keeps the original)."""
    idcol = STAMPED.get(table)
    if not idcol or not doc_id:
        return
    b, c = current()
    if not b and not c:
        return
    try:
        db.execute(f"UPDATE {table} SET branch_id=?, counter_id=? "
                   f"WHERE {idcol}=? AND branch_id IS NULL", (b, c, int(doc_id)))
    except Exception:
        pass


# ── add / edit (limits come from the product key) ────────────
def _limit(kind):
    try:
        from modules import license as lic
        return lic.limits().get(kind)
    except Exception:
        return None


def save_branch(branch_id, name_en, name_ar="", code="", address="", phone="", active=True):
    """Returns (ok, message)."""
    name_en = (name_en or "").strip()
    if not name_en:
        return False, "Enter the branch name."
    if active:
        lim = _limit("branches")
        n = sum(1 for b in list_branches(active_only=True) if b["branch_id"] != branch_id)
        if lim is not None and n + 1 > lim:
            return False, (f"Your product key allows {lim} branch(es). "
                           "Ask your DayBill dealer for a key with more branches.")
    try:
        if branch_id:
            db.execute("UPDATE branches SET name_en=?, name_ar=?, code=?, address=?, phone=?, "
                       "is_active=? WHERE branch_id=?",
                       (name_en, name_ar, code, address, phone, 1 if active else 0, branch_id))
        else:
            db.execute("INSERT INTO branches (name_en, name_ar, code, address, phone, is_active) "
                       "VALUES (?,?,?,?,?,?)",
                       (name_en, name_ar, code, address, phone, 1 if active else 0))
        return True, "Saved."
    except Exception as e:
        return False, str(e)[:200]


def save_counter(counter_id, branch_id, code, name_en, active=True):
    code = (code or "").strip().upper()
    name_en = (name_en or "").strip()
    if not branch_id:
        return False, "Pick the branch."
    if not code or not name_en:
        return False, "Enter the counter code and name."
    others = [c for c in list_counters() if c["counter_id"] != counter_id]
    if any(c["code"].upper() == code for c in others):
        return False, f"Counter code {code} is already used."
    if active:
        lim = _limit("counters")
        n = sum(1 for c in others if c["is_active"])
        if lim is not None and n + 1 > lim:
            return False, (f"Your product key allows {lim} counter(s). "
                           "Ask your DayBill dealer for a key with more counters.")
    try:
        if counter_id:
            db.execute("UPDATE counters SET branch_id=?, code=?, name_en=?, is_active=? "
                       "WHERE counter_id=?", (int(branch_id), code, name_en,
                                              1 if active else 0, counter_id))
        else:
            db.execute("INSERT INTO counters (branch_id, code, name_en, is_active) "
                       "VALUES (?,?,?,?)", (int(branch_id), code, name_en, 1 if active else 0))
        return True, "Saved."
    except Exception as e:
        return False, str(e)[:200]


# ── counter takings (Day Close per counter, Counter-wise Sales) ──
def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def takings(date_from, date_to, counter_id=None, branch_id=None):
    """Per counter: bills, sales total, cash / card / credit taken on the
    bills, cash receipts (+ cash refunds from suppliers), cash refunds
    (returns), cash paid out (expenses + supplier payments + cash
    purchases) and the cash that should be in the drawer.
    Returns {counter_id: dict} (counter_id None = not recorded)."""
    try:
        from modules import account_defaults as ad
        cash_ids = {ad.cash()}
        card_ids = {ad.card(), ad.bank()}
    except Exception:
        cash_ids, card_ids = set(), set()
    cond, params = "", [date_from, date_to]
    if counter_id:
        cond += " AND counter_id=?"; params.append(int(counter_id))
    if branch_id:
        cond += " AND branch_id=?"; params.append(int(branch_id))
    out = {}

    def row(cid):
        return out.setdefault(cid, {"counter_id": cid, "bills": 0, "total": 0.0, "vat": 0.0,
                                    "cash": 0.0, "card": 0.0, "credit": 0.0,
                                    "receipts": 0.0, "refunds": 0.0, "paid_out": 0.0,
                                    "returns": 0.0})
    for r in _q("SELECT counter_id, COUNT(*) AS n, SUM(ISNULL(total_amount,0)) AS t, "
                "SUM(ISNULL(vat_amount,0)) AS v FROM sales_invoices "
                "WHERE invoice_status='confirmed' AND invoice_date BETWEEN ? AND ?" + cond
                + " GROUP BY counter_id", tuple(params)):
        x = row(r["counter_id"]); x["bills"] = int(_f(r["n"])); x["total"] = _f(r["t"])
        x["vat"] = _f(r["v"])
    for r in _q("SELECT si.counter_id, jl.account_id, SUM(jl.debit) AS d FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "JOIN sales_invoices si ON si.invoice_id=je.source_id "
                "WHERE je.source_type IN ('sales','pos') AND si.invoice_status='confirmed' "
                "AND si.invoice_date BETWEEN ? AND ?"
                + cond.replace("counter_id", "si.counter_id").replace("branch_id", "si.branch_id")
                + " GROUP BY si.counter_id, jl.account_id", tuple(params)):
        x = row(r["counter_id"])
        if r["account_id"] in cash_ids:
            x["cash"] += _f(r["d"])
        elif r["account_id"] in card_ids:
            x["card"] += _f(r["d"])
    for x in out.values():
        x["credit"] = max(0.0, round(x["total"] - x["cash"] - x["card"], 2))
    for r in _q("SELECT counter_id, SUM(ISNULL(total_amount,0)) AS t, "
                "SUM(CASE WHEN LOWER(ISNULL(payment_method,'cash'))='cash' "
                "THEN ISNULL(total_amount,0) ELSE 0 END) AS c FROM sales_returns "
                "WHERE return_status='confirmed' AND return_date BETWEEN ? AND ?" + cond
                + " GROUP BY counter_id", tuple(params)):
        x = row(r["counter_id"]); x["returns"] = _f(r["t"]); x["refunds"] = _f(r["c"])
    for r in _q("SELECT counter_id, payment_type, SUM(amount) AS a FROM payments "
                "WHERE LOWER(payment_method)='cash' AND payment_date BETWEEN ? AND ?" + cond
                + " GROUP BY counter_id, payment_type", tuple(params)):
        x = row(r["counter_id"])
        if str(r["payment_type"]).lower() == "receipt":
            x["receipts"] += _f(r["a"])
        else:
            x["paid_out"] += _f(r["a"])
    for r in _q("SELECT counter_id, SUM(ISNULL(amount,0)+ISNULL(vat_amount,0)) AS a FROM expenses "
                "WHERE LOWER(ISNULL(payment_method,'cash'))='cash' "
                "AND expense_date BETWEEN ? AND ?" + cond + " GROUP BY counter_id", tuple(params)):
        row(r["counter_id"])["paid_out"] += _f(r["a"])
    # cash purchases paid from the drawer, cash refunds from suppliers (v5.26)
    for r in _q("SELECT counter_id, SUM(ISNULL(total_amount,0)) AS a FROM purchase_invoices "
                "WHERE invoice_status='confirmed' AND LOWER(ISNULL(payment_method,''))='cash' "
                "AND invoice_date BETWEEN ? AND ?" + cond + " GROUP BY counter_id", tuple(params)):
        row(r["counter_id"])["paid_out"] += _f(r["a"])
    for r in _q("SELECT counter_id, SUM(ISNULL(total_amount,0)) AS a FROM purchase_returns "
                "WHERE ISNULL(return_status,'confirmed')='confirmed' "
                "AND LOWER(ISNULL(payment_method,''))='cash' "
                "AND return_date BETWEEN ? AND ?" + cond + " GROUP BY counter_id", tuple(params)):
        row(r["counter_id"])["receipts"] += _f(r["a"])
    for x in out.values():
        x["expected_cash"] = round(x["cash"] + x["receipts"] - x["refunds"] - x["paid_out"], 2)
        for k in ("total", "vat", "cash", "card", "receipts", "refunds", "paid_out", "returns"):
            x[k] = round(x[k], 2)
    return out
