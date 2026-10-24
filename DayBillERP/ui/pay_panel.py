# ============================================================
# DayBill ERP - payment area of a document (v7.9)
# ------------------------------------------------------------
# Purchase, Sales Return and Purchase Return (the Sales window keeps its
# Cash / Card boxes, each with its account): how much was paid, and from
# / into WHICH cash or bank account — every cash and bank account of the
# chart is in the list (Main cash, Petty cash, each bank …). More than one
# account may be used. What is not paid stays on the party's account:
#
#   Total 200.00 · Paid 100.00 · On account 100.00
#
# The walk-in party (Cash Customer / Cash Supplier) has no account of its
# own, so it must be paid in full (ok_for_party() says why not).
#
#   p = PayPanel(parent, C, get_total, on_change=None, title="Paid from")
#   p.set_auto(method)       payment method chosen elsewhere (cash / bank /
#                            credit) → the panel follows it until typed in
#   p.rows()                 [{method, account_id, amount}] (amount > 0)
#   p.paid() / p.on_account() / p.manual
#   p.set_rows(rows)         a saved document
# ============================================================
import tkinter as tk
from tkinter import ttk


def money_accounts():
    try:
        from modules import multi_voucher as mv
        return mv.money_accounts()
    except Exception:
        return []


def _f(v):
    try:
        return round(float(str(v).replace(",", "") or 0), 2)
    except (TypeError, ValueError):
        return 0.0


