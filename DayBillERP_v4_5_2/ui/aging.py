# ============================================================
# DayBill ERP - Outstanding / Aging report
# ------------------------------------------------------------
# Who owes what. Two tabs:
#   Customers (receivable)  - balance of each customer's ledger account
#   Suppliers (payable)     - balance of each supplier's ledger account
# v5.26: one engine (modules/aging.py) — the balance always equals the
# Trial Balance / statement; receipts settled against bills close those
# bills, the rest is worked out first-in-first-out, against the payment terms (Not due / 1-30 / 31-60 / 61-90 / 90+ days
# overdue), advances get their own column. Double-click a party to see
# the bills that are still open.
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


BUCKETS = [("Not due", "not_due"), ("1-30", "b30"), ("31-60", "b60"),
           ("61-90", "b90"), ("90+", "b90p")]
COLS = [("code", "Code", 80, "w"), ("name", "{who}", 220, "w"), ("phone", "Phone", 110, "w"),
        ("terms", "Terms", 60, "e"), ("not_due", "Not due", 95, "e"), ("b30", "1-30", 90, "e"),
        ("b60", "31-60", 90, "e"), ("b90", "61-90", 90, "e"), ("b90p", "90+", 90, "e"),
        ("advance", "Advance", 90, "e"), ("balance", "Balance", 110, "e")]


