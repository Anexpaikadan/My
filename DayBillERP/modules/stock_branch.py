# ============================================================
# DayBill ERP - stock per branch + transfers between branches (v6.0)
# ------------------------------------------------------------
# The company total stays in products.stock_quantity (every report and
# screen keeps working). A branch's stock comes from the stock card:
#     inventory_transactions.branch_id
# Rows with no branch (everything before v6.0, one-branch shops) belong
# to the MAIN branch, so:
#     other branch  = Σ (in − out) of its rows
#     main branch   = company total − Σ other branches
# That can never drift away from the company total.
#
#   transfer(from, to, lines)   moves stock: out of one branch, into the
#                               other (company total and value unchanged,
#                               so no journal), batches + expiry move too
#   delete_transfer(id)         undoes it
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
        db.fetchone("SELECT TOP 1 branch_id FROM inventory_transactions")
        db.fetchone("SELECT TOP 1 transfer_id FROM stock_transfers")
        return True
    except Exception:
        return False


def branches():
    try:
        from modules import branches as BR
        return [b for b in BR.list_branches() if b.get("is_active", 1) in (1, True, None)]
    except Exception:
        return []


def main_branch_id():
    try:
        v = db.execute_scalar("SELECT MIN(branch_id) FROM branches WHERE ISNULL(is_active,1)=1")
        return int(v) if v else None
    except Exception:
        return None


def here():
    """Branch of THIS PC (its counter's branch), else the main branch."""
    try:
        from modules import branches as BR
        b = BR.current()[0]
        if b:
            return int(b)
    except Exception:
        pass
    return main_branch_id()


def branch_name(bid):
    b = next((x for x in branches() if x.get("branch_id") == bid), None)
    return (b or {}).get("name_en") or ("Branch %s" % bid if bid else "Main")


def multi():
    """More than one branch? (otherwise all of this stays out of sight)"""
    return len(branches()) > 1


# ── stamping ─────────────────────────────────────────────────
def stamp_doc(reference_type, reference_id, branch_id=None):
    """Give a document's stock-card rows their branch."""
    b = branch_id or here()
    main = main_branch_id()
    if not b or b == main or not ready():
        return
    try:
        db.execute("UPDATE inventory_transactions SET branch_id=? WHERE reference_type=? AND "
                   "reference_id=? AND branch_id IS NULL", (int(b), reference_type, int(reference_id)))
    except Exception:
        pass


def stamp_last(branch_id=None):
    """Give the stock-card row this PC just wrote its branch."""
    b = branch_id or here()
    if not b or b == main_branch_id() or not ready():
        return
    try:
        tid = db.last_identity("inventory_transactions", "txn_id")
        if tid:
            db.execute("UPDATE inventory_transactions SET branch_id=? WHERE txn_id=? AND "
                       "branch_id IS NULL", (int(b), int(tid)))
    except Exception:
        pass


# ── quantities ───────────────────────────────────────────────
def qty_by_branch(product_ids=None):
    """{product_id: {branch_id: qty}} for every active branch."""
    brs = [b["branch_id"] for b in branches()]
    main = main_branch_id()
    if not brs:
        return {}
    cond, params = "", []
    if product_ids:
        ids = [int(p) for p in product_ids][:900]
        cond = " AND product_id IN (%s)" % ",".join("?" * len(ids))
        params = ids
    others = {}
    if ready():
        try:
            for r in db.fetchall(
                    "SELECT product_id, branch_id, SUM(ISNULL(qty_in_base,0) - ISNULL(qty_out_base,0)) AS q "
                    "FROM inventory_transactions WHERE branch_id IS NOT NULL AND branch_id<>?%s "
                    "GROUP BY product_id, branch_id" % cond, tuple([main or 0] + params)) or []:
                others.setdefault(r["product_id"], {})[r["branch_id"]] = round(_f(r["q"]), 4)
        except Exception:
            others = {}
    totals = {}
    try:
        for r in db.fetchall("SELECT product_id, ISNULL(stock_quantity,0) AS q FROM products WHERE 1=1"
                             + cond, tuple(params)) or []:
            totals[r["product_id"]] = _f(r["q"])
    except Exception:
        pass
    out = {}
    for pid, tot in totals.items():
        row = {b: 0.0 for b in brs}
        o = others.get(pid, {})
        for b, q in o.items():
            row[b] = q
        if main:
            row[main] = round(tot - sum(q for b, q in o.items() if b != main), 4)
        out[pid] = row
    return out


