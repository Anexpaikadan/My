# ============================================================
# DayBill ERP - Packing Slip / Delivery Note and Item Load Request
# (v7.12.0) — documents that move NO stock and post NO accounts
# ------------------------------------------------------------
#   packing_slip   PS-YYYYMM-000001  what was packed / delivered to a
#                  customer — made by hand or loaded from a Sales Invoice
#                  or a Sales Order; vehicle, driver, number of packages.
#                  Open → Delivered (or Cancelled). A slip without a sales
#                  invoice is a "goods delivered, not invoiced yet" slip.
#   load_request   LR-YYYYMM-000001  a salesman asks the store to load
#                  items on his van: requested and loaded quantity per line.
#                  Open → Loaded (or Cancelled).
#
#   KINDS · save(kind, header, lines, doc_id) · get · docs · delete ·
#   set_status · source_lines(number) · pdf(doc_id, path)
# ============================================================
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

KINDS = {
    "packing_slip": dict(
        title="Packing Slip / Delivery Note", short="Packing Slip", icon="📦", prefix="PS",
        rights="sales", party="Customer", done_word="Delivered", done_qty="Packed",
        statuses=[("open", "Packed"), ("done", "Delivered"), ("cancelled", "Cancelled")],
        accent="#0F766E"),
    "load_request": dict(
        title="Item Load Request", short="Load Request", icon="🚚", prefix="LR",
        rights="inventory", party=None, done_word="Loaded", done_qty="Loaded",
        statuses=[("open", "Requested"), ("done", "Loaded"), ("cancelled", "Cancelled")],
        accent="#1D4ED8"),
}
STATUS_KEYS = ("open", "done", "cancelled")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        db.fetchall("SELECT doc_id FROM simple_docs WHERE 1=0")
        return True
    except Exception:
        return False


def status_label(kind, st):
    return dict(KINDS[kind]["statuses"]).get(st, str(st or "").title())


def next_number(kind):
    from modules.doc_numbering import next_number as _nn
    p = KINDS[kind]["prefix"]
    try:
        return _nn("simple_docs", "doc_number", p)
    except Exception:
        n = int(db.execute_scalar("SELECT COUNT(*) FROM simple_docs WHERE doc_kind=?", (kind,)) or 0)
        return "%s-%06d" % (p, n + 1)


def get(doc_id):
    h = db.fetchone("SELECT * FROM simple_docs WHERE doc_id=?", (int(doc_id),))
    if not h:
        return None, []
    lines = db.fetchall("SELECT * FROM simple_doc_lines WHERE doc_id=? ORDER BY line_number",
                        (int(doc_id),)) or []
    return dict(h), [dict(l) for l in lines]


def save(kind, header, lines, doc_id=None, user_id=None):
    """→ (doc_id, number). header keys: doc_date, customer_id, party_name,
    salesman_id, vehicle_id, route_id, driver_name, source_kind, source_id,
    source_number, packages, needed_date, doc_status, notes."""
    if kind not in KINDS:
        raise ValueError("Unknown document.")
    when = str(header.get("doc_date") or date.today().isoformat())[:10]
    st = header.get("doc_status") or "open"
    if st not in STATUS_KEYS:
        st = "open"
    rows = []
    for ln in lines or []:
        pid = ln.get("product_id")
        q = _f(ln.get("quantity"))
        if not pid:
            continue
        if not (0 < q < 1e7):
            raise ValueError("Quantity must be more than 0 (line %d)." % (len(rows) + 1))
        done = max(0.0, _f(ln.get("done_qty")))
        rows.append(dict(product_id=pid, product_code=ln.get("product_code") or "",
                         product_name_en=ln.get("product_name_en") or "",
                         product_name_ar=ln.get("product_name_ar") or "",
                         quantity=q, unit=ln.get("unit_of_measure_en") or "PCs",
                         done_qty=done, remarks=(str(ln.get("remarks") or "")[:200] or None)))
    if not rows:
        raise ValueError("Add at least one item.")
    if kind == "packing_slip" and not (header.get("customer_id") or
                                        str(header.get("party_name") or "").strip()):
        raise ValueError("Choose the customer (or type the name).")
    if kind == "load_request" and not header.get("salesman_id"):
        raise ValueError("Choose the salesman who asks for the load.")
    vals = dict(doc_date=when, customer_id=header.get("customer_id") or None,
                party_name=(str(header.get("party_name") or "")[:200] or None),
                salesman_id=header.get("salesman_id") or None,
                vehicle_id=header.get("vehicle_id") or None,
                route_id=header.get("route_id") or None,
                driver_name=(str(header.get("driver_name") or "")[:100] or None),
                source_kind=header.get("source_kind") or None,
                source_id=header.get("source_id") or None,
                source_number=(str(header.get("source_number") or "")[:50] or None),
                packages=int(_f(header.get("packages"))) or None,
                needed_date=(str(header.get("needed_date") or "")[:10] or None),
                doc_status=st, notes=(str(header.get("notes") or "")[:500] or None))
    with db.transaction():
        if doc_id:
            number = db.execute_scalar("SELECT doc_number FROM simple_docs WHERE doc_id=?",
                                       (int(doc_id),))
            if not number:
                raise ValueError("This document no longer exists.")
            db.execute("UPDATE simple_docs SET %s, updated_at=GETDATE() WHERE doc_id=?"
                       % ", ".join("%s=?" % k for k in vals), tuple(vals.values()) + (int(doc_id),))
            db.execute("DELETE FROM simple_doc_lines WHERE doc_id=?", (int(doc_id),))
        else:
            number = next_number(kind)
            cols = ["doc_kind", "doc_number"] + list(vals) + ["created_by"]
            db.execute("INSERT INTO simple_docs (%s) VALUES (%s)" % (", ".join(cols),
                                                                     ", ".join("?" * len(cols))),
                       (kind, number) + tuple(vals.values()) + (user_id,))
            doc_id = db.last_identity("simple_docs", "doc_id")
        for i, r in enumerate(rows, 1):
            db.execute("INSERT INTO simple_doc_lines (doc_id, line_number, product_id, product_code, "
                       "product_name_en, product_name_ar, quantity, unit_of_measure_en, done_qty, "
                       "remarks) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (int(doc_id), i, r["product_id"], r["product_code"], r["product_name_en"],
                        r["product_name_ar"], r["quantity"], r["unit"], r["done_qty"], r["remarks"]))
    try:
        from modules import branches as _br
        _br.stamp("simple_docs", doc_id)
    except Exception:
        pass
    try:
        from modules.doc_actions import audit
        audit("edit" if header.get("_edit") else "add", kind, int(doc_id), number)
    except Exception:
        pass
    return int(doc_id), number


