# ============================================================
# DayBill ERP - Stock Journal (v7.11.0)
# ------------------------------------------------------------
# Three numbered documents that change stock without a sale or a
# purchase (Inventory ▸ Transactions ▸ Stock Journal):
#
#   damage    DMG-YYYYMM-000001  broken, spoiled, expired → written off
#             stock OUT at cost   Dr Damaged Stock Written Off (5165)
#                                 Cr Inventory
#   shortage  SHT-YYYYMM-000001  less on the shelf than in DayBill (lost,
#             stolen, miscounted)
#             stock OUT at cost   Dr Stock Shortage (5166)  Cr Inventory
#   excess    EXS-YYYYMM-000001  more on the shelf than in DayBill (found,
#             free goods, counting error)
#             stock IN at cost    Dr Inventory  Cr Stock Excess (Gain) (4320)
#
# Saving a CONFIRMED entry moves the stock and posts the journal
# (doc_posting kind "stock_journal"); a draft moves nothing. Edit and
# delete reverse everything first, like every other document.
#
# Settings: sj_acc_<type> = account code · sj_prefix_<type> = number prefix
# ============================================================

import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db
from config import settings as cfg

# key, English, Arabic, prefix, account code, direction (+1 in / -1 out), icon, voucher code
TYPES = [
    ("damage", "Damage Entry", "إدخال تالف", "DMG", "5165", -1, "💔", "DMG"),
    ("excess", "Excess Stock (add)", "زيادة مخزون", "EXS", "4320", +1, "➕", "EXS"),
    ("shortage", "Shortage Stock (less)", "عجز مخزون", "SHT", "5166", -1, "➖", "SHT"),
    # v7.12: stock taken for own use (Consumable Entry) that comes back —
    # stock IN at cost, Cr the expense account of what it was used for
    ("consumable_return", "Consumable Return", "مرتجع استهلاك", "CRT", "", +1, "↩", "CRT"),
]
T = {t[0]: dict(key=t[0], en=t[1], ar=t[2], prefix=t[3], code=t[4], sign=t[5],
                icon=t[6], voucher=t[7]) for t in TYPES}
KEYS = [t[0] for t in TYPES]

# short reasons offered on the entry (any text can be typed)
REASONS = {
    "damage": ["Broken / damaged", "Expired", "Spoiled", "Customer return — not sellable",
               "Rats / insects", "Water / fire"],
    "shortage": ["Missing on count", "Theft", "Lost in transit", "Counting error"],
    "excess": ["Found on count", "Free goods from supplier", "Counting error",
               "Returned without bill"],
}


def _consumption_purposes():
    try:
        from modules import consumption as _cn
        return _cn.PURPOSES
    except Exception:
        return []


# a consumable return gives back what it was used for (the expense is reversed)
REASONS["consumable_return"] = [en for _k, en, _a, _c in _consumption_purposes()]

# journal source_type of each kind (one per type → its own voucher code)
SOURCE = {k: "stock_" + k for k in KEYS}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        return db.execute_scalar("SELECT OBJECT_ID('stock_journals','U')") is not None
    except Exception:
        return False


def label(kind, arabic=False):
    t = T.get(str(kind or ""))
    if not t:
        return str(kind or "")
    return t["ar"] if arabic else t["en"]


def _purpose_of(reason):
    """Consumable return: the Consumable Entry purpose its reason names."""
    r = str(reason or "").strip().lower()
    for k, en, ar, _c in _consumption_purposes():
        if r in (k, en.lower(), str(ar).lower()):
            return k
    return "staff_food"


def account_code_for(kind, reason=None):
    t = T.get(kind) or T["damage"]
    code = str(cfg.get("sj_acc_" + t["key"], "") or "").strip()
    if not code and kind == "consumable_return":
        try:
            from modules import consumption as _cn
            code = _cn.account_code_for(_purpose_of(reason))
        except Exception:
            code = "5390"
    return code or t["code"]


def account_for(kind, reason=None):
    """account_id of the type's account. When it is missing: Stock
    Adjustment (5160), then the general expense / other income account."""
    t = T.get(kind) or T["damage"]
    for code in (account_code_for(kind, reason), "5160",
                 "4300" if (t["sign"] > 0 and kind != "consumable_return") else "5390"):
        try:
            a = db.execute_scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
            if a:
                return a
        except Exception:
            pass
    return None


