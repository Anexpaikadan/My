# ============================================================
# DayBill ERP - Report export helper (Excel + printable PDF)
# Used by every report screen for consistent Export / Print.
# ------------------------------------------------------------
# v5.26:
#   Excel — amounts are real numbers (you can SUM them), right aligned,
#           columns sized to their contents, company name on top,
#           TOTAL rows bold, header frozen + filter, landscape when wide.
#   PDF   — fits the page (landscape for wide tables, column widths from
#           the contents, long text wraps), Arabic prints correctly,
#           numbers right aligned, TOTAL rows bold, page numbers.
#   path= — save straight to a file (no Save-As box, no message).
# ============================================================

import os
import re
from datetime import datetime


def _summary_pairs(summary):
    """Summary lines as (label, value) pairs. Screens pass either pairs
    or a plain line like "Opening 0.00 · Dr/Cr 715.00 / 0.00 · Closing
    486.00 Dr" — both work (a plain line used to crash the export with
    "not enough values to unpack")."""
    if not summary:
        return []
    items = [summary] if isinstance(summary, str) else list(summary)
    out = []
    for it in items:
        if isinstance(it, str):
            for part in [p.strip() for p in it.replace("\n", "·").split("·") if p.strip()]:
                head, _sp, rest = part.partition(" ")
                if rest and (rest.lstrip()[:1].isdigit() or rest.lstrip()[:1] in "-+"):
                    out.append((head, rest.strip()))
                else:
                    out.append((part, ""))
        elif isinstance(it, (list, tuple)):
            if len(it) >= 2:
                out.append((it[0], it[1]))
            elif len(it) == 1:
                out.append((it[0], ""))
        elif it is not None:
            out.append((str(it), ""))
    return out


# ── numbers ───────────────────────────────────────────────────
_DEC = re.compile(r"^\(?[-+]?(\d{1,3}(,\d{3})+|\d+)?\.\d+\)?(\s?(dr|cr|sar))?$", re.I)
_GROUPED = re.compile(r"^\(?[-+]?\d{1,3}(,\d{3})+\)?(\s?(dr|cr|sar))?$", re.I)
_INT = re.compile(r"^[-+]?\d+$")
# columns whose whole numbers are quantities / counts (not codes or phone numbers)
_COUNT_HEAD = re.compile(r"qty|quantity|count|items|stock|units?\b|days|bills|invoices|"
                         r"vouchers|pcs|age|كمية", re.I)
_TEXT_HEAD = re.compile(r"code|no\.?$|number|#|phone|mobile|ref|barcode|vat no|iban|cr\b|"
                        r"date|time|year", re.I)
_TOTAL_ROW = re.compile(r"^\W*(grand\s+)?total|^\W*closing|^\W*net\b|الإجمالي", re.I)


def _to_number(s):
    """'1,234.50' → 1234.5, '(12.00)' → -12, '45.00 Dr' → 45, else None."""
    if isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip()
    if not t:
        return None
    low = t.lower()
    if re.search(r"\d\s?(dr|cr)$", low):
        return None                     # "45.00 Cr" keeps its Dr / Cr text
    neg = t.startswith("(") and t.endswith(")")
    core = re.sub(r"\s?sar$", "", low).strip("()").replace(",", "")
    try:
        v = float(core)
    except ValueError:
        return None
    return -v if neg else v


def _numeric_columns(headers, rows):
    """Which columns hold numbers (amounts, quantities)."""
    out = []
    for ci, h in enumerate(headers):
        vals = [str(r[ci]).strip() for r in rows if ci < len(r) and r[ci] is not None
                and str(r[ci]).strip() not in ("", "—", "-")]
        if not vals:
            out.append(False)
            continue
        if _TEXT_HEAD.search(str(h)) and not _COUNT_HEAD.search(str(h)):
            out.append(False)
            continue
        dec = sum(1 for v in vals if _DEC.match(v) or _GROUPED.match(v))
        ints = sum(1 for v in vals if _INT.match(v) and not (len(v) > 1 and v.lstrip("+-")[:1] == "0"))
        if dec and (dec + ints) >= 0.8 * len(vals):
            out.append(True)
        elif ints >= 0.8 * len(vals) and _COUNT_HEAD.search(str(h)):
            out.append(True)
        else:
            out.append(False)
    return out


