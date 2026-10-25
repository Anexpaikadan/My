# ============================================================
# DayBill ERP — Claude connector (MCP server, READ-ONLY)
# ------------------------------------------------------------
# Lets Claude (desktop app / Cowork) answer questions from your
# DayBill database: sales, VAT, stock, profit, customer & supplier
# balances, expenses, day close, accounting statements, and any
# other SELECT query.
# v6.3: AI inventory management — inventory_health, stock_forecast,
# reorder_plan, abc_analysis, expiry_alerts, branch_transfers,
# bought_together, supplier_prices, data_check, price_check,
# sales_trends, daily_briefing — plus ready-made prompts.
#
# Safety
#   • Never writes: every tool only runs SELECT statements, the
#     connection is opened with ApplicationIntent=ReadOnly, and every
#     transaction is ROLLED BACK — nothing is ever committed.
#   • run_sql accepts one SELECT/WITH statement only; data-changing
#     keywords are rejected before the query reaches SQL Server.
#   • For extra safety use a read-only SQL login
#     (see create_readonly_login.sql + connector_config.json).
#
# Connection
#   Uses the same database settings as DayBill (config/db_config.json)
#   unless claude_connector/connector_config.json overrides them.
#
# Run by Claude desktop:  python daybill_mcp.py   (stdio transport)
# ============================================================

import os
import re
import sys
import json
import datetime as _dt
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
sys.path.insert(0, APP_ROOT)

try:                                    # MCP Python SDK v2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:                     # MCP Python SDK v1
    from mcp.server.fastmcp import FastMCP as _Server
try:
    from mcp.types import ToolAnnotations
    RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                         idempotentHint=True, openWorldHint=False)
except Exception:                       # very old SDK
    RO = None

import pyodbc

MAX_ROWS = 500

# ─────────────────────────────────────────────────────────────
# Read-only database access
# ─────────────────────────────────────────────────────────────
def _conn_string():
    from config.database import load_db_config, build_connection_string
    cfg = load_db_config()
    override = os.path.join(HERE, "connector_config.json")
    if os.path.exists(override):
        try:
            with open(override, "r", encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    if v not in ("", None) and not str(k).startswith("_"):
                        cfg[k] = v
        except Exception as e:
            print(f"[daybill-mcp] connector_config.json ignored: {e}", file=sys.stderr)
    if os.environ.get("DAYBILL_DATABASE"):
        cfg["database"] = os.environ["DAYBILL_DATABASE"]
    return build_connection_string(cfg) + "ApplicationIntent=ReadOnly;", cfg


def _clean(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)} bytes>"
    return v


class ReadOnlyDB:
    """Minimal db object (fetchall / fetchone / execute_scalar) — the same
    interface DayBill's own modules use, so their report functions can be
    reused unchanged. Every call runs in a transaction that is rolled back."""

    def __init__(self):
        self._conn = None

    def _c(self):
        if self._conn is None:
            cs, _ = _conn_string()
            self._conn = pyodbc.connect(cs, autocommit=False, timeout=15)
            self._conn.timeout = 60          # per-query timeout (seconds)
        return self._conn

    def _run(self, sql, params=(), limit=MAX_ROWS):
        conn = self._c()
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            if cur.description is None:
                return [], False
            cols = [c[0] for c in cur.description]
            rows = cur.fetchmany(limit + 1)
            more = len(rows) > limit
            return [{k: _clean(v) for k, v in zip(cols, r)} for r in rows[:limit]], more
        except pyodbc.Error:
            self._conn = None               # reconnect next time
            raise
        finally:
            try:
                cur.close()
                conn.rollback()             # never commit anything
            except Exception:
                pass

    def fetchall(self, sql, params=()):
        return self._run(sql, params, limit=100000)[0]

    def fetchone(self, sql, params=()):
        rows = self._run(sql, params, limit=1)[0]
        return rows[0] if rows else None

    def execute_scalar(self, sql, params=()):
        row = self.fetchone(sql, params)
        return next(iter(row.values())) if row else None

    def execute(self, *a, **k):
        raise PermissionError("DayBill connector is read-only.")


db = ReadOnlyDB()
_COLS = {}


def has_col(table, col):
    key = (table.lower(), col.lower())
    if key not in _COLS:
        try:
            _COLS[key] = bool(db.execute_scalar(
                "SELECT COUNT(*) FROM sys.columns WHERE object_id=OBJECT_ID(?) AND name=?",
                (table, col)))
        except Exception:
            _COLS[key] = False
    return _COLS[key]


def has_table(name):
    key = (name.lower(), "*")
    if key not in _COLS:
        try:
            _COLS[key] = bool(db.execute_scalar(
                "SELECT COUNT(*) FROM sys.objects WHERE name=? AND type IN ('U','V')", (name,)))
        except Exception:
            _COLS[key] = False
    return _COLS[key]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _period(date_from=None, date_to=None):
    """Default = this month to today. Accepts YYYY-MM-DD."""
    today = _dt.date.today()
    try:
        d_to = _dt.date.fromisoformat(str(date_to)[:10]) if date_to else today
    except ValueError:
        raise ValueError(f"date_to must be YYYY-MM-DD, got {date_to!r}")
    try:
        d_from = _dt.date.fromisoformat(str(date_from)[:10]) if date_from else d_to.replace(day=1)
    except ValueError:
        raise ValueError(f"date_from must be YYYY-MM-DD, got {date_from!r}")
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    return d_from.isoformat(), d_to.isoformat()


def _r(x, n=2):
    try:
        return round(float(x or 0), n)
    except Exception:
        return 0.0


def _cost_expr(alias="p"):
    """Cost per BASE unit: average cost, else purchase price, else 0."""
    parts = []
    if has_col("products", "average_cost"):
        parts.append(f"NULLIF({alias}.average_cost,0)")
    if has_col("products", "purchase_price"):
        parts.append(f"NULLIF({alias}.purchase_price,0)")
    if has_col("products", "last_purchase_cost"):
        parts.append(f"NULLIF({alias}.last_purchase_cost,0)")
    return "COALESCE(" + ", ".join(parts + ["0"]) + ")" if parts else "0"


def _unit_factor_apply(line_alias="sil"):
    """OUTER APPLY giving the line unit's conversion factor (Box = 12 …)."""
    if not has_table("product_units"):
        return "", "1"
    return (f" OUTER APPLY (SELECT TOP 1 pu.conversion_factor AS f FROM product_units pu "
            f"WHERE pu.product_id={line_alias}.product_id "
            f"AND pu.unit_name_en={line_alias}.unit_of_measure_en) uf ",
            "ISNULL(NULLIF(uf.f,0),1)")


def _safe(fn):
    """Turn DB errors into a readable result instead of a crash."""
    import functools

    @functools.wraps(fn)
    def wrap(*a, **k):
        try:
            return fn(*a, **k)
        except pyodbc.Error as e:
            msg = str(e)
            hint = ""
            if "Login failed" in msg or "28000" in msg:
                hint = " Check the SQL login in connector_config.json / DayBill DB settings."
            elif "08001" in msg or "server was not found" in msg.lower():
                hint = " Is SQL Server running and is the server name right?"
            return {"error": "Database error: " + msg[:400] + hint}
        except (ValueError, PermissionError) as e:
            return {"error": str(e)}
    return wrap


