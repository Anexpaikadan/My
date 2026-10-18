# ============================================================
# DayBill ERP - Price Change Labels
# ------------------------------------------------------------
# Every selling-price change (product form, units, bulk rates,
# Excel import) and every new priced item is listed here, so the
# shelf labels can be reprinted in one go — with the Label Designer
# template of your choice — and ticked off as printed.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules import price_watch as pw

SIMPLE = ["Simple sheet 3 × 8 (A4)", "Simple sheet 4 × 10 (A4)", "Simple sheet 2 × 7 (A4)"]


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


class PriceLabelsView:
    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.parent = parent
        self.rows = []
        self.sel = set()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=20, pady=(16, 2))
        tk.Label(top, text="🏷  Price Change Labels", font=("Segoe UI", 17, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Label(self.frame, text="Items whose selling price changed (or new items) — tick them "
                                  "and print new shelf labels.",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=22)

        bar = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        bar.pack(fill="x", padx=20, pady=(10, 6))
        b = tk.Frame(bar, bg=C["card_bg"]); b.pack(fill="x", padx=12, pady=8)
        tk.Label(b, text="Show", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.show = tk.StringVar(value="Not printed yet")
        cb = ttk.Combobox(b, textvariable=self.show, values=["Not printed yet", "All changes"],
                          state="readonly", width=15, font=("Segoe UI", 9))
        cb.pack(side="left", padx=(0, 14))
        cb.bind("<<ComboboxSelected>>", lambda e: self.load())
        tk.Label(b, text="Since", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.since = tk.StringVar(value=(date.today() - timedelta(days=30)).isoformat())
        se = tk.Entry(b, textvariable=self.since, width=11, font=("Segoe UI", 10),
                      relief="solid", bd=1)
        se.pack(side="left", ipady=2, padx=(0, 14))
        se.bind("<Return>", lambda e: self.load())
        try:
            from ui.datepicker import attach_datepicker
            attach_datepicker(se, self.since, on_pick=lambda *a: self.load())
        except Exception:
            pass
        tk.Label(b, text="Search", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.q = tk.StringVar()
        qe = tk.Entry(b, textvariable=self.q, width=24, font=("Segoe UI", 10),
                      relief="solid", bd=1)
        qe.pack(side="left", ipady=2)
        qe.bind("<KeyRelease>", lambda e: self._fill())
        tk.Button(b, text="🔄  Refresh", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=10, pady=3, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.load).pack(side="right")

        wrap = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        cols = [("sel", "✓", 40, "center"), ("when", "Changed", 145, "center"),
                ("code", "Code", 90, "w"), ("name", "Product", 250, "w"),
                ("unit", "Unit", 70, "center"), ("barcode", "Barcode", 130, "w"),
                ("old", "Old price", 90, "e"), ("new", "New price", 90, "e"),
                ("chg", "Change", 80, "e"), ("src", "Source", 90, "center"),
                ("printed", "Label", 80, "center")]
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings",
                                 selectmode="extended")
        for k, h, w, a in cols:
            self.tree.heading(k, text=h, anchor="e" if a == "e" else ("w" if a == "w" else "center"))
            self.tree.column(k, width=w, anchor=a, stretch=k == "name")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("on", background="#ECFDF3")
        self.tree.tag_configure("up", foreground=C["danger"])
        self.tree.tag_configure("down", foreground=C["success"])
        self.tree.bind("<Button-1>", self._click, add="+")
        self.tree.bind("<space>", lambda e: self._toggle_selected())
        self.tree.bind("<Control-a>", lambda e: (self.select_all(), "break")[1])

        foot = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        foot.pack(fill="x", padx=20, pady=(0, 14))
        f = tk.Frame(foot, bg=C["card_bg"]); f.pack(fill="x", padx=12, pady=8)
        for txt, cmd in (("☑  All", self.select_all), ("☐  None", self.select_none)):
            tk.Button(f, text=txt, font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", padx=10, pady=4, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=cmd).pack(side="left", padx=(0, 6))
        tk.Label(f, text="Label", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(12, 4))
        self.templates = []
        try:
            from modules import barcode_designer as bd
            self.templates = bd.list_templates() if bd.tables_ready() else []
        except Exception:
            self.templates = []
        opts = [t["template_name"] for t in self.templates] + SIMPLE
        self.tpl = tk.StringVar(value=opts[0])
        ttk.Combobox(f, textvariable=self.tpl, values=opts, state="readonly", width=26,
                     font=("Segoe UI", 9)).pack(side="left")
        tk.Label(f, text="Copies", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(12, 4))
        self.copies = tk.StringVar(value="1")
        tk.Spinbox(f, from_=1, to=50, textvariable=self.copies, width=4,
                   font=("Segoe UI", 10)).pack(side="left")
        self.count = tk.StringVar()
        tk.Label(f, textvariable=self.count, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(14, 0))
        tk.Button(f, text="🗑  Remove", font=("Segoe UI", 9), bg="#FEF2F2", fg=C["danger"],
                  relief="flat", padx=10, pady=5, cursor="hand2",
                  command=self.remove).pack(side="right")
        tk.Button(f, text="✔  Mark printed", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=10, pady=5, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.mark).pack(side="right", padx=(0, 6))
        tk.Button(f, text="🏷  Print Labels", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=5,
                  cursor="hand2", command=self.print_labels).pack(side="right", padx=(0, 6))
        self.load()

    # ── data ──────────────────────────────────────────────────
    def load(self):
        if not pw.ready():
            self.rows = []
            self._fill()
            self.count.set("⚠ Restart DayBill once to install the price log.")
            return
        try:
            self.rows = pw.pending(self.since.get().strip() or None,
                                   include_printed=self.show.get() == "All changes")
        except Exception as e:
            self.rows = []
            self.count.set("⚠ " + str(e)[:80])
        self.sel = {self._key(r) for r in self.rows if not r.get("label_printed")}
        self._fill()

    @staticmethod
    def _key(r):
        return f"{r['product_id']}:{r.get('unit_id') or 0}"

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        q = self.q.get().strip().lower()
        shown = 0
        for r in self.rows:
            if q and q not in " ".join(str(r.get(x) or "") for x in
                                       ("product_code", "product_name_en", "barcode")).lower():
                continue
            k = self._key(r)
            old, new = _f(r.get("first_old")), _f(r.get("new_price"))
            chg = ""
            tag = []
            if old and new is not None:
                pct = (new - old) / old * 100 if old else 0
                chg = ("▲ " if new > old else "▼ ") + f"{pct:+.1f}%"
            if k in self.sel:
                tag.append("on")
            when = str(r.get("changed_at") or "")[:16]
            self.tree.insert("", "end", iid=k, values=(
                "☑" if k in self.sel else "☐", when, r.get("product_code") or "",
                r.get("product_name_en") or "", r.get("unit_name") or "",
                r.get("barcode") or "", "" if old is None else f"{old:,.2f}",
                f"{new:,.2f}" if new is not None else "", chg or "new",
                (r.get("source") or "").replace("_", " "),
                "✔ printed" if r.get("label_printed") else "—"), tags=tuple(tag))
            shown += 1
        self.count.set(f"{shown} item(s) · {len(self.sel)} ticked")

    # ── selection ─────────────────────────────────────────────
    def _click(self, e):
        if self.tree.identify_region(e.x, e.y) != "cell":
            return
        iid = self.tree.identify_row(e.y)
        if iid and self.tree.identify_column(e.x) == "#1":
            self._toggle(iid)
            return "break"

    def _toggle(self, iid):
        if iid in self.sel:
            self.sel.discard(iid)
        else:
            self.sel.add(iid)
        self._fill()
        if self.tree.exists(iid):
            self.tree.focus(iid)

    def _toggle_selected(self):
        for iid in self.tree.selection() or ([self.tree.focus()] if self.tree.focus() else []):
            self._toggle(iid)
        return "break"

    def select_all(self):
        self.sel = {self._key(r) for r in self.rows}
        self._fill()

    def select_none(self):
        self.sel = set()
        self._fill()

    def _ticked(self):
        return [r for r in self.rows if self._key(r) in self.sel]

    # ── actions ───────────────────────────────────────────────
    def _items(self, rows, copies):
        prods = {}
        try:
            from modules import barcode_designer as bd
            for p in bd.products_for_print():
                prods[p["product_id"]] = p
        except Exception:
            pass
        out = []
        for r in rows:
            p = dict(prods.get(r["product_id"]) or {})
            name = r.get("product_name_en") or p.get("product_name_en") or ""
            unit = r.get("unit_name") or ""
            if unit and unit.lower() not in ("pcs", "unit", "piece", "nos", "each"):
                name = f"{name} ({unit})"
            p.update({"product_id": r["product_id"], "product_code": r.get("product_code"),
                      "product_name_en": name, "product_name_ar": r.get("product_name_ar"),
                      "unit_price": _f(r.get("new_price")) or 0,
                      "barcode_value": r.get("barcode") or p.get("barcode") or r.get("product_code"),
                      "copies": copies})
            out.append(p)
        return out

    def print_labels(self):
        try:
            from modules import permissions as _pm
            if not _pm.allowed("products", "print"):
                return
        except Exception:
            pass
        rows = self._ticked()
        if not rows:
            messagebox.showinfo("Labels", "Tick at least one item (click ☐ or press Space).")
            return
        try:
            copies = max(1, int(float(self.copies.get() or 1)))
        except Exception:
            copies = 1
        items = self._items(rows, copies)
        path = os.path.join(tempfile.gettempdir(), f"price_labels_{date.today():%Y%m%d}.pdf")
        choice = self.tpl.get()
        try:
            tpl = next((t for t in self.templates if t["template_name"] == choice), None)
            if tpl:
                from modules import barcode_designer as bd
                bd.render_labels_pdf(tpl, items, path)
            else:
                from ui.label_print import generate_label_sheet
                cols, rws = {"Simple sheet 4 × 10 (A4)": (4, 10),
                             "Simple sheet 2 × 7 (A4)": (2, 7)}.get(choice, (3, 8))
                generate_label_sheet([{"name": i["product_name_en"], "price": i["unit_price"],
                                       "barcode": i["barcode_value"], "copies": copies}
                                      for i in items], path, cols=cols, rows=rws,
                                     currency=__import__("modules.country", fromlist=["symbol"]).symbol())
        except Exception as e:
            messagebox.showerror("Labels", str(e)[:300])
            return
        ids = [i for r in rows for i in r["ids"]]
        try:
            pw.mark_printed(ids)
            from modules import audit
            audit.log("print", "price_labels", None, f"{len(rows)} items × {copies}")
        except Exception:
            pass
        self.last_pdf = path
        try:
            from ui import print_menu
            print_menu.send_pdf(self.frame, path, f"{len(rows) * copies} shelf label(s)",
                                "labels")
        except Exception:
            pass
        self.load()
        self.count.set(f"🏷 {len(rows) * copies} label(s) sent — {os.path.basename(path)}")

    def mark(self):
        rows = self._ticked()
        if rows and messagebox.askyesno("Labels", f"Mark {len(rows)} item(s) as printed "
                                                  f"without printing?"):
            pw.mark_printed([i for r in rows for i in r["ids"]])
            self.load()

    def remove(self):
        rows = self._ticked()
        if rows and messagebox.askyesno("Labels", f"Remove {len(rows)} item(s) from the list?"):
            pw.dismiss([i for r in rows for i in r["ids"]])
            self.load()
