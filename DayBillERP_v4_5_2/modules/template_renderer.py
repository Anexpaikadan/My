# ============================================================
# DayBill ERP - Template Renderer (drag-drop layout -> real PDF)
# ------------------------------------------------------------
# This is the piece that makes the Report Designer's saved layout
# ACTUALLY control the printed document, instead of the designer
# being a cosmetic mock-up. Given a saved template (paper size,
# margins, colors) + its elements[] (x/y/w/h in mm + type + key)
# + the live document data, it renders a pixel/mm-accurate PDF with
# reportlab.
#
# Public entry point for the rest of the app:
#     render_document(doc_type, invoice, company, lines, out_path)
# -> renders via the DEFAULT saved template for doc_type if one
#    exists; otherwise returns None so the caller can fall back to
#    the existing built-in renderer (generate_invoice_pdf /
#    generate_thermal_receipt). This keeps every existing print path
#    100% backward compatible — nothing breaks if no template exists.
# ============================================================

import sys, os
from datetime import date, datetime


def _fd(v):
    try:
        from config import settings as _c
        return _c.fmt_date(v)
    except Exception:
        return "" if v is None else str(v)


def _ft(v):
    try:
        from config import settings as _c
        return _c.fmt_time(v)
    except Exception:
        return "" if v is None else str(v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reportlab.lib.pagesizes import A4, A5, letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas

PXMM = 2.2  # must match the designer canvas scale (ui/report_designer.py)

PAPER_MM = {
    "A4": (210, 297), "A5": (148, 210), "Letter": (216, 279),
    "80mm": (80, None), "58mm": (58, None),   # height grows with content
}

DEFAULT_TABLE_COLS = ["item_code", "product_name", "quantity", "rate",
                      "tax", "line_total"]
NUM_COLS = ("quantity", "rate", "tax", "line_total", "discount", "line_amount")
COL_TITLES = {
    "item_code": "Code", "product_name": "Product", "description": "Description",
    "quantity": "Qty", "unit": "Unit", "rate": "Rate", "discount": "Disc",
    "tax": "VAT", "line_total": "Total", "line_amount": "Amount",
    "product_name_ar": "الصنف",
}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def num(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return str(v or "")


def amount_in_words(n, currency="Saudi Riyal"):
    """Simple English amount-in-words (0-999999 range, no external deps)."""
    try:
        n = round(float(n), 2)
    except Exception:
        return ""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
            "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
            "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
            "Eighty", "Ninety"]

    def two(x):
        if x < 20:
            return ones[x]
        return tens[x // 10] + (f" {ones[x % 10]}" if x % 10 else "")

    def three(x):
        if x >= 100:
            return f"{ones[x // 100]} Hundred" + (f" {two(x % 100)}" if x % 100 else "")
        return two(x)

    whole = int(n)
    cents = int(round((n - whole) * 100))
    if whole == 0:
        words = "Zero"
    else:
        parts = []
        for div, name in [(1_000_000, "Million"), (1_000, "Thousand"), (1, "")]:
            chunk = whole // div
            whole %= div
            if chunk:
                parts.append(f"{three(chunk)} {name}".strip())
        words = " ".join(parts)
    out = f"{words} {currency}"
    if cents:
        out += f" and {two(cents)} Halalas"
    return out + " Only"


# ── dynamic token resolvers ─────────────────────────────────────────
def _header_tokens(invoice, company, lines, totals=None):
    totals = totals or {}
    subtotal = totals.get("subtotal", invoice.get("subtotal_amount", 0))
    tax = totals.get("tax", invoice.get("vat_amount", 0))
    grand = totals.get("grand", invoice.get("total_amount", 0))
    return {
        "invoice_number": invoice.get("invoice_number", ""),
        "invoice_date": _fd(invoice.get("invoice_date", "")),
        "due_date": _fd(invoice.get("due_date")) if invoice.get("due_date") else "",
        "customer_name": invoice.get("customer_name_en", invoice.get("party_name", "")),
        "customer_address": invoice.get("customer_address", ""),
        "customer_vat": invoice.get("customer_vat_no", ""),
        "salesperson": invoice.get("salesperson", invoice.get("created_by", "")),
        "payment_terms": invoice.get("payment_method", ""),
        "subtotal": num(subtotal),
        "discount_total": num(invoice.get("discount_amount", 0)),
        "tax_total": num(tax),
        "grand_total": num(grand),
        "paid_amount": num(invoice.get("paid_amount", grand)),
        "balance_amount": num(invoice.get("balance_amount",
                                          _f(grand) - _f(invoice.get("paid_amount", grand)))),
        "amount_in_words": amount_in_words(grand),
        "company_name": company.get("company_name_en", ""),
        "company_vat": company.get("vat_registration_no", ""),
        "company_address": ", ".join(filter(None, [
            company.get("street_name_en"), company.get("city_en"),
            company.get("state_en")])),
        "current_date": _fd(date.today()),
        "current_time": _ft(datetime.now()),
        "company_website": company.get("website", "") or "",
        "company_country": company.get("country", "") or "",
        "company_business_type": company.get("business_type", "") or "",
        "branch": invoice.get("branch_name", ""),
        "warehouse": invoice.get("warehouse_name", ""),
        "company_name_ar": company.get("company_name_ar", "") or "",
        "company_cr": company.get("cr_number", "") or "",
        "company_phone": company.get("phone", "") or "",
        "customer_name_ar": invoice.get("customer_name_ar", "") or "",
        "reference": (invoice.get("reference") or invoice.get("reference_number")
                      or invoice.get("supplier_invoice_no") or invoice.get("original_invoice_no")
                      or invoice.get("original_purchase_no") or invoice.get("po_number") or ""),
        "notes": invoice.get("notes_en", "") or "",
        "invoice_time": _ft(invoice.get("invoice_time")) if invoice.get("invoice_time") else "",
    }


def _item_value(line, key):
    m = {"item_code": "product_code", "product_name": "product_name_en",
         "description": "product_name_en", "quantity": "quantity",
         "unit": "unit_of_measure_en", "rate": "unit_price",
         "discount": "discount_amount", "tax": "vat_amount",
         "line_total": "line_total"}
    if key == "vat_rate":
        try:
            return f"{float(line.get('vat_rate') or 0):g}%"
        except (TypeError, ValueError):
            return ""
    if key == "line_amount" and line.get("line_amount") in (None, ""):
        return num(_f(line.get("line_total")) - _f(line.get("vat_amount")))
    v = line.get(m.get(key, key), "")
    if key == "quantity":
        try:
            return f"{float(v or 0):g}"
        except (TypeError, ValueError):
            return str(v or "")
    if key in ("rate", "discount", "tax", "line_total", "line_amount"):
        return num(v)
    return str(v if v is not None else "")


# ── element drawing ──────────────────────────────────────────────────
def _ar(text):
    return any("\u0600" <= ch <= "\u06FF" for ch in str(text or ""))


def _draw_text(c, el, value, tmpl, W, H, top_y):
    x = el["x"] / PXMM * mm
    y = top_y - (el["y"] + el["h"]) / PXMM * mm
    w = el["w"] / PXMM * mm
    h = el["h"] / PXMM * mm
    font = "Helvetica-Bold" if el.get("bold") else "Helvetica"
    size = max(6, int(el.get("font", 9)))
    value = str(value if value is not None else "")
    if _ar(value):
        try:
            from modules import pdf_invoice as _pi
            _pi._register_fonts()
            font = _pi._AR_FONT_BOLD if el.get("bold") else _pi._AR_FONT
            value = _pi._shape_arabic(value)
        except Exception:
            pass
    c.setFont(font, size)
    c.setFillColor(colors.HexColor(tmpl.get("font_color") or "#1A1438"))
    align = el.get("align", "left")
    ty = y + h / 2 - size * 0.35
    if align == "center":
        c.drawCentredString(x + w / 2, ty, value)
    elif align == "right":
        c.drawRightString(x + w, ty, value)
    else:
        c.drawString(x, ty, value)


def _draw_line(c, el, top_y):
    x = el["x"] / PXMM * mm
    y = top_y - el["y"] / PXMM * mm
    w = el["w"] / PXMM * mm
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.6)
    c.line(x, y, x + w, y)


def _draw_placeholder(c, el, label, tmpl, top_y, dash=True):
    x = el["x"] / PXMM * mm
    y = top_y - (el["y"] + el["h"]) / PXMM * mm
    w = el["w"] / PXMM * mm
    h = el["h"] / PXMM * mm
    c.setStrokeColor(colors.HexColor("#B8B8C8"))
    if dash:
        c.setDash(3, 2)
    c.setLineWidth(0.8)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setDash()
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#8888A0"))
    c.drawCentredString(x + w / 2, y + h / 2 - 3, label)


def _draw_qr_missing(c, el, top_y):
    """Preview only: a dashed box where the QR goes, saying what is missing."""
    x = el["x"] / PXMM * mm
    y = top_y - (el["y"] + el["h"]) / PXMM * mm
    w = el["w"] / PXMM * mm
    h = el["h"] / PXMM * mm
    c.saveState()
    c.setStrokeColor(colors.HexColor("#DC2626"))
    c.setDash(3, 2)
    c.setLineWidth(0.8)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setDash()
    c.setFillColor(colors.HexColor("#DC2626"))
    fs = max(4.5, min(7.0, w / 2.0 / 4.2))
    c.setFont("Helvetica-Bold", fs)
    cx, cy = x + w / 2, y + h / 2
    for i, txt in enumerate(("NO QR", "set company", "VAT number")):
        c.drawCentredString(cx, cy + fs * 1.2 - i * fs * 1.25, txt)
    c.restoreState()


def _draw_qr(c, el, data, top_y):
    x = el["x"] / PXMM * mm
    y = top_y - (el["y"] + el["h"]) / PXMM * mm
    size = min(el["w"], el["h"]) / PXMM * mm
    if not data:
        return
    try:
        from reportlab.graphics.barcode import qr
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        widget = qr.QrCodeWidget(str(data or ""))
        b = widget.getBounds()
        w, h = b[2] - b[0], b[3] - b[1]
        d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
        d.add(widget)
        renderPDF.draw(d, c, x, y)
        return
    except Exception:
        pass
    try:            # second way: the qrcode library → picture
        import io
        import qrcode
        from reportlab.lib.utils import ImageReader
        img = qrcode.make(str(data))
        buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
        c.drawImage(ImageReader(buf), x, y, width=size, height=size)
    except Exception:
        pass


def _draw_barcode(c, el, value, top_y):
    x = el["x"] / PXMM * mm
    y = top_y - (el["y"] + el["h"]) / PXMM * mm
    try:
        from reportlab.graphics.barcode import code128
        bc = code128.Code128(str(value), barHeight=el["h"] / PXMM * mm * 0.8,
                             barWidth=0.35)
        bc.drawOn(c, x, y)
    except Exception:
        pass


def _draw_logo(c, el, company, tmpl, top_y):
    path = company.get("logo_path")
    x = el["x"] / PXMM * mm
    y = top_y - (el["y"] + el["h"]) / PXMM * mm
    w = el["w"] / PXMM * mm
    h = el["h"] / PXMM * mm
    if path and os.path.exists(path):
        try:
            c.drawImage(path, x, y, width=w, height=h,
                       preserveAspectRatio=True, mask="auto")
            return
        except Exception:
            pass
    # no logo file set: leave the space empty on real documents


# ── main entry ────────────────────────────────────────────────────────
ROW_MM = 6.5                      # item-table row height


def _band(c, W, top, height_mm, color, text, size, align_bottom=False):
    """Header / footer band exactly like the designer canvas shows it."""
    if not height_mm or height_mm <= 0:
        return
    col = colors.HexColor(color or "#3A1FD6")
    hb = height_mm * mm
    y = top - hb
    c.setFillColor(col)
    c.rect(0, y, W, hb, fill=1, stroke=0)
    if text:
        light = str(color or "").upper() in ("#FFFFFF", "#FFF", "WHITE")
        c.setFillColor(colors.HexColor("#1A1438") if light else colors.white)
        font = "Helvetica-Bold" if not align_bottom else "Helvetica"
        text = str(text)[:120]
        if _ar(text):
            try:
                from modules import pdf_invoice as _pi
                _pi._register_fonts()
                font = _pi._AR_FONT_BOLD if not align_bottom else _pi._AR_FONT
                text = _pi._shape_arabic(text)
            except Exception:
                pass
        c.setFont(font, size)
        c.drawString(4.5 * mm, y + hb / 2 - size * 0.35, text)


def render_template(template, elements, invoice, company, lines, out_path,
                    totals=None, preview=False):
    """Render one saved template + its elements to a real PDF.

    Everything is placed where it was drawn in the designer. The item
    table grows with the number of lines; whatever was drawn BELOW the
    table moves down by the same amount, and a long table continues on
    the next page (with the header band and column titles again)."""
    lines = list(lines or [])
    paper = template.get("paper_size", "A4")
    pw_mm, ph_mm = PAPER_MM.get(paper, (210, 297))
    if str(template.get("orientation", "portrait")) == "landscape" and ph_mm:
        pw_mm, ph_mm = ph_mm, pw_mm
    hdr_mm = float(template.get("header_height") or 0) / 3.0
    ftr_mm = float(template.get("footer_height") or 0) / 3.0
    elements = sorted(elements or [], key=lambda e: (e.get("y", 0), e.get("x", 0)))
    tbl = _items_table(elements)              # separate columns (or old one-block table)
    if tbl:
        _squeeze_to_page(tbl, pw_mm * PXMM)   # columns past the paper edge never get lost
    table = tbl["rect"] if tbl else None
    grow_px = 0.0
    if tbl:
        need_mm = tbl["head_mm"] + sum(_row_mm(tbl, ln) for ln in lines)
        grow_px = max(0.0, need_mm * PXMM - float(table.get("h") or 0))
    roll = ph_mm is None
    if roll:                        # thermal roll: page as long as needed
        bottom_px = max([float(e.get("y", 0)) + float(e.get("h", 0)) for e in elements] or [200])
        ph_mm = bottom_px / PXMM + grow_px / PXMM + ftr_mm + 12
    W, H = pw_mm * mm, ph_mm * mm
    c = rl_canvas.Canvas(out_path, pagesize=(W, H))
    tokens = _header_tokens(invoice, company, lines, totals)
    qr_data = invoice.get("qr_code_data")
    if not qr_data:
        try:
            from modules.zatca.qr_generator import phase1_for_invoice
            qr_data = phase1_for_invoice(invoice, company)
        except Exception:
            qr_data = ""
    hdr_color = template.get("header_color") or "#3A1FD6"
    ftr_color = template.get("footer_color") or hdr_color

    def bands():
        _band(c, W, H, hdr_mm, hdr_color, template.get("header_text") or "", 11)
        _band(c, W, ftr_mm * mm, ftr_mm, ftr_color, template.get("footer_text") or "", 8,
              align_bottom=True)

    def draw(el, top_y):
        etype = el.get("type", "text")
        key = el.get("key", "")
        if etype == "line":
            _draw_line(c, el, top_y)
        elif etype in ("image", "company_logo") or key == "company_logo":
            _draw_logo(c, el, company, template, top_y)
        elif etype == "qr" or key == "qr_code":
            if not qr_data and preview:          # designer Preview: say why it is empty
                _draw_qr_missing(c, el, top_y)
            else:
                _draw_qr(c, el, qr_data, top_y)
        elif etype == "barcode" or key == "barcode":
            _draw_barcode(c, el, tokens["invoice_number"], top_y)
        elif etype in ("signature", "stamp"):
            _draw_signature(c, el, template, top_y)
        else:  # plain text / dynamic token / custom label
            if key in ("text_label", "custom_text") or key not in tokens:
                value = el.get("custom_text") or el.get("label", "")
            else:
                value = tokens.get(key, "")
                if value in ("", None) and el.get("hide_empty", True):
                    return
                if key in ("discount_total",) and value in ("0.00", "0"):
                    return                           # no discount → no line
                value = f"{el.get('prefix', '') or ''}{value}"
            _draw_text(c, el, value, template, W, H, top_y)

    bands()
    page_top = H                                   # PDF y of designer y=0
    bottom_limit = (ftr_mm + 6) * mm
    if table is None:
        for el in elements:
            draw(el, page_top)
    else:
        t_y = float(table.get("y", 0))
        t_bottom = t_y + float(table.get("h") or 0)
        rest = [e for e in elements if e not in tbl["skip"]]
        tx0 = float(table["x"]); tx1 = tx0 + float(table["w"])
        above = [e for e in rest if float(e.get("y", 0)) < t_bottom
                 and float(e.get("y", 0)) + float(e.get("h", 0)) <= t_y + 1]
        # beside = next to the table (no horizontal overlap); anything that
        # overlaps the table's width and starts inside it goes UNDER it
        beside = [e for e in rest if e not in above and float(e.get("y", 0)) < t_bottom
                  and (float(e.get("x", 0)) >= tx1 - 1
                       or float(e.get("x", 0)) + float(e.get("w", 0)) <= tx0 + 1)]
        below = [e for e in rest if e not in above and e not in beside]
        for el in above + beside:
            draw(el, page_top)
        # table, continuing on new pages when it runs out of room
        y = page_top - t_y / PXMM * mm
        restart_y = H - (hdr_mm + 6) * mm
        y = _cols_header(c, tbl, y, template)
        for i, ln in enumerate(lines):
            rh = _row_mm(tbl, ln) * mm
            if not roll and y - rh < bottom_limit:
                c.showPage(); bands()
                y = _cols_header(c, tbl, restart_y, template)
            _cols_row(c, tbl, y, ln, i, template, rh)
            y -= rh
        # under the table: totals / QR / words FOLLOW the table; things
        # drawn in the lower part of the page (signatures, stamp, bank…)
        # stay ANCHORED there, just above the footer
        page_px = ph_mm * PXMM
        anchored = [] if roll else [e for e in below if e.get("anchor") == "bottom" or (
            e.get("anchor") != "follow" and float(e.get("y", 0)) >= page_px * 0.62)]
        follow = [e for e in below if e not in anchored]
        # under-table elements keep their gap to the table; one that was
        # drawn inside the table box starts just under the items
        f_top = min([float(e.get("y", 0)) for e in follow] or [t_bottom])
        base = min(t_bottom, f_top - 6)
        gap_top = y + base / PXMM * mm
        need = max([float(e.get("y", 0)) + float(e.get("h", 0)) - base for e in follow] or [0])
        anch_top = min([float(e.get("y", 0)) for e in anchored] or [page_px])
        floor = max(bottom_limit, page_top - anch_top / PXMM * mm + 2 * mm) if anchored else bottom_limit
        if follow and not roll and y - need / PXMM * mm < floor:
            c.showPage(); bands()
            gap_top = restart_y + base / PXMM * mm
            y = restart_y
        elif anchored and not follow and y < floor and not roll:
            c.showPage(); bands()
        for el in follow:
            draw(el, gap_top)
        for el in anchored:
            draw(el, page_top)
    c.showPage()
    c.save()
    return out_path


_OLD_COLS_R = {"description": "product_name"}


def _items_table(elements):
    """The item table of a layout: its separate column elements (or the
    old one-block table split into columns). None when there is none."""
    cols = [e for e in elements if e.get("type") == "item_col"]
    skip = list(cols)
    legacy = next((e for e in elements if e.get("type") == "table" or e.get("key") == "table"), None)
    if legacy is not None:
        skip.append(legacy)
        from modules.report_designer import split_table, item_columns
        if not cols:
            cols = split_table(legacy)
        else:
            # an old one-block table AND separate columns added later (e.g. a
            # 'VAT Amount' column): print ONE table with all of them — before,
            # the old table vanished and only the new column printed
            fields = [_OLD_COLS_R.get(f, f) for f in (legacy.get("cols") or DEFAULT_TABLE_COLS)]
            fields += [e.get("field") for e in cols if e.get("field") not in fields]
            cols = item_columns(fields, legacy.get("x", 8), legacy.get("y", 134),
                                legacy.get("w", 446), max(30, int(legacy.get("h") or 30)),
                                font=int(legacy.get("font") or 8))
    if not cols:
        return None
    cols = sorted(cols, key=lambda e: float(e.get("x", 0)))
    x0 = min(float(e["x"]) for e in cols)
    x1 = max(float(e["x"]) + float(e["w"]) for e in cols)
    y0 = min(float(e["y"]) for e in cols)
    y1 = max(float(e["y"]) + float(e.get("h") or 30) for e in cols)
    two_head = any(e.get("header_ar") and e.get("label_ar") for e in cols)
    return {"cols": cols, "skip": skip,
            "rect": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0},
            "head_mm": ROW_MM * (1.55 if two_head else 1.0),
            "two_line": [e for e in cols if e.get("field", "").startswith("product_name")
                         and e.get("ar_second_line", True) and e.get("field") == "product_name"]}


