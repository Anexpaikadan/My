# ============================================================
# Saudi Arabia ERP - Login Window
# Bilingual: Arabic (RTL) / English (LTR)
# Professional Saudi green theme
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.version import VERSION as _APP_VERSION
from config.language import t, load_language, current_lang, is_rtl
from config.database import db, load_db_config, save_db_config


class LoginWindow:
    # wrong-password protection: 5 misses → wait 60 s (per username)
    MAX_FAILS = 5
    LOCK_SECONDS = 60
    _fails = {}          # username(lower) -> [timestamps of recent misses]

    def __init__(self, parent):
        self.parent = parent
        self.login_success = False
        self.current_user = None
        self._build_window()

    # ── Build Window ──────────────────────────────────────────
    def _build_window(self):
        C = cfg.theme()

        self.window = tk.Toplevel(self.parent)
        self.window.title(t("app_title"))
        self.window.geometry("900x580")
        self.window.resizable(False, False)
        self.window.configure(bg=C["content_bg"])
        self._center_window(900, 580)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # Main frame (two columns: left panel + right form)
        main = tk.Frame(self.window, bg=C["content_bg"])
        main.pack(fill="both", expand=True)

        self._build_left_panel(main, C)
        self._build_right_panel(main, C)

        # Global UI polish (hover states, focus rings)
        try:
            from ui.ui_polish import beautify, enable_auto_polish
            enable_auto_polish(self.parent)
            from ui.ui_polish import enable_windows_behaviour
            enable_windows_behaviour(self.parent)
            self.window.after(120, lambda w=self.window: beautify(w))
        except Exception:
            pass

    # ── Left Decorative Panel ─────────────────────────────────
    def _build_left_panel(self, parent, C):
        left = tk.Frame(parent, bg=C["sidebar_bg"], width=380)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Spacer top
        tk.Frame(left, bg=C["sidebar_bg"], height=70).pack()

        # DayBill logo on a white card (logo has white background)
        logo_img = None
        try:
            from ui.widgets import load_logo
            logo_img = load_logo(max_width=260, max_height=130)
        except Exception:
            logo_img = None

        if logo_img is not None:
            card = tk.Frame(left, bg="white")
            card.pack(pady=(0, 22))
            lbl = tk.Label(card, image=logo_img, bg="white", bd=0)
            lbl.image = logo_img  # keep ref
            lbl.pack(padx=14, pady=10)
        else:
            tk.Label(left, text="DAYbill", font=("Segoe UI", 30, "bold"),
                     bg=C["sidebar_bg"], fg="white").pack(pady=(0, 6))
            tk.Label(left, text="Solution", font=("Segoe UI", 12, "italic"),
                     bg=C["sidebar_bg"], fg=C["accent"]).pack(pady=(0, 20))

        # App subtitle
        tk.Label(
            left,
            text=t("app_subtitle"),
            font=("Segoe UI", 10),
            bg=C["sidebar_bg"],
            fg="#C9C2F2",
            wraplength=300,
            justify="center"
        ).pack(pady=(0, 0), padx=20)

        # Divider
        tk.Frame(left, bg="#FFFFFF", height=1, width=200).pack(pady=30)

        # ZATCA badges
        badges = [
            ("✅", "ZATCA Phase 1 & Phase 2"),
            ("📄", "E-Invoice UBL 2.1 XML"),
            ("🔐", "Cryptographic Stamp"),
            ("🌐", "Arabic & English"),
        ]
        for icon, text in badges:
            row = tk.Frame(left, bg=C["sidebar_bg"])
            row.pack(anchor="w", padx=40, pady=4)
            tk.Label(row, text=icon, font=("Segoe UI Emoji", 12),
                     bg=C["sidebar_bg"], fg="white").pack(side="left")
            tk.Label(row, text=f"  {text}", font=("Segoe UI", 10),
                     bg=C["sidebar_bg"], fg="#D1FAE5").pack(side="left")

        # Version
        tk.Label(
            left,
            text="v%s  |  Saudi Arabia VAT 15%%" % _APP_VERSION,
            font=("Segoe UI", 8),
            bg=C["sidebar_bg"],
            fg="#6EAA8A"
        ).pack(side="bottom", pady=20)

    # ── Right Login Form ──────────────────────────────────────
    def _build_right_panel(self, parent, C):
        right = tk.Frame(parent, bg=C["content_bg"])
        right.pack(side="right", fill="both", expand=True)

        # Center container
        container = tk.Frame(right, bg=C["content_bg"])
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Language toggle (top right)
        lang_frame = tk.Frame(right, bg=C["content_bg"])
        lang_frame.place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=15)

        self.lang_btn = tk.Button(
            lang_frame,
            text="🌐  العربية" if current_lang() == "en" else "🌐  English",
            font=("Segoe UI", 9),
            bg=C["primary_light"],
            fg=C["primary"],
            relief="flat",
            cursor="hand2",
            padx=10, pady=5,
            command=self._toggle_language
        )
        self.lang_btn.pack()

        # Title
        tk.Label(
            container,
            text=t("login.title"),
            font=("Segoe UI", 22, "bold"),
            bg=C["content_bg"],
            fg=C["text_primary"]
        ).pack(anchor="w" if not is_rtl() else "e")

        tk.Label(
            container,
            text=t("login.subtitle"),
            font=("Segoe UI", 11),
            bg=C["content_bg"],
            fg=C["text_secondary"]
        ).pack(anchor="w" if not is_rtl() else "e", pady=(4, 30))

        # ── Username Field ────────────────────────────────────
        tk.Label(
            container,
            text=t("login.username"),
            font=("Segoe UI", 10, "bold"),
            bg=C["content_bg"],
            fg=C["text_primary"]
        ).pack(anchor="w" if not is_rtl() else "e")

        user_frame = tk.Frame(container, bg=C["border"], bd=0)
        user_frame.pack(fill="x", ipady=1, pady=(4, 14))

        inner_u = tk.Frame(user_frame, bg="white", bd=0)
        inner_u.pack(fill="both", padx=1, pady=1)

        tk.Label(inner_u, text="👤", font=("Segoe UI Emoji", 12),
                 bg="white", fg=C["text_secondary"]).pack(side="left", padx=(10, 5))

        self.username_var = tk.StringVar()
        self.username_entry = tk.Entry(
            inner_u,
            textvariable=self.username_var,
            font=("Segoe UI", 12),
            bg="white",
            fg=C["text_primary"],
            relief="flat",
            width=22,
            justify="right" if is_rtl() else "left"
        )
        self.username_entry.pack(side="left", fill="x", expand=True, ipady=8)

        # ── Password Field ────────────────────────────────────
        tk.Label(
            container,
            text=t("login.password"),
            font=("Segoe UI", 10, "bold"),
            bg=C["content_bg"],
            fg=C["text_primary"]
        ).pack(anchor="w" if not is_rtl() else "e")

        pass_frame = tk.Frame(container, bg=C["border"], bd=0)
        pass_frame.pack(fill="x", ipady=1, pady=(4, 6))

        inner_p = tk.Frame(pass_frame, bg="white", bd=0)
        inner_p.pack(fill="both", padx=1, pady=1)

        tk.Label(inner_p, text="🔒", font=("Segoe UI Emoji", 12),
                 bg="white", fg=C["text_secondary"]).pack(side="left", padx=(10, 5))

        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(
            inner_p,
            textvariable=self.password_var,
            font=("Segoe UI", 12),
            bg="white",
            fg=C["text_primary"],
            relief="flat",
            show="●",
            width=22,
            justify="right" if is_rtl() else "left"
        )
        self.password_entry.pack(side="left", fill="x", expand=True, ipady=8)

        # Show/hide password
        self.show_pass = False
        tk.Button(
            inner_p, text="👁", font=("Segoe UI Emoji", 11),
            bg="white", fg=C["text_secondary"], relief="flat",
            cursor="hand2", padx=6,
            command=self._toggle_password
        ).pack(side="right", padx=5)

        # ── Remember me ───────────────────────────────────────
        rem_frame = tk.Frame(container, bg=C["content_bg"])
        rem_frame.pack(fill="x", pady=6)
        _remembered = str(cfg.get("remember_username", "") or "")
        self.remember_var = tk.BooleanVar(value=bool(_remembered))
        tk.Checkbutton(
            rem_frame,
            text=t("login.remember_me"),
            variable=self.remember_var,
            font=("Segoe UI", 9),
            bg=C["content_bg"],
            fg=C["text_secondary"],
            activebackground=C["content_bg"],
            relief="flat"
        ).pack(side="left" if not is_rtl() else "right")

        # ── Financial Year (login-time selection) ─────────────
        fy_frame = tk.Frame(container, bg=C["content_bg"])
        fy_frame.pack(fill="x", pady=(2, 4))
        tk.Label(fy_frame, text="📅 Financial Year",
                 font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left" if not is_rtl()
                                            else "right")
        self.fy_var = tk.StringVar()
        self.fy_combo = ttk.Combobox(fy_frame, textvariable=self.fy_var,
                                     state="readonly", width=20,
                                     font=("Segoe UI", 9))
        self.fy_combo.pack(side="right" if not is_rtl() else "left")
        self._fy_years = []
        self._load_fy_years()

        # ── Error label ───────────────────────────────────────
        self.error_var = tk.StringVar()
        self.error_label = tk.Label(
            container,
            textvariable=self.error_var,
            font=("Segoe UI", 9),
            bg=C["content_bg"],
            fg=C["danger"],
            wraplength=280,
            justify="center"
        )
        self.error_label.pack(pady=(0, 8))

        # ── Sign In Button ────────────────────────────────────
        self.login_btn = tk.Button(
            container,
            text=t("login.sign_in"),
            font=("Segoe UI", 12, "bold"),
            bg=C["primary"],
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=20, pady=12,
            width=24,
            activebackground=C["primary_dark"],
            activeforeground="white",
            command=self._do_login
        )
        self.login_btn.pack(fill="x", pady=(0, 10))

        # ── DB Settings + Forgot password links ───────────────
        links = tk.Frame(container, bg=C["content_bg"])
        links.pack()
        tk.Button(
            links,
            text=f"⚙  {t('login.db_settings')}",
            font=("Segoe UI", 9),
            bg=C["content_bg"],
            fg=C["primary"],
            relief="flat",
            cursor="hand2",
            command=self._open_db_settings
        ).pack(side="left", padx=4)
        tk.Button(                                  # v6.0.2
            links,
            text="🔑  Forgot password?",
            font=("Segoe UI", 9),
            bg=C["content_bg"],
            fg=C["primary"],
            relief="flat",
            cursor="hand2",
            command=self._forgot_password
        ).pack(side="left", padx=4)

        # Bind Enter key
        self.window.bind("<Return>", lambda e: self._do_login())
        if _remembered:
            self.username_var.set(_remembered)
            self.password_entry.focus_set()
        else:
            self.username_entry.focus_set()

    # ── Login Logic ───────────────────────────────────────────
    def _load_fy_years(self):
        """Fill the Financial Year dropdown from the database. Silently
        shows '(all years)' when the DB or table isn't reachable yet."""
        years = []
        try:
            from modules import financial_year as fy
            if fy.tables_ready():
                years = fy.list_years() or []
        except Exception:
            years = []
        self._fy_years = years
        if not years:
            self.fy_combo["values"] = ["(default — all years)"]
            self.fy_combo.current(0)
            return
        vals = ["%s   (%s → %s)%s" % (
            y.get("label", ""), str(y.get("start_date", ""))[:10],
            str(y.get("end_date", ""))[:10],
            "  🔒" if y.get("is_closed") else "")
            for y in years]
        self.fy_combo["values"] = vals
        # preselect: last chosen, else the open year containing today
        try:
            from config import settings as cfg
            want = cfg.get("active_fy_id", None)
            idx = next((i for i, y in enumerate(years)
                        if str(y.get("fy_id")) == str(want)), None)
            if idx is None:
                from datetime import date as _d
                today = _d.today().isoformat()
                idx = next((i for i, y in enumerate(years)
                            if str(y.get("start_date"))[:10] <= today <=
                            str(y.get("end_date"))[:10]), 0)
            self.fy_combo.current(idx)
        except Exception:
            self.fy_combo.current(0)

    def _apply_fy_selection(self):
        """Persist the chosen financial year so every transaction screen
        restricts entries/edits to it (fy.guard_active)."""
        try:
            from modules import financial_year as fy
            i = self.fy_combo.current()
            if self._fy_years and 0 <= i < len(self._fy_years):
                fy.set_active(self._fy_years[i])
            else:
                fy.clear_active()
        except Exception:
            pass

    # ── wrong-password lock ───────────────────────────────────
    def _locked_for(self, username):
        import time
        now = time.time()
        key = username.lower()
        recent = [t0 for t0 in self._fails.get(key, []) if now - t0 < self.LOCK_SECONDS]
        self._fails[key] = recent
        if len(recent) >= self.MAX_FAILS:
            return int(self.LOCK_SECONDS - (now - recent[-self.MAX_FAILS])) + 1
        # v5.27: also count misses saved in the login history (restart /
        # another PC doesn't reset the lock)
        try:
            from modules import permissions as _perm
            if _perm.recent_failed_logins(username, self.LOCK_SECONDS) >= self.MAX_FAILS:
                return self.LOCK_SECONDS
        except Exception:
            pass
        return 0

    def _note_fail(self, username):
        import time
        self._fails.setdefault(username.lower(), []).append(time.time())

    @staticmethod
    def _needs_first_password(stored_hash):
        """True when the stored hash is the setup-script placeholder (or
        empty / unusable) — i.e. this account never had a real password."""
        h = str(stored_hash or "").strip()
        if not h or "placeholder" in h.lower():
            return True
        if h.startswith(("$2a$", "$2b$", "$2y$", "$argon2", "pbkdf2$")):
            return False
        return not (len(h) == 64 and all(ch in "0123456789abcdef" for ch in h.lower()))

    def _set_first_password(self, user):
        """First run: the admin user still has the placeholder password
        from the setup script — ask for a real one now."""
        dlg = FirstPasswordDialog(self.window, user.get("username", "admin"))
        self.window.wait_window(dlg.win)
        if not dlg.password:
            return None
        from modules import permissions as _perm
        new_hash = _perm.hash_password(dlg.password)
        db.execute("UPDATE users SET password_hash=?, updated_at=GETDATE() WHERE user_id=?",
                   (new_hash, user["user_id"]))
        _perm.mark_password_changed(user["user_id"])
        user = dict(user); user["password_hash"] = new_hash
        messagebox.showinfo("Password set",
                            "Password saved. Use it every time you sign in as "
                            f"'{user.get('username')}'.", parent=self.window)
        return user

    def _password_still_valid(self, user):
        """True to continue signing in. When the password is older than
        Settings ▸ Password Expiry, the user must choose a new one now."""
        try:
            days = int(float(cfg.get("pwd_expiry_days", 0) or 0))
        except Exception:
            days = 0
        if days <= 0:
            return True
        from modules import permissions as _perm
        age = _perm.password_age_days(user["user_id"])
        if age is None or age < days:
            return True
        dlg = FirstPasswordDialog(self.window, user.get("username", ""), expired_days=age)
        self.window.wait_window(dlg.win)
        if not dlg.password:
            self._fail("Your password has expired. Choose a new one to sign in.")
            return False
        if self._verify_password(dlg.password, user.get("password_hash", "")):
            self._fail("Please choose a NEW password (not the old one).")
            return False
        new_hash = _perm.hash_password(dlg.password)
        db.execute("UPDATE users SET password_hash=?, updated_at=GETDATE() WHERE user_id=?",
                   (new_hash, user["user_id"]))
        _perm.mark_password_changed(user["user_id"])
        user["password_hash"] = new_hash
        messagebox.showinfo("Password changed", "New password saved.", parent=self.window)
        return True

    def _fail(self, msg):
        self.error_var.set(msg)
        self.login_btn.config(text=t("login.sign_in"), state="normal")
        self.password_entry.delete(0, "end")
        self.password_entry.focus_set()

    def _do_login(self):
        C = cfg.theme()
        username = self.username_var.get().strip()
        raw_pw = self.password_var.get()
        password = raw_pw.strip()

        if not username or not raw_pw:
            self.error_var.set(t("login.error_empty"))
            return
        wait = self._locked_for(username)
        if wait:
            self.error_var.set(f"Too many wrong passwords. Try again in {wait} seconds.")
            return

        self.error_var.set("")
        self.login_btn.config(text=t("login.connecting"), state="disabled")
        self.window.update()

        # Connect to DB if not connected
        if not db.is_connected():
            if not db.connect():
                self.error_var.set(t("login.error_db"))
                self.login_btn.config(text=t("login.sign_in"), state="normal")
                # Guide the user straight to the DB setup dialog
                try:                       # v6.0.2: db_config.json copied from another PC
                    from config import secret_box as _sb
                    locked = "another computer" in str(_sb.last_error or "")
                except Exception:
                    locked = False
                messagebox.showwarning(
                    "Database Connection",
                    "Could not connect to the database.\n\n"
                    + ("The saved SQL password was locked on ANOTHER computer (the settings "
                       "were copied) — type the SQL password again in Database Settings.\n\n"
                       if locked else "") +
                    "Most likely causes:\n"
                    "  •  Wrong server name or login in Database Settings\n"
                    "     (🔍 Find tries the SQL Servers on this PC and the network)\n"
                    "  •  SQL Server service not running\n"
                    "  •  The DayBillERP database has not been created yet\n\n"
                    "The Database Settings window will now open so you can fix it.")
                try:
                    DbSettingsDialog(self.window)
                except Exception:
                    pass
                return

        # Authenticate user
        try:
            from modules import permissions as _perm
            if db.is_daybill() is False:          # v6.0.1: another program's database
                self._not_daybill()
                return
            user = db.fetchone("SELECT * FROM users WHERE username = ?", (username,))

            # first run: account still has the setup-script placeholder
            if user and user.get("is_active", 1) and \
                    self._needs_first_password(user.get("password_hash")):
                user = self._set_first_password(user)
                if not user:
                    self._fail("Set a password to continue.")
                    return
                raw_pw = password = None      # just set — no re-check needed
                ok = True
            else:
                ok = bool(user) and (
                    self._verify_password(raw_pw, user["password_hash"]) or
                    (password != raw_pw and
                     self._verify_password(password, user["password_hash"])))

            if not ok:
                self._note_fail(username)
                try:
                    _perm.log_login(user["user_id"] if user else None, username, False)
                except Exception:
                    pass
                left = self.MAX_FAILS - len(self._fails.get(username.lower(), []))
                self._fail(t("login.error_invalid") +
                           (f"  ({left} tries left)" if 0 < left <= 2 else ""))
                return

            if not user.get("is_active", 1):
                _perm.log_login(user["user_id"], username, False)
                self._fail("This user is switched off (inactive). "
                           "Ask the administrator to activate it.")
                return

            # RBAC: prime the permission session; a user whose type has no
            # rights at all can't do anything — say so instead of an empty app
            try:
                _perm.bootstrap_roles_and_permissions()
                _perm.set_session_user(user)
            except Exception:
                pass
            if not _perm.has_any_right():
                _perm.log_login(user["user_id"], username, False)
                self._fail("Your user type has no rights yet. Ask the administrator "
                           "to tick rights for it in Users & Rights.")
                return

            # Settings ▸ Users & Security ▸ Password Expiry
            if not self._password_still_valid(user):
                return
            db.execute("UPDATE users SET last_login = GETDATE() WHERE user_id = ?",
                       (user["user_id"],))
            # v5.27: an old unsalted password hash is replaced now
            try:
                if raw_pw and _perm.needs_rehash(user.get("password_hash")):
                    _ok_pw = raw_pw if self._verify_password(raw_pw, user["password_hash"]) \
                        else password
                    _perm.upgrade_hash(user["user_id"], _ok_pw)
            except Exception:
                pass
            try:
                _perm.log_login(user["user_id"], username, True)
            except Exception:
                pass
            self._fails.pop(username.lower(), None)
            # Remember me = remember the USERNAME (never the password)
            try:
                cfg.set("remember_username", username if self.remember_var.get() else "")
                cfg.save_settings()
            except Exception:
                pass
            load_language(user.get("preferred_language", "en") or "en")
            # persist the login-selected financial year
            self._apply_fy_selection()
            self.current_user = user
            self.login_success = True
            self.window.destroy()

        except Exception as e:
            self.error_var.set(f"{t('login.error_db')}\n{str(e)[:80]}")
            self.login_btn.config(text=t("login.sign_in"), state="normal")

    def _not_daybill(self):
        """v6.0.1: the database DayBill is set to has no DayBill tables — it
        belongs to another program (e.g. that program's .bak was restored
        under DayBill's name) or is empty. Say so clearly (it used to show
        "Database connection failed … 'user_id'") and open Database Settings.
        Nothing is written to that database."""
        try:
            name = (load_db_config() or {}).get("database") or "DayBillERP"
        except Exception:
            name = "DayBillERP"
        try:
            from modules.db_backup import backup_path
            folder = backup_path()
        except Exception:
            folder = r"C:\DayBillERP\Backups"
        self.error_var.set("'%s' is not a DayBill database — see Database Settings." % name)
        self.login_btn.config(text=t("login.sign_in"), state="normal")
        # v6.0.2: another way in — DayBill databases on the same server
        try:
            from modules.db_backup import list_databases_marked
            marked, _err = list_databases_marked()
            mine = [n for n, ok in marked if ok and n != name]
        except Exception:
            mine = []
        if len(mine) == 1 and messagebox.askyesno(
                "Not a DayBill database",
                "'%s' is not a DayBill database (another program's).\n\n"
                "This server has a DayBill database: '%s'.\nSwitch DayBill to '%s' now?"
                % (name, mine[0], mine[0]), parent=self.window):
            conf = load_db_config()
            conf["database"] = mine[0]
            save_db_config(conf)
            if db.connect(conf):
                self.error_var.set("Switched to '%s' — press Sign In." % mine[0])
                self._load_fy_years()
                return
        if len(mine) > 1:
            messagebox.showinfo(
                "Not a DayBill database",
                "'%s' is not a DayBill database.\n\nDayBill databases on this server:\n  •  %s"
                "\n\nPick one in Database Settings (🗂 List marks them ✓) and press Save."
                % (name, "\n  •  ".join(mine)), parent=self.window)
            try:
                DbSettingsDialog(self.window)
            except Exception:
                pass
            return
        messagebox.showwarning(
            "Not a DayBill database",
            "The database '%s' does not have DayBill's tables. It belongs to another "
            "program (for example, that program's backup was restored into it) or it "
            "is empty. DayBill did not change it.\n\n"
            "In Database Settings:\n"
            "  •  🗂 List → pick your DayBill database → Save, or\n"
            "  •  ♻ Restore Database (.bak) → your DayBill backup\n"
            "      (DayBill keeps them in %s), or\n"
            "  •  🆕 Create New Database for a new start." % (name, folder),
            parent=self.window)
        try:
            DbSettingsDialog(self.window)
        except Exception:
            pass

    def _forgot_password(self):
        ForgotPasswordDialog(self.window, self.username_var.get().strip() or "admin")

    def _verify_password(self, plain: str, stored_hash: str) -> bool:
        """Verify against bcrypt / Argon2 / PBKDF2 / legacy SHA-256."""
        try:
            from modules import permissions as _perm
            return _perm.verify_password(plain, stored_hash)
        except Exception:
            pass
        try:
            import bcrypt
            return bcrypt.checkpw(plain.encode(), stored_hash.encode())
        except Exception:
            h = hashlib.sha256(plain.encode()).hexdigest()
            return h == stored_hash

    # ── DB Settings Dialog ────────────────────────────────────
    def _open_db_settings(self):
        DbSettingsDialog(self.window)

    # ── Language Toggle ───────────────────────────────────────
    def _toggle_language(self):
        new_lang = "ar" if current_lang() == "en" else "en"
        load_language(new_lang)
        cfg.set("language", new_lang)
        cfg.save_settings()
        # Rebuild window
        self.window.destroy()
        self._build_window()

    # ── Show/hide password ────────────────────────────────────
    def _toggle_password(self):
        self.show_pass = not self.show_pass
        self.password_entry.config(show="" if self.show_pass else "●")

    def _center_window(self, w, h):
        self.window.update_idletasks()
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

    def _on_close(self):
        self.login_success = False
        self.window.destroy()


