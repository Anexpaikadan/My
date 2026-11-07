# ============================================================
# DayBill ERP - AI inventory engine (v6.3)
# ------------------------------------------------------------
# Smart stock answers worked out from the shop's own sales, purchases,
# batches and branches. READ-ONLY — nothing is ever changed.
# Used by:  Smart Insights screen (tabs + "Ask AI")  and the Claude
# connector (claude_connector/daybill_mcp.py tools).
#
#   health()            one score + the most important things to do
#   forecast()          sells / day, trend, days of stock left, run-out date
#   reorder_plan()      what to order, how much, grouped by supplier
#   abc()               A / B / C items (who makes the money) + A items at risk
#   expiry()            batches near expiry, how much will NOT sell in time
#   transfers()         move stock between branches (one short, one with extra)
#   bought_together()   items bought in the same bill (shelf / combo offers)
#   supplier_prices()   price per supplier for a product, cheapest, trend
#   data_check()        products with missing / wrong data
#   price_check()       selling below cost / thin margin
# ============================================================

import math
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db
from modules import insights as INS

STATUS_ORDER = {"out": 0, "critical": 1, "low": 2, "ok": 3, "overstock": 4, "no sales": 5}
STATUS_TEXT = {"out": "Out of stock (still selling)", "critical": "Runs out within 3 days",
               "low": "Runs out within 7 days", "ok": "OK",
               "overstock": "More than 4 months of stock", "no sales": "Not selling"}


def use_db(d):
    """Read through another db object (the Claude connector's read-only one)."""
    global db
    db = d
    import importlib
    for name in ("insights", "batches", "stock_branch", "branches"):
        try:
            importlib.import_module("modules." + name).db = d
        except Exception:
            pass


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


def _cost(p):
    return _f(p.get("avg_cost")) or _f(p.get("pp"))


def _match(p, text):
    t = (text or "").strip().lower()
    if not t:
        return True
    return any(t in str(p.get(k) or "").lower() for k in ("product_code", "product_name_en",
                                                           "product_name_ar", "barcode"))


def _products():
    rows = _q("SELECT p.product_id, p.product_code, p.product_name_en, p.product_name_ar, "
              "p.barcode, ISNULL(p.stock_quantity,0) AS stock, ISNULL(p.reorder_level,0) AS rl, "
              "ISNULL(p.min_stock,0) AS min_stock, ISNULL(p.average_cost,0) AS avg_cost, "
              "ISNULL(p.purchase_price,0) AS pp, ISNULL(p.unit_price,0) AS price, "
              "ISNULL(p.track_inventory,1) AS track, ISNULL(p.product_type,'product') AS ptype, "
              "p.category_id, p.vat_category_id FROM products p WHERE p.is_active=1")
    if not rows:                                  # older database: fewer columns
        rows = [dict(r, product_name_ar="", barcode="", min_stock=0, category_id=None)
                for r in INS._products()]
    return rows


def _stocked(p):
    """Goods that keep stock (same rule as stock posting: everything but services —
    the 'Track inventory' tick only changes how the product list shows it)."""
    return str(p.get("ptype") or "product").lower() != "service"


def find_products(text, limit=5):
    """Best matches for a code / barcode / name (exact code or barcode first)."""
    t = (text or "").strip()
    if not t:
        return []
    like = "%" + t + "%"
    rows = _q("SELECT TOP %d p.product_id, p.product_code, p.product_name_en, p.product_name_ar "
              "FROM products p WHERE p.product_code=? OR p.barcode=? OR p.product_name_en LIKE ? "
              "OR p.product_name_ar LIKE ? OR p.product_id IN (SELECT product_id FROM product_units "
              "WHERE barcode=?) ORDER BY CASE WHEN p.product_code=? OR p.barcode=? THEN 0 ELSE 1 END, "
              "p.product_name_en" % int(limit), (t, t, like, like, t, t, t))
    return rows


