# ============================================================
# DayBill ERP - Import item lines from Excel / CSV (v7.12.0)
# Used by Purchase Return ▸ 📥 Import (and any window with the item grid).
#
# The file needs a header row. Column names DayBill understands:
#   item / code / product code / barcode   — which item (code or barcode)
#   qty / quantity                         — how many
#   rate / price / cost                    — optional: the price per unit
# ============================================================
import csv
import os

_CODE = ("code", "item", "item code", "product code", "product_code", "barcode", "sku",
         "item no", "itemcode", "productcode")
_QTY = ("qty", "quantity", "qnty", "pcs")
_RATE = ("rate", "price", "cost", "unit price", "unit_price", "unit cost")


def _norm(h):
    return " ".join(str(h or "").strip().lower().replace("_", " ").split())


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def read_rows(path):
    """[{code, qty, rate}] from an .xlsx / .xls(x) / .csv file."""
    ext = os.path.splitext(path)[1].lower()
    table = []
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        for r in ws.iter_rows(values_only=True):
            table.append(list(r))
        wb.close()
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except Exception:
                dialect = csv.excel
            table = [row for row in csv.reader(f, dialect)]
    table = [r for r in table if r and any(str(c or "").strip() for c in r)]
    if not table:
        return []
    head = [_norm(h) for h in table[0]]

    def find(names):
        return next((i for i, h in enumerate(head) if h in names), None)
    ci, qi, ri = find(_CODE), find(_QTY), find(_RATE)
    start = 1
    if ci is None or qi is None:           # no header: code, qty[, rate]
        ci, qi, ri, start = 0, 1, (2 if len(table[0]) > 2 else None), 0
    out = []
    for r in table[start:]:
        code = str(r[ci] if ci < len(r) and r[ci] is not None else "").strip()
        if code.endswith(".0") and code[:-2].isdigit():      # Excel number → text
            code = code[:-2]
        qty = _num(r[qi]) if qi < len(r) else None
        rate = _num(r[ri]) if ri is not None and ri < len(r) else None
        if code and qty:
            out.append(dict(code=code, qty=qty, rate=rate))
    return out


def match(products, rows, units=None):
    """→ (found [(product, qty, rate)], missing [code]). A barcode of a
    product's other unit (box …) counts that unit's factor."""
    by_code, by_bar = {}, {}
    for p in products or []:
        if p.get("product_code"):
            by_code[str(p["product_code"]).strip().lower()] = p
        if p.get("barcode"):
            by_bar[str(p["barcode"]).strip().lower()] = p
    unit_bar = {}
    for pid, us in (units or {}).items():
        for u in us or []:
            if u.get("barcode"):
                unit_bar[str(u["barcode"]).strip().lower()] = (pid, float(u.get("conversion_factor")
                                                                         or u.get("factor") or 1))
    pid_map = {p.get("product_id"): p for p in products or []}
    found, missing = [], []
    for r in rows:
        k = r["code"].lower()
        p = by_code.get(k) or by_bar.get(k)
        qty, rate = r["qty"], r.get("rate")
        if p is None and k in unit_bar:
            pid, fac = unit_bar[k]
            p = pid_map.get(pid)
            qty = qty * (fac or 1)
            if rate:
                rate = rate / (fac or 1)
        if p is None:
            missing.append(r["code"])
        else:
            found.append((p, qty, rate))
    return found, missing
