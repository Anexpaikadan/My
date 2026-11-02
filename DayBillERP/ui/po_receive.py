# ============================================================
# DayBill ERP - 📦 Receive goods against a Purchase Order (v6.4)
# ------------------------------------------------------------
# Scan every item that came (barcode scanner or typed code; a Box
# barcode counts a whole box). The list shows ordered / received /
# difference: ✔ OK · ⚠ short · ✖ missing · ➕ more · ★ not on the order.
#   ✔ Make Purchase Invoice  → the invoice with what REALLY came (order
#                              prices), the order is marked received
#   🟢 Tell supplier          → WhatsApp: what is missing / short
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from config import settings as cfg
from ui import close_guard

STATUS = {"ok": "✔ OK", "short": "⚠ Short", "missing": "✖ Missing", "over": "➕ More",
          "extra": "★ Not on order"}


def _q(v):
    try:
        v = float(v)
        return ("%.3f" % v).rstrip("0").rstrip(".") if v != int(v) else "%d" % int(v)
    except Exception:
        return str(v)


class ReceiveDialog:
    def __init__(self, parent, po_id, on_done=None):
        from modules import supplier_orders as SO
        self.SO = SO
        self.rec = SO.Receiving(po_id)
        self.parent, self.on_done = parent, on_done
        C = self.C = cfg.theme()
        w = self.win = tk.Toplevel(parent)
        h = self.rec.head
        w.title("Receive %s" % (h.get("po_number") or ""))
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
            w.geometry("880x600")
        except Exception:
            pass
        close_guard.bind_escape(w)          # Esc closes (like ✕)
        top = tk.Frame(w, bg=C["card_bg"]); top.pack(fill="x")
        tk.Label(top, text="📦  Receive goods — %s" % (h.get("po_number") or ""),
                 font=("Segoe UI", 13, "bold"), bg=C["card_bg"], fg=C["text_primary"]).pack(
                     anchor="w", padx=14, pady=(10, 0))
        tk.Label(top, text="%s  ·  ordered %s  ·  scan every item that came (a Box barcode = one box)"
                 % (h.get("supplier_name_en") or "", str(h.get("po_date") or "")[:10]),
                 font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=14,
                                                                                      pady=(0, 10))
        sb = tk.Frame(w, bg=C["content_bg"]); sb.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(sb, text="Scan / code", font=("Segoe UI", 10), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.code = tk.StringVar()
        self.entry = e = tk.Entry(sb, textvariable=self.code, font=("Segoe UI", 12), width=26,
                                  relief="solid", bd=1)
        e.pack(side="left", padx=8, ipady=4)
        e.bind("<Return>", lambda ev: self.scan())
        self.qty = tk.StringVar(value="1")
        tk.Label(sb, text="×", font=("Segoe UI", 11), bg=C["content_bg"]).pack(side="left")
        tk.Entry(sb, textvariable=self.qty, width=5, font=("Segoe UI", 11), relief="solid", bd=1,
                 justify="center").pack(side="left", padx=6, ipady=3)
        tk.Button(sb, text="Add", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=12, pady=4, command=self.scan).pack(side="left")
        tk.Button(sb, text="All came as ordered", font=("Segoe UI", 9), bg=C["card_bg"],
                  relief="flat", padx=10, pady=4, highlightthickness=1,
                  highlightbackground=C["border"], command=self.all_came).pack(side="right")
        self.last = tk.StringVar(value="Scan the first item.")
        self.last_lbl = tk.Label(w, textvariable=self.last, font=("Segoe UI", 10, "bold"),
                                 bg=C["content_bg"], fg=C["primary"], anchor="w")
        self.last_lbl.pack(fill="x", padx=14)
        mid = tk.Frame(w, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        mid.pack(fill="both", expand=True, padx=12, pady=6)
        cols = [("name", "Item", 280, "w"), ("unit", "Order unit", 90, "center"),
                ("ordered", "Ordered", 90, "e"), ("received", "Received", 90, "e"),
                ("diff", "Difference", 90, "e"), ("status", "Status", 130, "w")]
        self.tv = ttk.Treeview(mid, columns=[c[0] for c in cols], show="headings")
        for k, t, wd, a in cols:
            self.tv.heading(k, text=t)
            self.tv.column(k, width=wd, anchor=a)
        vs = ttk.Scrollbar(mid, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tv.pack(fill="both", expand=True)
        for tag, col in (("ok", C["success"]), ("short", C["warning"]), ("missing", C["danger"]),
                         ("over", C["primary"]), ("extra", "#7C3AED")):
            self.tv.tag_configure(tag, foreground=col)
        self.tv.bind("<Double-1>", self._edit)
        self.sum = tk.StringVar()
        bot = tk.Frame(w, bg=C["content_bg"]); bot.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(bot, textvariable=self.sum, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        tk.Button(bot, text="Close", font=("Segoe UI", 9), relief="flat", bg=C["card_bg"], padx=12,
                  pady=6, highlightthickness=1, highlightbackground=C["border"],
                  command=self.win.destroy).pack(side="right")
        tk.Button(bot, text="✔  Make Purchase Invoice", font=("Segoe UI", 10, "bold"),
                  bg=C["success"], fg="white", relief="flat", padx=14, pady=6,
                  command=self.make_invoice).pack(side="right", padx=6)
        tk.Button(bot, text="🟢  Tell supplier what is missing", font=("Segoe UI", 9),
                  relief="flat", bg=C["card_bg"], padx=12, pady=6, highlightthickness=1,
                  highlightbackground=C["border"], command=self.tell_supplier).pack(side="right")
        self.refresh()
        e.focus_set()

    # ── actions ───────────────────────────────────────────────
    def scan(self, code=None):
        code = (code or self.code.get()).strip()
        if not code:
            return
        try:
            q = float(self.qty.get() or 1)
        except ValueError:
            q = 1.0
        try:
            hit = self.rec.scan(code, q)
        except ValueError as e:
            self.last.set("✖  " + str(e))
            self.last_lbl.configure(fg=self.C["danger"])
            self.win.bell()
            self.code.set("")
            return
        self.code.set(""); self.qty.set("1")
        txt = "%s  +%s pcs  →  %s of %s" % (hit["name"], _q(hit["base_added"]), _q(hit["received"]),
                                             _q(hit["ordered"]))
        if not hit["on_order"]:
            txt = "★ NOT ON THE ORDER: " + txt
        self.last.set(txt)
        self.last_lbl.configure(fg=self.C["primary"] if hit["on_order"] else "#7C3AED")
        self.refresh()
        return hit

    def all_came(self):
        self.rec.receive_all()
        self.last.set("All items set as ordered — change any that differ (double-click).")
        self.refresh()

    def _edit(self, _e=None):
        sel = self.tv.selection()
        if not sel:
            return
        pid = int(sel[0])
        r = next((x for x in self.rec.compare() if x["product_id"] == pid), None)
        if not r:
            return
        v = simpledialog.askfloat("Received", "How many PIECES of %s came?" % r["name"],
                                  initialvalue=r["received"], minvalue=0, parent=self.win)
        if v is not None:
            self.rec.set_received(pid, v)
            self.refresh()

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        for r in self.rec.compare():
            f = r["factor"] or 1.0

            def show(x):
                if f != 1 and abs(x / f - round(x / f)) < 1e-6:
                    return "%s %s" % (_q(x / f), r["unit"])
                return "%s pcs" % _q(x)
            self.tv.insert("", "end", iid=str(r["product_id"]), values=(
                r["name"], r["unit"], show(r["ordered"]), show(r["received"]),
                ("+" if r["diff"] > 0 else "") + _q(r["diff"]) if r["diff"] else "0",
                STATUS[r["status"]]), tags=(r["status"],))
        s = self.rec.summary()
        self.sum.set("✔ %d OK   ⚠ %d short   ✖ %d missing   ➕ %d more   ★ %d not on order"
                     % (s["ok"], s["short"], s["missing"], s["over"], s["extra"]))

    def tell_supplier(self):
        text = self.rec.missing_text()
        if not text:
            messagebox.showinfo("Supplier", "Nothing is missing.", parent=self.win)
            return
        try:
            from modules import whatsapp as wa
            from config.database import db
            sup = db.fetchone("SELECT phone FROM suppliers WHERE supplier_id=?",
                              (self.rec.head.get("supplier_id"),)) or {}
            phone = wa.normalize_phone(sup.get("phone"))
            # always the WhatsApp app here (free, and a typed message reaches the
            # supplier even when the Cloud API would need an approved template)
            wa.open_chat(phone, text)
            wa.log("po_missing", self.rec.po_id, phone, True, "opened chat")
            return text
        except Exception as e:
            try:
                self.win.clipboard_clear(); self.win.clipboard_append(text)
            except Exception:
                pass
            messagebox.showinfo("Supplier", "WhatsApp could not open (%s).\n\nThe message is "
                                "copied — paste it to the supplier:\n\n%s" % (str(e)[:80], text),
                                parent=self.win)
            return text

    def make_invoice(self):
        lines = self.rec.invoice_lines()
        if not lines:
            messagebox.showinfo("Receive", "Nothing received yet — scan the items first.",
                                parent=self.win)
            return None
        from modules import permissions as _pm
        if not _pm.allowed("purchase", "add"):
            return None
        rec = self.rec
        holder = {}

        def done():
            form = holder.get("form")
            pid = getattr(form, "purchase_id", None)
            if pid:
                rec.mark_received(pid)
                if self.on_done:
                    try:
                        self.on_done()
                    except Exception:
                        pass
        from ui.purchases import PurchaseForm
        form = PurchaseForm(self.parent, None, done)
        holder["form"] = form
        try:
            s = next((x for x in form.suppliers if x["supplier_id"] == rec.head.get("supplier_id")), None)
            if s:
                form.sup_cb.set(f"{s['supplier_code']} — {s['supplier_name_en']}")
            form.grid.set_lines(lines)
            form._on_change()
            try:
                form.hdr["notes"].set(rec.note())
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        return form
