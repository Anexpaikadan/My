# ============================================================
# DayBill ERP - Product window ▸ live "Product summary" (v6.9.4)
# ------------------------------------------------------------
# Designed in Figma: "DayBill ERP — Product window v6.9.4".
# A panel on the right of the Product window, the same on every page,
# that follows what you type:
#   sale price with / without VAT · cost · PROFIT and PROFIT % (green;
#   red when the price is below cost) · stock · PLU · units 1-3 · every
#   barcode of the product
# values(form) is the plain calculation (used by the panel and tests).
# ============================================================

import re
import tkinter as tk


def _num(v):
    try:
        return float(str(v.get() if hasattr(v, "get") else v).replace(",", "").strip() or 0)
    except Exception:
        return 0.0


def _get(form, key):
    w = form.fields.get(key)
    try:
        return w.get() if w is not None else ""
    except Exception:
        return ""


def vat_rate(text):
    """'S - Standard Rate (15.00%)' → 15.0"""
    m = re.search(r"\(([\d.]+)\s*%\)", str(text or ""))
    try:
        return float(m.group(1)) if m else 0.0
    except Exception:
        return 0.0


def values(form):
    """Everything the panel shows, worked out from the form's boxes."""
    price = _num(_get(form, "unit_price"))
    rate = vat_rate(_get(form, "vat_category_id"))
    incl = bool(getattr(form, "price_incl_var", None) and form.price_incl_var.get())
    net = price / (1 + rate / 100.0) if incl and rate else price
    gross = price if incl else price * (1 + rate / 100.0)
    cost = 0.0
    for k in ("average_cost", "purchase_price", "last_purchase_cost"):
        c = _num(_get(form, k))
        if c > 0:
            cost = c
            break
    profit = net - cost
    pct = (profit / net * 100.0) if net else None
    unit = str(_get(form, "unit_of_measure_en") or "").strip() or "Unit"
    units = []
    for r in getattr(form, "unit_rows", []) or []:
        try:
            name = str(r["name"].get() or "").strip()
            f = _num(r["qty"])
            if name and name != getattr(form, "_ADD_NEW", "\0"):
                units.append((name, f or 1.0, _num(r["price"])))
        except Exception:
            continue
    if not any(abs(u[1] - 1.0) < 1e-9 for u in units):    # Unit 1 = the base unit (× 1)
        units.append((unit, 1.0, price))
    units.sort(key=lambda u: u[1])
    if units and abs(units[0][1] - 1.0) < 1e-9 and not units[0][2]:
        units[0] = (units[0][0], 1.0, price)         # the base unit sells at the sale price
    codes = []
    for bc in [_get(form, "barcode")] + [_safe(r, "barcode") for r in getattr(form, "unit_rows", []) or []] \
            + list(getattr(form, "_extra_barcodes", []) or []):
        bc = str(bc or "").strip()
        if bc and bc not in codes:
            codes.append(bc)
    plu = str(_get(form, "scale_plu") or "").strip()
    return {"price": price, "gross": round(gross, 2), "net": round(net, 2), "rate": rate,
            "incl": incl, "cost": round(cost, 4), "profit": round(profit, 2),
            "pct": round(pct, 2) if pct is not None else None,
            "stock": _num(_get(form, "stock_quantity")), "unit": unit,
            "plu": plu, "units": units[:3], "more_units": max(0, len(units) - 3), "barcodes": codes}


def _safe(r, k):
    try:
        return r[k].get()
    except Exception:
        return ""


