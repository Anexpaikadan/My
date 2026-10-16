# ============================================================
# DayBill ERP - Offers & Promotions screen
# ------------------------------------------------------------
# Make an offer in a few clicks:
#   1. pick the deal  (−20 %, half price, special price, SAR off,
#      buy 1 get 1 / buy 1 get 2 / buy 2 get 1 …)
#   2. pick the products (type, scan a barcode, or a whole category)
#   3. pick when (start / end date + time, days of the week, hours)
# POS and the Sales invoice give the discount by themselves while the
# offer runs. 🎨 Poster prompt makes a ready prompt for ChatGPT /
# Gemini to draw the offer poster.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, webbrowser
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import offers as O

# deal buttons: key → (button text, offer_type, defaults)
DEALS = [
    ("pct",   "%  OFF",          "percent", {"offer_value": 20}),
    ("half",  "½  HALF PRICE",   "percent", {"offer_value": 50}),
    ("price", "🏷  SPECIAL PRICE", "price",  {}),
    ("amt",   "SAR  OFF",        "amount",  {"offer_value": 1}),
    ("bxgy",  "🎁  BUY X GET Y",  "buy_get", {"buy_qty": 1, "get_qty": 1, "get_pct": 100}),
]
GET_AT = [("FREE", 100), ("Half price", 50), ("25% off", 25), ("75% off", 75)]
# Saudi week order on screen; the mask is Mon..Sun
WEEK = [("Sun", 6), ("Mon", 0), ("Tue", 1), ("Wed", 2), ("Thu", 3), ("Fri", 4), ("Sat", 5)]


def _f(v, d=0.0):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return d


def _money(v):
    return "{:,.2f}".format(_f(v))


# ── product data (shared by the editor + poster) ─────────────
class _Catalog:
    def __init__(self):
        try:
            self.products = [dict(r) for r in db.fetchall(
                "SELECT product_id, product_code, product_name_en, product_name_ar, "
                "unit_price, category_id, barcode FROM products "
                "WHERE ISNULL(is_active,1)=1 ORDER BY product_name_en") or []]
        except Exception:
            self.products = []
        try:
            units = [dict(r) for r in db.fetchall(
                "SELECT unit_id, product_id, unit_name_en, conversion_factor, selling_price, "
                "barcode, is_default FROM product_units WHERE ISNULL(is_active,1)=1 "
                "ORDER BY product_id, conversion_factor") or []]
        except Exception:
            units = []
        self.units = {}
        for u in units:
            self.units.setdefault(u.get("product_id"), []).append(u)
        try:
            self.categories = [dict(r) for r in db.fetchall(
                "SELECT category_id, category_name_en FROM product_categories "
                "WHERE ISNULL(is_active,1)=1 ORDER BY category_name_en") or []]
        except Exception:
            self.categories = []
        self.products = [p for p in self.products if p.get("product_id") is not None]
        self.by_id = {p["product_id"]: p for p in self.products}

    def default_unit(self, pid):
        us = self.units.get(pid) or []
        return next((u for u in us if u.get("is_default")), us[0] if us else None)

    def price(self, pid, unit_name=None):
        """Selling price of the unit (default unit when none given)."""
        p = self.by_id.get(pid) or {}
        us = self.units.get(pid) or []
        u = None
        if unit_name:
            u = next((x for x in us if str(x["unit_name_en"]).lower() == str(unit_name).lower()), None)
        u = u or self.default_unit(pid)
        if u:
            return _f(u.get("selling_price")) or _f(p.get("unit_price")) * _f(u.get("conversion_factor"), 1)
        return _f(p.get("unit_price"))

    def find_code(self, code):
        """Exact barcode / product code → product."""
        code = str(code or "").strip()
        if not code:
            return None, None
        for pid, us in self.units.items():
            for u in us:
                if str(u.get("barcode") or "") == code:
                    return self.by_id.get(pid), u
        for p in self.products:
            if code in (str(p.get("barcode") or ""), str(p.get("product_code") or "")):
                return p, None
        try:      # extra barcodes / scale labels: the shared resolver
            from modules.barcode_resolver import resolve
            hit = resolve(code, products=self.products)
            if hit and self.by_id.get(hit["product_id"]):
                us = self.units.get(hit["product_id"]) or []
                u = next((x for x in us if hit["unit_id"] and x.get("unit_id") == hit["unit_id"]), None)
                return self.by_id[hit["product_id"]], u
        except Exception:
            pass
        return None, None

    def search(self, text, limit=8):
        t = str(text or "").strip().lower()
        if not t:
            return []
        out = []
        for p in self.products:
            hay = " ".join(str(p.get(k) or "") for k in
                           ("product_code", "product_name_en", "product_name_ar", "barcode")).lower()
            if t in hay:
                out.append(p)
                if len(out) >= limit:
                    break
        return out


