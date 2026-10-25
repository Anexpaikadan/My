# ============================================================
# DayBill ERP - 🩺 ZATCA Phase 2 readiness  (v6.5)
# ------------------------------------------------------------
#   wave_check()   do I have to connect, and by when?  (25th wave:
#                  taxable sales > 187,500 SAR in any of 2022–2025 →
#                  Phase 2 from 1 February 2027)
#   data_check()   what would make ZATCA reject bills: shop details, B2B
#                  customers without a full national address, wrong VAT
#                  numbers, products without a VAT category, certificate,
#                  documents waiting / rejected
#   fix_hint(msg)  ZATCA's error message → what to do, in simple words
# Read-only.
# ============================================================

import os
import re
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ZATCA Governor decision (Official Gazette, July 2026) — the 25th wave
WAVE = {"wave": 25, "threshold": 187500.0, "years": (2022, 2023, 2024, 2025),
        "deadline": date(2027, 2, 1)}


def _db():
    from config.database import db
    return db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _one(sql, params=()):
    try:
        r = _db().fetchone(sql, params)
        return dict(r) if r else {}
    except Exception:
        return {}


def _all(sql, params=()):
    try:
        return [dict(r) for r in (_db().fetchall(sql, params) or [])]
    except Exception:
        return []


def taxable_sales(year):
    """Taxable sales (before VAT) of one calendar year, credit notes taken off."""
    a, b = "%d-01-01" % year, "%d-12-31" % year
    inv = _one("SELECT ISNULL(SUM(CASE WHEN ISNULL(invoice_type_code,'388')='381' THEN -1 ELSE 1 END "
               "* ISNULL(taxable_amount,0)),0) AS t FROM sales_invoices WHERE invoice_status='confirmed' "
               "AND invoice_date BETWEEN ? AND ?", (a, b))
    ret = _one("SELECT ISNULL(SUM(ISNULL(taxable_amount,0)),0) AS t FROM sales_returns "
               "WHERE ISNULL(return_status,'confirmed')='confirmed' AND return_date BETWEEN ? AND ?", (a, b))
    return round(_f(inv.get("t")) - _f(ret.get("t")), 2)


def _connected():
    try:
        from modules.zatca import egs as E
        return bool(E.any_connected())
    except Exception:
        return False


def wave_check(today=None):
    today = today or date.today()
    years = {y: taxable_sales(y) for y in WAVE["years"]}
    over = [y for y, v in years.items() if v > WAVE["threshold"]]
    days_left = (WAVE["deadline"] - today).days
    connected = _connected()
    top = max(years.values()) if years else 0.0
    dl = WAVE["deadline"].strftime("%d %B %Y").lstrip("0")
    if connected:
        level, text = "ok", "✔ Connected to ZATCA (Phase 2) — nothing more to do for the %dth wave." % WAVE["wave"]
    elif over:
        y = max(over, key=lambda k: years[k])
        level = "fail" if days_left <= 60 else "warn"
        text = ("⚠ Your taxable sales were more than %s SAR in %s (%s SAR). ZATCA's %dth wave: connect "
                "DayBill to ZATCA (Phase 2) by %s — %s."
                % ("{:,.0f}".format(WAVE["threshold"]), y, "{:,.0f}".format(years[y]), WAVE["wave"], dl,
                   ("%d days left" % days_left) if days_left > 0 else "the date has PASSED, connect now"))
    else:
        level = "info"
        text = ("Your sales in DayBill were not more than %s SAR in any year 2022–2025, so the %dth wave "
                "(%s) does not include you. ZATCA tells each shop when its turn comes."
                % ("{:,.0f}".format(WAVE["threshold"]), WAVE["wave"], dl))
    note = ("Only sales saved in DayBill are counted — if you used another program before, check those "
            "years too. Shops above higher limits were due in earlier waves.")
    return {"years": years, "over": over, "max": top, "threshold": WAVE["threshold"],
            "deadline": WAVE["deadline"].isoformat(), "days_left": days_left, "connected": connected,
            "in_scope": bool(over), "level": level, "text": text, "note": note}


