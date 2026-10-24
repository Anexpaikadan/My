# ============================================================
# DayBill ERP - 💰 payroll runs, loans, final settlement  (v6.6)
# ------------------------------------------------------------
# One place for everything that changes payroll data (the HR screen only
# shows it):
#   generate(m, y)        a month: every active employee — overtime from
#                         attendance, absent / unpaid days, the sick-leave
#                         part the law does not pay (art. 117), joined or
#                         left in the month, loan instalment, GOSI
#   edit_line(...)        change overtime hours / bonus / other deduction
#                         of one payslip (draft months) → totals + books
#   regenerate            gives the loan instalments back and removes the
#                         old journal first (before v6.6 both happened twice)
#   approve / pay_salaries / pay_gosi / reopen
#   give_loan(...)        Dr Employee Loans / Cr Cash or Bank
#   settlement(...)       end of service (art. 84/85, actual wage) + unused
#                         leave (art. 111) − loans still owed → save + books
#   wps_rows / write_wps  bank / Mudad salary file (Iqama / ID, IBAN checked)
# ============================================================

import calendar
import csv
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db
from modules import payroll_engine as PE
from modules import hr_time as HT

MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
STATUS = {"draft": "📝 Draft", "approved": "✔ Approved", "paid": "💳 Paid"}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _d(v):
    return HT._d(v)


def _cfg(key, default):
    return HT._cfg(key, default)


def _flag(key, default):
    v = _cfg(key, default)
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")


def _has(table, col):
    try:
        return bool(db.execute_scalar("SELECT COUNT(*) FROM sys.columns WHERE object_id=OBJECT_ID(?) AND name=?",
                                      (table, col)))
    except Exception:
        try:
            db.fetchone("SELECT TOP 1 %s FROM %s" % (col, table))
            return True
        except Exception:
            return False


def v660():
    """True when the v6.6 database update is in (new payslip columns)."""
    return _has("payslips", "absence_deduction")


def _user():
    try:
        from modules import permissions as p
        return (p.session_user() or {}).get("user_id")
    except Exception:
        return None


def _audit(action, ref, text):
    try:
        from modules import audit
        audit.log(action, "payroll", ref, text)
    except Exception:
        pass


def month_range(y, m):
    return date(int(y), int(m), 1), date(int(y), int(m), calendar.monthrange(int(y), int(m))[1])


def run_of(m, y):
    try:
        r = db.fetchone("SELECT * FROM payroll_runs WHERE run_month=? AND run_year=?", (int(m), int(y)))
        return dict(r) if r else None
    except Exception:
        return None


def run_by_id(run_id):
    r = db.fetchone("SELECT * FROM payroll_runs WHERE run_id=?", (int(run_id),))
    return dict(r) if r else None


def lines(run_id):
    return [dict(r) for r in (db.fetchall("SELECT * FROM payslips WHERE run_id=? ORDER BY employee_name_en",
                                          (int(run_id),)) or [])]


# ── one employee's month ──────────────────────────────────────
def _active_loan(employee_id, until):
    r = db.fetchone("SELECT TOP 1 loan_id, monthly_deduction, balance FROM employee_loans WHERE employee_id=? "
                    "AND is_settled=0 AND balance > 0 AND loan_date <= ? ORDER BY loan_date, loan_id",
                    (int(employee_id), until.isoformat()))
    return dict(r) if r else None


def _service_gap(e, first, last):
    """Joined or left inside the month: the days NOT to pay, so the pay is
    days worked / 30 (a full month = 30 days, whatever its length)."""
    j, end = _d(e.get("join_date")), _d(e.get("end_date"))
    a = j if (j and first < j <= last) else first
    b = end if (end and first <= end < last) else last
    if a == first and b == last:
        return 0
    worked = max(0, (b - a).days + 1)
    return max(0, 30 - min(30, worked))


def compute(e, y, m, overtime_hours=None, bonus=0.0, other_deduction=0.0, loan_deduction=0.0):
    """The payslip of employee row `e` for the month (nothing saved)."""
    first, last = month_range(y, m)
    days = 0.0
    absence = 0.0
    if _flag("hr_deduct_unpaid_days", True):
        absence, d_ = HT.unpaid_deduction(e, y, m)
        days += d_
    gap = _service_gap(e, first, last)
    if gap:
        absence += round(PE.actual_wage(e, "actual") / 30.0 * gap, 2)
        days += gap
    sick, _lost = HT.sick_deduction(e, y, m)
    if overtime_hours is None:
        overtime_hours = HT.overtime_hours(e["employee_id"], y, m) if _flag("hr_overtime_from_attendance", True) else 0.0
    ps = PE.calc_payslip(e, overtime_hours=overtime_hours, loan_deduction=loan_deduction,
                         other_deduction=other_deduction, on=last.isoformat(), bonus=bonus,
                         absence_deduction=absence, sick_deduction=sick)
    ps["absence_days"] = round(days, 2)
    return ps


