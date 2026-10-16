# ============================================================
# DayBill ERP - Print preferences resolver
# ------------------------------------------------------------
# Reads the Print & Invoice settings (paper, toggles, footer) and
# the active A4 template (built-in or custom). Shared by
# pdf_invoice.py (and usable by thermal_receipt.py).
# ============================================================

import sys, os, json, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg

_BUILTIN = {
    "classic": {"accent": "#360DD9", "font": "sans",  "header": "split",   "table": "bordered"},
    "modern":  {"accent": "#360DD9", "font": "sans",  "header": "band",    "table": "striped"},
    "minimal": {"accent": "#1B1B2E", "font": "serif", "header": "minimal", "table": "clean"},
    "green":   {"accent": "#2E9E4F", "font": "sans",  "header": "band",    "table": "bordered"},
}

_FONTS = {
    "sans":  ("Helvetica", "Helvetica-Bold"),
    "serif": ("Times-Roman", "Times-Bold"),
    "mono":  ("Courier", "Courier-Bold"),
}


def active_template():
    tid = str(cfg.get("invoice_template_a4", "modern") or "modern")
    t = dict(_BUILTIN.get(tid, {}))
    if not t:
        try:
            for ct in json.loads(cfg.get("invoice_templates_custom", "[]") or "[]"):
                if ct.get("id") == tid:
                    t = dict(ct)
                    break
        except Exception:
            pass
    if not t:
        t = dict(_BUILTIN["modern"])
    # sanitize (mirrors the PHP active_template())
    if not re.match(r"^#[0-9A-Fa-f]{6}$", str(t.get("accent", ""))):
        t["accent"] = "#3A1FD6"
    if t.get("font") not in _FONTS:
        t["font"] = "sans"
    if t.get("header") not in ("split", "band", "minimal"):
        t["header"] = "band"
    if t.get("table") not in ("bordered", "striped", "clean"):
        t["table"] = "bordered"
    return t


def get_prefs():
    t = active_template()
    f, fb = _FONTS[t["font"]]
    return {
        "accent":      t["accent"],
        "header":      t["header"],
        "table":       t["table"],
        "font":        f,
        "font_bold":   fb,
        "footer":      str(cfg.get("invoice_footer", "") or "").strip(),
        "show_qr":     bool(cfg.get("print_zatca_qr", True)),
        "show_arabic": bool(cfg.get("print_arabic", True)),
        "paper_width": str(cfg.get("paper_width", "80")),
        "auto_print":  bool(cfg.get("print_auto", False)),
        # ── entry sections (Print & Invoice ▸ Invoice sections) ──
        "show_words":     bool(cfg.get("print_amount_words", True)),
        "show_payinfo":   bool(cfg.get("print_payment_info", True)),
        "show_signature": bool(cfg.get("print_signature", False)),
        "show_terms":     bool(cfg.get("print_terms", False)),
        "terms_text":     str(cfg.get("invoice_terms", "") or "").strip(),
        "show_bank":      bool(cfg.get("print_bank", False)),
        "bank_text":      str(cfg.get("invoice_bank", "") or "").strip(),
    }


# ── Amount in words (English, SAR) ────────────────────────────
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
         "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
         "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
         "Eighty", "Ninety"]


def _words_below_1000(n):
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        w = _TENS[n // 10]
        if n % 10:
            w += "-" + _ONES[n % 10]
        out.append(w)
    elif n > 0:
        out.append(_ONES[n])
    return " ".join(out)


def amount_in_words(value, currency="Saudi Riyals", cents="Halalas"):
    """1234.50 -> 'One Thousand Two Hundred Thirty-Four Saudi Riyals and
    Fifty Halalas Only' (English; ZATCA invoices keep figures for Arabic)."""
    try:
        value = round(float(value), 2)
    except Exception:
        return ""
    whole = int(value)
    frac = int(round((value - whole) * 100))
    if whole == 0 and frac == 0:
        return "Zero %s Only" % currency
    parts, scales = [], [(10 ** 9, "Billion"), (10 ** 6, "Million"),
                         (10 ** 3, "Thousand"), (1, "")]
    n = whole
    for div, name in scales:
        if n >= div:
            seg = _words_below_1000(n // div)
            parts.append((seg + " " + name).strip())
            n %= div
    words = " ".join(parts) if parts else "Zero"
    out = "%s %s" % (words, currency)
    if frac:
        out += " and %s %s" % (_words_below_1000(frac), cents)
    return out + " Only"