def _squeeze_to_page(tbl, page_px):
    """A column drawn (partly) past the right edge of the paper — e.g. a
    'VAT Amount' column added to an 80 mm roll — would be cut off. Shrink
    all columns by the same ratio so the whole table fits on the paper."""
    r = tbl["rect"]
    margin = 4.0 if page_px < 300 else 8.0
    right = page_px - margin
    if r["x"] + r["w"] <= right + 0.5 or r["x"] >= right - 20:
        return
    k = (right - r["x"]) / float(r["w"])
    new = []
    for e in tbl["cols"]:
        e = dict(e)
        e["x"] = r["x"] + (float(e["x"]) - r["x"]) * k
        e["w"] = float(e["w"]) * k
        new.append(e)
    two = {id(e) for e in tbl["two_line"]}
    tbl["two_line"] = [n for o, n in zip(tbl["cols"], new) if id(o) in two]
    tbl["cols"] = new
    r["w"] = right - r["x"]


def _row_mm(tbl, ln):
    if tbl["two_line"] and str(ln.get("product_name_ar") or "").strip() and \
            str(ln.get("product_name_ar")).strip() != str(ln.get("product_name_en") or "").strip():
        return ROW_MM * 1.6
    return ROW_MM


def _fit(c, text, font, size, width):
    """Shorten text to fit the column (…)."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    text = str(text or "")
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…" if text else ""


def _ar_font(bold=False):
    try:
        from modules import pdf_invoice as _pi
        _pi._register_fonts()
        return (_pi._AR_FONT_BOLD if bold else _pi._AR_FONT), _pi._shape_arabic
    except Exception:
        return ("Helvetica-Bold" if bold else "Helvetica"), (lambda t: t)


def _is_numberish(text):
    t = str(text or "").strip()
    return bool(t) and all(ch.isdigit() or ch in ".,-%+ " for ch in t)


def _cell_text(c, text, el, x, w, base_y, size, bold=False, align=None, color=None,
               shrink=False):
    """Write one table cell. Numbers / short values are never cut to '…'
    (a narrow VAT / Qty / # column on an 80 mm roll used to print '4.…' or
    nothing): the font gets smaller to fit instead. Long text is shortened."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    text = str(text or "")
    pad = min(1.6 * mm, max(0.4 * mm, w * 0.12))
    if _ar(text):
        font, shape = _ar_font(bold)
        text = shape(text)
        align = align or "right"
    else:
        font = "Helvetica-Bold" if bold else "Helvetica"
    room = max(2, w - 2 * pad)
    if shrink or _is_numberish(text) or len(text) <= 3:
        # column titles + numbers: smaller font before any '…'
        while size > 4.5 and stringWidth(text, font, size) > room:
            size -= 0.5
    if not (_is_numberish(text) or len(text) <= 3):
        text = _fit(c, text, font, size, room)
    c.setFont(font, size)
    if color is not None:
        c.setFillColor(color)
    al = align or el.get("align", "left")
    if al == "right":
        c.drawRightString(x + w - pad, base_y, text)
    elif al == "center":
        c.drawCentredString(x + w / 2, base_y, text)
    else:
        c.drawString(x + pad, base_y, text)


