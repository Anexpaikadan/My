# ============================================================
# Saudi Arabia ERP - Dashboard View
# KPI Cards + Recent Invoices + VAT Summary
# ============================================================

import tkinter as tk
from tkinter import ttk
import sys, os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t, is_rtl
from config.database import db


class DashboardView:
    def __init__(self, parent):
        C = cfg.theme()
        self.parent = parent

        # Scrollable canvas
        canvas = tk.Canvas(parent, bg=C["content_bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        self.frame = tk.Frame(canvas, bg=C["content_bg"])
        win = canvas.create_window((0, 0), window=self.frame, anchor="nw")

        def on_resize(e):
            canvas.itemconfig(win, width=e.width)
        canvas.bind("<Configure>", on_resize)
        self.frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self._build(C)

    def _build(self, C):
        f = self.frame
        pad_x = 24

        # ── Header ────────────────────────────────────────────
        header = tk.Frame(f, bg=C["content_bg"])
        header.pack(fill="x", padx=pad_x, pady=(16, 14))

        today = date.today().strftime("%A, %d %B %Y")
        who = ""
        try:
            from modules import permissions as _perm
            u = _perm.session_user()
            who = (u.get("full_name_en") or u.get("username") or "").strip()
        except Exception:
            who = ""
        hl = tk.Frame(header, bg=C["content_bg"])
        hl.pack(side="right" if is_rtl() else "left")
        tk.Label(hl, text=t("dashboard.title"),
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"],
                 anchor="e" if is_rtl() else "w").pack(fill="x")
        tk.Label(hl, text=(f"Welcome back, {who} — here is your business today"
                           if who else "Here is your business today"),
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"],
                 anchor="e" if is_rtl() else "w").pack(fill="x")
        tk.Label(header, text="📅  " + today,
                 font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"], padx=12, pady=6,
                 highlightthickness=1, highlightbackground=C["border"]).pack(
                     side="left" if is_rtl() else "right")

        # ── v6.0 warnings: ZATCA 24 hours, expiring batches ──
        self._v6_alerts(f, pad_x, C)

        # ── KPI Cards ─────────────────────────────────────────
        kpi_frame = tk.Frame(f, bg=C["content_bg"])
        kpi_frame.pack(fill="x", padx=pad_x, pady=(0, 14))

        kpis = self._get_kpi_data()
        tiles = [C.get("tile_blue", C["primary"]), C.get("tile_green", C["success"]),
                 C.get("tile_orange", "#F97316"), C.get("tile_purple", "#7C3AED")]
        for i, kpi in enumerate(kpis):
            kpi_frame.columnconfigure(i, weight=1, uniform="kpi")
            kpi["color"] = tiles[i % 4]
            self._kpi_card(kpi_frame, i, **kpi, C=C, solid=True)

        # ── Second KPI row: today's snapshot ──────────────────
        kpi_frame2 = tk.Frame(f, bg=C["content_bg"])
        kpi_frame2.pack(fill="x", padx=pad_x, pady=(0, 20))
        for i, kpi in enumerate(self._get_today_tiles(C)):
            kpi_frame2.columnconfigure(i, weight=1, uniform="kpi2")
            self._kpi_card(kpi_frame2, i, **kpi, C=C)

        # ── 🤖 Smart suggestions (modules/insights) ────────────
        self._ai_card(f, pad_x, C)

        # ── Middle Row: Recent Invoices + VAT Summary ─────────
        mid = tk.Frame(f, bg=C["content_bg"])
        mid.pack(fill="x", padx=pad_x, pady=(0, 20))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)

        self._recent_invoices(mid, C)
        self._vat_summary(mid, C)

        # ── Charts Row: sales trend + receivables aging ───────
        charts = tk.Frame(f, bg=C["content_bg"])
        charts.pack(fill="x", padx=pad_x, pady=(0, 20))
        charts.columnconfigure(0, weight=3)
        charts.columnconfigure(1, weight=2)
        self._sales_trend_chart(charts, C)
        self._aging_chart(charts, C)

        # ── Top Customers ──────────────────────────────────────
        self._top_customers(f, pad_x, C)

    def _v6_alerts(self, f, pad_x, C):
        """Red / orange lines that need action today (v6.0)."""
        msgs = []
        try:
            from modules.zatca import egs as _E
            if _E.any_connected():
                z = _E.overdue_text()
                if z:
                    msgs.append((z, "#FEF2F2", "#B91C1C", "zatca"))
        except Exception:
            pass
        try:
            from modules import batches as _B
            x = _B.alert_text()
            if x:
                msgs.append((x, "#FFF7ED", "#B45309", "expiry"))
        except Exception:
            pass
        self.alerts = [m[0] for m in msgs]
        for text, bg, fg, key in msgs:
            l = tk.Label(f, text=text, font=("Segoe UI", 10, "bold"), bg=bg, fg=fg, anchor="w",
                         padx=12, pady=7, cursor="hand2", wraplength=1100, justify="left")
            l.pack(fill="x", padx=pad_x, pady=(0, 8))
            try:
                from ui.main_window import navigate
                l.bind("<Button-1>", lambda e, k=key: navigate(k))
            except Exception:
                pass

    def _ai_card(self, f, pad_x, C):
        try:
            from modules import insights as AI
            lines = AI.briefing()[:4]
        except Exception:
            return
        card = tk.Frame(f, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        card.pack(fill="x", padx=pad_x, pady=(0, 14))
        head = tk.Frame(card, bg=C["card_bg"]); head.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(head, text="🤖  Smart suggestions", font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")

        def _open(e=None):
            try:
                import ui.main_window as _mw
                _mw.APP._menu_open("insights")
            except Exception:
                pass
        link = tk.Label(head, text="Open Smart Insights  →", font=("Segoe UI", 9, "bold"),
                        bg=C["card_bg"], fg=C["primary"], cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", _open)
        for line in lines:
            tk.Label(card, text="•  " + line, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_primary"], anchor="w", justify="left").pack(fill="x", padx=18)
        tk.Frame(card, bg=C["card_bg"], height=8).pack()

    # ── Charts ─────────────────────────────────────────────────
    def _card_shell(self, parent, col, title, C, height=220):
        card = tk.Frame(parent, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        card.grid(row=0, column=col, sticky="nsew",
                  padx=(0, 12) if col == 0 else (0, 0))
        tk.Label(card, text=title, font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w",
                 padx=16, pady=(12, 4))
        cv = tk.Canvas(card, bg=C["card_bg"], height=height,
                       highlightthickness=0)
        cv.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        return cv

    def _sales_trend_chart(self, parent, C):
        """Bar chart of confirmed sales for the last 12 weeks."""
        cv = self._card_shell(parent, 0, "📈  Sales — last 12 weeks", C)
        weeks = []
        today = date.today()
        for i in range(11, -1, -1):
            start = today - timedelta(days=today.weekday() + 7 * i)
            end = start + timedelta(days=6)
            total = 0.0
            try:
                total = float(db.execute_scalar(
                    "SELECT ISNULL(SUM(total_amount),0) FROM sales_invoices "
                    "WHERE invoice_status='confirmed' AND invoice_date BETWEEN ? AND ?",
                    (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))) or 0)
            except Exception:
                total = 0.0
            weeks.append((start.strftime("%d/%m"), total))
        self._draw_bars(cv, weeks, C, bar_color=C.get("primary", "#3A1FD6"))

    def _aging_chart(self, parent, C):
        """Receivables aging buckets across all customers."""
        cv = self._card_shell(parent, 1, "⏳  Receivables aging", C)
        buckets = {"Current": 0.0, "1-30": 0.0, "31-60": 0.0,
                   "61-90": 0.0, "90+": 0.0}
        try:
            rows = db.fetchall(
                "SELECT invoice_date, ISNULL(total_amount,0) AS total, "
                "ISNULL(paid_amount,0) AS paid FROM sales_invoices "
                "WHERE invoice_status='confirmed'") or []
        except Exception:
            rows = []
        today = date.today()
        for r in rows:
            due = float(r["total"] or 0) - float(r["paid"] or 0)
            if due <= 0.005:
                continue
            d = r["invoice_date"]
            if hasattr(d, "strftime"):
                dd = d if isinstance(d, date) else d.date()
            else:
                try:
                    dd = datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
                except Exception:
                    dd = today
            age = (today - dd).days
            if age <= 0:
                buckets["Current"] += due
            elif age <= 30:
                buckets["1-30"] += due
            elif age <= 60:
                buckets["31-60"] += due
            elif age <= 90:
                buckets["61-90"] += due
            else:
                buckets["90+"] += due
        cols = ["#16A34A", "#65A30D", "#CA8A04", "#EA580C", "#DC2626"]
        data = list(buckets.items())
        self._draw_bars(cv, data, C, per_bar_colors=cols)

    def _draw_bars(self, cv, data, C, bar_color="#2563EB", per_bar_colors=None):
        """Simple responsive bar chart on a Tk canvas."""
        def render(event=None):
            cv.delete("all")
            w = cv.winfo_width() or 400
            h = cv.winfo_height() or 200
            if w < 10:
                cv.after(50, render); return
            pad_l, pad_b, pad_t, pad_r = 46, 26, 12, 10
            plot_w = w - pad_l - pad_r
            plot_h = h - pad_b - pad_t
            vals = [v for _, v in data]
            mx = max(vals) if vals and max(vals) > 0 else 1.0
            # gridlines + y labels
            for gi in range(4):
                yy = pad_t + plot_h * gi / 3
                val = mx * (3 - gi) / 3
                cv.create_line(pad_l, yy, w - pad_r, yy, fill=C["border"])
                cv.create_text(pad_l - 6, yy, anchor="e",
                               text=f"{val:,.0f}", font=("Segoe UI", 7),
                               fill=C["text_secondary"])
            n = len(data)
            if n == 0:
                return
            slot = plot_w / n
            bw = slot * 0.6
            for i, (label, val) in enumerate(data):
                x0 = pad_l + slot * i + (slot - bw) / 2
                bh = (val / mx) * plot_h if mx else 0
                y1 = pad_t + plot_h
                y0 = y1 - bh
                col = per_bar_colors[i] if per_bar_colors else bar_color
                cv.create_rectangle(x0, y0, x0 + bw, y1, fill=col, outline="")
                if val > 0:
                    cv.create_text(x0 + bw / 2, y0 - 6, text=f"{val:,.0f}",
                                   font=("Segoe UI", 7, "bold"),
                                   fill=C["text_primary"])
                cv.create_text(x0 + bw / 2, y1 + 12, text=label,
                               font=("Segoe UI", 7), fill=C["text_secondary"])
        cv.bind("<Configure>", render)
        cv.after(60, render)

    def _get_today_tiles(self, C) -> list:
        from datetime import date as _d
        today = _d.today().strftime("%Y-%m-%d")
        # today's sales
        try:
            ts = db.fetchone(
                "SELECT ISNULL(SUM(total_amount),0) AS total, COUNT(*) AS cnt "
                "FROM sales_invoices WHERE invoice_date=? AND invoice_status='confirmed'",
                (today,)) or {}
        except Exception:
            ts = {"total": 0, "cnt": 0}
        # cash in hand = cash account balance (journal)
        cash = 0.0
        try:
            from modules import account_defaults as ad
            cid = ad.cash()
            if cid:
                cash = float(db.execute_scalar(
                    "SELECT COALESCE(SUM(jl.debit - jl.credit),0) FROM journal_lines jl "
                    "JOIN journal_entries je ON je.journal_id=jl.journal_id "
                    "WHERE jl.account_id=? AND je.is_posted=1", (cid,)) or 0)
        except Exception:
            cash = 0.0
        # low stock count — per-product reorder_level wins; products
        # without one fall back to Settings ▸ Inventory ▸ Low Stock Alert Level
        try:
            _global_low = float(cfg.get("inv_low_stock_level", 0) or 0)
        except Exception:
            _global_low = 0.0
        try:
            low = db.execute_scalar(
                "SELECT COUNT(*) FROM products WHERE track_inventory=1 "
                "AND stock_quantity <= ISNULL(NULLIF(reorder_level,0), ?)",
                (_global_low,)) or 0
        except Exception:
            low = 0
        # top product (this month, by qty)
        top_name, top_qty = "—", 0
        try:
            r = db.fetchone(
                "SELECT TOP 1 li.product_name_en AS name, SUM(li.quantity) AS qty "
                "FROM sales_invoice_lines li JOIN sales_invoices si "
                "ON si.invoice_id=li.invoice_id "
                "WHERE si.invoice_status='confirmed' "
                "AND si.invoice_date >= ? "
                "GROUP BY li.product_name_en ORDER BY SUM(li.quantity) DESC",
                (date.today().replace(day=1).strftime("%Y-%m-%d"),))
            if r:
                top_name = (r["name"] or "—")[:16]
                top_qty = float(r["qty"] or 0)
        except Exception:
            pass
        return [
            {"title": "Today's Sales", "value": f"{float(ts.get('total',0)):,.2f}",
             "icon": "🛒", "color": C["success"],
             "subtitle": f"{ts.get('cnt',0)} invoices today"},
            {"title": "Cash in Hand", "value": f"{cash:,.2f}",
             "icon": "💵", "color": C["primary"], "subtitle": "Cash account balance"},
            {"title": "Low Stock", "value": str(int(low)),
             "icon": "📉", "color": C["danger" if low else "success"],
             "subtitle": "At / below reorder level"},
            {"title": "Top Product", "value": top_name,
             "icon": "🏆", "color": C["info"],
             "subtitle": f"{top_qty:g} sold this month"},
        ]

    # ── KPI Card ──────────────────────────────────────────────
    @staticmethod
    def _mix(c1, c2, f):
        """Blend colour c1 toward c2 by f (0..1)."""
        try:
            a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
            b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
            return "#%02X%02X%02X" % tuple(int(x + (y - x) * f) for x, y in zip(a, b))
        except Exception:
            return c1

    def _kpi_card(self, parent, col, title, value, icon, color, subtitle="", C={},
                  solid=False):
        """solid=True: coloured tile with white text (top row).
        solid=False: white card with a coloured round icon."""
        rtl = is_rtl()
        bg = color if solid else C["card_bg"]
        fg = "white" if solid else C["text_primary"]
        sub_fg = self._mix(color, "#FFFFFF", 0.78) if solid else C["text_secondary"]
        card = tk.Frame(parent, bg=bg, relief="flat", bd=0,
                        highlightbackground=bg if solid else C["border"],
                        highlightthickness=1)
        card.grid(row=0, column=col, padx=(0, 12) if col < 3 else (0, 0),
                  sticky="nsew")

        inner = tk.Frame(card, bg=bg)
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        # round icon badge (right side)
        badge_bg = self._mix(color, "#FFFFFF", 0.22) if solid else self._mix(color, "#FFFFFF", 0.86)
        cv = tk.Canvas(inner, width=46, height=46, bg=bg, highlightthickness=0, bd=0)
        cv.pack(side="left" if rtl else "right", anchor="n")
        cv.create_oval(1, 1, 45, 45, fill=badge_bg, outline="")
        cv.create_text(23, 24, text=icon, font=("Segoe UI Emoji", 16),
                       fill="white" if solid else color)

        txt = tk.Frame(inner, bg=bg)
        txt.pack(side="right" if rtl else "left", fill="both", expand=True)
        tk.Label(txt, text=title, font=("Segoe UI", 9, "bold" if solid else "normal"),
                 bg=bg, fg=sub_fg if solid else C["text_secondary"],
                 anchor="e" if rtl else "w").pack(fill="x")
        tk.Label(txt, text=value, font=("Segoe UI", 19 if solid else 17, "bold"),
                 bg=bg, fg=fg, anchor="e" if rtl else "w").pack(fill="x", pady=(2, 0))
        if subtitle:
            tk.Label(txt, text=subtitle, font=("Segoe UI", 8),
                     bg=bg, fg=sub_fg, anchor="e" if rtl else "w").pack(fill="x")
        if not solid:
            tk.Frame(card, bg=color, height=3).pack(side="bottom", fill="x")

    # ── Recent Invoices Table ─────────────────────────────────
    def _recent_invoices(self, parent, C):
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12), ipady=4)

        # Header
        h = tk.Frame(card, bg=C["card_bg"])
        h.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(h, text=f"🧾  {t('dashboard.recent_invoices')}",
                 font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")

        # Table
        cols = ("invoice_number", "customer", "amount", "status", "date")
        headers = ("Invoice #", "Customer", "Amount (SAR)", "Status", "Date")

        style = ttk.Style()
        style.configure("ERP.Treeview",
                         background=C["card_bg"],
                         foreground=C["text_primary"],
                         fieldbackground=C["card_bg"],
                         rowheight=30,
                         font=("Segoe UI", 9))
        style.configure("ERP.Treeview.Heading",
                         background=C["content_bg"],
                         foreground=C["text_secondary"],
                         font=("Segoe UI", 9, "bold"),
                         relief="flat")
        style.map("ERP.Treeview", background=[("selected", C.get("select_bg", C["primary"]))],
                  foreground=[("selected", C.get("select_fg", "white"))])

        tree = ttk.Treeview(card, columns=cols, show="headings",
                            style="ERP.Treeview", height=8)

        widths = [100, 160, 110, 90, 90]
        for col, header, w in zip(cols, headers, widths):
            tree.heading(col, text=header)
            tree.column(col, width=w, anchor="center")

        tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Load data
        data = self._get_recent_invoices()
        for row in data:
            status_icon = {
                "confirmed": "✅", "draft": "📝", "cancelled": "❌"
            }.get(row.get("invoice_status", ""), "📄")
            tree.insert("", "end", values=(
                row.get("invoice_number", ""),
                row.get("customer_name_en", ""),
                f"{row.get('total_amount', 0):,.2f}",
                f"{status_icon} {row.get('invoice_status', '').title()}",
                str(row.get("invoice_date", ""))
            ))

        if not data:
            tree.insert("", "end", values=("—", t("common.no_data"), "—", "—", "—"))

    # ── VAT Summary ───────────────────────────────────────────
    def _vat_summary(self, parent, C):
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.grid(row=0, column=1, sticky="nsew", ipady=4)

        h = tk.Frame(card, bg=C["card_bg"])
        h.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(h, text=f"📋  {t('dashboard.vat_summary')}",
                 font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")

        month = date.today().strftime("%B %Y")
        tk.Label(h, text=month, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="right")

        vat_data = self._get_vat_summary()

        rows = [
            (t("vat.output_tax"),   f"{vat_data['output']:,.2f} SAR", C["success"]),
            (t("vat.input_tax"),    f"{vat_data['input']:,.2f} SAR",  C["info"]),
            (t("vat.net_payable"),  f"{vat_data['net']:,.2f} SAR",    C["warning"]),
        ]

        for label, val, color in rows:
            row = tk.Frame(card, bg=C["card_bg"])
            row.pack(fill="x", padx=16, pady=6)

            tk.Label(row, text=label, font=("Segoe UI", 9),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left")
            tk.Label(row, text=val, font=("Segoe UI", 11, "bold"),
                     bg=C["card_bg"], fg=color).pack(side="right")

            tk.Frame(card, bg=C["border"], height=1).pack(fill="x", padx=16)

        # Phase badges
        phase_frame = tk.Frame(card, bg=C["card_bg"])
        phase_frame.pack(fill="x", padx=16, pady=14)
        for phase, status in [("Phase 1", "✅ Active"), ("Phase 2", "⏳ Ready")]:
            p = tk.Frame(phase_frame, bg=C["primary_light"], padx=8, pady=4)
            p.pack(side="left", padx=(0, 8))
            tk.Label(p, text=f"{phase}  {status}", font=("Segoe UI", 8),
                     bg=C["primary_light"], fg=C["primary"]).pack()

    # ── Top Customers ─────────────────────────────────────────
    def _top_customers(self, parent, pad_x, C):
        card = tk.Frame(parent, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="x", padx=pad_x, pady=(0, 24))

        h = tk.Frame(card, bg=C["card_bg"])
        h.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(h, text=f"🏆  {t('dashboard.top_customers')}",
                 font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")

        customers = self._get_top_customers()

        for i, cust in enumerate(customers[:5]):
            row = tk.Frame(card, bg=C["card_bg"])
            row.pack(fill="x", padx=16, pady=4)

            # Rank badge
            badge_colors = ["#FFD700", "#C0C0C0", "#CD7F32", C["border"], C["border"]]
            badge = tk.Frame(row, bg=badge_colors[i], width=28, height=28)
            badge.pack(side="left")
            badge.pack_propagate(False)
            tk.Label(badge, text=str(i+1), font=("Segoe UI", 9, "bold"),
                     bg=badge_colors[i], fg="white").pack(expand=True)

            tk.Label(row, text=f"  {cust.get('customer_name_en', '')}",
                     font=("Segoe UI", 10), bg=C["card_bg"],
                     fg=C["text_primary"]).pack(side="left")

            # Progress-like amount bar
            amount = cust.get("total_invoiced", 0)
            tk.Label(row, text=f"{amount:,.2f} SAR",
                     font=("Segoe UI", 10, "bold"),
                     bg=C["card_bg"], fg=C["primary"]).pack(side="right")

        if not customers:
            tk.Label(card, text=t("common.no_data"),
                     font=("Segoe UI", 10),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(pady=20)

        tk.Frame(card, bg=C["card_bg"], height=10).pack()

    # ── Data Fetchers ─────────────────────────────────────────
    def _get_kpi_data(self) -> list:
        C = cfg.theme()
        try:
            today = date.today()
            month_start = today.replace(day=1)

            sales = db.fetchone(
                "SELECT ISNULL(SUM(total_amount),0) AS total, COUNT(*) AS cnt "
                "FROM sales_invoices WHERE invoice_status='confirmed' "
                "AND invoice_date >= ?", (month_start,)) or {}

            vat = db.fetchone(
                "SELECT ISNULL(SUM(vat_amount),0) AS total "
                "FROM sales_invoices WHERE invoice_status='confirmed' "
                "AND invoice_date >= ?", (month_start,)) or {}

            outstanding = db.fetchone(
                "SELECT ISNULL(SUM(total_amount - paid_amount),0) AS total "
                "FROM sales_invoices WHERE invoice_status='confirmed' "
                "AND payment_status != 'paid'") or {}

            today_inv = db.fetchone(
                "SELECT COUNT(*) AS cnt FROM sales_invoices WHERE invoice_date = ?",
                (today,)) or {}

        except Exception:
            sales = {"total": 0, "cnt": 0}
            vat = {"total": 0}
            outstanding = {"total": 0}
            today_inv = {"cnt": 0}

        return [
            {
                "title": t("dashboard.total_sales"),
                "value": f"{sales.get('total', 0):,.2f}",
                "icon": "💰",
                "color": C["success"],
                "subtitle": f"{t('dashboard.this_month')}  •  {sales.get('cnt', 0)} invoices"
            },
            {
                "title": t("dashboard.total_vat"),
                "value": f"{vat.get('total', 0):,.2f}",
                "icon": "📋",
                "color": C["info"],
                "subtitle": "VAT 15% collected"
            },
            {
                "title": t("dashboard.outstanding"),
                "value": f"{outstanding.get('total', 0):,.2f}",
                "icon": "⏳",
                "color": C["warning"],
                "subtitle": "Unpaid invoices"
            },
            {
                "title": t("dashboard.invoices_today"),
                "value": str(today_inv.get("cnt", 0)),
                "icon": "🧾",
                "color": C["primary"],
                "subtitle": date.today().strftime("%d %B %Y")
            },
        ]

    def _get_recent_invoices(self) -> list:
        try:
            return db.fetchall(
                "SELECT TOP 10 invoice_number, customer_name_en, "
                "total_amount, invoice_status, invoice_date "
                "FROM sales_invoices ORDER BY created_at DESC"
            )
        except Exception:
            return []

    def _get_vat_summary(self) -> dict:
        try:
            today = date.today()
            month_start = today.replace(day=1)
            output = db.execute_scalar(
                "SELECT ISNULL(SUM(vat_amount),0) FROM sales_invoices "
                "WHERE invoice_status='confirmed' AND invoice_date >= ?",
                (month_start,)) or 0
            inp = db.execute_scalar(
                "SELECT ISNULL(SUM(vat_amount),0) FROM purchase_invoices "
                "WHERE invoice_status='confirmed' AND invoice_date >= ?",
                (month_start,)) or 0
            return {"output": float(output), "input": float(inp),
                    "net": float(output) - float(inp)}
        except Exception:
            return {"output": 0, "input": 0, "net": 0}

    def _get_top_customers(self) -> list:
        try:
            return db.fetchall(
                "SELECT TOP 5 customer_name_en, "
                "SUM(total_amount) AS total_invoiced "
                "FROM sales_invoices WHERE invoice_status='confirmed' "
                "GROUP BY customer_name_en ORDER BY total_invoiced DESC"
            )
        except Exception:
            return []
