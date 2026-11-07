# ============================================================
# DayBill ERP - ⚡ Quick Product Entry  (v8.3)
# ------------------------------------------------------------
# A fast, spreadsheet-like way to add products one line after another.
#
#   • The TOP LINE is the new-product line:
#       Code (automatic) · Product Name · Unit · Category ·
#       Purchase Price · Sales Price
#   • Enter moves to the next box. Enter on Sales Price asks
#     "Save this product?" — Yes is the default, so Enter again saves.
#     The product is saved, shows at the top of the list, and the cursor
#     goes back to Product Name for the next line (Unit and Category stay
#     as they were, for a row of similar products).
#   • The list under it shows ALL products (newest first) or only the ones
#     typed here ("New only" — a blank list that fills line by line).
#   • Enter / double-click on a list row loads it into the top line to
#     change it (needs the Products ▸ Edit right).
#   • Esc clears the line. Ctrl+S saves. ↓ from the line goes to the list.
#
# New products are saved through modules.products_import.import_rows (the
# same code as the Excel import), so the code, system barcode, base unit,
# VAT and price history are made exactly like any other new product.
# The full Product window (Products ▸ ＋ New) is unchanged.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db

# (key, heading, width, anchor)
COLS = [("code", "Code", 90, "w"), ("name", "Product Name", 320, "w"),
        ("unit", "Unit", 90, "w"), ("cat", "Category", 170, "w"),
        ("pprice", "Purchase Price", 120, "e"), ("sprice", "Sales Price", 120, "e"),
        ("margin", "Margin %", 90, "e")]


def _num(v):
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s else None
    except Exception:
        return None


def _money(v):
    try:
        return "{:,.2f}".format(float(v or 0))
    except Exception:
        return ""


def _margin(pp, sp):
    try:
        pp, sp = float(pp or 0), float(sp or 0)
        if sp > 0 and pp > 0:
            return "%.1f" % ((sp - pp) / sp * 100.0)
    except Exception:
        pass
    return ""


