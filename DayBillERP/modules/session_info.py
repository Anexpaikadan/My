# ============================================================
# DayBill ERP - who / which database / which year (status bars)
# ------------------------------------------------------------
# One small line used at the bottom of the main window and the POS:
#     👤 admin   ·   🗄 DayBillERP   ·   📅 FY 2026
# ============================================================


def user_name():
    try:
        from modules import permissions
        u = permissions.session_user() or {}
        return str(u.get("username") or u.get("full_name_en") or "").strip()
    except Exception:
        return ""


def database_name():
    try:
        from config.database import load_db_config
        return str(load_db_config().get("database") or "").strip()
    except Exception:
        return ""


def year_label():
    try:
        from modules import financial_year as fy
        y = fy.active_year()
        if not y:
            return ""
        lab = str(y.get("label") or "").strip()
        if lab:
            return lab
        s, e = str(y.get("start_date") or "")[:4], str(y.get("end_date") or "")[:4]
        return ("FY " + s) if s == e else ("FY %s-%s" % (s, e))
    except Exception:
        return ""


def text(sep="   ·   "):
    out = []
    u, d, y = user_name(), database_name(), year_label()
    if u:
        out.append("👤 " + u)
    if d:
        out.append("🗄 " + d)
    if y:
        out.append("📅 " + y)
    return sep.join(out)
