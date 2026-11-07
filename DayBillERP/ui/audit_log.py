# ============================================================
# DayBill ERP - Audit Log viewer
# (BillPOS conversion: surfaces the audit_logs table with filters)
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


class AuditLogView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._topbar(C)
        self._table(C)
        self._load()

    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="🛡  Audit Log", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        f = tk.Frame(self.frame, bg=C["content_bg"])
        f.pack(fill="x", padx=24, pady=(12, 0))
        today = date.today()
        self.from_var = tk.StringVar(value=today.replace(day=1).strftime("%Y-%m-%d"))
        self.to_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        self.module_var = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")

        def lab(txt):
            tk.Label(f, text=txt, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        lab("From")
        tk.Entry(f, textvariable=self.from_var, width=11, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 10))
        lab("To")
        tk.Entry(f, textvariable=self.to_var, width=11, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 10))
        lab("Module")
        mods = ["", "sales", "pos", "purchase", "vouchers", "payments",
                "products", "customers", "suppliers", "users", "settings",
                "accounting", "returns", "login"]
        ttk.Combobox(f, textvariable=self.module_var, values=mods, width=12,
                     state="readonly").pack(side="left", padx=(0, 10))
        lab("Search")
        tk.Entry(f, textvariable=self.search_var, width=16, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 10))
        tk.Button(f, text="🔍 Filter", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=12, pady=5,
                  cursor="hand2", command=self._load).pack(side="left")
        tk.Button(f, text="🖨  Print", font=("Segoe UI", 9, "bold"), bg="#16A085",
                  fg="white", relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self._export_pdf).pack(side="left", padx=(10, 0))
        tk.Button(f, text="📥  Excel", font=("Segoe UI", 9, "bold"), bg="#2E86AB",
                  fg="white", relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self._export_excel).pack(side="left", padx=(8, 0))
        self.count_var = tk.StringVar()
        tk.Label(f, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right")

    def _table(self, C):
        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=12)
        cols = ("time", "user", "action", "module", "ref", "details", "ws")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        heads = [("time", "Time", 130, "center"),
                 ("user", "User", 110, "w"),
                 ("action", "Action", 80, "center"),
                 ("module", "Module", 90, "center"),
                 ("ref", "Ref", 80, "center"),
                 ("details", "Details", 320, "w"),
                 ("ws", "Workstation", 110, "w")]
        for cid, txt, w, anc in heads:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=anc)
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

    def _load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        sql = ("SELECT TOP 500 al.created_at, al.action, al.module, al.ref_id, "
               "al.details, al.workstation, u.full_name_en "
               "FROM audit_logs al LEFT JOIN users u ON u.user_id = al.user_id "
               "WHERE CAST(al.created_at AS DATE) BETWEEN ? AND ?")
        params = [self.from_var.get(), self.to_var.get()]
        if self.module_var.get():
            sql += " AND al.module = ?"
            params.append(self.module_var.get())
        if self.search_var.get().strip():
            sql += " AND (al.details LIKE ? OR al.ref_id LIKE ?)"
            s = f"%{self.search_var.get().strip()}%"
            params += [s, s]
        sql += " ORDER BY al.id DESC"
        try:
            rows = db.fetchall(sql, tuple(params)) or []
        except Exception as e:
            messagebox.showerror(
                "Audit Log",
                "Could not read audit_logs. Run database/audit_log_patch.sql "
                "first.\n\n" + str(e)[:150])
            return
        for r in rows:
            ts = r["created_at"]
            tstxt = ts.strftime("%d/%m/%y %H:%M") if hasattr(ts, "strftime") else str(ts)[:16]
            self.tree.insert("", "end", values=(
                tstxt, r["full_name_en"] or "—", r["action"], r["module"],
                r["ref_id"] or "", r["details"] or "", r["workstation"] or ""))
        self.count_var.set(f"{len(rows)} events")

    def _audit_headers(self):
        return ["Time", "User", "Action", "Module", "Ref", "Details", "Workstation"]

    def _audit_subtitle(self):
        s = "From %s to %s" % (self.from_var.get(), self.to_var.get())
        if self.module_var.get():
            s += "   ·   Module: %s" % self.module_var.get()
        if self.search_var.get().strip():
            s += "   ·   Search: %s" % self.search_var.get().strip()
        return s

    def _export_excel(self):
        if not self.tree.get_children():
            messagebox.showinfo("Audit Log", "Nothing to export — run a filter first.")
            return
        from modules.doc_actions import export_tree_excel
        export_tree_excel(self.frame, self.tree, "AuditLog", self._audit_headers(),
                          title="Audit Log", summary=self._audit_subtitle())

    def _export_pdf(self):
        if not self.tree.get_children():
            messagebox.showinfo("Audit Log", "Nothing to print — run a filter first.")
            return
        from modules.doc_actions import export_tree_pdf
        export_tree_pdf(self.frame, self.tree, "AuditLog", self._audit_headers(),
                        title="Audit Log", subtitle=self._audit_subtitle(),
                        col_align=["center", "left", "center", "center",
                                   "center", "left", "left"])
