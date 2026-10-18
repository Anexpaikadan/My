# ============================================================
# DayBill ERP - Report Designer backend
# Template CRUD, themes, printer settings, version control.
# The UI (drag-drop canvas) sits on top of this in ui/report_designer.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


def _cur():
    """v7.0: the company's currency symbol / tax words in new layouts."""
    try:
        from modules import country as _K
        return _K.symbol()
    except Exception:
        return "SAR"


def _taxword():
    try:
        from modules import country as _K
        return "VAT %g%%" % _K.std_rate() if not _K.is_in() else "GST"
    except Exception:
        return "VAT 15%"


def _taxno():
    try:
        from modules import country as _K
        return _K.tax_no_label()
    except Exception:
        return "VAT No"

def tables_ready():
    try:
        return bool(db.execute_scalar(
            "SELECT COUNT(*) FROM sys.tables WHERE name='report_templates'"))
    except Exception:
        return False


# ── Templates ─────────────────────────────────────────────────
_NUM_DEFAULTS = {"header_height": 38, "footer_height": 20, "print_copies": 1,
                 "font_size": 9}
_TXT_DEFAULTS = {"paper_size": "A4", "orientation": "portrait",
                 "header_color": "#3A1FD6", "table_color": "#3A1FD6",
                 "accent_color": "#3A1FD6", "font_color": "#20242B",
                 "footer_color": "#3A1FD6", "theme_name": "Modern"}


def _norm(row):
    """DB rows can hold explicit NULLs (dict.get defaults don't apply
    then). Coalesce numeric/colour columns so the designer and renderer
    never do arithmetic on None."""
    if not row:
        return row
    for k, d in _NUM_DEFAULTS.items():
        if k in row and row[k] is None:
            row[k] = d
    for k, d in _TXT_DEFAULTS.items():
        if k in row and (row[k] is None or str(row[k]).strip() == ""):
            row[k] = d
    return row


def list_templates(report_type="invoice"):
    try:
        rows = db.fetchall(
            "SELECT * FROM report_templates WHERE is_active=1 AND report_type=? "
            "ORDER BY is_default DESC, template_name", (report_type,)) or []
        return [_norm(r) for r in rows]
    except Exception:
        return []


def get_template(template_id):
    return _norm(db.fetchone(
        "SELECT * FROM report_templates WHERE template_id=?", (template_id,)))


def get_default_template(report_type="invoice"):
    return _norm(db.fetchone(
        "SELECT TOP 1 * FROM report_templates WHERE is_active=1 AND report_type=? "
        "ORDER BY is_default DESC, template_id", (report_type,)))


def create_template(data):
    """data: dict of column->value. Returns new template_id."""
    cols = ["template_name", "report_type", "paper_size", "orientation",
            "margin_top", "margin_bottom", "margin_left", "margin_right",
            "scaling", "print_copies", "theme_name", "header_color",
            "footer_color", "table_color", "font_color", "accent_color",
            "header_text", "footer_text", "header_height", "footer_height",
            "language", "layout_json"]
    vals = [data.get(c) for c in cols]
    placeholders = ",".join(["?"] * len(cols))
    db.execute(
        f"INSERT INTO report_templates ({','.join(cols)}) VALUES ({placeholders})",
        tuple(vals))
    return db.execute_scalar(
        "SELECT TOP 1 template_id FROM report_templates ORDER BY template_id DESC")


def update_template(template_id, data):
    if not data:
        return
    set_clause = ", ".join(f"{k}=?" for k in data)
    db.execute(
        f"UPDATE report_templates SET {set_clause}, version=version+1, "
        f"updated_at=GETDATE() WHERE template_id=?",
        (*data.values(), template_id))
    # snapshot version
    try:
        t = get_template(template_id)
        db.execute(
            "INSERT INTO report_versions (template_id, version, layout_json) "
            "VALUES (?,?,?)",
            (template_id, t.get("version", 1), t.get("layout_json")))
    except Exception:
        pass


def clone_template(template_id, new_name=None):
    t = get_template(template_id)
    if not t:
        return None
    data = dict(t)
    for drop in ("template_id", "created_at", "updated_at", "version", "is_default"):
        data.pop(drop, None)
    data["template_name"] = new_name or (t["template_name"] + " (Copy)")
    return create_template(data)


def delete_template(template_id):
    db.execute("UPDATE report_templates SET is_active=0 WHERE template_id=?",
               (template_id,))


def set_default(template_id, report_type="invoice"):
    db.execute("UPDATE report_templates SET is_default=0 WHERE report_type=?",
               (report_type,))
    db.execute("UPDATE report_templates SET is_default=1 WHERE template_id=?",
               (template_id,))