INSTRUCTIONS = """DayBill ERP business data (Saudi retail: POS, sales, purchases, stock,
VAT/ZATCA, accounting). All tools are READ-ONLY. Money is SAR. Dates are YYYY-MM-DD;
when the user gives no dates, tools default to the current month to today.
Start with business_overview for general questions, and inventory_health for stock
(then stock_forecast, reorder_plan, abc_analysis, expiry_alerts, branch_transfers,
bought_together, supplier_prices, data_check, price_check, sales_trends, daily_briefing). For any standard report (trial
balance, P&L, balance sheet, cash book, day book, VAT return, sales / POS / purchase
registers, stock, stock movement, item ledger) use list_reports + run_report — they
return exactly what DayBill's Reports Center shows. Only 'confirmed' invoices count as
sales/purchases (drafts and cancelled are excluded), matching DayBill's own reports.
Use run_sql only when no specific tool fits; call list_tables / describe_table first."""

server = _Server("DayBill ERP", instructions=INSTRUCTIONS)


def tool(fn):
    kw = {"annotations": RO} if RO is not None else {}
    return server.tool(**kw)(_safe(fn))


# ─────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────
@tool
def database_info() -> dict:
    """Which DayBill company database is connected, company details, record
    counts and the date range of sales data. Call this first if unsure."""
    _, cfg = _conn_string()
    comp = db.fetchone("SELECT TOP 1 company_name_en, company_name_ar, vat_registration_no, "
                       "cr_number, city_en, phone FROM company ORDER BY company_id") or {}
    counts = {}
    for t in ("products", "customers", "suppliers", "sales_invoices", "purchase_invoices"):
        try:
            counts[t] = db.execute_scalar(f"SELECT COUNT(*) FROM {t}")
        except Exception:
            counts[t] = None
    rng = db.fetchone("SELECT MIN(invoice_date) AS first_sale, MAX(invoice_date) AS last_sale "
                      "FROM sales_invoices WHERE invoice_status='confirmed'") or {}
    return {"server": cfg.get("server"), "database": cfg.get("database"),
            "company": comp, "record_counts": counts, "sales_date_range": rng,
            "today": _dt.date.today().isoformat()}


@tool
def business_overview(date_from: str = "", date_to: str = "") -> dict:
    """Headline numbers for a period: sales (net, VAT, total, invoice count,
    average bill), sales by payment method, returns, purchases, expenses,
    estimated gross profit, what customers owe, what you owe suppliers, and
    stock alerts. Default period: this month to today."""
    f, t = _period(date_from, date_to)
    s = db.fetchone(
        "SELECT COUNT(*) AS invoices, ISNULL(SUM(taxable_amount),0) AS net, "
        "ISNULL(SUM(vat_amount),0) AS vat, ISNULL(SUM(total_amount),0) AS total, "
        "ISNULL(SUM(discount_amount),0) AS discount "
        "FROM sales_invoices WHERE invoice_status='confirmed' "
        "AND ISNULL(invoice_type_code,'388')='388' AND invoice_date BETWEEN ? AND ?", (f, t)) or {}
    by_pay = db.fetchall(
        "SELECT ISNULL(NULLIF(payment_method,''),'unknown') AS method, COUNT(*) AS invoices, "
        "SUM(total_amount) AS total FROM sales_invoices WHERE invoice_status='confirmed' "
        "AND invoice_date BETWEEN ? AND ? GROUP BY ISNULL(NULLIF(payment_method,''),'unknown') "
        "ORDER BY total DESC", (f, t))
    returns = {"count": 0, "total": 0.0}
    if has_table("sales_returns"):
        returns = db.fetchone(
            "SELECT COUNT(*) AS count, ISNULL(SUM(total_amount),0) AS total FROM sales_returns "
            "WHERE ISNULL(return_status,'confirmed')='confirmed' "
            "AND TRY_CONVERT(date, return_date) BETWEEN ? AND ?", (f, t)) or returns
    p = db.fetchone(
        "SELECT COUNT(*) AS invoices, ISNULL(SUM(taxable_amount),0) AS net, "
        "ISNULL(SUM(vat_amount),0) AS vat, ISNULL(SUM(total_amount),0) AS total "
        "FROM purchase_invoices WHERE invoice_status='confirmed' "
        "AND invoice_date BETWEEN ? AND ?", (f, t)) or {}
    exp = {"total": 0.0}
    if has_table("expenses"):
        exp = db.fetchone("SELECT ISNULL(SUM(amount),0) AS total FROM expenses "
                          "WHERE expense_date BETWEEN ? AND ?", (f, t)) or exp
    fa, fx = _unit_factor_apply("sil")
    cogs = db.execute_scalar(
        f"SELECT ISNULL(SUM(sil.quantity * {fx} * {_cost_expr('p')}),0) "
        f"FROM sales_invoice_lines sil JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
        f"LEFT JOIN products p ON p.product_id=sil.product_id {fa}"
        f"WHERE si.invoice_status='confirmed' AND si.invoice_date BETWEEN ? AND ?", (f, t)) or 0
    recv = db.execute_scalar("SELECT ISNULL(SUM(balance_due),0) FROM vw_customer_balance "
                             "WHERE balance_due > 0") if has_table("vw_customer_balance") else None
    pay = db.execute_scalar(
        "SELECT ISNULL(SUM(total_amount - ISNULL(paid_amount,0)),0) FROM purchase_invoices "
        "WHERE invoice_status='confirmed' AND total_amount - ISNULL(paid_amount,0) > 0")
    low_col = "reorder_level" if has_col("products", "reorder_level") else None
    stock = db.fetchone(
        "SELECT SUM(CASE WHEN ISNULL(stock_quantity,0) <= 0 THEN 1 ELSE 0 END) AS out_of_stock, "
        + (f"SUM(CASE WHEN ISNULL(stock_quantity,0) > 0 AND ISNULL({low_col},0) > 0 "
           f"AND stock_quantity <= {low_col} THEN 1 ELSE 0 END) AS low_stock, " if low_col else "")
        + f"ISNULL(SUM(CASE WHEN stock_quantity > 0 THEN stock_quantity * {_cost_expr('products')} END),0) AS stock_value_at_cost "
        "FROM products WHERE is_active=1 AND ISNULL(product_type,'product')<>'service'") or {}
    net = _r(s.get("net")) - _r(returns.get("total")) / 1.15 if returns.get("total") else _r(s.get("net"))
    n = int(s.get("invoices") or 0)
    return {
        "period": {"from": f, "to": t},
        "sales": {"invoices": n, "net_before_vat": _r(s.get("net")), "vat": _r(s.get("vat")),
                  "total_with_vat": _r(s.get("total")), "discounts": _r(s.get("discount")),
                  "average_bill": _r(_r(s.get("total")) / n) if n else 0.0},
        "sales_by_payment_method": by_pay,
        "sales_returns": {"count": returns.get("count"), "total": _r(returns.get("total"))},
        "purchases": {"invoices": p.get("invoices"), "net": _r(p.get("net")),
                      "vat": _r(p.get("vat")), "total": _r(p.get("total"))},
        "expenses_total": _r(exp.get("total")),
        "estimated_cost_of_goods_sold": _r(cogs),
        "estimated_gross_profit": _r(_r(s.get("net")) - _r(cogs)),
        "estimated_net_after_expenses": _r(_r(s.get("net")) - _r(cogs) - _r(exp.get("total"))),
        "customers_owe_you": _r(recv) if recv is not None else None,
        "you_owe_suppliers": _r(pay),
        "stock": stock,
        "notes": "Profit uses each product's average/purchase cost per base unit — an "
                 "estimate if costs were not kept up to date. Net sales after returns ≈ "
                 f"{_r(net)}.",
    }


