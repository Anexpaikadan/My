# ============================================================
# DayBill ERP - Product Units Manager
# Add/edit/delete units per product | EAN-13 auto-generate
# Barcode label print | Conversion factors | Per-unit pricing
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db
from modules.barcode_gen import generate_ean13, validate_ean13


def _can_edit(parent=None):
    """Units and barcodes are part of the product: they need products.edit."""
    from modules import permissions as perm
    return perm.allowed("products", "edit", parent=parent)


class UnitsManagerDialog:
    """
    Full multi-unit manager for a single product.
    Open from the product form.
    """
    def __init__(self, parent, product_id: int, product_name: str,
                 base_price: float = 0.0, on_close=None):
        self.product_id = product_id
        self.product_name = product_name
        self.base_price = base_price
        self.on_close = on_close
        C = cfg.theme()

        self.win = tk.Toplevel(parent)
        # Esc = the same as ✕ (refreshes the product form too)
        self.win.bind("<Escape>", lambda e=None: self._on_close())
        self.win.title(f"Units — {product_name}")
        self.win.geometry("860x600")
        self.win.configure(bg=C["content_bg"])
        self.win.grab_set()
        self._center(860, 600)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build(C)
        self._load()

    def _build(self, C):
        # Header
        hdr = tk.Frame(self.win, bg=C["primary"], height=50)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"📦  Units & Barcodes — {self.product_name}",
                 font=("Segoe UI", 12, "bold"), bg=C["primary"], fg="white").pack(
                     side="left", padx=16)

        # Left: unit list | Right: add/edit form
        body = tk.Frame(self.win, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # ── Unit list ─────────────────────────────────────────
        left = tk.Frame(body, bg=C["content_bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        tk.Label(left, text="Product Units", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(anchor="w", pady=(0, 4))

        card = tk.Frame(left, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)

        cols = ("name", "factor", "buy", "sell", "barcode", "default")
        heads = {"name": ("Unit Name", 100, "w"),
                 "factor": ("Qty/Base", 70, "center"),
                 "buy": ("Buy Price", 85, "e"),
                 "sell": ("Sell Price", 85, "e"),
                 "barcode": ("Barcode", 120, "center"),
                 "default": ("Default", 60, "center")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 yscrollcommand=vsb.set, height=14)
        vsb.config(command=self.tree.yview)
        for col in cols:
            h, w, a = heads[col]
            self.tree.heading(col, text=h); self.tree.column(col, width=w, anchor=a)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("default_row", background="#E8F5EE")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        btns = tk.Frame(left, bg=C["content_bg"])
        btns.pack(fill="x", pady=(6, 0))
        tk.Button(btns, text="🗑 Delete", font=("Segoe UI", 9), bg="#FEF2F2",
                  fg=C["danger"], relief="flat", padx=10, pady=5, cursor="hand2",
                  command=self._delete).pack(side="left")
        tk.Button(btns, text="⭐ Set Default", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["primary"], relief="flat", padx=10, pady=5, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._set_default).pack(side="left", padx=6)
        tk.Button(btns, text="🏷 Print Label", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=10, pady=5, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._print_label).pack(side="left")

        # ── Add/edit form ─────────────────────────────────────
        right = tk.Frame(body, bg=C["card_bg"], width=280,
                         highlightbackground=C["border"], highlightthickness=1)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Frame(right, bg=C["primary"], height=4).pack(fill="x")
        rinner = tk.Frame(right, bg=C["card_bg"])
        rinner.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(rinner, text="Add / Edit Unit", font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", pady=(0, 10))

        def lbl(txt, req=False):
            tk.Label(rinner, text=txt + (" *" if req else ""),
                     font=("Segoe UI", 9, "bold" if req else "normal"),
                     bg=C["card_bg"],
                     fg=C["primary"] if req else C["text_secondary"]).pack(anchor="w")

        def entry(var, justify="left"):
            e = tk.Entry(rinner, textvariable=var, font=("Segoe UI", 10), bg="white",
                         relief="solid", bd=1, justify=justify)
            e.pack(fill="x", ipady=5, pady=(2, 8))
            return e

        lbl("Unit Name (EN)", req=True)
        self.f_name_en = tk.StringVar(); entry(self.f_name_en)

        lbl("اسم الوحدة (AR)")
        self.f_name_ar = tk.StringVar(); entry(self.f_name_ar, "right")

        lbl("Conversion Factor *", req=True)
        self.f_factor = tk.StringVar(value="1")
        tk.Entry(rinner, textvariable=self.f_factor, font=("Segoe UI", 10),
                 bg="white", relief="solid", bd=1).pack(fill="x", ipady=5, pady=(2, 2))
        tk.Label(rinner, text="(how many pieces/base units = 1 of this unit)",
                 font=("Segoe UI", 7), bg=C["card_bg"], fg=C["text_secondary"]).pack(
                     anchor="w", pady=(0, 8))

        lbl("Purchase Price (SAR)")
        self.f_buy = tk.StringVar(); entry(self.f_buy)

        lbl("Selling Price (SAR)")
        self.f_sell = tk.StringVar(); entry(self.f_sell)

        locked = cfg.flag("barcode_system_locked", True)
        lbl("Barcode (auto · system)" if locked else "Primary Barcode")
        bc_row = tk.Frame(rinner, bg=C["card_bg"]); bc_row.pack(fill="x", pady=(2, 0))
        self.f_barcode = tk.StringVar()
        bce = tk.Entry(bc_row, textvariable=self.f_barcode, font=("Segoe UI", 9),
                       bg="white", relief="solid", bd=1)
        bce.pack(side="left", fill="x", expand=True, ipady=5)
        if locked:        # made by DayBill on save — shown, never typed
            bce.configure(state="readonly", readonlybackground="#EFEDF8")
        else:
            tk.Button(bc_row, text="⚡", font=("Segoe UI", 10), bg=C["primary_light"],
                      fg=C["primary"], relief="flat", padx=6, cursor="hand2",
                      command=self._auto_barcode).pack(side="left", padx=(4, 0))
        tk.Label(rinner, text=("Made by the system on save. A maker's barcode → 🏷 Multiple Barcodes."
                               if locked else "⚡ = auto-generate.  Leave blank to auto-create on save."),
                 font=("Segoe UI", 7), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(0, 4))

        # Multiple barcodes per unit (e.g. many "1 SR sweet" barcodes → 1 PCS unit)
        tk.Button(rinner, text="🏷 Manage Multiple Barcodes…",
                  font=("Segoe UI", 9, "bold"), bg=C["card_bg"], fg=C["primary"],
                  relief="flat", padx=10, pady=5, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._manage_barcodes).pack(anchor="w", pady=(0, 8))

        # Use as purchase / sales unit
        checks = tk.Frame(rinner, bg=C["card_bg"]); checks.pack(fill="x", pady=(0, 10))
        self.f_is_purchase = tk.BooleanVar(value=True)
        self.f_is_sales = tk.BooleanVar(value=True)
        tk.Checkbutton(checks, text="Use for Purchasing", variable=self.f_is_purchase,
                       font=("Segoe UI", 9), bg=C["card_bg"],
                       activebackground=C["card_bg"]).pack(anchor="w")
        tk.Checkbutton(checks, text="Use for Sales", variable=self.f_is_sales,
                       font=("Segoe UI", 9), bg=C["card_bg"],
                       activebackground=C["card_bg"]).pack(anchor="w")

        self.status_var = tk.StringVar()
        tk.Label(rinner, textvariable=self.status_var, font=("Segoe UI", 8),
                 bg=C["card_bg"], fg=C["danger"], wraplength=220).pack(anchor="w")

        btns2 = tk.Frame(rinner, bg=C["card_bg"]); btns2.pack(fill="x", pady=(6, 0))
        tk.Button(btns2, text="🔄 Clear", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=10, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._clear_form).pack(side="left", padx=(0, 6))
        tk.Button(btns2, text="💾 Save Unit", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self._save).pack(side="left")

        self._editing_id = None

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        try:
            rows = db.fetchall(
                "SELECT * FROM product_units WHERE product_id=? AND is_active=1 "
                "ORDER BY is_default DESC, unit_id", (self.product_id,))
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return
        for r in rows:
            tags = ("default_row",) if r.get("is_default") else ()
            self.tree.insert("", "end", iid=str(r["unit_id"]), values=(
                r["unit_name_en"],
                f"{float(r['conversion_factor']):g}",
                f"{float(r.get('purchase_price', 0)):,.2f}",
                f"{float(r.get('selling_price', 0)):,.2f}",
                r.get("barcode", "") or "—",
                "⭐ Yes" if r.get("is_default") else ""), tags=tags)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        uid = int(sel[0])
        try:
            r = db.fetchone("SELECT * FROM product_units WHERE unit_id=?", (uid,))
        except Exception:
            return
        if not r:
            return
        self._editing_id = uid
        self.f_name_en.set(r.get("unit_name_en", ""))
        self.f_name_ar.set(r.get("unit_name_ar", "") or "")
        self.f_factor.set(str(float(r.get("conversion_factor", 1))))
        self.f_buy.set(str(float(r.get("purchase_price", 0))))
        self.f_sell.set(str(float(r.get("selling_price", 0))))
        self.f_barcode.set(r.get("barcode", "") or "")
        self.f_is_purchase.set(bool(r.get("is_purchase_unit", 1)))
        self.f_is_sales.set(bool(r.get("is_sales_unit", 1)))
        self.status_var.set("")

    def _auto_barcode(self):
        """Auto-generate the next free barcode (Settings ▸ Barcode: 6-digit
        numbers in order by default), unique across every product and unit."""
        try:
            from modules.barcode_gen import new_unique_barcode
            candidate = new_unique_barcode()
            self.f_barcode.set(candidate)
            self.status_var.set(f"✅ Generated: {candidate}")
        except Exception as e:
            self.status_var.set(f"❌ {e}")

    def _gen_unique_barcode(self):
        """Fresh barcode per Settings ▸ Barcode, verified unused."""
        from modules.barcode_gen import new_unique_barcode
        return new_unique_barcode()

    def _manage_barcodes(self):
        """Open the multiple-barcodes manager for the selected/edited unit."""
        from tkinter import messagebox
        if not self._editing_id:
            messagebox.showinfo("Multiple Barcodes",
                "Select or save a unit first, then manage its barcodes.")
            return
        BarcodeListDialog(self.win, self.product_id, self._editing_id,
                          self._gen_unique_barcode)

    def _save(self):
        if not _can_edit(self.win):
            return
        name = self.f_name_en.get().strip()
        if not name:
            self.status_var.set("⚠️ Unit name is required."); return
        try:
            factor = float(self.f_factor.get() or 1)
            buy = float(self.f_buy.get() or 0)
            sell = float(self.f_sell.get() or 0)
        except ValueError:
            self.status_var.set("⚠️ Invalid number."); return

        barcode = self.f_barcode.get().strip() or None
        # only a 13-digit number must pass the EAN check; UPC-A (12),
        # EAN-8, Code128 / internal codes are accepted as typed
        if barcode and len(barcode) == 13 and barcode.isdigit() and not validate_ean13(barcode):
            self.status_var.set("⚠️ 13-digit barcode has a wrong check digit. "
                                "Re-scan it or use ⚡ to generate."); return
        if barcode:
            from modules.product_lookup import barcode_owner
            o = barcode_owner(barcode, exclude_unit_id=self._editing_id)
            if o and not (o["product_id"] == self.product_id and not self._editing_id
                          and o["where"] == "product barcode"):
                self.status_var.set(f"⚠️ {barcode} already used by {o['product_name']} "
                                    f"({o['unit_name']})."); return
        # If left blank, auto-generate a fresh barcode so every unit always has one
        if not barcode:
            barcode = self._gen_unique_barcode()

        try:
            from modules import price_watch as _pw
            _before = _pw.snapshot([self.product_id])
        except Exception:
            _before = None
        try:
            if self._editing_id:
                db.execute(
                    "UPDATE product_units SET unit_name_en=?, unit_name_ar=?, "
                    "conversion_factor=?, purchase_price=?, selling_price=?, "
                    "barcode=?, is_purchase_unit=?, is_sales_unit=? "
                    "WHERE unit_id=?",
                    (name, self.f_name_ar.get().strip() or None, factor,
                     buy, sell, barcode,
                     1 if self.f_is_purchase.get() else 0,
                     1 if self.f_is_sales.get() else 0,
                     self._editing_id))
                self.status_var.set(f"✅ '{name}' updated.")
            else:
                # Check if first unit → make default
                count = db.execute_scalar(
                    "SELECT COUNT(*) FROM product_units WHERE product_id=?",
                    (self.product_id,)) or 0
                is_def = 1 if count == 0 else 0
                db.execute(
                    "INSERT INTO product_units (product_id, unit_name_en, unit_name_ar, "
                    "conversion_factor, purchase_price, selling_price, barcode, "
                    "is_default, is_purchase_unit, is_sales_unit) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (self.product_id, name, self.f_name_ar.get().strip() or None,
                     factor, buy, sell, barcode, is_def,
                     1 if self.f_is_purchase.get() else 0,
                     1 if self.f_is_sales.get() else 0))
                # Update product default_unit_id if first
                if is_def:
                    uid = db.execute_scalar(
                        "SELECT TOP 1 unit_id FROM product_units WHERE product_id=? "
                        "ORDER BY unit_id DESC", (self.product_id,))
                    db.execute("UPDATE products SET default_unit_id=? WHERE product_id=?",
                               (uid, self.product_id))
                self.status_var.set(f"✅ '{name}' added.")
            # Make sure the primary barcode is also in the multi-barcode table
            self._register_barcode(barcode)
            try:
                if _before is not None:
                    _pw.record(_before, "units")
            except Exception:
                pass
            self._load()
            self._clear_form()
        except Exception as e:
            err = str(e)
            if "UQ_product_unit_barcode" in err or "UNIQUE" in err:
                self.status_var.set("❌ Barcode already used. Generate a new one.")
            else:
                self.status_var.set(f"❌ {err[:70]}")

    def _set_default(self):
        if not _can_edit(self.win):
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a unit first."); return
        uid = int(sel[0])
        try:
            db.execute("UPDATE product_units SET is_default=0 WHERE product_id=?",
                       (self.product_id,))
            db.execute("UPDATE product_units SET is_default=1 WHERE unit_id=?", (uid,))
            db.execute("UPDATE products SET default_unit_id=? WHERE product_id=?",
                       (uid, self.product_id))
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete(self):
        if not _can_edit(self.win):
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a unit first."); return
        uid = int(sel[0])
        name = self.tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("Delete", f"Delete unit '{name}'?"):
            return
        try:
            db.execute("UPDATE product_units SET is_active=0 WHERE unit_id=?", (uid,))
            self._load()
            self._clear_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _print_label(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a unit to print label."); return
        uid = int(sel[0])
        try:
            r = db.fetchone("SELECT * FROM product_units WHERE unit_id=?", (uid,))
            if not r or not r.get("barcode"):
                messagebox.showwarning("No Barcode",
                    "This unit has no barcode. Add one first."); return
            from tkinter import filedialog
            from modules.barcode_gen import print_barcode_label
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                initialfile=f"label_{r['barcode']}.pdf")
            if not path:
                return
            print_barcode_label(r["barcode"], self.product_name,
                                float(r.get("selling_price", 0)), path)
            messagebox.showinfo("✅", f"Label saved:\n{path}")
            try:
                import os; os.startfile(path)
            except Exception:
                pass
        except ImportError:
            messagebox.showerror("Missing Library", "pip install reportlab pillow")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _clear_form(self):
        self._editing_id = None
        self.f_name_en.set(""); self.f_name_ar.set("")
        self.f_factor.set("1"); self.f_buy.set(""); self.f_sell.set("")
        self.f_barcode.set(""); self.f_is_purchase.set(True); self.f_is_sales.set(True)
        self.status_var.set("")
        self.tree.selection_remove(*self.tree.selection())

    def _on_close(self):
        if self.on_close:
            self.on_close()
        self.win.destroy()

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _register_barcode(self, barcode, unit_id=None):
        """Insert a barcode into product_unit_barcodes if not already there."""
        if not barcode:
            return
        uid = unit_id or self._editing_id
        if not uid:
            # find the unit we just inserted
            uid = db.execute_scalar(
                "SELECT TOP 1 unit_id FROM product_units WHERE product_id=? "
                "ORDER BY unit_id DESC", (self.product_id,))
        if not uid:
            return
        try:
            exists = db.execute_scalar(
                "SELECT COUNT(*) FROM product_unit_barcodes WHERE barcode=?",
                (barcode,)) or 0
            if not exists:
                db.execute(
                    "INSERT INTO product_unit_barcodes (unit_id, product_id, barcode) "
                    "VALUES (?,?,?)", (uid, self.product_id, barcode))
        except Exception:
            # Table may not exist yet (patch not run) — ignore silently
            pass


# ════════════════════════════════════════════════════════════
# Multiple-barcodes manager for a single unit
# ════════════════════════════════════════════════════════════
class BarcodeListDialog:
    """
    Barcode Manager for ONE unit — matches the ERP spec: a table of
    every barcode (Barcode / Type / Default / Active) with Add, Edit,
    Delete, Generate, Scan, Set Default, and Print Barcode Labels.
    Use case: a '1 SR Sweet' PCS unit that should ring up from dozens
    of different sweet barcodes, or a unit with EAN-13 + an internal
    Code128 alias.
    """
    BARCODE_TYPES = ["EAN-13", "EAN-8", "UPC", "Code128", "Code39", "QR"]

    def __init__(self, parent, product_id, unit_id, gen_func, product_name=""):
        self.product_id = product_id
        self.unit_id = unit_id
        self.gen_func = gen_func
        self.product_name = product_name
        C = cfg.theme()
        self.C = C

        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e=None: self.win.destroy())
        self.win.title("Barcode Manager")
        self.win.geometry("560x520")
        self.win.configure(bg=C["content_bg"])
        self.win.grab_set()

        tk.Label(self.win, text="🏷  Barcode Manager",
                 font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white", pady=12).pack(fill="x")
        tk.Label(self.win,
                 text="Every barcode listed here rings up as this unit. Add as "
                      "many as you need (e.g. several 1 SR sweets → one PCS unit).",
                 font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"],
                 wraplength=520, justify="left").pack(anchor="w", padx=16, pady=(10, 6))

        # ── Add row ──
        addrow = tk.Frame(self.win, bg=C["content_bg"]); addrow.pack(fill="x", padx=16)
        self.bc_var = tk.StringVar()
        tk.Entry(addrow, textvariable=self.bc_var, font=("Segoe UI", 10),
                 bg="white", relief="solid", bd=1).pack(side="left", fill="x",
                                                         expand=True, ipady=5)
        self.type_var = tk.StringVar(value="EAN-13")
        ttk.Combobox(addrow, textvariable=self.type_var, values=self.BARCODE_TYPES,
                     state="readonly", width=9, font=("Segoe UI", 9)).pack(
                         side="left", padx=4)
        tk.Button(addrow, text="⚡ Generate", font=("Segoe UI", 9), bg=C["primary_light"],
                  fg=C["primary"], relief="flat", padx=8, cursor="hand2",
                  command=self._generate).pack(side="left", padx=2)
        tk.Button(addrow, text="➕ Add", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=10, cursor="hand2",
                  command=self._add).pack(side="left")

        tk.Label(self.win, text="Tip: click in the box and SCAN a barcode to add it fast.",
                 font=("Segoe UI", 7), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=16, pady=(2, 8))

        # ── Table ──
        card = tk.Frame(self.win, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        cols = ("barcode", "type", "default", "active")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=10)
        for cid, txt, w, anc in [("barcode", "Barcode", 180, "w"),
                                 ("type", "Type", 80, "center"),
                                 ("default", "Default", 70, "center"),
                                 ("active", "Active", 60, "center")]:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=anc)
        ysb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e=None: self._edit())

        # ── row actions ──
        row_actions = tk.Frame(self.win, bg=C["content_bg"])
        row_actions.pack(fill="x", padx=16, pady=(0, 4))
        for txt, cmd in [("✎ Edit", self._edit), ("★ Set Default", self._set_default),
                         ("🗑 Delete", self._remove), ("🚫 Toggle Active", self._toggle_active)]:
            tk.Button(row_actions, text=txt, font=("Segoe UI", 8, "bold"),
                      bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=8,
                      pady=4, cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1, command=cmd).pack(side="left", padx=(0, 4))

        btns = tk.Frame(self.win, bg=C["content_bg"]); btns.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(btns, text="🖨 Print Barcode Labels", font=("Segoe UI", 9, "bold"),
                  bg=C["accent"], fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._print_labels).pack(side="left")
        tk.Button(btns, text="Close", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self.win.destroy).pack(side="right")

        self.status = tk.StringVar()
        tk.Label(self.win, textvariable=self.status, font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=16)

        self._load()

    def _load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = db.fetchall(
                "SELECT barcode_id, barcode, barcode_type, is_default, is_active "
                "FROM product_unit_barcodes WHERE unit_id=? ORDER BY "
                "is_default DESC, barcode_id", (self.unit_id,)) or []
            for r in rows:
                self.tree.insert("", "end", iid=str(r["barcode_id"]), values=(
                    r["barcode"], r.get("barcode_type") or "EAN-13",
                    "★" if r.get("is_default") else "", "✓" if r.get("is_active", 1) else "✕"))
            self.status.set(f"{len(rows)} barcode(s).")
        except Exception:
            self.status.set("⚠️ Run product_extras_patch.sql for barcode type/default.")

    def _generate(self):
        self.bc_var.set(self.gen_func())

    def _add(self):
        if not _can_edit(self.win):
            return
        bc = self.bc_var.get().strip()
        if not bc:
            self.status.set("Enter or scan a barcode, or click ⚡ Generate."); return
        try:
            exists = db.execute_scalar(
                "SELECT COUNT(*) FROM product_unit_barcodes WHERE barcode=?", (bc,)) or 0
            if exists:
                self.status.set("⚠ That barcode is already used (must be unique "
                               "across all products/units)."); return
            has_any = db.execute_scalar(
                "SELECT COUNT(*) FROM product_unit_barcodes WHERE unit_id=?",
                (self.unit_id,)) or 0
            db.execute(
                "INSERT INTO product_unit_barcodes (unit_id, product_id, barcode, "
                "barcode_type, is_default) VALUES (?,?,?,?,?)",
                (self.unit_id, self.product_id, bc, self.type_var.get(),
                 0 if has_any else 1))   # first barcode added becomes default
            self.bc_var.set("")
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _edit(self):
        if not _can_edit(self.win):
            return
        bid = self._selected_id()
        if not bid:
            self.status.set("Select a barcode to edit."); return
        from tkinter import simpledialog
        row = db.fetchone("SELECT barcode FROM product_unit_barcodes WHERE barcode_id=?",
                          (bid,))
        new_val = simpledialog.askstring("Edit Barcode", "Barcode:",
                                         initialvalue=row["barcode"] if row else "",
                                         parent=self.win)
        if not new_val:
            return
        try:
            dup = db.execute_scalar(
                "SELECT COUNT(*) FROM product_unit_barcodes WHERE barcode=? "
                "AND barcode_id<>?", (new_val, bid)) or 0
            if dup:
                self.status.set("⚠ That barcode is already used elsewhere."); return
            db.execute("UPDATE product_unit_barcodes SET barcode=? WHERE barcode_id=?",
                      (new_val, bid))
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _set_default(self):
        if not _can_edit(self.win):
            return
        bid = self._selected_id()
        if not bid:
            self.status.set("Select a barcode first."); return
        try:
            db.execute("UPDATE product_unit_barcodes SET is_default=0 WHERE unit_id=?",
                      (self.unit_id,))
            db.execute("UPDATE product_unit_barcodes SET is_default=1 WHERE barcode_id=?",
                      (bid,))
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _toggle_active(self):
        if not _can_edit(self.win):
            return
        bid = self._selected_id()
        if not bid:
            self.status.set("Select a barcode first."); return
        try:
            db.execute(
                "UPDATE product_unit_barcodes SET is_active = 1 - ISNULL(is_active,1) "
                "WHERE barcode_id=?", (bid,))
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _remove(self):
        if not _can_edit(self.win):
            return
        bid = self._selected_id()
        if not bid:
            self.status.set("Select a barcode to remove."); return
        if not messagebox.askyesno("Delete Barcode", "Remove this barcode?", parent=self.win):
            return
        try:
            db.execute("DELETE FROM product_unit_barcodes WHERE barcode_id=?", (bid,))
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _print_labels(self):
        try:
            rows = db.fetchall(
                "SELECT barcode FROM product_unit_barcodes WHERE unit_id=? "
                "AND ISNULL(is_active,1)=1", (self.unit_id,)) or []
        except Exception:
            rows = []
        if not rows:
            self.status.set("No active barcodes to print."); return
        try:
            import tempfile, os as _os
            from ui.label_print import generate_label_sheet
            items = [{"name": self.product_name, "price": "", "barcode": r["barcode"],
                     "copies": 1} for r in rows]
            out = _os.path.join(tempfile.gettempdir(), "unit_barcode_labels.pdf")
            generate_label_sheet(items, out, 3, 8)
            if _os.name == "nt":
                _os.startfile(out)
            else:
                self.status.set(f"Saved: {out}")
        except Exception as e:
            self.status.set(f"❌ Print failed: {str(e)[:80]}")


# ============================================================
# MultiBarcodeBox — the "MB" auto-popup (Polosys-style)
# ------------------------------------------------------------
# One window: pick ANY unit of this product from a dropdown at the
# top, then scan/type/generate as many barcodes as needed for that
# unit — switch units any time without closing the box. Opens
# automatically after Save when the product form's "MB" checkbox is
# ticked (ui/products.py wires this).
# ============================================================
class MultiBarcodeBox(tk.Toplevel):
    BARCODE_TYPES = ["EAN-13", "EAN-8", "UPC", "Code128", "Code39", "QR"]

    def __init__(self, parent, product_id, product_name="", unit_id=None,
                 on_close=None):
        super().__init__(parent)
        self.product_id = product_id
        self.product_name = product_name
        self.unit_id = None
        self._want_unit = unit_id
        self._on_close_cb = on_close
        try:
            self.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._close)
        C = cfg.theme()
        self.C = C

        self.bind("<Escape>", lambda e=None: self._close())
        self.title("Multi Barcode")
        self.geometry("660x580")
        self.configure(bg=C["content_bg"])
        self.grab_set()

        tk.Label(self, text="🏷  Multi Barcode Entry",
                 font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white", pady=12).pack(fill="x")
        tk.Label(self, text=product_name, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(anchor="w",
                                                                padx=16, pady=(10, 0))

        # ── Unit picker — every unit on this product ──
        urow = tk.Frame(self, bg=C["content_bg"]); urow.pack(fill="x", padx=16, pady=(6, 4))
        tk.Label(urow, text="Unit", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left", padx=(0, 8))
        self.unit_var = tk.StringVar()
        self.unit_cb = ttk.Combobox(urow, textvariable=self.unit_var, state="readonly",
                                    font=("Segoe UI", 10), width=22)
        self.unit_cb.pack(side="left")
        self.unit_cb.bind("<<ComboboxSelected>>", lambda e=None: self._on_unit_change())
        tk.Label(urow, text="  ← pick a unit, then scan/add its barcodes below",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")

        tk.Label(self,
                 text="Every barcode listed here rings up as the selected unit. "
                      "Add as many as you need, switch units any time.",
                 font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"],
                 wraplength=540, justify="left").pack(anchor="w", padx=16, pady=(4, 6))

        # ── Add row (scan lands here) ──
        addrow = tk.Frame(self, bg=C["content_bg"]); addrow.pack(fill="x", padx=16)
        self.bc_var = tk.StringVar()
        self.bc_entry = tk.Entry(addrow, textvariable=self.bc_var, font=("Segoe UI", 10),
                                 bg="white", relief="solid", bd=1)
        self.bc_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.bc_entry.bind("<Return>", lambda e=None: self._add())
        self.type_var = tk.StringVar(value="EAN-13")
        ttk.Combobox(addrow, textvariable=self.type_var, values=self.BARCODE_TYPES,
                     state="readonly", width=9, font=("Segoe UI", 9)).pack(
                         side="left", padx=4)
        tk.Button(addrow, text="⚡ Generate", font=("Segoe UI", 9), bg=C["primary_light"],
                  fg=C["primary"], relief="flat", padx=8, cursor="hand2",
                  command=self._generate).pack(side="left", padx=2)
        tk.Button(addrow, text="➕ Add", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=10, cursor="hand2",
                  command=self._add).pack(side="left")

        tk.Label(self, text="Tip: click in the box and SCAN a barcode — Enter (or the "
                 "scanner's own Enter) adds it and clears the box for the next scan.",
                 font=("Segoe UI", 7), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=16, pady=(2, 8))

        # ── Table ──
        card = tk.Frame(self, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        cols = ("barcode", "type", "default", "active")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=10)
        for cid, txt, w, anc in [("barcode", "Barcode", 200, "w"),
                                 ("type", "Type", 80, "center"),
                                 ("default", "Default", 70, "center"),
                                 ("active", "Active", 60, "center")]:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=anc)
        ysb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e=None: self._edit())

        row_actions = tk.Frame(self, bg=C["content_bg"])
        row_actions.pack(fill="x", padx=16, pady=(0, 4))
        for txt, cmd in [("✎ Edit", self._edit), ("★ Set Default", self._set_default),
                         ("🗑 Delete", self._remove), ("🚫 Toggle Active", self._toggle_active)]:
            tk.Button(row_actions, text=txt, font=("Segoe UI", 8, "bold"),
                      bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=8,
                      pady=4, cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1, command=cmd).pack(side="left", padx=(0, 4))

        btns = tk.Frame(self, bg=C["content_bg"]); btns.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(btns, text="🖨 Print Barcode Labels", font=("Segoe UI", 9, "bold"),
                  bg=C["accent"], fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._print_labels).pack(side="left")
        tk.Button(btns, text="✓ Done / Save & Close", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._close).pack(side="right")

        self.status = tk.StringVar()
        tk.Label(self, textvariable=self.status, font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=16)

        self._load_units()

    # ── unit list / switching ──
    def _load_units(self):
        try:
            self._units = db.fetchall(
                "SELECT unit_id, unit_name_en FROM product_units "
                "WHERE product_id=? AND is_active=1 ORDER BY conversion_factor",
                (self.product_id,)) or []
        except Exception:
            self._units = []
        if not self._units:
            self.unit_cb["values"] = ["(no units saved yet)"]
            self.unit_cb.current(0)
            self.status.set("This product has no saved units — add units first "
                            "(Units & Barcode tab), then reopen Multi Barcode.")
            return
        names = [u["unit_name_en"] for u in self._units]
        self.unit_cb["values"] = names
        idx = next((i for i, u in enumerate(self._units)
                    if u["unit_id"] == self._want_unit), 0)
        self.unit_cb.current(idx)
        self.unit_id = self._units[idx]["unit_id"]
        self._load()
        self.after(50, self.bc_entry.focus_set)

    def _close(self):
        cb = self._on_close_cb
        self.destroy()
        if cb:
            try:
                cb()
            except Exception:
                pass

    def _owner_msg(self, bc, exclude_barcode_id=None):
        """'' if the barcode is free, else who already uses it."""
        from modules.product_lookup import barcode_owner
        o = barcode_owner(bc)
        if not o:
            return ""
        if exclude_barcode_id:
            row = db.fetchone("SELECT barcode FROM product_unit_barcodes WHERE barcode_id=?",
                              (exclude_barcode_id,)) or {}
            if row.get("barcode") == bc:
                return ""
        if o["product_id"] == self.product_id:
            return f"⚠ {bc} is already on this product ({o['unit_name']} unit)."
        return f"⚠ {bc} is already used by {o['product_name']} ({o['unit_name']})."

    def _on_unit_change(self):
        i = self.unit_cb.current()
        if 0 <= i < len(getattr(self, "_units", [])):
            self.unit_id = self._units[i]["unit_id"]
            self._load()

    # ── barcode CRUD (scoped to the currently selected unit) ──
    def _load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        if not self.unit_id:
            return
        try:
            rows = db.fetchall(
                "SELECT barcode_id, barcode, barcode_type, is_default, is_active "
                "FROM product_unit_barcodes WHERE unit_id=? ORDER BY "
                "is_default DESC, barcode_id", (self.unit_id,)) or []
            for r in rows:
                self.tree.insert("", "end", iid=str(r["barcode_id"]), values=(
                    r["barcode"], r.get("barcode_type") or "EAN-13",
                    "★" if r.get("is_default") else "",
                    "✓" if r.get("is_active", 1) else "✕"))
            self.status.set(f"{len(rows)} barcode(s) for this unit.")
        except Exception:
            self.status.set("⚠️ Run product_extras_patch.sql for barcode type/default.")

    def _gen_unique_barcode(self):
        """Fresh barcode per Settings ▸ Barcode, verified unused."""
        from modules.barcode_gen import new_unique_barcode
        return new_unique_barcode()

    def _generate(self):
        self.bc_var.set(self._gen_unique_barcode())

    def _add(self):
        if not _can_edit(self):
            return
        if not self.unit_id:
            self.status.set("Pick a unit first."); return
        bc = self.bc_var.get().strip()
        if not bc:
            self.status.set("Enter or scan a barcode, or click ⚡ Generate."); return
        try:
            taken = self._owner_msg(bc)
            if taken:
                self.status.set(taken)
                self.bell()
                self.bc_entry.select_range(0, "end")
                return
            has_any = db.execute_scalar(
                "SELECT COUNT(*) FROM product_unit_barcodes WHERE unit_id=?",
                (self.unit_id,)) or 0
            db.execute(
                "INSERT INTO product_unit_barcodes (unit_id, product_id, barcode, "
                "barcode_type, is_default) VALUES (?,?,?,?,?)",
                (self.unit_id, self.product_id, bc, self.type_var.get(),
                 0 if has_any else 1))
            self.bc_var.set("")
            self._load()
            self.status.set(f"✅ Added {bc}  —  " + self.status.get())
            self.bc_entry.focus_set()      # ready for the next scan immediately
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _edit(self):
        if not _can_edit(self):
            return
        bid = self._selected_id()
        if not bid:
            self.status.set("Select a barcode to edit."); return
        from tkinter import simpledialog
        row = db.fetchone("SELECT barcode FROM product_unit_barcodes WHERE barcode_id=?",
                          (bid,))
        new_val = simpledialog.askstring("Edit Barcode", "Barcode:",
                                         initialvalue=(row or {}).get("barcode", ""),
                                         parent=self)
        if new_val and new_val.strip():
            taken = self._owner_msg(new_val.strip(), exclude_barcode_id=bid)
            if taken:
                self.status.set(taken); return
            try:
                db.execute("UPDATE product_unit_barcodes SET barcode=? WHERE barcode_id=?",
                          (new_val.strip(), bid))
                self._load()
            except Exception as e:
                self.status.set(f"❌ {str(e)[:60]}")

    def _set_default(self):
        if not _can_edit(self):
            return
        bid = self._selected_id()
        if not bid or not self.unit_id:
            self.status.set("Select a barcode to set as default."); return
        try:
            db.execute("UPDATE product_unit_barcodes SET is_default=0 WHERE unit_id=?",
                      (self.unit_id,))
            db.execute("UPDATE product_unit_barcodes SET is_default=1 WHERE barcode_id=?",
                      (bid,))
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _remove(self):
        if not _can_edit(self):
            return
        bid = self._selected_id()
        if not bid:
            self.status.set("Select a barcode to delete."); return
        if not messagebox.askyesno("Delete Barcode", "Remove this barcode?", parent=self):
            return
        try:
            db.execute("DELETE FROM product_unit_barcodes WHERE barcode_id=?", (bid,))
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _toggle_active(self):
        if not _can_edit(self):
            return
        bid = self._selected_id()
        if not bid:
            self.status.set("Select a barcode."); return
        try:
            db.execute(
                "UPDATE product_unit_barcodes SET is_active = "
                "CASE WHEN ISNULL(is_active,1)=1 THEN 0 ELSE 1 END WHERE barcode_id=?",
                (bid,))
            self._load()
        except Exception as e:
            self.status.set(f"❌ {str(e)[:60]}")

    def _print_labels(self):
        if not self.unit_id:
            return
        try:
            rows = db.fetchall(
                "SELECT barcode FROM product_unit_barcodes WHERE unit_id=? "
                "AND ISNULL(is_active,1)=1", (self.unit_id,)) or []
        except Exception:
            rows = []
        if not rows:
            self.status.set("No active barcodes to print."); return
        try:
            import tempfile, os as _os
            from ui.label_print import generate_label_sheet
            items = [{"name": self.product_name, "price": "", "barcode": r["barcode"],
                     "copies": 1} for r in rows]
            out = _os.path.join(tempfile.gettempdir(), "unit_barcode_labels.pdf")
            generate_label_sheet(items, out, 3, 8)
            if _os.name == "nt":
                _os.startfile(out)
            else:
                self.status.set(f"Saved: {out}")
        except Exception as e:
            self.status.set(f"❌ Print failed: {str(e)[:80]}")
