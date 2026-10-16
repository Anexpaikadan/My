# ============================================================
# DayBill ERP - shared product lookup
# ------------------------------------------------------------
# One place that answers:
#   • barcode_owner()   – who already owns this barcode? (product
#                         barcode, unit barcode, or extra/multi barcode)
#   • search_products() – find products by code, English/Arabic name,
#                         alias, or ANY of their barcodes
# Used by the Product list, the Product form search bar, the Multi
# Barcode box and the Units manager so they all agree.
# ============================================================
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _q(sql, params=()):
    try:
        return db.fetchall(sql, params) or []
    except Exception:
        return []


def barcode_owner(bc, exclude_product_id=None, exclude_unit_id=None):
    """{product_id, product_name, unit_name, unit_id, where} or None.
    exclude_product_id: ignore matches on this product (editing it).
    exclude_unit_id: ignore matches on this unit (re-saving it)."""
    bc = (bc or "").strip()
    if not bc:
        return None

    def mine(pid, uid=None):
        if exclude_unit_id is not None and uid == exclude_unit_id:
            return True
        return exclude_product_id is not None and pid == exclude_product_id

    for r in _q("SELECT pub.product_id, pub.unit_id, p.product_name_en, pu.unit_name_en "
                "FROM product_unit_barcodes pub "
                "JOIN products p ON p.product_id=pub.product_id "
                "LEFT JOIN product_units pu ON pu.unit_id=pub.unit_id "
                "WHERE pub.barcode=?", (bc,)):
        if not mine(r["product_id"], r.get("unit_id")):
            return {"product_id": r["product_id"], "product_name": r["product_name_en"],
                    "unit_name": r.get("unit_name_en") or "", "unit_id": r.get("unit_id"),
                    "where": "extra barcode"}
    for r in _q("SELECT pu.product_id, pu.unit_id, p.product_name_en, pu.unit_name_en "
                "FROM product_units pu JOIN products p ON p.product_id=pu.product_id "
                "WHERE pu.barcode=? AND ISNULL(pu.is_active,1)=1", (bc,)):
        if not mine(r["product_id"], r.get("unit_id")):
            return {"product_id": r["product_id"], "product_name": r["product_name_en"],
                    "unit_name": r.get("unit_name_en") or "", "unit_id": r.get("unit_id"),
                    "where": "unit barcode"}
    for r in _q("SELECT product_id, product_name_en FROM products WHERE barcode=?", (bc,)):
        if not mine(r["product_id"]):
            return {"product_id": r["product_id"], "product_name": r["product_name_en"],
                    "unit_name": "base", "unit_id": None, "where": "product barcode"}
    return None


def barcode_product_ids(text, exact=False):
    """product_id → matched barcode, for unit + extra barcodes."""
    text = (text or "").strip()
    if not text:
        return {}
    op, val = ("=", text) if exact else ("LIKE", "%" + text + "%")
    out = {}
    for r in _q(f"SELECT product_id, barcode FROM product_units WHERE barcode {op} ? "
                f"AND ISNULL(is_active,1)=1", (val,)):
        out.setdefault(r["product_id"], r["barcode"])
    for r in _q(f"SELECT product_id, barcode FROM product_unit_barcodes WHERE barcode {op} ?",
                (val,)):
        out.setdefault(r["product_id"], r["barcode"])
    return out


