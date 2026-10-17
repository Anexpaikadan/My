# ============================================================
# DayBill ERP - User Management
# List users, add/edit/deactivate, assign roles, reset password
# v6.9.3: every button checks its right (users.add / users.edit), and
# only a full-access user (Super Admin / Admin) may give a full-access
# user type or change / reset the password of a full-access user.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db


def password_problem(pw: str) -> str:
    """Settings > Users & Security > Password Minimum Length."""
    try:
        n = int(float(cfg.get("pwd_min_length", 4) or 0))
    except Exception:
        n = 4
    if n and len(pw or "") < n:
        return f"Password must be at least {n} characters."
    return ""


# ── v6.9.3: protect the administrators (also used by ui/user_rights.py) ──
def full_access_role_ids():
    """role_ids whose user type always has every right."""
    from modules import permissions as _perm
    try:
        return {r["role_id"] for r in db.fetchall("SELECT role_id, role_name_en FROM roles") or []
                if (r["role_name_en"] or "").strip().lower() in _perm.FULL_ACCESS_ROLES}
    except Exception:
        return set()


def is_full_access_user(user_id):
    """True for a Super Admin / Admin type user or the built-in 'admin'.
    When it can't be read: True (the safe answer)."""
    try:
        u = db.fetchone("SELECT username, role_id FROM users WHERE user_id=?", (user_id,))
    except Exception:
        return True
    if not u:
        return False
    if str(u.get("username", "")).strip().lower() == "admin":
        return True
    return u.get("role_id") in full_access_role_ids()


def admin_only_problem(user_id=None, role_id=None, username=None):
    """'' when the signed-in user may do this, else the reason.
    Only a full-access user may: change (or reset the password of) a
    full-access user, give a full-access user type, or use the name
    'admin' (that name always has full access)."""
    from modules import permissions as _perm
    if _perm.is_full_access():
        return ""
    if user_id and is_full_access_user(user_id):
        return ("Only an administrator (Super Admin / Admin) can change an "
                "administrator's account or password.")
    if role_id and role_id in full_access_role_ids():
        return "Only an administrator (Super Admin / Admin) can give an administrator user type."
    if username is not None and str(username).strip().lower() == "admin":
        return "The name 'admin' is kept for the built-in administrator."
    return ""


def _allowed(action, parent=None):
    """users.<action> with the usual 'not allowed' message."""
    try:
        from modules import permissions as _perm
        return bool(_perm.allowed("users", action, parent=parent))
    except Exception:
        return False


def hash_password(plain: str) -> str:
    """Salted hash (bcrypt → Argon2 → PBKDF2). Never plain SHA-256 (v5.27)."""
    from modules import permissions as _perm
    return _perm.hash_password(plain)


