# ============================================================
# DayBill ERP - cashier shifts (v6.0)
# ------------------------------------------------------------
#   open_shift(float)      the cashier starts: cash already in the drawer
#   current()              the open shift of THIS till (or None)
#   expected_cash(shift)   float + cash taken − cash given back
#   close_shift(counted)   the cashier counts the drawer ("blind count":
#                          the expected figure is not shown first); the
#                          difference is kept for the manager
#   summary(shift)         bills, sales, tenders, refunds, cash check
# Every POS bill / return made while a shift is open carries its
# shift_id. Settings ▸ POS ▸ "Cashier must open a shift" (off by default)
# makes the POS ask for the opening float before the first sale.
# ============================================================
import sys, os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        db.fetchone("SELECT TOP 1 shift_id FROM cashier_shifts")
        return True
    except Exception:
        return False


def _here():
    """(branch_id, counter_id) of this PC."""
    try:
        from modules import branches
        return branches.current()
    except Exception:
        return None, None


def _user():
    try:
        from modules import permissions as p
        u = p.session_user() or {}
        return u.get("user_id"), u.get("username") or ""
    except Exception:
        return None, ""


def required():
    try:
        from config import settings as cfg
        return bool(cfg.flag("pos_require_shift", False))
    except Exception:
        return False


def blind():
    try:
        from config import settings as cfg
        return bool(cfg.flag("pos_blind_count", True))
    except Exception:
        return True


def current(counter_id="this"):
    """The open shift of this till (dict) or None."""
    if not ready():
        return None
    cid = _here()[1] if counter_id == "this" else counter_id
    try:
        if cid:
            r = db.fetchone("SELECT TOP 1 * FROM cashier_shifts WHERE status='open' AND counter_id=? "
                            "ORDER BY shift_id DESC", (int(cid),))
        else:
            r = db.fetchone("SELECT TOP 1 * FROM cashier_shifts WHERE status='open' AND counter_id "
                            "IS NULL ORDER BY shift_id DESC")
        return dict(r) if r else None
    except Exception:
        return None


def current_id():
    s = current()
    return s["shift_id"] if s else None


def open_shift(opening_float, notes=""):
    """Start a shift on this till. → (shift_id, message)."""
    if not ready():
        return None, "Shifts need the v6.0 database update (Updates ▸ Apply)."
    if current():
        return None, "A shift is already open on this till — close it first."
    fl = round(_f(opening_float), 2)
    if fl < 0:
        return None, "The opening cash can't be below zero."
    br, cid = _here()
    uid, uname = _user()
    with db.transaction():
        db.execute("INSERT INTO cashier_shifts (counter_id, branch_id, user_id, username, opened_at, "
                   "opening_float, status, notes) VALUES (?,?,?,?,GETDATE(),?, 'open', ?)",
                   (cid, br, uid, uname[:50], fl, (notes or "")[:500] or None))
        sid = db.last_identity("cashier_shifts", "shift_id")
    try:
        from modules import audit
        audit.log("add", "shift", sid, "Shift opened, float %.2f" % fl)
    except Exception:
        pass
    return sid, "Shift opened with %.2f SAR in the drawer." % fl


def stamp(table, doc_id):
    """Mark a POS bill / return with the open shift (if any)."""
    sid = current_id()
    if not sid or not doc_id:
        return None
    pk = "invoice_id" if table == "sales_invoices" else "return_id"
    try:
        db.execute("UPDATE %s SET shift_id=? WHERE %s=?" % (table, pk), (sid, int(doc_id)))
    except Exception:
        return None
    return sid


