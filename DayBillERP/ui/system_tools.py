# ============================================================
# DayBill ERP - System tools (v7.12.0)
#   lock_screen(root)          🔒 hides DayBill until the user's password
#                              (or another user's) is typed — Ctrl+L
#   DeleteInactiveDialog(root) clears old DRAFT / CANCELLED documents
#   change_counter(root)       which counter this PC is
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

from config import settings as cfg
from config.database import db
from modules import permissions as perm

_LOCK = {"win": None}


def _check(username, password):
    """The user row when username + password are right, else None."""
    try:
        r = db.fetchone("SELECT user_id, username, full_name_en, password_hash, is_active "
                        "FROM users WHERE username=?", (username,))
    except Exception:
        r = None
    if not r or not r.get("is_active", 1):
        return None
    return r if perm.verify_password(password, r.get("password_hash")) else None


def lock_screen(root):
    """A full cover over DayBill. Open windows and bills stay as they
    were; only the right password opens it again."""
    if _LOCK["win"] is not None:
        try:
            _LOCK["win"].lift()
            return _LOCK["win"]
        except Exception:
            _LOCK["win"] = None
    C = cfg.theme()
    me = perm.session_user() or {}
    uname = me.get("username") or ""
    w = tk.Toplevel(root)
    _LOCK["win"] = w
    w.title("DayBill ERP — locked")
    w.configure(bg="#0F172A")
    w.geometry("%dx%d+0+0" % (root.winfo_screenwidth(), root.winfo_screenheight()))
    try:
        w.attributes("-fullscreen", True)
    except Exception:
        pass
    try:
        w.attributes("-topmost", True)
    except Exception:
        pass
    w.protocol("WM_DELETE_WINDOW", lambda: None)     # Alt+F4 does not open it
    hidden = []
    for t in root.winfo_children():                  # floating forms go behind the cover
        if isinstance(t, tk.Toplevel) and t is not w:
            try:
                if t.winfo_viewable():
                    t.withdraw()
                    hidden.append(t)
            except Exception:
                pass
    card = tk.Frame(w, bg="white", padx=34, pady=26)
    card.place(relx=0.5, rely=0.45, anchor="center")
    tk.Label(card, text="🔒", font=("Segoe UI Emoji", 34), bg="white").pack()
    tk.Label(card, text="DayBill is locked", font=("Segoe UI", 16, "bold"), bg="white",
             fg="#0F172A").pack(pady=(4, 0))
    tk.Label(card, text="البرنامج مقفل", font=("Segoe UI", 11), bg="white",
             fg="#475569").pack()
    clock = tk.Label(card, font=("Segoe UI", 10), bg="white", fg="#64748B")
    clock.pack(pady=(2, 12))
    f = tk.Frame(card, bg="white")
    f.pack()
    user_v, pw_v, msg_v = tk.StringVar(value=uname), tk.StringVar(), tk.StringVar()
    for r, (lbl, var, show) in enumerate((("User", user_v, ""), ("Password", pw_v, "●"))):
        tk.Label(f, text=lbl, font=("Segoe UI", 9, "bold"), bg="white", fg="#475569").grid(
            row=r, column=0, sticky="w", padx=(0, 8), pady=4)
        e = tk.Entry(f, textvariable=var, show=show, width=24, font=("Segoe UI", 12),
                     relief="solid", bd=1)
        e.grid(row=r, column=1, pady=4, ipady=3)
        if show:
            pw_e = e
    tk.Label(card, textvariable=msg_v, font=("Segoe UI", 9), bg="white", fg="#DC2626").pack(
        pady=(6, 0))

    def tick():
        try:
            from datetime import datetime
            clock.config(text=datetime.now().strftime("%A %d %b %Y  ·  %H:%M"))
            w.after(20000, tick)
        except Exception:
            pass
    tick()

    def unlock(e=None):
        u = _check(user_v.get().strip(), pw_v.get())
        if not u:
            msg_v.set("Wrong user or password · كلمة المرور غير صحيحة")
            pw_v.set("")
            pw_e.focus_set()
            return
        if uname and u["username"] != uname:
            msg_v.set("")
            try:                                   # another user opens it: he becomes the user
                perm.set_session_user(dict(u))
            except Exception:
                pass
        try:
            from modules.doc_actions import audit
            audit("unlock", "system", u["user_id"], u["username"])
        except Exception:
            pass
        _LOCK["win"] = None
        w.destroy()
        for t in hidden:
            try:
                t.deiconify()
            except Exception:
                pass
        try:
            import ui.main_window as _mw
            _mw.APP._refresh_counter_chip()
        except Exception:
            pass

    tk.Button(card, text="🔓  Unlock", font=("Segoe UI", 11, "bold"), bg=C["primary"], fg="white",
              relief="flat", padx=24, pady=6, cursor="hand2", command=unlock).pack(pady=(10, 0))
    w.bind("<Return>", unlock)
    w.bind("<Escape>", lambda e: "break")
    try:
        from modules.doc_actions import audit
        audit("lock", "system", me.get("user_id") or 0, uname)
    except Exception:
        pass
    w.after(80, lambda: (w.focus_force(), pw_e.focus_set()))
    try:
        w.grab_set()
    except Exception:
        pass
    return w