def branch_qty(product_id, branch_id):
    return _f(qty_by_branch([product_id]).get(int(product_id), {}).get(int(branch_id)))


# ── transfers ────────────────────────────────────────────────
def _next_number():
    try:
        from modules.doc_numbering import next_number
        return next_number("stock_transfers", "transfer_number", "TR")
    except Exception:
        return "TR-%s" % date.today().strftime("%Y%m%d%H%M%S")


def transfer(from_branch, to_branch, lines, notes="", when=None, allow_negative=None):
    """lines: [{"product_id", "quantity", "unit_name" (optional)}].
    → (transfer_id, number)."""
    if not ready():
        raise RuntimeError("Transfers need the v6.0 database update (Updates ▸ Apply).")
    fb, tb = int(from_branch or 0), int(to_branch or 0)
    if not fb or not tb:
        raise ValueError("Choose the branch the goods leave and the branch they go to.")
    if fb == tb:
        raise ValueError("The two branches must be different.")
    from modules import doc_posting as DP
    clean = []
    for ln in lines or []:
        pid = ln.get("product_id")
        q = _f(ln.get("quantity"))
        if not pid or q <= 0:
            continue
        f = DP.unit_factor(pid, ln.get("unit_name"))
        clean.append({"product_id": int(pid), "unit_name": ln.get("unit_name") or "Unit",
                      "factor": f, "quantity": q, "qty_base": round(q * f, 4),
                      "cost": DP.unit_cost(pid)})
    if not clean:
        raise ValueError("Add at least one product with a quantity.")
    if allow_negative is None:
        try:
            from config import settings as cfg
            allow_negative = bool(cfg.flag("allow_negative_stock", False))
        except Exception:
            allow_negative = False
    if not allow_negative:
        have = qty_by_branch([x["product_id"] for x in clean])
        need = {}
        for x in clean:
            need[x["product_id"]] = need.get(x["product_id"], 0.0) + x["qty_base"]
        short = []
        for pid, q in need.items():
            h = _f(have.get(pid, {}).get(fb))
            if h + 1e-6 < q:
                nm = db.execute_scalar("SELECT product_name_en FROM products WHERE product_id=?", (pid,))
                short.append("%s (has %g, needs %g)" % (nm, h, q))
        if short:
            raise ValueError("Not enough stock in %s: %s" % (branch_name(fb), "; ".join(short)))
    d = str(when or date.today().isoformat())[:10]
    try:
        from modules import permissions as p
        uid = (p.session_user() or {}).get("user_id")
    except Exception:
        uid = None
    with db.transaction():
        number = _next_number()
        db.execute("INSERT INTO stock_transfers (transfer_number, transfer_date, from_branch_id, "
                   "to_branch_id, status, notes, created_by) VALUES (?,?,?,?, 'done', ?, ?)",
                   (number, d, fb, tb, (notes or "")[:300] or None, uid))
        tid = db.execute_scalar("SELECT transfer_id FROM stock_transfers WHERE transfer_number=?",
                                (number,))
        for x in clean:
            db.execute("INSERT INTO stock_transfer_lines (transfer_id, product_id, unit_name, factor, "
                       "quantity, qty_base, unit_cost) VALUES (?,?,?,?,?,?,?)",
                       (tid, x["product_id"], x["unit_name"], x["factor"], x["quantity"],
                        x["qty_base"], round(x["cost"], 4)))
            bal = _f(db.execute_scalar("SELECT ISNULL(stock_quantity,0) FROM products WHERE "
                                       "product_id=?", (x["product_id"],)))
            for b, qin, qout, tt in ((fb, 0, x["qty_base"], "transfer_out"),
                                     (tb, x["qty_base"], 0, "transfer_in")):
                db.execute(
                    "INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type, "
                    "reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base, "
                    "balance_base, unit_cost, notes, branch_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (x["product_id"], d, tt, "stock_transfer", tid, x["unit_name"],
                     x["quantity"] if qin else 0, qin, x["quantity"] if qout else 0, qout, bal,
                     round(x["cost"], 4), ("%s %s → %s" % (number, branch_name(fb), branch_name(tb)))[:300],
                     b))
            try:                                         # batches + expiry go with the goods
                from modules import batches
                batches.move(x["product_id"], fb, tb, x["qty_base"], "stock_transfer", tid)
            except Exception:
                pass
    try:
        from modules import audit
        audit.log("add", "stock_transfer", tid, "%s: %d line(s) %s → %s"
                  % (number, len(clean), branch_name(fb), branch_name(tb)))
    except Exception:
        pass
    return tid, number


