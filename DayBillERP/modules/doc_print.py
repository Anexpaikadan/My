# ============================================================
# DayBill ERP - One print engine for every document
# ------------------------------------------------------------
# Sales invoice, POS bill, sales return, purchase invoice, purchase
# return, quotation, purchase order, receipt and payment all print the
# same three ways:
#
#   1. default    - the document's default layout: the ★ default
#                   template from Report / Invoice Designer when it has
#                   a design, otherwise the built-in layout (A4 or
#                   thermal for sales, as set in Print & Invoice).
#                   Goes to the printer.
#   2. dotmatrix  - fixed-width text for impact printers (80/132 col,
#                   Dot-matrix template in Print & Invoice).
#   3. pdf        - A4 PDF saved in Documents\DayBill PDF and opened
#                   (view / save / e-mail / print from the PDF app).
#
# Printer: Settings ▸ Printing ▸ "Print on the default printer without
# asking" (print_direct). On = straight to the printer; off = a small
# box asks which printer and how many copies.
# ============================================================

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db

OPTIONS = ("default", "dotmatrix", "pdf")

# kind -> how to read it and what to call it
KINDS = {
    "sales": dict(title="TAX INVOICE", label="Sales Invoice", table="sales_invoices",
                  pk="invoice_id", lines="sales_invoice_lines", fk="invoice_id",
                  num="invoice_number", date="invoice_date", party="customer",
                  tpl="sales_invoice", printer="sales_invoice", perm="sales",
                  status="invoice_status"),
    "pos": dict(title="SIMPLIFIED TAX INVOICE", label="POS Bill", table="sales_invoices",
                pk="invoice_id", lines="sales_invoice_lines", fk="invoice_id",
                num="invoice_number", date="invoice_date", party="customer",
                tpl="pos_invoice", printer="pos_invoice", perm="pos",
                status="invoice_status"),
    "sales_return": dict(title="SALES RETURN (CREDIT NOTE)", label="Sales Return",
                         table="sales_returns", pk="return_id", lines="sales_return_lines",
                         fk="return_id", num="return_number", date="return_date",
                         party="customer", tpl="sales_return", printer="credit_note",
                         perm="sales_return", generic="sales_return",
                         ref=("original_invoice_no", "Original invoice"),
                         status="return_status"),
    "purchase": dict(title="PURCHASE INVOICE", label="Purchase Invoice",
                     table="purchase_invoices", pk="purchase_id",
                     lines="purchase_invoice_lines", fk="purchase_id",
                     num="invoice_number", date="invoice_date", party="supplier",
                     tpl="purchase_invoice", printer="purchase_invoice", perm="purchase",
                     generic="purchase_invoice",
                     ref=("supplier_invoice_no", "Supplier invoice"),
                     status="invoice_status"),
    "purchase_return": dict(title="PURCHASE RETURN (DEBIT NOTE)", label="Purchase Return",
                            table="purchase_returns", pk="return_id",
                            lines="purchase_return_lines", fk="return_id",
                            num="return_number", date="return_date", party="supplier",
                            tpl="purchase_return", printer="purchase_invoice",
                            perm="purchase_return", generic="purchase_return",
                            ref=("original_purchase_no", "Original purchase"),
                            status="return_status"),
    "quotation": dict(title="QUOTATION", label="Quotation", table="quotations",
                      pk="quote_id", lines="quotation_lines", fk="quote_id",
                      num="quote_number", date="quote_date", party="customer",
                      tpl="quotation", printer="quotation", perm="quotation",
                      generic="quotation", ref=("reference", "Reference"),
                      extra=(("valid_until", "Valid until"),), status="status"),
    "purchase_order": dict(title="PURCHASE ORDER", label="Purchase Order",
                           table="purchase_orders", pk="po_id",
                           lines="purchase_order_lines", fk="po_id", num="po_number",
                           date="po_date", party="supplier", tpl="purchase_order",
                           printer="purchase_invoice", perm="purchase_order",
                           generic="purchase_order", ref=("reference", "Reference"),
                           extra=(("expected_date", "Expected"),), status="status"),
    "receipt": dict(title="RECEIPT VOUCHER", label="Receipt", table="payments",
                    pk="payment_id", lines=None, num="payment_number",
                    date="payment_date", party="customer", tpl="receipt_voucher",
                    printer="receipt_voucher", perm="receipt", generic="receipt_voucher",
                    voucher=True, ptype="receipt"),
    "payment": dict(title="PAYMENT VOUCHER", label="Payment", table="payments",
                    pk="payment_id", lines=None, num="payment_number",
                    date="payment_date", party="supplier", tpl="payment_voucher",
                    printer="payment_voucher", perm="payment", generic="payment_voucher",
                    voucher=True, ptype="disbursement"),
}

