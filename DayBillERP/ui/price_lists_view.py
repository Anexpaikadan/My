# ============================================================
# DayBill ERP - Price Lists page (Inventory ▸ Price Lists)  v6.0
# ------------------------------------------------------------
# Left : the lists (name, starts from, + / − %)
# Right: fixed prices of single products in the selected list
# Customers ▸ Contact & Credit ▸ Price list gives a customer a list.
# ============================================================
import tkinter as tk
from tkinter import messagebox

from modules import price_lists as PL
from ui import v6_kit as K


class PriceListsView:
    def __init__(self, parent):
        self.page = K.Page(parent, "💲  Price Lists",
                           "Sell to some customers at other prices: start from the normal price, the "
                           "wholesale price or the cost, add or take off a percent, and set fixed "
                           "prices for single products. Give a customer a list in Customers ▸ "
                           "Contact & Credit.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.list_id = None
        if not PL.ready():
            self.page.say("⚠ Price lists need the v6.0 database update — Updates ▸ Apply All Updates.",
                          ok=False)
            return
        body = self.page.body
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)
        self._left(body, C).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._right(body, C).grid(row=0, column=1, sticky="nsew")
        self.load()

    # ── lists ──────────────────────────────────────────────────
    def _left(self, parent, C):
        c = K.card(parent, C, "Price lists")
        self.ltree = K.tree(c, [("name", "Name", 170, "w"), ("base", "Starts from", 140, "w"),
                                ("adj", "+ / − %", 70, "e"), ("st", "Status", 70, "center")],
                            height=12)
        self.ltree.bind("<<TreeviewSelect>>", lambda e: self._pick())
        self.v = {k: tk.StringVar() for k in ("name_en", "name_ar", "adj")}
        self.base_v = tk.StringVar(value=PL.BASES[0][1])
        self.active_v = tk.BooleanVar(value=True)
        r1 = tk.Frame(c, bg=C["card_bg"]); r1.pack(fill="x", padx=10)
        K.entry(r1, C, "Name (English) *", self.v["name_en"], 20)
        K.entry(r1, C, "الاسم (عربي)", self.v["name_ar"], 16, justify="right")
        r2 = tk.Frame(c, bg=C["card_bg"]); r2.pack(fill="x", padx=10)
        K.combo(r2, C, "Starts from", self.base_v, [b[1] for b in PL.BASES], 20)
        K.entry(r2, C, "+ / − percent", self.v["adj"], 8, justify="right")
        r3 = tk.Frame(c, bg=C["card_bg"]); r3.pack(fill="x", padx=10, pady=(6, 10))
        tk.Checkbutton(r3, text="Active", variable=self.active_v, bg=C["card_bg"],
                       activebackground=C["card_bg"]).pack(side="left", padx=(0, 8))
        K.button(r3, C, "💾 Save list", self._save, primary=True)
        K.button(r3, C, "＋ New", self._new)
        K.button(r3, C, "🗑 Delete", self._delete)
        tk.Label(c, text="Example: 'VIP' starts from the normal price, −5 %.\n"
                         "'Restaurants' starts from the wholesale price, +0 %.",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                 justify="left").pack(anchor="w", padx=12, pady=(0, 8))
        return c

    # ── fixed prices ───────────────────────────────────────────
    def _right(self, parent, C):
        c = K.card(parent, C, "Fixed prices in this list (optional)")
        self.itree = K.tree(c, [("code", "Code", 80, "w"), ("name", "Product", 230, "w"),
                                ("unit", "Unit", 90, "w"), ("normal", "Normal price", 100, "e"),
                                ("price", "List price", 100, "e")], height=12)
        r1 = tk.Frame(c, bg=C["card_bg"]); r1.pack(fill="x", padx=10)
        self.finder = K.ProductFinder(r1, C, self._picked_product)
        self.finder.pack(side="left", padx=(0, 10))
        self.unit_v, self.price_v = tk.StringVar(value="(every unit)"), tk.StringVar()
        self.unit_cb = K.combo(r1, C, "Unit", self.unit_v, ["(every unit)"], 12)
        K.entry(r1, C, "Price *", self.price_v, 10, justify="right")
        r2 = tk.Frame(c, bg=C["card_bg"]); r2.pack(fill="x", padx=10, pady=(6, 10))
        K.button(r2, C, "💾 Set price", self._set_price, primary=True)
        K.button(r2, C, "🗑 Remove selected", self._remove_price)
        self.preview_v = tk.StringVar()
        tk.Label(c, textvariable=self.preview_v, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"], anchor="w", justify="left").pack(fill="x", padx=12, pady=(0, 8))
        return c

    # ── data ───────────────────────────────────────────────────
    def load(self, select=None):
        self.ltree.delete(*self.ltree.get_children())
        bases = dict(PL.BASES)
        for l in PL.lists(active_only=False):
            self.ltree.insert("", "end", iid=str(l["price_list_id"]),
                              values=(l["name_en"], bases.get(l.get("base_on"), l.get("base_on")),
                                      "%+.2f" % float(l.get("adjust_percent") or 0),
                                      "Active" if l.get("is_active", 1) else "Off"))
        if select:
            try:
                self.ltree.selection_set(str(select))
                self.ltree.see(str(select))
            except Exception:
                pass

    def _pick(self):
        sel = self.ltree.selection()
        if not sel:
            return
        l = PL.get(int(sel[0]))
        if not l:
            return
        self.list_id = l["price_list_id"]
        self.v["name_en"].set(l["name_en"])
        self.v["name_ar"].set(l.get("name_ar") or "")
        self.v["adj"].set("%g" % float(l.get("adjust_percent") or 0))
        self.base_v.set(dict(PL.BASES).get(l.get("base_on"), PL.BASES[0][1]))
        self.active_v.set(bool(l.get("is_active", 1)))
        self._load_items()

    def _load_items(self):
        self.itree.delete(*self.itree.get_children())
        if not self.list_id:
            return
        for it in PL.items(self.list_id):
            self.itree.insert("", "end", iid=str(it["item_id"]),
                              values=(it.get("product_code"), it.get("product_name_en"),
                                      it.get("unit_name") or "(every unit)",
                                      K.money(it.get("unit_price")), K.money(it.get("price"))))

    def _new(self):
        self.list_id = None
        for v in self.v.values():
            v.set("")
        self.base_v.set(PL.BASES[0][1])
        self.active_v.set(True)
        self.ltree.selection_remove(*self.ltree.selection())
        self.itree.delete(*self.itree.get_children())
        self.page.say("New price list — type a name and Save.")

    def _save(self):
        base = next((k for k, lbl in PL.BASES if lbl == self.base_v.get()), "retail")
        adj = K.num(self.v["adj"], 0.0)
        if adj is None:
            self.page.say("The percent must be a number (e.g. -5 or 10).", ok=False)
            return
        try:
            lid = PL.save_list(self.list_id, self.v["name_en"].get(), self.v["name_ar"].get(),
                               base, adj, self.active_v.get())
        except ValueError as e:
            self.page.say(str(e), ok=False)
            return
        except Exception as e:
            self.page.say("Not saved: %s" % str(e)[:150], ok=False)
            return
        self.list_id = lid
        self.load(select=lid)
        self.page.say("✓ Price list '%s' saved." % self.v["name_en"].get())

    def _delete(self):
        if not self.list_id:
            return
        if not messagebox.askyesno("Delete price list",
                                   "Delete '%s'? Customers using it go back to the normal price."
                                   % self.v["name_en"].get(), parent=self.frame):
            return
        PL.delete_list(self.list_id)
        self._new()
        self.load()
        self.page.say("Price list deleted.")

    def _picked_product(self, row):
        try:
            from modules import barcode_resolver as BR
            units = BR.units_of(row["product_id"]) or []
        except Exception:
            units = []
        self.unit_cb["values"] = ["(every unit)"] + [u.get("unit_name_en") for u in units if u.get("unit_name_en")]
        self.unit_v.set("(every unit)")
        self.price_v.set("")
        if self.list_id:
            now = PL.price_for(self.list_id, row["product_id"], None, row.get("unit_price"), 1)
            self.preview_v.set("Normal price %s  →  in this list now %s"
                               % (K.money(row.get("unit_price")), K.money(now)))

    def _set_price(self):
        if not self.list_id:
            self.page.say("Save or pick a price list first.", ok=False)
            return
        row = self.finder.picked
        if not row:
            self.page.say("Pick a product first (type and press Enter).", ok=False)
            return
        price = K.num(self.price_v)
        if price is None or price < 0:
            self.page.say("Type the price as a number.", ok=False)
            return
        unit = self.unit_v.get()
        PL.set_price(self.list_id, row["product_id"], price,
                     None if unit.startswith("(") else unit)
        self._load_items()
        self.finder.clear()
        self.price_v.set("")
        self.page.say("✓ %s: %s in this list." % (row.get("product_name_en"), K.money(price)))

    def _remove_price(self):
        sel = self.itree.selection()
        if not sel:
            return
        PL.remove_price(int(sel[0]))
        self._load_items()
        self.page.say("Fixed price removed — the list's percent applies again.")