class AgingView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._rows = {"customer": [], "supplier": []}
        self._topbar(C)
        self.cards = tk.Frame(self.frame, bg=C["content_bg"])
        self.cards.pack(fill="x", padx=24, pady=(10, 0))
        self.nb = ttk.Notebook(self.frame)
        self.nb.pack(fill="both", expand=True, padx=24, pady=12)
        self.cust_tab = tk.Frame(self.nb, bg=C["card_bg"])
        self.sup_tab = tk.Frame(self.nb, bg=C["card_bg"])
        self.nb.add(self.cust_tab, text="  Customers (Receivable)  ")
        self.nb.add(self.sup_tab, text="  Suppliers (Payable)  ")
        self.cust_tree = self._tree(self.cust_tab, "Customer", "customer")
        self.sup_tree = self._tree(self.sup_tab, "Supplier", "supplier")
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._cards())
        self._load()

    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="📊  Outstanding / Aging", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        self.asof_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        tk.Label(bar, text="As of", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(16, 4))
        e = tk.Entry(bar, textvariable=self.asof_var, width=12, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        e.pack(side="left", padx=(0, 8))
        try:
            from ui.datefield import enhance
            enhance(e, self.asof_var, on_pick=self._load)
        except Exception:
            pass
        e.bind("<Return>", lambda ev: self._load())
        tk.Label(bar, text="Search", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(8, 4))
        self.search_var = tk.StringVar()
        s = tk.Entry(bar, textvariable=self.search_var, width=18, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        s.pack(side="left", padx=(0, 8))
        self.search_var.trace_add("write", lambda *a: self._render())
        tk.Button(bar, text="🔄 Refresh", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._load).pack(side="left")
        tk.Button(bar, text="🖨  Print", font=("Segoe UI", 9, "bold"), bg="#16A085",
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._export_pdf).pack(side="right")
        tk.Button(bar, text="📥  Excel", font=("Segoe UI", 9, "bold"), bg="#2E86AB",
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._export_excel).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="📄 Open bills", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["primary"], relief="flat", padx=12, pady=6,
                  cursor="hand2", highlightthickness=1, highlightbackground=C["border"],
                  command=self._open_bills).pack(side="right", padx=(0, 8))

    def _side(self):
        try:
            cur = self.nb.select()
            if cur and self.nb.index(cur) == 1:
                return "supplier"
        except Exception:
            pass
        return "customer"

    def _active_aging(self):
        """The tree + labels for whichever tab (Receivable/Payable) is shown."""
        if self._side() == "supplier":
            return self.sup_tree, "Supplier", "Payable Aging", "AgingPayable"
        return self.cust_tree, "Customer", "Receivable Aging", "AgingReceivable"

    def _aging_headers(self, who):
        return [c[1].format(who=who) for c in COLS]

    def _export_rows(self, side):
        out = []
        for r in self._visible(side):
            out.append([r["code"], r["name"], r["phone"], str(r["terms"])]
                       + [money(r[k]) for _, k in BUCKETS]
                       + [money(r["advance"]), money(r["balance"])])
        t = self._totals(side)
        out.append(["", "TOTAL", "", ""] + [money(t[k]) for _, k in BUCKETS]
                   + [money(t["advance"]), money(t["balance"])])
        return out

    def _summary(self, side):
        t = self._totals(side)
        over = t["b30"] + t["b60"] + t["b90"] + t["b90p"]
        return [("As of", self.asof_var.get()), ("Balance", money(t["balance"])),
                ("Overdue", money(over)), ("Advances", money(t["advance"]))]

    def _export_excel(self, path=None):
        tree, who, title, name = self._active_aging()
        side = self._side()
        if not self._visible(side):
            if not path:
                messagebox.showinfo("Aging", "Nothing to export on this tab.")
            return None
        from modules.report_export import export_excel
        return export_excel(self.frame, name, self._aging_headers(who), self._export_rows(side),
                            title=title, summary=self._summary(side), path=path)

    def _export_pdf(self, path=None):
        tree, who, title, name = self._active_aging()
        side = self._side()
        if not self._visible(side):
            if not path:
                messagebox.showinfo("Aging", "Nothing to export on this tab.")
            return None
        from modules.report_export import export_pdf
        return export_pdf(self.frame, name, self._aging_headers(who), self._export_rows(side),
                          title=title, subtitle="As of %s" % self.asof_var.get(),
                          summary=self._summary(side)[1:], path=path)

    def _tree(self, parent, who, side):
        cols = tuple(c[0] for c in COLS)
        tree = ttk.Treeview(parent, columns=cols, show="headings")
        for cid, txt, w, a in COLS:
            tree.heading(cid, text=txt.format(who=who))
            tree.column(cid, width=w, anchor=a, stretch=True,
                        minwidth=120 if cid == "name" else 55)
        ysb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        try:
            from ui.ui_kit import fit_columns
            fit_columns(tree)
        except Exception:
            pass
        tree.tag_configure("total", font=("Segoe UI", 10, "bold"), background="#EEF2F8")
        tree.tag_configure("over", foreground="#B91C1C")
        tree.tag_configure("adv", foreground="#047857")
        tree.bind("<Double-1>", lambda e: self._open_bills())
        tree.bind("<Return>", lambda e: self._open_bills())
        return tree

    def _load(self):
        asof = self.asof_var.get().strip() or date.today().isoformat()
        try:
            from modules import aging as AG
            self._rows["customer"] = AG.party_aging("customer", asof)
            self._rows["supplier"] = AG.party_aging("supplier", asof)
        except Exception as e:
            messagebox.showerror("Aging", str(e)[:200])
            return
        self._render()

    def _visible(self, side):
        q = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        rows = self._rows.get(side, [])
        if q:
            rows = [r for r in rows if q in (r["name"] + " " + r["code"] + " " + r["phone"]).lower()]
        return rows

    def _totals(self, side):
        from modules import aging as AG
        return AG.totals(self._visible(side))

    def _render(self):
        for side, tree in (("customer", self.cust_tree), ("supplier", self.sup_tree)):
            for i in tree.get_children():
                tree.delete(i)
            for n, r in enumerate(self._visible(side)):
                tag = ("adv",) if r["balance"] < 0 else \
                    (("over",) if r["b60"] + r["b90"] + r["b90p"] > 0.005 else ())
                tree.insert("", "end", iid="p%d" % n, values=(
                    r["code"], r["name"], r["phone"], r["terms"] or "",
                    *[money(r[k]) for _, k in BUCKETS],
                    money(r["advance"]) if r["advance"] else "",
                    money(r["balance"])), tags=tag)
            t = self._totals(side)
            tree.insert("", "end", iid="total", values=(
                "", "▶ TOTAL", "", "", *[money(t[k]) for _, k in BUCKETS],
                money(t["advance"]), money(t["balance"])), tags=("total",))
        self._cards()

    def _cards(self):
        C = self.C
        for w in self.cards.winfo_children():
            w.destroy()
        side = self._side()
        t = self._totals(side)
        rows = self._visible(side)
        over = t["b30"] + t["b60"] + t["b90"] + t["b90p"]
        who = "Customers owe you" if side == "customer" else "You owe suppliers"
        for label, val, col in ((who, t["balance"] + t["advance"], C["primary"]),
                                ("Not yet due", t["not_due"], "#16A34A"),
                                ("Overdue", over, "#B91C1C"),
                                ("Over 90 days", t["b90p"], "#7F1D1D"),
                                ("Advances", t["advance"], "#047857"),
                                ("Parties", len(rows), C["text_primary"])):
            card = tk.Frame(self.cards, bg=C["card_bg"], highlightthickness=1,
                            highlightbackground=C["border"])
            card.pack(side="left", padx=(0, 10))
            tk.Label(card, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(6, 0))
            tk.Label(card, text=money(val) if label != "Parties" else str(val),
                     font=("Segoe UI", 13, "bold"), bg=C["card_bg"], fg=col).pack(
                         anchor="w", padx=12, pady=(0, 6))

    def _selected_row(self):
        side = self._side()
        tree = self.sup_tree if side == "supplier" else self.cust_tree
        sel = tree.selection() or ((tree.focus(),) if tree.focus() else ())
        if not sel or sel[0] == "total":
            return side, None
        try:
            return side, self._visible(side)[int(sel[0][1:])]
        except Exception:
            return side, None

    def _open_bills(self):
        """The bills that make up the selected party's balance."""
        side, r = self._selected_row()
        if r is None:
            messagebox.showinfo("Open bills", "Pick a customer or supplier first.")
            return
        C = self.C
        win = tk.Toplevel(self.frame)
        win.title(f"Open bills — {r['name']}")
        win.geometry("760x420")
        win.configure(bg=C["content_bg"])
        win.bind("<Escape>", lambda e: win.destroy())
        tk.Label(win, text=f"{r['name']}  ·  balance {money(r['balance'])}"
                 + (f"  ·  advance {money(r['advance'])}" if r["advance"] else ""),
                 font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=14, pady=(12, 6))
        cols = (("date", "Date", 90), ("type", "Document", 140), ("ref", "Ref", 120),
                ("due", "Due", 90), ("over", "Days overdue", 90), ("amount", "Amount", 100),
                ("open", "Still open", 100))
        tv = ttk.Treeview(win, columns=[c[0] for c in cols], show="headings", height=12)
        for k, t_, w in cols:
            tv.heading(k, text=t_)
            tv.column(k, width=w, anchor="e" if k in ("over", "amount", "open") else "w")
        tv.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        for it in r["items"]:
            tv.insert("", "end", values=(it["date"], it["type"], it["ref"], it["due"],
                                         max(0, it["overdue"]) or "", money(it["amount"]),
                                         money(it["open"])))
        if not r["items"]:
            tv.insert("", "end", values=("", "Nothing open — advance paid", "", "", "", "",
                                         money(0)))
        bar = tk.Frame(win, bg=C["content_bg"])
        bar.pack(fill="x", padx=14, pady=(0, 12))
        if r.get("id"):
            def stmt():
                try:
                    from ui.party_statement import StatementDialog
                    StatementDialog(self.frame, side, r["id"])
                except Exception as e:
                    messagebox.showerror("Statement", str(e)[:200])
            tk.Button(bar, text="📄 Full statement", font=("Segoe UI", 9, "bold"),
                      bg=C["primary"], fg="white", relief="flat", padx=12, pady=5,
                      cursor="hand2", command=stmt).pack(side="left")
        tk.Button(bar, text="Close", font=("Segoe UI", 9), relief="flat", padx=12, pady=5,
                  command=win.destroy).pack(side="right")
        self._bills_win = win
        return win
