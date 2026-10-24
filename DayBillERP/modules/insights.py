# ============================================================
# DayBill ERP - Smart Insights (the shop's "AI assistant")
# ------------------------------------------------------------
# Works offline on your own data — nothing leaves the PC:
#
#   reorder()      what will run out soon and how much to order
#                  (sales speed of the last N days → days of stock left)
#   dead_stock()   items with stock but no sale for N days (money stuck)
#   below_cost()   selling price at or below the average cost / thin margin
#   trends()       this week vs last week, best weekday, best hour,
#                  products going up / down
#   watch()        things to check today: deleted bills, big discounts,
#                  cash short/over at day close, many returns
#   briefing()     a short plain-language summary of all the above
# ============================================================

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


def _q(sql, params=()):
    try:
        return db.fetchall(sql, params) or []
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


def _sold_base(days, upto=None):
    """{product_id: qty sold in BASE units} over the last `days` days,
    from the stock movements of confirmed sales (net of sales returns)."""
    upto = upto or date.today()
    start = upto - timedelta(days=max(1, days) - 1)
    out = {}
    for r in _q("SELECT product_id, txn_type, SUM(ISNULL(qty_out_base,0)) AS qout, "
                "SUM(ISNULL(qty_in_base,0)) AS qin FROM inventory_transactions "
                "WHERE txn_type IN ('sale','return_in') AND txn_date BETWEEN ? AND ? "
                "GROUP BY product_id, txn_type", (start.isoformat(), upto.isoformat())):
        pid = r["product_id"]
        if r["txn_type"] == "sale":
            out[pid] = out.get(pid, 0.0) + _f(r["qout"])
        else:
            out[pid] = out.get(pid, 0.0) - _f(r["qin"])
    return out


def _products():
    return _q("SELECT product_id, product_code, product_name_en, "
              "ISNULL(stock_quantity,0) AS stock, ISNULL(reorder_level,0) AS rl, "
              "ISNULL(average_cost,0) AS avg_cost, ISNULL(purchase_price,0) AS pp, "
              "ISNULL(unit_price,0) AS price, ISNULL(track_inventory,1) AS track, "
              "ISNULL(product_type,'product') AS ptype, vat_category_id "
              "FROM products WHERE is_active=1")


def _purchase_unit(pid):
    """(unit name, factor) the product is normally bought in."""
    rows = _q("SELECT unit_name_en, ISNULL(conversion_factor,1) AS f, "
              "ISNULL(is_default_purchase,0) AS dp FROM product_units "
              "WHERE product_id=? AND ISNULL(is_active,1)=1 ORDER BY conversion_factor",
              (pid,))
    u = next((r for r in rows if r.get("dp")), None) or (rows[0] if rows else None)
    if not u:
        return "Unit", 1.0
    return u["unit_name_en"], max(1.0, _f(u["f"]))


def _last_supplier(pid):
    r = _q("SELECT TOP 1 pi.supplier_id, pi.supplier_name_en, pil.unit_price, "
           "pil.unit_of_measure_en FROM purchase_invoice_lines pil "
           "JOIN purchase_invoices pi ON pi.purchase_id=pil.purchase_id "
           "WHERE pil.product_id=? AND pi.invoice_status='confirmed' "
           "ORDER BY pi.invoice_date DESC, pi.purchase_id DESC", (pid,))
    return r[0] if r else {}


