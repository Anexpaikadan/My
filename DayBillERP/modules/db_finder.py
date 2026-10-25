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


def parse_browser_reply(data):
    """The SQL Server Browser's answer → ['PC\\INSTANCE', …]."""
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
            if name not in out:
                out.append(name)
    return out


def network_instances(timeout=1.5, targets=("255.255.255.255",), port=1434):
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
        for t in targets:
            try:
                s.sendto(b"\x02", (t, port))
            except OSError:
                pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, _addr = s.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            for n in parse_browser_reply(data):
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
        (network_instances() if network else [])
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
