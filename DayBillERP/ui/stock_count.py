# ============================================================
# DayBill ERP - 🧮 Stock Count (cycle counts, phone + approval)  v6.4
# ------------------------------------------------------------
#   📋 Today's list   what to count today (A weekly, B monthly, C every
#                     3 months — Settings ▸ Inventory). Print it, or type
#                     the counted quantities here and send them.
#   ✅ To approve      counts from phones / this PC: system qty · counted ·
#                     difference · value. Tick the right lines → Approve
#                     (stock changes); the rest go back to recount.
#   📜 History         every counted line, accuracy %, loss / gain.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from config import settings as cfg


def _q(v):
    try:
        v = float(v)
        return ("%.3f" % v).rstrip("0").rstrip(".") if v != int(v) else "%d" % int(v)
    except Exception:
        return str(v or "")


def _m(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


class StockCountView:
    def __init__(self, parent):
        from modules import cycle_count as CC
        self.CC = CC
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(top, text="🧮  Stock Count", font=("Segoe UI", 16, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        ev = CC.every_days()
        tk.Label(top, text="A items every %d days · B every %d · C every %d   ·   phones: Stock Count ▸ 📋 "
                           "Today's list" % (ev["A"], ev["B"], ev["C"]),
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left", padx=12)
        tk.Button(top, text="🔄  Refresh", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=14, pady=5, cursor="hand2", command=self.refresh).pack(side="right")
        self.nb = nb = ttk.Notebook(self.frame)
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # 📋 today's list
        p1 = tk.Frame(nb, bg=C["content_bg"]); nb.add(p1, text="📋 Today's list")
        b1 = tk.Frame(p1, bg=C["content_bg"]); b1.pack(fill="x", pady=6)
        self.plan_info = tk.StringVar()
        tk.Label(b1, textvariable=self.plan_info, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=4)
        tk.Button(b1, text="📤  Send counts for approval", font=("Segoe UI", 9, "bold"), bg=C["success"],
                  fg="white", relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self.send_counts).pack(side="right", padx=4)
        tk.Button(b1, text="🖨  Count sheet (PDF)", font=("Segoe UI", 9), bg=C["card_bg"], relief="flat",
                  padx=12, pady=5, cursor="hand2", highlightthickness=1, highlightbackground=C["border"],
                  command=self.sheet_pdf).pack(side="right", padx=4)
        self.t_plan = self._tree(p1, [("cls", "Class", 55, "center"), ("code", "Code", 90, "w"),
                                      ("name", "Product", 260, "w"), ("last", "Last counted", 110, "center"),
                                      ("since", "Days", 60, "e"), ("stock", "In stock", 85, "e"),
                                      ("counted", "Counted ✎", 90, "e")])
        self.t_plan.bind("<Double-1>", self._type_count)
        self.t_plan.bind("<Return>", self._type_count)
        self.counts = {}

        # ✅ to approve
        p2 = tk.Frame(nb, bg=C["content_bg"]); nb.add(p2, text="✅ To approve")
        self.p2 = p2
        b2 = tk.Frame(p2, bg=C["content_bg"]); b2.pack(fill="x", pady=6)
        self.appr_info = tk.StringVar()
        tk.Label(b2, textvariable=self.appr_info, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=4)
        tk.Button(b2, text="✔  Approve ticked lines", font=("Segoe UI", 9, "bold"), bg=C["success"],
                  fg="white", relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self.approve).pack(side="right", padx=4)
        tk.Button(b2, text="✖  Reject whole count", font=("Segoe UI", 9), bg="#FEF2F2", fg=C["danger"],
                  relief="flat", padx=12, pady=5, cursor="hand2", command=self.reject).pack(side="right", padx=4)
        self.t_ap = self._tree(p2, [("tick", "✓", 34, "center"), ("name", "Product / count", 230, "w"),
                                    ("sys", "In system", 80, "e"), ("counted", "Counted", 80, "e"),
                                    ("diff", "Difference", 80, "e"), ("value", "Value SAR", 90, "e"),
                                    ("note", "", 150, "w")], tree=True)
        self.t_ap.bind("<Button-1>", self._toggle, add="+")
        self.t_ap.bind("<space>", self._toggle_key)
        self.ticks = {}

        # 📜 history
        p3 = tk.Frame(nb, bg=C["content_bg"]); nb.add(p3, text="📜 History")
        b3 = tk.Frame(p3, bg=C["content_bg"]); b3.pack(fill="x", pady=6)
        self.hist_info = tk.StringVar()
        tk.Label(b3, textvariable=self.hist_info, font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left", padx=4)
        self.t_hist = self._tree(p3, [("date", "Date", 90, "center"), ("name", "Product", 210, "w"),
                                      ("sys", "In system", 75, "e"), ("counted", "Counted", 75, "e"),
                                      ("diff", "Difference", 75, "e"), ("value", "Value SAR", 85, "e"),
                                      ("status", "Status", 80, "center"), ("src", "From", 80, "w")])
        self.refresh()

    def _tree(self, parent, cols, tree=False):
        C = self.C
        wrap = tk.Frame(parent, bg=C["card_bg"]); wrap.pack(fill="both", expand=True)
        tv = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="tree headings" if tree else "headings")
        if tree:
            tv.column("#0", width=22, stretch=False)
        for k, t_, w, a in cols:
            tv.heading(k, text=t_)
            tv.column(k, width=w, anchor=a)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); tv.pack(side="left", fill="both", expand=True)
        tv.tag_configure("A", foreground=C["danger"])
        tv.tag_configure("B", foreground=C["warning"])
        tv.tag_configure("doc", font=("Segoe UI", 9, "bold"), background=C.get("primary_light", "#EAF1FE"))
        tv.tag_configure("big", foreground=C["danger"])
        tv.tag_configure("loss", foreground=C["danger"])
        tv.tag_configure("gain", foreground=C["success"])
        return tv

    # ── data ──────────────────────────────────────────────────
    def refresh(self):
        CC = self.CC
        try:
            self._plan = CC.plan()
        except Exception as e:                      # never block the screen
            print("[DayBill] count plan:", e)
            self._plan = []
        tv = self.t_plan
        tv.delete(*tv.get_children())
        for r in self._plan:
            c = self.counts.get(r["product_id"])
            tv.insert("", "end", iid=str(r["product_id"]), values=(
                r["class"], r["code"], r["name"], r["last_counted"] or "never",
                "—" if r["days_since"] is None else r["days_since"], _q(r["stock"]),
                "" if c is None else _q(c)), tags=(r["class"],))
        self.plan_info.set("%d item(s) to count today. Double-click a line to type what you counted."
                           % len(self._plan) if self._plan else "✔ Nothing to count today.")
        try:
            self._pend = CC.pending()
        except Exception as e:
            print("[DayBill] counts waiting:", e)
            self._pend = []
        tv = self.t_ap
        tv.delete(*tv.get_children())
        self.ticks = {}
        n_lines = 0
        for d in self._pend:
            did = "d:%d" % d["doc_id"]
            tv.insert("", "end", iid=did, open=True, tags=("doc",), values=(
                "", "%s  ·  %s" % (d["title"].replace("Stock Count · ", ""), d["device"]), "", "",
                "%d line(s)" % len(d["lines"]), _m(d["diff_value"]), d["created_at"]))
            for ln in d["lines"]:
                lid = "l:%d:%d" % (d["doc_id"], ln["product_id"])
                self.ticks[lid] = True
                n_lines += 1
                tv.insert(did, "end", iid=lid, tags=("big",) if ln["big"] else (), values=(
                    "☑", ln["name"], _q(ln["system_qty"]), _q(ln["counted"]),
                    ("+" if ln["diff"] > 0 else "") + _q(ln["diff"]), _m(ln["value"]),
                    "⚠ big — recount?" if ln["big"] else ""))
        self.appr_info.set("%d count(s), %d line(s) waiting. Click ☑ to untick a line: untick = "
                           "recount." % (len(self._pend), n_lines) if self._pend else "Nothing waiting.")
        try:
            self.nb.tab(self.p2, text="✅ To approve (%d)" % len(self._pend))
        except Exception:
            pass
        try:
            h = CC.history()
        except Exception as e:
            print("[DayBill] count history:", e)
            h = {"rows": [], "lines": 0, "exact": 0, "accuracy": None, "loss": 0.0, "gain": 0.0}
        tv = self.t_hist
        tv.delete(*tv.get_children())
        for r in h["rows"][:500]:
            dv = float(r.get("diff_value") or 0)
            tv.insert("", "end", values=(str(r.get("count_date") or "")[:10], r.get("product_name_en") or "",
                                         _q(r.get("system_qty")), _q(r.get("counted_qty")),
                                         _q(r.get("diff_qty")), _m(dv), r.get("status") or "",
                                         r.get("source") or ""),
                      tags=("loss",) if dv < 0 else (("gain",) if dv > 0 else ()))
        self.hist_info.set("Last 90 days: %d line(s) counted · exact %s · loss %s SAR · gain %s SAR"
                           % (h["lines"], "—" if h["accuracy"] is None else "%.1f %%" % h["accuracy"],
                              _m(h["loss"]), _m(h["gain"])))

    # ── today's list ──────────────────────────────────────────
    def _type_count(self, _e=None):
        sel = self.t_plan.selection()
        if not sel:
            return
        pid = int(sel[0])
        r = next((x for x in self._plan if x["product_id"] == pid), None)
        v = simpledialog.askfloat("Counted", "How many PIECES of %s are there?" % (r or {}).get("name", ""),
                                  minvalue=0, parent=self.frame)
        if v is None:
            return
        self.counts[pid] = v
        vals = list(self.t_plan.item(sel[0], "values"))
        vals[-1] = _q(v)
        self.t_plan.item(sel[0], values=vals)
        nxt = self.t_plan.next(sel[0])
        if nxt:
            self.t_plan.selection_set(nxt); self.t_plan.focus(nxt); self.t_plan.see(nxt)

    def send_counts(self):
        # sending can change stock at once (when approval is off)
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "add", parent=self.frame):
            return None
        if not self.counts:
            messagebox.showinfo("Stock Count", "Type the counted quantities first (double-click a line).",
                                parent=self.frame)
            return None
        try:
            doc = self.CC.submit_desktop(self.counts)
        except Exception as e:
            messagebox.showerror("Stock Count", str(e)[:300], parent=self.frame)
            return None
        self.counts = {}
        self.refresh()
        if self.CC.needs_approval():
            self.nb.select(self.p2)
        return doc

    def sheet_pdf(self):
        try:
            from modules.doc_actions import export_tree_pdf
            export_tree_pdf(self.frame, self.t_plan, "Count_Sheet",
                            ["Class", "Code", "Product", "Last counted", "Days", "In stock", "Counted"],
                            title="Stock count — today's list")
        except Exception as e:
            messagebox.showerror("Count sheet", str(e)[:300], parent=self.frame)

    # ── approve ───────────────────────────────────────────────
    def _toggle(self, e):
        if self.t_ap.identify_column(e.x) != "#1":
            return
        row = self.t_ap.identify_row(e.y)
        if row:
            self._flip(row)
            return "break"

    def _toggle_key(self, _e=None):
        for row in self.t_ap.selection():
            self._flip(row)
        return "break"

    def _flip(self, row):
        if row in self.ticks:
            self.ticks[row] = not self.ticks[row]
            vals = list(self.t_ap.item(row, "values"))
            vals[0] = "☑" if self.ticks[row] else "☐"
            self.t_ap.item(row, values=vals)
        elif row.startswith("d:"):                     # the count's row: tick / untick all its lines
            kids = self.t_ap.get_children(row)
            on = not all(self.ticks.get(k) for k in kids)
            for k in kids:
                if self.ticks.get(k) != on:
                    self._flip(k)

    def _doc(self):
        sel = self.t_ap.selection() or self.t_ap.get_children()
        if not sel:
            return None
        row = sel[0]
        return int(row.split(":")[1])

    def approve(self, doc_id=None):
        # approve = the stock changes, so it needs the approve right
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "approve", parent=self.frame):
            return None
        doc_id = doc_id or self._doc()
        if not doc_id:
            messagebox.showinfo("Approve", "Nothing waiting.", parent=self.frame)
            return None
        pids = [int(k.split(":")[2]) for k, on in self.ticks.items()
                if on and k.startswith("l:%d:" % doc_id)]
        try:
            msg = self.CC.approve(doc_id, pids)
        except Exception as e:
            messagebox.showerror("Approve", str(e)[:300], parent=self.frame)
            return None
        self.refresh()
        try:
            from ui.ui_polish import toast
            toast(self.frame.winfo_toplevel(), "✔ " + msg)
        except Exception:
            pass
        return msg

    def reject(self, doc_id=None):
        from modules import permissions as _pm
        if not _pm.allowed("stock_adjustment", "approve", parent=self.frame):
            return None
        doc_id = doc_id or self._doc()
        if not doc_id:
            return None
        if not messagebox.askyesno("Reject", "Reject this whole count? Nothing changes; count again.",
                                   parent=self.frame):
            return None
        self.CC.reject(doc_id, "count again")
        self.refresh()
        return True
