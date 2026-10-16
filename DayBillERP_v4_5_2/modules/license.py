# ============================================================
# DayBill ERP - Product key (licence) + 30-day trial
# ------------------------------------------------------------
# • Offline key: signed by the dealer's Key Generator (Ed25519). The app
#   only holds the PUBLIC key, so keys can't be made from the app.
#   A key carries: customer, installation ID it is for, branches,
#   counters, expiry date, serial.
# • Installation ID: made once per DATABASE (so every counter PC on the
#   shop's server shares one key) + the SQL Server name / database date.
# • Trial: 30 days from the first start, full app. After that (or when
#   a key expires / is blocked) the app is READ-ONLY: everything opens,
#   prints and exports, but nothing new can be saved.
# • Online (optional): Settings ▸ Product Key ▸ licence server URL. The
#   app checks now and then; the dealer can block, renew or change a
#   licence there. No internet = keeps working on the offline key.
# ============================================================

import base64
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db

PUBLIC_KEY_HEX = "875760407a68ac6b1c6e100a1c83448a0d38409f1fe8298acd5b09a121761249"
TRIAL_DAYS = 30
TRIAL_LIMITS = {"branches": 1, "counters": 2}
KEY_PREFIX = "DB1"
try:        # exe: next to DayBillERP.exe (not the temp unpack folder)
    from config.paths import config_file as _cfg_file
    _LOCAL = _cfg_file("license.json")
except Exception:
    _LOCAL = os.path.join(os.path.dirname(__file__), "..", "config", "license.json")
_cache = {"t": 0.0, "status": None}


# ── storage: app_license row id=1 (shared) or config/license.json ──
_MISSING = object()
_last_good = {}


def _db_row():
    """The row, None when there is no row yet, _MISSING when the read failed."""
    for _ in range(2):
        try:
            return db.fetchone("SELECT * FROM app_license WHERE id=1")
        except Exception:
            time.sleep(0.2)
    return _MISSING


def _db_ok():
    try:
        db.execute_scalar("SELECT COUNT(*) FROM app_license")
        return True
    except Exception:
        return False


def _local_read():
    try:
        with open(_LOCAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _local_write(d):
    try:
        with open(_LOCAL, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, default=str)
    except Exception:
        pass


def _record():
    """The licence record, created on first use. A failed read (network
    blip to the server) re-uses the last good record — it never makes a
    new installation ID."""
    if _db_ok():
        r = _db_row()
        if r is _MISSING:
            return dict(_last_good) if _last_good else {"install_id": "", "_unreadable": True}
        if not r:
            iid = uuid.uuid4().hex[:16].upper()
            try:
                db.execute("INSERT INTO app_license (id, install_id, installed_at) VALUES (1,?,?)",
                           (iid, date.today().isoformat()))
            except Exception:
                pass
            r = _db_row()
            if not r or r is _MISSING:
                return {"install_id": iid, "installed_at": date.today().isoformat()}
        _last_good.clear(); _last_good.update(dict(r)); _last_good["_from_db"] = True
        return dict(r)
    if _last_good and _last_good.get("_from_db"):
        return dict(_last_good)
    d = _local_read()
    if not d.get("install_id"):
        d = {"install_id": uuid.uuid4().hex[:16].upper(),
             "installed_at": date.today().isoformat()}
        _local_write(d)
    return d


def _save(**fields):
    if _db_ok():
        _record()
        sets = ", ".join(f"{k}=?" for k in fields)
        try:
            db.execute(f"UPDATE app_license SET {sets} WHERE id=1", tuple(fields.values()))
        except Exception:
            pass
    else:
        d = _local_read()
        d.update({k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in fields.items()})
        _local_write(d)
    _cache["t"] = 0


def _d(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


# ── installation ID (what the customer sends to the dealer) ──
_ident = {}


def _server_identity():
    """SQL Server name | database | database create date (cached)."""
    if "v" in _ident:
        return _ident["v"]
    for _ in range(2):
        try:
            r = db.fetchone("SELECT @@SERVERNAME AS s, DB_NAME() AS n, (SELECT create_date "
                            "FROM sys.databases WHERE name=DB_NAME()) AS d")
        except Exception:
            time.sleep(0.1)
            continue
        if r:
            _ident["v"] = f"{r.get('s')}|{r.get('n')}|{str(r.get('d'))[:19]}"
            return _ident["v"]
        break
    return ""


def installation_id():
    rec = _record()
    raw = f"{rec.get('install_id')}|{_server_identity()}".encode()
    code = base64.b32encode(hashlib.sha256(raw).digest()).decode()[:16]
    return "-".join(code[i:i + 4] for i in range(0, 16, 4))


def _norm_fp(fp):
    return str(fp or "").replace("-", "").replace(" ", "").upper()


# ── key decode / verify ──────────────────────────────────────
def _decode(key):
    s = "".join(ch for ch in str(key or "").upper() if ch.isalnum())
    if not s.startswith(KEY_PREFIX):
        raise ValueError("This is not a DayBill product key.")
    body = s[len(KEY_PREFIX):]
    body += "=" * (-len(body) % 8)
    raw = base64.b32decode(body)
    n = raw[0] | (raw[1] << 8)
    payload, sig = raw[2:2 + n], raw[2 + n:2 + n + 64]
    if len(sig) != 64:
        raise ValueError("The key is incomplete — copy all of it.")
    return payload, sig


def verify(key, fingerprint=None):
    """(True, info) or (False, reason). info = dict from the key."""
    try:
        payload, sig = _decode(key)
    except Exception as e:
        return False, str(e) if isinstance(e, ValueError) else "The key is not valid."
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX)).verify(sig, payload)
    except ImportError:
        return False, "Install the 'cryptography' package (install_requirements.py)."
    except Exception:
        return False, "The key is not valid (signature check failed)."
    try:
        info = json.loads(payload.decode("utf-8"))
    except Exception:
        return False, "The key is not valid."
    fp = _norm_fp(fingerprint if fingerprint is not None else installation_id())
    if info.get("f") not in ("*", fp):
        return False, ("This key was made for another installation "
                       f"({info.get('f')}). This PC's installation ID is {installation_id()}.")
    return True, info


