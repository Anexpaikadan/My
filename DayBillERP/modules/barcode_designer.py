# ============================================================
# DayBill ERP - Barcode Label Designer backend
# Template CRUD, sequence generation, batch label PDF rendering.
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


def tables_ready():
    try:
        return bool(db.execute_scalar(
            "SELECT COUNT(*) FROM sys.tables WHERE name='barcode_templates'"))
    except Exception:
        return False


# ── Templates ─────────────────────────────────────────────────
def list_templates():
    try:
        return db.fetchall(
            "SELECT * FROM barcode_templates WHERE is_active=1 "
            "ORDER BY is_default DESC, template_name") or []
    except Exception:
        return []


def get_template(tid):
    return db.fetchone("SELECT * FROM barcode_templates WHERE template_id=?", (tid,))


def create_template(data):
    cols = ["template_name", "barcode_type", "label_width_mm", "label_height_mm",
            "paper_mode", "cols_per_sheet", "rows_per_sheet", "gap_x_mm",
            "gap_y_mm", "margin_mm", "dpi", "layout_json"]
    vals = [data.get(c) for c in cols]
    ph = ",".join(["?"] * len(cols))
    db.execute(f"INSERT INTO barcode_templates ({','.join(cols)}) VALUES ({ph})",
               tuple(vals))
    return db.execute_scalar(
        "SELECT TOP 1 template_id FROM barcode_templates ORDER BY template_id DESC")


def update_template(tid, data):
    if not data:
        return
    set_clause = ", ".join(f"{k}=?" for k in data)
    db.execute(f"UPDATE barcode_templates SET {set_clause}, updated_at=GETDATE() "
               f"WHERE template_id=?", (*data.values(), tid))


def clone_template(tid, new_name=None):
    t = get_template(tid)
    if not t:
        return None
    data = dict(t)
    for d in ("template_id", "created_at", "updated_at", "is_default"):
        data.pop(d, None)
    data["template_name"] = new_name or (t["template_name"] + " (Copy)")
    return create_template(data)


def delete_template(tid):
    db.execute("UPDATE barcode_templates SET is_active=0 WHERE template_id=?", (tid,))


def set_default(tid):
    db.execute("UPDATE barcode_templates SET is_default=0")
    db.execute("UPDATE barcode_templates SET is_default=1 WHERE template_id=?", (tid,))


def save_layout(tid, elements):
    db.execute("UPDATE barcode_templates SET layout_json=?, updated_at=GETDATE() "
               "WHERE template_id=?", (json.dumps(elements), tid))


def load_layout(tid):
    t = get_template(tid)
    if t and t.get("layout_json"):
        try:
            return json.loads(t["layout_json"])
        except Exception:
            return []
    return []


# ── Sequences (auto barcode numbers) ──────────────────────────
def list_sequences():
    try:
        return db.fetchall("SELECT * FROM barcode_sequences ORDER BY prefix") or []
    except Exception:
        return []


def next_code(prefix):
    """Return next code like PRD000001 and advance the counter."""
    seq = db.fetchone("SELECT * FROM barcode_sequences WHERE prefix=?", (prefix,))
    if not seq:
        db.execute("INSERT INTO barcode_sequences (prefix, next_number, number_length) "
                   "VALUES (?,1,6)", (prefix,))
        seq = db.fetchone("SELECT * FROM barcode_sequences WHERE prefix=?", (prefix,))
    n = seq["next_number"]
    length = seq["number_length"]
    code = f"{prefix}{str(n).zfill(length)}"
    db.execute("UPDATE barcode_sequences SET next_number=next_number+1 WHERE prefix=?",
               (prefix,))
    return code


# ── Printers ──────────────────────────────────────────────────
PRINTER_BRANDS = ["Generic", "Zebra", "TSC", "XPrinter", "Honeywell", "Brother", "Epson"]


def list_printers():
    printers = []
    try:
        import win32print
        for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
            printers.append(p[2])
    except Exception:
        pass
    return printers or ["Default Printer", "Microsoft Print to PDF"]


