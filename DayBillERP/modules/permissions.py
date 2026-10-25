# ============================================================
# DayBill ERP — Role-Based Access Control (RBAC) core
# ------------------------------------------------------------
# One place that owns:
#   • the canonical list of MODULES and ACTIONS
#   • the predefined ROLES and their default grants
#   • resolving a logged-in user's effective permissions
#   • can() / require() checks used by every page & button
#   • password hashing (bcrypt → Argon2 → PBKDF2 fallback)
#   • login-history logging
#
# Design goals: fast (permissions cached per session), safe
# (Super Admin & the bootstrap 'admin' user always allowed),
# and backward-compatible (degrades gracefully if the RBAC
# tables aren't migrated yet — then it falls back to the old
# coarse can_master/can_reports/can_edit/can_delete flags).
# ============================================================

import os
import sys
import platform

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


# ── Canonical modules (order = display order) ───────────────
MODULES = [
    ("dashboard",         "Dashboard"),
    ("pos",               "POS / Cashier"),
    ("products",          "Products"),
    ("categories",        "Categories"),
    ("customers",         "Customers"),
    ("suppliers",         "Suppliers"),
    ("sales",             "Sales"),
    ("sales_return",      "Sales Return"),
    ("quotation",         "Quotation"),
    ("purchase",          "Purchase"),
    ("purchase_return",   "Purchase Return"),
    ("purchase_order",    "Purchase Order"),
    ("inventory",         "Inventory"),
    ("stock_adjustment",  "Stock Adjustment"),
    ("consumption",       "Consumable Entry (own use)"),
    ("accounts",          "Accounts"),
    ("receipt",           "Receipt"),
    ("payment",           "Payment"),
    ("journal",           "Journal"),
    ("day_close",         "Day Close / Z-Report"),
    ("hr",                "HR & Payroll"),
    ("reports",           "Reports"),
    ("users",             "Users"),
    ("user_rights",       "User Rights"),
    ("audit_log",         "Audit Log"),
    ("company_settings",  "Company Settings"),
]

# ── Canonical actions (order = column order in the matrix) ──
ACTIONS = [
    ("view",     "View"),
    ("add",      "Add"),
    ("edit",     "Edit"),
    ("delete",   "Delete"),
    ("print",    "Print"),
    ("export",   "Export"),
    ("reports",  "Reports"),
    ("approve",  "Approve"),
    ("settings", "Settings"),
]

MODULE_KEYS = [k for k, _ in MODULES]
ACTION_KEYS = [k for k, _ in ACTIONS]

# ── Predefined roles ────────────────────────────────────────
ROLES = ["Super Admin", "Admin", "Manager", "Accountant",
         "Sales", "Purchase", "Inventory", "Cashier", "Viewer"]

# Roles that always have every permission, regardless of grants.
# "Administrator" is the role the setup script creates for the admin user.
FULL_ACCESS_ROLES = {"super admin", "admin", "administrator"}


# ── Default grant templates for each predefined role ────────
# Value is a dict {module_key: set(action_keys)} or the string
# "ALL" meaning every action on every module.
def _all_actions():
    return set(ACTION_KEYS)


def _view_only(modules):
    return {m: {"view", "reports", "export", "print"} for m in modules}


