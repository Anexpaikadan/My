# ============================================================
# DayBill ERP - extra product facts for any table (v6.9.4)
# ------------------------------------------------------------
# The columns tool (ui/table_columns.py), the Report Center and the
# entry grids can show more about each product than the screen itself
# reads: cost, profit, profit %, PLU, stock, units 1-3, every barcode …
#
#   FIELDS                    the extra columns, in menu order
#   fields()                  FIELDS this user may see (cost / profit need
#                             the purchase or reports right)
#   resolve(ref)              product id from an id, code or barcode
#   values(ref, qty=None, net=None, unit=None, mode="sale")
#       every x_… value of that product. Profit:
#         mode "sale"      net sale (no VAT) − cost × qty in base units
#         mode "purchase"  sale price (no VAT) × base qty − net cost
#         no qty / net     profit of ONE base unit (price − cost)
#       Profit % = profit ÷ sale value × 100 (the margin).
# Everything is read with a few queries and kept for CACHE_SECONDS, so a
# list of thousands of rows does not ask the database once per row.
# ============================================================

import time

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

CACHE_SECONDS = 30

# key, label, kind (text | money | qty | pct), width, cost-sensitive
FIELDS = [
    ("x_profit", "Profit", "money", 90, True),
    ("x_profit_pct", "Profit %", "pct", 70, True),
    ("x_cost", "Product Cost", "money", 95, True),
    ("x_last_cost", "Last Purchase Cost", "money", 110, True),
    ("x_price", "Sale Price", "money", 90, False),
    ("x_plu", "PLU No", "text", 70, False),
    ("x_stock", "Stock", "qty", 80, False),
    ("x_stock_value", "Stock Value", "money", 100, True),
    ("x_reorder", "Reorder Level", "qty", 85, False),
    ("x_unit1", "Unit 1", "text", 150, False),
    ("x_unit2", "Unit 2", "text", 150, False),
    ("x_unit3", "Unit 3", "text", 150, False),
    ("x_barcode", "Barcode", "text", 120, False),
    ("x_barcodes", "Multi Barcode", "text", 210, False),
    ("x_name_ar", "Arabic Name", "text", 160, False),
    ("x_category", "Category", "text", 120, False),
    ("x_brand", "Brand", "text", 100, False),
    ("x_vat", "VAT %", "pct", 60, False),
    ("x_location", "Location", "text", 90, False),
]
KEYS = [f[0] for f in FIELDS]
BY_KEY = {f[0]: f for f in FIELDS}
COST_KEYS = {f[0] for f in FIELDS if f[4]}

_CACHE = {"at": 0.0, "by_id": {}, "by_code": {}, "by_bc": {}}


def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def can_see_cost():
    """Cost, profit and stock value: users who may see purchases or
    reports (a cashier with only sales rights does not)."""
    try:
        from modules import permissions as perm
        return bool(perm.can("purchase", "view") or perm.can("reports", "view"))
    except Exception:
        return True


def fields(with_cost=None):
    see = can_see_cost() if with_cost is None else with_cost
    return [f for f in FIELDS if see or not f[4]]


def invalidate():
    _CACHE["at"] = 0.0


def _rows(sql, params=()):
    try:
        return db.fetchall(sql, tuple(params)) or []
    except Exception:
        return []


def _incl():
    try:
        from config import settings as cfg
        return str(cfg.get("sales_price_tax_mode", "inclusive") or "").lower() == "inclusive"
    except Exception:
        return True


def _cost_of(p):
    for k in ("average_cost", "purchase_price", "last_purchase_cost"):
        if _f(p.get(k)) > 0:
            return _f(p.get(k))
    return 0.0


