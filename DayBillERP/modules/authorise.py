# ============================================================
# DayBill ERP - Authorisation (manager approval) (v7.18.0)
# Settings ▸ Users & Security: when a Sales Invoice is CONFIRMED and
#   • its total is above  auth_bill_over
#   • a line or the bill discount is more than  auth_disc_pct  %
#   • an item is sold below its cost  (auth_below_cost)
# a user who may not approve (Users & Rights ▸ Sales ▸ Approve) is asked
# for a manager's user name + password first. Every approval is in the
# Audit Log (who asked, who approved, why).
#
#   reasons(lines, total, bill_disc)  → [why, …]  ('' list = no approval)
#   approve(parent, reasons, what)    → True / False
# ============================================================
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def _cfg():
    from config import settings as cfg
    return cfg


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def enabled():
    try:
        return bool(_cfg().flag("auth_on", False))
    except Exception:
        return False


def reasons(lines, total=0.0, bill_disc=0.0, module="sales"):
    if not enabled():
        return []
    cfg = _cfg()
    out = []
    over = _f(cfg.get("auth_bill_over", 0))
    if over and _f(total) > over:
        out.append("Bill total %.2f is above %.2f" % (_f(total), over))
    pct = _f(cfg.get("auth_disc_pct", 0))
    gross = 0.0
    if pct:
        for ln in lines or []:
            q, p = _f(ln.get("quantity")), _f(ln.get("unit_price"))
            g = q * p
            gross += g
            d = _f(ln.get("discount_amount")) or g * _f(ln.get("discount_percent")) / 100.0
            if g > 0 and d / g * 100.0 > pct + 1e-6:
                out.append("%s: discount %.1f%% (limit %g%%)" % (
                    ln.get("product_name_en") or "item", d / g * 100.0, pct))
        if gross > 0 and _f(bill_disc) / gross * 100.0 > pct + 1e-6:
            out.append("Bill discount %.1f%% (limit %g%%)" % (_f(bill_disc) / gross * 100.0, pct))
    if cfg.flag("auth_below_cost", False):
        for ln in lines or []:
            cost = _f(ln.get("purchase_price"))
            q = _f(ln.get("quantity"))
            if q > 0 and cost > 0 and _f(ln.get("line_amount")) / q + 1e-6 < cost:
                out.append("%s sold below cost (%.2f < %.2f)" % (
                    ln.get("product_name_en") or "item", _f(ln.get("line_amount")) / q, cost))
    return out[:12]


def _may_approve(user_row, module="sales"):
    from modules import permissions as perm
    if str(user_row.get("username") or "").lower() == "admin":
        return True
    try:
        r = db.fetchone("SELECT r.role_id, r.role_name_en FROM users u JOIN roles r ON "
                        "r.role_id=u.role_id WHERE u.user_id=?", (user_row["user_id"],)) or {}
    except Exception:
        r = {}
    if str(r.get("role_name_en") or "").strip().lower() in getattr(perm, "FULL_ACCESS_ROLES", ()):
        return True
    if r.get("role_id"):
        g = perm.role_grants(r["role_id"])
        return "approve" in g.get(module, set())
    return False


def approve(parent, why, what="Sales invoice", module="sales"):
    """True when the current user may approve, or a manager approves now."""
    if not why:
        return True
    from modules import permissions as perm
    me = perm.session_user() or {}
    if perm.is_full_access() or perm.can(module, "approve"):
        _log(me, me, what, why)
        return True
    import tkinter as tk
    from tkinter import messagebox
    from config import settings as cfg
    C = cfg.theme()
    res = {"ok": False}
    w = tk.Toplevel(parent)
    w.title("Manager approval")
    w.configure(bg=C["card_bg"])
    w.resizable(False, False)
    try:
        w.transient(parent.winfo_toplevel())
    except Exception:
        pass
    band = tk.Frame(w, bg=C.get("warning", "#D97706"))
    band.pack(fill="x")
    tk.Label(band, text="🔑  Manager approval needed", font=("Segoe UI", 12, "bold"),
             bg=band["bg"], fg="white").pack(side="left", padx=12, pady=7)
    tk.Label(w, text="\n".join("• " + x for x in why), font=("Segoe UI", 9), bg=C["card_bg"],
             fg=C["text_primary"], justify="left").pack(anchor="w", padx=14, pady=(10, 6))
    f = tk.Frame(w, bg=C["card_bg"])
    f.pack(padx=14, pady=4)
    u_v, p_v, m_v = tk.StringVar(), tk.StringVar(), tk.StringVar()
    for r, (lbl, var, show) in enumerate((("Manager user", u_v, ""), ("Password", p_v, "●"))):
        tk.Label(f, text=lbl, font=("Segoe UI", 9, "bold"), bg=C["card_bg"]).grid(
            row=r, column=0, sticky="w", padx=(0, 8), pady=3)
        e = tk.Entry(f, textvariable=var, show=show, width=22, font=("Segoe UI", 11), relief="solid",
                     bd=1)
        e.grid(row=r, column=1, pady=3)
        if r == 0:
            first = e
    tk.Label(w, textvariable=m_v, font=("Segoe UI", 9), bg=C["card_bg"],
             fg=C.get("danger", "#DC2626")).pack()

    def ok(e=None):
        from ui.system_tools import _check
        u = _check(u_v.get().strip(), p_v.get())
        if not u:
            m_v.set("Wrong user or password")
            p_v.set("")
            return
        if not _may_approve(u, module):
            m_v.set("%s may not approve (Users & Rights ▸ Approve)" % u["username"])
            return
        _log(me, u, what, why)
        res["ok"] = True
        w.destroy()
    bf = tk.Frame(w, bg=C["card_bg"])
    bf.pack(fill="x", pady=10, padx=14)
    tk.Button(bf, text="Cancel", font=("Segoe UI", 9), relief="flat", padx=12,
              command=w.destroy).pack(side="right", padx=(6, 0))
    tk.Button(bf, text="✔ Approve", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
              relief="flat", padx=14, command=ok).pack(side="right")
    w.bind("<Return>", ok)
    w.bind("<Escape>", lambda e: w.destroy())
    try:
        w.grab_set()
    except Exception:
        pass
    first.focus_set()
    w.wait_window()
    if not res["ok"]:
        try:
            messagebox.showinfo("Manager approval", "Not saved — no approval.", parent=parent)
        except Exception:
            pass
    return res["ok"]


def _log(me, by, what, why):
    try:
        from modules import audit
        audit.log("approve", "authorisation", by.get("user_id") or 0,
                  ("%s · asked by %s · approved by %s · %s" % (
                      what, me.get("username") or "?", by.get("username") or "?",
                      "; ".join(why)))[:500])
    except Exception:
        pass