class UsersView:
    def __init__(self, parent):
        C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._roles = []
        self._build(C)
        self._load()

    def _build(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="👤  User Management", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="＋  Add User", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=7,
                  cursor="hand2", activebackground=C["primary_dark"],
                  command=self._add).pack(side="right")

        # table
        wrap = tk.Frame(self.frame, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=24, pady=18)

        cols = ("id", "username", "name", "role", "lang", "status")
        heads = {"id": ("ID", 50), "username": ("Username", 140),
                 "name": ("Full Name", 220), "role": ("Role", 140),
                 "lang": ("Lang", 60), "status": ("Status", 90)}
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Usr.Treeview", rowheight=32, font=("Segoe UI", 10))
        style.configure("Usr.Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background=C.get("heading_bg", C["content_bg"]), foreground="#374151")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 style="Usr.Treeview", selectmode="browse")
        for c in cols:
            txt, w = heads[c]
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w,
                             anchor="center" if c in ("id", "lang", "status") else "w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.bind("<Double-1>", lambda e: self._edit())

        btns = tk.Frame(self.frame, bg=C["content_bg"])
        btns.pack(fill="x", padx=24, pady=(0, 16))
        tk.Button(btns, text="✏ Edit", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._edit).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="🔑 Reset Password", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._reset_pw).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="🚫 Activate / Deactivate", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["danger"], relief="flat", padx=12, pady=6,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._toggle_active).pack(side="left")

    def _load(self):
        try:
            self._roles = db.fetchall(
                "SELECT role_id, role_name_en FROM roles WHERE is_active=1 "
                "ORDER BY role_id") or []
        except Exception:
            self._roles = []
        self.tree.delete(*self.tree.get_children())
        try:
            rows = db.fetchall(
                "SELECT u.user_id, u.username, u.full_name_en, u.preferred_language, "
                "u.is_active, r.role_name_en "
                "FROM users u LEFT JOIN roles r ON u.role_id=r.role_id "
                "ORDER BY u.user_id") or []
            for r in rows:
                self.tree.insert("", "end", iid=str(r["user_id"]), values=(
                    r["user_id"], r["username"], r.get("full_name_en", ""),
                    r.get("role_name_en", "—"),
                    (r.get("preferred_language") or "en").upper(),
                    "Active" if r.get("is_active", 1) else "Inactive"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _sel_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        if not _allowed("add", self.frame):
            return
        UserForm(self.frame, self._roles, on_save=self._load)

    def _edit(self):
        if not _allowed("edit", self.frame):
            return
        uid = self._sel_id()
        if not uid:
            messagebox.showinfo("Select", "Select a user first."); return
        prob = admin_only_problem(user_id=uid)
        if prob:
            messagebox.showwarning("Edit User", prob, parent=self.frame); return
        UserForm(self.frame, self._roles, user_id=uid, on_save=self._load)

    def _reset_pw(self):
        if not _allowed("edit", self.frame):
            return
        uid = self._sel_id()
        if not uid:
            messagebox.showinfo("Select", "Select a user first."); return
        prob = admin_only_problem(user_id=uid)
        if prob:
            messagebox.showwarning("Reset Password", prob, parent=self.frame); return
        from tkinter import simpledialog
        pw = simpledialog.askstring("Reset Password",
                                    "Enter a new password:", show="*", parent=self.frame)
        if not pw:
            return
        prob = password_problem(pw)
        if prob:
            messagebox.showwarning("Reset Password", prob); return
        try:
            db.execute("UPDATE users SET password_hash=?, updated_at=GETDATE() "
                       "WHERE user_id=?", (hash_password(pw), uid))
            try:
                from modules import permissions as _pm
                _pm.mark_password_changed(uid)
            except Exception:
                pass
            try:
                from modules import audit
                audit.log("reset_password", "users", uid)
            except Exception:
                pass
            messagebox.showinfo("Done", "Password reset.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _toggle_active(self):
        if not _allowed("edit", self.frame):
            return
        uid = self._sel_id()
        if not uid:
            messagebox.showinfo("Select", "Select a user first."); return
        prob = admin_only_problem(user_id=uid)
        if prob:
            messagebox.showwarning("Activate / Deactivate", prob, parent=self.frame); return
        try:
            row = db.fetchone("SELECT username, is_active FROM users WHERE user_id=?", (uid,)) or {}
            cur = row.get("is_active")
            if cur:                      # switching off: never lock everyone out
                from modules import permissions as _pm
                if str(row.get("username", "")).lower() == "admin":
                    messagebox.showwarning("Deactivate", "The built-in 'admin' user can't be "
                                           "switched off.", parent=self.frame); return
                if uid == _pm.session_user().get("user_id"):
                    messagebox.showwarning("Deactivate", "You can't switch off your own "
                                           "account.", parent=self.frame); return
            new = 0 if cur else 1
            db.execute("UPDATE users SET is_active=? WHERE user_id=?", (new, uid))
            try:
                from modules import audit
                audit.log("deactivate" if not new else "update", "users", uid,
                          "%s %s" % (row.get("username", ""), "switched off" if not new else "switched on"))
            except Exception:
                pass
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))


class UserForm:
    def __init__(self, parent, roles, user_id=None, on_save=None):
        self.user_id = user_id
        self.roles = roles
        self.on_save = on_save
        C = cfg.theme()

        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("Edit User" if user_id else "Add User")
        self.win.geometry("440x520")
        self.win.configure(bg=C["content_bg"])
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.grab_set()
        self._center(440, 520)

        tk.Label(self.win, text="👤  " + ("Edit User" if user_id else "Add User"),
                 font=("Segoe UI", 15, "bold"), bg=C["primary"], fg="white",
                 pady=12).pack(fill="x")

        body = tk.Frame(self.win, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=24, pady=16)

        self.f = {}

        def field(label, key, show=None):
            tk.Label(body, text=label, font=("Segoe UI", 9),
                     bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(8, 2))
            v = tk.StringVar()
            self.f[key] = v
            e = tk.Entry(body, textvariable=v, font=("Segoe UI", 11), bg="white",
                         relief="solid", bd=1, show=show)
            e.pack(fill="x", ipady=6)
            return v

        field("Username *", "username")
        field("Full Name (EN) *", "full_name_en")
        field("Full Name (AR)", "full_name_ar")
        field("Email", "email")
        field("Phone", "phone")

        # Role
        tk.Label(body, text="Role *", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(8, 2))
        self.role_var = tk.StringVar()
        self.role_cb = ttk.Combobox(body, textvariable=self.role_var,
                                    values=[r["role_name_en"] for r in roles],
                                    state="readonly", font=("Segoe UI", 11))
        self.role_cb.pack(fill="x", ipady=4)

        # Language
        tk.Label(body, text="Preferred Language", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(8, 2))
        self.lang_var = tk.StringVar(value="en")
        ttk.Combobox(body, textvariable=self.lang_var, values=["en", "ar"],
                     state="readonly", font=("Segoe UI", 11)).pack(fill="x", ipady=4)

        # Password (only required for new users)
        field("Password " + ("(leave blank to keep)" if user_id else "*"),
              "password", show="*")

        # Per-user rights
        tk.Label(body, text="Permissions", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", pady=(12, 2))
        rights_row = tk.Frame(body, bg=C["content_bg"]); rights_row.pack(anchor="w")
        self.right_master  = tk.BooleanVar(value=False)
        self.right_reports = tk.BooleanVar(value=False)
        self.right_edit    = tk.BooleanVar(value=False)
        self.right_delete  = tk.BooleanVar(value=False)
        for txt, var in (("Master", self.right_master),
                         ("Reports", self.right_reports),
                         ("Edit", self.right_edit),
                         ("Delete", self.right_delete)):
            tk.Checkbutton(rights_row, text=txt, variable=var,
                           font=("Segoe UI", 10), bg=C["content_bg"],
                           activebackground=C["content_bg"]).pack(side="left", padx=(0, 14))
        tk.Label(body,
                 text="Master = customers/suppliers/products/inventory · "
                      "Reports = reports/accounts · Edit/Delete = change records.",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"], wraplength=380,
                 justify="left").pack(anchor="w", pady=(2, 0))

        self.status = tk.StringVar()
        tk.Label(body, textvariable=self.status, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["danger"], wraplength=380).pack(anchor="w", pady=(8, 0))

        bb = tk.Frame(self.win, bg=C["content_bg"]); bb.pack(fill="x", padx=24, pady=(0, 16))
        tk.Button(bb, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(bb, text="💾 Save", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=18, pady=7, cursor="hand2",
                  command=self._save).pack(side="right")

        if user_id:
            self._load()
        elif roles:
            self.role_cb.current(0)

    def _load(self):
        try:
            u = db.fetchone("SELECT * FROM users WHERE user_id=?", (self.user_id,))
            if not u:
                return
            for k in ("username", "full_name_en", "full_name_ar", "email", "phone"):
                if u.get(k) is not None:
                    self.f[k].set(str(u[k]))
            self.lang_var.set(u.get("preferred_language", "en") or "en")
            for r in self.roles:
                if r["role_id"] == u.get("role_id"):
                    self.role_var.set(r["role_name_en"])
                    break
            # rights (columns may not exist on older DBs)
            self.right_master.set(bool(u.get("can_master", 0)))
            self.right_reports.set(bool(u.get("can_reports", 0)))
            self.right_edit.set(bool(u.get("can_edit", 0)))
            self.right_delete.set(bool(u.get("can_delete", 0)))
        except Exception as e:
            self.status.set(str(e))

    def _has_rights_columns(self):
        try:
            return bool(db.execute_scalar(
                "SELECT COUNT(*) FROM sys.columns "
                "WHERE object_id=OBJECT_ID('users') AND name='can_master'"))
        except Exception:
            return False

    def _save(self):
        if not _allowed("edit" if self.user_id else "add", self.win):
            return
        username = self.f["username"].get().strip()
        name = self.f["full_name_en"].get().strip()
        if not username or not name:
            self.status.set("Username and Full Name are required."); return
        role_id = None
        for r in self.roles:
            if r["role_name_en"] == self.role_var.get():
                role_id = r["role_id"]; break
        if not role_id:
            self.status.set("Please choose a role."); return
        # only an administrator may touch an administrator (v6.9.3)
        prob = admin_only_problem(user_id=self.user_id, role_id=role_id, username=username)
        if prob:
            self.status.set(prob); return
        pw = self.f["password"].get().strip()
        if pw or not self.user_id:
            prob = password_problem(pw)
            if prob:
                self.status.set(prob); return
        has_rights = self._has_rights_columns()
        rm = 1 if self.right_master.get() else 0
        rr = 1 if self.right_reports.get() else 0
        re_ = 1 if self.right_edit.get() else 0
        rd = 1 if self.right_delete.get() else 0

        try:
            if self.user_id:
                fields = {
                    "username": username, "full_name_en": name,
                    "full_name_ar": self.f["full_name_ar"].get().strip() or None,
                    "email": self.f["email"].get().strip() or None,
                    "phone": self.f["phone"].get().strip() or None,
                    "role_id": role_id,
                    "preferred_language": self.lang_var.get(),
                }
                if has_rights:
                    fields.update({"can_master": rm, "can_reports": rr,
                                   "can_edit": re_, "can_delete": rd})
                if pw:
                    fields["password_hash"] = hash_password(pw)
                set_clause = ", ".join(f"{k}=?" for k in fields)
                db.execute(f"UPDATE users SET {set_clause}, updated_at=GETDATE() "
                           f"WHERE user_id=?", (*fields.values(), self.user_id))
            else:
                if not pw:
                    self.status.set("Password is required for a new user."); return
                if has_rights:
                    db.execute(
                        "INSERT INTO users (username, password_hash, full_name_en, "
                        "full_name_ar, email, phone, role_id, preferred_language, "
                        "is_active, can_master, can_reports, can_edit, can_delete) "
                        "VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?)",
                        (username, hash_password(pw), name,
                         self.f["full_name_ar"].get().strip() or None,
                         self.f["email"].get().strip() or None,
                         self.f["phone"].get().strip() or None,
                         role_id, self.lang_var.get(), rm, rr, re_, rd))
                else:
                    db.execute(
                        "INSERT INTO users (username, password_hash, full_name_en, "
                        "full_name_ar, email, phone, role_id, preferred_language, is_active) "
                        "VALUES (?,?,?,?,?,?,?,?,1)",
                        (username, hash_password(pw), name,
                         self.f["full_name_ar"].get().strip() or None,
                         self.f["email"].get().strip() or None,
                         self.f["phone"].get().strip() or None,
                         role_id, self.lang_var.get()))
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err or "duplicate" in err.lower():
                self.status.set("That username already exists.")
            else:
                self.status.set(err[:90])

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