def _col_x(el):
    return float(el["x"]) / PXMM * mm, float(el["w"]) / PXMM * mm


def _cols_header(c, tbl, y, tmpl):
    cols = tbl["cols"]
    hh = tbl["head_mm"] * mm
    x0 = tbl["rect"]["x"] / PXMM * mm
    tw = tbl["rect"]["w"] / PXMM * mm
    c.setFillColor(colors.HexColor(tmpl.get("table_color") or "#3A1FD6"))
    c.rect(x0, y - hh, tw, hh, fill=1, stroke=0)
    two = tbl["head_mm"] > ROW_MM
    for el in cols:
        x, w = _col_x(el)
        size = max(6, int(el.get("font") or 8))
        if two and el.get("header_ar") and el.get("label_ar"):
            _cell_text(c, el.get("label", ""), el, x, w, y - hh * 0.42, size, True,
                       color=colors.white, shrink=True)
            _cell_text(c, el.get("label_ar", ""), el, x, w, y - hh * 0.85, size - 1, False,
                       align=el.get("align", "left") if el.get("align") != "left" else "left",
                       color=colors.white, shrink=True)
        else:
            _cell_text(c, el.get("label", ""), el, x, w, y - hh + (hh - size * 0.7) / 2,
                       size, True, color=colors.white, shrink=True)
    if cols[0].get("cell_lines", True):
        c.setStrokeColor(colors.white); c.setLineWidth(0.4)
        for el in cols[1:]:
            x, _w = _col_x(el)
            c.line(x, y - hh, x, y)
    return y - hh


