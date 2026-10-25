# ============================================================
# DayBill ERP - EAN-13 Barcode Generator
# Saudi GS1 prefix 6281 | Auto check digit | PNG output
# ============================================================

SAUDI_GS1_PREFIX = "6281"   # registered Saudi Arabia GS1 prefix


def ean13_check_digit(digits_12: str) -> int:
    """Compute the EAN-13 check digit from 12 data digits."""
    total = 0
    for i, ch in enumerate(digits_12):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return (10 - (total % 10)) % 10


def generate_ean13(product_id: int, unit_sequence: int = 1) -> str:
    """
    Generate a unique EAN-13 barcode for a product unit.
    Format: 6281 (4) + product_id (5) + unit_seq (3) + check (1) = 13 digits
    """
    prod = f"{int(product_id):05d}"
    unit = f"{int(unit_sequence):03d}"
    digits_12 = SAUDI_GS1_PREFIX + prod + unit
    check = ean13_check_digit(digits_12)
    return digits_12 + str(check)


def validate_ean13(barcode: str) -> bool:
    """Return True if the barcode is a valid EAN-13."""
    if not barcode or len(barcode) != 13 or not barcode.isdigit():
        return False
    return int(barcode[-1]) == ean13_check_digit(barcode[:12])


def barcode_to_image(barcode_str: str, width: int = 300, height: int = 100):
    """
    Render an EAN-13 barcode as a PIL Image.
    Returns None gracefully if python-barcode or pillow is missing.
    """
    try:
        import barcode as pybarcode
        from barcode.writer import ImageWriter
        import io
        from PIL import Image

        ean = pybarcode.get("ean13", barcode_str[:12], writer=ImageWriter())
        buf = io.BytesIO()
        ean.write(buf, options={"module_height": 15, "text_distance": 1,
                                "quiet_zone": 2, "font_size": 8})
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        return img
    except Exception:
        pass

    # Fallback: draw bars manually with Pillow only
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        # Encode digits to bars (simplified EAN-13 pattern)
        bars = _encode_ean13_bars(barcode_str)
        bar_w = max(1, (width - 20) // len(bars))
        x = 10
        for bar in bars:
            if bar:
                draw.rectangle([x, 5, x + bar_w - 1, height - 18], fill="black")
            x += bar_w

        # Draw digits below
        draw.text((10, height - 14), barcode_str, fill="black")
        return img
    except Exception:
        return None


def _encode_ean13_bars(barcode: str):
    """Return a list of booleans (True=black bar) for an EAN-13 string."""
    # L-code patterns (odd parity)
    L = {0: "0001101", 1: "0011001", 2: "0010011", 3: "0111101", 4: "0100011",
         5: "0110001", 6: "0101111", 7: "0111011", 8: "0110111", 9: "0001011"}
    # G-code patterns (even parity)
    G = {0: "0100111", 1: "0110011", 2: "0011011", 3: "0100001", 4: "0011101",
         5: "0111001", 6: "0000101", 7: "0010001", 8: "0001001", 9: "0010111"}
    # R-code patterns (right half)
    R = {0: "1110010", 1: "1100110", 2: "1101100", 3: "1000010", 4: "1011100",
         5: "1001110", 6: "1010000", 7: "1000100", 8: "1001000", 9: "1110100"}
    # First digit parity table
    parity = {0: "LLLLLL", 1: "LLGLGG", 2: "LLGGLG", 3: "LLGGGL", 4: "LGLLGG",
              5: "LGGLLG", 6: "LGGGLL", 7: "LGLGLG", 8: "LGLGGL", 9: "LGGLGL"}

    digits = [int(d) for d in barcode]
    first = digits[0]
    left = digits[1:7]
    right = digits[7:13]
    par = parity[first]

    bits = "101"  # start guard
    for i, d in enumerate(left):
        bits += L[d] if par[i] == "L" else G[d]
    bits += "01010"  # middle guard
    for d in right:
        bits += R[d]
    bits += "101"  # end guard

    return [b == "1" for b in bits]


def print_barcode_label(barcode_str: str, product_name: str, price: float,
                        output_path: str) -> str:
    """
    Generate a printable barcode label PDF (57mm × 32mm thermal label size).
    Returns output_path.
    """
    try:
        from reportlab.lib.pagesizes import mm
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        import io

        W, H = 57 * mm, 32 * mm
        c = canvas.Canvas(output_path, pagesize=(W, H))

        # Product name
        c.setFont("Helvetica-Bold", 7)
        name = product_name[:30]
        c.drawCentredString(W / 2, H - 8, name)

        # Barcode image
        img = barcode_to_image(barcode_str, width=180, height=60)
        if img:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(ImageReader(buf), 5 * mm, 8 * mm, W - 10 * mm, 16 * mm)

        # Price
        c.setFont("Helvetica-Bold", 9)
        from modules import country as _K
        c.drawCentredString(W / 2, 3 * mm, _K.money(price, sym=True))

        c.save()
        return output_path
    except Exception as e:
        raise RuntimeError(f"Label generation failed: {e}")


# ── Self-test ──────────────────────────────────────────────────
if __name__ == "__main__":
    bc = generate_ean13(42, 1)
    print(f"EAN-13 for product 42 unit 1: {bc}")
    print(f"Valid: {validate_ean13(bc)}")
    bc2 = generate_ean13(42, 2)
    print(f"EAN-13 for product 42 unit 2: {bc2}")
    assert validate_ean13(bc) and validate_ean13(bc2)
    print("Barcode engine OK ✅")


# ── Universal multi-format renderer (Code128 / EAN-13 / QR) ────────
def render_barcode(value: str, fmt: str = "code128",
                   width: int = 300, height: int = 100):
    """
    Render any supported barcode/QR as a PIL Image.
    fmt: 'code128' | 'ean13' | 'qr'. Returns None if libs missing.
    """
    fmt = (fmt or "code128").lower()
    try:
        if fmt == "qr":
            import qrcode
            qr = qrcode.QRCode(box_size=4, border=1)
            qr.add_data(value)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            side = min(width, height)
            return img.resize((side, side))
        else:
            import barcode as pybarcode
            from barcode.writer import ImageWriter
            import io
            from PIL import Image
            name = "ean13" if fmt == "ean13" else "code128"
            data = value[:12] if fmt == "ean13" else value
            if name == "ean13" and not (validate_ean13(value) or
                                        (len(value) == 12 and value.isdigit())):
                # not a real EAN-13: printing it as EAN would silently change
                # the digits and the label wouldn't scan back to this product
                name, data = "code128", value
            obj = pybarcode.get(name, data, writer=ImageWriter())
            buf = io.BytesIO()
            obj.write(buf, options={"module_height": 14, "text_distance": 5,
                                    "quiet_zone": 2, "font_size": 9})
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
            # scale PROPORTIONALLY (stretching squashed the digits into the
            # bars and could make scanners misread), then pad to the size
            scale = min(width / img.width, height / img.height)
            nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
            img = img.resize((nw, nh), Image.LANCZOS)
            canvas_img = Image.new("RGB", (width, height), "white")
            canvas_img.paste(img, ((width - nw) // 2, (height - nh) // 2))
            return canvas_img
    except Exception:
        # fall back to the EAN-13 manual drawer for linear types
        if fmt in ("code128", "ean13"):
            return barcode_to_image(value, width, height)
        return None


SUPPORTED_FORMATS = [("code128", "Code 128"), ("ean13", "EAN-13"), ("qr", "QR Code")]


# ─────────────────────────────────────────────────────────────
# Settings-driven unique barcode (used by every "Generate" button)
# Settings ▸ Barcode: Product Prefix (digits), Barcode Length (5-14),
# Check Digit Enabled. Default (v6.9.5) = a 5-digit shop number 10001…
#
# v6.9.5 SYSTEM BARCODE: every product also has its own 5-digit number
# made by DayBill (products.system_barcode, 10001 … 99999), apart from
# the barcode typed / scanned from the packet (products.barcode). Both
# scan in every barcode box. new_system_barcode() gives the next free one.
# ─────────────────────────────────────────────────────────────
def _mod10_check(body: str) -> int:
    """GS1 mod-10 check digit (works for EAN-8, UPC-A, EAN-13, ITF-14):
    weights 3,1,3,1… counted from the RIGHT of the data digits."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10


def barcode_rules():
    try:
        from config import settings as cfg
        prefix = "".join(ch for ch in str(cfg.get("barcode_prefix", "") or "") if ch.isdigit())
        length = int(float(cfg.get("barcode_length", 5) or 5))
        check = cfg.flag("barcode_check_digit", True)
    except Exception:
        prefix, length, check = "", 5, False
    length = max(5, min(14, length))
    if length < 8:
        check = False                  # short in-store number: plain 5 digits, no check digit
    if not prefix:
        prefix = SAUDI_GS1_PREFIX if length >= 12 else ""
    prefix = prefix[:max(0, length - 5)]          # leave room for a serial
    return prefix, length, check


def _short_codes_in_use(length):
    """Every barcode (and product code — a code typed in a barcode box finds
    its product too) of exactly `length` characters."""
    used = set()
    try:
        from config.database import db
        pat = "_" * length
        for sql in ("SELECT barcode FROM product_units WHERE barcode LIKE ?",
                    "SELECT barcode FROM product_unit_barcodes WHERE barcode LIKE ?",
                    "SELECT barcode FROM products WHERE barcode LIKE ?",
                    "SELECT system_barcode AS barcode FROM products WHERE system_barcode LIKE ?",
                    "SELECT product_code AS barcode FROM products WHERE product_code LIKE ?"):
            try:
                for r in db.fetchall(sql, (pat,)) or []:
                    v = str(r.get("barcode") or "").strip()
                    if len(v) == length:
                        used.add(v)
            except Exception:
                pass
    except Exception:
        pass
    return used


def _next_short_code(prefix, length, exclude):
    """Short codes (5 digits by default) are given in order: 10001,
    10002, … — the next number after the highest one in use, never one
    already used by any product, unit, extra or system barcode."""
    used = _short_codes_in_use(length) | {x for x in exclude if len(x) == length}
    free = length - len(prefix)
    lo = int(prefix + "1" + "0" * (free - 1)) if free > 0 else 0   # 10000 for 5 digits
    hi = int(prefix + "9" * free) if free > 0 else 0              # 99999
    # Settings ▸ Barcode ▸ First Auto Barcode (e.g. 543210): numbers start there
    try:
        from config import settings as cfg
        st = int(float(str(cfg.get("barcode_start", "") or 0)))
    except Exception:
        st = 0
    if lo < st <= hi:
        lo = st - 1
    nums = [int(u) for u in used if u.isdigit() and u.startswith(prefix) and lo <= int(u) <= hi]
    n = max(nums) + 1 if nums else lo + 1
    for cand in list(range(n, hi + 1)) + list(range(lo + 1, n)):   # wrap round to fill gaps
        code = str(cand)
        if code not in used and not _barcode_taken(code):
            return code
    raise RuntimeError("No free %d-digit barcode left — set a longer Barcode Length "
                       "in Settings ▸ Barcode." % length)


def _barcode_taken(code: str) -> bool:
    try:
        from config.database import db
        for sql in ("SELECT COUNT(*) FROM product_units WHERE barcode=?",
                    "SELECT COUNT(*) FROM product_unit_barcodes WHERE barcode=?",
                    "SELECT COUNT(*) FROM products WHERE barcode=?",
                    "SELECT COUNT(*) FROM products WHERE system_barcode=?",
                    "SELECT COUNT(*) FROM products WHERE product_code=?"):
            try:
                if db.execute_scalar(sql, (code,)):
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def new_unique_barcode(exclude=()) -> str:
    """A fresh barcode following Settings ▸ Barcode, verified unused in the
    database and not in `exclude` (codes already typed on the open form)."""
    import random
    prefix, length, check = barcode_rules()
    data_len = length - (1 if check else 0)
    free = data_len - len(prefix)
    exclude = {str(x) for x in exclude if x}
    if length < 8:                     # 6-digit in-store codes, in order, always unique
        return _next_short_code(prefix, length, exclude)
    for _ in range(200):
        body = prefix + "".join(str(random.randint(0, 9)) for _ in range(free))
        code = body + (str(_mod10_check(body)) if check else "")
        if code not in exclude and not _barcode_taken(code):
            return code
    body = prefix + str(random.randint(10 ** (free - 1), 10 ** free - 1))
    return body + (str(_mod10_check(body)) if check else "")


# ── v6.9.5: the product's own 5-digit system barcode ───────────────
SYSTEM_LENGTH = 5


_HAS_SYS = {}


def has_system_column():
    """True once the v6.9.5 update added products.system_barcode."""
    if _HAS_SYS.get("yes"):
        return True
    try:
        from config.database import db
        ok = db.execute_scalar("SELECT COL_LENGTH('products','system_barcode')") is not None
    except Exception:
        ok = False
    if ok:
        _HAS_SYS["yes"] = True
    return ok


def new_system_barcode(exclude=()) -> str:
    """The next free 5-digit system barcode: 10001, 10002 … (Settings ▸
    Barcode ▸ First System Barcode can move the start), never a number
    already used as any barcode or product code."""
    exclude = {str(x) for x in exclude if x}
    try:
        from config import settings as cfg
        st = int(float(str(cfg.get("system_barcode_start", "") or 0)))
    except Exception:
        st = 0
    lo, hi = 10 ** (SYSTEM_LENGTH - 1), 10 ** SYSTEM_LENGTH - 1
    used = _short_codes_in_use(SYSTEM_LENGTH) | {x for x in exclude if len(x) == SYSTEM_LENGTH}
    first = st if lo < st <= hi else lo + 1
    nums = [int(u) for u in used if u.isdigit() and first <= int(u) <= hi]
    n = max(nums) + 1 if nums else first
    for cand in list(range(n, hi + 1)) + list(range(first, n)):
        code = str(cand)
        if code not in used and not _barcode_taken(code):
            return code
    raise RuntimeError("All 5-digit system barcodes (10001 – 99999) are used.")


def sys_select(alias="p"):
    """SQL for the system barcode in a product SELECT ('' before the update)."""
    return ("ISNULL(%s.system_barcode,'') AS system_barcode" % alias) if has_system_column() \
        else "'' AS system_barcode"
