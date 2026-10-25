# ============================================================
# DayBill ERP - Textiles & Garments: size / colour variants (v7.0)
# ------------------------------------------------------------
# A STYLE is a normal product (e.g. "Polo Shirt"). Its VARIANTS are
# normal products too — "Polo Shirt - M - Red" — each with its own
# product code, 5-digit system barcode, units, price and stock, so
# sales, purchases, POS, stock and reports work for them as for any
# product. Only three columns link a variant to its style.
#
# Columns (database/patches/zzz_v700_textiles_patch.sql):
#   products.variant_parent_id   the style's product_id
#   products.variant_size        size   ('' when the style has no sizes)
#   products.variant_colour      colour ('' when the style has no colours)
#
#   ready()                       True once the update added the columns
#   on()                          textiles module on + ready
#   sizes() / colours()           the shop's lists (Settings, editable)
#   save_list(kind, values)       keep the size / colour list (company db)
#   size_key(s) / colour_key(c)   sort in the shop's order (XS S M … 28 30)
#   variant_name(name, s, c)      "Polo Shirt - M - Red"
#   style_of(product_id)          the style of a variant (or the product)
#   styles(search, category_id)   styles that have variants (+ counts)
#   variants(style_id)            the variants of a style, in size order
#   plan(style_id, sizes, colours)  what Create would make (new / made)
#   create(style_id, items)       make the variants (one transaction)
#   set_price(style_id, price, size=, colour=, product_ids=)
#   matrix(style_id)              size × colour → variant row
#   stock_matrix(style_ids=, category_id=, value_at=)
#                                 stock + value per size × colour
#   cost(row)                     average cost, else purchase price
#   unit_choices(base)            unit list for the product form
#                                 (+ Metre, Yard: cloth sold by length)
# ============================================================

import re

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

DEFAULT_SIZES = "XS,S,M,L,XL,XXL"
DEFAULT_COLOURS = "White,Black,Blue,Red,Green,Grey"
LENGTH_UNITS = ("Metre", "Yard")          # cloth sold by length (2.75 m)
MAX_PART = 40                              # NVARCHAR(40) columns

# product columns a variant never copies from its style
_NO_COPY = {"product_id", "product_code", "product_name_en", "product_name_ar", "barcode",
            "system_barcode", "stock_quantity", "created_at", "updated_at", "scale_plu",
            "is_favorite", "fav_order", "default_unit_id", "variant_parent_id",
            "variant_size", "variant_colour", "unit_price", "is_active", "list_in_sales",
            "list_in_purchase"}
# unit columns never copied
_NO_COPY_UNIT = {"unit_id", "product_id", "barcode", "created_at"}

# Arabic names of common colours (the Arabic product name of a variant)
COLOUR_AR = {
    "white": "أبيض", "black": "أسود", "blue": "أزرق", "red": "أحمر", "green": "أخضر",
    "grey": "رمادي", "gray": "رمادي", "yellow": "أصفر", "brown": "بني", "pink": "وردي",
    "orange": "برتقالي", "purple": "بنفسجي", "navy": "كحلي", "beige": "بيج",
    "maroon": "عنابي", "cream": "كريمي", "gold": "ذهبي", "silver": "فضي",
    "off white": "أوف وايت", "sky blue": "سماوي", "dark blue": "أزرق غامق",
    "light blue": "أزرق فاتح", "olive": "زيتي", "khaki": "كاكي",
}

_CACHE = {"ready": False, "cols": {}}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    """True once the v7.0 textiles update added the variant columns."""
    if _CACHE["ready"]:
        return True
    try:
        ok = db.execute_scalar("SELECT COL_LENGTH('products','variant_parent_id')") is not None
    except Exception:
        ok = False
    if ok:
        _CACHE["ready"] = True
    return ok


def on():
    """The company uses the Textiles module (and the update is in)."""
    try:
        from modules import business
        return business.has("textiles") and ready()
    except Exception:
        return False


