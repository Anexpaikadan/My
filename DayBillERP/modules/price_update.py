# ============================================================
# DayBill ERP - smart price update when the cost goes up  (v6.4)
# ------------------------------------------------------------
# A supplier's price went up → the shelf price that made X % margin now
# makes less. suggestions() finds every item whose LAST purchase cost
# (per piece) is higher than the purchase before it (by at least
# Settings ▸ Purchase ▸ "Suggest a new price when cost goes up by" %)
# and whose selling price was not changed since, and suggests the price
# that keeps the OLD margin, rounded UP to a nice price (Settings ▸
# Purchase ▸ "Round suggested prices to"). Box / Carton prices move by
# the same ratio. apply() saves them and logs every change, so the new
# shelf labels wait in Inventory ▸ Price Change Labels.
# ============================================================

import math
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _cfg(key, default):
    try:
        from config import settings as cfg
        v = cfg.get(key, default)
        return default if v in (None, "") else v
    except Exception:
        return default


def rounding():
    try:
        return max(0.01, float(_cfg("price_rounding", "0.25")))
    except (TypeError, ValueError):
        return 0.25


def alert_pct():
    try:
        return max(0.0, float(_cfg("price_alert_pct", 2)))
    except (TypeError, ValueError):
        return 2.0


def nice(price, step=None):
    """Round UP to the next nice price (0.25 → 11.25, 11.50 …)."""
    step = step or rounding()
    return round(math.ceil(round(price / step, 6) - 1e-9) * step, 2)


def _incl():
    return str(_cfg("sales_price_tax_mode", "inclusive")).lower() == "inclusive"


def _d(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _dt(v):
    """date / datetime / text → datetime (None when unknown)."""
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    s = str(v or "").strip().replace("T", " ")
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:n], fmt)
        except Exception:
            pass
    return None


