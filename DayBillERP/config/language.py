# ============================================================
# Saudi Arabia ERP - Language / Localization Manager
# Supports: English (LTR) | Arabic (RTL)
# ============================================================

import json
import os

# ── Available languages ───────────────────────────────────────
LANGUAGES = {
    "en": {"name": "English",  "flag": "🇬🇧", "rtl": False},
    "ar": {"name": "العربية",  "flag": "🇸🇦", "rtl": True},
}

_current_lang = "en"
_strings: dict = {}

LOCALE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "locales"))


def load_language(lang_code: str = "en"):
    """Load language file into memory."""
    global _current_lang, _strings
    lang_code = lang_code if lang_code in LANGUAGES else "en"
    locale_file = os.path.join(LOCALE_DIR, f"{lang_code}.json")
    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            _strings = json.load(f)
        _current_lang = lang_code
    except FileNotFoundError:
        # Fallback to English
        with open(os.path.join(LOCALE_DIR, "en.json"), "r", encoding="utf-8") as f:
            _strings = json.load(f)
        _current_lang = "en"


def t(key: str, **kwargs) -> str:
    """
    Translate a dot-notation key.
    Example: t("login.sign_in") -> "Sign In" or "تسجيل الدخول"
    """
    keys = key.split(".")
    val = _strings
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, key)
        else:
            return key
    result = val if isinstance(val, str) else key
    # Support simple variable substitution: t("key", name="Ahmed")
    for var, replacement in kwargs.items():
        result = result.replace(f"{{{var}}}", str(replacement))
    return result


def current_lang() -> str:
    """Return current language code."""
    return _current_lang


def is_rtl() -> bool:
    """Return True if current language is RTL (Arabic)."""
    return LANGUAGES.get(_current_lang, {}).get("rtl", False)


def get_font_family() -> str:
    """Return appropriate font family for current language."""
    if _current_lang == "ar":
        return "Arial"   # Arial has good Arabic support; Cairo if installed
    return "Segoe UI"


def toggle_language() -> str:
    """Toggle between Arabic and English. Returns new lang code."""
    new_lang = "ar" if _current_lang == "en" else "en"
    load_language(new_lang)
    return new_lang


# ── Initialize with English ───────────────────────────────────
load_language("en")