_COLS = ["basic_salary", "housing_allowance", "transport_allowance", "other_allowance", "overtime_hours",
         "overtime_amount", "gross_salary", "gosi_employee", "gosi_employer", "loan_deduction",
         "other_deduction", "total_deductions", "net_salary"]
_NEW = ["bonus_amount", "absence_days", "absence_deduction", "sick_deduction"]


def _insert_line(run_id, e, ps, loan_id, note=None):
    cols = ["run_id", "employee_id", "employee_name_en", "employee_name_ar"] + _COLS + ["iban", "bank_name", "notes"]
    vals = [run_id, e["employee_id"], e.get("full_name_en"), e.get("full_name_ar") or ""] + \
           [ps[k] for k in _COLS] + [e.get("iban"), e.get("bank_name"), note]
    if v660():
        cols += _NEW + ["loan_id"]
        vals += [ps.get(k, 0) for k in _NEW] + [loan_id]
    elif ps.get("absence_deduction") or ps.get("sick_deduction"):
        # old database: keep the money right (absence + sick as 'other')
        i = cols.index("other_deduction")
        vals[i] = round(ps["other_deduction"] + ps.get("absence_deduction", 0) + ps.get("sick_deduction", 0), 2)
    db.execute("INSERT INTO payslips (%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" * len(cols))),
               tuple(vals))


def _employees(first, last):
    """Active employees + those whose last day falls in this month (they are
    paid up to their last day; the final settlement is separate)."""
    rows = [dict(r) for r in (db.fetchall("SELECT * FROM employees WHERE is_active=1 OR (end_date BETWEEN ? AND ?) "
                                          "ORDER BY full_name_en", (first.isoformat(), last.isoformat())) or [])]
    out = []
    for e in rows:
        j = _d(e.get("join_date"))
        if j and j > last:
            continue                                   # starts after this month
        out.append(e)
    return out


# ── the month ─────────────────────────────────────────────────
class RunExists(Exception):
    pass


def _year_open(y, m):
    """A month in a closed financial year is never made, changed or deleted."""
    from modules import financial_year as fy
    msg = fy.lock_message(month_range(y, m)[1].isoformat())
    if msg:
        raise ValueError(msg)


def generate(m, y, replace=False):
    """Make the payroll of a month → (run_id, summary text).
    replace=True: a draft month is made again (loans given back, old books
    entry removed first). Approved / paid months must be reopened first."""
    m, y = int(m), int(y)
    first, last = month_range(y, m)
    _year_open(y, m)
    old = run_of(m, y)
    if old:
        if (old.get("status") or "draft") != "draft":
            raise ValueError("%s is %s — press ↩ Reopen first." % (old.get("run_label"), old.get("status")))
        if not replace:
            raise RunExists(old["run_id"])
    emps = _employees(first, last)
    if not emps:
        raise ValueError("Add active employees first (HR ▸ Employees).")
    label = "%s %d" % (MONTHS[m], y)
    with db.transaction():
        if old:
            _remove(old["run_id"])
        db.execute("INSERT INTO payroll_runs (run_month, run_year, run_label, status, created_by) "
                   "VALUES (?,?,?,?,?)", (m, y, label, "draft", _user()))
        run_id = db.execute_scalar("SELECT run_id FROM payroll_runs WHERE run_month=? AND run_year=?", (m, y))
        for e in emps:
            loan = _active_loan(e["employee_id"], last)
            ded = min(_f(loan["monthly_deduction"]), _f(loan["balance"])) if loan else 0.0
            ps = compute(e, y, m, loan_deduction=ded)
            _insert_line(run_id, e, ps, loan["loan_id"] if loan else None)
            if loan and ded > 0:
                nb = round(_f(loan["balance"]) - ded, 2)
                db.execute("UPDATE employee_loans SET balance=?, is_settled=? WHERE loan_id=?",
                           (nb, 1 if nb <= 0.01 else 0, loan["loan_id"]))
        t = _totals(run_id)
        _post(run_id)
    _audit("payroll", run_id, "%s generated: %d employees, net %.2f" % (label, len(emps), t["net"]))
    return run_id, "Payroll %s: %d employee(s) · net %s SAR" % (label, len(emps), "{:,.2f}".format(t["net"]))


def _restore_loans(run_id):
    for p in lines(run_id):
        ded = _f(p.get("loan_deduction"))
        if ded <= 0:
            continue
        lid = p.get("loan_id")
        if not lid:                                 # made before v6.6: the newest loan that has room
            r = db.fetchone("SELECT TOP 1 loan_id FROM employee_loans WHERE employee_id=? AND "
                            "balance + ? <= loan_amount + 0.01 ORDER BY loan_id DESC", (p["employee_id"], ded))
            lid = r and r["loan_id"]
        if lid:
            db.execute("UPDATE employee_loans SET balance=balance+?, is_settled=0 WHERE loan_id=?", (ded, lid))


