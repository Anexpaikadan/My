# ============================================================
# DayBill ERP - bill of materials / recipes (v7.0)
# ------------------------------------------------------------
# ONE list of "what goes into a product", shared by:
#   Production  - a production entry uses up the components and makes
#                 the finished product (modules/production.py)
#   Restaurant  - a dish whose recipe is marked "use up on sale": selling
#                 the dish takes its ingredients out of stock (doc_posting)
#
# Tables (database/patches/zzz_v700_patch.sql):
#   bom_headers  bom_id, product_id, bom_name, output_qty, output_unit,
#                labour_cost, overhead_cost, deduct_on_sale, is_default,
#                is_active, notes
#   bom_lines    line_id, bom_id, component_id, quantity, unit_name,
#                waste_pct, notes, sort_order
#
#   get(product_id)                the product's recipe {header, lines}
#   save(product_id, header, lines) → bom_id
#   delete(bom_id)
#   explode(product_id, qty_base)  [(component_id, base qty, unit cost)]
#                                  for qty_base of the product
#   cost(product_id)               cost of ONE base unit of the product
#                                  from its recipe (materials + labour +
#                                  overhead), None without a recipe
#   deducts_on_sale(product_id)    True when selling it uses up its recipe
#
# For the Recipes / Bill of Materials screen (ui/bom_editor.py):
#   units(product_id)              the product's unit names, base unit first
#   cost_each(component_id, unit)  cost of ONE unit of a component
#   sale_price(product_id, unit)   selling price of one unit, without VAT
#   rollup(product_id, head, rows) batch cost, cost per unit, profit …
#   with_recipe(text)              products that have a recipe (the list)
# ============================================================

import time

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

MAX_DEPTH = 4
_CACHE = {"at": 0.0, "sale": {}}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        return bool(db.execute_scalar("SELECT CASE WHEN OBJECT_ID('bom_headers','U') IS NULL "
                                      "THEN 0 ELSE 1 END"))
    except Exception:
        return False


def invalidate():
    _CACHE.update(at=0.0, sale={})


def _factor(pid, unit):
    try:
        from modules.doc_posting import unit_factor
        return unit_factor(pid, unit)
    except Exception:
        return 1.0


def _unit_cost(pid):
    try:
        from modules.doc_posting import unit_cost
        return unit_cost(pid)
    except Exception:
        return 0.0


def header(product_id):
    try:
        return db.fetchone("SELECT TOP 1 * FROM bom_headers WHERE product_id=? AND ISNULL(is_active,1)=1 "
                           "ORDER BY is_default DESC, bom_id", (int(product_id),))
    except Exception:
        return None


def lines(bom_id):
    try:
        return db.fetchall(
            "SELECT bl.*, p.product_code, p.product_name_en, p.unit_of_measure_en AS base_unit, "
            "ISNULL(p.product_type,'product') AS product_type "
            "FROM bom_lines bl LEFT JOIN products p ON p.product_id=bl.component_id "
            "WHERE bl.bom_id=? ORDER BY bl.sort_order, bl.line_id", (int(bom_id),)) or []
    except Exception:
        return []


def get(product_id):
    h = header(product_id)
    if not h:
        return None
    return {"header": dict(h), "lines": [dict(x) for x in lines(h["bom_id"])]}


def save(product_id, head, rows):
    """Save (replace) the product's default recipe. head: bom_name,
    output_qty, output_unit, labour_cost, overhead_cost, deduct_on_sale,
    notes. rows: [{component_id, quantity, unit_name, waste_pct, notes}]."""
    head = dict(head or {})
    pid = int(product_id)
    good = []
    for i, r in enumerate(rows or []):
        cid = r.get("component_id")
        q = _f(r.get("quantity"))
        if not cid or q <= 0:
            continue
        if int(cid) == pid:
            raise ValueError("A product cannot be a component of itself.")
        good.append((int(cid), q, str(r.get("unit_name") or "")[:50],
                     _f(r.get("waste_pct")), str(r.get("notes") or "")[:200], i))
    if not good:
        raise ValueError("Add at least one component with a quantity.")
    for cid, *_ in good:
        if _uses(cid, pid, 0):
            raise ValueError("A component's own recipe uses this product (a loop).")
    vals = (str(head.get("bom_name") or "")[:200], max(_f(head.get("output_qty")), 0.0001),
            str(head.get("output_unit") or "")[:50], _f(head.get("labour_cost")),
            _f(head.get("overhead_cost")), 1 if head.get("deduct_on_sale") else 0,
            str(head.get("notes") or "")[:500])
    with db.transaction():           # header + lines: all of it, or none
        old = header(pid)
        if old:
            bid = int(old["bom_id"])
            db.execute("UPDATE bom_headers SET bom_name=?, output_qty=?, output_unit=?, "
                       "labour_cost=?, overhead_cost=?, deduct_on_sale=?, notes=?, "
                       "updated_at=GETDATE() WHERE bom_id=?", vals + (bid,))
            db.execute("DELETE FROM bom_lines WHERE bom_id=?", (bid,))
        else:
            bid = db.execute_scalar(
                "INSERT INTO bom_headers (product_id, bom_name, output_qty, output_unit, "
                "labour_cost, overhead_cost, deduct_on_sale, notes, is_default, is_active) "
                "OUTPUT INSERTED.bom_id VALUES (?,?,?,?,?,?,?,?,1,1)", (pid,) + vals)
            bid = int(bid)
        for cid, q, u, w, n, i in good:
            db.execute("INSERT INTO bom_lines (bom_id, component_id, quantity, unit_name, "
                       "waste_pct, notes, sort_order) VALUES (?,?,?,?,?,?,?)",
                       (bid, cid, q, u, w, n, i))
    invalidate()
    return bid