def set_status(doc_id, status):
    if status not in STATUS_KEYS:
        return False
    try:
        db.execute("UPDATE simple_docs SET doc_status=?, updated_at=GETDATE() WHERE doc_id=?",
                   (status, int(doc_id)))
        return True
    except Exception:
        return False


def link_invoice(doc_id, invoice_id, invoice_number):
    """v7.13: a packing slip made into a Sales Invoice → it carries the
    invoice number and is Delivered."""
    try:
        db.execute("UPDATE simple_docs SET source_kind='sales', source_id=?, source_number=?, "
                   "doc_status='done', updated_at=GETDATE() WHERE doc_id=?",
                   (invoice_id, invoice_number, int(doc_id)))
        return True
    except Exception:
        return False


def all_done(doc_id):
    """v7.13 Load request: every line loaded in full, status Loaded."""
    try:
        with db.transaction():
            db.execute("UPDATE simple_doc_lines SET done_qty=quantity WHERE doc_id=?", (int(doc_id),))
            db.execute("UPDATE simple_docs SET doc_status='done', updated_at=GETDATE() "
                       "WHERE doc_id=?", (int(doc_id),))
        return True
    except Exception:
        return False


def delete(doc_id):
    try:
        with db.transaction():
            db.execute("DELETE FROM simple_doc_lines WHERE doc_id=?", (int(doc_id),))
            db.execute("DELETE FROM simple_docs WHERE doc_id=?", (int(doc_id),))
        return True
    except Exception:
        return False


def docs(kind, date_from=None, date_to=None, status=None, limit=500):
    if not ready():
        return []
    sql = ("SELECT TOP %d d.*, (SELECT COUNT(*) FROM simple_doc_lines l WHERE l.doc_id=d.doc_id) "
           "AS items, (SELECT SUM(l.quantity) FROM simple_doc_lines l WHERE l.doc_id=d.doc_id) "
           "AS qty FROM simple_docs d WHERE d.doc_kind=?" % int(limit))
    params = [kind]
    if date_from:
        sql += " AND d.doc_date >= ?"
        params.append(str(date_from)[:10])
    if date_to:
        sql += " AND d.doc_date <= ?"
        params.append(str(date_to)[:10])
    if status:
        sql += " AND d.doc_status=?"
        params.append(status)
    sql += " ORDER BY d.doc_date DESC, d.doc_id DESC"
    try:
        return [dict(r) for r in (db.fetchall(sql, tuple(params)) or [])]
    except Exception:
        return []


def source_lines(number):
    """A Sales Invoice or Sales Order by its number → (kind, header, lines)
    or (None, None, [])."""
    n = str(number or "").strip()
    if not n:
        return None, None, []
    for kind, tbl, idc, numc, lt in (
            ("sales", "sales_invoices", "invoice_id", "invoice_number", "sales_invoice_lines"),
            ("sales_order", "sales_orders", "so_id", "so_number", "sales_order_lines")):
        try:
            h = db.fetchone("SELECT * FROM %s WHERE %s=?" % (tbl, numc), (n,))
        except Exception:
            h = None
        if h:
            try:
                ls = db.fetchall("SELECT * FROM %s WHERE %s=? ORDER BY line_number" % (lt, idc),
                                 (h[idc],)) or []
            except Exception:
                ls = []
            return kind, dict(h), [dict(x) for x in ls if x.get("product_id")]
    return None, None, []


