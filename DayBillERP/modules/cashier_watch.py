# ============================================================
# DayBill ERP - 👀 Cashier watch  (v6.4)
# ------------------------------------------------------------
# Per cashier for a period: bills, sales, discounts, returns, items
# removed from a bill before payment (voids), bills cleared, documents
# deleted, cash short / over at shift close — and a warning when one
# cashier is far above the others (or above a fixed limit).
#   log_void(kind, lines)   called by the POS (✕ a line, clear a bill)
#   report(f, t)            rows + flags  (Reports ▸ Cashier Watch,
#                           the owner's evening report)
# Read-only except log_void (table pos_voids, v6.4 database update).
# ============================================================

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _q(sql, params=()):
    try:
        return [dict(r) for r in (db.fetchall(sql, params) or [])]
    except Exception:
        return []


def short_limit():
    try:
        from config import settings as cfg
        return abs(float(cfg.get("cashier_watch_short", 20) or 20))
    except Exception:
        return 20.0


def log_void(kind, lines):
    """A line removed (kind 'line') or a whole unpaid bill cleared ('clear')."""
    try:
        from modules import permissions as p
        uid = (p.session_user() or {}).get("user_id")
    except Exception:
        uid = None
    shift = counter = None
    try:
        from modules import shifts as SH
        cur = SH.current()
        shift = cur.get("shift_id") if cur else None
    except Exception:
        pass
    try:
        from modules import branches as BR
        counter = BR.current()[1]
    except Exception:
        pass
    today = date.today().isoformat()
    lines = [ln for ln in (lines or []) if ln]
    if not lines:
        return False

    def amount(ln):
        return _f(ln.get("line_total")) or _f(ln.get("quantity")) * _f(ln.get("unit_price"))
    if kind == "clear":                     # a whole bill: ONE row (items + total)
        names = ", ".join(str(ln.get("product_name_en") or "") for ln in lines[:4])
        rows = [(None, ("%d item(s): %s" % (len(lines), names))[:300], float(len(lines)),
                 sum(amount(ln) for ln in lines))]
    else:
        rows = [(ln.get("product_id"), str(ln.get("product_name_en") or "")[:300],
                 _f(ln.get("quantity")), amount(ln)) for ln in lines]
    try:
        for pid, name, qty, amt in rows:
            db.execute("INSERT INTO pos_voids (void_date, user_id, shift_id, counter_id, kind, product_id, "
                       "product_name, quantity, amount) VALUES (?,?,?,?,?,?,?,?,?)",
                       (today, uid, shift, counter, str(kind)[:20], pid, name, qty, round(amt, 2)))
    except Exception:
        return False
    return True


def _users():
    return {r["user_id"]: (r.get("full_name_en") or r.get("username") or "User %s" % r["user_id"])
            for r in _q("SELECT user_id, username, full_name_en FROM users")}


