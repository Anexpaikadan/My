# ============================================================
# DayBill ERP - Accounting Engine
# Double-entry posting + Trial Balance + P&L + Balance Sheet
# ============================================================

from datetime import date


# ─────────────────────────────────────────────────────────────
# JOURNAL POSTING
# ─────────────────────────────────────────────────────────────
def next_journal_number(db) -> str:
    year = date.today().year
    cnt = db.execute_scalar(
        "SELECT COUNT(*) FROM journal_entries WHERE YEAR(entry_date)=?", (year,)) or 0
    for n in range(cnt + 1, cnt + 10000):          # first number not used yet
        num = f"JV-{year}-{n:05d}"
        if not db.execute_scalar("SELECT COUNT(*) FROM journal_entries WHERE journal_number=?",
                                 (num,)):
            return num
    return f"JV-{year}-{cnt+1:05d}"


def post_journal(db, entry_date, lines, description_en="", description_ar="",
                 source_type="manual", source_id=None, reference=None,
                 created_by=None, auto_post=True):
    """
    Create a balanced journal entry.

    lines: list of dicts: {account_id, debit, credit, description}
    Debits must equal credits or a ValueError is raised.
    Returns the new journal_id.
    """
    total_debit  = round(sum(float(l.get("debit", 0) or 0) for l in lines), 2)
    total_credit = round(sum(float(l.get("credit", 0) or 0) for l in lines), 2)

    if abs(total_debit - total_credit) > 0.01:
        raise ValueError(
            f"Unbalanced entry: debit {total_debit} != credit {total_credit}")
    if total_debit == 0:
        raise ValueError("Journal entry has no amounts.")

    with db.transaction():            # header + lines together, or neither (v5.27)
        return _insert_journal(db, entry_date, lines, description_en, description_ar,
                               source_type, source_id, reference, created_by, auto_post,
                               total_debit, total_credit)


def _insert_journal(db, entry_date, lines, description_en, description_ar, source_type,
                    source_id, reference, created_by, auto_post, total_debit, total_credit):
    jnum = next_journal_number(db)
    db.execute(
        "INSERT INTO journal_entries (journal_number, entry_date, reference, "
        "description_en, description_ar, source_type, source_id, total_debit, "
        "total_credit, is_posted, created_by, posted_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (jnum, entry_date, reference, description_en, description_ar,
         source_type, source_id, total_debit, total_credit,
         1 if auto_post else 0, created_by,
         date.today() if auto_post else None))

    jid = db.execute_scalar(
        "SELECT MAX(journal_id) FROM journal_entries WHERE journal_number=?", (jnum,))
    try:                                    # v6.9.3 voucher type (JV, CR, CP …)
        from modules import voucher_types as _vt
        vt = _vt.code_for(source_type, [l.get("account_id") for l in lines], source_id)
        with db.savepoint():
            db.execute("UPDATE journal_entries SET voucher_type=? WHERE journal_id=?", (vt, jid))
    except Exception:
        pass

    for i, l in enumerate(lines, 1):
        db.execute(
            "INSERT INTO journal_lines (journal_id, line_number, account_id, "
            "debit, credit, description) VALUES (?,?,?,?,?,?)",
            (jid, i, l["account_id"], round(float(l.get("debit", 0) or 0), 2),
             round(float(l.get("credit", 0) or 0), 2), l.get("description", "")))

    return jid


def account_id_by_code(db, code: str):
    """Look up an account_id by its code (e.g. '4100')."""
    row = db.fetchone("SELECT account_id FROM accounts WHERE account_code=?", (code,))
    return row["account_id"] if row else None