def prefix(kind):
    t = T.get(kind) or T["damage"]
    return str(cfg.get("sj_prefix_" + t["key"]) or t["prefix"]).strip() or t["prefix"]


def next_number(kind):
    """DMG-202611-000001 / EXS-… / SHT-… — one series per type (doc_numbering)."""
    p = prefix(kind)
    from modules.doc_numbering import next_number as _nn
    try:
        return _nn("stock_journals", "entry_number", p)
    except Exception:
        n = int(db.execute_scalar("SELECT COUNT(*) FROM stock_journals WHERE entry_number LIKE ?",
                                  (p + "%",)) or 0) + 1
        return "%s-%06d" % (p, n)


def line_cost(product_id, unit_name=""):
    """Cost of ONE unit (as chosen on the line) — the stock leaves / comes
    in at the product's average cost."""
    from modules import doc_posting as dp
    try:
        return round(dp.unit_cost(product_id) * dp.unit_factor(product_id, unit_name or ""), 4)
    except Exception:
        return 0.0


def stock_of(product_id, unit_name=""):
    """Stock now, in the unit chosen on the line."""
    from modules import doc_posting as dp
    try:
        q = _f(db.execute_scalar("SELECT ISNULL(stock_quantity,0) FROM products WHERE product_id=?",
                                 (product_id,)))
        f = dp.unit_factor(product_id, unit_name or "") or 1.0
        return q / f
    except Exception:
        return 0.0


def get(entry_id):
    h = db.fetchone("SELECT * FROM stock_journals WHERE entry_id=?", (int(entry_id),))
    if not h:
        return None, []
    lines = db.fetchall("SELECT * FROM stock_journal_lines WHERE entry_id=? ORDER BY line_number",
                        (int(entry_id),)) or []
    return dict(h), [dict(l) for l in lines]


