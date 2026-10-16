# ============================================================
# DayBill ERP - "Ask AI" about your stock (v6.3)
# ------------------------------------------------------------
# Type a question in plain words ("what should I order this week?",
# "ايش الأصناف اللي بتخلص؟") → Claude answers using DayBill's own
# inventory engine (modules/inventory_ai.py) as tools: it asks for the
# forecast, reorder plan, ABC, expiry … and explains the result.
#
# Needs the Claude API key (Settings ▸ AI). Only stock and sales
# figures, product and supplier names are sent — never customer names,
# never the database itself. Nothing is changed: every tool only reads.
# ============================================================

import json
import queue
import threading

from modules import ai_client as AI
from modules import inventory_ai as IA

MAX_ROUNDS = 6
MAX_RESULT = 14000          # characters of one tool answer sent back

SYSTEM = (
    "You are the stock assistant inside DayBill ERP, the point-of-sale and accounting "
    "program of a retail shop in Saudi Arabia. Answer the owner's question about stock, "
    "ordering, sales speed, expiry, prices and suppliers. ALWAYS get the numbers from the "
    "tools — never invent figures. Money is SAR. Quantities are in each product's base "
    "unit unless a unit is given. Reply in the language of the question (Arabic or "
    "English), short and practical: what to do, with the key numbers; use a small table "
    "or a list when there are several items. If a tool returns nothing, say so plainly.")


def _schema(props=None, required=None):
    return {"type": "object", "properties": props or {}, "required": required or []}


_S = {"type": "string"}
_I = {"type": "integer"}
_N = {"type": "number"}

TOOLS = [
    {"name": "inventory_health",
     "description": "Health score 0-100 of the stock and the most important things to do now.",
     "input_schema": _schema()},
    {"name": "stock_forecast",
     "description": "Sales speed per day, trend, days of stock left and run-out date per item. "
                    "status: out, critical, low, ok, overstock, 'no sales'. search: code/name/barcode.",
     "input_schema": _schema({"search": _S, "status": _S, "limit": _I})},
    {"name": "reorder_plan",
     "description": "What to order now, quantity in the purchase unit, grouped by supplier with cost.",
     "input_schema": _schema({"supplier": _S, "cover_days": _I})},
    {"name": "abc_analysis",
     "description": "A/B/C items by revenue, profit or qty over the last days; A items at risk.",
     "input_schema": _schema({"by": {"type": "string", "enum": ["revenue", "profit", "qty"]},
                              "days": _I})},
    {"name": "expiry_alerts",
     "description": "Batches expiring within N days, qty that will not sell in time, advice.",
     "input_schema": _schema({"days": _I})},
    {"name": "dead_stock",
     "description": "Items with stock that did not sell for N days, with the money stuck.",
     "input_schema": _schema({"days": _I})},
    {"name": "branch_transfers",
     "description": "Stock to move between branches instead of buying (multi-branch shops).",
     "input_schema": _schema({"cover_days": _I})},
    {"name": "bought_together",
     "description": "Items bought in the same bill as a product (or top pairs if no product).",
     "input_schema": _schema({"product": _S, "days": _I})},
    {"name": "supplier_prices",
     "description": "Purchase price of one product per supplier, cheapest supplier, trend.",
     "input_schema": _schema({"product": _S}, ["product"])},
    {"name": "price_check",
     "description": "Items priced below cost or with a thin margin.",
     "input_schema": _schema({"min_margin": _N})},
    {"name": "data_check",
     "description": "Product data problems (no barcode, no cost, minus stock, duplicate barcodes …).",
     "input_schema": _schema()},
    {"name": "sales_trends",
     "description": "This week vs last week, busiest day and hour, items selling faster / slower.",
     "input_schema": _schema()},
]


def _cut(rows, n):
    return rows[:n] if isinstance(rows, list) else rows


