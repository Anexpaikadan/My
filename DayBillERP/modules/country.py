# ============================================================
# DayBill ERP - country profiles (v7.0)
# ------------------------------------------------------------
# A company works the way its COUNTRY works. The country is picked when
# the company is made (New Company wizard) and is kept in the company's
# own database (company.country_code), so every PC that opens that
# database behaves the same.
#
#   SA  Saudi Arabia   VAT 15 %   SAR   VAT No. (15 digits, 3…3)   ZATCA
#   AE  UAE            VAT 5 %    AED   TRN (15 digits, 100…)      VAT 201 return
#   IN  India          GST        INR ₹ GSTIN (15 characters)      GSTR-1 / GSTR-3B
#                      CGST + SGST inside the state, IGST between states
#
#   code()              the company's country ('SA' when not set)
#   profile(c=None)     everything about a country (dict)
#   tax_name()          'VAT' | 'GST'
#   tax_no_label()      'VAT No.' | 'TRN' | 'GSTIN'
#   valid_tax_no(no)    (ok, message)
#   symbol() / cur()    the currency symbol the company prints
#   money(x, sym=False) 1,234.50 · India 1,23,456.50 (lakh grouping)
#   words(x)            amount in words in the country's money
#   states()            regions / emirates / GST states: [(code, name)]
#   place_of_supply()   India: the state a sale or purchase belongs to
#   gst_split(tax, pos) {"cgst", "sgst", "igst"} for India, else {}
#   apply()             put the company's country settings into cfg
#                       (called after every database connect)
#   options() / set_option(k, v)   settings kept IN the company database
# ============================================================

import re

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

DEFAULT = "SA"

SA_REGIONS = [
    ("01", "Riyadh"), ("02", "Makkah"), ("03", "Madinah"), ("04", "Eastern Province"),
    ("05", "Qassim"), ("06", "Ha'il"), ("07", "Tabuk"), ("08", "Northern Borders"),
    ("09", "Jazan"), ("10", "Najran"), ("11", "Al Bahah"), ("12", "Al Jawf"), ("14", "Asir"),
]

# UAE VAT 201 box 1a … 1g order
AE_EMIRATES = [
    ("AZ", "Abu Dhabi"), ("DU", "Dubai"), ("SH", "Sharjah"), ("AJ", "Ajman"),
    ("UQ", "Umm Al Quwain"), ("RK", "Ras Al Khaimah"), ("FU", "Fujairah"),
]

# GST state codes (the first 2 digits of a GSTIN)
IN_STATES = [
    ("01", "Jammu and Kashmir"), ("02", "Himachal Pradesh"), ("03", "Punjab"),
    ("04", "Chandigarh"), ("05", "Uttarakhand"), ("06", "Haryana"), ("07", "Delhi"),
    ("08", "Rajasthan"), ("09", "Uttar Pradesh"), ("10", "Bihar"), ("11", "Sikkim"),
    ("12", "Arunachal Pradesh"), ("13", "Nagaland"), ("14", "Manipur"), ("15", "Mizoram"),
    ("16", "Tripura"), ("17", "Meghalaya"), ("18", "Assam"), ("19", "West Bengal"),
    ("20", "Jharkhand"), ("21", "Odisha"), ("22", "Chhattisgarh"), ("23", "Madhya Pradesh"),
    ("24", "Gujarat"), ("26", "Dadra and Nagar Haveli and Daman and Diu"),
    ("27", "Maharashtra"), ("29", "Karnataka"), ("30", "Goa"), ("31", "Lakshadweep"),
    ("32", "Kerala"), ("33", "Tamil Nadu"), ("34", "Puducherry"),
    ("35", "Andaman and Nicobar Islands"), ("36", "Telangana"), ("37", "Andhra Pradesh"),
    ("38", "Ladakh"), ("97", "Other Territory"), ("96", "Other Country (export)"),
]
# Union Territories without a legislature charge UTGST in place of SGST
IN_UTGST = {"04", "26", "31", "35", "38"}
EXPORT_STATE = "96"

