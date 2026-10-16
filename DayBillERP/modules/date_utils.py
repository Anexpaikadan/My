# ============================================================
# DayBill ERP - Date validation (shared)
# ------------------------------------------------------------
# One place that decides whether a date typed/picked into a
# transaction window (Sales Invoice, Purchase Invoice, Returns,
# Vouchers, ...) is acceptable before it reaches the database.
# Used alongside modules.financial_year for the FY-lock check.
# ============================================================

from datetime import datetime, date

_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def parse_date_strict(s):
    """Return a real `date` object, or None if the string isn't a valid
    calendar date in any of the accepted formats (no silent fallback to
    today — unlike the date-picker's internal parser, this one is used
    for validation, so a bad string must be reported, not guessed away)."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in _FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def validate_invoice_date(s):
    """
    Returns (ok, iso_date_or_None, error_message_or_None).
    Only checks that it's a genuine calendar date (rejects "31/02/2026",
    "abc", stray punctuation, etc.) and normalizes it to YYYY-MM-DD for
    storage. Deliberately does not restrict past/future dates — backdated
    corrections and advance-dated documents are both legitimate in
    accounting; the Financial Year lock (see modules.financial_year) is
    the real business-rule gate for "too old to edit".
    """
    if not (s or "").strip():
        return False, None, "Date is required."
    d = parse_date_strict(s)
    if d is None:
        return False, None, (f"'{s}' is not a valid date. Use YYYY-MM-DD "
                             f"or DD/MM/YYYY.")
    return True, d.isoformat(), None