@tool
def sales_report(date_from: str = "", date_to: str = "", group_by: str = "day") -> dict:
    """Sales totals grouped by 'day', 'month', 'payment_method', 'customer',
    'category' or 'hour'. Confirmed invoices only (same as DayBill's Sales report)."""
    f, t = _period(date_from, date_to)
    g = (group_by or "day").lower()
    if g == "category":
        rows = db.fetchall(
            "SELECT ISNULL(c.category_name_en,'(no category)') AS category, "
            "COUNT(DISTINCT si.invoice_id) AS invoices, SUM(sil.quantity) AS qty, "
            "SUM(sil.line_amount) AS net, SUM(sil.vat_amount) AS vat, SUM(sil.line_total) AS total "
            "FROM sales_invoice_lines sil JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
            "LEFT JOIN products p ON p.product_id=sil.product_id "
            "LEFT JOIN product_categories c ON c.category_id=p.category_id "
            "WHERE si.invoice_status='confirmed' AND si.invoice_date BETWEEN ? AND ? "
            "GROUP BY ISNULL(c.category_name_en,'(no category)') ORDER BY total DESC", (f, t))
        return {"period": {"from": f, "to": t}, "group_by": g, "rows": rows}
    key = {"day": "CONVERT(varchar(10), invoice_date, 23)",
           "month": "CONVERT(varchar(7), invoice_date, 23)",
           "payment_method": "ISNULL(NULLIF(payment_method,''),'unknown')",
           "customer": "ISNULL(customer_name_en,'(none)')",
           "hour": "RIGHT('0'+CAST(DATEPART(hour, ISNULL(CAST(invoice_time AS datetime), created_at)) AS varchar(2)),2)"}.get(g)
    if not key:
        raise ValueError("group_by must be day, month, payment_method, customer, category or hour")
    rows = db.fetchall(
        f"SELECT {key} AS [{g}], COUNT(*) AS invoices, SUM(taxable_amount) AS net, "
        f"SUM(vat_amount) AS vat, SUM(total_amount) AS total, "
        f"SUM(total_amount - ISNULL(paid_amount,0)) AS unpaid "
        f"FROM sales_invoices WHERE invoice_status='confirmed' AND invoice_date BETWEEN ? AND ? "
        f"GROUP BY {key} ORDER BY " + ("total DESC" if g in ("customer", "payment_method") else f"{key}"),
        (f, t))
    tot = {k: _r(sum(float(r.get(k) or 0) for r in rows)) for k in ("net", "vat", "total", "unpaid")}
    tot["invoices"] = sum(int(r.get("invoices") or 0) for r in rows)
    return {"period": {"from": f, "to": t}, "group_by": g, "totals": tot, "rows": rows}


@tool
def top_products(date_from: str = "", date_to: str = "", limit: int = 20,
                 order_by: str = "revenue") -> dict:
    """Best-selling products with quantity, revenue, estimated cost and profit
    and margin %. order_by: 'revenue', 'quantity', 'profit' or 'margin'.
    Use order_by='revenue' with a small limit for 'what sells most'."""
    f, t = _period(date_from, date_to)
    limit = max(1, min(int(limit or 20), 200))
    fa, fx = _unit_factor_apply("sil")
    order = {"revenue": "revenue DESC", "quantity": "qty_base DESC", "profit": "profit DESC",
             "margin": "margin_pct DESC"}.get((order_by or "revenue").lower(), "revenue DESC")
    rows = db.fetchall(
        f"SELECT TOP {limit} * FROM ("
        f" SELECT MAX(sil.product_code) AS code, sil.product_name_en AS product, "
        f" SUM(sil.quantity * {fx}) AS qty_base, SUM(sil.line_amount) AS revenue, "
        f" SUM(sil.quantity * {fx} * {_cost_expr('p')}) AS est_cost, "
        f" SUM(sil.line_amount) - SUM(sil.quantity * {fx} * {_cost_expr('p')}) AS profit, "
        f" CASE WHEN SUM(sil.line_amount)=0 THEN 0 ELSE "
        f"  100.0*(SUM(sil.line_amount) - SUM(sil.quantity * {fx} * {_cost_expr('p')}))/SUM(sil.line_amount) END AS margin_pct "
        f" FROM sales_invoice_lines sil JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
        f" LEFT JOIN products p ON p.product_id=sil.product_id {fa}"
        f" WHERE si.invoice_status='confirmed' AND si.invoice_date BETWEEN ? AND ? "
        f" GROUP BY sil.product_id, sil.product_name_en) x ORDER BY {order}", (f, t))
    for r in rows:
        r["margin_pct"] = _r(r.get("margin_pct"), 1)
    return {"period": {"from": f, "to": t}, "order_by": order_by,
            "note": "revenue is before VAT; qty_base is in each product's base unit",
            "rows": rows}


@tool
def slow_moving_products(days: int = 60, limit: int = 50) -> dict:
    """Products that have stock but have NOT sold in the last N days (dead
    stock), with stock value at cost. Good for 'what isn't selling'."""
    days = max(1, min(int(days or 60), 3650))
    limit = max(1, min(int(limit or 50), 500))
    rows = db.fetchall(
        f"SELECT TOP {limit} p.product_code AS code, p.product_name_en AS product, "
        f"p.stock_quantity AS stock, p.stock_quantity * {_cost_expr('p')} AS stock_value, "
        f"(SELECT MAX(si.invoice_date) FROM sales_invoice_lines sil JOIN sales_invoices si "
        f"  ON si.invoice_id=sil.invoice_id WHERE sil.product_id=p.product_id "
        f"  AND si.invoice_status='confirmed') AS last_sold "
        f"FROM products p WHERE p.is_active=1 AND ISNULL(p.stock_quantity,0) > 0 "
        f"AND NOT EXISTS (SELECT 1 FROM sales_invoice_lines sil JOIN sales_invoices si "
        f"  ON si.invoice_id=sil.invoice_id WHERE sil.product_id=p.product_id "
        f"  AND si.invoice_status='confirmed' "
        f"  AND si.invoice_date >= DATEADD(day, -?, CAST(GETDATE() AS date))) "
        f"ORDER BY stock_value DESC", (days,))
    return {"not_sold_in_days": days, "count": len(rows),
            "total_stock_value": _r(sum(float(r.get("stock_value") or 0) for r in rows)),
            "rows": rows}


def _rc():
    """DayBill's own Reports Center, reading through this read-only db."""
    from modules import report_center as RC
    if RC._db() is not db:
        RC.use_db(db)
    return RC