# tax categories a NEW company gets: code, name, Arabic name, rate, kind, active
#   kind: std (taxed) | zero | exempt | nil | oos (out of scope / non-GST)
TAX_CATEGORIES = {
    "SA": [
        ("S", "Standard Rate", "المعدل القياسي", 15.0, "std", 1),
        ("Z", "Zero Rate", "معدل صفري", 0.0, "zero", 1),
        ("E", "Exempt", "معفى", 0.0, "exempt", 1),
        ("O", "Out of Scope", "خارج النطاق", 0.0, "oos", 1),
    ],
    "AE": [
        ("S", "Standard Rate 5%", "المعدل الأساسي 5%", 5.0, "std", 1),
        ("Z", "Zero Rated", "خاضع لنسبة الصفر", 0.0, "zero", 1),
        ("E", "Exempt", "معفى", 0.0, "exempt", 1),
        ("O", "Out of Scope", "خارج النطاق", 0.0, "oos", 1),
    ],
    # GST rates after the September 2025 change: 5 % and 18 % (+ 40 %);
    # 12 % and 28 % are kept switched off for old bills and returns
    "IN": [
        ("S", "GST 18%", "GST 18%", 18.0, "std", 1),
        ("G5", "GST 5%", "GST 5%", 5.0, "std", 1),
        ("G40", "GST 40%", "GST 40%", 40.0, "std", 1),
        ("G3", "GST 3% (gold, silver)", "GST 3%", 3.0, "std", 1),
        ("G12", "GST 12% (old rate)", "GST 12%", 12.0, "std", 0),
        ("G28", "GST 28% (old rate)", "GST 28%", 28.0, "std", 0),
        ("G0", "Nil rated 0%", "Nil rated", 0.0, "nil", 1),
        ("Z", "Zero rated (export / SEZ)", "Zero rated", 0.0, "zero", 1),
        ("E", "Exempt", "Exempt", 0.0, "exempt", 1),
        ("O", "Non-GST supply", "Non-GST", 0.0, "oos", 1),
    ],
}

COUNTRIES = {
    "SA": {
        "code": "SA", "name": "Saudi Arabia", "name_ar": "المملكة العربية السعودية", "flag": "🇸🇦",
        "currency": "SAR", "currency_name": "Saudi Riyal",
        "symbols": ["SAR", "ر.س", "﷼", "⃁"], "symbol": "SAR", "symbol_after": True,
        "words": ("Saudi Riyals", "Halalas"), "grouping": "intl",
        "tax": "VAT", "tax_ar": "ضريبة القيمة المضافة", "std_rate": 15.0,
        "tax_no_label": "VAT No.", "tax_no_label_ar": "الرقم الضريبي",
        "tax_no_hint": "15 digits, starts and ends with 3",
        "states_label": "Region", "states": SA_REGIONS,
        "phone": "966", "fiscal_start": "01-01", "language": "ar", "round": "None",
        "e_invoice": "ZATCA", "return": "VAT Return (ZATCA)",
        "invoice_title": "Tax Invoice", "simplified_title": "Simplified Tax Invoice",
        "invoice_title_ar": "فاتورة ضريبية", "simplified_title_ar": "فاتورة ضريبية مبسطة",
        "qr": True, "payroll": "GOSI",
    },
    "AE": {
        "code": "AE", "name": "United Arab Emirates", "name_ar": "الإمارات العربية المتحدة",
        "flag": "🇦🇪",
        "currency": "AED", "currency_name": "UAE Dirham",
        "symbols": ["AED", "د.إ", "Dhs"], "symbol": "AED", "symbol_after": False,
        "words": ("UAE Dirhams", "Fils"), "grouping": "intl",
        "tax": "VAT", "tax_ar": "ضريبة القيمة المضافة", "std_rate": 5.0,
        "tax_no_label": "TRN", "tax_no_label_ar": "رقم التسجيل الضريبي",
        "tax_no_hint": "15 digits, starts with 100",
        "states_label": "Emirate", "states": AE_EMIRATES,
        "phone": "971", "fiscal_start": "01-01", "language": "en", "round": "None",
        "e_invoice": "", "return": "VAT 201 Return (FTA)",
        "invoice_title": "Tax Invoice", "simplified_title": "Simplified Tax Invoice",
        "invoice_title_ar": "فاتورة ضريبية", "simplified_title_ar": "فاتورة ضريبية مبسطة",
        "qr": False, "payroll": "WPS",
    },
    "IN": {
        "code": "IN", "name": "India", "name_ar": "الهند", "flag": "🇮🇳",
        "currency": "INR", "currency_name": "Indian Rupee",
        "symbols": ["₹", "Rs.", "INR"], "symbol": "₹", "symbol_after": False,
        "words": ("Rupees", "Paise"), "grouping": "indian",
        "tax": "GST", "tax_ar": "GST", "std_rate": 18.0,
        "tax_no_label": "GSTIN", "tax_no_label_ar": "GSTIN",
        "tax_no_hint": "15 characters, e.g. 27AAPFU0939F1ZV",
        "states_label": "State", "states": IN_STATES,
        "phone": "91", "fiscal_start": "04-01", "language": "en", "round": "Nearest 1.00",
        "e_invoice": "", "return": "GSTR-1 / GSTR-3B",
        "invoice_title": "Tax Invoice", "simplified_title": "Tax Invoice",
        "invoice_title_ar": "Tax Invoice", "simplified_title_ar": "Tax Invoice",
        "qr": False, "payroll": "PF/ESI",
    },
}

