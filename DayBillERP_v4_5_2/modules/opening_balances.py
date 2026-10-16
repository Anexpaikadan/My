# ============================================================
# DayBill ERP - Opening balances in the books
# ------------------------------------------------------------
# Everything a shop brings in on the day it starts with DayBill, posted
# against 3400 Opening Balance Equity, dated the OPENING DATE
# (Accounts ▸ Opening Balances; default = first day of the financial
# year):
#
#   account opening        Dr / Cr the account   | Opening Balance Equity
#   customer owes us       Dr customer ledger    | Cr Opening Balance Equity
#   we owe a supplier      Dr Opening Bal. Eq.   | Cr supplier ledger
#   opening stock          Dr Inventory          | Cr Opening Balance Equity
#                          (+ the stock quantity and the stock card)
#
# Changing an amount re-posts it (the new entry is made first, then
# the old one removed — nothing is lost if posting fails).
# ============================================================

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db, atomic

last_error = ""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _date():
    """First day of the current financial year."""
    try:
        from config import settings as cfg
        return cfg.fiscal_year_bounds()[0].isoformat()
    except Exception:
        return date(date.today().year, 1, 1).isoformat()


def opening_date():
    """The date opening balances are posted on (Settings key opening_date,
    default the first day of the financial year)."""
    try:
        from config import settings as cfg
        s = str(cfg.get("opening_date", "") or "").strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
    except Exception:
        pass
    return _date()


@atomic
def set_opening_date(d):
    """Save a new opening date and move every opening entry to it."""
    from config import settings as cfg
    d = str(d).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        raise ValueError("Use the date format YYYY-MM-DD.")
    cfg.set("opening_date", d)
    try:
        cfg.save_settings()
    except Exception:
        pass
    try:
        db.execute("UPDATE journal_entries SET entry_date=? WHERE source_type IN "
                   "('opening_accounts','opening_stock','opening_customer','opening_supplier')",
                   (d,))
        db.execute("UPDATE inventory_transactions SET txn_date=? WHERE txn_type='opening'", (d,))
    except Exception:
        pass
    return d


def _journal_ids(source_type, source_id):
    try:
        return [r["journal_id"] for r in db.fetchall(
            "SELECT journal_id FROM journal_entries WHERE source_type=? AND source_id=?",
            (source_type, int(source_id))) or []]
    except Exception:
        return []


def _delete_journals(ids):
    for jid in ids:
        for sql in ("DELETE FROM journal_lines WHERE journal_id=?",
                    "DELETE FROM journal_entries WHERE journal_id=?"):
            try:
                db.execute(sql, (jid,))
            except Exception:
                pass


def _remove(source_type, source_id):
    _delete_journals(_journal_ids(source_type, source_id))


def _replace(source_type, source_id, post):
    """Post the new entry first, then delete the old ones. post() returns
    journal_id or None (None with nothing to post = just remove)."""
    old = _journal_ids(source_type, source_id)
    jid = post()
    if jid or not last_error:
        _delete_journals([j for j in old if j != jid])
    return jid


# ════════════════════════════════════════════════════════════
#  Customers / suppliers
# ════════════════════════════════════════════════════════════
@atomic
def post_party(party_type, party_id):
    """(Re)post one customer's / supplier's opening balance.
    Returns journal_id, or None when there is nothing to post."""
    global last_error
    from modules import posting
    from modules import account_defaults as ad
    last_error = ""
    st = f"opening_{party_type}"
    tbl, col = (("customers", "customer") if party_type == "customer"
                else ("suppliers", "supplier"))
    try:
        row = db.fetchone(f"SELECT * FROM {tbl} WHERE {col}_id=?", (party_id,)) or {}
    except Exception:
        return None
    amt = round(_f(row.get("opening_balance")), 2)

    def post():
        global last_error
        if abs(amt) < 0.005 or not posting.enabled():
            return None
        party_acc = posting.ensure_party_account(party_type, party_id)
        eq = ad.opening_equity()
        if not party_acc or not eq:
            last_error = "Opening Balance Equity account (3400) not found."
            return None
        name = row.get(f"{col}_name_en") or ""
        if party_type == "customer":          # they owe us (negative = advance)
            lines = [(party_acc, max(amt, 0), max(-amt, 0), "Opening balance"),
                     (eq, max(-amt, 0), max(amt, 0), f"Opening balance – {name}")]
        else:                                 # we owe them
            lines = [(eq, max(amt, 0), max(-amt, 0), f"Opening balance – {name}"),
                     (party_acc, max(-amt, 0), max(amt, 0), "Opening balance")]
        jid = posting.post_journal(opening_date(), f"Opening balance – {name}"[:200], lines,
                                   st, int(party_id), reference=row.get(f"{col}_code"))
        if not jid:
            last_error = posting.last_error
        return jid
    return _replace(st, party_id, post)


