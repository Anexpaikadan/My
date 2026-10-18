# ============================================================
# Saudi Arabia ERP - ZATCA Bilingual PDF Invoice Generator
# ReportLab canvas | Arabic RTL shaping | Embedded QR
# A4 tax invoice layout (English + Arabic side by side)
# ============================================================

import os
import io
from datetime import datetime


def _pd(v):
    """Date as set in Settings ▸ Company ▸ Date Format."""
    try:
        from config import settings as _c
        return _c.fmt_date(v)
    except Exception:
        return "" if v is None else str(v)


def _pdt(v):
    try:
        from config import settings as _c
        return _c.fmt_datetime(v)
    except Exception:
        return "" if v is None else str(v)


def _ptime(v):
    try:
        from config import settings as _c
        return _c.fmt_time(v)
    except Exception:
        return "" if v is None else str(v)

# ── Arabic shaping helpers ────────────────────────────────────
def _shape_arabic(text: str) -> str:
    """
    Reshape + bidi-reorder Arabic text so it renders correctly in PDF.
    Falls back to the raw string if libraries are missing.
    """
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except ImportError:
        return str(text)


def _has_arabic(text: str) -> bool:
    if not text:
        return False
    return any("\u0600" <= ch <= "\u06FF" for ch in str(text))


# ── Font registration ─────────────────────────────────────────
_FONT_REGISTERED = False
_AR_FONT = "Helvetica"      # fallback
_AR_FONT_BOLD = "Helvetica-Bold"


