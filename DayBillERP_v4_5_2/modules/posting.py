# ============================================================
# DayBill ERP - Accounting posting engine  (default-account driven)
# ------------------------------------------------------------
# Auto-creates balanced double-entry journal entries for every
# transaction type. Account selection now comes from the
# configurable Default Accounts map (modules/account_defaults.py)
# instead of hardcoded codes, with a safe built-in fallback.
#
# Public API is unchanged, so existing callers (invoices, purchases,
# returns, payments, customers, suppliers) keep working as-is:
#   post_sale, post_purchase, post_sales_return, post_purchase_return,
#   post_receipt, post_payment, ensure_party_account, post_journal,
#   enabled
#
# New in this version:
#   post_pos_sale        - POS sale with split tenders -> method ledgers
#   post_expense         - expense voucher (paid now or on credit)
#   post_salary_payment  - pay net salaries (settles the payroll accrual)
#   post_bank_transfer   - move funds between cash/bank accounts
#   post_adjustment      - manual journal from a list of (code, dr, cr)
#
# Posting rules:
#   SALE     : Dr Cash/Card/Bank/Customer | Cr Sales + Cr VAT Output
#   PURCHASE : Dr Inventory + Dr VAT Input | Cr Cash/Bank/Supplier
#   RECEIPT  : Dr Cash/Bank | Cr Customer
#   PAYMENT  : Dr Supplier  | Cr Cash/Bank
#   EXPENSE  : Dr Expense + Dr VAT Input | Cr Cash/Bank (or Cr Payable)
#   SALARY   : Dr Salaries Payable | Cr Cash/Bank
#   TRANSFER : Dr To-account | Cr From-account
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db
from modules import account_defaults as ad

try:
    from config import settings as cfg
except Exception:
    cfg = None


# ── posting mode (auto vs manual approval) ────────────────────
def _auto_post():
    """Entries post live unless the user turned Auto Posting off or
    requires manual approval -> then they are saved as drafts."""
    if cfg is None:
        return True
    if cfg.get("acc_manual_approval", False):
        return False
    return bool(cfg.get("acc_auto_posting", True))


def enabled():
    """Accounting integration is active only if the journal tables exist."""
    try:
        return bool(db.execute_scalar(
            "SELECT COUNT(*) FROM sys.tables WHERE name='journal_entries'"))
    except Exception:
        return False


def _next_journal_number():
    n = db.execute_scalar("SELECT COUNT(*) FROM journal_entries") or 0
    for i in range(n + 1, n + 100000):
        num = f"JV{i:06d}"
        if not db.execute_scalar(
                "SELECT COUNT(*) FROM journal_entries WHERE journal_number=?", (num,)):
            return num
    return f"JV{n+1:06d}"


last_error = ""


def _fail(msg):
    """Remember why the last posting failed (shown to the user)."""
    global last_error
    last_error = msg
    try:
        from modules import audit
        audit.log("post_failed", "journal", None, msg[:250])
    except Exception:
        pass
    return None


def _round_line(lines, total_debit_side):
    """Balance tiny rounding / round-off differences into the
    Round-Off account instead of dropping the whole entry."""
    dr = round(sum(l[1] or 0 for l in lines), 2)
    cr = round(sum(l[2] or 0 for l in lines), 2)
    diff = round(dr - cr, 2)
    if diff and abs(diff) <= 1.0:
        acc = ad.round_off()
        if acc:
            lines.append((acc, 0, diff, "Round off") if diff > 0
                         else (acc, -diff, 0, "Round off"))
    return lines


def _clamp_tenders(total, *amounts):
    """Money tendered above the bill total is change given back:
    reduce cash first, then the others, so the entry balances."""
    vals = [round(a or 0, 2) for a in amounts]
    excess = round(sum(vals) - round(total or 0, 2), 2)
    i = 0
    while excess > 0.005 and i < len(vals):
        cut = min(vals[i], excess)
        vals[i] = round(vals[i] - cut, 2)
        excess = round(excess - cut, 2)
        i += 1
    return vals


