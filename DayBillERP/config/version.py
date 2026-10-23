# ============================================================
# DayBill ERP - one place for the version and the name shown on screen
# (sidebar, About, Updates). tools/version_info.txt (the .exe file
# properties) carries the same number.
# ============================================================
VERSION = "7.9.0"
APP_NAME = "DayBill ERP"
SUBTITLE = "Billing & Inventory Management"     # Settings ▸ System ▸ Sub name
TAGLINE = "Simple • Fast • Reliable"


def subtitle():
    """The line under the app name (the shop can change it in Settings)."""
    try:
        from config import settings as cfg
        s = str(cfg.get("app_subtitle", "") or "").strip()
        return s or SUBTITLE
    except Exception:
        return SUBTITLE
