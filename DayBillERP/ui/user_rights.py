# ============================================================
# DayBill ERP — User Management & User Rights (RBAC) UI
# ------------------------------------------------------------
# Two tabs:
#   • Users        — list, search, filter by role, New/Save/Edit/
#                    Delete/Refresh/Reset Password, login history
#   • User Rights  — role picker + permission matrix (modules ×
#                    actions) with Check All / Uncheck All /
#                    Copy from another role
#
# Every action is gated by modules.permissions.can(...) so an
# unauthorized user can open neither the tab buttons nor the
# destructive actions.
# v6.9.3: only a full-access user (Super Admin / Admin) may give a
# full-access user type, change / delete a full-access user or reset
# their password; nobody can tick a right they don't have themselves.
# F2 / F5 work only on this screen (bound on its own widgets).
# ============================================================

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import permissions as perm
from modules import audit


def _me():
    return (perm._session.get("user") or {})


def _full_access_role_ids():
    try:
        return {r["role_id"] for r in db.fetchall("SELECT role_id, role_name_en FROM roles") or []
                if (r["role_name_en"] or "").strip().lower() in perm.FULL_ACCESS_ROLES}
    except Exception:
        return set()


def _other_active_admins(exclude_user_id):
    """How many OTHER active users can still manage users & rights?"""
    try:
        ids = _full_access_role_ids()
        rows = db.fetchall("SELECT user_id, username, role_id FROM users WHERE is_active=1") or []
        return sum(1 for r in rows if r["user_id"] != exclude_user_id and
                   (r["role_id"] in ids or str(r["username"]).lower() == "admin"))
    except Exception:
        return 1


def _bind_on_screen(widget, seq, fn):
    """Bind a key on this screen's OWN widgets (not on the main window), so
    it never fires on another screen; "break" stops the global shortcut."""
    def h(e):
        fn()
        return "break"

    def walk(w):
        if isinstance(w, tk.Toplevel):          # a dialog opened from here
            return
        try:
            w.bind(seq, h)
        except Exception:
            pass
        for c in w.winfo_children():
            walk(c)
    walk(widget)


def _admin_problem(user_id=None, role_id=None, username=None):
    """'' or why only an administrator may do this (see ui/users.py)."""
    try:
        from ui.users import admin_only_problem
        return admin_only_problem(user_id=user_id, role_id=role_id, username=username)
    except Exception as e:
        return "Could not check the user: %s" % str(e)[:100]


def _modal(win, parent):
    """Dialog stays on top of its screen and blocks it until closed."""
    try:
        win.transient(parent.winfo_toplevel())
    except Exception:
        pass
    win.grab_set()


