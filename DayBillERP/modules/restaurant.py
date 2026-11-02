# ============================================================
# DayBill ERP - restaurant: tables, orders, kitchen tickets (v7.0)
# ------------------------------------------------------------
# A running order (a table that is eating, a takeaway being made, a
# delivery) is kept here while it is open; it is the "held bill" of the
# POS, tagged with its table and order type, and every PC sees it.
# When it is paid the POS writes a NORMAL POS bill — stock, recipe
# ingredients, VAT and the books post as for any sale — and the order
# is closed with a link to that bill (rest_orders.invoice_id).
#
# Tables (database/patches/zzz_v700_restaurant_patch.sql):
#   rest_areas, rest_tables              dining areas and tables
#   rest_stations                        kitchen stations + their printer
#   rest_station_categories              category → station (NULL = no KOT)
#   rest_orders, rest_order_lines        orders and what they hold
#   rest_kots, rest_kot_lines            kitchen order tickets (KOT); a
#                                        negative quantity = CANCEL
#
#   setting(key) / set_setting(key, v)   restaurant options (company DB)
#   order_types()                        the order types switched on
#   areas() tables() stations()          the set-up (save_* / delete_*)
#   table_board()                        every table with its live state
#                                        (free / occupied / billed)
#   running(dine_in=False)               orders not paid yet
#   open_order(type, table_id, …)        → order_id
#   save_lines(order_id, lines, version) the order's items (POS screen)
#   merge_lines(base, mine, theirs)      join changes made on two PCs
#   transfer(order_id, table_id)         move an order to a free table
#   merge(from_id, into_id)              one bill for two tables
#   cancel(order_id, reason)             cancel; the kitchen gets CANCEL
#   mark_billed(order_id, total)         the bill was printed
#   close(order_id, invoice_id, lines)   paid: the table is free again
#   unsent(order_id, lines)              what the kitchen does not have
#                                        yet: new (+) and taken off (−)
#   send_to_kitchen(order_id, lines)     → [kot_id], one per station
#   kots(...) bump(kot_id) set_kot_status(kot_id, status)
#   kot_text / kot_pdf / print_kot       the ticket (58 / 80 mm)
#   prebill_text / prebill_pdf           the bill before payment
#   receipt_rows(invoice_id)             order type, table, delivery …
#                                        for the printed receipt
# ============================================================

import os
import re
import tempfile
from collections import OrderedDict, defaultdict
from datetime import datetime

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

ORDER_TYPES = ("Dine-in", "Takeaway", "Delivery")
RUNNING = ("open", "billed")
KOT_FLOW = ("new", "preparing", "ready", "served")
KOT_LABEL = {"new": "New", "preparing": "Preparing", "ready": "Ready", "served": "Served"}
STATUS_LABEL = {"open": "Open", "billed": "Bill printed", "closed": "Paid",
                "cancelled": "Cancelled", "merged": "Merged"}

# options (company database first, then this PC's settings)
DEFAULTS = {"rest_order_types": "Dine-in,Takeaway,Delivery", "rest_kot_print": True,
            "rest_service_charge_pct": 0, "rest_kitchen_printer": "", "rest_kot_paper": "80",
            "rest_counter_as_takeaway": True, "rest_clear_after_kot": True,
            "rest_note_choices": "No onion,No garlic,Extra spicy,Less spicy,Less salt,"
                                 "No ice,Well done,Pack separately"}


class OrderChanged(Exception):
    """Another PC saved this order after this screen loaded it."""

    def __init__(self, version=None):
        Exception.__init__(self, "This order was changed on another computer. Open it again "
                                 "(F7) to see the new items, then try again.")
        self.version = version