def party_rows(party_type, search=""):
    """[{id, code, name, phone, opening}] for the Opening Balances page."""
    tbl, col = (("customers", "customer") if party_type == "customer"
                else ("suppliers", "supplier"))
    try:
        rows = db.fetchall(f"SELECT * FROM {tbl} ORDER BY {col}_code") or []
    except Exception:
        return []
    q = (search or "").strip().lower()
    out = []
    for r in rows:
        code = str(r.get(f"{col}_code") or "")
        if code.upper() in ("CASH", "WALKIN", "WALK-IN", "CASH-001"):
            continue                          # the cash customer has no balance
        name = r.get(f"{col}_name_en") or ""
        if q and q not in (code + " " + name + " " + str(r.get("phone") or "")).lower():
            continue
        out.append({"id": r.get(f"{col}_id"), "code": code, "name": name,
                    "phone": r.get("phone") or "", "opening": round(_f(r.get("opening_balance")), 2),
                    "active": r.get("is_active", 1) in (1, True, None)})
    return out


@atomic
def set_party_opening(party_type, party_id, amount):
    """Change a customer's / supplier's opening balance and re-post it."""
    tbl, col = (("customers", "customer") if party_type == "customer"
                else ("suppliers", "supplier"))
    db.execute(f"UPDATE {tbl} SET opening_balance=? WHERE {col}_id=?",
               (round(_f(amount), 2), party_id))
    return post_party(party_type, party_id)


# ════════════════════════════════════════════════════════════
#  Opening stock
# ════════════════════════════════════════════════════════════
def opening_qty(product_id):
    try:
        return round(_f(db.execute_scalar(
            "SELECT SUM(ISNULL(qty_in_base,0) - ISNULL(qty_out_base,0)) FROM "
            "inventory_transactions WHERE product_id=? AND txn_type='opening'",
            (product_id,))), 4)
    except Exception:
        return 0.0


def _opening_cost(product_id, qty):
    """Cost per base unit the opening stock was booked at."""
    try:
        c = db.execute_scalar(
            "SELECT TOP 1 unit_cost FROM inventory_transactions WHERE product_id=? "
            "AND txn_type='opening' ORDER BY txn_id DESC", (product_id,))
        if _f(c) > 0:
            return _f(c)
    except Exception:
        pass
    try:
        v = db.execute_scalar(
            "SELECT SUM(jl.debit) - SUM(jl.credit) FROM journal_lines jl JOIN journal_entries je "
            "ON je.journal_id=jl.journal_id WHERE je.source_type='opening_stock' "
            "AND je.source_id=? AND jl.account_id=?", (product_id, _inventory_acc()))
        if qty and _f(v):
            return abs(_f(v) / qty)
    except Exception:
        pass
    return 0.0


def _inventory_acc():
    try:
        from modules import account_defaults as ad
        return ad.inventory()
    except Exception:
        return None


def post_opening_stock(product_id, qty_base, when=None, cost=None):
    """Opening stock of a product at its cost → Inventory / Opening
    Balance Equity. Returns journal_id or None."""
    global last_error
    from modules import posting
    from modules import account_defaults as ad
    from modules import doc_posting as dp
    last_error = ""

    def post():
        global last_error
        try:
            if not posting.enabled() or not dp._is_stock_item(product_id):
                return None
            c = _f(cost) if _f(cost) > 0 else dp.unit_cost(product_id)
            value = round(abs(_f(qty_base)) * c, 2)
            if value <= 0:
                return None
            inv, eq = ad.inventory(), ad.opening_equity()
            if _f(qty_base) > 0:
                lines = [(inv, value, 0, "Opening stock"), (eq, 0, value, "Opening stock")]
            else:
                lines = [(eq, value, 0, "Opening stock"), (inv, 0, value, "Opening stock")]
            code = db.execute_scalar("SELECT product_code FROM products WHERE product_id=?",
                                     (product_id,)) or "OPEN"
            jid = posting.post_journal(when or opening_date(), f"Opening stock {code}"[:200],
                                       lines, "opening_stock", int(product_id),
                                       reference=str(code)[:50])
            if not jid:
                last_error = posting.last_error
            return jid
        except Exception as e:
            last_error = str(e)[:200]
            return None
    return _replace("opening_stock", product_id, post)