def change_counter(root):
    from ui import branches as UB
    from modules import branches as BR
    if not BR.tables_ready() or not BR.list_counters(active_only=True):
        messagebox.showinfo("Counter", "No counters yet. Add them in Administration ▸ "
                                       "Branches & Counters.", parent=root)
        return None
    return UB.choose_counter(root, force=True)


class DeleteInactiveDialog:
    """Old drafts and cancelled documents → find, look, then delete."""

    def __init__(self, root):
        if not perm.allowed("company_settings", "settings", parent=root):
            return
        from modules import inactive_cleanup as IC
        self.IC = IC
        C = self.C = cfg.theme()
        w = self.win = tk.Toplevel(root)
        w.title("Delete Inactive Transactions")
        w.geometry("860x580")
        w.configure(bg=C["content_bg"])
        try:
            w.transient(root)
        except Exception:
            pass
        band = tk.Frame(w, bg=C.get("danger", "#DC2626"))
        band.pack(fill="x")
        tk.Label(band, text="🧹  Delete Inactive Transactions", font=("Segoe UI", 12, "bold"),
                 bg=band["bg"], fg="white").pack(side="left", padx=12, pady=7)
        tk.Label(w, text="Only DRAFT and CANCELLED documents are deleted — confirmed bills are "
                         "never touched. Make a backup first.",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"]).pack(
            anchor="w", padx=14, pady=(8, 2))
        f = tk.Frame(w, bg=C["content_bg"])
        f.pack(fill="x", padx=14, pady=4)
        tk.Label(f, text="Older than", font=("Segoe UI", 9, "bold"), bg=C["content_bg"]).pack(
            side="left")
        self.before_v = tk.StringVar(value=(date.today() - timedelta(days=90)).isoformat())
        e = tk.Entry(f, textvariable=self.before_v, width=11, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        e.pack(side="left", padx=(4, 12))
        try:
            from ui.datefield import DateBox
            DateBox(e, self.before_v)
        except Exception:
            pass
        self.draft_v, self.canc_v = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        for txt, var in (("Drafts", self.draft_v), ("Cancelled", self.canc_v)):
            tk.Checkbutton(f, text=txt, variable=var, bg=C["content_bg"],
                           font=("Segoe UI", 9)).pack(side="left", padx=4)
        tk.Button(f, text="🔍 Find", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=12, cursor="hand2", command=self.find).pack(side="left",
                                                                                padx=10)
        kf = tk.Frame(w, bg=C["content_bg"])
        kf.pack(fill="x", padx=14)
        self.kind_v = {}
        for k, lbl in IC.kinds():
            self.kind_v[k] = tk.BooleanVar(value=True)
            tk.Checkbutton(kf, text=lbl, variable=self.kind_v[k], bg=C["content_bg"],
                           font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))
        wrap = tk.Frame(w, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=14, pady=8)
        cols = (("doc", "Document", 190, "w"), ("no", "Number", 170, "w"),
                ("d", "Date", 100, "center"), ("st", "Status", 100, "center"))
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for c, t, wd, a in cols:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=wd, anchor=a)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        foot = tk.Frame(w, bg=C["card_bg"])
        foot.pack(fill="x", side="bottom")
        self.sum_v = tk.StringVar(value="Pick a date and press Find.")
        tk.Label(foot, textvariable=self.sum_v, font=("Segoe UI", 10, "bold"), bg=C["card_bg"]).pack(
            side="left", padx=12, pady=8)
        tk.Button(foot, text="Close", font=("Segoe UI", 9), relief="flat", padx=12,
                  command=w.destroy).pack(side="right", padx=8)
        self.del_btn = tk.Button(foot, text="🗑  Delete these", font=("Segoe UI", 9, "bold"),
                                 bg=C.get("danger", "#DC2626"), fg="white", relief="flat", padx=14,
                                 state="disabled", cursor="hand2", command=self.delete)
        self.del_btn.pack(side="right", padx=4, pady=6)
        w.bind("<Escape>", lambda e: w.destroy())
        self.items = []

    def find(self):
        sts = [s for s, v in (("draft", self.draft_v), ("cancelled", self.canc_v)) if v.get()]
        kk = [k for k, v in self.kind_v.items() if v.get()]
        self.items = self.IC.find(self.before_v.get(), kk, sts) if sts and kk else []
        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i), values=(it["label"], it["number"], it["date"],
                                                            it["status"].title()))
        self.sum_v.set("%d document(s) found" % len(self.items))
        self.del_btn.config(state="normal" if self.items else "disabled")

    def delete(self):
        if not self.items:
            return
        from tkinter import simpledialog
        typed = simpledialog.askstring(
            "Delete", "%d draft / cancelled document(s) will be deleted for good.\n\n"
                      "Type DELETE to go on:" % len(self.items), parent=self.win)
        if (typed or "").strip().upper() != "DELETE":
            return
        done, skipped = self.IC.delete(self.items)
        msg = "Deleted: %d" % len(done)
        if skipped:
            msg += "\nKept: %d\n\n" % len(skipped) + "\n".join(
                "• %s %s — %s" % (a, b, c[:90]) for a, b, c in skipped[:12])
        messagebox.showinfo("Delete Inactive Transactions", msg, parent=self.win)
        self.find()
