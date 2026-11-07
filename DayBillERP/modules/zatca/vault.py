# ============================================================
# DayBill ERP - ZATCA key protection (v5.27)
# ------------------------------------------------------------
# The ZATCA private key and the two certificate secrets used to sit in
# the zatca_egs table as plain text: anyone with a database login — or a
# copy of a .bak backup — could take them. ZATCA's rules say the signing
# key must not be exportable.
#
# "Protect ZATCA keys" (ZATCA screen, admin) locks them with SQL Server's
# own encryption:
#     database master key  →  certificate DayBillZatcaCert
#                          →  AES-256 key DayBillZatcaKey
# Every DayBill PC connected to THIS SQL Server opens them automatically
# (nothing to copy between tills). A backup restored on ANOTHER server
# can't open them without the recovery code shown when you protect.
#
# Stored as   "sqlv1:" + base64(ciphertext)   in the same columns, so an
# unprotected (older) row keeps working unchanged.
#
# Safe by design: nothing is changed until a test value has gone in and
# come back out correctly on this server; "Unprotect" puts the plain text
# back. Moving to a new server: ZATCA screen ▸ Recovery code.
# ============================================================
import base64
import os
import secrets
import string

PREFIX = "sqlv1:"
KEY = "DayBillZatcaKey"
CERT = "DayBillZatcaCert"
SECRET_COLS = ("private_key", "ccsid_secret", "pcsid_secret")
last_error = ""


class VaultLocked(RuntimeError):
    """The protected ZATCA key can't be opened on this SQL Server."""


def _db():
    from config.database import db
    return db


# ── SQL Server backend (swappable in tests) ───────────────────
def _sql_ready():
    db = _db()
    k = db.execute_scalar("SELECT COUNT(*) FROM sys.symmetric_keys WHERE name=?", (KEY,))
    c = db.execute_scalar("SELECT COUNT(*) FROM sys.certificates WHERE name=?", (CERT,))
    return bool(k) and bool(c)


def _sql_setup(password):
    """Create master key (if the database has none), certificate and key.
    Returns True when WE made the master key (the recovery code is ours)."""
    db = _db()
    made = False
    has_dmk = db.execute_scalar("SELECT COUNT(*) FROM sys.symmetric_keys "
                                "WHERE name='##MS_DatabaseMasterKey##'")
    if not has_dmk:
        db.execute("CREATE MASTER KEY ENCRYPTION BY PASSWORD = '%s'" % password)
        made = True
    if not db.execute_scalar("SELECT COUNT(*) FROM sys.certificates WHERE name=?", (CERT,)):
        db.execute("CREATE CERTIFICATE %s WITH SUBJECT = 'DayBill ZATCA keys', "
                   "EXPIRY_DATE = '20991231'" % CERT)
    if not db.execute_scalar("SELECT COUNT(*) FROM sys.symmetric_keys WHERE name=?", (KEY,)):
        db.execute("CREATE SYMMETRIC KEY %s WITH ALGORITHM = AES_256 "
                   "ENCRYPTION BY CERTIFICATE %s" % (KEY, CERT))
    return made


def _sql_encrypt(text):
    db = _db()
    db.execute("OPEN SYMMETRIC KEY %s DECRYPTION BY CERTIFICATE %s" % (KEY, CERT))
    try:
        v = db.execute_scalar("SELECT ENCRYPTBYKEY(KEY_GUID('%s'), CAST(? AS NVARCHAR(4000)))"
                              % KEY, (text,))
    finally:
        try:
            db.execute("CLOSE SYMMETRIC KEY %s" % KEY)
        except Exception:
            pass
    return bytes(v) if v is not None else None


def _sql_decrypt(blob):
    return _db().execute_scalar(
        "SELECT CONVERT(NVARCHAR(4000), DECRYPTBYKEYAUTOCERT(CERT_ID('%s'), NULL, ?))" % CERT,
        (blob,))


def _sql_recover(code):
    db = _db()
    db.execute("OPEN MASTER KEY DECRYPTION BY PASSWORD = '%s'" % code)
    db.execute("ALTER MASTER KEY ADD ENCRYPTION BY SERVICE MASTER KEY")
    try:
        db.execute("CLOSE MASTER KEY")
    except Exception:
        pass


BACKEND = {"ready": _sql_ready, "setup": _sql_setup, "encrypt": _sql_encrypt,
           "decrypt": _sql_decrypt, "recover": _sql_recover}


# ── recovery code (kept on this PC, locked with Windows DPAPI) ─
_ALPHA = string.ascii_letters + string.digits + "#%+-=@"


def _new_code():
    while True:
        c = "".join(secrets.choice(_ALPHA) for _ in range(28))
        if (any(x.islower() for x in c) and any(x.isupper() for x in c)
                and any(x.isdigit() for x in c) and any(x in "#%+-=@" for x in c)):
            return c


def _code_ok(code):
    return bool(code) and 8 <= len(code) <= 128 and all(ch in _ALPHA for ch in code)


def _code_file():
    try:
        from config.paths import config_file
        return config_file("daybill_vault_recovery.dat")
    except Exception:
        return os.path.join(os.path.dirname(__file__), "..", "..", "config",
                            "daybill_vault_recovery.dat")


def saved_code():
    try:
        from config import secret_box as sb
        with open(_code_file(), "r", encoding="utf-8") as f:
            return sb.reveal(f.read().strip())
    except Exception:
        return ""


