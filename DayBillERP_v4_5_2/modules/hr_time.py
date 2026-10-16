# ============================================================
# DayBill ERP - leave & attendance (v6.0)
# ------------------------------------------------------------
# Leave    annual / sick / unpaid / emergency / Hajj / maternity /
#          other, from – to (days counted), paid or not.
#          Annual balance: 21 days a year, 30 after 5 years of service
#          (Saudi Labour Law art. 109) minus the annual leave taken.
# Attendance  one row per employee per day: present / absent / late /
#          leave / off, check-in / check-out (hours worked).
# Payroll  unpaid days of a month (absent + unpaid leave) can be taken
#          off the salary: (basic + housing + transport + other) / 30
#          per day (HR ▸ Payroll run uses it when the setting is on).
# ============================================================
import sys, os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

LEAVE_TYPES = [("annual", "Annual"), ("sick", "Sick"), ("unpaid", "Unpaid"),
               ("emergency", "Emergency"), ("marriage", "Marriage"), ("paternity", "New baby (father)"),
               ("bereavement", "Bereavement"), ("maternity", "Maternity"), ("hajj", "Hajj"),
               ("exam", "Exam"), ("other", "Other")]
# v6.6: paid days the Saudi Labour Law gives (arts. 113, 114, 151 — 2025 amendment)
LAW_DAYS = {"marriage": (5, "Marriage leave is 5 paid days (art. 113)"),
            "paternity": (3, "A father gets 3 paid days, within 7 days of the birth (art. 113)"),
            "bereavement": (5, "Bereavement is 5 paid days for a spouse, parent or child, 3 for a brother / "
                               "sister (art. 113)"),
            "maternity": (84, "Maternity leave is 12 weeks = 84 paid days (art. 151, 2025 law)"),
            "hajj": (15, "Hajj leave is 10–15 paid days, once, after 2 years of service (art. 114)")}
DOCS = [("iqama_expiry", "Iqama / ID"), ("passport_expiry", "Passport"),
        ("insurance_expiry", "Medical insurance"), ("contract_end", "Contract")]
STATUSES = [("present", "Present"), ("late", "Late"), ("absent", "Absent"),
            ("leave", "On leave"), ("off", "Day off")]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _d(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def ready():
    try:
        db.fetchone("SELECT TOP 1 leave_id FROM employee_leaves")
        db.fetchone("SELECT TOP 1 att_id FROM attendance")
        return True
    except Exception:
        return False


def employees(active_only=True):
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT employee_id, employee_code, full_name_en, join_date, basic_salary, housing_allowance, "
            "transport_allowance, other_allowance FROM employees %s ORDER BY full_name_en"
            % ("WHERE is_active=1" if active_only else "")) or []]
    except Exception:
        return []


# ── leave ────────────────────────────────────────────────────
def add_leave(employee_id, leave_type, start, end, paid=None, notes=""):
    s, e = _d(start), _d(end)
    if not employee_id:
        raise ValueError("Choose the employee.")
    if not s or not e:
        raise ValueError("Type the first and the last day of the leave.")
    if e < s:
        raise ValueError("The last day is before the first day.")
    lt = leave_type if leave_type in dict(LEAVE_TYPES) else "other"
    if paid is None:
        paid = lt != "unpaid"
    clash = db.execute_scalar("SELECT COUNT(*) FROM employee_leaves WHERE employee_id=? AND "
                              "status<>'cancelled' AND start_date <= ? AND end_date >= ?",
                              (int(employee_id), e.isoformat(), s.isoformat()))
    if clash:
        raise ValueError("This employee already has leave in these days.")
    days = (e - s).days + 1
    if lt == "annual":
        if carry():
            bal = annual_balance(employee_id, on=e)
            if days > bal["balance"] + 1e-6:
                raise ValueError("Only %g annual leave day(s) earned by %s (asked %d)."
                                 % (bal["balance"], e.isoformat(), days))
        else:
            bal = annual_balance(employee_id, s.year)
            if days > bal["balance"] + 1e-6:
                raise ValueError("Only %g annual leave day(s) left in %d (asked %d)." % (bal["balance"], s.year, days))
    if paid and lt in LAW_DAYS and days > LAW_DAYS[lt][0]:
        raise ValueError("%s — save the extra days as Annual or Unpaid leave." % LAW_DAYS[lt][1])
    if lt == "hajj" and paid:
        j = _join(employee_id)
        if j and (s - j).days < 2 * 365:
            raise ValueError("Hajj leave comes after 2 years of service (art. 114) — use Annual or Unpaid leave.")
        if db.execute_scalar("SELECT COUNT(*) FROM employee_leaves WHERE employee_id=? AND leave_type='hajj' "
                             "AND status<>'cancelled' AND paid=1", (int(employee_id),)):
            raise ValueError("Paid Hajj leave is once in the service (art. 114) — use Annual or Unpaid leave.")
    with db.transaction():
        db.execute("INSERT INTO employee_leaves (employee_id, leave_type, start_date, end_date, days, paid, "
                   "status, notes) VALUES (?,?,?,?,?,?, 'approved', ?)",
                   (int(employee_id), lt, s.isoformat(), e.isoformat(), days, 1 if paid else 0,
                    (notes or "")[:300] or None))
        lid = db.last_identity("employee_leaves", "leave_id")
        d = s
        while d <= e:                                  # the days show on attendance too
            _mark(employee_id, d, "leave", None, None, "%s leave" % dict(LEAVE_TYPES)[lt])
            d += timedelta(days=1)
    return lid


