# ============================================================
# DayBill ERP - customer loyalty QR card (v7.5)
# ------------------------------------------------------------
# Each customer can get a QR card (on WhatsApp or printed). Scanning it
# at the POS / Sales Invoice (barcode box) picks that customer — their
# price list and loyalty points come with them. After a sale the
# customer can get their points balance on WhatsApp (Cloud API).
#
#   make(customer_id) → code      (an older card stops working)
#   customer_for(code) → customers row or None
#   card_pdf(customer_id, code) · message(customer_id, code)
#   send_whatsapp(customer_id, code) → (ok, how)
#   after_sale(invoice_id) → WhatsApp points message (when switched on)
# ============================================================
import hashlib
import os
import re
import secrets

from config.database import db
from config import settings as cfg

PREFIX = "DBCUST:"
_RE = re.compile(r"^DBCUST:([A-Za-z0-9_\-]{12,64})$")


def _hash(k):
    return hashlib.sha256(str(k).encode("utf-8")).hexdigest()


def ready():
    try:
        return db.execute_scalar("SELECT COL_LENGTH('customers','loyalty_key_hash')") is not None
    except Exception:
        return False


def is_card(code):
    return bool(_RE.match(str(code or "").strip()))


def make(customer_id):
    if not ready():
        raise ValueError("Run the database update first (loyalty card column missing).")
    c = db.fetchone("SELECT customer_id, customer_code FROM customers WHERE customer_id=?", (int(customer_id),))
    if not c:
        raise ValueError("Customer not found.")
    if str(c.get("customer_code") or "").upper() in ("CASH", "WALKIN", "WALK-IN", "CASH-001"):
        raise ValueError("The cash / walk-in customer has no loyalty card.")
    key = secrets.token_urlsafe(12)
    db.execute("UPDATE customers SET loyalty_key_hash=? WHERE customer_id=?", (_hash(key), int(customer_id)))
    try:
        from modules import audit
        audit.log("loyalty_card", "customers", customer_id, "new loyalty QR card")
    except Exception:
        pass
    return PREFIX + key


def has_card(customer_id):
    try:
        return bool(db.execute_scalar("SELECT loyalty_key_hash FROM customers WHERE customer_id=?",
                                      (int(customer_id),)))
    except Exception:
        return False


def customer_for(code):
    m = _RE.match(str(code or "").strip())
    if not m or not ready():
        return None
    return db.fetchone("SELECT * FROM customers WHERE loyalty_key_hash=? AND ISNULL(is_active,1)=1",
                       (_hash(m.group(1)),))


def _points(customer_id):
    try:
        from modules import loyalty as L
        if L.enabled():
            return L.balance(customer_id)
    except Exception:
        pass
    return None


def png(code, path, box=8):
    import qrcode
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box, border=2)
    q.add_data(code)
    q.make(fit=True)
    q.make_image(fill_color="black", back_color="white").save(path)
    return path


def out_dir():
    try:
        from config.paths import DATA_DIR
        d = os.path.join(DATA_DIR, "loyalty_cards")
    except Exception:
        d = os.path.join(os.path.dirname(__file__), "..", "loyalty_cards")
    os.makedirs(d, exist_ok=True)
    return d


