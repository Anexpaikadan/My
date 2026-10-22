# ============================================================
# DayBill ERP - Recipes / Bill of Materials screen (v7.0)
# ------------------------------------------------------------
# ONE editor for "what goes into a product" (modules/bom.py), opened
# with two wordings:
#   RecipesView  Restaurant ▸ Recipes — dishes and their ingredients.
#                "Use up the ingredients when the dish is sold" is
#                ticked for a new recipe.
#   BomView      Production ▸ Bill of Materials — products and their
#                materials. That box is not ticked (a production entry
#                uses the materials up).
# Left : products that have a recipe (search by code / name / barcode).
# Right: the product, how many one batch makes, the components (qty,
#        unit, waste %), labour and overhead of one batch, and the live
#        cost: batch cost, cost of one unit, sale price, profit, profit %.
# Keys:  Enter adds the component · Delete removes the line ·
#        double-click a line to change it · Ctrl+S save · Ctrl+N new
# ============================================================

import weakref
import tkinter as tk
from tkinter import messagebox

from config.database import db
from modules import bom
from modules import permissions as perm
from ui import v6_kit as K

WORDS = {
    "recipe": dict(
        title="📋  Recipes",
        sub="What goes into each dish: the ingredients, how much, and the waste. DayBill works out "
            "what one dish costs and the profit on its price. With \"use up the ingredients\" "
            "ticked, selling the dish takes the ingredients out of stock.",
        list="Dishes with a recipe", product="Dish", component="Ingredient",
        components="Ingredients", makes="One recipe makes",
        deduct="Use up the ingredients when this dish is sold", deduct_default=True,
        new="New recipe", saved="Recipe saved", kind="recipe"),
    "bom": dict(
        title="📋  Bill of Materials",
        sub="What one batch of a product needs: the materials, how much, the waste, labour and "
            "overhead. DayBill works out what one unit costs and the profit on its price. A "
            "Production Entry uses the materials up and puts the product into stock.",
        list="Products with a bill of materials", product="Product", component="Material",
        components="Materials", makes="One batch makes",
        deduct="Use up the materials when this product is sold (no production entry)",
        deduct_default=False, new="New bill of materials", saved="Bill of materials saved",
        kind="bill of materials"),
}


_LIVE = weakref.WeakSet()           # open editors (Ctrl+S goes to the one on screen)


def _ctrl_s(event):
    for ed in list(_LIVE):
        try:
            if ed.frame.winfo_exists() and ed.frame.winfo_ismapped() and \
                    event.widget.winfo_toplevel() is ed.frame.winfo_toplevel():
                ed._save()
                return "break"
        except Exception:
            continue
    return None


def _money(v):
    try:
        from modules import country
        return country.money(v)
    except Exception:
        return K.money(v)


def _money_sym(v):
    try:
        from modules import country
        return country.money(v, sym=True)
    except Exception:
        return K.money(v)


def _qty(v):
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return "0"
    return ("%.4f" % x).rstrip("0").rstrip(".") or "0"


def _each(v):
    """Cost of one unit: 4 decimals when it is small (a gram of saffron)."""
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        x = 0.0
    if x and abs(x) < 1 and round(x, 2) != round(x, 4):
        return "%.4f" % x
    return _money(x)