def suggestions(min_rise=None, product_ids=None):
    """[{product, old_cost, new_cost, rise_pct, price, margin_now, suggested,
    margin_after, units:[…]}] — biggest rise first (only these products when
    product_ids is given, e.g. the lines of a purchase just confirmed)."""
    min_rise = alert_pct() if min_rise is None else float(min_rise)
    only = ""
    if product_ids:
        ids = sorted({int(x) for x in product_ids if x})[:900]
        if not ids:
            return []
        only = " AND pil.product_id IN (%s)" % ",".join(str(i) for i in ids)
    fac = {}
    for r in db.fetchall("SELECT product_id, unit_name_en, ISNULL(conversion_factor,1) AS f "
                         "FROM product_units") or []:
        fac[(r["product_id"], r["unit_name_en"])] = _f(r["f"]) or 1.0
    hist = {}
    for r in db.fetchall("SELECT pil.product_id, pi.invoice_date, pi.purchase_id, pil.unit_price, "
                         "ISNULL(pi.updated_at, pi.created_at) AS entered, "
                         "pil.unit_of_measure_en FROM purchase_invoice_lines pil JOIN purchase_invoices pi "
                         "ON pi.purchase_id=pil.purchase_id WHERE pi.invoice_status='confirmed' "
                         "AND pil.product_id IS NOT NULL AND ISNULL(pil.unit_price,0) > 0" + only +
                         " ORDER BY pil.product_id, pi.invoice_date DESC, pi.purchase_id DESC") or []:
        f = fac.get((r["product_id"], r.get("unit_of_measure_en")), 1.0)
        hist.setdefault(r["product_id"], []).append(
            (_d(r["invoice_date"]), r["purchase_id"], _f(r["unit_price"]) / f, _dt(r.get("entered"))))
    changed = {}
    try:
        for r in db.fetchall("SELECT product_id, MAX(changed_at) AS t FROM price_change_log "
                             "GROUP BY product_id") or []:
            changed[r["product_id"]] = _dt(r["t"])
    except Exception:
        pass
    rates = {r["vat_category_id"]: _f(r["vat_rate"]) for r in (db.fetchall(
        "SELECT vat_category_id, vat_rate FROM vat_categories") or [])}
    prods = {r["product_id"]: r for r in (db.fetchall(
        "SELECT product_id, product_code, product_name_en, ISNULL(unit_price,0) AS price, "
        "vat_category_id FROM products WHERE is_active=1") or [])}
    units = {}
    for r in db.fetchall("SELECT unit_id, product_id, unit_name_en, ISNULL(conversion_factor,1) AS f, "
                         "ISNULL(selling_price,0) AS sp FROM product_units WHERE ISNULL(is_active,1)=1 "
                         "ORDER BY conversion_factor") or []:
        units.setdefault(r["product_id"], []).append(r)
    incl, step = _incl(), rounding()
    out = []
    for pid, h in hist.items():
        p = prods.get(pid)
        if not p or len(h) < 2:
            continue
        new_d, new_pur, new, entered = h[0]
        # the newest cost may repeat over several purchases: the rise happened
        # at the OLDEST of them; compare with the cost before that run
        start, old = h[0], None
        for x in h[1:]:
            if abs(x[2] - new) <= 0.005:
                start = x
                continue
            old = x[2]
            break
        if not old or new <= old:
            continue
        rise = (new - old) / old * 100.0
        if rise < min_rise:
            continue
        when = start[3] or (_dt(start[0]) if start[0] else None)
        if changed.get(pid) and when and changed[pid] >= when:
            continue                               # price already changed after the cost went up
        us = units.get(pid) or []
        base = next((u for u in us if abs(_f(u["f"]) - 1) < 1e-9), None)
        price = _f(base["sp"]) if base and _f(base["sp"]) > 0 else _f(p["price"])
        if price <= 0:
            continue
        rate = rates.get(p.get("vat_category_id"), 15.0)
        net = price / (1 + rate / 100.0) if incl else price
        m_old = (net - old) / net if net else 0.0
        m_old = max(m_old, 0.05)                   # never aim below 5 %
        new_net = new / (1 - m_old)
        target = new_net * (1 + rate / 100.0) if incl else new_net
        sug = nice(target, step)
        if sug <= price + 0.001:
            continue                               # the price still keeps the margin
        net_after = sug / (1 + rate / 100.0) if incl else sug
        ratio = sug / price
        ulist = [{"unit_id": u["unit_id"], "unit": u["unit_name_en"], "factor": _f(u["f"]),
                  "price": round(_f(u["sp"]), 2),
                  "suggested": nice(_f(u["sp"]) * ratio, step) if _f(u["sp"]) > 0 else 0.0}
                 for u in us]
        out.append({"product_id": pid, "code": p["product_code"], "name": p["product_name_en"],
                    "purchase_date": start[0].isoformat() if start[0] else "",
                    "old_cost": round(old, 4), "new_cost": round(new, 4), "rise_pct": round(rise, 1),
                    "price": round(price, 2),
                    "margin_now": round((net - new) / net * 100.0, 1) if net else 0.0,
                    "margin_before": round((net - old) / net * 100.0, 1) if net else 0.0,
                    "suggested": sug,
                    "margin_after": round((net_after - new) / net_after * 100.0, 1) if net_after else 0.0,
                    "units": ulist})
    out.sort(key=lambda r: -r["rise_pct"])
    return out


def apply(changes):
    """changes: [{product_id, suggested (base price), units:[{unit_id, suggested}]}]
    (or the rows from suggestions()). Saves the prices; every change is logged
    for shelf labels. → number of products changed."""
    from modules import price_watch as PW
    pids = [int(c["product_id"]) for c in changes]
    if not pids:
        return 0
    before = PW.snapshot(pids)
    with db.transaction():
        for c in changes:
            pid, new = int(c["product_id"]), round(_f(c["suggested"]), 2)
            if new <= 0:
                continue
            db.execute("UPDATE products SET unit_price=?, updated_at=GETDATE() WHERE product_id=?",
                       (new, pid))
            ulist = c.get("units") or []
            if ulist:
                for u in ulist:
                    if _f(u.get("suggested")) > 0:
                        db.execute("UPDATE product_units SET selling_price=? WHERE unit_id=?",
                                   (round(_f(u["suggested"]), 2), int(u["unit_id"])))
            else:
                db.execute("UPDATE product_units SET selling_price=? WHERE product_id=? "
                           "AND ISNULL(is_active,1)=1 AND conversion_factor=1", (new, pid))
    try:
        PW.record(before, "cost_up")
    except Exception:
        pass
    try:
        from modules import audit
        audit.log("price_change", "products", None, "%d price(s) raised after a cost increase" % len(pids))
    except Exception:
        pass
    return len(pids)
