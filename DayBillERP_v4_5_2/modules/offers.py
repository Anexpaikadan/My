# ============================================================
# DayBill ERP - Offers & Promotions engine
# ------------------------------------------------------------
# Offer types (offers.offer_type):
#   percent  : −X %  (50 % = "Half price")           offer_value = X
#   price    : special price per item                 offer_items.offer_price
#   amount   : SAR X off each item                    offer_value = X
#   buy_get  : buy X get Y free (or Y at get_pct % off) buy_qty, get_qty, get_pct
# When: start_at … end_at, days of the week (days_mask Mon..Sun) and an
# optional daily time window (time_from–time_to, may pass midnight).
# Where: for_pos (POS) / for_sales (Sales invoice).
#
# The engine never changes the item's price: it gives the bill line a
# DISCOUNT (discount_amount) plus offer_id / offer_text, so the bill
# shows "price, offer, you saved" and VAT is worked out on what the
# customer really pays.
# ============================================================

import time as _time
from datetime import datetime, date

from config import settings as cfg

TYPES = ("percent", "price", "amount", "buy_get")
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

_CACHE = {"at": 0.0, "rows": None}
_TTL = 15.0                       # seconds — new / edited offers show up fast


def _db():
    from config.database import db
    return db


def tables_ready():
    try:
        _db().fetchone("SELECT TOP 1 offer_id FROM offers")
        return True
    except Exception:
        return False


def invalidate():
    _CACHE["at"] = 0.0
    _CACHE["rows"] = None


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def to_dt(v):
    """DATETIME from the DB (datetime, date or text) → datetime / None."""
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    s = str(v).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    return None


# ── loading ──────────────────────────────────────────────────
def load_all(include_items=True):
    """Every offer (newest first) with its items."""
    db = _db()
    try:
        offers = [dict(r) for r in db.fetchall(
            "SELECT * FROM offers ORDER BY offer_id DESC") or []]
        offers = [o for o in offers if o.get("offer_id") is not None]
    except Exception:
        return []
    if include_items and offers:
        try:
            items = [dict(r) for r in db.fetchall(
                "SELECT oi.*, p.product_code, p.product_name_en, p.product_name_ar, "
                "p.unit_price AS base_price, p.vat_category_id "
                "FROM offer_items oi LEFT JOIN products p ON p.product_id = oi.product_id "
                "ORDER BY oi.offer_item_id") or []]
        except Exception:
            items = []
        by = {}
        for it in items:
            by.setdefault(it.get("offer_id"), []).append(it)
        for o in offers:
            o["items"] = by.get(o.get("offer_id"), [])
    return offers


def _live_rows():
    now = _time.time()
    if _CACHE["rows"] is None or now - _CACHE["at"] > _TTL:
        rows = [o for o in load_all() if o.get("is_active")]
        _CACHE["rows"] = rows
        _CACHE["at"] = now
    return _CACHE["rows"]


# ── when is an offer on? ─────────────────────────────────────
def is_live(o, now=None):
    now = now or datetime.now()
    if not o.get("is_active"):
        return False
    st, en = to_dt(o.get("start_at")), to_dt(o.get("end_at"))
    if st and now < st:
        return False
    if en and now > en:
        return False
    mask = str(o.get("days_mask") or "1111111").ljust(7, "1")
    if mask[now.weekday()] != "1":
        return False
    tf, tt = (o.get("time_from") or "").strip(), (o.get("time_to") or "").strip()
    if tf and tt and tf != tt:
        t = now.strftime("%H:%M")
        if tf < tt:
            if not (tf <= t < tt):
                return False
        elif not (t >= tf or t < tt):        # e.g. 22:00 – 02:00
            return False
    return True


def status(o, now=None):
    """(code, text) for the offers list."""
    now = now or datetime.now()
    if not o.get("is_active"):
        return "paused", "⏸ Paused"
    st, en = to_dt(o.get("start_at")), to_dt(o.get("end_at"))
    if en and now > en:
        return "ended", "⛔ Ended"
    if st and now < st:
        return "soon", "🕒 Starts " + st.strftime("%d/%m %H:%M")
    if is_live(o, now):
        return "live", "🟢 Running now"
    return "wait", "🕒 Not at this time / day"