# ── Products for batch printing ───────────────────────────────
def products_for_print(category_id=None):
    """Products with everything a label field can show (category, brand,
    cost…). Falls back to the basic columns on older databases."""
    params = (category_id,) if category_id else ()
    where = " WHERE p.is_active=1" + (" AND p.category_id=?" if category_id else "")
    rich = ("SELECT p.*, ISNULL(p.barcode,'') AS barcode, "
            "ISNULL(p.stock_quantity,0) AS stock_quantity, "
            "c.category_name_en AS category_name "
            "FROM products p LEFT JOIN product_categories c "
            "ON c.category_id = p.category_id" + where + " ORDER BY p.product_name_en")
    try:
        return db.fetchall(rich, params) or []
    except Exception:
        pass
    sql = ("SELECT product_id, product_code, product_name_en, "
           "ISNULL(barcode,'') AS barcode, unit_price, "
           "ISNULL(stock_quantity,0) AS stock_quantity FROM products p" + where +
           " ORDER BY product_name_en")
    try:
        return db.fetchall(sql, params) or []
    except Exception:
        return []


# ── Batch label PDF ───────────────────────────────────────────
def render_labels_pdf(template, items, output_path):
    """
    items: list of dicts with keys matching label fields, plus
           'barcode_value', 'copies'. Renders to a PDF (thermal = one
           label per page; a4sheet = grid).
    """
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from modules.barcode_gen import render_barcode
    from PIL import Image
    import tempfile

    fmt = template.get("barcode_type", "code128")
    lw = float(template.get("label_width_mm", 50))
    lh = float(template.get("label_height_mm", 25))
    layout = []
    if template.get("layout_json"):
        try:
            layout = json.loads(template["layout_json"])
        except Exception:
            layout = []

    # expand copies
    expanded = []
    for it in items:
        for _ in range(int(it.get("copies", 1) or 1)):
            expanded.append(it)

    from reportlab.pdfbase.pdfmetrics import stringWidth

    def _fit(txt, font, size, max_w):
        """Trim text with … so it never runs past its box / the label."""
        txt = str(txt)
        if stringWidth(txt, font, size) <= max_w:
            return txt
        while txt and stringWidth(txt + "…", font, size) > max_w:
            txt = txt[:-1]
        return txt + "…" if txt else ""

    def draw_label(c, ox, oy, item):
        # Designer stores x / y / w in MILLIMETRES from the label's top-left
        # (canvas = mm × PXMM), so the PDF uses the same numbers 1:1.
        if template.get("show_border", 1):
            c.setLineWidth(0.3)
            c.rect(ox, oy, lw * mm, lh * mm)
        els = layout if layout else _default_label_layout(template)
        tmp_imgs = []
        top = oy + lh * mm
        for el in els:
            x = float(el.get("x", 2) or 0)
            y = float(el.get("y", 2) or 0)
            w = float(el.get("w", 30) or 30)
            w = max(4.0, min(w, lw - x))                  # keep inside label
            ex = ox + x * mm
            ey = top - y * mm
            key = el.get("key")
            if key in ("barcode", "qr"):
                val = str(item.get("barcode_value") or item.get("product_code") or "")
                if not val:
                    continue
                if key == "qr":
                    side = min(w, lh - y) * mm
                    img = render_barcode(val, "qr", 300, 300)
                    bw, bh = side, side
                else:
                    bh_mm = float(el.get("bh") or 14)
                    bh_mm = max(4.0, min(bh_mm, lh - y - 0.5))
                    img = render_barcode(val, fmt, 600, 200)
                    bw, bh = w * mm, bh_mm * mm
                if img:
                    tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    img.save(tf.name); tf.close(); tmp_imgs.append(tf.name)
                    c.drawImage(tf.name, ex, ey - bh, bw, bh,
                                preserveAspectRatio=True, anchor="nw")
            else:
                txt = _field_value(key, item, el)
                if txt in (None, ""):
                    continue
                font = "Helvetica-Bold" if el.get("bold") else "Helvetica"
                size = max(5, int(float(el.get("font", 8) or 8)))
                if key == "product_name_ar" or any("\u0600" <= ch <= "\u06FF" for ch in str(txt)):
                    try:
                        from modules import pdf_invoice as _pi
                        _pi._register_fonts()
                        font = _pi._AR_FONT
                        txt = _pi._shape_arabic(str(txt))
                    except Exception:
                        pass
                # designer draws text vertically centred in its row
                row_mm = max(8.0, size * 0.3528 * 1.25)
                base = ey - row_mm / 2 * mm - size * 0.3528 * mm * 0.35
                c.setFont(font, size)
                txt = _fit(txt, font, size, w * mm - 1 * mm)
                al = el.get("align") or ("right" if key in ("product_name_ar", "unit_ar",
                                                              "offer_text_ar") else "left")
                if al == "center":
                    c.drawCentredString(ex + w * mm / 2, base, txt)
                elif al == "right":
                    c.drawRightString(ex + w * mm - 0.5 * mm, base, txt)
                else:
                    c.drawString(ex + 0.5 * mm, base, txt)
                if key == "old_price" and txt:          # 'was' price: struck through
                    tw = stringWidth(txt, font, size)
                    x0 = (ex + w * mm / 2 - tw / 2) if al == "center" else \
                         (ex + w * mm - 0.5 * mm - tw) if al == "right" else ex + 0.5 * mm
                    c.setLineWidth(0.6)
                    c.line(x0, base + size * 0.3, x0 + tw, base + size * 0.3)
        return tmp_imgs

    all_tmp = []
    if template.get("paper_mode") == "a4sheet":
        c = canvas.Canvas(output_path, pagesize=A4)
        PW, PH = A4
        margin = float(template.get("margin_mm", 5)) * mm
        gx = float(template.get("gap_x_mm", 2)) * mm
        gy = float(template.get("gap_y_mm", 2)) * mm
        cols = max(1, int(template.get("cols_per_sheet") or 3))
        rows = max(1, int(template.get("rows_per_sheet") or 8))
        # the sheet must fit the paper: a 3 × 70 mm sheet is exactly 210 mm
        # wide, so a margin there would push the 3rd column off the page —
        # shrink the margins (centre the grid) instead
        need_w = cols * lw * mm + (cols - 1) * gx
        need_h = rows * lh * mm + (rows - 1) * gy
        mx = max(0.0, min(margin, (PW - need_w) / 2.0))
        my = max(0.0, min(margin, (PH - need_h) / 2.0))
        i = 0
        while i < len(expanded):
            for r in range(rows):
                for col in range(cols):
                    if i >= len(expanded):
                        break
                    ox = mx + col * (lw * mm + gx)
                    oy = PH - my - (r + 1) * lh * mm - r * gy
                    all_tmp += draw_label(c, ox, oy, expanded[i])
                    i += 1
            c.showPage()
        c.save()
    else:
        # thermal: one label per page sized to the label
        c = canvas.Canvas(output_path, pagesize=(lw * mm, lh * mm))
        for it in expanded:
            all_tmp += draw_label(c, 0, 0, it)
            c.showPage()
        c.save()

    for f in all_tmp:
        try:
            os.remove(f)
        except Exception:
            pass
    return output_path


