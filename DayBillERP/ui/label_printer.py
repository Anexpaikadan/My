# ============================================================
# DayBill ERP - Print Barcode Labels
# ------------------------------------------------------------
#   • scan a barcode (piece, box, carton, extra, scale label) or type a
#     name → the product is added WITH that unit (its own barcode + price)
#   • "Every unit" adds Piece + Box + Carton rows of a product at once
#   • copies per row (type, + / −, "= stock"), whole categories
#   • pick a design (★ = default) — live preview of the real label
#   • ⚡ makes the missing barcodes (product + every unit) in one click
#   • Print → label printer, or PDF
# Used as the "Print Labels" tab of Barcode & Labels, and as a window
# from the Products list.
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys, os, json, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg
from config.database import db
import modules.barcode_designer as bd
from modules import barcode_resolver as BR

PLACEHOLDER = "Scan a barcode or type a product name, then Enter"


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


class LabelPrintPanel:
    def __init__(self, parent, preselect=None, on_edit_design=None, every_unit=False):
        self.C = cfg.theme()
        self.on_edit_design = on_edit_design
        self.frame = tk.Frame(parent, bg=self.C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.rows = []                    # label rows (+ 'copies')
        self._imgs = []                   # keep preview images alive
        self._matches = []
        self._company = self._company_name()
        try:
            bd.ensure_ready_designs()
        except Exception:
            pass
        self._build()
        self.reload_designs()
        for pid in (preselect or []):
            self.add_product(pid, every_unit=every_unit, render=False)
        self._render()

    # ── data ────────────────────────────────────────────────
    def _company_name(self):
        try:
            r = db.fetchone("SELECT company_name_en FROM company") or {}
            return r.get("company_name_en") or ""
        except Exception:
            return ""

    def reload_designs(self, select_id=None):
        self.templates = bd.list_templates()
        names = [t["template_name"] + ("  ★" if t.get("is_default") else "") for t in self.templates]
        self.design_cb["values"] = names
        idx = 0
        keep = select_id or getattr(self, "_tpl_id", None)
        for i, t in enumerate(self.templates):
            if t["template_id"] == keep:
                idx = i
        if names:
            self.design_cb.current(idx)
        self._on_design()

    def template(self):
        i = self.design_cb.current()
        if 0 <= i < len(self.templates):
            return dict(self.templates[i])
        return None

    def _key(self, r):
        return (r["product_id"], r.get("unit_id"))

    def add_row(self, row, copies=1, render=True):
        """Add a label row (one product unit); the same unit again = +copies."""
        k = self._key(row)
        have = next((r for r in self.rows if self._key(r) == k), None)
        if have:
            have["copies"] = int(have.get("copies", 1)) + int(copies)
        else:
            row = dict(row)
            row["copies"] = int(copies)
            row["company_name"] = self._company
            self.rows.append(row)
            have = row
        if render:
            self._render(select=k)
        return have

    def add_product(self, product_id, every_unit=False, unit_id=None, copies=1, render=True):
        rows = BR.label_rows(product_id)
        if not rows:
            return []
        if every_unit:
            pick = rows
        elif unit_id:
            pick = [r for r in rows if r.get("unit_id") == unit_id] or rows[:1]
        else:
            units = BR.units_of(product_id)
            d = next((u for u in units if u.get("is_default")), None)
            pick = [r for r in rows if d and r.get("unit_id") == d["unit_id"]] or rows[:1]
        out = [self.add_row(r, copies, render=False) for r in pick]
        if render:
            self._render(select=self._key(out[-1]))
        return out

    def add_unit_named(self, product_id, unit_name, copies=1, render=True):
        """A document line (product + unit name + qty) → its label row."""
        rows = BR.label_rows(product_id)
        if not rows:
            return None
        un = str(unit_name or "").strip().lower()
        r = next((x for x in rows if str(x.get("unit_name") or "").strip().lower() == un), None) \
            or rows[0]
        return self.add_row(r, max(1, int(round(_f(copies, 1)))), render=render)

    def scan(self, text):
        """A scanned / typed code → its product + unit row. True if found."""
        hit = BR.resolve(text)
        if not hit:
            return False
        if self.every_v.get():
            self.add_product(hit["product_id"], every_unit=True)
        else:
            self.add_product(hit["product_id"], unit_id=hit["unit_id"] or
                             (hit.get("unit") or {}).get("unit_id"))
        self.msg_v.set("✔ " + BR.describe(hit))
        return True

    # ── UI ─────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, primary=False, danger=False, small=False):
        C = self.C
        bg = C["primary"] if primary else ("#FEF2F2" if danger else C["card_bg"])
        fg = "white" if primary else (C["danger"] if danger else C["text_primary"])
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat",
                      font=("Segoe UI", 8 if small else 9, "bold" if primary else "normal"),
                      padx=8 if small else 12, pady=3 if small else 6, cursor="hand2",
                      activebackground=C["primary_dark"] if primary else C["content_bg"],
                      highlightthickness=0 if primary else 1,
                      highlightbackground=C.get("field_border", C["border"]))
        return b

    def _build(self):
        C = self.C
        top = tk.Frame(self.frame, bg=C["card_bg"])
        top.pack(fill="x")
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill="x")
        tk.Label(top, text="🖨", font=("Segoe UI Emoji", 15), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left", padx=(14, 6), pady=8)
        tt = tk.Frame(top, bg=C["card_bg"]); tt.pack(side="left")
        tk.Label(tt, text="Print Barcode Labels", font=("Segoe UI", 13, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w")
        tk.Label(tt, text="scan or search · every unit has its own barcode + price · "
                          "choose a design · print", font=("Segoe UI", 8),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.print_btn = self._btn(top, "🖨  Print labels", lambda: self.print_labels(True),
                                   primary=True)
        self.print_btn.pack(side="right", padx=(4, 14), pady=10)
        self._btn(top, "📄 PDF", lambda: self.print_labels(False)).pack(side="right", padx=4)

        # design row
        dr = tk.Frame(self.frame, bg=C["content_bg"]); dr.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(dr, text="Design", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        self.design_cb = ttk.Combobox(dr, state="readonly", width=34, font=("Segoe UI", 9))
        self.design_cb.pack(side="left", padx=(6, 6))
        self.design_cb.bind("<<ComboboxSelected>>", lambda e: self._on_design())
        self.size_v = tk.StringVar()
        tk.Label(dr, textvariable=self.size_v, font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=4)
        if self.on_edit_design:
            self._btn(dr, "✏ Edit design", self._edit_design, small=True).pack(side="left", padx=6)
        self._btn(dr, "★ Use as default", self._make_default, small=True).pack(side="left")

        # add row
        ar = tk.Frame(self.frame, bg=C["content_bg"]); ar.pack(fill="x", padx=14, pady=(4, 2))
        box = tk.Frame(ar, bg="white", highlightbackground=C["primary"], highlightcolor=C["primary"],
                       highlightthickness=2)
        box.pack(side="left", fill="x", expand=True)
        tk.Label(box, text="🔎", font=("Segoe UI Emoji", 11), bg="white").pack(side="left", padx=(6, 0))
        self.find_v = tk.StringVar()
        self.find_e = tk.Entry(box, textvariable=self.find_v, font=("Segoe UI", 11), relief="flat",
                               bd=0, bg="white")
        self.find_e.pack(side="left", fill="x", expand=True, ipady=6, padx=6)
        self.find_e.bind("<Return>", self._find_enter)
        self.find_e.bind("<KP_Enter>", self._find_enter)
        self.find_e.bind("<KeyRelease>", self._find_type)
        self.find_e.bind("<Down>", lambda e: self._drop_focus())
        self.find_e.bind("<Escape>", lambda e: self._drop_hide())
        self.find_e.bind("<FocusIn>", lambda e: self._ph(False))
        self.find_e.bind("<FocusOut>", lambda e: self._ph(True))
        self.every_v = tk.BooleanVar(value=False)
        tk.Checkbutton(ar, text="Every unit (PCs + Box + Carton…)", variable=self.every_v,
                       bg=C["content_bg"], activebackground=C["content_bg"],
                       font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        self.cat_v = tk.StringVar()
        try:
            self._cats = db.fetchall("SELECT category_id, category_name_en FROM product_categories "
                                     "WHERE ISNULL(is_active,1)=1 ORDER BY category_name_en") or []
        except Exception:
            self._cats = []
        cc = ttk.Combobox(ar, textvariable=self.cat_v, state="readonly", width=16,
                          values=[c_["category_name_en"] for c_ in self._cats])
        cc.pack(side="left", padx=(8, 2))
        cc.set("Category…")
        self._btn(ar, "＋ Add", self._add_category, small=True).pack(side="left")
        self.msg_v = tk.StringVar(value="")
        tk.Label(self.frame, textvariable=self.msg_v, font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=16)

        # body: rows | preview
        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=14, pady=(2, 6))
        right = tk.Frame(body, bg=C["card_bg"], width=300, highlightbackground=C["border"],
                         highlightthickness=1)
        right.pack(side="right", fill="y", padx=(10, 0)); right.pack_propagate(False)
        left = tk.Frame(body, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True)

        cols = ("product", "unit", "barcode", "price", "offer", "copies")
        st = ttk.Style()
        try:
            st.configure("Labels.Treeview", rowheight=28, font=("Segoe UI", 10))
            st.configure("Labels.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        except Exception:
            pass
        tw = tk.Frame(left, bg=C["card_bg"]); tw.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree = ttk.Treeview(tw, columns=cols, show="headings", style="Labels.Treeview",
                                 selectmode="extended")
        for k, t, w, a in (("product", "Product", 230, "w"), ("unit", "Unit", 104, "w"),
                           ("barcode", "Barcode", 130, "w"), ("price", "Price (VAT)", 90, "e"),
                           ("offer", "Offer", 110, "w"), ("copies", "Copies", 70, "center")):
            self.tree.heading(k, text=t)
            self.tree.column(k, width=w, anchor=a, stretch=(k == "product"))
        vsb = ttk.Scrollbar(tw, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("nobc", foreground="#B91C1C", background="#FEF2F2")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<Double-1>", self._edit_copies_cell)
        self.tree.bind("<Delete>", lambda e: self._remove())
        self.tree.bind("<plus>", lambda e: self._bump(1))
        self.tree.bind("<KP_Add>", lambda e: self._bump(1))
        self.tree.bind("<minus>", lambda e: self._bump(-1))
        self.tree.bind("<KP_Subtract>", lambda e: self._bump(-1))
        self.empty = tk.Label(tw, text="No labels yet.\n\nScan a barcode or type a name above —\n"
                                       "or pick a category and press ＋ Add.",
                              font=("Segoe UI", 10), bg="white", fg=C["text_secondary"],
                              justify="center")

        bar = tk.Frame(left, bg=C["card_bg"]); bar.pack(fill="x", padx=6, pady=(0, 6))
        tk.Label(bar, text="Copies", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self._btn(bar, "−", lambda: self._bump(-1), small=True).pack(side="left", padx=(6, 1))
        self.copies_v = tk.StringVar(value="1")
        ce = tk.Entry(bar, textvariable=self.copies_v, width=5, justify="center",
                      font=("Segoe UI", 10), relief="solid", bd=1)
        ce.pack(side="left", ipady=2)
        ce.bind("<Return>", lambda e: self._set_copies(selected_only=True))
        self._btn(bar, "+", lambda: self._bump(1), small=True).pack(side="left", padx=(1, 6))
        self._btn(bar, "Set for all", lambda: self._set_copies(selected_only=False),
                  small=True).pack(side="left", padx=2)
        self._btn(bar, "= Stock", self._copies_from_stock, small=True).pack(side="left", padx=2)
        self._btn(bar, "🗑 Remove", self._remove, small=True, danger=True).pack(side="left", padx=(8, 2))
        self._btn(bar, "Clear all", self._clear, small=True).pack(side="left", padx=2)
        self.make_btn = self._btn(bar, "⚡ Make missing barcodes", self._make_barcodes, small=True)
        self.make_btn.pack(side="right")

        # preview
        tk.Label(right, text="Preview", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=10, pady=(8, 2))
        self.pv = tk.Canvas(right, bg="#E4E7EE", height=240, highlightthickness=0)
        self.pv.pack(fill="x", padx=8)
        self.pv_note = tk.StringVar()
        tk.Label(right, textvariable=self.pv_note, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"], wraplength=270, justify="left").pack(anchor="w", padx=10, pady=4)
        self.total_v = tk.StringVar()
        tk.Label(right, textvariable=self.total_v, font=("Segoe UI", 16, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=10, pady=(10, 0))
        tk.Label(right, text="Tips:\n• scan the same barcode again = +1 copy\n"
                             "• + / − keys change copies, Delete removes\n"
                             "• double-click Copies to type a number\n"
                             "• = Stock prints one label per item in stock",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                 justify="left").pack(anchor="w", padx=10, pady=(10, 0))

        # dropdown for name search
        self.drop = tk.Listbox(self.frame, font=("Segoe UI", 10), height=8, activestyle="none",
                               relief="solid", bd=1, highlightthickness=0,
                               selectbackground=C["primary"], selectforeground="white")
        self.drop.bind("<Return>", lambda e: self._drop_pick())
        self.drop.bind("<KP_Enter>", lambda e: self._drop_pick())
        self.drop.bind("<Double-1>", lambda e: self._drop_pick())
        self.drop.bind("<Escape>", lambda e: (self._drop_hide(), self.find_e.focus_set()))
        self._ph(True)

    def _ph(self, show):
        e = self.find_e
        if show and not self.find_v.get():
            e.configure(fg="#9CA3AF"); self.find_v.set(PLACEHOLDER)
        elif not show and self.find_v.get() == PLACEHOLDER:
            self.find_v.set(""); e.configure(fg="#111827")

    # ── search / scan ──────────────────────────────────────
    def _text(self):
        t = self.find_v.get().strip()
        return "" if t == PLACEHOLDER else t

    def _find_type(self, e=None):
        if e is not None and e.keysym in ("Return", "KP_Enter", "Down", "Up", "Escape"):
            return
        t = self._text()
        if len(t) < 2:
            self._drop_hide(); return
        from modules.product_lookup import search_products
        prods = search_products(t, limit=8, active_only=True)
        self._matches = []
        for p in prods:
            for r in BR.label_rows(p["product_id"]):
                self._matches.append(r)
            if len(self._matches) >= 12:
                break
        if not self._matches:
            self._drop_hide(); return
        self.drop.delete(0, "end")
        for r in self._matches:
            bc = r.get("barcode_value") or "no barcode"
            self.drop.insert("end", "  %s  ·  %s%s  ·  %.2f  ·  %s" % (
                r.get("product_name_en", ""), r.get("unit_name") or "-",
                (" ×%g" % r["factor"]) if abs(_f(r.get("factor"), 1) - 1) > 1e-9 else "",
                _f(r.get("price_vat")), bc))
        self.drop.selection_clear(0, "end"); self.drop.selection_set(0)
        try:
            self.frame.update_idletasks()
            x = self.find_e.winfo_rootx() - self.frame.winfo_rootx()
            y = self.find_e.winfo_rooty() - self.frame.winfo_rooty() + self.find_e.winfo_height() + 6
            self.drop.place(x=x - 30, y=y, width=max(420, self.find_e.winfo_width() + 30))
            self.drop.lift()
        except Exception:
            pass

    def _drop_hide(self):
        try:
            self.drop.place_forget()
        except Exception:
            pass

    def _drop_focus(self):
        if self.drop.winfo_ismapped():
            self.drop.focus_set()
            self.drop.selection_clear(0, "end"); self.drop.selection_set(0); self.drop.activate(0)
        return "break"

    def _drop_pick(self):
        sel = self.drop.curselection()
        i = sel[0] if sel else 0
        if 0 <= i < len(self._matches):
            r = self._matches[i]
            if self.every_v.get():
                self.add_product(r["product_id"], every_unit=True)
            else:
                self.add_row(r)
            self.msg_v.set("✔ %s · %s" % (r.get("product_name_en", ""), r.get("unit_name") or ""))
        self._drop_hide()
        self.find_v.set(""); self.find_e.focus_set()
        return "break"

    def _find_enter(self, e=None):
        t = self._text()
        if not t:
            return "break"
        if self.drop.winfo_ismapped() and self._matches and not BR.resolve(t, scale=True):
            return self._drop_pick()
        if self.scan(t):
            self._drop_hide()
            self.find_v.set(""); self.find_e.focus_set()
            return "break"
        self._find_type()
        if self._matches:
            return self._drop_pick() if len(self._matches) == 1 else self._drop_focus()
        self.msg_v.set("✖ Nothing found for “%s”" % t)
        self.frame.bell()
        return "break"

    def _add_category(self):
        name = self.cat_v.get()
        cat = next((c_ for c_ in self._cats if c_["category_name_en"] == name), None)
        if not cat:
            return
        try:
            ids = [r["product_id"] for r in (db.fetchall(
                "SELECT product_id FROM products WHERE category_id=? AND ISNULL(is_active,1)=1 "
                "ORDER BY product_name_en", (cat["category_id"],)) or [])]
        except Exception:
            ids = []
        for pid in ids:
            self.add_product(pid, every_unit=self.every_v.get(), render=False)
        self._render()
        self.msg_v.set("✔ %d product(s) from %s" % (len(ids), name))

    # ── rows ───────────────────────────────────────────────
    def _render(self, select=None):
        keep = select or [self._key(self.rows[int(i)]) for i in self.tree.selection()
                          if int(i) < len(self.rows)]
        if select is not None:
            keep = [select]
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            bc = r.get("barcode_value") or ""
            unit = (r.get("unit_name") or "") + ((" ×%g" % _f(r.get("factor"), 1))
                                                 if abs(_f(r.get("factor"), 1) - 1) > 1e-9 else "")
            price = _f(r.get("offer_price")) if r.get("offer_price") else _f(r.get("price_vat"))
            self.tree.insert("", "end", iid=str(i), values=(
                r.get("product_name_en", ""), unit, bc or "⚠ none", "%.2f" % price,
                r.get("offer_text") or "", r.get("copies", 1)),
                tags=(() if bc else ("nobc",)))
        sel = [str(i) for i, r in enumerate(self.rows) if self._key(r) in keep]
        if sel:
            self.tree.selection_set(sel); self.tree.see(sel[-1])
        if self.rows:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.45, anchor="center")
        n = sum(int(r.get("copies", 1)) for r in self.rows)
        self.total_v.set("%d label%s" % (n, "" if n == 1 else "s"))
        miss = sum(1 for r in self.rows if not r.get("barcode_value"))
        self.make_btn.configure(text=("⚡ Make %d missing barcode%s" % (miss, "" if miss == 1 else "s"))
                                if miss else "⚡ Make missing barcodes",
                                fg=self.C["danger"] if miss else self.C["text_primary"])
        try:
            self.print_btn.configure(text="🖨  Print %d label%s" % (n, "" if n == 1 else "s")
                                     if n else "🖨  Print labels")
        except Exception:
            pass
        self._preview()

    def _selected(self):
        return [self.rows[int(i)] for i in self.tree.selection() if int(i) < len(self.rows)]

    def _on_select(self):
        s = self._selected()
        if s:
            self.copies_v.set(str(s[0].get("copies", 1)))
        self._preview()

    def _bump(self, d):
        for r in self._selected() or self.rows[-1:]:
            r["copies"] = max(1, int(r.get("copies", 1)) + d)
        self._render()
        return "break"

    def _set_copies(self, selected_only=True):
        try:
            n = max(1, min(9999, int(float(self.copies_v.get()))))
        except ValueError:
            return
        for r in (self._selected() if selected_only else self.rows) or []:
            r["copies"] = n
        self._render()

    def _copies_from_stock(self):
        """One label per item in stock (in that unit: 120 PCs → 10 Box labels)."""
        for r in self._selected() or self.rows:
            stock = _f(r.get("stock_quantity"))
            r["copies"] = max(1, int(stock // max(1e-9, _f(r.get("factor"), 1))))
        self._render()

    def _edit_copies_cell(self, e):
        row = self.tree.identify_row(e.y)
        col = self.tree.identify_column(e.x)
        if not row or col != "#6":
            return
        x, y, w, h = self.tree.bbox(row, col)
        v = tk.StringVar(value=str(self.rows[int(row)].get("copies", 1)))
        ent = tk.Entry(self.tree, textvariable=v, justify="center", font=("Segoe UI", 10),
                       relief="solid", bd=1)
        ent.place(x=x, y=y, width=w, height=h); ent.focus_set(); ent.select_range(0, "end")

        def done(_e=None):
            try:
                self.rows[int(row)]["copies"] = max(1, min(9999, int(float(v.get()))))
            except ValueError:
                pass
            ent.destroy(); self._render()
        ent.bind("<Return>", done); ent.bind("<KP_Enter>", done); ent.bind("<FocusOut>", done)
        ent.bind("<Escape>", lambda _e: ent.destroy())

    def _remove(self):
        drop = {self._key(r) for r in self._selected()}
        self.rows = [r for r in self.rows if self._key(r) not in drop]
        self._render()

    def _clear(self):
        self.rows = []
        self._render()

    def _make_barcodes(self):
        """⚡ Every product + unit on the list gets its own barcode
        (Settings ▸ Barcode rules); the rows refresh with the new codes."""
        pids = sorted({r["product_id"] for r in self.rows if not r.get("barcode_value")})
        if not pids:
            self.msg_v.set("✔ Every label already has a barcode.")
            return []
        if not messagebox.askyesno(
                "Make barcodes", "Create a new barcode for %d product(s) / unit(s) without one?\n\n"
                "Each product and each unit (PCs, Box, Carton…) gets its own barcode, "
                "saved on the product." % sum(1 for r in self.rows if not r.get("barcode_value")),
                parent=self.frame):
            return []
        made = BR.ensure_barcodes(pids)
        fresh = {}
        for pid in pids:
            for r in BR.label_rows(pid):
                fresh[self._key(r)] = r
        for i, r in enumerate(self.rows):
            n = fresh.get(self._key(r))
            if n:
                cp = r.get("copies", 1)
                self.rows[i] = dict(n, copies=cp, company_name=self._company)
        self._render()
        self.msg_v.set("✔ %d barcode(s) created" % len(made))
        try:
            from modules import audit
            audit.log("edit", "products", None, "%d barcodes created (labels)" % len(made))
        except Exception:
            pass
        return made

    # ── design + preview ───────────────────────────────────
    def _on_design(self):
        t = self.template()
        if not t:
            self.size_v.set("No design yet — make one in Label Designer")
            self._tpl_id = None
            self._preview(); return
        self._tpl_id = t["template_id"]
        mode = "A4 sheet %s × %s" % (t.get("cols_per_sheet") or 3, t.get("rows_per_sheet") or 8) \
            if t.get("paper_mode") == "a4sheet" else "label roll"
        self.size_v.set("%g × %g mm · %s · %s" % (_f(t.get("label_width_mm"), 50),
                                                  _f(t.get("label_height_mm"), 25), mode,
                                                  str(t.get("barcode_type") or "code128").upper()))
        self._preview()

    def _make_default(self):
        t = self.template()
        if t:
            bd.set_default(t["template_id"])
            self.reload_designs(select_id=t["template_id"])
            self.msg_v.set("★ “%s” is now the default label design" % t["template_name"])

    def _edit_design(self):
        t = self.template()
        if self.on_edit_design:
            self.on_edit_design(t["template_id"] if t else None)

    def _preview(self):
        cv = self.pv
        cv.delete("all")
        self._imgs = []
        t = self.template()
        sel = self._selected()
        r = sel[0] if sel else (self.rows[0] if self.rows else None)
        if r is None:
            r = {"product_name_en": "Sample Product 1L", "product_name_ar": "منتج تجريبي",
                 "unit_name": "PCs", "price_vat": 9.5, "unit_price": 9.5,
                 "barcode_value": "6281000000014", "company_name": self._company}
        if not t:
            return
        lw, lh = _f(t.get("label_width_mm"), 50), _f(t.get("label_height_mm"), 25)
        W = max(240, cv.winfo_width() or 280)
        H = int(cv.cget("height"))
        k = min((W - 30) / lw, (H - 40) / lh)
        ox, oy = (W - lw * k) / 2, 16
        cv.create_rectangle(ox + 3, oy + 3, ox + lw * k + 3, oy + lh * k + 3, fill="#C7CCD6", outline="")
        cv.create_rectangle(ox, oy, ox + lw * k, oy + lh * k, fill="white", outline="#9CA3AF")
        layout = []
        try:
            layout = json.loads(t.get("layout_json") or "[]")
        except Exception:
            layout = []
        if not layout:
            layout = bd.starter_label_layout(lw, lh)
        fmt = t.get("barcode_type", "code128")
        for el in layout:
            key = el.get("key")
            x, y = _f(el.get("x"), 2), _f(el.get("y"), 2)
            w = max(4.0, min(_f(el.get("w"), 30), lw - x))
            if key in ("barcode", "qr"):
                val = str(r.get("barcode_value") or "")
                if not val:
                    cv.create_text(ox + (x + w / 2) * k, oy + (y + 4) * k, text="⚠ no barcode",
                                   fill="#B91C1C", font=("Segoe UI", 8, "bold"))
                    continue
                try:
                    from modules.barcode_gen import render_barcode
                    from PIL import ImageTk
                    if key == "qr":
                        side = min(w, lh - y)
                        img = render_barcode(val, "qr", 300, 300)
                        bw, bh = side, side
                    else:
                        bh = max(4.0, min(_f(el.get("bh"), 14), lh - y - 0.5))
                        img = render_barcode(val, fmt, 600, 200)
                        bw = w
                    if img is not None:
                        pw_, ph_ = max(1, int(bw * k)), max(1, int(bh * k))
                        sc = min(pw_ / img.width, ph_ / img.height)
                        img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))))
                        ph = ImageTk.PhotoImage(img)
                        self._imgs.append(ph)
                        cv.create_image(ox + x * k, oy + y * k, image=ph, anchor="nw")
                except Exception:
                    cv.create_rectangle(ox + x * k, oy + y * k, ox + (x + w) * k, oy + (y + 8) * k,
                                        outline="#888", dash=(3, 2))
                continue
            txt = bd._field_value(key, r, el)
            if txt in (None, ""):
                continue
            size = max(5, int(_f(el.get("font"), 8)))
            px = max(6, int(size * 0.3528 * k * 0.95))
            font = ("Segoe UI", -px, "bold" if el.get("bold") else "normal")
            row_mm = max(8.0, size * 0.3528 * 1.25)
            cy = oy + (y + row_mm / 2) * k
            al = el.get("align") or ("right" if key in ("product_name_ar", "unit_ar", "offer_text_ar")
                                     else "left")
            if al == "center":
                cv.create_text(ox + (x + w / 2) * k, cy, text=str(txt), font=font, fill="#111",
                               anchor="center", width=w * k)
            elif al == "right":
                cv.create_text(ox + (x + w - 0.5) * k, cy, text=str(txt), font=font, fill="#111",
                               anchor="e")
            else:
                cv.create_text(ox + (x + 0.5) * k, cy, text=str(txt), font=font, fill="#111",
                               anchor="w")
            if key == "old_price":
                bb = cv.bbox(cv.find_all()[-1])
                if bb:
                    cv.create_line(bb[0], (bb[1] + bb[3]) / 2, bb[2], (bb[1] + bb[3]) / 2, fill="#111")
        self.pv_note.set("%s · %s" % (r.get("product_name_en", ""), r.get("unit_name") or "")
                         if self.rows else "Sample — add products to see your own label.")

    # ── print ──────────────────────────────────────────────
    def items(self):
        out = []
        for r in self.rows:
            if not r.get("barcode_value"):
                continue
            it = dict(r)
            it["copies"] = int(r.get("copies", 1))
            out.append(it)
        return out

    def print_labels(self, to_printer=True, path=None):
        t = self.template()
        if not t:
            messagebox.showinfo("Labels", "Make a label design first (Label Designer).",
                                parent=self.frame)
            return None
        if not self.rows:
            messagebox.showinfo("Labels", "Scan or search a product first.", parent=self.frame)
            return None
        miss = [r for r in self.rows if not r.get("barcode_value")]
        if miss:
            if messagebox.askyesno("Labels", "%d row(s) have no barcode yet.\n\nMake their barcodes "
                                   "now (saved on the products)?" % len(miss), parent=self.frame):
                self._make_barcodes_quiet()
        items = self.items()
        if not items:
            messagebox.showwarning("Labels", "No row has a barcode to print.", parent=self.frame)
            return None
        if path is None:
            if to_printer:
                path = os.path.join(tempfile.gettempdir(), "daybill_labels.pdf")
            else:
                path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                                    filetypes=[("PDF", "*.pdf")],
                                                    initialfile="barcode_labels.pdf",
                                                    parent=self.frame)
                if not path:
                    return None
        try:
            bd.render_labels_pdf(t, items, path)
        except ImportError:
            messagebox.showerror("Missing Library", "pip install reportlab python-barcode qrcode pillow",
                                 parent=self.frame)
            return None
        except Exception as e:
            messagebox.showerror("Labels", str(e)[:250], parent=self.frame)
            return None
        n = sum(i["copies"] for i in items)
        self.last_pdf = path
        try:
            from modules import audit
            audit.log("print", "labels", None, "%d labels · %s" % (n, t.get("template_name")))
        except Exception:
            pass
        if to_printer:
            from ui import print_menu
            if print_menu.send_pdf(self.frame, path, "%d label(s)" % n, "labels"):
                self.msg_v.set("🖨 %d label(s) sent to the printer" % n)
        else:
            try:
                from modules import printer_service as ps
                ps.open_file(path)
            except Exception:
                pass
            self.msg_v.set("📄 %d label(s) saved: %s" % (n, path))
        return path

    def _make_barcodes_quiet(self):
        pids = sorted({r["product_id"] for r in self.rows if not r.get("barcode_value")})
        BR.ensure_barcodes(pids)
        fresh = {}
        for pid in pids:
            for r in BR.label_rows(pid):
                fresh[self._key(r)] = r
        for i, r in enumerate(self.rows):
            n = fresh.get(self._key(r))
            if n:
                self.rows[i] = dict(n, copies=r.get("copies", 1), company_name=self._company)
        self._render()


def open_window(parent, product_ids=None, every_unit=False):
    """Products list ▸ Print labels: the same panel in its own window."""
    C = cfg.theme()
    win = tk.Toplevel(parent)
    win.title("Print Barcode Labels")
    win.configure(bg=C["content_bg"])
    try:
        win.geometry("1080x640")
        win.transient(parent.winfo_toplevel())
    except Exception:
        pass
    win.bind("<Escape>", lambda e: win.destroy())
    panel = LabelPrintPanel(win, preselect=product_ids or [], every_unit=every_unit)
    win.panel = panel
    panel.find_e.focus_set()
    return win


def open_for_purchase(parent, purchase_id):
    """Purchases ▸ 🏷 Labels: one label per item received — each line's own
    unit (PCs / Box…), its barcode and price, copies = quantity bought."""
    try:
        lines = db.fetchall("SELECT product_id, unit_of_measure_en, quantity FROM "
                            "purchase_invoice_lines WHERE purchase_id=? AND product_id IS NOT NULL "
                            "ORDER BY line_id", (purchase_id,)) or []
    except Exception:
        lines = db.fetchall("SELECT product_id, unit_of_measure_en, quantity FROM "
                            "purchase_invoice_lines WHERE purchase_id=? AND product_id IS NOT NULL",
                            (purchase_id,)) or []
    win = open_window(parent, [])
    for ln in lines:
        q = _f(ln.get("quantity"))
        if q > 0:
            win.panel.add_unit_named(ln["product_id"], ln.get("unit_of_measure_en"), q, render=False)
    win.panel._render()
    win.panel.msg_v.set("✔ %d item(s) from the purchase — copies = quantity received" % len(lines))
    return win
