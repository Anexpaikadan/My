# ============================================================
# DayBill ERP - voucher types (v6.9.3)
# ------------------------------------------------------------
# Every journal entry carries a short voucher-type code, Tally style:
#
#   SI  Sales Invoice        POS POS Sale           SR  Sales Return
#   DN  Debit Note           COS Cost of Sales      PI  Purchase Invoice
#   PR  Purchase Return      CR  Cash Receipt       BR  Bank Receipt
#   CP  Cash Payment         BP  Bank Payment       EX  Expense
#   CT  Contra (cash/bank)   JV  Journal Voucher    OB  Opening Balance
#   ADJ Stock Adjustment     CE  Consumable Entry   PY  Payroll
#   SAL Salary Payment       GOSI GOSI Payment      EOS End of Service
#   LN  Employee Loan        DC  Day Close          SH  Shift
#
# Receipts / payments are CR / BR and CP / BP by the account the money
# went through: a cash (or petty cash / till) account → cash, else bank.
# New journals are numbered per type (CR-000015); older JV numbers stay.
#
#   code_for(source_type, account_ids=None, source_id=None)
#   name(code) / label(code)          "Cash Receipt" / "CR · Cash Receipt"
#   choices()                         [(code, name), …] for filters
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

TYPES = [
    ("SI", "Sales Invoice", "فاتورة مبيعات"),
    ("POS", "POS Sale", "بيع نقاط البيع"),
    ("SR", "Sales Return", "مرتجع مبيعات"),
    ("DN", "Debit Note", "إشعار مدين"),
    ("COS", "Cost of Sales", "تكلفة المبيعات"),
    ("PI", "Purchase Invoice", "فاتورة مشتريات"),
    ("PR", "Purchase Return", "مرتجع مشتريات"),
    ("CR", "Cash Receipt", "سند قبض نقدي"),
    ("BR", "Bank Receipt", "سند قبض بنكي"),
    ("CP", "Cash Payment", "سند صرف نقدي"),
    ("BP", "Bank Payment", "سند صرف بنكي"),
    ("EX", "Expense", "مصروف"),
    ("CT", "Contra (cash / bank)", "تحويل نقدية / بنك"),
    ("JV", "Journal Voucher", "قيد يومية"),
    ("OB", "Opening Balance", "رصيد افتتاحي"),
    ("ADJ", "Stock Adjustment", "تسوية مخزون"),
    ("CE", "Consumable Entry", "صرف للاستهلاك"),
    ("PY", "Payroll", "مسير الرواتب"),
    ("SAL", "Salary Payment", "صرف الرواتب"),
    ("GOSI", "GOSI Payment", "سداد التأمينات"),
    ("EOS", "End of Service", "مكافأة نهاية الخدمة"),
    ("LN", "Employee Loan", "سلفة موظف"),
    ("DC", "Day Close", "إقفال اليوم"),
    ("SH", "Shift", "وردية"),
]
_NAMES = {c: (en, ar) for c, en, ar in TYPES}

# source_type of journal_entries → code (receipt / payment / voucher are
# decided by cash or bank — see code_for)
BY_SOURCE = {
    "sales": "SI", "pos": "POS", "sales_return": "SR", "debit_note": "DN",
    "cogs": "COS", "cogs_return": "COS",
    "purchase": "PI", "purchase_return": "PR", "purchase_return_cost": "PR",
    "expense": "EX", "transfer": "CT",
    "manual": "JV", "journal": "JV", "voucher": "JV", "blank": "JV",
    "opening": "OB", "opening_accounts": "OB", "opening_stock": "OB", "adjustment": "JV",
    "opening_customer": "OB", "opening_supplier": "OB",          # v6.9.5
    "stock_adjust": "ADJ", "cycle_count": "ADJ", "consumption": "CE",
    "payroll": "PY", "salary_payment": "SAL", "gosi_payment": "GOSI", "eos": "EOS",
    "employee_loan": "LN", "day_close": "DC", "shift": "SH",
}
MONEY_IN, MONEY_OUT = ("receipt",), ("payment",)