last_message = ""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso(v):
    if v is None or v == "":
        return ""
    return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)[:10]


# ── load ─────────────────────────────────────────────────────
def _fill_line_barcodes(lines):
    """Lines don't store the barcode: take the one of the line's unit
    (else the product's main barcode) so a Barcode column can print it."""
    for ln in lines:
        if ln.get("barcode") or not ln.get("product_id"):
            continue
        bc = None
        try:
            r = db.fetchone("SELECT TOP 1 barcode FROM product_units WHERE product_id=? "
                            "AND unit_name_en=? AND barcode IS NOT NULL AND barcode<>'' "
                            "ORDER BY unit_id", (ln["product_id"], ln.get("unit_of_measure_en") or ""))
            bc = (r or {}).get("barcode")
            if not bc:
                r = db.fetchone("SELECT barcode FROM products WHERE product_id=?", (ln["product_id"],))
                bc = (r or {}).get("barcode")
        except Exception:
            bc = None
        if bc:
            ln["barcode"] = bc


def load(kind, doc_id):
    """Everything any layout needs for one saved document, or None."""
    k = KINDS[kind]
    row = db.fetchone(f"SELECT * FROM {k['table']} WHERE {k['pk']}=?", (doc_id,))
    if not row:
        return None
    row = dict(row)
    lines = []
    if k.get("lines"):
        lines = [dict(r) for r in (db.fetchall(
            f"SELECT * FROM {k['lines']} WHERE {k['fk']}=? ORDER BY line_number",
            (doc_id,)) or [])]
    company = dict(db.fetchone("SELECT * FROM company WHERE company_id=1") or {})
    _fill_line_barcodes(lines)

    # party
    if k.get("voucher"):
        is_cust = bool(row.get("customer_id"))
        ptype = "customer" if is_cust else "supplier"
    else:
        ptype = k["party"]
    pid = row.get(f"{ptype}_id")
    party = {}
    if pid:
        try:
            tbl = "customers" if ptype == "customer" else "suppliers"
            party = dict(db.fetchone(f"SELECT * FROM {tbl} WHERE {ptype}_id=?", (pid,)) or {})
        except Exception:
            party = {}
    pname = (row.get(f"{ptype}_name_en") or row.get("party_name_en")
             or party.get(f"{ptype}_name_en") or "")
    pname_ar = (row.get(f"{ptype}_name_ar") or row.get("party_name_ar")
                or party.get(f"{ptype}_name_ar") or "")
    pvat = (row.get(f"{ptype}_vat_no") or party.get("vat_registration_no")
            or party.get("vat_number") or "")
    paddr = (row.get("customer_address_en") or party.get("address_en")
             or party.get("city_en") or "")

    number = row.get(k["num"]) or str(doc_id)
    total = _f(row.get("amount")) if k.get("voucher") else _f(row.get("total_amount"))
    inv = dict(row)
    inv.update({
        "invoice_number": number,
        "invoice_date": row.get(k["date"]),
        "customer_name_en": pname, "customer_name_ar": pname_ar,
        "customer_vat_no": pvat, "customer_address": paddr,
        "total_amount": total,
        "subtotal_amount": row.get("subtotal_amount", total if k.get("voucher") else 0),
        "vat_amount": row.get("vat_amount", 0),
        "paid_amount": row.get("paid_amount", total if kind not in ("sales", "pos") else 0),
    })
    if kind in ("sales", "pos"):
        inv["paid_amount"] = row.get("paid_amount", 0)
        # Phase 2 (signed, cleared/reported) QR when there is one; otherwise
        # the Phase 1 QR is built from the SAVED invoice every time it is
        # printed, so it always matches the printed total / VAT / date —
        # also after an edit and for old / imported invoices.
        qr = row.get("zatca_qr_phase2")
        qr_problem = ""
        if not qr:
            try:
                from modules.zatca.qr_generator import phase1_for_invoice, vat_problem
                qr = phase1_for_invoice(row, company)
                if not qr:
                    qr_problem = vat_problem(company.get("vat_registration_no"))
            except Exception as e:
                qr = ""
                qr_problem = "The QR code could not be made (%s)." % str(e)[:120]
        inv["qr_code_data"] = qr
        inv["_qr_problem"] = qr_problem
    elif kind == "sales_return":
        qr = row.get("zatca_qr_phase2")                    # signed credit note
        if not qr:                 # v6.9.2: not signed (Phase 1) → the Phase 1 QR
            try:
                from modules.zatca.qr_generator import phase1_for_invoice
                qr = phase1_for_invoice({"invoice_date": row.get("return_date"),
                                         "created_at": row.get("created_at"),
                                         "total_amount": row.get("total_amount"),
                                         "vat_amount": row.get("vat_amount")}, company)
            except Exception:
                qr = ""
        inv["qr_code_data"] = qr or None
    extra = []
    ref = k.get("ref")
    if ref and row.get(ref[0]):
        extra.append((ref[1], row.get(ref[0])))
    for col, lbl in k.get("extra", ()):
        if row.get(col):
            extra.append((lbl, cfg.fmt_date(row.get(col))))
    if pvat:
        extra.append(("VAT No.", pvat))
    header = {
        "number": number, "date": cfg.fmt_date(row.get(k["date"])),
        "party_name": pname, "party_address": paddr, "extra": extra,
        "subtotal": row.get("subtotal_amount"), "vat": row.get("vat_amount"),
        "total": total, "amount": total, "currency": company.get("currency") or "SAR",
        "narration": row.get("notes_en") or "", "notes": row.get("notes_en") or "",
        "payment": row.get("payment_method") or "",
        # ZATCA Phase 2 QR of a signed credit note
        "qr": inv.get("qr_code_data") if kind == "sales_return" else None,
    }
    title = k["title"]
    if kind in ("sales", "pos") and str(row.get("invoice_kind") or "").lower() == "debit":
        # v6.0 debit note: its own title, the invoice it adds to and why
        inv["invoice_type_code"] = "383"
        title = "Debit Note"
        if row.get("original_invoice_no"):
            header["extra"].insert(0, ("Original invoice", row.get("original_invoice_no")))
        if row.get("debit_reason"):
            header["extra"].insert(1, ("Reason", row.get("debit_reason")))
    return {"kind": kind, "conf": k, "id": doc_id, "row": row, "inv": inv,
            "lines": lines, "company": company, "header": header,
            "number": number, "party_type": ptype, "title": title}


