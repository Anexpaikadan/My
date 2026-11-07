# ============================================================
# DayBill ERP - where things live (source run AND DayBillERP.exe)
# ------------------------------------------------------------
# Running from source:   everything is in the project folder.
# Running DayBillERP.exe (PyInstaller one-file): the program unpacks
# to a TEMP folder that is deleted when it closes — so settings saved
# there were LOST every time ("asks the database again", "licence
# gone"). Now:
#   RES_DIR   read-only files shipped inside the exe (locales, assets,
#             database patches, installer .sql)
#   DATA_DIR  YOUR files that must survive a restart:
#               config\app_settings.json, config\db_config.json,
#               config\license.json, logs\
#             = the folder of DayBillERP.exe when it can be written,
#               else  %LOCALAPPDATA%\DayBillERP
# ============================================================

import os
import sys

FROZEN = bool(getattr(sys, "frozen", False))

# project root (source) / unpack folder (exe)
RES_DIR = (getattr(sys, "_MEIPASS", None) if FROZEN else None) or \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable(folder):
    try:
        os.makedirs(folder, exist_ok=True)
        test = os.path.join(folder, ".daybill_write_test")
        with open(test, "w") as f:
            f.write("ok")
        os.remove(test)
        return True
    except Exception:
        return False


def _data_dir():
    if not FROZEN:
        return RES_DIR
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    if _writable(os.path.join(exe_dir, "config")):
        return exe_dir
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "DayBillERP")


DATA_DIR = _data_dir()
CONFIG_DIR = os.path.join(DATA_DIR, "config")
LOG_DIR = os.path.join(DATA_DIR, "logs")


def res(*parts):
    """A shipped (read-only) file, e.g. res('assets', 'app.ico')."""
    return os.path.join(RES_DIR, *parts)


def config_file(name):
    """A settings file that must survive a restart."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception:
        pass
    return os.path.join(CONFIG_DIR, name)


def log_file(name):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        pass
    return os.path.join(LOG_DIR, name)
