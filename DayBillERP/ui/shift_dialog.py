# ============================================================
# DayBill ERP - Open / close a cashier shift (v6.0)
# ------------------------------------------------------------
#   open : type the cash already in the drawer (opening float)
#   close: count the drawer and type the amount — with "blind count"
#          (Settings ▸ POS) the expected amount is shown only AFTER the
#          count is typed, so the count stays honest.
# ============================================================
import tkinter as tk
from tkinter import messagebox

from modules import shifts


def _money(v):
    return "{:,.2f}".format(float(v or 0))


class _Base(tk.Toplevel):
    NAVY = "#0B1F3A"

    def __init__(self, parent, title, sub):
        super().__init__(parent)
        self.title(title)
        self.configure(bg="white")
        self.transient(parent)
        self.resizable(False, False)
        self._keep_size = True
        hdr = tk.Frame(self, bg=self.NAVY); hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=("Segoe UI", 14, "bold"), bg=self.NAVY,
                 fg="white").pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(hdr, text=sub, font=("Segoe UI", 9), bg=self.NAVY, fg="#A9BCD6",
                 wraplength=420, justify="left").pack(anchor="w", padx=16, pady=(0, 10))
        self.body = tk.Frame(self, bg="white"); self.body.pack(fill="both", expand=True,
                                                               padx=16, pady=12)
        self.result = None

    def _amount_row(self, label, value=""):
        tk.Label(self.body, text=label, font=("Segoe UI", 10, "bold"), bg="white",
                 fg="#0F172A").pack(anchor="w")
        v = tk.StringVar(value=value)
        e = tk.Entry(self.body, textvariable=v, font=("Segoe UI", 20, "bold"), width=12,
                     justify="right", relief="solid", bd=1)
        e.pack(anchor="w", pady=(2, 8), ipady=3)
        e.focus_set()
        e.select_range(0, "end")
        return v, e

    def _buttons(self, ok_text, ok_cmd):
        f = tk.Frame(self, bg="#F8FAFC", highlightbackground="#D5DCE6", highlightthickness=1)
        f.pack(fill="x", side="bottom")
        tk.Button(f, text="Cancel", font=("Segoe UI", 10), bg="white", relief="flat",
                  cursor="hand2", command=self.destroy, padx=14,
                  highlightthickness=1, highlightbackground="#C7D0DD").pack(
                      side="left", padx=12, pady=10, ipady=4)
        self.ok_btn = tk.Button(f, text=ok_text, font=("Segoe UI", 12, "bold"), bg="#15803D",
                                fg="white", relief="flat", cursor="hand2", command=ok_cmd,
                                padx=18)
        self.ok_btn.pack(side="right", padx=12, pady=10, ipady=4)
        self.bind("<Return>", lambda e: ok_cmd())
        self.bind("<Escape>", lambda e: self.destroy())

    def _center(self, parent):
        self.update_idletasks()
        w, h = max(self.winfo_reqwidth(), 460), self.winfo_reqheight()
        try:
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - w) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - h) // 3)
            self.geometry("%dx%d+%d+%d" % (w, h, x, y))
        except Exception:
            self.geometry("%dx%d" % (w, h))

    @staticmethod
    def _num(v):
        try:
            return round(float(str(v.get()).replace(",", "").strip() or 0), 2)
        except ValueError:
            return None


class OpenShiftDialog(_Base):
    def __init__(self, parent, on_done=None):
        super().__init__(parent, "Open shift  ·  فتح وردية",
                         "Count the cash already in the drawer before the first sale. "
                         "At the end of the shift DayBill checks the drawer against it.")
        self.on_done = on_done
        self.float_v, self.entry = self._amount_row("Cash in the drawer now (SAR)", "0")
        self.msg = tk.Label(self.body, text="", font=("Segoe UI", 9), bg="white", fg="#B91C1C")
        self.msg.pack(anchor="w")
        self._buttons("Open shift", self._ok)
        self._center(parent)
        try:
            self.grab_set()
        except Exception:
            pass

    def _ok(self):
        v = self._num(self.float_v)
        if v is None or v < 0:
            self.msg.configure(text="Type the amount as a number (0 or more).")
            return
        sid, msg = shifts.open_shift(v)
        if not sid:
            self.msg.configure(text=msg)
            return
        self.result = sid
        cb = self.on_done
        self.destroy()
        if cb:
            cb(sid, msg)


