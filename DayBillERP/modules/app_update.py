# ============================================================
# DayBill ERP - update the program itself (v6.0)
# ------------------------------------------------------------
# Updates ▸ "Install a new version":
#   1. pick the DayBill update file — the release .zip (or a new
#      DayBillERP.exe when you run the built program)
#   2. DayBill checks it: a real DayBill, a NEWER version, nothing missing
#   3. it is unpacked next to the program (update_staging), then DayBill
#      closes; a small helper waits until it is closed, keeps a backup of
#      the old files (update_backup_<old version>), copies the new files,
#      and starts DayBill again. Your settings, database settings and
#      product key are never touched.
#   4. at the next start the database update runs by itself.
# v7.9.1: the helper starts DayBill with a CLEAN environment. A one-file
# DayBillERP.exe unpacks Python to a temporary _MEI… folder and tells its
# own child process where it is through environment variables; when the
# helper inherited them, the new DayBillERP.exe looked for python3xx.dll
# in the old _MEI… folder (already deleted) → "Failed to load Python DLL".
# Online: when Settings ▸ System ▸ "Update address" points at a
# latest.json ({"version", "url", "sha256"}), "Check online" downloads the
# zip and checks its SHA-256 before using it.
# ============================================================
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

KEEP = ("config/app_settings.json", "config/db_config.json", "config/license.json",
        "config/daybill_vault_recovery.dat", "config/table_layouts.json",
        "db_config.json", "license.json")


def app_dir():
    """Folder of the program (next to DayBillERP.exe when built)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def current_version():
    try:
        from config.version import VERSION
        return VERSION
    except Exception:
        return "0"


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:4]) or (0,)


def newer(a, b):
    """Is version a newer than b?"""
    return vtuple(a) > vtuple(b)


def _zip_root(names):
    """The folder inside the zip that holds main.py ('' or 'DayBillERP_v4_5_2/')."""
    for n in names:
        if n.endswith("main.py") and n.count("/") <= 1:
            return n[:-len("main.py")]
    return None


def inspect(path):
    """→ {"kind": "zip"|"exe", "version", "ok", "problems": [], "root"}"""
    out = {"kind": "", "version": "", "ok": False, "problems": [], "root": ""}
    if not path or not os.path.exists(path):
        out["problems"].append("The file was not found.")
        return out
    low = path.lower()
    if low.endswith(".exe"):
        out["kind"] = "exe"
        m = re.search(r"(\d+[._]\d+[._]\d+)", os.path.basename(path))
        out["version"] = m.group(1).replace("_", ".") if m else ""
        if not getattr(sys, "frozen", False):
            out["problems"].append("This PC runs DayBill from the source files — use the update .zip.")
        out["ok"] = not out["problems"]
        return out
    if not zipfile.is_zipfile(path):
        out["problems"].append("This is not a DayBill update (.zip or DayBillERP.exe).")
        return out
    out["kind"] = "zip"
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        root = _zip_root(names)
        if root is None:
            out["problems"].append("No main.py inside — this zip is not a DayBill program.")
            return out
        out["root"] = root
        try:
            txt = z.read(root + "config/version.py").decode("utf-8", "replace")
            m = re.search(r'VERSION\s*=\s*"([^"]+)"', txt)
            out["version"] = m.group(1) if m else ""
        except KeyError:
            out["problems"].append("config/version.py is missing in the zip.")
        for must in ("modules/", "ui/", "database/"):
            if not any(n.startswith(root + must) for n in names):
                out["problems"].append("The folder %s is missing in the zip." % must.strip("/"))
        bad = [n for n in names if n.startswith("/") or ".." in n.split("/")]
        if bad:
            out["problems"].append("Unsafe file names in the zip.")
    if out["version"] and not newer(out["version"], current_version()):
        out["problems"].append("This is version %s — you already have %s."
                               % (out["version"], current_version()))
    out["ok"] = not out["problems"]
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage(path, info=None):
    """Unpack the update next to the program → staging folder."""
    info = info or inspect(path)
    if not info["ok"]:
        raise ValueError("; ".join(info["problems"]))
    dst = os.path.join(app_dir(), "update_staging")
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst, exist_ok=True)
    if info["kind"] == "exe":
        shutil.copy2(path, os.path.join(dst, "DayBillERP.exe"))
        return dst
    root = info["root"]
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not n.startswith(root) or n.endswith("/"):
                continue
            rel = n[len(root):]
            if not rel or rel.replace("\\", "/") in KEEP or "/__pycache__/" in "/" + rel:
                continue
            target = os.path.normpath(os.path.join(dst, rel))
            if not target.startswith(os.path.normpath(dst)):
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(n) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    return dst


# PyInstaller's own variables (5.x: _MEIPASS2; 6.x: _PYI_…) — never pass
# them on to a new DayBill
_PYI_VARS = ("_MEIPASS2", "_PYI_APPLICATION_HOME_DIR", "_PYI_ARCHIVE_FILE",
             "_PYI_PARENT_PROCESS_LEVEL", "_PYI_SPLASH_IPC", "_PYI_LINUX_PROCESS_NAME")


def _mei_dir():
    """The temporary _MEI… folder of a one-file exe ('' otherwise)."""
    d = getattr(sys, "_MEIPASS", "") if getattr(sys, "frozen", False) else ""
    return d if d and os.path.basename(os.path.normpath(d)).upper().startswith("_MEI") else ""


def clean_env(env=None):
    """A copy of the environment without anything that points DayBill at
    this run's temporary _MEI… folder."""
    env = dict(os.environ if env is None else env)
    mei = _mei_dir()
    for k in list(env):
        if k.upper() in _PYI_VARS or k.upper().startswith("_PYI_"):
            env.pop(k, None)
        elif mei and k.upper() != "PATH" and os.path.normcase(mei) in os.path.normcase(str(env[k])):
            env.pop(k, None)               # TCL_LIBRARY, TK_LIBRARY, SSL_CERT_FILE …
    if mei and env.get("PATH"):
        env["PATH"] = os.pathsep.join(p for p in env["PATH"].split(os.pathsep)
                                      if os.path.normcase(mei) not in os.path.normcase(p))
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"   # PyInstaller 6.9+: start as a new program
    return env


