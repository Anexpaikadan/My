# ============================================================
# DayBill ERP - Reminders (v7.12.0)
# Things to remember on a date: renew the CR, pay the rent, call a
# customer … One can repeat every week / month / year; ticking a
# repeating reminder Done moves it to its next date.
#   save(values, rid=None)  rows(show)  due(user_id)  done(rid)  delete(rid)
# ============================================================
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

REPEATS = [("none", "Once"), ("week", "Every week"), ("month", "Every month"),
           ("year", "Every year")]


def ready():
    try:
        db.fetchall("SELECT reminder_id FROM reminders WHERE 1=0")
        return True
    except Exception:
        return False


def _d(v):
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def next_date(d, every):
    d = _d(d)
    if not d or every not in ("week", "month", "year"):
        return None
    if every == "week":
        return d + timedelta(days=7)
    if every == "year":
        try:
            return d.replace(year=d.year + 1)
        except ValueError:                       # 29 Feb
            return d.replace(year=d.year + 1, day=28)
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    day = d.day
    while day > 28:
        try:
            return date(y, m, day)
        except ValueError:
            day -= 1
    return date(y, m, day)


def rows(show="open", user_id=None):
    """show: 'open' | 'done' | 'all'"""
    if not ready():
        return []
    sql = "SELECT * FROM reminders WHERE 1=1"
    params = []
    if show == "open":
        sql += " AND is_done=0"
    elif show == "done":
        sql += " AND is_done=1"
    if user_id:
        sql += " AND (for_user_id IS NULL OR for_user_id=?)"
        params.append(int(user_id))
    sql += " ORDER BY is_done, due_date, reminder_id"
    try:
        return [dict(r) for r in (db.fetchall(sql, tuple(params)) or [])]
    except Exception:
        return []


def due(user_id=None, on=None):
    """Open reminders due today or earlier for this user."""
    on = _d(on) or date.today()
    return [r for r in rows("open", user_id) if (_d(r.get("due_date")) or on) <= on]


def save(values, rid=None, user_id=None):
    title = str(values.get("title") or "").strip()
    if not title:
        return False, "Type what to remember.", rid
    d = _d(values.get("due_date"))
    if not d:
        return False, "Pick the date (YYYY-MM-DD).", rid
    rep = values.get("repeat_every") or "none"
    if rep not in dict(REPEATS):
        rep = "none"
    who = values.get("for_user_id") or None
    det = str(values.get("details") or "").strip()[:500] or None
    if rid:
        db.execute("UPDATE reminders SET title=?, details=?, due_date=?, repeat_every=?, "
                   "for_user_id=? WHERE reminder_id=?",
                   (title[:150], det, d.isoformat(), rep, who, int(rid)))
    else:
        db.execute("INSERT INTO reminders (title, details, due_date, repeat_every, for_user_id, "
                   "is_done, created_by) VALUES (?, ?, ?, ?, ?, 0, ?)",
                   (title[:150], det, d.isoformat(), rep, who, user_id))
        rid = db.last_identity("reminders", "reminder_id")
    return True, "Saved.", rid


def done(rid):
    """Tick off; a repeating one moves on to its next date instead.
    Returns the next date (repeating) or None."""
    r = db.fetchone("SELECT * FROM reminders WHERE reminder_id=?", (int(rid),))
    if not r:
        return None
    nd = next_date(r.get("due_date"), r.get("repeat_every"))
    if nd:
        while nd <= date.today():                 # long overdue: the next one still ahead
            nd = next_date(nd, r.get("repeat_every"))
        db.execute("UPDATE reminders SET due_date=? WHERE reminder_id=?", (nd.isoformat(), int(rid)))
        return nd
    db.execute("UPDATE reminders SET is_done=1, done_at=GETDATE() WHERE reminder_id=?", (int(rid),))
    return None


def snooze(rid, days=1):
    d = date.today() + timedelta(days=int(days))
    db.execute("UPDATE reminders SET due_date=? WHERE reminder_id=?", (d.isoformat(), int(rid)))
    return d


def reopen(rid):
    db.execute("UPDATE reminders SET is_done=0, done_at=NULL WHERE reminder_id=?", (int(rid),))


def delete(rid):
    db.execute("DELETE FROM reminders WHERE reminder_id=?", (int(rid),))