@tool
def vat_report(date_from: str = "", date_to: str = "") -> dict:
    """VAT return for a period exactly as DayBill's VAT Report / Reports Center
    calculate it (ZATCA boxes 1-16): output VAT on sales less credit notes and
    sales returns, input VAT on purchases and VAT-bearing expenses less
    purchase returns, and net VAT payable (negative = refundable). For a
    quarter pass its first and last day."""
    f, t = _period(date_from, date_to)
    d = _rc().vat_return_data(f, t)
    return {"period": {"from": f, "to": t}, "boxes": d["boxes"],
            "output_vat": d["output_vat"], "input_vat": d["input_vat"],
            "net_vat_payable": d["net"], "sales_returns": d["sales_returns"],
            "purchase_returns": d["purchase_returns"], "expenses_with_vat": d["expenses"]}


@tool
def list_reports() -> dict:
    """Every report in DayBill's Reports Center that run_report can produce:
    accounting (trial balance, P&L, balance sheet, cash/bank book, day book,
    ledger, VAT), sales & POS, purchases and inventory (stock, movement, item
    ledger, low / dead stock). Shows each report's id and which filters it takes."""
    return {"reports": [{"id": r["id"], "group": r["group"], "title": r["title"],
                         "filters": [p for p in r["params"] if p not in ("period", "as_now")],
                         "uses_dates": "period" in r["params"] or "as_of" in r["params"],
                         "about": r["desc"]} for r in _rc().catalog()]}


@tool
def run_report(report: str, date_from: str = "", date_to: str = "", account: str = "",
               product: str = "", category: str = "", party: str = "",
               channel: str = "", method: str = "", stock_filter: str = "",
               max_rows: int = 200) -> dict:
    """Run any DayBill report by id (see list_reports), e.g. 'trial_balance',
    'profit_loss', 'balance_sheet', 'cash_book', 'day_book', 'vat_return',
    'sales_register', 'sales_items', 'pos_summary', 'purchase_register',
    'stock', 'stock_movement', 'stock_ledger', 'low_stock'. Dates YYYY-MM-DD
    (default this month). Filters: account (code, for ledger / cash_book),
    product (code / barcode / name), category, party (customer or supplier
    name), channel (POS / Invoice), method (cash / card / credit),
    stock_filter (In stock / Low / Out of stock / Negative).
    Returns the same columns, rows, totals and summary as the DayBill screen."""
    RC = _rc()
    rid = (report or "").strip().lower()
    if rid not in RC.REGISTRY:
        raise ValueError("Unknown report %r. Call list_reports for ids." % report)
    f, t = _period(date_from, date_to)
    kw = {"date_from": f, "date_to": t}
    for k, v in (("account", account), ("product", product), ("category", category),
                 ("party", party), ("channel", channel), ("method", method),
                 ("stock_filter", stock_filter)):
        if v:
            kw[k] = v
    res = RC.run(rid, **kw)
    limit = max(1, min(int(max_rows or 200), MAX_ROWS))
    rows = [{k: v for k, v in r.items() if k != "_style" or v} for r in res["rows"]]
    return {"report": res["title"], "period": res.get("subtitle"),
            "columns": [{"key": c["key"], "label": c["label"], "type": c["kind"]}
                        for c in res["columns"]],
            "rows": rows[:limit], "rows_total": len(rows),
            "truncated": len(rows) > limit, "totals": res.get("totals"),
            "summary": [{"label": l, "value": v} for l, v, _k in res.get("summary") or []],
            "notes": res.get("notes") or []}


@tool
def stock_report(filter: str = "all", search: str = "", limit: int = 100) -> dict:
    """Stock on hand with cost value and selling value. filter: 'all', 'low'
    (at/below reorder level), 'out' (zero), 'negative', 'overstock'. search
    matches code, name, Arabic name or barcode."""
    limit = max(1, min(int(limit or 100), MAX_ROWS))
    reorder = "p.reorder_level" if has_col("products", "reorder_level") else "0"
    maxs = "p.max_stock" if has_col("products", "max_stock") else "0"
    where = ["p.is_active=1", "ISNULL(p.product_type,'product')<>'service'"]
    flt = (filter or "all").lower()
    if flt == "low":
        where.append(f"ISNULL({reorder},0) > 0 AND ISNULL(p.stock_quantity,0) <= {reorder}")
    elif flt == "out":
        where.append("ISNULL(p.stock_quantity,0) = 0")
    elif flt == "negative":
        where.append("ISNULL(p.stock_quantity,0) < 0")
    elif flt == "overstock":
        where.append(f"ISNULL({maxs},0) > 0 AND p.stock_quantity > {maxs}")
    params = []
    if search:
        where.append("(p.product_code LIKE ? OR p.product_name_en LIKE ? OR "
                     "p.product_name_ar LIKE ? OR p.barcode LIKE ?)")
        params += ["%" + search + "%"] * 4
    rows = db.fetchall(
        f"SELECT TOP {limit} p.product_code AS code, p.product_name_en AS product, "
        f"ISNULL(c.category_name_en,'') AS category, p.stock_quantity AS stock, "
        f"{reorder} AS reorder_level, {_cost_expr('p')} AS unit_cost, p.unit_price AS sell_price, "
        f"p.stock_quantity * {_cost_expr('p')} AS value_at_cost, "
        f"p.stock_quantity * p.unit_price AS value_at_price "
        f"FROM products p LEFT JOIN product_categories c ON c.category_id=p.category_id "
        f"WHERE {' AND '.join(where)} ORDER BY p.product_name_en", tuple(params))
    total = db.fetchone(
        f"SELECT COUNT(*) AS products, ISNULL(SUM(CASE WHEN p.stock_quantity>0 THEN "
        f"p.stock_quantity * {_cost_expr('p')} END),0) AS value_at_cost "
        f"FROM products p WHERE {' AND '.join(where)}", tuple(params)) or {}
    return {"filter": flt, "matching_products": total.get("products"),
            "total_value_at_cost": _r(total.get("value_at_cost")),
            "shown": len(rows), "rows": rows}


@tool
def product_lookup(search: str) -> dict:
    """Everything about one product (or the few best matches): prices, cost,
    stock, units with barcodes, last purchase and sales in the last 30 days."""
    if not (search or "").strip():
        raise ValueError("Give a product name, code or barcode.")
    like = "%" + search.strip() + "%"
    prods = db.fetchall(
        "SELECT TOP 5 p.*, c.category_name_en AS category FROM products p "
        "LEFT JOIN product_categories c ON c.category_id=p.category_id "
        "WHERE p.product_code=? OR p.barcode=? OR p.product_name_en LIKE ? OR p.product_name_ar LIKE ? "
        + ("OR p.product_id IN (SELECT product_id FROM product_units WHERE barcode=?) "
           if has_table("product_units") else "")
        + "ORDER BY CASE WHEN p.product_code=? OR p.barcode=? THEN 0 ELSE 1 END, p.product_name_en",
        tuple([search, search, like, like] + ([search] if has_table("product_units") else [])
              + [search, search]))
    out = []
    for p in prods:
        pid = p["product_id"]
        keep = {k: p.get(k) for k in ("product_id", "product_code", "product_name_en",
                                      "product_name_ar", "category", "barcode", "unit_price",
                                      "purchase_price", "average_cost", "last_purchase_cost",
                                      "wholesale_price", "stock_quantity", "reorder_level",
                                      "is_active", "is_weighed", "scale_plu") if k in p}
        if has_table("product_units"):
            keep["units"] = db.fetchall(
                "SELECT unit_name_en AS unit, conversion_factor AS base_qty, selling_price, "
                "purchase_price, barcode, is_default FROM product_units "
                "WHERE product_id=? AND ISNULL(is_active,1)=1 ORDER BY conversion_factor", (pid,))
        keep["last_purchases"] = db.fetchall(
            "SELECT TOP 5 pi.invoice_date, pi.invoice_number, pi.supplier_name_en AS supplier, "
            "pil.quantity, pil.unit_of_measure_en AS unit, pil.unit_price "
            "FROM purchase_invoice_lines pil JOIN purchase_invoices pi ON pi.purchase_id=pil.purchase_id "
            "WHERE pil.product_id=? AND pi.invoice_status='confirmed' "
            "ORDER BY pi.invoice_date DESC, pi.purchase_id DESC", (pid,))
        keep["sold_last_30_days"] = db.fetchone(
            "SELECT ISNULL(SUM(sil.quantity),0) AS qty, ISNULL(SUM(sil.line_amount),0) AS net "
            "FROM sales_invoice_lines sil JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
            "WHERE sil.product_id=? AND si.invoice_status='confirmed' "
            "AND si.invoice_date >= DATEADD(day,-30,CAST(GETDATE() AS date))", (pid,))
        out.append(keep)
    return {"matches": len(out), "products": out}