# settings that belong to the COMPANY (kept in its database), not to the PC
COMPANY_KEYS = ("currency_symbol", "currency_symbol_after", "tax_sales_rate",
                "round_off_enabled", "round_off_method", "fiscal_year_start",
                "wa_country_code", "sales_price_tax_mode", "country_tax_profile",
                "gst_hsn_digits", "gst_b2cl_limit")

_STATE = {"loaded": False, "row": {}, "opts": {}}


# ── reading the company ───────────────────────────────────────
def _row():
    if _STATE["loaded"]:
        return _STATE["row"]
    row = {}
    try:
        r = db.fetchone("SELECT TOP 1 * FROM company ORDER BY company_id") if db else None
        row = dict(r or {})
    except Exception:
        row = {}
    _STATE.update(loaded=True, row=row)
    try:
        _STATE["opts"] = {str(r["opt_key"]): r["opt_value"] for r in
                          (db.fetchall("SELECT opt_key, opt_value FROM company_options") or [])}
    except Exception:
        _STATE["opts"] = {}
    return row


def invalidate():
    """Call after the company row or the database changes."""
    _STATE.update(loaded=False, row={}, opts={})


def code():
    c = str(_row().get("country_code") or "").strip().upper()
    return c if c in COUNTRIES else DEFAULT


def profile(c=None):
    return COUNTRIES.get(str(c or code()).upper(), COUNTRIES[DEFAULT])


def is_sa():
    return code() == "SA"


def is_ae():
    return code() == "AE"


def is_in():
    return code() == "IN"


def name(c=None):
    return profile(c)["name"]


def tax_name(c=None):
    return profile(c)["tax"]


def tax_no_label(c=None, ar=False):
    p = profile(c)
    return p["tax_no_label_ar"] if ar else p["tax_no_label"]


def std_rate(c=None):
    return float(profile(c)["std_rate"])


