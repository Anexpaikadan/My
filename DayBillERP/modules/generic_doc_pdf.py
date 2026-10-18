# ============================================================
# DayBill ERP - Generic document PDF (built-in fallback)
# ------------------------------------------------------------
# Purchase Invoice, Sales/Purchase Return, and Vouchers had NO print
# capability at all. This gives every one of them a clean, on-brand
# PDF using the same visual language as the sales invoice (accent
# color, header band, item table) — used whenever no custom Report
# Designer template exists for that document type.
#
# Two shapes:
#   with_items=True   -> header + party block + item table + totals
#                         (Purchase Invoice, Sales/Purchase Return)
#   with_items=False  -> header + party block + single amount +
#                         narration (Payment/Receipt/Journal Voucher)
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

TITLES = {
    "purchase_invoice": "PURCHASE INVOICE", "sales_return": "SALES RETURN",
    "purchase_return": "PURCHASE RETURN", "payment_voucher": "PAYMENT VOUCHER",
    "receipt_voucher": "RECEIPT VOUCHER", "journal_voucher": "JOURNAL VOUCHER",
    "contra_voucher": "CONTRA VOUCHER",
    "quotation": "QUOTATION", "purchase_order": "PURCHASE ORDER",
}
ACCENTS = {
    "purchase_invoice": "#1D4ED8", "sales_return": "#B91C1C",
    "purchase_return": "#B45309", "payment_voucher": "#B91C1C",
    "receipt_voucher": "#0F766E", "journal_voucher": "#475569",
    "contra_voucher": "#475569",
    "quotation": "#0F766E", "purchase_order": "#1D4ED8",
}


def _cur():
    try:
        from modules import country as _K
        return _K.symbol()
    except Exception:
        return "SAR"

def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