# ── DB Settings Dialog ─────────────────────────────────────────
_MARK_OK, _MARK_OTHER = "   ✓ DayBill", "   ✗ other program"


def _db_label(name, ok):
    """'DayBillERP   ✓ DayBill' for the picker (v6.0.2)."""
    return name + (_MARK_OK if ok else (_MARK_OTHER if ok is False else ""))


def _plain_db(value):
    """The database name without the ✓ / ✗ mark."""
    v = str(value or "")
    for m in (_MARK_OK, _MARK_OTHER):
        if v.endswith(m):
            v = v[:-len(m)]
    return v.strip()


class DbSettingsDialog:
    def __init__(self, parent):
        C = cfg.theme()
        config = load_db_config()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(t("settings.database"))
        self.dialog.geometry("460x420")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.configure(bg=C["content_bg"])
        self._center(460, 420)

        pad = {"padx": 30, "pady": 6}
        self._entry_map = {}

        tk.Label(self.dialog, text=f"⚙  {t('settings.database')}",
                 font=("Segoe UI", 14, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(pady=(20, 10))

        # Server — v6.0.2: 🔍 Find tries the SQL Servers on this PC and on
        # the network with the sign-in settings below
        tk.Label(self.dialog, text=t("settings.server"),
                 font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=30)
        srow = tk.Frame(self.dialog, bg=C["content_bg"])
        srow.pack(anchor="w", padx=30, pady=(2, 6))
        self.server_var = tk.StringVar(value=config.get("server", "localhost"))
        self._entry_map["server"] = self.server_var
        self.server_combo = ttk.Combobox(srow, textvariable=self.server_var,
                                         font=("Segoe UI", 10), width=26)
        self.server_combo.pack(side="left")
        tk.Button(srow, text="🔍 Find", font=("Segoe UI", 9, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat",
                  padx=8, pady=3, cursor="hand2",
                  command=self._find_servers).pack(side="left", padx=(6, 0))

        # Database — combobox so all company databases on the server can
        # be listed and picked (company change)
        tk.Label(self.dialog, text=t("settings.database_name"),
                 font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=30)
        dbrow = tk.Frame(self.dialog, bg=C["content_bg"])
        dbrow.pack(anchor="w", padx=30, pady=(2, 6))
        self.db_var = tk.StringVar(value=config.get("database", "DayBillERP"))
        self._entry_map["database"] = self.db_var
        self.db_combo = ttk.Combobox(dbrow, textvariable=self.db_var,
                                     font=("Segoe UI", 10), width=26)
        self.db_combo.pack(side="left")
        tk.Button(dbrow, text="🗂 List", font=("Segoe UI", 9, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat",
                  padx=8, pady=3, cursor="hand2",
                  command=self._list_dbs).pack(side="left", padx=(6, 0))
        # type-to-search: typing in the box filters the listed databases
        self._all_dbs = []
        self.db_combo.bind("<KeyRelease>", self._filter_dbs)
        tk.Label(self.dialog, text="Type to search · pick any company "
                 "database on this server to switch companies",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=30)

        # Auth type
        self.auth_var = tk.StringVar(value=config.get("auth_type", "windows"))
        auth_frame = tk.Frame(self.dialog, bg=C["content_bg"])
        auth_frame.pack(fill="x", **pad)
        tk.Label(auth_frame, text="Authentication", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(anchor="w")
        tk.Radiobutton(auth_frame, text=t("settings.auth_windows"),
                       variable=self.auth_var, value="windows",
                       bg=C["content_bg"], command=self._toggle_auth).pack(anchor="w")
        tk.Radiobutton(auth_frame, text=t("settings.auth_sql"),
                       variable=self.auth_var, value="sql",
                       bg=C["content_bg"], command=self._toggle_auth).pack(anchor="w")

        # SQL credentials
        self.sql_frame = tk.Frame(self.dialog, bg=C["content_bg"])
        self.sql_frame.pack(fill="x", padx=30)
        self._field(t("settings.username"), config.get("username", ""), parent=self.sql_frame, key="username")
        self._field(t("settings.password"), config.get("password", ""), parent=self.sql_frame,
                    key="password", show="*")

        self._toggle_auth()

        # Status label
        self.status_var = tk.StringVar()
        tk.Label(self.dialog, textvariable=self.status_var,
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["success"], wraplength=400).pack(pady=4)

        # Buttons
        btn_frame = tk.Frame(self.dialog, bg=C["content_bg"])
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=t("settings.test_conn"),
                  font=("Segoe UI", 10), bg=C["primary_light"], fg=C["primary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._test).pack(side="left", padx=5)

        tk.Button(btn_frame, text=t("settings.save_conn"),
                  font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._save).pack(side="left", padx=5)

        tk.Button(btn_frame, text=t("common.cancel"),
                  font=("Segoe UI", 10), bg=C["border"], fg=C["text_primary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self.dialog.destroy).pack(side="left", padx=5)

        # second row: database tools (new installation / company change)
        tools = tk.Frame(self.dialog, bg=C["content_bg"])
        tools.pack(pady=(0, 10))
        tk.Button(tools, text="♻  Restore Database (.bak)…",
                  font=("Segoe UI", 9, "bold"), bg="#8E44AD", fg="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._restore_db).pack(side="left", padx=5)
        tk.Button(tools, text="🆕  Create New Database…",
                  font=("Segoe UI", 9, "bold"), bg="#27AE60", fg="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._create_db).pack(side="left", padx=5)
        tk.Button(tools, text="💾  Backup Now",
                  font=("Segoe UI", 9, "bold"), bg="#2E86AB", fg="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._backup_now).pack(side="left", padx=5)

        self._entries = {k: v for k, v in self._entry_map.items()}

    def _filter_dbs(self, _e=None):
        """Type-to-search: narrow the database dropdown as you type."""
        if not self._all_dbs:
            return
        txt = self.db_var.get().strip().lower()
        vals = [d for d in self._all_dbs if txt in d.lower()] if txt \
            else list(self._all_dbs)
        self.db_combo["values"] = vals or self._all_dbs

    def _create_db(self):
        """New installation: create a fresh company database and run the
        all-in-one setup script into it."""
        from tkinter import simpledialog
        save_db_config(self._get_config())
        name = simpledialog.askstring(
            "Create New Database",
            "Name of the new company database (letters/numbers):",
            parent=self.dialog)
        if not name or not name.strip():
            return
        from modules import db_backup as dbb
        script = dbb.find_install_script()
        run_it = False
        if script:
            run_it = messagebox.askyesno(
                "Create New Database",
                "Also run the full setup script into it?\n\n"
                "%s\n\n(Yes = ready-to-use company with all tables. "
                "This can take a minute.)" % script, parent=self.dialog)
        self.status_var.set("⏳ Creating database — please wait…")
        self.dialog.update_idletasks()
        ok, msg = dbb.create_database(name.strip(),
                                      install_script=script if run_it else None)
        self.status_var.set(("✅ " if ok else "❌ ") + msg[:180])
        if ok:
            self._list_dbs()
            self.db_var.set("".join(ch for ch in name.strip()
                                    if ch.isalnum() or ch in "_-"))
            messagebox.showinfo("Create New Database",
                                msg + "\n\nPick it in the Database box and "
                                "press Save to switch to the new company.",
                                parent=self.dialog)

    def _backup_now(self):
        save_db_config(self._get_config())
        try:
            from modules import db_backup as dbb
            okp, pmsg = dbb.check_backup_path()
            if not okp:
                self.status_var.set("❌ Backup path: " + str(pmsg)[:160])
                return
            self.status_var.set("⏳ Backing up — please wait…")
            self.dialog.update_idletasks()
            ok, msg = dbb.backup_now(note="manual")
            self.status_var.set(("✅ " if ok else "❌ ") + str(msg)[:180])
        except Exception as e:
            self.status_var.set("❌ " + str(e)[:180])

    def _list_dbs(self):
        """Load every company database on this server into the picker —
        v6.0.2: DayBill's are marked ✓ (and come first), another program's ✗."""
        save_db_config(self._get_config())     # so the lister uses this server
        try:
            from modules.db_backup import list_databases_marked
            marked, err = list_databases_marked()
        except Exception as e:
            marked, err = [], str(e)[:200]
        if err:
            self.status_var.set("❌ " + err)
            return
        labels = [_db_label(n, ok) for n, ok in marked]
        self._all_dbs = list(labels)
        self.db_combo["values"] = labels
        n_day = sum(1 for _n, ok in marked if ok)
        n_other = sum(1 for _n, ok in marked if ok is False)
        self.status_var.set("✅ %d database(s): %d DayBill ✓%s — pick a ✓ one and Save."
                            % (len(marked), n_day,
                               (", %d other program ✗" % n_other) if n_other else ""))
        if labels:
            try:
                self.db_combo.event_generate("<Button-1>")
            except Exception:
                pass

    def _find_servers(self):
        """v6.0.2 — another way to connect: try the SQL Servers on this PC
        (Windows registry), the usual names and the ones that answer on the
        network, with the sign-in settings shown; list the ones that work."""
        import threading
        conf = self._get_config()
        self.status_var.set("🔍 Looking for SQL Server on this PC and the network…")
        box = {"done": False, "found": [], "msg": ""}

        def work():
            try:
                from modules.db_finder import find_servers
                box["found"] = find_servers(conf, progress=lambda m: box.__setitem__("msg", m))
            except Exception as e:
                box["msg"] = str(e)[:150]
            box["done"] = True

        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                if not self.dialog.winfo_exists():
                    return
            except Exception:
                return
            if not box["done"]:
                if box["msg"]:
                    self.status_var.set("🔍 " + box["msg"])
                self.dialog.after(150, poll)
                return
            found = box["found"]
            if not found:
                self.status_var.set("❌ No SQL Server let us in with these sign-in settings. Is the "
                                    "SQL Server service running (Windows ▸ Services ▸ SQL Server)? "
                                    "Try the other Authentication.")
                return
            names = [n for n, _v in found]
            self.server_combo["values"] = names
            if self.server_var.get().strip().lower() not in [n.lower() for n in names]:
                self.server_var.set(names[0])
            self.status_var.set("✅ SQL Server found: %s — now 🗂 List the databases."
                                % ", ".join(names))

        poll()
        return box

    def _restore_db(self):
        """Restore a .bak backup as the selected database name — used for
        a NEW installation or bringing in another company's data.
        v6.0.1: the backup is looked at first; another program's backup is
        never put over an existing database, and the database that is
        replaced is first saved as a safety copy."""
        from tkinter import filedialog, messagebox
        bak = filedialog.askopenfilename(
            parent=self.dialog, title="Choose SQL backup (.bak)",
            filetypes=[("SQL Server backup", "*.bak"), ("All files", "*.*")])
        if not bak:
            return
        target = _plain_db(self.db_var.get()) or "DayBillERP"
        if not messagebox.askyesno(
                "Restore Database",
                "Restore\n%s\ninto database '%s'?\n\nIf '%s' already exists "
                "it will be REPLACED with the backup's data (a safety copy of it "
                "is saved first)." % (bak, target, target), parent=self.dialog):
            return
        try:
            before = (load_db_config() or {}).get("database") or ""
        except Exception:
            before = ""
        save_db_config(self._get_config())

        def say(txt):
            self.status_var.set("♻ " + txt)
            try:
                self.dialog.update_idletasks()
            except Exception:
                pass

        def ask(question):
            return messagebox.askyesno("Restore Database", question, parent=self.dialog)

        try:
            from modules.db_backup import safe_restore
            ok, msg, kind = safe_restore(bak, target, ask=ask, say=say)
        except Exception as e:
            ok, msg, kind = False, str(e)[:250], None
        if (not ok or kind == "foreign") and before and before != target:
            back = self._get_config()           # DayBill stays on its own database
            back["database"] = before
            save_db_config(back)
            self.db_var.set(before)
            msg += "\n\nDayBill stays on '%s'." % before
        self.status_var.set(("✅ " if ok else "❌ ") + msg.split("\n")[0])
        (messagebox.showinfo if ok else messagebox.showwarning)(
            "Restore Database", msg, parent=self.dialog)

    def _field(self, label, default="", parent=None, key=None, show=None):
        C = cfg.theme()
        p = parent or self.dialog
        tk.Label(p, text=label, font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(anchor="w")
        var = tk.StringVar(value=default)
        e = tk.Entry(p, textvariable=var, font=("Segoe UI", 10),
                     bg="white", relief="solid", bd=1, width=36)
        if show:
            e.config(show=show)
        e.pack(anchor="w", pady=(2, 6))
        if key:
            self._entry_map[key] = var
        return var

    def _toggle_auth(self):
        if self.auth_var.get() == "windows":
            self.sql_frame.pack_forget()
        else:
            self.sql_frame.pack(fill="x", padx=30)

    def _get_config(self) -> dict:
        em = getattr(self, "_entry_map", {})
        server = (em.get("server").get().strip()
                  if em.get("server") else "") or "localhost\\SQLEXPRESS"
        database = (_plain_db(em.get("database").get())
                    if em.get("database") else "") or "DayBillERP"
        return {
            "server":    server,
            "database":  database,
            "auth_type": self.auth_var.get(),
            "username":  em.get("username").get() if "username" in em else "",
            "password":  em.get("password").get() if "password" in em else "",
            "driver":    "ODBC Driver 17 for SQL Server",
            "timeout":   30
        }

    def _test(self):
        config = self._get_config()
        ok, msg = db.test_connection(config)
        C = cfg.theme()
        color = C["success"] if ok else C["danger"]
        self.status_var.set(f"{'✅' if ok else '❌'} {msg}")

    def _save(self):
        config = self._get_config()
        save_db_config(config)
        ok = db.connect(config)
        C = cfg.theme()
        if ok and db.is_daybill() is False:       # v6.0.1
            self.status_var.set("⚠ Connected, but '%s' is not a DayBill database — pick your "
                                "DayBill database (🗂 List)." % config.get("database"))
            return
        if ok:
            self.status_var.set("✅ Saved & Connected!")
            self.dialog.after(1500, self.dialog.destroy)
        else:
            self.status_var.set("❌ Saved but connection failed.")

    def _center(self, w, h):
        self.dialog.update_idletasks()
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        self.dialog.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ============================================================
# First-run: set the admin password (setup script only ships a
# placeholder that can never match any password)
# ============================================================
def reset_query(database, username):
    """v6.0.2: the SQL a dealer / IT person runs in SQL Server Management
    Studio when nobody can sign in. It changes NOTHING on a database that
    isn't DayBill's. Afterwards that user signs in with any password and
    DayBill asks for a new one (the same as a new installation)."""
    dbn = str(database or "DayBillERP").replace("]", "]]")
    u = str(username or "admin").replace("'", "''")
    return ("USE [%s];\n"
            "IF COL_LENGTH('users','user_id') IS NULL OR OBJECT_ID('sales_invoices') IS NULL\n"
            "    RAISERROR('This is not a DayBill database - nothing was changed.', 16, 1);\n"
            "ELSE\n"
            "BEGIN\n"
            "    UPDATE users SET password_hash = N'RESET', is_active = 1 WHERE username = N'%s';\n"
            "    IF OBJECT_ID('login_history') IS NOT NULL\n"
            "        DELETE FROM login_history WHERE username = N'%s' AND success = 0;\n"
            "    SELECT username, is_active FROM users WHERE username = N'%s';\n"
            "END\n" % (dbn, u, u, u))


class ForgotPasswordDialog:
    """🔑 Forgot password? (login screen, v6.0.2) — the two safe ways back in."""
    def __init__(self, parent, username="admin"):
        C = cfg.theme()
        try:
            self.database = (load_db_config() or {}).get("database") or "DayBillERP"
        except Exception:
            self.database = "DayBillERP"
        self.win = tk.Toplevel(parent)
        self.win.title("Forgot password")
        self.win.configure(bg=C["content_bg"])
        self.win.transient(parent)
        self.win.resizable(False, False)
        tk.Label(self.win, text="🔑  Forgot password?", font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white", pady=10).pack(fill="x")
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(padx=22, pady=12, fill="x")

        def para(txt, bold=False, color=None):
            tk.Label(body, text=txt, font=("Segoe UI", 9, "bold" if bold else "normal"),
                     bg=C["content_bg"], fg=color or C["text_primary"], justify="left",
                     wraplength=520).pack(anchor="w", pady=(0, 4))

        para("1.  Another administrator can give you a new password:", bold=True)
        para("     System ▸ Users & Rights → pick the user → 🔑 Reset Password.")
        para("2.  Nobody can sign in?  On the server PC open SQL Server Management Studio, "
             "connect, click New Query and run this:", bold=True)
        urow = tk.Frame(body, bg=C["content_bg"]); urow.pack(anchor="w", pady=(2, 4))
        tk.Label(urow, text="User name", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.user_var = tk.StringVar(value=username or "admin")
        e = tk.Entry(urow, textvariable=self.user_var, font=("Segoe UI", 10), width=18,
                     relief="solid", bd=1)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda _e: self._fill())
        self.txt = tk.Text(body, height=12, width=78, font=("Consolas", 9), relief="solid", bd=1,
                           bg="#F8FAFC", fg="#0F172A", wrap="word")
        self.txt.pack(fill="x", pady=(2, 6))
        para("Then sign in as that user with any password — DayBill asks for a new password "
             "first. The same query is in the DayBill folder: database\\RESET_user_password.sql. "
             "It changes nothing on a database that isn't DayBill's.",
             color=C["text_secondary"])
        try:
            if db.is_daybill() is False:
                para("⚠  DayBill is now set to '%s', which is NOT a DayBill database — fix it in "
                     "Database Settings first (🗂 List marks DayBill's ✓)." % self.database,
                     bold=True, color=C["danger"])
        except Exception:
            pass
        bar = tk.Frame(body, bg=C["content_bg"]); bar.pack(fill="x", pady=(6, 0))
        self.copied = tk.StringVar()
        tk.Label(bar, textvariable=self.copied, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["success"]).pack(side="left")
        tk.Button(bar, text="Close", font=("Segoe UI", 10), relief="flat", padx=12, pady=6,
                  command=self.win.destroy).pack(side="right")
        tk.Button(bar, text="📋 Copy the query", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._copy).pack(side="right", padx=6)
        self._fill()
        self.win.bind("<Escape>", lambda _e: self.win.destroy())
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")

    def query(self):
        return reset_query(self.database, self.user_var.get().strip() or "admin")

    def _fill(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", self.query())
        self.txt.configure(state="disabled")

    def _copy(self):
        try:
            self.win.clipboard_clear()
            self.win.clipboard_append(self.query())
            self.copied.set("✓ Copied")
        except Exception as e:
            self.copied.set(str(e)[:60])


class FirstPasswordDialog:
    def __init__(self, parent, username, expired_days=None):
        C = cfg.theme()
        self.password = None
        self.win = tk.Toplevel(parent)
        self.win.title("Set password")
        self.win.configure(bg=C["content_bg"])
        self.win.transient(parent)
        self.win.resizable(False, False)
        tk.Label(self.win, text=("🔐  Password expired — choose a new one"
                                 if expired_days is not None else
                                 "🔐  Welcome — set your password"),
                 font=("Segoe UI", 13, "bold"), bg=C["primary"], fg="white",
                 pady=10).pack(fill="x")
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(padx=24, pady=14)
        try:
            n = int(float(cfg.get("pwd_min_length", 4) or 4))
        except Exception:
            n = 4
        self.min_len = max(4, n)
        tk.Label(body, text=(f"The password of '{username}' is {expired_days} days old.\n"
                             f"Choose a new one — at least {self.min_len} characters."
                             if expired_days is not None else
                             f"'{username}' has no password (new installation, or it was\n"
                             f"reset). Choose one now — at least {self.min_len} characters."),
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"],
                 justify="left").pack(anchor="w", pady=(0, 10))
        self.p1, self.p2 = tk.StringVar(), tk.StringVar()
        for lbl, var in (("New password", self.p1), ("Type it again", self.p2)):
            tk.Label(body, text=lbl, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                     fg=C["text_primary"]).pack(anchor="w")
            e = tk.Entry(body, textvariable=var, show="●", font=("Segoe UI", 11),
                         width=28, relief="solid", bd=1)
            e.pack(fill="x", ipady=4, pady=(2, 8))
            if var is self.p1:
                e.focus_set()
        self.msg = tk.StringVar()
        tk.Label(body, textvariable=self.msg, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["danger"]).pack(anchor="w")
        bar = tk.Frame(body, bg=C["content_bg"]); bar.pack(fill="x", pady=(8, 0))
        tk.Button(bar, text="Save password", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._ok).pack(side="right")
        tk.Button(bar, text="Cancel", font=("Segoe UI", 10), relief="flat",
                  padx=12, pady=6, command=self.win.destroy).pack(side="right", padx=6)
        self.win.bind("<Return>", lambda e: self._ok())
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")
        try:
            self.win.grab_set()
        except Exception:
            pass

    def _ok(self):
        a, b = self.p1.get(), self.p2.get()
        if len(a) < self.min_len:
            self.msg.set(f"At least {self.min_len} characters, please."); return
        if a != b:
            self.msg.set("The two passwords are different."); return
        self.password = a
        self.win.destroy()
