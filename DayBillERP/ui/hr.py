# ============================================================
# DayBill ERP - HR & Payroll Module  (v6.6)
# Employees | Payroll | Loans | End of Service | Leave | Attendance | Documents
# ------------------------------------------------------------
# The screens only show and ask; every change goes through
# modules/payroll.py (payroll months, loans, final settlement) and
# modules/hr_time.py (leave, attendance, documents).
# v6.9.3: making a month AGAIN needs hr.delete + typing the month
# (e.g. 2026-09); Delete month needs hr.delete + typing the month;
# every Save checks its right; dialogs stay on top of their screen.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db
from modules import payroll_engine as PE
from modules import payroll as PR
from modules import hr_time as HT
from modules import permissions as perm


def _m(v):
    try:
        return f"{float(v or 0):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _btn(parent, C, text, cmd, primary=False, side="left", danger=False):
    b = tk.Button(parent, text=text, font=("Segoe UI", 9, "bold" if primary else "normal"),
                  bg=C["primary"] if primary else C["card_bg"],
                  fg="white" if primary else (C["danger"] if danger else C["text_primary"]),
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=0 if primary else 1, command=cmd)
    b.pack(side=side, padx=(0, 6) if side == "left" else (6, 0))
    return b


def _modal(win, parent):
    """Dialog stays on top of the screen that opened it and blocks it."""
    try:
        if parent is not None:
            win.transient(parent.winfo_toplevel())
    except Exception:
        pass
    win.grab_set()


def _month_word(m, y):
    """What the user types to confirm a payroll month: 2026-09."""
    return "%d-%02d" % (int(y), int(m))