def post_journal(entry_date, description, lines, source_type, source_id,
                 reference=None, is_posted=None):
    """
    Create a balanced journal entry.
    lines: list of (account_id, debit, credit, line_description)
    Returns journal_id, or None if unbalanced / disabled / no real lines.
    is_posted: override the auto/manual posting mode if given.
    """
    global last_error
    last_error = ""
    if not enabled():
        return None
    # Refuse posting into a locked/closed financial year (if the FY table
    # exists and the date falls inside a closed year). Fails open (allows
    # posting) if the FY module/table isn't set up, so this never blocks
    # normal use on installs that haven't run the FY patch.
    try:
        from modules import financial_year as fy
        if fy.tables_ready() and fy.is_locked(entry_date):
            return _fail(f"{entry_date} is in a closed financial year")
    except Exception:
        pass
    missing = [l for l in lines if l[0] is None and ((l[1] or 0) or (l[2] or 0))]
    if missing:
        return _fail("account not found for: " + ", ".join(
            str(l[3]) for l in missing[:3]) + " (Settings ▸ Default Accounts)")
    # drop empty lines AND lines whose account could not be resolved,
    # then re-check the balance so we never persist a lop-sided entry.
    lines = [l for l in lines
             if l[0] is not None and ((l[1] or 0) or (l[2] or 0))]
    if not lines:
        return None
    total_debit = round(sum(l[1] or 0 for l in lines), 2)
    total_credit = round(sum(l[2] or 0 for l in lines), 2)
    if abs(total_debit - total_credit) > 0.01:
        return _fail(f"entry not balanced (Dr {total_debit:,.2f} / Cr {total_credit:,.2f})")
    posted = _auto_post() if is_posted is None else bool(is_posted)
    try:
        # header + lines are ONE unit: a failure never leaves a journal
        # without its lines (v5.27). Inside a document save this is a
        # savepoint of the document's transaction.
        # two tills may pick the same JV number at the same moment: the
        # second one simply takes the next number (unique key → retry)
        for _attempt in range(4):
            try:
                with db.transaction():
                    jnum = _next_journal_number()
                    db.execute(
                        "INSERT INTO journal_entries (journal_number, entry_date, reference, "
                        "description_en, source_type, source_id, total_debit, total_credit, "
                        "is_posted, posted_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (jnum, entry_date, reference, description, source_type, source_id,
                         total_debit, total_credit, 1 if posted else 0, None))
                    # this connection's new row — never another till's journal
                    jid = db.last_identity("journal_entries", "journal_id")
                    if posted:
                        db.execute("UPDATE journal_entries SET posted_at=GETDATE() "
                                   "WHERE journal_id=?", (jid,))
                    for i, (acc, dr, cr, desc) in enumerate(lines, 1):
                        db.execute(
                            "INSERT INTO journal_lines (journal_id, line_number, account_id, "
                            "debit, credit, description) VALUES (?,?,?,?,?,?)",
                            (jid, i, acc, round(dr or 0, 2), round(cr or 0, 2), desc))
                break
            except Exception as _e:
                from config.database import is_duplicate_error
                if _attempt < 3 and is_duplicate_error(_e):
                    continue
                raise
        try:
            from modules import audit
            audit.log("post", source_type or "journal", jid,
                      f"{jnum} {description} = {total_debit:,.2f}")
        except Exception:
            pass
        return jid
    except Exception as e:
        return _fail("database error: " + str(e)[:150])


# ── party ledger lookup ───────────────────────────────────────
def _customer_account(customer_id):
    if not customer_id:
        return None
    return db.execute_scalar(
        "SELECT account_id FROM customers WHERE customer_id=?", (customer_id,))


def _supplier_account(supplier_id):
    if not supplier_id:
        return None
    return db.execute_scalar(
        "SELECT account_id FROM suppliers WHERE supplier_id=?", (supplier_id,))


