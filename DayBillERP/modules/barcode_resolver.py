# ============================================================
# DayBill ERP - ONE barcode resolver for every scan box
# ------------------------------------------------------------
# resolve(code) answers "what is this code?" the same way in POS,
# Sales / Purchase / Returns / Quotes, Offers, stock screens and the
# label printer:
#
#   1. a unit's own barcode          (product_units.barcode)  → that unit
#   2. an extra barcode of a unit    (product_unit_barcodes)  → that unit
#   3. the product's main barcode    (products.barcode)       → default unit
#   4. the product code typed exactly                         → default unit
#   5. a weighing-scale label (PLU + weight or price inside)  → base unit,
#      with the weighed quantity / label amount
#
# The answer is a plain dict:
#   product_id, product (full products row), unit_id (None when the code
#   was not a unit's own), unit (the unit row that applies), unit_name,
#   factor, price, barcode, via ('unit'|'extra'|'product'|'code'|'scale'),
#   quantity (1, or the weight of a scale label), amount (price labels),
#   active (product is active)
#
# ensure_barcodes() gives every product and every unit its own barcode
# (following Settings ▸ Barcode), so each one can be scanned and printed.
# ============================================================
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def clean(code):
    """What a scanner / keyboard really sent: trimmed, Arabic digits made
    plain, no spaces or the stray CR/TAB some scanners add."""
    s = str(code or "").translate(_AR_DIGITS)
    return "".join(s.split())


def _one(sql, params=()):
    try:
        return db.fetchone(sql, params)
    except Exception:
        return None


def _all(sql, params=()):
    try:
        return db.fetchall(sql, params) or []
    except Exception:
        return []


def units_of(product_id):
    """Active units of a product, smallest first (base unit first)."""
    rows = _all("SELECT unit_id, product_id, unit_name_en, ISNULL(unit_name_ar,'') AS unit_name_ar, "
                "conversion_factor, selling_price, purchase_price, ISNULL(barcode,'') AS barcode, "
                "is_default FROM product_units WHERE product_id=? AND ISNULL(is_active,1)=1 "
                "ORDER BY conversion_factor, unit_id", (product_id,))
    if not rows:
        rows = _all("SELECT unit_id, product_id, unit_name_en, conversion_factor, selling_price, "
                    "purchase_price, ISNULL(barcode,'') AS barcode, is_default FROM product_units "
                    "WHERE product_id=? AND ISNULL(is_active,1)=1 "
                    "ORDER BY conversion_factor, unit_id", (product_id,))
    return rows


def _default_unit(units):
    if not units:
        return None
    return next((u for u in units if u.get("is_default")), None) or \
        next((u for u in units if abs(float(u.get("conversion_factor") or 1) - 1) < 1e-9), None) or \
        units[0]


def _build(pid, unit_id, via, code, products=None):
    prod = None
    if products:
        prod = next((p for p in products if p.get("product_id") == pid), None)
    if prod is None:
        prod = _one("SELECT * FROM products WHERE product_id=?", (pid,))
    if not prod:
        return None
    units = units_of(pid)
    unit = next((u for u in units if u.get("unit_id") == unit_id), None) if unit_id else None
    if unit is None:
        unit_id = None
    use = unit or _default_unit(units)
    price = float((use or {}).get("selling_price") or 0) or float(prod.get("unit_price") or 0)
    return {"product_id": pid, "product": prod, "unit_id": unit_id, "unit": use,
            "unit_name": (use or {}).get("unit_name_en") or prod.get("unit_of_measure_en") or "",
            "factor": float((use or {}).get("conversion_factor") or 1),
            "price": price, "barcode": code, "via": via, "quantity": 1.0, "amount": None,
            "active": bool(prod.get("is_active", 1) if prod.get("is_active") is not None else 1)}


