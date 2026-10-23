# ============================================================
# DayBill ERP - ZATCA Phase 2: connection, signing at save, send queue
# ------------------------------------------------------------
#   connect()      one call does everything: key + CSR → compliance CSID
#                  (OTP) → 6 test documents → production CSID → saved
#   after_save()   called right after a sale / POS bill / return is saved:
#                  next counter (ICV) + previous hash (PIH), UBL XML,
#                  signature + Phase 2 QR (simplified) — the bill prints
#                  with the Phase 2 QR straight away
#   send_*()       report (B2C) / clear (B2B) the waiting documents —
#                  in the background, retried when the internet is back
#   locked()       a document already in the ZATCA chain can't be edited
# All network work is separate from database work so the UI can do the
# network part in a thread (pyodbc stays in the main thread).
# ============================================================

import base64
import json
from datetime import datetime, date, time as dtime

from modules.zatca import phase2 as P

try:                                       # the one app version (config/version.py)
    from config.version import VERSION as APP_VERSION
except Exception:
    APP_VERSION = "7.9.0"
LOG = []                                  # recent events for the ZATCA screen


def _db():
    from config.database import db
    return db


def log(msg):
    LOG.append((datetime.now().strftime("%H:%M:%S"), msg))
    del LOG[:-200]


def tables_ready():
    try:
        _db().fetchone("SELECT TOP 1 egs_id FROM zatca_egs")
        return True
    except Exception:
        return False


# ── shop + EGS ───────────────────────────────────────────────
def company():
    try:
        return dict(_db().fetchone("SELECT * FROM company WHERE company_id=1") or {})
    except Exception:
        return {}


def this_counter():
    """counter_id of THIS PC (Settings ▸ Branches & counters) or None."""
    try:
        from modules import branches
        return branches.current()[1]
    except Exception:
        return None


def _has_counter_col():
    try:
        _db().fetchone("SELECT TOP 1 counter_id FROM zatca_egs")
        return True
    except Exception:
        return False


def active(counter_id="this"):
    """The EGS (ZATCA unit) THIS PC signs with (dict) or None.
    v6.0: every till can have its own unit (own counter + hash chain, as
    ZATCA expects one unit per device). A till without its own unit uses
    the shop-wide one (counter_id empty) — that is how older versions
    worked, so nothing changes until a till is connected on its own."""
    db = _db()
    try:
        if _has_counter_col():
            cid = this_counter() if counter_id == "this" else counter_id
            if cid:
                r = db.fetchone("SELECT TOP 1 * FROM zatca_egs WHERE is_active=1 AND counter_id=? "
                                "ORDER BY egs_id DESC", (int(cid),))
                if r:
                    return dict(r)
            r = db.fetchone("SELECT TOP 1 * FROM zatca_egs WHERE is_active=1 AND counter_id IS NULL "
                            "ORDER BY egs_id DESC")
            return dict(r) if r else None
        r = db.fetchone("SELECT TOP 1 * FROM zatca_egs WHERE is_active=1 ORDER BY egs_id DESC")
        return dict(r) if r else None
    except Exception:
        return None


def units():
    """Every connected unit (all tills) — for the ZATCA screen."""
    try:
        return [dict(r) for r in _db().fetchall(
            "SELECT * FROM zatca_egs WHERE is_active=1 ORDER BY egs_id") or []]
    except Exception:
        return []


def by_id(egs_id):
    try:
        r = _db().fetchone("SELECT * FROM zatca_egs WHERE egs_id=?", (int(egs_id),))
        return dict(r) if r else None
    except Exception:
        return None


def opened(egs):
    """The EGS with its protected secrets opened (v5.27, modules/zatca/vault).
    Raises vault.VaultLocked when this SQL Server can't open them."""
    if not egs:
        return egs
    from modules.zatca import vault
    return vault.open_row(egs)


def any_connected():
    """Is ANY till connected? (the background sender sends every till's
    waiting documents, each with its own unit)"""
    return any(u.get("status") == "connected" and u.get("pcsid_token") for u in units())


def connected():
    e = active()
    return bool(e and e.get("status") == "connected" and e.get("pcsid_token"))


def seller(comp=None):
    c = comp or company()
    from modules.zatca.qr_generator import clean_vat_number
    crn = str(c.get("cr_number") or "").strip()
    return {"name": (c.get("company_name_ar") or c.get("company_name_en") or "").strip(),
            "vat": clean_vat_number(c.get("vat_registration_no")),
            "crn": crn, "id_scheme": id_scheme(crn, c.get("id_scheme")),
            "street": (c.get("street_name_en") or c.get("street_name_ar") or "").strip(),
            "building": str(c.get("building_number") or "").strip(),
            "district": (c.get("district_en") or c.get("district_ar") or "").strip(),
            "city": (c.get("city_en") or c.get("city_ar") or "").strip(),
            "postal": str(c.get("postal_code") or "").strip(),
            "country": "SA"}


def id_scheme(number, chosen=None):
    """ZATCA scheme of the seller ID (BR-KSA-08): 'CRN' for a commercial
    registration, '700' for the new Unified National Number (10 digits
    starting with 7 — Commercial Register Law 2025)."""
    ch = str(chosen or "").strip().upper()
    if ch in ("CRN", "MOM", "MLS", "700", "SAG", "OTH"):
        return ch
    n = str(number or "").strip()
    if len(n) == 10 and n.isdigit() and n.startswith("7"):
        return "700"
    return "CRN"