class OrderClosed(Exception):
    """The order is paid, cancelled or merged already."""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _i(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _s(v, n=200):
    return str(v or "").strip()[:n]


def _user():
    try:
        from modules import permissions as p
        return (p.session_user() or {}).get("user_id")
    except Exception:
        return None


def ready():
    try:
        return bool(db.execute_scalar("SELECT CASE WHEN OBJECT_ID('rest_orders','U') IS NULL "
                                      "THEN 0 ELSE 1 END"))
    except Exception:
        return False


def on():
    """The company uses the restaurant module."""
    try:
        from modules import business
        return business.has("restaurant")
    except Exception:
        return False


def money(x, sym=True):
    try:
        from modules import country
        return country.money(x, sym=sym)
    except Exception:
        return "{:,.2f}".format(_f(x))


def symbol():
    try:
        from modules import country
        return country.symbol()
    except Exception:
        return ""


def natural_key(text):
    """'T2' before 'T10'."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", str(text or ""))]


# ── options ──────────────────────────────────────────────────
def setting(key, default=None):
    if default is None:
        default = DEFAULTS.get(key)
    try:
        from modules import country
        v = country.option(key)
        if v is not None:
            return v
    except Exception:
        pass
    try:
        from config import settings as cfg
        v = cfg.get(key, None)
        return default if v is None else v
    except Exception:
        return default


def flag(key):
    v = setting(key)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def set_setting(key, value):
    """Keep a restaurant option in the company database (every PC)."""
    ok = False
    try:
        from modules import country
        ok = country.set_option(key, value)
    except Exception:
        ok = False
    try:
        from config import settings as cfg
        cfg.set(key, value)
    except Exception:
        pass
    return ok


def order_types():
    """The order types switched on (Settings ▸ Restaurant Setup)."""
    want = [x.strip().lower() for x in str(setting("rest_order_types") or "").split(",")]
    out = [t for t in ORDER_TYPES if t.lower() in want]
    return out or list(ORDER_TYPES)


def service_pct():
    return max(0.0, min(_f(setting("rest_service_charge_pct")), 50.0))


def note_choices():
    return [x.strip() for x in str(setting("rest_note_choices") or "").split(",") if x.strip()]


# ── areas ────────────────────────────────────────────────────
def areas(active_only=False):
    try:
        return db.fetchall("SELECT * FROM rest_areas" + (" WHERE is_active=1" if active_only else "")
                           + " ORDER BY sort_order, area_name") or []
    except Exception:
        return []


def save_area(area_id, name, sort_order=0, active=True):
    name = _s(name, 100)
    if not name:
        raise ValueError("Type the area name.")
    dup = db.fetchone("SELECT area_id FROM rest_areas WHERE area_name=? AND area_id<>?",
                      (name, int(area_id or 0)))
    if dup:
        raise ValueError("There is already an area called '%s'." % name)
    if area_id:
        db.execute("UPDATE rest_areas SET area_name=?, sort_order=?, is_active=? WHERE area_id=?",
                   (name, _i(sort_order), 1 if active else 0, int(area_id)))
        return int(area_id)
    return int(db.execute_scalar("INSERT INTO rest_areas (area_name, sort_order, is_active) "
                                 "OUTPUT INSERTED.area_id VALUES (?,?,?)",
                                 (name, _i(sort_order), 1 if active else 0)))


def delete_area(area_id):
    """The area's tables stay (without an area)."""
    with db.transaction():
        db.execute("UPDATE rest_tables SET area_id=NULL WHERE area_id=?", (int(area_id),))
        db.execute("DELETE FROM rest_areas WHERE area_id=?", (int(area_id),))


# ── tables ───────────────────────────────────────────────────
def tables(active_only=True):
    try:
        rows = db.fetchall(
            "SELECT t.*, ISNULL(a.area_name,'') AS area_name, ISNULL(a.sort_order, 9999) AS area_sort "
            "FROM rest_tables t LEFT JOIN rest_areas a ON a.area_id=t.area_id"
            + (" WHERE t.is_active=1" if active_only else "")) or []
    except Exception:
        return []
    rows.sort(key=lambda r: (r["area_sort"], natural_key(r["area_name"]), _i(r.get("sort_order")),
                             natural_key(r["table_name"])))
    return rows


def table(table_id):
    if not table_id:
        return None
    return db.fetchone("SELECT t.*, ISNULL(a.area_name,'') AS area_name FROM rest_tables t "
                       "LEFT JOIN rest_areas a ON a.area_id=t.area_id WHERE t.table_id=?",
                       (int(table_id),))


def save_table(table_id, name, area_id=None, seats=4, sort_order=0, active=True):
    name = _s(name, 50)
    if not name:
        raise ValueError("Type the table name or number.")
    area_id = int(area_id) if area_id else None
    dup = db.fetchone("SELECT table_id FROM rest_tables WHERE table_name=? AND ISNULL(area_id,0)=? "
                      "AND table_id<>? AND is_active=1", (name, area_id or 0, int(table_id or 0)))
    if dup:
        raise ValueError("There is already a table '%s' in this area." % name)
    vals = (name, area_id, max(1, _i(seats, 4)), _i(sort_order), 1 if active else 0)
    if table_id:
        if not active and running_order_of(table_id):
            raise ValueError("This table has an open order. Close the order first.")
        db.execute("UPDATE rest_tables SET table_name=?, area_id=?, seats=?, sort_order=?, is_active=? "
                   "WHERE table_id=?", vals + (int(table_id),))
        return int(table_id)
    return int(db.execute_scalar("INSERT INTO rest_tables (table_name, area_id, seats, sort_order, "
                                 "is_active) OUTPUT INSERTED.table_id VALUES (?,?,?,?,?)", vals))


def delete_table(table_id):
    """A table with past orders is only switched off (reports keep it)."""
    if running_order_of(table_id):
        raise ValueError("This table has an open order. Close the order first.")
    used = db.execute_scalar("SELECT COUNT(*) FROM rest_orders WHERE table_id=?", (int(table_id),))
    if used:
        db.execute("UPDATE rest_tables SET is_active=0 WHERE table_id=?", (int(table_id),))
        return "off"
    db.execute("DELETE FROM rest_tables WHERE table_id=?", (int(table_id),))
    return "deleted"


def add_tables(first, last, prefix="", area_id=None, seats=4):
    """Quick set-up: tables first … last ('T1' … 'T20'). Names that are
    already there are skipped. → how many were added."""
    first, last = _i(first, 1), _i(last, 0)
    if last < first or last - first > 199:
        raise ValueError("Give a range like 1 to 20 (at most 200 tables at once).")
    have = {r["table_name"].lower() for r in tables(active_only=True)
            if (r.get("area_id") or None) == (int(area_id) if area_id else None)}
    n = 0
    with db.transaction():
        for k in range(first, last + 1):
            name = ("%s%d" % (_s(prefix, 20), k)).strip()
            if name.lower() in have:
                continue
            db.execute("INSERT INTO rest_tables (table_name, area_id, seats, sort_order, is_active) "
                       "VALUES (?,?,?,?,1)", (name, int(area_id) if area_id else None,
                                              max(1, _i(seats, 4)), k))
            n += 1
    return n


# ── kitchen stations ─────────────────────────────────────────
def stations(active_only=True):
    try:
        return db.fetchall("SELECT * FROM rest_stations" + (" WHERE is_active=1" if active_only else "")
                           + " ORDER BY sort_order, station_id") or []
    except Exception:
        return []


def save_station(station_id, name, printer="", paper_mm=80, copies=1, sort_order=0, active=True):
    name = _s(name, 100)
    if not name:
        raise ValueError("Type the station name (for example Kitchen, Grill, Drinks).")
    vals = (name, _s(printer, 200), 58 if _i(paper_mm, 80) == 58 else 80,
            max(1, min(_i(copies, 1), 5)), _i(sort_order), 1 if active else 0)
    if station_id:
        db.execute("UPDATE rest_stations SET station_name=?, printer_name=?, paper_mm=?, copies=?, "
                   "sort_order=?, is_active=? WHERE station_id=?", vals + (int(station_id),))
        return int(station_id)
    return int(db.execute_scalar("INSERT INTO rest_stations (station_name, printer_name, paper_mm, "
                                 "copies, sort_order, is_active) OUTPUT INSERTED.station_id "
                                 "VALUES (?,?,?,?,?,?)", vals))


def delete_station(station_id):
    """Its categories go back to the default station."""
    with db.transaction():
        db.execute("DELETE FROM rest_station_categories WHERE station_id=?", (int(station_id),))
        db.execute("DELETE FROM rest_stations WHERE station_id=?", (int(station_id),))


def categories():
    try:
        return db.fetchall("SELECT category_id, category_name_en FROM product_categories "
                           "WHERE ISNULL(is_active,1)=1 ORDER BY category_name_en") or []
    except Exception:
        return []


def category_map():
    """{category_id: station_id or None (not sent to the kitchen)}.
    A category that is not listed goes to the default station."""
    try:
        return {r["category_id"]: r["station_id"] for r in
                (db.fetchall("SELECT category_id, station_id FROM rest_station_categories") or [])}
    except Exception:
        return {}


def set_category_station(category_id, station):
    """station: a station_id, None = not sent to the kitchen,
    'default' = the default station."""
    cid = int(category_id)
    db.execute("DELETE FROM rest_station_categories WHERE category_id=?", (cid,))
    if station != "default":
        db.execute("INSERT INTO rest_station_categories (category_id, station_id) VALUES (?,?)",
                   (cid, int(station) if station else None))


def default_station():
    st = stations()
    if st:
        return dict(st[0])
    return {"station_id": None, "station_name": "Kitchen", "printer_name": "",
            "paper_mm": _i(setting("rest_kot_paper"), 80), "copies": 1}


def _routes(product_ids):
    """{product_id: station dict, or None when it is not sent}."""
    ids = sorted({int(p) for p in product_ids if p})
    if not ids:
        return {}
    cats = {}
    try:
        for r in db.fetchall("SELECT product_id, category_id FROM products WHERE product_id IN (%s)"
                             % ",".join("?" * len(ids)), tuple(ids)) or []:
            cats[r["product_id"]] = r.get("category_id")
    except Exception:
        pass
    cmap = category_map()
    by_id = {s["station_id"]: dict(s) for s in stations()}
    dflt = default_station()
    out = {}
    for pid in ids:
        c = cats.get(pid)
        if c in cmap:
            sid = cmap[c]
            out[pid] = None if sid is None else by_id.get(sid, dflt)
        else:
            out[pid] = dflt
    return out


# ── waiters ──────────────────────────────────────────────────
def waiters():
    """Names for the waiter box: active employees + waiters used lately."""
    names = []
    try:
        names += [r["full_name_en"] for r in (db.fetchall(
            "SELECT full_name_en FROM employees WHERE ISNULL(is_active,1)=1 ORDER BY full_name_en") or [])
            if r.get("full_name_en")]
    except Exception:
        pass
    try:
        names += [r["waiter_name"] for r in (db.fetchall(
            "SELECT DISTINCT waiter_name FROM rest_orders WHERE ISNULL(waiter_name,'')<>'' "
            "AND opened_at >= DATEADD(day,-90,GETDATE())") or [])]
    except Exception:
        pass
    out = []
    for n in names:
        if n and n not in out:
            out.append(n)
    return sorted(out, key=str.lower)


def delivery_lookup(phone):
    """Name and address for a phone number: the last delivery to it,
    else the customer with that phone. → {} when not known."""
    ph = _s(phone, 30)
    if len(re.sub(r"\D", "", ph)) < 5:
        return {}
    try:
        r = db.fetchone("SELECT TOP 1 customer_name, delivery_address FROM rest_orders "
                        "WHERE customer_phone=? AND ISNULL(customer_name,'')<>'' ORDER BY order_id DESC", (ph,))
        if r:
            return {"customer_name": r.get("customer_name") or "", "address": r.get("delivery_address") or ""}
    except Exception:
        pass
    try:
        r = db.fetchone("SELECT TOP 1 customer_name_en, ISNULL(address_en,'') AS a, ISNULL(city_en,'') AS c "
                        "FROM customers WHERE phone=? AND ISNULL(is_active,1)=1", (ph,))
        if r:
            return {"customer_name": r.get("customer_name_en") or "",
                    "address": ", ".join(x for x in (r.get("a"), r.get("c")) if x)}
    except Exception:
        pass
    return {}


# ── orders ───────────────────────────────────────────────────
_ORDER_SQL = ("SELECT o.*, ISNULL(t.table_name,'') AS table_name, ISNULL(a.area_name,'') AS area_name, "
              "DATEDIFF(minute, o.opened_at, GETDATE()) AS minutes "
              "FROM rest_orders o LEFT JOIN rest_tables t ON t.table_id=o.table_id "
              "LEFT JOIN rest_areas a ON a.area_id=t.area_id ")


def get_order(order_id):
    if not order_id:
        return None
    r = db.fetchone(_ORDER_SQL + "WHERE o.order_id=?", (int(order_id),))
    return dict(r) if r else None


def order_of_invoice(invoice_id):
    if not invoice_id:
        return None
    r = db.fetchone(_ORDER_SQL + "WHERE o.invoice_id=? ORDER BY o.order_id", (int(invoice_id),))
    return dict(r) if r else None


def running_order_of(table_id):
    if not table_id:
        return None
    r = db.fetchone(_ORDER_SQL + "WHERE o.table_id=? AND o.status IN ('open','billed') "
                    "ORDER BY o.order_id", (int(table_id),))
    return dict(r) if r else None


def order_lines(order_id):
    return [dict(r) for r in (db.fetchall("SELECT * FROM rest_order_lines WHERE order_id=? "
                                          "ORDER BY line_no, line_id", (int(order_id),)) or [])]


def running(dine_in=False):
    """Orders not paid yet. dine_in=False: only those without a table
    (takeaway, delivery); True: every running order."""
    where = "WHERE o.status IN ('open','billed')"
    if not dine_in:
        where += " AND o.table_id IS NULL"
    try:
        return [dict(r) for r in (db.fetchall(_ORDER_SQL + where + " ORDER BY o.opened_at") or [])]
    except Exception:
        return []


def table_board():
    """Every active table with its live state:
    state 'free' / 'occupied' / 'billed' + the running order's number,
    guests, waiter, total and minutes open."""
    try:
        rows = db.fetchall(
            "SELECT t.table_id, t.table_name, t.seats, t.area_id, t.sort_order, "
            "ISNULL(a.area_name,'') AS area_name, ISNULL(a.sort_order, 9999) AS area_sort, "
            "o.order_id, o.order_no, o.status, o.guests, o.waiter_name, o.running_total, "
            "o.opened_at, o.bill_printed_at, o.bill_total, "
            "DATEDIFF(minute, o.opened_at, GETDATE()) AS minutes "
            "FROM rest_tables t LEFT JOIN rest_areas a ON a.area_id=t.area_id "
            "OUTER APPLY (SELECT TOP 1 * FROM rest_orders x WHERE x.table_id=t.table_id "
            "             AND x.status IN ('open','billed') ORDER BY x.order_id) o "
            "WHERE t.is_active=1") or []
    except Exception:
        return []
    out = []
    for r in rows:
        r = dict(r)
        r["state"] = ("free" if not r.get("order_id") else
                      ("billed" if r.get("status") == "billed" else "occupied"))
        out.append(r)
    out.sort(key=lambda r: (r["area_sort"], natural_key(r["area_name"]), _i(r.get("sort_order")),
                            natural_key(r["table_name"])))
    return out


def _next_no(table, no_col, date_col):
    """Running number of the day (inside a transaction: two tills at
    once never get the same one)."""
    return int(db.execute_scalar(
        "SELECT ISNULL(MAX(%s),0)+1 FROM %s WITH (UPDLOCK, HOLDLOCK) WHERE %s=CAST(GETDATE() AS DATE)"
        % (no_col, table, date_col)) or 1)


def open_order(order_type="Dine-in", table_id=None, guests=None, waiter=None, customer_name=None,
               phone=None, address=None, driver=None, notes=None):
    """Start an order. A table may have only one open order."""
    if order_type not in ORDER_TYPES:
        raise ValueError("Unknown order type '%s'." % order_type)
    if order_type == "Dine-in" and not table_id:
        raise ValueError("Pick a table for a dine-in order.")
    with db.transaction():
        if table_id:
            t = table(table_id)
            if not t or not t.get("is_active"):
                raise ValueError("This table is not in the list any more.")
            busy = db.fetchone("SELECT order_no FROM rest_orders WITH (UPDLOCK, HOLDLOCK) "
                               "WHERE table_id=? AND status IN ('open','billed')", (int(table_id),))
            if busy:
                raise ValueError("Table %s already has an open order (#%s)."
                                 % (t["table_name"], busy["order_no"]))
        no = _next_no("rest_orders", "order_no", "order_date")
        oid = db.execute_scalar(
            "INSERT INTO rest_orders (order_no, order_type, table_id, guests, waiter_name, "
            "customer_name, customer_phone, delivery_address, driver_name, notes, opened_by, status) "
            "OUTPUT INSERTED.order_id VALUES (?,?,?,?,?,?,?,?,?,?,?, 'open')",
            (no, order_type, int(table_id) if table_id else None,
             _i(guests) if guests not in (None, "") else None, _s(waiter, 100) or None,
             _s(customer_name, 200) or None, _s(phone, 30) or None, _s(address, 500) or None,
             _s(driver, 100) or None, _s(notes, 500) or None, _user()))
    return int(oid)


def update_order(order_id, **fields):
    """Change guests, waiter, delivery details, notes or service_on."""
    allowed = {"guests": lambda v: _i(v) if v not in (None, "") else None,
               "waiter_name": lambda v: _s(v, 100) or None,
               "customer_name": lambda v: _s(v, 200) or None,
               "customer_phone": lambda v: _s(v, 30) or None,
               "delivery_address": lambda v: _s(v, 500) or None,
               "driver_name": lambda v: _s(v, 100) or None,
               "notes": lambda v: _s(v, 500) or None,
               "service_on": lambda v: 1 if v else 0}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append("%s=?" % k)
            vals.append(allowed[k](v))
    if not sets:
        return
    db.execute("UPDATE rest_orders SET %s, updated_at=GETDATE() WHERE order_id=?" % ", ".join(sets),
               tuple(vals) + (int(order_id),))


def set_type(order_id, order_type, table_id=None):
    """Dine-in ↔ Takeaway ↔ Delivery. Dine-in needs a free table; the
    other types free the table."""
    if order_type not in ORDER_TYPES:
        raise ValueError("Unknown order type '%s'." % order_type)
    with db.transaction():
        o = _lock_running(order_id)
        if order_type == "Dine-in":
            table_id = table_id or o.get("table_id")
            if not table_id:
                raise ValueError("Pick a table for a dine-in order.")
            if table_id != o.get("table_id"):
                _check_free(table_id)
        else:
            table_id = None
        db.execute("UPDATE rest_orders SET order_type=?, table_id=?, version=version+1, "
                   "updated_at=GETDATE() WHERE order_id=?",
                   (order_type, int(table_id) if table_id else None, int(order_id)))


def _lock_running(order_id):
    o = db.fetchone("SELECT * FROM rest_orders WITH (UPDLOCK) WHERE order_id=?", (int(order_id),))
    if not o:
        raise OrderClosed("This order is not there any more.")
    if o["status"] not in RUNNING:
        raise OrderClosed("Order #%s is already %s." % (o["order_no"],
                                                        STATUS_LABEL.get(o["status"], o["status"]).lower()))
    return dict(o)


def _check_free(table_id):
    t = table(table_id)
    if not t or not t.get("is_active"):
        raise ValueError("This table is not in the list any more.")
    busy = db.fetchone("SELECT order_no FROM rest_orders WITH (UPDLOCK, HOLDLOCK) "
                       "WHERE table_id=? AND status IN ('open','billed')", (int(table_id),))
    if busy:
        raise ValueError("Table %s is not free (order #%s)." % (t["table_name"], busy["order_no"]))
    return t


# ── the order's items ────────────────────────────────────────
def _note(ln):
    return _s(ln.get("note") if "note" in ln else ln.get("kitchen_note"), 200)


def line_key(ln):
    """One kind of item: product + unit + kitchen note."""
    return (ln.get("product_id"), str(ln.get("unit_name") or "").strip().lower(),
            _note(ln).lower())


def _is_item(ln):
    """A real item line of the order (not the service charge)."""
    return not ln.get("_service") and _f(ln.get("quantity")) != 0


def save_lines(order_id, lines, version=None, price_incl=True, total=None):
    """Replace the order's items with `lines` (POS cart lines).
    version = the order version this screen loaded (None = do not check).
    → the new version. OrderChanged when another PC saved in between."""
    lines = [ln for ln in (lines or []) if _is_item(ln)]
    with db.transaction():
        o = _lock_running(order_id)
        if version is not None and _i(o.get("version")) != _i(version):
            raise OrderChanged(o.get("version"))
        db.execute("DELETE FROM rest_order_lines WHERE order_id=?", (int(order_id),))
        for i, ln in enumerate(lines, 1):
            _insert_line(order_id, i, ln, price_incl)
        tot = round(_f(total) if total is not None else sum(_f(ln.get("line_total")) for ln in lines), 2)
        status = o["status"]
        if status == "billed" and abs(tot - _f(o.get("bill_total"))) > 0.005:
            status = "open"                      # items changed after the bill was printed
        db.execute("UPDATE rest_orders SET running_total=?, status=?, version=version+1, "
                   "updated_at=GETDATE(), bill_printed_at=CASE WHEN ?='open' THEN NULL "
                   "ELSE bill_printed_at END WHERE order_id=?",
                   (tot, status, status, int(order_id)))
        return _i(o.get("version")) + 1


def _insert_line(order_id, i, ln, price_incl):
    db.execute(
        "INSERT INTO rest_order_lines (order_id, line_no, product_id, product_code, product_name_en, "
        "product_name_ar, unit_name, factor, quantity, unit_price, price_incl, price_typed, vat_rate, "
        "vat_code, vat_category_id, line_total, kitchen_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (int(order_id), i, ln.get("product_id"), _s(ln.get("product_code"), 50),
         _s(ln.get("product_name_en"), 200) or "Item", _s(ln.get("product_name_ar"), 200),
         _s(ln.get("unit_name"), 50), _f(ln.get("factor")) or 1.0, round(_f(ln.get("quantity")), 3),
         round(_f(ln.get("unit_price")), 4), 1 if ln.get("price_incl", price_incl) else 0,
         1 if (ln.get("_price_typed") or ln.get("price_typed")) else 0, _f(ln.get("vat_rate")),
         _s(ln.get("vat_code") or "S", 5), ln.get("vat_category_id"),
         round(_f(ln.get("line_total")), 2), _note(ln) or None))


