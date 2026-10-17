# ============================================================
# DayBill ERP - Year-End Closing page (Accounts)  v6.0
# ------------------------------------------------------------
# Pick a financial year → see its income, expenses and profit, the
# things still open (ZATCA, drafts) → Close: the closing entry moves the
# profit to Retained Earnings and the year is locked. Reopen undoes it.
# v6.9.3: Close and Reopen need accounts.approve + typing the year's name.
# ============================================================
import tkinter as tk

from modules import year_end as YE
from ui import danger
from ui import v6_kit as K


class YearEndView:
    def __init__(self, parent):
        self.page = K.Page(parent, "📅  Year-End Closing",
                           "Close a financial year: its profit (or loss) moves to Retained Earnings "
                           "with one closing entry on the last day, income and expense accounts start "
                           "the new year at zero, and the year is locked against changes.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        top = tk.Frame(self.page.body, bg=C["content_bg"]); top.pack(fill="x")
        self.fy_v = tk.StringVar()
        try:
            from modules import financial_year as FY
            self.years = [dict(y) for y in FY.list_years()]
        except Exception:
            self.years = []
        labels = ["%s  (%s → %s)%s" % (y.get("label"), str(y.get("start_date"))[:10],
                                       str(y.get("end_date"))[:10], "  · CLOSED" if y.get("is_closed") else "")
                  for y in self.years]
        f = tk.Frame(top, bg=C["content_bg"]); f.pack(side="left")
        cb = K.combo(f, {"card_bg": C["content_bg"], "text_secondary": C["text_secondary"]},
                     "Financial year", self.fy_v, labels, 40)
        cb.bind("<<ComboboxSelected>>", lambda e: self.load())
        if labels:
            open_i = next((i for i, y in enumerate(self.years) if not y.get("is_closed")), 0)
            self.fy_v.set(labels[open_i])
        self._labels = labels
        bar = tk.Frame(top, bg=C["content_bg"]); bar.pack(side="right")
        self.close_btn = K.button(bar, C, "🔒 Close the year", self._close, primary=True)
        self.reopen_btn = K.button(bar, C, "🔓 Reopen", self._reopen)
        self.sum_v = tk.StringVar()
        tk.Label(self.page.body, textvariable=self.sum_v, font=("Segoe UI", 13, "bold"),
                 bg=C["content_bg"], fg=C["primary"], anchor="w").pack(fill="x", pady=(10, 2))
        self.chk_v = tk.StringVar()
        self.chk_lbl = tk.Label(self.page.body, textvariable=self.chk_v, font=("Segoe UI", 9, "bold"),
                                bg=C["content_bg"], fg=C["danger"], anchor="w", justify="left",
                                wraplength=1000)
        self.chk_lbl.pack(fill="x")
        self.tree = K.tree(self.page.body, [("code", "Code", 90, "w"), ("name", "Account", 300, "w"),
                                            ("type", "Type", 90, "w"), ("bal", "Balance to close", 140, "e")],
                           height=16)
        if not self.years:
            self.page.say("No financial years yet — Settings ▸ Financial Year ▸ New.", ok=False)
            return
        self.load()

    def _fy(self):
        try:
            i = self._labels.index(self.fy_v.get())
            return self.years[i]
        except (ValueError, IndexError):
            return None

    def load(self):
        y = self._fy()
        self.tree.delete(*self.tree.get_children())
        if not y:
            return
        p = YE.preview(y["fy_id"])
        for acc, code, name, typ, bal in p["lines"]:
            self.tree.insert("", "end", values=(code, name, typ.title(), K.money(bal)))
        self.sum_v.set("Income %s   −   Expenses %s   =   %s %s SAR"
                       % (K.money(p["revenue"]), K.money(p["expenses"]),
                          "Profit" if p["profit"] >= 0 else "Loss", K.money(abs(p["profit"]))))
        probs = [] if y.get("is_closed") else YE.checks(y["fy_id"])
        self.chk_v.set(("Before closing:  • " + "   • ".join(probs)) if probs else
                       ("✓ This year is closed." if y.get("is_closed") else "✓ Ready to close."))
        self.chk_lbl.configure(fg=self.C["danger"] if probs else self.C.get("success", "#16A34A"))
        self.close_btn.configure(state="disabled" if y.get("is_closed") else "normal")
        self.reopen_btn.configure(state="normal" if y.get("is_closed") else "disabled")

    def _refresh_years(self, keep_id):
        from modules import financial_year as FY
        self.years = [dict(x) for x in FY.list_years()]
        self._labels = ["%s  (%s → %s)%s" % (y.get("label"), str(y.get("start_date"))[:10],
                                             str(y.get("end_date"))[:10], "  · CLOSED" if y.get("is_closed") else "")
                        for y in self.years]
        i = next((i for i, y in enumerate(self.years) if y["fy_id"] == keep_id), 0)
        self.fy_v.set(self._labels[i] if self._labels else "")
        self.load()

    def _close(self):
        # v6.9.3: accounts.approve + typing the year's name (danger.gate)
        y = self._fy()
        if not y:
            return
        probs = YE.checks(y["fy_id"])
        q = ("Close %s and lock it?\n\nIts profit (or loss) moves to Retained Earnings and no "
             "new transactions can be posted into it." % y.get("label"))
        if probs:
            q += "\n\nNot finished yet:\n• " + "\n• ".join(probs)
        if not danger.gate(self.frame, "accounts", "approve", "Close the year", q,
                           word=y.get("label") or "CLOSE"):
            return
        try:
            ok, msg = YE.close(y["fy_id"], force=True)
        except Exception as e:
            ok, msg = False, "Nothing was changed: %s" % str(e)[:200]
        self.page.say(msg.replace("\n", " "), ok=ok)
        if ok:
            self._refresh_years(y["fy_id"])

    def _reopen(self):
        # v6.9.3: accounts.approve + typing the year's name (danger.gate)
        y = self._fy()
        if not y or not danger.gate(self.frame, "accounts", "approve", "Reopen the year",
                                    "Reopen %s? The closing entry is removed and the year can "
                                    "be changed again." % y.get("label"),
                                    word=y.get("label") or "REOPEN"):
            return
        try:
            ok, msg = YE.reopen(y["fy_id"])
        except Exception as e:
            ok, msg = False, str(e)[:200]
        self.page.say(msg, ok=ok)
        if ok:
            self._refresh_years(y["fy_id"])