class PayPanel:
    MAX_ROWS = 4

    def __init__(self, parent, C, get_total, on_change=None, title="Paid from", state="normal"):
        self.C, self.get_total, self.on_change = C, get_total, on_change
        self.state = state
        self.accounts = money_accounts()
        self.labels = ["%s · %s" % (a["code"], a["name"]) for a in self.accounts]
        self.by_label = {l: a for l, a in zip(self.labels, self.accounts)}
        self.manual = False
        self._busy = False
        self.frame = tk.Frame(parent, bg=C["card_bg"], highlightthickness=1,
                              highlightbackground=C.get("border", "#E2E6EE"))
        self.frame.pack(fill="x", side="bottom")
        inner = tk.Frame(self.frame, bg=C["card_bg"])
        inner.pack(fill="x", padx=10, pady=4)
        tk.Label(inner, text="💳 " + title.upper(), font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left", padx=(0, 8))
        self.rows_box = tk.Frame(inner, bg=C["card_bg"])
        self.rows_box.pack(side="left")
        self.add_btn = tk.Button(inner, text="＋ account", font=("Segoe UI", 8), relief="flat",
                                 bg=C["content_bg"], cursor="hand2", command=self.add_row)
        self.add_btn.pack(side="left", padx=(4, 0))
        tk.Button(inner, text="Pay all", font=("Segoe UI", 8, "bold"), relief="flat", bg=C["content_bg"],
                  cursor="hand2", command=self.pay_all).pack(side="left", padx=(6, 0))
        tk.Button(inner, text="All on account", font=("Segoe UI", 8), relief="flat", bg=C["content_bg"],
                  cursor="hand2", command=self.all_on_account).pack(side="left", padx=(4, 0))
        self.summary = tk.Label(inner, text="", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                                fg=C["text_primary"])
        self.summary.pack(side="right")
        self._rows = []
        self.add_row(user=False)
        if state != "normal":
            for w in (self.add_btn,):
                w.configure(state="disabled")

    # ── rows ──────────────────────────────────────────────────
    def _default_label(self, kind="cash"):
        for l, a in self.by_label.items():
            if a.get("kind") == kind:
                return l
        return self.labels[0] if self.labels else ""

    def add_row(self, user=True, label=None, amount=0.0):
        if len(self._rows) >= self.MAX_ROWS:
            return None
        C = self.C
        fr = tk.Frame(self.rows_box, bg=C["card_bg"])
        fr.pack(side="left", padx=(0, 8))
        av = tk.StringVar(value=label or self._default_label(
            "bank" if self._rows else "cash"))
        mv = tk.StringVar(value="%.2f" % amount if amount else "")
        cb = ttk.Combobox(fr, textvariable=av, values=self.labels, state="readonly" if self.state == "normal"
                          else "disabled", width=20, font=("Segoe UI", 9))
        cb.pack(side="left")
        e = tk.Entry(fr, textvariable=mv, width=9, justify="right", font=("Segoe UI", 10, "bold"),
                     relief="solid", bd=1, state=self.state)
        e.pack(side="left", padx=(3, 0))
        x = tk.Button(fr, text="✕", font=("Segoe UI", 8), relief="flat", bg=C["card_bg"],
                      fg=C["text_secondary"], cursor="hand2", bd=0,
                      command=lambda: self.remove_row(row))
        x.pack(side="left", padx=(1, 0))
        row = {"frame": fr, "acct": av, "amount": mv, "entry": e, "combo": cb}
        self._rows.append(row)
        mv.trace_add("write", lambda *a: self._typed())
        cb.bind("<<ComboboxSelected>>", lambda e_: self._typed())
        if user:
            self.manual = True
            e.focus_set()
        self._refresh()
        return row

    def remove_row(self, row):
        if row in self._rows and len(self._rows) > 1:
            self._rows.remove(row)
            row["frame"].destroy()
        elif row in self._rows:
            row["amount"].set("")
        self.manual = True
        self._refresh()

    def _typed(self):
        if not self._busy:
            self.manual = True
        self._refresh()

    # ── what is paid ──────────────────────────────────────────
    def rows(self):
        out = []
        for r in self._rows:
            amt = _f(r["amount"].get())
            a = self.by_label.get(r["acct"].get())
            if amt > 0 and a:
                out.append({"method": a.get("kind") or "cash", "account_id": a["account_id"],
                            "amount": amt})
        return out

    def paid(self):
        return round(sum(x["amount"] for x in self.rows()), 2)

    def on_account(self):
        return round(max(0.0, _f(self.get_total()) - self.paid()), 2)

    def change(self):
        return round(max(0.0, self.paid() - _f(self.get_total())), 2)

    def method(self):
        """For the document's payment method column: credit when nothing is
        paid, else the kind (cash / bank) of the biggest amount paid."""
        rows = self.rows()
        if not rows:
            return "credit"
        big = max(rows, key=lambda x: x["amount"])
        return "bank_transfer" if big["method"] == "bank" else "cash"

    # ── set from outside ──────────────────────────────────────
    def _set(self, pairs):
        """pairs [(label, amount)] → the rows (first row reused)."""
        self._busy = True
        try:
            while len(self._rows) > max(1, len(pairs)):
                r = self._rows.pop()
                r["frame"].destroy()
            while len(self._rows) < len(pairs):
                self.add_row(user=False)
            if not pairs:
                self._rows[0]["amount"].set("")
            for r, (lab, amt) in zip(self._rows, pairs):
                if lab:
                    r["acct"].set(lab)
                r["amount"].set(("%.2f" % amt) if amt else "")
        finally:
            self._busy = False
        self._refresh()

    def set_auto(self, method):
        """The payment method box (cash / bank / credit …) → the panel,
        while nobody has typed in it."""
        if self.manual:
            self._refresh()
            return
        m = str(method or "").lower()
        tot = _f(self.get_total())
        if m == "credit" or tot <= 0:
            self._set([])
        elif m in ("bank_transfer", "bank", "card", "cheque", "mada"):
            self._set([(self._default_label("bank"), tot)])
        else:
            self._set([(self._default_label("cash"), tot)])

    def total_changed(self):
        """The bill total moved: an untouched panel follows it."""
        if not self.manual and self._rows and _f(self._rows[0]["amount"].get()) and len(self._rows) == 1:
            self._busy = True
            try:
                self._rows[0]["amount"].set("%.2f" % _f(self.get_total()))
            finally:
                self._busy = False
        self._refresh()

    def set_rows(self, rows):
        """A saved document: [{account_id, amount}]."""
        pairs = []
        for x in rows or []:
            if _f(x.get("amount")) <= 0:
                continue
            lab = next((l for l, a in self.by_label.items() if a["account_id"] == x.get("account_id")), None)
            pairs.append((lab, _f(x.get("amount"))))
        self._set(pairs)
        self.manual = bool(rows)

    def pay_all(self):
        rest = self.on_account()
        if rest <= 0:
            return
        last = self._rows[-1]
        last["amount"].set("%.2f" % (_f(last["amount"].get()) + rest))
        self.manual = True
        self._refresh()

    def all_on_account(self):
        self._set([])
        self.manual = True
        self._refresh()

    # ── the summary line ──────────────────────────────────────
    def _refresh(self):
        C = self.C
        tot, paid = _f(self.get_total()), self.paid()
        rest, chg = self.on_account(), self.change()
        try:
            from modules import country as _K
            m = lambda v: _K.money(v)
        except Exception:
            m = lambda v: "{:,.2f}".format(v)
        if chg > 0.004:
            txt, fg = "Total %s · Paid %s · Change %s" % (m(tot), m(paid), m(chg)), "#15803D"
        elif rest > 0.004:
            txt, fg = "Total %s · Paid %s · On account %s" % (m(tot), m(paid), m(rest)), C.get("danger", "#B91C1C")
        else:
            txt, fg = "Total %s · Paid in full" % m(tot), "#15803D"
        try:
            self.summary.configure(text=txt, fg=fg)
        except tk.TclError:
            return
        if self.on_change and not self._busy:
            try:
                self.on_change()
            except Exception:
                pass

    def save(self, doc_type, doc_id):
        """The rows → payment_tenders (inside the document's save). A bill
        with nothing paid keeps a 0.00 'on_account' marker row."""
        from modules import tenders as _td
        rows = self.rows()
        tot = _f(self.get_total())
        if self.change() > 0.004:                 # change is given back, never booked
            excess = round(sum(x["amount"] for x in rows) - tot, 2)
            for x in rows:
                if excess <= 0.004:
                    break
                cut = min(x["amount"], excess)
                x["amount"] = round(x["amount"] - cut, 2)
                excess = round(excess - cut, 2)
            rows = [x for x in rows if x["amount"] > 0.004]
        if not rows:
            rows = [{"method": "on_account", "amount": 0.0, "account_id": None}]
        return _td.save_lines(doc_type, doc_id, rows)


def ok_for_party(is_walkin, total, paid, party="customer"):
    """'' when fine; else why the walk-in party can't leave money on account."""
    if is_walkin and round(float(total or 0) - float(paid or 0), 2) > 0.004:
        who = "Cash Customer" if party == "customer" else "Cash Supplier"
        return ("The %s has no account of its own — pay the full amount, or pick a %s to leave "
                "the rest on their account." % (who, party))
    return ""
