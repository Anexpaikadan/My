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
#   3b. its 5-digit system barcode   (products.system_barcode, v6.9.5) → base unit
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
    if not r:                                  # v6.9.5: the 5-digit system barcode = one piece
        via = "system"
        r = _one("SELECT product_id FROM products WHERE system_barcode=?", (code,))
        if r:
            base = next((u for u in units_of(r["product_id"])
                         if abs(float(u.get("conversion_factor") or 1) - 1) < 1e-9), None)
            r = {"product_id": r["product_id"], "unit_id": (base or {}).get("unit_id")}
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
    """(products without a barcode, units without a barcode) — active only.
    v6.9.5: a product's own barcode is its system barcode (a packet barcode
    typed by hand is extra, never required)."""
    from modules.barcode_gen import has_system_column
    ids = list(product_ids or [])
    where, params = "", ()
    if ids:
        where = " AND product_id IN (%s)" % ",".join("?" * len(ids))
        params = tuple(ids)
    col = "system_barcode" if has_system_column() else "barcode"
    p = _one("SELECT COUNT(*) AS n FROM products WHERE ISNULL(is_active,1)=1 "
             "AND ISNULL(%s,'')=''" % col + where, params)
    u = _one("SELECT COUNT(*) AS n FROM product_units WHERE ISNULL(is_active,1)=1 "
             "AND ISNULL(barcode,'')=''" + where, params)
    return int((p or {}).get("n") or 0), int((u or {}).get("n") or 0)


def ensure_system_barcodes(product_ids=None):
    """v6.9.5: every product (or the given ones) gets its 5-digit system
    barcode. Returns [(product_id, code)]."""
    from modules.barcode_gen import has_system_column, new_system_barcode
    if not has_system_column():
        return []
    if product_ids:
        rows = [r for r in (_one("SELECT product_id FROM products WHERE product_id=? "
                                 "AND ISNULL(system_barcode,'')=''", (pid,)) for pid in product_ids) if r]
    else:
        rows = _all("SELECT product_id FROM products WHERE ISNULL(system_barcode,'')='' "
                    "ORDER BY product_id")
    made, taken = [], []
    for r in rows:
        code = new_system_barcode(exclude=taken)
        taken.append(code)
        db.execute("UPDATE products SET system_barcode=? WHERE product_id=?", (code, r["product_id"]))
        made.append((r["product_id"], code))
    return made


def system_barcode(product_id):
    """The product's system barcode ('' before the v6.9.5 update)."""
    r = _one("SELECT ISNULL(system_barcode,'') AS s FROM products WHERE product_id=?", (product_id,))
    return str((r or {}).get("s") or "")


def ensure_barcodes(product_ids=None):
    """Fill every missing barcode. Every product gets its 5-digit system
    barcode (v6.9.5); its base unit scans with the packet barcode typed on
    the product, else with that system barcode; every other unit (Box,
    Carton…) gets its own. Codes follow Settings ▸ Barcode and are checked
    unused. Returns a list of (product_id, unit_name, code)."""
    from modules.barcode_gen import new_unique_barcode, has_system_column
    made_sys = dict(ensure_system_barcodes(product_ids))
    sys_on = has_system_column()
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
        sbc = system_barcode(pid) if sys_on else ""
        if pid in made_sys:
            made.append((pid, "", made_sys[pid]))
        units = units_of(pid)
        base = next((u for u in units
                     if abs(float(u.get("conversion_factor") or 1) - 1) < 1e-9), None)
        if base is not None and not (base.get("barcode") or "").strip():
            owner = None
            if pbc:
                from modules.product_lookup import barcode_owner
                owner = barcode_owner(pbc, exclude_product_id=pid)
            mine = any((u.get("barcode") or "").strip() == pbc for u in units)
            code = pbc if (pbc and not owner and not mine) else (sbc or fresh())
            db.execute("UPDATE product_units SET barcode=? WHERE unit_id=?", (code, base["unit_id"]))
            base["barcode"] = code
            made.append((pid, base.get("unit_name_en") or "", code))
        if not pbc and not sys_on:            # before v6.9.5 the product's own code lived here
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


LABEL_SOURCES = [("system", "System barcode (5-digit, made by DayBill)"),
                 ("manual", "Manual barcode (typed / from the packet)"),
                 ("manual_system", "Manual barcode, else the system barcode")]


def label_source():
    """Settings: which barcode a label prints (v6.9.5)."""
    try:
        from config import settings as cfg
        v = str(cfg.get("label_barcode_source", "system") or "system")
    except Exception:
        v = "system"
    return v if v in dict(LABEL_SOURCES) else "system"


def is_system_code(code):
    """A short number made by DayBill (5 / 6 digits), not a packet barcode."""
    c = str(code or "").strip()
    return c.isdigit() and len(c) < 8


def pick_barcode(row, source=None):
    """The barcode a label row prints for the chosen source."""
    src = source or label_source()
    man, sysc = row.get("manual_barcode") or "", row.get("system_barcode") or ""
    if src == "manual":
        return man
    if src == "manual_system":
        return man or sysc
    return sysc or man


def label_rows(product_id, source=None):
    """One printable row per unit of a product (or one row for a product
    without units): everything a label field can show — the unit's own
    barcode and price, price with VAT, and a live offer. v6.9.5: each row
    has its manual_barcode and system_barcode; barcode_value is the one
    the label prints (Settings / the label screen: system, manual, or
    manual else system)."""
    prod = _one("SELECT p.*, c.category_name_en AS category_name FROM products p "
                "LEFT JOIN product_categories c ON c.category_id=p.category_id "
                "WHERE p.product_id=?", (product_id,)) or \
        _one("SELECT * FROM products WHERE product_id=?", (product_id,))
    if not prod:
        return []
    rate = _vat_rate(prod)
    units = units_of(product_id)
    man0 = (prod.get("barcode") or "").strip()
    sys0 = str(prod.get("system_barcode") or "").strip()
    if not units:
        r = dict(prod)
        r.update(unit_id=None, unit_name=prod.get("unit_of_measure_en") or "", unit_name_ar="",
                 factor=1.0, manual_barcode=man0 if man0 != sys0 else "",
                 system_barcode=sys0 or (man0 if is_system_code(man0) else ""))
        r["barcode_value"] = pick_barcode(r, source)
        return [_prices(r, rate)]
    out = []
    for u in units:
        r = dict(prod)
        price = float(u.get("selling_price") or 0) or \
            float(prod.get("unit_price") or 0) * float(u.get("conversion_factor") or 1)
        ubc = (u.get("barcode") or "").strip()
        fac = float(u.get("conversion_factor") or 1)
        if abs(fac - 1) < 1e-9:              # the piece: the product's own two barcodes
            man = man0 or ("" if (ubc == sys0 or is_system_code(ubc)) else ubc)
            sysc = sys0 or (ubc if is_system_code(ubc) else "")
        else:                                # Box / Carton: the unit's own barcode
            man = "" if is_system_code(ubc) else ubc
            sysc = ubc if is_system_code(ubc) else ""
        r.update(unit_id=u["unit_id"], unit_name=u.get("unit_name_en") or "",
                 unit_name_ar=u.get("unit_name_ar") or "",
                 factor=fac, unit_price=price, manual_barcode=man, system_barcode=sysc)
        src = source or label_source()
        r["barcode_value"] = pick_barcode(r, src) or ("" if src == "manual" else ubc)
        out.append(_prices(r, rate))
    return out
