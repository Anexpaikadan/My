# ============================================================
# Saudi Arabia ERP - ZATCA QR Code Generator
# TLV (Tag-Length-Value) encoding per ZATCA specification
# Phase 1 compliant QR data
# ============================================================

import base64
import struct
import hashlib
from datetime import datetime


def _tlv_encode(tag: int, value: str) -> bytes:
    """Encode a single TLV field (a value is at most 255 bytes)."""
    encoded_value = str(value or "").encode("utf-8")
    if len(encoded_value) > 255:          # cut on a character boundary
        encoded_value = encoded_value[:255].decode("utf-8", "ignore").encode("utf-8")
    length = len(encoded_value)
    return bytes([tag, length]) + encoded_value


def generate_zatca_qr(
    seller_name: str,
    vat_number: str,
    invoice_datetime: str,   # ISO 8601: "2025-01-15T10:30:00Z"
    total_with_vat: float,
    vat_amount: float,
) -> str:
    """
    Generate ZATCA Phase 1 compliant QR code data (TLV base64 encoded).

    Tags:
      Tag 1 = Seller name
      Tag 2 = VAT registration number
      Tag 3 = Invoice date/time (ISO 8601)
      Tag 4 = Invoice total (including VAT)
      Tag 5 = VAT amount
    """
    # Accept either numeric or pre-formatted string amounts
    total_str = f"{float(total_with_vat):.2f}"
    vat_str   = f"{float(vat_amount):.2f}"

    tlv_data = b""
    tlv_data += _tlv_encode(1, seller_name)
    tlv_data += _tlv_encode(2, vat_number)
    tlv_data += _tlv_encode(3, invoice_datetime)
    tlv_data += _tlv_encode(4, total_str)
    tlv_data += _tlv_encode(5, vat_str)

    return base64.b64encode(tlv_data).decode("utf-8")


def decode_zatca_qr(qr_base64: str) -> dict:
    """Decode a ZATCA QR code for verification (Phase 1 tags 1-5 and
    Phase 2 tags 6-9). Binary tags (8=public key, 9=cert signature) are
    returned Base64-encoded since they are not UTF-8 text."""
    tag_names = {
        1: "seller_name",
        2: "vat_number",
        3: "invoice_datetime",
        4: "total_with_vat",
        5: "vat_amount",
        6: "invoice_hash",
        7: "signature",
        8: "public_key",
        9: "cert_signature",
    }
    try:
        data = base64.b64decode(qr_base64)
    except Exception as e:
        return {"error": f"base64 decode failed: {e}"}

    result = {}
    i = 0
    while i + 1 < len(data):
        tag    = data[i]
        length = data[i + 1]
        raw    = data[i + 2 : i + 2 + length]
        name   = tag_names.get(tag, f"tag_{tag}")
        try:
            result[name] = raw.decode("utf-8")
        except UnicodeDecodeError:
            # Binary value (e.g. public key / signature) -> base64
            result[name] = base64.b64encode(raw).decode("ascii")
        i += 2 + length
    return result


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def clean_vat_number(vat_no) -> str:
    """The VAT number as plain digits: Arabic digits → 0-9, and spaces,
    dashes, dots or slashes typed between the groups are dropped
    ('300 123 456 700 003' → '300123456700003'). Anything else (letters)
    is kept, so a wrong number stays visibly wrong."""
    v = str(vat_no or "").strip().translate(_AR_DIGITS)
    if v and all(ch.isdigit() or ch in " -./_ " for ch in v):
        v = "".join(ch for ch in v if ch.isdigit())
    return v


def valid_vat_number(vat_no) -> bool:
    """Saudi VAT number: 15 digits, starts and ends with 3."""
    v = clean_vat_number(vat_no)
    return len(v) == 15 and v.isascii() and v.isdigit() and v[0] == "3" and v[-1] == "3"


def vat_problem(vat_no) -> str:
    """'' when the number is good for the ZATCA QR, else why not (simple English)."""
    v = clean_vat_number(vat_no)
    if not v:
        return "The company VAT number is empty."
    if valid_vat_number(v):
        return ""
    return ("The company VAT number '%s' is not right: a Saudi VAT number has "
            "15 digits and starts and ends with 3 (like 300000000000003)." % str(vat_no).strip())


QR_FIX_HINT = "Fill it in Settings ▸ Company ▸ VAT number, then print again."


def invoice_timestamp(invoice: dict) -> str:
    """The invoice's own date + time (shop's local time) as ISO 8601 UTC
    ('2026-09-27T10:50:06Z'), so the QR always matches the printed bill."""
    from datetime import date as _date, time as _time, timezone
    d = invoice.get("invoice_date")
    t = invoice.get("invoice_time")
    try:
        if isinstance(d, datetime):
            d = d.date()
        elif not isinstance(d, _date):
            d = datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except Exception:
        d = None
    try:
        if isinstance(t, datetime):
            t = t.time()
        elif hasattr(t, "total_seconds"):             # timedelta from some drivers
            sec = int(t.total_seconds()); t = _time(sec // 3600 % 24, sec // 60 % 60, sec % 60)
        elif t and not isinstance(t, _time):
            parts = (str(t).split(".")[0].split(":") + ["0", "0"])[:3]
            t = _time(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        t = None
    created = None
    ca = invoice.get("created_at")
    try:
        created = ca if isinstance(ca, datetime) else datetime.strptime(
            str(ca)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except Exception:
        created = None
    if t is None and created is not None and (d is None or created.date() == d):
        t = created.time().replace(microsecond=0)
    if d is None:
        if created is None:
            return format_zatca_datetime()
        local = created
    else:
        local = datetime.combine(d, t or _time(0, 0, 0))
    try:
        return local.astimezone().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return local.strftime("%Y-%m-%dT%H:%M:%SZ")


def seller_name(company: dict) -> str:
    return str((company or {}).get("company_name_ar") or (company or {}).get("company_name_en") or "").strip()


def phase1_for_invoice(invoice: dict, company: dict) -> str:
    """ZATCA Phase 1 QR (tags 1-5) built from the SAVED invoice: seller name,
    company VAT number, the invoice's date/time, total incl. VAT, VAT.
    '' when the company VAT number is missing / not a valid Saudi number."""
    vat_no = clean_vat_number((company or {}).get("vat_registration_no"))
    if not valid_vat_number(vat_no):
        return ""
    def _f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0
    return generate_zatca_qr(seller_name(company), vat_no, invoice_timestamp(invoice),
                             _f(invoice.get("total_amount")), _f(invoice.get("vat_amount")))


def generate_invoice_hash(invoice_xml: str) -> str:
    """Generate SHA-256 hash of invoice XML (used for Phase 2)."""
    return hashlib.sha256(invoice_xml.encode("utf-8")).hexdigest()


def format_zatca_datetime(dt: datetime = None) -> str:
    """Format datetime to ZATCA ISO 8601 format."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── QR Code Image Generator (requires qrcode + Pillow) ───────
def generate_qr_image(qr_data: str, size: int = 200):
    """
    Generate QR code image from ZATCA TLV data.
    Returns PIL Image object or None if qrcode not installed.
    """
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=4,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img
    except ImportError:
        return None
    except Exception:
        return None


def generate_qr_photoimage(qr_data: str, size: int = 160):
    """
    Generate a tkinter PhotoImage from QR code data.
    Returns tkinter PhotoImage or None.
    """
    try:
        import qrcode
        from PIL import ImageTk, Image

        qr = qrcode.QRCode(version=None, box_size=4, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None