def delete(bom_id):
    with db.transaction():
        db.execute("DELETE FROM bom_lines WHERE bom_id=?", (int(bom_id),))
        db.execute("DELETE FROM bom_headers WHERE bom_id=?", (int(bom_id),))
    invalidate()


def _uses(product_id, target, depth):
    """True when product_id's recipe (at any depth) uses target."""
    if depth > MAX_DEPTH:
        return False
    h = header(product_id)
    if not h:
        return False
    for ln in lines(h["bom_id"]):
        c = ln.get("component_id")
        if c == target or _uses(c, target, depth + 1):
            return True
    return False


def explode(product_id, qty_base, depth=0, stock_only=True):
    """Components used for qty_base (base units) of the product:
    [(component_id, base qty, unit cost)]. A component that is not kept
    in stock (a service, or a sub-recipe made fresh — its own recipe
    marked "use up on sale") is opened up into its own components."""
    h = header(product_id)
    if not h or depth > MAX_DEPTH:
        return []
    out_q = _f(h.get("output_qty")) or 1.0
    out_f = _factor(product_id, h.get("output_unit")) if h.get("output_unit") else 1.0
    batches = _f(qty_base) / (out_q * (out_f or 1.0))
    res = {}
    for ln in lines(h["bom_id"]):
        cid = ln.get("component_id")
        if not cid:
            continue
        q = _f(ln.get("quantity")) * _factor(cid, ln.get("unit_name")) * batches
        q *= 1 + _f(ln.get("waste_pct")) / 100.0
        sub = header(cid)
        if sub and (str(ln.get("product_type") or "").lower() == "service" or sub.get("deduct_on_sale")):
            for c2, q2, k2 in explode(cid, q, depth + 1, stock_only):
                a = res.setdefault(c2, [0.0, k2])
                a[0] += q2
            continue
        if stock_only and str(ln.get("product_type") or "").lower() == "service":
            continue
        a = res.setdefault(cid, [0.0, _unit_cost(cid)])
        a[0] += q
    return [(c, round(v[0], 6), v[1]) for c, v in res.items() if v[0]]


def cost(product_id, depth=0):
    """Cost of ONE base unit of the product from its recipe."""
    h = header(product_id)
    if not h or depth > MAX_DEPTH:
        return None
    out_q = _f(h.get("output_qty")) or 1.0
    out_f = _factor(product_id, h.get("output_unit")) if h.get("output_unit") else 1.0
    base_out = out_q * (out_f or 1.0)
    mat = 0.0
    for ln in lines(h["bom_id"]):
        cid = ln.get("component_id")
        if not cid:
            continue
        q = _f(ln.get("quantity")) * _factor(cid, ln.get("unit_name"))
        q *= 1 + _f(ln.get("waste_pct")) / 100.0
        c = _unit_cost(cid)
        if c <= 0:
            sub = cost(cid, depth + 1)
            c = sub or 0.0
        mat += q * c
    total = mat + _f(h.get("labour_cost")) + _f(h.get("overhead_cost"))
    return round(total / base_out, 4) if base_out else None


def deducts_on_sale(product_id):
    """Selling this product uses up its recipe (restaurant dishes)."""
    if not product_id:
        return False
    if time.time() - _CACHE["at"] > 30:
        _CACHE.update(at=time.time(), sale={})
        try:
            rows = db.fetchall("SELECT DISTINCT product_id FROM bom_headers WHERE ISNULL(is_active,1)=1 "
                               "AND ISNULL(deduct_on_sale,0)=1") or []
            _CACHE["sale"] = {int(r["product_id"]): True for r in rows}
        except Exception:
            _CACHE["sale"] = {}
    return bool(_CACHE["sale"].get(int(product_id)))


# ── Recipes / Bill of Materials screen helpers ───────────────
def units(product_id):
    """The product's unit names: its base unit first, then its other
    units (Box, Carton, kg …)."""
    out = []
    try:
        base = db.execute_scalar("SELECT unit_of_measure_en FROM products WHERE product_id=?",
                                 (int(product_id),))
        out.append(str(base or "").strip() or "Unit")
        for r in db.fetchall("SELECT unit_name_en FROM product_units WHERE product_id=? "
                             "AND ISNULL(is_active,1)=1 ORDER BY conversion_factor, unit_id",
                             (int(product_id),)) or []:
            u = str(r.get("unit_name_en") or "").strip()
            if u and u not in out:
                out.append(u)
    except Exception:
        pass
    return out or ["Unit"]