@tool
def customer_balances(min_balance: float = 0.01, limit: int = 50, with_aging: bool = True) -> dict:
    """Who owes you money: balance per customer (same as DayBill's customer
    balance), largest first, with optional aging buckets by due date
    (current, 1-30, 31-60, 61-90, over 90 days)."""
    limit = max(1, min(int(limit or 50), MAX_ROWS))
    rows = db.fetchall(
        f"SELECT TOP {limit} customer_code AS code, customer_name_en AS customer, "
        f"total_invoiced, total_paid, balance_due FROM vw_customer_balance "
        f"WHERE balance_due >= ? ORDER BY balance_due DESC", (float(min_balance or 0),))
    aging = None
    if with_aging:
        aging = db.fetchall(
            "SELECT ISNULL(c.customer_name_en, si.customer_name_en) AS customer, "
            "SUM(CASE WHEN d <= 0 THEN bal ELSE 0 END) AS [current], "
            "SUM(CASE WHEN d BETWEEN 1 AND 30 THEN bal ELSE 0 END) AS [1_30], "
            "SUM(CASE WHEN d BETWEEN 31 AND 60 THEN bal ELSE 0 END) AS [31_60], "
            "SUM(CASE WHEN d BETWEEN 61 AND 90 THEN bal ELSE 0 END) AS [61_90], "
            "SUM(CASE WHEN d > 90 THEN bal ELSE 0 END) AS [over_90], SUM(bal) AS total "
            "FROM (SELECT customer_id, customer_name_en, total_amount - ISNULL(paid_amount,0) AS bal, "
            "      DATEDIFF(day, ISNULL(due_date, invoice_date), CAST(GETDATE() AS date)) AS d "
            "      FROM sales_invoices WHERE invoice_status='confirmed' "
            "      AND total_amount - ISNULL(paid_amount,0) > 0.005) si "
            "LEFT JOIN customers c ON c.customer_id=si.customer_id "
            "GROUP BY ISNULL(c.customer_name_en, si.customer_name_en) ORDER BY total DESC")[:limit]
    return {"total_receivable": _r(sum(float(r.get("balance_due") or 0) for r in rows)),
            "customers": rows, "aging": aging}


@tool
def supplier_balances(limit: int = 50) -> dict:
    """What you owe suppliers: unpaid confirmed purchase invoices per supplier,
    with aging by due date."""
    limit = max(1, min(int(limit or 50), MAX_ROWS))
    rows = db.fetchall(
        f"SELECT TOP {limit} ISNULL(s.supplier_name_en, pi.supplier_name_en) AS supplier, "
        f"COUNT(*) AS unpaid_invoices, SUM(bal) AS balance, "
        f"SUM(CASE WHEN d <= 0 THEN bal ELSE 0 END) AS [not_due], "
        f"SUM(CASE WHEN d BETWEEN 1 AND 30 THEN bal ELSE 0 END) AS [overdue_1_30], "
        f"SUM(CASE WHEN d BETWEEN 31 AND 60 THEN bal ELSE 0 END) AS [overdue_31_60], "
        f"SUM(CASE WHEN d > 60 THEN bal ELSE 0 END) AS [overdue_60_plus] "
        f"FROM (SELECT supplier_id, supplier_name_en, total_amount - ISNULL(paid_amount,0) AS bal, "
        f"      DATEDIFF(day, ISNULL(due_date, invoice_date), CAST(GETDATE() AS date)) AS d "
        f"      FROM purchase_invoices WHERE invoice_status='confirmed' "
        f"      AND total_amount - ISNULL(paid_amount,0) > 0.005) pi "
        f"LEFT JOIN suppliers s ON s.supplier_id=pi.supplier_id "
        f"GROUP BY ISNULL(s.supplier_name_en, pi.supplier_name_en) ORDER BY balance DESC")
    return {"total_payable": _r(sum(float(r.get("balance") or 0) for r in rows)), "suppliers": rows}


@tool
def party_statement(party: str, party_type: str = "customer",
                    date_from: str = "", date_to: str = "") -> dict:
    """Statement for one customer or supplier (party_type 'customer' or
    'supplier'; party = code or part of the name): invoices, payments and
    running balance for the period, with opening balance."""
    f, t = _period(date_from or "2000-01-01", date_to)
    if (party_type or "customer").lower().startswith("sup"):
        p = db.fetchone("SELECT TOP 1 supplier_id AS id, supplier_code AS code, supplier_name_en AS name "
                        "FROM suppliers WHERE supplier_code=? OR supplier_name_en LIKE ? "
                        "ORDER BY CASE WHEN supplier_code=? THEN 0 ELSE 1 END",
                        (party, "%" + party + "%", party))
        if not p:
            return {"error": f"No supplier matching '{party}'."}
        docs_sql = ("SELECT invoice_date AS date, 'Purchase ' + invoice_number AS doc, "
                    "0 AS debit, total_amount AS credit FROM purchase_invoices "
                    "WHERE supplier_id=? AND invoice_status='confirmed'")
        pay_sql = ("SELECT payment_date AS date, 'Payment ' + payment_number AS doc, "
                   "amount AS debit, 0 AS credit FROM payments WHERE supplier_id=?")
        sign = -1          # balance = credit - debit (what we owe)
    else:
        p = db.fetchone("SELECT TOP 1 customer_id AS id, customer_code AS code, customer_name_en AS name "
                        "FROM customers WHERE customer_code=? OR customer_name_en LIKE ? OR phone=? "
                        "ORDER BY CASE WHEN customer_code=? THEN 0 ELSE 1 END",
                        (party, "%" + party + "%", party, party))
        if not p:
            return {"error": f"No customer matching '{party}'."}
        docs_sql = ("SELECT invoice_date AS date, 'Invoice ' + invoice_number AS doc, "
                    "total_amount AS debit, 0 AS credit FROM sales_invoices "
                    "WHERE customer_id=? AND invoice_status='confirmed'")
        pay_sql = ("SELECT payment_date AS date, 'Receipt ' + payment_number AS doc, "
                   "0 AS debit, amount AS credit FROM payments WHERE customer_id=?")
        sign = 1
    union = f"SELECT * FROM ({docs_sql} UNION ALL {pay_sql}) x"
    opening = db.fetchone(f"SELECT ISNULL(SUM(debit),0) AS dr, ISNULL(SUM(credit),0) AS cr "
                          f"FROM ({union}) y WHERE date < ?", (p["id"], p["id"], f)) or {}
    lines = db.fetchall(f"{union} WHERE date BETWEEN ? AND ? ORDER BY date",
                        (p["id"], p["id"], f, t))
    bal = sign * (float(opening.get("dr") or 0) - float(opening.get("cr") or 0))
    for ln in lines:
        bal += sign * (float(ln["debit"] or 0) - float(ln["credit"] or 0))
        ln["balance"] = _r(bal)
    return {"party": p, "period": {"from": f, "to": t},
            "opening_balance": _r(sign * (float(opening.get("dr") or 0) - float(opening.get("cr") or 0))),
            "closing_balance": _r(bal), "lines": lines[:MAX_ROWS],
            "note": "Payments are those recorded in DayBill ▸ Payments. Cash paid at the "
                    "till is inside the invoice's paid amount, not listed as a receipt."}