@atomic
def set_opening_stock(product_id, qty, cost=None, when=None, adjust_stock=True):
    """Set (replace) one product's opening stock: qty in base units at
    `cost` per base unit (empty = the product's cost). Updates the stock
    quantity by the difference, the stock card and the books. Returns
    journal_id (or None when the value is zero). adjust_stock=False when
    the quantity is already on the product (new product just saved)."""
    qty = round(_f(qty), 4)
    when = when or opening_date()
    old = opening_qty(product_id)
    old_c = _opening_cost(product_id, old) if old else 0.0
    delta = round(qty - old, 4)
    p = db.fetchone("SELECT * FROM products WHERE product_id=?", (product_id,)) or {}
    if not p:
        raise ValueError("Product not found.")
    if not adjust_stock:                   # already counted in stock_quantity
        p = dict(p, stock_quantity=_f(p.get("stock_quantity")) - delta)
    c = _f(cost)
    if c <= 0:
        c = old_c
    if c <= 0:
        from modules import doc_posting as dp
        c = dp.unit_cost(product_id)
    # stock card
    db.execute("DELETE FROM inventory_transactions WHERE product_id=? AND txn_type='opening'",
               (product_id,))
    if abs(qty) > 1e-9:
        db.execute(
            "INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type, "
            "qty_in_base, qty_out_base, balance_base, unit_cost, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (product_id, when, "opening", "opening", max(qty, 0), max(-qty, 0),
             round(_f(p.get("stock_quantity")) + delta, 4), round(c, 2), "Opening stock"))
    # quantity
    if adjust_stock and abs(delta) > 1e-9:
        db.execute("UPDATE products SET stock_quantity=ISNULL(stock_quantity,0)+? "
                   "WHERE product_id=?", (delta, product_id))
    # cost: the old opening leaves the average cost, the new one joins it —
    # so stock × average cost stays equal to the Inventory account (v5.26:
    # changing only the cost of an opening left the two apart)
    if c > 0:
        s_before = _f(p.get("stock_quantity"))       # includes the old opening qty
        a = _f(p.get("average_cost")) or (old_c if old else 0.0)
        q_after = s_before + delta
        v_after = s_before * a - old * old_c + qty * c
        if a <= 0 or s_before <= 0 or q_after <= 1e-9 or v_after <= 0:
            new_avg = c
        else:
            new_avg = v_after / q_after
        try:
            db.execute("UPDATE products SET average_cost=?, purchase_price=CASE WHEN "
                       "ISNULL(purchase_price,0)=0 THEN ? ELSE purchase_price END "
                       "WHERE product_id=?", (round(new_avg, 4), round(c, 4), product_id))
        except Exception:
            pass
    return post_opening_stock(product_id, qty, when, c)


def _stock_movement_totals():
    """{product_id: qty in − qty out of every recorded movement}."""
    try:
        from modules import report_center as RC
        out = {}
        for m in RC._movements("1900-01-01"):
            out[m["pid"]] = out.get(m["pid"], 0.0) + m["qin"] - m["qout"]
        return out
    except Exception:
        return {}


def stock_rows(search=""):
    """Stock items for the Opening Stock grid: code, name, unit, stock,
    opening qty / cost / value and 'untracked' stock (on the product but
    with no movement behind it — e.g. typed in before or imported)."""
    q = (search or "").strip().lower()
    try:
        prods = db.fetchall("SELECT * FROM products ORDER BY product_code") or []
    except Exception:
        return []
    units = {}
    try:
        for u in db.fetchall("SELECT product_id, unit_name_en, conversion_factor FROM "
                             "product_units WHERE is_active=1") or []:
            if abs(_f(u.get("conversion_factor")) - 1) < 1e-9 and u["product_id"] not in units:
                units[u["product_id"]] = u.get("unit_name_en") or ""
    except Exception:
        pass
    opening = {}
    try:
        for r in db.fetchall(
                "SELECT product_id, SUM(ISNULL(qty_in_base,0)-ISNULL(qty_out_base,0)) AS q, "
                "MAX(unit_cost) AS c FROM inventory_transactions WHERE txn_type='opening' "
                "GROUP BY product_id") or []:
            opening[r["product_id"]] = (_f(r["q"]), _f(r["c"]))
    except Exception:
        pass
    moves = _stock_movement_totals()
    out = []
    for p in prods:
        if str(p.get("product_type") or "product").lower() == "service":
            continue
        code = str(p.get("product_code") or "")
        name = p.get("product_name_en") or ""
        if q and q not in (code + " " + name + " " + str(p.get("product_name_ar") or "")
                           + " " + str(p.get("barcode") or "")).lower():
            continue
        oq, oc = opening.get(p["product_id"], (0.0, 0.0))
        cost = oc or _f(p.get("average_cost")) or _f(p.get("purchase_price")) \
            or _f(p.get("last_purchase_cost"))
        stock = _f(p.get("stock_quantity"))
        out.append({"id": p["product_id"], "code": code, "name": name,
                    "unit": units.get(p["product_id"]) or p.get("unit_of_measure_en") or "",
                    "stock": round(stock, 3), "opening": round(oq, 3), "cost": round(cost, 2),
                    "value": round(oq * cost, 2),
                    "untracked": round(stock - moves.get(p["product_id"], 0.0), 3),
                    "active": p.get("is_active", 1) in (1, True, None)})
    return out