def _cols_row(c, tbl, y, ln, i, tmpl, rh):
    cols = tbl["cols"]
    x0 = tbl["rect"]["x"] / PXMM * mm
    tw = tbl["rect"]["w"] / PXMM * mm
    lines_on = tbl["cols"][0].get("cell_lines", True)
    if i % 2 == 1 and tbl["cols"][0].get("stripes", True):
        c.setFillColor(colors.HexColor("#F5F6FA"))
        c.rect(x0, y - rh, tw, rh, fill=1, stroke=0)
    ink = colors.HexColor(tmpl.get("font_color") or "#1A1438")
    for el in cols:
        x, w = _col_x(el)
        f = el.get("field") or str(el.get("key", "")).replace("col:", "")
        size = max(6, int(el.get("font") or 8))
        bold = bool(el.get("bold"))
        if f == "line_no":
            val = str(i + 1)
        else:
            val = _item_value(ln, f)
        if f == "product_name" and rh > ROW_MM * mm * 1.2:
            # English on the first line, Arabic on the second
            _cell_text(c, val, el, x, w, y - rh * 0.40, size, bold, color=ink)
            _cell_text(c, ln.get("product_name_ar", ""), el, x, w, y - rh * 0.84,
                       size, False, color=colors.HexColor("#444A55"))
        else:
            _cell_text(c, val, el, x, w, y - rh / 2 - size * 0.35, size, bold, color=ink)
    if lines_on:
        c.setStrokeColor(colors.HexColor("#C9D2DE")); c.setLineWidth(0.4)
        c.line(x0, y - rh, x0 + tw, y - rh)                  # under the row
        c.line(x0, y, x0, y - rh); c.line(x0 + tw, y, x0 + tw, y - rh)
        for el in cols[1:]:
            x, _w = _col_x(el)
            c.line(x, y, x, y - rh)


