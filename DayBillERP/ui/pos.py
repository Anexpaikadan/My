# ============================================================
# DayBill ERP - Point of Sale (POS) Window  [LANDVIZ-style]
# Barcode-first touchscreen cashier screen:
#   - Big barcode box (scan/type -> instant line)
#   - Cart grid: Code / Name / Qty / Unit / Rate / Amount
#   - +/- qty, on-screen number pad (Qty/Rate/Clear/Enter)
#   - Hold [F6] / Retrieve [F7] / Price Check [F8]
#   - Save / Print / Delete Bill
#   - Totals: Qty / Gross / Discount / Tax / Grand Total
#   - Multi-unit aware (Space cycles unit) + multi-barcode lookup
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db

try:
    from modules.smart_search import filter_products
except Exception:
    filter_products = None



def _price_incl():
    """Single source of truth shared with the Sales Invoice window:
    Settings > Tax > Sales Price Mode (inclusive / exclusive)."""
    try:
        return str(cfg.get("sales_price_tax_mode", "inclusive")).lower() == "inclusive"
    except Exception:
        return True


def _set_price_incl(on):
    try:
        cfg.set("sales_price_tax_mode", "inclusive" if on else "exclusive")
        cfg.set("pos_price_incl_vat", bool(on))   # legacy key kept in sync
        cfg.save_settings()
    except Exception:
        pass

