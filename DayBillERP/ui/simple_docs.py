# ============================================================
# DayBill ERP - Packing Slip / Delivery Note and Item Load Request
# screens (v7.12.0)
#   SimpleDocView(parent, kind)   the list: status tabs, period, totals
#   SimpleDocForm(parent, kind)   one document: items + quantities,
#                                 (packing slip) 📂 load a Sales Invoice /
#                                 Sales Order by its number
# No stock moves, no accounts — the invoice does that.
# Keys: Enter adds the item · Delete removes the line · double-click a
#       line = the packed / loaded quantity · Ctrl+S save · Ctrl+P print ·
#       Esc close
# ============================================================
import os
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date

from config import settings as cfg
from config.database import db
from modules import simple_docs as SD
from modules import masters as M
from modules import permissions as perm
from ui import close_guard

NONE = "— None —"


class SimpleDocView:
    def __init__(self, parent, kind="packing_slip"):
        C = self.C = cfg.theme()
        self.kind = kind
        k = SD.KINDS[kind]
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        # v7.17.1: the window title already names the page — buttons only here
        # (a long heading pushed ＋ New out of a smaller window)
        for txt, cmd, primary in (("🗑  Delete", self._delete, False),
                                  ("✔  %s" % k["done_word"], self._done, False),
                                  ("✏  Edit", self._edit, False),
                                  ("＋  New", self._new, True)):
            tk.Button(top, text=txt, font=("Segoe UI", 9, "bold"),
                      bg=C["primary"] if primary else C["card_bg"],
                      fg="white" if primary else C["text_primary"], relief="flat", padx=12,
                      pady=5, cursor="hand2", command=cmd).pack(side="right", padx=(6, 0))
        tk.Label(top, text=("No stock moves, no accounts — the invoice does that"
                            if kind == "packing_slip" else "Request only — no stock moves"),
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"]).pack(
                     side="left")
        tabs = tk.Frame(self.frame, bg=C["content_bg"])
        tabs.pack(fill="x", padx=20, pady=(4, 2))
        self.tab_btns = {}
        self.status = "open"
        for st, lbl in [("open", None), ("done", None), ("cancelled", None), ("", "All")]:
            b = tk.Button(tabs, text=lbl or SD.status_label(kind, st), font=("Segoe UI", 9, "bold"),
                          relief="flat", padx=12, pady=4, cursor="hand2",
                          command=lambda s=st: self.show(s))
            b.pack(side="left", padx=(0, 4))
            self.tab_btns[st] = b
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=20, pady=(4, 6))
        today = date.today()
        self.from_v = tk.StringVar(value=today.replace(day=1).isoformat())
        self.to_v = tk.StringVar(value=today.isoformat())
        for lbl, var in (("From", self.from_v), ("To", self.to_v)):
            tk.Label(bar, text=lbl, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            e = tk.Entry(bar, textvariable=var, width=11, font=("Segoe UI", 10), relief="solid", bd=1)
            e.pack(side="left", padx=(0, 10))
            try:
                from ui.datefield import DateBox
                DateBox(e, var)
            except Exception:
                pass
        tk.Button(bar, text="🔍 Show", font=("Segoe UI", 9, "bold"), bg=C["card_bg"], relief="flat",
                  padx=10, cursor="hand2", command=self._load).pack(side="left")
        self.sum_v = tk.StringVar()
        tk.Label(bar, textvariable=self.sum_v, font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="right")
        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        if kind == "packing_slip":
            cols = [("no", "Number", 150, "w"), ("date", "Date", 90, "center"),
                    ("party", "Customer", 210, "w"), ("src", "From invoice / order", 150, "w"),
                    ("veh", "Vehicle", 120, "w"), ("pk", "Packages", 70, "e"),
                    ("items", "Items", 60, "e"), ("qty", "Qty", 70, "e"),
                    ("st", "Status", 90, "center")]
        else:
            cols = [("no", "Number", 150, "w"), ("date", "Date", 90, "center"),
                    ("party", "Salesman", 170, "w"), ("route", "Route", 140, "w"),
                    ("veh", "Vehicle", 120, "w"), ("need", "Needed by", 90, "center"),
                    ("items", "Items", 60, "e"), ("qty", "Qty", 70, "e"),
                    ("st", "Status", 90, "center")]
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for c, t, w, a in cols:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.tree.bind("<Return>", lambda e: self._edit())
        self.tree.bind("<Delete>", lambda e: self._delete())
        self.frame.new_record = self._new
        if not SD.ready():
            self.sum_v.set("⚠ needs the v7.12 database update (it runs when DayBill starts)")
        self.show("open")

    def show(self, status):
        self.status = status
        C = self.C
        for st, b in self.tab_btns.items():
            on = st == status
            b.configure(bg=C["primary"] if on else C["card_bg"],
                        fg="white" if on else C["text_primary"])
        self._load()

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        rows = SD.docs(self.kind, self.from_v.get(), self.to_v.get(), self.status or None)
        tq = 0.0
        for r in rows:
            tq += float(r.get("qty") or 0)
            st = SD.status_label(self.kind, r.get("doc_status"))
            veh = M.label_of("vehicles", r.get("vehicle_id")) if r.get("vehicle_id") else ""
            if self.kind == "packing_slip":
                src = r.get("source_number") or "— not invoiced —"
                vals = (r["doc_number"], str(r.get("doc_date") or "")[:10], r.get("party_name") or "",
                        src, veh, r.get("packages") or "", r.get("items") or 0,
                        "%g" % float(r.get("qty") or 0), st)
            else:
                vals = (r["doc_number"], str(r.get("doc_date") or "")[:10],
                        M.label_of("salesmen", r.get("salesman_id")),
                        M.label_of("routes", r.get("route_id")) if r.get("route_id") else "", veh,
                        str(r.get("needed_date") or "")[:10], r.get("items") or 0,
                        "%g" % float(r.get("qty") or 0), st)
            self.tree.insert("", "end", iid=str(r["doc_id"]), values=vals)
        self.sum_v.set("%d document(s) · %g items' qty" % (len(rows), tq))

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _new(self):
        if perm.allowed(SD.KINDS[self.kind]["rights"], "add", parent=self.frame):
            SimpleDocForm(self.frame, self.kind, on_save=self._load)

    def _edit(self):
        did = self._sel()
        if did:
            ro = not perm.can(SD.KINDS[self.kind]["rights"], "edit")
            SimpleDocForm(self.frame, self.kind, doc_id=did, on_save=self._load, view_only=ro)

    def _done(self):
        did = self._sel()
        if not did or not perm.allowed(SD.KINDS[self.kind]["rights"], "edit", parent=self.frame):
            return
        SD.set_status(did, "done")
        self._load()

    def _delete(self):
        did = self._sel()
        if not did or not perm.allowed(SD.KINDS[self.kind]["rights"], "delete", parent=self.frame):
            return
        num = self.tree.set(str(did), "no")
        if messagebox.askyesno(SD.KINDS[self.kind]["short"], "Delete %s?" % num, parent=self.frame):
            SD.delete(did)
            self._load()


class SimpleDocForm:
    def __init__(self, parent, kind="packing_slip", doc_id=None, on_save=None, view_only=False):
        C = self.C = cfg.theme()
        self.kind = kind
        self.k = k = SD.KINDS[kind]
        self.doc_id = doc_id
        self.on_save = on_save
        self.view_only = view_only
        self.number = ""
        self.lines = []
        self.source = (None, None, None)          # (kind, id, number)
        self._load_lookups()
        w = self.win = tk.Toplevel(parent)
        w._is_dirty = self._is_dirty
        w.title(k["title"])
        w.geometry("1000x640")
        w.minsize(800, 480)
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass
        acc = k.get("accent") or C["primary"]
        band = tk.Frame(w, bg=acc)
        band.pack(fill="x")
        self.title_v = tk.StringVar(value="%s  New %s" % (k["icon"], k["short"]))
        tk.Label(band, textvariable=self.title_v, font=("Segoe UI", 11, "bold"), bg=acc,
                 fg="white").pack(side="left", padx=12, pady=6)
        tk.Label(band, text="No stock · no accounts" if kind == "packing_slip"
                 else "Request only — stock moves with the Stock Transfer / Van sale",
                 font=("Segoe UI", 8), bg=acc, fg="#E0F2F1").pack(side="right", padx=12)
        st = "disabled" if view_only else "normal"
        ro = "disabled" if view_only else "readonly"
        head = tk.Frame(w, bg=C["card_bg"])
        head.pack(fill="x", padx=10, pady=(8, 4))
        self.v = {x: tk.StringVar() for x in ("date", "party", "salesman", "vehicle", "route",
                                              "driver", "source", "packages", "needed", "status",
                                              "notes")}
        self.v["date"].set(date.today().isoformat())
        self.v["status"].set(SD.status_label(kind, "open"))
        for x in ("salesman", "vehicle", "route"):
            self.v[x].set(NONE)

        def cell(r, c, label, widget, span=1):
            tk.Label(head, text=label, font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=c, sticky="w", padx=(8, 4), pady=3)
            widget.grid(row=r, column=c + 1, columnspan=span, sticky="w", pady=3)

        def entry(var, width):
            e = tk.Entry(head, textvariable=var, width=width, font=("Segoe UI", 10), relief="solid",
                         bd=1, state=st)
            e._fixed_width = True
            return e

        de = entry(self.v["date"], 12)
        cell(0, 0, "Date", de)
        try:
            if not view_only:
                from ui.datefield import DateBox
                DateBox(de, self.v["date"])
        except Exception:
            pass
        if kind == "packing_slip":
            self.party_cb = ttk.Combobox(head, textvariable=self.v["party"], width=34,
                                         values=[c["label"] for c in self.customers], state=st)
            cell(0, 2, "Customer *", self.party_cb)
            src = tk.Frame(head, bg=C["card_bg"])
            tk.Entry(src, textvariable=self.v["source"], width=16, font=("Segoe UI", 10),
                     relief="solid", bd=1, state=st).pack(side="left")
            if not view_only:
                tk.Button(src, text="📂 Load", font=("Segoe UI", 8, "bold"), bg=C["primary"],
                          fg="white", relief="flat", padx=8, cursor="hand2",
                          command=self._load_source).pack(side="left", padx=(4, 0))
            cell(0, 4, "Invoice / order #", src)
            cell(1, 0, "Packages", entry(self.v["packages"], 6))
            cell(1, 2, "Driver", entry(self.v["driver"], 20))
        else:
            cell(0, 2, "Salesman *", ttk.Combobox(head, textvariable=self.v["salesman"], width=26,
                                                 values=[NONE] + list(self.salesmen), state=ro))
            cell(0, 4, "Route", ttk.Combobox(head, textvariable=self.v["route"], width=20,
                                             values=[NONE] + list(self.routes), state=ro))
            ne = entry(self.v["needed"], 12)
            cell(1, 0, "Needed by", ne)
            try:
                if not view_only:
                    from ui.datefield import DateBox
                    DateBox(ne, self.v["needed"])
            except Exception:
                pass
            cell(1, 2, "Driver", entry(self.v["driver"], 20))
        cell(1, 4, "Vehicle", ttk.Combobox(head, textvariable=self.v["vehicle"], width=20,
                                           values=[NONE] + list(self.vehicles), state=ro))
        cell(2, 0, "Status", ttk.Combobox(head, textvariable=self.v["status"], width=12, state=ro,
                                          values=[l for _s, l in k["statuses"]]))
        cell(2, 2, "Notes", entry(self.v["notes"], 60), span=3)

        add = tk.Frame(w, bg=C["content_bg"])
        add.pack(fill="x", padx=10, pady=(2, 2))
        tk.Button(add, text="＋ Add  [Enter]", font=("Segoe UI", 9, "bold"), bg=acc,
                  fg="white", relief="flat", padx=10, cursor="hand2", command=self._add,
                  state=st).pack(side="right", padx=(8, 0))
        tk.Label(add, text="Item (scan / code / name)", font=("Segoe UI", 8, "bold"),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        self.item_v = tk.StringVar()
        self.item_cb = ttk.Combobox(add, textvariable=self.item_v, width=34, values=self._choices,
                                    state=st)
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
        self.unit_v = tk.StringVar()
        self.unit_cb = ttk.Combobox(add, textvariable=self.unit_v, width=9, state=ro)
        self.unit_cb.pack(side="left")
        tk.Label(add, text="Remark", font=("Segoe UI", 8, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(8, 2))
        self.rem_v = tk.StringVar()
        self.rem_e = tk.Entry(add, textvariable=self.rem_v, width=14, font=("Segoe UI", 10),
                              relief="solid", bd=1, state=st)
        self.rem_e.pack(side="left")
        for wdg in (self.item_cb, self.qty_e, self.rem_e):
            wdg.bind("<Return>", lambda e: (self._add(), "break")[1])

        wrap = tk.Frame(w, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=4)
        cols = (("n", "#", 36, "center"), ("code", "Code", 100, "w"), ("name", "Item", 330, "w"),
                ("qty", "Qty", 80, "e"), ("unit", "Unit", 80, "center"),
                ("done", k["done_qty"], 80, "e"), ("rem", "Remark", 180, "w"))
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for c, t, wd, a in cols:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=wd, anchor=a)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Delete>", lambda e: self._remove())
        self.tree.bind("<Double-1>", lambda e: self._set_done())

        foot = tk.Frame(w, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        foot.pack(fill="x", side="bottom")
        self.total_v = tk.StringVar(value="0 items")
        tk.Label(foot, textvariable=self.total_v, font=("Segoe UI", 13, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(side="left", padx=12, pady=6)
        hint = tk.Label(foot, text="No stock moves · double-click a line = %s qty"
                        % k["done_qty"].lower(), font=("Segoe UI", 8), bg=C["card_bg"],
                        fg=C["text_secondary"])
        tk.Button(foot, text="Esc  Close", font=("Segoe UI", 9), relief="flat", padx=10,
                  cursor="hand2", command=lambda: close_guard.request_close(self.win)).pack(
                      side="right", padx=6, pady=6)
        tk.Button(foot, text="🖨 Print  [Ctrl+P]", font=("Segoe UI", 9), relief="flat", padx=10,
                  cursor="hand2", command=self._print).pack(side="right", padx=4)
        w.bind("<Control-p>", lambda e: (self._print(), "break")[1])
        if not view_only:
            tk.Button(foot, text="✔ Save  [Ctrl+S]", font=("Segoe UI", 9, "bold"),
                      bg=C.get("success", "#16A34A"), fg="white", relief="flat", padx=12,
                      cursor="hand2", command=self._save).pack(side="right", padx=4, pady=6)
            tk.Button(foot, text="Remove  [Del]", font=("Segoe UI", 9), relief="flat", padx=8,
                      cursor="hand2", command=self._remove).pack(side="left", padx=4)
            if kind == "packing_slip":              # v7.13
                tk.Button(foot, text="🧾 Invoice", font=("Segoe UI", 9, "bold"),
                          bg=acc, fg="white", relief="flat", padx=12, cursor="hand2",
                          command=self._make_invoice).pack(side="right", padx=4, pady=6)
            else:
                tk.Button(foot, text="✔ All loaded", font=("Segoe UI", 9, "bold"),
                          bg=acc, fg="white", relief="flat", padx=12, cursor="hand2",
                          command=self._all_loaded).pack(side="right", padx=4, pady=6)
            w.bind("<Control-s>", lambda e: (self._save(), "break")[1])
        hint.pack(side="left", padx=6)            # after the buttons: it gives way first
        close_guard.bind_escape(w)
        if doc_id:
            self._load_doc()
        if not view_only:
            self.item_cb.focus_set()

    # ── lookups ───────────────────────────────────────────────
    def _load_lookups(self):
        try:
            self.products = db.fetchall(
                "SELECT product_id, product_code, product_name_en, product_name_ar, barcode, "
                "unit_of_measure_en FROM products WHERE ISNULL(is_active,1)=1 "
                "ORDER BY product_name_en") or []
        except Exception:
            self.products = []
        self._choices = ["%s — %s" % (p.get("product_code") or "", p.get("product_name_en") or "")
                         for p in self.products]
        self.customers = []
        try:
            for r in db.fetchall("SELECT customer_id, customer_code, customer_name_en FROM customers "
                                 "WHERE ISNULL(is_active,1)=1 ORDER BY customer_name_en") or []:
                self.customers.append(dict(id=r["customer_id"], name=r["customer_name_en"],
                                           label="%s — %s" % (r["customer_code"], r["customer_name_en"])))
        except Exception:
            pass
        self.salesmen = {l: i for i, l in M.choices("salesmen")} if M.ready("salesmen") else {}
        self.routes = {l: i for i, l in M.choices("routes")} if M.ready("routes") else {}
        self.vehicles = {l: i for i, l in M.choices("vehicles")} if M.ready("vehicles") else {}

    def _keep(self, d, kind, rid):
        """A switched-off salesman / route / vehicle still shows on its document."""
        if rid and rid not in d.values():
            lbl = M.label_of(kind, rid)
            if lbl:
                d[lbl] = rid
        return next((l for l, i in d.items() if i == rid), NONE)

    def _filter(self, e=None):
        if e is not None and e.keysym in ("Return", "Up", "Down", "Escape", "Tab"):
            return
        q = self.item_v.get().strip().lower()
        self.item_cb["values"] = ([c for c in self._choices if all(x in c.lower() for x in q.split())][:60]
                                  if q else self._choices)

    def _product(self):
        txt = self.item_v.get().strip()
        if not txt:
            return None
        code = txt.split(" — ")[0].strip().lower()
        for p in self.products:
            if str(p.get("barcode") or "").lower() == txt.lower() or \
                    str(p.get("product_code") or "").lower() == code:
                return p
        try:
            from modules import product_lookup as PL
            hit = PL.search_products(txt, limit=2)
            if len(hit) == 1:
                return next((p for p in self.products if p["product_id"] == hit[0].get("product_id")),
                            None)
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
            self.unit_v.set(u[0])
            self.qty_e.focus_set()
            self.qty_e.select_range(0, "end")

    # ── lines ─────────────────────────────────────────────────
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
        unit = self.unit_v.get() or (p.get("unit_of_measure_en") or "PCs")
        rem = self.rem_v.get().strip()
        same = next((l for l in self.lines if l["product_id"] == p["product_id"]
                     and l["unit_of_measure_en"] == unit and (l.get("remarks") or "") == rem), None)
        if same:
            same["quantity"] += qty
            if self.kind == "packing_slip":
                same["done_qty"] = float(same.get("done_qty") or 0) + qty
        else:
            self.lines.append(dict(product_id=p["product_id"], product_code=p.get("product_code"),
                                   product_name_en=p.get("product_name_en"),
                                   product_name_ar=p.get("product_name_ar"), quantity=qty,
                                   unit_of_measure_en=unit,
                                   done_qty=qty if self.kind == "packing_slip" else 0.0,
                                   remarks=rem))
        for v, d in ((self.item_v, ""), (self.qty_v, "1"), (self.unit_v, ""), (self.rem_v, "")):
            v.set(d)
        self.item_cb["values"] = self._choices
        self._render()
        self.item_cb.focus_set()

    def _remove(self):
        if self.view_only:
            return
        drop = {int(i) for i in self.tree.selection()}
        self.lines = [l for i, l in enumerate(self.lines) if i not in drop]
        self._render()

    def _set_done(self):
        if self.view_only:
            return
        sel = self.tree.selection()
        if not sel:
            return
        ln = self.lines[int(sel[0])]
        v = simpledialog.askfloat(self.k["done_qty"], "%s quantity of %s (of %g):" % (
            self.k["done_qty"], ln.get("product_name_en"), ln["quantity"]),
            initialvalue=ln.get("done_qty") or ln["quantity"], minvalue=0, parent=self.win)
        if v is not None:
            ln["done_qty"] = float(v)
            self._render()

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        tq = td = 0.0
        for i, l in enumerate(self.lines):
            tq += float(l["quantity"])
            td += float(l.get("done_qty") or 0)
            self.tree.insert("", "end", iid=str(i), values=(
                i + 1, l.get("product_code") or "", l.get("product_name_en") or "",
                "%g" % float(l["quantity"]), l["unit_of_measure_en"],
                ("%g" % float(l["done_qty"])) if l.get("done_qty") else "", l.get("remarks") or ""))
        self.total_v.set("%d items · qty %g%s" % (len(self.lines), tq,
                                                  (" · %s %g" % (self.k["done_qty"].lower(), td))
                                                  if td else ""))

    def _load_source(self):
        kind, h, lines = SD.source_lines(self.v["source"].get())
        if not h:
            messagebox.showinfo(self.k["short"], "No Sales Invoice or Sales Order has number %s."
                                % self.v["source"].get(), parent=self.win)
            return
        num = h.get("invoice_number") or h.get("so_number")
        self.source = (kind, h.get("invoice_id") or h.get("so_id"), num)
        cid = h.get("customer_id")
        c = next((x for x in self.customers if x["id"] == cid), None)
        self.v["party"].set(c["label"] if c else (h.get("customer_name_en") or ""))
        self.lines = [dict(product_id=l["product_id"], product_code=l.get("product_code"),
                           product_name_en=l.get("product_name_en"),
                           product_name_ar=l.get("product_name_ar"),
                           quantity=float(l.get("quantity") or 0),
                           unit_of_measure_en=l.get("unit_of_measure_en") or "PCs",
                           done_qty=float(l.get("quantity") or 0), remarks="")
                      for l in lines if float(l.get("quantity") or 0) > 0]
        self._render()
        try:                                     # the customer's salesman / route
            links = M.customer_links(cid) if cid else {}
            if links.get("route_id"):
                self.v["route"].set(self._keep(self.routes, "routes", links["route_id"]))
        except Exception:
            pass

    def _load_doc(self):
        h, lines = SD.get(self.doc_id)
        if not h:
            return
        self.number = h["doc_number"]
        self.v["date"].set(str(h.get("doc_date") or "")[:10])
        c = next((x for x in self.customers if x["id"] == h.get("customer_id")), None)
        self.v["party"].set(c["label"] if c else (h.get("party_name") or ""))
        self.v["salesman"].set(self._keep(self.salesmen, "salesmen", h.get("salesman_id")))
        self.v["route"].set(self._keep(self.routes, "routes", h.get("route_id")))
        self.v["vehicle"].set(self._keep(self.vehicles, "vehicles", h.get("vehicle_id")))
        self.v["driver"].set(h.get("driver_name") or "")
        self.v["source"].set(h.get("source_number") or "")
        self.source = (h.get("source_kind"), h.get("source_id"), h.get("source_number"))
        self.v["packages"].set(str(h.get("packages") or ""))
        self.v["needed"].set(str(h.get("needed_date") or "")[:10])
        self.v["status"].set(SD.status_label(self.kind, h.get("doc_status")))
        self.v["notes"].set(h.get("notes") or "")
        self.lines = [dict(product_id=l["product_id"], product_code=l.get("product_code"),
                           product_name_en=l.get("product_name_en"),
                           product_name_ar=l.get("product_name_ar"),
                           quantity=float(l.get("quantity") or 0),
                           unit_of_measure_en=l.get("unit_of_measure_en") or "PCs",
                           done_qty=float(l.get("done_qty") or 0), remarks=l.get("remarks") or "")
                      for l in lines]
        self.title_v.set("%s  %s  %s" % (self.k["icon"], self.k["short"], self.number))
        self._render()
        self._clean = close_guard.lines_sig(self.lines)

    # ── save / print ──────────────────────────────────────────
    def _header(self):
        party = self.v["party"].get().strip()
        c = next((x for x in self.customers if x["label"] == party), None)
        src_kind, src_id, src_no = self.source
        typed = self.v["source"].get().strip()
        if typed != (src_no or ""):              # a number typed but not loaded
            src_kind, src_id, src_no = (None, None, typed or None)
        st = next((s for s, l in self.k["statuses"] if l == self.v["status"].get()), "open")
        return dict(doc_date=self.v["date"].get(), customer_id=c["id"] if c else None,
                    party_name=c["name"] if c else party,
                    salesman_id=self.salesmen.get(self.v["salesman"].get()),
                    route_id=self.routes.get(self.v["route"].get()),
                    vehicle_id=self.vehicles.get(self.v["vehicle"].get()),
                    driver_name=self.v["driver"].get(), source_kind=src_kind, source_id=src_id,
                    source_number=src_no, packages=self.v["packages"].get(),
                    needed_date=self.v["needed"].get(), doc_status=st,
                    notes=self.v["notes"].get(), _edit=bool(self.doc_id))

    def _save(self):
        if self.view_only:
            return False
        if not perm.allowed(self.k["rights"], "edit" if self.doc_id else "add", parent=self.win):
            return False
        u = perm.session_user() or {}
        try:
            did, number = SD.save(self.kind, self._header(), self.lines, self.doc_id,
                                  u.get("user_id"))
        except Exception as e:
            messagebox.showerror(self.k["short"], str(e)[:300], parent=self.win)
            return False
        self.doc_id, self.number = did, number
        self._clean = close_guard.lines_sig(self.lines)
        self.title_v.set("%s  %s  %s" % (self.k["icon"], self.k["short"], number))
        from ui import toast
        toast.show("%s saved." % number, "ok", 2600, self.win)
        if self.on_save:
            try:
                self.on_save()
            except Exception:
                pass
        return True

    def _print(self):
        if not self.doc_id:
            if self.view_only or not messagebox.askyesno(self.k["short"], "Save it first, then print?",
                                                         parent=self.win):
                return
            if not self._save():
                return
        path = os.path.join(tempfile.gettempdir(), "%s_%s.pdf" % (self.kind, self.number))
        try:
            SD.pdf(self.doc_id, path)
        except Exception as e:
            messagebox.showerror("Print", str(e)[:200], parent=self.win)
            return
        try:
            from ui import print_menu
            print_menu.send_pdf(self.win, path, "%s %s" % (self.k["short"], self.number), self.kind)
        except Exception:
            try:
                os.startfile(path)
            except Exception:
                messagebox.showinfo("Print", "Saved: %s" % path, parent=self.win)

    # ── v7.13: packing slip → Sales Invoice · load request all loaded ──
    def _make_invoice(self):
        src_kind, _sid, src_no = self.source
        if src_kind == "sales" and src_no:
            messagebox.showinfo(self.k["short"], "This delivery is already on invoice %s." % src_no,
                                parent=self.win)
            return
        if not self.lines:
            messagebox.showwarning(self.k["short"], "Add the items first.", parent=self.win)
            return
        if not perm.allowed("sales", "add", parent=self.win):
            return
        if (not self.doc_id or self._is_dirty()) and not self._save():
            return
        party = self.v["party"].get().strip()
        did = self.doc_id
        holder = {}

        def saved():
            f = holder.get("f")
            inv_id = getattr(f, "invoice_id", None)
            if not inv_id:
                return
            try:
                num = db.execute_scalar("SELECT invoice_number FROM sales_invoices WHERE invoice_id=?",
                                        (inv_id,))
            except Exception:
                num = None
            SD.link_invoice(did, inv_id, num)
            self.source = ("sales", inv_id, num)
            try:
                self.v["source"].set(num or "")
                self.v["status"].set(SD.status_label(self.kind, "done"))
            except Exception:
                pass
            if self.on_save:
                try:
                    self.on_save()
                except Exception:
                    pass
        try:
            from ui.invoices import InvoiceForm
            f = InvoiceForm(self.win.master, on_save=saved)
        except Exception as e:
            messagebox.showerror("Sales Invoice", str(e)[:300], parent=self.win)
            return
        holder["f"] = f
        try:
            if party and party in list(f.cust_combo["values"]):
                f.cust_var.set(party)
                f._on_customer_select()
        except Exception:
            pass
        qty = [(l["product_id"], float(l.get("done_qty") or l["quantity"])) for l in self.lines]
        try:
            n = f.line_grid.add_product_lines(qty)
        except Exception:
            n = 0
        if n < len(qty):
            messagebox.showinfo("Sales Invoice", "%d of %d items came on the invoice (the others "
                                "are not for sale or switched off)." % (n, len(qty)), parent=f.win)
        try:
            f.hdr_vars["notes_en"].set("Delivery note %s" % self.number)
        except Exception:
            pass

    def _all_loaded(self):
        for l in self.lines:
            l["done_qty"] = float(l["quantity"])
        self.v["status"].set(SD.status_label(self.kind, "done"))
        self._render()

    def _is_dirty(self):
        if self.view_only or not self.lines:
            return False
        return close_guard.lines_sig(self.lines) != getattr(self, "_clean", None)


class PackingSlipView(SimpleDocView):
    def __init__(self, parent):
        super().__init__(parent, "packing_slip")


class LoadRequestView(SimpleDocView):
    def __init__(self, parent):
        super().__init__(parent, "load_request")