def _register_fonts():
    """
    Register an Arabic-capable TTF font. Tries common system paths.
    Uses Amiri/Cairo/DejaVu if available, else falls back to Helvetica
    (Arabic will not render with Helvetica, so shipping a TTF is advised).
    """
    global _FONT_REGISTERED, _AR_FONT, _AR_FONT_BOLD
    if _FONT_REGISTERED:
        return

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Candidate fonts that include Arabic glyphs (first match wins).
    # assets/fonts/* is checked first so a bundled Amiri/Cairo is preferred,
    # then common Windows Arabic-capable fonts (present on every Saudi PC),
    # then Linux paths for the build/CI environment.
    candidates = [
        ("Amiri",   "../assets/fonts/Amiri-Regular.ttf", "../assets/fonts/Amiri-Bold.ttf"),
        ("Cairo",   "../assets/fonts/Cairo-Regular.ttf", "../assets/fonts/Cairo-Bold.ttf"),
        ("NotoAr",  "../assets/fonts/NotoNaskhArabic-Regular.ttf",
                    "../assets/fonts/NotoNaskhArabic-Bold.ttf"),
        ("Tahoma",  "C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/tahomabd.ttf"),
        ("Arabtype","C:/Windows/Fonts/arabtype.ttf", "C:/Windows/Fonts/arabtype.ttf"),
        ("Arial",   "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("SegoeUI", "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
        ("Amiri",   "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf",
                    "/usr/share/fonts/truetype/amiri/Amiri-Bold.ttf"),
        ("DejaVu",  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]

    # Also check a local 'fonts' dir next to this module
    base = os.path.dirname(__file__)
    for name, reg, bold in candidates:
        reg_path  = reg  if os.path.isabs(reg)  else os.path.join(base, reg)
        bold_path = bold if os.path.isabs(bold) else os.path.join(base, bold)
        try:
            if os.path.exists(reg_path):
                pdfmetrics.registerFont(TTFont(name, reg_path))
                _AR_FONT = name
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(name + "-Bold", bold_path))
                    _AR_FONT_BOLD = name + "-Bold"
                else:
                    _AR_FONT_BOLD = name
                break
        except Exception:
            continue

    _FONT_REGISTERED = True


# ── Main generator ────────────────────────────────────────────
# ── v7.0: country words and tax lines ────────────────────────
def _with_hsn(lines):
    """India: each line's HSN / SAC code (from the product)."""
    try:
        from modules import country as C
        if not C.is_in():
            return lines
        from config.database import db
    except Exception:
        return lines
    out, cache = [], {}
    for ln in lines or []:
        d = dict(ln)
        pid = d.get("product_id")
        if not d.get("hsn_code") and pid:
            if pid not in cache:
                try:
                    cache[pid] = db.execute_scalar("SELECT hsn_code FROM products WHERE product_id=?", (pid,)) or ""
                except Exception:
                    cache[pid] = ""
            d["hsn_code"] = cache[pid]
        out.append(d)
    return out


def _country_ctx(company, invoice, lines):
    """What the bill prints for the company's country."""
    try:
        from modules import country as C
        p = C.profile()
        code = p["code"]
        sym = C.symbol()
        num = C.num
    except Exception:
        C, p, code, sym = None, {}, "SA", "SAR"
        num = lambda v, *a, **k: "{:,.2f}".format(float(v or 0))  # noqa: E731
    k = {"code": code, "symbol": sym, "num": lambda v: num(v),
         "tax": p.get("tax", "VAT"), "tax_no_label": p.get("tax_no_label", "VAT"),
         "reg_label": {"AE": "Trade Licence", "IN": "PAN"}.get(code, "CR"),
         "qr": code == "SA", "pos_text": "", "heads": [], "rate_rows": [],
         "bill_of_supply": False,
         "vat_label": "VAT %g%%" % float(p.get("std_rate", 15)) if code != "IN" else "GST",
         "footer": {"SA": "This is a ZATCA-compliant electronic tax invoice",
                    "AE": "Tax invoice issued by a VAT registered supplier (TRN %s)"
                          % (company.get("vat_registration_no") or "—"),
                    "IN": "This is a computer generated invoice"}.get(code, "")}
    rates = {round(float(l.get("vat_rate") or 0), 2) for l in lines or [] if float(l.get("vat_amount") or 0)}
    if code != "IN" and len(rates) == 1:
        k["vat_label"] = "%s %g%%" % (k["tax"], list(rates)[0])
    elif code != "IN" and len(rates) > 1:
        k["vat_label"] = k["tax"]
    if code == "IN" and C is not None:
        pos = C.place_of_supply("sales", invoice)
        k["pos_text"] = C.state_label(pos)
        sp = C.gst_split(invoice.get("vat_amount", 0), pos)
        if sp.get("igst"):
            k["heads"] = [("IGST", sp["igst"])]
        else:
            k["heads"] = [("CGST", sp.get("cgst", 0)), (C.tax_head_label("sgst", C.company_state()),
                                                        sp.get("sgst", 0))]
        k["rate_rows"] = C.split_lines(lines, pos)
        k["bill_of_supply"] = not any(float(l.get("vat_amount") or 0) for l in lines or [])
    return k


def _gst_table(c, x, y, K, F, FB, DARK, GREY, BORDER, mm):
    """India: GST by rate — taxable, CGST, SGST, IGST. Returns the y below."""
    cols = [("GST %", 16), ("Taxable", 26), ("CGST", 22), ("SGST", 22), ("IGST", 22)]
    c.setFont(FB, 8); c.setFillColor(DARK)
    c.drawString(x, y - 4 * mm, "GST summary")
    yy = y - 9 * mm
    cx = x
    c.setFont(FB, 7)
    for name, w in cols:
        c.drawRightString(cx + w * mm - 1 * mm, yy, name)
        cx += w * mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.3)
    c.line(x, yy - 1.5 * mm, cx, yy - 1.5 * mm)
    c.setFont(F, 7)
    for r in K["rate_rows"][:6]:
        yy -= 4.2 * mm
        vals = ["%g%%" % r["rate"], K["num"](r["taxable"]), K["num"](r["cgst"]),
                K["num"](r["sgst"]), K["num"](r["igst"])]
        cx = x
        for (name, w), v in zip(cols, vals):
            c.drawRightString(cx + w * mm - 1 * mm, yy, v)
            cx += w * mm
    return yy - 2 * mm


