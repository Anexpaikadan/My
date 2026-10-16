# ============================================================
# DayBill ERP - Batches & Expiry page (Inventory)  v6.0
# ------------------------------------------------------------
# Every batch still in stock, the soonest expiry first: red = expired,
# orange = expires within the alert days (Settings: expiry_alert_days).
# "Write off" takes expired / damaged batches out of stock and posts
# the loss (Dr Stock Adjustment | Cr Inventory).
# ============================================================
import tkinter as tk
from tkinter import messagebox

from modules import batches as B
from ui import v6_kit as K


class ExpiryView:
    def __init__(self, parent):
        self.page = K.Page(parent, "⏰  Batches & Expiry",
                           "Goods with an expiry date, the soonest first. Sales take the batch that "
                           "expires first. Tick 'Track expiry dates' on a product and type the dates "
                           "in Purchase ▸ ⏰ Expiry dates.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        if not B.ready():
            self.page.say("⚠ Needs the v6.0 database update — Updates ▸ Apply All Updates.", ok=False)
            return
        top = tk.Frame(self.page.body, bg=C["content_bg"]); top.pack(fill="x")
        self.show_v = tk.StringVar(value="Expiring within 30 days")
        try:
            from config import settings as cfg
            self.days = int(cfg.get("expiry_alert_days", 30) or 30)
        except Exception:
            self.days = 30
        opts = ["Expired", "Expiring within %d days" % self.days, "Expiring within 90 days", "All batches"]
        self.show_v.set(opts[1])
        f = tk.Frame(top, bg=C["content_bg"]); f.pack(side="left")
        K.combo(f, {"card_bg": C["content_bg"], "text_secondary": C["text_secondary"]}, "Show",
                self.show_v, opts, 24).bind("<<ComboboxSelected>>", lambda e: self.load())
        self.sum_v = tk.StringVar()
        tk.Label(top, textvariable=self.sum_v, font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left", padx=16)
        bar = tk.Frame(top, bg=C["content_bg"]); bar.pack(side="right")
        K.button(bar, C, "🗑 Write off selected", self._write_off, danger=True)
        K.button(bar, C, "↻ Refresh", self.load)
        self.tree = K.tree(self.page.body, [
            ("code", "Code", 90, "w"), ("name", "Product", 240, "w"), ("batch", "Batch", 100, "w"),
            ("exp", "Expiry", 95, "center"), ("days", "Days left", 80, "e"),
            ("qty", "Quantity", 90, "e"), ("branch", "Branch", 120, "w"), ("rec", "Received", 95, "center")],
            height=20)
        self.tree.configure(selectmode="extended")
        self.tree.tag_configure("gone", background="#FEE2E2")
        self.tree.tag_configure("soon", background="#FFF7ED")
        self.load()

    def load(self):
        mode = self.show_v.get()
        if mode == "Expired":
            rows = B.expired()
        elif "90" in mode:
            rows = B.near_expiry(90)
        elif mode == "All batches":
            rows = B.list_batches()
        else:
            rows = B.near_expiry(self.days)
        try:
            from modules import stock_branch as SB
            names = {b["branch_id"]: b.get("name_en") for b in SB.branches()}
            main = SB.main_branch_id()
        except Exception:
            names, main = {}, None
        self.tree.delete(*self.tree.get_children())
        gone = soon = 0
        for r in rows:
            d = r.get("days_left")
            tag = "gone" if d is not None and d < 0 else ("soon" if d is not None and d <= self.days else "")
            gone += tag == "gone"
            soon += tag == "soon"
            self.tree.insert("", "end", iid=str(r["batch_id"]), tags=(tag,), values=(
                r.get("product_code"), r.get("product_name_en"), r.get("batch_no") or "—",
                str(r.get("expiry_date") or "")[:10] or "—",
                ("EXPIRED %d d" % -d) if (d is not None and d < 0) else ("" if d is None else d),
                "%g" % float(r.get("qty_base") or 0),
                names.get(r.get("branch_id") or main, ""), str(r.get("received_date") or "")[:10]))
        self.sum_v.set("%d batch(es)  ·  %d expired  ·  %d expiring soon" % (len(rows), gone, soon))

    def _write_off(self):
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "add", parent=self.frame):
            return
        sel = [int(x) for x in self.tree.selection()]
        if not sel:
            self.page.say("Select the batches to write off (Ctrl / Shift + click for several).", ok=False)
            return
        if not messagebox.askyesno("Write off", "Take %d batch(es) out of stock as a loss?" % len(sel),
                                   parent=self.frame):
            return
        try:
            n, q = B.write_off(sel)
        except Exception as e:
            self.page.say("Nothing written off: %s" % str(e)[:150], ok=False)
            return
        self.load()
        self.page.say("✓ %d batch(es) written off (%g units) — the loss is posted." % (n, q))
