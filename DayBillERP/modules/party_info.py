# ============================================================
# DayBill ERP - party facts for the transaction windows (v7.8)
# ------------------------------------------------------------
# When a customer / supplier is picked in the Sales window, the POS or
# a voucher, the window shows at once:
#   • the party's LEDGER BALANCE (posted vouchers, Dr / Cr)
#   • the party's LAST BILL (number, date, amount)
#   • the LAST BILL OF THIS COUNTER (the till / PC the window runs on)
# The walk-in "Cash Customer" / "Cash Supplier" has no balance of its own
# (it is booked straight to the cash account): only the counter's last
# bill is shown for it.
#
#   is_cash(kind, party_id)          the walk-in party?
#   has_no_account(kind, party_id)   strict: CASH party / booked to cash
#   balance(kind, party_id)          Dr − Cr of the party's ledger
#   last_bill(kind, party_id, exclude_id=None)  {id, number, date, total}
#   counter_last_bill(exclude_id=None)          {id, number, date, total}
#   facts(kind, party_id, exclude_id=None)      all of it
#   text(kind, party_id, exclude_id=None)       one line for a label
# ============================================================
from config.database import db

_DOCS = {
    "customer": ("sales_invoices", "invoice_id", "customer_id", "invoice_number", "invoice_date"),
    "supplier": ("purchase_invoices", "purchase_id", "supplier_id", "invoice_number", "invoice_date"),
}


def _f(v):
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def money(v):
    try:
        from modules import country as _K
        return _K.money(v)
    except Exception:
        return "{:,.2f}".format(_f(v))


def _account(kind, party_id):
    try:
        from modules import posting
        return posting._customer_account(party_id) if kind == "customer" else posting._supplier_account(party_id)
    except Exception:
        return None


def is_cash(kind, party_id):
    """The walk-in party: booked to the cash account, or coded CASH / named
    Cash Customer / Cash Supplier."""
    if not party_id:
        return True
    tbl, code, name = (("customers", "customer_code", "customer_name_en") if kind == "customer"
                       else ("suppliers", "supplier_code", "supplier_name_en"))
    try:
        r = db.fetchone("SELECT %s AS code, %s AS name FROM %s WHERE %s_id=?" % (code, name, tbl, kind),
                        (int(party_id),)) or {}
    except Exception:
        r = {}
    c, n = str(r.get("code") or "").upper(), str(r.get("name") or "").lower()
    if c in ("CASH", "WALKIN", "WALK-IN") or n.startswith("cash ") or "walk-in" in n or "walk in" in n:
        return True
    acc = _account(kind, party_id)
    try:
        from modules import account_defaults as ad
        return bool(acc) and acc == ad.cash()
    except Exception:
        return False


def has_no_account(kind, party_id):
    """Strict test for a save guard: no party, the built-in CASH party, or a
    party booked to the cash account. A customer only NAMED "walk-in" with
    a ledger of its own may still buy on credit."""
    if not party_id:
        return True
    tbl, code = ("customers", "customer_code") if kind == "customer" else ("suppliers", "supplier_code")
    try:
        r = db.fetchone("SELECT %s AS code FROM %s WHERE %s_id=?" % (code, tbl, kind), (int(party_id),)) or {}
    except Exception:
        r = {}
    if str(r.get("code") or "").upper() == "CASH":
        return True
    acc = _account(kind, party_id)
    try:
        from modules import account_defaults as ad
        return bool(acc) and acc == ad.cash()
    except Exception:
        return False


def balance(kind, party_id):
    """Ledger balance, Dr − Cr (a customer who owes us is +, a supplier we
    owe is −)."""
    acc = _account(kind, party_id)
    if not acc:
        return 0.0
    try:
        return _f(db.execute_scalar(
            "SELECT ISNULL(SUM(jl.debit - jl.credit),0) FROM journal_lines jl "
            "JOIN journal_entries je ON je.journal_id=jl.journal_id "
            "WHERE je.is_posted=1 AND jl.account_id=?", (acc,)))
    except Exception:
        return 0.0


def balance_text(v):
    v = _f(v)
    if not v:
        return money(0)
    return "%s %s" % (money(abs(v)), "Dr" if v > 0 else "Cr")