def merge_lines(base, mine, theirs):
    """Two PCs changed one order. base = the items when this screen
    loaded it, mine = this screen now, theirs = what the other PC saved.
    Both changes are kept: qty = theirs + (mine − base) per kind of item."""
    def qmap(lines):
        q, first = OrderedDict(), {}
        for ln in lines or []:
            if not _is_item(ln) or _f(ln.get("quantity")) < 0:
                continue
            k = line_key(ln)
            q[k] = q.get(k, 0.0) + _f(ln.get("quantity"))
            first.setdefault(k, ln)
        return q, first
    qb, _fb = qmap(base)
    qm, fm = qmap(mine)
    qt, ft = qmap(theirs)
    out = []
    for k in list(qt.keys()) + [k for k in qm.keys() if k not in qt]:
        q = qt.get(k, 0.0) + (qm.get(k, 0.0) - qb.get(k, 0.0))
        if q <= 1e-9:
            continue
        touched = k in qm and abs(qm.get(k, 0.0) - qb.get(k, 0.0)) > 1e-9
        tpl = fm[k] if (touched or k not in ft) else ft[k]
        ln = dict(tpl)
        ln["quantity"] = round(q, 3)
        out.append(ln)
    return out


# ── moving orders ────────────────────────────────────────────
def transfer(order_id, to_table_id):
    """Move a running order to a free table (a takeaway that sits down
    becomes dine-in)."""
    with db.transaction():
        _lock_running(order_id)
        _check_free(to_table_id)
        db.execute("UPDATE rest_orders SET table_id=?, order_type=N'Dine-in', version=version+1, "
                   "updated_at=GETDATE() WHERE order_id=?", (int(to_table_id), int(order_id)))


