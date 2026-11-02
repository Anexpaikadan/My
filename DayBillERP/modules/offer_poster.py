# ============================================================
# DayBill ERP - Offer poster prompt
# ------------------------------------------------------------
# Builds a ready-to-paste prompt for ChatGPT / Gemini (image
# generation) from one offer: shop name, headline, products with
# old / new price, dates, Arabic + English text, poster size and
# style. The shop copies it, pastes it in ChatGPT or Gemini and
# gets the poster — no design work.
# ============================================================

from datetime import datetime

from modules import offers as O

SIZES = {
    "A4 print poster (portrait)": "A4 portrait poster for printing (2480 × 3508 px, 300 dpi)",
    "Instagram / Facebook post": "square-ish social media post, 1080 × 1350 px (4:5 portrait)",
    "WhatsApp / Instagram status": "full-screen phone story, 1080 × 1920 px (9:16)",
    "Shop window banner (landscape)": "wide landscape banner, 3508 × 2480 px (A4 landscape, 300 dpi)",
    "Shelf tag (small)": "small shelf price tag, A6 landscape (1748 × 1240 px)",
}
LANGS = ("English + Arabic", "English only", "Arabic only")
STYLES = {
    "Bright supermarket sale": "bright supermarket sale style: red, yellow and white, bold starburst "
                               "price badges, energetic and eye-catching",
    "Fresh & green": "fresh, natural style: green and white, light background, clean and healthy feel",
    "Premium / dark": "premium style: dark navy or black background with gold accents, elegant",
    "Minimal clean": "minimal clean style: lots of white space, one accent colour, modern flat design",
    "Ramadan / Eid festive": "festive Ramadan / Eid style: crescent moon, lanterns, deep purple and "
                             "gold, warm and celebratory",
    "National Day (green)": "Saudi National Day style: green and white, celebratory, modern",
}


def _money(v):
    try:
        return "%.2f" % float(v)
    except (TypeError, ValueError):
        return "0.00"


def _date_txt(dt):
    return dt.strftime("%d %b %Y").lstrip("0") if dt else ""


def product_prices(offer, items):
    """[(name_en, name_ar, old_price, new_price or None, badge)] for the poster."""
    out = []
    t = offer.get("offer_type")
    v = O._f(offer.get("offer_value"))
    for it in items:
        old = O._f(it.get("normal_price") if it.get("normal_price") is not None
                   else it.get("base_price"))
        new = None
        if t == "percent":
            new = old * (1 - v / 100.0) if old else None
        elif t == "price":
            new = O._f(it.get("offer_price")) or None
        elif t == "amount":
            new = max(0.0, old - v) if old else None
        badge = O.label(offer, it)
        out.append((it.get("product_name_en") or "", it.get("product_name_ar") or "",
                    old, new, badge))
    return out


def when_lines(offer):
    """('3 Oct 2026 – 10 Oct 2026', 'Fri & Sat, 4:00 PM – 8:00 PM')"""
    st, en = O.to_dt(offer.get("start_at")), O.to_dt(offer.get("end_at"))
    if st and en:
        span = "%s – %s" % (_date_txt(st), _date_txt(en)) if st.date() != en.date() \
            else _date_txt(st)
    elif en:
        span = "until %s" % _date_txt(en)
    elif st:
        span = "from %s" % _date_txt(st)
    else:
        span = "limited time"
    extra = []
    mask = str(offer.get("days_mask") or "1111111").ljust(7, "1")
    if mask != "1111111":
        names = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        extra.append(" & ".join(n for n, m in zip(names, mask) if m == "1"))
    tf, tt = offer.get("time_from"), offer.get("time_to")
    if tf and tt and tf != tt:
        def h(x):
            try:
                return datetime.strptime(x, "%H:%M").strftime("%I:%M %p").lstrip("0")
            except ValueError:
                return x
        extra.append("%s – %s" % (h(tf), h(tt)))
    return span, ", ".join(extra)


def headline(offer):
    t = offer.get("offer_type")
    if t == "percent":
        v = O._f(offer.get("offer_value"))
        if abs(v - 50) < 1e-9:
            return "HALF PRICE!", "نصف السعر!"
        return "%s%% OFF" % O._num(v), "خصم %s٪" % O._num(v)
    if t == "price":
        return "SPECIAL OFFER PRICES", "أسعار العرض الخاص"
    if t == "amount":
        try:
            from modules import country as _K
            loc = _K.localize
        except Exception:
            loc = str
        return loc("SAVE %s SAR" % _money(offer.get("offer_value"))), \
            loc("وفّر %s ريال" % _money(offer.get("offer_value")))
    if t == "buy_get":
        return O.label(offer), O.label_ar(offer)
    return "SPECIAL OFFER", "عرض خاص"