def last_id(kind):
    """Id of the most recent saved document of this kind ('print previous')."""
    k = KINDS[kind]
    where = []
    if kind == "pos":
        where.append("sale_channel='POS'")
    elif kind == "sales":
        where.append("ISNULL(sale_channel,'INV')<>'POS'")
    if k.get("ptype"):
        where.append(f"payment_type='{k['ptype']}'")
    sql = f"SELECT TOP 1 {k['pk']} AS id FROM {k['table']}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {k['pk']} DESC"
    try:
        r = db.fetchone(sql)
    except Exception:
        try:                                   # older DB: no sale_channel yet
            r = db.fetchone(f"SELECT TOP 1 {k['pk']} AS id FROM {k['table']} "
                            + (f"WHERE payment_type='{k['ptype']}' " if k.get("ptype") else "")
                            + f"ORDER BY {k['pk']} DESC")
        except Exception:
            r = None
    return (r or {}).get("id")


# ── designer template (Report / Invoice Designer) ────────────
def designer_template(kind):
    """(template, elements) of the ★ default design for this document,
    or (None, None) when there is no design yet."""
    try:
        from modules import report_designer as rd
        if not rd.tables_ready():
            return None, None
        tpl = rd.get_default_template(KINDS[kind]["tpl"])
        if not tpl:
            return None, None
        els = rd.load_layout(tpl["template_id"])
        return (tpl, els) if els else (None, None)
    except Exception:
        return None, None


