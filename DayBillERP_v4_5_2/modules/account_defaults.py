# ============================================================
# DayBill ERP - Default Account Resolver
# ------------------------------------------------------------
# Single source of truth for "which ledger account does each role
# use". Posting and reporting ask here instead of hardcoding codes.
#
# Resolution order for every key:
#   1. config/app_settings.json override  (acc_* key, if set)
#   2. account_settings table              (set by the SQL patch / UI)
#   3. built-in fallback code              (so it always works)
#
# A value may be stored as an account CODE ('1100'), a NAME, or an
# account_id; all three resolve correctly.
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db
try:
    from config import settings as cfg
except Exception:                       # settings optional at import time
    cfg = None

# Role key  ->  built-in fallback account code
FALLBACK = {
    "default_cash":            "1100",
    "default_bank":            "1110",
    "default_card":            "1120",
    "default_savings":         "1130",
    "default_gateway":         "1140",
    "default_petty_cash":      "1150",
    "default_sales":           "4100",
    "default_purchase":        "1300",
    "default_inventory":       "1300",
    "default_receivable":      "1200",
    "default_payable":         "2100",
    "default_tax_payable":     "2210",
    "default_tax_receivable":  "2220",
    "default_cogs":            "5100",
    "default_salary_expense":  "5200",
    "default_discount":        "5400",
    "default_round_off":       "5900",
    "default_sales_return":    "4200",
    "default_purchase_return": "5150",
    "default_stock_adjust":    "5160",
    "default_opening_equity":  "3400",
}

# Role key  ->  legacy app_settings.json key (so the Settings > Accounting
# section and the Default Accounts tab both feed the same resolver).
JSON_KEYS = {
    "default_cash":            "acc_cash",
    "default_bank":            "acc_bank",
    "default_card":            "acc_card",
    "default_savings":         "acc_savings",
    "default_gateway":         "acc_gateway",
    "default_petty_cash":      "acc_petty_cash",
    "default_sales":           "acc_sales",
    "default_purchase":        "acc_purchase",
    "default_inventory":       "acc_inventory",
    "default_receivable":      "acc_ar",
    "default_payable":         "acc_ap",
    "default_tax_payable":     "acc_vat_output",
    "default_tax_receivable":  "acc_vat_input",
    "default_cogs":            "acc_cogs",
    "default_salary_expense":  "acc_salary_expense",
    "default_discount":        "acc_discount",
    "default_round_off":       "acc_round_off",
    "default_sales_return":    "acc_sales_return",
    "default_purchase_return": "acc_purchase_return",
    "default_stock_adjust":    "acc_stock_adjust",
    "default_opening_equity":  "acc_opening_equity",
}

_cache = {}


def invalidate():
    """Call after the user changes any default-account setting."""
    _cache.clear()


# ── low-level helpers ─────────────────────────────────────────
def _id_from_code(code):
    if not code:
        return None
    return db.execute_scalar(
        "SELECT TOP 1 account_id FROM accounts WHERE account_code=?", (str(code),))


def _id_from_name(name):
    if not name:
        return None
    return db.execute_scalar(
        "SELECT TOP 1 account_id FROM accounts "
        "WHERE account_name_en=? OR account_name_ar=?", (name, name))


def _to_id(value):
    """Resolve a code / name / id string to an account_id."""
    if value in (None, ""):
        return None
    s = str(value).strip()
    acc = _id_from_code(s)          # codes can be numeric strings -> try first
    if acc:
        return acc
    acc = _id_from_name(s)
    if acc:
        return acc
    if s.isdigit():                 # last resort: treat as a raw account_id
        ok = db.execute_scalar(
            "SELECT TOP 1 account_id FROM accounts WHERE account_id=?", (int(s),))
        if ok:
            return ok
    return None


def _setting_value(key):
    """The configured code/name for a role key, or None (no fallback)."""
    if cfg is not None and key in JSON_KEYS:
        v = cfg.get(JSON_KEYS[key])
        if v not in (None, ""):
            return v
    try:
        row = db.fetchone(
            "SELECT account_id, account_code FROM account_settings WHERE setting_key=?",
            (key,))
        if row:
            return row.get("account_code") or row.get("account_id")
    except Exception:
        pass
    return None


# ── public API ────────────────────────────────────────────────
def acc(key):
    """Return the account_id for a role key (e.g. 'default_cash')."""
    if key in _cache:
        return _cache[key]
    acc_id = _to_id(_setting_value(key))
    if acc_id is None:
        acc_id = _id_from_code(FALLBACK.get(key))
    _cache[key] = acc_id
    return acc_id