# ── 1. forecast: days of stock left ──────────────────────────
def forecast(days=30, search="", status="", limit=500, today=None):
    """Sales speed (base units / day), trend and the day each item runs out.
    The speed weights the last 14 days (60 %) and the last `days` (40 %)."""
    today = today or date.today()
    days = max(7, int(days or 30))
    long_ = INS._sold_base(days, today)
    recent = INS._sold_base(14, today)
    before = INS._sold_base(14, today - timedelta(days=14))
    out = []
    for p in _products():
        if not _stocked(p) or not _match(p, search):
            continue
        pid = p["product_id"]
        r_long = max(0.0, long_.get(pid, 0.0)) / days
        r_recent = max(0.0, recent.get(pid, 0.0)) / 14.0
        r_before = max(0.0, before.get(pid, 0.0)) / 14.0
        rate = 0.6 * r_recent + 0.4 * r_long if (r_recent or r_long) else 0.0
        stock = _f(p["stock"])
        if stock <= 0 and rate <= 0 and not search:
            continue                                   # nothing to say
        left = stock / rate if rate > 0 else None
        if r_recent > r_before * 1.25 and r_recent - r_before >= 0.1:
            trend = "up"
        elif r_recent < r_before * 0.75 and r_before - r_recent >= 0.1:
            trend = "down"
        else:
            trend = "flat"
        if stock <= 0 and rate > 0:
            st = "out"
        elif left is None:
            st = "no sales"
        elif left <= 3:
            st = "critical"
        elif left <= 7:
            st = "low"
        elif left > 120:
            st = "overstock"
        else:
            st = "ok"
        if status and st != status:
            continue
        cost = _cost(p)
        out.append({
            "product_id": pid, "code": p["product_code"], "name": p["product_name_en"],
            "stock": round(stock, 3), "sells_per_day": round(rate, 2),
            "last_14_days_per_day": round(r_recent, 2), "trend": trend,
            "days_left": None if left is None else round(left, 1),
            "runs_out_on": (today + timedelta(days=int(left))).isoformat()
            if left is not None and stock > 0 else ("now" if st == "out" else None),
            "status": st, "status_text": STATUS_TEXT[st],
            "reorder_level": _f(p.get("rl")), "unit_cost": round(cost, 2),
            "stock_value": round(max(stock, 0) * cost, 2)})
    out.sort(key=lambda r: (STATUS_ORDER[r["status"]],
                            r["days_left"] if r["days_left"] is not None else 10 ** 6, r["name"] or ""))
    return out[:max(1, int(limit or 500))]


# ── 2. what to order, by supplier ────────────────────────────
def reorder_plan(days=30, cover_days=14, warn_days=7, supplier=""):
    items = INS.reorder(days=days, cover_days=cover_days, warn_days=warn_days)
    s = (supplier or "").strip().lower()
    if s:
        items = [i for i in items if s in str(i.get("supplier") or "").lower()]
    groups = {}
    for i in items:
        key = i.get("supplier") or "No supplier yet (buy it once with a Purchase Invoice)"
        g = groups.setdefault(key, {"supplier": key, "supplier_id": i.get("supplier_id"),
                                    "lines": 0, "total_cost": 0.0, "items": []})
        g["lines"] += 1
        g["total_cost"] = round(g["total_cost"] + _f(i.get("value")), 2)
        g["items"].append({k: i.get(k) for k in ("code", "name", "stock", "per_day", "days_left",
                                                  "order_qty", "unit", "unit_cost", "value")})
    out = sorted(groups.values(), key=lambda g: (g["supplier_id"] is None, -g["total_cost"]))
    return {"based_on_days": days, "cover_days": cover_days, "suppliers": len(out),
            "lines": len(items), "total_cost": round(sum(g["total_cost"] for g in out), 2),
            "orders": out}