def _unpost(source_type, source_id):
    db.execute("DELETE FROM journal_entries WHERE source_type=? AND source_id=?", (source_type, int(source_id)))


def _remove(run_id):
    _restore_loans(run_id)
    _unpost("payroll", run_id)
    db.execute("DELETE FROM payslips WHERE run_id=?", (int(run_id),))
    db.execute("DELETE FROM payroll_runs WHERE run_id=?", (int(run_id),))


def delete(run_id):
    r = run_by_id(run_id)
    if not r:
        return
    if (r.get("status") or "draft") != "draft":
        raise ValueError("Reopen the month first.")
    _year_open(r["run_year"], r["run_month"])
    with db.transaction():
        _remove(run_id)
    _audit("delete", run_id, "payroll %s deleted" % r.get("run_label"))


def _totals(run_id):
    t = {"gross": 0.0, "deductions": 0.0, "net": 0.0, "gosi_employee": 0.0, "gosi_employer": 0.0,
         "loans": 0.0, "absence": 0.0, "sick": 0.0, "other": 0.0, "overtime": 0.0, "bonus": 0.0, "count": 0}
    for p in lines(run_id):
        t["count"] += 1
        t["gross"] += _f(p.get("gross_salary"))
        t["deductions"] += _f(p.get("total_deductions"))
        t["net"] += _f(p.get("net_salary"))
        t["gosi_employee"] += _f(p.get("gosi_employee"))
        t["gosi_employer"] += _f(p.get("gosi_employer"))
        t["loans"] += _f(p.get("loan_deduction"))
        t["absence"] += _f(p.get("absence_deduction"))
        t["sick"] += _f(p.get("sick_deduction"))
        t["other"] += _f(p.get("other_deduction"))
        t["overtime"] += _f(p.get("overtime_amount"))
        t["bonus"] += _f(p.get("bonus_amount"))
    t = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in t.items()}
    db.execute("UPDATE payroll_runs SET total_gross=?, total_deductions=?, total_net=?, total_gosi_employee=?, "
               "total_gosi_employer=? WHERE run_id=?",
               (t["gross"], t["deductions"], t["net"], t["gosi_employee"], t["gosi_employer"], int(run_id)))
    return t


def totals(run_id):
    return _totals(run_id)


def _acc(code):
    from modules import account_defaults as ad
    return ad._id_from_code(code)


def _post(run_id):
    """Books for the month (replaces the month's old entry):
    Dr Salaries Expense (gross) · Dr GOSI Expense (employer)
    Cr Salaries Payable (net) · Cr GOSI Payable (both shares) · Cr Employee Loans
    (instalments) · Cr Salaries Expense (absent / unpaid / sick / other days)."""
    from modules import posting
    run = run_by_id(run_id)
    t = _totals(run_id)
    _unpost("payroll", run_id)
    if not t["count"] or not t["gross"]:
        return None
    off = round(t["absence"] + t["sick"] + t["other"], 2)
    sal = _acc("5200")
    lines_ = [(sal, t["gross"], 0, "Gross salaries %s" % run["run_label"]),
              (_acc("5210"), t["gosi_employer"], 0, "Employer GOSI"),
              (_acc("2300"), 0, t["net"], "Net salaries payable"),
              (_acc("2310"), 0, round(t["gosi_employee"] + t["gosi_employer"], 2), "GOSI payable"),
              (_acc("2320"), 0, t["loans"], "Loan instalments taken back"),
              (sal, 0, off, "Absent / unpaid / sick days and other deductions")]
    _, last = month_range(run["run_year"], run["run_month"])
    jid = posting.post_journal(last.isoformat(), "Payroll %s" % run["run_label"], lines_, "payroll", run_id,
                               reference=run["run_label"])
    if not jid:
        raise ValueError("Payroll not saved — its journal could not be posted: %s" % posting.last_error)
    return jid


