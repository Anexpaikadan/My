# ============================================================
# DayBill ERP - HR ▸ Leave and HR ▸ Attendance tabs (v6.0)
# ============================================================
import tkinter as tk
from tkinter import messagebox
from datetime import date

from modules import hr_time as HT
from ui import v6_kit as K


def _emp_labels():
    emps = HT.employees()
    return emps, ["%s — %s" % (e["employee_code"], e["full_name_en"]) for e in emps]


class LeaveTab:
    def __init__(self, parent, C):
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        if not HT.ready():
            tk.Label(self.frame, text="⚠ Leave needs the v6.0 database update — Updates ▸ Apply All Updates.",
                     bg=C["content_bg"], fg=C["danger"], font=("Segoe UI", 10, "bold")).pack(padx=20, pady=20)
            return
        c = K.card(self.frame, C, "New leave", fill="x", padx=16, pady=(10, 6))
        r = tk.Frame(c, bg=C["card_bg"]); r.pack(fill="x", padx=10, pady=(0, 8))
        self.emps, labels = _emp_labels()
        self.emp_v = tk.StringVar(value=labels[0] if labels else "")
        K.combo(r, C, "Employee *", self.emp_v, labels, 28).bind("<<ComboboxSelected>>",
                                                                lambda e: self._show_balance())
        self.type_v = tk.StringVar(value=HT.LEAVE_TYPES[0][1])
        K.combo(r, C, "Type", self.type_v, [x[1] for x in HT.LEAVE_TYPES], 16).bind(
            "<<ComboboxSelected>>", lambda e: self._show_balance())
        self.from_v, self.to_v = tk.StringVar(value=date.today().isoformat()), tk.StringVar(value=date.today().isoformat())
        K.date_entry(r, C, "First day *", self.from_v)
        K.date_entry(r, C, "Last day *", self.to_v)
        self.notes_v = tk.StringVar()
        K.entry(r, C, "Notes", self.notes_v, 24)
        K.button(r, C, "💾 Save leave", self._save, primary=True).pack_configure(pady=(14, 0))
        self.bal_v = tk.StringVar()
        tk.Label(c, textvariable=self.bal_v, font=("Segoe UI", 9, "bold"), bg=C["card_bg"], justify="left",
                 fg=C["primary"]).pack(anchor="w", padx=12, pady=(0, 8))
        self.msg_v = tk.StringVar()
        tk.Label(self.frame, textvariable=self.msg_v, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["danger"]).pack(anchor="w", padx=18)
        self.tree = K.tree(self.frame, [("emp", "Employee", 200, "w"), ("type", "Type", 90, "w"),
                                        ("from", "From", 90, "center"), ("to", "To", 90, "center"),
                                        ("days", "Days", 60, "e"), ("paid", "Paid", 60, "center"),
                                        ("notes", "Notes", 220, "w")], height=12)
        b = tk.Frame(self.frame, bg=C["content_bg"]); b.pack(fill="x", padx=16, pady=(0, 8))
        K.button(b, C, "🗑 Delete selected", self._delete)
        self.load()
        self._show_balance()

    def _emp(self):
        lbl = self.emp_v.get()
        return next((e for e in self.emps if "%s — %s" % (e["employee_code"], e["full_name_en"]) == lbl), None)

    def _show_balance(self):
        e = self._emp()
        if not e:
            return
        txt = HT.balance_text(e["employee_id"])
        lt = next((k for k, v in HT.LEAVE_TYPES if v == self.type_v.get()), "annual")
        if lt in HT.LAW_DAYS:
            txt += "\n%s." % HT.LAW_DAYS[lt][1]
        elif lt == "sick":
            txt += "\nSick leave (art. 117): in one year 30 days full pay, 60 days ¾ pay, 30 days unpaid — " \
                   "payroll takes the unpaid part off by itself."
        self.bal_v.set(txt)

    def _save(self):
        e = self._emp()
        lt = next((k for k, v in HT.LEAVE_TYPES if v == self.type_v.get()), "other")
        try:
            HT.add_leave(e and e["employee_id"], lt, self.from_v.get(), self.to_v.get(),
                         notes=self.notes_v.get())
        except ValueError as ex:
            self.msg_v.set(str(ex))
            return
        except Exception as ex:
            self.msg_v.set("Not saved: %s" % str(ex)[:150])
            return
        self.msg_v.set("")
        self.notes_v.set("")
        self.load()
        self._show_balance()

    def load(self):
        self.tree.delete(*self.tree.get_children())
        for l in HT.leaves():
            self.tree.insert("", "end", iid=str(l["leave_id"]), values=(
                l.get("full_name_en"), dict(HT.LEAVE_TYPES).get(l.get("leave_type"), l.get("leave_type")),
                str(l.get("start_date"))[:10], str(l.get("end_date"))[:10], "%g" % float(l.get("days") or 0),
                "Yes" if l.get("paid") in (1, True) else "No", l.get("notes") or ""))

    def _delete(self):
        sel = self.tree.selection()
        if sel and messagebox.askyesno("Delete leave", "Delete the selected leave?", parent=self.frame):
            HT.delete_leave(int(sel[0]))
            self.load()
            self._show_balance()