@tool
def purchase_report(date_from: str = "", date_to: str = "", group_by: str = "supplier") -> dict:
    """Purchases grouped by 'supplier', 'day', 'month' or 'product'. Confirmed only."""
    f, t = _period(date_from, date_to)
    g = (group_by or "supplier").lower()
    if g == "product":
        rows = db.fetchall(
            "SELECT TOP 200 pil.product_name_en AS product, SUM(pil.quantity) AS qty, "
            "SUM(pil.line_amount) AS net, SUM(pil.vat_amount) AS vat, SUM(pil.line_total) AS total, "
            "AVG(pil.unit_price) AS avg_price "
            "FROM purchase_invoice_lines pil JOIN purchase_invoices pi ON pi.purchase_id=pil.purchase_id "
            "WHERE pi.invoice_status='confirmed' AND pi.invoice_date BETWEEN ? AND ? "
            "GROUP BY pil.product_name_en ORDER BY total DESC", (f, t))
    else:
        key = {"supplier": "ISNULL(supplier_name_en,'(none)')",
               "day": "CONVERT(varchar(10), invoice_date, 23)",
               "month": "CONVERT(varchar(7), invoice_date, 23)"}.get(g)
        if not key:
            raise ValueError("group_by must be supplier, day, month or product")
        rows = db.fetchall(
            f"SELECT {key} AS [{g}], COUNT(*) AS invoices, SUM(taxable_amount) AS net, "
            f"SUM(vat_amount) AS vat, SUM(total_amount) AS total, "
            f"SUM(total_amount - ISNULL(paid_amount,0)) AS unpaid "
            f"FROM purchase_invoices WHERE invoice_status='confirmed' AND invoice_date BETWEEN ? AND ? "
            f"GROUP BY {key} ORDER BY " + ("total DESC" if g == "supplier" else key), (f, t))
    return {"period": {"from": f, "to": t}, "group_by": g,
            "total": _r(sum(float(r.get("total") or 0) for r in rows)), "rows": rows}


@tool
def expense_report(date_from: str = "", date_to: str = "") -> dict:
    """Expenses grouped by expense account, plus the full list for the period."""
    f, t = _period(date_from, date_to)
    if not has_table("expenses"):
        return {"error": "This database has no expenses table yet."}
    by_acc = db.fetchall(
        "SELECT ISNULL(a.account_name_en,'(unknown)') AS account, COUNT(*) AS entries, "
        "SUM(e.amount) AS amount, SUM(ISNULL(e.vat_amount,0)) AS vat "
        "FROM expenses e LEFT JOIN accounts a ON a.account_id=e.expense_account_id "
        "WHERE e.expense_date BETWEEN ? AND ? GROUP BY ISNULL(a.account_name_en,'(unknown)') "
        "ORDER BY amount DESC", (f, t))
    items = db.fetchall(
        "SELECT TOP 200 e.expense_date AS date, ISNULL(a.account_name_en,'') AS account, "
        "e.amount, e.vat_amount, e.payment_method, e.reference, e.description "
        "FROM expenses e LEFT JOIN accounts a ON a.account_id=e.expense_account_id "
        "WHERE e.expense_date BETWEEN ? AND ? ORDER BY e.expense_date DESC", (f, t))
    return {"period": {"from": f, "to": t},
            "total": _r(sum(float(r.get("amount") or 0) for r in by_acc)),
            "by_account": by_acc, "entries": items}


@tool
def day_close(date: str = "") -> dict:
    """Z-report style summary for one day (default today): sales by payment
    method, invoices, returns, customer receipts, supplier payments, expenses
    and the expected cash in drawer."""
    d = _period(date or None, date or None)[1] if date else _dt.date.today().isoformat()
    by_pay = db.fetchall(
        "SELECT ISNULL(NULLIF(payment_method,''),'unknown') AS method, COUNT(*) AS invoices, "
        "SUM(total_amount) AS total, SUM(ISNULL(paid_amount,0)) AS collected "
        "FROM sales_invoices WHERE invoice_status='confirmed' AND invoice_date=? "
        "GROUP BY ISNULL(NULLIF(payment_method,''),'unknown')", (d,))
    cash_sales = sum(float(r.get("collected") or 0) for r in by_pay if r["method"] == "cash")
    rec = db.fetchall("SELECT payment_type, payment_method, COUNT(*) AS n, SUM(amount) AS total "
                      "FROM payments WHERE payment_date=? GROUP BY payment_type, payment_method", (d,))
    cash_in = sum(float(r["total"] or 0) for r in rec
                  if r["payment_method"] == "cash" and str(r["payment_type"]).startswith("rec"))
    cash_out = sum(float(r["total"] or 0) for r in rec
                   if r["payment_method"] == "cash" and not str(r["payment_type"]).startswith("rec"))
    exp = []
    if has_table("expenses"):
        exp = db.fetchall("SELECT payment_method, SUM(amount) AS total FROM expenses "
                          "WHERE expense_date=? GROUP BY payment_method", (d,))
    cash_exp = sum(float(r["total"] or 0) for r in exp if (r["payment_method"] or "cash") == "cash")
    ret = {"count": 0, "total": 0}
    if has_table("sales_returns"):
        ret = db.fetchone("SELECT COUNT(*) AS count, ISNULL(SUM(total_amount),0) AS total "
                          "FROM sales_returns WHERE TRY_CONVERT(date, return_date)=?", (d,)) or ret
    return {"date": d, "sales_by_payment_method": by_pay,
            "total_sales": _r(sum(float(r.get("total") or 0) for r in by_pay)),
            "payments_and_receipts": rec, "expenses": exp, "sales_returns": ret,
            "expected_cash_in_drawer_from_today": _r(cash_sales + cash_in - cash_out - cash_exp),
            "note": "Expected cash excludes the opening float and cash refunds for returns."}


