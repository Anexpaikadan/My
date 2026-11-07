# ============================================================
# DayBill ERP - Consumable entry screens (v6.9.3)
#   ConsumptionView  list (Inventory ▸ 🍞 Consumable Entry)
#   ConsumptionForm  one entry: what the shop used itself — staff /
#                    room food, a production unit (bakery, kitchen),
#                    shop supplies, samples, damaged stock
# Keys: Enter adds the item · Delete removes the line · Ctrl+S save ·
#       Ctrl+D save as draft · Esc close · F1 all shortcut keys
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from config import settings as cfg
from config.database import db
from modules import consumption as CN
from modules import permissions as perm
from ui import close_guard


def _money(v):
    try:
        return "{:,.2f}".format(float(v or 0))
    except (TypeError, ValueError):
        return "0.00"


class ConsumptionView:
    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(top, text="🍞  Consumable Entry", font=("Segoe UI", 16, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Label(top, text="  stock used by the shop itself — staff food, bakery / kitchen, "
                      "shop supplies, samples, damaged", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        for txt, cmd, primary in (("＋  New", self._new, True),
                                  ("✏  Edit", self._edit, False),
                                  ("🗑  Delete", self._delete, False)):
            tk.Button(top, text=txt, font=("Segoe UI", 9, "bold"),
                      bg=C["primary"] if primary else C["card_bg"],
                      fg="white" if primary else C["text_primary"], relief="flat",
                      padx=12, pady=5, cursor="hand2", command=cmd).pack(side="right", padx=(6, 0))

        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=20, pady=(2, 6))
        today = date.today()
        self.from_v = tk.StringVar(value=today.replace(day=1).isoformat())
        self.to_v = tk.StringVar(value=today.isoformat())
        self.purpose_v = tk.StringVar(value="All")
        for lbl, var, w in (("From", self.from_v, 11), ("To", self.to_v, 11)):
            tk.Label(bar, text=lbl, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            tk.Entry(bar, textvariable=var, width=w, font=("Segoe UI", 10), relief="solid",
                     bd=1).pack(side="left", padx=(0, 10))
        tk.Label(bar, text="Used for", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.purpose_v, state="readonly", width=34,
                     values=["All"] + [en for _k, en, _a, _c in CN.PURPOSES]).pack(side="left")
        tk.Button(bar, text="🔍 Show", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                  relief="flat", padx=10, cursor="hand2", command=self._load).pack(side="left", padx=8)
        self.sum_v = tk.StringVar()
        tk.Label(bar, textvariable=self.sum_v, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="right")

        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        cols = ("no", "date", "purpose", "unit", "account", "cost", "status", "notes")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, t, w, a in (("no", "Number", 110, "w"), ("date", "Date", 90, "center"),
                           ("purpose", "Used for", 230, "w"), ("unit", "Room / unit", 140, "w"),
                           ("account", "Expense account", 200, "w"), ("cost", "Cost", 100, "e"),
                           ("status", "Status", 80, "center"), ("notes", "Notes", 220, "w")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.tree.bind("<Return>", lambda e: self._edit())
        self.tree.bind("<Delete>", lambda e: self._delete())
        self.frame.new_record = self._new          # Ctrl+N (main window shortcut)
        self._load()

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        want = self.purpose_v.get()
        pkey = next((k for k, en, _a, _c in CN.PURPOSES if en == want), None)
        rows = CN.entries(self.from_v.get(), self.to_v.get(), pkey)
        tot = 0.0
        for r in rows:
            tot += float(r.get("total_cost") or 0) if r.get("entry_status") == "confirmed" else 0
            acc = ("%s %s" % (r.get("account_code") or "", r.get("account_name_en") or "")).strip()
            self.tree.insert("", "end", iid=str(r["entry_id"]), values=(
                r["entry_number"], str(r.get("entry_date") or "")[:10],
                CN.purpose_label(r.get("purpose")), r.get("unit_name") or "", acc,
                _money(r.get("total_cost")), (r.get("entry_status") or "").title(),
                r.get("notes") or ""))
        self.sum_v.set("%d entries · used %s SAR" % (len(rows), _money(tot)))

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _new(self):
        from ui import txn_connector as tc
        tc.new_txn(self.frame, "consumption", self._load)

    def _edit(self):
        eid = self._sel()
        if not eid:
            return
        from ui import txn_connector as tc
        t = dict(key="consumption", journal_id=None, doc_id=eid, number="",
                 source_type="consumption", source_id=eid, label=tc.CONN["consumption"]["label"])
        if not tc.can("consumption", "edit"):
            ConsumptionForm(self.frame, entry_id=eid, view_only=True)
            return
        tc.edit_txn(self.frame, t, self._load)

    def _delete(self):
        eid = self._sel()
        if not eid:
            return
        from ui import txn_connector as tc
        t = dict(key="consumption", journal_id=None, doc_id=eid, number="",
                 source_type="consumption", source_id=eid, label=tc.CONN["consumption"]["label"])
        if tc.delete_txn(self.frame, t, self._load):
            self._load()


class ConsumptionForm:
    def __init__(self, parent, entry_id=None, on_save=None, view_only=False):
        C = self.C = cfg.theme()
        self.entry_id = entry_id
        self.on_save = on_save
        self.view_only = view_only
        self.lines = []
        self._load_products()
        w = self.win = tk.Toplevel(parent)
        w._is_dirty = self._is_dirty        # close guard: ask only when unsaved
        w.title("Consumable Entry")
        w.geometry("940x620")
        w.minsize(760, 460)
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass

        band = tk.Frame(w, bg=C["primary"])
        band.pack(fill="x")
        self.title_v = tk.StringVar(value="🍞  New Consumable Entry")
        tk.Label(band, textvariable=self.title_v, font=("Segoe UI", 11, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=12, pady=6)

        head = tk.Frame(w, bg=C["card_bg"])
        head.pack(fill="x", padx=10, pady=(8, 4))
        self.date_v = tk.StringVar(value=date.today().isoformat())
        self.purpose_v = tk.StringVar(value=CN.PURPOSES[0][1])
        self.unit_v = tk.StringVar()
        self.notes_v = tk.StringVar()
        self.status_v = tk.StringVar(value="confirmed")

        def lbl(r, c, t):
            tk.Label(head, text=t, font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=c, sticky="w", padx=(8, 4), pady=3)
        st = "disabled" if view_only else "normal"
        lbl(0, 0, "Date")
        tk.Entry(head, textvariable=self.date_v, width=12, font=("Segoe UI", 10), relief="solid",
                 bd=1, state=st).grid(row=0, column=1, sticky="w")
        lbl(0, 2, "Used for")
        self.purpose_cb = ttk.Combobox(head, textvariable=self.purpose_v, width=36,
                                       state="disabled" if view_only else "readonly",
                                       values=[en for _k, en, _a, _c in CN.PURPOSES])
        self.purpose_cb.grid(row=0, column=3, sticky="w")
        self.purpose_cb.bind("<<ComboboxSelected>>", lambda e: self._show_account())
        lbl(0, 4, "Room / production unit")
        tk.Entry(head, textvariable=self.unit_v, width=20, font=("Segoe UI", 10), relief="solid",
                 bd=1, state=st).grid(row=0, column=5, sticky="w")
        lbl(1, 0, "Notes")
        tk.Entry(head, textvariable=self.notes_v, width=60, font=("Segoe UI", 10), relief="solid",
                 bd=1, state=st).grid(row=1, column=1, columnspan=3, sticky="we")
        self.acc_v = tk.StringVar()
        tk.Label(head, textvariable=self.acc_v, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["primary"]).grid(row=1, column=4, columnspan=2, sticky="w", padx=8)

        add = tk.Frame(w, bg=C["content_bg"])
        add.pack(fill="x", padx=10, pady=(2, 2))
        tk.Label(add, text="Item (scan / code / name)", font=("Segoe UI", 8, "bold"),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        self.item_v = tk.StringVar()
        self.item_cb = ttk.Combobox(add, textvariable=self.item_v, width=44,
                                    values=self._choices, state=st)
        self.item_cb.pack(side="left", padx=4)
        self.item_cb.bind("<KeyRelease>", self._filter)
        self.item_cb.bind("<<ComboboxSelected>>", lambda e: self._pick_units())
        tk.Label(add, text="Qty", font=("Segoe UI", 8, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(8, 2))
        self.qty_v = tk.StringVar(value="1")
        self.qty_e = tk.Entry(add, textvariable=self.qty_v, width=7, font=("Segoe UI", 10),
                              relief="solid", bd=1, justify="right", state=st)
        self.qty_e.pack(side="left")
        tk.Label(add, text="Unit", font=("Segoe UI", 8, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(8, 2))
        self.unit_cb_v = tk.StringVar()
        self.unit_cb = ttk.Combobox(add, textvariable=self.unit_cb_v, width=10,
                                    state="disabled" if view_only else "readonly")
        self.unit_cb.pack(side="left")
        self.add_btn = tk.Button(add, text="＋ Add  [Enter]", font=("Segoe UI", 9, "bold"),
                                 bg=C["primary"], fg="white", relief="flat", padx=10,
                                 cursor="hand2", command=self._add, state=st)
        self.add_btn.pack(side="left", padx=8)
        for wdg in (self.item_cb, self.qty_e):
            wdg.bind("<Return>", lambda e: (self._add(), "break")[1])

        wrap = tk.Frame(w, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("n", "code", "name", "qty", "unit", "cost", "total")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, t, wd, a in (("n", "#", 40, "center"), ("code", "Code", 100, "w"),
                            ("name", "Item", 330, "w"), ("qty", "Qty", 80, "e"),
                            ("unit", "Unit", 80, "center"), ("cost", "Unit cost", 100, "e"),
                            ("total", "Cost", 110, "e")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=wd, anchor=a)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Delete>", lambda e: self._remove())

        foot = tk.Frame(w, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        foot.pack(fill="x", side="bottom")
        self.total_v = tk.StringVar(value="Cost 0.00")
        tk.Label(foot, textvariable=self.total_v, font=("Segoe UI", 13, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(side="left", padx=12, pady=6)
        tk.Label(foot, text="Dr expense · Cr Inventory, at cost · no VAT",
                 font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=6)
        tk.Button(foot, text="Esc  Close", font=("Segoe UI", 9), relief="flat", padx=10,
                  cursor="hand2", command=self._close).pack(side="right", padx=6, pady=6)
        if not view_only:
            tk.Button(foot, text="✔ Save  [Ctrl+S]", font=("Segoe UI", 9, "bold"),
                      bg=C.get("success", "#16A34A"), fg="white", relief="flat", padx=12,
                      cursor="hand2", command=lambda: self._save(confirm=True)).pack(
                          side="right", padx=4, pady=6)
            tk.Button(foot, text="Save draft  [Ctrl+D]", font=("Segoe UI", 9), relief="flat",
                      padx=10, cursor="hand2",
                      command=lambda: self._save(confirm=False)).pack(side="right", padx=4)
            tk.Button(foot, text="Remove line  [Del]", font=("Segoe UI", 9), relief="flat",
                      padx=10, cursor="hand2", command=self._remove).pack(side="left", padx=6)
            w.bind("<Control-s>", lambda e: (self._save(confirm=True), "break")[1])
            w.bind("<Control-S>", lambda e: (self._save(confirm=True), "break")[1])
            w.bind("<Control-d>", lambda e: (self._save(confirm=False), "break")[1])
        # Esc / ✕ / Close: ui/close_guard.py asks only when lines are unsaved
        close_guard.bind_escape(w)
        if entry_id:
            self._load_entry()
        self._show_account()
        try:
            from ui import txn_connector as _tc
            _tc.attach(self, "consumption")
        except Exception:
            pass
        if not view_only:
            self.item_cb.focus_set()

    # ── data ──────────────────────────────────────────────────
    def _load_products(self):
        try:
            self.products = db.fetchall(
                "SELECT product_id, product_code, product_name_en, barcode, unit_of_measure_en "
                "FROM products WHERE ISNULL(is_active,1)=1 ORDER BY product_name_en") or []
        except Exception:
            self.products = []
        self._choices = ["%s — %s" % (p.get("product_code") or "", p.get("product_name_en") or "")
                         for p in self.products]

    def _filter(self, e=None):
        if e is not None and e.keysym in ("Return", "Up", "Down", "Escape", "Tab"):
            return
        q = self.item_v.get().strip().lower()
        if not q:
            self.item_cb["values"] = self._choices
            return
        self.item_cb["values"] = [c for c in self._choices if all(t in c.lower() for t in q.split())][:60]

    def _product(self):
        txt = self.item_v.get().strip()
        if not txt:
            return None
        code = txt.split(" — ")[0].strip().lower()
        for p in self.products:                         # barcode / code typed or scanned
            if str(p.get("barcode") or "").lower() == txt.lower() or \
                    str(p.get("product_code") or "").lower() == code:
                return p
        hits = [p for p, c in zip(self.products, self._choices)
                if all(t in c.lower() for t in txt.lower().split())]
        return hits[0] if len(hits) == 1 else None

    def _units(self, p):
        out = [p.get("unit_of_measure_en") or "PCs"]
        try:
            for r in db.fetchall("SELECT unit_name_en FROM product_units WHERE product_id=? "
                                 "AND ISNULL(is_active,1)=1", (p["product_id"],)) or []:
                if r.get("unit_name_en") and r["unit_name_en"] not in out:
                    out.append(r["unit_name_en"])
        except Exception:
            pass
        return out

    def _pick_units(self):
        p = self._product()
        if p:
            u = self._units(p)
            self.unit_cb["values"] = u
            self.unit_cb_v.set(u[0])
            self.qty_e.focus_set()
            self.qty_e.select_range(0, "end")

    def _add(self):
        if self.view_only:
            return
        p = self._product()
        if not p:
            self.item_cb.event_generate("<Down>")
            return
        try:
            qty = float(self.qty_v.get() or 0)
        except ValueError:
            qty = 0
        if qty <= 0:
            messagebox.showwarning("Quantity", "Type a quantity above 0.", parent=self.win)
            return
        unit = self.unit_cb_v.get() or (p.get("unit_of_measure_en") or "PCs")
        if unit not in self._units(p):
            unit = p.get("unit_of_measure_en") or "PCs"
        same = next((l for l in self.lines if l["product_id"] == p["product_id"]
                     and l["unit_of_measure_en"] == unit), None)
        if same:
            same["quantity"] += qty
        else:
            self.lines.append({"product_id": p["product_id"], "product_code": p.get("product_code"),
                               "product_name_en": p.get("product_name_en"), "quantity": qty,
                               "unit_of_measure_en": unit,
                               "unit_cost": CN.line_cost(p["product_id"], unit)})
        self.item_v.set("")
        self.qty_v.set("1")
        self.unit_cb_v.set("")
        self.item_cb["values"] = self._choices
        self._render()
        self.item_cb.focus_set()

    def _remove(self):
        if self.view_only:
            return
        for iid in self.tree.selection():
            i = int(iid)
            if 0 <= i < len(self.lines):
                self.lines[i] = None
        self.lines = [l for l in self.lines if l]
        self._render()

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        tot = 0.0
        for i, l in enumerate(self.lines):
            t = round(float(l.get("unit_cost") or 0) * float(l["quantity"]), 2)
            tot += t
            self.tree.insert("", "end", iid=str(i), values=(
                i + 1, l.get("product_code") or "", l.get("product_name_en") or "",
                "%g" % float(l["quantity"]), l["unit_of_measure_en"],
                _money(l.get("unit_cost")), _money(t)))
        self.total_v.set("Cost %s SAR" % _money(tot))

    def _purpose_key(self):
        return next((k for k, en, _a, _c in CN.PURPOSES if en == self.purpose_v.get()), "staff_food")

    def _show_account(self):
        code = CN.account_code_for(self._purpose_key())
        try:
            r = db.fetchone("SELECT account_code, account_name_en FROM accounts WHERE account_code=?",
                            (code,)) or {}
        except Exception:
            r = {}
        self.acc_v.set("→ expense %s %s" % (r.get("account_code") or code, r.get("account_name_en") or ""))

    def _load_entry(self):
        h, lines = CN.get(self.entry_id)
        if not h:
            return
        self.date_v.set(str(h.get("entry_date") or "")[:10])
        self.purpose_v.set(CN.purpose_label(h.get("purpose")))
        self.unit_v.set(h.get("unit_name") or "")
        self.notes_v.set(h.get("notes") or "")
        self.status_v.set(h.get("entry_status") or "confirmed")
        self.lines = [{"product_id": l["product_id"], "product_code": l.get("product_code"),
                       "product_name_en": l.get("product_name_en"),
                       "quantity": float(l.get("quantity") or 0),
                       "unit_of_measure_en": l.get("unit_of_measure_en") or "PCs",
                       "unit_cost": float(l.get("unit_cost") or 0)} for l in lines]
        self.title_v.set("🍞  Consumable Entry  %s  (%s)" % (h["entry_number"],
                                                           (h.get("entry_status") or "").title()))
        self._render()
        self._mark_clean()

    # ── save / close ──────────────────────────────────────────
    def _save(self, confirm=True):
        if self.view_only:
            return False
        action = "edit" if self.entry_id else "add"
        if not perm.allowed("consumption", action, parent=self.win):
            return False
        # v6.9.5: a CONFIRMED entry stays confirmed when it is changed
        # (Save draft / Ctrl+D took its stock and journal back out)
        if self.entry_id and not confirm:
            from modules import doc_edit
            confirm = doc_edit.info("consumption", self.entry_id)[1] == "confirmed"
        if not self.lines:
            messagebox.showwarning("Consumable Entry", "Add at least one item.", parent=self.win)
            return False
        u = perm.session_user() or {}
        try:
            eid, number, warn = CN.save(
                {"entry_date": self.date_v.get(), "purpose": self._purpose_key(),
                 "unit_name": self.unit_v.get(), "notes": self.notes_v.get(),
                 "entry_status": "confirmed" if confirm else "draft", "_edit": bool(self.entry_id)},
                self.lines, entry_id=self.entry_id, user_id=u.get("user_id"))
        except Exception as e:
            messagebox.showerror("Consumable Entry", str(e)[:300], parent=self.win)
            return False
        was = self.entry_id
        self.entry_id = eid
        self._saved = True
        self._mark_clean()              # close guard: nothing unsaved now
        messagebox.showinfo("Consumable Entry",
                            "%s saved%s." % (number, "" if confirm else " as draft (no stock moved)")
                            + (("\n\n⚠ " + warn) if warn else ""), parent=self.win)
        if self.on_save:
            try:
                self.on_save()
            except Exception:
                pass
        # v6.9.3: the window stays open (Settings ▸ General ▸ After saving)
        from ui import after_save
        parent, cb = self.win.master, self.on_save
        after_save.finish(self, number,
                          new=lambda: ConsumptionForm(parent, on_save=cb),
                          keep=lambda: ConsumptionForm(parent, entry_id=eid, on_save=cb),
                          edited=bool(was))
        return True

    def _close(self):
        """Close button: like ✕ — close_guard asks "close without saving?"
        only when _is_dirty() (one question, never two)."""
        close_guard.request_close(self.win)

    def _mark_clean(self):
        """The lines now match the saved / loaded entry."""
        self._clean_sig = close_guard.lines_sig(self.lines)

    def _is_dirty(self):
        """Lines added and not saved: a new entry, or lines changed since
        load / save."""
        if self.view_only or not self.lines:
            return False
        if not self.entry_id:
            return True
        return close_guard.lines_sig(self.lines) != getattr(self, "_clean_sig", None)