def search_products(text, limit=20, active_only=False):
    """Products matching code / name / Arabic / alias / any barcode.
    An exact barcode or code match is always listed first."""
    text = (text or "").strip()
    if not text:
        return []
    like = "%" + text + "%"
    act = " AND ISNULL(p.is_active,1)=1" if active_only else ""
    has_alias = bool(_q("SELECT name FROM sys.columns WHERE object_id=OBJECT_ID('products') "
                        "AND name='alias_name'"))
    alias = "OR p.alias_name LIKE ? " if has_alias else ""
    params = [like, like, like, like] + ([like] if has_alias else [])
    rows = _q(f"SELECT TOP {int(limit) * 2} p.product_id, p.product_code, p.product_name_en, "
              f"ISNULL(p.product_name_ar,'') AS product_name_ar, ISNULL(p.barcode,'') AS barcode, "
              f"p.unit_price, p.stock_quantity, p.is_active FROM products p "
              f"WHERE (p.product_code LIKE ? OR p.product_name_en LIKE ? OR "
              f"p.product_name_ar LIKE ? OR p.barcode LIKE ? {alias}){act} "
              f"ORDER BY p.product_name_en", tuple(params))
    seen = {r["product_id"] for r in rows}
    via = barcode_product_ids(text)
    extra_ids = [pid for pid in via if pid not in seen]
    if extra_ids:
        ph = ",".join("?" * len(extra_ids[:200]))
        rows += _q(f"SELECT p.product_id, p.product_code, p.product_name_en, "
                   f"ISNULL(p.product_name_ar,'') AS product_name_ar, ISNULL(p.barcode,'') AS barcode, "
                   f"p.unit_price, p.stock_quantity, p.is_active FROM products p "
                   f"WHERE p.product_id IN ({ph}){act}", tuple(extra_ids[:200]))
    for r in rows:
        if r["product_id"] in via and not r.get("matched_barcode"):
            r["matched_barcode"] = via[r["product_id"]]
    t = text.lower()

    def rank(r):
        exact = (str(r.get("product_code", "")).lower() == t or
                 str(r.get("barcode", "")).lower() == t or
                 str(r.get("matched_barcode", "")).lower() == t)
        starts = str(r.get("product_name_en", "")).lower().startswith(t)
        return (0 if exact else 1 if starts else 2, str(r.get("product_name_en", "")).lower())
    rows.sort(key=rank)
    return rows[:limit]


# ── Product codes: always unique, in any format ────────────────────
def norm_code(code):
    """'p001 ', 'P001' and 'P1' are the same code; '0012' and '12' too."""
    import re
    c = str(code or "").strip().upper()
    c = re.sub(r"\s+", "", c)
    # a number part loses its leading zeros: P0012 → P12, 0012 → 12
    m = re.match(r"^(\D*)0*(\d+)$", c)
    if m:
        c = m.group(1) + str(int(m.group(2)))
    return c


def code_owner(code, exclude_product_id=None):
    """Who already uses this product code — as another product's code (in
    any format) or as anyone's barcode? {product_id, product_name, as} or None."""
    n = norm_code(code)
    if not n:
        return None
    for r in _q("SELECT product_id, product_code, product_name_en FROM products"):
        if r["product_id"] != exclude_product_id and norm_code(r.get("product_code")) == n:
            return {"product_id": r["product_id"], "product_name": r["product_name_en"],
                    "as": "product code %s" % r.get("product_code")}
    o = barcode_owner(str(code).strip(), exclude_product_id=exclude_product_id)
    if o:
        return {"product_id": o["product_id"], "product_name": o["product_name"],
                "as": "barcode (%s)" % (o.get("unit_name") or "")}
    return None


def code_max_len():
    """Settings ▸ Inventory ▸ Product code maximum length (default 8;
    0 = no limit)."""
    try:
        from config import settings as cfg
        n = int(float(str(cfg.get("product_code_max_len", 8) or 0)))
        return max(0, min(50, n))
    except Exception:
        return 8


def next_product_code(max_len=None):
    """The last created product's code + 1 (P0012 → P0013, 1005 → 1006),
    skipping any code already used in any format. New shop → 1001.
    Never longer than the product code maximum length (default 8)."""
    import re
    if max_len is None:
        max_len = code_max_len()
    rows = _q("SELECT product_id, product_code FROM products ORDER BY product_id DESC")
    taken = {norm_code(r.get("product_code")) for r in rows}
    base = None
    for r in rows:                         # newest product whose code ends in a number
        c = str(r.get("product_code") or "").strip()
        if re.search(r"\d+$", c) and (not max_len or len(c) <= max_len):
            base = c
            break
    if base is None:
        nums = [int(norm_code(r.get("product_code"))) for r in rows
                if norm_code(r.get("product_code")).isdigit()
                and (not max_len or len(norm_code(r.get("product_code"))) <= max_len)]
        base = str(max(nums)) if nums else "1000"
    m = re.match(r"^(.*?)(\d+)$", base)
    pre, num, width = m.group(1), int(m.group(2)), len(m.group(2))
    for _ in range(100000):
        num += 1
        cand = pre + str(num).zfill(width)
        if max_len and len(cand) > max_len:
            break                          # P9999999 → no room: plain numbers below
        if norm_code(cand) not in taken and not barcode_owner(cand):
            return cand
    num = 1000
    for _ in range(100000):
        num += 1
        cand = str(num)
        if max_len and len(cand) > max_len:
            break
        if norm_code(cand) not in taken and not barcode_owner(cand):
            return cand
    return pre + str(num + 1)