def default_grants(role_name):
    r = (role_name or "").strip().lower()
    if r in FULL_ACCESS_ROLES:
        return "ALL"

    if r == "manager":
        # everything except user administration & company settings edit
        g = {m: _all_actions() for m in MODULE_KEYS
             if m not in ("users", "user_rights", "company_settings", "audit_log")}
        g["users"] = {"view"}
        g["audit_log"] = {"view", "export", "print"}
        g["company_settings"] = {"view"}
        return g

    if r == "accountant":
        acc_mods = ["dashboard", "customers", "suppliers", "accounts",
                    "receipt", "payment", "journal", "reports", "day_close", "hr"]
        g = {m: {"view", "add", "edit", "print", "export", "reports"}
             for m in acc_mods}
        g["accounts"].add("approve")
        return g

    if r == "sales":
        g = {
            "dashboard": {"view"},
            "pos":       {"view", "add", "print"},
            "customers": {"view", "add", "edit"},
            "products":  {"view"},
            "sales":     {"view", "add", "edit", "print", "export"},
            "sales_return": {"view", "add", "print"},
            "quotation": {"view", "add", "edit", "print", "export"},
            "receipt":   {"view", "add", "print"},
            "reports":   {"view", "reports", "export"},
        }
        return g

    if r == "purchase":
        return {
            "dashboard": {"view"},
            "suppliers": {"view", "add", "edit"},
            "products":  {"view"},
            "purchase":  {"view", "add", "edit", "print", "export"},
            "purchase_return": {"view", "add", "print"},
            "purchase_order": {"view", "add", "edit", "print", "export"},
            "payment":   {"view", "add", "print"},
            "reports":   {"view", "reports", "export"},
        }

    if r == "inventory":
        return {
            "dashboard":        {"view"},
            "products":         {"view", "add", "edit"},
            "categories":       {"view", "add", "edit"},
            "inventory":        {"view", "add", "edit", "export", "print"},
            "stock_adjustment": {"view", "add", "edit", "approve"},
            "consumption":      {"view", "add", "edit", "print"},   # v6.9.3 own use
            "reports":          {"view", "reports", "export"},
        }

    if r == "cashier":
        return {
            "dashboard": {"view"},
            "pos":       {"view", "add", "print"},
            "day_close": {"view", "print"},
            "sales":     {"view", "add", "print"},
            "customers": {"view", "add"},
            "receipt":   {"view", "add", "print"},
            "products":  {"view"},
        }

    if r == "viewer":
        return _view_only(["dashboard", "products", "customers", "suppliers",
                           "sales", "quotation", "purchase", "purchase_order",
                           "inventory", "accounts",
                           "reports"])

    # unknown role → dashboard view only
    return {"dashboard": {"view"}}


# ============================================================
#  Schema helpers (seed modules/actions, migrations)
# ============================================================
def tables_ready():
    try:
        return bool(db.execute_scalar(
            "SELECT COUNT(*) FROM sys.tables "
            "WHERE name IN ('permissions','role_permissions')") == 2)
    except Exception:
        return False


def ensure_permissions_seeded():
    """Make sure every (module, action) pair exists in `permissions`.
    Cheap and idempotent — safe to call at startup."""
    if not tables_ready():
        return False
    try:
        existing = db.fetchall("SELECT module_key, action_key FROM permissions") or []
        have = {(r["module_key"], r["action_key"]) for r in existing}
        had_any = bool(have)
        known_modules = {m for m, _ in have}
        new_modules = [mk for mk in MODULE_KEYS if mk not in known_modules]
        for mk in MODULE_KEYS:
            for ak in ACTION_KEYS:
                if (mk, ak) not in have:
                    db.execute(
                        "INSERT INTO permissions (module_key, action_key) "
                        "VALUES (?,?)", (mk, ak))
        # A module added in a later version (e.g. POS, HR, Day Close):
        # give every EXISTING role its default grants for just that module,
        # so upgrading never silently takes a screen away from anyone.
        if had_any and new_modules:
            _grant_defaults_for_modules(new_modules)
        return True
    except Exception:
        return False


def _grant_defaults_for_modules(modules):
    try:
        pid = {(r["module_key"], r["action_key"]): r["permission_id"]
               for r in db.fetchall("SELECT permission_id, module_key, action_key "
                                    "FROM permissions") or []}
        for r in db.fetchall("SELECT role_id, role_name_en FROM roles") or []:
            g = default_grants(r["role_name_en"])
            for m in modules:
                acts = set(ACTION_KEYS) if g == "ALL" else g.get(m, set())
                for a in acts:
                    p = pid.get((m, a))
                    if p:
                        try:
                            db.execute("INSERT INTO role_permissions (role_id, "
                                       "permission_id, allowed) VALUES (?,?,1)",
                                       (r["role_id"], p))
                        except Exception:
                            pass          # already there
    except Exception:
        pass


def permission_id_map():
    """{(module_key, action_key): permission_id}"""
    ensure_permissions_seeded()
    out = {}
    try:
        for r in db.fetchall(
                "SELECT permission_id, module_key, action_key FROM permissions") or []:
            out[(r["module_key"], r["action_key"])] = r["permission_id"]
    except Exception:
        pass
    return out


def seed_role_defaults(role_id, role_name, overwrite=False):
    """Grant a role its default permission template. If overwrite is
    False, existing grants are left untouched (only missing ones added)."""
    if not tables_ready():
        return
    pid = permission_id_map()
    grants = default_grants(role_name)
    if grants == "ALL":
        wanted = {(m, a) for m in MODULE_KEYS for a in ACTION_KEYS}
    else:
        wanted = {(m, a) for m, acts in grants.items() for a in acts}
    try:
        if overwrite:
            db.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
            have = set()
        else:
            have = {r["permission_id"] for r in db.fetchall(
                "SELECT permission_id FROM role_permissions WHERE role_id=?",
                (role_id,)) or []}
        for (m, a) in wanted:
            p = pid.get((m, a))
            if p and p not in have:
                db.execute(
                    "INSERT INTO role_permissions (role_id, permission_id, allowed) "
                    "VALUES (?,?,1)", (role_id, p))
    except Exception:
        pass


