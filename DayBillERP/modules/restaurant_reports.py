# ============================================================
# DayBill ERP - Restaurant reports (v7.0)
# ------------------------------------------------------------
# Shown in Reports ▸ Restaurant when the company uses the Restaurant
# module (needs="restaurant"). Loaded by modules/report_center.py.
#
#   rest_by_type      sales by order type (Dine-in / Takeaway / Delivery)
#                     + other sales without an order, so it adds up to
#                     the day's sales
#   rest_by_table     sales by table (orders, guests, per guest)
#   rest_by_waiter    sales by waiter
#   rest_kot_log      every kitchen ticket line, CANCEL lines in red
#   rest_void         items taken off after the kitchen had them
#                     (and cancelled orders) — the void report
#   rest_ingredients  ingredients used by recipes ("use up on sale")
#
# Only PAID orders count (rest_orders.status 'closed' with a CONFIRMED
# POS bill); money is the bill's own net / VAT / total.
# ============================================================

from collections import OrderedDict, defaultdict

from modules.report_center import report, col, _result, _sum_totals, _q, _q1, _f, _d, _has_table

GROUP = "Restaurant"
NO_TABLES = ["The restaurant tables are not in this database yet (open DayBill again to update it)."]


def _tax():
    try:
        from modules import country
        return country.tax_name()
    except Exception:
        return "VAT"


def _paid(f, t):
    """Paid orders of the period with their bill."""
    return _q("SELECT o.*, si.invoice_number, si.invoice_date, ISNULL(si.taxable_amount,0) AS net, "
              "ISNULL(si.vat_amount,0) AS vat, ISNULL(si.total_amount,0) AS total, "
              "ISNULL(t.table_name,'') AS table_name, ISNULL(a.area_name,'') AS area_name "
              "FROM rest_orders o JOIN sales_invoices si ON si.invoice_id=o.invoice_id "
              "LEFT JOIN rest_tables t ON t.table_id=o.table_id "
              "LEFT JOIN rest_areas a ON a.area_id=t.area_id "
              "WHERE o.status='closed' AND si.invoice_status='confirmed' "
              "AND si.invoice_date BETWEEN ? AND ? ORDER BY si.invoice_date, o.order_id", (f, t))


def _group(rows, keyf, label_key, extra=None):
    by = OrderedDict()
    for o in rows:
        k = keyf(o)
        g = by.setdefault(k, {label_key: k, "orders": 0, "guests": 0, "net": 0.0, "vat": 0.0,
                              "total": 0.0, "minutes": 0.0})
        g["orders"] += 1
        g["guests"] += int(o.get("guests") or 0)
        g["net"] += _f(o.get("net"))
        g["vat"] += _f(o.get("vat"))
        g["total"] += _f(o.get("total"))
        if o.get("closed_at") and o.get("opened_at"):
            try:
                g["minutes"] += (o["closed_at"] - o["opened_at"]).total_seconds() / 60.0
            except Exception:
                pass
        if extra:
            extra(g, o)
    out = []
    grand = sum(g["total"] for g in by.values())
    for g in by.values():
        n = g["orders"] or 1
        g["avg"] = round(g["total"] / n, 2)
        g["per_guest"] = round(g["total"] / g["guests"], 2) if g["guests"] else None
        g["avg_min"] = round(g.pop("minutes") / n, 0)
        g["share"] = round(100.0 * g["total"] / grand, 1) if grand else 0.0
        for k in ("net", "vat", "total"):
            g[k] = round(g[k], 2)
        out.append(g)
    return out


def _money_cols(tax):
    return [col("net", "Net", "money"), col("vat", tax, "money"), col("total", "Total", "money")]


@report("rest_by_type", GROUP, "Sales by Order Type", desc="Dine-in, takeaway and delivery: orders, "
        "guests, net, tax, total, average order — plus sales without an order.", needs="restaurant")