def rate_or_std(v):
    """A tax rate read from a product / line: 0 stays 0 (nil, zero rated,
    exempt); only a missing rate becomes the country's standard rate."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return std_rate()
    try:
        return float(v)
    except (TypeError, ValueError):
        return std_rate()


def has_zatca():
    return is_sa()


def company_state():
    s = str(_row().get("state_code") or "").strip()
    if not s and is_in():                     # from the company's own GSTIN
        g = str(_row().get("vat_registration_no") or "").strip()
        if len(g) >= 2 and g[:2].isdigit():
            s = g[:2]
    return s


def business_modules_text():
    return str(_row().get("business_modules") or "")


# ── company options (settings kept in the company database) ───
def options():
    _row()
    return dict(_STATE["opts"])


def option(key, default=None):
    _row()
    v = _STATE["opts"].get(key)
    return default if v in (None, "") else v


def set_option(key, value):
    """Keep a company setting in the company database."""
    try:
        v = "" if value is None else str(value)
        db.execute("IF EXISTS (SELECT 1 FROM company_options WHERE opt_key=?) "
                   "UPDATE company_options SET opt_value=? WHERE opt_key=? "
                   "ELSE INSERT INTO company_options (opt_key, opt_value) VALUES (?,?)",
                   (key, v, key, key, v))
        _row()
        _STATE["opts"][key] = v
        return True
    except Exception:
        return False


def _cast(key, v):
    """A company option (kept as text) back to its type."""
    hint = None
    try:
        from modules import business as _biz
        for d in _biz.DEFAULTS.values():
            if key in d:
                hint = d[key]
    except Exception:
        pass
    if key in ("round_off_enabled", "currency_symbol_after") or isinstance(hint, bool):
        return str(v).strip().lower() in ("1", "true", "yes", "on")
    if key in ("tax_sales_rate", "gst_b2cl_limit") or isinstance(hint, float):
        try:
            return float(v)
        except (TypeError, ValueError):
            return v
    if key == "gst_hsn_digits" or isinstance(hint, int):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return hint if hint is not None else 4
    return v


def apply():
    """Lay the company's country behaviour over the PC's settings (in
    memory only — see cfg.set_company): tax rate for new products, the
    WhatsApp country code, financial year start, round-off, currency …
    Company options saved in Settings win over the country defaults.
    A Saudi company keeps the PC's own values (as before v7.0)."""
    invalidate()
    try:
        from config import settings as cfg
    except Exception:
        return
    try:
        from modules import account_defaults as _ad
        _ad.invalidate()
    except Exception:
        pass
    cfg.clear_company()
    p = profile()
    row = _row()
    defaults = {
        "currency_symbol": str(row.get("currency_symbol") or "").strip() or p["symbol"],
        "currency_symbol_after": p["symbol_after"],
    }
    if p["code"] != "SA":
        defaults.update(tax_sales_rate=p["std_rate"], wa_country_code=p["phone"], currency=p["currency"],
                        country_tax_profile={"AE": "UAE VAT 5%"}.get(p["code"], "Custom"),
                        fiscal_year_start=p["fiscal_start"])
    fy = str(row.get("fiscal_year_start") or "").strip()
    if p["code"] != "SA" and re.match(r"^\d{2}-\d{2}$", fy):
        defaults["fiscal_year_start"] = fy
    if p["code"] == "IN":
        defaults.update(round_off_enabled=True, round_off_method=p["round"],
                        gst_hsn_digits=4, gst_b2cl_limit=100000.0)
    elif p["code"] == "AE":
        defaults.update(round_off_enabled=False)
    for k, v in defaults.items():
        cfg.set_company(k, v)
    for k, v in options().items():
        if not str(k).startswith("_"):
            cfg.set_company(k, _cast(k, v))
    cfg.set_company("company_country", p["code"])


def save_settings(values):
    """Settings ▸ Save: company settings go into the company database and
    stay laid over the PC's settings; returns the keys it took."""
    took = []
    try:
        from config import settings as cfg
    except Exception:
        return took
    keys = set(COMPANY_KEYS)
    try:
        from modules import business as _biz
        for d in _biz.DEFAULTS.values():
            keys |= set(d)
    except Exception:
        pass
    for k, v in (values or {}).items():
        if k in keys:
            if set_option(k, v):
                cfg.set_company(k, _cast(k, v))
                took.append(k)
    return took


# ── tax numbers ───────────────────────────────────────────────
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_char(first14):
    """The 15th character of a GSTIN (mod-36 check)."""
    total = 0
    for i, ch in enumerate(first14.upper()):
        v = _B36.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return _B36[(36 - total % 36) % 36]


