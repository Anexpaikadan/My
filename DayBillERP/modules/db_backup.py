# ============================================================
# DayBill ERP — SQL Server backup / restore / database tools
# ------------------------------------------------------------
#   backup_now()          -> .bak into the configured backup path
#   list_databases()      -> user databases on the server
#   restore_database()    -> restore a .bak (company change/new install)
#   safe_restore()        -> the Restore button (v6.0.1): looks inside the
#                            .bak first, never puts another program's
#                            database over an existing one, and saves a
#                            safety copy of the database it replaces
#   check_backup_path()   -> validate/create the backup folder
#
# BACKUP/RESTORE cannot run inside a transaction, so this module
# opens its OWN autocommit connection (to master for restores),
# reusing the app's saved server / auth settings.
# ============================================================

import os, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import build_connection_string, load_db_config, DAYBILL_CHECK_SQL
from config import settings as cfg

DEFAULT_BACKUP_DIR = r"C:\DayBillERP\Backups"


def _connect(database=None):
    """Fresh AUTOCOMMIT connection using the app's saved settings.
    database=None keeps the configured DB; 'master' for server ops."""
    import pyodbc
    conf = dict(load_db_config())
    if database:
        conf["database"] = database
    return pyodbc.connect(build_connection_string(conf), autocommit=True,
                          timeout=15)


def backup_path():
    p = str(cfg.get("backup_path", "") or "").strip() or DEFAULT_BACKUP_DIR
    return p


def check_backup_path(create=True):
    """(ok, message). Creates the folder when the SQL Server is local.
    For a remote server the path must exist on THAT machine."""
    p = backup_path()
    try:
        if create:
            os.makedirs(p, exist_ok=True)
        ok = os.path.isdir(p)
        return ok, (p if ok else
                    "Path not reachable from this PC: %s\n(If SQL Server "
                    "runs on another machine, the folder must exist there.)"
                    % p)
    except Exception as e:
        return False, "%s — %s" % (p, e)


def backup_now(note=""):
    """BACKUP DATABASE to <backup_path>\\DayBillERP_YYYYmmdd_HHMM.bak.
    Returns (ok, path_or_error)."""
    conf = load_db_config()
    dbname = conf.get("database", "DayBillERP")
    folder = backup_path()
    try:
        os.makedirs(folder, exist_ok=True)     # best effort (local server)
    except Exception:
        pass
    fname = "%s_%s%s.bak" % (dbname, datetime.now().strftime("%Y%m%d_%H%M"),
                             ("_" + note) if note else "")
    full = os.path.join(folder, fname)
    try:
        cn = _connect()
        cur = cn.cursor()
        cur.execute(
            "BACKUP DATABASE [%s] TO DISK = ? WITH INIT, "
            "NAME = 'DayBill auto backup'" % dbname, (full,))
        while cur.nextset():
            pass
        cn.close()
        # prune: keep the newest N backups (settings backup_keep, default 30)
        try:
            keep = int(cfg.get("backup_keep", 30) or 30)
            baks = sorted((f for f in os.listdir(folder)
                           if f.lower().endswith(".bak")
                           and f.startswith(dbname + "_")), reverse=True)
            for old in baks[keep:]:
                os.remove(os.path.join(folder, old))
        except Exception:
            pass
        return True, full
    except Exception as e:
        return False, str(e)[:300]


def list_databases():
    """User databases on the configured server (for company selection)."""
    try:
        cn = _connect("master")
        cur = cn.cursor()
        cur.execute("SELECT name FROM sys.databases WHERE database_id > 4 "
                    "AND state = 0 ORDER BY name")
        names = [r[0] for r in cur.fetchall()]
        cn.close()
        return names, ""
    except Exception as e:
        return [], str(e)[:250]


def _layout(cur, bak_path):
    """Logical files inside the backup + the server's default folders."""
    cur.execute("RESTORE FILELISTONLY FROM DISK = ?", (bak_path,))
    files = cur.fetchall()
    cur.execute("SELECT CAST(SERVERPROPERTY('InstanceDefaultDataPath') "
                "AS NVARCHAR(500)), "
                "CAST(SERVERPROPERTY('InstanceDefaultLogPath') "
                "AS NVARCHAR(500))")
    drow = cur.fetchone()
    data_dir = (drow[0] or "").rstrip("\\")
    log_dir = (drow[1] or data_dir or "").rstrip("\\")
    return files, data_dir, log_dir


def _restore_into(cur, bak_path, target_db, files, data_dir, log_dir):
    moves = []
    for f in files:
        logical, ftype = f[0], (f[2] or "D")
        tgt_dir = log_dir if str(ftype).upper().startswith("L") else data_dir
        ext = ".ldf" if str(ftype).upper().startswith("L") else ".mdf"
        moves.append("MOVE N'%s' TO N'%s\\%s_%s%s'"
                     % (logical, tgt_dir, target_db, logical, ext))
    # kick existing users off if the DB already exists
    cur.execute("SELECT COUNT(*) FROM sys.databases WHERE name = ?",
                (target_db,))
    if cur.fetchone()[0]:
        cur.execute("ALTER DATABASE [%s] SET SINGLE_USER WITH "
                    "ROLLBACK IMMEDIATE" % target_db)
    sql = ("RESTORE DATABASE [%s] FROM DISK = ? WITH REPLACE, %s"
           % (target_db, ", ".join(moves)))
    cur.execute(sql, (bak_path,))
    while cur.nextset():
        pass
    try:
        cur.execute("ALTER DATABASE [%s] SET MULTI_USER" % target_db)
    except Exception:
        pass


