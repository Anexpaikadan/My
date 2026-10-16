# ============================================================
# DayBill ERP - Database Tool (v6.1)   — DayBillERP.exe --dbtool
# ------------------------------------------------------------
#   1. Server & databases   find the SQL Server, list every database
#                           (✓ DayBill / ✗ other program), pick FROM / TO,
#                           make a new DayBill database, open a SQLite file
#   2. Reset password       DayBill users: ask a new password at the next
#                           sign-in, or set one now. Another program's
#                           users: set a new password in the SAME format
#                           (only known formats; a backup is made first)
#   3. Convert to DayBill   read another program's database (never
#                           changed), check, convert: products, barcodes,
#                           categories, customers, suppliers, opening stock
#                           and opening balances
# ============================================================
import os
import queue
import threading
import tkinter as tk
from datetime import date
from tkinter import ttk, messagebox, simpledialog, filedialog

from config import settings as cfg
from config.database import db, load_db_config, save_db_config
from modules import db_convert as CV

NONE = "(none)"


def _label_spec(spec):
    if isinstance(spec, list):
        return " + ".join(spec)
    if isinstance(spec, dict) and spec.get("lookup"):
        lk = spec["lookup"]
        return "%s → %s.%s" % (spec["column"], lk["table"], lk["value"])
    if isinstance(spec, dict) and spec.get("const") is not None:
        return "= %s" % spec["const"]
    return spec or NONE


