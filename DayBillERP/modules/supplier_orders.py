# ============================================================
# DayBill ERP - one-tap supplier orders  (v6.4)
# ------------------------------------------------------------
#   create_from_plan(rows)   reorder suggestions → one SAVED Purchase
#                            Order per supplier (then: WhatsApp each)
#   Receiving(po_id)         goods arrive: scan them against the order →
#                            ordered / received / missing / extra, then
#                            a Purchase Invoice with what really came
# A Purchase Order never moves stock or posts to the books; the
# purchase invoice made from it does (same as Purchase Orders screen).
# ============================================================

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _vat(product_id):
    """(vat_category_id, code, rate) of a product (15 % S when unknown)."""
    try:
        r = db.fetchone("SELECT p.vat_category_id, vc.category_code, vc.vat_rate FROM products p "
                        "LEFT JOIN vat_categories vc ON vc.vat_category_id=p.vat_category_id "
                        "WHERE p.product_id=?", (product_id,)) or {}
    except Exception:
        r = {}
    rate = r.get("vat_rate")
    return r.get("vat_category_id"), (r.get("category_code") or "S"), (15.0 if rate is None else _f(rate))


def _user_id():
    try:
        from modules import permissions as p
        return (p.session_user() or {}).get("user_id")
    except Exception:
        return None


def next_po_number():
    try:
        from modules.doc_numbering import next_number
        return next_number("purchase_orders", "po_number", "PO")
    except Exception:
        n = db.execute_scalar("SELECT COUNT(*) FROM purchase_orders") or 0
        return "PO-%s-%06d" % (date.today().strftime("%Y%m"), int(n) + 1)


def create_po(supplier_id, items, expected_days=7, note="From the reorder plan (Smart Insights)"):
    """items: [{product_id, code, name, name_ar?, qty, unit, unit_cost}] (cost
    before VAT). Saves the order (status 'open') → (po_id, number, total)."""
    sup = db.fetchone("SELECT supplier_id, supplier_name_en, supplier_name_ar, vat_registration_no "
                      "FROM suppliers WHERE supplier_id=?", (int(supplier_id),))
    if not sup:
        raise ValueError("Supplier %s not found." % supplier_id)
    lines = []
    for it in items:
        qty = _f(it.get("qty") or it.get("order_qty"))
        if qty <= 0:
            continue
        price = round(_f(it.get("unit_cost")), 4)
        vid, vcode, rate = _vat(it["product_id"])
        amt = round(qty * price, 2)
        vat = round(amt * rate / 100.0, 2)
        lines.append({"product_id": it["product_id"], "code": it.get("code") or "",
                      "name": it.get("name") or "", "name_ar": it.get("name_ar") or "",
                      "qty": qty, "unit": it.get("unit") or "PCs", "price": price,
                      "amount": amt, "vat_id": vid, "vat_code": vcode, "rate": rate, "vat": vat,
                      "total": round(amt + vat, 2)})
    if not lines:
        raise ValueError("Nothing to order.")
    if not all(l["name_ar"] and l["name"] and l["code"] for l in lines):
        pr = {r["product_id"]: r for r in db.fetchall(
            "SELECT product_id, product_code, product_name_en, product_name_ar FROM products "
            "WHERE product_id IN (%s)" % ",".join(str(int(l["product_id"])) for l in lines)) or []}
        for l in lines:
            p = pr.get(l["product_id"]) or {}
            l["code"] = l["code"] or p.get("product_code") or ""
            l["name"] = l["name"] or p.get("product_name_en") or ""
            l["name_ar"] = l["name_ar"] or p.get("product_name_ar") or ""
    taxable = round(sum(l["amount"] for l in lines), 2)
    vat = round(sum(l["vat"] for l in lines), 2)
    total = round(sum(l["total"] for l in lines), 2)
    today = date.today()
    num = next_po_number()
    with db.transaction():
        if db.execute_scalar("SELECT COUNT(*) FROM purchase_orders WHERE po_number=?", (num,)):
            num = num + "-%d" % (int(db.execute_scalar("SELECT COUNT(*) FROM purchase_orders") or 0) + 1)
        db.execute("INSERT INTO purchase_orders (po_number, po_date, expected_date, supplier_id, "
                   "supplier_name_en, supplier_name_ar, supplier_vat_no, reference, subtotal_amount, "
                   "discount_amount, taxable_amount, vat_amount, total_amount, status, notes_en, created_by) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (num, today.isoformat(), (today + timedelta(days=int(expected_days))).isoformat(),
                    sup["supplier_id"], sup.get("supplier_name_en"), sup.get("supplier_name_ar") or "",
                    sup.get("vat_registration_no") or "", None, taxable, 0, taxable, vat, total,
                    "open", note[:500] if note else None, _user_id()))
        po_id = db.execute_scalar("SELECT po_id FROM purchase_orders WHERE po_number=?", (num,))
        for i, l in enumerate(lines, 1):
            db.execute("INSERT INTO purchase_order_lines (po_id, line_number, product_id, product_code, "
                       "product_name_en, product_name_ar, quantity, unit_of_measure_en, unit_price, "
                       "discount_amount, line_amount, vat_category_id, vat_category_code, vat_rate, "
                       "vat_amount, line_total) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (po_id, i, l["product_id"], l["code"], l["name"], l["name_ar"], l["qty"],
                        l["unit"], l["price"], 0, l["amount"], l["vat_id"], l["vat_code"], l["rate"],
                        l["vat"], l["total"]))
    try:
        from modules import audit
        audit.log("save", "purchase_order", po_id, "%s %.2f (reorder plan)" % (num, total))
    except Exception:
        pass
    return po_id, num, total


