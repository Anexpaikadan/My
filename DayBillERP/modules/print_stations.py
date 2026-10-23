# ============================================================
# DayBill ERP - Print stations (v7.5)
# ------------------------------------------------------------
# Where the items of a sale / order are printed for the people who make
# or pick them:
#   Kitchen 1, Kitchen 2, Juice bar …   (restaurant counter / POS sales —
#                                        table orders keep the Restaurant
#                                        kitchen tickets, Restaurant Setup)
#   Warehouse 1, Cold store …           (wholesale / supermarket picking)
#   Tailor Ahmed, Tailor 2 …            (tailor shop — the order goes to
#                                        the tailor picked on the invoice)
# Each station has its own printer, template (80 mm / 58 mm roll, A5, A4),
# copies, and which documents it prints (sales invoice, POS bill, sales
# order). Items go to a station by product, else by category; a station
# with nothing assigned takes every item no other station takes.
#
#   stations() · save_station(data) · delete_station(id)
#   set_category(category_id, station_id|None) · set_product(...)
#   set_product_stations(product_id, [station_id…])   (v7.7 product form ticks)
#   route(lines, assigned=None) → {station_id: [lines]}
#   send(doc_kind, doc_id, assigned=None, reprint=False) → [result]
# ============================================================
import os
import tempfile

from config.database import db

KINDS = [("kitchen", "Kitchen", "🍳"), ("warehouse", "Warehouse", "🏬"),
         ("tailor", "Tailor", "🧵"), ("other", "Other", "🖨")]
TEMPLATES = [("thermal80", "80 mm roll"), ("thermal58", "58 mm roll"), ("a5", "A5 page"),
             ("a4", "A4 page")]
DOC_FLAGS = {"sales": "on_sales", "pos": "on_pos", "sales_order": "on_orders"}
DOC_TITLES = {"sales": "SALE", "pos": "POS BILL", "sales_order": "SALES ORDER"}
last_error = ""


