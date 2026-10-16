# ============================================================
# DayBill ERP — PLU Manager (weighing-scale items)
# ------------------------------------------------------------
# Weighing-scale products (fruit, veg, meat, deli) are sold by
# weight. The scale prints an embedded-weight barcode that starts
# with a flag digit, then the PLU code, then the weight/price, then
# a check digit. This screen manages those items:
#   • lists every scale (PLU) product with its PLU code & price
#   • lets you pick the scale BARCODE FORMAT (how the embedded
#     barcode is built) and previews it live
#   • warns on DUPLICATE PLU codes (two products can't share one)
#   • one-click EXPORT of the whole PLU table to a file/path
#     (CSV / TXT / the common scale "PLU.txt" layout)
# ============================================================

import os
import sys
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db

try:
    from modules import permissions as perm
except Exception:
    perm = None


# ── scale barcode formats ───────────────────────────────────
# Each format describes how the scale builds the 13-digit EAN-13:
#   F = flag digit(s), P = PLU digits, W = weight digits,
#   R = price digits, C = check digit (auto)
# The token string is what we show/preview and store in settings.
SCALE_FORMATS = {
    # layouts exactly as modules/scale_barcode.decode reads them
    "EAN13_WEIGHT_2":  {
        "label": "EAN-13 weight  ·  2 F PPPPP WWWWW C   (starts 2, any flag)",
        "tokens": "2FPPPPPWWWWWC", "plu_len": 5, "field": "weight"},
    "EAN13_PRICE_2":   {
        "label": "EAN-13 price   ·  2 F PPPPP RRRRR C   (starts 2, any flag)",
        "tokens": "2FPPPPPRRRRRC", "plu_len": 5, "field": "price"},
    "EAN13_WEIGHT_20": {
        "label": "EAN-13 weight  ·  20 PPPPP WWWWW C    (starts 20)",
        "tokens": "20PPPPPWWWWWC", "plu_len": 5, "field": "weight"},
    "EAN13_PRICE_21":  {
        "label": "EAN-13 price   ·  21 PPPPP RRRRR C    (starts 21)",
        "tokens": "21PPPPPRRRRRC", "plu_len": 5, "field": "price"},
    "PLU_ONLY":        {
        "label": "PLU only  ·  scale looks price up by PLU (no barcode math)",
        "tokens": "PLU", "plu_len": 5, "field": "none"},
}
DEFAULT_FORMAT = "EAN13_WEIGHT_2"


def _fmt_key():
    try:
        return cfg.get("plu_barcode_format", DEFAULT_FORMAT) or DEFAULT_FORMAT
    except Exception:
        return DEFAULT_FORMAT


def _set_fmt_key(key):
    try:
        cfg.set("plu_barcode_format", key)
    except Exception:
        pass


def _ean13_check(d12):
    total = 0
    for i, ch in enumerate(d12):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return (10 - (total % 10)) % 10


def build_scale_barcode(fmt_key, plu, sample_weight=1.234, sample_price=5.00):
    """Preview the embedded barcode a scale would print for this PLU.
    Weight in kg (3 dp) or price in currency (2 dp) fills the W/R field."""
    spec = SCALE_FORMATS.get(fmt_key, SCALE_FORMATS[DEFAULT_FORMAT])
    tokens = spec["tokens"]
    if tokens == "PLU":
        return str(plu)
    try:
        plu_s = str(int(plu))
    except Exception:
        plu_s = "".join(ch for ch in str(plu) if ch.isdigit()) or "0"
    plu_s = plu_s.zfill(spec["plu_len"])[-spec["plu_len"]:]

    # Standard GS1 in-store layout (matches modules/scale_barcode.decode):
    #   prefix(2) + PLU(5) + value(5) + check  — "2" formats use flag 0
    if tokens != "PLU":
        pre = {"EAN13_WEIGHT_20": "20", "EAN13_PRICE_21": "21"}.get(fmt_key, "20")
        plu5 = plu_s.zfill(5)[-5:]
        if spec["field"] == "weight":
            val = str(int(round(sample_weight * 1000))).zfill(5)[-5:]
        else:
            val = str(int(round(sample_price * 100))).zfill(5)[-5:]
        d12 = pre + plu5 + val
        return d12 + str(_ean13_check(d12))
    out = []
    wcount = tokens.count("W")
    rcount = tokens.count("R")
    weight_field = str(int(round(sample_weight * 1000))).zfill(wcount)[-wcount:] \
        if wcount else ""
    price_field = str(int(round(sample_price * 100))).zfill(rcount)[-rcount:] \
        if rcount else ""
    pi = 0
    for ch in tokens:
        if ch == "P":
            out.append(plu_s[pi]); pi += 1
        elif ch == "W":
            out.append(weight_field[0]); weight_field = weight_field[1:]
        elif ch == "R":
            out.append(price_field[0]); price_field = price_field[1:]
        elif ch == "C":
            continue          # check digit is appended after, not inline
        else:
            out.append(ch)
    d12 = "".join(out)[:12].ljust(12, "0")
    return d12 + str(_ean13_check(d12))