class DbToolApp:
    def __init__(self, root, sync=False):
        self.root = root
        self.sync = sync                     # tests: run work in the same thread
        self.C = C = cfg.theme()
        root.title("DayBill Database Tool")
        try:
            from ui import zoom
            zoom.apply(root)
        except Exception:
            pass
        root.geometry("1200x740")
        root.minsize(1000, 640)
        root.configure(bg=C["content_bg"])
        self.config = load_db_config()
        self.marked = []                     # [(name, True/False/None)]
        self.src = None                      # source (read only)
        self.src_label = tk.StringVar(value="—")
        self.tgt_name = ""
        self.tgt_label = tk.StringVar(value="—")
        self.shape = None
        self.mapping = {}
        self.program = ""
        self.plan = None
        self._q = queue.Queue()

        head = tk.Frame(root, bg=C["primary"])
        head.pack(fill="x")
        tk.Label(head, text="🛠  DayBill Database Tool", font=("Segoe UI", 16, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16, pady=10)
        tk.Label(head, text="Pick a database · reset a password · bring another program's data into "
                 "DayBill. The other program's database is only read — never changed.",
                 font=("Segoe UI", 9), bg=C["primary"], fg="white").pack(side="left", padx=6)
        bar = tk.Frame(root, bg=C["content_bg"])
        bar.pack(fill="x", padx=14, pady=(8, 0))
        tk.Label(bar, text="FROM (other program):", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        tk.Label(bar, textvariable=self.src_label, font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg="#B45309").pack(side="left", padx=(4, 24))
        tk.Label(bar, text="TO (DayBill):", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        tk.Label(bar, textvariable=self.tgt_label, font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg="#15803D").pack(side="left", padx=4)
        self.status = tk.StringVar(value="Start with 1. Server & databases → Connect.")
        tk.Label(root, textvariable=self.status, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"], anchor="w").pack(side="bottom", fill="x", padx=14, pady=(0, 6))
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=8)
        self.t1 = tk.Frame(self.nb, bg=C["content_bg"])
        self.t2 = tk.Frame(self.nb, bg=C["content_bg"])
        self.t3 = tk.Frame(self.nb, bg=C["content_bg"])
        self.nb.add(self.t1, text="  1. Server & databases  ")
        self.nb.add(self.t2, text="  2. Reset password  ")
        self.nb.add(self.t3, text="  3. Convert to DayBill  ")
        self._build_t1()
        self._build_t2()
        self._build_t3()

    # ── helpers ──────────────────────────────────────────────
    def say(self, txt, ok=True):
        self.status.set(txt)

    def _btn(self, parent, text, cmd, primary=False, danger=False, side="left"):
        C = self.C
        bg = C["primary"] if primary else ("#DC2626" if danger else C["card_bg"])
        b = tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 9, "bold" if primary else "normal"),
                      bg=bg, fg="white" if (primary or danger) else C["text_primary"], relief="flat",
                      padx=12, pady=5, cursor="hand2", highlightthickness=1,
                      highlightbackground=C["border"])
        b.pack(side=side, padx=4, pady=3)
        return b

    def _tree(self, parent, cols, height=10):
        f = tk.Frame(parent, bg=self.C["content_bg"])
        f.pack(fill="both", expand=True)
        t = ttk.Treeview(f, columns=[c[0] for c in cols], show="headings", height=height)
        for key, title, w, anchor in cols:
            t.heading(key, text=title)
            t.column(key, width=w, anchor=anchor, stretch=True)
        sb = ttk.Scrollbar(f, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return t

    def _bg(self, work, done):
        """Run `work` away from the screen; `done(result, error)` after."""
        if self.sync:
            try:
                r, e = work(), None
            except Exception as ex:
                r, e = None, ex
            done(r, e)
            return

        def run():
            try:
                self._q.put((done, work(), None))
            except Exception as ex:
                self._q.put((done, None, ex))
        threading.Thread(target=run, daemon=True).start()
        self.root.after(120, self._poll)

    def _poll(self):
        try:
            done, r, e = self._q.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll)
            return
        done(r, e)

    def _conf(self, database=None):
        c = dict(self.config)
        c.update(server=self.server_var.get().strip() or c.get("server"),
                 auth_type=self.auth_var.get(), username=self.user_var.get(),
                 password=self.pass_var.get())
        if database:
            c["database"] = database
        return c

    # ── 1. server & databases ────────────────────────────────
    def _build_t1(self):
        C, p = self.C, self.t1
        box = tk.Frame(p, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="x", padx=8, pady=8)
        row = tk.Frame(box, bg=C["card_bg"]); row.pack(fill="x", padx=10, pady=8)
        tk.Label(row, text="SQL Server", font=("Segoe UI", 9, "bold"), bg=C["card_bg"]).pack(side="left")
        self.server_var = tk.StringVar(value=self.config.get("server", "localhost\\SQLEXPRESS"))
        self.server_combo = ttk.Combobox(row, textvariable=self.server_var, width=30)
        self.server_combo.pack(side="left", padx=6)
        self._btn(row, "🔍 Find", self._find)
        self.auth_var = tk.StringVar(value=self.config.get("auth_type", "windows"))
        tk.Radiobutton(row, text="Windows sign-in", variable=self.auth_var, value="windows",
                       bg=C["card_bg"]).pack(side="left", padx=(16, 2))
        tk.Radiobutton(row, text="SQL login", variable=self.auth_var, value="sql",
                       bg=C["card_bg"]).pack(side="left")
        self.user_var = tk.StringVar(value=self.config.get("username", ""))
        self.pass_var = tk.StringVar(value=self.config.get("password", ""))
        tk.Label(row, text="SQL user", bg=C["card_bg"]).pack(side="left", padx=(10, 2))
        tk.Entry(row, textvariable=self.user_var, width=10).pack(side="left")
        tk.Label(row, text="Password", bg=C["card_bg"]).pack(side="left", padx=(8, 2))
        tk.Entry(row, textvariable=self.pass_var, width=12, show="●").pack(side="left")
        row2 = tk.Frame(box, bg=C["card_bg"]); row2.pack(fill="x", padx=10, pady=(0, 8))
        self._btn(row2, "Connect & list databases", self._list, primary=True)
        tk.Label(row2, text="(the same server and sign-in DayBill uses — SQL user / password only for "
                 "'SQL login')", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=8)
        self.db_tree = self._tree(p, [("name", "Database", 320, "w"), ("kind", "What is it", 260, "w")],
                                  height=14)
        acts = tk.Frame(p, bg=C["content_bg"]); acts.pack(fill="x", padx=8, pady=6)
        self._btn(acts, "⬅ Use as FROM (other program)", self._use_from)
        self._btn(acts, "➡ Use as TO (DayBill)", self._use_to, primary=True)
        self._btn(acts, "🆕 New DayBill database…", self._new_db)
        self._btn(acts, "📂 Open a SQLite file (e.g. Aronium)…", self._open_file)
        tk.Label(p, text="Tip: restore the other program's .bak under a NEW name first (DayBill login ▸ "
                 "Database Settings ▸ ♻ Restore), then pick it here as FROM.", font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=12)

    def _find(self):
        conf = self._conf()
        self.say("🔍 Looking for SQL Server on this PC and the network…")

        def work():
            from modules.db_finder import find_servers
            return find_servers(conf)

        def done(found, err):
            if err or not found:
                self.say("❌ No SQL Server let us in — is the SQL Server service running? Try the "
                         "other sign-in.", ok=False)
                return
            names = [n for n, _v in found]
            self.server_combo["values"] = names
            if self.server_var.get().strip().lower() not in [n.lower() for n in names]:
                self.server_var.set(names[0])
            self.say("✅ SQL Server found: %s — press Connect & list databases." % ", ".join(names))
        self._bg(work, done)

    def _list(self):
        conf = self._conf()
        keep = dict(load_db_config())        # DayBill keeps its own database choice
        keep.update(server=conf["server"], auth_type=conf["auth_type"],
                    username=conf["username"], password=conf["password"])
        save_db_config(keep)
        self.config = keep
        self.say("Reading the databases on %s …" % conf["server"])

        def work():
            from modules.db_backup import list_databases_marked
            return list_databases_marked()

        def done(res, err):
            marked, msg = (res or ([], str(err)[:200]))
            if msg:
                self.say("❌ " + msg, ok=False)
                return
            self.marked = marked
            self.db_tree.delete(*self.db_tree.get_children())
            for n, ok in marked:
                self.db_tree.insert("", "end", iid=n, values=(
                    n, "✓ DayBill database" if ok else ("✗ another program" if ok is False else "? can't look")))
            self._fill_db_combos()
            self.say("✅ %d database(s). Pick the other program's one → Use as FROM, and a DayBill one "
                     "→ Use as TO." % len(marked))
        self._bg(work, done)

    def _sel_db(self):
        s = self.db_tree.selection()
        if not s:
            messagebox.showwarning("Database", "Pick a database in the list first.", parent=self.root)
            return None
        return s[0]

    def _kind(self, name):
        return next((ok for n, ok in self.marked if n == name), None)

    def _use_from(self, name=None):
        name = name or self._sel_db()
        if not name:
            return
        if self._kind(name) is True and not messagebox.askyesno(
                "FROM", "'%s' is a DayBill database. Use it as FROM anyway (to copy one DayBill "
                "into another)?" % name, parent=self.root):
            return
        try:
            src = CV.open_mssql(self._conf(), name)
        except Exception as e:
            messagebox.showerror("FROM", "Could not open '%s':\n%s" % (name, str(e)[:300]), parent=self.root)
            return
        self._set_source(src, name)

    def _set_source(self, src, label):
        if self.src is not None:
            try:
                self.src.close()
            except Exception:
                pass
        self.src = src
        self.src_label.set(label)
        self.shape, self.mapping, self.plan = None, {}, None
        self.say("FROM = %s. Now 3. Convert to DayBill → 🔎 Read the old database." % label)

    def _open_file(self):
        p = filedialog.askopenfilename(parent=self.root, title="Another program's SQLite database",
                                       filetypes=[("SQLite database", "*.db *.sqlite *.sqlite3 *.db3"),
                                                  ("All files", "*.*")])
        if not p:
            return
        try:
            self._set_source(CV.open_sqlite(p), os.path.basename(p))
        except Exception as e:
            messagebox.showerror("Open", str(e)[:300], parent=self.root)

    def _use_to(self, name=None):
        name = name or self._sel_db()
        if not name:
            return
        if self._kind(name) is not True:
            messagebox.showwarning("TO", "'%s' is not a DayBill database. Pick one marked ✓, or make "
                                   "one with 🆕 New DayBill database." % name, parent=self.root)
            return
        if not self._connect_target(name):
            return
        self.tgt_name = name
        self.tgt_label.set(name)
        self.say("TO = %s (DayBill)." % name)

    def _connect_target(self, name):
        conf = self._conf(name)
        if not db.connect(conf):
            messagebox.showerror("TO", "Could not open '%s'." % name, parent=self.root)
            return False
        if db.is_daybill() is False:
            messagebox.showwarning("TO", "'%s' is not a DayBill database." % name, parent=self.root)
            return False
        return True

    def _new_db(self):
        name = simpledialog.askstring("New DayBill database", "Name of the new database (letters, "
                                      "numbers, _ or -):", parent=self.root)
        if not name or not name.strip():
            return
        from modules import db_backup as BK
        script = BK.find_install_script()
        if not script:
            messagebox.showerror("New database", "database\\INSTALL_DayBillERP_AllInOne.sql is missing.",
                                 parent=self.root)
            return
        self.say("⏳ Making the DayBill database '%s' — this can take a minute…" % name)

        def work():
            return BK.create_database(name.strip(), install_script=script)

        def done(res, err):
            ok, msg = res if res else (False, str(err)[:200])
            self.say(("✅ " if ok else "❌ ") + msg.split("\n")[0], ok=ok)
            if ok:
                clean = "".join(ch for ch in name.strip() if ch.isalnum() or ch in "_-")
                self.marked.append((clean, True))
                self.db_tree.insert("", "end", iid=clean, values=(clean, "✓ DayBill database (new)"))
                self._fill_db_combos()
                self._use_to(clean)
        self._bg(work, done)

    # ── 2. reset password ────────────────────────────────────
    def _build_t2(self):
        C, p = self.C, self.t2
        top = tk.Frame(p, bg=C["content_bg"]); top.pack(fill="x", padx=8, pady=8)
        tk.Label(top, text="Database", font=("Segoe UI", 9, "bold"), bg=C["content_bg"]).pack(side="left")
        self.pw_db = tk.StringVar()
        self.pw_combo = ttk.Combobox(top, textvariable=self.pw_db, width=34, state="readonly")
        self.pw_combo.pack(side="left", padx=6)
        self._btn(top, "Show its users", self._show_users, primary=True)
        self.pw_info = tk.StringVar(value="Pick a database and press Show its users.")
        tk.Label(p, textvariable=self.pw_info, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"], anchor="w", justify="left", wraplength=1100).pack(fill="x", padx=12)
        self.user_tree = self._tree(p, [("user", "User", 220, "w"), ("name", "Name / table", 260, "w"),
                                        ("state", "Active", 80, "center"),
                                        ("fmt", "Password kept as", 200, "w")], height=13)
        acts = tk.Frame(p, bg=C["content_bg"]); acts.pack(fill="x", padx=8, pady=6)
        self.btn_reset = self._btn(acts, "🔑 Ask a new password at the next sign-in", self._pw_reset, primary=True)
        self.btn_setpw = self._btn(acts, "Set a new password now…", self._pw_set)
        self.owner_var = tk.BooleanVar(value=False)
        tk.Checkbutton(p, text="I am the owner of this data, or the owner allowed me (needed for another "
                       "program's database — a backup of it is made first)", variable=self.owner_var,
                       bg=C["content_bg"]).pack(anchor="w", padx=12)
        self._pw_mode = None                 # "daybill" | "other"
        self._pw_rows = {}

    def _fill_db_combos(self):
        names = [n for n, _ok in self.marked]
        self.pw_combo["values"] = names
        if names and not self.pw_db.get():
            mine = [n for n, ok in self.marked if ok]
            self.pw_db.set(mine[0] if mine else names[0])

    def _pw_conn(self, name):
        from modules.db_backup import _connect
        return _connect(name)

    def _show_users(self):
        name = self.pw_db.get().strip()
        if not name:
            return
        self.user_tree.delete(*self.user_tree.get_children())
        self._pw_rows = {}
        try:
            cn = self._pw_conn(name)
        except Exception as e:
            self.pw_info.set("❌ Could not open '%s': %s" % (name, str(e)[:200]))
            return
        try:
            cur = cn.cursor()
            from config.database import DAYBILL_CHECK_SQL
            cur.execute(DAYBILL_CHECK_SQL)
            is_day = bool(cur.fetchone()[0])
            if is_day:
                self._pw_mode = "daybill"
                cur.execute("SELECT username, full_name_en, is_active, password_hash FROM users ORDER BY username")
                for u, fn, act, h in cur.fetchall():
                    self._pw_rows[u] = {"user": u}
                    self.user_tree.insert("", "end", iid="u:" + u, values=(
                        u, fn or "", "yes" if act in (1, True) else "no",
                        "asks for a new one" if CV.hash_kind(h) in ("reset", "plain text?", "empty")
                        and not str(h or "").startswith("$") else "salted (safe)"))
                self.pw_info.set("'%s' is a DayBill database. Pick a user → 🔑 Ask a new password at the "
                                 "next sign-in (they sign in with any password, then choose a new one), "
                                 "or Set a new password now." % name)
            else:
                self._pw_mode = "other"
                sh = CV.Shape(CV.MssqlSource(cn, name), sample_rows=50)
                found = CV.find_user_tables(sh)
                for t, uc, pc in found:
                    for r in CV.MssqlSource(cn, name).rows(t, [uc, pc], limit=500):
                        u = str(r.get(uc))
                        kind = CV.hash_kind(r.get(pc))
                        key = "%s|%s" % (t, u)
                        self._pw_rows[key] = {"table": t, "ucol": uc, "pcol": pc, "user": r.get(uc),
                                              "old": r.get(pc), "kind": kind}
                        self.user_tree.insert("", "end", iid="o:" + key, values=(u, t, "", kind))
                self.pw_info.set(("'%s' belongs to another program. Its sign-in table%s: %s. Only the "
                                  "formats shown can be set (in the same format); the password itself is "
                                  "never shown. A backup of the database is made first." %
                                  (name, "s" if len(found) > 1 else "", ", ".join(t for t, _u, _p in found)))
                                 if found else "'%s' belongs to another program and no sign-in table "
                                 "(user + password columns) was found." % name)
        except Exception as e:
            self.pw_info.set("❌ %s" % str(e)[:250])
        finally:
            try:
                cn.close()
            except Exception:
                pass

    def _pw_pick(self):
        s = self.user_tree.selection()
        if not s:
            messagebox.showwarning("Password", "Pick a user first.", parent=self.root)
            return None
        return self._pw_rows.get(s[0][2:])

    def _pw_reset(self):
        r = self._pw_pick()
        if not r:
            return
        if self._pw_mode != "daybill":
            messagebox.showinfo("Password", "For another program's users use Set a new password now.",
                                parent=self.root)
            return
        name = self.pw_db.get()
        cn = self._pw_conn(name)
        try:
            cur = cn.cursor()
            cur.execute("UPDATE users SET password_hash=?, is_active=1 WHERE username=?", ("RESET", r["user"]))
            try:
                cur.execute("DELETE FROM login_history WHERE username=? AND success=0", (r["user"],))
            except Exception:
                pass
        finally:
            cn.close()
        self.say("✅ '%s' signs in with any password next time, then chooses a new one." % r["user"])
        self._show_users()

    def _ask_new_pw(self, user):
        a = simpledialog.askstring("New password", "New password for '%s' (at least 4 characters):" % user,
                                   show="●", parent=self.root)
        if not a:
            return None
        b = simpledialog.askstring("New password", "Type it again:", show="●", parent=self.root)
        if a != b:
            messagebox.showwarning("New password", "The two passwords are different.", parent=self.root)
            return None
        if len(a) < 4:
            messagebox.showwarning("New password", "At least 4 characters, please.", parent=self.root)
            return None
        return a

    def _pw_set(self):
        r = self._pw_pick()
        if not r:
            return
        name = self.pw_db.get()
        if self._pw_mode == "daybill":
            pw = self._ask_new_pw(r["user"])
            if not pw:
                return
            from modules import permissions as P
            cn = self._pw_conn(name)
            try:
                cn.cursor().execute("UPDATE users SET password_hash=?, is_active=1 WHERE username=?",
                                    (P.hash_password(pw), r["user"]))
            finally:
                cn.close()
            self.say("✅ New password saved for '%s'." % r["user"])
            self._show_users()
            return
        # another program's database
        if not self.owner_var.get():
            messagebox.showwarning("Password", "Tick 'I am the owner of this data…' first.", parent=self.root)
            return
        try:
            CV.new_password_value(r["kind"], r["old"], "x")
        except ValueError as e:
            messagebox.showwarning("Password", "%s\n\nUse that program's own reset, or ask its maker." % e,
                                   parent=self.root)
            return
        pw = self._ask_new_pw(r["user"])
        if not pw:
            return
        from modules import db_backup as BK
        ok, where = BK.backup_database(name, note="before_password_change")
        if not ok:
            messagebox.showerror("Password", "A backup of '%s' could not be made — nothing was changed.\n\n%s"
                                 % (name, where), parent=self.root)
            return
        value = CV.new_password_value(r["kind"], r["old"], pw)
        cn = self._pw_conn(name)
        try:
            cn.cursor().execute("UPDATE %s SET %s=? WHERE %s=?" % (CV._q(r["table"]), CV._q(r["pcol"]),
                                                                  CV._q(r["ucol"])), (value, r["user"]))
        finally:
            cn.close()
        try:
            from config.paths import log_file
            with open(log_file("dbtool_passwords.txt"), "a", encoding="utf-8") as f:
                f.write("%s  %s.%s user %s: new password set (%s) by the owner; backup %s\n"
                        % (date.today(), name, r["table"], r["user"], r["kind"], where))
        except Exception:
            pass
        messagebox.showinfo("Password", "New password set for '%s' in %s (same format: %s).\n\nA backup "
                            "was made first:\n%s" % (r["user"], name, r["kind"], where), parent=self.root)
        self._show_users()

    # ── 3. convert ───────────────────────────────────────────
    def _build_t3(self):
        C, p = self.C, self.t3
        top = tk.Frame(p, bg=C["content_bg"]); top.pack(fill="x", padx=8, pady=(6, 0))
        self._btn(top, "🔎 Read the old database", self._scan, primary=True)
        self.found_var = tk.StringVar(value="Pick FROM and TO on page 1, then read it.")
        tk.Label(p, textvariable=self.found_var, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"], anchor="w").pack(fill="x", padx=14)
        panes = ttk.Panedwindow(p, orient="vertical")
        panes.pack(fill="both", expand=True, padx=8, pady=(2, 0))
        mid = tk.Frame(panes, bg=C["content_bg"])
        low = tk.Frame(panes, bg=C["content_bg"])
        panes.add(mid, weight=5)
        panes.add(low, weight=2)
        left = tk.Frame(mid, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(mid, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        right.pack(side="right", fill="y", padx=(8, 0))
        # what to map
        er = tk.Frame(left, bg=C["card_bg"]); er.pack(fill="x", padx=8, pady=(6, 2))
        self.ent_var = tk.StringVar(value="products")
        for e in CV.ENTITIES:
            tk.Radiobutton(er, text=CV.ENTITY_TITLES[e], variable=self.ent_var, value=e, indicatoron=False,
                           padx=10, pady=3, bg=C["card_bg"], selectcolor=C.get("primary_light", "#DBEAFE"),
                           command=self._show_entity).pack(side="left", padx=2)
        tk.Label(er, text="Old table", font=("Segoe UI", 9, "bold"), bg=C["card_bg"]).pack(side="left", padx=(16, 4))
        self.table_var = tk.StringVar()
        self.table_combo = ttk.Combobox(er, textvariable=self.table_var, width=30, state="readonly")
        self.table_combo.pack(side="left")
        self.table_combo.bind("<<ComboboxSelected>>", lambda e: self._table_changed())
        self.where_var = tk.StringVar(value="")
        tk.Label(er, textvariable=self.where_var, bg=C["card_bg"], fg=C["text_secondary"],
                 font=("Segoe UI", 8)).pack(side="left", padx=6)
        # the field grid scrolls (small screens: 1366 × 768)
        gwrap = tk.Frame(left, bg=C["card_bg"]); gwrap.pack(fill="both", expand=True, padx=8, pady=2)
        canvas = tk.Canvas(gwrap, bg=C["card_bg"], highlightthickness=0)
        gsb = ttk.Scrollbar(gwrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=gsb.set)
        gsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.grid = tk.Frame(canvas, bg=C["card_bg"])
        canvas.create_window((0, 0), window=self.grid, anchor="nw")
        self.grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self._grid_canvas = canvas
        self._field_vars = {}
        # options
        tk.Label(right, text="Options", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=10, pady=(6, 0))
        self.opt_incl = tk.BooleanVar(value=True)
        self.opt_stock = tk.BooleanVar(value=True)
        self.opt_bal = tk.BooleanVar(value=True)
        for txt, var in (("Old sell prices include VAT", self.opt_incl),
                         ("Stock on hand → opening stock", self.opt_stock),
                         ("Customer / supplier balances", self.opt_bal)):
            tk.Checkbutton(right, text=txt, variable=var, bg=C["card_bg"]).pack(anchor="w", padx=8)
        r1 = tk.Frame(right, bg=C["card_bg"]); r1.pack(fill="x", padx=10, pady=(4, 0))
        tk.Label(r1, text="VAT if none", bg=C["card_bg"]).pack(side="left")
        self.opt_vat = tk.StringVar(value="S  15%")
        ttk.Combobox(r1, textvariable=self.opt_vat, state="readonly", width=13,
                     values=["S  15%", "Z  zero-rated", "E  exempt"]).pack(side="left", padx=4)
        r2 = tk.Frame(right, bg=C["card_bg"]); r2.pack(fill="x", padx=10, pady=(4, 0))
        tk.Label(r2, text="Opening date", bg=C["card_bg"]).pack(side="left")
        self.opt_date = tk.StringVar(value="")
        tk.Entry(r2, textvariable=self.opt_date, width=12).pack(side="left", padx=4)
        tk.Label(right, text="YYYY-MM-DD · empty = keep DayBill's", font=("Segoe UI", 7), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=10)
        r3 = tk.Frame(right, bg=C["card_bg"]); r3.pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(r3, text="Your name", bg=C["card_bg"]).pack(side="left")
        self.op_name = tk.StringVar(value="")
        tk.Entry(r3, textvariable=self.op_name, width=16).pack(side="left", padx=4)
        self.conv_owner = tk.BooleanVar(value=False)
        tk.Checkbutton(right, text="I am the owner of this data,\nor the owner allowed me",
                       variable=self.conv_owner, bg=C["card_bg"], justify="left").pack(anchor="w", padx=8, pady=4)
        # actions (top row, right) + results (always visible)
        self.btn_equity = self._btn(top, "Close openings to capital", self._close_equity, side="right")
        self.btn_convert = self._btn(top, "⬇ Convert into DayBill", self._convert, primary=True, side="right")
        self._btn(top, "💾 Save map", self._save_map, side="right")
        self._btn(top, "✔ Check", self._check, side="right")
        self._btn(top, "👁 Preview", self._preview, side="right")
        acts = tk.Frame(low, bg=C["content_bg"]); acts.pack(fill="x", pady=(2, 0))
        self._btn(acts, "Export the problems (CSV)…", self._export_issues, side="right")
        self.sum_var = tk.StringVar(value="")
        tk.Label(low, textvariable=self.sum_var, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"], anchor="w", justify="left", wraplength=1100).pack(fill="x", padx=4)
        self.res_tree = self._tree(low, [("a", "", 110, "w"), ("b", "", 150, "w"), ("c", "", 150, "w"),
                                         ("d", "", 180, "w"), ("e", "", 420, "w")], height=5)

    def _options(self):
        return {"prices_include_vat": bool(self.opt_incl.get()), "import_stock": bool(self.opt_stock.get()),
                "import_balances": bool(self.opt_bal.get()), "default_vat": self.opt_vat.get()[:1],
                "default_unit": "PCs", "opening_date": self.opt_date.get().strip()}

    def _scan(self):
        if self.src is None:
            messagebox.showwarning("Convert", "Pick FROM first (page 1).", parent=self.root)
            return
        self.say("🔎 Reading the old database …")
        src = self.src

        def work():
            sh = CV.Shape(src)
            m, how = CV.guess_mapping(sh)
            return sh, m, how

        def done(res, err):
            if err:
                self.say("❌ %s" % str(err)[:250], ok=False)
                return
            self.shape, self.mapping, self.program = res
            n = len(self.shape.tables)
            how = self.program
            self.found_var.set(("Recognised: %s ✓" % how) if how not in ("guessed", "saved") else
                               ("Your saved map ✓" if how == "saved" else
                                "Unknown program — guessed. Check each column."))
            tabs = ["%s  (%d rows)" % (t, c_) for t, c_ in sorted(self.shape.tables.items())]
            self._table_labels = {lab: t for lab, t in zip(tabs, sorted(self.shape.tables))}
            self.table_combo["values"] = [NONE] + tabs
            self._show_entity()
            self.say("✅ %d tables read from %s. Check each tab (Products, Extra barcodes, Customers, "
                     "Suppliers), then ✔ Check." % (n, self.src_label.get()))
        self._bg(work, done)

    def _label_of(self, t):
        return next((lab for lab, tt in getattr(self, "_table_labels", {}).items() if tt == t), NONE)

    def _show_entity(self):
        for w in self.grid.winfo_children():
            w.destroy()
        self._field_vars = {}
        if not self.shape:
            return
        ent = self.ent_var.get()
        em = self.mapping.get(ent)
        self.table_var.set(self._label_of(em["table"]) if em else NONE)
        self.where_var.set(("%s = %s" % tuple(em["where"])) if em and em.get("where") else "all rows")
        if not em:
            tk.Label(self.grid, text="Not taken from the old database. Pick its table above if it has one.",
                     bg=self.C["card_bg"], fg=self.C["text_secondary"]).grid(row=0, column=0, sticky="w")
            return
        scores = CV.score_columns(self.shape, em["table"], ent)
        cols = [NONE] + self.shape.colnames(em["table"])
        smp = self.shape.sample(em["table"])
        hdr = ("DayBill field", "Old column", "Sure?", "Example values")
        for ci, h in enumerate(hdr):
            tk.Label(self.grid, text=h, font=("Segoe UI", 8, "bold"), bg=self.C["card_bg"],
                     fg=self.C["text_secondary"]).grid(row=0, column=ci, sticky="w", padx=4)
        for ri, (f, label) in enumerate(CV.FIELDS[ent], 1):
            spec = em["fields"].get(f)
            tk.Label(self.grid, text=label, bg=self.C["card_bg"], anchor="w").grid(row=ri, column=0, sticky="w", padx=4)
            var = tk.StringVar(value=_label_spec(spec) if spec else NONE)
            vals = list(cols)
            if spec and not isinstance(spec, str):
                vals = [_label_spec(spec)] + vals
            cb = ttk.Combobox(self.grid, textvariable=var, values=vals, width=30, state="readonly")
            cb.grid(row=ri, column=1, sticky="w", padx=4, pady=1)
            cb.bind("<<ComboboxSelected>>", lambda e, f_=f, v_=var, s_=spec: self._field_changed(f_, v_, s_))
            self._field_vars[f] = var
            conf = ""
            if isinstance(spec, str):
                sc = next((s for s, c_, _w in scores.get(f, []) if c_ == spec), None)
                conf = "%d%%" % (sc * 100) if sc is not None else "you"
            elif spec:
                conf = "map"
            colr = "#15803D" if conf in ("map", "you") or (conf.endswith("%") and int(conf[:-1]) >= 80) else \
                ("#B45309" if conf.endswith("%") and int(conf[:-1]) >= 50 else "#B91C1C")
            tk.Label(self.grid, text=conf, fg=colr if conf else self.C["text_secondary"], bg=self.C["card_bg"],
                     font=("Segoe UI", 9, "bold")).grid(row=ri, column=2, sticky="w", padx=4)
            ex = ""
            if isinstance(spec, str):
                ex = " · ".join(str(r.get(spec))[:18] for r in smp[:4] if r.get(spec) not in (None, ""))
            elif isinstance(spec, list):
                ex = " · ".join(" ".join(str(r.get(c) or "") for c in spec)[:24] for r in smp[:3])
            tk.Label(self.grid, text=ex, fg=self.C["text_secondary"], bg=self.C["card_bg"],
                     font=("Segoe UI", 8)).grid(row=ri, column=3, sticky="w", padx=4)

    def _field_changed(self, field, var, spec):
        ent = self.ent_var.get()
        v = var.get()
        em = self.mapping.setdefault(ent, {"table": None, "where": None, "fields": {}})
        if v == NONE:
            em["fields"].pop(field, None)
        elif spec is not None and v == _label_spec(spec):
            em["fields"][field] = spec
        else:
            em["fields"][field] = v
        self.plan = None
        self._show_entity()

    def _table_changed(self):
        ent = self.ent_var.get()
        lab = self.table_var.get()
        if lab == NONE:
            self.mapping.pop(ent, None)
        else:
            t = self._table_labels[lab]
            self.mapping[ent] = CV.guess_entity(self.shape, ent, t)
        self.plan = None
        self._show_entity()

    def _prepare(self):
        if not self.shape:
            messagebox.showwarning("Convert", "Press 🔎 Read the old database first.", parent=self.root)
            return None
        p = CV.prepare(self.src, self.mapping, self._options())
        p.program = self.program
        p.source = self.src_label.get()
        self.plan = p
        return p

    def _show_rows(self, heads, rows):
        t = self.res_tree
        t.delete(*t.get_children())
        keys = ("a", "b", "c", "d", "e")
        for k, h in zip(keys, list(heads) + [""] * 5):
            t.heading(k, text=h)
        for r in rows:
            t.insert("", "end", values=[str(x) for x in r][:5])

    def _preview(self):
        p = self._prepare()
        if not p:
            return
        ent = self.ent_var.get()
        recs = p.preview(ent, 30)
        if ent == "products":
            self._show_rows(("Code", "Barcode", "Name", "Price · cost · VAT", "Category · unit · stock"),
                            [(r["code"], r["barcode"], "%s | %s" % (r["name_en"], r["name_ar"]),
                              "%s · %s · %s" % (r["price"], r["cost"], r["vat"]),
                              "%s · %s · %s%s" % (r["category"], r["unit"], r["qty"], "" if r["active"] else " · inactive"))
                             for r in recs])
        elif ent == "barcodes":
            self._show_rows(("Product code", "Extra barcode"), [(r["code"], r["barcode"]) for r in recs])
        else:
            self._show_rows(("Code", "Name", "Phone · e-mail", "VAT number", "Balance"),
                            [(r["code"], "%s | %s" % (r["name_en"], r["name_ar"]), "%s %s" % (r["phone"], r["email"]),
                              r["vat_no"], r["balance"]) for r in recs])
        self.sum_var.set("Preview of the first %d %s exactly as they will be in DayBill (of %d)."
                         % (len(recs), CV.ENTITY_TITLES[ent].lower(), len(p.records[ent])))

    def _check(self):
        p = self._prepare()
        if not p:
            return None
        tgt = {}
        if self.tgt_name:
            try:
                tgt = CV.check_target(p)
            except Exception as e:
                tgt = {"error": str(e)[:120]}
        c = p.counts()
        self._show_rows(("Level", "Data", "Record", "Code", "Problem"), [i.row() for i in p.issues])
        self.sum_var.set(
            "Will bring: %d products%s · %d extra barcodes · %d customers · %d suppliers.   Stock value "
            "%.2f · customers owe %.2f · we owe suppliers %.2f.   Problems: %d errors (skipped), %d "
            "warnings (fixed as shown)." % (
                c["products"], (" (%d new, %d updated)" % (tgt.get("new", 0), tgt.get("update", 0)))
                if tgt.get("new") is not None else "", c["barcodes"], c["customers"], c["suppliers"],
                c["stock_value"], c["receivable"], c["payable"], c["errors"], c["warnings"]))
        return p

    def _save_map(self):
        if not self.shape:
            return
        path = CV.save_mapping(self.shape, self.mapping, self.src_label.get())
        self.say("💾 Map saved — the next database with the same tables opens with it: %s" % path)

    def _export_issues(self):
        if not self.plan:
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            initialfile="daybill_convert_problems.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            self.plan.issues_csv(path)
            self.say("Saved: %s" % path)

    def _convert(self):
        if not self.tgt_name:
            messagebox.showwarning("Convert", "Pick TO (a DayBill database) on page 1 first.", parent=self.root)
            return
        if not self.conv_owner.get() or not self.op_name.get().strip():
            messagebox.showwarning("Convert", "Type your name and tick 'I am the owner of this data, or the "
                                   "owner allowed me'.", parent=self.root)
            return
        p = self._check()
        if not p:
            return
        c = p.counts()
        if not messagebox.askyesno(
                "Convert into DayBill",
                "Bring into '%s':\n\n  %d products (+ %d extra barcodes)\n  %d customers, %d suppliers\n"
                "  opening stock value %.2f\n  balances: customers %.2f · suppliers %.2f\n\n"
                "%d records with errors are skipped (see the list). A backup of '%s' is made first.\n"
                "The old database is not changed. Go ahead?" % (
                    self.tgt_name, c["products"], c["barcodes"], c["customers"], c["suppliers"],
                    c["stock_value"], c["receivable"], c["payable"], c["errors"], self.tgt_name),
                parent=self.root):
            return
        from modules import db_backup as BK
        self.say("💾 Backing up '%s' first …" % self.tgt_name)
        okb, where = BK.backup_database(self.tgt_name, note="before_convert")
        if not okb and not messagebox.askyesno(
                "Backup", "The backup could not be made:\n%s\n\nConvert anyway?" % where, parent=self.root):
            return
        opts, op = self._options(), self.op_name.get().strip()
        prog = []

        def work():
            return CV.apply(p, opts, progress=prog.append, operator=op)

        def done(res, err):
            if err:
                self.say("❌ Stopped: %s — the backup is %s" % (str(err)[:200], where if okb else "-"), ok=False)
                messagebox.showerror("Convert", "Stopped:\n%s" % str(err)[:400], parent=self.root)
                return
            self.last_result = res
            errs = res.get("errors") or []
            self._show_rows(("Result", "", "", "", "Details"),
                            [("products", "new %d" % res["inserted"], "updated %d" % res["updated"], "", ""),
                             ("barcodes", res["barcodes"], "", "", ""),
                             ("customers", res["customers"], "", "", ""),
                             ("suppliers", res["suppliers"], "", "", ""),
                             ("equity", "%.2f" % (res.get("equity") or 0), "", "", "Opening Balance Equity")]
                            + [("error", "", "", "", e) for e in errs])
            self.sum_var.set("✅ Converted into '%s'. Opening Balance Equity now %.2f — when all openings are in, "
                             "press 'Close opening balances to capital'. Log: %s" % (
                                 self.tgt_name, res.get("equity") or 0, res.get("log")))
            self.say("✅ Done. Backup made first: %s" % (where if okb else "none"))
            if load_db_config().get("database") != self.tgt_name and messagebox.askyesno(
                    "DayBill", "Make DayBill open '%s' from now on?" % self.tgt_name, parent=self.root):
                conf = load_db_config()
                conf["database"] = self.tgt_name
                save_db_config(conf)
        self.say("⏳ Converting … (the screen comes back when it is done)")
        self._bg(work, done)

    def _close_equity(self):
        if not self.tgt_name:
            return
        from modules import opening_balances as OB
        amt = OB.equity_balance()
        if abs(amt) < 0.005:
            self.say("Opening Balance Equity is already zero.")
            return
        if not messagebox.askyesno("Capital", "Move %.2f from Opening Balance Equity to Owner's Capital?"
                                   % amt, parent=self.root):
            return
        jid = OB.move_equity_to_capital()
        self.say("✅ Moved to Owner's Capital." if jid else "❌ %s" % OB.last_error)


def main():
    from config import language
    cfg.load_settings()
    try:
        language.load_language(cfg.get("language", "en") or "en")
    except Exception:
        pass
    root = tk.Tk()
    try:
        from config.paths import res
        root.iconbitmap(res("assets", "app.ico"))
    except Exception:
        pass
    try:
        from ui.ui_kit import apply_modern_theme
        apply_modern_theme(root)
    except Exception:
        pass
    DbToolApp(root)
    root.mainloop()
