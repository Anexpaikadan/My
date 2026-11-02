# ============================================================
# DayBill ERP - Bank Reconciliation page (Accounts)  v6.0
# ------------------------------------------------------------
# Account + statement date + statement balance → Load. Tick the lines
# that are on the statement (Space / double-click / "Tick all up to");
# Finish when the difference is 0.00.
# v6.9.3: Load / tick = accounts.edit · Finish and Undo = accounts.approve
# (both written to the Audit Log).
# ============================================================
import tkinter as tk
from tkinter import messagebox
from datetime import date

from modules import bank_rec as BR
from ui import danger
from ui import v6_kit as K


def _allowed(action, parent):
    """accounts.<action> with the usual 'not allowed' message."""
    try:
        from modules import permissions as perm
        return bool(perm.allowed("accounts", action, parent=parent))
    except Exception:
        return False


class BankRecView:
    def __init__(self, parent):
        self.page = K.Page(parent, "🏦  Bank Reconciliation",
                           "Match the books with the bank statement: tick every line that is on the "
                           "statement. When the difference is 0.00, Finish. Lines left over are "
                           "cheques not cashed yet, deposits in transit — or a bank charge to post.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.rec_id = None
        if not BR.ready():
            self.page.say("⚠ Needs the v6.0 database update — Updates ▸ Apply All Updates.", ok=False)
            return
        top = K.card(self.page.body, C, fill="x")
        r = tk.Frame(top, bg=C["card_bg"]); r.pack(fill="x", padx=10, pady=8)
        self.accs = BR.bank_accounts()
        self.acc_v = tk.StringVar(value=self.accs[0][1] if self.accs else "")
        K.combo(r, C, "Bank account", self.acc_v, [a[1] for a in self.accs], 30)
        self.date_v = tk.StringVar(value=date.today().isoformat())
        K.date_entry(r, C, "Statement date", self.date_v)
        self.bal_v = tk.StringVar()
        K.entry(r, C, "Statement closing balance *", self.bal_v, 14, justify="right")
        K.button(r, C, "Load", self.load, primary=True).pack_configure(pady=(14, 0))
        K.button(r, C, "↶ Undo last finished", self._undo).pack_configure(pady=(14, 0))
        fig = tk.Frame(self.page.body, bg=C["content_bg"]); fig.pack(fill="x", pady=(8, 4))
        self.fig_vars = {}
        for key, lbl in (("opening", "Last agreed balance"), ("ticked", "Ticked lines"),
                         ("cleared", "Cleared balance"), ("statement", "Statement balance"),
                         ("difference", "Difference"), ("book", "Book balance")):
            f = tk.Frame(fig, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
            f.pack(side="left", padx=(0, 8), fill="x", expand=True)
            tk.Label(f, text=lbl, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=10, pady=(6, 0))
            v = tk.StringVar(value="—")
            l = tk.Label(f, textvariable=v, font=("Segoe UI", 14, "bold"), bg=C["card_bg"],
                         fg=C["text_primary"])
            l.pack(anchor="w", padx=10, pady=(0, 6))
            self.fig_vars[key] = (v, l)
        bar = tk.Frame(self.page.body, bg=C["content_bg"]); bar.pack(fill="x")
        K.button(bar, C, "✔ Tick selected", lambda: self._tick(True))
        K.button(bar, C, "✖ Untick selected", lambda: self._tick(False))
        K.button(bar, C, "✔ Tick all", self._tick_all)
        self.fin_btn = K.button(bar, C, "🏁 Finish", self._finish, primary=True, side="right")
        self.tree = K.tree(self.page.body, [
            ("t", "✓", 36, "center"), ("date", "Date", 90, "center"), ("jv", "Voucher", 110, "w"),
            ("ref", "Reference", 120, "w"), ("desc", "Description", 300, "w"),
            ("in", "Money in", 110, "e"), ("out", "Money out", 110, "e")], height=16)
        self.tree.configure(selectmode="extended")
        self.tree.tag_configure("on", background="#ECFDF3")
        self.tree.bind("<Double-1>", lambda e: self._toggle_row())
        self.tree.bind("<space>", lambda e: (self._toggle_row(), "break")[1])

    def _acc(self):
        return next((a for a, l in self.accs if l == self.acc_v.get()), None)

    def load(self):
        acc = self._acc()
        if not acc:
            self.page.say("Choose the bank account.", ok=False)
            return
        if not _allowed("edit", self.frame):         # it starts / opens a draft
            return
        bal = K.num(self.bal_v)
        if bal is None:
            d = BR.draft(acc)
            if d:
                bal = float(d.get("statement_balance") or 0)
                self.bal_v.set("%.2f" % bal)
            else:
                self.page.say("Type the closing balance printed on the bank statement.", ok=False)
                return
        self.rec_id = BR.start(acc, self.date_v.get(), bal)
        self._fill()

    def _fill(self):
        if not self.rec_id:
            return
        acc = self._acc()
        self.tree.delete(*self.tree.get_children())
        for ln in BR.lines(acc, self.date_v.get(), self.rec_id):
            a = ln["amount"]
            self.tree.insert("", "end", iid=str(ln["line_id"]), tags=("on",) if ln["ticked"] else (),
                             values=("✔" if ln["ticked"] else "", str(ln["entry_date"])[:10],
                                     ln.get("journal_number") or "", ln.get("reference") or "",
                                     (ln.get("description_en") or ln.get("description") or "")[:80],
                                     K.money(a) if a > 0 else "", K.money(-a) if a < 0 else ""))
        f = BR.figures(self.rec_id)
        for k, (v, l) in self.fig_vars.items():
            v.set(K.money(f.get(k)))
            if k == "difference":
                l.configure(fg="#16A34A" if abs(f.get(k, 1)) < 0.005 else "#DC2626")
        self.page.say("Difference %s — %s" % (K.money(f["difference"]),
                                             "ready to Finish ✓" if abs(f["difference"]) < 0.005
                                             else "tick the lines that are on the statement"),
                      ok=abs(f["difference"]) < 0.005)

    def _tick(self, on):
        if not self.rec_id or not _allowed("edit", self.frame):
            return
        BR.tick(self.rec_id, self.tree.selection(), on)
        self._fill()

    def _toggle_row(self):
        sel = self.tree.selection()
        if not sel or not self.rec_id or not _allowed("edit", self.frame):
            return
        on = not bool(self.tree.set(sel[0], "t"))
        BR.tick(self.rec_id, sel, on)
        self._fill()

    def _tick_all(self):
        if self.rec_id and _allowed("edit", self.frame):
            BR.tick(self.rec_id, self.tree.get_children(), True)
            self._fill()

    def _finish(self):
        if not self.rec_id or not _allowed("approve", self.frame):
            return
        rec_id = self.rec_id
        ok, msg = BR.finish(rec_id)
        self.page.say(msg, ok=ok)
        if ok:
            danger.audit("finish", "bank_rec", rec_id, "Bank reconciliation finished: %s · %s"
                         % (self.acc_v.get(), self.date_v.get()))
            self.rec_id = None
            self.tree.delete(*self.tree.get_children())
            self.bal_v.set("")

    def _undo(self):
        acc = self._acc()
        if not acc or not _allowed("approve", self.frame):
            return
        if not messagebox.askyesno("Undo", "Reopen the last finished reconciliation of this "
                                   "account?", parent=self.frame):
            return
        ok, msg = BR.undo_last(acc)
        self.page.say(msg, ok=ok)
        if ok:
            danger.audit("undo", "bank_rec", None, "%s — %s" % (self.acc_v.get(), msg))
