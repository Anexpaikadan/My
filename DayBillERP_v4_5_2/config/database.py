# ============================================================
# DayBill ERP - Database Connection Manager  (rewritten)
# MS SQL Server via pyodbc
#
# Fixes the connection problems for good:
#  - Defaults server to localhost\SQLEXPRESS (never blank)
#  - Auto-detects ODBC Driver 19 -> 18 -> 17
#  - Always adds TrustServerCertificate (Driver 18/19 need it)
#  - Never saves an empty server name back to the config
#  - Plain-language error messages
# ============================================================

import os
import json
import logging
from contextlib import contextmanager

import pyodbc

logger = logging.getLogger(__name__)

try:        # exe: next to DayBillERP.exe (not the temp unpack folder)
    from config.paths import config_file as _cfg_file
    CONFIG_FILE = _cfg_file("db_config.json")
except Exception:
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), "db_config.json")

# What we fall back to if the config file is missing or a field is blank
DEFAULTS = {
    "server":     "localhost\\SQLEXPRESS",
    "database":   "DayBillERP",
    "username":   "",
    "password":   "",
    "auth_type":  "windows",          # "windows" or "sql"
    "driver":     "ODBC Driver 19 for SQL Server",
    "trust_cert": "yes",
    "timeout":    30,
}


# ─────────────────────────────────────────────────────────────
# Driver detection
# ─────────────────────────────────────────────────────────────
def detect_odbc_driver(preferred: str = None) -> str:
    """Pick the best installed SQL Server ODBC driver (19 > 18 > 17)."""
    try:
        installed = [d for d in pyodbc.drivers() if "SQL Server" in d]
    except Exception:
        installed = []
    if not installed:
        return preferred or "ODBC Driver 19 for SQL Server"
    if preferred and preferred in installed:
        return preferred
    for name in ("ODBC Driver 19 for SQL Server",
                 "ODBC Driver 18 for SQL Server",
                 "ODBC Driver 17 for SQL Server"):
        if name in installed:
            return name
    # last resort: anything with "SQL Server" (e.g. the legacy driver)
    return installed[0]


# ─────────────────────────────────────────────────────────────
# Config load / save
# ─────────────────────────────────────────────────────────────
def load_db_config() -> dict:
    """Load config, filling any missing/blank field from DEFAULTS."""
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                # ignore blank strings so a blank server can't override default
                if v not in ("", None):
                    cfg[k] = v
            # v5.27: the SQL password is kept locked to this computer
            try:
                from config import secret_box as _sb
                if _sb.is_protected(cfg.get("password")):
                    cfg["password"] = _sb.reveal(cfg["password"])
                elif cfg.get("password") and _sb.available():
                    save_db_config(cfg)            # older file → lock it now
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Could not read db_config.json: {e}")
    # Safety: never allow a blank server
    if not str(cfg.get("server", "")).strip():
        cfg["server"] = DEFAULTS["server"]
    return cfg


def save_db_config(config: dict):
    """Save config, but never persist a blank server name."""
    to_save = dict(DEFAULTS)
    to_save.update(config or {})
    if not str(to_save.get("server", "")).strip():
        to_save["server"] = DEFAULTS["server"]
    try:                                        # never in plain text (v5.27)
        from config import secret_box as _sb
        if to_save.get("password"):
            to_save["password"] = _sb.protect(str(to_save["password"]))
    except Exception:
        pass
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4)


# ─────────────────────────────────────────────────────────────
# Connection string
# ─────────────────────────────────────────────────────────────
# v6.0.1: 1 when a database is DayBill's (its users table, sales and
# company tables are there), 0 for another program's or an empty one.
DAYBILL_CHECK_SQL = ("SELECT CASE WHEN COL_LENGTH('users','user_id') IS NOT NULL "
                     "AND COL_LENGTH('users','password_hash') IS NOT NULL "
                     "AND OBJECT_ID('sales_invoices') IS NOT NULL "
                     "AND OBJECT_ID('company') IS NOT NULL THEN 1 ELSE 0 END")


def build_connection_string(config: dict = None) -> str:
    if config is None:
        config = load_db_config()

    driver   = detect_odbc_driver(config.get("driver"))
    server   = str(config.get("server") or DEFAULTS["server"]).strip()
    database = str(config.get("database") or DEFAULTS["database"]).strip()
    timeout  = config.get("timeout", 30)
    trust    = config.get("trust_cert", "yes")

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        f"TrustServerCertificate={trust}",
        f"Connection Timeout={timeout}",
    ]
    if config.get("auth_type") == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={config.get('username','')}")
        parts.append(f"PWD={config.get('password','')}")
    return ";".join(parts) + ";"