class POSWindow:
    def __init__(self, parent=None):
        C = cfg.theme()
        self.cart = []
        self.products = []
        self._company = {}
        self._walkin_id = None
        self._units = {}
        self._held = []
        self._sel_idx = None
        self._pad_target = "qty"
        self._pad_buffer = ""

        self.win = tk.Toplevel(parent) if parent else tk.Tk()
        self.win._no_zoom = True           # POS keeps its own size (Settings ▸ POS ▸ Screen size)
        self.win.title("DayBill POS")
        try:                                   # which till this PC is
            from modules import branches as _br
            _bn, _cn = _br.labels()
            if _cn:
                self.win.title(f"DayBill POS — {_bn} · {_cn}")
        except Exception:
            pass
        self.win.configure(bg="#0F2027")
        # Settings ▸ POS: fullscreen on open (default on)
        # not full screen: a window that always fits this screen
        _sw, _sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        _geo = "%dx%d+%d+%d" % (min(1280, int(_sw * 0.9)), min(760, int(_sh * 0.85)),
                                max(0, (_sw - min(1280, int(_sw * 0.9))) // 2), 10)
        if cfg.flag("pos_fullscreen", True):
            try:
                self.win.state("zoomed")
            except Exception:
                self.win.geometry(_geo)
        else:
            self.win.geometry(_geo)

        self._load_data()
        self._build(C)
        # window ✕ asks first (own message — not the general one)
        self.win._no_close_confirm = True
        if isinstance(self.win, tk.Toplevel):
            self.win.protocol("WM_DELETE_WINDOW", self._close_pos)
        self._bind_keys()
        self._offline_job = None
        try:                                   # v6.0: bills kept while the server was gone
            from modules import offline_pos as _off
            if _off.enabled():
                _off.sync_seq()
            if _off.count():
                self._offline_schedule(3000)
        except Exception:
            pass
        self._render_cart()
        # show the default customer (Cash Account) in the header
        self._set_customer(getattr(self, "_customer", None), quiet=True)
        # Settings ▸ POS: auto-focus barcode on open (default on)
        if cfg.flag("pos_auto_focus_barcode", True):
            self.win.after(100, lambda: self.barcode_entry.focus_set())

        # Global UI polish (hover states, focus rings, striped tables)
        try:
            from ui.ui_polish import beautify, enable_auto_polish
            enable_auto_polish(self.win)
            from ui.ui_polish import enable_windows_behaviour
            enable_windows_behaviour(self.win)
            self.win.after(120, lambda w=self.win: beautify(w))
        except Exception:
            pass

    # -- Data --------------------------------------------------
    def _load_data(self):
        try:
            self._company = db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
            try:
                self.products = db.fetchall(
                    "SELECT p.product_id, p.product_code, p.product_name_en, "
                    "p.product_name_ar, p.unit_price, p.barcode, "
                    "ISNULL(p.alias_name,'') AS alias_name, "
                    "ISNULL(p.stock_quantity,0) AS stock_quantity, "
                    "ISNULL(p.reorder_level,0) AS reorder_level, "
                    "ISNULL(pc.category_name_en,'Other') AS category_name, "
                    "ISNULL(p.purchase_price,0) AS purchase_price, "
                    "ISNULL(vc.vat_rate,15) AS vat_rate, "
                    "ISNULL(vc.category_code,'S') AS vat_code, p.vat_category_id "
                    "FROM products p "
                    "LEFT JOIN vat_categories vc ON p.vat_category_id=vc.vat_category_id "
                    "LEFT JOIN product_categories pc ON p.category_id=pc.category_id "
                    "WHERE p.is_active=1 AND ISNULL(p.list_in_sales,1)=1 "
                    "ORDER BY p.product_name_en") or []
            except Exception:
                # fallback if some columns/tables differ on this DB
                self.products = db.fetchall(
                    "SELECT p.product_id, p.product_code, p.product_name_en, "
                    "p.product_name_ar, p.unit_price, p.barcode, "
                    "ISNULL(p.alias_name,'') AS alias_name, "
                    "ISNULL(vc.vat_rate,15) AS vat_rate, "
                    "ISNULL(vc.category_code,'S') AS vat_code, p.vat_category_id "
                    "FROM products p "
                    "LEFT JOIN vat_categories vc ON p.vat_category_id=vc.vat_category_id "
                    "WHERE p.is_active=1 AND ISNULL(p.list_in_sales,1)=1 "
                    "ORDER BY p.product_name_en") or []
                for p in self.products:
                    p.setdefault("stock_quantity", 0)
                    p.setdefault("reorder_level", 0)
                    p.setdefault("category_name", "Other")
                    p.setdefault("purchase_price", 0)
            try:
                try:
                    allu = db.fetchall(
                        "SELECT unit_id, product_id, unit_name_en, conversion_factor, "
                        "selling_price, ISNULL(purchase_price,0) AS purchase_price, "
                        "is_default, barcode FROM product_units "
                        "WHERE is_active=1 ORDER BY conversion_factor")
                except Exception:
                    allu = db.fetchall(
                        "SELECT unit_id, product_id, unit_name_en, conversion_factor, "
                        "selling_price, is_default, barcode FROM product_units "
                        "WHERE is_active=1 ORDER BY conversion_factor")
                self._units = {}                 # reload = fresh, never doubled
                for u in (allu or []):
                    self._units.setdefault(u["product_id"], []).append(u)
            except Exception:
                self._units = {}
            walkin = db.fetchone(
                "SELECT customer_id FROM customers WHERE customer_code='WALKIN' OR "
                "customer_name_en LIKE 'Walk%' ORDER BY customer_id")
            self._walkin_id = walkin["customer_id"] if walkin else None
            # customers for the search-by name/phone/VAT box
            try:
                self._customers = db.fetchall(
                    "SELECT customer_id, customer_code, customer_name_en, "
                    "ISNULL(customer_name_ar,'') AS customer_name_ar, "
                    "ISNULL(phone,'') AS phone, "
                    "ISNULL(vat_registration_no,'') AS vat_no "
                    "FROM customers WHERE is_active=1 "
                    "ORDER BY customer_name_en") or []
            except Exception:
                self._customers = []
            # Default customer = the Cash account (falls back to Walk-in)
            cash = next((c for c in self._customers
                         if str(c.get("customer_code", "")).upper() == "CASH"
                         or str(c.get("customer_name_en", "")).strip().lower()
                            .startswith("cash")), None)
            if not cash:
                cash = next((c for c in self._customers
                             if c["customer_id"] == self._walkin_id), None)
            self._default_customer = cash
            self._customer = cash
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    # -- Build UI ----------------------------------------------
    # Look follows the 1366×768 design mockup: navy top bar, customer strip,
    # white cart with column lines, quick-product tiles, a right column with
    # totals / PAID-BALANCE-CHANGE / keypad / Cash + Card / big Save, and a
    # bottom bar with big Hold + Retrieve, Clear, Last bill print.
    NAVY, STRIP, BG, LINE = "#0B1F3A", "#132B4D", "#EEF1F6", "#D5DCE6"
    BLUE, MUTED, INK = "#1D4ED8", "#475569", "#0F172A"
    # (key, heading, width, anchor)
    POS_COLS = [("no", "#", 44, "center"), ("code", "Code", 90, "w"),
                ("name", "Item", 260, "w"), ("name_ar", "الاسم العربي", 180, "e"),
                ("qty", "Qty", 70, "center"), ("unit", "Unit", 80, "center"),
                ("rate", "Rate", 90, "e"), ("vat", "VAT", 80, "e"),
                ("amount", "Amount", 110, "e"), ("del", "✕", 40, "center")]

    # ── POS size: Settings ▸ POS ▸ Screen size (small / medium / large) ──
    SIZES = {"small": 0.72, "medium": 0.85, "large": 1.0}

    def _size_factor(self):
        if cfg.flag("pos_touchscreen", False):      # touch screens keep big buttons
            return 1.0
        return self.SIZES.get(str(cfg.get("pos_ui_size", "medium") or "medium").lower(), 0.85)

    def _shrink(self, top):
        """Make every font, padding and fixed height in `top` smaller by the
        chosen size (run after building; new tiles are shrunk too).
        Fonts also undo the app's Text size (ui/zoom.py): the POS has its
        own size setting, so it looks the same at any Text size."""
        f = self._size_factor()
        try:
            from ui import zoom as _zoom
            ff = f / _zoom.factor()
        except Exception:
            ff = f
        if f >= 0.999 and abs(ff - 1.0) < 0.01:
            return
        stack = [top]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if getattr(w, "_pos_sized", False):
                continue
            w._pos_sized = True
            try:
                parts = w.tk.splitlist(w.cget("font"))
                if len(parts) >= 2 and str(parts[1]).lstrip("-").isdigit():
                    size = int(parts[1])
                    new = max(6, int(round(abs(size) * ff)))
                    w.configure(font=(parts[0], new) + tuple(parts[2:]))
            except Exception:
                pass
            if f >= 0.999:
                continue                           # pixel sizes: only for small / medium
            try:                                   # fixed-height bars
                if w.winfo_class() == "Frame" and int(w.cget("height") or 0) > 0 \
                        and not w.pack_propagate():
                    w.configure(height=int(int(w.cget("height")) * f))
            except Exception:
                pass
            for mgr in ("pack", "grid"):
                try:
                    info = w.pack_info() if mgr == "pack" else w.grid_info()
                except Exception:
                    continue
                if not info:
                    continue
                opts = {}
                for k in ("ipady", "ipadx"):
                    try:
                        v = int(info.get(k, 0))
                        if v > 1:
                            opts[k] = max(1, int(v * f))
                    except Exception:
                        pass
                if opts:
                    try:
                        (w.pack_configure if mgr == "pack" else w.grid_configure)(**opts)
                    except Exception:
                        pass

    def _visible_cols(self):
        """Columns the cashier ticked (▤ Columns). 'Item' is always on;
        the ✕ remove column is on unless turned off."""
        s = str(cfg.get("pos_columns", "") or "").strip()
        keys = [k for k, *_ in self.POS_COLS]
        if s:
            want = [k for k in s.split(",") if k in keys and k != "del"]
        else:
            want = ["no", "code", "name", "qty", "unit", "rate", "vat", "amount"]
            if not cfg.flag("pos_show_vat_column", True):
                want.remove("vat")
        if "name" not in want:
            want.append("name")
        if cfg.flag("pos_show_remove_col", True):
            want.append("del")
        return [k for k in keys if k in want]

    def _apply_columns(self):
        self.tree["displaycolumns"] = self._visible_cols()
        self._fit_columns()

    def _fit_columns(self, event=None):
        """Item (and Arabic name) take the width the other columns leave."""
        try:
            vis = self._visible_cols()
            W = self.tree.winfo_width()
            if W < 200:
                return
            fixed = sum(w for k, _h, w, _a in self.POS_COLS
                        if k in vis and k not in ("name", "name_ar"))
            avail = max(W - fixed - 4, 120)
            if "name_ar" in vis:
                nm = max(110, int(avail * 0.58)); ar = max(110, avail - nm)
                self.tree.column("name", width=nm); self.tree.column("name_ar", width=ar)
            else:
                self.tree.column("name", width=avail)
            self.tree._excel_grid.schedule()
        except Exception:
            pass

    def _open_columns(self):
        """Small popup: tick the cart columns you want to see."""
        C = self
        d = tk.Toplevel(self.win); d.title("Columns"); d.configure(bg="white")
        d.transient(self.win); d.resizable(False, False)
        tk.Label(d, text="Cart columns", font=("Segoe UI", 12, "bold"), bg=self.NAVY,
                 fg="white", anchor="w", padx=14, pady=8).pack(fill="x")
        tk.Label(d, text="Tick the columns you want in the bill grid",
                 font=("Segoe UI", 9), bg="white", fg=self.MUTED, anchor="w",
                 padx=14).pack(fill="x", pady=(8, 2))
        have = set(self._visible_cols())
        vars_ = {}

        def changed(*_):
            keys = [k for k, *_r in self.POS_COLS
                    if (vars_[k].get() or k == "name") and k != "del"]
            cfg.set("pos_columns", ",".join(keys))
            cfg.set("pos_show_vat_column", "vat" in keys)
            cfg.set("pos_show_remove_col", bool(vars_["del"].get()))
            try:
                cfg.save_settings()
            except Exception:
                pass
            self._apply_columns()
        for k, head, _w, _a in self.POS_COLS:
            vars_[k] = tk.BooleanVar(value=k in have)
            cb = tk.Checkbutton(d, text=("Item (always on)" if k == "name" else
                                         ("Arabic name" if k == "name_ar" else
                                          ("Line no. (#)" if k == "no" else
                                           ("✕ Remove button" if k == "del" else head)))),
                                variable=vars_[k], command=changed, bg="white",
                                font=("Segoe UI", 12), anchor="w", activebackground="white",
                                state="disabled" if k == "name" else "normal",
                                cursor="hand2")
            cb.pack(fill="x", padx=18, pady=2)
        tk.Button(d, text="Done", font=("Segoe UI", 11, "bold"), bg=self.BLUE, fg="white",
                  relief="flat", cursor="hand2", command=d.destroy).pack(
                      fill="x", padx=14, pady=12, ipady=6)
        d.bind("<Escape>", lambda e: d.destroy())
        d.update_idletasks()
        x = self.win.winfo_rootx() + 60
        y = self.win.winfo_rooty() + 220
        d.geometry("+%d+%d" % (x, y))
        d.grab_set()

    def _btn(self, parent, text, bg, fg, cmd, font=("Segoe UI", 11, "bold"), **kw):
        return tk.Button(parent, text=text, font=font, bg=bg, fg=fg, relief="flat",
                         bd=0, cursor="hand2", activebackground=bg, activeforeground=fg,
                         command=cmd, **kw)

    def _build(self, C):
        HEAD = "#1B3A4B"
        ACCENT = "#2E86AB"

        top = tk.Frame(self.win, bg=HEAD, height=88)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="POS", font=("Segoe UI", 13, "bold"),
                 bg=HEAD, fg="white", justify="left").pack(side="left", padx=(10, 2))

        bcbox = tk.Frame(top, bg=HEAD); bcbox.pack(side="left", padx=8)
        tk.Label(bcbox, text="Barcode", font=("Segoe UI", 9, "bold"),
                 bg=HEAD, fg="#9FC3D6").pack(anchor="w")
        self.barcode_var = tk.StringVar()
        self.barcode_entry = tk.Entry(bcbox, textvariable=self.barcode_var,
                                      font=("Segoe UI", 16), width=11, bg="#EAF4FA",
                                      relief="flat", bd=0)
        self.barcode_entry.pack(ipady=10)
        self.barcode_entry.bind("<Return>", self._on_barcode_enter)

        srchbox = tk.Frame(top, bg=HEAD); srchbox.pack(side="left", padx=8)
        tk.Label(srchbox, text="Search Product (e.g. 'pe co 250')",
                 font=("Segoe UI", 9, "bold"), bg=HEAD, fg="#9FC3D6").pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(srchbox, textvariable=self.search_var,
                                     font=("Segoe UI", 14, "bold"), width=14,
                                     bg="#FFFDEA", relief="flat", bd=0)
        self.search_entry.pack(fill="x", ipady=6)
        self.search_entry.bind("<Return>", self._on_search_enter)
        # live results while typing (this is what makes Search actually
        # load matches — before, nothing appeared until Enter)
        self.search_entry.bind("<KeyRelease>", self._on_search_type)
        self.search_entry.bind("<Down>", lambda e: self._search_dd_move(1))
        self.search_entry.bind("<Up>", lambda e: self._search_dd_move(-1))
        self.search_entry.bind("<Escape>", lambda e: self._close_search_dd())
        self.search_entry.bind("<FocusOut>",
                               lambda e: self.win.after(150, self._close_search_dd))
        self._search_dd = None
        self._search_matches = []

        # ── Bill # browser: ▲ ▼ walk saved bills into this window ──
        # Highlighted panel so it's impossible to miss, with big
        # touch-size buttons (▲ newer · ▼ previous · 🖨 print loaded).
        billbox = tk.Frame(top, bg="#14512E", padx=8, pady=4,
                           highlightbackground="#2ECC71", highlightthickness=2)
        billbox.pack(side="left", padx=10, pady=6)
        tk.Label(billbox, text="BILL No", font=("Segoe UI", 9, "bold"),
                 bg="#14512E", fg="#7FD1B9").pack(anchor="w")
        brow = tk.Frame(billbox, bg="#14512E"); brow.pack()
        self.bill_var = tk.StringVar(value="NEW")
        tk.Entry(brow, textvariable=self.bill_var, font=("Segoe UI", 17, "bold"),
                 width=7, justify="center", bg="#0B3B1F", fg="#2ECC71",
                 relief="flat", bd=0, state="readonly",
                 readonlybackground="#0B3B1F").pack(side="left", ipady=8)
        for txt, cmd, bg in [("▲", lambda: self._nav_bill(+1), "#2E86AB"),
                             ("▼", lambda: self._nav_bill(-1), "#2E86AB"),
                             ("🖨", self._print_loaded, "#16A085")]:
            b = tk.Button(brow, text=txt,
                          font=("Segoe UI Emoji" if txt == "🖨" else "Segoe UI",
                                14, "bold"),
                          width=2, bg=bg, fg="white", relief="flat",
                          cursor="hand2", activebackground="#1B6E8F",
                          command=cmd)
            b.pack(side="left", padx=(4, 0), ipady=6)
        self._loaded_invoice_id = None
        self._loaded_split = None

        # ── Customer: search by NAME / PHONE / VAT — default Cash ──
        # slim strip under the top bar (keeps the top bar free for a BIG search)
        STRIP = "#16313F"
        cust = tk.Frame(self.win, bg=STRIP)
        cust.pack(fill="x", after=top)
        tk.Label(cust, text="Customer  (name / phone / VAT #)",
                 font=("Segoe UI", 9, "bold"), bg=STRIP, fg="#9FC3D6").pack(
                     side="left", padx=(12, 6))
        crow = tk.Frame(cust, bg=STRIP); crow.pack(side="left", pady=4)
        self.cust_search_var = tk.StringVar()
        self.cust_entry = tk.Entry(crow, textvariable=self.cust_search_var,
                                   font=("Segoe UI", 13), width=22,
                                   bg="#EAF4FA", relief="flat", bd=0)
        self.cust_entry.pack(side="left", ipady=4)
        tk.Button(crow, text="✕", font=("Segoe UI", 11, "bold"), width=3,
                  bg="#95A5A6", fg="white", relief="flat", cursor="hand2",
                  command=self._reset_customer).pack(side="left", padx=(4, 0),
                                                     ipady=5)
        tk.Button(crow, text="＋", font=("Segoe UI", 11, "bold"), width=3,
                  bg="#27AE60", fg="white", relief="flat", cursor="hand2",
                  activebackground="#1E8449",
                  command=self._add_customer_quick).pack(side="left", padx=(4, 0),
                                                         ipady=5)
        self.cust_label_var = tk.StringVar(value="Cash Account")
        tk.Label(cust, textvariable=self.cust_label_var, font=("Segoe UI", 10, "bold"),
                 bg=STRIP, fg="#2ECC71").pack(side="left", padx=10)
        self.cust_entry.bind("<KeyRelease>", self._on_cust_type)
        self.cust_entry.bind("<Down>", lambda e: self._cust_dd_move(1))
        self.cust_entry.bind("<Up>", lambda e: self._cust_dd_move(-1))
        self.cust_entry.bind("<Return>", self._on_cust_enter)
        self.cust_entry.bind("<Escape>", lambda e: self._close_cust_dd())
        self.cust_entry.bind("<FocusOut>",
                             lambda e: self.win.after(150, self._close_cust_dd))
        self._cust_dd = None
        self._cust_matches = []
        # legacy alias some code may still touch
        self.mobile_var = tk.StringVar()

        rightbox = tk.Frame(top, bg=HEAD)
        rb = tk.Frame(rightbox, bg=HEAD); rb.pack(pady=(6, 2))
        tk.Button(rb, text="⚙", font=("Segoe UI", 13, "bold"), width=3,
                  bg="#34495E", fg="white", relief="flat",
                  cursor="hand2", activebackground="#2C3E50",
                  command=self._open_pos_settings).pack(side="left", ipady=4)
        tk.Button(rb, text="✕", font=("Segoe UI", 13, "bold"), width=3,
                  bg="#C0392B", fg="white", relief="flat",
                  cursor="hand2", activebackground="#96281B",
                  command=self._close_pos).pack(side="left", padx=(4, 0), ipady=4)
        self.clock_var = tk.StringVar()
        tk.Label(rightbox, textvariable=self.clock_var, font=("Segoe UI", 9),
                 bg=HEAD, fg="#9FC3D6").pack()
        self._tick()
        # top bar: Close/Settings, Bill No and Customer keep their size on
        # the right; the product Search takes ALL the space that is left
        for w in (srchbox, billbox):
            w.pack_forget()
        rightbox.pack(side="right", padx=(4, 8))
        billbox.pack(side="right", padx=(6, 4), pady=6)
        srchbox.pack(side="left", fill="x", expand=True, padx=8)

        sb = tk.Frame(self.win, bg="#0A1519"); sb.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready - scan or type a product, then Enter.")
        tk.Label(sb, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg="#0A1519", fg="#7FD1B9", anchor="w").pack(side="left", fill="x", expand=True)
        try:
            from modules import session_info
            _who = session_info.text()
        except Exception:
            _who = ""
        tk.Label(sb, text=_who, font=("Segoe UI", 8), bg="#0A1519",
                 fg="#7F9AAB").pack(side="right", padx=(4, 8))
        self.day_var = tk.StringVar(value="")
        tk.Label(sb, textvariable=self.day_var, font=("Segoe UI", 8, "bold"),
                 bg="#0A1519", fg="#F1C40F").pack(side="right", padx=8)
        body = tk.Frame(self.win, bg="#0F2027")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        left = tk.Frame(body, bg="white")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Favorite / quick products touch panel (category tabs + stock colours)
        self._build_favorites(left)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        _f = self._size_factor()
        try:
            from ui.zoom import unscaled as _u      # same look at any app Text size
        except Exception:
            _u = lambda n: n
        style.configure("POS.Treeview",
                        rowheight=int((56 if cfg.flag("pos_touchscreen", False) else 44) * _f),
                        font=("Segoe UI", _u(int(round((13 if cfg.flag("pos_touchscreen", False)
                                                        else 12) * _f)))),
                        fieldbackground="white")
        style.configure("POS.Treeview.Heading", font=("Segoe UI", _u(int(round(11 * _f))), "bold"),
                        background=ACCENT, foreground="white")

        cols = [k for k, *_ in self.POS_COLS]
        self.tree = ttk.Treeview(left, columns=cols, show="headings",
                                 style="POS.Treeview", selectmode="browse")
        self.tree._no_zoom = True
        self.tree._own_columns = True          # POS has its own column setting
        for k, head, w, anc in self.POS_COLS:
            self.tree.heading(k, text=head)
            self.tree.column(k, width=w, anchor=anc, stretch=(k in ("name", "name_ar")),
                             minwidth=110 if k in ("name", "name_ar") else (40 if k == "no" else 60))
        self.tree["displaycolumns"] = self._visible_cols()
        try:                                   # Excel-style cell lines
            from ui.grid_lines import excel_grid
            excel_grid(self.tree, select_bg="#FFE8CC", color="#D5DCE6")
        except Exception:
            pass
        self.tree.tag_configure("ret", foreground="#C0392B", background="#FDEDEC")
        self.tree.tag_configure("offer", foreground="#0E7C3A", background="#EAFBF0")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.tree.bind("<Delete>", lambda e: (self._remove_selected(), "break")[1])
        self.tree.bind("<Configure>", self._fit_columns, add="+")
        self.tree.bind("<Double-1>", self._edit_cart_line)
        # HOLD Ctrl → purchase price + box qty of the selected line; let go = closed
        try:
            from ui.product_boxes import CtrlHold
            self._ctrl_hold = CtrlHold([self.win], self._ctrl_box)
        except Exception:
            self._ctrl_hold = None

        # totals at the very bottom, the +/- strip above them, the bill grid
        # takes the space that is left (nothing is cut off on a 768 screen)
        totals = tk.Frame(left, bg="#1B3A4B"); totals.pack(fill="x", side="bottom")
        strip = tk.Frame(left, bg="#ECF0F1", height=52)
        strip.pack(fill="x", side="bottom"); strip.pack_propagate(False)
        self.tree.pack(fill="both", expand=True, side="top")
        tk.Button(strip, text="+", font=("Segoe UI", 17, "bold"), width=5,
                  bg="#27AE60", fg="white", relief="flat", cursor="hand2",
                  command=lambda: self._bump(1)).pack(side="left", padx=4, pady=4)
        tk.Button(strip, text="-", font=("Segoe UI", 17, "bold"), width=5,
                  bg="#E67E22", fg="white", relief="flat", cursor="hand2",
                  command=lambda: self._bump(-1)).pack(side="left", padx=4, pady=4)
        self.minus_btn = tk.Button(strip, text="↩ Return (−)", font=("Segoe UI", 11, "bold"),
                                   bg="#8E44AD", fg="white", relief="flat", padx=10,
                                   cursor="hand2", activebackground="#6C3483",
                                   activeforeground="white", command=self._toggle_minus)
        self.minus_btn.pack(side="left", padx=4)
        self._minus = False
        tk.Button(strip, text="Remove Line", font=("Segoe UI", 12, "bold"), bg="#E74C3C",
                  fg="white", relief="flat", padx=10, cursor="hand2",
                  command=self._remove_selected).pack(side="left", padx=4)
        tk.Button(strip, text="Edit Line", font=("Segoe UI", 11, "bold"), bg="#34495E",
                  fg="white", relief="flat", padx=10, cursor="hand2",
                  command=lambda: self._edit_cart_line()).pack(side="left", padx=4)
        tk.Button(strip, text="▤ Columns", font=("Segoe UI", 9, "bold"), bg="white",
                  fg="#2C3E50", relief="flat", padx=8, cursor="hand2",
                  command=self._open_columns).pack(side="right", padx=6)
        self.lines_var = tk.StringVar(value="0 lines · 0 qty")
        tk.Label(strip, textvariable=self.lines_var, font=("Segoe UI", 9), bg="#ECF0F1",
                 fg="#7F8C8D").pack(side="right", padx=6)

        self.tqty_var = tk.StringVar(value="0")
        self.gross_var = tk.StringVar(value="0.00")
        self.disc_var = tk.StringVar(value="0.00")
        self.tax_var = tk.StringVar(value="0.00")
        self.total_var = tk.StringVar(value="0.00")
        self.paid_var = tk.StringVar(value="0.00")
        self.balance_var = tk.StringVar(value="0.00")
        self.change_var = tk.StringVar(value="0.00")
        TB = "#1B3A4B"
        g = tk.Frame(totals, bg=TB); g.pack(side="left", fill="y", padx=(12, 6), pady=6)

        def cell(r, c, lbl, var):
            tk.Label(g, text=lbl, font=("Segoe UI", 9), bg=TB, fg="#9FC3D6").grid(
                row=r, column=c * 2, sticky="w", padx=(0 if c == 0 else 18, 6))
            l = tk.Label(g, textvariable=var, font=("Segoe UI", 10, "bold"), bg=TB, fg="white",
                         width=9, anchor="e")
            l.grid(row=r, column=c * 2 + 1, sticky="e")
            return l
        cell(0, 0, "Total Qty", self.tqty_var)
        cell(1, 0, "Gross Amount", self.gross_var)
        cell(2, 0, "Discount", self.disc_var)
        cell(3, 0, "Total Tax (VAT)", self.tax_var)
        tk.Label(g, text="Paid Amount", font=("Segoe UI", 9), bg=TB, fg="#9FC3D6").grid(
            row=0, column=2, sticky="w", padx=(18, 6))
        pe = tk.Entry(g, textvariable=self.paid_var, font=("Segoe UI", 11, "bold"),
                      width=9, justify="right", relief="flat", bg="#EAF4FA")
        pe.grid(row=0, column=3, sticky="e")
        pe.bind("<FocusIn>", lambda e: self._set_pad("paid", quiet=True))
        self._paid_tile = pe
        self._balance_lbl = cell(1, 1, "Balance Due", self.balance_var)
        cell(2, 1, "Change Return", self.change_var)
        self.paid_var.trace("w", lambda *a: self._update_change())
        # Settings ▸ POS / Tax: the entered Rate already includes VAT
        self.incl_vat_var = tk.BooleanVar(value=_price_incl())
        tk.Checkbutton(g, text="Sale price includes VAT",
                       variable=self.incl_vat_var, command=self._toggle_incl_vat,
                       font=("Segoe UI", 9, "bold"), bg=TB, fg="#F1C40F",
                       selectcolor=TB, activebackground=TB,
                       activeforeground="#F1C40F", bd=0, highlightthickness=0,
                       cursor="hand2").grid(row=3, column=2, columnspan=2, sticky="w",
                                            padx=(18, 0))
        big = tk.Frame(totals, bg="#0B2533"); big.pack(side="right", fill="both", expand=True,
                                                       padx=(6, 8), pady=6)
        self.total_cap_var = tk.StringVar(value="TOTAL (SAR)")
        tk.Label(big, textvariable=self.total_cap_var, font=("Segoe UI", 12, "bold"),
                 bg="#0B2533", fg="#9FC3D6").pack(anchor="ne", padx=12, pady=(6, 0))
        self.total_lbl = tk.Label(big, textvariable=self.total_var, font=("Segoe UI", 30, "bold"),
                                  bg="#0B2533", fg="#2ECC71")
        self.total_lbl.pack(anchor="e", padx=12)

        right = tk.Frame(body, bg="#0F2027", width=int(440 * self._size_factor()) + 20)
        right.pack(side="right", fill="y"); right.pack_propagate(False)

        act = tk.Frame(right, bg="#0F2027"); act.pack(fill="x", pady=(0, 6))
        self._abtn(act, "Hold\n[F6]", "#2E86AB", self._hold, 0, 0)
        self.retrieve_lbl = self._abtn(act, "Retrieve\n[F7]", "#2E86AB", self._retrieve, 0, 1)
        self._abtn(act, "New\n[F3]", "#16A085", self._new_sale, 0, 2)
        self._abtn(act, "Last Bill\n🖨", "#34495E", self._print_last_bill, 0, 3)
        _ncol = 4
        try:                                   # v6.9.2: ⭐ loyalty points
            from modules import loyalty as _loy
            if _loy.enabled():
                self.points_btn = self._abtn(act, "⭐ Points\n[F10]", "#B7950B",
                                             self._use_points, 0, 4)
                _ncol = 5
        except Exception:
            pass
        for i in range(_ncol):
            act.columnconfigure(i, weight=1, uniform="a")

        pad = tk.Frame(right, bg="#0F2027"); pad.pack(fill="both", expand=True)

        bigcol = tk.Frame(pad, bg="#0F2027"); bigcol.pack(side="left", fill="y", padx=(0, 6))
        # only Cash and Card — both open the Cash + Card window (mixed payment)
        for _lbl, _clr, _pm in (("Cash", "#27AE60", "cash"), ("Card", "#2980B9", "card")):
            if cfg.payment_enabled(_pm):
                self._bigbtn(bigcol, _lbl, _clr, lambda p=_pm: self._open_pay(p))

        grid = tk.Frame(pad, bg="#0F2027"); grid.pack(side="left", fill="both", expand=True)
        keys = [("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
                ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
                ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
                (".", 3, 0), ("0", 3, 1), ("<", 3, 2)]
        for txt, r, c in keys:
            tk.Button(grid, text=txt, font=("Segoe UI", 18, "bold"),
                      bg="#ECF0F1", fg="#2C3E50", relief="flat", cursor="hand2",
                      command=lambda v=txt: self._pad_press(v)).grid(
                      row=r, column=c, sticky="nsew", padx=3, pady=3, ipady=10)
        for i in range(3):
            grid.columnconfigure(i, weight=1)
        for i in range(4):
            grid.rowconfigure(i, weight=1)

        sidecol = tk.Frame(pad, bg="#0F2027"); sidecol.pack(side="left", fill="y", padx=(6, 0))
        self.qty_btn = tk.Button(sidecol, text="Qty", font=("Segoe UI", 13, "bold"),
                                 bg="#E67E22", fg="white", relief="flat", width=7,
                                 cursor="hand2", command=lambda: self._set_pad("qty"))
        self.qty_btn.pack(fill="x", pady=3, ipady=12)
        self.rate_btn = tk.Button(sidecol, text="Rate", font=("Segoe UI", 13, "bold"),
                                  bg="#95A5A6", fg="white", relief="flat", width=7,
                                  cursor="hand2", command=lambda: self._set_pad("rate"))
        self.rate_btn.pack(fill="x", pady=3, ipady=12)
        tk.Button(sidecol, text="Clear", font=("Segoe UI", 13, "bold"),
                  bg="#95A5A6", fg="white", relief="flat", width=7, cursor="hand2",
                  command=self._pad_clear).pack(fill="x", pady=3, ipady=12)
        tk.Button(sidecol, text="Enter", font=("Segoe UI", 13, "bold"),
                  bg="#2980B9", fg="white", relief="flat", width=7, cursor="hand2",
                  command=self._pad_enter).pack(fill="x", pady=3, ipady=12)

        bot = tk.Frame(right, bg="#0F2027"); bot.pack(fill="x", pady=(8, 0))
        tk.Button(bot, text="SAVE   [F1]", font=("Segoe UI", 22, "bold"),
                  bg="#27AE60", fg="white", relief="flat", cursor="hand2",
                  activebackground="#1E8449", activeforeground="white",
                  command=lambda: self._save_smart()).grid(
                  row=0, column=0, columnspan=3, sticky="nsew", padx=2, ipady=14)
        tk.Button(bot, text="Save+Print [F2]", font=("Segoe UI", 11, "bold"),
                  bg="#2980B9", fg="white", relief="flat", cursor="hand2",
                  command=lambda: self._save_smart(do_print=True)).grid(
                  row=1, column=0, sticky="nsew", padx=2, pady=(4, 0), ipady=6)
        # v6.0: cashier shift (opening float → counted cash)
        self.shift_btn = tk.Button(bot, text="Shift [F9]", font=("Segoe UI", 11, "bold"),
                                   bg="#7C3AED", fg="white", relief="flat", cursor="hand2",
                                   command=self._shift)
        self.shift_btn.grid(row=1, column=1, sticky="nsew", padx=2, pady=(4, 0), ipady=6)
        tk.Button(bot, text="Delete Bill", font=("Segoe UI", 11, "bold"),
                  bg="#C0392B", fg="white", relief="flat", cursor="hand2",
                  command=self._delete_bill).grid(
                  row=1, column=2, sticky="nsew", padx=2, pady=(4, 0), ipady=6)
        for i in range(3):
            bot.columnconfigure(i, weight=1, uniform="b")

        self._refresh_day_info()
        self._shift_label()
        self._shrink(self.win)

    def _abtn(self, parent, txt, bg, cmd, r, c):
        b = tk.Button(parent, text=txt, font=("Segoe UI", 13, "bold"), bg=bg,
                      fg="white", relief="flat", cursor="hand2", command=cmd)
        b.grid(row=r, column=c, sticky="nsew", padx=3, ipady=12)
        return b

    def _bigbtn(self, parent, txt, bg, cmd):
        tk.Button(parent, text=txt, font=("Segoe UI", 18, "bold"), bg=bg,
                  fg="white", relief="flat", width=6, cursor="hand2",
                  command=cmd).pack(fill="both", expand=True, pady=3, ipadx=4)

    # -- Favorite / quick products touch panel ------------------
    def _stock_color(self, p):
        """Green = available, Yellow = low (<= reorder), Red = out of stock."""
        try:
            s = float(p.get("stock_quantity", 0) or 0)
            r = float(p.get("reorder_level", 0) or 0)
        except Exception:
            s, r = 1, 0
        if s <= 0:
            return "#E74C3C"
        if r > 0 and s <= r:
            return "#F39C12"
        return "#27AE60"

    def _build_favorites(self, parent):
        if not cfg.flag("pos_show_favorites", True):   # Settings ▸ POS
            self.fav_area = tk.Frame(parent)            # keep attribute valid
            return
        small = self.win.winfo_screenheight() < 820
        self.FAV_PER_PAGE = 12 if small else 18
        wrap = tk.Frame(parent, bg="#ECF0F1", height=140 if small else 192)
        wrap.pack(fill="x", side="top")
        wrap.pack_propagate(False)

        # category tabs
        cats = []
        for p in self.products:
            c = p.get("category_name", "Other") or "Other"
            if c not in cats:
                cats.append(c)
        cats = ["★ Favourites"] + sorted(cats)[:9]
        self._fav_cats = cats

        tabbar = tk.Frame(wrap, bg="#1B3A4B", height=34)
        tabbar.pack(fill="x"); tabbar.pack_propagate(False)
        self._fav_tab_btns = {}
        for c in cats:
            b = tk.Button(tabbar, text=c, font=("Segoe UI", 9, "bold"),
                          bg="#1B3A4B", fg="white", relief="flat", cursor="hand2",
                          padx=10, command=lambda cc=c: self._show_fav_category(cc))
            b.pack(side="left", padx=1, pady=3)
            self._fav_tab_btns[c] = b

        for txt, col in (("Out", "#E74C3C"), ("Low", "#F39C12"), ("In stock", "#27AE60")):
            tk.Label(tabbar, text=txt, font=("Segoe UI", 7), bg="#1B3A4B",
                     fg="#9FC3D6").pack(side="right", padx=(2, 8))
            tk.Label(tabbar, text="  ", bg=col).pack(side="right")

        self.fav_area = tk.Frame(wrap, bg="#ECF0F1")
        self.fav_area.pack(fill="both", expand=True)

        self._show_fav_category(cats[0])

    FAV_PER_PAGE = 18

    def _favourite_products(self):
        """Products ticked ⭐ POS Favourite (Product form / list). Until
        any are marked, show this month's best sellers instead."""
        by_id = {p["product_id"]: p for p in self.products}
        ids = []
        try:
            ids = [r["product_id"] for r in (db.fetchall(
                "SELECT product_id FROM products WHERE ISNULL(is_favorite,0)=1 "
                "AND is_active=1 ORDER BY ISNULL(fav_order,0), product_name_en") or [])]
        except Exception:
            ids = []
        favs = [by_id[i] for i in ids if i in by_id]
        if favs:
            return favs, True
        try:
            top = db.fetchall(
                "SELECT TOP 18 sil.product_id FROM sales_invoice_lines sil "
                "JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
                "WHERE si.invoice_status='confirmed' "
                "AND si.invoice_date >= DATEADD(day,-30,CAST(GETDATE() AS date)) "
                "GROUP BY sil.product_id ORDER BY SUM(sil.quantity) DESC") or []
            favs = [by_id[r["product_id"]] for r in top if r["product_id"] in by_id]
        except Exception:
            favs = []
        return (favs or self.products[:self.FAV_PER_PAGE]), False

    def _show_fav_category(self, cat, page=0):
        for c, b in getattr(self, "_fav_tab_btns", {}).items():
            b.configure(bg="#2E86AB" if c == cat else "#1B3A4B")
        for w in self.fav_area.winfo_children():
            w.destroy()
        marked = True
        if cat.startswith("★"):
            items, marked = self._favourite_products()
        else:
            items = [p for p in self.products
                     if (p.get("category_name", "Other") or "Other") == cat]
        n = self.FAV_PER_PAGE
        pages = max(1, (len(items) + n - 1) // n)
        page = max(0, min(page, pages - 1))
        shown = items[page * n:(page + 1) * n]
        touch = cfg.flag("pos_touchscreen", False)      # Settings ▸ POS
        pics = self._fav_images(shown) if cfg.flag("pos_show_images", False) else {}
        for i, p in enumerate(shown):
            name = (p.get("product_name_en", "") or "")[:16]
            price = float(p.get("unit_price", 0) or 0)
            img = pics.get(p.get("product_id"))
            opts = dict(image=img, compound="top", width=110) if img else dict(width=12)
            b = tk.Button(self.fav_area,
                          text=f"{name}\n{price:,.2f}",
                          font=("Segoe UI", 10 if touch else 8, "bold"),
                          bg=self._stock_color(p), fg="white", relief="flat",
                          cursor="hand2",
                          command=lambda pp=p: self._fav_add(pp), **opts)
            b.grid(row=i // 6, column=i % 6, sticky="nsew", padx=3 if touch else 2,
                   pady=3 if touch else 2, ipady=(4 if img else (16 if touch else 6)))
        for c in range(6):
            self.fav_area.columnconfigure(c, weight=1)
        # paging + hint row
        foot = tk.Frame(self.fav_area, bg="#ECF0F1")
        foot.grid(row=4, column=0, columnspan=6, sticky="ew")
        if cat.startswith("★") and not marked:
            tk.Label(foot, text="Showing best sellers — mark your own with ⭐ POS Favourite "
                     "in Products", font=("Segoe UI", 7), bg="#ECF0F1",
                     fg="#7F8C8D").pack(side="left", padx=4)
        if pages > 1:
            tk.Button(foot, text="▶", font=("Segoe UI", 8, "bold"), bg="#1B3A4B", fg="white",
                      relief="flat", cursor="hand2", padx=8,
                      state="normal" if page < pages - 1 else "disabled",
                      command=lambda: self._show_fav_category(cat, page + 1)).pack(side="right")
            tk.Label(foot, text=f"{page + 1}/{pages}", font=("Segoe UI", 8),
                     bg="#ECF0F1", fg="#1B3A4B").pack(side="right", padx=4)
            tk.Button(foot, text="◀", font=("Segoe UI", 8, "bold"), bg="#1B3A4B", fg="white",
                      relief="flat", cursor="hand2", padx=8,
                      state="normal" if page > 0 else "disabled",
                      command=lambda: self._show_fav_category(cat, page - 1)).pack(side="right")
        self._shrink(self.fav_area)

    def _fav_images(self, products):
        """Settings ▸ POS ▸ Show Product Pictures: small thumbnails of each
        product's main picture (Products ▸ Images). Cached per session."""
        cache = self.__dict__.setdefault("_fav_img_cache", {})
        want = [p.get("product_id") for p in products
                if p.get("product_id") and p.get("product_id") not in cache]
        if want:
            try:
                rows = db.fetchall(
                    "SELECT product_id, image_path, is_default FROM product_images "
                    "WHERE product_id IN (%s) ORDER BY is_default DESC, image_id"
                    % ",".join("?" * len(want)), tuple(want)) or []
            except Exception:
                rows = []
            paths = {}
            for r in rows:
                paths.setdefault(r["product_id"], r.get("image_path"))
            try:
                from PIL import Image, ImageTk
            except Exception:
                Image = None
            size = 56 if cfg.flag("pos_touchscreen", False) else 40
            for pid in want:
                cache[pid] = None
                path = paths.get(pid)
                if not (Image and path and os.path.exists(str(path))):
                    continue
                try:
                    im = Image.open(path)
                    im.thumbnail((size, size))
                    cache[pid] = ImageTk.PhotoImage(im, master=self.win)
                except Exception:
                    cache[pid] = None
        return {p.get("product_id"): cache.get(p.get("product_id")) for p in products}

    def _fav_add(self, p):
        self._add_to_cart(p)
        try:
            self.barcode_entry.focus_set()
        except Exception:
            pass

    def _clear_scan_box(self):
        """Esc — clear whatever's typed in the scan/barcode box and
        refocus it, without closing the POS window."""
        try:
            self.barcode_var.set("")
            self.barcode_entry.focus_set()
        except Exception:
            pass
        if getattr(self, "_minus", False):
            self._set_minus(False)
            self.status_var.set("Return / − cancelled.")

    def _bind_keys(self):
        self.win.bind("<F1>", lambda e: self._save_smart())
        self.win.bind("<F2>", lambda e: self._save_smart(do_print=True))
        self.win.bind("<F3>", lambda e: self._new_sale())
        self.win.bind("<F6>", lambda e: self._hold())
        self.win.bind("<F7>", lambda e: self._retrieve())
        self.win.bind("<F8>", lambda e: self._price_check())
        self.win.bind("<F9>", lambda e: self._shift())
        self.win.bind("<F10>", lambda e: (self._use_points(), "break")[1])
        self.win.bind("<space>", self._space_cycle_unit)
        self.win.bind("<Escape>", lambda e: self._clear_scan_box())

    # ── v6.0: keep selling when the server is briefly gone ────
    def _keep_offline(self, err):
        """The bill could not reach the server: offer to keep it on this PC.
        → True when it was kept (the screen is ready for the next customer)."""
        try:
            from modules import offline_pos as OFF
        except Exception:
            return False
        pend = getattr(self, "_pending_offline", None)
        self._pending_offline = None
        if not pend or not OFF.enabled() or not OFF.is_connection_error(err):
            return False
        lines, h, is_credit, loaded_id, do_print = pend
        if is_credit or loaded_id:
            messagebox.showwarning("Server not reachable",
                                   "The server can't be reached.\n\nA sale on account (or a change to "
                                   "a saved bill) needs the server — take the payment in cash / card, "
                                   "or try again when the connection is back.", parent=self.win)
            return True
        if not messagebox.askyesno(
                "Server not reachable  ·  الخادم غير متاح",
                "The bill could not reach the server.\n\nKeep it on THIS PC and send it by itself when "
                "the server is back?\n(The receipt is marked PROVISIONAL; the tax invoice can be "
                "reprinted later from Last Bill.)", parent=self.win):
            return True
        try:
            from modules import shifts as _sh, permissions as _p
            sid = (_sh.current() or {}).get("shift_id") if _sh.ready() else None
        except Exception:
            sid = None
        if sid is None:                          # server gone: the shift we last saw open
            sid = getattr(self, "_known_shift_id", None)
        try:
            uid = (_p.session_user() or {}).get("user_id")
        except Exception:
            uid = None
        number = OFF.keep(lines, h, shift_id=sid, user_id=uid)
        if do_print:
            try:
                from modules import printer_service as PS
                pdf = OFF.provisional_receipt(lines, h, number, getattr(self, "_company", {}) or {})
                PS.print_pdf(pdf, PS.printer_for("pos"))
            except Exception:
                pass
        if h.get("cash_amt", 0) > 0 and cfg.flag("pos_open_drawer", True):
            try:
                from modules import voice_alert
                voice_alert.open_cash_drawer()
            except Exception:
                pass
        self.cart = []
        self._sel_idx = None
        self.bill_var.set("NEW")
        self.paid_var.set("0.00")
        self._loaded_split = None
        self._reset_customer()
        self._render_cart()
        self.status_var.set("📴 Server offline — bill %s kept on this PC (%d waiting). It is sent "
                            "by itself when the server is back." % (number, OFF.count()))
        try:
            self.barcode_entry.focus_set()
        except Exception:
            pass
        self._offline_schedule(30000)
        return True

    def _offline_schedule(self, ms=60000):
        try:
            if getattr(self, "_offline_job", None):
                return
            self._offline_job = self.win.after(ms, self._offline_tick)
        except Exception:
            pass

    def _offline_tick(self):
        """Every minute: send the bills kept on this PC when the server is back."""
        self._offline_job = None
        try:
            from modules import offline_pos as OFF
            if not OFF.count():
                return
            if not db.is_connected():
                try:
                    db.connect()
                except Exception:
                    pass
            if not db.is_connected():
                self._offline_schedule(60000)
                return
            sent, errors = OFF.send_all(getattr(self, "_company", None))
            left = OFF.count()
            if sent:
                self.status_var.set("✅ %d bill(s) kept offline are now saved on the server%s."
                                    % (sent, (" — %d still waiting" % left) if left else ""))
                self._refresh_day_info()
            elif errors and not errors[0].startswith("server"):
                self.status_var.set("⚠ Offline bills: " + errors[0][:120])
            if left:
                self._offline_schedule(60000)
        except Exception:
            self._offline_schedule(60000)

    # ── v6.0: cashier shifts ──────────────────────────────────
    def _shift(self):
        """Shift [F9]: open a shift (opening float) or close it (count)."""
        try:
            from ui import shift_dialog
            d = shift_dialog.shift_button(self.win, self.status_var)
        except Exception as e:
            self.status_var.set("Shift: %s" % str(e)[:80])
            return None
        try:
            self.win.after(400, self._shift_label)
        except Exception:
            pass
        return d

    def _shift_label(self):
        try:
            from modules import shifts
            if not shifts.ready():               # server gone (or no shifts yet): keep what we know
                return
            s = shifts.current()
            self._known_shift_id = (s or {}).get("shift_id")
            self.shift_btn.configure(text=("Shift ● [F9]" if s else "Shift [F9]"),
                                     bg="#7C3AED" if s else "#6B7280")
        except Exception:
            pass

    def _shift_ok(self):
        """Settings ▸ POS ▸ 'Cashier must open a shift': no sale before the
        opening float is counted."""
        try:
            from modules import shifts
            if not shifts.ready() or not shifts.required() or shifts.current():
                return True
        except Exception:
            return True
        self.status_var.set("Open a shift first: count the cash in the drawer.")
        try:
            from ui import shift_dialog
            d = shift_dialog.OpenShiftDialog(self.win)
            self.win.wait_window(d)
            self._shift_label()
            return bool(d.result)
        except Exception:
            return False

    def _price_check(self):
        """F8 — Price Check: scan to see a price (any unit, offers, stock)
        without adding anything to the bill."""
        try:
            from ui.price_check import open_price_check
            self._pc = open_price_check(self.win, on_close=self._focus_barcode_default)
        except Exception as e:
            self.status_var.set("Price check: %s" % str(e)[:80])
        return "break"

    def _tick(self):
        self.clock_var.set(datetime.now().strftime("%d/%m/%Y  %H:%M"))
        self.win.after(1000, self._tick)

    # -- Barcode / search entry --------------------------------
    def _on_barcode_enter(self, event=None):
        """Barcode field — strict lookup only (exact barcode or product
        code). Handles MULTIPLE codes arriving at once (batch scanners,
        a second scan landing before the first Enter, pasted lists):
        the buffer is split and every code is processed one by one —
        repeated codes simply increase the quantity. Always returns
        focus here afterwards."""
        import re
        raw = self.barcode_var.get()
        if not raw.strip():
            return "break"
        # split on newline / tab / space / comma / semicolon
        codes = [c for c in re.split(r"[\s,;]+", raw.strip()) if c]
        self.barcode_var.set("")
        if codes == ["-"] or codes == ["*-"]:          # '−' + Enter → next item is '−'
            self._toggle_minus()
            return "break"
        added, missed = 0, []
        for txt in codes:
            if self._scan_one(txt):
                added += 1
            else:
                missed.append(txt)
        if len(codes) > 1:
            msg = "%d scans: %d added" % (len(codes), added)
            if missed:
                msg += ", %d not found (%s)" % (len(missed),
                                                ", ".join(missed[:3]))
            self.status_var.set(msg)
        elif missed:
            self.status_var.set("No product found for barcode '%s'."
                                % missed[0])
        if missed:
            self._alert_not_found()
        self._focus_barcode_default()
        return "break"

    def _scan_one(self, txt):
        """Add ONE scanned code to the cart. True if a product matched."""
        txt = txt.strip()
        if not txt:
            return True
        if txt.startswith("-") and len(txt) > 1:       # '-' typed before the scan
            self._set_minus(True)
            txt = txt[1:]
            if not self._scan_one(txt):
                self._set_minus(False)
                return False
            return True
        res = self._resolve_barcode(txt)
        if res:
            prod, unit_id = res
            self._add_to_cart(prod, unit_id=unit_id)
            return True
        # fall back to an exact product-code match (not fuzzy — that's
        # the Search field's job)
        prod = next((p for p in self.products
                    if str(p.get("product_code", "")).strip().lower() == txt.lower()), None)
        if prod:
            self._add_to_cart(prod)
            return True
        # weighing-scale label (PLU + weight/price inside the barcode)
        try:
            from modules.scale_barcode import decode
            hit = decode(txt)
        except Exception:
            hit = None
        if hit:
            pid = hit["product"].get("product_id")
            prod = next((p for p in self.products if p["product_id"] == pid), None)
            if prod and getattr(self, "_minus", False):
                # weighed item taken off / returned: its own weight + price
                self._set_minus(False)
                from modules.scale_barcode import line_values
                try:
                    incl = bool(self.incl_vat_var.get())
                except Exception:
                    incl = _price_incl()
                qty, price = line_values(hit, incl, float(prod.get("vat_rate") or 0))
                self._minus_item(prod, None, qty=float(qty or 1), price=price)
                return True
            if prod:
                self._add_to_cart(prod)
                # a scale label is its own line: set the weighed qty
                ln = next((l for l in reversed(self.cart) if l["product_id"] == pid), None)
                if ln:
                    from modules.scale_barcode import line_values
                    try:
                        incl = bool(self.incl_vat_var.get())
                    except Exception:
                        incl = _price_incl()
                    qty, price = line_values(hit, incl, float(ln.get("vat_rate") or 0))
                    if price is not None and ln["quantity"] > 1:
                        # a price label is its own line (exact label amount)
                        ln["quantity"] -= 1
                        self._recalc(ln)
                        ln = dict(ln)
                        self.cart.append(ln)
                        ln["quantity"] = 0
                    if ln["quantity"] > 1:            # merged onto an existing line
                        ln["quantity"] = ln["quantity"] - 1 + qty
                    else:
                        ln["quantity"] = qty
                    if price is not None:
                        ln["unit_price"] = price
                        ln.update(offer_off=True, discount_amount=0.0, offer_id=None, offer_text="")  # label price = the price
                    self._recalc(ln)
                    self._render_cart(select_pid=pid, select_unit=ln["unit_name"])
                    self.status_var.set("⚖ %s  %g %s" % (prod.get("product_name_en", ""),
                                                        hit["quantity"], ln["unit_name"]))
                return True
        return False

    def _on_search_enter(self, event=None):
        """Enter in Search — picks the highlighted dropdown match if the
        live results are open, else the best fuzzy match. Multi-unit
        products open the Unit Picker (editable price + stock)."""
        txt = self.search_var.get().strip()
        if txt and " " not in txt and len(txt) >= 4:
            # a barcode scanned into Search (Box / Carton / extra / scale
            # label) rings up exactly like the Barcode field
            try:
                from modules.barcode_resolver import resolve
                hit = resolve(txt, products=self.products)
            except Exception:
                hit = None
            if hit and hit.get("via") != "code":
                self._close_search_dd()
                self.search_var.set("")
                if not self._scan_one(txt):
                    self._alert_not_found()
                self._focus_barcode_default()
                return "break"
        if self._search_dd is not None and self._search_dd.winfo_exists():
            self._pick_dd_index()
            return "break"
        txt = self.search_var.get().strip()
        if not txt:
            return "break"
        prod = self._best_match(txt)
        if not prod:
            self.status_var.set("No product matches '%s'." % txt)
            self._alert_not_found()
            self._focus_barcode_default()
            return "break"
        self.search_var.set("")
        self._pick_search_result(prod)
        return "break"

    def _on_unit_picked(self, prod, unit_id, price_override=None):
        """Callback from the Unit Picker dialog — add with the chosen
        unit, applying any price the user edited in the dialog."""
        if getattr(self, "_minus", False):
            self._set_minus(False)
            self._minus_item(prod, unit_id, price=price_override)
            self._focus_barcode_default()
            return
        self._add_to_cart(prod, unit_id=unit_id)
        if price_override is not None:
            # the line just added is the last one touching this product+unit
            unit = next((u for u in self._units_for(prod["product_id"])
                        if u["unit_id"] == unit_id), None)
            uname = unit["unit_name_en"] if unit else None
            for ln in reversed(self.cart):
                if ln["product_id"] == prod["product_id"] and ln["quantity"] > 0 and (
                        uname is None or ln["unit_name"] == uname):
                    ln["unit_price"] = float(price_override)
                    ln.update(offer_off=True, discount_amount=0.0, offer_id=None, offer_text="")  # price typed by the cashier
                    self._recalc(ln)
                    self._render_cart(select_line=ln)
                    break
        self._focus_barcode_default()

    def _focus_barcode_default(self):
        """The Barcode field is the permanent resting place for the
        cursor in POS — call this after every action completes."""
        try:
            self.barcode_entry.focus_set()
        except Exception:
            pass

    # ── Live product-search dropdown ───────────────────────────
    def _all_matches(self, query, limit=8):
        if filter_products:
            try:
                found = (filter_products(query, self.products) or [])[:limit]
                if not found and " " not in query.strip() and len(query.strip()) >= 4:
                    res = self._resolve_barcode(query.strip())   # Box / Carton / extra barcode
                    if res:
                        found = [res[0]]
                return found
            except Exception:
                pass
        q = query.lower()
        out = []
        for p in self.products:
            hay = " ".join([str(p.get("product_name_en", "")),
                            str(p.get("product_code", "")),
                            str(p.get("alias_name", ""))]).lower()
            if all(tok in hay for tok in q.split()):
                out.append(p)
                if len(out) >= limit:
                    break
        return out

    def _on_search_type(self, event=None):
        if event and event.keysym in ("Return", "Up", "Down", "Escape",
                                      "Left", "Right", "Tab"):
            return
        txt = self.search_var.get().strip()
        if not txt:
            self._close_search_dd()
            return
        try:   # Settings ▸ Performance ▸ Product Search Limit
            _lim = max(5, min(500, int(float(cfg.get("perf_search_limit", 50) or 50))))
        except Exception:
            _lim = 8
        self._search_matches = self._all_matches(txt, limit=_lim)
        if not self._search_matches:
            self._close_search_dd()
            return
        self._show_search_dd()

    def _show_search_dd(self):
        """Live search results as a table: code, name, Arabic, unit,
        stock, purchase price, sales price (incl. VAT)."""
        show_cost = cfg.flag("pos_show_cost_in_search", True)
        cols = ["code", "name", "ar", "unit", "stock"] + (["cost"] if show_cost else []) + ["price"]
        if self._search_dd is None or not self._search_dd.winfo_exists():
            self._search_dd = tk.Toplevel(self.win)
            self._search_dd.overrideredirect(True)
            self._search_dd.attributes("-topmost", True)
            st = ttk.Style()
            try:
                from ui.zoom import unscaled as _u
            except Exception:
                _u = lambda n: n
            st.configure("PosSearch.Treeview", rowheight=36, font=("Segoe UI", _u(13)),
                         background="white", fieldbackground="white")
            st.configure("PosSearch.Treeview.Heading", font=("Segoe UI", _u(10), "bold"),
                         background="#1B3A4B", foreground="white")
            st.map("PosSearch.Treeview", background=[("selected", "#2E86AB")],
                   foreground=[("selected", "white")])
            fr = tk.Frame(self._search_dd, bg="#1B3A4B", bd=0,
                          highlightthickness=2, highlightbackground="#2E86AB")
            fr.pack(fill="both", expand=True)
            self._search_lb = ttk.Treeview(fr, columns=cols, show="headings",
                                           style="PosSearch.Treeview", height=8,
                                           selectmode="browse")
            self._search_lb._no_zoom = True
            self._search_lb._own_columns = True
            heads = {"code": ("Code", 90, "w"), "name": ("Product", 330, "w"),
                     "ar": ("الاسم", 200, "e"), "unit": ("Unit", 70, "center"),
                     "stock": ("Stock", 90, "e"), "cost": ("Purchase", 100, "e"),
                     "price": ("Sales Price", 120, "e")}
            for c in cols:
                t_, w, anc = heads[c]
                self._search_lb.heading(c, text=t_, anchor=anc)
                self._search_lb.column(c, width=w, anchor=anc, stretch=c == "name")
            self._search_lb.tag_configure("out", foreground="#C0392B")
            self._search_lb.tag_configure("low", foreground="#D35400")
            self._search_lb.pack(fill="both", expand=True)
            self._search_lb.bind("<ButtonRelease-1>", lambda e: self._pick_dd_index())
            try:
                from ui.grid_lines import excel_grid
                excel_grid(self._search_lb, fill_empty=False, select_bg="#2E86AB",
                           select_fg="white")
            except Exception:
                pass
        tv = self._search_lb
        tv.delete(*tv.get_children())
        try:
            low_lvl = float(cfg.get("inv_low_stock_level", 5) or 5)
        except Exception:
            low_lvl = 5.0
        for i, p in enumerate(self._search_matches):
            stock = float(p.get("stock_quantity", 0) or 0)
            sp = float(p.get("unit_price", 0) or 0)
            vrate = float(p.get("vat_rate", 15) or 0)
            sp_vat = cfg.price_with_vat(sp, vrate)
            units = self._units_for(p["product_id"])
            du = next((u for u in units if u.get("is_default")),
                      (units[0] if units else None))
            uname = du.get("unit_name_en", "") if du else ""
            fac = float((du or {}).get("conversion_factor") or 1) or 1.0
            if du and float(du.get("selling_price") or 0):
                sp_vat = cfg.price_with_vat(float(du["selling_price"]), vrate)
            stock = stock / fac                      # in the unit shown
            cost = float((du or {}).get("purchase_price") or 0) or \
                float(p.get("purchase_price", 0) or 0) * fac
            vals = {"code": p.get("product_code", ""), "name": p.get("product_name_en", ""),
                    "ar": p.get("product_name_ar", "") or "", "unit": uname,
                    "stock": f"{stock:,.0f}" if stock == int(stock) else f"{stock:,.2f}",
                    "cost": f"{cost:,.2f}", "price": f"{sp_vat:,.2f}"}
            tag = "out" if stock <= 0 else ("low" if stock <= low_lvl else "")
            tv.insert("", "end", iid=str(i), values=[vals[c] for c in cols], tags=(tag,))
        kids = tv.get_children()
        if kids:
            tv.selection_set(kids[0]); tv.focus(kids[0])
        tv.configure(height=min(10, max(3, len(kids))))
        self._search_dd.update_idletasks()
        ew = self.search_entry.winfo_width()
        w = max(ew, 1000)
        x = self.search_entry.winfo_rootx()
        sw = self.win.winfo_screenwidth()
        if x + w > sw - 8:
            x = max(8, sw - 8 - w)
        y = self.search_entry.winfo_rooty() + self.search_entry.winfo_height() + 2
        self._search_dd.geometry("%dx%d+%d+%d" % (w, self._search_dd.winfo_reqheight(), x, y))
        self._search_dd.lift()

    def _search_dd_move(self, delta):
        if self._search_dd is None or not self._search_dd.winfo_exists():
            return "break"
        tv = self._search_lb
        kids = tv.get_children()
        if not kids:
            return "break"
        cur = tv.selection()
        i = (kids.index(cur[0]) if cur else 0) + delta
        i = max(0, min(len(kids) - 1, i))
        tv.selection_set(kids[i]); tv.focus(kids[i]); tv.see(kids[i])
        return "break"

    def _close_search_dd(self):
        try:
            if self._search_dd is not None and self._search_dd.winfo_exists():
                self._search_dd.destroy()
        except Exception:
            pass
        self._search_dd = None

    def _pick_dd_index(self):
        if self._search_dd is None or not self._search_dd.winfo_exists():
            return
        cur = self._search_lb.selection()
        if not cur:
            return
        i = int(cur[0])
        if i >= len(self._search_matches):
            return
        prod = self._search_matches[i]
        self._close_search_dd()
        self.search_var.set("")
        self._pick_search_result(prod)

    def _pick_search_result(self, prod):
        units = self._units_for(prod["product_id"])
        if len(units) > 1:
            UnitPriceStockDialog(self.win, prod, units,
                                 on_pick=self._on_unit_picked)
        else:
            self._add_to_cart(prod)
            self._focus_barcode_default()

    # ── Customer search: name / phone / VAT — default Cash ────
    def _set_customer(self, cust, quiet=False):
        if cust is not getattr(self, "_customer", None):
            self._points = 0                  # points belong to the customer chosen
        self._customer = cust
        try:                                  # v6.0: prices follow the customer's list
            from modules import price_lists as PL
            new_key = PL.for_customer((cust or {}).get("customer_id"))
        except Exception:
            new_key = None
        _extra = ""
        if new_key != getattr(self, "_price_key", None):
            self._price_key = new_key
            if getattr(self, "cart", None):
                n = self._reprice_cart()
                if n:
                    _extra = "  ·  %d line(s) re-priced (%s)" % (n, PL.label_for_key(new_key))
        if cust:
            label = "%s — %s" % (cust.get("customer_code", ""),
                                 cust.get("customer_name_en", ""))
            if cust is self._default_customer or \
               str(cust.get("customer_code", "")).upper() == "CASH":
                label += "  (default)"
        else:
            label = "Cash Account"
        try:
            self.cust_label_var.set(label)
        except Exception:
            pass
        if not quiet:
            self.status_var.set("Customer: " + label + _extra)

    def _reset_customer(self):
        self.cust_search_var.set("")
        self._close_cust_dd()
        self._set_customer(self._default_customer)

    def _cust_matches_for(self, query, limit=8):
        q = query.strip().lower()
        out = []
        for c in getattr(self, "_customers", []):
            hay = " ".join([str(c.get("customer_name_en", "")),
                            str(c.get("customer_name_ar", "")),
                            str(c.get("customer_code", "")),
                            str(c.get("phone", "")),
                            str(c.get("vat_no", ""))]).lower()
            if all(tok in hay for tok in q.split()):
                out.append(c)
                if len(out) >= limit:
                    break
        return out

    def _on_cust_type(self, event=None):
        if event and event.keysym in ("Return", "Up", "Down", "Escape",
                                      "Left", "Right", "Tab"):
            return
        txt = self.cust_search_var.get().strip()
        if not txt:
            self._close_cust_dd()
            return
        self._cust_matches = self._cust_matches_for(txt)
        if not self._cust_matches:
            self._close_cust_dd()
            return
        if self._cust_dd is None or not self._cust_dd.winfo_exists():
            self._cust_dd = tk.Toplevel(self.win)
            self._cust_dd.overrideredirect(True)
            self._cust_dd.attributes("-topmost", True)
            self._cust_lb = tk.Listbox(self._cust_dd, font=("Segoe UI", 12),
                                       height=8, bg="white", fg="#1B3A4B",
                                       selectbackground="#16A085",
                                       selectforeground="white", width=52,
                                       activestyle="none", relief="solid", bd=1)
            self._cust_lb.pack(fill="both", expand=True)
            self._cust_lb.bind("<ButtonRelease-1>",
                               lambda e: self._pick_cust_index())
        lb = self._cust_lb
        lb.delete(0, "end")
        for c in self._cust_matches:
            bits = [c.get("customer_code", ""), c.get("customer_name_en", "")]
            extra = []
            if c.get("phone"):
                extra.append("📞 " + str(c["phone"]))
            if c.get("vat_no"):
                extra.append("VAT " + str(c["vat_no"]))
            lb.insert("end", " %s — %s   %s" % (bits[0], bits[1],
                                                "  ·  ".join(extra)))
        lb.selection_clear(0, "end"); lb.selection_set(0); lb.activate(0)
        x = self.cust_entry.winfo_rootx()
        y = self.cust_entry.winfo_rooty() + self.cust_entry.winfo_height() + 2
        self._cust_dd.geometry("+%d+%d" % (x, y))
        self._cust_dd.lift()

    def _cust_dd_move(self, delta):
        if self._cust_dd is None or not self._cust_dd.winfo_exists():
            return "break"
        lb = self._cust_lb
        cur = lb.curselection()
        i = max(0, min(lb.size() - 1, (cur[0] if cur else 0) + delta))
        lb.selection_clear(0, "end"); lb.selection_set(i)
        lb.activate(i); lb.see(i)
        return "break"

    def _on_cust_enter(self, event=None):
        if self._cust_dd is not None and self._cust_dd.winfo_exists():
            self._pick_cust_index()
        return "break"

    def _pick_cust_index(self):
        cur = self._cust_lb.curselection() if self._cust_dd else None
        if not cur or cur[0] >= len(self._cust_matches):
            return
        self._set_customer(self._cust_matches[cur[0]])
        self.cust_search_var.set("")
        self._close_cust_dd()
        self._focus_barcode_default()

    def _close_cust_dd(self):
        try:
            if self._cust_dd is not None and self._cust_dd.winfo_exists():
                self._cust_dd.destroy()
        except Exception:
            pass
        self._cust_dd = None

    # ── Bill # browser: ▲ ▼ load saved bills into the window ──
    def _nav_bill(self, direction):
        """▼ (direction −1) loads the previous saved bill; ▲ (+1) moves
        toward newer, and past the newest returns to a fresh NEW sale."""
        try:
            if self._loaded_invoice_id is None:
                if direction >= 0:
                    self.status_var.set("Already on a new bill.")
                    return
                row = db.fetchone(
                    "SELECT TOP 1 invoice_id FROM sales_invoices "
                    "ORDER BY invoice_id DESC")
            elif direction < 0:
                row = db.fetchone(
                    "SELECT TOP 1 invoice_id FROM sales_invoices "
                    "WHERE invoice_id < ? ORDER BY invoice_id DESC",
                    (self._loaded_invoice_id,))
            else:
                row = db.fetchone(
                    "SELECT TOP 1 invoice_id FROM sales_invoices "
                    "WHERE invoice_id > ? ORDER BY invoice_id ASC",
                    (self._loaded_invoice_id,))
                if not row:
                    self._new_sale(ask=False)
                    return
            if not row:
                self.status_var.set("No more bills in that direction.")
                return
            self._load_bill(row["invoice_id"])
        except Exception as e:
            messagebox.showerror("Browse Bills", str(e)[:300])

    def _load_bill(self, invoice_id):
        """Pull a saved bill into the cart: view it, edit lines and Save
        to UPDATE it, Delete Bill to remove it, 🖨 to print it."""
        inv = db.fetchone("SELECT * FROM sales_invoices WHERE invoice_id=?",
                          (invoice_id,))
        if not inv:
            return
        lines = db.fetchall(
            "SELECT * FROM sales_invoice_lines WHERE invoice_id=? "
            "ORDER BY line_number", (invoice_id,)) or []
        self.cart = []
        for l in lines:
            ln = {"product_id": l.get("product_id"),
                  "product_code": l.get("product_code", ""),
                  "product_name_en": l.get("product_name_en", ""),
                  "product_name_ar": l.get("product_name_ar", ""),
                  "unit_name": l.get("unit_of_measure_en", "Unit"),
                  "factor": 1.0,
                  "unit_price": float(l.get("unit_price", 0) or 0),
                  "quantity": float(l.get("quantity", 0) or 0),
                  "vat_rate": float(l.get("vat_rate", 0) or 0),
                  "vat_code": l.get("vat_category_code", "S"),
                  "vat_category_id": l.get("vat_category_id")}
            # a saved bill keeps the offer it was sold with (until its qty changes)
            ln.update(discount_amount=float(l.get("discount_amount") or 0),
                      offer_id=l.get("offer_id"), offer_text=l.get("offer_text") or "",
                      offer_off=True, _frozen_qty=ln["quantity"])
            self._recalc(ln)
            self.cart.append(ln)
        self._sel_idx = None
        self._loaded_invoice_id = invoice_id
        # ⭐ points this bill spent are inside its lines and stay spent (v6.9.2)
        self._loaded_points = int(float(inv.get("loyalty_points_redeemed") or 0))
        self.bill_var.set(str(inv.get("invoice_number", invoice_id)))
        # reflect the bill's customer in the header
        cust = next((c for c in getattr(self, "_customers", [])
                     if c["customer_id"] == inv.get("customer_id")), None)
        if cust:
            self._set_customer(cust, quiet=True)
        self.paid_var.set("{:,.2f}".format(float(inv.get("paid_amount", 0) or 0)))
        try:    # remember a part-cash / part-card split for re-saving
            c_, k_ = float(inv.get("cash_paid") or 0), float(inv.get("card_paid") or 0)
            self._loaded_split = (c_, k_) if (c_ > 0 and k_ > 0) else None
            from modules import tenders as _td            # v6.0: STC Pay, Tabby …
            _rows = _td.lines_for("sales", invoice_id)
            _ext = {r["method"]: float(r["amount"] or 0) for r in _rows
                    if r["method"] not in ("cash", "card")}
            if _ext:
                _cash = sum(float(r["amount"] or 0) for r in _rows if r["method"] == "cash")
                _card = sum(float(r["amount"] or 0) for r in _rows if r["method"] == "card")
                self._loaded_split = (_cash, _card, _ext)
        except Exception:
            self._loaded_split = None
        self._render_cart()
        self.status_var.set(
            "Loaded %s (%s) — edit lines then Save to update, "
            "Delete Bill to remove, 🖨 to print." % (
                inv.get("invoice_number", ""), inv.get("invoice_status", "")))

    def _print_loaded(self):
        """🖨: print the loaded bill, or the previous (last saved) bill."""
        from modules import permissions as _pm
        if not _pm.allowed("pos", "print"):
            return False
        if self._loaded_invoice_id:
            self._print(self._loaded_invoice_id)
            return
        from modules import doc_print as DP
        prev = DP.last_id("pos")
        if prev:
            self._print(prev)
        else:
            self.status_var.set("No saved bill yet.")

    def _best_match(self, query):
        if filter_products:
            res = filter_products(query, self.products)
            return res[0] if res else None
        q = query.lower()
        for p in self.products:
            if q in (p.get("product_name_en", "") or "").lower() or \
               q in (p.get("product_code", "") or "").lower():
                return p
        return None

    def _resolve_barcode(self, code):
        """Scanned code → (product, unit_id): the ONE shared resolver
        (unit barcode → extra barcode → product barcode → code)."""
        try:
            from modules.barcode_resolver import resolve
            hit = resolve(code, scale=False, products=self.products)
            if hit:
                prod = next((p for p in self.products
                             if p["product_id"] == hit["product_id"]), None)
                if prod:
                    return prod, hit["unit_id"]
                return None
        except Exception:
            pass
        try:
            row = db.fetchone(
                "SELECT product_id, unit_id FROM product_unit_barcodes "
                "WHERE barcode=? AND is_active=1", (code,))
            if row:
                prod = next((p for p in self.products
                             if p["product_id"] == row["product_id"]), None)
                if prod:
                    return prod, row["unit_id"]
        except Exception:
            pass
        try:
            row = db.fetchone(
                "SELECT product_id, unit_id FROM product_units WHERE barcode=?", (code,))
            if row:
                prod = next((p for p in self.products
                             if p["product_id"] == row["product_id"]), None)
                if prod:
                    return prod, row["unit_id"]
        except Exception:
            pass
        prod = next((p for p in self.products if (p.get("barcode") or "") == code), None)
        if prod:
            return prod, None
        return None

    # -- Cart operations ---------------------------------------
    def _units_for(self, product_id):
        return self._units.get(product_id, [])

    def _add_to_cart(self, p, unit_id=None):
        if getattr(self, "_minus", False):          # '−' then scan / tap / search
            self._set_minus(False)
            return self._minus_item(p, unit_id)
        units = self._units_for(p["product_id"])
        unit_name, factor, price = "Unit", 1.0, float(p["unit_price"])
        chosen = None
        if units:
            if unit_id:
                chosen = next((u for u in units if u["unit_id"] == unit_id), None)
            if not chosen:
                chosen = next((u for u in units if u.get("is_default")), units[0])
        if chosen:
            unit_name = chosen["unit_name_en"]
            factor = float(chosen.get("conversion_factor", 1) or 1)
            price = float(chosen.get("selling_price") or 0) or \
                    float(p["unit_price"]) * factor
        base_price = price
        price = self._list_price(p["product_id"], unit_name, factor, price)

        for ln in self.cart:
            if ln["product_id"] == p["product_id"] and ln["unit_name"] == unit_name \
                    and ln["quantity"] > 0:
                ln["quantity"] += 1
                self._recalc(ln)
                self._render_cart(select_line=ln)
                self.status_var.set("+ %s -> qty %g" % (p["product_name_en"], ln["quantity"]))
                self._offer_hint(ln)
                return

        ln = {"product_id": p["product_id"],
              "product_code": p.get("product_code", ""),
              "product_name_en": p.get("product_name_en", ""),
              "product_name_ar": p.get("product_name_ar", ""),
              "unit_name": unit_name, "factor": factor,
              "unit_price": price, "quantity": 1, "_base_price": base_price,
              "vat_rate": float(p["vat_rate"]), "vat_code": p.get("vat_code", "S"),
              "vat_category_id": p.get("vat_category_id")}
        self._recalc(ln)
        self.cart.append(ln)
        self._render_cart(select_line=ln)
        self.status_var.set("+ Added %s (%s)" % (p["product_name_en"], unit_name)
                            + (("   🏷 " + ln["offer_text"]) if ln.get("offer_text") else ""))
        self._offer_hint(ln)

    # -- '−' : take off this bill, or a RETURN line ------------------
    def _set_minus(self, on):
        """'−' mode: the NEXT product scanned / tapped / searched is taken
        off the bill (if it is on it) or added as a RETURN (money back)."""
        self._minus = bool(on)
        try:
            self.minus_btn.configure(
                bg="#C0392B" if on else "#8E44AD",
                text="↩ RETURN ON — scan item" if on else "↩ Return (−)")
        except Exception:
            pass
        if on:
            self.status_var.set("−  Scan / tap the product to take it off the bill or "
                                "RETURN it (Esc = cancel).")

    def _toggle_minus(self):
        self._set_minus(not getattr(self, "_minus", False))
        try:
            self.barcode_entry.focus_set()
        except Exception:
            pass

    def _unit_for(self, p, unit_id=None):
        units = self._units_for(p["product_id"])
        unit_name, factor, price = "Unit", 1.0, float(p["unit_price"])
        chosen = None
        if units:
            if unit_id:
                chosen = next((u for u in units if u["unit_id"] == unit_id), None)
            if not chosen:
                chosen = next((u for u in units if u.get("is_default")), units[0])
        if chosen:
            unit_name = chosen["unit_name_en"]
            factor = float(chosen.get("conversion_factor", 1) or 1)
            price = float(chosen.get("selling_price") or 0) or float(p["unit_price"]) * factor
        return unit_name, factor, self._list_price(p["product_id"], unit_name, factor, price)

    # ── v6.0: the customer's price list ───────────────────────
    def _list_price(self, product_id, unit_name, factor, price):
        key = getattr(self, "_price_key", None)
        if key is None:
            return price
        try:
            from modules import price_lists as PL
            return round(float(PL.price_for(key, product_id, unit_name, price, factor)), 4)
        except Exception:
            return price

    def _reprice_cart(self):
        n = 0
        for ln in self.cart:
            if ln.get("_price_typed") or ln.get("quantity", 0) < 0 or "_base_price" not in ln:
                continue
            new = self._list_price(ln["product_id"], ln.get("unit_name"), ln.get("factor", 1),
                                   ln["_base_price"])
            if abs(new - float(ln["unit_price"])) > 1e-6:
                ln["unit_price"] = new
                self._recalc(ln)
                n += 1
        if n:
            self._render_cart()
        return n

    def _minus_item(self, p, unit_id=None, qty=1.0, price=None):
        """1) the product is on this bill → take `qty` off (line goes at 0);
        2) not on the bill → a RETURN line (negative qty, money back)."""
        pid = p["product_id"]
        unit_name, factor, uprice = self._unit_for(p, unit_id)
        on_bill = [l for l in self.cart if l["product_id"] == pid and l["quantity"] > 0]
        if on_bill:
            ln = next((l for l in reversed(on_bill) if l["unit_name"] == unit_name),
                      on_bill[-1])
            if ln["quantity"] <= qty + 1e-9:
                self.cart.remove(ln)
                self._sel_idx = None
                self._render_cart()
            else:
                ln["quantity"] = round(ln["quantity"] - qty, 3)
                self._recalc(ln)
                self._render_cart(select_line=ln)
            self.status_var.set("−  %s: %g taken off the bill" % (p.get("product_name_en", ""), qty))
            return
        # ── a return (customer brings back an item bought before) ──
        if self._loaded_invoice_id:
            messagebox.showwarning("Return", "A return can't be added to a saved bill.\n"
                                   "Press New [F3], then scan the returned item.",
                                   parent=self.win)
            return
        from modules import permissions as _pm
        if not _pm.allowed("sales_return", "add", parent=self.win):
            return
        ln = next((l for l in self.cart if l["product_id"] == pid and l["quantity"] < 0
                   and l["unit_name"] == unit_name and price is None), None)
        if ln:
            ln["quantity"] = round(ln["quantity"] - qty, 3)
        else:
            ln = {"product_id": pid, "product_code": p.get("product_code", ""),
                  "product_name_en": p.get("product_name_en", ""),
                  "product_name_ar": p.get("product_name_ar", ""),
                  "unit_name": unit_name, "factor": factor,
                  "unit_price": uprice if price is None else float(price),
                  "quantity": -float(qty),
                  "vat_rate": float(p["vat_rate"]), "vat_code": p.get("vat_code", "S"),
                  "vat_category_id": p.get("vat_category_id")}
            self.cart.append(ln)
        self._recalc(ln)
        self._render_cart(select_line=ln)
        self.status_var.set("↩  RETURN %s  %g %s  (money back %s)" % (
            p.get("product_name_en", ""), -ln["quantity"], unit_name,
            "{:,.2f}".format(-ln["line_total"])))

    def _recalc(self, ln):
        rate = ln["vat_rate"]
        try:  # Settings ▸ Tax: global switch + Apply VAT On POS Invoice
            from config import settings as _cfg
            if not _cfg.flag("vat_enabled", True) or not _cfg.flag("apply_vat_pos", True):
                rate = 0.0
        except Exception:
            pass
        incl = False
        try:
            incl = bool(self.incl_vat_var.get())
        except Exception:
            incl = _price_incl()
        # Offers & promotions (−20 %, half price, buy 1 get 1 …) → line discount
        if ln.get("_frozen_qty") is not None and abs(ln["quantity"] - ln["_frozen_qty"]) > 1e-9:
            ln.update(offer_off=False, _frozen_qty=None)   # qty changed → today's offers
        try:
            from modules import offers as _offers
            _offers.apply_to_line(ln, "pos", unit_key="unit_name", line_incl=incl, rate=rate)
        except Exception:
            pass
        gross_line = ln["quantity"] * ln["unit_price"] - float(ln.get("discount_amount") or 0)
        if incl and rate:
            # Rate already contains VAT -> split it back out
            taxable = gross_line / (1 + rate / 100.0)
            ln["taxable"] = taxable
            ln["vat_amount"] = gross_line - taxable
            ln["line_total"] = gross_line
        else:
            ln["taxable"] = gross_line
            ln["vat_amount"] = gross_line * rate / 100.0
            ln["line_total"] = gross_line + ln["vat_amount"]

    def _render_cart(self, select_pid=None, select_unit=None, select_line=None):
        self.tree.delete(*self.tree.get_children())
        sel_iid = None
        for idx, ln in enumerate(self.cart):
            iid = str(idx)
            ret = ln["quantity"] < 0
            tags = ("ret",) if ret else (("offer",) if ln.get("offer_text") else ())
            self.tree.insert("", "end", iid=iid, values=(
                idx + 1, ln["product_code"],
                ("↩ RETURN  " if ret else "") + ln["product_name_en"]
                + (("   🏷 " + ln["offer_text"]) if ln.get("offer_text") else ""),
                ln.get("product_name_ar", "") or "",
                "%g" % ln["quantity"], ln["unit_name"],
                "{:,.2f}".format(ln["unit_price"]),
                "{:,.2f}".format(ln.get("vat_amount", 0) or 0),
                "{:,.2f}".format(ln["line_total"]), "✕"),
                tags=tags)
            if select_line is not None:
                if ln is select_line:
                    sel_iid = iid
            elif select_pid and ln["product_id"] == select_pid and \
                    (select_unit is None or ln["unit_name"] == select_unit):
                sel_iid = iid
        if sel_iid:
            self.tree.selection_set(sel_iid)
            self.tree.see(sel_iid)
            self._sel_idx = int(sel_iid)
        self._update_totals()

    def _on_tree_click(self, event):
        """Click on the ✕ cell of a line removes that line."""
        try:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            row = self.tree.identify_row(event.y)
            col = self.tree.identify_column(event.x)
            shown = list(self.tree["displaycolumns"])
            if shown == ["#all"]:
                shown = list(self.tree["columns"])
            key = shown[int(col.replace("#", "")) - 1]
        except Exception:
            return
        if key == "del" and row:
            self._remove_line(int(row))
            return "break"

    def _remove_line(self, idx):
        if not (0 <= idx < len(self.cart)):
            return
        ln = self.cart.pop(idx)
        self._sel_idx = None
        self._render_cart()
        self.status_var.set("✕ Removed %s from the bill." % ln.get("product_name_en", ""))
        try:                                       # v6.4 cashier watch
            from modules import cashier_watch as _cw
            _cw.log_void("line", [ln])
        except Exception:
            pass
        try:
            self.barcode_entry.focus_set()
        except Exception:
            pass

    def _on_tree_select(self, event=None):
        sel = self.tree.selection()
        self._sel_idx = int(sel[0]) if sel else None

    def _ctrl_box(self):
        """Box shown while Ctrl is held: units, box qty, purchase price,
        profit and stock of the selected bill line."""
        idx = self._sel_idx
        if idx is None or not (0 <= idx < len(self.cart)):
            if not self.cart:
                return None
            idx = len(self.cart) - 1
        pid = self.cart[idx]["product_id"]
        prod = next((p for p in self.products if p["product_id"] == pid), None)
        if not prod:
            return None
        from ui.product_boxes import UnitProfitBox
        return UnitProfitBox(self.win, prod, self._units_for(pid), cfg.theme(), hold=True)

    def _show_product_details(self, event=None):
        """Kept for old callers: show the Ctrl box (closes on Ctrl release)."""
        return self._ctrl_box()

    def _bump(self, delta):
        if self._sel_idx is None or not (0 <= self._sel_idx < len(self.cart)):
            self.status_var.set("Select a line first."); return
        ln = self.cart[self._sel_idx]
        sign = -1 if ln["quantity"] < 0 else 1          # a RETURN line counts down
        mag = abs(ln["quantity"]) + delta
        if mag <= 1e-9:
            del self.cart[self._sel_idx]
            self._sel_idx = None
            self._render_cart()
        else:
            ln["quantity"] = sign * mag
            self._recalc(ln)
            self._render_cart(select_line=ln)
            if sign > 0:
                self._offer_hint(ln)

    def _remove_selected(self):
        if self._sel_idx is None or not (0 <= self._sel_idx < len(self.cart)):
            self.status_var.set("Select a line to remove."); return
        self._remove_line(self._sel_idx)

    def _space_cycle_unit(self, event=None):
        w = self.win.focus_get()
        if isinstance(w, tk.Entry):
            return
        if self._sel_idx is None or not (0 <= self._sel_idx < len(self.cart)):
            return "break"
        ln = self.cart[self._sel_idx]
        units = self._units_for(ln["product_id"])
        if len(units) < 2:
            self.status_var.set("This product has only one unit.")
            return "break"
        names = [u["unit_name_en"] for u in units]
        try:
            i = names.index(ln["unit_name"])
        except ValueError:
            i = -1
        nxt = units[(i + 1) % len(units)]
        ln["unit_name"] = nxt["unit_name_en"]
        ln["factor"] = float(nxt.get("conversion_factor", 1) or 1)
        ln["unit_price"] = float(nxt.get("selling_price") or 0) or ln["unit_price"]
        self._recalc(ln)
        self._render_cart(select_line=ln)
        self.status_var.set("Unit -> %s  @ %s" % (ln["unit_name"],
                            "{:,.2f}".format(ln["unit_price"])))
        return "break"

    def _bill_parts(self):
        """Sale lines, RETURN lines (negative qty) and their totals.
        net = what the customer pays (negative = money back)."""
        sale = [l for l in self.cart if l["quantity"] > 0]
        rets = [l for l in self.cart if l["quantity"] < 0]
        s_gross = sum(l["taxable"] for l in sale)
        s_vat = sum(l["vat_amount"] for l in sale)
        pv = self._points_value() if sale else 0.0      # ⭐ points off (v6.9.2)
        s_total = s_gross + s_vat - pv
        if sale:
            try:  # Settings ▸ Tax: automatic round-off (same helper as invoices)
                s_total, _adj = cfg.round_off(s_total)
            except Exception:
                pass
        r_gross = -sum(l["taxable"] for l in rets)
        r_vat = -sum(l["vat_amount"] for l in rets)
        r_total = round(r_gross + r_vat, 2)
        s_total = round(s_total, 2)
        # v6.9.2: VAT the ZATCA way (once per rate on the bill, after the
        # round-off is spread) — the same VAT the saved bill and its QR carry
        try:
            from modules.doc_math import doc_totals, spread_bill_adjustment
            if sale:
                L = [dict(l, line_amount=l["taxable"]) for l in sale]
                adj = round(round(sum(l["line_total"] for l in sale), 2) - s_total, 2)
                if 0.005 <= abs(adj) <= 1.0 + pv:
                    L = spread_bill_adjustment(L, adj, _price_incl())
                s_vat = doc_totals(L, _price_incl(), code="vat_code")["vat"]
                s_gross = round(s_total - s_vat, 2)
            if rets:
                r_vat = -doc_totals([dict(l, line_amount=l["taxable"]) for l in rets],
                                    _price_incl(), code="vat_code")["vat"]
                r_gross = round(r_total - r_vat, 2)
        except Exception:
            pass
        return {"sale": sale, "rets": rets, "s_gross": s_gross, "s_vat": s_vat,
                "s_total": s_total, "r_gross": r_gross, "r_vat": r_vat,
                "r_total": r_total, "net": round(s_total - r_total, 2)}

    # -- ⭐ loyalty points (v6.9.2) -----------------------------
    def _points_value(self):
        """SAR off this bill for the points the cashier chose (sale only)."""
        pts = int(getattr(self, "_points", 0) or 0)
        if pts <= 0 or any(l["quantity"] < 0 for l in self.cart):
            return 0.0
        try:
            from modules import loyalty
            return loyalty.value_of(pts) if loyalty.enabled() else 0.0
        except Exception:
            return 0.0

    def _use_points(self):
        """F10 — spend the customer's points on this bill."""
        try:
            from modules import loyalty
        except Exception:
            return
        if not loyalty.enabled():
            self.status_var.set("Loyalty points are off (Settings ▸ Customer).")
            return
        sale = [l for l in self.cart if l["quantity"] > 0]
        if not sale or len(sale) != len(self.cart):
            self.status_var.set("⭐ Points: a sale bill only (no return lines).")
            return
        cust = getattr(self, "_customer", None)
        if loyalty.is_walk_in(cust):
            self.status_var.set("⭐ Points: pick the customer first.")
            return
        self._points = 0
        before = round(sum(l["line_total"] for l in sale), 2)
        have = loyalty.balance(cust["customer_id"])
        most = loyalty.can_spend(cust["customer_id"], before)
        if most <= 0:
            self.status_var.set("⭐ %s has %d points (at least %d are needed)."
                                % (cust.get("customer_name_en", ""), have, loyalty.min_redeem()))
            self._update_totals()
            return
        from tkinter import simpledialog
        n = simpledialog.askinteger(
            "⭐ Loyalty points",
            "%s has %d points (1 point = %.2f SAR).\nPoints to spend on this bill (up to %d):"
            % (cust.get("customer_name_en", ""), have, loyalty.point_value(), most),
            parent=self.win, initialvalue=most, minvalue=0, maxvalue=most)
        if n and n >= loyalty.min_redeem():
            self._points = int(n)
            self.status_var.set("⭐ %d points = %.2f SAR off" % (n, loyalty.value_of(n)))
        elif n:
            self.status_var.set("⭐ At least %d points." % loyalty.min_redeem())
        self._update_totals()

    def _update_totals(self):
        if not self.cart:
            self._points = 0                  # a new bill starts without points
        P = self._bill_parts()
        tqty = sum(ln["quantity"] for ln in self.cart)
        gross = P["s_gross"] - P["r_gross"]
        vat = P["s_vat"] - P["r_vat"]
        total = P["net"]
        self.tqty_var.set("%g" % tqty)
        try:
            txt = "%d line%s · %g qty" % (len(self.cart), "" if len(self.cart) == 1 else "s", tqty)
            if P["rets"]:
                txt += "  ·  ↩ return %s" % "{:,.2f}".format(P["r_total"])
            saved = self._offer_savings()
            if saved > 0.004:
                txt += "  ·  🏷 saved %s" % "{:,.2f}".format(saved)
            self.lines_var.set(txt)
        except Exception:
            pass
        self.gross_var.set("{:,.2f}".format(gross))
        try:            # offers & promotions + ⭐ points on this bill
            self.disc_var.set("{:,.2f}".format(self._offer_savings() + self._points_value()))
        except Exception:
            pass
        self.tax_var.set("{:,.2f}".format(vat))
        self.total_var.set("{:,.2f}".format(total))
        try:
            refund = total < -0.004
            self.total_cap_var.set("REFUND TO CUSTOMER (SAR)" if refund else
                                   ("TOTAL after return (SAR)" if P["rets"] else "TOTAL (SAR)"))
            self.total_lbl.configure(fg="#FF7675" if refund else "#2ECC71")
        except Exception:
            pass
        self._update_change()

    def _offer_savings(self):
        """What the offers save the customer on this bill (sale lines)."""
        return sum(float(l.get("discount_amount") or 0) for l in self.cart
                   if l["quantity"] > 0 and l.get("offer_id"))

    def _offer_hint(self, ln):
        """Status bar: 'BUY 1 GET 1 FREE — add 1 more, it is FREE'."""
        try:
            from modules import offers as _offers
            h = _offers.hint(ln["product_id"], ln["unit_name"], ln["quantity"], "pos")
            if h:
                self.status_var.set(h)
        except Exception:
            pass

    def _update_change(self):
        if not hasattr(self, "paid_var"):
            return
        def num(v):
            try:
                return float(str(v).replace(",", "") or 0)
            except Exception:
                return 0.0
        total = num(self.total_var.get())
        paid = num(self.paid_var.get())
        if total < 0:                       # money back to the customer
            self.balance_var.set("0.00")
            self.change_var.set("{:,.2f}".format(-total))
            return
        diff = paid - total
        if diff >= 0:
            self.change_var.set("{:,.2f}".format(diff))
            self.balance_var.set("0.00")
        else:
            self.change_var.set("0.00")
            self.balance_var.set("{:,.2f}".format(-diff))
        try:
            self._balance_lbl.configure(fg="#FF7675" if diff < -0.005 and paid > 0
                                        else "white")
        except Exception:
            pass

    # -- Number pad --------------------------------------------
    def _set_pad(self, target, quiet=False):
        """Qty / Rate keys. Works both ways:
           • Qty, then the number, then Enter
           • the number, then Qty (applied at once)."""
        if target == "rate" and not cfg.flag("allow_price_edit", True):
            self.status_var.set("Price editing is turned off (Settings ▸ Sales).")
            try: self.win.bell()
            except Exception: pass
            target = "qty"
        pending = getattr(self, "_pad_buffer", "")
        if pending and target in ("qty", "rate") and not quiet \
                and getattr(self, "_pad_target", "qty") != "paid":
            # number typed first, then the function key → apply it now
            self._pad_target = target
            self._pad_enter()
            return
        self._pad_target = target
        self._pad_buffer = ""
        self._pad_show()
        try:
            self._paid_tile.configure(bg="#FFF3C4" if target == "paid" else "#EAF4FA")
        except Exception:
            pass
        if not quiet:
            self.status_var.set("Number pad -> %s." % (
                "PAID amount" if target == "paid" else
                "type the new %s of the selected line, then Enter" % target.upper()))

    def _pad_show(self):
        """Light the active key and show what is typed on it."""
        t, buf = getattr(self, "_pad_target", "qty"), getattr(self, "_pad_buffer", "")
        try:
            self.qty_btn.configure(bg="#E67E22" if t == "qty" else "#95A5A6",
                                   text="Qty\n" + buf if (t == "qty" and buf) else "Qty")
            self.rate_btn.configure(bg="#E67E22" if t == "rate" else "#95A5A6",
                                    text="Rate\n" + buf if (t == "rate" and buf) else "Rate")
        except Exception:
            pass

    def _pad_line(self):
        """The line the keypad works on: the selected one, else the last."""
        if self._sel_idx is not None and 0 <= self._sel_idx < len(self.cart):
            return self._sel_idx
        if self.cart:
            self._sel_idx = len(self.cart) - 1
            return self._sel_idx
        return None

    def _pad_press(self, v):
        if self._pad_target != "paid" and self._pad_line() is None:
            self.status_var.set("Add a product first, then type its Qty or Rate.")
            return
        if v == "<":
            self._pad_buffer = self._pad_buffer[:-1]
        elif v == "." and "." in self._pad_buffer:
            return
        elif len(self._pad_buffer) >= 9:
            return
        else:
            self._pad_buffer += v
        if self._pad_target == "paid":
            self.paid_var.set(self._pad_buffer or "0.00")
        self._pad_show()
        self.status_var.set("%s = %s   (Enter to apply)" % (self._pad_target.upper(),
                                                           self._pad_buffer))

    def _pad_clear(self):
        """Clear: what you typed; pressed again (nothing typed) → back to Qty."""
        if not self._pad_buffer and self._pad_target != "qty":
            if self._pad_target == "paid":
                self.paid_var.set("0.00")
            self._set_pad("qty", quiet=True)
            self.status_var.set("Keypad back to Qty.")
            return
        self._pad_buffer = ""
        if self._pad_target == "paid":
            self.paid_var.set("0.00")
        self._pad_show()
        self.status_var.set("Cleared.")

    def _pad_enter(self):
        if self._pad_target == "paid":
            try:
                v = float(self._pad_buffer or self.paid_var.get().replace(",", "") or 0)
            except ValueError:
                self.status_var.set("Invalid number."); return
            self.paid_var.set("{:,.2f}".format(v))
            self._pad_buffer = ""
            return
        idx = self._pad_line()
        if idx is None or self._pad_buffer in ("", "."):
            return
        try:
            val = float(self._pad_buffer)
        except ValueError:
            self.status_var.set("Invalid number."); return
        ln = self.cart[idx]
        if self._pad_target == "qty":
            if val <= 0:
                self.status_var.set("Quantity must be more than 0 (use ✕ / Remove line).")
                self._pad_buffer = ""; self._pad_show()
                return
            ln["quantity"] = -val if ln["quantity"] < 0 else val   # a RETURN stays a return
            msg = "Qty -> %g" % val
        else:
            ln["unit_price"] = val
            ln.update(offer_off=True, discount_amount=0.0, offer_id=None, offer_text="")  # price typed by the cashier
            msg = "Rate -> %s" % "{:,.2f}".format(val)
        self._recalc(ln)
        self._pad_buffer = ""
        self._render_cart(select_line=ln)
        self._set_pad("qty", quiet=True)          # back to Qty after every change
        self.status_var.set("%s   (%s)" % (msg, ln.get("product_name_en", "")))

    # -- Hold / Retrieve ---------------------------------------
    def _hold(self):
        from modules import permissions as _pm
        if not _pm.allowed("pos", "add"):
            return False
        try:  # Settings ▸ POS: Enable Hold Bills
            from config import settings as _cfg
            if not _cfg.flag("pos_enable_hold", True):
                self.status_var.set("Hold is disabled in Settings ▸ POS.")
                return
        except Exception:
            pass
        if not self.cart:
            self.status_var.set("Nothing to hold."); return
        label = datetime.now().strftime("%H:%M:%S")
        self._held.append((label, [dict(x) for x in self.cart]))
        self.cart = []
        self._sel_idx = None
        self._render_cart()
        self._update_held_badge()
        self.status_var.set("Sale held (%s). %d on hold. Press Retrieve [F7]."
                            % (label, len(self._held)))
        self.barcode_entry.focus_set()

    def _update_held_badge(self):
        n = len(self._held)
        try:
            self.retrieve_lbl.configure(text="Retrieve" + (" (%d)" % n if n else "") + "\n[F7]")
        except Exception:
            pass

    def _retrieve(self):
        if not self._held:
            self.status_var.set("No held sales."); return
        d = tk.Toplevel(self.win); d.title("Retrieve Held Sale")
        d.geometry("340x380"); d.configure(bg="white"); d.grab_set()
        tk.Label(d, text="Held Sales", font=("Segoe UI", 13, "bold"),
                 bg="#1B3A4B", fg="white", pady=10).pack(fill="x")
        lb = tk.Listbox(d, font=("Segoe UI", 11))
        lb.pack(fill="both", expand=True, padx=12, pady=10)
        for lbl, items in self._held:
            tot = sum(x["line_total"] for x in items)
            lb.insert("end", "%s  -  %d items  -  %s SAR"
                      % (lbl, len(items), "{:,.2f}".format(tot)))

        def do_get():
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            if self.cart:
                self._held.append((datetime.now().strftime("%H:%M:%S"),
                                   [dict(x) for x in self.cart]))
            _, items = self._held.pop(i)
            self.cart = items
            self._sel_idx = None
            self._render_cart()
            self._update_held_badge()
            d.destroy()
            self.status_var.set("Held sale retrieved.")
            self.barcode_entry.focus_set()

        tk.Button(d, text="Retrieve", font=("Segoe UI", 11, "bold"),
                  bg="#27AE60", fg="white", relief="flat", pady=8,
                  cursor="hand2", command=do_get).pack(fill="x", padx=12, pady=(0, 12))

    # -- New / Delete ------------------------------------------
    def _new_sale(self, ask=True):
        if ask and self.cart and self._loaded_invoice_id is None and \
                not messagebox.askyesno("New Sale",
            "Start a new sale? Current items will be cleared (use Hold to keep them)."):
            return
        if ask and self.cart and self._loaded_invoice_id is None:
            try:                                   # v6.4 cashier watch: an unpaid bill cleared
                from modules import cashier_watch as _cw
                _cw.log_void("clear", list(self.cart))
            except Exception:
                pass
        self.cart = []
        self._sel_idx = None
        self._loaded_invoice_id = None
        self._loaded_split = None
        self.bill_var.set("NEW")
        self.paid_var.set("0.00")
        # every new sale starts on the default Cash account
        self._reset_customer()
        self._render_cart()
        self.barcode_var.set("")
        self.barcode_entry.focus_set()
        self.status_var.set("New sale — customer: Cash (default).")

    def _delete_bill(self):
        from modules import permissions as _pm
        if not _pm.allowed("pos", "delete"):
            return False
        """Delete Bill — if a saved bill is loaded (via ▲▼), it is
        deleted from the database (lines + posted journals + audit),
        with an extra warning for confirmed bills. Otherwise it just
        clears the unsaved cart."""
        if self._loaded_invoice_id:
            inv = db.fetchone(
                "SELECT invoice_number, invoice_status FROM sales_invoices "
                "WHERE invoice_id=?", (self._loaded_invoice_id,))
            if not inv:
                self._new_sale(ask=False)
                return
            try:
                from modules import doc_edit as _de
                why = _de.block_reason("sales", self._loaded_invoice_id, "delete")
            except Exception:
                why = ""
            if why:
                messagebox.showwarning("Delete Bill", why, parent=self.win)
                return
            status = (inv.get("invoice_status") or "").lower()
            warn = "Permanently delete bill %s?" % inv["invoice_number"]
            if status == "confirmed":
                warn = ("Bill %s is CONFIRMED — deleting removes its "
                        "posted journal entries and affects reports.\n\n"
                        "Delete anyway?" % inv["invoice_number"])
            if not messagebox.askyesno("Delete Bill", warn):
                return
            try:
                from modules.doc_actions import remove_document_effects, audit
                remove_document_effects("sales", self._loaded_invoice_id)
                db.execute("DELETE FROM sales_invoice_lines WHERE invoice_id=?",
                           (self._loaded_invoice_id,))
                db.execute("DELETE FROM sales_invoices WHERE invoice_id=?",
                           (self._loaded_invoice_id,))
                audit("delete", "sales_invoice", self._loaded_invoice_id,
                      inv["invoice_number"])
                self.status_var.set("Deleted bill %s." % inv["invoice_number"])
            except Exception as e:
                messagebox.showerror("Delete Bill", str(e)[:300])
                return
            self._new_sale(ask=False)
            return
        if not self.cart:
            return
        if messagebox.askyesno("Delete Bill", "Clear all items from this bill?"):
            try:                                   # v6.4 cashier watch
                from modules import cashier_watch as _cw
                _cw.log_void("clear", list(self.cart))
            except Exception:
                pass
            self.cart = []
            self._sel_idx = None
            self._render_cart()
            self.status_var.set("Bill cleared.")

    # -- Save / Checkout ---------------------------------------
    def _save(self, pay="cash", do_print=False, tenders=None):
        """tenders = (cash, card) from the Cash + Card window: the bill is
        paid in part cash, part card (any remainder goes on the customer's
        account). Without it: one tender, as before."""
        from modules import permissions as _pm
        if not _pm.allowed("pos", "edit" if self._loaded_invoice_id else "add"):
            return False
        if self._loaded_invoice_id:
            try:
                from modules import doc_edit as _de
                why = _de.block_reason("sales", self._loaded_invoice_id, "edit")
            except Exception:
                why = ""
            if why:
                messagebox.showwarning("Save", why, parent=self.win)
                return
        if not self._shift_ok():
            return
        if tenders is not None:
            _c, _k = float(tenders[0] or 0), float(tenders[1] or 0)
            if _k > 0.004 and not cfg.payment_enabled("card"):
                self.status_var.set("Card payments are turned off (Settings ▸ Payment).")
                return
            if _c > 0.004 and not cfg.payment_enabled("cash"):
                self.status_var.set("Cash payments are turned off (Settings ▸ Payment).")
                return
        elif not cfg.payment_enabled(pay):
            self.status_var.set("%s payments are turned off (Settings ▸ Payment)." % pay.title())
            try: self.win.bell()
            except Exception: pass
            return
        # Settings ▸ POS: turning Auto Print off suppresses printing
        do_print = do_print and cfg.flag("pos_auto_print", True)
        if not self.cart:
            self._empty_bill_msg()
            return
        if any(ln["quantity"] < 0 for ln in self.cart):
            return self._save_exchange(pay, do_print, tenders)
        gross = sum(ln["taxable"] for ln in self.cart)
        vat = sum(ln["vat_amount"] for ln in self.cart)
        _pv = self._points_value()                      # ⭐ points off (v6.9.2)
        total = gross + vat - _pv
        try:  # Settings ▸ Tax: same round-off as the live display
            from config import settings as _cfg
            total, _adj = _cfg.round_off(total)
        except Exception:
            pass
        self._pending_offline = None      # only THIS bill may be kept offline (never an older one)
        try:
            # who is this bill for? — selected customer, default Cash
            cust = getattr(self, "_customer", None)
            cust_id = cust["customer_id"] if cust else self._walkin_id
            cust_en = (cust or {}).get("customer_name_en", "Walk-in Customer")
            cust_ar = (cust or {}).get("customer_name_ar", "") or cust_en

            # Credit sale is unpaid (goes on the party's account); every
            # other tender is settled in full at the till.
            from modules import tenders as _td
            cash_amt = card_amt = 0.0
            tender_lines = None
            if tenders is not None:
                ext = dict(tenders[2]) if len(tenders) > 2 and tenders[2] else {}
                ext_tot = round(sum(max(float(v or 0), 0.0) for v in ext.values()), 2)
                card_amt = round(min(max(float(tenders[1] or 0), 0.0), max(0.0, total - ext_tot)), 2)
                cash_amt = round(min(max(float(tenders[0] or 0), 0.0),
                                     max(0.0, total - card_amt - ext_tot)), 2)
                rest = round(total - cash_amt - card_amt - ext_tot, 2)
                tender_lines = _td.clean([("cash", cash_amt), ("card", card_amt)] + list(ext.items()))
                pay = _td.method_name(tender_lines)        # cash / card / stc_pay … / mixed / credit
                card_amt = round(card_amt + ext_tot, 2)    # card_paid = everything not cash
                is_credit = rest > 0.005
                if is_credit and not self._is_real_party():
                    messagebox.showwarning("Payment", "The amount paid is less than the "
                                           "total. Choose a customer to leave the rest on "
                                           "account.")
                    return
                paid_amt = cash_amt + card_amt
                pay_status = ("unpaid" if paid_amt <= 0.005 else
                              ("partial" if is_credit else "paid"))
            else:
                is_credit = (pay == "credit")
                pay_status = "unpaid" if is_credit else "paid"
                paid_amt = 0 if is_credit else total
                if pay == "cash":
                    cash_amt = total
                elif pay in ("card", "bank", "bank_transfer"):
                    card_amt = total
                if not is_credit:
                    tender_lines = _td.clean([("bank_transfer" if pay in ("bank", "bank_transfer")
                                               else pay, total)])

            if is_credit and not self._loaded_invoice_id:
                from modules import credit_check   # Settings ▸ Customer
                if not credit_check.confirm(cust_id, total - paid_amt, parent=self.win):
                    self.status_var.set("Credit sale stopped — over credit limit.")
                    return

            if self._loaded_invoice_id:
                try:   # receipts settled on this bill later stay counted
                    from modules import allocation
                    paid_amt = min(total, paid_amt + allocation.allocated_total(
                        "receipt", self._loaded_invoice_id))
                    pay_status = ("paid" if paid_amt >= total - 0.005 else
                                  ("partial" if paid_amt > 0.005 else "unpaid"))
                except Exception:
                    pass
            _h = dict(cust_id=cust_id, cust_en=cust_en, cust_ar=cust_ar,
                      gross=gross, vat=vat, total=total, pay=pay,
                      pay_status=pay_status, paid_amt=paid_amt,
                      cash_amt=cash_amt, card_amt=card_amt,
                      tender_lines=tender_lines,
                      points=(int(getattr(self, "_loaded_points", 0) or 0)
                              if self._loaded_invoice_id else 0)
                             + (int(getattr(self, "_points", 0) or 0) if _pv else 0),
                      points_value=_pv)
            self._pending_offline = (list(self.cart), _h, bool(is_credit),
                                     self._loaded_invoice_id, do_print)
            invoice_id, invoice_number = self._write_invoice(
                self.cart, _h, invoice_id=self._loaded_invoice_id)
            self._pending_offline = None      # saved on the server
            from modules import doc_posting
            if doc_posting.last_warning:
                self.status_var.set("Saved — accounts: " + doc_posting.last_warning[:80])

            # ── Cash tender: pop the cash drawer (teller) ──
            if cash_amt > 0 and cfg.flag("pos_open_drawer", True):
                try:
                    from modules import voice_alert
                    voice_alert.open_cash_drawer()
                except Exception:
                    pass

            self.status_var.set("%s %s - %s SAR"
                                % ("Updated" if self._loaded_invoice_id else "Saved",
                                   invoice_number, "{:,.2f}".format(total)))
            change = max(0.0, float(tenders[0] or 0) - cash_amt) if tenders is not None \
                else self._typed_change(total)
            if do_print:
                self._print(invoice_id)
            else:
                self._show_done(invoice_number, total, invoice_id, pay=pay,
                                cash=cash_amt, card=card_amt, change=change)
            self.cart = []
            self._sel_idx = None
            self._loaded_invoice_id = None
            self.bill_var.set("NEW")
            self.paid_var.set("0.00")
            self._loaded_split = None
            self._reset_customer()
            self._render_cart()
            self._refresh_day_info()
            self.barcode_entry.focus_set()
        except Exception as e:
            if self._keep_offline(e):            # v6.0: server gone → keep on this PC
                return
            messagebox.showerror("Not saved", "The bill was NOT saved — nothing was kept, the "
                                 "items are still on the screen. Please try again.\n\n" + str(e)[:400],
                                 parent=self.win)

    # -- bill with RETURN lines: sale invoice + sales return ------
    def _save_exchange(self, pay="cash", do_print=False, tenders=None):
        """Sale lines → a POS sales invoice; RETURN lines → a Sales Return
        (credit note: stock back in, VAT reversed). Money:
          customer pays   net = sale − return   (Cash + Card window), or
          customer gets   return − sale  back   (cash / card / account).
        The returned goods pay part of the sale, so the cash drawer and
        the card account move only by what really changed hands."""
        from modules import permissions as _pm
        if self._loaded_invoice_id:
            messagebox.showwarning("Return", "A return can't be added to a saved bill.\n"
                                   "Press New [F3] and ring it as a new bill.", parent=self.win)
            return
        if not _pm.allowed("sales_return", "add", parent=self.win):
            return
        if not self._shift_ok():
            return
        P = self._bill_parts()
        S, R, net = P["s_total"], P["r_total"], P["net"]
        party = self._is_real_party()
        cust = getattr(self, "_customer", None)
        cust_id = cust["customer_id"] if cust else self._walkin_id
        cust_en = (cust or {}).get("customer_name_en", "Walk-in Customer")
        cust_ar = (cust or {}).get("customer_name_ar", "") or cust_en
        change = 0.0
        ext = {}
        if tenders is not None and net > 0:
            c = max(float(tenders[0] or 0), 0.0)
            k = max(float(tenders[1] or 0), 0.0)
            ext = {m: round(max(float(v or 0), 0.0), 2) for m, v in
                   ((tenders[2] if len(tenders) > 2 and tenders[2] else {}) or {}).items()}
            ext_tot = round(sum(ext.values()), 2)
            card_amt = round(min(k, max(0.0, net - ext_tot)), 2)
            cash_amt = round(min(c, max(0.0, net - card_amt - ext_tot)), 2)
            card_amt = round(card_amt + ext_tot, 2)       # every non-cash tender
            rest = round(net - cash_amt - card_amt, 2)
            if rest > 0.005 and not party:
                messagebox.showwarning("Payment", "The amount paid is less than the total. "
                                       "Choose a customer to leave the rest on account.",
                                       parent=self.win)
                return
            change = round(max(0.0, c - cash_amt), 2)
            ret_method = "cash"                   # returned goods offset the sale in cash
            inv_cash, inv_card = round(cash_amt + min(R, S), 2), card_amt
            drawer = cash_amt
            how = ("mixed" if cash_amt > 0.004 and card_amt > 0.004 else
                   ("card" if card_amt > 0.004 else "cash"))
        else:
            m = str(pay or "cash").lower()
            m = "card" if m in ("card", "bank", "bank_transfer") else \
                ("credit" if (m == "credit" and party) else "cash")
            ret_method = m
            inv_cash = S if m == "cash" else 0.0
            inv_card = S if m == "card" else 0.0
            drawer = (S - R) if m == "cash" else 0.0
            how = m
            if m == "cash" and net > 0:
                change = self._typed_change(net)
        paid_amt = round(inv_cash + inv_card, 2)
        try:
            invoice_id = invoice_number = None
            if P["sale"]:
                on_acc = round(S - paid_amt - (R if ret_method == "credit" else 0.0), 2)
                if on_acc > 0.005:
                    from modules import credit_check   # Settings ▸ Customer
                    if not credit_check.confirm(cust_id, on_acc, parent=self.win):
                        self.status_var.set("Stopped — over the customer's credit limit.")
                        return
                pay_label = ("credit" if paid_amt <= 0.005 else
                             ("mixed" if inv_cash > 0.004 and inv_card > 0.004 else
                              ("card" if inv_card > 0.004 else "cash")))
                pay_status = ("unpaid" if paid_amt <= 0.005 else
                              ("partial" if paid_amt < S - 0.005 else "paid"))
            # the new bill and the return are kept together, or neither (v5.27)
            with db.transaction():
                if P["sale"]:
                    from modules import tenders as _td
                    _tl = None
                    if ext:
                        _tl = _td.clean([("cash", inv_cash), ("card", round(inv_card - sum(ext.values()), 2))]
                                        + list(ext.items()))
                        pay_label = _td.method_name(_tl) if paid_amt > 0.005 else pay_label
                    invoice_id, invoice_number = self._write_invoice(
                        P["sale"], dict(cust_id=cust_id, cust_en=cust_en, cust_ar=cust_ar,
                                        gross=P["s_gross"], vat=P["s_vat"], total=S,
                                        pay=pay_label, pay_status=pay_status,
                                        paid_amt=paid_amt, cash_amt=inv_cash,
                                        card_amt=inv_card, tender_lines=_tl))
                rid, rnum = self._write_return(P["rets"], ret_method, cust, cust_id,
                                               cust_en, cust_ar, P, invoice_number)
            from modules import doc_posting
            if abs(drawer) > 0.004 and cfg.flag("pos_open_drawer", True):
                try:
                    from modules import voice_alert
                    voice_alert.open_cash_drawer()
                except Exception:
                    pass
            self.status_var.set("Saved %s%s  ·  %s %s SAR" % (
                (invoice_number + " + ") if invoice_number else "", rnum,
                "customer pays" if net > 0.004 else "money back",
                "{:,.2f}".format(abs(net))))
            if doc_posting.last_warning:
                self.status_var.set("Saved — accounts: " + doc_posting.last_warning[:80])
            self._last_saved = (invoice_number or rnum, net)
            if do_print:
                if invoice_id:
                    self._print(invoice_id)
                self._print_return(rid)
            else:
                self._show_done(invoice_number or rnum, net, invoice_id, pay=how,
                                change=change, ret=(rid, rnum, R, S, ret_method))
            self.cart = []
            self._sel_idx = None
            self._loaded_invoice_id = None
            self.bill_var.set("NEW")
            self.paid_var.set("0.00")
            self._loaded_split = None
            self._set_minus(False)
            self._reset_customer()
            self._render_cart()
            self._refresh_day_info()
            self.barcode_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Not saved", "Nothing was saved (bill and return) — the items "
                                 "are still on the screen. Please try again.\n\n" + str(e)[:400],
                                 parent=self.win)

    def _write_return(self, lines, method, cust, cust_id, cust_en, cust_ar, P,
                      invoice_number=None):
        """Sales Return (credit note) for the RETURN lines, confirmed:
        stock back in, sales + VAT reversed, money back by `method`.
        One transaction: kept whole, or not at all (v5.27)."""
        with db.transaction():
            return self._write_return_body(lines, method, cust, cust_id, cust_en,
                                           cust_ar, P, invoice_number)

    def _write_return_body(self, lines, method, cust, cust_id, cust_en, cust_ar, P,
                           invoice_number=None):
        try:
            from modules.doc_numbering import next_number
            number = next_number("sales_returns", "return_number", "SR")
        except Exception:
            number = "SR-%s-%s" % (datetime.now().strftime("%Y%m"),
                                   datetime.now().strftime("%d%H%M%S"))
        note = "POS return" + ((" · exchange with " + invoice_number) if invoice_number else "")
        db.execute(
            "INSERT INTO sales_returns (return_number, return_date, original_invoice_no, "
            "customer_id, customer_name_en, customer_name_ar, customer_vat_no, "
            "subtotal_amount, discount_amount, taxable_amount, vat_amount, total_amount, "
            "payment_method, notes_en, return_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (number, date.today().strftime("%Y-%m-%d"), invoice_number or "",
             cust_id, cust_en, cust_ar, (cust or {}).get("vat_no", "") or "",
             round(P["r_gross"], 2), 0, round(P["r_gross"], 2), round(P["r_vat"], 2),
             P["r_total"], method, note, "confirmed"))
        rid = db.execute_scalar("SELECT return_id FROM sales_returns WHERE return_number=?",
                                (number,))
        try:                                     # v6.0: the cashier's shift
            from modules import shifts as _sh
            _sh.stamp("sales_returns", rid)
        except Exception:
            pass
        for i, ln in enumerate(lines, 1):
            db.execute(
                "INSERT INTO sales_return_lines (return_id, line_number, product_id, "
                "product_code, product_name_en, product_name_ar, quantity, "
                "unit_of_measure_en, unit_price, discount_amount, line_amount, "
                "vat_category_code, vat_rate, vat_amount, line_total) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, i, ln["product_id"], ln.get("product_code", ""),
                 ln["product_name_en"], ln.get("product_name_ar", ""), -ln["quantity"],
                 ln.get("unit_name", "Unit"), ln["unit_price"],
                 round(-float(ln.get("discount_amount") or 0), 2), -ln["taxable"],
                 ln.get("vat_code", "S"), ln["vat_rate"], -ln["vat_amount"],
                 -ln["line_total"]))
        from modules import doc_posting
        try:
            doc_posting.sync("sales_return", rid)
        except Exception as e:
            doc_posting.last_warning = str(e)[:200]
        try:            # ZATCA Phase 2: the credit note is signed + queued
            from modules.zatca import egs as _zegs
            _zegs.after_save("sales_return", rid)
        except Exception:
            pass
        return rid, number

    def _print_return(self, return_id):
        try:
            from ui import print_menu
            return print_menu.run(self.win, "sales_return", return_id, "default",
                                  status=self.status_var)
        except Exception as e:
            self.status_var.set("Return print: " + str(e)[:80])

    # -- write one POS sales invoice (new or update) -------------
    def _write_invoice(self, lines, h, invoice_id=None):
        """Header + lines + QR + POS tag + cash/card split + stock and
        accounts. Returns (invoice_id, invoice_number). One transaction:
        a bill is saved whole or not at all (v5.27)."""
        with db.transaction():
            return self._write_invoice_body(lines, h, invoice_id)

    def _write_invoice_body(self, lines, h, invoice_id=None):
        # v6.9: a rounded total (Settings ▸ Tax ▸ round-off) is spread over
        # the lines BEFORE VAT, so the lines, taxable, VAT and total agree
        # (the header used to keep the rounded total with unrounded VAT)
        try:
            _lt = round(sum(float(l.get("line_total") or 0) for l in lines), 2)
            _adj = round(_lt - float(h.get("total") or 0), 2)
            if lines and 0.005 <= abs(_adj) <= 1.0 + float(h.get("points_value") or 0):
                from modules.doc_math import spread_bill_adjustment
                _tmp = spread_bill_adjustment(
                    [dict(l, line_amount=l.get("taxable")) for l in lines], _adj, _price_incl())
                lines = [dict(l, taxable=t["line_amount"], vat_amount=t["vat_amount"],
                              line_total=t["line_total"], discount_amount=t["discount_amount"])
                         for l, t in zip(lines, _tmp)]
                h = dict(h, gross=round(sum(float(l["taxable"]) for l in lines), 2),
                         vat=round(sum(float(l["vat_amount"]) for l in lines), 2))
        except Exception:
            pass
        # v6.9.2: lines in halalas, VAT the ZATCA way (once per rate on the
        # bill); the total stays what the customer paid, taxable = total - VAT
        try:
            from modules.doc_math import doc_totals, round_lines
            lines = round_lines(lines, net="taxable")
            _v = doc_totals(lines, _price_incl(), net="taxable", code="vat_code")["vat"]
            _t = round(float(h.get("total") or 0), 2)
            h = dict(h, vat=_v, gross=round(_t - _v, 2), total=_t)
        except Exception:
            pass
        if invoice_id:
            inv = db.fetchone("SELECT invoice_number FROM sales_invoices "
                              "WHERE invoice_id=?", (invoice_id,)) or {}
            invoice_number = inv.get("invoice_number", str(invoice_id))
            db.execute(
                "UPDATE sales_invoices SET customer_id=?, customer_name_en=?, "
                "customer_name_ar=?, subtotal_amount=?, taxable_amount=?, "
                "vat_amount=?, total_amount=?, payment_method=?, "
                "payment_status=?, paid_amount=?, discount_amount=?, updated_at=GETDATE() "
                "WHERE invoice_id=?",
                (h["cust_id"], h["cust_en"], h["cust_ar"], h["gross"], h["gross"], h["vat"],
                 h["total"], h["pay"], h["pay_status"], h["paid_amt"],
                 round(sum(float(l.get("discount_amount") or 0) for l in lines), 2),
                 invoice_id))
            db.execute("DELETE FROM sales_invoice_lines WHERE invoice_id=?", (invoice_id,))
        else:
            from config.database import is_duplicate_error
            _when = str(h.get("when") or "")[:19]        # a bill kept offline (v6.0)
            for _n_try in range(4):          # two tills at once → next number
                invoice_number = h.get("number") or db.get_next_invoice_number("SALES")
                try:
                    with db.savepoint():
                        db.execute(
                            "INSERT INTO sales_invoices (invoice_number, invoice_date, customer_id, "
                            "customer_name_en, customer_name_ar, customer_country_code, "
                            "subtotal_amount, discount_amount, taxable_amount, vat_amount, "
                            "total_amount, payment_method, payment_status, paid_amount, "
                            "invoice_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (invoice_number, _when[:10] or date.today().strftime("%Y-%m-%d"), h["cust_id"],
                             h["cust_en"], h["cust_ar"], "SA", h["gross"],
                             round(sum(float(l.get("discount_amount") or 0) for l in lines), 2),
                             h["gross"], h["vat"],
                             h["total"], h["pay"], h["pay_status"], h["paid_amt"], "confirmed"))
                    break
                except Exception as _e:
                    if _n_try < 3 and is_duplicate_error(_e) and not h.get("number"):
                        continue
                    raise
            invoice_id = db.execute_scalar(
                "SELECT invoice_id FROM sales_invoices WHERE invoice_number=?",
                (invoice_number,))
            if _when:                                    # the real time of the sale
                try:
                    db.execute("UPDATE sales_invoices SET invoice_time=?, created_at=? WHERE invoice_id=?",
                               (_when[11:19] or None, _when, invoice_id))
                except Exception:
                    pass
        for i, ln in enumerate(lines, 1):
            db.execute(
                "INSERT INTO sales_invoice_lines (invoice_id, line_number, product_id, "
                "product_code, product_name_en, product_name_ar, quantity, "
                "unit_of_measure_en, unit_price, discount_amount, line_amount, "
                "vat_category_id, vat_category_code, vat_rate, vat_amount, line_total) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (invoice_id, i, ln["product_id"], ln.get("product_code", ""),
                 ln["product_name_en"], ln.get("product_name_ar", ""), ln["quantity"],
                 ln.get("unit_name", "Unit"), ln["unit_price"],
                 round(float(ln.get("discount_amount") or 0), 2), ln["taxable"],
                 ln.get("vat_category_id"), ln.get("vat_code", "S"),
                 ln["vat_rate"], ln["vat_amount"], ln["line_total"]))
            if ln.get("offer_id"):
                try:            # which offer gave this discount (bill + offer report)
                    db.execute("UPDATE sales_invoice_lines SET offer_id=?, offer_text=? "
                               "WHERE invoice_id=? AND line_number=?",
                               (ln["offer_id"], (ln.get("offer_text") or "")[:80],
                                invoice_id, i))
                except Exception:
                    pass
        try:
            from modules.zatca.qr_generator import (generate_zatca_qr, format_zatca_datetime,
                                                    seller_name, clean_vat_number)
            _qdt = None
            if h.get("when"):
                try:
                    # the QR time is UTC ("…Z"); the kept bill's time is this PC's clock
                    from datetime import timezone as _tz
                    _qdt = (datetime.strptime(str(h["when"])[:19], "%Y-%m-%d %H:%M:%S")
                            .astimezone(_tz.utc).replace(tzinfo=None))
                except Exception:
                    _qdt = None
            tlv = generate_zatca_qr(
                seller_name(self._company),
                clean_vat_number(self._company.get("vat_registration_no", "")),
                format_zatca_datetime(_qdt), "%.2f" % h["total"], "%.2f" % h["vat"])
            db.execute("UPDATE sales_invoices SET qr_code_data=? WHERE invoice_id=?",
                       (tlv, invoice_id))
        except Exception:
            pass
        # POS bills are tagged (POS report) with the cashier who rang them
        try:
            from modules import permissions as _p
            _uid = h.get("user_id") or (_p.session_user() or {}).get("user_id")
        except Exception:
            _uid = None
        try:
            db.execute("UPDATE sales_invoices SET sale_channel='POS' "
                       "WHERE invoice_id=?", (invoice_id,))
        except Exception:
            pass
        try:    # how much was cash / card (reports split a mixed bill)
            db.execute("UPDATE sales_invoices SET cash_paid=?, card_paid=? "
                       "WHERE invoice_id=?", (h["cash_amt"], h["card_amt"], invoice_id))
        except Exception:
            pass
        # v6.0: every way it was paid (cash, mada, STC Pay, Tabby …) + the shift
        from modules import tenders as _td
        tl = h.get("tender_lines")
        if tl is None:
            tl = _td.clean([("cash", h["cash_amt"]), ("card", h["card_amt"])])
        _td.save_lines("sales", invoice_id, tl)
        try:
            from modules import shifts as _sh
            if h.get("offline"):                  # the shift it was sold in
                if h.get("shift_id"):
                    db.execute("UPDATE sales_invoices SET shift_id=? WHERE invoice_id=?",
                               (h["shift_id"], invoice_id))
            else:
                _sh.stamp("sales_invoices", invoice_id)
        except Exception:
            pass
        if _uid:
            try:
                db.execute("UPDATE sales_invoices SET created_by=? WHERE "
                           "invoice_id=? AND created_by IS NULL", (_uid, invoice_id))
            except Exception:
                pass
        # ── Stock + ledger: cash -> cash account, card -> bank account,
        #    credit -> the party's receivable; stock out + cost of sales.
        #    Editing a loaded bill re-syncs it. A posting hiccup never
        #    blocks the sale from saving. ──
        try:            # ⭐ loyalty points spent on this bill (loyalty.sync_sale reads it)
            db.execute("UPDATE sales_invoices SET loyalty_points_redeemed=? WHERE invoice_id=?",
                       (int(h.get("points") or 0) or None, invoice_id))
        except Exception:
            pass
        from modules import doc_posting
        try:
            doc_posting.sync("sales", invoice_id, tenders=_td.for_posting(tl))
        except Exception as e:
            doc_posting.last_warning = str(e)[:200]
        try:            # ZATCA Phase 2: sign now so the bill prints with the new QR
            from modules.zatca import egs as _zegs
            _zegs.after_save("sales", invoice_id)
        except Exception:
            pass
        return invoice_id, invoice_number

    # -- Smart save / party detection --------------------------
    def _is_real_party(self):
        """True only when a genuine customer is selected (not the
        default Cash / Walk-in account)."""
        c = getattr(self, "_customer", None)
        if not c:
            return False
        if c is getattr(self, "_default_customer", None):
            return False
        code = str(c.get("customer_code", "")).strip().upper()
        if code in ("CASH", "WALKIN", "WALK-IN", ""):
            name = str(c.get("customer_name_en", "")).strip().lower()
            if code in ("CASH", "WALKIN", "WALK-IN") or name.startswith("cash") \
               or name.startswith("walk"):
                return False
        return True

    def _save_smart(self, do_print=False):
        """Plain Save button: a selected party -> credit sale on that
        party's account; otherwise a straight Cash sale. A saved bill that
        was paid part cash / part card re-opens the Cash + Card window."""
        sp = getattr(self, "_loaded_split", None)
        if self._loaded_invoice_id and sp and ((sp[0] > 0 and sp[1] > 0)
                                               or (len(sp) > 2 and sp[2])):
            self._open_pay("cash", prefill=sp, do_print=do_print)
            return
        pay = "credit" if self._is_real_party() else "cash"
        if self.cart and any(l["quantity"] < 0 for l in self.cart) \
                and self._bill_parts()["net"] <= 0.004:
            self._refund(pay, do_print=do_print)     # asks first (cash back / account)
            return
        self._save(pay=pay, do_print=do_print)

    def _refund(self, method="cash", do_print=False):
        """Bill with returns where the customer gets money back (or a
        straight swap): one question, then save."""
        P = self._bill_parts()
        back = -P["net"]
        party = self._is_real_party()
        if back <= 0.004:
            q = "Exchange — nothing to pay and nothing to give back.\n\nSave?"
            method = "cash"
        elif party and method not in ("card",):
            method = "credit"
            q = ("Give back %s SAR?\n\nIt goes to %s's account (credit note).\n\nSave?"
                 % ("{:,.2f}".format(back), (self._customer or {}).get("customer_name_en", "")))
        else:
            q = ("Give the customer %s SAR back  —  %s.\n\nSave?"
                 % ("{:,.2f}".format(back), "by CARD" if method == "card" else "in CASH"))
        if not messagebox.askyesno("Refund  /  استرجاع", q, parent=self.win):
            return
        self._save(pay=method, do_print=do_print)

    def _empty_bill_msg(self):
        """Save / Cash / Card with an empty bill: say so, keep POS open."""
        self.status_var.set("No products in the bill - scan or add a product first.")
        messagebox.showwarning("Empty bill",
                               "No products in the bill.\nScan or add a product first.\n\n"
                               "لا توجد منتجات في الفاتورة", parent=self.win)
        try:
            self.win.lift(); self.barcode_entry.focus_set()
        except Exception:
            pass

    def _close_pos(self):
        """✕ / window close: Yes / No first (warns about an unsaved bill)."""
        n = len(self.cart)
        txt = ("This bill has %d product(s) that are NOT saved.\nClose POS anyway?" % n
               if n and self._loaded_invoice_id is None else "Close POS?")
        if messagebox.askyesno("Close POS", txt + "\nهل تريد إغلاق نقطة البيع؟",
                               icon="warning" if n else "question", parent=self.win):
            self._close_search_dd(); self._close_cust_dd()
            self.win.destroy()

    def _cur_total(self):
        try:
            return float(str(self.total_var.get()).replace(",", "") or 0)
        except Exception:
            return 0.0

    def _typed_change(self, total):
        """Change to hand back when a cash amount was typed on the PAID tile."""
        try:
            paid = float(str(self.paid_var.get()).replace(",", "") or 0)
        except Exception:
            return 0.0
        return max(0.0, paid - total)

    # -- Cash + Card window ------------------------------------
    def _open_pay(self, start="cash", prefill=None, do_print=False):
        """Tap Cash / Card -> number pad with a Cash field and a Card field.
        e.g. total 40: customer pays 20 cash + 20 card."""
        if not self.cart:
            self._empty_bill_msg()
            return
        P = self._bill_parts()
        if P["rets"] and P["net"] <= 0.004:
            self._refund(start, do_print=do_print)     # money back (or even swap)
            return
        total = P["net"] if P["rets"] else self._cur_total()
        try:
            typed = float(str(self.paid_var.get()).replace(",", "") or 0)
        except Exception:
            typed = 0.0

        def done(cash, card, print_it, extras=None):
            self._save(tenders=(cash, card, extras or {}), do_print=print_it)
        try:
            from modules import tenders as _td
            extras = _td.extra_methods()
        except Exception:
            extras = []
        PayDialog(self.win, total, start=start, on_done=done,
                  prefill=prefill or ((typed, 0.0) if start == "cash" and typed > 0 else None),
                  party=self._is_real_party(), do_print=do_print,
                  card_on=cfg.payment_enabled("card"), cash_on=cfg.payment_enabled("cash"),
                  extras=extras)

    def _print_last_bill(self):
        """Print the last saved POS bill again."""
        from modules import permissions as _pm
        if not _pm.allowed("pos", "print"):
            return False
        try:
            from modules import doc_print as DP
            prev = DP.last_id("pos")
        except Exception:
            prev = None
        if prev:
            self._print(prev)
        else:
            self.status_var.set("No saved bill yet.")

    def _refresh_day_info(self):
        """Status bar: last bill number + amount, today's bills."""
        if hasattr(self, "shift_btn"):
            self._shift_label()
        try:
            r = db.fetchone("SELECT COUNT(*) AS n, ISNULL(SUM(total_amount),0) AS t "
                            "FROM sales_invoices WHERE sale_channel='POS' AND "
                            "invoice_date=?", (date.today().strftime("%Y-%m-%d"),)) or {}
            last = db.fetchone("SELECT TOP 1 invoice_number, total_amount FROM sales_invoices "
                               "WHERE sale_channel='POS' ORDER BY invoice_id DESC") or {}
            txt = ""
            if last.get("invoice_number"):
                txt = "Last bill %s  =  %s SAR" % (last["invoice_number"],
                                                   "{:,.2f}".format(float(last.get("total_amount") or 0)))
            txt += ("   |   " if txt else "") + "Today %d bills · %s" % (
                int(r.get("n") or 0), "{:,.2f}".format(float(r.get("t") or 0)))
            self.day_var.set(txt)
        except Exception:
            self.day_var.set("")

    def _alert_not_found(self):
        """Barcode/search miss -> speak/beep (Settings ▸ POS toggle)."""
        if not cfg.flag("pos_voice_not_found", True):
            return
        try:
            from modules import voice_alert
            voice_alert.not_found(widget=self.win)
        except Exception:
            try:
                self.win.bell()
            except Exception:
                pass

    def _toggle_incl_vat(self):
        """Persist the VAT-inclusive flag and re-price the whole cart."""
        try:
            _set_price_incl(bool(self.incl_vat_var.get()))
        except Exception:
            pass
        for ln in self.cart:
            self._recalc(ln)
        self._render_cart()
        self.status_var.set("Sale price %s VAT."
                            % ("includes" if self.incl_vat_var.get() else "excludes"))

    # -- Cart line quick-edit (double-click) -------------------
    def _edit_cart_line(self, event=None):
        """Double-click a cart line -> product details popup with an
        editable Sale Price (and Qty). Saves straight back to the line."""
        # ignore double-clicks on the header
        try:
            if self.tree.identify_region(event.x, event.y) == "heading":
                return
        except Exception:
            pass
        sel = self.tree.selection()
        idx = int(sel[0]) if sel else self._sel_idx
        if idx is None or not (0 <= idx < len(self.cart)):
            return
        ln = self.cart[idx]
        prod = next((p for p in self.products
                     if p["product_id"] == ln["product_id"]), None)

        units = self._units_for(ln["product_id"])
        sign = -1 if ln["quantity"] < 0 else 1           # RETURN line: qty shown positive

        def _calc(price, qty, uname, factor):
            tmp = dict(ln); tmp["unit_price"] = price; tmp["quantity"] = sign * qty
            self._recalc(tmp)
            return tmp["line_total"]

        def _apply(new_price, new_qty, new_unit=None):
            if new_price is not None:
                if abs(float(new_price) - float(ln["unit_price"])) > 1e-6:
                    ln.update(offer_off=True, discount_amount=0.0, offer_id=None, offer_text="")  # price changed by hand
                    ln["_price_typed"] = True
                ln["unit_price"] = float(new_price)
            if new_unit is not None:
                ln["unit_name"] = new_unit["unit_name_en"]
                ln["factor"] = float(new_unit.get("conversion_factor", 1) or 1)
                if new_price is None:       # price edit is off -> the unit's own price
                    ln["unit_price"] = float(new_unit.get("selling_price") or 0) or \
                        float((prod or {}).get("unit_price", 0) or 0) * ln["factor"]
            if new_qty is not None and new_qty > 0:
                ln["quantity"] = sign * new_qty
            # same product + same unit (+ same sale/return side) -> join the lines
            for other in self.cart:
                if other is not ln and other["product_id"] == ln["product_id"] \
                        and other["unit_name"] == ln["unit_name"] \
                        and (other["quantity"] < 0) == (ln["quantity"] < 0):
                    other["quantity"] += ln["quantity"]
                    self.cart.remove(ln)
                    self._recalc(other)
                    self._render_cart(select_line=other)
                    self._focus_barcode_default()
                    return
            self._recalc(ln)
            self._render_cart(select_line=ln)
            self.status_var.set("%s -> %s %s @ %s"
                                % (ln["product_name_en"], "%g" % ln["quantity"],
                                   ln["unit_name"], "{:,.2f}".format(ln["unit_price"])))
            self._focus_barcode_default()

        shown = dict(ln, quantity=abs(ln["quantity"]))
        if sign < 0:
            shown["product_name_en"] = "↩ RETURN  " + ln["product_name_en"]
        CartLineEditDialog(self.win, shown, prod, _apply, units=units, calc=_calc)

    # -- POS Settings popup ------------------------------------
    def _open_pos_settings(self):
        POSSettingsDialog(self.win, on_change=self._apply_pos_settings)

    def _apply_pos_settings(self):
        """Re-read live POS flags after the settings popup closes."""
        try:
            self.incl_vat_var.set(_price_incl())
            for ln in self.cart:
                self._recalc(ln)
            self._render_cart()
        except Exception:
            pass

    # -- Quick add customer ------------------------------------
    def _add_customer_quick(self):
        def _created(new_cust):
            # refresh the customer cache and select the new one
            self._load_customers()
            match = next((c for c in getattr(self, "_customers", [])
                          if c["customer_id"] == new_cust["customer_id"]), new_cust)
            self._set_customer(match)
            self.cust_search_var.set("")
            self._close_cust_dd()
            self.status_var.set("Customer added & selected: %s"
                                % new_cust.get("customer_name_en", ""))
            self._focus_barcode_default()
        QuickCustomerDialog(self.win, on_save=_created)

    def _load_customers(self):
        try:
            self._customers = db.fetchall(
                "SELECT customer_id, customer_code, customer_name_en, "
                "ISNULL(customer_name_ar,'') AS customer_name_ar, "
                "ISNULL(phone,'') AS phone, "
                "ISNULL(vat_registration_no,'') AS vat_no "
                "FROM customers WHERE is_active=1 "
                "ORDER BY customer_name_en") or []
        except Exception:
            pass

    def _show_done(self, invoice_number, total, invoice_id, pay="cash", cash=0.0,
                   card=0.0, change=0.0, ret=None):
        """Saved window. `ret` = (return_id, return_no, return_total,
        sale_total, method) when the bill had RETURN lines."""
        d = tk.Toplevel(self.win); d.title("Saved")
        d.configure(bg="white"); d.transient(self.win)
        d._no_close_confirm = True
        W, H = 400, 345 if ret else 330
        sw, sh = d.winfo_screenwidth(), d.winfo_screenheight()
        d.geometry("%dx%d+%d+%d" % (W, H, (sw - W) // 2, (sh - H) // 2))
        ok = tk.Label(d, text="✓", font=("Segoe UI", 26, "bold"), bg="#DCFCE7", fg="#15803D",
                      width=3)
        ok.pack(pady=(18, 4))
        how = {"cash": "Cash", "card": "Card", "mixed": "Cash + Card",
               "credit": "On account"}.get(pay, str(pay).title())
        if ret:
            rid, rno, R, S, rmeth = ret
            title = ("Exchange saved" if S > 0.004 else "Return saved") + " · " + how
            tk.Label(d, text=title, font=("Segoe UI", 14, "bold"), bg="white",
                     fg=self.INK).pack()
            box = tk.Frame(d, bg="white"); box.pack(pady=4)
            rows = []
            if S > 0.004:
                rows.append(("Sale  " + (invoice_number if invoice_number != rno else ""),
                             S, self.INK))
            rows.append(("Return  " + rno, -R, "#B91C1C"))
            for lbl, amt, col in rows:
                r = tk.Frame(box, bg="white"); r.pack(fill="x")
                tk.Label(r, text=lbl, font=("Segoe UI", 10), bg="white", fg=self.MUTED,
                         width=24, anchor="w").pack(side="left")
                tk.Label(r, text="{:,.2f}".format(amt), font=("Segoe UI", 10, "bold"),
                         bg="white", fg=col, width=10, anchor="e").pack(side="left")
            cap = "Customer paid" if total > 0.004 else (
                "Give back" if total < -0.004 else "Nothing to pay")
            tk.Label(d, text="%s  %s SAR" % (cap, "{:,.2f}".format(abs(total))),
                     font=("Segoe UI", 20, "bold"), bg="white",
                     fg="#B91C1C" if total < -0.004 else self.INK).pack(pady=(6, 0))
            if total < -0.004 and rmeth == "credit":
                tk.Label(d, text="(credited to the customer's account)", font=("Segoe UI", 9),
                         bg="white", fg=self.MUTED).pack()
        else:
            tk.Label(d, text="Sale saved · %s" % how, font=("Segoe UI", 14, "bold"),
                     bg="white", fg=self.INK).pack()
            tk.Label(d, text=invoice_number, font=("Segoe UI", 10), bg="white",
                     fg=self.MUTED).pack(pady=2)
            tk.Label(d, text="%s SAR" % "{:,.2f}".format(total), font=("Segoe UI", 24, "bold"),
                     bg="white", fg=self.INK).pack(pady=(2, 0))
            if pay == "mixed":
                tk.Label(d, text="Cash %s   +   Card %s" % ("{:,.2f}".format(cash),
                                                            "{:,.2f}".format(card)),
                         font=("Segoe UI", 11), bg="white", fg=self.MUTED).pack()
        if change > 0.004:
            tk.Label(d, text="Change  %s SAR" % "{:,.2f}".format(change),
                     font=("Segoe UI", 14, "bold"), bg="white", fg="#166534").pack(pady=4)

        def _print_all():
            if invoice_id:
                self._print(invoice_id)
            if ret:
                self._print_return(ret[0])
        b = tk.Frame(d, bg="white"); b.pack(pady=14, fill="x", padx=20, side="bottom")
        self._btn(b, "Print receipt", "white", self.INK, _print_all,
                  font=("Segoe UI", 11, "bold"),
                  highlightbackground="#C7D0DD", highlightthickness=1).pack(
                      side="left", expand=True, fill="x", ipady=8, padx=(0, 4))
        nb = self._btn(b, "New sale", "#15803D", "white", d.destroy,
                       font=("Segoe UI", 11, "bold"))
        nb.pack(side="left", expand=True, fill="x", ipady=8, padx=(4, 0))
        d.bind("<Return>", lambda e: d.destroy()); d.bind("<Escape>", lambda e: d.destroy())
        nb.focus_set()
        d.grab_set()

    def _print(self, invoice_id, option="default"):
        """Print the bill with its default layout (thermal receipt, or A4
        when Settings ▸ POS ▸ Receipt Format is A4) on the POS printer."""
        from ui import print_menu
        return print_menu.run(self.win, "pos", invoice_id, option,
                              status=self.status_var)


# ============================================================
# Unit Picker — opens when a Search match has multiple units.
# Shows every unit with an EDITABLE sales price and its stock in
# that unit; double-click / Enter adds it to the cart.
# ============================================================
class UnitPriceStockDialog(tk.Toplevel):
    def __init__(self, parent, product, units, on_pick):
        super().__init__(parent)
        self.product = product
        self.units = units
        self.on_pick = on_pick
        self.title("Select Unit — %s" % product.get("product_name_en", ""))
        self.configure(bg="#0F2027")
        self.geometry("560x360")
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text=product.get("product_name_en", ""),
                 font=("Segoe UI", 14, "bold"), bg="#0F2027", fg="white"
                 ).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="This product has multiple units. Pick one — "
                            "price is editable for this sale.",
                 font=("Segoe UI", 9), bg="#0F2027", fg="#9FC3D6"
                 ).pack(anchor="w", padx=16, pady=(0, 10))

        wrap = tk.Frame(self, bg="white"); wrap.pack(fill="both", expand=True,
                                                     padx=16, pady=(0, 10))
        cols = ("unit", "conv", "price", "stock")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=8)
        for cid, txt, w, anc in [("unit", "Unit", 120, "w"),
                                 ("conv", "= Base Units", 110, "center"),
                                 ("price", "Sales Price", 110, "e"),
                                 ("stock", "Stock (in unit)", 120, "e")]:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=anc)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set); ysb.pack(side="right", fill="y")

        base_stock = float(product.get("stock_quantity", 0) or 0)
        for u in units:
            factor = float(u.get("conversion_factor", 1) or 1)
            price = float(u.get("selling_price") or 0)
            stock_in_unit = base_stock / factor if factor else base_stock
            self.tree.insert("", "end", iid=str(u["unit_id"]), values=(
                u.get("unit_name_en", ""), f"{factor:g}",
                f"{price:,.2f}", f"{stock_in_unit:,.2f}"))
        if units:
            first = str(units[0]["unit_id"])
            self.tree.selection_set(first); self.tree.focus(first)

        # editable price box, synced to the selected row
        prow = tk.Frame(self, bg="#0F2027"); prow.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(prow, text="Sales Price for this sale:", font=("Segoe UI", 10),
                 bg="#0F2027", fg="white").pack(side="left")
        self.price_var = tk.StringVar()
        pe = tk.Entry(prow, textvariable=self.price_var, font=("Segoe UI", 12, "bold"),
                     width=12, justify="right")
        pe.pack(side="left", padx=8)

        def sync_price(event=None):
            sel = self.tree.selection()
            if sel:
                u = next((x for x in units if str(x["unit_id"]) == sel[0]), None)
                if u:
                    self.price_var.set(f"{float(u.get('selling_price') or 0):.2f}")
        self.tree.bind("<<TreeviewSelect>>", sync_price)
        sync_price()

        self.tree.bind("<Double-1>", lambda e: self._confirm())
        self.tree.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())

        btns = tk.Frame(self, bg="#0F2027"); btns.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#34495E", fg="white",
                  relief="flat", padx=14, pady=7, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="✓ Add to Cart", font=("Segoe UI", 10, "bold"),
                  bg="#27AE60", fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._confirm).pack(side="right")

        self.tree.focus_set()

    def _confirm(self):
        sel = self.tree.selection()
        if not sel:
            return
        unit_id = int(sel[0])
        try:
            price = float(self.price_var.get() or 0)
        except ValueError:
            price = None
        self.destroy()
        self.on_pick(self.product, unit_id, price_override=price)