def edit_line(payslip_id, overtime_hours=None, bonus=None, other_deduction=None, note=None):
    """Change one payslip of a DRAFT month → recalculated + totals + books."""
    p = db.fetchone("SELECT * FROM payslips WHERE payslip_id=?", (int(payslip_id),))
    if not p:
        raise ValueError("Payslip not found.")
    p = dict(p)
    run = run_by_id(p["run_id"])
    if (run.get("status") or "draft") != "draft":
        raise ValueError("%s is %s — press ↩ Reopen to change it." % (run["run_label"], run["status"]))
    _year_open(run["run_year"], run["run_month"])
    e = db.fetchone("SELECT * FROM employees WHERE employee_id=?", (p["employee_id"],))
    e = dict(e)
    ot = _f(p.get("overtime_hours")) if overtime_hours is None else max(0.0, _f(overtime_hours))
    bn = _f(p.get("bonus_amount")) if bonus is None else max(0.0, _f(bonus))
    od = _f(p.get("other_deduction")) if other_deduction is None else max(0.0, _f(other_deduction))
    ps = compute(e, run["run_year"], run["run_month"], overtime_hours=ot, bonus=bn, other_deduction=od,
                 loan_deduction=_f(p.get("loan_deduction")))
    sets = {k: ps[k] for k in _COLS}
    if v660():
        sets.update({k: ps.get(k, 0) for k in _NEW})
    if note is not None:
        sets["notes"] = (note or "")[:300] or None
    with db.transaction():
        db.execute("UPDATE payslips SET %s WHERE payslip_id=?" % ", ".join("%s=?" % k for k in sets),
                   tuple(sets.values()) + (int(payslip_id),))
        _post(p["run_id"])
    return ps


def approve(run_id):
    r = run_by_id(run_id)
    if (r.get("status") or "draft") == "draft":
        db.execute("UPDATE payroll_runs SET status='approved', approved_at=GETDATE() WHERE run_id=?", (int(run_id),))
        _audit("approve", run_id, "payroll %s approved" % r["run_label"])
    return run_by_id(run_id)


def pay_salaries(run_id, method="bank", on=None):
    """Net salaries paid: Dr Salaries Payable / Cr Bank (or Cash)."""
    from modules import posting
    r = run_by_id(run_id)
    if r.get("paid_at"):
        raise ValueError("The salaries of %s are already paid." % r["run_label"])
    if (r.get("status") or "draft") == "draft":
        approve(run_id)
    t = _totals(run_id)
    on = (_d(on) or date.today()).isoformat()
    with db.transaction():
        posting.post_salary_payment(run_id, on, t["net"], method, r["run_label"])
        if _has("payroll_runs", "paid_at"):
            db.execute("UPDATE payroll_runs SET status='paid', paid_at=?, paid_method=? WHERE run_id=?",
                       (on, method, int(run_id)))
        else:
            db.execute("UPDATE payroll_runs SET status='paid' WHERE run_id=?", (int(run_id),))
    _audit("pay", run_id, "salaries %s paid %.2f (%s)" % (r["run_label"], t["net"], method))
    return t["net"]


def pay_gosi(run_id, method="bank", on=None):
    """GOSI of the month paid: Dr GOSI Payable / Cr Bank (or Cash)."""
    from modules import posting, account_defaults as ad
    r = run_by_id(run_id)
    if r.get("gosi_paid_at"):
        raise ValueError("The GOSI of %s is already paid." % r["run_label"])
    if (r.get("status") or "draft") == "draft":
        approve(run_id)                    # as pay_salaries: no re-make / delete until ↩ Reopen
    t = _totals(run_id)
    amt = round(t["gosi_employee"] + t["gosi_employer"], 2)
    if amt <= 0:
        raise ValueError("No GOSI in %s." % r["run_label"])
    on = (_d(on) or date.today()).isoformat()
    with db.transaction():
        posting.post_journal(on, "GOSI %s" % r["run_label"],
                             [(_acc("2310"), amt, 0, "GOSI paid"),
                              (ad.method_account(method), 0, amt, "GOSI payment")],
                             "gosi_payment", run_id, reference=r["run_label"])
        if _has("payroll_runs", "gosi_paid_at"):
            db.execute("UPDATE payroll_runs SET gosi_paid_at=? WHERE run_id=?", (on, int(run_id)))
    _audit("pay", run_id, "GOSI %s paid %.2f" % (r["run_label"], amt))
    return amt


def reopen(run_id):
    """Back to draft: the payment entries are removed (salaries + GOSI)."""
    r = run_by_id(run_id)
    _year_open(r["run_year"], r["run_month"])
    with db.transaction():
        _unpost("salary_payment", run_id)
        _unpost("gosi_payment", run_id)
        sets = "status='draft', approved_at=NULL"
        if _has("payroll_runs", "paid_at"):
            sets += ", paid_at=NULL, paid_method=NULL, gosi_paid_at=NULL"
        db.execute("UPDATE payroll_runs SET %s WHERE run_id=?" % sets, (int(run_id),))
    _audit("reopen", run_id, "payroll %s reopened" % r["run_label"])
    return run_by_id(run_id)