def summary(shift):
    """Figures of one shift (dict row or id)."""
    if not isinstance(shift, dict):
        shift = dict(db.fetchone("SELECT * FROM cashier_shifts WHERE shift_id=?", (int(shift),)) or {})
    if not shift:
        return {}
    sid = shift["shift_id"]
    out = {"shift_id": sid, "opened_at": shift.get("opened_at"), "closed_at": shift.get("closed_at"),
           "username": shift.get("username"), "opening_float": _f(shift.get("opening_float")),
           "bills": 0, "sales": 0.0, "returns": 0.0, "cash_refunds": 0.0, "tenders": {}}
    try:
        r = db.fetchone("SELECT COUNT(*) AS n, SUM(ISNULL(total_amount,0)) AS t FROM sales_invoices "
                        "WHERE shift_id=? AND invoice_status='confirmed'", (sid,)) or {}
        out["bills"], out["sales"] = int(_f(r.get("n"))), round(_f(r.get("t")), 2)
    except Exception:
        pass
    try:
        from modules import tenders
        out["tenders"] = _shift_tenders(sid)
    except Exception:
        pass
    try:
        r = db.fetchone("SELECT SUM(ISNULL(total_amount,0)) AS t, SUM(CASE WHEN payment_method='cash' "
                        "THEN ISNULL(total_amount,0) ELSE 0 END) AS c FROM sales_returns "
                        "WHERE shift_id=? AND return_status='confirmed'", (sid,)) or {}
        out["returns"], out["cash_refunds"] = round(_f(r.get("t")), 2), round(_f(r.get("c")), 2)
    except Exception:
        pass
    cash_in = out["tenders"].get("cash", 0.0)
    out["expected_cash"] = round(out["opening_float"] + cash_in - out["cash_refunds"], 2)
    if shift.get("counted_cash") is not None:
        out["counted_cash"] = round(_f(shift.get("counted_cash")), 2)
        out["difference"] = round(out["counted_cash"] - out["expected_cash"], 2)
    return out


def _shift_tenders(sid):
    out = {}
    for r in db.fetchall(
            "SELECT pt.method, SUM(pt.amount) AS a FROM payment_tenders pt JOIN sales_invoices si "
            "ON si.invoice_id=pt.doc_id AND pt.doc_type='sales' WHERE si.shift_id=? "
            "AND si.invoice_status='confirmed' GROUP BY pt.method", (sid,)) or []:
        out[r["method"]] = round(_f(r["a"]), 2)
    r = db.fetchone("SELECT SUM(ISNULL(cash_paid,0)) AS c, SUM(ISNULL(card_paid,0)) AS k FROM "
                    "sales_invoices si WHERE si.shift_id=? AND si.invoice_status='confirmed' AND "
                    "NOT EXISTS (SELECT 1 FROM payment_tenders pt WHERE pt.doc_type='sales' AND "
                    "pt.doc_id=si.invoice_id)", (sid,)) or {}
    if _f(r.get("c")):
        out["cash"] = round(out.get("cash", 0.0) + _f(r.get("c")), 2)
    if _f(r.get("k")):
        out["card"] = round(out.get("card", 0.0) + _f(r.get("k")), 2)
    return out


def close_shift(counted_cash, notes="", shift=None):
    """Close the open shift with the cash counted in the drawer.
    → (summary dict, message)."""
    s = shift or current()
    if not s:
        return None, "No open shift on this till."
    counted = round(_f(counted_cash), 2)
    sm = summary(s)
    diff = round(counted - sm["expected_cash"], 2)
    with db.transaction():
        db.execute("UPDATE cashier_shifts SET closed_at=GETDATE(), expected_cash=?, counted_cash=?, "
                   "difference=?, status='closed', notes=COALESCE(?, notes) WHERE shift_id=? "
                   "AND status='open'",
                   (sm["expected_cash"], counted, diff, (notes or "")[:500] or None, s["shift_id"]))
    sm.update(counted_cash=counted, difference=diff, closed_at=datetime.now())
    try:
        from modules import audit
        audit.log("edit", "shift", s["shift_id"], "Shift closed: expected %.2f counted %.2f diff %.2f"
                  % (sm["expected_cash"], counted, diff))
    except Exception:
        pass
    if abs(diff) < 0.005:
        msg = "Shift closed — the drawer is exactly right ✓"
    elif diff > 0:
        msg = "Shift closed — %.2f SAR MORE than expected in the drawer." % diff
    else:
        msg = "Shift closed — %.2f SAR SHORT in the drawer." % -diff
    return sm, msg


def history(date_from=None, date_to=None, limit=200):
    """Closed + open shifts for the report (newest first)."""
    if not ready():
        return []
    cond, params = [], []
    if date_from:
        cond.append("opened_at >= ?"); params.append(str(date_from)[:10])
    if date_to:
        cond.append("opened_at < DATEADD(day, 1, ?)"); params.append(str(date_to)[:10])
    try:
        rows = db.fetchall("SELECT TOP %d * FROM cashier_shifts %s ORDER BY shift_id DESC"
                           % (int(limit), ("WHERE " + " AND ".join(cond)) if cond else ""),
                           tuple(params)) or []
    except Exception:
        return []
    return [dict(r) for r in rows]