def r_by_type(date_from, date_to, **_):
    tax = _tax()
    cols = [col("type", "Order type", width=170), col("orders", "Orders", "int", 70),
            col("guests", "Guests", "int", 70)] + _money_cols(tax) + [
            col("avg", "Average order", "money"), col("share", "Share %", "pct", 70),
            col("cancelled", "Cancelled orders", "int", 110)]
    if not _has_table("rest_orders"):
        return _result("Sales by Order Type", cols, [], notes=NO_TABLES)
    rows = _group(_paid(date_from, date_to), lambda o: o.get("order_type") or "?", "type")
    order = {"Dine-in": 0, "Takeaway": 1, "Delivery": 2}
    rows.sort(key=lambda r: order.get(r["type"], 9))
    canc = {r["order_type"]: int(r["n"]) for r in _q(
        "SELECT order_type, COUNT(*) AS n FROM rest_orders WHERE status='cancelled' "
        "AND CAST(opened_at AS DATE) BETWEEN ? AND ? GROUP BY order_type", (date_from, date_to))}
    for r in rows:
        r["cancelled"] = canc.pop(r["type"], 0)
    for typ, n in canc.items():
        rows.append({"type": typ, "orders": 0, "guests": 0, "net": 0.0, "vat": 0.0, "total": 0.0,
                     "avg": 0.0, "share": 0.0, "cancelled": n})
    other = _q1("SELECT COUNT(*) AS n, ISNULL(SUM(CASE WHEN ISNULL(si.invoice_type_code,'388')='381' "
                "THEN -1 ELSE 1 END * si.taxable_amount),0) AS net, "
                "ISNULL(SUM(CASE WHEN ISNULL(si.invoice_type_code,'388')='381' THEN -1 ELSE 1 END "
                "* si.vat_amount),0) AS vat, ISNULL(SUM(CASE WHEN ISNULL(si.invoice_type_code,'388')='381' "
                "THEN -1 ELSE 1 END * si.total_amount),0) AS total FROM sales_invoices si "
                "WHERE si.invoice_status='confirmed' AND si.invoice_date BETWEEN ? AND ? AND NOT EXISTS "
                "(SELECT 1 FROM rest_orders o WHERE o.invoice_id=si.invoice_id AND o.status='closed')",
                (date_from, date_to)) or {}
    if int(other.get("n") or 0):
        rows.append({"type": "Other sales (no order)", "orders": int(other["n"]), "guests": None,
                     "net": round(_f(other["net"]), 2), "vat": round(_f(other["vat"]), 2),
                     "total": round(_f(other["total"]), 2), "avg": None, "share": None,
                     "cancelled": None, "_style": "sub"})
    tot = _sum_totals([dict(r, _style=None) for r in rows], ("orders", "guests", "net", "vat", "total",
                                                             "cancelled"), "type", "TOTAL")
    paid = [r for r in rows if not r.get("_style")]
    n = sum(r["orders"] for r in paid)
    t_paid = sum(r["total"] for r in paid)
    return _result("Sales by Order Type", cols, rows, tot,
                   [("Paid orders", n, "int"), ("Order sales", round(t_paid, 2), "money"),
                    ("Average order", round(t_paid / n, 2) if n else 0, "money"),
                    ("All sales", tot["total"], "money")],
                   ["Paid orders by the date of their bill. 'Other sales' are bills without a restaurant "
                    "order (sales invoices, old bills), so the TOTAL is all sales of the period."])


@report("rest_by_table", GROUP, "Sales by Table", desc="Per table: orders, guests, total, average per "
        "order and per guest, minutes a table is used.", needs="restaurant")
def r_by_table(date_from, date_to, **_):
    tax = _tax()
    cols = [col("table", "Table", width=110), col("area", "Area", width=120),
            col("orders", "Orders", "int", 70), col("guests", "Guests", "int", 70)] + _money_cols(tax) + [
            col("avg", "Per order", "money"), col("per_guest", "Per guest", "money"),
            col("avg_min", "Minutes per order", "int", 110), col("share", "Share %", "pct", 70)]
    if not _has_table("rest_orders"):
        return _result("Sales by Table", cols, [], notes=NO_TABLES)
    paid = [o for o in _paid(date_from, date_to) if o.get("table_id")]
    rows = _group(paid, lambda o: o.get("table_name") or "?", "table",
                  extra=lambda g, o: g.__setitem__("area", o.get("area_name") or ""))
    try:
        from modules.restaurant import natural_key
        rows.sort(key=lambda r: (natural_key(r.get("area")), natural_key(r["table"])))
    except Exception:
        pass
    tot = _sum_totals(rows, ("orders", "guests", "net", "vat", "total"), "table", "TOTAL")
    tot["per_guest"] = round(tot["total"] / tot["guests"], 2) if tot["guests"] else None
    tot["avg"] = round(tot["total"] / tot["orders"], 2) if tot["orders"] else None
    best = max(rows, key=lambda r: r["total"]) if rows else None
    return _result("Sales by Table", cols, rows, tot,
                   [("Tables used", len(rows), "int"), ("Dine-in orders", tot["orders"], "int"),
                    ("Guests", tot["guests"], "int"), ("Per guest", tot["per_guest"] or 0, "money"),
                    ("Best table", best["table"] if best else "-", "text")],
                   ["Dine-in orders that were paid, by the table they were paid on (after any move)."])


@report("rest_by_waiter", GROUP, "Sales by Waiter", desc="Per waiter: orders, guests, total, average "
        "order and per guest.", needs="restaurant")