def make_key(info, private_key):
    """Used by the dealer's Key Generator (needs the PRIVATE key)."""
    payload = json.dumps(info, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = private_key.sign(payload)
    raw = bytes([len(payload) & 0xFF, len(payload) >> 8]) + payload + sig
    body = base64.b32encode(raw).decode().rstrip("=")
    groups = [body[i:i + 5] for i in range(0, len(body), 5)]
    return KEY_PREFIX + "-" + "-".join(groups)


# ── status ───────────────────────────────────────────────────
def status(refresh=False):
    """{mode: licensed|trial|trial_over|expired|blocked|invalid, days_left,
    customer, branches, counters, expiry, serial, message}"""
    if not refresh and _cache["status"] and time.time() - _cache["t"] < 60:
        return _cache["status"]
    rec = _record()
    if rec.get("_unreadable"):
        # database not reachable right now: don't lock the shop over it
        return _cache["status"] or {"mode": "trial", "days_left": TRIAL_DAYS, "customer": "",
                                    "branches": None, "counters": None, "expiry": None,
                                    "serial": "", "message": "", "online": "", "installed": None}
    today = date.today()
    st = {"mode": "trial", "days_left": None, "customer": "", "branches": None,
          "counters": None, "expiry": None, "serial": "", "message": "",
          "online": rec.get("online_status") or "", "installed": _d(rec.get("installed_at"))}
    key = rec.get("product_key")
    if key:
        ok, info = verify(key)
        if ok:
            exp = _d(info.get("e"))
            st.update(customer=info.get("c", ""), branches=info.get("b") or None,
                      counters=info.get("n") or None, expiry=exp, serial=info.get("s", ""))
            if exp and exp < today:
                st.update(mode="expired", days_left=0,
                          message=f"Your product key expired on {exp:%d/%m/%Y}.")
            else:
                st.update(mode="licensed", days_left=(exp - today).days if exp else None)
            if str(rec.get("online_status") or "").lower() == "blocked":
                st.update(mode="blocked", message=rec.get("online_message")
                          or "This licence was blocked by your dealer.")
        else:
            st.update(mode="invalid", message=info)
    if st["mode"] in ("trial", "invalid"):
        start = _d(rec.get("installed_at")) or today
        left = TRIAL_DAYS - (today - start).days
        if st["mode"] == "trial":
            st["days_left"] = max(0, left)
            if left <= 0:
                st.update(mode="trial_over", message="The 30-day trial has ended.")
        else:
            st["days_left"] = max(0, left)
            if left > 0:
                st["mode"] = "trial"
    _cache.update(t=time.time(), status=st)
    return st


def write_ok():
    return status()["mode"] in ("licensed", "trial")


def block_message():
    st = status()
    base = st.get("message") or "The product key is not active."
    return (base + "\n\nDayBill is now READ-ONLY: you can open, print and export, "
            "but not save new or changed documents.\n\nEnter a product key in "
            "Help ▸ Product Key (installation ID: " + installation_id() + ").")


def limits():
    st = status()
    if st["mode"] == "licensed":
        return {"branches": st["branches"], "counters": st["counters"]}
    return dict(TRIAL_LIMITS)


def banner_text():
    """Short text for the top bar ('' when licensed without expiry soon)."""
    st = status()
    m = st["mode"]
    if m == "trial":
        return f"Trial — {st['days_left']} day(s) left"
    if m == "licensed":
        if st["days_left"] is not None and st["days_left"] <= 15:
            return f"Key expires in {st['days_left']} day(s)"
        return ""
    return {"trial_over": "Trial ended — read-only", "expired": "Key expired — read-only",
            "blocked": "Licence blocked — read-only",
            "invalid": "Key not valid — read-only"}.get(m, "")


def activate(key):
    ok, info = verify(key)
    if not ok:
        return False, info
    _save(product_key="".join(str(key).split()), activated_at=datetime.now(),
          online_status="", online_message="")
    st = status(refresh=True)
    if st["mode"] == "expired":
        return False, st["message"]
    lim = []
    lim.append(f"{info.get('b') or 'unlimited'} branch(es)")
    lim.append(f"{info.get('n') or 'unlimited'} counter(s)")
    exp = info.get("e") or "no expiry"
    return True, f"Activated for {info.get('c', '')}: {', '.join(lim)}, {exp}."


def remove_key():
    _save(product_key=None, activated_at=None)


# ── online licence server ─────────────────────────────────────
# The dealer's server is built in, so a customer only types the code.
DEFAULT_SERVER = "https://key.daybill.online/new/api.php"


def _server_url():
    try:
        from config import settings as cfg
        return str(cfg.get("license_server", "") or "").strip() or DEFAULT_SERVER
    except Exception:
        return DEFAULT_SERVER


def _ssl_ctx():
    import ssl
    ctx = ssl.create_default_context()
    try:                                    # some Windows PCs lack root certificates
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def _doh_lookup(host, timeout=6):
    """Find the server's IP through Google / Cloudflare (DNS over HTTPS) —
    used when the PC's own DNS can't find it (Chrome can, Windows can't)."""
    import urllib.request
    ips = []
    for base, hdr in (("https://8.8.8.8/resolve", {}),
                      ("https://1.1.1.1/dns-query", {"accept": "application/dns-json"})):
        for rtype in ("A", "AAAA"):
            try:
                req = urllib.request.Request(f"{base}?name={host}&type={rtype}", headers=hdr)
                with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
                    js = json.loads(r.read().decode("utf-8") or "{}")
                for a in js.get("Answer") or []:
                    if a.get("type") in (1, 28) and a.get("data"):
                        ips.append(a["data"])
            except Exception:
                continue
        if ips:
            break
    return ips


def _post_via_ip(url, data, headers, timeout):
    """POST to `url` but connect to an IP found by _doh_lookup (keeps
    the real host name for HTTPS / the website)."""
    import http.client, socket
    from urllib.parse import urlsplit
    u = urlsplit(url)
    host = u.hostname
    port = u.port or (443 if u.scheme == "https" else 80)
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    last = None
    for ip in _doh_lookup(host):
        try:
            if u.scheme == "https":
                ctx = _ssl_ctx()

                class _C(http.client.HTTPSConnection):
                    def connect(self):
                        sock = socket.create_connection((ip, port), self.timeout)
                        self.sock = ctx.wrap_socket(sock, server_hostname=host)
                conn = _C(host, port, timeout=timeout, context=ctx)
            else:
                conn = http.client.HTTPConnection(ip, port, timeout=timeout)
            h = dict(headers); h["Host"] = host
            conn.request("POST", path, body=data, headers=h)
            r = conn.getresponse()
            body = r.read().decode("utf-8")
            conn.close()
            return json.loads(body or "{}")
        except Exception as e:
            last = e
    raise last or RuntimeError("server not found")


class ServerError(Exception):
    """Licence server can't be reached — message is for the user."""


def _post(payload, timeout=10):
    import urllib.request, urllib.error, socket
    url = _server_url()
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "DayBillERP"}
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:            # server answered (e.g. 500)
        try:
            return json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            raise ServerError(f"The licence server gave an error ({e.code}). "
                              "Please try again later.")
    except Exception as first:
        # PC's DNS can't find the server → ask Google / Cloudflare and retry
        try:
            return _post_via_ip(url, data, headers, timeout)
        except Exception:
            pass
        raise ServerError("Can't reach the licence server. Check this PC has internet, "
                          "then try again.\n\nNo internet here? Send the Installation ID "
                          "to your dealer for an offline key.\n\n(" + str(first)[:90] + ")")