class ProductSummary:
    WIDTH = 236

    def __init__(self, parent, form, C):
        self.form, self.C = form, C
        self._sig = None
        self.frame = tk.Frame(parent, bg=C["card_bg"], highlightbackground=C["border"],
                              highlightthickness=1, width=self.WIDTH)
        self.frame.pack_propagate(False)
        inner = tk.Frame(self.frame, bg=C["card_bg"])
        inner.pack(fill="both", expand=True, padx=12, pady=10)
        self.inner = inner
        self._head(inner, "PRODUCT SUMMARY")
        self.rows = {}
        for k, lbl in (("gross", "Sale price (with VAT)"), ("net", "Net (no VAT)"),
                       ("cost", "Cost (average)")):
            self.rows[k] = self._row(inner, lbl)
        # profit block: big number + % chip
        self.pbox = tk.Frame(inner, bg="#E8F7EE")
        self.pbox.pack(fill="x", pady=(6, 6))
        left = tk.Frame(self.pbox, bg="#E8F7EE")
        left.pack(side="left", padx=10, pady=6)
        self.p_cap = tk.Label(left, text="Profit / unit", font=("Segoe UI", 8), bg="#E8F7EE",
                              fg=C["text_secondary"])
        self.p_cap.pack(anchor="w")
        self.p_val = tk.Label(left, text="0.00", font=("Segoe UI", 16, "bold"), bg="#E8F7EE",
                              fg=C["success"])
        self.p_val.pack(anchor="w")
        self.p_pct = tk.Label(self.pbox, text="—", font=("Segoe UI", 9, "bold"), bg=C["success"],
                              fg="white", padx=8, pady=2)
        self.p_pct.pack(side="right", padx=10)
        for k, lbl in (("stock", "Stock"), ("plu", "PLU No")):
            self.rows[k] = self._row(inner, lbl)
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", pady=(6, 4))
        self._head(inner, "UNITS")
        self.unit_rows = [self._row(inner, "") for _ in range(3)]
        self.more_units = tk.Label(inner, text="", font=("Segoe UI", 8), bg=C["card_bg"],
                                   fg=C["text_secondary"])
        self.more_units.pack(anchor="w")
        self.bc_head = self._head(inner, "BARCODES")
        self.bc_text = tk.Label(inner, text="", font=("Consolas", 8), bg=C["card_bg"],
                                fg=C["text_primary"], justify="left", anchor="w",
                                wraplength=self.WIDTH - 30)
        self.bc_text.pack(fill="x", anchor="w")
        self.refresh()
        self._tick()

    def _head(self, parent, text):
        lb = tk.Label(parent, text=text, font=("Segoe UI", 8, "bold"), bg=self.C["card_bg"],
                      fg=self.C["text_secondary"])
        lb.pack(anchor="w", pady=(2, 2))
        return lb

    def _row(self, parent, label):
        f = tk.Frame(parent, bg=self.C["card_bg"])
        f.pack(fill="x", pady=1)
        a = tk.Label(f, text=label, font=("Segoe UI", 9), bg=self.C["card_bg"],
                     fg=self.C["text_secondary"])
        a.pack(side="left")
        b = tk.Label(f, text="", font=("Segoe UI", 9, "bold"), bg=self.C["card_bg"],
                     fg=self.C["text_primary"])
        b.pack(side="right")
        return a, b

    def _tick(self):
        try:
            if not self.frame.winfo_exists():
                return
            self.refresh()
            self.frame.after(400, self._tick)
        except Exception:
            pass

    def refresh(self):
        v = values(self.form)
        sig = repr(sorted(v.items()))
        if sig == self._sig:
            return v
        self._sig = sig
        m = lambda x: format(x, ",.2f")
        self.rows["gross"][1].configure(text=m(v["gross"]))
        self.rows["net"][1].configure(text=m(v["net"]))
        self.rows["cost"][1].configure(text=m(v["cost"]) if v["cost"] else "—")
        loss = v["profit"] < 0
        bg = "#FDECEC" if loss else "#E8F7EE"
        fg = self.C.get("danger", "#DC2626") if loss else self.C.get("success", "#16A34A")
        for w in (self.pbox, self.p_cap, self.p_val, self.p_cap.master):
            w.configure(bg=bg)
        self.p_cap.configure(text="Loss / unit — below cost" if loss else "Profit / unit")
        self.p_val.configure(text=m(v["profit"]) if v["net"] else "—", fg=fg)
        self.p_pct.configure(text=("%.1f %%" % v["pct"]) if v["pct"] is not None else "—", bg=fg)
        self.rows["stock"][1].configure(text="%g %s" % (v["stock"], v["unit"]))
        self.rows["plu"][1].configure(text=v["plu"] or "—")
        for i, (a, b) in enumerate(self.unit_rows):
            if i < len(v["units"]):
                name, f, price = v["units"][i]
                a.configure(text="%d · %s × %g" % (i + 1, name, f))
                b.configure(text=m(price) if price else "—")
            else:
                a.configure(text="")
                b.configure(text="")
        self.more_units.configure(text=("+ %d more" % v["more_units"]) if v["more_units"] else "")
        self.bc_head.configure(text="BARCODES  (%d)" % len(v["barcodes"]))
        bcs = v["barcodes"]
        self.bc_text.configure(text="\n".join(bcs[:5]) + (("\n+ %d more" % (len(bcs) - 5)) if len(bcs) > 5 else "")
                               if bcs else "— (made on Save)")
        return v