def friendly_error(err: Exception) -> str:
    """Turn a pyodbc error into a plain-language hint."""
    msg = str(err)
    if "4060" in msg or "Cannot open database" in msg:
        return ("Connected to SQL Server, but could not open the database.\n"
                "• Make sure the database exists and your Windows user has access.")
    if "Login failed" in msg or "18456" in msg:
        return ("Login failed. Your Windows user may not be allowed.\n"
                "• In SSMS, add your user as a login with access to the database.")
    if "server was not found" in msg or "(2)" in msg or "08001" in msg:
        return ("SQL Server not found at this server name.\n"
                "• Try server:  localhost\\SQLEXPRESS\n"
                "• Make sure the SQL Server (SQLEXPRESS) service is running.")
    if "certificate" in msg.lower() or "SSL" in msg:
        return ("Encryption/certificate blocked the connection.\n"
                "• This build already trusts the certificate; update the app code.")
    if "Data source name not found" in msg or "IM002" in msg:
        return ("ODBC driver not found.\n"
                "• Install 'ODBC Driver 19 for SQL Server' from Microsoft.")
    return msg


# ─────────────────────────────────────────────────────────────
# Manager (singleton) — same interface the whole app uses
# ─────────────────────────────────────────────────────────────
def atomic(fn):
    """Decorator: run the whole function as ONE transaction (savepoint when
    called inside another one). v5.27"""
    import functools

    @functools.wraps(fn)
    def run(*a, **k):
        with db.transaction():
            return fn(*a, **k)
    return run


def is_duplicate_error(err) -> bool:
    """A unique key said no (two tills took the same number at once)."""
    m = str(err)
    return ("2627" in m or "2601" in m or "UNIQUE" in m.upper()
            or "duplicate key" in m.lower())


class TransactionLost(RuntimeError):
    """SQL Server rolled the whole transaction back (deadlock, lost
    connection, serious error). Nothing of the save was kept."""


class _Tx:
    """One all-or-nothing unit of work (see DatabaseManager.begin)."""

    def __init__(self, mgr, savepoint=None):
        self.mgr, self.sp, self.done, self.failed = mgr, savepoint, False, False

    @property
    def kept(self):
        """False until the save really reached the database."""
        return self.done and not self.failed

    def commit(self):
        if self.done:
            return
        self.done = True
        try:
            self.mgr._tx_end(self, ok=True)
        except BaseException:
            self.failed = True                 # rolled back — nothing was kept
            raise

    def rollback(self):
        if self.done:
            return
        self.done = self.failed = True
        self.mgr._tx_end(self, ok=False)

    # usable as a context manager too
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            self.commit()
        else:
            self.rollback()
        return False


