# ============================================================
# DayBill ERP — Product side-boxes (two distinct, minimal boxes)
# ------------------------------------------------------------
# 1) UnitProfitBox   — shown while Ctrl is HELD (CtrlHold). Minimal
#    card at the BOTTOM of the window: each unit with its box qty,
#    sale / purchase price, profit and stock. Let go of Ctrl = closed.
#
# 2) ProductHistoryBox — opens AUTOMATICALLY when a product is picked
#    and the cursor lands on the Quantity field. Shows the last 5
#    purchases and last 5 sales (date · invoice # · party · rate).
#    Non-modal, unobtrusive, auto-refreshes as you pick products.
# ============================================================

import tkinter as tk
from tkinter import ttk


def _money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


# ============================================================
#  1) Ctrl-toggle — units + purchase rate + profit only
# ============================================================
class UnitProfitBox(tk.Toplevel):
    """Minimal, frameless box anchored to the bottom of the parent
    window: each unit → how many pieces · sale · purchase · profit ·
    stock in that unit.
    hold=True  : shown while Ctrl is HELD, closes when Ctrl is let go
                 (never takes the keyboard focus).
    hold=False : old toggle box (Ctrl again / Esc / click closes)."""

    def __init__(self, parent, product, units, theme, hold=False):
        super().__init__(parent)
        C = theme
        self.C = C
        self.overrideredirect(True)             # frameless / minimal
        self.configure(bg=C.get("border", "#E3E0F4"))
        self.attributes("-topmost", True)

        card = tk.Frame(self, bg=C.get("card_bg", "white"))
        card.pack(fill="both", expand=True, padx=1, pady=1)

        # slim header: product name + purchase price of the base unit
        head = tk.Frame(card, bg=C.get("primary", "#3A1FD6"))
        head.pack(fill="x")
        tk.Label(head, text=product.get("product_name_en", ""),
                 font=("Segoe UI", 10, "bold"), bg=head["bg"], fg="white"
                 ).pack(side="left", padx=10, pady=5)
        base_cost = float(product.get("purchase_price", 0) or 0)
        stock = float(product.get("stock_quantity", 0) or 0)
        tk.Label(head, text="Purchase " + _money(base_cost) + "   ·   Stock %g" % stock,
                 font=("Segoe UI", 9, "bold"), bg=head["bg"], fg="#FFF3B0"
                 ).pack(side="right", padx=10)

        rows = units or [{"unit_name_en": product.get("unit_of_measure_en", "Unit"),
                          "conversion_factor": 1, "is_default": 1,
                          "selling_price": product.get("unit_price", 0)}]
        base = min(rows, key=lambda u: float(u.get("conversion_factor") or 1))
        base_name = base.get("unit_name_en", "") or "pcs"
        cols = ("unit", "pcs", "sale", "salevat", "cost", "profit", "stock")
        tv = ttk.Treeview(card, columns=cols, show="headings",
                          height=min(max(len(rows), 1), 6))
        for cid, txt, w, anc in [("unit", "Unit", 84, "w"),
                                 ("pcs", "Box qty", 86, "center"),
                                 ("sale", "Sale", 72, "e"),
                                 ("salevat", "Rate+VAT", 92, "e"),
                                 ("cost", "Purchase", 84, "e"),
                                 ("profit", "Profit", 70, "e"),
                                 ("stock", "Stock", 68, "e")]:
            tv.heading(cid, text=txt)
            tv.column(cid, width=w, anchor=anc)
        tv.tag_configure("default", background="#EDF9E8")
        tv.tag_configure("odd", background="#F7F6FD")
        tv.tag_configure("loss", foreground="#DC2626")
        vat_rate = float(product.get("vat_rate", 15) or 0)
        for i, u in enumerate(rows):
            factor = float(u.get("conversion_factor", 1) or 1)
            sale = float(u.get("selling_price") or 0) or \
                float(product.get("unit_price", 0) or 0) * factor
            sale_vat = sale * (1 + vat_rate / 100.0)
            cost = float(u.get("purchase_price") or 0) or base_cost * factor
            profit = sale - cost
            name = u.get("unit_name_en", "") + ("  ★" if u.get("is_default") else "")
            pcs = ("%g %s" % (factor, base_name)) if factor != 1 else "1"
            st = stock / factor if factor else stock
            tag = ("default" if u.get("is_default")
                   else ("odd" if i % 2 else ""))
            if profit < 0:
                tag = "loss"
            tv.insert("", "end", values=(name, pcs, _money(sale), _money(sale_vat),
                                         _money(cost), _money(profit),
                                         "%g" % round(st, 2)),
                      tags=(tag,))
        tv.pack(fill="both", expand=True, padx=6, pady=6)

        tk.Label(card, text=("Let go of Ctrl to close" if hold else "Ctrl / Esc to close"),
                 font=("Segoe UI", 7), bg=card["bg"],
                 fg=C.get("text_secondary", "#9CA3AF")).pack(pady=(0, 4))

        if not hold:
            # old toggle box: close on Ctrl again, Esc, or click-away
            for seq in ("<Control_L>", "<Control_R>", "<Escape>", "<Button-1>"):
                self.bind(seq, lambda e: self.destroy())
            self.bind("<FocusOut>", lambda e: self.destroy())
        else:
            self.bind("<Button-1>", lambda e: self.destroy())

        # anchor to the bottom-center of the parent window
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        try:
            pw = parent.winfo_width()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            ph = parent.winfo_height()
            x = px + max((pw - w) // 2, 0)
            y = py + ph - h - 54           # sit just above the footer
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry(f"{w}x{h}")
        if not hold:
            self.focus_set()


class CtrlHold:
    """Hold Ctrl → `opener()` shows a box; let go of Ctrl → it closes.
    Ctrl + another key (Ctrl+C, Ctrl+V…) never shows it."""
    OPEN_DELAY = 180      # ms Ctrl must be held before the box shows

    def __init__(self, widgets, opener):
        self.opener = opener
        self.box = None
        self._open_job = None
        self._close_job = None
        self._w = widgets[0]
        for w in widgets:
            self.attach(w)

    def attach(self, w):
        """Also listen on `w` (e.g. a cell editor that has the focus)."""
        try:
            for k in ("Control_L", "Control_R"):
                w.bind(f"<KeyPress-{k}>", self._press, add="+")
                w.bind(f"<KeyRelease-{k}>", self._release, add="+")
            w.bind("<Control-Key>", self._combo, add="+")
        except Exception:
            pass

    def _alive(self):
        try:
            return self.box is not None and self.box.winfo_exists()
        except Exception:
            return False

    def _cancel(self, attr):
        job = getattr(self, attr)
        if job:
            try:
                self._w.after_cancel(job)
            except Exception:
                pass
            setattr(self, attr, None)

    def _press(self, e=None):
        self._cancel("_close_job")             # key repeat / X11 auto-repeat
        if self._alive() or self._open_job:
            return
        self._open_job = self._w.after(self.OPEN_DELAY, self._do_open)

    def _do_open(self):
        self._open_job = None
        try:
            self.box = self.opener()
        except Exception:
            self.box = None

    def _release(self, e=None):
        self._cancel("_open_job")
        self._cancel("_close_job")
        self._close_job = self._w.after(60, self.close)

    def _combo(self, e=None):
        if e is not None and str(getattr(e, "keysym", "")).startswith("Control"):
            return
        self._cancel("_open_job")
        self.close()

    def close(self):
        self._close_job = None
        if self._alive():
            try:
                self.box.destroy()
            except Exception:
                pass
        self.box = None


# ============================================================
#  2) Auto history — last 5 purchases + last 5 sales
# ============================================================
class ProductHistoryBox:
    """Two INDEPENDENT small windows — Last 8 Purchases (bottom-LEFT of
    the screen/app) and Last 8 Sales (bottom-RIGHT) — each showing
    Date · Invoice # · Party · Qty · Rate. Only the last 4 rows are
    visible without scrolling; the remaining 4 are one scroll away.
    Opens automatically when a product is selected and the cursor moves
    to Quantity. Non-modal, reused/refreshed for the next product."""

    _buy_box = None
    _sell_box = None

    @classmethod
    def show(cls, parent, product, theme):
        cls._buy_box = _HistoryPanel.open_or_refresh(
            cls._buy_box, parent, product, theme, "buy",
            "📥 Last 8 Purchases", "Supplier")
        cls._sell_box = _HistoryPanel.open_or_refresh(
            cls._sell_box, parent, product, theme, "sell",
            "📤 Last 8 Sales", "Customer")
        return cls._buy_box

    @classmethod
    def close_all(cls):
        for box in (cls._buy_box, cls._sell_box):
            try:
                if box is not None and box.winfo_exists():
                    box.destroy()
            except Exception:
                pass
        cls._buy_box = None
        cls._sell_box = None


class _HistoryPanel(tk.Toplevel):
    """One side of the split history box (either Purchases or Sales)."""

    @classmethod
    def open_or_refresh(cls, inst, parent, product, theme, kind, title, party_head):
        if inst is not None and inst.winfo_exists():
            inst._load(product)
            inst._reposition(parent)
            inst.lift()
            return inst
        return cls(parent, product, theme, kind, title, party_head)

    def __init__(self, parent, product, theme, kind, title, party_head):
        super().__init__(parent)
        C = theme
        self.C = C
        self.kind = kind
        self.party_head = party_head
        self._parent = parent
        self.overrideredirect(True)
        self.configure(bg=C.get("border", "#E3E0F4"))
        self.attributes("-topmost", True)

        self.card = tk.Frame(self, bg=C.get("card_bg", "white"))
        self.card.pack(fill="both", expand=True, padx=1, pady=1)

        self.head = tk.Frame(self.card, bg=C.get("primary", "#3A1FD6"))
        self.head.pack(fill="x")
        self.title_var = tk.StringVar()
        tk.Label(self.head, textvariable=self.title_var,
                 font=("Segoe UI", 10, "bold"), bg=self.head["bg"], fg="white"
                 ).pack(side="left", padx=10, pady=5)
        tk.Button(self.head, text="✕", font=("Segoe UI", 9, "bold"),
                  bg=self.head["bg"], fg="white", relief="flat", cursor="hand2",
                  activebackground=self.head["bg"], activeforeground="#FFD",
                  command=self._close_both).pack(side="right", padx=8)

        tk.Label(self.card, text=title, font=("Segoe UI", 9, "bold"),
                 bg=self.card["bg"], fg=C.get("primary", "#3A1FD6")
                 ).pack(anchor="w", padx=10, pady=(6, 2))

        # table + vertical scrollbar — 4 rows visible, scroll for the rest
        wrap = tk.Frame(self.card, bg=self.card["bg"])
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        vsb = ttk.Scrollbar(wrap, orient="vertical")
        vsb.pack(side="right", fill="y")
        self.tv = ttk.Treeview(wrap, columns=("date", "inv", "party", "qty", "rate"),
                               show="headings", height=4, yscrollcommand=vsb.set)
        vsb.config(command=self.tv.yview)
        for cid, txt, w, anc in [("date", "Date", 64, "center"),
                                 ("inv", "Invoice #", 84, "w"),
                                 ("party", party_head, 110, "w"),
                                 ("qty", "Qty", 50, "e"),
                                 ("rate", "Rate", 62, "e")]:
            self.tv.heading(cid, text=txt)
            self.tv.column(cid, width=w, anchor=anc)
        self.tv.pack(side="left", fill="both", expand=True)

        self.bind("<Escape>", lambda e: self._close_both())
        self._load(product)
        self._reposition(parent)
        self.after(100, self._add_dismiss_hook)

    def _fill(self, rows):
        self.tv.delete(*self.tv.get_children())
        if not rows:
            self.tv.insert("", "end", values=("—", "—", "No history yet", "—", "—"))
            return
        for r in rows:
            d = r.get("date")
            dtxt = d.strftime("%d/%m/%y") if hasattr(d, "strftime") else str(d)[:10]
            self.tv.insert("", "end", values=(
                dtxt, r.get("invoice_number", ""),
                r.get("party_name", "") or "—",
                f"{float(r.get('quantity', 0) or 0):g}",
                _money(r.get("unit_price", 0))))

    def _load(self, product):
        self.product = product
        self.title_var.set(product.get("product_name_en", ""))
        try:
            from modules import product_history as ph
            rows = (ph.last_purchases(product["product_id"], limit=8)
                    if self.kind == "buy" else
                    ph.last_sales(product["product_id"], limit=8))
        except Exception:
            rows = []
        self._fill(rows)

    def _reposition(self, parent):
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 300)
        h = self.winfo_reqheight()
        try:
            pw = parent.winfo_width()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            phh = parent.winfo_height()
            # split: Purchases hugs the bottom-LEFT, Sales the bottom-RIGHT
            x = px + 16 if self.kind == "buy" else px + pw - w - 16
            y = py + phh - h - 54
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry(f"{w}x{h}")

    def _add_dismiss_hook(self):
        try:
            self._parent.bind("<Destroy>", lambda e: self._safe_close(), add="+")
        except Exception:
            pass

    def _safe_close(self):
        try:
            if self.winfo_exists():
                self.destroy()
        except Exception:
            pass

    def _close_both(self):
        ProductHistoryBox.close_all()
