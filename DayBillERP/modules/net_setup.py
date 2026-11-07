# ============================================================
# DayBill ERP - several counters on one server (v7.9.3)
# ------------------------------------------------------------
# Helpers for Database Settings on the login screen:
#   allow_sql_firewall()   SERVER PC: let the counters reach SQL Server
#                          (Windows Firewall: TCP 1433 + UDP 1434 for the
#                          SQL Browser, private / domain networks only)
#   server_address()       what the counters type in Server
#                          (192.168.1.10,1433 — or PC\SQLEXPRESS)
#   guide_text()           docs/MULTI_COUNTER_SETUP.md (also inside the exe)
# The full steps are in docs/MULTI_COUNTER_SETUP.md.
# ============================================================
import os
import sys

SQL_PORT = 1433
BROWSER_PORT = 1434
RULES = (("DayBill SQL Server", "TCP", SQL_PORT),
         ("DayBill SQL Browser", "UDP", BROWSER_PORT))


def firewall_commands(port=SQL_PORT):
    """The netsh commands (without 'netsh') — delete + add, so pressing the
    button twice never makes two rules."""
    out = []
    for name, proto, p in RULES:
        p = port if proto == "TCP" else p
        out.append('advfirewall firewall delete rule name="%s"' % name)
        out.append('advfirewall firewall add rule name="%s" dir=in action=allow protocol=%s '
                   'localport=%d profile=private,domain' % (name, proto, p))
    return out


def manual_text(port=SQL_PORT):
    return "\n".join("netsh " + c for c in firewall_commands(port) if " add " in c)


def allow_sql_firewall(port=SQL_PORT):
    """→ (asked, message). On Windows the rules are added through one
    'Run as administrator' prompt; elsewhere the commands are returned."""
    if os.name != "nt":
        return False, "Run this once as Administrator (Command Prompt) on the server PC:\n\n" + manual_text(port)
    line = " & ".join("netsh " + c for c in firewall_commands(port))
    try:
        import ctypes
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", '/c ' + line, None, 0)
    except Exception:
        r = 0
    if r > 32:
        return True, ("Windows asked for permission. If you pressed Yes, the counters can now reach "
                      "SQL Server on this PC (TCP %d, UDP %d).\n\nCounters type in Server:\n    %s"
                      % (port, BROWSER_PORT, server_address(port)))
    return False, ("Not done (permission was not given). Run this once as Administrator "
                   "(Command Prompt) on the server PC:\n\n" + manual_text(port))


def local_ips():
    try:
        from modules.mobile_server import local_ips as _ips
        return [ip for ip in _ips() if not ip.startswith("127.")]
    except Exception:
        return []


def server_address(port=SQL_PORT):
    """'192.168.1.10,1433' (this PC on the shop network), or the PC name."""
    ips = local_ips()
    if ips:
        return "%s,%d" % (ips[0], port)
    return (os.environ.get("COMPUTERNAME") or "SERVER-PC") + "\\SQLEXPRESS"