def _counters_in_use():
    try:
        return int(db.execute_scalar("SELECT COUNT(*) FROM counters WHERE ISNULL(is_active,1)=1") or 0)
    except Exception:
        return 0


def _check_payload():
    st = status(refresh=True)
    return {"action": "check", "serial": st.get("serial", ""),
            "fingerprint": installation_id(), "customer": st.get("customer", ""),
            "counters": _counters_in_use(), "app": "DayBillERP"}


def _apply_check(res):
    s = str(res.get("status") or "unknown").lower()
    msg = str(res.get("message") or "")
    fields = {"last_online": datetime.now(), "online_status": s, "online_message": msg[:300]}
    new_key = res.get("key")
    if new_key:
        ok, _info = verify(new_key)
        if ok:
            fields["product_key"] = "".join(str(new_key).split())
    _save(**fields)
    status(refresh=True)
    return msg or f"Licence status: {s}"


def online_check():
    """Ask the dealer's server about this licence. Returns (ok, message)."""
    try:
        res = _post(_check_payload())
    except Exception as e:
        return False, str(e)
    return True, _apply_check(res)


def looks_like_key(text):
    """A full offline product key (DB1-…) vs a short licence code."""
    t = "".join(str(text or "").split()).upper()
    return t.startswith("DB1-") or len(t.replace("-", "")) > 24