def valid_tax_no(no, c=None):
    """(ok, message) — empty is fine (a person / walk-in customer)."""
    s = re.sub(r"\s+", "", str(no or "")).upper()
    if not s:
        return True, ""
    c = str(c or code()).upper()
    if c == "SA":
        if len(s) == 15 and s.isdigit() and s[0] == "3" and s[-1] == "3":
            return True, ""
        return False, "A Saudi VAT number is 15 digits and starts and ends with 3."
    if c == "AE":
        if len(s) == 15 and s.isdigit() and s.startswith("100"):
            return True, ""
        return False, "A UAE TRN is 15 digits and starts with 100."
    if c == "IN":
        if not _GSTIN_RE.match(s):
            return False, "A GSTIN is 15 characters: state code, PAN, entity no., Z, check letter."
        if s[:2] not in {k for k, _n in IN_STATES}:
            return False, "The first 2 digits of the GSTIN (%s) are not a GST state code." % s[:2]
        if gstin_check_char(s[:14]) != s[14]:
            return False, "The last character of the GSTIN does not match (typing mistake?)."
        return True, ""
    return True, ""


def state_from_tax_no(no):
    """India: the state of a GSTIN (its first 2 digits)."""
    s = str(no or "").strip()
    return s[:2] if is_in() and len(s) >= 2 and s[:2].isdigit() else ""


# ── states / emirates ─────────────────────────────────────────
def states(c=None):
    return list(profile(c)["states"])


def state_name(state, c=None):
    s = str(state or "").strip()
    for k, n in profile(c)["states"]:
        if k == s:
            return n
    return s


def state_label(state, c=None):
    """'27 - Maharashtra' (as the screens show it)."""
    s = str(state or "").strip()
    return ("%s - %s" % (s, state_name(s, c))) if s else ""


def state_code_of(label):
    """'27 - Maharashtra' / 'Maharashtra' / '27' → '27'."""
    t = str(label or "").strip()
    if not t:
        return ""
    if " - " in t:
        return t.split(" - ", 1)[0].strip()
    for k, n in states():
        if t.lower() in (k.lower(), n.lower()):
            return k
    return t[:10]


# ── currency ──────────────────────────────────────────────────
def symbol():
    try:
        from config import settings as cfg
        s = cfg.get("currency_symbol")
        if s:
            return str(s)
    except Exception:
        pass
    return str(_row().get("currency_symbol") or "").strip() or profile()["symbol"]


cur = symbol


def currency_code():
    return profile()["currency"]


def symbol_after():
    try:
        from config import settings as cfg
        v = cfg.get("currency_symbol_after")
        if v is not None:
            return bool(v)
    except Exception:
        pass
    return bool(profile()["symbol_after"])


def _indian_group(int_str):
    s = int_str
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def num(x, dec=2, c=None):
    """A number grouped the country's way: 1,234,567.50 · India 12,34,567.50"""
    try:
        v = float(x or 0)
    except (TypeError, ValueError):
        return str(x or "")
    if profile(c)["grouping"] != "indian":
        return format(v, ",.%df" % dec)
    neg = v < 0
    s = format(abs(v), ".%df" % dec)
    whole, _, frac = s.partition(".")
    out = _indian_group(whole) + (("." + frac) if frac else "")
    return ("-" if neg else "") + out


def money(x, sym=False, dec=2, c=None):
    """1,234.50 — with sym=True: 'SAR 1,234.50' style per the country
    (₹1,23,450.00 · AED 1,234.50 · 1,234.50 SAR)."""
    n = num(x, dec, c)
    if not sym:
        return n
    s = symbol() if c is None else profile(c)["symbol"]
    after = symbol_after() if c is None else profile(c)["symbol_after"]
    if after:
        return "%s %s" % (n, s)
    return ("%s%s" % (s, n)) if s == "₹" else ("%s %s" % (s, n))


# ── amount in words ───────────────────────────────────────────
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n):
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")


def _three(n):
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n:
        out.append(_two(n))
    return " ".join(out)


