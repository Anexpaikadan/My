# ============================================================
# DayBill ERP - Audit trail helper
# (Converted from BillPOS PHP includes/functions.php audit())
# ------------------------------------------------------------
# Usage:
#   from modules import audit
#   audit.set_user(current_user_dict)        # once, after login
#   audit.log("create", "sales", invoice_id, "INV-000123 total 115.00")
#
# Never raises: an audit failure must not break a transaction.
# Desktop app, so the PHP ip_address column becomes workstation name.
# ============================================================

import sys, os, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db

_user = {}


def set_user(user):
    """Remember the logged-in user (dict with user_id) for this session."""
    global _user
    _user = user or {}


def enabled():
    try:
        return bool(db.execute_scalar(
            "SELECT COUNT(*) FROM sys.tables WHERE name='audit_logs'"))
    except Exception:
        return False


def _category_on(action, module):
    """Settings ▸ Audit: per-category switches."""
    try:
        from config import settings as cfg
        a, m = str(action).lower(), str(module).lower()
        if m == "login" or a in ("login", "logout"):
            key = "audit_login"
        elif m == "settings":
            key = "audit_settings"
        elif a in ("delete", "clear", "deactivate", "void"):
            key = "audit_deleted"
        elif "cost" in a or "cost" in m:
            key = "audit_cost_changes"
        elif "price" in a or m in ("products",) and a in ("bulk_update", "price_change"):
            key = "audit_price_changes"
        else:
            key = "audit_user_activity"
        return cfg.flag(key, True)
    except Exception:
        return True


def log(action, module, ref_id=None, details=""):
    """Write one audit row. Silently no-ops if the table is missing."""
    if not enabled():
        return
    if not _category_on(action, module):
        return
    try:
        db.execute(
            "INSERT INTO audit_logs (user_id, action, module, ref_id, details, "
            "workstation) VALUES (?,?,?,?,?,?)",
            (_user.get("user_id"), str(action)[:50], str(module)[:50],
             str(ref_id)[:50] if ref_id is not None else None,
             str(details)[:4000] if details else None,
             platform.node()[:100]))
    except Exception:
        pass