# ── loans / advances ─────────────────────────────────────────
def give_loan(employee_id, amount, monthly, method="cash", notes="", on=None):
    """Record a loan / salary advance and pay it out: Dr Employee Loans / Cr Cash or Bank."""
    from modules import posting, account_defaults as ad
    amount, monthly = round(_f(amount), 2), round(_f(monthly), 2)
    if amount <= 0 or monthly <= 0:
        raise ValueError("Type the loan amount and the monthly instalment.")
    if monthly > amount:
        monthly = amount
    on = (_d(on) or date.today()).isoformat()
    with db.transaction():
        db.execute("INSERT INTO employee_loans (employee_id, loan_date, loan_amount, monthly_deduction, balance, "
                   "notes) VALUES (?,?,?,?,?,?)", (int(employee_id), on, amount, monthly, amount, notes or None))
        lid = db.last_identity("employee_loans", "loan_id")
        posting.post_journal(on, "Employee loan / advance", [(_acc("2320"), amount, 0, "Loan to employee"),
                                                              (ad.method_account(method), 0, amount, "Paid out")],
                             "employee_loan", lid)
    _audit("save", lid, "loan %.2f to employee %s" % (amount, employee_id))
    return lid


def loan_balance(employee_id):
    return round(_f(db.execute_scalar("SELECT ISNULL(SUM(balance),0) FROM employee_loans WHERE employee_id=? "
                                      "AND is_settled=0", (int(employee_id),))), 2)


# ── end of service / final settlement ─────────────────────────
NOTICE_DAYS = {"employer": 60, "employee": 30}      # open contracts, art. 75 (2025: 30 for a Saudi employee)


def service_years(e, end):
    """(years, days not counted) — unpaid leave over 20 days is left out (art. 116)."""
    out = HT.unpaid_days_not_counted(e["employee_id"], end)
    days = max(0, (end - _d(e["join_date"])).days - out)
    return round(days / 365.25, 2), out


def compensation_77(e, end, years, wage):
    """Art. 77 — the contract ended without a valid reason: a fixed-term contract →
    the wage for the rest of it; an open one → 15 days' wage a year; never less
    than 2 months' wage."""
    ce = _d(e.get("contract_end"))
    if ce and ce > end:
        amt = wage / 30.0 * (ce - end).days
        how = "rest of the contract (%d days)" % (ce - end).days
    else:
        amt = wage / 30.0 * 15 * years
        how = "15 days a year × %.2f years" % years
    if amt < 2 * wage:
        amt, how = 2 * wage, "at least 2 months' wage"
    return round(amt, 2), how


def settlement(employee_id, end_date, reason="termination", leave_days=None, notice_days=0,
               notice_by="employer", comp_77=False):
    """Final settlement of one employee (nothing saved). leave_days: the unused
    annual leave to pay (None = DayBill's balance).
    notice_days: days of notice NOT given — notice_by 'employer' (the shop ended it
    without notice → paid to the employee, art. 76) or 'employee' (left without
    notice → taken from the settlement). comp_77: ended without a valid reason."""
    e = db.fetchone("SELECT * FROM employees WHERE employee_id=?", (int(employee_id),))
    if not e:
        raise ValueError("Employee not found.")
    e = dict(e)
    if not e.get("is_active") and db.execute_scalar("SELECT COUNT(*) FROM eos_settlements WHERE employee_id=?",
                                                    (int(employee_id),)):
        raise ValueError("%s already has a final settlement." % e.get("full_name_en"))
    end = _d(end_date)
    if not end:
        raise ValueError("Type the last working day.")
    if not e.get("join_date"):
        raise ValueError("The employee has no join date.")
    if end < _d(e["join_date"]):
        raise ValueError("The last day is before the join date.")
    years, not_counted = service_years(e, end)
    wage = PE.actual_wage(e)
    eos = PE.calc_eos_gratuity(years, wage, reason)
    bal = HT.annual_balance(employee_id, on=end) if HT.carry() else HT.annual_balance(employee_id, end.year)
    leave_auto = max(0.0, round(_f(bal.get("balance")), 2))
    leave_days = leave_auto if leave_days in (None, "") else max(0.0, round(_f(leave_days), 2))
    day_wage = PE.actual_wage(e, "actual") / 30.0
    leave_pay = round(day_wage * leave_days, 2)
    nd = max(0.0, round(_f(notice_days), 2))
    notice_pay = round(day_wage * nd, 2) if notice_by == "employer" else 0.0
    notice_due = round(day_wage * nd, 2) if notice_by == "employee" else 0.0
    comp, comp_how = compensation_77(e, end, years, PE.actual_wage(e, "actual")) if comp_77 else (0.0, "")
    owed = loan_balance(employee_id)
    gross = round(eos["gratuity_amount"] + leave_pay + notice_pay + comp, 2)
    notice_taken = round(min(notice_due, gross), 2)
    recovered = round(min(owed, gross - notice_taken), 2)
    return {"employee": e, "end_date": end.isoformat(), "years": years, "days_not_counted": not_counted,
            "wage": wage, "wage_basis": PE.wage_basis(), "reason": eos["reason"], "award_full": eos["award_full"],
            "share": eos["share"], "award": eos["gratuity_amount"], "leave_days": leave_days,
            "leave_pay": leave_pay, "day_wage": round(day_wage, 2), "leave_auto": leave_auto, "notice_days": nd, "notice_by": notice_by,
            "notice_pay": notice_pay, "notice_taken": notice_taken, "comp_77": comp, "comp_77_how": comp_how,
            "gross": gross, "loan_owed": owed, "loan_recovered": recovered,
            "loan_left": round(owed - recovered, 2), "net": round(gross - notice_taken - recovered, 2)}


