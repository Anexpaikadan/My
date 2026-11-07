# ============================================================
# DayBill ERP - more reports (v7.12.0)
# ------------------------------------------------------------
# Reports that use the v7.10 Masters (salesmen, routes, brands,
# sections, party categories) and the v7.12 documents, plus a few
# account summaries. Same rules as the Report Center: confirmed
# documents only, sales returns / credit notes taken off.
#
#   Sales Analysis   salesman_sales · salesman_incentive · route_sales ·
#                    brand_sales · section_sales · party_category_sales ·
#                    party_month_sales · customer_visits · promo_sales ·
#                    pending_sales_orders · packing_slips · load_requests
#   Purchases        party_month_purchase · pending_purchase_orders ·
#                    credit_purchase_summary
#   Accounts & VAT   month_ledger · income_expense · transaction_analysis ·
#                    daily_cash_bank
# ============================================================
from collections import OrderedDict
from datetime import date

from modules.report_center import (report, col, _result, _sum_totals, _q, _q1, _f, _d, _has_col,
                                   _has_table, _match, _sales_headers, _sales_lines,
                                   _is_credit_note, _return_headers, _return_lines,
                                   _purchase_headers, _cash_accounts, GROUP_SALES, GROUP_PUR,
                                   GROUP_ACC)

GROUP_AN = "Sales Analysis"
_NEEDS_UPDATE = "This report needs the v7.10 / v7.12 database update (it runs when DayBill starts)."


