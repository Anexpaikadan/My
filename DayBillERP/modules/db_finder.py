# ============================================================
# DayBill ERP - find SQL Server and the DayBill databases (v6.0.2)
# ------------------------------------------------------------
# "Another way to connect" when Database Settings is wrong:
#   find_servers(config)      tries the SQL Servers installed on this PC
#                             (Windows registry), the usual names
#                             (localhost\SQLEXPRESS, localhost …) and the
#                             servers that answer on the network (SQL
#                             Server Browser, UDP 1434 — e.g. the server
#                             PC of a till) → the ones that let us in
#   daybill_databases()       which databases on the server are DayBill's
#                             (db_backup.list_databases_marked)
# Nothing is changed on any server — it only connects and looks.
# ============================================================
import socket
import time

COMMON = ["localhost\\SQLEXPRESS", "localhost", "(localdb)\\MSSQLLocalDB"]


def local_instances():
    """SQL Server instances installed on THIS PC (from the Windows registry)."""
    out = []
    try:
        import winreg
    except ImportError:                      # not Windows
        return out
    for path in (r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL",
                 r"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\Instance Names\SQL"):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                inst = winreg.EnumValue(key, i)[0]
            except OSError:
                break
            i += 1
            name = "localhost" if str(inst).upper() == "MSSQLSERVER" else "localhost\\" + str(inst)
            if name not in out:
                out.append(name)
    return out


def parse_browser_reply(data, ip=None):
    """The SQL Server Browser's answer → ['PC\\INSTANCE', …]. v7.9.9: with the
    sender's ip also 'IP,port' — PC names often don't resolve on shop
    networks, the IP always does."""
    if not data or data[0] != 0x05:
        return []
    txt = bytes(data[3:]).decode("ascii", "replace")
    out = []
    for block in txt.split(";;"):
        f = block.split(";")
        d = {f[i]: f[i + 1] for i in range(0, len(f) - 1, 2)}
        host, inst = d.get("ServerName"), d.get("InstanceName")
        if host:
            name = host if not inst or inst.upper() == "MSSQLSERVER" else "%s\\%s" % (host, inst)
            if ip and d.get("tcp"):
                byip = "%s,%s" % (ip, d["tcp"])
                if byip not in out:
                    out.append(byip)
            if name not in out:
                out.append(name)
    return out


def local_ipv4():
    """This PC's addresses on the shop network."""
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
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return [ip for ip in ips if not ip.startswith(("127.", "169.254."))]


def subnet_broadcasts():
    """x.y.z.255 of every local /24 network (a plain 255.255.255.255 is
    dropped by many routers and Windows setups)."""
    return ["%s.255" % ip.rsplit(".", 1)[0] for ip in local_ipv4()]


def tcp_sweep(port=1433, timeout=0.3, limit=254):
    """PCs on the local /24 networks with SQL Server's port open — finds a
    server even when the SQL Server Browser is off → ['192.168.1.10,1433']."""
    import threading
    hits, lock = [], threading.Lock()
    mine = set(local_ipv4())

    def probe(ip):
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                with lock:
                    hits.append("%s,%d" % (ip, port))
        except Exception:
            pass
    threads = []
    for ip in mine:
        base = ip.rsplit(".", 1)[0]
        for i in range(1, min(254, limit) + 1):
            t = threading.Thread(target=probe, args=("%s.%d" % (base, i),), daemon=True)
            threads.append(t)
            t.start()
    for t in threads:
        t.join(timeout + 0.5)
    for ip in mine:                         # this PC itself
        if "%s,%d" % (ip, port) in hits:
            hits.remove("%s,%d" % (ip, port))
            hits.insert(0, "%s,%d" % (ip, port))
    return sorted(set(hits), key=hits.index)


def network_instances(timeout=1.5, targets=None, port=1434):
    """Ask every SQL Server Browser on the network who is there (UDP 1434)."""
    found = []
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            pass
        s.settimeout(0.2)
        if targets is None:
            targets = ["255.255.255.255"] + subnet_broadcasts()
        for t in targets:
            try:
                s.sendto(b"\x02", (t, port))
            except OSError:
                pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = s.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            for n in parse_browser_reply(data, addr[0] if addr else None):
                if n not in found:
                    found.append(n)
    except Exception:
        pass
    finally:
        try:
            if s is not None:
                s.close()
        except Exception:
            pass
    return found


def candidates(current=None, network=True):
    """Server names worth trying, best first, no repeats."""
    names, seen = [], set()
    pool = ([current] if current else []) + local_instances() + list(COMMON) + \
        (network_instances() + tcp_sweep() if network else [])
    for n in pool:
        n = str(n or "").strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            names.append(n)
    return names


def try_server(config, server, timeout=3):
    """(ok, version_or_error): can DayBill log in to this server with the
    sign-in settings of `config` (Windows or SQL login)?"""
    try:
        import pyodbc
        from config.database import build_connection_string
        c = dict(config or {})
        c.update(server=server, database="master", timeout=timeout)
        cn = pyodbc.connect(build_connection_string(c), timeout=timeout)
        try:
            cur = cn.cursor()
            cur.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(40))")
            row = cur.fetchone()
        finally:
            cn.close()
        return True, str((row[0] if row else "") or "")
    except Exception as e:
        return False, str(e)[:160]


def find_servers(config, progress=None, network=True):
    """→ [(server, version)] of the SQL Servers that let us in."""
    ok = []
    for n in candidates((config or {}).get("server"), network):
        if progress:
            try:
                progress("Trying %s …" % n)
            except Exception:
                pass
        good, info = try_server(config, n)
        if good:
            ok.append((n, info))
    return ok
