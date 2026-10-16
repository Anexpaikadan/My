# ============================================================
# DayBill ERP - print engine self-test   (DayBillERP.exe --selftest)
# ------------------------------------------------------------
# Renders a sample bill through every print path WITHOUT a database:
# your designer template (A4 + 80 mm), QR, barcodes, Arabic, the
# built-in A4 invoice and the 80 mm receipt. BUILD_EXE.bat runs it on
# the new exe, so a missing library shows up at build time, not at
# the shop counter. Result: logs\selftest.log  (exit code 0 = all OK)
# ============================================================
import os
import sys
import traceback
from datetime import datetime


def _sample():
    company = {"company_name_en": "DayBill Test Shop", "company_name_ar": "متجر ديبل",
               "vat_registration_no": "310123456700003", "cr_number": "1010101010",
               "address_en": "Riyadh", "phone": "0500000000"}
    inv = {"invoice_id": 1, "invoice_number": "INV-SELFTEST", "invoice_date": datetime.now(),
           "invoice_time": datetime.now().strftime("%H:%M:%S"),
           "customer_name_en": "Cash Customer", "customer_name_ar": "عميل نقدي",
           "subtotal_amount": 100.0, "discount_amount": 0.0, "taxable_amount": 100.0,
           "vat_amount": 15.0, "total_amount": 115.0, "paid_amount": 115.0,
           "payment_method": "cash", "qr_code_data": "AQ5EYXlCaWxsIFRlc3QgU2hvcA==",
           "notes_en": "Self test"}
    lines = [{"line_number": 1, "product_code": "P1", "barcode": "6281234567890",
              "product_name_en": "Milk 1L", "product_name_ar": "حليب ١ لتر",
              "quantity": 2, "unit_of_measure_en": "PCs", "unit_price": 50.0,
              "discount_amount": 0, "line_amount": 100.0, "vat_rate": 15,
              "vat_amount": 15.0, "line_total": 115.0}]
    return company, inv, lines


