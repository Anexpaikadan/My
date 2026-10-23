# ============================================================
# DayBill ERP - Mobile server (same Wi-Fi)
# ------------------------------------------------------------
# A small web server inside DayBill. Phones and PDT scanners on the
# shop Wi-Fi open  http://<this PC's IP>:8090  in Chrome (or the
# DayBill Android app) and get the DayBill Mobile app:
#   Goods In · Goods Out · Stock Count · Stock Adjust · Product Info ·
#   Price Check · Van Sales · Purchase Order · Barcode Labels · Offer Poster
# Every request is answered by modules/mobile_api.py. All database work
# runs on DayBill's own (main) thread, one request at a time, so the
# desktop and the phones never trip over each other.
# ============================================================
import sys, os, json, socket, threading, queue, time, mimetypes, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "mobile")
if getattr(sys, "frozen", False):                       # PyInstaller exe
    WEB = os.path.join(getattr(sys, "_MEIPASS", ROOT), "mobile")
DEFAULT_PORT = 8090
try:
    from config.version import VERSION
except Exception:
    VERSION = "7.5.0"


def local_ips():
    """This PC's addresses on the shop network (for the phone link)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


# ── run database work on DayBill's main thread ────────────────
class MainThreadRunner:
    """Server threads hand a job to the Tk main loop and wait for it."""

    def __init__(self, tk_root=None):
        self.root = tk_root
        self.q = queue.Queue()
        self.lock = threading.Lock()
        if tk_root is not None:
            self._pump()

    def _pump(self):
        try:
            while True:
                fn, box, ev = self.q.get_nowait()
                try:
                    box["ok"] = fn()
                except BaseException as e:      # noqa: B902 - handed back to the thread
                    box["err"] = e
                ev.set()
        except queue.Empty:
            pass
        try:
            self.root.after(25, self._pump)
        except Exception:
            pass

    def call(self, fn, timeout=30):
        if self.root is None:                  # no window (tests / service): one at a time
            with self.lock:
                return fn()
        box, ev = {}, threading.Event()
        self.q.put((fn, box, ev))
        if not ev.wait(timeout):
            raise TimeoutError("DayBill is busy — try again.")
        if "err" in box:
            raise box["err"]
        return box.get("ok")


# ── request handling (also used directly by the tests) ──────
def handle(method, path, query, body, token):
    """Returns (status, dict)."""
    from modules import mobile_api as M
    try:
        q = {k: v[0] for k, v in (query or {}).items()}
        if path == "/api/ping":
            c = M.company()
            return 200, {"ok": True, "app": "DayBill Mobile", "version": VERSION,
                         "shop": c.get("company_name_en") or "", "shop_ar": c.get("company_name_ar") or ""}
        if path == "/api/login" and method == "POST":
            return 200, M.login(body.get("username"), body.get("password"), body.get("device", ""))
        if path == "/api/login_qr" and method == "POST":      # v7.4: personal QR
            return 200, M.login_qr(body.get("code"), body.get("device", ""))
        user = M.user_for(token or q.get("t", ""))     # a PDF link carries ?t=<token>
        if path == "/api/me":
            return 200, {"user": user["name"], "modules": user["modules"]}
        if path == "/api/logout":
            from config.database import db
            db.execute("DELETE FROM mobile_tokens WHERE token=?", (token,))
            return 200, {"ok": True}
        if path == "/api/resolve":
            return 200, M.resolve(user, q.get("code", ""))
        if path == "/api/search":
            return 200, {"items": M.search(user, q.get("q", ""))}
        if path == "/api/product":
            return 200, M.product_card(int(q.get("id") or 0), int(q["unit_id"]) if q.get("unit_id") else None,
                                       show_cost=bool({"goods_in", "po", "price_change", "receive_po"} & set(user["modules"])))
        if path == "/api/suppliers":
            M.need(user, "po" if "po" in user["modules"] and "goods_in" not in user["modules"] else "goods_in")
            return 200, {"items": M.suppliers(q.get("q", ""))}
        if path == "/api/po_suggest":            # v7.2: low stock → purchase order
            return 200, {"items": M.po_suggest(user, int(q["supplier_id"]) if q.get("supplier_id") else None)}
        if path == "/api/po_list":
            return 200, {"items": M.po_list(user)}
        if path == "/api/po_open":               # v7.5: receive against a PO
            return 200, {"items": M.po_open(user, q.get("q", ""))}
        if path == "/api/po_detail":
            return 200, M.po_detail(user, int(q.get("id") or 0))
        if path == "/api/label_designs":
            if "price_change" in user["modules"] and "labels" not in user["modules"]:
                return 200, {"items": M.label_designs(dict(user, modules=user["modules"] + ["labels"]))}
            return 200, {"items": M.label_designs(user)}
        if path == "/api/poster_options":
            return 200, M.poster_options(user)
        if path == "/api/file":                  # the label / poster PDF of a job
            data, name = M.doc_pdf(user, int(q.get("doc") or 0))
            return 200, {"_bytes": data, "_ctype": "application/pdf", "_name": name}
        if path == "/api/submit" and method == "POST":
            return 200, M.submit(user, body.get("doc") or body, source="wifi",
                                 device=body.get("device", ""))
        if path == "/api/docs":
            return 200, {"items": M.my_docs(user)}
        if path == "/api/doc_status":
            return 200, M.doc_status(user, q.get("uid", ""))
        if path == "/api/count_plan":            # v6.4: today's cycle-count list
            M.need(user, "count")
            from modules import cycle_count as CC
            items = CC.plan(limit=int(q.get("limit") or 0) or None)
            return 200, M.clean({"items": [{k: r[k] for k in ("product_id", "code", "name", "name_ar",
                                                             "class", "last_counted", "days_since",
                                                             "barcode")} for r in items],
                                 "approval": CC.needs_approval()})
        if path == "/api/catalog":
            M.need(user, "van")
            return 200, M.van_catalog(user["user_id"])
        return 404, {"error": "Not found"}
    except M.MobileError as e:
        return (401 if "sign in" in str(e).lower() else 400), {"error": str(e)}
    except (ValueError, TypeError, AttributeError, KeyError) as e:     # malformed request
        return 400, {"error": "Bad request: %s" % str(e)[:120]}
    except Exception as e:
        traceback.print_exc()
        return 500, {"error": "DayBill error: %s" % str(e)[:200]}


class _Handler(BaseHTTPRequestHandler):
    server_version = "DayBillMobile/" + VERSION
    runner = None

    def log_message(self, fmt, *args):         # keep the console quiet
        pass

    def _send(self, status, payload, ctype="application/json; charset=utf-8", extra=None):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Cache-Control", "no-store" if ctype.startswith("application/json") else "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def _route(self, method):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            body = {}
            if method == "POST":
                try:
                    n = max(0, int(self.headers.get("Content-Length") or 0))
                except ValueError:
                    return self._send(400, {"error": "Bad Content-Length"})
                if n > 5_000_000:
                    return self._send(413, {"error": "Too big"})
                try:
                    body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                except Exception:
                    return self._send(400, {"error": "Bad JSON"})
                if not isinstance(body, dict):
                    return self._send(400, {"error": "Bad JSON"})
            tok = (self.headers.get("Authorization") or "").replace("Bearer", "").strip()
            try:
                status, out = self.runner.call(
                    lambda: handle(method, u.path, parse_qs(u.query), body, tok))
            except TimeoutError as e:
                status, out = 503, {"error": str(e)}
            if isinstance(out, dict) and "_bytes" in out:
                return self._send(status, out["_bytes"], out.get("_ctype") or "application/octet-stream",
                                  {"Content-Disposition": 'inline; filename="%s"' % out.get("_name", "file")})
            return self._send(status, out)
        # static app files
        rel = u.path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(WEB, rel))
        if not full.startswith(os.path.normpath(WEB)) or not os.path.isfile(full):
            full = os.path.join(WEB, "index.html")          # single-page app
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            return self._send(404, {"error": "app files missing"})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".webmanifest"):
            ctype = "application/manifest+json"
        if full.endswith(".js"):
            ctype = "application/javascript"
        if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
            ctype += "; charset=utf-8"
        self._send(200, data, ctype)


def bind_address():
    """v7.5: which network the phone server listens on (Mobile ▸ Wi-Fi ▸
    Listen on): '0.0.0.0' every network (default), one address of this PC
    (the shop Wi-Fi only), or 127.0.0.1 (this PC only)."""
    try:
        from config import settings as cfg
        v = str(cfg.get("mobile_bind", "") or "").strip()
    except Exception:
        v = ""
    if not v or v.lower() in ("all", "any", "0.0.0.0"):
        return "0.0.0.0"
    if v == "127.0.0.1" or v.lower() == "localhost":
        return "127.0.0.1"
    return v if v in local_ips() else "0.0.0.0"     # the PC's address changed → every network


class MobileServer:
    """start() / stop(); one per DayBill window."""

    def __init__(self, tk_root=None, port=None):
        from config import settings as cfg
        self.port = int(port or cfg.get("mobile_port", DEFAULT_PORT) or DEFAULT_PORT)
        self.runner = MainThreadRunner(tk_root)
        self.httpd = None
        self.thread = None
        self.error = ""

    @property
    def running(self):
        return self.httpd is not None

    def start(self):
        if self.httpd:
            return True
        handler = type("H", (_Handler,), {"runner": self.runner})
        self.host = bind_address()
        try:
            self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        except OSError as e:
            self.error = ("Port %d is busy (another program uses it). Change Settings ▸ "
                          "Mobile ▸ Port." % self.port) if "in use" in str(e).lower() or \
                getattr(e, "errno", 0) in (98, 10048) else str(e)
            self.httpd = None
            return False
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="daybill-mobile",
                                       daemon=True)
        self.thread.start()
        self.error = ""
        return True

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        self.httpd = None

    def urls(self):
        host = getattr(self, "host", None) or bind_address()
        if host not in ("0.0.0.0", ""):
            return ["http://%s:%d" % (host, self.port)]
        return ["http://%s:%d" % (ip, self.port) for ip in local_ips()]


_SERVER = {"s": None}


def get_server(tk_root=None):
    if _SERVER["s"] is None:
        _SERVER["s"] = MobileServer(tk_root)
    return _SERVER["s"]
