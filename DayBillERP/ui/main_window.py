# ============================================================
# Saudi Arabia ERP - Main Window (Shell + Navigation)
# Sidebar nav, topbar, content area
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t, is_rtl, current_lang, load_language
from config.database import db


APP = None  # set to the live MainWindow so detached windows can navigate


def navigate(module_key):
    """Open a screen in the main content area from anywhere (e.g. the
    floating invoice window's toolbar). Brings the main window forward."""
    if APP is not None:
        try:
            APP._menu_open(module_key)
            APP.root.lift()
            APP.root.focus_force()
        except Exception:
            pass


class MainWindow:
    def __init__(self, root, current_user=None):
        self.root = root
        try:
            root._daybill_main = self      # pages can open reports / modules
        except Exception:
            pass
        self.current_user = current_user or {}
        globals()['APP'] = self
        # ── Global crash guard: any unhandled error inside a Tk
        #    callback (button clicks, timers, module screens) is logged
        #    and shown — the app NEVER closes or freezes because of it.
        self._last_err_dlg = 0.0
        self.root.report_callback_exception = self._tk_error
        # Modern, app-like styling for every form field across the app
        try:
            from ui.ui_kit import apply_modern_theme
            apply_modern_theme(self.root)
        except Exception as _e:
            print("[DayBill] modern theme skipped:", _e)
        # ERP keyboard flow + polish on EVERY widget as it appears
        # (all forms, all dialogs): Enter = next field, numpad Enter,
        # select-on-focus, hover states, striped sortable tables.
        try:
            from ui.ui_polish import enable_auto_polish
            enable_auto_polish(self.root)
        except Exception as _e:
            print("[DayBill] auto polish skipped:", _e)
        # auto-apply any pending SQL patches (idempotent), unless disabled
        try:
            from config import settings as _cfg
            if _cfg.get("auto_migrate", True):
                from modules import db_migrate
                applied, errs = db_migrate.run_pending()
                if applied:
                    print("[DayBill] applied patches:", ", ".join(applied))
                try:          # v6.9.5: every product has its 5-digit system barcode
                    from modules import barcode_resolver as _BR
                    _BR.ensure_system_barcodes()
                except Exception:
                    pass
                if errs:
                    from tkinter import messagebox
                    messagebox.showwarning(
                        "Database update",
                        "Some patches did not apply:\n" +
                        "\n".join(f"- {n}: {e}" for n, e in errs))
        except Exception as _e:
            print("[DayBill] migrate skipped:", _e)
        # v7.0: this company's country (tax, currency, financial year …) and
        # its business modules (restaurant, textiles, production …)
        try:
            from modules import country as _ctry, business as _biz
            _ctry.apply()
            _biz.invalidate()
            from ui import country_text as _ctext       # SAR → AED / ₹, VAT → GST on screens
            _ctext.install()
        except Exception as _e:
            print("[DayBill] country settings skipped:", _e)
        # once: customer / supplier opening balances into the books
        try:
            from config import settings as _cfg
            if not _cfg.flag("opening_balances_posted", False):
                from modules import opening_balances as _ob
                _n = _ob.backfill()
                if _n:
                    print("[DayBill] opening balances posted:", _n)
                _cfg.set("opening_balances_posted", True)
                _cfg.save_settings()
        except Exception as _e:
            print("[DayBill] opening balances skipped:", _e)
        # once (v5.26): old entries on Accounts Receivable / Payable → each
        # customer's / supplier's own ledger (statements + aging agree)
        try:
            from config import settings as _cfg
            if not _cfg.flag("party_lines_relinked_v526", False):
                from modules import posting as _po
                _n = _po.relink_control_lines()
                if _n:
                    print("[DayBill] party ledger lines moved:", _n)
                _cfg.set("party_lines_relinked_v526", True)
                _cfg.save_settings()
        except Exception as _e:
            print("[DayBill] party relink skipped:", _e)
        try:
            from ui.setup_wizard import maybe_run
            maybe_run(self.root)
        except Exception:
            pass
        try:    # ZATCA Phase 2: send waiting e-invoices in the background
            from ui import zatca_sender
            zatca_sender.start(self.root)
        except Exception:
            pass
        try:    # phones / PDT server + van auto-sync (Mobile & Van)
            from ui import mobile_center
            mobile_center.start_background(self.root)
        except Exception:
            pass
        try:
            from modules import audit
            audit.set_user(self.current_user)
            audit.log("login", "login", None,
                      f"{self.current_user.get('username','?')} opened DayBill")
        except Exception:
            pass
        try:
            from modules import permissions as _perm
            _perm.bootstrap_roles_and_permissions()
            _perm.set_session_user(self.current_user)
        except Exception:
            pass
        self.current_module = None
        self.nav_buttons = {}
        self._compute_rights()
        self._setup_window()
        self._build_layout()
        # open the first module the user is allowed to see
        first = self._first_allowed_module()
        if first:
            self._load_module(first)
        self._layout_ready = True
        # a new PC in a shop with several counters: which till is this?
        try:
            from ui.branches import choose_counter
            self.root.after(700, lambda: choose_counter(self.root))
        except Exception:
            pass
        # product key: quiet online check + ask for a key when read-only
        try:
            from modules import license as _lic
            _lic.background_check(self.root, on_done=self._refresh_license_chip)
            if not _lic.write_ok():
                self.root.after(1500, self._open_license)
        except Exception:
            pass
        # Settings ▸ Alerts: low stock / invoices due, once at start-up
        try:
            self.root.after(1200, self._startup_alerts)
        except Exception:
            pass

    def _startup_alerts(self):
        self._startup_toasts()
        if not (cfg.flag("notify_low_stock", True) or cfg.flag("notify_payment_due", True)):
            return
        if not (self._can_see("reports") or self._can_see("report_center")
                or self._can_see("dashboard")):
            return
        try:
            from ui import alerts
            alerts.show_startup_alerts(self.root, open_report=self._open_report)
        except Exception as e:
            print("[DayBill] alerts skipped:", e)

    def _startup_toasts(self):
        """v6.4: cloud backup too old · phone stock counts waiting for an OK."""
        msgs = []
        try:
            from modules import cloud_backup as _cb
            a = _cb.alert_text()
            if a:
                msgs.append((a, "warning"))
        except Exception:
            pass
        try:
            if self._can_see("stock_count"):
                from modules import cycle_count as _cc
                n = len(_cc.pending())
                if n:
                    msgs.append(("🧮 %d stock count(s) wait for your OK — Inventory ▸ Stock Count" % n, "info"))
        except Exception:
            pass
        try:                                       # v6.6: Iqama / passport / insurance expiring
            if self._can_see("hr"):
                from modules import hr_time as _ht
                d = _ht.expiry_text()
                if d:
                    msgs.append((d, "warning"))
        except Exception:
            pass
        try:                                       # v6.5: ZATCA 25th wave (1 Feb 2027)
            if self._can_see("zatca"):
                from modules.zatca import readiness as _zr
                z = _zr.startup_text()
                if z:
                    msgs.append((z, "warning"))
        except Exception:
            pass
        self.startup_toasts = [m for m, _k in msgs]
        try:
            from ui.ui_polish import toast
            for i, (m, k) in enumerate(msgs):
                self.root.after(i * 6500, lambda m=m, k=k: toast(self.root, m, k, 6000))
        except Exception:
            pass

    def _compute_rights(self):
        """Determine this user's rights. Admin gets everything."""
        u = self.current_user or {}
        is_admin = (str(u.get("username", "")).lower() == "admin")
        def flag(key):
            if is_admin:
                return True
            return bool(u.get(key, 0))
        self.rights = {
            "master":  flag("can_master"),
            "reports": flag("can_reports"),
            "edit":    flag("can_edit"),
            "delete":  flag("can_delete"),
            "admin":   is_admin,
        }
        # Which module keys each group unlocks
        self._module_group = {
            # Sales group — everyone who can log in can sell
            "dashboard": "always", "pos": "always", "sales": "always",
            "customers": "master", "sales_return": "always",
            # Purchase
            "suppliers": "master", "purchases": "master",
            "purchase_return": "master",
            "payments": "master",
            # Inventory / Master
            "products": "master", "inventory": "master",
            "barcode_designer": "master",
            "plu": "master",
            # Accounts
            "accounting": "reports", "hr": "master",
            "vouchers": "reports", "ledger": "reports",
            "audit_log": "admin", "print_settings": "admin", "day_close": "reports", "setup": "dashboard", "integrations": "admin", "expenses": "reports", "aging": "reports", "printer_mgmt": "admin", "account_defaults": "admin", "opening": "admin", "fin_reports": "reports", "cust_statement": "reports", "supp_statement": "reports", "report_center": "reports", "insights": "reports", "branches": "admin", "quotations": "always", "purchase_orders": "master", "price_labels": "master", "offers": "master", "label_print": "master", "mobile": "master",
            # v6.0
            "price_lists": "master", "stock_transfers": "master", "expiry": "master",
            "stock_count": "master", "price_updates": "master", "consumption": "master",
            "debit_notes": "always", "bank_rec": "reports", "year_end": "admin",
            # Reports
            "reports": "reports", "vat_report": "reports", "zatca": "reports",
            # Admin
            "users": "admin", "settings": "admin", "updates": "admin",
            "report_designer": "admin",
        }

    # Nav module key → (RBAC module, action) that unlocks it. Every screen
    # is listed, so the Users & Rights matrix controls ALL of them.
    _RBAC_NAV = {
        "dashboard": ("dashboard", "view"), "setup": ("dashboard", "view"),
        "pos": ("pos", "view"),
        "products": ("products", "view"), "customers": ("customers", "view"),
        "suppliers": ("suppliers", "view"),
        "sales": ("sales", "view"), "sales_return": ("sales_return", "view"),
        "purchases": ("purchase", "view"), "purchase_return": ("purchase_return", "view"),
        "inventory": ("inventory", "view"),
        "barcode_designer": ("products", "print"), "plu": ("products", "edit"),
        "accounting": ("accounts", "view"), "expenses": ("accounts", "view"),
        "vouchers": ("journal", "view"), "ledger": ("journal", "view"),
        "payments": ("payment", "view"), "day_close": ("day_close", "view"),
        "hr": ("hr", "view"),
        "reports": ("reports", "view"), "vat_report": ("reports", "view"),
        "zatca": ("reports", "view"), "fin_reports": ("reports", "view"),
        "aging": ("reports", "view"), "cust_statement": ("reports", "view"),
        "supp_statement": ("reports", "view"), "report_center": ("reports", "view"),
        "insights": ("reports", "view"),
        "branches": ("company_settings", "settings"),
        "quotations": ("quotation", "view"), "purchase_orders": ("purchase_order", "view"),
        "price_labels": ("products", "print"),
        "label_print": ("products", "print"),
        "mobile": ("inventory", "view"),
        "offers": ("products", "edit"),
        # v6.0
        "price_lists": ("products", "edit"), "stock_transfers": ("inventory", "view"),
        "stock_count": ("inventory", "view"), "price_updates": ("products", "edit"),
        "consumption": ("consumption", "view"),
        "expiry": ("inventory", "view"), "debit_notes": ("sales", "view"),
        "bank_rec": ("accounts", "view"), "year_end": ("accounts", "edit"),
        "users": ("users", "view"), "audit_log": ("audit_log", "view"),
        "settings": ("company_settings", "view"),
        "account_defaults": ("company_settings", "settings"),
        "opening": ("accounts", "edit"),
        "print_settings": ("company_settings", "settings"),
        "printer_mgmt": ("company_settings", "settings"),
        "report_designer": ("company_settings", "settings"),
        "integrations": ("company_settings", "settings"),
        "updates": ("company_settings", "settings"),
    }

    def _can_see(self, module_key):
        # v7.0: pages this company's country / business modules do not use
        try:
            from modules import business as _biz, country as _ctry
            if module_key in _biz.hidden_screens():
                return False
            if module_key == "zatca" and not _ctry.has_zatca():
                return False
        except Exception:
            pass
        # RBAC: when the rights tables exist they decide for every screen
        try:
            from modules import permissions as _perm
            if _perm.tables_ready():
                if _perm.is_full_access():
                    return True
                if module_key == "payments":      # receipts OR supplier payments
                    return _perm.can("receipt", "view") or _perm.can("payment", "view")
                if module_key == "vouchers":      # typed CR / CP / JV vouchers
                    return any(_perm.can(m, "view") for m in ("journal", "receipt", "payment"))
                m = self._RBAC_NAV.get(module_key)
                if m is None:
                    try:
                        from modules import business as _biz
                        m = _biz.RIGHTS.get(module_key)
                    except Exception:
                        m = None
                if m is None:
                    return False          # unknown screen: full-access users only
                mod, act = m if isinstance(m, tuple) else (m, "view")
                return _perm.can(mod, act)
        except Exception:
            pass
        # Legacy fallback (pre-RBAC databases)
        grp = self._module_group.get(module_key, "always")
        if grp == "always":
            return True
        if grp == "admin":
            return self.rights["admin"]
        if grp == "dashboard":
            return True
        return self.rights.get(grp, False)

    def _first_allowed_module(self):
        for k in ("dashboard", "sales", "products", "customers", "purchases",
                  "inventory", "accounting", "reports", "users", "settings"):
            if self._can_see(k):
                return k
        return None                     # (POS-only users use the POS button)

    # ── Window Setup ──────────────────────────────────────────
    def _setup_window(self):
        C = cfg.theme()
        w = cfg.get("window_width",  1280)
        h = cfg.get("window_height", 780)
        self.root.title(t("app_title"))
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(1024, 640)
        self.root.configure(bg=C["content_bg"])
        self._center_window(w, h)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # timed automatic SQL backup (Settings ▸ Backup)
        try:
            hours = float(cfg.get("backup_every_hours", 0) or 0)
            if hours > 0:
                self.root.after(int(hours * 3600 * 1000), self._backup_tick)
        except Exception:
            pass
        # v6.4: owner's evening report + nightly cloud backup (modules/daily_jobs)
        try:
            from modules import daily_jobs as _dj
            _dj.start(self.root)
        except Exception as e:
            print("[DayBill] daily jobs not started:", e)
        # v6.8: online forms (Tally) — quiet check at start + every hour
        try:
            from ui import online_forms_view as _ofv
            _ofv.start_auto(self.root)
        except Exception as e:
            print("[DayBill] online forms check not started:", e)
        # daily backup at a set time (Settings ▸ Backup ▸ Daily backup at)
        self._daily_backup_done = ""
        try:
            if str(cfg.get("backup_time", "") or "").strip():
                self.root.after(30 * 1000, self._backup_daily_tick)
        except Exception:
            pass
        # Use the whole screen (e.g. fills a 1600×900 display)
        try:
            self.root.state("zoomed")          # Windows / most Linux WMs
        except Exception:
            try:
                self.root.attributes("-zoomed", True)
            except Exception:
                pass
            try:                               # no WM zoom: fill the screen
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                self.root.geometry(f"{sw}x{sh - 40}+0+0")
            except Exception:
                pass
        # Windows 11 title bar (white, round corners) — no-op elsewhere
        try:
            from ui.ui_polish import win11_frame
            self.root.after(200, lambda: win11_frame(self.root))
        except Exception:
            pass

    def _center_window(self, w, h):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Layout ────────────────────────────────────────────────
    def _build_layout(self):
        C = cfg.theme()
        from ui.zoom import px

        # Outer container
        outer = tk.Frame(self.root, bg=C["content_bg"])
        outer.pack(fill="both", expand=True)
        self.outer = outer

        # Sidebar (left or right based on language) — navy, Windows 11 style
        side = "right" if is_rtl() else "left"
        self.sidebar = tk.Frame(outer, bg=C["sidebar_bg"], width=px(236))
        self.sidebar.pack(side=side, fill="y")
        self.sidebar.pack_propagate(False)

        # Main area
        self.main_area = tk.Frame(outer, bg=C["content_bg"])
        self.main_area.pack(side=side, fill="both", expand=True)

        # Topbar: search · POS · language · alerts · user
        # v6.3: slimmer header (58 → 44) — more room for the page
        self.topbar = tk.Frame(self.main_area, bg=C["topbar_bg"], height=px(44))
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)
        tk.Frame(self.main_area, bg=C["border"], height=1).pack(side="top", fill="x")

        # Taskbar (pinned bottom) — open/minimized windows dock here
        self.taskbar = tk.Frame(self.main_area, bg=C["card_bg"], height=px(32))
        self.taskbar.pack(side="bottom", fill="x")
        self.taskbar.pack_propagate(False)
        tk.Frame(self.main_area, bg=C["border"], height=1).pack(side="bottom", fill="x")
        tk.Label(self.taskbar, text="⊞", bg=C["card_bg"], fg=C["primary"],
                 font=("Segoe UI Symbol", 13)).pack(side="left", padx=(10, 4))
        # who / which database / which financial year — small, on the right
        self._who_lbl = None
        try:
            from modules import session_info
            self._who_lbl = tk.Label(self.taskbar, text=session_info.text(),
                                     font=("Segoe UI", 8), bg=C["card_bg"],
                                     fg=C.get("text_secondary", "#6B7280"))
            self._who_lbl.pack(side="right", padx=(6, 12))
        except Exception:
            pass

        # Content area = MDI desktop
        self.content = tk.Frame(self.main_area, bg=C["content_bg"])
        self.content.pack(fill="both", expand=True)

        from ui.mdi import MDIManager
        self.mdi = MDIManager(self.content, self.taskbar, C)
        self.mdi.on_focus = self._on_window_focus
        try:
            if self._who_lbl is not None:
                self.mdi.reserve_right = self._who_lbl.winfo_reqwidth() + 20
        except Exception:
            pass

        self._build_sidebar()
        self._build_topbar()
        self._build_menubar()

    def apply_live(self):
        """Re-apply theme + language to the whole app without a restart.
        Rebuilds the shell (sidebar/topbar/taskbar/menus) and reopens the
        window that was active. Behaviour settings already apply on use."""
        reopen = None
        try:
            if getattr(self, "mdi", None) and self.mdi.active:
                reopen = self.mdi.active.key
        except Exception:
            reopen = None
        try:
            self.root.config(menu=tk.Menu(self.root))   # clear old menubar
        except Exception:
            pass
        try:
            if getattr(self, "outer", None):
                self.outer.destroy()
        except Exception:
            pass
        # rebuild everything fresh with the new theme/language/text size
        try:
            from ui import zoom
            zoom.apply(self.root)
        except Exception:
            pass
        try:
            from ui.ui_kit import apply_modern_theme
            apply_modern_theme(self.root)
        except Exception:
            pass
        self._build_layout()
        try:
            self.root.configure(bg=cfg.theme()["content_bg"])
        except Exception:
            pass
        self._menu_open(reopen or "dashboard")

    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        def additem(menu, label, module=None, accel=None):
            if module and module.startswith("rc:"):
                menu.add_command(
                    label=label, accelerator=accel,
                    command=lambda r=module[3:]: self._open_report(r))
            elif module:
                menu.add_command(
                    label=label, accelerator=accel,
                    command=lambda m=module: self._menu_open(m))
            else:
                menu.add_command(
                    label=label, accelerator=accel,
                    command=lambda l=label: self._planned(l))

        # ── System ────────────────────────────────────────────
        m_sys = tk.Menu(menubar, tearoff=0)
        additem(m_sys, "Application Settings", "settings")
        additem(m_sys, "Company Profile", "settings")
        m_sys.add_separator()
        additem(m_sys, "Print & Invoice", "print_settings")
        additem(m_sys, "Printer Management", "printer_mgmt")
        additem(m_sys, "Invoice Designer", "report_designer")
        m_sys.add_separator()
        m_lbl = tk.Menu(m_sys, tearoff=0)
        additem(m_lbl, "Label Design", "barcode_designer")
        additem(m_lbl, "Print Barcode Labels", "label_print")
        additem(m_lbl, "Mobile, PDT && Van Sales", "mobile")
        additem(m_lbl, "Price Change Labels", "price_labels")
        m_lbl.add_command(label="Price Check (F8 in POS)",
                          command=lambda: __import__("ui.close_guard", fromlist=["x"]).single(
                              "price_check", lambda: __import__("ui.price_check", fromlist=["x"])
                              .open_price_check(self.root)))
        additem(m_lbl, "PLU Manager (Scale)", "plu")
        m_sys.add_cascade(label="Barcode && Labels", menu=m_lbl)
        m_sys.add_separator()
        additem(m_sys, "Users && Rights", "users")
        additem(m_sys, "Audit Log", "audit_log")
        m_sys.add_separator()
        additem(m_sys, "Vouchers", "vouchers")
        additem(m_sys, "Day Close", "day_close")
        m_sys.add_separator()
        additem(m_sys, "Export / Import (Products)", "products")
        additem(m_sys, "Integrations (Wathq)", "integrations")
        additem(m_sys, "Updates", "updates")
        m_sys.add_separator()
        m_sys.add_command(label="Exit", command=self._logout)
        menubar.add_cascade(label="System", menu=m_sys)

        # ── Accounts ──────────────────────────────────────────
        m_acc = tk.Menu(menubar, tearoff=0)
        m_acc_m = tk.Menu(m_acc, tearoff=0)
        additem(m_acc_m, "Account Group", "accounting")
        additem(m_acc_m, "Account Ledger", "ledger")
        additem(m_acc_m, "Chart Of Accounts", "accounting")
        additem(m_acc_m, "Branch Ledgers", "ledger")
        additem(m_acc_m, "Default Accounts", "account_defaults")
        additem(m_acc_m, "Customers", "customers")
        additem(m_acc_m, "Suppliers", "suppliers")
        additem(m_acc_m, "Customer Ledger (statement)", "cust_statement")
        additem(m_acc_m, "Supplier Ledger (statement)", "supp_statement")
        m_acc.add_cascade(label="Masters", menu=m_acc_m)

        m_acc_t = tk.Menu(m_acc, tearoff=0)
        additem(m_acc_t, "Cash Payments", "payments", "Ctrl+P")
        m_acc_t.add_command(label="New Cash Payment (CP)", accelerator="F7",
                            command=lambda: self._run_favourite("cash_payment"))
        additem(m_acc_t, "Cash Receipts", "payments")
        m_acc_t.add_command(label="New Cash Receipt (CR)", accelerator="F6",
                            command=lambda: self._run_favourite("cash_receipt"))
        additem(m_acc_t, "Bank Payment / Contra", "payments")
        additem(m_acc_t, "Bank Receipt / Contra", "payments")
        additem(m_acc_t, "Opening Balances (accounts, stock, parties)", "opening")
        additem(m_acc_t, "Vouchers (journal entries)", "vouchers", "Ctrl+J")
        m_acc_t.add_command(label="New Journal Voucher (JV)", accelerator="Ctrl+Shift+J",
                            command=lambda: self._run_favourite("journal_new"))
        m_acc_t.add_command(label="New Bank Payment (BP)",       # v7.1 multi-line vouchers
                            command=lambda: self._run_favourite("bank_payment"))
        m_acc_t.add_command(label="New Bank Receipt (BR)",
                            command=lambda: self._run_favourite("bank_receipt"))
        m_acc_t.add_command(label="New Contra (cash ↔ bank) (CT)",
                            command=lambda: self._run_favourite("contra_new"))
        additem(m_acc_t, "Debit Note (sales)", "debit_notes")
        additem(m_acc_t, "Credit Note (sales return)", "sales_return")
        additem(m_acc_t, "Closing Balance (financial reports)", "fin_reports")
        additem(m_acc_t, "Multi Journal Entry", "vouchers")
        additem(m_acc_t, "Vouchers List", "vouchers")
        additem(m_acc_t, "Day Close / Z-Report", "day_close", "Ctrl+Shift+Z")
        additem(m_acc_t, "Expenses", "expenses")
        additem(m_acc_t, "Tax On Expenses", "expenses")
        additem(m_acc_t, "Bank Reconciliation", "bank_rec")
        additem(m_acc_t, "Year-End Closing", "year_end")
        m_acc.add_cascade(label="Transactions", menu=m_acc_t)

        m_acc_r = tk.Menu(m_acc, tearoff=0)
        for lbl, rid in (("Trial Balance", "trial_balance"),
                         ("Profit And Loss Account", "profit_loss"),
                         ("Balance Sheet", "balance_sheet"),
                         ("Day Book", "day_book"),
                         ("Cash Book", "cash_book"), ("Bank Book", "bank_book"),
                         ("Ledger Report", "ledger"),
                         ("Journal Register", "journal_register"),
                         (None, None),
                         ("VAT Return", "vat_return"), ("VAT Detail Register", "vat_detail"),
                         ("Output VAT Register (Sales VAT)", "output_vat"),
                         ("Input VAT Register (Purchase VAT)", "input_vat"),
                         (None, None),
                         ("Cash & Bank Balances", "cash_bank"),
                         ("Day Report", "day_report"),
                         (None, None),
                         ("Outstanding — Customers", "receivables"),
                         ("Outstanding — Suppliers", "payables"),
                         ("Receivable Aging", "receivable_aging"),
                         ("Payable Aging", "payable_aging"),
                         ("Customer Outstanding Bills", "receivable_bills"),
                         ("Supplier Outstanding Bills", "payable_bills"),
                         ("Payment / Collection Report", "receipts_payments"),
                         ("Expense Report", "expenses"),
                         ("Expense Summary (all expenses)", "expense_summary"),
                         ("Opening Balances", "opening_balances"),
                         ("Daily Summary Report", "sales_daily"),
                         ("Billwise Profit Report (Sales)", "bill_profit"),
                         ("Counter Shift Report (POS)", "pos_summary"),
                         ("Cashier Shifts (opening float / counted cash)", "cashier_shifts"),
                         ("Party Summary Report", "sales_customers")):
            if lbl is None:
                m_acc_r.add_separator()
            else:
                additem(m_acc_r, lbl, "rc:" + rid)
        m_acc_r.add_separator()
        additem(m_acc_r, "Outstanding / Aging", "aging")
        additem(m_acc_r, "Cash Flow Statement", "fin_reports")
        additem(m_acc_r, "Customer Statement", "cust_statement")
        additem(m_acc_r, "Supplier Statement", "supp_statement")
        m_acc.add_cascade(label="Reports", menu=m_acc_r)
        menubar.add_cascade(label="Accounts", menu=m_acc)

        # ── Inventory ─────────────────────────────────────────
        m_inv = tk.Menu(menubar, tearoff=0)
        m_inv_m = tk.Menu(m_inv, tearoff=0)
        additem(m_inv_m, "Products", "products", "F8")
        for lbl in ("Product Groups", "Product Category", "Brands",
                    "Price Category", "Unit of Measures", "Vehicles",
                    "Tax Category", "Product Prices", "Sales Route",
                    "Salesman Route", "General Master", "Schemes",
                    "Scheme Settings", "Group Category", "Sections"):
            additem(m_inv_m, lbl, "price_lists" if lbl == "Price Category" else
                    ("products" if "Product" in lbl else
                     ("offers" if lbl.startswith("Scheme") else None)))
        m_inv.add_cascade(label="Masters", menu=m_inv_m)

        m_inv_t = tk.Menu(m_inv, tearoff=0)
        additem(m_inv_t, "Sales Quotation", "quotations")
        additem(m_inv_t, "Offers & Promotions", "offers")
        additem(m_inv_t, "Sales", "sales")
        additem(m_inv_t, "POS (cashier)", "pos", "F3")
        additem(m_inv_t, "VAT Sales Invoice", "sales", "F2")
        additem(m_inv_t, "Sales Return", "sales_return", "Ctrl+R")
        additem(m_inv_t, "Sales Return / Credit Note (VAT)", "sales_return")
        additem(m_inv_t, "Purchase Order", "purchase_orders")
        additem(m_inv_t, "Purchase Invoice", "purchases")
        additem(m_inv_t, "VAT Purchase Invoice", "purchases", "F4")
        additem(m_inv_t, "Purchase Return", "purchases")
        additem(m_inv_t, "Purchase Return VAT", "purchase_return", "Ctrl+Shift+R")
        additem(m_inv_t, "Stock Journal", "inventory")
        additem(m_inv_t, "Stock Transfer (between branches)", "stock_transfers")
        additem(m_inv_t, "Batches & Expiry", "expiry")
        additem(m_inv_t, "Stock Count (phone / cycle count)", "stock_count")
        additem(m_inv_t, "Price Updates (cost went up)", "price_updates")
        m_inv_t.add_command(label="Opening Stock", command=self._open_opening_stock)
        m_inv.add_cascade(label="Transactions", menu=m_inv_t)

        m_inv_r = tk.Menu(m_inv, tearoff=0)
        for lbl, rid in (("Stock Report", "stock"),
                         ("Stock Valuation / Inventory Summary", "stock_valuation"),
                         ("Stock Flow / Movement Report", "stock_movement"),
                         ("Stock Ledger Report (Item Card)", "stock_ledger"),
                         ("Stock Transactions (all movements)", "stock_transactions"),
                         ("Low Stock / Reorder", "low_stock"),
                         ("Stock by Branch", "stock_by_branch"),
                         ("Batches & Expiry", "expiry_report"),
                         ("Non-moving / Dead Stock", "dead_stock"),
                         (None, None),
                         ("Sales Register", "sales_register"),
                         ("Sales Register — item details", "sales_lines"),
                         ("Item wise Sales & Profit", "sales_items"),
                         ("Category wise Sales", "sales_category"),
                         ("Customer wise Sales", "sales_customers"),
                         ("Daily Statements", "sales_daily"),
                         ("POS Bills", "pos_bills"), ("POS / Counter Summary", "pos_summary"),
                         ("Sales Return Register", "sales_returns"),
                         (None, None),
                         ("Purchase Register", "purchase_register"),
                         ("Purchase Register — item details", "purchase_lines"),
                         ("Item wise Purchases", "purchase_items"),
                         ("Supplier wise Purchases", "purchase_suppliers"),
                         ("Purchase Return Register", "purchase_returns"),
                         (None, None),
                         ("Tax Reports (VAT Detail)", "vat_detail"),
                         ("Output VAT Register (Sales VAT)", "output_vat"),
                         ("Input VAT Register (Purchase VAT)", "input_vat"),
                         ("VAT Return", "vat_return")):
            if lbl is None:
                m_inv_r.add_separator()
            else:
                additem(m_inv_r, lbl, "rc:" + rid)
        m_inv_r.add_separator()
        additem(m_inv_r, "Graphical Reports", "reports")
        m_inv.add_cascade(label="Reports", menu=m_inv_r)
        additem(m_inv, "Search Invoice", "sales")
        menubar.add_cascade(label="Inventory", menu=m_inv)

        # ── Reports (every report, grouped) ───────────────────
        m_rep = tk.Menu(menubar, tearoff=0)
        additem(m_rep, "Reports Center…", "report_center")
        additem(m_rep, "🤖 Smart Insights (AI)", "insights")
        m_rep.add_separator()
        try:
            from modules import report_center as _RC
            _groups = {}
            for _spec in _RC.catalog():
                if _spec["group"] not in _groups:
                    _groups[_spec["group"]] = tk.Menu(m_rep, tearoff=0)
                    m_rep.add_cascade(label=_spec["group"], menu=_groups[_spec["group"]])
                additem(_groups[_spec["group"]], _spec["title"], "rc:" + _spec["id"])
        except Exception:
            pass
        m_rep.add_separator()
        additem(m_rep, "Graphical Reports", "reports")
        additem(m_rep, "VAT Report (form)", "vat_report")
        menubar.add_cascade(label="Reports", menu=m_rep)

        # ── HR ────────────────────────────────────────────────
        m_hr = tk.Menu(menubar, tearoff=0)
        additem(m_hr, "Employees", "hr")
        # v6.6: each item opens its own tab (before, all opened Employees)
        for _lbl, _tab in (("Payroll", "payroll"), ("Attendance", "attendance"), ("Leave Management", "leave"),
                           ("Loans / Advances", "loans"), ("End of Service / Final Settlement", "eos"),
                           ("Documents (Iqama, passport, insurance)", "documents")):
            m_hr.add_command(label=_lbl, command=lambda tb=_tab: self._open_hr(tb))
        m_hr.add_separator()
        for _lbl, _rid in (("Payroll Register", "payroll_register"), ("GOSI Contributions", "gosi_report"),
                           ("Leave Balances", "leave_balances"), ("Attendance Summary", "attendance_summary"),
                           ("Documents Expiry", "hr_documents"), ("End-of-Service Liability", "eos_liability")):
            m_hr.add_command(label="📊  " + _lbl, command=lambda r=_rid: self._open_report(r))
        menubar.add_cascade(label="HR", menu=m_hr)

        # ── Windows ───────────────────────────────────────────
        m_win = tk.Menu(menubar, tearoff=0)
        additem(m_win, "Dashboard", "dashboard")
        additem(m_win, "POS / Cashier", "pos")
        m_win.add_command(label="Calculator", command=self._calculator)
        additem(m_win, "Change Password", "users")
        m_win.add_command(label="Refresh", accelerator="F5", command=self._refresh_active)
        menubar.add_cascade(label="Windows", menu=m_win)

        # ── Languages ─────────────────────────────────────────
        m_lang = tk.Menu(menubar, tearoff=0)
        m_lang.add_command(label="English", command=lambda: self._set_lang("en"))
        m_lang.add_command(label="العربية (Arabic)", command=lambda: self._set_lang("ar"))
        menubar.add_cascade(label="Languages", menu=m_lang)

        # ── Help ──────────────────────────────────────────────
        m_help = tk.Menu(menubar, tearoff=0)
        from ui import shortcuts as _scm
        m_help.add_command(label="⌨  Keyboard Shortcuts", accelerator="F1",
                           command=lambda: _scm.show(self.root))
        m_help.add_separator()
        additem(m_help, "Setup Checklist", "setup")
        m_help.add_command(label="Run Setup Wizard", command=self._run_wizard)
        m_help.add_separator()
        m_help.add_command(label="🔑 Product Key…", command=self._open_license)
        m_help.add_command(label="About DayBill ERP", command=self._about)
        additem(m_help, "User Guide", "setup")
        menubar.add_cascade(label="Help", menu=m_help)

        try:
            self.root.config(menu=menubar)
        except Exception:
            pass

        # Polosys-style global hotkeys
        # Only when the key isn't already used by the window/screen that
        # has focus (Sales, POS, Product form… have their own F-keys), and
        # Ctrl shortcuts never fire while typing in a field.
        def hot(seq, fn, typing_safe=False, shift=False):
            def handler(e):
                try:
                    if shift and not (e.state & 0x0001):
                        return            # Ctrl+R vs Ctrl+Shift+R (Caps Lock safe)
                    if not shift and seq.startswith("<Control-") and (e.state & 0x0001) \
                            and seq[-2:-1].isalpha():
                        return
                    w = e.widget if isinstance(e.widget, tk.Misc) else None
                    if w is None or w.winfo_toplevel() is not self.root:
                        return            # another window (POS, forms, dialogs)
                    if typing_safe and isinstance(w, (tk.Entry, tk.Text, ttk.Entry,
                                                      ttk.Combobox, tk.Spinbox)):
                        return            # e.g. Ctrl+Z = undo while typing
                    x = w
                    while x is not None and x is not self.root:
                        if x.bind(seq):
                            return        # this screen defines the key itself
                        x = x.master
                except Exception:
                    return
                fn()
                return "break"
            self.root.bind_all(seq, handler)
        try:
            # v6.9.3: the whole list is in ui/shortcuts.py (Help ▸ ⌨ Keyboard Shortcuts, F1)
            from ui import shortcuts as _sc
            hot("<F1>", lambda: _sc.show(self.root))
            hot("<F2>", lambda: self._menu_open("sales"))
            hot("<F3>", lambda: self._menu_open("pos"))
            hot("<F4>", lambda: self._menu_open("purchases"))
            hot("<F6>", lambda: self._run_favourite("cash_receipt"))
            hot("<F7>", lambda: self._run_favourite("cash_payment"))
            hot("<F8>", lambda: self._menu_open("products"))
            hot("<F9>", lambda: self._menu_open("ledger"))
            hot("<F11>", lambda: self._menu_open("inventory"))
            hot("<F12>", lambda: self._menu_open("report_center"))
            hot("<Control-n>", self._new_in_screen, typing_safe=True)
            hot("<Control-l>", lambda: self._menu_open("ledger"), typing_safe=True)
            hot("<Control-i>", lambda: self._menu_open("inventory"), typing_safe=True)
            hot("<Control-e>", lambda: self._menu_open("expenses"), typing_safe=True)
            hot("<Control-r>", lambda: self._menu_open("sales_return"), typing_safe=True)
            hot("<Control-R>", lambda: self._menu_open("purchase_return"), typing_safe=True,
                shift=True)
            hot("<Control-N>", lambda: self._run_favourite("add_product"), typing_safe=True,
                shift=True)
            hot("<Control-C>", lambda: self._run_favourite("new_consumption"), typing_safe=True,
                shift=True)
            hot("<Control-J>", lambda: self._run_favourite("journal_new"), typing_safe=True,
                shift=True)
            hot("<Control-p>", lambda: self._menu_open("payments"), typing_safe=True)
            hot("<Control-j>", lambda: self._menu_open("vouchers"), typing_safe=True)
            # Day Close moved from Ctrl+Z (= undo everywhere else) to Ctrl+Shift+Z
            hot("<Control-Z>", lambda: self._menu_open("day_close"), typing_safe=True,
                shift=True)
            hot("<F5>", lambda: self._refresh_active())
            # the open screens (MDI windows): close / next / previous
            hot("<Control-w>", self._close_screen, typing_safe=True)
            hot("<Control-F4>", self._close_screen)
            hot("<Control-Tab>", lambda: self._next_screen(1))
            hot("<Control-ISO_Left_Tab>", lambda: self._next_screen(-1))
            hot("<Control-Shift-Tab>", lambda: self._next_screen(-1))
        except Exception:
            pass

    def _close_screen(self):
        """Ctrl+W / Ctrl+F4 — close the open screen (MDI window)."""
        try:
            ch = self.mdi.active
            if ch is not None:
                self.mdi.close(ch)
        except Exception:
            pass

    def _next_screen(self, step=1):
        """Ctrl+Tab / Ctrl+Shift+Tab — next / previous open screen."""
        try:
            keys = list(self.mdi.windows.keys())
            if len(keys) < 2:
                return
            cur = getattr(self.mdi.active, "key", keys[0])
            i = (keys.index(cur) + step) % len(keys) if cur in keys else 0
            self.mdi.windows[keys[i]].restore()
        except Exception:
            pass

    # Ctrl+N in the main window: a new record of the screen that is open
    _NEW_FOR = {"sales": "sales", "purchases": "purchase", "sales_return": "sales_return",
                "purchase_return": "purchase_return", "expenses": "expense",
                "consumption": "consumption", "vouchers": "journal", "accounting": "journal",
                "payments": "receipt"}

    def _new_in_screen(self):
        ch = getattr(getattr(self, "mdi", None), "active", None)
        key = getattr(ch, "key", None) or getattr(self, "current_module", None)
        parent = getattr(self, "content", None) or self.root
        from modules import permissions as _pm
        try:
            if key in self._NEW_FOR:
                from ui import txn_connector as tc
                tc.new_txn(parent, self._NEW_FOR[key], self._refresh_active)
            elif key == "products":
                self._run_favourite("add_product")
            elif key == "customers":
                if _pm.allowed("customers", "add"):
                    from ui.customers import CustomerForm
                    CustomerForm(parent, on_save=self._refresh_active)
            elif key == "suppliers":
                if _pm.allowed("suppliers", "add"):
                    from ui.suppliers import SupplierForm
                    SupplierForm(parent, on_save=self._refresh_active)
            elif key in ("quotations", "purchase_orders"):
                mod = "quotation" if key == "quotations" else "purchase_order"
                if _pm.allowed(mod, "add"):
                    from ui.quotes import DocForm
                    DocForm(parent, "quotation" if key == "quotations" else "purchase_order",
                            on_save=self._refresh_active)
            else:
                from ui import shortcuts as _sc
                _sc.show(self.root, "Everywhere")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("New", str(e)[:200])

    def _menu_open(self, module_key):
        if self._can_see(module_key):
            self._load_module(module_key)
        else:
            from tkinter import messagebox
            messagebox.showinfo("Permission",
                                "You don't have permission for this screen.")

    def _refresh_active(self):
        """Reload the focused MDI window's screen."""
        try:
            ch = self.mdi.active
            if ch and ch.key == "report_center":
                v = getattr(self, "_rc_view", None)
                if v is not None and v.frame.winfo_exists():
                    v.run()                    # F5 in Reports = Run
                    return
            if ch:
                key = ch.key
                self.mdi.close(ch)
                self._menu_open(key)
        except Exception:
            pass

    def _open_opening_stock(self):
        """Inventory ▸ Opening Stock → Opening Balances, stock tab."""
        self._opening_tab = "stock"
        self._menu_open("opening")
        try:
            import gc
            from ui.opening_balances import OpeningBalancesView
            for o in gc.get_objects():
                if isinstance(o, OpeningBalancesView) and o.frame.winfo_exists():
                    o.nav.show("stock")
        except Exception:
            pass

    def _open_hr(self, tab):
        """HR ▸ Attendance / Leave open the HR page on that tab (v6.0)."""
        try:
            from ui.hr import HRView
            HRView.start_tab = tab
            ch = self.mdi.windows.get("hr") if hasattr(self, "mdi") else None
            if ch is not None:                  # already open: re-open on the tab
                try:
                    self.mdi.close(ch)
                except Exception:
                    pass
        except Exception:
            pass
        self._menu_open("hr")

    def _open_report(self, rid):
        """Open the Reports Center on a given report (menus use this)."""
        if not self._can_see("report_center"):
            messagebox.showinfo("Permission", "You don't have permission for reports.")
            return
        self._rc_pending = rid
        self._menu_open("report_center")
        v = getattr(self, "_rc_view", None)
        try:
            if v is not None and v.frame.winfo_exists() and v._current != rid:
                v.select(rid)
        except Exception:
            pass

    def _calculator(self):
        try:
            from ui.calculator import Calculator
            from ui import close_guard
            close_guard.single("calculator", lambda: Calculator(self.root))   # one at a time
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Calculator", str(e)[:160])

    def _planned(self, name):
        from tkinter import messagebox
        messagebox.showinfo(
            "Polosys-style module",
            f"'{name}' is part of the full Polosys menu structure.\n\n"
            f"The menu slot is ready — this screen is planned for an upcoming "
            f"build. Tell me to build '{name}' next and I will.")

    def _set_lang(self, lang):
        try:
            cfg.set("language", lang); cfg.save_settings()
            from tkinter import messagebox
            messagebox.showinfo("Language",
                                "Language changed. Please restart the app.")
        except Exception:
            pass

    def _run_wizard(self):
        try:
            from ui.setup_wizard import SetupWizard
            SetupWizard(self.root)
        except Exception:
            pass

    def _about(self):
        from tkinter import messagebox
        from config import version as _v
        messagebox.showinfo(
            "About",
            "%s  %s\n%s\n%s\n\nSaudi Arabia billing, accounting, inventory, POS & payroll\n"
            "ZATCA Phase 1 & 2 compliant · Bilingual EN/AR" % (
                _v.APP_NAME, _v.VERSION, _v.subtitle(), _v.TAGLINE))

    def _nav_def(self):
        """The menu: (group heading, [(key, icon, label_key), …]).
        v7.0: the company's business modules add their groups after
        Inventory (Restaurant, Production, Textiles) and the country
        decides the tax pages (ZATCA only in Saudi Arabia)."""
        groups = self._nav_base()
        try:
            from modules import business as _biz, country as _ctry
            extra = _biz.nav_groups()
            i = next((n for n, (g, _it) in enumerate(groups) if g == "Inventory"), len(groups) - 1)
            groups[i + 1:i + 1] = [(g, list(items)) for g, items in extra]
            p = _ctry.profile()
            for g, items in groups:
                for n, it in enumerate(items):
                    if it[0] == "vat_report" and p["code"] != "SA":
                        items[n] = (it[0], it[1], "GST Returns" if p["code"] == "IN" else "VAT 201 Return")
        except Exception as _e:
            print("[DayBill] business menu skipped:", _e)
        return groups

    def _nav_base(self):
        return [
            ("", [
                ("dashboard",  "🏠", "nav.dashboard"),
            ]),
            ("Sales", [
                ("pos",        "🛍", "nav.pos"),
                ("sales",      "🧾", "nav.sales"),
                ("quotations", "📝", "Quotations"),
                ("offers",     "🏷", "Offers & Promotions"),
                ("sales_return", "↩", "nav.sales_return"),
                ("debit_notes", "➕", "Debit Notes"),
                ("customers",  "👥", "nav.customers"),
                ("cust_statement", "📄", "Customer Statement"),
            ]),
            ("Purchase", [
                ("purchases",  "🛒", "nav.purchases"),
                ("purchase_orders", "📋", "Purchase Orders"),
                ("purchase_return", "↩", "nav.purchase_return"),
                ("suppliers",  "🏭", "nav.suppliers"),
                ("supp_statement", "📄", "Supplier Statement"),
            ]),
            ("Inventory", [
                ("products",   "📦", "nav.products"),
                ("inventory",  "🗃", "nav.inventory"),
                ("price_lists", "💲", "Price Lists"),
                ("stock_transfers", "🔁", "Stock Transfers"),
                ("expiry", "⏰", "Batches & Expiry"),
                ("label_print", "🖨", "Print Barcode Labels"),
                ("stock_count", "🧮", "nav.stock_count"),
                ("consumption", "🍞", "Consumable Entry"),
                ("mobile", "📱", "Mobile, PDT & Van"),
                ("barcode_designer", "🏷", "nav.barcode_designer"),
                ("price_updates", "📈", "nav.price_updates"),
                ("price_labels", "💲", "Price Change Labels"),
            ]),
            ("Accounts", [
                ("accounting", "📒", "nav.accounting"),
                ("opening",    "🏁", "Opening Balances"),
                ("ledger",     "📖", "Account Ledger"),
                ("vouchers",   "🧾", "Vouchers"),
                ("payments",   "💳", "nav.payments"),
                ("expenses",   "💸", "Expenses & Assets"),
                ("aging",      "⏳", "Outstanding / Aging"),
                ("fin_reports", "📊", "Financial Reports"),
                ("day_close",  "🌙", "Day Close / Z-Report"),
                ("bank_rec",   "🏦", "Bank Reconciliation"),
                ("year_end",   "📅", "Year-End Closing"),
                ("account_defaults", "🔗", "Default Accounts"),
            ]),
            ("HR & Payroll", [
                ("hr",         "👔", "nav.hr"),
            ]),
            ("Reports & Compliance", [
                ("report_center", "📊", "Reports Center"),
                ("insights", "🤖", "Smart Insights (AI)"),
                ("reports",    "📈", "nav.reports"),
                ("vat_report", "📋", "nav.vat_report"),
                ("zatca",      "🔐", "nav.zatca"),
                ("report_designer", "🧩", "nav.report_designer"),
            ]),
            ("Administration", [
                ("users",      "👤", "nav.users"),
                ("branches",   "🏬", "Branches & Counters"),
                ("audit_log",  "📜", "Audit Log"),
                ("print_settings", "🖨", "Print & Invoice"),
                ("printer_mgmt", "🖨", "Printer Management"),
                ("integrations", "🔌", "Integrations"),
                ("setup",      "✅", "Setup Checklist"),
                ("settings",   "⚙️", "nav.settings"),
                ("updates",    "🔄", "nav.updates"),
            ]),
        ]

    # ── Sidebar ───────────────────────────────────────────────
    def _build_sidebar(self):
        if cfg.flag("sidebar_collapsed", False):
            return self._build_rail()
        C = cfg.theme()
        sb = self.sidebar
        SB = C["sidebar_bg"]
        rtl = is_rtl()
        near = "right" if rtl else "left"
        anchor = "e" if rtl else "w"
        from ui.zoom import px
        from config import version as _ver

        # ── Brand: logo + app name + sub name ──
        brand = tk.Frame(sb, bg=SB, cursor="hand2")
        brand.pack(fill="x", padx=px(14), pady=(px(14), px(10)))
        s = px(40)
        ic = tk.Canvas(brand, width=s, height=s, bg=SB, highlightthickness=0, bd=0,
                       cursor="hand2")
        ic.pack(side=near)
        self._logo_mark(ic, s, C)
        txt = tk.Frame(brand, bg=SB, cursor="hand2")
        txt.pack(side=near, fill="x", expand=True,
                 padx=(0, px(10)) if rtl else (px(10), 0))
        l1 = tk.Label(txt, text=_ver.APP_NAME, font=("Segoe UI", 14, "bold"), bg=SB,
                      fg="white", anchor=anchor, cursor="hand2")
        l1.pack(fill="x")
        l2 = tk.Label(txt, text=_ver.subtitle(), font=("Segoe UI", 8), bg=SB,
                      fg=C.get("sidebar_muted", "#9AA3C7"), anchor=anchor,
                      justify="right" if rtl else "left", wraplength=px(170), cursor="hand2")
        l2.pack(fill="x")
        for w in (brand, ic, txt, l1, l2):
            w.bind("<Button-1>", lambda e: self._load_module("dashboard"))

        # ── Search the menu ──
        self._build_nav_search(sb, C)

        nav_groups = self._nav_def()

        # ── Bottom: Logout, then the app name · tagline · version ──
        foot = tk.Frame(sb, bg=SB, cursor="hand2")
        foot.pack(side="bottom", fill="x", padx=px(14), pady=(px(4), px(12)))
        fs = px(28)
        fic = tk.Canvas(foot, width=fs, height=fs, bg=SB, highlightthickness=0, bd=0,
                        cursor="hand2")
        fic.pack(side=near, anchor="n", pady=(px(2), 0))
        self._logo_mark(fic, fs, C)
        ft = tk.Frame(foot, bg=SB, cursor="hand2")
        ft.pack(side=near, fill="x", expand=True, padx=(0, px(8)) if rtl else (px(8), 0))
        f1 = tk.Label(ft, text=_ver.APP_NAME, font=("Segoe UI", 10, "bold"), bg=SB,
                      fg="white", anchor=anchor, cursor="hand2")
        f1.pack(fill="x")
        f2 = tk.Label(ft, text=_ver.TAGLINE, font=("Segoe UI", 8), bg=SB,
                      fg=C.get("sidebar_muted", "#9AA3C7"), anchor=anchor, cursor="hand2")
        f2.pack(fill="x")
        f3 = tk.Label(ft, text="Version " + _ver.VERSION, font=("Segoe UI", 8), bg=SB,
                      fg=C.get("sidebar_muted", "#9AA3C7"), anchor=anchor, cursor="hand2")
        f3.pack(fill="x")
        self._version_lbl = f3
        for w in (foot, fic, ft, f1, f2, f3):
            w.bind("<Button-1>", lambda e: self._about())

        bottom = tk.Frame(sb, bg=SB)
        bottom.pack(side="bottom", fill="x")
        tk.Frame(bottom, bg=C["sidebar_hover"], height=1).pack(fill="x", padx=px(14), pady=(0, px(4)))

        # Scrollable nav area (so all groups are reachable on small screens)
        navwrap = tk.Frame(sb, bg=SB)
        navwrap.pack(side="top", fill="both", expand=True)
        nav_canvas = tk.Canvas(navwrap, bg=SB, highlightthickness=0, bd=0)
        nav_canvas.pack(side="left", fill="both", expand=True)
        self._nav_canvas = nav_canvas

        self.nav_frame = tk.Frame(nav_canvas, bg=SB)
        navwin = nav_canvas.create_window((0, 0), window=self.nav_frame, anchor="nw")
        nav_canvas.bind("<Configure>",
                        lambda e: nav_canvas.itemconfig(navwin, width=e.width))
        self.nav_frame.bind(
            "<Configure>",
            lambda e: nav_canvas.configure(scrollregion=nav_canvas.bbox("all")))

        def _wheel(e):
            if e.num == 4:
                d = -1
            elif e.num == 5:
                d = 1
            else:
                d = int(-1 * (e.delta / 120)) or (-1 if e.delta > 0 else 1)
            top, bot = nav_canvas.yview()
            if (d < 0 and top <= 0) or (d > 0 and bot >= 1):
                return "break"
            nav_canvas.yview_scroll(d, "units")
            return "break"
        self._nav_wheel = _wheel

        # the menu tree (headings + pages) and the search results share the area
        self._nav_tree = tk.Frame(self.nav_frame, bg=SB)
        self._nav_tree.pack(fill="x")
        self._nav_res = tk.Frame(self.nav_frame, bg=SB)      # shown while searching

        self._nav_index = []            # (key, icon, label, group) for search
        self._nav_icons = {}
        # every heading folds its pages away (click the heading to open it)
        self._nav_groups = {}           # group -> {"body", "arrow", "header"}
        self._nav_key_group = {}        # module key -> group
        top_frame = self._nav_tree
        self.nav_frame = top_frame
        for group_name, items in nav_groups:
            visible = [it for it in items if self._can_see(it[0])]
            if not visible:
                continue   # whole group hidden if user has no items in it
            body = None
            if group_name:
                self.nav_frame = top_frame
                header, arrow = self._nav_group_header(group_name)
                body = tk.Frame(top_frame, bg=SB)
                self._nav_groups[group_name] = {"body": body, "arrow": arrow,
                                                "header": header}
                self.nav_frame = body
            for key, icon, label_key in visible:
                label = t(label_key) if str(label_key).startswith("nav.") else label_key
                self._nav_button(key, icon, label)
                self._nav_index.append((key, icon, label, group_name or "Home"))
                self._nav_icons[key] = icon
                if group_name:
                    self._nav_key_group[key] = group_name
            self.nav_frame = top_frame
            if not group_name:                 # v6.9.3: ⭐ Favourites under Home
                self._build_favourites(top_frame)
        # open the heading used last time (or none) — the rest stay folded
        self._nav_open = None
        last = str(cfg.get("nav_open_group", "") or "")
        if last in self._nav_groups:
            self._nav_toggle(last, remember=False)

        # build the logout button into the pinned bottom frame
        saved = self.nav_frame
        self.nav_frame = bottom
        self._nav_button("logout", "⏻", t("nav.logout"), is_logout=True)
        self.nav_frame = saved

        # the wheel scrolls the menu wherever the pointer is on it
        def _bind_wheel(w):
            try:
                w.bind("<MouseWheel>", _wheel)
                w.bind("<Button-4>", _wheel)
                w.bind("<Button-5>", _wheel)
            except Exception:
                pass
            for c in w.winfo_children():
                _bind_wheel(c)
        _bind_wheel(nav_canvas)
        self._bind_nav_wheel = _bind_wheel

    # ── ⭐ Favourites (v6.9.3) ────────────────────────────────
    # A block at the top of the menu, one click each. Items are menu pages
    # (sales, ledger …) or direct actions (a new Cash Payment voucher …).
    # Right-click any menu item ▸ Add to Favourites; right-click a favourite
    # ▸ Remove / Move up / Move down / Reset. Saved per user on this PC.
    FAV_ACTIONS = {
        "cash_payment": ("💸", "Cash Payment (CP)", ("payment", "add")),
        "cash_receipt": ("💰", "Cash Receipt (CR)", ("receipt", "add")),
        "bank_payment": ("🏦", "Bank Payment (BP)", ("payment", "add")),
        "bank_receipt": ("🏦", "Bank Receipt (BR)", ("receipt", "add")),
        "journal_new": ("🧾", "Journal Voucher (JV)", ("journal", "add")),
        "contra_new": ("⇄", "Contra Voucher (CT)", ("journal", "add")),
        "add_product": ("➕", "Add Product", ("products", "add")),
        "new_sale": ("🧾", "New Sales Invoice", ("sales", "add")),
        "new_purchase": ("🛒", "New Purchase", ("purchase", "add")),
        "new_consumption": ("🍞", "New Consumable Entry", ("consumption", "add")),
    }
    FAV_DEFAULT = ["cash_payment", "cash_receipt", "ledger", "inventory", "sales", "pos",
                   "add_product", "sales_return", "purchases", "purchase_return"]

    def _fav_setting(self):
        uid = (self.current_user or {}).get("user_id") or "0"
        return "nav_favorites_%s" % uid

    def _favourites(self):
        v = cfg.get(self._fav_setting())
        if isinstance(v, list):
            return [str(x) for x in v]
        return list(self.FAV_DEFAULT)

    def _fav_store(self, keys):
        cfg.set(self._fav_setting(), list(dict.fromkeys(keys)))
        try:
            cfg.save_settings()
        except Exception:
            pass
        self._rebuild_sidebar_soon()

    def _rebuild_sidebar_soon(self):
        def go():
            try:
                for w in self.sidebar.winfo_children():
                    w.destroy()
                self.nav_buttons = {}
                self._build_sidebar()
                if getattr(self, "current_module", None):
                    self._paint_nav(self.current_module, "active")
            except Exception:
                pass
        self.root.after(10, go)

    def _fav_info(self, key):
        """(icon, label) of a favourite, or None when it is unknown."""
        if key in self.FAV_ACTIONS:
            return self.FAV_ACTIONS[key][:2]
        for _g, items in self._nav_def():
            for k, icon, lk in items:
                if k == key:
                    return icon, (t(lk) if str(lk).startswith("nav.") else lk)
        return None

    def _fav_allowed(self, key):
        if key in self.FAV_ACTIONS:
            mod, act = self.FAV_ACTIONS[key][2]
            try:
                from modules import permissions as _pm
                return _pm.can(mod, act)
            except Exception:
                return False
        return self._can_see(key)

    def _build_favourites(self, parent):
        from ui.zoom import px
        C = cfg.theme()
        SB = C["sidebar_bg"]
        items = [k for k in self._favourites() if self._fav_info(k) and self._fav_allowed(k)]
        if not items:
            return
        rtl = is_rtl()
        hdr = tk.Frame(parent, bg=SB)
        hdr.pack(fill="x", pady=(px(3), 0), padx=px(10))
        tk.Label(hdr, text="⭐  FAVOURITES", font=("Segoe UI", 8, "bold"), bg=SB,
                 fg=C.get("warning", "#F5B700"), anchor="e" if rtl else "w").pack(
                     fill="x", padx=px(6), pady=px(4))
        hdr.bind("<Button-3>", lambda e: self._fav_menu(e, None))
        body = tk.Frame(parent, bg=SB)
        body.pack(fill="x")
        saved = self.nav_frame
        self.nav_frame = body
        for k in items:
            icon, label = self._fav_info(k)
            self._nav_button("fav:" + k, icon, label)
        self.nav_frame = saved
        tk.Frame(parent, bg=C.get("sidebar_hover", "#2A3352"), height=1).pack(
            fill="x", padx=px(14), pady=(px(4), px(2)))

    def _run_favourite(self, key):
        if not self._fav_allowed(key):
            from tkinter import messagebox
            messagebox.showinfo("Permission", "You don't have permission for this.")
            return
        if key not in self.FAV_ACTIONS:
            self._load_module(key)
            return
        parent = getattr(self, "content", None) or self.root
        try:
            if key in ("cash_payment", "cash_receipt", "bank_payment", "bank_receipt", "journal_new",
                       "contra_new"):
                from ui.vouchers import VoucherForm
                vt = {"cash_payment": ("payment", "cash"), "cash_receipt": ("receipt", "cash"),
                      "bank_payment": ("payment", "bank"), "bank_receipt": ("receipt", "bank"),
                      "journal_new": ("journal", "cash"), "contra_new": ("contra", "cash")}[key]
                VoucherForm(parent, on_saved=self._refresh_active, vtype=vt[0], mode=vt[1])
            elif key == "add_product":
                from ui.products import ProductForm
                ProductForm(parent, on_save=self._refresh_active)
            elif key in ("new_sale", "new_purchase", "new_consumption"):
                from ui import txn_connector as tc
                tc.new_txn(parent, {"new_sale": "sales", "new_purchase": "purchase",
                                    "new_consumption": "consumption"}[key], self._refresh_active)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Favourites", str(e)[:200])

    def _fav_menu(self, event, key):
        favs = self._favourites()
        real = key[4:] if key and key.startswith("fav:") else key
        m = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 10))
        if real and real in favs:
            i = favs.index(real)
            m.add_command(label="☆  Remove from Favourites",
                          command=lambda: self._fav_store([k for k in favs if k != real]))
            if i > 0:
                m.add_command(label="▲  Move up", command=lambda: self._fav_store(
                    favs[:i - 1] + [real, favs[i - 1]] + favs[i + 1:]))
            if i < len(favs) - 1:
                m.add_command(label="▼  Move down", command=lambda: self._fav_store(
                    favs[:i] + [favs[i + 1], real] + favs[i + 2:]))
        elif real and self._fav_info(real):
            m.add_command(label="⭐  Add to Favourites",
                          command=lambda: self._fav_store(favs + [real]))
        add = [k for k in self.FAV_ACTIONS if k not in favs]
        if add:
            sub = tk.Menu(m, tearoff=0, font=("Segoe UI", 10))
            for k in add:
                icon, label, _p = self.FAV_ACTIONS[k]
                sub.add_command(label="%s  %s" % (icon, label),
                                command=lambda k=k: self._fav_store(favs + [k]))
            m.add_cascade(label="⭐  Add a quick action", menu=sub)
        m.add_separator()
        m.add_command(label="↺  Reset Favourites", command=lambda: self._fav_store(self.FAV_DEFAULT))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ── folded sidebar: an icon rail (☰ in the top bar folds / opens it) ──
    GROUP_ICONS = {"Sales": "🧾", "Purchase": "🛒", "Inventory": "📦", "Accounts": "📒",
                   "HR & Payroll": "👔", "Reports & Compliance": "📊", "Administration": "⚙"}

    def _build_rail(self):
        from ui.zoom import px
        C = cfg.theme()
        sb = self.sidebar
        SB = C["sidebar_bg"]
        sb.configure(width=px(64))
        self._nav_groups, self._nav_key_group = {}, {}
        self._nav_index, self._nav_icons = [], {}
        self._rail_btns = {}
        s = px(36)
        logo = tk.Canvas(sb, width=s, height=s, bg=SB, highlightthickness=0, bd=0, cursor="hand2")
        logo.pack(pady=(px(14), px(10)))
        self._logo_mark(logo, s, C)
        logo.bind("<Button-1>", lambda e: self._toggle_sidebar())
        self._rail_tip(logo, "Open the menu")

        def item(icon, tip, cmd, key=None, danger=False):
            b = tk.Label(sb, text=icon, font=("Segoe UI Emoji", 14), bg=SB,
                         fg="#FCA5A5" if danger else C.get("sidebar_text", "#E6EBF5"),
                         cursor="hand2", pady=px(6))
            b.pack(fill="x", padx=px(8), pady=1)
            b.bind("<Button-1>", lambda e, w=b: cmd(w))
            b.bind("<Enter>", lambda e, w=b: w.config(bg=C["sidebar_hover"]) if w is not self._rail_on else None)
            b.bind("<Leave>", lambda e, w=b: w.config(bg=SB) if w is not self._rail_on else None)
            self._rail_tip(b, tip)
            if key:
                self._rail_btns[key] = b
            return b
        self._rail_on = None
        item("🔍", "Search the menu", lambda w: (self._toggle_sidebar(),
                                                 self.root.after(80, lambda: self._nav_entry.focus_set())))
        favs = [k for k in self._favourites() if self._fav_info(k) and self._fav_allowed(k)]
        if favs:
            item("⭐", "Favourites", lambda w: self._rail_favs(w, favs))
        for group, items in self._nav_def():
            visible = [it for it in items if self._can_see(it[0])]
            if not visible:
                continue
            for key, icon, label_key in visible:
                label = t(label_key) if str(label_key).startswith("nav.") else label_key
                self._nav_index.append((key, icon, label, group or "Home"))
                self._nav_icons[key] = icon
                if group:
                    self._nav_key_group[key] = group
            if not group:
                for key, icon, _l in visible:
                    item(icon, t(_l) if str(_l).startswith("nav.") else _l,
                         lambda w, k=key: self._load_module(k), key=key)
                continue
            item(self.GROUP_ICONS.get(group, "•"), group,
                 lambda w, g=group, its=visible: self._rail_menu(w, g, its), key="grp:" + group)
        bottom = tk.Frame(sb, bg=SB)
        bottom.pack(side="bottom", fill="x", pady=(0, px(10)))
        b = tk.Label(bottom, text="⏻", font=("Segoe UI Emoji", 13), bg=SB, fg="#FCA5A5",
                     cursor="hand2", pady=px(6))
        b.pack(fill="x", padx=px(8))
        b.bind("<Button-1>", lambda e: self._logout())
        self._rail_tip(b, t("nav.logout"))
        self._rail_paint()

    def _rail_favs(self, w, favs):
        m = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 10))
        m.add_command(label="⭐ FAVOURITES", state="disabled")
        m.add_separator()
        for k in favs:
            icon, label = self._fav_info(k)
            m.add_command(label="%s  %s" % (icon, label), command=lambda k=k: self._run_favourite(k))
        try:
            m.tk_popup(w.winfo_rootx() + w.winfo_width(), w.winfo_rooty())
        finally:
            m.grab_release()

    def _rail_menu(self, w, group, items):
        m = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 10))
        m.add_command(label=group.upper(), state="disabled")
        m.add_separator()
        for key, icon, label_key in items:
            label = t(label_key) if str(label_key).startswith("nav.") else label_key
            m.add_command(label="%s   %s" % (icon, label),
                          command=lambda k=key: self._load_module(k))
        try:
            if is_rtl():
                m.tk_popup(w.winfo_rootx() - 220, w.winfo_rooty())
            else:
                m.tk_popup(w.winfo_rootx() + w.winfo_width() + 2, w.winfo_rooty())
        finally:
            try:
                m.grab_release()
            except Exception:
                pass

    def _rail_paint(self):
        btns = getattr(self, "_rail_btns", None)
        if not btns:
            return
        C = cfg.theme()
        key = self.current_module
        grp = getattr(self, "_nav_key_group", {}).get(key)
        on = btns.get(key) or (btns.get("grp:" + grp) if grp else None)
        for b in btns.values():
            try:
                b.config(bg=C["sidebar_bg"])
            except Exception:
                pass
        self._rail_on = on
        if on is not None:
            try:
                on.config(bg=C.get("sidebar_active", C["primary"]))
            except Exception:
                pass

    def _below_tip(self, w, text):
        """A small tip under a top-bar button while the mouse is on it."""
        tip = {}

        def show(e=None):
            try:
                t_ = tk.Toplevel(w); t_.overrideredirect(True)
                t_.attributes("-topmost", True)
                tk.Label(t_, text=text, font=("Segoe UI", 9), bg="#111827", fg="white",
                         padx=8, pady=3).pack()
                t_.update_idletasks()
                x = w.winfo_rootx() + w.winfo_width() // 2 - t_.winfo_reqwidth() // 2
                x = max(0, min(x, w.winfo_screenwidth() - t_.winfo_reqwidth() - 4))
                t_.geometry("+%d+%d" % (x, w.winfo_rooty() + w.winfo_height() + 4))
                tip["w"] = t_
            except Exception:
                pass

        def hide(e=None):
            try:
                tip.pop("w").destroy()
            except Exception:
                pass
        w.bind("<Enter>", show, add="+")
        w.bind("<Leave>", hide, add="+")
        w.bind("<Button-1>", hide, add="+")

    def _rail_tip(self, w, text):
        tip = {}

        def show(e=None):
            try:
                t_ = tk.Toplevel(w); t_.overrideredirect(True)
                t_.attributes("-topmost", True)
                tk.Label(t_, text=text, font=("Segoe UI", 9), bg="#111827", fg="white",
                         padx=8, pady=3).pack()
                x = w.winfo_rootx() + (-t_.winfo_reqwidth() - 6 if is_rtl() else w.winfo_width() + 6)
                t_.geometry("+%d+%d" % (x, w.winfo_rooty() + 4))
                tip["w"] = t_
            except Exception:
                pass

        def hide(e=None):
            try:
                tip.pop("w").destroy()
            except Exception:
                pass
        w.bind("<Enter>", show, add="+")
        w.bind("<Leave>", hide, add="+")
        w.bind("<Button-1>", hide, add="+")

    def _toggle_sidebar(self):
        """☰ — fold the sidebar to icons / open it again (remembered)."""
        from ui.zoom import px
        cfg.set("sidebar_collapsed", not cfg.flag("sidebar_collapsed", False))
        try:
            cfg.save_settings()
        except Exception:
            pass
        for w in self.sidebar.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self.nav_buttons = {}
        if not cfg.flag("sidebar_collapsed", False):
            self.sidebar.configure(width=px(236))
        self._build_sidebar()
        try:
            if self.current_module:
                self._paint_nav(self.current_module, "active")
                self._nav_reveal(self.current_module)
        except Exception:
            pass


    def _on_window_focus(self, key):
        """A window came to the front (taskbar click): highlight its page."""
        if not key or key == self.current_module:
            return
        old = self.current_module
        self.current_module = key
        try:
            if old:
                self._paint_nav(old, "normal")
            self._paint_nav(key, "active")
            self._rail_paint()
        except Exception:
            pass

    def _logo_mark(self, cv, s, C):
        """DayBill mark: blue rounded square, white D, green dot (any size)."""
        r = max(4, int(s * 0.24))
        self._round_rect(cv, 1, 1, s - 1, s - 1, r, fill=C["primary"], outline="")
        cv.create_text(s * 0.47, s * 0.5, text="D", fill="white",
                       font=("Segoe UI", -int(s * 0.52), "bold"))
        d = max(4, int(s * 0.19))
        cv.create_oval(s * 0.68, s * 0.64, s * 0.68 + d, s * 0.64 + d,
                       fill=C.get("accent", "#22C55E"), outline="")

    # ── Sidebar menu search ───────────────────────────────────
    def _build_nav_search(self, parent, C):
        from ui.zoom import px
        rtl = is_rtl()
        near = "right" if rtl else "left"
        FIELD = C.get("sidebar_field", "#1A2B50")
        box = tk.Frame(parent, bg=FIELD, highlightthickness=1,
                       highlightbackground=C.get("sidebar_hover", "#1B2C52"),
                       highlightcolor=C["primary"])
        box.pack(fill="x", padx=px(12), pady=(0, px(10)))
        tk.Label(box, text="🔍", bg=FIELD, fg=C.get("sidebar_muted", "#9AA3C7"),
                 font=("Segoe UI Emoji", 9)).pack(side=near, padx=(px(9), px(3)))
        self._nav_q = tk.StringVar()
        ent = tk.Entry(box, textvariable=self._nav_q, relief="flat", bd=0,
                       highlightthickness=0, bg=FIELD, fg="white",
                       insertbackground="white", font=("Segoe UI", 10),
                       justify="right" if rtl else "left")
        ent.pack(side=near, fill="x", expand=True, ipady=px(6))
        clr = tk.Label(box, text="✕", bg=FIELD, fg=C.get("sidebar_muted", "#9AA3C7"),
                       font=("Segoe UI", 9), cursor="hand2", padx=px(8))
        self._nav_entry, self._nav_clear_btn, self._nav_box = ent, clr, box
        self._nav_hint = "ابحث في القائمة…" if rtl else "Search menu…"
        self._nav_sel = 0
        self._nav_hits = []
        self._nav_placeholder(True)
        ent.bind("<FocusIn>", lambda e: self._nav_placeholder(False))
        ent.bind("<FocusOut>", lambda e: self._nav_placeholder(True))
        # typing while the grey hint is still there (focus never left): hint goes first
        ent.bind("<KeyPress>", lambda e: self._nav_placeholder(False)
                 if getattr(self, "_nav_ph", False) and len(e.char or "") == 1 else None)
        ent.bind("<Button-1>", lambda e: self._nav_placeholder(False), add="+")
        ent.bind("<KeyRelease>", self._nav_filter)
        ent.bind("<Return>", lambda e: (self._nav_open_hit(), "break")[1])
        ent.bind("<KP_Enter>", lambda e: (self._nav_open_hit(), "break")[1])
        ent.bind("<Down>", lambda e: (self._nav_move(1), "break")[1])
        ent.bind("<Up>", lambda e: (self._nav_move(-1), "break")[1])
        ent.bind("<Escape>", lambda e: (self._nav_search_clear(), "break")[1])
        clr.bind("<Button-1>", lambda e: self._nav_search_clear())
        box.bind("<Button-1>", lambda e: ent.focus_set())

    def _nav_placeholder(self, show):
        ent = getattr(self, "_nav_entry", None)
        if ent is None:
            return
        C = cfg.theme()
        if show and not self._nav_q.get():
            self._nav_ph = True
            ent.insert(0, self._nav_hint)
            ent.config(fg=C.get("sidebar_muted", "#9AA3C7"))
        elif not show and getattr(self, "_nav_ph", False):
            self._nav_ph = False
            ent.delete(0, "end")
            ent.config(fg="white")

    def _nav_query(self):
        if getattr(self, "_nav_ph", False):
            return ""
        return (self._nav_q.get() or "").strip()

    def _nav_filter(self, e=None):
        if e is not None and getattr(e, "keysym", "") in (
                "Return", "KP_Enter", "Up", "Down", "Escape", "Tab"):
            return
        q = self._nav_query().lower()
        if not q:
            self._nav_show_tree()
            return
        from ui.page_info import KEYWORDS
        words = q.split()
        hits = []
        for key, icon, label, group in getattr(self, "_nav_index", []):
            hay = ("%s %s %s %s" % (label, group, key.replace("_", " "),
                                    KEYWORDS.get(key, ""))).lower()
            if all(w in hay for w in words):
                # the page whose name — or first search word — starts with the
                # text comes first ("stock" → Inventory, then Stock Transfers)
                starts = label.lower().startswith(q) or \
                    KEYWORDS.get(key, "").lower().startswith(q)
                hits.append((0 if starts else 1, key, icon, label, group))
        hits.sort(key=lambda h: (h[0], h[3].lower()))
        self._nav_hits = [h[1:] for h in hits]
        self._nav_sel = 0
        self._nav_paint_results()

    def _nav_show_tree(self):
        self._nav_hits = []
        try:
            self._nav_res.pack_forget()
            for w in self._nav_res.winfo_children():
                w.destroy()
            if not self._nav_tree.winfo_manager():
                self._nav_tree.pack(fill="x")
            self._nav_clear_btn.pack_forget()
            self._nav_canvas.yview_moveto(0)
        except Exception:
            pass

    def _nav_paint_results(self):
        from ui.zoom import px
        C = cfg.theme()
        SB = C["sidebar_bg"]
        rtl = is_rtl()
        near = "right" if rtl else "left"
        res = self._nav_res
        for w in res.winfo_children():
            w.destroy()
        self._nav_tree.pack_forget()
        if not res.winfo_manager():
            res.pack(fill="x")
        if not self._nav_clear_btn.winfo_manager():
            self._nav_clear_btn.pack(side="left" if rtl else "right")
        muted = C.get("sidebar_muted", "#9AA3C7")
        tk.Label(res, text=("%d found" % len(self._nav_hits)) if self._nav_hits
                 else "Nothing found — try another word",
                 font=("Segoe UI", 8, "bold"), bg=SB, fg=muted,
                 anchor="e" if rtl else "w").pack(fill="x", padx=px(16), pady=(px(2), px(4)))
        for i, (key, icon, label, group) in enumerate(self._nav_hits[:40]):
            sel = i == self._nav_sel
            bg = C.get("sidebar_active", C["primary"]) if sel else SB
            row = tk.Frame(res, bg=bg, cursor="hand2")
            row.pack(fill="x", padx=px(10), pady=1)
            a = tk.Label(row, text=icon, font=("Segoe UI Emoji", 11), bg=bg, fg="white",
                         width=2, cursor="hand2")
            a.pack(side=near, padx=(px(6), px(4)), pady=px(5))
            box = tk.Frame(row, bg=bg, cursor="hand2")
            box.pack(side=near, fill="x", expand=True)
            b = tk.Label(box, text=label, font=("Segoe UI", 10, "bold" if sel else "normal"),
                         bg=bg, fg="white", anchor="e" if rtl else "w", cursor="hand2")
            b.pack(fill="x")
            c = tk.Label(box, text=group, font=("Segoe UI", 7), bg=bg,
                         fg="#DCE6FF" if sel else muted, anchor="e" if rtl else "w",
                         cursor="hand2")
            c.pack(fill="x")
            for w in (row, a, box, b, c):
                w.bind("<Button-1>", lambda e, k=key: self._nav_open_hit(k))
                if not sel:
                    w.bind("<Enter>", lambda e, r=row: self._nav_hover(r, True))
                    w.bind("<Leave>", lambda e, r=row: self._nav_hover(r, False))
        try:
            self._bind_nav_wheel(res)
            self._nav_canvas.yview_moveto(0)
        except Exception:
            pass

    def _nav_hover(self, row, on):
        C = cfg.theme()
        bg = C["sidebar_hover"] if on else C["sidebar_bg"]
        stack = [row]
        while stack:
            w = stack.pop()
            try:
                w.config(bg=bg)
            except Exception:
                pass
            stack.extend(w.winfo_children())

    def _nav_move(self, d):
        if not self._nav_hits:
            return
        self._nav_sel = max(0, min(len(self._nav_hits) - 1, self._nav_sel + d))
        self._nav_paint_results()

    def _nav_open_hit(self, key=None):
        if key is None:
            if not self._nav_hits:
                return
            key = self._nav_hits[min(self._nav_sel, len(self._nav_hits) - 1)][0]
        self._nav_search_clear(keep_focus=False)
        self._load_module(key)

    def _nav_search_clear(self, keep_focus=True):
        try:
            self._nav_ph = False
            self._nav_q.set("")
            self._nav_show_tree()
            if keep_focus:
                self._nav_entry.focus_set()
            else:
                self.root.focus_set()
                if self.root.focus_get() is not self._nav_entry:
                    self._nav_placeholder(True)
        except Exception:
            pass

    @staticmethod
    def _round_rect(cv, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    def _nav_group_header(self, name):
        """A clickable heading (▸ SALES). Its pages are folded under it."""
        from ui.zoom import px
        C = cfg.theme()
        SB = C["sidebar_bg"]
        rtl = is_rtl()
        f = tk.Frame(self.nav_frame, bg=SB, cursor="hand2")
        f.pack(fill="x", pady=(px(3), 0), padx=px(10))
        arrow = tk.Label(f, text="◂" if rtl else "▸", font=("Segoe UI", 9, "bold"), bg=SB,
                         fg=C.get("sidebar_muted", "#9AA3C7"), width=2, cursor="hand2")
        arrow.pack(side="right" if rtl else "left", padx=(px(6), 0), pady=px(6))
        lbl = tk.Label(f, text=name.upper(), font=("Segoe UI", 8, "bold"), bg=SB,
                       fg=C.get("sidebar_muted", "#9AA3C7"),
                       anchor="e" if rtl else "w", cursor="hand2")
        lbl.pack(side="right" if rtl else "left", fill="x", expand=True, pady=px(6))
        hover = C.get("sidebar_hover", "#2A3352")

        def enter(e=None):
            for w in (f, arrow, lbl):
                w.config(bg=hover)

        def leave(e=None):
            for w in (f, arrow, lbl):
                w.config(bg=SB)
        for w in (f, arrow, lbl):
            w.bind("<Button-1>", lambda e, n=name: self._nav_toggle(n))
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
        return f, arrow

    def _nav_toggle(self, name, remember=True, force_open=False):
        """Open one heading (closing the one that was open); click the open
        heading again to fold it."""
        g = getattr(self, "_nav_groups", {}).get(name)
        if not g:
            return
        rtl = is_rtl()
        opening = force_open or self._nav_open != name
        if self._nav_open and self._nav_open in self._nav_groups and \
                (self._nav_open != name or not opening):
            old = self._nav_groups[self._nav_open]
            old["body"].pack_forget()
            old["arrow"].config(text="◂" if rtl else "▸")
            self._nav_open = None
        if opening:
            g["body"].pack(fill="x", after=g["header"])
            g["arrow"].config(text="▾")
            self._nav_open = name
        if remember:
            try:
                cfg.set("nav_open_group", self._nav_open or "")
                cfg.save_settings()
            except Exception:
                pass
        try:
            self.nav_frame.update_idletasks()
            self._nav_canvas.configure(scrollregion=self._nav_canvas.bbox("all"))
        except Exception:
            pass

    def _nav_reveal(self, key):
        """The page being opened shows in the menu: open its heading."""
        grp = getattr(self, "_nav_key_group", {}).get(key)
        if (grp and grp in getattr(self, "_nav_groups", {})
                and getattr(self, "_nav_open", None) != grp):
            self._nav_toggle(grp, remember=False, force_open=True)

    def _nav_colors(self, mode, is_logout=False):
        C = cfg.theme()
        if mode == "active":
            return C.get("sidebar_active", C["primary"]), "white"
        if mode == "hover":
            return C["sidebar_hover"], "white"
        return C["sidebar_bg"], ("#FCA5A5" if is_logout else C.get("sidebar_text", "#E6EBF5"))

    def _paint_nav(self, key, mode):
        d = self.nav_buttons.get(key)
        if not d:
            return
        bg, fg = self._nav_colors(mode, d.get("logout", False))
        try:
            for w in (d["content"], d["icon"], d["text"]):
                w.config(bg=bg)
            d["icon"].config(fg=fg)
            d["text"].config(fg=fg, font=("Segoe UI", 10, "bold" if mode == "active" else "normal"))
            d["indicator"].config(bg=bg)
        except Exception:
            pass

    def _nav_button(self, key, icon, label, is_logout=False):
        C = cfg.theme()
        SB = C["sidebar_bg"]
        rtl = is_rtl()
        bg, fg = self._nav_colors("normal", is_logout)

        from ui.zoom import px
        btn = tk.Frame(self.nav_frame, bg=SB, cursor="hand2")
        btn.pack(fill="x", padx=px(10), pady=1)

        # the rounded-look "pill" that turns blue when active
        content_frame = tk.Frame(btn, bg=bg, cursor="hand2")
        content_frame.pack(fill="x")
        indicator = tk.Frame(content_frame, bg=bg, width=4)
        indicator.pack(side="right" if rtl else "left", fill="y")

        icon_lbl = tk.Label(content_frame, text=icon, font=("Segoe UI Emoji", 11),
                            bg=bg, fg=fg, width=2, cursor="hand2")
        icon_lbl.pack(side="right" if rtl else "left", padx=(px(4), px(6)), pady=px(6))

        text_lbl = tk.Label(content_frame, text=label, font=("Segoe UI", 10),
                            bg=bg, fg=fg, anchor="e" if rtl else "w", cursor="hand2")
        text_lbl.pack(side="right" if rtl else "left", fill="x", expand=True, pady=px(6))

        def on_hover(e=None):
            if key != self.current_module:
                self._paint_nav(key, "hover")

        def on_leave(e=None):
            if key != self.current_module:
                self._paint_nav(key, "normal")

        def on_click(e=None, k=key):
            if k == "logout":
                self._logout()
            elif k.startswith("fav:"):
                self._run_favourite(k[4:])
            else:
                self._load_module(k)

        for widget in [btn, content_frame, indicator, icon_lbl, text_lbl]:
            widget.bind("<Enter>", on_hover)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)
            if not is_logout:              # ⭐ add to / remove from Favourites
                widget.bind("<Button-3>", lambda e, k=key: self._fav_menu(e, k))

        self.nav_buttons[key] = {
            "frame": btn, "indicator": indicator,
            "icon": icon_lbl, "text": text_lbl,
            "content": content_frame, "logout": is_logout,
        }

    # ── Topbar ────────────────────────────────────────────────
    def _build_topbar(self):
        C = cfg.theme()
        tb = self.topbar
        TB = C["topbar_bg"]
        rtl = is_rtl()
        near, far = ("right", "left") if rtl else ("left", "right")
        from ui.zoom import px
        try:
            wide = self.root.winfo_screenwidth() >= 1500
        except Exception:
            wide = True

        # page title kept for code that reads it (shown in the window bar)
        self.page_title_var = tk.StringVar(value=t("nav.dashboard"))

        # ☰ fold / open the sidebar
        burger = tk.Label(tb, text="☰", font=("Segoe UI Symbol", 15), bg=TB,
                          fg=C["text_primary"], cursor="hand2", padx=px(10))
        burger.pack(side=near, padx=(px(8), 0), fill="y")
        burger.bind("<Button-1>", lambda e: self._toggle_sidebar())
        burger.bind("<Enter>", lambda e: burger.config(bg=C["content_bg"]))
        burger.bind("<Leave>", lambda e: burger.config(bg=TB))
        self._burger = burger

        # ── Search anything… (Ctrl+K) ──
        box = tk.Frame(tb, bg=C["content_bg"], highlightthickness=1,
                       highlightbackground=C["border"], highlightcolor=C["primary"])
        box.pack(side=near, padx=(px(6), px(18)), pady=px(6))
        tk.Label(box, text="🔍", bg=C["content_bg"], fg=C["text_secondary"],
                 font=("Segoe UI Emoji", 10)).pack(side=near, padx=(px(10), px(4)))
        self._search_var = tk.StringVar()
        ent = tk.Entry(box, textvariable=self._search_var, width=34 if wide else 24,
                       relief="flat", bd=0,
                       highlightthickness=0, bg=C["content_bg"], fg=C["text_primary"],
                       font=("Segoe UI", 10), insertbackground=C["primary"])
        ent.pack(side=near, ipady=px(5))
        chip = tk.Label(box, text="Ctrl+K", bg=C["card_bg"], fg=C["text_secondary"],
                        font=("Segoe UI", 8), padx=px(6), highlightthickness=1,
                        highlightbackground=C["border"])
        chip.pack(side=near, padx=(px(4), px(8)), pady=px(5))
        self._search_entry = ent
        self._search_box = box
        self._search_hint = "Search anything…"
        self._search_placeholder(True)
        ent.bind("<FocusIn>", lambda e: (self._search_placeholder(False),
                                         box.config(highlightbackground=C["primary"])))
        ent.bind("<FocusOut>", lambda e: (self._search_placeholder(True),
                                          box.config(highlightbackground=C["border"]),
                                          self.root.after(180, self._search_hide)))
        ent.bind("<KeyRelease>", self._search_key)
        ent.bind("<Return>", lambda e: (self._search_open(), "break")[1])
        ent.bind("<KP_Enter>", lambda e: (self._search_open(), "break")[1])
        ent.bind("<Down>", lambda e: (self._search_move(1), "break")[1])
        ent.bind("<Up>", lambda e: (self._search_move(-1), "break")[1])
        ent.bind("<Escape>", lambda e: (self._search_clear(), "break")[1])
        for w in (box, chip):
            w.bind("<Button-1>", lambda e: ent.focus_set())
        self._search_pop = None
        self._search_hits = []
        try:
            self.root.bind_all("<Control-k>", self._search_focus, add="+")
            self.root.bind_all("<Control-K>", self._search_focus, add="+")
        except Exception:
            pass

        # ── this PC's branch · counter (click → Branches & Counters) ──
        self._counter_chip = tk.Label(tb, text="", bg=C["content_bg"], fg=C["text_primary"],
                                      font=("Segoe UI", 9, "bold"), padx=10, pady=5,
                                      cursor="hand2", highlightthickness=1,
                                      highlightbackground=C["border"])
        self._counter_chip.pack(side=near, padx=(0, 8))
        self._counter_chip.bind("<Button-1>", lambda e: self._counter_chip_click())
        self._refresh_counter_chip()

        # ── licence: trial days left / read-only (click → Product Key) ──
        self._lic_chip = tk.Label(tb, text="", bg=C["warning"], fg="white",
                                  font=("Segoe UI", 9, "bold"), padx=10, pady=5,
                                  cursor="hand2")
        self._lic_chip.pack(side=near, padx=(0, 8))
        self._lic_chip.bind("<Button-1>", lambda e: self._open_license())
        self._refresh_license_chip()

        # ── right side: user · alerts · language · POS ──
        right = tk.Frame(tb, bg=TB)
        # packed first: the buttons on the right always keep their room; the
        # search box and the chips get what is left on small screens
        right.pack(side=far, padx=(0, px(14)) if not rtl else (px(14), 0), before=box)

        u = self.current_user or {}
        uname = (u.get("full_name_en") or u.get("username") or "User").strip()
        if str(u.get("username", "")).lower() == "admin" and uname.lower() == "admin":
            uname = "Admin"
        try:
            from modules import permissions as _perm
            role = _perm._session.get("role_name") or ""
        except Exception:
            role = ""
        if str(u.get("username", "")).lower() == "admin":
            role = "Administrator"
        initials = "".join(p[0] for p in uname.split()[:2]).upper() or "U"

        user = tk.Frame(right, bg=TB, cursor="hand2")
        user.pack(side=far, padx=(6, 0))
        a_s = px(28)
        av = tk.Canvas(user, width=a_s, height=a_s, bg=TB, highlightthickness=0, bd=0,
                       cursor="hand2")
        av.pack(side=near)
        av.create_oval(1, 1, a_s - 1, a_s - 1, fill=C["primary_light"], outline=C["primary"])
        av.create_text(a_s / 2, a_s / 2, text=initials[:2], fill=C["primary"],
                       font=("Segoe UI", -int(a_s * 0.36), "bold"))
        who = tk.Frame(user, bg=TB, cursor="hand2")
        who.pack(side=near, padx=(8, 4))
        l1 = tk.Label(who, text=uname[:22], bg=TB, fg=C["text_primary"],
                      font=("Segoe UI", 9, "bold"), anchor="w", cursor="hand2")
        l1.pack(fill="x")
        l2 = tk.Label(who, text=role or "User", bg=TB, fg=C["text_secondary"],
                      font=("Segoe UI", 8), anchor="w", cursor="hand2")
        l2.pack(fill="x")
        caret = tk.Label(user, text="▾", bg=TB, fg=C["text_secondary"],
                         font=("Segoe UI", 9), cursor="hand2")
        caret.pack(side=near)
        for w in (user, av, who, l1, l2, caret):
            w.bind("<Button-1>", lambda e, a=user: self._user_menu(a))

        tk.Frame(right, bg=C["border"], width=1, height=px(30)).pack(side=far, padx=px(10))

        # alerts bell with a count badge
        bw, bh = px(32), px(30)
        bell = tk.Canvas(right, width=bw, height=bh, bg=TB, highlightthickness=0,
                         bd=0, cursor="hand2")
        bell.pack(side=far, padx=2)
        bell.create_text(bw / 2 - 1, bh / 2 + 1, text="🔔", font=("Segoe UI Emoji", -int(bh * 0.5)),
                         fill=C["text_secondary"])
        self._bell = bell
        bell.bind("<Button-1>", lambda e: self._show_alerts())
        bell.bind("<Enter>", lambda e: bell.config(bg=C["content_bg"]))
        bell.bind("<Leave>", lambda e: bell.config(bg=TB))
        try:
            self.root.after(1500, self._refresh_bell)
        except Exception:
            pass

        # Text size (Aa ▾): bigger / smaller letters for the whole app
        aa = tk.Label(right, text="Aa ▾", font=("Segoe UI", 10, "bold"), bg=TB,
                      fg=C["text_primary"], padx=px(9), pady=px(4), cursor="hand2",
                      highlightthickness=1, highlightbackground=C["border"])
        aa.pack(side=far, padx=px(4))
        aa.bind("<Button-1>", lambda e, a=aa: self._text_size_menu(a))
        aa.bind("<Enter>", lambda e: aa.config(bg=C["content_bg"]))
        aa.bind("<Leave>", lambda e: aa.config(bg=TB))
        self._aa_btn = aa

        # 🎨 Theme: pick the colours of the whole app (changes at once)
        th = tk.Label(right, text="🎨 ▾", font=("Segoe UI", 10, "bold"), bg=TB,
                      fg=C["text_primary"], padx=px(8), pady=px(4), cursor="hand2",
                      highlightthickness=1, highlightbackground=C["border"])
        th.pack(side=far, padx=px(4))
        th.bind("<Button-1>", lambda e, a=th: self._theme_picker(a))
        th.bind("<Enter>", lambda e: th.config(bg=C["content_bg"]))
        th.bind("<Leave>", lambda e: th.config(bg=TB))
        self._theme_btn = th
        self._below_tip(th, "Theme — colours of the whole app")

        # Language toggle
        lang_text = "🌐 العربية" if current_lang() == "en" else "🌐 English"
        tk.Button(right, text=lang_text, font=("Segoe UI", 9), bg=TB,
                  fg=C["text_primary"], relief="flat", bd=0, padx=px(10), pady=px(5),
                  cursor="hand2", activebackground=C["content_bg"],
                  highlightthickness=1, highlightbackground=C["border"],
                  command=self._toggle_language).pack(side=far, padx=6)

        # POS launch button (only for users allowed to use POS)
        if self._can_see("pos"):
            tk.Button(right, text="🛍  POS", font=("Segoe UI", 9, "bold"),
                      bg=C["primary"], fg="white", relief="flat", bd=0,
                      padx=px(14), pady=px(5), cursor="hand2",
                      activebackground=C["primary_dark"], activeforeground="white",
                      command=self._open_pos).pack(side=far, padx=px(6))

        # date + time (like a till): wide screens only
        if wide:
            self._clock_var = tk.StringVar()
            ck = tk.Label(right, textvariable=self._clock_var, font=("Segoe UI", 10),
                          bg=TB, fg=C["text_primary"], padx=px(6))
            ck.pack(side=far, padx=(px(4), px(8)))
            self._clock_lbl = ck
            self._clock_tick()

    def _clock_tick(self):
        lbl = getattr(self, "_clock_lbl", None)
        try:
            if lbl is None or not lbl.winfo_exists():
                return
            from datetime import datetime as _dt
            self._clock_var.set("📅  " + _dt.now().strftime("%d/%m/%Y   %H:%M"))
            lbl.after(15000, self._clock_tick)
        except Exception:
            pass

    def _text_size_menu(self, anchor):
        """Aa ▾ → Normal / Large / Larger … (the whole app, right away)."""
        from ui import zoom
        cur = zoom.percent()
        m = tk.Menu(self.root, tearoff=0)
        names = {100: "Normal (old size)", 112: "Medium", 125: "Large (default)",
                 140: "Larger", 160: "Extra large"}
        m.add_command(label="Text size — whole app", state="disabled")
        m.add_separator()
        for c in zoom.CHOICES:
            p = int(c.rstrip("%"))
            m.add_command(label=("●  " if p == cur else "     ") + "%s   %s" % (c, names.get(p, "")),
                          command=lambda p=p: self._set_text_size(p))
        try:
            m.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 4)
        finally:
            try:
                m.grab_release()
            except Exception:
                pass

    def _theme_picker(self, anchor):
        """🎨 Theme → pictures of every theme; a click changes the whole app."""
        try:
            from ui.theme_picker import ThemePicker
            self._theme_win = ThemePicker(anchor, on_apply=self.apply_live)
        except Exception as e:
            messagebox.showerror("Theme", str(e)[:200])

    def _set_text_size(self, p):
        cfg.set("ui_text_size", "%d%%" % int(p))
        try:
            cfg.save_settings()
        except Exception:
            pass
        self.apply_live()

    def _refresh_counter_chip(self):
        chip = getattr(self, "_counter_chip", None)
        if chip is None:
            return
        try:
            from modules import branches as _br
            bn, cn = _br.labels()
        except Exception:
            bn, cn = "", ""
        if cn or bn:
            try:
                n = 30 if self.root.winfo_screenwidth() >= 1500 else 14
            except Exception:
                n = 30
            cut = lambda v: v if len(v) <= n else v[:n - 1] + "…"
            chip.config(text=f"🏬 {cut(bn or '—')}  ·  🖥 {cut(cn or 'no counter')}")
            chip.pack_configure()
        else:
            chip.config(text="")
            try:
                chip.pack_forget()
            except Exception:
                pass

    def _refresh_license_chip(self):
        chip = getattr(self, "_lic_chip", None)
        if chip is None:
            return
        try:
            from modules import license as _lic
            txt, ok = _lic.banner_text(), _lic.write_ok()
        except Exception:
            txt, ok = "", True
        C = cfg.theme()
        if txt:
            chip.config(text=("⏳ " if ok else "⛔ ") + txt,
                        bg=C["warning"] if ok else C["danger"])
            chip.pack_configure()
        else:
            chip.config(text="")
            try:
                chip.pack_forget()
            except Exception:
                pass

    def _open_license(self):
        try:
            from ui.license_dialog import LicenseDialog
            LicenseDialog(self.root, on_change=self._refresh_license_chip)
        except Exception as e:
            messagebox.showerror("Product key", str(e)[:300])

    def _counter_chip_click(self):
        if self._can_see("branches"):
            self._menu_open("branches")
        else:
            try:
                from ui.branches import choose_counter
                choose_counter(self.root, force=True)
            except Exception:
                pass

    # ── top bar helpers: search, alerts, user menu ──
    def _search_placeholder(self, show):
        C = cfg.theme()
        e = getattr(self, "_search_entry", None)
        if e is None:
            return
        try:
            if show and not self._search_var.get().strip():
                e._ph = True
                e.config(fg=C["text_secondary"])
                self._search_var.set(self._search_hint)
            elif not show and getattr(e, "_ph", False):
                e._ph = False
                self._search_var.set("")
                e.config(fg=C["text_primary"])
        except Exception:
            pass

    def _search_focus(self, e=None):
        try:
            w = e.widget if e is not None else None
            if isinstance(w, tk.Misc) and w.winfo_toplevel() is not self.root:
                return None             # POS / dialogs keep their own keys
            self._search_entry.focus_set()
            self._search_entry.select_range(0, "end")
        except Exception:
            pass
        return "break"

    def _search_items(self):
        items = [(label, icon, group, ("mod", key))
                 for key, icon, label, group in getattr(self, "_nav_index", [])]
        if self._can_see("report_center"):
            try:
                from modules import report_center as _RC
                for r in _RC.catalog():
                    items.append((r["title"], "📊", "Report · " + str(r.get("group", "")),
                                  ("rc", r["id"])))
            except Exception:
                pass
        return items

    def _search_key(self, e=None):
        if e is not None and e.keysym in ("Return", "KP_Enter", "Up", "Down", "Escape"):
            return
        q = self._search_var.get().strip().lower()
        if not q or getattr(self._search_entry, "_ph", False):
            self._search_hide()
            return
        words = q.split()
        hits = []
        for label, icon, group, target in self._search_items():
            hay = (label + " " + group).lower()
            if all(w in hay for w in words):
                score = (0 if label.lower().startswith(q) else
                         1 if q in label.lower() else 2)
                hits.append((score, label, icon, group, target))
        # screens before reports, then the closest (shortest) name
        hits.sort(key=lambda h: (h[0], h[4][0] != "mod", len(h[1]), h[1]))
        self._search_hits = hits[:9]
        self._search_show()

    def _search_show(self):
        C = cfg.theme()
        self._search_hide()
        if not self._search_hits:
            return
        box = self._search_box
        pop = tk.Toplevel(self.root)
        pop.overrideredirect(True)
        try:
            pop.attributes("-topmost", True)
        except Exception:
            pass
        pop.configure(bg=C["border"])
        inner = tk.Frame(pop, bg=C["card_bg"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self._search_rows = []
        for i, (_s, label, icon, group, target) in enumerate(self._search_hits):
            row = tk.Frame(inner, bg=C["card_bg"], cursor="hand2")
            row.pack(fill="x")
            a = tk.Label(row, text=icon, bg=C["card_bg"], fg=C["primary"],
                         font=("Segoe UI Emoji", 10), width=3)
            a.pack(side="left", pady=4)
            b = tk.Label(row, text=label, bg=C["card_bg"], fg=C["text_primary"],
                         font=("Segoe UI", 10), anchor="w")
            b.pack(side="left", fill="x", expand=True)
            c = tk.Label(row, text=group, bg=C["card_bg"], fg=C["text_secondary"],
                         font=("Segoe UI", 8))
            c.pack(side="right", padx=10)
            for w in (row, a, b, c):
                w.bind("<Button-1>", lambda e, i=i: self._search_open(i))
                w.bind("<Enter>", lambda e, i=i: self._search_select(i))
            self._search_rows.append((row, a, b, c))
        self._search_pop = pop
        pop.update_idletasks()
        x = box.winfo_rootx()
        y = box.winfo_rooty() + box.winfo_height() + 2
        w = max(box.winfo_width(), 420)
        h = inner.winfo_reqheight() + 2
        pop.geometry(f"{w}x{h}+{x}+{y}")
        self._search_sel = 0
        self._search_select(0)

    def _search_select(self, i):
        C = cfg.theme()
        self._search_sel = i
        for j, ws in enumerate(getattr(self, "_search_rows", [])):
            bg = C["primary_light"] if j == i else C["card_bg"]
            for w in ws:
                try:
                    w.config(bg=bg)
                except Exception:
                    pass

    def _search_move(self, d):
        if not self._search_hits:
            self._search_key()
            return
        n = len(self._search_hits)
        self._search_select((getattr(self, "_search_sel", 0) + d) % n)

    def _search_hide(self):
        p = getattr(self, "_search_pop", None)
        self._search_pop = None
        if p is not None:
            try:
                p.destroy()
            except Exception:
                pass

    def _search_clear(self):
        self._search_hide()
        self._search_var.set("")
        try:
            self.root.focus_set()
        except Exception:
            pass

    def _search_open(self, i=None):
        if not self._search_hits:
            self._search_key()
            if not self._search_hits:
                return
        if i is None:
            i = getattr(self, "_search_sel", 0)
        try:
            _s, label, icon, group, (kind, target) = self._search_hits[i]
        except Exception:
            return
        self._search_hits = []
        self._search_clear()
        if kind == "rc":
            self._open_report(target)
        else:
            self._menu_open(target)

    def _alert_count(self):
        try:
            from ui import alerts as _al
            n = 0
            if cfg.flag("notify_low_stock", True):
                n += len(_al.low_stock_items())
            if cfg.flag("notify_payment_due", True):
                n += len(_al.due_invoices())
            return n
        except Exception:
            return 0

    def _refresh_bell(self):
        C = cfg.theme()
        bell = getattr(self, "_bell", None)
        try:
            if bell is None or not bell.winfo_exists():
                return
        except Exception:
            return
        n = self._alert_count()
        bell.delete("badge")
        if n:
            from ui.zoom import px
            txt = str(n) if n < 100 else "99+"
            w = px(8 + 6 * len(txt))
            R, H = px(35), px(16)
            self._round_rect(bell, R - w, 1, R, H, px(7), fill=C["danger"],
                             outline="white", tags="badge")
            bell.create_text(R - w / 2, H / 2 + 0.5, text=txt, fill="white",
                             font=("Segoe UI", -px(10), "bold"), tags="badge")
        try:
            self.root.after(5 * 60 * 1000, self._refresh_bell)
        except Exception:
            pass

    def _show_alerts(self):
        try:
            from ui import alerts as _al
            n = _al.show_startup_alerts(self.root, force=True,
                                        open_report=self._open_report)
            if not n:
                messagebox.showinfo("Alerts", "No alerts — stock and payments are fine.")
        except Exception as e:
            self._ui_fail("Alerts", e)

    def _user_menu(self, anchor):
        m = tk.Menu(self.root, tearoff=0)
        u = self.current_user or {}
        m.add_command(label="👤  " + str(u.get("username") or "user"), state="disabled")
        m.add_separator()
        if self._can_see("users"):
            m.add_command(label="Users & Rights / Change Password",
                          command=lambda: self._menu_open("users"))
        if self._can_see("settings"):
            m.add_command(label="Settings", command=lambda: self._menu_open("settings"))
        m.add_command(label="Alerts", command=self._show_alerts)
        m.add_separator()
        m.add_command(label="Log out", command=self._logout)
        try:
            m.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 4)
        finally:
            try:
                m.grab_release()
            except Exception:
                pass

    # ── Module Loader ─────────────────────────────────────────
    def _tk_error(self, exc, val, tb):
        """Global handler for errors raised inside any Tk callback.
        Logs the traceback, releases stray modal grabs (so the window
        never appears frozen), restores the main window if minimized,
        and shows one friendly dialog — the app keeps running."""
        import traceback, time
        txt = "".join(traceback.format_exception(exc, val, tb))
        print(txt)
        try:                                        # persist for support
            try:
                from config.paths import LOG_DIR as logdir
            except Exception:
                logdir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(logdir, exist_ok=True)
            from datetime import datetime as _dt
            with open(os.path.join(logdir, "ui_errors.log"), "a",
                      encoding="utf-8") as f:
                f.write("\n[%s]\n%s" % (_dt.now(), txt))
        except Exception:
            pass
        try:                                        # release stuck grab
            cur = self.root.grab_current()
            if cur is not None:
                cur.grab_release()
        except Exception:
            pass
        try:                                        # bring the app back
            if self.root.state() == "iconic":
                self.root.deiconify()
            self.root.lift()
        except Exception:
            pass
        now = time.time()                           # throttle dialogs
        if now - self._last_err_dlg > 2.0:
            self._last_err_dlg = now
            try:
                messagebox.showerror(
                    "Unexpected Error",
                    "Something went wrong in this screen:\n\n%s\n\n"
                    "The app is still running — details were saved to "
                    "logs/ui_errors.log." % str(val)[:280])
            except Exception:
                pass

    def _ui_fail(self, where, e):
        """Consistent non-fatal error report for guarded actions."""
        import traceback
        traceback.print_exc()
        try:
            cur = self.root.grab_current()
            if cur is not None:
                cur.grab_release()
        except Exception:
            pass
        try:
            messagebox.showerror(where,
                                 "%s\n\nThe app is still running." %
                                 str(e)[:280])
        except Exception:
            pass

    def _load_module(self, module_key: str):
        """Crash-proof module opener: an error while opening any screen
        shows a message and leaves the shell fully usable."""
        try:
            self._load_module_impl(module_key)
        except Exception as e:
            self._ui_fail("Open '%s'" % module_key, e)
            try:                        # clean up a half-open MDI child
                ch = self.mdi.windows.get(module_key)
                if ch is not None:
                    self.mdi.close(ch)
            except Exception:
                pass

    def _load_module_impl(self, module_key: str):
        C = cfg.theme()

        # Permission guard — never load a module the user can't see
        if module_key not in ("logout",) and not self._can_see(module_key):
            if getattr(self, "_layout_ready", False):
                messagebox.showwarning(
                    "Not allowed",
                    "Your user type can't open this screen.\n\n"
                    "Ask the administrator to give this right in Users & Rights.")
            return

        # POS opens its own window, not in the content area
        if module_key == "pos":
            self._open_pos()
            return

        # Deactivate old button, activate the new one (blue pill)
        old_key = self.current_module
        self.current_module = module_key
        if old_key and old_key != module_key:
            self._paint_nav(old_key, "normal")
        self._paint_nav(module_key, "active")
        try:
            self._nav_reveal(module_key)
            self._rail_paint()
        except Exception:
            pass

        # Update page title
        title_map = {
            "dashboard":  t("nav.dashboard"),
            "pos":        t("nav.pos"),
            "customers":  t("nav.customers"),
            "suppliers":  t("nav.suppliers"),
            "products":   t("nav.products"),
            "sales":      t("nav.sales"),
            "purchases":  t("nav.purchases"),
            "payments":   t("nav.payments"),
            "inventory":  t("nav.inventory"),
            "vat_report": t("nav.vat_report"),
            "zatca":      t("nav.zatca"),
            "reports":    t("nav.reports"),
            "accounting": t("nav.accounting"),
            "hr":         t("nav.hr"),
            "settings":   t("nav.settings"),
            "updates":    t("nav.updates"),
            "users":      t("nav.users"),
            "report_designer": t("nav.report_designer"),
            "barcode_designer": t("nav.barcode_designer"),
            "plu": "PLU Manager",
            "sales_return": t("nav.sales_return"),
            "purchase_return": t("nav.purchase_return"),
            "vouchers":   "Vouchers",
            "ledger":     "Account Ledger",
            "audit_log":  "Audit Log",
            "print_settings": "Print & Invoice",
            "day_close":  "Day Close / Z-Report",
            "setup":      "Setup Checklist",
            "integrations": "Integrations",
            "expenses":   "Expenses",
            "consumption": "Consumable Entry",
            "aging":      "Outstanding / Aging",
            "printer_mgmt": "Printer Management",
            "account_defaults": "Default Accounts",
            "opening":    "Opening Balances",
            "fin_reports": "Financial Reports",
            "cust_statement": "Customer Statement",
            "supp_statement": "Supplier Statement",
            "report_center": "Reports Center",
            "insights": "Smart Insights",
            "branches": "Branches & Counters",
            "quotations": "Quotations",
            "offers": "Offers & Promotions",
            "price_labels": "Price Change Labels",
            "label_print": "Print Barcode Labels",
            "mobile": "Mobile, PDT & Van",
            "purchase_orders": "Purchase Orders",
            "price_lists": "Price Lists",
            "stock_transfers": "Stock Transfers & Branch Stock",
            "expiry": "Batches & Expiry",
            "stock_count": "Stock Count",
            "price_updates": "Price Updates",
            "debit_notes": "Debit Notes",
            "bank_rec": "Bank Reconciliation",
            "year_end": "Year-End Closing",
        }
        try:                          # v7.0: business module pages
            from modules import business as _biz
            for _g, _items in _biz.NAV.values():
                for _k, _i, _l in _items:
                    title_map.setdefault(_k, _l)
            from modules import country as _ctry
            if not _ctry.is_sa():
                title_map["vat_report"] = "GST Returns" if _ctry.is_in() else "VAT 201 Return"
        except Exception:
            pass
        self.page_title_var.set(title_map.get(module_key, module_key.title()))

        # Open (or focus) an MDI child window; build the view into its body.
        title = title_map.get(module_key, module_key.title())
        try:
            from ui.page_info import subtitle as _sub
            sub = _sub(module_key)
        except Exception:
            sub = ""
        body = self.mdi.open(module_key, title,
                             icon=getattr(self, "_nav_icons", {}).get(module_key, ""),
                             subtitle=sub)
        if body is None:
            return                      # already open — restored & focused
        self.content = body             # the View chain below mounts here

        # (fresh body is empty; nothing to clear)

        # Load module view
        try:
            if module_key == "dashboard":
                from ui.dashboard import DashboardView
                DashboardView(self.content)

            elif module_key == "customers":
                from ui.customers import CustomersView
                CustomersView(self.content)

            elif module_key == "products":
                from ui.products import ProductsView
                ProductsView(self.content)

            elif module_key == "sales":
                from ui.invoices import SalesInvoiceView
                SalesInvoiceView(self.content)

            elif module_key == "zatca":
                from ui.zatca import ZatcaView
                ZatcaView(self.content)

            elif module_key == "vat_report":
                from modules import country as _ctry
                if _ctry.is_sa():
                    from ui.vat_report import VatReportView
                    VatReportView(self.content)
                else:                    # v7.0: GSTR-3B (India) / VAT 201 (UAE)
                    from ui.report_center import ReportCenterView
                    ReportCenterView(self.content, initial="gstr3b" if _ctry.is_in() else "uae_vat201")

            elif module_key == "suppliers":
                from ui.suppliers import SuppliersView
                SuppliersView(self.content)

            elif module_key == "payments":
                from ui.payments import PaymentsView
                PaymentsView(self.content)

            elif module_key == "purchases":
                from ui.purchases import PurchaseInvoiceView
                PurchaseInvoiceView(self.content)

            elif module_key == "inventory":
                from ui.inventory import InventoryView
                InventoryView(self.content)

            elif module_key == "reports":
                from ui.reports import ReportsView
                ReportsView(self.content)

            elif module_key == "accounting":
                from ui.accounting import AccountingView
                AccountingView(self.content)

            elif module_key == "vouchers":
                from ui.vouchers import VouchersView
                VouchersView(self.content)

            elif module_key == "ledger":
                from ui.ledger import LedgerView
                LedgerView(self.content)

            elif module_key == "audit_log":
                from ui.audit_log import AuditLogView
                AuditLogView(self.content)

            elif module_key == "print_settings":
                from ui.print_settings import PrintSettingsView
                PrintSettingsView(self.content)

            elif module_key == "day_close":
                from ui.day_close import DayCloseView
                DayCloseView(self.content)

            elif module_key == "setup":
                from ui.setup_wizard import SetupChecklist
                SetupChecklist(self.content)

            elif module_key == "integrations":
                from ui.integrations import IntegrationsView
                IntegrationsView(self.content)

            elif module_key == "expenses":
                from ui.expenses import ExpensesView
                ExpensesView(self.content)

            elif module_key == "consumption":
                from ui.consumption import ConsumptionView
                ConsumptionView(self.content)

            elif module_key == "aging":
                from ui.aging import AgingView
                AgingView(self.content)

            elif module_key == "printer_mgmt":
                from ui.printer_management import PrinterManagementView
                PrinterManagementView(self.content)

            elif module_key == "opening":
                from ui.opening_balances import OpeningBalancesView
                OpeningBalancesView(self.content, tab=getattr(self, "_opening_tab", "accounts"))
                self._opening_tab = "accounts"

            elif module_key == "account_defaults":
                from ui.account_defaults_tab import DefaultAccountsTab
                DefaultAccountsTab(self.content).pack(fill="both", expand=True)

            elif module_key == "fin_reports":
                from ui.financial_reports import FinancialReportsView
                FinancialReportsView(self.content)

            elif module_key == "price_labels":
                from ui.price_labels import PriceLabelsView
                PriceLabelsView(self.content)

            elif module_key == "quotations":
                from ui.quotes import QuotationsView
                QuotationsView(self.content)

            elif module_key == "offers":
                from ui.offers import OffersView
                OffersView(self.content)

            elif module_key == "branches":
                from ui.branches import BranchesView
                BranchesView(self.content)

            elif module_key == "insights":
                from ui.insights import InsightsView
                InsightsView(self.content)

            elif module_key == "stock_count":
                from ui.stock_count import StockCountView
                StockCountView(self.content)

            elif module_key == "price_updates":
                from ui.price_updates import PriceUpdatesView
                PriceUpdatesView(self.content)

            elif module_key == "purchase_orders":
                from ui.quotes import PurchaseOrdersView
                PurchaseOrdersView(self.content)

            elif module_key == "report_center":
                from ui.report_center import ReportCenterView
                self._rc_view = ReportCenterView(
                    self.content, initial=getattr(self, "_rc_pending", None))

            elif module_key == "cust_statement":
                from ui.statements import CustomerStatementView
                CustomerStatementView(self.content)

            elif module_key == "supp_statement":
                from ui.statements import SupplierStatementView
                SupplierStatementView(self.content)

            elif module_key == "hr":
                from ui.hr import HRView
                HRView(self.content)

            elif module_key == "updates":
                from ui.updates import UpdatesView
                UpdatesView(self.content)

            elif module_key == "users":
                try:
                    from ui.user_rights import UserRightsView
                    UserRightsView(self.content)
                except Exception:
                    from ui.users import UsersView
                    UsersView(self.content)

            elif module_key == "report_designer":
                from ui.report_designer import ReportDesignerView
                ReportDesignerView(self.content)

            elif module_key == "barcode_designer":
                from ui.barcode_designer import BarcodeDesignerView
                BarcodeDesignerView(self.content)

            elif module_key == "mobile":
                from ui.mobile_center import MobileCenterView
                MobileCenterView(self.content)

            elif module_key == "label_print":
                from ui.barcode_designer import BarcodeDesignerView
                BarcodeDesignerView(self.content, start="print")

            elif module_key == "plu":
                from ui.plu_manager import PLUManagerView
                PLUManagerView(self.content)

            elif module_key == "settings":
                from ui.settings import SettingsView
                SettingsView(self.content)

            elif module_key == "sales_return":
                from ui.returns import SalesReturnView
                SalesReturnView(self.content)

            # ── v6.0 pages ──
            elif module_key == "price_lists":
                from ui.price_lists_view import PriceListsView
                PriceListsView(self.content)

            elif module_key == "stock_transfers":
                from ui.stock_transfers import StockTransfersView
                StockTransfersView(self.content)

            elif module_key == "expiry":
                from ui.expiry_view import ExpiryView
                ExpiryView(self.content)

            elif module_key == "debit_notes":
                from ui.debit_notes import DebitNotesView
                DebitNotesView(self.content)

            elif module_key == "bank_rec":
                from ui.bank_rec_view import BankRecView
                BankRecView(self.content)

            elif module_key == "year_end":
                from ui.year_end_view import YearEndView
                YearEndView(self.content)

            elif module_key == "purchase_return":
                from ui.returns import PurchaseReturnView
                PurchaseReturnView(self.content)

            elif self._biz_screen(module_key):
                import importlib
                from modules import business as _biz
                _mod, _cls = _biz.SCREENS[module_key]
                getattr(importlib.import_module(_mod), _cls)(self.content)

            else:
                self._placeholder(module_key)

        except ImportError as e:
            print(f"Module import error: {e}")
            self._load_error(module_key, e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._load_error(module_key, e)

        # the window header shows the page name + sub-heading: hide the page's
        # own copy of the same title (shown once, not twice)
        try:
            from ui.mdi import dedupe_heading
            body_ref2 = self.content
            body_ref2.after(60, lambda b=body_ref2, tt=title:
                            dedupe_heading(b, tt) if b.winfo_exists() else None)
        except Exception:
            pass

        # ── Global UI polish pass (ui_polish.py) ──
        # Hover states, focus rings, zebra-striped & sortable tables on
        # every view. after(): let the view finish building first.
        try:
            from ui.ui_polish import beautify, fit_page
            body_ref = self.content
            body_ref.after(80, lambda b=body_ref: beautify(b))
            # buttons under a table stay on screen on small monitors
            fit_page(body_ref)
            body_ref.after(400, lambda b=body_ref: fit_page(b) if b.winfo_exists() else None)
        except Exception:
            pass

    @staticmethod
    def _biz_screen(module_key):
        try:
            from modules import business as _biz
            return module_key in _biz.SCREENS
        except Exception:
            return False

    def _load_error(self, module_key, err):
        """A page hit an error while opening: say so plainly (not "coming
        soon"). If the page was built, a thin strip at the bottom; if not,
        a card with the message."""
        C = cfg.theme()
        msg = str(err).strip() or err.__class__.__name__
        try:
            built = any(w.winfo_manager() for w in self.content.winfo_children())
        except Exception:
            built = False
        if built:
            bar = tk.Frame(self.content, bg="#FEF2F2", highlightthickness=1,
                           highlightbackground="#FCA5A5")
            bar.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
            tk.Label(bar, text="⚠  Part of this page could not load: " + msg[:160],
                     font=("Segoe UI", 9), bg="#FEF2F2", fg="#B91C1C", anchor="w",
                     justify="left", wraplength=900).pack(fill="x", padx=10, pady=6)
            return
        card = tk.Frame(self.content, bg=C["card_bg"], highlightthickness=1,
                        highlightbackground=C["border"])
        card.pack(expand=True, padx=40, pady=40)
        tk.Label(card, text="⚠", font=("Segoe UI Emoji", 28), bg=C["card_bg"],
                 fg=C["warning"]).pack(pady=(18, 4))
        tk.Label(card, text="This page could not open", font=("Segoe UI", 14, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack()
        tk.Label(card, text=msg[:300], font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"], wraplength=520, justify="center").pack(padx=24, pady=(6, 4))
        tk.Label(card, text="Close it and open it again. If it keeps happening, send this message "
                            "to your DayBill dealer.", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"], wraplength=520, justify="center").pack(padx=24, pady=(0, 18))

    def _placeholder(self, module_key: str):
        C = cfg.theme()
        frame = tk.Frame(self.content, bg=C["content_bg"])
        frame.pack(fill="both", expand=True)

        icons = {
            "customers": "👥", "suppliers": "🏭", "products": "📦",
            "sales": "🧾", "purchases": "🛒", "payments": "💳",
            "vat_report": "📋", "zatca": "🔐", "reports": "📈", "report_center": "📊",
            "inventory": "📦", "accounting": "📒", "hr": "👔",
            "settings": "⚙️", "updates": "🔄", "users": "👤"
        }
        icon = icons.get(module_key, "📄")

        tk.Label(frame, text=icon, font=("Segoe UI Emoji", 48),
                 bg=C["content_bg"]).pack(expand=True, pady=(80, 10))
        tk.Label(frame, text=module_key.replace("_", " ").title() + " Module",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack()
        tk.Label(frame, text="Coming in next steps...",
                 font=("Segoe UI", 11),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(pady=8)

    # ── Open POS ──────────────────────────────────────────────
    def _open_pos(self):
        if not self._can_see("pos"):
            messagebox.showwarning("Not allowed",
                                   "Your user type can't use the POS / Cashier screen.")
            return
        before = set(self.root.winfo_children())
        try:
            from ui.pos import POSWindow
            from ui import close_guard
            close_guard.single("pos", lambda: POSWindow(self.root))   # F3 again → the open POS
        except Exception as e:
            import traceback; traceback.print_exc()
            # a POS window that failed half-way through building would
            # otherwise stay fullscreen and dead over the app — remove it
            try:
                for w in set(self.root.winfo_children()) - before:
                    if isinstance(w, tk.Toplevel):
                        try:
                            w.grab_release()
                        except Exception:
                            pass
                        w.destroy()
            except Exception:
                pass
            try:
                cur = self.root.grab_current()
                if cur is not None:
                    cur.grab_release()
            except Exception:
                pass
            try:
                self.root.deiconify(); self.root.lift()
            except Exception:
                pass
            messagebox.showerror("POS Error",
                                 "%s\n\nThe app is still running." %
                                 str(e)[:280])

    # ── Language Toggle ───────────────────────────────────────
    def _toggle_language(self):
        new_lang = "ar" if current_lang() == "en" else "en"
        load_language(new_lang)
        cfg.set("language", new_lang)
        cfg.save_settings()
        messagebox.showinfo(
            "Language / اللغة",
            "Please restart the app to apply the language change.\nأعد تشغيل التطبيق لتطبيق تغيير اللغة."
        )

    # ── Logout ────────────────────────────────────────────────
    def _logout(self):
        C = cfg.theme()
        if messagebox.askyesno(t("nav.logout"), "Are you sure you want to logout?\nهل تريد تسجيل الخروج؟"):
            db.disconnect()
            self.root.destroy()

    def _on_close(self):
        if not messagebox.askyesno("Exit DayBill ERP",
                                   "Do you want to close DayBill ERP?\n"
                                   "هل تريد إغلاق البرنامج؟", parent=self.root):
            return
        # second step — make sure (open bills / forms are closed too)
        if not messagebox.askyesno("Confirm exit",
                                   "Are you sure?\nAny bill or form that is not saved "
                                   "will be lost.\n\nYes = close DayBill ERP\n"
                                   "هل أنت متأكد؟", icon="warning", parent=self.root):
            return
        # ── Automatic SQL backup on exit (Settings ▸ Backup) ──
        try:
            if cfg.get("backup_on_exit", True):
                from modules import db_backup
                ok, res = db_backup.backup_now(note="exit")
                if not ok:
                    print("[DayBill] exit backup failed:", res)
        except Exception as e:
            print("[DayBill] exit backup error:", e)
        try:
            cfg.save_settings()
            db.disconnect()
        except Exception:
            pass
        self.root.destroy()

    def _backup_daily_tick(self):
        """Fire a backup once per day at the configured HH:MM (Settings ▸
        Backup ▸ 'Daily backup at time'). Checked every minute."""
        try:
            want = str(cfg.get("backup_time", "") or "").strip()
            if want:
                from datetime import datetime as _dt
                now = _dt.now()
                today_key = now.strftime("%Y-%m-%d")
                if (now.strftime("%H:%M") >= want[:5]
                        and self._daily_backup_done != today_key):
                    self._daily_backup_done = today_key
                    try:
                        from modules import db_backup
                        ok, res = db_backup.backup_now(note="daily")
                        print("[DayBill] daily backup:",
                              "OK " + res if ok else "FAILED " + res)
                        from ui import alerts as _al
                        _al.backup_notice(self.root, ok, res)
                    except Exception as e:
                        print("[DayBill] daily backup error:", e)
        except Exception:
            pass
        try:
            self.root.after(60 * 1000, self._backup_daily_tick)
        except Exception:
            pass

    def _backup_tick(self):
        """Timed automatic backup (Settings ▸ Backup ▸ every N hours)."""
        try:
            hours = float(cfg.get("backup_every_hours", 0) or 0)
        except Exception:
            hours = 0
        if hours <= 0:
            return
        try:
            from modules import db_backup
            ok, res = db_backup.backup_now(note="auto")
            print("[DayBill] auto backup:", "OK " + res if ok else
                  "FAILED " + res)
            from ui import alerts as _al
            _al.backup_notice(self.root, ok, res)
        except Exception as e:
            print("[DayBill] auto backup error:", e)
        try:
            self.root.after(int(hours * 3600 * 1000), self._backup_tick)
        except Exception:
            pass