@tool
def find_invoice(number: str = "", customer: str = "", date_from: str = "",
                 date_to: str = "", kind: str = "sales") -> dict:
    """Find sales (kind='sales') or purchase (kind='purchase') invoices by
    number, or by customer/supplier name within dates. One exact number
    returns the full invoice with its lines."""
    purchase = (kind or "sales").lower().startswith("pur")
    tbl, idc, party = (("purchase_invoices", "purchase_id", "supplier_name_en") if purchase
                       else ("sales_invoices", "invoice_id", "customer_name_en"))
    lines_tbl = "purchase_invoice_lines" if purchase else "sales_invoice_lines"
    if number:
        inv = db.fetchone(f"SELECT * FROM {tbl} WHERE invoice_number=?", (number.strip(),))
        if inv:
            for k in ("qr_code_data", "zatca_xml", "zatca_response", "zatca_clearance_stamp"):
                inv.pop(k, None)
            inv["lines"] = db.fetchall(
                f"SELECT line_number, product_code, product_name_en, quantity, unit_of_measure_en AS unit, "
                f"unit_price, line_amount, vat_amount, line_total FROM {lines_tbl} "
                f"WHERE {idc}=? ORDER BY line_number", (inv[idc],))
            return {"invoice": inv}
    f, t = _period(date_from or "2000-01-01", date_to)
    params = [f, t]
    where = "invoice_date BETWEEN ? AND ?"
    if number:
        where += " AND invoice_number LIKE ?"; params.append("%" + number + "%")
    if customer:
        where += f" AND {party} LIKE ?"; params.append("%" + customer + "%")
    rows = db.fetchall(
        f"SELECT TOP 100 invoice_number, invoice_date, {party} AS party, total_amount, "
        f"ISNULL(paid_amount,0) AS paid, total_amount-ISNULL(paid_amount,0) AS balance, "
        f"invoice_status FROM {tbl} WHERE {where} ORDER BY invoice_date DESC", tuple(params))
    return {"matches": len(rows), "invoices": rows}


@tool
def profit_and_loss(date_from: str = "", date_to: str = "") -> dict:
    """Profit & Loss from the accounting journals — identical to DayBill ▸
    Accounting ▸ Profit & Loss (posted entries only)."""
    from modules import accounting_engine as acc
    f, t = _period(date_from, date_to)
    res = acc.profit_and_loss(db, f, t)
    res["period"] = {"from": f, "to": t}
    return res


@tool
def trial_balance(date_to: str = "") -> dict:
    """Trial balance up to a date — identical to DayBill ▸ Accounting ▸ Trial Balance."""
    from modules import accounting_engine as acc
    t = _period(None, date_to)[1]
    rows = acc.trial_balance(db, t)
    return {"as_of": t, "total_debit": _r(sum(r["debit"] for r in rows)),
            "total_credit": _r(sum(r["credit"] for r in rows)), "accounts": rows}


@tool
def balance_sheet(date_to: str = "") -> dict:
    """Balance sheet as of a date — identical to DayBill ▸ Accounting ▸ Balance Sheet."""
    from modules import accounting_engine as acc
    t = _period(None, date_to)[1]
    res = acc.balance_sheet(db, t)
    if isinstance(res, dict):
        res["as_of"] = t
    return res


@tool
def account_ledger(account: str, date_from: str = "", date_to: str = "") -> dict:
    """General ledger for one account (code or part of the name, e.g. '1100'
    or 'Cash'): opening balance, every journal line and running balance."""
    from modules import accounting_engine as acc
    a = db.fetchone("SELECT TOP 1 account_id, account_code, account_name_en, account_type "
                    "FROM accounts WHERE account_code=? OR account_name_en LIKE ? "
                    "ORDER BY CASE WHEN account_code=? THEN 0 ELSE 1 END",
                    (account, "%" + account + "%", account))
    if not a:
        return {"error": f"No account matching '{account}'."}
    f, t = _period(date_from, date_to)
    res = acc.general_ledger(db, a["account_id"], f, t) or {"lines": []}
    if isinstance(res, list):
        res = {"lines": res}
    for k, v in list(res.items()):
        if isinstance(v, list) and len(v) > MAX_ROWS:
            res[k] = v[-MAX_ROWS:]
            res["note"] = f"Showing the last {MAX_ROWS} entries."
    res["account"] = a
    res["period"] = {"from": f, "to": t}
    return res


# ── Free-form (guarded) SQL ───────────────────────────────────
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|"
    r"deny|backup|restore|shutdown|dbcc|openrowset|opendatasource|openquery|openxml|bulk|"
    r"waitfor|use|kill|declare|set|into|reconfigure|checkpoint|receive|send|begin|commit|"
    r"rollback|save|disable|enable)\b|\bxp_|\bsp_", re.I)


# ─────────────────────────────────────────────────────────────
# AI inventory management (v6.3) — DayBill's own inventory engine
# (modules/inventory_ai.py, the same one the Smart Insights screen uses)
# ─────────────────────────────────────────────────────────────
def _inv():
    from modules import inventory_ai as IA
    if IA.db is not db:
        IA.use_db(db)
    return IA


def _cap(rows, limit):
    limit = max(1, min(int(limit or 100), MAX_ROWS))
    return rows[:limit], len(rows) > limit


@tool
def inventory_health() -> dict:
    """START HERE for stock questions. One inventory health score (0-100)
    and the most important things to do now, in priority order: items out
    of stock or running out within 3 days, best sellers (A items) running
    low, expired batches, items priced below cost, minus stock, stock that
    may expire before it sells, branch transfers, money stuck in dead stock,
    overstock and product data to fix. Also stock value at cost and price."""
    return _inv().health()


@tool
def stock_forecast(search: str = "", status: str = "", days: int = 30, limit: int = 100) -> dict:
    """Days of stock left and the date each item runs out, from its sales
    speed (last 14 days weighted with the last `days`), plus the trend
    (up / down / flat). status filter: out, critical (≤3 days), low (≤7),
    ok, overstock (>4 months), 'no sales'. search = code / name / barcode."""
    rows, more = _cap(_inv().forecast(days=days, search=search, status=status), limit)
    return {"count": len(rows), "truncated": more, "rows": rows,
            "note": "quantities are in each product's base unit (PCs)"}


@tool
def reorder_plan(supplier: str = "", cover_days: int = 14, days: int = 30, warn_days: int = 7) -> dict:
    """What to order now, grouped by supplier (one purchase order each):
    items that run out within `warn_days` or are at their reorder level,
    with a quantity in the unit they are bought in (Box / Carton …) to cover
    `cover_days` of sales, the supplier's last price and the total cost.
    supplier filters by supplier name. DayBill ▸ Smart Insights ▸ Reorder ▸
    'Make Purchase Order(s)' turns it into draft purchase orders."""
    return _inv().reorder_plan(days=days, cover_days=cover_days, warn_days=warn_days,
                               supplier=supplier)


@tool
def abc_analysis(by: str = "revenue", days: int = 90, limit: int = 100) -> dict:
    """ABC analysis: A items make the first 80 % of sales (by 'revenue',
    'profit' or 'qty' over the last `days`), B the next 15 %, C the rest.
    Includes A items that are out / running low (fix those first)."""
    r = _inv().abc(days=days, by=by)
    r["rows"], r["truncated"] = _cap(r["rows"], limit)
    return r


@tool
def expiry_alerts(days: int = 30) -> dict:
    """Batches that expire within `days` (and expired ones): quantity, value,
    how much will probably NOT sell before the expiry date at the current
    sales speed (first-expiry-first-out), and what to do (sell first,
    discount now, write off / return)."""
    return _inv().expiry(days=days)


