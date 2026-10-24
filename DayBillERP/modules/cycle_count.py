# ============================================================
# DayBill ERP - stock count with the phone: the cycle-count plan (v6.4)
# ------------------------------------------------------------
# Count a little every day instead of closing the shop for a full count:
#   A items (best sellers) every 7 days · B every 30 · C every 90
#   (Settings ▸ Inventory). plan() = today's list, most important first;
#   the phone shows it (Stock Count ▸ 📋 Today's list) and staff scan.
# A phone count waits for the owner (Settings ▸ Inventory ▸ "Phone stock
# counts wait for approval", on by default): Stock Count screen ▸ To
# approve shows system qty / counted / difference / value per line —
# approve the right lines, send the doubtful ones back to recount.
# Every counted line is kept in stock_count_log (history + accuracy).
# ============================================================

import json
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _d(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _cfg(key, default):
    try:
        from config import settings as cfg
        v = cfg.get(key, default)
        return default if v in (None, "") else v
    except Exception:
        return default


def every_days():
    out = {}
    for c, k, d in (("A", "count_every_a_days", 7), ("B", "count_every_b_days", 30),
                    ("C", "count_every_c_days", 90)):
        try:
            out[c] = max(1, int(float(_cfg(k, d))))
        except (TypeError, ValueError):
            out[c] = d
    return out


def needs_approval():
    try:
        from config import settings as cfg
        return bool(cfg.flag("count_needs_approval", True))
    except Exception:
        return True


def ready():
    try:
        db.fetchone("SELECT TOP 1 log_id FROM stock_count_log")
        return True
    except Exception:
        return False


def _user_id():
    try:
        from modules import permissions as p
        return (p.session_user() or {}).get("user_id")
    except Exception:
        return None


def last_counted():
    """{product_id: last date it was counted (approved)}"""
    if not ready():
        return {}
    return {r["product_id"]: _d(r["d"]) for r in (db.fetchall(
        "SELECT product_id, MAX(count_date) AS d FROM stock_count_log WHERE status='applied' "
        "GROUP BY product_id") or [])}


def _local_qty(pid):
    try:
        from modules import stock_branch as SB
        return _f(SB.local_qty(pid)[0])
    except Exception:
        r = db.fetchone("SELECT stock_quantity FROM products WHERE product_id=?", (pid,)) or {}
        return _f(r.get("stock_quantity"))


def _cost(pid):
    r = db.fetchone("SELECT ISNULL(average_cost,0) AS a, ISNULL(purchase_price,0) AS p "
                    "FROM products WHERE product_id=?", (pid,)) or {}
    return _f(r.get("a")) or _f(r.get("p"))


# ── today's list ─────────────────────────────────────────────
def plan(today=None, limit=None):
    """Items due for counting today, most important first:
    A before B before C, then the longest overdue, then stock value."""
    from modules import inventory_ai as IA
    today = today or date.today()
    every = every_days()
    try:
        limit = int(limit or float(_cfg("count_list_size", 40)))
    except (TypeError, ValueError):
        limit = 40
    cls = {r["product_id"]: r["class"] for r in IA.abc(days=90, today=today)["rows"]}
    last = last_counted()
    out = []
    for p in IA._products():
        if not IA._stocked(p):
            continue
        pid = p["product_id"]
        c = cls.get(pid, "C")
        stock = _f(p["stock"])
        if c == "C" and stock == 0 and pid not in cls:
            continue                                   # nothing on the shelf, not selling
        lc = last.get(pid)
        since = (today - lc).days if lc else None
        if since is not None and since < every[c]:
            continue
        overdue = 10 ** 5 if since is None else since - every[c]
        out.append({"product_id": pid, "code": p["product_code"], "name": p["product_name_en"],
                    "name_ar": p.get("product_name_ar") or "", "barcode": p.get("barcode") or "",
                    "class": c, "every_days": every[c],
                    "last_counted": lc.isoformat() if lc else None,
                    "days_since": since, "stock": round(stock, 3),
                    "value": round(max(stock, 0) * IA._cost(p), 2), "_overdue": overdue})
    out.sort(key=lambda r: ("ABC".index(r["class"]), -r["_overdue"], -r["value"]))
    for r in out:
        r.pop("_overdue", None)
    return out[:max(1, limit)]


# ── applying a count (phone or desktop) ──────────────────────
def counted_by_product(lines):
    from modules import mobile_api as M
    out = {}
    for ln in lines:
        if ln.get("product_id"):
            out[int(ln["product_id"])] = out.get(int(ln["product_id"]), 0.0) + M._base_qty(ln)
    return out


def log_line(pid, system_qty, counted_qty, status="applied", doc_id=None, source=None,
             counted_by=None, approved_by=None, note=None):
    if not ready():
        return
    cost = _cost(pid)
    diff = _f(counted_qty) - _f(system_qty)
    branch = None
    try:
        from modules import stock_branch as SB
        branch = SB.here()
    except Exception:
        pass
    db.execute("INSERT INTO stock_count_log (product_id, branch_id, count_date, system_qty, counted_qty, "
               "diff_qty, unit_cost, diff_value, status, doc_id, source, counted_by, approved_by, note) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (int(pid), branch, date.today().isoformat(), round(_f(system_qty), 4),
                round(_f(counted_qty), 4), round(diff, 4), round(cost, 4), round(diff * cost, 2),
                status, doc_id, (source or "")[:20], counted_by, approved_by, (note or "")[:300] or None))


