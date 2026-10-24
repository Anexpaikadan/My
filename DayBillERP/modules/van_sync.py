# ============================================================
# DayBill ERP - Van sales over the internet (Hostinger relay)
# ------------------------------------------------------------
#   Van phone  ⇄  your Hostinger site (van_relay/van_api.php)  ⇄  DayBill
#
#   sync():  1. collect the vans' new bills from the relay and book them
#               (same rules as Wi-Fi: modules/mobile_api.submit — a bill is
#               never booked twice), then tell the relay what happened
#            2. send the fresh product list, prices, customers and the
#               van users (PIN hashes only) up to the relay
#   The shop PC only calls OUT to the relay — nothing on the shop PC is
#   opened to the internet.
#
#   build_upload_folder(): makes the folder (+ a .zip) to upload to Hostinger:
#   van_api.php (+ api.php, the old name) + van_db.php + check.php + .htaccess +
#   the van app (config.js in relay mode, van.html) and, when the MySQL
#   details are given, a ready relay_config.php with the shop key.
#   5.23.2: every call has a fresh address (…&_=time) and the relay answers
#   "never cache" — an old saved redirect of the site can't get in the way.
# ============================================================
import sys, os, json, time, secrets, shutil, ssl, zipfile, urllib.request, urllib.error, urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if getattr(sys, "frozen", False):
    ROOT = getattr(sys, "_MEIPASS", ROOT)


class SyncError(Exception):
    """kind: loop | ssl | net | notfound | notrelay | relay.  http_ok: the http://
    address that works when https does not (set by test())."""
    def __init__(self, msg, kind="relay", http_ok=None):
        Exception.__init__(self, msg)
        self.kind = kind
        self.http_ok = http_ok


# 5.23.2 relay first (new address — never saved by any cache), then the old name
ENDPOINTS = ("van_api.php", "api.php")
_EP = {}            # relay address → the endpoint that answered
_CACHE_MARKS = ("x-origin-cache-status", "x-cdn-cache-status", "x-litespeed-cache", "x-cache",
                "cf-cache-status", "x-proxy-cache", "x-hcdn-cache-status")


def relay_url():
    u = str(cfg.get("van_relay_url", "") or "").strip()
    if u and not u.endswith("/"):
        u += "/"
    return u


def check_page_url():
    return relay_url() + "check.php" if relay_url() else ""


