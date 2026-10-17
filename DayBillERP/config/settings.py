# ============================================================
# Saudi Arabia ERP - App Settings & Theme Manager
# ============================================================

import json
import os

try:        # exe: next to DayBillERP.exe (not the temp unpack folder)
    from config.paths import config_file as _cfg_file
    SETTINGS_FILE = _cfg_file("app_settings.json")
except Exception:
    SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "app_settings.json")

# ── Color Themes ──────────────────────────────────────────────
THEMES = {
    # Modern Windows 10/11 look: navy sidebar, blue accent, light-grey
    # page, white cards / windows, coloured KPI tiles.
    "daybill": {
        "name":          "DayBill Modern",
        "primary":       "#2563EB",
        "primary_dark":  "#1D4ED8",
        "primary_light": "#EAF1FE",
        "accent":        "#22C55E",
        "accent_dark":   "#16A34A",
        "sidebar_bg":    "#0F1D3A",
        "sidebar_text":  "#E6EBF5",
        "sidebar_hover": "#1B2C52",
        "sidebar_active":"#2563EB",
        "sidebar_muted": "#9DAACB",
        "sidebar_field": "#1A2B50",
        "topbar_bg":     "#FFFFFF",
        "content_bg":    "#F3F5F9",
        "card_bg":       "#FFFFFF",
        "text_primary":  "#111827",
        "text_secondary":"#4B5563",
        "border":        "#E2E6EE",
        "heading_bg":    "#F1F3F7",
        "select_bg":     "#2F6FED",
        "select_fg":     "#FFFFFF",
        "field_border":  "#CDD4DF",
        "success":       "#16A34A",
        "warning":       "#D97706",
        "danger":        "#DC2626",
        "info":          "#2563EB",
        "tile_blue":     "#2F7CF6",
        "tile_green":    "#1FAA59",
        "tile_orange":   "#F59E0B",
        "tile_purple":   "#8B5CF6",
        "slate":         "#5B6B82",
    },
    # the previous purple DayBill brand (Settings ▸ System ▸ Theme)
    "purple": {
        "name":          "DayBill Purple (classic)",
        "primary":       "#3A1FD6",
        "primary_dark":  "#2A14A8",
        "primary_light": "#ECE9FB",
        "accent":        "#7ED957",
        "accent_dark":   "#5FB840",
        "sidebar_bg":    "#2A14A8",
        "sidebar_text":  "#FFFFFF",
        "sidebar_hover": "#3A1FD6",
        "topbar_bg":     "#FFFFFF",
        "content_bg":    "#F6F5FD",
        "card_bg":       "#FFFFFF",
        "text_primary":  "#1A1438",
        "text_secondary":"#6B7280",
        "border":        "#E3E0F4",
        "success":       "#5FB840",
        "warning":       "#D97706",
        "danger":        "#DC2626",
        "info":          "#3A1FD6",
    },
    "green": {
        "name":         "Saudi Green",
        "primary":      "#006C35",   # Saudi flag green
        "primary_dark": "#004D26",
        "primary_light":"#E8F5EE",
        "accent":       "#FFFFFF",
        "accent_dark":  "#004D26",
        "sidebar_bg":   "#004D26",
        "sidebar_text": "#FFFFFF",
        "sidebar_hover":"#006C35",
        "topbar_bg":    "#FFFFFF",
        "content_bg":   "#F5F7FA",
        "card_bg":      "#FFFFFF",
        "text_primary": "#1A1A2E",
        "text_secondary":"#6B7280",
        "border":       "#E5E7EB",
        "success":      "#16A34A",
        "warning":      "#D97706",
        "danger":       "#DC2626",
        "info":         "#2563EB",
    },
    "blue": {
        "name":         "Corporate Blue",
        "primary":      "#1E40AF",
        "primary_dark": "#1E3A8A",
        "primary_light":"#EFF6FF",
        "accent":       "#FFFFFF",
        "accent_dark":  "#1E3A8A",
        "sidebar_bg":   "#1E3A8A",
        "sidebar_text": "#FFFFFF",
        "sidebar_hover":"#1E40AF",
        "topbar_bg":    "#FFFFFF",
        "content_bg":   "#F0F4FF",
        "card_bg":      "#FFFFFF",
        "text_primary": "#111827",
        "text_secondary":"#6B7280",
        "border":       "#E5E7EB",
        "success":      "#16A34A",
        "warning":      "#D97706",
        "danger":       "#DC2626",
        "info":         "#2563EB",
    },
    "dark": {
        "name":          "Dark Mode",
        "primary":       "#6C5CE7",
        "primary_dark":  "#5849C4",
        "primary_light": "#2A2640",
        "accent":        "#7ED957",
        "accent_dark":   "#5FB840",
        "sidebar_bg":    "#15131F",
        "sidebar_text":  "#E8E6F5",
        "sidebar_hover": "#211D33",
        "topbar_bg":     "#1C1930",
        "content_bg":    "#121020",
        "card_bg":       "#1C1930",
        "text_primary":  "#EDEBFA",
        "text_secondary":"#9C97BD",
        "border":        "#2E2A47",
        "success":       "#5FB840",
        "warning":       "#D97706",
        "danger":        "#EF4444",
        "info":          "#6C5CE7",
    }
}


