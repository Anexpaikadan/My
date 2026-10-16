# ============================================================
# DayBill ERP - Barcode label batch print
# ------------------------------------------------------------
# Generates an A4 sheet of barcode labels (name · price · EAN-13)
# for selected products, N copies each. Uses reportlab's built-in
# EAN-13 widget (no extra dependency). Opened from the product list.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db


def _money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


def generate_label_sheet(items, out_path, cols=3, rows=8,
                         currency="SAR", company=""):
    """
    items: list of dicts {name, price, barcode, copies}
    Lays them out on A4 in a cols×rows grid.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics.barcode import eanbc, code128
    from reportlab.graphics import renderPDF
    from reportlab.graphics.shapes import Drawing

    W, H = A4
    margin = 8 * mm
    cell_w = (W - 2 * margin) / cols
    cell_h = (H - 2 * margin) / rows
    c = canvas.Canvas(out_path, pagesize=A4)

    # expand copies
    flat = []
    for it in items:
        flat.extend([it] * max(1, int(it.get("copies", 1))))

    i = 0
    for it in flat:
        col = i % cols
        row = (i // cols) % rows
        if i > 0 and col == 0 and row == 0:
            c.showPage()
        x = margin + col * cell_w
        y = H - margin - (row + 1) * cell_h
        cx = x + cell_w / 2

        # name
        c.setFont("Helvetica-Bold", 8)
        name = (it.get("name") or "")[:28]
        c.drawCentredString(cx, y + cell_h - 10, name)
        # price
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(cx, y + cell_h - 22,
                            f"{_money(it.get('price'))} {currency}")
        # barcode
        code = "".join(ch for ch in str(it.get("barcode") or "") if ch.isdigit())
        try:
            if len(code) in (12, 13):
                bc = eanbc.Ean13BarcodeWidget(code[:13].rjust(13, "0"))
            elif code:
                bc = code128.Code128(code, barHeight=12 * mm, barWidth=0.4)
                bc.drawOn(c, x + 6 * mm, y + 6)
                bc = None
            else:
                bc = None
            if bc is not None:
                d = Drawing()
                d.add(bc)
                b = d.getBounds()
                scale = min((cell_w - 10 * mm) / (b[2] - b[0]), 1.4)
                d.scale(scale, scale)
                renderPDF.draw(d, c, cx - ((b[2] - b[0]) * scale) / 2, y + 5)
        except Exception:
            c.setFont("Helvetica", 7)
            c.drawCentredString(cx, y + 12, code or "(no barcode)")

        # cut guide
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.3)
        c.rect(x + 2, y + 2, cell_w - 4, cell_h - 4, stroke=1, fill=0)
        i += 1

    c.showPage()
    c.save()
    return out_path


class LabelPrintDialog:
    """Pick products + copies, then generate the sheet."""
    def __init__(self, parent, preselected_ids=None):
        C = cfg.theme()
        self.C = C
        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("Print Barcode Labels")
        self.win.configure(bg=C["card_bg"])
        self.win.geometry("560x560")
        self.win.transient(parent.winfo_toplevel())
        self.win.grab_set()
        self.products = self._load_products()
        self.copies = {}
        self._build(C, preselected_ids or set())

    def _load_products(self):
        try:
            return db.fetchall(
                "SELECT product_id, product_code, product_name_en, unit_price, "
                "ISNULL(barcode,'') AS barcode FROM products WHERE is_active=1 "
                "ORDER BY product_name_en") or []
        except Exception:
            return []

    def _build(self, C, preselected):
        tk.Label(self.win, text="🏷  Barcode Labels", font=("Segoe UI", 14, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", padx=16, pady=(12, 4))

        opt = tk.Frame(self.win, bg=C["card_bg"]); opt.pack(fill="x", padx=16)
        tk.Label(opt, text="Layout", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        _LAYOUTS = ["20x10 mm", "30x20 mm", "40x25 mm", "50x25 mm", "60x40 mm",
                    "2 × 7 (14/page)", "3 × 8 (24/page)", "4 × 10 (40/page)"]
        _def = str(cfg.get("barcode_label_size", "40x25 mm") or "")   # Settings ▸ Barcode
        if _def and "mm" not in _def and "×" not in _def:
            _def = _def + " mm"
        self.layout_var = tk.StringVar(value=_def if _def in _LAYOUTS else "40x25 mm")
        ttk.Combobox(opt, textvariable=self.layout_var, width=18, state="readonly",
                     values=["20x10 mm", "30x20 mm", "40x25 mm", "50x25 mm",
                             "60x40 mm", "2 × 7 (14/page)", "3 × 8 (24/page)",
                             "4 × 10 (40/page)"]).pack(side="left", padx=(6, 16))
        tk.Label(opt, text="Default copies", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.def_copies = tk.StringVar(value="1")
        tk.Entry(opt, textvariable=self.def_copies, width=5, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(6, 0))
        tk.Button(opt, text="Apply to all", font=("Segoe UI", 8, "bold"),
                  bg=C["content_bg"], relief="flat", cursor="hand2",
                  command=self._apply_all).pack(side="left", padx=(6, 0))

        # search
        sf = tk.Frame(self.win, bg=C["card_bg"]); sf.pack(fill="x", padx=16, pady=(8, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._render_rows())
        tk.Entry(sf, textvariable=self.search_var, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(fill="x", ipady=3)
        tk.Label(sf, text="Set a copy count next to each product (0 = skip).",
                 font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")

        # scrollable product list
        wrap = tk.Frame(self.win, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=4)
        self.canvas = tk.Canvas(wrap, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.rows_holder = tk.Frame(self.canvas, bg="white")
        self.rows_holder.bind("<Configure>",
                              lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.rows_holder, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for p in self.products:
            self.copies[p["product_id"]] = tk.StringVar(
                value="1" if p["product_id"] in preselected else "0")
        self._render_rows()

        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", padx=16, pady=10)
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#EEF1F6",
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self.win.destroy).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(btns, text="🖨  Generate sheet", font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg="white", relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self._generate).pack(side="left", expand=True,
                                                               fill="x", padx=(4, 0))

    def _render_rows(self):
        C = self.C
        for w in self.rows_holder.winfo_children():
            w.destroy()
        q = self.search_var.get().lower()
        for p in self.products:
            if q and q not in (p["product_name_en"] or "").lower() \
                    and q not in str(p["barcode"]).lower():
                continue
            r = tk.Frame(self.rows_holder, bg="white")
            r.pack(fill="x", pady=1)
            tk.Entry(r, textvariable=self.copies[p["product_id"]], width=4,
                     font=("Segoe UI", 9), relief="solid", bd=1,
                     justify="center").pack(side="left", padx=(2, 8))
            tk.Label(r, text=(p["product_name_en"] or "")[:36], bg="white",
                     fg=C["text_primary"], font=("Segoe UI", 9), anchor="w",
                     width=34).pack(side="left")
            tk.Label(r, text=f"{_money(p['unit_price'])}", bg="white",
                     fg=C["text_secondary"], font=("Segoe UI", 9),
                     width=10, anchor="e").pack(side="left")
            tk.Label(r, text=p["barcode"] or "—", bg="white",
                     fg=C["text_secondary"], font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))

    def _apply_all(self):
        v = self.def_copies.get()
        for var in self.copies.values():
            var.set(v)
        self._render_rows()

    def _generate(self):
        sel = self.layout_var.get()
        mm_sizes = {"20x10 mm": (20, 10), "30x20 mm": (30, 20),
                    "40x25 mm": (40, 25), "50x25 mm": (50, 25),
                    "60x40 mm": (60, 40)}
        if sel in mm_sizes:
            lw, lh = mm_sizes[sel]
            # A4 usable area ~194 x 281 mm with 8mm margins
            layout = (max(1, int(194 // lw)), max(1, int(281 // lh)))
        else:
            layout = {"2 × 7 (14/page)": (2, 7), "3 × 8 (24/page)": (3, 8),
                      "4 × 10 (40/page)": (4, 10)}.get(sel, (3, 8))
        items = []
        for p in self.products:
            try:
                cp = int(float(self.copies[p["product_id"]].get() or 0))
            except Exception:
                cp = 0
            if cp > 0:
                items.append({"name": p["product_name_en"], "price": p["unit_price"],
                              "barcode": p["barcode"], "copies": cp})
        if not items:
            messagebox.showwarning("Labels", "Set a copy count (>0) for at least "
                                   "one product.", parent=self.win)
            return
        out = os.path.join(tempfile.gettempdir(), "labels.pdf")
        try:
            generate_label_sheet(items, out, cols=layout[0], rows=layout[1],
                                  currency=cfg.get("currency", "SAR"))
            try:
                from modules import audit
                audit.log("print", "labels", None, f"{sum(i['copies'] for i in items)} labels")
            except Exception:
                pass
            self.last_pdf = out
            from ui import print_menu
            print_menu.send_pdf(self.win, out,
                                f"{sum(i['copies'] for i in items)} label(s)", "labels")
            self.win.destroy()
        except Exception as e:
            messagebox.showerror("Labels", str(e)[:250], parent=self.win)
