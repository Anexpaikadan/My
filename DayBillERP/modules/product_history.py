# ============================================================
# DayBill ERP - Product Transaction History
# ------------------------------------------------------------
# "What did we last sell/buy this product for, and to/from whom?"
# Used by the Product Info dialog (shared invoice grid) so a user
# picking a multi-unit product — or just checking Ctrl+details —
# can see recent context without leaving the invoice window.
# Reads the denormalized name snapshot already stored on each
# invoice header (customer_name_en / supplier_name_en), so this
# works even if the party was later renamed or deactivated.
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def last_sales(product_id, limit=5):
    """[{date, party_name, invoice_number, quantity, unit_price}] newest first."""
    try:
        rows = db.fetchall(
            f"SELECT TOP {int(limit)} si.invoice_date AS date, "
            f"si.customer_name_en AS party_name, si.invoice_number, "
            f"sil.quantity, sil.unit_price FROM sales_invoice_lines sil "
            f"JOIN sales_invoices si ON si.invoice_id = sil.invoice_id "
            f"WHERE sil.product_id=? AND si.invoice_status='confirmed' "
            f"ORDER BY si.invoice_date DESC, si.invoice_id DESC",
            (product_id,)) or []
        return rows
    except Exception:
        return []


def last_purchases(product_id, limit=5):
    """[{date, party_name, invoice_number, quantity, unit_price}] newest first."""
    try:
        rows = db.fetchall(
            f"SELECT TOP {int(limit)} pi.invoice_date AS date, "
            f"pi.supplier_name_en AS party_name, pi.invoice_number, "
            f"pil.quantity, pil.unit_price FROM purchase_invoice_lines pil "
            f"JOIN purchase_invoices pi ON pi.purchase_id = pil.purchase_id "
            f"WHERE pil.product_id=? AND pi.invoice_status='confirmed' "
            f"ORDER BY pi.invoice_date DESC, pi.purchase_id DESC",
            (product_id,)) or []
        return rows
    except Exception:
        return []