@atomic
def add_untracked_stock(when=None):
    """Products whose stock has no movement behind it (typed straight into
    the product or imported): book that quantity as opening stock so the
    stock card, Stock Movement and the Inventory account agree.
    Returns how many products were fixed."""
    n = 0
    for r in stock_rows():
        u = r["untracked"]
        if abs(u) < 1e-6:
            continue
        old = opening_qty(r["id"])
        # the quantity is already on the product: record it without changing stock
        new_q = round(old + u, 4)
        try:
            db.execute("UPDATE products SET stock_quantity=ISNULL(stock_quantity,0)-? "
                       "WHERE product_id=?", (u, r["id"]))
            set_opening_stock(r["id"], new_q, r["cost"] or None, when)
            n += 1
        except Exception:
            pass
    return n


# ════════════════════════════════════════════════════════════
#  Account openings (cash, bank, assets, loans, capital …)
# ════════════════════════════════════════════════════════════
def _excluded_accounts():
    """Accounts that get their opening elsewhere: receivable / payable
    (customers / suppliers), inventory (opening stock) and Opening
    Balance Equity itself (it takes the difference)."""
    out = set()
    try:
        from modules import account_defaults as ad
        out = {ad.receivable(), ad.payable(), ad.inventory(), ad.opening_equity()}
    except Exception:
        pass
    return {x for x in out if x}


def account_rows(search=""):
    """Balance-sheet accounts that can take an opening balance:
    [{id, code, name, type, debit, credit}]."""
    q = (search or "").strip().lower()
    try:
        accs = db.fetchall("SELECT * FROM accounts ORDER BY account_code") or []
    except Exception:
        return []
    parents = {a.get("parent_account_id") for a in accs if a.get("parent_account_id")}
    excl = _excluded_accounts()
    cur = {}
    for jid in _journal_ids("opening_accounts", 0):
        try:
            for l in db.fetchall("SELECT account_id, debit, credit FROM journal_lines "
                                 "WHERE journal_id=?", (jid,)) or []:
                d, c = cur.get(l["account_id"], (0.0, 0.0))
                cur[l["account_id"]] = (d + _f(l["debit"]), c + _f(l["credit"]))
        except Exception:
            pass
    out = []
    for a in accs:
        aid = a["account_id"]
        typ = str(a.get("account_type") or "").lower()
        code = str(a.get("account_code") or "")
        if typ not in ("asset", "liability", "equity") or aid in parents or aid in excl:
            continue
        if "-" in code or a.get("is_active", 1) in (0, False):
            continue                       # customer / supplier ledgers
        if q and q not in (code + " " + str(a.get("account_name_en") or "")).lower():
            continue
        d, c = cur.get(aid, (0.0, 0.0))
        net = round(d - c, 2)
        out.append({"id": aid, "code": code, "name": a.get("account_name_en") or "",
                    "type": typ.title(), "debit": net if net > 0 else 0.0,
                    "credit": -net if net < 0 else 0.0})
    return out


@atomic
def save_account_openings(amounts, when=None):
    """amounts = {account_id: (debit, credit)} for every account that has
    an opening (accounts left out get none). The difference goes to
    Opening Balance Equity. Returns journal_id (None = nothing to post)."""
    global last_error
    from modules import posting
    from modules import account_defaults as ad
    last_error = ""
    lines = []
    for aid, (dr, cr) in amounts.items():
        net = round(_f(dr) - _f(cr), 2)
        if abs(net) < 0.005:
            continue
        lines.append((aid, max(net, 0), max(-net, 0), "Opening balance"))

    def post():
        global last_error
        if not lines:
            return None
        eq = ad.opening_equity()
        if not eq:
            last_error = "Opening Balance Equity account (3400) not found."
            return None
        diff = round(sum(l[1] for l in lines) - sum(l[2] for l in lines), 2)
        ls = list(lines)
        if abs(diff) >= 0.005:
            ls.append((eq, max(-diff, 0), max(diff, 0), "Opening balance difference"))
        jid = posting.post_journal(when or opening_date(), "Opening balances — accounts", ls,
                                   "opening_accounts", 0, reference="OPEN")
        if not jid:
            last_error = posting.last_error or "Could not post the opening entry."
        return jid
    return _replace("opening_accounts", 0, post)