# ── 3. ABC analysis ──────────────────────────────────────────
def abc(days=90, by="revenue", today=None, fc=None):
    """A = the items making the first 80 % (of revenue / profit / qty),
    B = the next 15 %, C = the rest."""
    today = today or date.today()
    days = max(7, int(days or 90))
    by = by if by in ("revenue", "profit", "qty") else "revenue"
    f, t = (today - timedelta(days=days - 1)).isoformat(), today.isoformat()
    rev, cost = {}, {}
    for r in _q("SELECT sil.product_id, si.invoice_type_code AS tc, SUM(ISNULL(sil.line_amount,0)) AS a "
                "FROM sales_invoice_lines sil JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
                "WHERE si.invoice_status='confirmed' AND si.invoice_date BETWEEN ? AND ? "
                "AND sil.product_id IS NOT NULL GROUP BY sil.product_id, si.invoice_type_code", (f, t)):
        sg = -1 if str(r.get("tc") or "388") == "381" else 1
        rev[r["product_id"]] = rev.get(r["product_id"], 0.0) + sg * _f(r["a"])
    for r in _q("SELECT l.product_id, SUM(ISNULL(l.line_amount,0)) AS a FROM sales_return_lines l "
                "JOIN sales_returns h ON h.return_id=l.return_id WHERE ISNULL(h.return_status,'confirmed')"
                "='confirmed' AND h.return_date BETWEEN ? AND ? AND l.product_id IS NOT NULL "
                "GROUP BY l.product_id", (f, t)):
        rev[r["product_id"]] = rev.get(r["product_id"], 0.0) - _f(r["a"])
    for r in _q("SELECT product_id, txn_type, SUM(ISNULL(qty_out_base,0)*ISNULL(unit_cost,0)) AS co, "
                "SUM(ISNULL(qty_in_base,0)*ISNULL(unit_cost,0)) AS ci FROM inventory_transactions "
                "WHERE txn_type IN ('sale','return_in') AND txn_date BETWEEN ? AND ? "
                "GROUP BY product_id, txn_type", (f, t)):
        v = _f(r["co"]) if r["txn_type"] == "sale" else -_f(r["ci"])
        cost[r["product_id"]] = cost.get(r["product_id"], 0.0) + v
    qty = INS._sold_base(days, today)
    prods = {p["product_id"]: p for p in _products()}
    if fc is None:
        fc = forecast(today=today)
    left = {r["product_id"]: r for r in fc}
    rows = []
    for pid in set(rev) | set(qty):
        p = prods.get(pid)
        if not p:
            continue
        revenue = rev.get(pid, 0.0)
        profit = revenue - cost.get(pid, 0.0)
        q = qty.get(pid, 0.0)
        metric = {"revenue": revenue, "profit": profit, "qty": q}[by]
        if metric <= 0:
            continue
        rows.append({"product_id": pid, "code": p["product_code"], "name": p["product_name_en"],
                     "revenue": round(revenue, 2), "profit": round(profit, 2), "qty": round(q, 3),
                     "metric": metric, "stock": round(_f(p["stock"]), 3),
                     "days_left": (left.get(pid) or {}).get("days_left"),
                     "status": (left.get(pid) or {}).get("status", "")})
    rows.sort(key=lambda r: -r["metric"])
    total = sum(r["metric"] for r in rows) or 1.0
    cum = 0.0
    classes = {c: {"items": 0, "share": 0.0} for c in "ABC"}
    for r in rows:
        share = r["metric"] / total * 100.0
        cls = "A" if cum < 80.0 else ("B" if cum < 95.0 else "C")
        cum += share
        r["share_pct"] = round(share, 2)
        r["cumulative_pct"] = round(cum, 2)
        r["class"] = cls
        classes[cls]["items"] += 1
        classes[cls]["share"] = round(classes[cls]["share"] + share, 2)
        r.pop("metric", None)
    risk = [r for r in rows if r["class"] == "A" and r["status"] in ("out", "critical", "low")]
    return {"by": by, "period": {"from": f, "to": t}, "classes": classes,
            "a_items_at_risk": risk, "rows": rows,
            "advice": "A items make most of the money: never let them run out, count "
                      "them often, keep them in the best shelf places. C items: order "
                      "less, think about dropping slow ones."}