def _cash_ids():
    """Accounts that hold cash: the default cash, petty cash, the cash
    tender account and every branch's cash / petty cash account."""
    ids = set()
    try:
        from modules import account_defaults as ad
        for fn in (ad.cash, getattr(ad, "petty_cash", None)):
            if fn:
                a = fn()
                if a:
                    ids.add(a)
        a = ad.method_account("cash")
        if a:
            ids.add(a)
    except Exception:
        pass
    try:                                  # branch-wise cash accounts (when set up)
        if db.execute_scalar("SELECT OBJECT_ID('branch_cash_accounts','U')") is not None:
            for r in db.fetchall("SELECT cash_account_id, petty_cash_account_id "
                                 "FROM branch_cash_accounts") or []:
                for k in ("cash_account_id", "petty_cash_account_id"):
                    if r.get(k):
                        ids.add(r[k])
    except Exception:
        pass
    return ids


def code_for(source_type, account_ids=None, source_id=None, reference=None):
    """The voucher-type code of a journal about to be posted (or already
    posted: pass its line accounts)."""
    st = str(source_type or "").strip().lower()
    if st == "expense" and not source_id:
        st = "payment"            # an expense paid from a voucher = Cash / Bank Payment
    if st == "adjustment" and str(reference or "").upper().startswith("OPEN"):
        return "OB"
    if st in MONEY_IN or st in MONEY_OUT:
        accs = set(a for a in (account_ids or []) if a)
        cash = bool(accs & _cash_ids()) if accs else True
        if st in MONEY_IN:
            return "CR" if cash else "BR"
        return "CP" if cash else "BP"
    if st == "sales" and source_id:
        try:                                  # a debit note is saved as a sales invoice
            if str(db.execute_scalar("SELECT invoice_kind FROM sales_invoices WHERE invoice_id=?",
                                     (source_id,)) or "").lower() == "debit":
                return "DN"
        except Exception:
            pass
    return BY_SOURCE.get(st, "JV")


def name(code, arabic=False):
    en, ar = _NAMES.get(str(code or "").upper(), (str(code or "Journal"), str(code or "")))
    return ar if arabic else en


def label(code):
    c = str(code or "JV").upper()
    return "%s · %s" % (c, name(c))


def choices():
    return [(c, en) for c, en, _ar in TYPES]


def next_number(code):
    """CR-000015 — numbered per voucher type."""
    c = str(code or "JV").upper()
    try:
        n = int(db.execute_scalar("SELECT COUNT(*) FROM journal_entries WHERE voucher_type=?",
                                  (c,)) or 0)
    except Exception:
        n = int(db.execute_scalar("SELECT COUNT(*) FROM journal_entries") or 0)
    for i in range(n + 1, n + 100000):
        num = "%s-%06d" % (c, i)
        if not db.execute_scalar("SELECT COUNT(*) FROM journal_entries WHERE journal_number=?",
                                 (num,)):
            return num
    return "%s-%06d" % (c, n + 1)


_HAS_COL = {}


def col(alias="je"):
    """SQL for the voucher_type column ('NULL' before the v6.9.3 update)."""
    if "v" not in _HAS_COL:
        try:
            _HAS_COL["v"] = db.execute_scalar(
                "SELECT COL_LENGTH('journal_entries','voucher_type')") is not None
        except Exception:
            _HAS_COL["v"] = False
    return ("%s.voucher_type" % alias) if _HAS_COL["v"] else "NULL"


def of_journal(row):
    """Code of a saved journal row (dict with voucher_type / source_type)."""
    c = (row or {}).get("voucher_type")
    if c:
        return str(c).upper()
    return BY_SOURCE.get(str((row or {}).get("source_type") or "").lower(), "JV")