DETAIL_FIELDS = [
    # key in company, label, rule
    ("company_name_ar", "Company name (Arabic)", "text"),
    ("company_name_en", "Company name (English)", "text"),
    ("vat_registration_no", "VAT number (15 digits, 3…3)", "vat"),
    ("cr_number", "CR / Unified number (700…)", "crn"),
    ("building_number", "Building number (4 digits)", "building"),
    ("street_name_en", "Street", "text"),
    ("district_en", "District", "text"),
    ("city_en", "City", "text"),
    ("postal_code", "Postal code (5 digits)", "postal"),
]


def check_value(rule, v):
    """'' when fine, else what is wrong (simple English)."""
    from modules.zatca.qr_generator import vat_problem
    v = str(v or "").strip()
    if rule == "vat":
        return vat_problem(v)
    if not v:
        return "missing"
    if rule == "building" and not (v.isdigit() and len(v) == 4):
        return "must be 4 digits (from the national address)"
    if rule == "postal" and not (v.isdigit() and len(v) == 5):
        return "must be 5 digits"
    if rule == "crn" and not (v.isalnum() and len(v) <= 20):
        return "letters / digits only"
    return ""


def detail_problems(comp=None):
    c = comp or company()
    out = []
    for key, label, rule in DETAIL_FIELDS:
        if key == "company_name_en" and (c.get("company_name_ar") or "").strip():
            continue                       # one of the two names is enough
        if key == "company_name_ar" and (c.get("company_name_en") or "").strip():
            continue
        p = check_value(rule, c.get(key))
        if p:
            out.append((key, label, p))
    return out


def save_details(values):
    """Write the details typed in the Connect screen into the company."""
    keys = [k for k, _l, _r in DETAIL_FIELDS if k in values]
    if not keys:
        return
    from modules.zatca.qr_generator import clean_vat_number
    vals = []
    for k in keys:
        v = str(values[k] or "").strip()
        if k == "vat_registration_no":
            v = clean_vat_number(v) or v
        vals.append(v)
    _db().execute("UPDATE company SET " + ", ".join("%s=?" % k for k in keys)
                  + " WHERE company_id=1", tuple(vals))


# ============================================================
# documents → neutral dict for phase2.build_xml
# ============================================================
_TABLES = {
    "sales": ("sales_invoices", "invoice_id", "sales_invoice_lines", "invoice_id"),
    "sales_return": ("sales_returns", "return_id", "sales_return_lines", "return_id"),
}
PAY_CODES = {"cash": "10", "card": "48", "credit_card": "48", "debit_card": "48", "mada": "48",
             "visa": "48", "master": "48", "amex": "48", "apple_pay": "48", "stc_pay": "48",
             "tabby": "ZZZ", "tamara": "ZZZ", "voucher": "ZZZ", "gift": "ZZZ",
             "bank": "42", "transfer": "42", "bank_transfer": "42", "cheque": "20",
             "credit": "30", "on_account": "30", "mixed": "10", "split": "10"}