def list_databases_marked():
    """v6.0.2: [(name, True/False/None)] — True = a DayBill database,
    False = another program's, None = couldn't look. DayBill's first."""
    names, err = list_databases()
    if err:
        return [], err
    out = [(n, is_daybill_db(n)) for n in names if not str(n).startswith("DayBillCheck_")]
    out.sort(key=lambda x: (0 if x[1] else (2 if x[1] is False else 1), str(x[0]).lower()))
    return out, ""


def restore_database(bak_path, target_db):
    """RESTORE a .bak over/into target_db (company restore).
    Moves data files to the server's default paths via WITH MOVE.
    Returns (ok, message). The Restore button uses safe_restore()."""
    if not bak_path or not target_db:
        return False, "Backup file and database name are required."
    try:
        cn = _connect("master")
        cur = cn.cursor()
        files, data_dir, log_dir = _layout(cur, bak_path)
        _restore_into(cur, bak_path, target_db, files, data_dir, log_dir)
        cn.close()
        return True, "Database '%s' restored from:\n%s" % (target_db, bak_path)
    except Exception as e:
        return False, str(e)[:400]


# ── v6.0.1: safe restore ─────────────────────────────────────
def database_exists(name):
    """True / False — None when the server can't be asked."""
    try:
        cn = _connect("master")
        try:
            cur = cn.cursor()
            cur.execute("SELECT COUNT(*) FROM sys.databases WHERE name = ?", (name,))
            return bool(cur.fetchone()[0])
        finally:
            cn.close()
    except Exception:
        return None


def is_daybill_db(database):
    """Does this database hold DayBill's own tables? True / False — None
    when it can't be checked."""
    try:
        cn = _connect(database)
        try:
            cur = cn.cursor()
            cur.execute(DAYBILL_CHECK_SQL)
            return bool(int(cur.fetchone()[0]))
        finally:
            cn.close()
    except Exception:
        return None


def backup_database(dbname, note="before_restore"):
    """BACKUP one named database into the backup folder → (ok, path_or_error)."""
    folder = backup_path()
    try:
        os.makedirs(folder, exist_ok=True)     # best effort (local server)
    except Exception:
        pass
    full = os.path.join(folder, "%s_%s_%s.bak" % (dbname, datetime.now().strftime("%Y%m%d_%H%M%S"), note))
    try:
        cn = _connect("master")
        cur = cn.cursor()
        cur.execute("BACKUP DATABASE [%s] TO DISK = ? WITH INIT, "
                    "NAME = 'DayBill safety copy'" % dbname, (full,))
        while cur.nextset():
            pass
        cn.close()
        return True, full
    except Exception as e:
        return False, str(e)[:300]


def _drop(cur, name):
    cur.execute("SELECT COUNT(*) FROM sys.databases WHERE name = ?", (name,))
    if cur.fetchone()[0]:
        cur.execute("ALTER DATABASE [%s] SET SINGLE_USER WITH ROLLBACK IMMEDIATE" % name)
        cur.execute("DROP DATABASE [%s]" % name)


def check_backup(bak_path):
    """Look INSIDE a .bak: it is restored once into a throw-away database,
    checked, and dropped again. → {"daybill": True/False/None, "error": ""}"""
    out = {"daybill": None, "error": ""}
    tmp = "DayBillCheck_%s" % datetime.now().strftime("%Y%m%d%H%M%S")
    cn = None
    try:
        cn = _connect("master")
        cur = cn.cursor()
        files, data_dir, log_dir = _layout(cur, bak_path)
        _restore_into(cur, bak_path, tmp, files, data_dir, log_dir)
        out["daybill"] = is_daybill_db(tmp)
    except Exception as e:
        out["error"] = str(e)[:300]
    finally:
        try:
            if cn is None:
                cn = _connect("master")
            _drop(cn.cursor(), tmp)
        except Exception:
            pass
        try:
            if cn is not None:
                cn.close()
        except Exception:
            pass
    return out


NOT_DAYBILL = ("This backup is NOT a DayBill database — it belongs to another program "
               "(DayBill can't sign in to it).")


