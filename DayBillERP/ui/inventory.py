# ============================================================
# DayBill ERP - Inventory Management Module
# Stock levels | Movements ledger | Manual adjustments
# Low stock alerts | Purchase auto-update integration
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db


# ── Compatibility wrappers ─────────────────────────────────────
# Stock for documents is handled by modules/doc_posting (one engine:
# draft = nothing, confirmed = stock + journal, edits re-sync). These
# old entry points are kept so any external caller keeps working.
def update_stock_from_purchase(db_conn, purchase_id: int):
    from modules import doc_posting
    return doc_posting.sync("purchase", purchase_id)


def update_stock_from_sale(db_conn, invoice_id: int):
    from modules import doc_posting
    return doc_posting.sync("sales", invoice_id)


# ── UI ────────────────────────────────────────────────────────
class InventoryView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._topbar(C)
        self._tabs(C)

    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="📦  Inventory", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="⚙ Adjust Stock", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._adjust).pack(side="right")
        tk.Button(bar, text="🧮 Stock Count", font=("Segoe UI", 10, "bold"),
                  bg=C["card_bg"], fg=C["primary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=self._stock_count).pack(side="right", padx=(0, 8))
        # Clear Stock zeroes the whole branch: only shown with the approve right
        from modules import permissions as _pm
        if _pm.can("stock_adjustment", "approve"):
            tk.Button(bar, text="🧹 Clear Stock", font=("Segoe UI", 10, "bold"),
                      bg="#FEF2F2", fg=C["danger"], relief="flat", padx=14, pady=7,
                      cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1,
                      command=self._clear_stock).pack(side="right", padx=(0, 8))

    def _tabs(self, C):
        style = ttk.Style()
        style.configure("INV.TNotebook", background=C["content_bg"], borderwidth=0)
        style.configure("INV.TNotebook.Tab", font=("Segoe UI", 10), padding=(14, 8))
        nb = ttk.Notebook(self.frame, style="INV.TNotebook")
        nb.pack(fill="both", expand=True, padx=24, pady=14)

        self.t_stock = tk.Frame(nb, bg=C["content_bg"])
        self.t_moves = tk.Frame(nb, bg=C["content_bg"])
        self.t_low = tk.Frame(nb, bg=C["content_bg"])
        nb.add(self.t_stock, text="  📊  Stock Levels  ")
        nb.add(self.t_moves, text="  📋  Movements  ")
        nb.add(self.t_low, text="  ⚠️  Low Stock  ")

        self._build_stock(self.t_stock, C)
        self._build_movements(self.t_moves, C)
        self._build_low(self.t_low, C)

    # ── Stock Levels ──────────────────────────────────────────
    def _build_stock(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"])
        bar.pack(fill="x", pady=(10, 8))
        sf = tk.Frame(bar, bg="white", highlightbackground=C["border"], highlightthickness=1)
        sf.pack(side="left")
        tk.Label(sf, text="🔍", bg="white", fg=C["text_secondary"],
                 font=("Segoe UI Emoji", 11)).pack(side="left", padx=(8, 4))
        self.stock_search = tk.StringVar()
        self.stock_search.trace("w", lambda *a: self._load_stock())
        tk.Entry(sf, textvariable=self.stock_search, font=("Segoe UI", 10), bg="white",
                 relief="flat", width=26).pack(side="left", ipady=7, padx=(0, 8))
        self.stock_count = tk.StringVar()
        tk.Label(bar, textvariable=self.stock_count, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right")
        tk.Button(bar, text="🖨 Print", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: self._export_stock("pdf")).pack(side="right", padx=(0, 8))
        tk.Button(bar, text="📥 Export Excel", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=lambda: self._export_stock("excel")).pack(side="right", padx=(0, 8))

        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("code", "product", "stock", "unit", "buy", "sell", "profit", "reorder", "status")
        h = {"code": ("Code", 80, "center"), "product": ("Product", 200, "w"),
             "stock": ("Stock", 90, "e"), "unit": ("Unit", 70, "center"),
             "buy": ("Cost", 90, "e"), "sell": ("Price", 90, "e"),
             "profit": ("Margin%", 80, "center"),
             "reorder": ("Reorder", 80, "e"), "status": ("Status", 90, "center")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.stock_tree = ttk.Treeview(card, columns=cols, show="headings",
                                       yscrollcommand=vsb.set)
        vsb.config(command=self.stock_tree.yview)
        for col in cols:
            lbl, w, a = h[col]
            self.stock_tree.heading(col, text=lbl); self.stock_tree.column(col, width=w, anchor=a)
        self.stock_tree.pack(fill="both", expand=True)
        self.stock_tree.tag_configure("low", background="#FEF2F2", foreground="#DC2626")
        self.stock_tree.tag_configure("ok", background="#F0FDF4")
        self._load_stock()

    def _export_stock(self, mode="excel"):
        from modules import permissions as _pm
        if not _pm.allowed("inventory", "export"):
            return False
        rows = [list(self.stock_tree.item(i)["values"])
                for i in self.stock_tree.get_children()]
        if not rows:
            messagebox.showinfo("Nothing to export", "No stock to export.")
            return
        headers = ["Code", "Product", "Stock", "Unit", "Cost", "Price",
                   "Margin%", "Reorder", "Status"]
        try:
            if mode == "pdf":
                from modules.report_export import export_pdf
                export_pdf(self.frame, "Stock_Report", headers, rows, title="Stock Report")
            else:
                from modules.report_export import export_excel
                export_excel(self.frame, "Stock_Report", headers, rows, title="Stock Report")
        except ImportError:
            messagebox.showerror("Missing Library", "pip install openpyxl reportlab")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _load_stock(self):
        q = self.stock_search.get().lower() if hasattr(self, "stock_search") else ""
        try:
            rows = db.fetchall(
                "SELECT p.product_id, p.product_code, p.product_name_en, "
                "ISNULL(p.stock_quantity,0) AS stock, "
                "ISNULL(p.purchase_price,0) AS buy, "
                "p.unit_price AS sell, "
                "ISNULL(p.reorder_level,0) AS reorder, "
                "ISNULL(pu.unit_name_en,'Unit') AS unit_name "
                "FROM products p "
                "LEFT JOIN product_units pu ON p.default_unit_id=pu.unit_id "
                "WHERE p.is_active=1 AND p.product_type='product' "
                "ORDER BY p.product_name_en")
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return

        self.stock_tree.delete(*self.stock_tree.get_children())
        count = 0
        for r in rows:
            if q and q not in (str(r.get("product_code","")) + str(r.get("product_name_en",""))).lower():
                continue
            stock = float(r.get("stock", 0))
            buy = float(r.get("buy", 0))
            sell = float(r.get("sell", 0))
            reorder = float(r.get("reorder", 0))
            margin = round((sell - buy) / sell * 100, 1) if sell > 0 else 0
            is_low = stock <= reorder
            tag = "low" if is_low else "ok"
            status = "⚠️ Low" if is_low else "✅ OK"
            self.stock_tree.insert("", "end", values=(
                r.get("product_code", ""), r.get("product_name_en", ""),
                f"{stock:,.2f}", r.get("unit_name", "Unit"),
                f"{buy:,.2f}", f"{sell:,.2f}",
                f"{margin:.1f}%", f"{reorder:,.0f}", status), tags=(tag,))
            count += 1
        self.stock_count.set(f"{count} products")

    # ── Movements ─────────────────────────────────────────────
    def _build_movements(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"]); bar.pack(fill="x", pady=(10, 8))
        tk.Label(bar, text="From:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.mv_from = tk.StringVar(value=date.today().replace(day=1).strftime("%Y-%m-%d"))
        _mvf = tk.Entry(bar, textvariable=self.mv_from, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1)
        _mvf.pack(side="left", padx=(4, 10))
        tk.Label(bar, text="To:", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.mv_to = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        _mvt = tk.Entry(bar, textvariable=self.mv_to, width=12, font=("Segoe UI", 9),
                 relief="solid", bd=1)
        _mvt.pack(side="left", padx=(4, 10))
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(_mvf, self.mv_from)
            attach_datepicker(_mvt, self.mv_to)
        except Exception:
            pass
        tk.Button(bar, text="🔍 Load", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._load_moves).pack(side="left")

        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("date", "product", "type", "ref", "in_qty", "out_qty", "balance")
        h = {"date": ("Date", 100, "center"), "product": ("Product", 200, "w"),
             "type": ("Type", 110, "center"), "ref": ("Reference", 130, "center"),
             "in_qty": ("In", 90, "e"), "out_qty": ("Out", 90, "e"),
             "balance": ("Balance", 90, "e")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.mv_tree = ttk.Treeview(card, columns=cols, show="headings",
                                    yscrollcommand=vsb.set)
        vsb.config(command=self.mv_tree.yview)
        for col in cols:
            lbl, w, a = h[col]
            self.mv_tree.heading(col, text=lbl); self.mv_tree.column(col, width=w, anchor=a)
        self.mv_tree.pack(fill="both", expand=True)
        self.mv_tree.tag_configure("in_row", background="#F0FDF4")
        self.mv_tree.tag_configure("out_row", background="#FEF2F2")
        self._load_moves()

    def _load_moves(self):
        self.mv_tree.delete(*self.mv_tree.get_children())
        try:
            rows = db.fetchall(
                "SELECT it.txn_date, p.product_name_en, it.txn_type, "
                "it.reference_type, it.reference_id, "
                "it.qty_in_base, it.qty_out_base, it.balance_base "
                "FROM inventory_transactions it "
                "JOIN products p ON it.product_id=p.product_id "
                "WHERE it.txn_date BETWEEN ? AND ? "
                "ORDER BY it.txn_date DESC, it.txn_id DESC",
                (self.mv_from.get(), self.mv_to.get()))
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return
        for r in rows:
            qi = float(r.get("qty_in_base", 0))
            qo = float(r.get("qty_out_base", 0))
            ref = f"{r.get('reference_type','')} #{r.get('reference_id','')}"
            tag = "in_row" if qi > 0 else "out_row"
            self.mv_tree.insert("", "end", values=(
                str(r.get("txn_date", "")), r.get("product_name_en", ""),
                r.get("txn_type", "").title(), ref,
                f"+{qi:,.2f}" if qi > 0 else "",
                f"-{qo:,.2f}" if qo > 0 else "",
                f"{float(r.get('balance_base', 0)):,.2f}"), tags=(tag,))

    # ── Low Stock ─────────────────────────────────────────────
    def _build_low(self, parent, C):
        bar = tk.Frame(parent, bg=C["content_bg"]); bar.pack(fill="x", pady=(10, 8))
        tk.Button(bar, text="🔄 Refresh", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load_low).pack(side="right")
        self.low_count = tk.StringVar()
        tk.Label(bar, textvariable=self.low_count, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["danger"]).pack(side="left")

        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("product", "code", "stock", "reorder", "short", "unit")
        h = {"product": ("Product", 240, "w"), "code": ("Code", 80, "center"),
             "stock": ("Current Stock", 120, "e"), "reorder": ("Reorder Level", 110, "e"),
             "short": ("Shortage", 100, "e"), "unit": ("Unit", 80, "center")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.low_tree = ttk.Treeview(card, columns=cols, show="headings",
                                     yscrollcommand=vsb.set)
        vsb.config(command=self.low_tree.yview)
        for col in cols:
            lbl, w, a = h[col]
            self.low_tree.heading(col, text=lbl); self.low_tree.column(col, width=w, anchor=a)
        self.low_tree.pack(fill="both", expand=True)
        self._load_low()

    def _load_low(self):
        self.low_tree.delete(*self.low_tree.get_children())
        try:
            rows = db.fetchall(
                "SELECT p.product_name_en, p.product_code, "
                "ISNULL(p.stock_quantity,0) AS stock, "
                "ISNULL(p.reorder_level,0) AS reorder, "
                "ISNULL(pu.unit_name_en,'Unit') AS unit_name "
                "FROM products p "
                "LEFT JOIN product_units pu ON p.default_unit_id=pu.unit_id "
                "WHERE p.is_active=1 AND p.product_type='product' "
                "AND ISNULL(p.stock_quantity,0) <= ISNULL(p.reorder_level,0) "
                "ORDER BY (ISNULL(p.reorder_level,0)-ISNULL(p.stock_quantity,0)) DESC")
        except Exception as e:
            messagebox.showerror("DB Error", str(e)); return
        for r in rows:
            stock = float(r.get("stock", 0))
            reorder = float(r.get("reorder", 0))
            short = max(0, reorder - stock)
            self.low_tree.insert("", "end", values=(
                r.get("product_name_en", ""), r.get("product_code", ""),
                f"{stock:,.2f}", f"{reorder:,.2f}",
                f"{short:,.2f}", r.get("unit_name", "Unit")))
        self.low_count.set(f"⚠️ {len(self.low_tree.get_children())} product(s) need restocking")

    # ── Manual Adjustment ─────────────────────────────────────
    def _adjust(self):
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "add"):
            return False
        StockAdjustDialog(self.frame, on_save=self._load_stock)

    def _stock_count(self):
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "add"):
            return False
        """Physical stock count: type the counted quantity per product and
        the system posts the difference (up or down) as an adjustment."""
        StockCountDialog(self.frame, on_save=self._load_stock)

    def _clear_stock(self):
        """Zero-out stock for a fresh physical count. Writes an adjustment
        movement for every product so the audit trail stays intact."""
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "approve", parent=self.frame):
            return False
        try:
            rows = db.fetchall(
                "SELECT product_id, ISNULL(stock_quantity,0) AS stock "
                "FROM products WHERE is_active=1 AND product_type='product' "
                "AND ISNULL(stock_quantity,0) <> 0") or []
        except Exception as e:
            messagebox.showerror("Clear Stock", str(e)[:200]); return
        if not rows:
            messagebox.showinfo("Clear Stock", "All stock is already zero.")
            return
        # dangerous: right + the user must type CLEAR (v6.9.3)
        from ui import danger
        if not danger.gate(
                self.frame.winfo_toplevel(), "stock_adjustment", "approve",
                "Clear Stock",
                "%d products of this branch go to 0 stock so you can do a "
                "fresh physical count.\n\nEach change is logged as an "
                "adjustment." % len(rows),
                word="CLEAR"):
            return
        try:
            today = date.today().strftime("%Y-%m-%d")
            with db.transaction():          # all products, or none (v5.27)
                from modules import stock_branch as _sb
                for r in rows:
                    pid = r["product_id"]
                    # v6.0: with several branches only THIS branch is cleared
                    cur, _tot, _b = _sb.local_qty(pid)
                    if abs(cur) < 1e-9:
                        continue
                    db.execute("UPDATE products SET stock_quantity=ISNULL(stock_quantity,0)-? "
                               "WHERE product_id=?", (cur, pid))
                    db.execute(
                        "INSERT INTO inventory_transactions (product_id, txn_date, "
                        "txn_type, reference_type, qty_in_base, qty_out_base, "
                        "balance_base, notes) VALUES (?,?,?,?,?,?,?,?)",
                        (pid, today, "adjustment_out" if cur > 0 else "adjustment_in",
                         "stock_clear", 0 if cur > 0 else -cur, cur if cur > 0 else 0,
                         round(_tot - cur, 4), "Stock cleared for physical count"))
                    _sb.after_manual_move(pid, -cur, "stock_clear", pid)
                    try:
                        from modules import doc_posting
                        with db.savepoint():
                            doc_posting.post_stock_adjustment(
                                pid, -cur, "Stock cleared for count", today, "CLEAR")
                    except Exception:
                        pass
                try:
                    from modules.doc_actions import audit
                    audit("clear", "stock", None, "%d products zeroed" % len(rows))
                except Exception:
                    pass
            messagebox.showinfo("Clear Stock",
                                "Stock cleared for %d product(s)." % len(rows))
            self._load_stock()
        except Exception as e:
            messagebox.showerror("Clear Stock", str(e)[:200])


class StockAdjustDialog:
    def __init__(self, parent, on_save=None):
        self.on_save = on_save
        self.products = []
        C = cfg.theme()
        self.win = tk.Toplevel(parent); self.win.bind("<Escape>", lambda e: self.win.destroy()); self.win.title("Stock Adjustment")
        self.win.geometry("460x460"); self.win.configure(bg=C["content_bg"])
        self.win.grab_set(); self._center(460, 460)

        hdr = tk.Frame(self.win, bg=C["primary"], height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="⚙  Stock Adjustment", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)

        body = tk.Frame(self.win, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=20, pady=12)

        try:
            self.products = db.fetchall(
                "SELECT product_id, product_code, product_name_en, "
                "ISNULL(stock_quantity,0) AS stock "
                "FROM products WHERE is_active=1 AND product_type='product' "
                "ORDER BY product_name_en")
        except Exception:
            self.products = []

        tk.Label(body, text="Product *", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        self.prod_var = tk.StringVar()
        self.prod_cb = ttk.Combobox(body, textvariable=self.prod_var,
                                    values=[f"{p['product_code']} — {p['product_name_en']}"
                                            for p in self.products], font=("Segoe UI", 10))
        self.prod_cb.pack(fill="x", ipady=4, pady=(0, 2))
        self.prod_cb.bind("<<ComboboxSelected>>", self._on_prod)
        self.prod_cb.bind("<Return>", self._scan_or_search)
        self.prod_cb.bind("<KP_Enter>", self._scan_or_search)
        self._view = list(range(len(self.products)))
        self._scanned = None
        tk.Label(body, text="Scan any barcode (piece, box, carton, scale label) or type a "
                            "name + Enter", font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(0, 6))

        self.current_lbl = tk.StringVar(value="Current stock: —")
        tk.Label(body, textvariable=self.current_lbl, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(0, 8))

        tk.Label(body, text="Adjustment Type *", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        self.adj_var = tk.StringVar(value="adjustment_in")
        rf = tk.Frame(body, bg=C["content_bg"]); rf.pack(anchor="w", pady=(2, 8))
        tk.Radiobutton(rf, text="➕ Add stock", variable=self.adj_var,
                       value="adjustment_in", font=("Segoe UI", 9),
                       bg=C["content_bg"], activebackground=C["content_bg"]).pack(side="left")
        tk.Radiobutton(rf, text="➖ Remove stock", variable=self.adj_var,
                       value="adjustment_out", font=("Segoe UI", 9),
                       bg=C["content_bg"], activebackground=C["content_bg"]).pack(side="left", padx=8)
        tk.Radiobutton(rf, text="🎯 Set exact", variable=self.adj_var,
                       value="set_exact", font=("Segoe UI", 9),
                       bg=C["content_bg"], activebackground=C["content_bg"]).pack(side="left")

        self.allow_neg_var = tk.BooleanVar(value=False)
        tk.Checkbutton(body, text="Allow negative stock (oversold / correction)",
                       variable=self.allow_neg_var, font=("Segoe UI", 8),
                       bg=C["content_bg"], activebackground=C["content_bg"],
                       fg=C["text_secondary"]).pack(anchor="w", pady=(0, 4))

        tk.Label(body, text="Quantity *", font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w")
        self.qty_var = tk.StringVar()
        tk.Entry(body, textvariable=self.qty_var, font=("Segoe UI", 12),
                 bg="white", relief="solid", bd=1).pack(fill="x", ipady=5, pady=(0, 8))

        tk.Label(body, text="Notes", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.notes_var = tk.StringVar()
        tk.Entry(body, textvariable=self.notes_var, font=("Segoe UI", 10),
                 bg="white", relief="solid", bd=1).pack(fill="x", ipady=5)

        self.status_var = tk.StringVar()
        self.status_lbl = tk.Label(body, textvariable=self.status_var, font=("Segoe UI", 9),
                                   bg=C["content_bg"], fg=C["danger"])
        self.status_lbl.pack(anchor="w", pady=4)
        # red for problems, blue for a scan confirmation
        self.status_var.trace_add("write", lambda *a: self.status_lbl.configure(
            fg=C["primary"] if self.status_var.get().startswith("🔎") else C["danger"]))

        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", side="bottom")
        bi = tk.Frame(btns, bg=C["card_bg"]); bi.pack(fill="x", padx=20, pady=10)
        tk.Button(bi, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(bi, text="💾 Apply", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=16, pady=6, cursor="hand2",
                  command=self._save).pack(side="right")

    def _picked(self):
        """The chosen product row (the list may be narrowed by a search)."""
        idx = self.prod_cb.current()
        if idx < 0 or idx >= len(self._view):
            return None
        return self.products[self._view[idx]]

    def _on_prod(self, e=None):
        p = self._picked()
        if p:
            stock = float(p.get("stock", 0))
            self.current_lbl.set(f"Current stock: {stock:,.2f}")

    def _scan_or_search(self, e=None):
        """Enter in the product box: a barcode → that product, and its unit
        is counted in pieces (a Box ×12 scan adds 12; scan again = +12).
        A name / code → the matching products."""
        txt = self.prod_var.get().strip()
        if not txt or (self.prod_cb.current() >= 0 and " — " in txt):
            return                          # a product is already chosen
        hit = None
        try:
            from modules.barcode_resolver import resolve
            hit = resolve(txt, products=self.products)
        except Exception:
            hit = None
        if hit:
            i = next((k for k, p in enumerate(self.products)
                      if p["product_id"] == hit["product_id"]), None)
            if i is not None:
                self._view = list(range(len(self.products)))
                self.prod_cb["values"] = [f"{p['product_code']} — {p['product_name_en']}"
                                          for p in self.products]
                self.prod_cb.current(i)
                self._on_prod()
                add = float(hit.get("factor") or 1) * float(hit.get("quantity") or 1)
                try:
                    cur = float(self.qty_var.get() or 0) if self._scanned == hit["product_id"] else 0.0
                except ValueError:
                    cur = 0.0
                self._scanned = hit["product_id"]
                self.qty_var.set(f"{cur + add:g}")
                unit = hit.get("unit_name") or ""
                self.status_var.set(f"🔎 {unit} ×{hit.get('factor', 1):g} scanned → quantity "
                                    f"{cur + add:g} (pieces)" if unit else "")
                return "break"
        t_ = txt.lower()
        m = [k for k, p in enumerate(self.products)
             if t_ in (str(p.get("product_code", "")) + " " + str(p.get("product_name_en", ""))).lower()]
        if not m:
            self.status_var.set(f"⚠️ No product found for '{txt}'.")
            return "break"
        self._view = m
        self.prod_cb["values"] = [f"{self.products[k]['product_code']} — "
                                  f"{self.products[k]['product_name_en']}" for k in m]
        if len(m) == 1:
            self.prod_cb.current(0); self._on_prod()
        else:
            try:
                self.prod_cb.event_generate("<Down>")
            except Exception:
                pass
        self.status_var.set("")
        return "break"

    def _save(self):
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "add"):
            return False
        p = self._picked()
        if p is None:
            self.status_var.set("⚠️ Select a product."); return
        try:
            qty = float(self.qty_var.get())
        except ValueError:
            self.status_var.set("⚠️ Enter a valid quantity."); return
        # Add/Remove need a positive amount; Set-exact accepts any target
        if self.adj_var.get() != "set_exact" and qty <= 0:
            self.status_var.set("⚠️ Enter a quantity greater than zero."); return

        pid = p["product_id"]
        adj_type = self.adj_var.get()
        cur = float(p.get("stock", 0))
        allow_neg = self.allow_neg_var.get()
        if adj_type == "adjustment_in":
            new_bal = cur + qty
            qi, qo = qty, 0
        elif adj_type == "set_exact":
            # "Set exact" — qty IS the new balance (can be negative if allowed)
            new_bal = qty if allow_neg else max(0, qty)
            diff = new_bal - cur
            qi, qo = (diff, 0) if diff >= 0 else (0, -diff)
            adj_type = "adjustment_in" if diff >= 0 else "adjustment_out"
        else:
            new_bal = cur - qty if allow_neg else max(0, cur - qty)
            qi, qo = 0, qty
        if new_bal < 0 and not allow_neg:
            new_bal = 0
        if new_bal < 0:
            if not messagebox.askyesno(
                    "Negative Stock",
                    "This leaves a NEGATIVE balance of %.2f. Continue?" % new_bal):
                return

        try:
            # v5.27: one transaction, and the change is worked out from the
            # stock as it is NOW (a till may have sold since this opened)
            with db.transaction():
                from modules import stock_branch as _sb
                now, _tot, _b = _sb.local_qty(pid)      # this branch (v6.0) / company
                if self.adj_var.get() == "set_exact":
                    delta = new_bal - now
                else:
                    delta = (new_bal - cur)
                    if not allow_neg and now + delta < 0:
                        delta = -now
                new_bal = now + delta
                qi, qo = (delta, 0) if delta >= 0 else (0, -delta)
                db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) + ? "
                           "WHERE product_id=?", (delta, pid))
                db.execute(
                    "INSERT INTO inventory_transactions "
                    "(product_id, txn_date, txn_type, reference_type, "
                    "qty_in_base, qty_out_base, balance_base, notes) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (pid, date.today().strftime("%Y-%m-%d"),
                     "adjustment_in" if delta >= 0 else "adjustment_out", "manual",
                     qi, qo, round(_tot + delta, 4), self.notes_var.get() or None))
                _sb.after_manual_move(pid, delta, "manual_adjust", pid)
                try:
                    from modules import doc_posting
                    with db.savepoint():
                        doc_posting.post_stock_adjustment(
                            pid, delta,
                            "Stock adjustment" + (": " + self.notes_var.get()
                                                  if self.notes_var.get() else ""))
                except Exception:
                    pass
            messagebox.showinfo(t("common.success"),
                f"Stock adjusted. New balance: {new_bal:,.2f}")
            if self.on_save:
                self.on_save()
            # v6.9.3: the window stays open (Settings ▸ General ▸ After saving)
            from ui import after_save
            parent, cb = self.win.master, self.on_save
            after_save.finish(self, "", new=lambda: StockAdjustDialog(parent, on_save=cb))
        except Exception as e:
            self.status_var.set(f"❌ {str(e)[:70]}")

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


class StockCountDialog:
    """Physical stock count sheet: shows every product with its system
    stock and a 'Counted' box. Type the counted quantity; on Apply the
    system posts the difference (up or down) as an adjustment so the
    books match the shelf. Search filters the list."""
    def __init__(self, parent, on_save=None):
        self.on_save = on_save
        C = cfg.theme()
        self.win = tk.Toplevel(parent); self.win.bind("<Escape>", lambda e: self.win.destroy()); self.win.title("Physical Stock Count")
        self.win.geometry("820x620"); self.win.configure(bg=C["content_bg"])
        self.win.grab_set(); self._center(820, 620)

        hdr = tk.Frame(self.win, bg=C["primary"], height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="🧮  Physical Stock Count", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=16)
        tk.Label(hdr, text="Type the counted qty; blank = unchanged",
                 font=("Segoe UI", 8), bg=C["primary"], fg="#D1FAE5").pack(
                     side="right", padx=16)

        bar = tk.Frame(self.win, bg=C["content_bg"]); bar.pack(fill="x", padx=16, pady=8)
        tk.Label(bar, text="🔍", bg=C["content_bg"], font=("Segoe UI Emoji", 11)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._reload())
        self.search_e = tk.Entry(bar, textvariable=self.search_var, font=("Segoe UI", 10),
                                 bg="white", relief="solid", bd=1, width=30)
        self.search_e.pack(side="left", ipady=4, padx=(4, 0))
        self.search_e.bind("<Return>", self._scan_count)
        self.search_e.bind("<KP_Enter>", self._scan_count)
        tk.Label(bar, text="scan = +1 counted (a Box adds its pieces)", font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left", padx=8)
        self.scan_msg = tk.StringVar()
        tk.Label(self.win, textvariable=self.scan_msg, font=("Segoe UI", 9, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", padx=16)
        self.count_lbl = tk.StringVar()
        tk.Label(bar, textvariable=self.count_lbl, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right")

        # scrollable rows
        card = tk.Frame(self.win, bg="white", highlightbackground=C["border"],
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16)
        head = tk.Frame(card, bg=C["primary_light"]); head.pack(fill="x")
        for txt, w in [("Code", 12), ("Product", 34), ("System", 10),
                       ("Counted", 12), ("Diff", 10)]:
            tk.Label(head, text=txt, font=("Segoe UI", 9, "bold"),
                     bg=C["primary_light"], fg=C["primary"], width=w,
                     anchor="w").pack(side="left", padx=4, pady=4)
        cv = tk.Canvas(card, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(card, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(fill="both", expand=True)
        self._rowsframe = tk.Frame(cv, bg="white")
        cv.create_window((0, 0), window=self._rowsframe, anchor="nw")
        self._rowsframe.bind("<Configure>",
                             lambda e: cv.configure(scrollregion=cv.bbox("all")))
        self._C = C
        self._rows = []
        self._counts = {}          # product_id → counted text (kept while searching)
        self._cur = {}
        try:
            self._prods = db.fetchall(
                "SELECT product_id, product_code, product_name_en, "
                "ISNULL(stock_quantity,0) AS stock FROM products "
                "WHERE is_active=1 AND product_type='product' "
                "ORDER BY product_name_en") or []
        except Exception:
            self._prods = []
        for p in self._prods:
            self._cur[p["product_id"]] = float(p.get("stock", 0))
        self._reload()

        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", side="bottom")
        bi = tk.Frame(btns, bg=C["card_bg"]); bi.pack(fill="x", padx=16, pady=10)
        tk.Button(bi, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(bi, text="💾 Post Count", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._post).pack(side="right")

    def _reload(self):
        C = self._C
        for w in self._rowsframe.winfo_children():
            w.destroy()
        self._rows = []
        q = self.search_var.get().lower()
        prods = getattr(self, "_prods", None) or []
        only = getattr(self, "_only_pid", None)
        shown = 0
        for p in prods:
            if only is not None:
                if p["product_id"] != only:
                    continue
            elif q and q not in (str(p.get("product_code", "")) +
                                 str(p.get("product_name_en", ""))).lower():
                continue
            if shown >= 400:                # a huge list: narrow it with the search
                break
            row = tk.Frame(self._rowsframe, bg="white")
            row.pack(fill="x")
            cur = float(p.get("stock", 0))
            tk.Label(row, text=p.get("product_code", ""), font=("Segoe UI", 9),
                     bg="white", width=12, anchor="w").pack(side="left", padx=4, pady=1)
            tk.Label(row, text=p.get("product_name_en", "")[:40], font=("Segoe UI", 9),
                     bg="white", width=34, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=f"{cur:,.2f}", font=("Segoe UI", 9), bg="white",
                     width=10, anchor="w").pack(side="left", padx=4)
            cnt = tk.StringVar(value=self._counts.get(p["product_id"], ""))
            diff = tk.StringVar(value="—")
            e = tk.Entry(row, textvariable=cnt, font=("Segoe UI", 9), width=12,
                         relief="solid", bd=1, justify="right")
            e.pack(side="left", padx=4)
            dl = tk.Label(row, textvariable=diff, font=("Segoe UI", 9, "bold"),
                          bg="white", width=10, anchor="w")
            dl.pack(side="left", padx=4)

            def on_type(*a, v=cnt, d=diff, base=cur, lbl=dl, pid=p["product_id"]):
                s = v.get().strip()
                self._counts[pid] = s
                if s == "":
                    d.set("—"); lbl.configure(fg="#6B7280"); return
                try:
                    diffv = float(s) - base
                    d.set(f"{diffv:+,.2f}")
                    lbl.configure(fg="#16A34A" if diffv >= 0 else "#DC2626")
                except ValueError:
                    d.set("?"); lbl.configure(fg="#DC2626")
            cnt.trace("w", on_type)
            if cnt.get():
                on_type()
            self._rows.append({"pid": p["product_id"], "cur": cur, "cnt": cnt, "entry": e})
            shown += 1
        done = sum(1 for v in self._counts.values() if str(v).strip())
        self.count_lbl.set(f"{shown} products shown · {done} counted")

    def _scan_count(self, e=None):
        """Enter in the search box: a scanned barcode adds to that
        product's counted quantity (Box ×12 → +12). Text just filters."""
        txt = self.search_var.get().strip()
        if not txt:
            return "break"
        try:
            from modules.barcode_resolver import resolve
            hit = resolve(txt, products=self._prods)
        except Exception:
            hit = None
        if not hit or hit["product_id"] not in self._cur:
            rows = self._rows
            if len(rows) == 1:
                rows[0]["entry"].focus_set()
            return "break"
        pid = hit["product_id"]
        add = float(hit.get("factor") or 1) * float(hit.get("quantity") or 1)
        try:
            now = float(self._counts.get(pid) or 0)
        except ValueError:
            now = 0.0
        self._counts[pid] = f"{now + add:g}"
        self._only_pid = pid
        self.search_var.set("")             # reloads, showing only that product
        self._only_pid = None
        self.scan_msg.set(f"✔ {hit['product'].get('product_name_en', '')} · "
                          f"{hit.get('unit_name') or ''} ×{hit.get('factor', 1):g} → counted "
                          f"{now + add:g}")
        self._show_only(pid)
        self.search_e.focus_set()
        return "break"

    def _show_only(self, pid):
        self._only_pid = pid
        try:
            self._reload()
        finally:
            self._only_pid = None

    def _post(self):
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "add"):
            return False
        changes = []
        for pid, s in self._counts.items():     # every counted product, shown or not
            s = str(s or "").strip()
            if s == "" or pid not in self._cur:
                continue
            try:
                counted = float(s)
            except ValueError:
                continue
            if abs(counted - self._cur[pid]) > 1e-9:
                changes.append((pid, self._cur[pid], counted))
        if not changes:
            messagebox.showinfo("Stock Count", "No differences to post.")
            return
        if not messagebox.askyesno(
                "Post Stock Count",
                "Apply counted quantities for %d product(s)? The difference "
                "for each is logged as an adjustment." % len(changes)):
            return
        try:
            today = date.today().strftime("%Y-%m-%d")
            with db.transaction():       # the whole count posts, or none of it (v5.27)
                from modules import stock_branch as _sb
                for pid, cur, counted in changes:
                    # v6.0: with several branches the count is THIS branch's stock
                    now, _tot, _b = _sb.local_qty(pid)
                    diff = counted - now
                    if abs(diff) < 1e-9:
                        continue
                    db.execute("UPDATE products SET stock_quantity=ISNULL(stock_quantity,0)+? "
                               "WHERE product_id=?", (diff, pid))
                    db.execute(
                        "INSERT INTO inventory_transactions (product_id, txn_date, "
                        "txn_type, reference_type, qty_in_base, qty_out_base, "
                        "balance_base, notes) VALUES (?,?,?,?,?,?,?,?)",
                        (pid, today,
                         "adjustment_in" if diff > 0 else "adjustment_out",
                         "stock_count",
                         diff if diff > 0 else 0, -diff if diff < 0 else 0,
                         round(_tot + diff, 4), "Physical stock count"))
                    _sb.after_manual_move(pid, diff, "stock_count", pid)
                    try:
                        from modules import doc_posting
                        with db.savepoint():
                            doc_posting.post_stock_adjustment(
                                pid, diff, "Physical stock count", today, "COUNT")
                    except Exception:
                        pass
                try:
                    from modules.doc_actions import audit
                    audit("stock_count", "stock", None,
                          "%d products counted and applied" % len(changes))
                except Exception:
                    pass
            messagebox.showinfo("Stock Count",
                                "Posted %d adjustment(s)." % len(changes))
            if self.on_save:
                self.on_save()
            self.win.destroy()
        except Exception as e:
            messagebox.showerror("Stock Count", str(e)[:200])

    def _center(self, w, h):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
