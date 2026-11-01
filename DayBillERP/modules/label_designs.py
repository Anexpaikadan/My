# ============================================================
# DayBill ERP - ready barcode label designs (v7.9.7)
# ------------------------------------------------------------
# A gallery of full label designs — Modern, Classic, Minimal, Big price,
# Expiry date, Barcode, Shelf, Shelf offer, Mini, Jewellery — each drawn
# once at a base size and SCALED to any label size:
#
#   layout(design, w, h)             elements for a w × h mm label
#   scale_layout(els, ow, oh, w, h)  every element moved / resized / its
#                                    font scaled when the label size changes
#   SIZES                            the usual label sizes (default first)
#
# Element units are millimetres from the label's top-left (like the
# designer). Besides the data fields a design may use:
#   key "box"    a filled / outlined rectangle (hh = height, fill, stroke,
#                lw = line width in points, radius in mm)
#   key "hline"  a line (lw, color)
# and text options: color, bg (a band behind the text), serif, prefix,
# rh (row height; the text is centred in it).
# ============================================================
import copy

# (label, width, height, sheet?) — the first one is the default size
SIZES = [
    ("50 × 30 mm", 50, 30, False), ("50 × 25 mm", 50, 25, False),
    ("40 × 30 mm", 40, 30, False), ("38 × 25 mm", 38, 25, False),
    ("30 × 20 mm", 30, 20, False), ("58 × 40 mm", 58, 40, False),
    ("60 × 40 mm", 60, 40, False), ("75 × 50 mm", 75, 50, False),
    ("80 × 35 mm · shelf", 80, 35, False), ("100 × 50 mm", 100, 50, False),
    ("A4 sheet 3 × 8 (70 × 37 mm)", 70, 37, True),
]
DEFAULT_SIZE = SIZES[0][0]

INK, MUTED, BRAND, SALE = "#111827", "#4B5563", "#1D4ED8", "#DC2626"


def _t(key, x, y, w, rh, font, bold=False, align="left", **kw):
    e = {"key": key, "x": x, "y": y, "w": w, "rh": rh, "font": font, "bold": bold, "align": align}
    e.update(kw)
    return e


def _box(x, y, w, hh, fill="", stroke="", lw=0.4, radius=0.0):
    return {"key": "box", "x": x, "y": y, "w": w, "hh": hh, "fill": fill, "stroke": stroke,
            "lw": lw, "radius": radius}


def _line(x, y, w, lw=0.3, color=INK):
    return {"key": "hline", "x": x, "y": y, "w": w, "lw": lw, "color": color}


def _bar(x, y, w, bh):
    return {"key": "barcode", "x": x, "y": y, "w": w, "bh": bh}


# name → (description, base width, base height, own frame?, elements)
# Every design carries the shop name; the barcode prints the short system
# barcode (fewer, wider bars → scans best) — Properties ▸ Barcode prints.
def _shop(x, y, w, rh, font=5, align="right", **kw):
    kw.setdefault("color", MUTED)
    return _t("company_name", x, y, w, rh, font, False, align, **kw)


