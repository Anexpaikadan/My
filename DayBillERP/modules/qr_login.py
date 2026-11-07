# ============================================================
# DayBill ERP - QR sign-in for every user / employee (v7.4)
# ------------------------------------------------------------
# Each DayBill user (an employee, a cashier, a van driver …) can have a
# personal QR code:
#   • on the phone: scan it with the camera → DayBill Mobile opens on the
#     shop Wi-Fi and signs in as that user (the modules of Mobile ▸ Users)
#   • at the desktop login: scan the QR card with the barcode scanner →
#     signed in, no password typing
# The QR is sent to the person on WhatsApp (link + card PDF) or printed as
# a staff card. Only a hash of the key is kept; a new QR makes the old one
# stop working, and it can expire or be turned off at any time.
#
#   make(user_id, days=None)  → key   (old QR stops working)
#   payload(key)              → what the QR holds (the phone link)
#   user_for(code, where)     → the user row, or raises QrError
#   revoke(user_id) · status(user_id) · png(...) · card_pdf(...)
#   send_whatsapp(user_id, key) → (ok, how)
# ============================================================
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta

from config.database import db

PREFIX = "DBQR:"
_KEY_RE = re.compile(r"(?:#|[?&])k=([A-Za-z0-9_\-]{20,80})|^DBQR:([A-Za-z0-9_\-]{20,80})$")
MAX_FAILS, LOCK_SECONDS = 5, 300


class QrError(Exception):
    pass


def _hash(key):
    return hashlib.sha256(str(key).encode("utf-8")).hexdigest()


def ready():
    try:
        return db.execute_scalar("SELECT OBJECT_ID('user_qr_keys','U')") is not None
    except Exception:
        return False


def key_of(code):
    """The key inside a scanned / typed QR text (phone link or DBQR:…), else ''."""
    s = str(code or "").strip()
    m = _KEY_RE.search(s)
    return (m.group(1) or m.group(2)) if m else ""


def looks_like_qr(code):
    return bool(key_of(code))


def _me():
    try:
        from modules import permissions as p
        return (p.session_user() or {}).get("user_id")
    except Exception:
        return None


def make(user_id, days=None, allow_mobile=True, allow_desktop=True):
    """A new personal QR key for the user (the old one stops working)."""
    if not ready():
        raise QrError("Run the database update first (QR sign-in table missing).")
    u = db.fetchone("SELECT user_id, is_active FROM users WHERE user_id=?", (int(user_id),))
    if not u:
        raise QrError("User not found.")
    if not u.get("is_active", 1):
        raise QrError("This user is switched off — activate it first.")
    key = secrets.token_urlsafe(24)
    exp = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S") if days else None
    db.execute("DELETE FROM user_qr_keys WHERE user_id=?", (int(user_id),))
    db.execute("INSERT INTO user_qr_keys (user_id, key_hash, key_hint, allow_mobile, allow_desktop, expires_at, "
               "is_active, created_by) VALUES (?,?,?,?,?,?,1,?)",
               (int(user_id), _hash(key), key[-4:], 1 if allow_mobile else 0, 1 if allow_desktop else 0,
                exp, _me()))
    _audit("qr_make", user_id, "new QR sign-in%s" % ((" (valid %s days)" % days) if days else ""))
    return key


def revoke(user_id):
    if ready():
        db.execute("UPDATE user_qr_keys SET is_active=0 WHERE user_id=?", (int(user_id),))
        _audit("qr_revoke", user_id, "QR sign-in turned off")


def status(user_id):
    """{} when the user has no QR, else its row (no key — only the hash is kept)."""
    if not ready():
        return {}
    r = db.fetchone("SELECT * FROM user_qr_keys WHERE user_id=?", (int(user_id),)) or {}
    if r:
        r = dict(r)
        r["expired"] = bool(r.get("expires_at") and r["expires_at"] < datetime.now())
        r["working"] = bool(r.get("is_active")) and not r["expired"]
    return r


def statuses():
    """{user_id: status row} for the Users list."""
    if not ready():
        return {}
    out = {}
    for r in db.fetchall("SELECT * FROM user_qr_keys") or []:
        r = dict(r)
        r["expired"] = bool(r.get("expires_at") and r["expires_at"] < datetime.now())
        r["working"] = bool(r.get("is_active")) and not r["expired"]
        out[r["user_id"]] = r
    return out


def _failed_recently(where):
    try:
        from modules import permissions as p
        return p.recent_failed_logins("QR:" + where, LOCK_SECONDS) >= MAX_FAILS
    except Exception:
        return False


def _log(user_id, where, ok):
    try:
        from modules import permissions as p
        p.log_login(user_id, "QR:" + where, ok)
    except Exception:
        pass


