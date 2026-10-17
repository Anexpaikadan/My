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
    old = header(pid)
    if old:
        bid = int(old["bom_id"])
        db.execute("UPDATE bom_headers SET bom_name=?, output_qty=?, output_unit=?, labour_cost=?, "
                   "overhead_cost=?, deduct_on_sale=?, notes=?, updated_at=GETDATE() WHERE bom_id=?",
                   vals + (bid,))
        db.execute("DELETE FROM bom_lines WHERE bom_id=?", (bid,))
    else:
        bid = db.execute_scalar(
            "INSERT INTO bom_headers (product_id, bom_name, output_qty, output_unit, labour_cost, "
            "overhead_cost, deduct_on_sale, notes, is_default, is_active) "
            "OUTPUT INSERTED.bom_id VALUES (?,?,?,?,?,?,?,?,1,1)", (pid,) + vals)
        bid = int(bid)
    for cid, q, u, w, n, i in good:
        db.execute("INSERT INTO bom_lines (bom_id, component_id, quantity, unit_name, waste_pct, "
                   "notes, sort_order) VALUES (?,?,?,?,?,?,?)", (bid, cid, q, u, w, n, i))
    invalidate()
    return bid


def delete(bom_id):
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
