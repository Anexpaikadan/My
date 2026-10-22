# ============================================================
# DayBill ERP - Production reports (v7.0)
# ------------------------------------------------------------
# Shown in Reports ▸ Production when the company uses the Production
# module (needs="production"). Only CONFIRMED production entries count
# (drafts and cancelled entries are left out), like every report.
#
#   production_register      every production run: what was made, how
#                            many, materials + labour + overhead, cost
#                            of one unit
#   production_materials     material usage: planned (bill of materials)
#                            against really used, the difference and
#                            what it cost
#   production_cost_trend    cost of one unit of each finished product,
#                            month by month, and how much it changed
#
# report_center imports this file by itself (see its last lines).
# ============================================================

from collections import OrderedDict

from modules import report_center as RC
from modules.report_center import report, col, _result, _sum_totals, _q

GROUP = "Production"

# the stock card / movement reports call these rows "Production"
RC._ADJ_TYPES.setdefault("production", "Production")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _totals(rows, keys, label_key):
    """Like report_center._sum_totals, but rows shown in colour ("hi")
    still count — they are real rows, not sub-totals."""
    t = {k: round(sum(_f(r.get(k)) for r in rows), 2) for k in keys}
    t[label_key] = "TOTAL"
    return t


def _ready():
    return RC._has_table("production_entries") and RC._has_table("production_lines")


def _entries(date_from, date_to, product=""):
    if not _ready():
        return []
    rows = _q("SELECT e.*, ISNULL(p.unit_of_measure_en,'') AS base_unit, ISNULL(p.barcode,'') AS barcode "
              "FROM production_entries e LEFT JOIN products p ON p.product_id=e.product_id "
              "WHERE e.entry_status='confirmed' AND e.entry_date BETWEEN ? AND ? "
              "ORDER BY e.entry_date, e.entry_id", (date_from, date_to))
    return [r for r in rows if RC._match(product, r.get("product_code"), r.get("product_name_en"),
                                         r.get("barcode"), r.get("entry_number"))]


@report("production_register", GROUP, "Production Register", params=("period", "product"),
        desc="Every production run in the period: product made, quantity, materials, labour, "
             "overhead, total cost and the cost of one unit.", needs="production")
def r_production_register(date_from, date_to, product="", **_):
    rows = []
    for e in _entries(date_from, date_to, product):
        rows.append({"date": RC._d(e.get("entry_date")), "number": e.get("entry_number") or "",
                     "code": e.get("product_code") or "", "name": e.get("product_name_en") or "",
                     "qty": round(_f(e.get("quantity")), 3), "unit": e.get("unit_name") or "",
                     "materials": round(_f(e.get("material_cost")), 2),
                     "labour": round(_f(e.get("labour_cost")), 2),
                     "overhead": round(_f(e.get("overhead_cost")), 2),
                     "total": round(_f(e.get("total_cost")), 2),
                     "unit_cost": round(_f(e.get("unit_cost")), 4),
                     "notes": e.get("notes") or ""})
    cols = [col("date", "Date", "date", 90), col("number", "Number", width=130),
            col("code", "Code", width=80), col("name", "Product made", width=200),
            col("qty", "Qty made", "qty", 80), col("unit", "Unit", width=60),
            col("materials", "Materials", "money", 100), col("labour", "Labour", "money", 90),
            col("overhead", "Overhead", "money", 90), col("total", "Total cost", "money", 100),
            col("unit_cost", "Cost of 1 unit", "money", 100), col("notes", "Notes", width=160)]
    tot = _sum_totals(rows, ("materials", "labour", "overhead", "total"), "name", "TOTAL")
    tot["qty"] = None
    return _result("Production Register", cols, rows, tot,
                   [("Production runs", len(rows), "int"), ("Materials", tot["materials"], "money"),
                    ("Labour + overhead", round(tot["labour"] + tot["overhead"], 2), "money"),
                    ("Total cost", tot["total"], "money")],
                   ["Only confirmed production entries. Cost of 1 unit = total cost ÷ quantity made."])


@report("production_materials", GROUP, "Material Usage (planned vs used)",
        params=("period", "product"),
        desc="Each material used in production: planned by the bill of materials against "
             "really used, the difference (over / under use) and its cost.", needs="production")