# ── Layout (drag-drop canvas state) ───────────────────────────
def save_layout(template_id, elements):
    """elements: list of dicts describing canvas elements."""
    db.execute(
        "UPDATE report_templates SET layout_json=?, version=version+1, "
        "updated_at=GETDATE() WHERE template_id=?",
        (json.dumps(elements), template_id))


def load_layout(template_id):
    t = get_template(template_id)
    if t and t.get("layout_json"):
        try:
            els = json.loads(t["layout_json"])
            # coalesce geometry so the canvas/renderer never multiplies None
            for el in els:
                for k, d in (("x", 30), ("y", 30), ("w", 120), ("h", 22),
                             ("font_size", 9)):
                    if el.get(k) is None:
                        el[k] = d
            return els
        except Exception:
            return []
    return []


# ── Themes ────────────────────────────────────────────────────
def list_themes():
    try:
        return db.fetchall("SELECT * FROM report_themes ORDER BY theme_id") or []
    except Exception:
        return []


def get_theme(theme_name):
    return db.fetchone("SELECT * FROM report_themes WHERE theme_name=?", (theme_name,))


# ── Printer settings ──────────────────────────────────────────
def list_printers():
    """Real installed system printers — delegates to the canonical
    printer_service (same list used by Printer Management and by actual
    document printing), so the designer never shows a different set."""
    try:
        from modules.printer_service import list_printers as _lp
        printers = _lp() or []
    except Exception:
        printers = []
    if not printers:
        printers = ["(no printers detected)"]
    return printers


def get_default_printer():
    try:
        from modules.printer_service import default_printer as _dp
        return _dp()
    except Exception:
        return None


def get_template_printer(template_id):
    """The printer saved for this template, if any."""
    try:
        row = db.fetchone(
            "SELECT TOP 1 printer_name FROM report_printer_settings "
            "WHERE template_id=? AND is_default=1 ORDER BY printer_id DESC",
            (template_id,))
        return row["printer_name"] if row and row.get("printer_name") else None
    except Exception:
        return None


def save_printer_setting(template_id, printer_name, printer_type="A4", is_default=True):
    """Upsert: one saved printer per template (replaces any previous
    choice instead of accumulating duplicate rows on every selection)."""
    try:
        db.execute("DELETE FROM report_printer_settings WHERE template_id=?",
                  (template_id,))
    except Exception:
        pass
    db.execute(
        "INSERT INTO report_printer_settings (template_id, printer_name, "
        "printer_type, is_default) VALUES (?,?,?,?)",
        (template_id, printer_name, printer_type, 1 if is_default else 0))


def clear_template_printer(template_id):
    """'Use the default printer' ticked: forget the template's own printer."""
    try:
        db.execute("DELETE FROM report_printer_settings WHERE template_id=?", (template_id,))
    except Exception:
        pass


# Documents that can have their own designs (key, label, print kind)
DOC_TYPES = [
    ("sales_invoice", "Sales Invoice", "sales"),
    ("pos_invoice", "POS Bill (thermal)", "pos"),
    ("sales_return", "Sales Return", "sales_return"),
    ("purchase_invoice", "Purchase Invoice", "purchase"),
    ("purchase_return", "Purchase Return", "purchase_return"),
    ("quotation", "Quotation", "quotation"),
    ("purchase_order", "Purchase Order", "purchase_order"),
    ("receipt_voucher", "Receipt Voucher", "receipt"),
    ("payment_voucher", "Payment Voucher", "payment"),
]
TITLES = {"sales_invoice": "TAX INVOICE  فاتورة ضريبية",
          "pos_invoice": "SIMPLIFIED TAX INVOICE",
          "sales_return": "SALES RETURN (CREDIT NOTE)",
          "purchase_invoice": "PURCHASE INVOICE", "purchase_return": "PURCHASE RETURN",
          "quotation": "QUOTATION", "purchase_order": "PURCHASE ORDER",
          "receipt_voucher": "RECEIPT VOUCHER", "payment_voucher": "PAYMENT VOUCHER"}
SUPPLIER_DOCS = ("purchase_invoice", "purchase_return", "purchase_order")
VOUCHER_DOCS = ("receipt_voucher", "payment_voucher")


def kind_of(doc_type):
    return next((k for d, _l, k in DOC_TYPES if d == doc_type), "sales")