def _words_int(n, indian=False):
    if n == 0:
        return "Zero"
    scales = ([(10 ** 7, "Crore"), (10 ** 5, "Lakh"), (10 ** 3, "Thousand"), (1, "")] if indian
              else [(10 ** 9, "Billion"), (10 ** 6, "Million"), (10 ** 3, "Thousand"), (1, "")])
    parts = []
    for div, nm in scales:
        if n >= div:
            q = n // div
            seg = _words_int(q, indian) if (indian and div == 10 ** 7 and q >= 100) else _three(q)
            parts.append((seg + " " + nm).strip())
            n %= div
    return " ".join(parts)


def words(value, c=None):
    """1234.50 → 'One Thousand Two Hundred Thirty-Four Saudi Riyals and
    Fifty Halalas Only' · India: 'Rupees One Lakh … and Fifty Paise Only'."""
    try:
        value = round(abs(float(value)), 2)
    except (TypeError, ValueError):
        return ""
    p = profile(c)
    big, small = p["words"]
    whole = int(value)
    frac = int(round((value - whole) * 100))
    indian = p["grouping"] == "indian"
    w = _words_int(whole, indian)
    if indian:
        out = "%s %s" % (big, w)
    else:
        out = "%s %s" % (w, big)
    if frac:
        out += " and %s %s" % (_two(frac), small)
    return out + " Only"


# ── India GST: place of supply and CGST / SGST / IGST ─────────
def is_interstate(pos, home=None):
    """True when the place of supply is another state (or abroad)."""
    home = str(home or company_state() or "").strip()
    pos = str(pos or "").strip()
    if not pos or not home:
        return False
    return pos != home


def place_of_supply(kind, header):
    """India: the state a document belongs to.
    sales / sales return → the bill's place of supply, else the customer's
    state, else (customer abroad) 96, else the company's own state.
    purchase / purchase return → the supplier's state the same way."""
    h = header or {}
    pos = str(h.get("place_of_supply") or "").strip()
    if pos:
        return pos
    party = "supplier" if kind in ("purchase", "purchase_return") else "customer"
    pid = h.get(party + "_id")
    if pid and db is not None:
        try:
            r = db.fetchone("SELECT state_code, country_code, vat_registration_no FROM %ss "
                            "WHERE %s_id=?" % (party, party), (pid,)) or {}
            st = str(r.get("state_code") or "").strip()
            if st:
                return st
            ctry = str(r.get("country_code") or "").strip().upper()
            if ctry and ctry not in ("IN", "IND"):
                return EXPORT_STATE
            st = state_from_tax_no(r.get("vat_registration_no"))
            if st:
                return st
        except Exception:
            pass
    return company_state()


def tax_head_label(head, pos=None):
    """'SGST' or 'UTGST' (Union Territories without a legislature)."""
    if head == "sgst" and str(pos or company_state()) in IN_UTGST:
        return "UTGST"
    return head.upper()


def gst_split(tax, pos=None, home=None):
    """India: {"cgst", "sgst", "igst"} of a tax amount; other countries {}."""
    if not is_in():
        return {}
    tax = round(float(tax or 0), 2)
    if is_interstate(pos, home):
        return {"cgst": 0.0, "sgst": 0.0, "igst": tax}
    c = round(tax / 2.0, 2)
    return {"cgst": c, "sgst": round(tax - c, 2), "igst": 0.0}


def split_lines(lines, pos=None, home=None, rate="vat_rate", vat="vat_amount"):
    """India: tax per rate for a bill's lines — for the tax table on the
    print: [{"rate", "taxable", "cgst", "sgst", "igst", "tax"}]."""
    by = {}
    for ln in lines or []:
        r = float(ln.get(rate) or 0)
        d = by.setdefault(r, {"rate": r, "taxable": 0.0, "tax": 0.0})
        d["taxable"] += float(ln.get("line_amount") or 0)
        d["tax"] += float(ln.get(vat) or 0)
    out = []
    for r in sorted(by):
        d = by[r]
        d["taxable"], d["tax"] = round(d["taxable"], 2), round(d["tax"], 2)
        d.update(gst_split(d["tax"], pos, home) or {"cgst": 0.0, "sgst": 0.0, "igst": 0.0})
        out.append(d)
    return out


