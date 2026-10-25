# ============================================================
# DayBill ERP - ⭐ loyalty points of one customer (v6.9.2)
# Customers ▸ ⭐ Points: balance, what it is worth, every movement,
# and give / take points by hand (needs the right to edit customers).
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox

from config import settings as cfg
from config.database import db
from modules import loyalty
from modules import permissions as perm
from ui import close_guard


class LoyaltyDialog:
    def __init__(self, parent, customer_id, on_change=None):
        self.cid = customer_id
        self.on_change = on_change
        C = self.C = cfg.theme()
        row = db.fetchone("SELECT customer_code, customer_name_en FROM customers "
                          "WHERE customer_id=?", (customer_id,)) or {}
        self.name = "%s — %s" % (row.get("customer_code", ""), row.get("customer_name_en", ""))
        w = self.win = tk.Toplevel(parent)
        w.title("⭐ Loyalty points")
        w.geometry("620x460")
        w.configure(bg=C["content_bg"])
        w.transient(parent.winfo_toplevel())
        close_guard.bind_escape(w)          # Esc closes (like ✕)

        top = tk.Frame(w, bg=C["content_bg"])
        top.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(top, text=self.name, font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        self.bal_var = tk.StringVar()
        tk.Label(top, textvariable=self.bal_var, font=("Segoe UI", 11, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="right")
        self.rule_var = tk.StringVar()
        tk.Label(w, textvariable=self.rule_var, font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=14)

        cols = ("date", "what", "points", "sar")
        self.tree = ttk.Treeview(w, columns=cols, show="headings", height=12)
        for c, txt, wd, anc in (("date", "Date", 130, "w"), ("what", "What", 290, "w"),
                                ("points", "Points", 80, "e"), ("sar", "SAR", 80, "e")):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=wd, anchor=anc)
        self.tree.pack(fill="both", expand=True, padx=14, pady=6)

        adj = tk.Frame(w, bg=C["content_bg"])
        adj.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(adj, text="Points (+ give / − take)", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        self.pts_var = tk.StringVar()
        tk.Entry(adj, textvariable=self.pts_var, width=8, font=("Segoe UI", 10),
                 relief="solid", bd=1, justify="right").pack(side="left", padx=(4, 8))
        tk.Label(adj, text="Note", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.note_var = tk.StringVar()
        tk.Entry(adj, textvariable=self.note_var, width=22, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(4, 8))
        self.adj_btn = tk.Button(adj, text="Save", font=("Segoe UI", 9, "bold"),
                                 bg=C["primary"], fg="white", relief="flat", padx=12,
                                 cursor="hand2", command=self._adjust)
        self.adj_btn.pack(side="left")
        tk.Button(adj, text="Close", font=("Segoe UI", 9), relief="flat", padx=12,
                  cursor="hand2", command=w.destroy).pack(side="right")
        if not perm.allowed("customers", "edit"):
            self.adj_btn.configure(state="disabled")
        self._load()

    def _load(self):
        bal = loyalty.balance(self.cid)
        self.bal_var.set("⭐ %d points  =  %.2f SAR" % (bal, loyalty.value_of(bal) if bal > 0 else 0))
        self.rule_var.set("1 point per %.2f SAR spent · 1 point = %.2f SAR · at least %d points "
                          "per bill · loyalty is %s"
                          % (loyalty.sar_per_point(), loyalty.point_value(), loyalty.min_redeem(),
                             "ON" if loyalty.enabled() else "OFF (Settings ▸ Customer)"))
        self.tree.delete(*self.tree.get_children())
        for r in loyalty.history(self.cid):
            amt = r.get("amount")
            self.tree.insert("", "end", values=(
                str(r.get("entry_date") or "")[:16], r.get("note") or r.get("source_type") or "",
                "%+d" % int(r.get("points") or 0), "%.2f" % float(amt) if amt is not None else ""))

    def _adjust(self):
        try:
            pts = int(str(self.pts_var.get()).strip().replace("+", ""))
        except ValueError:
            messagebox.showwarning("Points", "Type a whole number, e.g. 50 or -20.",
                                   parent=self.win)
            return
        if not pts:
            return
        if pts < 0 and loyalty.balance(self.cid) + pts < 0:
            messagebox.showwarning("Points", "The customer does not have that many points.",
                                   parent=self.win)
            return
        note = self.note_var.get().strip() or ("Given by hand" if pts > 0 else "Taken by hand")
        if loyalty.adjust(self.cid, pts, note):
            try:
                from modules.doc_actions import audit
                audit("loyalty_adjust", "customer", self.cid, "%+d points · %s" % (pts, note))
            except Exception:
                pass
            self.pts_var.set("")
            self.note_var.set("")
            self._load()
            if self.on_change:
                try:
                    self.on_change()
                except Exception:
                    pass