def phone_url():
    """The address van phones open (van.html is new in 5.23.2, so no old saved
    answer of the site can sit on it)."""
    return relay_url() + "van.html" if relay_url() else ""


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are followed by _request itself (keeps POST + body, spots loops)."""
    def redirect_request(self, *a, **k):
        return None


def _open(url, data, headers, timeout):
    ctx = _ctx() if url.startswith("https") else None
    opener = urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=ctx)) \
        if ctx else urllib.request.build_opener(_NoRedirect())
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    return opener.open(req, timeout=timeout)


class _Fail(Exception):
    def __init__(self, kind, msg="", where="", cached=""):
        Exception.__init__(self, msg)
        self.kind, self.msg, self.where, self.cached = kind, msg, where, cached


def _stamp(url):
    """A fresh address every time (…&_=time): a cache can never answer it."""
    return url + ("&" if "?" in url else "?") + "_=%d" % int(time.time() * 1000)


def _request(url, data, headers, timeout):
    """One call; follows up to 6 redirects itself. Returns (json, final url)."""
    seen = []
    for _hop in range(7):
        try:
            with _open(url, data, headers, timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            try:
                out = json.loads(raw or "{}")
            except ValueError:
                raise _Fail("notrelay", where=url)
            if not isinstance(out, dict):
                raise _Fail("notrelay", where=url)
            return out, url
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                loc = e.headers.get("Location") or ""
                nxt = urllib.parse.urljoin(url, loc) if loc else ""
                seen.append(url)
                if not nxt or nxt in seen or len(seen) > 6:
                    hit = next(("%s: %s" % (k, e.headers.get(k)) for k in _CACHE_MARKS
                                if "hit" in str(e.headers.get(k) or "").lower()), "")
                    raise _Fail("loop", where=nxt or url, cached=hit)
                url = nxt
                continue
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error")
            except Exception:
                msg = None
            if msg:
                raise _Fail("relay", msg, url)
            raise _Fail("notfound" if e.code in (403, 404, 410) else "http", "HTTP %s" % e.code, url)
        except urllib.error.URLError as e:
            reason = e.reason
            if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(reason).upper() or "SSL" in str(reason).upper():
                raise _Fail("ssl", str(getattr(reason, "verify_message", "") or reason), url)
            raise _Fail("net", str(reason), url)
        except (ssl.SSLError, ConnectionError, TimeoutError, OSError) as e:
            if isinstance(e, ssl.SSLError):
                raise _Fail("ssl", str(e), url)
            raise _Fail("net", str(e), url)
    raise _Fail("loop", where=url)


def _explain(f, base):
    """Plain words for the DayBill screen."""
    if f.kind == "loop":
        if f.cached:
            why = ("The site still gives an OLD SAVED answer for this address (%s) — left over from the "
                   "force-https line of the DayBill 5.23.0 .htaccess." % f.cached)
        else:
            why = ("An https rule (in .htaccess of this folder or of the main site) or “Force HTTPS” sends "
                   "it back to the same address.")
        return SyncError(
            "%s goes round in a loop (redirects to itself).\n%s\n"
            "Fix: 📁 Make upload folder ▸ upload the DayBill 5.23.2 relay files (new addresses + new .htaccess, "
            "they work at once) ▸ Test again. Still wrong? Press 🌐 Check page." % (base, why), "loop")
    if f.kind == "ssl":
        return SyncError(
            "The https certificate of %s is not valid (%s).\nOpen 🌐 Check page; on Hostinger the free SSL "
            "must be installed for this exact sub-domain." % (base, f.msg[:120]), "ssl")
    if f.kind == "net":
        return SyncError("Can't reach the relay (%s). Check the internet / the address." % f.msg[:150], "net")
    if f.kind == "notfound":
        return SyncError("The relay is not at %s (van_api.php / api.php not found). Upload ALL files of the "
                         "upload folder into this folder of your site, or fix the address." % base, "notfound")
    if f.kind == "notrelay":
        return SyncError("The address answers, but not as the DayBill relay. Check that ALL files of the upload "
                         "folder are in this folder of your site (%s)." % base, "notrelay")
    return SyncError(f.msg or "Relay error", "relay")


def _call(action, body=None, timeout=60, base=None, with_key=True):
    base = base or relay_url()
    if not base:
        raise SyncError("Type your relay address first (e.g. https://van.yourshop.com/).", "relay")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "DayBill-ERP",
               "Cache-Control": "no-cache", "Pragma": "no-cache"}
    if with_key:
        headers["X-Shop-Key"] = str(cfg.get("van_relay_key", "") or "")
    last = None
    for ep in ENDPOINTS:                   # always the new address first (the site may have been updated)
        url = _stamp(base + ep + "?a=" + action)
        try:
            out, final = _request(url, data, headers, timeout)
        except _Fail as f:
            if f.kind in ("notfound", "notrelay"):
                last = f
                continue                   # try the other file name
            raise _explain(f, base)
        fixed = final.split(ep + "?")[0]
        _EP[base] = _EP[fixed] = ep
        if with_key and fixed != base and base == relay_url():   # the site moved us: keep the right address
            cfg.set("van_relay_url", fixed)
            try:
                cfg.save_settings()
            except Exception:
                pass
        return out
    raise _explain(last, base)


def _ping(base):
    """Open ping (no shop key is sent) — is the relay reachable at this address?"""
    try:
        return (_call("ping", timeout=15, base=base, with_key=False) or {}).get("app") == "DayBill Van Relay"
    except SyncError:
        return False


def test():
    base = relay_url()
    try:
        r = _call("shop_ping", timeout=20)
    except SyncError as e:
        if base.startswith("https://") and e.kind in ("loop", "ssl", "net"):
            alt = "http://" + base[len("https://"):]
            if _ping(alt):
                e.http_ok = alt
                e.args = (str(e) + "\n➜ The http address works: " + alt,)
        raise
    msg = "✔ Relay OK — %d van bill(s) waiting." % int(r.get("waiting") or 0)
    base = relay_url()                 # may have been corrected by a redirect
    if not r.get("v"):                     # shop_ping of the 5.23.0 / 5.23.1 relay has no version
        msg += ("\n⚠ Your site has the OLD relay files. Upload the 5.23.2 files (📁 Make upload folder ▸ "
                "update only) — the van app needs them for https.")
    if base.startswith("http://"):
        alt = "https://" + base[len("http://"):]
        if _ping(alt):
            cfg.set("van_relay_url", alt)
            try:
                cfg.save_settings()
            except Exception:
                pass
            msg += "\n✔ https works now — DayBill switched to %s" % alt
        else:
            msg += ("\n⚠ Using http (not encrypted). Van phones need https to open the app with no signal — "
                    "press 🌐 Check page to see why https does not work.")
    return msg


def vans():
    """Van users (DayBill users with the Van Sales module + a van code)."""
    from config.database import db
    out = []
    for r in db.fetchall("SELECT a.user_id, a.van_code, a.van_pin_hash, a.modules, u.full_name_en, "
                         "u.username FROM mobile_access a JOIN users u ON u.user_id=a.user_id "
                         "WHERE ISNULL(a.is_active,1)=1 AND ISNULL(u.is_active,1)=1") or []:
        if "van" in str(r.get("modules") or "").split(",") and r.get("van_code") and r.get("van_pin_hash"):
            out.append({"van_code": str(r["van_code"]).upper(), "pin_hash": r["van_pin_hash"],
                        "name": r.get("full_name_en") or r["username"], "user_id": r["user_id"]})
    return out


def _import(items):
    """Book the van bills (main thread). Returns results for the relay."""
    from modules import mobile_api as M
    by_code = {v["van_code"]: v for v in vans()}
    res = []
    for it in items:
        uid = (it.get("doc") or {}).get("uid") or it.get("uid")
        v = by_code.get(str(it.get("van_code") or "").upper())
        if not v:
            res.append({"uid": uid, "status": "error", "result": "Unknown van %s" % it.get("van_code")})
            continue
        user = {"user_id": v["user_id"], "username": v["van_code"], "name": v["name"], "modules": ["van"]}
        try:
            r = M.submit(user, it.get("doc") or {}, source="van", device=it.get("device") or v["van_code"])
            res.append({"uid": uid, "status": r.get("status") or "applied", "result": r.get("result") or ""})
        except Exception as e:          # one bad document must not stop the ack / every later sync
            res.append({"uid": uid, "status": "error", "result": str(e)[:300]})
    return res


def sync(run=None, log=None):
    """run(fn) executes database work on DayBill's main thread (the
    Mobile & Van screen passes it); network calls stay in this thread."""
    run = run or (lambda fn: fn())
    say = log or (lambda m: None)
    pulled = _call("shop_pull").get("items") or []
    done = []
    if pulled:
        say("Booking %d van bill(s)…" % len(pulled))
        done = run(lambda: _import(pulled))
        _call("shop_ack", {"results": done})
    say("Sending the product list…")
    from modules import mobile_api as M
    payload = run(lambda: {"catalog": M.van_catalog(), "vans": vans()})
    _call("shop_push", payload, timeout=120)
    ok = sum(1 for d in done if d["status"] in ("applied", "pending"))
    bad = [d for d in done if d["status"] == "error"]
    cfg.set("van_last_sync", datetime.now().strftime("%Y-%m-%d %H:%M"))
    try:
        cfg.save_settings()
    except Exception:
        pass
    msg = "✔ %d van bill(s) booked · %d products · %d van(s) sent" % (
        ok, len(payload["catalog"]["products"]), len(payload["vans"]))
    if bad:
        msg += " · ⚠ %d with a problem: %s" % (len(bad), bad[0]["result"][:80])
    return msg


RELAY_FILES = ("van_api.php", "api.php", "van_db.php", "check.php", ".htaccess", "relay_config.sample.php")


def build_upload_folder(dest, mysql=None, make_zip=True):
    """Folder (+ the same as a .zip) to upload to Hostinger (the sub-domain's
    folder, or public_html/van).
    mysql = {host, name, user, password} → also writes relay_config.php with
    the shop key (kept from DayBill, or a new one) and saves that key here.
    mysql = None → "update only": the site keeps its own relay_config.php."""
    if os.path.isfile(os.path.join(dest, "api.php")) or os.path.isfile(os.path.join(dest, "van_api.php")):
        shutil.rmtree(dest, ignore_errors=True)       # an older upload folder of DayBill: make it fresh
    os.makedirs(dest, exist_ok=True)
    for f in RELAY_FILES:
        shutil.copy2(os.path.join(ROOT, "van_relay", f), os.path.join(dest, f))
    web = os.path.join(ROOT, "mobile")
    for base, _dirs, files in os.walk(web):
        rel = os.path.relpath(base, web)
        os.makedirs(os.path.join(dest, rel), exist_ok=True)
        for f in files:
            if f in ("config.js", "manifest.webmanifest"):
                continue
            shutil.copy2(os.path.join(base, f), os.path.join(dest, rel, f))
    with open(os.path.join(dest, "config.js"), "w", encoding="utf-8") as f:
        f.write('// DayBill Van app on the relay: talks to van_api.php next to it.\n'
                'window.DAYBILL = { mode: "relay", api: "van_api.php" };\n')
    # van phones open van.html (a new address: no old saved answer of the site can sit on it)
    shutil.copy2(os.path.join(web, "index.html"), os.path.join(dest, "van.html"))
    with open(os.path.join(web, "manifest.webmanifest"), encoding="utf-8") as f:
        man = json.load(f)
    man.update({"name": "DayBill Van", "short_name": "DayBill Van", "start_url": "van.html", "scope": "./"})
    with open(os.path.join(dest, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.join(dest, "data"), exist_ok=True)
    with open(os.path.join(dest, "data", ".htaccess"), "w") as f:
        f.write("<IfModule mod_authz_core.c>\n  Require all denied\n</IfModule>\n"
                "<IfModule !mod_authz_core.c>\n  Order allow,deny\n  Deny from all\n</IfModule>\n")
    key = None
    if mysql:
        key = cfg.get("van_relay_key") or ""
        if len(str(key)) < 32:
            key = secrets.token_urlsafe(36)
        esc = lambda v: str(v or "").replace("\\", "\\\\").replace("'", "\\'")
        with open(os.path.join(dest, "relay_config.php"), "w", encoding="utf-8") as f:
            f.write("<?php\n// DayBill Van Relay — made by DayBill %s. PRIVATE: holds the shop key + DB password.\n"
                    "define('DB_DRIVER', 'mysql');\ndefine('DB_HOST', '%s');\ndefine('DB_NAME', '%s');\n"
                    "define('DB_USER', '%s');\ndefine('DB_PASS', '%s');\n"
                    "define('DB_SQLITE_FILE', __DIR__ . '/data/relay.sqlite');\n"
                    "define('SHOP_KEY', '%s');\n" % (
                        datetime.now().strftime("%Y-%m-%d"), esc(mysql.get("host") or "localhost"),
                        esc(mysql.get("name")), esc(mysql.get("user")), esc(mysql.get("password")), key))
        cfg.set("van_relay_key", key)
        try:
            cfg.save_settings()
        except Exception:
            pass
    if make_zip:
        # one file to upload: File Manager ▸ Upload ▸ right-click ▸ Extract (files land in that folder)
        zpath = dest.rstrip("/\\") + ".zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _dirs, files in os.walk(dest):
                for f in sorted(files):
                    full = os.path.join(base, f)
                    z.write(full, os.path.relpath(full, dest).replace(os.sep, "/"))
    return dest, key
