# ============================================================
# DayBill ERP - Customer credit-limit check (shared by Sales
# Invoice and POS). Driven by Settings > Customer:
#   "Credit Limit Enabled"  -> block a credit sale over the limit
#   "Over Credit Warning"   -> warn (Yes/No) instead of blocking
# A limit of 0 means "no limit".
# ============================================================
from config import settings as cfg
from config.database import db


def check(customer_id, new_amount, exclude_invoice_id=None):
    """Returns (status, message). status: 'ok' | 'warn' | 'block'."""
    enforce = cfg.flag("cust_credit_limit", False)
    warn = cfg.flag("cust_over_credit_warn", True)
    if not (enforce or warn) or not customer_id:
        return "ok", ""
    try:
        row = db.fetchone("SELECT customer_name_en, ISNULL(credit_limit,0) AS credit_limit "
                          "FROM customers WHERE customer_id=?", (customer_id,)) or {}
        limit = float(row.get("credit_limit") or 0)
        if limit <= 0:
            return "ok", ""
        bal = db.execute_scalar("SELECT ISNULL(balance_due,0) FROM vw_customer_balance "
                                "WHERE customer_id=?", (customer_id,)) or 0
        bal = float(bal)
        after = bal + float(new_amount or 0)
        if after <= limit + 0.005:
            return "ok", ""
        msg = ("%s is over the credit limit.\n\n"
               "Credit limit:      %s\nCurrent balance:  %s\nThis invoice:       %s\n"
               "Balance after:     %s  (over by %s)"
               % (row.get("customer_name_en", "Customer"),
                  f"{limit:,.2f}", f"{bal:,.2f}", f"{float(new_amount):,.2f}",
                  f"{after:,.2f}", f"{after - limit:,.2f}"))
        return ("block" if enforce else "warn"), msg
    except Exception:
        return "ok", ""


def confirm(customer_id, new_amount, parent=None):
    """UI helper: True = go ahead with the sale, False = stop."""
    from tkinter import messagebox
    status, msg = check(customer_id, new_amount)
    if status == "ok":
        return True
    if status == "block":
        messagebox.showerror("Credit Limit",
                             msg + "\n\nTake payment now, or raise the limit on the customer.",
                             parent=parent)
        return False
    return messagebox.askyesno("Credit Limit", msg + "\n\nSave anyway?", parent=parent)