def user_for(code, where="mobile"):
    """The users row a scanned QR signs in as. where = 'mobile' | 'desktop'."""
    key = key_of(code)
    if not key:
        raise QrError("This is not a DayBill sign-in QR.")
    if not ready():
        raise QrError("QR sign-in is not set up in this database.")
    if _failed_recently(where):
        raise QrError("Too many wrong QR codes — wait 5 minutes and try again.")
    r = db.fetchone("SELECT q.*, u.username, u.is_active AS user_active FROM user_qr_keys q "
                    "JOIN users u ON u.user_id=q.user_id WHERE q.key_hash=?", (_hash(key),))
    if not r:
        _log(None, where, False)
        raise QrError("This QR code is not valid (a newer one was made, or it was turned off).")
    if not r.get("is_active"):
        _log(r["user_id"], where, False)
        raise QrError("This QR code was turned off. Ask the office for a new one.")
    if r.get("expires_at") and r["expires_at"] < datetime.now():
        _log(r["user_id"], where, False)
        raise QrError("This QR code has expired. Ask the office for a new one.")
    if not r.get("user_active", 1):
        _log(r["user_id"], where, False)
        raise QrError("This user is switched off.")
    if where == "desktop" and not r.get("allow_desktop"):
        raise QrError("This QR code is for the phone app only.")
    if where == "mobile" and not r.get("allow_mobile"):
        raise QrError("This QR code is for the desktop sign-in only.")
    db.execute("UPDATE user_qr_keys SET last_used=GETDATE(), use_count=use_count+1 WHERE user_id=?",
               (r["user_id"],))
    _log(r["user_id"], where, True)
    return db.fetchone("SELECT * FROM users WHERE user_id=?", (r["user_id"],))


# ── what the QR holds ─────────────────────────────────────────
def app_url():
    """The phone app's address on the shop Wi-Fi (Mobile server)."""
    try:
        from config import settings as cfg
        fixed = str(cfg.get("qr_login_url", "") or "").strip().rstrip("/")
        if fixed:
            return fixed
        from modules import mobile_server as MS
        port = int(cfg.get("mobile_port", MS.DEFAULT_PORT) or MS.DEFAULT_PORT)
        return "http://%s:%d" % (MS.local_ips()[0], port)
    except Exception:
        return "http://127.0.0.1:8090"


def payload(key):
    """The phone link with the key — the phone camera opens it and signs in;
    the desktop login reads the same text from the scanner."""
    return "%s/#k=%s" % (app_url(), key)


def png(text, path, box=8):
    import qrcode
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box, border=2)
    q.add_data(text)
    q.make(fit=True)
    q.make_image(fill_color="black", back_color="white").save(path)
    return path


def _user_info(user_id):
    u = db.fetchone("SELECT * FROM users WHERE user_id=?", (int(user_id),)) or {}
    emp = {}
    try:
        emp = db.fetchone("SELECT TOP 1 * FROM employees WHERE user_id=?", (int(user_id),)) or {}
    except Exception:
        emp = {}
    role = ""
    try:
        role = db.execute_scalar("SELECT role_name_en FROM roles WHERE role_id=?", (u.get("role_id"),)) or ""
    except Exception:
        pass
    return u, emp, role


def phone_of(user_id):
    """The user's mobile: the user's own, else the linked employee's."""
    u, emp, _r = _user_info(user_id)
    return str(u.get("phone") or emp.get("phone") or "").strip()


def out_dir():
    try:
        from config.paths import DATA_DIR
        d = os.path.join(DATA_DIR, "qr_cards")
    except Exception:
        d = os.path.join(os.path.dirname(__file__), "..", "qr_cards")
    os.makedirs(d, exist_ok=True)
    return d