def safe_restore(bak_path, target_db, ask=None, say=None):
    """The ♻ Restore Database button.
      1. look inside the backup first (check_backup);
      2. another program's backup is NEVER put over an existing database —
         only into a NEW name, after ask() says yes (to keep it on the server);
      3. a database that is replaced is first saved as a safety copy
         (<name>_<date>_before_restore.bak in the backup folder); if that
         can't be done, ask() first.
    ask(question) → True/False;  say(text) shows what is happening.
    → (ok, message, kind)   kind: "daybill" | "foreign" | None (couldn't tell)"""
    ask = ask or (lambda q: False)
    say = say or (lambda t: None)
    if not bak_path or not target_db:
        return False, "Backup file and database name are required.", None
    say("Checking the backup…")
    chk = check_backup(bak_path)
    if chk["error"]:
        return False, "The backup could not be read — nothing was changed.\n\n" + chk["error"], None
    kind = {True: "daybill", False: "foreign"}.get(chk["daybill"])
    exists = database_exists(target_db)
    if kind == "foreign":
        if exists is not False:
            return False, (NOT_DAYBILL + "\n\n'%s' was NOT changed.\n\nTo keep that program's data on "
                           "this server, type a NEW name in the Database box (for example OldSoftware) "
                           "and restore again." % target_db), kind
        if not ask(NOT_DAYBILL + "\n\nRestore it as a NEW database '%s', only to keep its data on this "
                   "server? DayBill stays on its own database." % target_db):
            return False, "Nothing was restored.", kind
    elif kind is None and exists is not False:
        if not ask("DayBill could not look inside this backup.\n\nReplace '%s' with it anyway?"
                   % target_db):
            return False, "Nothing was restored.", None
    safety = ""
    if exists:
        say("Saving a safety copy of '%s'…" % target_db)
        okb, where = backup_database(target_db)
        if okb:
            safety = where
        elif not ask("A safety copy of '%s' could not be saved:\n%s\n\nReplace it anyway? Its data "
                     "would be lost." % (target_db, where)):
            return False, "Nothing was restored — '%s' was not changed." % target_db, kind
    say("Restoring… this can take a minute.")
    ok, msg = restore_database(bak_path, target_db)
    if ok and safety:
        msg += "\n\nThe old '%s' was saved first as:\n%s" % (target_db, safety)
    if ok and kind == "foreign":
        msg += "\n\n" + NOT_DAYBILL
    return ok, msg, kind


def run_sql_script(path, database=None, progress=None):
    """Execute a .sql file (splitting on GO batch separators) against
    `database` (or the configured one). Returns (ok, message)."""
    import re
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            script = f.read()
    except Exception as e:
        return False, "Cannot read script: %s" % e
    batches = [b.strip() for b in
               re.split(r"^\s*GO\s*;?\s*$", script,
                        flags=re.IGNORECASE | re.MULTILINE) if b.strip()]
    if database:
        # The installer was written for a database called DayBillERP: it
        # creates it and switches to it (USE). For a new company database
        # those lines would put every table in DayBillERP instead — drop
        # them so everything lands in `database`.
        use_re = re.compile(r"^\s*USE\s+\[?[\w\-]+\]?\s*;?\s*$", re.IGNORECASE | re.MULTILINE)
        cleaned = []
        for b in batches:
            if re.search(r"\bCREATE\s+DATABASE\b", b, re.IGNORECASE):
                continue
            b = use_re.sub("", b).strip()
            if b:
                cleaned.append(b)
        batches = cleaned
    try:
        cn = _connect(database)
        cn.autocommit = True
        cur = cn.cursor()
        done = 0
        for b in batches:
            try:
                cur.execute(b)
            except Exception as e:
                # keep going: patches are idempotent; report at the end
                print("[install] batch skipped:", str(e)[:120])
            done += 1
            if progress:
                try:
                    progress(done, len(batches))
                except Exception:
                    pass
        cn.close()
        return True, "Executed %d batches from %s" % (done,
                                                      os.path.basename(path))
    except Exception as e:
        return False, str(e)[:300]


def create_database(name, install_script=None, progress=None):
    """Create a brand-new database (for a new company). Optionally run
    the all-in-one install script into it. Returns (ok, message)."""
    name = "".join(ch for ch in str(name).strip()
                   if ch.isalnum() or ch in "_-")
    if not name:
        return False, "Give the new database a name (letters/numbers)."
    try:
        cn = _connect("master")
        cn.autocommit = True
        cur = cn.cursor()
        exists = cur.execute(
            "SELECT COUNT(*) FROM sys.databases WHERE name=?",
            (name,)).fetchone()[0]
        if exists:
            cn.close()
            return False, "Database '%s' already exists." % name
        cur.execute("CREATE DATABASE [%s] COLLATE Arabic_CI_AS" % name)
        cn.close()
    except Exception as e:
        return False, str(e)[:300]
    if install_script and os.path.exists(install_script):
        ok, msg = run_sql_script(install_script, database=name,
                                 progress=progress)
        return ok, ("Database '%s' created. " % name) + msg
    return True, ("Database '%s' created (empty). Run "
                  "INSTALL_DayBillERP_AllInOne.sql to add the tables." % name)


def find_install_script():
    """Locate database/INSTALL_DayBillERP_AllInOne.sql (5.24+), or the
    old place next to the app."""
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for p in (os.path.join(base, "database", "INSTALL_DayBillERP_AllInOne.sql"),
              os.path.join(base, "INSTALL_DayBillERP_AllInOne.sql")):
        if os.path.exists(p):
            return os.path.abspath(p)
    return None
