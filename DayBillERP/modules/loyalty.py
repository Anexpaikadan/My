# ============================================================
# DayBill ERP - customer loyalty points (v6.9.2)
# ------------------------------------------------------------
# Settings ▸ Customer ▸ Loyalty points
#   loyalty_enabled        on / off (off: nothing is earned or spent)
#   loyalty_sar_per_point  spend this many SAR to earn 1 point   (10)
#   loyalty_point_value    what 1 point is worth when spent, SAR (0.10)
#   loyalty_min_redeem     fewest points that can be spent at once (50)
#
# Every confirmed sale to a named customer (not the cash / walk-in
# customer) earns points on what was paid for it; a sales return takes
# its points back. Points are spent on a bill as a discount — the
# discount is spread over the lines BEFORE VAT (doc_math), so taxable,
# VAT, the ZATCA e-invoice and the books stay right.
#
# loyalty_ledger keeps one row per movement; a bill's rows are written
# again from the saved bill every time it is posted (doc_posting.sync),
# so editing, re-saving, cancelling or deleting a bill can never count
# its points twice.
#
#   balance(customer_id)            points the customer has now
#   points_for(amount)              points a sale of `amount` earns
#   value_of(points)                SAR the points are worth
#   can_spend(customer_id, total)   most points usable on a bill
#   sync_sale(invoice_id) / sync_return(return_id) / remove(kind, id)
#   adjust(customer_id, points, note)
#   history(customer_id) / summary(date_from, date_to)
# ============================================================

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db
from config import settings as cfg

WALK_IN = ("CASH", "WALKIN", "WALK-IN", "CASH-001", "WALKIN-001")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def enabled():
    return cfg.flag("loyalty_enabled", False)


def sar_per_point():
    v = _f(cfg.get("loyalty_sar_per_point", 10))
    return v if v > 0 else 10.0


def point_value():
    v = _f(cfg.get("loyalty_point_value", 0.10))
    return v if v > 0 else 0.10


def min_redeem():
    return max(int(_f(cfg.get("loyalty_min_redeem", 50))), 1)


def points_for(amount):
    """Whole points a sale of `amount` SAR earns."""
    a = _f(amount)
    return int(math.floor(a / sar_per_point() + 1e-9)) if a > 0 else 0


def value_of(points):
    from modules.doc_math import r2
    return r2(max(int(points or 0), 0) * point_value())


def _ready():
    try:
        return db.execute_scalar("SELECT OBJECT_ID('loyalty_ledger','U')") is not None
    except Exception:
        return False


def is_walk_in(customer):
    """The cash / walk-in customer collects no points."""
    if not customer:
        return True
    code = str(customer.get("customer_code") or "").strip().upper()
    return code in WALK_IN or code.startswith("WALK")


def _customer(customer_id):
    if not customer_id:
        return None
    try:
        return db.fetchone("SELECT customer_id, customer_code, customer_name_en "
                           "FROM customers WHERE customer_id=?", (customer_id,))
    except Exception:
        return None


def balance(customer_id):
    if not customer_id or not _ready():
        return 0
    try:
        return int(db.execute_scalar("SELECT ISNULL(SUM(points),0) FROM loyalty_ledger "
                                     "WHERE customer_id=?", (customer_id,)) or 0)
    except Exception:
        return 0


def can_spend(customer_id, bill_total, already=0):
    """Most points usable on a bill: the customer's points (plus any this
    bill already spent, when it is edited), never more than the bill is
    worth, and nothing below the minimum."""
    if not enabled() or not customer_id:
        return 0
    have = balance(customer_id) + max(int(already or 0), 0)
    worth = int(math.floor(_f(bill_total) / point_value() + 1e-9))
    pts = max(min(have, worth), 0)
    return pts if pts >= min_redeem() else 0


def _write(customer_id, source_type, source_id, points, amount=None, note=""):
    if not points:
        return
    db.execute("INSERT INTO loyalty_ledger (customer_id, source_type, source_id, points, "
               "amount, note) VALUES (?,?,?,?,?,?)",
               (customer_id, source_type, source_id, int(points), amount, (note or "")[:200]))


