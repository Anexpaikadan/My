# ============================================================
# DayBill ERP - sales debit notes (v6.0)
# ------------------------------------------------------------
# A debit note raises what a customer owes on an invoice that is
# already issued (price was too low, a delivery / service charge was
# forgotten …). ZATCA type 383, it refers to the original invoice and
# says why. Signed invoices can't be edited — this is the legal way to
# add to them (a credit note = Sales Return takes away).
#
#   create(original_invoice_id, lines, reason, pay="credit")
#     lines: [{"description", "quantity", "unit_price" (without VAT),
#              "vat_rate", "product_id" (optional)}]
# Books: Dr customer (or Cash) | Cr Sales + Cr VAT output.
# Stock never moves. Stored in sales_invoices (invoice_kind='debit').
# ============================================================
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        db.fetchone("SELECT TOP 1 invoice_kind FROM sales_invoices")
        return True
    except Exception:
        return False


def find_invoice(number):
    """A confirmed sales invoice / POS bill by its number (not a debit note)."""
    n = str(number or "").strip()
    if not n:
        return None
    try:
        r = db.fetchone("SELECT * FROM sales_invoices WHERE invoice_number=? AND "
                        "ISNULL(invoice_kind,'')<>'debit'", (n,))
        return dict(r) if r else None
    except Exception:
        return None


def notes_for(invoice_number):
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT invoice_id, invoice_number, invoice_date, total_amount, debit_reason "
            "FROM sales_invoices WHERE invoice_kind='debit' AND original_invoice_no=? "
            "ORDER BY invoice_id", (str(invoice_number),)) or []]
    except Exception:
        return []


def list_notes(date_from=None, date_to=None, limit=300):
    cond, params = ["invoice_kind='debit'"], []
    if date_from:
        cond.append("invoice_date >= ?"); params.append(str(date_from)[:10])
    if date_to:
        cond.append("invoice_date <= ?"); params.append(str(date_to)[:10])
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT TOP %d invoice_id, invoice_number, invoice_date, original_invoice_no, "
            "customer_name_en, total_amount, vat_amount, payment_method, debit_reason, "
            "zatca_status FROM sales_invoices WHERE %s ORDER BY invoice_id DESC"
            % (int(limit), " AND ".join(cond)), tuple(params)) or []]
    except Exception:
        return []


def compute(lines):
    """→ (clean lines, taxable, vat, total)."""
    out, taxable, vat = [], 0.0, 0.0
    for ln in lines or []:
        qty = _f(ln.get("quantity") or 1)
        price = round(_f(ln.get("unit_price")), 4)
        rate = _f(ln.get("vat_rate") if ln.get("vat_rate") is not None else 15)
        desc = str(ln.get("description") or "").strip()
        if qty <= 0 or price <= 0 or not desc:
            continue
        from modules.doc_math import r2              # half up, like the windows
        amt = r2(qty * price)
        v = r2(amt * rate / 100.0)
        out.append({"description": desc[:200], "quantity": qty, "unit_price": price,
                    "vat_rate": rate, "line_amount": amt, "vat_amount": v,
                    "line_total": round(amt + v, 2), "product_id": ln.get("product_id"),
                    "vat_code": "S" if rate > 0 else "Z"})
    from modules.doc_math import doc_totals      # v6.9.2: VAT once per rate (ZATCA)
    T = doc_totals(out, False, code="vat_code")
    return out, T["taxable"], T["vat"], T["total"]