def _months(f, t):
    """['2026-01', '2026-02' …] from f to t."""
    y, m = int(f[:4]), int(f[5:7])
    out = []
    while (y, m) <= (int(t[:4]), int(t[5:7])) and len(out) < 36:
        out.append("%04d-%02d" % (y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _mlabel(k):
    return date(int(k[:4]), int(k[5:7]), 1).strftime("%b %Y")


def _names(table, idc, *cols):
    if not _has_table(table):
        return {}
    out = {}
    for r in _q("SELECT * FROM %s" % table):
        name = next((r.get(c) for c in cols if r.get(c)), None)
        out[r[idc]] = str(name or r[idc])
    return out


def _r2(d):
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}


def _cust_col(colname):
    """{customer_id: value of customers.<colname>}"""
    if not _has_col("customers", colname):
        return {}
    return {r["customer_id"]: r.get(colname)
            for r in _q("SELECT customer_id, %s FROM customers" % colname)}


# ── sales grouped by something on the bill / the customer ────
def _sales_by(f, t, keyfn, party=""):
    """{key: {bills, net, vat, total, paid, returns}} — credit notes and
    sales returns taken off."""
    by = OrderedDict()
    bill_key = {}
    for h in _sales_headers(f, t):
        if not _match(party, h.get("customer_name_en")):
            continue
        k = keyfn(h)
        bill_key[h["invoice_id"]] = k
        sg = -1 if _is_credit_note(h) else 1
        c = by.setdefault(k, dict(bills=0, net=0.0, vat=0.0, total=0.0, paid=0.0, returns=0.0))
        c["bills"] += 1 if sg > 0 else 0
        c["net"] += sg * _f(h.get("taxable_amount"))
        c["vat"] += sg * _f(h.get("vat_amount"))
        c["total"] += sg * _f(h.get("total_amount"))
        c["paid"] += sg * min(_f(h.get("paid_amount")), _f(h.get("total_amount")))
    for r in _return_headers("sales", f, t):
        k = bill_key.get(r.get("original_invoice_id") or r.get("invoice_id"))
        if k is None:
            k = keyfn(dict(r, salesman_id=None, route_id=None))
        if k not in by:
            if not _match(party, r.get("customer_name_en")):
                continue
            by[k] = dict(bills=0, net=0.0, vat=0.0, total=0.0, paid=0.0, returns=0.0)
        by[k]["returns"] += _f(r.get("total_amount"))
        by[k]["ret_net"] = by[k].get("ret_net", 0.0) + _f(
            r.get("taxable_amount") if r.get("taxable_amount") is not None else r.get("total_amount"))
    return by


def _grouped_result(title, by, label, label_w=220, extra_cols=(), extra=None, notes=None):
    rows = []
    for k, c in by.items():
        r = dict(c)
        r.pop("ret_net", None)
        r["name"] = label(k)
        r["net_total"] = r["total"] - r["returns"]
        r["unpaid"] = r["total"] - r["paid"]
        if extra:
            extra(k, r)
        rows.append(_r2(r))
    rows.sort(key=lambda r: -r["net_total"])
    cols = [col("name", title.split(" wise")[0].split("-wise")[0], width=label_w),
            col("bills", "Bills", "int", 60), col("net", "Net", "money"), col("vat", "VAT", "money"),
            col("total", "Total", "money"), col("returns", "Returns", "money"),
            col("net_total", "Net total", "money"), col("paid", "Collected", "money"),
            col("unpaid", "Unpaid", "money")] + list(extra_cols)
    keys = ["bills", "net", "vat", "total", "returns", "net_total", "paid", "unpaid"] + \
        [c["key"] for c in extra_cols if c["kind"] in ("money", "int", "qty")]
    tot = _sum_totals(rows, keys, "name", "TOTAL")
    return _result(title, cols, rows, tot, notes=notes)


@report("salesman_sales", GROUP_AN, "Salesman-wise Sales & Collection", params=("period", "party"),
        desc="Bills, sales, returns, money collected and unpaid per salesman (Masters ▸ Salesmen).")
def r_salesman_sales(date_from, date_to, party="", **_):
    if not _has_col("sales_invoices", "salesman_id"):
        return _result("Salesman-wise Sales & Collection", [], [], notes=[_NEEDS_UPDATE])
    names = _names("salesmen", "salesman_id", "name_en")
    cust_sm = _cust_col("salesman_id")
    by = _sales_by(date_from, date_to,
                   lambda h: h.get("salesman_id") or cust_sm.get(h.get("customer_id")), party)
    return _grouped_result("Salesman-wise Sales & Collection", by,
                           lambda k: names.get(k, "(no salesman)"),
                           notes=["A bill without a salesman counts for its customer's salesman."])


@report("salesman_incentive", GROUP_AN, "Salesman Incentive / Commission",
        desc="Each salesman's net sales against his monthly target, and the commission earned "
             "(Masters ▸ Salesmen ▸ Commission %).")
def r_salesman_incentive(date_from, date_to, **_):
    if not _has_table("salesmen") or not _has_col("sales_invoices", "salesman_id"):
        return _result("Salesman Incentive / Commission", [], [], notes=[_NEEDS_UPDATE])
    sm = {r["salesman_id"]: r for r in _q("SELECT * FROM salesmen")}
    cust_sm = _cust_col("salesman_id")
    by = _sales_by(date_from, date_to,
                   lambda h: h.get("salesman_id") or cust_sm.get(h.get("customer_id")))
    months = max(1, len(_months(date_from, date_to)))
    rows = []
    for sid, s in sm.items():
        c = by.get(sid, {})
        net = _f(c.get("net")) - _f(c.get("ret_net")) if c else 0.0
        target = _f(s.get("monthly_target")) * months
        pct = _f(s.get("commission_pct"))
        if not c and not target:
            continue
        rows.append(_r2(dict(name=s.get("name_en") or "", bills=c.get("bills", 0), net=net,
                             target=target, achieved=(net / target * 100.0) if target else None,
                             comm_pct=pct, commission=net * pct / 100.0,
                             short=max(0.0, target - net) if target else 0.0)))
    rows.sort(key=lambda r: -r["net"])
    cols = [col("name", "Salesman", width=200), col("bills", "Bills", "int", 60),
            col("net", "Net sales", "money"), col("target", "Target", "money"),
            col("achieved", "Achieved %", "pct", 90), col("short", "Short of target", "money"),
            col("comm_pct", "Comm. %", "pct", 70), col("commission", "Commission", "money")]
    tot = _sum_totals(rows, ("bills", "net", "target", "short", "commission"), "name")
    return _result("Salesman Incentive / Commission", cols, rows, tot,
                   [("Commission to pay", tot["commission"], "money")],
                   ["Net sales = sales after returns, without VAT. Target = monthly target × "
                    "%d month(s) in the period." % months])


@report("route_sales", GROUP_AN, "Route / Area-wise Sales", params=("period", "party"),
        desc="Sales and collection per sales route / area (the bill's route, else the customer's).")
def r_route_sales(date_from, date_to, party="", **_):
    if not _has_table("sales_routes"):
        return _result("Route / Area-wise Sales", [], [], notes=[_NEEDS_UPDATE])
    names = _names("sales_routes", "route_id", "name_en")
    cust_rt = _cust_col("route_id")
    has = _has_col("sales_invoices", "route_id")
    by = _sales_by(date_from, date_to,
                   lambda h: (h.get("route_id") if has else None) or cust_rt.get(h.get("customer_id")),
                   party)
    return _grouped_result("Route / Area-wise Sales", by, lambda k: names.get(k, "(no route)"))


@report("party_category_sales", GROUP_AN, "Party Category-wise Sales", params=("period", "party"),
        desc="Sales per kind of customer — Wholesale, Retail, VIP … (Masters ▸ Party Categories).")
def r_party_category_sales(date_from, date_to, party="", **_):
    if not _has_table("party_categories"):
        return _result("Party Category-wise Sales", [], [], notes=[_NEEDS_UPDATE])
    names = _names("party_categories", "party_category_id", "name_en")
    cat = _cust_col("party_category_id")
    by = _sales_by(date_from, date_to, lambda h: cat.get(h.get("customer_id")), party)
    return _grouped_result("Party Category-wise Sales", by, lambda k: names.get(k, "(no category)"))


# ── item sales grouped by a product field ────────────────────
def _items_by(f, t, keyfn, product=""):
    prods = {r["product_id"]: r for r in _q("SELECT * FROM products")}
    by = OrderedDict()
    for ln in _sales_lines(f, t):
        p = prods.get(ln.get("product_id")) or {}
        if not _match(product, ln.get("product_name_en"), ln.get("product_code")):
            continue
        sg = -1 if str(ln.get("invoice_type_code") or "388") == "381" else 1
        k = keyfn(p)
        c = by.setdefault(k, dict(items=set(), qty=0.0, net=0.0, vat=0.0, total=0.0, ret=0.0))
        c["items"].add(ln.get("product_id"))
        c["qty"] += sg * _f(ln.get("quantity"))
        c["net"] += sg * _f(ln.get("line_amount"))
        c["vat"] += sg * _f(ln.get("vat_amount"))
        c["total"] += sg * _f(ln.get("line_total"))
    for ln in _return_lines("sales", f, t):
        p = prods.get(ln.get("product_id")) or {}
        if not _match(product, ln.get("product_name_en"), ln.get("product_code")):
            continue
        k = keyfn(p)
        c = by.setdefault(k, dict(items=set(), qty=0.0, net=0.0, vat=0.0, total=0.0, ret=0.0))
        c["ret"] += _f(ln.get("line_amount"))
        c["qty"] -= _f(ln.get("quantity"))
    return by


def _items_result(title, head, by, label):
    rows = []
    grand = sum(c["net"] - c["ret"] for c in by.values()) or 0.0
    for k, c in by.items():
        net = c["net"] - c["ret"]
        rows.append(_r2(dict(name=label(k), items=len(c["items"]), qty=c["qty"], net=c["net"],
                             ret=c["ret"], net_after=net, vat=c["vat"],
                             share=(net / grand * 100.0) if grand else 0.0)))
    rows.sort(key=lambda r: -r["net_after"])
    cols = [col("name", head, width=220), col("items", "Items", "int", 60), col("qty", "Qty", "qty"),
            col("net", "Sales", "money"), col("ret", "Returns", "money"),
            col("net_after", "Net sales", "money"), col("vat", "VAT", "money"),
            col("share", "Share %", "pct", 70)]
    tot = _sum_totals(rows, ("items", "qty", "net", "ret", "net_after", "vat"), "name")
    return _result(title, cols, rows, tot, notes=["Amounts without VAT; returns taken off."])


@report("brand_sales", GROUP_AN, "Brand-wise Sales", params=("period", "product"),
        desc="Quantity and net sales per brand.")
def r_brand_sales(date_from, date_to, product="", **_):
    names = _names("product_brands", "brand_id", "brand_name_en")
    by = _items_by(date_from, date_to, lambda p: p.get("brand_id"), product)
    return _items_result("Brand-wise Sales", "Brand", by, lambda k: names.get(k, "(no brand)"))


@report("section_sales", GROUP_AN, "Section-wise Sales", params=("period", "product"),
        desc="Quantity and net sales per section (Masters ▸ Sections).")
def r_section_sales(date_from, date_to, product="", **_):
    if not _has_col("products", "section_id"):
        return _result("Section-wise Sales", [], [], notes=[_NEEDS_UPDATE])
    names = _names("product_sections", "section_id", "name_en")
    by = _items_by(date_from, date_to, lambda p: p.get("section_id"), product)
    return _items_result("Section-wise Sales", "Section", by, lambda k: names.get(k, "(no section)"))


@report("promo_sales", GROUP_AN, "Promotional / Offer Sales", params=("period", "product"),
        desc="What each offer sold: lines, quantity, sales and the discount it gave.")
def r_promo_sales(date_from, date_to, product="", **_):
    if not _has_col("sales_invoice_lines", "offer_id"):
        return _result("Promotional / Offer Sales", [], [], notes=[_NEEDS_UPDATE])
    names = _names("offers", "offer_id", "offer_name")
    by = OrderedDict()
    for ln in _sales_lines(date_from, date_to):
        if not ln.get("offer_id"):
            continue
        if not _match(product, ln.get("product_name_en"), ln.get("product_code")):
            continue
        sg = -1 if str(ln.get("invoice_type_code") or "388") == "381" else 1
        c = by.setdefault(ln["offer_id"], dict(bills=set(), lines=0, qty=0.0, net=0.0, disc=0.0))
        c["bills"].add(ln.get("invoice_id"))
        c["lines"] += 1
        c["qty"] += sg * _f(ln.get("quantity"))
        c["net"] += sg * _f(ln.get("line_amount"))
        c["disc"] += sg * _f(ln.get("discount_amount"))
    rows = [_r2(dict(name=names.get(k, ln_text(k)), bills=len(c["bills"]), lines=c["lines"],
                     qty=c["qty"], net=c["net"], disc=c["disc"])) for k, c in by.items()]
    rows.sort(key=lambda r: -r["net"])
    cols = [col("name", "Offer", width=240), col("bills", "Bills", "int", 60),
            col("lines", "Lines", "int", 60), col("qty", "Qty", "qty"),
            col("net", "Net sales", "money"), col("disc", "Discount given", "money")]
    tot = _sum_totals(rows, ("bills", "lines", "qty", "net", "disc"), "name")
    return _result("Promotional / Offer Sales", cols, rows, tot)


def ln_text(k):
    return "Offer #%s" % k


# ── month-wise per party ─────────────────────────────────────
def _month_matrix(title, head, headers, datek, namek, idk, party, notes=None):
    ms = _months(*headers["period"])
    by = OrderedDict()
    for h in headers["rows"]:
        name = h.get(namek) or "(no name)"
        if not _match(party, name):
            continue
        sg = -1 if _is_credit_note(h) else 1
        r = by.setdefault(h.get(idk) or name, OrderedDict(name=name))
        mk = _d(h.get(datek))[:7]
        r[mk] = r.get(mk, 0.0) + sg * _f(h.get("total_amount"))
    rows = []
    for r in by.values():
        r["total"] = sum(_f(r.get(m)) for m in ms)
        rows.append(_r2(dict(r)))
    rows.sort(key=lambda r: -r["total"])
    cols = [col("name", head, width=200)] + [col(m, _mlabel(m), "money", 95) for m in ms] + \
        [col("total", "Total", "money")]
    tot = _sum_totals(rows, ms + ["total"], "name")
    return _result(title, cols, rows, tot, notes=notes or ["Bill totals with VAT; credit notes taken off."])


@report("party_month_sales", GROUP_AN, "Party Month-wise Sales", params=("period", "party"),
        desc="Each customer's sales month by month.")
def r_party_month_sales(date_from, date_to, party="", **_):
    return _month_matrix("Party Month-wise Sales", "Customer",
                         {"period": (date_from, date_to),
                          "rows": _sales_headers(date_from, date_to)},
                         "invoice_date", "customer_name_en", "customer_id", party)


@report("party_month_purchase", GROUP_PUR, "Party Month-wise Purchases", params=("period", "party"),
        desc="Each supplier's purchases month by month.")
def r_party_month_purchase(date_from, date_to, party="", **_):
    return _month_matrix("Party Month-wise Purchases", "Supplier",
                         {"period": (date_from, date_to),
                          "rows": _purchase_headers(date_from, date_to)},
                         "invoice_date", "supplier_name_en", "supplier_id", party,
                         ["Bill totals with VAT."])


@report("customer_visits", GROUP_AN, "Customer Visits", params=("period", "party"),
        desc="How often each customer came: bills, days, first and last visit, average bill.")
def r_customer_visits(date_from, date_to, party="", **_):
    by = OrderedDict()
    for h in _sales_headers(date_from, date_to):
        if _is_credit_note(h) or not h.get("customer_id"):
            continue
        name = h.get("customer_name_en") or "(no name)"
        if not _match(party, name):
            continue
        c = by.setdefault(h["customer_id"], dict(name=name, bills=0, days=set(), total=0.0,
                                                 first="", last=""))
        d = _d(h.get("invoice_date"))
        c["bills"] += 1
        c["days"].add(d)
        c["total"] += _f(h.get("total_amount"))
        c["first"] = min(c["first"] or d, d)
        c["last"] = max(c["last"], d)
    today = date.today()
    rows = []
    for c in by.values():
        try:
            since = (today - date.fromisoformat(c["last"])).days
        except Exception:
            since = None
        rows.append(_r2(dict(name=c["name"], bills=c["bills"], days=len(c["days"]),
                             first=c["first"], last=c["last"], since=since, total=c["total"],
                             avg=c["total"] / c["bills"] if c["bills"] else 0.0)))
    rows.sort(key=lambda r: (-r["days"], -r["total"]))
    cols = [col("name", "Customer", width=220), col("bills", "Bills", "int", 60),
            col("days", "Days visited", "int", 85), col("first", "First visit", "date", 95),
            col("last", "Last visit", "date", 95), col("since", "Days since", "int", 80),
            col("total", "Total bought", "money"), col("avg", "Average bill", "money")]
    tot = _sum_totals(rows, ("bills", "days", "total"), "name")
    return _result("Customer Visits", cols, rows, tot)


# ── orders still to deliver / receive ────────────────────────
def _pending(title, head_tbl, line_tbl, idc, numc, datec, partyc, party, party_head):
    if not _has_table(head_tbl) or not _has_col(line_tbl, "delivered_qty"):
        return _result(title, [], [], notes=[_NEEDS_UPDATE])
    rows = []
    for r in _q("SELECT h.%s AS num, h.%s AS d, h.%s AS party, ISNULL(h.status,'open') AS st, "
                "l.product_code, l.product_name_en, l.quantity, l.delivered_qty, l.unit_price, "
                "l.unit_of_measure_en FROM %s l JOIN %s h ON h.%s=l.%s "
                "WHERE LOWER(ISNULL(h.status,'open')) NOT IN ('cancelled','closed','converted',"
                "'done') AND ISNULL(l.quantity,0) > ISNULL(l.delivered_qty,0) "
                "ORDER BY h.%s, h.%s"
                % (numc, datec, partyc, line_tbl, head_tbl, idc, idc, datec, numc)):
        if not _match(party, r.get("party"), r.get("num"), r.get("product_name_en")):
            continue
        left = _f(r.get("quantity")) - _f(r.get("delivered_qty"))
        rows.append(_r2(dict(num=r["num"], d=_d(r.get("d")), party=r.get("party") or "",
                             code=r.get("product_code") or "", item=r.get("product_name_en") or "",
                             qty=_f(r.get("quantity")), done=_f(r.get("delivered_qty")),
                             left=left, unit=r.get("unit_of_measure_en") or "",
                             value=left * _f(r.get("unit_price")), st=str(r.get("st")).title())))
    cols = [col("num", "Order", width=130), col("d", "Date", "date", 90),
            col("party", party_head, width=180), col("code", "Code", width=80),
            col("item", "Item", width=200), col("qty", "Ordered", "qty"),
            col("done", "Done", "qty"), col("left", "Pending", "qty"), col("unit", "Unit", width=60),
            col("value", "Pending value", "money"), col("st", "Status", width=80)]
    tot = _sum_totals(rows, ("qty", "done", "left", "value"), "num")
    return _result(title, cols, rows, tot,
                   [("Orders", len({r["num"] for r in rows}), "int"),
                    ("Pending value", tot["value"], "money")],
                   ["Every order line not fully done, whatever its date. Value without VAT."])


@report("pending_sales_orders", GROUP_AN, "Pending Sales Orders", params=("period", "party"),
        desc="Sales order lines not yet invoiced / delivered.")
def r_pending_sales_orders(date_from, date_to, party="", **_):
    return _pending("Pending Sales Orders", "sales_orders", "sales_order_lines", "so_id",
                    "so_number", "so_date", "customer_name_en", party, "Customer")


@report("pending_purchase_orders", GROUP_PUR, "Pending Purchase Orders (in transit)",
        params=("period", "party"),
        desc="Purchase order lines the supplier has not delivered yet.")
def r_pending_purchase_orders(date_from, date_to, party="", **_):
    return _pending("Pending Purchase Orders (in transit)", "purchase_orders",
                    "purchase_order_lines", "po_id", "po_number", "po_date", "supplier_name_en",
                    party, "Supplier")


@report("credit_purchase_summary", GROUP_PUR, "Credit Purchase Summary", params=("period", "party"),
        desc="Purchases on credit per supplier: bills, total, paid and still owed.")
def r_credit_purchase_summary(date_from, date_to, party="", **_):
    by = OrderedDict()
    for h in _purchase_headers(date_from, date_to):
        tot, paid = _f(h.get("total_amount")), min(_f(h.get("paid_amount")), _f(h.get("total_amount")))
        if tot - paid < 0.005:
            continue
        name = h.get("supplier_name_en") or "(no name)"
        if not _match(party, name):
            continue
        c = by.setdefault(h.get("supplier_id") or name, dict(name=name, bills=0, total=0.0, paid=0.0,
                                                             oldest=""))
        c["bills"] += 1
        c["total"] += tot
        c["paid"] += paid
        d = _d(h.get("invoice_date"))
        c["oldest"] = min(c["oldest"] or d, d)
    rows = []
    for c in by.values():
        c["owed"] = c["total"] - c["paid"]
        rows.append(_r2(c))
    rows.sort(key=lambda r: -r["owed"])
    cols = [col("name", "Supplier", width=220), col("bills", "Credit bills", "int", 80),
            col("total", "Bills total", "money"), col("paid", "Paid", "money"),
            col("owed", "Still owed", "money"), col("oldest", "Oldest bill", "date", 95)]
    tot = _sum_totals(rows, ("bills", "total", "paid", "owed"), "name")
    return _result("Credit Purchase Summary", cols, rows, tot,
                   [("Owed to suppliers", tot["owed"], "money")],
                   ["Bills of the period not fully paid (paid on the bill). Payments made later "
                    "against the supplier are in Supplier Statement / Outstanding Bills."])


# ── accounts ─────────────────────────────────────────────────
def _account_of(text):
    t = str(text or "").strip()
    if not t:
        return None
    code = t.split(" ")[0].split("—")[0].strip()
    r = _q1("SELECT account_id, account_code, account_name_en FROM accounts WHERE account_code=?",
            (code,))
    if r:
        return r
    rows = [a for a in _q("SELECT account_id, account_code, account_name_en FROM accounts")
            if t.lower() in str(a.get("account_name_en") or "").lower()]
    return rows[0] if len(rows) == 1 else None


@report("month_ledger", GROUP_ACC, "Month-wise Ledger Summary", params=("period", "account"),
        desc="One account month by month: opening, debit, credit and closing.")
def r_month_ledger(date_from, date_to, account="", **_):
    a = _account_of(account)
    title = "Month-wise Ledger Summary"
    if not a:
        return _result(title, [], [], notes=["Pick an account."])
    rows = []
    op = _f((_q1("SELECT ISNULL(SUM(jl.debit - jl.credit),0) AS b FROM journal_lines jl "
                 "JOIN journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 "
                 "AND jl.account_id=? AND je.entry_date < ?", (a["account_id"], date_from)) or {})
            .get("b"))
    mv = {}
    for r in _q("SELECT je.entry_date AS d, jl.debit, jl.credit FROM journal_lines jl "
                "JOIN journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 "
                "AND jl.account_id=? AND je.entry_date BETWEEN ? AND ?",
                (a["account_id"], date_from, date_to)):
        m = mv.setdefault(_d(r["d"])[:7], [0.0, 0.0, 0])
        m[0] += _f(r.get("debit"))
        m[1] += _f(r.get("credit"))
        m[2] += 1
    bal = op
    for mk in _months(date_from, date_to):
        dr, cr, n = mv.get(mk, (0.0, 0.0, 0))
        rows.append(_r2(dict(month=_mlabel(mk), entries=n, opening=bal, debit=dr, credit=cr,
                             closing=bal + dr - cr)))
        bal += dr - cr
    cols = [col("month", "Month", width=110), col("entries", "Entries", "int", 70),
            col("opening", "Opening", "money"), col("debit", "Debit", "money"),
            col("credit", "Credit", "money"), col("closing", "Closing", "money")]
    tot = _sum_totals(rows, ("entries", "debit", "credit"), "month")
    tot["opening"], tot["closing"] = round(op, 2), round(bal, 2)
    return _result(title, cols, rows, tot, subtitle="%s %s  ·  %s → %s" % (
        a["account_code"], a["account_name_en"], date_from, date_to))


@report("income_expense", GROUP_ACC, "Income & Expense Statement",
        desc="Every income and expense account of the period, and what is left (simple P&L).")
def r_income_expense(date_from, date_to, **_):
    rows = []
    sums = {}
    for r in _q("SELECT a.account_code, a.account_name_en, LOWER(a.account_type) AS t, "
                "ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr "
                "FROM journal_lines jl JOIN journal_entries je ON je.journal_id=jl.journal_id "
                "JOIN accounts a ON a.account_id=jl.account_id WHERE je.is_posted=1 "
                "AND je.entry_date BETWEEN ? AND ? AND LOWER(a.account_type) IN "
                "('revenue','income','expense','cost') "
                "AND ISNULL(je.source_type,'') NOT LIKE 'closing%' "
                "GROUP BY a.account_code, a.account_name_en, LOWER(a.account_type) "
                "ORDER BY a.account_code", (date_from, date_to)):
        inc = r["t"] in ("revenue", "income")
        amt = (_f(r["cr"]) - _f(r["dr"])) if inc else (_f(r["dr"]) - _f(r["cr"]))
        if abs(amt) < 0.005:
            continue
        side = "Income" if inc else "Expense"
        sums[side] = sums.get(side, 0.0) + amt
        rows.append(dict(side=side, code=r["account_code"], name=r["account_name_en"],
                         income=round(amt, 2) if inc else None,
                         expense=None if inc else round(amt, 2)))
    rows.sort(key=lambda r: (r["side"] != "Income", r["code"]))
    inc, exp = round(sums.get("Income", 0.0), 2), round(sums.get("Expense", 0.0), 2)
    cols = [col("side", "", width=80), col("code", "Code", width=80),
            col("name", "Account", width=260), col("income", "Income", "money"),
            col("expense", "Expense", "money")]
    tot = {"name": "TOTAL", "income": inc, "expense": exp}
    return _result("Income & Expense Statement", cols, rows, tot,
                   [("Income", inc, "money"), ("Expenses", exp, "money"),
                    ("Left (profit)" if inc >= exp else "Loss", round(inc - exp, 2), "money")],
                   ["Cost of goods sold is an expense here. The full Profit & Loss "
                    "(gross profit, groups) is in Accounts ▸ Reports."])


@report("transaction_analysis", GROUP_ACC, "Transaction Analysis",
        desc="How many of each kind of entry were made in the period and their total.")
def r_transaction_analysis(date_from, date_to, **_):
    try:
        from modules import voucher_types as VT
        lbl = {k: v.get("en") if isinstance(v, dict) else str(v) for k, v in
               getattr(VT, "BY_SOURCE", {}).items()}
    except Exception:
        lbl = {}
    rows = []
    for r in _q("SELECT ISNULL(je.source_type,'manual') AS st, COUNT(DISTINCT je.journal_id) AS n, "
                "ISNULL(SUM(jl.debit),0) AS amt, MIN(je.entry_date) AS f, MAX(je.entry_date) AS l "
                "FROM journal_entries je JOIN journal_lines jl ON jl.journal_id=je.journal_id "
                "WHERE je.is_posted=1 AND je.entry_date BETWEEN ? AND ? "
                "GROUP BY ISNULL(je.source_type,'manual') ORDER BY ISNULL(je.source_type,'manual')",
                (date_from, date_to)):
        st = r["st"] or "manual"
        name = lbl.get(st)
        if isinstance(name, dict):
            name = name.get("en")
        rows.append(_r2(dict(kind=str(name or st.replace("_", " ").title()), src=st, n=r["n"],
                             amt=_f(r["amt"]), first=_d(r.get("f")), last=_d(r.get("l")),
                             avg=_f(r["amt"]) / r["n"] if r["n"] else 0.0)))
    rows.sort(key=lambda r: -r["amt"])
    cols = [col("kind", "Kind of entry", width=220), col("src", "Source", width=120),
            col("n", "Entries", "int", 70), col("amt", "Amount", "money"),
            col("avg", "Average", "money"), col("first", "First", "date", 90),
            col("last", "Last", "date", 90)]
    tot = _sum_totals(rows, ("n", "amt"), "kind")
    return _result("Transaction Analysis", cols, rows, tot)


@report("daily_cash_bank", GROUP_ACC, "Daily Cash & Bank Balance", params=("period", "cashbank"),
        desc="Cash and bank day by day: opening, money in, money out, closing.")
def r_daily_cash_bank(date_from, date_to, account="", **_):
    accs = _cash_accounts()
    if account:
        a = _account_of(account)
        accs = [x for x in accs if a and x["account_id"] == a["account_id"]] or accs
    ids = [a["account_id"] for a in accs]
    rows = []
    if ids:
        ph = ",".join("?" * len(ids))
        op = _f((_q1("SELECT ISNULL(SUM(jl.debit - jl.credit),0) AS b FROM journal_lines jl "
                     "JOIN journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 "
                     "AND je.entry_date < ? AND jl.account_id IN (%s)" % ph,
                     (date_from, *ids)) or {}).get("b"))
        bal = op
        for r in _q("SELECT je.entry_date AS d, ISNULL(SUM(jl.debit),0) AS dr, "
                    "ISNULL(SUM(jl.credit),0) AS cr FROM journal_lines jl "
                    "JOIN journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 "
                    "AND je.entry_date BETWEEN ? AND ? AND jl.account_id IN (%s) "
                    "GROUP BY je.entry_date ORDER BY je.entry_date" % ph,
                    (date_from, date_to, *ids)):
            dr, cr = _f(r["dr"]), _f(r["cr"])
            rows.append(_r2(dict(d=_d(r["d"]), opening=bal, inn=dr, out=cr, closing=bal + dr - cr)))
            bal += dr - cr
    else:
        op = bal = 0.0
    cols = [col("d", "Date", "date", 100), col("opening", "Opening", "money"),
            col("inn", "Money in", "money"), col("out", "Money out", "money"),
            col("closing", "Closing", "money")]
    tot = _sum_totals(rows, ("inn", "out"), "d")
    tot["opening"], tot["closing"] = round(op, 2), round(bal, 2)
    return _result("Daily Cash & Bank Balance", cols, rows, tot,
                   [("Opening", round(op, 2), "money"), ("Closing", round(bal, 2), "money")],
                   ["Accounts: " + ", ".join(a["account_name_en"] for a in accs[:8])
                    + (" …" if len(accs) > 8 else "")])


# ── v7.20 Polosys ▸ Accounts ▸ Reports: Bank Flow, Daily Account Statement ──
def _bank_accounts():
    """The bank / card accounts (cash and petty cash left out)."""
    skip = set()
    try:
        from modules import account_defaults as ad
        for role in ("cash", "petty_cash"):
            a = getattr(ad, role)()
            if a:
                skip.add(a)
    except Exception:
        pass
    return [a for a in _cash_accounts() if a["account_id"] not in skip
            and "cash" not in str(a.get("account_name_en") or "").lower()]


def _daily_flow(ids, date_from, date_to):
    """[(day, money in, money out)] and the opening of these accounts."""
    if not ids:
        return 0.0, []
    ph = ",".join("?" * len(ids))
    op = _f((_q1("SELECT ISNULL(SUM(jl.debit - jl.credit),0) AS b FROM journal_lines jl "
                 "JOIN journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 "
                 "AND je.entry_date < ? AND jl.account_id IN (%s)" % ph,
                 (date_from, *ids)) or {}).get("b"))
    days = _q("SELECT je.entry_date AS d, ISNULL(SUM(jl.debit),0) AS dr, "
              "ISNULL(SUM(jl.credit),0) AS cr, COUNT(DISTINCT je.journal_id) AS n FROM journal_lines jl "
              "JOIN journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 "
              "AND je.entry_date BETWEEN ? AND ? AND jl.account_id IN (%s) "
              "GROUP BY je.entry_date ORDER BY je.entry_date" % ph,
              (date_from, date_to, *ids))
    return op, days


@report("bank_flow", GROUP_ACC, "Bank Flow", params=("period", "cashbank"),
        desc="Bank and card accounts day by day: opening, deposits, withdrawals, closing.")
def r_bank_flow(date_from, date_to, account="", **_):
    accs = _bank_accounts()
    if account:
        a = _account_of(account)
        if a:
            accs = [x for x in _cash_accounts() if x["account_id"] == a["account_id"]] or accs
    op, days = _daily_flow([a["account_id"] for a in accs], date_from, date_to)
    bal, rows = op, []
    for r in days:
        dr, cr = _f(r["dr"]), _f(r["cr"])
        rows.append(_r2(dict(d=_d(r["d"]), n=int(r.get("n") or 0), opening=bal, inn=dr, out=cr,
                             closing=bal + dr - cr)))
        bal += dr - cr
    cols = [col("d", "Date", "date", 100), col("n", "Entries", "int", 70),
            col("opening", "Opening", "money"), col("inn", "Deposits", "money"),
            col("out", "Withdrawals", "money"), col("closing", "Closing", "money")]
    tot = _sum_totals(rows, ("n", "inn", "out"), "d")
    tot["opening"], tot["closing"] = round(op, 2), round(bal, 2)
    return _result("Bank Flow", cols, rows, tot,
                   [("Opening", round(op, 2), "money"), ("Deposits", tot.get("inn", 0), "money"),
                    ("Withdrawals", tot.get("out", 0), "money"), ("Closing", round(bal, 2), "money")],
                   ["Accounts: " + (", ".join(a["account_name_en"] for a in accs[:8]) or "no bank account")
                    + (" …" if len(accs) > 8 else "")])


@report("daily_account_statement", GROUP_ACC, "Daily Account Statement", params=("period", "account"),
        desc="One account day by day: opening, debit, credit and closing balance of each day.")
def r_daily_account_statement(date_from, date_to, account="", **_):
    cols = [col("d", "Date", "date", 100), col("n", "Entries", "int", 70),
            col("opening", "Opening", "money"), col("dr", "Debit", "money"),
            col("cr", "Credit", "money"), col("closing", "Closing", "money")]
    a = _account_of(account) if account else None
    if not a:
        return _result("Daily Account Statement", cols, [], None, [], ["Choose an account."])
    # credit-side accounts (liability, income, equity) read as credit balances
    t_ = (_q1("SELECT account_type FROM accounts WHERE account_id=?", (a["account_id"],)) or {})
    sgn = 1 if str(t_.get("account_type") or "asset") in ("asset", "expense") else -1
    op, days = _daily_flow([a["account_id"]], date_from, date_to)
    bal, rows = sgn * op, []
    for r in days:
        dr, cr = _f(r["dr"]), _f(r["cr"])
        rows.append(_r2(dict(d=_d(r["d"]), n=int(r.get("n") or 0), opening=bal, dr=dr, cr=cr,
                             closing=bal + sgn * (dr - cr))))
        bal += sgn * (dr - cr)
    tot = _sum_totals(rows, ("n", "dr", "cr"), "d")
    tot["opening"], tot["closing"] = round(sgn * op, 2), round(bal, 2)
    return _result("Daily Account Statement", cols, rows, tot,
                   [("Account", "%s %s" % (a.get("account_code", ""), a.get("account_name_en", "")), "text"),
                    ("Opening", round(sgn * op, 2), "money"), ("Closing", round(bal, 2), "money")])


# ── v7.12 documents ──────────────────────────────────────────
def _simple(kind, date_from, date_to, party, only_open=False):
    from modules import simple_docs as SD
    from modules import masters as M
    out = []
    for r in SD.docs(kind, date_from, date_to, None, limit=5000):
        if only_open and (r.get("source_number") or r.get("doc_status") == "cancelled"):
            continue
        who = (r.get("party_name") if kind == "packing_slip"
               else M.label_of("salesmen", r.get("salesman_id")))
        if not _match(party, who, r.get("doc_number")):
            continue
        out.append(dict(num=r["doc_number"], d=_d(r.get("doc_date")), who=who or "",
                        src=r.get("source_number") or "", veh=M.label_of("vehicles", r.get("vehicle_id"))
                        if r.get("vehicle_id") else "", drv=r.get("driver_name") or "",
                        items=int(r.get("items") or 0), qty=round(_f(r.get("qty")), 3),
                        st=SD.status_label(kind, r.get("doc_status"))))
    return out


@report("packing_slips", GROUP_AN, "Delivery Notes not Invoiced", params=("period", "party"),
        desc="Packing slips / delivery notes with no Sales Invoice yet (goods out, bill not made).")
def r_packing_slips(date_from, date_to, party="", **_):
    try:
        rows = _simple("packing_slip", date_from, date_to, party, only_open=True)
    except Exception:
        rows = []
    cols = [col("num", "Number", width=140), col("d", "Date", "date", 90),
            col("who", "Customer", width=200), col("veh", "Vehicle", width=120),
            col("drv", "Driver", width=120), col("items", "Items", "int", 60),
            col("qty", "Qty", "qty"), col("st", "Status", width=90)]
    tot = _sum_totals(rows, ("items", "qty"), "num")
    return _result("Delivery Notes not Invoiced", cols, rows, tot,
                   [("Notes", len(rows), "int")])


@report("load_requests", GROUP_AN, "Item Load Requests", params=("period", "party"),
        desc="Load requests of the salesmen's vans and their status.")
def r_load_requests(date_from, date_to, party="", **_):
    try:
        rows = _simple("load_request", date_from, date_to, party)
    except Exception:
        rows = []
    cols = [col("num", "Number", width=140), col("d", "Date", "date", 90),
            col("who", "Salesman", width=180), col("veh", "Vehicle", width=120),
            col("items", "Items", "int", 60), col("qty", "Qty", "qty"),
            col("st", "Status", width=90)]
    tot = _sum_totals(rows, ("items", "qty"), "num")
    return _result("Item Load Requests", cols, rows, tot)


@report("card_commission", GROUP_ACC, "Card Sales & Bank Commission",
        desc="Money taken by each bank card / card machine (its account in Masters) and the bank's "
             "commission on it.")
def r_card_commission(date_from, date_to, **_):
    title = "Card Sales & Bank Commission"
    if not _has_table("bank_cards"):
        return _result(title, [], [], notes=[_NEEDS_UPDATE])
    src = [("Card", r.get("card_name"), r.get("account_id"), _f(r.get("commission_pct")))
           for r in _q("SELECT * FROM bank_cards WHERE ISNULL(is_active,1)=1")]
    if _has_table("card_machines"):
        src += [("Machine", "%s%s" % (r.get("machine_name") or "",
                                       (" · " + r["terminal_id"]) if r.get("terminal_id") else ""),
                 r.get("account_id"), None)
                for r in _q("SELECT * FROM card_machines WHERE ISNULL(is_active,1)=1")]
    accs = {a["account_id"]: a for a in _q("SELECT account_id, account_code, account_name_en "
                                           "FROM accounts")}
    pct_of_acc = {}
    for kind, _n, aid, pct in src:
        if aid and pct:
            pct_of_acc.setdefault(aid, pct)
    rows, seen = [], set()
    for kind, name, aid, pct in src:
        if not aid:
            rows.append(dict(kind=kind, name=name, acc="— no account set —", inn=None, out=None,
                             pct=pct, comm=None, net=None))
            continue
        r = _q1("SELECT ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr, "
                "COUNT(*) AS n FROM journal_lines jl JOIN journal_entries je "
                "ON je.journal_id=jl.journal_id WHERE je.is_posted=1 AND jl.account_id=? "
                "AND je.entry_date BETWEEN ? AND ?", (aid, date_from, date_to)) or {}
        inn, out = _f(r.get("dr")), _f(r.get("cr"))
        p = pct if pct is not None else pct_of_acc.get(aid, 0.0)
        shared = aid in seen
        seen.add(aid)
        a = accs.get(aid) or {}
        comm = 0.0 if shared else inn * (p or 0) / 100.0
        rows.append(_r2(dict(kind=kind, name=name,
                             acc="%s %s%s" % (a.get("account_code") or "", a.get("account_name_en") or "",
                                              "  (same account as above)" if shared else ""),
                             inn=0.0 if shared else inn, out=0.0 if shared else out, pct=p,
                             comm=comm, net=(inn - comm) if not shared else 0.0)))
    cols = [col("kind", "", width=70), col("name", "Card / machine", width=190),
            col("acc", "Account", width=230), col("inn", "Money in", "money"),
            col("out", "Settled / out", "money"), col("pct", "Comm. %", "pct", 70),
            col("comm", "Bank commission", "money"), col("net", "Net after commission", "money")]
    tot = _sum_totals(rows, ("inn", "out", "comm", "net"), "name")
    return _result(title, cols, rows, tot,
                   [("Card money in", tot["inn"], "money"), ("Bank commission", tot["comm"], "money")],
                   ["Money in = everything posted into the card's account in the period. Give each "
                    "card its own clearing account (Accounts ▸ Masters ▸ Bank Cards) for exact "
                    "figures; cards sharing one account are counted once."])


@report("cost_centre", GROUP_ACC, "Cost Centre Report", params=("period", "account"),
        desc="Income and expenses of each cost centre (the Cost centre box on vouchers), "
             "account by account.")
def r_cost_centre(date_from, date_to, account="", **_):
    title = "Cost Centre Report"
    if not _has_col("journal_lines", "cost_center_id") or not _has_table("cost_centers"):
        return _result(title, [], [], notes=[_NEEDS_UPDATE])
    names = _names("cost_centers", "cost_center_id", "name_en")
    a = _account_of(account) if account else None
    sql = ("SELECT jl.cost_center_id AS cc, a.account_code, a.account_name_en, "
           "LOWER(a.account_type) AS t, ISNULL(SUM(jl.debit),0) AS dr, ISNULL(SUM(jl.credit),0) AS cr "
           "FROM journal_lines jl JOIN journal_entries je ON je.journal_id=jl.journal_id "
           "JOIN accounts a ON a.account_id=jl.account_id WHERE je.is_posted=1 "
           "AND jl.cost_center_id IS NOT NULL AND je.entry_date BETWEEN ? AND ? ")
    params = [date_from, date_to]
    if a:
        sql += "AND jl.account_id=? "
        params.append(a["account_id"])
    sql += ("GROUP BY jl.cost_center_id, a.account_code, a.account_name_en, LOWER(a.account_type) "
            "ORDER BY jl.cost_center_id, a.account_code")
    rows, by = [], OrderedDict()
    for r in _q(sql, tuple(params)):
        by.setdefault(r["cc"], []).append(r)
    for cc, items in by.items():
        inc = exp = 0.0
        rows.append({"_style": "sub", "cc": names.get(cc, "#%s" % cc)})
        for r in items:
            dr, cr = _f(r["dr"]), _f(r["cr"])
            is_inc = r["t"] in ("revenue", "income")
            is_exp = r["t"] in ("expense", "cost")
            if is_inc:
                inc += cr - dr
            elif is_exp:
                exp += dr - cr
            rows.append(_r2(dict(cc="", code=r["account_code"], name=r["account_name_en"],
                                 dr=dr, cr=cr,
                                 income=(cr - dr) if is_inc else None,
                                 expense=(dr - cr) if is_exp else None)))
        rows.append(_r2({"_style": "total", "cc": "", "name": "Net of " + names.get(cc, "#%s" % cc),
                         "income": inc, "expense": exp, "dr": None, "cr": inc - exp}))
    cols = [col("cc", "Cost centre", width=150), col("code", "Code", width=80),
            col("name", "Account", width=230), col("dr", "Debit", "money"),
            col("cr", "Credit / Net", "money"), col("income", "Income", "money"),
            col("expense", "Expense", "money")]
    return _result(title, cols, rows, None,
                   notes=["Pick a cost centre on Receipt / Payment / Journal vouchers "
                          "(Masters ▸ Cost Centres) to see it here."])


# ════════════════════════════════════════════════════════════
#  v7.16 — more reports (Polosys list, DayBill way)
# ════════════════════════════════════════════════════════════
from modules.report_center import GROUP_INV   # noqa: E402

_TXN_LABEL = {"sale": "Sales", "sales": "Sales", "return_in": "Sales return",
              "sales_return": "Sales return", "purchase": "Purchase",
              "return_out": "Purchase return", "purchase_return": "Purchase return",
              "opening": "Opening stock", "consumption": "Consumption (own use)",
              "transfer_in": "Branch transfer in", "transfer_out": "Branch transfer out",
              "transit_in": "Sent (in transit)", "transit_out": "Received from transit",
              "adjustment_in": "Adjustment in", "adjustment_out": "Adjustment out",
              "stock_damage": "Damage", "stock_excess": "Excess", "stock_shortage": "Shortage",
              "stock_consumable_return": "Consumable return", "production_in": "Production in",
              "production_out": "Production used"}


def _tlabel(t):
    try:
        from modules.report_center import _ADJ_TYPES
        if t in _ADJ_TYPES and t not in _TXN_LABEL:
            return _ADJ_TYPES[t]
    except Exception:
        pass
    return _TXN_LABEL.get(t, str(t or "").replace("_", " ").title())


@report("price_list", GROUP_INV, "Product List (Price List)", params=("as_now", "product", "category"),
        desc="Every active product with its unit, selling price, wholesale price, cost, VAT and stock.")
def r_price_list(date_from, date_to, product="", category="", **_):
    cats = _names("product_categories", "category_id", "category_name_en")
    has_w = _has_col("products", "wholesale_price")
    rows = []
    for p in _q("SELECT p.*, vc.vat_rate AS vr FROM products p LEFT JOIN vat_categories vc "
                "ON vc.vat_category_id=p.vat_category_id WHERE ISNULL(p.is_active,1)=1 "
                "ORDER BY p.product_name_en"):
        if not _match(product, p.get("product_code"), p.get("product_name_en"), p.get("barcode")):
            continue
        cat = cats.get(p.get("category_id"), "")
        if category and not _match(category, cat):
            continue
        cost = _f(p.get("average_cost")) or _f(p.get("purchase_price"))
        price = _f(p.get("unit_price"))
        rows.append(_r2(dict(code=p.get("product_code") or "", name=p.get("product_name_en") or "",
                             name_ar=p.get("product_name_ar") or "", cat=cat,
                             unit=p.get("unit_of_measure_en") or "", price=price,
                             whole=_f(p.get("wholesale_price")) if has_w else None, cost=cost,
                             margin=((price - cost) / price * 100.0) if price else None,
                             vat=_f(p.get("vr")), stock=_f(p.get("stock_quantity")),
                             barcode=p.get("barcode") or "")))
    cols = [col("code", "Code", width=80), col("name", "Product", width=220),
            col("name_ar", "الاسم", width=160), col("cat", "Category", width=120),
            col("unit", "Unit", width=60), col("price", "Price", "money"),
            col("whole", "Wholesale", "money"), col("cost", "Cost", "money"),
            col("margin", "Margin %", "pct", 75), col("vat", "VAT %", "pct", 60),
            col("stock", "Stock", "qty"), col("barcode", "Barcode", width=120)]
    return _result("Product List (Price List)", cols, rows, None,
                   [("Products", len(rows), "int")], subtitle="Today")


@report("net_sales", GROUP_AN, "Net Sales (day by day)", params=("period",),
        desc="Each day: sales, returns, net sales, VAT, cash and credit.")
def r_net_sales(date_from, date_to, **_):
    by = OrderedDict()

    def day(d):
        return by.setdefault(d, dict(d=d, bills=0, sales=0.0, ret=0.0, vat=0.0, cash=0.0,
                                     credit=0.0))
    for h in _sales_headers(date_from, date_to):
        c = day(_d(h.get("invoice_date")))
        tot = _f(h.get("total_amount"))
        if _is_credit_note(h):
            c["ret"] += tot
            c["vat"] -= _f(h.get("vat_amount"))
            continue
        c["bills"] += 1
        c["sales"] += tot
        c["vat"] += _f(h.get("vat_amount"))
        paid = min(_f(h.get("paid_amount")), tot)
        c["cash"] += paid
        c["credit"] += tot - paid
    for r in _return_headers("sales", date_from, date_to):
        c = day(_d(r.get("return_date")))
        c["ret"] += _f(r.get("total_amount"))
        c["vat"] -= _f(r.get("vat_amount"))
    rows = []
    for k in sorted(by):
        c = by[k]
        c["net"] = c["sales"] - c["ret"]
        rows.append(_r2(c))
    cols = [col("d", "Date", "date", 95), col("bills", "Bills", "int", 60),
            col("sales", "Sales", "money"), col("ret", "Returns", "money"),
            col("net", "Net sales", "money"), col("vat", "VAT (net)", "money"),
            col("cash", "Paid at once", "money"), col("credit", "On credit", "money")]
    tot = _sum_totals(rows, ("bills", "sales", "ret", "net", "vat", "cash", "credit"), "d")
    return _result("Net Sales (day by day)", cols, rows, tot,
                   [("Net sales", tot["net"], "money"), ("Returns", tot["ret"], "money")],
                   ["Amounts with VAT."])


@report("sales_and_returns", GROUP_AN, "Sales & Sales Return Register", params=("period", "party"),
        desc="Sales bills and sales returns of the period in one list, with the net.")
def r_sales_and_returns(date_from, date_to, party="", **_):
    rows = []
    for h in _sales_headers(date_from, date_to):
        if not _match(party, h.get("customer_name_en"), h.get("invoice_number")):
            continue
        sg = -1 if _is_credit_note(h) else 1
        rows.append(dict(d=_d(h.get("invoice_date")), kind="Credit note" if sg < 0 else "Sale",
                         num=h.get("invoice_number"), party=h.get("customer_name_en") or "",
                         net=round(sg * _f(h.get("taxable_amount")), 2),
                         vat=round(sg * _f(h.get("vat_amount")), 2),
                         total=round(sg * _f(h.get("total_amount")), 2)))
    for r in _return_headers("sales", date_from, date_to):
        if not _match(party, r.get("customer_name_en"), r.get("return_number")):
            continue
        rows.append(dict(d=_d(r.get("return_date")), kind="Sales return", num=r.get("return_number"),
                         party=r.get("customer_name_en") or "",
                         net=-round(_f(r.get("taxable_amount")), 2),
                         vat=-round(_f(r.get("vat_amount")), 2),
                         total=-round(_f(r.get("total_amount")), 2)))
    rows.sort(key=lambda r: (r["d"], str(r["num"])))
    cols = [col("d", "Date", "date", 95), col("kind", "Kind", width=100),
            col("num", "Number", width=140), col("party", "Customer", width=200),
            col("net", "Net", "money"), col("vat", "VAT", "money"), col("total", "Total", "money")]
    tot = _sum_totals(rows, ("net", "vat", "total"), "num")
    return _result("Sales & Sales Return Register", cols, rows, tot,
                   notes=["Returns and credit notes are minus."])


def _doc_summary(title, table, lt, idc, numc, datec, partyc, party, date_from, date_to, head):
    if not _has_table(table):
        return _result(title, [], [], notes=[_NEEDS_UPDATE])
    has_del = _has_col(lt, "delivered_qty")
    rows = []
    for h in _q("SELECT * FROM %s WHERE %s BETWEEN ? AND ? ORDER BY %s, %s"
                % (table, datec, datec, idc), (date_from, date_to)):
        if not _match(party, h.get(partyc), h.get(numc)):
            continue
        q = _q1("SELECT ISNULL(SUM(quantity),0) AS q%s FROM %s WHERE %s=?"
                % (", ISNULL(SUM(delivered_qty),0) AS dq" if has_del else "", lt, idc),
                (h[idc],)) or {}
        qty, dq = _f(q.get("q")), _f(q.get("dq"))
        rows.append(_r2(dict(num=h.get(numc), d=_d(h.get(datec)), party=h.get(partyc) or "",
                             total=_f(h.get("total_amount")), qty=qty, done=dq,
                             pct=(dq / qty * 100.0) if qty else 0.0,
                             st=str(h.get("status") or "open").title())))
    cols = [col("num", "Number", width=140), col("d", "Date", "date", 95),
            col("party", head, width=200), col("total", "Total", "money"),
            col("qty", "Qty", "qty"), col("done", "Done", "qty"), col("pct", "Done %", "pct", 70),
            col("st", "Status", width=90)]
    tot = _sum_totals(rows, ("total", "qty", "done"), "num")
    by = OrderedDict()
    for r in rows:
        by[r["st"]] = by.get(r["st"], 0) + 1
    return _result(title, cols, rows, tot, [(k, v, "int") for k, v in by.items()])


@report("order_summary", GROUP_AN, "Sales Order Summary", params=("period", "party"),
        desc="Every sales order of the period: total, quantity delivered and status.")
def r_order_summary(date_from, date_to, party="", **_):
    return _doc_summary("Sales Order Summary", "sales_orders", "sales_order_lines", "so_id",
                        "so_number", "so_date", "customer_name_en", party, date_from, date_to,
                        "Customer")


@report("quotation_summary", GROUP_AN, "Sales Quotation Summary", params=("period", "party"),
        desc="Every quotation of the period, its total and whether it became a bill.")
def r_quotation_summary(date_from, date_to, party="", **_):
    return _doc_summary("Sales Quotation Summary", "quotations", "quotation_lines", "quote_id",
                        "quote_number", "quote_date", "customer_name_en", party, date_from,
                        date_to, "Customer")


@report("po_summary", GROUP_PUR, "Purchase Order Summary", params=("period", "party"),
        desc="Every purchase order of the period, quantity received and status.")
def r_po_summary(date_from, date_to, party="", **_):
    return _doc_summary("Purchase Order Summary", "purchase_orders", "purchase_order_lines",
                        "po_id", "po_number", "po_date", "supplier_name_en", party, date_from,
                        date_to, "Supplier")


@report("daywise_profit", GROUP_AN, "Day-wise Sales with Profit", params=("period",),
        desc="Each day: net sales, cost of the goods sold, profit and margin.")
def r_daywise_profit(date_from, date_to, **_):
    prods = {r["product_id"]: r for r in _q("SELECT product_id, average_cost, purchase_price "
                                             "FROM products")}
    fm = {}
    try:
        from modules.report_center import _factor_map
        fm = _factor_map()
    except Exception:
        pass
    by = OrderedDict()
    for ln in _sales_lines(date_from, date_to):
        d = _d(ln.get("invoice_date"))
        sg = -1 if str(ln.get("invoice_type_code") or "388") == "381" else 1
        p = prods.get(ln.get("product_id")) or {}
        unit_cost = _f(p.get("average_cost")) or _f(p.get("purchase_price"))
        fac = fm.get((ln.get("product_id"), str(ln.get("unit_of_measure_en") or "").strip().lower()),
                     1.0)
        c = by.setdefault(d, dict(d=d, bills=set(), net=0.0, cost=0.0))
        c["bills"].add(ln.get("invoice_id"))
        c["net"] += sg * _f(ln.get("line_amount"))
        c["cost"] += sg * _f(ln.get("quantity")) * fac * unit_cost
    for ln in _return_lines("sales", date_from, date_to):
        d = _d(ln.get("return_date"))
        p = prods.get(ln.get("product_id")) or {}
        unit_cost = _f(p.get("average_cost")) or _f(p.get("purchase_price"))
        c = by.setdefault(d, dict(d=d, bills=set(), net=0.0, cost=0.0))
        c["net"] -= _f(ln.get("line_amount"))
        c["cost"] -= _f(ln.get("quantity")) * unit_cost
    rows = []
    for k in sorted(by):
        c = by[k]
        prof = c["net"] - c["cost"]
        rows.append(_r2(dict(d=k, bills=len(c["bills"]), net=c["net"], cost=c["cost"], profit=prof,
                             margin=(prof / c["net"] * 100.0) if c["net"] else 0.0)))
    cols = [col("d", "Date", "date", 95), col("bills", "Bills", "int", 60),
            col("net", "Net sales", "money"), col("cost", "Cost", "money"),
            col("profit", "Profit", "money"), col("margin", "Margin %", "pct", 75)]
    tot = _sum_totals(rows, ("bills", "net", "cost", "profit"), "d")
    tot["margin"] = round(tot["profit"] / tot["net"] * 100.0, 2) if tot["net"] else 0.0
    return _result("Day-wise Sales with Profit", cols, rows, tot,
                   [("Profit", tot["profit"], "money"), ("Margin %", tot["margin"], "pct")],
                   ["Without VAT; cost = today's average cost (else purchase price)."])


def _inv_rows(date_from, date_to, product=""):
    if not _has_table("inventory_transactions"):
        return []
    rows = _q("SELECT t.product_id, t.txn_type, t.txn_date, ISNULL(t.qty_in_base,0) AS qin, "
              "ISNULL(t.qty_out_base,0) AS qout, ISNULL(t.unit_cost,0) AS uc, p.product_code, "
              "p.product_name_en FROM inventory_transactions t JOIN products p "
              "ON p.product_id=t.product_id WHERE t.txn_date BETWEEN ? AND ?",
              (date_from, date_to))
    if product:
        rows = [r for r in rows if _match(product, r.get("product_code"), r.get("product_name_en"))]
    return rows


@report("item_movement", GROUP_INV, "Item-wise Summary (all movements)", params=("period", "product"),
        desc="Each item: how much came in and went out in the period — sales, returns, purchases, "
             "opening, transfers, damage, excess, shortage, own use.")
def r_item_movement(date_from, date_to, product="", **_):
    rows_in = _inv_rows(date_from, date_to, product)
    types = []
    by = OrderedDict()
    for r in rows_in:
        t = r["txn_type"] or "other"
        if t not in types:
            types.append(t)
        c = by.setdefault(r["product_id"], OrderedDict(code=r["product_code"] or "",
                                                      name=r["product_name_en"] or ""))
        c[t] = c.get(t, 0.0) + _f(r["qin"]) - _f(r["qout"])
        c["_in"] = c.get("_in", 0.0) + _f(r["qin"])
        c["_out"] = c.get("_out", 0.0) + _f(r["qout"])
    order = ["opening", "purchase", "return_out", "sale", "return_in"]
    types.sort(key=lambda t: (order.index(t) if t in order else 99, t))
    rows = []
    for c in by.values():
        r = {k: v for k, v in c.items() if not k.startswith("_")}
        r["tin"], r["tout"] = round(c.get("_in", 0.0), 3), round(c.get("_out", 0.0), 3)
        r["net"] = round(r["tin"] - r["tout"], 3)
        rows.append({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    rows.sort(key=lambda r: r["name"])
    cols = [col("code", "Code", width=80), col("name", "Item", width=200)] + \
        [col(t, _tlabel(t), "qty", 90) for t in types] + \
        [col("tin", "Total in", "qty"), col("tout", "Total out", "qty"), col("net", "Net", "qty")]
    tot = _sum_totals(rows, types + ["tin", "tout", "net"], "name")
    return _result("Item-wise Summary (all movements)", cols, rows, tot,
                   notes=["Base units (a box of 12 = 12). In = +, out = −."])


@report("inv_txn_summary", GROUP_INV, "Inventory Transaction Summary", params=("period", "product"),
        desc="Each kind of stock movement in the period: entries, items, quantity in / out and value.")
def r_inv_txn_summary(date_from, date_to, product="", **_):
    by = OrderedDict()
    for r in _inv_rows(date_from, date_to, product):
        t = r["txn_type"] or "other"
        c = by.setdefault(t, dict(kind=_tlabel(t), n=0, items=set(), qin=0.0, qout=0.0, val=0.0))
        c["n"] += 1
        c["items"].add(r["product_id"])
        c["qin"] += _f(r["qin"])
        c["qout"] += _f(r["qout"])
        c["val"] += (_f(r["qin"]) - _f(r["qout"])) * _f(r["uc"])
    rows = [_r2(dict(kind=c["kind"], n=c["n"], items=len(c["items"]), qin=c["qin"], qout=c["qout"],
                     val=c["val"])) for c in by.values()]
    rows.sort(key=lambda r: -abs(r["val"]))
    cols = [col("kind", "Movement", width=200), col("n", "Lines", "int", 70),
            col("items", "Items", "int", 70), col("qin", "Qty in", "qty"),
            col("qout", "Qty out", "qty"), col("val", "Value (+ in / − out)", "money", 140)]
    tot = _sum_totals(rows, ("n", "qin", "qout", "val"), "kind")
    return _result("Inventory Transaction Summary", cols, rows, tot,
                   notes=["Value at the cost each movement was made with."])


@report("stock_daily_balance", GROUP_INV, "Daily Stock Balance", params=("period", "product"),
        desc="Day by day: stock at the start, in, out and at the end (one item, or all items "
             "by value).")
def r_stock_daily_balance(date_from, date_to, product="", **_):
    title = "Daily Stock Balance"
    if not _has_table("inventory_transactions"):
        return _result(title, [], [], notes=[_NEEDS_UPDATE])
    one = None
    if product:
        hits = [p for p in _q("SELECT product_id, product_code, product_name_en FROM products")
                if _match(product, p.get("product_code"), p.get("product_name_en"))]
        one = hits[0] if len(hits) == 1 else None
    if one:
        pid = one["product_id"]
        op = _f((_q1("SELECT ISNULL(SUM(ISNULL(qty_in_base,0) - ISNULL(qty_out_base,0)),0) AS b "
                     "FROM inventory_transactions WHERE product_id=? AND txn_date < ?",
                     (pid, date_from)) or {}).get("b"))
        q = ("SELECT txn_date AS d, ISNULL(SUM(qty_in_base),0) AS i, ISNULL(SUM(qty_out_base),0) AS o "
             "FROM inventory_transactions WHERE product_id=? AND txn_date BETWEEN ? AND ? "
             "GROUP BY txn_date ORDER BY txn_date")
        params, kind, sub = (pid, date_from, date_to), "qty", "%s %s" % (one["product_code"],
                                                                         one["product_name_en"])
    else:
        op = _f((_q1("SELECT ISNULL(SUM((ISNULL(qty_in_base,0) - ISNULL(qty_out_base,0)) * "
                     "ISNULL(unit_cost,0)),0) AS b FROM inventory_transactions WHERE txn_date < ?",
                     (date_from,)) or {}).get("b"))
        q = ("SELECT txn_date AS d, ISNULL(SUM(qty_in_base * ISNULL(unit_cost,0)),0) AS i, "
             "ISNULL(SUM(qty_out_base * ISNULL(unit_cost,0)),0) AS o FROM inventory_transactions "
             "WHERE txn_date BETWEEN ? AND ? GROUP BY txn_date ORDER BY txn_date")
        params, kind, sub = (date_from, date_to), "money", "All items (value at cost)"
    rows, bal = [], op
    for r in _q(q, params):
        i, o = _f(r["i"]), _f(r["o"])
        rows.append(dict(d=_d(r["d"]), op=round(bal, 3), i=round(i, 3), o=round(o, 3),
                         cl=round(bal + i - o, 3)))
        bal += i - o
    cols = [col("d", "Date", "date", 95), col("op", "Opening", kind), col("i", "In", kind),
            col("o", "Out", kind), col("cl", "Closing", kind)]
    tot = _sum_totals(rows, ("i", "o"), "d")
    tot["op"], tot["cl"] = round(op, 3), round(bal, 3)
    return _result(title, cols, rows, tot, subtitle="%s  ·  %s → %s" % (sub, date_from, date_to),
                   notes=["Type one item in Product to see its quantity; empty = value of all items."])


@report("income_detail", GROUP_ACC, "Income Report", params=("period", "account"),
        desc="Every income entry of the period (sales, other income …), account by account.")
def r_income_detail(date_from, date_to, account="", **_):
    a = _account_of(account) if account else None
    sql = ("SELECT je.entry_date AS d, je.journal_number AS num, je.source_type AS st, "
           "ISNULL(jl.description, je.description_en) AS txt, a.account_code, a.account_name_en, "
           "jl.debit, jl.credit FROM journal_lines jl JOIN journal_entries je "
           "ON je.journal_id=jl.journal_id JOIN accounts a ON a.account_id=jl.account_id "
           "WHERE je.is_posted=1 AND je.entry_date BETWEEN ? AND ? AND LOWER(a.account_type) IN "
           "('revenue','income') AND ISNULL(je.source_type,'') NOT LIKE 'closing%' ")
    params = [date_from, date_to]
    if a:
        sql += "AND jl.account_id=? "
        params.append(a["account_id"])
    sql += "ORDER BY a.account_code, je.entry_date, je.journal_id"
    rows = []
    for r in _q(sql, tuple(params)):
        amt = _f(r["credit"]) - _f(r["debit"])
        if abs(amt) < 0.005:
            continue
        rows.append(_r2(dict(d=_d(r["d"]), num=r.get("num") or "", acc="%s %s" % (
            r["account_code"], r["account_name_en"]), src=str(r.get("st") or "").replace("_", " "),
            txt=r.get("txt") or "", amt=amt)))
    cols = [col("d", "Date", "date", 95), col("num", "Voucher", width=130),
            col("acc", "Income account", width=200), col("src", "From", width=100),
            col("txt", "Details", width=240), col("amt", "Amount", "money")]
    tot = _sum_totals(rows, ("amt",), "txt")
    return _result("Income Report", cols, rows, tot, [("Income", tot["amt"], "money")])


@report("cash_summary", GROUP_ACC, "Cash Summary", params=("period", "cashbank"),
        desc="Each day: cash in and out by kind (sales, receipts, payments, expenses …) and the "
             "closing cash.")
def r_cash_summary(date_from, date_to, account="", **_):
    accs = _cash_accounts()
    if account:
        a = _account_of(account)
        accs = [x for x in accs if a and x["account_id"] == a["account_id"]] or accs
    else:
        cash = [x for x in accs if str(x.get("account_code") or "").startswith("110")]
        accs = cash or accs
    ids = [a["account_id"] for a in accs]
    rows, kinds = [], []
    if not ids:
        return _result("Cash Summary", [], [], notes=["No cash account."])
    ph = ",".join("?" * len(ids))
    op = _f((_q1("SELECT ISNULL(SUM(jl.debit - jl.credit),0) AS b FROM journal_lines jl JOIN "
                 "journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 AND "
                 "je.entry_date < ? AND jl.account_id IN (%s)" % ph, (date_from, *ids)) or {})
            .get("b"))
    by = OrderedDict()
    for r in _q("SELECT je.entry_date AS d, ISNULL(je.source_type,'manual') AS st, "
                "ISNULL(SUM(jl.debit - jl.credit),0) AS amt FROM journal_lines jl JOIN "
                "journal_entries je ON je.journal_id=jl.journal_id WHERE je.is_posted=1 AND "
                "je.entry_date BETWEEN ? AND ? AND jl.account_id IN (%s) GROUP BY je.entry_date, "
                "ISNULL(je.source_type,'manual') ORDER BY je.entry_date" % ph,
                (date_from, date_to, *ids)):
        st = str(r["st"] or "manual")
        if st not in kinds:
            kinds.append(st)
        c = by.setdefault(_d(r["d"]), OrderedDict(d=_d(r["d"])))
        c[st] = c.get(st, 0.0) + _f(r["amt"])
    bal = op
    for d in sorted(by):
        c = by[d]
        net = sum(_f(c.get(k)) for k in kinds)
        c["op"], c["net"], c["cl"] = bal, net, bal + net
        bal += net
        rows.append(_r2(dict(c)))
    cols = [col("d", "Date", "date", 95), col("op", "Opening", "money")] + \
        [col(k, k.replace("_", " ").title(), "money", 100) for k in kinds] + \
        [col("net", "Net", "money"), col("cl", "Closing", "money")]
    tot = _sum_totals(rows, kinds + ["net"], "d")
    tot["op"], tot["cl"] = round(op, 2), round(bal, 2)
    return _result("Cash Summary", cols, rows, tot,
                   [("Opening", round(op, 2), "money"), ("Closing", round(bal, 2), "money")],
                   ["+ = money in, − = money out. Accounts: " + ", ".join(
                       a["account_name_en"] for a in accs[:6])])



@report("in_transit", GROUP_INV, "Goods in Transit (branch transfers)", params=("as_now", "product"),
        desc="Branch transfers sent and not received yet: what is on the way, from where to where.")
def r_in_transit(date_from, date_to, product="", **_):
    try:
        from modules import stock_branch as SB
        docs = SB.in_transit()
    except Exception:
        docs = []
    rows = []
    today = date.today()
    for t in docs:
        for ln in SB.transfer_lines(t["transfer_id"]):
            if not _match(product, ln.get("product_code"), ln.get("product_name_en")):
                continue
            try:
                days = (today - date.fromisoformat(_d(t.get("transfer_date")))).days
            except Exception:
                days = None
            rows.append(_r2(dict(num=t["transfer_number"], d=_d(t.get("transfer_date")),
                                 fr=t.get("from_name") or "", to=t.get("to_name") or "",
                                 code=ln.get("product_code") or "", item=ln.get("product_name_en") or "",
                                 qty=_f(ln.get("quantity")), unit=ln.get("unit_name") or "",
                                 value=_f(ln.get("qty_base")) * _f(ln.get("unit_cost")), days=days)))
    cols = [col("num", "Transfer", width=120), col("d", "Sent", "date", 90),
            col("fr", "From", width=120), col("to", "To", width=120), col("code", "Code", width=80),
            col("item", "Item", width=200), col("qty", "Qty", "qty"), col("unit", "Unit", width=60),
            col("value", "Value", "money"), col("days", "Days on the way", "int", 100)]
    tot = _sum_totals(rows, ("qty", "value"), "num")
    return _result("Goods in Transit (branch transfers)", cols, rows, tot,
                   [("Transfers", len(docs), "int"), ("Value on the way", tot["value"], "money")],
                   subtitle="Now")


@report("bookings", GROUP_AN, "Bookings & Advances (sales orders)", params=("period", "party"),
        desc="Sales orders of the period with the advance the customer paid and what is left.")
def r_bookings(date_from, date_to, party="", **_):
    title = "Bookings & Advances (sales orders)"
    if not _has_table("sales_orders"):
        return _result(title, [], [], notes=[_NEEDS_UPDATE])
    rows = []
    for h in _q("SELECT * FROM sales_orders WHERE so_date BETWEEN ? AND ? ORDER BY so_date, so_id",
                (date_from, date_to)):
        if not _match(party, h.get("customer_name_en"), h.get("so_number")):
            continue
        num = str(h.get("so_number") or "")
        adv = 0.0
        if num:
            r = _q1("SELECT ISNULL(SUM(amount),0) AS a FROM payments WHERE payment_type='receipt' AND "
                    "reference_number LIKE ?", ("%" + num + "%",)) or {}
            adv = _f(r.get("a"))
        tot = _f(h.get("total_amount"))
        rows.append(_r2(dict(num=num, d=_d(h.get("so_date")), deliv=_d(h.get("delivery_date")),
                             party=h.get("customer_name_en") or "", total=tot, adv=adv,
                             left=tot - adv, st=str(h.get("status") or "open").title())))
    cols = [col("num", "Order", width=130), col("d", "Date", "date", 90),
            col("deliv", "Delivery", "date", 90), col("party", "Customer", width=200),
            col("total", "Total", "money"), col("adv", "Advance paid", "money"),
            col("left", "Balance", "money"), col("st", "Status", width=90)]
    tot = _sum_totals(rows, ("total", "adv", "left"), "num")
    return _result(title, cols, rows, tot,
                   [("Advances held", tot["adv"], "money"), ("Still to collect", tot["left"], "money")],
                   ["Advance = receipts whose reference has the order number (💰 Advance on the "
                    "Sales Order window)."])