def apply_lines(doc, approve_pids=None, by_user=None):
    """Inside the caller's transaction: counted qty → this branch's stock for
    the approved products (all when approve_pids is None); the others are
    logged 'recount' (they stay on the list). → (applied, changed, recount)"""
    from modules import mobile_api as M
    lines = json.loads(doc.get("lines_json") or "[]")
    counted = counted_by_product(lines)
    ok = set(counted) if approve_pids is None else {int(p) for p in approve_pids}
    applied = changed = recount = 0
    for pid, q in counted.items():
        before = _local_qty(pid)
        if pid in ok:
            d = M._move_stock(pid, 0, "count", "stock_count",
                              "Stock count (%s)" % (doc.get("device") or doc.get("source") or "mobile"),
                              doc.get("doc_id"), set_to=q)
            applied += 1
            changed += 1 if d else 0
            log_line(pid, before, q, "applied", doc.get("doc_id"), doc.get("source"),
                     doc.get("user_id"), by_user)
        else:
            recount += 1
            log_line(pid, before, q, "recount", doc.get("doc_id"), doc.get("source"),
                     doc.get("user_id"), by_user, "sent back to recount")
    return applied, changed, recount


def pending():
    """Phone / desktop counts waiting for approval, line by line."""
    try:
        docs = db.fetchall("SELECT * FROM mobile_docs WHERE doc_type='count' AND status='pending' "
                           "ORDER BY doc_id") or []
    except Exception:
        return []
    out = []
    names = {}
    for d in docs:
        counted = counted_by_product(json.loads(d.get("lines_json") or "[]"))
        if not counted:
            continue
        ids = ",".join(str(int(p)) for p in counted)
        for r in db.fetchall("SELECT product_id, product_code, product_name_en FROM products "
                             "WHERE product_id IN (%s)" % ids) or []:
            names[r["product_id"]] = r
        lines = []
        for pid, q in counted.items():
            sysq = _local_qty(pid)
            cost = _cost(pid)
            diff = q - sysq
            lines.append({"product_id": pid, "code": (names.get(pid) or {}).get("product_code") or "",
                          "name": (names.get(pid) or {}).get("product_name_en") or str(pid),
                          "system_qty": round(sysq, 3), "counted": round(q, 3), "diff": round(diff, 3),
                          "value": round(diff * cost, 2),
                          "big": bool(abs(diff * cost) >= 50
                                      or (sysq and abs(diff) / max(abs(sysq), 1) >= 0.2))})
        lines.sort(key=lambda x: -abs(x["value"]))
        out.append({"doc_id": d["doc_id"], "title": d.get("title") or "Stock Count",
                    "device": d.get("device") or d.get("source") or "", "user_id": d.get("user_id"),
                    "created_at": str(d.get("created_at") or "")[:16], "lines": lines,
                    "diff_value": round(sum(x["value"] for x in lines), 2)})
    return out


