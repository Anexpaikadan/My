# ============================================================
# DayBill ERP - On-screen Number Pad (shared widget)
# ------------------------------------------------------------
# Reusable touch keypad used by the invoice grid (Qty entry) and
# the Teller cash-tender popup. Keyboard entry keeps working; this
# is an additional on-screen option.
#
#   NumberPad        - a frame of digit buttons that feeds a StringVar
#   NumberPadPopup   - a small Toplevel: display + NumberPad + OK/Cancel
#   CashTenderDialog - Teller: total due, cash received, live change
# ============================================================

import tkinter as tk

_DEF = {
    "card_bg": "#FFFFFF", "primary": "#2563EB", "primary_dark": "#1D4ED8",
    "accent": "#16A34A", "danger": "#DC2626", "text_primary": "#111827",
    "text_secondary": "#6B7280", "border": "#E2E6EE",
}


def _theme(t):
    if not t:
        return dict(_DEF)
    return {k: t.get(k, v) for k, v in _DEF.items()}


def _append(s, ch):
    """Calculator-style append into a numeric string."""
    s = s or ""
    if ch == "C":
        return ""
    if ch == "<":                       # backspace
        return s[:-1]
    if ch == ".":
        if "." in s:
            return s
        return (s or "0") + "."
    # digit
    if s in ("", "0"):
        return ch
    return s + ch


class NumberPad(tk.Frame):
    """Digit grid that edits `variable`. Optional Unit / Enter actions."""
    def __init__(self, parent, variable, on_enter=None, on_unit=None,
                 theme=None, big=True, **kw):
        C = _theme(theme)
        super().__init__(parent, bg=C["card_bg"], **kw)
        self.var = variable
        self.on_enter = on_enter
        self.on_unit = on_unit
        self.C = C
        self._big = big
        self._build()

    def _build(self):
        C = self.C
        fnt = ("Segoe UI", 16 if self._big else 13, "bold")
        pad = 3

        def mk(parent, text, cmd, bg=None, fg=None, w=4):
            b = tk.Button(parent, text=text, font=fnt, width=w,
                          bg=bg or "#F2F1FB", fg=fg or C["text_primary"],
                          relief="flat", bd=0, cursor="hand2",
                          activebackground=C["primary"], activeforeground="white",
                          command=cmd)
            return b

        rows = [["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"]]
        for r, line in enumerate(rows):
            fr = tk.Frame(self, bg=C["card_bg"]); fr.pack()
            for ch in line:
                mk(fr, ch, lambda c=ch: self._key(c)).pack(side="left", padx=pad, pady=pad, ipady=6)

        # bottom rows: 0 . <
        fr = tk.Frame(self, bg=C["card_bg"]); fr.pack()
        mk(fr, "0", lambda: self._key("0")).pack(side="left", padx=pad, pady=pad, ipady=6)
        mk(fr, ".", lambda: self._key(".")).pack(side="left", padx=pad, pady=pad, ipady=6)
        mk(fr, "\u232b", lambda: self._key("<"),
           bg="#FCE8E8", fg=C["danger"]).pack(side="left", padx=pad, pady=pad, ipady=6)

        # action row: Clear / Unit / Enter
        fr = tk.Frame(self, bg=C["card_bg"]); fr.pack(pady=(2, 0))
        mk(fr, "C", lambda: self._key("C"), bg="#FCE8E8", fg=C["danger"], w=4).pack(
            side="left", padx=pad, pady=pad, ipady=6)
        if self.on_unit:
            mk(fr, "\u27f3 Unit", self.on_unit, bg=C["primary_dark"], fg="white", w=6).pack(
                side="left", padx=pad, pady=pad, ipady=6)
        if self.on_enter:
            mk(fr, "Enter", self.on_enter, bg=C["accent"], fg="white", w=6).pack(
                side="left", padx=pad, pady=pad, ipady=6)

    def _key(self, ch):
        self.var.set(_append(self.var.get(), ch))


class NumberPadPopup(tk.Toplevel):
    """Small popup with a display and a NumberPad. Calls on_ok(value)."""
    def __init__(self, parent, initial="", title="Enter Quantity",
                 on_ok=None, on_unit=None, theme=None, anchor_widget=None,
                 variable=None):
        super().__init__(parent)
        C = _theme(theme)
        self.on_ok = on_ok
        self.configure(bg=C["card_bg"])
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.var = variable if variable is not None else tk.StringVar(value=str(initial))

        tk.Label(self, text=title, font=("Segoe UI", 9, "bold"),
                 bg=C["primary_dark"], fg="white").pack(fill="x")
        tk.Label(self, textvariable=self.var, font=("Segoe UI", 20, "bold"),
                 bg="white", fg=C["text_primary"], anchor="e",
                 relief="solid", bd=1).pack(fill="x", padx=8, pady=6, ipady=4)
        NumberPad(self, self.var, on_enter=self._ok, on_unit=on_unit,
                  theme=C).pack(padx=8, pady=(0, 6))
        row = tk.Frame(self, bg=C["card_bg"]); row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(row, text="Cancel", font=("Segoe UI", 10), bg="#EEF1F6",
                  relief="flat", cursor="hand2", command=self.destroy).pack(
                      side="left", expand=True, fill="x", padx=2)
        tk.Button(row, text="OK", font=("Segoe UI", 10, "bold"), bg=C["accent"],
                  fg="white", relief="flat", cursor="hand2",
                  command=self._ok).pack(side="left", expand=True, fill="x", padx=2)

        self._place(anchor_widget)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _place(self, w):
        self.update_idletasks()
        if w is not None and w.winfo_exists():
            x = w.winfo_rootx()
            y = w.winfo_rooty() + w.winfo_height() + 2
        else:
            x = self.winfo_screenwidth() // 2 - 110
            y = self.winfo_screenheight() // 2 - 160
        self.geometry(f"+{x}+{y}")

    def _ok(self):
        if self.on_ok:
            try:
                self.on_ok(self.var.get())
            except Exception:
                pass
        self.destroy()


