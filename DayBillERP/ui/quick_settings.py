# ============================================================
# DayBill ERP - quick settings of a bill (v7.20, like Polosys)
# ------------------------------------------------------------
# The ⚙ Settings button on Sales / Purchase / Return windows opens this
# small panel under the button: the ticks a cashier changes most, saved
# for this PC as soon as ✔ Apply is pressed (Settings right needed).
# "All settings…" opens the full Settings page at the Sales section.
#
#   open_panel(form, anchor_widget)
# ============================================================

import tkinter as tk
from tkinter import ttk

# (key, label, default) — every key is a normal setting (Settings ▸ Sales)
ENTRY = [
    ("bill_qty_after_barcode", "Qty after barcode", True),
    ("cart_dup_check", "Duplication message (same item again)", True),
    ("bill_confirm_remove", "Ask confirmation for remove item", False),
    ("bill_block_zero", "Block zero figure entry (rate or qty 0)", False),
    ("allow_price_edit", "Allow price edit", True),
    ("allow_discount_edit", "Allow discount edit", True),
    ("barcode_mandatory_sales", "Barcode mandatory", False),
    ("show_stock_during_sales", "Show stock in product search", True),
    ("pos_show_cost_in_search", "Show cost in product search", False),
    ("auto_history_box", "Show last prices box", True),
    ("warn_sale_below_cost", "Warn when selling below cost", True),
]
NEW_BILL = [
    ("bill_focus_customer", "Initial focus to customer", False),
    ("bill_no_default_customer", "Not set default customer", False),
    ("bill_hold_salesman", "Hold salesman for the next bill", False),
    ("bill_default_cash", "Set default Cash Received", False),
    ("bill_date_edit", "Enable transaction date (change the date)", True),
    ("round_off_enabled", "Round off the bill total", False),
    ("inv_print_after_save", "Print after save", True),
    ("bill_print_confirm", "Show print confirmation", False),
    ("allow_negative_stock", "Allow negative stock", False),
]
DECIMALS = ["", "0", "1", "2", "3"]
ALL_KEYS = [k for k, _l, _d in ENTRY + NEW_BILL] + ["bill_qty_decimals"]


def _cfg():
    from config import settings as cfg
    return cfg


def value(key, default=False):
    cfg = _cfg()
    return cfg.flag(key, cfg.DEFAULT_SETTINGS.get(key, default))