# Convenience getters used by the posting engine
def cash():            return acc("default_cash")
def bank():            return acc("default_bank")
def card():            return acc("default_card")
def savings():         return acc("default_savings")
def gateway():         return acc("default_gateway")
def petty_cash():      return acc("default_petty_cash")
def sales():           return acc("default_sales")
def purchase():        return acc("default_purchase")
def inventory():       return acc("default_inventory")
def receivable():      return acc("default_receivable")
def payable():         return acc("default_payable")
def tax_payable():     return acc("default_tax_payable")
def tax_receivable():  return acc("default_tax_receivable")
def cogs():            return acc("default_cogs")
def salary_expense():  return acc("default_salary_expense")
def discount():        return acc("default_discount")
def round_off():       return acc("default_round_off")
def sales_return():    return acc("default_sales_return")
def purchase_return(): return acc("default_purchase_return")
def stock_adjust():    return acc("default_stock_adjust")
def opening_equity():  return acc("default_opening_equity")


def method_account(method):
    """Ledger account for a POS/payment tender ('cash','card','bank_transfer','gateway')."""
    m = (method or "cash").lower()
    try:
        a = db.execute_scalar(
            "SELECT TOP 1 account_id FROM payment_method_accounts "
            "WHERE method_code=? AND is_active=1", (m,))
        if a:
            return a
    except Exception:
        pass
    # card / mada / cheque settle to the bank account — the same account the
    # sales invoices, POS bills, purchases and refunds use (v5.26: receipts,
    # payments and expenses by card or cheque went to other accounts)
    if m in ("card", "mada", "visa", "cheque", "check", "bank", "bank_transfer",
             "transfer"):
        return bank() or cash()
    if m in ("gateway", "online"):           return gateway() or bank() or cash()
    return cash()


def branch_cash_account(branch_id, kind="cash"):
    """Branch-wise cash/petty/bank account; falls back to the global default."""
    col = {"cash": "cash_account_id", "petty": "petty_cash_account_id",
           "bank": "bank_account_id"}.get(kind, "cash_account_id")
    if branch_id:
        try:
            a = db.execute_scalar(
                f"SELECT TOP 1 {col} FROM branch_cash_accounts WHERE branch_id=?",
                (branch_id,))
            if a:
                return a
        except Exception:
            pass
    return {"cash": cash, "petty": petty_cash, "bank": bank}.get(kind, cash)()


def all_accounts():
    """[(account_id, code, name_en, type)] for UI pickers."""
    try:
        rows = db.fetchall(
            "SELECT account_id, account_code, account_name_en, account_type "
            "FROM accounts WHERE is_active=1 ORDER BY account_code")
        return [(r["account_id"], r["account_code"], r["account_name_en"],
                 r["account_type"]) for r in rows]
    except Exception:
        return []


def set_default(key, code):
    """Persist a default-account selection (stores the account CODE)."""
    acc_id = _id_from_code(code)
    # 1) DB map (authoritative for SQL/reporting)
    try:
        exists = db.execute_scalar(
            "SELECT COUNT(*) FROM account_settings WHERE setting_key=?", (key,))
        if exists:
            db.execute(
                "UPDATE account_settings SET account_code=?, account_id=?, "
                "updated_at=GETDATE() WHERE setting_key=?", (code, acc_id, key))
        else:
            db.execute(
                "INSERT INTO account_settings (setting_key, account_code, account_id) "
                "VALUES (?,?,?)", (key, code, acc_id))
    except Exception:
        pass
    # 2) mirror into app_settings.json so the Settings UI reflects it
    if cfg is not None and key in JSON_KEYS:
        cfg.set(JSON_KEYS[key], code)
        try:
            cfg.save_settings()
        except Exception:
            pass
    invalidate()
    return acc_id


def set_method_account(method_code, account_id):
    try:
        exists = db.execute_scalar(
            "SELECT COUNT(*) FROM payment_method_accounts WHERE method_code=?",
            (method_code,))
        if exists:
            db.execute("UPDATE payment_method_accounts SET account_id=? "
                       "WHERE method_code=?", (account_id, method_code))
        else:
            db.execute("INSERT INTO payment_method_accounts (method_code, account_id) "
                       "VALUES (?,?)", (method_code, account_id))
    except Exception:
        pass