def resolve(code, scale=True, products=None):
    """Product + unit for a scanned / typed code, or None (see top)."""
    code = clean(code)
    if not code:
        return None
    r = _one("SELECT product_id, unit_id FROM product_units "
             "WHERE barcode=? AND ISNULL(is_active,1)=1", (code,))
    via = "unit"
    if not r:
        via = "extra"
        r = _one("SELECT product_id, unit_id FROM product_unit_barcodes "
                 "WHERE barcode=? AND ISNULL(is_active,1)=1", (code,)) or \
            _one("SELECT product_id, unit_id FROM product_unit_barcodes WHERE barcode=?", (code,))
    if not r:
        via = "product"
        r = _one("SELECT product_id FROM products WHERE barcode=?", (code,))
    if not r:
        via = "code"
        r = _one("SELECT product_id FROM products WHERE product_code=?", (code,))
        if not r and products:
            p = next((p for p in products
                      if str(p.get("product_code") or "").strip().lower() == code.lower()), None)
            r = {"product_id": p["product_id"]} if p else None
    if r:
        return _build(r["product_id"], r.get("unit_id"), via, code, products)
    if not scale:
        return None
    try:
        from modules.scale_barcode import decode
        s = decode(code)
    except Exception:
        s = None
    if not s:
        return None
    hit = _build(s["product"].get("product_id"), None, "scale", code, products)
    if hit:
        base = next((u for u in units_of(hit["product_id"])
                     if abs(float(u.get("conversion_factor") or 1) - 1) < 1e-9), None)
        if base:
            hit.update(unit=base, unit_name=base.get("unit_name_en") or hit["unit_name"], factor=1.0,
                       price=float(base.get("selling_price") or 0) or hit["price"])
        hit.update(quantity=float(s.get("quantity") or 1), amount=s.get("amount"),
                   scale=s, plu=s.get("plu"))
    return hit


def describe(hit):
    """'Milk 1L · Box ×12 · SAR 54.00' — for status lines and tool tips."""
    if not hit:
        return ""
    p = hit["product"]
    out = str(p.get("product_name_en") or "")
    if hit.get("unit_name"):
        out += " · " + hit["unit_name"]
        if hit.get("factor") and abs(hit["factor"] - 1) > 1e-9:
            out += " ×%g" % hit["factor"]
    if hit.get("via") == "scale":
        out += " · %g" % hit.get("quantity", 1)
    return out + " · %.2f" % float(hit.get("price") or 0)


# ── every product + every unit gets its own barcode ──────────────────
def missing_count(product_ids=None):
    """(products without a barcode, units without a barcode) — active only."""
    ids = list(product_ids or [])
    where, params = "", ()
    if ids:
        where = " AND product_id IN (%s)" % ",".join("?" * len(ids))
        params = tuple(ids)
    p = _one("SELECT COUNT(*) AS n FROM products WHERE ISNULL(is_active,1)=1 "
             "AND ISNULL(barcode,'')=''" + where, params)
    u = _one("SELECT COUNT(*) AS n FROM product_units WHERE ISNULL(is_active,1)=1 "
             "AND ISNULL(barcode,'')=''" + where, params)
    return int((p or {}).get("n") or 0), int((u or {}).get("n") or 0)


def ensure_barcodes(product_ids=None):
    """Fill every missing barcode. The product's main barcode and its base
    unit share ONE code (the code printed on a single piece); every other
    unit (Box, Carton…) gets its own. Codes follow Settings ▸ Barcode and
    are checked unused. Returns a list of (product_id, unit_name, code)."""
    from modules.barcode_gen import new_unique_barcode
    if product_ids:
        prods = []
        for pid in product_ids:
            r = _one("SELECT product_id, ISNULL(barcode,'') AS barcode FROM products "
                     "WHERE product_id=?", (pid,))
            if r:
                prods.append(r)
    else:
        prods = _all("SELECT product_id, ISNULL(barcode,'') AS barcode FROM products "
                     "WHERE ISNULL(is_active,1)=1 ORDER BY product_id")
    made, taken = [], []

    def fresh():
        code = new_unique_barcode(exclude=taken)
        taken.append(code)
        return code

    for p in prods:
        pid, pbc = p["product_id"], (p.get("barcode") or "").strip()
        units = units_of(pid)
        base = next((u for u in units
                     if abs(float(u.get("conversion_factor") or 1) - 1) < 1e-9), None)
        if base is not None and not (base.get("barcode") or "").strip():
            owner = None
            if pbc:
                from modules.product_lookup import barcode_owner
                owner = barcode_owner(pbc, exclude_product_id=pid)
            mine = any((u.get("barcode") or "").strip() == pbc for u in units)
            code = pbc if (pbc and not owner and not mine) else fresh()
            db.execute("UPDATE product_units SET barcode=? WHERE unit_id=?", (code, base["unit_id"]))
            base["barcode"] = code
            made.append((pid, base.get("unit_name_en") or "", code))
        if not pbc:
            code = (base or {}).get("barcode") or fresh()
            db.execute("UPDATE products SET barcode=? WHERE product_id=?", (code, pid))
            if base is None:
                made.append((pid, "", code))
        for u in units:
            if u is base or (u.get("barcode") or "").strip():
                continue
            code = fresh()
            db.execute("UPDATE product_units SET barcode=? WHERE unit_id=?", (code, u["unit_id"]))
            made.append((pid, u.get("unit_name_en") or "", code))
    return made


