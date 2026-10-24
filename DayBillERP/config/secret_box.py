# ============================================================
# DayBill ERP - keep passwords / API keys unreadable on disk (v5.27)
# ------------------------------------------------------------
# Windows DPAPI ("Data Protection API", machine scope): the text is
# locked to THIS computer. Anyone who copies db_config.json or
# app_settings.json to another PC (or reads it in Notepad) sees only
#   "dpapi:AQAAANCMnd8BFdERjHoAwE/Cl+sBAAAA…"
# Any Windows user of this computer (the till, the office user) can still
# use it, so nothing changes for the shop.
#
#   protect("abc")   -> "dpapi:…"   (unchanged off Windows / on failure)
#   reveal("dpapi:…") -> "abc"      (a plain old value is returned as is,
#                                    so older files keep working)
# ============================================================
import base64
import logging
import sys

PREFIX = "dpapi:"
_ENTROPY = b"DayBill ERP secret v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_CRYPTPROTECT_LOCAL_MACHINE = 0x04
logger = logging.getLogger(__name__)
last_error = ""


def available() -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        return hasattr(ctypes, "windll") and hasattr(ctypes.windll, "crypt32")
    except Exception:
        return False


def _call(fn_name, data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return DATA_BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    src, _keep1 = blob(data)
    ent, _keep2 = blob(_ENTROPY)
    out = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    flags = _CRYPTPROTECT_UI_FORBIDDEN | _CRYPTPROTECT_LOCAL_MACHINE
    if fn_name == "protect":
        ok = crypt32.CryptProtectData(ctypes.byref(src), "DayBill", ctypes.byref(ent),
                                      None, None, flags, ctypes.byref(out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(src), None, ctypes.byref(ent),
                                        None, None, _CRYPTPROTECT_UI_FORBIDDEN,
                                        ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI %s failed" % fn_name)
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        try:
            ctypes.windll.kernel32.LocalFree(out.pbData)
        except Exception:
            pass


def is_protected(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def protect(text):
    """Lock a secret to this computer. Empty / already locked / not on
    Windows → returned unchanged (never loses the value)."""
    global last_error
    if not isinstance(text, str) or not text or is_protected(text) or not available():
        return text
    try:
        enc = _call("protect", text.encode("utf-8"))
        locked = PREFIX + base64.b64encode(enc).decode("ascii")
        if reveal(locked) != text:                 # must open again before we trust it
            raise OSError("DPAPI check failed")
        return locked
    except Exception as e:
        last_error = str(e)
        logger.warning("secret_box.protect: %s", e)
        return text


def reveal(value, default=""):
    """The plain secret. A locked value from another computer (copied
    file) can't be opened → default ('' : the screen asks for it again)."""
    global last_error
    if not is_protected(value):
        return value
    try:
        raw = base64.b64decode(value[len(PREFIX):])
        return _call("reveal", raw).decode("utf-8")
    except Exception as e:
        last_error = "This secret was locked on another computer — type it again (%s)" % e
        logger.warning("secret_box.reveal: %s", e)
        return default