def _is_total(row):
    for v in row[:3]:
        if v not in (None, "") and _TOTAL_ROW.search(str(v)):
            return True
    return False


def _company():
    try:
        from config.database import db
        return (db.fetchone("SELECT * FROM company WHERE company_id=1")
                or db.fetchone("SELECT TOP 1 * FROM company") or {})
    except Exception:
        return {}


def _ask_path(name, ext, path):
    if path:
        return path
    from tkinter import filedialog
    kinds = {".xlsx": [("Excel", "*.xlsx")], ".pdf": [("PDF", "*.pdf")]}
    return filedialog.asksaveasfilename(defaultextension=ext, filetypes=kinds[ext],
                                        initialfile=f"{_safe(name)}{ext}")


def _safe(name):
    return re.sub(r'[\\/:*?"<>|]+', "_", str(name or "Report")).strip() or "Report"


def _done(path, quiet, title, msg):
    if quiet:
        return path
    try:
        from tkinter import messagebox
        messagebox.showinfo(title, msg)
    except Exception:
        pass
    try:
        os.startfile(path)            # opens in Excel / the PDF viewer
    except Exception:
        pass
    return path


def _screen_columns(parent, headers, rows, aligns=None):
    """v6.2 columns tool: rows read from a table on screen whose columns the
    user hid or moved → the file has the same columns, in the same order."""
    try:
        from ui.table_columns import find_table, export_view
        t = find_table(parent, headers, rows)
        if t is not None:
            return export_view(t, list(headers), rows, aligns)
    except Exception:
        pass
    return headers, rows, aligns