# ── 4. expiry: what will not sell in time ────────────────────
def expiry(days=30, today=None):
    today = today or date.today()
    try:
        from modules import batches as B
        if not B.ready():
            return {"tracked": False, "rows": [], "expired": {"batches": 0, "value": 0.0},
                    "soon": {"batches": 0, "value": 0.0}, "at_risk_value": 0.0}
        rows = B.near_expiry(int(days or 30))
    except Exception:
        rows = []
    speed = INS._sold_base(30, today)
    prods = {p["product_id"]: p for p in _products()}
    used = {}
    out = []
    for r in sorted(rows, key=lambda x: (x.get("days_left") or 0, x.get("batch_id") or 0)):
        pid = r.get("product_id")
        p = prods.get(pid, {})
        qty = _f(r.get("qty_base"))
        dl = r.get("days_left")
        rate = max(0.0, speed.get(pid, 0.0)) / 30.0
        cost = _f(r.get("unit_cost")) or _cost(p)
        if dl is not None and dl < 0:
            sell, advice = 0.0, "Expired — take off the shelf; write off or return to the supplier"
        else:
            room = max(0.0, rate * max(0, dl or 0) - used.get(pid, 0.0))   # FEFO: earlier batches first
            sell = min(qty, room)
            used[pid] = used.get(pid, 0.0) + sell
            if qty - sell <= 0.0001:
                advice = "Will sell in time (sell this batch first)"
            elif (dl or 0) <= 7:
                advice = "Discount / offer now — will not all sell before it expires"
            else:
                advice = "Put in front / promote — part may not sell in time"
        at_risk = max(0.0, qty - sell)
        out.append({"code": r.get("product_code") or p.get("product_code"),
                    "name": r.get("product_name_en") or p.get("product_name_en"),
                    "batch_no": r.get("batch_no") or "", "expiry_date": str(r.get("expiry_date") or "")[:10],
                    "days_left": dl, "qty": round(qty, 3), "sells_per_day": round(rate, 2),
                    "qty_at_risk": round(at_risk, 3), "value": round(qty * cost, 2),
                    "value_at_risk": round(at_risk * cost, 2), "advice": advice})
    gone = [x for x in out if x["days_left"] is not None and x["days_left"] < 0]
    soon = [x for x in out if x not in gone]
    return {"tracked": True, "within_days": int(days or 30), "rows": out,
            "expired": {"batches": len(gone), "value": round(sum(x["value"] for x in gone), 2)},
            "soon": {"batches": len(soon), "value": round(sum(x["value"] for x in soon), 2)},
            "at_risk_value": round(sum(x["value_at_risk"] for x in out), 2)}


# ── 5. branch transfers ──────────────────────────────────────
def transfers(days=30, cover_days=14, today=None):
    """One branch is short (less than a week left) while another has more
    than double what it needs → move stock instead of buying."""
    today = today or date.today()
    try:
        from modules import stock_branch as SB
        if not SB.multi():
            return {"branches": 1, "suggestions": [],
                    "note": "Only one branch — nothing to move."}
        brs = {b["branch_id"]: b.get("name_en") or "Branch %s" % b["branch_id"] for b in SB.branches()}
        main = SB.main_branch_id()
        qty = SB.qty_by_branch()
    except Exception:
        return {"branches": 1, "suggestions": [], "note": "Branches are not set up."}
    since = (today - timedelta(days=max(7, int(days)) - 1)).isoformat()
    sold = {}
    for r in _q("SELECT product_id, branch_id, SUM(ISNULL(qty_out_base,0)) AS q FROM "
                "inventory_transactions WHERE txn_type='sale' AND txn_date >= ? "
                "GROUP BY product_id, branch_id", (since,)):
        b = r.get("branch_id") or main
        sold.setdefault(r["product_id"], {})
        sold[r["product_id"]][b] = sold[r["product_id"]].get(b, 0.0) + _f(r["q"])
    prods = {p["product_id"]: p for p in _products()}
    out = []
    for pid, per in qty.items():
        p = prods.get(pid)
        if not p or not _stocked(p):
            continue
        rate = {b: sold.get(pid, {}).get(b, 0.0) / float(max(7, int(days))) for b in per}
        need = {b: rate[b] * cover_days - per[b] for b in per if rate[b] > 0
                and (per[b] <= 0 or per[b] / rate[b] <= 7)}
        spare = {}
        for b in per:
            keep = rate[b] * cover_days * 2
            if per[b] - keep >= 1:
                spare[b] = per[b] - keep
        for b_to, n in sorted(need.items(), key=lambda x: -x[1]):
            for b_from in sorted(spare, key=lambda x: -spare[x]):
                if b_from == b_to or spare[b_from] < 1 or n <= 0:
                    continue
                q = math.floor(min(spare[b_from], math.ceil(n)))
                if q < 1:
                    continue
                spare[b_from] -= q
                n -= q
                out.append({"code": p["product_code"], "name": p["product_name_en"],
                            "from_branch": brs.get(b_from, str(b_from)),
                            "to_branch": brs.get(b_to, str(b_to)), "qty": q,
                            "from_has": round(per[b_from], 2), "to_has": round(per[b_to], 2),
                            "to_sells_per_day": round(rate[b_to], 2),
                            "value": round(q * _cost(p), 2)})
    out.sort(key=lambda r: -r["value"])
    return {"branches": len(brs), "cover_days": cover_days, "suggestions": out,
            "note": "Make them with Inventory ▸ Stock Transfer (between branches)."}