# ── labels ───────────────────────────────────────────────────
def _num(x):
    x = _f(x)
    return ("%d" % x) if abs(x - round(x)) < 1e-9 else ("%g" % round(x, 3))


def label(o, item=None):
    """Short text on the bill line / receipt: −20%, HALF PRICE, …"""
    t = o.get("offer_type")
    v = _f(o.get("offer_value"))
    if t == "percent":
        return "HALF PRICE" if abs(v - 50) < 1e-9 else "-%s%%" % _num(v)
    if t == "price":
        p = _f((item or {}).get("offer_price"))
        return "OFFER PRICE %.2f" % p if p else "OFFER PRICE"
    if t == "amount":
        return "%.2f OFF" % v
    if t == "buy_get":
        x, y, pct = _num(o.get("buy_qty")), _num(o.get("get_qty")), _f(o.get("get_pct"), 100)
        tail = "FREE" if pct >= 99.999 else ("HALF" if abs(pct - 50) < 1e-9 else "%s%% OFF" % _num(pct))
        return "BUY %s GET %s %s" % (x, y, tail)
    return "OFFER"


def label_ar(o, item=None):
    t = o.get("offer_type")
    v = _f(o.get("offer_value"))
    if t == "percent":
        return "نصف السعر" if abs(v - 50) < 1e-9 else "خصم %s٪" % _num(v)
    if t == "price":
        p = _f((item or {}).get("offer_price"))
        return "سعر العرض %.2f" % p if p else "سعر العرض"
    if t == "amount":
        return "خصم %.2f ريال" % v
    if t == "buy_get":
        x, y, pct = _num(o.get("buy_qty")), _num(o.get("get_qty")), _f(o.get("get_pct"), 100)
        tail = "مجاناً" if pct >= 99.999 else ("بنصف السعر" if abs(pct - 50) < 1e-9 else "بخصم %s٪" % _num(pct))
        return "اشترِ %s واحصل على %s %s" % (x, y, tail)
    return "عرض"


def when_text(o):
    """'03/10 08:00 → 10/10 23:59 · Fri Sat · 16:00–20:00'"""
    parts = []
    st, en = to_dt(o.get("start_at")), to_dt(o.get("end_at"))
    if st or en:
        yr = datetime.now().year
        whole = (not st or st.strftime("%H:%M") == "00:00") and \
                (not en or en.strftime("%H:%M") in ("23:59", "00:00"))

        def f(d):
            fmt = "%d/%m" if d.year == yr else "%d/%m/%Y"
            return d.strftime(fmt if whole else fmt + " %H:%M")
        parts.append("%s → %s" % (f(st) if st else "now", f(en) if en else "no end"))
    mask = str(o.get("days_mask") or "1111111").ljust(7, "1")
    if mask != "1111111":
        parts.append(" ".join(d for d, m in zip(DAY_NAMES, mask) if m == "1") or "no day")
    tf, tt = o.get("time_from"), o.get("time_to")
    if tf and tt and tf != tt:
        parts.append("%s–%s" % (tf, tt))
    return "  ·  ".join(parts) or "Always"


# ── the maths ────────────────────────────────────────────────
def _shop_incl():
    return str(cfg.get("sales_price_tax_mode", "inclusive")).lower() == "inclusive"


def _to_line_mode(amount, line_incl, rate):
    """An amount typed in the shop's price mode (Settings ▸ Tax), expressed
    the way this bill line holds its price (with / without VAT)."""
    if not rate:
        return amount
    shop = _shop_incl()
    if shop == bool(line_incl):
        return amount
    return amount / (1 + rate / 100.0) if shop else amount * (1 + rate / 100.0)