def _tree(parent, C, cols, height=None):
    card = tk.Frame(parent, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
    card.pack(fill="both", expand=True)
    vsb = ttk.Scrollbar(card, orient="vertical")
    vsb.pack(side="right", fill="y")
    kw = {"height": height} if height else {}
    tv = ttk.Treeview(card, columns=[c[0] for c in cols], show="headings", yscrollcommand=vsb.set, **kw)
    vsb.config(command=tv.yview)
    for k, lbl, w, a in cols:
        tv.heading(k, text=lbl)
        tv.column(k, width=w, anchor=a, stretch=(a == "w"))
    tv.pack(fill="both", expand=True)
    return tv


class HRView:
    start_tab = None

    def __init__(self, parent):
        self.parent = parent
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._tabs(C)

    def _tabs(self, C):
        style = ttk.Style()
        style.configure("HR.TNotebook", background=C["content_bg"], borderwidth=0)
        style.configure("HR.TNotebook.Tab", font=("Segoe UI", 10), padding=(12, 6))
        nb = ttk.Notebook(self.frame, style="HR.TNotebook")
        nb.pack(fill="both", expand=True, padx=16, pady=(10, 10))
        self.nb = nb
        names = [("emp", "👥  Employees"), ("pay", "💰  Payroll"), ("loan", "🏦  Loans"),
                 ("eos", "📤  End of Service"), ("leave", "🌴  Leave"), ("att", "🕘  Attendance"),
                 ("docs", "📄  Documents")]
        for key, text in names:
            f = tk.Frame(nb, bg=C["content_bg"])
            setattr(self, "t_" + key, f)
            nb.add(f, text="  %s  " % text)
        # one tab that cannot load (old database, bad data) never blocks the others
        for build, tab in ((self._build_employees, self.t_emp), (self._build_payroll, self.t_pay),
                           (self._build_loans, self.t_loan), (self._build_eos, self.t_eos)):
            try:
                build(tab, C)
            except Exception as e:
                print("[DayBill] HR tab:", e)
                tk.Label(tab, text="⚠ This part could not load: %s\nUpdates ▸ Apply All Updates, then open "
                                   "HR again." % str(e)[:200], font=("Segoe UI", 10), bg=C["content_bg"],
                         fg=C["danger"], justify="left").pack(anchor="w", padx=16, pady=16)
        try:
            from ui.hr_time_view import LeaveTab, AttendanceTab
            self.leave_tab = LeaveTab(self.t_leave, C)
            self.att_tab = AttendanceTab(self.t_att, C)
        except Exception as e:
            tk.Label(self.t_leave, text="Leave: %s" % e, bg=C["content_bg"]).pack()
        self.docs_tab = DocumentsTab(self.t_docs, C, self)
        start = HRView.start_tab
        if start:
            try:
                nb.select({"leave": self.t_leave, "attendance": self.t_att, "payroll": self.t_pay,
                           "loans": self.t_loan, "eos": self.t_eos, "documents": self.t_docs}.get(start, self.t_emp))
            except Exception:
                pass
            HRView.start_tab = None

    # ═══════════════ EMPLOYEES ═══════════════
    def _build_employees(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(10, 6))
        tk.Label(bar, text="🔍", bg=C["content_bg"]).pack(side="left")
        self.emp_q = tk.StringVar()
        e = tk.Entry(bar, textvariable=self.emp_q, width=26, font=("Segoe UI", 10), relief="solid", bd=1)
        e.pack(side="left", padx=(4, 10), ipady=3)
        self.emp_q.trace_add("write", lambda *a: self._load_emps())
        self.emp_all = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Show ex-employees", variable=self.emp_all, bg=C["content_bg"],
                       activebackground=C["content_bg"], font=("Segoe UI", 9),
                       command=self._load_emps).pack(side="left")
        _btn(bar, C, "＋ New Employee", self._new_emp, primary=True, side="right")
        _btn(bar, C, "🔄 Refresh", self._load_emps, side="right")
        self.emp_strip = tk.Frame(parent, bg=C["content_bg"])
        self.emp_strip.pack(fill="x", pady=(0, 6))
        self.emp_tree = _tree(parent, C, [
            ("code", "Code", 55, "center"), ("name", "Name", 160, "w"), ("title", "Job Title", 105, "w"),
            ("dept", "Dept", 80, "w"), ("nat", "Nationality", 75, "center"), ("basic", "Basic", 70, "e"),
            ("wage", "Monthly wage", 85, "e"), ("docs", "Documents", 130, "w"), ("status", "Status", 50, "center")])
        self.emp_tree.tag_configure("bad", foreground=C["danger"])
        self.emp_tree.tag_configure("due", foreground=C.get("warning", "#B45309"))
        self.emp_tree.tag_configure("off", foreground=C["text_secondary"])
        self.emp_tree.bind("<Double-1>", lambda e: self._edit_emp())
        self._load_emps()

    def _strip(self):
        C = self.C
        for w in self.emp_strip.winfo_children():
            w.destroy()
        try:
            s = PR.staff_summary()
        except Exception:
            return
        self.staff = s
        items = [("👥 Employees", str(s["employees"]), C["primary"]),
                 ("🇸🇦 Saudis", "%d  (%.1f %%)" % (s["saudis"], s["saudi_pct"]), C.get("success", "#16A34A")),
                 ("💰 Monthly cost (wages + employer GOSI)", _m(s["monthly_cost"]), C["text_primary"]),
                 ("📄 Documents to renew", "%d%s" % (s["docs_due"], ("  (%d expired)" % s["docs_expired"])
                                                     if s["docs_expired"] else ""),
                  C["danger"] if s["docs_due"] else C.get("success", "#16A34A"))]
        for lbl, val, col in items:
            card = tk.Frame(self.emp_strip, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 8))
            tk.Label(card, text=lbl, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=10, pady=(4, 0))
            tk.Label(card, text=val, font=("Segoe UI", 12, "bold"), bg=C["card_bg"], fg=col).pack(
                anchor="w", padx=10, pady=(0, 4))
            if lbl.startswith("📄"):
                for w in (card,) + tuple(card.winfo_children()):
                    w.bind("<Button-1>", lambda e: self.nb.select(self.t_docs))
                    w.configure(cursor="hand2")

    def _load_emps(self):
        tv = self.emp_tree
        tv.delete(*tv.get_children())
        try:
            rows = db.fetchall(
                "SELECT e.*, ISNULL(d.name_en,'—') AS dept FROM employees e LEFT JOIN departments d "
                "ON e.department_id=d.department_id %s ORDER BY e.full_name_en"
                % ("" if self.emp_all.get() else "WHERE e.is_active=1"))
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            return
        q = self.emp_q.get().strip().lower()
        soon = {}
        for d in HT.expiring(include_all=True):
            if d.get("employee_id") not in soon:
                soon[d.get("employee_id")] = d
        alert = HT.doc_alert_days()
        for r in rows:
            r = dict(r)
            if r.get("employee_id") is None:          # not an employee row
                continue
            if q and q not in " ".join(str(r.get(k) or "") for k in
                                       ("employee_code", "full_name_en", "full_name_ar", "national_id",
                                        "job_title_en")).lower():
                continue
            d = soon.get(r["employee_id"])
            tag, docs = (), ""
            if d:
                if d["days_left"] < 0:
                    docs, tag = "✖ %s expired %s" % (d["doc"], d["date"]), ("bad",)
                elif d["days_left"] <= alert:
                    docs, tag = "⚠ %s in %d day(s)" % (d["doc"], d["days_left"]), ("due",)
                else:
                    docs = "✔ next: %s %s" % (d["doc"], d["date"])
            if not r.get("is_active"):
                tag = ("off",)
            tv.insert("", "end", iid=str(r["employee_id"]), tags=tag, values=(
                r.get("employee_code", ""), r.get("full_name_en", ""), r.get("job_title_en") or "—",
                r.get("dept", "—"), r.get("nationality") or "—", "{:,.0f}".format(float(r.get("basic_salary") or 0)),
                "{:,.0f}".format(PE.actual_wage(r, "actual")), docs, "✅" if r.get("is_active") else "⛔"))
        self._strip()

    @perm.guard("hr", "add")
    def _new_emp(self):
        EmployeeForm(self.frame, None, self._after_emp)

    @perm.guard("hr", "edit")
    def _edit_emp(self, employee_id=None):
        s = [employee_id] if employee_id else self.emp_tree.selection()
        if s and s[0]:
            EmployeeForm(self.frame, int(s[0]), self._after_emp)

    def _after_emp(self):
        self._load_emps()
        try:
            self.docs_tab.load()
        except Exception:
            pass

    # ═══════════════ PAYROLL ═══════════════
    def _build_payroll(self, parent, C):
        # row 1: which month + the month's steps in order (generate → approve → pay → GOSI)
        r1 = tk.Frame(parent, bg=C["content_bg"]); r1.pack(fill="x", pady=(10, 4))
        tk.Label(r1, text="Month", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.pr_month = tk.StringVar(value=str(date.today().month))          # the number (1–12)
        self.pr_month_name = tk.StringVar(value=PR.MONTHS[date.today().month])
        cb = ttk.Combobox(r1, textvariable=self.pr_month_name, values=PR.MONTHS[1:], state="readonly", width=11)
        cb.pack(side="left", padx=4)

        def _pick(_e=None):
            self.pr_month.set(str(PR.MONTHS.index(self.pr_month_name.get())))
            self._load_existing_run()
        cb.bind("<<ComboboxSelected>>", _pick)
        self.pr_month.trace_add("write", lambda *a: self.pr_month_name.set(
            PR.MONTHS[int(self.pr_month.get())] if str(self.pr_month.get()).isdigit()
            and 1 <= int(self.pr_month.get()) <= 12 else ""))
        tk.Label(r1, text="Year", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(8, 0))
        self.pr_year = tk.StringVar(value=str(date.today().year))
        cb = ttk.Combobox(r1, textvariable=self.pr_year, state="readonly", width=6,
                          values=[str(y) for y in range(date.today().year - 3, date.today().year + 2)])
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._load_existing_run())
        _btn(r1, C, "⚙ Generate", self._run_payroll, primary=True).pack_configure(padx=(10, 6))
        self.step_btns = {}
        _btn(r1, C, "↩ Reopen", self._reopen, side="right")
        for key, txt, cmd in (("gosi", "③ Pay GOSI", lambda: self._pay("gosi")),
                              ("pay", "② Pay salaries", lambda: self._pay("salaries")),
                              ("approve", "① Approve", self._approve)):
            self.step_btns[key] = _btn(r1, C, txt, cmd, side="right")
        # row 2: where the month is + changes + one menu for every print / file
        r2 = tk.Frame(parent, bg=C["content_bg"]); r2.pack(fill="x", pady=(0, 6))
        self.pr_status = tk.StringVar(value="")
        self.pr_status_lbl = tk.Label(r2, textvariable=self.pr_status, font=("Segoe UI", 9, "bold"),
                                      bg=C["primary_light"], fg=C["primary"], padx=10, pady=5, anchor="w")
        self.pr_status_lbl.pack(side="left", padx=(0, 8))
        mb = tk.Menubutton(r2, text="📤 Print / export  ▾", font=("Segoe UI", 9), bg=C["card_bg"],
                           fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                           highlightbackground=C["border"], highlightthickness=1)
        menu = tk.Menu(mb, tearoff=0, font=("Segoe UI", 10))
        for txt, cmd in (("🖨  Print the month", lambda: self._export_payroll("pdf")),
                         ("📥  Excel", lambda: self._export_payroll("excel")),
                         ("🧾  Payslip PDF (selected)", self._payslip_pdf),
                         ("📲  Send payslips on WhatsApp", self._send_payslips),
                         ("🏦  WPS / Mudad bank file", self._export_wps)):
            menu.add_command(label=txt, command=cmd)
        mb.configure(menu=menu)
        mb.pack(side="right")
        self.pr_menu = menu
        _btn(r2, C, "🗑 Delete month", self._delete_month, side="right", danger=True)
        _btn(r2, C, "✏ Change line", self._edit_line, side="right")
        self.pr_summary = tk.Frame(parent, bg=C["content_bg"])
        self.pr_summary.pack(fill="x", pady=(0, 6))
        self.pay_tree = _tree(parent, C, [
            ("emp", "Employee", 160, "w"), ("basic", "Basic", 75, "e"), ("allow", "Allowances", 80, "e"),
            ("oth", "OT h", 45, "e"), ("ot", "Overtime", 70, "e"), ("bonus", "Bonus", 65, "e"),
            ("gross", "Gross", 85, "e"), ("gosi", "GOSI", 70, "e"), ("absent", "Absent / sick", 85, "e"),
            ("loan", "Loan", 65, "e"), ("other", "Other", 60, "e"), ("net", "Net Pay", 90, "e")])
        self.pay_tree.configure(selectmode="extended")
        self.pay_tree.bind("<Double-1>", lambda e: self._edit_line())
        self._current_run_id = None
        self._load_existing_run()

    def _summary_cards(self, tt):
        C = self.C
        for w in self.pr_summary.winfo_children():
            w.destroy()
        items = [("💰 Gross", tt.get("gross", 0), C["primary"]),
                 ("📥 GOSI (employee + employer)", tt.get("gosi_employee", 0) + tt.get("gosi_employer", 0), C["info"]),
                 ("➖ Deductions", tt.get("deductions", 0), C["warning"]),
                 ("✅ Net to pay", tt.get("net", 0), C["success"])]
        if tt.get("overtime"):
            items.insert(1, ("⏱ Overtime", tt["overtime"], C["text_primary"]))
        for label, val, color in items:
            card = tk.Frame(self.pr_summary, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 8))
            tk.Label(card, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=10, pady=(4, 0))
            tk.Label(card, text=_m(val), font=("Segoe UI", 13, "bold"), bg=C["card_bg"],
                     fg=color).pack(anchor="w", padx=10, pady=(0, 4))

    def _period(self):
        return int(self.pr_month.get()), int(self.pr_year.get())

    def _load_existing_run(self):
        m, y = self._period()
        try:
            run = PR.run_of(m, y)
        except Exception:
            run = None
        self.pay_tree.delete(*self.pay_tree.get_children())
        self._pay_rows = []
        if not run or run.get("run_id") is None:
            self._current_run_id = None
            self._summary_cards({})
            self.pr_status.set("No payroll for %s %d yet — press ⚙ Generate" % (PR.MONTHS[m], y))
            self._steps(None)
            return
        self._current_run_id = run["run_id"]
        self._render_run(run["run_id"])

    def _render_run(self, run_id):
        run = PR.run_by_id(run_id)
        self.pay_tree.delete(*self.pay_tree.get_children())
        self._pay_rows = []
        for r in PR.lines(run_id):
            allow = float(r["housing_allowance"] or 0) + float(r["transport_allowance"] or 0) + \
                float(r["other_allowance"] or 0)
            absent = float(r.get("absence_deduction") or 0) + float(r.get("sick_deduction") or 0)
            vals = (r["employee_name_en"], "{:,.0f}".format(float(r["basic_salary"] or 0)), "{:,.0f}".format(allow),
                    "%g" % float(r.get("overtime_hours") or 0), _m(r["overtime_amount"]), _m(r.get("bonus_amount")),
                    _m(r["gross_salary"]), _m(r["gosi_employee"]), _m(absent), _m(r["loan_deduction"]),
                    _m(r["other_deduction"]), _m(r["net_salary"]))
            self.pay_tree.insert("", "end", iid=str(r["payslip_id"]), values=vals)
            self._pay_rows.append(list(vals))
        tt = PR.totals(run_id)
        self._summary_cards(tt)
        st = PR.STATUS.get(run.get("status") or "draft", run.get("status"))
        extra = []
        if run.get("paid_at"):
            extra.append("salaries paid %s" % str(run["paid_at"])[:10])
        if run.get("gosi_paid_at"):
            extra.append("GOSI paid %s" % str(run["gosi_paid_at"])[:10])
        self.pr_status.set("%s · %s%s" % (run["run_label"], st, (" · " + " · ".join(extra)) if extra else
                                          ("  (double-click a line to change it)" if (run.get("status") or "draft")
                                           == "draft" else "")))
        self._steps(run)

    def _steps(self, run=None):
        """The next step of the month is the blue button; done steps show ✔."""
        C = self.C
        st = (run or {}).get("status") or ""
        done = {"approve": st in ("approved", "paid"), "pay": st == "paid" or bool((run or {}).get("paid_at")),
                "gosi": bool((run or {}).get("gosi_paid_at"))}
        nxt = None if not run else next((k for k in ("approve", "pay", "gosi") if not done[k]), None)
        base = {"approve": "Approve", "pay": "Pay salaries", "gosi": "Pay GOSI"}
        for i, k in enumerate(("approve", "pay", "gosi"), 1):
            b = self.step_btns.get(k)
            if not b:
                continue
            if done[k]:
                b.config(text="✔ " + base[k], bg=C["card_bg"], fg=C["success"], highlightthickness=1,
                         font=("Segoe UI", 9))
            elif k == nxt:
                b.config(text="%s %s" % ("①②③"[i - 1], base[k]), bg=C["primary"], fg="white",
                         highlightthickness=0, font=("Segoe UI", 9, "bold"))
            else:
                b.config(text="%s %s" % ("①②③"[i - 1], base[k]), bg=C["card_bg"], fg=C["text_secondary"],
                         highlightthickness=1, font=("Segoe UI", 9))

    @perm.guard("hr", "add")
    def _run_payroll(self):
        m, y = self._period()
        try:
            try:
                run_id, msg = PR.generate(m, y)
            except PR.RunExists:
                # v6.9.3: the old month and its journal are DELETED first →
                # hr.delete + typing the month
                if not perm.allowed("hr", "delete", parent=self.frame):
                    return
                from ui import danger
                word = _month_word(m, y)
                if not danger.confirm_typed(
                        self.frame, "Make the payroll again",
                        "The payroll of %s %d is there already.\n\nMaking it again DELETES it and its "
                        "journal first (loan instalments are given back), then makes it new — "
                        "line changes (overtime, bonus, deductions) are lost." % (PR.MONTHS[m], y),
                        word=word):
                    return
                run_id, msg = PR.generate(m, y, replace=True)
                danger.audit("regenerate", "payroll", run_id, "Payroll %s made again" % word)
        except ValueError as e:
            messagebox.showwarning("Payroll", str(e), parent=self.frame)
            return
        except Exception as e:
            messagebox.showerror("Payroll Error", str(e)[:300], parent=self.frame)
            return
        self._current_run_id = run_id
        self._render_run(run_id)
        self._toast("✔ " + msg)

    def _toast(self, msg, kind="success"):
        try:
            from ui.ui_polish import toast
            toast(self.frame.winfo_toplevel(), msg, kind, 3500)
        except Exception:
            pass

    def _need_run(self):
        if not self._current_run_id:
            messagebox.showinfo("Payroll", "Generate the payroll of this month first.", parent=self.frame)
            return False
        return True

    @perm.guard("hr", "edit")
    def _edit_line(self):
        if not self._need_run():
            return None
        sel = self.pay_tree.selection()
        if not sel:
            messagebox.showinfo("Payroll", "Select an employee line first.", parent=self.frame)
            return None
        run = PR.run_by_id(self._current_run_id)
        if (run.get("status") or "draft") != "draft":
            messagebox.showinfo("Payroll", "%s is %s — press ↩ Reopen to change it." % (run["run_label"], run["status"]),
                                parent=self.frame)
            return None
        return PayLineDialog(self.frame, int(sel[0]), lambda: self._render_run(self._current_run_id))

    @perm.guard("hr", "approve")
    def _approve(self):
        if self._need_run():
            PR.approve(self._current_run_id)
            self._render_run(self._current_run_id)

    @perm.guard("hr", "approve")
    def _pay(self, what, method=None):
        if not self._need_run():
            return None
        run = PR.run_by_id(self._current_run_id)
        tt = PR.totals(self._current_run_id)
        amt = tt["net"] if what == "salaries" else tt["gosi_employee"] + tt["gosi_employer"]
        if method is None:
            ans = messagebox.askyesnocancel(
                "Pay " + ("salaries" if what == "salaries" else "GOSI"),
                "%s of %s: %s SAR\n\nPaid from the BANK?\n(Yes = bank transfer · No = cash · Cancel = not now)"
                % ("Net salaries" if what == "salaries" else "GOSI (both shares)", run["run_label"], _m(amt)),
                parent=self.frame)
            if ans is None:
                return None
            method = "bank" if ans else "cash"
        try:
            if what == "salaries":
                PR.pay_salaries(self._current_run_id, method)
            else:
                PR.pay_gosi(self._current_run_id, method)
        except ValueError as e:
            messagebox.showinfo("Payroll", str(e), parent=self.frame)
            return None
        self._render_run(self._current_run_id)
        self._toast("✔ %s paid (%s) — in the books" % ("Salaries" if what == "salaries" else "GOSI", method))
        return True

    @perm.guard("hr", "approve")
    def _reopen(self):
        if self._need_run() and messagebox.askyesno(
                "Reopen", "Open the month again for changes?\nThe payments of salaries / GOSI are taken out of "
                          "the books (pay again after the change).", parent=self.frame):
            PR.reopen(self._current_run_id)
            self._render_run(self._current_run_id)

    @perm.guard("hr", "delete")
    def _delete_month(self):
        if not self._need_run():
            return
        from ui import danger
        run = PR.run_by_id(self._current_run_id) or {}
        try:
            word = _month_word(run["run_month"], run["run_year"])
        except Exception:
            word = _month_word(*self._period())
        if not danger.gate(self.frame, "hr", "delete", "Delete payroll month",
                           "Delete the payroll of %s? Loan instalments are given back and its "
                           "journal is removed." % (run.get("run_label") or word), word=word):
            return
        try:
            PR.delete(self._current_run_id)
        except ValueError as e:
            messagebox.showinfo("Payroll", str(e), parent=self.frame)
            return
        self._load_existing_run()

    @perm.guard("hr", "export")
    def _export_payroll(self, mode="excel"):
        rows = getattr(self, "_pay_rows", [])
        if not rows:
            messagebox.showinfo("Nothing to export", "Generate payroll first.", parent=self.frame)
            return
        headers = ["Employee", "Basic", "Allowances", "OT h", "Overtime", "Bonus", "Gross", "GOSI",
                   "Absent / sick", "Loan", "Other", "Net Pay"]
        title = "Payroll Register %s/%s" % (self.pr_month.get(), self.pr_year.get())
        try:
            if mode == "pdf":
                from modules.report_export import export_pdf
                export_pdf(self.frame, "Payroll_Register", headers, rows, title=title)
            else:
                from modules.report_export import export_excel
                export_excel(self.frame, "Payroll_Register", headers, rows, title=title)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self.frame)

    @perm.guard("hr", "export")
    def _export_wps(self, path=None):
        if not self._need_run():
            return None
        rows = PR.wps_rows(self._current_run_id)
        bad = [r for r in rows if r["problems"]]
        if bad and path is None:
            txt = "\n".join("• %s: %s" % (r["name"], "; ".join(r["problems"])) for r in bad[:12])
            if not messagebox.askyesno("WPS file", "%d employee(s) need a fix (HR ▸ Employees ▸ edit):\n\n%s\n\n"
                                       "The bank / Mudad will refuse these lines. Save the file anyway?"
                                       % (len(bad), txt), parent=self.frame):
                return None
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("WPS CSV", "*.csv")],
                                                initialfile=PR.wps_filename(self._current_run_id))
            if not path:
                return None
        try:
            PR.write_wps(self._current_run_id, path)
        except Exception as e:
            messagebox.showerror("WPS Error", str(e), parent=self.frame)
            return None
        messagebox.showinfo(t("common.success"), "WPS file saved (%d employees):\n%s\n\nUpload it in your bank's "
                            "payroll service or in Mudad (check the layout with your bank once)."
                            % (len(rows), path), parent=self.frame)
        return path

    def _payslip_pdf(self):
        sel = self.pay_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an employee line first.", parent=self.frame)
            return None
        try:
            ps = db.fetchone("SELECT * FROM payslips WHERE payslip_id=?", (int(sel[0]),))
            run = PR.run_by_id(self._current_run_id)
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                                initialfile=f"Payslip_{ps['employee_name_en']}_{run['run_label']}.pdf")
            if not path:
                return None
            path = PR.payslip_pdf(int(sel[0]), path=path)
            try:
                os.startfile(path)
            except Exception:
                pass
            return path
        except Exception as e:
            messagebox.showerror("Payslip Error", str(e), parent=self.frame)
            return None

    @perm.guard("hr", "print")
    def _send_payslips(self):
        if not self._need_run():
            return None
        from modules import whatsapp as wa
        if not wa.enabled():
            messagebox.showinfo("WhatsApp", "Turn WhatsApp on first: Settings ▸ WhatsApp.", parent=self.frame)
            return None
        sel = list(self.pay_tree.selection())
        if not sel:
            if wa.mode() != "api":
                messagebox.showinfo("WhatsApp", "Select the employee line(s) to send (WhatsApp app: one chat "
                                    "opens for each).", parent=self.frame)
                return None
            if not messagebox.askyesno("WhatsApp", "Send every payslip of this month on WhatsApp?",
                                       parent=self.frame):
                return None
            sel = list(self.pay_tree.get_children())
        res = [PR.send_payslip(int(i)) for i in sel]
        ok = sum(1 for r in res if r[0])
        msg = "%d of %d payslip(s) sent / opened." % (ok, len(res))
        bad = [m for o, m in res if not o]
        if bad:
            msg += "\n\n" + "\n".join("• " + b for b in bad[:8])
        messagebox.showinfo("WhatsApp", msg, parent=self.frame)
        return res

    # ═══════════════ LOANS ═══════════════
    def _build_loans(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(10, 8))
        tk.Label(bar, text="A loan / salary advance is paid out now and taken back in the payroll, a monthly "
                           "instalment at a time.", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        _btn(bar, C, "＋ New Loan / Advance", self._new_loan, primary=True, side="right")
        self.loan_tree = _tree(parent, C, [
            ("emp", "Employee", 200, "w"), ("date", "Date", 100, "center"), ("amount", "Loan Amount", 110, "e"),
            ("monthly", "Monthly", 100, "e"), ("balance", "Balance", 110, "e"), ("status", "Status", 100, "center"),
            ("notes", "Notes", 200, "w")])
        self._load_loans()

    def _load_loans(self):
        self.loan_tree.delete(*self.loan_tree.get_children())
        try:
            rows = db.fetchall("SELECT l.*, e.full_name_en FROM employee_loans l JOIN employees e ON "
                               "l.employee_id=e.employee_id ORDER BY l.is_settled, l.loan_date DESC")
        except Exception:
            rows = []
        for r in rows:
            self.loan_tree.insert("", "end", iid=str(r["loan_id"]), values=(
                r["full_name_en"], str(r.get("loan_date", ""))[:10], _m(r["loan_amount"]),
                _m(r["monthly_deduction"]), _m(r["balance"]),
                "✅ Settled" if r.get("is_settled") else "🔄 Active", r.get("notes") or ""))

    @perm.guard("hr", "add")
    def _new_loan(self):
        return LoanForm(self.frame, self._load_loans)

    # ═══════════════ END OF SERVICE ═══════════════
    def _build_eos(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(10, 8))
        tk.Label(bar, text="End-of-service award (arts. 84–87, last actual wage) + unused annual leave (art. 111) "
                           "− loans still owed.", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        _btn(bar, C, "🧮 Final settlement", self._calc_eos, primary=True, side="right")
        self.eos_tree = _tree(parent, C, [
            ("emp", "Employee", 170, "w"), ("join", "Join", 90, "center"), ("end", "Last day", 90, "center"),
            ("years", "Years", 55, "center"), ("wage", "Wage", 85, "e"), ("reason", "Reason", 120, "w"),
            ("award", "Award", 90, "e"), ("leave", "Leave pay", 85, "e"), ("loan", "Loans", 75, "e"),
            ("net", "Net paid", 95, "e")])
        self._load_eos()

    def _load_eos(self):
        self.eos_tree.delete(*self.eos_tree.get_children())
        try:
            rows = db.fetchall("SELECT * FROM eos_settlements ORDER BY settled_at DESC")
        except Exception:
            rows = []
        names = dict(PE.EOS_REASONS)
        for r in rows:
            r = dict(r)
            net = r.get("net_settlement")
            self.eos_tree.insert("", "end", iid=str(r["eos_id"]), values=(
                r.get("employee_name_en", ""), str(r.get("join_date", ""))[:10], str(r.get("end_date", ""))[:10],
                "%.2f" % float(r.get("years_served") or 0), "{:,.0f}".format(float(r.get("last_salary") or 0)),
                (names.get(r.get("reason")) or r.get("reason") or "").split(" — ")[0].split(" (")[0],
                _m(r.get("gratuity_amount")), _m(r.get("leave_pay")), _m(r.get("loan_recovered")),
                _m(net if net is not None else r.get("gratuity_amount"))))

    @perm.guard("hr", "edit")
    def _calc_eos(self):
        return EOSDialog(self.frame, self._after_eos)

    def _after_eos(self):
        self._load_eos()
        self._load_emps()
        self._load_loans()


# ─────────────────────────────────────────────────────────────
# DOCUMENTS TAB
# ─────────────────────────────────────────────────────────────
class DocumentsTab:
    def __init__(self, parent, C, view):
        self.C, self.view = C, view
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        bar = tk.Frame(self.frame, bg=C["content_bg"]); bar.pack(fill="x", pady=(10, 6))
        self.show = tk.StringVar(value="Expired or due within %d days" % HT.doc_alert_days())
        cb = ttk.Combobox(bar, textvariable=self.show, state="readonly", width=30,
                          values=["Expired or due within %d days" % HT.doc_alert_days(), "All documents"])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.load())
        self.info = tk.StringVar()
        tk.Label(bar, textvariable=self.info, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=10)
        _btn(bar, C, "✏ Edit employee", self._edit, side="right")
        self.tree = _tree(self.frame, C, [
            ("code", "Code", 70, "center"), ("name", "Employee", 200, "w"), ("doc", "Document", 140, "w"),
            ("date", "Expires", 100, "center"), ("left", "Days left", 90, "e"), ("todo", "", 260, "w")])
        self.tree.tag_configure("bad", foreground=C["danger"])
        self.tree.tag_configure("due", foreground=C.get("warning", "#B45309"))
        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.load()

    def load(self):
        allr = self.show.get().startswith("All")
        rows = HT.expiring(include_all=allr)
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            tag = ("bad",) if r["days_left"] < 0 else (("due",) if r["days_left"] <= HT.doc_alert_days() else ())
            todo = "EXPIRED — renew now" if r["days_left"] < 0 else ("renew soon" if tag else "")
            self.tree.insert("", "end", iid="%d:%d" % (r["employee_id"], i), tags=tag, values=(
                r["code"], r["name"], r["doc"], r["date"], r["days_left"], todo))
        self.rows = rows
        self.info.set("%d document(s)" % len(rows) if rows else
                      "✔ Nothing expires within %d days (type the dates in HR ▸ Employees ▸ edit)" % HT.doc_alert_days())

    def _edit(self):
        sel = self.tree.selection()
        if sel:
            self.view._edit_emp(int(sel[0].split(":")[0]))


# ─────────────────────────────────────────────────────────────
# CHANGE ONE PAYSLIP LINE
# ─────────────────────────────────────────────────────────────
class PayLineDialog:
    def __init__(self, parent, payslip_id, on_done=None):
        C = self.C = cfg.theme()
        self.pid, self.on_done = payslip_id, on_done
        p = dict(db.fetchone("SELECT * FROM payslips WHERE payslip_id=?", (payslip_id,)))
        run = PR.run_by_id(p["run_id"])
        self.p = p
        w = self.win = tk.Toplevel(parent)
        w.title("Payroll line")
        w.configure(bg=C["content_bg"])
        w.bind("<Escape>", lambda e: w.destroy())
        try:
            w.transient(parent.winfo_toplevel()); w.grab_set()
        except Exception:
            pass
        hdr = tk.Frame(w, bg=C["primary"]); hdr.pack(fill="x")
        tk.Label(hdr, text="✏  %s — %s" % (p["employee_name_en"], run["run_label"]), font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=14, pady=10)
        body = tk.Frame(w, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=18, pady=10)
        att = HT.overtime_hours(p["employee_id"], run["run_year"], run["run_month"])
        e = db.fetchone("SELECT * FROM employees WHERE employee_id=?", (p["employee_id"],)) or {}
        rate = PE.overtime_rate(dict(e)) if e else 0
        self.vars = {}
        for key, label, val, hint in (
                ("ot", "Overtime hours", p.get("overtime_hours"),
                 "from attendance: %g h · %s SAR an hour (art. 107: hourly wage + 50 %% of hourly basic)"
                 % (att, _m(rate))),
                ("bonus", "Bonus / commission (SAR)", p.get("bonus_amount"), "added to the salary"),
                ("other", "Other deduction (SAR)", p.get("other_deduction"),
                 "e.g. a penalty — absent / unpaid / sick days are worked out by themselves"),
                ("note", "Note (shows on the payslip list)", p.get("notes") or "", "")):
            tk.Label(body, text=label, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                     fg=C["text_primary"]).pack(anchor="w", pady=(6, 0))
            v = tk.StringVar(value=("%g" % float(val or 0)) if key != "note" else str(val))
            tk.Entry(body, textvariable=v, font=("Segoe UI", 11), relief="solid", bd=1,
                     width=34).pack(anchor="w", ipady=3)
            if hint:
                tk.Label(body, text=hint, font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"],
                         wraplength=430, justify="left").pack(anchor="w")
            self.vars[key] = v
        self.msg = tk.StringVar(value="Absent / unpaid days %g · %s SAR   ·   sick leave not paid %s SAR   ·   loan %s"
                                % (float(p.get("absence_days") or 0), _m(p.get("absence_deduction")),
                                   _m(p.get("sick_deduction")), _m(p.get("loan_deduction"))))
        tk.Label(body, textvariable=self.msg, font=("Segoe UI", 9), bg=C["content_bg"], fg=C["primary"],
                 wraplength=430, justify="left").pack(anchor="w", pady=(10, 0))
        bot = tk.Frame(w, bg=C["card_bg"]); bot.pack(fill="x", side="bottom")
        _btn(bot, C, "💾 Save", self.save, primary=True, side="right").pack_configure(pady=10, padx=12)
        _btn(bot, C, "Cancel", w.destroy, side="right").pack_configure(pady=10)
        w.update_idletasks()
        w.geometry("500x470")

    def save(self):
        if not perm.allowed("hr", "edit", parent=self.win):
            return None
        try:
            ps = PR.edit_line(self.pid, overtime_hours=self.vars["ot"].get() or 0, bonus=self.vars["bonus"].get() or 0,
                              other_deduction=self.vars["other"].get() or 0, note=self.vars["note"].get())
        except ValueError as e:
            self.msg.set("⚠ " + str(e))
            return None
        except Exception as e:
            self.msg.set("⚠ " + str(e)[:200])
            return None
        self.win.destroy()
        if self.on_done:
            self.on_done()
        return ps


# ─────────────────────────────────────────────────────────────
# EMPLOYEE FORM
# ─────────────────────────────────────────────────────────────
class EmployeeForm:
    def __init__(self, parent, employee_id=None, on_save=None):
        self.employee_id = employee_id
        self.on_save = on_save
        self.fields = {}
        self.depts = []
        C = self.C = cfg.theme()
        title = "Edit Employee" if employee_id else "New Employee"
        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title(title)
        self.win.configure(bg=C["content_bg"])
        _modal(self.win, parent)
        sh = self.win.winfo_screenheight()
        self._center(880, min(700, sh - 80))
        hdr = tk.Frame(self.win, bg=C["primary"], height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"👤  {title}", font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=20)
        try:
            self.depts = db.fetchall("SELECT department_id, name_en FROM departments WHERE is_active=1")
        except Exception:
            self.depts = []
        self.v66 = PR._has("employees", "iqama_expiry")

        footer = tk.Frame(self.win, bg=C["card_bg"])
        footer.pack(fill="x", side="bottom")
        inner = tk.Frame(footer, bg=C["card_bg"]); inner.pack(fill="x", padx=20, pady=10)
        self.status_var = tk.StringVar()
        tk.Label(inner, textvariable=self.status_var, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["danger"], wraplength=520, justify="left").pack(side="left")
        tk.Button(inner, text=t("common.cancel"), font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(inner, text="💾 Save", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=18, pady=7, cursor="hand2",
                  command=self._save).pack(side="right")

        # scrollable body (small screens)
        wrap = tk.Frame(self.win, bg=C["content_bg"]); wrap.pack(fill="both", expand=True)
        cv = tk.Canvas(wrap, bg=C["content_bg"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        body = tk.Frame(cv, bg=C["content_bg"])
        win_id = cv.create_window((0, 0), window=body, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.bind("<Configure>", lambda ev: cv.itemconfig(win_id, width=ev.width))
        body.bind("<Configure>", lambda ev: cv.configure(scrollregion=cv.bbox("all")))
        sb.pack(side="right", fill="y"); cv.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=6)
        self.body, self.canvas = body, cv
        for c_ in range(3):
            body.columnconfigure(c_, weight=1, uniform="emp")
        row = [0]

        def head(text):
            row[0] += 1
            tk.Label(body, text=text, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                     fg=C["primary"]).grid(row=row[0], column=0, columnspan=3, sticky="w", pady=(10, 0), padx=6)
            row[0] += 1

        def fld(label, key, col, req=False, rtl=False, date_=False):
            cell = tk.Frame(body, bg=C["content_bg"])
            cell.grid(row=row[0], column=col, sticky="ew", padx=6, pady=4)
            tk.Label(cell, text=label + (" *" if req else ""), font=("Segoe UI", 9, "bold" if req else "normal"),
                     bg=C["content_bg"], fg=C["primary"] if req else C["text_secondary"]).pack(anchor="w")
            var = tk.StringVar()
            self.fields[key] = var
            ent = tk.Entry(cell, textvariable=var, font=("Segoe UI", 10), bg="white",
                           relief="solid", bd=1, justify="right" if rtl else "left")
            ent.pack(fill="x", ipady=4)
            self._cells[key] = cell
            if date_:
                try:
                    from ui.datefield import DateBox
                    DateBox(ent, var)
                except Exception:
                    pass
            return cell

        def combo(label, var, values, col):
            cell = tk.Frame(body, bg=C["content_bg"])
            cell.grid(row=row[0], column=col, sticky="ew", padx=6, pady=4)
            tk.Label(cell, text=label, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
            cb = ttk.Combobox(cell, textvariable=var, values=values, state="readonly", font=("Segoe UI", 10))
            cb.pack(fill="x", ipady=3)
            return cb

        def live_check(key, test, ok_text, bad_text):
            """A line under the field that says right away if it looks right."""
            cell = self._cells[key]
            lbl = tk.Label(cell, text="", font=("Segoe UI", 8), bg=C["content_bg"], anchor="w")
            lbl.pack(anchor="w")

            def upd(*_a):
                v = self.fields[key].get().strip()
                if not v:
                    lbl.config(text="")
                elif test(v):
                    lbl.config(text="✓ " + ok_text, fg=C["success"])
                else:
                    lbl.config(text="✗ " + bad_text, fg=C["danger"])
            self.fields[key].trace_add("write", upd)
            self._checks[key] = lbl
        self._cells, self._checks = {}, {}

        head("— Personal —")
        fld("Employee Code", "employee_code", 0, req=True)
        fld("Full Name (EN)", "full_name_en", 1, req=True)
        fld("الاسم (عربي)", "full_name_ar", 2, rtl=True)
        row[0] += 1
        fld("Iqama / National ID (10 digits)", "national_id", 0)
        live_check("national_id", PR.id_ok, "looks right", "10 digits, starting with 1 (Saudi) or 2 (Iqama)")
        fld("Nationality", "nationality", 1)
        sc = tk.Frame(body, bg=C["content_bg"]); sc.grid(row=row[0], column=2, sticky="w", padx=6)
        self.saudi_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sc, text="🇸🇦 Saudi National", variable=self.saudi_var, font=("Segoe UI", 9),
                       bg=C["content_bg"], activebackground=C["content_bg"]).pack(anchor="w", pady=(16, 0))
        self.gender_var = tk.StringVar()
        if self.v66:
            row[0] += 1
            fld("Mobile (payslips on WhatsApp)", "phone", 0)
            fld("Email", "email", 1)
            combo("Gender", self.gender_var, ["", "Male", "Female"], 2)
            row[0] += 1
            fld("Birth date (YYYY-MM-DD)", "birth_date", 0, date_=True)

        head("— Job —")
        fld("Job Title (EN)", "job_title_en", 0)
        fld("Job Title (AR)", "job_title_ar", 1, rtl=True)
        self.dept_var = tk.StringVar()
        combo("Department", self.dept_var, ["— None —"] + [d["name_en"] for d in self.depts], 2)
        row[0] += 1
        fld("Join Date (YYYY-MM-DD)", "join_date", 0, date_=True)
        if self.v66:
            fld("Contract ends (empty = open)", "contract_end", 1, date_=True)
        self.gosi_var = tk.StringVar(value="Old (before 3 Jul 2024)")
        self.gosi_cb = combo("GOSI system (Saudis)", self.gosi_var,
                             ["Old (before 3 Jul 2024)", "New (from 3 Jul 2024)"], 2)
        self._gosi_touched = False
        self.gosi_cb.bind("<<ComboboxSelected>>", lambda e: setattr(self, "_gosi_touched", True))
        self.v66b = PR._has("employees", "probation_days")
        self.ramadan_var = tk.BooleanVar(value=True)
        self.resign_status = tk.StringVar(value=HT.RESIGN_STATUS[0][1])
        if self.v66b:                         # v6.6: probation (2025: up to 180 days) + Ramadan hours
            row[0] += 1
            fld("Probation (days, at most 180)", "probation_days", 0)
            self.prob_lbl = tk.Label(body, text="", font=("Segoe UI", 9), bg=C["content_bg"], fg=C["primary"],
                                     anchor="w", justify="left")
            self.prob_lbl.grid(row=row[0], column=1, sticky="w", padx=6)
            rc = tk.Frame(body, bg=C["content_bg"]); rc.grid(row=row[0], column=2, sticky="w", padx=6)
            tk.Checkbutton(rc, text="Ramadan hours (%g a day, art. 98)" % (HT.ramadan_hours() or 6),
                           variable=self.ramadan_var, font=("Segoe UI", 9), bg=C["content_bg"],
                           activebackground=C["content_bg"]).pack(anchor="w", pady=(16, 0))
            for k in ("probation_days", "join_date"):
                self.fields[k].trace_add("write", lambda *a: self._prob_hint())

        # v7.4: the DayBill user this employee signs in with + their QR sign-in
        self.v74 = PR._has("employees", "user_id")
        self.user_link_var = tk.StringVar(value="— None —")
        self._user_choices = {}
        if self.v74:
            head("— Sign-in (DayBill user · 📱 QR on WhatsApp) —")
            try:
                taken = {r["user_id"] for r in (db.fetchall(
                    "SELECT user_id FROM employees WHERE user_id IS NOT NULL AND employee_id<>?",
                    (self.employee_id or 0,)) or [])}
                us = db.fetchall("SELECT user_id, username, full_name_en FROM users WHERE is_active=1 "
                                 "ORDER BY username") or []
            except Exception:
                taken, us = set(), []
            for u_ in us:
                if u_["user_id"] not in taken:
                    self._user_choices["%s · %s" % (u_["username"], u_.get("full_name_en") or "")] = u_["user_id"]
            self.user_cb = combo("DayBill user", self.user_link_var, ["— None —"] + list(self._user_choices), 0)
            if self.employee_id:
                try:
                    cur_uid = db.execute_scalar("SELECT user_id FROM employees WHERE employee_id=?",
                                                (self.employee_id,))
                except Exception:
                    cur_uid = None
                lab_ = next((k for k, v in self._user_choices.items() if v == cur_uid), None)
                if lab_:
                    self.user_link_var.set(lab_)
            bc = tk.Frame(body, bg=C["content_bg"]); bc.grid(row=row[0], column=1, columnspan=2, sticky="w", padx=6)
            tk.Button(bc, text="➕ Make a user for this employee", font=("Segoe UI", 9), relief="flat",
                      bg=C["card_bg"], cursor="hand2", command=self._make_user).pack(side="left", pady=(16, 0))
            tk.Button(bc, text="📱 QR sign-in…", font=("Segoe UI", 9, "bold"), relief="flat", bg=C["primary"],
                      fg="white", cursor="hand2", command=self._qr_login).pack(side="left", padx=6, pady=(16, 0))

        head("— Salary (SAR / month) —")
        fld("Basic Salary", "basic_salary", 0, req=True)
        fld("Housing Allowance", "housing_allowance", 1)
        fld("Transport Allowance", "transport_allowance", 2)
        row[0] += 1
        fld("Other Allowance", "other_allowance", 0)
        self.wage_lbl = tk.Label(body, text="", font=("Segoe UI", 9), bg=C["content_bg"], fg=C["primary"],
                                 justify="left", anchor="w")
        self.wage_lbl.grid(row=row[0], column=1, columnspan=2, sticky="w", padx=6)
        for k in ("basic_salary", "housing_allowance", "transport_allowance", "other_allowance"):
            self.fields[k].trace_add("write", lambda *a: self._wage_hint())

        head("— Bank (WPS) —")
        fld("Bank Name", "bank_name", 0)
        c_ = fld("IBAN (SA + 22 digits)", "iban", 1)
        c_.grid(columnspan=2, sticky="ew")
        live_check("iban", lambda v: PR.iban_ok(PR.clean_iban(v)),
                   "looks right", "SA + 22 digits (24 in all) — the WPS bank file needs it")

        if self.v66:
            head("— Documents (DayBill warns before they expire) —")
            fld("Iqama / ID expires", "iqama_expiry", 0, date_=True)
            fld("Passport No.", "passport_no", 1)
            fld("Passport expires", "passport_expiry", 2, date_=True)
            row[0] += 1
            fld("Medical insurance expires", "insurance_expiry", 0, date_=True)
            head("— Annual leave balance carried in (leave taken before DayBill) —")
            fld("Days left on that date", "leave_open_days", 0)
            fld("On date (YYYY-MM-DD)", "leave_open_date", 1, date_=True)
            tk.Label(body, text="Empty = DayBill counts the leave earned since the join date (21 days a year, "
                                "30 after 5 years) minus the annual leave saved in DayBill.",
                     font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"], justify="left",
                     wraplength=230).grid(row=row[0], column=2, sticky="w", padx=6)
        if self.v66b:                         # v6.6: resignation (2025 law)
            head("— Resignation (if the employee hands one in) —")
            fld("Handed in on (YYYY-MM-DD)", "resign_date", 0, date_=True)
            combo("Answer", self.resign_status, [x[1] for x in HT.RESIGN_STATUS], 1)
            self.resign_lbl = tk.Label(body, text="", font=("Segoe UI", 8), bg=C["content_bg"], fg=C["warning"],
                                       justify="left", anchor="w", wraplength=230)
            self.resign_lbl.grid(row=row[0], column=2, sticky="w", padx=6)
            self.fields["resign_date"].trace_add("write", lambda *a: self._resign_hint())
            self.resign_status.trace_add("write", lambda *a: self._resign_hint())
        row[0] += 1
        tk.Frame(body, bg=C["content_bg"], height=10).grid(row=row[0], column=0)

        def _wheel(ev):
            try:
                cv.yview_scroll(int(-ev.delta / 120) or (-1 if ev.num == 4 else 1), "units")
            except Exception:
                pass
        self.win.bind("<MouseWheel>", _wheel)
        if employee_id:
            self._load()

    def _wage_hint(self):
        try:
            e = {k: float(self.fields[k].get() or 0) for k in ("basic_salary", "housing_allowance",
                                                               "transport_allowance", "other_allowance")}
        except ValueError:
            self.wage_lbl.config(text="")
            return
        self.wage_lbl.config(text="Monthly wage %s · a day %s · overtime %s an hour"
                             % (_m(PE.actual_wage(e, "actual")), _m(PE.actual_wage(e, "actual") / 30.0),
                                _m(PE.overtime_rate(e))))

    def _prob_hint(self):
        try:
            emp = {"join_date": self.fields["join_date"].get(), "probation_days": self.fields["probation_days"].get()}
            raw = str(emp["probation_days"] or "").strip()
            if raw and (not raw.isdigit() or int(raw) > 180):
                self.prob_lbl.config(text="✗ at most 180 days (2025 law)", fg=self.C["danger"])
                return
            end = HT.probation_end(emp)
            if "180" in self.status_var.get():
                self.status_var.set("")
            self.prob_lbl.config(text=("Probation ends %s" % end.isoformat()) if end else "Type the join date",
                                 fg=self.C["primary"])
        except Exception:
            pass

    def _resign_status_key(self):
        return next((k for k, lbl in HT.RESIGN_STATUS if lbl == self.resign_status.get()), "waiting")

    def _resign_hint(self):
        try:
            info = HT.resignation({"resign_date": self.fields["resign_date"].get(),
                                   "resign_status": self._resign_status_key()})
            self.resign_lbl.config(text=info.get("text", ""))
        except Exception:
            pass

    def _load(self):
        d = db.fetchone("SELECT * FROM employees WHERE employee_id=?", (self.employee_id,))
        if not d:
            return
        d = dict(d)
        for k, v in self.fields.items():
            if d.get(k) is not None:
                v.set(str(d[k])[:10] if k.endswith(("_date", "_expiry", "_end")) else
                      ("%g" % float(d[k]) if k in ("leave_open_days", "basic_salary", "housing_allowance",
                                                    "transport_allowance", "other_allowance") else str(d[k])))
        self.saudi_var.set(bool(d.get("is_saudi", 0)))
        if self.v66b:
            self.ramadan_var.set(HT.ramadan_applies(d))
            self.resign_status.set(dict(HT.RESIGN_STATUS).get(d.get("resign_status") or "waiting"))
            if d.get("probation_days") is not None:
                self.fields["probation_days"].set(str(d["probation_days"]))
            self._prob_hint(); self._resign_hint()
        self.gender_var.set({"M": "Male", "F": "Female"}.get(d.get("gender") or "", ""))
        if d.get("gosi_system"):
            self.gosi_var.set("New (from 3 Jul 2024)" if d.get("gosi_system") == "new" else "Old (before 3 Jul 2024)")
            self._gosi_touched = True
        elif d.get("is_saudi"):
            if PE.guess_system(d.get("join_date")) == "new":
                self.gosi_var.set("New (from 3 Jul 2024)")
        if d.get("department_id"):
            for dep in self.depts:
                if dep["department_id"] == d["department_id"]:
                    self.dept_var.set(dep["name_en"]); break
        self._wage_hint()

    def _save(self, confirm=True):
        # v6.9.3: hr.edit for a change, hr.add for a new employee
        if not perm.allowed("hr", "edit" if self.employee_id else "add", parent=self.win):
            return False
        F = self.fields
        if not F["employee_code"].get().strip():
            self.status_var.set("⚠️ Code required."); return False
        if not F["full_name_en"].get().strip():
            self.status_var.set("⚠️ Name required."); return False

        def num(k):
            try:
                return float(F[k].get() or 0)
            except ValueError:
                return 0.0
        bad_dates = []

        def dt(k):
            v = F[k].get().strip() if k in F else ""
            if not v:
                return None
            d = HT._d(v)
            if not d:
                bad_dates.append(k)
                return None
            return d.isoformat()
        dept_id = next((dep["department_id"] for dep in self.depts if dep["name_en"] == self.dept_var.get()), None)
        data = {
            "employee_code": F["employee_code"].get().strip(),
            "full_name_en": F["full_name_en"].get().strip(),
            "full_name_ar": F["full_name_ar"].get().strip() or None,
            "national_id": F["national_id"].get().strip() or None,
            "nationality": F["nationality"].get().strip() or None,
            "is_saudi": 1 if self.saudi_var.get() else 0,
            "department_id": dept_id,
            "job_title_en": F["job_title_en"].get().strip() or None,
            "job_title_ar": F["job_title_ar"].get().strip() or None,
            "join_date": dt("join_date"),
            "basic_salary": num("basic_salary"),
            "housing_allowance": num("housing_allowance"),
            "transport_allowance": num("transport_allowance"),
            "other_allowance": num("other_allowance"),
            "bank_name": F["bank_name"].get().strip() or None,
            "iban": PR.clean_iban(F["iban"].get()) or None,
        }
        if not self.employee_id:
            data["is_active"] = 1
        if getattr(self, "v74", False):
            data["user_id"] = self._user_choices.get(self.user_link_var.get())
        if self.v66:
            data.update({"phone": F["phone"].get().strip() or None, "email": F["email"].get().strip() or None,
                         "gender": {"Male": "M", "Female": "F"}.get(self.gender_var.get()),
                         "birth_date": dt("birth_date"), "contract_end": dt("contract_end"),
                         "iqama_expiry": dt("iqama_expiry"), "passport_no": F["passport_no"].get().strip() or None,
                         "passport_expiry": dt("passport_expiry"), "insurance_expiry": dt("insurance_expiry"),
                         "leave_open_date": dt("leave_open_date"),
                         "leave_open_days": num("leave_open_days") if F["leave_open_days"].get().strip() else None})
            if data["leave_open_days"] is not None and not data["leave_open_date"]:
                self.status_var.set("⚠️ Type the date of the leave balance too."); return False
        if self.v66b:
            pdays = F["probation_days"].get().strip()
            if pdays and (not pdays.isdigit() or int(pdays) > 180):
                self.status_var.set("⚠️ Probation is at most 180 days (2025 law)."); return False
            data.update({"probation_days": int(pdays) if pdays else None,
                         "ramadan_hours": 1 if self.ramadan_var.get() else 0,
                         "resign_date": dt("resign_date"),
                         "resign_status": self._resign_status_key() if F["resign_date"].get().strip() else None})
        if bad_dates:
            self.status_var.set("⚠️ Dates are like 2026-10-31 (check: %s)." % ", ".join(
                k.replace("_", " ") for k in bad_dates)); return False
        warn = []
        if data["iban"] and not PR.iban_ok(data["iban"]):
            warn.append("the IBAN does not look right (SA + 22 digits)")
        if data["national_id"] and not PR.id_ok(data["national_id"]):
            warn.append("the Iqama / ID is not 10 digits starting with 1 or 2")
        if warn and confirm and not messagebox.askyesno("Check", "Please check: " + "; ".join(warn) +
                                                        ".\n\nThe WPS salary file needs them right. Save anyway?",
                                                        parent=self.win):
            return False
        try:
            if data["is_saudi"]:
                data["gosi_system"] = ("new" if self.gosi_var.get().startswith("New") else "old") \
                    if self._gosi_touched else PE.guess_system(data["join_date"])
            else:
                data["gosi_system"] = None
            if not PR._has("employees", "gosi_system"):
                data.pop("gosi_system", None)
        except Exception:
            data.pop("gosi_system", None)
        try:
            if self.employee_id:
                sc = ", ".join([f"{k}=?" for k in data])
                db.execute(f"UPDATE employees SET {sc}, updated_at=GETDATE() WHERE employee_id=?",
                           (*data.values(), self.employee_id))
            else:
                cols = ", ".join(data.keys()); ph = ", ".join(["?"] * len(data))
                db.execute(f"INSERT INTO employees ({cols}) VALUES ({ph})", tuple(data.values()))
        except Exception as e:
            err = str(e)
            self.status_var.set("❌ Code exists." if "UNIQUE" in err or "duplicate" in err.lower()
                                else f"❌ {err[:90]}")
            return False
        if confirm:
            messagebox.showinfo(t("common.success"), "Employee saved.", parent=self.win)
        if self.on_save:
            self.on_save()
        self.win.destroy()
        return True

    # ── v7.4: sign-in user + QR ───────────────────────────────
    def _make_user(self):
        """A DayBill user for this employee (they sign in with the QR)."""
        if not self.employee_id:
            messagebox.showinfo("DayBill user", "Save the employee first.", parent=self.win)
            return None
        if not perm.allowed("users", "add", parent=self.win):
            return None
        from modules import qr_login as Q
        try:
            uid = Q.create_user_for_employee(self.employee_id)
        except Exception as e:
            messagebox.showerror("DayBill user", str(e)[:200], parent=self.win)
            return None
        u = db.fetchone("SELECT username, full_name_en FROM users WHERE user_id=?", (uid,)) or {}
        lab = "%s · %s" % (u.get("username"), u.get("full_name_en") or "")
        self._user_choices[lab] = uid
        self.user_cb["values"] = ["— None —"] + list(self._user_choices)
        self.user_link_var.set(lab)
        self.status_var.set("✅ User '%s' made and linked — press 📱 QR sign-in to send the QR." % u.get("username"))
        return uid

    def _qr_login(self):
        uid = self._user_choices.get(self.user_link_var.get())
        if not uid:
            messagebox.showinfo("QR sign-in", "Pick the DayBill user (or ➕ make one) first.", parent=self.win)
            return None
        if self.employee_id:
            from modules import qr_login as Q
            Q.link_employee(self.employee_id, uid)
        from ui.qr_login_dialog import QrLoginDialog
        return QrLoginDialog(self.win, uid)

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{max(0, (sh-h)//2 - 20)}")


# ─────────────────────────────────────────────────────────────
# LOAN FORM
# ─────────────────────────────────────────────────────────────
class LoanForm:
    def __init__(self, parent, on_save=None):
        self.on_save = on_save
        C = cfg.theme()
        self.win = tk.Toplevel(parent); self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("New Loan / Advance")
        self.win.configure(bg=C["content_bg"])
        _modal(self.win, parent); self._center(460, 500)
        hdr = tk.Frame(self.win, bg=C["primary"], height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="🏦  New Loan / Advance", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)
        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", side="bottom")
        bi = tk.Frame(btns, bg=C["card_bg"]); bi.pack(fill="x", padx=20, pady=10)
        tk.Button(bi, text=t("common.cancel"), font=("Segoe UI", 10), bg=C["card_bg"], fg=C["text_secondary"],
                  relief="flat", padx=14, pady=7, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(bi, text="💾 Save & pay out", font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=18, pady=7, cursor="hand2", command=self._save).pack(side="right")
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=20, pady=10)
        try:
            self.emps = [dict(r) for r in db.fetchall("SELECT employee_id, full_name_en FROM employees "
                                                       "WHERE is_active=1 ORDER BY full_name_en") or []]
        except Exception:
            self.emps = []

        def lbl(text, req=True):
            tk.Label(body, text=text + (" *" if req else ""), font=("Segoe UI", 9, "bold" if req else "normal"),
                     bg=C["content_bg"], fg=C["primary"] if req else C["text_secondary"]).pack(anchor="w")
        lbl("Employee")
        self.emp_var = tk.StringVar()
        self.emp_cb = ttk.Combobox(body, textvariable=self.emp_var, values=[e["full_name_en"] for e in self.emps],
                                   font=("Segoe UI", 10), state="readonly")
        self.emp_cb.pack(fill="x", ipady=4, pady=(0, 8))
        lbl("Loan Amount (SAR)")
        self.amount_var = tk.StringVar()
        tk.Entry(body, textvariable=self.amount_var, font=("Segoe UI", 12), bg="white", relief="solid",
                 bd=1).pack(fill="x", ipady=4, pady=(0, 8))
        lbl("Monthly Instalment (SAR)")
        self.monthly_var = tk.StringVar()
        tk.Entry(body, textvariable=self.monthly_var, font=("Segoe UI", 12), bg="white", relief="solid",
                 bd=1).pack(fill="x", ipady=4, pady=(0, 8))
        lbl("Paid out from")
        self.method_var = tk.StringVar(value="Cash")
        ttk.Combobox(body, textvariable=self.method_var, values=["Cash", "Bank transfer"], state="readonly",
                     font=("Segoe UI", 10)).pack(fill="x", ipady=3, pady=(0, 8))
        lbl("Notes", req=False)
        self.notes_var = tk.StringVar()
        tk.Entry(body, textvariable=self.notes_var, font=("Segoe UI", 10), bg="white", relief="solid",
                 bd=1).pack(fill="x", ipady=4)
        self.status_var = tk.StringVar()
        tk.Label(body, textvariable=self.status_var, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["danger"]).pack(anchor="w", pady=4)

    def _save(self):
        if not perm.allowed("hr", "add", parent=self.win):
            return None
        if self.emp_cb.current() < 0:
            self.status_var.set("⚠️ Select employee."); return None
        try:
            amount, monthly = float(self.amount_var.get()), float(self.monthly_var.get())
            if amount <= 0 or monthly <= 0:
                raise ValueError
        except ValueError:
            self.status_var.set("⚠️ Enter valid amounts."); return None
        emp = self.emps[self.emp_cb.current()]
        try:
            lid = PR.give_loan(emp["employee_id"], amount, monthly,
                               "bank" if self.method_var.get().startswith("Bank") else "cash",
                               self.notes_var.get())
        except Exception as e:
            self.status_var.set(f"❌ {str(e)[:80]}"); return None
        if self.on_save:
            self.on_save()
        self.win.destroy()
        return lid

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ─────────────────────────────────────────────────────────────
# END OF SERVICE / FINAL SETTLEMENT
# ─────────────────────────────────────────────────────────────
class EOSDialog:
    def __init__(self, parent, on_save=None):
        self.on_save = on_save
        C = self.C = cfg.theme()
        self.win = tk.Toplevel(parent); self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("Final settlement")
        self.win.configure(bg=C["content_bg"])
        _modal(self.win, parent)
        sh = self.win.winfo_screenheight()
        self._center(640, min(720, sh - 60))
        hdr = tk.Frame(self.win, bg=C["primary"], height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="📤  Final settlement — end of service", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)
        bot = tk.Frame(self.win, bg=C["card_bg"]); bot.pack(fill="x", side="bottom")
        bi = tk.Frame(bot, bg=C["card_bg"]); bi.pack(fill="x", padx=16, pady=10)
        _btn(bi, C, "🧮 Calculate", self._calc)
        _btn(bi, C, "🖨 Print", self._print)
        _btn(bi, C, "💾 Save & settle", self._save, primary=True, side="right")
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=20, pady=8)
        try:
            self.emps = [dict(r) for r in db.fetchall("SELECT employee_id, full_name_en FROM employees WHERE "
                                                       "is_active=1 ORDER BY full_name_en") or []]
        except Exception:
            self.emps = []

        def lbl(text):
            tk.Label(body, text=text, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                     fg=C["primary"]).pack(anchor="w", pady=(4, 0))
        lbl("Employee *")
        self.emp_var = tk.StringVar()
        self.emp_cb = ttk.Combobox(body, textvariable=self.emp_var, values=[e["full_name_en"] for e in self.emps],
                                   font=("Segoe UI", 10), state="readonly")
        self.emp_cb.pack(fill="x", ipady=3)
        self.emp_cb.bind("<<ComboboxSelected>>", lambda e: (self.leave_var.set(""), self._from_resignation(),
                                                             self._calc()))
        row = tk.Frame(body, bg=C["content_bg"]); row.pack(fill="x", pady=(6, 0))
        a = tk.Frame(row, bg=C["content_bg"]); a.pack(side="left")
        tk.Label(a, text="Last working day *", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(anchor="w")
        self.end_var = tk.StringVar(value=date.today().isoformat())
        self._leave_auto = None
        # the leave days DayBill filled in follow a new last day (typed ones stay)
        self.end_var.trace_add("write", lambda *a: getattr(self, "leave_var", None) is not None
                               and self.leave_var.get() == self._leave_auto and self.leave_var.set(""))
        en = tk.Entry(a, textvariable=self.end_var, font=("Segoe UI", 10), width=14, relief="solid", bd=1)
        en.pack(anchor="w", ipady=3)
        try:
            from ui.datefield import DateBox
            DateBox(en, self.end_var)
        except Exception:
            pass
        b = tk.Frame(row, bg=C["content_bg"]); b.pack(side="left", padx=18)
        tk.Label(b, text="Unused annual leave days to pay", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(anchor="w")
        self.leave_var = tk.StringVar()
        tk.Entry(b, textvariable=self.leave_var, font=("Segoe UI", 10), width=10, relief="solid",
                 bd=1).pack(anchor="w", ipady=3)
        lbl("Reason")
        self.reason_var = tk.StringVar(value=PE.EOS_REASONS[0][1])
        rb = ttk.Combobox(body, textvariable=self.reason_var, values=[x[1] for x in PE.EOS_REASONS],
                          state="readonly", font=("Segoe UI", 9))
        rb.pack(fill="x", ipady=3)
        rb.bind("<<ComboboxSelected>>", lambda e: self._calc())
        # v6.6: notice not given (arts. 75–76) + art. 77
        nrow = tk.Frame(body, bg=C["content_bg"]); nrow.pack(fill="x", pady=(8, 0))
        tk.Label(nrow, text="Notice NOT given (days)", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left")
        self.notice_var = tk.StringVar(value="0")
        ne = tk.Entry(nrow, textvariable=self.notice_var, font=("Segoe UI", 10), width=6, relief="solid", bd=1)
        ne.pack(side="left", padx=(6, 10), ipady=3)
        ne.bind("<FocusOut>", lambda e: self._calc())
        self.notice_by = tk.StringVar(value="employer")
        for val, txt in (("employer", "shop ended it → pay the employee"),
                         ("employee", "employee left → take from the settlement")):
            tk.Radiobutton(nrow, text=txt, variable=self.notice_by, value=val, font=("Segoe UI", 9),
                           bg=C["content_bg"], activebackground=C["content_bg"],
                           command=self._calc).pack(side="left", padx=(0, 6))
        tk.Label(body, text="Open contracts: the shop gives 60 days' notice, the employee 30 (art. 75). "
                            "Days not given are paid as wages (art. 76).", font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"], wraplength=590, justify="left").pack(anchor="w")
        self.comp_var = tk.BooleanVar(value=False)
        tk.Checkbutton(body, text="Ended by the shop WITHOUT a valid reason — add art. 77 compensation "
                                  "(rest of a fixed contract, or 15 days a year; at least 2 months' wage)",
                       variable=self.comp_var, font=("Segoe UI", 9), bg=C["content_bg"], wraplength=590,
                       justify="left", activebackground=C["content_bg"], command=self._calc).pack(anchor="w", pady=(4, 0))
        self.result = tk.Frame(body, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        self.result.pack(fill="both", expand=True, pady=8)
        self.result_var = tk.StringVar(value="Choose the employee.")
        self._show_result(None, "Choose the employee.")
        self._last = None

    def _show_result(self, s, msg=""):
        """The breakdown: what is added, what is taken, the net — easy to read."""
        C = self.C
        for w in self.result.winfo_children():
            w.destroy()
        if not s:
            tk.Label(self.result, text=msg, font=("Segoe UI", 10), bg=C["card_bg"],
                     fg=C["danger"] if msg.startswith(("⚠", "❌")) else C["text_secondary"],
                     wraplength=560, justify="left").pack(anchor="w", padx=14, pady=12)
            return
        basis = "actual wage: basic + all allowances" if s["wage_basis"] == "actual" else "basic + housing"
        head = "Joined %s · last day %s · %.2f years of service" % (
            str(s["employee"].get("join_date"))[:10], s["end_date"], s["years"])
        tk.Label(self.result, text=head, font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=14, pady=(10, 0))
        sub = "Wage %s SAR a month (%s)" % (_m(s["wage"]), basis)
        if s.get("days_not_counted"):
            sub += " · %d days of unpaid leave not counted (art. 116)" % s["days_not_counted"]
        tk.Label(self.result, text=sub, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                 wraplength=580, justify="left").pack(anchor="w", padx=14)
        g = tk.Frame(self.result, bg=C["card_bg"]); g.pack(fill="x", padx=14, pady=(8, 4))
        g.columnconfigure(0, weight=1)
        rows = [("End-of-service award (%.0f %% of %s)" % (s["share"] * 100, _m(s["award_full"])), s["award"], "+")]
        if s["leave_pay"]:
            rows.append(("Unused annual leave · %g days × %s" % (s["leave_days"], _m(s["day_wage"])),
                         s["leave_pay"], "+"))
        if s.get("notice_pay"):
            rows.append(("Notice not given by the shop · %g days" % s["notice_days"], s["notice_pay"], "+"))
        if s.get("comp_77"):
            rows.append(("Compensation, art. 77 · %s" % s["comp_77_how"], s["comp_77"], "+"))
        if s.get("notice_taken"):
            rows.append(("Notice not given by the employee · %g days" % s["notice_days"], s["notice_taken"], "−"))
        if s["loan_recovered"]:
            rows.append(("Loans taken back (owed %s)" % _m(s["loan_owed"]), s["loan_recovered"], "−"))
        for i, (txt, amt, sign) in enumerate(rows):
            col = C["text_primary"] if sign == "+" else C["warning"]
            tk.Label(g, text=txt, font=("Segoe UI", 10), bg=C["card_bg"], fg=col, anchor="w").grid(
                row=i, column=0, sticky="w", pady=2)
            tk.Label(g, text=("− " if sign == "−" else "") + _m(amt), font=("Segoe UI", 10), bg=C["card_bg"],
                     fg=col, anchor="e").grid(row=i, column=1, sticky="e", pady=2)
        tk.Frame(self.result, bg=C["border"], height=1).pack(fill="x", padx=14, pady=(4, 4))
        nt = tk.Frame(self.result, bg=C["card_bg"]); nt.pack(fill="x", padx=14)
        tk.Label(nt, text="NET TO PAY", font=("Segoe UI", 12, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(side="left")
        tk.Label(nt, text="%s SAR" % _m(s["net"]), font=("Segoe UI", 15, "bold"), bg=C["card_bg"],
                 fg=C["success"]).pack(side="right")
        notes = []
        if s["loan_left"]:
            notes.append("The employee still owes %s SAR of loans." % _m(s["loan_left"]))
        if abs(s["leave_days"] - s.get("leave_auto", s["leave_days"])) > 0.01:
            notes.append("DayBill counted %g leave days — you typed %g." % (s["leave_auto"], s["leave_days"]))
        rs = HT.resignation(s["employee"]) if hasattr(HT, "resignation") else {}
        if rs.get("text"):
            notes.append(rs["text"] + ".")
        for n in notes:
            tk.Label(self.result, text="ℹ " + n, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                     wraplength=580, justify="left").pack(anchor="w", padx=14)

    def _reason(self):
        return next((k for k, v in PE.EOS_REASONS if v == self.reason_var.get()), "termination")

    def _from_resignation(self):
        """v6.6: an employee who resigned → reason 'resignation' and the last day the law gives."""
        idx = self.emp_cb.current()
        if idx < 0:
            return
        try:
            e = dict(db.fetchone("SELECT * FROM employees WHERE employee_id=?", (self.emps[idx]["employee_id"],)) or {})
        except Exception:
            return
        rs = HT.resignation(e)
        if rs and rs.get("status") != "withdrawn":
            self.reason_var.set(dict(PE.EOS_REASONS)["resignation"])
            if rs.get("last_day"):
                self.end_var.set(rs["last_day"])

    def _calc(self):
        idx = self.emp_cb.current()
        if idx < 0:
            self.result_var.set("⚠️ Choose the employee."); self._show_result(None, "⚠ Choose the employee.")
            return None
        try:
            nd = float(self.notice_var.get() or 0)
        except ValueError:
            nd = 0.0
        try:
            s = PR.settlement(self.emps[idx]["employee_id"], self.end_var.get(), self._reason(),
                              self.leave_var.get().strip() or None, notice_days=nd,
                              notice_by=self.notice_by.get(), comp_77=self.comp_var.get())
        except Exception as e:
            self.result_var.set("❌ %s" % e); self._show_result(None, "❌ %s" % e); self._last = None
            return None
        if not self.leave_var.get().strip():
            self.leave_var.set("%g" % s["leave_days"])
            self._leave_auto = self.leave_var.get()
        self._last = s
        basis = "basic + all allowances (actual wage)" if s["wage_basis"] == "actual" else "basic + housing"
        lines = ["Joined %s · last day %s · %.2f years" % (str(s["employee"].get("join_date"))[:10],
                                                           s["end_date"], s["years"]),
                 "Wage %s SAR  (%s)" % (_m(s["wage"]), basis), "",
                 "End-of-service award (full)      %12s" % _m(s["award_full"]),
                 "Share for this reason            %11.0f %%" % (s["share"] * 100),
                 "Award                            %12s" % _m(s["award"]),
                 "Unused leave %6g days × %8s %12s" % (s["leave_days"], _m(s["day_wage"]), _m(s["leave_pay"])),
                 "Loans still owed  (%8s) −    %12s" % (_m(s["loan_owed"]), _m(s["loan_recovered"])),
                 "─" * 47,
                 "NET TO PAY                       %12s SAR" % _m(s["net"])]
        if s["loan_left"]:
            lines.append("(the employee still owes %s SAR of loans)" % _m(s["loan_left"]))
        if abs(s["leave_days"] - s.get("leave_auto", s["leave_days"])) > 0.01:
            lines.append("(DayBill counted %g leave days — you typed %g)" % (s["leave_auto"], s["leave_days"]))
        if s.get("notice_pay"):
            lines.append("Notice not given by the shop %g days: + %s" % (s["notice_days"], _m(s["notice_pay"])))
        if s.get("notice_taken"):
            lines.append("Notice not given by the employee %g days: − %s" % (s["notice_days"], _m(s["notice_taken"])))
        if s.get("comp_77"):
            lines.append("Compensation art. 77: + %s" % _m(s["comp_77"]))
        self.result_var.set("\n".join(lines))
        self._show_result(s)
        return s

    def _print(self):
        s = self._calc()
        if not s:
            return None
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                            initialfile="Final_settlement_%s.pdf" % (
                                                s["employee"].get("full_name_en") or "employee").replace(" ", "_"))
        if not path:
            return None
        return settlement_pdf(s, path)

    def _save(self):
        if not perm.allowed("hr", "edit", parent=self.win):
            return None
        s = self._calc()
        if not s:
            return None
        if not messagebox.askyesno("Final settlement", "Save the final settlement of %s?\n\nNet to pay %s SAR. "
                                   "The employee is set as left, loans are taken back and the journal is posted."
                                   % (s["employee"].get("full_name_en"), _m(s["net"])), parent=self.win):
            return None
        try:
            res = PR.save_settlement(s["employee"]["employee_id"], s["end_date"], s["reason"],
                                     leave_days=s["leave_days"], notice_days=s["notice_days"],
                                     notice_by=s["notice_by"], comp_77=bool(s["comp_77"]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e)[:300], parent=self.win)
            return None
        messagebox.showinfo(t("common.success"), "Final settlement saved: %s SAR.\nPay it from Accounts "
                            "(Salaries Payable)." % _m(res["net"]), parent=self.win)
        if self.on_save:
            self.on_save()
        self.win.destroy()
        return res

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{max(0, (sh-h)//2 - 20)}")


def settlement_pdf(s, path):
    """A one-page final settlement to print and sign."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from modules import pdf_invoice as PI
    PI._register_fonts()
    font = PI._AR_FONT or "Helvetica"
    bold = PI._AR_FONT_BOLD or "Helvetica-Bold"
    comp = db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
    W, H = A4
    c = canvas.Canvas(path, pagesize=A4)
    y = H - 60
    c.setFont(bold, 15); c.drawString(50, y, str(comp.get("company_name_en") or ""))
    if comp.get("company_name_ar"):
        c.drawRightString(W - 50, y, PI._shape_arabic(comp.get("company_name_ar")))
    y -= 34
    c.setFont(bold, 13); c.drawString(50, y, "FINAL SETTLEMENT — END OF SERVICE")
    c.drawRightString(W - 50, y, PI._shape_arabic("مخالصة نهائية — مكافأة نهاية الخدمة"))
    e = s["employee"]
    y -= 30
    c.setFont(font, 10)
    for a, b in (("Employee", "%s  %s" % (e.get("employee_code") or "", e.get("full_name_en") or "")),
                 ("Iqama / ID", e.get("national_id") or "—"),
                 ("Joined / last day", "%s  →  %s  (%.2f years)" % (str(e.get("join_date"))[:10], s["end_date"], s["years"])),
                 ("Reason", dict(PE.EOS_REASONS).get(s["reason"], s["reason"]).split(" — ")[0]),
                 ("Monthly wage", "%s SAR (%s)" % (_m(s["wage"]), "actual wage" if s["wage_basis"] == "actual"
                                                    else "basic + housing"))):
        c.drawString(50, y, a); c.drawString(190, y, str(b)); y -= 18
    y -= 10
    for a, b in (("End-of-service award (full)", _m(s["award_full"])),
                 ("Share (%.0f %%)" % (s["share"] * 100), _m(s["award"])),
                 ("Unused annual leave: %g days" % s["leave_days"], _m(s["leave_pay"])),
                 ("Notice not given by the employer: %g days" % s.get("notice_days", 0), _m(s.get("notice_pay", 0))),
                 ("Compensation (art. 77)", _m(s.get("comp_77", 0))),
                 ("Notice not given by the employee", "- " + _m(s.get("notice_taken", 0))),
                 ("Loans taken back", "- " + _m(s["loan_recovered"]))):
        if b in ("0.00", "- 0.00") and not a.startswith(("Unused", "Loans")):
            continue
        c.drawString(50, y, a); c.drawRightString(W - 50, y, b); y -= 18
    c.line(50, y + 6, W - 50, y + 6)
    y -= 8
    c.setFont(bold, 12); c.drawString(50, y, "NET TO PAY"); c.drawRightString(W - 50, y, _m(s["net"]) + " SAR")
    y -= 60
    c.setFont(font, 9)
    c.drawString(50, y, "I received the amount above and have no other claims on the employer.")
    c.drawRightString(W - 50, y - 16, PI._shape_arabic("استلمت المبلغ أعلاه وليس لي أي مطالبات أخرى لدى صاحب العمل"))
    y -= 70
    c.drawString(50, y, "Employee signature: ____________________")
    c.drawRightString(W - 50, y, "For the employer: ____________________")
    c.showPage(); c.save()
    return path