def run(out_dir=None):
    """Returns (ok, report_text)."""
    if out_dir is None:
        try:
            from config.paths import LOG_DIR
            out_dir = LOG_DIR
        except Exception:
            out_dir = os.path.abspath("logs")
    os.makedirs(out_dir, exist_ok=True)
    company, inv, lines = _sample()
    rows, ok_all = [], True

    def step(name, fn):
        nonlocal ok_all
        try:
            fn()
            rows.append("OK    " + name)
        except Exception as e:
            ok_all = False
            rows.append("FAIL  %s : %s" % (name, str(e)[:300]))
            rows.append("      " + traceback.format_exc().strip().splitlines()[-1][:300])

    def barcodes():
        from reportlab.graphics.barcode import createBarcodeDrawing, getCodeNames
        names = getCodeNames()          # loads every barcode type ReportLab has
        for code, val in (("QR", "DayBill"), ("Code128", "P1-123"), ("EAN13", "628123456789")):
            if code in names:
                createBarcodeDrawing(code, value=val)
        from reportlab.graphics.barcode import qr, code128, eanbc   # noqa: F401

    def designer(paper):
        from modules import report_designer as rd
        from modules.template_renderer import render_template
        els = rd.starter_layout("pos_invoice" if paper != "A4" else "sales_invoice", paper)
        nid = max([e.get("id", 0) for e in els] + [0]) + 1
        els.append({"id": nid, "key": "barcode", "label": "Barcode", "type": "barcode",
                    "x": 10, "y": 5, "w": 120, "h": 30, "font": 8})
        tpl = {"template_name": "Self test", "paper_size": paper, "orientation": "portrait",
               "header_text": "SIMPLIFIED TAX INVOICE"}
        path = os.path.join(out_dir, "selftest_designer_%s.pdf" % paper)
        render_template(tpl, els, inv, company, lines, path)
        if os.path.getsize(path) < 800:
            raise RuntimeError("empty PDF")

    def builtin_a4():
        from modules.pdf_invoice import generate_invoice_pdf
        path = os.path.join(out_dir, "selftest_a4.pdf")
        generate_invoice_pdf(inv, company, lines, path, qr_base64=inv["qr_code_data"])

    def thermal():
        from modules.thermal_receipt import generate_thermal_receipt
        path = os.path.join(out_dir, "selftest_80mm.pdf")
        generate_thermal_receipt(inv, company, lines, path, qr_data=inv["qr_code_data"])

    def arabic():
        import arabic_reshaper
        from bidi.algorithm import get_display
        get_display(arabic_reshaper.reshape("فاتورة ضريبية"))

    def libs():
        import pyodbc, openpyxl, qrcode, PIL  # noqa: F401
        import openpyxl as ox
        ox.Workbook().save(os.path.join(out_dir, "selftest.xlsx"))

    def win_print():
        if sys.platform != "win32":
            return
        import win32print, win32api  # noqa: F401
        import pypdfium2  # noqa: F401

    def zatca_phase2():
        """Key + self-made test certificate → sign a simplified invoice and
        check the hash / QR tags (needs lxml + cryptography in the exe)."""
        import base64, datetime as _dt
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from modules.zatca import phase2 as P
        key = ec.generate_private_key(ec.SECP256K1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "DayBill self test")])
        now = _dt.datetime.now(_dt.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(1)
                .not_valid_before(now).not_valid_after(now + _dt.timedelta(days=1))
                .sign(key, hashes.SHA256()))
        cert_b64 = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
        key_pem = key.private_bytes(serialization.Encoding.PEM,
                                    serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()).decode()
        doc = {"number": "SELFTEST-1", "uuid": P.new_uuid(), "issue_date": "2026-01-01",
               "issue_time": "10:00:00", "type_code": P.TYPE_INVOICE, "subtype": P.SUB_SIMPLIFIED,
               "icv": 1, "pih": P.GENESIS_PIH,
               "seller": {"name": "Test", "vat": "399999999900003", "crn": "1010010000",
                          "street": "Street", "building": "1234", "district": "District",
                          "city": "Riyadh", "postal": "12222"},
               "lines": [{"name": "Item", "qty": 1, "net_amount": 10, "vat_code": "S",
                          "vat_rate": 15}], "total": 11.5}
        signed = P.sign_xml(P.build_xml(doc), cert_b64, key_pem)
        assert P.invoice_hash(signed["xml"]) == signed["hash"], "hash changed after signing"
        b = base64.b64decode(signed["qr"])
        assert b[0] == 1 and len(b) > 200, "Phase 2 QR too short"
        with open(os.path.join(out_dir, "selftest_zatca_signed.xml"), "w", encoding="utf-8") as f:
            f.write(signed["xml"])

    step("Libraries (pyodbc, Excel, QR, images)", libs)
    step("Barcodes + QR (ReportLab)", barcodes)
    step("Arabic text", arabic)
    step("Designer template A4", lambda: designer("A4"))
    step("Designer template 80 mm", lambda: designer("80mm"))
    step("Built-in A4 invoice", builtin_a4)
    step("Built-in 80 mm receipt", thermal)
    step("Windows printing (pywin32, pypdfium2)", win_print)
    step("ZATCA Phase 2 (XML, hash, signature, QR)", zatca_phase2)

    def labels():
        # every ready label design renders (python-barcode + Pillow in the exe)
        from modules import barcode_designer as bd
        import json as _json
        item = {"product_name_en": "Self test 1L", "product_name_ar": "اختبار", "unit_name": "Box",
                "unit_price": 10, "price_vat": 11.5, "offer_text": "HALF PRICE", "offer_price": 5.75,
                "old_price": 11.5, "barcode_value": "6281000000014", "copies": 2}
        for name, w, h, sheet, els in bd.READY_DESIGNS:
            tpl = {"template_name": name, "barcode_type": "code128", "label_width_mm": w,
                   "label_height_mm": h, "paper_mode": "a4sheet" if sheet else "thermal",
                   "cols_per_sheet": 3, "rows_per_sheet": 8, "margin_mm": 5,
                   "layout_json": _json.dumps(els)}
            path = os.path.join(out_dir, "selftest_label_%dx%d.pdf" % (w, h))
            bd.render_labels_pdf(tpl, [item], path)
            if os.path.getsize(path) < 800:
                raise RuntimeError("empty label PDF: " + name)
    step("Barcode labels (every ready design)", labels)

    def columns_tool():
        # v6.2: every table gets the columns tool; the VAT registers are there
        from tkinter import ttk
        from ui import table_columns as tc
        if ttk.Treeview.__init__ is not tc._init or not tc._O:
            raise RuntimeError("columns tool not installed on tables")
        from modules import report_center as rc
        need = {"output_vat", "input_vat", "sales_register", "sales_returns", "purchase_register",
                "purchase_returns", "vat_return", "stock", "sales_lines", "purchase_lines"}
        miss = need - set(rc.REGISTRY)
        if miss:
            raise RuntimeError("reports missing: " + ", ".join(sorted(miss)))
    step("Columns tool + VAT registers", columns_tool)

    def ai_inventory():
        # v6.3: the AI inventory engine and Ask AI load in this build
        from modules import inventory_ai as ia, inventory_chat as ic
        for fn in ("health", "forecast", "reorder_plan", "abc", "expiry", "transfers",
                   "bought_together", "supplier_prices", "data_check", "price_check"):
            if not callable(getattr(ia, fn, None)):
                raise RuntimeError("inventory engine incomplete: " + fn)
        if len(ic.TOOLS) < 10:
            raise RuntimeError("Ask AI tools missing")
    step("AI inventory engine + Ask AI", ai_inventory)

    def ops_v640():
        from modules import (supplier_orders as so, cycle_count as cc, price_update as pu,
                             cashier_watch as cw, owner_report as orp, cloud_backup as cb, daily_jobs as dj)
        for mod, fns in ((so, ("create_from_plan", "Receiving")), (cc, ("plan", "approve", "pending")),
                         (pu, ("suggestions", "apply")), (cw, ("report", "log_void")),
                         (orp, ("build", "send")), (cb, ("run", "folders")), (dj, ("tick", "start"))):
            for fn in fns:
                if not hasattr(mod, fn):
                    raise RuntimeError("%s.%s missing" % (mod.__name__, fn))
        if pu.nice(12.9375, 0.25) != 13.0 or dj.hhmm("2130", "") != "21:30":
            raise RuntimeError("price rounding / job time wrong")
        import ui.stock_count, ui.price_updates, ui.po_receive  # noqa: F401  (screens load)
    step("Supplier orders, stock count, price updates, cashier watch, evening jobs", ops_v640)

    def upd_v650():
        from modules.zatca import readiness as zr
        from modules import whatsapp as wa, owner_report as orp, ai_client as aic
        code, hint = zr.fix_hint("BR-KSA-37: The seller address building number must contain 4 digits.")
        if code != "BR-KSA-37" or "4 digits" not in hint:
            raise RuntimeError("ZATCA how-to-fix wrong")
        if zr.WAVE["deadline"].isoformat() != "2027-02-01" or zr.WAVE["threshold"] != 187500:
            raise RuntimeError("ZATCA 25th wave wrong")
        p = orp.template_params({"date_text": "Mon 12 Oct", "sales": 10, "summary": "a\nb", "lang": "en"})
        if len(p) != 3 or any("\n" in x for x in p):
            raise RuntimeError("evening report template values wrong")
        if not hasattr(wa, "usage") or aic.MODEL_FAST != "claude-haiku-5-5":
            raise RuntimeError("WhatsApp count / AI model missing")
    step("ZATCA readiness, evening report template, WhatsApp count", upd_v650)

    def hr_v660():
        from modules import payroll_engine as pe, hr_time as ht, payroll as pr
        e = {"basic_salary": 6000, "housing_allowance": 1500, "transport_allowance": 500, "other_allowance": 0}
        if abs(pe.overtime_rate(e) - 45.8333) > 0.001:
            raise RuntimeError("overtime rate wrong (art. 107)")
        if pe.calc_eos_gratuity(3, 6000, "resignation")["gratuity_amount"] != 3000.0:
            raise RuntimeError("end-of-service resignation share wrong (art. 85)")
        if not ht.is_ramadan("2027-02-08") or ht.is_ramadan("2027-03-09"):
            raise RuntimeError("Ramadan dates wrong")
        if ht.probation_days({"probation_days": 400}) != 180:
            raise RuntimeError("probation limit wrong")
        for fn in ("settlement", "compensation_77", "service_years", "write_wps"):
            if not hasattr(pr, fn):
                raise RuntimeError("payroll.%s missing" % fn)
    step("HR & payroll by the Labour Law (overtime, EOS, Ramadan, probation)", hr_v660)

    def ui_v670():
        from ui import compact as cp
        for fn in ("doc_form", "one_row", "strip", "tighten", "edges", "page_shadow", "strong_border"):
            if not hasattr(cp, fn):
                raise RuntimeError("compact.%s missing" % fn)
        if not str(cp.strong_border()).startswith("#"):
            raise RuntimeError("edge colour wrong")
    step("Compact headers + window edges", ui_v670)

    def forms_v680():
        from ui import form_style as fs
        from modules import online_forms as of
        if fs.check_vat("300000000000003") or not fs.check_vat("12"):
            raise RuntimeError("VAT check wrong")
        if fs.check_phone("0551234567") or not fs.check_phone("05"):
            raise RuntimeError("mobile check wrong")
        if of.parse_form_id("https://tally.so/r/abc123") != "abc123":
            raise RuntimeError("Tally link not read")
        v = of.map_answers("customer", {"Name (English) · x": "A", "Mobile · y": "+966551234567",
                                        "Customer type": "Company · شركة"})
        if v.get("customer_name_en") != "A" or v.get("phone") != "0551234567" or v.get("customer_type") != "B2B":
            raise RuntimeError("online form answers not mapped: %s" % v)
    step("Tally-style boxes + online forms", forms_v680)

    text = "DayBill ERP self-test  %s\n%s\n\n%s\n" % (
        datetime.now().strftime("%Y-%m-%d %H:%M"), "-" * 40, "\n".join(rows))
    text += "\nRESULT: %s\n" % ("ALL OK" if ok_all else "PROBLEMS FOUND")
    try:
        with open(os.path.join(out_dir, "selftest.log"), "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    return ok_all, text
