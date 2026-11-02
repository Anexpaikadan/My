# ============================================================
# DayBill ERP - Selling-price change log (shelf labels)
# ------------------------------------------------------------
#   before = price_watch.snapshot([product_id, ...])
#   ... save the product / units / bulk rates ...
#   price_watch.record(before, "product")      -> rows logged
# A product with units is watched per unit (PCs, Box …: each has its
# own barcode + price on the shelf); a product without units is
# watched on products.unit_price.
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _f(v):
    try:
        return round(float(v), 4)
    except Exception:
        return None


def ready():
    try:
        db.execute_scalar("SELECT COUNT(*) FROM price_change_log WHERE 1=0")
        return True
    except Exception:
        return False


def snapshot(product_ids):
    """{(pid, unit_id or 0): {price, unit, barcode}} for these products."""
    out = {}
    ids = [int(p) for p in (product_ids or []) if p]
    for pid in ids:
        try:
            units = db.fetchall(
                "SELECT unit_id, unit_name_en, selling_price, barcode FROM product_units "
                "WHERE product_id=? AND is_active=1", (pid,)) or []
        except Exception:
            units = []
        if units:
            for u in units:
                out[(pid, u["unit_id"])] = {"price": _f(u.get("selling_price")),
                                            "unit": u.get("unit_name_en") or "",
                                            "barcode": u.get("barcode") or ""}
        else:
            try:
                p = db.fetchone("SELECT unit_price, unit_of_measure_en, barcode "
                                "FROM products WHERE product_id=?", (pid,))
            except Exception:
                p = None
            if p:
                out[(pid, 0)] = {"price": _f(p.get("unit_price")),
                                 "unit": p.get("unit_of_measure_en") or "",
                                 "barcode": p.get("barcode") or ""}
    out[("_ids",)] = ids
    return out


def _user():
    try:
        from modules import permissions as _p
        return (_p.session_user() or {}).get("user_id")
    except Exception:
        return None


def log_change(pid, unit_id, unit_name, barcode, old, new, source="edit"):
    if new is None or not ready():
        return False
    try:
        db.execute("INSERT INTO price_change_log (product_id, unit_id, unit_name, barcode, "
                   "old_price, new_price, source, changed_by) VALUES (?,?,?,?,?,?,?,?)",
                   (pid, unit_id or None, unit_name, barcode, old, new, source, _user()))
        return True
    except Exception:
        return False


def record(before, source="edit", new_product=False):
    """Compare with the prices now; log every changed (or new) price."""
    if not before or not ready():
        return 0
    ids = before.get(("_ids",), [])
    after = snapshot(ids)
    n = 0
    for key, now in after.items():
        if key == ("_ids",) or now.get("price") is None:
            continue
        was = before.get(key)
        old = was.get("price") if was else None
        if old is not None and abs((old or 0) - (now["price"] or 0)) < 0.005:
            continue
        if old is None and (now["price"] or 0) <= 0:
            continue
        if log_change(key[0], key[1], now["unit"], now["barcode"], old, now["price"],
                      "new" if (new_product and old is None) else source):
            n += 1
    return n


def pending(date_from=None, include_printed=False, search=""):
    """Latest change per product/unit (older unprinted ones folded in)."""
    if not ready():
        return []
    where, params = [], []
    if not include_printed:
        where.append("ISNULL(l.label_printed,0)=0")
    if date_from:
        where.append("l.changed_at >= ?"); params.append(date_from)
    sql = ("SELECT l.*, p.product_code, p.product_name_en, p.product_name_ar, "
           "p.category_id FROM price_change_log l JOIN products p "
           "ON p.product_id=l.product_id" + (" WHERE " + " AND ".join(where) if where else "") +
           " ORDER BY l.changed_at DESC, l.log_id DESC")
    rows = db.fetchall(sql, tuple(params)) or []
    seen, out = {}, []
    s = (search or "").strip().lower()
    for r in rows:
        k = (r["product_id"], r.get("unit_id") or 0)
        if k in seen:
            seen[k]["ids"].append(r["log_id"])
            if r.get("old_price") is not None:
                seen[k]["first_old"] = r["old_price"]
            continue
        if s and s not in " ".join(str(r.get(x) or "") for x in
                                   ("product_code", "product_name_en", "barcode")).lower():
            continue
        item = dict(r)
        item["ids"] = [r["log_id"]]
        item["first_old"] = r.get("old_price")
        seen[k] = item
        out.append(item)
    return out


def mark_printed(log_ids):
    ids = [int(i) for i in log_ids or []]
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        ph = ",".join("?" * len(chunk))
        db.execute(f"UPDATE price_change_log SET label_printed=1, printed_at=GETDATE() "
                   f"WHERE log_id IN ({ph})", tuple(chunk))


def dismiss(log_ids):
    ids = [int(i) for i in log_ids or []]
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        ph = ",".join("?" * len(chunk))
        db.execute(f"DELETE FROM price_change_log WHERE log_id IN ({ph})", tuple(chunk))
