# ============================================================
# DayBill ERP - Payroll Calculation Engine
# Saudi labor law: GOSI, overtime, End-of-Service gratuity
# Pure functions (no DB) so they are easy to test.
# ============================================================

# ── GOSI rates ────────────────────────────────────────────────
# OLD system (Saudis first registered with GOSI before 3 July 2024):
#   pension 9% + 9%, SANED 0.75% + 0.75%, hazards 2% employer
#   → employee 9.75%, employer 11.75%
# NEW system (Social Insurance Law, registered on / after 3 July 2024):
#   the pension part steps up every 1 July by 0.5 point each side:
#   2024 9% · 2025 9.5% · 2026 10% · 2027 10.5% · 2028 11%
#   (SANED and hazards stay the same)
# Non-Saudis: employer 2% (hazards only), employee 0%.
# All of these are settings (Settings ▸ HR & Payroll ▸ GOSI) so a new
# GOSI decision needs no new version (v6.0).
GOSI_SAUDI_EMPLOYEE   = 0.0975
GOSI_SAUDI_EMPLOYER   = 0.1175
GOSI_NONSAUDI_EMPLOYEE = 0.0
GOSI_NONSAUDI_EMPLOYER = 0.02
GOSI_NEW_SYSTEM_FROM = "2024-07-03"
GOSI_NEW_PENSION_STEPS = "2024-07-03:9,2025-07-01:9.5,2026-07-01:10,2027-07-01:10.5,2028-07-01:11"

# GOSI is capped at SAR 45,000 of contributory wage (basic + housing)
GOSI_WAGE_CAP = 45000.0

# Standard working hours per month for overtime hourly rate
STANDARD_MONTHLY_HOURS = 240.0   # ~30 days * 8h  (Settings ▸ HR ▸ hours a day × 30)
OVERTIME_MULTIPLIER = 1.5         # (old formula on basic only — kept for reference)

# End-of-service reasons (Saudi Labour Law arts. 80, 81, 84, 85, 87)
EOS_REASONS = [
    ("termination", "Ended by the employer / end of contract — full award"),
    ("resignation", "Resignation — share by years (art. 85: <2 none, 2–5 one third, 5–10 two thirds, 10+ full)"),
    ("resignation_full", "Resignation with full award (art. 81 employer breach · art. 87 force majeure, "
                         "woman within 6 months of marriage / 3 months of giving birth)"),
    ("dismissal_80", "Dismissed under art. 80 (serious misconduct) — no award"),
]


def _setting(key, default):
    try:
        from config import settings as cfg
        v = cfg.get(key, default)
        return default if v in (None, "") else v
    except Exception:
        return default


def _pct(key, default):
    try:
        return float(_setting(key, default)) / 100.0
    except (TypeError, ValueError):
        return float(default) / 100.0


def gosi_rates(is_saudi, system="old", on=None):
    """(employee rate, employer rate) as fractions.
    system: 'old' / 'new' (Saudis); on: the payroll date (new system steps)."""
    if not is_saudi:
        return (_pct("gosi_nonsaudi_employee_pct", 0.0), _pct("gosi_nonsaudi_employer_pct", 2.0))
    saned = _pct("gosi_saned_pct", 0.75)
    hazard = _pct("gosi_hazard_pct", 2.0)
    if str(system or "old").lower() != "new":
        pension = _pct("gosi_old_pension_pct", 9.0)
    else:
        from datetime import date as _date
        d = str(on or _date.today().isoformat())[:10]
        pension = 0.09
        steps = str(_setting("gosi_new_pension_steps", GOSI_NEW_PENSION_STEPS))
        for part in steps.split(","):
            try:
                when, pct = part.split(":")
                if d >= when.strip():
                    pension = float(pct) / 100.0
            except ValueError:
                continue
    return (round(pension + saned, 6), round(pension + saned + hazard, 6))


def guess_system(join_date, is_saudi=True):
    """'new' when the employee joined on / after 3 July 2024 — only a first
    guess: someone who worked elsewhere before stays on the old system.
    The employee form lets you choose."""
    if not is_saudi:
        return ""
    return "new" if str(join_date or "")[:10] >= str(_setting("gosi_new_system_from",
                                                              GOSI_NEW_SYSTEM_FROM)) else "old"


def gosi_contributory_wage(basic: float, housing: float) -> float:
    """GOSI base = basic + housing, capped (SAR 45,000 by default)."""
    wage = float(basic) + float(housing)
    try:
        cap = float(_setting("gosi_wage_cap", GOSI_WAGE_CAP))
    except (TypeError, ValueError):
        cap = GOSI_WAGE_CAP
    return min(wage, cap)


def calc_gosi(basic: float, housing: float, is_saudi: bool, system="old", on=None) -> dict:
    """Return {employee, employer, base, employee_rate, employer_rate}."""
    base = gosi_contributory_wage(basic, housing)
    er, rr = gosi_rates(is_saudi, system, on)
    return {"employee": round(base * er, 2), "employer": round(base * rr, 2),
            "base": round(base, 2), "employee_rate": er, "employer_rate": rr}


def daily_hours():
    try:
        return max(1.0, float(_setting("hr_daily_hours", 8)))
    except (TypeError, ValueError):
        return 8.0


def monthly_hours():
    """Hours of one month for the hourly wage: 30 days × the hours of a day."""
    return 30.0 * daily_hours()


def wage_basis():
    """'actual' = basic + every fixed allowance (the law's 'actual wage', art. 2)
    or 'basic_housing' (if the contract / work rules say so)."""
    v = str(_setting("hr_wage_basis", "actual") or "actual").lower()
    return "basic_housing" if v.startswith("basic") else "actual"


def actual_wage(emp, basis=None):
    """The monthly wage used for end of service, leave pay and the daily /
    hourly wage: basic + housing + transport + other allowances (actual wage)."""
    basis = basis or wage_basis()
    f = lambda k: float(emp.get(k, 0) or 0)
    if basis == "basic_housing":
        return round(f("basic_salary") + f("housing_allowance"), 2)
    return round(f("basic_salary") + f("housing_allowance") + f("transport_allowance") + f("other_allowance"), 2)


def calc_overtime(basic: float, overtime_hours: float, actual=None) -> float:
    """
    Saudi Labour Law art. 107: each overtime hour = the hourly ACTUAL wage
    + 50 % of the hourly BASIC wage.  hourly = monthly / (30 × hours a day).
    (actual not given → basic, i.e. the old 1.5 × basic.)
    """
    if overtime_hours <= 0 or basic <= 0:
        return 0.0
    hours = monthly_hours()
    act = float(actual if actual is not None else basic)
    rate = act / hours + 0.5 * float(basic) / hours
    return round(rate * float(overtime_hours), 2)


def overtime_rate(emp):
    basic = float(emp.get("basic_salary", 0) or 0)
    if not basic:
        return 0.0
    hours = monthly_hours()                      # not rounded to 2 places: the hourly rate itself
    return round(actual_wage(emp, "actual") / hours + 0.5 * basic / hours, 4)