def cost_each(component_id, unit_name=""):
    """Cost of ONE `unit_name` of a component: its average cost (else
    purchase price); a component with no cost but its own recipe is
    costed from that recipe."""
    if not component_id:
        return 0.0
    f = _factor(component_id, unit_name) if unit_name else 1.0
    c = _unit_cost(component_id)
    if c <= 0:
        c = cost(component_id) or 0.0
    return round(c * (f or 1.0), 6)


def sale_price(product_id, unit_name=""):
    """Selling price of ONE `unit_name` of the product WITHOUT VAT (what
    the shop keeps) — the unit's own price when it has one."""
    try:
        r = db.fetchone("SELECT ISNULL(p.unit_price,0) AS price, p.unit_of_measure_en AS base, "
                        "ISNULL(v.vat_rate,0) AS rate FROM products p LEFT JOIN vat_categories v "
                        "ON v.vat_category_id=p.vat_category_id WHERE p.product_id=?",
                        (int(product_id),))
    except Exception:
        r = None
    if not r:
        return 0.0
    price = _f(r.get("price")) * (_factor(product_id, unit_name) if unit_name else 1.0)
    if unit_name and unit_name != (r.get("base") or ""):
        try:
            up = db.execute_scalar("SELECT TOP 1 ISNULL(selling_price,0) FROM product_units "
                                   "WHERE product_id=? AND unit_name_en=? ORDER BY is_active DESC",
                                   (int(product_id), unit_name))
            if _f(up) > 0:
                price = _f(up)
        except Exception:
            pass
    rate = _f(r.get("rate"))
    try:
        from config import settings as _cfg
        incl = _cfg.sales_price_includes_vat()
    except Exception:
        incl = True
    if incl and rate:
        price = price / (1 + rate / 100.0)
    return round(price, 4)


def rollup(product_id, head, rows):
    """Live cost of a recipe as typed (nothing saved):
    head: output_qty, output_unit, labour_cost, overhead_cost
    rows: [{component_id, quantity, unit_name, waste_pct}]
    → {lines: [{cost_each, line_cost}], materials, labour, overhead, total,
       per_unit, sale, profit, pct} — per_unit / sale / profit are for ONE
    output unit."""
    head = dict(head or {})
    out_lines, mat = [], 0.0
    for r in rows or []:
        each = cost_each(r.get("component_id"), r.get("unit_name") or "")
        q = _f(r.get("quantity")) * (1 + _f(r.get("waste_pct")) / 100.0)
        lc = round(q * each, 4)
        mat += lc
        out_lines.append({"cost_each": each, "line_cost": lc})
    lab, ovh = _f(head.get("labour_cost")), _f(head.get("overhead_cost"))
    total = mat + lab + ovh
    oq = _f(head.get("output_qty")) or 1.0
    per = total / oq
    sale = sale_price(product_id, head.get("output_unit") or "") if product_id else 0.0
    profit = sale - per
    pct = (profit / sale * 100.0) if sale else None
    return {"lines": out_lines, "materials": round(mat, 4), "labour": round(lab, 4),
            "overhead": round(ovh, 4), "total": round(total, 4), "per_unit": round(per, 4),
            "sale": round(sale, 4), "profit": round(profit, 4),
            "pct": round(pct, 2) if pct is not None else None}


def with_recipe(text="", deduct=None):
    """Products that have a recipe, for the list on the left:
    [{product_id, product_code, product_name_en, bom_id, output_qty,
      output_unit, deduct_on_sale, n_lines}]. text filters by code / name
    / barcode; deduct=True / False keeps only recipes that do / don't use
    up on sale."""
    sql = ("SELECT h.bom_id, h.product_id, h.output_qty, h.output_unit, h.deduct_on_sale, "
           "p.product_code, p.product_name_en, ISNULL(p.barcode,'') AS barcode, "
           "(SELECT COUNT(*) FROM bom_lines l WHERE l.bom_id=h.bom_id) AS n_lines "
           "FROM bom_headers h JOIN products p ON p.product_id=h.product_id "
           "WHERE ISNULL(h.is_active,1)=1")
    params = []
    t = str(text or "").strip()
    if t:
        sql += " AND (p.product_code LIKE ? OR p.product_name_en LIKE ? OR p.barcode LIKE ?)"
        params += ["%" + t + "%"] * 3
    if deduct is not None:
        sql += " AND ISNULL(h.deduct_on_sale,0)=?"
        params.append(1 if deduct else 0)
    sql += " ORDER BY p.product_name_en, h.is_default DESC, h.bom_id"
    try:
        rows = db.fetchall(sql, tuple(params)) or []
    except Exception:
        return []
    seen, out = set(), []
    for r in rows:
        if r["product_id"] in seen:
            continue
        seen.add(r["product_id"])
        out.append(dict(r))
    return out