def create_from_plan(rows, expected_days=7):
    """Reorder suggestions (Smart Insights / inventory_ai) → one saved order
    per supplier. Rows without a supplier are left out (returned)."""
    by, skipped = {}, []
    for r in rows:
        if not r.get("supplier_id"):
            skipped.append(r)
            continue
        by.setdefault(int(r["supplier_id"]), []).append({
            "product_id": r["product_id"], "code": r.get("code"), "name": r.get("name"),
            "qty": r.get("order_qty") or r.get("qty"), "unit": r.get("unit"),
            "unit_cost": r.get("unit_cost")})
    made = []
    for sid, items in by.items():
        po_id, num, total = create_po(sid, items, expected_days)
        sup = db.fetchone("SELECT supplier_name_en, phone FROM suppliers WHERE supplier_id=?", (sid,)) or {}
        made.append({"po_id": po_id, "number": num, "supplier_id": sid,
                     "supplier": sup.get("supplier_name_en") or "", "phone": sup.get("phone") or "",
                     "lines": len(items), "total": total})
    return made, skipped


# ── goods arrive: scan against the order ─────────────────────
def po_lines(po_id):
    rows = db.fetchall("SELECT l.*, (SELECT TOP 1 ISNULL(conversion_factor,1) FROM product_units u "
                       "WHERE u.product_id=l.product_id AND u.unit_name_en=l.unit_of_measure_en) AS factor "
                       "FROM purchase_order_lines l WHERE l.po_id=? ORDER BY l.line_number", (po_id,)) or []
    out = []
    for r in rows:
        f = _f(r.get("factor")) or 1.0
        out.append({"product_id": r.get("product_id"), "code": r.get("product_code") or "",
                    "name": r.get("product_name_en") or "", "name_ar": r.get("product_name_ar") or "",
                    "unit": r.get("unit_of_measure_en") or "PCs", "factor": f,
                    "qty": _f(r.get("quantity")), "base": _f(r.get("quantity")) * f,
                    "price": _f(r.get("unit_price")), "vat_id": r.get("vat_category_id"),
                    "vat_code": r.get("vat_category_code") or "S",
                    "rate": 15.0 if r.get("vat_rate") is None else _f(r.get("vat_rate"))})
    return out