# ── the size and colour lists ─────────────────────────────────
def split_list(text):
    """'XS, S,M;L' → ['XS', 'S', 'M', 'L'] (trimmed, no repeats)."""
    out, seen = [], set()
    if isinstance(text, (list, tuple)):
        text = ",".join(str(x) for x in text)
    for part in re.split(r"[,;\n]+", str(text or "")):
        p = " ".join(part.split())[:MAX_PART]
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def _setting(key, default):
    v = None
    try:
        from modules import country
        v = country.option(key)          # kept in the company database
    except Exception:
        v = None
    if v in (None, ""):
        try:
            from config import settings as cfg
            v = cfg.get(key)
        except Exception:
            v = None
    return default if v in (None, "") else v


def sizes():
    return split_list(_setting("textile_sizes", DEFAULT_SIZES)) or split_list(DEFAULT_SIZES)


def colours():
    return split_list(_setting("textile_colours", DEFAULT_COLOURS)) or split_list(DEFAULT_COLOURS)


def save_list(kind, values):
    """Keep the size (kind 'sizes') or colour list in the company database
    and use it at once. Returns the saved list."""
    key = "textile_sizes" if kind == "sizes" else "textile_colours"
    items = split_list(values)
    if not items:
        raise ValueError("Type at least one %s." % ("size" if kind == "sizes" else "colour"))
    text = ",".join(items)
    try:
        from modules import country
        country.set_option(key, text)
    except Exception:
        pass
    try:
        from config import settings as cfg
        cfg.set_company(key, text)
    except Exception:
        pass
    return items