# ── 6. bought together ───────────────────────────────────────
def bought_together(product="", days=90, limit=20, min_count=2, today=None):
    today = today or date.today()
    since = (today - timedelta(days=max(7, int(days or 90)) - 1)).isoformat()
    bills = {}
    for r in _q("SELECT sil.invoice_id, sil.product_id FROM sales_invoice_lines sil "
                "JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
                "WHERE si.invoice_status='confirmed' AND ISNULL(si.invoice_type_code,'388')<>'381' "
                "AND si.invoice_date >= ? AND sil.product_id IS NOT NULL", (since,)):
        bills.setdefault(r["invoice_id"], set()).add(r["product_id"])
    bills = [b for b in bills.values() if 2 <= len(b) <= 60]
    names = {p["product_id"]: (p["product_code"], p["product_name_en"]) for p in _products()}
    n_bills = len(bills) or 1
    in_bills = {}
    for b in bills:
        for pid in b:
            in_bills[pid] = in_bills.get(pid, 0) + 1
    limit = max(1, int(limit or 20))
    if product:
        hits = find_products(product, 1)
        if not hits:
            raise ValueError("No product matches %r." % product)
        tid = hits[0]["product_id"]
        with_t = [b for b in bills if tid in b]
        co = {}
        for b in with_t:
            for pid in b:
                if pid != tid:
                    co[pid] = co.get(pid, 0) + 1
        rows = []
        for pid, n in co.items():
            if n < min_count:
                continue
            conf = n / len(with_t)
            lift = conf / (in_bills.get(pid, 1) / n_bills)
            rows.append({"code": names.get(pid, ("", ""))[0], "name": names.get(pid, ("", str(pid)))[1],
                         "bills_together": n, "pct_of_its_bills": round(conf * 100, 1),
                         "lift": round(lift, 2)})
        rows.sort(key=lambda r: (-r["bills_together"], -r["lift"]))
        return {"product": hits[0]["product_name_en"], "bills_with_it": len(with_t),
                "days": int(days or 90), "rows": rows[:limit],
                "advice": "Put these next to it on the shelf, or make a combo offer."}
    pairs = {}
    for b in bills:
        if len(b) > 30:
            continue
        s = sorted(b)
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                pairs[(s[i], s[j])] = pairs.get((s[i], s[j]), 0) + 1
    rows = []
    for (a, b), n in pairs.items():
        if n < min_count:
            continue
        lift = (n / n_bills) / ((in_bills.get(a, 1) / n_bills) * (in_bills.get(b, 1) / n_bills))
        rows.append({"item_1": names.get(a, ("", str(a)))[1], "item_2": names.get(b, ("", str(b)))[1],
                     "bills_together": n, "lift": round(lift, 2)})
    rows.sort(key=lambda r: (-r["bills_together"], -r["lift"]))
    return {"days": int(days or 90), "bills_looked_at": len(bills), "rows": rows[:limit],
            "advice": "Pairs often bought together: shelf them close, make combo offers. "
                      "Lift above 1 = more often together than by chance."}