def starter_label_layout(lw=50.0, lh=25.0):
    """Name · price · barcode placed to fit a label of lw × lh mm
    (x / y / w in mm from the label's top-left, like the designer)."""
    lw, lh = float(lw or 50), float(lh or 25)
    small = lh < 22 or lw < 35
    fs = 6 if small else 8
    price_y = 5.0 if small else 6.0
    bar_y = 10.0 if small else 12.0
    bh = max(5.0, lh - bar_y - 1.5)
    return [
        {"id": 1, "key": "product_name", "label": "Product Name", "x": 1.5, "y": 0.5,
         "w": lw - 3, "h": 8, "font": fs, "bold": True},
        {"id": 2, "key": "selling_price", "label": "Selling Price", "x": 1.5, "y": price_y,
         "w": lw - 3, "h": 8, "font": fs + 1, "bold": True},
        {"id": 3, "key": "barcode", "label": "Barcode", "x": 1.5, "y": bar_y,
         "w": lw - 3, "h": 8, "bh": bh, "font": 8, "bold": False},
    ]


def _default_label_layout(template):
    return starter_label_layout(template.get("label_width_mm", 50),
                                template.get("label_height_mm", 25))


def _field_value(key, item, el):
    """Real product data for each designer field. Unknown/empty data prints
    nothing (never the field's name)."""
    def g(*keys):
        for k in keys:
            v = item.get(k)
            if v not in (None, ""):
                return v
        return ""

    def d(v):
        return str(v)[:10] if v else ""
    mapping = {
        "product_name": g("product_name_en"),
        "product_name_ar": g("product_name_ar"),
        "product_code": g("product_code"),
        "sku": g("sku", "product_code"),
        "selling_price": _money(g("unit_price")),
        "cost_price": _money(g("purchase_price")),
        "discount_price": _money(g("discount_price", "offer_price")) if g("discount_price", "offer_price") not in ("", None) else "",
        "currency": g("currency") or "SAR",
        "quantity": g("stock_quantity"),
        "category": g("category_name", "category_name_en"),
        "brand": g("brand_name", "brand"),
        "batch": g("batch_number", "batch"),
        "serial": g("serial_number", "serial"),
        "warehouse": g("warehouse_name", "warehouse"),
        "rack": g("rack_number", "rack_location", "rack"),
        "supplier": g("supplier_name", "supplier_name_en"),
        "mfg_date": d(g("mfg_date", "manufacture_date")),
        "exp_date": d(g("exp_date", "expiry_date")),
        "barcode_value": g("barcode_value"),
        "system_barcode": g("system_barcode"),          # v6.9.5: the 5-digit number
        "manual_barcode": g("manual_barcode"),          # the packet barcode
        "unit": g("unit_name", "unit_of_measure_en"),
        "unit_ar": g("unit_name_ar"),
        # the price the customer pays NOW: the offer price while an offer runs
        # (the normal price then prints in 'Old Price', struck through)
        "price_vat": _money(g("offer_price", "price_vat", "unit_price")),
        "offer_text": g("offer_text"),
        "offer_text_ar": g("offer_text_ar"),
        "offer_price": _money(g("offer_price")) if g("offer_price") not in ("", None) else "",
        "old_price": _money(g("old_price")) if g("old_price") not in ("", None) else "",
        "vat_note": ("Price incl. %g%% VAT" % float(g("vat_rate") or 15)) if g("price_vat") else "",
        "company_name": g("company_name"),
        "custom_text": el.get("label", ""),
        "text_label": el.get("text") or el.get("label", ""),
    }
    return mapping.get(key, "")