def save(header, lines, entry_id=None, user_id=None):
    """Save (new or edit) and post.
    header: entry_type, entry_date, reason, notes, entry_status
            ('confirmed' | 'draft'), account_id (optional)
    lines:  [{product_id, quantity, unit_of_measure_en, remarks}]
    → (entry_id, number, warning)"""
    kind = str(header.get("entry_type") or "")
    if kind not in T:
        raise ValueError("Choose Damage, Excess, Shortage or Consumable Return.")
    when = str(header.get("entry_date") or date.today().isoformat())[:10]
    from modules import financial_year as fy
    msg = fy.lock_message(when)
    if not msg and entry_id:
        from modules import doc_edit
        msg = doc_edit.block_reason("stock_journal", entry_id, "edit")
    if msg:
        raise ValueError(msg)
    if entry_id:                      # the type of a saved entry never changes
        old = db.execute_scalar("SELECT entry_type FROM stock_journals WHERE entry_id=?",
                                (int(entry_id),))
        if old and old != kind:
            raise ValueError("A saved %s can't become a %s — make a new entry."
                             % (label(old), label(kind)))
    status = "draft" if str(header.get("entry_status") or "").lower() == "draft" else "confirmed"
    rows = []
    for ln in lines or []:
        pid = ln.get("product_id")
        qty = _f(ln.get("quantity"))
        if not pid:
            continue
        if not (0 < qty < 1e6):
            raise ValueError("Quantity must be more than 0 (line %d)." % (len(rows) + 1))
        p = db.fetchone("SELECT product_id, product_code, product_name_en, product_name_ar, "
                        "unit_of_measure_en, ISNULL(product_type,'product') AS product_type "
                        "FROM products WHERE product_id=?", (pid,))
        if not p:
            raise ValueError("Product %s not found." % pid)
        if str(p.get("product_type") or "").lower() == "service":
            raise ValueError("%s is a service — it has no stock." % p.get("product_name_en"))
        unit = ln.get("unit_of_measure_en") or p.get("unit_of_measure_en") or "PCs"
        uc = line_cost(pid, unit)
        rows.append(dict(product_id=pid, product_code=p.get("product_code") or "",
                         product_name_en=p.get("product_name_en") or "",
                         product_name_ar=p.get("product_name_ar") or "",
                         quantity=qty, unit=unit, unit_cost=uc,
                         line_total=round(uc * qty, 2),
                         remarks=(str(ln.get("remarks") or "")[:200] or None)))
    if not rows:
        raise ValueError("Add at least one item.")
    acc = header.get("account_id") or account_for(kind, header.get("reason"))
    total = round(sum(r["line_total"] for r in rows), 2)
    reason = (str(header.get("reason") or "")[:100]) or None
    notes = (str(header.get("notes") or "")[:500]) or None
    from modules import doc_posting
    with db.transaction():
        if entry_id:
            number = db.execute_scalar("SELECT entry_number FROM stock_journals WHERE entry_id=?",
                                       (int(entry_id),))
            if not number:
                raise ValueError("This entry no longer exists.")
            db.execute("UPDATE stock_journals SET entry_date=?, reason=?, account_id=?, "
                       "total_cost=?, notes=?, entry_status=?, updated_at=GETDATE() "
                       "WHERE entry_id=?",
                       (when, reason, acc, total, notes, status, int(entry_id)))
            db.execute("DELETE FROM stock_journal_lines WHERE entry_id=?", (int(entry_id),))
        else:
            number = next_number(kind)
            db.execute("INSERT INTO stock_journals (entry_number, entry_type, entry_date, reason, "
                       "account_id, total_cost, notes, entry_status, created_by) "
                       "VALUES (?,?,?,?,?,?,?,?,?)",
                       (number, kind, when, reason, acc, total, notes, status, user_id))
            entry_id = db.last_identity("stock_journals", "entry_id")
        for i, r in enumerate(rows, 1):
            db.execute("INSERT INTO stock_journal_lines (entry_id, line_number, product_id, "
                       "product_code, product_name_en, product_name_ar, quantity, "
                       "unit_of_measure_en, unit_cost, line_total, remarks) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (int(entry_id), i, r["product_id"], r["product_code"],
                        r["product_name_en"], r["product_name_ar"], r["quantity"], r["unit"],
                        r["unit_cost"], r["line_total"], r["remarks"]))
        warn = doc_posting.sync("stock_journal", int(entry_id)) or ""
        if status == "confirmed" and ("journal not posted" in warn or "stock not updated" in warn):
            raise ValueError("Not saved — " + warn)
    try:
        from modules.doc_actions import audit
        audit("edit" if header.get("_edit") else "add", "stock_journal", int(entry_id),
              "%s · %s · %.2f" % (number, label(kind), total))
    except Exception:
        pass
    return int(entry_id), number, warn


def entries(kind=None, date_from=None, date_to=None, limit=500):
    if not ready():
        return []
    sql = ("SELECT TOP %d e.*, a.account_code, a.account_name_en FROM stock_journals e "
           "LEFT JOIN accounts a ON a.account_id=e.account_id WHERE 1=1" % int(limit))
    params = []
    if kind:
        sql += " AND e.entry_type=?"
        params.append(kind)
    if date_from:
        sql += " AND e.entry_date >= ?"
        params.append(str(date_from)[:10])
    if date_to:
        sql += " AND e.entry_date <= ?"
        params.append(str(date_to)[:10])
    sql += " ORDER BY e.entry_date DESC, e.entry_id DESC"
    try:
        return db.fetchall(sql, tuple(params)) or []
    except Exception:
        return []


def register(date_from=None, date_to=None, kind=None):
    """Item lines of the confirmed entries (the Stock Journal Register)."""
    if not ready():
        return []
    sql = ("SELECT e.entry_number, e.entry_type, e.entry_date, e.reason, l.product_code, "
           "l.product_name_en, l.quantity, l.unit_of_measure_en, l.unit_cost, l.line_total, "
           "l.remarks FROM stock_journal_lines l JOIN stock_journals e ON e.entry_id=l.entry_id "
           "WHERE e.entry_status='confirmed'")
    params = []
    if kind:
        sql += " AND e.entry_type=?"
        params.append(kind)
    if date_from:
        sql += " AND e.entry_date >= ?"
        params.append(str(date_from)[:10])
    if date_to:
        sql += " AND e.entry_date <= ?"
        params.append(str(date_to)[:10])
    sql += " ORDER BY e.entry_date, e.entry_id, l.line_number"
    try:
        return [dict(r) for r in (db.fetchall(sql, tuple(params)) or [])]
    except Exception:
        return []