def delete_leave(leave_id):
    r = db.fetchone("SELECT * FROM employee_leaves WHERE leave_id=?", (int(leave_id),))
    if not r:
        return
    with db.transaction():
        db.execute("DELETE FROM attendance WHERE employee_id=? AND status='leave' AND work_date BETWEEN ? AND ?",
                   (r["employee_id"], str(r["start_date"])[:10], str(r["end_date"])[:10]))
        db.execute("DELETE FROM employee_leaves WHERE leave_id=?", (int(leave_id),))


def leaves(employee_id=None, year=None):
    cond, params = ["1=1"], []
    if employee_id:
        cond.append("l.employee_id=?"); params.append(int(employee_id))
    if year:
        cond.append("l.end_date >= ? AND l.start_date <= ?")
        params += ["%d-01-01" % int(year), "%d-12-31" % int(year)]
    try:
        return [dict(r) for r in db.fetchall(
            "SELECT l.*, e.full_name_en, e.employee_code FROM employee_leaves l JOIN employees e ON "
            "e.employee_id=l.employee_id WHERE %s ORDER BY l.start_date DESC" % " AND ".join(cond),
            tuple(params)) or []]
    except Exception:
        return []


def _join(employee_id):
    try:
        return _d(db.execute_scalar("SELECT join_date FROM employees WHERE employee_id=?", (int(employee_id),)))
    except Exception:
        return None


def _cfg(key, default):
    try:
        from config import settings as cfg
        v = cfg.get(key, default)
        return default if v in (None, "") else v
    except Exception:
        return default


def carry():
    """v6.6: unused annual leave carries on (earned from the join date, art. 109 /
    paid at the end of service, art. 111). Off = the old way: 21 / 30 days per
    calendar year, unused days are not carried."""
    v = _cfg("hr_leave_carry", True)
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")


def entitlement(employee_id, on=None):
    """21 days a year; 30 after 5 full years of service."""
    j = _join(employee_id)
    on = _d(on) or date.today()
    if j and (on - j).days >= 5 * 365:
        return 30
    return 21


def accrued(employee_id, on=None):
    """Annual leave earned from the join date to `on`: 21 days a year for the
    first 5 years of service, 30 a year after (art. 109)."""
    j = _join(employee_id)
    on = _d(on) or date.today()
    if not j or on < j:
        return 0.0
    days = (on - j).days + 1
    first = min(days, 5 * 365)
    rest = max(0, days - 5 * 365)
    return round(first * 21.0 / 365.0 + rest * 30.0 / 365.0, 2)


def opening(employee_id):
    """(date, days) — the annual leave balance typed in for a day (leave
    taken before DayBill); (None, 0) when not set."""
    try:
        r = db.fetchone("SELECT leave_open_date, leave_open_days FROM employees WHERE employee_id=?",
                        (int(employee_id),)) or {}
    except Exception:
        return None, 0.0
    d = _d(r.get("leave_open_date"))
    return (d, _f(r.get("leave_open_days"))) if d else (None, 0.0)