# ── 7. supplier prices ───────────────────────────────────────
def supplier_prices(product, limit=60):
    hits = find_products(product, 1)
    if not hits:
        raise ValueError("No product matches %r." % product)
    pid = hits[0]["product_id"]
    fac = {r["unit_name_en"]: _f(r["f"]) or 1.0 for r in _q(
        "SELECT unit_name_en, ISNULL(conversion_factor,1) AS f FROM product_units WHERE product_id=?",
        (pid,))}
    rows = _q("SELECT TOP %d pi.invoice_date, pi.invoice_number, pi.supplier_id, pi.supplier_name_en, "
              "pil.unit_of_measure_en, pil.unit_price, pil.quantity FROM purchase_invoice_lines pil "
              "JOIN purchase_invoices pi ON pi.purchase_id=pil.purchase_id "
              "WHERE pil.product_id=? AND pi.invoice_status='confirmed' "
              "ORDER BY pi.invoice_date DESC, pi.purchase_id DESC" % max(1, int(limit or 60)), (pid,))
    by = {}
    hist = []
    for r in rows:
        f = fac.get(r.get("unit_of_measure_en") or "", 1.0) or 1.0
        base = _f(r["unit_price"]) / f
        sup = r.get("supplier_name_en") or "(no name)"
        d = str(r.get("invoice_date") or "")[:10]
        hist.append({"date": d, "supplier": sup, "unit": r.get("unit_of_measure_en") or "",
                     "price": round(_f(r["unit_price"]), 2), "price_per_base_unit": round(base, 4),
                     "qty": _f(r["quantity"]), "invoice": r.get("invoice_number")})
        s = by.setdefault(sup, {"supplier": sup, "purchases": 0, "last_price_base": base,
                                "last_date": d, "min_base": base, "max_base": base, "sum": 0.0})
        s["purchases"] += 1
        s["min_base"] = min(s["min_base"], base)
        s["max_base"] = max(s["max_base"], base)
        s["sum"] += base
    sups = []
    for s in by.values():
        sups.append({"supplier": s["supplier"], "purchases": s["purchases"], "last_date": s["last_date"],
                     "last_price_per_base_unit": round(s["last_price_base"], 4),
                     "lowest": round(s["min_base"], 4), "highest": round(s["max_base"], 4),
                     "average": round(s["sum"] / s["purchases"], 4)})
    sups.sort(key=lambda s: s["last_price_per_base_unit"])
    trend = None
    if len(hist) >= 2 and hist[-1]["price_per_base_unit"]:
        trend = round((hist[0]["price_per_base_unit"] - hist[-1]["price_per_base_unit"])
                      / hist[-1]["price_per_base_unit"] * 100.0, 1)
    p = next((x for x in _products() if x["product_id"] == pid), {})
    return {"product": hits[0]["product_name_en"], "code": hits[0]["product_code"],
            "current_cost": round(_cost(p), 4) if p else None,
            "selling_price": round(_f(p.get("price")), 2) if p else None,
            "cheapest_now": sups[0]["supplier"] if sups else None,
            "price_change_pct_since_first": trend, "suppliers": sups, "history": hist[:20]}


