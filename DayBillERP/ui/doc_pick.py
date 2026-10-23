# ============================================================
# DayBill ERP - pick a document, then pick its lines (v7.5)
# ------------------------------------------------------------
#   DocPicker   — the bills / orders to load (search by number or party)
#   LinePicker  — its lines: ✓ which ones, how many (never more than is
#                 left), search an item, ✓ All / None
# Used by Sales / Purchase Return (load the bill) and Sales / Purchase
# Invoice (load a quotation, sales order or purchase order).
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox

from config import settings as cfg
from modules import doc_links as DL


def _n(v):
    s = "%.3f" % float(v or 0)
    return s.rstrip("0").rstrip(".") if "." in s else s


class DocPicker:
    """kinds: ['sales_invoice'] / ['quotation', 'sales_order'] / ['purchase_order'] …"""

    def __init__(self, parent, kinds, party_id=None, search="", title=None, modal=True):
        C = self.C = cfg.theme()
        self.kinds = list(kinds)
        self.party_id = party_id
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title(title or "Pick " + " / ".join(DL.KINDS[k]["title"] for k in self.kinds))
        self.win.configure(bg=C["content_bg"])
        self.win.geometry("760x480")
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        top = tk.Frame(self.win, bg=C["content_bg"]); top.pack(fill="x", padx=10, pady=8)
        self.kind_var = tk.StringVar(value=self.kinds[0])
        if len(self.kinds) > 1:
            for k in self.kinds:
                tk.Radiobutton(top, text=DL.KINDS[k]["title"], variable=self.kind_var, value=k,
                               indicatoron=False, padx=10, pady=3, bg=C["card_bg"],
                               selectcolor=C.get("primary_light", "#DBEAFE"),
                               command=self.load).pack(side="left", padx=(0, 4))
        tk.Label(top, text="🔍", bg=C["content_bg"]).pack(side="left", padx=(8, 2))
        self.q = tk.StringVar(value=search or "")
        e = tk.Entry(top, textvariable=self.q, font=("Segoe UI", 10), relief="solid", bd=1, width=26)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<KeyRelease>", lambda ev: self.load() if ev.keysym not in ("Down", "Up", "Return") else None)
        e.bind("<Down>", lambda ev: (self._first(), "break")[1])
        e.bind("<Return>", lambda ev: (self.pick(), "break")[1])
        self.only_party = tk.BooleanVar(value=bool(party_id))
        if party_id:
            tk.Checkbutton(top, text="This party only", variable=self.only_party, bg=C["content_bg"],
                           command=self.load).pack(side="left", padx=6)
        self.tv = ttk.Treeview(self.win, columns=("number", "date", "party", "total", "status"),
                               show="headings", height=14)
        for c, t, w, a in (("number", "Number", 150, "w"), ("date", "Date", 100, "center"),
                           ("party", "Party", 260, "w"), ("total", "Total", 110, "e"),
                           ("status", "Status", 90, "center")):
            self.tv.heading(c, text=t); self.tv.column(c, width=w, anchor=a)
        self.tv.pack(fill="both", expand=True, padx=10)
        self.tv.bind("<Double-1>", lambda e: self.pick())
        self.tv.bind("<Return>", lambda e: (self.pick(), "break")[1])
        bot = tk.Frame(self.win, bg=C["content_bg"]); bot.pack(fill="x", padx=10, pady=8)
        self.info = tk.StringVar()
        tk.Label(bot, textvariable=self.info, bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        tk.Button(bot, text="Cancel", relief="flat", padx=12, command=self.win.destroy).pack(side="right")
        tk.Button(bot, text="✔ Load", relief="flat", padx=14, bg=C["primary"], fg="white",
                  font=("Segoe UI", 9, "bold"), command=self.pick).pack(side="right", padx=6)
        self.rows = []
        self.load()
        e.focus_set()
        if modal:
            self.win.grab_set()
            parent.wait_window(self.win)

    def load(self):
        kind = self.kind_var.get()
        self.rows = DL.docs(kind, self.q.get().strip(),
                            self.party_id if self.only_party.get() else None)
        self.tv.delete(*self.tv.get_children())
        for r in self.rows:
            self.tv.insert("", "end", iid=str(r["id"]), values=(
                r["number"], r["date"], r["party"], "{:,.2f}".format(r["total"]), r["status"]))
        self.info.set("%d %s" % (len(self.rows), DL.KINDS[kind]["title"].lower() + "(s)"))
        if self.rows:
            self.tv.selection_set(str(self.rows[0]["id"]))

    def _first(self):
        kids = self.tv.get_children()
        if kids:
            self.tv.focus_set(); self.tv.selection_set(kids[0]); self.tv.focus(kids[0])

    def pick(self):
        s = self.tv.selection()
        if not s:
            return
        self.result = (self.kind_var.get(), int(s[0]))
        self.win.destroy()


class LinePicker:
    """lines carry _sold / _done / _left (doc_links). result = the lines
    with _pick = the quantity chosen (only picked ones)."""

    def __init__(self, parent, lines, title="Pick the items", done_label="Returned", modal=True,
                 sold_label="Sold"):
        C = self.C = cfg.theme()
        self.lines = [dict(l) for l in lines]
        for l in self.lines:
            l["_pick"] = 0.0
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.configure(bg=C["content_bg"])
        self.win.geometry("860x520")
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        top = tk.Frame(self.win, bg=C["content_bg"]); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text=title, font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        tk.Button(top, text="✓ All (what is left)", relief="flat", bg=C["card_bg"],
                  command=self.all).pack(side="right")
        tk.Button(top, text="✕ None", relief="flat", bg=C["card_bg"], command=self.none).pack(side="right", padx=4)
        sf = tk.Frame(self.win, bg=C["content_bg"]); sf.pack(fill="x", padx=10)
        tk.Label(sf, text="🔍 Find item", bg=C["content_bg"]).pack(side="left")
        self.q = tk.StringVar()
        qe = tk.Entry(sf, textvariable=self.q, relief="solid", bd=1, font=("Segoe UI", 10))
        qe.pack(side="left", fill="x", expand=True, padx=6)
        qe.bind("<KeyRelease>", lambda e: self.paint())
        cols = ("pick", "product", "unit", "sold", "done", "left", "qty")
        self.tv = ttk.Treeview(self.win, columns=cols, show="headings", height=14)
        for c, t, w, a in (("pick", "✓", 34, "center"), ("product", "Product", 320, "w"),
                           ("unit", "Unit", 80, "w"), ("sold", sold_label, 80, "e"),
                           ("done", done_label, 90, "e"), ("left", "Left", 80, "e"),
                           ("qty", "Qty to take", 100, "e")):
            self.tv.heading(c, text=t); self.tv.column(c, width=w, anchor=a)
        self.tv.pack(fill="both", expand=True, padx=10, pady=6)
        self.tv.tag_configure("on", background="#DCFCE7")
        self.tv.tag_configure("none", foreground="#9CA3AF")
        self.tv.bind("<Double-1>", self._dbl)
        self.tv.bind("<space>", lambda e: (self.toggle(), "break")[1])
        self.tv.bind("<Return>", lambda e: (self.edit_qty(), "break")[1])
        bot = tk.Frame(self.win, bg=C["content_bg"]); bot.pack(fill="x", padx=10, pady=8)
        self.info = tk.StringVar()
        tk.Label(bot, textvariable=self.info, bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        tk.Button(bot, text="Cancel", relief="flat", padx=12, command=self.win.destroy).pack(side="right")
        tk.Button(bot, text="✔ Load picked items", relief="flat", padx=14, bg=C["primary"], fg="white",
                  font=("Segoe UI", 9, "bold"), command=self.ok).pack(side="right", padx=6)
        tk.Label(self.win, text="Space = pick / unpick · double-click Qty or Enter = change it · "
                                "quantities never go above what is left", font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=12)
        self.paint()
        qe.focus_set()
        if modal:
            self.win.grab_set()
            parent.wait_window(self.win)

    def _shown(self):
        q = self.q.get().strip().lower()
        return [i for i, l in enumerate(self.lines)
                if not q or q in ("%s %s %s" % (l.get("product_code") or "", l.get("product_name_en") or "",
                                                l.get("product_name_ar") or "")).lower()]

    def paint(self):
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        for i in self._shown():
            l = self.lines[i]
            tags = ("on",) if l["_pick"] > 0 else (("none",) if l["_left"] <= 0 else ())
            self.tv.insert("", "end", iid=str(i), tags=tags, values=(
                "✓" if l["_pick"] > 0 else "", "%s  %s" % (l.get("product_code") or "", l.get("product_name_en") or ""),
                l.get("unit_of_measure_en") or "", _n(l["_sold"]), _n(l["_done"]), _n(l["_left"]),
                _n(l["_pick"]) if l["_pick"] else ""))
        for s in sel:
            if self.tv.exists(s):
                self.tv.selection_set(s)
        n = sum(1 for l in self.lines if l["_pick"] > 0)
        self.info.set("%d of %d line(s) picked" % (n, len(self.lines)))

    def _idx(self):
        s = self.tv.selection() or ((self.tv.focus(),) if self.tv.focus() else ())
        return int(s[0]) if s else None

    def set_qty(self, i, q):
        l = self.lines[i]
        try:
            q = float(q)
        except (TypeError, ValueError):
            return False
        l["_pick"] = round(max(0.0, min(q, l["_left"])), 4)
        return True

    def toggle(self, i=None):
        i = self._idx() if i is None else i
        if i is None:
            return
        l = self.lines[i]
        self.set_qty(i, 0 if l["_pick"] > 0 else l["_left"])
        self.paint()

    def all(self):
        for i in range(len(self.lines)):
            self.set_qty(i, self.lines[i]["_left"])
        self.paint()

    def none(self):
        for l in self.lines:
            l["_pick"] = 0.0
        self.paint()

    def _dbl(self, e):
        if self.tv.identify_column(e.x) == "#7":
            self.edit_qty()
        else:
            self.toggle()

    def edit_qty(self, i=None):
        i = self._idx() if i is None else i
        if i is None:
            return
        bbox = self.tv.bbox(str(i), "qty")
        if not bbox:
            return
        x, y, w, h = bbox
        var = tk.StringVar(value=_n(self.lines[i]["_pick"] or self.lines[i]["_left"]))
        ent = tk.Entry(self.tv, textvariable=var, justify="right")
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set(); ent.select_range(0, "end")

        def done(_e=None):
            if self.set_qty(i, var.get()) and float(var.get() or 0) > self.lines[i]["_left"] + 1e-9:
                self.info.set("⚠ Only %s left on this line — set to %s." % (_n(self.lines[i]["_left"]),
                                                                          _n(self.lines[i]["_left"])))
            ent.destroy(); self.paint(); self.tv.focus_set()
        ent.bind("<Return>", done)
        ent.bind("<KP_Enter>", done)
        ent.bind("<FocusOut>", done)
        ent.bind("<Escape>", lambda e: (ent.destroy(), "break")[1])

    def ok(self):
        picked = [l for l in self.lines if l["_pick"] > 0]
        if not picked:
            messagebox.showinfo("Pick", "Pick at least one item (Space, or ✓ All).", parent=self.win)
            return
        self.result = picked
        self.win.destroy()