@tool
def branch_transfers(cover_days: int = 14, days: int = 30) -> dict:
    """Shops with more than one branch: stock to MOVE between branches
    instead of buying — a branch running out within a week while another
    has more than double what it needs (sales speed per branch)."""
    return _inv().transfers(days=days, cover_days=cover_days)


@tool
def bought_together(product: str = "", days: int = 90, limit: int = 20) -> dict:
    """Market-basket analysis from sales bills: with a product → the items
    most often bought in the same bill with it (% of its bills, lift);
    without → the top pairs bought together. For shelf placement and combo
    offers (Offers & Promotions)."""
    return _inv().bought_together(product=product, days=days, limit=limit)


@tool
def supplier_prices(product: str) -> dict:
    """Purchase price of one product per supplier (per base unit, so a Box
    and a PCs price compare): last, lowest, highest, average, cheapest
    supplier now, price change since the first purchase, recent history."""
    if not (product or "").strip():
        raise ValueError("Give a product name, code or barcode.")
    return _inv().supplier_prices(product)


@tool
def data_check(samples: int = 15) -> dict:
    """Product data problems that break stock and reports: no barcode, stock
    without cost, no selling price, minus stock, a barcode on 2+ products,
    no category / Arabic name / VAT category, selling items without a
    reorder level. Each with a count, how to fix it and examples."""
    return _inv().data_check(samples=samples)


@tool
def price_check(min_margin: float = 5.0) -> dict:
    """Items sold BELOW cost or with a margin under `min_margin` % (selling
    price before VAT vs average cost)."""
    return _inv().price_check(min_margin=min_margin)


@tool
def sales_trends() -> dict:
    """This week vs last week, busiest weekday and hour (last 90 days), and
    the products selling faster / slower (last 14 days vs the 14 before)."""
    _inv()
    from modules import insights as INS
    t = INS.trends()
    t["by_weekday"] = {k: _r(v) for k, v in (t.get("by_weekday") or {}).items()}
    return t


@tool
def daily_briefing() -> dict:
    """A short plain-language briefing for the owner (sales trend, items to
    reorder, dead stock, items below cost) plus the things to check today
    (deleted bills, big discounts, many returns, minus stock)."""
    _inv()
    from modules import insights as INS
    return {"briefing": INS.briefing(),
            "watch_today": [{"what": w, "detail": d} for _i, w, d in INS.watch()]}


# ── ready-made questions (Claude ▸ + ▸ prompts) ─────────────
PROMPTS = {
    "daily_stock_check": ("Daily stock check",
                          "Using DayBill, call inventory_health and daily_briefing. Give me the "
                          "5 most important things to do in the shop today, short, with numbers."),
    "what_to_order": ("What to order this week",
                      "Using DayBill, call reorder_plan (cover 14 days). Make one clean order list "
                      "per supplier (item, quantity + unit, price, total) that I can send. Then list "
                      "best sellers that are low but have no supplier yet."),
    "weekly_review": ("Weekly business review",
                      "Using DayBill, call business_overview for the last 7 days, sales_trends and "
                      "abc_analysis. Explain how the week went, what sold well, what to watch, in "
                      "simple words, with a short table."),
    "expiry_and_dead_stock": ("Expiry & dead stock clean-up",
                              "Using DayBill, call expiry_alerts (30 days) and slow_moving_products "
                              "(60 days). Suggest what to discount, put in front, return or write off, "
                              "and the money involved."),
    "price_and_margin": ("Price & margin check",
                         "Using DayBill, call price_check and supplier_prices for the items below "
                         "cost. Tell me which selling prices to change and to how much."),
    "fix_product_data": ("Fix product data",
                         "Using DayBill, call data_check. Give me a short to-do list to clean my "
                         "products, most important first."),
    "vat_month_check": ("Month-end VAT check",
                        "Using DayBill, run_report output_vat and input_vat for last month and "
                        "vat_report. Check the totals match and list anything odd before I file."),
}


def _add_prompts():
    if not hasattr(server, "prompt"):
        return
    for key, (title, text) in PROMPTS.items():
        def make(t=text):
            def fn() -> str:
                return t
            return fn
        try:
            server.prompt(name=key, description=title)(make())
        except TypeError:
            try:
                server.prompt(key, title)(make())
            except Exception:
                pass
        except Exception:
            pass


_add_prompts()


def _check_select(sql):
    s = re.sub(r"--[^\n]*", " ", sql or "")
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = s.strip().rstrip(";").strip()
    if not s:
        raise ValueError("Empty query.")
    if ";" in s:
        raise ValueError("Only one statement is allowed.")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise ValueError("Only SELECT (or WITH … SELECT) queries are allowed.")
    # ignore words inside string literals when checking keywords
    bare = re.sub(r"'(?:''|[^'])*'", "''", s)
    bad = _FORBIDDEN.search(bare)
    if bad:
        raise ValueError(f"'{bad.group(0)}' is not allowed — this connector is read-only.")
    return s


@tool
def run_sql(query: str) -> dict:
    """Run ONE read-only SELECT query (T-SQL, SQL Server) against the DayBill
    database for anything the other tools don't cover. Max 500 rows returned.
    Use list_tables / describe_table first to get exact column names. Only
    count invoice_status='confirmed' as real sales/purchases."""
    s = _check_select(query)
    rows, more = db._run(s, (), limit=MAX_ROWS)
    return {"rows": rows, "row_count": len(rows), "truncated": more}


@tool
def list_tables() -> dict:
    """All tables and views in the DayBill database with row counts."""
    rows = db.fetchall(
        "SELECT o.name, CASE o.type WHEN 'U' THEN 'table' ELSE 'view' END AS kind, "
        "(SELECT SUM(p.rows) FROM sys.partitions p WHERE p.object_id=o.object_id "
        " AND p.index_id IN (0,1)) AS rows "
        "FROM sys.objects o WHERE o.type IN ('U','V') AND o.is_ms_shipped=0 ORDER BY o.name")
    return {"count": len(rows), "objects": rows}


@tool
def describe_table(table: str) -> dict:
    """Columns (name, type, nullable) of one table or view."""
    if not re.match(r"^[A-Za-z0-9_]+$", table or ""):
        raise ValueError("Table name may only contain letters, digits and _.")
    cols = db.fetchall(
        "SELECT c.name AS column_name, t.name AS type, c.max_length, c.is_nullable "
        "FROM sys.columns c JOIN sys.types t ON t.user_type_id=c.user_type_id "
        "WHERE c.object_id=OBJECT_ID(?) ORDER BY c.column_id", (table,))
    if not cols:
        return {"error": f"No table or view named '{table}'."}
    return {"table": table, "columns": cols}


def main():
    if "--test" in sys.argv:            # connection check for the installer
        try:
            info = database_info()
        except Exception as e:
            info = {"error": str(e)}
        if isinstance(info, dict) and info.get("error"):
            print("  Connection failed:", info["error"])
            sys.exit(1)
        comp = (info.get("company") or {}).get("company_name_en", "?")
        print(f"  Connected: {info.get('database')} on {info.get('server')}  —  {comp}")
        print(f"  Records: {info.get('record_counts')}")
        return
    server.run("stdio")


if __name__ == "__main__":
    main()