def create(original_invoice_id, lines, reason, pay="credit", when=None):
    """Save + post + sign a debit note. → (invoice_id, number)."""
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Write why the amount is raised (ZATCA needs a reason).")
    org = db.fetchone("SELECT * FROM sales_invoices WHERE invoice_id=?", (int(original_invoice_id),))
    if not org:
        raise ValueError("The original invoice was not found.")
    org = dict(org)
    if str(org.get("invoice_kind") or "") == "debit":
        raise ValueError("Pick the original invoice, not another debit note.")
    if str(org.get("invoice_status") or "").lower() != "confirmed":
        raise ValueError("The original invoice must be confirmed (not a draft or cancelled).")
    rows, taxable, vat, total = compute(lines)
    if not rows:
        raise ValueError("Add at least one line with a description and an amount.")
    pay = "cash" if str(pay).lower() == "cash" else "credit"
    if pay == "credit":
        code = ""
        try:
            code = str(db.execute_scalar("SELECT customer_code FROM customers WHERE customer_id=?",
                                         (org.get("customer_id"),)) or "").upper()
        except Exception:
            pass
        if not org.get("customer_id") or code in ("WALKIN", "CASH", "WALK-IN"):
            pay = "cash"                    # a walk-in customer can't owe → paid in cash
    d = str(when or date.today().isoformat())[:10]
    with db.transaction():
        try:
            from modules.doc_numbering import next_number
            number = next_number("sales_invoices", "invoice_number", "DN")
        except Exception:
            number = "DN-%s" % date.today().strftime("%Y%m%d%H%M%S")
        db.execute(
            "INSERT INTO sales_invoices (invoice_number, invoice_date, customer_id, customer_name_en, "
            "customer_name_ar, customer_vat_no, customer_country_code, subtotal_amount, discount_amount, "
            "taxable_amount, vat_amount, total_amount, payment_method, payment_status, paid_amount, "
            "notes_en, invoice_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (number, d, org.get("customer_id"), org.get("customer_name_en"),
             org.get("customer_name_ar"), org.get("customer_vat_no"),
             org.get("customer_country_code") or "SA", taxable, 0, taxable, vat, total, pay,
             "paid" if pay == "cash" else "unpaid", total if pay == "cash" else 0,
             ("Debit note for %s: %s" % (org.get("invoice_number"), reason))[:1000], "confirmed"))
        iid = db.execute_scalar("SELECT invoice_id FROM sales_invoices WHERE invoice_number=?",
                                (number,))
        db.execute("UPDATE sales_invoices SET invoice_kind='debit', original_invoice_no=?, "
                   "debit_reason=?, sale_channel='DN' WHERE invoice_id=?",
                   (str(org.get("invoice_number") or ""), reason[:200], iid))
        for i, ln in enumerate(rows, 1):
            db.execute(
                "INSERT INTO sales_invoice_lines (invoice_id, line_number, product_id, product_code, "
                "product_name_en, product_name_ar, quantity, unit_of_measure_en, unit_price, "
                "discount_amount, line_amount, vat_category_code, vat_rate, vat_amount, line_total) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (iid, i, ln.get("product_id"), "", ln["description"], ln["description"],
                 ln["quantity"], "Unit", ln["unit_price"], 0, ln["line_amount"], ln["vat_code"],
                 ln["vat_rate"], ln["vat_amount"], ln["line_total"]))
        try:
            from modules import tenders
            tenders.save_lines("sales", iid, [{"method": "cash", "amount": total}] if pay == "cash" else [])
        except Exception:
            pass
        try:                                     # Phase 1 QR (Phase 2 replaces it when signed)
            from modules.zatca.qr_generator import (generate_zatca_qr, format_zatca_datetime,
                                                    seller_name, clean_vat_number)
            comp = dict(db.fetchone("SELECT * FROM company WHERE company_id=1") or {})
            db.execute("UPDATE sales_invoices SET qr_code_data=? WHERE invoice_id=?",
                       (generate_zatca_qr(seller_name(comp), clean_vat_number(comp.get("vat_registration_no", "")),
                                          format_zatca_datetime(), "%.2f" % total, "%.2f" % vat), iid))
        except Exception:
            pass
        from modules import doc_posting
        doc_posting.sync("sales", iid, tenders={"cash": total if pay == "cash" else 0.0, "bank": 0.0})
        try:
            from modules.zatca import egs
            egs.after_save("sales", iid)
        except Exception:
            pass
    try:
        from modules import audit
        audit.log("add", "debit_note", iid, "%s for %s (%.2f): %s"
                  % (number, org.get("invoice_number"), total, reason[:100]))
    except Exception:
        pass
    return iid, number