def _money(v):
    try:
        return f"SAR {float(v):,.2f}"
    except Exception:
        return ""


# Toolbox for the designer palette
TOOLBOX = {
    "Product Info": [
        ("product_name", "Product Name"), ("product_name_ar", "Product Name (Arabic)"),
        ("product_code", "Product Code"),
        ("sku", "SKU"), ("barcode", "Barcode"), ("qr", "QR Code"),
        ("system_barcode", "System Barcode No."), ("manual_barcode", "Manual Barcode No."),
        ("category", "Category"), ("brand", "Brand"),
        ("batch", "Batch Number"), ("serial", "Serial Number"),
    ],
    "Pricing": [
        ("price_vat", "Price incl. VAT"), ("selling_price", "Selling Price"),
        ("unit", "Unit (PCs / Box…)"), ("unit_ar", "Unit (Arabic)"),
        ("offer_text", "Offer (HALF PRICE…)"), ("offer_text_ar", "Offer (Arabic)"),
        ("offer_price", "Offer Price"), ("old_price", "Old Price (struck)"),
        ("vat_note", "'incl. 15% VAT' note"),
        ("cost_price", "Cost Price"), ("discount_price", "Discount Price"),
        ("currency", "Currency"),
    ],
    "Inventory": [
        ("warehouse", "Warehouse"), ("rack", "Rack Number"),
        ("quantity", "Quantity"),
    ],
    "Custom": [
        ("mfg_date", "Mfg Date"), ("exp_date", "Expiry Date"),
        ("supplier", "Supplier"), ("company_name", "Shop Name"),
        ("text_label", "Custom Text"),
    ],
}


