# ============================================================
# DayBill ERP - Offer poster PDF (v7.2)
# ------------------------------------------------------------
# A ready-to-print offer poster made right here — no design work and
# no internet: shop name, big headline (English + Arabic), product
# cards with the old price crossed out and the new price in a badge,
# the offer dates and a footer. A4 / A5 portrait, A4 landscape or a
# square social post. Used by the PDT "Offer Poster" module and the
# Offers screen (🖨 Poster PDF).
#
#   render(path, data)  data = {headline, headline_ar, sub, when,
#                               shop, shop_ar, footer, size, theme,
#                               items: [{name, name_ar, old, new, badge}]}
# ============================================================

import os

SIZES = {                       # key: (label, width mm, height mm)
    "a4": ("A4 portrait", 210, 297),
    "a5": ("A5 portrait", 148, 210),
    "a4l": ("A4 landscape (window banner)", 297, 210),
    "square": ("Square social post", 200, 200),
}
THEMES = {                      # key: (label, background, band, accent, badge, text)
    "sale": ("Bright sale (red / yellow)", "#FFF8E1", "#D32F2F", "#FFC107", "#D32F2F", "#1F2937"),
    "fresh": ("Fresh & green", "#F1F8E9", "#2E7D32", "#AED581", "#2E7D32", "#1B3A1F"),
    "premium": ("Premium dark / gold", "#111827", "#1F2937", "#D4AF37", "#B8860B", "#F9FAFB"),
    "clean": ("Minimal clean (blue)", "#FFFFFF", "#1D4ED8", "#DBEAFE", "#1D4ED8", "#111827"),
    "festive": ("Ramadan / Eid (purple / gold)", "#F5F3FF", "#5B21B6", "#FBBF24", "#7C3AED", "#2E1065"),
}


def _fonts():
    """(regular, bold) — an Arabic-capable font when the PC has one."""
    try:
        from modules import pdf_invoice as P
        P._register_fonts()
        return P._AR_FONT, P._AR_FONT_BOLD
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _ar(text):
    try:
        from modules import pdf_invoice as P
        return P._shape_arabic(text) if P._has_arabic(text) else str(text or "")
    except Exception:
        return str(text or "")


def _money(v):
    try:
        from modules import country as K
        return K.money(v)
    except Exception:
        try:
            return "{:,.2f}".format(float(v))
        except (TypeError, ValueError):
            return ""


def _cur():
    try:
        from modules import country as K
        return K.symbol()
    except Exception:
        return "SAR"