def r_by_waiter(date_from, date_to, **_):
    tax = _tax()
    cols = [col("waiter", "Waiter", width=180), col("orders", "Orders", "int", 70),
            col("guests", "Guests", "int", 70)] + _money_cols(tax) + [
            col("avg", "Per order", "money"), col("per_guest", "Per guest", "money"),
            col("share", "Share %", "pct", 70)]
    if not _has_table("rest_orders"):
        return _result("Sales by Waiter", cols, [], notes=NO_TABLES)
    rows = _group(_paid(date_from, date_to), lambda o: o.get("waiter_name") or "(no waiter)", "waiter")
    rows.sort(key=lambda r: -r["total"])
    tot = _sum_totals(rows, ("orders", "guests", "net", "vat", "total"), "waiter", "TOTAL")
    return _result("Sales by Waiter", cols, rows, tot,
                   [("Waiters", len([r for r in rows if r["waiter"] != "(no waiter)"]), "int"),
                    ("Orders", tot["orders"], "int"), ("Total", tot["total"], "money")])


def _kot_lines(f, t, cancels_only=False):
    return _q("SELECT k.kot_no, k.sent_at, k.status, k.station_name, k.sent_by, o.order_no, o.order_type, "
              "o.status AS order_status, o.cancel_reason, ISNULL(t.table_name,'') AS table_name, "
              "o.waiter_name, kl.product_name, kl.unit_name, kl.quantity, ISNULL(kl.unit_price,0) AS price, "
              "kl.kitchen_note, k.kot_note FROM rest_kot_lines kl JOIN rest_kots k ON k.kot_id=kl.kot_id "
              "JOIN rest_orders o ON o.order_id=k.order_id LEFT JOIN rest_tables t ON t.table_id=o.table_id "
              "WHERE k.kot_date BETWEEN ? AND ?" + (" AND kl.quantity < 0" if cancels_only else "")
              + " ORDER BY k.sent_at, k.kot_id, kl.kot_line_id", (f, t))


def _users():
    try:
        return {r["user_id"]: (r.get("full_name_en") or r.get("username") or "")
                for r in _q("SELECT user_id, username, full_name_en FROM users")}
    except Exception:
        return {}


def _kot_row(r, users):
    q = _f(r["quantity"])
    where = ("Table %s" % r["table_name"]) if r.get("table_name") else r.get("order_type") or ""
    return {"time": str(r["sent_at"])[:16], "kot": r["kot_no"], "order": "#%s" % r["order_no"],
            "where": where, "station": r.get("station_name") or "",
            "item": ("CANCEL  " if q < 0 else "") + (r.get("product_name") or ""),
            "qty": round(q, 3), "note": r.get("kitchen_note") or r.get("kot_note") or "",
            "value": round(q * _f(r.get("price")), 2), "status": (r.get("status") or "").title(),
            "waiter": r.get("waiter_name") or "", "by": users.get(r.get("sent_by"), ""),
            "_style": "neg" if q < 0 else None}


KOT_COLS = [col("time", "Sent", width=120), col("kot", "KOT", "int", 55), col("order", "Order", width=65),
            col("where", "Table / type", width=100), col("station", "Station", width=90),
            col("item", "Item", width=200), col("qty", "Qty", "qty", 60), col("note", "Note", width=140),
            col("value", "Value", "money", 85), col("status", "Status", width=80),
            col("waiter", "Waiter", width=100), col("by", "Sent by", width=100)]


@report("rest_kot_log", GROUP, "Kitchen Tickets (KOT Log)", desc="Every line sent to the kitchen; items "
        "taken off after they were sent show as CANCEL in red.", needs="restaurant")
def r_kot_log(date_from, date_to, **_):
    if not _has_table("rest_kots"):
        return _result("Kitchen Tickets (KOT Log)", KOT_COLS, [], notes=NO_TABLES)
    users = _users()
    rows = [_kot_row(r, users) for r in _kot_lines(date_from, date_to)]
    sent = [r for r in rows if r["qty"] > 0]
    canc = [r for r in rows if r["qty"] < 0]
    kots = len({(r["time"][:10], r["kot"]) for r in rows})
    tot = {"item": "TOTAL", "qty": round(sum(r["qty"] for r in rows), 3),
           "value": round(sum(r["value"] for r in rows), 2)}
    return _result("Kitchen Tickets (KOT Log)", KOT_COLS, rows, tot,
                   [("Tickets", kots, "int"), ("Items sent", round(sum(r["qty"] for r in sent), 3), "qty"),
                    ("Items cancelled", round(-sum(r["qty"] for r in canc), 3), "qty"),
                    ("Cancelled value", round(-sum(r["value"] for r in canc), 2), "money")],
                   ["Value = quantity × the price with tax at the time it was sent."])


