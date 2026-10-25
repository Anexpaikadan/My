# ============================================================
# DayBill ERP - price lists (v6.0)
# ------------------------------------------------------------
# A customer (or one invoice) can be sold at another price:
#   Standard   the product's normal selling price (per unit)
#   Wholesale  the product's wholesale price (Product ▸ Prices), else normal
#   any list you make: "VIP −5 %", "Restaurants", "Staff at cost +10 %" …
#     • a list starts from the normal / wholesale price or the cost and
#       adds or takes off a percent, and
#     • can have its own fixed price for single products (and units).
# Customers ▸ Price list picks the list; the Sales invoice "Price
# Category" box and the POS follow the customer (the box can still be
# changed for one invoice).
# ============================================================
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

STANDARD, WHOLESALE = "Standard", "Wholesale"
BASES = [("retail", "Normal selling price"), ("wholesale", "Wholesale price"),
         ("cost", "Cost (average)")]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        db.fetchone("SELECT TOP 1 price_list_id FROM price_lists")
        return True
    except Exception:
        return False


def lists(active_only=True):
    if not ready():
        return []
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT * FROM price_lists %s ORDER BY name_en"
            % ("WHERE is_active=1" if active_only else "")) or []]
    except Exception:
        return []


def get(list_id):
    try:
        r = db.fetchone("SELECT * FROM price_lists WHERE price_list_id=?", (int(list_id),))
        return dict(r) if r else None
    except Exception:
        return None


def choices():
    """[(label, key)] for the Price Category box: key None = Standard,
    'wholesale', or a price_list_id."""
    out = [(STANDARD, None), (WHOLESALE, "wholesale")]
    out += [(l["name_en"], l["price_list_id"]) for l in lists()]
    return out


def key_for_label(label):
    return next((k for l, k in choices() if l == label), None)


def label_for_key(key):
    return next((l for l, k in choices() if k == key), STANDARD)


def save_list(list_id, name_en, name_ar="", base_on="retail", adjust_percent=0, active=True):
    name_en = (name_en or "").strip()
    if not name_en:
        raise ValueError("Type a name for the price list.")
    if name_en.lower() in (STANDARD.lower(), WHOLESALE.lower()):
        raise ValueError("'%s' is a built-in price — choose another name." % name_en)
    if base_on not in dict(BASES):
        base_on = "retail"
    adj = round(_f(adjust_percent), 3)
    if adj <= -100:
        raise ValueError("The percent must be more than −100.")
    dup = db.execute_scalar("SELECT price_list_id FROM price_lists WHERE name_en=? AND "
                            "price_list_id<>?", (name_en, int(list_id or 0)))
    if dup:
        raise ValueError("A price list with this name already exists.")
    if list_id:
        db.execute("UPDATE price_lists SET name_en=?, name_ar=?, base_on=?, adjust_percent=?, "
                   "is_active=? WHERE price_list_id=?",
                   (name_en, name_ar or None, base_on, adj, 1 if active else 0, int(list_id)))
        return int(list_id)
    db.execute("INSERT INTO price_lists (name_en, name_ar, base_on, adjust_percent, is_active) "
               "VALUES (?,?,?,?,?)", (name_en, name_ar or None, base_on, adj, 1 if active else 0))
    return db.execute_scalar("SELECT price_list_id FROM price_lists WHERE name_en=?", (name_en,))


def delete_list(list_id):
    with db.transaction():
        db.execute("UPDATE customers SET price_list_id=NULL WHERE price_list_id=?", (int(list_id),))
        db.execute("DELETE FROM price_list_items WHERE price_list_id=?", (int(list_id),))
        db.execute("DELETE FROM price_lists WHERE price_list_id=?", (int(list_id),))


def items(list_id):
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT i.*, p.product_code, p.product_name_en, p.unit_price FROM price_list_items i "
            "JOIN products p ON p.product_id=i.product_id WHERE i.price_list_id=? "
            "ORDER BY p.product_name_en, i.unit_name", (int(list_id),)) or []]
    except Exception:
        return []