class QuickProductsView:
    def __init__(self, parent):
        self.parent = parent
        self.C = C = cfg.theme()
        self._rows = []              # products in the list (dicts)
        self._session_ids = []       # saved here, newest first
        self._edit_id = None         # product_id loaded into the line (None = new)
        self._edit_code = None
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._load_lookups()
        self._build(C)
        self._new_line()
        self._load_list()
        self.frame.after(150, self._focus_name)

    # ── data ──────────────────────────────────────────────────
    def _load_lookups(self):
        try:
            self._cats = db.fetchall(
                "SELECT category_id, category_name_en FROM product_categories "
                "WHERE is_active=1 ORDER BY category_name_en") or []
        except Exception:
            self._cats = []
        units = None
        try:
            from modules import masters as _ms
            units = _ms.unit_names()
            if not units:
                units = list(_ms.DEFAULT_UNITS)
        except Exception:
            units = ["PCs", "Box", "Carton", "Dozen", "Kg", "Gram", "Liter", "Pack", "Bag", "Unit"]
        self._units = units

    def _cat_names(self):
        return [str(c.get("category_name_en") or "").strip() for c in self._cats
                if str(c.get("category_name_en") or "").strip()]

    def _cat_id(self, name, create=True):
        """Category id for a name; a new name is added to Product Categories."""
        name = str(name or "").strip()
        if not name:
            return None
        for c in self._cats:
            if str(c.get("category_name_en") or "").strip().lower() == name.lower():
                return c["category_id"]
        if not create:
            return None
        db.execute("INSERT INTO product_categories (category_name_en, category_name_ar) "
                   "VALUES (?, ?)", (name[:100], name[:100]))
        self._load_lookups()
        try:
            self.cat_cb.configure(values=self._cat_names())
        except Exception:
            pass
        for c in self._cats:
            if str(c.get("category_name_en") or "").strip().lower() == name.lower():
                return c["category_id"]
        return None

    def _query(self, where="", params=()):
        base = ("SELECT p.product_id, p.product_code, p.product_name_en, p.unit_of_measure_en, "
                "ISNULL(pc.category_name_en,'') AS category_name, {pp} AS purchase_price, "
                "p.unit_price FROM products p "
                "LEFT JOIN product_categories pc ON p.category_id=pc.category_id ")
        order = " ORDER BY p.product_id DESC"
        try:
            return db.fetchall(base.format(pp="ISNULL(p.purchase_price,0)") + where + order,
                               params) or []
        except Exception:
            return db.fetchall(base.format(pp="0") + where + order, params) or []

    def _load_list(self):
        show_all = self.show_var.get() == "all"
        try:
            if show_all:
                self._rows = self._query("WHERE ISNULL(p.is_active,1)=1")
            elif self._session_ids:
                ids = ",".join(str(int(i)) for i in self._session_ids)
                self._rows = self._query("WHERE p.product_id IN (%s)" % ids)
            else:
                self._rows = []
        except Exception as e:
            self._rows = []
            self._status("Could not load the products: %s" % str(e)[:120], err=True)
        self._fill_tree()

    def _fill_tree(self):
        q = self.search_var.get().strip().lower()
        tv = self.tree
        tv.delete(*tv.get_children())
        n = 0
        for r in self._rows:
            vals = (r.get("product_code") or "", r.get("product_name_en") or "",
                    r.get("unit_of_measure_en") or "", r.get("category_name") or "",
                    _money(r.get("purchase_price")), _money(r.get("unit_price")),
                    _margin(r.get("purchase_price"), r.get("unit_price")))
            if q and not any(q in str(v).lower() for v in vals[:4]):
                continue
            tags = ("new",) if r.get("product_id") in self._session_ids[:1] else ()
            tv.insert("", "end", iid=str(r["product_id"]), values=vals, tags=tags)
            n += 1
        self.count_var.set("%d product%s" % (n, "" if n == 1 else "s"))

    # ── layout ────────────────────────────────────────────────
    def _build(self, C):
        CARD, PAGE = C["card_bg"], C["content_bg"]
        muted, ink = C["text_secondary"], C["text_primary"]

        # header
        hd = tk.Frame(self.frame, bg=PAGE)
        hd.pack(fill="x", padx=24, pady=(18, 12))
        left = tk.Frame(hd, bg=PAGE)
        left.pack(side="left")
        tk.Label(left, text="⚡  Quick Product Entry", font=("Segoe UI", 17, "bold"),
                 bg=PAGE, fg=ink).pack(anchor="w")
        tk.Label(left, text="Type a line · Enter goes to the next box · Enter on Sales Price "
                            "saves (Yes is the default) · Esc clears",
                 font=("Segoe UI", 9), bg=PAGE, fg=muted).pack(anchor="w")
        right = tk.Frame(hd, bg=PAGE)
        right.pack(side="right")
        self.show_var = tk.StringVar(value="all" if cfg.flag("quick_prod_show_all", True) else "new")
        for val, txt in (("all", "All products"), ("new", "New only (blank list)")):
            tk.Radiobutton(right, text=txt, value=val, variable=self.show_var,
                           command=self._show_changed, font=("Segoe UI", 9, "bold"),
                           bg=PAGE, fg=ink, activebackground=PAGE, selectcolor=CARD,
                           highlightthickness=0, cursor="hand2").pack(side="left", padx=(0, 10))
        tk.Button(right, text="📦  Full product window", command=self._open_full,
                  font=("Segoe UI", 9, "bold"), bg=CARD, fg=ink, relief="flat", bd=0,
                  padx=12, pady=6, cursor="hand2", highlightthickness=1,
                  highlightbackground=C.get("field_border", C["border"]),
                  activebackground=C.get("heading_bg", PAGE)).pack(side="left", padx=(6, 0))

        # the entry line (a white card)
        card = tk.Frame(self.frame, bg=CARD, highlightthickness=1,
                        highlightbackground=C["border"])
        card.pack(fill="x", padx=24)
        tk.Frame(card, bg=C["primary"], height=3).pack(fill="x")
        line = tk.Frame(card, bg=CARD)
        line.pack(fill="x", padx=16, pady=(10, 12))
        self._line = line

        def caps(col, text):
            tk.Label(line, text=text.upper(), font=("Segoe UI", 8, "bold"), bg=CARD,
                     fg=muted, anchor="w").grid(row=0, column=col, sticky="w",
                                                 padx=(0, 10), pady=(0, 4))

        fld = dict(relief="flat", bd=0, highlightthickness=1,
                   highlightbackground=C.get("field_border", C["border"]),
                   highlightcolor=C["primary"], bg=CARD, fg=ink,
                   insertbackground=C["primary"])
        F = ("Segoe UI", 11)

        self.code_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.unit_var = tk.StringVar(value=self._units[0] if self._units else "PCs")
        self.cat_var = tk.StringVar()
        self.pp_var = tk.StringVar()
        self.sp_var = tk.StringVar()

        caps(0, "Code")
        self.code_lbl = tk.Label(line, textvariable=self.code_var, font=("Segoe UI", 11, "bold"),
                                 bg=C.get("primary_light", PAGE), fg=C["primary"],
                                 width=9, anchor="w", padx=8, pady=5)
        self.code_lbl.grid(row=1, column=0, sticky="w", padx=(0, 10))
        caps(1, "Product Name *")
        self.name_e = tk.Entry(line, textvariable=self.name_var, font=F, width=34, **fld)
        self.name_e.grid(row=1, column=1, sticky="ew", padx=(0, 10), ipady=5)
        caps(2, "Unit")
        self.unit_cb = ttk.Combobox(line, textvariable=self.unit_var, values=self._units,
                                    font=F, width=9)
        self.unit_cb.grid(row=1, column=2, sticky="ew", padx=(0, 10), ipady=3)
        caps(3, "Category")
        self.cat_cb = ttk.Combobox(line, textvariable=self.cat_var, values=self._cat_names(),
                                   font=F, width=16)
        self.cat_cb.grid(row=1, column=3, sticky="ew", padx=(0, 10), ipady=3)
        caps(4, "Purchase Price")
        self.pp_e = tk.Entry(line, textvariable=self.pp_var, font=F, width=11, justify="right", **fld)
        self.pp_e.grid(row=1, column=4, sticky="ew", padx=(0, 10), ipady=5)
        caps(5, "Sales Price *")
        self.sp_e = tk.Entry(line, textvariable=self.sp_var, font=("Segoe UI", 11, "bold"),
                             width=11, justify="right", **fld)
        self.sp_e.grid(row=1, column=5, sticky="ew", padx=(0, 10), ipady=5)
        self.save_btn = tk.Button(line, text="✔  Save  ↵", command=self._save_line,
                                  font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white",
                                  activebackground=C.get("primary_dark", C["primary"]),
                                  activeforeground="white", relief="flat", bd=0, padx=14,
                                  pady=6, cursor="hand2")
        self.save_btn.grid(row=1, column=6, sticky="w", padx=(4, 6))
        tk.Button(line, text="Clear  Esc", command=self._new_line, font=("Segoe UI", 9, "bold"),
                  bg=CARD, fg=ink, relief="flat", bd=0, padx=10, pady=6, cursor="hand2",
                  highlightthickness=1, highlightbackground=C.get("field_border", C["border"]),
                  activebackground=C.get("heading_bg", PAGE)).grid(row=1, column=7, sticky="w")
        line.columnconfigure(1, weight=1)
        self.mode_var = tk.StringVar()
        tk.Label(line, textvariable=self.mode_var, font=("Segoe UI", 8, "bold"), bg=CARD,
                 fg=C["primary"], anchor="w").grid(row=2, column=0, columnspan=8, sticky="w",
                                                    pady=(6, 0))

        # key flow: Enter → next box; Enter on Sales Price → save
        order = [self.name_e, self.unit_cb, self.cat_cb, self.pp_e, self.sp_e]
        self._order = order
        for i, w in enumerate(order):
            w.bind("<Return>", lambda e, i=i: self._enter(i))
            w.bind("<KP_Enter>", lambda e, i=i: self._enter(i))
            w.bind("<Escape>", lambda e: (self._new_line(), "break")[1])
            w.bind("<Control-s>", lambda e: (self._save_line(), "break")[1])
            w.bind("<FocusIn>", lambda e, w=w: self._select_all(w), add="+")
        self.name_e.bind("<Down>", lambda e: (self._focus_list(), "break")[1])
        for w in (self.pp_e, self.sp_e):
            w.bind("<KeyRelease>", lambda e: self._show_margin(), add="+")

        # list
        lt = tk.Frame(self.frame, bg=PAGE)
        lt.pack(fill="x", padx=24, pady=(16, 8))
        tk.Label(lt, text="PRODUCTS", font=("Segoe UI", 8, "bold"), bg=PAGE, fg=muted).pack(side="left")
        self.count_var = tk.StringVar()
        tk.Label(lt, textvariable=self.count_var, font=("Segoe UI", 9), bg=PAGE,
                 fg=muted).pack(side="left", padx=(8, 0))
        self.search_var = tk.StringVar()
        se = tk.Entry(lt, textvariable=self.search_var, font=("Segoe UI", 10), width=28, **fld)
        se.pack(side="right", ipady=4)
        tk.Label(lt, text="🔍", bg=PAGE, fg=muted).pack(side="right", padx=(0, 4))
        self.search_var.trace_add("write", lambda *a: self._fill_tree())

        box = tk.Frame(self.frame, bg=CARD, highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        self.tree = ttk.Treeview(box, columns=[c[0] for c in COLS], show="headings",
                                 selectmode="browse")
        for k, head, w, anc in COLS:
            self.tree.heading(k, text=head, anchor=anc)
            self.tree.column(k, width=w, anchor=anc, stretch=(k == "name"))
        vsb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("new", background="#E7F8EF")
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())
        self.tree.bind("<Return>", lambda e: (self._edit_selected(), "break")[1])
        self.tree.bind("<Escape>", lambda e: (self._focus_name(), "break")[1])

        foot = tk.Frame(self.frame, bg=PAGE)
        foot.pack(fill="x", padx=24, pady=(0, 12))
        self.status_var = tk.StringVar(value="")
        self.status_lbl = tk.Label(foot, textvariable=self.status_var, font=("Segoe UI", 9),
                                   bg=PAGE, fg=C.get("success", "#12A15E"), anchor="w")
        self.status_lbl.pack(side="left", fill="x", expand=True)
        tk.Label(foot, text="Enter / double-click a row = change it in the top line",
                 font=("Segoe UI", 8), bg=PAGE, fg=muted).pack(side="right")

    # ── behaviour ─────────────────────────────────────────────
    def _status(self, text, err=False):
        try:
            self.status_var.set(text)
            self.status_lbl.configure(fg=self.C.get("danger", "#E5484D") if err
                                      else self.C.get("success", "#12A15E"))
        except Exception:
            pass

    @staticmethod
    def _select_all(w):
        try:
            w.after(1, lambda: (w.select_range(0, "end"), w.icursor("end")))
        except Exception:
            pass

    def _focus_name(self):
        try:
            self.name_e.focus_set()
        except Exception:
            pass

    def _focus_list(self):
        kids = self.tree.get_children()
        if kids:
            self.tree.focus_set()
            self.tree.selection_set(kids[0])
            self.tree.focus(kids[0])

    def _complete(self, var, values):
        """Typed 'bo' in a list box → 'Box' (first name that starts with it)."""
        typed = var.get().strip()
        if not typed:
            return
        for v in values:
            if str(v).lower() == typed.lower():
                var.set(v)
                return
        for v in values:
            if str(v).lower().startswith(typed.lower()):
                var.set(v)
                return

    def _enter(self, i):
        w = self._order[i]
        if w is self.unit_cb:
            self._complete(self.unit_var, self._units)
        elif w is self.cat_cb:
            self._complete(self.cat_var, self._cat_names())
        if w is self.name_e and not self.name_var.get().strip():
            self._status("Type the product name first.", err=True)
            return "break"
        if i + 1 < len(self._order):
            self._order[i + 1].focus_set()
        else:
            self._save_line()
        return "break"

    def _show_margin(self):
        pp, sp = _num(self.pp_var.get()), _num(self.sp_var.get())
        m = _margin(pp, sp)
        base = ("Changing %s" % self._edit_code) if self._edit_id else "New product"
        self.mode_var.set(base + (("   ·   margin %s %%" % m) if m else ""))

    def _new_line(self):
        """Empty top line for the next new product (Unit / Category stay)."""
        self._edit_id = None
        self._edit_code = None
        try:
            from modules.product_lookup import next_product_code
            code = next_product_code()
        except Exception:
            code = ""
        self.code_var.set(code or "auto")
        self.name_var.set("")
        self.pp_var.set("")
        self.sp_var.set("")
        self.mode_var.set("New product")
        try:
            self.save_btn.configure(text="✔  Save  ↵")
        except Exception:
            pass
        self._focus_name()
        return "break"

    def _show_changed(self):
        try:
            cfg.set("quick_prod_show_all", self.show_var.get() == "all")
            cfg.save_settings()
        except Exception:
            pass
        self._load_list()

    def _open_full(self):
        try:
            from ui.main_window import navigate
            navigate("products")
        except Exception:
            pass

    def _edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return
        pid = int(sel[0])
        r = next((x for x in self._rows if x.get("product_id") == pid), None)
        if not r:
            return
        self._edit_id = pid
        self._edit_code = r.get("product_code") or ""
        self.code_var.set(self._edit_code)
        self.name_var.set(r.get("product_name_en") or "")
        self.unit_var.set(r.get("unit_of_measure_en") or "")
        self.cat_var.set(r.get("category_name") or "")
        pp = float(r.get("purchase_price") or 0)
        self.pp_var.set(("%g" % pp) if pp else "")
        self.sp_var.set("%g" % float(r.get("unit_price") or 0))
        self.save_btn.configure(text="✔  Update  ↵")
        self._show_margin()
        self._focus_name()

    def _validate(self):
        name = self.name_var.get().strip()
        if cfg.flag("prod_name_upper", False):
            name = name.upper()
        if not name:
            self._status("Type the product name.", err=True)
            self.name_e.focus_set()
            return None
        sp = _num(self.sp_var.get())
        if sp is None or sp < 0:
            self._status("Type the sales price (a number).", err=True)
            self.sp_e.focus_set()
            return None
        pp = _num(self.pp_var.get())
        if self.pp_var.get().strip() and (pp is None or pp < 0):
            self._status("The purchase price is not a number.", err=True)
            self.pp_e.focus_set()
            return None
        unit = self.unit_var.get().strip() or "PCs"
        return {"name": name, "unit": unit, "cat": self.cat_var.get().strip(),
                "pp": pp or 0.0, "sp": sp}

    def _save_line(self):
        d = self._validate()
        if not d:
            return "break"
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit" if self._edit_id else "add"):
            return "break"
        top = self.frame.winfo_toplevel()
        warn = ""
        if d["pp"] and d["sp"] < d["pp"]:
            warn = "\n\n⚠ The sales price is LOWER than the purchase price."
        if not self._edit_id:
            try:
                same = db.execute_scalar(
                    "SELECT COUNT(*) FROM products WHERE product_name_en=?", (d["name"],))
            except Exception:
                same = 0
            if same:
                warn += "\n\n⚠ A product with this name already exists."
        what = "Update" if self._edit_id else "Save"
        ok = messagebox.askyesno(
            "%s product" % what,
            "%s this product?\n\n%s\n%s · %s\nPurchase %s   ·   Sales %s%s"
            % (what, d["name"], d["unit"], d["cat"] or "no category",
               _money(d["pp"]), _money(d["sp"]), warn),
            default="yes", parent=top)
        if not ok:
            self.sp_e.focus_set()
            return "break"
        try:
            pid = self._update(d) if self._edit_id else self._insert(d)
        except Exception as e:
            self._status("Not saved: %s" % str(e)[:160], err=True)
            messagebox.showerror("Not saved", str(e)[:400], parent=top)
            return "break"
        if pid:
            if pid in self._session_ids:
                self._session_ids.remove(pid)
            self._session_ids.insert(0, pid)
        self._load_list()
        if pid:
            try:
                self.tree.see(str(pid))
            except Exception:
                pass
        self._status("✔ %s  %s  —  %s" % ("Updated" if self._edit_id else "Saved",
                                         self.code_var.get(), d["name"]))
        self._new_line()
        return "break"

    def _insert(self, d):
        from modules.products_import import import_rows
        from modules.product_lookup import next_product_code
        code = self.code_var.get().strip()
        if not code or code == "auto":
            code = next_product_code()
        else:
            try:                                   # taken meanwhile (another PC)?
                if db.execute_scalar("SELECT COUNT(*) FROM products WHERE product_code=?", (code,)):
                    code = next_product_code()
            except Exception:
                pass
        self.code_var.set(code)
        cat_id = self._cat_id(d["cat"]) if d["cat"] else None
        row = {"product_code": code, "product_name_en": d["name"], "product_type": "product",
               "unit_price": d["sp"], "purchase_price": d["pp"],
               "unit_of_measure_en": d["unit"], "unit_of_measure_ar": d["unit"],
               "vat_code": "S", "category_name": d["cat"] if cat_id else "",
               "track_inventory": "1", "list_in_sales": "1", "list_in_purchase": "1",
               "is_active": "1"}
        ins, upd, errs = import_rows([row])
        if not ins and not upd:
            raise RuntimeError("; ".join(errs) or "the product was not saved")
        pid = db.execute_scalar("SELECT product_id FROM products WHERE product_code=?", (code,))
        try:
            from modules.doc_actions import audit
            audit("add", "product", pid, d["name"])
        except Exception:
            pass
        if errs:
            self._status("Saved, with a note: %s" % errs[0][:140], err=True)
        return pid

    def _update(self, d):
        pid = self._edit_id
        cat_id = self._cat_id(d["cat"]) if d["cat"] else None
        try:
            from modules import price_watch as _pw
            before = _pw.snapshot([pid])
        except Exception:
            _pw, before = None, None
        try:
            db.execute("UPDATE products SET product_name_en=?, unit_of_measure_en=?, category_id=?, "
                       "purchase_price=?, unit_price=?, updated_at=GETDATE() WHERE product_id=?",
                       (d["name"], d["unit"], cat_id, d["pp"], d["sp"], pid))
        except Exception:                          # older database: no purchase_price column
            db.execute("UPDATE products SET product_name_en=?, unit_of_measure_en=?, category_id=?, "
                       "unit_price=?, updated_at=GETDATE() WHERE product_id=?",
                       (d["name"], d["unit"], cat_id, d["sp"], pid))
        # the base unit (factor 1) carries the same unit name and prices
        try:
            db.execute("UPDATE product_units SET unit_name_en=?, selling_price=?, purchase_price=? "
                       "WHERE product_id=? AND conversion_factor=1", (d["unit"], d["sp"], d["pp"], pid))
        except Exception:
            try:
                db.execute("UPDATE product_units SET unit_name_en=?, selling_price=? "
                           "WHERE product_id=? AND conversion_factor=1", (d["unit"], d["sp"], pid))
            except Exception:
                pass
        try:
            if before is not None:
                before[("_ids",)] = [pid]
                _pw.record(before, "quick entry", new_product=False)
        except Exception:
            pass
        try:
            from modules.doc_actions import audit
            audit("edit", "product", pid, d["name"])
        except Exception:
            pass
        return pid