# ── 1. reorder suggestions ───────────────────────────────────
def reorder(days=30, cover_days=14, warn_days=7):
    """Items that run out within `warn_days` (or are at the reorder
    level), with a suggested order to cover `cover_days` of sales."""
    sold = _sold_base(days)
    out = []
    for p in _products():
        if str(p["ptype"]).lower() == "service":        # same rule as doc_posting
            continue
        per_day = max(0.0, sold.get(p["product_id"], 0.0)) / float(days)
        stock = _f(p["stock"])
        rl = _f(p["rl"])
        left = (stock / per_day) if per_day > 0 else None
        urgent = (left is not None and left <= warn_days) or (rl > 0 and stock <= rl)
        if not urgent:
            continue
        need = max(per_day * cover_days - stock, rl - stock if rl else 0.0, 0.0)
        if need <= 0 and stock > 0:
            continue
        unit, factor = _purchase_unit(p["product_id"])
        units_to_order = max(1, int(-(-need // factor))) if need > 0 else 1
        sup = _last_supplier(p["product_id"])
        cost_base = _f(p["avg_cost"]) or _f(p["pp"])
        # the supplier's last price counts only when it was for this unit
        unit_cost = (_f(sup.get("unit_price"))
                     if str(sup.get("unit_of_measure_en") or "") == unit else 0.0) \
            or cost_base * factor
        out.append({
            "product_id": p["product_id"], "code": p["product_code"],
            "name": p["product_name_en"], "stock": stock, "per_day": round(per_day, 2),
            "days_left": None if left is None else round(left, 1),
            "order_qty": units_to_order, "unit": unit, "factor": factor,
            "supplier_id": sup.get("supplier_id"), "supplier": sup.get("supplier_name_en") or "",
            "unit_cost": round(unit_cost, 2),
            "value": round(units_to_order * unit_cost, 2),
        })
    out.sort(key=lambda r: (r["days_left"] if r["days_left"] is not None else -1, r["name"]))
    return out


# ── 2. dead / slow stock ─────────────────────────────────────
def dead_stock(days=60):
    """Items with stock on hand but not sold for `days` days."""
    since = (date.today() - timedelta(days=days)).isoformat()
    last = {r["product_id"]: _d(r["d"]) for r in _q(
        "SELECT product_id, MAX(txn_date) AS d FROM inventory_transactions "
        "WHERE txn_type='sale' GROUP BY product_id")}
    out = []
    for p in _products():
        stock = _f(p["stock"])
        if p["ptype"] == "service" or stock <= 0:
            continue
        ls = last.get(p["product_id"])
        if ls and ls.isoformat() >= since:
            continue
        value = round(stock * (_f(p["avg_cost"]) or _f(p["pp"])), 2)
        out.append({"product_id": p["product_id"], "code": p["product_code"],
                    "name": p["product_name_en"], "stock": stock,
                    "last_sale": ls.isoformat() if ls else "never",
                    "value": value})
    out.sort(key=lambda r: -r["value"])
    return out


# ── 3. selling below cost / thin margin ──────────────────────
def below_cost(min_margin=5.0):
    """Base-unit selling price (before VAT) vs average cost."""
    try:
        from config import settings as cfg
        incl = str(cfg.get("sales_price_tax_mode", "inclusive")).lower() == "inclusive"
    except Exception:
        incl = True
    rates = {r["vat_category_id"]: _f(r["vat_rate"]) for r in _q(
        "SELECT vat_category_id, vat_rate FROM vat_categories")}
    base_price = {r["product_id"]: _f(r["sp"]) for r in _q(
        "SELECT product_id, selling_price AS sp FROM product_units "
        "WHERE ISNULL(conversion_factor,1)=1 AND ISNULL(is_active,1)=1")}
    out = []
    for p in _products():
        cost = _f(p["avg_cost"]) or _f(p["pp"])
        if cost <= 0 or p["ptype"] == "service":
            continue
        price = base_price.get(p["product_id"]) or _f(p["price"])
        if price <= 0:
            continue
        net = price / (1 + rates.get(p["vat_category_id"], 15.0) / 100.0) if incl else price
        margin = (net - cost) / net * 100.0 if net else 0.0
        if margin < min_margin:
            out.append({"product_id": p["product_id"], "code": p["product_code"],
                        "name": p["product_name_en"], "price_net": round(net, 2),
                        "cost": round(cost, 2), "margin": round(margin, 1),
                        "loss": net < cost})
    out.sort(key=lambda r: r["margin"])
    return out


# ── 4. trends ────────────────────────────────────────────────
def _sales_rows(d1, d2):
    return _q("SELECT invoice_date, invoice_time, ISNULL(total_amount,0) AS t "
              "FROM sales_invoices WHERE invoice_status='confirmed' "
              "AND invoice_date BETWEEN ? AND ?", (d1.isoformat(), d2.isoformat()))


def trends():
    today = date.today()
    this_w = sum(_f(r["t"]) for r in _sales_rows(today - timedelta(days=6), today))
    last_w = sum(_f(r["t"]) for r in _sales_rows(today - timedelta(days=13),
                                                 today - timedelta(days=7)))
    change = ((this_w - last_w) / last_w * 100.0) if last_w else None
    rows = _sales_rows(today - timedelta(days=89), today)
    wd = {}
    hr = {}
    for r in rows:
        d = _d(r["invoice_date"])
        if d:
            wd[d.strftime("%A")] = wd.get(d.strftime("%A"), 0.0) + _f(r["t"])
        t = r.get("invoice_time")
        try:
            h = t.hour if hasattr(t, "hour") else int(str(t)[:2])
            hr[h] = hr.get(h, 0.0) + _f(r["t"])
        except Exception:
            pass
    best_day = max(wd.items(), key=lambda x: x[1])[0] if wd else ""
    best_hour = max(hr.items(), key=lambda x: x[1])[0] if hr else None
    now = _sold_base(14)
    before = _sold_base(14, today - timedelta(days=14))
    names = {p["product_id"]: p["product_name_en"] for p in _products()}
    moves = []
    for pid in set(now) | set(before):
        a, b = now.get(pid, 0.0), before.get(pid, 0.0)
        if a + b < 3:
            continue
        pct = ((a - b) / b * 100.0) if b else 100.0
        moves.append({"product_id": pid, "name": names.get(pid, str(pid)),
                      "now": round(a, 2), "before": round(b, 2), "change": round(pct, 1)})
    up = sorted([m for m in moves if m["change"] > 0], key=lambda m: -m["change"])[:5]
    down = sorted([m for m in moves if m["change"] < 0], key=lambda m: m["change"])[:5]
    return {"this_week": round(this_w, 2), "last_week": round(last_w, 2),
            "change": None if change is None else round(change, 1),
            "best_day": best_day, "best_hour": best_hour,
            "by_weekday": wd, "up": up, "down": down}


# ── 5. things to check today ─────────────────────────────────
def watch(big_discount_pct=20.0):
    today = date.today().isoformat()
    out = []
    n = _q("SELECT COUNT(*) AS n FROM audit_logs WHERE LOWER(action)='delete' "
           "AND CONVERT(date, created_at)=?", (today,))
    if n and _f(n[0]["n"]):
        out.append(("🗑", f"{int(_f(n[0]['n']))} document(s) deleted today",
                    "See Audit Log for who and what."))
    for r in _q("SELECT invoice_number, ISNULL(discount_amount,0) AS d, "
                "ISNULL(subtotal_amount,0) AS s FROM sales_invoices "
                "WHERE invoice_status='confirmed' AND invoice_date=?", (today,)):
        s, dsc = _f(r["s"]), _f(r["d"])
        if s > 0 and dsc / (s + dsc) * 100.0 >= big_discount_pct:
            out.append(("🏷", f"Big discount on bill {r['invoice_number']}",
                        f"{dsc:,.2f} SAR ({dsc / (s + dsc) * 100:.0f}%)."))
    ret = _q("SELECT COUNT(*) AS n, ISNULL(SUM(total_amount),0) AS t FROM sales_returns "
             "WHERE return_status='confirmed' AND return_date=?", (today,))
    if ret and _f(ret[0]["n"]) >= 3:
        out.append(("↩", f"{int(_f(ret[0]['n']))} sales returns today",
                    f"{_f(ret[0]['t']):,.2f} SAR returned."))
    neg = _q("SELECT COUNT(*) AS n FROM products WHERE is_active=1 "
             "AND ISNULL(track_inventory,1)=1 AND ISNULL(stock_quantity,0) < 0")
    if neg and _f(neg[0]["n"]):
        out.append(("⚠", f"{int(_f(neg[0]['n']))} item(s) with negative stock",
                    "Sold more than received — check purchases / stock count."))
    return out


# ── summary in plain words ───────────────────────────────────
def briefing():
    lines = []
    try:
        t = trends()
        if t["change"] is not None:
            word = "up" if t["change"] >= 0 else "down"
            lines.append(f"Sales this week {t['this_week']:,.2f} SAR — {word} "
                         f"{abs(t['change']):.0f}% on last week.")
        elif t["this_week"]:
            lines.append(f"Sales this week {t['this_week']:,.2f} SAR.")
        if t["best_day"]:
            h = t["best_hour"]
            lines.append(f"Busiest day: {t['best_day']}"
                         + (f", busiest hour {h:02d}:00–{(h + 1) % 24:02d}:00." if h is not None else "."))
        if t["up"]:
            lines.append("Selling faster: " + ", ".join(m["name"] for m in t["up"][:3]) + ".")
    except Exception:
        pass
    r = reorder()
    if r:
        soon = [x for x in r if x["days_left"] is not None and x["days_left"] <= 3]
        lines.append(f"{len(r)} item(s) to reorder"
                     + (f" — {len(soon)} run out within 3 days." if soon else "."))
    d = dead_stock()
    if d:
        lines.append(f"{len(d)} item(s) not sold for 60 days — "
                     f"{sum(x['value'] for x in d):,.2f} SAR of stock waiting.")
    b = below_cost()
    loss = [x for x in b if x["loss"]]
    if loss:
        lines.append(f"{len(loss)} item(s) priced BELOW cost — check prices.")
    for icon, title, _ in watch():
        lines.append(f"{icon} {title}.")
    return lines or ["All good — nothing needs attention right now."]
