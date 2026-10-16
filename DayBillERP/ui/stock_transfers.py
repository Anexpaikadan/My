# ============================================================
# DayBill ERP - Stock per branch + transfers (Inventory)  v6.0
# ------------------------------------------------------------
# Tab 1 Transfer: pick the two branches, add products, Save → stock
#                 leaves one branch and arrives in the other.
# Tab 2 Stock by branch: every product's stock in each branch.
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from modules import stock_branch as SB
from ui import v6_kit as K


class StockTransfersView:
    def __init__(self, parent):
        self.page = K.Page(parent, "🔁  Stock Transfers & Branch Stock",
                           "Move goods from one branch to another and see the stock of every branch. "
                           "The company total does not change, so there is no journal; batches and "
                           "expiry dates move with the goods.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        if not SB.ready():
            self.page.say("⚠ Needs the v6.0 database update — Updates ▸ Apply All Updates.", ok=False)
            return
        self.brs = SB.branches()
        if len(self.brs) < 2:
            self.page.say("Only one branch: add another in Administration ▸ Branches & Counters "
                          "to move stock between branches.", ok=False)
        nb = ttk.Notebook(self.page.body)
        nb.pack(fill="both", expand=True)
        t1 = tk.Frame(nb, bg=C["content_bg"]); nb.add(t1, text="  Transfer  ")
        t2 = tk.Frame(nb, bg=C["content_bg"]); nb.add(t2, text="  Stock by branch  ")
        self.nb = nb
        self._transfer_tab(t1, C)
        self._stock_tab(t2, C)
        nb.bind("<<NotebookTabChanged>>", lambda e: self._load_stock() if nb.index("current") == 1 else None)
        self.load()

    def _names(self):
        return ["%s — %s" % (b["branch_id"], b.get("name_en") or "") for b in self.brs]

    @staticmethod
    def _bid(label):
        try:
            return int(str(label).split(" — ")[0])
        except (TypeError, ValueError):
            return None

    # ── transfer ───────────────────────────────────────────────
    def _transfer_tab(self, parent, C):
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)
        c = K.card(parent, C, "New transfer")
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=6)
        r1 = tk.Frame(c, bg=C["card_bg"]); r1.pack(fill="x", padx=10)
        self.from_v, self.to_v = tk.StringVar(), tk.StringVar()
        names = self._names()
        K.combo(r1, C, "From branch *", self.from_v, names, 22)
        K.combo(r1, C, "To branch *", self.to_v, names, 22)
        here = SB.here()
        if names:
            self.from_v.set(next((n for n in names if self._bid(n) == here), names[0]))
            self.to_v.set(next((n for n in names if self._bid(n) != self._bid(self.from_v.get())), names[0]))
        self.date_v = tk.StringVar(value=date.today().isoformat())
        K.date_entry(r1, C, "Date", self.date_v)
        self.lines_tree = K.tree(c, [("code", "Code", 90, "w"), ("name", "Product", 240, "w"),
                                     ("have", "In 'from' branch", 110, "e"), ("unit", "Unit", 80, "w"),
                                     ("qty", "Quantity", 90, "e")], height=9)
        r2 = tk.Frame(c, bg=C["card_bg"]); r2.pack(fill="x", padx=10)
        self.finder = K.ProductFinder(r2, C, self._picked)
        self.finder.pack(side="left", padx=(0, 10))
        self.unit_v, self.qty_v = tk.StringVar(), tk.StringVar(value="1")
        self.unit_cb = K.combo(r2, C, "Unit", self.unit_v, [], 10)
        e = K.entry(r2, C, "Quantity *", self.qty_v, 8, justify="right")
        e.bind("<Return>", lambda ev: self._add())
        r3 = tk.Frame(c, bg=C["card_bg"]); r3.pack(fill="x", padx=10, pady=(4, 0))
        K.button(r3, C, "＋ Add", self._add)
        K.button(r3, C, "✕ Remove line", self._remove)
        self.notes_v = tk.StringVar()
        r4 = tk.Frame(c, bg=C["card_bg"]); r4.pack(fill="x", padx=10, pady=(6, 10))
        K.entry(r4, C, "Notes", self.notes_v, 40)
        K.button(r4, C, "💾 Save transfer", self._save, primary=True).pack_configure(pady=(14, 0))
        self._lines = []

        l = K.card(parent, C, "Transfers")
        l.grid(row=0, column=1, sticky="nsew", pady=6)
        self.tree = K.tree(l, [("no", "No.", 110, "w"), ("date", "Date", 85, "center"),
                               ("from", "From", 110, "w"), ("to", "To", 110, "w"),
                               ("n", "Lines", 50, "e"), ("v", "Value", 90, "e")], height=14)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_detail())
        self.detail_v = tk.StringVar()
        tk.Label(l, textvariable=self.detail_v, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"], justify="left", anchor="w", wraplength=420).pack(fill="x", padx=12)
        r = tk.Frame(l, bg=C["card_bg"]); r.pack(fill="x", padx=10, pady=(4, 10))
        K.button(r, C, "🗑 Undo selected", self._delete, danger=True)
        K.button(r, C, "↻ Refresh", self.load)

    def _picked(self, row):
        try:
            from modules import barcode_resolver as BR
            units = [u.get("unit_name_en") for u in (BR.units_of(row["product_id"]) or []) if u.get("unit_name_en")]
        except Exception:
            units = []
        self.unit_cb["values"] = units or ["Unit"]
        self.unit_v.set((units or ["Unit"])[0])

    def _add(self):
        row = self.finder.picked
        q = K.num(self.qty_v)
        if not row or q is None or q <= 0:
            self.page.say("Pick a product and type a quantity above 0.", ok=False)
            return
        fb = self._bid(self.from_v.get())
        have = SB.branch_qty(row["product_id"], fb) if fb else 0
        self._lines.append({"product_id": row["product_id"], "code": row.get("product_code"),
                            "name": row.get("product_name_en"), "unit_name": self.unit_v.get(),
                            "quantity": q, "have": have})
        self.finder.clear()
        self.qty_v.set("1")
        self._show_lines()
        self.finder.entry.focus_set()

    def _remove(self):
        sel = self.lines_tree.selection()
        if sel:
            del self._lines[int(sel[0])]
            self._show_lines()

    def _show_lines(self):
        self.lines_tree.delete(*self.lines_tree.get_children())
        for i, ln in enumerate(self._lines):
            self.lines_tree.insert("", "end", iid=str(i), values=(
                ln["code"], ln["name"], "%g" % ln["have"], ln["unit_name"], "%g" % ln["quantity"]))

    def _save(self):
        from modules import permissions as _pm
        if not _pm.allowed("inventory", "add", parent=self.frame):
            return
        try:
            tid, number = SB.transfer(self._bid(self.from_v.get()), self._bid(self.to_v.get()),
                                      self._lines, self.notes_v.get(), self.date_v.get())
        except ValueError as e:
            self.page.say(str(e), ok=False)
            return
        except Exception as e:
            self.page.say("Not saved — nothing was moved: %s" % str(e)[:200], ok=False)
            return
        self._lines = []
        self._show_lines()
        self.notes_v.set("")
        self.load()
        self.page.say("✓ Transfer %s saved." % number)

    def load(self):
        self.tree.delete(*self.tree.get_children())
        for r in SB.list_transfers():
            self.tree.insert("", "end", iid=str(r["transfer_id"]), values=(
                r["transfer_number"], str(r["transfer_date"])[:10], r["from_name"], r["to_name"],
                r.get("n_lines") or 0, K.money(r.get("value"))))

    def _show_detail(self):
        sel = self.tree.selection()
        if not sel:
            return
        ls = SB.transfer_lines(int(sel[0]))
        self.detail_v.set("  ·  ".join("%s %g %s" % (l.get("product_name_en"), float(l.get("quantity") or 0),
                                                    l.get("unit_name") or "") for l in ls)[:600])

    def _delete(self):
        from modules import permissions as _pm
        if not _pm.allowed("inventory", "delete", parent=self.frame):
            return
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Undo transfer", "Undo this transfer? The goods go back to the "
                                   "branch they came from.", parent=self.frame):
            return
        try:
            SB.delete_transfer(int(sel[0]))
        except Exception as e:
            self.page.say("Not undone: %s" % str(e)[:150], ok=False)
            return
        self.load()
        self.page.say("Transfer undone.")

    # ── stock by branch ────────────────────────────────────────
    def _stock_tab(self, parent, C):
        top = tk.Frame(parent, bg=C["content_bg"]); top.pack(fill="x", pady=(6, 0))
        self.q_v = tk.StringVar()
        e = tk.Entry(top, textvariable=self.q_v, width=30, font=("Segoe UI", 10), relief="solid", bd=1)
        e.pack(side="left", ipady=2)
        e.bind("<Return>", lambda ev: self._load_stock())
        K.button(top, C, "🔎 Filter", self._load_stock).pack_configure(padx=6)
        cols = [("code", "Code", 90, "w"), ("name", "Product", 240, "w"), ("total", "Total", 80, "e")]
        cols += [("b%s" % b["branch_id"], (b.get("name_en") or str(b["branch_id"]))[:16], 95, "e")
                 for b in self.brs]
        self.stree = K.tree(parent, cols, height=18)

    def _load_stock(self):
        from config.database import db
        q = self.q_v.get().strip()
        try:
            if q:
                rows = db.fetchall("SELECT TOP 500 product_id, product_code, product_name_en, stock_quantity "
                                   "FROM products WHERE ISNULL(product_type,'product')<>'service' AND (product_code LIKE ? "
                                   "OR product_name_en LIKE ?) ORDER BY product_name_en",
                                   ("%" + q + "%", "%" + q + "%")) or []
            else:
                rows = db.fetchall("SELECT TOP 500 product_id, product_code, product_name_en, stock_quantity "
                                   "FROM products WHERE ISNULL(product_type,'product')<>'service' AND ISNULL(is_active,1)=1 "
                                   "ORDER BY product_name_en") or []
        except Exception:
            rows = []
        by = SB.qty_by_branch([r["product_id"] for r in rows]) if rows else {}
        self.stree.delete(*self.stree.get_children())
        for r in rows:
            b = by.get(r["product_id"], {})
            self.stree.insert("", "end", values=[r["product_code"], r["product_name_en"],
                                                 "%g" % float(r.get("stock_quantity") or 0)]
                              + ["%g" % float(b.get(x["branch_id"], 0)) for x in self.brs])