def payment_codes(row):
    """ZATCA payment means codes of a saved bill — one per way it was paid
    (v6.0: a part-cash / part-card bill says both, not just 'cash')."""
    method = str(row.get("payment_method") or "cash").lower()
    if method not in ("mixed", "split", "multi"):
        return [PAY_CODES.get(method, "10")]
    codes = []
    try:
        from modules import tenders
        for t in tenders.lines_for("sales", row.get("invoice_id")):
            c = PAY_CODES.get(str(t.get("method") or "").lower(), "ZZZ")
            if c not in codes:
                codes.append(c)
    except Exception:
        pass
    if not codes:
        if _f(row.get("cash_paid")) > 0.004:
            codes.append("10")
        if _f(row.get("card_paid")) > 0.004:
            codes.append("48")
    return codes or ["10"]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso_date(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    s = str(v or "").strip()[:10]
    if len(s) == 10 and s[4] == "-":
        return s
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return date.today().isoformat()


def _iso_time(*vals):
    for v in vals:
        if isinstance(v, datetime):
            return v.strftime("%H:%M:%S")
        if isinstance(v, dtime):
            return v.strftime("%H:%M:%S")
        s = str(v or "").strip()
        if len(s) >= 8 and s[2] == ":" and s[5] == ":":
            return s[:8]
        if len(s) >= 19 and s[13] == ":":           # 'YYYY-MM-DD HH:MM:SS'
            return s[11:19]
    return datetime.now().strftime("%H:%M:%S")


def _buyer(cust, vat_hint=""):
    from modules.zatca.qr_generator import valid_vat_number, clean_vat_number
    c = cust or {}
    vat = clean_vat_number(c.get("vat_registration_no") or vat_hint)
    b2b = valid_vat_number(vat)
    code = str(c.get("customer_code") or "").upper()
    name = (c.get("customer_name_ar") or c.get("customer_name_en") or "").strip() \
        if code not in ("WALKIN", "CASH", "") else ""
    if not b2b:
        return {"name": name} if name else {}, False
    return {"name": (c.get("customer_name_ar") or c.get("customer_name_en") or "").strip(),
            "vat": vat,
            "street": (c.get("street_name_en") or c.get("street_name_ar") or c.get("address_en") or "").strip(),
            "building": str(c.get("building_number") or "").strip(),
            "district": (c.get("district_en") or c.get("district_ar") or "").strip(),
            "city": (c.get("city_en") or c.get("city_ar") or "").strip(),
            "postal": str(c.get("postal_code") or "").strip(),
            "country": (c.get("country_code") or "SA").strip() or "SA"}, True


def buyer_problems(b):
    out = []
    for key, label, rule in (("street", "street", "text"), ("building", "building number (4 digits)", "building"),
                             ("district", "district", "text"), ("city", "city", "text"),
                             ("postal", "postal code (5 digits)", "postal")):
        p = check_value(rule, b.get(key))
        if p:
            out.append("customer %s %s" % (label, p))
    return out


def _lines(rows):
    out = []
    for l in rows:
        qty = abs(_f(l.get("quantity")))
        if qty <= 0:
            continue
        rate = _f(l.get("vat_rate"))
        net = abs(_f(l.get("line_amount")))
        tot = abs(_f(l.get("line_total")))
        price = abs(_f(l.get("unit_price")))
        disc = abs(_f(l.get("discount_amount")))
        # was the price / discount typed with VAT (inclusive) or without?
        gross = qty * price - disc
        incl = rate > 0 and abs(gross - tot) < abs(gross - net)
        disc_ex = disc / (1 + rate / 100.0) if incl else disc
        code = (l.get("vat_category_code") or "S").upper()[:1]
        vatex = None
        if code in ("Z", "E", "O"):
            vatex = _vatex_for(code)
        out.append({"name": (l.get("product_name_en") or l.get("product_name_ar") or "Item").strip(),
                    "qty": qty, "unit_code": "PCE", "net_amount": net, "discount": round(disc_ex, 2),
                    "vat_code": code if code in ("S", "Z", "E", "O") else "S", "vat_rate": rate,
                    "vatex": vatex})
    return out


def _vatex_for(code):
    try:
        from config import settings as cfg
        key = {"Z": "zatca_vatex_z", "E": "zatca_vatex_e", "O": "zatca_vatex_o"}[code]
        want = str(cfg.get(key, "") or "")
        if code == "Z" and want == "VATEX-SA-36" and not cfg.flag("zatca_vatex_v692", False):
            # before v6.9.2 SA-36 was wrongly labelled "medicines" (it is
            # qualifying metals): a shop that picked it meant SA-35
            want = "VATEX-SA-35"
            cfg.set(key, want)
            cfg.set("zatca_vatex_v692", True)
            try:
                cfg.save_settings()
            except Exception:
                pass
        hit = next((c for c in P.VATEX_CHOICES if c[0] == want), None)
        if hit:
            return hit
    except Exception:
        pass
    return P.VATEX.get(code)


def build_doc(kind, doc_id, comp=None):
    """(doc dict, problems[]) for a saved sale / return."""
    db = _db()
    table, pk, ltable, lfk = _TABLES[kind]
    row = dict(db.fetchone("SELECT * FROM %s WHERE %s=?" % (table, pk), (doc_id,)) or {})
    if not row:
        return None, ["document not found"]
    lines = [dict(r) for r in db.fetchall(
        "SELECT * FROM %s WHERE %s=? ORDER BY line_number" % (ltable, lfk), (doc_id,)) or []]
    cust = {}
    if row.get("customer_id"):
        cust = dict(db.fetchone("SELECT * FROM customers WHERE customer_id=?",
                                (row["customer_id"],)) or {})
    buyer, b2b = _buyer(cust, row.get("customer_vat_no") or "")
    problems = []
    if b2b:
        problems += buyer_problems(buyer)
    c = comp or company()
    # v6.9.2: shop details changed after connecting (e.g. building number "12")
    # → held as 'fix', no counter used, instead of a bill ZATCA will reject
    problems += ["shop %s %s" % (lbl, p) for _k, lbl, p in detail_problems(c)]
    uuid = str(row.get("zatca_uuid") or row.get("invoice_uuid") or "").strip().lower()
    if len(uuid) != 36:
        uuid = P.new_uuid()
    if kind == "sales" and str(row.get("invoice_kind") or "").lower() == "debit":
        # v6.0: debit note — a price raised / something added after the invoice
        number, d_, t_ = row.get("invoice_number"), row.get("invoice_date"), row.get("invoice_time")
        type_code = P.TYPE_DEBIT
        ref = ("Invoice %s" % row["original_invoice_no"]) if row.get("original_invoice_no") \
            else "Not specified"
        reason = (row.get("debit_reason") or row.get("notes_en") or "Price adjustment").strip()[:200]
    elif kind == "sales":
        number, d_, t_ = row.get("invoice_number"), row.get("invoice_date"), row.get("invoice_time")
        type_code, ref, reason = P.TYPE_INVOICE, None, None
    else:
        number, d_, t_ = row.get("return_number"), row.get("return_date"), None
        type_code = P.TYPE_CREDIT
        ref = ("Invoice %s" % row["original_invoice_no"]) if row.get("original_invoice_no") \
            else "Not specified"
        reason = (row.get("notes_en") or "Goods returned by the customer").strip()[:200]
    issue_date = _iso_date(d_)
    doc = {"number": str(number or doc_id), "uuid": uuid, "issue_date": issue_date,
           "issue_time": _iso_time(t_, row.get("created_at")),
           "type_code": type_code, "subtype": P.SUB_STANDARD if b2b else P.SUB_SIMPLIFIED,
           "seller": seller(c), "buyer": buyer,
           "payment_code": payment_codes(row)[0], "payment_codes": payment_codes(row),
           "billing_ref": ref, "reason": reason,
           "delivery_date": issue_date if b2b else None,
           "lines": _lines(lines), "total": abs(_f(row.get("total_amount")))}
    if not doc["lines"]:
        problems.append("no lines")
    return doc, problems


# ============================================================
# signing at save
# ============================================================
def locked(kind, doc_id):
    """True when the document is already in the ZATCA chain."""
    table, pk = _TABLES[kind][0], _TABLES[kind][1]
    try:
        r = _db().fetchone("SELECT zatca_icv FROM %s WHERE %s=?" % (table, pk), (doc_id,))
        return bool(r and r.get("zatca_icv"))
    except Exception:
        return False


LOCK_TEXT = ("This document is already signed for ZATCA (e-invoicing Phase 2), so it "
             "cannot be changed or deleted.\n\nMake a Sales Return (credit note) for it instead.")


class _CounterTaken(Exception):
    """Another till used the counter first."""


def _reload(egs):
    try:
        r = _db().fetchone("SELECT * FROM zatca_egs WHERE egs_id=?", (egs["egs_id"],))
        return dict(r) if r else active()
    except Exception:
        return active()


def prepare(kind, doc_id, egs=None):
    """Put a saved document into the ZATCA chain: ICV + PIH, XML, sign
    (simplified) and store. Returns the stored state or None (not connected)."""
    egs = egs or active()
    if not egs or egs.get("status") != "connected":
        return None
    table, pk = _TABLES[kind][0], _TABLES[kind][1]
    db = _db()
    if locked(kind, doc_id):
        return {"status": "already"}
    comp = company()
    for _try in range(5):                        # another till may take the same number
        doc, problems = build_doc(kind, doc_id, comp)
        if doc is None:
            return None
        if problems:
            # wrong / missing data (e.g. B2B customer address): hold it OUT of
            # the chain until fixed — no counter used, nothing signed yet
            db.execute("UPDATE %s SET zatca_status='fix', zatca_kind=?, zatca_last_error=? "
                       "WHERE %s=?" % (table, pk),
                       ("simplified" if doc["subtype"] == P.SUB_SIMPLIFIED else "standard",
                        ("Fix before sending: " + "; ".join(problems))[:2000], doc_id))
            log("✋ %s %s held: %s" % ("Bill" if kind == "sales" else "Return", doc["number"],
                                      "; ".join(problems)[:150]))
            return {"status": "fix", "problems": problems}
        icv = int(egs.get("icv") or 0) + 1
        pih = egs.get("last_hash") or P.GENESIS_PIH
        doc["icv"], doc["pih"] = icv, pih
        xml = P.build_xml(doc)
        simplified = doc["subtype"] == P.SUB_SIMPLIFIED
        if simplified:
            cert = P.cert_b64_from_token(egs["pcsid_token"])
            s = P.sign_xml(xml, cert, opened(egs)["private_key"])
        else:
            s = P.unsigned_payload(xml)
        status = "waiting"
        # counter + document change together: never a used counter without
        # its signed document (savepoint inside the bill's save — v5.27)
        try:
            with db.savepoint():
                n = db.execute("UPDATE zatca_egs SET icv=?, last_hash=? WHERE egs_id=? AND icv=?",
                               (icv, s["hash"], egs["egs_id"], int(egs.get("icv") or 0)))
                if n == 0:
                    raise _CounterTaken()
                db.execute(
                    "UPDATE %s SET zatca_uuid=?, zatca_icv=?, zatca_kind=?, zatca_egs_id=?, "
                    "zatca_invoice_hash=?, zatca_previous_hash=?, zatca_signed_xml=?, "
                    "zatca_qr_phase2=?, zatca_status=?, zatca_attempts=0, zatca_last_error=? "
                    "WHERE %s=?" % (table, pk),
                    (doc["uuid"], icv, "simplified" if simplified else "standard", egs["egs_id"],
                     s["hash"], pih, s["xml"], s["qr"] or None, status, None, doc_id))
        except _CounterTaken:                    # taken — reload and build again
            egs = _reload(egs)
            continue
        log("%s %s signed (ICV %d, %s)" % ("Bill" if kind == "sales" else "Return",
                                          doc["number"], icv, "B2C" if simplified else "B2B"))
        return {"status": status, "icv": icv, "hash": s["hash"], "qr": s["qr"],
                "simplified": simplified, "problems": problems}
    raise RuntimeError("Could not get the next ZATCA counter — try again.")


def after_save(kind, doc_id):
    """Hook for POS / Sales / Returns: never stops the sale."""
    try:
        if not connected():
            return None
        r = prepare(kind, doc_id)
        try:
            from ui import zatca_sender
            zatca_sender.kick()
        except Exception:
            pass
        return r
    except Exception as e:
        log("⚠ could not sign %s %s: %s" % (kind, doc_id, str(e)[:150]))
        try:        # v6.9.2: shown in the ZATCA list as 'fix' — not silently left out
            table, pk = _TABLES[kind][0], _TABLES[kind][1]
            _db().execute("UPDATE %s SET zatca_status='fix', zatca_last_error=? WHERE %s=? "
                          "AND zatca_icv IS NULL" % (table, pk),
                          (("Could not sign: %s" % e)[:2000], doc_id))
        except Exception:
            pass
        return None


def rebuild(kind, doc_id):
    """A rejected document (e.g. customer address fixed): sign it again
    with the next counter and send again."""
    table, pk = _TABLES[kind][0], _TABLES[kind][1]
    _db().execute("UPDATE %s SET zatca_icv=NULL, zatca_status=NULL, zatca_signed_xml=NULL, "
                  "zatca_qr_phase2=NULL, zatca_last_error=NULL WHERE %s=?" % (table, pk), (doc_id,))
    return prepare(kind, doc_id)


# ============================================================
# sending (network part separated from DB part)
# ============================================================
def next_items(limit=20):
    """Waiting documents, oldest counter first."""
    out = []
    for kind, (table, pk, _l, _f2) in _TABLES.items():
        try:
            rows = _db().fetchall(
                "SELECT TOP %d %s AS id, %s AS number, zatca_icv, zatca_uuid, zatca_invoice_hash, "
                "zatca_signed_xml, zatca_kind, zatca_egs_id FROM %s WHERE zatca_status='waiting' "
                "AND zatca_icv IS NOT NULL ORDER BY zatca_icv"
                % (limit, pk, "invoice_number" if kind == "sales" else "return_number", table)) or []
        except Exception:
            rows = []
        for r in rows:
            if not r.get("zatca_signed_xml"):
                continue
            out.append({"kind": kind, "id": r["id"], "icv": r["zatca_icv"], "number": r.get("number"),
                        "egs_id": r.get("zatca_egs_id"),
                        "simplified": r.get("zatca_kind") != "standard",
                        "payload": {"invoiceHash": r["zatca_invoice_hash"], "uuid": r["zatca_uuid"],
                                    "invoice": base64.b64encode(
                                        r["zatca_signed_xml"].encode("utf-8")).decode()}})
    out.sort(key=lambda x: (x.get("egs_id") or 0, x["icv"]))
    seen, uniq = set(), []
    for it in out:
        k = (it["kind"], it["id"])
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq[:limit]


def unit_for(item, egs=None):
    """The unit that signed this document (each till sends with its own
    certificate). DB only — call before the network part."""
    want = item.get("egs_id")
    if want and (not egs or egs.get("egs_id") != want):
        egs = by_id(want) or egs
    return opened(egs)


def send_one(egs, item):
    """NETWORK ONLY: report / clear one document → (http status, data).
    `egs` should come from unit_for(item) (secrets opened)."""
    from modules.zatca import vault
    if egs and vault.is_locked_value(egs.get("pcsid_secret")):
        try:
            egs = vault.open_row(egs)
        except Exception as e:
            return 0, {"message": str(e)}
    env, tok, sec = egs["env"], egs["pcsid_token"], egs["pcsid_secret"]
    try:
        if item["simplified"]:
            return P.api_report(env, tok, sec, item["payload"])
        st, d = P.api_clear(env, tok, sec, item["payload"])
        if st == 303:                              # clearance switched off → report
            return P.api_report(env, tok, sec, item["payload"])
        return st, d
    except P.ApiError as e:
        return 0, {"message": str(e)}


def apply_result(item, status, data):
    """DB ONLY: store ZATCA's answer. Returns the new status text."""
    table, pk = _TABLES[item["kind"]][0], _TABLES[item["kind"]][1]
    errs, warns = P.messages(data)
    resp = json.dumps(data, ensure_ascii=False)[:8000]
    db = _db()
    # v6.0 (ZATCA duplicate check, Aug 2025):
    #   reporting 409 = this invoice was ALREADY reported successfully → done
    #   clearance 208 = this hash was already cleared → done (cleared XML comes back)
    #   clearance 409 = a real conflict → NOT cleared: kept for a look
    dup = (item["simplified"] and status == 409) or (not item["simplified"] and status == 208)
    if not item["simplified"] and status == 409:
        db.execute("UPDATE %s SET zatca_status='rejected', zatca_response=?, zatca_last_error=?, "
                   "zatca_submitted_at=GETDATE() WHERE %s=?" % (table, pk),
                   (resp, ("ZATCA answered 409 (conflict) — not cleared: %s"
                           % ("; ".join(errs) or data.get("message") or "check the invoice"))[:2000],
                    item["id"]))
        log("❌ Bill %s NOT cleared (409 conflict)" % (item.get("number") or item["id"]))
        return "rejected"
    if status in (200, 202) or dup:
        new = "reported" if item["simplified"] else "cleared"
        if dup:
            warns = list(warns) + ["ZATCA: already %s earlier (HTTP %s) — not counted twice"
                                   % (new, status)]
        cleared_xml, qr = None, None
        if data.get("clearedInvoice"):
            try:
                cleared_xml = base64.b64decode(data["clearedInvoice"]).decode("utf-8")
                qr = P.qr_from_xml(cleared_xml) or None
            except Exception:
                cleared_xml = None
        db.execute("UPDATE %s SET zatca_status=?, zatca_warnings=?, zatca_response=?, "
                   "zatca_submitted_at=GETDATE(), zatca_last_error=NULL, "
                   "zatca_cleared_xml=COALESCE(?, zatca_cleared_xml), "
                   "zatca_qr_phase2=COALESCE(?, zatca_qr_phase2) WHERE %s=?" % (table, pk),
                   (new, "\n".join(warns)[:4000] or None, resp, cleared_xml, qr, item["id"]))
        log("✅ %s %s %s%s" % ("Bill" if item["kind"] == "sales" else "Credit note",
                               item.get("number") or item["id"], new.upper(),
                               " (with warnings)" if warns else ""))
        return new
    if status == 400:
        db.execute("UPDATE %s SET zatca_status='rejected', zatca_response=?, zatca_warnings=?, "
                   "zatca_last_error=?, zatca_submitted_at=GETDATE() WHERE %s=?" % (table, pk),
                   (resp, "\n".join(warns)[:4000] or None, ("; ".join(errs) or "Rejected")[:2000],
                    item["id"]))
        log("❌ %s %s REJECTED: %s" % ("Bill" if item["kind"] == "sales" else "Credit note",
                                      item.get("number") or item["id"], "; ".join(errs)[:200]))
        return "rejected"
    # 0 (no internet), 401/403 (certificate), 429, 5xx → try again later
    msg = data.get("message") or "; ".join(errs) or ("HTTP %s" % status)
    if status in (401, 403):
        msg = "ZATCA did not accept DayBill's certificate (%s). Open ZATCA ▸ Reconnect." % status
    db.execute("UPDATE %s SET zatca_attempts=COALESCE(zatca_attempts,0)+1, zatca_last_error=? "
               "WHERE %s=?" % (table, pk), (("Waiting: " + str(msg))[:2000], item["id"]))
    log("⏳ %s %s not sent yet: %s" % ("Bill" if item["kind"] == "sales" else "Credit note",
                                      item.get("number") or item["id"], str(msg)[:150]))
    return "waiting"


def send_pending_sync(limit=50):
    """Send everything now, in this thread (tests / 'Send now' fallback)."""
    if not any_connected():
        return {}
    done = {}
    for item in next_items(limit):
        try:
            st, d = send_one(unit_for(item, active()), item)
        except Exception as e:                         # key can't be opened
            st, d = 0, {"message": str(e)[:300]}
        new = apply_result(item, st, d)
        done[new] = done.get(new, 0) + 1
        if new == "waiting" and st == 0:
            break                                    # no internet — stop for now
    return done


def stats():
    out = {"waiting": 0, "reported": 0, "cleared": 0, "rejected": 0, "fix": 0}
    for kind, (table, pk, _l, _f2) in _TABLES.items():
        try:
            rows = _db().fetchall("SELECT zatca_status AS s, COUNT(*) AS n FROM %s "
                                  "WHERE zatca_icv IS NOT NULL OR zatca_status='fix' "
                                  "GROUP BY zatca_status" % table) or []
        except Exception:
            rows = []
        for r in rows:
            if r.get("s") in out:
                out[r["s"]] += int(r.get("n") or 0)
    return out


def documents(limit=200, only=None):
    """Recent documents in the ZATCA chain for the screen list."""
    out = []
    q = {"sales": ("SELECT TOP %d invoice_id AS id, invoice_number AS number, invoice_date AS d, "
                   "customer_name_en AS party, total_amount AS total, zatca_kind, zatca_status, "
                   "zatca_icv, zatca_last_error, zatca_warnings, zatca_submitted_at "
                   "FROM sales_invoices WHERE zatca_icv IS NOT NULL OR zatca_status='fix' "
                   "ORDER BY zatca_icv DESC"),
         "sales_return": ("SELECT TOP %d return_id AS id, return_number AS number, return_date AS d, "
                          "customer_name_en AS party, total_amount AS total, zatca_kind, zatca_status, "
                          "zatca_icv, zatca_last_error, zatca_warnings, zatca_submitted_at "
                          "FROM sales_returns WHERE zatca_icv IS NOT NULL OR zatca_status='fix' "
                          "ORDER BY zatca_icv DESC")}
    for kind, sql in q.items():
        try:
            for r in _db().fetchall(sql % limit) or []:
                r = dict(r); r["kind"] = kind
                if only and r.get("zatca_status") not in only:
                    continue
                out.append(r)
        except Exception:
            pass
    out.sort(key=lambda r: (r.get("zatca_icv") is not None, -(r.get("zatca_icv") or 0)))
    return out[:limit]


def xml_of(kind, doc_id):
    table, pk = _TABLES[kind][0], _TABLES[kind][1]
    r = _db().fetchone("SELECT zatca_signed_xml, zatca_cleared_xml FROM %s WHERE %s=?"
                       % (table, pk), (doc_id,)) or {}
    return r.get("zatca_cleared_xml") or r.get("zatca_signed_xml") or ""


# ============================================================
# connect (onboarding) — DB part / network part / DB part
# ============================================================
STEPS = [("csr", "Make DayBill's key + request"),
         ("ccsid", "Compliance certificate (OTP)"),
         ("checks", "6 test documents checked by ZATCA"),
         ("pcsid", "Production certificate"),
         ("done", "Connected — bills are signed and sent")]


def start_connect(env, otp, branch="", industry="", counter_id=None):
    """DB part 1: check details, make key + CSR. → ctx (no network).
    counter_id: connect ONE till as its own unit (its own counter and
    hash chain); empty = one shop-wide unit (as before)."""
    c = company()
    probs = detail_problems(c)
    if probs:
        raise ValueError("Fill these first:\n" + "\n".join("• %s — %s" % (l, p) for _k, l, p in probs))
    otp = "".join(ch for ch in str(otp or "") if ch.isdigit())
    if env == "sandbox" and not otp:
        otp = P.SANDBOX_OTP
    if len(otp) != 6:
        raise ValueError("Type the 6-digit OTP from the Fatoora portal "
                         "(Fatoora ▸ Onboard new solution unit ▸ Generate OTP).")
    s = seller(c)
    vat = s["vat"]
    group = len(vat) == 15 and vat[10] == "1"           # VAT group: OU must be the 10-digit TIN
    egs_serial = "1-DayBill|2-%s|3-%s" % (APP_VERSION, P.new_uuid())
    till = ""
    if counter_id:
        try:
            from modules import branches
            till = next((c.get("code") or str(c["counter_id"]) for c in branches.list_counters()
                         if c["counter_id"] == int(counter_id)), str(counter_id))
        except Exception:
            till = str(counter_id)
    info = {"common_name": "DayBill-EGS-%s%s" % (vat[-6:], ("-" + str(till))[:12] if till else ""),
            "serial": egs_serial, "vat": vat,
            "org_unit": (s["crn"] if group else (branch or s["city"] or "Main Branch"))[:64],
            "org_name": (c.get("company_name_en") or c.get("company_name_ar") or "Company")[:64],
            "invoice_type": "1100",
            "location": ("%s %s, %s, %s" % (s["building"], s["street"], s["district"], s["city"]))[:100],
            "industry": (industry or c.get("business_type") or "Retail")[:100]}
    key_pem, csr_b64 = P.make_csr(info, env)
    return {"env": env, "otp": otp, "info": info, "key": key_pem, "csr": csr_b64,
            "seller": s, "egs_name": info["common_name"], "egs_serial": egs_serial,
            "counter_id": int(counter_id) if counter_id else None}


def compliance_samples(ctx):
    """The 6 documents ZATCA wants to see before the production certificate."""
    now = datetime.now()
    s = ctx["seller"]
    buyer = {"name": "ZATCA Test Buyer", "vat": "399999999800003", "street": "Prince Sultan",
             "building": "2322", "district": "Al-Murabba", "city": "Riyadh", "postal": "23333",
             "country": "SA"}
    line = [{"name": "Test item", "qty": 2, "net_amount": 20.00, "vat_code": "S", "vat_rate": 15}]
    out = []
    for i, (sub, typ, label) in enumerate([
            (P.SUB_STANDARD, P.TYPE_INVOICE, "Standard invoice"),
            (P.SUB_STANDARD, P.TYPE_CREDIT, "Standard credit note"),
            (P.SUB_STANDARD, P.TYPE_DEBIT, "Standard debit note"),
            (P.SUB_SIMPLIFIED, P.TYPE_INVOICE, "Simplified invoice"),
            (P.SUB_SIMPLIFIED, P.TYPE_CREDIT, "Simplified credit note"),
            (P.SUB_SIMPLIFIED, P.TYPE_DEBIT, "Simplified debit note")], 1):
        out.append((label, {
            "number": "TEST-%d" % i, "uuid": P.new_uuid(),
            "issue_date": now.strftime("%Y-%m-%d"), "issue_time": now.strftime("%H:%M:%S"),
            "type_code": typ, "subtype": sub, "icv": i, "seller": s,
            "buyer": buyer if sub == P.SUB_STANDARD else {},
            "payment_code": "10", "billing_ref": "Invoice TEST-1" if typ != P.TYPE_INVOICE else None,
            "reason": "Test return" if typ != P.TYPE_INVOICE else None,
            "delivery_date": now.strftime("%Y-%m-%d") if sub == P.SUB_STANDARD else None,
            "lines": line, "total": 46.00}))
    return out


def run_connect(ctx, progress=None):
    """NETWORK part: compliance CSID → 6 checks → production CSID.
    progress(step, state, text) — state: 'run' | 'ok' | 'fail'. Returns result dict."""
    def say(step, state, text=""):
        if progress:
            try:
                progress(step, state, text)
            except Exception:
                pass
    env = ctx["env"]
    res = {"env": env}
    say("csr", "ok", "key + request made")
    say("ccsid", "run", "asking ZATCA…")
    try:
        cc = P.api_compliance_csid(env, ctx["csr"], ctx["otp"])
    except P.ApiError as e:
        say("ccsid", "fail", str(e))
        raise
    res["ccsid"] = cc
    say("ccsid", "ok", "request %s" % cc.get("requestID", ""))
    say("checks", "run", "0 / 6")
    cert = P.cert_b64_from_token(cc["binarySecurityToken"])
    pih = P.GENESIS_PIH
    passed = []
    for n, (label, doc) in enumerate(compliance_samples(ctx), 1):
        doc["pih"] = pih
        xml = P.build_xml(doc)
        signed = P.sign_xml(xml, cert, ctx["key"]) if doc["subtype"] == P.SUB_SIMPLIFIED \
            else P.unsigned_payload(xml)
        try:
            st, d = P.api_compliance_check(env, cc["binarySecurityToken"], cc["secret"],
                                           P.payload(signed, doc["uuid"]))
        except P.ApiError as e:
            say("checks", "fail", "%s: %s" % (label, e))
            raise
        errs, warns = P.messages(d)
        vr = (d.get("validationResults") or {}).get("status", "")
        okay = st in (200, 202) and vr in ("PASS", "WARNING", "") and not errs
        if not okay:
            msg = "%s was not accepted: %s" % (label, "; ".join(errs) or d.get("message") or st)
            say("checks", "fail", msg)
            raise P.ApiError(msg, st, d)
        passed.append(label)
        pih = signed["hash"]
        say("checks", "run", "%d / 6  ✓ %s" % (n, label))
    say("checks", "ok", "6 / 6 accepted")
    say("pcsid", "run", "asking ZATCA…")
    try:
        pc = P.api_production_csid(env, cc["binarySecurityToken"], cc["secret"], cc.get("requestID"))
    except P.ApiError as e:
        say("pcsid", "fail", str(e))
        raise
    res["pcsid"] = pc
    say("pcsid", "ok", "request %s" % pc.get("requestID", ""))
    res["checks"] = passed
    return res


def finish_connect(ctx, res):
    """DB part 2: store the EGS (switch off the older one of the same till /
    the older shop-wide one). Secrets are locked when key protection is on."""
    db = _db()
    from modules.zatca import vault
    cert = P.cert_b64_from_token(res["pcsid"]["binarySecurityToken"])
    exp = P.cert_expiry(cert)
    cid = ctx.get("counter_id")
    secrets_ = vault.lock_row_values({"private_key": ctx["key"],
                                      "ccsid_secret": res["ccsid"]["secret"],
                                      "pcsid_secret": res["pcsid"]["secret"]})
    with db.transaction():
        if _has_counter_col():
            if cid:
                db.execute("UPDATE zatca_egs SET is_active=0 WHERE is_active=1 AND counter_id=?",
                           (int(cid),))
            else:
                db.execute("UPDATE zatca_egs SET is_active=0 WHERE is_active=1 AND counter_id IS NULL")
        else:
            db.execute("UPDATE zatca_egs SET is_active=0 WHERE is_active=1")
        db.execute(
            "INSERT INTO zatca_egs (env, egs_name, egs_serial, private_key, csr, ccsid_token, "
            "ccsid_secret, ccsid_request_id, pcsid_token, pcsid_secret, pcsid_request_id, "
            "cert_expires, icv, last_hash, status, is_active, auto_send, onboarded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,GETDATE())",
            (ctx["env"], ctx["egs_name"], ctx["egs_serial"], secrets_["private_key"], ctx["csr"],
             res["ccsid"]["binarySecurityToken"], secrets_["ccsid_secret"],
             str(res["ccsid"].get("requestID", "")), res["pcsid"]["binarySecurityToken"],
             secrets_["pcsid_secret"], str(res["pcsid"].get("requestID", "")),
             exp.strftime("%Y-%m-%d %H:%M:%S") if exp else None, 0, P.GENESIS_PIH,
             "connected", 1, 1))
        if cid and _has_counter_col():
            new_id = db.last_identity("zatca_egs", "egs_id")
            db.execute("UPDATE zatca_egs SET counter_id=? WHERE egs_id=?", (int(cid), new_id))
    try:
        db.execute("UPDATE company SET zatca_onboarded=1 WHERE company_id=1")
    except Exception:
        pass
    try:
        db.execute("UPDATE company SET zatca_env=? WHERE company_id=1", (ctx["env"],))
    except Exception:
        pass
    log("🔐 Connected to ZATCA (%s) as %s%s" % (ctx["env"], ctx["egs_name"],
                                                (" — till %s" % cid) if cid else ""))
    try:
        from modules import audit
        audit.log("zatca", "connect", None, "ZATCA Phase 2 connected (%s)" % ctx["env"])
    except Exception:
        pass
    return active(cid) if cid else active(None)


def connect(env, otp, branch="", industry="", progress=None, counter_id=None):
    """All three parts in one go (tests / simple callers)."""
    ctx = start_connect(env, otp, branch, industry, counter_id=counter_id)
    res = run_connect(ctx, progress)
    return finish_connect(ctx, res)


def disconnect(egs_id=None):
    """Stop signing + sending with THIS PC's unit (or the given one)."""
    e = by_id(egs_id) if egs_id else active()
    if not e:
        return
    _db().execute("UPDATE zatca_egs SET is_active=0, status='off' WHERE egs_id=?", (e["egs_id"],))
    if not units():
        try:
            _db().execute("UPDATE company SET zatca_onboarded=0 WHERE company_id=1")
        except Exception:
            pass
    log("ZATCA connection switched off (%s)" % (e.get("egs_name") or e["egs_id"]))


def overdue(hours=20, now=None):
    """Simplified (B2C) bills / credit notes signed but NOT yet reported
    after `hours` — ZATCA wants them within 24 hours of the sale. Also
    documents held as '✋ fix' (they are not in the chain yet!).
    → [{kind, id, number, when, age_hours, status}] oldest first."""
    now = now or datetime.now()
    out = []
    q = {"sales": ("invoice_id", "invoice_number", "invoice_date", "invoice_time", "sales_invoices"),
         "sales_return": ("return_id", "return_number", "return_date", None, "sales_returns")}
    for kind, (pk, num, dcol, tcol, table) in q.items():
        try:
            rows = _db().fetchall(
                "SELECT %s AS id, %s AS number, %s AS d, %s AS t, created_at, zatca_status, "
                "zatca_kind FROM %s WHERE zatca_status IN ('waiting','fix')"
                % (pk, num, dcol, tcol or "NULL", table)) or []
        except Exception:
            rows = []
        for r in rows:
            when = None
            ca = r.get("created_at")
            if isinstance(ca, datetime):
                when = ca
            elif isinstance(ca, str) and len(ca) >= 19:
                try:
                    when = datetime.strptime(ca[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    when = None
            if when is None:
                try:
                    when = datetime.strptime("%s %s" % (_iso_date(r.get("d")), _iso_time(r.get("t"), ca)),
                                             "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
            age = (now - when).total_seconds() / 3600.0
            if r.get("zatca_status") == "waiting" and r.get("zatca_kind") == "standard":
                continue                 # B2B: cleared before it is given — no 24 h rule
            if age >= hours:
                out.append({"kind": kind, "id": r["id"], "number": r.get("number"), "when": when,
                            "age_hours": round(age, 1), "status": r.get("zatca_status")})
    out.sort(key=lambda x: x["when"])
    return out


def overdue_text(hours=20):
    """One line for the dashboard / day close, '' when all is fine."""
    od = overdue(hours)
    if not od:
        return ""
    late = [x for x in od if x["age_hours"] >= 24]
    if late:
        return ("⚠ ZATCA: %d bill(s) are more than 24 hours old and NOT reported yet (oldest %s). "
                "Check the internet and ZATCA ▸ Send now." % (len(late), late[0]["number"]))
    return ("⏳ ZATCA: %d bill(s) are %d+ hours old and not reported yet — send them before 24 hours."
            % (len(od), hours))


def set_auto_send(on):
    e = active()
    if e:
        _db().execute("UPDATE zatca_egs SET auto_send=? WHERE egs_id=?", (1 if on else 0, e["egs_id"]))
