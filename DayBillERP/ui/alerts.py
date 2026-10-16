# ============================================================
# DayBill ERP - Start-up alerts (Settings ▸ Alerts)
# ------------------------------------------------------------
# When the app opens it shows, in one small window:
#   • products at / below their reorder level      (notify_low_stock)
#   • customer invoices overdue or due within N days (notify_payment_due)
# Each list has a button that opens the full report. Automatic
# backups report success / failure with a toast   (notify_backup).
# ============================================================

import os
import sys
import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


def low_stock_items(limit=200):
    """[(code, name, stock, level)] — per-product reorder level first,
    else Settings ▸ Inventory ▸ Low Stock Alert Level."""
    try:
        glob = float(cfg.get("inv_low_stock_level", 0) or 0)
    except Exception:
        glob = 0.0
    try:
        rows = db.fetchall(
            "SELECT product_code, product_name_en, ISNULL(stock_quantity,0) AS stock, "
            "ISNULL(NULLIF(reorder_level,0), ?) AS lvl FROM products "
            "WHERE is_active=1 AND ISNULL(track_inventory,1)=1 "
            "AND ISNULL(stock_quantity,0) <= ISNULL(NULLIF(reorder_level,0), ?) "
            "ORDER BY stock_quantity, product_name_en", (glob, glob)) or []
    except Exception:
        return []
    out = []
    for r in rows[:limit]:
        lvl = float(r.get("lvl") or 0)
        stock = float(r.get("stock") or 0)
        if lvl <= 0 and stock > 0:
            continue                        # no level set anywhere
        out.append((r.get("product_code") or "", r.get("product_name_en") or "",
                    stock, lvl))
    return out


def due_invoices(days=None, limit=300):
    """[(number, customer, due date, balance, days overdue)] for confirmed
    customer invoices with money still owed, due within `days` days."""
    if days is None:
        try:
            days = int(float(cfg.get("notify_payment_due_days", 3) or 0))
        except Exception:
            days = 3
    upto = date.today() + timedelta(days=max(0, days))
    try:
        rows = db.fetchall(
            "SELECT si.invoice_number, si.invoice_date, si.due_date, "
            "ISNULL(si.total_amount,0) AS total, ISNULL(si.paid_amount,0) AS paid, "
            "c.customer_name_en AS customer, c.customer_code "
            "FROM sales_invoices si LEFT JOIN customers c ON c.customer_id=si.customer_id "
            "WHERE si.invoice_status='confirmed' "
            "AND ISNULL(si.total_amount,0) - ISNULL(si.paid_amount,0) > 0.009 "
            "ORDER BY ISNULL(si.due_date, si.invoice_date), si.invoice_id") or []
    except Exception:
        return []
    out = []
    today = date.today()
    for r in rows:
        due = _d(r.get("due_date")) or _d(r.get("invoice_date"))
        if due is None or due > upto:
            continue
        out.append((r.get("invoice_number") or "", r.get("customer") or "",
                    due, float(r.get("total") or 0) - float(r.get("paid") or 0),
                    (today - due).days))
        if len(out) >= limit:
            break
    return out


def _d(v):
    if v is None or v == "":
        return None
    if hasattr(v, "year"):
        return date(v.year, v.month, v.day)
    try:
        y, m, dd = str(v)[:10].split("-")
        return date(int(y), int(m), int(dd))
    except Exception:
        return None


def show_startup_alerts(root, force=False, open_report=None):
    """Show the alerts window. Returns how many alert rows were shown
    (0 = nothing to show, no window)."""
    lows = low_stock_items() if (force or cfg.flag("notify_low_stock", True)) else []
    dues = due_invoices() if (force or cfg.flag("notify_payment_due", True)) else []
    if not lows and not dues:
        return 0
    C = cfg.theme()
    win = tk.Toplevel(root)
    win.title("Today's alerts")
    win.configure(bg=C["content_bg"])
    win.geometry("760x560")
    try:
        win.transient(root)
    except Exception:
        pass
    win.bind("<Escape>", lambda e: win.destroy())
    head = tk.Frame(win, bg=C["primary"]); head.pack(fill="x")
    tk.Label(head, text="🔔  Needs your attention today", font=("Segoe UI", 13, "bold"),
             bg=C["primary"], fg="white").pack(side="left", padx=16, pady=10)
    foot = tk.Frame(win, bg=C["card_bg"]); foot.pack(side="bottom", fill="x")
    tk.Label(foot, text="Turn these off in Settings ▸ Alerts", font=("Segoe UI", 8),
             bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=14)
    tk.Button(foot, text="Close", font=("Segoe UI", 10), relief="flat", padx=16, pady=6,
              bg=C["primary"], fg="white", cursor="hand2",
              command=win.destroy).pack(side="right", padx=12, pady=8)
    body = tk.Frame(win, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=14, pady=8)

    def block(title, cols, widths, rows, anchor_right, btn_text, report_id):
        box = tk.Frame(body, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        box.pack(fill="both", expand=True, pady=6)
        top = tk.Frame(box, bg=C["card_bg"]); top.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(top, text=title, font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(side="left")
        if open_report:
            tk.Button(top, text=btn_text, font=("Segoe UI", 9, "bold"), relief="flat",
                      bg=C["primary_light"], fg=C["primary"], padx=10, pady=3, cursor="hand2",
                      command=lambda: (win.destroy(), open_report(report_id))).pack(side="right")
        frame = tk.Frame(box, bg=C["card_bg"]); frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        tv = ttk.Treeview(frame, columns=cols, show="headings", height=min(8, max(3, len(rows))))
        for c, w in zip(cols, widths):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="e" if c in anchor_right else "w", stretch=(c == cols[1]))
        sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); tv.pack(fill="both", expand=True)
        for r in rows:
            tv.insert("", "end", values=r)
        return tv

    win.low_tree = win.due_tree = None
    if lows:
        win.low_tree = block(f"📦  {len(lows)} product(s) at or below reorder level",
                             ("Code", "Product", "Stock", "Reorder level"), (100, 320, 90, 125),
                             [(a, b, f"{c:g}", f"{d:g}") for a, b, c, d in lows],
                             ("Stock", "Reorder level"), "Open Low Stock report", "low_stock")
    if dues:
        total = sum(r[3] for r in dues)
        win.due_tree = block(f"💰  {len(dues)} customer invoice(s) due — {total:,.2f} to collect",
                             ("Invoice", "Customer", "Due", "Balance", "Status"),
                             (120, 260, 110, 110, 120),
                             [(a, b, cfg.fmt_date(c), f"{d:,.2f}",
                               (f"{e} days late" if e > 0 else ("due today" if e == 0
                                                                 else f"in {-e} days")))
                              for a, b, c, d, e in dues],
                             ("Balance",), "Open Receivables", "receivables")
    try:
        root._daybill_alerts = win
    except Exception:
        pass
    return len(lows) + len(dues)


def backup_notice(root, ok, info):
    """Settings ▸ Alerts ▸ backup message (failures are always shown)."""
    if ok and not cfg.flag("notify_backup", True):
        return
    try:
        from ui.ui_polish import toast
        toast(root, ("✅  Automatic backup done" if ok else "⚠  Automatic backup FAILED: ")
              + ("" if ok else str(info)[:80]), kind="success" if ok else "danger",
              ms=4000 if ok else 9000)
    except Exception:
        pass
