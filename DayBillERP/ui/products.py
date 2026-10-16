# ============================================================
# Saudi Arabia ERP - Products / Services Module
# Full CRUD: List + Add + Edit + Delete
# Categories | VAT Rates | Inventory Tracking | Barcode
# Bilingual Arabic/English
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t, is_rtl
from config.database import db


# ─────────────────────────────────────────────────────────────
# PRODUCTS LIST VIEW
# ─────────────────────────────────────────────────────────────
class ProductsView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self._all_data  = []
        self._categories = []
        self._vat_cats   = []

        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        self._load_lookups()
        self._build_topbar(C)
        self._build_stats_bar(C)
        self._build_search_bar(C)
        self._build_table(C)
        self._load_products()
        self._bind_shortcuts()

    # ── Lookups ───────────────────────────────────────────────
    def _load_lookups(self):
        try:
            self._categories = db.fetchall(
                "SELECT category_id, category_name_en, category_name_ar "
                "FROM product_categories WHERE is_active=1 ORDER BY category_name_en"
            )
            self._vat_cats = db.fetchall(
                "SELECT vat_category_id, category_code, category_name_en, vat_rate "
                "FROM vat_categories WHERE is_active=1 ORDER BY vat_rate DESC"
            )
        except Exception:
            self._categories = []
            self._vat_cats   = []

    # ── Top Bar ───────────────────────────────────────────────
    def _build_topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(18, 0))
        tk.Label(bar, text=f"📦  {t('nav.products')}",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        # ── Windows-style command bar ─────────────────────────
        cmd = tk.Frame(self.frame, bg=C["card_bg"],
                       highlightbackground=C["border"], highlightthickness=1)
        cmd.pack(fill="x", padx=24, pady=(12, 0))
        inner = tk.Frame(cmd, bg=C["card_bg"])
        inner.pack(fill="x", padx=8, pady=6)

        def tool(parent, text, cmd_fn, primary=False, danger=False, side="left"):
            if primary:
                bg, fg = C["primary"], "white"
            elif danger:
                bg, fg = C["card_bg"], C["danger"]
            else:
                bg, fg = C["card_bg"], C["text_primary"]
            b = tk.Button(parent, text=text, font=("Segoe UI", 9,
                          "bold" if primary else "normal"),
                          bg=bg, fg=fg, relief="flat", padx=14, pady=8,
                          cursor="hand2", activebackground=C["primary_light"],
                          command=cmd_fn)
            b.pack(side=side, padx=2)
            return b

        def sep(parent):
            tk.Frame(parent, bg=C["border"], width=1).pack(
                side="left", fill="y", padx=6, pady=4)

        tool(inner, "＋  New", self._open_add_form, primary=True)
        tool(inner, "✏  Edit", self._open_edit_form)
        tool(inner, "💲  Bulk Rate", self._bulk_rate_edit)
        tool(inner, "🏷  Make Offer", self._make_offer)
        tool(inner, "🗑  Delete", self._delete_product, danger=True)
        sep(inner)
        tool(inner, "🔄  Refresh", self._load_products)
        sep(inner)
        tool(inner, "🧹  Clean-up", self._ai_cleanup)
        tool(inner, "🧾  Supplier Invoice (AI)", self._ai_invoice_import)
        # right-aligned secondary actions
        tool(inner, "🗂  Categories", self._manage_categories, side="right")
        tool(inner, "📊  Report", self._report_pdf, side="right")
        tool(inner, "📥  Export", self._export_excel, side="right")
        tool(inner, "📤  Import", self._import_excel, side="right")

        tk.Label(self.frame, text="Tips:  Double-click or F2 = Edit · "
                 "Insert = New · Delete = Remove · F5 = Refresh · Ctrl+F = Search",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=26, pady=(4, 0))

    def _bind_shortcuts(self):
        """Keys work only while THIS screen is on show (they used to stay
        bound to the main window after leaving Products)."""
        w = self.frame.winfo_toplevel()

        def only_here(fn):
            def h(e):
                try:
                    if not self.frame.winfo_exists() or not self.frame.winfo_ismapped():
                        return None
                    if e.widget.winfo_toplevel() is not w:
                        return None
                except Exception:
                    return None
                fn()
                return "break"
            return h
        for seq, fn in (("<F2>", self._open_edit_form), ("<F5>", self._load_products),
                        ("<Insert>", self._open_add_form),
                        ("<Control-f>", self._focus_search)):
            w.bind(seq, only_here(fn))
        if hasattr(self, "tree"):
            self.tree.bind("<Return>", lambda e=None: self._open_edit_form())

    def _focus_search(self):
        try:
            self.search_entry.focus_set()
        except Exception:
            pass

    # ── Stats Bar ─────────────────────────────────────────────
    def _build_stats_bar(self, C):
        self.stats_frame = tk.Frame(self.frame, bg=C["content_bg"])
        self.stats_frame.pack(fill="x", padx=24, pady=(14, 0))

    def _refresh_stats(self, data):
        C = cfg.theme()
        for w in self.stats_frame.winfo_children():
            w.destroy()

        total    = len(data)
        products = sum(1 for r in data if r.get("product_type") == "product")
        services = total - products
        low_stock= sum(1 for r in data
                       if r.get("track_inventory") and
                       float(r.get("stock_quantity", 0)) <= float(r.get("reorder_level", 0) or 0))

        stats = [
            ("📦", "Total Items",    str(total),    C["primary"]),
            ("🛒", "Products",       str(products), C["info"]),
            ("🔧", "Services",       str(services), C["success"]),
            ("⚠️", "Low Stock",      str(low_stock),C["warning"]),
        ]
        for icon, label, val, color in stats:
            card = tk.Frame(self.stats_frame, bg=C["card_bg"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 10), ipadx=12, ipady=4)
            tk.Label(card, text=f"{icon}  {label}",
                     font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=val, font=("Segoe UI", 16, "bold"),
                     bg=C["card_bg"], fg=color).pack(anchor="w", padx=8, pady=(0, 6))

    # ── Search + Filter Bar ───────────────────────────────────
    def _build_search_bar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(14, 0))

        # Search input
        sf = tk.Frame(bar, bg="white",
                      highlightbackground=C["border"], highlightthickness=1)
        sf.pack(side="left")
        tk.Label(sf, text="🔍", font=("Segoe UI Emoji", 11),
                 bg="white", fg=C["text_secondary"]).pack(side="left", padx=(10, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._filter_table())
        self.search_entry = tk.Entry(sf, textvariable=self.search_var,
                 font=("Segoe UI", 10), bg="white", relief="flat",
                 width=30, fg=C["text_primary"])
        self.search_entry.pack(side="left", ipady=7, padx=(0, 10))
        self.search_entry.bind("<Return>", self._search_enter)
        self.search_entry.bind("<KP_Enter>", self._search_enter)
        self.search_entry.bind("<Down>", lambda e=None: (self._focus_first_row(), "break")[1])
        tk.Label(bar, text="name · code · Arabic · alias · any barcode  (Enter = open)",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(6, 0))

        # Type filter
        self.ptype_var = tk.StringVar(value="All")
        tf = tk.Frame(bar, bg=C["content_bg"])
        tf.pack(side="left", padx=12)
        tk.Label(tf, text="Type:", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        for val in ["All", "Product", "Service"]:
            tk.Radiobutton(tf, text=val, variable=self.ptype_var, value=val,
                           font=("Segoe UI", 9), bg=C["content_bg"],
                           activebackground=C["content_bg"],
                           command=self._filter_table).pack(side="left", padx=4)

        # Category filter
        cat_frame = tk.Frame(bar, bg=C["content_bg"])
        cat_frame.pack(side="left", padx=8)
        tk.Label(cat_frame, text="Category:", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        self.cat_var = tk.StringVar(value="All")
        cat_options = ["All"] + [c["category_name_en"] for c in self._categories]
        cat_cb = ttk.Combobox(cat_frame, textvariable=self.cat_var,
                               values=cat_options, state="readonly",
                               width=14, font=("Segoe UI", 9))
        cat_cb.pack(side="left", padx=4)
        cat_cb.bind("<<ComboboxSelected>>", lambda e=None: self._filter_table())

        # Active only
        self.active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="Active only",
                       variable=self.active_var, command=self._filter_table,
                       font=("Segoe UI", 9), bg=C["content_bg"],
                       fg=C["text_secondary"]).pack(side="left", padx=8)

        # Low stock only
        self.lowstock_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="⚠️ Low Stock",
                       variable=self.lowstock_var, command=self._filter_table,
                       font=("Segoe UI", 9), bg=C["content_bg"],
                       fg=C["warning"]).pack(side="left")
        # POS favourites only
        self.favonly_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="⭐ POS favourites",
                       variable=self.favonly_var, command=self._filter_table,
                       font=("Segoe UI", 9), bg=C["content_bg"],
                       fg="#B7950B").pack(side="left", padx=(8, 0))

        # Count
        self.count_var = tk.StringVar()
        tk.Label(bar, textvariable=self.count_var,
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="right")

    # ── Data Table ────────────────────────────────────────────
    def _build_table(self, C):
        wrapper = tk.Frame(self.frame, bg=C["content_bg"])
        wrapper.pack(fill="both", expand=True, padx=24, pady=(10, 24))

        card = tk.Frame(wrapper, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)

        cols    = ("fav", "code", "name_en", "name_ar", "type", "category",
                   "price", "vat", "stock", "unit", "status")
        headers = {
            "fav":      ("⭐",           34,  "center"),
            "code":     ("Code",         80,  "center"),
            "name_en":  ("Name (EN)",    160, "w"),
            "name_ar":  ("الاسم (AR)",   130, "e"),
            "type":     ("Type",         70,  "center"),
            "category": ("Category",     110, "center"),
            "price":    ("Unit Price",   100, "e"),
            "vat":      ("VAT",          70,  "center"),
            "stock":    ("Stock",        70,  "e"),
            "unit":     ("Unit",         70,  "center"),
            "status":   ("Status",       70,  "center"),
        }

        style = ttk.Style()
        style.configure("Prod.Treeview",
                         background="white", foreground=C["text_primary"],
                         fieldbackground="white", rowheight=34,
                         font=("Segoe UI", 9))
        style.configure("Prod.Treeview.Heading",
                         background=C["content_bg"], foreground=C["text_secondary"],
                         font=("Segoe UI", 9, "bold"), relief="flat", padding=(8, 6))
        style.map("Prod.Treeview",
                  background=[("selected", C.get("select_bg", C["primary"]))],
                  foreground=[("selected", C.get("select_fg", "white"))])

        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(card, orient="horizontal")
        hsb.pack(side="bottom", fill="x")

        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                  style="Prod.Treeview",
                                  yscrollcommand=vsb.set,
                                  xscrollcommand=hsb.set)
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        for col in cols:
            h, w, anchor = headers[col]
            self.tree.heading(col, text=h,
                              command=lambda c=col: self._sort_col(c))
            self.tree.column(col, width=w, anchor=anchor,
                             minwidth=30 if col == "fav" else 50,
                             stretch=(col != "fav"))

        self.tree.pack(fill="both", expand=True)

        # Tags
        self.tree.tag_configure("product",  background="#EFF6FF")
        self.tree.tag_configure("service",  background="#F0FDF4")
        self.tree.tag_configure("lowstock", background="#FEF9C3")
        self.tree.tag_configure("inactive", foreground="#9CA3AF")
        self.tree.tag_configure("even",     background="#FAFAFA")

        # Events
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Delete>",   lambda e=None: self._delete_product())
        self._build_context_menu()

        # Bottom bar
        self._build_bottom_bar(C, wrapper)

    def _build_bottom_bar(self, C, parent):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(6, 0))

        tk.Button(bar, text=f"✏️  {t('common.edit')}",
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._open_edit_form).pack(side="left", padx=(0, 6))

        tk.Button(bar, text=f"🗑  {t('common.delete')}",
                  font=("Segoe UI", 9), bg="#FEF2F2", fg=C["danger"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._delete_product).pack(side="left", padx=(0, 6))

        tk.Button(bar, text="📋  Adjust Stock",
                  font=("Segoe UI", 9), bg="#FFFBEB", fg=C["warning"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._adjust_stock).pack(side="left")

        tk.Button(bar, text="🏷  Labels",
                  font=("Segoe UI", 9), bg="#EAF1FE", fg=C["primary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._print_labels).pack(side="left", padx=(6, 0))

        tk.Button(bar, text="🔄  Refresh",
                  font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load_products).pack(side="right")

    def _build_context_menu(self):
        C = cfg.theme()
        self.ctx = tk.Menu(self.tree, tearoff=0, bg="white",
                            fg=C["text_primary"], font=("Segoe UI", 9))
        self.ctx.add_command(label="✏️  Edit Product",    command=self._open_edit_form)
        self.ctx.add_command(label="📋  Adjust Stock",    command=self._adjust_stock)
        self.ctx.add_command(label="⭐  Add / remove POS favourite",
                             command=self._toggle_favourite)
        self.ctx.add_command(label="🏷  Make offer (−%, half price, buy 1 get 1 …)",
                             command=self._make_offer)
        self.ctx.add_separator()
        self.ctx.add_command(label="🗑  Delete",          command=self._delete_product,
                              foreground=C["danger"])
        def popup(e):
            row = self.tree.identify_row(e.y)
            if row and row not in self.tree.selection():
                self.tree.selection_set(row)
            self.ctx.post(e.x_root, e.y_root)
        self.tree.bind("<Button-3>", popup)

    def _make_offer(self):
        """🏷 An offer for the selected product(s): −20 %, half price,
        special price, buy 1 get 1 … with start / end date and time."""
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Make offer", "Select one or more products first "
                                   "(Ctrl / Shift + click for many).")
            return
        try:
            ids = [int(i) for i in sel]
        except ValueError:
            return
        from ui.offers import open_offer_for_products
        open_offer_for_products(self.frame, ids)

    # ── Load / Filter ─────────────────────────────────────────
    def _load_products(self):
        try:
            self._all_data = db.fetchall(
                "SELECT p.*, "
                "ISNULL(pc.category_name_en,'—') AS category_name, "
                "ISNULL(vc.category_code,'S') AS vat_code, "
                "ISNULL(vc.vat_rate,15) AS vat_rate "
                "FROM products p "
                "LEFT JOIN product_categories pc ON p.category_id = pc.category_id "
                "LEFT JOIN vat_categories vc ON p.vat_category_id = vc.vat_category_id "
                "ORDER BY p.product_name_en"
            )
        except Exception as e:
            self._all_data = []
            messagebox.showerror("DB Error", str(e))
        self._filter_table()

    def _filter_table(self):
        query    = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        ptype    = self.ptype_var.get()           if hasattr(self, "ptype_var") else "All"
        cat      = self.cat_var.get()             if hasattr(self, "cat_var") else "All"
        active   = self.active_var.get()           if hasattr(self, "active_var") else True
        lowstock = self.lowstock_var.get()         if hasattr(self, "lowstock_var") else False

        favonly  = self.favonly_var.get()          if hasattr(self, "favonly_var") else False
        # barcodes of units / extra barcodes can match too
        via_bc = {}
        if query:
            try:
                from modules.product_lookup import barcode_product_ids
                via_bc = barcode_product_ids(query)
            except Exception:
                via_bc = {}
        self._via_bc = via_bc

        filtered = []
        for row in self._all_data:
            if active and not row.get("is_active"):
                continue
            if favonly and not row.get("is_favorite"):
                continue
            if ptype != "All" and row.get("product_type", "").lower() != ptype.lower():
                continue
            if cat != "All" and row.get("category_name", "") != cat:
                continue
            if lowstock:
                if not (row.get("track_inventory") and
                        float(row.get("stock_quantity", 0)) <=
                        float(row.get("reorder_level") or 0)):
                    continue
            if query:
                searchable = " ".join(str(row.get(k) or "") for k in (
                    "product_code", "product_name_en", "product_name_ar",
                    "barcode", "alias_name")).lower()
                if query not in searchable and row["product_id"] not in via_bc:
                    continue
            filtered.append(row)

        self._populate_table(filtered)
        self._refresh_stats(self._all_data)
        if hasattr(self, "count_var"):
            self.count_var.set(f"{len(filtered)} record(s)")

    def _populate_table(self, data):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(data):
            ptype = row.get("product_type", "product")
            stock = row.get("stock_quantity", 0)
            reorder = row.get("reorder_level") or 0
            is_low  = row.get("track_inventory") and float(stock) <= float(reorder)
            active  = row.get("is_active", 1)
            vat_rate = row.get("vat_rate", 15)
            vat_code = row.get("vat_code", "S")

            tags = []
            if not active:
                tags.append("inactive")
            elif is_low:
                tags.append("lowstock")
            elif ptype == "product":
                tags.append("product" if i % 2 == 0 else "even")
            else:
                tags.append("service" if i % 2 == 0 else "even")

            stock_disp = (
                f"{float(stock):,.2f}" if row.get("track_inventory")
                else "—"
            )
            status = "✅ Active" if active else "⛔ Inactive"
            if is_low:
                status = "⚠️ Low Stock"

            self.tree.insert("", "end",
                iid=str(row["product_id"]),
                values=(
                    "⭐" if row.get("is_favorite") else "",
                    row.get("product_code", ""),
                    row.get("product_name_en", ""),
                    row.get("product_name_ar", ""),
                    "📦 Product" if ptype == "product" else "🔧 Service",
                    row.get("category_name", "—"),
                    f"{float(row.get('unit_price', 0)):,.2f}",
                    f"{vat_code} ({vat_rate}%)",
                    stock_disp,
                    row.get("unit_of_measure_en", "Unit"),
                    status
                ),
                tags=tuple(tags)
            )

    def _sort_col(self, col):
        data = [(self.tree.set(c, col), c) for c in self.tree.get_children("")]
        data.sort(key=lambda x: x[0].lower())
        for i, (_, child) in enumerate(data):
            self.tree.move(child, "", i)

    def _on_double(self, e):
        if self.tree.identify_region(e.x, e.y) == "heading":
            return
        if self.tree.identify_column(e.x) == "#1" and self.tree.identify_row(e.y):
            self.tree.selection_set(self.tree.identify_row(e.y))
            self._toggle_favourite()      # double-click the ⭐ cell = toggle
            return
        self._open_edit_form()

    def _focus_first_row(self):
        ch = self.tree.get_children()
        if ch:
            self.tree.focus_set(); self.tree.selection_set(ch[0]); self.tree.focus(ch[0])

    def _search_enter(self, _e=None):
        """Enter in the search box: open the product for editing when the
        search points at exactly one product (scan a barcode → Enter)."""
        q = self.search_var.get().strip().lower()
        ch = self.tree.get_children()
        pick = None
        if len(ch) == 1:
            pick = ch[0]
        elif q:
            for r in self._all_data:
                if str(r["product_id"]) in ch and q in (
                        str(r.get("product_code", "")).lower(),
                        str(r.get("barcode", "")).lower(),
                        str(getattr(self, "_via_bc", {}).get(r["product_id"], "")).lower()):
                    pick = str(r["product_id"]); break
        if pick:
            self.tree.selection_set(pick); self.tree.see(pick)
            self._open_edit_form()
        elif ch:
            self._focus_first_row()
        return "break"

    def _toggle_favourite(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return False
        """⭐ POS favourite on/off for the selected product(s)."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a product first.")
            return
        ids = [int(i) for i in sel]
        rows = {r["product_id"]: r for r in self._all_data}
        turn_on = not all(rows.get(i, {}).get("is_favorite") for i in ids)
        try:
            ph = ",".join("?" * len(ids))
            db.execute(f"UPDATE products SET is_favorite=? WHERE product_id IN ({ph})",
                       (1 if turn_on else 0, *ids))
        except Exception as e:
            messagebox.showerror("POS favourite",
                                 "Could not save (restart DayBill once so the database "
                                 f"update runs).\n\n{str(e)[:200]}")
            return
        for i in ids:
            if i in rows:
                rows[i]["is_favorite"] = 1 if turn_on else 0
        self._filter_table()
        for i in ids:
            if self.tree.exists(str(i)):
                self.tree.selection_add(str(i))
        try:
            from ui.fluent_widgets import show_toast
            show_toast(self.frame.winfo_toplevel(),
                       ("⭐ Added to" if turn_on else "Removed from") +
                       f" POS favourites ({len(ids)})", kind="success")
        except Exception:
            pass

    # ── CRUD ──────────────────────────────────────────────────
    def _ai_cleanup(self):
        from ui.product_ai_ui import CleanupDialog
        CleanupDialog(self.frame, on_change=self._load_products)

    def _ai_invoice_import(self):
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "add"):
            return
        from ui.product_ai_ui import InvoiceImportDialog
        InvoiceImportDialog(self.frame, on_change=self._load_products)

    def _get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a product first.")
            return None
        return int(sel[0])

    def _open_add_form(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "add"):
            return False
        # ➕ New Product opens the SAME big tabbed ProductForm used for
        # editing — one consistent product window for add + edit (the
        # small Quick form used to open as a confusing second window).
        ProductForm(self.frame, product_id=None,
                    categories=self._categories, vat_cats=self._vat_cats,
                    on_save=self._load_products)

    def _open_edit_form(self):
        pid = self._get_selected_id()
        if pid:
            ProductForm(self.frame, product_id=pid,
                        categories=self._categories, vat_cats=self._vat_cats,
                        on_save=self._load_products)

    def _delete_product(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "delete"):
            return False
        pid = self._get_selected_id()
        if not pid:
            return
        name = self.tree.item(str(pid))["values"][1]
        if not messagebox.askyesno(t("common.warning"),
                                   f"{t('common.confirm_delete')}\n\n{name}"):
            return
        try:
            used = db.execute_scalar(
                "SELECT COUNT(*) FROM sales_invoice_lines WHERE product_id=?", (pid,))
            if used and used > 0:
                messagebox.showerror(t("common.error"),
                    f"Cannot delete. Product used in {used} invoice line(s).\n"
                    "Deactivate the product instead.")
                return
            db.execute("DELETE FROM products WHERE product_id=?", (pid,))
            messagebox.showinfo(t("common.success"), f"'{name}' deleted.")
            self._load_products()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))


    def _print_labels(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "print"):
            return False
        try:
            from ui.label_printer import open_window
            sel = []
            try:
                for iid in self.tree.selection():
                    sel.append(int(iid))
            except Exception:
                pass
            open_window(self.frame, sel)
        except Exception as e:
            messagebox.showerror("Labels", str(e)[:200])

    def _adjust_stock(self):
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "add"):
            return False
        pid = self._get_selected_id()
        if not pid:
            return
        row = db.fetchone(
            "SELECT product_name_en, stock_quantity, track_inventory "
            "FROM products WHERE product_id=?", (pid,))
        if not row:
            return
        if not row.get("track_inventory"):
            messagebox.showinfo("Info",
                "Inventory tracking is disabled for this product.\n"
                "Enable it in the product form first.")
            return
        StockAdjustDialog(self.frame, pid, row, on_save=self._load_products)

    def _bulk_rate_edit(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return False
        try:
            from modules import permissions as _perm
            if not _perm.can("products", "edit"):
                messagebox.showwarning("Access Denied",
                                       "You don't have permission to edit prices.")
                return
        except Exception:
            pass
        BulkRateDialog(self.frame, on_save=self._load_products)

    def _manage_categories(self):
        from modules import permissions as _pm
        if not _pm.allowed("categories", "view"):
            return False
        CategoryManagerDialog(self.frame, on_close=self._load_lookups)

    def _import_excel(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "add"):
            return False
        """Bulk import products from an Excel file (all fields)."""
        from tkinter import filedialog
        C = cfg.theme()
        d = tk.Toplevel(self.frame)
        d.bind("<Escape>", lambda e=None: d.destroy())
        d.title("Import Products from Excel")
        d.geometry("440x300")
        d.configure(bg=C["content_bg"])
        d.grab_set()
        d.update_idletasks()
        sw, sh = d.winfo_screenwidth(), d.winfo_screenheight()
        d.geometry(f"440x300+{(sw-440)//2}+{(sh-300)//2}")

        tk.Label(d, text="📤  Bulk Import Products",
                 font=("Segoe UI", 14, "bold"), bg=C["primary"], fg="white",
                 pady=12).pack(fill="x")
        tk.Label(d, text="Step 1 — download the template, fill in your products,\n"
                 "then Step 2 — choose the file to import.\n\n"
                 "Existing products (same code) are updated; new ones are added.",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"], justify="left").pack(padx=20, pady=14)

        def dl_template():
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                initialfile="DayBill_Products_Template.xlsx")
            if not path:
                return
            try:
                from modules.products_import import write_template
                write_template(path)
                messagebox.showinfo("Template Saved",
                    f"Template saved:\n{path}\n\nFill it in, then click Choose File.")
                try:
                    os.startfile(path)
                except Exception:
                    pass
            except ImportError:
                messagebox.showerror("Missing Library", "pip install openpyxl")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def choose_file():
            path = filedialog.askopenfilename(
                filetypes=[("Excel", "*.xlsx *.xlsm"), ("All", "*.*")])
            if not path:
                return
            try:
                from modules.products_import import read_rows, import_rows
                rows = read_rows(path)
                if not rows:
                    messagebox.showwarning("Empty", "No product rows found.")
                    return
                if not messagebox.askyesno("Confirm Import",
                    f"Found {len(rows)} product rows.\n\nImport now?"):
                    return
                ins, upd, errs = import_rows(rows)
                msg = f"✅ Imported.\n\nNew: {ins}\nUpdated: {upd}"
                if errs:
                    msg += f"\nErrors: {len(errs)}\n\n" + "\n".join(errs[:8])
                    if len(errs) > 8:
                        msg += f"\n…and {len(errs)-8} more."
                messagebox.showinfo("Import Result", msg)
                d.destroy()
                self._load_products()
            except ImportError:
                messagebox.showerror("Missing Library", "pip install openpyxl")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))

        btns = tk.Frame(d, bg=C["content_bg"]); btns.pack(pady=10)
        tk.Button(btns, text="⬇ Download Template", font=("Segoe UI", 10),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=14, pady=8, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=dl_template).pack(side="left", padx=6)
        tk.Button(btns, text="📂 Choose File & Import", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=8,
                  cursor="hand2", command=choose_file).pack(side="left", padx=6)

    def _report_pdf(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "print"):
            return False
        """Printable product list PDF of exactly what the grid shows
        (search / category filters applied)."""
        try:
            from modules.doc_actions import tree_rows
            from modules.report_export import export_pdf
            headers = ["Fav", "Code", "Name (EN)", "Name (AR)", "Type", "Category",
                       "Unit Price", "VAT", "Stock", "Unit", "Status"]
            # PDF fonts have no ⭐ / emoji glyphs — plain text instead
            rows = []
            for r in tree_rows(self.tree):
                r = ["Yes" if (r and r[0]) else ""] + [
                    str(v).replace("📦 ", "").replace("🔧 ", "").replace("✅ ", "")
                          .replace("⛔ ", "").replace("⚠️ ", "") for v in r[1:]]
                rows.append(r)
            export_pdf(self.frame, "Product_List", headers, rows,
                       title="Product List",
                       subtitle=f"{len(rows)} products")
        except Exception as e:
            messagebox.showerror("Report", str(e)[:300])

    def _export_excel(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "export"):
            return False
        try:
            import openpyxl
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="Products.xlsx")
            if not path:
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Products"
            ws.append(["POS Fav", "Code", "Name (EN)", "Name (AR)", "Type",
                        "Category", "Unit Price", "VAT", "Stock", "Unit", "Status"])
            for child in self.tree.get_children():
                vals = list(self.tree.item(child)["values"])
                vals[0] = "Yes" if vals and vals[0] else ""
                ws.append(vals)
            wb.save(path)
            messagebox.showinfo(t("common.success"), f"Exported:\n{path}")
        except ImportError:
            messagebox.showerror("Error", "pip install openpyxl")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))


# ─────────────────────────────────────────────────────────────
# PRODUCT FORM (Add / Edit)
# ─────────────────────────────────────────────────────────────
from ui.fluent_widgets import (RoundedButton, ToggleSwitch, Accordion, PageNav,
                               show_toast, mark_invalid, clear_invalid,
                               bind_enter_navigation, labeled_toggle)


class ProductForm:
    def __init__(self, parent, product_id=None, categories=None,
                 vat_cats=None, on_save=None):
        self.parent      = parent
        self.product_id  = product_id
        self.categories  = categories or []
        self.vat_cats    = vat_cats or []
        # opened from another screen without the lists → read them here,
        # so the VAT / category boxes never show (and save) blank
        if not self.categories:
            try:
                self.categories = db.fetchall(
                    "SELECT category_id, category_name_en, category_name_ar "
                    "FROM product_categories WHERE is_active=1 "
                    "ORDER BY category_name_en") or []
            except Exception:
                self.categories = []
        if not self.vat_cats:
            try:
                self.vat_cats = db.fetchall(
                    "SELECT vat_category_id, category_code, category_name_en, vat_rate "
                    "FROM vat_categories WHERE is_active=1 ORDER BY vat_rate DESC") or []
            except Exception:
                self.vat_cats = []
        self.on_save     = on_save
        self.fields      = {}
        self._loaded_as_edit = product_id is not None
        self._build_window()
        if product_id:
            self._load_data()

    GEOM_KEY = "product_form_geometry_v524"     # new key: old full-screen sizes are not reused

    def _remember_geometry(self):
        """Remember the window size/position the user left it at."""
        try:
            if self.win.state() == "normal":
                cfg.set(self.GEOM_KEY, self.win.geometry())
                cfg.save_settings()
        except Exception:
            pass

    BASE_SIZE = (860, 500)      # at 100 % text; grows with Settings ▸ Text size
    MIN_SIZE = (720, 460)

    def _saved_geometry(self):
        """The size/position the user last left the window at (real screen
        pixels), or None."""
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        saved = str(cfg.get(self.GEOM_KEY, "") or "")
        m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", saved)
        if m:
            w, h, x, y = map(int, m.groups())
            if 600 <= w <= sw - 40 and 420 <= h <= sh - 60 and 0 <= x < sw - 100 and 0 <= y < sh - 100:
                return f"{w}x{h}+{x}+{y}"
        return None

    def _initial_geometry(self):
        """A normal-size window in the middle of the screen (not full
        screen). The app Text size makes it bigger together with the text."""
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = self.BASE_SIZE
        return f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}"

    def _build_window(self):
        C = cfg.theme()
        self.C = C
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        is_edit = self.product_id is not None
        title   = "Edit Product" if is_edit else "Add Product / Service"

        self.win = tk.Toplevel()
        self.win.withdraw()                    # no flash while building
        self.win.bind("<Escape>", lambda e=None: self._close())
        self.win.protocol("WM_DELETE_WINDOW", self._close)
        self.win.title(title)
        try:                                   # stays on top of DayBill, one taskbar entry
            self.win.transient(self.parent.winfo_toplevel())
        except Exception:
            pass
        self.win._keep_size = True     # its own size: never auto-grown / maximized
        self.win.minsize(*self.MIN_SIZE)
        saved = self._saved_geometry()
        if saved:                      # already real screen pixels: not grown again
            self.win._no_zoom = True
            self.win.geometry(saved)
            self.win._no_zoom = False
        else:
            self.win.geometry(self._initial_geometry())
        self.win.resizable(True, True)
        self.win.after(10, self.win.deiconify)
        self.win.configure(bg=C["content_bg"])
        self.win.grab_set()

        # Header — slim app-style strip
        hdr = tk.Frame(self.win, bg=C["primary"], height=40)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        icon = "✏️" if is_edit else "➕"
        self._hdr_title = tk.Label(hdr, text=f"{icon}  {title}",
                                   font=("Segoe UI", 12, "bold"),
                                   bg=C["primary"], fg="white")
        self._hdr_title.pack(side="left", padx=16)

        # Footer FIRST so it always stays visible at the bottom (no scroll)
        self._build_footer(C)

        # ── Product search bar (barcode / code / name / alias / Arabic),
        #    autocomplete — loads an existing product straight into this
        #    same window (add + edit + search in one screen). ──
        self._build_search_bar(C)

        # ── Body: PAGES (tabs) — no scrolling. Every page is two columns
        #    and fits the window:  Basic · Price & VAT · Stock ·
        #    Units & Barcodes · More (suppliers, history, images, notes) ──
        outer = tk.Frame(self.win, bg=C["content_bg"])
        outer.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        self._pagenav = PageNav(outer, C)
        self._pagenav.frame.pack(fill="both", expand=True)

        def two_cols(page):
            page.columnconfigure(0, weight=1, uniform="pc")
            page.columnconfigure(1, weight=1, uniform="pc")
            page.rowconfigure(0, weight=1)
            left = tk.Frame(page, bg=C["content_bg"])
            right = tk.Frame(page, bg=C["content_bg"])
            left.grid(row=0, column=0, sticky="nsew", padx=(4, 6), pady=(6, 8))
            right.grid(row=0, column=1, sticky="nsew", padx=(6, 4), pady=(6, 8))
            return left, right

        p_basic = self._pagenav.add_page("Basic", "📋")
        self.tab_details, self.tab_class = two_cols(p_basic)
        p_price = self._pagenav.add_page("Price & VAT", "💰")
        self.tab_pricing, self.tab_cost = two_cols(p_price)
        p_stock = self._pagenav.add_page("Stock", "📦")
        self.tab_inv, self.tab_status = two_cols(p_stock)
        self.tab_units  = self._pagenav.add_page("Units & Barcodes", "📐")
        self.tab_rates    = self.tab_units    # rates are edited in the Units table
        self.tab_barcode  = self.tab_units
        more = self._pagenav.add_page("More", "➕")
        more_nb = ttk.Notebook(more)
        more_nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_supp = tk.Frame(more_nb, bg=C["content_bg"])
        self.tab_stock = tk.Frame(more_nb, bg=C["content_bg"])
        self.tab_sales = tk.Frame(more_nb, bg=C["content_bg"])
        self.tab_purch = tk.Frame(more_nb, bg=C["content_bg"])
        self.tab_images = tk.Frame(more_nb, bg=C["content_bg"])
        self.tab_notes = tk.Frame(more_nb, bg=C["content_bg"])
        for fr, txt in ((self.tab_supp, "🏭 Suppliers"), (self.tab_stock, "📊 Stock history"),
                        (self.tab_sales, "🧾 Sales"), (self.tab_purch, "🛒 Purchases"),
                        (self.tab_images, "🖼 Images"), (self.tab_notes, "📝 Notes")):
            more_nb.add(fr, text="  %s  " % txt)
        self._pagenav.show_page(p_basic)

        # Build every section's fields (unchanged internal logic — only
        # the container each one draws into has changed above)
        self.body = self.tab_details
        self._build_form(C)
        self._build_units_tab(C)
        self._build_rates_tab(C)
        self._build_barcode_tab(C)
        self._build_pricing_tab(C)
        self._build_inventory_tab(C)
        self._build_accounting_tab(C)
        self._build_stock_tab(C)
        self._build_sales_tab(C)
        self._build_purchase_tab(C)
        self._build_suppliers_tab(C)
        self._build_images_tab(C)
        self._build_notes_tab(C)

        # keyboard-first workflow: Enter/Shift+Enter move between fields;
        # Ctrl+S / F4 save, F5 save & print, Ctrl+D duplicate, Ctrl+B / Ctrl+P
        # barcode actions — matches the shortcuts printed on the toolbar.
        bind_enter_navigation(self.win)
        self.win.bind("<Control-s>", lambda e=None: self._save(mode="close"))
        self.win.bind("<F4>", lambda e=None: self._save(mode="close"))
        self.win.bind("<F5>", lambda e=None: self._save(mode="print"))
        if self.product_id:
            self.win.bind("<Control-d>", lambda e=None: self._duplicate_product())
            self.win.bind("<Control-p>", lambda e=None: self._print_product_barcode())
        self.win.bind("<Control-b>", lambda e=None: self._quick_generate_barcode())

    def _open_units_tab_dialog(self, kind):
        """Shared opener used by the Units/Rates/Barcodes tabs."""
        if not self.product_id:
            messagebox.showinfo("Save First",
                "Please save the product first (Details tab → Save), then "
                "manage units, rates and barcodes.")
            return
        try:
            from ui.units_manager import UnitsManagerDialog
            name = self.fields.get("product_name_en")
            pname = name.get() if name else "Product"
            UnitsManagerDialog(self.win, self.product_id, pname)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _goto_units(self):
        """Switch to the Units & Barcodes page."""
        try:
            self._pagenav.show_page(self.tab_units)
        except Exception:
            pass

    def _build_search_bar(self, C):
        """Top search bar: barcode / code / name / alias / Arabic name,
        with a live autocomplete dropdown. Selecting a result loads that
        product straight into THIS window (add + edit + search, one
        screen) — mirrors the Product Code 'already exists?' flow."""
        bar = tk.Frame(self.win, bg=C["card_bg"],
                       highlightbackground=C["border"], highlightthickness=1)
        bar.pack(fill="x", padx=8, pady=(6, 0))
        inner = tk.Frame(bar, bg=C["card_bg"]); inner.pack(fill="x", padx=10,
                                                           pady=6)
        tk.Label(inner, text="🔎", font=("Segoe UI", 12), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left")
        self._search_var = tk.StringVar()
        se = tk.Entry(inner, textvariable=self._search_var,
                     font=("Segoe UI", 10), relief="flat", bg=C["card_bg"],
                     fg=C["text_primary"])
        se.pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=4)
        se.insert(0, "")
        placeholder = "Search by barcode, code, name, alias, or Arabic name…"
        se.configure(fg=C["text_secondary"])
        se.insert(0, placeholder)

        def clear_ph(_e=None):
            if se.get() == placeholder:
                se.delete(0, "end"); se.configure(fg=C["text_primary"])

        def restore_ph(_e=None):
            if not se.get().strip():
                se.configure(fg=C["text_secondary"])
                se.insert(0, placeholder)

        se.bind("<FocusIn>", clear_ph)
        # hide the list only if focus didn't move INTO it (clicking a
        # result used to close the list before the click registered)
        se.bind("<FocusOut>", lambda e=None: self.win.after(200, self._maybe_hide_search,
                                                       restore_ph))
        se.bind("<KeyRelease>", self._on_search_type)
        se.bind("<Down>", lambda e=None: self._search_move(1))
        se.bind("<Up>", lambda e=None: self._search_move(-1))
        se.bind("<Return>", self._search_enter)
        se.bind("<Escape>", lambda e=None: (self._hide_search_results(), "break")[1])
        self._search_entry = se
        self._search_results_popup = None

    def _on_search_type(self, _e=None):
        if _e is not None and _e.keysym in ("Up", "Down", "Return", "KP_Enter",
                                            "Escape", "Tab"):
            return
        txt = self._search_var.get().strip()
        if not txt or txt.startswith("Search by barcode"):
            self._hide_search_results(); return
        if len(txt) < 2:
            self._hide_search_results(); return
        from modules.product_lookup import search_products
        self._show_search_results(search_products(txt, limit=12))

    def _show_search_results(self, rows):
        if not rows:
            self._hide_search_results()
            return
        C = cfg.theme()
        if self._search_results_popup is None or not self._search_results_popup.winfo_exists():
            pop = tk.Toplevel(self.win)
            pop.overrideredirect(True)
            pop.attributes("-topmost", True)
            lb = tk.Listbox(pop, font=("Segoe UI", 10), relief="solid", bd=1,
                            activestyle="none", selectbackground=C["primary"],
                            selectforeground="white", exportselection=False)
            lb.pack(fill="both", expand=True)
            lb.bind("<ButtonRelease-1>", self._pick_search_result)
            lb.bind("<Return>", self._pick_search_result)
            lb.bind("<Escape>", lambda e=None: self._hide_search_results())
            self._search_results_popup, self._search_lb = pop, lb
        pop, lb = self._search_results_popup, self._search_lb
        lb.delete(0, "end")
        self._search_rows = rows
        for r in rows:
            bc = r.get("matched_barcode") or r.get("barcode") or ""
            tag = "" if r.get("is_active", 1) else "   (inactive)"
            lb.insert("end", "  %s — %s   %s%s" % (
                r.get("product_code", ""), r.get("product_name_en", ""),
                ("▮ " + bc) if bc else "", tag))
        lb.configure(height=min(10, len(rows)))
        lb.selection_clear(0, "end"); lb.selection_set(0); lb.activate(0)
        e = self._search_entry
        self.win.update_idletasks()
        x, y = e.winfo_rootx() - 30, e.winfo_rooty() + e.winfo_height() + 4
        w = max(420, e.winfo_width() + 30)
        pop.geometry(f"{w}x{min(10, len(rows)) * 20 + 6}+{x}+{y}")
        pop.lift()

    def _search_move(self, d):
        lb = getattr(self, "_search_lb", None)
        if not lb or not self._search_results_popup:
            return "break"
        cur = lb.curselection()
        i = max(0, min(lb.size() - 1, (cur[0] if cur else -1) + d))
        lb.selection_clear(0, "end"); lb.selection_set(i); lb.activate(i); lb.see(i)
        return "break"

    def _search_enter(self, _e=None):
        if self._search_results_popup is not None:
            self._pick_search_result()
        return "break"

    def _maybe_hide_search(self, restore_ph=None):
        try:
            f = self.win.focus_get()
        except Exception:
            f = None
        if f is not None and f is getattr(self, "_search_lb", None):
            return
        self._hide_search_results()
        if restore_ph:
            restore_ph()

    def _hide_search_results(self):
        if getattr(self, "_search_results_popup", None) is not None:
            try:
                self._search_results_popup.destroy()
            except Exception:
                pass
            self._search_results_popup = None

    def _pick_search_result(self, _e=None):
        lb = getattr(self, "_search_lb", None)
        sel = lb.curselection() if lb else None
        if not sel:
            return
        row = self._search_rows[sel[0]]
        self._hide_search_results()
        self.open_other_product(row["product_id"], row.get("product_name_en", ""))

    def open_other_product(self, product_id, name=""):
        """Open another product for editing IN PLACE of this window (fresh
        form, same size/position) — nothing from this one carries over."""
        dirty = (not self._loaded_as_edit and
                 self.fields["product_name_en"].get().strip())
        if dirty and not messagebox.askyesno(
                "Open product", "Discard the new product you were typing and open "
                f"'{name}'?", parent=self.win):
            return
        self._remember_geometry()
        parent, cats, vats, on_save = self.parent, self.categories, self.vat_cats, self.on_save
        self.win.destroy()
        f = ProductForm(parent, product_id=product_id, categories=cats,
                        vat_cats=vats, on_save=on_save)
        try:
            show_toast(f.win, "Loaded: %s" % name, kind="info")
        except Exception:
            pass
        return f

    def _quick_generate_barcode(self):
        """Ctrl+B — generate a barcode into the primary Barcode field on
        Basic Information (the fast path; per-unit barcodes still live
        in the Units & Barcode table)."""
        try:
            from modules.barcode_gen import generate_ean13
        except Exception:
            messagebox.showinfo("Barcode", "Barcode generator not available.")
            return
        fld = self.fields.get("barcode")
        if fld is None:
            return
        if self._bc_locked():
            show_toast(self.win, "Barcodes are made by the system on Save "
                                 "(Settings ▸ Barcode).", kind="info")
            return
        from modules.barcode_gen import new_unique_barcode
        code = new_unique_barcode(exclude=self._typed_barcodes())
        fld.set(code)
        show_toast(self.win, "Barcode generated: %s" % code, kind="info")

    def _next_product_code(self):
        """Auto product code — the last created product's code + 1
        (P0012 → P0013, 1005 → 1006), never one already used in any format."""
        try:
            from modules.product_lookup import next_product_code
            return next_product_code()
        except Exception:
            return "1001"

    @staticmethod
    def _bc_locked():
        """Settings ▸ Barcode: system barcodes are made by DayBill only."""
        return cfg.flag("barcode_system_locked", True)

    def _next_system_barcode(self):
        from modules.barcode_gen import new_unique_barcode
        return new_unique_barcode(exclude=self._typed_barcodes())

    def _toggle_manual_code(self):
        """Manual tick — lets the user type their own code; unticking on a
        new product restores the auto-generated one."""
        if self.manual_code_var.get():
            self.code_entry.configure(state="normal")
            self.code_entry.focus_set()
        else:
            self.code_entry.configure(state="normal")
            if self.product_id is None:
                self.fields["product_code"].set(self._next_product_code())
            self.code_entry.configure(state="disabled")

    def _check_code_exists(self):
        """Typing a code that is ALREADY SAVED offers to load that product
        into this form for editing (so this one window does add + edit)."""
        if self.product_id is not None:
            return                       # already editing a product
        code = self.fields["product_code"].get().strip()
        if not code:
            return
        try:
            from modules.product_lookup import code_owner
            o = code_owner(code)
        except Exception:
            o = None
        if o and not o["as"].startswith("product code"):
            messagebox.showwarning(
                "Product Code", "%s is already a barcode of:\n\n    %s\n\n"
                "Product codes must be different from every barcode — type another code."
                % (code, o["product_name"]))
            self.manual_code_var.set(True)
            self.code_entry.configure(state="normal")
            self.fields["product_code"].set(self._next_product_code())
            self.code_entry.focus_set()
            return
        row = {"product_id": o["product_id"], "product_name_en": o["product_name"]} if o else None
        if not row:
            return
        if messagebox.askyesno(
                "Product Code Exists",
                "Code %s is already used by:\n\n    %s\n\n"
                "Load that product here for editing?"
                % (code, row["product_name_en"])):
            self._loaded_as_edit = True        # don't ask "discard?" for this
            self.open_other_product(row["product_id"], row["product_name_en"])
        else:
            self.manual_code_var.set(True)
            self.code_entry.configure(state="normal")
            self.fields["product_code"].set("")
            self.code_entry.focus_set()

    def _build_units_tab(self, C):
        """Modern editable Multi Units table:
        Default (★S / ★P) | Barcode | Unit | Base Qty | Sales Price |
        Purchase Price | Stock — matches the redesigned spec. Internal
        row dict keys are unchanged (name/qty/barcode/price/pprice/
        remarks) so _save_units / _load_units keep working."""
        f = self.tab_units
        tk.Label(f, text="Each unit (PCs, Box, Carton…) with its barcode and prices.   "
                 "★S = default Sales unit · ★P = default Purchase unit",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=20, pady=(10, 4))

        # Column headers — header and every row share the SAME pixel
        # column widths, so titles sit exactly over their boxes
        self._UCOLS = [70, 200, 118, 72, 96, 104, 78, 56]
        hdr = tk.Frame(f, bg=C["content_bg"]); hdr.pack(fill="x", padx=20, pady=(4, 0))
        for ci, (txt, anc) in enumerate([("Default", "w"), ("Barcode", "w"), ("Unit", "w"),
                                         ("Base Qty", "center"), ("Sales Price", "e"),
                                         ("Purchase Price", "e"), ("Stock", "e"),
                                         ("More", "center")]):
            hdr.columnconfigure(ci, minsize=self._UCOLS[ci])
            tk.Label(hdr, text=txt, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                     fg=C["text_secondary"], anchor=anc).grid(row=0, column=ci,
                                                             sticky="ew", padx=2)

        self.unit_rows = []
        # Shared unit state — may already exist if _build_form's Pricing
        # card (Unit (EN) field) initialized it first; always the SAME
        # pool everywhere so a new unit added from either place shows up
        # in both immediately.
        if not hasattr(self, "_unit_choices"):
            self._unit_choices = ["PCs", "Box", "Carton", "Dozen", "Kg", "Gram",
                                  "Liter", "Pack", "Bag", "Bundle", "Unit"]
        if not hasattr(self, "_ADD_NEW"):
            self._ADD_NEW = "➕ Add New Unit…"
        if not hasattr(self, "_unit_combos"):
            self._unit_combos = []
        if not hasattr(self, "def_sales_unit"):
            self.def_sales_unit = tk.StringVar(value="PCs")
        if not hasattr(self, "def_purch_unit"):
            self.def_purch_unit = tk.StringVar(value="PCs")
        ADD_NEW = self._ADD_NEW

        def combo_values():
            return self._unit_choices + [ADD_NEW]

        def on_unit_pick(var, combo):
            if var.get() == ADD_NEW:
                from tkinter import simpledialog
                name = simpledialog.askstring(
                    "Add New Unit", "Name of the new unit (e.g. Tray, Roll):",
                    parent=self.win)
                name = (name or "").strip()
                if name and name not in self._unit_choices:
                    self._unit_choices.append(name)
                    for cb in self._unit_combos:
                        cb.configure(values=combo_values())
                var.set(name or "")
            self._refresh_default_stars()

        # cache the product's current stock once, for the per-row Stock
        # column (base_stock ÷ that row's factor)
        self._units_stock_cache = 0.0
        if self.product_id:
            try:
                self._units_stock_cache = float(db.execute_scalar(
                    "SELECT ISNULL(stock_quantity,0) FROM products "
                    "WHERE product_id=?", (self.product_id,)) or 0)
            except Exception:
                pass

        body = tk.Frame(f, bg=C["content_bg"]); body.pack(fill="x", padx=20)
        for i in range(10):
            row = tk.Frame(body, bg=C["content_bg"]); row.pack(fill="x", pady=1)
            for ci, w in enumerate(self._UCOLS):
                row.columnconfigure(ci, minsize=w)

            name_v = tk.StringVar(value="PCs" if i == 0 else "")
            qty_v  = tk.StringVar(value="1" if i == 0 else "")
            bc_v   = tk.StringVar()
            price_v= tk.StringVar()
            pprice_v = tk.StringVar()
            rem_v  = tk.StringVar()

            # Default stars — click to make THIS row the sales/purchase
            # default unit (replaces the old separate combo row)
            star_cell = tk.Frame(row, bg=C["content_bg"])
            star_cell.grid(row=0, column=0, sticky="w", padx=2)
            s_star = tk.Label(star_cell, text="☆S", font=("Segoe UI", 9, "bold"),
                              bg=C["content_bg"], fg=C["text_secondary"],
                              cursor="hand2")
            s_star.pack(side="left")
            p_star = tk.Label(star_cell, text="☆P", font=("Segoe UI", 9, "bold"),
                              bg=C["content_bg"], fg=C["text_secondary"],
                              cursor="hand2")
            p_star.pack(side="left", padx=(4, 0))
            s_star.bind("<Button-1>", lambda e=None, v=name_v: (
                self.def_sales_unit.set(v.get()), self._refresh_default_stars()))
            p_star.bind("<Button-1>", lambda e=None, v=name_v: (
                self.def_purch_unit.set(v.get()), self._refresh_default_stars()))

            bc_cell = tk.Frame(row, bg=C["content_bg"])
            bc_cell.grid(row=0, column=1, sticky="ew", padx=2)
            bc_e = tk.Entry(bc_cell, textvariable=bc_v, font=("Segoe UI", 9), width=15,
                            relief="solid", bd=1)
            bc_e.pack(side="left", fill="x", expand=True)
            if self._bc_locked():         # system barcode: shown, never typed
                bc_e.configure(state="readonly", readonlybackground="#EFEDF8",
                               fg=C["text_primary"])
            bc_e.bind("<FocusOut>",
                      lambda e=None, v=bc_v, w=bc_e: self._check_barcode_dup(v, w))
            bc_e.bind("<Return>",
                      lambda e=None, v=bc_v, w=bc_e: self._check_barcode_dup(v, w))
            tk.Button(bc_cell, text="🔍", font=("Segoe UI Emoji", 8), bg=C["card_bg"],
                      fg=C["primary"], relief="flat", cursor="hand2", padx=3,
                      command=lambda v=bc_v: self._barcode_search(v.get())
                      ).pack(side="left")
            if not self._bc_locked():
                tk.Button(bc_cell, text="⚡", font=("Segoe UI Emoji", 8), bg=C["card_bg"],
                          fg=C["success"], relief="flat", cursor="hand2", padx=3,
                          command=lambda v=bc_v, i=i: self._row_generate_barcode(v, i)
                          ).pack(side="left")

            nc = ttk.Combobox(row, textvariable=name_v, values=combo_values(),
                              font=("Segoe UI", 9), width=10)
            nc.grid(row=0, column=2, sticky="ew", padx=2)
            nc.bind("<<ComboboxSelected>>",
                    lambda e=None, v=name_v, cb=nc: on_unit_pick(v, cb))
            self._unit_combos.append(nc)

            tk.Entry(row, textvariable=qty_v, font=("Segoe UI", 9), width=6,
                     relief="solid", bd=1, justify="center").grid(row=0, column=3,
                                                                  sticky="ew", padx=2)
            tk.Entry(row, textvariable=price_v, font=("Segoe UI", 9), width=8,
                     relief="solid", bd=1, justify="right").grid(row=0, column=4,
                                                                 sticky="ew", padx=2)
            tk.Entry(row, textvariable=pprice_v, font=("Segoe UI", 9), width=8,
                     relief="solid", bd=1, justify="right").grid(row=0, column=5,
                                                                 sticky="ew", padx=2)

            stock_lbl = tk.Label(row, text="—", font=("Segoe UI", 9),
                                 bg=C["content_bg"], fg=C["text_secondary"], anchor="e")
            stock_lbl.grid(row=0, column=6, sticky="ew", padx=2)
            # 🏷 extra barcodes for THIS unit (scan many barcodes per unit)
            mb_btn = tk.Button(row, text="🏷 +", font=("Segoe UI", 8, "bold"),
                               bg=C["primary_light"], fg=C["primary"], relief="flat",
                               cursor="hand2", padx=6,
                               command=lambda i=i: self._row_multi_barcodes(i))
            mb_btn.grid(row=0, column=7, padx=(6, 0))
            self._add_tooltip(mb_btn, "More barcodes for this unit\n"
                                      "(scan several barcodes that all ring up as it)")

            def _recalc_stock(*_a, qv=qty_v, lbl=stock_lbl):
                try:
                    fct = float(qv.get() or 0)
                    lbl.configure(text=f"{(self._units_stock_cache / fct):,.2f}"
                                       if fct else "—")
                except Exception:
                    lbl.configure(text="—")
            qty_v.trace("w", _recalc_stock)

            self.unit_rows.append({"name": name_v, "qty": qty_v, "barcode": bc_v,
                                   "price": price_v, "pprice": pprice_v,
                                   "remarks": rem_v, "bc_entry": bc_e,
                                   "s_star": s_star, "p_star": p_star,
                                   "stock_lbl": stock_lbl, "frame": row,
                                   "mb_btn": mb_btn, "unit_id": None,
                                   "orig_barcode": ""})
            _recalc_stock()
            name_v.trace("w", lambda *a: self._show_unit_rows())

        self.def_sales_unit.trace("w", lambda *a: self._refresh_default_stars())
        self.def_purch_unit.trace("w", lambda *a: self._refresh_default_stars())

        # Save units button + multi-barcode access
        btns = tk.Frame(f, bg=C["content_bg"]); btns.pack(anchor="w", padx=20, pady=(14, 0))
        tk.Button(btns, text="💾  Save Units", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=7,
                  cursor="hand2", command=self._save_units).pack(side="left")
        tk.Button(btns, text="➕  Add Unit", font=("Segoe UI", 10, "bold"),
                  bg="#27AE60", fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2",
                  command=self._add_new_unit_prompt).pack(side="left", padx=8)
        tk.Button(btns, text="🖨  Print Barcodes", font=("Segoe UI", 10),
                  bg=C["card_bg"], fg=C["primary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=self._print_units_labels).pack(side="left", padx=8)
        tk.Button(btns, text="🗑  Remove All Units", font=("Segoe UI", 10),
                  bg="#E74C3C", fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2",
                  command=self._remove_all_units).pack(side="left", padx=(0, 8))
        tk.Label(f, text="Tip: Unit 1 is the base unit (factor 1). Box/Carton use the "
                 "factor (e.g. Box = 4 pieces). Leave a barcode blank to auto-generate.",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=20, pady=(8, 0))

        self._load_units()
        self._refresh_default_stars()
        self._show_unit_rows()

    def _show_unit_rows(self):
        """App-style grid: show the filled unit rows plus ONE empty row
        to type the next unit into (instead of ten empty rows)."""
        rows = getattr(self, "unit_rows", [])
        if not rows:
            return
        last = max([i for i, r in enumerate(rows) if r["name"].get().strip()] or [0])
        want = [i <= last + 1 for i in range(len(rows))]
        if want == getattr(self, "_rows_shown", None):
            return
        self._rows_shown = want
        for r in rows:
            r["frame"].pack_forget()
        for r, w in zip(rows, want):
            if w:
                r["frame"].pack(fill="x", pady=1)

    def _row_multi_barcodes(self, idx):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return False
        """🏷 on a unit row → Multi Barcode box opened on THAT unit.
        Saves first (without closing) if the product/unit isn't saved."""
        r = self.unit_rows[idx]
        if not r["name"].get().strip():
            messagebox.showinfo("Multi Barcode", "Type the unit name on this row first.",
                                parent=self.win)
            return
        if not self.product_id or not r.get("unit_id"):
            if not messagebox.askyesno("Save first",
                                       "The product and its units must be saved before "
                                       "adding extra barcodes.\n\nSave now?", parent=self.win):
                return
            if not self._save(mode="stay"):
                return
            r = self.unit_rows[idx]
        try:
            from ui.units_manager import MultiBarcodeBox
            nm = self.fields.get("product_name_en")
            MultiBarcodeBox(self.win, self.product_id, nm.get() if nm else "Product",
                            unit_id=r.get("unit_id"),
                            on_close=self._refresh_mb_counts)
        except Exception as e:
            messagebox.showerror("Multi Barcode", str(e)[:200], parent=self.win)

    def _refresh_mb_counts(self):
        """Show how many extra barcodes each unit has on its 🏷 button."""
        counts = {}
        if self.product_id:
            try:
                for rr in db.fetchall(
                        "SELECT unit_id, COUNT(*) AS n FROM product_unit_barcodes "
                        "WHERE product_id=? GROUP BY unit_id", (self.product_id,)) or []:
                    counts[rr["unit_id"]] = rr["n"]
            except Exception:
                pass
        for r in getattr(self, "unit_rows", []):
            n = counts.get(r.get("unit_id"), 0)
            try:
                r["mb_btn"].configure(text=("🏷 %d" % n) if n else "🏷 +")
            except Exception:
                pass

    def _on_unit_field_pick(self, var, combo):
        """Unit (EN) field in the Pricing card — same pool as Multi
        Units. Picking '➕ Add New Unit…' adds it everywhere at once."""
        if var.get() == self._ADD_NEW:
            from tkinter import simpledialog
            name = simpledialog.askstring(
                "Add New Unit", "Name of the new unit (e.g. Tray, Roll):",
                parent=self.win)
            name = (name or "").strip()
            if name and name not in self._unit_choices:
                self._unit_choices.append(name)
                vals = self._unit_choices + [self._ADD_NEW]
                for cb in self._unit_combos:
                    cb.configure(values=vals)
            var.set(name or "")
        try:
            self._refresh_default_stars()
        except Exception:
            pass

    def _refresh_default_stars(self):
        """Repaint ★S/★P on whichever row currently matches the chosen
        default sales/purchase unit names."""
        s_name = self.def_sales_unit.get()
        p_name = self.def_purch_unit.get()
        for r in self.unit_rows:
            nm = r["name"].get()
            is_s = bool(nm) and nm == s_name
            is_p = bool(nm) and nm == p_name
            r["s_star"].configure(text="★S" if is_s else "☆S",
                                  fg="#F1C40F" if is_s else self.C["text_secondary"])
            r["p_star"].configure(text="★P" if is_p else "☆P",
                                  fg="#16A085" if is_p else self.C["text_secondary"])

    def _typed_barcodes(self):
        """Barcodes already entered on this form (not yet saved)."""
        out = []
        try:
            out.append(self.fields["barcode"].get())
        except Exception:
            pass
        for r in getattr(self, "unit_rows", []) or []:
            try:
                v = r.get("barcode") if isinstance(r, dict) else None
                out.append(v.get() if hasattr(v, "get") else v)
            except Exception:
                pass
        return [x for x in out if x]

    def _row_generate_barcode(self, bc_var, row_idx):
        try:
            from modules.barcode_gen import generate_ean13
        except Exception:
            messagebox.showinfo("Barcode", "Barcode generator not available.")
            return
        if self._bc_locked():
            show_toast(self.win, "Barcodes are made by the system on Save "
                                 "(Settings ▸ Barcode).", kind="info")
            return
        from modules.barcode_gen import new_unique_barcode
        code = new_unique_barcode(exclude=self._typed_barcodes())
        bc_var.set(code)
        show_toast(self.win, "Barcode generated: %s" % code, kind="info")

    def _add_new_unit_prompt(self):
        """Visible '➕ New Unit' button — define a new unit-of-measure name
        and add it to every unit dropdown in this form."""
        from tkinter import simpledialog
        name = simpledialog.askstring(
            "Add New Unit", "Name of the new unit (e.g. Tray, Roll, Sack):",
            parent=self.win)
        name = (name or "").strip()
        if not name:
            return
        if name not in self._unit_choices:
            self._unit_choices.append(name)
            vals = self._unit_choices + [self._ADD_NEW]
            for cb in self._unit_combos:
                try:
                    cb.configure(values=vals)
                except Exception:
                    pass
        # drop it straight into the first empty unit row for convenience
        for r in self.unit_rows:
            if not r["name"].get().strip():
                r["name"].set(name)
                if not r["qty"].get().strip():
                    r["qty"].set("1")
                break
        messagebox.showinfo("Add New Unit",
                            "Unit '%s' added. Set its factor, barcode and "
                            "price, then Save Units." % name)

    def _remove_all_units(self):
        """🗑 Clear every unit row in this form. If the product already has
        saved units, offer to delete them from the database too."""
        if not messagebox.askyesno(
                "Remove All Units",
                "Clear all unit rows for this product?\n\n"
                "This empties the Multi Units grid. You can re-enter units "
                "and Save Units afterwards."):
            return
        for r in self.unit_rows:
            r["name"].set(""); r["qty"].set("")
            r["barcode"].set(""); r["price"].set("")
            r["pprice"].set(""); r["remarks"].set("")
            try:
                r["bc_entry"].configure(bg="white")
            except Exception:
                pass
        # base unit defaults back onto row 1 so the product still has a unit
        if self.unit_rows:
            self.unit_rows[0]["name"].set("PCs")
            self.unit_rows[0]["qty"].set("1")
        for v in (self.def_sales_unit, self.def_purch_unit):
            v.set("PCs")
        self._refresh_default_stars()
        # if this is a saved product, offer to delete the stored units
        if self.product_id and messagebox.askyesno(
                "Delete Saved Units",
                "Also delete the units already saved in the database for "
                "this product?\n\n(The base unit on the product itself is kept.)"):
            try:
                # deactivate (never DELETE): invoices / stock history keep
                # pointing at valid units; barcodes are freed for reuse
                db.execute("UPDATE product_units SET is_active=0, barcode=NULL, "
                           "is_default=0, is_default_purchase=0 WHERE product_id=?",
                           (self.product_id,))
                for r in self.unit_rows:
                    r["unit_id"] = None
                    r["orig_barcode"] = ""
                self._refresh_mb_counts()
                messagebox.showinfo("Remove All Units",
                                    "Saved units removed for this product.")
            except Exception as e:
                messagebox.showerror("Remove All Units", str(e)[:200])

    def _load_units(self):
        """Load existing product_units into the unit grid (grid is cleared
        first so nothing from a previously shown product is left over)."""
        for r in getattr(self, "unit_rows", []):
            for k in ("name", "qty", "barcode", "price", "pprice", "remarks"):
                r[k].set("")
            r["unit_id"] = None
            r["orig_barcode"] = ""
        if self.unit_rows:
            self.unit_rows[0]["name"].set("PCs")
            self.unit_rows[0]["qty"].set("1")
        if not self.product_id:
            return
        try:
            rows = db.fetchall(
                "SELECT * FROM product_units WHERE product_id=? AND is_active=1 "
                "ORDER BY conversion_factor, unit_id", (self.product_id,)) or []
        except Exception:
            rows = []
        if rows:
            self.unit_rows[0]["name"].set("")
            self.unit_rows[0]["qty"].set("")
        for i, u in enumerate(rows[:10]):
            r = self.unit_rows[i]
            r["unit_id"] = u.get("unit_id")
            r["orig_barcode"] = u.get("barcode") or ""
            r["name"].set(u.get("unit_name_en", ""))
            r["qty"].set(f"{float(u.get('conversion_factor', 1)):g}")
            r["barcode"].set(u.get("barcode", "") or "")
            r["price"].set(f"{float(u.get('selling_price', 0)):g}")
            r["pprice"].set(f"{float(u.get('purchase_price', 0) or 0):g}")
            if u.get("is_default"):
                self.def_sales_unit.set(u.get("unit_name_en", "PCs"))
            if u.get("is_default_purchase"):
                self.def_purch_unit.set(u.get("unit_name_en", "PCs"))
        self._load_rates_table()
        self._refresh_units_summary()
        self._refresh_default_stars()
        self._refresh_mb_counts()
        try:
            self._show_unit_rows()
        except Exception:
            pass

    def _barcode_owner(self, bc, exclude_product_id=None):
        from modules.product_lookup import barcode_owner
        return barcode_owner(bc, exclude_product_id=exclude_product_id)

    def _check_barcode_dup(self, var, entry=None):
        """Live check as barcodes are typed: if this barcode is already
        saved on another product, say so immediately (Polosys style) and
        mark the field red."""
        bc = var.get().strip()
        if entry is not None:
            entry.configure(bg="white")
        if not bc:
            return True
        owner = self._barcode_owner(bc, exclude_product_id=self.product_id)
        if owner:
            if entry is not None:
                entry.configure(bg="#FDE8E8")
            messagebox.showwarning(
                "Barcode Already Saved",
                "Barcode %s is ALREADY SAVED on:\n\n    %s  (%s unit)\n\n"
                "Use a different barcode, or edit that product instead."
                % (bc, owner["product_name"], owner["unit_name"]))
            return False
        return True

    def _barcode_search(self, bc=None):
        """🔍 Barcode search — find which product a barcode belongs to,
        with the option to open that product for editing."""
        from tkinter import simpledialog
        bc = (bc or "").strip()
        if not bc:
            bc = simpledialog.askstring("Search Barcode",
                                        "Enter the barcode to search:",
                                        parent=self.win) or ""
            bc = bc.strip()
        if not bc:
            return
        owner = self._barcode_owner(bc)
        if not owner:
            messagebox.showinfo("Barcode Search",
                                "Barcode %s is not saved yet — free to use." % bc)
            return
        if owner["product_id"] == self.product_id:
            messagebox.showinfo("Barcode Search",
                                "Barcode %s belongs to THIS product (%s unit)."
                                % (bc, owner["unit_name"]))
            return
        if messagebox.askyesno(
                "Barcode Found",
                "Barcode %s is saved on:\n\n    %s  (%s unit)\n\n"
                "Open that product for editing?"
                % (bc, owner["product_name"], owner["unit_name"])):
            self.open_other_product(owner["product_id"], owner["product_name"])

    def _collect_units(self):
        """Read + validate the unit grid. Returns (rows, error_text).
        Rules: a base unit (factor 1) must exist; unit names and barcodes
        must be unique on this product; barcodes must not belong to any
        other product; blank prices fall back to Sales Price × factor."""
        try:
            base_price = float(self.fields["unit_price"].get() or 0)
        except (ValueError, KeyError):
            base_price = 0.0
        try:
            base_pprice = float(self._ext_val("purchase_price", numeric=True) or 0)
        except Exception:
            base_pprice = 0.0
        rows, names, codes = [], {}, {}
        for i, r in enumerate(self.unit_rows):
            name = r["name"].get().strip()
            if not name or name == getattr(self, "_ADD_NEW", None):
                continue
            key = name.lower()
            if key in names:
                return None, f"Unit '{name}' is listed twice (rows {names[key]} and {i + 1})."
            names[key] = i + 1
            try:
                factor = float(r["qty"].get() or (1 if not rows else 0))
            except ValueError:
                return None, f"Row {i + 1} ({name}): Base Qty must be a number."
            if factor <= 0:
                return None, f"Row {i + 1} ({name}): Base Qty must be more than 0 (e.g. Box = 12)."
            try:
                price = float(r["price"].get() or 0)
                pprice = float(r["pprice"].get() or 0)
            except ValueError:
                return None, f"Row {i + 1} ({name}): prices must be numbers."
            if price <= 0:
                price = round(base_price * factor, 2)
            if pprice <= 0 and base_pprice:
                pprice = round(base_pprice * factor, 2)
            bc = r["barcode"].get().strip()
            if bc:
                if bc in codes:
                    return None, (f"Barcode {bc} is on two units ({codes[bc]} and {name}). "
                                  f"Each barcode can ring up only one unit.")
                codes[bc] = name
                owner = self._barcode_owner(bc, exclude_product_id=self.product_id)
                if owner:
                    return None, (f"Barcode {bc} ({name}) is already saved on "
                                  f"{owner['product_name']} ({owner['unit_name']}).")
            rows.append({"row": i, "unit_id": r.get("unit_id"),
                         "orig_barcode": r.get("orig_barcode") or "",
                         "name": name, "factor": factor, "price": price,
                         "pprice": pprice, "barcode": bc})
        if not rows:
            rows.append({"row": 0, "unit_id": None, "orig_barcode": "", "name": "PCs",
                         "factor": 1.0, "price": base_price, "pprice": base_pprice,
                         "barcode": ""})
        if not any(abs(u["factor"] - 1) < 1e-9 for u in rows):
            return None, ("One unit must be the base unit with Base Qty 1 "
                          "(e.g. PCs = 1, Box = 12).")
        s_def = self.def_sales_unit.get().strip().lower()
        p_def = self.def_purch_unit.get().strip().lower()
        base = next(u for u in rows if abs(u["factor"] - 1) < 1e-9)
        for u in rows:
            u["is_default"] = u["name"].lower() == s_def
            u["is_default_purchase"] = u["name"].lower() == p_def
        if not any(u["is_default"] for u in rows):
            base["is_default"] = True
        if not any(u["is_default_purchase"] for u in rows):
            (next((u for u in rows if u["is_default"]), base))["is_default_purchase"] = True
        return rows, ""

    def _write_units(self, rows):
        """Save units IN PLACE: existing units are UPDATED (their unit_id
        never changes, so extra barcodes, stock history and invoices that
        point at them stay linked); new rows are INSERTED; units removed
        from the grid are deactivated, never deleted."""
        from modules.barcode_gen import new_unique_barcode
        auto_bc = cfg.flag("auto_unit_barcode", True) or self._bc_locked()
        existing = {u["unit_id"]: u for u in (db.fetchall(
            "SELECT unit_id, barcode FROM product_units WHERE product_id=? AND is_active=1",
            (self.product_id,)) or [])}
        kept = set()
        taken = [u["barcode"] for u in rows if u["barcode"]]
        main_bc = (self.fields["barcode"].get().strip() if self.fields.get("barcode") else "")
        for u in rows:
            bc = u["barcode"]
            if not bc and auto_bc:
                if main_bc and abs(u["factor"] - 1) < 1e-9 and main_bc not in taken:
                    bc = main_bc              # the piece scans with the product's own barcode
                else:
                    bc = new_unique_barcode(exclude=taken + [main_bc])
                taken.append(bc)
                u["barcode"] = bc
            vals = (u["name"], u["factor"], u["price"], u["pprice"], bc or None,
                    1 if u["is_default"] else 0, 1 if u["is_default_purchase"] else 0)
            uid = u["unit_id"] if u["unit_id"] in existing else None
            if uid:
                db.execute("UPDATE product_units SET unit_name_en=?, conversion_factor=?, "
                           "selling_price=?, purchase_price=?, barcode=?, is_default=?, "
                           "is_default_purchase=?, is_active=1 WHERE unit_id=?", vals + (uid,))
                old = (existing[uid].get("barcode") or "").strip()
                if old and old != (bc or ""):
                    # the unit's own barcode changed: drop the stale copy that
                    # older installs mirrored into the extra-barcodes table
                    try:
                        db.execute("DELETE FROM product_unit_barcodes WHERE unit_id=? "
                                   "AND barcode=?", (uid, old))
                    except Exception:
                        pass
            else:
                db.execute("INSERT INTO product_units (product_id, unit_name_en, "
                           "conversion_factor, selling_price, purchase_price, barcode, "
                           "is_default, is_default_purchase, is_sales_unit, "
                           "is_purchase_unit, is_active) VALUES (?,?,?,?,?,?,?,?,1,1,1)",
                           (self.product_id,) + vals)
                uid = db.execute_scalar(
                    "SELECT MAX(unit_id) FROM product_units WHERE product_id=? "
                    "AND unit_name_en=?", (self.product_id, u["name"]))
            kept.add(uid)
            r = self.unit_rows[u["row"]]
            r["unit_id"], r["orig_barcode"] = uid, bc or ""
            r["barcode"].set(bc or "")
        for uid in existing:
            if uid not in kept:
                # soft-remove: keeps history valid; frees its barcode for reuse
                db.execute("UPDATE product_units SET is_active=0, barcode=NULL, "
                           "is_default=0, is_default_purchase=0 WHERE unit_id=?", (uid,))
        # keep the product row's unit / price in step with the default unit
        d = next(u for u in rows if u["is_default"])
        base = next(u for u in rows if abs(u["factor"] - 1) < 1e-9)
        if auto_bc and not main_bc and base.get("barcode"):
            # Settings ▸ auto barcode: the product gets its piece barcode too,
            # so every product AND every unit can be scanned and printed
            try:
                db.execute("UPDATE products SET barcode=? WHERE product_id=? "
                           "AND ISNULL(barcode,'')=''", (base["barcode"], self.product_id))
                if self.fields.get("barcode") is not None:
                    self.fields["barcode"].set(base["barcode"])
            except Exception:
                pass
        db.execute("UPDATE products SET unit_of_measure_en=?, unit_price=? WHERE product_id=?",
                   (d["name"], base["price"], self.product_id))
        try:
            if self.fields.get("unit_price") is not None:
                self.fields["unit_price"].set(f"{base['price']:g}")
        except Exception:
            pass

    def _save_units(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit" if self._loaded_as_edit else "add"):
            return False
        """💾 Save Units button — same rules as the main Save."""
        if not self.product_id:
            self._save(mode="stay")
            return
        rows, err = self._collect_units()
        if err:
            messagebox.showwarning("Units", err, parent=self.win)
            return
        try:
            self._write_units(rows)
            show_toast(self.win, "✅ Units saved", kind="success")
            self._refresh_default_stars()
            self._refresh_units_summary()
            self._load_rates_table()
            self._refresh_mb_counts()
        except Exception as e:
            messagebox.showerror("Units Error", str(e)[:300], parent=self.win)

    def _build_rates_tab(self, C):
        """Rates are shown and edited in the Units & Barcodes table (the
        separate read-only 'Multi Rates' table was removed)."""
        self._rates_tv = None

    def _product_vat_rate(self):
        """This product's VAT % (from the VAT category chosen on the form)."""
        try:
            if hasattr(self, "vat_var") and self.vat_var.get():
                return self._current_vat_rate()
        except Exception:
            pass
        try:
            vid = None
            w = self.fields.get("vat_category_id")
            if w is not None:
                vid = w.get() if hasattr(w, "get") else None
            if self.product_id:
                r = db.execute_scalar(
                    "SELECT ISNULL(vc.vat_rate,15) FROM products p "
                    "LEFT JOIN vat_categories vc ON p.vat_category_id=vc.vat_category_id "
                    "WHERE p.product_id=?", (self.product_id,))
                if r is not None:
                    return float(r)
        except Exception:
            pass
        return 15.0

    def _load_rates_table(self):
        tv = getattr(self, "_rates_tv", None)
        if tv is None:
            return
        tv.delete(*tv.get_children())
        vrate = self._product_vat_rate()
        rows = []
        if self.product_id:
            try:
                rows = db.fetchall(
                    "SELECT unit_name_en, conversion_factor, selling_price, barcode "
                    "FROM product_units WHERE product_id=? AND is_active=1 "
                    "ORDER BY conversion_factor", (self.product_id,)) or []
            except Exception:
                rows = []
        if not rows:
            tv.insert("", "end", values=("(save units first)", "", "", "", ""))
            return
        for u in rows:
            rate = float(u.get("selling_price", 0) or 0)
            tv.insert("", "end", values=(
                u.get("unit_name_en", ""),
                f"{float(u.get('conversion_factor', 1) or 1):g}",
                f"{rate:,.2f}", f"{cfg.price_with_vat(rate, vrate):,.2f}",
                u.get("barcode", "") or ""))

    def _build_barcode_tab(self, C):
        f = self.tab_barcode
        row = tk.Frame(f, bg=C["content_bg"]); row.pack(fill="x", padx=20, pady=(10, 8))
        tk.Button(row, text="🏷  Many barcodes for one unit…", font=("Segoe UI", 9, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat", padx=12, pady=5,
                  cursor="hand2",
                  command=lambda: self._open_units_tab_dialog("barcodes")).pack(side="left")
        tk.Button(row, text="🔍  Which product has this barcode?", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["primary"], relief="flat", padx=12, pady=5,
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: self._barcode_search(None)).pack(side="left", padx=(8, 0))

    # ── Form Body (Details tab) ───────────────────────────────
    def _build_form(self, C):
        b = self.body

        def section(text, icon, target=None):
            tgt = target if target is not None else b
            tk.Frame(tgt, bg=C["border"], height=1).pack(fill="x", padx=14, pady=(6, 0))
            f = tk.Frame(tgt, bg=C["content_bg"])
            f.pack(fill="x", padx=14, pady=(3, 0))
            tk.Label(f, text=f"{icon}  {text}",
                     font=("Segoe UI", 9, "bold"),
                     bg=C["content_bg"], fg=C["primary"]).pack(side="left")

        def lbl_entry(parent, label, key, col=None, required=False,
                      justify="left", width=None):
            cell = parent if col is None else tk.Frame(parent, bg=C["content_bg"])
            if col is not None:
                cell.grid(row=0, column=col, sticky="ew",
                          padx=(0, 10) if col == 0 else (10, 0))
            lbl_text = f"{label} *" if required else label
            tk.Label(cell, text=lbl_text,
                     font=("Segoe UI", 9, "bold" if required else "normal"),
                     bg=C["content_bg"],
                     fg=C["primary"] if required else C["text_secondary"]).pack(anchor="w")
            var = tk.StringVar()
            self.fields[key] = var
            opts = dict(textvariable=var, font=("Segoe UI", 10),
                        bg="white", fg=C["text_primary"],
                        relief="solid", bd=1, justify=justify)
            if width:
                opts["width"] = width
            tk.Entry(cell, **opts).pack(fill="x", ipady=4, pady=(2, 0))
            return var, cell

        # ── PRODUCT TYPE TOGGLE ───────────────────────────────
        section("Product Type", "🔀")
        type_row = tk.Frame(b, bg=C["content_bg"])
        type_row.pack(fill="x", padx=14, pady=(6, 0))

        self.ptype_var = tk.StringVar(value="product")
        self.fields["product_type"] = self.ptype_var

        self.prod_btn = tk.Radiobutton(
            type_row, text="📦  Product",
            variable=self.ptype_var, value="product",
            font=("Segoe UI", 10, "bold"), indicatoron=False,
            bg=C["content_bg"], fg=C["info"], selectcolor=C["info"],
            activebackground=C["content_bg"],
            relief="solid", padx=12, pady=5, bd=1,
            command=self._on_type_change
        )
        self.prod_btn.pack(side="left", padx=(0, 8))

        self.svc_btn = tk.Radiobutton(
            type_row, text="🔧  Service",
            variable=self.ptype_var, value="service",
            font=("Segoe UI", 10, "bold"), indicatoron=False,
            bg=C["content_bg"], fg=C["success"], selectcolor=C["success"],
            activebackground=C["content_bg"],
            relief="solid", padx=12, pady=5, bd=1,
            command=self._on_type_change
        )
        self.svc_btn.pack(side="left")
        self._paint_type()

        # ── BASIC INFO ────────────────────────────────────────
        section("Basic Information", "📋")

        row1 = tk.Frame(b, bg=C["content_bg"])
        row1.pack(fill="x", padx=14, pady=(6, 0))
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        # Product Code — Polosys style: auto-generated, with a "Manual"
        # tick to type your own. Typing a code that is ALREADY SAVED
        # offers to load that product straight into this form for edit.
        # medium box: a code is at most 8 characters (Settings ▸ Inventory)
        from modules.product_lookup import code_max_len
        from ui.form_kit import limit_length
        self._code_max = code_max_len()
        code_cell = tk.Frame(row1, bg=C["content_bg"])
        code_cell.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Label(code_cell, text="Code *" + ("   (max %d)" % self._code_max if self._code_max else ""),
                 font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(anchor="w")
        code_row = tk.Frame(code_cell, bg=C["content_bg"])
        code_row.pack(fill="x", pady=(2, 0))
        cv = tk.StringVar()
        self.fields["product_code"] = cv
        self.code_entry = tk.Entry(code_row, textvariable=cv,
                                   font=("Segoe UI", 10, "bold"), bg="white",
                                   fg=C["text_primary"], relief="solid", bd=1,
                                   width=max(10, min(self._code_max or 12, 16) + 3),
                                   disabledbackground="#EFEDF8",
                                   disabledforeground=C["text_primary"])
        self.code_entry._fixed_width = True
        self.code_entry.pack(side="left", ipady=4)
        if self._code_max:
            limit_length(self.code_entry, self._code_max)
        self.manual_code_var = tk.BooleanVar(value=self.product_id is not None)
        tk.Checkbutton(code_row, text="Manual", variable=self.manual_code_var,
                       font=("Segoe UI", 8), bg=C["content_bg"],
                       activebackground=C["content_bg"],
                       command=self._toggle_manual_code).pack(side="left", padx=(8, 0))
        self.code_entry.bind("<FocusOut>", lambda e=None: self._check_code_exists())
        self.code_entry.bind("<Return>", lambda e=None: self._check_code_exists())
        if self.product_id is None:
            cv.set(self._next_product_code())
            self.code_entry.configure(state="disabled")   # auto until Manual

        lbl_entry(row1, "اسم المنتج (عربي)", "product_name_ar", col=1, justify="right")

        # ── Product Name (English) — THE most important field on this
        # form, so it gets its own full-width row and a noticeably
        # larger box instead of sharing a cramped 1/3 column. ──
        name_row = tk.Frame(b, bg=C["content_bg"])
        name_row.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(name_row, text="Product Name (English) *",
                 font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(anchor="w")
        name_var = tk.StringVar()
        self.fields["product_name_en"] = name_var
        self.name_entry = tk.Entry(name_row, textvariable=name_var,
                                   font=("Segoe UI", 15), bg="white",
                                   fg=C["text_primary"], relief="solid", bd=1)
        self.name_entry.pack(fill="x", ipady=10, pady=(4, 0))

        # ✨ Translate the English name → Arabic (online AI when set up,
        # else the offline grocery dictionary)
        auto_row = tk.Frame(b, bg=C["content_bg"])
        auto_row.pack(fill="x", padx=14, pady=(3, 0))
        self.ai_tr_btn = tk.Button(auto_row, text="✨ Translate to Arabic",
                                   font=("Segoe UI", 8, "bold"), bg=C["primary_light"],
                                   fg=C["primary"], relief="flat", padx=10, pady=3,
                                   cursor="hand2", command=self._auto_arabic)
        self.ai_tr_btn.pack(side="right")
        self.ai_tr_note = tk.StringVar(value="")
        tk.Label(auto_row, textvariable=self.ai_tr_note, font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right", padx=6)
        # smart hints under the name: duplicate warning (#3) + auto-fill (#4)
        self.ai_hints = tk.Frame(b, bg=C["content_bg"])
        self.ai_hints.pack(fill="x", padx=14)
        self._ai_last_name = None
        self.name_entry.bind("<FocusOut>", lambda e: self._ai_name_done(), add="+")
        self.name_entry.bind("<Return>", lambda e: self._ai_name_done(), add="+")

        # Alias + listing flags row
        alias_row = tk.Frame(b, bg=C["content_bg"])
        alias_row.pack(fill="x", padx=14, pady=(6, 0))
        alias_row.columnconfigure(0, weight=1)
        alias_row.columnconfigure(1, weight=0)
        lbl_entry(alias_row, "Alias Name (search)", "alias_name", col=0)

        flags_cell = tk.Frame(alias_row, bg=C["content_bg"])
        flags_cell.grid(row=0, column=1, sticky="nw", padx=(14, 0))
        tk.Label(flags_cell, text="List In", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        flags_inner = tk.Frame(flags_cell, bg=C["content_bg"])
        flags_inner.pack(anchor="w", pady=(3, 0))
        self.list_sales_var = tk.BooleanVar(value=True)
        self.list_purchase_var = tk.BooleanVar(value=True)
        labeled_toggle(flags_inner, "Sales", self.list_sales_var, C,
                      font_size=9)[0].pack(anchor="w")
        labeled_toggle(flags_inner, "Purchase", self.list_purchase_var, C,
                      font_size=9)[0].pack(anchor="w", pady=(2, 0))

        # ── PRICING & VAT ─────────────────────────────────────
        pc = self.tab_pricing
        section("Pricing & VAT", "💰", target=pc)

        price_row = tk.Frame(pc, bg=C["content_bg"])
        price_row.pack(fill="x", padx=14, pady=(6, 0))
        price_row.columnconfigure(0, weight=1)
        price_row.columnconfigure(1, weight=1)

        lbl_entry(price_row, "Sales Price (SAR)", "unit_price", col=0, required=True)

        # Unit of measure — THIS IS the default Sales unit (same pool,
        # same variable, as the ★S column in Multi Units below; picking
        # or adding a unit here updates Multi Units too, and vice versa)
        um_cell = tk.Frame(price_row, bg=C["content_bg"])
        um_cell.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        uhead = tk.Frame(um_cell, bg=C["content_bg"]); uhead.pack(fill="x")
        tk.Label(uhead, text="Unit (EN) *",
                 font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left")
        tk.Button(uhead, text="+ New", font=("Segoe UI", 7, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat",
                  padx=5, cursor="hand2",
                  command=self._add_new_unit_prompt).pack(side="right")
        # shared unit state — initialized here since this runs before
        # _build_units_tab; that method reuses these same objects
        self._unit_choices = ["PCs", "Box", "Carton", "Dozen", "Kg", "Gram",
                              "Liter", "Pack", "Bag", "Bundle", "Unit"]
        self._ADD_NEW = "➕ Add New Unit…"
        self._unit_combos = []
        self.def_sales_unit = tk.StringVar(value="PCs")
        self.def_purch_unit = tk.StringVar(value="PCs")
        self.fields["unit_of_measure_en"] = self.def_sales_unit
        self.uom_cb = ttk.Combobox(um_cell, textvariable=self.def_sales_unit,
                               values=self._unit_choices + [self._ADD_NEW],
                               font=("Segoe UI", 10), width=14)
        self.uom_cb.pack(fill="x", ipady=5, pady=(3, 0))
        self.uom_cb.bind("<<ComboboxSelected>>",
                         lambda e=None: self._on_unit_field_pick(self.def_sales_unit,
                                                            self.uom_cb))
        self._unit_combos.append(self.uom_cb)

        vat_row = tk.Frame(pc, bg=C["content_bg"])
        vat_row.pack(fill="x", padx=14, pady=(8, 0))
        vat_row.columnconfigure(0, weight=1)
        vat_row.columnconfigure(1, weight=1)

        # VAT Category (+ quick add, without leaving the page)
        vat_cell = tk.Frame(vat_row, bg=C["content_bg"])
        vat_cell.grid(row=0, column=0, sticky="ew")
        vhead = tk.Frame(vat_cell, bg=C["content_bg"]); vhead.pack(fill="x")
        tk.Label(vhead, text="VAT Category *",
                 font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left")
        tk.Button(vhead, text="+ New", font=("Segoe UI", 7, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat",
                  padx=5, cursor="hand2",
                  command=self._quick_vat).pack(side="right")
        self.vat_var = tk.StringVar()
        self.fields["vat_category_id"] = self.vat_var
        vat_options = [f"{v['category_code']} - {v['category_name_en']} ({v['vat_rate']}%)"
                       for v in self.vat_cats]
        self.vat_cb = ttk.Combobox(vat_cell, textvariable=self.vat_var,
                                    values=vat_options, state="readonly",
                                    font=("Segoe UI", 10))
        self.vat_cb.pack(fill="x", ipady=5, pady=(3, 0))
        if vat_options:                 # Settings ▸ Tax ▸ Default VAT Rate
            self.vat_cb.current(cfg.default_vat_index([v.get("vat_rate") for v in self.vat_cats]))

        # (Currency box removed — products are priced in the shop currency)
        self.fields["currency"] = tk.StringVar(value=str(cfg.get("currency", "SAR") or "SAR"))
        vat_row.columnconfigure(1, weight=0)

        # Tax Included / Tax Exclusive — a display-only toggle that flips
        # how the Price Preview below reads (the tax rate itself always
        # comes from the VAT Category chosen above).
        tax_row = tk.Frame(pc, bg=C["content_bg"])
        tax_row.pack(fill="x", padx=14, pady=(10, 0))
        # Bound to Settings ▸ Tax ▸ Sales Price Mode — the SAME switch the
        # Sales Invoice and POS use, so the price means the same everywhere
        self.price_incl_var = tk.BooleanVar(value=cfg.sales_price_includes_vat())
        labeled_toggle(tax_row, "Sales price includes VAT (all products)",
                       self.price_incl_var, C,
                       command=self._on_price_mode_toggle)[0].pack(anchor="w")

        # Price preview
        self.price_preview_var = tk.StringVar(value="")
        tk.Label(pc, textvariable=self.price_preview_var,
                 font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["success"]).pack(
                     anchor="w", padx=18, pady=(8, 0))
        self.fields["unit_price"].trace("w", self._update_price_preview)
        self.vat_var.trace("w", self._update_price_preview)

        # ── CATEGORY / BARCODE (Basic Information — left panel) ─
        cl = self.tab_class
        section("Classification", "🗂", target=cl)
        cat_row = tk.Frame(cl, bg=C["content_bg"])
        cat_row.pack(fill="x", padx=14, pady=(6, 0))
        cat_row.columnconfigure(0, weight=1)

        # Category (+ quick add, without leaving the page)
        cat_cell = tk.Frame(cat_row, bg=C["content_bg"])
        cat_cell.grid(row=0, column=0, sticky="ew")
        chead = tk.Frame(cat_cell, bg=C["content_bg"]); chead.pack(fill="x")
        tk.Label(chead, text="Category *", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="left")
        tk.Button(chead, text="+ New", font=("Segoe UI", 7, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat",
                  padx=5, cursor="hand2",
                  command=self._quick_category).pack(side="right")
        self.cat_var = tk.StringVar()
        self.fields["category_id"] = self.cat_var
        cat_opts = ["— None —"] + [c["category_name_en"] for c in self.categories]
        self.cat_cb = ttk.Combobox(cat_cell, textvariable=self.cat_var,
                               values=cat_opts, state="readonly",
                               font=("Segoe UI", 10))
        self.cat_cb.pack(fill="x", ipady=5, pady=(3, 0))
        self.cat_cb.current(0)

        # Barcode (primary/simple barcode; multi-unit barcodes live in
        # the Units & Barcode table below)
        bc_row = tk.Frame(cl, bg=C["content_bg"])
        bc_row.pack(fill="x", padx=14, pady=(8, 0))
        if self._bc_locked():
            _bv, _bcell = lbl_entry(bc_row, "Barcode  (auto · system)", "barcode")
            self.barcode_entry = [w for w in _bcell.winfo_children() if isinstance(w, tk.Entry)][-1]
            self.barcode_entry.configure(state="readonly", readonlybackground="#EFEDF8",
                                         font=("Segoe UI", 10, "bold"))
            if self.product_id is None:
                try:      # the code this product will get (fixed on Save)
                    _bv.set(self._next_system_barcode())
                except Exception:
                    pass
        else:
            lbl_entry(bc_row, "Barcode", "barcode")

        # Brand
        brand_row = tk.Frame(cl, bg=C["content_bg"])
        brand_row.pack(fill="x", padx=14, pady=(8, 0))
        brand_cell = tk.Frame(brand_row, bg=C["content_bg"])
        brand_cell.pack(side="left", fill="x", expand=True)
        tk.Label(brand_cell, text="Brand", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w")
        brand_inner = tk.Frame(brand_cell, bg=C["content_bg"])
        brand_inner.pack(fill="x", pady=(3, 0))
        self.brands = self._load_brands()
        self.brand_var = tk.StringVar()
        self.fields["brand_id"] = self.brand_var
        self.brand_cb = ttk.Combobox(
            brand_inner, textvariable=self.brand_var,
            values=["— None —"] + [x["brand_name_en"] for x in self.brands],
            state="readonly", font=("Segoe UI", 10))
        self.brand_cb.pack(side="left", fill="x", expand=True, ipady=5)
        if self.brand_cb["values"]:
            self.brand_cb.current(0)
        tk.Button(brand_inner, text="+ Add", font=("Segoe UI", 8, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat", padx=8,
                  cursor="hand2", command=self._quick_brand).pack(side="left", padx=(6, 0))

        # ── INVENTORY (right panel) ────────────────────────────
        ic = self.tab_inv
        section("Inventory (Products Only)", "📊", target=ic)

        self.inv_frame = tk.Frame(ic, bg=C["content_bg"])
        self.inv_frame.pack(fill="x", padx=14, pady=(6, 0))

        # Track inventory — toggle switch
        self.track_var = tk.BooleanVar(value=False)
        self.fields["track_inventory"] = self.track_var
        labeled_toggle(self.inv_frame, "📦  Track Inventory for this product",
                       self.track_var, C,
                       command=self._toggle_inventory)[0].pack(anchor="w",
                                                                pady=(0, 8))

        self.inv_detail = tk.Frame(self.inv_frame, bg=C["content_bg"])
        self.inv_detail.pack(fill="x")
        self.inv_detail.columnconfigure(0, weight=1)
        self.inv_detail.columnconfigure(1, weight=1)

        _sv, self._stock_cell = lbl_entry(self.inv_detail, "Opening Stock Qty",
                                          "stock_quantity", col=0)
        lbl_entry(self.inv_detail, "Reorder Level", "reorder_level", col=1)
        # v6.0: batches + expiry dates (purchase ▸ ⏰ Expiry dates, FEFO)
        self.expiry_var = tk.BooleanVar(value=False)
        labeled_toggle(self.inv_frame, "⏰  Track expiry dates (batches)",
                       self.expiry_var, C)[0].pack(anchor="w", pady=(6, 0))

        # Disable by default
        self._toggle_inventory()

        # ── WEIGHT SCALE ──────────────────────────────────────
        st = self.tab_status
        section("Weight Scale", "⚖", target=st)
        wrap = tk.Frame(st, bg=C["content_bg"])
        wrap.pack(fill="x", padx=20, pady=(8, 0))
        self.weighed_var = tk.BooleanVar(value=False)
        self.fields["is_weighed"] = self.weighed_var
        labeled_toggle(wrap, "⚖  Sold by weight (per kg)",
                       self.weighed_var, C,
                       command=self._toggle_weight)[0].pack(anchor="w")

        self.weight_detail = tk.Frame(wrap, bg=C["content_bg"])
        self.weight_detail.pack(fill="x", pady=(6, 0))
        self.weight_detail.columnconfigure(0, weight=1)
        self.weight_detail.columnconfigure(1, weight=1)

        wu_cell = tk.Frame(self.weight_detail, bg=C["content_bg"])
        wu_cell.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Label(wu_cell, text="Weight Unit", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.fields["weight_unit"] = tk.StringVar(value="kg")
        ttk.Combobox(wu_cell, textvariable=self.fields["weight_unit"],
                     values=["kg", "g", "lb"], state="readonly",
                     font=("Segoe UI", 10), width=8).pack(fill="x", ipady=5, pady=(3, 0))

        lbl_entry(self.weight_detail, "Scale PLU code (optional)", "scale_plu", col=1)
        tk.Label(self.weight_detail,
                 text="PLU = the short code the weighing scale prints on the label.",
                 wraplength=300, justify="left",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).grid(row=1, column=0, columnspan=2,
                                              sticky="w", pady=(2, 0))
        self._toggle_weight()

        # ── STATUS (Active / Inactive) — right panel, toggle switch ──
        section("Status", "✅", target=st)
        status_row = tk.Frame(st, bg=C["content_bg"])
        status_row.pack(fill="x", padx=20, pady=(6, 14))
        self.active_var = tk.BooleanVar(value=True)
        self.fields["is_active"] = self.active_var
        labeled_toggle(status_row, "Active (visible in invoices)",
                       self.active_var, C)[0].pack(anchor="w")
        # ⭐ POS favourite — one-touch button on the POS ★ Favourites tab
        self.fav_var = tk.BooleanVar(value=False)
        fav_w = labeled_toggle(status_row, "⭐ POS Favourite", self.fav_var, C)[0]
        fav_w.pack(anchor="w", pady=(6, 0))
        self._add_tooltip(fav_w, "Shows this product as a one-touch button\n"
                                 "on the POS ★ Favourites tab.")

        # (the read-only "Units & Rates Summary" table was removed — the
        #  Units & Barcodes page shows and edits the same rows)
        self._units_summary_tv = None



    def _refresh_units_summary(self):
        """Repaint the Details-tab units/rates summary from saved data
        (or from the yet-unsaved Multi Units grid rows if this is a new
        product that hasn't been saved yet)."""
        tv = getattr(self, "_units_summary_tv", None)
        if tv is None:
            return
        tv.delete(*tv.get_children())
        rows = []
        if self.product_id:
            try:
                rows = db.fetchall(
                    "SELECT unit_name_en, conversion_factor, selling_price, "
                    "purchase_price, barcode, is_default, is_default_purchase "
                    "FROM product_units WHERE product_id=? AND is_active=1 "
                    "ORDER BY conversion_factor", (self.product_id,)) or []
            except Exception:
                rows = []
        stock = 0.0
        if self.product_id:
            try:
                stock = float(db.execute_scalar(
                    "SELECT ISNULL(stock_quantity,0) FROM products "
                    "WHERE product_id=?", (self.product_id,)) or 0)
            except Exception:
                stock = 0.0
        if not rows:
            tv.insert("", "end", values=("(save the product & units first)",
                                         "", "", "", "", "", "", ""))
            return
        for u in rows:
            fct = float(u.get("conversion_factor", 1) or 1)
            tv.insert("", "end", values=(
                u.get("barcode", "") or "—",
                u.get("unit_name_en", ""), f"{fct:g}",
                f"{float(u.get('selling_price', 0) or 0):,.2f}",
                f"{float(u.get('purchase_price', 0) or 0):,.2f}",
                "★" if u.get("is_default") else "",
                "★" if u.get("is_default_purchase") else "",
                f"{(stock / fct if fct else stock):,.2f}"))

    # ── Price Preview ─────────────────────────────────────────
    def _arabic_fallback(self):
        """Arabic name is required by the database (and shown on ZATCA
        invoices). If left empty, transliterate the English name."""
        name = self.fields["product_name_en"].get().strip()
        try:
            from modules.arabic_translit import transliterate
            ar = (transliterate(name) or "").strip()
            if ar:
                self.fields["product_name_ar"].set(ar)
                return ar
        except Exception:
            pass
        return name

    def _auto_arabic(self, quiet=False):
        """✨ English name → Arabic field. Offline dictionary at once; the
        online AI (Settings ▸ AI) replaces it with a proper translation
        a moment later — unless the user typed something meanwhile."""
        en = self.fields.get("product_name_en")
        ar = self.fields.get("product_name_ar")
        if en is None or ar is None:
            return
        name = en.get().strip()
        if not name:
            return
        from modules import product_ai as _pa
        offline = _pa.translate_offline(name)
        ar.set(offline)
        try:
            from modules import ai_client as _ai
            use_ai = _ai.enabled()
        except Exception:
            use_ai = False
        if not use_ai:
            self.ai_tr_note.set("offline dictionary — set up AI in Settings for better names"
                                if not quiet else "")
            return
        self.ai_tr_note.set("✨ AI translating…")
        try:
            self.ai_tr_btn.configure(state="disabled")
        except Exception:
            pass
        from ui.product_ai_ui import run_bg

        def done(out):
            try:
                self.ai_tr_btn.configure(state="normal")
            except Exception:
                pass
            if out and out[0] and ar.get().strip() == offline and en.get().strip() == name:
                ar.set(out[0])
                self.ai_tr_note.set("✨ translated by AI")
            else:
                self.ai_tr_note.set("")

        def fail(e):
            try:
                self.ai_tr_btn.configure(state="normal")
            except Exception:
                pass
            self.ai_tr_note.set("AI not reachable — offline translation used")
        run_bg(self.win, lambda: _ai.translate_names([name], "ar"), done, fail)

    # ── #3 duplicates + #4 auto-fill, when the English name is typed ──
    def _ai_name_done(self):
        name = self.fields["product_name_en"].get().strip()
        if not name or name == self._ai_last_name:
            return
        self._ai_last_name = name
        for w in self.ai_hints.winfo_children():
            w.destroy()
        C = cfg.theme()
        from modules import product_ai as _pa
        # Arabic still empty → fill it
        ar = self.fields.get("product_name_ar")
        if ar is not None and not ar.get().strip() and cfg.flag("ai_auto_translate", True):
            self._auto_arabic(quiet=True)
        # #3 looks like an existing product?
        if cfg.flag("ai_dup_check", True):
            dups = _pa.find_duplicates(name, ar.get() if ar is not None else "",
                                       exclude_id=self.product_id, limit=2)
            for d in dups:
                p = d["product"]
                row = tk.Frame(self.ai_hints, bg="#FFF4E5", highlightthickness=1,
                               highlightbackground="#F5C26B")
                row.pack(fill="x", pady=(4, 0))
                tk.Button(row, text="Open it", font=("Segoe UI", 8, "bold"), relief="flat",
                          bg="#F5C26B", fg="#5A3600", cursor="hand2", padx=8,
                          command=lambda pp=p: self.open_other_product(
                              pp["product_id"], pp["product_name_en"])).pack(side="right", padx=6)
                self._wrap_label(tk.Label(row, text=f"⚠  Looks like an existing product:  "
                                          f"{p['product_code']}  {p['product_name_en']}   ({d['why']})",
                                          font=("Segoe UI", 9, "bold"), bg="#FFF4E5",
                                          fg="#9A5B00", anchor="w", justify="left"), row)
        # #4 new product: copy the set-up of similar products
        if self.product_id is None and cfg.flag("ai_autofill", True):
            sug = _pa.suggest_from_similar(name)
            if sug and (sug.get("category_id") or sug.get("vat_category_id")):
                self._ai_sug = sug
                bits = []
                if sug.get("category_name"):
                    bits.append(sug["category_name"])
                if sug.get("vat"):
                    bits.append(f"VAT {float(sug['vat'].get('vat_rate') or 0):g}%")
                if sug.get("unit"):
                    bits.append(sug["unit"])
                for un, fac in sug.get("extra_units") or []:
                    bits.append(f"{un} = {fac:g}")
                if sug.get("supplier"):
                    bits.append(f"usually from {sug['supplier']}")
                row = tk.Frame(self.ai_hints, bg=C["primary_light"])
                row.pack(fill="x", pady=(4, 0))
                tk.Button(row, text="✓ Apply", font=("Segoe UI", 8, "bold"), relief="flat",
                          bg=C["primary"], fg="white", cursor="hand2", padx=10,
                          command=self._ai_apply_suggestion).pack(side="right", padx=6)
                self._wrap_label(tk.Label(row, text="💡  Like " + ", ".join(sug["based_on"][:2])
                                          + ":   " + "  ·  ".join(bits),
                                          font=("Segoe UI", 9), bg=C["primary_light"],
                                          fg=C["primary"], anchor="w", justify="left"), row)

    @staticmethod
    def _wrap_label(lbl, row):
        """Hint text wraps to the space left of its button."""
        lbl.pack(side="left", fill="x", expand=True, padx=8, pady=4)

        def fit(_e=None):
            try:
                lbl.configure(wraplength=max(120, lbl.winfo_width() - 6))
            except tk.TclError:
                pass
        lbl.bind("<Configure>", fit)
        return lbl

    def _ai_apply_suggestion(self):
        sug = getattr(self, "_ai_sug", None) or {}
        try:
            if sug.get("category_name"):
                self.cat_var.set(sug["category_name"])
            if sug.get("vat_category_id"):
                for i, vc in enumerate(self.vat_cats):
                    if vc["vat_category_id"] == sug["vat_category_id"]:
                        self.vat_cb.current(i)
                        break
            if sug.get("unit"):
                self.def_sales_unit.set(sug["unit"])
            if sug.get("brand_id") and hasattr(self, "brands"):
                b = next((x for x in self.brands if x.get("brand_id") == sug["brand_id"]), None)
                if b:
                    self.brand_var.set(b.get("brand_name_en") or "")
            # extra pack units (Box = 12 …) into the empty unit rows
            rows = getattr(self, "unit_rows", [])
            have = {r["name"].get().strip().lower() for r in rows if r["name"].get().strip()}
            try:
                base_price = float(self.fields["unit_price"].get() or 0)
            except ValueError:
                base_price = 0.0
            for un, fac in sug.get("extra_units") or []:
                if un.lower() in have:
                    continue
                r = next((r for r in rows if not r["name"].get().strip()), None)
                if r is None:
                    break
                if un not in self._unit_choices:
                    self._unit_choices.append(un)
                r["name"].set(un); r["qty"].set(f"{fac:g}")
                if base_price:
                    r["price"].set(f"{base_price * fac:g}")
                have.add(un.lower())
            try:
                self._refresh_units_summary(); self._show_unit_rows()
            except Exception:
                pass
        except Exception as e:
            self.status_var.set(f"⚠ Could not apply: {e}")
            return
        for w in self.ai_hints.winfo_children():
            if isinstance(w, tk.Frame) and w.cget("bg") == cfg.theme()["primary_light"]:
                w.destroy()
        self.status_var.set("✓ Set-up copied from similar products — check and Save.")

    def _current_vat_rate(self):
        """VAT % of the category chosen on this form right now."""
        sel = self.vat_var.get() if hasattr(self, "vat_var") else ""
        for vc in self.vat_cats:
            if sel and (sel.startswith(str(vc["category_code"]) + " ") or
                        sel == str(vc["category_code"])):
                try:
                    return float(vc.get("vat_rate") or 0)
                except (TypeError, ValueError):
                    return 0.0
        m = re.search(r"\(([\d.]+)%\)", sel or "")
        return float(m.group(1)) if m else 15.0

    def _on_price_mode_toggle(self):
        want = bool(self.price_incl_var.get())
        if want == cfg.sales_price_includes_vat():
            return
        if not messagebox.askyesno(
                "Sales Price Mode",
                "This changes how ALL sales prices are read — in POS, Sales "
                "Invoice and every product:\n\n" +
                ("• Prices INCLUDE VAT (6.50 = customer pays 6.50)" if want else
                 "• Prices EXCLUDE VAT (6.50 + 15% = customer pays 7.48)") +
                "\n\nSame as Settings ▸ Tax ▸ Sales Price Mode. Change it?",
                parent=self.win):
            self.price_incl_var.set(not want)
            return
        cfg.set("sales_price_tax_mode", "inclusive" if want else "exclusive")
        try:
            cfg.save_settings()
        except Exception:
            pass
        self._update_price_preview()
        self._load_rates_table()

    def _update_price_preview(self, *args):
        try:
            price = float(self.fields["unit_price"].get() or 0)
            rate = self._current_vat_rate()
            if self.price_incl_var.get():
                net = price / (1 + rate / 100.0) if rate else price
                vat_amt, total = price - net, price
            else:
                net, vat_amt = price, price * rate / 100.0
                total = price + vat_amt
            self.price_preview_var.set(
                f"Net {net:,.2f} + VAT {vat_amt:,.2f} = {total:,.2f} SAR")
        except Exception:
            self.price_preview_var.set("")

    # ── Type Toggle ───────────────────────────────────────────
    def _paint_type(self):
        """Selected Product / Service button: coloured with WHITE text
        (the text used to vanish into the selected colour)."""
        C = cfg.theme()
        is_prod = self.ptype_var.get() == "product"
        for btn, on, col in ((self.prod_btn, is_prod, C["info"]),
                             (self.svc_btn, not is_prod, C["success"])):
            btn.config(bg=col if on else C["content_bg"], fg="white" if on else col,
                       selectcolor=col, activeforeground="white" if on else col)

    def _on_type_change(self):
        is_prod = self.ptype_var.get() == "product"
        self._paint_type()
        if not is_prod:
            self.track_var.set(False)
            self._toggle_inventory()

    # ── Inventory Toggle ──────────────────────────────────────
    def _toggle_inventory(self):
        C = cfg.theme()
        enabled = self.track_var.get()
        state   = "normal" if enabled else "disabled"
        bg      = "white" if enabled else C["content_bg"]
        for widget in self.inv_detail.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, tk.Entry):
                    child.config(state=state, bg=bg)
        # a saved product's stock only changes through purchases, sales,
        # Stock Adjustment or Accounts ▸ Opening Balances (never by typing here)
        if self.product_id and getattr(self, "_stock_cell", None) is not None:
            for child in self._stock_cell.winfo_children():
                if isinstance(child, tk.Entry):
                    child.config(state="disabled", disabledbackground=C["content_bg"])
                elif isinstance(child, tk.Label):
                    child.config(text="Current Stock  (change with Stock Adjustment)")

    # ── Load Data ─────────────────────────────────────────────
    def _load_data(self):
        try:
            data = db.fetchone(
                "SELECT * FROM products WHERE product_id=?", (self.product_id,))
            if not data:
                return

            # Simple string fields — unit_of_measure_en is NOT loaded here
            # any more: it's the same variable as def_sales_unit, already
            # set correctly (from product_units.is_default) by
            # _load_units() during _build_units_tab, which ran moments
            # ago as part of _build_window(). Loading the products
            # table's own (denormalized, can go stale) column here would
            # overwrite that with a possibly-wrong value.
            str_keys = ["product_code", "product_name_en", "product_name_ar",
                        "description_en", "description_ar", "unit_price",
                        "unit_of_measure_ar",
                        "stock_quantity", "reorder_level", "barcode", "currency",
                        "alias_name", "weight_unit", "scale_plu"]
            for k in str_keys:
                if k in self.fields and data.get(k) is not None:
                    self.fields[k].set(str(data[k]))
            self._loaded_code = str(data.get("product_code") or "").strip()

            # Extended pricing / inventory fields (StringVars)
            for k in ["purchase_price", "wholesale_price", "last_purchase_cost",
                      "average_cost", "min_stock", "max_stock",
                      "reorder_quantity", "storage_location"]:
                w = self.fields.get(k)
                if isinstance(w, tk.StringVar) and data.get(k) is not None:
                    w.set(str(data[k]))
            # Notes (Text widgets)
            for k in ["internal_notes", "sales_notes", "purchase_notes"]:
                w = self.fields.get(k)
                if isinstance(w, tk.Text) and data.get(k):
                    try:
                        w.delete("1.0", "end")
                        w.insert("1.0", str(data[k]))
                    except Exception:
                        pass

            # Listing flags (default to listed if column missing)
            self.list_sales_var.set(bool(data.get("list_in_sales", 1)))
            self.list_purchase_var.set(bool(data.get("list_in_purchase", 1)))

            # Product type
            self.ptype_var.set(data.get("product_type", "product"))
            self._on_type_change()

            # Active
            self.active_var.set(bool(data.get("is_active", 1)))
            if hasattr(self, "fav_var"):
                self.fav_var.set(bool(data.get("is_favorite", 0)))

            # Track inventory
            self.track_var.set(bool(data.get("track_inventory", 0)))
            self._toggle_inventory()
            if hasattr(self, "expiry_var"):
                self.expiry_var.set(bool(data.get("track_expiry", 0)))

            # Weight scale
            if hasattr(self, "weighed_var"):
                self.weighed_var.set(bool(data.get("is_weighed", 0)))
                self._toggle_weight()

            # VAT category
            vat_id = data.get("vat_category_id")
            if vat_id:
                for i, vc in enumerate(self.vat_cats):
                    if vc["vat_category_id"] == vat_id:
                        self.vat_cb.current(i)
                        break

            # Category
            cat_id = data.get("category_id")
            if cat_id:
                for i, c in enumerate(self.categories):
                    if c["category_id"] == cat_id:
                        self.cat_var.set(c["category_name_en"])
                        break

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def _toggle_weight(self):
        C = cfg.theme()
        enabled = self.weighed_var.get() if hasattr(self, "weighed_var") else False
        state = "normal" if enabled else "disabled"
        bg = "white" if enabled else C["content_bg"]
        for widget in self.weight_detail.winfo_children():
            if isinstance(widget, tk.Entry):
                widget.config(state=state, bg=bg)
            for child in widget.winfo_children():
                if isinstance(child, (tk.Entry, ttk.Combobox)):
                    try:
                        child.config(state=state)
                    except Exception:
                        pass

    def _open_units(self):
        if not self.product_id:
            messagebox.showinfo("Save First",
                "Please save the product first, then open Multi Units & Barcodes.")
            return
        try:
            from ui.units_manager import UnitsManagerDialog
            name = self.fields.get("product_name_en")
            pname = name.get() if name else "Product"
            UnitsManagerDialog(self.win, self.product_id, pname)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Footer Buttons ────────────────────────────────────────
    def _build_footer(self, C):
        footer = tk.Frame(self.win, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        inner = tk.Frame(footer, bg=C["card_bg"])
        inner.pack(fill="x", padx=16, pady=10)

        self.status_var = tk.StringVar()
        tk.Label(inner, textvariable=self.status_var,
                 font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["danger"]).pack(side="left")

        # MB — tick this, then Save: a Multi Barcode box opens automatically
        # right after the product is saved (pick a unit, scan several
        # barcodes for it). Matches the reference ERP's "MB" checkbox.
        self.mb_var = tk.BooleanVar(value=False)
        mb_check = tk.Checkbutton(inner, text="MB", variable=self.mb_var,
                      font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                      fg=C["text_primary"], activebackground=C["card_bg"],
                      cursor="hand2")
        mb_check.pack(side="left", padx=(16, 0))
        self._add_tooltip(mb_check,
                          "Multi Barcode: tick this, then Save — a barcode\n"
                          "scan box opens automatically for this product.\n"
                          "Pick a unit, scan as many barcodes as it has.")

        # secondary icon actions (edit-mode only) — small, left-of-center
        if self.product_id:
            # the less-used actions sit in one "More ▾" menu (the bar stays short)
            mb = tk.Menubutton(inner, text="⋯  More ▾", font=("Segoe UI", 9, "bold"),
                               bg=C["card_bg"], fg=C["primary"], relief="flat",
                               activebackground=C["content_bg"], cursor="hand2",
                               highlightthickness=1, highlightbackground=C["border"],
                               padx=10, pady=4)
            menu = tk.Menu(mb, tearoff=0)
            for text, cmd in (("🏷  Multi Barcodes…", self._open_multi_barcode_box),
                              ("▦  QR code", self._generate_product_qr),
                              ("🏷  Print barcode      Ctrl+P", self._print_product_barcode),
                              ("⧉  Duplicate product  Ctrl+D", self._duplicate_product),
                              (None, None),
                              ("🗑  Delete product", self._delete_from_form)):
                if text is None:
                    menu.add_separator()
                else:
                    menu.add_command(label=text, command=cmd)
            mb.configure(menu=menu)
            mb.pack(side="left", padx=(10, 0))
            self._more_menu = menu

        # primary actions — rounded pills, right-aligned (Fluent style),
        # Cancel outermost, Save innermost/primary
        pills = tk.Frame(inner, bg=C["card_bg"])
        pills.pack(side="right")
        RoundedButton(pills, "Save  F4", command=lambda: self._save(mode="close"),
                     bg=C["primary"], width=100).pack(side="right", padx=(8, 0))
        RoundedButton(pills, "Save & Print  F5",
                     command=lambda: self._save(mode="print"),
                     bg="#16A085", width=150).pack(side="right", padx=(8, 0))
        RoundedButton(pills, "Save & New", command=lambda: self._save(mode="new"),
                     bg="#2E86AB", width=110).pack(side="right", padx=(8, 0))
        RoundedButton(pills, "Cancel  Esc", command=self._close,
                     bg="#95A5A6", width=132).pack(side="right", padx=(8, 0))

    def _add_tooltip(self, widget, text):
        """Small hover tooltip — no external deps, auto-positions below
        the widget, disappears on mouse-leave."""
        tip = {"win": None}

        def show(_e=None):
            if tip["win"] is not None:
                return
            t = tk.Toplevel(widget)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tk.Label(t, text=text, font=("Segoe UI", 8), bg="#2B2F38",
                     fg="white", justify="left", padx=8, pady=5).pack()
            t.geometry(f"+{x}+{y}")
            tip["win"] = t

        def hide(_e=None):
            if tip["win"] is not None:
                try:
                    tip["win"].destroy()
                except Exception:
                    pass
                tip["win"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # ── header-row actions ──────────────────────────────────────
    def _open_multi_barcode_box(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return False
        if not self.product_id:
            messagebox.showinfo("Multi Barcode", "Save the product first.")
            return
        try:
            from ui.units_manager import MultiBarcodeBox
            name = self.fields.get("product_name_en")
            pname = name.get() if name else "Product"
            MultiBarcodeBox(self.win, self.product_id, pname)
        except Exception as e:
            messagebox.showerror("Multi Barcode", str(e)[:200])

    def _duplicate_product(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "add"):
            return False
        if not self.product_id:
            return
        if not messagebox.askyesno(
                "Duplicate Product",
                "Create a copy of this product with a new code? You can "
                "edit the details before saving."):
            return
        try:
            row = db.fetchone("SELECT * FROM products WHERE product_id=?",
                             (self.product_id,))
            if not row:
                return
            self.win.destroy()
            dlg = ProductForm(self.parent, product_id=None,
                              categories=self.categories,
                              vat_cats=self.vat_cats, on_save=self.on_save)
            # pre-fill the new form from the source product (new code required)
            for key, var in dlg.fields.items():
                if key in ("product_code", "stock_quantity"):
                    continue    # code must be unique; the copy starts with no stock
                if key in row and row[key] is not None:
                    try:
                        var.set(row[key])
                    except Exception:
                        pass
            dlg.status_var.set("Copied from existing product — set a new "
                              "Product Code before saving.")
        except Exception as e:
            messagebox.showerror("Duplicate", str(e)[:200])

    def _delete_from_form(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "delete"):
            return False
        if not self.product_id:
            return
        if not messagebox.askyesno(
                "Delete Product",
                "Delete this product permanently? This cannot be undone.",
                icon="warning"):
            return
        try:
            db.execute("DELETE FROM products WHERE product_id=?", (self.product_id,))
            messagebox.showinfo("Deleted", "Product deleted.")
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except Exception as e:
            messagebox.showerror(
                "Delete",
                "Could not delete — this product may be used in existing "
                f"invoices.\n\n{str(e)[:150]}")

    def _print_units_labels(self):
        """🖨 Print Barcodes on the units page → label printing for this
        product (saves first if it's new)."""
        if not self.product_id and not self._save(mode="stay"):
            return
        self._print_product_barcode()

    def _print_product_barcode(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "print"):
            return False
        try:
            row = db.fetchone(
                "SELECT product_name_en, unit_price, barcode FROM products "
                "WHERE product_id=?", (self.product_id,))
            if not row:
                return
            from ui.label_printer import open_window
            open_window(self.win, [self.product_id], every_unit=True)   # every unit's own label
        except Exception as e:
            messagebox.showerror("Print Barcode", str(e)[:200])

    def _generate_product_qr(self):
        try:
            import tempfile, os as _os
            from reportlab.graphics.barcode import qr
            from reportlab.graphics.shapes import Drawing
            from reportlab.graphics import renderPDF
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.units import mm

            row = db.fetchone("SELECT product_code, product_name_en, barcode "
                             "FROM products WHERE product_id=?", (self.product_id,))
            data = (row.get("barcode") or row.get("product_code") or
                   str(self.product_id)) if row else str(self.product_id)
            out = _os.path.join(tempfile.gettempdir(), f"qr_{self.product_id}.pdf")
            c = rl_canvas.Canvas(out, pagesize=(40 * mm, 40 * mm))
            widget = qr.QrCodeWidget(str(data))
            b = widget.getBounds()
            w, h = b[2] - b[0], b[3] - b[1]
            size = 34 * mm
            d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
            d.add(widget)
            renderPDF.draw(d, c, 3 * mm, 3 * mm)
            c.showPage(); c.save()
            if _os.name == "nt":
                _os.startfile(out)
            else:
                messagebox.showinfo("QR Code", f"Saved: {out}")
        except Exception as e:
            messagebox.showerror("Generate QR", str(e)[:200])

    def _load_brands(self):
        try:
            return db.fetchall(
                "SELECT brand_id, brand_name_en FROM product_brands "
                "WHERE is_active=1 ORDER BY brand_name_en") or []
        except Exception:
            return []   # product_extras_patch.sql not run yet

    def _quick_category(self):
        from modules import permissions as _pm
        if not _pm.allowed("categories", "add"):
            return False
        """+ New — add a Category without leaving the product page."""
        from tkinter import simpledialog
        name = simpledialog.askstring("New Category", "Category name (English):",
                                      parent=self.win)
        if not name or not name.strip():
            return
        try:
            db.execute(
                "INSERT INTO product_categories (category_name_en, category_name_ar) "
                "VALUES (?, ?)", (name.strip(), name.strip()))
            self.categories = db.fetchall(
                "SELECT category_id, category_name_en FROM product_categories "
                "WHERE is_active=1 ORDER BY category_name_en") or []
            self.cat_cb["values"] = ["— None —"] + [c["category_name_en"]
                                                     for c in self.categories]
            self.cat_var.set(name.strip())
            clear_invalid(self.cat_cb)
        except Exception as e:
            messagebox.showerror("Category", str(e)[:200], parent=self.win)

    def _quick_vat(self):
        """+ New — add a VAT Category without leaving the product page."""
        from tkinter import simpledialog
        name = simpledialog.askstring("New VAT Category",
                                      "Name (e.g. 'Standard Rate'):",
                                      parent=self.win)
        if not name or not name.strip():
            return
        rate_s = simpledialog.askstring("New VAT Category", "VAT rate % (e.g. 15):",
                                        parent=self.win, initialvalue="15")
        try:
            rate = float(rate_s or 0)
        except ValueError:
            rate = 0
        code_s = simpledialog.askstring("New VAT Category",
                                        "Short code (e.g. S, Z, E):",
                                        parent=self.win, initialvalue="S")
        code = (code_s or "S").strip()[:5].upper()
        try:
            db.execute(
                "INSERT INTO vat_categories (category_code, category_name_en, "
                "category_name_ar, vat_rate) VALUES (?,?,?,?)",
                (code, name.strip(), name.strip(), rate))
            self.vat_cats = db.fetchall(
                "SELECT * FROM vat_categories WHERE is_active=1 "
                "ORDER BY vat_rate DESC") or []
            opts = [f"{v['category_code']} - {v['category_name_en']} "
                   f"({v['vat_rate']}%)" for v in self.vat_cats]
            self.vat_cb["values"] = opts
            match = next((o for o in opts if o.startswith(code + " -")), None)
            if match:
                self.vat_var.set(match)
            clear_invalid(self.vat_cb)
        except Exception as e:
            if "UNIQUE" in str(e):
                messagebox.showerror("VAT Category",
                                     "Code '%s' already exists — pick another."
                                     % code, parent=self.win)
            else:
                messagebox.showerror("VAT Category", str(e)[:200], parent=self.win)

    def _quick_brand(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("New Brand", "Brand name:", parent=self.win)
        if not name:
            return
        try:
            db.execute("INSERT INTO product_brands (brand_name_en) VALUES (?)",
                      (name,))
            self.brands = self._load_brands()
            self.brand_cb["values"] = ["— None —"] + [x["brand_name_en"]
                                                       for x in self.brands]
            self.brand_var.set(name)
        except Exception as e:
            messagebox.showerror(
                "Brand",
                "Could not add brand — run database/patches/product_extras_patch.sql "
                f"first.\n\n{str(e)[:150]}", parent=self.win)

    # ── Save ──────────────────────────────────────────────────
    def _product_cols(self):
        """Set of column names that exist on the products table (cached)."""
        if hasattr(self, "_pcols"):
            return self._pcols
        try:
            rows = db.fetchall("SELECT name FROM sys.columns "
                               "WHERE object_id=OBJECT_ID('products')")
            self._pcols = {r["name"] for r in (rows or [])}
        except Exception:
            self._pcols = set()
        return self._pcols

    def _field_row(self, parent, C, label, key, kind="text", options=None):
        f = tk.Frame(parent, bg=C["content_bg"])
        f.pack(fill="x", padx=4, pady=6)
        tk.Label(f, text=label, font=("Segoe UI", 8, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        if kind == "long":
            e = tk.Text(f, height=3, font=("Segoe UI", 10), relief="solid", bd=1,
                        wrap="word")
            e.pack(fill="x", pady=(2, 0))
            self.fields[key] = e   # Text widget stored directly
            return e
        # reuse an existing StringVar so shared fields stay in sync
        existing = self.fields.get(key)
        if isinstance(existing, tk.StringVar):
            var = existing
        else:
            var = tk.StringVar()
            self.fields[key] = var
        tk.Entry(f, textvariable=var, font=("Segoe UI", 10), relief="solid",
                 bd=1, bg="white", width=8).pack(fill="x", ipady=5, pady=(2, 0))
        return var

    def _grid_field(self, parent, C, row, col, label, key):
        """Label + box in a 2-column grid (shares an existing StringVar)."""
        cell = tk.Frame(parent, bg=C["content_bg"])
        cell.grid(row=row, column=col, sticky="ew", padx=(0, 10) if col == 0 else (10, 0), pady=(0, 8))
        tk.Label(cell, text=label, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        var = self.fields.get(key)
        if not isinstance(var, tk.StringVar):
            var = tk.StringVar()
            self.fields[key] = var
        tk.Entry(cell, textvariable=var, font=("Segoe UI", 10), relief="solid", bd=1,
                 bg="white", width=8).pack(fill="x", ipady=4, pady=(2, 0))
        return var

    def _section(self, parent, C, text, icon):
        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=14, pady=(6, 0))
        tk.Label(parent, text=f"{icon}  {text}", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=14, pady=(3, 0))

    def _build_pricing_tab(self, C):
        f = self.tab_cost
        self._section(f, C, "Cost & Margin", "📈")
        g = tk.Frame(f, bg=C["content_bg"]); g.pack(fill="x", padx=14, pady=(6, 0))
        g.columnconfigure(0, weight=1); g.columnconfigure(1, weight=1)
        self._grid_field(g, C, 0, 0, "Purchase Price", "purchase_price")
        self._grid_field(g, C, 0, 1, "Wholesale Price", "wholesale_price")
        self._grid_field(g, C, 1, 0, "Last Purchase Cost", "last_purchase_cost")
        self._grid_field(g, C, 1, 1, "Average Cost", "average_cost")
        row = tk.Frame(f, bg=C["content_bg"]); row.pack(fill="x", padx=14, pady=(4, 0))
        tk.Button(row, text="Calculate Margin", font=("Segoe UI", 9, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat", padx=12, pady=4,
                  cursor="hand2", command=self._calc_margin).pack(side="left")
        self.margin_var = tk.StringVar(value="Margin: —")
        tk.Label(f, textvariable=self.margin_var, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["success"], wraplength=360,
                 justify="left").pack(anchor="w", padx=14, pady=(6, 0))

    def _build_accounting_tab(self, C):
        """Accounting tab was removed from the product header (per-product
        account overrides now live only in Settings ▸ Default Accounts).
        We still create the vars so Save keeps working — they simply stay
        on '— Use Default —' and post to the configured default accounts."""
        self.acc_vars = {}
        for varname in ("acc_sales_var", "acc_purchase_var",
                        "acc_inventory_var", "acc_tax_var"):
            var = tk.StringVar(value="— Use Default —")
            self.acc_vars[varname] = var
            setattr(self, varname, var)
        self._acc_lookup = {}

    def _acc_val(self, varname):
        var = self.acc_vars.get(varname) if hasattr(self, "acc_vars") else None
        if not var:
            return None
        sel = var.get()
        if not sel or sel == "— Use Default —":
            return None
        return getattr(self, "_acc_lookup", {}).get(sel)

    def _build_images_tab(self, C):
        f = self.tab_images
        tk.Label(f, text="🖼  Product Images", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=20,
                                                           pady=(12, 2))
        tk.Label(f, text="Upload one or more images. The default image is what "
                        "shows in POS and invoices.",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=20, pady=(0, 10))

        bar = tk.Frame(f, bg=C["content_bg"]); bar.pack(fill="x", padx=20)
        tk.Button(bar, text="📤  Upload Image(s)", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._upload_images).pack(side="left")
        tk.Label(bar, text="  (drag-and-drop from the OS isn't available in "
                          "this Tkinter build — use Upload to browse files)",
                 font=("Segoe UI", 7), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(8, 0))

        self.images_holder = tk.Frame(f, bg=C["content_bg"])
        self.images_holder.pack(fill="both", expand=True, padx=20, pady=12)
        self._refresh_images()

    def _refresh_images(self):
        C = cfg.theme()
        for w in self.images_holder.winfo_children():
            w.destroy()
        if not self.product_id:
            tk.Label(self.images_holder, text="Save the product first, then "
                                              "add images.", font=("Segoe UI", 9),
                     bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w")
            return
        try:
            rows = db.fetchall(
                "SELECT image_id, image_path, is_default FROM product_images "
                "WHERE product_id=? ORDER BY is_default DESC, sort_order",
                (self.product_id,)) or []
        except Exception:
            tk.Label(self.images_holder,
                     text="Run database/patches/product_extras_patch.sql to enable "
                         "multiple product images.",
                     font=("Segoe UI", 9), bg="#FFF7E6", fg="#9A6700",
                     wraplength=520, justify="left").pack(anchor="w", ipady=6, fill="x")
            return
        if not rows:
            tk.Label(self.images_holder, text="No images yet.",
                     font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
        for r in rows:
            row = tk.Frame(self.images_holder, bg=C["card_bg"],
                           highlightbackground=C["border"], highlightthickness=1)
            row.pack(fill="x", pady=3)
            name = os.path.basename(r["image_path"])
            star = "★ " if r.get("is_default") else ""
            tk.Label(row, text=f"{star}{name}", font=("Segoe UI", 9),
                     bg=C["card_bg"], fg=C["text_primary"]).pack(
                         side="left", padx=10, pady=8)
            tk.Button(row, text="🗑", font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["danger"], relief="flat", cursor="hand2",
                      command=lambda iid=r["image_id"]: self._delete_image(iid)
                      ).pack(side="right", padx=6)
            if not r.get("is_default"):
                tk.Button(row, text="Set Default", font=("Segoe UI", 8, "bold"),
                          bg=C["content_bg"], fg=C["primary"], relief="flat",
                          padx=8, cursor="hand2",
                          command=lambda iid=r["image_id"]: self._set_default_image(iid)
                          ).pack(side="right", padx=6)

    def _upload_images(self):
        if not self.product_id:
            messagebox.showinfo("Images", "Save the product first, then add images.")
            return
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(
            title="Select product image(s)",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.gif"), ("All files", "*.*")])
        if not paths:
            return
        try:
            has_any = db.execute_scalar(
                "SELECT COUNT(*) FROM product_images WHERE product_id=?",
                (self.product_id,)) or 0
            for i, p in enumerate(paths):
                db.execute(
                    "INSERT INTO product_images (product_id, image_path, "
                    "is_default, sort_order) VALUES (?,?,?,?)",
                    (self.product_id, p, 1 if (not has_any and i == 0) else 0, i))
            self._refresh_images()
        except Exception as e:
            messagebox.showerror(
                "Images",
                "Could not save — run database/patches/product_extras_patch.sql "
                f"first.\n\n{str(e)[:150]}")

    def _delete_image(self, image_id):
        try:
            db.execute("DELETE FROM product_images WHERE image_id=?", (image_id,))
            self._refresh_images()
        except Exception as e:
            messagebox.showerror("Images", str(e)[:150])

    def _set_default_image(self, image_id):
        try:
            db.execute("UPDATE product_images SET is_default=0 WHERE product_id=?",
                      (self.product_id,))
            db.execute("UPDATE product_images SET is_default=1 WHERE image_id=?",
                      (image_id,))
            self._refresh_images()
        except Exception as e:
            messagebox.showerror("Images", str(e)[:150])

    def _calc_margin(self):
        def num(k):
            w = self.fields.get(k)
            try:
                return float(w.get() or 0)
            except Exception:
                return 0.0
        cost = num("purchase_price")
        sell = num("unit_price")  # main selling price from Details
        if not sell:
            sell = num("unit_price2")
        if sell <= 0:
            self.margin_var.set("Margin: —")
            return
        profit = sell - cost
        margin = profit / sell * 100 if sell else 0
        markup = profit / cost * 100 if cost else 0
        self.margin_var.set(f"Profit: {profit:,.2f}   |   Margin: {margin:.1f}%   "
                            f"|   Markup: {markup:.1f}%")

    def _build_inventory_tab(self, C):
        f = self.tab_inv
        self._section(f, C, "Stock Limits", "📏")
        g = tk.Frame(f, bg=C["content_bg"]); g.pack(fill="x", padx=14, pady=(6, 0))
        g.columnconfigure(0, weight=1); g.columnconfigure(1, weight=1)
        self._grid_field(g, C, 0, 0, "Minimum Stock", "min_stock")
        self._grid_field(g, C, 0, 1, "Maximum Stock", "max_stock")
        self._grid_field(g, C, 1, 0, "Reorder Quantity", "reorder_quantity")
        self._grid_field(g, C, 1, 1, "Storage Location", "storage_location")

    def _ref_table(self, parent, cols, height=6):
        """Shared read-only Treeview builder for the reference tabs."""
        wrap = tk.Frame(parent, bg=parent["bg"]); wrap.pack(fill="both",
                                                            expand=True, padx=20)
        ids = [c[0] for c in cols]
        tv = ttk.Treeview(wrap, columns=ids, show="headings", height=height)
        for cid, txt, w, anc in cols:
            tv.heading(cid, text=txt); tv.column(cid, width=w, anchor=anc)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tv

    def _need_save_note(self, f, C, what):
        tk.Label(f, text="Save the product first to see its %s." % what,
                 font=("Segoe UI", 10), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=20, pady=10)

    def _build_stock_tab(self, C):
        f = self.tab_stock
        if not self.product_id:
            self._need_save_note(f, C, "stock and cost figures")
            return
        try:
            p = db.fetchone(
                "SELECT ISNULL(stock_quantity,0) AS q, ISNULL(average_cost,0) AS avg, "
                "ISNULL(last_purchase_cost,0) AS last, ISNULL(purchase_price,0) AS pp, "
                "ISNULL(unit_price,0) AS sp, ISNULL(reorder_level,0) AS rl "
                "FROM products WHERE product_id=?", (self.product_id,)) or {}
        except Exception:
            p = {}
        q = float(p.get("q", 0) or 0); avg = float(p.get("avg", 0) or 0)
        last = float(p.get("last", 0) or 0); pp = float(p.get("pp", 0) or 0)
        sp = float(p.get("sp", 0) or 0); rl = float(p.get("rl", 0) or 0)
        cards = tk.Frame(f, bg=C["content_bg"]); cards.pack(fill="x", padx=14, pady=(8, 0))
        def _qty(v):
            return f"{v:,.3f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
        stats = [("On Hand (base units)", _qty(q), "#2E86AB"),
                 ("Average Cost", f"{avg:,.2f}", "#8E44AD"),
                 ("Last Purchase Cost", f"{last:,.2f}", "#E67E22"),
                 ("Purchase Price", f"{pp:,.2f}", "#16A085"),
                 ("Stock Value (qty × avg)", f"{q * avg:,.2f}", "#2C3E50"),
                 ("Sale Price", f"{sp:,.2f}", "#27AE60")]
        for i, (lab, val, col) in enumerate(stats):
            cell = tk.Frame(cards, bg="white", highlightbackground=C["border"],
                            highlightthickness=1)
            cell.grid(row=0, column=i, sticky="nsew", padx=3, pady=3)
            tk.Label(cell, text=lab, font=("Segoe UI", 8), bg="white",
                     fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(4, 0))
            tk.Label(cell, text=val, font=("Segoe UI", 12, "bold"), bg="white",
                     fg=col).pack(anchor="w", padx=8, pady=(0, 4))
        for c in range(6):
            cards.columnconfigure(c, weight=1, uniform="sc")
        if rl and q <= rl:
            tk.Label(f, text="⚠  At or below reorder level (%g)." % rl,
                     font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                     fg="#C0392B").pack(anchor="w", padx=20, pady=(4, 0))
        # two tables side by side: each unit | every movement (no scrolling page)
        panes = tk.Frame(f, bg=C["content_bg"]); panes.pack(fill="both", expand=True, pady=(4, 6))
        lpane = tk.Frame(panes, bg=C["content_bg"])
        rpane = tk.Frame(panes, bg=C["content_bg"])
        try:
            units = db.fetchall(
                "SELECT unit_name_en, conversion_factor FROM product_units "
                "WHERE product_id=? AND is_active=1 ORDER BY conversion_factor",
                (self.product_id,)) or []
        except Exception:
            units = []
        if units:
            lpane.pack(side="left", fill="y")
            tk.Label(lpane, text="In each unit:", font=("Segoe UI", 9, "bold"),
                     bg=C["content_bg"], fg=C["primary"]).pack(anchor="w",
                                                              padx=20, pady=(6, 2))
            tv = self._ref_table(lpane, [("unit", "Unit", 64, "w"),
                                         ("factor", "= Base", 48, "center"),
                                         ("instock", "In Stock", 64, "e")], height=6)
            for u in units:
                fct = float(u.get("conversion_factor", 1) or 1)
                tv.insert("", "end", values=(u.get("unit_name_en", ""),
                          f"{fct:g}", f"{(q / fct if fct else q):,.2f}"))
        # every stock movement (item ledger) — newest first
        try:
            moves = db.fetchall(
                "SELECT TOP 200 txn_date, txn_type, reference_type, reference_id, unit_name, "
                "ISNULL(qty_in_base,0) AS qin, ISNULL(qty_out_base,0) AS qout, "
                "ISNULL(unit_cost,0) AS cost, notes FROM inventory_transactions "
                "WHERE product_id=? ORDER BY txn_date DESC, txn_id DESC",
                (self.product_id,)) or []
        except Exception:
            moves = []
        rpane.pack(side="left", fill="both", expand=True)
        tk.Label(rpane, text="Stock movements (latest 200):", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=20, pady=(6, 2))
        tv2 = self._ref_table(rpane, [("date", "Date", 78, "w"), ("type", "Type", 84, "w"),
                                  ("ref", "Document", 84, "w"), ("unit", "Unit", 48, "w"),
                                  ("in", "In", 52, "e"), ("out", "Out", 52, "e"),
                                  ("cost", "Cost / base", 72, "e")], height=6)
        names = {"sale": "Sale", "purchase": "Purchase", "return_in": "Sales return",
                 "return_out": "Purchase return", "adjustment": "Adjustment",
                 "opening": "Opening stock", "count": "Stock count"}
        for m in moves:
            d = m.get("txn_date")
            tv2.insert("", "end", values=(
                d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")[:10],
                names.get(str(m.get("txn_type") or ""), str(m.get("txn_type") or "").title()),
                (m.get("notes") or f"{m.get('reference_type') or ''} #{m.get('reference_id') or ''}")[:40],
                m.get("unit_name") or "",
                _qty(float(m["qin"])) if float(m["qin"] or 0) else "",
                _qty(float(m["qout"])) if float(m["qout"] or 0) else "",
                f"{float(m['cost'] or 0):,.2f}"))
        if not moves:
            tv2.insert("", "end", values=("—", "No movements yet", "", "", "", "", ""))

    def _build_sales_tab(self, C):
        f = self.tab_sales
        tk.Label(f, text="🧾  Recent Sales", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w",
                                                           padx=20, pady=(12, 6))
        if not self.product_id:
            self._need_save_note(f, C, "sales history")
            return
        tv = self._ref_table(f, [("date", "Date", 100, "w"),
                                 ("inv", "Invoice", 120, "w"),
                                 ("party", "Customer", 200, "w"),
                                 ("qty", "Qty", 70, "e"),
                                 ("unit", "Unit", 80, "w"),
                                 ("rate", "Rate", 90, "e"),
                                 ("amt", "Amount", 100, "e"),
                                 ("st", "Status", 90, "w")])
        try:
            rows = db.fetchall(
                "SELECT TOP 100 si.invoice_date, si.invoice_number, "
                "si.customer_name_en, sil.quantity, sil.unit_of_measure_en, "
                "sil.unit_price, sil.line_total, si.invoice_status AS status "
                "FROM sales_invoice_lines sil JOIN sales_invoices si "
                "ON si.invoice_id=sil.invoice_id WHERE sil.product_id=? "
                "ORDER BY si.invoice_date DESC, si.invoice_id DESC",
                (self.product_id,)) or []
        except Exception:
            rows = []
        self._fill_doc_rows(tv, rows, "customer_name_en")

    def _build_purchase_tab(self, C):
        f = self.tab_purch
        tk.Label(f, text="🛒  Recent Purchases", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w",
                                                           padx=20, pady=(12, 6))
        if not self.product_id:
            self._need_save_note(f, C, "purchase history")
            return
        tv = self._ref_table(f, [("date", "Date", 100, "w"),
                                 ("inv", "Invoice", 120, "w"),
                                 ("party", "Supplier", 200, "w"),
                                 ("qty", "Qty", 70, "e"),
                                 ("unit", "Unit", 80, "w"),
                                 ("rate", "Rate", 90, "e"),
                                 ("amt", "Amount", 100, "e"),
                                 ("st", "Status", 90, "w")])
        try:
            rows = db.fetchall(
                "SELECT TOP 100 pi.invoice_date, pi.invoice_number, "
                "pi.supplier_name_en, pil.quantity, pil.unit_of_measure_en, "
                "pil.unit_price, pil.line_total, pi.invoice_status AS status "
                "FROM purchase_invoice_lines pil JOIN purchase_invoices pi "
                "ON pi.purchase_id=pil.purchase_id WHERE pil.product_id=? "
                "ORDER BY pi.invoice_date DESC, pi.purchase_id DESC",
                (self.product_id,)) or []
        except Exception:
            rows = []
        self._fill_doc_rows(tv, rows, "supplier_name_en")

    def _fill_doc_rows(self, tv, rows, party_key):
        if not rows:
            tv.insert("", "end", values=("—", "No records yet", "", "", "", "", "", ""))
            return
        tv.tag_configure("cancelled", foreground="#9CA3AF")
        tv.tag_configure("draft", foreground="#B45309")
        for r in rows:
            d = str(r.get("invoice_date", ""))[:10]
            st = str(r.get("status") or "").lower()
            tv.insert("", "end", values=(
                d, r.get("invoice_number", ""), r.get(party_key, ""),
                f"{float(r.get('quantity', 0) or 0):g}",
                r.get("unit_of_measure_en", ""),
                f"{float(r.get('unit_price', 0) or 0):,.2f}",
                f"{float(r.get('line_total', 0) or 0):,.2f}",
                st.title()), tags=(st,) if st in ("cancelled", "draft") else ())

    def _build_suppliers_tab(self, C):
        f = self.tab_supp
        tk.Label(f, text="🏭  Suppliers of this product",
                 font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=20, pady=(12, 6))
        if not self.product_id:
            self._need_save_note(f, C, "suppliers")
            return
        tv = self._ref_table(f, [("supp", "Supplier", 220, "w"),
                                 ("times", "Times", 70, "center"),
                                 ("qty", "Total Qty", 100, "e"),
                                 ("avg", "Avg Rate", 100, "e"),
                                 ("last", "Last Purchase", 120, "w")])
        try:
            rows = db.fetchall(
                "SELECT pi.supplier_name_en AS supp, COUNT(*) AS times, "
                "SUM(pil.quantity) AS qty, "
                "CASE WHEN SUM(pil.quantity)>0 THEN SUM(pil.line_amount)/SUM(pil.quantity) "
                "ELSE 0 END AS avg_rate, MAX(pi.invoice_date) AS last_date "
                "FROM purchase_invoice_lines pil JOIN purchase_invoices pi "
                "ON pi.purchase_id=pil.purchase_id WHERE pil.product_id=? "
                "AND pi.invoice_status='confirmed' "
                "GROUP BY pi.supplier_name_en ORDER BY MAX(pi.invoice_date) DESC",
                (self.product_id,)) or []
        except Exception:
            rows = []
        if not rows:
            tv.insert("", "end", values=("No suppliers yet", "", "", "", ""))
            return
        for r in rows:
            tv.insert("", "end", values=(
                r.get("supp", ""), r.get("times", 0),
                f"{float(r.get('qty', 0) or 0):g}",
                f"{float(r.get('avg_rate', 0) or 0):,.2f}",
                str(r.get("last_date", ""))[:10]))

    def _build_notes_tab(self, C):
        f = self.tab_notes
        tk.Label(f, text="📝  Notes", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=20, pady=(12, 4))
        body = tk.Frame(f, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=20)
        self._field_row(body, C, "Internal Notes", "internal_notes", kind="long")
        self._field_row(body, C, "Sales Notes", "sales_notes", kind="long")
        self._field_row(body, C, "Purchase Notes", "purchase_notes", kind="long")

    def _ext_val(self, key, numeric=False):
        """Read a value from a StringVar or Text widget in self.fields."""
        w = self.fields.get(key)
        if w is None:
            return 0 if numeric else None
        try:
            txt = w.get("1.0", "end").strip() if isinstance(w, tk.Text) else w.get().strip()
        except Exception:
            txt = ""
        if numeric:
            try:
                return float(txt or 0)
            except Exception:
                return 0
        return txt or None

    def _has_weight_columns(self):
        try:
            r = db.execute_scalar(
                "SELECT COUNT(*) FROM sys.columns "
                "WHERE object_id=OBJECT_ID('products') AND name='is_weighed'")
            return bool(r)
        except Exception:
            return False

    def _save(self, mode="close"):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit" if self._loaded_as_edit else "add"):
            return False
        # Validate — required: Product Name, Category, Unit, Sales Price, VAT.
        # Invalid fields get a red border (cleared as soon as they're fixed).
        for w in (getattr(self, "code_entry", None),
                  getattr(self, "cat_cb", None), getattr(self, "vat_cb", None),
                  getattr(self, "uom_cb", None)):
            if w is not None:
                clear_invalid(w)
        errors = []
        _code = self.fields["product_code"].get().strip()
        _max = getattr(self, "_code_max", 0)
        if not _code:
            errors.append("Product Code required.")
            if getattr(self, "code_entry", None):
                mark_invalid(self.code_entry)
        elif _max and len(_code) > _max and _code != getattr(self, "_loaded_code", None):
            errors.append("Product Code can be at most %d characters "
                          "(Settings ▸ Inventory)." % _max)
            if getattr(self, "code_entry", None):
                mark_invalid(self.code_entry)
        else:
            try:
                from modules.product_lookup import code_owner
                o = code_owner(self.fields["product_code"].get(), exclude_product_id=self.product_id)
            except Exception:
                o = None
            if o and not self.product_id and not self.manual_code_var.get():
                # the auto code was taken meanwhile (another till): take the next one
                self.fields["product_code"].set(self._next_product_code())
                o = None
            if o:
                errors.append("Code %s is already used as %s of %s — product codes must be unique."
                              % (self.fields["product_code"].get().strip(), o["as"], o["product_name"]))
                if getattr(self, "code_entry", None):
                    mark_invalid(self.code_entry)
        if not self.fields["product_name_en"].get().strip():
            errors.append("Product Name (EN) required.")
        if not self.cat_var.get().strip() or self.cat_var.get() == "— None —":
            errors.append("Category required.")
            if getattr(self, "cat_cb", None):
                mark_invalid(self.cat_cb)
        if not self.fields.get("unit_of_measure_en", tk.StringVar()).get().strip():
            errors.append("Unit required.")
            if getattr(self, "uom_cb", None):
                mark_invalid(self.uom_cb)
        if not self.vat_var.get().strip():
            errors.append("VAT Category required.")
            if getattr(self, "vat_cb", None):
                mark_invalid(self.vat_cb)
        try:
            price = float(self.fields["unit_price"].get() or 0)
            if price < 0:
                errors.append("Sales price cannot be negative.")
            elif price == 0:
                errors.append("Sales Price required.")
        except ValueError:
            errors.append("Invalid unit price.")

        if errors:
            self.status_var.set("⚠️  " + "  |  ".join(errors))
            try:
                show_toast(self.win, "⚠️ " + errors[0], kind="error")
            except Exception:
                pass
            return False

        # System barcode (Settings ▸ Barcode): made by DayBill, 6 digits,
        # never typed — a fresh one if empty or taken meanwhile
        if self._bc_locked() and self.fields.get("barcode") is not None:
            cur = self.fields["barcode"].get().strip()
            if not cur or (not self.product_id and self._barcode_owner(cur)):
                try:
                    self.fields["barcode"].set(self._next_system_barcode())
                except Exception as e:
                    self.status_var.set("⚠️ " + str(e)[:120])
                    return False
        # Barcode must be unique across all products — Polosys behavior
        bc_main = (self.fields.get("barcode").get().strip()
                   if self.fields.get("barcode") else "")
        if bc_main:
            owner = self._barcode_owner(bc_main,
                                        exclude_product_id=self.product_id)
            if owner:
                self.status_var.set("❌ Barcode already saved on %s (%s unit)."
                                    % (owner["product_name"],
                                       owner["unit_name"]))
                messagebox.showwarning(
                    "Barcode Already Saved",
                    "Barcode %s is ALREADY SAVED on:\n\n    %s  (%s unit)\n\n"
                    "Use a different barcode."
                    % (bc_main, owner["product_name"], owner["unit_name"]))
                return False

        # #3 a NEW product that looks like one already saved → ask first
        if not self.product_id and cfg.flag("ai_dup_check", True):
            try:
                from modules import product_ai as _pa
                dups = [d for d in _pa.find_duplicates(
                    self.fields["product_name_en"].get(),
                    self.fields["product_name_ar"].get() if self.fields.get("product_name_ar") else "",
                    limit=3) if d["score"] >= 0.85]
            except Exception:
                dups = []
            if dups and not messagebox.askyesno(
                    "Looks like a duplicate",
                    "This product looks like one you already have:\n\n" +
                    "\n".join(f"   {d['product']['product_code']}  "
                              f"{d['product']['product_name_en']}   ({d['why']})" for d in dups) +
                    "\n\nSave it as a NEW product anyway?", parent=self.win):
                self.status_var.set("Not saved — open the existing product instead.")
                return False

        # Units grid is saved WITH the product (validated first, so a bad
        # unit row never leaves a half-saved product behind)
        unit_rows_data, uerr = self._collect_units()
        if uerr:
            self.status_var.set("⚠️  " + uerr)
            try:
                show_toast(self.win, "⚠️ " + uerr, kind="error")
                self._goto_units()
            except Exception:
                pass
            return False

        self.status_var.set("")

        def v(key, default=""):
            val = self.fields.get(key)
            if val is None:
                return default
            if isinstance(val, tk.BooleanVar):
                return 1 if val.get() else 0
            return val.get().strip() or default

        # Resolve VAT category ID
        vat_sel = self.vat_var.get()
        vat_id  = None
        for vc in self.vat_cats:
            if vc["category_code"] in vat_sel:
                vat_id = vc["vat_category_id"]
                break

        # Resolve category ID
        cat_name = self.cat_var.get()
        cat_id = None
        for c in self.categories:
            if c["category_name_en"] == cat_name:
                cat_id = c["category_id"]
                break

        # Resolve brand ID (optional — product_extras_patch.sql adds the column)
        brand_id = None
        if hasattr(self, "brand_var"):
            brand_name = self.brand_var.get()
            for br in getattr(self, "brands", []):
                if br["brand_name_en"] == brand_name:
                    brand_id = br["brand_id"]
                    break

        data = {
            "product_code":       v("product_code"),
            "product_name_en":    v("product_name_en"),
            "product_name_ar":    v("product_name_ar") or self._arabic_fallback(),
            "description_en":     v("description_en") or None,
            "description_ar":     v("description_ar") or None,
            "product_type":       v("product_type", "product"),
            "unit_price":         float(v("unit_price", "0") or 0),
            "currency":           v("currency", "SAR"),
            "unit_of_measure_en": v("unit_of_measure_en", "Unit"),
            "unit_of_measure_ar": v("unit_of_measure_ar", "وحدة") or "وحدة",
            "vat_category_id":    vat_id,
            "category_id":        cat_id,
            "barcode":            v("barcode") or None,
            "track_inventory":    1 if self.track_var.get() else 0,
            "stock_quantity":     float(v("stock_quantity", "0") or 0),
            "reorder_level":      float(v("reorder_level", "0") or 0),
            "alias_name":         v("alias_name") or None,
            "list_in_sales":      1 if self.list_sales_var.get() else 0,
            "list_in_purchase":   1 if self.list_purchase_var.get() else 0,
            "is_active":          1 if self.active_var.get() else 0,
        }

        # Weight-scale fields — only include if the DB has those columns
        if self._has_weight_columns():
            data["is_weighed"] = 1 if (hasattr(self, "weighed_var")
                                       and self.weighed_var.get()) else 0
            data["weight_unit"] = v("weight_unit", "kg") or "kg"
            data["scale_plu"] = v("scale_plu") or None

        # Extended product-master fields — only persist columns that exist
        pcols = self._product_cols()
        ext = {
            "purchase_price":     self._ext_val("purchase_price", numeric=True),
            "wholesale_price":    self._ext_val("wholesale_price", numeric=True),
            "last_purchase_cost": self._ext_val("last_purchase_cost", numeric=True),
            "average_cost":       self._ext_val("average_cost", numeric=True),
            "min_stock":          self._ext_val("min_stock", numeric=True),
            "max_stock":          self._ext_val("max_stock", numeric=True),
            "reorder_quantity":   self._ext_val("reorder_quantity", numeric=True),
            "storage_location":   self._ext_val("storage_location"),
            "internal_notes":     self._ext_val("internal_notes"),
            "sales_notes":        self._ext_val("sales_notes"),
            "purchase_notes":     self._ext_val("purchase_notes"),
            "brand_id":           brand_id,
            "is_favorite":        (1 if getattr(self, "fav_var", None) is not None
                                   and self.fav_var.get() else 0),
            "sales_account_id":     self._acc_val("acc_sales_var"),
            "purchase_account_id": self._acc_val("acc_purchase_var"),
            "inventory_account_id": self._acc_val("acc_inventory_var"),
            "tax_account_id":       self._acc_val("acc_tax_var"),
            "track_expiry":         (1 if getattr(self, "expiry_var", None) is not None
                                     and self.expiry_var.get() else 0),
        }
        for k, val in ext.items():
            if k in pcols:
                data[k] = val

        # shelf-label price watch (Inventory ▸ Price Change Labels)
        _was_new = not self.product_id
        _opening_qty = 0.0
        try:
            from modules import price_watch as _pw
            _price_before = _pw.snapshot([self.product_id] if self.product_id else [])
        except Exception:
            _price_before = None
        _tx = None
        try:
            # v5.27: product, units, barcodes and opening stock are ONE
            # transaction — a used barcode no longer leaves half a product
            _tx = db.begin()
            if self.product_id:
                # stock is never written from this form (it would undo sales made
                # meanwhile and bypass the stock card / books)
                data.pop("stock_quantity", None)
                set_clause = ", ".join([f"{k}=?" for k in data])
                sql = (f"UPDATE products SET {set_clause}, updated_at=GETDATE() "
                       f"WHERE product_id=?")
                db.execute(sql, (*data.values(), self.product_id))
                msg = f"Product '{data['product_name_en']}' updated."
            else:
                cols = ", ".join(data.keys())
                ph   = ", ".join(["?"] * len(data))
                sql  = f"INSERT INTO products ({cols}) VALUES ({ph})"
                db.execute(sql, tuple(data.values()))
                msg = f"Product '{data['product_name_en']}' added."
                try:                       # so Save & Print / Duplicate work
                    self.product_id = db.execute_scalar(
                        "SELECT product_id FROM products WHERE product_code=?",
                        (data["product_code"],))
                except Exception:
                    pass
                # opening stock typed on a new product: recorded by
                # opening_balances.set_opening_stock after the units are saved
                try:
                    _opening_qty = float(data.get("stock_quantity") or 0)
                except Exception:
                    _opening_qty = 0.0

            # units (same transaction of intent as the product)
            self._write_units(unit_rows_data)
            self._saved_ok = True
            # opening stock → stock card + Inventory / Opening Balance Equity
            # (same date as every other opening: Accounts ▸ Opening Balances)
            if _was_new and _opening_qty and self.product_id:
                try:
                    from modules import opening_balances as _ob
                    _ob.set_opening_stock(self.product_id, _opening_qty, None,
                                          adjust_stock=False)
                except Exception:
                    pass
            try:
                from modules import price_watch as _pw
                if _price_before is not None and self.product_id:
                    _price_before[("_ids",)] = [self.product_id]
                    _pw.record(_price_before, "product", new_product=_was_new)
            except Exception:
                pass
            _tx.commit()
            # Settings ▸ PLU Scale ▸ export the scale file automatically
            if data.get("is_weighed") and cfg.flag("plu_export_on_save", False):
                try:
                    from ui import plu_manager as _plu
                    self._plu_export = _plu.auto_export()
                except Exception:
                    pass

            if self.on_save:
                self.on_save()
            was_new_id = self.product_id
            was_new = not bool(getattr(self, "_loaded_as_edit", False))
            if mode == "stay":
                # saved, window stays open as an edit form
                self._loaded_as_edit = True
                self.win.title("Edit Product")
                try:
                    self._hdr_title.configure(text="✏️  Edit Product")
                except Exception:
                    pass
                self.status_var.set("✅ Saved")
                show_toast(self.win, "✅  " + msg, kind="success")
                self._refresh_units_summary()
                self._refresh_mb_counts()
                return True
            parent = self.parent
            categories, vat_cats, on_save = self.categories, self.vat_cats, self.on_save
            mb_wanted = bool(self.mb_var.get())
            pname_field = self.fields.get("product_name_en")
            pname_val = pname_field.get() if pname_field else "Product"
            root = None
            try:
                root = self.parent.winfo_toplevel()
            except Exception:
                pass
            self._remember_geometry()
            self.win.destroy()
            if root is not None:
                show_toast(root, "✅  " + msg, kind="success")
            if mode == "print" and was_new_id:
                try:
                    from ui.label_printer import open_window
                    open_window(root or parent, [was_new_id], every_unit=True)
                except Exception as e:
                    messagebox.showerror("Print Barcode", str(e)[:200])
            if mb_wanted and was_new_id:
                # MB ticked — open the Multi Barcode box right after Save
                # (units are saved now, so its unit dropdown is ready)
                try:
                    from ui.units_manager import MultiBarcodeBox
                    MultiBarcodeBox(root or parent, was_new_id, pname_val)
                except Exception as e:
                    messagebox.showerror("Multi Barcode", str(e)[:200])
            if mode == "new":
                # Save & New: a fresh blank form for rapid entry
                ProductForm(parent, product_id=None, categories=categories,
                           vat_cats=vat_cats, on_save=on_save)
            return True

        except Exception as e:
            if _tx is not None and not _tx.kept:
                _tx.rollback()                    # nothing of a failed save is kept
                if _was_new:
                    self.product_id = None
                self._saved_ok = False
            err = str(e)
            if ("UNIQUE" in err or "duplicate" in err.lower()) and "barcode" in err.lower():
                self.status_var.set("❌ A barcode on this product is already used.")
            elif "UNIQUE" in err or "duplicate" in err.lower():
                self.status_var.set("❌ Product code already exists.")
            else:
                self.status_var.set(f"❌ {err[:120]}")
            try:
                show_toast(self.win, self.status_var.get(), kind="error")
            except Exception:
                pass
            return False

    def _close(self):
        self._hide_search_results()
        self._remember_geometry()
        try:
            self.win.destroy()
        except Exception:
            pass

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ─────────────────────────────────────────────────────────────
# STOCK ADJUST DIALOG
# ─────────────────────────────────────────────────────────────
class StockAdjustDialog:
    def __init__(self, parent, product_id, product_data, on_save=None):
        self.product_id   = product_id
        self.product_data = product_data
        self.on_save      = on_save
        C = cfg.theme()

        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e=None: self.win.destroy())
        self.win.title("Adjust Stock")
        self.win.geometry("420x320")
        self.win.resizable(False, False)
        self.win.configure(bg=C["content_bg"])
        self.win.grab_set()
        self._center(420, 320)

        # Header
        tk.Frame(self.win, bg=C["warning"], height=4).pack(fill="x")
        hdr = tk.Frame(self.win, bg=C["content_bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text=f"📋  Adjust Stock",
                 font=("Segoe UI", 13, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        current = float(product_data.get("stock_quantity", 0))
        name    = product_data.get("product_name_en", "")

        tk.Label(self.win, text=name,
                 font=("Segoe UI", 11), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=20, pady=(8, 0))

        # Current stock display
        cur_frame = tk.Frame(self.win, bg=C["primary_light"])
        cur_frame.pack(fill="x", padx=20, pady=14)
        tk.Label(cur_frame, text=f"Current Stock:  {current:,.3f}",
                 font=("Segoe UI", 12, "bold"),
                 bg=C["primary_light"], fg=C["primary"],
                 padx=16, pady=10).pack(side="left")

        # Adjustment type
        type_row = tk.Frame(self.win, bg=C["content_bg"])
        type_row.pack(fill="x", padx=20)
        self.adj_type = tk.StringVar(value="add")
        tk.Radiobutton(type_row, text="➕  Add",
                       variable=self.adj_type, value="add",
                       font=("Segoe UI", 10), bg=C["content_bg"],
                       fg=C["success"]).pack(side="left", padx=(0, 16))
        tk.Radiobutton(type_row, text="➖  Remove",
                       variable=self.adj_type, value="remove",
                       font=("Segoe UI", 10), bg=C["content_bg"],
                       fg=C["danger"]).pack(side="left", padx=(0, 16))
        tk.Radiobutton(type_row, text="⚙️  Set Exact",
                       variable=self.adj_type, value="set",
                       font=("Segoe UI", 10), bg=C["content_bg"],
                       fg=C["info"]).pack(side="left")

        # Quantity input
        qty_frame = tk.Frame(self.win, bg=C["content_bg"])
        qty_frame.pack(fill="x", padx=20, pady=12)
        tk.Label(qty_frame, text="Quantity:",
                 font=("Segoe UI", 10), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        self.qty_var = tk.StringVar(value="0")
        tk.Entry(qty_frame, textvariable=self.qty_var,
                 font=("Segoe UI", 12), bg="white", relief="solid",
                 bd=1, width=12).pack(side="left", padx=8, ipady=6)

        # Status
        self.status_var = tk.StringVar()
        tk.Label(self.win, textvariable=self.status_var,
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["danger"]).pack(padx=20)

        # Buttons
        btn_row = tk.Frame(self.win, bg=C["content_bg"])
        btn_row.pack(fill="x", padx=20, pady=10)
        tk.Button(btn_row, text=t("common.cancel"),
                  font=("Segoe UI", 10), bg=C["card_bg"], fg=C["text_secondary"],
                  relief="flat", padx=12, pady=6,
                  command=self.win.destroy).pack(side="right", padx=(6, 0))
        tk.Button(btn_row, text="✅  Apply",
                  font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white",
                  relief="flat", padx=16, pady=6,
                  command=self._apply).pack(side="right")

    def _apply(self):
        try:
            qty = float(self.qty_var.get())
            if qty < 0:
                self.status_var.set("Quantity must be ≥ 0")
                return
            current = float(self.product_data.get("stock_quantity", 0))
            adj_type = self.adj_type.get()

            if adj_type == "add":
                new_qty = current + qty
            elif adj_type == "remove":
                new_qty = current - qty
                if new_qty < 0:
                    self.status_var.set("Cannot remove more than current stock.")
                    return
            else:
                new_qty = qty

            db.execute(
                "UPDATE products SET stock_quantity=?, updated_at=GETDATE() "
                "WHERE product_id=?",
                (new_qty, self.product_id)
            )
            # log the movement (stock ledger) + keep Inventory account in step
            diff = new_qty - current
            if diff:
                try:
                    from datetime import date as _d
                    db.execute(
                        "INSERT INTO inventory_transactions (product_id, txn_date, "
                        "txn_type, reference_type, qty_in_base, qty_out_base, "
                        "balance_base, notes) VALUES (?,?,?,?,?,?,?,?)",
                        (self.product_id, _d.today().strftime("%Y-%m-%d"),
                         "adjustment_in" if diff > 0 else "adjustment_out",
                         "manual", diff if diff > 0 else 0,
                         -diff if diff < 0 else 0, new_qty,
                         "Product window adjustment"))
                    from modules import stock_branch as _sb       # v6.0
                    _sb.after_manual_move(self.product_id, diff, "manual_adjust", self.product_id)
                except Exception:
                    pass
                try:
                    from modules import doc_posting
                    doc_posting.post_stock_adjustment(self.product_id, diff,
                                                      "Stock adjustment")
                except Exception:
                    pass
            messagebox.showinfo(t("common.success"),
                                f"Stock updated to {new_qty:,.3f}")
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except ValueError:
            self.status_var.set("Invalid quantity entered.")
        except Exception as e:
            self.status_var.set(str(e)[:80])

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ─────────────────────────────────────────────────────────────
# CATEGORY MANAGER DIALOG
# ─────────────────────────────────────────────────────────────
class BulkRateDialog:
    """Bulk sales-rate editor. Shows every product with an editable
    Sales Rate cell, plus one-shot bulk operations:
      • +/- a percentage
      • +/- a fixed amount
      • set price = cost + margin%
    applied to all rows or just a filtered/selected subset. Nothing is
    written until Save, so you can review every new price first."""
    def __init__(self, parent, on_save=None):
        self.on_save = on_save
        C = cfg.theme()
        self.C = C
        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e=None: self.win.destroy())
        self.win.title("Bulk Sales-Rate Edit")
        self.win.configure(bg=C["content_bg"])
        self.win.grab_set()
        self._center(820, 640)

        tk.Label(self.win, text="💲  Bulk Sales-Rate Edit",
                 font=("Segoe UI", 14, "bold"), bg=C["primary"], fg="white",
                 pady=10).pack(fill="x")

        # bulk-op bar
        op = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                      highlightthickness=1)
        op.pack(fill="x", padx=14, pady=(10, 6))
        oi = tk.Frame(op, bg=C["card_bg"]); oi.pack(fill="x", padx=12, pady=10)
        tk.Label(oi, text="Apply:", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
        self.mode_var = tk.StringVar(value="pct")
        ttk.Combobox(oi, textvariable=self.mode_var, state="readonly",
                     font=("Segoe UI", 9), width=22,
                     values=["pct", "amount", "margin"]).pack(side="left", padx=6)
        tk.Label(oi, text="(pct = %  ·  amount = SAR  ·  margin = cost+%)",
                 font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 8))
        self.val_var = tk.StringVar(value="10")
        tk.Entry(oi, textvariable=self.val_var, font=("Segoe UI", 10), width=8,
                 relief="solid", bd=1, justify="right").pack(side="left", ipady=3)
        self.scope_var = tk.StringVar(value="all")
        ttk.Combobox(oi, textvariable=self.scope_var, state="readonly",
                     font=("Segoe UI", 9), width=12,
                     values=["all", "selected"]).pack(side="left", padx=6)
        tk.Button(oi, text="↳ Apply to rows", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=12, pady=4,
                  cursor="hand2", command=self._apply_bulk).pack(side="left", padx=6)
        # search filter
        tk.Label(oi, text="🔍", bg=C["card_bg"],
                 font=("Segoe UI Emoji", 10)).pack(side="left", padx=(14, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._reload())
        tk.Entry(oi, textvariable=self.search_var, font=("Segoe UI", 10),
                 width=18, relief="solid", bd=1).pack(side="left", ipady=3)

        # table with editable rate
        card = tk.Frame(self.win, bg="white", highlightbackground=C["border"],
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14)
        head = tk.Frame(card, bg=C["primary_light"]); head.pack(fill="x")
        for txt, w in [("✓", 3), ("Code", 12), ("Product", 34),
                       ("Cost", 10), ("Old Rate", 10), ("New Rate", 12)]:
            tk.Label(head, text=txt, font=("Segoe UI", 9, "bold"),
                     bg=C["primary_light"], fg=C["primary"], width=w,
                     anchor="w").pack(side="left", padx=4, pady=4)
        cv = tk.Canvas(card, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(card, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(fill="both", expand=True)
        self.rowsf = tk.Frame(cv, bg="white")
        cv.create_window((0, 0), window=self.rowsf, anchor="nw")
        self.rowsf.bind("<Configure>",
                        lambda e=None: cv.configure(scrollregion=cv.bbox("all")))
        self._rows = []
        self._reload()

        # footer
        foot = tk.Frame(self.win, bg=C["card_bg"]); foot.pack(fill="x", side="bottom")
        fi = tk.Frame(foot, bg=C["card_bg"]); fi.pack(fill="x", padx=14, pady=10)
        self.status = tk.StringVar()
        tk.Label(fi, textvariable=self.status, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["primary"]).pack(side="left")
        tk.Button(fi, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self.win.destroy).pack(
            side="right", padx=(8, 0))
        tk.Button(fi, text="💾 Save changed rates", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._save).pack(side="right")

    def _reload(self):
        C = self.C
        for w in self.rowsf.winfo_children():
            w.destroy()
        self._rows = []
        q = self.search_var.get().lower().strip()
        try:
            prods = db.fetchall(
                "SELECT product_id, product_code, product_name_en, "
                "ISNULL(purchase_price,0) AS cost, ISNULL(unit_price,0) AS rate "
                "FROM products WHERE is_active=1 AND product_type='product' "
                "ORDER BY product_name_en") or []
        except Exception:
            prods = []
        for p in prods:
            if q and q not in (str(p.get("product_code", "")) +
                               str(p.get("product_name_en", ""))).lower():
                continue
            row = tk.Frame(self.rowsf, bg="white"); row.pack(fill="x")
            sel = tk.BooleanVar(value=False)
            tk.Checkbutton(row, variable=sel, bg="white",
                           activebackground="white").pack(side="left", padx=2)
            tk.Label(row, text=p.get("product_code", ""), font=("Segoe UI", 9),
                     bg="white", width=12, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=(p.get("product_name_en", "") or "")[:40],
                     font=("Segoe UI", 9), bg="white", width=34,
                     anchor="w").pack(side="left", padx=4)
            cost = float(p.get("cost", 0) or 0)
            old = float(p.get("rate", 0) or 0)
            tk.Label(row, text=f"{cost:,.2f}", font=("Segoe UI", 9), bg="white",
                     width=10, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=f"{old:,.2f}", font=("Segoe UI", 9), bg="white",
                     fg="#6B7280", width=10, anchor="w").pack(side="left", padx=4)
            newv = tk.StringVar(value=f"{old:.2f}")
            e = tk.Entry(row, textvariable=newv, font=("Segoe UI", 9), width=12,
                         relief="solid", bd=1, justify="right")
            e.pack(side="left", padx=4)
            self._rows.append({"pid": p["product_id"], "cost": cost,
                               "old": old, "new": newv, "sel": sel})
        if hasattr(self, "status"):
            self.status.set(f"{len(self._rows)} product(s)")

    def _apply_bulk(self):
        try:
            val = float(self.val_var.get())
        except ValueError:
            self.status.set("Enter a number for the bulk value."); return
        mode = self.mode_var.get()
        scope = self.scope_var.get()
        n = 0
        for r in self._rows:
            if scope == "selected" and not r["sel"].get():
                continue
            old = r["old"]
            if mode == "pct":
                new = old * (1 + val / 100.0)
            elif mode == "amount":
                new = old + val
            else:  # margin over cost
                new = r["cost"] * (1 + val / 100.0)
            r["new"].set(f"{max(new, 0):.2f}")
            n += 1
        self.status.set(f"Applied to {n} row(s) — review, then Save.")

    def _save(self):
        changes = []
        for r in self._rows:
            try:
                new = float(r["new"].get())
            except ValueError:
                continue
            if abs(new - r["old"]) > 0.005:
                changes.append((r["pid"], new))
        if not changes:
            self.status.set("No rate changes to save."); return
        if not messagebox.askyesno(
                "Save Rates",
                f"Update the sales rate for {len(changes)} product(s)?"):
            return
        try:
            try:
                from modules import price_watch as _pw
                _before = _pw.snapshot([pid for pid, _n in changes])
            except Exception:
                _before = None
            for pid, new in changes:
                db.execute("UPDATE products SET unit_price=?, updated_at=GETDATE() "
                           "WHERE product_id=?", (new, pid))
                # keep the base unit's shelf price in step with the rate
                try:
                    db.execute("UPDATE product_units SET selling_price=? WHERE product_id=? "
                               "AND is_active=1 AND conversion_factor=1", (new, pid))
                except Exception:
                    pass
            try:
                if _before is not None:
                    _pw.record(_before, "bulk_rate")
            except Exception:
                pass
            try:
                from modules import audit
                audit.log("bulk_update", "products", None,
                          f"{len(changes)} sales rates updated")
            except Exception:
                pass
            messagebox.showinfo("Bulk Rate Edit",
                                f"Updated {len(changes)} product rate(s).")
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except Exception as e:
            messagebox.showerror("Bulk Rate Edit", str(e)[:200])

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


class CategoryManagerDialog:
    def __init__(self, parent, on_close=None):
        self.on_close = on_close
        C = cfg.theme()

        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e=None: self.win.destroy())
        self.win.title("Manage Product Categories")
        self.win.geometry("500x590")
        self.win.resizable(False, True)
        self.win.configure(bg=C["content_bg"])
        self.win.grab_set()
        self._center(500, 590)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        # Header
        hdr = tk.Frame(self.win, bg=C["primary"], height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🗂  Product Categories",
                 font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)

        # Add new row
        add_row = tk.Frame(self.win, bg=C["content_bg"])
        add_row.pack(fill="x", padx=16, pady=14)

        tk.Label(add_row, text="EN:", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        self.new_en = tk.StringVar()
        tk.Entry(add_row, textvariable=self.new_en,
                 font=("Segoe UI", 10), bg="white", relief="solid",
                 bd=1, width=16).pack(side="left", padx=(4, 8), ipady=5)

        tk.Label(add_row, text="AR:", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        self.new_ar = tk.StringVar()
        tk.Entry(add_row, textvariable=self.new_ar,
                 font=("Segoe UI", 10), bg="white", relief="solid",
                 bd=1, width=14, justify="right").pack(side="left", padx=(4, 10), ipady=5)

        tk.Button(add_row, text="＋ Add",
                  font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white",
                  relief="flat", padx=10, pady=5,
                  command=self._add_category).pack(side="left")

        # Category list
        list_frame = tk.Frame(self.win, bg=C["card_bg"],
                              highlightbackground=C["border"], highlightthickness=1)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        cols = ("en", "ar", "products")
        style = ttk.Style()
        style.configure("Cat.Treeview", rowheight=30, font=("Segoe UI", 9))
        style.configure("Cat.Treeview.Heading", font=("Segoe UI", 9, "bold"))

        vsb = ttk.Scrollbar(list_frame, orient="vertical")
        vsb.pack(side="right", fill="y")
        self.cat_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                      style="Cat.Treeview",
                                      yscrollcommand=vsb.set, height=12)
        vsb.config(command=self.cat_tree.yview)
        self.cat_tree.heading("en", text="Category (EN)")
        self.cat_tree.heading("ar", text="الفئة (AR)")
        self.cat_tree.heading("products", text="Products")
        self.cat_tree.column("en", width=180)
        self.cat_tree.column("ar", width=160, anchor="e")
        self.cat_tree.column("products", width=80, anchor="center")
        self.cat_tree.pack(fill="both", expand=True)

        # Bottom buttons
        btn_row = tk.Frame(self.win, bg=C["content_bg"])
        btn_row.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(btn_row, text="🗑  Delete Selected",
                  font=("Segoe UI", 9), bg="#FEF2F2", fg=C["danger"],
                  relief="flat", padx=10, pady=5,
                  command=self._delete_category).pack(side="left")
        tk.Button(btn_row, text="✅  Done",
                  font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white",
                  relief="flat", padx=14, pady=5,
                  command=self._on_close).pack(side="right")

        self._load_categories()

    def _load_categories(self):
        self.cat_tree.delete(*self.cat_tree.get_children())
        try:
            cats = db.fetchall(
                "SELECT pc.category_id, pc.category_name_en, pc.category_name_ar, "
                "COUNT(p.product_id) AS product_count "
                "FROM product_categories pc "
                "LEFT JOIN products p ON pc.category_id = p.category_id "
                "WHERE pc.is_active=1 "
                "GROUP BY pc.category_id, pc.category_name_en, pc.category_name_ar "
                "ORDER BY pc.category_name_en"
            )
            for c in cats:
                self.cat_tree.insert("", "end",
                    iid=str(c["category_id"]),
                    values=(c["category_name_en"],
                            c.get("category_name_ar", ""),
                            c.get("product_count", 0)))
        except Exception:
            pass

    def _add_category(self):
        from modules import permissions as _pm
        if not _pm.allowed("categories", "add"):
            return False
        en = self.new_en.get().strip()
        ar = self.new_ar.get().strip()
        if not en:
            messagebox.showwarning("Required", "Category name (EN) is required.")
            return
        try:
            db.execute(
                "INSERT INTO product_categories (category_name_en, category_name_ar) "
                "VALUES (?, ?)", (en, ar or en))
            self.new_en.set("")
            self.new_ar.set("")
            self._load_categories()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_category(self):
        from modules import permissions as _pm
        if not _pm.allowed("categories", "delete"):
            return False
        sel = self.cat_tree.selection()
        if not sel:
            return
        cid  = int(sel[0])
        name = self.cat_tree.item(sel[0])["values"][0]
        cnt  = self.cat_tree.item(sel[0])["values"][2]
        if cnt and int(cnt) > 0:
            messagebox.showerror(t("common.error"),
                f"Cannot delete. {cnt} product(s) use this category.")
            return
        if messagebox.askyesno(t("common.warning"),
                               f"Delete category '{name}'?"):
            db.execute("UPDATE product_categories SET is_active=0 "
                       "WHERE category_id=?", (cid,))
            self._load_categories()

    def _on_close(self):
        if self.on_close:
            self.on_close()
        self.win.destroy()

    def _center(self, w, h):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