def card_pdf(user_id, key, path=None):
    """A staff card (credit-card size, 2 per A4 row when printed): shop,
    name, job, user name and the QR."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white
    u, emp, role = _user_info(user_id)
    comp = db.fetchone("SELECT TOP 1 * FROM company") or {}
    path = path or os.path.join(out_dir(), "qr_%s.pdf" % re.sub(r"\W+", "_", u.get("username") or str(user_id)))
    qr = png(payload(key), path[:-4] + ".png", box=10)
    W, H = 86 * mm, 54 * mm
    try:
        from modules import pdf_invoice as P
        P._register_fonts()
        REG, BOLD = P._AR_FONT, P._AR_FONT_BOLD
        shape = lambda t: P._shape_arabic(t) if P._has_arabic(t) else str(t or "")
    except Exception:
        REG, BOLD, shape = "Helvetica", "Helvetica-Bold", lambda t: str(t or "")
    c = canvas.Canvas(path, pagesize=(W, H))
    c.setFillColor(HexColor("#1D4ED8")); c.rect(0, H - 12 * mm, W, 12 * mm, stroke=0, fill=1)
    c.setFillColor(white); c.setFont(BOLD, 10)
    c.drawString(4 * mm, H - 8 * mm, str(comp.get("company_name_en") or "DayBill")[:34])
    c.setFont(REG, 7); c.drawRightString(W - 4 * mm, H - 8 * mm, "STAFF SIGN-IN")
    c.drawImage(qr, W - 38 * mm, 4 * mm, 34 * mm, 34 * mm)
    c.setFillColor(HexColor("#111827"))
    name = emp.get("full_name_en") or u.get("full_name_en") or u.get("username") or ""
    c.setFont(BOLD, 11); c.drawString(4 * mm, H - 20 * mm, str(name)[:24])
    ar = emp.get("full_name_ar") or u.get("full_name_ar") or ""
    if ar:
        c.setFont(BOLD, 10); c.drawString(4 * mm, H - 26 * mm, shape(ar)[:24])
    c.setFont(REG, 8); c.setFillColor(HexColor("#374151"))
    y = H - 32 * mm
    for line in (emp.get("job_title_en") or role, "User: %s" % (u.get("username") or ""),
                 ("Code: %s" % emp["employee_code"]) if emp.get("employee_code") else ""):
        if line:
            c.drawString(4 * mm, y, str(line)[:30]); y -= 4.5 * mm
    c.setFont(REG, 6); c.setFillColor(HexColor("#6B7280"))
    c.drawString(4 * mm, 4 * mm, "Scan to sign in · keep it private")
    c.showPage(); c.save()
    return path


def message(user_id, key):
    u, emp, _r = _user_info(user_id)
    comp = db.fetchone("SELECT TOP 1 company_name_en FROM company") or {}
    name = emp.get("full_name_en") or u.get("full_name_en") or u.get("username")
    return ("Hello %s,\n\nYour DayBill sign-in for %s:\n%s\n\n"
            "Open the link on the shop Wi-Fi (or scan the QR card) — DayBill opens and signs you in "
            "as '%s'.\nKeep this message private: anyone with it can sign in as you." % (
                name, comp.get("company_name_en") or "the shop", payload(key), u.get("username")))


def send_whatsapp(user_id, key, phone=None):
    """(ok, how) — with the WhatsApp API the card PDF goes too; else a
    WhatsApp chat opens with the message (link)."""
    from modules import whatsapp as W
    phone = str(phone or phone_of(user_id) or "").strip()
    if not phone:
        return False, "No mobile number — type it on the user (or the employee)."
    text = message(user_id, key)
    ok, how = False, ""
    try:
        num = W.normalize_phone(phone) or phone
        if W.api_ready():
            pdf = card_pdf(user_id, key)
            r = W.api_send(num, text, pdf_path=pdf, template="", kind="qr_login")
            ok = bool(r[0] if isinstance(r, tuple) else r)
            how = "sent by the WhatsApp API with the QR card"
        if not ok:
            W.open_chat(num, text)
            ok, how = True, "WhatsApp opened with the message — press Send"
    except Exception as e:
        return False, "WhatsApp: %s" % str(e)[:120]
    if ok and ready():
        db.execute("UPDATE user_qr_keys SET sent_to=?, sent_at=GETDATE() WHERE user_id=?",
                   (phone[:30], int(user_id)))
        _audit("qr_send", user_id, "QR sign-in sent to %s" % phone)
    return ok, how


# ── employees ↔ users ─────────────────────────────────────────
def link_employee(employee_id, user_id):
    db.execute("UPDATE employees SET user_id=? WHERE employee_id=?",
               (int(user_id) if user_id else None, int(employee_id)))


def user_for_employee(employee_id):
    try:
        uid = db.execute_scalar("SELECT user_id FROM employees WHERE employee_id=?", (int(employee_id),))
        return int(uid) if uid else None
    except Exception:
        return None


def create_user_for_employee(employee_id, role_id=None):
    """A DayBill user for an employee (user name = employee code, a random
    password nobody needs to know — they sign in with the QR). → user_id"""
    e = db.fetchone("SELECT * FROM employees WHERE employee_id=?", (int(employee_id),))
    if not e:
        raise QrError("Employee not found.")
    if e.get("user_id"):
        return int(e["user_id"])
    from modules import permissions as p
    if not role_id:
        role_id = db.execute_scalar("SELECT TOP 1 role_id FROM roles WHERE role_name_en IN ('Cashier','Salesman','Staff') "
                                    "ORDER BY role_id") or \
            db.execute_scalar("SELECT TOP 1 role_id FROM roles ORDER BY role_id DESC")
    base = re.sub(r"[^A-Za-z0-9_.-]", "", str(e.get("employee_code") or "emp%d" % employee_id)).lower() or "emp"
    name, n = base, 2
    while db.execute_scalar("SELECT COUNT(*) FROM users WHERE username=?", (name,)):
        name = "%s%d" % (base, n)
        n += 1
    db.execute("INSERT INTO users (username, password_hash, full_name_en, full_name_ar, phone, role_id, is_active) "
               "VALUES (?,?,?,?,?,?,1)",
               (name, p.hash_password(secrets.token_urlsafe(18)), e.get("full_name_en") or name,
                e.get("full_name_ar"), e.get("phone"), role_id))
    uid = db.execute_scalar("SELECT user_id FROM users WHERE username=?", (name,))
    link_employee(employee_id, uid)
    _audit("add", uid, "user %s made for employee %s" % (name, e.get("employee_code")))
    return int(uid)


def _audit(action, user_id, text):
    try:
        from modules import audit
        audit.log(action, "users", user_id, text)
    except Exception:
        pass