def set_price(list_id, product_id, price, unit_name=None):
    """Fixed price of one product (and unit; None = every unit × factor)."""
    price = round(_f(price), 4)
    u = (unit_name or "").strip() or None
    with db.transaction():
        if u is None:
            db.execute("DELETE FROM price_list_items WHERE price_list_id=? AND product_id=? "
                       "AND unit_name IS NULL", (int(list_id), int(product_id)))
        else:
            db.execute("DELETE FROM price_list_items WHERE price_list_id=? AND product_id=? "
                       "AND unit_name=?", (int(list_id), int(product_id), u))
        db.execute("INSERT INTO price_list_items (price_list_id, product_id, unit_name, price) "
                   "VALUES (?,?,?,?)", (int(list_id), int(product_id), u, price))


def remove_price(item_id):
    db.execute("DELETE FROM price_list_items WHERE item_id=?", (int(item_id),))


def for_customer(customer_id):
    """The customer's price list key (None / price_list_id)."""
    if not customer_id or not ready():
        return None
    try:
        v = db.execute_scalar("SELECT price_list_id FROM customers WHERE customer_id=?",
                              (int(customer_id),))
        return int(v) if v else None
    except Exception:
        return None


def set_customer(customer_id, list_id):
    db.execute("UPDATE customers SET price_list_id=? WHERE customer_id=?",
               (int(list_id) if list_id else None, int(customer_id)))


def _product(pid):
    try:
        r = db.fetchone("SELECT unit_price, ISNULL(wholesale_price,0) AS wholesale_price, "
                        "ISNULL(average_cost,0) AS average_cost, ISNULL(purchase_price,0) AS "
                        "purchase_price FROM products WHERE product_id=?", (int(pid),))
    except Exception:
        try:
            r = db.fetchone("SELECT unit_price FROM products WHERE product_id=?", (int(pid),))
        except Exception:
            r = None
    return dict(r) if r else {}


def price_for(key, product_id, unit_name=None, base_price=None, factor=1.0):
    """Selling price of one unit under the price list `key`.
    base_price = the normal price of THIS unit (what the screen shows now);
    factor     = base units in this unit (Box = 12).
    Returns base_price when the list has nothing to say."""
    base = _f(base_price)
    factor = _f(factor) or 1.0
    if key in (None, "", STANDARD) or not product_id:
        return base
    p = _product(product_id)
    if key == "wholesale" or key == WHOLESALE:
        w = _f(p.get("wholesale_price"))
        return round(w * factor, 4) if w > 0 else base
    try:
        lid = int(key)
    except (TypeError, ValueError):
        return base
    pl = get(lid)
    if not pl or not pl.get("is_active", 1):
        return base
    u = (unit_name or "").strip()
    try:
        fixed = None
        if u:
            fixed = db.execute_scalar("SELECT price FROM price_list_items WHERE price_list_id=? "
                                      "AND product_id=? AND unit_name=?", (lid, int(product_id), u))
        if fixed is None:
            one = db.execute_scalar("SELECT price FROM price_list_items WHERE price_list_id=? "
                                    "AND product_id=? AND unit_name IS NULL", (lid, int(product_id)))
            if one is not None:
                fixed = _f(one) * factor
        if fixed is not None:
            return round(_f(fixed), 4)
    except Exception:
        pass
    b = pl.get("base_on") or "retail"
    if b == "wholesale":
        w = _f(p.get("wholesale_price"))
        start = w * factor if w > 0 else base
    elif b == "cost":
        c = _f(p.get("average_cost")) or _f(p.get("purchase_price"))
        start = c * factor if c > 0 else base
    else:
        start = base
    return round(start * (1 + _f(pl.get("adjust_percent")) / 100.0), 4)
