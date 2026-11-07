# ============================================================
# DayBill ERP - Masters page (v7.10.0)
# ------------------------------------------------------------
# One page for the short lists DayBill picks from:
#   left   the lists (Brands, Sections, Group Categories, Units of
#          Measure, Tax Categories, Routes, Salesmen, Vehicles, Party
#          Categories, Cost Centres, Currencies, General Master)
#   right  the rows of the list (search, Active / Off) and the form
#          of the selected row; Salesmen tick their routes, a Group
#          Category ticks its product categories, a currency shows its
#          rate history.
# Keys (only while this page has the focus):
#   Insert / Ctrl+N  new     Ctrl+S  save     Delete  delete (in the list)
#   F5  refresh             Ctrl+F  search    Esc     clear the search
# A row that is in use is never deleted: untick Active instead.
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox

from modules import masters as M
from modules import permissions as perm
from ui import v6_kit as K

NONE = "— None —"


class MastersView:
    start_kind = None          # the menu sets this to open on one list
    _live = None               # the open page (menus switch its list)

    def __init__(self, parent, kind=None):
        self.page = K.Page(parent, "🗂  Masters",
                           "Brands, sections, units, tax categories, routes, salesmen, vehicles, "
                           "party categories, cost centres, currencies and your own lists — "
                           "the names DayBill offers in products, customers and bills.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.kind = None
        self.rid = None
        self.vars = {}
        self.widgets = {}
        self.maps = {}             # field col → {label: value}
        self.link_ticks = {}
        self._search_job = None
        MastersView._live = self
        try:
            M.ensure_base_currency()
        except Exception:
            pass

        body = self.page.body
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_kinds(body, C).grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        self.right = K.card(body, C)
        self.right.grid(row=0, column=1, sticky="nsew")
        self._build_right(self.right, C)
        self._bind_keys()

        first = kind or MastersView.start_kind or "brands"
        MastersView.start_kind = None
        self.select_kind(first if first in M.KINDS else "brands")

    # ── left: the lists ────────────────────────────────────────
    def _build_kinds(self, parent, C):
        c = K.card(parent, C, "Lists")
        wrap = tk.Frame(c, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.ktree = ttk.Treeview(wrap, columns=("n",), show="tree headings", height=22,
                                  selectmode="browse")
        self.ktree.heading("#0", text="List", anchor="w")
        self.ktree.heading("n", text="Rows", anchor="e")
        self.ktree.column("#0", width=200, stretch=True)
        self.ktree.column("n", width=50, anchor="e", stretch=False)
        self.ktree.pack(side="left", fill="both", expand=True)
        for g in M.GROUPS:
            gid = "g:" + g
            self.ktree.insert("", "end", iid=gid, text=g.upper(), open=True)
            for key in M.ORDER:
                k = M.KINDS[key]
                if k["group"] == g:
                    self.ktree.insert(gid, "end", iid=key,
                                      text="  %s  %s" % (k["icon"], k.get("short", k["title"])),
                                      values=("",))
        self.ktree.bind("<<TreeviewSelect>>", self._on_kind_pick)
        self._fill_counts()
        return c

    def _fill_counts(self):
        for key in M.ORDER:
            n = ""
            if M.ready(key):
                try:
                    n = str(len(M.rows(key)))
                except Exception:
                    n = ""
            else:
                n = "—"
            try:
                self.ktree.set(key, "n", n)
            except Exception:
                pass

    def _on_kind_pick(self, _e=None):
        sel = self.ktree.selection()
        if not sel or sel[0].startswith("g:"):
            return
        if sel[0] != self.kind:
            self.select_kind(sel[0], from_tree=True)

    def select_kind(self, key, from_tree=False):
        if key not in M.KINDS:
            return
        self.kind = key
        if not from_tree:
            try:
                self.ktree.selection_set(key)
                self.ktree.see(key)
            except Exception:
                pass
        k = M.KINDS[key]
        self.title_v.set("%s  %s" % (k["icon"], k["title"]))
        self.help_v.set(k["help"])
        self.search_v.set("")
        self._build_table(k)
        self._build_form(k)
        self._build_links(k)
        self._build_extra(k)
        ok = M.ready(key)
        for b in (self.b_new, self.b_save, self.b_del):
            b.configure(state="normal" if ok else "disabled")
        if not ok:
            self.page.say("⚠ This list needs the v7.10 database update. It runs by itself when "
                          "DayBill starts — or Administration ▸ Updates ▸ Apply All Updates.",
                          ok=False)
        else:
            self.page.say("")
        self.load()
        self.new(focus=False)

    # ── right: toolbar, table, form ────────────────────────────
    def _build_right(self, c, C):
        top = tk.Frame(c, bg=C["card_bg"])
        top.pack(fill="x", padx=12, pady=(10, 0))
        self.title_v = tk.StringVar()
        tk.Label(top, textvariable=self.title_v, font=("Segoe UI", 13, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
        self.help_v = tk.StringVar()
        hl = tk.Label(c, textvariable=self.help_v, font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_secondary"], anchor="w", justify="left", wraplength=760)
        hl.pack(fill="x", padx=12, pady=(2, 6))
        c.bind("<Configure>", lambda e, l=hl: l.configure(wraplength=max(300, e.width - 40)),
               add="+")

        bar = tk.Frame(c, bg=C["card_bg"])
        bar.pack(fill="x", padx=12)
        tk.Label(bar, text="🔍", bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left")
        self.search_v = tk.StringVar()
        self.search_e = tk.Entry(bar, textvariable=self.search_v, width=26, font=("Segoe UI", 10),
                                 relief="solid", bd=1)
        self.search_e.pack(side="left", padx=(4, 10), ipady=2)
        self.search_e._fixed_width = True
        self.search_e.bind("<KeyRelease>", self._search_soon)
        self.search_e.bind("<Escape>", lambda e: (self.search_v.set(""), self.load()) and "break")
        self.search_e.bind("<Down>", lambda e: self._focus_table())
        self.only_active_v = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Active only", variable=self.only_active_v, bg=C["card_bg"],
                       activebackground=C["card_bg"], command=self.load).pack(side="left")
        self.b_del = K.button(bar, C, "🗑 Delete  Del", self.delete, side="right")
        self.b_save = K.button(bar, C, "💾 Save  Ctrl+S", self.save, primary=True, side="right")
        self.b_new = K.button(bar, C, "＋ New  Ins", self.new, side="right")
        K.button(bar, C, "↻", self.refresh, side="right")

        # the form (and the rate history) are anchored to the bottom and
        # packed BEFORE the table: on a small screen the table gets
        # shorter, the form is never cut off
        self.extra_holder = tk.Frame(c, bg=C["card_bg"])
        self.extra_holder.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        low = tk.Frame(c, bg=C["card_bg"])
        low.pack(side="bottom", fill="x", padx=12, pady=(0, 6))
        self.links_holder = tk.Frame(low, bg=C["card_bg"])
        self.links_holder.pack(side="right", fill="y", padx=(10, 0))
        self.form_holder = tk.Frame(low, bg=C["card_bg"])
        self.form_holder.pack(side="left", fill="both", expand=True, anchor="n")

        mid = tk.Frame(c, bg=C["card_bg"])
        mid.pack(fill="both", expand=True, padx=0, pady=(6, 0))
        self.table_holder = tk.Frame(mid, bg=C["card_bg"])
        self.table_holder.pack(fill="both", expand=True)

    def _build_table(self, k):
        for w in self.table_holder.winfo_children():
            w.destroy()
        cols = [(f.col, f.head, f.list_width, "e" if f.kind in ("num", "rate", "int") else
                 ("center" if f.kind == "bool" else "w"))
                for f in k["fields"] if f.list_width]
        cols.append(("_st", "Status", 70, "center"))
        self.table_cols = cols
        self.tree = K.tree(self.table_holder, cols, height=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_row_pick)
        self.tree.bind("<Delete>", lambda e: (self.delete(), "break")[1])
        self.tree.bind("<Return>", lambda e: (self._focus_form(), "break")[1])
        self._bind_keys(self.table_holder)

    def _build_form(self, k):
        C = self.C
        for w in self.form_holder.winfo_children():
            w.destroy()
        self.vars, self.widgets, self.maps = {}, {}, {}
        tk.Label(self.form_holder, text="Details", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", pady=(4, 2))
        row = None
        used = 0
        room = 58 if (k.get("links") or self.kind == "currencies") else 80   # box width per row
        for f in k["fields"]:
            need = 16 if f.kind == "bool" else max(int(f.width), len(f.label) * 0.8) + 2
            if row is None or (used and used + need > room):
                row = tk.Frame(self.form_holder, bg=C["card_bg"])
                row.pack(fill="x", anchor="w")
                used = 0
            used += need
            self._field(row, f)
        last = tk.Frame(self.form_holder, bg=C["card_bg"])
        last.pack(fill="x", anchor="w", pady=(4, 0))
        self.active_v = tk.BooleanVar(value=True)
        tk.Checkbutton(last, text="Active (offered in the lists)", variable=self.active_v,
                       bg=C["card_bg"], activebackground=C["card_bg"]).pack(side="left")
        self.use_v = tk.StringVar()
        tk.Label(last, textvariable=self.use_v, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(12, 0))
        self._bind_keys(self.form_holder)

    def _field(self, row, f):
        C = self.C
        box = tk.Frame(row, bg=C["card_bg"])
        box.pack(side="left", padx=(0, 12), pady=2, anchor="n")
        need = " *" if f.required else ""
        if f.kind != "bool":
            tk.Label(box, text=f.label + need, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
        if f.kind == "bool":
            v = tk.BooleanVar(value=False)
            w = tk.Checkbutton(box, text=f.label, variable=v, bg=C["card_bg"],
                               activebackground=C["card_bg"])
            w.pack(anchor="w", pady=(14, 0))
        elif f.kind in ("choice", "user", "vehicle", "parent", "type", "account"):
            v = tk.StringVar()
            values, m = self._options(f)
            self.maps[f.col] = m
            w = ttk.Combobox(box, textvariable=v, values=values, width=f.width,
                             state="normal" if f.kind == "type" else "readonly")
            w.pack(anchor="w", ipady=1)
        elif f.kind == "date":
            v = tk.StringVar()
            w = tk.Entry(box, textvariable=v, width=12, font=("Segoe UI", 10), relief="solid", bd=1)
            w.pack(anchor="w", ipady=2)
            w._fixed_width = True
            try:
                from ui.datefield import DateBox
                DateBox(w, v)
            except Exception:
                pass
        else:
            v = tk.StringVar()
            just = "right" if f.kind in ("ar", "num", "rate", "int") else "left"
            w = tk.Entry(box, textvariable=v, width=f.width, font=("Segoe UI", 10), relief="solid",
                         bd=1, justify=just)
            w.pack(anchor="w", ipady=2)
            w._fixed_width = True
        if f.tip:
            tk.Label(box, text=f.tip, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
        try:
            w.bind("<Return>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[1])
        except Exception:
            pass
        self.vars[f.col] = v
        self.widgets[f.col] = w

    def _options(self, f):
        """(labels, {label: value}) for a picker field."""
        if f.kind == "choice":
            return [l for _v, l in f.options], {l: v for v, l in f.options}
        if f.kind == "user":
            pairs = M.users()
        elif f.kind == "vehicle":
            pairs = M.choices("vehicles") if M.ready("vehicles") else []
        elif f.kind == "parent":
            pairs = [(i, l) for i, l in M.choices(self.kind) if i != self.rid]
        elif f.kind == "account":
            pairs = M.accounts()
        else:                                     # type: the general master's list names
            t = M.types()
            return t, {x: x for x in t}
        labels = [NONE] + [l for _i, l in pairs]
        m = {NONE: None}
        m.update({l: i for i, l in pairs})
        return labels, m

    def _refresh_pickers(self):
        k = M.KINDS[self.kind]
        for f in k["fields"]:
            if f.kind in ("user", "vehicle", "parent", "type"):
                labels, m = self._options(f)
                cur = self.vars[f.col].get()
                if f.kind in ("vehicle", "parent") and self.rid:
                    # a switched-off vehicle still shows on the salesman who has it
                    r = M.get(self.kind, self.rid) or {}
                    held = r.get(f.col)
                    src = "vehicles" if f.kind == "vehicle" else self.kind
                    if held and held not in m.values():
                        lbl = M.label_of(src, held)
                        if lbl:
                            labels.append(lbl)
                            m[lbl] = held
                self.maps[f.col] = m
                try:
                    self.widgets[f.col]["values"] = labels
                except Exception:
                    pass
                self.vars[f.col].set(cur)

    # ── links (salesman routes / group categories) ────────────
    def _build_links(self, k):
        C = self.C
        for w in self.links_holder.winfo_children():
            w.destroy()
        self.link_tree = None
        self.link_ticks = {}
        L = k.get("links")
        if not L:
            return
        tk.Label(self.links_holder, text=L["title"], font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", pady=(4, 2))
        wrap = tk.Frame(self.links_holder, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True)
        t = ttk.Treeview(wrap, columns=("tick", "name", "note"), show="headings", height=5,
                         selectmode="browse")
        t.heading("tick", text="✓")
        t.heading("name", text="Name", anchor="w")
        t.heading("note", text="", anchor="w")
        t.column("tick", width=34, anchor="center", stretch=False)
        t.column("name", width=170, anchor="w")
        t.column("note", width=90, anchor="w")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.bind("<Button-1>", self._link_click)
        t.bind("<space>", lambda e: (self._link_toggle(t.focus()), "break")[1])
        self.link_tree = t
        tk.Label(self.links_holder, text="Click or Space ticks · saved with 💾 Save",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")

    def _load_links(self):
        t = self.link_tree
        if t is None:
            return
        t.delete(*t.get_children())
        mine = M.links(self.kind, self.rid) if self.rid else set()
        names = {}
        if self.kind == "group_categories":
            names = {r["group_category_id"]: r["name_en"] for r in M.rows("group_categories")}
        self.link_ticks = {}
        for i, lbl, owner in M.link_options(self.kind):
            on = i in mine
            note = ""
            if owner and owner != self.rid and owner in names:
                note = "now in: %s" % names[owner]
            self.link_ticks[i] = on
            t.insert("", "end", iid=str(i), values=("☑" if on else "☐", lbl, note))

    def _link_click(self, e):
        t = self.link_tree
        iid = t.identify_row(e.y)
        if iid:
            t.focus(iid)
            t.selection_set(iid)
            self._link_toggle(iid)
        return "break"

    def _link_toggle(self, iid):
        if not iid:
            return
        i = int(iid)
        self.link_ticks[i] = not self.link_ticks.get(i)
        self.link_tree.set(iid, "tick", "☑" if self.link_ticks[i] else "☐")

    # ── extra: currency rate history ───────────────────────────
    def _build_extra(self, k):
        for w in self.extra_holder.winfo_children():
            w.destroy()
        self.hist_tree = None
        if self.kind != "currencies":
            return
        C = self.C
        box = self.links_holder                 # beside the form (the lists have no ticks)
        tk.Label(box, text="Rate history", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", pady=(4, 2))
        self.hist_tree = K.tree(box, [("when", "Changed", 110, "w"), ("old", "Old", 60, "e"),
                                      ("new", "New", 60, "e"), ("who", "By", 70, "w")],
                                height=5)
        self.base_v = tk.StringVar()
        tk.Label(box, textvariable=self.base_v, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")

    def _load_extra(self):
        if self.hist_tree is None:
            return
        base = M.base_currency()
        self.base_v.set(("Shop currency: %s — its rate is always 1." % base) if base else "")
        self.hist_tree.delete(*self.hist_tree.get_children())
        if not self.rid:
            return
        for n, h in enumerate(M.rate_history(self.rid)):
            o = h.get("old_rate")
            self.hist_tree.insert("", "end", iid=str(n), values=(
                str(h.get("changed_at") or "")[:16], "%g" % float(o) if o is not None else "—",
                "%g" % float(h.get("new_rate") or 0), h.get("changed_by") or ""))

    # ── data ───────────────────────────────────────────────────
    def load(self, select=None):
        k = M.KINDS[self.kind]
        self.tree.delete(*self.tree.get_children())
        data = M.rows(self.kind, self.search_v.get(), self.only_active_v.get())
        users = dict(M.users()) if any(f.kind == "user" for f in k["fields"]) else {}
        for r in data:
            vals = []
            for col, _h, _w, _a in self.table_cols:
                if col == "_st":
                    st = "Active" if r.get("is_active", 1) else "Off"
                    if self.kind == "currencies" and r.get("is_base"):
                        st = "★ Shop"
                    vals.append(st)
                    continue
                f = next(x for x in k["fields"] if x.col == col)
                vals.append(self._show(f, r.get(col), users))
            self.tree.insert("", "end", iid=str(r[k["id"]]), values=vals)
        try:
            self.ktree.set(self.kind, "n", str(len(M.rows(self.kind))))
        except Exception:
            pass
        if select:
            try:
                self.tree.selection_set(str(select))
                self.tree.see(str(select))
            except Exception:
                pass

    def _show(self, f, v, users):
        if v is None:
            return ""
        if f.kind == "bool":
            return "✓" if v else ""
        if f.kind == "rate":
            return "%g" % float(v)
        if f.kind == "num":
            return "{:,.2f}".format(float(v)) if f.col == "monthly_target" else "%g" % float(v)
        if f.kind == "choice":
            return dict(f.options).get(v, v)
        if f.kind == "user":
            return users.get(v, "")
        if f.kind == "vehicle":
            return M.label_of("vehicles", v)
        if f.kind == "parent":
            return M.label_of(self.kind, v)
        if f.kind == "account":
            return M.account_label(v)
        if f.kind == "date":
            return str(v)[:10]
        return str(v)

    def _search_soon(self, e=None):
        if e is not None and e.keysym in ("Down", "Up", "Return", "Escape", "Tab"):
            return
        if self._search_job:
            try:
                self.frame.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.frame.after(250, self.load)

    def _on_row_pick(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = M.get(self.kind, int(sel[0]))
        if not r:
            return
        self.rid = r[M.KINDS[self.kind]["id"]]
        self._refresh_pickers()
        self._fill(r)

    def _fill(self, r):
        k = M.KINDS[self.kind]
        for f in k["fields"]:
            v = r.get(f.col) if r else None
            var = self.vars[f.col]
            if f.kind == "bool":
                var.set(bool(v))
            elif f.kind in ("choice", "user", "vehicle", "parent", "account"):
                m = self.maps.get(f.col, {})
                lbl = next((l for l, x in m.items() if x == v), None)
                if lbl is None:
                    lbl = NONE if f.kind != "choice" else (f.options[0][1] if f.options else "")
                var.set(lbl)
            elif f.kind in ("num", "rate"):
                var.set("" if v is None else ("%g" % float(v)))
            elif f.kind == "date":
                var.set("" if v is None else str(v)[:10])
            else:
                var.set("" if v is None else str(v))
        self.active_v.set(bool(r.get("is_active", 1)) if r else True)
        if r and self.rid:
            use = M.usage(self.kind, self.rid)
            self.use_v.set(("Used by: " + M.usage_text(use)) if use else "Not used yet")
        else:
            self.use_v.set("")
        locked = set()
        if r and self.rid and k.get("locked_when_used") and M.usage(self.kind, self.rid):
            locked = set(k["locked_when_used"])
        if self.kind == "currencies" and r and r.get("is_base"):
            locked |= {"currency_code", "rate_to_base"}
        for f in k["fields"]:
            w = self.widgets.get(f.col)
            if isinstance(w, tk.Entry):
                w.configure(state="disabled" if f.col in locked else "normal")
        self._load_links()
        self._load_extra()

    def _values(self):
        k = M.KINDS[self.kind]
        out = {}
        for f in k["fields"]:
            v = self.vars[f.col].get()
            if f.kind in ("choice", "user", "vehicle", "parent", "account"):
                v = self.maps.get(f.col, {}).get(v)
            out[f.col] = v
        return out

    # ── actions ────────────────────────────────────────────────
    def _right(self, action):
        k = M.KINDS[self.kind]
        act = k.get("right_action") or action
        return perm.allowed(k["rights"], act, parent=self.frame)

    def new(self, focus=True):
        self.rid = None
        try:
            self.tree.selection_remove(*self.tree.selection())
        except Exception:
            pass
        self._refresh_pickers()
        self._fill({})
        k = M.KINDS[self.kind]
        for f in k["fields"]:                      # sensible starting values
            if f.kind == "choice" and f.options:
                self.vars[f.col].set(f.options[0][1])
            if self.kind == "currencies" and f.col == "decimals":
                self.vars[f.col].set("2")
            if self.kind == "general" and f.col == "gm_type" and getattr(self, "_last_type", ""):
                self.vars[f.col].set(self._last_type)
        if focus:
            self._focus_form()
            self.page.say("＋ New row in %s — fill it in and press 💾 Save (Ctrl+S)." % k["title"])

    def save(self):
        if not M.ready(self.kind):
            return
        if not self._right("edit" if self.rid else "add"):
            return
        k = M.KINDS[self.kind]
        ok, msg, rid = M.save(self.kind, self._values(), self.rid, self.active_v.get())
        if not ok:
            self.page.say("⚠ " + msg, ok=False)
            messagebox.showwarning(k["title"], msg, parent=self.frame)
            return
        if k.get("links") and rid:
            M.set_links(self.kind, rid, [i for i, on in self.link_ticks.items() if on])
        if self.kind == "general":
            self._last_type = str(self.vars["gm_type"].get() or "").strip()
        self.rid = rid
        self.load(select=rid)
        self._refresh_pickers()
        r = M.get(self.kind, rid)
        if r:
            self._fill(r)
        self.page.say("✓ " + msg)

    def delete(self):
        if not self.rid or not M.ready(self.kind):
            return
        if not self._right("delete"):
            return
        k = M.KINDS[self.kind]
        name = M.label_of(self.kind, self.rid)
        use = M.usage(self.kind, self.rid)
        if use:
            msg = ("'%s' is used by %s, so it can't be deleted.\n\n"
                   "Switch it off instead? It stays on old bills and reports but is no "
                   "longer offered." % (name, M.usage_text(use)))
            if messagebox.askyesno(k["title"], msg, parent=self.frame):
                ok, m = M.set_active(self.kind, self.rid, False)
                self.page.say(("✓ " if ok else "⚠ ") + m, ok=ok)
                self.load(select=self.rid)
                r = M.get(self.kind, self.rid)
                if r:
                    self._fill(r)
            return
        if not messagebox.askyesno(k["title"], "Delete '%s'?" % name, parent=self.frame):
            return
        ok, m = M.delete(self.kind, self.rid)
        self.page.say(("✓ " if ok else "⚠ ") + m, ok=ok)
        if ok:
            self.load()
            self.new(focus=False)

    def refresh(self):
        M.forget()
        self._fill_counts()
        self.select_kind(self.kind)

    # ── keys / focus ───────────────────────────────────────────
    def _focus_form(self):
        k = M.KINDS[self.kind]
        for f in k["fields"]:
            w = self.widgets.get(f.col)
            try:
                if str(w.cget("state")) not in ("disabled",):
                    w.focus_set()
                    if isinstance(w, tk.Entry):
                        w.select_range(0, "end")
                    return
            except Exception:
                continue

    def _focus_table(self):
        try:
            kids = self.tree.get_children()
            if kids:
                cur = self.tree.selection() or (kids[0],)
                self.tree.focus_set()
                self.tree.focus(cur[0])
                self.tree.selection_set(cur[0])
        except Exception:
            pass
        return "break"

    def _bind_keys(self, root=None):
        """Keys bound on this page's own widgets, never on the main window
        (there they would take over F5 / Ctrl+N of the other screens)."""
        keys = (("<Insert>", lambda: self.new()), ("<Control-n>", lambda: self.new()),
                ("<Control-s>", self.save), ("<F5>", self.refresh),
                ("<Control-f>", lambda: (self.search_e.focus_set(),
                                         self.search_e.select_range(0, "end"))))

        def run(fn):
            def h(_e=None):
                try:
                    fn()
                except Exception as ex:
                    self.page.say("⚠ %s" % str(ex)[:160], ok=False)
                return "break"
            return h

        def walk(w):
            for seq, fn in keys:
                try:
                    w.bind(seq, run(fn), add="+")
                except Exception:
                    pass
            for ch in w.winfo_children():
                if isinstance(ch, (tk.Toplevel, tk.Menu)):
                    continue
                walk(ch)
        try:
            walk(root or self.frame)
        except Exception:
            pass


def open_on(kind):
    """Menus: show the Masters page on one list (opening it if needed)."""
    v = MastersView._live
    try:
        if v is not None and v.frame.winfo_exists():
            v.select_kind(kind)
            return True
    except Exception:
        pass
    MastersView.start_kind = kind
    return False
