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
    """v7.18.1: ONE small strip at the bottom-right of the bill (was two
    big boxes over the grid): the last 3 purchases and the last 3 sales of
    the product, side by side. It never covers other programs (not
    'always on top'), closes by itself after a few seconds, with Esc, when
    the next product is picked, or when the bill closes."""

    _box = None

    @classmethod
    def show(cls, parent, product, theme):
        try:
            from config import settings as _cfg
            if not _cfg.flag("auto_history_box", True):
                return None
        except Exception:
            pass
        if cls._box is not None:
            try:
                if cls._box.winfo_exists() and cls._box.master is parent:
                    cls._box.load(product)
                    return cls._box
                cls._box.destroy()
            except Exception:
                pass
        cls._box = _HistoryStrip(parent, product, theme)
        return cls._box

    @classmethod
    def close_all(cls):
        try:
            if cls._box is not None and cls._box.winfo_exists():
                cls._box.destroy()
        except Exception:
            pass
        cls._box = None


class _HistoryStrip(tk.Toplevel):
    SECONDS = 7

    def __init__(self, parent, product, theme):
        super().__init__(parent)
        C = self.C = theme
        self._parent = parent
        self._timer = None
        self.overrideredirect(True)
        try:
            self.transient(parent)            # in front of the bill only, not of other programs
        except Exception:
            pass
        self.configure(bg=C.get("border", "#D6DBE6"))
        card = tk.Frame(self, bg=C.get("card_bg", "white"))
        card.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Frame(card, bg=C.get("card_bg", "white"))
        head.pack(fill="x", padx=8, pady=(4, 0))
        self.title_v = tk.StringVar()
        tk.Label(head, textvariable=self.title_v, font=("Segoe UI", 9, "bold"),
                 bg=head["bg"], fg=C.get("primary", "#2563EB")).pack(side="left")
        x = tk.Label(head, text="✕", font=("Segoe UI", 9), bg=head["bg"],
                     fg=C.get("text_secondary", "#6B7280"), cursor="hand2")
        x.pack(side="right")
        x.bind("<Button-1>", lambda e: ProductHistoryBox.close_all())
        body = tk.Frame(card, bg=head["bg"])
        body.pack(fill="both", padx=8, pady=(2, 6))
        self.cols = {}
        for kind, title in (("buy", "📥 Last purchases"), ("sell", "📤 Last sales")):
            f = tk.Frame(body, bg=head["bg"])
            f.pack(side="left", fill="both", expand=True, padx=(0, 10))
            tk.Label(f, text=title, font=("Segoe UI", 8, "bold"), bg=head["bg"],
                     fg=C.get("text_secondary", "#6B7280")).pack(anchor="w")
            lab = tk.Label(f, text="", font=("Consolas", 9), bg=head["bg"],
                           fg=C.get("text_primary", "#111827"), justify="left", anchor="w")
            lab.pack(anchor="w")
            self.cols[kind] = lab
        for w in (self, card, body):
            w.bind("<Enter>", lambda e: self._stop())
            w.bind("<Leave>", lambda e: self._start())
        try:
            parent.bind("<Destroy>", lambda e: ProductHistoryBox.close_all()
                        if e.widget is parent else None, add="+")
            parent.bind("<Escape>", lambda e: ProductHistoryBox.close_all(), add="+")
        except Exception:
            pass
        self.load(product)

    def _rows(self, kind, pid):
        try:
            from modules import product_history as ph
            rows = (ph.last_purchases(pid, limit=3) if kind == "buy" else ph.last_sales(pid, limit=3))
        except Exception:
            rows = []
        if not rows:
            return "no history yet"
        out = []
        for r in rows:
            d = r.get("date")
            dt = d.strftime("%d/%m/%y") if hasattr(d, "strftime") else str(d or "")[:10]
            party = str(r.get("party_name") or "—")[:14]
            out.append("%-8s %-14s %6g × %s" % (dt, party, float(r.get("quantity") or 0),
                                                _money(r.get("unit_price"))))
        return "\n".join(out)

    def load(self, product):
        self.title_v.set(str(product.get("product_name_en") or "")[:48])
        for kind, lab in self.cols.items():
            lab.config(text=self._rows(kind, product["product_id"]))
        self._place()
        self._start()

    def _place(self):
        try:
            self.update_idletasks()
            p = self._parent
            w, h = max(self.winfo_reqwidth(), 520), self.winfo_reqheight()
            x = p.winfo_rootx() + p.winfo_width() - w - 14
            y = p.winfo_rooty() + p.winfo_height() - h - 120    # above the totals / buttons
            self.geometry("%dx%d+%d+%d" % (w, h, x, max(0, y)))
            self.lift()
        except Exception:
            pass

    def _stop(self):
        if self._timer:
            try:
                self.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None

    def _start(self):
        self._stop()
        try:
            self._timer = self.after(self.SECONDS * 1000, ProductHistoryBox.close_all)
        except Exception:
            pass
