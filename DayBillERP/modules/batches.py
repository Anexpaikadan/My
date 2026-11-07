# ============================================================
# DayBill ERP - batches & expiry dates (v6.0)
# ------------------------------------------------------------
# Products with "Track expiry dates" (Product ▸ Stock) get a batch for
# every purchase line: batch no. + expiry date + quantity (+ branch).
# Sales, purchase returns and stock losses take from the batch that
# expires FIRST (FEFO); a sales return goes back into the batch that
# expires last; transfers move batches between branches.
# Every change is a batch_movements row (source_type / source_id), so
# editing or deleting a document undoes it exactly.
#
#   receive(...) / consume(...) / move(...) / reverse(source_type, id)
#   near_expiry(days) / expired() / write_off(batch_ids)
# The product's stock total stays the truth; batches show WHICH goods
# (and when they expire).
# ============================================================
import sys, os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _d(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def ready():
    try:
        db.fetchone("SELECT TOP 1 batch_id FROM product_batches")
        return True
    except Exception:
        return False


def tracked(product_id):
    """Does this product keep batches? (Track expiry ticked, or it already
    has batches)."""
    if not product_id or not ready():
        return False
    try:
        if db.execute_scalar("SELECT ISNULL(track_expiry,0) FROM products WHERE product_id=?",
                             (int(product_id),)):
            return True
        return bool(db.execute_scalar("SELECT TOP 1 batch_id FROM product_batches WHERE product_id=?",
                                      (int(product_id),)))
    except Exception:
        return False


def _main():
    try:
        from modules import stock_branch
        return stock_branch.main_branch_id()
    except Exception:
        return None


def _log(batch_id, source_type, source_id, qty):
    db.execute("INSERT INTO batch_movements (batch_id, source_type, source_id, qty_base) VALUES (?,?,?,?)",
               (int(batch_id), str(source_type), int(source_id), round(qty, 4)))
    db.execute("UPDATE product_batches SET qty_base = qty_base + ? WHERE batch_id=?",
               (round(qty, 4), int(batch_id)))


def receive(product_id, qty_base, source_type, source_id, batch_no=None, expiry=None,
            branch_id=None, cost=None, received=None):
    """Goods in → a batch (an existing one with the same no. + expiry +
    branch grows)."""
    if not ready() or qty_base <= 0 or not product_id:
        return None
    exp = _d(expiry)
    bno = (str(batch_no).strip() or None) if batch_no else None
    b = branch_id or _main()
    found = None
    try:
        rows = db.fetchall("SELECT batch_id, batch_no, expiry_date, branch_id FROM product_batches "
                           "WHERE product_id=?", (int(product_id),)) or []
        for r in rows:
            if (str(r.get("batch_no") or "") == str(bno or "") and _d(r.get("expiry_date")) == exp
                    and (r.get("branch_id") or _main()) == b):
                found = r["batch_id"]
                break
    except Exception:
        found = None
    if not found:
        db.execute("INSERT INTO product_batches (product_id, branch_id, batch_no, expiry_date, qty_base, "
                   "unit_cost, received_date) VALUES (?,?,?,?,0,?,?)",
                   (int(product_id), b, bno, exp.isoformat() if exp else None,
                    round(_f(cost), 4) if cost else None,
                    (_d(received) or date.today()).isoformat()))
        found = db.last_identity("product_batches", "batch_id")
    _log(found, source_type, source_id, qty_base)
    return found


def _open_batches(product_id, branch_id=None, order="fefo"):
    rows = [dict(r) for r in db.fetchall(
        "SELECT batch_id, batch_no, expiry_date, qty_base, branch_id FROM product_batches "
        "WHERE product_id=? AND qty_base > 0", (int(product_id),)) or []]
    main = _main()
    if branch_id:
        same = [r for r in rows if (r.get("branch_id") or main) == branch_id]
        rows = same or rows                       # no batch in this branch → any branch
    far = date(9999, 12, 31)
    rows.sort(key=lambda r: (_d(r.get("expiry_date")) or far, r["batch_id"]),
              reverse=(order == "lefo"))
    return rows


def consume(product_id, qty_base, source_type, source_id, branch_id=None):
    """Goods out → take from the batch that expires first. Returns the
    quantity taken from batches (the rest had no batch)."""
    if not ready() or qty_base <= 0 or not tracked(product_id):
        return 0.0
    left, took = round(qty_base, 4), 0.0
    for r in _open_batches(product_id, branch_id):
        if left <= 1e-6:
            break
        t = min(_f(r["qty_base"]), left)
        if t <= 0:
            continue
        _log(r["batch_id"], source_type, source_id, -t)
        left = round(left - t, 4)
        took += t
    return round(took, 4)


def give_back(product_id, qty_base, source_type, source_id, branch_id=None):
    """A sales return: back into the batch that expires LAST (not expired)."""
    if not ready() or qty_base <= 0 or not tracked(product_id):
        return None
    rows = [dict(r) for r in db.fetchall(
        "SELECT batch_id, expiry_date, branch_id FROM product_batches WHERE product_id=?",
        (int(product_id),)) or []]
    main, today = _main(), date.today()
    rows = [r for r in rows if (_d(r.get("expiry_date")) or date(9999, 12, 31)) >= today] or rows
    if branch_id:
        rows = [r for r in rows if (r.get("branch_id") or main) == branch_id] or rows
    if not rows:
        return None
    rows.sort(key=lambda r: (_d(r.get("expiry_date")) or date(9999, 12, 31), r["batch_id"]))
    _log(rows[-1]["batch_id"], source_type, source_id, qty_base)
    return rows[-1]["batch_id"]


def move(product_id, from_branch, to_branch, qty_base, source_type, source_id):
    """Transfer: batches leave one branch (FEFO) and arrive in the other
    with the same batch no. and expiry."""
    if not ready() or qty_base <= 0 or not tracked(product_id):
        return
    left = round(qty_base, 4)
    main = _main()
    for r in _open_batches(product_id, from_branch):
        if left <= 1e-6:
            break
        if (r.get("branch_id") or main) != from_branch:
            continue
        t = min(_f(r["qty_base"]), left)
        _log(r["batch_id"], source_type, source_id, -t)
        receive(product_id, t, source_type, source_id, r.get("batch_no"), r.get("expiry_date"),
                branch_id=to_branch)
        left = round(left - t, 4)


def reverse(source_type, source_id):
    """Undo everything a document did to batches (edit / delete)."""
    if not ready() or not source_id:
        return 0
    rows = [dict(r) for r in db.fetchall(
        "SELECT move_id, batch_id, qty_base FROM batch_movements WHERE source_type=? AND source_id=?",
        (str(source_type), int(source_id))) or []]
    for r in rows:
        db.execute("UPDATE product_batches SET qty_base = qty_base - ? WHERE batch_id=?",
                   (round(_f(r["qty_base"]), 4), r["batch_id"]))
    if rows:
        db.execute("DELETE FROM batch_movements WHERE source_type=? AND source_id=?",
                   (str(source_type), int(source_id)))
        for bid in {r["batch_id"] for r in rows}:   # an empty batch nobody else used goes away
            try:
                left = db.execute_scalar("SELECT COUNT(*) FROM batch_movements WHERE batch_id=?", (bid,))
                q = _f(db.execute_scalar("SELECT qty_base FROM product_batches WHERE batch_id=?", (bid,)))
                if not left and abs(q) < 1e-6:
                    db.execute("DELETE FROM product_batches WHERE batch_id=?", (bid,))
            except Exception:
                pass
    return len(rows)


# ── what the shop sees ───────────────────────────────────────
def list_batches(product_id=None, only_open=True, branch_id=None):
    if not ready():
        return []
    cond, params = [], []
    if product_id:
        cond.append("b.product_id=?"); params.append(int(product_id))
    if only_open:
        cond.append("b.qty_base > 0")
    rows = [dict(r) for r in db.fetchall(
        "SELECT b.*, p.product_code, p.product_name_en FROM product_batches b JOIN products p "
        "ON p.product_id=b.product_id %s ORDER BY b.expiry_date, b.batch_id"
        % (("WHERE " + " AND ".join(cond)) if cond else ""), tuple(params)) or []]
    main = _main()
    if branch_id:
        rows = [r for r in rows if (r.get("branch_id") or main) == branch_id]
    today = date.today()
    for r in rows:
        e = _d(r.get("expiry_date"))
        r["days_left"] = (e - today).days if e else None
    rows.sort(key=lambda r: (r["days_left"] if r["days_left"] is not None else 10 ** 6, r["batch_id"]))
    return rows


def near_expiry(days=30, branch_id=None):
    """Open batches expiring within `days` (and the ones already expired)."""
    return [r for r in list_batches(branch_id=branch_id)
            if r["days_left"] is not None and r["days_left"] <= days]


def expired(branch_id=None):
    return [r for r in near_expiry(0, branch_id) if r["days_left"] < 0]


def alert_text(days=None):
    """One line for the dashboard ('' when nothing is close)."""
    try:
        from config import settings as cfg
        days = int(days if days is not None else (cfg.get("expiry_alert_days", 30) or 30))
    except Exception:
        days = 30
    rows = near_expiry(days)
    if not rows:
        return ""
    gone = [r for r in rows if r["days_left"] < 0]
    soon = [r for r in rows if r["days_left"] >= 0]
    parts = []
    if gone:
        parts.append("%d batch(es) EXPIRED" % len(gone))
    if soon:
        parts.append("%d batch(es) expire within %d days" % (len(soon), days))
    return "⏰ " + " · ".join(parts) + " — Inventory ▸ Batches & Expiry"


def write_off(batch_ids, note="Expired goods written off"):
    """Take expired / damaged batches out of stock: stock goes down, the
    loss is posted (Dr Stock Adjustment | Cr Inventory) and the batch is
    emptied. → (count, total base qty)."""
    from modules import doc_posting as DP
    n, total = 0, 0.0
    today = date.today().isoformat()
    with db.transaction():
        for bid in batch_ids or []:
            r = db.fetchone("SELECT * FROM product_batches WHERE batch_id=?", (int(bid),))
            if not r or _f(r.get("qty_base")) <= 0:
                continue
            q, pid = _f(r["qty_base"]), r["product_id"]
            db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) - ? "
                       "WHERE product_id=?", (q, pid))
            bal = _f(db.execute_scalar("SELECT ISNULL(stock_quantity,0) FROM products WHERE product_id=?",
                                       (pid,)))
            db.execute("INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type, "
                       "reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base, "
                       "balance_base, unit_cost, notes, branch_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (pid, today, "adjust_out", "batch_writeoff", int(bid), "Unit", 0, 0, q, q, bal,
                        round(DP.unit_cost(pid), 4),
                        ("%s — batch %s exp %s" % (note, r.get("batch_no") or "-",
                                                    str(r.get("expiry_date") or "")[:10]))[:300],
                        r.get("branch_id")))
            _log(int(bid), "batch_writeoff", int(bid), -q)
            DP.post_stock_adjustment(pid, -q, note=note, when=today, reference="EXP")
            n += 1
            total += q
    try:
        from modules import audit
        audit.log("edit", "batch_writeoff", None, "%d batch(es), %.2f units written off" % (n, total))
    except Exception:
        pass
    return n, round(total, 4)
