# ============================================================
# DayBill ERP - Price Check (F8 in POS)
# ------------------------------------------------------------
# Scan any barcode (piece, box, carton, extra, scale label) or type a
# name: shows the product, the scanned unit's price WITH VAT, a live
# offer, stock, and every other unit with its own barcode + price.
# Nothing is added to the bill.
# ============================================================
import tkinter as tk
from tkinter import ttk
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg
from modules import barcode_resolver as BR


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


class PriceCheckWindow:
    def __init__(self, parent, on_close=None):
        C = self.C = cfg.theme()
        self.on_close = on_close
        self.win = tk.Toplevel(parent)
        self.win.title("Price Check")
        self.win.configure(bg="white")
        try:
            self.win.geometry("620x520")
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.close())
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        top = tk.Frame(self.win, bg=C["primary"]); top.pack(fill="x")
        tk.Label(top, text="🔎  Price Check", font=("Segoe UI", 14, "bold"), bg=C["primary"],
                 fg="white").pack(side="left", padx=14, pady=10)
        tk.Label(top, text="scan or type · Esc closes", font=("Segoe UI", 9), bg=C["primary"],
                 fg="#DBEAFE").pack(side="right", padx=14)
        self.v = tk.StringVar()
        self.e = tk.Entry(self.win, textvariable=self.v, font=("Segoe UI", 16), relief="solid", bd=1,
                          justify="center")
        self.e.pack(fill="x", padx=16, pady=(14, 6), ipady=6)
        self.e.bind("<Return>", self.lookup)
        self.e.bind("<KP_Enter>", self.lookup)
        self.name = tk.StringVar(); self.name_ar = tk.StringVar()
        self.price = tk.StringVar(); self.unit = tk.StringVar()
        self.offer = tk.StringVar(); self.info = tk.StringVar()
        tk.Label(self.win, textvariable=self.name, font=("Segoe UI", 16, "bold"), bg="white",
                 fg="#111827", wraplength=580).pack(pady=(8, 0))
        tk.Label(self.win, textvariable=self.name_ar, font=("Segoe UI", 13), bg="white",
                 fg="#374151").pack()
        tk.Label(self.win, textvariable=self.price, font=("Segoe UI", 34, "bold"), bg="white",
                 fg=C["primary"]).pack(pady=(4, 0))
        tk.Label(self.win, textvariable=self.unit, font=("Segoe UI", 11), bg="white",
                 fg="#4B5563").pack()
        tk.Label(self.win, textvariable=self.offer, font=("Segoe UI", 13, "bold"), bg="white",
                 fg="#DC2626").pack(pady=(4, 0))
        tk.Label(self.win, textvariable=self.info, font=("Segoe UI", 9), bg="white",
                 fg="#6B7280").pack(pady=(2, 6))
        wrap = tk.Frame(self.win, bg="white"); wrap.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.tree = ttk.Treeview(wrap, columns=("unit", "price", "barcode"), show="headings", height=4)
        for k, t, w, a in (("unit", "Unit", 160, "w"), ("price", "Price (VAT)", 120, "e"),
                           ("barcode", "Barcode", 200, "w")):
            self.tree.heading(k, text=t); self.tree.column(k, width=w, anchor=a)
        self.tree.pack(fill="both", expand=True)
        self.e.focus_set()
        self.hit = None

    def lookup(self, e=None):
        txt = self.v.get().strip()
        self.v.set("")
        if not txt:
            return "break"
        hit = BR.resolve(txt)
        if not hit:
            from modules.product_lookup import search_products
            found = search_products(txt, limit=1, active_only=True)
            if found:
                hit = BR.resolve(found[0].get("product_code") or "") or None
        self.show(hit, txt)
        return "break"

    def show(self, hit, typed=""):
        self.hit = hit
        self.tree.delete(*self.tree.get_children())
        if not hit:
            self.name.set("Not found: %s" % typed); self.name_ar.set("")
            self.price.set(""); self.unit.set(""); self.offer.set(""); self.info.set("")
            try:
                self.win.bell()
            except Exception:
                pass
            return
        p = hit["product"]
        rows = BR.label_rows(hit["product_id"])
        uid = (hit.get("unit") or {}).get("unit_id")
        me = next((r for r in rows if r.get("unit_id") == uid), rows[0] if rows else None)
        self.name.set(p.get("product_name_en") or "")
        self.name_ar.set(p.get("product_name_ar") or "")
        if me:
            now = me.get("offer_price") or me.get("price_vat")
            self.price.set("SAR %.2f" % _f(now))
            self.unit.set("per %s%s" % (me.get("unit_name") or "unit",
                                        (" (%g pcs)" % me["factor"]) if abs(_f(me.get("factor"), 1) - 1) > 1e-9 else ""))
            self.offer.set(("🏷 %s   (was SAR %.2f)" % (me["offer_text"], _f(me["old_price"])))
                           if me.get("offer_price") else ("🏷 " + me["offer_text"] if me.get("offer_text") else ""))
        stock = _f(p.get("stock_quantity"))
        stock_txt = "%g" % stock
        big = sorted([r for r in rows if _f(r.get("factor"), 1) > 1], key=lambda r: -_f(r.get("factor")))
        if big and stock > 0:                 # 13 PCs → "1 Box + 1 PCs"
            left, parts = stock, []
            for r in big:
                n = int(left // _f(r["factor"]))
                if n:
                    parts.append("%d %s" % (n, r.get("unit_name")))
                    left -= n * _f(r["factor"])
            base = next((r for r in rows if abs(_f(r.get("factor"), 1) - 1) < 1e-9), None)
            if left > 1e-9:
                parts.append("%g %s" % (round(left, 3), (base or {}).get("unit_name") or "pcs"))
            if parts:
                stock_txt = "%g (%s)" % (stock, " + ".join(parts))
        extra = ""
        if hit.get("via") == "scale":
            extra = " · scale label %.3f" % _f(hit.get("quantity"))
        self.info.set("Code %s · stock %s · incl. %g%% VAT%s" % (p.get("product_code") or "-", stock_txt,
                                                               _f((me or {}).get("vat_rate"), 15), extra))
        for r in rows:
            nm = (r.get("unit_name") or "-") + ((" ×%g" % r["factor"]) if abs(_f(r.get("factor"), 1) - 1) > 1e-9 else "")
            pr = r.get("offer_price") or r.get("price_vat")
            iid = self.tree.insert("", "end", values=(nm, "%.2f" % _f(pr), r.get("barcode_value") or "—"))
            if me is not None and r.get("unit_id") == me.get("unit_id"):
                self.tree.selection_set(iid)

    def close(self):
        try:
            self.win.destroy()
        finally:
            if self.on_close:
                try:
                    self.on_close()
                except Exception:
                    pass


def open_price_check(parent, on_close=None):
    return PriceCheckWindow(parent, on_close)