def _is_roll(tpl):
    return str((tpl or {}).get("paper_size", "A4")) in ("80mm", "58mm")


# ── build files ──────────────────────────────────────────────
def _safe(s):
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(s))


def _tmp(doc, tag, ext):
    return os.path.join(tempfile.gettempdir(),
                        f"{_safe(doc['kind'])}_{_safe(doc['number'])}_{tag}.{ext}")


def _builtin_pdf(doc, fmt, path):
    kind, inv, lines, comp = doc["kind"], doc["inv"], doc["lines"], doc["company"]
    k = doc["conf"]
    if kind in ("sales", "pos"):
        if fmt == "thermal":
            from modules.thermal_receipt import generate_thermal_receipt
            generate_thermal_receipt(inv, comp, lines, path, qr_data=inv.get("qr_code_data"))
        else:
            from modules.pdf_invoice import generate_invoice_pdf
            generate_invoice_pdf(inv, comp, lines, path, qr_base64=inv.get("qr_code_data"))
        return path
    from modules.generic_doc_pdf import generate_generic_pdf
    plabel = "Customer" if doc["party_type"] == "customer" else "Supplier"
    if k.get("voucher"):
        plabel = "Received from" if kind == "receipt" else "Paid to"
    generate_generic_pdf(k["generic"], doc["header"], comp, lines, path,
                         party_label=plabel, with_items=not k.get("voucher"))
    return path


def builtin_format(doc):
    """'thermal' or 'a4' for the built-in default layout."""
    if doc["kind"] == "pos":
        return "a4" if str(cfg.get("pos_print_format", "thermal")).lower() == "a4" else "thermal"
    if doc["kind"] == "sales":
        return "thermal" if str(cfg.get("paper_width", "80")) in ("58", "80") else "a4"
    return "a4"


last_template_error = ""      # set when YOUR designer template could not be used
last_qr_note = ""             # set when a sales / POS invoice printed WITHOUT its QR


def _has_qr_box(els):
    return any(str(e.get("type", "")) == "qr" or e.get("key") == "qr_code"
               for e in (els or []))


