# ============================================================
# DayBill ERP - DB migration runner
# ------------------------------------------------------------
# Applies pending SQL patches automatically so you never forget to
# run one in SSMS. Only touches files named *_patch.sql in the
# database/ folder (all idempotent, IF NOT EXISTS-guarded). Tracks
# what's been applied in a _migrations table and skips those.
#
# It deliberately ignores the full schema / setup / optional / reset
# scripts — those are never auto-run against an existing database.
# ============================================================

import sys, os, glob, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_DIR = os.path.join(_ROOT, "database")

# split a SQL Server script into batches on lines that are just "GO"
_GO = re.compile(r"^\s*GO\s*;?\s*$", re.IGNORECASE | re.MULTILINE)


def _ensure_table():
    db.execute(
        "IF OBJECT_ID('_migrations','U') IS NULL "
        "CREATE TABLE _migrations (filename NVARCHAR(200) PRIMARY KEY, "
        "applied_at DATETIME DEFAULT GETDATE())")


def _applied():
    try:
        rows = db.fetchall("SELECT filename FROM _migrations") or []
        return {r["filename"] for r in rows}
    except Exception:
        return set()


def _pending_files():
    files = sorted(glob.glob(os.path.join(_DB_DIR, "*_patch.sql")))
    done = _applied()
    return [f for f in files if os.path.basename(f) not in done]


def _is_already_exists(err):
    """True for harmless 'object/index/column already exists' errors that mean
    the patch was effectively applied before (idempotency)."""
    msg = str(err).lower()
    return any(s in msg for s in (
        "already exists", "there is already an object",
        "already an index", "duplicate", "42s11", "2714", "1913"))


def _run_file(path):
    """Run a patch. Idempotency errors ('already exists') are ignored per
    batch so re-running a patch never surfaces as a failure. Returns the
    count of batches skipped as already-applied."""
    with open(path, "r", encoding="utf-8-sig") as fh:
        sql = fh.read()
    skipped = 0
    for batch in _GO.split(sql):
        stmt = batch.strip()
        if not stmt:
            continue
        # skip a bare "USE <db>" — we're already connected to the right DB
        if re.match(r"^use\s+\w+\s*;?\s*$", stmt, re.IGNORECASE):
            continue
        try:
            db.execute(stmt)
        except Exception as e:
            if _is_already_exists(e):
                skipped += 1
                continue          # harmless — object is already there
            raise                 # genuine error → bubble up
    return skipped


def run_pending(verbose=False):
    """Apply all pending *_patch.sql. Returns (applied_list, errors_list).
    Never raises — a failure is recorded and reported, not fatal."""
    applied, errors = [], []
    if db.is_daybill() is False:       # v6.0.1: never change another program's database
        return applied, [("(not a DayBill database)",
                          "This database has no DayBill tables — DayBill updates were not applied.")]
    try:
        _ensure_table()
    except Exception as e:
        return applied, [("(_migrations table)", str(e))]

    for path in _pending_files():
        name = os.path.basename(path)
        try:
            _run_file(path)
            db.execute("INSERT INTO _migrations (filename) VALUES (?)", (name,))
            applied.append(name)
            if verbose:
                print(f"[migrate] applied {name}")
        except Exception as e:
            errors.append((name, str(e)[:200]))
            if verbose:
                print(f"[migrate] FAILED {name}: {e}")
    return applied, errors


def status():
    """(applied_count, pending_filenames) for a settings/checklist display."""
    return len(_applied()), [os.path.basename(f) for f in _pending_files()]
