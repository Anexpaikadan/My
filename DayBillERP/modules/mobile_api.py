# ============================================================
# DayBill ERP - Mobile / PDT / Van sales: the back office side
# ------------------------------------------------------------
# Everything a phone, a PDT scanner or a van can ask DayBill to do.
# Plain functions (JSON in, JSON out) — the Wi-Fi server
# (modules/mobile_server.py) and the internet van sync
# (modules/van_sync.py) both call these, so the rules are the same.
#
#   login(user, password, device)        → token + the modules this user may use
#   resolve(code) / search(text)          → product + unit (one barcode answer)
#   product_info(product_id)              → units, prices, barcodes, stock …
#   submit(token, doc)                    → Goods In / Goods Out / Stock Count /
#                                           Stock Adjust / Van Sale
#   apply_doc(doc_id) / reject_doc(...)    → office approves from the inbox
#   van_catalog()                          → everything a van needs offline
#
# Stock moves follow the same rules as the desktop screens:
#   Goods In     → a DRAFT purchase (office checks supplier prices, confirms)
#   Goods Out    → stock out (damage / expired / own use / transfer) + journal
#   Stock Count  → counted qty becomes the stock (difference posted)
#   Stock Adjust → + / − stock + journal
#   Van Sale     → a confirmed sales invoice (channel VAN) + stock + journal
# Every document has the device's own id (doc_uid): sending it twice never
# books it twice.
# ============================================================
import sys, os, json, secrets, hashlib
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db
from config import settings as cfg

MODULES = [
    # key, English, Arabic, icon
    ("goods_in", "Goods In", "استلام بضاعة", "📥"),
    ("goods_out", "Goods Out", "إخراج بضاعة", "📤"),
    ("count", "Stock Count", "جرد", "🧮"),
    ("adjust", "Stock Adjust", "تسوية مخزون", "⚖"),
    ("info", "Product Info", "معلومات الصنف", "🔎"),
    ("price", "Price Check", "فحص السعر", "🏷"),
    ("van", "Van Sales", "مبيعات السيارة", "🚚"),
]
MODULE_KEYS = [m[0] for m in MODULES]
OUT_REASONS = ["Damaged", "Expired", "Own use", "Transfer out", "Sample / gift", "Other"]


class MobileError(Exception):
    pass


# ── small helpers ─────────────────────────────────────────────
def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _check_date(head):
    """The bill date the device sent: a real date, not in a closed year."""
    when = str(head.get("date") or date.today().isoformat())[:10]
    try:
        datetime.strptime(when, "%Y-%m-%d")
    except ValueError:
        raise MobileError("Bad date '%s'." % when)
    from modules import financial_year as _fy
    msg = _fy.lock_message(when)
    if msg:
        raise MobileError(msg)
    return when


def _product_or_fail(ln):
    p = _one("SELECT * FROM products WHERE product_id=?", (ln.get("product_id"),))
    if not p:                       # never save a bill without one of its items
        raise MobileError("Product %s is not in DayBill — sync the device and send again."
                          % ln.get("product_id"))
    return p


def _posted_or_fail(kind, doc_id, **kw):
    """Stock + books for a document saved from a device. A bill whose journal
    cannot be posted is NOT kept: everything rolls back and the document
    waits in the office Inbox with the reason (v6.9.2)."""
    from modules import doc_posting
    warn = doc_posting.sync(kind, doc_id, **kw) or ""
    if "journal not posted" in warn:
        raise MobileError("Not booked — " + warn)
    return warn