# ── print ───────────────────────────────────────────────────
def pdf(doc_id, path):
    """A clean A4 slip / request: header band, party, details, items with
    quantities only (no prices), signatures."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    h, lines = get(doc_id)
    if not h:
        raise ValueError("Document not found.")
    k = KINDS[h["doc_kind"]]
    try:
        comp = db.fetchone("SELECT TOP 1 * FROM company ORDER BY company_id") or {}
    except Exception:
        comp = {}
    from modules import masters as M
    W, H = A4
    m = 16 * mm
    c = canvas.Canvas(path, pagesize=A4)
    acc = colors.HexColor(k["accent"])

    def band():
        c.setFillColor(acc)
        c.rect(0, H - 30 * mm, W, 30 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(m, H - 14 * mm, str(comp.get("company_name_en") or "Company")[:60])
        c.setFont("Helvetica", 8)
        c.drawString(m, H - 20 * mm, str(comp.get("address_en") or comp.get("city_en") or "")[:90])
        c.setFont("Helvetica-Bold", 13)
        c.drawRightString(W - m, H - 14 * mm, k["title"].upper())
        c.setFont("Helvetica", 9)
        c.drawRightString(W - m, H - 20 * mm, "No: %s" % h["doc_number"])
        c.drawRightString(W - m, H - 25 * mm, "Date: %s" % str(h.get("doc_date") or "")[:10])

    band()
    y = H - 38 * mm
    info = []
    if k["party"]:
        info.append((k["party"], h.get("party_name") or ""))
    if h.get("salesman_id"):
        info.append(("Salesman", M.label_of("salesmen", h["salesman_id"])))
    if h.get("route_id"):
        info.append(("Route", M.label_of("routes", h["route_id"])))
    if h.get("vehicle_id"):
        info.append(("Vehicle", M.label_of("vehicles", h["vehicle_id"])))
    if h.get("driver_name"):
        info.append(("Driver", h["driver_name"]))
    if h.get("source_number"):
        info.append(("From", "%s %s" % ("Invoice" if h.get("source_kind") == "sales" else "Order",
                                         h["source_number"])))
    if h.get("packages"):
        info.append(("Packages", str(h["packages"])))
    if h.get("needed_date"):
        info.append(("Needed by", str(h["needed_date"])[:10]))
    info.append(("Status", status_label(h["doc_kind"], h.get("doc_status"))))
    c.setFillColor(colors.HexColor("#222"))
    for i, (lab, val) in enumerate(info):
        col_x = m if i % 2 == 0 else W / 2
        if i % 2 == 0 and i:
            y -= 6 * mm
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#777"))
        c.drawString(col_x, y, lab.upper())
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#222"))
        c.drawString(col_x + 24 * mm, y, str(val)[:48])
    y -= 10 * mm
    cols = [("#", m, "l"), ("Code", m + 10 * mm, "l"), ("Item", m + 34 * mm, "l"),
            ("Qty", W - 70 * mm, "r"), ("Unit", W - 66 * mm, "l"),
            (k["done_qty"], W - 40 * mm, "r"), ("Remark", W - 36 * mm, "l")]

    def head(yy):
        c.setFillColor(acc)
        c.rect(m, yy - 7 * mm, W - 2 * m, 7 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        for name, x, al in cols:
            (c.drawRightString if al == "r" else c.drawString)(x, yy - 5 * mm, name)
        return yy - 7 * mm

    y = head(y)
    tq = 0.0
    c.setFont("Helvetica", 9)
    for i, ln in enumerate(lines, 1):
        if y < 40 * mm:
            c.showPage()
            band()
            y = head(H - 38 * mm)
            c.setFont("Helvetica", 9)
        y -= 6 * mm
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#F3F4F6"))
            c.rect(m, y - 1.8 * mm, W - 2 * m, 6 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#222"))
        q = _f(ln.get("quantity"))
        tq += q
        vals = [str(i), str(ln.get("product_code") or "")[:12],
                str(ln.get("product_name_en") or "")[:44], "%g" % q,
                str(ln.get("unit_of_measure_en") or "")[:8],
                ("%g" % _f(ln.get("done_qty"))) if _f(ln.get("done_qty")) else "",
                str(ln.get("remarks") or "")[:22]]
        for (name, x, al), v in zip(cols, vals):
            (c.drawRightString if al == "r" else c.drawString)(x, y, v)
    y -= 9 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m, y, "%d item(s)" % len(lines))
    c.drawRightString(W - 70 * mm, y, "%g" % tq)
    if h.get("notes"):
        y -= 8 * mm
        c.setFont("Helvetica", 9)
        c.drawString(m, y, "Notes: %s" % str(h["notes"])[:110])
    c.setFont("Helvetica", 9)
    c.setStrokeColor(colors.HexColor("#999"))
    for i, lab in enumerate(("Prepared by", "Checked by", "Received by")):
        x = m + i * (W - 2 * m) / 3
        c.line(x, 26 * mm, x + 50 * mm, 26 * mm)
        c.drawString(x, 21 * mm, lab)
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#999"))
    c.drawCentredString(W / 2, 10 * mm, "Generated by DayBill ERP")
    c.save()
    return path