class BomEditor:
    def __init__(self, parent, mode="bom"):
        self.mode = mode if mode in WORDS else "bom"
        self.W = W = WORDS[self.mode]
        self.page = K.Page(parent, W["title"], W["sub"])
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.frame.new_record = self._new             # Ctrl+N (main window)
        self.product = None                            # products row of the product
        self.bom_id = None
        self.lines = []
        self._edit_idx = None
        self._each_cache = {}
        self._clean_sig = None
        self.cost = {}
        if not bom.ready():
            self.page.say("⚠ Recipes need the v7.0 database update — Updates ▸ Apply All Updates.",
                          ok=False)
            return
        body = self.page.body
        body.columnconfigure(0, weight=2, minsize=260)
        body.columnconfigure(1, weight=5)
        body.rowconfigure(0, weight=1)
        self._left(body, C).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._right(body, C).grid(row=0, column=1, sticky="nsew")
        _LIVE.add(self)
        root = self.frame.winfo_toplevel()
        if not getattr(root, "_bom_ctrl_s", False):     # installed once
            root._bom_ctrl_s = True
            for seq in ("<Control-s>", "<Control-S>"):
                self.frame.bind_all(seq, _ctrl_s, add="+")
        self.load_list()
        self._new()

    # ── left: the products that have a recipe ─────────────────
    def _left(self, parent, C):
        c = K.card(parent, C, self.W["list"])
        r = tk.Frame(c, bg=C["card_bg"])
        r.pack(fill="x", padx=10)
        self.search_v = tk.StringVar()
        e = K.entry(r, C, "Find (code, name or barcode)", self.search_v, 24)
        self.search_v.trace_add("write", lambda *a: self.load_list())
        e.bind("<Down>", lambda ev: (self._focus_list(), "break")[1])
        self.ltree = K.tree(c, [("code", "Code", 70, "w"), ("name", self.W["product"], 170, "w"),
                                ("makes", "Makes", 70, "e"), ("sale", "Used up on sale", 60, "center")],
                            height=14)
        self.ltree.bind("<<TreeviewSelect>>", lambda ev: self._pick_from_list())
        self.ltree.bind("<Return>", lambda ev: self._pick_from_list())
        rb = tk.Frame(c, bg=C["card_bg"])
        rb.pack(fill="x", padx=10, pady=(0, 10))
        K.button(rb, C, "＋  " + self.W["new"], self._new, primary=True)
        self.count_v = tk.StringVar()
        tk.Label(rb, textvariable=self.count_v, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="right")
        return c

    def _focus_list(self):
        kids = self.ltree.get_children()
        if kids:
            self.ltree.focus_set()
            self.ltree.focus(kids[0])

    def load_list(self, select=None):
        if not hasattr(self, "ltree"):
            return
        self.ltree.delete(*self.ltree.get_children())
        rows = bom.with_recipe(self.search_v.get())
        for r in rows:
            self.ltree.insert("", "end", iid=str(r["product_id"]), values=(
                r.get("product_code") or "", r.get("product_name_en") or "",
                "%s %s" % (_qty(r.get("output_qty")), r.get("output_unit") or ""),
                "Yes" if r.get("deduct_on_sale") else ""))
        self.count_v.set("%d %s" % (len(rows), "recipe(s)" if self.mode == "recipe" else "item(s)"))
        if select:
            try:
                self._quiet_select = True
                self.ltree.selection_set(str(select))
                self.ltree.see(str(select))
            except Exception:
                pass
            finally:
                self.frame.after_idle(lambda: setattr(self, "_quiet_select", False))

    def _pick_from_list(self):
        if getattr(self, "_quiet_select", False):
            return
        sel = self.ltree.selection()
        if not sel:
            return
        pid = int(sel[0])
        if self.product and self.product.get("product_id") == pid and self.bom_id:
            return
        if not self._may_leave():
            return
        self.open_product(pid)

    # ── right: the recipe ─────────────────────────────────────
    def _right(self, parent, C):
        W = self.W
        c = K.card(parent, C, None)
        # the product
        r1 = tk.Frame(c, bg=C["card_bg"])
        r1.pack(fill="x", padx=10, pady=(8, 0))
        self.finder = K.ProductFinder(r1, C, self._picked_product,
                                      label="%s (code, name or barcode)" % W["product"], width=30)
        self.finder.pack(side="left", padx=(0, 10), anchor="n")
        self.prod_info_v = tk.StringVar(value="Pick the %s first." % W["product"].lower())
        tk.Label(r1, textvariable=self.prod_info_v, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"], justify="left", anchor="w").pack(side="left", fill="x",
                                                                        expand=True, pady=(14, 0))
        r2 = tk.Frame(c, bg=C["card_bg"])
        r2.pack(fill="x", padx=10)
        self.out_qty_v = tk.StringVar(value="1")
        self.out_unit_v = tk.StringVar()
        self.name_v = tk.StringVar()
        K.entry(r2, C, W["makes"], self.out_qty_v, 8, justify="right")
        self.out_unit_cb = K.combo(r2, C, "Unit", self.out_unit_v, [], 10)
        self.out_unit_cb.bind("<<ComboboxSelected>>", lambda e: self._recalc())
        K.entry(r2, C, "Recipe name (optional)", self.name_v, 26)

        # the components
        cc = K.card(c, C, W["components"], fill="both", expand=True, padx=10, pady=(6, 4))
        ra = tk.Frame(cc, bg=C["card_bg"])
        ra.pack(fill="x", padx=10)
        self.comp_finder = K.ProductFinder(ra, C, self._picked_component,
                                           label="%s (code, name or barcode)" % W["component"],
                                           width=28)
        self.comp_finder.pack(side="left", padx=(0, 10), anchor="n")
        self.qty_v, self.unit_v, self.waste_v = tk.StringVar(value="1"), tk.StringVar(), tk.StringVar(value="0")
        self.qty_e = K.entry(ra, C, "Qty", self.qty_v, 8, justify="right")
        self.unit_cb = K.combo(ra, C, "Unit", self.unit_v, [], 9)
        self.waste_e = K.entry(ra, C, "Waste %", self.waste_v, 6, justify="right")
        bf = tk.Frame(ra, bg=C["card_bg"])
        bf.pack(side="left", pady=(14, 0))
        self.add_btn = K.button(bf, C, "＋ Add  [Enter]", self._add, primary=True)
        for w in (self.qty_e, self.waste_e):
            w.bind("<Return>", lambda e: (self._add(), "break")[1])
        self.tree = K.tree(cc, [("n", "#", 34, "center"), ("code", "Code", 70, "w"),
                                ("name", W["component"], 190, "w"), ("qty", "Qty", 70, "e"),
                                ("unit", "Unit", 60, "center"), ("waste", "Waste %", 60, "e"),
                                ("each", "Cost each", 85, "e"), ("cost", "Line cost", 90, "e")],
                           height=7)
        self.tree.tag_configure("nocost", foreground=C.get("danger", "#DC2626"))
        self.tree.bind("<Double-1>", lambda e: self._edit_line())
        self.tree.bind("<Return>", lambda e: self._edit_line())
        self.tree.bind("<Delete>", lambda e: self._remove())
        rl = tk.Frame(cc, bg=C["card_bg"])
        rl.pack(fill="x", padx=10, pady=(0, 8))
        K.button(rl, C, "✏ Change line", self._edit_line)
        K.button(rl, C, "🗑 Remove line  [Del]", self._remove)
        K.button(rl, C, "▲", lambda: self._move(-1))
        K.button(rl, C, "▼", lambda: self._move(1))
        tk.Label(rl, text="Waste % adds to the quantity used (peel, trim, spill).",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"]).pack(side="right")

        # labour / overhead / use-up + the cost
        bottom = tk.Frame(c, bg=C["card_bg"])
        bottom.pack(fill="x", padx=10, pady=(2, 0))
        lf = tk.Frame(bottom, bg=C["card_bg"])
        lf.pack(side="left", fill="both", expand=True, anchor="n")
        r3 = tk.Frame(lf, bg=C["card_bg"])
        r3.pack(fill="x")
        self.labour_v, self.overhead_v = tk.StringVar(value="0"), tk.StringVar(value="0")
        K.entry(r3, C, "Labour (one batch)", self.labour_v, 10, justify="right")
        K.entry(r3, C, "Overhead (gas, power …)", self.overhead_v, 10, justify="right")
        self.deduct_v = tk.BooleanVar(value=W["deduct_default"])
        tk.Checkbutton(lf, text=W["deduct"], variable=self.deduct_v, bg=C["card_bg"],
                       activebackground=C["card_bg"], font=("Segoe UI", 9), anchor="w",
                       command=self._recalc).pack(fill="x", pady=(4, 0))
        self.notes_v = tk.StringVar()
        r4 = tk.Frame(lf, bg=C["card_bg"])
        r4.pack(fill="x")
        K.entry(r4, C, "Notes", self.notes_v, 44)
        for v in (self.out_qty_v, self.labour_v, self.overhead_v):
            v.trace_add("write", lambda *a: self._recalc())

        cf = tk.Frame(bottom, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        cf.pack(side="right", anchor="n", padx=(10, 0))
        self.sum_vars = {}
        rows = (("materials", "Materials"), ("labour", "Labour"), ("overhead", "Overhead"),
                ("total", "Cost of one batch"), ("per_unit", "Cost of 1 unit"),
                ("sale", "Sale price (no VAT)"), ("profit", "Profit on 1 unit"), ("pct", "Profit %"))
        for i, (k, label) in enumerate(rows):
            bold = k in ("total", "per_unit", "profit")
            lv = tk.StringVar(value=label)
            self.sum_vars[k + "_label"] = lv
            tk.Label(cf, textvariable=lv, font=("Segoe UI", 9, "bold" if bold else "normal"),
                     bg=C["card_bg"], fg=C["text_secondary"], anchor="w").grid(
                         row=i, column=0, sticky="w", padx=(10, 16), pady=1)
            v = tk.StringVar(value="0.00")
            self.sum_vars[k] = v
            lbl = tk.Label(cf, textvariable=v, font=("Segoe UI", 10, "bold" if bold else "normal"),
                           bg=C["card_bg"], fg=C["text_primary"], anchor="e")
            lbl.grid(row=i, column=1, sticky="e", padx=(0, 10), pady=1)
            if k in ("profit", "pct"):
                setattr(self, "_lbl_" + k, lbl)

        rb = tk.Frame(c, bg=C["card_bg"])
        rb.pack(fill="x", padx=10, pady=(6, 10))
        K.button(rb, C, "💾  Save  [Ctrl+S]", self._save, primary=True)
        K.button(rb, C, "＋  New", self._new)
        K.button(rb, C, "🗑  Delete", self._delete, danger=True)
        return c

    # ── product ───────────────────────────────────────────────
    def _product_row(self, pid):
        try:
            return db.fetchone("SELECT product_id, product_code, product_name_en, unit_of_measure_en, "
                               "ISNULL(unit_price,0) AS unit_price, ISNULL(stock_quantity,0) AS stock, "
                               "ISNULL(product_type,'product') AS product_type FROM products "
                               "WHERE product_id=?", (int(pid),))
        except Exception:
            return None

    def _picked_product(self, row):
        pid = row.get("product_id")
        if not pid:
            return
        if self.product and self.product.get("product_id") == pid:
            return
        if bom.header(pid):
            if self.lines and self._is_dirty() and not self.bom_id:
                if not messagebox.askyesno(self.W["title"].strip("📋 "),
                                           "%s already has a %s.\n\nOpen it? (the lines you typed "
                                           "here are not saved)" % (row.get("product_name_en"),
                                                                    self.W["kind"]),
                                           parent=self.frame):
                    self._show_product(self.product)
                    return
            self.open_product(pid)
            return
        # a product without a recipe: start one (keeps lines typed so far)
        self._set_product(pid)
        self.bom_id = None
        self.page.say("%s has no %s yet — add the %s and Save."
                      % (row.get("product_name_en"), self.W["kind"], self.W["components"].lower()))
        self.comp_finder.entry.focus_set()

    def _set_product(self, pid):
        p = self._product_row(pid)
        self.product = dict(p) if p else None
        units = bom.units(pid) if p else []
        self.out_unit_cb["values"] = units
        if units and self.out_unit_v.get() not in units:
            self.out_unit_v.set(units[0])
        self._show_product(self.product)
        self._sale_cache = {}
        self._recalc()

    def _show_product(self, p):
        if not p:
            self.finder.clear()
            self.prod_info_v.set("Pick the %s first." % self.W["product"].lower())
            return
        self.finder.picked = p
        self.finder.var.set("%s — %s" % (p.get("product_code"), p.get("product_name_en")))
        self.prod_info_v.set("Base unit: %s   ·   Price %s   ·   In stock %s"
                             % (p.get("unit_of_measure_en") or "Unit", _money_sym(p.get("unit_price")),
                                _qty(p.get("stock"))))

    def open_product(self, product_id):
        """Load the product's saved recipe into the editor."""
        r = bom.get(product_id)
        self._clear(keep_list=True)
        self._set_product(product_id)
        if not r:
            return
        h = r["header"]
        self.bom_id = h.get("bom_id")
        self.out_qty_v.set(_qty(h.get("output_qty")) or "1")
        if h.get("output_unit"):
            self.out_unit_v.set(h["output_unit"])
        self.name_v.set(h.get("bom_name") or "")
        self.labour_v.set(_qty(h.get("labour_cost")))
        self.overhead_v.set(_qty(h.get("overhead_cost")))
        self.deduct_v.set(bool(h.get("deduct_on_sale")))
        self.notes_v.set(h.get("notes") or "")
        self.lines = [{"component_id": l["component_id"], "product_code": l.get("product_code") or "",
                       "product_name_en": l.get("product_name_en") or "",
                       "quantity": float(l.get("quantity") or 0),
                       "unit_name": l.get("unit_name") or l.get("base_unit") or "",
                       "waste_pct": float(l.get("waste_pct") or 0)} for l in r["lines"]]
        self._render()
        self._mark_clean()
        self.load_list(select=product_id)
        self.page.say("%s — %s." % (self.W["kind"].capitalize(), self.product.get("product_name_en")
                                    if self.product else product_id))

    # ── components ────────────────────────────────────────────
    def _picked_component(self, row):
        cid = row.get("product_id")
        units = bom.units(cid) if cid else []
        self.unit_cb["values"] = units
        if units:
            self.unit_v.set(units[0])
        self.qty_e.focus_set()
        self.qty_e.select_range(0, "end")

    def _add(self):
        p = self.comp_finder.picked
        if not p:
            self.comp_finder.find()
            return
        qty = K.num(self.qty_v)
        if not qty or qty <= 0:
            messagebox.showwarning(self.W["component"], "Type a quantity above 0.", parent=self.frame)
            return
        waste = K.num(self.waste_v, 0) or 0.0
        if waste < 0 or waste >= 100:
            messagebox.showwarning(self.W["component"], "Waste % must be from 0 to 99.",
                                   parent=self.frame)
            return
        if self.product and p["product_id"] == self.product.get("product_id"):
            messagebox.showwarning(self.W["component"], "A product can't be an %s of itself."
                                   % self.W["component"].lower(), parent=self.frame)
            return
        units = bom.units(p["product_id"])
        unit = self.unit_v.get() if self.unit_v.get() in units else units[0]
        line = {"component_id": p["product_id"], "product_code": p.get("product_code") or "",
                "product_name_en": p.get("product_name_en") or "", "quantity": float(qty),
                "unit_name": unit, "waste_pct": float(waste)}
        if self._edit_idx is not None and 0 <= self._edit_idx < len(self.lines):
            self.lines[self._edit_idx] = line
        else:
            same = next((l for l in self.lines if l["component_id"] == line["component_id"]
                         and l["unit_name"] == unit and abs(l["waste_pct"] - waste) < 1e-9), None)
            if same:
                same["quantity"] += line["quantity"]
            else:
                self.lines.append(line)
        self._reset_add_row()
        self._render()

    def _reset_add_row(self):
        self._edit_idx = None
        self.comp_finder.clear()
        self.qty_v.set("1")
        self.waste_v.set("0")
        self.unit_v.set("")
        self.unit_cb["values"] = []
        self.add_btn.configure(text="＋ Add  [Enter]")
        try:
            self.comp_finder.entry.focus_set()
        except Exception:
            pass

    def _sel_idx(self):
        s = self.tree.selection()
        if not s:
            return None
        i = int(s[0])
        return i if 0 <= i < len(self.lines) else None

    def _edit_line(self):
        i = self._sel_idx()
        if i is None:
            return
        l = self.lines[i]
        self._edit_idx = i
        self.comp_finder.picked = {"product_id": l["component_id"], "product_code": l["product_code"],
                                   "product_name_en": l["product_name_en"]}
        self.comp_finder.var.set("%s — %s" % (l["product_code"], l["product_name_en"]))
        self.unit_cb["values"] = bom.units(l["component_id"])
        self.unit_v.set(l["unit_name"])
        self.qty_v.set(_qty(l["quantity"]))
        self.waste_v.set(_qty(l["waste_pct"]))
        self.add_btn.configure(text="✔ Update line  [Enter]")
        self.qty_e.focus_set()
        self.qty_e.select_range(0, "end")

    def _remove(self):
        i = self._sel_idx()
        if i is None:
            return
        del self.lines[i]
        if self._edit_idx is not None:
            self._reset_add_row()
        self._render()

    def _move(self, step):
        i = self._sel_idx()
        if i is None:
            return
        j = i + step
        if not (0 <= j < len(self.lines)):
            return
        self.lines[i], self.lines[j] = self.lines[j], self.lines[i]
        self._render()
        self.tree.selection_set(str(j))

    # ── cost ──────────────────────────────────────────────────
    def _cost_each(self, cid, unit):
        key = (cid, unit)
        if key not in self._each_cache:
            self._each_cache[key] = bom.cost_each(cid, unit)
        return self._each_cache[key]

    def _sale(self, unit):
        if not self.product:
            return 0.0
        cache = getattr(self, "_sale_cache", None)
        if cache is None:
            cache = self._sale_cache = {}
        if unit not in cache:
            cache[unit] = bom.sale_price(self.product["product_id"], unit)
        return cache[unit]

    def _recalc(self):
        """Live roll-up (the same sums as bom.rollup, from cached costs)."""
        if not hasattr(self, "sum_vars"):
            return
        mat = 0.0
        for l in self.lines:
            each = self._cost_each(l["component_id"], l["unit_name"])
            l["cost_each"] = each
            l["line_cost"] = l["quantity"] * (1 + l["waste_pct"] / 100.0) * each
            mat += l["line_cost"]
        lab = K.num(self.labour_v, 0) or 0.0
        ovh = K.num(self.overhead_v, 0) or 0.0
        total = mat + lab + ovh
        oq = K.num(self.out_qty_v, 0) or 0.0
        per = total / oq if oq > 0 else 0.0
        unit = self.out_unit_v.get() or ((self.product or {}).get("unit_of_measure_en") or "unit")
        sale = self._sale(self.out_unit_v.get()) if self.product else 0.0
        profit = sale - per
        pct = (profit / sale * 100.0) if sale else None
        self.cost = {"materials": round(mat, 4), "labour": lab, "overhead": ovh,
                     "total": round(total, 4), "per_unit": round(per, 4), "sale": round(sale, 4),
                     "profit": round(profit, 4), "pct": round(pct, 2) if pct is not None else None}
        v = self.sum_vars
        v["materials"].set(_money(mat))
        v["labour"].set(_money(lab))
        v["overhead"].set(_money(ovh))
        v["total"].set(_money_sym(total))
        v["per_unit_label"].set("Cost of 1 %s" % unit)
        v["per_unit"].set(_money_sym(per))
        v["sale"].set(_money_sym(sale) if sale else "—")
        v["profit"].set(_money_sym(profit) if sale else "—")
        v["pct"].set(("%.1f %%" % pct) if pct is not None else "—")
        col = self.C.get("success", "#16A34A") if profit >= 0 else self.C.get("danger", "#DC2626")
        for k in ("profit", "pct"):
            try:
                getattr(self, "_lbl_" + k).configure(fg=col if sale else self.C["text_primary"])
            except Exception:
                pass
        if hasattr(self, "tree"):
            for i, l in enumerate(self.lines):
                if self.tree.exists(str(i)):
                    self.tree.set(str(i), "each", _each(l["cost_each"]))
                    self.tree.set(str(i), "cost", _money(l["line_cost"]))

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        for i, l in enumerate(self.lines):
            each = self._cost_each(l["component_id"], l["unit_name"])
            self.tree.insert("", "end", iid=str(i), tags=("nocost",) if each <= 0 else (), values=(
                i + 1, l["product_code"], l["product_name_en"], _qty(l["quantity"]), l["unit_name"],
                _qty(l["waste_pct"]) if l["waste_pct"] else "", _each(each), ""))
        self._recalc()

    # ── save / delete / new ───────────────────────────────────
    def _head(self):
        return {"bom_name": self.name_v.get().strip(), "output_qty": K.num(self.out_qty_v, 0) or 0,
                "output_unit": self.out_unit_v.get().strip(), "labour_cost": K.num(self.labour_v, 0) or 0,
                "overhead_cost": K.num(self.overhead_v, 0) or 0, "deduct_on_sale": bool(self.deduct_v.get()),
                "notes": self.notes_v.get().strip()}

    def _save(self):
        if not perm.allowed("products", "edit", parent=self.frame):
            return False
        if not self.product:
            messagebox.showwarning(self.W["title"].strip("📋 "), "Pick the %s first."
                                   % self.W["product"].lower(), parent=self.frame)
            return False
        if self._edit_idx is not None and self.comp_finder.picked:
            self._add()                       # a line being changed: keep the change
        h = self._head()
        if h["output_qty"] <= 0:
            messagebox.showwarning(self.W["title"].strip("📋 "), "How many does one batch make? "
                                   "Type a number above 0.", parent=self.frame)
            return False
        if h["labour_cost"] < 0 or h["overhead_cost"] < 0:
            messagebox.showwarning(self.W["title"].strip("📋 "), "Labour and overhead can't be "
                                   "below 0.", parent=self.frame)
            return False
        if not self.lines:
            messagebox.showwarning(self.W["title"].strip("📋 "), "Add at least one %s."
                                   % self.W["component"].lower(), parent=self.frame)
            return False
        try:
            bid = bom.save(self.product["product_id"], h, self.lines)
        except ValueError as e:
            msg = str(e)
            if "loop" in msg.lower() or "itself" in msg.lower():
                msg += ("\n\nTake that %s out — a product can't be made from something that "
                        "is made from it." % self.W["component"].lower())
            messagebox.showwarning(self.W["title"].strip("📋 "), msg, parent=self.frame)
            return False
        except Exception as e:
            messagebox.showerror(self.W["title"].strip("📋 "), "Not saved: %s" % str(e)[:300],
                                 parent=self.frame)
            return False
        self.bom_id = bid
        self._mark_clean()
        self.load_list(select=self.product["product_id"])
        try:
            from modules.doc_actions import audit
            audit("edit", "bom", bid, "%s: %d line(s)" % (self.product.get("product_name_en"),
                                                         len(self.lines)))
        except Exception:
            pass
        self.page.say("✔ %s — %s. Cost of 1 %s: %s" % (
            self.W["saved"], self.product.get("product_name_en"),
            self.out_unit_v.get() or "unit", _money_sym(self.cost.get("per_unit"))))
        return True

    def _delete(self):
        if not self.bom_id or not self.product:
            messagebox.showinfo(self.W["title"].strip("📋 "), "Nothing saved to delete.",
                                parent=self.frame)
            return False
        if not perm.allowed("products", "delete", parent=self.frame):
            return False
        if not messagebox.askyesno(self.W["title"].strip("📋 "),
                                   "Delete the %s of %s?\n\nSaved production entries keep their "
                                   "materials." % (self.W["kind"], self.product.get("product_name_en")),
                                   parent=self.frame):
            return False
        try:
            bom.delete(self.bom_id)
        except Exception as e:
            messagebox.showerror(self.W["title"].strip("📋 "), str(e)[:300], parent=self.frame)
            return False
        name = self.product.get("product_name_en")
        self._new()
        self.load_list()
        self.page.say("🗑 Deleted the %s of %s." % (self.W["kind"], name))
        return True

    def _clear(self, keep_list=False):
        self.product = None
        self.bom_id = None
        self.lines = []
        self._each_cache = {}
        self._sale_cache = {}
        self.finder.clear()
        self.out_qty_v.set("1")
        self.out_unit_v.set("")
        self.out_unit_cb["values"] = []
        self.name_v.set("")
        self.labour_v.set("0")
        self.overhead_v.set("0")
        self.notes_v.set("")
        self.deduct_v.set(self.W["deduct_default"])
        self._reset_add_row()
        self._show_product(None)
        self._render()

    def _new(self):
        if not hasattr(self, "tree"):
            return
        if not self._may_leave():
            return
        self._clear()
        self._mark_clean()
        try:
            self._quiet_select = True
            self.ltree.selection_remove(*self.ltree.selection())
        finally:
            self.frame.after_idle(lambda: setattr(self, "_quiet_select", False))
        self.page.say("%s — pick the %s, then add the %s." % (
            self.W["new"], self.W["product"].lower(), self.W["components"].lower()))
        try:
            self.finder.entry.focus_set()
        except Exception:
            pass

    # ── unsaved changes ───────────────────────────────────────
    def _sig(self):
        return (self.product.get("product_id") if self.product else None,
                tuple((l["component_id"], round(l["quantity"], 6), l["unit_name"],
                       round(l["waste_pct"], 6)) for l in self.lines),
                tuple(sorted((k, str(v)) for k, v in self._head().items())))

    def _mark_clean(self):
        self._clean_sig = self._sig()

    def _is_dirty(self):
        if not self.product and not self.lines:
            return False
        return self._sig() != self._clean_sig

    def _may_leave(self):
        if not self._is_dirty() or not self.lines:
            return True
        return messagebox.askyesno(self.W["title"].strip("📋 "),
                                   "The %s you are typing is not saved.\n\nLeave it without "
                                   "saving?" % self.W["kind"], parent=self.frame)


class RecipesView(BomEditor):
    """Restaurant ▸ Recipes."""

    def __init__(self, parent):
        super().__init__(parent, "recipe")


class BomView(BomEditor):
    """Production ▸ Bill of Materials."""

    def __init__(self, parent):
        super().__init__(parent, "bom")
