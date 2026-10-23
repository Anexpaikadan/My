# ============================================================
# DayBill ERP - ways to pay (tenders) for POS bills (v6.0)
# ------------------------------------------------------------
# A bill can be paid with several tenders at once:
#   cash 50 + mada 30 + STC Pay 20 …
# Each tender is one row in payment_tenders (doc_type 'sales', doc_id)
# and is debited to its own ledger account:
#   cash                          → Cash account
#   mada / card / Apple Pay / STC → Bank account (the card terminal pays
#                                   into the bank — same as v5.26)
#   bank transfer                 → Bank account
#   Tabby / Tamara (buy now, pay later) → "BNPL receivable" (1260):
#                                   the provider pays the shop later
#   gift voucher                  → "Gift vouchers" liability (2360)
#   on account (credit)           → the customer's own ledger
# Settings ▸ POS ▸ Payment methods chooses which tiles the POS shows;
# Default Accounts ▸ Payment Method mapping can point any of them
# at another account.
# ============================================================
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

# key, English, Arabic, posts as
METHODS = [
    ("cash",          "Cash",           "نقدي",          "cash"),
    ("card",          "Card / mada",    "بطاقة / مدى",    "card"),
    ("stc_pay",       "STC Pay",        "STC Pay",       "card"),
    ("apple_pay",     "Apple Pay",      "Apple Pay",     "card"),
    ("bank_transfer", "Bank transfer",  "تحويل بنكي",     "bank"),
    ("tabby",         "Tabby",          "تابي",          "bnpl"),
    ("tamara",        "Tamara",         "تمارا",          "bnpl"),
    ("voucher",       "Gift voucher",   "قسيمة",         "voucher"),
]
NAMES = {k: en for k, en, _ar, _p in METHODS}
NAMES_AR = {k: ar for k, _en, ar, _p in METHODS}
POSTS_AS = {k: p for k, _en, _ar, p in METHODS}
EXTRA_DEFAULT = ["stc_pay", "tabby", "tamara"]          # tiles beside Cash / Card


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def extra_methods():
    """Tender tiles the POS shows next to Cash and Card (Settings ▸ POS)."""
    try:
        from config import settings as cfg
        raw = cfg.get("pos_extra_tenders", EXTRA_DEFAULT)
    except Exception:
        raw = EXTRA_DEFAULT
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",")]
    return [k for k in (raw or []) if k in NAMES and k not in ("cash", "card")]


def label(key, lang="en"):
    return (NAMES_AR if lang == "ar" else NAMES).get(key, str(key).replace("_", " ").title())


# ── accounts ─────────────────────────────────────────────────
def _ensure_account(code, name_en, name_ar, typ, parent_code=None):
    try:
        a = db.execute_scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
        if a:
            return a
        parent = None
        if parent_code:
            parent = db.execute_scalar("SELECT account_id FROM accounts WHERE account_code=?",
                                       (parent_code,))
        db.execute("INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
                   "account_type, parent_account_id, is_active) VALUES (?,?,?,?,?,1)",
                   (code, name_en, name_ar, typ, parent))
        return db.execute_scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
    except Exception:
        return None


def account_for(method):
    """Ledger account a tender is debited to (None = on the customer's account)."""
    from modules import account_defaults as ad
    m = str(method or "cash").lower()
    if m in ("credit", "on_account"):
        return None
    try:                                   # Default Accounts ▸ Payment Method mapping
        a = db.execute_scalar("SELECT TOP 1 account_id FROM payment_method_accounts "
                              "WHERE method_code=? AND is_active=1", (m,))
        if a:
            return a
    except Exception:
        pass
    kind = POSTS_AS.get(m, "card")
    if kind == "cash":
        return ad.cash()
    if kind == "bank":
        return ad.bank() or ad.cash()
    if kind == "bnpl":
        return _ensure_account("1260", "BNPL receivable (Tabby / Tamara)",
                               "ذمم الشراء الآن والدفع لاحقا", "asset", "1200") or ad.bank()
    if kind == "voucher":
        return _ensure_account("2360", "Gift vouchers sold", "قسائم هدايا مباعة",
                               "liability") or ad.cash()
    return ad.method_account("card")          # card / mada settle to the bank (v5.26)


# ── rows ─────────────────────────────────────────────────────
def clean(lines, total=None):
    """[(method, amount, ref)] or {method: amount} → [{method, amount, reference}]
    without zero rows; cash beyond the total is change (not kept)."""
    if isinstance(lines, dict):
        lines = [(k, v, "") for k, v in lines.items()]
    out = []
    for item in lines or []:
        if isinstance(item, dict):
            m, a, r = item.get("method"), item.get("amount"), item.get("reference", "")
        else:
            m, a, r = (list(item) + ["", "", ""])[:3]
        a = round(_f(a), 2)
        if m and a > 0.004:
            out.append({"method": str(m).lower(), "amount": a, "reference": str(r or "")[:100]})
    if total is not None:
        excess = round(sum(x["amount"] for x in out) - round(_f(total), 2), 2)
        for x in out:                         # change comes out of cash first
            if excess <= 0.004:
                break
            if x["method"] == "cash":
                cut = min(x["amount"], excess)
                x["amount"] = round(x["amount"] - cut, 2)
                excess = round(excess - cut, 2)
        out = [x for x in out if x["amount"] > 0.004]
    return out