class Receiving:
    """What came from the supplier, scanned or typed, against the order."""

    def __init__(self, po_id):
        self.po_id = int(po_id)
        self.head = db.fetchone("SELECT * FROM purchase_orders WHERE po_id=?", (self.po_id,)) or {}
        if not self.head:
            raise ValueError("Purchase order not found.")
        self.lines = po_lines(self.po_id)
        self.got = {}                 # product_id → base qty received
        self.extra = {}               # product_id → {name, code, cost} (not on the order)

    def ordered(self, pid):
        return sum(l["base"] for l in self.lines if l["product_id"] == pid)

    def scan(self, code, qty=1.0):
        """A barcode (or code) + how many of the scanned unit → hit dict."""
        from modules import barcode_resolver as BR
        hit = BR.resolve(str(code or "").strip())
        if not hit:
            raise ValueError("Unknown barcode: %s" % code)
        pid = hit["product_id"]
        base = _f(qty) * (_f(hit.get("factor")) or 1.0) * (_f(hit.get("quantity")) or 1.0)
        self.got[pid] = self.got.get(pid, 0.0) + base
        if not any(l["product_id"] == pid for l in self.lines) and pid not in self.extra:
            p = hit.get("product") or {}
            self.extra[pid] = {"name": p.get("product_name_en") or "", "code": p.get("product_code") or "",
                               "name_ar": p.get("product_name_ar") or "",
                               "cost": _f(p.get("purchase_price")) or _f(p.get("average_cost"))}
        return {"product_id": pid, "name": (hit.get("product") or {}).get("product_name_en") or "",
                "unit": hit.get("unit_name") or "", "base_added": base,
                "received": self.got[pid], "ordered": self.ordered(pid),
                "on_order": pid not in self.extra}

    def set_received(self, pid, base_qty):
        self.got[pid] = max(0.0, _f(base_qty))

    def receive_all(self):
        for l in self.lines:
            self.got[l["product_id"]] = self.ordered(l["product_id"])

    def compare(self):
        rows, seen = [], set()
        for l in self.lines:
            pid = l["product_id"]
            if pid in seen:
                continue
            seen.add(pid)
            o, g = self.ordered(pid), self.got.get(pid, 0.0)
            d = g - o
            st = "ok" if abs(d) < 1e-6 else ("short" if d < 0 else "over")
            if g <= 0:
                st = "missing"
            rows.append({"product_id": pid, "code": l["code"], "name": l["name"], "unit": l["unit"],
                         "factor": l["factor"], "ordered": o, "received": g, "diff": d, "status": st})
        for pid, x in self.extra.items():
            g = self.got.get(pid, 0.0)
            if g > 0:
                rows.append({"product_id": pid, "code": x["code"], "name": x["name"], "unit": "PCs",
                             "factor": 1.0, "ordered": 0.0, "received": g, "diff": g, "status": "extra"})
        return rows

    def summary(self):
        rows = self.compare()
        n = {k: sum(1 for r in rows if r["status"] == k) for k in ("ok", "short", "over", "missing", "extra")}
        n["complete"] = not any(n[k] for k in ("short", "over", "missing", "extra"))
        return n

    def invoice_lines(self):
        """Lines for the Purchase Invoice: what really came, at the order's
        prices (whole order units when it divides, else pieces)."""
        out = []
        for r in self.compare():
            g = r["received"]
            if g <= 0:
                continue
            l = next((x for x in self.lines if x["product_id"] == r["product_id"]), None)
            if l:
                f = l["factor"] or 1.0
                if abs(g / f - round(g / f)) < 1e-6:
                    qty, unit, price = round(g / f, 4), l["unit"], l["price"]
                else:
                    qty, unit, price = g, "PCs" if f != 1 else l["unit"], l["price"] / f
                vid, vcode, rate = l["vat_id"], l["vat_code"], l["rate"]
                name, name_ar, code = l["name"], l["name_ar"], l["code"]
            else:
                x = self.extra[r["product_id"]]
                qty, unit, price = g, "PCs", x["cost"]
                vid, vcode, rate = _vat(r["product_id"])
                name, name_ar, code = x["name"], x["name_ar"], x["code"]
            amt = round(qty * price, 2)
            v = round(amt * rate / 100.0, 2)
            out.append({"product_id": r["product_id"], "product_code": code, "product_name_en": name,
                        "product_name_ar": name_ar, "quantity": qty, "unit_of_measure_en": unit,
                        "unit_price": round(price, 4), "discount_percent": 0, "discount_amount": 0,
                        "line_amount": amt, "vat_category_id": vid, "vat_category_code": vcode,
                        "vat_rate": rate, "vat_amount": v, "line_total": round(amt + v, 2)})
        return out

    def missing_text(self):
        """Message for the supplier: what did not come (or was short)."""
        rows = [r for r in self.compare() if r["status"] in ("short", "missing")]
        if not rows:
            return ""
        lines = []
        for r in rows:
            f = r["factor"] or 1.0
            miss = -r["diff"]
            q = "%g %s" % (miss / f, r["unit"]) if abs(miss / f - round(miss / f)) < 1e-6 \
                else "%g PCs" % miss
            lines.append("• %s — %s" % (r["name"], q))
        return ("Order %s: these items did not arrive (or were short):\n%s\nPlease send them. "
                "Thank you." % (self.head.get("po_number") or "", "\n".join(lines)))

    def note(self):
        s = self.summary()
        bits = []
        if s["short"] or s["missing"]:
            bits.append("%d short / missing" % (s["short"] + s["missing"]))
        if s["over"] or s["extra"]:
            bits.append("%d more / extra" % (s["over"] + s["extra"]))
        return "From PO %s%s" % (self.head.get("po_number") or "",
                                  (" · " + ", ".join(bits)) if bits else " · complete")

    def mark_received(self, purchase_id=None):
        db.execute("UPDATE purchase_orders SET status='received', converted_purchase_id=?, "
                   "notes_en=?, updated_at=GETDATE() WHERE po_id=?",
                   (purchase_id, (self.note())[:500], self.po_id))
