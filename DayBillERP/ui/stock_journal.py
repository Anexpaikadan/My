# ============================================================
# DayBill ERP - Stock Journal screens (v7.11.0)
#   StockJournalView  list (Inventory ▸ 📒 Stock Journal) with a tab per
#                     type: Damage · Excess · Shortage · All
#   StockJournalForm  one entry — items, quantities, the reason; the
#                     stock moves at cost when it is saved (confirmed)
# Keys: Enter adds the item · Delete removes the line · Ctrl+S save ·
#       Ctrl+D save as draft · Ctrl+P print · Esc close
# ============================================================

import os
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from config import settings as cfg
from config.database import db
from modules import stock_journal as SJ
from modules import permissions as perm
from ui import close_guard

ALL = "all"


def _money(v):
    try:
        return "{:,.2f}".format(float(v or 0))
    except (TypeError, ValueError):
        return "0.00"


def _cur():
    try:
        from modules import country as _c
        return _c.symbol()
    except Exception:
        return "SAR"


class StockJournalView:
    start_kind = None              # the menu opens the list on one type

    def __init__(self, parent, kind=None):
        C = self.C = cfg.theme()
        self.kind = kind or StockJournalView.start_kind or ALL
        StockJournalView.start_kind = None
        StockJournalView._live = self
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(top, text="📒  Stock Journal", font=("Segoe UI", 16, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Label(top, text="  damaged, extra and missing stock — each with its own number",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.btns = {}
        for txt, cmd, primary in (("🗑  Delete", self._delete, False),
                                  ("✏  Edit", self._edit, False)):
            tk.Button(top, text=txt, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                      command=cmd).pack(side="right", padx=(6, 0))
        for k in reversed(SJ.KEYS):
            t = SJ.T[k]
            tk.Button(top, text="＋ %s" % t["en"].split(" (")[0], font=("Segoe UI", 9, "bold"),
                      bg=C["primary"], fg="white", relief="flat", padx=12, pady=5,
                      cursor="hand2", command=lambda k=k: self._new(k)).pack(side="right",
                                                                         padx=(6, 0))

        # type tabs
        tabs = tk.Frame(self.frame, bg=C["content_bg"])
        tabs.pack(fill="x", padx=20, pady=(4, 2))
        self.tab_btns = {}
        for k, txt in [(ALL, "All")] + [(k, "%s  %s" % (SJ.T[k]["icon"], SJ.T[k]["en"]))
                                        for k in SJ.KEYS]:
            b = tk.Button(tabs, text=txt, font=("Segoe UI", 9, "bold"), relief="flat",
                          padx=12, pady=4, cursor="hand2", command=lambda k=k: self.show(k))
            b.pack(side="left", padx=(0, 4))
            self.tab_btns[k] = b

        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=20, pady=(4, 6))
        today = date.today()
        self.from_v = tk.StringVar(value=today.replace(day=1).isoformat())
        self.to_v = tk.StringVar(value=today.isoformat())
        for lbl, var in (("From", self.from_v), ("To", self.to_v)):
            tk.Label(bar, text=lbl, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            e = tk.Entry(bar, textvariable=var, width=11, font=("Segoe UI", 10), relief="solid",
                         bd=1)
            e.pack(side="left", padx=(0, 10))
            try:
                from ui.datefield import DateBox
                DateBox(e, var)
            except Exception:
                pass
        tk.Button(bar, text="🔍 Show", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                  relief="flat", padx=10, cursor="hand2", command=self._load).pack(side="left")
        self.sum_v = tk.StringVar()
        tk.Label(bar, textvariable=self.sum_v, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="right")

        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        cols = ("no", "date", "type", "reason", "account", "cost", "status", "notes")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, t, w, a in (("no", "Number", 150, "w"), ("date", "Date", 90, "center"),
                           ("type", "Type", 150, "w"), ("reason", "Reason", 170, "w"),
                           ("account", "Account", 190, "w"), ("cost", "Cost", 100, "e"),
                           ("status", "Status", 80, "center"), ("notes", "Notes", 200, "w")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.tree.bind("<Return>", lambda e: self._edit())
        self.tree.bind("<Delete>", lambda e: self._delete())
        self.frame.new_record = lambda: self._new(self.kind if self.kind != ALL else "damage")
        if not SJ.ready():
            self.sum_v.set("⚠ needs the v7.11 database update (it runs when DayBill starts)")
        self.show(self.kind)

    def show(self, kind):
        self.kind = kind
        C = self.C
        for k, b in self.tab_btns.items():
            on = k == kind
            b.configure(bg=C["primary"] if on else C["card_bg"],
                        fg="white" if on else C["text_primary"])
        self._load()

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        rows = SJ.entries(None if self.kind == ALL else self.kind, self.from_v.get(),
                          self.to_v.get())
        tot = {k: 0.0 for k in SJ.KEYS}
        for r in rows:
            if r.get("entry_status") == "confirmed" and r.get("entry_type") in tot:
                tot[r["entry_type"]] += float(r.get("total_cost") or 0)
            acc = ("%s %s" % (r.get("account_code") or "", r.get("account_name_en") or "")).strip()
            t = SJ.T.get(r.get("entry_type"), {})
            self.tree.insert("", "end", iid=str(r["entry_id"]), values=(
                r["entry_number"], str(r.get("entry_date") or "")[:10],
                "%s %s" % (t.get("icon", ""), t.get("en", r.get("entry_type"))),
                r.get("reason") or "", acc, _money(r.get("total_cost")),
                (r.get("entry_status") or "").title(), r.get("notes") or ""))
        parts = ["%s %s" % (SJ.T[k]["en"].split(" (")[0], _money(v))
                 for k, v in tot.items() if self.kind in (ALL, k)]
        self.sum_v.set("%d entries · %s %s" % (len(rows), " · ".join(parts), _cur()))

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _txn(self, eid):
        from ui import txn_connector as tc
        return dict(key="stock_journal", journal_id=None, doc_id=eid, number="",
                    source_type="stock_journal", source_id=eid,
                    label=tc.CONN["stock_journal"]["label"])

    def _new(self, kind):
        from ui import txn_connector as tc
        tc.new_txn(self.frame, "stock_journal", self._load, kind=kind)

    def _edit(self):
        eid = self._sel()
        if not eid:
            return
        from ui import txn_connector as tc
        if not tc.can("stock_journal", "edit"):
            StockJournalForm(self.frame, entry_id=eid, view_only=True)
            return
        tc.edit_txn(self.frame, self._txn(eid), self._load)

    def _delete(self):
        eid = self._sel()
        if not eid:
            return
        from ui import txn_connector as tc
        if tc.delete_txn(self.frame, self._txn(eid), self._load):
            self._load()


class StockJournalForm:
    def __init__(self, parent, entry_id=None, kind="damage", on_save=None, view_only=False):
        C = self.C = cfg.theme()
        self.entry_id = entry_id
        self.on_save = on_save
        self.view_only = view_only
        self.kind = kind if kind in SJ.T else "damage"
        self.number = ""
        self.lines = []
        if entry_id:                       # the type of a saved entry is its own
            try:
                k = db.execute_scalar("SELECT entry_type FROM stock_journals WHERE entry_id=?",
                                      (int(entry_id),))
                if k in SJ.T:
                    self.kind = k
            except Exception:
                pass
        t = SJ.T[self.kind]
        self._load_products()
        w = self.win = tk.Toplevel(parent)
        w._is_dirty = self._is_dirty
        w.title(t["en"])
        w.geometry("1080x640")
        w.minsize(780, 460)
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass

        band = tk.Frame(w, bg=C["primary"])
        band.pack(fill="x")
        self.title_v = tk.StringVar(value="%s  New %s" % (t["icon"], t["en"]))
        tk.Label(band, textvariable=self.title_v, font=("Segoe UI", 11, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=12, pady=6)

        head = tk.Frame(w, bg=C["card_bg"])
        head.pack(fill="x", padx=10, pady=(8, 4))
        self.date_v = tk.StringVar(value=date.today().isoformat())
        self.reason_v = tk.StringVar(value=(SJ.REASONS.get(self.kind) or [""])[0])
        self.notes_v = tk.StringVar()

        def lbl(r, c, txt):
            tk.Label(head, text=txt, font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=c, sticky="w", padx=(8, 4), pady=3)
        st = "disabled" if view_only else "normal"
        lbl(0, 0, "Date")
        de = tk.Entry(head, textvariable=self.date_v, width=12, font=("Segoe UI", 10),
                      relief="solid", bd=1, state=st)
        de.grid(row=0, column=1, sticky="w")
        try:
            if not view_only:
                from ui.datefield import DateBox
                DateBox(de, self.date_v)
        except Exception:
            pass
        lbl(0, 2, "Reason")
        self.reason_cb = ttk.Combobox(head, textvariable=self.reason_v, width=32,
                                      values=SJ.REASONS.get(self.kind, []),
                                      state="disabled" if view_only else "normal")
        self.reason_cb.grid(row=0, column=3, sticky="w")
        self.reason_cb.bind("<<ComboboxSelected>>", lambda e: self._show_account())
        self.acc_v = tk.StringVar()
        tk.Label(head, textvariable=self.acc_v, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["primary"]).grid(row=0, column=4, sticky="w", padx=8)
        lbl(1, 0, "Notes")
        tk.Entry(head, textvariable=self.notes_v, width=70, font=("Segoe UI", 10),
                 relief="solid", bd=1, state=st).grid(row=1, column=1, columnspan=4, sticky="we")

        add = tk.Frame(w, bg=C["content_bg"])
        add.pack(fill="x", padx=10, pady=(2, 2))
        tk.Label(add, text="Item (scan / code / name)", font=("Segoe UI", 8, "bold"),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        self.item_v = tk.StringVar()
        self.item_cb = ttk.Combobox(add, textvariable=self.item_v, width=40,
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
        self.unit_cb = ttk.Combobox(add, textvariable=self.unit_cb_v, width=9,
                                    state="disabled" if view_only else "readonly")
        self.unit_cb.pack(side="left")
        tk.Label(add, text="Remark", font=("Segoe UI", 8, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(8, 2))
        self.rem_v = tk.StringVar()
        self.rem_e = tk.Entry(add, textvariable=self.rem_v, width=14, font=("Segoe UI", 10),
                              relief="solid", bd=1, state=st)
        self.rem_e.pack(side="left")
        self.add_btn = tk.Button(add, text="＋ Add  [Enter]", font=("Segoe UI", 9, "bold"),
                                 bg=C["primary"], fg="white", relief="flat", padx=10,
                                 cursor="hand2", command=self._add, state=st)
        self.add_btn.pack(side="left", padx=8)
        for wdg in (self.item_cb, self.qty_e, self.rem_e):
            wdg.bind("<Return>", lambda e: (self._add(), "break")[1])

        wrap = tk.Frame(w, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("n", "code", "name", "stock", "qty", "unit", "cost", "total", "remark")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, txt, wd, a in (("n", "#", 36, "center"), ("code", "Code", 90, "w"),
                              ("name", "Item", 260, "w"), ("stock", "Stock now", 80, "e"),
                              ("qty", "Qty", 70, "e"), ("unit", "Unit", 70, "center"),
                              ("cost", "Unit cost", 90, "e"), ("total", "Cost", 100, "e"),
                              ("remark", "Remark", 130, "w")):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=wd, anchor=a)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Delete>", lambda e: self._remove())

        foot = tk.Frame(w, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        foot.pack(fill="x", side="bottom")
        self.total_v = tk.StringVar(value="Cost 0.00")
        tk.Label(foot, textvariable=self.total_v, font=("Segoe UI", 13, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(side="left", padx=12, pady=6)
        how = ("Dr Inventory · Cr %s, at cost" if t["sign"] > 0
               else "Dr %s · Cr Inventory, at cost") % "the account above"
        tk.Label(foot, text=how + " · no VAT", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=6)
        tk.Button(foot, text="Esc  Close", font=("Segoe UI", 9), relief="flat", padx=10,
                  cursor="hand2", command=self._close).pack(side="right", padx=6, pady=6)
        tk.Button(foot, text="🖨 Print  [Ctrl+P]", font=("Segoe UI", 9), relief="flat", padx=10,
                  cursor="hand2", command=self._print).pack(side="right", padx=4)
        w.bind("<Control-p>", lambda e: (self._print(), "break")[1])
        if not view_only:
            tk.Button(foot, text="✔ Save  [Ctrl+S]", font=("Segoe UI", 9, "bold"),
                      bg=C.get("success", "#16A34A"), fg="white", relief="flat", padx=12,
                      cursor="hand2", command=lambda: self._save(confirm=True)).pack(
                          side="right", padx=4, pady=6)
            tk.Button(foot, text="Save draft  [Ctrl+D]", font=("Segoe UI", 9), relief="flat",
                      padx=10, cursor="hand2",
                      command=lambda: self._save(confirm=False)).pack(side="right", padx=4)
            tk.Button(foot, text="Remove [Del]", font=("Segoe UI", 9), relief="flat",
                      padx=10, cursor="hand2", command=self._remove).pack(side="left", padx=6)
            w.bind("<Control-s>", lambda e: (self._save(confirm=True), "break")[1])
            w.bind("<Control-S>", lambda e: (self._save(confirm=True), "break")[1])
            w.bind("<Control-d>", lambda e: (self._save(confirm=False), "break")[1])
        close_guard.bind_escape(w)
        if entry_id:
            self._load_entry()
        self._show_account()
        try:
            from ui import txn_connector as _tc
            _tc.attach(self, "stock_journal")
        except Exception:
            pass
        if not view_only:
            self.item_cb.focus_set()

    # ── data ──────────────────────────────────────────────────
    def _load_products(self):
        try:
            self.products = db.fetchall(
                "SELECT product_id, product_code, product_name_en, barcode, unit_of_measure_en "
                "FROM products WHERE ISNULL(is_active,1)=1 "
                "AND ISNULL(product_type,'product')<>'service' ORDER BY product_name_en") or []
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
        self.item_cb["values"] = [c for c in self._choices
                                  if all(x in c.lower() for x in q.split())][:60]

    def _product(self):
        txt = self.item_v.get().strip()
        if not txt:
            return None
        code = txt.split(" — ")[0].strip().lower()
        for p in self.products:                         # barcode / code typed or scanned
            if str(p.get("barcode") or "").lower() == txt.lower() or \
                    str(p.get("product_code") or "").lower() == code:
                return p
        try:                                            # unit / extra barcodes too
            from modules import product_lookup as PL
            hit = PL.search_products(txt, limit=2)
            if len(hit) == 1:
                pid = hit[0].get("product_id")
                for p in self.products:
                    if p["product_id"] == pid:
                        return p
        except Exception:
            pass
        hits = [p for p, c in zip(self.products, self._choices)
                if all(x in c.lower() for x in txt.lower().split())]
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
        rem = self.rem_v.get().strip()
        same = next((l for l in self.lines if l["product_id"] == p["product_id"]
                     and l["unit_of_measure_en"] == unit
                     and (l.get("remarks") or "") == rem), None)
        if same:
            same["quantity"] += qty
        else:
            self.lines.append({"product_id": p["product_id"], "product_code": p.get("product_code"),
                               "product_name_en": p.get("product_name_en"), "quantity": qty,
                               "unit_of_measure_en": unit, "remarks": rem,
                               "unit_cost": SJ.line_cost(p["product_id"], unit),
                               "stock": SJ.stock_of(p["product_id"], unit)})
        out = SJ.T[self.kind]["sign"] < 0
        ln = same or self.lines[-1]
        if out and ln["quantity"] > float(ln.get("stock") or 0) + 1e-9:
            messagebox.showinfo(SJ.T[self.kind]["en"],
                                "%s: only %g %s in stock — the stock will go below zero."
                                % (p.get("product_name_en"), float(ln.get("stock") or 0), unit),
                                parent=self.win)
        self.item_v.set("")
        self.qty_v.set("1")
        self.unit_cb_v.set("")
        self.rem_v.set("")
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
            st = l.get("stock")
            self.tree.insert("", "end", iid=str(i), values=(
                i + 1, l.get("product_code") or "", l.get("product_name_en") or "",
                ("%g" % float(st)) if st is not None else "", "%g" % float(l["quantity"]),
                l["unit_of_measure_en"], _money(l.get("unit_cost")), _money(t),
                l.get("remarks") or ""))
        self.total_v.set("Cost %s %s" % (_money(tot), _cur()))

    def _show_account(self):
        code = SJ.account_code_for(self.kind, self.reason_v.get())
        try:
            r = db.fetchone("SELECT account_code, account_name_en FROM accounts WHERE account_code=?",
                            (code,)) or {}
        except Exception:
            r = {}
        side = "Cr" if SJ.T[self.kind]["sign"] > 0 else "Dr"
        self.acc_v.set("→ %s %s %s" % (side, r.get("account_code") or code,
                                       r.get("account_name_en") or ""))

    def _load_entry(self):
        h, lines = SJ.get(self.entry_id)
        if not h:
            return
        self.number = h.get("entry_number") or ""
        self.date_v.set(str(h.get("entry_date") or "")[:10])
        self.reason_v.set(h.get("reason") or "")
        self.notes_v.set(h.get("notes") or "")
        self.lines = [{"product_id": l["product_id"], "product_code": l.get("product_code"),
                       "product_name_en": l.get("product_name_en"),
                       "quantity": float(l.get("quantity") or 0),
                       "unit_of_measure_en": l.get("unit_of_measure_en") or "PCs",
                       "unit_cost": float(l.get("unit_cost") or 0),
                       "remarks": l.get("remarks") or "",
                       "stock": SJ.stock_of(l["product_id"], l.get("unit_of_measure_en") or "")}
                      for l in lines]
        t = SJ.T[self.kind]
        self.title_v.set("%s  %s  %s  (%s)" % (t["icon"], t["en"], self.number,
                                                (h.get("entry_status") or "").title()))
        self._render()
        self._mark_clean()

    # ── save / print / close ──────────────────────────────────
    def _save(self, confirm=True):
        if self.view_only:
            return False
        action = "edit" if self.entry_id else "add"
        if not perm.allowed("stock_journal", action, parent=self.win):
            return False
        if self.entry_id and not confirm:       # a confirmed entry stays confirmed
            from modules import doc_edit
            confirm = doc_edit.info("stock_journal", self.entry_id)[1] == "confirmed"
        t = SJ.T[self.kind]
        if not self.lines:
            messagebox.showwarning(t["en"], "Add at least one item.", parent=self.win)
            return False
        u = perm.session_user() or {}
        try:
            eid, number, warn = SJ.save(
                {"entry_type": self.kind, "entry_date": self.date_v.get(),
                 "reason": self.reason_v.get(), "notes": self.notes_v.get(),
                 "entry_status": "confirmed" if confirm else "draft",
                 "_edit": bool(self.entry_id)},
                self.lines, entry_id=self.entry_id, user_id=u.get("user_id"))
        except Exception as e:
            messagebox.showerror(t["en"], str(e)[:300], parent=self.win)
            return False
        was = self.entry_id
        self.entry_id = eid
        self.number = number
        self._mark_clean()
        __import__("ui.toast", fromlist=["x"]).info(t["en"], "%s saved%s." % (number, "" if confirm else
                                                      " as draft (no stock moved)")
                            + (("\n\n⚠ " + warn) if warn else ""), parent=self.win)
        if self.on_save:
            try:
                self.on_save()
            except Exception:
                pass
        from ui import after_save
        parent, cb, kind = self.win.master, self.on_save, self.kind
        after_save.finish(self, number,
                          new=lambda: StockJournalForm(parent, kind=kind, on_save=cb),
                          keep=lambda: StockJournalForm(parent, entry_id=eid, on_save=cb),
                          edited=bool(was))
        return True

    def _print(self):
        if not self.lines:
            return
        t = SJ.T[self.kind]
        try:
            company = db.fetchone("SELECT TOP 1 * FROM company ORDER BY company_id") or {}
        except Exception:
            company = {}
        total = sum(round(float(l.get("unit_cost") or 0) * float(l["quantity"]), 2)
                    for l in self.lines)
        number = self.number or "(not saved)"
        header = {"number": number, "date": self.date_v.get(),
                  "party_name": t["en"], "party_address": self.reason_v.get(),
                  "notes": self.notes_v.get(), "subtotal": total, "vat": 0, "total": total,
                  "extra": [("Account", self.acc_v.get().lstrip("→ "))]}
        lines = [{"product_code": l.get("product_code"),
                  "product_name_en": ("%s  (%s)" % (l.get("product_name_en"), l["remarks"])
                                      if l.get("remarks") else l.get("product_name_en")),
                  "quantity": l["quantity"], "unit_price": l.get("unit_cost") or 0,
                  "vat_amount": 0,
                  "line_total": round(float(l.get("unit_cost") or 0) * float(l["quantity"]), 2)}
                 for l in self.lines]
        doc = "stock_" + self.kind
        path = os.path.join(tempfile.gettempdir(), "%s_%s.pdf" % (
            doc, (self.number or "draft").replace("/", "-")))
        try:
            from modules.generic_doc_pdf import generate_generic_pdf
            generate_generic_pdf(doc, header, company, lines, path, party_label="Stock journal")
        except Exception as e:
            messagebox.showerror("Print", str(e)[:200], parent=self.win)
            return
        try:
            from ui import print_menu
            print_menu.send_pdf(self.win, path, "%s %s" % (t["en"], number), doc)
        except Exception:
            try:
                os.startfile(path)
            except Exception as e:
                messagebox.showinfo("Print", "Saved: %s\n%s" % (path, e), parent=self.win)

    def _close(self):
        close_guard.request_close(self.win)

    def _mark_clean(self):
        self._clean_sig = close_guard.lines_sig(self.lines)

    def _is_dirty(self):
        if self.view_only or not self.lines:
            return False
        if not self.entry_id:
            return True
        return close_guard.lines_sig(self.lines) != getattr(self, "_clean_sig", None)


def open_on(kind):
    """Menus: show the Stock Journal list on one type."""
    v = getattr(StockJournalView, "_live", None)
    try:
        if v is not None and v.frame.winfo_exists():
            v.show(kind)
            return True
    except Exception:
        pass
    StockJournalView.start_kind = kind
    return False