# ── Ready-made label designs (added once; the user may edit / delete) ──
def _el(i, key, label, x, y, w, font=8, bold=False, align="left", bh=None):
    e = {"id": i, "key": key, "label": label, "x": x, "y": y, "w": w, "h": 8,
         "font": font, "bold": bold, "align": align}
    if bh is not None:
        e["bh"] = bh
    return e


READY_DESIGNS = [
    # name, width, height, sheet?, elements
    ("Price tag 40×30 · big price", 40, 30, False, [
        # text sits centred in an 8 mm row (as on the designer canvas)
        _el(1, "product_name", "Product Name", 1, 0, 38, 7, True, "center"),
        _el(2, "price_vat", "Price incl. VAT", 1, 5, 38, 15, True, "center"),
        _el(3, "unit", "Unit", 1, 9.3, 38, 6, False, "center"),
        _el(4, "barcode", "Barcode", 2, 15, 36, bh=14.5)]),
    ("Shelf 58×40 · Arabic + offer", 58, 40, False, [
        _el(1, "product_name", "Product Name", 1.5, 0.5, 55, 8, True),
        _el(2, "product_name_ar", "Product Name (Arabic)", 1.5, 5, 55, 8, False, "right"),
        _el(3, "offer_text", "Offer", 1.5, 10, 30, 8, True),
        _el(4, "old_price", "Old Price", 32, 10, 24.5, 7, False, "right"),
        _el(5, "price_vat", "Price incl. VAT", 1.5, 14.5, 36, 15, True),
        _el(6, "unit", "Unit", 38, 16, 18.5, 7, False, "right"),
        _el(7, "barcode", "Barcode", 1.5, 23, 55, bh=15.5)]),
    ("Small 38×25 · name + barcode", 38, 25, False, [
        _el(1, "product_name", "Product Name", 1, 0.5, 36, 6, True, "center"),
        _el(2, "price_vat", "Price incl. VAT", 1, 4.5, 36, 8, True, "center"),
        _el(3, "barcode", "Barcode", 1.5, 9.5, 35, bh=14.5)]),
    ("A4 sheet 3×8 · 70×37", 70, 37, True, [
        _el(1, "product_name", "Product Name", 3, 1, 64, 9, True),
        _el(2, "product_name_ar", "Product Name (Arabic)", 3, 6, 64, 9, False, "right"),
        _el(3, "price_vat", "Price incl. VAT", 3, 11.5, 40, 14, True),
        _el(4, "unit", "Unit", 44, 13, 23, 8, False, "right"),
        _el(5, "barcode", "Barcode", 6, 20, 58, bh=15)]),
]


def ensure_ready_designs():
    """Add the ready-made designs once (Settings flag), so a new shop can
    print good labels straight away. Never re-adds a design the user
    deleted. Returns the number added."""
    try:
        from config import settings as cfg
        if cfg.flag("label_ready_designs_v522", False):
            return 0
    except Exception:
        return 0
    if not tables_ready():
        return 0
    have = {str(t.get("template_name") or "") for t in list_templates()}
    n = 0
    for name, w, h, sheet, els in READY_DESIGNS:
        if name in have:
            continue
        try:
            create_template({"template_name": name, "barcode_type": "code128",
                             "label_width_mm": w, "label_height_mm": h,
                             "paper_mode": "a4sheet" if sheet else "thermal",
                             "cols_per_sheet": 3 if sheet else 1,
                             "rows_per_sheet": 8 if sheet else 1,
                             "gap_x_mm": 0 if sheet else 2, "gap_y_mm": 0 if sheet else 2,
                             "margin_mm": 5 if sheet else 0, "dpi": 203,
                             "layout_json": json.dumps(els)})
            n += 1
        except Exception:
            pass
    try:
        cfg.set("label_ready_designs_v522", True)
        cfg.save_settings()
    except Exception:
        pass
    return n