class QuickSettings:
    def __init__(self, form, anchor=None):
        self.form = form
        cfg = _cfg()
        C = cfg.theme()
        parent = getattr(form, "win", None) or form
        self.win = w = tk.Toplevel(parent)
        w.title("Bill settings")
        w.configure(bg=C.get("border", "#CBD5E1"))
        w.resizable(False, False)
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass
        inner = tk.Frame(w, bg="white")
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Frame(inner, bg="white")
        head.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(head, text="Bill settings", font=("Segoe UI", 11, "bold"), bg="white",
                 fg="#0F172A").pack(side="left")
        tk.Label(head, text="saved on this PC · the next bill uses them", font=("Segoe UI", 9),
                 bg="white", fg="#64748B").pack(side="left", padx=8)
        body = tk.Frame(inner, bg="white")
        body.pack(fill="both", padx=10, pady=(4, 0))
        self.vars = {}
        for col, (title, rows) in enumerate((("While entering items", ENTRY),
                                             ("New bill and Save", NEW_BILL))):
            box = tk.Frame(body, bg="white")
            box.grid(row=0, column=col, sticky="nw", padx=(4, 18))
            tk.Label(box, text=title.upper(), font=("Segoe UI", 8, "bold"), bg="white",
                     fg="#64748B").pack(anchor="w", pady=(4, 2))
            for key, label, dflt in rows:
                v = tk.BooleanVar(master=w, value=value(key, dflt))
                self.vars[key] = v
                tk.Checkbutton(box, text=label, variable=v, font=("Segoe UI", 9), bg="white",
                               activebackground="#EDF2FF", anchor="w", cursor="hand2",
                               highlightthickness=0, padx=2, pady=3).pack(fill="x", anchor="w")
            if col == 0:
                row = tk.Frame(box, bg="white")
                row.pack(anchor="w", pady=(6, 0))
                tk.Label(row, text="Qty decimal point", font=("Segoe UI", 9), bg="white",
                         fg="#0F172A").pack(side="left", padx=(4, 6))
                self.dec_var = tk.StringVar(master=w, value=str(cfg.get("bill_qty_decimals", "") or ""))
                ttk.Combobox(row, textvariable=self.dec_var, values=DECIMALS, width=4,
                             state="readonly").pack(side="left")
                tk.Label(row, text="(empty = as typed)", font=("Segoe UI", 8), bg="white",
                         fg="#64748B").pack(side="left", padx=6)
        self.msg = tk.StringVar(master=w, value="")
        bar = tk.Frame(inner, bg="#F8FAFC")
        bar.pack(fill="x", pady=(10, 0))
        tk.Button(bar, text="All settings…", font=("Segoe UI", 9, "underline"), bg="#F8FAFC",
                  fg="#1F43C7", relief="flat", bd=0, cursor="hand2",
                  command=self.all_settings).pack(side="left", padx=12, pady=8)
        tk.Label(bar, textvariable=self.msg, font=("Segoe UI", 9), bg="#F8FAFC",
                 fg="#B91C1C").pack(side="left")
        tk.Button(bar, text="✔  Apply", font=("Segoe UI", 9, "bold"), bg="#2952E3", fg="white",
                  activebackground="#1F43C7", activeforeground="white", relief="flat", bd=0,
                  padx=14, pady=5, cursor="hand2", command=self.apply).pack(side="right", padx=(4, 10), pady=6)
        tk.Button(bar, text="Close", font=("Segoe UI", 9), bg="white", fg="#1F2937",
                  relief="flat", bd=0, padx=12, pady=5, cursor="hand2", highlightthickness=1,
                  highlightbackground="#CBD5E1", command=self.close).pack(side="right", padx=4, pady=6)
        w.bind("<Escape>", lambda e: self.close())
        self._place(anchor)
        w.focus_set()

    def _place(self, anchor):
        w = self.win
        try:
            w.update_idletasks()
            if anchor is not None:
                x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 2
            else:
                x, y = w.winfo_pointerx() - 40, w.winfo_pointery() + 10
            sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
            x = max(0, min(x, sw - w.winfo_reqwidth() - 8))
            y = max(0, min(y, sh - w.winfo_reqheight() - 48))
            w.geometry("+%d+%d" % (x, y))
        except Exception:
            pass

    def changes(self):
        out = {}
        dflt = {k: d for k, _l, d in ENTRY + NEW_BILL}
        for key, v in self.vars.items():
            if bool(v.get()) != value(key, dflt.get(key, False)):
                out[key] = bool(v.get())
        cfg = _cfg()
        d = self.dec_var.get()
        if d != str(cfg.get("bill_qty_decimals", "") or ""):
            out["bill_qty_decimals"] = d
        return out

    def apply(self):
        ch = self.changes()
        if not ch:
            return self.close()
        try:
            from modules import permissions as perm
            if not perm.allowed("company_settings", "settings", parent=self.win):
                self.msg.set("You don't have the Settings right.")
                return
        except Exception:
            pass
        cfg = _cfg()
        for k, v in ch.items():
            cfg.set(k, v)
        try:
            cfg.save_settings()
        except Exception:
            pass
        try:
            from modules import audit
            audit.log("settings", "update", "Bill settings: " + ", ".join(
                "%s=%s" % (k, v) for k, v in ch.items()))
        except Exception:
            pass
        apply_now = getattr(self.form, "_apply_quick_settings", None)
        if callable(apply_now):
            try:
                apply_now()
            except Exception:
                pass
        try:
            from ui.fluent_widgets import show_toast
            show_toast(getattr(self.form, "win", self.win), "✅  Bill settings saved", kind="success")
        except Exception:
            pass
        self.close()

    def all_settings(self):
        self.close()
        try:
            from ui import main_window as mw
            app = getattr(mw, "APP", None)
            if app is not None:
                app._open_settings_section("bill")
                app.root.lift()
        except Exception:
            pass

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass


def open_panel(form, anchor=None):
    old = getattr(form, "_quick_settings", None)
    try:
        if old is not None and old.win.winfo_exists():
            old.close()
            return None
    except Exception:
        pass
    form._quick_settings = QuickSettings(form, anchor)
    return form._quick_settings