# ============================================================
# Offers list
# ============================================================
class OffersView:
    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.parent = parent
        self.rows = []
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=20, pady=(16, 2))
        tk.Label(top, text="🏷  Offers & Promotions", font=("Segoe UI", 17, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        self.live_lbl = tk.Label(top, text="", font=("Segoe UI", 9, "bold"),
                                 bg="#ECFDF3", fg="#047857", padx=10, pady=4)
        self.live_lbl.pack(side="right")
        tk.Label(self.frame, text="Pick the deal, the products and the dates — POS and the Sales "
                                  "invoice give the discount by themselves while the offer runs.",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=22)

        # quick-start tiles
        tiles = tk.Frame(self.frame, bg=C["content_bg"]); tiles.pack(fill="x", padx=20, pady=(10, 4))
        quick = [("−20%", "#E11D48", ("pct", {"offer_value": 20})),
                 ("½ Half price", "#EA580C", ("half", {})),
                 ("🏷 Special price", "#2563EB", ("price", {})),
                 ("SAR off", "#0891B2", ("amt", {})),
                 ("🎁 Buy 1 Get 1", "#16A34A", ("bxgy", {"buy_qty": 1, "get_qty": 1})),
                 ("🎁 Buy 1 Get 2", "#15803D", ("bxgy", {"buy_qty": 1, "get_qty": 2})),
                 ("🎁 Buy 2 Get 1", "#166534", ("bxgy", {"buy_qty": 2, "get_qty": 1}))]
        for txt, col, preset in quick:
            tk.Button(tiles, text=txt, font=("Segoe UI", 10, "bold"), bg=col, fg="white",
                      activebackground=col, activeforeground="white", relief="flat",
                      padx=14, pady=8, cursor="hand2",
                      command=lambda p=preset: self._new(p)).pack(side="left", padx=(0, 8))

        bar = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        bar.pack(fill="x", padx=20, pady=(6, 6))
        b = tk.Frame(bar, bg=C["card_bg"]); b.pack(fill="x", padx=12, pady=8)
        tk.Label(b, text="Show", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.show = tk.StringVar(value="All")
        cb = ttk.Combobox(b, textvariable=self.show, state="readonly", width=16,
                          values=["All", "Running now", "Starting later", "Ended", "Paused"],
                          font=("Segoe UI", 9))
        cb.pack(side="left", padx=(0, 14))
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill())
        tk.Label(b, text="Search", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        self.q = tk.StringVar()
        qe = tk.Entry(b, textvariable=self.q, width=26, font=("Segoe UI", 10),
                      relief="solid", bd=1)
        qe.pack(side="left", ipady=2)
        qe.bind("<KeyRelease>", lambda e: self._fill())
        tk.Button(b, text="＋  New offer", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=12, pady=4, cursor="hand2",
                  command=lambda: self._new()).pack(side="right")
        tk.Button(b, text="🔄", font=("Segoe UI", 9), bg=C["card_bg"], relief="flat",
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=self.load).pack(side="right", padx=(0, 8))

        wrap = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        cols = [("status", "Status", 175, "w"), ("name", "Offer", 200, "w"),
                ("deal", "Deal", 150, "w"), ("items", "Products", 230, "w"),
                ("when", "When", 250, "w"), ("where", "Used in", 85, "center"),
                ("sold", "Sold (discount)", 150, "e")]
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings",
                                 selectmode="browse")
        for k, h, w, a in cols:
            self.tree.heading(k, text=h, anchor="e" if a == "e" else ("w" if a == "w" else "center"))
            self.tree.column(k, width=w, anchor=a, stretch=k in ("name", "items", "when"))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("live", background="#ECFDF3")
        self.tree.tag_configure("ended", foreground="#9CA3AF")
        self.tree.tag_configure("paused", foreground="#B45309")
        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.tree.bind("<Return>", lambda e: self._edit())
        self.tree.bind("<Delete>", lambda e: self._delete())

        foot = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        foot.pack(fill="x", padx=20, pady=(0, 14))
        f = tk.Frame(foot, bg=C["card_bg"]); f.pack(fill="x", padx=12, pady=8)
        for txt, cmd in (("✏  Edit", self._edit), ("⧉  Copy", self._copy),
                         ("⏸ / ▶  Pause / Run", self._toggle), ("🗑  Delete", self._delete)):
            tk.Button(f, text=txt, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=cmd).pack(side="left", padx=(0, 6))
        tk.Button(f, text="🎨  Poster prompt (ChatGPT / Gemini)", font=("Segoe UI", 9, "bold"),
                  bg="#7C3AED", fg="white", relief="flat", padx=12, pady=4, cursor="hand2",
                  command=self._poster).pack(side="right")
        self.msg = tk.StringVar()
        tk.Label(f, textvariable=self.msg, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=12)
        self.load()

    # ── data ─────────────────────────────────────────────────
    def load(self):
        if not O.tables_ready():
            self.rows = []
            self.msg.set("⚠ Offer tables are missing — open Updates ▸ Apply All Updates once.")
            self._fill()
            return
        O.invalidate()
        self.rows = O.load_all()
        for o in self.rows:
            o["_status"] = O.status(o)
            o["_sold"] = O.sales_summary(o["offer_id"])
        self._fill()

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        want = {"Running now": ("live",), "Starting later": ("soon", "wait"),
                "Ended": ("ended",), "Paused": ("paused",)}.get(self.show.get())
        q = self.q.get().strip().lower()
        live = 0
        for o in self.rows:
            code, stxt = o.get("_status", ("", ""))
            live += code == "live"
            if want and code not in want:
                continue
            names = [str(it.get("product_name_en") or "?") for it in o.get("items", [])]
            if q and q not in (str(o.get("offer_name") or "") + " " + " ".join(names)).lower():
                continue
            prod = ("%d · " % len(names) + ", ".join(names[:3])
                    + (" …" if len(names) > 3 else "")) if names else "—"
            where = "+".join(x for x, k in (("POS", "for_pos"), ("Sales", "for_sales")) if o.get(k)) or "—"
            bills, qty, disc = o.get("_sold", (0, 0, 0))
            self.tree.insert("", "end", iid=str(o["offer_id"]), values=(
                stxt, o.get("offer_name", ""), O.label(o, (o.get("items") or [{}])[0]),
                prod, O.when_text(o), where,
                ("%d bill%s · %s" % (bills, "" if bills == 1 else "s", _money(disc)))
                if bills else "—"),
                tags=(code,) if code in ("live", "ended", "paused") else ())
        self.live_lbl.configure(text="🟢 %d offer%s running now" % (live, "" if live == 1 else "s"))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Offers", "Select an offer first.", parent=self.frame)
            return None
        oid = int(sel[0])
        return next((o for o in self.rows if o["offer_id"] == oid), None)

    # ── actions ──────────────────────────────────────────────
    def _new(self, preset=None, product_ids=None):
        if not O.tables_ready():
            messagebox.showwarning("Offers", "Offer tables are missing — open Updates ▸ "
                                   "Apply All Updates once.", parent=self.frame)
            return
        OfferEditor(self.frame, preset=preset, product_ids=product_ids, on_saved=self._saved)

    def _edit(self):
        o = self._selected()
        if o:
            OfferEditor(self.frame, offer=o, on_saved=self._saved)

    def _copy(self):
        o = self._selected()
        if o:
            c = dict(o); c.pop("offer_id", None)
            c["offer_name"] = (o.get("offer_name") or "") + " (copy)"
            OfferEditor(self.frame, offer=c, on_saved=self._saved)

    def _toggle(self):
        o = self._selected()
        if o:
            O.set_active(o["offer_id"], not o.get("is_active"))
            self.msg.set(("▶ Running: " if not o.get("is_active") else "⏸ Paused: ")
                         + o.get("offer_name", ""))
            self.load()

    def _delete(self):
        o = self._selected()
        if o and messagebox.askyesno("Delete offer", "Delete the offer '%s'?\n\nBills already "
                                     "sold keep their discount." % o.get("offer_name", ""),
                                     parent=self.frame):
            O.delete(o["offer_id"])
            self.msg.set("🗑 Deleted: " + o.get("offer_name", ""))
            self.load()

    def _poster(self):
        o = self._selected()
        if o:
            PosterPromptDialog(self.frame, o, o.get("items", []))

    def _saved(self, oid):
        self.load()
        try:
            self.tree.selection_set(str(oid)); self.tree.see(str(oid))
        except Exception:
            pass
        self.msg.set("✅ Offer saved — POS and Sales use it at once.")


# ============================================================
# Offer editor
# ============================================================
class OfferEditor(tk.Toplevel):
    def __init__(self, parent, offer=None, preset=None, product_ids=None, on_saved=None):
        super().__init__(parent)
        C = self.C = cfg.theme()
        self.on_saved = on_saved
        self.offer = dict(offer or {})
        self.cat = _Catalog()
        self.items = []                 # [{product_id, unit_name, offer_price}]
        self.title("Offer" if not self.offer.get("offer_id") else
                   "Offer — " + str(self.offer.get("offer_name", "")))
        self.configure(bg=C["content_bg"])
        self.geometry("980x700")
        self.minsize(900, 620)
        try:
            self.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self._build()
        self._load(preset, product_ids)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-s>", lambda e: self._save())
        self.name_e.focus_set()

    # ── layout ───────────────────────────────────────────────
    def _card(self, parent, title):
        C = self.C
        box = tk.Frame(parent, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        box.pack(fill="x", padx=14, pady=(8, 0))
        tk.Label(box, text=title, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=12, pady=(6, 0))
        inner = tk.Frame(box, bg=C["card_bg"]); inner.pack(fill="x", padx=12, pady=(2, 8))
        return inner

    def _lbl(self, parent, text):
        return tk.Label(parent, text=text, font=("Segoe UI", 9), bg=self.C["card_bg"],
                        fg=self.C["text_secondary"])

    def _entry(self, parent, var, width, **kw):
        e = tk.Entry(parent, textvariable=var, width=width, font=("Segoe UI", 10),
                     relief="solid", bd=1, **kw)
        return e

    def _build(self):
        C = self.C
        # footer first (always visible)
        foot = tk.Frame(self, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        foot.pack(side="bottom", fill="x")
        ff = tk.Frame(foot, bg=C["card_bg"]); ff.pack(fill="x", padx=14, pady=8)
        self.preview = tk.StringVar()
        tk.Label(ff, textvariable=self.preview, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg="#047857", anchor="w", justify="left", wraplength=520).pack(side="left")
        tk.Button(ff, text="💾  Save offer  (Ctrl+S)", font=("Segoe UI", 10, "bold"),
                  bg=C.get("tile_green", "#16A34A"), fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._save).pack(side="right")
        tk.Button(ff, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"], relief="flat",
                  padx=12, pady=6, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self.destroy).pack(side="right", padx=8)
        tk.Button(ff, text="🎨  Poster prompt", font=("Segoe UI", 10, "bold"), bg="#7C3AED",
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._poster).pack(side="right")

        # 1. name + deal
        a = self._card(self, "1.  NAME  &  DEAL")
        r = tk.Frame(a, bg=C["card_bg"]); r.pack(fill="x")
        self.name_v = tk.StringVar(); self.name_ar_v = tk.StringVar()
        self._lbl(r, "Offer name").pack(side="left")
        self.name_e = self._entry(r, self.name_v, 34); self.name_e.pack(side="left", padx=(4, 14), ipady=2)
        self._lbl(r, "Arabic name").pack(side="left")
        self._entry(r, self.name_ar_v, 28, justify="right").pack(side="left", padx=4, ipady=2)
        d = tk.Frame(a, bg=C["card_bg"]); d.pack(fill="x", pady=(8, 0))
        self.deal = tk.StringVar(value="pct")
        self.deal_btns = {}
        for key, txt, _t, _d in DEALS:
            b = tk.Button(d, text=txt, font=("Segoe UI", 10, "bold"), relief="flat", padx=14,
                          pady=6, cursor="hand2", command=lambda k=key: self._set_deal(k))
            b.pack(side="left", padx=(0, 6))
            self.deal_btns[key] = b
        self.deal_opts = tk.Frame(a, bg=C["card_bg"]); self.deal_opts.pack(fill="x", pady=(8, 0))
        self.val_v = tk.StringVar(value="20")
        self.buy_v = tk.StringVar(value="1"); self.get_v = tk.StringVar(value="1")
        self.getat_v = tk.StringVar(value="FREE")
        self.minq_v = tk.StringVar(value="")
        for v in (self.val_v, self.buy_v, self.get_v, self.getat_v, self.minq_v,
                  self.name_v):
            v.trace_add("write", lambda *x: self._refresh_items())

        # 2. when
        w = self._card(self, "2.  WHEN")
        r1 = tk.Frame(w, bg=C["card_bg"]); r1.pack(fill="x")
        today = date.today()
        self.sd_v = tk.StringVar(value=today.isoformat()); self.st_v = tk.StringVar(value="00:00")
        self.ed_v = tk.StringVar(value=(today + timedelta(days=6)).isoformat())
        self.et_v = tk.StringVar(value="23:59")
        for lbl, dv, tv in (("Start", self.sd_v, self.st_v), ("End", self.ed_v, self.et_v)):
            self._lbl(r1, lbl).pack(side="left")
            de = self._entry(r1, dv, 11); de.pack(side="left", padx=(4, 2), ipady=2)
            try:
                from ui.datepicker import attach_datepicker
                attach_datepicker(de, dv, on_pick=lambda *x: self._refresh_items())
            except Exception:
                pass
            self._entry(r1, tv, 6, justify="center").pack(side="left", padx=(0, 14), ipady=2)
        for txt, fn in (("Today", lambda: self._span(0)), ("3 days", lambda: self._span(2)),
                        ("1 week", lambda: self._span(6)), ("Weekend", self._weekend),
                        ("This month", self._month), ("No end", self._no_end)):
            tk.Button(r1, text=txt, font=("Segoe UI", 8), bg="#EEF2FF", fg=C["primary"],
                      relief="flat", padx=8, pady=2, cursor="hand2",
                      command=fn).pack(side="left", padx=(0, 4))
        r2 = tk.Frame(w, bg=C["card_bg"]); r2.pack(fill="x", pady=(6, 0))
        self._lbl(r2, "Days").pack(side="left")
        self.day_v = {}
        for nm, idx in WEEK:
            v = tk.BooleanVar(value=True); self.day_v[idx] = v
            tk.Checkbutton(r2, text=nm, variable=v, bg=C["card_bg"], font=("Segoe UI", 9),
                           command=self._refresh_items).pack(side="left")
        self._lbl(r2, "   Hours  from").pack(side="left")
        self.tf_v = tk.StringVar(); self.tt_v = tk.StringVar()
        self._entry(r2, self.tf_v, 6, justify="center").pack(side="left", padx=4, ipady=2)
        self._lbl(r2, "to").pack(side="left")
        self._entry(r2, self.tt_v, 6, justify="center").pack(side="left", padx=4, ipady=2)
        self._lbl(r2, "(empty = all day)").pack(side="left")
        r3 = tk.Frame(w, bg=C["card_bg"]); r3.pack(fill="x", pady=(6, 0))
        self.pos_v = tk.BooleanVar(value=True); self.sales_v = tk.BooleanVar(value=True)
        self.active_v = tk.BooleanVar(value=True)
        self._lbl(r3, "Use in").pack(side="left")
        for txt, v in (("POS", self.pos_v), ("Sales invoice", self.sales_v),
                       ("Offer is ON", self.active_v)):
            tk.Checkbutton(r3, text=txt, variable=v, bg=C["card_bg"],
                           font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 10))

        # 3. products
        p = tk.Frame(self, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        p.pack(fill="both", expand=True, padx=14, pady=8)
        hdr = tk.Frame(p, bg=C["card_bg"]); hdr.pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(hdr, text="3.  PRODUCTS", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left")
        self._lbl(hdr, "   Type a name / code or scan a barcode, Enter = add").pack(side="left")
        sr = tk.Frame(p, bg=C["card_bg"]); sr.pack(fill="x", padx=12)
        self.find_v = tk.StringVar()
        self.find_e = self._entry(sr, self.find_v, 36)
        self.find_e.pack(side="left", ipady=3)
        self.find_e.bind("<KeyRelease>", self._find_key)
        self.find_e.bind("<Return>", self._find_enter)
        self.find_e.bind("<Down>", lambda e: self._drop_focus())
        tk.Button(sr, text="＋ Add", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=10, pady=2, cursor="hand2",
                  command=lambda: self._find_enter(None)).pack(side="left", padx=6)
        self.cat_v = tk.StringVar(value="＋ Whole category…")
        cc = ttk.Combobox(sr, textvariable=self.cat_v, state="readonly", width=24,
                          values=[c.get("category_name_en") or "?" for c in self.cat.categories])
        cc.pack(side="left", padx=6)
        cc.bind("<<ComboboxSelected>>", lambda e: self._add_category())
        tk.Button(sr, text="✕ Remove", font=("Segoe UI", 9), bg=C["card_bg"], relief="flat",
                  padx=8, pady=2, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._remove_sel).pack(side="right")
        self.drop = tk.Listbox(p, height=6, font=("Segoe UI", 10), activestyle="dotbox")
        self.drop.bind("<Return>", lambda e: self._drop_pick())
        self.drop.bind("<Double-1>", lambda e: self._drop_pick())
        self.drop.bind("<Escape>", lambda e: (self.drop.place_forget(), self.find_e.focus_set()))
        self._matches = []

        tw = tk.Frame(p, bg=C["card_bg"]); tw.pack(fill="both", expand=True, padx=12, pady=(6, 8))
        cols = [("code", "Code", 90, "w"), ("name", "Product", 260, "w"),
                ("unit", "Unit", 90, "center"), ("old", "Normal price", 112, "e"),
                ("new", "Offer price", 100, "e"), ("save", "Customer saves", 170, "e"),
                ("del", "✕", 34, "center")]
        self.tree = ttk.Treeview(tw, columns=[c[0] for c in cols], show="headings", height=8)
        for k, h, wd, an in cols:
            self.tree.heading(k, text=h, anchor="e" if an == "e" else ("w" if an == "w" else "center"))
            self.tree.column(k, width=wd, anchor=an, stretch=k == "name")
        vs = ttk.Scrollbar(tw, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("bad", foreground="#DC2626")
        self.tree.bind("<Button-1>", self._tree_click, add="+")
        self.tree.bind("<Double-1>", self._tree_double)
        self.tree.bind("<Delete>", lambda e: self._remove_sel())
        self.count_v = tk.StringVar()
        tk.Label(p, textvariable=self.count_v, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(0, 6))

    # ── deal ─────────────────────────────────────────────────
    def _set_deal(self, key, keep_values=False):
        C = self.C
        self.deal.set(key)
        for k, b in self.deal_btns.items():
            on = k == key
            b.configure(bg=C["primary"] if on else "#EEF1F6", fg="white" if on else C["text_primary"])
        for w in self.deal_opts.winfo_children():
            w.destroy()
        f = self.deal_opts
        _k, _txt, _t, dflt = next(d for d in DEALS if d[0] == key)
        if not keep_values:
            if "offer_value" in dflt:
                self.val_v.set(O._num(dflt["offer_value"]))
        if key == "pct":
            self._lbl(f, "Discount").pack(side="left")
            self._entry(f, self.val_v, 6, justify="center").pack(side="left", padx=4, ipady=2)
            self._lbl(f, "%   quick:").pack(side="left")
            for n in (10, 15, 20, 25, 30, 40, 60, 70):
                tk.Button(f, text="%d%%" % n, font=("Segoe UI", 8), bg="#FEE2E2", fg="#B91C1C",
                          relief="flat", padx=6, cursor="hand2",
                          command=lambda n=n: self.val_v.set(str(n))).pack(side="left", padx=2)
        elif key == "half":
            self.val_v.set("50")
            self._lbl(f, "Every product in the list at HALF its normal price (50 % off).").pack(side="left")
        elif key == "price":
            self._lbl(f, "Type the OFFER PRICE of each product in the list below "
                         "(double-click the Offer price cell).  Or set all to").pack(side="left")
            self.allpct = tk.StringVar(value="10")
            self._entry(f, self.allpct, 4, justify="center").pack(side="left", padx=4)
            self._lbl(f, "% less").pack(side="left")
            tk.Button(f, text="Fill", font=("Segoe UI", 8, "bold"), bg="#DBEAFE", fg="#1D4ED8",
                      relief="flat", padx=8, cursor="hand2",
                      command=self._fill_prices).pack(side="left", padx=4)
        elif key == "amt":
            self._lbl(f, "Take").pack(side="left")
            self._entry(f, self.val_v, 7, justify="center").pack(side="left", padx=4, ipady=2)
            self._lbl(f, "SAR off each item").pack(side="left")
        elif key == "bxgy":
            self._lbl(f, "Buy").pack(side="left")
            self._entry(f, self.buy_v, 4, justify="center").pack(side="left", padx=4, ipady=2)
            self._lbl(f, "get").pack(side="left")
            self._entry(f, self.get_v, 4, justify="center").pack(side="left", padx=4, ipady=2)
            ttk.Combobox(f, textvariable=self.getat_v, state="readonly", width=10,
                         values=[g[0] for g in GET_AT]).pack(side="left", padx=4)
            self._lbl(f, "   quick:").pack(side="left")
            for bq, gq in ((1, 1), (1, 2), (2, 1), (3, 1)):
                tk.Button(f, text="%d+%d" % (bq, gq), font=("Segoe UI", 8, "bold"), bg="#DCFCE7",
                          fg="#166534", relief="flat", padx=6, cursor="hand2",
                          command=lambda b=bq, g=gq: (self.buy_v.set(str(b)),
                                                      self.get_v.set(str(g)),
                                                      self.getat_v.set("FREE"))).pack(side="left", padx=2)
        if key in ("pct", "half", "amt", "price"):
            self._lbl(f, "    only from qty").pack(side="left")
            self._entry(f, self.minq_v, 4, justify="center").pack(side="left", padx=4, ipady=2)
        self._refresh_items()

    # ── loading ──────────────────────────────────────────────
    def _load(self, preset, product_ids):
        o = self.offer
        if o.get("offer_type"):
            t = o["offer_type"]
            key = {"percent": "half" if abs(_f(o.get("offer_value")) - 50) < 1e-9 else "pct",
                   "price": "price", "amount": "amt", "buy_get": "bxgy"}.get(t, "pct")
            self.name_v.set(o.get("offer_name") or "")
            self.name_ar_v.set(o.get("offer_name_ar") or "")
            self.val_v.set(O._num(o.get("offer_value")))
            self.buy_v.set(O._num(o.get("buy_qty") or 1)); self.get_v.set(O._num(o.get("get_qty") or 1))
            pct = _f(o.get("get_pct"), 100)
            self.getat_v.set(next((g[0] for g in GET_AT if abs(g[1] - pct) < 1e-9), "FREE"))
            self.minq_v.set(O._num(o.get("min_qty")) if _f(o.get("min_qty")) else "")
            st, en = O.to_dt(o.get("start_at")), O.to_dt(o.get("end_at"))
            self.sd_v.set(st.date().isoformat() if st else "")
            self.st_v.set(st.strftime("%H:%M") if st else "00:00")
            self.ed_v.set(en.date().isoformat() if en else "")
            self.et_v.set(en.strftime("%H:%M") if en else "23:59")
            mask = str(o.get("days_mask") or "1111111").ljust(7, "1")
            for i, v in self.day_v.items():
                v.set(mask[i] == "1")
            self.tf_v.set(o.get("time_from") or ""); self.tt_v.set(o.get("time_to") or "")
            self.pos_v.set(bool(o.get("for_pos", 1))); self.sales_v.set(bool(o.get("for_sales", 1)))
            self.active_v.set(bool(o.get("is_active", 1)))
            for it in o.get("items", []):
                if it.get("product_id") in self.cat.by_id:
                    self.items.append({"product_id": it["product_id"],
                                       "unit_name": it.get("unit_name"),
                                       "offer_price": it.get("offer_price")})
            self._set_deal(key, keep_values=True)
        else:
            key, vals = preset or ("pct", {})
            self._set_deal(key)
            if "offer_value" in vals:
                self.val_v.set(O._num(vals["offer_value"]))
            if "buy_qty" in vals:
                self.buy_v.set(O._num(vals["buy_qty"])); self.get_v.set(O._num(vals["get_qty"]))
            for pid in product_ids or []:
                self._add_product(pid, quiet=True)
            self._last_auto = self._auto_name()
            self.name_v.set(self._last_auto)
        self._refresh_items()

    def _auto_name(self):
        o = self._collect(partial=True)
        t, v = o["offer_type"], _f(o["offer_value"])
        if t == "percent":
            return "Half Price" if abs(v - 50) < 1e-9 else "%s%% Off" % O._num(v)
        if t == "price":
            return "Special Prices"
        if t == "amount":
            return "SAR %s Off" % O._num(v)
        tail = next((g[0] for g in GET_AT if abs(g[1] - _f(o["get_pct"], 100)) < 1e-9), "Free")
        return "Buy %s Get %s %s" % (O._num(o["buy_qty"]), O._num(o["get_qty"]),
                                     "Free" if tail == "FREE" else tail)

    # ── dates ────────────────────────────────────────────────
    def _span(self, days):
        t = date.today()
        self.sd_v.set(t.isoformat()); self.st_v.set("00:00")
        self.ed_v.set((t + timedelta(days=days)).isoformat()); self.et_v.set("23:59")
        self._refresh_items()

    def _weekend(self):
        """The coming Friday + Saturday (Saudi weekend)."""
        t = date.today()
        fri = t + timedelta(days=(4 - t.weekday()) % 7)
        if t.weekday() == 5:              # it is Saturday: today only
            fri = t - timedelta(days=1)
        self.sd_v.set(max(fri, t).isoformat()); self.st_v.set("00:00")
        self.ed_v.set((fri + timedelta(days=1)).isoformat()); self.et_v.set("23:59")
        self._refresh_items()

    def _month(self):
        t = date.today()
        nxt = (t.replace(day=28) + timedelta(days=4)).replace(day=1)
        self.sd_v.set(t.isoformat()); self.st_v.set("00:00")
        self.ed_v.set((nxt - timedelta(days=1)).isoformat()); self.et_v.set("23:59")
        self._refresh_items()

    def _no_end(self):
        self.ed_v.set(""); self.et_v.set("")
        self._refresh_items()

    # ── products ─────────────────────────────────────────────
    def _add_product(self, pid, unit=None, quiet=False):
        if pid not in self.cat.by_id:
            return False
        if any(it["product_id"] == pid for it in self.items):
            if not quiet:
                self.count_v.set("Already in the list: " + self.cat.by_id[pid]["product_name_en"])
            return False
        un = None
        if self.deal.get() == "price":
            u = unit or self.cat.default_unit(pid)
            un = u["unit_name_en"] if u else None
        self.items.append({"product_id": pid, "unit_name": un, "offer_price": None})
        self._refresh_items(select=pid)
        return True

    def _find_key(self, e):
        if e.keysym in ("Return", "Down", "Up", "Escape"):
            if e.keysym == "Escape":
                self.drop.place_forget()
            return
        self._matches = self.cat.search(self.find_v.get())
        self.drop.delete(0, "end")
        if not self._matches:
            self.drop.place_forget()
            return
        for pr in self._matches:
            self.drop.insert("end", "  %s   %s   %s" % (pr.get("product_code") or "",
                                                      pr.get("product_name_en") or "",
                                                      _money(self.cat.price(pr["product_id"]))))
        x = self.find_e.winfo_x() + self.find_e.master.winfo_x()
        y = self.find_e.master.winfo_y() + self.find_e.winfo_height() + 2
        self.drop.place(x=x, y=y, width=460)
        self.drop.lift()

    def _drop_focus(self):
        if self._matches:
            self.drop.focus_set(); self.drop.selection_clear(0, "end")
            self.drop.selection_set(0); self.drop.activate(0)

    def _drop_pick(self):
        sel = self.drop.curselection()
        if sel and sel[0] < len(self._matches):
            self._add_product(self._matches[sel[0]]["product_id"])
        self.drop.place_forget()
        self.find_v.set("")
        self.find_e.focus_set()

    def _find_enter(self, e):
        txt = self.find_v.get().strip()
        if not txt:
            return
        prod, unit = self.cat.find_code(txt)            # a scanned barcode
        if prod:
            self._add_product(prod["product_id"], unit)
        elif self._matches or self.cat.search(txt):
            m = self._matches or self.cat.search(txt)
            self._add_product(m[0]["product_id"])
        else:
            self.count_v.set("No product found for '%s'" % txt)
            return
        self.drop.place_forget()
        self.find_v.set("")
        self.find_e.focus_set()

    def _add_category(self):
        name = self.cat_v.get()
        cat = next((c for c in self.cat.categories if c.get("category_name_en") == name), None)
        if not cat:
            return
        n = 0
        for pr in self.cat.products:
            if pr.get("category_id") == cat.get("category_id") and self._add_product(pr["product_id"], quiet=True):
                n += 1
        self.count_v.set("+ %d products from %s" % (n, name))
        self.cat_v.set("＋ Whole category…")

    def _remove_sel(self):
        sel = self.tree.selection()
        if not sel:
            return
        pids = {int(s) for s in sel}
        self.items = [it for it in self.items if it["product_id"] not in pids]
        self._refresh_items()

    def _tree_click(self, e):
        if self.tree.identify_region(e.x, e.y) != "cell":
            return
        col = self.tree.identify_column(e.x)
        row = self.tree.identify_row(e.y)
        if row and col == "#7":
            self.items = [it for it in self.items if it["product_id"] != int(row)]
            self._refresh_items()
            return "break"

    def _tree_double(self, e):
        row = self.tree.identify_row(e.y)
        col = self.tree.identify_column(e.x)
        if not row:
            return
        pid = int(row)
        it = next((x for x in self.items if x["product_id"] == pid), None)
        if not it:
            return
        if col == "#5" and self.deal.get() == "price":
            self._edit_cell(row, "#5", it)
        elif col == "#3" and self.deal.get() == "price":
            us = self.cat.units.get(pid) or []
            if len(us) > 1:
                m = tk.Menu(self, tearoff=0)
                for u in us:
                    m.add_command(label="%s  (%s)" % (u["unit_name_en"], _money(u.get("selling_price"))),
                                  command=lambda u=u: (it.update(unit_name=u["unit_name_en"],
                                                                 offer_price=None),
                                                       self._refresh_items(select=pid)))
                m.tk_popup(e.x_root, e.y_root)

    def _edit_cell(self, row, col, it):
        bbox = self.tree.bbox(row, col)
        if not bbox:
            return
        x, y, w, h = bbox
        v = tk.StringVar(value=O._num(it["offer_price"]) if it.get("offer_price") else "")
        ent = tk.Entry(self.tree, textvariable=v, font=("Segoe UI", 10), justify="right",
                       relief="solid", bd=1)
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set(); ent.select_range(0, "end")

        def done(_e=None, move=0):
            val = _f(v.get(), None)
            it["offer_price"] = val if val and val > 0 else None
            ent.destroy()
            self._refresh_items(select=it["product_id"])
            if move:
                ids = list(self.tree.get_children())
                i = ids.index(row) + move if row in ids else -1
                if 0 <= i < len(ids):
                    nxt = next((x for x in self.items if x["product_id"] == int(ids[i])), None)
                    if nxt:
                        self.tree.selection_set(ids[i]); self.tree.see(ids[i])
                        self.after(10, lambda: self._edit_cell(ids[i], "#5", nxt))
            return "break"
        ent.bind("<Return>", lambda e: done(e, 1))
        ent.bind("<Tab>", lambda e: done(e, 1))
        ent.bind("<FocusOut>", done)
        ent.bind("<Escape>", lambda e: (ent.destroy(), "break")[1])

    def _fill_prices(self):
        pct = _f(getattr(self, "allpct", tk.StringVar()).get(), 0)
        if pct <= 0 or pct >= 100:
            return
        for it in self.items:
            old = self.cat.price(it["product_id"], it.get("unit_name"))
            it["offer_price"] = round(old * (1 - pct / 100.0), 2) if old else None
        self._refresh_items()

    def _refresh_items(self, select=None):
        if not hasattr(self, "tree"):
            return
        o = self._collect(partial=True)
        t = o["offer_type"]
        self.tree.delete(*self.tree.get_children())
        for it in self.items:
            pid = it["product_id"]
            pr = self.cat.by_id.get(pid) or {}
            if t == "price" and not it.get("unit_name"):
                u = self.cat.default_unit(pid)
                it["unit_name"] = u["unit_name_en"] if u else None
            if t != "price":
                it["unit_name"] = None
            old = self.cat.price(pid, it.get("unit_name"))
            new_txt, save_txt, bad = "", "", False
            if t == "price":
                np_ = _f(it.get("offer_price"))
                new_txt = _money(np_) if np_ else "← type price"
                if np_ and old:
                    save_txt = "%s  (%d%%)" % (_money(old - np_), round((old - np_) * 100 / old)) \
                        if np_ < old else "not cheaper!"
                    bad = np_ >= old
                else:
                    bad = True
            elif t == "percent":
                v = _f(o["offer_value"])
                new_txt = _money(old * (1 - v / 100.0)) if old else ""
                save_txt = "%s  (%s%%)" % (_money(old * v / 100.0), O._num(v)) if old else ""
            elif t == "amount":
                v = _f(o["offer_value"])
                new_txt = _money(max(0, old - v)) if old else ""
                save_txt = _money(min(v, old))
            else:
                save_txt = O.label(o)
            self.tree.insert("", "end", iid=str(pid), values=(
                pr.get("product_code") or "", pr.get("product_name_en") or "",
                it.get("unit_name") or "All units", _money(old), new_txt, save_txt, "✕"),
                tags=("bad",) if bad else ())
        if select is not None and self.tree.exists(str(select)):
            self.tree.selection_set(str(select)); self.tree.see(str(select))
        n = len(self.items)
        self.count_v.set("%d product%s in this offer" % (n, "" if n == 1 else "s"))
        if not self.offer.get("offer_id"):      # the name follows the deal until typed
            auto = self._auto_name()
            cur = self.name_v.get()
            if cur in ("", getattr(self, "_last_auto", "")) and cur != auto:
                self._last_auto = auto
                self.name_v.set(auto)
        try:
            self.preview.set("Customer sees on the bill:  🏷 %s   ·   %s" % (O.label(o, (self.items or [{}])[0]),
                                                                          O.when_text(o)))
        except Exception:
            pass

    # ── collect + save ───────────────────────────────────────
    def _collect(self, partial=False):
        key = self.deal.get()
        t = next(d[2] for d in DEALS if d[0] == key)
        val = 50.0 if key == "half" else _f(self.val_v.get())
        pct = next((g[1] for g in GET_AT if g[0] == self.getat_v.get()), 100)

        def dt(dv, tv, end=False):
            d = (dv.get() or "").strip()
            if not d:
                return None
            tm = (tv.get() or "").strip() or ("23:59" if end else "00:00")
            try:
                return datetime.strptime("%s %s" % (d, tm), "%Y-%m-%d %H:%M")
            except ValueError:
                if partial:
                    return None
                raise ValueError("Date / time '%s %s' — use YYYY-MM-DD and HH:MM." % (d, tm))
        mask = "".join("1" if self.day_v[i].get() else "0" for i in range(7))
        tf, tt = self.tf_v.get().strip(), self.tt_v.get().strip()
        for x in (tf, tt):
            if x and not partial:
                try:
                    datetime.strptime(x, "%H:%M")
                except ValueError:
                    raise ValueError("Hours '%s' — use HH:MM like 16:00." % x)
        return {
            "offer_id": self.offer.get("offer_id"),
            "offer_name": self.name_v.get().strip(),
            "offer_name_ar": self.name_ar_v.get().strip() or None,
            "offer_type": t,
            "offer_value": val if t in ("percent", "amount") else 0,
            "buy_qty": _f(self.buy_v.get()) if t == "buy_get" else 0,
            "get_qty": _f(self.get_v.get()) if t == "buy_get" else 0,
            "get_pct": pct if t == "buy_get" else 100,
            "min_qty": _f(self.minq_v.get()) if t != "buy_get" else 0,
            "start_at": dt(self.sd_v, self.st_v), "end_at": dt(self.ed_v, self.et_v, True),
            "days_mask": mask, "time_from": tf or None, "time_to": tt or None,
            "for_pos": self.pos_v.get(), "for_sales": self.sales_v.get(),
            "is_active": self.active_v.get(), "notes": self.offer.get("notes"),
        }

    def _save(self):
        try:
            o = self._collect()
        except ValueError as e:
            messagebox.showwarning("Offer", str(e), parent=self)
            return
        problems = []
        if not o["offer_name"]:
            o["offer_name"] = self._auto_name()
        if not self.items:
            problems.append("Add at least one product (type a name or scan a barcode).")
        t = o["offer_type"]
        if t == "percent" and not (0 < o["offer_value"] < 100):
            problems.append("Discount % must be between 1 and 99.")
        if t == "amount" and o["offer_value"] <= 0:
            problems.append("Type how many SAR to take off.")
        if t == "buy_get" and (o["buy_qty"] <= 0 or o["get_qty"] <= 0):
            problems.append("Buy and Get must both be 1 or more.")
        if t == "price":
            missing = [self.cat.by_id[i["product_id"]]["product_name_en"] for i in self.items
                       if not _f(i.get("offer_price"))]
            if missing:
                problems.append("Type the offer price for: " + ", ".join(missing[:5])
                                + (" …" if len(missing) > 5 else ""))
        if o["start_at"] and o["end_at"] and o["end_at"] <= o["start_at"]:
            problems.append("The end must be after the start.")
        if "1" not in o["days_mask"]:
            problems.append("Tick at least one day.")
        if not (o["for_pos"] or o["for_sales"]):
            problems.append("Tick POS and / or Sales invoice.")
        if problems:
            messagebox.showwarning("Offer", "\n".join("• " + p for p in problems), parent=self)
            return
        if t == "price":
            dear = [self.cat.by_id[i["product_id"]]["product_name_en"] for i in self.items
                    if _f(i.get("offer_price")) >= self.cat.price(i["product_id"], i.get("unit_name"))]
            if dear and not messagebox.askyesno(
                    "Offer", "The offer price is NOT cheaper than the normal price for:\n"
                    + "\n".join(dear[:8]) + "\n\nThese items get no discount. Save anyway?",
                    parent=self):
                return
        if o["end_at"] and o["end_at"] < datetime.now() and not messagebox.askyesno(
                "Offer", "The end date is already over — the offer will not run.\nSave anyway?",
                parent=self):
            return
        try:
            from modules import permissions as _p
            user = (_p.session_user() or {}).get("username")
        except Exception:
            user = None
        try:
            oid = O.save(o, self.items, user=user)
        except Exception as e:
            messagebox.showerror("Offer", "Could not save the offer:\n%s" % str(e)[:300], parent=self)
            return
        try:
            from modules import audit
            audit.log("save", "offer", oid, "%s · %s · %d items" % (o["offer_name"], O.label(o),
                                                                      len(self.items)))
        except Exception:
            pass
        self.offer["offer_id"] = oid
        if self.on_saved:
            try:
                self.on_saved(oid)
            except Exception:
                pass
        self.destroy()

    def _poster(self):
        try:
            o = self._collect(partial=True)
        except Exception:
            return
        if not o["offer_name"]:
            o["offer_name"] = self._auto_name()
        items = []
        for it in self.items:
            pr = self.cat.by_id.get(it["product_id"]) or {}
            items.append(dict(it, product_name_en=pr.get("product_name_en"),
                              product_name_ar=pr.get("product_name_ar"),
                              normal_price=self.cat.price(it["product_id"], it.get("unit_name"))))
        PosterPromptDialog(self, o, items, catalog=self.cat)


# ============================================================
# 🎨 Poster prompt
# ============================================================
class PosterPromptDialog(tk.Toplevel):
    def __init__(self, parent, offer, items, catalog=None):
        super().__init__(parent)
        from modules import offer_poster as P
        self.P = P
        C = self.C = cfg.theme()
        self.offer = offer
        cat = catalog or _Catalog()
        self.items = []
        for it in items:
            pid = it.get("product_id")
            pr = cat.by_id.get(pid) or {}
            self.items.append(dict(it,
                                   product_name_en=it.get("product_name_en") or pr.get("product_name_en"),
                                   product_name_ar=it.get("product_name_ar") or pr.get("product_name_ar"),
                                   normal_price=it.get("normal_price") if it.get("normal_price") is not None
                                   else cat.price(pid, it.get("unit_name"))))
        try:
            self.company = dict(db.fetchone("SELECT * FROM company WHERE company_id=1") or {})
        except Exception:
            self.company = {}
        self.title("🎨 Poster prompt — " + str(offer.get("offer_name") or "offer"))
        self.configure(bg=C["content_bg"])
        self.geometry("860x640")
        self._no_close_confirm = True
        try:
            self.transient(parent.winfo_toplevel())
        except Exception:
            pass
        top = tk.Frame(self, bg=C["content_bg"]); top.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(top, text="🎨  Make the offer poster with ChatGPT or Gemini",
                 font=("Segoe UI", 13, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(anchor="w")
        tk.Label(top, text="1. Choose size, language and style   2. 📋 Copy   3. Open ChatGPT or "
                           "Gemini and paste (Ctrl+V) — it draws the poster.",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w")
        opts = tk.Frame(self, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        opts.pack(fill="x", padx=14, pady=6)
        o = tk.Frame(opts, bg=C["card_bg"]); o.pack(fill="x", padx=10, pady=8)
        self.size_v = tk.StringVar(value=list(P.SIZES)[0])
        self.lang_v = tk.StringVar(value=P.LANGS[0])
        self.style_v = tk.StringVar(value=list(P.STYLES)[0])
        self.prices_v = tk.BooleanVar(value=True)
        for lbl, var, vals, w in (("Size", self.size_v, list(P.SIZES), 28),
                                  ("Language", self.lang_v, list(P.LANGS), 16),
                                  ("Style", self.style_v, list(P.STYLES), 22)):
            tk.Label(o, text=lbl, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(o, textvariable=var, values=vals, state="readonly", width=w)
            cb.pack(side="left", padx=(0, 10))
            cb.bind("<<ComboboxSelected>>", lambda e: self._make())
        tk.Checkbutton(o, text="Show prices", variable=self.prices_v, bg=C["card_bg"],
                       command=self._make).pack(side="left")
        n = tk.Frame(opts, bg=C["card_bg"]); n.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(n, text="Extra wishes (optional)", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.notes_v = tk.StringVar()
        ne = tk.Entry(n, textvariable=self.notes_v, font=("Segoe UI", 10), relief="solid", bd=1)
        ne.pack(side="left", fill="x", expand=True, padx=6, ipady=2)
        ne.bind("<KeyRelease>", lambda e: self._make())

        btns = tk.Frame(self, bg=C["content_bg"]); btns.pack(side="bottom", fill="x", padx=14, pady=10)
        self.msg = tk.StringVar(value="Tip: Ctrl+V pastes the prompt in ChatGPT / Gemini.")
        tk.Label(self, textvariable=self.msg, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg="#047857", anchor="w").pack(side="bottom", fill="x", padx=16)
        tk.Button(btns, text="Close", font=("Segoe UI", 10), relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self.destroy).pack(side="right")
        tk.Button(btns, text="✨  Open Gemini", font=("Segoe UI", 10, "bold"), bg="#1A73E8",
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._gemini).pack(side="right", padx=6)
        tk.Button(btns, text="💬  Open ChatGPT", font=("Segoe UI", 10, "bold"), bg="#10A37F",
                  fg="white", relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._chatgpt).pack(side="right")
        tk.Button(btns, text="📋  Copy prompt", font=("Segoe UI", 10, "bold"), bg="#7C3AED",
                  fg="white", relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._copy).pack(side="right", padx=6)

        tw = tk.Frame(self, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        tw.pack(fill="both", expand=True, padx=14, pady=(0, 2))
        self.text = tk.Text(tw, font=("Consolas", 10), wrap="word", relief="flat",
                            padx=10, pady=8)
        sb = ttk.Scrollbar(tw, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.text.pack(fill="both", expand=True)
        self._make()

    def prompt(self):
        return self.text.get("1.0", "end").strip()

    def _make(self):
        txt = self.P.build_prompt(self.offer, self.items, self.company, self.size_v.get(),
                                  self.lang_v.get(), self.style_v.get(), self.prices_v.get(),
                                  self.notes_v.get())
        self.text.delete("1.0", "end")
        self.text.insert("1.0", txt)

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.prompt())
        self.update()
        self.msg.set("✅ Copied — paste it in ChatGPT / Gemini with Ctrl+V")
        return True

    def _chatgpt(self):
        self._copy()
        try:
            webbrowser.open(self.P.chatgpt_url(self.prompt()))
            self.msg.set("✅ ChatGPT opened with the prompt (also copied — Ctrl+V if empty)")
        except Exception:
            pass

    def _gemini(self):
        self._copy()
        try:
            webbrowser.open(self.P.GEMINI_URL)
            self.msg.set("✅ Copied — in Gemini click the box and press Ctrl+V, then Enter")
        except Exception:
            pass


def open_offer_for_products(parent, product_ids):
    """Products screen ▸ 🏷 Make offer: a new offer with these products."""
    if not O.tables_ready():
        messagebox.showwarning("Offers", "Offer tables are missing — open Updates ▸ Apply All "
                               "Updates once.", parent=parent)
        return None
    return OfferEditor(parent, preset=("pct", {"offer_value": 20}), product_ids=product_ids)