def remove(kind, doc_id):
    """A bill / return that is cancelled or deleted gives its points back."""
    if not doc_id or not _ready():
        return
    src = "sales" if kind == "sales" else "sales_return"
    db.execute("DELETE FROM loyalty_ledger WHERE source_type=? AND source_id=?", (src, doc_id))


def sync_sale(invoice_id):
    """Write the points of a saved sales bill again (earned + spent)."""
    if not invoice_id or not _ready():
        return 0
    h = db.fetchone("SELECT * FROM sales_invoices WHERE invoice_id=?", (invoice_id,))
    if not h:
        remove("sales", invoice_id)
        return 0
    if not enabled():
        return 0                       # switched off: keep what is there, add nothing
    remove("sales", invoice_id)
    if str(h.get("invoice_status") or "").lower() != "confirmed":
        return 0
    if str(h.get("invoice_type_code") or "388") == "381":
        return 0                       # a credit note is not a sale
    cust = _customer(h.get("customer_id"))
    if is_walk_in(cust):
        return 0
    num = h.get("invoice_number") or ""
    spent = int(_f(h.get("loyalty_points_redeemed")))
    if spent > 0:
        _write(cust["customer_id"], "sales", invoice_id, -spent, value_of(spent),
               "Spent on bill %s" % num)
    earned = points_for(h.get("total_amount"))
    if earned > 0:
        _write(cust["customer_id"], "sales", invoice_id, earned, None,
               "Earned on bill %s" % num)
    return earned


def sync_return(return_id):
    """A sales return takes back the points its amount earned."""
    if not return_id or not _ready():
        return 0
    h = db.fetchone("SELECT * FROM sales_returns WHERE return_id=?", (return_id,))
    if not h:
        remove("sales_return", return_id)
        return 0
    if not enabled():
        return 0
    remove("sales_return", return_id)
    if str(h.get("return_status") or "confirmed").lower() != "confirmed":
        return 0
    cust = _customer(h.get("customer_id"))
    if is_walk_in(cust):
        return 0
    back = points_for(h.get("total_amount"))
    if back > 0:
        _write(cust["customer_id"], "sales_return", return_id, -back, None,
               "Return %s" % (h.get("return_number") or ""))
    return -back


def adjust(customer_id, points, note=""):
    """Points given or taken by hand (Customers ▸ Loyalty)."""
    if not customer_id or not int(points or 0) or not _ready():
        return False
    _write(customer_id, "adjust", None, int(points), None, note or "Adjusted by hand")
    return True


def history(customer_id, limit=200):
    if not customer_id or not _ready():
        return []
    try:
        return db.fetchall(
            "SELECT TOP %d entry_date, source_type, source_id, points, amount, note "
            "FROM loyalty_ledger WHERE customer_id=? ORDER BY entry_id DESC" % int(limit),
            (customer_id,)) or []
    except Exception:
        return []


def summary(date_from=None, date_to=None):
    """Per customer: earned / spent in the period and the balance now."""
    if not _ready():
        return []
    where, params = "", []
    if date_from:
        where += " AND CAST(l.entry_date AS DATE) >= ?"
        params.append(str(date_from)[:10])
    if date_to:
        where += " AND CAST(l.entry_date AS DATE) <= ?"
        params.append(str(date_to)[:10])
    try:
        rows = db.fetchall(
            "SELECT c.customer_id, c.customer_code, c.customer_name_en, c.phone, "
            "  ISNULL(SUM(CASE WHEN l.points > 0 AND 1=1 %s THEN l.points END),0) AS earned, "
            "  ISNULL(-SUM(CASE WHEN l.points < 0 AND 1=1 %s THEN l.points END),0) AS spent, "
            "  ISNULL(SUM(l.points),0) AS balance "
            "FROM loyalty_ledger l JOIN customers c ON c.customer_id=l.customer_id "
            "GROUP BY c.customer_id, c.customer_code, c.customer_name_en, c.phone "
            "ORDER BY balance DESC" % (where, where), tuple(params + params)) or []
    except Exception:
        return []
    return rows