def report(date_from, date_to):
    f, t = date_from, date_to
    names = _users()
    rows = {}

    def row(uid):
        key = uid if uid is not None else 0
        if key not in rows:
            rows[key] = {"user_id": uid, "cashier": names.get(uid, "(no user / back office)"),
                         "bills": 0, "sales": 0.0, "discount": 0.0, "returns": 0, "returns_amt": 0.0,
                         "voids": 0, "voids_amt": 0.0, "clears": 0, "deletes": 0,
                         "cash_short": 0.0, "cash_over": 0.0}
        return rows[key]
    for r in _q("SELECT created_by AS u, COUNT(*) AS n, SUM(ISNULL(total_amount,0)) AS s, "
                "SUM(ISNULL(discount_amount,0)) AS d FROM sales_invoices WHERE invoice_status='confirmed' "
                "AND ISNULL(invoice_type_code,'388')<>'381' AND invoice_date BETWEEN ? AND ? "
                "GROUP BY created_by", (f, t)):
        x = row(r["u"])
        x["bills"] += int(_f(r["n"]))
        x["sales"] += _f(r["s"])
        x["discount"] += _f(r["d"])
    shift_user = {r["shift_id"]: r["user_id"] for r in _q("SELECT shift_id, user_id FROM cashier_shifts")}
    for r in _q("SELECT shift_id, COUNT(*) AS n, SUM(ISNULL(total_amount,0)) AS s FROM sales_returns "
                "WHERE ISNULL(return_status,'confirmed')='confirmed' AND return_date BETWEEN ? AND ? "
                "GROUP BY shift_id", (f, t)):
        x = row(shift_user.get(r.get("shift_id")))
        x["returns"] += int(_f(r["n"]))
        x["returns_amt"] += _f(r["s"])
    for r in _q("SELECT user_id AS u, kind, COUNT(*) AS n, SUM(ISNULL(amount,0)) AS a FROM pos_voids "
                "WHERE void_date BETWEEN ? AND ? GROUP BY user_id, kind", (f, t)):
        x = row(r["u"])
        if r["kind"] == "clear":
            x["clears"] += int(_f(r["n"]))
        else:
            x["voids"] += int(_f(r["n"]))
        x["voids_amt"] += _f(r["a"])
    for r in _q("SELECT user_id AS u, COUNT(*) AS n FROM audit_logs WHERE LOWER(action)='delete' "
                "AND CONVERT(date, created_at) BETWEEN ? AND ? GROUP BY user_id", (f, t)):
        row(r["u"])["deletes"] += int(_f(r["n"]))
    for r in _q("SELECT user_id AS u, ISNULL(difference,0) AS d FROM cashier_shifts WHERE status='closed' "
                "AND CONVERT(date, closed_at) BETWEEN ? AND ?", (f, t)):
        x = row(r["u"])
        d = _f(r["d"])
        if d < 0:
            x["cash_short"] += d
        else:
            x["cash_over"] += d
    out = [x for x in rows.values() if x["bills"] or x["returns"] or x["voids"] or x["clears"]
           or x["deletes"] or x["cash_short"] or x["cash_over"]]
    for x in out:
        gross = x["sales"] + x["discount"]
        x["discount_pct"] = round(x["discount"] / gross * 100.0, 1) if gross else 0.0
        x["returns_pct"] = round(x["returns_amt"] / x["sales"] * 100.0, 1) if x["sales"] else 0.0
        x["voids_per_100"] = round(x["voids"] / x["bills"] * 100.0, 1) if x["bills"] else float(x["voids"])
        for k in ("sales", "discount", "returns_amt", "voids_amt", "cash_short", "cash_over"):
            x[k] = round(x[k], 2)
    _flag(out)
    out.sort(key=lambda x: (-len(x["flags"]), -x["sales"]))
    return out


def _avg_others(rows, x, key):
    o = [r[key] for r in rows if r is not x and r["bills"] >= 5]
    return sum(o) / len(o) if o else None


def _flag(rows):
    lim = short_limit()
    for x in rows:
        fl = []
        a = _avg_others(rows, x, "discount_pct")
        if x["discount_pct"] >= 3 and x["bills"] >= 3 and (a is None and x["discount_pct"] >= 10
                                                            or a is not None and x["discount_pct"] > max(2 * a, a + 3)):
            fl.append("High discounts %.1f%%" % x["discount_pct"])
        a = _avg_others(rows, x, "returns_pct")
        if x["returns"] >= 2 and (a is None and x["returns_pct"] >= 5
                                  or a is not None and x["returns_pct"] > max(2 * a, a + 2)):
            fl.append("Many returns ×%d (%.1f%%)" % (x["returns"], x["returns_pct"]))
        a = _avg_others(rows, x, "voids_per_100")
        if x["voids"] >= 3 and (a is None and x["voids_per_100"] >= 10
                                or a is not None and x["voids_per_100"] > max(2 * a, a + 5)):
            fl.append("Items removed ×%d" % x["voids"])
        if x["clears"] >= 3:
            fl.append("Bills cleared ×%d" % x["clears"])
        if x["deletes"]:
            fl.append("Deleted docs ×%d" % x["deletes"])
        if x["cash_short"] <= -lim:
            fl.append("Cash short %.2f" % -x["cash_short"])
        x["flags"] = fl
    return rows


def flags_text(date_from, date_to=None):
    """Short lines for the owner's report ('' list when all is normal)."""
    out = []
    for x in report(date_from, date_to or date_from):
        for fl in x["flags"]:
            out.append("%s: %s" % (x["cashier"], fl))
    return out