def _bill(where, params, kind="customer", exclude_id=None):
    tbl, idc, _pc, num, dt = _DOCS[kind]
    cond = ["ISNULL(invoice_status,'') NOT IN ('cancelled','void')"] + list(where)
    params = list(params)
    if exclude_id:
        cond.append("%s<>?" % idc)
        params.append(int(exclude_id))
    try:
        r = db.fetchone("SELECT TOP 1 %s AS id, %s AS number, %s AS d, total_amount AS total FROM %s WHERE %s "
                        "ORDER BY %s DESC" % (idc, num, dt, tbl, " AND ".join(cond), idc), tuple(params))
    except Exception:
        r = None
    if not r:
        return None
    return {"id": r["id"], "number": str(r["number"] or ""), "date": str(r["d"] or "")[:10],
            "total": _f(r["total"])}


def last_bill(kind, party_id, exclude_id=None):
    if not party_id or kind not in _DOCS:
        return None
    return _bill(["%s=?" % _DOCS[kind][2]], [int(party_id)], kind, exclude_id)


def counter_last_bill(exclude_id=None, kind="customer"):
    """The last bill made on THIS counter (Settings ▸ Branches ▸ this PC);
    with no counters set up, the last bill of the shop."""
    cid = None
    try:
        from modules import branches
        cid = branches.current()[1]
    except Exception:
        cid = None
    if cid:
        try:
            has = db.execute_scalar("SELECT COL_LENGTH('%s','counter_id')" % _DOCS[kind][0]) is not None
        except Exception:
            has = False
        if has:
            return _bill(["counter_id=?"], [int(cid)], kind, exclude_id)
    return _bill([], [], kind, exclude_id)


def facts(kind, party_id, exclude_id=None):
    cash = is_cash(kind, party_id)
    return {"cash": cash,
            "balance": None if cash else balance(kind, party_id),
            "last": None if cash else last_bill(kind, party_id, exclude_id),
            "counter": counter_last_bill(exclude_id, kind)}


def text(kind, party_id, exclude_id=None, f=None):
    f = f or facts(kind, party_id, exclude_id)
    bits = []
    if f["balance"] is not None:
        bits.append("Bal: %s" % balance_text(f["balance"]))
    if f["last"]:
        bits.append("L.Bill: %s (#%s, %s)" % (money(f["last"]["total"]), f["last"]["number"], f["last"]["date"]))
    elif not f["cash"]:
        bits.append("L.Bill: —")
    if f["counter"]:
        bits.append("Counter last: %s (#%s)" % (money(f["counter"]["total"]), f["counter"]["number"]))
    return "   ".join(bits) or "L.Bill: —"


# ── the customer typed on the bill (not in Customers) ────────
def clean_tax_no(v):
    return "".join(str(v or "").split()).upper()


def check_tax_no(v):
    """'' when fine (or empty), else what is wrong with it."""
    vat = clean_tax_no(v)
    if not vat:
        return ""
    if len(vat) > 15:
        return "The tax number has %d characters — at most 15." % len(vat)
    try:
        from modules import country as _K
        ok, why = _K.valid_tax_no(vat)
        return "" if ok else why
    except Exception:
        return ""


def save_typed(invoice_id, typed, card=None):
    """typed = {name, vat, mobile, address} from the Sales window / POS →
    the bill's customer snapshot (what prints). Blank = keep the card's."""
    typed, card = typed or {}, card or {}
    name = str(typed.get("name") or "").strip()
    vat = clean_tax_no(typed.get("vat"))
    addr = str(typed.get("address") or "").strip()
    mob = str(typed.get("mobile") or "").strip()
    sets, vals = [], []
    if name:
        same = name == (card.get("customer_name_en") or "")
        sets += ["customer_name_en=?", "customer_name_ar=?"]
        # a name typed for this bill has no Arabic of its own: no copy of it there
        vals += [name[:200], ((card.get("customer_name_ar") or "") if same else "")[:200]]
    if vat:
        sets.append("customer_vat_no=?"); vals.append(vat[:15])
    if addr:
        sets.append("customer_address_en=?"); vals.append(addr[:500])
    if mob:
        sets.append("customer_phone=?"); vals.append(mob[:30])
    if not sets or not invoice_id:
        return False
    try:
        db.execute("UPDATE sales_invoices SET %s WHERE invoice_id=?" % ", ".join(sets),
                   tuple(vals) + (int(invoice_id),))
    except Exception:
        keep = [(x, v) for x, v in zip(sets, vals) if not x.startswith("customer_phone")]
        if not keep:
            return False
        db.execute("UPDATE sales_invoices SET %s WHERE invoice_id=?" % ", ".join(x for x, _v in keep),
                   tuple(v for _x, v in keep) + (int(invoice_id),))
    return True