def bootstrap_roles_and_permissions():
    """First-run setup: seed the permission catalogue and give each
    predefined role sensible defaults (without clobbering edits)."""
    if not ensure_permissions_seeded():
        return False
    try:
        roles = db.fetchall("SELECT role_id, role_name_en FROM roles") or []
        for r in roles:
            # only seed a role that has no grants yet
            n = db.execute_scalar(
                "SELECT COUNT(*) FROM role_permissions WHERE role_id=?",
                (r["role_id"],)) or 0
            if n == 0:
                seed_role_defaults(r["role_id"], r["role_name_en"])
        return True
    except Exception:
        return False


# ============================================================
#  Grant read / write for the matrix UI
# ============================================================
def role_grants(role_id):
    """Return {module_key: set(action_keys)} currently granted to a role."""
    out = {}
    if not tables_ready():
        return out
    try:
        rows = db.fetchall(
            "SELECT p.module_key, p.action_key FROM role_permissions rp "
            "JOIN permissions p ON p.permission_id=rp.permission_id "
            "WHERE rp.role_id=? AND rp.allowed=1", (role_id,)) or []
        for r in rows:
            out.setdefault(r["module_key"], set()).add(r["action_key"])
    except Exception:
        pass
    return out


def save_role_grants(role_id, grants):
    """Replace a role's grants with `grants` = {module_key: set(actions)}."""
    if not tables_ready():
        return False
    pid = permission_id_map()
    try:
        db.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
        n = 0
        for m, acts in grants.items():
            for a in acts:
                p = pid.get((m, a))
                if p:
                    db.execute(
                        "INSERT INTO role_permissions (role_id, permission_id, "
                        "allowed) VALUES (?,?,1)", (role_id, p))
                    n += 1
        if n == 0 and pid.get(("dashboard", "view")):
            # "nothing allowed" marker (allowed=0): the role now HAS a row,
            # so startup never re-seeds it with defaults
            db.execute("INSERT INTO role_permissions (role_id, permission_id, "
                       "allowed) VALUES (?,?,0)", (role_id, pid[("dashboard", "view")]))
        return True
    except Exception:
        return False


def copy_role_grants(from_role_id, to_role_id):
    return save_role_grants(to_role_id, role_grants(from_role_id))


# ============================================================
#  Session permission checks
# ============================================================
_session = {"user": {}, "role_name": "", "grants": None, "rbac": False}


def set_session_user(user):
    """Call once after login. Caches the user's role name and effective
    grants so can() checks are instant."""
    _session["user"] = user or {}
    role_name = ""
    grants = {}
    rbac = tables_ready()
    try:
        rid = (user or {}).get("role_id")
        if rid:
            row = db.fetchone("SELECT role_name_en FROM roles WHERE role_id=?",
                              (rid,))
            role_name = (row or {}).get("role_name_en", "") if row else ""
            grants = role_grants(rid)
    except Exception:
        pass
    _session["role_name"] = role_name
    _session["grants"] = grants
    _session["rbac"] = rbac


def session_user():
    """The logged-in user dict ({} before login)."""
    return dict(_session.get("user") or {})


def refresh_session():
    """Re-read the logged-in user's rights (after rights were edited)."""
    if _session.get("user"):
        set_session_user(_session["user"])


def is_full_access():
    return _is_full_access()


def has_any_right():
    """False when the user can't use ANY screen (no role / nothing ticked)."""
    if _is_full_access():
        return True
    if _session.get("rbac"):
        return any(_session.get("grants", {}).values())
    return True


def _is_full_access():
    u = _session["user"] or {}
    if str(u.get("username", "")).lower() == "admin":
        return True
    return (_session.get("role_name", "") or "").strip().lower() in FULL_ACCESS_ROLES


# Product key: without an active key (after the trial) nothing new can be
# saved. Settings, users and company stay usable so a key can be entered.
_WRITE_ACTIONS = {"add", "edit", "delete", "approve"}
_LICENSE_FREE = {"company_settings", "users"}


def _license_ok():
    try:
        from modules import license as _lic
        return _lic.write_ok()
    except Exception:
        return True