# ════════════════════════════════════════════════════════════
#  Summary
# ════════════════════════════════════════════════════════════
def summary():
    """Totals of everything opened, and Opening Balance Equity (= what
    the owner brought into the business)."""
    s = {"accounts_dr": 0.0, "accounts_cr": 0.0, "stock_value": 0.0, "stock_items": 0,
         "receivable": 0.0, "payable": 0.0, "equity": 0.0, "date": opening_date()}
    try:
        from modules import account_defaults as ad
        inv, eq = ad.inventory(), ad.opening_equity()
        rows = db.fetchall(
            "SELECT je.source_type, jl.account_id, SUM(jl.debit) AS dr, SUM(jl.credit) AS cr "
            "FROM journal_lines jl JOIN journal_entries je ON je.journal_id=jl.journal_id "
            "WHERE je.source_type IN ('opening_accounts','opening_stock','opening_customer',"
            "'opening_supplier') GROUP BY je.source_type, jl.account_id") or []
        for r in rows:
            dr, cr = _f(r["dr"]), _f(r["cr"])
            st, aid = r["source_type"], r["account_id"]
            if aid == eq:
                s["equity"] += cr - dr
                continue
            if st == "opening_accounts":
                s["accounts_dr"] += dr
                s["accounts_cr"] += cr
            elif st == "opening_stock" and aid == inv:
                s["stock_value"] += dr - cr
            elif st == "opening_customer":
                s["receivable"] += dr - cr
            elif st == "opening_supplier":
                s["payable"] += cr - dr
        s["stock_items"] = int(_f(db.execute_scalar(
            "SELECT COUNT(DISTINCT product_id) FROM inventory_transactions WHERE txn_type='opening'")))
    except Exception:
        pass
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()}


def equity_balance():
    """What sits in Opening Balance Equity now (credit = positive)."""
    try:
        from modules import account_defaults as ad
        eq = ad.opening_equity()
        return round(_f(db.execute_scalar(
            "SELECT SUM(jl.credit) - SUM(jl.debit) FROM journal_lines jl JOIN journal_entries je "
            "ON je.journal_id=jl.journal_id WHERE je.is_posted=1 AND jl.account_id=?", (eq,))), 2)
    except Exception:
        return 0.0


@atomic
def move_equity_to_capital(capital_code="3100", when=None):
    """Close Opening Balance Equity into Owner's Capital (one journal for
    whatever is in it now). Returns journal_id or None."""
    global last_error
    from modules import posting
    from modules import account_defaults as ad
    last_error = ""
    amt = equity_balance()
    if abs(amt) < 0.005:
        last_error = "Opening Balance Equity is already zero."
        return None
    eq = ad.opening_equity()
    cap = ad._id_from_code(capital_code) or ad._id_from_code("3000")
    if not eq or not cap:
        last_error = "Owner's Capital account (3100) not found."
        return None
    lines = ([(eq, amt, 0, "Opening balance to capital"), (cap, 0, amt, "Owner's capital")]
             if amt > 0 else
             [(cap, -amt, 0, "Owner's capital"), (eq, 0, -amt, "Opening balance to capital")])
    jid = posting.post_journal(when or opening_date(), "Opening Balance Equity → Owner's Capital",
                               lines, "adjustment", None, reference="OPEN-CAP")
    if not jid:
        last_error = posting.last_error
    return jid


def backfill():
    """Post every customer / supplier opening balance that has no entry
    yet (older data). Returns how many were posted."""
    n = 0
    for tbl, col, pt in (("customers", "customer", "customer"),
                         ("suppliers", "supplier", "supplier")):
        try:
            rows = db.fetchall(
                f"SELECT {col}_id AS id FROM {tbl} WHERE ISNULL(opening_balance,0)<>0 "
                f"AND NOT EXISTS (SELECT 1 FROM journal_entries je WHERE "
                f"je.source_type='opening_{pt}' AND je.source_id={tbl}.{col}_id)") or []
        except Exception:
            rows = []
        for r in rows:
            if post_party(pt, r["id"]):
                n += 1
    return n