def _num(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None


def size_key(s, order=None):
    """Sizes in the shop's order (XS, S, M …), then numbers (28, 30 …),
    then the rest A-Z. No size ('') comes first."""
    s = str(s or "")
    if not s:
        return (0, 0, 0.0, "")
    order = order if order is not None else [x.lower() for x in sizes()]
    low = s.lower()
    if low in order:
        return (1, order.index(low), 0.0, "")
    n = _num(s)
    if n is not None:
        return (2, 0, n, "")
    return (3, 0, 0.0, low)


def colour_key(c, order=None):
    c = str(c or "")
    if not c:
        return (0, 0, "")
    order = order if order is not None else [x.lower() for x in colours()]
    low = c.lower()
    if low in order:
        return (1, order.index(low), "")
    return (2, 0, low)


def sort_sizes(values):
    order = [x.lower() for x in sizes()]
    return sorted(values, key=lambda s: size_key(s, order))


def sort_colours(values):
    order = [x.lower() for x in colours()]
    return sorted(values, key=lambda c: colour_key(c, order))


def colour_ar(c):
    return COLOUR_AR.get(str(c or "").strip().lower(), str(c or ""))


def variant_name(name, size="", colour="", limit=200):
    """'Polo Shirt - M - Red' (a part left out when it is empty)."""
    tail = " - ".join(p for p in (str(size or "").strip(), str(colour or "").strip()) if p)
    base = str(name or "").strip()
    if not tail:
        return base[:limit]
    room = max(1, limit - len(tail) - 3)
    return "%s - %s" % (base[:room].rstrip(), tail)


def variant_name_ar(name_ar, name_en, size="", colour=""):
    """Arabic name of a variant: the style's Arabic name + size + colour
    in Arabic; without an Arabic name the English one is spelt in Arabic."""
    ar = str(name_ar or "").strip()
    if ar and ar != str(name_en or "").strip():
        return variant_name(ar, size, colour_ar(colour))
    en = variant_name(name_en, size, colour)
    try:
        from modules.arabic_translit import transliterate
        t = (transliterate(en) or "").strip()
        if t:
            return t[:200]
    except Exception:
        pass
    return en


def cost(row):
    """Cost of one base unit: average cost, else purchase price, else the
    last purchase cost (the same rule as the Report Center)."""
    for k in ("average_cost", "purchase_price", "last_purchase_cost"):
        if _f((row or {}).get(k)) > 0:
            return _f(row.get(k))
    return 0.0


# ── reading ───────────────────────────────────────────────────
def _columns(table):
    if table not in _CACHE["cols"]:
        rows = db.fetchall("SELECT name FROM sys.columns WHERE object_id=OBJECT_ID(?) "
                           "AND is_identity=0 AND is_computed=0 ORDER BY column_id", (table,)) or []
        _CACHE["cols"][table] = [r["name"] for r in rows]
    return _CACHE["cols"][table]


def _product(pid):
    return db.fetchone("SELECT * FROM products WHERE product_id=?", (int(pid),))


def style_of(product_id):
    """The style a product belongs to: its parent when it is a variant (and
    the parent still exists), else the product itself. None if unknown."""
    if not product_id or not ready():
        return None
    r = db.fetchone("SELECT p.product_id, p.variant_parent_id, s.product_id AS sid "
                    "FROM products p LEFT JOIN products s ON s.product_id=p.variant_parent_id "
                    "WHERE p.product_id=?", (int(product_id),))
    if not r:
        return None
    return int(r["sid"]) if r.get("sid") else int(r["product_id"])


def is_variant(product_id):
    if not product_id or not ready():
        return False
    return bool(db.execute_scalar("SELECT COUNT(*) FROM products p JOIN products s "
                                  "ON s.product_id=p.variant_parent_id WHERE p.product_id=?",
                                  (int(product_id),)))


def styles(search="", category_id=None, active_only=True):
    """Styles that have variants: product_id, product_code, product_name_en,
    category, unit_price, variants (count), stock (sum of the variants)."""
    if not ready():
        return []
    sql = ("SELECT s.product_id, s.product_code, s.product_name_en, s.product_name_ar, "
           "s.category_id, ISNULL(pc.category_name_en,'') AS category, s.unit_price, "
           "COUNT(v.product_id) AS variants, SUM(ISNULL(v.stock_quantity,0)) AS stock "
           "FROM products s JOIN products v ON v.variant_parent_id=s.product_id "
           "LEFT JOIN product_categories pc ON pc.category_id=s.category_id WHERE 1=1")
    params = []
    if active_only:
        sql += " AND ISNULL(v.is_active,1)=1"
    if category_id:
        sql += " AND s.category_id=?"
        params.append(int(category_id))
    if search:
        sql += " AND (s.product_name_en LIKE ? OR s.product_code LIKE ? OR s.product_name_ar LIKE ?)"
        params += ["%" + search + "%"] * 3
    sql += (" GROUP BY s.product_id, s.product_code, s.product_name_en, s.product_name_ar, "
            "s.category_id, pc.category_name_en, s.unit_price ORDER BY s.product_name_en")
    return db.fetchall(sql, tuple(params)) or []


def variants(style_id, active_only=True):
    """The variants of a style (full product rows + size, colour, stock,
    cost), sorted by size then colour."""
    if not style_id or not ready():
        return []
    sql = ("SELECT p.*, ISNULL(p.variant_size,'') AS size, ISNULL(p.variant_colour,'') AS colour, "
           "ISNULL(p.stock_quantity,0) AS stock FROM products p WHERE p.variant_parent_id=?")
    if active_only:
        sql += " AND ISNULL(p.is_active,1)=1"
    rows = [dict(r) for r in (db.fetchall(sql, (int(style_id),)) or [])]
    so = [x.lower() for x in sizes()]
    co = [x.lower() for x in colours()]
    for r in rows:
        r["system_barcode"] = str(r.get("system_barcode") or "")      # '' before v6.9.5
        r["stock"] = _f(r.get("stock"))
        r["cost"] = cost(r)
    rows.sort(key=lambda r: (size_key(r["size"], so), colour_key(r["colour"], co)))
    return rows


def matrix(style_id, active_only=True):
    """{"sizes": [...], "colours": [...], "cells": {(size, colour): row}}."""
    rows = variants(style_id, active_only=active_only)
    cells = {(r["size"], r["colour"]): r for r in rows}
    return {"sizes": sort_sizes({r["size"] for r in rows}),
            "colours": sort_colours({r["colour"] for r in rows}), "cells": cells}


def default_price(style, existing, size):
    """Price for a NEW variant: what this size already sells for, else the
    price most variants have, else the style's price."""
    same = [_f(r.get("unit_price")) for r in existing
            if r["size"].lower() == str(size or "").lower() and _f(r.get("unit_price")) > 0]
    if same:
        return max(set(same), key=same.count)
    allp = [_f(r.get("unit_price")) for r in existing if _f(r.get("unit_price")) > 0]
    if allp:
        return max(set(allp), key=allp.count)
    return _f((style or {}).get("unit_price"))


def plan(style_id, sizes_=(), colours_=()):
    """Every ticked size × colour (one list may be empty):
    [{size, colour, name, price, status ('new' | 'made' | 'inactive'),
      product_id}] in size order."""
    sizes_ = [s for s in split_list(list(sizes_ or []))]
    colours_ = [c for c in split_list(list(colours_ or []))]
    if not style_id or not (sizes_ or colours_):
        return []
    style = _product(style_id)
    if not style:
        return []
    existing = variants(style_id, active_only=False)
    have = {(r["size"].lower(), r["colour"].lower()): r for r in existing}
    out = []
    for s in sort_sizes(sizes_ or [""]):
        for c in sort_colours(colours_ or [""]):
            old = have.get((s.lower(), c.lower()))
            status = "new" if old is None else ("made" if old.get("is_active") in (1, True, None)
                                                else "inactive")
            out.append({"size": s, "colour": c,
                        "name": variant_name(style["product_name_en"], s, c),
                        "price": round(_f(old["unit_price"]) if old else
                                       default_price(style, existing, s), 2),
                        "status": status,
                        "product_id": old["product_id"] if old else None})
    return out


# ── making variants ───────────────────────────────────────────
def _unit_rows(pid):
    try:
        return db.fetchall("SELECT * FROM product_units WHERE product_id=? AND ISNULL(is_active,1)=1 "
                           "ORDER BY conversion_factor, unit_id", (int(pid),)) or []
    except Exception:
        return []


def _insert(table, data):
    cols = list(data.keys())
    db.execute("INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(cols), ", ".join("?" * len(cols))),
               tuple(data[c] for c in cols))


def _unit_price_for(unit, old_base, new_base):
    """A unit's selling price after the piece price changes from old_base
    to new_base (a Box keeps the same mark-up over its pieces)."""
    factor = _f(unit.get("conversion_factor")) or 1.0
    if abs(factor - 1) < 1e-9:
        return round(new_base, 2)
    sp = _f(unit.get("selling_price"))
    if sp > 0 and old_base > 0:
        return round(sp * new_base / old_base, 2)
    return round(new_base * factor, 2)


def _make_variant(style, size, colour, price):
    """Insert one variant product + its units; returns its product_id."""
    from modules.product_lookup import next_product_code
    pcols = _columns("products")
    data = {c: style.get(c) for c in pcols if c not in _NO_COPY and c in style}
    code = next_product_code()
    name = variant_name(style.get("product_name_en"), size, colour)
    data.update(product_code=code, product_name_en=name,
                product_name_ar=variant_name_ar(style.get("product_name_ar"),
                                                style.get("product_name_en"), size, colour),
                unit_price=round(_f(price), 2), variant_parent_id=int(style["product_id"]),
                variant_size=size or "", variant_colour=colour or "")
    for k, v in (("stock_quantity", 0), ("is_active", 1), ("list_in_sales", 1),
                 ("list_in_purchase", 1), ("barcode", None)):
        if k in pcols:
            data[k] = v
    data = {k: v for k, v in data.items() if k in pcols}
    _insert("products", data)
    pid = db.execute_scalar("SELECT product_id FROM products WHERE product_code=?", (code,))
    pid = int(pid)
    # units: the style's units (PCs, Box …) with their prices; barcodes are
    # made below by the app's normal rule (each one unique)
    ucols = _columns("product_units")
    old_base = _f(style.get("unit_price"))
    units = _unit_rows(style["product_id"])
    new_ids = {}
    if not units:
        units = [{"unit_name_en": style.get("unit_of_measure_en") or "PCs",
                  "unit_name_ar": style.get("unit_of_measure_ar"), "conversion_factor": 1,
                  "purchase_price": _f(style.get("purchase_price")),
                  "selling_price": _f(price), "is_default": 1, "is_purchase_unit": 1,
                  "is_sales_unit": 1, "is_active": 1, "is_default_purchase": 1}]
    for u in units:
        ud = {c: u.get(c) for c in ucols if c not in _NO_COPY_UNIT and c in u}
        ud.update(product_id=pid, selling_price=_unit_price_for(u, old_base, _f(price)))
        if "is_active" in ucols:
            ud["is_active"] = 1
        ud = {k: v for k, v in ud.items() if k in ucols}
        _insert("product_units", ud)
        nid = db.execute_scalar("SELECT MAX(unit_id) FROM product_units WHERE product_id=? "
                                "AND unit_name_en=?", (pid, ud.get("unit_name_en")))
        if u.get("unit_id"):
            new_ids[u["unit_id"]] = nid
    if style.get("default_unit_id") in new_ids and "default_unit_id" in pcols:
        db.execute("UPDATE products SET default_unit_id=? WHERE product_id=?",
                   (new_ids[style["default_unit_id"]], pid))
    from modules import barcode_resolver as BR
    BR.ensure_barcodes([pid])          # 5-digit system barcode + every unit's own
    return pid


def create(style_id, items):
    """Make the variants of a style. items: [{size, colour, price}].
    A size / colour already made is skipped (never a second one); one made
    before and switched off is switched on again. All in one transaction.
    Returns {"made": [ids], "again": [ids], "skipped": n}."""
    if not ready():
        raise RuntimeError("Please update the database first (Textiles update not applied).")
    style = _product(style_id)
    if not style:
        raise ValueError("The style was not found.")
    if style.get("variant_parent_id") and style_of(style_id) != int(style_id):
        raise ValueError("%s is itself a size / colour of another style. "
                         "Pick the main style." % style.get("product_name_en"))
    existing = {(r["size"].lower(), r["colour"].lower()): r
                for r in variants(style_id, active_only=False)}
    made, again, skipped, seen = [], [], 0, set()
    with db.transaction():
        for it in items or []:
            s = " ".join(str(it.get("size") or "").split())[:MAX_PART]
            c = " ".join(str(it.get("colour") or "").split())[:MAX_PART]
            if not (s or c) or (s.lower(), c.lower()) in seen:
                continue
            seen.add((s.lower(), c.lower()))
            price = it.get("price")
            price = _f(style.get("unit_price")) if price in (None, "") else _f(price)
            if price < 0:
                raise ValueError("Price cannot be below 0 (%s)." % variant_name("", s, c).strip(" -"))
            old = existing.get((s.lower(), c.lower()))
            if old is not None:
                if old.get("is_active") in (0, False):
                    db.execute("UPDATE products SET is_active=1, list_in_sales=1, list_in_purchase=1, "
                               "updated_at=GETDATE() WHERE product_id=?", (old["product_id"],))
                    again.append(int(old["product_id"]))
                else:
                    skipped += 1
                continue
            made.append(_make_variant(style, s, c, price))
    _after_change(made, new_product=True)
    return {"made": made, "again": again, "skipped": skipped}


def hide_style(style_id, hide=True):
    """Sell only the sizes / colours: the style itself leaves (or comes
    back to) the sales and purchase product lists."""
    v = 0 if hide else 1
    db.execute("UPDATE products SET list_in_sales=?, list_in_purchase=?, updated_at=GETDATE() "
               "WHERE product_id=?", (v, v, int(style_id)))


def _after_change(pids, new_product=False, before=None):
    try:
        from modules import product_info
        product_info.invalidate()
    except Exception:
        pass
    if not pids:
        return
    try:
        from modules import price_watch as PW
        b = before if before is not None else ({} if new_product else PW.snapshot(pids))
        b[("_ids",)] = list(pids)
        PW.record(b, "textiles", new_product=new_product)
    except Exception:
        pass


def set_price(style_id, price, size=None, colour=None, product_ids=None):
    """New selling price for the variants of a style: all of them, one size
    (size=), one colour (colour=) or the chosen products (product_ids=).
    Box / carton prices keep their mark-up. Returns how many changed."""
    price = _f(price)
    if price <= 0:
        raise ValueError("Type a price more than 0.")
    rows = variants(style_id, active_only=False)
    if product_ids:
        want = {int(p) for p in product_ids}
        rows = [r for r in rows if int(r["product_id"]) in want]
    if size is not None:
        rows = [r for r in rows if r["size"].lower() == str(size).lower()]
    if colour is not None:
        rows = [r for r in rows if r["colour"].lower() == str(colour).lower()]
    ids = [int(r["product_id"]) for r in rows]
    if not ids:
        return 0
    try:
        from modules import price_watch as PW
        before = PW.snapshot(ids)
    except Exception:
        before = None
    with db.transaction():
        for r in rows:
            old = _f(r.get("unit_price"))
            db.execute("UPDATE products SET unit_price=?, updated_at=GETDATE() WHERE product_id=?",
                       (round(price, 2), r["product_id"]))
            for u in _unit_rows(r["product_id"]):
                db.execute("UPDATE product_units SET selling_price=? WHERE unit_id=?",
                           (_unit_price_for(u, old, price), u["unit_id"]))
    if before is not None:
        _after_change(ids, before=before)
    else:
        _after_change([], new_product=False)
    return len(ids)


# ── stock by size and colour ──────────────────────────────────
def stock_matrix(style_ids=None, category_id=None, value_at="cost", search=""):
    """Stock of the variants as a matrix: colours (rows, per style) ×
    sizes (columns). value_at: 'cost' or 'price'. Returns
    {"sizes": [...], "rows": [{style_id, style, code, colour, cells
     {size: qty}, total, value}], "col_totals": {size: qty}, "total",
     "value", "styles", "variants"}."""
    out = {"sizes": [], "rows": [], "col_totals": {}, "total": 0.0, "value": 0.0,
           "styles": 0, "variants": 0}
    if not ready():
        return out
    sql = ("SELECT v.*, ISNULL(v.variant_size,'') AS size, ISNULL(v.variant_colour,'') AS colour, "
           "s.product_code AS style_code, s.product_name_en AS style_name "
           "FROM products v JOIN products s ON s.product_id=v.variant_parent_id "
           "WHERE ISNULL(v.is_active,1)=1")
    params = []
    if style_ids:
        ids = [int(x) for x in style_ids]
        sql += " AND s.product_id IN (%s)" % ",".join("?" * len(ids))
        params += ids
    if category_id:
        sql += " AND s.category_id=?"
        params.append(int(category_id))
    if search:
        sql += " AND (s.product_name_en LIKE ? OR s.product_code LIKE ?)"
        params += ["%" + search + "%"] * 2
    rows = db.fetchall(sql, tuple(params)) or []
    so = [x.lower() for x in sizes()]
    co = [x.lower() for x in colours()]
    by = {}
    size_set = set()
    for r in rows:
        k = (r["variant_parent_id"], r["colour"])
        e = by.setdefault(k, {"style_id": r["variant_parent_id"], "style": r["style_name"] or "",
                              "code": r["style_code"] or "", "colour": r["colour"], "cells": {},
                              "total": 0.0, "value": 0.0})
        q = _f(r.get("stock_quantity"))
        e["cells"][r["size"]] = round(e["cells"].get(r["size"], 0.0) + q, 3)
        e["total"] += q
        unit_val = cost(r) if value_at == "cost" else _f(r.get("unit_price"))
        e["value"] += q * unit_val
        size_set.add(r["size"])
    out["sizes"] = sorted(size_set, key=lambda s: size_key(s, so))
    out["rows"] = sorted(by.values(), key=lambda e: (e["style"].lower(), e["style_id"],
                                                     colour_key(e["colour"], co)))
    for e in out["rows"]:
        e["total"] = round(e["total"], 3)
        e["value"] = round(e["value"], 2)
        for s, q in e["cells"].items():
            out["col_totals"][s] = round(out["col_totals"].get(s, 0.0) + q, 3)
    out["total"] = round(sum(e["total"] for e in out["rows"]), 3)
    out["value"] = round(sum(e["value"] for e in out["rows"]), 2)
    out["styles"] = len({e["style_id"] for e in out["rows"]})
    out["variants"] = len(rows)
    return out


# ── product form: cloth sold by length ────────────────────────
def unit_choices(base):
    """The product form's unit list with Metre and Yard (textiles shops)."""
    base = list(base or [])
    if not on():
        return base
    have = {str(u).lower() for u in base}
    add = [u for u in LENGTH_UNITS if u.lower() not in have]
    return base[:1] + add + base[1:]