def general_ledger(db, account_id, date_from, date_to):
    """
    General Ledger for a single account: every posted journal line in the
    period, plus the opening balance carried from before date_from, with a
    running balance.

    Returns:
      {
        "account": {code, name_en, type},
        "opening": float,
        "entries": [ {date, journal_number, description, debit, credit, balance} ],
        "total_debit": float, "total_credit": float, "closing": float,
      }
    Sign convention: debit-normal accounts (asset/expense) increase with debits;
    credit-normal accounts (liability/equity/revenue) increase with credits.
    """
    acct = db.fetchone(
        "SELECT account_code, account_name_en, account_name_ar, account_type "
        "FROM accounts WHERE account_id=?", (account_id,))
    if not acct:
        return None

    debit_normal = acct["account_type"] in ("asset", "expense")

    def signed(dr, cr):
        return (dr - cr) if debit_normal else (cr - dr)

    # Opening balance = sum of all signed movements strictly before date_from
    op = db.fetchone(
        "SELECT ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr "
        "FROM journal_lines jl JOIN journal_entries je ON jl.journal_id=je.journal_id "
        "WHERE je.is_posted=1 AND jl.account_id=? AND je.entry_date < ?",
        (account_id, date_from)) or {"dr": 0, "cr": 0}
    opening = round(signed(float(op["dr"]), float(op["cr"])), 2)

    rows = db.fetchall(
        "SELECT je.entry_date, je.journal_number, "
        "ISNULL(jl.description, je.description_en) AS description, "
        "jl.debit, jl.credit "
        "FROM journal_lines jl JOIN journal_entries je ON jl.journal_id=je.journal_id "
        "WHERE je.is_posted=1 AND jl.account_id=? "
        "AND je.entry_date BETWEEN ? AND ? "
        "ORDER BY je.entry_date, je.journal_id, jl.line_id",
        (account_id, date_from, date_to))

    entries = []
    running = opening
    total_dr = total_cr = 0.0
    for r in rows:
        dr = float(r["debit"]); cr = float(r["credit"])
        running += signed(dr, cr)
        total_dr += dr; total_cr += cr
        entries.append({
            "date": str(r["entry_date"]),
            "journal_number": r["journal_number"],
            "description": r.get("description", "") or "",
            "debit": round(dr, 2), "credit": round(cr, 2),
            "balance": round(running, 2),
        })

    return {
        "account": {"code": acct["account_code"],
                    "name_en": acct["account_name_en"],
                    "type": acct["account_type"]},
        "opening": opening,
        "entries": entries,
        "total_debit": round(total_dr, 2),
        "total_credit": round(total_cr, 2),
        "closing": round(running, 2),
    }


# ─────────────────────────────────────────────────────────────
# AUTO-POSTING HELPERS (called by other modules)
# ─────────────────────────────────────────────────────────────
def post_sales_invoice(db, invoice: dict):
    """
    DR Accounts Receivable (total)
       CR Sales Revenue (taxable)
       CR VAT Collected/Output (vat)
    """
    ar  = account_id_by_code(db, "1200")   # Accounts Receivable
    rev = account_id_by_code(db, "4100")   # Sales Revenue
    vat = account_id_by_code(db, "2210")   # VAT Collected (Output)
    if not all([ar, rev, vat]):
        return None
    total   = float(invoice.get("total_amount", 0))
    taxable = float(invoice.get("taxable_amount", invoice.get("subtotal_amount", 0)))
    vat_amt = float(invoice.get("vat_amount", 0))
    lines = [
        {"account_id": ar,  "debit": total, "credit": 0, "description": "Sales invoice"},
        {"account_id": rev, "debit": 0, "credit": taxable, "description": "Revenue"},
        {"account_id": vat, "debit": 0, "credit": vat_amt, "description": "Output VAT"},
    ]
    return post_journal(db, invoice.get("invoice_date", date.today()), lines,
                        description_en=f"Sales invoice {invoice.get('invoice_number','')}",
                        source_type="sales", source_id=invoice.get("invoice_id"),
                        reference=invoice.get("invoice_number"))


def post_payroll_run(db, run: dict, totals: dict):
    """
    DR Salaries Expense (gross)
    DR GOSI Expense (employer share)
       CR Salaries Payable (net)
       CR GOSI Payable (employee + employer)
    """
    sal_exp  = account_id_by_code(db, "5200")
    gosi_exp = account_id_by_code(db, "5210")
    sal_pay  = account_id_by_code(db, "2300")
    gosi_pay = account_id_by_code(db, "2310")
    if not all([sal_exp, gosi_exp, sal_pay, gosi_pay]):
        return None

    gross        = float(totals.get("gross", 0))
    net          = float(totals.get("net", 0))
    gosi_emp     = float(totals.get("gosi_employee", 0))
    gosi_empr    = float(totals.get("gosi_employer", 0))
    other_ded    = round(gross - net - gosi_emp, 2)  # loans + other deductions

    lines = [
        {"account_id": sal_exp,  "debit": gross, "credit": 0, "description": "Gross salaries"},
        {"account_id": gosi_exp, "debit": gosi_empr, "credit": 0, "description": "Employer GOSI"},
        {"account_id": sal_pay,  "debit": 0, "credit": net, "description": "Net payable"},
        {"account_id": gosi_pay, "debit": 0, "credit": gosi_emp + gosi_empr, "description": "GOSI payable"},
    ]
    # Balance any loan/other deductions back to Employee Loans (asset reduction)
    if other_ded > 0.01:
        loans = account_id_by_code(db, "2320")
        if loans:
            lines.append({"account_id": loans, "debit": 0, "credit": other_ded,
                          "description": "Loan/other deductions recovered"})

    return post_journal(db, date(run["run_year"], run["run_month"], 28), lines,
                        description_en=f"Payroll {run.get('run_label','')}",
                        source_type="payroll", source_id=run.get("run_id"))