DESIGNS = {
    "Modern": ("Dark name band, big price, shop name, barcode", 50, 30, False, [
        _box(0, 0, 50, 8, fill=INK),
        _t("product_name", 2, 0, 46, 8, 8, True, color="#FFFFFF"),
        _t("price_vat", 2, 8.4, 30, 7.4, 13, True),
        _shop(31, 8.6, 17, 3.5),
        _t("unit", 31, 12, 17, 3.5, 6, align="right", color=MUTED),
        _bar(2, 16.2, 46, 13.4)]),
    "Classic": ("Double frame, serif type, shop name on top", 50, 30, True, [
        _box(0.7, 0.7, 48.6, 28.6, stroke=INK, lw=0.8),
        _box(1.7, 1.7, 46.6, 26.6, stroke=INK, lw=0.25),
        _shop(3, 2.1, 44, 3.6, 5.5, "center", serif=True),
        _t("product_name", 3, 5.5, 44, 5, 8, True, "center", serif=True),
        _line(12, 10.7, 26, 0.4),
        _t("price_vat", 3, 11, 44, 6, 12, True, "center", serif=True),
        _bar(5, 17.4, 40, 10.6)]),
    "Minimal": ("Name, price, barcode and a small shop name", 50, 25, False, [
        _t("product_name", 1.5, 0.3, 32, 5, 7, True),
        _shop(34, 0.3, 14.5, 5),
        _t("price_vat", 1.5, 5.4, 47, 5.6, 11, True),
        _bar(1.5, 11.2, 47, 13.5)]),
    "Big price": ("Huge price for shelves and fresh food", 50, 30, False, [
        _t("product_name", 1.5, 0.3, 47, 4.3, 6, True, "center"),
        _t("price_vat", 1, 4.3, 48, 11, 21, True, "center"),
        _t("unit", 1.5, 15, 23, 3.3, 6, False, "left", color=MUTED),
        _shop(25, 15, 23.5, 3.3),
        _bar(2, 18.6, 46, 11)]),
    "Expiry date": ("EXP badge, MFG date, batch, barcode", 50, 30, False, [
        _t("product_name", 1.5, 0.3, 31, 5, 7, True),
        _shop(33, 0.3, 15.5, 5),
        _t("exp_date", 1.5, 5.6, 24, 5, 7, True, color="#FFFFFF", bg=INK, prefix="EXP  "),
        _t("mfg_date", 26.5, 5.6, 22, 5, 6, False, "right", prefix="MFG  "),
        _t("batch", 1.5, 11, 25, 4.5, 6, False, color=MUTED, prefix="Batch  "),
        _t("price_vat", 26.5, 10.6, 22, 5, 8, True, "right"),
        _bar(1.5, 16.2, 47, 13.4)]),
    "Barcode": ("Framed barcode with code, price and shop name", 50, 25, True, [
        _t("product_name", 1.5, 0, 31, 4.5, 6, True),
        _shop(33, 0, 15.5, 4.5),
        _box(1.5, 4.6, 47, 15.2, stroke=INK, lw=0.5, radius=1.5),
        _bar(3, 5.3, 44, 13.8),
        _t("product_code", 1.5, 20.2, 23, 4.3, 6, False, color=MUTED, prefix="Code "),
        _t("price_vat", 25, 20.2, 23.5, 4.3, 7, True, "right")]),
    "Shelf": ("Shelf edge: colour stripe, EN + AR name, big price", 80, 35, True, [
        _box(0, 0, 80, 35, stroke=INK, lw=0.3),
        _box(0, 0, 4, 35, fill=BRAND),
        _t("product_name", 6, 1, 72, 6, 9, True),
        _t("product_name_ar", 6, 7, 72, 6, 9, False, "right"),
        _t("price_vat", 6, 13.2, 46, 11, 22, True),
        _t("unit", 52, 16.8, 26, 5, 7, False, "right", color=MUTED),
        _line(6, 25, 72, 0.3),
        _bar(6, 25.6, 42, 9),
        _shop(50, 26.3, 28, 4, 6),
        _t("product_code", 50, 30.4, 28, 4, 5.5, False, "right", color=MUTED, prefix="Code ")]),
    "Shelf offer": ("Red offer band, old price struck, offer price", 80, 35, True, [
        _box(0, 0, 80, 35, stroke=SALE, lw=0.5),
        _box(0, 0, 80, 7, fill=SALE),
        _t("text_label", 2.5, 0, 50, 7, 9, True, color="#FFFFFF", text="SPECIAL OFFER"),
        _t("offer_text", 40, 0, 38, 7, 8, True, "right", color="#FFFFFF"),
        _t("product_name", 3, 8, 74, 6, 9, True),
        _t("old_price", 3, 14.6, 30, 6, 9, False),
        _t("price_vat", 32, 13.2, 46, 10, 20, True, "right", color=SALE),
        _bar(3, 24, 46, 10.4),
        _t("unit", 51, 25.6, 27, 4.4, 7, False, "right", color=MUTED),
        _shop(51, 30, 27, 4.4, 6)]),
    "Mini": ("Small labels: name, price, barcode, shop", 30, 20, False, [
        _t("product_name", 0.8, 0, 28.4, 3.6, 5, True, "center"),
        _t("price_vat", 0.8, 3.4, 28.4, 4, 7.5, True, "center"),
        _bar(1, 7.4, 28, 10),
        _shop(0.8, 17.5, 28.4, 2.4, 5, "center")]),
    "Jewellery": ("Thin frame, shop name, code + unit, barcode", 50, 25, True, [
        _box(0.6, 0.6, 48.8, 23.8, stroke=INK, lw=0.3, radius=2),
        _t("product_name", 2.5, 1, 45, 4.5, 7, True, "center", serif=True),
        _shop(2.5, 5.2, 45, 3, 5, "center", serif=True),
        _t("product_code", 2.5, 8.2, 22, 4, 6, False, prefix="Code "),
        _t("unit", 25.5, 8.2, 22, 4, 6, False, "right"),
        _t("price_vat", 2.5, 12, 45, 4.6, 9, True, "center", serif=True),
        _bar(4.5, 16.7, 41, 7.2)]),
}
for _d in DESIGNS.values():                     # short system barcode by default
    for _e in _d[4]:
        if _e["key"] == "barcode":
            _e.setdefault("source", "system")