def annual_taken(employee_id, until=None, since=None):
    until = _d(until) or date.today()
    since = _d(since)
    used = 0.0
    for l in leaves(employee_id):
        if l.get("leave_type") == "annual" and l.get("status") != "cancelled":
            s = _d(l["start_date"])
            if s and s <= until and (since is None or s > since):
                used += _f(l.get("days")) or ((_d(l["end_date"]) - s).days + 1)
    return used


def annual_balance(employee_id, year=None, on=None):
    if carry():
        y = int(year or date.today().year)
        if on:
            on = _d(on)
        elif year and int(year) < date.today().year:
            on = date(int(year), 12, 31)
        else:
            on = date.today()
        od, odays = opening(employee_id)
        if od and on >= od:                        # balance typed in for a day + earned after it
            acc = round(odays + accrued(employee_id, on) - accrued(employee_id, od), 2)
            used = annual_taken(employee_id, on, since=od)
        else:
            acc = accrued(employee_id, on)
            used = annual_taken(employee_id, on)
        return {"year": y, "entitlement": entitlement(employee_id, on), "accrued": acc, "used": used,
                "balance": round(acc - used, 2), "mode": "accrued", "as_of": on.isoformat(),
                "opening_date": od.isoformat() if od else None, "opening_days": odays}
    y = int(year or (_d(on).year if on else date.today().year))
    ent = entitlement(employee_id, date(y, 12, 31))
    used = 0.0
    for l in leaves(employee_id, y):
        if l.get("leave_type") == "annual" and l.get("status") != "cancelled":
            s, e = max(_d(l["start_date"]), date(y, 1, 1)), min(_d(l["end_date"]), date(y, 12, 31))
            used += max(0, (e - s).days + 1)
    return {"year": y, "entitlement": ent, "accrued": ent, "used": used, "balance": round(ent - used, 1),
            "mode": "year", "as_of": date(y, 12, 31).isoformat()}


def balance_text(employee_id):
    b = annual_balance(employee_id)
    if b["mode"] == "accrued":
        since = ("%g on %s + earned since" % (b["opening_days"], b["opening_date"]) if b.get("opening_date")
                 else "earned since joining")
        return ("Annual leave (%d days a year now): %s %g · taken %g · left %g (as of %s)"
                % (b["entitlement"], since, b["accrued"], b["used"], b["balance"], b["as_of"]))
    return ("Annual leave %d: %g day(s) a year · taken %g · left %g"
            % (b["year"], b["entitlement"], b["used"], b["balance"]))


# ── attendance ───────────────────────────────────────────────
def _hours(cin, cout):
    try:
        a = datetime.strptime(str(cin)[:5], "%H:%M")
        b = datetime.strptime(str(cout)[:5], "%H:%M")
        h = (b - a).total_seconds() / 3600.0
        if h < 0:
            h += 24                                    # night shift
        return round(h, 2)
    except Exception:
        return None


def _mark(employee_id, day, status, cin=None, cout=None, notes=""):
    d = _d(day).isoformat()
    st = status if status in dict(STATUSES) else "present"
    h = _hours(cin, cout) if cin and cout else None
    if db.execute_scalar("SELECT att_id FROM attendance WHERE employee_id=? AND work_date=?",
                         (int(employee_id), d)):
        db.execute("UPDATE attendance SET status=?, check_in=?, check_out=?, hours=?, notes=? "
                   "WHERE employee_id=? AND work_date=?",
                   (st, cin or None, cout or None, h, (notes or "")[:200] or None, int(employee_id), d))
    else:
        db.execute("INSERT INTO attendance (employee_id, work_date, check_in, check_out, hours, status, notes) "
                   "VALUES (?,?,?,?,?,?,?)", (int(employee_id), d, cin or None, cout or None, h, st,
                                              (notes or "")[:200] or None))


def mark(employee_id, day, status, cin=None, cout=None, notes=""):
    for t in (cin, cout):
        if t and _hours(t, t) is None:
            raise ValueError("Times are like 08:30.")
    with db.transaction():
        _mark(employee_id, day, status, cin, cout, notes)