def merge(from_id, into_id):
    """One bill for two tables: the items (and kitchen tickets) of order
    from_id move into order into_id; from_id is marked 'merged'."""
    if int(from_id) == int(into_id):
        raise ValueError("Pick two different orders.")
    with db.transaction():
        src = _lock_running(from_id)
        dst = _lock_running(into_id)
        n = _i(db.execute_scalar("SELECT ISNULL(MAX(line_no),0) FROM rest_order_lines WHERE order_id=?",
                                 (int(into_id),)))
        db.execute("UPDATE rest_order_lines SET order_id=?, line_no=line_no+? WHERE order_id=?",
                   (int(into_id), n, int(from_id)))
        db.execute("UPDATE rest_kots SET order_id=? WHERE order_id=?", (int(into_id), int(from_id)))
        tot = _f(db.execute_scalar("SELECT ISNULL(SUM(line_total),0) FROM rest_order_lines "
                                   "WHERE order_id=?", (int(into_id),)))
        guests = (_i(dst.get("guests")) + _i(src.get("guests"))) or None
        db.execute("UPDATE rest_orders SET running_total=?, guests=?, status=N'open', bill_printed_at=NULL, "
                   "version=version+1, updated_at=GETDATE() WHERE order_id=?",
                   (round(tot, 2), guests, int(into_id)))
        db.execute("UPDATE rest_orders SET status=N'merged', merged_into=?, running_total=0, "
                   "closed_at=GETDATE(), closed_by=?, version=version+1, updated_at=GETDATE() "
                   "WHERE order_id=?", (int(into_id), _user(), int(from_id)))


