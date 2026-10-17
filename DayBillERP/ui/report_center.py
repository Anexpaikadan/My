# ============================================================
# DayBill ERP - Reports Center (screen)
# ------------------------------------------------------------
# One window for every report: pick a report from the groups on top
# (each a drop-down) or Find, set the period / filters, Run (F5). Totals, summary cards, Excel / PDF /
# Print on every report. Data comes from modules/report_center.py.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys, os, tempfile
import calendar
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules import report_center as RC

ICONS = {RC.GROUP_ACC: "📒", RC.GROUP_SALES: "🧾", RC.GROUP_PUR: "🛒", RC.GROUP_INV: "📦",
         getattr(RC, "GROUP_HR", "HR & Payroll"): "👔"}

QUICK = ["Today", "Yesterday", "This week", "This month", "Last month",
         "This quarter", "Last quarter", "This year", "Last year", "Custom"]


def quick_range(name, today=None):
    d = today or date.today()
    if name == "Today":
        return d, d
    if name == "Yesterday":
        y = d - timedelta(days=1)
        return y, y
    if name == "This week":
        return d - timedelta(days=(d.weekday() + 1) % 7), d   # week starts Sunday
    if name == "This month":
        return d.replace(day=1), d
    if name == "Last month":
        last = d.replace(day=1) - timedelta(days=1)
        return last.replace(day=1), last
    if name in ("This quarter", "Last quarter"):
        q = (d.month - 1) // 3
        if name == "Last quarter":
            q -= 1
        y = d.year
        if q < 0:
            q, y = 3, y - 1
        start = date(y, q * 3 + 1, 1)
        end_m = q * 3 + 3
        end = date(y, end_m, calendar.monthrange(y, end_m)[1])
        return start, min(end, d) if name == "This quarter" else end
    if name == "This year":                 # financial year (Settings ▸ Company)
        return cfg.fiscal_year_bounds(d)[0], d
    if name == "Last year":
        return cfg.fiscal_year_bounds(d, -1)
    return None, None


class _CalendarPopup(tk.Toplevel):
    """Tiny month calendar under a date box (click a day to pick)."""

    def __init__(self, anchor, var):
        super().__init__(anchor)
        self.var = var
        self.overrideredirect(True)
        self.configure(bg="#1F4E79")
        try:
            cur = date.fromisoformat(var.get())
        except Exception:
            cur = date.today()
        self.y, self.m = cur.year, cur.month
        self.sel = cur
        x = anchor.winfo_rootx(); y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        self.geometry(f"+{x}+{y}")
        self.body = tk.Frame(self, bg="white")
        self.body.pack(padx=1, pady=1)
        self._draw()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<FocusOut>", lambda e: self.after(150, self._maybe_close))
        self.focus_set()

    def _maybe_close(self):
        try:
            if self.focus_get() is None or not str(self.focus_get()).startswith(str(self)):
                self.destroy()
        except Exception:
            try:
                self.destroy()
            except Exception:
                pass

    def _draw(self):
        for w in self.body.winfo_children():
            w.destroy()
        hdr = tk.Frame(self.body, bg="white"); hdr.grid(row=0, column=0, columnspan=7, sticky="ew")
        tk.Button(hdr, text="‹", relief="flat", bg="white", cursor="hand2",
                  command=lambda: self._move(-1)).pack(side="left")
        tk.Label(hdr, text=f"{calendar.month_name[self.m]} {self.y}", bg="white",
                 font=("Segoe UI", 9, "bold")).pack(side="left", expand=True)
        tk.Button(hdr, text="›", relief="flat", bg="white", cursor="hand2",
                  command=lambda: self._move(1)).pack(side="right")
        for i, d in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            tk.Label(self.body, text=d, bg="white", fg="#6B7280",
                     font=("Segoe UI", 8)).grid(row=1, column=i, padx=1)
        for r, week in enumerate(calendar.monthcalendar(self.y, self.m), 2):
            for c, day in enumerate(week):
                if not day:
                    continue
                dd = date(self.y, self.m, day)
                is_sel = dd == self.sel; is_today = dd == date.today()
                tk.Button(self.body, text=str(day), width=3, relief="flat", cursor="hand2",
                          bg="#1F4E79" if is_sel else ("#E8EEF7" if is_today else "white"),
                          fg="white" if is_sel else "#1F2A44", font=("Segoe UI", 8),
                          command=lambda x=dd: self._pick(x)).grid(row=r, column=c, padx=1, pady=1)

    def _move(self, step):
        self.m += step
        if self.m == 0:
            self.m, self.y = 12, self.y - 1
        elif self.m == 13:
            self.m, self.y = 1, self.y + 1
        self._draw()

    def _pick(self, d):
        self.var.set(d.isoformat())
        self.destroy()