def write_helper(staging, restart=True):
    """The small Windows helper that swaps the files after DayBill closes.
    → path of update_daybill.bat"""
    ad = app_dir()
    backup = os.path.join(ad, "update_backup_%s" % current_version().replace(".", "_"))
    exe = os.path.join(ad, "DayBillERP.exe")
    pid = os.getpid()
    # a one-file exe runs as two processes: the small launcher (parent) and
    # Python (this one). Wait for both — the launcher holds DayBillERP.exe
    # open and removes the _MEI… folder when it ends.
    pids = [pid]
    if _mei_dir():
        try:
            if os.getppid() and os.getppid() != pid:
                pids.append(os.getppid())
        except Exception:
            pass
    start = ('start "" "%s"' % exe) if getattr(sys, "frozen", False) else \
        ('start "" "%s" "%s"' % (sys.executable.replace("python.exe", "pythonw.exe"),
                                 os.path.join(ad, "main.py")))
    excl = " ".join('"%s"' % os.path.basename(k) for k in KEEP)
    lines = [
        "@echo off",
        "title DayBill ERP - installing the update",
        "echo Waiting for DayBill ERP to close...",
    ] + [x for p_ in pids for x in (
        ":wait%d" % p_,
        'tasklist /fi "PID eq %d" | find "%d" >nul && (timeout /t 1 /nobreak >nul & goto wait%d)' % (p_, p_, p_),
    )] + [
        "echo Keeping a copy of the old version in %s" % backup,
        'robocopy "%s" "%s" /E /XD update_staging update_backup_* logs backups __pycache__ /NFL /NDL /NJH /NJS >nul'
        % (ad, backup),
        "echo Copying the new version...",
        'robocopy "%s" "%s" /E /R:20 /W:2 /XF %s /NFL /NDL /NJH /NJS' % (staging, ad, excl),
        "if errorlevel 8 goto failed",
        'rmdir /s /q "%s"' % staging,
        "echo Done.",
        # start the new version as a NEW program (not part of the old run)
        "set PYINSTALLER_RESET_ENVIRONMENT=1",
    ] + ["set %s=" % v for v in _PYI_VARS] + (
        ["set TCL_LIBRARY=", "set TK_LIBRARY="] if _mei_dir() else []) + [
        start if restart else "",
        "exit /b 0",
        ":failed",
        "echo The update could not be copied. The old version is in %s" % backup,
        "pause",
    ]
    p = os.path.join(ad, "update_daybill.bat")
    with open(p, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(l for l in lines if l is not None) + "\n")
    return p


def launch_helper(bat):
    """Start the helper (Windows) — the caller then closes DayBill."""
    import subprocess
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10)
    subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True, env=clean_env(),
                     cwd=app_dir())


# ── online check ─────────────────────────────────────────────
def check_online(url=None, timeout=15):
    """→ {"version", "url", "sha256", "newer"} or raises."""
    if not url:
        from config import settings as cfg
        url = str(cfg.get("update_url", "") or "").strip()
    if not url:
        raise ValueError("No update address set (Settings ▸ System ▸ Update address).")
    import requests
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    d["newer"] = newer(d.get("version"), current_version())
    return d


def download(info, timeout=120):
    import requests
    dst = os.path.join(app_dir(), "update_download.zip")
    with requests.get(info["url"], stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    want = str(info.get("sha256") or "").lower()
    if want and sha256(dst) != want:
        os.remove(dst)
        raise ValueError("The downloaded file is damaged (SHA-256 does not match) — nothing was changed.")
    return dst