def _fit(c, text, font, size, max_w, min_size=7):
    """Largest font size (≤ size) that fits max_w."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    s = size
    while s > min_size and stringWidth(text, font, s) > max_w:
        s -= 0.5
    return s


def _trim(text, font, size, max_w):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    t = str(text or "")
    if stringWidth(t, font, size) <= max_w:
        return t
    while t and stringWidth(t + "…", font, size) > max_w:
        t = t[:-1]
    return t + "…"


def render(path, data):
    """Draw the poster to path (PDF). Returns path."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white

    size = data.get("size") if data.get("size") in SIZES else "a4"
    theme = data.get("theme") if data.get("theme") in THEMES else "sale"
    _l, W, H = SIZES[size]
    W, H = W * mm, H * mm
    _t, bg, band, accent, badge, ink = THEMES[theme]
    BG, BAND, ACC, BADGE, INK = (HexColor(x) for x in (bg, band, accent, badge, ink))
    REG, BOLD = _fonts()
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    c = canvas.Canvas(path, pagesize=(W, H))
    c.setTitle(str(data.get("headline") or "Offer"))
    m = 10 * mm
    c.setFillColor(BG); c.rect(0, 0, W, H, stroke=0, fill=1)

    # ── top band: shop name ──
    band_h = H * 0.085
    c.setFillColor(BAND); c.rect(0, H - band_h, W, band_h, stroke=0, fill=1)
    shop = str(data.get("shop") or "").strip()
    shop_ar = str(data.get("shop_ar") or "").strip()
    c.setFillColor(white)
    if shop:
        s = _fit(c, shop, BOLD, band_h * 0.42, W * (0.55 if shop_ar else 0.9))
        c.setFont(BOLD, s)
        c.drawString(m, H - band_h / 2 - s * 0.35, shop) if shop_ar else \
            c.drawCentredString(W / 2, H - band_h / 2 - s * 0.35, shop)
    if shop_ar:
        t = _ar(shop_ar)
        s = _fit(c, t, BOLD, band_h * 0.42, W * (0.4 if shop else 0.9))
        c.setFont(BOLD, s)
        c.drawRightString(W - m, H - band_h / 2 - s * 0.35, t) if shop else \
            c.drawCentredString(W / 2, H - band_h / 2 - s * 0.35, t)

    # ── headline ──
    y = H - band_h - 6 * mm
    head = str(data.get("headline") or "SPECIAL OFFER").upper()
    hs = _fit(c, head, BOLD, H * 0.075, W - 2 * m)
    c.setFillColor(BADGE); c.setFont(BOLD, hs)
    y -= hs
    c.drawCentredString(W / 2, y, head)
    if data.get("headline_ar"):
        t = _ar(data["headline_ar"])
        s = _fit(c, t, BOLD, hs * 0.75, W - 2 * m)
        c.setFont(BOLD, s); y -= s * 1.25
        c.drawCentredString(W / 2, y, t)
    if data.get("sub"):
        s = _fit(c, str(data["sub"]), REG, hs * 0.35, W - 2 * m)
        c.setFillColor(INK); c.setFont(REG, s); y -= s * 1.6
        c.drawCentredString(W / 2, y, str(data["sub"]))
    if data.get("when"):
        s = _fit(c, str(data["when"]), BOLD, hs * 0.32, W - 2 * m)
        txt_w = c.stringWidth(str(data["when"]), BOLD, s) + 8 * mm
        y -= s * 2.2
        c.setFillColor(ACC); c.roundRect(W / 2 - txt_w / 2, y - s * 0.45, txt_w, s * 1.6, s * 0.5,
                                         stroke=0, fill=1)
        c.setFillColor(INK if theme != "premium" else HexColor("#111827")); c.setFont(BOLD, s)
        c.drawCentredString(W / 2, y, str(data["when"]))
    top = y - 7 * mm

    # ── product cards grid ──
    foot_h = H * 0.07
    items = list(data.get("items") or [])[:12]
    bottom = foot_h + 4 * mm
    if items:
        n = len(items)
        cols = 1 if n == 1 else 2 if n <= 4 else 3
        if size == "a4l":
            cols = min(n, 4) if n > 2 else n
        rows = (n + cols - 1) // cols
        gap = 4 * mm
        cw = (W - 2 * m - gap * (cols - 1)) / cols
        ch = min((top - bottom - gap * (rows - 1)) / rows, cw * 1.05)
        card_bg = HexColor("#FFFFFF") if theme != "premium" else HexColor("#1F2937")
        name_ink = INK if theme != "premium" else HexColor("#F9FAFB")
        cur = _cur()
        for i, it in enumerate(items):
            r, k = divmod(i, cols)
            x0 = m + k * (cw + gap)
            y0 = top - (r + 1) * ch - r * gap
            c.setFillColor(card_bg); c.setStrokeColor(ACC); c.setLineWidth(1.2)
            c.roundRect(x0, y0, cw, ch, 3 * mm, stroke=1, fill=1)
            pad = 3 * mm
            ns = min(ch * 0.11, cw * 0.09, 20)
            ty = y0 + ch - pad - ns
            if it.get("badge"):                   # the badge sits top-right: the name goes under it
                ty -= min(ch * 0.075, 12) * 1.9
            c.setFillColor(name_ink); c.setFont(BOLD, ns)
            c.drawCentredString(x0 + cw / 2, ty, _trim(it.get("name") or "", BOLD, ns, cw - 2 * pad))
            if it.get("name_ar"):
                t = _ar(it["name_ar"])
                c.setFont(BOLD, ns * 0.9); ty -= ns * 1.25
                c.drawCentredString(x0 + cw / 2, ty, _trim(t, BOLD, ns * 0.9, cw - 2 * pad))
            new, old = it.get("new"), it.get("old")
            price = new if new not in (None, "") else old
            # price badge
            bh = ch * 0.34
            by = y0 + pad + (ch * 0.12 if old not in (None, "") and new not in (None, "") else 0)
            c.setFillColor(BADGE); c.roundRect(x0 + pad, by, cw - 2 * pad, bh, 2.5 * mm, stroke=0, fill=1)
            if price not in (None, ""):
                ptxt = _money(price)
                ps = _fit(c, ptxt, BOLD, bh * 0.62, (cw - 2 * pad) * 0.72)
                c.setFillColor(white); c.setFont(BOLD, ps)
                c.drawCentredString(x0 + cw / 2 - ps * 0.6, by + bh / 2 - ps * 0.33, ptxt)
                c.setFont(BOLD, ps * 0.38)
                c.drawString(x0 + cw / 2 + c.stringWidth(ptxt, BOLD, ps) / 2 - ps * 0.5,
                             by + bh / 2 - ps * 0.33, cur)
            if old not in (None, "") and new not in (None, "") and float(new) < float(old):
                otxt = "%s %s" % (_money(old), cur)
                os_ = min(ch * 0.07, 13)
                c.setFillColor(HexColor("#6B7280")); c.setFont(REG, os_)
                ox = x0 + cw / 2; oy = y0 + pad + os_ * 0.2
                c.drawCentredString(ox, oy, otxt)
                ow = c.stringWidth(otxt, REG, os_)
                c.setStrokeColor(HexColor("#DC2626")); c.setLineWidth(1.4)
                c.line(ox - ow / 2 - 1, oy + os_ * 0.35, ox + ow / 2 + 1, oy + os_ * 0.35)
            if it.get("badge"):
                bt = str(it["badge"])[:18]
                bs = min(ch * 0.075, 12)
                bw = c.stringWidth(bt, BOLD, bs) + 4 * mm
                c.setFillColor(ACC); c.roundRect(x0 + cw - bw - 1.5 * mm, y0 + ch - bs * 2.6, bw, bs * 1.8,
                                                bs * 0.6, stroke=0, fill=1)
                c.setFillColor(HexColor("#111827")); c.setFont(BOLD, bs)
                c.drawCentredString(x0 + cw - bw / 2 - 1.5 * mm, y0 + ch - bs * 2.6 + bs * 0.5, bt)

    # ── footer ──
    c.setFillColor(BAND); c.rect(0, 0, W, foot_h, stroke=0, fill=1)
    foot = str(data.get("footer") or "").strip()
    if foot:
        s = _fit(c, foot, REG, foot_h * 0.32, W - 2 * m)
        c.setFillColor(white); c.setFont(REG, s)
        c.drawCentredString(W / 2, foot_h / 2 - s * 0.35, foot)
    c.showPage(); c.save()
    return path


