# ============================================================
# DayBill ERP - Document numbering (shared)
# ------------------------------------------------------------
# One reliable "next number" function used by every document window
# (Sales Invoice, Sales Return, Purchase Invoice, Purchase Return,
# and any future voucher type) so numbering behaves identically
# everywhere instead of each screen having its own copy.
#
# Format: {PREFIX}-{YYYYMM}-{000001}  e.g. SR-202607-000001
# Scans the existing column for the highest number THIS MONTH, then
# verifies the candidate isn't already taken (handles gaps/edits),
# bumping until a free number is found.
# ============================================================

import sys, os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def next_number(table: str, column: str, prefix: str, width: int = 6) -> str:
    """
    table  : e.g. "sales_returns", "purchase_invoices"
    column : e.g. "return_number", "invoice_number"
    prefix : e.g. "SR", "PI"
    Returns a fresh, verified-unused number string.
    """
    ym = datetime.now().strftime("%Y%m")
    pat = f"{prefix}-{ym}-"
    mx = 0
    try:
        rows = db.fetchall(
            f"SELECT {column} FROM {table} WHERE {column} LIKE ?", (pat + "%",)) or []
        for r in rows:
            tail = str(r[column]).rsplit("-", 1)[-1]
            if tail.isdigit():
                mx = max(mx, int(tail))
    except Exception:
        mx = 0

    # verify the candidate is actually free (covers manual edits / gaps),
    # bumping forward if it's somehow already taken
    for _ in range(50):
        candidate = f"{pat}{mx + 1:0{width}d}"
        try:
            taken = db.execute_scalar(
                f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (candidate,))
        except Exception:
            taken = 0
        if not taken:
            return candidate
        mx += 1
    # extremely unlikely fallback
    return f"{pat}{mx + 1:0{width}d}"


def next_party_code(table: str, column: str, prefix: str, width: int = 4) -> str:
    """Next free customer/supplier code, e.g. C0001, C0002 …
    Uses Settings > Customer/Supplier prefix. Scans existing codes with
    that prefix for the highest numeric tail, then verifies it's free."""
    prefix = (prefix or "").strip()
    mx = 0
    try:
        rows = db.fetchall(f"SELECT {column} FROM {table} WHERE {column} LIKE ?",
                           (prefix + "%",)) or []
        for r in rows:
            tail = str(r.get(column) or "")[len(prefix):]
            if tail.isdigit():
                mx = max(mx, int(tail))
    except Exception:
        mx = 0
    n = mx + 1
    for _ in range(100000):
        code = f"{prefix}{n:0{width}d}"
        try:
            if not db.execute_scalar(f"SELECT COUNT(*) FROM {table} WHERE {column}=?",
                                     (code,)):
                return code
        except Exception:
            return code
        n += 1
    return f"{prefix}{n:0{width}d}"
