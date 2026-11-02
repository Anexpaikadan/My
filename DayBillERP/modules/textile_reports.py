# ============================================================
# DayBill ERP - Textiles & Garments reports (v7.0)
# ------------------------------------------------------------
# Shown in Reports ▸ Textiles for companies with the Textiles module.
# They read the size / colour variants (products.variant_parent_id,
# variant_size, variant_colour — modules/textiles.py) and follow the
# Report Center rules: confirmed documents only, quantities in BASE
# units (Box of 12 = 12), sales returns taken off, cost = average cost
# (else purchase price).
#
#   tex_sales_size     Sales by Size
#   tex_sales_colour   Sales by Colour
#   tex_sales_style    Sales by Style (net qty per size)
#   tex_stock_style    Stock by Style (colours × sizes, value)
# ============================================================

from collections import OrderedDict

from modules.report_center import (report, col, _result, _sum_totals, _q, _f, _has_col,
                                   _item_sales, _cost, _match)

GROUP_TEX = "Textiles"
_NOTE_UPDATE = "The Textiles update is not in this database yet."


def _ready():
    return _has_col("products", "variant_parent_id")


def _orders():
    try:
        from modules import textiles as TX
        return ([x.lower() for x in TX.sizes()], [x.lower() for x in TX.colours()])
    except Exception:
        return ([], [])


def _size_key(s, order):
    from modules.textiles import size_key
    return size_key(s, order)


def _colour_key(c, order):
    from modules.textiles import colour_key
    return colour_key(c, order)


def _variants():
    """{variant product_id: {size, colour, style_id, style_code, style, category}}"""
    rows = _q("SELECT v.product_id, ISNULL(v.variant_size,'') AS size, "
              "ISNULL(v.variant_colour,'') AS colour, s.product_id AS style_id, "
              "s.product_code AS style_code, s.product_name_en AS style, "
              "ISNULL(pc.category_name_en,'') AS category "
              "FROM products v JOIN products s ON s.product_id=v.variant_parent_id "
              "LEFT JOIN product_categories pc ON pc.category_id=s.category_id")
    return {r["product_id"]: r for r in rows}


def _sales(date_from, date_to, category="", product=""):
    """Item sales (report_center._item_sales) of the variants only, each
    with its size / colour / style."""
    vm = _variants()
    out = []
    for a in _item_sales(date_from, date_to):
        v = vm.get(a.get("pid"))
        if not v:
            continue
        if category and category != "All" and (v.get("category") or "(no category)") != category:
            continue
        if not _match(product, v.get("style_code"), v.get("style"), a.get("code"), a.get("name")):
            continue
        out.append(dict(a, size=v["size"], colour=v["colour"], style_id=v["style_id"],
                        style_code=v["style_code"] or "", style=v["style"] or ""))
    return out


def _empty(title, columns, note):
    return _result(title, columns, [], None, [], [note])


def _by(rows, key, label, order_key):
    by = {}
    for a in rows:
        k = a[key] or ""
        e = by.setdefault(k.lower(), {key: k or "—", "qty": 0.0, "r_qty": 0.0, "net_qty": 0.0,
                                      "net_sales": 0.0, "cost": 0.0, "profit": 0.0,
                                      "_sort": order_key(k)})
        e["qty"] += a["qty"]
        e["r_qty"] += a["r_qty"]
        e["net_qty"] += a["qty"] - a["r_qty"]
        e["net_sales"] += a["net_sales"]
        e["cost"] += a["cost"]
        e["profit"] += a["profit"]
    out = sorted(by.values(), key=lambda e: e.pop("_sort"))
    tot_ns = sum(e["net_sales"] for e in out)
    for e in out:
        for k in ("qty", "r_qty", "net_qty"):
            e[k] = round(e[k], 3)
        for k in ("net_sales", "cost", "profit"):
            e[k] = round(e[k], 2)
        e["share"] = round(100.0 * e["net_sales"] / tot_ns, 1) if tot_ns else 0.0
        e["margin"] = round(100.0 * e["profit"] / e["net_sales"], 1) if e["net_sales"] else 0.0
    cols = [col(key, label, width=120), col("qty", "Qty sold", "qty", 80),
            col("r_qty", "Qty returned", "qty", 90), col("net_qty", "Net qty", "qty", 80),
            col("net_sales", "Net sales", "money"), col("share", "Share %", "pct", 70),
            col("cost", "Cost", "money"), col("profit", "Profit", "money"),
            col("margin", "Margin %", "pct", 70)]
    tot = _sum_totals(out, ("qty", "r_qty", "net_qty", "net_sales", "cost", "profit"), key, "TOTAL")
    tot["margin"] = round(100.0 * tot["profit"] / tot["net_sales"], 1) if tot["net_sales"] else 0.0
    return out, cols, tot