def _i(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ready():
    try:
        return db.execute_scalar("SELECT OBJECT_ID('print_stations','U')") is not None
    except Exception:
        return False


# ── stations ──────────────────────────────────────────────────
def stations(active_only=True, doc_kind=None):
    if not ready():
        return []
    q = "SELECT * FROM print_stations WHERE 1=1"
    if active_only:
        q += " AND is_active=1"
    if doc_kind in DOC_FLAGS:
        q += " AND %s=1" % DOC_FLAGS[doc_kind]
    return [dict(r) for r in (db.fetchall(q + " ORDER BY kind, name") or [])]


def station(station_id):
    r = db.fetchone("SELECT * FROM print_stations WHERE station_id=?", (int(station_id),)) if station_id else None
    return dict(r) if r else None


def next_name(kind):
    """'Kitchen 3' — the next free name of that kind."""
    base = dict((k, n) for k, n, _i_ in KINDS).get(kind, "Station")
    names = {str(s["name"]).lower() for s in stations(active_only=False)}
    n = 1
    while ("%s %d" % (base, n)).lower() in names:
        n += 1
    return "%s %d" % (base, n)


def save_station(data):
    """data: {station_id?, name, kind, printer_name, template, copies,
    employee_id, on_sales, on_pos, on_orders, show_prices, is_active} → id"""
    name = str(data.get("name") or "").strip()[:60]
    if not name:
        raise ValueError("Type the station name (for example Kitchen 1, Warehouse 1, Tailor Ahmed).")
    kind = data.get("kind") if data.get("kind") in dict((k, 1) for k, _n, _i_ in KINDS) else "other"
    tpl = data.get("template") if data.get("template") in dict(TEMPLATES) else "thermal80"
    vals = (name, kind, (str(data.get("printer_name") or "").strip()[:200] or None), tpl,
            max(1, min(_i(data.get("copies"), 1), 5)), _i(data.get("employee_id")) or None,
            1 if data.get("on_sales", True) else 0, 1 if data.get("on_pos", True) else 0,
            1 if data.get("on_orders", True) else 0, 1 if data.get("show_prices") else 0,
            1 if data.get("is_active", True) else 0)
    sid = data.get("station_id")
    dup = db.execute_scalar("SELECT COUNT(*) FROM print_stations WHERE name=? AND station_id<>?",
                            (name, _i(sid)))
    if dup:
        raise ValueError("A station named '%s' already exists." % name)
    if sid:
        db.execute("UPDATE print_stations SET name=?, kind=?, printer_name=?, template=?, copies=?, employee_id=?, "
                   "on_sales=?, on_pos=?, on_orders=?, show_prices=?, is_active=? WHERE station_id=?",
                   vals + (int(sid),))
        return int(sid)
    return int(db.execute_scalar(
        "INSERT INTO print_stations (name, kind, printer_name, template, copies, employee_id, on_sales, on_pos, "
        "on_orders, show_prices, is_active) OUTPUT INSERTED.station_id VALUES (?,?,?,?,?,?,?,?,?,?,?)", vals))


def delete_station(station_id):
    db.execute("DELETE FROM print_stations WHERE station_id=?", (int(station_id),))


# ── which items go where ──────────────────────────────────────
def category_map():
    if not ready():
        return {}
    return {r["category_id"]: r["station_id"] for r in (db.fetchall(
        "SELECT category_id, station_id FROM print_station_map WHERE category_id IS NOT NULL") or [])}


def product_map():
    if not ready():
        return {}
    return {r["product_id"]: r["station_id"] for r in (db.fetchall(
        "SELECT product_id, station_id FROM print_station_map WHERE product_id IS NOT NULL") or [])}


def set_category(category_id, station_id):
    """station_id None = the category is not sent to any station."""
    db.execute("DELETE FROM print_station_map WHERE category_id=?", (int(category_id),))
    if station_id:
        db.execute("INSERT INTO print_station_map (station_id, category_id) VALUES (?,?)",
                   (int(station_id), int(category_id)))


def set_product(product_id, station_id):
    db.execute("DELETE FROM print_station_map WHERE product_id=?", (int(product_id),))
    if station_id:
        db.execute("INSERT INTO print_station_map (station_id, product_id) VALUES (?,?)",
                   (int(station_id), int(product_id)))


def product_map_multi():
    """v7.7: {product_id: [station_id, …]} — a product may print at more
    than one station (Kitchen 1 and the Juice bar; Warehouse 1 and 2)."""
    if not ready():
        return {}
    out = {}
    for r in db.fetchall("SELECT product_id, station_id FROM print_station_map "
                         "WHERE product_id IS NOT NULL ORDER BY map_id") or []:
        out.setdefault(r["product_id"], []).append(r["station_id"])
    return out


def product_stations(product_id):
    """The stations ticked on the product form (empty = by its category)."""
    return product_map_multi().get(int(product_id), []) if product_id else []


def set_product_stations(product_id, station_ids):
    """Product form ▸ Print at: replace the ticked stations of a product."""
    if not ready():
        return
    db.execute("DELETE FROM print_station_map WHERE product_id=?", (int(product_id),))
    for sid in dict.fromkeys(int(x) for x in (station_ids or []) if x):
        db.execute("INSERT INTO print_station_map (station_id, product_id) VALUES (?,?)",
                   (sid, int(product_id)))


def route(lines, doc_kind=None, assigned=None):
    """{station_id: [lines]}. assigned = a station picked on the document
    (tailor / picker): every item goes there."""
    sts = stations(doc_kind=doc_kind)
    if not sts:
        return {}
    by = {s["station_id"]: s for s in sts}
    real = [l for l in lines if l.get("product_id") and _f(l.get("quantity")) > 0]
    if assigned:
        return {int(assigned): real} if int(assigned) in by else {}
    pmap, cmap = product_map_multi(), category_map()
    mapped = {x for v in pmap.values() for x in v} | set(cmap.values())
    catch_all = [s["station_id"] for s in sts if s["station_id"] not in mapped and s["kind"] != "tailor"]
    cats = {}
    ids = sorted({int(l["product_id"]) for l in real})
    if ids:
        for r in db.fetchall("SELECT product_id, category_id FROM products WHERE product_id IN (%s)"
                             % ",".join("?" * len(ids)), tuple(ids)) or []:
            cats[r["product_id"]] = r.get("category_id")
    out = {}
    for l in real:
        pid = int(l["product_id"])
        own = [x for x in pmap.get(pid, []) if x in by]          # ticked on the product
        if not own and cmap.get(cats.get(pid)) in by:              # else its category
            own = [cmap.get(cats.get(pid))]
        targets = own or catch_all
        for t in targets:
            out.setdefault(t, []).append(l)
    return out


# ── the document ──────────────────────────────────────────────
def _doc(doc_kind, doc_id):
    if doc_kind in ("sales", "pos"):
        h = db.fetchone("SELECT invoice_number AS number, invoice_date AS d, customer_name_en AS party, "
                        "notes_en AS notes, created_at FROM sales_invoices WHERE invoice_id=?", (int(doc_id),))
        lines = db.fetchall("SELECT * FROM sales_invoice_lines WHERE invoice_id=? ORDER BY line_number",
                            (int(doc_id),)) or []
    elif doc_kind == "sales_order":
        h = db.fetchone("SELECT so_number AS number, so_date AS d, customer_name_en AS party, notes_en AS notes, "
                        "delivery_date, created_at FROM sales_orders WHERE so_id=?", (int(doc_id),))
        lines = db.fetchall("SELECT * FROM sales_order_lines WHERE so_id=? ORDER BY line_number",
                            (int(doc_id),)) or []
    else:
        return None, []
    return (dict(h) if h else None), [dict(l) for l in lines]


def _num(q):
    s = "%.3f" % _f(q)
    return s.rstrip("0").rstrip(".") if "." in s else s


def entries(st, doc_kind, head, lines, reprint=False):
    """Print entries (restaurant roll format) of one station's slip."""
    from datetime import datetime
    out = [("c", st["name"].upper(), 15, True)]
    if st.get("employee_id"):
        try:
            emp = db.execute_scalar("SELECT full_name_en FROM employees WHERE employee_id=?", (st["employee_id"],))
            if emp:
                out.append(("c", str(emp), 10, False))
        except Exception:
            pass
    out.append(("c", "%s %s%s" % (DOC_TITLES.get(doc_kind, "ORDER"), head.get("number") or "",
                                  "  (REPRINT)" if reprint else ""), 11, True))
    out.append(("lr", str(head.get("d") or "")[:10], datetime.now().strftime("%H:%M"), 9, False))
    if head.get("party"):
        out.append(("l", "Customer: %s" % head["party"], 9, False))
    if head.get("delivery_date"):
        out.append(("l", "Delivery: %s" % str(head["delivery_date"])[:10], 9, True))
    out.append(("rule",))
    total = 0.0
    for l in lines:
        name = l.get("product_name_en") or l.get("product_code") or ""
        unit = l.get("unit_of_measure_en") or ""
        left = "%s x %s%s" % (_num(l.get("quantity")), name, (" (%s)" % unit) if unit else "")
        if st.get("show_prices"):
            amt = _f(l.get("line_total"))
            total += amt
            out.append(("lr", left, "{:,.2f}".format(amt), 11, True))
        else:
            out.append(("l", left, 12, True))
        if l.get("product_name_ar"):
            out.append(("ar", l["product_name_ar"], 10))
        note = l.get("kitchen_note") or l.get("note") or l.get("line_note")
        if note:
            out.append(("l", "   * %s" % note, 9, False))
    out.append(("rule",))
    if st.get("show_prices"):
        out.append(("lr", "Total", "{:,.2f}".format(total), 11, True))
    if head.get("notes"):
        out.append(("l", "Note: %s" % head["notes"], 9, False))
    out.append(("c", "%d item(s)" % len(lines), 9, False))
    out.append(("gap", 6))
    return out


def _page_pdf(path, title, ents, size="a4"):
    """A5 / A4 slip: the same lines on a page."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, A5
    from reportlab.lib.units import mm
    W, H = A5 if size == "a5" else A4
    c = canvas.Canvas(path, pagesize=(W, H))
    try:
        from modules import pdf_invoice as P
        P._register_fonts()
        AR, shape = P._AR_FONT, P._shape_arabic
    except Exception:
        AR, shape = None, None
    y, left, right = H - 15 * mm, 15 * mm, W - 15 * mm
    for en in ents:
        k = en[0]
        if y < 20 * mm:
            c.showPage(); y = H - 15 * mm
        if k == "rule":
            c.line(left, y + 2 * mm, right, y + 2 * mm); y -= 5 * mm; continue
        if k == "gap":
            continue
        if k == "ar":
            if AR and shape:
                c.setFont(AR, en[2] + 1); c.drawRightString(right, y, shape(str(en[1]))); y -= 6 * mm
            continue
        size, bold = en[-2] + 2, en[-1]
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if k == "c":
            c.drawCentredString(W / 2, y, str(en[1]))
        elif k == "lr":
            c.drawString(left, y, str(en[1])); c.drawRightString(right, y, str(en[2]))
        else:
            c.drawString(left, y, str(en[1]))
        y -= size * 0.42 * mm + 3 * mm
    c.showPage(); c.save()
    return path


def slip_pdf(st, doc_kind, head, lines, reprint=False):
    ents = entries(st, doc_kind, head, lines, reprint)
    safe = "".join(ch if ch.isalnum() else "_" for ch in "%s_%s" % (st["name"], head.get("number")))
    path = os.path.join(tempfile.gettempdir(), "daybill_station_%s.pdf" % safe)
    tpl = st.get("template") or "thermal80"
    if tpl in ("a4", "a5"):
        return _page_pdf(path, st["name"], ents, tpl)
    from modules import restaurant as R
    return R._roll_pdf(ents, path, 58 if tpl == "thermal58" else 80)


def slip_text(st, doc_kind, head, lines):
    from modules import restaurant as R
    return R._entries_text(entries(st, doc_kind, head, lines), 32 if st.get("template") == "thermal58" else 42)


def send(doc_kind, doc_id, assigned=None, reprint=False, open_if_no_printer=False):
    """Print the document's items at every station they belong to.
    → [{station, lines, printed, info, pdf}]"""
    global last_error
    last_error = ""
    if not ready() or not doc_id:
        return []
    head, lines = _doc(doc_kind, doc_id)
    if not head:
        return []
    routes = route(lines, doc_kind, assigned)
    out = []
    from modules import printer_service as ps
    for sid, ls in routes.items():
        st = station(sid)
        if not st or not ls:
            continue
        try:
            pdf = slip_pdf(st, doc_kind, head, ls, reprint)
        except Exception as e:
            last_error = str(e)[:200]
            out.append({"station": st["name"], "lines": len(ls), "printed": False, "info": last_error, "pdf": None})
            continue
        printer = st.get("printer_name") or ""
        ok, info = False, ""
        if printer:
            ok = bool(ps.print_pdf(pdf, printer, copies=max(1, _i(st.get("copies"), 1))))
            info = ("sent to %s" % printer) if ok else ("not printed on %s: %s" % (printer, ps.last_error))
        else:
            info = "no printer set — PDF made"
            if open_if_no_printer:
                ps.open_file(pdf)
        try:
            db.execute("INSERT INTO print_station_log (station_id, doc_kind, doc_id, doc_number, lines, printed, info) "
                       "VALUES (?,?,?,?,?,?,?)", (sid, doc_kind, int(doc_id), head.get("number"), len(ls),
                                                  1 if ok else 0, info[:300]))
        except Exception:
            pass
        out.append({"station": st["name"], "lines": len(ls), "printed": ok, "info": info, "pdf": pdf})
    return out


def summary(results):
    if not results:
        return ""
    return " · ".join("%s: %d item(s) %s" % (r["station"], r["lines"], "🖨" if r["printed"] else "📄")
                      for r in results)


def log(limit=50):
    if not ready():
        return []
    return [dict(r) for r in (db.fetchall(
        "SELECT TOP %d l.*, s.name FROM print_station_log l LEFT JOIN print_stations s ON s.station_id=l.station_id "
        "ORDER BY l.log_id DESC" % int(limit)) or [])]