class AttendanceTab:
    def __init__(self, parent, C):
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        if not HT.ready():
            tk.Label(self.frame, text="⚠ Attendance needs the v6.0 database update — Updates ▸ Apply All Updates.",
                     bg=C["content_bg"], fg=C["danger"], font=("Segoe UI", 10, "bold")).pack(padx=20, pady=20)
            return
        top = K.card(self.frame, C, None, fill="x", padx=16, pady=(10, 6))
        r = tk.Frame(top, bg=C["card_bg"]); r.pack(fill="x", padx=10, pady=8)
        self.day_v = tk.StringVar(value=date.today().isoformat())
        e = K.date_entry(r, C, "Day", self.day_v)
        e.bind("<Return>", lambda ev: self.load())
        K.button(r, C, "Show", self.load).pack_configure(pady=(14, 0))
        K.button(r, C, "✔ Everyone present", self._all_present).pack_configure(pady=(14, 0))
        self.st_v = tk.StringVar(value="Present")
        K.combo(r, C, "Mark selected as", self.st_v, [x[1] for x in HT.STATUSES], 12)
        self.in_v, self.out_v = tk.StringVar(), tk.StringVar()
        K.entry(r, C, "In (08:00)", self.in_v, 6)
        K.entry(r, C, "Out (17:00)", self.out_v, 6)
        K.button(r, C, "💾 Mark", self._mark, primary=True).pack_configure(pady=(14, 0))
        self.msg_v = tk.StringVar()
        tk.Label(self.frame, textvariable=self.msg_v, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=18)
        self.tree = K.tree(self.frame, [("code", "Code", 80, "w"), ("name", "Employee", 220, "w"),
                                        ("st", "Status", 90, "center"), ("in", "In", 70, "center"),
                                        ("out", "Out", 70, "center"), ("h", "Hours", 70, "e"),
                                        ("notes", "Notes", 220, "w")], height=14)
        self.tree.configure(selectmode="extended")
        self.load()

    def load(self):
        self.tree.delete(*self.tree.get_children())
        try:
            rows = HT.day_sheet(self.day_v.get())
        except Exception:
            self.msg_v.set("Type the day as YYYY-MM-DD.")
            return
        names = dict(HT.STATUSES)
        for r in rows:
            self.tree.insert("", "end", iid=str(r["employee_id"]), values=(
                r["code"], r["name"], names.get(r["status"], "—"), r["check_in"], r["check_out"],
                "" if r["hours"] is None else "%g" % float(r["hours"]), r["notes"]))
        done = sum(1 for r in rows if r["status"])
        self.msg_v.set("%d of %d employee(s) marked for %s" % (done, len(rows), self.day_v.get()))

    def _mark(self):
        sel = self.tree.selection()
        if not sel:
            self.msg_v.set("Select the employee(s) first (Ctrl / Shift + click for several).")
            return
        st = next((k for k, v in HT.STATUSES if v == self.st_v.get()), "present")
        try:
            for eid in sel:
                HT.mark(int(eid), self.day_v.get(), st, self.in_v.get().strip() or None,
                        self.out_v.get().strip() or None)
        except ValueError as ex:
            self.msg_v.set(str(ex))
            return
        self.load()

    def _all_present(self):
        for eid in self.tree.get_children():
            if not self.tree.set(eid, "st") or self.tree.set(eid, "st") == "—":
                HT.mark(int(eid), self.day_v.get(), "present")
        self.load()