def cancel(order_id, reason=""):
    """Cancel a running order. Items the kitchen already has get a
    CANCEL ticket. → [kot_id] of those tickets."""
    with db.transaction():
        o = _lock_running(order_id)
        kot_ids = send_to_kitchen(order_id, [], note="ORDER CANCELLED")
        db.execute("UPDATE rest_orders SET status=N'cancelled', cancel_reason=?, closed_at=GETDATE(), "
                   "closed_by=?, version=version+1, updated_at=GETDATE() WHERE order_id=?",
                   (_s(reason, 200) or None, _user(), int(order_id)))
    try:                                        # cashier watch: an unpaid order cleared
        from modules import cashier_watch as _cw
        lines = order_lines(order_id)
        if lines:
            _cw.log_void("clear", lines)
    except Exception:
        pass
    _ = o
    return kot_ids


def mark_billed(order_id, total):
    """The bill (before payment) was printed: the table shows 'bill printed'."""
    db.execute("UPDATE rest_orders SET status=N'billed', bill_printed_at=GETDATE(), bill_total=?, "
               "updated_at=GETDATE() WHERE order_id=? AND status IN ('open','billed')",
               (round(_f(total), 2), int(order_id)))


def close(order_id, invoice_id, lines=None, price_incl=True, total=None):
    """Paid: the order points at its POS bill and the table is free."""
    o = get_order(order_id)
    if not o:
        return False
    if lines is not None:
        items = [ln for ln in lines if _is_item(ln)]
        db.execute("DELETE FROM rest_order_lines WHERE order_id=?", (int(order_id),))
        for i, ln in enumerate(items, 1):
            _insert_line(order_id, i, ln, price_incl)
    if total is None:
        total = db.execute_scalar("SELECT total_amount FROM sales_invoices WHERE invoice_id=?",
                                  (int(invoice_id),))
    db.execute("UPDATE rest_orders SET status=N'closed', invoice_id=?, closed_at=GETDATE(), closed_by=?, "
               "running_total=?, version=version+1, updated_at=GETDATE() WHERE order_id=?",
               (int(invoice_id), _user(), round(_f(total), 2), int(order_id)))
    try:        # A4 invoices and designer templates print the bill's notes
        db.execute("UPDATE sales_invoices SET notes_en=? WHERE invoice_id=? "
                   "AND ISNULL(notes_en,'')=''", (summary(o)[:1000], int(invoice_id)))
    except Exception:
        pass
    return True


def summary(o, short=False):
    """'Dine-in · Table 5 · 4 guests · Waiter: Ali' — order on one line."""
    if not o:
        return ""
    parts = ["%s #%s" % (o.get("order_type") or "", o.get("order_no") or "")]
    if o.get("table_name"):
        parts.append("Table %s" % o["table_name"])
    if o.get("guests") and not short:
        parts.append("%s guest%s" % (o["guests"], "" if _i(o["guests"]) == 1 else "s"))
    if o.get("waiter_name"):
        parts.append("Waiter: %s" % o["waiter_name"])
    if o.get("customer_name"):
        parts.append(o["customer_name"])
    if o.get("customer_phone"):
        parts.append(o["customer_phone"])
    if o.get("delivery_address") and not short:
        parts.append(o["delivery_address"])
    if o.get("driver_name") and not short:
        parts.append("Driver: %s" % o["driver_name"])
    return " · ".join(p for p in parts if p)


def receipt_rows(invoice_id):
    """[(label, value)] printed on the receipt of a paid order."""
    if not invoice_id or not on():
        return []
    try:
        o = order_of_invoice(invoice_id)
    except Exception:
        return []
    if not o:
        return []
    rows = [("Order", "#%s  %s" % (o.get("order_no"), o.get("order_type") or ""))]
    if o.get("table_name"):
        rows.append(("Table", o["table_name"]))
    if o.get("guests"):
        rows.append(("Guests", str(o["guests"])))
    if o.get("waiter_name"):
        rows.append(("Waiter", o["waiter_name"]))
    for lbl, key in (("Customer", "customer_name"), ("Phone", "customer_phone"),
                     ("Address", "delivery_address"), ("Driver", "driver_name")):
        v = _s(o.get(key), 500)
        while v:
            rows.append((lbl, v[:24]))
            v, lbl = v[24:].strip(), ""
    return rows


