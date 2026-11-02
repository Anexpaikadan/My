# ============================================================
# DayBill ERP - Setup Wizard + Setup Checklist
# ------------------------------------------------------------
# SetupChecklist : a screen (menu: Help → Setup Checklist) that
#                  shows each setup task with a done/pending status
#                  and an "Open" button that jumps to the screen.
# SetupWizard    : a first-run step-by-step dialog (Company → Default
#                  Accounts → Printer → Finish). Each step explains
#                  what to do and opens the matching screen.
# maybe_run()    : called at startup; launches the wizard once until
#                  the user marks setup complete.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


# ── status checks (all defensive — tables may be missing) ─────
def _scalar(sql, params=()):
    try:
        return db.execute_scalar(sql, params)
    except Exception:
        return None


def check_company():
    """True when the shop's own name is filled in (not the empty-install
    placeholder 'Your Company Name')."""
    r = _scalar("SELECT TOP 1 company_name_en FROM company ORDER BY company_id")
    name = str(r or "").strip().lower()
    return bool(name) and name not in ("your company name", "company name", "my company")


def check_vat():
    """True when the VAT number is good enough for the ZATCA QR code
    (15 digits, starts and ends with 3)."""
    r = _scalar("SELECT TOP 1 vat_registration_no FROM company WHERE company_id=1")
    try:
        from modules.zatca.qr_generator import valid_vat_number
        return valid_vat_number(r)
    except Exception:
        return bool(r and len(str(r)) >= 10)


def check_accounting():
    return bool(_scalar("SELECT COUNT(*) FROM sys.tables WHERE name='journal_entries'"))


def check_accounts_map():
    return bool(_scalar("SELECT COUNT(*) FROM sys.tables WHERE name='account_settings'"))


def check_products():
    return bool(_scalar("SELECT COUNT(*) FROM products") or 0)


def check_customers():
    return bool(_scalar("SELECT COUNT(*) FROM customers") or 0)


def check_printer():
    return bool(cfg.get("paper_width"))


# task list: (key, title, hint, check_fn, screen_to_open)
TASKS = [
    ("company",   "Company profile", "Name, address, logo, contact",
     check_company, "settings"),
    ("vat",       "VAT / ZATCA number", "15-digit VAT registration for tax invoices",
     check_vat, "settings"),
    ("accounting","Accounting tables", "Run the accounting SQL patches in SSMS",
     check_accounting, None),
    ("accounts",  "Default accounts", "Cash / bank / sales / VAT account mapping",
     check_accounts_map, "settings"),
    ("printer",   "Printer & invoice", "Paper size, template, footer",
     check_printer, "print_settings"),
    ("products",  "Add products", "At least one product to sell",
     check_products, "products"),
    ("customers", "Customers", "Cash customer + any regulars",
     check_customers, "customers"),
]


def setup_complete():
    return bool(cfg.get("setup_complete"))


def all_done():
    return all(t[3]() for t in TASKS)