def startup_text(today=None):
    """One line for the start-up message ('' when nothing to say)."""
    w = wave_check(today)
    if w["connected"] or not w["in_scope"]:
        return ""
    if w["days_left"] > 0:
        return "🔐 ZATCA Phase 2: connect DayBill by %s (%d days left) — open ZATCA" % (
            WAVE["deadline"].strftime("%d %b %Y").lstrip("0"), w["days_left"])
    return "🔐 ZATCA Phase 2: the date (1 Feb 2027) has passed — connect DayBill now (open ZATCA)"


# ── data that ZATCA would reject ───────────────────────────────
def _check(key, title, level, count=0, detail="", fix=""):
    return {"key": key, "title": title, "level": level, "count": count, "detail": detail, "fix": fix}


def data_check():
    from modules.zatca import egs as E
    from modules.zatca.qr_generator import valid_vat_number, clean_vat_number
    out = []
    probs = E.detail_problems()
    out.append(_check("shop", "Shop details (VAT number, CR, national address)", "fail" if probs else "ok",
                      len(probs), "  ·  ".join("%s — %s" % (l, p) for _k, l, p in probs),
                      "ZATCA ▸ step 1, or Settings ▸ Company" if probs else ""))
    custs = _all("SELECT customer_code, customer_name_en, customer_name_ar, vat_registration_no, building_number, "
                 "street_name_en, street_name_ar, district_en, district_ar, city_en, city_ar, postal_code, "
                 "address_en FROM customers WHERE ISNULL(is_active,1)=1 AND ISNULL(vat_registration_no,'')<>''")
    no_addr, bad_vat = [], []
    for c in custs:
        vat = clean_vat_number(c.get("vat_registration_no"))
        name = c.get("customer_name_en") or c.get("customer_name_ar") or c.get("customer_code") or "?"
        if not valid_vat_number(vat):
            bad_vat.append(name)
            continue
        b, _b2b = E._buyer(c)
        if E.buyer_problems(b):
            no_addr.append(name)
    out.append(_check("b2b_address", "B2B customers (with a VAT number) need the full national address",
                      "fail" if no_addr else "ok", len(no_addr),
                      ("Their tax invoices will be REJECTED: " + ", ".join(no_addr[:6])
                       + (" …" if len(no_addr) > 6 else "")) if no_addr else "",
                      "Customers ▸ edit ▸ building no. (4 digits), street, district, city, postal code (5 digits)"
                      if no_addr else ""))
    out.append(_check("b2b_vat", "Customer VAT numbers look right (15 digits, 3…3)", "warn" if bad_vat else "ok",
                      len(bad_vat), ("Their bills go as simple B2C invoices: " + ", ".join(bad_vat[:6])
                                     + (" …" if len(bad_vat) > 6 else "")) if bad_vat else "",
                      "Customers ▸ edit ▸ VAT number (or clear it)" if bad_vat else ""))
    nv = _all("SELECT product_code, product_name_en FROM products WHERE ISNULL(is_active,1)=1 "
              "AND vat_category_id IS NULL")
    out.append(_check("product_vat", "Every product has a VAT category", "warn" if nv else "ok", len(nv),
                      ", ".join(str(p.get("product_code") or p.get("product_name_en")) for p in nv[:8])
                      + (" …" if len(nv) > 8 else ""),
                      "Products ▸ edit ▸ VAT (or Inventory ▸ AI data check)" if nv else ""))
    if E.any_connected():
        e = E.active() or {}
        exp = e.get("cert_expires")
        try:
            from modules.offers import to_dt
            exp_d = to_dt(exp)
        except Exception:
            exp_d = None
        if exp_d:
            left = (exp_d - datetime.now()).days
            out.append(_check("cert", "ZATCA certificate valid until %s" % exp_d.strftime("%d/%m/%Y"),
                              "fail" if left < 0 else ("warn" if left < 30 else "ok"), max(left, 0),
                              "%d day(s) left" % left if left >= 0 else "ENDED",
                              "ZATCA ▸ 🔄 Reconnect / renew (new OTP)" if left < 30 else ""))
        st = E.stats()
        od = E.overdue_text()
        out.append(_check("waiting", "Bills sent to ZATCA in time (24 hours)", "fail" if od else
                          ("warn" if st.get("waiting") else "ok"), st.get("waiting", 0),
                          od or ("%d waiting to send" % st["waiting"] if st.get("waiting") else ""),
                          "ZATCA ▸ 📤 Send now (check the internet)" if (od or st.get("waiting")) else ""))
        bad = st.get("rejected", 0) + st.get("fix", 0)
        out.append(_check("rejected", "No rejected bills", "fail" if bad else "ok", bad,
                          "%d rejected / need a fix" % bad if bad else "",
                          "ZATCA ▸ click the bill: 'How to fix' shows what to do" if bad else ""))
    else:
        out.append(_check("connect", "Connected to ZATCA", "warn", 0, "Not connected yet",
                          "ZATCA ▸ 3 steps ▸ 🔐 Connect (Sandbox first to try)"))
    return out