class DatabaseManager:
    _instance = None
    _connection = None
    _tx_stack = None          # open transactions (outer first)
    _tx_doomed = False        # the server already rolled the outer one back
    _sp_seq = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self, config: dict = None) -> bool:
        try:
            conn_str = build_connection_string(config)
            self._connection = pyodbc.connect(conn_str, autocommit=False)
            try:
                # Decode tolerantly: SQL Server may return Windows-1252 bytes
                # (e.g. 0x96). errors='replace' avoids hard crashes.
                self._connection.setdecoding(pyodbc.SQL_CHAR,  encoding="utf-8", errors="replace")
                self._connection.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8", errors="replace")
                self._connection.setencoding(encoding="utf-8")
            except Exception:
                pass
            logger.info("Database connected.")
            return True
        except pyodbc.Error as e:
            logger.error(f"Database connection failed: {e}")
            self._connection = None
            return False

    def disconnect(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def is_connected(self) -> bool:
        if self._connection is None:
            return False
        try:
            self._connection.cursor().execute("SELECT 1")
            return True
        except Exception:
            return False

    def test_connection(self, config: dict):
        """Return (success, message). Message is plain-language on failure."""
        try:
            conn_str = build_connection_string(config)
            c = pyodbc.connect(conn_str, timeout=5)
            c.close()
            drv = detect_odbc_driver(config.get("driver"))
            return True, f"Connection successful!  (using {drv})"
        except pyodbc.Error as e:
            return False, friendly_error(e)

    # ── transactions (v5.27) ──────────────────────────────────
    # Every statement used to commit on its own, so a failure half-way
    # through a save left half a document (stock moved, no journal …).
    # Now a save runs inside ONE transaction: all of it is kept, or none.
    #
    #   with db.transaction():          # or: tx = db.begin() … tx.commit()
    #       db.execute(…); db.execute(…)
    #
    # A transaction opened inside another one is a SAVEPOINT: if the inner
    # part fails, only the inner part is undone and the outer one goes on.
    def in_transaction(self) -> bool:
        return bool(self._tx_stack)

    def begin(self):
        if self._tx_stack is None:
            self._tx_stack = []
        if self._tx_stack:                              # nested → savepoint
            if self._tx_doomed:
                raise TransactionLost("The database cancelled this save — nothing was kept. "
                                      "Please try again.")
            DatabaseManager._sp_seq += 1
            name = "dbsp%d" % DatabaseManager._sp_seq
            self._raw(f"SAVE TRANSACTION {name}")
            tx = _Tx(self, name)
        else:
            if not self.is_connected():
                self.connect()
            if self._connection is None:
                raise RuntimeError("No database connection.")
            try:                                        # nothing may be pending
                self._connection.commit()
            except Exception:
                pass
            # An explicit BEGIN TRANSACTION (driver in autocommit while it is
            # open) so SAVE TRANSACTION / @@TRANCOUNT behave exactly as T-SQL
            # documents, whatever the ODBC driver does with implicit ones.
            try:
                self._connection.autocommit = True
            except Exception:
                pass
            try:
                self._raw("BEGIN TRANSACTION")
            except Exception:
                try:
                    self._connection.autocommit = False
                except Exception:
                    pass
                raise
            self._tx_doomed = False
            tx = _Tx(self, None)
        self._tx_stack.append(tx)
        return tx

    @contextmanager
    def transaction(self):
        tx = self.begin()
        try:
            yield tx
        except BaseException:
            tx.rollback()
            raise
        else:
            tx.commit()

    savepoint = transaction                              # same thing, nested

    def _raw(self, sql):
        cur = self._connection.cursor()
        try:
            cur.execute(sql)
        finally:
            cur.close()

    def _tx_end(self, tx, ok):
        stack = self._tx_stack or []
        if tx not in stack:
            return
        # anything opened inside and never closed goes with it
        while stack and stack[-1] is not tx:
            inner = stack.pop()
            inner.done = True
        stack.pop()
        if tx.sp is None:                               # the outer transaction
            doomed, self._tx_doomed = self._tx_doomed, False
            try:
                if ok and not doomed:
                    try:
                        self._raw("COMMIT TRANSACTION")
                        return
                    except Exception:
                        try:
                            self._raw("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION")
                        except Exception:
                            pass
                        raise
                try:
                    self._raw("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION")
                except Exception:
                    pass
                if ok and doomed:
                    raise TransactionLost("The database cancelled this save — nothing was "
                                          "kept. Please try again.")
                return
            finally:
                try:
                    self._connection.autocommit = False
                except Exception:
                    pass
        if ok or self._tx_doomed:
            return                                      # savepoint stays part of the outer
        try:
            self._raw(f"ROLLBACK TRANSACTION {tx.sp}")
        except Exception:
            self._check_doomed()

    def _check_doomed(self):
        """After an error inside a transaction: did the server roll the
        whole thing back? (deadlock victim, lost connection, …)"""
        try:
            cur = self._connection.cursor()
            try:
                cur.execute("SELECT @@TRANCOUNT")
                n = cur.fetchone()[0]
            finally:
                cur.close()
            if not n:
                self._tx_doomed = True
        except Exception:
            self._tx_doomed = True

    def is_daybill(self):
        """v6.0.1: does the connected database hold DayBill's own tables?
        True / False — None when it can't be told (then carry on as before).
        False = another program's database (e.g. its backup was restored
        under DayBill's name) or an empty one: DayBill must not sign in to
        it or run its updates on it."""
        try:
            v = self.execute_scalar(DAYBILL_CHECK_SQL)
        except Exception:
            return None
        if v is None:
            return None
        try:
            return bool(int(v))
        except (TypeError, ValueError):
            return None

    def last_identity(self, table=None, key=None):
        """Id of the row this connection just inserted (not another till's).
        Falls back to the highest id when the server can't say."""
        try:
            v = self.execute_scalar("SELECT CAST(@@IDENTITY AS BIGINT)")
            if v is not None:
                return int(v)
        except Exception:
            pass
        if table and key:
            return self.execute_scalar(f"SELECT TOP 1 {key} FROM {table} ORDER BY {key} DESC")
        return None

    @contextmanager
    def get_cursor(self):
        in_tx = bool(self._tx_stack)
        if in_tx:
            if self._tx_doomed:
                raise TransactionLost("The database cancelled this save — nothing was kept. "
                                      "Please try again.")
            if self._connection is None:
                raise TransactionLost("The database connection was lost — nothing was kept.")
        elif not self.is_connected():
            self.connect()
        if self._connection is None:
            raise RuntimeError("No database connection.")
        cursor = self._connection.cursor()
        try:
            yield cursor
            if not in_tx:
                self._connection.commit()
        except Exception as e:
            if in_tx:
                self._check_doomed()
            else:
                try:
                    self._connection.rollback()
                except Exception:
                    pass
            logger.error(f"DB Error: {e}")
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    # ── Query helpers ─────────────────────────────────────────
    def fetchall(self, sql: str, params: tuple = ()) -> list:
        with self.get_cursor() as cur:
            cur.execute(sql, params)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def fetchone(self, sql: str, params: tuple = ()):
        with self.get_cursor() as cur:
            cur.execute(sql, params)
            cols = [c[0] for c in cur.description]
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self.get_cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def execute_scalar(self, sql: str, params: tuple = ()):
        with self.get_cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None

    def execute_sp(self, sp_name: str, params: dict = {}) -> list:
        with self.get_cursor() as cur:
            param_str = ", ".join([f"@{k}=?" for k in params])
            cur.execute(f"EXEC {sp_name} {param_str}", list(params.values()))
            results = []
            while True:
                if cur.description:
                    cols = [c[0] for c in cur.description]
                    results.append([dict(zip(cols, r)) for r in cur.fetchall()])
                if not cur.nextset():
                    break
            return results

    def get_next_invoice_number(self, invoice_type: str, plain: bool = True) -> str:
        """
        Get the next invoice number.
        plain=True  -> returns a plain number like '1001' (Polosys style)
        plain=False -> returns a prefixed number like 'SALES-0001'
        Scans existing numbers (both plain and prefixed) to find the highest,
        then verifies the candidate is free, bumping until unused.
        """
        prefix = (invoice_type or "SALES").upper()
        table = "sales_invoices"
        if prefix.startswith("PUR"):
            table = "purchase_invoices"

        # Settings > Sales / Purchase: starting number + optional prefix
        try:
            from config import settings as _cfg
            is_pur = table == "purchase_invoices"
            START = int(float(_cfg.get("purchase_start_no" if is_pur else "sales_start_no",
                                       1 if is_pur else 1001) or 0)) or 1001
            user_prefix = "" if is_pur else str(_cfg.get("sales_prefix", "") or "").strip()
        except Exception:
            START, user_prefix = 1001, ""

        def highest_existing():
            """Highest numeric value found in any invoice_number (plain or suffixed)."""
            try:
                with self.get_cursor() as cur:
                    cur.execute(f"SELECT invoice_number FROM {table}")
                    mx = 0
                    for (inv,) in cur.fetchall():
                        if not inv:
                            continue
                        # take the trailing run of digits (after last dash if any)
                        tail = str(inv).rsplit("-", 1)[-1]
                        digits = "".join(ch for ch in tail if ch.isdigit())
                        if digits:
                            try:
                                mx = max(mx, int(digits))
                            except ValueError:
                                pass
                    return mx
            except Exception:
                return 0

        def fmt(n):
            if user_prefix:
                return f"{user_prefix}{n}"
            return str(n) if plain else f"{prefix}-{n:04d}"

        def exists(num):
            try:
                with self.get_cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE invoice_number=?", (num,))
                    return cur.fetchone()[0] > 0
            except Exception:
                return False

        n = highest_existing()
        n = (n + 1) if n >= START else START   # never below the starting no.
        # verify free; bump until unused
        for _ in range(100000):
            candidate = fmt(n)
            if not exists(candidate):
                return candidate
            n += 1
        return fmt(n)


db = DatabaseManager()