class CloseShiftDialog(_Base):
    def __init__(self, parent, on_done=None):
        s = shifts.current()
        self.shift = s
        super().__init__(parent, "Close shift  ·  إغلاق الوردية",
                         "Count the cash in the drawer and type it below."
                         + ("" if shifts.blind() else "  The expected amount is shown."))
        self.on_done = on_done
        sm = shifts.summary(s) if s else {}
        self.sm = sm
        info = tk.Frame(self.body, bg="#F1F5F9"); info.pack(fill="x", pady=(0, 10))
        rows = [("Opened", str(sm.get("opened_at") or "")[:16]),
                ("Cashier", sm.get("username") or ""),
                ("Bills", str(sm.get("bills", 0))),
                ("Sales", _money(sm.get("sales")))]
        for k, a in sorted((sm.get("tenders") or {}).items()):
            try:
                from modules import tenders as _td
                rows.append(("  " + _td.label(k), _money(a)))
            except Exception:
                rows.append(("  " + k, _money(a)))
        rows.append(("Opening cash", _money(sm.get("opening_float"))))
        if sm.get("cash_refunds"):
            rows.append(("Cash refunds", "−" + _money(sm.get("cash_refunds"))))
        if not shifts.blind():
            rows.append(("Expected in drawer", _money(sm.get("expected_cash"))))
        for i, (k, v) in enumerate(rows):
            tk.Label(info, text=k, font=("Segoe UI", 9), bg="#F1F5F9", fg="#475569").grid(
                row=i, column=0, sticky="w", padx=10, pady=1)
            tk.Label(info, text=v, font=("Segoe UI", 9, "bold"), bg="#F1F5F9", fg="#0F172A").grid(
                row=i, column=1, sticky="e", padx=10, pady=1)
        info.grid_columnconfigure(1, weight=1)
        self.count_v, self.entry = self._amount_row("Cash counted in the drawer (SAR)", "")
        self.msg = tk.Label(self.body, text="", font=("Segoe UI", 10, "bold"), bg="white",
                            fg="#B91C1C", wraplength=420, justify="left")
        self.msg.pack(anchor="w")
        self._buttons("Close shift", self._ok)
        self._center(parent)
        try:
            self.grab_set()
        except Exception:
            pass

    def _ok(self):
        if not self.shift:
            self.destroy()
            return
        v = self._num(self.count_v)
        if v is None or v < 0 or not str(self.count_v.get()).strip():
            self.msg.configure(text="Count the drawer and type the amount.")
            return
        sm, msg = shifts.close_shift(v)
        self.result = sm
        cb = self.on_done
        self.destroy()
        if cb:
            cb(sm, msg)


def shift_button(parent_win, status_var=None):
    """POS ▸ Shift [F9]: open a shift, or close the one that is open."""
    if not shifts.ready():
        try:
            from config.database import db
            db.execute_scalar("SELECT 1")
            server_ok = True
        except Exception:
            server_ok = False
        messagebox.showinfo("Shift", "Cashier shifts need the v6.0 database update "
                            "(Updates ▸ Apply All Updates)." if server_ok else
                            "The server can't be reached right now — open or close the shift "
                            "when the connection is back.", parent=parent_win)
        return None

    def opened(sid, msg):
        if status_var is not None:
            status_var.set(msg)

    def closed(sm, msg):
        if status_var is not None:
            status_var.set(msg)
        if sm:
            d = sm.get("difference", 0.0)
            messagebox.showinfo(
                "Shift closed",
                "%s\n\nExpected in drawer:  %s\nCounted:  %s\nDifference:  %s"
                % (msg, _money(sm.get("expected_cash")), _money(sm.get("counted_cash")),
                   ("+" if d > 0 else "") + _money(d)), parent=parent_win)

    if shifts.current():
        try:                       # v6.0: bills kept on this PC while the server was gone
            from modules import offline_pos as OFF
            if OFF.count():
                OFF.send_all()
            left = OFF.count()
        except Exception:
            left = 0
        if left and not messagebox.askyesno(
                "Shift", "%d bill(s) of this shift are still kept on this PC (the server could not be "
                "reached).\n\nClose the shift anyway? Their money is in the drawer but not yet in the "
                "expected cash, so the count will show a difference." % left, parent=parent_win):
            return None
        return CloseShiftDialog(parent_win, on_done=closed)
    return OpenShiftDialog(parent_win, on_done=opened)