def run_tool(name, args):
    """Run one inventory tool (read-only) → a JSON-able answer."""
    a = dict(args or {})
    from modules import insights as INS
    if name == "inventory_health":
        return IA.health()
    if name == "stock_forecast":
        return {"rows": _cut(IA.forecast(search=a.get("search", ""), status=a.get("status", "")),
                             int(a.get("limit") or 60))}
    if name == "reorder_plan":
        return IA.reorder_plan(supplier=a.get("supplier", ""), cover_days=int(a.get("cover_days") or 14))
    if name == "abc_analysis":
        r = IA.abc(days=int(a.get("days") or 90), by=a.get("by") or "revenue")
        r["rows"] = _cut(r["rows"], 60)
        return r
    if name == "expiry_alerts":
        return IA.expiry(days=int(a.get("days") or 30))
    if name == "dead_stock":
        return {"rows": _cut(INS.dead_stock(int(a.get("days") or 60)), 60)}
    if name == "branch_transfers":
        return IA.transfers(cover_days=int(a.get("cover_days") or 14))
    if name == "bought_together":
        return IA.bought_together(product=a.get("product", ""), days=int(a.get("days") or 90))
    if name == "supplier_prices":
        return IA.supplier_prices(a.get("product", ""))
    if name == "price_check":
        return IA.price_check(float(a.get("min_margin") or 5.0))
    if name == "data_check":
        return IA.data_check(samples=8)
    if name == "sales_trends":
        return INS.trends()
    raise ValueError("Unknown tool %s" % name)


def _json(v):
    s = json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= MAX_RESULT else s[:MAX_RESULT] + ' …"(cut — ask for fewer items)"'


class Chat:
    """One conversation. ask() for a plain call; ask_async() keeps the
    screen alive (the internet call runs in the background, the tools run
    on the screen's thread — the database is never used from two threads)."""

    def __init__(self, post=None):
        self.messages = []
        self.tools_used = []
        self._post = post or AI._post

    def _payload(self):
        return {"model": AI._model("vision"), "max_tokens": 1600, "system": SYSTEM,
                "tools": TOOLS, "messages": self.messages}

    def _after_reply(self, res):
        """→ ('more', None) when tools were called (results added), or
        ('done', answer text)."""
        content = res.get("content") or []
        self.messages.append({"role": "assistant", "content": content})
        calls = [b for b in content if b.get("type") == "tool_use"]
        if calls and res.get("stop_reason") == "tool_use":
            results = []
            for b in calls:
                self.tools_used.append(b.get("name"))
                try:
                    out = _json(run_tool(b.get("name"), b.get("input") or {}))
                    results.append({"type": "tool_result", "tool_use_id": b.get("id"), "content": out})
                except Exception as e:
                    results.append({"type": "tool_result", "tool_use_id": b.get("id"),
                                    "content": "Error: %s" % str(e)[:300], "is_error": True})
            self.messages.append({"role": "user", "content": results})
            return "more", None
        text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
        return "done", text or "(no answer)"

    def ask(self, question):
        self.messages.append({"role": "user", "content": str(question)})
        for _ in range(MAX_ROUNDS):
            kind, text = self._after_reply(self._post(self._payload(), timeout=90))
            if kind == "done":
                return text
        return "I needed too many steps — please ask a smaller question."

    def ask_async(self, widget, question, on_done, on_status=None):
        """on_done(text, error) is called on the screen's thread."""
        self.messages.append({"role": "user", "content": str(question)})
        state = {"round": 0}

        def call():
            q = queue.Queue()
            payload = self._payload()

            def work():
                try:
                    q.put(("ok", self._post(payload, timeout=90)))
                except Exception as e:                      # AIError: friendly text
                    q.put(("err", e))
            threading.Thread(target=work, daemon=True).start()

            def poll():
                try:
                    kind, val = q.get_nowait()
                except queue.Empty:
                    widget.after(150, poll)
                    return
                if kind == "err":
                    on_done(None, str(val))
                    return
                k, text = self._after_reply(val)
                if k == "done":
                    on_done(text, None)
                    return
                state["round"] += 1
                if state["round"] >= MAX_ROUNDS:
                    on_done(None, "Too many steps — ask a smaller question.")
                    return
                if on_status:
                    on_status("Looking at: " + ", ".join(self.tools_used[-3:]).replace("_", " ") + " …")
                call()
            widget.after(150, poll)
        call()