def activate_any(text):
    """One box for everything: a long DB1- key activates offline, a short
    licence code activates through the dealer's server."""
    t = str(text or "").strip()
    if not t:
        return False, "Type your licence code or paste the product key."
    if looks_like_key(t):
        return activate(t)
    return activate_online(t)


def activate_payload(order_code):
    code = "".join(str(order_code or "").split()).upper()
    return {"action": "activate", "code": code, "fingerprint": installation_id(),
            "app": "DayBillERP"}


def finish_activate(res):
    """Server answer → activate the key it sent. (ok, message)"""
    res = res or {}
    if res.get("key"):
        ok, msg = activate(res["key"])
        if ok:
            _save(last_online=datetime.now(), online_status="active", online_message="")
        return ok, msg
    return False, str(res.get("message") or "The server did not give a key.")


def activate_online(order_code):
    """Dealer's server turns an order / licence code into a key for THIS
    installation."""
    try:
        res = _post(activate_payload(order_code))
    except Exception as e:
        return False, str(e)
    return finish_activate(res)


def background_check(root=None, days=3, on_done=None):
    """Start-up: a quiet online check at most every `days` days. The
    network call runs in a thread; the Tk thread polls for the answer and
    saves it (Tk and the database connection stay on the main thread)."""
    rec = _record()
    if not rec.get("product_key"):          # trial: nothing to check yet
        return
    last = rec.get("last_online")
    try:
        if last and not isinstance(last, datetime):
            last = datetime.strptime(str(last)[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        last = None
    if last and datetime.now() - last < timedelta(days=days):
        return
    payload = _check_payload()
    box = {}

    def work():
        try:
            box["res"] = _post(payload)
        except Exception:
            box["res"] = None
    threading.Thread(target=work, daemon=True).start()
    if root is None:
        return

    def poll(n=0):
        if "res" not in box:
            if n < 60:
                try:
                    root.after(500, lambda: poll(n + 1))
                except Exception:
                    pass
            return
        if box["res"]:
            _safe(lambda: _apply_check(box["res"]))
            if on_done:
                _safe(on_done)
    try:
        root.after(500, poll)
    except Exception:
        pass


def _safe(fn):
    try:
        fn()
    except Exception:
        pass
