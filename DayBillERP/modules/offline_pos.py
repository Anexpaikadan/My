# ============================================================
# DayBill ERP - POS keeps selling when the server is briefly gone (v6.0)
# ------------------------------------------------------------
# When a POS bill can't be saved because SQL Server can't be reached
# (network cable, Wi-Fi, server PC restarting …) the cashier is asked:
#     "Keep this bill on this PC and send it when the server is back?"
# The bill is written to  config/offline_bills/OFF-<till>-00001.json
# (number unique to this till), a receipt marked PROVISIONAL can be
# printed, and the next customer is served. Every minute the POS tries
# again; when the server answers, each kept bill is saved exactly as a
# normal POS bill — same number, same date and time, same tenders —
# with stock, books, shift and ZATCA signing. The number uses the till's
# id (T3 …), so two tills never clash; if a number is ever found taken by
# another bill, "-2" is added — a kept bill is never dropped. (ZATCA allows simplified
# bills to be reported within 24 hours; the tax invoice with the full
# ZATCA QR can then be reprinted from Last Bill).
# Only fully paid bills (cash / card / STC Pay …) can be kept — a sale
# on account needs the customer's credit check on the server.
# ============================================================
import json
import os
import uuid
from datetime import datetime


def _cfg():
    from config import settings as cfg
    return cfg


def enabled():
    try:
        return bool(_cfg().flag("pos_offline_queue", True))
    except Exception:
        return True


def folder():
    try:
        from config.paths import config_file
        d = config_file("offline_bills")
    except Exception:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config",
                         "offline_bills")
    os.makedirs(d, exist_ok=True)
    return d


CONN_WORDS = ("08s01", "08001", "08003", "communication link", "tcp provider", "login timeout",
              "server was not found", "no database connection", "connection was lost",
              "network-related", "connection failure", "is not reachable",
              "unable to connect", "connection forcibly closed", "named pipes provider")
# (a save the server cancelled — deadlock etc. — is NOT a lost server: the
#  cashier just presses Save again, so it is not kept offline)


def is_connection_error(err):
    """True when the save failed because the SERVER could not be reached
    (not a data problem such as a duplicate barcode)."""
    try:
        from config.database import TransactionLost
        if isinstance(err, TransactionLost) and "connection" in str(err).lower():
            return True
    except Exception:
        pass
    m = str(err).lower()
    return any(w in m for w in CONN_WORDS)


def _till_code():
    """A tag unique to this till, known WITHOUT the server: T<counter id>
    (counter ids are unique in the whole company — two branches may both
    have a till called C1), else this computer's name."""
    try:
        cid = _cfg().get("counter_id")
        if cid:
            return "T%d" % int(cid)
    except Exception:
        pass
    import re
    import socket
    import hashlib
    try:
        host = socket.gethostname() or "PC"
    except Exception:
        host = "PC"
    tag = re.sub(r"[^A-Za-z0-9]", "", host).upper() or "PC"
    if len(tag) > 8:                      # keep it short AND unique
        tag = tag[:4] + hashlib.md5(host.encode("utf-8")).hexdigest()[:4].upper()
    return tag


def _seq_path():
    return os.path.join(folder(), "_seq.json")


def _read_seq():
    try:
        with open(_seq_path(), "r", encoding="utf-8") as f:
            return int(json.load(f).get("n", 0))
    except Exception:
        return 0


def _write_seq(n):
    tmp = _seq_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"n": int(n)}, f)
    os.replace(tmp, _seq_path())


def next_number():
    """OFF-<till>-00001 … kept per till (never used by another till)."""
    n = _read_seq() + 1
    _write_seq(n)
    return "OFF-%s-%05d" % (_till_code(), n)


def sync_seq():
    """Server reachable (POS opening): never start below a number this till
    already used — e.g. after Windows / DayBill was reinstalled on this PC."""
    try:
        from config.database import db
        top = db.execute_scalar("SELECT MAX(invoice_number) FROM sales_invoices WHERE invoice_number "
                                "LIKE ?", ("OFF-%s-%%" % _till_code(),))
        if top:
            used = int(str(top).split("-")[2])      # OFF-T3-00042(-2) → 42
            if used > _read_seq():
                _write_seq(used)
    except Exception:
        pass


def _clean_line(ln):
    keep = {}
    for k, v in ln.items():
        if k.startswith("_") and k not in ("_base_price",):
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            keep[k] = v
    return keep


