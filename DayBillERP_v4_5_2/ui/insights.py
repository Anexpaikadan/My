# ============================================================
# DayBill ERP - 🤖 Smart Insights page — AI inventory (v6.3)
# ------------------------------------------------------------
# Health score + what to do now, then tabs: Reorder (one-click Purchase
# Order per supplier), Forecast (days left / run-out date), ABC, Expiry,
# Not selling, Price, Bought together, Branches (2+ branches), Data
# check, Trends, Today. All worked out from your own data, offline
# (modules/insights.py + modules/inventory_ai.py).
# 💬 Ask AI: questions in plain words, answered by Claude with these
# numbers (needs the API key in Settings ▸ AI).
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules import insights as AI
from modules import inventory_ai as IA

PRIO = {"high": "#DC2626", "medium": "#D97706", "low": "#2563EB"}


def _money(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


def _qty(v):
    try:
        v = float(v)
        return f"{v:,.3f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
    except Exception:
        return str(v)


class InsightsView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build(C)
        self.refresh()

    def _build(self, C):
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(top, text="🤖  Smart Insights", font=("Segoe UI", 16, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Label(top, text="AI inventory — worked out from your own sales & stock",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=12, pady=(6, 0))
        tk.Button(top, text="🔄  Refresh", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self.refresh).pack(side="right")
        tk.Button(top, text="🔌  Claude desktop", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=self._connector).pack(side="right", padx=6)
        tk.Button(top, text="💬  Ask AI", font=("Segoe UI", 9, "bold"),
                  bg=C.get("tile_purple", "#8B5CF6"), fg="white", relief="flat", padx=14, pady=5,
                  cursor="hand2", command=self.ask_ai).pack(side="right")

        # health card: score + what to do now
        self.brief = tk.Frame(self.frame, bg=C["card_bg"], highlightthickness=1,
                              highlightbackground=C["border"])
        self.brief.pack(fill="x", padx=16, pady=(2, 8))

        st = ttk.Style()           # compact tabs: all 11 fit on a 1366 screen
        st.configure("AIns.TNotebook.Tab", padding=[7, 4], font=("Segoe UI", 9))
        nb = ttk.Notebook(self.frame, style="AIns.TNotebook")
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.nb = nb
        self.t_reorder = self._tab(nb, "📦 Reorder",
                                   [("name", "Product", 220, "w"), ("stock", "In stock", 80, "e"),
                                    ("per_day", "Sells / day", 80, "e"),
                                    ("left", "Days left", 80, "e"),
                                    ("order", "Suggest order", 120, "e"),
                                    ("supplier", "Last supplier", 160, "w"),
                                    ("value", "Approx. cost", 100, "e")])
        bar = tk.Frame(self.t_reorder.master.master, bg=C["content_bg"])
        bar.pack(fill="x", before=self.t_reorder.master)
        tk.Label(bar, text="Based on the last 30 days of sales, to cover 14 days.",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=4, pady=6)
        tk.Button(bar, text="📤  Make & send POs", font=("Segoe UI", 9, "bold"),
                  bg=C["success"], fg="white", relief="flat", padx=12, pady=5,
                  cursor="hand2", command=self._make_send_po).pack(side="right", padx=4, pady=4)
        tk.Button(bar, text="📋  Make POs (check first)", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=12, pady=5,
                  cursor="hand2", highlightthickness=1, highlightbackground=C["border"],
                  command=self._make_po).pack(side="right", padx=4, pady=4)
        tk.Button(bar, text="📥  Excel", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=lambda: self._excel(self.t_reorder, "Reorder_Suggestions")).pack(
                      side="right", padx=4)

        # 🔮 forecast — days of stock left
        self.t_fc = self._tab(nb, "🔮 Forecast",
                              [("name", "Product", 230, "w"), ("stock", "In stock", 80, "e"),
                               ("speed", "Sells / day", 85, "e"), ("trend", "Trend", 70, "center"),
                               ("left", "Days left", 80, "e"), ("date", "Runs out on", 100, "center"),
                               ("status", "Status", 200, "w"), ("value", "Stock value", 100, "e")])
        fb = self._bar(self.t_fc, "Speed = last 14 days (60 %) + last 30 days (40 %).")
        self.fc_filter = tk.StringVar(value="Needs action")
        cb = ttk.Combobox(fb, textvariable=self.fc_filter, state="readonly", width=16,
                          values=["Needs action", "All", "Out of stock", "Within 3 days",
                                  "Within 7 days", "Overstock", "Not selling"])
        cb.pack(side="right", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill_forecast())
        tk.Label(fb, text="Show", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="right")

        # 🅰 ABC
        self.t_abc = self._tab(nb, "🅰 ABC",
                               [("cls", "Class", 55, "center"), ("name", "Product", 240, "w"),
                                ("revenue", "Sales (90 d)", 110, "e"), ("profit", "Profit", 100, "e"),
                                ("qty", "Qty", 80, "e"), ("share", "Share %", 75, "e"),
                                ("cum", "Running %", 80, "e"), ("left", "Days left", 80, "e")])
        ab = self._bar(self.t_abc, "A = first 80 % of sales (never let them run out) · B = next 15 % · C = the rest.")
        self.abc_by = tk.StringVar(value="revenue")
        cb = ttk.Combobox(ab, textvariable=self.abc_by, state="readonly", width=9,
                          values=["revenue", "profit", "qty"])
        cb.pack(side="right", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill_abc())
        tk.Label(ab, text="By", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="right")

        # ⏳ expiry
        self.t_exp = self._tab(nb, "⏳ Expiry",
                               [("name", "Product", 210, "w"), ("batch", "Batch", 80, "w"),
                                ("date", "Expiry", 95, "center"), ("left", "Days left", 75, "e"),
                                ("qty", "Qty", 70, "e"), ("risk", "Won't sell", 80, "e"),
                                ("value", "At risk SAR", 95, "e"), ("advice", "What to do", 330, "w")])
        self._bar(self.t_exp, "Batches expiring within 30 days. 'Won't sell' = more than the sales "
                              "speed sells before the date (first expiry first).")

        self.t_dead = self._tab(nb, "💤 Not selling",
                                [("name", "Product", 260, "w"), ("stock", "In stock", 90, "e"),
                                 ("last", "Last sale", 110, "center"),
                                 ("value", "Stock value", 110, "e")])
        self.t_cost = self._tab(nb, "💸 Price",
                                [("name", "Product", 260, "w"),
                                 ("price", "Price (excl VAT)", 120, "e"),
                                 ("cost", "Average cost", 110, "e"),
                                 ("margin", "Margin %", 90, "e")])

        # 🛒 bought together
        self.t_tog = self._tab(nb, "🛒 Together",
                               [("a", "Item", 260, "w"), ("b", "Bought with", 260, "w"),
                                ("n", "Bills together", 100, "e"), ("pct", "% of its bills", 100, "e"),
                                ("lift", "Lift", 70, "e")])
        tb = self._bar(self.t_tog, "Last 90 days. Shelf them close or make a combo offer.")
        self.tog_var = tk.StringVar()
        tk.Button(tb, text="Show", font=("Segoe UI", 9), relief="flat", bg=C["card_bg"],
                  highlightthickness=1, highlightbackground=C["border"], cursor="hand2",
                  command=self._fill_together).pack(side="right", padx=4)
        en = tk.Entry(tb, textvariable=self.tog_var, width=22, font=("Segoe UI", 10),
                      relief="solid", bd=1)
        en.pack(side="right", ipady=2)
        en.bind("<Return>", lambda e: self._fill_together())
        tk.Label(tb, text="Product (empty = top pairs)", font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right", padx=4)

        # 🔁 branches (only when there are 2+ branches)
        self.t_br = None
        try:
            from modules import stock_branch as SB
            multi = SB.multi()
        except Exception:
            multi = False
        if multi:
            self.t_br = self._tab(nb, "🔁 Branches",
                                  [("name", "Product", 230, "w"), ("from", "From", 140, "w"),
                                   ("to", "To", 140, "w"), ("qty", "Move", 70, "e"),
                                   ("has", "From has", 80, "e"), ("to_has", "To has", 80, "e"),
                                   ("speed", "To sells / day", 100, "e"), ("value", "Value", 90, "e")])
            self._bar(self.t_br, "Move stock instead of buying — Inventory ▸ Stock Transfer.")

        # 🧹 data check
        self.t_dq = self._tab(nb, "🧹 Data",
                              [("what", "Problem", 230, "w"), ("count", "Items", 70, "e"),
                               ("fix", "How to fix", 380, "w"), ("eg", "For example", 300, "w")])

        self.t_trend = tk.Frame(nb, bg=C["content_bg"])
        nb.add(self.t_trend, text="📈 Trends")
        self.t_watch = self._tab(nb, "👀 Today",
                                 [("icon", "", 40, "center"), ("what", "What", 320, "w"),
                                  ("detail", "Detail", 360, "w")])

    def _bar(self, tv, text):
        C = self.C
        bar = tk.Frame(tv.master.master, bg=C["content_bg"])
        bar.pack(fill="x", before=tv.master)
        tk.Label(bar, text=text, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=4, pady=6)
        return bar

    def _tab(self, nb, title, cols):
        C = self.C
        page = tk.Frame(nb, bg=C["content_bg"])
        nb.add(page, text=title)
        wrap = tk.Frame(page, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True)
        tv = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for cid, txt, w, a in cols:
            tv.heading(cid, text=txt)
            tv.column(cid, width=w, anchor=a)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        tv.tag_configure("red", foreground=C["danger"])
        tv.tag_configure("amber", foreground=C["warning"])
        return tv

    # ── data ──────────────────────────────────────────────────
    def refresh(self):
        C = self.C
        for w in self.brief.winfo_children():
            w.destroy()
        try:
            h = IA.health()
        except Exception as e:
            h = {"score": None, "grade": "", "actions": [{"priority": "low", "what": str(e)[:200]}]}
        self._health = h
        sc = h.get("score")
        col = C["success"] if (sc or 0) >= 85 else (C["warning"] if (sc or 0) >= 65 else C["danger"])
        left = tk.Frame(self.brief, bg=C["card_bg"])
        left.pack(side="left", padx=(14, 6), pady=8)
        cv = tk.Canvas(left, width=86, height=86, bg=C["card_bg"], highlightthickness=0)
        cv.pack()
        cv.create_oval(5, 5, 81, 81, outline=C["border"], width=7)
        if sc is not None:
            cv.create_arc(5, 5, 81, 81, start=90, extent=-3.6 * sc, style="arc", outline=col, width=7)
        cv.create_text(43, 38, text="—" if sc is None else str(sc), font=("Segoe UI", 18, "bold"),
                       fill=C["text_primary"])
        cv.create_text(43, 60, text=h.get("grade", ""), font=("Segoe UI", 8), fill=col)
        tk.Label(left, text="Stock health", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack()
        right = tk.Frame(self.brief, bg=C["card_bg"])
        right.pack(side="left", fill="both", expand=True, padx=(6, 14), pady=8)
        head = tk.Frame(right, bg=C["card_bg"]); head.pack(fill="x")
        tk.Label(head, text="What to do now", font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
        if h.get("stock_value_cost") is not None:
            tk.Label(head, text="Stock value %s SAR at cost  ·  %s at selling price"
                     % (_money(h.get("stock_value_cost")), _money(h.get("stock_value_price"))),
                     font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"]).pack(side="right")
        try:
            trend = AI.briefing()[0]
        except Exception:
            trend = ""
        for a in (h.get("actions") or [])[:5]:
            row = tk.Frame(right, bg=C["card_bg"]); row.pack(fill="x")
            tk.Label(row, text="●", font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=PRIO.get(a.get("priority"), C["primary"])).pack(side="left", padx=(2, 6))
            tk.Label(row, text=a.get("what", ""), font=("Segoe UI", 10), bg=C["card_bg"],
                     fg=C["text_primary"], anchor="w", justify="left",
                     wraplength=900).pack(side="left", fill="x")
        if trend and trend.startswith("Sales"):
            tk.Label(right, text="📈  " + trend, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"], anchor="w").pack(fill="x", pady=(2, 0))

        self._reorder = AI.reorder()
        tv = self.t_reorder
        tv.delete(*tv.get_children())
        for i, r in enumerate(self._reorder):
            left = "—" if r["days_left"] is None else f"{r['days_left']:g}"
            tag = ("red",) if (r["days_left"] is not None and r["days_left"] <= 3) or r["stock"] <= 0 \
                else ("amber",)
            tv.insert("", "end", iid=str(i), values=(
                r["name"], _qty(r["stock"]), f"{r['per_day']:g}", left,
                f"{r['order_qty']} {r['unit']}", r["supplier"] or "—", _money(r["value"])),
                tags=tag)
        if not self._reorder:
            self.t_reorder.insert("", "end", values=("✔ Nothing to reorder now", "", "", "", "", "", ""))
        tv = self.t_dead
        tv.delete(*tv.get_children())
        for r in AI.dead_stock():
            tv.insert("", "end", values=(r["name"], _qty(r["stock"]), r["last_sale"],
                                         _money(r["value"])))
        tv = self.t_cost
        tv.delete(*tv.get_children())
        for r in AI.below_cost():
            tv.insert("", "end", values=(r["name"], _money(r["price_net"]), _money(r["cost"]),
                                         f"{r['margin']:.1f}"),
                      tags=("red",) if r["loss"] else ("amber",))
        tv = self.t_watch
        tv.delete(*tv.get_children())
        for icon, what, detail in AI.watch() or [("✔", "Nothing unusual today", "")]:
            tv.insert("", "end", values=(icon, what, detail))
        self._trends()
        for fn in (self._fill_forecast, self._fill_abc, self._fill_expiry, self._fill_together,
                   self._fill_branches, self._fill_data):
            try:
                fn()
            except Exception:
                pass

    # ── new AI inventory tabs (v6.3) ──────────────────────────
    FC_FILTER = {"Needs action": ("out", "critical", "low"), "Out of stock": ("out",),
                 "Within 3 days": ("out", "critical"), "Within 7 days": ("out", "critical", "low"),
                 "Overstock": ("overstock",), "Not selling": ("no sales",)}
    TREND = {"up": "▲ up", "down": "▼ down", "flat": "–"}

    def _fill_forecast(self):
        tv = self.t_fc
        tv.delete(*tv.get_children())
        want = self.FC_FILTER.get(self.fc_filter.get())
        for r in IA.forecast():
            if want and r["status"] not in want:
                continue
            tag = ("red",) if r["status"] in ("out", "critical") else \
                (("amber",) if r["status"] in ("low", "overstock") else ())
            tv.insert("", "end", values=(
                r["name"], _qty(r["stock"]), f"{r['sells_per_day']:g}", self.TREND[r["trend"]],
                "—" if r["days_left"] is None else f"{r['days_left']:g}", r["runs_out_on"] or "—",
                r["status_text"], _money(r["stock_value"])), tags=tag)
        if not tv.get_children():
            tv.insert("", "end", values=("✔ Nothing here — no item runs out within 7 days"
                                         if want and "low" in want else "✔ Nothing here",
                                         "", "", "", "", "", "", ""))

    def _fill_abc(self):
        tv = self.t_abc
        tv.delete(*tv.get_children())
        res = IA.abc(by=self.abc_by.get())
        for r in res["rows"]:
            tag = ("red",) if r["class"] == "A" and r["status"] in ("out", "critical", "low") else ()
            tv.insert("", "end", values=(
                r["class"], r["name"], _money(r["revenue"]), _money(r["profit"]), _qty(r["qty"]),
                f"{r['share_pct']:.1f}", f"{r['cumulative_pct']:.1f}",
                "—" if r["days_left"] is None else f"{r['days_left']:g}"), tags=tag)

    def _fill_expiry(self):
        tv = self.t_exp
        tv.delete(*tv.get_children())
        res = IA.expiry(30)
        if not res.get("rows"):
            tv.insert("", "end", values=("No batch expires within 30 days" if res.get("tracked")
                                         else "No expiry dates kept (Product ▸ Track expiry dates)",
                                         "", "", "", "", "", "", ""))
        for r in res.get("rows") or []:
            tag = ("red",) if (r["days_left"] is not None and r["days_left"] < 0) or r["qty_at_risk"] > 0 \
                else ()
            tv.insert("", "end", values=(
                r["name"], r["batch_no"], r["expiry_date"],
                "—" if r["days_left"] is None else r["days_left"], _qty(r["qty"]),
                _qty(r["qty_at_risk"]), _money(r["value_at_risk"]), r["advice"]), tags=tag)

    def _fill_together(self):
        tv = self.t_tog
        tv.delete(*tv.get_children())
        prod = self.tog_var.get().strip()
        try:
            res = IA.bought_together(product=prod)
        except ValueError as e:
            tv.insert("", "end", values=(str(e), "", "", "", ""))
            return
        if prod:
            for r in res["rows"]:
                tv.insert("", "end", values=(res["product"], r["name"], r["bills_together"],
                                             f"{r['pct_of_its_bills']:.0f}", f"{r['lift']:g}"))
        else:
            for r in res["rows"]:
                tv.insert("", "end", values=(r["item_1"], r["item_2"], r["bills_together"], "",
                                             f"{r['lift']:g}"))
        if not res["rows"]:
            tv.insert("", "end", values=("Not enough bills with 2+ items yet.", "", "", "", ""))

    def _fill_branches(self):
        if self.t_br is None:
            return
        tv = self.t_br
        tv.delete(*tv.get_children())
        for r in IA.transfers().get("suggestions") or []:
            tv.insert("", "end", values=(r["name"], r["from_branch"], r["to_branch"], _qty(r["qty"]),
                                         _qty(r["from_has"]), _qty(r["to_has"]),
                                         f"{r['to_sells_per_day']:g}", _money(r["value"])))

    def _fill_data(self):
        tv = self.t_dq
        tv.delete(*tv.get_children())
        res = IA.data_check(samples=3)
        for c in res["checks"]:
            if not c["count"]:
                continue
            eg = ", ".join((x["name"] or x["code"] or "") + (" (%s)" % x["detail"] if x["detail"] else "")
                           for x in c["samples"][:3])
            tv.insert("", "end", values=(c["title"], c["count"], c["fix"], eg),
                      tags=("red",) if c["check"] in ("negative_stock", "duplicate_barcode", "no_cost",
                                                      "no_price") else ("amber",))
        if not tv.get_children():
            tv.insert("", "end", values=("✔ Product data looks clean", "", "", ""))

    # ── 💬 Ask AI · 🔌 Claude desktop ────────────────────────
    def ask_ai(self):
        self._ask = AskAIWindow(self.frame, self.C)
        return self._ask

    def _connector(self):
        """Claude desktop app (MCP connector): installs / shows how to."""
        here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "claude_connector")
        bat = os.path.join(here, "INSTALL_CLAUDE_CONNECTOR.bat")
        msg = ("Claude desktop can read DayBill (read-only) and answer questions like "
               "'what should I order this week?' with 36 tools (stock health, forecast, "
               "reorder plan, ABC, expiry, branch transfers, bought together, supplier "
               "prices, data check, VAT, reports …) and ready-made prompts.\n\n")
        if os.path.exists(bat):
            if messagebox.askyesno("Claude desktop",
                                   msg + "Install / update it on this PC now?\n(needs Python and "
                                         "internet; then quit and reopen Claude)", parent=self.frame):
                try:
                    os.startfile(bat)
                except Exception as e:
                    messagebox.showerror("Claude desktop", str(e)[:300], parent=self.frame)
                return True
            return False
        messagebox.showinfo("Claude desktop", msg + "Copy the 'claude_connector' folder from the "
                                                    "DayBill zip next to DayBill, then run "
                                                    "INSTALL_CLAUDE_CONNECTOR.bat.", parent=self.frame)
        return False

    def _trends(self):
        C = self.C
        for w in self.t_trend.winfo_children():
            w.destroy()
        t = AI.trends()
        box = tk.Frame(self.t_trend, bg=C["content_bg"])
        box.pack(fill="x", pady=8)
        chg = "—" if t["change"] is None else f"{t['change']:+.0f}%"
        for i, (lab, val) in enumerate((("This week", _money(t["this_week"])),
                                        ("Last week", _money(t["last_week"])),
                                        ("Change", chg),
                                        ("Busiest day", t["best_day"] or "—"),
                                        ("Busiest hour", "—" if t["best_hour"] is None
                                         else f"{t['best_hour']:02d}:00"))):
            card = tk.Frame(box, bg=C["card_bg"], highlightthickness=1,
                            highlightbackground=C["border"])
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 8))
            box.columnconfigure(i, weight=1)
            tk.Label(card, text=lab, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(card, text=val, font=("Segoe UI", 15, "bold"), bg=C["card_bg"],
                     fg=C["text_primary"]).pack(anchor="w", padx=12, pady=(0, 8))
        cols = tk.Frame(self.t_trend, bg=C["content_bg"])
        cols.pack(fill="both", expand=True)
        for j, (title, rows, color) in enumerate((("⬆  Selling faster (last 14 days)", t["up"], C["success"]),
                                                  ("⬇  Selling slower", t["down"], C["danger"]))):
            f = tk.Frame(cols, bg=C["card_bg"], highlightthickness=1,
                         highlightbackground=C["border"])
            f.grid(row=0, column=j, sticky="nsew", padx=(0, 8) if j == 0 else 0)
            cols.columnconfigure(j, weight=1)
            tk.Label(f, text=title, font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                     fg=color).pack(anchor="w", padx=12, pady=(8, 4))
            for m in rows or []:
                tk.Label(f, text=f"{m['name']}   {m['before']:g} → {m['now']:g}   "
                                 f"({m['change']:+.0f}%)", font=("Segoe UI", 9),
                         bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", padx=16)
            if not rows:
                tk.Label(f, text="Not enough sales yet.", font=("Segoe UI", 9),
                         bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=16)
            tk.Frame(f, bg=C["card_bg"], height=8).pack()

    # ── actions ───────────────────────────────────────────────
    def _excel(self, tv, name):
        try:
            from modules.doc_actions import export_tree_excel
            headers = [tv.heading(c)["text"] for c in tv["columns"]]
            export_tree_excel(self.frame, tv, name, headers, title=name.replace("_", " "))
        except Exception as e:
            messagebox.showerror("Export", str(e)[:300])

    def _make_send_po(self, ask=True):
        """v6.4: one SAVED Purchase Order per supplier, then each one on
        WhatsApp to its supplier (Cloud API: sent; app: chat opens)."""
        from modules import permissions as _pm
        if not _pm.allowed("purchase_order", "add"):
            return None
        sel = [int(i) for i in self.t_reorder.selection() if str(i).isdigit()]
        rows = [self._reorder[i] for i in sel] if sel else list(self._reorder)
        if not rows:
            messagebox.showinfo("Purchase Order", "Nothing to order now.", parent=self.frame)
            return None
        sups = {r.get("supplier") for r in rows if r.get("supplier_id")}
        if ask and not messagebox.askyesno(
                "Make & send", "Save %d purchase order(s) (%s) and send each one to its "
                "supplier on WhatsApp?" % (len(sups), ", ".join(sorted(sups))[:200]), parent=self.frame):
            return None
        from modules import supplier_orders as SO
        try:
            made, skipped = SO.create_from_plan(rows)
        except Exception as e:
            messagebox.showerror("Purchase Order", str(e)[:300], parent=self.frame)
            return None
        sent = 0
        try:
            from modules import whatsapp as _wa
            from ui.whatsapp_send import send_document
            if _wa.enabled():
                for m in made:
                    try:
                        if send_document(self.frame, "purchase_order", m["po_id"], auto=True) is not None:
                            sent += 1
                    except Exception:
                        pass
        except Exception:
            pass
        msg = "Saved: " + ", ".join("%s (%s %.2f)" % (m["number"], m["supplier"], m["total"]) for m in made)
        if skipped:
            msg += "\n\n%d item(s) have no supplier yet — buy them once with a Purchase Invoice." % len(skipped)
        if not sent:
            msg += "\n\nWhatsApp is off (Settings ▸ WhatsApp) — send them from Purchase Orders."
        try:
            from ui.ui_polish import toast
            toast(self.frame.winfo_toplevel(), "%d purchase order(s) saved" % len(made))
        except Exception:
            pass
        messagebox.showinfo("Purchase Orders", msg, parent=self.frame)
        self._made_pos = made
        return made

    def _make_po(self):
        """One draft Purchase Order per supplier with the ticked (selected)
        suggestions — or all of them when nothing is selected."""
        from modules import permissions as _pm
        if not _pm.allowed("purchase_order", "add"):
            return
        sel = [int(i) for i in self.t_reorder.selection() if str(i).isdigit()]
        rows = [self._reorder[i] for i in sel] if sel else list(self._reorder)
        rows = [r for r in rows if r.get("supplier_id")]
        if not rows:
            messagebox.showinfo("Purchase Order",
                                "No suggestion with a known supplier. Buy the item once "
                                "(Purchase Invoice) so DayBill knows who supplies it.")
            return
        by_sup = {}
        for r in rows:
            by_sup.setdefault(r["supplier_id"], []).append(r)
        from ui.quotes import DocForm
        opened = 0
        for sid, items in by_sup.items():
            try:
                f = DocForm(self.frame, "purchase_order")
                p = next((x for x in f._parties if x["id"] == sid), None)
                if p:
                    f.v["party"].set(f"{p['code']} — {p['name']}")
                lines = []
                for r in items:
                    prod = next((x for x in f._products
                                 if x["product_id"] == r["product_id"]), {})
                    rate = float(prod.get("vat_rate") or 15)
                    amt = round(r["order_qty"] * r["unit_cost"], 2)
                    lines.append({
                        "product_id": r["product_id"], "product_code": r["code"],
                        "product_name_en": r["name"],
                        "product_name_ar": prod.get("product_name_ar", ""),
                        "quantity": r["order_qty"], "unit_of_measure_en": r["unit"],
                        "unit_price": r["unit_cost"], "discount_amount": 0,
                        "line_amount": amt, "vat_rate": rate,
                        "vat_category_id": prod.get("vat_category_id"),
                        "vat_category_code": prod.get("vat_code") or "S",
                        "vat_amount": round(amt * rate / 100, 2),
                        "line_total": round(amt * (1 + rate / 100), 2),
                        "box_qty": r["factor"] if r["factor"] != 1 else ""})
                f.grid.set_lines(lines)
                f._on_change()
                opened += 1
            except Exception as e:
                messagebox.showerror("Purchase Order", str(e)[:300])
        if opened:
            try:
                from ui.ui_polish import toast
                toast(self.frame.winfo_toplevel(),
                      f"{opened} draft Purchase Order(s) opened — check and Save.")
            except Exception:
                pass


class AskAIWindow:
    """💬 Ask AI — a question in plain words, the answer from Claude using
    DayBill's inventory numbers (modules/inventory_chat.py)."""
    EXAMPLES = ["What should I order this week?", "Which items run out in 3 days?",
                "What is not selling? How much money is stuck?", "Which best sellers are low?",
                "ايش الأصناف اللي لازم أطلبها؟"]

    def __init__(self, parent, C, post=None):
        from modules import inventory_chat as IC
        from modules import ai_client as AIC
        self.C = C
        self.chat = IC.Chat(post=post)
        self.busy = False
        w = self.win = tk.Toplevel(parent)
        w.title("Ask AI — your stock")
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
            w.geometry("760x600")
        except Exception:
            pass
        head = tk.Frame(w, bg=C["card_bg"]); head.pack(fill="x")
        tk.Label(head, text="💬  Ask AI about your stock", font=("Segoe UI", 13, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", padx=14, pady=(10, 0))
        note = ("Claude answers with DayBill's own numbers (forecast, reorder, ABC, expiry …). "
                "Sent: stock & sales figures, product and supplier names — never customer names. "
                "Nothing is changed.")
        if not AIC.enabled() and post is None:
            note = "⚠ Add your Claude API key first: Settings ▸ AI.   " + note
        tk.Label(head, text=note, font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                 wraplength=720, justify="left").pack(anchor="w", padx=14, pady=(2, 10))
        ex = tk.Frame(w, bg=C["content_bg"]); ex.pack(fill="x", padx=10, pady=(8, 0))
        for q in self.EXAMPLES:
            tk.Button(ex, text=q, font=("Segoe UI", 8), relief="flat", bg=C["card_bg"],
                      fg=C["primary"], cursor="hand2", highlightthickness=1,
                      highlightbackground=C["border"], padx=8, pady=2,
                      command=lambda q=q: self.send(q)).pack(side="left", padx=3, pady=2)
        mid = tk.Frame(w, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        mid.pack(fill="both", expand=True, padx=10, pady=8)
        self.out = tk.Text(mid, wrap="word", font=("Segoe UI", 10), relief="flat", bd=0,
                           bg=C["card_bg"], fg=C["text_primary"], padx=10, pady=8)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.out.yview)
        self.out.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.out.pack(fill="both", expand=True)
        self.out.tag_configure("me", foreground=C["primary"], font=("Segoe UI", 10, "bold"),
                               spacing1=8)
        self.out.tag_configure("ai", spacing1=4, spacing3=6)
        self.out.tag_configure("err", foreground=C["danger"])
        self.out.tag_configure("dim", foreground=C["text_secondary"], font=("Segoe UI", 9, "italic"))
        self.out.configure(state="disabled")
        bot = tk.Frame(w, bg=C["content_bg"]); bot.pack(fill="x", padx=10, pady=(0, 10))
        self.q = tk.StringVar()
        e = tk.Entry(bot, textvariable=self.q, font=("Segoe UI", 11), relief="solid", bd=1)
        e.pack(side="left", fill="x", expand=True, ipady=5)
        e.bind("<Return>", lambda ev: self.send())
        self.send_btn = tk.Button(bot, text="Ask  ➤", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                                  fg="white", relief="flat", padx=16, pady=5, cursor="hand2",
                                  command=self.send)
        self.send_btn.pack(side="left", padx=(8, 0))
        self.status = tk.StringVar()
        tk.Label(w, textvariable=self.status, font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(0, 6))
        e.focus_set()

    def _write(self, text, tag):
        self.out.configure(state="normal")
        self.out.insert("end", text + "\n", tag)
        self.out.configure(state="disabled")
        self.out.see("end")

    def send(self, question=None):
        q = (question or self.q.get()).strip()
        if not q or self.busy:
            return
        self.q.set("")
        self._write("You:  " + q, "me")
        self.busy = True
        self.send_btn.configure(state="disabled")
        self.status.set("Thinking …")
        self.chat.ask_async(self.win, q, self._done, self.status.set)

    def _done(self, text, error):
        self.busy = False
        try:
            self.send_btn.configure(state="normal")
            self.status.set("")
            if error:
                self._write("⚠  " + error, "err")
            else:
                self._write(text, "ai")
                if self.chat.tools_used:
                    used = sorted(set(self.chat.tools_used))
                    self._write("(used: " + ", ".join(u.replace("_", " ") for u in used) + ")", "dim")
        except tk.TclError:
            pass