def guide_path():
    roots = [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    for r in roots:
        p = os.path.join(r, "docs", "MULTI_COUNTER_SETUP.md") if r else ""
        if p and os.path.exists(p):
            return p
    return ""


def guide_text():
    p = guide_path()
    if not p:
        return "The guide docs/MULTI_COUNTER_SETUP.md is missing."
    with open(p, encoding="utf-8") as f:
        return f.read()


# ── v7.9.9: why can't this PC reach the server? (step by step) ─────────
def parse_server(text):
    """'192.168.1.10,1433' / 'PC\\SQLEXPRESS' / 'PC' → (host, instance, port)."""
    t = str(text or "").strip().replace("tcp:", "")
    port = None
    if "," in t:
        t, p = t.split(",", 1)
        try:
            port = int(p.strip())
        except ValueError:
            port = None
    host, _sep, inst = t.partition("\\")
    host = host.strip() or "localhost"
    if host in (".", "(local)"):
        host = "localhost"
    return host, inst.strip() or None, port


def browser_port(host, instance, timeout=1.5):
    """Ask the server's SQL Server Browser (UDP 1434) for an instance's TCP
    port → port, or None when nobody answers."""
    import socket
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(b"\x04" + instance.encode("ascii", "ignore") + b"\x00", (host, 1434))
        data, _a = s.recvfrom(65535)
        txt = bytes(data[3:]).decode("ascii", "replace")
        f = txt.split(";")
        d = {f[i]: f[i + 1] for i in range(0, len(f) - 1, 2)}
        return int(d["tcp"]) if d.get("tcp") else None
    except Exception:
        return None
    finally:
        if s is not None:
            s.close()


def diagnose(server, config=None, tcp_timeout=2.0):
    """Check each step between this PC and the SQL Server → list of
    (ok: True/False/None for info, step, detail / what to do)."""
    import socket
    import time
    out = []
    host, inst, port = parse_server(server)
    try:
        ip = socket.gethostbyname(host)
        out.append((True, "Server name found", "%s → %s" % (host, ip)))
    except Exception:
        out.append((False, "Server name not found",
                    "This PC can't find '%s'. Type the server's IP address instead, e.g. "
                    "192.168.1.10,1433 (ipconfig on the server shows it)." % host))
        return out
    if port is None and inst:
        port = browser_port(ip, inst)
        if port:
            out.append((True, "SQL Server Browser answered", "instance %s uses TCP port %d" % (inst, port)))
        else:
            out.append((False, "No answer from SQL Server Browser (UDP 1434)",
                        "On the server: start the 'SQL Server Browser' service (Automatic) and press "
                        "🛡 Allow SQL Server in Firewall — or set TCP port 1433 and type %s,1433." % ip))
            port = 1433
    elif port is None:
        port = 1433
    t0 = time.time()
    try:
        with socket.create_connection((ip, port), timeout=tcp_timeout):
            pass
        out.append((True, "TCP port %d open" % port, "%.0f ms" % ((time.time() - t0) * 1000)))
    except Exception:
        out.append((False, "TCP port %d closed or blocked" % port,
                    "On the server: SQL Server Configuration Manager ▸ TCP/IP ▸ Enable, IPAll TCP Port = %d, "
                    "restart the SQL Server service; press 🛡 Allow SQL Server in Firewall there; the "
                    "network must be 'Private'." % port))
        return out
    if config is None:
        return out
    try:
        import pyodbc
        from config.database import build_connection_string
        c = dict(config)
        c["server"] = server
        c.setdefault("timeout", 5)
        cn = pyodbc.connect(build_connection_string(c), timeout=5)
    except Exception as e:
        msg = str(e)
        if "18456" in msg or "Login failed" in msg:
            fix = ("Wrong user / password, or the server only allows Windows sign-in: SSMS ▸ server "
                   "Properties ▸ Security ▸ 'SQL Server and Windows Authentication', restart the service; "
                   "use SQL Server Authentication with the 'daybill' login here.")
        elif "4060" in msg or "Cannot open database" in msg:
            fix = ("Signed in, but this login may not open the database: SSMS ▸ Security ▸ Logins ▸ the "
                   "login ▸ User Mapping ▸ tick the DayBill database ▸ db_owner.")
        elif "certificate" in msg.lower() or "SSL" in msg:
            fix = "Encryption problem: tick 'Trust server certificate' (DayBill does it by default)."
        else:
            fix = msg[:220]
        out.append((False, "Sign-in failed", fix))
        return out
    try:
        cur = cn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        t0 = time.time()
        for _ in range(10):
            cur.execute("SELECT 1")
            cur.fetchone()
        ms = (time.time() - t0) * 100.0
        out.append((True, "Signed in to the database", str(config.get("database") or "")))
        if ms <= 3:
            out.append((True, "Speed: %.1f ms per request" % ms, "fast (cable network or this PC)"))
        elif ms <= 15:
            out.append((None, "Speed: %.1f ms per request" % ms, "good"))
        else:
            out.append((False, "Speed: %.1f ms per request — slow" % ms,
                        "Use a network cable instead of Wi-Fi, keep the server PC awake (no sleep), type "
                        "the server as IP,1433 (skips the name lookup)."))
    finally:
        cn.close()
    return out


# ── v7.9.9: speed up the database ──────────────────────────────────────
def optimise(db_conn=None, fragmented_pct=30.0, min_pages=100):
    """Refresh the statistics (SQL Server then picks fast query plans) and
    tidy fragmented indexes (REORGANIZE — online, safe while people work).
    → {'stats': True/False, 'indexes': n, 'errors': [...]}"""
    if db_conn is None:
        from config.database import db as db_conn
    res = {"stats": False, "indexes": 0, "errors": []}
    try:
        db_conn.execute("EXEC sp_updatestats")
        res["stats"] = True
    except Exception as e:
        res["errors"].append("statistics: %s" % str(e)[:120])
    try:
        rows = db_conn.fetchall(
            "SELECT OBJECT_SCHEMA_NAME(s.object_id) AS sch, OBJECT_NAME(s.object_id) AS tbl, i.name AS idx "
            "FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') s "
            "JOIN sys.indexes i ON i.object_id=s.object_id AND i.index_id=s.index_id "
            "WHERE s.avg_fragmentation_in_percent >= ? AND s.page_count >= ? AND i.name IS NOT NULL",
            (fragmented_pct, min_pages)) or []
    except Exception as e:
        rows = []
        res["errors"].append("fragmentation: %s" % str(e)[:120])
    for r in rows:
        try:
            db_conn.execute("ALTER INDEX [%s] ON [%s].[%s] REORGANIZE"
                            % (r["idx"].replace("]", "]]"), r["sch"].replace("]", "]]"),
                               r["tbl"].replace("]", "]]")))
            res["indexes"] += 1
        except Exception as e:
            res["errors"].append("%s: %s" % (r["idx"], str(e)[:80]))
    return res