def day_sheet(day):
    """Every active employee with the day's attendance (or blank)."""
    d = _d(day).isoformat()
    try:
        rows = {r["employee_id"]: dict(r) for r in db.fetchall(
            "SELECT * FROM attendance WHERE work_date=?", (d,)) or []}
    except Exception:
        rows = {}
    out = []
    for e in employees():
        a = rows.get(e["employee_id"], {})
        out.append({"employee_id": e["employee_id"], "code": e["employee_code"], "name": e["full_name_en"],
                    "status": a.get("status") or "", "check_in": a.get("check_in") or "",
                    "check_out": a.get("check_out") or "", "hours": a.get("hours"), "notes": a.get("notes") or ""})
    return out


def month_summary(employee_id, year, month):
    first = date(int(year), int(month), 1)
    last = (date(int(year) + (month == 12), (int(month) % 12) + 1, 1) - timedelta(days=1))
    out = {"present": 0, "late": 0, "absent": 0, "leave": 0, "off": 0, "hours": 0.0,
           "unpaid_leave": 0, "days_in_month": (last - first).days + 1}
    try:
        for r in db.fetchall("SELECT status, hours FROM attendance WHERE employee_id=? AND work_date "
                             "BETWEEN ? AND ?", (int(employee_id), first.isoformat(), last.isoformat())) or []:
            if r["status"] in out:
                out[r["status"]] += 1
            out["hours"] += _f(r.get("hours"))
        for l in leaves(employee_id):
            if l.get("paid") in (0, False) and l.get("status") != "cancelled":
                s, e = max(_d(l["start_date"]), first), min(_d(l["end_date"]), last)
                if e >= s:
                    out["unpaid_leave"] += (e - s).days + 1
    except Exception:
        pass
    out["hours"] = round(out["hours"], 2)
    return out


def _month(year, month):
    first = date(int(year), int(month), 1)
    last = (date(int(year) + (int(month) == 12), (int(month) % 12) + 1, 1) - timedelta(days=1))
    return first, last


def sick_tiers_on():
    v = _cfg("hr_sick_tiers", True)
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")


def sick_factors(employee_id):
    """{day: part of the wage paid} for every (paid) sick-leave day — art. 117:
    in one year counted from the first sick day, 30 days full pay, the next 60
    days three quarters, the next 30 days without pay."""
    days = set()
    for l in leaves(employee_id):
        if l.get("leave_type") == "sick" and l.get("status") != "cancelled" and l.get("paid") not in (0, False):
            d, e = _d(l["start_date"]), _d(l["end_date"])
            while d and e and d <= e:
                days.add(d)
                d += timedelta(days=1)
    out, start, n = {}, None, 0
    for d in sorted(days):
        if start is None or (d - start).days >= 365:
            start, n = d, 0
        n += 1
        out[d] = 1.0 if n <= 30 else (0.75 if n <= 90 else 0.0)
    return out


def sick_deduction(emp, year, month):
    """(amount, unpaid day-equivalents) of the sick days of the month the law
    does not pay in full."""
    if not sick_tiers_on():
        return 0.0, 0.0
    first, last = _month(year, month)
    lost = sum(1.0 - f for d, f in sick_factors(emp["employee_id"]).items() if first <= d <= last)
    if lost <= 0:
        return 0.0, 0.0
    from modules import payroll_engine as PE
    return round(PE.actual_wage(emp, "actual") / 30.0 * lost, 2), round(lost, 2)


def overtime_hours(employee_id, year, month):
    """Overtime from attendance: hours above the day's hours on a working day,
    and every hour worked on a day off (art. 107)."""
    first, last = _month(year, month)
    total = 0.0
    try:
        emp = db.fetchone("SELECT * FROM employees WHERE employee_id=?", (int(employee_id),)) or {}
    except Exception:
        emp = {}
    try:
        for r in db.fetchall("SELECT status, hours, work_date FROM attendance WHERE employee_id=? AND work_date "
                             "BETWEEN ? AND ?", (int(employee_id), first.isoformat(), last.isoformat())) or []:
            h = r.get("hours")
            if h is None:
                continue
            h = _f(h)
            if r.get("status") in ("present", "late"):
                total += max(0.0, h - day_hours(dict(emp), r.get("work_date")))   # v6.6: Ramadan 6 h
            elif r.get("status") == "off":
                total += h
    except Exception:
        return 0.0
    return round(total, 2)


# ── v6.6: documents with an expiry date ─────────────────────
def doc_alert_days():
    try:
        return max(1, int(float(_cfg("hr_doc_alert_days", 30))))
    except (TypeError, ValueError):
        return 30


def expiring(days=None, today=None, include_all=False):
    """[{employee_id, code, name, doc, doc_key, date, days_left}] — expired or
    expiring within `days` (Settings ▸ HR, 30 by default), soonest first."""
    days = doc_alert_days() if days is None else int(days)
    today = _d(today) or date.today()
    cols = ", ".join(k for k, _ in DOCS)
    try:
        rows = db.fetchall("SELECT employee_id, employee_code, full_name_en, %s FROM employees "
                           "WHERE is_active=1" % cols) or []
    except Exception:
        return []
    out = []
    try:                                    # v6.6: probation ends · resignation accepted by law
        extra = {r_["employee_id"]: dict(r_) for r_ in (db.fetchall(
            "SELECT employee_id, join_date, probation_days, resign_date, resign_status FROM employees "
            "WHERE is_active=1") or [])}
    except Exception:
        extra = {}
    for r in rows:
        x = extra.get(r["employee_id"])
        if x:
            pe = probation_end(x)
            if pe and (pe - today).days >= 0 and (include_all or (pe - today).days <= min(days, 14)):
                out.append({"employee_id": r["employee_id"], "code": r.get("employee_code") or "",
                            "name": r.get("full_name_en") or "", "doc": "Probation ends", "doc_key": "probation",
                            "date": pe.isoformat(), "days_left": (pe - today).days})
            rs = resignation(x)
            if rs.get("last_day") and rs.get("status") in ("waiting", "delayed"):
                ld = _d(rs["last_day"])
                out.append({"employee_id": r["employee_id"], "code": r.get("employee_code") or "",
                            "name": r.get("full_name_en") or "",
                            "doc": "Resignation accepted by law" if rs["status"] == "waiting" else "Resignation ends",
                            "doc_key": "resignation", "date": ld.isoformat(), "days_left": (ld - today).days})
        for k, label in DOCS:
            d = _d(r.get(k))
            if not d:
                continue
            left = (d - today).days
            if include_all or left <= days:
                out.append({"employee_id": r["employee_id"], "code": r.get("employee_code") or "",
                            "name": r.get("full_name_en") or "", "doc": label, "doc_key": k,
                            "date": d.isoformat(), "days_left": left})
    out.sort(key=lambda x: x["days_left"])
    return out


def expiry_text(today=None):
    rows = expiring(today=today)
    if not rows:
        return ""
    gone = sum(1 for r in rows if r["days_left"] < 0)
    return ("👔 %d employee document(s) expire within %d days%s — HR ▸ Employees"
            % (len(rows), doc_alert_days(), (" (%d already expired)" % gone) if gone else ""))


def unpaid_deduction(emp, year, month):
    """Salary to take off for absent days + unpaid leave days of the month:
    (basic + housing + transport + other) / 30 per day."""
    s = month_summary(emp["employee_id"], year, month)
    days = s["absent"] + s["unpaid_leave"]
    if days <= 0:
        return 0.0, 0
    monthly = sum(_f(emp.get(k)) for k in ("basic_salary", "housing_allowance",
                                           "transport_allowance", "other_allowance"))
    return round(monthly / 30.0 * days, 2), days


# ── v6.6: Ramadan hours (art. 98) ───────────────────────────
# Ramadan (Umm al-Qura calendar) → Gregorian first / last day. Settings ▸ HR ▸
# "Ramadan dates" can change a year when the moon is seen a day earlier / later.
RAMADAN = {1445: ("2024-03-11", "2024-04-09"), 1446: ("2025-03-01", "2025-03-29"),
           1447: ("2026-02-18", "2026-03-19"), 1448: ("2027-02-08", "2027-03-08"),
           1449: ("2028-01-28", "2028-02-25"), 1450: ("2029-01-16", "2029-02-13"),
           1451: ("2030-01-05", "2030-02-03"), 1452: ("2030-12-26", "2031-01-23"),
           1453: ("2031-12-15", "2032-01-13"), 1454: ("2032-12-04", "2033-01-01"),
           1455: ("2033-11-23", "2033-12-22"), 1456: ("2034-11-12", "2034-12-11"),
           1457: ("2035-11-01", "2035-11-30"), 1458: ("2036-10-20", "2036-11-18"),
           1459: ("2037-10-10", "2037-11-07"), 1460: ("2038-09-30", "2038-10-28"),
           1461: ("2039-09-19", "2039-10-18")}