def generate_invoice_pdf(invoice: dict, company: dict, lines: list,
                         output_path: str, qr_base64: str = None) -> str:
    """
    Generate a ZATCA-style bilingual tax invoice PDF.

    invoice : sales_invoices row (dict)
    company : company row (dict)
    lines   : list of sales_invoice_lines rows
    output_path : where to write the .pdf
    qr_base64   : ZATCA QR TLV (Phase 1 or 2). If None, uses invoice['qr_code_data'].

    Returns the output_path.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    _register_fonts()

    if qr_base64 is None:
        qr_base64 = invoice.get("qr_code_data") or invoice.get("zatca_qr_phase2")
    lines = _with_hsn(lines)

    W, H = A4
    c = canvas.Canvas(output_path, pagesize=A4)

    # ── Print & Invoice settings (template, toggles, footer) ──
    try:
        from modules.print_prefs import get_prefs
        _prefs = get_prefs()
    except Exception:
        _prefs = {"accent": "#3A1FD6", "header": "band", "table": "bordered",
                  "font": "Helvetica", "font_bold": "Helvetica-Bold",
                  "footer": "", "show_qr": True, "show_arabic": True}
    F, FB = _prefs["font"], _prefs["font_bold"]
    HDR, TBL = _prefs["header"], _prefs["table"]
    SHOW_AR, SHOW_QR = _prefs["show_arabic"], _prefs["show_qr"]

    # v7.0: the company's country decides the words, the tax lines, the
    # QR (Saudi ZATCA only) and Arabic (not on Indian bills)
    K = _country_ctx(company, invoice, lines)
    if not K["qr"]:
        SHOW_QR = False
    if K["code"] == "IN":
        SHOW_AR = False
    money = K["num"]

    GREEN = colors.HexColor(_prefs["accent"])   # template accent
    DARK  = colors.HexColor("#1A1438")
    GREY  = colors.HexColor("#6B7280")
    LIGHT = colors.HexColor("#ECE9FB")   # light indigo tint
    BORDER= colors.HexColor("#D1D5DB")
    LIME  = colors.HexColor("#7ED957")   # brand accent

    margin = 15 * mm
    y = H - margin

    def text_en(x, yy, s, font="Helvetica", size=9, color=DARK):
        c.setFont(font, size)
        c.setFillColor(color)
        c.drawString(x, yy, str(s))

    def text_en_right(x, yy, s, font="Helvetica", size=9, color=DARK):
        c.setFont(font, size)
        c.setFillColor(color)
        c.drawRightString(x, yy, str(s))

    def text_ar_right(x, yy, s, size=9, color=DARK, bold=False):
        """Draw shaped Arabic right-aligned (honours the Arabic toggle)."""
        if not SHOW_AR:
            return
        c.setFont(_AR_FONT_BOLD if bold else _AR_FONT, size)
        c.setFillColor(color)
        c.drawRightString(x, yy, _shape_arabic(s))

    # ── Header (style from template: band / split / minimal) ──
    addr = ", ".join(filter(None, [
        company.get("building_number"), company.get("street_name_en"),
        company.get("district_en"), company.get("city_en"),
        company.get("state_en")]))
    if not addr:
        addr = str(company.get("address_en") or "").replace("\n", ", ")[:110]
    addr_ar = "، ".join(filter(None, [
        company.get("city_ar"), company.get("district_ar"),
        company.get("street_name_ar")]))

    # ── Repeatable page header (company + address) ────────────
    # Wrapped in a function so the SAME shop-name header is drawn again
    # at the top of every page after a page break — not just page 1.
    def draw_page_header():
        if HDR == "band":
            c.setFillColor(GREEN)
            c.rect(0, H - 38 * mm, W, 38 * mm, fill=1, stroke=0)
            c.setFillColor(LIME)
            c.rect(0, H - 39.5 * mm, W, 1.5 * mm, fill=1, stroke=0)
            text_en(margin, H - 16 * mm, company.get("company_name_en", "Company"),
                    FB, 16, colors.white)
            text_en(margin, H - 22 * mm,
                    f"{K['tax_no_label']}: {company.get('vat_registration_no', '')}", F, 9, LIGHT)
            if company.get("cr_number"):
                text_en(margin, H - 27 * mm, f"{K['reg_label']}: {company.get('cr_number')}",
                        F, 9, LIGHT)
            text_en(margin, H - 32 * mm, addr, F, 8, LIGHT)
            text_ar_right(W - margin, H - 16 * mm,
                          company.get("company_name_ar", ""), 15, colors.white,
                          bold=True)
            if addr_ar:
                text_ar_right(W - margin, H - 32 * mm, addr_ar, 8, LIGHT)
            return H - 46 * mm
        elif HDR == "split":
            text_en(margin, H - 18 * mm, company.get("company_name_en", "Company"),
                    FB, 16, GREEN)
            text_en(margin, H - 24 * mm,
                    f"{K['tax_no_label']}: {company.get('vat_registration_no', '')}", F, 9, GREY)
            if company.get("cr_number"):
                text_en(margin, H - 28.5 * mm, f"{K['reg_label']}: {company.get('cr_number')}",
                        F, 9, GREY)
            text_en(margin, H - 33 * mm, addr, F, 8, GREY)
            text_ar_right(W - margin, H - 18 * mm,
                          company.get("company_name_ar", ""), 15, GREEN, bold=True)
            if addr_ar:
                text_ar_right(W - margin, H - 33 * mm, addr_ar, 8, GREY)
            c.setStrokeColor(GREEN); c.setLineWidth(1.2)
            c.line(margin, H - 37 * mm, W - margin, H - 37 * mm)
            return H - 44 * mm
        else:  # minimal
            text_en(margin, H - 16 * mm, company.get("company_name_en", "Company"),
                    FB, 13, DARK)
            text_ar_right(W - margin, H - 16 * mm,
                          company.get("company_name_ar", ""), 12, DARK, bold=True)
            text_en(margin, H - 21.5 * mm,
                    f"{K['tax_no_label']}: {company.get('vat_registration_no', '')}   {addr}",
                    F, 8, GREY)
            c.setStrokeColor(BORDER); c.setLineWidth(0.6)
            c.line(margin, H - 25 * mm, W - margin, H - 25 * mm)
            return H - 32 * mm

    y = draw_page_header()

    # ── Title bar ─────────────────────────────────────────────
    c.setFillColor(LIGHT)
    c.rect(margin, y - 9 * mm, W - 2 * margin, 9 * mm, fill=1, stroke=0)
    type_code = str(invoice.get("invoice_type_code", "388"))
    title_en = {"388": "TAX INVOICE", "381": "CREDIT NOTE",
                "383": "DEBIT NOTE"}.get(type_code, "TAX INVOICE")
    title_ar = {"388": "فاتورة ضريبية", "381": "إشعار دائن",
                "383": "إشعار مدين"}.get(type_code, "فاتورة ضريبية")
    # B2C (buyer without VAT number) = Simplified Tax Invoice
    if type_code == "388" and not str(invoice.get("customer_vat_no") or "").strip() and K["code"] != "IN":
        title_en, title_ar = "SIMPLIFIED TAX INVOICE", "فاتورة ضريبية مبسطة"
    if type_code == "388" and K["code"] == "IN" and K["bill_of_supply"]:
        title_en = "BILL OF SUPPLY"            # India: no GST on any line
    text_en(margin + 4 * mm, y - 6.2 * mm, title_en, "Helvetica-Bold", 12, GREEN)
    text_ar_right(W - margin - 4 * mm, y - 6.2 * mm, title_ar, 12, GREEN, bold=True)
    y -= 14 * mm

    # ── Invoice meta + customer (two columns) ─────────────────
    col_w = (W - 2 * margin) / 2
    box_top = y
    box_h = 34 * mm

    # Left box: invoice details
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.rect(margin, box_top - box_h, col_w - 2 * mm, box_h, fill=0, stroke=1)

    lx = margin + 3 * mm
    ly = box_top - 6 * mm
    text_en(lx, ly, "Invoice Details", "Helvetica-Bold", 9, GREEN)
    c.setFont(_AR_FONT, 8); c.setFillColor(GREEN)
    c.drawRightString(margin + col_w - 4 * mm, ly, _shape_arabic("تفاصيل الفاتورة"))
    ly -= 6 * mm
    meta = [
        ("Invoice No", invoice.get("invoice_number", "")),
        ("Date", _pd(invoice.get("invoice_date", "")) +
         (f"  {_ptime(invoice.get('invoice_time'))}" if invoice.get("invoice_time") else "")),
        ("Due Date", _pd(invoice.get("due_date")) if invoice.get("due_date") else "—"),
        ("Payment", str(invoice.get("payment_method", "") or "—")),
    ]
    for label, val in meta:
        text_en(lx, ly, f"{label}:", "Helvetica", 8, GREY)
        text_en(lx + 28 * mm, ly, val, "Helvetica-Bold", 8, DARK)
        ly -= 5 * mm

    # Right box: customer
    rx0 = margin + col_w + 0 * mm
    c.rect(rx0, box_top - box_h, col_w - 0 * mm, box_h, fill=0, stroke=1)
    rx = rx0 + 3 * mm
    ry = box_top - 6 * mm
    text_en(rx, ry, "Bill To", "Helvetica-Bold", 9, GREEN)
    c.setFont(_AR_FONT, 8); c.setFillColor(GREEN)
    c.drawRightString(rx0 + col_w - 3 * mm, ry, _shape_arabic("فاتورة إلى"))
    ry -= 6 * mm
    text_en(rx, ry, invoice.get("customer_name_en", ""),
            "Helvetica-Bold", 9, DARK)
    if invoice.get("customer_name_ar"):
        text_ar_right(rx0 + col_w - 3 * mm, ry,
                      invoice.get("customer_name_ar", ""), 9, DARK, bold=True)
    ry -= 5 * mm
    if invoice.get("customer_vat_no"):
        text_en(rx, ry, f"{K['tax_no_label']}: {invoice['customer_vat_no']}",
                "Helvetica", 8, GREY); ry -= 5 * mm
    cust_addr = ", ".join(filter(None, [
        invoice.get("customer_city_en"), invoice.get("customer_country_code")]))
    if cust_addr:
        text_en(rx, ry, cust_addr, "Helvetica", 8, GREY); ry -= 5 * mm
    if K["pos_text"]:                     # India: place of supply
        text_en(rx, ry, "Place of supply: " + K["pos_text"], "Helvetica-Bold", 8, DARK)

    y = box_top - box_h - 8 * mm

    # ── Line items table ──────────────────────────────────────
    headers = ["#", "Description", "Qty", "Price", "VAT%", "VAT", "Total"]
    headers_ar = ["", "الوصف", "الكمية", "السعر", "%", "الضريبة", "الإجمالي"]
    col_widths = [8, 70, 16, 24, 14, 24, 24]  # in mm, sums < 180
    if K["code"] == "IN":                 # India: HSN / SAC column, GST
        headers = ["#", "Description", "HSN/SAC", "Qty", "Rate", "GST%", "Taxable", "Total"]
        headers_ar = ["", "", "", "", "", "", "", ""]
        col_widths = [8, 58, 18, 14, 22, 12, 24, 24]
    elif K["tax"] != "VAT":
        headers = [h.replace("VAT", K["tax"]) for h in headers]
    total_w = sum(col_widths)
    scale = (W - 2 * margin) / (total_w * mm)
    col_x = [margin]
    for cw in col_widths:
        col_x.append(col_x[-1] + cw * mm * scale)

    # Header row — as a function so it repeats atop every page
    row_h = 8 * mm
    aligns = ["c", "l", "c", "r", "c", "r", "r"]
    if K["code"] == "IN":
        aligns = ["c", "l", "c", "c", "r", "c", "r", "r"]

    def draw_table_header(yy):
        c.setFillColor(GREEN)
        c.rect(margin, yy - row_h, W - 2 * margin, row_h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        for i, (h, al) in enumerate(zip(headers, aligns)):
            cx = col_x[i]
            cw = col_x[i + 1] - col_x[i]
            c.setFont("Helvetica-Bold", 8)
            if al == "l":
                c.drawString(cx + 2 * mm, yy - 4 * mm, h)
            elif al == "r":
                c.drawRightString(col_x[i + 1] - 2 * mm, yy - 4 * mm, h)
            else:
                c.drawCentredString(cx + cw / 2, yy - 4 * mm, h)
            ar = headers_ar[i]
            if ar:
                c.setFont(_AR_FONT, 7)
                shaped = _shape_arabic(ar)
                if al == "l":
                    c.drawString(cx + 2 * mm, yy - 7 * mm, shaped)
                elif al == "r":
                    c.drawRightString(col_x[i + 1] - 2 * mm, yy - 7 * mm, shaped)
                else:
                    c.drawCentredString(cx + cw / 2, yy - 7 * mm, shaped)
        return yy - row_h

    # small page-footer (shop name + page number) drawn on every page
    _page_state = {"n": 1}

    def draw_page_footer():
        c.setFillColor(GREY)
        c.setFont("Helvetica", 6.5)
        c.drawString(margin, 8 * mm,
                     company.get("company_name_en", "") or "")
        c.drawRightString(W - margin, 8 * mm,
                          "Page %d" % _page_state["n"])

    def page_break(yy):
        draw_page_footer()
        c.showPage()
        _register_fonts()
        _page_state["n"] += 1
        top = draw_page_header()
        return draw_table_header(top)

    # ── Bottom block: totals + QR + words + payment + bank + terms +
    #    signatures. Measured first, then drawn ANCHORED to the page
    #    bottom just above the footer (not floating under the items).
    def _bottom(c, y):
        low = [y]
        # ── Totals box (right) + QR (left) ────────────────────────
        totals_w = 70 * mm
        tx = W - margin - totals_w
        ty = y

        def total_line(label_en, label_ar, val, bold=False, fill=False):
            nonlocal ty
            lh = 7 * mm
            if fill:
                c.setFillColor(GREEN)
                c.rect(tx, ty - lh, totals_w, lh, fill=1, stroke=0)
                txtcol = colors.white
            else:
                txtcol = DARK
            c.setFillColor(txtcol)
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 9 if bold else 8)
            c.drawString(tx + 2 * mm, ty - 5 * mm, label_en)
            c.setFont(_AR_FONT_BOLD if bold else _AR_FONT, 9 if bold else 8)
            c.drawCentredString(tx + totals_w / 2 + 4 * mm, ty - 5 * mm,
                                _shape_arabic(label_ar))
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 9 if bold else 8)
            c.setFillColor(txtcol)
            c.drawRightString(tx + totals_w - 2 * mm, ty - 5 * mm, money(val))
            if not fill:
                c.setStrokeColor(BORDER); c.setLineWidth(0.3)
                c.line(tx, ty - lh, tx + totals_w, ty - lh)
            ty -= lh

        c.setStrokeColor(BORDER); c.setLineWidth(0.5)
        total_line("Subtotal", "المجموع الفرعي", invoice.get("subtotal_amount", 0))
        if float(invoice.get("discount_amount", 0)):
            total_line("Discount", "الخصم", invoice.get("discount_amount", 0))
        if K["code"] == "IN":             # India: taxable value, then each GST head
            total_line("Taxable value", "", invoice.get("taxable_amount") or invoice.get("subtotal_amount", 0))
            for head, amt in K["heads"]:
                total_line(head, "", amt)
        else:
            total_line(K["vat_label"], "ضريبة القيمة المضافة", invoice.get("vat_amount", 0))
        total_line("Total (%s)" % K["symbol"], "الإجمالي", invoice.get("total_amount", 0),
                   bold=True, fill=True)

        # ── Entry sections (Print & Invoice ▸ Invoice sections) ────
        sy = ty - 4 * mm            # continue below the totals box
        left_w = W - 2 * margin - totals_w - 6 * mm

        # amount in words
        if _prefs.get("show_words", True):
            try:
                from modules.print_prefs import amount_in_words
                words = amount_in_words(invoice.get("total_amount", 0))
            except Exception:
                words = ""
            if words:
                c.setFont(FB, 8); c.setFillColor(DARK)
                c.drawString(tx, sy, "Amount in words:")
                c.setFont(F, 8)
                # wrap to the totals-box width
                import textwrap as _tw
                for i, seg in enumerate(_tw.wrap(words, 52)[:3]):
                    c.drawString(tx, sy - (i + 1) * 4 * mm, seg)
                sy -= (min(len(_tw.wrap(words, 52)), 3) + 1) * 4 * mm + 3 * mm

        # payment info
        if _prefs.get("show_payinfo", True):
            pm = str(invoice.get("payment_method", "") or "").title()
            paid = float(invoice.get("paid_amount", 0) or 0)
            bal = float(invoice.get("total_amount", 0) or 0) - paid
            c.setFont(FB, 8); c.setFillColor(DARK)
            c.drawString(tx, sy, "Payment")
            c.setFont(F, 8)
            c.drawString(tx, sy - 4 * mm, "Method: %s" % (pm or "—"))
            c.drawString(tx, sy - 8 * mm,
                         "Paid: %s    Balance: %s" % ("{:,.2f}".format(paid),
                                                      "{:,.2f}".format(bal)))
            sy -= 14 * mm

        # bank details (left column, under the QR)
        by = y - 38 * mm if (qr_base64 and SHOW_QR) else y - 4 * mm
        if K["code"] == "IN" and K["rate_rows"]:     # India: GST by rate
            by = _gst_table(c, margin, y, K, F, FB, DARK, GREY, BORDER, mm) - 4 * mm
        if _prefs.get("show_bank") and _prefs.get("bank_text"):
            c.setFont(FB, 8); c.setFillColor(DARK)
            c.drawString(margin, by, "Bank Details")
            c.setFont(F, 7.5)
            for i, ln_txt in enumerate(_prefs["bank_text"].splitlines()[:4]):
                c.drawString(margin, by - (i + 1) * 3.8 * mm, ln_txt[:70])
            by -= (min(len(_prefs["bank_text"].splitlines()), 4) + 1) * 3.8 * mm + 3 * mm

        # terms & conditions
        if _prefs.get("show_terms") and _prefs.get("terms_text"):
            c.setFont(FB, 8); c.setFillColor(DARK)
            c.drawString(margin, by, "Terms & Conditions")
            c.setFont(F, 7)
            c.setFillColor(GREY)
            import textwrap as _tw2
            tl = 0
            for para in _prefs["terms_text"].splitlines():
                for seg in _tw2.wrap(para, 90):
                    tl += 1
                    if tl > 5:
                        break
                    c.drawString(margin, by - tl * 3.5 * mm, seg)
                if tl > 5:
                    break
            by -= (min(tl, 5) + 1) * 3.5 * mm + 3 * mm

        # signature area
        if _prefs.get("show_signature"):
            sig_y = min(sy, by) - 8 * mm
            c.setStrokeColor(DARK); c.setLineWidth(0.5)
            c.setFont(F, 7.5); c.setFillColor(DARK)
            c.line(margin, sig_y, margin + 50 * mm, sig_y)
            c.drawString(margin, sig_y - 4 * mm, "Receiver's Signature")
            c.line(W - margin - 50 * mm, sig_y, W - margin, sig_y)
            c.drawRightString(W - margin, sig_y - 4 * mm, "Authorized Signature")

        # QR code (left side, aligned with totals)
        if qr_base64 and SHOW_QR:
            try:
                from modules.zatca.qr_generator import generate_qr_image
                qr_img = generate_qr_image(qr_base64, size=110)
                if qr_img:
                    buf = io.BytesIO()
                    qr_img.save(buf, format="PNG")
                    buf.seek(0)
                    from reportlab.lib.utils import ImageReader
                    qr_size = 30 * mm
                    c.drawImage(ImageReader(buf), margin, y - qr_size,
                                qr_size, qr_size)
                    c.setFont("Helvetica", 7)
                    c.setFillColor(GREY)
                    c.drawString(margin, y - qr_size - 4 * mm, "ZATCA QR Code")
                    if SHOW_AR:
                        try:
                            c.setFont(_AR_FONT, 7)
                        except Exception:
                            pass
                        c.drawString(margin + 22 * mm, y - qr_size - 4 * mm,
                                     _shape_arabic("رمز الاستجابة السريعة"))
            except Exception:
                pass
        low += [ty, sy, by]
        if qr_base64 and SHOW_QR:
            low.append(y - 30 * mm - 5 * mm)
        if _prefs.get("show_signature"):
            low.append(sig_y - 5 * mm)
        return min(low)

    FOOT = 22 * mm                        # footer text sits below this
    SUMM_H = 16 * mm                      # 'Items: …' summary under the table
    _probe = canvas.Canvas(io.BytesIO(), pagesize=(W, H))
    try:
        _register_fonts()
    except Exception:
        pass
    block_h = H - _bottom(_probe, H)

    y = draw_table_header(y)

    # Data rows
    c.setFont("Helvetica", 8)
    # track how many times each product name appears (line repeat count)
    name_counts = {}
    for idx, ln in enumerate(lines, 1):
        nm_full = ln.get("product_name_en", "")
        name_counts[nm_full] = name_counts.get(nm_full, 0) + 1
        rh = 7 * mm
        if TBL == "striped" and idx % 2 == 0:
            c.setFillColor(colors.HexColor("#F4F4F8"))
            c.rect(margin, y - rh, W - 2 * margin, rh, fill=1, stroke=0)
        c.setFillColor(DARK)

        name_en = nm_full
        if ln.get("offer_text") and float(ln.get("discount_amount") or 0):
            name_en = (name_en[:24] + "  · " + str(ln["offer_text"]))   # offer on this line
        vals = [
            str(idx),
            name_en[:42],
            f"{float(ln.get('quantity', 0)):g}",
            money(ln.get('unit_price', 0)),
            f"{float(ln.get('vat_rate', 15)):g}",
            money(ln.get('vat_amount', 0)),
            money(ln.get('line_total', 0)),
        ]
        if K["code"] == "IN":
            vals = [str(idx), name_en[:34], str(ln.get("hsn_code") or ""),
                    f"{float(ln.get('quantity', 0)):g}", money(ln.get('unit_price', 0)),
                    f"{float(ln.get('vat_rate', 0)):g}", money(ln.get('line_amount', 0)),
                    money(ln.get('line_total', 0))]
        for i, (v, al) in enumerate(zip(vals, aligns)):
            cx = col_x[i]; cw = col_x[i + 1] - col_x[i]
            c.setFont("Helvetica", 8)
            if al == "l":
                c.drawString(cx + 2 * mm, y - 5 * mm, v)
            elif al == "r":
                c.drawRightString(col_x[i + 1] - 2 * mm, y - 5 * mm, v)
            else:
                c.drawCentredString(cx + cw / 2, y - 5 * mm, v)
        if TBL == "bordered":
            c.setStrokeColor(BORDER); c.setLineWidth(0.3)
            c.line(margin, y - rh, W - margin, y - rh)
        y -= rh

        # page break: fill the page; the last page always gets at least a
        # few lines together with the totals block (never totals alone)
        left = len(lines) - idx
        if left:
            fits_all = y - left * rh - SUMM_H - block_h >= FOOT
            if not fits_all and (y - rh < 16 * mm
                                 or (left <= 3 and y - left * rh - SUMM_H - block_h < FOOT)):
                y = page_break(y)

    y -= 2 * mm

    # ── Line/description summary: total lines + repeated products ──
    total_qty = sum(float(l.get("quantity", 0) or 0) for l in lines)
    repeated = {n: cnt for n, cnt in name_counts.items() if cnt > 1}
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(margin, y - 4 * mm,
                 "Items: %d lines  ·  %d distinct products  ·  total qty %g"
                 % (len(lines), len(name_counts), total_qty))
    if repeated:
        rep_txt = ", ".join("%s ×%d" % (n[:20], cnt)
                            for n, cnt in list(repeated.items())[:6])
        c.drawString(margin, y - 8 * mm, "Repeated: " + rep_txt)
        y -= 4 * mm
    y -= 6 * mm

    if y - block_h < FOOT:                # no room under the items: new page
        y = page_break(y)
    top = FOOT + block_h
    c.setStrokeColor(BORDER); c.setLineWidth(0.4)
    c.line(margin, top + 3 * mm, W - margin, top + 3 * mm)
    _bottom(c, top)

    # ── Footer ────────────────────────────────────────────────
    if _prefs.get("footer"):
        c.setFillColor(DARK)
        c.setFont(FB, 8)
        c.drawCentredString(W / 2, 17.5 * mm, _prefs["footer"][:120])
    c.setFillColor(GREY)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 13 * mm, K["footer"])
    if SHOW_AR and K["code"] == "SA":
        c.setFont(_AR_FONT, 7)
        c.drawCentredString(W / 2, 9.5 * mm,
                            _shape_arabic("فاتورة ضريبية إلكترونية متوافقة مع "
                                          "هيئة الزكاة والضريبة والجمارك"))
    c.setFillColor(GREY)
    c.setFont("Helvetica", 6)
    _web = str(company.get("website") or "").strip()
    c.drawCentredString(W / 2, 6 * mm,
                        (f"{_web}   ·   " if _web else "") +
                        f"Generated {_pdt(datetime.now())}")
    c.drawRightString(W - margin, 8 * mm, "Page %d" % _page_state["n"])

    c.showPage()
    c.save()
    return output_path