# ─────────────────────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────────────────────
def trial_balance(db, date_to=None):
    """
    Returns list of {account_code, account_name_en, account_type, debit, credit}.
    Debit/credit are the net balance placed on the correct side.
    """
    where = "WHERE je.is_posted=1"
    params = ()
    if date_to:
        where += " AND je.entry_date <= ?"
        params = (date_to,)

    rows = db.fetchall(
        "SELECT a.account_code, a.account_name_en, a.account_name_ar, a.account_type, "
        "ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr "
        "FROM accounts a "
        "LEFT JOIN journal_lines jl ON a.account_id = jl.account_id "
        "LEFT JOIN journal_entries je ON jl.journal_id = je.journal_id " + where + " "
        "GROUP BY a.account_code, a.account_name_en, a.account_name_ar, a.account_type "
        "HAVING ISNULL(SUM(jl.debit),0) <> 0 OR ISNULL(SUM(jl.credit),0) <> 0 "
        "ORDER BY a.account_code", params)

    result = []
    for r in rows:
        dr = float(r["dr"]); cr = float(r["cr"])
        net = dr - cr
        # Assets/expenses are normally debit; liabilities/equity/revenue credit
        if net >= 0:
            debit, credit = round(net, 2), 0.0
        else:
            debit, credit = 0.0, round(-net, 2)
        result.append({
            "account_code": r["account_code"],
            "account_name_en": r["account_name_en"],
            "account_name_ar": r.get("account_name_ar", ""),
            "account_type": r["account_type"],
            "debit": debit, "credit": credit,
        })
    return result


def profit_and_loss(db, date_from, date_to):
    """
    Returns {revenue:[], expenses:[], total_revenue, total_expenses, net_profit}.
    """
    rows = db.fetchall(
        "SELECT a.account_code, a.account_name_en, a.account_type, "
        "ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr "
        "FROM accounts a "
        "JOIN journal_lines jl ON a.account_id = jl.account_id "
        "JOIN journal_entries je ON jl.journal_id = je.journal_id "
        "WHERE je.is_posted=1 AND je.entry_date BETWEEN ? AND ? "
        "AND a.account_type IN ('revenue','expense') AND ISNULL(je.source_type,'')<>'year_close' "
        "GROUP BY a.account_code, a.account_name_en, a.account_type "
        "ORDER BY a.account_code", (date_from, date_to))

    revenue, expenses = [], []
    total_rev = total_exp = 0.0
    for r in rows:
        dr = float(r["dr"]); cr = float(r["cr"])
        if r["account_type"] == "revenue":
            amt = round(cr - dr, 2)        # revenue normal balance = credit
            revenue.append({"code": r["account_code"],
                            "name": r["account_name_en"], "amount": amt})
            total_rev += amt
        else:
            amt = round(dr - cr, 2)        # expense normal balance = debit
            expenses.append({"code": r["account_code"],
                             "name": r["account_name_en"], "amount": amt})
            total_exp += amt

    return {
        "revenue": revenue, "expenses": expenses,
        "total_revenue": round(total_rev, 2),
        "total_expenses": round(total_exp, 2),
        "net_profit": round(total_rev - total_exp, 2),
    }


def balance_sheet(db, date_to):
    """
    Returns {assets:[], liabilities:[], equity:[], totals...}.
    Retained earnings (net profit to date) is folded into equity.
    """
    rows = db.fetchall(
        "SELECT a.account_code, a.account_name_en, a.account_type, "
        "ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr "
        "FROM accounts a "
        "JOIN journal_lines jl ON a.account_id = jl.account_id "
        "JOIN journal_entries je ON jl.journal_id = je.journal_id "
        "WHERE je.is_posted=1 AND je.entry_date <= ? "
        "GROUP BY a.account_code, a.account_name_en, a.account_type "
        "ORDER BY a.account_code", (date_to,))

    assets, liabilities, equity = [], [], []
    t_assets = t_liab = t_equity = 0.0
    retained = 0.0

    for r in rows:
        dr = float(r["dr"]); cr = float(r["cr"])
        t = r["account_type"]
        if t == "asset":
            amt = round(dr - cr, 2)
            assets.append({"code": r["account_code"], "name": r["account_name_en"], "amount": amt})
            t_assets += amt
        elif t == "liability":
            amt = round(cr - dr, 2)
            liabilities.append({"code": r["account_code"], "name": r["account_name_en"], "amount": amt})
            t_liab += amt
        elif t == "equity":
            amt = round(cr - dr, 2)
            equity.append({"code": r["account_code"], "name": r["account_name_en"], "amount": amt})
            t_equity += amt
        elif t == "revenue":
            retained += round(cr - dr, 2)
        elif t == "expense":
            retained -= round(dr - cr, 2)

    if abs(retained) > 0.01:
        equity.append({"code": "3900", "name": "Retained Earnings",
                       "amount": round(retained, 2)})
        t_equity += retained

    return {
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "total_assets": round(t_assets, 2),
        "total_liabilities": round(t_liab, 2),
        "total_equity": round(t_equity, 2),
        "balanced": abs(t_assets - (t_liab + t_equity)) < 0.01,
    }
