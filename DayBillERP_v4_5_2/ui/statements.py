# ============================================================
# DayBill ERP - Customer & Supplier Statements
# ------------------------------------------------------------
# Account statement for one party over a date range: opening balance,
# every posted journal line touching their ledger sub-account with a
# running balance, and the closing balance. Built from the journal.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


class StatementView:
    def __init__(self, parent, side="customer"):
        C = cfg.theme()
        self.C = C
        self.side = side               # "customer" | "supplier"
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.parties = self._load_parties()
        self._build(C)

    def _load_parties(self):
        is_c = self.side == "customer"
        tbl = "customers" if is_c else "suppliers"
        idc = "customer_id" if is_c else "supplier_id"
        namec = "customer_name_en" if is_c else "supplier_name_en"
        codec = "customer_code" if is_c else "supplier_code"
        try:
            return db.fetchall(
                f"SELECT {idc} AS pid, {codec} AS code, {namec} AS name, "
                f"account_id FROM {tbl} WHERE is_active=1 ORDER BY {namec}") or []
        except Exception:
            return []

    def _build(self, C):
        title = "Customer Statement" if self.side == "customer" else "Supplier Statement"
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text=f"🧾  {title}", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        f = tk.Frame(self.frame, bg=C["content_bg"])
        f.pack(fill="x", padx=24, pady=(12, 0))
        tk.Label(f, text="Party", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.party_var = tk.StringVar()
        self.party_combo = ttk.Combobox(
            f, textvariable=self.party_var, width=34, state="readonly",
            values=[f"{p['code']} — {p['name']}" for p in self.parties])
        self.party_combo.pack(side="left", padx=(0, 12))
        today = date.today()
        self.from_var = tk.StringVar(value=cfg.fiscal_year_bounds(today)[0].strftime("%Y-%m-%d"))
        self.to_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        for lbl, var in [("From", self.from_var), ("To", self.to_var)]:
            tk.Label(f, text=lbl, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            tk.Entry(f, textvariable=var, width=11, font=("Segoe UI", 10),
                     relief="solid", bd=1).pack(side="left", padx=(0, 10))
        tk.Button(f, text="🔄 Run", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._load).pack(side="left")
        if self.side == "customer":
            tk.Button(f, text="🟢 WhatsApp", font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", padx=12, pady=5,
                      cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1,
                      command=self._whatsapp).pack(side="right", padx=(8, 0))
        tk.Button(f, text="📄 PDF", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=lambda: self._export("pdf")).pack(side="right")
        tk.Button(f, text="📥 Excel", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=lambda: self._export("excel")).pack(side="right",
                  padx=(0, 8))

        # balances strip
        s = tk.Frame(self.frame, bg=C["content_bg"])
        s.pack(fill="x", padx=24, pady=(10, 0))
        self.opening_var = tk.StringVar(value="0.00")
        self.closing_var = tk.StringVar(value="0.00")
        for lbl, var, col in [("Opening", self.opening_var, C["text_secondary"]),
                              ("Closing", self.closing_var, C["primary"])]:
            cell = tk.Frame(s, bg=C["card_bg"], highlightbackground=C["border"],
                            highlightthickness=1)
            cell.pack(side="left", padx=(0, 10))
            tk.Label(cell, text=lbl, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(padx=14, pady=(6, 0), anchor="w")
            tk.Label(cell, textvariable=var, font=("Segoe UI", 14, "bold"),
                     bg=C["card_bg"], fg=col).pack(padx=14, pady=(0, 6))
        # aging strip
        self.aging_frame = tk.Frame(s, bg=C["content_bg"])
        self.aging_frame.pack(side="left", padx=(16, 0))

        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=12)
        cols = ("date", "voucher", "narration", "debit", "credit", "balance")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for cid, txt, w, a in [("date", "Date", 95, "center"),
                               ("voucher", "Voucher", 120, "w"),
                               ("narration", "Narration", 320, "w"),
                               ("debit", "Debit", 110, "e"),
                               ("credit", "Credit", 110, "e"),
                               ("balance", "Balance", 120, "e")]:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=a)
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        if self.parties:
            self.party_combo.current(0)
            self._load()

    def _load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        sel = self.party_var.get()
        if not sel:
            return
        code = sel.split(" — ")[0]
        party = next((p for p in self.parties if p["code"] == code), None)
        if not party:
            return
        # Document-based statement (works for every party, whether or not
        # a GL account exists yet). Same engine as the pop-up statement.
        try:
            from ui.party_statement import build_statement
            data = build_statement(self.side, party["pid"],
                                   self.from_var.get(), self.to_var.get())
        except Exception as e:
            messagebox.showerror("Statement", str(e)[:160])
            return
        self._data = data
        self.opening_var.set(money(data["opening"]))
        self.tree.insert("", "end", values=(
            self.from_var.get(), "", "Opening balance", "", "",
            money(data["opening"])))
        for r in data["rows"]:
            self.tree.insert("", "end", values=(
                r["date"], r["ref"], r["doc"],
                money(r["debit"]) if r["debit"] else "",
                money(r["credit"]) if r["credit"] else "",
                money(r["balance"])))
        self.closing_var.set(money(data["closing"]))
        self.tree.insert("", "end", values=(
            self.to_var.get(), "", "▶ Closing balance",
            money(data["debit_total"]), money(data["credit_total"]),
            money(data["closing"])))
        self._render_aging(data["aging"])

    def _render_aging(self, ag):
        C = self.C
        for w in self.aging_frame.winfo_children():
            w.destroy()
        tk.Label(self.aging_frame, text="Aging", font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w")
        row = tk.Frame(self.aging_frame, bg=C["content_bg"]); row.pack()
        for label, key, col in [("Current", "current", "#16A34A"),
                                ("1-30", "b30", "#65A30D"),
                                ("31-60", "b60", "#CA8A04"),
                                ("61-90", "b90", "#EA580C"),
                                ("90+", "b90p", "#DC2626")]:
            v = ag.get(key, 0)
            cell = tk.Frame(row, bg=C["content_bg"]); cell.pack(side="left", padx=6)
            tk.Label(cell, text=label, font=("Segoe UI", 8), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack()
            tk.Label(cell, text=money(v), font=("Segoe UI", 10, "bold"),
                     bg=C["content_bg"],
                     fg=col if v > 0.005 else C["text_secondary"]).pack()

    def _whatsapp(self):
        code = self.party_var.get().split(" — ")[0]
        party = next((p for p in self.parties if p["code"] == code), None)
        if not party:
            messagebox.showinfo("WhatsApp", "Pick a customer first.")
            return
        try:
            from ui.whatsapp_send import send_document
            send_document(self.frame, "statement", party["pid"])
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:300])

    def _export(self, kind):
        data = getattr(self, "_data", None)
        if not data:
            messagebox.showinfo("Export", "Run a statement first.")
            return
        headers = ["Date", "Reference", "Document", "Debit", "Credit", "Balance"]
        body = [[self.from_var.get(), "", "Opening balance", "", "",
                 money(data["opening"])]]
        for r in data["rows"]:
            body.append([r["date"], r["ref"], r["doc"],
                         money(r["debit"]) if r["debit"] else "",
                         money(r["credit"]) if r["credit"] else "",
                         money(r["balance"])])
        body.append([self.to_var.get(), "", "Closing balance",
                     money(data["debit_total"]), money(data["credit_total"]),
                     money(data["closing"])])
        ptype = "Customer" if self.side == "customer" else "Supplier"
        name = f"{ptype}_Statement_{data['code'] or data['name']}".replace(" ", "_")
        title = f"{ptype} Statement — {data['name']} ({data['code']})"
        ag = data["aging"]
        summary = [
            ("Period", f"{self.from_var.get()} to {self.to_var.get()}"),
            ("Opening", money(data["opening"])),
            ("Closing", money(data["closing"])),
            ("Aging", f"Current {money(ag['current'])} · 1-30 {money(ag['b30'])} "
                      f"· 31-60 {money(ag['b60'])} · 61-90 {money(ag['b90'])} "
                      f"· 90+ {money(ag['b90p'])}"),
        ]
        try:
            if kind == "pdf":
                from modules.report_export import export_pdf
                export_pdf(self.frame, name, headers, body, title=title,
                           subtitle=f"{self.from_var.get()} to {self.to_var.get()}",
                           summary=summary,
                           col_align=["center","left","left","right","right","right"])
            else:
                from modules.report_export import export_excel
                export_excel(self.frame, name, headers, body, title=title,
                             summary=summary)
        except ImportError:
            messagebox.showerror("Export", "Install reportlab / openpyxl.")
        except Exception as e:
            messagebox.showerror("Export", str(e)[:200])


class CustomerStatementView(StatementView):
    def __init__(self, parent):
        super().__init__(parent, side="customer")


class SupplierStatementView(StatementView):
    def __init__(self, parent):
        super().__init__(parent, side="supplier")