# ============================================================
# Checklist screen
# ============================================================
class SetupChecklist:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build(C)

    def _build(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(bar, text="🧭  Setup Checklist", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="🔄 Refresh", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=12,
                  pady=6, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._refresh).pack(side="right")
        tk.Button(bar, text="▶ Run Wizard", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2",
                  command=lambda: SetupWizard(self.frame)).pack(side="right", padx=(0, 8))

        self.prog_var = tk.StringVar()
        tk.Label(self.frame, textvariable=self.prog_var, font=("Segoe UI", 10),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=24)

        self.holder = tk.Frame(self.frame, bg=C["content_bg"])
        self.holder.pack(fill="both", expand=True, padx=24, pady=12)
        self._refresh()

    def _refresh(self):
        C = self.C
        for w in self.holder.winfo_children():
            w.destroy()
        done = 0
        for key, title, hint, fn, screen in TASKS:
            ok = False
            try:
                ok = bool(fn())
            except Exception:
                ok = False
            if ok:
                done += 1
            card = tk.Frame(self.holder, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(fill="x", pady=4)
            inner = tk.Frame(card, bg=C["card_bg"]); inner.pack(fill="x", padx=14, pady=10)
            tk.Label(inner, text="✓" if ok else "○",
                     font=("Segoe UI", 16, "bold"), bg=C["card_bg"],
                     fg=C["accent"] if ok else C["text_secondary"],
                     width=2).pack(side="left")
            txt = tk.Frame(inner, bg=C["card_bg"]); txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=title, font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                     fg=C["text_primary"], anchor="w").pack(anchor="w")
            tk.Label(txt, text=hint, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"], anchor="w").pack(anchor="w")
            if screen:
                tk.Button(inner, text="Open →", font=("Segoe UI", 9, "bold"),
                          bg=C["content_bg"], fg=C["primary"], relief="flat",
                          padx=12, pady=5, cursor="hand2",
                          command=lambda s=screen: self._open(s)).pack(side="right")
            elif not ok:
                tk.Label(inner, text="Run SQL patch", font=("Segoe UI", 8, "bold"),
                         bg=C["card_bg"], fg=C["danger"]).pack(side="right")
        self.prog_var.set(f"{done} of {len(TASKS)} complete"
                          + ("  —  all set! 🎉" if done == len(TASKS) else ""))

    def _open(self, screen):
        try:
            from ui import main_window as mw
            mw.navigate(screen)
        except Exception:
            pass


# ============================================================
# First-run wizard
# ============================================================
class SetupWizard:
    STEPS = [
        ("Welcome", "Welcome to DayBill ERP",
         "Let's get your shop ready in a few steps. You can skip any step "
         "and finish it later from Help → Setup Checklist.", None),
        ("Company", "1. Company profile",
         "Set your store name, address, logo and contact details — these "
         "appear on every invoice.", "settings"),
        ("VAT", "2. VAT / ZATCA",
         "Enter your 15-digit VAT registration number so tax invoices and "
         "the ZATCA QR code are valid.", "settings"),
        ("Accounts", "3. Default accounts",
         "Map the Cash, Bank, Sales and VAT accounts that postings use. "
         "(Run the accounting SQL patches first if you haven't.)", "settings"),
        ("Printer", "4. Printer & invoice",
         "Choose paper size (58/80mm or A4), the invoice template and footer.",
         "print_settings"),
        ("Products", "5. Add products",
         "Add at least one product (with its units) so you can start billing.",
         "products"),
        ("Finish", "All set! 🎉",
         "You're ready to make your first sale. Re-open this anytime from "
         "Help → Setup Checklist.", None),
    ]

    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.i = 0
        self.win = tk.Toplevel(parent)
        self.win.title("DayBill Setup")
        _mark_shown()                     # shown once — ✕ / Skip / Finish all count
        self.win.protocol("WM_DELETE_WINDOW", self._finish)
        self.win._no_close_confirm = True
        self.win.configure(bg=C["card_bg"])
        self.win.geometry("520x360")
        try:
            self.win.transient(parent.winfo_toplevel())
            self.win.grab_set()
        except Exception:
            pass
        self._build(C)
        self._render()

    def _build(self, C):
        head = tk.Frame(self.win, bg=C["primary"]); head.pack(fill="x")
        self.title_var = tk.StringVar()
        tk.Label(head, textvariable=self.title_var, font=("Segoe UI", 14, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16, pady=12)
        self.step_var = tk.StringVar()
        tk.Label(head, textvariable=self.step_var, font=("Segoe UI", 9),
                 bg=C["primary"], fg="#D9D4FF").pack(side="right", padx=16)

        self.body = tk.Frame(self.win, bg=C["card_bg"])
        self.body.pack(fill="both", expand=True, padx=20, pady=16)
        self.desc_var = tk.StringVar()
        tk.Label(self.body, textvariable=self.desc_var, font=("Segoe UI", 11),
                 bg=C["card_bg"], fg=C["text_primary"], wraplength=460,
                 justify="left").pack(anchor="w")
        self.open_btn = tk.Button(self.body, text="", font=("Segoe UI", 10, "bold"),
                                  bg=C["info"], fg="white", relief="flat", padx=16,
                                  pady=8, cursor="hand2", command=self._open_screen)
        self.status_lbl = tk.Label(self.body, text="", font=("Segoe UI", 9, "bold"),
                                   bg=C["card_bg"])

        nav = tk.Frame(self.win, bg=C["card_bg"]); nav.pack(fill="x", padx=20, pady=14)
        self.skip_btn = tk.Button(nav, text="Skip setup", font=("Segoe UI", 9),
                                  bg=C["card_bg"], fg=C["text_secondary"], relief="flat",
                                  cursor="hand2", command=self._finish)
        self.skip_btn.pack(side="left")
        self.next_btn = tk.Button(nav, text="Next →", font=("Segoe UI", 10, "bold"),
                                  bg=C["accent"], fg="white", relief="flat", padx=18,
                                  pady=7, cursor="hand2", command=self._next)
        self.next_btn.pack(side="right")
        self.back_btn = tk.Button(nav, text="← Back", font=("Segoe UI", 10),
                                  bg="#EEF1F6", relief="flat", padx=16, pady=7,
                                  cursor="hand2", command=self._back)
        self.back_btn.pack(side="right", padx=(0, 8))

    def _render(self):
        key, title, desc, screen = self.STEPS[self.i]
        self.title_var.set(title)
        self.step_var.set(f"Step {self.i + 1} / {len(self.STEPS)}")
        self.desc_var.set(desc)
        self._screen = screen
        if screen:
            self.open_btn.config(text=f"Open this screen  →")
            self.open_btn.pack(anchor="w", pady=(14, 6))
        else:
            self.open_btn.pack_forget()
        # live status for the step that has a check
        check = {"Company": check_company, "VAT": check_vat,
                 "Printer": check_printer, "Products": check_products,
                 "Accounts": check_accounts_map}.get(key)
        if check:
            ok = False
            try:
                ok = bool(check())
            except Exception:
                ok = False
            self.status_lbl.config(
                text=("✓ Looks done" if ok else "○ Not done yet"),
                fg=self.C["accent"] if ok else self.C["text_secondary"])
            self.status_lbl.pack(anchor="w")
        else:
            self.status_lbl.pack_forget()
        self.back_btn.config(state="normal" if self.i > 0 else "disabled")
        self.next_btn.config(text="Finish ✓" if self.i == len(self.STEPS) - 1 else "Next →")

    def _open_screen(self):
        if self._screen:
            try:
                from ui import main_window as mw
                mw.navigate(self._screen)
            except Exception:
                pass

    def _next(self):
        if self.i < len(self.STEPS) - 1:
            self.i += 1
            self._render()
        else:
            self._finish()

    def _back(self):
        if self.i > 0:
            self.i -= 1
            self._render()

    def _finish(self):
        try:
            cfg.set("setup_complete", True)
            cfg.save_settings()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


def maybe_run(root):
    """The 'Welcome to DayBill ERP' wizard opens ONCE — on a brand-new
    installation whose company profile is still empty. It never opens
    again after it was shown (Finish, Skip or ✕ all count), and never on
    a shop that is already set up. Help ▸ Setup Checklist ▸ Run Wizard
    opens it any time."""
    try:
        if setup_complete() or cfg.get("setup_wizard_shown"):
            return
        if check_company():            # shop already set up → mark and stay quiet
            _mark_shown()
            return
        root.after(600, lambda: SetupWizard(root))
    except Exception:
        pass


def _mark_shown():
    try:
        cfg.set("setup_wizard_shown", True)
        cfg.set("setup_complete", True)
        cfg.save_settings()
    except Exception:
        pass