def export_excel(parent, name, headers, data_rows, title=None, summary=None,
                 path=None, company=None):
    """
    Write a styled .xlsx. data_rows = list of lists (already formatted —
    amounts are turned back into numbers). summary = optional
    (label, value) pairs shown at the top. Returns saved path or None.
    """
    headers, data_rows, _a = _screen_columns(parent, headers, data_rows)
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        if not path:
            from tkinter import messagebox
            messagebox.showerror("Missing Library", "pip install openpyxl")
        return None
    quiet = bool(path)
    path = _ask_path(name, ".xlsx", path)
    if not path:
        return None
    headers = [str(h) for h in headers]
    rows = [list(r) for r in (data_rows or [])]
    numeric = _numeric_columns(headers, rows)
    company = company if company is not None else _company()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = re.sub(r"[\[\]:*?/\\]", "-", str(name))[:31] or "Report"
    r = 1
    ws.cell(r, 1, (company or {}).get("company_name_en") or "DayBill ERP").font = \
        Font(bold=True, size=14, color="1F2A44")
    r += 1
    if title:
        ws.cell(r, 1, str(title)).font = Font(bold=True, size=12)
        r += 1
    ws.cell(r, 1, "Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M")).font = \
        Font(size=9, color="6B7280")
    r += 2
    pairs = _summary_pairs(summary)
    for label, value in pairs:
        ws.cell(r, 1, str(label)).font = Font(bold=True)
        v = _to_number(value) if isinstance(value, str) and (_DEC.match(value.strip())
                                                             or _GROUPED.match(value.strip())) else value
        c = ws.cell(r, 2, v if isinstance(v, (int, float)) and not isinstance(v, bool) else str(value))
        if isinstance(v, float):
            c.number_format = '#,##0.00;(#,##0.00)'
        r += 1
    if pairs:
        r += 1
    head_fill = PatternFill("solid", fgColor="1F4E79")
    thin = Side(style="thin", color="D9D9D9")
    head_row = r
    for ci, h in enumerate(headers, 1):
        c = ws.cell(r, ci, h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    r += 1
    widths = [len(h) + 2 for h in headers]
    tot_fill = PatternFill("solid", fgColor="F2F2F2")
    for row in rows:
        total = _is_total(row)
        for ci, val in enumerate(row, 1):
            num = numeric[ci - 1] if ci - 1 < len(numeric) else False
            v = _to_number(val) if num else None
            if num and v is not None:
                c = ws.cell(r, ci, v)
                txt = str(val)
                c.number_format = ('#,##0.00;(#,##0.00)' if ("." in txt or isinstance(val, float))
                                   else '#,##0')
                c.alignment = Alignment(horizontal="right")
            else:
                c = ws.cell(r, ci, "" if val is None else val)
            c.border = Border(bottom=thin)
            if total:
                c.font = Font(bold=True)
                c.fill = tot_fill
            if ci - 1 < len(widths):
                widths[ci - 1] = max(widths[ci - 1], min(60, len(str(val or "")) + 2))
        r += 1
    for ci, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = max(9, min(60, w))
    if rows:
        ws.freeze_panes = ws.cell(head_row + 1, 1)
        ws.auto_filter.ref = f"A{head_row}:{get_column_letter(len(headers))}{r - 1}"
    ws.page_setup.orientation = "landscape" if len(headers) > 7 else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0
    try:
        wb.save(path)
    except Exception as e:
        if not quiet:
            from tkinter import messagebox
            messagebox.showerror("Error", str(e))
        return None
    return _done(path, quiet, "Exported", f"Saved:\n{path}")


def _fonts():
    """(regular, bold, shape) — Arabic-capable when a font is installed."""
    font, font_b = "Helvetica", "Helvetica-Bold"
    shape = None
    try:
        from modules import pdf_invoice as _pi
        _pi._register_fonts()
        if getattr(_pi, "_AR_FONT", None):
            font = _pi._AR_FONT
            font_b = getattr(_pi, "_AR_FONT_BOLD", None) or font
            shape = _pi._shape_arabic
    except Exception:
        pass
    return font, font_b, shape


def _has_arabic(s):
    return any("؀" <= ch <= "ۿ" for ch in str(s))


def export_pdf(parent, name, headers, data_rows, title=None, subtitle=None,
               summary=None, company=None, col_align=None, path=None):
    """
    Build a printable PDF table and open it (so the user can print).
    col_align: optional list of 'left'/'right'/'center' per column
    (numbers are found and right-aligned automatically).
    Returns saved path or None.
    """
    headers, data_rows, col_align = _screen_columns(parent, headers, data_rows, col_align)
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase.pdfmetrics import stringWidth
    except ImportError:
        if not path:
            from tkinter import messagebox
            messagebox.showerror("Missing Library", "pip install reportlab")
        return None
    quiet = bool(path)
    path = _ask_path(name, ".pdf", path)
    if not path:
        return None

    from xml.sax.saxutils import escape
    font, font_b, shape = _fonts()
    headers = [str(h) for h in headers]
    rows = [["" if c is None else str(c) for c in row] for row in (data_rows or [])]
    numeric = _numeric_columns(headers, rows)
    company = company if company is not None else _company()

    def txt(s):
        s = "" if s is None else str(s)
        return shape(s) if (shape and _has_arabic(s)) else s

    # page + column widths from the contents
    n = max(1, len(headers))
    size = 8.5 if n <= 6 else (7.8 if n <= 9 else 7.0)
    natural = []
    for ci, h in enumerate(headers):
        w = stringWidth(h, font_b, size) + 10
        for row in rows[:400]:
            if ci < len(row):
                w = max(w, stringWidth(txt(row[ci]), font, size) + 10)
        natural.append(min(w, 230))
    portrait_w = A4[0] - 20 * mm
    page = A4 if (sum(natural) <= portrait_w * 1.05 and n <= 7) else landscape(A4)
    avail = page[0] - 20 * mm
    tot = sum(natural) or 1
    if tot > avail:                     # shrink wide text columns first
        fixed = sum(w for ci, w in enumerate(natural) if numeric[ci])
        flex = [ci for ci in range(n) if not numeric[ci]]
        room = max(avail - fixed, 40 * len(flex) or 1)
        flex_tot = sum(natural[ci] for ci in flex) or 1
        widths = [natural[ci] if numeric[ci] else natural[ci] * room / flex_tot
                  for ci in range(n)]
        scale = avail / (sum(widths) or 1)
        widths = [w * min(1.0, scale) for w in widths]
    else:
        widths = [w * avail / tot for w in natural]

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName=font_b, fontSize=15,
                        textColor=colors.HexColor("#1F2A44"), alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=font_b, fontSize=12, spaceAfter=2)
    sm = ParagraphStyle("sm", parent=ss["Normal"], fontName=font, fontSize=8,
                        textColor=colors.HexColor("#6B7280"))
    cell = ParagraphStyle("cell", parent=ss["Normal"], fontName=font, fontSize=size,
                          leading=size + 2)
    cell_b = ParagraphStyle("cellb", parent=cell, fontName=font_b)
    cell_r = ParagraphStyle("cellr", parent=cell, alignment=2)
    cell_rb = ParagraphStyle("cellrb", parent=cell_r, fontName=font_b)

    el = [Paragraph(escape(txt((company or {}).get("company_name_en") or "DayBill ERP")), h1)]
    if (company or {}).get("vat_registration_no"):
        el.append(Paragraph("VAT No. " + escape(str(company["vat_registration_no"])), sm))
    if title:
        el.append(Paragraph(escape(txt(title)), h2))
    if subtitle:
        el.append(Paragraph(escape(txt(subtitle)), sm))
    el.append(Paragraph("Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M"), sm))
    el.append(Spacer(1, 6))
    pairs = _summary_pairs(summary)
    if pairs:
        cells = [[txt(l), txt(v)] for l, v in pairs]
        grid = []
        for i in range(0, len(cells), 3):
            row = []
            for c in cells[i:i + 3]:
                row += c
            row += [""] * (6 - len(row))
            grid.append(row)
        st = Table(grid, hAlign="LEFT")
        st.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (1, 0), (1, -1), font_b), ("FONTNAME", (3, 0), (3, -1), font_b),
            ("FONTNAME", (5, 0), (5, -1), font_b),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2A44")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F6FB")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D3E3")),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
        el += [st, Spacer(1, 8)]

    amap = {"left": 0, "right": 2, "center": 1}
    align = []
    for ci in range(n):
        a = (col_align[ci] if col_align and ci < len(col_align) else None)
        align.append(amap.get(a, 2 if numeric[ci] else 0))
    data = [[Paragraph(escape(txt(h)), ParagraphStyle("hd", parent=cell_b,
                                                      textColor=colors.white,
                                                      alignment=align[ci]))
             for ci, h in enumerate(headers)]]
    styles = []
    for ri, row in enumerate(rows, 1):
        total = _is_total(row)
        out = []
        for ci in range(n):
            v = row[ci] if ci < len(row) else ""
            if align[ci] == 2:
                st = cell_rb if total else cell_r
            else:
                st = ParagraphStyle("c%d" % align[ci], parent=cell_b if total else cell,
                                    alignment=align[ci])
            out.append(Paragraph(escape(txt(v)), st))
        data.append(out)
        if total:
            styles.append(("BACKGROUND", (0, ri), (-1, ri), colors.HexColor("#F2F2F2")))
            styles.append(("LINEABOVE", (0, ri), (-1, ri), 0.6, colors.HexColor("#8497B0")))
    tbl = Table(data, colWidths=widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#D9D9D9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")] + styles))
    el.append(tbl)

    doc = SimpleDocTemplate(path, pagesize=page, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=10 * mm, rightMargin=10 * mm, title=str(title or name))

    def _footer(canv, d):
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(colors.HexColor("#6B7280"))
        canv.drawRightString(page[0] - 10 * mm, 8 * mm, f"Page {d.page}")
        canv.drawString(10 * mm, 8 * mm, "DayBill ERP · " + str(title or name)[:90])
        canv.restoreState()
    try:
        doc.build(el, onFirstPage=_footer, onLaterPages=_footer)
    except Exception as e:
        if not quiet:
            from tkinter import messagebox
            messagebox.showerror("Error", str(e))
        return None
    return _done(path, quiet, "PDF Ready", f"Saved:\n{path}\n\nOpening for print…")