def _vat_rate(prod):
    r = _one("SELECT vat_rate FROM vat_categories WHERE vat_category_id=?",
             (prod.get("vat_category_id"),)) if prod.get("vat_category_id") else None
    if r and r.get("vat_rate") is not None:
        return float(r["vat_rate"])
    return float(prod.get("vat_rate") or 15)


def _prices(r, rate):
    """Shelf prices of one label row: with VAT, and the live offer (if any)."""
    from config import settings as cfg
    price = float(r.get("unit_price") or 0)
    incl = cfg.sales_price_includes_vat() if hasattr(cfg, "sales_price_includes_vat") else True
    with_vat = price if incl else price * (1 + rate / 100.0)
    r.update(vat_rate=rate, price_vat=round(with_vat + 1e-9, 2), offer_text="", offer_text_ar="",
             offer_price=None, old_price=None)
    try:
        from modules import offers as OF
        cands = OF.candidates(r["product_id"], r.get("unit_name"), "pos")
        if cands:
            o, it = cands[0]
            r["offer_text"], r["offer_text_ar"] = OF.label(o, it), OF.label_ar(o, it)
            top = OF.best(r["product_id"], r.get("unit_name"), 1, price, "pos", incl, rate)
            if top and top["discount"] > 0:
                net = price - top["discount"]
                r["offer_price"] = round((net if incl else net * (1 + rate / 100.0)) + 1e-9, 2)
                r["old_price"] = r["price_vat"]
    except Exception:
        pass
    return r


def label_rows(product_id):
    """One printable row per unit of a product (or one row for a product
    without units): everything a label field can show — the unit's own
    barcode and price, price with VAT, and a live offer."""
    prod = _one("SELECT p.*, c.category_name_en AS category_name FROM products p "
                "LEFT JOIN product_categories c ON c.category_id=p.category_id "
                "WHERE p.product_id=?", (product_id,)) or \
        _one("SELECT * FROM products WHERE product_id=?", (product_id,))
    if not prod:
        return []
    rate = _vat_rate(prod)
    units = units_of(product_id)
    if not units:
        r = dict(prod)
        r.update(unit_id=None, unit_name=prod.get("unit_of_measure_en") or "", unit_name_ar="",
                 factor=1.0, barcode_value=(prod.get("barcode") or "").strip())
        return [_prices(r, rate)]
    out = []
    for u in units:
        r = dict(prod)
        price = float(u.get("selling_price") or 0) or \
            float(prod.get("unit_price") or 0) * float(u.get("conversion_factor") or 1)
        r.update(unit_id=u["unit_id"], unit_name=u.get("unit_name_en") or "",
                 unit_name_ar=u.get("unit_name_ar") or "",
                 factor=float(u.get("conversion_factor") or 1), unit_price=price,
                 barcode_value=(u.get("barcode") or "").strip())
        if not r["barcode_value"] and abs(r["factor"] - 1) < 1e-9:
            r["barcode_value"] = (prod.get("barcode") or "").strip()
        out.append(_prices(r, rate))
    return out