def _complete_theme(t):
    """Every theme gets the newer keys (sidebar active / muted, table
    heading + selection colours, KPI tile colours)."""
    t.setdefault("sidebar_active", t["primary"])
    t.setdefault("sidebar_muted", "#9AA3C7" if t.get("name") != "Dark Mode" else "#6F6A90")
    t.setdefault("heading_bg", t["content_bg"])
    t.setdefault("select_bg", t["primary"])
    t.setdefault("select_fg", "#FFFFFF")
    t.setdefault("field_border", t["border"])
    t.setdefault("slate", "#5B6B82")
    t.setdefault("tile_blue", t.get("info", t["primary"]))
    t.setdefault("tile_green", t["success"])
    t.setdefault("tile_orange", "#F97316")
    t.setdefault("tile_purple", "#7C3AED")
    return t


for _t in THEMES.values():
    _complete_theme(_t)


# ── v6.2.1: more themes, and a theme from your own colour ─────
def _rgb(c):
    c = str(c or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise ValueError("not a colour: %r" % c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _hexc(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(c1, c2, t):
    """Colour c1 moved towards c2 by t (0 … 1)."""
    a, b = _rgb(c1), _rgb(c2)
    return _hexc([a[i] + (b[i] - a[i]) * t for i in range(3)])


def valid_color(c):
    try:
        _rgb(c)
        return True
    except Exception:
        return False


def _lum(c):
    r, g, b = (v / 255.0 for v in _rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def make_theme(name, primary, sidebar=None, content=None):
    """A full theme from one main colour (white text must stay readable on
    it, so a very light colour is made darker)."""
    p = _hexc(_rgb(primary))
    n = 0
    while _lum(p) > 0.48 and n < 8:
        p = mix(p, "#000000", 0.15)
        n += 1
    sb = _hexc(_rgb(sidebar)) if sidebar else mix(p, "#000000", 0.66)
    return _complete_theme({
        "name": name, "primary": p, "primary_dark": mix(p, "#000000", 0.18),
        "primary_light": mix(p, "#FFFFFF", 0.90),
        "accent": "#22C55E", "accent_dark": "#16A34A",
        "sidebar_bg": sb, "sidebar_text": "#E6EBF5", "sidebar_hover": mix(sb, "#FFFFFF", 0.10),
        "sidebar_active": p, "sidebar_muted": mix(sb, "#FFFFFF", 0.60),
        "sidebar_field": mix(sb, "#FFFFFF", 0.08),
        "topbar_bg": "#FFFFFF", "content_bg": content or mix("#F3F5F9", p, 0.03),
        "card_bg": "#FFFFFF", "text_primary": "#111827", "text_secondary": "#4B5563",
        "border": "#E2E6EE", "heading_bg": "#F1F3F7", "select_bg": p, "select_fg": "#FFFFFF",
        "field_border": "#CDD4DF", "success": "#16A34A", "warning": "#D97706",
        "danger": "#DC2626", "info": p, "tile_blue": "#2F7CF6", "tile_green": "#1FAA59",
        "tile_orange": "#F59E0B", "tile_purple": "#8B5CF6", "slate": "#5B6B82"})


for _t in THEMES.values():          # older themes: the search box in the side menu
    _t.setdefault("sidebar_field", mix(_t["sidebar_bg"], "#FFFFFF", 0.08))
THEMES["teal"] = make_theme("Teal", "#0F766E", "#0B2F2D")
THEMES["graphite"] = make_theme("Graphite", "#334155", "#111827", "#F4F5F7")
THEMES["maroon"] = make_theme("Maroon", "#9F1239", "#3B0A1A")
THEMES["sand"] = make_theme("Desert Sand", "#B45309", "#3A2512", "#F8F5F0")
THEMES["green"]["name"] = "Saudi Green"
THEMES["daybill"]["name"] = "DayBill Blue"

# the order in the 🎨 Theme picker and Settings ▸ System
THEME_ORDER = ["daybill", "green", "blue", "teal", "graphite", "maroon", "sand", "purple"]


def theme_choices():
    """[(key, name)] — the themes you can pick (+ your own colour)."""
    out = [(k, THEMES[k]["name"]) for k in THEME_ORDER if k in THEMES]
    if valid_color(_settings.get("theme_custom_color")):
        out.append(("custom", "My colour"))
    return out


def _resolve_theme():
    name = _settings.get("theme") or "daybill"
    if name == "custom":
        c = _settings.get("theme_custom_color")
        if valid_color(c):
            THEMES["custom"] = make_theme("My colour", c)
        else:
            name = "daybill"
    return THEMES.get(name, THEMES["daybill"])


def set_theme(name, custom_color=None):
    """Switch the theme now (screens built after this use it)."""
    global _theme
    if custom_color:
        if not valid_color(custom_color):
            raise ValueError("Not a colour: %s" % custom_color)
        _settings["theme_custom_color"] = _hexc(_rgb(custom_color))
        name = "custom"
    if name not in THEMES and name != "custom":
        name = "daybill"
    _settings["theme"] = name
    _settings["theme_user_chosen"] = True
    _theme = _resolve_theme()
    return _theme

DEFAULT_SETTINGS = {
    "theme":            "daybill",
    "language":         "en",
    "font_size":        11,
    "ui_text_size":     "125%",   # whole-app text size (ui/zoom.py)
    "sidebar_collapsed": False,   # ☰ folds the side menu to icons
    "win11_frame":      True,     # Windows 11 title bar (white, round corners)
    "product_code_max_len": 8,    # product code: at most 8 characters (0 = no limit)
    "window_width":     1280,
    "window_height":    780,
    "window_maximized": False,
    "sidebar_width":    220,
    "date_format":      "dd/MM/yyyy",
    "decimal_places":   2,
    "currency":         "SAR",
    "vat_enabled":            True,
    "sales_price_tax_mode":   "inclusive",
    "purchase_cost_tax_mode": "exclusive",
    "tax_sales_rate":         15,
    "tax_purchase_rate":      15,
    # Checkbox settings whose behaviour is ON unless the user turns it
    # off. Listed here so the Settings screen shows the same state the
    # app actually uses (and saving a section never flips them off).
    "apply_vat_sales": True, "apply_vat_sales_return": True,
    "apply_vat_pos": True, "apply_vat_purchase": True,
    "apply_vat_purchase_return": True, "pos_print_vat_no": True,
    "allow_price_edit": True, "allow_discount_edit": True,
    "allow_sales_return": True, "allow_purchase_return": True,
    "allow_edit_confirmed": True,
    "ai_enabled": True, "ai_api_key": "", "ai_model_fast": "claude-haiku-5-5",
    "ai_model_vision": "claude-sonnet-5-5", "ai_markup_pct": 25,
    "ai_auto_translate": True, "ai_dup_check": True, "ai_autofill": True,
    "show_stock_during_sales": True, "cart_dup_check": True,
    "warn_sale_below_cost": True, "sales_auto_number": True,
    "pos_fullscreen": True, "pos_auto_focus_barcode": True,
    "pos_extra_tenders": "stc_pay, tabby, tamara", "pos_require_shift": False, "pos_blind_count": True,
    "pos_offline_queue": True,
    "expiry_alert_days": 30, "hr_deduct_unpaid_days": True,
    "gosi_old_pension_pct": 9.0,
    "gosi_new_pension_steps": "2024-07-03:9,2025-07-01:9.5,2026-07-01:10,2027-07-01:10.5,2028-07-01:11",
    "gosi_new_system_from": "2024-07-03", "gosi_saned_pct": 0.75, "gosi_hazard_pct": 2.0,
    "gosi_nonsaudi_employer_pct": 2.0, "gosi_wage_cap": 45000,
    "pos_auto_print": True, "pos_enable_hold": True, "pos_qr_print": True, "pos_show_cost_in_search": True,
    "pos_show_vat_column": True, "pos_show_vat_receipt": True, "receipt_vat_per_item": True, "pos_columns": "", "confirm_close_windows": True, "pos_ui_size": "medium",
    "acc_auto_posting": True, "backup_on_exit": True,
    "cust_auto_code": True, "sup_auto_code": True,
    "cust_over_credit_warn": True, "fy_lock_previous": True,
    "fy_warn_before_close": True,
    "pay_method_cash": True, "pay_method_bank": True,
    "pay_method_credit_card": True, "pay_method_debit_card": True,
    "pay_method_cheque": True, "pay_allow_partial": True,
    "audit_user_activity": True, "audit_price_changes": True,
    "audit_cost_changes": True, "audit_deleted": True,
    "audit_login": True, "audit_settings": True,
    "cust_prefix": "C", "sup_prefix": "S",
    # v6.9.3 entry windows stay open after Save: new | keep | close
    "after_save_mode": "new",
    # v6.9.2 loyalty points (off until the shop switches them on)
    "loyalty_enabled": False, "loyalty_sar_per_point": 10, "loyalty_point_value": 0.10,
    "loyalty_min_redeem": 50,
    "sales_start_no": 1001, "purchase_start_no": 1,
    "pwd_min_length": 4, "perf_search_limit": 50,
    "pos_paper_size": "80mm", "auto_update_cost": True,
    "cost_basis": "Last Purchase", "barcode_check_digit": True,
    "barcode_length": 5, "plu_enabled": True,
    "barcode_start": 10001, "barcode_system_locked": True,
    # v6.9.5: every product's own 5-digit system barcode + which barcode labels print
    "system_barcode_start": 10001, "label_barcode_source": "system",
    "pos_show_favorites": True,
    # WhatsApp (Settings ▸ WhatsApp)
    "wa_enabled": False, "wa_mode": "WhatsApp app (free — you press Send)",
    "wa_open_with": "WhatsApp Desktop app", "wa_country_code": "966",
    "wa_template_lang": "en",
    # options that live on other screens too, shown in Settings as well
    "auto_history_box": True, "auto_unit_barcode": True,
    "acc_post_stock_adjust": True, "pos_print_format": "thermal",
    "pos_open_drawer": True, "pos_voice_not_found": True,
    "auto_migrate": True, "voice_search_enabled": False,
    "plu_barcode_format": "EAN13_WEIGHT_2",
    # printed documents
    "time_format": "24-hour", "fiscal_year_start": "01-01",
    "country_tax_profile": "Saudi Arabia VAT 15%",
    # POS look
    "pos_touchscreen": False, "pos_show_images": False,
    # scale export / stock
    "plu_export_path": "", "plu_export_on_save": False,
    # security
    "pwd_expiry_days": 0,
    # alerts
    "notify_low_stock": True, "notify_payment_due": True,
    "notify_payment_due_days": 3, "notify_backup": True,
    "pay_auto_receipt": False,
    # printing (Settings ▸ Printing / Printer Management)
    "print_direct": True, "print_copies": 1,
    "printer_dotmatrix": "", "printer_labels": "",
    # v6.4 — stock count / prices / cashier watch / evening jobs
    "count_needs_approval": True, "count_every_a_days": 7, "count_every_b_days": 30,
    "count_every_c_days": 90, "count_list_size": 40,
    "price_alert_pct": 2, "price_rounding": "0.25",
    "cashier_watch_short": 20,
    "owner_report_enabled": False, "owner_report_time": "23:00",
    "cloud_backup_enabled": False, "cloud_backup_folder": "", "cloud_backup_time": "23:30",
    "cloud_backup_keep": 14,
    # v6.5 — evening report language / template, WhatsApp message count
    "owner_report_lang": "en", "wa_owner_template": "", "wa_price_per_msg": 0,
    # v6.6 — HR & payroll
    "hr_sick_tiers": True, "hr_overtime_from_attendance": True, "hr_leave_carry": True,
    "hr_daily_hours": 8, "hr_wage_basis": "actual", "hr_doc_alert_days": 30,
    "hr_probation_days": 90, "hr_ramadan_hours": 6, "hr_ramadan_dates": "",
    "ui_compact": True,
    "ui_form_style": True,
    "tally_api_key": "",
    "tally_form_customer": "",
    "tally_form_supplier": "",
    "tally_form_feedback": "",
    "tally_auto_check": False,
    "receipt_feedback_qr": False,
}

_settings = {}
_theme = {}
# saved locked to this computer (Windows DPAPI) — see config/secret_box.py
SECRET_KEYS = ("ai_api_key", "wathq_api_key", "van_relay_key", "wa_api_token",
               "smtp_password", "relay_password",
               "tally_api_key", "jotform_api_key")        # v6.9: form keys locked too


def load_settings() -> dict:
    global _settings, _theme
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            _settings = {**DEFAULT_SETTINGS, **json.load(f)}
    else:
        _settings = DEFAULT_SETTINGS.copy()
    # v5.27: API keys are stored locked to this computer — open them here
    _plain_on_disk = False
    try:
        from config import secret_box as _sb
        for _k in SECRET_KEYS:
            _v = _settings.get(_k)
            if _sb.is_protected(_v):
                _settings[_k] = _sb.reveal(_v)
            elif _v and _sb.available():
                _plain_on_disk = True
    except Exception:
        pass
    if _plain_on_disk:            # an older file: lock its keys once
        try:
            save_settings()
        except Exception:
            pass
    # v6.5: an older Claude model saved in Settings ▸ AI → the current one
    for _k in ("ai_model_fast", "ai_model_vision"):
        if str(_settings.get(_k) or "").startswith("claude-haiku-4-5"):
            _settings[_k] = "claude-haiku-5-5"
    # One-time brand migration: older installs saved theme "green"/"blue".
    # Move them to the DayBill brand theme unless the user explicitly
    # set a custom theme flag.
    if _settings.get("theme") in ("green", "blue") and \
       not _settings.get("theme_user_chosen"):
        _settings["theme"] = "daybill"
        try:
            save_settings()
        except Exception:
            pass
    # v5.22.1: new products / units get 6-digit barcodes. Installs still on
    # the old default (13) move to 6 once; a length the user chose stays.
    if not _settings.get("barcode_six_digit_v5221"):
        if str(_settings.get("barcode_length", 13)).strip() in ("13", "13.0", ""):
            _settings["barcode_length"] = 6
        _settings["barcode_six_digit_v5221"] = True
        try:
            save_settings()
        except Exception:
            pass
    # v6.9.5: new products / units get 5-digit numbers (10001…). Installs on
    # the 6-digit default move to 5 once; a length the user chose stays.
    if not _settings.get("barcode_five_digit_v695"):
        if str(_settings.get("barcode_length", 6)).strip() in ("6", "6.0", ""):
            _settings["barcode_length"] = 5
            if str(_settings.get("barcode_start", "")).strip() in ("100001", "100001.0", ""):
                _settings["barcode_start"] = 10001
        _settings["barcode_five_digit_v695"] = True
        try:
            save_settings()
        except Exception:
            pass
    _theme = _resolve_theme()
    return _settings


def save_settings(settings: dict = None):
    global _settings
    if settings:
        _settings.update(settings)
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    data = dict(_settings)
    try:                           # v5.27: keys never written in plain text
        from config import secret_box as _sb
        for _k in SECRET_KEYS:
            if data.get(_k):
                data[_k] = _sb.protect(str(data[_k]))
    except Exception:
        pass
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# v7.0: the company's country behaviour (tax rate, currency symbol,
# round-off, financial year …) is laid OVER the PC's settings while that
# company is open. It is never written to this PC's settings file, so the
# next company opened on the PC starts from the PC's own values.
_company = {}


def set_company(key: str, value):
    _company[key] = value


def clear_company():
    _company.clear()


def company_values() -> dict:
    return dict(_company)


def get(key: str, default=None):
    if key in _company:
        return _company[key]
    return _settings.get(key, default)


def set(key: str, value):
    global _theme
    _company.pop(key, None)
    _settings[key] = value
    if key in ("theme", "theme_custom_color"):      # a new theme applies right away
        _theme = _resolve_theme()


def theme() -> dict:
    return _theme


def color(key: str) -> str:
    return _theme.get(key, "#000000")


def flag(key: str, default: bool = False) -> bool:
    """Robust boolean read — checkbox settings arrive as True/1/'1'/'true'."""
    v = _company[key] if key in _company else _settings.get(key, default)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


_ROUND_STEPS = {"Nearest 0.05": 0.05, "Nearest 0.10": 0.10,
                "Nearest 1.00": 1.00}


def round_off(amount):
    """Settings ▸ Tax: automatic invoice-total round-off.

    Returns (rounded_total, adjustment). The single source of truth used
    by the invoice window, POS and any future document — so a 142.37
    total rounds identically everywhere (Nearest 0.05 -> 142.35, -0.02).
    Disabled or method 'None' -> (amount, 0.0)."""
    try:
        amount = float(amount)
        if not flag("round_off_enabled"):
            return amount, 0.0
        step = _ROUND_STEPS.get(str(get("round_off_method", "None")))
        if not step:
            return amount, 0.0
        import math
        # retail half-up (142.50 -> 143.00), not Python's banker's rounding;
        # +1e-9 defeats IEEE float midpoints (142.35/0.10 = 1423.4999...)
        rounded = round(math.floor(amount / step + 0.5 + 1e-9) * step, 2)
        return rounded, round(rounded - amount, 2)
    except Exception:
        return amount, 0.0


# Initialize
load_settings()


# ── Settings ▸ Payment: which payment methods are offered ──────────
_PAY_FLAGS = {
    "cash": ("pay_method_cash",),
    "card": ("pay_method_credit_card", "pay_method_debit_card"),
    "bank_transfer": ("pay_method_bank",),
    "bank": ("pay_method_bank",),
    "cheque": ("pay_method_cheque",),
}


def payment_enabled(method: str) -> bool:
    """True if a payment method is switched on (credit/mixed always are)."""
    keys = _PAY_FLAGS.get(str(method or "").lower())
    if not keys:
        return True
    return any(flag(k, DEFAULT_SETTINGS.get(k, True)) for k in keys)


def payment_methods(choices):
    """Filter a list of method codes down to the enabled ones
    (never returns an empty list)."""
    out = [m for m in choices if payment_enabled(m)]
    return out or list(choices)[:1]


# ── Settings ▸ Tax ▸ Sales Price Mode, for DISPLAY of prices ───────
def sales_price_includes_vat() -> bool:
    return str(get("sales_price_tax_mode", "inclusive") or "").lower() == "inclusive"


def price_with_vat(price, vat_rate) -> float:
    """Customer price incl. VAT for a stored selling price: the price
    itself when prices are VAT-inclusive, else price + VAT."""
    try:
        p, r = float(price or 0), float(vat_rate or 0)
    except (TypeError, ValueError):
        return 0.0
    return p if sales_price_includes_vat() else p * (1 + r / 100.0)


# ── Settings ▸ Company ▸ Date / Time Format, for PRINTED documents ──
_DATE_FMT = {"dd/MM/yyyy": "%d/%m/%Y", "yyyy-MM-dd": "%Y-%m-%d",
             "MM/dd/yyyy": "%m/%d/%Y", "dd-MM-yyyy": "%d-%m-%Y"}


def _as_datetime(value):
    from datetime import datetime as _dt, date as _d
    if value is None or value == "":
        return None
    if isinstance(value, _dt):
        return value
    if isinstance(value, _d):
        return _dt(value.year, value.month, value.day)
    s = str(value).strip().replace("T", " ")
    for f in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
              "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return _dt.strptime(s[:26], f)
        except ValueError:
            continue
    return None


def fmt_date(value):
    """A date as the owner wants it printed (Settings ▸ Date Format).
    Unknown input comes back unchanged."""
    d = _as_datetime(value)
    if d is None:
        return "" if value is None else str(value)
    return d.strftime(_DATE_FMT.get(str(get("date_format", "dd/MM/yyyy")), "%d/%m/%Y"))


def fmt_time(value):
    """HH:MM (24-hour) or hh:MM AM/PM (Settings ▸ Time Format)."""
    from datetime import datetime as _dt, time as _t
    if value is None or value == "":
        return ""
    if isinstance(value, _t):
        t = value
    else:
        d = _as_datetime(value)
        if d is None:
            s = str(value).strip()
            for f in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
                try:
                    t = _dt.strptime(s[:15], f).time()
                    break
                except ValueError:
                    continue
            else:
                return s
        else:
            t = d.time()
    if "12" in str(get("time_format", "24-hour")):
        return t.strftime("%I:%M %p").lstrip("0")
    return t.strftime("%H:%M")


def fmt_datetime(value):
    d = _as_datetime(value)
    if d is None:
        return "" if value is None else str(value)
    return f"{fmt_date(d)} {fmt_time(d)}"


def fiscal_year_bounds(today=None, offset=0):
    """(start, end) dates of the financial year containing `today`
    (Settings ▸ Company ▸ Financial Year Start, MM-DD). offset=-1 gives
    the previous year."""
    from datetime import date as _d, timedelta as _td
    today = today or _d.today()
    raw = str(get("fiscal_year_start", "01-01") or "01-01").strip()
    try:
        mm, dd = [int(x) for x in raw.replace("/", "-").split("-")[:2]]
        _d(2001, mm, dd)
    except Exception:
        mm, dd = 1, 1
    y = today.year if (today.month, today.day) >= (mm, dd) else today.year - 1
    y += offset

    def _mk(year):
        try:
            return _d(year, mm, dd)
        except ValueError:                      # 29 Feb in a normal year
            return _d(year, mm, 28)
    start = _mk(y)
    end = _mk(y + 1) - _td(days=1)
    return start, end


# ── Settings ▸ Tax ▸ Default VAT Rate, for NEW products ─────────────
TAX_PROFILES = {"Saudi Arabia VAT 15%": 15, "UAE VAT 5%": 5, "Bahrain VAT 10%": 10,
                "Qatar VAT": 0, "Oman VAT 5%": 5, "Custom": None}


def default_vat_index(rates):
    """Index in `rates` (list of numbers) of the default VAT rate for a
    new product; 0 when nothing matches."""
    try:
        want = float(get("tax_sales_rate", 15) or 0)
    except (TypeError, ValueError):
        return 0
    for i, r in enumerate(rates):
        try:
            if abs(float(r) - want) < 0.001:
                return i
        except (TypeError, ValueError):
            continue
    return 0
