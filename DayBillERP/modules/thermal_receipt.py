# ============================================================
# DayBill ERP - Thermal Receipt (80mm) Generator
# Narrow receipt for thermal/POS printers. Includes ZATCA QR.
# ============================================================



def generate_thermal_receipt(invoice: dict, company: dict, lines: list,
                             output_path: str, qr_data: str = None, _page_h=None) -> str:
    """
    Generate an 80mm-wide thermal receipt PDF.
    The page is exactly as long as the content (first pass measures it),
    so the ZATCA QR and footer are never cut off.
    """
    import io as _io
    if qr_data is None:
        qr_data = invoice.get("qr_code_data")
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    # Reuse Arabic helpers from the A4 invoice module
    try:
        from modules.pdf_invoice import _shape_arabic, _register_fonts
        _register_fonts()
        from modules import pdf_invoice as _pi
        AR = _pi._AR_FONT
    except Exception:
        AR = "Helvetica"
        def _shape_arabic(t):  # noqa
            return t

    # Print & Invoice settings (paper width, footer, Arabic toggle)
    try:
        from modules.print_prefs import get_prefs
        _prefs = get_prefs()
    except Exception:
        _prefs = {"paper_width": "80", "footer": "", "show_arabic": True}
    _SHOW_AR = _prefs.get("show_arabic", True)
    _pw = str(_prefs.get("paper_width"))
    if _pw not in ("58", "80"):
        # A4 chosen for invoices -> receipts follow Settings ▸ Printing ▸ POS Paper Size
        try:
            from config import settings as _c
            _pw = "58" if str(_c.get("pos_paper_size", "80mm")).startswith("58") else "80"
        except Exception:
            _pw = "80"
    width = (58 * mm) if _pw == "58" else (80 * mm)
    measuring = _page_h is None
    height = (2000 * mm) if measuring else _page_h
    c = canvas.Canvas(_io.BytesIO() if measuring else output_path, pagesize=(width, height))
    y = height - 6 * mm
    cx = width / 2

    def center(text, size=8, font="Helvetica", gap=4.5):
        nonlocal y
        c.setFont(font, size)
        c.drawCentredString(cx, y, str(text))
        y -= gap * mm

    def center_ar(text, size=8, gap=4.5):
        nonlocal y
        c.setFont(AR, size)
        c.drawCentredString(cx, y, _shape_arabic(text))
        y -= gap * mm

    def rule():
        nonlocal y
        c.setDash(1, 2)
        c.line(4 * mm, y, width - 4 * mm, y)
        c.setDash()
        y -= 3 * mm

    def row(left, right, size=7, font="Helvetica"):
        nonlocal y
        c.setFont(font, size)
        c.drawString(4 * mm, y, str(left)[:28])
        c.drawRightString(width - 4 * mm, y, str(right))
        y -= 4 * mm

    # v7.0: the company's country — tax word, tax-number label, symbol,
    # Saudi QR only, no Arabic on Indian bills, CGST / SGST / IGST
    try:
        from modules import country as _K
        _code, _sym, _tax, _taxno = _K.code(), _K.symbol(), _K.tax_name(), _K.tax_no_label()
        _num = _K.num
    except Exception:
        _K, _code, _sym, _tax, _taxno = None, "SA", "SAR", "VAT", "VAT"
        _num = lambda v, *a, **k: "{:,.2f}".format(float(v or 0))  # noqa: E731
    if _code == "IN":
        _SHOW_AR = False
    if _code != "SA":
        qr_data = None

    # ── Header ───────────────────────────────────────────────
    center(company.get("company_name_en", "Store"), 11, "Helvetica-Bold", 5)
    if _SHOW_AR and company.get("company_name_ar"):
        center_ar(company.get("company_name_ar"), 10, 5)
    try:  # Settings ▸ POS: custom receipt header line
        from config import settings as _cfg0
        _hdr = str(_cfg0.get("pos_receipt_header") or "").strip()
        if _hdr:
            center(_hdr[:40], 7)
        _print_vat_no = _cfg0.flag("pos_print_vat_no", True)
    except Exception:
        _print_vat_no = True
    if company.get("vat_registration_no") and _print_vat_no:
        center(f"{_taxno}: {company['vat_registration_no']}", 7)
    if company.get("address_en"):
        center(company.get("address_en", "")[:40], 6, "Helvetica", 4)
    y -= 1 * mm
    # B2C bill (buyer has no VAT number) = Simplified Tax Invoice
    if str(invoice.get("invoice_type_code") or "") == "383":       # v6.0 debit note
        center("DEBIT NOTE", 9, "Helvetica-Bold", 4.2)
        center_ar("إشعار مدين", 9, 4.5)
        if invoice.get("original_invoice_no"):
            center("For invoice %s" % invoice.get("original_invoice_no"), 7)
    elif str(invoice.get("customer_vat_no") or "").strip() or _code == "IN":
        center("TAX INVOICE" if (_code != "IN" or float(invoice.get("vat_amount") or 0))
               else "BILL OF SUPPLY", 9, "Helvetica-Bold", 4.2)
        if _SHOW_AR:
            center_ar("فاتورة ضريبية", 9, 4.5)
    else:
        center("SIMPLIFIED TAX INVOICE", 9, "Helvetica-Bold", 4.2)
        center_ar("فاتورة ضريبية مبسطة", 9, 4.5)
    rule()

    # ── Invoice meta ─────────────────────────────────────────
    row("Invoice #", invoice.get("invoice_number", ""))
    try:
        from config import settings as _cf
        _dt_txt = _cf.fmt_date(invoice.get("invoice_date", ""))
        if invoice.get("invoice_time"):
            _dt_txt += "  " + _cf.fmt_time(invoice.get("invoice_time"))
    except Exception:
        _dt_txt = str(invoice.get("invoice_date", ""))
    row("Date", _dt_txt)
    if invoice.get("customer_name_en"):
        row("Customer", invoice.get("customer_name_en", ""))
    if invoice.get("customer_vat_no") and _code != "SA":
        row(_taxno, invoice.get("customer_vat_no"))
    _pos = ""
    if _code == "IN" and _K is not None:
        _pos = _K.place_of_supply("sales", invoice)
        row("Place of supply", _K.state_label(_pos)[:26], 6)
    rule()

    # ── Column headers ───────────────────────────────────────
    try:    # Settings ▸ POS: print the VAT of each item
        from config import settings as _cv
        _vat_item = _cv.flag("receipt_vat_per_item", True)
    except Exception:
        _vat_item = True
    _vat_col = _vat_item and width >= 76 * mm          # 80 mm: own column
    # x of the right edge of each number column
    if _vat_col:
        X_QTY, X_PRICE, X_VAT, X_TOT = width - 33 * mm, width - 23 * mm, width - 13 * mm, width - 4 * mm
    else:
        X_QTY, X_PRICE, X_VAT, X_TOT = width - 22 * mm, width - 12 * mm, None, width - 4 * mm
    c.setFont("Helvetica-Bold", 6)
    c.drawString(4 * mm, y, "Item")
    c.drawRightString(X_QTY, y, "Qty")
    c.drawRightString(X_PRICE, y, "Price")
    if X_VAT:
        c.drawRightString(X_VAT, y, _tax)
    c.drawRightString(X_TOT, y, "Total")
    y -= 4 * mm
    rule()

    # ── Line items ───────────────────────────────────────────
    for ln in lines:
        name = str(ln.get("product_name_en", ""))[:30]
        qty = float(ln.get("quantity", 0))
        price = float(ln.get("unit_price", 0))
        total = float(ln.get("line_total", ln.get("line_amount", 0)))
        c.setFont("Helvetica", 7)
        c.drawString(4 * mm, y, name)
        y -= 3.6 * mm
        c.setFont("Helvetica", 6)
        _lvat = float(ln.get("vat_amount") or 0)
        c.drawRightString(X_QTY, y, f"{qty:g}")
        c.drawRightString(X_PRICE, y, f"{price:,.2f}")
        if X_VAT:
            c.drawRightString(X_VAT, y, f"{_lvat:,.2f}")
        c.drawRightString(X_TOT, y, f"{total:,.2f}")
        y -= 4.5 * mm
        if _vat_item and not X_VAT and abs(_lvat) > 0.004:    # 58 mm: small line
            c.setFont("Helvetica", 5.5)
            c.drawRightString(X_TOT, y + 1.2 * mm, _tax + " %g%%  %s" % (
                float(ln.get("vat_rate") or 0), f"{_lvat:,.2f}"))
            y -= 2.6 * mm
        _disc = float(ln.get("discount_amount") or 0)
        if abs(_disc) > 0.004:          # offer / discount on this line
            c.setFont("Helvetica-Oblique", 6)
            c.drawString(6 * mm, y + 1 * mm,
                         ("Offer: " + str(ln.get("offer_text") or "discount"))[:34])
            c.drawRightString(width - 4 * mm, y + 1 * mm, f"-{abs(_disc):,.2f}")
            y -= 3.2 * mm
    rule()
    _saved = sum(float(l.get("discount_amount") or 0) for l in lines
                 if float(l.get("quantity") or 0) > 0)

    # ── Totals ───────────────────────────────────────────────
    sub = float(invoice.get("subtotal_amount") or invoice.get("taxable_amount") or 0)
    vat = float(invoice.get("vat_amount") or 0)
    grand = float(invoice.get("total_amount") or 0)
    try:
        from config import settings as _c2
        _show_vat = _c2.flag("pos_show_vat_receipt", True)
        _rate = float(_c2.get("tax_sales_rate", 15) or 15)
    except Exception:
        _show_vat, _rate = True, 15.0
    _rates = {round(float(l.get("vat_rate") or 0), 2) for l in lines if abs(float(l.get("vat_amount") or 0)) > 0.004}
    if len(_rates) == 1:
        _rate = list(_rates)[0]
    row("Subtotal", _num(sub), 7)
    if _show_vat:
        if _code == "IN" and _K is not None:      # India: CGST + SGST, or IGST
            _sp = _K.gst_split(vat, _pos)
            if _sp["igst"]:
                row("IGST", _num(_sp["igst"]), 7)
            else:
                row("CGST", _num(_sp["cgst"]), 7)
                row(_K.tax_head_label("sgst"), _num(_sp["sgst"]), 7)
        else:
            row((_tax + " %g%%" % _rate) if len(_rates) <= 1 else _tax, _num(vat), 7)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(4 * mm, y, "TOTAL")
    _gt = _num(grand)
    c.drawRightString(width - 4 * mm, y, (_sym + _gt) if _sym == "₹" else
                      ("%s %s" % (_gt, _sym) if _code == "SA" else "%s %s" % (_sym, _gt)))
    y -= 6 * mm
    if _saved > 0.004:                  # what the offers saved the customer
        center(f"*** YOU SAVED {_num(_saved)} {_sym} ***", 8, "Helvetica-Bold", 4.2)
        if _SHOW_AR:
            center_ar("وفّرت %s %s" % (f"{_saved:,.2f}", "درهم" if _code == "AE" else "ريال"), 8, 4.5)
    rule()

    # ── ZATCA QR code ────────────────────────────────────────
    try:  # Settings ▸ POS: Print QR Code
        from config import settings as _cfgq
        _qr_on = _cfgq.flag("pos_qr_print", True)
    except Exception:
        _qr_on = True
    if qr_data and _qr_on:
        try:
            import qrcode, io
            qr = qrcode.make(qr_data)
            buf = io.BytesIO(); qr.save(buf, format="PNG"); buf.seek(0)
            size = min(32 * mm, width - 16 * mm)
            c.drawImage(ImageReader(buf), cx - size / 2, y - size, size, size)
            y -= size + 2 * mm
        except Exception:
            pass

    # Settings ▸ POS: receipt footer fallback + custom thank-you line
    try:
        from config import settings as _cfg
        if not _prefs.get("footer"):
            _pf = str(_cfg.get("pos_receipt_footer") or "").strip()
            if _pf:
                _prefs["footer"] = _pf
        _thanks = str(_cfg.get("pos_thankyou") or "").strip()
    except Exception:
        _thanks = ""

    if _prefs.get("footer"):
        for chunk in [(_prefs["footer"][i:i+38]) for i in range(0, len(_prefs["footer"][:114]), 38)]:
            center(chunk, 7, "Helvetica", 4)
    if _thanks:
        center(_thanks[:48], 8, "Helvetica-Bold", 4)
    elif _SHOW_AR:
        center("Thank you!", 8, "Helvetica-Bold", 4)
        center_ar("شكراً لزيارتكم", 8, 4)
    else:
        center("Thank you!", 8, "Helvetica-Bold", 4)
    # v6.8: "Rate your visit" QR → the Tally feedback form, with this bill no.
    try:
        from modules import online_forms as _of
        _fb = _of.receipt_qr_link(invoice)
    except Exception:
        _fb = ""
    if _fb:
        try:
            import qrcode, io
            y -= 1 * mm
            center("Rate your visit - scan", 7, "Helvetica-Bold", 3.5)
            if _SHOW_AR:
                center_ar("قيّم زيارتك", 7, 3.5)
            buf = io.BytesIO(); qrcode.make(_fb, border=1).save(buf, format="PNG"); buf.seek(0)
            size = min(20 * mm, width - 20 * mm)
            c.drawImage(ImageReader(buf), cx - size / 2, y - size, size, size)
            y -= size + 2 * mm
        except Exception:
            pass
    center("Powered by DayBill ERP", 5, "Helvetica", 4)

    c.showPage()
    c.save()
    if measuring:
        used = height - y + 3 * mm
        return generate_thermal_receipt(invoice, company, lines, output_path,
                                        qr_data=qr_data, _page_h=used)
    return output_path
