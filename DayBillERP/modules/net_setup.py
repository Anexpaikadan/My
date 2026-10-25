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