# ── poster data from an offer (Offers screen) ────────────────
def data_from_offer(offer, items, size="a4", theme="sale", company=None):
    """offer + items (offers.load_all format) → render() data."""
    from modules import offer_poster as OP
    company = company or {}
    h_en, h_ar = OP.headline(offer)
    span, extra = OP.when_lines(offer)
    rows = OP.product_prices(offer, items)
    return {"headline": h_en, "headline_ar": h_ar,
            "sub": str(offer.get("offer_name") or "") if str(offer.get("offer_name") or "").upper()
            != h_en.upper() else "",
            "when": span + ((" · " + extra) if extra else ""),
            "shop": company.get("company_name_en") or "", "shop_ar": company.get("company_name_ar") or "",
            "footer": footer(company), "size": size, "theme": theme,
            "items": [{"name": n, "name_ar": a, "old": old, "new": new,
                       "badge": b if offer.get("offer_type") in ("buy_get", "percent", "amount") else ""}
                      for n, a, old, new, b in rows]}


def footer(company):
    bits = [str(company.get(k) or "").strip() for k in ("address_en", "city_en")]
    bits = [b for b in bits if b]
    if company.get("phone"):
        bits.append("Tel " + str(company["phone"]).strip())
    try:
        from modules import country as K
        tax = K.tax_name()
    except Exception:
        tax = "VAT"
    bits.append("Prices include %s · While stocks last" % tax)
    return " · ".join(bits)