def card_pdf(customer_id, code, path=None):
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white
    c_ = db.fetchone("SELECT * FROM customers WHERE customer_id=?", (int(customer_id),)) or {}
    comp = db.fetchone("SELECT TOP 1 * FROM company") or {}
    path = path or os.path.join(out_dir(), "card_%s.pdf" % re.sub(r"\W+", "_", str(c_.get("customer_code") or customer_id)))
    qr = png(code, path[:-4] + ".png", box=10)
    W, H = 86 * mm, 54 * mm
    try:
        from modules import pdf_invoice as P
        P._register_fonts()
        REG, BOLD = P._AR_FONT, P._AR_FONT_BOLD
        shape = lambda t: P._shape_arabic(t) if P._has_arabic(t) else str(t or "")
    except Exception:
        REG, BOLD, shape = "Helvetica", "Helvetica-Bold", lambda t: str(t or "")
    cv = canvas.Canvas(path, pagesize=(W, H))
    cv.setFillColor(HexColor("#B45309")); cv.rect(0, 0, W, H, stroke=0, fill=1)
    cv.setFillColor(HexColor("#FDE68A")); cv.rect(0, H - 13 * mm, W, 13 * mm, stroke=0, fill=1)
    cv.setFillColor(HexColor("#78350F")); cv.setFont(BOLD, 10)
    cv.drawString(4 * mm, H - 8.5 * mm, str(comp.get("company_name_en") or "DayBill")[:30])
    cv.setFont(BOLD, 8); cv.drawRightString(W - 4 * mm, H - 8.5 * mm, "⭐ LOYALTY CARD".replace("⭐ ", ""))
    cv.setFillColor(white); cv.roundRect(W - 38 * mm, 3 * mm, 35 * mm, 35 * mm, 2 * mm, stroke=0, fill=1)
    cv.drawImage(qr, W - 37 * mm, 4 * mm, 33 * mm, 33 * mm)
    cv.setFillColor(white); cv.setFont(BOLD, 12)
    cv.drawString(4 * mm, H - 22 * mm, str(c_.get("customer_name_en") or "")[:22])
    if c_.get("customer_name_ar"):
        cv.setFont(BOLD, 10); cv.drawString(4 * mm, H - 28 * mm, shape(c_["customer_name_ar"])[:22])
    cv.setFont(REG, 8)
    cv.drawString(4 * mm, H - 35 * mm, "Card: %s" % (c_.get("customer_code") or ""))
    pts = _points(customer_id)
    if pts is not None:
        cv.drawString(4 * mm, H - 40 * mm, "Points: %s" % int(pts))
    cv.setFont(REG, 6); cv.drawString(4 * mm, 4 * mm, "Show this QR at the counter")
    cv.showPage(); cv.save()
    return path


def message(customer_id, code=None):
    c_ = db.fetchone("SELECT customer_name_en FROM customers WHERE customer_id=?", (int(customer_id),)) or {}
    comp = db.fetchone("SELECT TOP 1 company_name_en FROM company") or {}
    pts = _points(customer_id)
    txt = "Hello %s,\n\nYour %s loyalty card%s." % (
        c_.get("customer_name_en") or "", comp.get("company_name_en") or "shop",
        (" — points: %d" % int(pts)) if pts is not None else "")
    if code:
        txt += "\nShow the QR card (attached / at the counter) when you pay — your points are added." \
               "\nCard code: %s" % code
    return txt


def send_whatsapp(customer_id, code, phone=None):
    from modules import whatsapp as W
    c_ = db.fetchone("SELECT phone, mobile FROM customers WHERE customer_id=?", (int(customer_id),)) \
        if _has_mobile() else db.fetchone("SELECT phone FROM customers WHERE customer_id=?", (int(customer_id),))
    phone = str(phone or (c_ or {}).get("mobile") or (c_ or {}).get("phone") or "").strip()
    if not phone:
        return False, "No mobile number on the customer."
    num = W.normalize_phone(phone) or phone
    text = message(customer_id, code)
    try:
        if W.api_ready():
            r = W.api_send(num, text, pdf_path=card_pdf(customer_id, code), template="", kind="loyalty_card")
            if r[0] if isinstance(r, tuple) else r:
                return True, "sent by the WhatsApp API with the card"
        W.open_chat(num, text)
        return True, "WhatsApp opened with the message — attach the card PDF and press Send"
    except Exception as e:
        return False, "WhatsApp: %s" % str(e)[:120]


def _has_mobile():
    try:
        return db.execute_scalar("SELECT COL_LENGTH('customers','mobile')") is not None
    except Exception:
        return False


def after_sale(invoice_id):
    """Settings ▸ Loyalty: 'WhatsApp the points after each sale' (Cloud API
    only — never opens a window at the counter). → True when sent."""
    if not cfg.flag("loyalty_wa_after_sale", False):
        return False
    try:
        from modules import whatsapp as W, loyalty as L
        if not (W.api_ready() and L.enabled()):
            return False
        inv = db.fetchone("SELECT customer_id, invoice_number, total_amount FROM sales_invoices WHERE invoice_id=?",
                          (int(invoice_id),))
        if not inv or not inv.get("customer_id") or not has_card(inv["customer_id"]):
            return False
        c_ = db.fetchone("SELECT * FROM customers WHERE customer_id=?", (inv["customer_id"],)) or {}
        if L.is_walk_in(c_) or not (c_.get("phone") or c_.get("mobile")):
            return False
        bal = L.balance(inv["customer_id"])
        text = "Thank you %s! Bill %s · %.2f. Your points now: %d." % (
            c_.get("customer_name_en") or "", inv["invoice_number"], float(inv["total_amount"] or 0), int(bal))
        ok = W.api_send(W.normalize_phone(c_.get("mobile") or c_.get("phone")), text, template="", kind="loyalty_points")
        return bool(ok[0] if isinstance(ok, tuple) else ok)
    except Exception:
        return False