def build_prompt(offer, items, company=None, size="A4 print poster (portrait)",
                 lang="English + Arabic", style="Bright supermarket sale",
                 show_prices=True, notes=""):
    company = company or {}
    shop_en = (company.get("company_name_en") or "").strip()
    shop_ar = (company.get("company_name_ar") or "").strip()
    if shop_en.lower() in ("your company name", "company name", "my company"):
        shop_en = ""
    en = lang != "Arabic only"
    ar = lang != "English only"
    h_en, h_ar = headline(offer)
    span, extra = when_lines(offer)
    L = []
    L.append("Create a professional promotional offer poster for a supermarket / retail "
             "shop in Saudi Arabia.")
    L.append("")
    L.append("FORMAT: " + SIZES.get(size, size) + ".")
    L.append("STYLE: " + STYLES.get(style, style) + ".")
    L.append("")
    if shop_en or shop_ar:
        shop = shop_en if shop_en else shop_ar
        if shop_en and shop_ar and ar:
            shop = "%s  (Arabic: %s)" % (shop_en, shop_ar)
        L.append("SHOP NAME (top of the poster, clear and readable): " + shop)
    L.append("MAIN HEADLINE (the biggest text on the poster):")
    if en:
        L.append('  English: "%s"' % h_en)
    if ar:
        L.append('  Arabic: "%s"' % h_ar)
    name = (offer.get("offer_name") or "").strip()
    if name and name.upper() != h_en.upper():
        L.append('OFFER NAME (smaller, under the headline): "%s"' % name
                 + (' / Arabic: "%s"' % offer.get("offer_name_ar") if ar and offer.get("offer_name_ar") else ""))
    L.append("OFFER VALID: " + span + ((" — " + extra) if extra else ""))
    L.append("")
    rows = product_prices(offer, items)
    if rows:
        L.append("PRODUCTS ON OFFER (show each one with a realistic product photo, its name "
                 "and a big price badge):")
        for i, (n_en, n_ar, old, new, badge) in enumerate(rows[:12], 1):
            nm = []
            if en and n_en:
                nm.append(n_en)
            if ar and n_ar:
                nm.append(n_ar)
            line = "  %d. %s" % (i, " — ".join(nm) or n_en or n_ar)
            if show_prices and old:
                if new is not None and new < old:
                    line += " — was %s SAR (crossed out), NOW %s SAR" % (_money(old), _money(new))
                else:
                    line += " — %s SAR" % _money(old)
            if offer.get("offer_type") in ("buy_get", "percent", "amount"):
                line += "  [badge: %s]" % badge
            L.append(line)
        if len(rows) > 12:
            L.append("  … and more products in store.")
        L.append("")
    foot = []
    if company.get("address_en"):
        foot.append(str(company["address_en"]).strip())
    if company.get("city_en"):
        foot.append(str(company["city_en"]).strip())
    if company.get("phone"):
        foot.append("Tel " + str(company["phone"]).strip())
    L.append("FOOTER (small text at the bottom): "
             + (" · ".join(foot) + " · " if foot else "")
             + ("Prices include VAT · While stocks last" if en else "")
             + (" · الأسعار شاملة الضريبة · حتى نفاد الكمية" if ar else ""))
    L.append("")
    L.append("TEXT RULES:")
    L.append("- Use exactly the text, product names and prices written above. Do not invent "
             "other products, prices, dates or words.")
    if ar:
        L.append("- Arabic text must be correct Arabic script, written right-to-left with "
                 "properly joined letters (not reversed, not broken).")
    try:
        from modules import country as _K
        _cur = _K.currency_code()
    except Exception:
        _cur = "SAR"
    L.append("- Prices in " + _cur + " with 2 decimals; make prices and the headline very large and "
             "easy to read from far away.")
    L.append("- Leave clean space around the edges for printing; no watermark, no fake logos.")
    if notes.strip():
        L.append("")
        L.append("EXTRA WISHES: " + notes.strip())
    try:                          # v7.0: the company's country money
        from modules import country as _K
        return _K.localize("\n".join(L))
    except Exception:
        return "\n".join(L)


def chatgpt_url(prompt):
    import urllib.parse
    return "https://chatgpt.com/?q=" + urllib.parse.quote(prompt)


GEMINI_URL = "https://gemini.google.com/app"
