# ============================================================
# DayBill ERP - Financial Year management
# ------------------------------------------------------------
# Real backing for Settings -> Financial Year: create a new FY,
# close/lock one so no more postings land in it, and resolve which
# FY a given date belongs to. Table created by
# database/financial_year_patch.sql (idempotent).
# ============================================================

import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def tables_ready():
    try:
        return bool(db.execute_scalar(
            "SELECT COUNT(*) FROM sys.tables WHERE name='financial_years'"))
    except Exception:
        return False


def list_years():
    try:
        return db.fetchall(
            "SELECT * FROM financial_years ORDER BY start_date DESC") or []
    except Exception:
        return []


def current_year():
    """The FY whose range contains today, else the most recent open one."""
    today = date.today().isoformat()
    try:
        row = db.fetchone(
            "SELECT * FROM financial_years WHERE ? BETWEEN start_date AND end_date",
            (today,))
        if row:
            return row
        return db.fetchone(
            "SELECT TOP 1 * FROM financial_years WHERE is_closed=0 "
            "ORDER BY start_date DESC")
    except Exception:
        return None


def year_for_date(d):
    """Resolve which FY a transaction date falls in (string or date)."""
    ds = d.isoformat() if hasattr(d, "isoformat") else str(d)[:10]
    try:
        return db.fetchone(
            "SELECT * FROM financial_years WHERE ? BETWEEN start_date AND end_date",
            (ds,))
    except Exception:
        return None


def is_locked(d):
    """True if the FY containing date d is closed/locked (blocks posting)."""
    fy = year_for_date(d)
    return bool(fy and fy.get("is_closed"))


def lock_message(d):
    """
    Returns a clear, user-facing error message if `d` falls inside a
    closed financial year, else None. Call this from every transaction
    window's Save validation — the posting engine already refuses to
    journal a locked date, but it fails SILENTLY (no exception), so
    without this check a user could save a document that looks fine
    but never reaches the ledger.
    """
    try:
        if not tables_ready():
            return None
        fy = year_for_date(d)
        if fy and fy.get("is_closed"):
            return (f"'{fy['label']}' ({fy['start_date']} → {fy['end_date']}) "
                    f"is closed. Pick a date in an open financial year, or "
                    f"reopen it in Settings → Financial Year.")
    except Exception:
        pass
    return None


def create_year(start_date, end_date, label=None, opening_balances=None):
    """
    Create a new financial year. start_date/end_date: 'YYYY-MM-DD'.
    Rejects overlap with any existing year. Returns (ok, message).
    """
    try:
        overlap = db.fetchone(
            "SELECT TOP 1 fy_id FROM financial_years WHERE "
            "NOT (end_date < ? OR start_date > ?)", (start_date, end_date))
        if overlap:
            return False, "This date range overlaps an existing financial year."
        if not label:
            y1, y2 = start_date[:4], end_date[:4]
            label = f"FY {y1}" if y1 == y2 else f"FY {y1}-{y2}"
        db.execute(
            "INSERT INTO financial_years (label, start_date, end_date, "
            "is_closed, created_at) VALUES (?,?,?,0,?)",
            (label, start_date, end_date, datetime.now().isoformat()))
        return True, f"Created {label}."
    except Exception as e:
        return False, str(e)[:200]


def close_year(fy_id, lock_transactions=True):
    """
    Close (lock) a financial year. Once closed, is_locked() returns True
    for any date inside it, and posting.py should refuse new postings
    there (checked by callers).
    """
    try:
        db.execute(
            "UPDATE financial_years SET is_closed=1, closed_at=?, "
            "locked=? WHERE fy_id=?",
            (datetime.now().isoformat(), 1 if lock_transactions else 0, fy_id))
        return True, "Financial year closed."
    except Exception as e:
        return False, str(e)[:200]


def reopen_year(fy_id):
    try:
        db.execute("UPDATE financial_years SET is_closed=0, locked=0, "
                  "closed_at=NULL WHERE fy_id=?", (fy_id,))
        return True, "Financial year reopened."
    except Exception as e:
        return False, str(e)[:200]


def set_opening_balance(fy_id, account_id, amount, side="debit"):
    """Record an opening balance for the new year (carried forward)."""
    try:
        db.execute(
            "INSERT INTO fy_opening_balances (fy_id, account_id, amount, side) "
            "VALUES (?,?,?,?)", (fy_id, account_id, amount, side))
        return True
    except Exception:
        return False


# ── Login-selected financial year ─────────────────────────────
def active_year():
    """The FY chosen on the login page (persisted in settings); falls
    back to the open year containing today. None if FY table absent."""
    try:
        from config import settings as cfg
        fid = cfg.get("active_fy_id", None)
        if fid:
            r = db.fetchone("SELECT * FROM financial_years WHERE fy_id=?",
                            (int(fid),))
            if r:
                return r
    except Exception:
        pass
    return current_year()


def set_active(fy_row_or_id):
    """Persist the login page's FY selection for this workstation."""
    from config import settings as cfg
    try:
        if isinstance(fy_row_or_id, dict):
            y = fy_row_or_id
        else:
            y = db.fetchone("SELECT * FROM financial_years WHERE fy_id=?",
                            (int(fy_row_or_id),)) or {}
        cfg.set("active_fy_id", y.get("fy_id"))
        cfg.set("active_fy_label", y.get("label", ""))
        cfg.set("active_fy_start", str(y.get("start_date", ""))[:10])
        cfg.set("active_fy_end", str(y.get("end_date", ""))[:10])
        cfg.save_settings()
        return True
    except Exception:
        return False


def clear_active():
    try:
        from config import settings as cfg
        for k in ("active_fy_id", "active_fy_label",
                  "active_fy_start", "active_fy_end"):
            cfg.set(k, "")
        cfg.save_settings()
    except Exception:
        pass


def guard_active(d):
    """'' when the date may be posted/edited; otherwise the reason.
    Combines the closed-year lock with the LOGIN-SELECTED year rule:
    transactions and edits are only allowed inside the financial year
    chosen at login."""
    msg = lock_message(d)
    if msg:
        return msg
    try:
        # Settings ▸ Financial Year ▸ Lock Previous Financial Years:
        # when OFF, only CLOSED years are blocked (not the whole range
        # outside the year picked at login).
        from config import settings as cfg
        if not cfg.flag("fy_lock_previous", True):
            return ""
    except Exception:
        pass
    try:
        y = active_year()
        if not y:
            return ""
        s = str(y.get("start_date", ""))[:10]
        e = str(y.get("end_date", ""))[:10]
        dd = str(d)[:10]
        if s and e and not (s <= dd <= e):
            return ("Date %s is outside the selected financial year %s "
                    "(%s → %s). Only transactions inside the selected "
                    "year can be added or edited — choose another year "
                    "on the login page." %
                    (dd, y.get("label", ""), s, e))
    except Exception:
        return ""
    return ""