def generate_generic_pdf(doc_type, header, company, lines, out_path,
                         party_label="Party", with_items=True):
    """
    header : {"number","date","party_name","party_address","notes",
              "subtotal","vat","total","amount","narration",...}
    lines  : list of item dicts (product_code/product_name_en/quantity/
              unit_price/vat_amount/line_total) — ignored if with_items=False
    """
    accent = colors.HexColor(ACCENTS.get(doc_type, "#3A1FD6"))
    title = TITLES.get(doc_type, doc_type.replace("_", " ").upper())
    W, H = A4
    c = canvas.Canvas(out_path, pagesize=A4)
    margin = 16 * mm

    # header band
    c.setFillColor(accent)
    c.rect(0, H - 32 * mm, W, 32 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, H - 14 * mm, company.get("company_name_en", "Company"))
    c.setFont("Helvetica", 8)
    c.drawString(margin, H - 20 * mm, f"VAT: {company.get('vat_registration_no', '')}")
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(W - margin, H - 14 * mm, title)
    c.setFont("Helvetica", 9)
    c.drawRightString(W - margin, H - 20 * mm, f"No: {header.get('number', '')}")
    try:
        from config import settings as _cf
        _d = _cf.fmt_date(header.get("date", ""))
    except Exception:
        _d = header.get("date", "")
    c.drawRightString(W - margin, H - 25 * mm, f"Date: {_d}")

    y = H - 40 * mm
    c.setFillColor(colors.HexColor("#888"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, y, party_label.upper())
    y -= 5 * mm
    c.setFillColor(colors.HexColor("#222"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, header.get("party_name", "") or "—")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    if header.get("party_address"):
        c.drawString(margin, y, str(header["party_address"]))
        y -= 4.5 * mm
    if header.get("ref"):
        c.drawString(margin, y, f"Reference: {header['ref']}")
        y -= 4.5 * mm
    for lab, val in header.get("extra") or []:
        if val:
            c.drawString(margin, y, f"{lab}: {val}")
            y -= 4.5 * mm
    y -= 6 * mm

    if with_items:
        cols = [("#", margin, "l"), ("Description", margin + 12 * mm, "l"),
                ("Qty", W - 78 * mm, "r"), ("Rate", W - 58 * mm, "r"),
                ("VAT", W - 38 * mm, "r"), ("Total", W - margin, "r")]
        page = {"n": 1}

        def table_header(yy):
            c.setFillColor(accent)
            c.rect(margin, yy - 7 * mm, W - 2 * margin, 7 * mm, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 8)
            for name, x, al in cols:
                (c.drawRightString if al == "r" else c.drawString)(x, yy - 5 * mm, name)
            return yy - 7 * mm

        def page_foot():
            c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#999"))
            c.drawString(margin, 12 * mm, f"{title}  {header.get('number', '')}")
            c.drawRightString(W - margin, 12 * mm, "Page %d" % page["n"])

        # notes wrapped once (used to measure and to draw)
        note_lines = []
        if header.get("notes"):
            line = ""
            for w_ in str(header["notes"]).split():
                if len(line) + len(w_) > 95:
                    note_lines.append(line); line = ""
                line = (line + " " + w_).strip()
            if line:
                note_lines.append(line)
            note_lines = note_lines[:6]
        tot_rows = [(lb, v, bd) for lb, v, bd in (
            ("Subtotal", header.get("subtotal"), False), ("VAT", header.get("vat"), False),
            ("TOTAL", header.get("total"), True)) if not (v in (None, "") and lb != "TOTAL")]
        tot_h = sum(8 * mm if bd else 6 * mm for _l, _v, bd in tot_rows)
        notes_h = (11 * mm + (len(note_lines) - 1) * 4.5 * mm + 2 * mm) if note_lines else 0
        block_h = tot_h + notes_h
        SIG_TOP = 48 * mm                 # signature lines are at 40 mm
        SUMM_H = 4 * mm

        y = table_header(y)
        c.setFont("Helvetica", 9)
        n = len(lines or [])
        for i, ln in enumerate(lines or [], 1):
            rh = 7 * mm
            if i % 2 == 0:
                c.setFillColor(colors.HexColor("#F5F5FA"))
                c.rect(margin, y - rh, W - 2 * margin, rh, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#222")); c.setFont("Helvetica", 9)
            c.drawString(cols[0][1], y - 5 * mm, str(i))
            name = ln.get("product_name_en", "") or ln.get("description", "")
            unit = ln.get("unit_of_measure_en") or ""
            if unit:
                name = f"{name}  ({unit})"
            c.drawString(cols[1][1], y - 5 * mm, str(name)[:52])
            c.drawRightString(cols[2][1], y - 5 * mm, f"{float(ln.get('quantity', 0)):g}")
            c.drawRightString(cols[3][1], y - 5 * mm, money(ln.get("unit_price", 0)))
            c.drawRightString(cols[4][1], y - 5 * mm, money(ln.get("vat_amount", 0)))
            c.drawRightString(cols[5][1], y - 5 * mm, money(ln.get("line_total", 0)))
            y -= rh
            left = n - i
            if left:
                fits_all = y - left * rh - SUMM_H - block_h >= SIG_TOP
                if not fits_all and (y - rh < 20 * mm or
                                     (left <= 3 and y - left * rh - SUMM_H - block_h < SIG_TOP)):
                    page_foot(); c.showPage(); page["n"] += 1
                    y = table_header(H - margin)
        if y - SUMM_H - block_h < SIG_TOP:          # totals don't fit: own page
            page_foot(); c.showPage(); page["n"] += 1
            y = table_header(H - margin)
        if page["n"] > 1:
            page_foot()

        # totals + notes: anchored just above the signature lines
        top = SIG_TOP + block_h
        c.setStrokeColor(colors.HexColor("#DDDDDD")); c.setLineWidth(0.4)
        c.line(margin, top + 3 * mm, W - margin, top + 3 * mm)
        ty = top
        bx = W - margin - 70 * mm
        for label, val, bold in tot_rows:
            if bold:
                c.setFillColor(accent)
                c.rect(bx, ty - 8 * mm, 70 * mm, 8 * mm, fill=1, stroke=0)
                c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12)
                c.drawString(bx + 3 * mm, ty - 6 * mm, label)
                c.drawRightString(W - margin - 3 * mm, ty - 6 * mm, money(val))
                ty -= 8 * mm
            else:
                c.setFillColor(colors.HexColor("#444")); c.setFont("Helvetica", 10)
                c.drawString(bx + 3 * mm, ty - 5 * mm, label)
                c.drawRightString(W - margin - 3 * mm, ty - 5 * mm, money(val))
                ty -= 6 * mm
        if note_lines:
            c.setFillColor(colors.HexColor("#444")); c.setFont("Helvetica-Bold", 8)
            c.drawString(margin, ty - 6 * mm, "Notes / Terms")
            c.setFont("Helvetica", 9)
            ny = ty - 11 * mm
            for ln_ in note_lines:
                c.drawString(margin, ny, ln_); ny -= 4.5 * mm
    else:
        # voucher: single amount + narration
        c.setFillColor(accent)
        c.rect(margin, y - 16 * mm, W - 2 * margin, 16 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 9)
        c.drawString(margin + 6 * mm, y - 6 * mm, "Amount")
        c.setFont("Helvetica-Bold", 18)
        c.drawRightString(W - margin - 6 * mm, y - 11 * mm,
                          f"{money(header.get('amount', 0))} "
                          f"{header.get('currency') or _cur()}")
        y -= 22 * mm
        try:
            from modules.print_prefs import amount_in_words
            words = amount_in_words(header.get("amount", 0))
        except Exception:
            words = ""
        if words:
            c.setFillColor(colors.HexColor("#444")); c.setFont("Helvetica-Oblique", 9)
            c.drawString(margin, y, "In words: " + words[:120])
            y -= 8 * mm
        if header.get("narration"):
            c.setFillColor(colors.HexColor("#444")); c.setFont("Helvetica", 9)
            c.drawString(margin, y, "Narration:")
            y -= 5 * mm
            c.setFont("Helvetica", 10)
            c.drawString(margin, y, str(header["narration"])[:110])
            y -= 8 * mm
        if header.get("payment"):
            c.setFillColor(colors.HexColor("#444")); c.setFont("Helvetica", 9)
            c.drawString(margin, y, f"Paid via: {header['payment']}")
            y -= 6 * mm

    # signature lines
    sig_y = 40 * mm
    c.setStrokeColor(colors.HexColor("#CCCCCC")); c.setLineWidth(0.6)
    c.line(margin, sig_y, margin + 55 * mm, sig_y)
    c.line(W - margin - 55 * mm, sig_y, W - margin, sig_y)
    c.setFont("Helvetica", 8); c.setFillColor(colors.HexColor("#888"))
    c.drawString(margin, sig_y - 4 * mm, "Prepared by")
    c.drawString(W - margin - 55 * mm, sig_y - 4 * mm, "Approved by")

    if header.get("qr"):                 # ZATCA QR (credit notes, Phase 2)
        try:
            import io, qrcode
            from reportlab.lib.utils import ImageReader
            img = qrcode.make(str(header["qr"]))
            buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
            size = 26 * mm
            c.drawImage(ImageReader(buf), W / 2 - size / 2, 15 * mm, size, size)
        except Exception:
            pass
    c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#999"))
    c.drawCentredString(W / 2, 12 * mm, "Generated by DayBill ERP")
    c.showPage()
    c.save()
    return out_path