@report("rest_void", GROUP, "Cancelled Items (Void Report)", desc="Items taken off an order after the "
        "kitchen had them, and cancelled orders, with who sent them.", needs="restaurant")
def r_void(date_from, date_to, **_):
    cols = KOT_COLS[:9] + [col("reason", "Order / reason", width=170), KOT_COLS[10], KOT_COLS[11]]
    if not _has_table("rest_kots"):
        return _result("Cancelled Items (Void Report)", cols, [], notes=NO_TABLES)
    users = _users()
    rows = []
    for r in _kot_lines(date_from, date_to, cancels_only=True):
        x = _kot_row(r, users)
        x["_style"] = None
        x["reason"] = ("Order cancelled: %s" % (r.get("cancel_reason") or "")).strip(": ") \
            if r.get("order_status") == "cancelled" else "Taken off the order"
        rows.append(x)
    tot = {"item": "TOTAL", "qty": round(sum(r["qty"] for r in rows), 3),
           "value": round(sum(r["value"] for r in rows), 2)}
    by_item = defaultdict(float)
    for r in rows:
        by_item[r["item"]] += -r["value"]
    top = max(by_item.items(), key=lambda x: x[1])[0].replace("CANCEL  ", "") if by_item else "-"
    n_orders = _q1("SELECT COUNT(*) AS n FROM rest_orders WHERE status='cancelled' "
                   "AND CAST(closed_at AS DATE) BETWEEN ? AND ?", (date_from, date_to)) or {}
    return _result("Cancelled Items (Void Report)", cols, rows, tot,
                   [("Lines cancelled", len(rows), "int"), ("Value", round(-tot["value"], 2), "money"),
                    ("Orders cancelled", int(n_orders.get("n") or 0), "int"), ("Most cancelled", top, "text")],
                   ["Only items the kitchen already had. Items removed before Send to Kitchen are in "
                    "Reports ▸ Sales ▸ Cashier Watch."])


@report("rest_ingredients", GROUP, "Ingredient Usage (Recipes)", params=("period", "product"),
        desc="Ingredients taken out of stock by dishes sold (recipes marked 'use up on sale').",
        needs="restaurant")
def r_ingredients(date_from, date_to, product="", **_):
    cols = [col("code", "Code", width=80), col("name", "Ingredient", width=200), col("unit", "Unit", width=70),
            col("qty", "Used", "qty", 90), col("returned", "Back (returns)", "qty", 100),
            col("net", "Net used", "qty", 90), col("cost", "Cost", "money"),
            col("dishes", "Used in", width=260)]
    rows = _q("SELECT it.product_id, p.product_code, p.product_name_en, it.unit_name, "
              "ISNULL(it.qty_out_base,0) AS qout, ISNULL(it.qty_in_base,0) AS qin, "
              "ISNULL(it.unit_cost,0) AS cost, it.notes FROM inventory_transactions it "
              "LEFT JOIN products p ON p.product_id=it.product_id "
              "WHERE it.notes LIKE 'Recipe:%' AND it.txn_date BETWEEN ? AND ?", (date_from, date_to))
    by = OrderedDict()
    pf = (product or "").strip().lower()
    for r in rows:
        if pf and pf not in str(r.get("product_name_en") or "").lower() \
                and pf not in str(r.get("product_code") or "").lower():
            continue
        g = by.setdefault(r["product_id"], {"code": r.get("product_code") or "",
                                            "name": r.get("product_name_en") or "", "unit": r.get("unit_name") or "",
                                            "qty": 0.0, "returned": 0.0, "cost": 0.0, "_d": defaultdict(float)})
        g["qty"] += _f(r["qout"])
        g["returned"] += _f(r["qin"])
        g["cost"] += (_f(r["qout"]) - _f(r["qin"])) * _f(r["cost"])
        dish = str(r.get("notes") or "")[7:].split(" · ")[0].strip()
        g["_d"][dish] += _f(r["qout"]) - _f(r["qin"])
    out = []
    for g in by.values():
        d = g.pop("_d")
        g["net"] = round(g["qty"] - g["returned"], 3)
        g["qty"], g["returned"], g["cost"] = round(g["qty"], 3), round(g["returned"], 3), round(g["cost"], 2)
        g["dishes"] = ", ".join(k for k, _v in sorted(d.items(), key=lambda x: -x[1])[:5] if k)
        out.append(g)
    out.sort(key=lambda r: -r["cost"])
    tot = _sum_totals(out, ("cost",), "name", "TOTAL")
    return _result("Ingredient Usage (Recipes)", cols, out, tot,
                   [("Ingredients", len(out), "int"), ("Cost of ingredients", tot["cost"], "money")],
                   ["Quantities in each ingredient's base unit, at the cost they left stock with. Only "
                    "dishes whose recipe is marked 'use up on sale' take ingredients out of stock."])