def ramadan_hours():
    """Working hours a day in Ramadan (Muslim staff, art. 98: at most 6). 0 = off."""
    try:
        return max(0.0, float(_cfg("hr_ramadan_hours", 6) or 0))
    except (TypeError, ValueError):
        return 6.0


def ramadan_ranges():
    """[(first, last)] — the table, changed by Settings ▸ HR ▸ Ramadan dates
    ('2027-02-09:2027-03-09, …' replaces the table's Ramadan that starts near it)."""
    out = [(_d(a), _d(b)) for a, b in RAMADAN.values()]
    for part in str(_cfg("hr_ramadan_dates", "") or "").replace(";", ",").split(","):
        if ":" in part:
            a, b = (x.strip() for x in part.split(":", 1))
            da, db_ = _d(a), _d(b)
            if da and db_ and 25 <= (db_ - da).days <= 31:
                out = [r for r in out if abs((r[0] - da).days) > 20] + [(da, db_)]
    return sorted(out)


def is_ramadan(day):
    d = _d(day)
    return bool(d) and any(a <= d <= b for a, b in ramadan_ranges())


def ramadan_applies(emp):
    """The employee works Ramadan hours (the employee form; empty = yes)."""
    v = (emp or {}).get("ramadan_hours")
    return v is None or v in (1, True, "1", "true", "True")


def day_hours(emp, day):
    """Normal hours of that day for the employee (Ramadan → 6)."""
    from modules import payroll_engine as PE
    std = PE.daily_hours()
    rh = ramadan_hours()
    if rh and rh < std and ramadan_applies(emp) and is_ramadan(day):
        return rh
    return std


# ── v6.6: probation (2025 law: up to 180 days) ──────────────
def probation_days(emp):
    v = (emp or {}).get("probation_days")
    if v in (None, ""):
        v = _cfg("hr_probation_days", 90)
    try:
        return max(0, min(180, int(float(v))))
    except (TypeError, ValueError):
        return 90


def probation_end(emp):
    j = _d((emp or {}).get("join_date"))
    n = probation_days(emp)
    return (j + timedelta(days=n - 1)) if (j and n) else None


# ── v6.6: resignation (art. 79, 2025): withdraw 7 days, accepted after 30 ──
RESIGN_STATUS = [("waiting", "Waiting for an answer"), ("accepted", "Accepted"),
                 ("delayed", "Delayed by the employer (up to 60 days)"), ("withdrawn", "Withdrawn")]


def resignation(emp):
    """{} when there is no resignation, else the dates the law gives."""
    d = _d((emp or {}).get("resign_date"))
    if not d:
        return {}
    st = (emp or {}).get("resign_status") or "waiting"
    info = {"date": d.isoformat(), "status": st,
            "withdraw_until": (d + timedelta(days=7)).isoformat(),
            "auto_accept": (d + timedelta(days=30)).isoformat(),
            "delay_until": (d + timedelta(days=60)).isoformat()}
    if st == "waiting":
        info["text"] = ("Resignation handed in %s — can be withdrawn until %s; if not answered it is "
                        "accepted by law on %s" % (d.isoformat(), info["withdraw_until"], info["auto_accept"]))
        info["last_day"] = info["auto_accept"]
    elif st == "delayed":
        info["text"] = "Resignation %s — delayed by the employer, ends at the latest on %s" % (
            d.isoformat(), info["delay_until"])
        info["last_day"] = info["delay_until"]
    elif st == "accepted":
        info["text"] = "Resignation %s — accepted" % d.isoformat()
        info["last_day"] = None
    else:
        info["text"] = "Resignation %s — withdrawn" % d.isoformat()
        info["last_day"] = None
    return info


# ── v6.6: unpaid leave over 20 days is not service (art. 116) ─
def unpaid_days_not_counted(employee_id, until=None):
    """Days of unpaid leave beyond the first 20 of each leave — the contract is
    suspended for them, so they do not count for the end-of-service years."""
    until = _d(until) or date.today()
    out = 0
    for l in leaves(employee_id):
        if l.get("leave_type") != "unpaid" or l.get("status") == "cancelled":
            continue
        s, e = _d(l["start_date"]), _d(l["end_date"])
        if not s or not e or s > until:
            continue
        e = min(e, until)
        n = (e - s).days + 1
        out += max(0, n - 20)
    return out