# ── kitchen: what is not sent yet ────────────────────────────
def sent_map(order_id):
    """{line_key: (qty the kitchen has, name, name_ar, unit, note, price)}."""
    out = {}
    rows = db.fetchall(
        "SELECT kl.product_id, kl.product_name, kl.product_name_ar, kl.unit_name, kl.kitchen_note, "
        "kl.quantity, kl.unit_price FROM rest_kot_lines kl JOIN rest_kots k ON k.kot_id=kl.kot_id "
        "WHERE k.order_id=? ORDER BY kl.kot_line_id", (int(order_id),)) or []
    for r in rows:
        k = (r.get("product_id"), str(r.get("unit_name") or "").strip().lower(),
             _s(r.get("kitchen_note")).lower())
        q, name, name_ar, unit, note, price = out.get(k, (0.0, r.get("product_name"),
                                                          r.get("product_name_ar"), r.get("unit_name"),
                                                          r.get("kitchen_note"), r.get("unit_price")))
        out[k] = (q + _f(r.get("quantity")), name, name_ar, unit, note, price)
    return out


def unsent(order_id, lines):
    """What the kitchen does not have yet, compared with the tickets sent
    before: [{product_id, product_name_en, unit_name, note, quantity,
    unit_price}] — quantity < 0 = CANCEL (lowered or taken off after it
    was sent). Items whose category is 'not sent to the kitchen' and the
    service charge are left out."""
    cur, first = OrderedDict(), {}
    for ln in lines or []:
        if not _is_item(ln) or not ln.get("product_id") or _f(ln.get("quantity")) < 0:
            continue
        k = line_key(ln)
        cur[k] = cur.get(k, 0.0) + _f(ln.get("quantity"))
        first.setdefault(k, ln)
    sent = sent_map(order_id) if order_id else {}
    routes = _routes([k[0] for k in list(cur.keys()) + list(sent.keys())])
    out = []
    for k in list(cur.keys()) + [k for k in sent.keys() if k not in cur]:
        if k[0] and routes.get(k[0]) is None:
            continue                             # not a kitchen item
        d = round(cur.get(k, 0.0) - sent.get(k, (0.0,))[0], 3)
        if abs(d) < 1e-9:
            continue
        if k in first:
            ln = first[k]
            q = _f(ln.get("quantity"))
            price = (_f(ln.get("line_total")) / q) if q else _f(ln.get("unit_price"))
            out.append({"product_id": k[0], "product_name_en": ln.get("product_name_en") or "",
                        "product_name_ar": ln.get("product_name_ar") or "",
                        "unit_name": ln.get("unit_name") or "", "note": _note(ln),
                        "quantity": d, "unit_price": round(price, 4)})
        else:
            _q, name, name_ar, unit, note, price = sent[k]
            out.append({"product_id": k[0], "product_name_en": name or "",
                        "product_name_ar": name_ar or "", "unit_name": unit or "",
                        "note": note or "", "quantity": d, "unit_price": _f(price)})
    out.sort(key=lambda x: x["quantity"] < 0)    # new items first, cancels after
    return out


def unsent_count(order_id, lines):
    return sum(1 for x in unsent(order_id, lines))


def send_to_kitchen(order_id, lines, note=None):
    """Make the kitchen tickets for what is not sent yet — one ticket per
    station. → [kot_id] (empty when the kitchen has everything)."""
    diff = unsent(order_id, lines)
    if not diff:
        return []
    routes = _routes([d["product_id"] for d in diff])
    groups = OrderedDict()
    for d in diff:
        st = routes.get(d["product_id"]) or default_station()
        key = st.get("station_id")
        groups.setdefault(key, (st, []))[1].append(d)
    ids = []
    with db.transaction():
        for _key, (st, items) in groups.items():
            no = _next_no("rest_kots", "kot_no", "kot_date")
            kid = int(db.execute_scalar(
                "INSERT INTO rest_kots (kot_no, order_id, station_id, station_name, status, sent_by, "
                "kot_note) OUTPUT INSERTED.kot_id VALUES (?,?,?,?, N'new', ?, ?)",
                (no, int(order_id), st.get("station_id"), _s(st.get("station_name"), 100) or "Kitchen",
                 _user(), _s(note, 200) or None)))
            for d in items:
                db.execute("INSERT INTO rest_kot_lines (kot_id, product_id, product_name, product_name_ar, "
                           "unit_name, quantity, unit_price, kitchen_note) VALUES (?,?,?,?,?,?,?,?)",
                           (kid, d["product_id"], _s(d["product_name_en"], 200) or "Item",
                            _s(d.get("product_name_ar"), 200) or None, _s(d.get("unit_name"), 50) or None,
                            d["quantity"], d.get("unit_price"), _s(d.get("note"), 200) or None))
            ids.append(kid)
    return ids


# ── kitchen tickets ──────────────────────────────────────────
_KOT_SQL = ("SELECT k.*, o.order_no, o.order_type, o.table_id, o.guests, o.waiter_name, o.customer_name, "
            "o.customer_phone, o.status AS order_status, ISNULL(t.table_name,'') AS table_name, "
            "DATEDIFF(minute, k.sent_at, GETDATE()) AS minutes "
            "FROM rest_kots k JOIN rest_orders o ON o.order_id=k.order_id "
            "LEFT JOIN rest_tables t ON t.table_id=o.table_id ")


def kot(kot_id):
    r = db.fetchone(_KOT_SQL + "WHERE k.kot_id=?", (int(kot_id),))
    if not r:
        return None
    r = dict(r)
    r["lines"] = kot_lines(kot_id)
    return r


def kot_lines(kot_id):
    return [dict(x) for x in (db.fetchall("SELECT * FROM rest_kot_lines WHERE kot_id=? "
                                          "ORDER BY CASE WHEN quantity<0 THEN 1 ELSE 0 END, kot_line_id",
                                          (int(kot_id),)) or [])]


def kots(statuses=("new", "preparing", "ready"), station_id=None, today_only=False, order_id=None,
         limit=200):
    """Tickets with their lines, oldest first."""
    where, p = [], []
    if statuses:
        where.append("k.status IN (%s)" % ",".join("?" * len(statuses)))
        p += list(statuses)
    if station_id:
        where.append("k.station_id=?")
        p.append(int(station_id))
    if today_only:
        where.append("k.kot_date=CAST(GETDATE() AS DATE)")
    if order_id:
        where.append("k.order_id=?")
        p.append(int(order_id))
    sql = _KOT_SQL.replace("SELECT ", "SELECT TOP %d " % int(limit), 1)
    sql += ("WHERE " + " AND ".join(where) if where else "") + " ORDER BY k.sent_at, k.kot_id"
    try:
        rows = [dict(r) for r in (db.fetchall(sql, tuple(p)) or [])]
    except Exception:
        return []
    if rows:
        ids = [r["kot_id"] for r in rows]
        by = defaultdict(list)
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            for ln in db.fetchall("SELECT * FROM rest_kot_lines WHERE kot_id IN (%s) ORDER BY "
                                  "CASE WHEN quantity<0 THEN 1 ELSE 0 END, kot_line_id"
                                  % ",".join("?" * len(part)), tuple(part)) or []:
                by[ln["kot_id"]].append(dict(ln))
        for r in rows:
            r["lines"] = by.get(r["kot_id"], [])
    return rows


