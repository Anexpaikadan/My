# ============================================================
# DayBill ERP - 🍳 Print Stations screen (v7.5)
# ------------------------------------------------------------
# Settings ▸ Print Stations: create Kitchen 1 / Kitchen 2, Warehouse 1,
# Tailor Ahmed … each with its printer, template (80 / 58 mm roll, A5,
# A4) and copies; which categories go to which station; test print;
# print a sale / order again; what was printed lately.
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from config import settings as cfg
from config.database import db
from modules import print_stations as PS
from modules import permissions as perm

NONE = "— not printed —"
AUTO = "Any station without categories"


class PrintStationsView:
    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(top, text="🍳  Print Stations", font=("Segoe UI", 16, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        for kind, name, icon in reversed(PS.KINDS):
            tk.Button(top, text="＋ %s %s" % (icon, name), font=("Segoe UI", 9, "bold"),
                      bg=C["primary"] if kind == "kitchen" else C["card_bg"],
                      fg="white" if kind == "kitchen" else C["text_primary"], relief="flat", padx=10, pady=5,
                      cursor="hand2", command=lambda k=kind: self.add(k)).pack(side="right", padx=(6, 0))
        tk.Label(self.frame, text="Each station prints the items that belong to it when a Sales Invoice, POS bill or "
                                  "Sales Order is saved — kitchens, warehouse picking, tailors. Restaurant TABLE orders "
                                  "print their kitchen tickets from Restaurant ▸ Setup ▸ Kitchen stations.",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"], wraplength=1100,
                 justify="left").pack(fill="x", padx=16)
        body = tk.PanedWindow(self.frame, orient="horizontal", bg=C["content_bg"], sashwidth=6)
        body.pack(fill="both", expand=True, padx=12, pady=8)
        left = tk.Frame(body, bg=C["card_bg"]); right = tk.Frame(body, bg=C["card_bg"])
        body.add(left, width=720); body.add(right)
        cols = ("name", "kind", "printer", "template", "copies", "docs", "who", "on")
        self.tv = ttk.Treeview(left, columns=cols, show="headings", height=10)
        for c, t, w in (("name", "Station", 150), ("kind", "Kind", 80), ("printer", "Printer", 170),
                        ("template", "Template", 90), ("copies", "Copies", 50), ("docs", "Prints for", 130),
                        ("who", "Employee", 110), ("on", "On", 40)):
            self.tv.heading(c, text=t); self.tv.column(c, width=w, anchor="w")
        self.tv.pack(fill="both", expand=True, padx=6, pady=6)
        self.tv.bind("<Double-1>", lambda e: self.edit())
        bb = tk.Frame(left, bg=C["card_bg"]); bb.pack(fill="x", padx=6, pady=(0, 6))
        for txt, cmd in (("✎ Edit", self.edit), ("🗑 Delete", self.delete), ("🖨 Test print", self.test),
                         ("↻ Print a sale / order again…", self.reprint)):
            tk.Button(bb, text=txt, relief="flat", bg=C["content_bg"], padx=10, pady=4, cursor="hand2",
                      command=cmd).pack(side="left", padx=(0, 6))
        tk.Label(left, text="Recently printed", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=8)
        self.logv = ttk.Treeview(left, columns=("time", "station", "doc", "lines", "info"), show="headings", height=6)
        for c, t, w in (("time", "Time", 110), ("station", "Station", 120), ("doc", "Document", 140),
                        ("lines", "Items", 50), ("info", "Result", 260)):
            self.logv.heading(c, text=t); self.logv.column(c, width=w, anchor="w")
        self.logv.pack(fill="both", expand=False, padx=6, pady=(0, 6))
        tk.Label(right, text="Which categories go to which station", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", padx=8, pady=(8, 2))
        tk.Label(right, text="Double-click a category to choose its station. A station with no categories "
                             "takes every item no other station takes (one Warehouse / Kitchen shops).",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"], wraplength=380,
                 justify="left").pack(anchor="w", padx=8)
        self.cv = ttk.Treeview(right, columns=("cat", "station"), show="headings", height=18)
        self.cv.heading("cat", text="Category"); self.cv.column("cat", width=200)
        self.cv.heading("station", text="Station"); self.cv.column("station", width=180)
        self.cv.pack(fill="both", expand=True, padx=6, pady=6)
        self.cv.bind("<Double-1>", lambda e: self.pick_station())
        self.msg = tk.StringVar()
        tk.Label(self.frame, textvariable=self.msg, bg=C["content_bg"], fg="#047857",
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=16, pady=(0, 6))
        self.load()

    # ── data ──────────────────────────────────────────────────
    def load(self):
        if not PS.ready():
            self.msg.set("Run the database update first (Print Stations tables missing).")
            return
        emps = {}
        try:
            emps = {r["employee_id"]: r["full_name_en"] for r in (db.fetchall(
                "SELECT employee_id, full_name_en FROM employees") or [])}
        except Exception:
            pass
        self.tv.delete(*self.tv.get_children())
        kinds = {k: n for k, n, _i in PS.KINDS}
        tpls = dict(PS.TEMPLATES)
        for s in PS.stations(active_only=False):
            docs = [n for f, n in (("on_sales", "Sales"), ("on_pos", "POS"), ("on_orders", "Orders")) if s.get(f)]
            self.tv.insert("", "end", iid=str(s["station_id"]), values=(
                s["name"], kinds.get(s["kind"], s["kind"]), s.get("printer_name") or "(PDF only)",
                tpls.get(s["template"], s["template"]), s.get("copies") or 1, ", ".join(docs),
                emps.get(s.get("employee_id"), ""), "✔" if s.get("is_active") else "—"))
        names = {s["station_id"]: s["name"] for s in PS.stations(active_only=False)}
        cmap = PS.category_map()
        self.cv.delete(*self.cv.get_children())
        try:
            cats = db.fetchall("SELECT category_id, category_name_en FROM product_categories "
                               "WHERE ISNULL(is_active,1)=1 ORDER BY category_name_en") or []
        except Exception:
            cats = []
        for c in cats:
            sid = cmap.get(c["category_id"])
            self.cv.insert("", "end", iid=str(c["category_id"]), values=(
                c["category_name_en"], names.get(sid, AUTO)))
        self.logv.delete(*self.logv.get_children())
        for r in PS.log(30):
            self.logv.insert("", "end", values=(str(r.get("created_at"))[:16], r.get("name") or "",
                                                "%s %s" % (r.get("doc_kind"), r.get("doc_number") or ""),
                                                r.get("lines"), r.get("info") or ""))

    def _sel(self):
        s = self.tv.selection()
        return int(s[0]) if s else None

    def _allowed(self):
        return perm.allowed("company_settings", "settings", parent=self.frame)

    # ── actions ───────────────────────────────────────────────
    def add(self, kind):
        if not self._allowed():
            return None
        return StationForm(self.frame, {"kind": kind, "name": PS.next_name(kind)}, on_save=self.load)

    def edit(self):
        sid = self._sel()
        if not sid:
            messagebox.showinfo("Print Stations", "Pick a station first.", parent=self.frame)
            return None
        if not self._allowed():
            return None
        return StationForm(self.frame, PS.station(sid), on_save=self.load)

    def delete(self):
        sid = self._sel()
        if not sid or not self._allowed():
            return
        st = PS.station(sid)
        if messagebox.askyesno("Print Stations", "Delete station '%s'? Its categories go back to 'any station'."
                               % st["name"], parent=self.frame):
            PS.delete_station(sid)
            self.load()

    def pick_station(self):
        s = self.cv.selection()
        if not s or not self._allowed():
            return
        cid = int(s[0])
        sts = PS.stations(active_only=False)
        win = tk.Toplevel(self.frame); win.title("Station for %s" % self.cv.set(s[0], "cat"))
        win.transient(self.frame.winfo_toplevel())
        var = tk.StringVar(value=self.cv.set(s[0], "station"))
        ttk.Combobox(win, textvariable=var, state="readonly", width=30,
                     values=[AUTO] + [x["name"] for x in sts]).pack(padx=14, pady=12)

        def ok():
            v = var.get()
            PS.set_category(cid, next((x["station_id"] for x in sts if x["name"] == v), None))
            win.destroy(); self.load()
        tk.Button(win, text="✔ Save", command=ok, bg=self.C["primary"], fg="white", relief="flat",
                  padx=14).pack(pady=(0, 12))
        self._picker = (win, var, ok)
        return win

    def test(self):
        sid = self._sel()
        if not sid:
            messagebox.showinfo("Print Stations", "Pick a station first.", parent=self.frame)
            return None
        st = PS.station(sid)
        head = {"number": "TEST-001", "d": __import__("datetime").date.today().isoformat(),
                "party": "Test customer", "notes": "Test print"}
        lines = [{"product_id": 1, "product_name_en": "Sample item", "product_name_ar": "صنف تجريبي",
                  "quantity": 2, "unit_of_measure_en": "PCs", "line_total": 20},
                 {"product_id": 2, "product_name_en": "Another item", "quantity": 1,
                  "unit_of_measure_en": "Box", "line_total": 35, "kitchen_note": "no onion"}]
        pdf = PS.slip_pdf(st, "sales", head, lines)
        from modules import printer_service as ps
        if st.get("printer_name"):
            ok = ps.print_pdf(pdf, st["printer_name"], copies=1)
            self.msg.set(("🖨 Test sent to %s" % st["printer_name"]) if ok else ("❌ " + str(ps.last_error)))
        else:
            ps.open_file(pdf)
            self.msg.set("📄 No printer set for %s — the test slip opened as a PDF." % st["name"])
        return pdf

    def reprint(self):
        num = simpledialog.askstring("Print again", "Invoice / POS bill / sales order number:", parent=self.frame)
        if not num:
            return None
        num = num.strip()
        r = db.fetchone("SELECT invoice_id AS id, ISNULL(sale_channel,'') AS ch FROM sales_invoices "
                        "WHERE invoice_number=?", (num,))
        kind = None
        if r:
            kind = "pos" if str(r["ch"]).upper() == "POS" else "sales"
        else:
            try:
                r = db.fetchone("SELECT so_id AS id FROM sales_orders WHERE so_number=?", (num,))
            except Exception:
                r = None
            kind = "sales_order" if r else None
        if not r:
            messagebox.showinfo("Print again", "No sale or order '%s'." % num, parent=self.frame)
            return None
        res = PS.send(kind, r["id"], reprint=True, open_if_no_printer=True)
        self.msg.set(PS.summary(res) or "No station takes these items.")
        self.load()
        return res


class StationForm:
    def __init__(self, parent, data, on_save=None):
        C = self.C = cfg.theme()
        self.data = dict(data or {})
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Print station — %s" % (self.data.get("name") or "new"))
        self.win.configure(bg=C["content_bg"])
        self.win.geometry("460x560")
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        f = tk.Frame(self.win, bg=C["content_bg"]); f.pack(fill="both", expand=True, padx=16, pady=12)

        def lab(t):
            tk.Label(f, text=t, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                     fg=C["text_secondary"], anchor="w").pack(fill="x", pady=(8, 2))
        lab("Station name")
        self.name = tk.StringVar(value=self.data.get("name") or "")
        tk.Entry(f, textvariable=self.name, font=("Segoe UI", 11), relief="solid", bd=1).pack(fill="x")
        lab("Kind")
        kinds = {k: "%s %s" % (i, n) for k, n, i in PS.KINDS}
        self.kind = tk.StringVar(value=kinds.get(self.data.get("kind"), kinds["other"]))
        self._kinds = {v: k for k, v in kinds.items()}
        ttk.Combobox(f, textvariable=self.kind, state="readonly", values=list(kinds.values())).pack(fill="x")
        lab("Printer (empty = the slip opens as a PDF)")
        try:
            from modules import printer_service as ps
            printers = ps.list_printers()
        except Exception:
            printers = []
        self.printer = tk.StringVar(value=self.data.get("printer_name") or "")
        ttk.Combobox(f, textvariable=self.printer, values=[""] + printers).pack(fill="x")
        row = tk.Frame(f, bg=C["content_bg"]); row.pack(fill="x")
        lt = tk.Frame(row, bg=C["content_bg"]); lt.pack(side="left", fill="x", expand=True)
        tk.Label(lt, text="Template", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(8, 2))
        tpls = dict(PS.TEMPLATES)
        self.tpl = tk.StringVar(value=tpls.get(self.data.get("template"), tpls["thermal80"]))
        self._tpls = {v: k for k, v in tpls.items()}
        ttk.Combobox(lt, textvariable=self.tpl, state="readonly", values=list(tpls.values()), width=16).pack(anchor="w")
        rt = tk.Frame(row, bg=C["content_bg"]); rt.pack(side="left", padx=(12, 0))
        tk.Label(rt, text="Copies", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(8, 2))
        self.copies = tk.StringVar(value=str(self.data.get("copies") or 1))
        ttk.Spinbox(rt, from_=1, to=5, textvariable=self.copies, width=5).pack(anchor="w")
        lab("Employee (tailor / picker this station belongs to)")
        try:
            self.emps = {r["full_name_en"]: r["employee_id"] for r in (db.fetchall(
                "SELECT employee_id, full_name_en FROM employees WHERE ISNULL(is_active,1)=1 ORDER BY full_name_en")
                or [])}
        except Exception:
            self.emps = {}
        cur = next((n for n, i in self.emps.items() if i == self.data.get("employee_id")), "")
        self.emp = tk.StringVar(value=cur)
        ttk.Combobox(f, textvariable=self.emp, state="readonly", values=[""] + list(self.emps)).pack(fill="x")
        lab("Prints for")
        self.flags = {}
        for key, txt in (("on_sales", "Sales Invoice"), ("on_pos", "POS bill"), ("on_orders", "Sales Order"),
                         ("show_prices", "Show prices on the slip"), ("is_active", "Station is on")):
            v = tk.BooleanVar(value=bool(self.data.get(key, key != "show_prices")))
            self.flags[key] = v
            tk.Checkbutton(f, text=txt, variable=v, bg=C["content_bg"], anchor="w").pack(fill="x")
        self.msg = tk.StringVar()
        tk.Label(self.win, textvariable=self.msg, bg=C["content_bg"], fg=C["danger"]).pack(fill="x", padx=16)
        bb = tk.Frame(self.win, bg=C["content_bg"]); bb.pack(fill="x", padx=16, pady=10)
        tk.Button(bb, text="Cancel", relief="flat", padx=12, command=self.win.destroy).pack(side="right")
        tk.Button(bb, text="💾 Save", relief="flat", padx=14, bg=C["primary"], fg="white",
                  font=("Segoe UI", 9, "bold"), command=self.save).pack(side="right", padx=6)

    def save(self):
        d = {"station_id": self.data.get("station_id"), "name": self.name.get(),
             "kind": self._kinds.get(self.kind.get(), "other"), "printer_name": self.printer.get(),
             "template": self._tpls.get(self.tpl.get(), "thermal80"), "copies": self.copies.get(),
             "employee_id": self.emps.get(self.emp.get())}
        d.update({k: v.get() for k, v in self.flags.items()})
        try:
            sid = PS.save_station(d)
        except ValueError as e:
            self.msg.set(str(e))
            return None
        if self.on_save:
            self.on_save()
        self.win.destroy()
        return sid