def clean(obj):
    """Rows → JSON-safe (Decimal → float, dates → text)."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", "replace")
    return obj


def _one(sql, p=()):
    try:
        return db.fetchone(sql, p)
    except Exception:
        return None


def _all(sql, p=()):
    try:
        return db.fetchall(sql, p) or []
    except Exception:
        return []


def tables_ready():
    try:
        db.fetchone("SELECT COUNT(*) AS n FROM mobile_docs")
        return True
    except Exception:
        return False


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _vat_rate(prod):
    if not cfg.flag("vat_enabled", True):
        return 0.0
    r = _one("SELECT vat_rate FROM vat_categories WHERE vat_category_id=?",
             (prod.get("vat_category_id"),)) if prod.get("vat_category_id") else None
    return _f((r or {}).get("vat_rate"), 15.0) if r else 15.0


def _price_incl():
    return str(cfg.get("sales_price_tax_mode", "inclusive")).lower() == "inclusive"


# ── who may use what ─────────────────────────────────────────
def access(user_id):
    """{modules: [...], van_code, active} for a DayBill user. The 'admin'
    user may use every module even without a row."""
    row = _one("SELECT * FROM mobile_access WHERE user_id=?", (user_id,))
    u = _one("SELECT username FROM users WHERE user_id=?", (user_id,)) or {}
    if not row:
        if str(u.get("username", "")).lower() == "admin":
            return {"modules": list(MODULE_KEYS), "van_code": "", "active": True}
        return {"modules": [], "van_code": "", "active": False}
    mods = [m for m in str(row.get("modules") or "").split(",") if m in MODULE_KEYS]
    return {"modules": mods, "van_code": row.get("van_code") or "",
            "active": bool(row.get("is_active", 1))}


def set_access(user_id, modules, active=True, van_code=None, van_pin=None):
    mods = ",".join(m for m in MODULE_KEYS if m in (modules or []))
    pin_hash = None
    if van_pin:
        salt = secrets.token_hex(8)
        pin_hash = salt + "$" + hashlib.sha256((salt + str(van_pin)).encode()).hexdigest()
    have = _one("SELECT user_id, van_pin_hash FROM mobile_access WHERE user_id=?", (user_id,))
    if have:
        db.execute("UPDATE mobile_access SET modules=?, is_active=?, van_code=?, "
                   "van_pin_hash=?, updated_at=GETDATE() WHERE user_id=?",
                   (mods, 1 if active else 0, van_code or None,
                    pin_hash or have.get("van_pin_hash"), user_id))
    else:
        db.execute("INSERT INTO mobile_access (user_id, modules, is_active, van_code, "
                   "van_pin_hash) VALUES (?,?,?,?,?)",
                   (user_id, mods, 1 if active else 0, van_code or None, pin_hash))


def check_pin(stored, pin):
    try:
        salt, h = str(stored).split("$", 1)
        return hashlib.sha256((salt + str(pin)).encode()).hexdigest() == h
    except Exception:
        return False


MOBILE_MAX_FAILS, MOBILE_LOCK_SECONDS = 5, 300


def login(username, password, device=""):
    name = str(username or "").strip()[:50]
    from modules import permissions as _pm
    # v6.9.2: the same lock as the desktop sign-in — 5 wrong passwords, then wait
    if _pm.recent_failed_logins(name, MOBILE_LOCK_SECONDS) >= MOBILE_MAX_FAILS:
        raise MobileError("Too many wrong passwords — wait 5 minutes and try again.")
    u = _one("SELECT user_id, username, password_hash, full_name_en, is_active FROM users "
             "WHERE username=?", (name,))
    if not u or not u.get("is_active", 1) or not _pm.verify_password(password or "",
                                                                        u.get("password_hash")):
        _pm.log_login(u["user_id"] if u else None, name, False)
        raise MobileError("Wrong user name or password.")
    acc = access(u["user_id"])
    if not acc["active"] or not acc["modules"]:
        raise MobileError("This user has no mobile access. In DayBill: Inventory ▸ "
                          "Mobile & Van ▸ Users — tick the modules for %s." % u["username"])
    _pm.log_login(u["user_id"], name, True)
    tok = secrets.token_hex(24)
    db.execute("INSERT INTO mobile_tokens (token, user_id, device) VALUES (?,?,?)",
               (tok, u["user_id"], str(device or "")[:120]))
    try:            # v6.9.2: the sign-in ends when the password is changed
        db.execute("UPDATE mobile_tokens SET pw_sig=? WHERE token=?",
                   (_pw_sig(u.get("password_hash")), tok))
    except Exception:
        pass
    dev_no = next_device_no(u["user_id"], acc)
    return {"token": tok, "user": u["full_name_en"] or u["username"], "device_no": dev_no,
            "user_id": u["user_id"], "modules": acc["modules"], "van_code": acc["van_code"],
            "module_list": [{"key": k, "en": en, "ar": ar, "icon": ic}
                            for k, en, ar, ic in MODULES if k in acc["modules"]],
            "company": company(), "settings": app_settings()}


def next_device_no(user_id, acc=None):
    """Every sign-in gets its own number, so two phones of the same van
    never print the same bill number (VAN1-2-00005)."""
    if not _one("SELECT user_id FROM mobile_access WHERE user_id=?", (user_id,)):
        a = acc or access(user_id)
        set_access(user_id, a["modules"], active=True)
    try:
        db.execute("UPDATE mobile_access SET device_seq=ISNULL(device_seq,0)+1 WHERE user_id=?", (user_id,))
        r = _one("SELECT device_seq FROM mobile_access WHERE user_id=?", (user_id,))
        return int((r or {}).get("device_seq") or 1)
    except Exception:
        return 1


def _pw_sig(password_hash):
    """A short fingerprint of the stored password: a new password → new sig."""
    return hashlib.sha256(str(password_hash or "").encode("utf-8")).hexdigest()[:16]


def user_for(token):
    """Token → {user_id, username, modules}; MobileError when unknown."""
    t = _one("SELECT t.*, u.username, u.full_name_en, u.is_active, u.password_hash "
             "FROM mobile_tokens t JOIN users u ON u.user_id=t.user_id WHERE t.token=?",
             (str(token or ""),))
    if not t or not t.get("is_active", 1):
        raise MobileError("Please sign in again.")
    if t.get("pw_sig") and t["pw_sig"] != _pw_sig(t.get("password_hash")):
        db.execute("DELETE FROM mobile_tokens WHERE token=?", (str(token),))
        raise MobileError("The password was changed — please sign in again.")
    acc = access(t["user_id"])
    if not acc["active"]:
        raise MobileError("Mobile access was turned off for this user — please sign in again.")
    try:
        db.execute("UPDATE mobile_tokens SET last_seen=GETDATE() WHERE token=?", (token,))
    except Exception:
        pass
    return {"user_id": t["user_id"], "username": t["username"],
            "name": t.get("full_name_en") or t["username"], "modules": acc["modules"]}


def need(user, module):
    if module not in user["modules"]:
        raise MobileError("Your user may not use %s." % dict((m[0], m[1]) for m in MODULES)
                          .get(module, module))


def company():
    c = _one("SELECT * FROM company") or {}
    return clean({k: c.get(k) for k in ("company_name_en", "company_name_ar",
                                          "vat_registration_no", "cr_number", "phone",
                                          "address_en", "address_ar", "city_en",
                                          "building_number", "street_name_en")})


def app_settings():
    return {"price_incl_vat": _price_incl(), "vat_enabled": cfg.flag("vat_enabled", True),
            "currency": cfg.get("currency", "SAR") or "SAR",
            "approve_stock": cfg.flag("mobile_approve_stock", False),
            "out_reasons": OUT_REASONS,
            "receipt_footer": cfg.get("receipt_footer", "") or "Thank you!"}


# ── products ─────────────────────────────────────────────────
def product_card(pid, unit_id=None, show_cost=False):
    """Everything a scanner screen shows for one product."""
    from modules import barcode_resolver as BR
    p = _one("SELECT p.*, c.category_name_en FROM products p LEFT JOIN product_categories c "
             "ON c.category_id=p.category_id WHERE p.product_id=?", (pid,)) \
        or _one("SELECT * FROM products WHERE product_id=?", (pid,))
    if not p:
        raise MobileError("Product not found.")
    rows = BR.label_rows(pid)
    rate = _vat_rate(p)
    extras = {}
    for r in _all("SELECT unit_id, barcode FROM product_unit_barcodes WHERE product_id=? "
                  "AND ISNULL(is_active,1)=1", (pid,)):
        extras.setdefault(r["unit_id"], []).append(r["barcode"])
    stock = _f(p.get("stock_quantity"))
    units = []
    for r in rows:
        fac = _f(r.get("factor"), 1) or 1
        u = {"unit_id": r.get("unit_id"), "unit": r.get("unit_name") or "",
             "unit_ar": r.get("unit_name_ar") or "", "factor": fac,
             "price": round(_f(r.get("unit_price")), 2),
             "price_vat": _f(r.get("offer_price") or r.get("price_vat")),
             "normal_price_vat": _f(r.get("price_vat")),
             "offer": r.get("offer_text") or "", "barcode": r.get("barcode_value") or "",
             "extra_barcodes": extras.get(r.get("unit_id"), []),
             "stock_in_unit": round(stock / fac, 3)}
        if show_cost:
            uc = _one("SELECT purchase_price FROM product_units WHERE unit_id=?",
                      (r.get("unit_id"),)) if r.get("unit_id") else None
            u["cost"] = round(_f((uc or {}).get("purchase_price")) or
                              _f(p.get("purchase_price")) * fac, 2)
        units.append(u)
    big = sorted([u for u in units if u["factor"] > 1], key=lambda u: -u["factor"])
    left, parts = stock, []
    for u in big:
        n = int(left // u["factor"]) if left > 0 else 0
        if n:
            parts.append("%d %s" % (n, u["unit"]))
            left -= n * u["factor"]
    base = next((u for u in units if abs(u["factor"] - 1) < 1e-9), None)
    if parts and left > 1e-9:
        parts.append("%g %s" % (round(left, 3), (base or {}).get("unit") or "pcs"))
    card = {"product_id": pid, "code": p.get("product_code"), "name": p.get("product_name_en"),
            "name_ar": p.get("product_name_ar") or "", "category": p.get("category_name_en") or "",
            "stock": stock, "stock_text": " + ".join(parts) if parts else "%g" % stock,
            "reorder_level": _f(p.get("reorder_level")), "vat_rate": rate,
            "location": p.get("storage_location") or "", "units": units,
            "unit_id": unit_id or ((base or units[0])["unit_id"] if units else None),
            "is_active": bool(p.get("is_active", 1))}
    if show_cost:
        last = _one("SELECT TOP 1 pi.invoice_date, pi.supplier_name_en, l.unit_price, "
                    "l.unit_of_measure_en FROM purchase_invoice_lines l JOIN purchase_invoices pi "
                    "ON pi.purchase_id=l.purchase_id WHERE l.product_id=? AND "
                    "pi.invoice_status='confirmed' ORDER BY pi.invoice_date DESC, pi.purchase_id DESC",
                    (pid,))
        if last:
            card["last_purchase"] = clean(last)
    return clean(card)


def resolve(user, code):
    """Scanned code → product card with the scanned unit selected."""
    from modules import barcode_resolver as BR
    hit = BR.resolve(code)
    if not hit:
        raise MobileError("No product for “%s”." % str(code).strip())
    uid = hit["unit_id"] or (hit.get("unit") or {}).get("unit_id")
    card = product_card(hit["product_id"], uid,
                        show_cost=bool(set(user["modules"]) & {"goods_in"}))
    card["scanned_unit_id"] = uid
    card["scan_qty"] = _f(hit.get("quantity"), 1)
    card["via"] = hit.get("via")
    return card


def search(user, text, limit=15):
    from modules.product_lookup import search_products
    out = []
    for r in search_products(text, limit=limit, active_only=True):
        out.append({"product_id": r["product_id"], "code": r.get("product_code"),
                    "name": r.get("product_name_en"), "name_ar": r.get("product_name_ar") or "",
                    "stock": _f(r.get("stock_quantity")),
                    "price": _f(r.get("unit_price"))})
    return clean(out)


def suppliers(text=""):
    like = "%" + str(text or "") + "%"
    return clean(_all("SELECT TOP 30 supplier_id, supplier_code, supplier_name_en FROM suppliers "
                      "WHERE ISNULL(is_active,1)=1 AND (supplier_name_en LIKE ? OR "
                      "supplier_code LIKE ?) ORDER BY supplier_name_en", (like, like)))


# ── stock moves (same as the desktop Stock Adjustment) ───────
def _move_stock(pid, delta, txn_type, ref_type, note, ref_id=None, set_to=None):
    p = _one("SELECT stock_quantity FROM products WHERE product_id=?", (pid,))
    if not p:
        raise MobileError("Product %s not found." % pid)
    try:                                   # v6.0: a count sets THIS branch's stock
        from modules import stock_branch as _sb
        here_q, cur, _b = _sb.local_qty(pid)
    except Exception:
        _sb, cur = None, _f(p.get("stock_quantity"))
        here_q = cur
    if set_to is not None:
        delta = set_to - here_q
    new = cur + delta
    if abs(delta) < 1e-9:
        return 0.0
    db.execute("UPDATE products SET stock_quantity=ISNULL(stock_quantity,0)+? WHERE product_id=?",
               (delta, pid))
    db.execute("INSERT INTO inventory_transactions (product_id, txn_date, txn_type, "
               "reference_type, reference_id, qty_in_base, qty_out_base, balance_base, notes) "
               "VALUES (?,?,?,?,?,?,?,?,?)",
               (pid, date.today().strftime("%Y-%m-%d"),
                "adjustment_in" if delta > 0 else "adjustment_out", ref_type, ref_id,
                delta if delta > 0 else 0, -delta if delta < 0 else 0, new, (note or "")[:300]))
    if _sb is not None:
        _sb.after_manual_move(pid, delta, "mobile_" + str(ref_type or "move"), ref_id or pid)
    try:
        from modules import doc_posting
        doc_posting.post_stock_adjustment(pid, delta, note[:120] if note else "Mobile",
                                          reference="MOB")
    except Exception:
        pass
    return delta


def _base_qty(ln):
    fac = _f(ln.get("factor"), 0)
    if not fac and ln.get("unit_id"):
        u = _one("SELECT conversion_factor FROM product_units WHERE unit_id=?", (ln["unit_id"],))
        fac = _f((u or {}).get("conversion_factor"), 1)
    return _f(ln.get("qty")) * (fac or 1)


# ── documents from devices ───────────────────────────────────
DOC_TITLES = {"goods_in": "Goods In", "goods_out": "Goods Out", "count": "Stock Count",
              "adjust": "Stock Adjust", "van_sale": "Van Sale"}


def submit(user, doc, source="wifi", device=""):
    """Save a document sent by a device, then apply it (or leave it in the
    office inbox when Settings ▸ Mobile asks for approval).
    doc = {uid, type, header{}, lines[{product_id, unit_id, factor, qty, …}]}"""
    if not isinstance(doc, dict) or not isinstance(doc.get("lines") or [], list) \
            or not isinstance(doc.get("header") or {}, dict):
        raise MobileError("Bad document.")
    dtype = str(doc.get("type") or "")
    module = "van" if dtype == "van_sale" else dtype
    if dtype not in DOC_TITLES:
        raise MobileError("Unknown document type.")
    need(user, module)
    uid = str(doc.get("uid") or "").strip()[:64]
    if not uid:
        raise MobileError("Missing document id.")
    have = _one("SELECT doc_id, status, result, ref_table, ref_id, user_id FROM mobile_docs "
                "WHERE doc_uid=?", (uid,))
    if have and have.get("user_id") not in (None, user["user_id"]):
        raise MobileError("This document id is used by another user.")
    lines = [ln for ln in (doc.get("lines") or []) if isinstance(ln, dict) and ln.get("product_id")]
    head = doc.get("header") or {}
    if have and have.get("status") == "error" and lines:
        # sent again after a failure (product synced, year reopened …): try again
        db.execute("UPDATE mobile_docs SET header_json=?, lines_json=? WHERE doc_id=?",
                   (json.dumps(head, ensure_ascii=False), json.dumps(lines, ensure_ascii=False),
                    have["doc_id"]))
        return apply_doc(have["doc_id"], by_user=user["user_id"])
    if have:                                   # sent twice → same answer, nothing booked twice
        have.pop("user_id", None)
        return clean(dict(have, duplicate=True))
    if not lines:
        raise MobileError("The list is empty.")
    title = DOC_TITLES[dtype]
    if dtype == "goods_out":
        title += " · " + str(head.get("reason") or "")
    elif dtype == "goods_in" and head.get("supplier_name"):
        title += " · " + str(head.get("supplier_name"))
    elif dtype == "van_sale":
        title += " · %s · %.2f" % (head.get("customer_name") or "Cash", _f(head.get("total")))
    db.execute("INSERT INTO mobile_docs (doc_uid, doc_type, source, user_id, device, status, title, "
               "header_json, lines_json) VALUES (?,?,?,?,?,?,?,?,?)",
               (uid, dtype, source, user["user_id"], str(device or "")[:120], "pending",
                title[:200], json.dumps(head, ensure_ascii=False),
                json.dumps(lines, ensure_ascii=False)))
    did = _one("SELECT doc_id FROM mobile_docs WHERE doc_uid=?", (uid,))["doc_id"]
    approve = cfg.flag("mobile_approve_stock", False) and dtype in ("goods_out", "count", "adjust")
    if dtype == "count" and cfg.flag("count_needs_approval", True):     # v6.4: owner approves counts
        approve = True
    if approve:
        return {"doc_id": did, "status": "pending",
                "result": "Sent — waiting for approval in DayBill."}
    return apply_doc(did, by_user=user["user_id"])


def apply_doc(doc_id, by_user=None):
    d = _one("SELECT * FROM mobile_docs WHERE doc_id=?", (doc_id,))
    if not d:
        raise MobileError("Document not found.")
    if d["status"] == "applied":
        return clean({"doc_id": doc_id, "status": "applied", "result": d.get("result"),
                      "ref_table": d.get("ref_table"), "ref_id": d.get("ref_id")})
    head = json.loads(d.get("header_json") or "{}")
    lines = json.loads(d.get("lines_json") or "[]")
    t = d["doc_type"]
    note_who = "%s (%s)" % (DOC_TITLES[t], d.get("device") or "mobile")
    ref_table, ref_id = None, None
    try:
        # the document and its "applied" mark are ONE transaction (v5.27):
        # a failure keeps nothing, so a re-send can never book it twice
        with db.transaction():
            if t == "goods_in":
                ref_table = "purchase_invoices"
                ref_id, msg = _goods_in(head, lines, d)
            elif t == "goods_out":
                reason = str(head.get("reason") or "Other")
                n = 0
                for ln in lines:
                    n += 1 if _move_stock(ln["product_id"], -abs(_base_qty(ln)), "adjustment_out",
                                          "mobile", "%s: %s" % (note_who, reason), doc_id) else 0
                msg = "%d item(s) taken out of stock (%s)." % (n, reason)
            elif t == "count":                 # v6.4: every counted line is logged
                from modules import cycle_count as CC
                a_, n, _r = CC.apply_lines(d, None, by_user)
                msg = "%d product(s) counted, %d changed." % (a_, n)
            elif t == "adjust":
                n = 0
                for ln in lines:
                    n += 1 if _move_stock(ln["product_id"], _base_qty(ln) * (1 if _f(ln.get("sign"), 1) >= 0 else -1),
                                          "adjust", "mobile",
                                          "%s: %s" % (note_who, ln.get("note") or head.get("note") or ""),
                                          doc_id) else 0
                msg = "%d item(s) adjusted." % n
            elif t == "van_sale":
                ref_table = "sales_invoices"
                ref_id, msg = _van_sale(head, lines, d)
            else:
                raise MobileError("Unknown document type.")
            db.execute("UPDATE mobile_docs SET status='applied', result=?, ref_table=?, ref_id=?, "
                       "applied_at=GETDATE(), applied_by=? WHERE doc_id=?",
                       (msg[:400], ref_table, ref_id, by_user, doc_id))
        try:
            from modules import audit
            audit.log("add", "mobile", doc_id, "%s — %s" % (d.get("title"), msg))
        except Exception:
            pass
        return {"doc_id": doc_id, "status": "applied", "result": msg,
                "ref_table": ref_table, "ref_id": ref_id}
    except MobileError as e:
        db.execute("UPDATE mobile_docs SET status='error', result=? WHERE doc_id=?",
                   (str(e)[:400], doc_id))
        raise
    except Exception as e:
        db.execute("UPDATE mobile_docs SET status='error', result=? WHERE doc_id=?",
                   (str(e)[:400], doc_id))
        raise MobileError("Could not save: %s" % str(e)[:200])


def reject_doc(doc_id, why="", by_user=None):
    db.execute("UPDATE mobile_docs SET status='rejected', result=?, applied_by=?, "
               "applied_at=GETDATE() WHERE doc_id=? AND status IN ('pending','error')",
               (("Rejected: " + why)[:400], by_user, doc_id))


def doc_status(user, uid):
    d = _one("SELECT doc_id, doc_type, status, result, ref_table, ref_id, created_at "
             "FROM mobile_docs WHERE doc_uid=? AND user_id=?", (uid, user["user_id"]))
    return clean(d or {"status": "unknown"})


def my_docs(user, limit=30):
    return clean(_all("SELECT TOP %d doc_id, doc_uid, doc_type, status, title, result, created_at "
                      "FROM mobile_docs WHERE user_id=? ORDER BY doc_id DESC" % int(limit),
                      (user["user_id"],)))


def inbox(status=None, limit=200):
    where = "WHERE d.status=?" if status else ""
    p = (status,) if status else ()
    return clean(_all("SELECT TOP %d d.*, u.username FROM mobile_docs d LEFT JOIN users u "
                      "ON u.user_id=d.user_id %s ORDER BY d.doc_id DESC" % (int(limit), where), p))


# ── Goods In → draft purchase ─────────────────────────────────
def _goods_in(head, lines, d):
    from modules.doc_numbering import next_number
    sid = head.get("supplier_id")
    s = _one("SELECT * FROM suppliers WHERE supplier_id=?", (sid,)) if sid else None
    if not s:
        s = _one("SELECT * FROM suppliers WHERE supplier_code IN ('CASH','S-CASH') OR "
                 "supplier_name_en LIKE 'Cash%' ORDER BY supplier_id")
    if not s:
        raise MobileError("Choose a supplier.")
    pnum = next_number("purchase_invoices", "invoice_number",
                       str(cfg.get("purchase_prefix") or "PI").strip() or "PI")
    vat_on = cfg.flag("vat_enabled", True) and cfg.flag("apply_vat_purchase", True)
    rows = []
    for ln in lines:
        p = _product_or_fail(ln)
        u = _one("SELECT unit_name_en, conversion_factor, purchase_price FROM product_units "
                 "WHERE unit_id=?", (ln.get("unit_id"),)) if ln.get("unit_id") else None
        fac = _f((u or {}).get("conversion_factor"), _f(ln.get("factor"), 1)) or 1
        cost = _f(ln.get("cost")) or _f((u or {}).get("purchase_price")) or \
            _f(p.get("purchase_price")) * fac
        rate = _vat_rate(p) if vat_on else 0.0
        qty = _f(ln.get("qty"))
        if not (0 < qty < 1e6 and 0 <= cost < 1e7):    # also NaN / infinity
            raise MobileError("Bad quantity or cost for %s." % p.get("product_code"))
        from modules.doc_math import r2              # half up, like the windows
        amt = r2(qty * cost)
        vat = r2(amt * rate / 100.0)
        rows.append(dict(product_id=p["product_id"], product_code=p.get("product_code"),
                         product_name_en=p.get("product_name_en"),
                         unit=(u or {}).get("unit_name_en") or ln.get("unit") or
                         p.get("unit_of_measure_en") or "PCs",
                         qty=qty, cost=cost, amt=amt, vat_category_id=p.get("vat_category_id"),
                         rate=rate, vat=vat, total=round(amt + vat, 2)))
    if not rows:
        raise MobileError("No valid items.")
    from modules.doc_math import doc_totals     # v6.9.2: VAT once per rate
    T = doc_totals(rows, False, net="amt", vat="vat", total="total", rate="rate")
    sub, vat, total = T["taxable"], T["vat"], T["total"]
    note = "From %s (mobile) — check prices, then Confirm." % (d.get("device") or "PDT")
    db.execute("INSERT INTO purchase_invoices (invoice_number, supplier_invoice_no, invoice_date, "
               "supplier_id, supplier_name_en, supplier_name_ar, supplier_vat_no, payment_method, "
               "subtotal_amount, taxable_amount, vat_amount, total_amount, invoice_status, "
               "payment_status, paid_amount, notes_en, created_by) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (pnum, str(head.get("supplier_invoice") or "")[:50] or None,
                date.today().strftime("%Y-%m-%d"), s["supplier_id"], s.get("supplier_name_en"),
                s.get("supplier_name_ar") or "", s.get("vat_registration_no") or "", "credit",
                sub, sub, vat, total, "draft", "unpaid", 0, note, d.get("user_id")))
    pid = _one("SELECT purchase_id FROM purchase_invoices WHERE invoice_number=?", (pnum,))["purchase_id"]
    for i, r in enumerate(rows, 1):
        db.execute("INSERT INTO purchase_invoice_lines (purchase_id, line_number, product_id, "
                   "product_code, product_name_en, quantity, unit_of_measure_en, unit_price, "
                   "line_amount, vat_category_id, vat_rate, vat_amount, line_total) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (pid, i, r["product_id"], r["product_code"], r["product_name_en"], r["qty"],
                    r["unit"], r["cost"], r["amt"], r["vat_category_id"], r["rate"], r["vat"],
                    r["total"]))
    if cfg.flag("mobile_goods_in_confirm", False):
        from modules import doc_posting
        db.execute("UPDATE purchase_invoices SET invoice_status='confirmed' WHERE purchase_id=?", (pid,))
        _posted_or_fail("purchase", pid)
        return pid, "Purchase %s confirmed — stock added (%d item(s))." % (pnum, len(rows))
    return pid, ("Purchase %s saved as DRAFT (%d item(s)). Office: Purchases ▸ open it, "
                 "check prices ▸ Confirm → stock goes in." % (pnum, len(rows)))


# ── Van sale → confirmed sales invoice ────────────────────────
def _van_sale(head, lines, d):
    incl = _price_incl()
    vat_on = cfg.flag("vat_enabled", True) and cfg.flag("apply_vat_pos", True)
    cust = _one("SELECT * FROM customers WHERE customer_id=?", (head.get("customer_id"),)) \
        if head.get("customer_id") else None
    if str(head.get("payment") or "cash").lower() == "credit" and not cust:
        raise MobileError("Choose the customer for a credit bill.")
    when = _check_date(head)
    if not cust:
        cust = _one("SELECT * FROM customers WHERE customer_code='WALKIN' OR "
                    "customer_name_en LIKE 'Walk%' OR customer_name_en LIKE 'Cash%' "
                    "ORDER BY customer_id") or {}
    rows = []
    for ln in lines:
        p = _product_or_fail(ln)
        rate = _vat_rate(p) if vat_on else 0.0
        vc = _one("SELECT category_code FROM vat_categories WHERE vat_category_id=?",
                  (p.get("vat_category_id"),)) or {}
        qty, price = _f(ln.get("qty")), _f(ln.get("price"))
        disc = _f(ln.get("discount"))
        if not (0 < qty < 1e6 and 0 <= price < 1e7 and 0 <= disc <= qty * price):
            raise MobileError("Bad quantity, price or discount for %s." % p.get("product_code"))
        gross = qty * price - disc
        if incl and rate:
            taxable = gross / (1 + rate / 100.0)
            vat = gross - taxable
            total = gross
        else:
            taxable = gross
            vat = gross * rate / 100.0
            total = gross + vat
        rows.append(dict(product_id=p["product_id"], product_code=p.get("product_code") or "",
                         product_name_en=p.get("product_name_en"),
                         product_name_ar=p.get("product_name_ar") or "",
                         unit=ln.get("unit") or "PCs", qty=qty, price=price, disc=round(disc, 2),
                         taxable=taxable, vat_category_id=p.get("vat_category_id"),
                         vat_code=vc.get("category_code") or "S", rate=rate,
                         vat=vat, total=total))           # rounded below (round_lines)
    if not rows:
        raise MobileError("No valid items.")
    # v6.9.2: same maths as the Sales Invoice window — each line adds up in
    # halalas, the bill's VAT is worked out once per rate (the ZATCA way)
    from modules.doc_math import doc_totals, round_lines
    keys = dict(net="taxable", vat="vat", total="total")
    rows = round_lines(rows, **keys)
    T = doc_totals(rows, incl, rate="rate", code="vat_code", **keys)
    gross, vat, total = T["taxable"], T["vat"], T["total"]
    printed = round(_f(head.get("total")), 2)
    if printed and abs(printed - total) >= 0.005:
        # the van printed its own total (its rounding): the books follow the
        # paper bill, the difference spread over the lines BEFORE VAT — a
        # real mismatch is not booked but waits in the office Inbox
        if abs(printed - total) > 1.0:
            raise MobileError("Van total %.2f does not match its lines %.2f — not booked."
                              % (printed, total))
        from modules.doc_math import spread_bill_adjustment
        L = [dict(r, line_amount=r["taxable"], vat_amount=r["vat"], line_total=r["total"],
                  discount_amount=r["disc"], quantity=r["qty"], unit_price=r["price"]) for r in rows]
        L = spread_bill_adjustment(L, round(total - printed, 2), incl)
        rows = [dict(r, taxable=o["line_amount"], vat=o["vat_amount"], total=o["line_total"],
                     disc=round(o["discount_amount"], 2)) for r, o in zip(rows, L)]
        T = doc_totals(rows, incl, rate="rate", code="vat_code", **keys)
        vat, total = T["vat"], printed
        gross = round(total - vat, 2)
    pay = str(head.get("payment") or "cash").lower()
    cash_amt = card_amt = 0.0
    if pay == "credit":
        from modules import credit_check        # Settings ▸ Customer ▸ Credit limit
        st, msg = credit_check.check(cust.get("customer_id"), total)
        if st == "block":
            raise MobileError(msg or "Over the customer's credit limit — not booked.")
        paid, status = 0.0, "unpaid"
    else:
        paid, status = total, "paid"
        if pay == "card":
            card_amt = total
        else:
            pay, cash_amt = "cash", total
    num = db.get_next_invoice_number("SALES")
    db.execute("INSERT INTO sales_invoices (invoice_number, invoice_date, customer_id, "
               "customer_name_en, customer_name_ar, customer_country_code, subtotal_amount, "
               "discount_amount, taxable_amount, vat_amount, total_amount, payment_method, "
               "payment_status, paid_amount, invoice_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (num, when, cust.get("customer_id"), cust.get("customer_name_en") or "Cash Customer",
                cust.get("customer_name_ar") or "", "SA", gross,
                round(sum(r["disc"] for r in rows), 2), gross, vat, total, pay, status, paid,
                "confirmed"))
    iid = _one("SELECT invoice_id FROM sales_invoices WHERE invoice_number=?", (num,))["invoice_id"]
    for i, r in enumerate(rows, 1):
        db.execute("INSERT INTO sales_invoice_lines (invoice_id, line_number, product_id, "
                   "product_code, product_name_en, product_name_ar, quantity, unit_of_measure_en, "
                   "unit_price, discount_amount, line_amount, vat_category_id, vat_category_code, "
                   "vat_rate, vat_amount, line_total) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (iid, i, r["product_id"], r["product_code"], r["product_name_en"],
                    r["product_name_ar"], r["qty"], r["unit"], r["price"], r["disc"], r["taxable"],
                    r["vat_category_id"], r["vat_code"], r["rate"], r["vat"], r["total"]))
    for col, val in (("sale_channel", "VAN"), ("van_ref", str(head.get("number") or "")[:40]),
                     ("cash_paid", cash_amt), ("card_paid", card_amt),
                     ("created_by", d.get("user_id"))):
        try:
            db.execute("UPDATE sales_invoices SET %s=? WHERE invoice_id=?" % col, (val, iid))
        except Exception:
            pass
    try:
        from modules.zatca.qr_generator import (generate_zatca_qr, seller_name,
                                                clean_vat_number)
        c = _one("SELECT * FROM company") or {}
        stamp = str(head.get("time") or "") or datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        tlv = generate_zatca_qr(seller_name(c), clean_vat_number(c.get("vat_registration_no", "")),
                                stamp, "%.2f" % total, "%.2f" % vat)
        db.execute("UPDATE sales_invoices SET qr_code_data=? WHERE invoice_id=?", (tlv, iid))
    except Exception:
        pass
    try:            # a van is not this PC's till: its cash is not in this drawer
        from modules import branches as _br
        _b, _c = _br.current()
        if _b:
            db.execute("UPDATE sales_invoices SET branch_id=?, counter_id=NULL "
                       "WHERE invoice_id=?", (_b, iid))
    except Exception:
        pass
    warn = _posted_or_fail("sales", iid, tenders={"cash": cash_amt, "bank": card_amt})
    try:
        from modules.zatca import egs as _zegs
        _zegs.after_save("sales", iid)
    except Exception:
        pass
    return iid, "Sales invoice %s (van bill %s) · %.2f%s" % (
        num, head.get("number") or "-", total, (" · ⚠ " + warn[:120]) if warn else "")


# ── what a van takes on the road ──────────────────────────────
def van_catalog(van_user_id=None):
    """Products (every unit with its barcodes + price), customers and the
    shop details — everything a van needs to sell with no signal."""
    from modules import barcode_resolver as BR
    prods = []
    extras = {}
    for r in _all("SELECT product_id, unit_id, barcode FROM product_unit_barcodes "
                  "WHERE ISNULL(is_active,1)=1"):
        extras.setdefault((r["product_id"], r["unit_id"]), []).append(r["barcode"])
    for p in _all("SELECT product_id FROM products WHERE ISNULL(is_active,1)=1 "
                  "AND ISNULL(product_type,'product') IN ('product','service') ORDER BY product_name_en"):
        try:
            rows = BR.label_rows(p["product_id"])
        except Exception:
            continue
        if not rows:
            continue
        r0 = rows[0]
        dflt = {u["unit_id"]: bool(u.get("is_default")) for u in BR.units_of(p["product_id"])}
        units = []
        for r in rows:
            bcs = [b for b in [r.get("barcode_value")] if b]
            bcs += extras.get((p["product_id"], r.get("unit_id")), [])
            units.append({"unit_id": r.get("unit_id"), "unit": r.get("unit_name") or "PCs",
                          "factor": _f(r.get("factor"), 1), "price": round(_f(r.get("unit_price")), 2),
                          "price_vat": _f(r.get("price_vat")), "barcodes": bcs,
                          "default": dflt.get(r.get("unit_id"), False)})
        prods.append({"id": p["product_id"], "code": r0.get("product_code"),
                      "name": r0.get("product_name_en"), "name_ar": r0.get("product_name_ar") or "",
                      "vat": _f(r0.get("vat_rate"), 15), "stock": _f(r0.get("stock_quantity")),
                      "units": units})
    custs = _all("SELECT c.customer_id, c.customer_code, c.customer_name_en, c.customer_name_ar, "
                 "c.vat_registration_no, c.phone, ISNULL(c.credit_limit,0) AS credit_limit "
                 "FROM customers c WHERE ISNULL(c.is_active,1)=1 ORDER BY c.customer_name_en")
    bal = {}
    for r in _all("SELECT customer_id, balance_due FROM vw_customer_balance"):
        bal[r["customer_id"]] = _f(r.get("balance_due"))
    for c in custs:
        c["balance"] = bal.get(c["customer_id"], 0.0)
    return clean({"version": datetime.now().strftime("%Y%m%d%H%M%S"), "products": prods,
                  "customers": custs, "company": company(), "settings": app_settings()})