def is_cancel_only(k):
    lines = k.get("lines") if isinstance(k, dict) else None
    return bool(lines) and all(_f(x.get("quantity")) < 0 for x in lines)


def set_kot_status(kot_id, status):
    if status not in KOT_FLOW:
        raise ValueError("Unknown status '%s'." % status)
    stamp = {"preparing": "started_at", "ready": "ready_at", "served": "served_at"}.get(status)
    db.execute("UPDATE rest_kots SET status=?%s WHERE kot_id=?"
               % ((", %s=ISNULL(%s, GETDATE())" % (stamp, stamp)) if stamp else ""),
               (status, int(kot_id)))


def bump(kot_id):
    """Next step: new → preparing → ready → served. A ticket that only
    cancels items goes straight to served (the kitchen has seen it).
    → the new status."""
    k = kot(kot_id)
    if not k:
        return None
    st = k.get("status") or "new"
    if is_cancel_only(k) or st not in KOT_FLOW:
        nxt = "served"
    else:
        nxt = KOT_FLOW[min(KOT_FLOW.index(st) + 1, len(KOT_FLOW) - 1)]
    set_kot_status(kot_id, nxt)
    return nxt


def _who(user_id):
    if not user_id:
        return ""
    try:
        r = db.fetchone("SELECT username, full_name_en FROM users WHERE user_id=?", (int(user_id),))
        return (r or {}).get("full_name_en") or (r or {}).get("username") or ""
    except Exception:
        return ""


def _when(v):
    try:
        from config import settings as cfg
        return cfg.fmt_datetime(v)
    except Exception:
        return str(v or "")[:16]


def _qty(q):
    return ("%.3f" % abs(_f(q))).rstrip("0").rstrip(".")


def kot_head(k):
    """'Table 5' / 'TAKEAWAY #12' / 'DELIVERY #13' — the big line."""
    if k.get("table_name"):
        return "Table %s" % k["table_name"]
    return "%s #%s" % (str(k.get("order_type") or "Order").upper(), k.get("order_no") or "")


def _kot_entries(k):
    """What a ticket says, as print entries (shared by text and PDF)."""
    reprint = _i(k.get("print_count")) > 0
    e = [("c", "KOT %s" % k.get("kot_no"), 16, True),
         ("c", str(k.get("station_name") or "Kitchen").upper(), 10, True)]
    if reprint:
        e.append(("c", "** REPRINT **", 9, True))
    if k.get("kot_note"):
        e.append(("c", str(k["kot_note"]), 11, True))
    e.append(("c", kot_head(k), 15, True))
    sub = ["%s #%s" % (k.get("order_type") or "", k.get("order_no") or "")]
    if k.get("guests"):
        sub.append("%s guests" % k["guests"])
    e.append(("c", "  ·  ".join(sub), 9, False))
    if k.get("waiter_name"):
        e.append(("c", "Waiter: %s" % k["waiter_name"], 9, False))
    if k.get("customer_name"):
        e.append(("c", "Customer: %s" % k["customer_name"], 9, False))
    e.append(("c", _when(k.get("sent_at")), 8, False))
    e.append(("rule",))
    for ln in k.get("lines") or []:
        q = _f(ln.get("quantity"))
        unit = str(ln.get("unit_name") or "").strip()
        name = str(ln.get("product_name") or "")
        if unit and unit.lower() not in ("unit", "pcs", "pc", "piece", "nos"):
            name += " (%s)" % unit
        if q < 0:
            e.append(("l", "CANCEL  %s x %s" % (_qty(q), name), 12, True))
        else:
            e.append(("l", "%s  x  %s" % (_qty(q), name), 12, True))
        if ln.get("product_name_ar"):
            e.append(("ar", str(ln["product_name_ar"]), 10))
        if ln.get("kitchen_note"):
            e.append(("l", "     * %s" % ln["kitchen_note"], 10, False))
    e.append(("rule",))
    who = _who(k.get("sent_by"))
    if who:
        e.append(("c", "Sent by: %s" % who, 8, False))
    return e


def kot_text(kot_id, width=None):
    """The ticket as plain text (preview, tests)."""
    k = kot(kot_id) if not isinstance(kot_id, dict) else kot_id
    if not k:
        return ""
    w = int(width or (32 if _i(k.get("paper_mm") or _station_paper(k)) == 58 else 42))
    return _entries_text(_kot_entries(k), w)


def _station_paper(k):
    sid = k.get("station_id")
    if sid:
        try:
            r = db.fetchone("SELECT paper_mm FROM rest_stations WHERE station_id=?", (int(sid),))
            if r and r.get("paper_mm"):
                return _i(r["paper_mm"], 80)
        except Exception:
            pass
    return _i(setting("rest_kot_paper"), 80)


def _entries_text(entries, w):
    out = []
    for en in entries:
        kind = en[0]
        if kind == "rule":
            out.append("-" * w)
        elif kind == "c":
            out.append(str(en[1])[:w].center(w).rstrip())
        elif kind == "lr":
            left, right = str(en[1]), str(en[2])
            room = max(1, w - len(right) - 1)
            out.append(left[:room].ljust(room) + " " + right)
        elif kind == "ar":
            out.append(("  " + str(en[1]))[:w])
        else:
            text = str(en[1])
            first = True
            while text:
                out.append((text if first else "    " + text)[:w])
                text = text[w if first else w - 4:]
                first = False
    return "\n".join(out) + "\n"