def approve(doc_id, approve_pids=None, by_user=None):
    """The owner approves a waiting count (all lines, or only some: the rest
    go back to the list to recount)."""
    d = db.fetchone("SELECT * FROM mobile_docs WHERE doc_id=?", (int(doc_id),))
    if not d or d.get("doc_type") != "count":
        raise ValueError("Count not found.")
    if d.get("status") != "pending":
        raise ValueError("This count is already %s." % d.get("status"))
    by_user = by_user or _user_id()
    with db.transaction():
        a, c, r = apply_lines(d, approve_pids, by_user)
        msg = "%d product(s) approved, %d changed%s." % (a, c, (", %d to recount" % r) if r else "")
        db.execute("UPDATE mobile_docs SET status='applied', result=?, applied_at=GETDATE(), applied_by=? "
                   "WHERE doc_id=?", (msg[:400], by_user, int(doc_id)))
    try:
        from modules import audit
        audit.log("approve", "stock_count", doc_id, msg)
    except Exception:
        pass
    return msg


def reject(doc_id, why="", by_user=None):
    from modules import mobile_api as M
    M.reject_doc(int(doc_id), why or "count again", by_user or _user_id())
    try:
        from modules import audit
        audit.log("reject", "stock_count", doc_id, why or "count again")
    except Exception:
        pass


def submit_desktop(counts, note=""):
    """Counts typed on the PC ({product_id: base qty}) → the same approval
    path as a phone count. Returns the doc_id."""
    lines = [{"product_id": int(p), "factor": 1, "qty": _f(q)} for p, q in counts.items()
             if q is not None and str(q).strip() != ""]
    if not lines:
        raise ValueError("Type at least one counted quantity.")
    uid = "pc-count-%s" % datetime.now().strftime("%Y%m%d%H%M%S%f")
    user = _user_id()
    db.execute("INSERT INTO mobile_docs (doc_uid, doc_type, source, user_id, device, status, title, "
               "header_json, lines_json) VALUES (?,?,?,?,?,?,?,?,?)",
               (uid, "count", "desktop", user, "this PC", "pending", "Stock Count · PC",
                json.dumps({"note": note}), json.dumps(lines)))
    doc_id = db.execute_scalar("SELECT doc_id FROM mobile_docs WHERE doc_uid=?", (uid,))
    try:
        from modules import audit
        audit.log("submit", "stock_count", doc_id, "%d line(s) from this PC" % len(lines))
    except Exception:
        pass
    if not needs_approval():
        approve(doc_id, None, user)
    return doc_id


# ── history ──────────────────────────────────────────────────
def history(days=90):
    if not ready():
        return {"rows": [], "lines": 0, "exact": 0, "accuracy": None, "loss": 0.0, "gain": 0.0}
    since = (date.today() - timedelta(days=int(days) - 1)).isoformat()
    rows = db.fetchall("SELECT l.*, p.product_code, p.product_name_en FROM stock_count_log l "
                       "LEFT JOIN products p ON p.product_id=l.product_id WHERE l.count_date >= ? "
                       "ORDER BY l.log_id DESC", (since,)) or []
    ap = [r for r in rows if r.get("status") == "applied"]
    exact = sum(1 for r in ap if abs(_f(r.get("diff_qty"))) < 1e-6)
    return {"rows": rows, "lines": len(ap), "exact": exact,
            "accuracy": round(exact / len(ap) * 100.0, 1) if ap else None,
            "loss": round(sum(_f(r.get("diff_value")) for r in ap if _f(r.get("diff_value")) < 0), 2),
            "gain": round(sum(_f(r.get("diff_value")) for r in ap if _f(r.get("diff_value")) > 0), 2)}