def qr_note(doc, option="default", source=None):
    """Why this sales / POS invoice has no ZATCA QR code ('' = it has one).
    source: 'designer' / 'builtin' when known (after rendering)."""
    if not doc or doc.get("kind") not in ("sales", "pos"):
        return ""
    if option == "dotmatrix":
        return ("Dot-matrix printing is text only, so it cannot print the QR "
                "code. Use 🖨 Print (default layout) for an invoice with the QR.")
    inv = doc.get("inv") or {}
    row = doc.get("row") or {}
    if row.get("zatca_kind") == "standard" and str(row.get("zatca_status") or "") != "cleared":
        return ("This B2B tax invoice is not cleared by ZATCA yet "
                "(ZATCA ▸ status: %s), so the ZATCA QR is not on it. Print again after it is "
                "cleared — DayBill sends it automatically." % (row.get("zatca_status") or "waiting"))
    if not inv.get("qr_code_data"):
        from modules.zatca.qr_generator import QR_FIX_HINT
        why = inv.get("_qr_problem") or "The company VAT number is missing."
        return why + "\n" + QR_FIX_HINT
    tpl, els = designer_template(doc["kind"])
    if source is None:
        source = "designer" if (tpl and (option != "pdf" or not _is_roll(tpl))) else "builtin"
    if source == "designer" and tpl:
        if not _has_qr_box(els):
            return ("Your own template '%s' has no QR code box.\nInvoice Designer ▸ "
                    "add 'QR Code (ZATCA)' to it and save." % tpl.get("template_name", ""))
        return ""
    fmt = "a4" if option == "pdf" else builtin_format(doc)
    if fmt == "thermal" and not cfg.flag("pos_qr_print", True):
        return "Settings ▸ POS ▸ 'Print QR Code' is switched off. Tick it to print the QR."
    if fmt == "a4" and not cfg.get("print_zatca_qr", True):
        return ("Print & Invoice ▸ 'ZATCA QR code (Saudi)' is switched off. "
                "Tick it to print the QR.")
    return ""


def render_default(doc):
    """PDF of the default layout. Returns (path, source) where source is
    'designer' or 'builtin'."""
    global last_template_error
    last_template_error = ""
    tpl, els = designer_template(doc["kind"])
    path = _tmp(doc, "print", "pdf")
    if tpl:
        try:
            from modules.template_renderer import render_template
            render_template(tpl, els, doc["inv"], doc["company"], doc["lines"], path)
            return path, "designer"
        except Exception as e:
            print("[DayBill] designer template failed, using built-in:", e)
            last_template_error = "%s: %s" % (tpl.get("template_name", "template"), str(e)[:200])
    return _builtin_pdf(doc, builtin_format(doc), path), "builtin"


def render_pdf(doc, folder=None):
    """A4 PDF for viewing / saving. Kept in Documents\\DayBill PDF."""
    tpl, els = designer_template(doc["kind"])
    folder = folder or pdf_folder()
    path = os.path.join(folder, f"{_safe(doc['conf']['label'])}_{_safe(doc['number'])}.pdf")
    if tpl and not _is_roll(tpl):
        try:
            from modules.template_renderer import render_template
            render_template(tpl, els, doc["inv"], doc["company"], doc["lines"], path)
            return path
        except Exception as e:
            print("[DayBill] designer template failed, using built-in:", e)
            global last_template_error
            last_template_error = "%s: %s" % (tpl.get("template_name", "template"), str(e)[:200])
    return _builtin_pdf(doc, "a4", path)


def render_dotmatrix(doc, width=None):
    """(text, width) for impact printers."""
    from modules import dotmatrix_receipt as DM
    tpl = DM.get_active_template()
    w = int(width or tpl.get("width", 80) or 80)
    w = 132 if w >= 132 else 80
    k = doc["conf"]
    if k.get("voucher"):
        method = doc["row"].get("payment_method") or ""
        txt = DM.build_voucher_text(
            doc["company"], k["title"], doc["number"], doc["header"]["date"],
            "Received from" if doc["kind"] == "receipt" else "Paid to",
            doc["header"]["party_name"], doc["header"]["amount"], method,
            doc["header"]["narration"], width=w,
            extra=[("Cheque No", doc["row"].get("cheque_number")),
                   ("Reference", doc["row"].get("reference_number"))])
        return txt, w
    t = dict(tpl); t["width"] = w
    labels = {"title": k["title"], "zatca": doc["kind"] in ("sales", "pos"),
              "number": "Number" if doc["kind"] not in ("sales", "pos") else "Invoice #",
              "party": "Customer" if doc["party_type"] == "customer" else "Supplier",
              "extra": [e for e in doc["header"]["extra"] if e[0] != "VAT No."]}
    return DM.build_invoice_text(doc["inv"], doc["company"], doc["lines"], width=w,
                                 template=t, labels=labels), w