def _roll_pdf(entries, path, width_mm=80, _height=None):
    """Draw print entries on a 58 / 80 mm roll; the page is exactly as
    long as the text (measured first, like the thermal receipt)."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.pdfmetrics import stringWidth
    import io
    try:
        from modules.pdf_invoice import _shape_arabic, _register_fonts
        _register_fonts()
        from modules import pdf_invoice as _pi
        AR = _pi._AR_FONT
    except Exception:
        AR = None
        _shape_arabic = None
    width = (58 if _i(width_mm, 80) == 58 else 80) * mm
    measuring = _height is None
    height = 2000 * mm if measuring else _height
    c = canvas.Canvas(io.BytesIO() if measuring else path, pagesize=(width, height))
    y = height - 5 * mm
    left, right = 3 * mm, width - 3 * mm
    room = right - left

    def font(bold):
        return "Helvetica-Bold" if bold else "Helvetica"

    def wrap(text, fnt, size, indent=0.0):
        words, lines, cur = str(text).split(" "), [], ""
        for wd in words:
            t = (cur + " " + wd) if cur else wd
            if stringWidth(t, fnt, size) <= room - (indent if lines else 0):
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        return lines or [""]

    for en in entries:
        kind = en[0]
        if kind == "rule":
            c.setDash(2, 2)
            c.line(left, y + 1 * mm, right, y + 1 * mm)
            c.setDash()
            y -= 3 * mm
            continue
        if kind == "gap":
            y -= en[1] * mm
            continue
        if kind == "ar":
            if AR and _shape_arabic:
                c.setFont(AR, en[2])
                c.drawRightString(right, y, _shape_arabic(str(en[1])))
                y -= en[2] * 0.42 * mm + 1.6 * mm
            continue
        size, bold = en[-2], en[-1]
        fnt = font(bold)
        step = size * 0.42 * mm + 1.6 * mm
        if kind == "lr":
            c.setFont(fnt, size)
            c.drawString(left, y, str(en[1]))
            c.drawRightString(right, y, str(en[2]))
            y -= step
        elif kind == "c":
            for part in wrap(en[1], fnt, size):
                c.setFont(fnt, size)
                c.drawCentredString(width / 2, y, part)
                y -= step
        else:
            ind = 6 * mm
            for i, part in enumerate(wrap(en[1], fnt, size, ind)):
                c.setFont(fnt, size)
                c.drawString(left + (ind if i else 0), y, part)
                y -= step
    c.showPage()
    c.save()
    if measuring:
        return _roll_pdf(entries, path, width_mm, _height=height - y + 4 * mm)
    return path


def _tmp(name):
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(name))
    return os.path.join(tempfile.gettempdir(), "daybill_%s.pdf" % safe)


def kot_pdf(kot_id, width_mm=None):
    k = kot(kot_id) if not isinstance(kot_id, dict) else kot_id
    if not k:
        return None
    w = width_mm or _station_paper(k)
    return _roll_pdf(_kot_entries(k), _tmp("kot_%s_%s" % (k.get("kot_no"), k.get("kot_id"))), w)


def kot_printer(k):
    """(printer name or '', paper mm, copies) for a ticket."""
    st = None
    if k.get("station_id"):
        try:
            st = db.fetchone("SELECT * FROM rest_stations WHERE station_id=?", (int(k["station_id"]),))
        except Exception:
            st = None
    printer = _s((st or {}).get("printer_name")) or _s(setting("rest_kitchen_printer"))
    paper = _i((st or {}).get("paper_mm"), 0) or _i(setting("rest_kot_paper"), 80)
    copies = max(1, _i((st or {}).get("copies"), 1))
    return printer, paper, copies


def print_kot(kot_id):
    """Print one ticket: the station's printer, else the default kitchen
    printer, else the PDF opens on the screen. → (ok, message)."""
    k = kot(kot_id)
    if not k:
        return False, "Ticket not found."
    printer, paper, copies = kot_printer(k)
    path = kot_pdf(k, paper)
    from modules import printer_service as ps
    if printer:
        ok = ps.print_pdf(path, printer, copies=copies)
        msg = ("KOT %s sent to %s." % (k["kot_no"], printer) if ok else
               "KOT %s could not be printed on %s. %s" % (k["kot_no"], printer, ps.last_error))
    else:
        ok = ps.open_file(path)
        msg = ("No kitchen printer is set (Restaurant Setup ▸ Kitchen) — KOT %s opened as a PDF."
               % k["kot_no"])
    try:
        db.execute("UPDATE rest_kots SET print_count=print_count+1 WHERE kot_id=?", (int(kot_id),))
    except Exception:
        pass
    return ok, msg


# ── the bill before payment ──────────────────────────────────
def _company():
    try:
        return dict(db.fetchone("SELECT TOP 1 * FROM company ORDER BY company_id") or {})
    except Exception:
        return {}


def _prebill_entries(o, lines, totals):
    comp = _company()
    try:
        from modules import country
        tax = country.tax_name()
    except Exception:
        tax = "VAT"
    e = [("c", comp.get("company_name_en") or "", 12, True)]
    if comp.get("company_name_ar"):
        e.append(("ar_c", comp["company_name_ar"], 10))
    e += [("c", "BILL  -  NOT PAID YET", 11, True), ("rule",)]
    e.append(("lr", "Order", "#%s  %s" % (o.get("order_no"), o.get("order_type") or ""), 8, False))
    if o.get("table_name"):
        e.append(("lr", "Table", o["table_name"], 8, False))
    if o.get("guests"):
        e.append(("lr", "Guests", str(o["guests"]), 8, False))
    if o.get("waiter_name"):
        e.append(("lr", "Waiter", o["waiter_name"], 8, False))
    if o.get("customer_name"):
        e.append(("lr", "Customer", o["customer_name"], 8, False))
    if o.get("customer_phone"):
        e.append(("lr", "Phone", o["customer_phone"], 8, False))
    e.append(("lr", "Date", _when(datetime.now()), 8, False))
    e.append(("rule",))
    for ln in lines:
        if _f(ln.get("quantity")) == 0:
            continue
        e.append(("l", str(ln.get("product_name_en") or ""), 8, False))
        e.append(("lr", "   %s x %s" % (_qty(ln.get("quantity")), money(ln.get("unit_price"), sym=False)),
                  money(ln.get("line_total"), sym=False), 8, False))
        if ln.get("note"):
            e.append(("l", "   * %s" % ln["note"], 7, False))
    e.append(("rule",))
    e.append(("lr", "Total before %s" % tax, money(totals.get("net"), sym=False), 8, False))
    e.append(("lr", tax, money(totals.get("vat"), sym=False), 8, False))
    e.append(("lr", "TOTAL", money(totals.get("total")), 11, True))
    e.append(("rule",))
    e.append(("c", "This is not a tax invoice.", 8, False))
    e.append(("c", "The tax invoice is printed when you pay.", 7, False))
    return e


def prebill_text(o, lines, totals, width=42):
    e = [x if x[0] != "ar_c" else ("c", x[1], x[2], False) for x in _prebill_entries(o, lines, totals)]
    return _entries_text(e, width)


def prebill_pdf(o, lines, totals, width_mm=None):
    if width_mm is None:
        try:
            from config import settings as cfg
            width_mm = 58 if str(cfg.get("pos_paper_size", "80mm")).startswith("58") else 80
        except Exception:
            width_mm = 80
    e = [x if x[0] != "ar_c" else ("ar", x[1], x[2]) for x in _prebill_entries(o, lines, totals)]
    return _roll_pdf(e, _tmp("bill_%s_%s" % (o.get("order_no"), o.get("order_id"))), width_mm)