def _load():
    if time.time() - _CACHE["at"] < CACHE_SECONDS and _CACHE["by_id"]:
        return _CACHE
    by_id, by_code, by_bc = {}, {}, {}
    cats = {r["category_id"]: r.get("category_name_en") or ""
            for r in _rows("SELECT category_id, category_name_en FROM product_categories")}
    brands = {r["brand_id"]: r.get("brand_name_en") or ""
              for r in _rows("SELECT brand_id, brand_name_en FROM product_brands")}
    rates = {r["vat_category_id"]: _f(r.get("vat_rate"))
             for r in _rows("SELECT vat_category_id, vat_rate FROM vat_categories")}
    incl = _incl()
    for p in _rows("SELECT * FROM products"):
        pid = p["product_id"]
        rate = rates.get(p.get("vat_category_id"), 15.0)
        price = _f(p.get("unit_price"))
        d = {"pid": pid, "code": str(p.get("product_code") or ""),
             "price": price, "price_ex": price / (1 + rate / 100.0) if incl and rate else price,
             "cost": _cost_of(p), "last_cost": _f(p.get("last_purchase_cost")) or _f(p.get("purchase_price")),
             "stock": _f(p.get("stock_quantity")), "reorder": _f(p.get("reorder_level")),
             "plu": "" if p.get("scale_plu") in (None, "") else str(p.get("scale_plu")),
             "barcode": str(p.get("barcode") or ""), "name_ar": p.get("product_name_ar") or "",
             "category": cats.get(p.get("category_id"), ""), "brand": brands.get(p.get("brand_id"), ""),
             "vat": rate, "location": p.get("storage_location") or "",
             "base_unit": p.get("unit_of_measure_en") or "", "units": [], "barcodes": []}
        if d["barcode"]:
            d["barcodes"].append(d["barcode"])
            by_bc.setdefault(d["barcode"], pid)
        by_id[pid] = d
        if d["code"]:
            by_code[d["code"].lower()] = pid
    for u in _rows("SELECT unit_id, product_id, unit_name_en, conversion_factor, selling_price, "
                   "purchase_price, barcode, is_active FROM product_units "
                   "ORDER BY product_id, conversion_factor, unit_id"):
        d = by_id.get(u["product_id"])
        if d is None or u.get("is_active") in (0, False):
            continue
        d["units"].append({"name": u.get("unit_name_en") or "", "factor": _f(u.get("conversion_factor")) or 1.0,
                           "price": _f(u.get("selling_price")), "id": u.get("unit_id")})
        bc = str(u.get("barcode") or "")
        if bc and bc not in d["barcodes"]:
            d["barcodes"].append(bc)
            by_bc.setdefault(bc, u["product_id"])
    for d in by_id.values():             # Unit 1 = the base unit (× 1), then the bigger ones
        if not any(abs(x["factor"] - 1.0) < 1e-9 for x in d["units"]):
            d["units"].insert(0, {"name": d["base_unit"] or "Unit", "factor": 1.0,
                                  "price": d["price"], "id": None})
        d["units"].sort(key=lambda x: x["factor"])
    for b in _rows("SELECT product_id, barcode FROM product_unit_barcodes"):
        d = by_id.get(b.get("product_id"))
        bc = str(b.get("barcode") or "")
        if d is not None and bc and bc not in d["barcodes"]:
            d["barcodes"].append(bc)
            by_bc.setdefault(bc, d["pid"])
    _CACHE.update(at=time.time(), by_id=by_id, by_code=by_code, by_bc=by_bc)
    return _CACHE


def resolve(ref):
    """Product id from a product id, a product code or any barcode."""
    if ref in (None, ""):
        return None
    c = _load()
    if isinstance(ref, int) and ref in c["by_id"]:
        return ref
    s = str(ref).strip()
    return c["by_code"].get(s.lower()) or c["by_bc"].get(s)


def product(ref):
    pid = resolve(ref)
    return _load()["by_id"].get(pid) if pid is not None else None


def factor(ref, unit=None):
    """Base units in one `unit` of the product (1 for the base unit)."""
    d = product(ref)
    if not d or not unit:
        return 1.0
    u = str(unit).strip().lower()
    for x in d["units"]:
        if x["name"].strip().lower() == u:
            return x["factor"] or 1.0
    return 1.0


def _unit_text(x):
    if not x:
        return ""
    t = "%s × %g" % (x["name"], x["factor"])
    if x["price"]:
        t += "  = %.2f" % x["price"]
    return t


def values(ref, qty=None, net=None, unit=None, mode="sale"):
    """{x_key: value} for one product (raw numbers; empty when unknown)."""
    d = product(ref)
    if not d:
        return {}
    cost, price_ex = d["cost"], d["price_ex"]
    if qty is None and net is None:                     # one base unit
        sale, profit = price_ex, price_ex - cost
    else:
        base_qty = _f(qty) * factor(d["pid"], unit)
        if mode == "purchase":
            sale = price_ex * base_qty
            profit = sale - _f(net) if net is not None else (price_ex - cost) * base_qty
        elif net is None:                               # stock: what it would earn
            sale = price_ex * base_qty
            profit = (price_ex - cost) * base_qty
        else:
            sale = _f(net)
            profit = sale - cost * base_qty
    units = (d["units"] + [None, None, None])[:3]
    return {
        "_sale": round(sale, 2),                         # for a total Profit %
        "x_profit": round(profit, 2),
        "x_profit_pct": round(profit / sale * 100.0, 2) if sale else None,
        "x_cost": round(cost, 4), "x_last_cost": round(d["last_cost"], 4),
        "x_price": d["price"], "x_plu": d["plu"], "x_stock": d["stock"],
        "x_stock_value": round(d["stock"] * cost, 2), "x_reorder": d["reorder"],
        "x_unit1": _unit_text(units[0]),
        "x_unit2": _unit_text(units[1]), "x_unit3": _unit_text(units[2]),
        "x_barcode": d["barcode"], "x_barcodes": ", ".join(d["barcodes"]),
        "x_name_ar": d["name_ar"], "x_category": d["category"], "x_brand": d["brand"],
        "x_vat": d["vat"], "x_location": d["location"],
    }


def text(key, value):
    """A value as the screen shows it."""
    if value is None or value == "":
        return ""
    kind = BY_KEY.get(key, (key, "", "text"))[2]
    try:
        if kind == "money":
            x = float(value)
            return "(%s)" % format(abs(x), ",.2f") if x < 0 else format(x, ",.2f")
        if kind == "pct":
            return "%.2f%%" % float(value) if key != "x_vat" else "%g%%" % float(value)
        if kind == "qty":
            return "%g" % float(value)
    except Exception:
        pass
    return str(value)