def _party_ledger(kind, party_id):
    """The party's own ledger account — made now if it has none yet
    (customers / suppliers from older versions or an import), so every
    credit sale, receipt, return … shows on their statement, in Customer /
    Supplier Balances and in Aging. Falls back to the control account."""
    acc = None
    if party_id:
        try:
            acc = ensure_party_account(kind, party_id)
        except Exception:
            acc = (_customer_account if kind == "customer" else _supplier_account)(party_id)
    return acc or (ad.receivable() if kind == "customer" else ad.payable())


# ── Sale posting ──────────────────────────────────────────────
def post_sale(invoice_id, invoice_date, customer_id, taxable, vat, total,
              cash=0, card=0, bank=0, invoice_number="", others=None):
    """
    Cash sale (no customer)  -> Dr Cash | Cr Sales + Cr VAT
    Credit sale (customer)   -> Dr Customer ledger | Cr Sales + Cr VAT
    Mixed tenders supported (cash + card + bank, remainder on account).
    others (v6.0): {account_id: amount} — STC Pay, Tabby, vouchers … each
    debited to its own account.
    """
    if not enabled():
        return None
    total = round(total or 0, 2)
    others = {a: round(v or 0, 2) for a, v in (others or {}).items() if a and round(v or 0, 2)}
    o_keys = list(others)
    vals = _clamp_tenders(total, cash, card, bank, *[others[k] for k in o_keys])
    cash, card, bank = vals[:3]
    others = {k: v for k, v in zip(o_keys, vals[3:]) if v}
    on_credit = round(total - (cash + card + bank + sum(others.values())), 2)
    if on_credit < 0:
        on_credit = 0

    lines = []
    if cash:
        lines.append((ad.cash(), cash, 0, "Cash received"))
    if card:
        lines.append((ad.card(), card, 0, "Card received"))
    if bank:
        lines.append((ad.bank(), bank, 0, "Bank received"))
    for acc_id, amt in others.items():
        lines.append((acc_id, amt, 0, "Received (other tender)"))
    if on_credit > 0:
        cust = _party_ledger("customer", customer_id)
        lines.append((cust, on_credit, 0, "On account"))
    lines.append((ad.sales(), 0, round(taxable, 2), "Sales revenue"))
    if vat:
        lines.append((ad.tax_payable(), 0, round(vat, 2), "VAT output"))
    _round_line(lines, True)

    return post_journal(invoice_date, f"Sales Invoice {invoice_number}".strip(),
                        lines, "sales", invoice_id, reference=invoice_number)


# ── POS sale (split tenders mapped to per-method ledgers) ─────
def post_pos_sale(invoice_id, invoice_date, taxable, vat, total,
                  payments=None, method="cash", invoice_number=""):
    """
    payments: dict of {tender: amount}, e.g. {"cash":50,"card":65}.
              If omitted, the whole total is taken via `method`.
    Each tender is debited to its mapped ledger (Default Accounts ->
    Payment Method mapping). Credits Sales + VAT.
    """
    if not enabled():
        return None
    if not payments:
        payments = {method: total}
    lines = []
    for tender, amt in payments.items():
        amt = round(amt or 0, 2)
        if amt:
            lines.append((ad.method_account(tender), amt, 0, f"{tender} tender"))
    lines.append((ad.sales(), 0, round(taxable, 2), "POS sales revenue"))
    if vat:
        lines.append((ad.tax_payable(), 0, round(vat, 2), "VAT output"))
    return post_journal(invoice_date, f"POS Sale {invoice_number}".strip(),
                        lines, "pos", invoice_id, reference=invoice_number)