def pdf_folder():
    base = os.path.join(os.path.expanduser("~"), "Documents", "DayBill PDF")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        base = tempfile.gettempdir()
    return base


# ── printer choice ───────────────────────────────────────────
def default_printer_for(doc, option="default"):
    """Which printer this document goes to when nobody is asked."""
    from modules import printer_service as ps
    if option == "dotmatrix":
        return ps.printer_for("dotmatrix")
    tpl, _els = designer_template(doc["kind"])
    if tpl:
        try:
            from modules import report_designer as rd
            p = rd.get_template_printer(tpl["template_id"])
            if p:
                return p
        except Exception:
            pass
    key = doc["conf"]["printer"]
    if doc["kind"] == "sales" and builtin_format(doc) == "thermal" and not tpl:
        key = "pos_invoice"
    return ps.printer_for(key)


def copies_for(doc):
    tpl, _els = designer_template(doc["kind"])
    try:
        if tpl and int(tpl.get("print_copies") or 0) > 1:
            return int(tpl["print_copies"])
    except (TypeError, ValueError):
        pass
    try:
        return max(1, int(cfg.get("print_copies", 1) or 1))
    except (TypeError, ValueError):
        return 1


# ── print ────────────────────────────────────────────────────
def print_document(kind, doc_id, option="default", printer=None, copies=None,
                   ask=None, parent=None, width=None):
    """Print (or open as PDF) one saved document.
    ask: None = follow Settings (print_direct); True = always ask the
    printer; False = never ask. Returns (ok, message)."""
    global last_message, last_qr_note
    from modules import printer_service as ps
    last_qr_note = ""
    if option not in OPTIONS:
        option = "default"
    doc = load(kind, doc_id)
    if not doc:
        last_message = "Document not found."
        return False, last_message
    label = f"{doc['conf']['label']} {doc['number']}"

    if option == "pdf":
        path = render_pdf(doc)
        try:
            last_qr_note = qr_note(doc, "pdf",
                                   "builtin" if last_template_error else None)
        except Exception:
            last_qr_note = ""
        ps.open_file(path)
        _audit(doc, "pdf", path)
        last_message = f"📄 {label} saved as PDF:\n{path}"
        return True, last_message

    if printer is None:
        printer = default_printer_for(doc, option)
    if copies is None:
        copies = copies_for(doc)
    if ask is None:
        ask = not ps.print_direct()
    if ask and parent is not None:
        try:
            from ui.print_menu import ask_printer
            got = ask_printer(parent, label, printer, copies,
                              dotmatrix=(option == "dotmatrix"),
                              map_key=doc["conf"]["printer"])
        except Exception:
            got = (printer, copies)
        if not got:
            last_message = "Print cancelled."
            return False, last_message
        printer, copies = got

    if option == "dotmatrix":
        text, w = render_dotmatrix(doc, width)
        ok = ps.print_text(text, printer, width=w, copies=copies,
                           name=f"{kind}_{doc['number']}")
        _src = None
    else:
        path, _src = render_default(doc)
        ok = ps.print_pdf(path, printer, copies=copies)
    try:
        last_qr_note = qr_note(doc, option, _src)
    except Exception:
        last_qr_note = ""
    _audit(doc, option, printer)
    where = f" on {printer}" if printer else ""
    last_message = (f"🖨 {label} sent{where}." if ok else
                    f"⚠ {label} could not be printed{where}. {ps.last_error}")
    return ok, last_message


def _audit(doc, option, where):
    try:
        from modules import audit
        audit.log("print", doc["kind"], doc["id"], f"{doc['number']} {option} {where or ''}"[:200])
    except Exception:
        pass


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")