# ============================================================
#  Top-level view with the two tabs
# ============================================================
class UserRightsView:
    def __init__(self, parent):
        C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.C = C

        # make sure the catalogue + role defaults exist
        try:
            perm.bootstrap_roles_and_permissions()
        except Exception:
            pass

        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(18, 0))
        tk.Label(bar, text="🔐  Users & Rights", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("UR.TNotebook", background=C["content_bg"], borderwidth=0)
        style.configure("UR.TNotebook.Tab", font=("Segoe UI", 10, "bold"),
                        padding=(16, 8))
        nb = ttk.Notebook(self.frame, style="UR.TNotebook")
        nb.pack(fill="both", expand=True, padx=24, pady=14)

        self.t_users = tk.Frame(nb, bg=C["content_bg"])
        self.t_rights = tk.Frame(nb, bg=C["content_bg"])
        nb.add(self.t_users, text="  👤 Users  ")
        # only show the rights matrix to those who may manage it
        self._can_rights = perm.can("user_rights", "view")
        if self._can_rights:
            nb.add(self.t_rights, text="  🧩 User Rights  ")

        UsersPanel(self.t_users, C)
        if self._can_rights:
            RightsMatrixPanel(self.t_rights, C)


# ============================================================
#  Users tab
# ============================================================
class UsersPanel:
    def __init__(self, parent, C):
        self.parent = parent
        self.C = C
        self._roles = []
        self._build()
        self._load_roles()
        self._load()
        self._bind_keys()

    # ── build ──────────────────────────────────────────────
    def _build(self):
        C = self.C
        top = tk.Frame(self.parent, bg=C["content_bg"])
        top.pack(fill="x", pady=(10, 8))

        # search
        sf = tk.Frame(top, bg="white", highlightbackground=C["border"],
                      highlightthickness=1)
        sf.pack(side="left")
        tk.Label(sf, text="🔍", bg="white", font=("Segoe UI Emoji", 11)).pack(
            side="left", padx=(8, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._load())
        tk.Entry(sf, textvariable=self.search_var, font=("Segoe UI", 10),
                 bg="white", relief="flat", width=24).pack(side="left", ipady=6,
                 padx=(0, 8))

        # filter by role
        tk.Label(top, text="Role:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(14, 4))
        self.filter_var = tk.StringVar(value="All roles")
        self.filter_cb = ttk.Combobox(top, textvariable=self.filter_var,
                                      state="readonly", font=("Segoe UI", 9),
                                      width=16)
        self.filter_cb.pack(side="left")
        self.filter_cb.bind("<<ComboboxSelected>>", lambda e: self._load())

        # action buttons (right)
        def btn(txt, cmd, primary=False, danger=False, enabled=True):
            bg = C["primary"] if primary else ("#FEF2F2" if danger else C["card_bg"])
            fg = "white" if primary else (C["danger"] if danger else C["text_primary"])
            state = "normal" if enabled else "disabled"
            b = tk.Button(top, text=txt, font=("Segoe UI", 9, "bold"),
                          bg=bg, fg=fg, relief="flat", padx=12, pady=6,
                          cursor="hand2", state=state,
                          highlightbackground=C["border"], highlightthickness=1,
                          command=cmd)
            b.pack(side="right", padx=(0, 6))
            return b

        can_add = perm.can("users", "add")
        can_edit = perm.can("users", "edit")
        can_del = perm.can("users", "delete")
        btn("➕ New  (F2)", self._new, primary=True, enabled=can_add)
        btn("✏ Edit", self._edit, enabled=can_edit)
        btn("🗑 Delete", self._delete, danger=True, enabled=can_del)
        btn("🔑 Reset Password", self._reset_pw, enabled=can_edit)
        btn("🔄 Refresh", self._load)
        btn("🕓 Login History", self._login_history)

        # table
        card = tk.Frame(self.parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("id", "username", "name", "role", "mobile", "email",
                "branch", "status", "last_login")
        heads = {"id": ("ID", 45), "username": ("Username", 120),
                 "name": ("Full Name", 170), "role": ("Role", 110),
                 "mobile": ("Mobile", 100), "email": ("Email", 150),
                 "branch": ("Branch", 90), "status": ("Status", 80),
                 "last_login": ("Last Login", 130)}
        style = ttk.Style()
        style.configure("URU.Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("URU.Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background=C.get("heading_bg", C["content_bg"]), foreground="#374151")
        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 style="URU.Treeview", selectmode="browse",
                                 yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for c in cols:
            txt, w = heads[c]
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w,
                             anchor="center" if c in ("id", "status") else "w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.tag_configure("inactive", foreground="#9CA3AF")
        if perm.can("users", "edit"):
            self.tree.bind("<Double-1>", lambda e: self._edit())

        self.count_var = tk.StringVar()
        tk.Label(self.parent, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w",
                 pady=(4, 0))

    def _bind_keys(self):
        _bind_on_screen(self.parent, "<F2>",
                        lambda: self._new() if perm.can("users", "add") else None)
        _bind_on_screen(self.parent, "<F5>", self._load)

    # ── data ───────────────────────────────────────────────
    def _load_roles(self):
        try:
            self._roles = db.fetchall(
                "SELECT role_id, role_name_en FROM roles WHERE is_active=1 "
                "ORDER BY role_id") or []
        except Exception:
            self._roles = []
        names = ["All roles"] + [r["role_name_en"] for r in self._roles]
        self.filter_cb.configure(values=names)

    def _has_col(self, col):
        try:
            return bool(db.execute_scalar(
                "SELECT COUNT(*) FROM sys.columns WHERE object_id="
                "OBJECT_ID('users') AND name=?", (col,)))
        except Exception:
            return False

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        q = self.search_var.get().lower().strip()
        role_filter = self.filter_var.get()
        # build column list defensively (mobile/branch may be un-migrated)
        opt_cols = []
        for c in ("mobile", "branch", "warehouse"):
            opt_cols.append(c if self._has_col(c) else "NULL AS " + c)
        try:
            rows = db.fetchall(
                "SELECT u.user_id, u.username, u.full_name_en, u.is_active, "
                "u.last_login, r.role_name_en, " + ", ".join(
                    "u." + c if " AS " not in c else c for c in opt_cols) +
                ", ISNULL(u.email,'') AS email "
                "FROM users u LEFT JOIN roles r ON u.role_id=r.role_id "
                "ORDER BY u.user_id") or []
        except Exception as e:
            messagebox.showerror("Users", str(e)[:200]); return
        shown = 0
        for r in rows:
            role = r.get("role_name_en") or "—"
            if role_filter != "All roles" and role != role_filter:
                continue
            hay = (str(r.get("username", "")) + str(r.get("full_name_en", "")) +
                   str(r.get("email", ""))).lower()
            if q and q not in hay:
                continue
            ll = r.get("last_login")
            ll_txt = ll.strftime("%Y-%m-%d %H:%M") if hasattr(ll, "strftime") \
                else (str(ll)[:16] if ll else "—")
            active = r.get("is_active", 1)
            self.tree.insert("", "end", iid=str(r["user_id"]), values=(
                r["user_id"], r.get("username", ""), r.get("full_name_en", ""),
                role, r.get("mobile") or "", r.get("email") or "",
                r.get("branch") or "", "Active" if active else "Inactive",
                ll_txt), tags=() if active else ("inactive",))
            shown += 1
        self.count_var.set(f"{shown} user(s)")

    def _sel_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # ── actions ────────────────────────────────────────────
    def _new(self):
        if not perm.can("users", "add"):
            return self._deny()
        UserForm(self.parent, self._roles, on_save=self._load)

    def _edit(self):
        if not perm.can("users", "edit"):
            return self._deny()
        uid = self._sel_id()
        if not uid:
            messagebox.showinfo("Select", "Select a user first."); return
        prob = _admin_problem(user_id=uid)
        if prob:
            messagebox.showwarning("Edit User", prob, parent=self.parent); return
        UserForm(self.parent, self._roles, user_id=uid, on_save=self._load)

    def _delete(self):
        if not perm.can("users", "delete"):
            return self._deny()
        uid = self._sel_id()
        if not uid:
            messagebox.showinfo("Select", "Select a user first."); return
        u = db.fetchone("SELECT username, role_id FROM users WHERE user_id=?", (uid,))
        uname = (u or {}).get("username", str(uid))
        if str(uname).lower() == "admin":
            messagebox.showwarning("Delete User",
                                   "The built-in 'admin' user cannot be deleted.")
            return
        if uid == _me().get("user_id"):
            messagebox.showwarning("Delete User", "You can't delete yourself while "
                                   "signed in.")
            return
        prob = _admin_problem(user_id=uid)
        if prob:
            messagebox.showwarning("Delete User", prob, parent=self.parent)
            return
        if (u or {}).get("role_id") in _full_access_role_ids() and \
                _other_active_admins(uid) == 0:
            messagebox.showwarning("Delete User", "This is the last administrator — "
                                   "keep at least one user who can manage users.")
            return
        if not messagebox.askyesno(
                "Delete User",
                f"Delete user '{uname}'?\nThis cannot be undone. Consider "
                "deactivating instead to keep history."):
            return
        try:
            try:
                db.execute("DELETE FROM login_history WHERE user_id=?", (uid,))
            except Exception:
                pass
            db.execute("DELETE FROM users WHERE user_id=?", (uid,))
            audit.log("delete", "users", uid, str(uname))
            self._load()
        except Exception as e:
            err = str(e).lower()
            if "reference" in err or "foreign key" in err or "547" in err:
                # user is linked to invoices / payments → keep, just switch off
                if messagebox.askyesno(
                        "Delete User",
                        f"'{uname}' has invoices or other records, so it can't be "
                        "deleted (the history would lose its author).\n\n"
                        "Deactivate the user instead? They won't be able to sign in."):
                    db.execute("UPDATE users SET is_active=0 WHERE user_id=?", (uid,))
                    audit.log("deactivate", "users", uid, str(uname))
                    self._load()
            else:
                messagebox.showerror("Delete User", str(e)[:200])

    def _reset_pw(self):
        if not perm.can("users", "edit"):
            return self._deny()
        uid = self._sel_id()
        if not uid:
            messagebox.showinfo("Select", "Select a user first."); return
        prob = _admin_problem(user_id=uid)           # an admin's password: admins only
        if prob:
            messagebox.showwarning("Reset Password", prob, parent=self.parent); return
        from ui.users import password_problem
        _n = int(float(cfg.get("pwd_min_length", 4) or 4))
        pw = simpledialog.askstring("Reset Password",
                                    f"New password (min {_n} chars):",
                                    parent=self.parent, show="*")
        if not pw:
            return
        prob = password_problem(pw)          # Settings ▸ Users & Security
        if prob:
            messagebox.showwarning("Reset Password", prob)
            return
        try:
            db.execute("UPDATE users SET password_hash=?, updated_at=GETDATE() "
                       "WHERE user_id=?", (perm.hash_password(pw), uid))
            perm.mark_password_changed(uid)
            audit.log("reset_password", "users", uid)
            messagebox.showinfo("Reset Password", "Password updated.")
        except Exception as e:
            messagebox.showerror("Reset Password", str(e)[:200])

    def _login_history(self):
        LoginHistoryDialog(self.parent)

    def _deny(self):
        messagebox.showwarning("Access Denied",
                               "You don't have permission for that action.")


# ============================================================
#  User add/edit form
# ============================================================
class UserForm:
    def __init__(self, parent, roles, user_id=None, on_save=None):
        self.user_id = user_id
        self.roles = roles
        self.on_save = on_save
        C = cfg.theme()
        self.C = C

        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("Edit User" if user_id else "New User")
        self.win.configure(bg=C["content_bg"])
        _modal(self.win, parent)
        self._center(520, 640)

        tk.Label(self.win, text=("✏️  Edit User" if user_id else "➕  New User"),
                 font=("Segoe UI", 14, "bold"), bg=C["primary"], fg="white",
                 pady=10).pack(fill="x")

        body = tk.Frame(self.win, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=22, pady=10)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(3, weight=1)

        self.f = {}
        r = 0

        def entry(label, key, row, col=0, show=None, width=None):
            tk.Label(body, text=label, font=("Segoe UI", 9),
                     bg=C["content_bg"], fg=C["text_secondary"]).grid(
                row=row, column=col, sticky="w", pady=(6, 0), padx=(0, 6))
            v = tk.StringVar(); self.f[key] = v
            e = tk.Entry(body, textvariable=v, font=("Segoe UI", 10), bg="white",
                         relief="solid", bd=1, show=show)
            e.grid(row=row + 1, column=col, sticky="ew", ipady=4, padx=(0, 10))
            return v

        # User ID (auto, read-only display)
        tk.Label(body, text="User ID", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).grid(row=r, column=0, sticky="w",
                 pady=(6, 0))
        self.id_var = tk.StringVar(value=str(user_id) if user_id else "(auto)")
        tk.Entry(body, textvariable=self.id_var, font=("Segoe UI", 10),
                 bg="#EFEDF8", relief="solid", bd=1, state="readonly").grid(
            row=r + 1, column=0, sticky="ew", ipady=4, padx=(0, 10))

        entry("Full Name *", "full_name_en", r, col=1)
        r += 2
        entry("Username *", "username", r, col=0)
        entry("Mobile", "mobile", r, col=1)
        r += 2
        entry("Email", "email", r, col=0)

        # Status
        tk.Label(body, text="Status", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).grid(row=r, column=1, sticky="w",
                 pady=(6, 0))
        self.active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(body, text="Active", variable=self.active_var,
                       font=("Segoe UI", 10), bg=C["content_bg"],
                       activebackground=C["content_bg"]).grid(
            row=r + 1, column=1, sticky="w")
        r += 2

        # Role
        tk.Label(body, text="Role *", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).grid(row=r, column=0, sticky="w",
                 pady=(6, 0))
        self.role_var = tk.StringVar()
        self.role_cb = ttk.Combobox(body, textvariable=self.role_var,
                                    values=[x["role_name_en"] for x in roles],
                                    state="readonly", font=("Segoe UI", 10))
        self.role_cb.grid(row=r + 1, column=0, sticky="ew", ipady=2, padx=(0, 10))

        entry("Branch", "branch", r, col=1)
        r += 2
        entry("Warehouse", "warehouse", r, col=0)
        r += 2

        # Password
        entry("Password " + ("(blank = keep)" if user_id else "*"),
              "password", r, col=0, show="●")
        entry("Confirm Password", "password2", r, col=1, show="●")
        r += 2

        # meta (edit only)
        self.meta_var = tk.StringVar()
        tk.Label(body, textvariable=self.meta_var, font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"]).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
        r += 1

        self.status = tk.StringVar()
        tk.Label(body, textvariable=self.status, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["danger"], wraplength=460,
                 justify="left").grid(row=r, column=0, columnspan=2,
                 sticky="w", pady=(6, 0))

        bb = tk.Frame(self.win, bg=C["card_bg"]); bb.pack(fill="x", side="bottom")
        bi = tk.Frame(bb, bg=C["card_bg"]); bi.pack(fill="x", padx=22, pady=10)
        tk.Button(bi, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self.win.destroy).pack(
            side="right", padx=(8, 0))
        tk.Button(bi, text="💾 Save  (F4)", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=18, pady=6,
                  cursor="hand2", command=self._save).pack(side="right")
        self.win.bind("<F4>", lambda e: self._save())

        if user_id:
            self._load()
        elif roles:
            self.role_cb.current(0)

    def _load(self):
        try:
            u = db.fetchone("SELECT * FROM users WHERE user_id=?", (self.user_id,))
            if not u:
                return
            for k in ("username", "full_name_en", "email", "mobile",
                      "branch", "warehouse"):
                if u.get(k) is not None:
                    if k in self.f:
                        self.f[k].set(str(u[k]))
            self.active_var.set(bool(u.get("is_active", 1)))
            for x in self.roles:
                if x["role_id"] == u.get("role_id"):
                    self.role_var.set(x["role_name_en"]); break
            created = u.get("created_at")
            created_txt = created.strftime("%Y-%m-%d") if hasattr(created, "strftime") \
                else str(created or "")[:10]
            cb = u.get("created_by")
            self.meta_var.set("Created %s%s" % (
                created_txt, ("  ·  by user #%s" % cb) if cb else ""))
        except Exception as e:
            self.status.set(str(e)[:120])

    def _save(self):
        if not perm.allowed("users", "edit" if self.user_id else "add", parent=self.win):
            return
        username = self.f["username"].get().strip()
        name = self.f["full_name_en"].get().strip()
        if not username or not name:
            self.status.set("Username and Full Name are required."); return
        role_id = None
        for x in self.roles:
            if x["role_name_en"] == self.role_var.get():
                role_id = x["role_id"]; break
        if not role_id:
            self.status.set("Please choose a role."); return
        # v6.9.3: no privilege escalation — admin accounts / types are for admins
        prob = _admin_problem(user_id=self.user_id, role_id=role_id, username=username)
        if prob:
            self.status.set(prob); return
        pw = self.f["password"].get()
        pw2 = self.f["password2"].get()
        if pw or pw2:
            if pw != pw2:
                self.status.set("Passwords do not match."); return
            from ui.users import password_problem
            prob = password_problem(pw)      # Settings ▸ Users & Security
            if prob:
                self.status.set(prob); return

        # only include optional columns that exist in the DB
        def has(c):
            try:
                return bool(db.execute_scalar(
                    "SELECT COUNT(*) FROM sys.columns WHERE object_id="
                    "OBJECT_ID('users') AND name=?", (c,)))
            except Exception:
                return False

        # ── lock-out protection ──
        if self.user_id:
            cur = db.fetchone("SELECT username, role_id, is_active FROM users "
                              "WHERE user_id=?", (self.user_id,)) or {}
            if str(cur.get("username", "")).lower() == "admin" and username.lower() != "admin":
                self.status.set("The built-in 'admin' username can't be renamed "
                                "(it is the recovery login)."); return
            if str(cur.get("username", "")).lower() == "admin" and not self.active_var.get():
                self.status.set("The built-in 'admin' user can't be switched off."); return
            if self.user_id == _me().get("user_id") and not self.active_var.get():
                self.status.set("You can't switch off your own account."); return
            admin_ids = _full_access_role_ids()
            was_admin = cur.get("role_id") in admin_ids and cur.get("is_active", 1)
            stays_admin = role_id in admin_ids and self.active_var.get()
            if was_admin and not stays_admin and _other_active_admins(self.user_id) == 0:
                self.status.set("This is the last administrator — keep at least one "
                                "active user with an Admin role."); return
            if self.user_id == _me().get("user_id") and was_admin and not stays_admin:
                if not messagebox.askyesno(
                        "Your own rights",
                        "You are removing your OWN administrator rights. You may lose "
                        "access to Users & Rights. Continue?", parent=self.win):
                    return

        fields = {
            "username": username,
            "full_name_en": name,
            "email": self.f["email"].get().strip() or None,
            "role_id": role_id,
            "is_active": 1 if self.active_var.get() else 0,
        }
        for opt in ("mobile", "branch", "warehouse"):
            if has(opt):
                fields[opt] = self.f[opt].get().strip() or None

        try:
            if self.user_id:
                if pw:
                    fields["password_hash"] = perm.hash_password(pw)
                sets = ", ".join(f"{k}=?" for k in fields)
                db.execute(f"UPDATE users SET {sets}, updated_at=GETDATE() "
                           f"WHERE user_id=?",
                           (*fields.values(), self.user_id))
                audit.log("update", "users", self.user_id, username)
            else:
                if not pw:
                    self.status.set("Password is required for a new user."); return
                fields["password_hash"] = perm.hash_password(pw)
                if has("created_by"):
                    me = (perm._session.get("user") or {}).get("user_id")
                    if me:
                        fields["created_by"] = me
                cols = ", ".join(fields.keys())
                qs = ", ".join("?" for _ in fields)
                db.execute(f"INSERT INTO users ({cols}) VALUES ({qs})",
                           tuple(fields.values()))
                audit.log("create", "users", None, username)
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err or "duplicate" in err.lower():
                self.status.set("That username already exists.")
            else:
                self.status.set(err[:120])

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ============================================================
#  Permission matrix (role × module × action)
# ============================================================
class RightsMatrixPanel:
    def __init__(self, parent, C):
        self.parent = parent
        self.C = C
        self.role_id = None
        self.vars = {}          # (module_key, action_key) -> BooleanVar
        self._roles = []
        self._cbs = []
        self._dirty = False
        self._loading = False
        self._can_edit = perm.can("user_rights", "edit") or \
            perm.can("user_rights", "settings")
        self._build()
        self._load_roles()

    def _build(self):
        C = self.C
        top = tk.Frame(self.parent, bg=C["content_bg"])
        top.pack(fill="x", pady=(10, 6))
        tk.Label(top, text="User type:", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        self.role_var = tk.StringVar()
        self.role_cb = ttk.Combobox(top, textvariable=self.role_var,
                                    state="readonly", font=("Segoe UI", 10),
                                    width=22)
        self.role_cb.pack(side="left", padx=(6, 6))
        self.role_cb.bind("<<ComboboxSelected>>", lambda e: self._on_role_pick())
        if self._can_edit:
            for txt, cmd in (("＋ New type", self._new_role), ("✎ Rename", self._rename_role),
                             ("🗑", self._delete_role)):
                tk.Button(top, text=txt, font=("Segoe UI", 8), bg=C["card_bg"],
                          fg=C["primary"], relief="flat", padx=8, pady=4, cursor="hand2",
                          highlightbackground=C["border"], highlightthickness=1,
                          command=cmd).pack(side="left", padx=2)
            tk.Frame(top, bg=C["border"], width=1).pack(side="left", fill="y",
                                                        padx=10, pady=2)

        if self._can_edit:
            tk.Button(top, text="✓ Check All", font=("Segoe UI", 9),
                      bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                      padx=10, pady=5, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=lambda: self._set_all(True)).pack(side="left", padx=4)
            tk.Button(top, text="✕ Uncheck All", font=("Segoe UI", 9),
                      bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                      padx=10, pady=5, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=lambda: self._set_all(False)).pack(side="left", padx=4)
            tk.Button(top, text="⧉ Copy from role…", font=("Segoe UI", 9),
                      bg=C["card_bg"], fg=C["primary"], relief="flat",
                      padx=10, pady=5, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=self._copy_from).pack(side="left", padx=4)
            tk.Button(top, text="💾 Save Rights", font=("Segoe UI", 9, "bold"),
                      bg=C["primary"], fg="white", relief="flat",
                      padx=14, pady=5, cursor="hand2",
                      command=self._save).pack(side="right")

        # scrollable matrix
        card = tk.Frame(self.parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cv = tk.Canvas(card, bg=C["card_bg"], highlightthickness=0)
        sb = ttk.Scrollbar(card, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(fill="both", expand=True)
        self.grid = tk.Frame(cv, bg=C["card_bg"])
        cv.create_window((0, 0), window=self.grid, anchor="nw")
        self.grid.bind("<Configure>",
                       lambda e: cv.configure(scrollregion=cv.bbox("all")))

        # header row
        hdr_bg = C["primary_light"]
        tk.Label(self.grid, text="Module", font=("Segoe UI", 9, "bold"),
                 bg=hdr_bg, fg=C["primary"], width=18, anchor="w").grid(
            row=0, column=0, sticky="nsew", padx=1, pady=1)
        for ci, (ak, alabel) in enumerate(perm.ACTIONS, start=1):
            h = tk.Frame(self.grid, bg=hdr_bg)
            h.grid(row=0, column=ci, sticky="nsew", padx=1, pady=1)
            tk.Label(h, text=alabel, font=("Segoe UI", 8, "bold"),
                     bg=hdr_bg, fg=C["primary"], width=8).pack()
            if self._can_edit:
                tk.Button(h, text="all", font=("Segoe UI", 7), bg=hdr_bg,
                          fg=C["text_secondary"], relief="flat", cursor="hand2",
                          command=lambda a=ak: self._toggle_column(a)).pack()

        # module rows
        for ri, (mk, mlabel) in enumerate(perm.MODULES, start=1):
            rbg = "white" if ri % 2 else "#F7F6FD"
            rowf = tk.Frame(self.grid, bg=rbg)
            rowf.grid(row=ri, column=0, sticky="nsew", padx=1, pady=1)
            tk.Label(rowf, text=mlabel, font=("Segoe UI", 9), bg=rbg,
                     fg=C["text_primary"], width=18, anchor="w").pack(
                side="left", padx=4)
            if self._can_edit:
                tk.Button(rowf, text="·", font=("Segoe UI", 8), bg=rbg,
                          fg=C["text_secondary"], relief="flat", cursor="hand2",
                          command=lambda m=mk: self._toggle_row(m)).pack(side="right")
            for ci, (ak, _al) in enumerate(perm.ACTIONS, start=1):
                v = tk.BooleanVar(value=False)
                v.trace_add("write", lambda *a: self._mark_dirty())
                self.vars[(mk, ak)] = v
                cell = tk.Frame(self.grid, bg=rbg)
                cell.grid(row=ri, column=ci, sticky="nsew", padx=1, pady=1)
                cb = tk.Checkbutton(cell, variable=v, bg=rbg,
                                    activebackground=rbg,
                                    state="normal" if self._can_edit else "disabled")
                cb.pack()
                self._cbs.append(cb)

        self.status = tk.StringVar()
        tk.Label(self.parent, textvariable=self.status, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", pady=(4, 0))

    def _load_roles(self, select=None):
        try:
            self._roles = db.fetchall(
                "SELECT role_id, role_name_en FROM roles WHERE is_active=1 "
                "ORDER BY role_id") or []
        except Exception:
            self._roles = []
        names = [r["role_name_en"] for r in self._roles]
        self.role_cb.configure(values=names)
        if self._roles:
            self.role_cb.current(names.index(select) if select in names else 0)
            self._load_grants()

    def _current_role_id(self):
        for r in self._roles:
            if r["role_name_en"] == self.role_var.get():
                return r["role_id"]
        return None

    def _mark_dirty(self):
        if not self._loading:
            self._dirty = True

    def _on_role_pick(self):
        new = self.role_var.get()
        prev = next((r["role_name_en"] for r in self._roles
                     if r["role_id"] == self.role_id), None)
        if self._dirty and prev and prev != new:
            ans = messagebox.askyesnocancel(
                "Unsaved rights", f"Save the changes you made to '{prev}' first?",
                parent=self.parent)
            if ans is None:                       # cancel → stay on previous role
                self.role_var.set(prev); return
            if ans:
                self.role_var.set(prev)
                if not self._save():
                    return
                self.role_var.set(new)
        self._load_grants()

    def _load_grants(self):
        self.role_id = self._current_role_id()
        grants = perm.role_grants(self.role_id) if self.role_id else {}
        full = (self.role_var.get() or "").strip().lower() in perm.FULL_ACCESS_ROLES
        self._loading = True
        for (mk, ak), v in self.vars.items():
            v.set(True if full else (ak in grants.get(mk, set())))
        self._loading = False
        self._dirty = False
        state = "disabled" if (full or not self._can_edit) else "normal"
        for cb in self._cbs:
            cb.configure(state=state)
        try:
            n = db.execute_scalar("SELECT COUNT(*) FROM users WHERE role_id=?",
                                  (self.role_id,)) or 0
        except Exception:
            n = 0
        if full:
            self.status.set(f"'{self.role_var.get()}' always has FULL access — nothing to "
                            f"tick.  ({n} user(s) of this type)")
        else:
            self.status.set(f"{n} user(s) of this type. Tick what they may do, then "
                            "💾 Save Rights.")

    # ── user types (roles) ─────────────────────────────────
    def _role_name_ok(self, name, exclude_id=None):
        name = (name or "").strip()
        if not name:
            return False
        if name.lower() in perm.FULL_ACCESS_ROLES:
            messagebox.showwarning("User type", f"'{name}' is reserved for full-access "
                                   "administrators.", parent=self.parent)
            return False
        if any(r["role_name_en"].strip().lower() == name.lower() and r["role_id"] != exclude_id
               for r in self._roles):
            messagebox.showwarning("User type", f"'{name}' already exists.",
                                   parent=self.parent)
            return False
        return True

    def _may_edit_rights(self):
        """The matrix rule (user_rights edit or settings), checked again at
        the button itself."""
        if perm.can("user_rights", "edit") or perm.can("user_rights", "settings"):
            return True
        messagebox.showwarning("Not allowed", "Your user type can't change user rights.\n\n"
                               "Ask the administrator.", parent=self.parent)
        return False

    def _new_role(self):
        if not self._may_edit_rights():
            return
        name = simpledialog.askstring("New user type",
                                      "Name of the new user type (e.g. Store Keeper):",
                                      parent=self.parent)
        if not self._role_name_ok(name):
            return
        name = name.strip()
        try:
            db.execute("INSERT INTO roles (role_name_en, role_name_ar, is_active) "
                       "VALUES (?,?,1)", (name, name))
            rid = db.execute_scalar("SELECT MAX(role_id) FROM roles WHERE role_name_en=?",
                                    (name,))
            perm.save_role_grants(rid, {"dashboard": {"view"}})
            audit.log("create", "user_rights", rid, name)
        except Exception as e:
            messagebox.showerror("New user type", str(e)[:200], parent=self.parent)
            return
        self._dirty = False
        self._load_roles(select=name)
        self.status.set(f"'{name}' created with Dashboard only — tick its rights, "
                        "then 💾 Save Rights.")

    def _rename_role(self):
        if not self._may_edit_rights():
            return
        rid, old = self.role_id, self.role_var.get()
        if not rid:
            return
        if old.strip().lower() in perm.FULL_ACCESS_ROLES:
            messagebox.showinfo("Rename", "Administrator types can't be renamed "
                                "(the name is what gives full access).", parent=self.parent)
            return
        name = simpledialog.askstring("Rename user type", "New name:", initialvalue=old,
                                      parent=self.parent)
        if not name or name.strip() == old or not self._role_name_ok(name, exclude_id=rid):
            return
        db.execute("UPDATE roles SET role_name_en=? WHERE role_id=?", (name.strip(), rid))
        audit.log("update", "user_rights", rid, f"{old} → {name.strip()}")
        self._load_roles(select=name.strip())

    def _delete_role(self):
        if not self._may_edit_rights():
            return
        rid, name = self.role_id, self.role_var.get()
        if not rid:
            return
        if name.strip().lower() in perm.FULL_ACCESS_ROLES:
            messagebox.showinfo("Delete", "Administrator types can't be deleted.",
                                parent=self.parent)
            return
        n = db.execute_scalar("SELECT COUNT(*) FROM users WHERE role_id=?", (rid,)) or 0
        if n:
            messagebox.showwarning("Delete user type",
                                   f"{n} user(s) are '{name}'. Move them to another type "
                                   "first (Users tab ▸ Edit).", parent=self.parent)
            return
        if not messagebox.askyesno("Delete user type", f"Delete '{name}'?",
                                   parent=self.parent):
            return
        try:
            db.execute("DELETE FROM role_permissions WHERE role_id=?", (rid,))
            db.execute("DELETE FROM roles WHERE role_id=?", (rid,))
        except Exception:
            db.execute("UPDATE roles SET is_active=0 WHERE role_id=?", (rid,))
        audit.log("delete", "user_rights", rid, name)
        self._dirty = False
        self._load_roles()

    def _set_all(self, val):
        for v in self.vars.values():
            v.set(val)

    def _toggle_column(self, action_key):
        target = not all(self.vars[(mk, action_key)].get()
                         for mk, _ in perm.MODULES)
        for mk, _ in perm.MODULES:
            self.vars[(mk, action_key)].set(target)

    def _toggle_row(self, module_key):
        target = not all(self.vars[(module_key, ak)].get()
                         for ak, _ in perm.ACTIONS)
        for ak, _ in perm.ACTIONS:
            self.vars[(module_key, ak)].set(target)

    def _copy_from(self):
        others = [r["role_name_en"] for r in self._roles
                  if r["role_name_en"] != self.role_var.get()]
        if not others:
            return
        pick = _choose_dialog(self.parent, "Copy Permissions",
                              "Copy grants FROM which role?", others)
        if not pick:
            return
        src_id = next((r["role_id"] for r in self._roles
                       if r["role_name_en"] == pick), None)
        if not src_id:
            return
        grants = perm.role_grants(src_id)
        for (mk, ak), v in self.vars.items():
            v.set(ak in grants.get(mk, set()))
        self.status.set(f"Copied from {pick} — review, then Save Rights.")

    def _save(self):
        if not self.role_id:
            return False
        if not self._may_edit_rights():
            return False
        if (self.role_var.get() or "").strip().lower() in perm.FULL_ACCESS_ROLES:
            messagebox.showinfo("Rights",
                                "Administrator types always have full access — "
                                "no need to edit their grants.")
            return False
        grants = {}
        for (mk, ak), v in self.vars.items():
            if v.get():
                grants.setdefault(mk, set()).add(ak)
        # any right on a module implies being able to open it
        for mk, acts in grants.items():
            acts.add("view")
        # v6.9.3: a user who is not an administrator can't GIVE a right
        # he doesn't have himself (rights the type already had may stay)
        if not perm.is_full_access():
            had = perm.role_grants(self.role_id) or {}
            new = sorted("%s ▸ %s" % (dict(perm.MODULES).get(mk, mk), dict(perm.ACTIONS).get(ak, ak))
                         for mk, acts in grants.items() for ak in acts
                         if ak not in had.get(mk, set()) and not perm.can(mk, ak))
            if new:
                messagebox.showwarning(
                    "Rights", "You can't give rights you don't have yourself:\n\n• "
                    + "\n• ".join(new[:15]) + ("\n…" if len(new) > 15 else "")
                    + "\n\nUntick them, or ask an administrator.", parent=self.parent)
                return False
        if perm.save_role_grants(self.role_id, grants):
            audit.log("update", "user_rights", self.role_id, self.role_var.get())
            self._dirty = False
            self._loading = True
            for (mk, ak), v in self.vars.items():
                v.set(ak in grants.get(mk, set()))
            self._loading = False
            perm.refresh_session()           # applies at once to this PC's user
            self.status.set("✅ Rights saved for " + self.role_var.get() +
                            ". Other signed-in users get them at their next sign-in.")
            return True
        self.status.set("❌ Could not save — restart DayBill once so the database "
                        "update (rights tables) runs, then try again.")
        return False


# ============================================================
#  Login history dialog
# ============================================================
class LoginHistoryDialog:
    def __init__(self, parent):
        C = cfg.theme()
        self.win = tk.Toplevel(parent); self.win.bind("<Escape>", lambda e: self.win.destroy()); self.win.title("Login History")
        self.win.configure(bg=C["content_bg"]); _modal(self.win, parent)
        self.win.geometry("640x460")
        tk.Label(self.win, text="🕓  Login History", font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white", pady=8).pack(fill="x")
        card = tk.Frame(self.win, bg=C["card_bg"]); card.pack(fill="both",
                        expand=True, padx=12, pady=12)
        cols = ("time", "user", "result", "station")
        tree = ttk.Treeview(card, columns=cols, show="headings")
        for c, txt, w in [("time", "Time", 150), ("user", "Username", 140),
                          ("result", "Result", 90), ("station", "Workstation", 160)]:
            tree.heading(c, text=txt); tree.column(c, width=w)
        tree.pack(fill="both", expand=True)
        try:
            rows = db.fetchall(
                "SELECT TOP 200 login_time, username, success, workstation "
                "FROM login_history ORDER BY login_id DESC") or []
            for r in rows:
                lt = r.get("login_time")
                lt = lt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(lt, "strftime") \
                    else str(lt)
                tree.insert("", "end", values=(
                    lt, r.get("username", ""),
                    "✅ Success" if r.get("success") else "❌ Failed",
                    r.get("workstation", "")))
        except Exception:
            tk.Label(card, text="Login history table not found. Run Updates ▸ Apply All Updates.",
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(pady=20)


# ── tiny single-choice dialog (avoids a heavyweight combobox modal) ──
def _choose_dialog(parent, title, prompt, options):
    C = cfg.theme()
    win = tk.Toplevel(parent); win.title(title); win.configure(bg=C["content_bg"])
    _modal(win, parent); win.geometry("340x160")
    tk.Label(win, text=prompt, font=("Segoe UI", 10), bg=C["content_bg"],
             fg=C["text_primary"], wraplength=300).pack(padx=16, pady=(16, 8))
    var = tk.StringVar(value=options[0])
    ttk.Combobox(win, textvariable=var, values=options, state="readonly",
                 font=("Segoe UI", 10)).pack(padx=16, fill="x")
    result = {"val": None}

    def ok():
        result["val"] = var.get(); win.destroy()
    bb = tk.Frame(win, bg=C["content_bg"]); bb.pack(fill="x", padx=16, pady=16)
    tk.Button(bb, text="Cancel", font=("Segoe UI", 9), bg=C["card_bg"],
              relief="flat", padx=12, pady=5, command=win.destroy).pack(side="right",
              padx=(6, 0))
    tk.Button(bb, text="OK", font=("Segoe UI", 9, "bold"), bg=C["primary"],
              fg="white", relief="flat", padx=16, pady=5, command=ok).pack(side="right")
    win.wait_window()
    return result["val"]


# Backward-compatible alias so existing nav ("users") keeps working
UsersView = UserRightsView