def can(module_key, action_key="view"):
    """The single check used everywhere. Returns True/False.

    Order of precedence:
      1. Super Admin / Admin role or the bootstrap 'admin' user → always True
      2. RBAC grants (role_permissions) when the tables exist
      3. Legacy fallback to the old can_master/can_reports/... flags
    """
    if action_key in _WRITE_ACTIONS and module_key not in _LICENSE_FREE and not _license_ok():
        return False                 # trial over / key expired → read-only
    if _is_full_access():
        return True

    grants = _session.get("grants")
    if _session.get("rbac"):         # rights tables exist → they decide,
        # even when this role has nothing ticked (then: no access)
        return action_key in (grants or {}).get(module_key, set())

    # ── Legacy fallback (pre-RBAC databases) ───────────────
    return _legacy_can(module_key, action_key)


def _legacy_can(module_key, action_key):
    u = _session["user"] or {}
    master  = bool(u.get("can_master", 0))
    reports = bool(u.get("can_reports", 0))
    can_edit = bool(u.get("can_edit", 0))
    can_del  = bool(u.get("can_delete", 0))
    always = {"dashboard", "sales", "sales_return", "receipt"}
    master_mods = {"products", "categories", "customers", "suppliers",
                   "purchase", "purchase_return", "inventory",
                   "stock_adjustment", "consumption", "payment"}
    report_mods = {"accounts", "journal", "reports"}
    if action_key == "edit" and not can_edit:
        if module_key not in always:
            return False
    if action_key == "delete" and not can_del:
        return False
    if module_key in always:
        return True
    if module_key in master_mods:
        return master
    if module_key in report_mods:
        return reports
    if module_key in ("users", "user_rights", "company_settings"):
        return str(u.get("username", "")).lower() == "admin"
    return True


_ACTION_WORDS = {"view": "open", "add": "create", "edit": "change", "delete": "delete",
                 "print": "print", "export": "export", "reports": "run reports for",
                 "approve": "approve", "settings": "change settings of"}


def allowed(module_key, action_key="view", parent=None, quiet=False):
    """can() + a friendly 'not allowed' message. Use at the top of any
    button handler:   if not perm.allowed("products", "delete"): return"""
    if can(module_key, action_key):
        return True
    if (not quiet and action_key in _WRITE_ACTIONS and module_key not in _LICENSE_FREE
            and not _license_ok()):
        try:
            from tkinter import messagebox
            from modules import license as _lic
            messagebox.showwarning("Product key", _lic.block_message(), parent=parent)
        except Exception:
            pass
        return False
    if not quiet:
        try:
            from tkinter import messagebox
            label = dict(MODULES).get(module_key, module_key.replace("_", " "))
            messagebox.showwarning(
                "Not allowed",
                "Your user type can't %s %s.\n\nAsk the administrator to "
                "give this right in Users & Rights." % (
                    _ACTION_WORDS.get(action_key, action_key), label),
                parent=parent)
        except Exception:
            pass
    return False


def require(module_key, action_key="view"):
    """Raise PermissionError if the current user lacks the permission.
    Use at the top of a handler that must be protected server-side."""
    if not can(module_key, action_key):
        raise PermissionError(
            "You don't have permission to %s %s."
            % (action_key, module_key.replace("_", " ")))


def guard(module_key, action_key, silent=False):
    """Decorator for UI action handlers. If the current user lacks the
    permission, the wrapped method does NOT run — a polite 'Access
    Denied' box is shown (unless silent) and the handler returns None.

    Usage:
        @perm.guard("customers", "delete")
        def _delete_customer(self): ...

    This is real, server-side-style enforcement: even if a button is
    somehow reached, the action is blocked at the handler."""
    def deco(fn):
        import functools

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if can(module_key, action_key):
                return fn(*args, **kwargs)
            if (not silent and action_key in _WRITE_ACTIONS
                    and module_key not in _LICENSE_FREE and not _license_ok()):
                try:
                    from tkinter import messagebox
                    from modules import license as _lic
                    messagebox.showwarning("Product key", _lic.block_message())
                except Exception:
                    pass
                return None
            if not silent:
                try:
                    from tkinter import messagebox
                    messagebox.showwarning(
                        "Access Denied",
                        "You don't have permission to %s %s."
                        % (action_key, module_key.replace("_", " ")))
                except Exception:
                    pass
            return None
        wrapper._perm = (module_key, action_key)
        return wrapper
    return deco