def calc_payslip(emp: dict, overtime_hours: float = 0.0,
                 loan_deduction: float = 0.0,
                 other_deduction: float = 0.0, on=None, bonus: float = 0.0,
                 absence_deduction: float = 0.0, sick_deduction: float = 0.0) -> dict:
    """
    Compute a full payslip for one employee.
    emp keys: basic_salary, housing_allowance, transport_allowance,
              other_allowance, is_saudi
    gross = basic + allowances + overtime + bonus; deductions = GOSI (employee)
    + loan + absence / unpaid days + sick-leave part not paid + other.
    """
    basic     = float(emp.get("basic_salary", 0) or 0)
    housing   = float(emp.get("housing_allowance", 0) or 0)
    transport = float(emp.get("transport_allowance", 0) or 0)
    other_al  = float(emp.get("other_allowance", 0) or 0)
    is_saudi  = bool(emp.get("is_saudi", 0))

    overtime_amount = calc_overtime(basic, overtime_hours, basic + housing + transport + other_al)
    bonus = round(float(bonus or 0), 2)

    gross = basic + housing + transport + other_al + overtime_amount + bonus

    # not chosen yet → old system, exactly as before v6.0 (the employee
    # form suggests 'new' from the join date; the shop confirms it)
    system = emp.get("gosi_system") or "old"
    gosi = calc_gosi(basic, housing, is_saudi, system, on)
    gosi_emp  = gosi["employee"]
    gosi_empr = gosi["employer"]

    absence_deduction = round(float(absence_deduction or 0), 2)
    sick_deduction = round(float(sick_deduction or 0), 2)
    total_ded = round(gosi_emp + float(loan_deduction) + float(other_deduction)
                      + absence_deduction + sick_deduction, 2)
    net = round(gross - total_ded, 2)

    return {
        "basic_salary":        round(basic, 2),
        "housing_allowance":   round(housing, 2),
        "transport_allowance": round(transport, 2),
        "other_allowance":     round(other_al, 2),
        "overtime_hours":      round(float(overtime_hours), 2),
        "overtime_amount":     overtime_amount,
        "bonus_amount":        bonus,
        "absence_deduction":   absence_deduction,
        "sick_deduction":      sick_deduction,
        "gross_salary":        round(gross, 2),
        "gosi_employee":       gosi_emp,
        "gosi_employer":       gosi_empr,
        "loan_deduction":      round(float(loan_deduction), 2),
        "other_deduction":     round(float(other_deduction), 2),
        "total_deductions":    total_ded,
        "net_salary":          net,
    }


# ── End of Service Gratuity (Saudi Labor Law Art. 84) ─────────
def calc_eos_gratuity(years_served: float, last_wage: float,
                      reason: str = "termination") -> dict:
    """
    End-of-service award (art. 84), on the LAST ACTUAL wage (actual_wage()):
      - first 5 years:  half a month's wage per year
      - after 5 years:  a full month's wage per year
      - parts of a year count in proportion
    Resignation (art. 85): < 2 years none · 2–5 one third · 5–10 two thirds ·
      10+ full.  'resignation_full' (art. 81 / 87) and 'termination' /
      end of contract: full.  'dismissal_80' (art. 80): none.
    """
    years = max(0.0, float(years_served))
    wage  = float(last_wage)

    # Base award
    if years <= 5:
        award = years * (wage / 2)
    else:
        award = (5 * (wage / 2)) + ((years - 5) * wage)
    full = award

    reason = (reason or "termination").lower()
    factor = 1.0
    if reason == "resignation":
        if years < 2:
            factor = 0.0
        elif years < 5:
            factor = 1.0 / 3.0
        elif years < 10:
            factor = 2.0 / 3.0
        else:
            factor = 1.0
    elif reason == "dismissal_80":
        factor = 0.0
    award = full * factor

    return {
        "years_served":   round(years, 2),
        "last_wage":      round(wage, 2),
        "reason":         reason,
        "award_full":     round(full, 2),
        "share":          round(factor, 4),
        "gratuity_amount": round(award, 2),
    }


def years_between(join_date, end_date) -> float:
    """Fractional years between two dates (date objects or ISO strings)."""
    from datetime import datetime
    def _d(x):
        if isinstance(x, str):
            return datetime.strptime(x[:10], "%Y-%m-%d").date()
        return x
    j, e = _d(join_date), _d(end_date)
    days = (e - j).days
    return round(days / 365.25, 2)


# ── Self-test ──────────────────────────────────────────────────
if __name__ == "__main__":
    emp = {"basic_salary": 6000, "housing_allowance": 1500,
           "transport_allowance": 500, "other_allowance": 0, "is_saudi": True}
    ps = calc_payslip(emp, overtime_hours=10, loan_deduction=500)
    for k, v in ps.items():
        print(f"{k:22s}: {v}")
    print("---")
    print("EOS (6y, term):", calc_eos_gratuity(6, 7500, "termination"))
    print("EOS (3y, resign):", calc_eos_gratuity(3, 7500, "resignation"))