def save_settlement(employee_id, end_date, reason="termination", notes="", leave_days=None, notice_days=0,
                    notice_by="employer", comp_77=False):
    """Save the final settlement, take the loans back, end the employee, books:
    Dr End of Service Expense (award + art. 77) · Dr Salaries Expense (leave + notice pay)
    Cr Employee Loans (taken back) · Cr Other Income (notice the employee did not give)
    · Cr Salaries Payable (net to pay)."""
    from modules import posting
    s = settlement(employee_id, end_date, reason, leave_days, notice_days, notice_by, comp_77)
    e = s["employee"]
    with db.transaction():
        cols = ["employee_id", "employee_name_en", "join_date", "end_date", "years_served", "last_salary",
                "reason", "gratuity_amount", "notes"]
        vals = [e["employee_id"], e.get("full_name_en"), e.get("join_date"), s["end_date"], s["years"], s["wage"],
                s["reason"], s["award"], (notes or "")[:500] or None]
        if _has("eos_settlements", "net_settlement"):
            cols += ["award_full", "award_share", "leave_days", "leave_pay", "loan_recovered", "net_settlement",
                     "wage_basis"]
            vals += [s["award_full"], s["share"], s["leave_days"], s["leave_pay"], s["loan_recovered"], s["net"],
                     s["wage_basis"]]
        if _has("eos_settlements", "notice_amount"):
            cols += ["days_not_counted", "notice_days", "notice_amount", "compensation_77"]
            vals += [s["days_not_counted"], s["notice_days"], s["notice_pay"] - s["notice_taken"], s["comp_77"]]
        db.execute("INSERT INTO eos_settlements (%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" * len(cols))),
                   tuple(vals))
        eos_id = db.last_identity("eos_settlements", "eos_id")
        left = s["loan_recovered"]
        for ln in db.fetchall("SELECT loan_id, balance FROM employee_loans WHERE employee_id=? AND is_settled=0 "
                              "ORDER BY loan_date, loan_id", (e["employee_id"],)) or []:
            if left <= 0.005:
                break
            take = min(left, _f(ln["balance"]))
            nb = round(_f(ln["balance"]) - take, 2)
            db.execute("UPDATE employee_loans SET balance=?, is_settled=? WHERE loan_id=?",
                       (nb, 1 if nb <= 0.01 else 0, ln["loan_id"]))
            left = round(left - take, 2)
        db.execute("UPDATE employees SET is_active=0, end_date=? WHERE employee_id=?", (s["end_date"], e["employee_id"]))
        posting.post_journal(s["end_date"], "Final settlement %s" % (e.get("full_name_en") or ""),
                             [x for x in [
                                 (_acc("5220"), s["award"], 0, "End-of-service award"),
                                 (_acc("5220"), s["comp_77"], 0, "Compensation, art. 77 (%s)" % s["comp_77_how"]),
                                 (_acc("5200"), s["leave_pay"], 0, "Unused annual leave paid (%g days)" % s["leave_days"]),
                                 (_acc("5200"), s["notice_pay"], 0, "Notice not given by the employer (%g days)"
                                  % s["notice_days"]),
                                 (_acc("4300"), 0, s["notice_taken"], "Notice not given by the employee (%g days)"
                                  % s["notice_days"]),
                                 (_acc("2320"), 0, s["loan_recovered"], "Loans taken back"),
                                 (_acc("2300"), 0, s["net"], "Final settlement payable")]
                              if x[1] or x[2] or x[3] in ("End-of-service award", "Final settlement payable")],
                             "eos", eos_id)
    _audit("save", eos_id, "final settlement %s: %.2f" % (e.get("full_name_en"), s["net"]))
    s["eos_id"] = eos_id
    return s