def delete_transfer(transfer_id):
    tid = int(transfer_id)
    with db.transaction():
        try:
            from modules import batches
            batches.reverse("stock_transfer", tid)
        except Exception:
            pass
        db.execute("DELETE FROM inventory_transactions WHERE reference_type='stock_transfer' "
                   "AND reference_id=?", (tid,))
        db.execute("DELETE FROM stock_transfer_lines WHERE transfer_id=?", (tid,))
        db.execute("DELETE FROM stock_transfers WHERE transfer_id=?", (tid,))
    try:
        from modules import audit
        audit.log("delete", "stock_transfer", tid, "Stock transfer deleted")
    except Exception:
        pass


def list_transfers(date_from=None, date_to=None, limit=300):
    if not ready():
        return []
    cond, params = [], []
    if date_from:
        cond.append("t.transfer_date >= ?"); params.append(str(date_from)[:10])
    if date_to:
        cond.append("t.transfer_date <= ?"); params.append(str(date_to)[:10])
    try:
        rows = db.fetchall(
            "SELECT TOP %d t.*, (SELECT COUNT(*) FROM stock_transfer_lines l WHERE "
            "l.transfer_id=t.transfer_id) AS n_lines, (SELECT SUM(l.qty_base * ISNULL(l.unit_cost,0)) "
            "FROM stock_transfer_lines l WHERE l.transfer_id=t.transfer_id) AS value FROM "
            "stock_transfers t %s ORDER BY t.transfer_id DESC"
            % (int(limit), ("WHERE " + " AND ".join(cond)) if cond else ""), tuple(params)) or []
    except Exception:
        return []
    out = []
    for r in rows:
        r = dict(r)
        r["from_name"], r["to_name"] = branch_name(r["from_branch_id"]), branch_name(r["to_branch_id"])
        out.append(r)
    return out


def transfer_lines(transfer_id):
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT l.*, p.product_code, p.product_name_en FROM stock_transfer_lines l JOIN products p "
            "ON p.product_id=l.product_id WHERE l.transfer_id=? ORDER BY l.line_id", (int(transfer_id),)) or []]
    except Exception:
        return []


def local_qty(product_id):
    """(qty here, company total, branch_id) — 'here' = this PC's branch when
    the shop has several branches; with one branch it is the company total,
    exactly as before. Used by counts and 'set stock to' adjustments."""
    try:
        total = _f(db.execute_scalar("SELECT ISNULL(stock_quantity,0) FROM products WHERE product_id=?",
                                     (int(product_id),)))
    except Exception:
        total = 0.0
    if not ready() or not multi():
        return total, total, None
    b = here()
    return branch_qty(product_id, b), total, b


def after_manual_move(product_id, delta_base, source_type="manual", source_id=0):
    """After a manual stock change wrote its stock-card row: give the row this
    PC's branch and take a loss out of the batches (first expiry first)."""
    stamp_last()
    if delta_base < 0:
        try:
            from modules import batches
            batches.consume(product_id, -delta_base, source_type, int(source_id or 0), here())
        except Exception:
            pass