def _mix(c1, c2, t):
    try:
        return cfg.mix(c1, c2, t)
    except Exception:
        return c1


class ReportCenterView:
    """v6.2.1 layout: the report groups are on TOP (each one a drop-down
    with all its reports under it) + a Find box, so the report table gets
    the full page width. Colours come from the theme (🎨 Theme)."""

    def __init__(self, parent, initial=None):
        self.parent = parent
        self.C = C = cfg.theme()
        self._res = None
        self._current = None
        self._menus = {}
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build_nav(C)
        self._build_body(C)
        self._build_finder(C)
        self._fill_tree()
        self.select(initial or "sales_register")   # F5 = Run (via main window)

    # ── top: report groups (drop-downs) + Find ────────────────
    def _groups(self):
        out = []
        for spec in RC.catalog():
            if spec["group"] not in out:
                out.append(spec["group"])
        return out

    def _build_nav(self, C):
        nav = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        nav.pack(fill="x", padx=12, pady=(10, 0))
        self.nav = row = tk.Frame(nav, bg=C["card_bg"])
        row.pack(fill="x", padx=6, pady=5)
        self.group_btns = {}
        for g in self._groups():
            n = sum(1 for sp in RC.catalog() if sp["group"] == g)
            b = tk.Label(row, text=f"{ICONS.get(g, '•')}  {g}  ({n})  ▾", font=("Segoe UI", 10),
                         bg=C["card_bg"], fg=C["text_primary"], padx=12, pady=6, cursor="hand2")
            b.pack(side="left", padx=(0, 2))
            b.bind("<Button-1>", lambda e, g=g, b=b: self._group_menu(g, b))
            b.bind("<Enter>", lambda e, g=g, b=b: b.configure(bg=C["content_bg"])
                   if g != self._cur_group() else None)
            b.bind("<Leave>", lambda e, g=g, b=b: self._paint_group(g))
            self.group_btns[g] = b
        fbox = tk.Frame(row, bg=C["card_bg"], highlightbackground=C.get("field_border", C["border"]),
                        highlightthickness=1)
        fbox.pack(side="right", padx=(8, 2))
        tk.Label(fbox, text="🔍", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(6, 0))
        self.find_var = tk.StringVar()
        self.find_entry = e = tk.Entry(fbox, textvariable=self.find_var, width=26, relief="flat",
                                       bd=0, font=("Segoe UI", 10), bg=C["card_bg"],
                                       fg=C["text_primary"], insertbackground=C["text_primary"])
        e.pack(side="left", ipady=4, padx=(4, 6))
        self._find_hint = tk.Label(fbox, text="Find a report…", font=("Segoe UI", 9),
                                   bg=C["card_bg"], fg=C["text_secondary"], cursor="xterm")
        self._find_hint.place(in_=e, x=2, rely=0.5, anchor="w")
        self._find_hint.bind("<Button-1>", lambda ev: e.focus_set())
        self.find_var.trace_add("write", lambda *a: self._fill_tree())
        e.bind("<Down>", lambda ev: self._finder_focus())
        e.bind("<Return>", lambda ev: self._finder_open_first())
        e.bind("<Escape>", lambda ev: self.find_var.set(""))
        e.bind("<FocusIn>", lambda ev: self._find_hint.place_forget())
        e.bind("<FocusOut>", lambda ev: self.frame.after(200, self._finder_maybe_hide))

    def _cur_group(self):
        return RC.REGISTRY[self._current]["group"] if self._current in RC.REGISTRY else None

    def _paint_group(self, g):
        C, b = self.C, self.group_btns.get(g)
        if b is None:
            return
        on = g == self._cur_group()
        b.configure(bg=C.get("primary_light", C["content_bg"]) if on else C["card_bg"],
                    fg=C["primary"] if on else C["text_primary"],
                    font=("Segoe UI", 10, "bold" if on else "normal"))

    def _group_menu(self, g, widget=None, popup=True):
        """All the reports of a group, in a drop-down under its button."""
        C = self.C
        m = tk.Menu(self.frame, tearoff=0, font=("Segoe UI", 10),
                    activebackground=C["primary"], activeforeground="white")
        for spec in RC.catalog():
            if spec["group"] != g:
                continue
            on = spec["id"] == self._current
            m.add_command(label=("●  " if on else "     ") + spec["title"],
                          command=lambda r=spec["id"]: self.select(r))
        self._menus[g] = m
        if popup and widget is not None:
            try:
                m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
            finally:
                try:
                    m.grab_release()
                except Exception:
                    pass
        return m

    # ── Find: matching reports drop down under the box ────────
    def _build_finder(self, C):
        self.finder = tk.Frame(self.frame, bg=C["border"])
        inner = tk.Frame(self.finder, bg=C["card_bg"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        st = ttk.Style()
        st.configure("RC.Treeview", rowheight=26, font=("Segoe UI", 10),
                     background=C["card_bg"], fieldbackground=C["card_bg"], borderwidth=0)
        self.tree = ttk.Treeview(inner, show="tree", style="RC.Treeview", selectmode="browse",
                                 height=12)
        vs = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("grp", font=("Segoe UI", 9, "bold"), foreground=C["primary"])
        self.tree.bind("<ButtonRelease-1>", self._on_pick)          # click = open
        self.tree.bind("<Return>", self._on_pick)
        self.tree.bind("<Escape>", lambda e: (self.find_var.set(""), self.find_entry.focus_set()))
        self.tree.bind("<FocusOut>", lambda e: self.frame.after(200, self._finder_maybe_hide))
        self._finder_on = False

    def _fill_tree(self):
        q = (self.find_var.get() if hasattr(self, "find_var") else "").strip().lower()
        try:
            if q:
                self._find_hint.place_forget()
            elif self.frame.focus_get() is not self.find_entry:
                self._find_hint.place(in_=self.find_entry, x=2, rely=0.5, anchor="w")
        except Exception:
            pass
        self.tree.delete(*self.tree.get_children())
        groups = {}
        for spec in RC.catalog():
            if q and q not in (spec["title"] + " " + spec["desc"] + " " + spec["group"]).lower():
                continue
            g = spec["group"]
            if g not in groups:
                groups[g] = self.tree.insert("", "end", iid="g:" + g,
                                             text=f"{ICONS.get(g, '•')}  {g}", open=True,
                                             tags=("grp",))
            self.tree.insert(groups[g], "end", iid=spec["id"], text="   " + spec["title"])
        if q:
            self._finder_show(bool(groups))
        else:
            self._finder_hide()

    def _finder_show(self, any_found=True):
        if not any_found:
            self.tree.insert("", "end", iid="g:none", text="   No report found", tags=("grp",))
        try:
            self.finder.place(in_=self.find_entry.master, relx=1.0, rely=1.0, x=0, y=3,
                              anchor="ne", width=420)
            self.finder.lift()
            self._finder_on = True
        except Exception:
            pass

    def _finder_hide(self):
        try:
            self.finder.place_forget()
        except Exception:
            pass
        self._finder_on = False

    def _finder_maybe_hide(self):
        try:
            f = self.frame.focus_get()
        except Exception:
            f = None
        if f is not self.tree and f is not self.find_entry:
            self._finder_hide()
        if f is not self.find_entry and not self.find_var.get():
            try:
                self._find_hint.place(in_=self.find_entry, x=2, rely=0.5, anchor="w")
            except Exception:
                pass

    def _finder_first(self):
        for g in self.tree.get_children():
            for c in self.tree.get_children(g):
                return c
        return None

    def _finder_focus(self):
        first = self._finder_first()
        if first:
            self.tree.focus_set(); self.tree.focus(first)
            self.tree.selection_set(first); self.tree.see(first)
        return "break"

    def _finder_open_first(self):
        first = self._finder_first()
        if first:
            self.find_var.set("")
            self.select(first)
        return "break"

    def _on_pick(self, _e=None):
        sel = self.tree.selection()
        if _e is not None and getattr(_e, "y", None) is not None and getattr(_e, "keysym", "??") == "??":
            row = self.tree.identify_row(_e.y)          # the row under the mouse
            if row:
                sel = (row,)
        if not sel or sel[0].startswith("g:"):
            return
        if sel[0] != self._current or self._finder_on:
            rid = sel[0]
            if self._finder_on:
                self.find_var.set("")          # closes the list
            if rid != self._current:
                self._set_report(rid)

    def select(self, rid):
        """Open a report by id (used by the menus)."""
        if rid not in RC.REGISTRY:
            rid = "sales_register"
        self._set_report(rid)

    # ── the page: title + actions, filters, summary, table ────
    def _btn(self, parent, text, cmd, primary=False):
        C = self.C
        b = tk.Button(parent, text=text, command=cmd, cursor="hand2", relief="flat", bd=0,
                      font=("Segoe UI", 10 if primary else 9, "bold" if primary else "normal"),
                      bg=C["primary"] if primary else C["card_bg"],
                      fg="white" if primary else C["text_primary"],
                      activebackground=C.get("primary_dark", C["primary"]) if primary else C["content_bg"],
                      activeforeground="white" if primary else C["text_primary"],
                      padx=16 if primary else 11, pady=5,
                      highlightthickness=0 if primary else 1, highlightbackground=C["border"])
        return b

    def _build_body(self, C):
        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(8, 10))
        right = body
        head = tk.Frame(body, bg=C["content_bg"])
        head.pack(fill="x")
        acts = tk.Frame(head, bg=C["content_bg"])
        acts.pack(side="right", anchor="n", pady=(2, 0))
        for txt, cmd in (("📥  Excel", self.export_excel), ("📄  PDF", self.export_pdf),
                         ("🖨  Print", self.print_report), ("☰  Columns", self.columns)):
            self._btn(acts, txt, cmd).pack(side="left", padx=(6, 0))
        tl = tk.Frame(head, bg=C["content_bg"])
        tl.pack(side="left", fill="x", expand=True)
        self.title_var = tk.StringVar(); self.desc_var = tk.StringVar()
        self.group_var = tk.StringVar()
        tk.Label(tl, textvariable=self.group_var, font=("Segoe UI", 8, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        tk.Label(tl, textvariable=self.title_var, font=("Segoe UI", 15, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(anchor="w")
        desc = tk.Label(tl, textvariable=self.desc_var, font=("Segoe UI", 9), justify="left",
                        anchor="w", bg=C["content_bg"], fg=C["text_secondary"])
        desc.pack(anchor="w", fill="x")
        # long descriptions wrap to the room left of the buttons
        tl.bind("<Configure>", lambda e, d=desc: d.configure(wraplength=max(200, e.width - 8)))

        bar = tk.Frame(right, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        bar.pack(fill="x", pady=(8, 8))
        line = tk.Frame(bar, bg=C["card_bg"])
        line.pack(fill="x", padx=10, pady=7)
        self.bar = tk.Frame(line, bg=C["card_bg"]); self.bar.pack(side="left")
        today = date.today()
        self.from_var = tk.StringVar(value=today.replace(day=1).isoformat())
        self.to_var = tk.StringVar(value=today.isoformat())
        self.quick_var = tk.StringVar(value="This month")
        self.param_vars = {}
        self.run_btn = self._btn(line, "▶  Run  [F5]", self.run, primary=True)
        self.run_btn.pack(side="left", padx=(2, 0))
        self.extra_btn = tk.Button(line, text="", font=("Segoe UI", 9), bg=C["card_bg"],
                                   fg=C["warning"], relief="flat", padx=12, pady=5,
                                   cursor="hand2", highlightbackground=C["border"],
                                   highlightthickness=1, command=self._post_missing_cogs)
        self.status_var = tk.StringVar()
        crow = tk.Frame(right, bg=C["content_bg"]); crow.pack(fill="x")
        # period · rows on the right of the summary (the filter line stays free)
        tk.Label(crow, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right", anchor="s")
        self.cards = tk.Frame(crow, bg=C["content_bg"]); self.cards.pack(side="left", fill="x")

        tbl = tk.Frame(right, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        tbl.pack(fill="both", expand=True, pady=(8, 0))
        st = ttk.Style()
        st.configure("RCR.Treeview", rowheight=26, font=("Segoe UI", 9))
        st.configure("RCR.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.grid = ttk.Treeview(tbl, show="headings", style="RCR.Treeview")
        vs = ttk.Scrollbar(tbl, orient="vertical", command=self.grid.yview)
        hs = ttk.Scrollbar(tbl, orient="horizontal", command=self.grid.xview)
        self.grid.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y"); hs.pack(side="bottom", fill="x")
        self.grid.pack(fill="both", expand=True)
        card, pr = C["card_bg"], C["primary"]
        self.grid.tag_configure("odd", background=_mix(card, C["content_bg"], 0.55))
        self.grid.tag_configure("head", font=("Segoe UI", 9, "bold"),
                                background=C.get("primary_light", _mix(card, pr, 0.1)), foreground=pr)
        self.grid.tag_configure("total", font=("Segoe UI", 9, "bold"),
                                background=_mix(card, C["text_secondary"], 0.10))
        self.grid.tag_configure("grand", font=("Segoe UI", 10, "bold"),
                                background=C.get("primary_light", _mix(card, pr, 0.1)))
        self.grid.tag_configure("hi", background=_mix(card, pr, 0.05))
        self.grid.tag_configure("sub", font=("Segoe UI", 9, "italic"), foreground=C["text_secondary"])
        self.grid.tag_configure("neg", foreground=C["danger"])
        self.notes_var = tk.StringVar()
        notes = tk.Label(right, textvariable=self.notes_var, font=("Segoe UI", 8), justify="left",
                         anchor="w", bg=C["content_bg"], fg=C["text_secondary"], wraplength=600)
        notes.pack(fill="x", anchor="w", pady=(6, 0))
        # wrap the notes to the page width (a fixed width cut them off on both sides)
        notes.bind("<Configure>", lambda e: e.widget.configure(wraplength=max(200, e.width - 8)))

    def _date_box(self, parent, label, var):
        C = self.C
        tk.Label(parent, text=label, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        e = tk.Entry(parent, textvariable=var, width=11, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        e.pack(side="left", ipady=3, padx=(0, 10))
        try:                  # 📅 calendar + quick ranges + shortcuts (ui/datefield.py)
            from ui.datefield import enhance
            enhance(e, var, on_pick=lambda: self.quick_var.set("Custom"))
        except Exception:
            pass
        e.bind("<Return>", lambda ev: self.run())
        e.bind("<Key>", lambda ev: self.quick_var.set("Custom") if ev.char else None)
        return e

    def _set_report(self, rid):
        C = self.C
        self._current = rid
        spec = RC.REGISTRY[rid]
        self.title_var.set(spec["title"]); self.desc_var.set(spec["desc"])
        self.group_var.set(f"{ICONS.get(spec['group'], '•')}  {spec['group'].upper()}")
        for g in getattr(self, "group_btns", {}):
            self._paint_group(g)
        for w in self.bar.winfo_children():
            w.destroy()
        old = {k: v.get() for k, v in self.param_vars.items()}
        self.param_vars = {}
        p = spec["params"]
        if "period" in p or "as_of" in p:
            if "period" in p:
                self._date_box(self.bar, "From", self.from_var)
            self._date_box(self.bar, "To" if "period" in p else "As of", self.to_var)
            cb = ttk.Combobox(self.bar, textvariable=self.quick_var, values=QUICK,
                              state="readonly", width=12, font=("Segoe UI", 9))
            cb.pack(side="left", padx=(0, 12))
            cb.bind("<<ComboboxSelected>>", self._on_quick)
        elif "as_now" in p:
            tk.Label(self.bar, text="Current stock (as of now)", font=("Segoe UI", 9, "italic"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=(0, 14))

        def combo(key, label, values, width=18, default=None):
            tk.Label(self.bar, text=label, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            v = tk.StringVar(value=old.get(key) if old.get(key) in values else
                             (default if default is not None else (values[0] if values else "")))
            cbx = ttk.Combobox(self.bar, textvariable=v, values=values, width=width,
                               font=("Segoe UI", 9), state="readonly")
            cbx.pack(side="left", padx=(0, 12))
            cbx.bind("<<ComboboxSelected>>", lambda e: self.run())
            self.param_vars[key] = v

        def entry(key, label, width=16, hint=""):
            tk.Label(self.bar, text=label, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            v = tk.StringVar(value=old.get(key, ""))
            en = tk.Entry(self.bar, textvariable=v, width=width, font=("Segoe UI", 10),
                          relief="solid", bd=1)
            en.pack(side="left", ipady=3, padx=(0, 12))
            en.bind("<Return>", lambda e: self.run())
            self.param_vars[key] = v

        try:
            if "cashbank" in p or "account" in p:
                accs = RC.accounts_list("cashbank" if "cashbank" in p else "all")
                vals = [f"{c}  {n}" for c, n in accs]
                role = "bank" if rid == "bank_book" else "cash"
                dc = RC._default_code(role)
                default = next((x for x in vals if x.split()[0] == dc), vals[0] if vals else "")
                combo("account", "Account", vals, 30, default)
            if "category" in p:
                combo("category", "Category", ["All"] + RC.category_names(), 16)
        except Exception:
            pass
        if "product" in p:
            entry("product", "Product", 18)
        if "party" in p:
            entry("party", "Customer / Supplier", 18)
        if "channel" in p:
            combo("channel", "Channel", ["All", "POS", "Invoice"], 9)
        if "method" in p:
            combo("method", "Payment", ["All", "cash", "card", "bank", "credit"], 9)
        if "stock_filter" in p:
            combo("stock_filter", "Show", ["All", "In stock", "Low", "Out of stock", "Negative"], 12)
        if rid == "profit_loss":
            self.extra_btn.config(text="⚙  Post missing cost of sales")
            self.extra_btn.pack(side="left", padx=(8, 0))
        else:
            self.extra_btn.pack_forget()
        if rid == "stock_ledger" and not self.param_vars["product"].get():
            self._clear_result("Type a product code, barcode or name, then press Run.")
            return
        self.run()

    def _on_quick(self, _e=None):
        f, t = quick_range(self.quick_var.get())
        if f:
            self.from_var.set(f.isoformat()); self.to_var.set(t.isoformat())
            self.run()

    def _params(self):
        kw = {"date_from": self.from_var.get().strip(), "date_to": self.to_var.get().strip()}
        for k in ("date_from", "date_to"):
            try:
                date.fromisoformat(kw[k])
            except Exception:
                raise ValueError("Dates must be YYYY-MM-DD (e.g. %s)." % date.today().isoformat())
        for k, v in self.param_vars.items():
            val = v.get()
            if k == "account":
                val = val.split()[0] if val else ""
            kw[k] = val
        return kw

    # ── run & render ──────────────────────────────────────────
    def _clear_result(self, msg=""):
        self.grid.delete(*self.grid.get_children())
        self.grid["columns"] = ()
        for w in self.cards.winfo_children():
            w.destroy()
        self.notes_var.set(msg)
        self._res = None

    def run(self):
        if not self._current:
            return
        try:
            kw = self._params()
        except ValueError as e:
            self.status_var.set("⚠  " + str(e))
            return
        self.status_var.set("Running…")
        try:
            self.frame.update_idletasks()
        except Exception:
            pass
        try:
            res = RC.run(self._current, **kw)
        except Exception as e:
            self._clear_result()
            self.status_var.set("⚠  Could not run: " + str(e)[:120])
            return
        self._res = res
        self._render(res)

    def _render(self, res):
        C = self.C
        cols = res["columns"]
        self.grid.delete(*self.grid.get_children())
        self.grid["columns"] = [c["key"] for c in cols]
        # wide reports: keep every column at its width and scroll sideways
        # (stretching would squeeze the name column to a few letters)
        try:
            room = self.grid.winfo_width()
        except Exception:
            room = 0
        wide = room > 50 and sum(c["width"] for c in cols) > room
        for c in cols:
            self.grid.heading(c["key"], text=c["label"],
                              anchor="e" if c["align"] == "e" else "w")
            self.grid.column(c["key"], width=c["width"], minwidth=40,
                             anchor=c["align"],
                             stretch=(not wide) and c["kind"] == "text" and c["width"] >= 180)
        for i, r in enumerate(res["rows"]):
            st = r.get("_style")
            tags = [st] if st else (["odd"] if i % 2 else [])
            vals = []
            for c in cols:
                v = r.get(c["key"])
                vals.append(RC.fmt(v, c["kind"]) if c["kind"] in RC.NUMERIC else ("" if v is None else v))
            self.grid.insert("", "end", values=vals, tags=tags)
        if res.get("totals"):
            t = res["totals"]
            self.grid.insert("", "end", values=[
                RC.fmt(t.get(c["key"]), c["kind"]) if c["kind"] in RC.NUMERIC
                else (t.get(c["key"]) or "") for c in cols], tags=("total",))
        for w in self.cards.winfo_children():
            w.destroy()
        summ = (res.get("summary") or [])[:8]
        if summ:                            # one clean strip: label over value, thin dividers
            strip = tk.Frame(self.cards, bg=C["card_bg"], highlightbackground=C["border"],
                             highlightthickness=1)
            strip.pack(side="left", anchor="w")
            for i, (lbl, val, kind) in enumerate(summ):
                if i:
                    tk.Frame(strip, bg=C["border"], width=1).pack(side="left", fill="y", pady=6)
                cell = tk.Frame(strip, bg=C["card_bg"])
                cell.pack(side="left", padx=14, pady=4)
                tk.Label(cell, text=lbl, font=("Segoe UI", 8), bg=C["card_bg"],
                         fg=C["text_secondary"]).pack(anchor="w")
                neg = kind == "money" and isinstance(val, (int, float)) and val < 0
                tk.Label(cell, text=RC.fmt(val, kind) if kind in RC.NUMERIC else str(val),
                         font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                         fg=C["danger"] if neg else C["text_primary"]).pack(anchor="w")
        self.notes_var.set("   ".join("ℹ " + n for n in res.get("notes") or []))
        n = sum(1 for r in res["rows"] if not r.get("_style"))
        self.status_var.set(f"{res.get('subtitle', '')}   ·   {n} row(s)")

    # ── columns (v6.2): show / hide / order / width, remembered per report ──
    def columns(self):
        if not self._need():
            return
        from ui.table_columns import ColumnsDialog
        ColumnsDialog(self.grid)

    def _shown_res(self):
        """The result with only the columns on screen, in the screen order
        and at the screen widths — what Excel / PDF / Print use."""
        res = self._res
        try:
            from ui.table_columns import shown_columns
            from ui import zoom
            zf = zoom.factor() or 1.0
            by = {c["key"]: c for c in res["columns"]}
            cols = []
            for k in shown_columns(self.grid):
                if k in by:
                    w = int(round(int(self.grid.column(k, "width")) / zf))
                    cols.append(dict(by[k], width=max(30, w)))
            if cols:
                return dict(res, columns=cols)
        except Exception:
            pass
        return res

    # ── export / print ────────────────────────────────────────
    def _need(self):
        if not self._res:
            messagebox.showinfo("Reports", "Run a report first.", parent=self.frame)
            return False
        return True

    def _allowed(self, action):
        try:
            from modules import permissions as _pm
            return _pm.allowed("reports", action)
        except Exception:
            return True

    def _fname(self, ext):
        base = (self._res.get("title") or "Report").split("—")[0].strip().replace(" ", "_")
        base = "".join(ch for ch in base if ch.isalnum() or ch in "_-&")
        return f"{base}_{self.from_var.get()}_{self.to_var.get()}.{ext}"

    def export_excel(self):
        if not self._need() or not self._allowed("export"):
            return
        path = filedialog.asksaveasfilename(parent=self.frame, defaultextension=".xlsx",
                                            filetypes=[("Excel", "*.xlsx")],
                                            initialfile=self._fname("xlsx"))
        if not path:
            return
        try:
            RC.to_excel(self._shown_res(), path)
            self.status_var.set("Saved " + os.path.basename(path))
            try:
                os.startfile(path)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Excel", str(e)[:300], parent=self.frame)

    def export_pdf(self):
        if not self._need() or not self._allowed("print"):
            return
        path = filedialog.asksaveasfilename(parent=self.frame, defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf")],
                                            initialfile=self._fname("pdf"))
        if not path:
            return
        try:
            RC.to_pdf(self._shown_res(), path)
            self.status_var.set("Saved " + os.path.basename(path))
            try:
                os.startfile(path)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("PDF", str(e)[:300], parent=self.frame)

    def print_report(self):
        if not self._need() or not self._allowed("print"):
            return
        try:
            path = os.path.join(tempfile.gettempdir(), self._fname("pdf"))
            RC.to_pdf(self._shown_res(), path)
            from ui import print_menu
            ok = print_menu.send_pdf(self.frame, path, self._res.get("title", "Report")
                                     if isinstance(self._res, dict) else "Report", "report")
            self.status_var.set("Sent to printer." if ok else "Not printed — use PDF.")
        except Exception as e:
            messagebox.showerror("Print", str(e)[:300], parent=self.frame)

    def _post_missing_cogs(self):
        # v6.9.3: posting many journals at once → journal.approve; days in a
        # closed (or not selected) financial year are skipped and listed;
        # everything is posted in ONE transaction (all or nothing).
        try:
            from modules import permissions as _pm
            if not _pm.allowed("journal", "approve", parent=self.frame):
                return
        except Exception:
            return
        d_from, d_to = self.from_var.get(), self.to_var.get()
        try:
            runs, skipped = self._cogs_open_days(d_from, d_to)
        except Exception as e:
            messagebox.showerror("Cost of sales", str(e)[:300], parent=self.frame)
            return
        skip_txt = ""
        if skipped:
            n_inv = sum(n for _d, n in skipped)
            days = ", ".join(d for d, _n in skipped[:8]) + (" …" if len(skipped) > 8 else "")
            skip_txt = ("\n\nSkipped: %d sale(s) on %d day(s) in a closed financial year (or "
                        "outside the year chosen at sign-in): %s" % (n_inv, len(skipped), days))
        if not runs:
            messagebox.showinfo("Cost of sales", "Nothing to post in this period." + skip_txt,
                                parent=self.frame)
            return
        if not messagebox.askyesno(
                "Cost of sales",
                "Post a cost-of-sales entry (Dr Cost of Goods Sold / Cr Inventory) for "
                "every confirmed sale in this period that has none yet?\n\n"
                "Use this once for sales saved before this update. Stock quantities "
                "are not changed." + skip_txt, parent=self.frame):
            return
        try:
            from config.database import db
            from modules import doc_posting
            n, amt = 0, 0.0
            with db.transaction():                  # all or nothing
                for a, b in runs:
                    k, x = doc_posting.post_missing_cogs(a, b)
                    n += k
                    amt += x
        except Exception as e:
            messagebox.showerror("Cost of sales", "Nothing was posted:\n%s" % str(e)[:300],
                                 parent=self.frame)
            return
        try:
            from ui import danger
            danger.audit("post", "journal", None,
                         "Missing cost of sales %s → %s: %d entr%s, %.2f SAR; %d day(s) skipped "
                         "(closed year)" % (d_from, d_to, n, "y" if n == 1 else "ies", amt,
                                            len(skipped)))
        except Exception:
            pass
        messagebox.showinfo("Cost of sales", f"Posted {n} entr{'y' if n == 1 else 'ies'} "
                            f"· {amt:,.2f} SAR." + skip_txt, parent=self.frame)
        self.run()

    @staticmethod
    def _cogs_open_days(d_from, d_to):
        """Days with confirmed sales that have no cost entry yet →
        ([(from, to) runs of days that may be posted], [(day, sales) skipped]).
        A day is skipped when financial_year.guard_active() says no."""
        from config.database import db
        from modules import financial_year as FY
        where = ["si.invoice_status='confirmed'",
                 "NOT EXISTS (SELECT 1 FROM journal_entries je WHERE je.source_type='cogs' "
                 "AND je.source_id=si.invoice_id)"]
        params = []
        if d_from:
            where.append("si.invoice_date >= ?"); params.append(d_from)
        if d_to:
            where.append("si.invoice_date <= ?"); params.append(d_to)
        rows = db.fetchall("SELECT si.invoice_date AS d, COUNT(*) AS n FROM sales_invoices si WHERE "
                           + " AND ".join(where) + " GROUP BY si.invoice_date ORDER BY si.invoice_date",
                           tuple(params)) or []
        runs, skipped, cur = [], [], None
        for r in rows:
            d = str(r["d"])[:10]
            if FY.guard_active(d):                  # closed / not the chosen year
                skipped.append((d, int(r["n"] or 0)))
                if cur:
                    runs.append(tuple(cur))
                    cur = None
                continue
            if cur:
                cur[1] = d
            else:
                cur = [d, d]
        if cur:
            runs.append(tuple(cur))
        return runs, skipped