# ── 8. data check ────────────────────────────────────────────
def data_check(samples=15, today=None):
    prods = [p for p in _products()]
    unit_bc = {}
    for r in _q("SELECT product_id, barcode FROM product_units WHERE ISNULL(barcode,'')<>'' "
                "AND ISNULL(is_active,1)=1"):
        unit_bc.setdefault(str(r["barcode"]).strip(), set()).add(r["product_id"])
    has_bc = set()
    for bc, pids in unit_bc.items():
        has_bc |= pids
    for p in prods:
        b = str(p.get("barcode") or "").strip()
        if b:
            has_bc.add(p["product_id"])
            unit_bc.setdefault(b, set()).add(p["product_id"])
    unit_price = {r["product_id"]: _f(r["sp"]) for r in _q(
        "SELECT product_id, MAX(ISNULL(selling_price,0)) AS sp FROM product_units GROUP BY product_id")}
    speed = INS._sold_base(30, today)
    names = {p["product_id"]: p for p in prods}
    dup = {}
    for bc, pids in unit_bc.items():
        if len(pids) > 1:
            for pid in pids:
                dup.setdefault(pid, bc)

    def row(p, detail=""):
        return {"code": p["product_code"], "name": p["product_name_en"], "detail": detail}
    checks = [
        ("no_barcode", "No barcode", "Product ▸ Units: give each unit a barcode (or 🔄 Auto)",
         [row(p) for p in prods if _stocked(p) and p["product_id"] not in has_bc]),
        ("no_cost", "Has stock but no cost", "Enter the purchase price — profit and stock value are wrong",
         [row(p, "stock %g" % _f(p["stock"])) for p in prods
          if _f(p["stock"]) > 0 and _cost(p) <= 0]),
        ("no_price", "No selling price", "Set the price before it reaches the till",
         [row(p) for p in prods if _f(p["price"]) <= 0 and unit_price.get(p["product_id"], 0) <= 0
          and str(p["ptype"]).lower() != "service"]),
        ("negative_stock", "Minus stock", "Sold more than received: post the purchase or count it",
         [row(p, "stock %g" % _f(p["stock"])) for p in prods if _stocked(p) and _f(p["stock"]) < 0]),
        ("duplicate_barcode", "Barcode used by 2+ products", "The till may pick the wrong item",
         [row(names[pid], "barcode " + bc) for pid, bc in dup.items() if pid in names]),
        ("no_category", "No category", "Category reports and offers miss it",
         [row(p) for p in prods if not p.get("category_id")]),
        ("no_arabic_name", "No Arabic name", "Arabic receipts show it blank (🤖 AI can translate)",
         [row(p) for p in prods if not str(p.get("product_name_ar") or "").strip()]),
        ("no_vat_category", "No VAT category", "VAT may be wrong on the invoice",
         [row(p) for p in prods if not p.get("vat_category_id")]),
        ("no_reorder_level", "Sells but no reorder level", "Set a reorder level so DayBill warns before it runs out",
         [row(p, "%.2f / day" % (speed.get(p["product_id"], 0) / 30.0)) for p in prods
          if _stocked(p) and speed.get(p["product_id"], 0) > 0 and _f(p["rl"]) <= 0
          and _f(p.get("min_stock")) <= 0]),
    ]
    out = []
    for key, title, fix, items in checks:
        out.append({"check": key, "title": title, "count": len(items), "fix": fix,
                    "samples": items[:max(1, int(samples or 15))]})
    return {"products": len(prods), "issues_total": sum(c["count"] for c in out),
            "checks": out}


# ── 9. prices below cost ─────────────────────────────────────
def price_check(min_margin=5.0):
    rows = INS.below_cost(float(min_margin or 5.0))
    return {"min_margin_pct": float(min_margin or 5.0),
            "below_cost": sum(1 for r in rows if r["loss"]),
            "thin_margin": sum(1 for r in rows if not r["loss"]),
            "rows": [{k: r[k] for k in ("code", "name", "price_net", "cost", "margin", "loss")}
                     for r in rows]}