# ============================================================
# Product Details — Ctrl key on a selected cart line. Shows every
# unit's sales price, purchase price, and profit (amount + %).
# ============================================================
class ProductDetailsDialog(tk.Toplevel):
    """Ctrl details box — minimal card, auto-sized to the unit count,
    centered over POS. Closes on Ctrl again, Esc, the Close button, or
    a tap anywhere on the card (touch-friendly)."""
    def __init__(self, parent, product, units):
        super().__init__(parent)
        self.overrideredirect(True)          # frameless minimal card
        self.configure(bg="#1B3A4B")
        self.transient(parent)
        self.grab_set()

        card = tk.Frame(self, bg="white", highlightbackground="#2E86AB",
                        highlightthickness=2)
        card.pack(fill="both", expand=True)

        # header strip: name + code + big default price
        hdr = tk.Frame(card, bg="#1B3A4B"); hdr.pack(fill="x")
        nm = tk.Frame(hdr, bg="#1B3A4B"); nm.pack(side="left", padx=12, pady=8)
        tk.Label(nm, text=product.get("product_name_en", ""),
                 font=("Segoe UI", 13, "bold"), bg="#1B3A4B",
                 fg="white").pack(anchor="w")
        stock = product.get("stock_quantity", 0)
        tk.Label(nm, text="Code %s   ·   Stock %g" % (
                     product.get("product_code", ""), float(stock or 0)),
                 font=("Segoe UI", 9), bg="#1B3A4B",
                 fg="#9FC3D6").pack(anchor="w")
        base_cost = float(product.get("purchase_price", 0) or 0)
        rows = units if units else [{"unit_name_en": product.get("unit_of_measure_en", "Unit"),
                                     "conversion_factor": 1, "is_default": 1,
                                     "selling_price": product.get("unit_price", 0)}]
        dft = next((u for u in rows if u.get("is_default")), rows[0])
        dprice = float(dft.get("selling_price") or 0) or \
            float(product.get("unit_price", 0) or 0)
        tk.Label(hdr, text="%s\n%s" % ("{:,.2f}".format(dprice),
                                       dft.get("unit_name_en", "Unit")),
                 font=("Segoe UI", 15, "bold"), bg="#1B3A4B", fg="#2ECC71",
                 justify="right").pack(side="right", padx=12, pady=6)

        # compact unit table — height fits the rows, no dead space
        cols = ("unit", "sale", "cost", "profit", "margin")
        tree = ttk.Treeview(card, columns=cols, show="headings",
                            height=min(max(len(rows), 1), 6))
        for cid, txt, w, anc in [("unit", "Unit", 110, "w"),
                                 ("sale", "Sale", 90, "e"),
                                 ("cost", "Cost", 90, "e"),
                                 ("profit", "Profit", 80, "e"),
                                 ("margin", "Margin", 70, "e")]:
            tree.heading(cid, text=txt)
            tree.column(cid, width=w, anchor=anc)
        tree.tag_configure("odd", background="#F4F9FC")
        tree.tag_configure("default", background="#E9F9EF")
        for i, u in enumerate(rows):
            factor = float(u.get("conversion_factor", 1) or 1)
            sale = float(u.get("selling_price") or 0) or \
                float(product.get("unit_price", 0) or 0) * factor
            cost = base_cost * factor
            profit = sale - cost
            margin = (profit / sale * 100) if sale else 0
            name = u.get("unit_name_en", "") + ("  ★" if u.get("is_default") else "")
            tree.insert("", "end", values=(
                name, f"{sale:,.2f}", f"{cost:,.2f}",
                f"{profit:,.2f}", f"{margin:.1f}%"),
                tags=("default" if u.get("is_default") else
                      ("odd" if i % 2 else ""),))
        tree.pack(fill="x", padx=10, pady=(8, 4))

        foot = tk.Frame(card, bg="white"); foot.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(foot, text="Ctrl / Esc / tap = close",
                 font=("Segoe UI", 8), bg="white",
                 fg="#95A5A6").pack(side="left")
        tk.Button(foot, text="Close", font=("Segoe UI", 11, "bold"),
                  bg="#2E86AB", fg="white", relief="flat", padx=22, pady=8,
                  cursor="hand2", command=self.destroy).pack(side="right")

        # close on Ctrl again / Esc / any tap on the card (touch)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control_L>", lambda e: self.destroy())
        self.bind("<Control_R>", lambda e: self.destroy())
        for w in (card, hdr, nm, tree, foot):
            w.bind("<Button-1>", lambda e: self.destroy(), add="+")

        # size to content, centered over the POS window
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 470)
        h = self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            self.geometry("%dx%d+%d+%d" % (w, h, px + (pw - w) // 2,
                                           py + (ph - h) // 3))
        except Exception:
            self.geometry("%dx%d" % (w, h))
        self.focus_set()

# ============================================================
# Cart Line Quick-Edit — double-click a cart line. Shows the
# product with cost/profit reference and an EDITABLE Sale Price
# (+ Qty), writing straight back to that line.
# ============================================================
class CartLineEditDialog(tk.Toplevel):
    """Double-click a bill line: change the UNIT (piece / box / carton…),
    the quantity and the price. Each unit shows its own price; stock is
    shown in the chosen unit. A small number pad works on the field you
    last touched."""
    NAVY, BLUE, INK, MUTED = "#0B1F3A", "#1D4ED8", "#0F172A", "#475569"

    def __init__(self, parent, line, product, on_apply, units=None, calc=None):
        super().__init__(parent)
        self.on_apply = on_apply
        self.calc = calc
        self.line = line
        self.product = product or {}
        self.units = list(units or [])
        self.title("Edit Line")
        self.configure(bg="white")
        self.transient(parent)
        self.cur_unit = next((u for u in self.units
                              if u.get("unit_name_en") == line.get("unit_name")), None)
        self.factor = float((self.cur_unit or {}).get("conversion_factor")
                            or line.get("factor", 1) or 1) or 1.0
        self.base_unit = (min(self.units, key=lambda u: float(u.get("conversion_factor") or 1))
                          .get("unit_name_en", "Unit")) if self.units else line.get("unit_name", "Unit")
        self.can_price = cfg.flag("allow_price_edit", True)

        hdr = tk.Frame(self, bg=self.NAVY); hdr.pack(fill="x")
        tk.Label(hdr, text=line.get("product_name_en", ""), font=("Segoe UI", 14, "bold"),
                 bg=self.NAVY, fg="white", anchor="w").pack(fill="x", padx=16, pady=(10, 0))
        ar = line.get("product_name_ar", "") or ""
        tk.Label(hdr, text=("%s    ·    " % ar if ar else "") + "Code %s" % line.get("product_code", ""),
                 font=("Segoe UI", 10), bg=self.NAVY, fg="#A9BCD6", anchor="w").pack(
                     fill="x", padx=16, pady=(0, 10))

        body = tk.Frame(self, bg="white"); body.pack(fill="both", expand=True, padx=16, pady=12)
        left = tk.Frame(body, bg="white"); left.pack(side="left", fill="y")
        right = tk.Frame(body, bg="white"); right.pack(side="left", padx=(18, 0))

        # units
        self.unit_btns = []
        if len(self.units) > 1:
            tk.Label(left, text="UNIT  (tap to change)", font=("Segoe UI", 8, "bold"),
                     bg="white", fg=self.MUTED).pack(anchor="w")
            ur = tk.Frame(left, bg="white"); ur.pack(fill="x", pady=(2, 10))
            for i, u in enumerate(self.units):
                f = float(u.get("conversion_factor") or 1)
                pr = float(u.get("selling_price") or 0) or \
                    float(self.product.get("unit_price", 0) or 0) * f
                txt = "%s%s\n%s" % (u.get("unit_name_en", ""),
                                    ("  ×%g" % f) if f != 1 else "", "{:,.2f}".format(pr))
                b = tk.Button(ur, text=txt, font=("Segoe UI", 10, "bold"), relief="flat",
                              cursor="hand2", width=11, highlightthickness=1,
                              command=lambda uu=u: self._pick_unit(uu))
                b.grid(row=i // 3, column=i % 3, padx=3, pady=3, ipady=4)
                self.unit_btns.append((u, b))
        else:
            tk.Label(left, text="UNIT   %s" % line.get("unit_name", "Unit"),
                     font=("Segoe UI", 10, "bold"), bg="white", fg=self.MUTED).pack(
                         anchor="w", pady=(0, 8))

        grid = tk.Frame(left, bg="white"); grid.pack(fill="x")
        tk.Label(grid, text="PRICE", font=("Segoe UI", 8, "bold"), bg="white",
                 fg=self.MUTED).grid(row=0, column=0, sticky="w")
        tk.Label(grid, text="QUANTITY", font=("Segoe UI", 8, "bold"), bg="white",
                 fg=self.MUTED).grid(row=0, column=1, sticky="w", padx=(14, 0))
        self.price_var = tk.StringVar(value="%.2f" % float(line.get("unit_price", 0)))
        self.qty_var = tk.StringVar(value="%g" % float(line.get("quantity", 1)))
        self.pe = tk.Entry(grid, textvariable=self.price_var, font=("Segoe UI", 20, "bold"),
                           width=9, justify="right", relief="solid", bd=1, bg="#FFFDEA",
                           state="normal" if self.can_price else "readonly")
        self.pe.grid(row=1, column=0, ipady=6, sticky="w")
        qf = tk.Frame(grid, bg="white"); qf.grid(row=1, column=1, padx=(14, 0), sticky="w")
        tk.Button(qf, text="−", font=("Segoe UI", 16, "bold"), bg="#B45309", fg="white",
                  relief="flat", cursor="hand2", width=3,
                  command=lambda: self._step(-1)).pack(side="left", ipady=4)
        self.qe = tk.Entry(qf, textvariable=self.qty_var, font=("Segoe UI", 20, "bold"),
                           width=6, justify="center", relief="solid", bd=1, bg="#EAF4FA")
        self.qe.pack(side="left", ipady=6, padx=3)
        tk.Button(qf, text="+", font=("Segoe UI", 16, "bold"), bg="#15803D", fg="white",
                  relief="flat", cursor="hand2", width=3,
                  command=lambda: self._step(1)).pack(side="left", ipady=4)
        self.active = self.qe
        for e in (self.pe, self.qe):
            e.bind("<FocusIn>", lambda ev, w=e: setattr(self, "active", w))
            e.bind("<KeyRelease>", lambda ev: self._refresh())

        self.info_var = tk.StringVar()
        tk.Label(left, textvariable=self.info_var, font=("Segoe UI", 10), bg="white",
                 fg=self.MUTED, anchor="w", justify="left").pack(fill="x", pady=(10, 0))
        self.total_var = tk.StringVar()
        tk.Label(left, textvariable=self.total_var, font=("Segoe UI", 16, "bold"), bg="white",
                 fg=self.INK, anchor="w").pack(fill="x", pady=(6, 0))
        self.profit_var = tk.StringVar()
        if cfg.flag("pos_show_cost_in_search", True):
            tk.Label(left, textvariable=self.profit_var, font=("Segoe UI", 10, "bold"),
                     bg="white", fg="#0F766E", anchor="w").pack(fill="x")

        # keypad (works on the last touched field)
        keys = ["7", "8", "9", "4", "5", "6", "1", "2", "3", ".", "0", "⌫"]
        for i, k in enumerate(keys):
            tk.Button(right, text=k, font=("Segoe UI", 16, "bold"), bg="white", fg=self.INK,
                      relief="flat", cursor="hand2", width=4, highlightthickness=1,
                      highlightbackground="#C7D0DD",
                      command=lambda kk=k: self._key(kk)).grid(
                          row=i // 3, column=i % 3, padx=2, pady=2, ipady=5)

        foot = tk.Frame(self, bg="#F8FAFC", highlightbackground="#D5DCE6", highlightthickness=1)
        foot.pack(fill="x", side="bottom")
        tk.Button(foot, text="Cancel", font=("Segoe UI", 11), bg="white", fg=self.INK,
                  relief="flat", cursor="hand2", highlightthickness=1,
                  highlightbackground="#C7D0DD", command=self.destroy, padx=16).pack(
                      side="left", padx=12, pady=10, ipady=7)
        tk.Button(foot, text="✓ Apply   Enter", font=("Segoe UI", 13, "bold"), bg="#15803D",
                  fg="white", relief="flat", cursor="hand2", activebackground="#166534",
                  activeforeground="white", command=self._apply, padx=22).pack(
                      side="right", padx=12, pady=10, ipady=7)

        self.bind("<Return>", lambda e: self._apply())
        self.bind("<Escape>", lambda e: self.destroy())
        self._mark_units()
        self._refresh()
        self.update_idletasks()
        w, h = max(self.winfo_reqwidth(), 560), self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            self.geometry("%dx%d+%d+%d" % (w, h, px + max(0, (pw - w) // 2),
                                           py + max(0, (ph - h) // 3)))
        except Exception:
            self.geometry("%dx%d" % (w, h))
        self.grab_set()
        self.qe.focus_set(); self.qe.select_range(0, "end")

    # ── helpers ──
    def _mark_units(self):
        for u, b in self.unit_btns:
            on = (u is self.cur_unit)
            b.configure(bg=self.BLUE if on else "#F1F5F9", fg="white" if on else self.INK,
                        activebackground=self.BLUE if on else "#E2E8F0",
                        highlightbackground=self.BLUE if on else "#C7D0DD")

    def _pick_unit(self, u):
        self.cur_unit = u
        self.factor = float(u.get("conversion_factor") or 1) or 1.0
        pr = float(u.get("selling_price") or 0) or \
            float(self.product.get("unit_price", 0) or 0) * self.factor
        if self.can_price:
            self.price_var.set("%.2f" % pr)
        self._mark_units()
        self._refresh()

    def _val(self, var):
        try:
            return float(str(var.get()).replace(",", "") or 0)
        except ValueError:
            return 0.0

    def _step(self, d):
        q = max(0.0, self._val(self.qty_var) + d)
        self.qty_var.set("%g" % q)
        self._refresh()

    def _key(self, k):
        e = self.active
        var = self.price_var if e is self.pe else self.qty_var
        if e is self.pe and not self.can_price:
            return
        cur = var.get()
        try:
            sel = e.selection_present()
        except Exception:
            sel = False
        if sel:
            cur = ""
        if k == "⌫":
            cur = cur[:-1]
        elif k == "." and "." in cur:
            return
        else:
            cur += k
        var.set(cur)
        self._refresh()

    def _refresh(self):
        price, qty = self._val(self.price_var), self._val(self.qty_var)
        uname = (self.cur_unit or {}).get("unit_name_en") or self.line.get("unit_name", "Unit")
        txt = []
        if self.factor != 1:
            txt.append("1 %s = %g %s" % (uname, self.factor, self.base_unit))
            txt.append("%g %s = %g %s" % (qty, uname, qty * self.factor, self.base_unit))
        try:
            stock = float(self.product.get("stock_quantity", 0) or 0)
            st = stock / self.factor
            txt.append("In stock: %s %s%s" % (("%g" % round(st, 3)), uname,
                       ("  (%g %s)" % (round(stock, 3), self.base_unit)) if self.factor != 1 else ""))
        except Exception:
            pass
        self.info_var.set("\n".join(txt))
        tot = None
        if self.calc:
            try:
                tot = self.calc(price, qty, uname, self.factor)
            except Exception:
                tot = None
        if tot is None:
            tot = price * qty
        self.total_var.set("Line total   %s SAR" % "{:,.2f}".format(tot))
        try:
            cost = float(self.product.get("purchase_price", 0) or 0) * self.factor
            if self.cur_unit and float(self.cur_unit.get("purchase_price") or 0):
                cost = float(self.cur_unit["purchase_price"])
            profit = price - cost
            margin = (profit / price * 100) if price else 0
            self.profit_var.set("Cost %s   ·   Profit %s   ·   Margin %.1f%%"
                                % ("{:,.2f}".format(cost), "{:,.2f}".format(profit), margin))
        except Exception:
            pass

    def _apply(self):
        price = self._val(self.price_var) if self.can_price else None
        qty = self._val(self.qty_var)
        if qty <= 0:
            try: self.bell()
            except Exception: pass
            return
        unit = self.cur_unit
        self.destroy()
        self.on_apply(price, qty, unit)


# ============================================================
# Cash + Card window — opens when Cash / Card is tapped.
# Two fields (Cash, Card) + number pad: the customer may say
# "20 cash and 20 card". The field you did not touch fills in the
# rest automatically, change is worked out from cash only.
# ============================================================
class PayDialog(tk.Toplevel):
    NAVY, BLUE, INK, MUTED = "#0B1F3A", "#1D4ED8", "#0F172A", "#475569"

    def __init__(self, parent, total, start="cash", on_done=None, prefill=None,
                 party=False, do_print=False, card_on=True, cash_on=True, extras=None):
        super().__init__(parent)
        self.total = round(float(total or 0), 2)
        self.on_done = on_done
        self.party = party
        self.card_on, self.cash_on = card_on, cash_on
        # v6.0: more ways to pay beside Cash / Card (STC Pay, Tabby, Tamara …)
        self.extras = [k for k in (extras or []) if k not in ("cash", "card")]
        self.title("Payment")
        self.configure(bg="white")
        self.transient(parent)
        self.vals = {"cash": "", "card": ""}
        self.auto = {"cash": True, "card": True}      # untouched = filled automatically
        self.fresh = {"cash": True, "card": True}     # first key replaces the content
        for _k in self.extras:
            self.vals[_k], self.auto[_k], self.fresh[_k] = "", False, True
        self.active = "card" if start == "card" and card_on else "cash"
        if start in self.extras:
            self.active = start
        if prefill:
            c, k = float(prefill[0] or 0), float(prefill[1] or 0)
            self.vals.update({"cash": self._fmt(c) if c else "", "card": self._fmt(k) if k else ""})
            self.auto = {k_: False for k_ in self.auto}
            for _k, _a in ((prefill[2] if len(prefill) > 2 else None) or {}).items():
                if _k in self.vals and float(_a or 0) > 0:
                    self.vals[_k] = self._fmt(float(_a))
        elif start in self.extras:
            self.vals[start] = self._fmt(self.total)
            self.auto["cash"] = self.auto["card"] = False
        elif start == "card" and card_on:
            self.vals["card"] = self._fmt(self.total)
        elif cash_on:
            self.vals["cash"] = self._fmt(self.total)
        else:
            self.vals["card"] = self._fmt(self.total); self.active = "card"

        hdr = tk.Frame(self, bg=self.NAVY); hdr.pack(fill="x")
        tk.Label(hdr, text="TOTAL TO PAY", font=("Segoe UI", 10, "bold"), bg=self.NAVY,
                 fg="#A9BCD6").pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text="%s SAR" % "{:,.2f}".format(self.total),
                 font=("Segoe UI", 26, "bold"), bg=self.NAVY, fg="white").pack(
                     side="right", padx=16, pady=6)

        body = tk.Frame(self, bg="white"); body.pack(fill="both", expand=True, padx=16, pady=12)
        left = tk.Frame(body, bg="white"); left.pack(side="left", fill="y")
        right = tk.Frame(body, bg="white"); right.pack(side="left", padx=(16, 0))

        self.tiles = {}
        for key, cap, clr, on in (("cash", "CASH  نقدي", "#15803D", cash_on),
                                  ("card", "CARD  بطاقة", "#1D4ED8", card_on)):
            if not on:
                continue
            f = tk.Frame(left, bg="white", highlightthickness=3, highlightbackground="#D5DCE6",
                         cursor="hand2")
            f.pack(fill="x", pady=(0, 8))
            c1 = tk.Label(f, text=cap, font=("Segoe UI", 9, "bold"), bg="white", fg=clr,
                          anchor="w")
            c1.pack(fill="x", padx=12, pady=(6, 0))
            v = tk.StringVar()
            c2 = tk.Label(f, textvariable=v, font=("Segoe UI", 26, "bold"), bg="white",
                          fg=self.INK, anchor="e", width=11)
            c2.pack(fill="x", padx=12, pady=(0, 6))
            for w in (f, c1, c2):
                w.bind("<Button-1>", lambda e, k=key: self._focus(k))
            self.tiles[key] = (f, v, clr)
        if self.extras:                    # small tiles: STC Pay, Tabby, Tamara …
            try:
                from modules import tenders as _td
            except Exception:
                _td = None
            xr = tk.Frame(left, bg="white"); xr.pack(fill="x", pady=(0, 8))
            for i, key in enumerate(self.extras):
                cap = _td.label(key) if _td else key
                clr = "#7C3AED" if key in ("tabby", "tamara") else "#0E7490"
                f = tk.Frame(xr, bg="white", highlightthickness=3, highlightbackground="#D5DCE6",
                             cursor="hand2")
                f.grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 4), pady=(0, 4))
                xr.grid_columnconfigure(i % 3, weight=1)
                c1 = tk.Label(f, text=cap, font=("Segoe UI", 8, "bold"), bg="white", fg=clr,
                              anchor="w")
                c1.pack(fill="x", padx=8, pady=(4, 0))
                v = tk.StringVar()
                c2 = tk.Label(f, textvariable=v, font=("Segoe UI", 14, "bold"), bg="white",
                              fg=self.INK, anchor="e", width=7)
                c2.pack(fill="x", padx=8, pady=(0, 4))
                for w in (f, c1, c2):
                    w.bind("<Button-1>", lambda e, k=key: self._focus(k))
                self.tiles[key] = (f, v, clr)

        q = tk.Frame(left, bg="white"); q.pack(fill="x", pady=(0, 8))
        tk.Label(q, text="Quick cash", font=("Segoe UI", 8, "bold"), bg="white",
                 fg=self.MUTED).pack(anchor="w")
        qr = tk.Frame(q, bg="white"); qr.pack(fill="x")
        quick = [("Exact", None), ("10", 10), ("20", 20), ("50", 50), ("100", 100),
                 ("200", 200), ("500", 500)]
        for i, (txt, amt) in enumerate(quick):
            tk.Button(qr, text=txt, font=("Segoe UI", 10, "bold"), bg="#E8F0FB", fg="#1E3A8A",
                      relief="flat", cursor="hand2", width=5,
                      command=lambda a=amt: self._quick(a)).grid(
                          row=i // 4, column=i % 4, padx=2, pady=2, sticky="ew", ipady=4)

        self.lbl_state = tk.Label(left, text="", font=("Segoe UI", 15, "bold"), bg="white",
                                  anchor="w")
        self.lbl_state.pack(fill="x", pady=(2, 0))
        self.lbl_sub = tk.Label(left, text="", font=("Segoe UI", 10), bg="white",
                                fg=self.MUTED, anchor="w", justify="left", wraplength=290)
        self.lbl_sub.pack(fill="x")

        # keypad
        pad = tk.Frame(right, bg="white"); pad.pack()
        keys = ["7", "8", "9", "4", "5", "6", "1", "2", "3", ".", "0", "⌫"]
        for i, k in enumerate(keys):
            tk.Button(pad, text=k, font=("Segoe UI", 18, "bold"), bg="white", fg=self.INK,
                      relief="flat", cursor="hand2", width=4, highlightthickness=1,
                      highlightbackground="#C7D0DD",
                      command=lambda kk=k: self._key(kk)).grid(
                          row=i // 3, column=i % 3, padx=3, pady=3, ipady=8)
        tk.Button(pad, text="Clear", font=("Segoe UI", 11, "bold"), bg="#F1F5F9", fg="#334155",
                  relief="flat", cursor="hand2", highlightthickness=1,
                  highlightbackground="#C7D0DD", command=lambda: self._clear()).grid(
                      row=4, column=0, columnspan=3, sticky="ew", padx=3, pady=3, ipady=4)

        foot = tk.Frame(self, bg="#F8FAFC", highlightbackground="#D5DCE6", highlightthickness=1)
        foot.pack(fill="x", side="bottom")
        tk.Button(foot, text="Cancel", font=("Segoe UI", 11), bg="white", fg=self.INK,
                  relief="flat", cursor="hand2", highlightthickness=1,
                  highlightbackground="#C7D0DD", command=self.destroy, padx=16).pack(
                      side="left", padx=12, pady=10, ipady=8)
        self.btn_save = tk.Button(foot, text="Save   Enter", font=("Segoe UI", 14, "bold"),
                                  bg="#15803D", fg="white", relief="flat", cursor="hand2",
                                  activebackground="#166534", activeforeground="white",
                                  command=lambda: self._confirm(False), padx=22)
        self.btn_save.pack(side="right", padx=(6, 12), pady=10, ipady=8)
        tk.Button(foot, text="Save + Print", font=("Segoe UI", 11, "bold"), bg=self.BLUE,
                  fg="white", relief="flat", cursor="hand2", activebackground="#1E40AF",
                  activeforeground="white", command=lambda: self._confirm(True),
                  padx=14).pack(side="right", padx=6, pady=10, ipady=8)

        self.bind("<Key>", self._on_key)
        self.bind("<Return>", lambda e: self._confirm(False))
        self.bind("<KP_Enter>", lambda e: self._confirm(False))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Tab>", lambda e: (self._focus(self._next_key()), "break")[1])
        self._focus(self.active)
        self.update_idletasks()
        w, h = max(self.winfo_reqwidth(), 640), self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            self.geometry("%dx%d+%d+%d" % (w, h, px + max(0, (pw - w) // 2),
                                           py + max(0, (ph - h) // 2)))
        except Exception:
            self.geometry("%dx%d" % (w, h))
        self.grab_set()
        self.focus_force()

    # ── helpers ──
    @staticmethod
    def _fmt(v):
        return ("%.2f" % v).rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else "%d" % round(v)

    def _num(self, key):
        try:
            return round(float(self.vals[key] or 0), 2)
        except ValueError:
            return 0.0

    def _next_key(self):
        keys = list(self.tiles)
        if not keys:
            return self.active
        i = keys.index(self.active) if self.active in keys else -1
        return keys[(i + 1) % len(keys)]

    def _other(self, key):
        """The field that takes what is left: Card for Cash, Cash for Card;
        for STC Pay / Tabby … Cash (or Card) if still untouched."""
        if key in ("cash", "card"):
            o = "card" if key == "cash" else "cash"
            return o if o in self.tiles else None
        for o in ("cash", "card"):
            if o in self.tiles and self.auto.get(o):
                return o
        return None

    def _focus(self, key):
        if key not in self.tiles:
            return
        self.active = key
        self.fresh[key] = True
        self._refresh()

    def _quick(self, amt):
        if "cash" not in self.tiles:
            return
        k = "cash"
        if amt is None:
            card = self._num("card") if not self.auto["card"] or self.vals["card"] else 0.0
            self.vals[k] = self._fmt(max(0.0, round(self.total - card, 2)))
        else:
            self.vals[k] = self._fmt(amt)
        self.auto[k] = False
        self.active = k
        self._after_edit(k)

    def _on_key(self, e):
        ch = e.char
        if ch and ch in "0123456789.":
            self._key(ch)
        elif e.keysym == "BackSpace":
            self._key("⌫")
        elif e.keysym == "Delete":
            self._clear()

    def _clear(self):
        k = self.active
        self.vals[k] = ""
        self.auto[k] = False
        self.fresh[k] = False
        self._after_edit(k)

    def _key(self, ch):
        k = self.active
        cur = self.vals[k]
        if ch == "⌫":
            cur = cur[:-1]
            self.fresh[k] = False
        else:
            if self.fresh[k]:
                cur = ""
                self.fresh[k] = False
            if ch == "." and "." in cur:
                return
            if "." in cur and len(cur.split(".")[1]) >= 2:
                return
            cur += ch
        self.vals[k] = cur
        self.auto[k] = False
        self._after_edit(k)

    def _after_edit(self, key):
        """The other field (if still untouched) takes what is left."""
        o = self._other(key)
        if o and self.auto[o]:
            others = sum(self._num(k) for k in self.vals if k != o)
            rest = round(self.total - others, 2)
            self.vals[o] = self._fmt(rest) if rest > 0.004 else ""
        self._refresh()

    # ── numbers ──
    def extra_amounts(self):
        """{method: amount} typed on the extra tiles (STC Pay, Tabby …)."""
        return {k: self._num(k) for k in self.extras if self._num(k) > 0.004}

    def figures(self):
        cash, card = self._num("cash"), self._num("card")
        ext = round(sum(self.extra_amounts().values()), 2)
        card_eff = min(card, max(0.0, round(self.total - ext, 2)))
        cash_eff = min(cash, max(0.0, round(self.total - card_eff - ext, 2)))
        change = round(max(0.0, cash - cash_eff), 2)
        rest = round(self.total - cash_eff - card_eff - ext, 2)
        return cash, card, cash_eff, card_eff, change, max(rest, 0.0)

    def _noncash_over(self):
        return round(self._num("card") + sum(self.extra_amounts().values()), 2) > self.total + 0.004

    def _paid_text(self, ce, ke):
        parts = ["Cash %s" % "{:,.2f}".format(ce), "Card %s" % "{:,.2f}".format(ke)]
        try:
            from modules import tenders as _td
            parts += ["%s %s" % (_td.label(k), "{:,.2f}".format(a))
                      for k, a in self.extra_amounts().items()]
        except Exception:
            pass
        return "  ·  ".join(parts)

    def _refresh(self):
        for key, (f, v, clr) in self.tiles.items():
            txt = self.vals[key]
            v.set(txt if txt else "0.00")
            f.configure(highlightbackground=clr if key == self.active else "#D5DCE6")
        cash, card, ce, ke, change, rest = self.figures()
        over_card = self._noncash_over()
        if over_card:
            self.lbl_state.configure(text="Card / other is more than the bill", fg="#B91C1C")
            self.lbl_sub.configure(text="Card and the other tenders can only pay up to %s "
                                        "(no change is given on them)." % "{:,.2f}".format(self.total))
        elif rest > 0.004:
            self.lbl_state.configure(text="Balance due  %s" % "{:,.2f}".format(rest),
                                     fg="#B91C1C")
            self.lbl_sub.configure(
                text=("This will be left on the customer's account." if self.party
                      else "Enter more, or pick a customer to leave the rest on account."))
        elif change > 0.004:
            self.lbl_state.configure(text="Change  %s" % "{:,.2f}".format(change), fg="#166534")
            self.lbl_sub.configure(text=self._paid_text(ce, ke))
        else:
            self.lbl_state.configure(text="Paid in full ✓", fg="#166534")
            self.lbl_sub.configure(text=self._paid_text(ce, ke))

    def _confirm(self, print_it):
        cash, card, ce, ke, change, rest = self.figures()
        ext = self.extra_amounts()
        if self._noncash_over():
            self.bell(); return
        if rest > 0.004 and not self.party:
            self.bell(); return
        if ce + ke + sum(ext.values()) <= 0.004 and not self.party:
            self.bell(); return
        cb = self.on_done
        self.destroy()
        if cb:
            if ext:
                cb(cash, card, print_it, ext)
            else:
                cb(cash, card, print_it)


# ============================================================
# POS Settings — compact popup of the most-used POS toggles.
# Writes straight to config settings; a "More Settings…" button
# opens the full settings window when available.
# ============================================================
class POSSettingsDialog(tk.Toplevel):
    OPTIONS = [
        ("pos_fullscreen",       "Open POS full screen",            True),
        ("pos_auto_focus_barcode", "Auto-focus barcode on open",    True),
        ("pos_auto_print",       "Auto print receipt on Save+Print", True),
        ("pos_open_drawer",      "Open cash drawer on Cash sale",   True),
        ("pos_voice_not_found",  "Voice alert when product not found", True),
        ("pos_price_incl_vat",   "Sale price includes VAT (same as Invoice)", True),
        ("apply_vat_pos",        "Apply VAT on POS invoice",        True),
    ]

    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self.title("POS Settings")
        self.configure(bg="#1B3A4B")
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="⚙  POS Settings", font=("Segoe UI", 15, "bold"),
                 bg="#1B3A4B", fg="white").pack(anchor="w", padx=18, pady=(14, 2))
        tk.Label(self, text="Changes apply to this cash register immediately.",
                 font=("Segoe UI", 9), bg="#1B3A4B",
                 fg="#9FC3D6").pack(anchor="w", padx=18, pady=(0, 10))

        card = tk.Frame(self, bg="white"); card.pack(fill="both", expand=True,
                                                     padx=14, pady=(0, 10))
        self.vars = {}
        for key, label, dflt in self.OPTIONS:
            v = tk.BooleanVar(value=(_price_incl() if key == "pos_price_incl_vat"
                                     else cfg.flag(key, dflt)))
            self.vars[key] = v
            tk.Checkbutton(card, text=label, variable=v, font=("Segoe UI", 11),
                           bg="white", fg="#1B3A4B", selectcolor="#EAF4FA",
                           activebackground="white", anchor="w", bd=0,
                           highlightthickness=0, cursor="hand2").pack(
                           fill="x", padx=16, pady=5)

        sz = tk.Frame(card, bg="white"); sz.pack(fill="x", padx=16, pady=(8, 10))
        tk.Label(sz, text="Screen size", font=("Segoe UI", 11, "bold"), bg="white",
                 fg="#1B3A4B").pack(side="left")
        self.size_var = tk.StringVar(value=str(cfg.get("pos_ui_size", "medium") or "medium").lower())
        for val, txt in (("small", "Small"), ("medium", "Medium"), ("large", "Large")):
            tk.Radiobutton(sz, text=txt, value=val, variable=self.size_var,
                           font=("Segoe UI", 11), bg="white", activebackground="white",
                           selectcolor="#EAF4FA", cursor="hand2").pack(side="left", padx=6)
        tk.Label(card, text="(size changes when POS opens next time)", font=("Segoe UI", 8),
                 bg="white", fg="#7F8C8D").pack(anchor="w", padx=16, pady=(0, 8))

        btns = tk.Frame(self, bg="#1B3A4B"); btns.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(btns, text="More Settings…", font=("Segoe UI", 10), bg="#34495E",
                  fg="white", relief="flat", padx=14, pady=8, cursor="hand2",
                  command=self._open_full).pack(side="left")
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#95A5A6",
                  fg="white", relief="flat", padx=16, pady=8, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="✓ Save", font=("Segoe UI", 11, "bold"), bg="#27AE60",
                  fg="white", relief="flat", padx=20, pady=8, cursor="hand2",
                  command=self._save).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        w, h = max(self.winfo_reqwidth(), 360), self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            self.geometry("%dx%d+%d+%d" % (w, h, px + (pw - w) // 2,
                                           py + (ph - h) // 4))
        except Exception:
            self.geometry("%dx%d" % (w, h))

    def _save(self):
        try:
            for key, v in self.vars.items():
                cfg.set(key, bool(v.get()))
            cfg.set("pos_ui_size", self.size_var.get())
            cfg.save_settings()
            if "pos_price_incl_vat" in self.vars:
                _set_price_incl(bool(self.vars["pos_price_incl_vat"].get()))
        except Exception as e:
            messagebox.showerror("POS Settings", str(e)[:200])
            return
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass
        self.destroy()

    def _open_full(self):
        """Open the full Settings screen in its own window, on top of POS."""
        master = self.master
        self.destroy()
        try:
            from ui.settings import SettingsView
            win = tk.Toplevel(master)
            win.title("Settings")
            win.transient(master)
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            w, h = min(1100, sw - 80), min(720, sh - 100)
            win.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))
            host = tk.Frame(win); host.pack(fill="both", expand=True)
            SettingsView(host)
            win.bind("<Escape>", lambda e: win.destroy())
            win.lift(); win.focus_force()
        except Exception as e:
            messagebox.showerror("Settings", "Could not open settings:\n%s" % str(e)[:200])


# ============================================================
# Quick Add Customer — minimal fields so the cashier can create
# and select a customer without leaving the POS. Auto-generates
# a customer code and (if accounting is on) a ledger account.
# ============================================================
class QuickCustomerDialog(tk.Toplevel):
    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.title("New Customer")
        self.configure(bg="#1B3A4B")
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="＋  New Customer", font=("Segoe UI", 15, "bold"),
                 bg="#1B3A4B", fg="white").pack(anchor="w", padx=18, pady=(14, 8))

        card = tk.Frame(self, bg="white"); card.pack(fill="both", expand=True,
                                                     padx=14, pady=(0, 10))
        self.vars = {}

        def field(label, key, hint="", ar=False):
            tk.Label(card, text=label, font=("Segoe UI", 10, "bold"),
                     bg="white", fg="#1B3A4B").pack(anchor="w", padx=16, pady=(8, 0))
            v = tk.StringVar()
            self.vars[key] = v
            e = tk.Entry(card, textvariable=v, font=("Segoe UI", 12),
                         relief="solid", bd=1, bg="white",
                         justify="right" if ar else "left")
            e.pack(fill="x", padx=16, ipady=5)
            if hint:
                tk.Label(card, text=hint, font=("Segoe UI", 8), bg="white",
                         fg="#95A5A6").pack(anchor="w", padx=16)
            return e

        name_e = field("Name (English) *", "name_en")
        field("Name (Arabic)", "name_ar", ar=True)
        field("Phone", "phone")
        field("VAT Registration No.", "vat_no",
              hint="Required for B2B / VAT invoices")

        self.status = tk.StringVar()
        tk.Label(card, textvariable=self.status, font=("Segoe UI", 9, "bold"),
                 bg="white", fg="#C0392B").pack(anchor="w", padx=16, pady=(6, 4))

        btns = tk.Frame(self, bg="#1B3A4B"); btns.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#95A5A6",
                  fg="white", relief="flat", padx=16, pady=8, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="✓ Save & Select", font=("Segoe UI", 11, "bold"),
                  bg="#27AE60", fg="white", relief="flat", padx=18, pady=8,
                  cursor="hand2", command=self._save).pack(side="right")

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        name_e.focus_set()

        self.update_idletasks()
        w, h = max(self.winfo_reqwidth(), 380), self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            self.geometry("%dx%d+%d+%d" % (w, h, px + (pw - w) // 2,
                                           py + (ph - h) // 4))
        except Exception:
            self.geometry("%dx%d" % (w, h))

    def _next_code(self):
        try:
            from modules.doc_numbering import next_party_code
            return next_party_code("customers", "customer_code", cfg.get("cust_prefix", "C"))
        except Exception:
            pass
        try:
            n = (db.execute_scalar(
                "SELECT COUNT(*) FROM customers") or 0) + 1
            for i in range(n, n + 100000):
                code = "C%04d" % i
                if not db.execute_scalar(
                        "SELECT COUNT(*) FROM customers WHERE customer_code=?", (code,)):
                    return code
        except Exception:
            pass
        return "C%04d" % (datetime.now().microsecond % 10000)

    def _save(self):
        name = self.vars["name_en"].get().strip()
        if not name:
            self.status.set("Name (English) is required.")
            return
        code = self._next_code()
        data = {
            "customer_code": code,
            "customer_name_en": name,
            "customer_name_ar": self.vars["name_ar"].get().strip() or name,
            "customer_type": "B2B" if self.vars["vat_no"].get().strip() else "B2C",
            "vat_registration_no": self.vars["vat_no"].get().strip() or None,
            "country_code": "SA",
            "phone": self.vars["phone"].get().strip() or None,
            "is_active": 1,
        }
        try:
            cols = ", ".join(data.keys())
            ph = ", ".join(["?"] * len(data))
            db.execute("INSERT INTO customers (%s) VALUES (%s)" % (cols, ph),
                       tuple(data.values()))
            new_id = db.execute_scalar(
                "SELECT TOP 1 customer_id FROM customers "
                "WHERE customer_code=? ORDER BY customer_id DESC", (code,))
            # ledger account so credit sales can post to this customer
            try:
                from modules import posting
                posting.ensure_party_account("customer", new_id)
            except Exception:
                pass
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err or "duplicate" in err.lower():
                self.status.set("Customer code already exists — try again.")
            else:
                self.status.set(err[:90])
            return
        new_cust = {
            "customer_id": new_id, "customer_code": code,
            "customer_name_en": name,
            "customer_name_ar": data["customer_name_ar"],
            "phone": data["phone"] or "", "vat_no": data["vat_registration_no"] or "",
        }
        self.destroy()
        if self.on_save:
            self.on_save(new_cust)