def _table_header(c, x0, y, w, cols, tmpl, row_h):
    col_w = w / max(1, len(cols))
    c.setFillColor(colors.HexColor(tmpl.get("table_color") or "#3A1FD6"))
    c.rect(x0, y - row_h, w, row_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    for i, key in enumerate(cols):
        cx = x0 + i * col_w
        title = COL_TITLES.get(key, key.replace("_", " ").title())
        if key in NUM_COLS:
            c.drawRightString(cx + col_w - 3, y - row_h + 2 * mm, title)
        else:
            c.drawString(cx + 3, y - row_h + 2 * mm, title)
    return y - row_h


def _table_row(c, x0, y, w, cols, ln, i, tmpl, row_h):
    col_w = w / max(1, len(cols))
    if i % 2 == 0:
        c.setFillColor(colors.HexColor("#F5F5FA"))
        c.rect(x0, y - row_h, w, row_h, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(tmpl.get("font_color") or "#1A1438"))
    c.setFont("Helvetica", 8)
    for j, key in enumerate(cols):
        cx = x0 + j * col_w
        val = _item_value(ln, key)
        if key in NUM_COLS:
            c.drawRightString(cx + col_w - 3, y - row_h + 2 * mm, val)
        elif _ar(val):
            try:
                from modules import pdf_invoice as _pi
                _pi._register_fonts()
                c.setFont(_pi._AR_FONT, 8)
                c.drawRightString(cx + col_w - 3, y - row_h + 2 * mm, _pi._shape_arabic(val[:40]))
            finally:
                c.setFont("Helvetica", 8)
        else:
            max_chars = max(4, int(col_w / (8 * 0.5)))
            c.drawString(cx + 3, y - row_h + 2 * mm, val[:max_chars])


def _draw_signature(c, el, tmpl, top_y):
    """A signature / stamp line with its caption (no dashed box on paper)."""
    x = el["x"] / PXMM * mm
    y = top_y - (el["y"] + el["h"]) / PXMM * mm
    w = el["w"] / PXMM * mm
    c.setStrokeColor(colors.HexColor("#888888"))
    c.setLineWidth(0.6)
    c.line(x, y + 4 * mm, x + w, y + 4 * mm)
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(x, y + 1 * mm, str(el.get("label") or "Signature"))


def render_document(doc_type, invoice, company, lines, out_path, totals=None):
    """
    Try the user's saved default template for doc_type. Returns the PDF
    path on success, or None if no custom template exists (caller should
    then fall back to the existing built-in renderer — nothing breaks).
    """
    try:
        from modules import report_designer as rd
        if not rd.tables_ready():
            return None
        tmpl = rd.get_default_template(doc_type)
        if not tmpl:
            return None
        elements = rd.load_layout(tmpl["template_id"])
        if not elements:
            return None
        return render_template(tmpl, elements, invoice, company, lines,
                               out_path, totals=totals)
    except Exception:
        return None   # any problem -> silently fall back, never break printing


def get_template_printer(doc_type):
    """The printer saved against doc_type's DEFAULT template, if any.
    Returns None if no template or no printer was chosen — callers should
    fall back to Printer Management's per-document mapping."""
    try:
        from modules import report_designer as rd
        if not rd.tables_ready():
            return None
        tmpl = rd.get_default_template(doc_type)
        if not tmpl:
            return None
        return rd.get_template_printer(tmpl["template_id"])
    except Exception:
        return None


def demo_data():
    """Realistic sample data for the designer's Preview button."""
    invoice = {
        "invoice_number": "INV-000123", "invoice_date": date.today().isoformat(),
        "due_date": "", "customer_name_en": "Al Salam Trading Est.",
        "customer_address": "Olaya St, Riyadh", "customer_vat_no": "300000000000003",
        "payment_method": "Cash", "subtotal_amount": 100, "vat_amount": 15,
        "total_amount": 115, "discount_amount": 0, "paid_amount": 115,
        "balance_amount": 0, "qr_code_data": "",   # real ZATCA QR built from these figures
    }
    company = {"company_name_en": "My Company", "vat_registration_no": "310000000000003",
              "city_en": "Riyadh", "street_name_en": "King Fahd Rd", "logo_path": ""}
    lines = [
        {"product_code": "P0001", "product_name_en": "Basmati Rice 5kg",
         "product_name_ar": "أرز بسمتي 5 كجم", "barcode": "6281000000017",
         "quantity": 2, "unit_of_measure_en": "Pcs", "unit_price": 25, "vat_rate": 15,
         "line_amount": 50, "vat_amount": 7.5, "line_total": 57.5},
        {"product_code": "P0002", "product_name_en": "Olive Oil 1L",
         "product_name_ar": "زيت زيتون 1 لتر", "barcode": "6281000000024",
         "quantity": 1, "unit_of_measure_en": "Pcs", "unit_price": 50, "vat_rate": 15,
         "line_amount": 50, "vat_amount": 7.5, "line_total": 57.5},
    ]
    return invoice, company, lines
