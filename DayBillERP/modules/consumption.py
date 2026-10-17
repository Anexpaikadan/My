# ============================================================
# DayBill ERP - Consumable entry (v6.9.3)
# ------------------------------------------------------------
# Stock the shop uses ITSELF — not sold:
#   staff_food   food for the staff room / accommodation
#   production   raw material used by a production unit (bakery,
#                kitchen, juice counter …) — the unit name is kept
#   shop_use     cleaning, packing, tea / coffee for the shop
#   samples      samples and tasting
#   damaged      spoiled / damaged / expired, written off
#
# Saving a CONFIRMED entry takes the stock out at its cost and posts
#   Dr  <purpose expense account>      Cr  Inventory
# (doc_posting kind "consumption", voucher type CE). A draft moves
# nothing. Edit / delete reverse everything first (doc_posting.sync /
# doc_edit.delete_document), exactly like the other documents.
#
# Settings ▸ Inventory ▸ consume_acc_<purpose> = account code to use.
# ============================================================

import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db
from config import settings as cfg

PURPOSES = [
    # key, English, Arabic, default expense account code
    ("staff_food", "Staff / room food", "طعام الموظفين / السكن", "5460"),
    ("production", "Production unit (bakery, kitchen …)", "وحدة إنتاج (مخبز، مطبخ …)", "5470"),
    ("shop_use", "Shop use (cleaning, packing, tea …)", "استخدام المحل (تنظيف، تغليف، شاي …)", "5480"),
    ("samples", "Samples / tasting", "عينات / تذوق", "5490"),
    ("damaged", "Damaged / expired (write-off)", "تالف / منتهي (شطب)", "5160"),
]
_P = {k: (en, ar, code) for k, en, ar, code in PURPOSES}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        return db.execute_scalar("SELECT OBJECT_ID('consumption_entries','U')") is not None
    except Exception:
        return False


def purpose_label(key, arabic=False):
    en, ar, _c = _P.get(str(key or ""), (str(key or ""), str(key or ""), ""))
    return ar if arabic else en


def account_code_for(purpose):
    p = str(purpose or "staff_food")
    code = str(cfg.get("consume_acc_" + p, "") or "").strip()
    return code or _P.get(p, ("", "", "5390"))[2] or "5390"


def account_for(purpose):
    """account_id of the purpose's expense account (General Expense when the
    account is missing)."""
    for code in (account_code_for(purpose), "5390"):
        try:
            a = db.execute_scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
            if a:
                return a
        except Exception:
            pass
    return None


def next_number():
    from modules.doc_numbering import next_number as _nn
    try:
        return _nn("consumption_entries", "entry_number",
                   str(cfg.get("consumption_prefix") or "CE").strip() or "CE")
    except Exception:
        n = int(db.execute_scalar("SELECT COUNT(*) FROM consumption_entries") or 0) + 1
        return "CE-%06d" % n


def line_cost(product_id, unit_name=""):
    """Cost of ONE unit (as chosen on the line) — the cost the stock will
    leave with."""
    from modules import doc_posting as dp
    try:
        return round(dp.unit_cost(product_id) * dp.unit_factor(product_id, unit_name or ""), 4)
    except Exception:
        return 0.0


def get(entry_id):
    h = db.fetchone("SELECT * FROM consumption_entries WHERE entry_id=?", (int(entry_id),))
    if not h:
        return None, []
    lines = db.fetchall("SELECT * FROM consumption_lines WHERE entry_id=? ORDER BY line_number",
                        (int(entry_id),)) or []
    return dict(h), [dict(l) for l in lines]