def summary(checks):
    n = {k: sum(1 for c in checks if c["level"] == k) for k in ("ok", "warn", "fail")}
    n["ready"] = not n["fail"]
    return n


# ── ZATCA's message → what to do ───────────────────────────────
_HINTS = [
    (r"previous invoice hash|\bpih\b|invoice counter|\bicv\b",
     "The chain of bills is out of order (two PCs with one ZATCA unit, or a bill sent twice). Press 📤 Send "
     "now so the waiting bills go in order; if it stays, give every till its own unit (Connect this till)."),
    (r"certificate|csid|unauthori[sz]ed|\b401\b|\b403\b",
     "ZATCA did not accept DayBill's certificate (ended or revoked). ZATCA ▸ 🔄 Reconnect / renew with a "
     "new OTP from the Fatoora portal."),
    (r"building\s*number",
     "The building number must be 4 digits (national address). Shop: ZATCA step 1 / Settings ▸ Company. "
     "Customer: Customers ▸ edit. Then 🔁 Send again."),
    (r"postal|zip\s*code",
     "The postal code must be 5 digits (national address) — fix the shop or the customer, then 🔁 Send again."),
    (r"vat\s*(registration)?\s*(number|no)|tax\s*registration|\bbr-ksa-(39|40|44)\b",
     "The VAT number must be 15 digits, starting and ending with 3 — fix the shop or the customer, then 🔁 "
     "Send again."),
    (r"exemption|vatex|zero[- ]rated|tax\s*category",
     "A zero-rated / exempt item needs a reason: ZATCA ▸ Zero-rated reason, and check the product's VAT "
     "category. Then 🔁 Send again."),
    (r"issue\s*date|issue\s*time|future|time\s*zone",
     "The bill's date or time is wrong — check the PC date, time and time zone (Riyadh, UTC+3), then 🔁 "
     "Send again."),
    (r"signature|signed\s*properties|digest|hash",
     "The signature does not match — the bill was changed after it was signed, or the key is wrong. Do not "
     "edit signed bills; make a credit note. 🔁 Send again; if it stays, 🔄 Reconnect."),
    (r"street|district|city|address|buyer|customer",
     "The customer's details are not complete for a B2B tax invoice — Customers ▸ edit ▸ name, VAT number "
     "and the full national address (building 4 digits, street, district, city, postal code 5 digits)."),
    (r"seller|supplier",
     "The shop's details are not complete — ZATCA step 1 / Settings ▸ Company (VAT, CR, national address)."),
    (r"internet|connection|timed?\s*out|name resolution|waiting:",
     "No answer from ZATCA yet (internet). DayBill sends it again by itself — or press 📤 Send now."),
    (r"\b409\b|conflict|already",
     "ZATCA says this bill was already sent (duplicate). Nothing to fix if it shows as reported / cleared."),
]


def fix_hint(msg):
    """ZATCA's (English) message → (code, what to do)."""
    m = str(msg or "")
    code = ""
    hit = re.search(r"\b(BR-KSA-[A-Z0-9-]+|BR-[A-Z]{0,3}-?\d+|KSA-\d+)\b", m, re.I)
    if hit:
        code = hit.group(1).upper()
    low = m.lower()
    if not low.strip():
        return code, ""
    for pat, hint in _HINTS:
        if re.search(pat, low):
            return code, hint
    return code, ("Read ZATCA's message, fix the bill or the data, then 🔁 Send again. If it keeps "
                  "failing, send the message to your DayBill dealer.")