def r_production_materials(date_from, date_to, product="", **_):
    """product filters the PRODUCT MADE (or the material) by code / name."""
    made = {e["entry_id"]: e for e in _entries(date_from, date_to)}
    ids = list(made)
    agg = OrderedDict()
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        ph = ",".join("?" * len(chunk))
        for ln in _q("SELECT l.*, ISNULL(p.unit_of_measure_en,'') AS base_unit FROM production_lines l "
                     "LEFT JOIN products p ON p.product_id=l.component_id "
                     "WHERE l.entry_id IN (%s) ORDER BY l.product_name_en" % ph, tuple(chunk)):
            e = made.get(ln["entry_id"], {})
            if product and not (RC._match(product, ln.get("product_code"), ln.get("product_name_en"))
                                or RC._match(product, e.get("product_code"), e.get("product_name_en"))):
                continue
            f = _f(ln.get("unit_factor")) or 1.0
            a = agg.setdefault(ln["component_id"], {
                "code": ln.get("product_code") or "", "name": ln.get("product_name_en") or "",
                "unit": ln.get("base_unit") or ln.get("unit_name") or "", "runs": set(),
                "planned": 0.0, "used": 0.0, "cost": 0.0})
            a["planned"] += _f(ln.get("qty_planned")) * f
            a["used"] += _f(ln.get("qty_used")) * f
            a["cost"] += _f(ln.get("line_cost"))
            a["runs"].add(ln["entry_id"])
    rows = []
    for a in agg.values():
        var = a["used"] - a["planned"]
        each = a["cost"] / a["used"] if a["used"] else 0.0
        rows.append({"code": a["code"], "name": a["name"], "unit": a["unit"], "runs": len(a["runs"]),
                     "planned": round(a["planned"], 3), "used": round(a["used"], 3),
                     "variance": round(var, 3),
                     "var_pct": round(var / a["planned"] * 100.0, 2) if a["planned"] else None,
                     "each": round(each, 4), "cost": round(a["cost"], 2),
                     "var_value": round(var * each, 2),
                     "_style": "hi" if var > 1e-9 else None})
    rows.sort(key=lambda r: r["name"].lower())
    cols = [col("code", "Code", width=80), col("name", "Material", width=200),
            col("unit", "Unit", width=60), col("runs", "Runs", "int", 55),
            col("planned", "Planned", "qty", 85), col("used", "Used", "qty", 85),
            col("variance", "Difference", "qty", 85), col("var_pct", "Difference %", "pct", 90),
            col("each", "Cost each", "money", 90), col("cost", "Cost used", "money", 100),
            col("var_value", "Difference value", "money", 110)]
    tot = _totals(rows, ("cost", "var_value"), "name")
    over = round(sum(r["var_value"] for r in rows if r["var_value"] > 0), 2)
    return _result("Material Usage (planned vs used)", cols, rows, tot,
                   [("Materials", len(rows), "int"), ("Cost used", tot["cost"], "money"),
                    ("Used more than planned", over, "money"),
                    ("Net difference", tot["var_value"], "money")],
                   ["Quantities in each material's base unit. Difference = used − planned "
                    "(more than planned is shown in colour). Only confirmed production entries."])


@report("production_cost_trend", GROUP, "Finished Goods Cost per Unit (trend)",
        params=("period", "product"),
        desc="Cost of one unit of each finished product, month by month: runs, quantity "
             "made, total cost, cost of 1 unit and the change from the month before.",
        needs="production")
def r_production_cost_trend(date_from, date_to, product="", **_):
    agg = OrderedDict()
    for e in _entries(date_from, date_to, product):
        month = RC._d(e.get("entry_date"))[:7]
        key = (e["product_id"], month)
        qb = _f(e.get("qty_base")) or _f(e.get("quantity")) * (_f(e.get("unit_factor")) or 1.0)
        each = (_f(e.get("total_cost")) / qb) if qb else 0.0
        a = agg.setdefault(key, {"pid": e["product_id"], "code": e.get("product_code") or "",
                                 "name": e.get("product_name_en") or "",
                                 "unit": e.get("base_unit") or e.get("unit_name") or "",
                                 "month": month, "runs": 0, "qty": 0.0, "cost": 0.0,
                                 "low": None, "high": None})
        a["runs"] += 1
        a["qty"] += qb
        a["cost"] += _f(e.get("total_cost"))
        a["low"] = each if a["low"] is None else min(a["low"], each)
        a["high"] = each if a["high"] is None else max(a["high"], each)
    rows = []
    prev = {}
    for a in sorted(agg.values(), key=lambda x: (x["name"].lower(), x["pid"], x["month"])):
        per = a["cost"] / a["qty"] if a["qty"] else 0.0
        before = prev.get(a["pid"])
        change = ((per - before) / before * 100.0) if before else None
        prev[a["pid"]] = per
        rows.append({"code": a["code"], "name": a["name"], "unit": a["unit"], "month": a["month"],
                     "runs": a["runs"], "qty": round(a["qty"], 3), "cost": round(a["cost"], 2),
                     "per_unit": round(per, 4), "low": round(a["low"] or 0, 4),
                     "high": round(a["high"] or 0, 4),
                     "change": round(change, 2) if change is not None else None,
                     "_style": "hi" if change is not None and change > 5 else None})
    cols = [col("code", "Code", width=80), col("name", "Product made", width=200),
            col("unit", "Unit", width=60), col("month", "Month", width=75),
            col("runs", "Runs", "int", 55), col("qty", "Qty made", "qty", 85),
            col("cost", "Total cost", "money", 100), col("per_unit", "Cost of 1 unit", "money", 100),
            col("low", "Lowest", "money", 85), col("high", "Highest", "money", 85),
            col("change", "Change %", "pct", 80)]
    tot = _totals(rows, ("runs", "cost"), "name")
    up = sum(1 for r in rows if r["change"] is not None and r["change"] > 0)
    return _result("Finished Goods Cost per Unit (trend)", cols, rows, tot,
                   [("Products", len({r["code"] for r in rows}), "int"),
                    ("Production runs", int(tot["runs"]), "int"), ("Total cost", tot["cost"], "money"),
                    ("Months the cost went up", up, "int")],
                   ["Cost of 1 unit = the month's total cost ÷ quantity made, in the product's base "
                    "unit. Change % is against the month before (a rise above 5% is shown in colour)."])