# ============================================================
#  Password hashing (bcrypt → argon2 → pbkdf2)
# ============================================================
def mark_password_changed(user_id):
    """Start the password-expiry clock for this user (Settings ▸ Users &
    Security ▸ Password Expiry). Silent when the column isn't there yet."""
    try:
        db.execute("UPDATE users SET password_changed_at=GETDATE() WHERE user_id=?",
                   (user_id,))
    except Exception:
        pass


def password_age_days(user_id):
    """Days since the password was set, or None when unknown (the clock
    is started now in that case)."""
    try:
        row = db.fetchone("SELECT password_changed_at FROM users WHERE user_id=?",
                          (user_id,)) or {}
    except Exception:
        return None
    when = row.get("password_changed_at")
    if not when:
        mark_password_changed(user_id)
        return None
    from datetime import datetime as _dt
    if not hasattr(when, "year"):
        s = str(when).replace("T", " ")[:19]
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                when = _dt.strptime(s[:len(f) + 2], f)
                break
            except ValueError:
                continue
        else:
            return None
    if not hasattr(when, "hour"):
        when = _dt(when.year, when.month, when.day)
    return (_dt.now() - when).days


def hash_password(plain):
    plain = plain or ""
    try:
        import bcrypt
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    except Exception:
        pass
    try:
        from argon2 import PasswordHasher
        return PasswordHasher().hash(plain)
    except Exception:
        pass
    # last-resort salted PBKDF2 (still far better than plain SHA)
    import hashlib
    import binascii
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 200_000)
    return "pbkdf2$" + binascii.hexlify(salt).decode() + "$" + \
        binascii.hexlify(dk).decode()


def verify_password(plain, stored_hash):
    plain = plain or ""
    stored_hash = stored_hash or ""
    # bcrypt
    if stored_hash.startswith("$2"):
        try:
            import bcrypt
            return bcrypt.checkpw(plain.encode(), stored_hash.encode())
        except Exception:
            return False
    # argon2
    if stored_hash.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher
            PasswordHasher().verify(stored_hash, plain)
            return True
        except Exception:
            return False
    # pbkdf2 fallback
    if stored_hash.startswith("pbkdf2$"):
        try:
            import hashlib
            import binascii
            _, salt_hex, dk_hex = stored_hash.split("$")
            salt = binascii.unhexlify(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 200_000)
            return binascii.hexlify(dk).decode() == dk_hex
        except Exception:
            return False
    # legacy plain SHA-256
    try:
        import hashlib
        return hashlib.sha256(plain.encode()).hexdigest() == stored_hash
    except Exception:
        return False


def needs_rehash(stored_hash):
    """An old unsalted SHA-256 hash (or a weak fallback) — replace it with a
    proper salted hash the next time the user logs in (v5.27)."""
    h = str(stored_hash or "")
    return not h.startswith(("$2a$", "$2b$", "$2y$", "$argon2"))


def upgrade_hash(user_id, plain):
    """After a correct password: store it with today's strong hash."""
    try:
        new = hash_password(plain)
        if new.startswith(("$2", "$argon2")):
            db.execute("UPDATE users SET password_hash=? WHERE user_id=?", (new, user_id))
            return True
    except Exception:
        pass
    return False


def recent_failed_logins(username, seconds=60):
    """Wrong passwords for this user name in the last `seconds`, counted
    from the login history (so closing and opening DayBill — or another
    PC — doesn't reset the lock). Only misses after the last success."""
    from datetime import datetime as _dt, timedelta as _td

    def _when(v):
        if isinstance(v, _dt):
            return v
        try:
            return _dt.strptime(str(v)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    try:
        now = _when(db.execute_scalar("SELECT GETDATE()")) or _dt.now()   # the SERVER's clock
        rows = db.fetchall(
            "SELECT TOP 20 success, login_time FROM login_history WHERE username=? "
            "ORDER BY login_id DESC", (str(username)[:50],)) or []
    except Exception:
        return 0
    n = 0
    for r in rows:                         # newest first, stop at the last success
        if r.get("success") in (1, True):
            break
        t = _when(r.get("login_time"))
        if t is None or now - t > _td(seconds=int(seconds)):
            break
        n += 1
    return n


# ============================================================
#  Login history
# ============================================================
def log_login(user_id, username, success):
    try:
        if not db.execute_scalar(
                "SELECT COUNT(*) FROM sys.tables WHERE name='login_history'"):
            return
        db.execute(
            "INSERT INTO login_history (user_id, username, success, "
            "workstation) VALUES (?,?,?,?)",
            (user_id, str(username)[:50], 1 if success else 0,
             platform.node()[:100]))
    except Exception:
        pass