# ── Purchase posting ──────────────────────────────────────────
def post_purchase(invoice_id, invoice_date, supplier_id, taxable, vat, total,
                  cash=0, bank=0, invoice_number=""):
    if not enabled():
        return None
    total = round(total or 0, 2)
    cash, bank = _clamp_tenders(total, cash, bank)
    on_credit = round(total - (cash + bank), 2)
    if on_credit < 0:
        on_credit = 0

    lines = [(ad.inventory(), round(taxable, 2), 0, "Inventory")]
    if vat:
        lines.append((ad.tax_receivable(), round(vat, 2), 0, "VAT input"))
    if cash:
        lines.append((ad.cash(), 0, cash, "Cash paid"))
    if bank:
        lines.append((ad.bank(), 0, bank, "Bank paid"))
    if on_credit > 0:
        sup = _party_ledger("supplier", supplier_id)
        lines.append((sup, 0, on_credit, "On account"))
    _round_line(lines, False)

    return post_journal(invoice_date, f"Purchase Invoice {invoice_number}".strip(),
                        lines, "purchase", invoice_id, reference=invoice_number)


# ── Sales Return ──────────────────────────────────────────────
def post_sales_return(return_id, entry_date, customer_id, taxable, vat, total,
                      method="cash", number=""):
    """
    Dr Sales Returns (contra-revenue) + Dr VAT Output reversal
    Cr Cash/Card/Bank refunded, or Cr Customer ledger (credit note).
    """
    if not enabled():
        return None
    lines = [(ad.sales_return(), round(taxable, 2), 0, "Sales return")]
    if vat:
        lines.append((ad.tax_payable(), round(vat, 2), 0, "VAT output reversal"))
    m = (method or "cash").lower()
    refund = (ad.method_account(m) if m in ("cash", "card", "mada", "cheque", "bank",
              "bank_transfer", "gateway") else None)
    if refund:
        lines.append((refund, 0, round(total, 2), "Refund to customer"))
    else:
        lines.append((_party_ledger("customer", customer_id), 0,
                      round(total, 2), "Credit to customer account"))
    _round_line(lines, True)
    return post_journal(entry_date, f"Sales Return {number}".strip(),
                        lines, "sales_return", return_id, reference=number)


# ── Purchase Return ───────────────────────────────────────────
def post_purchase_return(return_id, entry_date, supplier_id, taxable, vat, total,
                         method="credit", number=""):
    """
    Dr Cash/Bank refunded, or Dr Supplier ledger (reduce payable)
    Cr Inventory (the goods leave stock at their purchase value)
    + Cr VAT Input reversal.
    """
    if not enabled():
        return None
    m = (method or "credit").lower()
    debit = (ad.method_account(m) if m in ("cash", "card", "mada", "cheque", "bank",
                                          "bank_transfer") else None)
    lines = []
    if debit:
        lines.append((debit, round(total, 2), 0, "Refund from supplier"))
    else:
        lines.append((_party_ledger("supplier", supplier_id),
                      round(total, 2), 0, "Reduce payable"))
    # Purchases are booked to Inventory, so a return must come back out
    # of Inventory — crediting a separate "Purchase Returns" account would
    # leave the stock value overstated.
    lines.append((ad.inventory() or ad.purchase_return(), 0, round(taxable, 2),
                  "Purchase return (stock out)"))
    if vat:
        lines.append((ad.tax_receivable(), 0, round(vat, 2), "VAT input reversal"))
    _round_line(lines, False)
    return post_journal(entry_date, f"Purchase Return {number}".strip(),
                        lines, "purchase_return", return_id, reference=number)


# ── Receipt (money IN from a customer) ────────────────────────
def post_receipt(payment_id, date, customer_id, amount, method="cash",
                 reference=""):
    if not enabled() or not amount:
        return None
    debit = ad.method_account(method)
    cust = _party_ledger("customer", customer_id)
    lines = [(debit, round(amount, 2), 0, "Money received"),
             (cust, 0, round(amount, 2), "Customer settlement")]
    return post_journal(date, f"Receipt {reference}".strip(), lines,
                        "receipt", payment_id, reference=reference)