# ── tax categories ────────────────────────────────────────────
def categories(c=None):
    return list(TAX_CATEGORIES.get(str(c or code()).upper(), TAX_CATEGORIES["SA"]))


def category_kind(cat_code, rate=None, c=None):
    """std | zero | exempt | nil | oos for a tax category code."""
    cc = str(cat_code or "").strip().upper()
    for k, _n, _a, _r, kind, _on in categories(c):
        if k == cc:
            return kind
    first = cc[:1]
    if first == "Z":
        return "zero"
    if first == "E":
        return "exempt"
    if first == "O":
        return "oos"
    try:
        return "std" if float(rate or 0) > 0 else "nil"
    except (TypeError, ValueError):
        return "std"


def invoice_title(simplified=False, ar=False):
    p = profile()
    if ar:
        return p["simplified_title_ar"] if simplified else p["invoice_title_ar"]
    return p["simplified_title"] if simplified else p["invoice_title"]


# ── Saudi words → the company's country (screens, messages, PDFs) ─
_AMT = r"-?\d[\d,]*(?:\.\d+)?"
_TAXNO = re.compile(r"\b((?:Customer |Supplier )?)VAT (?:Registration )?(?:No\b\.?|Number\b|number\b)")
_RULES = {"key": None, "rules": []}


def _rules(c, sym):
    before = sym if sym == "₹" else sym + " "
    money_rx = [
        (re.compile(r"(%s)\s*SAR\b" % _AMT), lambda m: before + m.group(1)),
        (re.compile(r"\bSAR\s*(%s)" % _AMT), lambda m: before + m.group(1)),
        (re.compile(r"\bSAR\b"), lambda m: sym),
    ]
    if c == "AE":
        return money_rx + [
            (re.compile(r"\bSaudi Riyals?\b"), lambda m: "UAE Dirhams"),
            (re.compile(r"\bHalalas?\b"), lambda m: "Fils"),
            (re.compile(r"ريال"), lambda m: "درهم"),
            (_TAXNO, lambda m: m.group(1) + "TRN"),
            (re.compile(r"\bVAT 15\s?%"), lambda m: "VAT 5%"),
            (re.compile(r"\(15\s?%\)"), lambda m: "(5%)"),
            (re.compile(r"\b15\s?% VAT\b"), lambda m: "5% VAT"),
        ]
    if c == "IN":
        return money_rx + [
            (re.compile(r"\bSaudi Riyals?\b"), lambda m: "Rupees"),
            (re.compile(r"\bHalalas?\b"), lambda m: "Paise"),
            (re.compile(r"ريال"), lambda m: "₹"),
            (_TAXNO, lambda m: m.group(1) + "GSTIN"),
            (re.compile(r"\bVAT 15\s?%"), lambda m: "GST"),
            (re.compile(r"\s?\(15\s?%\)"), lambda m: ""),
            (re.compile(r"\b15\s?% VAT\b"), lambda m: "GST"),
            (re.compile(r"\bVAT\b"), lambda m: "GST"),
        ]
    return []


def localize(text):
    """Text written for Saudi Arabia in the company's country words:
    UAE  SAR → AED · VAT No. → TRN · 15% → 5%
    India SAR → ₹ · VAT → GST · VAT No. → GSTIN · Riyals → Rupees
    A Saudi company gets the text back unchanged."""
    if not isinstance(text, str) or not text:
        return text
    c = code()
    if c == "SA":
        return text
    if "SAR" not in text and "VAT" not in text and "Riyal" not in text and "Halala" not in text \
            and "15" not in text and "ريال" not in text:
        return text
    key = (c, symbol())
    if _RULES["key"] != key:
        _RULES.update(key=key, rules=_rules(*key))
    for rx, fn in _RULES["rules"]:
        text = rx.sub(fn, text)
    return text