def save_lines(doc_type, doc_id, lines):
    """Replace the tender rows of a document (inside its save transaction)."""
    try:
        db.execute("DELETE FROM payment_tenders WHERE doc_type=? AND doc_id=?",
                   (doc_type, int(doc_id)))
    except Exception:
        return False                       # table not there yet (old database)
    for x in lines or []:
        db.execute("INSERT INTO payment_tenders (doc_type, doc_id, method, amount, reference, "
                   "account_id) VALUES (?,?,?,?,?,?)",
                   (doc_type, int(doc_id), x["method"], x["amount"], x.get("reference") or None,
                    x.get("account_id") or account_for(x["method"])))   # v7.9: the account picked
    return True


def lines_for(doc_type, doc_id):
    if not doc_id:
        return []
    try:
        rows = [dict(r) for r in db.fetchall(
            "SELECT method, amount, reference, account_id FROM payment_tenders "
            "WHERE doc_type=? AND doc_id=? ORDER BY tender_id", (doc_type, int(doc_id))) or []]
        for r in rows:                     # DECIMAL from the database → float (sums with floats)
            r["amount"] = round(_f(r.get("amount")), 2)
        return rows
    except Exception:
        return []


def delete_lines(doc_type, doc_id):
    try:
        db.execute("DELETE FROM payment_tenders WHERE doc_type=? AND doc_id=?",
                   (doc_type, int(doc_id)))
    except Exception:
        pass


def method_name(lines):
    """'cash' / 'card' / 'tabby' … for one tender, 'mixed' for several,
    'credit' for none."""
    ms = {x["method"] for x in lines or []}
    if not ms:
        return "credit"
    if len(ms) == 1:
        return next(iter(ms))
    return "mixed"


def split_cash(lines):
    """(cash, everything else) — for the cash_paid / card_paid columns."""
    cash = round(sum(x["amount"] for x in lines or [] if x["method"] == "cash"), 2)
    other = round(sum(x["amount"] for x in lines or [] if x["method"] != "cash"), 2)
    return cash, other


def for_posting(lines):
    """{"cash": c, "bank": card+bank, "other": {account_id: amount}} for
    doc_posting.sync — tenders with their own account go to "other"."""
    from modules import account_defaults as ad
    out = {"cash": 0.0, "bank": 0.0, "other": {}}
    cash_acc, bank_acc = ad.cash(), ad.bank()
    for x in lines or []:
        acc = x.get("account_id") or account_for(x["method"])   # v7.9: the account picked on the bill
        if acc is None:
            continue
        amt = _f(x.get("amount"))
        if acc == cash_acc:
            out["cash"] = round(out["cash"] + amt, 2)
        elif acc == bank_acc:
            out["bank"] = round(out["bank"] + amt, 2)
        else:
            out["other"][acc] = round(out["other"].get(acc, 0.0) + amt, 2)
    return out


def totals_by_method(date_from, date_to, counter_id=None, shift_id=None):
    """{method: amount} of POS / sales tenders in a period (day close,
    shift close). Bills without tender rows count by cash_paid / card_paid."""
    cond, params = ["si.invoice_status='confirmed'", "si.invoice_date >= ?", "si.invoice_date <= ?"], \
        [date_from, date_to]
    if counter_id:
        cond.append("si.counter_id=?"); params.append(int(counter_id))
    if shift_id:
        cond.append("si.shift_id=?"); params.append(int(shift_id))
    out = {}
    try:
        for r in db.fetchall(
                "SELECT pt.method, SUM(pt.amount) AS a FROM payment_tenders pt JOIN sales_invoices si "
                "ON si.invoice_id=pt.doc_id AND pt.doc_type='sales' WHERE " + " AND ".join(cond)
                + " GROUP BY pt.method", tuple(params)) or []:
            out[r["method"]] = round(_f(r["a"]), 2)
        rows = db.fetchall(
            "SELECT SUM(ISNULL(si.cash_paid,0)) AS c, SUM(ISNULL(si.card_paid,0)) AS k FROM sales_invoices si "
            "WHERE " + " AND ".join(cond) + " AND NOT EXISTS (SELECT 1 FROM payment_tenders pt "
            "WHERE pt.doc_type='sales' AND pt.doc_id=si.invoice_id)", tuple(params)) or []
        if rows:
            out["cash"] = round(out.get("cash", 0.0) + _f(rows[0].get("c")), 2)
            out["card"] = round(out.get("card", 0.0) + _f(rows[0].get("k")), 2)
    except Exception:
        pass
    return {k: v for k, v in out.items() if abs(v) > 0.004}
