# ============================================================
# DayBill ERP - Reminders screen + the "due today" pop-up (v7.12.0)
#   RemindersView(parent)      list (Open / Done / All) and a small form
#   show_due(root)             at sign-in: what is due today or overdue
# Keys: Ctrl+N new · Ctrl+S save · Space = done · Delete
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from config import settings as cfg
from modules import reminders as R
from modules import masters as M
from modules import permissions as perm

EVERYONE = "Everyone"


def _me():
    return (perm.session_user() or {}).get("user_id")


class RemindersView:
    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.rid = None
        self.users = dict((n, i) for i, n in M.users())
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(top, text="Renew the CR, pay the rent, call a customer … shown when you sign in",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        tabs = tk.Frame(self.frame, bg=C["content_bg"])
        tabs.pack(fill="x", padx=20, pady=(2, 4))
        self.show_v = "open"
        self.tab_btns = {}
        for key, lbl in (("open", "Open"), ("done", "Done"), ("all", "All")):
            b = tk.Button(tabs, text=lbl, font=("Segoe UI", 9, "bold"), relief="flat", padx=12,
                          pady=4, cursor="hand2", command=lambda k=key: self.show(k))
            b.pack(side="left", padx=(0, 4))
            self.tab_btns[key] = b
        for txt, cmd in (("🗑 Delete", self._delete), ("↻ Snooze 1 day", self._snooze),
                         ("✔ Done  [Space]", self._done)):
            tk.Button(tabs, text=txt, font=("Segoe UI", 9, "bold"), bg=C["card_bg"], relief="flat",
                      padx=10, cursor="hand2", command=cmd).pack(side="right", padx=(6, 0))

        # form (bottom) first so the list shrinks on a small screen
        form = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        form.pack(fill="x", side="bottom", padx=20, pady=(4, 14))
        self.v = {k: tk.StringVar() for k in ("title", "details", "due", "repeat", "who")}
        self._clear_vals()
        g = tk.Frame(form, bg=C["card_bg"])
        g.pack(fill="x", padx=10, pady=8)

        def lab(r, c, t):
            tk.Label(g, text=t, font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=c, sticky="w", padx=(6, 4), pady=3)
        lab(0, 0, "Remember *")
        self.title_e = tk.Entry(g, textvariable=self.v["title"], width=40, font=("Segoe UI", 10),
                                relief="solid", bd=1)
        self.title_e.grid(row=0, column=1, sticky="w")
        lab(0, 2, "Date *")
        de = tk.Entry(g, textvariable=self.v["due"], width=12, font=("Segoe UI", 10), relief="solid",
                      bd=1)
        de.grid(row=0, column=3, sticky="w")
        try:
            from ui.datefield import DateBox
            DateBox(de, self.v["due"])
        except Exception:
            pass
        lab(0, 4, "Repeat")
        ttk.Combobox(g, textvariable=self.v["repeat"], state="readonly", width=13,
                     values=[l for _k, l in R.REPEATS]).grid(row=0, column=5, sticky="w")
        lab(1, 0, "Details")
        tk.Entry(g, textvariable=self.v["details"], width=40, font=("Segoe UI", 10), relief="solid",
                 bd=1).grid(row=1, column=1, sticky="w")
        lab(1, 2, "For")
        ttk.Combobox(g, textvariable=self.v["who"], state="readonly", width=20,
                     values=[EVERYONE] + list(self.users)).grid(row=1, column=3, columnspan=3,
                                                                sticky="w")
        bf = tk.Frame(form, bg=C["card_bg"])
        bf.pack(fill="x", padx=10, pady=(0, 8))
        self.mode_v = tk.StringVar(value="New reminder")
        tk.Label(bf, textvariable=self.mode_v, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left", padx=6)
        tk.Button(bf, text="✔ Save  [Ctrl+S]", font=("Segoe UI", 9, "bold"),
                  bg=C.get("success", "#16A34A"), fg="white", relief="flat", padx=12,
                  cursor="hand2", command=self._save).pack(side="right", padx=4)
        tk.Button(bf, text="＋ New  [Ctrl+N]", font=("Segoe UI", 9), relief="flat", padx=10,
                  cursor="hand2", command=self._new).pack(side="right", padx=4)

        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=20)
        cols = (("due", "Date", 100, "center"), ("title", "Remember", 300, "w"),
                ("det", "Details", 260, "w"), ("rep", "Repeat", 100, "center"),
                ("who", "For", 120, "w"), ("st", "", 110, "center"))
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for c, t, w, a in cols:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a)
        self.tree.tag_configure("late", foreground=C.get("danger", "#DC2626"))
        self.tree.tag_configure("today", foreground=C.get("warning", "#D97706"))
        self.tree.tag_configure("done", foreground=C["text_secondary"])
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._pick())
        self.tree.bind("<space>", lambda e: (self._done(), "break")[1])
        self.tree.bind("<Delete>", lambda e: self._delete())
        for wdg in (self.frame, self.title_e):
            wdg.bind("<Control-s>", lambda e: (self._save(), "break")[1])
            wdg.bind("<Control-n>", lambda e: (self._new(), "break")[1])
        self.frame.new_record = self._new
        if not R.ready():
            self.mode_v.set("⚠ needs the v7.12 database update (it runs when DayBill starts)")
        self.show("open")

    def _clear_vals(self):
        for k in ("title", "details"):
            self.v[k].set("")
        self.v["due"].set(date.today().isoformat())
        self.v["repeat"].set(R.REPEATS[0][1])
        self.v["who"].set(EVERYONE)

    def show(self, key):
        self.show_v = key
        for k, b in self.tab_btns.items():
            on = k == key
            b.configure(bg=self.C["primary"] if on else self.C["card_bg"],
                        fg="white" if on else self.C["text_primary"])
        self._load()

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        today = date.today()
        names = dict((i, n) for n, i in self.users.items())
        self._rows = {}
        for r in R.rows(self.show_v):
            d = R._d(r.get("due_date"))
            if r.get("is_done"):
                tag, st = "done", "✔ done"
            elif d and d < today:
                tag, st = "late", "overdue %d day(s)" % (today - d).days
            elif d == today:
                tag, st = "today", "today"
            else:
                tag, st = "", "in %d day(s)" % ((d - today).days if d else 0)
            self._rows[str(r["reminder_id"])] = r
            self.tree.insert("", "end", iid=str(r["reminder_id"]), tags=(tag,), values=(
                str(r.get("due_date") or "")[:10], r.get("title") or "", r.get("details") or "",
                dict(R.REPEATS).get(r.get("repeat_every"), "Once"),
                names.get(r.get("for_user_id"), EVERYONE), st))

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _pick(self):
        rid = self._sel()
        r = self._rows.get(str(rid)) if rid else None
        if not r:
            return
        self.rid = rid
        self.v["title"].set(r.get("title") or "")
        self.v["details"].set(r.get("details") or "")
        self.v["due"].set(str(r.get("due_date") or "")[:10])
        self.v["repeat"].set(dict(R.REPEATS).get(r.get("repeat_every"), "Once"))
        names = dict((i, n) for n, i in self.users.items())
        self.v["who"].set(names.get(r.get("for_user_id"), EVERYONE))
        self.mode_v.set("Editing: %s" % (r.get("title") or ""))

    def _new(self):
        self.rid = None
        self.tree.selection_remove(self.tree.selection())
        self._clear_vals()
        self.mode_v.set("New reminder")
        self.title_e.focus_set()

    def _save(self):
        rep = next((k for k, l in R.REPEATS if l == self.v["repeat"].get()), "none")
        vals = dict(title=self.v["title"].get(), details=self.v["details"].get(),
                    due_date=self.v["due"].get(), repeat_every=rep,
                    for_user_id=self.users.get(self.v["who"].get()))
        try:
            ok, msg, rid = R.save(vals, self.rid, _me())
        except Exception as e:
            ok, msg = False, str(e)[:200]
        if not ok:
            messagebox.showwarning("Reminders", msg, parent=self.frame)
            return
        self._load()
        self._new()

    def _done(self):
        rid = self._sel()
        if not rid:
            return
        nd = R.done(rid)
        if nd:
            self.mode_v.set("Done — next one on %s" % nd.isoformat())
        self._load()

    def _snooze(self):
        rid = self._sel()
        if rid:
            R.snooze(rid, 1)
            self._load()

    def _delete(self):
        rid = self._sel()
        if rid and messagebox.askyesno("Reminders", "Delete this reminder?", parent=self.frame):
            R.delete(rid)
            self._new()
            self._load()


def show_due(root, open_screen=None):
    """A small box with today's and overdue reminders (nothing when none)."""
    try:
        if not R.ready():
            return None
        items = R.due(_me())
    except Exception:
        return None
    if not items:
        return None
    C = cfg.theme()
    w = tk.Toplevel(root)
    w.title("Reminders")
    w.configure(bg=C["card_bg"])
    w.geometry("460x%d" % min(520, 160 + 34 * len(items)))
    try:
        w.transient(root)
    except Exception:
        pass
    band = tk.Frame(w, bg=C.get("warning", "#D97706"))
    band.pack(fill="x")
    tk.Label(band, text="⏰  %d reminder(s) due" % len(items), font=("Segoe UI", 12, "bold"),
             bg=band["bg"], fg="white").pack(side="left", padx=12, pady=7)
    body = tk.Frame(w, bg=C["card_bg"])
    body.pack(fill="both", expand=True, padx=12, pady=8)
    today = date.today()

    def row(r):
        f = tk.Frame(body, bg=C["card_bg"])
        f.pack(fill="x", pady=2)
        d = R._d(r.get("due_date"))
        late = d and d < today
        tk.Label(f, text=("⚠ " if late else "• ") + (r.get("title") or ""),
                 font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C.get("danger", "#DC2626") if late else C["text_primary"], anchor="w").pack(
            side="left")
        tk.Label(f, text="  " + str(r.get("due_date") or "")[:10], font=("Segoe UI", 8),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left")

        def done():
            R.done(r["reminder_id"])
            f.destroy()
        tk.Button(f, text="✔ Done", font=("Segoe UI", 8), relief="flat", cursor="hand2",
                  command=done).pack(side="right")
    for r in items[:12]:
        row(r)
    foot = tk.Frame(w, bg=C["card_bg"])
    foot.pack(fill="x", side="bottom", pady=8)
    tk.Button(foot, text="Close", font=("Segoe UI", 9), relief="flat", padx=12,
              command=w.destroy).pack(side="right", padx=10)
    if open_screen:
        tk.Button(foot, text="Open Reminders", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=12,
                  command=lambda: (w.destroy(), open_screen())).pack(side="right")
    w.bind("<Escape>", lambda e: w.destroy())
    return w
