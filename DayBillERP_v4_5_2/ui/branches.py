# ============================================================
# DayBill ERP - Branches & Counters page (Administration)
# ------------------------------------------------------------
# Left: branches (shops). Right: counters (tills) of the branches.
# "Use on this PC" makes the selected counter this computer's till.
# choose_counter() = the small box a new PC shows at start-up when
# the shop has more than one counter.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules import branches as BR


class BranchesView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.b_id = None
        self.c_id = None
        self._build(C)
        self.load()

    # ── layout ────────────────────────────────────────────────
    def _build(self, C):
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(top, text="🏬  Branches & Counters", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        self.pc_var = tk.StringVar()
        tk.Label(self.frame, textvariable=self.pc_var, font=("Segoe UI", 10, "bold"),
                 bg=C["primary_light"], fg=C["primary"], anchor="w", padx=12,
                 pady=7).pack(fill="x", padx=20, pady=(4, 6))
        self.lim_var = tk.StringVar()
        tk.Label(self.frame, textvariable=self.lim_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"], anchor="w").pack(fill="x", padx=22)

        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=20, pady=(6, 14))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._branch_panel(body, C).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._counter_panel(body, C).grid(row=0, column=1, sticky="nsew")

    def _card(self, parent, C, title):
        card = tk.Frame(parent, bg=C["card_bg"], highlightthickness=1,
                        highlightbackground=C["border"])
        tk.Label(card, text=title, font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=12, pady=(10, 4))
        return card

    def _entry(self, parent, C, label, var, width=18):
        f = tk.Frame(parent, bg=C["card_bg"])
        f.pack(side="left", padx=(0, 8), pady=2)
        tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        tk.Entry(f, textvariable=var, width=width, font=("Segoe UI", 10)).pack(anchor="w", ipady=2)

    def _btn(self, parent, text, cmd, primary=False, side="left"):
        C = self.C
        tk.Button(parent, text=text, font=("Segoe UI", 9, "bold" if primary else "normal"),
                  bg=C["primary"] if primary else C["card_bg"],
                  fg="white" if primary else C["text_primary"], relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2", highlightthickness=0 if primary else 1,
                  highlightbackground=C["border"], command=cmd).pack(side=side, padx=(0, 6))

    def _branch_panel(self, parent, C):
        card = self._card(parent, C, "Branches (shops)")
        self.btree = ttk.Treeview(card, columns=("code", "name", "phone", "st"),
                                  show="headings", height=8)
        for cid, txt, w in (("code", "Code", 60), ("name", "Name", 200),
                            ("phone", "Phone", 110), ("st", "Status", 70)):
            self.btree.heading(cid, text=txt); self.btree.column(cid, width=w, anchor="w")
        self.btree.pack(fill="both", expand=True, padx=10)
        self.btree.bind("<<TreeviewSelect>>", lambda e: self._pick_branch())
        self.bv = {k: tk.StringVar() for k in ("code", "name_en", "name_ar", "address", "phone")}
        self.b_active = tk.BooleanVar(value=True)
        r1 = tk.Frame(card, bg=C["card_bg"]); r1.pack(fill="x", padx=10, pady=(8, 0))
        self._entry(r1, C, "Code", self.bv["code"], 6)
        self._entry(r1, C, "Name (English) *", self.bv["name_en"], 22)
        self._entry(r1, C, "Name (Arabic)", self.bv["name_ar"], 18)
        r2 = tk.Frame(card, bg=C["card_bg"]); r2.pack(fill="x", padx=10)
        self._entry(r2, C, "Address", self.bv["address"], 30)
        self._entry(r2, C, "Phone", self.bv["phone"], 14)
        r3 = tk.Frame(card, bg=C["card_bg"]); r3.pack(fill="x", padx=10, pady=(6, 10))
        tk.Checkbutton(r3, text="Active", variable=self.b_active, bg=C["card_bg"],
                       activebackground=C["card_bg"]).pack(side="left", padx=(0, 10))
        self._btn(r3, "💾 Save branch", self._save_branch, primary=True)
        self._btn(r3, "＋ New", self._new_branch)
        return card

    def _counter_panel(self, parent, C):
        card = self._card(parent, C, "Counters (tills / billing PCs)")
        self.ctree = ttk.Treeview(card, columns=("code", "name", "branch", "pc", "st"),
                                  show="headings", height=8)
        for cid, txt, w in (("code", "Code", 60), ("name", "Counter", 130),
                            ("branch", "Branch", 130), ("pc", "Last PC", 120),
                            ("st", "Status", 70)):
            self.ctree.heading(cid, text=txt); self.ctree.column(cid, width=w, anchor="w")
        self.ctree.pack(fill="both", expand=True, padx=10)
        self.ctree.bind("<<TreeviewSelect>>", lambda e: self._pick_counter())
        self.cv = {k: tk.StringVar() for k in ("code", "name_en", "branch")}
        self.c_active = tk.BooleanVar(value=True)
        r1 = tk.Frame(card, bg=C["card_bg"]); r1.pack(fill="x", padx=10, pady=(8, 0))
        self._entry(r1, C, "Code *", self.cv["code"], 6)
        self._entry(r1, C, "Counter name *", self.cv["name_en"], 20)
        f = tk.Frame(r1, bg=C["card_bg"]); f.pack(side="left", pady=2)
        tk.Label(f, text="Branch *", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.branch_cb = ttk.Combobox(f, textvariable=self.cv["branch"], state="readonly", width=20)
        self.branch_cb.pack(anchor="w")
        r3 = tk.Frame(card, bg=C["card_bg"]); r3.pack(fill="x", padx=10, pady=(8, 10))
        tk.Checkbutton(r3, text="Active", variable=self.c_active, bg=C["card_bg"],
                       activebackground=C["card_bg"]).pack(side="left", padx=(0, 10))
        self._btn(r3, "💾 Save counter", self._save_counter, primary=True)
        self._btn(r3, "＋ New", self._new_counter)
        self._btn(r3, "🖥 Use on THIS PC", self._use_here)
        return card

    # ── data ──────────────────────────────────────────────────
    def load(self):
        if not BR.tables_ready():
            self.pc_var.set("⚠ Run Updates ▸ Apply All Updates (branch / counter tables missing).")
            return
        bn, cn = BR.labels()
        self.pc_var.set(f"🖥  This PC ({BR.pc_name()}) is  {cn or '— no counter —'}"
                        + (f"  ·  {bn}" if bn else ""))
        try:
            from modules import license as lic
            lim = lic.limits()
            self.lim_var.set(f"Product key allows: {lim.get('branches') or 'unlimited'} branch(es), "
                             f"{lim.get('counters') or 'unlimited'} counter(s).")
        except Exception:
            self.lim_var.set("")
        self._branches = BR.list_branches()
        self.btree.delete(*self.btree.get_children())
        for b in self._branches:
            self.btree.insert("", "end", iid=str(b["branch_id"]), values=(
                b["code"], b["name_en"], b["phone"], "Active" if b["is_active"] else "Off"))
        self.branch_cb.config(values=[b["name_en"] for b in self._branches if b["is_active"]])
        self._counters = BR.list_counters()
        _b, here = BR.current()
        self.ctree.delete(*self.ctree.get_children())
        self.ctree.tag_configure("here", foreground=self.C["primary"],
                                 font=("Segoe UI", 10, "bold"))
        for c in self._counters:
            self.ctree.insert("", "end", iid=str(c["counter_id"]), values=(
                c["code"], c["name_en"], c["branch_name"] or "", c["workstation"],
                "Active" if c["is_active"] else "Off"),
                tags=("here",) if c["counter_id"] == here else ())

    def _pick_branch(self):
        s = self.btree.selection()
        if not s:
            return
        b = next(x for x in self._branches if x["branch_id"] == int(s[0]))
        self.b_id = b["branch_id"]
        for k in self.bv:
            self.bv[k].set(b.get(k) or "")
        self.b_active.set(bool(b["is_active"]))

    def _new_branch(self):
        self.b_id = None
        for v in self.bv.values():
            v.set("")
        self.bv["code"].set(f"B{len(self._branches) + 1}")
        self.b_active.set(True)

    def _save_branch(self):
        from modules import permissions as _pm
        if not _pm.allowed("company_settings", "settings"):
            return
        ok, msg = BR.save_branch(self.b_id, self.bv["name_en"].get(), self.bv["name_ar"].get(),
                                 self.bv["code"].get(), self.bv["address"].get(),
                                 self.bv["phone"].get(), self.b_active.get())
        (messagebox.showinfo if ok else messagebox.showwarning)("Branch", msg)
        if ok:
            self.load()

    def _pick_counter(self):
        s = self.ctree.selection()
        if not s:
            return
        c = next(x for x in self._counters if x["counter_id"] == int(s[0]))
        self.c_id = c["counter_id"]
        self.cv["code"].set(c["code"]); self.cv["name_en"].set(c["name_en"])
        self.cv["branch"].set(c["branch_name"] or "")
        self.c_active.set(bool(c["is_active"]))

    def _new_counter(self):
        self.c_id = None
        n = len(self._counters) + 1
        self.cv["code"].set(f"C{n}"); self.cv["name_en"].set(f"Counter {n}")
        act = [b for b in self._branches if b["is_active"]]
        self.cv["branch"].set(act[0]["name_en"] if act else "")
        self.c_active.set(True)

    def _save_counter(self):
        from modules import permissions as _pm
        if not _pm.allowed("company_settings", "settings"):
            return
        bid = next((b["branch_id"] for b in self._branches
                    if b["name_en"] == self.cv["branch"].get()), None)
        ok, msg = BR.save_counter(self.c_id, bid, self.cv["code"].get(),
                                  self.cv["name_en"].get(), self.c_active.get())
        (messagebox.showinfo if ok else messagebox.showwarning)("Counter", msg)
        if ok:
            self.load()

    def _use_here(self):
        s = self.ctree.selection()
        if not s:
            messagebox.showwarning("Counter", "Select a counter first.")
            return
        c = next(x for x in self._counters if x["counter_id"] == int(s[0]))
        if not c["is_active"]:
            messagebox.showwarning("Counter", "That counter is switched off.")
            return
        BR.bind_this_pc(c["counter_id"])
        self.load()
        _refresh_shell()
        messagebox.showinfo("Counter", f"This PC is now {c['name_en']} ({c['branch_name']}).")


def _refresh_shell():
    try:
        import ui.main_window as _mw
        _mw.APP._refresh_counter_chip()
    except Exception:
        pass


def choose_counter(root, force=False):
    """Start-up box on a PC that has no counter yet (several exist)."""
    if not force and not BR.needs_choice():
        return
    C = cfg.theme()
    counters = BR.list_counters(active_only=True)
    if not counters:
        return
    win = tk.Toplevel(root)
    win.title("Which counter is this PC?")
    win.configure(bg=C["card_bg"])
    win.geometry("420x360")
    try:
        win.transient(root)
    except Exception:
        pass
    head = tk.Frame(win, bg=C["primary"]); head.pack(fill="x")
    tk.Label(head, text="🖥  Which counter is this PC?", font=("Segoe UI", 12, "bold"),
             bg=C["primary"], fg="white").pack(side="left", padx=14, pady=8)
    tk.Label(win, text=f"PC name: {BR.pc_name()}\nBills made here will carry this counter.",
             font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
             justify="left").pack(anchor="w", padx=16, pady=(10, 4))
    lb = tk.Listbox(win, font=("Segoe UI", 11), height=8)
    lb.pack(fill="both", expand=True, padx=16)
    for c in counters:
        pc = f"   (last used on {c['workstation']})" if c["workstation"] else ""
        lb.insert("end", f"{c['name_en']} · {c['branch_name']}{pc}")
    lb.selection_set(0)

    def ok(e=None):
        sel = lb.curselection()
        if not sel:
            return
        BR.bind_this_pc(counters[sel[0]]["counter_id"])
        win.destroy()
        _refresh_shell()
    lb.bind("<Double-1>", ok)
    lb.bind("<Return>", ok)
    tk.Button(win, text="✓  Use this counter", font=("Segoe UI", 10, "bold"),
              bg=C["primary"], fg="white", relief="flat", padx=14, pady=6,
              command=ok).pack(pady=10)
    return win
