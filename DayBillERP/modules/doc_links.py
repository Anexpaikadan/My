# ============================================================
# DayBill ERP - load one document into another (v7.5)
# ------------------------------------------------------------
#   Sales Invoice   → Sales Return       pick the bill, pick items / all,
#   Purchase Invoice → Purchase Return   change quantities (never more than
#                                        sold − already returned)
#   Quotation / Sales Order → Sales Invoice    pick the order, pick lines,
#   Purchase Order          → Purchase Invoice change quantities; what is
#                                        invoiced is counted on the order
#                                        (delivered_qty) → partial / done
#
#   docs(kind, search, party_id, open_only)   the documents to pick from
#   return_lines(mode, src_id, exclude_return_id)  sold / returned / left
#   order_lines(kind, doc_id)                 ordered / delivered / left
#   record_delivery(kind, doc_id, taken, dest_id)  after the invoice saved
#   check_return(mode, ref, lines, return_id)  problems ([] = fine)
#   link(form, kind, doc_id, taken) / after_save(form, dest_id)
# ============================================================
from config.database import db

KINDS = {
    "sales_invoice": {"table": "sales_invoices", "lines": "sales_invoice_lines", "id": "invoice_id",
                      "number": "invoice_number", "date": "invoice_date", "party": "customer_id",
                      "party_name": "customer_name_en", "title": "Sales Invoice"},
    "purchase_invoice": {"table": "purchase_invoices", "lines": "purchase_invoice_lines", "id": "purchase_id",
                         "number": "invoice_number", "date": "invoice_date", "party": "supplier_id",
                         "party_name": "supplier_name_en", "title": "Purchase Invoice"},
    "quotation": {"table": "quotations", "lines": "quotation_lines", "id": "quote_id", "number": "quote_number",
                  "date": "quote_date", "party": "customer_id", "party_name": "customer_name_en",
                  "title": "Quotation", "done": "converted", "conv_col": "converted_invoice_id"},
    "sales_order": {"table": "sales_orders", "lines": "sales_order_lines", "id": "so_id", "number": "so_number",
                    "date": "so_date", "party": "customer_id", "party_name": "customer_name_en",
                    "title": "Sales Order", "done": "converted", "conv_col": "converted_invoice_id"},
    "purchase_order": {"table": "purchase_orders", "lines": "purchase_order_lines", "id": "po_id",
                       "number": "po_number", "date": "po_date", "party": "supplier_id",
                       "party_name": "supplier_name_en", "title": "Purchase Order", "done": "received",
                       "conv_col": "converted_purchase_id"},
}
RETURN_SRC = {"sales": "sales_invoice", "purchase": "purchase_invoice"}
RETURN_TABLES = {"sales": ("sales_returns", "sales_return_lines", "original_invoice_no"),
                 "purchase": ("purchase_returns", "purchase_return_lines", "original_purchase_no")}
ORDERS_FOR = {"sales": ("quotation", "sales_order"), "purchase": ("purchase_order",)}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _has(table):
    try:
        return db.execute_scalar("SELECT OBJECT_ID(?, 'U')", (table,)) is not None
    except Exception:
        return False


def _has_col(table, col):
    try:
        return db.execute_scalar("SELECT COL_LENGTH(?, ?)", (table, col)) is not None
    except Exception:
        return False


def _key(ln):
    return (ln.get("product_id"), str(ln.get("unit_of_measure_en") or "").strip().lower())