# ============================================================
#  Data helpers
# ============================================================
def plu_products():
    """All weighing-scale products with their PLU code and price."""
    try:
        return db.fetchall(
            "SELECT product_id, product_code, product_name_en, "
            "ISNULL(scale_plu,'') AS scale_plu, ISNULL(unit_price,0) AS price, "
            "ISNULL(weight_unit,'kg') AS weight_unit "
            "FROM products WHERE ISNULL(is_weighed,0)=1 AND is_active=1 "
            "ORDER BY scale_plu, product_name_en") or []
    except Exception:
        return []


def duplicate_plus():
    """Return {plu: [product rows]} for any PLU used by 2+ products."""
    seen = {}
    for p in plu_products():
        code = str(p.get("scale_plu", "")).strip()
        if not code:
            continue
        seen.setdefault(code, []).append(p)
    return {k: v for k, v in seen.items() if len(v) > 1}


def write_plu_file(path, prods, fmt):
    """Write the scale file: .csv = full table, anything else = the
    common flat 'PLU<TAB>Name<TAB>Price<TAB>Unit' layout."""
    ext = os.path.splitext(path)[1].lower()
    with open(path, "w", newline="", encoding="utf-8") as fh:
        if ext == ".csv":
            w = csv.writer(fh)
            w.writerow(["PLU", "ItemCode", "Name", "Price", "Unit",
                        "SampleBarcode"])
            for p in prods:
                plu = str(p["scale_plu"]).strip()
                w.writerow([plu, p.get("product_code", ""),
                            p.get("product_name_en", ""),
                            f"{float(p.get('price', 0) or 0):.2f}",
                            p.get("weight_unit", "kg"),
                            build_scale_barcode(fmt, plu)])
        else:
            for p in prods:
                plu = str(p["scale_plu"]).strip()
                fh.write("%s\t%s\t%.2f\t%s\n" % (
                    plu, p.get("product_name_en", ""),
                    float(p.get("price", 0) or 0),
                    p.get("weight_unit", "kg")))
    return path


def auto_export(force=False, folder=None, fmt=None):
    """Settings ▸ PLU Scale ▸ Export automatically: rewrite PLU.txt in the
    export folder. Returns (ok, message). Quiet no-op when switched off
    (unless force=True, used by the 'Export now' button)."""
    if not force and not cfg.flag("plu_export_on_save", False):
        return False, "Automatic export is off."
    folder = str(folder if folder is not None else cfg.get("plu_export_path", "") or "").strip()
    if not folder:
        return False, "Choose the PLU export folder first (Settings ▸ PLU Scale)."
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return False, f"Cannot use folder {folder}: {e}"
    prods = [p for p in plu_products() if str(p.get("scale_plu", "")).strip()]
    if not prods:
        return False, "No scale items have a PLU code yet."
    fmt = fmt or _fmt_key()
    path = os.path.join(folder, "PLU.txt")
    try:
        write_plu_file(path, prods, fmt)
    except Exception as e:
        return False, f"Export failed: {e}"
    try:
        from modules import audit
        audit.log("export", "plu", None, "%d PLU items -> %s (auto)" % (len(prods), path))
    except Exception:
        pass
    return True, f"Exported {len(prods)} PLU item(s) to:\n{path}"