def starter_layout(doc_type, paper="A4"):
    """A ready layout to start a new template from (designer px units:
    2.2 px = 1 mm, y=0 is the top of the page; header band ≈ 28 px)."""
    party = ("Supplier: " if doc_type in SUPPLIER_DOCS else
             "Received from: " if doc_type == "receipt_voucher" else
             "Paid to: " if doc_type == "payment_voucher" else "Customer: ")
    els = []

    def add(key, label, x, y, w, h, font=9, bold=False, align="left", typ="text",
            prefix="", **kw):
        e = {"id": len(els) + 1, "key": key, "label": label, "type": typ,
             "x": x, "y": y, "w": w, "h": h, "font": font, "bold": bold,
             "align": align, "prefix": prefix}
        e.update(kw)
        els.append(e)

    if str(paper) in ("80mm", "58mm"):
        W = 176 if str(paper) == "80mm" else 128
        add("company_name", "Company Name", 4, 32, W - 8, 16, 11, True, "center")
        add("company_vat", "Company VAT", 4, 48, W - 8, 12, 7, False, "center", prefix="VAT: ")
        add("line", "Line", 4, 64, W - 8, 2, typ="line")
        add("invoice_number", "Number", 4, 68, W - 8, 12, 8, True, prefix="No: ")
        add("invoice_date", "Date", 4, 80, W - 8, 12, 8, prefix="Date: ")
        add("customer_name", "Party", 4, 92, W - 8, 12, 8, prefix=party)
        if doc_type in VOUCHER_DOCS:
            add("grand_total", "Amount", 4, 110, W - 8, 16, 11, True, "right", prefix="Amount: ")
            add("amount_in_words", "In words", 4, 128, W - 8, 12, 6)
            add("payment_terms", "Method", 4, 140, W - 8, 12, 7, prefix="Paid by: ")
            for e in els:
                e["y"] = max(4, e["y"] - 24)
            return els
        for c_ in item_columns(["product_name", "quantity", "rate", "line_total"],
                               4, 108, W - 8, 40, font=7, header_ar=False):
            c_["id"] = len(els) + 1
            els.append(c_)
        add("subtotal", "Subtotal", 4, 144, W - 8, 12, 8, False, "right", prefix="Subtotal: ")
        add("tax_total", "VAT", 4, 156, W - 8, 12, 8, False, "right", prefix="VAT: ")
        add("grand_total", "Total", 4, 170, W - 8, 16, 11, True, "right", prefix="TOTAL: ")
        if doc_type in ("sales_invoice", "pos_invoice"):
            add("qr_code", "QR Code", (W - 70) // 2, 192, 70, 70, typ="qr")
        for e in els:                 # roll paper has no header band
            e["y"] = max(4, e["y"] - 24)
        return els

    # A4 (462 x 653 px)
    add("company_logo", "Company Logo", 8, 34, 60, 44, typ="image")
    add("company_name", "Company Name", 74, 34, 230, 18, 13, True)
    add("company_address", "Company Address", 74, 52, 230, 12, 8)
    add("company_vat", "Company VAT", 74, 64, 230, 12, 8, prefix="%s: " % _taxno())
    add("invoice_number", "Number", 300, 34, 154, 14, 10, True, "right", prefix="No: ")
    add("invoice_date", "Date", 300, 48, 154, 12, 9, False, "right", prefix="Date: ")
    add("reference", "Reference", 300, 60, 154, 12, 8, False, "right", prefix="Ref: ")
    add("line", "Line", 8, 84, 446, 2, typ="line")
    add("customer_name", "Party Name", 8, 90, 290, 14, 10, True, prefix=party)
    add("customer_vat", "Party VAT", 8, 104, 290, 12, 8, prefix="%s: " % _taxno())
    add("customer_address", "Party Address", 8, 116, 290, 12, 8)
    add("payment_terms", "Payment", 300, 90, 154, 12, 8, False, "right", prefix="Payment: ")
    if doc_type in VOUCHER_DOCS:
        add("grand_total", "Amount", 8, 140, 446, 22, 16, True, "left", prefix="Amount %s " % _cur())
        add("amount_in_words", "Amount in words", 8, 166, 446, 12, 9)
        add("notes", "Narration", 8, 184, 446, 12, 9, prefix="Narration: ")
        add("signature", "Received by", 8, 560, 150, 40, typ="signature")
        add("stamp", "Authorized signature", 300, 560, 154, 40, typ="signature")
        return els
    for c_ in item_columns(["line_no", "product_name", "quantity", "unit", "rate",
                            "line_amount", "tax", "line_total"], 8, 134, 446, 44):
        c_["id"] = len(els) + 1
        els.append(c_)
    add("subtotal", "Subtotal", 300, 172, 154, 12, 9, False, "right", prefix="Subtotal: ")
    add("discount_total", "Discount", 300, 184, 154, 12, 9, False, "right", prefix="Discount: ")
    add("tax_total", "VAT", 300, 196, 154, 12, 9, False, "right", prefix="%s: " % _taxword())
    add("grand_total", "Grand Total", 300, 210, 154, 18, 12, True, "right", prefix="TOTAL %s " % _cur())
    add("amount_in_words", "Amount in words", 8, 234, 446, 12, 8)
    add("notes", "Notes", 8, 248, 446, 12, 8, prefix="Notes: ")
    if doc_type in ("sales_invoice", "pos_invoice"):
        add("qr_code", "QR Code", 8, 172, 66, 66, typ="qr")
    add("signature", "Receiver", 8, 560, 150, 40, typ="signature")
    add("stamp", "Authorized signature", 300, 560, 154, 40, typ="signature")
    for e in els:                     # room under the (taller) item columns
        if e.get("type") != "item_col" and 164 <= e["y"] < 500:
            e["y"] += 14
    return els


# Available toolbox fields (for the drag-drop palette)
DEFAULT_TABLE_COLS = ["item_code", "product_name", "quantity", "rate",
                      "tax", "line_total"]
TOOLBOX = {
    "Company": [
        ("company_name", "Company Name"), ("company_name_ar", "Company Name (Arabic)"),
        ("company_address", "Company Address"), ("company_vat", "Company VAT No."),
        ("company_cr", "Company CR No."), ("company_phone", "Company Phone"),
        ("company_website", "Company Website"),
    ],
    "Document": [
        ("invoice_number", "Document Number"), ("invoice_date", "Date"),
        ("invoice_time", "Time"), ("due_date", "Due Date"), ("reference", "Reference"),
        ("customer_name", "Customer / Supplier Name"),
        ("customer_name_ar", "Customer / Supplier (Arabic)"),
        ("customer_address", "Customer / Supplier Address"),
        ("customer_vat", "Customer / Supplier VAT"), ("salesperson", "Salesperson"),
        ("payment_terms", "Payment Method"), ("notes", "Notes / Narration"),
        ("current_date", "Print Date"),
    ],
    "Item Columns (each separate)": [
        ("col:line_no", "▥ No. (#)"), ("col:item_code", "▥ Code"),
        ("col:barcode", "▥ Barcode"), ("col:product_name", "▥ Item (EN + Arabic)"),
        ("col:product_name_ar", "▥ Item Arabic only"), ("col:quantity", "▥ Qty"),
        ("col:unit", "▥ Unit"), ("col:rate", "▥ Price"), ("col:discount", "▥ Discount"),
        ("col:line_amount", "▥ Amount (excl VAT)"), ("col:vat_rate", "▥ VAT %"),
        ("col:tax", "▥ VAT Amount"), ("col:line_total", "▥ Total"),
    ],
    "Product Table": [
        ("table", "▦ Items Table (one block)"),
    ],
    "Totals": [
        ("subtotal", "Sub Total"), ("discount_total", "Discount Total"),
        ("tax_total", "VAT Total"), ("grand_total", "Grand Total"),
        ("paid_amount", "Paid Amount"), ("balance_amount", "Balance"),
        ("amount_in_words", "Amount in Words"),
    ],
    "Extras": [
        ("text_label", "Text Label"), ("company_logo", "Company Logo"),
        ("qr_code", "QR Code (ZATCA)"), ("barcode", "Barcode (number)"),
        ("signature", "Signature Line"), ("stamp", "Stamp / Authorised Line"),
        ("line", "Line Separator"),
    ],
}
TABLE_COLUMNS = ["item_code", "product_name", "product_name_ar", "description",
                 "quantity", "unit", "rate", "discount", "line_amount", "tax", "line_total"]

SECTIONS = ["report_header", "page_header", "detail", "group_header",
            "group_footer", "page_footer", "report_footer"]


# ── Item columns: every column of the items table is its own element ──
# (field, header EN, header AR, relative width, align)
ITEM_COLUMNS = [
    ("line_no", "#", "م", 5, "center"),
    ("item_code", "Code", "الرمز", 12, "left"),
    ("barcode", "Barcode", "الباركود", 16, "left"),
    ("product_name", "Item", "الصنف", 40, "left"),
    ("product_name_ar", "Item (AR)", "الصنف", 30, "right"),
    ("quantity", "Qty", "الكمية", 8, "right"),
    ("unit", "Unit", "الوحدة", 9, "center"),
    ("rate", "Price", "السعر", 12, "right"),
    ("discount", "Disc", "الخصم", 10, "right"),
    ("line_amount", "Amount", "المبلغ", 13, "right"),
    ("vat_rate", "VAT %", "النسبة", 8, "right"),
    ("tax", "VAT", "الضريبة", 11, "right"),
    ("line_total", "Total", "الإجمالي", 14, "right"),
]
_COLINFO = {c[0]: c for c in ITEM_COLUMNS}
# old one-block table column keys → item column fields
_OLD_COLS = {"description": "product_name"}


def column_info(field):
    return _COLINFO.get(field, (field, field.replace("_", " ").title(), "", 10, "left"))


def item_columns(fields, x, y, w, h, font=8, header_ar=True):
    """Separate column elements side by side across x..x+w (widths by
    the usual size of each column)."""
    fields = [_OLD_COLS.get(f, f) for f in fields]
    rel = [column_info(f)[3] for f in fields]
    tot = float(sum(rel)) or 1.0
    out, cx = [], float(x)
    for i, f in enumerate(fields):
        info = column_info(f)
        cw = w * rel[i] / tot
        if i == len(fields) - 1:
            cw = x + w - cx
        out.append({"id": 0, "key": "col:" + f, "field": f, "type": "item_col",
                    "label": info[1], "label_ar": info[2], "header_ar": header_ar,
                    "x": int(round(cx)), "y": int(y), "w": max(8, int(round(cw))), "h": int(h),
                    "font": font, "bold": False, "align": info[4],
                    "ar_second_line": f == "product_name"})
        cx += cw
    # integer rounding: make the columns touch exactly
    for a, b in zip(out, out[1:]):
        b["x"] = a["x"] + a["w"]
    if out:
        out[-1]["w"] = max(8, int(x + w) - out[-1]["x"])
    return out


def split_table(table_el, start_id=1):
    """One-block items table → separate column elements (same place)."""
    cols = table_el.get("cols") or DEFAULT_TABLE_COLS
    out = item_columns(cols, table_el.get("x", 8), table_el.get("y", 134),
                       table_el.get("w", 446), max(30, int(table_el.get("h") or 30)),
                       font=int(table_el.get("font") or 8))
    for i, c in enumerate(out):
        c["id"] = start_id + i
    return out


# ── Save a template to a file / open it / copy it to another document ──
FILE_KIND = "daybill-template"
_TPL_FIELDS = ("template_name", "paper_size", "orientation", "margin_top", "margin_bottom",
               "margin_left", "margin_right", "scaling", "print_copies", "theme_name",
               "header_color", "footer_color", "table_color", "font_color", "accent_color",
               "header_text", "footer_text", "header_height", "footer_height", "language")


def template_to_dict(template, elements, report_type=None):
    t = {k: template.get(k) for k in _TPL_FIELDS if k in template}
    for k, v in list(t.items()):
        if hasattr(v, "isoformat"):
            t[k] = v.isoformat()
        elif v is not None and not isinstance(v, (str, int, float, bool)):
            t[k] = float(v)
    clean = [{k: v for k, v in e.items() if not str(k).startswith("_")} for e in elements or []]
    return {"kind": FILE_KIND, "version": 1, "report_type": report_type or template.get("report_type"),
            "template": t, "elements": clean}


def export_template(path, template, elements, report_type=None):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template_to_dict(template, elements, report_type), f, ensure_ascii=False, indent=2)
    return path


def read_template_file(path):
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict) or d.get("kind") != FILE_KIND or not isinstance(d.get("elements"), list):
        raise ValueError("This is not a DayBill template file.")
    return d


def create_from_dict(d, report_type, name=None, make_default=False):
    """New template in `report_type` from a saved dict (file or copy)."""
    t = dict(d.get("template") or {})
    t["template_name"] = (name or t.get("template_name") or "Imported design")[:100]
    t["report_type"] = report_type
    els = d.get("elements") or []
    for i, e in enumerate(els, 1):
        e["id"] = i
    t["layout_json"] = json.dumps(els)
    t.setdefault("paper_size", "A4"); t.setdefault("orientation", "portrait")
    t.setdefault("print_copies", 1)
    tid = create_template(t)
    if make_default:
        set_default(tid, report_type)
    return tid


def import_template(path, report_type, name=None, make_default=False):
    return create_from_dict(read_template_file(path), report_type, name, make_default)


def copy_to(template_id, report_type, name=None, make_default=False, elements=None):
    """Same design for another document (e.g. Sales Invoice → Sales Return)."""
    t = get_template(template_id)
    if not t:
        return None
    d = template_to_dict(t, elements if elements is not None else load_layout(template_id))
    lbl = next((l for k, l, _ in DOC_TYPES if k == report_type), report_type)
    return create_from_dict(d, report_type, name or f"{t['template_name']} ({lbl})", make_default)