DESIGN_NAMES = list(DESIGNS)
# designs that only work (and scan) from a minimum label size, mm
MIN_SIZE = {"Shelf": (58, 30), "Shelf offer": (58, 30)}


def sizes_for(design):
    """The SIZES this design is offered in (big enough to scan well)."""
    mw, mh = MIN_SIZE.get(design, (0, 0))
    return [s for s in SIZES if s[1] >= mw and s[2] >= mh]

_X = ("x", "w")
_Y = ("y", "bh", "hh", "rh")


def scale_layout(elements, ow, oh, w, h):
    """The elements of an ow × oh label placed on a w × h label: positions
    and sizes follow the new width / height, fonts follow the smaller of
    the two (so a wider label doesn't get taller letters)."""
    ow, oh, w, h = float(ow or 50), float(oh or 25), float(w or 50), float(h or 25)
    sx, sy = w / ow, h / oh
    sf = min(sx, sy)
    out = []
    for e in copy.deepcopy(elements or []):
        if "rh" not in e and e.get("key") not in ("barcode", "qr", "box", "hline"):
            e["rh"] = 8.0                       # older text rows were 8 mm
        for k in _X:
            if k in e:
                e[k] = round(float(e[k]) * sx, 2)
        for k in _Y:
            if k in e and e[k] not in (None, ""):
                e[k] = round(float(e[k]) * sy, 2)
        if "font" in e:
            e["font"] = max(4.0, round(float(e["font"]) * sf, 1))
        if "lw" in e:
            e["lw"] = max(0.15, round(float(e["lw"]) * sf, 2))
        if "radius" in e:
            e["radius"] = round(float(e["radius"]) * sf, 2)
        out.append(e)
    return out


def layout(design, w, h):
    """Elements of a gallery design for a w × h mm label (with ids / labels)."""
    _desc, bw, bh, _frame, els = DESIGNS.get(design) or DESIGNS["Modern"]
    out = scale_layout(els, bw, bh, w, h)
    for i, e in enumerate(out, 1):
        e["id"] = i
        e.setdefault("label", LABELS.get(e["key"], e["key"]))
        e.setdefault("h", e.get("rh", 8))
    return out


def own_frame(design):
    """True when the design draws its own border (the plain label border is off)."""
    return bool((DESIGNS.get(design) or DESIGNS["Modern"])[3])


LABELS = {"product_name": "Product Name", "product_name_ar": "Product Name (Arabic)",
          "price_vat": "Price incl. VAT", "unit": "Unit", "barcode": "Barcode",
          "exp_date": "Expiry Date", "mfg_date": "Mfg Date", "batch": "Batch Number",
          "product_code": "Product Code", "old_price": "Old Price", "offer_text": "Offer",
          "text_label": "Custom Text", "box": "Box", "hline": "Line",
          "company_name": "Shop Name"}


def size_of(label):
    return next((s for s in SIZES if s[0] == label), SIZES[0])


def template_data(name, design, size_label):
    """barcode_templates row for a design in a size (ready to create)."""
    _lbl, w, h, sheet = size_of(size_label)
    import json
    return {"template_name": name, "barcode_type": "code128",
            "label_width_mm": w, "label_height_mm": h,
            "paper_mode": "a4sheet" if sheet else "thermal",
            "cols_per_sheet": 3 if sheet else 1, "rows_per_sheet": 8 if sheet else 1,
            "gap_x_mm": 0 if sheet else 2, "gap_y_mm": 0 if sheet else 2,
            "margin_mm": 5 if sheet else 0, "dpi": 203,
            "show_border": 0 if own_frame(design) else 1,
            "layout_json": json.dumps(layout(design, w, h))}