# ============================================================
#  UI
# ============================================================
class PLUManagerView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build(C)
        self._load()

    def _build(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(bar, text="⚖️  PLU Manager  (weighing-scale items)",
                 font=("Segoe UI", 18, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="📤  Export PLU File", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._export).pack(side="right")
        tk.Button(bar, text="🔄 Refresh", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._load).pack(side="right",
                  padx=(0, 8))
        tk.Button(bar, text="⚠ Check Duplicates", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["danger"], relief="flat", padx=12, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=self._check_dups).pack(side="right", padx=(0, 8))

        # ── format picker + live preview ──
        fbar = tk.Frame(self.frame, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        fbar.pack(fill="x", padx=24, pady=(0, 8))
        inner = tk.Frame(fbar, bg=C["card_bg"]); inner.pack(fill="x", padx=14, pady=10)
        tk.Label(inner, text="Scale barcode format:", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
        self.fmt_var = tk.StringVar()
        self._fmt_labels = {v["label"]: k for k, v in SCALE_FORMATS.items()}
        cur = _fmt_key()
        cur_label = SCALE_FORMATS.get(cur, SCALE_FORMATS[DEFAULT_FORMAT])["label"]
        self.fmt_var.set(cur_label)
        cb = ttk.Combobox(inner, textvariable=self.fmt_var,
                          values=list(self._fmt_labels.keys()),
                          state="readonly", font=("Segoe UI", 9), width=48)
        cb.pack(side="left", padx=(8, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self._fmt_changed())
        self.preview_var = tk.StringVar()
        tk.Label(inner, textvariable=self.preview_var, font=("Consolas", 11, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(side="left", padx=(6, 0))
        tk.Button(inner, text="Save format", font=("Segoe UI", 8), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  padx=8, pady=3, command=self._save_fmt).pack(side="right")

        # ── table ──
        card = tk.Frame(self.frame, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        cols = ("plu", "code", "name", "price", "unit", "barcode")
        heads = {"plu": ("PLU", 80), "code": ("Item Code", 110),
                 "name": ("Product", 240), "price": ("Price/kg", 100),
                 "unit": ("Unit", 70), "barcode": ("Sample Barcode", 160)}
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("PLU.Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("PLU.Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background=C.get("heading_bg", C["content_bg"]), foreground="#374151")
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 style="PLU.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for c in cols:
            txt, w = heads[c]
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w,
                             anchor="e" if c == "price" else
                             ("center" if c in ("plu", "unit") else "w"))
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.tag_configure("dup", background="#FDE8E8")
        self.tree.tag_configure("noplu", foreground="#9CA3AF")

        self.count_var = tk.StringVar()
        tk.Label(self.frame, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(anchor="w",
                 padx=24, pady=(0, 12))

    # ── format handling ────────────────────────────────────
    def _current_fmt(self):
        return self._fmt_labels.get(self.fmt_var.get(), DEFAULT_FORMAT)

    def _fmt_changed(self):
        self._load()  # re-preview all sample barcodes with the new format

    def _save_fmt(self):
        _set_fmt_key(self._current_fmt())
        messagebox.showinfo("PLU Format",
                            "Scale barcode format saved. It will be used for "
                            "exports and label previews.")

    # ── data ───────────────────────────────────────────────
    def _load(self):
        self.tree.delete(*self.tree.get_children())
        fmt = self._current_fmt()
        prods = plu_products()
        dups = duplicate_plus()
        dup_codes = set(dups.keys())
        # live preview of the format on a sample 1.234 kg / 5.00 price
        sample_plu = next((p["scale_plu"] for p in prods if p.get("scale_plu")),
                          "12345")
        self.preview_var.set("e.g. " + build_scale_barcode(fmt, sample_plu))
        n_with = 0
        for p in prods:
            plu = str(p.get("scale_plu", "")).strip()
            tags = []
            if not plu:
                tags.append("noplu")
            elif plu in dup_codes:
                tags.append("dup")
            else:
                n_with += 1
            bc = build_scale_barcode(fmt, plu) if plu else "— no PLU —"
            self.tree.insert("", "end", iid=str(p["product_id"]), values=(
                plu or "—", p.get("product_code", ""),
                p.get("product_name_en", ""),
                f"{float(p.get('price', 0) or 0):,.2f}",
                p.get("weight_unit", "kg"), bc), tags=tuple(tags))
        msg = f"{len(prods)} scale item(s)"
        if dups:
            msg += f"  ·  ⚠ {len(dups)} duplicate PLU code(s)"
        self.count_var.set(msg)

    def _check_dups(self):
        dups = duplicate_plus()
        if not dups:
            messagebox.showinfo("Duplicate PLU",
                                "No duplicate PLU codes — every scale item is unique.")
            return
        lines = []
        for code, items in dups.items():
            names = ", ".join(i.get("product_name_en", "")[:24] for i in items)
            lines.append(f"PLU {code}:  {names}")
        messagebox.showwarning(
            "Duplicate PLU Codes",
            "These PLU codes are used by more than one product — the scale "
            "cannot tell them apart:\n\n" + "\n".join(lines) +
            "\n\nGive each product a unique PLU before exporting.")

    # ── export ─────────────────────────────────────────────
    def _export(self):
        if perm and not perm.can("products", "export"):
            messagebox.showwarning("Access Denied",
                                   "You don't have permission to export.")
            return
        prods = [p for p in plu_products() if str(p.get("scale_plu", "")).strip()]
        if not prods:
            messagebox.showinfo("Export PLU",
                                "No scale items have a PLU code yet.")
            return
        dups = duplicate_plus()
        if dups and not messagebox.askyesno(
                "Duplicate PLU",
                f"{len(dups)} duplicate PLU code(s) exist. Export anyway?"):
            return
        path = filedialog.asksaveasfilename(
            title="Export PLU file",
            defaultextension=".txt",
            initialfile="PLU.txt",
            initialdir=str(cfg.get("plu_export_path", "") or "") or None,
            filetypes=[("Scale PLU file", "*.txt"),
                       ("CSV file", "*.csv"),
                       ("All files", "*.*")])
        if not path:
            return
        fmt = self._current_fmt()
        try:
            write_plu_file(path, prods, fmt)
            try:
                from modules import audit
                audit.log("export", "plu", None,
                          "%d PLU items -> %s" % (len(prods), os.path.basename(path)))
            except Exception:
                pass
            if messagebox.askyesno("Export PLU",
                                   "Exported %d PLU item(s) to:\n%s\n\nOpen the "
                                   "folder?" % (len(prods), path)):
                self._open_folder(os.path.dirname(path))
        except Exception as e:
            messagebox.showerror("Export PLU", str(e)[:200])

    def _open_folder(self, folder):
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess; subprocess.Popen(["open", folder])
            else:
                import subprocess; subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass
