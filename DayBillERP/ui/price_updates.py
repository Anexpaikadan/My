# ============================================================
# DayBill ERP - 📈 Price Updates (cost went up)  v6.4
# ------------------------------------------------------------
# Every item whose last purchase cost more than the one before (and whose
# price was not changed since): cost before → now, the margin you had,
# the margin now, and a NEW price that keeps the old margin (rounded up
# to a nice price; Box / Carton prices move by the same ratio).
# Tick → ✔ Apply: prices saved, shelf labels wait in Price Change Labels.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from config import settings as cfg


def _m(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


class PriceUpdatesView:
    def __init__(self, parent):
        from modules import price_update as PU
        self.PU = PU
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.parent = parent
        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(top, text="📈  Price Updates", font=("Segoe UI", 16, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        tk.Label(top, text="cost went up ≥ %g %% · new price keeps your old margin · rounded up to %s"
                 % (PU.alert_pct(), PU.rounding()),
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left", padx=12)
        tk.Button(top, text="🔄  Refresh", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=14, pady=5, cursor="hand2", command=self.refresh).pack(side="right")
        wrap = tk.Frame(self.frame, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(4, 6))
        cols = [("tick", "✓", 30, "center"), ("name", "Product", 180, "w"),
                ("cost", "Cost per piece", 110, "e"), ("rise", "Up", 55, "e"),
                ("price", "Price now", 70, "e"), ("new", "New price ✎", 75, "e"),
                ("margin", "Margin now → new", 120, "center"),
                ("units", "Box / other units", 150, "w")]
        self.tv = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for k, t_, w, a in cols:
            self.tv.heading(k, text=t_)
            self.tv.column(k, width=w, anchor=a)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tv.pack(fill="both", expand=True)
        self.tv.tag_configure("loss", foreground=C["danger"])
        self.tv.bind("<Button-1>", self._click, add="+")
        self.tv.bind("<Double-1>", self._edit)
        self.tv.bind("<space>", lambda e: ([self._flip(i) for i in self.tv.selection()], "break")[1])
        bot = tk.Frame(self.frame, bg=C["content_bg"]); bot.pack(fill="x", padx=16, pady=(0, 12))
        self.info = tk.StringVar()
        tk.Label(bot, textvariable=self.info, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        tk.Button(bot, text="💲  Price Change Labels", font=("Segoe UI", 9), bg=C["card_bg"], relief="flat",
                  padx=12, pady=6, highlightthickness=1, highlightbackground=C["border"], cursor="hand2",
                  command=self._labels).pack(side="right")
        tk.Button(bot, text="✔  Apply ticked prices", font=("Segoe UI", 10, "bold"), bg=C["success"],
                  fg="white", relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self.apply).pack(side="right", padx=6)
        self.refresh()

    def refresh(self):
        try:
            self.rows = self.PU.suggestions()
        except Exception as e:                      # never block the screen
            print("[DayBill] price updates:", e)
            self.rows = []
        self.tick = {r["product_id"]: True for r in self.rows}
        self._fill()

    def _fill(self):
        tv = self.tv
        tv.delete(*tv.get_children())
        for r in self.rows:
            units = ",  ".join("%s %s → %s" % (u["unit"], _m(u["price"]), _m(u["suggested"]))
                               for u in r["units"] if abs(u["factor"] - 1) > 1e-9 and u["price"] > 0)
            tv.insert("", "end", iid=str(r["product_id"]), tags=("loss",) if r["margin_now"] < 0 else (),
                      values=("☑" if self.tick.get(r["product_id"]) else "☐", r["name"],
                              "%s → %s" % (_m(r["old_cost"]), _m(r["new_cost"])), "+%.1f%%" % r["rise_pct"],
                              _m(r["price"]), _m(r["suggested"]),
                              "%.1f%% → %.1f%%" % (r["margin_now"], r["margin_after"]), units))
        n = sum(1 for v in self.tick.values() if v)
        self.info.set("%d item(s) cost more now; %d ticked. Double-click a new price to change it."
                      % (len(self.rows), n) if self.rows else "✔ No cost went up since the last price change.")

    def _flip(self, iid):
        pid = int(iid)
        self.tick[pid] = not self.tick.get(pid)
        vals = list(self.tv.item(iid, "values"))
        vals[0] = "☑" if self.tick[pid] else "☐"
        self.tv.item(iid, values=vals)

    def _click(self, e):
        if self.tv.identify_column(e.x) == "#1":
            row = self.tv.identify_row(e.y)
            if row:
                self._flip(row)
                return "break"

    def _edit(self, e=None):
        sel = self.tv.selection()
        if not sel:
            return
        r = next((x for x in self.rows if x["product_id"] == int(sel[0])), None)
        if not r:
            return
        v = simpledialog.askfloat("New price", "New selling price of %s (now %s):" % (r["name"], _m(r["price"])),
                                  initialvalue=r["suggested"], minvalue=0.01, parent=self.frame)
        if v:
            ratio = v / r["price"] if r["price"] else 1.0
            r["suggested"] = round(v, 2)
            for u in r["units"]:
                if u["price"] > 0 and abs(u["factor"] - 1) > 1e-9:
                    u["suggested"] = self.PU.nice(u["price"] * ratio)
                elif abs(u["factor"] - 1) < 1e-9:
                    u["suggested"] = round(v, 2)
            self._fill()

    def apply(self, ask=True):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return 0
        rows = [r for r in self.rows if self.tick.get(r["product_id"])]
        if not rows:
            messagebox.showinfo("Price Updates", "Tick at least one item.", parent=self.frame)
            return 0
        if ask and not messagebox.askyesno("Price Updates", "Save the new price of %d item(s)?\n\nThe "
                                           "shelf labels will wait in Price Change Labels." % len(rows),
                                           parent=self.frame):
            return 0
        try:
            n = self.PU.apply(rows)
        except Exception as e:
            messagebox.showerror("Price Updates", str(e)[:300], parent=self.frame)
            return 0
        self.refresh()
        try:
            from ui.ui_polish import toast
            toast(self.frame.winfo_toplevel(), "✔ %d price(s) saved — labels in Price Change Labels" % n)
        except Exception:
            pass
        return n

    def _labels(self):
        try:
            from ui import main_window as mw
            if getattr(mw, "APP", None):
                mw.APP._load_module("price_labels")
        except Exception:
            pass