# ── documents to pick from ────────────────────────────────────
def docs(kind, search="", party_id=None, open_only=True, limit=200):
    """[{id, number, date, party, total, status}] newest first."""
    k = KINDS[kind]
    if not _has(k["table"]):
        return []
    where, p = ["1=1"], []
    if search:
        where.append("(%s LIKE ? OR %s LIKE ?)" % (k["number"], k["party_name"]))
        p += ["%" + search + "%", "%" + search + "%"]
    if party_id:
        where.append("%s=?" % k["party"])
        p.append(party_id)
    if kind in ("sales_invoice", "purchase_invoice"):
        st = "invoice_status"
        if _has_col(k["table"], st):
            where.append("ISNULL(%s,'') NOT IN ('cancelled','draft')" % st)
        if kind == "sales_invoice" and _has_col(k["table"], "invoice_kind"):
            where.append("ISNULL(invoice_kind,'') <> 'debit'")
        stcol = st if _has_col(k["table"], st) else None
    else:
        stcol = "status"
        if open_only:
            where.append("ISNULL(status,'open') NOT IN ('%s','cancelled')" % k["done"])
    rows = db.fetchall("SELECT TOP %d %s AS id, %s AS number, %s AS d, %s AS party, total_amount AS total%s "
                       "FROM %s WHERE %s ORDER BY %s DESC" % (
                           int(limit), k["id"], k["number"], k["date"], k["party_name"],
                           (", %s AS status" % stcol) if stcol else "", k["table"], " AND ".join(where),
                           k["id"]), tuple(p)) or []
    return [{"id": r["id"], "number": r["number"], "date": str(r["d"] or "")[:10], "party": r["party"] or "",
             "total": _f(r["total"]), "status": r.get("status") or ""} for r in rows]


def header(kind, doc_id):
    k = KINDS[kind]
    return db.fetchone("SELECT * FROM %s WHERE %s=?" % (k["table"], k["id"]), (doc_id,))


def _lines(kind, doc_id):
    k = KINDS[kind]
    return [dict(r) for r in (db.fetchall("SELECT * FROM %s WHERE %s=? ORDER BY line_number"
                                          % (k["lines"], k["id"]), (doc_id,)) or [])]


# ── returns ───────────────────────────────────────────────────
def returned_qty(mode, number, exclude_return_id=None):
    """{(product_id, unit): qty already returned against bill `number`}."""
    t, tl, ref = RETURN_TABLES[mode]
    out = {}
    if not number or not _has(t):
        return out
    q = ("SELECT l.product_id, l.unit_of_measure_en, SUM(l.quantity) AS q FROM %s l JOIN %s r ON "
         "r.return_id=l.return_id WHERE r.%s=? AND ISNULL(r.return_status,'') <> 'cancelled'" % (tl, t, ref))
    p = [number]
    if exclude_return_id:
        q += " AND r.return_id<>?"
        p.append(int(exclude_return_id))
    q += " GROUP BY l.product_id, l.unit_of_measure_en"
    for r in db.fetchall(q, tuple(p)) or []:
        k = _key(r)
        out[k] = out.get(k, 0.0) + _f(r["q"])
    return out


def return_lines(mode, src_id, exclude_return_id=None):
    """The bill's lines with sold / returned / left (what can still go back)."""
    kind = RETURN_SRC[mode]
    h = header(kind, src_id)
    if not h:
        return None, []
    done = returned_qty(mode, h.get("invoice_number"), exclude_return_id)
    used = {}
    out = []
    for ln in _lines(kind, src_id):
        k = _key(ln)
        sold = _f(ln.get("quantity"))
        prev = min(sold, max(0.0, done.get(k, 0.0) - used.get(k, 0.0)))   # same item twice on the bill
        used[k] = used.get(k, 0.0) + prev
        ln.update(_sold=sold, _done=round(prev, 4), _left=round(max(0.0, sold - prev), 4))
        out.append(ln)
    return h, out


def check_return(mode, ref, lines, return_id=None):
    """Problems of a return against its bill ([] = fine): more than sold,
    or more than is left after earlier returns, or an item not on the bill."""
    kind = RETURN_SRC[mode]
    k = KINDS[kind]
    if not ref:
        return []
    h = db.fetchone("SELECT %s AS id FROM %s WHERE invoice_number=?" % (k["id"], k["table"]), (ref,))
    if not h:
        return []
    _h, src = return_lines(mode, h["id"], exclude_return_id=return_id)
    left = {}
    sold = {}
    for ln in src:
        key = _key(ln)
        left[key] = left.get(key, 0.0) + ln["_left"]
        sold[key] = sold.get(key, 0.0) + ln["_sold"]
    want = {}
    names = {}
    for ln in lines:
        if not ln.get("product_id"):
            continue
        key = _key(ln)
        want[key] = want.get(key, 0.0) + _f(ln.get("quantity"))
        names[key] = ln.get("product_name_en") or ln.get("product_code") or ""
    out = []
    for key, q in want.items():
        if key not in sold:
            out.append("%s is not on bill %s." % (names[key], ref))
        elif q > left[key] + 1e-6:
            out.append("%s: %g asked, only %g can go back (sold %g, returned before %g)."
                       % (names[key], q, left[key], sold[key], sold[key] - left[key]))
    return out