def eos_liability(on=None):
    """If everyone left on `on`: the end-of-service award (ended by the
    employer / if they resigned) + unused leave value, per active employee."""
    on = _d(on) or date.today()
    out = []
    for e in db.fetchall("SELECT * FROM employees WHERE is_active=1 ORDER BY full_name_en") or []:
        e = dict(e)
        if not e.get("join_date") or _d(e["join_date"]) > on:
            continue
        yrs, _out = service_years(e, on)                 # v6.6: unpaid leave > 20 days left out
        wage = PE.actual_wage(e)
        full = PE.calc_eos_gratuity(yrs, wage, "termination")["gratuity_amount"]
        res = PE.calc_eos_gratuity(yrs, wage, "resignation")["gratuity_amount"]
        bal = HT.annual_balance(e["employee_id"], on=on) if HT.carry() else HT.annual_balance(e["employee_id"], on.year)
        ld = max(0.0, _f(bal.get("balance")))
        out.append({"employee_id": e["employee_id"], "code": e.get("employee_code"), "name": e.get("full_name_en"),
                    "join_date": str(e["join_date"])[:10], "years": yrs, "wage": wage, "award_ended": full,
                    "award_resigned": res, "leave_days": round(ld, 2),
                    "leave_value": round(PE.actual_wage(e, "actual") / 30.0 * ld, 2)})
    return out


# ── WPS / Mudad salary file ──────────────────────────────────
BANKS = {"05": "Alinma Bank", "10": "Saudi National Bank", "15": "Bank AlBilad", "20": "Riyad Bank",
         "30": "Arab National Bank", "45": "Saudi Awwal Bank (SAB)", "55": "Banque Saudi Fransi",
         "60": "Bank AlJazira", "65": "Saudi Investment Bank", "80": "Al Rajhi Bank"}


def clean_iban(v):
    return "".join(str(v or "").split()).upper()


def iban_ok(v):
    """Saudi IBAN: SA + 22 digits, check digits right (ISO 13616 mod 97)."""
    s = clean_iban(v)
    if len(s) != 24 or not s.startswith("SA") or not s[2:].isdigit():
        return False
    r = s[4:] + s[:4]
    num = "".join(str(int(ch, 36)) for ch in r)
    return int(num) % 97 == 1


def bank_code(iban):
    s = clean_iban(iban)
    return s[4:6] if len(s) >= 6 else ""


def id_ok(v):
    """National ID (1…) or Iqama (2…): 10 digits."""
    s = str(v or "").strip()
    return len(s) == 10 and s.isdigit() and s[0] in "12"


def wps_rows(run_id):
    """[{…, problems: [...]}] — one per payslip, with the employee's ID."""
    ids = {r["employee_id"]: dict(r) for r in (db.fetchall("SELECT employee_id, employee_code, national_id, iban, "
                                                           "bank_name FROM employees") or [])}
    out = []
    for p in lines(run_id):
        e = ids.get(p["employee_id"], {})
        iban = clean_iban(p.get("iban") or e.get("iban"))
        nid = str(e.get("national_id") or "").strip()
        probs = []
        if not id_ok(nid):
            probs.append("Iqama / ID must be 10 digits (1… Saudi, 2… resident)" if nid else "no Iqama / ID number")
        if not iban:
            probs.append("no IBAN")
        elif not iban_ok(iban):
            probs.append("IBAN is not right (SA + 22 digits)")
        other = _f(p.get("transport_allowance")) + _f(p.get("other_allowance")) + _f(p.get("overtime_amount")) \
            + _f(p.get("bonus_amount"))
        if _f(p.get("net_salary")) <= 0:
            probs.append("net salary is 0 or less")
        out.append({"payslip_id": p["payslip_id"], "employee_id": p["employee_id"], "code": e.get("employee_code") or "",
                    "id": nid, "name": p.get("employee_name_en") or "", "iban": iban, "bank_code": bank_code(iban),
                    "bank": BANKS.get(bank_code(iban)) or p.get("bank_name") or e.get("bank_name") or "",
                    "basic": round(_f(p.get("basic_salary")), 2), "housing": round(_f(p.get("housing_allowance")), 2),
                    "other": round(other, 2), "deductions": round(_f(p.get("total_deductions")), 2),
                    "net": round(_f(p.get("net_salary")), 2), "problems": probs})
    return out


WPS_HEADERS = ["Employee ID (Iqama / National ID)", "Employee Name", "IBAN", "Bank Code", "Bank Name",
               "Basic Salary", "Housing Allowance", "Other Earnings", "Deductions", "Net Salary",
               "Payment Date", "Salary Month", "Employee Code"]


def write_wps(run_id, path, payment_date=None):
    """The salary file (CSV, UTF-8) → (path, rows, problems)."""
    run = run_by_id(run_id)
    comp = db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
    rows = wps_rows(run_id)
    pay_d = (_d(payment_date) or date.today()).isoformat()
    month = "%04d-%02d" % (int(run["run_year"]), int(run["run_month"]))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["EMPLOYER", comp.get("company_name_en") or "", "CR " + str(comp.get("cr_number") or ""),
                    "VAT " + str(comp.get("vat_registration_no") or ""), "Employees %d" % len(rows),
                    "Total net %.2f SAR" % sum(r["net"] for r in rows), "Month " + month])
        w.writerow(WPS_HEADERS)
        for r in rows:
            w.writerow([r["id"], r["name"], r["iban"], r["bank_code"], r["bank"], "%.2f" % r["basic"],
                        "%.2f" % r["housing"], "%.2f" % r["other"], "%.2f" % r["deductions"], "%.2f" % r["net"],
                        pay_d, month, r["code"]])
        w.writerow(["TOTAL", "", "", "", "", "%.2f" % sum(r["basic"] for r in rows),
                    "%.2f" % sum(r["housing"] for r in rows), "%.2f" % sum(r["other"] for r in rows),
                    "%.2f" % sum(r["deductions"] for r in rows), "%.2f" % sum(r["net"] for r in rows), "", "", ""])
    return path, rows, [r for r in rows if r["problems"]]