def keep(lines, h, shift_id=None, user_id=None):
    """Save one bill on this PC. → its number."""
    number = next_number()
    payload = {"id": uuid.uuid4().hex, "number": number,
               "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "lines": [_clean_line(l) for l in lines],
               "h": {k: v for k, v in h.items() if isinstance(v, (str, int, float, bool, list)) or v is None},
               "shift_id": shift_id, "user_id": user_id,
               "counter_id": _cfg().get("counter_id")}
    path = os.path.join(folder(), number + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return number


def pending():
    out = []
    try:
        for name in sorted(os.listdir(folder())):
            if name.startswith("OFF-") and name.endswith(".json"):
                p = os.path.join(folder(), name)
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        out.append((p, json.load(f)))
                except Exception:
                    continue
    except Exception:
        pass
    return out


def count():
    return len(pending())


class _Writer:
    """Uses the POS's own save code (same as a bill rung at the till)."""
    def __init__(self, company):
        self._company = company or {}


def _on_server(p):
    """Is this kept bill's number already on the server?
    → True  (yes, and it IS this bill — saved before a crash),
      False (number free),
      None  (the number belongs to another bill)."""
    from config.database import db
    r = db.fetchone("SELECT total_amount, invoice_date FROM sales_invoices WHERE invoice_number=?",
                    (p["number"],))
    if not r:
        return False
    try:
        same_total = abs(float(r["total_amount"] or 0) - float((p.get("h") or {}).get("total") or 0)) < 0.01
    except Exception:
        same_total = False
    return True if (same_total and str(r["invoice_date"])[:10] == str(p.get("created"))[:10]) else None


def _free_number(base):
    from config.database import db
    for i in range(2, 100):
        n = "%s-%d" % (base, i)
        if not db.execute_scalar("SELECT invoice_id FROM sales_invoices WHERE invoice_number=?", (n,)):
            return n
    return "%s-%s" % (base, uuid.uuid4().hex[:6].upper())


def _rewrite(path, p):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def send_all(company=None):
    """Save every kept bill on the server. → (sent, errors[]).
    Stops at the first connection problem (try again later). A kept bill
    is never dropped: it leaves this PC only once it is on the server."""
    from config.database import db
    from ui.pos import POSWindow
    _Writer._write_invoice_body = POSWindow._write_invoice_body
    _Writer._write_invoice = POSWindow._write_invoice
    if company is None:
        try:
            company = dict(db.fetchone("SELECT * FROM company WHERE company_id=1") or {})
        except Exception as e:
            return 0, [str(e)[:200]]
    w = _Writer(company)
    sent, errors = 0, []
    for path, p in pending():
        try:
            there = _on_server(p)
            if there is True:                       # already saved (sent before a crash)
                os.replace(path, path + ".sent")
                continue
            if there is None:                       # number taken by another bill → next free one
                p["number_printed"] = p.get("number_printed") or p["number"]
                p["number"] = _free_number(p["number"])
                _rewrite(path, p)
            h = dict(p.get("h") or {})
            h.update(number=p["number"], when=p["created"], shift_id=p.get("shift_id"),
                     user_id=p.get("user_id"), offline=True)
            w._write_invoice(p["lines"], h)
            os.replace(path, path + ".sent")
            sent += 1
        except Exception as e:
            if is_connection_error(e):
                errors.append("server not reachable yet")
                break
            try:
                if _on_server(p) is True:           # it did get saved
                    os.replace(path, path + ".sent")
                    continue
            except Exception:
                pass
            errors.append("%s: %s" % (p["number"], str(e)[:150]))
    return sent, errors


def provisional_receipt(lines, h, number, company):
    """A receipt PDF for a kept bill (Phase 1 QR, marked PROVISIONAL)."""
    import tempfile
    try:
        from modules.zatca.qr_generator import (generate_zatca_qr, seller_name, clean_vat_number,
                                                format_zatca_datetime)
        qr = generate_zatca_qr(seller_name(company), clean_vat_number(company.get("vat_registration_no", "")),
                               format_zatca_datetime(), "%.2f" % float(h.get("total") or 0),
                               "%.2f" % float(h.get("vat") or 0))
    except Exception:
        qr = ""
    inv = {"invoice_number": number + "  (PROVISIONAL)", "invoice_date": datetime.now().strftime("%Y-%m-%d"),
           "customer_name_en": h.get("cust_en") or "", "customer_name_ar": h.get("cust_ar") or "",
           "customer_vat_no": "", "subtotal_amount": h.get("gross"), "taxable_amount": h.get("gross"),
           "vat_amount": h.get("vat"), "total_amount": h.get("total"), "paid_amount": h.get("paid_amt"),
           "payment_method": h.get("pay"), "qr_code_data": qr,
           "notes_en": "Server offline — this bill is kept on the till and becomes the tax invoice "
                       "when the connection is back (reprint it from Last Bill)."}
    rows = [{"product_name_en": l.get("product_name_en"), "product_name_ar": l.get("product_name_ar"),
             "quantity": l.get("quantity"), "unit_price": l.get("unit_price"),
             "unit_of_measure_en": l.get("unit_name"), "line_amount": l.get("taxable"),
             "vat_rate": l.get("vat_rate"), "vat_amount": l.get("vat_amount"),
             "line_total": l.get("line_total"), "discount_amount": l.get("discount_amount") or 0}
            for l in lines]
    path = os.path.join(tempfile.gettempdir(), number + ".pdf")
    from modules.thermal_receipt import generate_thermal_receipt
    generate_thermal_receipt(inv, company or {}, rows, path, qr_data=qr)
    return path
