# ============================================================
# DayBill ERP - ⏰ evening jobs on this PC  (v6.4)
# ------------------------------------------------------------
# Checked every minute while DayBill is open (MainWindow starts it):
#   📲 owner's evening report   Settings ▸ WhatsApp ▸ "Send the owner's
#                               evening report automatically" at HH:MM
#   ☁ cloud backup              Settings ▸ Backup ▸ "Copy a backup to the
#                               cloud folder every night" at HH:MM
# Each job runs once per day after its time. When the PC was off at that
# time yesterday, the cloud backup runs 5 minutes after DayBill opens
# (and the evening report of yesterday is sent when WhatsApp Cloud API
# sends by itself). Last runs are kept in config/daily_jobs.json, so
# opening DayBill twice never sends twice.
# Turn these on only on ONE PC (the owner's / main PC).
# ============================================================

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CATCH_UP_MIN = 5                     # minutes after start before a missed job runs
_started = datetime.now()


def _cfg():
    from config import settings as cfg
    return cfg


def _file():
    try:
        from config.paths import config_file
        return config_file("daily_jobs.json")
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "daily_jobs.json")


def state():
    try:
        with open(_file(), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _mark(job, when, **extra):
    s = state()
    s[job] = dict(s.get(job) or {}, last_run=when.strftime("%Y-%m-%d %H:%M"), **extra)
    try:
        with open(_file(), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)
    except Exception:
        pass
    return s


def hhmm(v, default):
    """'9:5' / '21.30' / '2130' → '09:05' / '21:30' (default when bad)."""
    t = str(v or "").strip().replace(".", ":")
    if t.isdigit() and len(t) in (3, 4):
        t = t[:-2] + ":" + t[-2:]
    try:
        h, m = t.split(":")[:2]
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return "%02d:%02d" % (h, m)
    except Exception:
        pass
    return default


def _slot(now, at):
    h, m = map(int, at.split(":"))
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def _last(job):
    v = (state().get(job) or {}).get("last_run")
    try:
        return datetime.strptime(v[:16], "%Y-%m-%d %H:%M")
    except Exception:
        return None


def due(job, at, now=None, catch_up=False, started=None, first_too=True):
    """→ None | 'slot' (today's time passed, not run since) |
    'missed' (yesterday's time was missed — PC off — and DayBill has been
    open CATCH_UP_MIN minutes)."""
    now = now or datetime.now()
    slot = _slot(now, at)
    last = _last(job)
    if now >= slot and (last is None or last < slot):
        return "slot"
    if catch_up:
        y = slot - timedelta(days=1)
        if ((last is None and first_too) or (last is not None and last < y)) \
                and now - (started or _started) >= timedelta(minutes=CATCH_UP_MIN):
            return "missed"
    return None


def jobs():
    """[(name, enabled, time)] for the screens / tests."""
    cfg = _cfg()
    return [("owner_report", bool(cfg.flag("owner_report_enabled", False)),
             hhmm(cfg.get("owner_report_time", "23:00"), "23:00")),
            ("cloud_backup", bool(cfg.flag("cloud_backup_enabled", False)),
             hhmm(cfg.get("cloud_backup_time", "23:30"), "23:30"))]


def tick(now=None, notify=None, started=None):
    """Run what is due → [(job, ok, message)]. notify(job, ok, message) is
    called for each (the main window shows a toast)."""
    now = now or datetime.now()
    out = []
    for name, on, at in jobs():
        if not on:
            continue
        try:
            if name == "owner_report":
                from modules import whatsapp as wa
                why = due(name, at, now, catch_up=(wa.mode() == "api"), started=started,
                          first_too=False)            # never "yesterday" on the first day
                if not why:
                    continue
                _mark(name, now, why=why)              # first: never twice, even when it fails
                from modules import owner_report as OR
                day = (now - timedelta(days=1)).date().isoformat() if why == "missed" else now.date().isoformat()
                ok, msg = OR.send(day)
            else:
                why = due(name, at, now, catch_up=True, started=started)
                if not why:
                    continue
                _mark(name, now, why=why)
                from modules import cloud_backup as CB
                box = {}
                ok, msg = CB.run(background=bool(notify),
                                 on_done=(lambda o, m: box.update(res=(o, m))) if notify else None)
                if notify and ok:                     # the copy finishes in a thread
                    _watch(box, name, notify)
                    out.append((name, ok, msg))
                    continue
            out.append((name, ok, msg))
            if notify:
                notify(name, ok, msg)
        except Exception as e:
            out.append((name, False, str(e)[:200]))
            if notify:
                try:
                    notify(name, False, str(e)[:200])
                except Exception:
                    pass
    return out


_pending = []


def _watch(box, name, notify):
    _pending.append((box, name, notify))


def poll_pending():
    """Called from the Tk main loop: deliver results of finished copies."""
    for item in list(_pending):
        box, name, notify = item
        if "res" in box:
            _pending.remove(item)
            try:
                notify(name, *box["res"])
            except Exception:
                pass
    return len(_pending)


def start(root):
    """Check every minute on the Tk main loop (MainWindow)."""
    def notify(name, ok, msg):
        try:
            from ui.ui_polish import toast
            icon = "📲" if name == "owner_report" else "☁"
            toast(root, "%s %s" % (icon, msg), "success" if ok else "danger", 6000)
        except Exception:
            pass
        print("[DayBill] %s: %s %s" % (name, "OK" if ok else "FAILED", msg))

    def loop():
        try:
            tick(notify=notify)
        except Exception as e:
            print("[DayBill] daily jobs:", e)
        try:
            root.after(60 * 1000, loop)
        except Exception:
            pass

    def fast():
        try:
            if poll_pending():
                root.after(1000, fast)
                return
        except Exception:
            pass
        try:
            root.after(5000, fast)
        except Exception:
            pass
    try:
        root.after(45 * 1000, loop)
        root.after(5000, fast)
    except Exception:
        pass