@report("tex_sales_size", GROUP_TEX, "Sales by Size", params=("period", "product", "category"),
        desc="Quantity and sales of each size (all styles, or one style / category).",
        needs="textiles")
def r_sales_size(date_from, date_to, product="", category="", **_):
    title = "Sales by Size"
    if not _ready():
        return _empty(title, [col("size", "Size")], _NOTE_UPDATE)
    so, _co = _orders()
    rows, cols, tot = _by(_sales(date_from, date_to, category, product), "size", "Size",
                          lambda s: _size_key(s, so))
    best = max(rows, key=lambda r: r["net_qty"])["size"] if rows else "—"
    return _result(title, cols, rows, tot,
                   [("Sizes", len(rows), "int"), ("Net qty", tot["net_qty"], "qty"),
                    ("Net sales", tot["net_sales"], "money"), ("Profit", tot["profit"], "money"),
                    ("Best size", best, "text")],
                   ["Only size / colour products count. Quantities in base units; "
                    "returns are taken off."])


@report("tex_sales_colour", GROUP_TEX, "Sales by Colour", params=("period", "product", "category"),
        desc="Quantity and sales of each colour (all styles, or one style / category).",
        needs="textiles")
def r_sales_colour(date_from, date_to, product="", category="", **_):
    title = "Sales by Colour"
    if not _ready():
        return _empty(title, [col("colour", "Colour")], _NOTE_UPDATE)
    _so, co = _orders()
    rows, cols, tot = _by(_sales(date_from, date_to, category, product), "colour", "Colour",
                          lambda c: _colour_key(c, co))
    best = max(rows, key=lambda r: r["net_qty"])["colour"] if rows else "—"
    return _result(title, cols, rows, tot,
                   [("Colours", len(rows), "int"), ("Net qty", tot["net_qty"], "qty"),
                    ("Net sales", tot["net_sales"], "money"), ("Profit", tot["profit"], "money"),
                    ("Best colour", best, "text")],
                   ["Only size / colour products count. Quantities in base units; "
                    "returns are taken off."])


@report("tex_sales_style", GROUP_TEX, "Sales by Style (sizes)", params=("period", "product", "category"),
        desc="Each style with the net quantity sold of every size, net sales and profit.",
        needs="textiles")
def r_sales_style(date_from, date_to, product="", category="", **_):
    title = "Sales by Style (sizes)"
    if not _ready():
        return _empty(title, [col("style", "Style")], _NOTE_UPDATE)
    so, _co = _orders()
    data = _sales(date_from, date_to, category, product)
    sizes = sorted({a["size"] for a in data}, key=lambda s: _size_key(s, so))
    keys = {s: "sz%d" % i for i, s in enumerate(sizes)}
    by = OrderedDict()
    for a in sorted(data, key=lambda a: (a["style"].lower(), a["style_id"])):
        e = by.setdefault(a["style_id"], {"code": a["style_code"], "style": a["style"],
                                          "total": 0.0, "net_sales": 0.0, "profit": 0.0})
        k = keys[a["size"]]
        e[k] = round(e.get(k, 0.0) + a["qty"] - a["r_qty"], 3)
        e["total"] += a["qty"] - a["r_qty"]
        e["net_sales"] += a["net_sales"]
        e["profit"] += a["profit"]
    rows = list(by.values())
    for e in rows:
        e["total"] = round(e["total"], 3)
        e["net_sales"] = round(e["net_sales"], 2)
        e["profit"] = round(e["profit"], 2)
    rows.sort(key=lambda e: -e["net_sales"])
    cols = [col("code", "Code", width=80), col("style", "Style", width=200)]
    cols += [col(keys[s], s or "—", "qty", 60) for s in sizes]
    cols += [col("total", "Total qty", "qty", 80), col("net_sales", "Net sales", "money"),
             col("profit", "Profit", "money")]
    tot = _sum_totals(rows, [keys[s] for s in sizes] + ["total", "net_sales", "profit"],
                      "style", "TOTAL")
    for s in sizes:
        tot[keys[s]] = round(sum(_f(r.get(keys[s])) for r in rows), 3)
    tot["total"] = round(sum(r["total"] for r in rows), 3)
    return _result(title, cols, rows, tot,
                   [("Styles", len(rows), "int"), ("Net qty", tot["total"], "qty"),
                    ("Net sales", tot["net_sales"], "money"), ("Profit", tot["profit"], "money")],
                   ["Size columns = net quantity sold (sales − returns), in base units."])


