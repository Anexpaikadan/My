# ============================================================
# DayBill ERP - Bilingual Payslip PDF Generator
# Reuses Arabic shaping + font registration from pdf_invoice
# ============================================================

import os


def generate_payslip_pdf(payslip: dict, run: dict, company: dict, output_path: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    # Reuse the invoice module's Arabic helpers
    from modules.pdf_invoice import _shape_arabic, _register_fonts, _AR_FONT, _AR_FONT_BOLD
    _register_fonts()
    # re-import the (possibly updated) font names after registration
    from modules import pdf_invoice as _pi
    AR = _pi._AR_FONT
    ARB = _pi._AR_FONT_BOLD

    W, H = A4
    c = canvas.Canvas(output_path, pagesize=A4)
    GREEN = colors.HexColor("#006C35")
    DARK = colors.HexColor("#1A1A2E")
    GREY = colors.HexColor("#6B7280")
    LIGHT = colors.HexColor("#E8F5EE")
    BORDER = colors.HexColor("#D1D5DB")
    margin = 18 * mm

    def en(x, y, s, font="Helvetica", size=9, color=DARK):
        c.setFont(font, size); c.setFillColor(color); c.drawString(x, y, str(s))

    def en_r(x, y, s, font="Helvetica", size=9, color=DARK):
        c.setFont(font, size); c.setFillColor(color); c.drawRightString(x, y, str(s))

    def ar_r(x, y, s, size=9, color=DARK, bold=False):
        c.setFont(ARB if bold else AR, size); c.setFillColor(color)
        c.drawRightString(x, y, _shape_arabic(s))

    # Header
    c.setFillColor(GREEN); c.rect(0, H - 32 * mm, W, 32 * mm, fill=1, stroke=0)
    en(margin, H - 15 * mm, company.get("company_name_en", "Company"),
       "Helvetica-Bold", 15, colors.white)
    en(margin, H - 22 * mm, f"VAT: {company.get('vat_registration_no', '')}",
       "Helvetica", 9, LIGHT)
    ar_r(W - margin, H - 15 * mm, company.get("company_name_ar", ""), 14, colors.white, bold=True)

    # Title band
    y = H - 42 * mm
    c.setFillColor(LIGHT); c.rect(margin, y - 9 * mm, W - 2 * margin, 9 * mm, fill=1, stroke=0)
    en(margin + 4 * mm, y - 6.2 * mm, f"PAYSLIP — {run.get('run_label', '')}",
       "Helvetica-Bold", 12, GREEN)
    ar_r(W - margin - 4 * mm, y - 6.2 * mm, "قسيمة الراتب", 12, GREEN, bold=True)
    y -= 16 * mm

    # Employee box
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.rect(margin, y - 22 * mm, W - 2 * margin, 22 * mm, fill=0, stroke=1)
    en(margin + 4 * mm, y - 6 * mm, "Employee / الموظف", "Helvetica-Bold", 9, GREEN)
    en(margin + 4 * mm, y - 12 * mm, payslip.get("employee_name_en", ""),
       "Helvetica-Bold", 11, DARK)
    if payslip.get("employee_name_ar"):
        ar_r(W - margin - 4 * mm, y - 12 * mm, payslip.get("employee_name_ar", ""), 11, DARK, bold=True)
    en(margin + 4 * mm, y - 18 * mm, f"Period: {run.get('run_label', '')}", "Helvetica", 9, GREY)
    if payslip.get("iban"):
        en_r(W - margin - 4 * mm, y - 18 * mm, f"IBAN: {payslip['iban']}", "Helvetica", 8, GREY)
    y -= 30 * mm

    # Two columns: Earnings | Deductions
    col_w = (W - 2 * margin - 6 * mm) / 2
    box_h = 60 * mm

    # Earnings
    ex = margin
    c.setFillColor(GREEN); c.rect(ex, y - 8 * mm, col_w, 8 * mm, fill=1, stroke=0)
    en(ex + 4 * mm, y - 5.5 * mm, "EARNINGS", "Helvetica-Bold", 10, colors.white)
    ar_r(ex + col_w - 4 * mm, y - 5.5 * mm, "المستحقات", 10, colors.white, bold=True)
    c.setStrokeColor(BORDER); c.rect(ex, y - box_h, col_w, box_h - 8 * mm, fill=0, stroke=1)

    earnings = [
        ("Basic Salary", "الراتب الأساسي", payslip.get("basic_salary", 0)),
        ("Housing", "بدل السكن", payslip.get("housing_allowance", 0)),
        ("Transport", "بدل النقل", payslip.get("transport_allowance", 0)),
        ("Other Allowance", "بدلات أخرى", payslip.get("other_allowance", 0)),
        ("Overtime" + (" (%g h)" % float(payslip.get("overtime_hours") or 0)
                       if float(payslip.get("overtime_hours") or 0) else ""),
         "العمل الإضافي", payslip.get("overtime_amount", 0)),
    ]
    if float(payslip.get("bonus_amount") or 0):                     # v6.6
        earnings.append(("Bonus / Commission", "مكافأة / عمولة", payslip.get("bonus_amount", 0)))
    ey = y - 14 * mm
    for lbl_en, lbl_ar, val in earnings:
        en(ex + 4 * mm, ey, lbl_en, "Helvetica", 9, DARK)
        en_r(ex + col_w - 4 * mm, ey, f"{float(val):,.2f}", "Helvetica", 9, DARK)
        ey -= 7 * mm
    # gross
    c.setFillColor(LIGHT); c.rect(ex, ey - 2 * mm, col_w, 8 * mm, fill=1, stroke=0)
    en(ex + 4 * mm, ey + 0.5 * mm, "Gross Salary", "Helvetica-Bold", 9, GREEN)
    en_r(ex + col_w - 4 * mm, ey + 0.5 * mm, f"{float(payslip.get('gross_salary', 0)):,.2f}",
         "Helvetica-Bold", 9, GREEN)

    # Deductions
    dx = margin + col_w + 6 * mm
    c.setFillColor(colors.HexColor("#DC2626")); c.rect(dx, y - 8 * mm, col_w, 8 * mm, fill=1, stroke=0)
    en(dx + 4 * mm, y - 5.5 * mm, "DEDUCTIONS", "Helvetica-Bold", 10, colors.white)
    ar_r(dx + col_w - 4 * mm, y - 5.5 * mm, "الاستقطاعات", 10, colors.white, bold=True)
    c.setStrokeColor(BORDER); c.rect(dx, y - box_h, col_w, box_h - 8 * mm, fill=0, stroke=1)

    deductions = [
        ("GOSI (Employee)", "التأمينات", payslip.get("gosi_employee", 0)),
        ("Loan / Advance", "سلفة", payslip.get("loan_deduction", 0)),
    ]
    if float(payslip.get("absence_deduction") or 0):               # v6.6
        deductions.append(("Absent / unpaid days (%g)" % float(payslip.get("absence_days") or 0),
                           "أيام غياب / بدون راتب", payslip.get("absence_deduction", 0)))
    if float(payslip.get("sick_deduction") or 0):
        deductions.append(("Sick leave not paid (art. 117)", "إجازة مرضية غير مدفوعة",
                           payslip.get("sick_deduction", 0)))
    deductions.append(("Other Deduction", "استقطاعات أخرى", payslip.get("other_deduction", 0)))
    dy = y - 14 * mm
    for lbl_en, lbl_ar, val in deductions:
        en(dx + 4 * mm, dy, lbl_en, "Helvetica", 9, DARK)
        en_r(dx + col_w - 4 * mm, dy, f"{float(val):,.2f}", "Helvetica", 9, DARK)
        dy -= 7 * mm
    c.setFillColor(colors.HexColor("#FEF2F2")); c.rect(dx, dy + 13 * mm, col_w, 8 * mm, fill=1, stroke=0)
    en(dx + 4 * mm, dy + 15.5 * mm, "Total Deductions", "Helvetica-Bold", 9,
       colors.HexColor("#DC2626"))
    en_r(dx + col_w - 4 * mm, dy + 15.5 * mm, f"{float(payslip.get('total_deductions', 0)):,.2f}",
         "Helvetica-Bold", 9, colors.HexColor("#DC2626"))

    y -= box_h + 6 * mm

    # Net pay band
    c.setFillColor(GREEN); c.rect(margin, y - 14 * mm, W - 2 * margin, 14 * mm, fill=1, stroke=0)
    en(margin + 6 * mm, y - 9 * mm, "NET SALARY", "Helvetica-Bold", 14, colors.white)
    ar_r(W / 2 + 10 * mm, y - 9 * mm, "صافي الراتب", 13, colors.white, bold=True)
    en_r(W - margin - 6 * mm, y - 9 * mm, f"{float(payslip.get('net_salary', 0)):,.2f} SAR",
         "Helvetica-Bold", 16, colors.white)

    # Footer
    c.setFillColor(GREY); c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 14 * mm,
                        "Employer GOSI contribution: "
                        f"{float(payslip.get('gosi_employer', 0)):,.2f} SAR (not deducted from employee)")
    c.setFont(AR, 7)
    c.drawCentredString(W / 2, 10 * mm, _shape_arabic("هذه قسيمة راتب صادرة آلياً"))

    c.showPage(); c.save()
    return output_path