# ── Payment (money OUT to a supplier) ─────────────────────────
def post_payment(payment_id, date, supplier_id, amount, method="cash",
                 reference=""):
    if not enabled() or not amount:
        return None
    credit = ad.method_account(method)
    sup = _party_ledger("supplier", supplier_id)
    lines = [(sup, round(amount, 2), 0, "Supplier settlement"),
             (credit, 0, round(amount, 2), "Money paid")]
    return post_journal(date, f"Payment {reference}".strip(), lines,
                        "payment", payment_id, reference=reference)


# ── Expense voucher ───────────────────────────────────────────
def post_expense(expense_id, date, expense_account_id, amount, vat=0,
                 method="cash", on_credit=False, reference="", description="",
                 supplier_id=None):
    """
    Dr Expense + Dr VAT Input | Cr Cash/Bank (or Cr Supplier Payable if on_credit).
    expense_account_id: the chosen expense ledger (e.g. Rent 5300).
    """
    if not enabled() or not amount:
        return None
    amount = round(amount, 2); vat = round(vat or 0, 2)
    lines = [(expense_account_id, amount, 0, description or "Expense")]
    if vat:
        lines.append((ad.tax_receivable(), vat, 0, "VAT input"))
    if on_credit:
        credit = _party_ledger("supplier", supplier_id)
    else:
        credit = ad.method_account(method)
    lines.append((credit, 0, amount + vat, "Paid" if not on_credit else "On account"))
    return post_journal(date, f"Expense {reference}".strip() or "Expense",
                        lines, "expense", expense_id, reference=reference)


# ── Salary payment (settles the payroll accrual) ──────────────
def post_salary_payment(run_id, date, amount, method="bank", reference=""):
    """
    Dr Salaries Payable | Cr Cash/Bank.
    Use after post_payroll_run accrued the expense; this is the cash-out leg.
    For shops that pay without accruing, point default_salary_expense at the
    Salaries Expense account and call this with that account instead.
    """
    if not enabled() or not amount:
        return None
    payable_acc = ad.acc("default_salary_expense")
    # if a Salaries Payable account exists, prefer it for the debit
    sal_payable = ad._id_from_code("2300") or payable_acc
    lines = [(sal_payable, round(amount, 2), 0, "Net salaries paid"),
             (ad.method_account(method), 0, round(amount, 2), "Salary payout")]
    return post_journal(date, f"Salary Payment {reference}".strip(),
                        lines, "salary_payment", run_id, reference=reference)


# ── Bank / cash fund transfer ─────────────────────────────────
def post_bank_transfer(transfer_id, date, from_account_id, to_account_id,
                       amount, reference=""):
    """Dr destination account | Cr source account."""
    if not enabled() or not amount:
        return None
    lines = [(to_account_id, round(amount, 2), 0, "Transfer in"),
             (from_account_id, 0, round(amount, 2), "Transfer out")]
    return post_journal(date, f"Fund Transfer {reference}".strip(),
                        lines, "transfer", transfer_id, reference=reference)


# ── Manual adjustment journal ─────────────────────────────────
def post_adjustment(date, code_lines, description="Adjustment", reference=""):
    """
    code_lines: list of (account_code, debit, credit, line_desc).
    Resolves codes to ids and posts (respects manual-approval mode).
    """
    if not enabled():
        return None
    lines = [(ad._id_from_code(c), dr, cr, d) for (c, dr, cr, d) in code_lines]
    return post_journal(date, description, lines, "adjustment", None,
                        reference=reference)


# ── Ensure a party has its own ledger account ─────────────────
def _free_sub_code(base):
    """Next unused sub-account code base-0001, base-0002 … (a deleted
    party's code is never reused by mistake)."""
    n = (db.execute_scalar(
        f"SELECT COUNT(*) FROM accounts WHERE account_code LIKE '{base}-%'") or 0) + 1
    for i in range(n, n + 100000):
        code = f"{base}-{i:04d}"
        if not db.execute_scalar("SELECT COUNT(*) FROM accounts WHERE account_code=?", (code,)):
            return code
    return f"{base}-{n:04d}"


