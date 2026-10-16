# ============================================================
# DayBill ERP - what to order (suggested purchase order)  v6.0
# ------------------------------------------------------------
# Products at or below their reorder level (or minimum stock):
#   order = reorder quantity                      when it is set
#         = max stock − stock now                 when max stock is set
#         = enough for 14 days of sales, at least back to 2 × reorder level
# Only the products last bought from the chosen supplier when one is
# given. Purchase Orders ▸ 💡 Suggest fills the order with them.
# ============================================================
import sys, os, math
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _sold_per_day(days=30):
    since = (date.today() - timedelta(days=days)).isoformat()
    out = {}
    try:
        for r in db.fetchall("SELECT product_id, SUM(ISNULL(qty_out_base,0)) AS q FROM inventory_transactions "
                             "WHERE txn_type='sale' AND txn_date >= ? GROUP BY product_id", (since,)) or []:
            out[r["product_id"]] = _f(r["q"]) / float(days)
    except Exception:
        pass
    return out


def _last_supplier():
    out = {}
    try:
        for r in db.fetchall("SELECT pil.product_id, pi.supplier_id, pi.invoice_date, pi.purchase_id FROM "
                             "purchase_invoice_lines pil JOIN purchase_invoices pi ON "
                             "pi.purchase_id=pil.purchase_id WHERE pi.invoice_status='confirmed' "
                             "ORDER BY pi.invoice_date, pi.purchase_id") or []:
            out[r["product_id"]] = r["supplier_id"]
    except Exception:
        pass
    return out


def suggest(supplier_id=None, days_cover=14, limit=300):
    try:
        rows = db.fetchall(
            "SELECT product_id, product_code, product_name_en, ISNULL(stock_quantity,0) AS stock, "
            "ISNULL(reorder_level,0) AS reorder_level, ISNULL(reorder_quantity,0) AS reorder_quantity, "
            "ISNULL(min_stock,0) AS min_stock, ISNULL(max_stock,0) AS max_stock, "
            "ISNULL(purchase_price,0) AS cost FROM products WHERE ISNULL(is_active,1)=1 "
            "AND ISNULL(product_type,'product')<>'service'") or []
    except Exception:
        try:
            rows = db.fetchall(
                "SELECT product_id, product_code, product_name_en, ISNULL(stock_quantity,0) AS stock, "
                "ISNULL(reorder_level,0) AS reorder_level FROM products WHERE ISNULL(is_active,1)=1") or []
        except Exception:
            return []
    per_day = _sold_per_day()
    last = _last_supplier() if supplier_id else {}
    out = []
    for r in rows:
        stock = _f(r.get("stock"))
        level = max(_f(r.get("reorder_level")), _f(r.get("min_stock")))
        if level <= 0 or stock > level:
            continue
        if supplier_id and last.get(r["product_id"]) not in (None, int(supplier_id)):
            continue
        rq, mx = _f(r.get("reorder_quantity")), _f(r.get("max_stock"))
        if rq > 0:
            q = rq
        elif mx > 0:
            q = mx - stock
        else:
            q = max(2 * level - stock, per_day.get(r["product_id"], 0.0) * days_cover - stock)
        q = math.ceil(max(q, 0.0))
        if q <= 0:
            continue
        out.append({"product_id": r["product_id"], "code": r.get("product_code"),
                    "name": r.get("product_name_en"), "stock": stock, "level": level,
                    "per_day": round(per_day.get(r["product_id"], 0.0), 2), "qty": q,
                    "cost": _f(r.get("cost"))})
    out.sort(key=lambda x: (x["stock"] - x["level"], x["name"] or ""))
    return out[:limit]
