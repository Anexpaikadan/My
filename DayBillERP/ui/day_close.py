# ============================================================
# DayBill ERP - Day Close / Z-Report
# ------------------------------------------------------------
# The one report a shop runs every night. Reads the JOURNAL (the
# single source every screen posts to) for a chosen day:
#   Opening cash  -> Cash account balance before the day
#   + Cash sales / receipts          (cash debits to the cash a/c)
#   − Cash payments / expenses       (cash credits from the cash a/c)
#   = Expected cash in drawer
# Plus card/bank tenders, VAT collected, and a sales-by-type
# breakdown. A denomination counter lets the user enter the actual
# drawer count and shows the variance (over / short).
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import account_defaults as ad


def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


# Saudi riyal notes + coins (halalas as .50 etc.)
DENOMS = [500, 200, 100, 50, 10, 5, 1, 0.50, 0.25, 0.10, 0.05]


class DayCloseView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build(C)
        self._load()

    def _build(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="🌙  Day Close / Z-Report", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        tk.Label(bar, text="Date", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(16, 4))
        tk.Entry(bar, textvariable=self.date_var, width=12, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 8))
        # counter (till): All = whole shop (cash account); one counter =
        # that drawer's own takings and expected cash
        self._counters = []
        try:
            from modules import branches as _br
            if _br.tables_ready():
                self._counters = _br.list_counters(active_only=True)
        except Exception:
            self._counters = []
        self.counter_var = tk.StringVar(value="All counters")
        if len(self._counters) > 1:
            tk.Label(bar, text="Counter", font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            try:
                from modules import branches as _br
                _b, here = _br.current()
                me = next((c for c in self._counters if c["counter_id"] == here), None)
                if me:
                    self.counter_var.set(f"{me['code']} · {me['name_en']}")
            except Exception:
                pass
            cb = ttk.Combobox(bar, textvariable=self.counter_var, state="readonly", width=18,
                              values=["All counters"] + [f"{c['code']} · {c['name_en']}"
                                                         for c in self._counters])
            cb.pack(side="left", padx=(0, 8))
            cb.bind("<<ComboboxSelected>>", lambda e: self._load())
        tk.Button(bar, text="🔄 Run", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._load).pack(side="left")
        tk.Button(bar, text="🖨 Print", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=14,
                  pady=6, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._print).pack(side="right")
        tk.Button(bar, text="🟢 Send to Owner", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=14,
                  pady=6, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._whatsapp).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="📲 Owner report", font=("Segoe UI", 9, "bold"),
                  bg=C["success"], fg="white", relief="flat", padx=14,
                  pady=6, cursor="hand2", command=self._owner_report).pack(side="right", padx=(0, 8))

        wrap = tk.Frame(self.frame, bg=C["content_bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=12)
        # left: cash summary  | right: denomination counter
        # left side scrolls (a counter card + the shop cards can be taller than the screen)
        lw = tk.Frame(wrap, bg=C["content_bg"])
        lw.pack(side="left", fill="both", expand=True, padx=(0, 12))
        cv = tk.Canvas(lw, bg=C["content_bg"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(lw, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(side="left", fill="both", expand=True)
        self.left = tk.Frame(cv, bg=C["content_bg"])
        win = cv.create_window((0, 0), window=self.left, anchor="nw")
        self.left.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=e.width))

        def _wheel(e):
            try:
                if cv.winfo_exists() and self.left.winfo_height() > cv.winfo_height():
                    cv.yview_scroll(int(-e.delta / 120) or (-1 if e.num == 4 else 1), "units")
            except Exception:
                pass
        for w_ in (cv, self.left):
            w_.bind("<Enter>", lambda e: (cv.bind_all("<MouseWheel>", _wheel),
                                          cv.bind_all("<Button-4>", _wheel),
                                          cv.bind_all("<Button-5>", _wheel)))
        self._left_canvas = cv
        self.right = tk.Frame(wrap, bg=C["card_bg"],
                              highlightbackground=C["border"], highlightthickness=1)
        self.right.pack(side="left", fill="y")
        self._build_counter(C)

    # ── cash counter (right) ──────────────────────────────────
    def _build_counter(self, C):
        tk.Label(self.right, text="💵 Count the drawer", font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", padx=14, pady=(12, 6))
        grid = tk.Frame(self.right, bg=C["card_bg"]); grid.pack(padx=14)
        tk.Label(grid, text="Denom", font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                 fg=C["text_secondary"], width=8, anchor="w").grid(row=0, column=0)
        tk.Label(grid, text="Count", font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                 fg=C["text_secondary"], width=6).grid(row=0, column=1)
        tk.Label(grid, text="Amount", font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                 fg=C["text_secondary"], width=9, anchor="e").grid(row=0, column=2)
        self.denom_vars = {}
        self.denom_amt = {}
        for i, d in enumerate(DENOMS, 1):
            tk.Label(grid, text=f"{d:g}", font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_primary"], anchor="w", width=8).grid(row=i, column=0, pady=1)
            v = tk.StringVar(value="")
            v.trace("w", lambda *a: self._recount())
            tk.Entry(grid, textvariable=v, width=6, font=("Segoe UI", 9),
                     relief="solid", bd=1, justify="center").grid(row=i, column=1, pady=1)
            self.denom_vars[d] = v
            amt = tk.StringVar(value="0.00")
            tk.Label(grid, textvariable=amt, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"], anchor="e", width=9).grid(row=i, column=2, pady=1)
            self.denom_amt[d] = amt
        tk.Frame(self.right, bg=C["border"], height=1).pack(fill="x", padx=14, pady=8)
        self.counted_var = tk.StringVar(value="0.00")
        self.variance_var = tk.StringVar(value="0.00")
        for lbl, var, col in [("Counted cash", self.counted_var, C["text_primary"]),
                              ("Variance", self.variance_var, C["danger"])]:
            r = tk.Frame(self.right, bg=C["card_bg"]); r.pack(fill="x", padx=14, pady=2)
            tk.Label(r, text=lbl, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left")
            tk.Label(r, textvariable=var, font=("Segoe UI", 12, "bold"),
                     bg=C["card_bg"], fg=col).pack(side="right")
        tk.Label(self.right, text="(Counted − Expected cash)", font=("Segoe UI", 7),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(pady=(0, 12))

    def _recount(self):
        total = 0.0
        for d, v in self.denom_vars.items():
            try:
                n = int(float(v.get() or 0))
            except Exception:
                n = 0
            amt = n * d
            self.denom_amt[d].set(money(amt))
            total += amt
        self.counted_var.set(money(total))
        expected = getattr(self, "_expected_cash", 0.0)
        var = total - expected
        self.variance_var.set(("+" if var >= 0 else "−") + money(abs(var)))

    # ── summary card builder ──────────────────────────────────
    def _row(self, parent, label, var, bold=False, color=None, big=False):
        C = self.C
        r = tk.Frame(parent, bg=C["card_bg"]); r.pack(fill="x", padx=16, pady=2)
        tk.Label(r, text=label, font=("Segoe UI", 11 if big else 9,
                 "bold" if bold else "normal"), bg=C["card_bg"],
                 fg=color or C["text_primary"]).pack(side="left")
        tk.Label(r, textvariable=var, font=("Segoe UI", 13 if big else 10, "bold"),
                 bg=C["card_bg"], fg=color or C["text_primary"]).pack(side="right")

    def _card(self, title):
        C = self.C
        c = tk.LabelFrame(self.left, text=f"  {title}  ", bg=C["card_bg"],
                          fg=C["primary"], font=("Segoe UI", 10, "bold"))
        c.pack(fill="x", pady=(0, 10))
        return c

    def _one_counter(self):
        sel = self.counter_var.get() if hasattr(self, "counter_var") else "All counters"
        return any(f"{x['code']} · {x['name_en']}" == sel for x in getattr(self, "_counters", []))

    # ── load (journal-based) ──────────────────────────────────
    def _load(self):
        for w in self.left.winfo_children():
            w.destroy()
        d = self.date_var.get()
        # v6.0: ZATCA wants simplified bills reported within 24 hours
        try:
            from modules.zatca import egs as _E
            z = _E.overdue_text(12) if _E.any_connected() else ""
        except Exception:
            z = ""
        self.zatca_warning = z
        if z:
            tk.Label(self.left, text=z + "  — send them before closing the day.",
                     font=("Segoe UI", 10, "bold"), bg="#FEF2F2", fg="#B91C1C", anchor="w",
                     padx=10, pady=6, wraplength=640, justify="left").pack(fill="x", pady=(0, 8))
        try:                       # v6.0: POS bills kept on this PC while the server was gone
            from modules import offline_pos as _OFF
            n_off = _OFF.count()
        except Exception:
            n_off = 0
        if n_off:
            tk.Label(self.left, text="📴 %d POS bill(s) are kept on this PC and not yet on the server — "
                     "they are sent by themselves when the POS is open and the server answers; "
                     "they are not in these totals yet." % n_off,
                     font=("Segoe UI", 10, "bold"), bg="#FFFBEB", fg="#B45309", anchor="w",
                     padx=10, pady=6, wraplength=640, justify="left").pack(fill="x", pady=(0, 8))
        cash_id = ad.cash()
        try:
            opening = float(db.execute_scalar(
                "SELECT COALESCE(SUM(jl.debit - jl.credit),0) FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE jl.account_id=? AND je.entry_date < ? AND je.is_posted=1",
                (cash_id, d)) or 0)
            cash_in = float(db.execute_scalar(
                "SELECT COALESCE(SUM(jl.debit),0) FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE jl.account_id=? AND je.entry_date=? AND je.is_posted=1",
                (cash_id, d)) or 0)
            cash_out = float(db.execute_scalar(
                "SELECT COALESCE(SUM(jl.credit),0) FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE jl.account_id=? AND je.entry_date=? AND je.is_posted=1",
                (cash_id, d)) or 0)
            # sales by type
            by_type = db.fetchall(
                "SELECT je.source_type, COUNT(DISTINCT je.journal_id) AS n, "
                "COALESCE(SUM(je.total_debit),0) AS amt FROM journal_entries je "
                "WHERE je.entry_date=? AND je.is_posted=1 GROUP BY je.source_type "
                "ORDER BY amt DESC", (d,)) or []
            # money into the bank / card accounts today: card (mada) taken on
            # the bills, and everything else (receipts by bank, transfers)
            bank_ids = [a for a in {ad.bank(), ad.card()} if a]
            card_in = bank_in = 0.0
            if bank_ids:
                ph = ",".join("?" * len(bank_ids))
                card_in = float(db.execute_scalar(
                    "SELECT COALESCE(SUM(jl.debit),0) FROM journal_lines jl "
                    "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                    f"WHERE jl.account_id IN ({ph}) AND je.entry_date=? AND je.is_posted=1 "
                    "AND je.source_type IN ('sales','pos')", (*bank_ids, d)) or 0)
                bank_in = float(db.execute_scalar(
                    "SELECT COALESCE(SUM(jl.debit),0) FROM journal_lines jl "
                    "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                    f"WHERE jl.account_id IN ({ph}) AND je.entry_date=? AND je.is_posted=1 "
                    "AND ISNULL(je.source_type,'') NOT IN ('sales','pos')",
                    (*bank_ids, d)) or 0)
            vat_today = float(db.execute_scalar(
                "SELECT COALESCE(SUM(jl.credit - jl.debit),0) FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "WHERE jl.account_id=? AND je.entry_date=? AND je.is_posted=1",
                (ad.tax_payable(), d)) or 0)
        except Exception as e:
            messagebox.showerror(
                "Day Close",
                "Could not read the journal. Make sure the accounting patches "
                "are applied.\n\n" + str(e)[:150])
            return

        expected = opening + cash_in - cash_out
        self._expected_cash = expected
        self._snapshot = dict(date=d, opening=opening, cash_in=cash_in,
                              cash_out=cash_out, expected=expected,
                              card=card_in, bank=bank_in, vat=vat_today,
                              by_type=by_type)

        # Cash card
        cc = self._card("Cash drawer" if not self._one_counter() else "Whole shop — cash account (all counters)")
        v_open = tk.StringVar(value=money(opening))
        v_in = tk.StringVar(value=money(cash_in))
        v_out = tk.StringVar(value="−" + money(cash_out))
        v_exp = tk.StringVar(value=money(expected))
        self._row(cc, "Opening cash", v_open)
        self._row(cc, "Cash received (sales + receipts)", v_in, color=self.C["accent"])
        self._row(cc, "Cash paid out (expenses + payments)", v_out, color=self.C["danger"])
        tk.Frame(cc, bg=self.C["border"], height=1).pack(fill="x", padx=16, pady=4)
        self._row(cc, "Expected cash in drawer", v_exp, bold=True,
                  color=self.C["primary"], big=True)

        # Other tenders
        tc = self._card("Other tenders & tax")
        self._row(tc, "Card / mada on bills", tk.StringVar(value=money(card_in)))
        self._row(tc, "Other money into the bank", tk.StringVar(value=money(bank_in)))
        self._row(tc, "VAT collected (net output)", tk.StringVar(value=money(vat_today)),
                  color=self.C["info"])
        # v6.0: every way the bills were paid today (cash, mada, STC Pay, Tabby …)
        try:
            from modules import tenders as _td
            sel_c = self.counter_var.get() if hasattr(self, "counter_var") else "All counters"
            cc_ = next((x for x in self._counters if f"{x['code']} · {x['name_en']}" == sel_c), None)
            tb = _td.totals_by_method(d, d, counter_id=cc_["counter_id"] if cc_ else None)
        except Exception:
            tb = {}
        self._snapshot["tenders"] = tb
        if tb:
            tt = self._card("Bills paid by")
            for k, a in sorted(tb.items(), key=lambda kv: -kv[1]):
                self._row(tt, _td.label(k), tk.StringVar(value=money(a)))

        # Activity by type
        ac = self._card("Activity by type")
        if by_type:
            for r in by_type:
                try:
                    from modules.report_center import type_label
                    lbl = type_label(r["source_type"] or "other")
                except Exception:
                    lbl = (r["source_type"] or "other").replace("_", " ").title()
                self._row(ac, f"{lbl}  ({r['n']})",
                          tk.StringVar(value=money(r["amt"])))
        else:
            tk.Label(ac, text="No posted entries for this day.",
                     font=("Segoe UI", 9), bg=self.C["card_bg"],
                     fg=self.C["text_secondary"]).pack(padx=16, pady=8)

        # one counter chosen: its own drawer figures replace the shop total
        sel = self.counter_var.get() if hasattr(self, "counter_var") else "All counters"
        c = next((x for x in self._counters
                  if f"{x['code']} · {x['name_en']}" == sel), None)
        if c:
            try:
                from modules import branches as _br
                x = _br.takings(d, d, counter_id=c["counter_id"]).get(c["counter_id"]) or {}
            except Exception:
                x = {}
            kc = self._card(f"Counter {c['code']} · {c['name_en']}  ({c['branch_name']})")
            first = self.left.winfo_children()[0]
            if first is not kc:
                kc.pack_configure(before=first)     # this drawer first
            for lbl, key, color in (("Bills", "bills", None), ("Sales total", "total", None),
                                    ("Cash on bills", "cash", self.C["accent"]),
                                    ("Card / bank on bills", "card", None),
                                    ("On credit", "credit", None),
                                    ("Cash receipts at this counter", "receipts", self.C["accent"]),
                                    ("Cash refunds (returns)", "refunds", self.C["danger"]),
                                    ("Cash paid out at this counter", "paid_out", self.C["danger"])):
                v = x.get(key, 0)
                self._row(kc, lbl, tk.StringVar(value=str(int(v)) if key == "bills" else money(v)),
                          color=color)
            tk.Frame(kc, bg=self.C["border"], height=1).pack(fill="x", padx=16, pady=4)
            self._row(kc, "Expected cash in THIS drawer",
                      tk.StringVar(value=money(x.get("expected_cash", 0))), bold=True,
                      color=self.C["primary"], big=True)
            self._expected_cash = float(x.get("expected_cash", 0) or 0)
            self._snapshot["expected"] = self._expected_cash
            self._snapshot["counter"] = f"{c['code']} · {c['name_en']}"

        self._recount()

    def summary_text(self):
        """Short Z-report for WhatsApp."""
        snap = getattr(self, "_snapshot", None)
        if not snap:
            return ""
        try:
            comp = db.fetchone("SELECT company_name_en FROM company WHERE company_id=1") or {}
        except Exception:
            comp = {}
        lines = [f"*{comp.get('company_name_en') or 'DayBill'} — Day Close {snap['date']}*",
                 f"Opening cash: {money(snap['opening'])}",
                 f"Cash in: {money(snap['cash_in'])}",
                 f"Cash out: {money(snap['cash_out'])}",
                 f"Expected cash: {money(snap['expected'])}",
                 f"Card on bills: {money(snap['card'])}   Other bank: {money(snap['bank'])}",
                 f"VAT collected: {money(snap['vat'])}"]
        if snap.get("counter"):
            lines.insert(1, f"Counter: {snap['counter']}  (expected = this drawer)")
        try:
            counted = float(str(self.counted_var.get()).replace(",", "") or 0)
            if counted:
                lines.append(f"Counted cash: {money(counted)}   Variance: "
                             f"{self.variance_var.get()}")
        except Exception:
            pass
        try:
            from modules.report_center import type_label
            for r in snap.get("by_type") or []:
                if r.get("source_type") in ("sales", "pos", "sales_return", "expense",
                                            "receipt", "payment", "purchase"):
                    lines.append(f"{type_label(r['source_type'])} ({r['n']}): {money(r['amt'])}")
        except Exception:
            pass
        return "\n".join(lines)

    def _whatsapp(self):
        if not getattr(self, "_snapshot", None):
            self._load()
        try:
            from ui.whatsapp_send import send_document
            send_document(self.frame, "day_close", None, text=self.summary_text())
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:300])

    def _owner_report(self, ask=True):
        """📲 The owner's evening report (sales vs last week, cash short,
        best items, stock + cashier alerts) for the date shown."""
        from modules import owner_report as OR
        day = (self.date_var.get() or "").strip()[:10] or None
        try:
            text, _d = OR.build(day)
        except Exception as e:
            messagebox.showerror("Owner report", str(e)[:300])
            return False
        self.owner_text = text
        if ask and not messagebox.askyesno("📲 Owner report",
                                           text + "\n\nSend this to the owner's WhatsApp?", parent=self.frame):
            return False
        ok, msg = OR.send(day, interactive=True)
        (messagebox.showinfo if ok else messagebox.showwarning)("📲 Owner report", msg, parent=self.frame)
        return ok

    def _print(self):
        snap = getattr(self, "_snapshot", None)
        if not snap:
            return
        try:
            import tempfile, os
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
            path = os.path.join(tempfile.gettempdir(), f"zreport_{snap['date']}.pdf")
            c = canvas.Canvas(path, pagesize=A4)
            W, H = A4
            y = H - 25 * mm
            c.setFont("Helvetica-Bold", 16)
            c.drawString(20 * mm, y, "Day Close / Z-Report")
            c.setFont("Helvetica", 10)
            y -= 8 * mm
            c.drawString(20 * mm, y, f"Date: {snap['date']}")
            y -= 10 * mm

            def line(label, val, bold=False):
                nonlocal y
                c.setFont("Helvetica-Bold" if bold else "Helvetica", 11 if bold else 10)
                c.drawString(22 * mm, y, label)
                c.drawRightString(W - 22 * mm, y, money(val))
                y -= 7 * mm

            line("Opening cash", snap["opening"])
            line("Cash received", snap["cash_in"])
            line("Cash paid out", -snap["cash_out"])
            line("Expected cash in drawer", snap["expected"], bold=True)
            y -= 4 * mm
            line("Card / mada on bills", snap["card"])
            line("Other money into the bank", snap["bank"])
            line("VAT collected", snap["vat"])
            y -= 4 * mm
            line("Counted cash", float(str(self.counted_var.get()).replace(",", "") or 0))
            line("Variance", float(str(self.variance_var.get())
                                   .replace(",", "").replace("−", "-").replace("+", "") or 0))
            c.setFont("Helvetica", 7)
            c.drawCentredString(W / 2, 12 * mm, "Generated by DayBill ERP")
            c.showPage(); c.save()
            try:
                from modules import audit
                audit.log("print", "day_close", snap["date"], "Z-Report")
            except Exception:
                pass
            if os.name == "nt":
                os.startfile(path)
            else:
                messagebox.showinfo("Z-Report", f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Z-Report", str(e)[:200])