# ── 10. one health score + what to do ────────────────────────
def health(today=None):
    today = today or date.today()
    prods = _products()
    val_cost = sum(max(_f(p["stock"]), 0) * _cost(p) for p in prods if _stocked(p))
    val_price = sum(max(_f(p["stock"]), 0) * _f(p["price"]) for p in prods if _stocked(p))
    fc = forecast(today=today)
    cnt = {s: 0 for s in STATUS_ORDER}
    for r in fc:
        cnt[r["status"]] += 1
    over_val = sum(r["stock_value"] for r in fc if r["status"] == "overstock")
    dead = INS.dead_stock()
    dead_val = sum(_f(x["value"]) for x in dead)
    below = INS.below_cost()
    loss = [x for x in below if x["loss"]]
    ex = expiry(30, today)
    dq = data_check(samples=3, today=today)
    a = abc(today=today, fc=fc)
    tr = transfers(today=today)
    neg = next((c["count"] for c in dq["checks"] if c["check"] == "negative_stock"), 0)
    score = 100.0
    score -= min(25, cnt["out"] * 4 + cnt["critical"] * 2 + cnt["low"] * 0.5)
    score -= min(15, (dead_val / val_cost * 100.0 * 0.5) if val_cost else 0)
    score -= min(15, len(loss) * 3)
    score -= min(15, ex["expired"]["batches"] * 5 + (3 if ex["at_risk_value"] > 0 else 0))
    score -= min(10, neg * 2)
    score -= min(10, len(a["a_items_at_risk"]) * 3)
    score -= min(10, dq["issues_total"] * 0.2)
    score = max(0, int(round(score)))
    grade = "Good" if score >= 85 else ("Fair" if score >= 65 else "Needs work")

    def names(rows, n=3, key="name"):
        s = ", ".join(str(r.get(key)) for r in rows[:n])
        return s + (" …" if len(rows) > n else "")
    actions = []
    urgent = [r for r in fc if r["status"] in ("out", "critical")]
    if urgent:
        actions.append(("high", "Order now: %d item(s) out or running out within 3 days — %s"
                        % (len(urgent), names(urgent))))
    if a["a_items_at_risk"]:
        actions.append(("high", "Best sellers (A) running low: %s" % names(a["a_items_at_risk"])))
    if ex["expired"]["batches"]:
        actions.append(("high", "%d expired batch(es), %s SAR — take off the shelf, write off or "
                        "return" % (ex["expired"]["batches"], "{:,.2f}".format(ex["expired"]["value"]))))
    if loss:
        actions.append(("high", "%d item(s) priced BELOW cost — %s" % (len(loss), names(loss))))
    if neg:
        actions.append(("medium", "%d item(s) with minus stock — post the purchases or count them" % neg))
    risky = [x for x in ex["rows"] if x["qty_at_risk"] > 0 and (x["days_left"] or 0) >= 0]
    if risky:
        actions.append(("medium", "%s SAR of stock may expire before it sells — %s"
                        % ("{:,.2f}".format(ex["at_risk_value"]), names(risky))))
    if tr.get("suggestions"):
        s = tr["suggestions"][0]
        actions.append(("medium", "Move stock between branches instead of buying: %d suggestion(s), "
                        "e.g. %g × %s %s → %s" % (len(tr["suggestions"]), s["qty"], s["name"],
                                                  s["from_branch"], s["to_branch"])))
    if dead:
        actions.append(("medium", "Money stuck: %d item(s) not sold for 60 days (%s SAR) — "
                        "make an offer" % (len(dead), "{:,.2f}".format(dead_val))))
    if cnt["low"]:
        lows = [r for r in fc if r["status"] == "low"]
        actions.append(("low", "Plan the next order: %d item(s) run out within a week — %s"
                        % (len(lows), names(lows))))
    if over_val > 0:
        actions.append(("low", "%d item(s) with more than 4 months of stock (%s SAR) — buy less"
                        % (cnt["overstock"], "{:,.2f}".format(over_val))))
    if dq["issues_total"]:
        top = sorted(dq["checks"], key=lambda c: -c["count"])[0]
        actions.append(("low", "Fix product data: %d issue(s) (most: %s — %d)"
                        % (dq["issues_total"], top["title"].lower(), top["count"])))
    if not actions:
        actions.append(("low", "All good — nothing needs attention right now."))
    return {"score": score, "grade": grade, "date": today.isoformat(),
            "stock_value_cost": round(val_cost, 2), "stock_value_price": round(val_price, 2),
            "products": len(prods),
            "status_counts": {STATUS_TEXT[k]: v for k, v in cnt.items()},
            "dead_stock": {"items": len(dead), "value": round(dead_val, 2)},
            "below_cost": len(loss), "expired_batches": ex["expired"]["batches"],
            "expiry_value_at_risk": ex["at_risk_value"],
            "a_items_at_risk": len(a["a_items_at_risk"]),
            "branch_transfers": len(tr.get("suggestions") or []),
            "data_issues": dq["issues_total"],
            "actions": [{"priority": p, "what": w} for p, w in actions]}