@report("tex_stock_style", GROUP_TEX, "Stock by Style (size × colour)",
        params=("as_now", "product", "category"),
        desc="Stock of every colour (rows) and size (columns) of each style, with value.",
        needs="textiles")
def r_stock_style(product="", category="", **_):
    title = "Stock by Style (size × colour)"
    if not _ready():
        return _empty(title, [col("style", "Style")], _NOTE_UPDATE)
    so, co = _orders()
    rows = _q("SELECT v.*, ISNULL(v.variant_size,'') AS size, ISNULL(v.variant_colour,'') AS colour, "
              "s.product_code AS style_code, s.product_name_en AS style_name, "
              "ISNULL(pc.category_name_en,'') AS style_category "
              "FROM products v JOIN products s ON s.product_id=v.variant_parent_id "
              "LEFT JOIN product_categories pc ON pc.category_id=s.category_id "
              "WHERE ISNULL(v.is_active,1)=1")
    if category and category != "All":
        rows = [r for r in rows if (r.get("style_category") or "(no category)") == category]
    if product:
        rows = [r for r in rows if _match(product, r.get("style_code"), r.get("style_name"))]
    sizes = sorted({r["size"] for r in rows}, key=lambda s: _size_key(s, so))
    keys = {s: "sz%d" % i for i, s in enumerate(sizes)}
    by = {}
    for r in rows:
        k = (r["variant_parent_id"], r["colour"].lower())
        e = by.setdefault(k, {"code": r["style_code"] or "", "style": r["style_name"] or "",
                              "colour": r["colour"] or "—", "total": 0.0, "value": 0.0,
                              "_sort": ((r["style_name"] or "").lower(), r["variant_parent_id"],
                                        _colour_key(r["colour"], co))})
        q = _f(r.get("stock_quantity"))
        e[keys[r["size"]]] = round(_f(e.get(keys[r["size"]])) + q, 3)
        e["total"] += q
        e["value"] += q * _cost(r)
    out = sorted(by.values(), key=lambda e: e.pop("_sort"))
    for e in out:
        e["total"] = round(e["total"], 3)
        e["value"] = round(e["value"], 2)
    cols = [col("code", "Code", width=80), col("style", "Style", width=190),
            col("colour", "Colour", width=100)]
    cols += [col(keys[s], s or "—", "qty", 60) for s in sizes]
    cols += [col("total", "Total", "qty", 80), col("value", "Value (cost)", "money")]
    tot = _sum_totals(out, ["value"], "style", "TOTAL")
    for s in sizes:
        tot[keys[s]] = round(sum(_f(e.get(keys[s])) for e in out), 3)
    tot["total"] = round(sum(e["total"] for e in out), 3)
    n_styles = len({e["code"] + e["style"] for e in out})
    return _result(title, cols, out, tot,
                   [("Styles", n_styles, "int"), ("Sizes / colours", len(rows), "int"),
                    ("In stock", tot["total"], "qty"), ("Value", tot["value"], "money")],
                   ["Value = stock × average cost (else purchase price)."])