def ensure_party_account(party_type, party_id):
    if not enabled():
        return None
    if party_type == "customer":
        acc = _customer_account(party_id)
        if acc:
            return acc
        row = db.fetchone("SELECT customer_name_en FROM customers WHERE customer_id=?",
                          (party_id,))
        if not row:
            return None                    # no such customer: never make a stray account
        name = row["customer_name_en"] or f"Customer {party_id}"
        code = _free_sub_code("1200")
        parent = ad.receivable()
        db.execute(
            "INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
            "account_type, parent_account_id) VALUES (?,?,?,?,?)",
            (code, name, name, "asset", parent))
        acc = db.execute_scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
        db.execute("UPDATE customers SET account_id=? WHERE customer_id=?", (acc, party_id))
        return acc
    else:
        acc = _supplier_account(party_id)
        if acc:
            return acc
        row = db.fetchone("SELECT supplier_name_en FROM suppliers WHERE supplier_id=?",
                          (party_id,))
        if not row:
            return None
        name = row["supplier_name_en"] or f"Supplier {party_id}"
        code = _free_sub_code("2100")
        parent = ad.payable()
        db.execute(
            "INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
            "account_type, parent_account_id) VALUES (?,?,?,?,?)",
            (code, name, name, "liability", parent))
        acc = db.execute_scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
        db.execute("UPDATE suppliers SET account_id=? WHERE supplier_id=?", (acc, party_id))
        return acc


# ── Old entries on the control account → the party's own ledger ──
_PARTY_SOURCES = {
    # source_type: (kind, table, id column, party column)
    "sales": ("customer", "sales_invoices", "invoice_id", "customer_id"),
    "pos": ("customer", "sales_invoices", "invoice_id", "customer_id"),
    "sales_return": ("customer", "sales_returns", "return_id", "customer_id"),
    "receipt": ("customer", "payments", "payment_id", "customer_id"),
    "purchase": ("supplier", "purchase_invoices", "purchase_id", "supplier_id"),
    "purchase_return": ("supplier", "purchase_returns", "return_id", "supplier_id"),
    "payment": ("supplier", "payments", "payment_id", "supplier_id"),
    "expense": ("supplier", "expenses", "expense_id", "supplier_id"),
}


def relink_control_lines():
    """Entries made before a customer / supplier had their own ledger went
    straight to Accounts Receivable / Payable. Move each such line to the
    party's own ledger (a sub-account of the same control account, so the
    Trial Balance does not change) — statements, Customer / Supplier
    Balances and Aging then show them. Returns how many lines moved."""
    if not enabled():
        return 0
    moved = 0
    for kind, ctrl in (("customer", ad.receivable()), ("supplier", ad.payable())):
        if not ctrl:
            continue
        try:
            rows = db.fetchall(
                "SELECT jl.line_id, je.source_type, je.source_id FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE jl.account_id=? AND je.source_id IS NOT NULL", (ctrl,)) or []
        except Exception:
            continue
        cache = {}
        for r in rows:
            src = _PARTY_SOURCES.get(str(r.get("source_type") or ""))
            if not src or src[0] != kind:
                continue
            _k, tbl, idc, pcol = src
            key = (tbl, r["source_id"])
            if key not in cache:
                try:
                    cache[key] = db.execute_scalar(
                        f"SELECT {pcol} FROM {tbl} WHERE {idc}=?", (r["source_id"],))
                except Exception:
                    cache[key] = None
            pid = cache[key]
            if not pid:
                continue
            acc = ensure_party_account(kind, pid)
            if not acc or acc == ctrl:
                continue
            try:                                   # only real receivable / payable ledgers
                parent = db.execute_scalar(
                    "SELECT parent_account_id FROM accounts WHERE account_id=?", (acc,))
                if parent != ctrl:
                    continue
                db.execute("UPDATE journal_lines SET account_id=? WHERE line_id=?",
                           (acc, r["line_id"]))
                moved += 1
            except Exception:
                pass
    return moved