# ── orders → invoices ─────────────────────────────────────────
def order_lines(kind, doc_id):
    """The order's lines with ordered / delivered / left."""
    h = header(kind, doc_id)
    if not h:
        return None, []
    out = []
    for ln in _lines(kind, doc_id):
        q = _f(ln.get("quantity"))
        d = _f(ln.get("delivered_qty"))
        ln.update(_sold=q, _done=round(d, 4), _left=round(max(0.0, q - d), 4))
        out.append(ln)
    return h, out


def record_delivery(kind, doc_id, taken, dest_id=None):
    """Count what an invoice took from the order: taken = [{line_id, qty}].
    → the order's new status ('partial' or done)."""
    k = KINDS[kind]
    has_d = _has_col(k["lines"], "delivered_qty")
    with db.transaction():
        if has_d:
            for t in taken:
                if t.get("line_id") and _f(t.get("qty")) > 0:
                    db.execute("UPDATE %s SET delivered_qty=ISNULL(delivered_qty,0)+? WHERE line_id=? AND %s=?"
                               % (k["lines"], k["id"]), (_f(t["qty"]), int(t["line_id"]), int(doc_id)))
            _h, ls = order_lines(kind, doc_id)
            full = all(l["_left"] <= 1e-6 for l in ls)
        else:
            full = True
        status = k["done"] if full else "partial"
        sets, p = ["status=?"], [status]
        if dest_id and k.get("conv_col"):
            sets.append("%s=?" % k["conv_col"])
            p.append(int(dest_id))
        try:
            db.execute("UPDATE %s SET %s, updated_at=GETDATE() WHERE %s=?" % (k["table"], ", ".join(sets), k["id"]),
                       tuple(p) + (int(doc_id),))
        except Exception:
            db.execute("UPDATE %s SET %s WHERE %s=?" % (k["table"], ", ".join(sets), k["id"]),
                       tuple(p) + (int(doc_id),))
    return status


def taken_from(lines):
    """[{line_id, qty}] of picked lines (the _src_line_id each carries)."""
    return [{"line_id": l.get("_src_line_id"), "qty": _f(l.get("quantity"))}
            for l in lines if l.get("_src_line_id")]


def to_grid(lines, qty_key="_pick"):
    """Picked lines → rows for the item grid (quantity = the picked qty,
    amounts scaled; the source line id kept for the delivery count)."""
    out = []
    for ln in lines:
        q = _f(ln.get(qty_key))
        if q <= 0:
            continue
        r = {k: v for k, v in ln.items() if not str(k).startswith("_") and k not in ("line_id", "delivered_qty")}
        orig = _f(ln.get("quantity")) or 1.0
        ratio = q / orig
        r["quantity"] = q
        for m in ("discount_amount", "line_amount", "vat_amount", "line_total"):
            if m in r:
                r[m] = round(_f(r[m]) * ratio, 2)
        r["_src_line_id"] = ln.get("line_id")
        out.append(r)
    return out


# ── the window that loaded an order ───────────────────────────
def link(form, kind, doc_id, taken):
    """Remember on the invoice window which order (and lines) it took;
    after_save() counts the delivery once the invoice is saved."""
    form._order_link = {"kind": kind, "doc_id": int(doc_id), "taken": list(taken)}


def after_save(form, dest_id):
    """Called by the Sales / Purchase Invoice after a save."""
    ol = getattr(form, "_order_link", None)
    if not ol or not dest_id:
        return None
    form._order_link = None                 # once — a later re-save never counts twice
    taken = ol["taken"]
    grid = getattr(form, "line_grid", None) or getattr(form, "grid", None)
    try:                                    # the quantities as saved (changed after loading?)
        now = taken_from(grid.data_lines())
        if now or not taken:
            taken = now
    except Exception:
        pass
    try:
        return record_delivery(ol["kind"], ol["doc_id"], taken, dest_id)
    except Exception:
        return None