def _save_code(code):
    try:
        from config import secret_box as sb
        p = _code_file()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(sb.protect(code))
    except Exception:
        pass


# ── value level ───────────────────────────────────────────────
def is_locked_value(v):
    return isinstance(v, str) and v.startswith(PREFIX)


def lock(text):
    """Plain → 'sqlv1:…' (checked to open again before it is returned)."""
    if not text or is_locked_value(text):
        return text
    enc = BACKEND["encrypt"](text)
    if not enc:
        raise RuntimeError("SQL Server could not encrypt (key missing?)")
    if BACKEND["decrypt"](enc) != text:
        raise RuntimeError("SQL Server encryption check failed — nothing changed")
    return PREFIX + base64.b64encode(enc).decode("ascii")


def unlock(value):
    """'sqlv1:…' → plain. Plain values come back as they are."""
    if not is_locked_value(value):
        return value
    blob = base64.b64decode(value[len(PREFIX):])
    try:
        plain = BACKEND["decrypt"](blob)
    except Exception as e:
        raise VaultLocked("The ZATCA key can't be opened: %s" % str(e)[:150])
    if plain is None:
        raise VaultLocked("The ZATCA key is protected and this SQL Server can't open it "
                          "(database restored on another server?). ZATCA ▸ 🔑 Recovery "
                          "code, or give this PC's database login db_owner rights.")
    return plain


def open_row(row):
    """EGS row with its secrets opened (a copy). Raises VaultLocked."""
    if not row:
        return row
    out = dict(row)
    for c in SECRET_COLS:
        if c in out:
            out[c] = unlock(out[c])
    return out


def lock_row_values(values):
    """For new EGS rows when protection is on: {col: value} → locked."""
    if not enabled():
        return values
    return {k: (lock(v) if k in SECRET_COLS else v) for k, v in values.items()}


# ── whole-table switch ────────────────────────────────────────
def enabled():
    try:
        db = _db()
        n = db.execute_scalar("SELECT COUNT(*) FROM zatca_egs WHERE private_key LIKE ?",
                              (PREFIX + "%",))
        return bool(n)
    except Exception:
        return False


def status():
    """('protected' | 'plain' | 'none', text)"""
    try:
        db = _db()
        rows = db.fetchall("SELECT private_key FROM zatca_egs WHERE private_key IS NOT NULL") or []
    except Exception:
        return "none", ""
    if not rows:
        return "none", "No ZATCA unit yet."
    locked = sum(1 for r in rows if is_locked_value(r.get("private_key")))
    if locked == len(rows):
        return "protected", "🔒 ZATCA keys are protected (SQL Server encryption)."
    return "plain", "⚠ ZATCA keys are stored in plain text — click 🔒 Protect keys."


def protect_all():
    """Set up the SQL Server key (once) and lock every EGS secret.
    Returns (ok, message, recovery_code or '')."""
    global last_error
    db = _db()
    code = ""
    try:
        if not BACKEND["ready"]():
            code = _new_code()
            made = BACKEND["setup"](code)
            if not made:
                code = ""                     # the database already had a master key
        rows = [dict(r) for r in (db.fetchall("SELECT * FROM zatca_egs") or [])]
        new = {}
        for r in rows:
            vals = {}
            for c in SECRET_COLS:
                v = r.get(c)
                if v and not is_locked_value(v):
                    vals[c] = lock(v)             # each one checked before use
            if vals:
                new[r["egs_id"]] = vals
        with db.transaction():
            for eid, vals in new.items():
                db.execute("UPDATE zatca_egs SET %s WHERE egs_id=?"
                           % ", ".join("%s=?" % k for k in vals), (*vals.values(), eid))
        if code:
            _save_code(code)
        try:
            from modules import audit
            audit.log("zatca", "protect_keys", None, "ZATCA keys protected (%d unit(s))" % len(new))
        except Exception:
            pass
        return True, "ZATCA keys protected on this SQL Server (%d unit(s))." % len(new), code
    except Exception as e:
        last_error = str(e)
        return False, ("Could not protect the keys — nothing was changed.\n%s\n\n"
                       "The DayBill database login needs db_owner rights." % str(e)[:300]), ""


def unprotect_all():
    """Put the plain values back (e.g. before moving to a server where
    you can't use the recovery code)."""
    db = _db()
    try:
        rows = [dict(r) for r in (db.fetchall("SELECT * FROM zatca_egs") or [])]
        new = {}
        for r in rows:
            vals = {c: unlock(r[c]) for c in SECRET_COLS if is_locked_value(r.get(c))}
            if vals:
                new[r["egs_id"]] = vals
        with db.transaction():
            for eid, vals in new.items():
                db.execute("UPDATE zatca_egs SET %s WHERE egs_id=?"
                           % ", ".join("%s=?" % k for k in vals), (*vals.values(), eid))
        return True, "ZATCA keys are stored without protection again (%d unit(s))." % len(new)
    except Exception as e:
        return False, "Nothing was changed: %s" % str(e)[:300]


def recover(code):
    """Database restored on a new SQL Server: re-open the master key with
    the recovery code so every PC can sign again."""
    code = (code or "").strip()
    if not _code_ok(code):
        return False, "That is not a DayBill recovery code."
    try:
        BACKEND["recover"](code)
        return True, "ZATCA keys can be opened on this server again."
    except Exception as e:
        return False, "The code did not open the key: %s" % str(e)[:200]