def wps_filename(run_id):
    run = run_by_id(run_id)
    comp = db.fetchone("SELECT cr_number FROM company WHERE company_id=1") or {}
    cr = "".join(ch for ch in str(comp.get("cr_number") or "") if ch.isalnum()) or "DayBill"
    return "WPS_%s_%04d%02d.csv" % (cr, int(run["run_year"]), int(run["run_month"]))


# ── people / numbers for the screens ─────────────────────────
def staff_summary(today=None):
    """Head count, Saudis %, monthly cost (gross + employer GOSI), documents."""
    rows = [dict(r) for r in (db.fetchall("SELECT * FROM employees WHERE is_active=1") or [])]
    n = len(rows)
    sa = sum(1 for r in rows if r.get("is_saudi"))
    cost = 0.0
    for r in rows:
        g = PE.calc_gosi(_f(r.get("basic_salary")), _f(r.get("housing_allowance")), bool(r.get("is_saudi")),
                         r.get("gosi_system") or "old")
        cost += PE.actual_wage(r, "actual") + g["employer"]
    docs = HT.expiring(today=today)
    return {"employees": n, "saudis": sa, "saudi_pct": round(sa * 100.0 / n, 1) if n else 0.0,
            "monthly_cost": round(cost, 2), "docs_due": len(docs),
            "docs_expired": sum(1 for d in docs if d["days_left"] < 0)}


def payslip_pdf(payslip_id, folder=None, path=None):
    from modules.payslip_pdf import generate_payslip_pdf
    ps = dict(db.fetchone("SELECT * FROM payslips WHERE payslip_id=?", (int(payslip_id),)))
    run = dict(db.fetchone("SELECT * FROM payroll_runs WHERE run_id=?", (ps["run_id"],)))
    comp = db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
    if not folder:
        try:
            from modules import whatsapp as wa
            folder = wa.pdf_folder()
        except Exception:
            import tempfile
            folder = tempfile.gettempdir()
    safe = "".join(ch if ch.isalnum() else "_" for ch in (ps.get("employee_name_en") or "employee"))[:40]
    path = path or os.path.join(folder, "Payslip_%s_%s.pdf" % (safe, (run.get("run_label") or "").replace(" ", "_")))
    generate_payslip_pdf(ps, run, dict(comp), path)
    return path


def send_payslip(payslip_id):
    """WhatsApp the payslip to the employee → (ok, message).
    Cloud API: the PDF with the documents template ({{1}} name, {{2}} month,
    {{3}} net). WhatsApp app: the chat opens (drop the PDF in)."""
    from modules import whatsapp as wa
    ps = dict(db.fetchone("SELECT * FROM payslips WHERE payslip_id=?", (int(payslip_id),)))
    run = dict(db.fetchone("SELECT * FROM payroll_runs WHERE run_id=?", (ps["run_id"],)))
    e = db.fetchone("SELECT * FROM employees WHERE employee_id=?", (ps["employee_id"],)) or {}
    phone = wa.normalize_phone(e.get("phone") if _has("employees", "phone") else "")
    if not phone:
        return False, "%s has no mobile number (HR ▸ Employees ▸ edit ▸ Mobile)." % ps.get("employee_name_en")
    pdf = payslip_pdf(payslip_id)
    net = "{:,.2f}".format(_f(ps.get("net_salary")))
    text = ("Dear %s,\nYour payslip for %s is attached.\nNet salary: %s SAR"
            % (ps.get("employee_name_en"), run.get("run_label"), net))
    if wa.mode() == "api":
        ok, res = wa.api_send(phone, text, pdf, [ps.get("employee_name_en") or "-", run.get("run_label") or "-",
                                                 net], kind="payslip")
        wa.log("payslip", payslip_id, phone, ok, res)
        return ok, ("Sent ✔" if ok else "WhatsApp Cloud API: %s" % res)
    how = wa.open_chat(phone, text)
    wa.show_file(pdf)
    wa.log("payslip", payslip_id, phone, True, "opened chat (%s)" % how)
    return True, "WhatsApp opened — drop the PDF into the chat and press Send:\n%s" % pdf