def free_units(qty, buy, get):
    """Buy X get Y: how many of `qty` are the 'get' (free / cheaper) ones.
    buy 1 get 1, qty 3 → 1 · qty 4 → 2 · buy 1 get 2, qty 3 → 2."""
    qty, buy, get = _f(qty), _f(buy), _f(get)
    if qty <= 0 or buy <= 0 or get <= 0:
        return 0.0
    group = buy + get
    full = int(qty // group + 1e-9)
    rest = qty - full * group
    return full * get + max(0.0, min(get, rest - buy))


def line_discount(o, item, qty, price, line_incl=True, rate=0.0):
    """Discount (in the line's own price mode) this offer gives a bill line
    of `qty` × `price`. 0 when it does not apply."""
    qty, price = _f(qty), _f(price)
    mag = abs(qty)
    if mag <= 0 or price <= 0:
        return 0.0
    if _f(o.get("min_qty")) > 0 and mag + 1e-9 < _f(o.get("min_qty")):
        return 0.0
    t = o.get("offer_type")
    if t == "percent":
        d = mag * price * min(100.0, max(0.0, _f(o.get("offer_value")))) / 100.0
    elif t == "price":
        sp = _to_line_mode(_f(item.get("offer_price")), line_incl, rate)
        d = mag * (price - sp) if 0 <= sp < price else 0.0
    elif t == "amount":
        a = _to_line_mode(_f(o.get("offer_value")), line_incl, rate)
        d = mag * min(price, max(0.0, a))
    elif t == "buy_get":
        if qty < 0:
            return 0.0                    # a returned item gets its paid price back
        n = free_units(mag, o.get("buy_qty"), o.get("get_qty"))
        d = n * price * min(100.0, max(0.0, _f(o.get("get_pct"), 100))) / 100.0
    else:
        d = 0.0
    return round(max(0.0, d), 4)


def candidates(product_id, unit_name, channel="pos", now=None):
    """[(offer, item)] live offers that cover this product + unit."""
    if not product_id:
        return []
    now = now or datetime.now()
    key = "for_pos" if channel == "pos" else "for_sales"
    out = []
    for o in _live_rows():
        if not o.get(key) or not is_live(o, now):
            continue
        for it in o.get("items", []):
            if it.get("product_id") != product_id:
                continue
            un = (it.get("unit_name") or "").strip()
            if un and unit_name and un.lower() != str(unit_name).strip().lower():
                continue
            out.append((o, it))
    return out


def best(product_id, unit_name, qty, price, channel="pos", line_incl=True, rate=0.0,
         now=None):
    """The offer that saves the customer most on this line:
    {offer_id, text, discount} or None."""
    top = None
    for o, it in candidates(product_id, unit_name, channel, now):
        d = line_discount(o, it, qty, price, line_incl, rate)
        if d > 0.004 and (top is None or d > top["discount"]):
            top = {"offer_id": o["offer_id"], "text": label(o, it),
                   "text_ar": label_ar(o, it), "name": o.get("offer_name", ""),
                   "discount": d}
    return top


def hint(product_id, unit_name, qty, channel="pos", now=None):
    """'Add 1 more — it is FREE' for buy-X-get-Y when the customer is
    one step away from the free item (POS status bar)."""
    for o, it in candidates(product_id, unit_name, channel, now):
        if o.get("offer_type") != "buy_get":
            continue
        q = _f(qty)
        if q <= 0:
            continue
        buy, get = _f(o.get("buy_qty")), _f(o.get("get_qty"))
        nxt = free_units(q + 1, buy, get) - free_units(q, buy, get)
        if nxt > 0:
            return "🎁 %s — add 1 more, it is %s" % (
                label(o, it), "FREE" if _f(o.get("get_pct"), 100) >= 99.999 else "on offer")
    return ""


def apply_to_line(ln, channel="pos", qty_key="quantity", price_key="unit_price",
                  unit_key="unit_name", line_incl=True, rate=0.0, now=None):
    """Set the line's offer discount (or take an old one off). A line the
    user changed by hand (ln['offer_off']) keeps its own discount."""
    if ln.get("offer_off"):
        return ln
    o = None
    try:
        o = best(ln.get("product_id"), ln.get(unit_key), ln.get(qty_key),
                 ln.get(price_key), channel, line_incl, rate, now)
    except Exception:
        o = None
    if o:
        disc = o["discount"]
        if _f(ln.get(qty_key)) < 0:
            disc = -disc                  # a RETURN line: discount counts the other way
        ln["discount_amount"] = round(disc, 4)
        ln["offer_id"] = o["offer_id"]
        ln["offer_text"] = o["text"][:80]
    elif ln.get("offer_id"):
        ln["discount_amount"] = 0.0
        ln["offer_id"] = None
        ln["offer_text"] = ""
    return ln


# ── saving ───────────────────────────────────────────────────
def save(offer, items, user=None):
    """Insert / update one offer and its items. Returns offer_id."""
    db = _db()
    o = dict(offer)
    cols = ["offer_name", "offer_name_ar", "offer_type", "offer_value", "buy_qty",
            "get_qty", "get_pct", "min_qty", "start_at", "end_at", "days_mask",
            "time_from", "time_to", "for_pos", "for_sales", "is_active", "notes"]
    dflt = {"offer_value": 0, "buy_qty": 0, "get_qty": 0, "get_pct": 100, "min_qty": 0,
            "days_mask": "1111111", "for_pos": 1, "for_sales": 1, "is_active": 1}
    vals = [o.get(c) if o.get(c) is not None else dflt.get(c) for c in cols]
    for i, c in enumerate(cols):
        if c in ("start_at", "end_at") and isinstance(vals[i], datetime):
            vals[i] = vals[i].strftime("%Y-%m-%d %H:%M:%S")
        if c in ("for_pos", "for_sales", "is_active"):
            vals[i] = 1 if vals[i] else 0
    oid = o.get("offer_id")
    if oid:
        db.execute("UPDATE offers SET " + ", ".join(f"{c}=?" for c in cols)
                   + ", updated_at=GETDATE() WHERE offer_id=?", tuple(vals) + (oid,))
        db.execute("DELETE FROM offer_items WHERE offer_id=?", (oid,))
    else:
        db.execute("INSERT INTO offers (" + ", ".join(cols) + ", created_by) VALUES ("
                   + ", ".join("?" for _ in cols) + ", ?)", tuple(vals) + (user,))
        oid = db.execute_scalar("SELECT MAX(offer_id) FROM offers")
    for it in items:
        db.execute("INSERT INTO offer_items (offer_id, product_id, unit_name, offer_price) "
                   "VALUES (?,?,?,?)",
                   (oid, it["product_id"], (it.get("unit_name") or None),
                    it.get("offer_price")))
    invalidate()
    return oid


def set_active(offer_id, on):
    _db().execute("UPDATE offers SET is_active=?, updated_at=GETDATE() WHERE offer_id=?",
                  (1 if on else 0, offer_id))
    invalidate()


def delete(offer_id):
    db = _db()
    db.execute("DELETE FROM offer_items WHERE offer_id=?", (offer_id,))
    db.execute("DELETE FROM offers WHERE offer_id=?", (offer_id,))
    invalidate()


def sales_summary(offer_id):
    """(bills, qty, discount given) for one offer from saved sales."""
    try:
        r = _db().fetchone(
            "SELECT COUNT(DISTINCT l.invoice_id) AS bills, "
            "COALESCE(SUM(l.quantity),0) AS qty, "
            "COALESCE(SUM(l.discount_amount),0) AS disc "
            "FROM sales_invoice_lines l JOIN sales_invoices i ON i.invoice_id=l.invoice_id "
            "WHERE l.offer_id=? AND i.invoice_status<>'cancelled'", (offer_id,)) or {}
        return int(r.get("bills") or 0), _f(r.get("qty")), _f(r.get("disc"))
    except Exception:
        return 0, 0.0, 0.0
