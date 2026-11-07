# ============================================================
# DayBill ERP - ☁ automatic cloud backup  (v6.4)
# ------------------------------------------------------------
# Every night (Settings ▸ Backup ▸ Cloud backup at …) DayBill makes a
# database backup and puts a ZIPPED copy in a folder that Google Drive,
# OneDrive or Dropbox uploads by itself — so a broken or stolen PC never
# means lost data. Nothing is sent by DayBill itself; the cloud app on
# this PC does the upload (install it and sign in once).
#   folders()        cloud folders found on this PC
#   target()         <cloud folder>\DayBill Backups
#   run()            backup → zip → keep the newest N → status
#   status() / alert_text()   last good copy (alert after 2 days)
# ============================================================

import glob
import json
import os
import sys
import threading
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SUB = "DayBill Backups"


def _cfg():
    from config import settings as cfg
    return cfg


def enabled():
    try:
        return bool(_cfg().flag("cloud_backup_enabled", False))
    except Exception:
        return False


def keep():
    try:
        return max(1, int(float(_cfg().get("cloud_backup_keep", 14) or 14)))
    except Exception:
        return 14


def folders():
    """[(name, path)] of cloud folders that exist on this PC."""
    env = os.environ
    home = os.path.expanduser("~")
    cands = []
    for k in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive"):
        if env.get(k):
            cands.append(("OneDrive", env[k]))
    cands.append(("OneDrive", os.path.join(home, "OneDrive")))
    for d in ("G", "H", "I"):                          # Google Drive for desktop
        cands.append(("Google Drive", "%s:\\My Drive" % d))
    cands += [("Google Drive", os.path.join(home, "Google Drive")),
              ("Google Drive", os.path.join(home, "My Drive")),
              ("Dropbox", os.path.join(home, "Dropbox"))]
    seen, out = set(), []
    for name, p in cands:
        try:
            ap = os.path.abspath(p)
        except Exception:
            continue
        if ap.lower() in seen or not os.path.isdir(ap):
            continue
        seen.add(ap.lower())
        out.append((name, ap))
    return out


def target():
    """The folder the zips go to (None when no cloud folder is set / found)."""
    p = str(_cfg().get("cloud_backup_folder", "") or "").strip()
    if not p:
        f = folders()
        p = f[0][1] if f else ""
    if not p:
        return None
    if os.path.basename(os.path.normpath(p)).lower() != SUB.lower():
        p = os.path.join(p, SUB)
    return p


def _status_file():
    try:
        from config.paths import config_file
        return config_file("cloud_backup_status.json")
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "cloud_backup_status.json")


def status():
    try:
        with open(_status_file(), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_status(**kw):
    s = status()
    s.update(kw)
    try:
        with open(_status_file(), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)
    except Exception:
        pass
    return s


def age_days():
    s = status().get("last_ok")
    if not s:
        return None
    try:
        return (datetime.now() - datetime.strptime(s[:16], "%Y-%m-%d %H:%M")).total_seconds() / 86400.0
    except Exception:
        return None


def alert_text():
    """One line for the dashboard / evening report ('' when fine or off)."""
    if not enabled():
        return ""
    a = age_days()
    if a is None:
        return "☁ No cloud backup yet — Settings ▸ Backup ▸ cloud backup"
    if a > 2:
        return "☁ Last cloud backup %d days ago — check the cloud folder / Google Drive / OneDrive" % int(a)
    return ""


def _zip(bak, dest_dir, base_name):
    os.makedirs(dest_dir, exist_ok=True)
    tmp = os.path.join(dest_dir, base_name + ".zip.part")
    final = os.path.join(dest_dir, base_name + ".zip")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(bak, os.path.basename(bak))
        z.writestr("README.txt", "DayBill ERP backup made %s.\r\nTo restore: unzip, then DayBill login "
                                 "▸ Database Settings ▸ ♻ Restore Database (.bak).\r\n"
                   % datetime.now().strftime("%Y-%m-%d %H:%M"))
    os.replace(tmp, final)
    return final


def _prune(dest_dir, prefix):
    zips = sorted(glob.glob(os.path.join(dest_dir, prefix + "_*.zip")), reverse=True)
    gone = 0
    for old in zips[keep():]:
        try:
            os.remove(old)
            gone += 1
        except Exception:
            pass
    return gone


def run(background=False, on_done=None):
    """Backup now and copy it to the cloud folder. → (ok, message).
    background=True: the zip / copy runs in a thread (the database part
    always runs here); on_done(ok, message) is called from that thread."""
    dest = target()
    if not dest:
        msg = ("No cloud folder found. Install Google Drive / OneDrive / Dropbox and sign in, "
               "or choose the folder in Settings ▸ Backup.")
        _save_status(last_error=msg, last_try=datetime.now().strftime("%Y-%m-%d %H:%M"))
        return False, msg
    from modules import db_backup
    ok, bak = db_backup.backup_now(note="cloud")
    if not ok:
        _save_status(last_error="Backup failed: " + str(bak), last_try=datetime.now().strftime("%Y-%m-%d %H:%M"))
        return False, "Backup failed: " + str(bak)
    if not os.path.exists(bak):
        msg = ("The backup was made on the SQL Server computer (%s) — this PC cannot reach it. Run the "
               "cloud backup on that computer, or set Settings ▸ Backup ▸ Backup Folder to a shared "
               "folder." % bak)
        _save_status(last_error=msg, last_try=datetime.now().strftime("%Y-%m-%d %H:%M"))
        return False, msg
    try:
        from config.database import load_db_config
        prefix = (load_db_config() or {}).get("database") or "DayBillERP"
    except Exception:
        prefix = "DayBillERP"
    name = "%s_%s" % (prefix, datetime.now().strftime("%Y-%m-%d_%H%M%S"))

    def work():
        try:
            z = _zip(bak, dest, name)
            _prune(dest, prefix)
            size = os.path.getsize(z)
            _save_status(last_ok=datetime.now().strftime("%Y-%m-%d %H:%M"), last_file=z,
                              last_size=size, last_error="")
            res = (True, "Cloud backup ✔ %s (%.1f MB)" % (os.path.basename(z), size / 1048576.0))
        except Exception as e:
            _save_status(last_error=str(e)[:300], last_try=datetime.now().strftime("%Y-%m-%d %H:%M"))
            res = (False, "Could not copy to the cloud folder: %s" % str(e)[:200])
        if on_done:
            try:
                on_done(*res)
            except Exception:
                pass
        return res
    if background:
        threading.Thread(target=work, daemon=True).start()
        return True, "Backup made — copying to %s …" % dest
    return work()