def save(header, lines, entry_id=None, user_id=None):
    """Save (new or edit) and post. header: entry_date, purpose, unit_name,
    notes, entry_status ('confirmed' | 'draft'), expense_account_id (opt).
    lines: [{product_id, quantity, unit_of_measure_en}]. → (entry_id, number, warning)"""
    when = str(header.get("entry_date") or date.today().isoformat())[:10]
    from modules import financial_year as fy
    msg = fy.lock_message(when)
    if not msg and entry_id:        # v6.9.5: the saved entry's own rules (closed
        from modules import doc_edit    # year, …) — a new date never moves it out
        msg = doc_edit.block_reason("consumption", entry_id, "edit")
    if msg:
        raise ValueError(msg)
    purpose = header.get("purpose") or "staff_food"
    if purpose not in _P:
        raise ValueError("Choose what the stock was used for.")
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
                        "unit_of_measure_en FROM products WHERE product_id=?", (pid,))
        if not p:
            raise ValueError("Product %s not found." % pid)
        unit = ln.get("unit_of_measure_en") or p.get("unit_of_measure_en") or "PCs"
        uc = line_cost(pid, unit)
        rows.append(dict(product_id=pid, product_code=p.get("product_code") or "",
                         product_name_en=p.get("product_name_en") or "",
                         product_name_ar=p.get("product_name_ar") or "",
                         quantity=qty, unit=unit, unit_cost=uc,
                         line_total=round(uc * qty, 2)))
    if not rows:
        raise ValueError("Add at least one item.")
    exp = header.get("expense_account_id") or account_for(purpose)
    total = round(sum(r["line_total"] for r in rows), 2)
    from modules import doc_posting
    with db.transaction():
        if entry_id:
            number = db.execute_scalar("SELECT entry_number FROM consumption_entries "
                                       "WHERE entry_id=?", (int(entry_id),))
            if not number:
                raise ValueError("This entry no longer exists.")
            db.execute("UPDATE consumption_entries SET entry_date=?, purpose=?, "
                       "expense_account_id=?, unit_name=?, total_cost=?, notes=?, "
                       "entry_status=?, updated_at=GETDATE() WHERE entry_id=?",
                       (when, purpose, exp, (header.get("unit_name") or "")[:100] or None,
                        total, (header.get("notes") or "")[:500] or None, status, int(entry_id)))
            db.execute("DELETE FROM consumption_lines WHERE entry_id=?", (int(entry_id),))
        else:
            number = next_number()
            db.execute("INSERT INTO consumption_entries (entry_number, entry_date, purpose, "
                       "expense_account_id, unit_name, total_cost, notes, entry_status, "
                       "created_by) VALUES (?,?,?,?,?,?,?,?,?)",
                       (number, when, purpose, exp,
                        (header.get("unit_name") or "")[:100] or None, total,
                        (header.get("notes") or "")[:500] or None, status, user_id))
            entry_id = db.last_identity("consumption_entries", "entry_id")
        for i, r in enumerate(rows, 1):
            db.execute("INSERT INTO consumption_lines (entry_id, line_number, product_id, "
                       "product_code, product_name_en, product_name_ar, quantity, "
                       "unit_of_measure_en, unit_cost, line_total) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (int(entry_id), i, r["product_id"], r["product_code"],
                        r["product_name_en"], r["product_name_ar"], r["quantity"], r["unit"],
                        r["unit_cost"], r["line_total"]))
        warn = doc_posting.sync("consumption", int(entry_id)) or ""
        if status == "confirmed" and "journal not posted" in warn:
            raise ValueError("Not saved — " + warn)
    try:
        from modules.doc_actions import audit
        audit("edit" if header.get("_edit") else "add", "consumption", int(entry_id),
              "%s · %s · %.2f" % (number, purpose_label(purpose), total))
    except Exception:
        pass
    return int(entry_id), number, warn


def entries(date_from=None, date_to=None, purpose=None, limit=500):
    if not ready():
        return []
    sql = ("SELECT TOP %d e.*, a.account_code, a.account_name_en FROM consumption_entries e "
           "LEFT JOIN accounts a ON a.account_id=e.expense_account_id WHERE 1=1" % int(limit))
    params = []
    if date_from:
        sql += " AND e.entry_date >= ?"
        params.append(str(date_from)[:10])
    if date_to:
        sql += " AND e.entry_date <= ?"
        params.append(str(date_to)[:10])
    if purpose:
        sql += " AND e.purpose=?"
        params.append(purpose)
    sql += " ORDER BY e.entry_date DESC, e.entry_id DESC"
    try:
        return db.fetchall(sql, tuple(params)) or []
    except Exception:
        return []
