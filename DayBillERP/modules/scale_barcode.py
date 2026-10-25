# ============================================================
# DayBill ERP - Weighing-scale barcode decoder
# ------------------------------------------------------------
# Scales print a label whose barcode carries the item's PLU and
# either its WEIGHT or its PRICE. Standard GS1 in-store layout:
#
#     2 F  P P P P P  V V V V V  C      (13 digits, EAN-13)
#     │ │  └─ PLU ─┘  └ value ─┘  └ check digit
#     │ └ flag digit (0-9, set on the scale)
#     └ in-store prefix "2"
#
#   value = weight in grams  (1.234 kg -> 01234)   weight formats
#   value = price in halalas (5.00     -> 00500)   price formats
#
# Which one applies comes from PLU Manager ▸ Barcode format
# (settings key plu_barcode_format). Called ONLY after a normal
# barcode lookup failed, so real product barcodes starting with 2
# are never misread.
# ============================================================
from config import settings as cfg
from config.database import db

PREFIX = {"EAN13_WEIGHT_2": "2", "EAN13_PRICE_2": "2",
          "EAN13_WEIGHT_20": "20", "EAN13_PRICE_21": "21"}


def _check_ok(code):
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(code[:12]))
    return (10 - total % 10) % 10 == int(code[12])


def decode(code):
    """Returns dict(product=<row>, quantity=<float>, price=<float|None>,
    plu=<str>, kind='weight'|'price'|'plu') or None."""
    code = str(code or "").strip()
    if not cfg.flag("plu_enabled", True):      # Settings ▸ PLU Scale
        return None
    fmt = str(cfg.get("plu_barcode_format", "EAN13_WEIGHT_2") or "EAN13_WEIGHT_2")
    if not code.isdigit():
        return None
    if fmt == "PLU_ONLY":
        plu, value, kind = code, None, "plu"
    else:
        pre = PREFIX.get(fmt, "2")
        if len(code) != 13 or not code.startswith(pre) or not _check_ok(code):
            return None
        plu, value = code[2:7], int(code[7:12])
        kind = "price" if "PRICE" in fmt else "weight"
    try:
        rows = db.fetchall(
            "SELECT * FROM products WHERE ISNULL(is_weighed,0)=1 AND is_active=1 "
            "AND ISNULL(scale_plu,'')<>''") or []
    except Exception:
        return None
    try:
        want = int(plu)
    except ValueError:
        return None
    prod = None
    for r in rows:
        try:
            if int(str(r.get("scale_plu")).strip()) == want:
                prod = r
                break
        except (TypeError, ValueError):
            continue
    if not prod:
        return None
    unit_price = float(prod.get("unit_price") or 0)
    if kind == "weight":
        grams = value
        qty = grams / 1000.0
        if str(prod.get("weight_unit") or "kg").lower() in ("g", "gm", "gram", "grams"):
            qty = float(grams)
        return {"product": prod, "quantity": round(qty, 3), "price": None,
                "plu": plu, "kind": kind}
    if kind == "price":
        amount = value / 100.0
        qty = round(amount / unit_price, 3) if unit_price > 0 else 1.0
        return {"product": prod, "quantity": qty or 0.001, "price": None,
                "amount": amount, "plu": plu, "kind": kind}
    return {"product": prod, "quantity": 1.0, "price": None, "plu": plu, "kind": kind}


def line_values(hit, price_incl=True, vat_rate=0.0):
    """(quantity, unit_price or None) for a decoded scale label.

    Weight labels: the weighed quantity at the product's normal price.
    Price labels: the quantity is worked out from the price, and the unit
    price is set so the line comes to EXACTLY the amount printed on the
    label (scale prices include VAT; in 'price excludes VAT' mode the net
    is used so the total with VAT still equals the label)."""
    qty = float(hit.get("quantity") or 0) or 0.001
    if hit.get("kind") != "price" or not hit.get("amount"):
        return qty, None
    amount = float(hit["amount"])
    target = amount if price_incl or not vat_rate else amount / (1 + float(vat_rate) / 100.0)
    return qty, target / qty