class CashTenderDialog(tk.Toplevel):
    """Teller: shows total due, cash received via keypad, live change.
    Calls on_confirm(received_float) when confirmed."""
    def __init__(self, parent, total_due, on_confirm=None, theme=None,
                 currency="SAR"):
        super().__init__(parent)
        C = _theme(theme)
        self.on_confirm = on_confirm
        self.total = round(float(total_due or 0), 2)
        self.currency = currency
        self.title("Teller - Cash Tender")
        self.configure(bg=C["card_bg"])
        self.transient(parent)
        self.grab_set()
        self.received = tk.StringVar(value=f"{self.total:.2f}")
        self.change_var = tk.StringVar(value="0.00")
        self.C = C

        head = tk.Frame(self, bg=C["primary_dark"]); head.pack(fill="x")
        tk.Label(head, text="Cash Tender", font=("Segoe UI", 13, "bold"),
                 bg=C["primary_dark"], fg="white").pack(side="left", padx=14, pady=8)

        body = tk.Frame(self, bg=C["card_bg"]); body.pack(padx=16, pady=12)

        def field(label, var, color, big=False):
            f = tk.Frame(body, bg=C["card_bg"]); f.pack(fill="x", pady=4)
            tk.Label(f, text=label, font=("Segoe UI", 10), bg=C["card_bg"],
                     fg=C["text_secondary"], width=14, anchor="w").pack(side="left")
            tk.Label(f, textvariable=var,
                     font=("Segoe UI", 18 if big else 13, "bold"),
                     bg=C["card_bg"], fg=color, anchor="e").pack(side="right")

        self.total_var = tk.StringVar(value=f"{self.total:,.2f} {currency}")
        field("Total Due", self.total_var, C["text_primary"], big=True)

        rf = tk.Frame(body, bg=C["card_bg"]); rf.pack(fill="x", pady=4)
        tk.Label(rf, text="Cash Received", font=("Segoe UI", 10), bg=C["card_bg"],
                 fg=C["text_secondary"], width=14, anchor="w").pack(side="left")
        tk.Label(rf, textvariable=self.received, font=("Segoe UI", 18, "bold"),
                 bg="white", fg=C["primary"], anchor="e", relief="solid",
                 bd=1, width=12).pack(side="right", ipady=2)

        field("Change", self.change_var, C["accent"], big=True)

        # quick amounts
        qa = tk.Frame(body, bg=C["card_bg"]); qa.pack(fill="x", pady=(6, 2))
        for amt in self._quick_amounts():
            tk.Button(qa, text=f"{amt:g}", font=("Segoe UI", 10, "bold"),
                      bg="#EAF1FE", relief="flat", cursor="hand2",
                      command=lambda a=amt: self._set(a)).pack(
                          side="left", expand=True, fill="x", padx=2, ipady=4)

        self.received.trace("w", lambda *a: self._recompute())
        NumberPad(self, self.received, on_enter=self._confirm,
                  theme=C).pack(padx=16, pady=(0, 8))

        btns = tk.Frame(self, bg=C["card_bg"]); btns.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(btns, text="Cancel", font=("Segoe UI", 11), bg="#EEF1F6",
                  relief="flat", cursor="hand2", command=self.destroy).pack(
                      side="left", expand=True, fill="x", padx=3, ipady=4)
        tk.Button(btns, text="Confirm", font=("Segoe UI", 11, "bold"),
                  bg=C["accent"], fg="white", relief="flat", cursor="hand2",
                  command=self._confirm).pack(side="left", expand=True, fill="x",
                                              padx=3, ipady=4)
        self._recompute()
        self.bind("<Escape>", lambda e: self.destroy())

    def _quick_amounts(self):
        """Suggest exact + a few common round notes above the total."""
        t = self.total
        notes = [n for n in (50, 100, 200, 500) if n >= t]
        out = [round(t, 2)] + notes[:3]
        seen, uniq = set(), []
        for v in out:
            if v not in seen:
                seen.add(v); uniq.append(v)
        return uniq[:4]

    def _set(self, amt):
        self.received.set(f"{amt:.2f}")

    def _num(self, v):
        try:
            return float(str(v).replace(",", "") or 0)
        except Exception:
            return 0.0

    def _recompute(self):
        rec = self._num(self.received.get())
        change = round(rec - self.total, 2)
        if change >= 0:
            self.change_var.set(f"{change:,.2f} {self.currency}")
        else:
            self.change_var.set(f"Short {abs(change):,.2f}")

    def _confirm(self):
        rec = self._num(self.received.get())
        if self.on_confirm:
            try:
                self.on_confirm(rec)
            except Exception:
                pass
        self.destroy()
