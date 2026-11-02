# ============================================================
# DayBill ERP - Production screens (v7.0)
#   ProductionView        Production ▸ Production Entry: the list (date,
#                         status, find) — New / Open / Cancel / Delete /
#                         Print
#   ProductionForm        one production run: the product made and how
#                         many; the materials filled from its bill of
#                         materials × quantity, with the stock on hand and
#                         what is short (red); the quantity really used
#                         can be changed; labour, overhead and the cost of
#                         one unit. Save draft / Confirm / Cancel / Print.
#   ProductionReportView  Production ▸ Production Report: production
#                         register, material usage (planned vs used) and
#                         cost of one unit month by month
#                         (modules/production_reports.py)
# Data and posting: modules/production.py
# Keys (entry window): double-click / F2 changes the quantity used ·
#   Delete removes the line · Ctrl+S confirm · Ctrl+D save draft ·
#   Ctrl+P print · Esc close
# ============================================================

import os
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

from config import settings as cfg
from config.database import db
from modules import production as PR
from modules import bom
from modules import permissions as perm
from ui import close_guard
from ui import v6_kit as K

STATUS_LABEL = {"draft": "Draft", "confirmed": "Confirmed", "cancelled": "Cancelled"}


def _money(v):
    try:
        from modules import country
        return country.money(v)
    except Exception:
        return K.money(v)


def _money_sym(v):
    try:
        from modules import country
        return country.money(v, sym=True)
    except Exception:
        return K.money(v)


def _sym():
    try:
        from modules import country
        return country.symbol()
    except Exception:
        return ""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _qty(v):
    x = _f(v)
    return ("%.4f" % x).rstrip("0").rstrip(".") or "0"


def _each(v):
    x = _f(v)
    if x and abs(x) < 1 and round(x, 2) != round(x, 4):
        return "%.4f" % x
    return _money(x)


def _open_file(path):
    try:
        os.startfile(path)                    # Windows
    except Exception:
        pass


# ════════════════════════════════════════════════════════════
#  The list
# ════════════════════════════════════════════════════════════
class ProductionView:
    def __init__(self, parent):
        self.page = K.Page(parent, "🏭  Production Entry",
                           "Make products from their bill of materials: the materials leave stock at "
                           "their cost, the product made comes into stock at materials + labour + "
                           "overhead. A draft moves nothing; Confirm moves the stock and posts the "
                           "journal.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.frame.new_record = self._new
        tr = self.page.top_right
        for txt, cmd, primary in (("🖨  Print", self._print, False), ("🗑  Delete", self._delete, False),
                                  ("✖  Cancel entry", self._cancel, False), ("✏  Open", self._open, False),
                                  ("＋  New", self._new, True)):
            K.button(tr, C, txt, cmd, primary=primary, side="right").pack_configure(padx=(6, 0))
        if not PR.ready():
            self.page.say("⚠ Production needs the v7.0 database update — Updates ▸ Apply All Updates.",
                          ok=False)
            self.tree = None
            return
        bar = K.card(self.page.body, C, None, fill="x", pady=(0, 6))
        row = tk.Frame(bar, bg=C["card_bg"])
        row.pack(fill="x", padx=10, pady=(4, 6))
        today = date.today()
        self.from_v = tk.StringVar(value=today.replace(day=1).isoformat())
        self.to_v = tk.StringVar(value=today.isoformat())
        self.status_v = tk.StringVar(value="All")
        self.find_v = tk.StringVar()
        K.date_entry(row, C, "From", self.from_v)
        K.date_entry(row, C, "To", self.to_v)
        K.combo(row, C, "Status", self.status_v, ["All", "Draft", "Confirmed", "Cancelled"], 12)
        fe = K.entry(row, C, "Find (number, product, notes)", self.find_v, 26)
        fe.bind("<Return>", lambda e: self._load())
        bf = tk.Frame(row, bg=C["card_bg"])
        bf.pack(side="left", pady=(14, 0))
        K.button(bf, C, "🔍 Show", self._load)
        self.sum_v = tk.StringVar()
        tk.Label(row, textvariable=self.sum_v, font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="right", pady=(14, 0))
        wrap = K.card(self.page.body, C, None, fill="both", expand=True)
        self.tree = K.tree(wrap, [("no", "Number", 140, "w"), ("date", "Date", 90, "center"),
                                  ("product", "Product made", 220, "w"), ("qty", "Qty", 70, "e"),
                                  ("unit", "Unit", 60, "center"), ("mat", "Materials", 95, "e"),
                                  ("lab", "Labour + overhead", 115, "e"), ("total", "Total cost", 100, "e"),
                                  ("each", "Cost of 1", 85, "e"), ("status", "Status", 85, "center"),
                                  ("notes", "Notes", 160, "w")], height=16)
        self.tree.tag_configure("draft", foreground=C.get("text_secondary", "#6B7280"))
        self.tree.tag_configure("cancelled", foreground=C.get("danger", "#DC2626"))
        self.tree.bind("<Double-1>", lambda e: self._open())
        self.tree.bind("<Return>", lambda e: self._open())
        self.tree.bind("<Delete>", lambda e: self._delete())
        self._load()

    def _load(self):
        if not self.tree:
            return
        self.tree.delete(*self.tree.get_children())
        st = self.status_v.get().lower()
        rows = PR.entries(self.from_v.get(), self.to_v.get(), st if st in PR.STATUSES else None,
                          self.find_v.get())
        tot, n_conf = 0.0, 0
        for r in rows:
            status = str(r.get("entry_status") or "").lower()
            if status == "confirmed":
                tot += _f(r.get("total_cost"))
                n_conf += 1
            self.tree.insert("", "end", iid=str(r["entry_id"]), tags=(status,), values=(
                r.get("entry_number"), str(r.get("entry_date") or "")[:10],
                "%s  %s" % (r.get("product_code") or "", r.get("product_name_en") or ""),
                _qty(r.get("quantity")), r.get("unit_name") or "", _money(r.get("material_cost")),
                _money(_f(r.get("labour_cost")) + _f(r.get("overhead_cost"))),
                _money(r.get("total_cost")), _each(r.get("unit_cost")),
                STATUS_LABEL.get(status, status.title()), r.get("notes") or ""))
        self.sum_v.set("%d entries · %d confirmed · made for %s" % (len(rows), n_conf, _money_sym(tot)))

    def _sel(self):
        if not self.tree:
            return None
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _new(self):
        if not perm.allowed("inventory", "add", parent=self.frame):
            return None
        return ProductionForm(self.frame, on_save=self._load)

    def _open(self):
        eid = self._sel()
        if not eid:
            return None
        number, status, _d = PR.info(eid)
        view_only = status == "cancelled" or not perm.can("inventory", "edit")
        if not view_only:
            why = PR.block_reason(eid, "edit")
            if why:
                messagebox.showwarning("Production Entry", why + "\n\nIt opens to look at only.",
                                       parent=self.frame)
                view_only = True
            elif status == "confirmed":
                view_only = not messagebox.askyesno(
                    "Production Entry",
                    "Production entry %s is CONFIRMED.\n\nYou can change it. When you save, the old "
                    "stock and account entries are reversed and the new ones posted automatically."
                    "\n\nOpen it for changing? (No = look only)" % number, parent=self.frame)
        return ProductionForm(self.frame, entry_id=eid, on_save=self._load, view_only=view_only)

    def _cancel(self):
        eid = self._sel()
        if not eid:
            return False
        if not perm.allowed("inventory", "edit", parent=self.frame):
            return False
        ok = cancel_entry(self.frame, eid)
        if ok:
            self._load()
        return ok

    def _delete(self):
        eid = self._sel()
        if not eid:
            return False
        if not perm.allowed("inventory", "delete", parent=self.frame):
            return False
        number, status, _d = PR.info(eid)
        why = PR.block_reason(eid, "delete")
        if why:
            messagebox.showwarning("Delete Production Entry", why, parent=self.frame)
            return False
        if not messagebox.askyesno("Delete Production Entry", "Delete %s (%s)?" % (number, status),
                                   parent=self.frame):
            return False
        try:
            PR.delete(eid)
        except Exception as e:
            messagebox.showerror("Delete Production Entry", str(e)[:300], parent=self.frame)
            return False
        self._load()
        self.page.say("🗑 %s deleted." % number)
        return True

    def _print(self):
        eid = self._sel()
        if not eid:
            messagebox.showinfo("Print", "Pick an entry in the list first.", parent=self.frame)
            return None
        return print_entry(self.frame, eid)


def cancel_entry(parent, entry_id):
    """Ask, then cancel a production entry. True when cancelled."""
    number, status, _d = PR.info(entry_id)
    why = PR.block_reason(entry_id, "cancel")
    if why:
        messagebox.showwarning("Cancel Production Entry", why, parent=parent)
        return False
    text = ("Cancel production entry %s?\n\n" % number)
    if status == "confirmed":
        text += ("The materials go back into stock, the product made comes out of stock and its "
                 "journal is removed.\n\n")
    text += "A cancelled entry can't be changed again."
    if not messagebox.askyesno("Cancel Production Entry", text, parent=parent):
        return False
    try:
        PR.cancel(entry_id)
    except Exception as e:
        messagebox.showerror("Cancel Production Entry", str(e)[:300], parent=parent)
        return False
    return True


def print_entry(parent, entry_id, ask_path=False):
    """The production sheet as PDF: to the printer (or a file). → path"""
    if not perm.allowed("inventory", "print", parent=parent):
        return None
    number = PR.info(entry_id)[0]
    if ask_path:
        path = filedialog.asksaveasfilename(parent=parent, defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf")],
                                            initialfile="Production_%s.pdf" % number)
        if not path:
            return None
    else:
        path = os.path.join(tempfile.gettempdir(), "Production_%s.pdf" % number)
    try:
        PR.print_pdf(entry_id, path)
    except Exception as e:
        messagebox.showerror("Print", "Could not make the PDF: %s" % str(e)[:250], parent=parent)
        return None
    if ask_path:
        _open_file(path)
        return path
    try:
        from ui import print_menu
        if not print_menu.send_pdf(parent, path, "Production %s" % number, "a4"):
            _open_file(path)
    except Exception:
        _open_file(path)
    return path


# ════════════════════════════════════════════════════════════
#  One production run
# ════════════════════════════════════════════════════════════
class ProductionForm:
    def __init__(self, parent, entry_id=None, on_save=None, view_only=False):
        C = self.C = cfg.theme()
        self.parent = parent
        self.entry_id = entry_id
        self.on_save = on_save
        self.view_only = view_only
        self.status = "draft"
        self.number = ""
        self.product = None
        self.plan = None
        self.lines = []
        self._have = {}
        self._lab_typed = self._ovh_typed = False
        self._loading = False
        self._replan_job = None
        self.reopened = None
        self._recipes = bom.with_recipe()
        w = self.win = tk.Toplevel(parent)
        w._is_dirty = self._is_dirty          # close guard: ask only when unsaved
        w.title("Production Entry")
        w.geometry("1140x700")
        w.minsize(940, 580)
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass
        band = tk.Frame(w, bg=C["primary"])
        band.pack(fill="x")
        self.title_v = tk.StringVar(value="🏭  New Production Entry")
        tk.Label(band, textvariable=self.title_v, font=("Segoe UI", 11, "bold"), bg=C["primary"],
                 fg="white").pack(side="left", padx=12, pady=6)
        self.badge_v = tk.StringVar(value="DRAFT")
        self.badge = tk.Label(band, textvariable=self.badge_v, font=("Segoe UI", 9, "bold"),
                              bg="white", fg=C["primary"], padx=8)
        self.badge.pack(side="right", padx=12, pady=6)
        self._build_head(w, C)
        self._build_foot(w, C)
        self._build_lines(w, C)
        close_guard.bind_escape(w)
        if not view_only:
            w.bind("<Control-s>", lambda e: (self._save(confirm=True), "break")[1])
            w.bind("<Control-S>", lambda e: (self._save(confirm=True), "break")[1])
            w.bind("<Control-d>", lambda e: (self._save(confirm=False), "break")[1])
        w.bind("<Control-p>", lambda e: (self._print(), "break")[1])
        if entry_id:
            self._load_entry()
        self._apply_mode()
        self._render()
        if not entry_id:
            self._mark_clean()
            try:
                self.prod_cb.focus_set()
            except Exception:
                pass

    # ── building ──────────────────────────────────────────────
    def _build_head(self, w, C):
        head = K.card(w, C, None, fill="x", padx=10, pady=(8, 4))
        r1 = tk.Frame(head, bg=C["card_bg"])
        r1.pack(fill="x", padx=10, pady=(6, 0))
        self.date_v = tk.StringVar(value=date.today().isoformat())
        self.date_e = K.date_entry(r1, C, "Date", self.date_v)
        f = tk.Frame(r1, bg=C["card_bg"])
        f.pack(side="left", padx=(0, 10), anchor="n")
        tk.Label(f, text="Product made (code, name or barcode)", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.prod_v = tk.StringVar()
        self._choices = ["%s — %s" % (r.get("product_code") or "", r.get("product_name_en") or "")
                         for r in self._recipes]
        self.prod_cb = ttk.Combobox(f, textvariable=self.prod_v, values=self._choices, width=36)
        self.prod_cb.pack(anchor="w", ipady=1)
        self.prod_cb.bind("<KeyRelease>", self._filter_products)
        self.prod_cb.bind("<<ComboboxSelected>>", lambda e: self._pick_product())
        self.prod_cb.bind("<Return>", lambda e: (self._pick_product(), "break")[1])
        self.qty_v, self.unit_v = tk.StringVar(value=""), tk.StringVar()
        self.qty_e = K.entry(r1, C, "Quantity made", self.qty_v, 9, justify="right")
        self.unit_cb = K.combo(r1, C, "Unit", self.unit_v, [], 9)
        self.unit_cb.bind("<<ComboboxSelected>>", lambda e: self._replan_soon(0))
        self.qty_v.trace_add("write", lambda *a: self._replan_soon())
        self.qty_e.bind("<Return>", lambda e: self._replan_soon(0))
        bf = tk.Frame(r1, bg=C["card_bg"])
        bf.pack(side="left", pady=(14, 0))
        self.reset_btn = K.button(bf, C, "↻ Fill from recipe", self._reset_from_recipe)
        r2 = tk.Frame(head, bg=C["card_bg"])
        r2.pack(fill="x", padx=10, pady=(0, 6))
        self.notes_v = tk.StringVar()
        self.notes_e = K.entry(r2, C, "Notes (batch no., who made it …)", self.notes_v, 50)
        self.recipe_v = tk.StringVar(value="Pick the product made — its materials fill in from the "
                                           "bill of materials.")
        tk.Label(r2, textvariable=self.recipe_v, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["primary"], anchor="w", justify="left").pack(side="left", padx=6, pady=(14, 0))

    def _build_lines(self, w, C):
        body = tk.Frame(w, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=10, pady=4)
        lc = K.card(body, C, "Materials", side="left", fill="both", expand=True)
        ra = tk.Frame(lc, bg=C["card_bg"])
        ra.pack(fill="x", padx=10)
        self.add_finder = K.ProductFinder(ra, C, self._picked_extra,
                                          label="Add a material (code, name or barcode)", width=26)
        self.add_finder.pack(side="left", padx=(0, 10), anchor="n")
        self.add_qty_v, self.add_unit_v = tk.StringVar(value="1"), tk.StringVar()
        self.add_qty_e = K.entry(ra, C, "Qty used", self.add_qty_v, 8, justify="right")
        self.add_unit_cb = K.combo(ra, C, "Unit", self.add_unit_v, [], 8)
        self.add_qty_e.bind("<Return>", lambda e: (self._add_extra(), "break")[1])
        bf = tk.Frame(ra, bg=C["card_bg"])
        bf.pack(side="left", pady=(14, 0))
        self.add_btn = K.button(bf, C, "＋ Add", self._add_extra)
        self.tree = K.tree(lc, [("n", "#", 32, "center"), ("code", "Code", 70, "w"),
                                ("name", "Material", 180, "w"), ("planned", "Planned", 75, "e"),
                                ("used", "Used ✎", 75, "e"), ("unit", "Unit", 55, "center"),
                                ("stock", "In stock", 75, "e"), ("short", "Short", 65, "e"),
                                ("each", "Cost each", 80, "e"), ("cost", "Line cost", 85, "e")],
                           height=10)
        self.tree.tag_configure("short", foreground=C.get("danger", "#DC2626"))
        self.tree.tag_configure("service", foreground=C.get("text_secondary", "#6B7280"))
        self.tree.bind("<Double-1>", self._edit_used)
        self.tree.bind("<F2>", self._edit_used)
        self.tree.bind("<Delete>", lambda e: self._remove())
        rl = tk.Frame(lc, bg=C["card_bg"])
        rl.pack(fill="x", padx=10, pady=(0, 8))
        self.edit_btn = K.button(rl, C, "✎ Change qty used  [F2]", self._edit_used)
        self.remove_btn = K.button(rl, C, "🗑 Remove line  [Del]", self._remove)
        self.short_v = tk.StringVar()
        tk.Label(rl, textvariable=self.short_v, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C.get("danger", "#DC2626"), anchor="e").pack(side="right")

        cc = K.card(body, C, "Cost", side="right", fill="y", padx=(8, 0))
        g = tk.Frame(cc, bg=C["card_bg"])
        g.pack(fill="x", padx=12, pady=(2, 10))
        self.lab_v, self.ovh_v = tk.StringVar(value="0"), tk.StringVar(value="0")
        self.cost_vars = {}

        def row(r, label, key=None, var=None, bold=False):
            tk.Label(g, text=label, font=("Segoe UI", 9, "bold" if bold else "normal"), bg=C["card_bg"],
                     fg=C["text_secondary"], anchor="w").grid(row=r, column=0, sticky="w", pady=2)
            if var is not None:
                e = tk.Entry(g, textvariable=var, width=11, font=("Segoe UI", 10), relief="solid",
                             bd=1, justify="right")
                e.grid(row=r, column=1, sticky="e", pady=2)
                e._fixed_width = True
                return e
            v = tk.StringVar(value="0.00")
            self.cost_vars[key] = v
            tk.Label(g, textvariable=v, font=("Segoe UI", 11 if bold else 10, "bold" if bold else "normal"),
                     bg=C["card_bg"], fg=C["text_primary"], anchor="e").grid(row=r, column=1, sticky="e",
                                                                            pady=2)
            return None
        row(0, "Materials", "materials")
        self.lab_e = row(1, "Labour", var=self.lab_v)
        self.ovh_e = row(2, "Overhead (gas, power …)", var=self.ovh_v)
        tk.Frame(g, bg=C["border"], height=1).grid(row=3, column=0, columnspan=2, sticky="we", pady=4)
        row(4, "Total cost", "total", bold=True)
        self.each_label_v = tk.StringVar(value="Cost of 1 unit")
        tk.Label(g, textvariable=self.each_label_v, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["text_secondary"], anchor="w").grid(row=5, column=0, sticky="w", pady=2)
        v = tk.StringVar(value="0.00")
        self.cost_vars["each"] = v
        tk.Label(g, textvariable=v, font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                 fg=C["primary"], anchor="e").grid(row=5, column=1, sticky="e", pady=2)
        tk.Frame(g, bg=C["border"], height=1).grid(row=6, column=0, columnspan=2, sticky="we", pady=4)
        row(7, "Average cost now", "avg")
        row(8, "Sale price (no VAT)", "sale")
        row(9, "Profit on 1 unit", "profit")
        tk.Label(cc, text="Confirm posts:  Dr Inventory (made)\nCr Inventory (materials)\n"
                          "Cr Labour & Overheads Applied", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"], justify="left").pack(anchor="w", padx=12, pady=(0, 10))
        self.lab_v.trace_add("write", lambda *a: self._typed("lab"))
        self.ovh_v.trace_add("write", lambda *a: self._typed("ovh"))

    def _build_foot(self, w, C):
        foot = tk.Frame(w, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        foot.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar()
        tk.Label(foot, textvariable=self.status_var, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left", padx=12, pady=8)
        tk.Button(foot, text="Esc  Close", font=("Segoe UI", 9), relief="flat", padx=10, cursor="hand2",
                  command=self._close).pack(side="right", padx=6, pady=6)
        self.btns = {}
        for key, txt, cmd, kw in (
                ("confirm", "✔ Confirm  [Ctrl+S]", lambda: self._save(confirm=True),
                 dict(bg=C.get("success", "#16A34A"), fg="white")),
                ("draft", "Save draft  [Ctrl+D]", lambda: self._save(confirm=False), {}),
                ("cancel", "✖ Cancel entry", self._cancel_entry, {}),
                ("print", "🖨 Print  [Ctrl+P]", self._print, {}),
                ("pdf", "📄 PDF", lambda: self._print(ask_path=True), {})):
            b = tk.Button(foot, text=txt, font=("Segoe UI", 9, "bold" if key == "confirm" else "normal"),
                          relief="flat", padx=12, cursor="hand2", command=cmd, **kw)
            b.pack(side="right", padx=4, pady=6)
            self.btns[key] = b

    def _apply_mode(self):
        """Buttons / boxes by status and rights."""
        saved = bool(self.entry_id)
        ro = self.view_only
        for k in ("confirm", "draft"):
            self.btns[k].pack_forget()
        self.btns["cancel"].pack_forget()
        self.btns["print"].pack_forget()
        self.btns["pdf"].pack_forget()
        order = []
        if not ro:
            order.append("confirm")
            if self.status != "confirmed":
                order.append("draft")
        if saved and self.status in ("draft", "confirmed") and not ro:
            order.append("cancel")
        if saved:
            order += ["print", "pdf"]
        for k in order:
            self.btns[k].pack(side="right", padx=4, pady=6)
        if self.status == "confirmed" and not ro:
            self.btns["confirm"].configure(text="✔ Save changes  [Ctrl+S]")
        st = "disabled" if ro else "normal"
        for wdg in (self.date_e, self.qty_e, self.notes_e, self.lab_e, self.ovh_e, self.add_qty_e,
                    self.add_finder.entry, self.add_btn, self.edit_btn, self.remove_btn, self.reset_btn):
            try:
                wdg.configure(state=st)
            except Exception:
                pass
        self.prod_cb.configure(state="disabled" if (ro or self.status == "confirmed") else "normal")
        self.unit_cb.configure(state="disabled" if ro else "readonly")
        self.add_unit_cb.configure(state="disabled" if ro else "readonly")
        self.badge_v.set((STATUS_LABEL.get(self.status, self.status) +
                          ("  ·  VIEW ONLY" if ro and saved else "")).upper())
        colors = {"draft": "#6B7280", "confirmed": self.C.get("success", "#16A34A"),
                  "cancelled": self.C.get("danger", "#DC2626")}
        self.badge.configure(fg=colors.get(self.status, self.C["primary"]))

    # ── product ───────────────────────────────────────────────
    def _filter_products(self, e=None):
        if e is not None and e.keysym in ("Return", "Up", "Down", "Escape", "Tab"):
            return
        q = self.prod_v.get().strip().lower()
        if not q:
            self.prod_cb["values"] = self._choices
            return
        self.prod_cb["values"] = [c for c in self._choices if all(t in c.lower() for t in q.split())][:60]

    def _find_product(self, text):
        t = (text or "").strip()
        if not t:
            return None
        code = t.split(" — ")[0].strip().lower()
        for r in self._recipes:
            if str(r.get("product_code") or "").lower() == code or \
                    str(r.get("barcode") or "").lower() == t.lower():
                return r
        try:                                     # any barcode of the product (units, extra codes)
            from modules import product_lookup as PL
            ids = set(PL.barcode_product_ids(t))
            hit = [r for r in self._recipes if r["product_id"] in ids]
            if hit:
                return hit[0]
        except Exception:
            pass
        hits = [r for r, c in zip(self._recipes, self._choices)
                if all(x in c.lower() for x in t.lower().split())]
        return hits[0] if len(hits) == 1 else None

    def _pick_product(self):
        r = self._find_product(self.prod_v.get())
        if not r:
            if self.prod_v.get().strip():
                self.prod_cb.event_generate("<Down>")
                self.status_var.set("Pick a product that has a bill of materials.")
            return
        self.set_product(r["product_id"])
        self.qty_e.focus_set()
        self.qty_e.select_range(0, "end")

    def set_product(self, product_id, qty=None):
        """Choose the product made: units, recipe info and the materials."""
        try:
            p = db.fetchone("SELECT product_id, product_code, product_name_en, unit_of_measure_en, "
                            "ISNULL(stock_quantity,0) AS stock, ISNULL(average_cost,0) AS avg "
                            "FROM products WHERE product_id=?", (int(product_id),))
        except Exception:
            p = None
        if not p:
            return
        same = self.product and self.product.get("product_id") == p["product_id"]
        self.product = dict(p)
        self.prod_v.set("%s — %s" % (p.get("product_code") or "", p.get("product_name_en") or ""))
        units = bom.units(p["product_id"])
        self.unit_cb["values"] = units
        h = bom.header(p["product_id"])
        if not same:
            self._sale_cache = {}
            unit = (h or {}).get("output_unit") or units[0]
            self.unit_v.set(unit if unit in units else units[0])
            self._loading = True
            self.qty_v.set(_qty(qty if qty is not None else ((h or {}).get("output_qty") or 1)))
            self._loading = False
            self._lab_typed = self._ovh_typed = False
            self.lines = []
            self._replan(reset=True)

    def _recipe_text(self):
        pl = self.plan
        if not self.product:
            return ""
        if not pl:
            return "⚠ %s has no bill of materials now — add materials yourself." % \
                self.product.get("product_name_en")
        return ("Recipe: one batch makes %s %s  ·  this is %s batch(es)"
                % (_qty(pl["output_qty"]), pl["output_unit"] or "", _qty(round(pl["batches"], 4))))

    # ── the plan (materials from the recipe × quantity) ───────
    def _replan_soon(self, ms=450):
        if self._loading or self.view_only or not self.product:
            return
        if self._replan_job:
            try:
                self.win.after_cancel(self._replan_job)
            except Exception:
                pass
        self._replan_job = self.win.after(ms, self._replan)

    def _replan(self, reset=False):
        """Fill / rescale the materials from the bill of materials. Lines
        whose quantity used was typed keep it (unless reset)."""
        self._replan_job = None
        if not self.product:
            return
        qty = K.num(self.qty_v)
        if not qty or qty <= 0:
            self._render()
            return
        pl = PR.plan(self.product["product_id"], qty, self.unit_v.get())
        self.plan = pl
        if pl:
            fresh = {(l["component_id"], l["unit_name"]): l for l in pl["lines"]}
            if reset:
                self.lines = [dict(l, _used_typed=False, _extra=False) for l in pl["lines"]]
            else:
                kept = []
                for l in self.lines:
                    key = (l["component_id"], l["unit_name"])
                    if key in fresh:
                        nl = fresh.pop(key)
                        l["qty_planned"] = nl["qty_planned"]
                        if not l.get("_used_typed"):
                            l["qty_used"] = nl["qty_planned"]
                        kept.append(l)
                    elif l.get("_extra") or l.get("_used_typed"):
                        l["qty_planned"] = 0.0 if not l.get("_extra") else l.get("qty_planned", 0.0)
                        kept.append(l)
                for nl in fresh.values():
                    kept.append(dict(nl, _used_typed=False, _extra=False))
                self.lines = kept
            if not self._lab_typed:
                self._set_quiet(self.lab_v, _qty(pl["labour_cost"]))
            if not self._ovh_typed:
                self._set_quiet(self.ovh_v, _qty(pl["overhead_cost"]))
        self.recipe_v.set(self._recipe_text())
        self._refresh_stock()
        self._render()

    def _reset_from_recipe(self):
        if self.view_only or not self.product:
            return
        if self.lines and any(l.get("_used_typed") or l.get("_extra") for l in self.lines):
            if not messagebox.askyesno("Fill from recipe", "Put back the materials and quantities "
                                       "of the bill of materials?\n\nQuantities you changed and "
                                       "materials you added are replaced.", parent=self.win):
                return
        self._lab_typed = self._ovh_typed = False
        self._replan(reset=True)

    def _set_quiet(self, var, value):
        was = self._loading
        self._loading = True
        try:
            var.set(value)
        finally:
            self._loading = was

    def _typed(self, which):
        if self._loading:
            return
        if which == "lab":
            self._lab_typed = True
        else:
            self._ovh_typed = True
        self._recalc()

    # ── extra materials / quantity used ───────────────────────
    def _picked_extra(self, row):
        units = bom.units(row["product_id"])
        self.add_unit_cb["values"] = units
        self.add_unit_v.set(units[0])
        self.add_qty_e.focus_set()
        self.add_qty_e.select_range(0, "end")

    def _add_extra(self):
        if self.view_only:
            return
        p = self.add_finder.picked
        if not p:
            self.add_finder.find()
            return
        if self.product and p["product_id"] == self.product["product_id"]:
            messagebox.showwarning("Material", "The product made can't be one of its own materials.",
                                   parent=self.win)
            return
        q = K.num(self.add_qty_v)
        if not q or q <= 0:
            messagebox.showwarning("Material", "Type the quantity used (more than 0).", parent=self.win)
            return
        from modules import doc_posting as dp
        units = bom.units(p["product_id"])
        unit = self.add_unit_v.get() if self.add_unit_v.get() in units else units[0]
        same = next((l for l in self.lines if l["component_id"] == p["product_id"]
                     and l["unit_name"] == unit), None)
        if same:
            same["qty_used"] = _f(same["qty_used"]) + q
            same["_used_typed"] = True
        else:
            f = dp.unit_factor(p["product_id"], unit)
            stock_item = dp._is_stock_item(p["product_id"])
            self.lines.append({"component_id": p["product_id"], "product_code": p.get("product_code") or "",
                               "product_name_en": p.get("product_name_en") or "", "qty_planned": 0.0,
                               "qty_used": q, "unit_name": unit, "unit_factor": f, "is_stock": stock_item,
                               "cost_each": round(dp.unit_cost(p["product_id"]) * f, 6),
                               "_used_typed": True, "_extra": True})
        self.add_finder.clear()
        self.add_qty_v.set("1")
        self.add_unit_v.set("")
        self._refresh_stock()
        self._render()
        self.add_finder.entry.focus_set()

    def _sel_idx(self):
        s = self.tree.selection()
        if not s:
            return None
        i = int(s[0])
        return i if 0 <= i < len(self.lines) else None

    def set_used(self, idx, qty):
        """Change the quantity really used of line idx."""
        if self.view_only or not (0 <= idx < len(self.lines)):
            return False
        q = _f(qty)
        if q < 0:
            return False
        self.lines[idx]["qty_used"] = round(q, 4)
        self.lines[idx]["_used_typed"] = abs(q - _f(self.lines[idx].get("qty_planned"))) > 1e-9
        self._render()
        try:
            self.tree.selection_set(str(idx))
        except Exception:
            pass
        return True

    def _edit_used(self, event=None):
        """A small box over the 'Used' cell: Enter keeps it, Esc leaves it."""
        if self.view_only:
            return "break"
        if event is not None and getattr(event, "y", None) is not None and event.type == tk.EventType.ButtonPress:
            iid = self.tree.identify_row(event.y)
            if iid:
                self.tree.selection_set(iid)
        i = self._sel_idx()
        if i is None:
            return "break"
        bb = self.tree.bbox(str(i), "used")
        if not bb:
            return "break"
        x, y, w, h = bb
        var = tk.StringVar(value=_qty(self.lines[i]["qty_used"]))
        e = tk.Entry(self.tree, textvariable=var, justify="right", font=("Segoe UI", 10), relief="solid", bd=1)
        e.place(x=x, y=y, width=w, height=h)
        e.focus_set()
        e.select_range(0, "end")
        self._cell = e
        done = {"v": False}

        def keep(_ev=None):
            if done["v"]:
                return "break"
            done["v"] = True
            v = K.num(var)
            e.destroy()
            self._cell = None
            if v is not None and v >= 0:
                self.set_used(i, v)
            self.tree.focus_set()
            return "break"

        def leave(_ev=None):
            done["v"] = True
            e.destroy()
            self._cell = None
            self.tree.focus_set()
            return "break"
        e.bind("<Return>", keep)
        e.bind("<KP_Enter>", keep)
        e.bind("<Tab>", keep)
        e.bind("<FocusOut>", keep)
        e.bind("<Escape>", leave)
        return "break"

    def _remove(self):
        if self.view_only:
            return
        i = self._sel_idx()
        if i is None:
            return
        del self.lines[i]
        self._refresh_stock()
        self._render()

    # ── stock / cost ──────────────────────────────────────────
    def _refresh_stock(self):
        ids = [l["component_id"] for l in self.lines]
        took = self.entry_id if self.status == "confirmed" else None
        try:
            self._have = PR.stock_on_hand(ids, took)
        except Exception:
            self._have = {}

    def _shortfalls(self):
        return PR.shortfalls(self.lines, None, None, _have=self._have)

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        short = {c: (h, q) for c, _n, h, q in self._shortfalls()}
        for i, l in enumerate(self.lines):
            f = _f(l.get("unit_factor")) or 1.0
            cid = l["component_id"]
            if not l.get("is_stock", True):
                stock_txt, short_txt, tags = "service", "", ("service",)
            else:
                have = _f(self._have.get(cid))
                stock_txt = _qty(round(have / f, 4))
                short_txt, tags = "", ()
                if cid in short:
                    h, q = short[cid]
                    short_txt = _qty(round((q - h) / f, 4))
                    tags = ("short",)
            lc = round(_f(l.get("qty_used")) * _f(l.get("cost_each")), 2)
            self.tree.insert("", "end", iid=str(i), tags=tags, values=(
                i + 1, l.get("product_code") or "", l.get("product_name_en") or "",
                _qty(l.get("qty_planned")), _qty(l.get("qty_used")), l.get("unit_name") or "",
                stock_txt, short_txt, _each(l.get("cost_each")), _money(lc)))
        if short and self.status != "cancelled" and not self.view_only:
            self.short_v.set("⚠ Not enough stock of %d material(s)%s" % (
                len(short), "" if PR.allow_negative() else " — Confirm is refused"))
        else:
            self.short_v.set("")
        self._recalc()

    def _sale(self, unit):
        if not self.product:
            return 0.0
        cache = getattr(self, "_sale_cache", None)
        if cache is None:
            cache = self._sale_cache = {}
        if unit not in cache:
            cache[unit] = bom.sale_price(self.product["product_id"], unit)
        return cache[unit]

    def totals(self):
        """{materials, labour, overhead, total, each} as on screen."""
        mat = round(sum(round(_f(l.get("qty_used")) * _f(l.get("cost_each")), 2) for l in self.lines), 2)
        lab = K.num(self.lab_v, 0) or 0.0
        ovh = K.num(self.ovh_v, 0) or 0.0
        total = round(mat + lab + ovh, 2)
        qty = K.num(self.qty_v, 0) or 0.0
        return {"materials": mat, "labour": lab, "overhead": ovh, "total": total,
                "each": (total / qty) if qty > 0 else 0.0}

    def _recalc(self):
        t = self.totals()
        self.cost_vars["materials"].set(_money_sym(t["materials"]))
        self.cost_vars["total"].set(_money_sym(t["total"]))
        unit = self.unit_v.get() or "unit"
        self.each_label_v.set("Cost of 1 %s" % unit)
        self.cost_vars["each"].set(_money_sym(t["each"]))
        if self.product:
            from modules import doc_posting as dp
            f = dp.unit_factor(self.product["product_id"], self.unit_v.get())
            self.cost_vars["avg"].set(_money_sym(_f(self.product.get("avg")) * f))
            sale = self._sale(self.unit_v.get())
            self.cost_vars["sale"].set(_money_sym(sale) if sale else "—")
            self.cost_vars["profit"].set(_money_sym(sale - t["each"]) if sale else "—")
        else:
            for k in ("avg", "sale", "profit"):
                self.cost_vars[k].set("—")

    # ── load ──────────────────────────────────────────────────
    def _load_entry(self):
        h, lines = PR.get(self.entry_id)
        if not h:
            self.status_var.set("This entry no longer exists.")
            return
        self._loading = True
        try:
            self.status = str(h.get("entry_status") or "draft").lower()
            self.number = h.get("entry_number") or ""
            self.date_v.set(str(h.get("entry_date") or "")[:10])
            self.notes_v.set(h.get("notes") or "")
            try:
                p = db.fetchone("SELECT product_id, product_code, product_name_en, unit_of_measure_en, "
                                "ISNULL(stock_quantity,0) AS stock, ISNULL(average_cost,0) AS avg "
                                "FROM products WHERE product_id=?", (int(h["product_id"]),))
            except Exception:
                p = None
            self.product = dict(p) if p else {"product_id": h["product_id"],
                                              "product_code": h.get("product_code"),
                                              "product_name_en": h.get("product_name_en"), "avg": 0}
            self.prod_v.set("%s — %s" % (h.get("product_code") or "", h.get("product_name_en") or ""))
            self.unit_cb["values"] = bom.units(h["product_id"])
            self.unit_v.set(h.get("unit_name") or "")
            self.qty_v.set(_qty(h.get("quantity")))
            self.lab_v.set(_qty(h.get("labour_cost")))
            self.ovh_v.set(_qty(h.get("overhead_cost")))
            self._lab_typed = self._ovh_typed = True
            from modules import doc_posting as dp
            self.lines = []
            for l in lines:
                f = _f(l.get("unit_factor")) or 1.0
                each = _f(l.get("cost_each"))
                if self.status == "draft":           # a draft costs at today's average cost
                    each = round(dp.unit_cost(l["component_id"]) * f, 6)
                self.lines.append({"component_id": l["component_id"], "product_code": l.get("product_code") or "",
                                   "product_name_en": l.get("product_name_en") or "",
                                   "qty_planned": _f(l.get("qty_planned")), "qty_used": _f(l.get("qty_used")),
                                   "unit_name": l.get("unit_name") or "", "unit_factor": f,
                                   "is_stock": bool(l.get("is_stock", 1)), "cost_each": each,
                                   "_used_typed": abs(_f(l.get("qty_used")) - _f(l.get("qty_planned"))) > 1e-9,
                                   "_extra": _f(l.get("qty_planned")) <= 0})
            try:
                self.plan = PR.plan(h["product_id"], _f(h.get("quantity")), h.get("unit_name") or "")
            except Exception:
                self.plan = None
        finally:
            self._loading = False
        self.recipe_v.set(self._recipe_text())
        self.title_v.set("🏭  Production Entry  %s" % self.number)
        self._refresh_stock()
        self._render()
        self._mark_clean()

    # ── save / cancel / print ─────────────────────────────────
    def _header(self, confirm):
        return {"entry_date": self.date_v.get(), "product_id": (self.product or {}).get("product_id"),
                "quantity": K.num(self.qty_v, 0) or 0, "unit_name": self.unit_v.get(),
                "labour_cost": K.num(self.lab_v, 0) or 0, "overhead_cost": K.num(self.ovh_v, 0) or 0,
                "notes": self.notes_v.get().strip(),
                "entry_status": "confirmed" if confirm else "draft"}

    def _save(self, confirm=True):
        if self.view_only:
            return False
        if self._replan_job:                 # a quantity just typed: fill the materials first
            try:
                self.win.after_cancel(self._replan_job)
            except Exception:
                pass
            self._replan()
        action = "edit" if self.entry_id else "add"
        if not perm.allowed("inventory", action, parent=self.win):
            return False
        if self.entry_id and self.status == "confirmed":
            confirm = True                   # a confirmed entry stays confirmed (Cancel undoes it)
        if not self.product:
            messagebox.showwarning("Production Entry", "Choose the product you made.", parent=self.win)
            return False
        if not (K.num(self.qty_v, 0) or 0) > 0:
            messagebox.showwarning("Production Entry", "Type how many you made (more than 0).",
                                   parent=self.win)
            return False
        if not any(_f(l.get("qty_used")) > 0 for l in self.lines):
            messagebox.showwarning("Production Entry", "Add the materials used (at least one with a "
                                   "quantity).", parent=self.win)
            return False
        if confirm:
            self._refresh_stock()
            short = self._shortfalls()
            if short:
                text = PR.short_text(short)
                if not PR.allow_negative():
                    messagebox.showwarning(
                        "Not enough stock",
                        "There is not enough stock to make this:\n\n%s\n\nBuy or move the stock in "
                        "first, or change the quantity used. You can Save it as a draft now and "
                        "confirm it later." % text.replace("; ", "\n"), parent=self.win)
                    self._render()
                    return False
                if not messagebox.askyesno("Not enough stock",
                                           "These materials will go below zero:\n\n%s\n\nConfirm "
                                           "anyway?" % text.replace("; ", "\n"), parent=self.win):
                    return False
        u = perm.session_user() or {}
        rows = [{"component_id": l["component_id"], "qty_planned": l.get("qty_planned"),
                 "qty_used": l.get("qty_used"), "unit_name": l.get("unit_name")} for l in self.lines]
        try:
            eid, number, warn = PR.save(self._header(confirm), rows, entry_id=self.entry_id,
                                        user_id=u.get("user_id"))
        except Exception as e:
            messagebox.showerror("Production Entry", str(e)[:400], parent=self.win)
            return False
        was = self.entry_id
        self.entry_id = eid
        self._mark_clean()
        messagebox.showinfo("Production Entry",
                            "%s saved%s." % (number, "" if confirm else " as a draft (no stock moved)")
                            + (("\n\n⚠ " + warn) if warn else ""), parent=self.win)
        if self.on_save:
            try:
                self.on_save()
            except Exception:
                pass
        from ui import after_save
        parent, cb = self.parent, self.on_save
        self.reopened = after_save.finish(
            self, number, new=lambda: ProductionForm(parent, on_save=cb),
            keep=lambda: ProductionForm(parent, entry_id=eid, on_save=cb), edited=bool(was))
        return True

    def _cancel_entry(self):
        if self.view_only or not self.entry_id:
            return False
        if not perm.allowed("inventory", "edit", parent=self.win):
            return False
        if not cancel_entry(self.win, self.entry_id):
            return False
        if self.on_save:
            try:
                self.on_save()
            except Exception:
                pass
        parent, cb, eid = self.parent, self.on_save, self.entry_id
        self._clean_sig = None
        geo = self.win.geometry()
        self.win.destroy()
        self.reopened = ProductionForm(parent, entry_id=eid, on_save=cb, view_only=True)
        try:
            self.reopened.win.geometry(geo)
            self.reopened.status_var.set("✖ Cancelled — stock and journal reversed.")
        except Exception:
            pass
        return True

    def _print(self, ask_path=False):
        if not self.entry_id:
            messagebox.showinfo("Print", "Save the entry first.", parent=self.win)
            return None
        if self._is_dirty():
            messagebox.showinfo("Print", "Save your changes first — the print shows the saved entry.",
                                parent=self.win)
        return print_entry(self.win, self.entry_id, ask_path=ask_path)

    def _close(self):
        close_guard.request_close(self.win)

    # ── unsaved changes ───────────────────────────────────────
    def _sig(self):
        return (self.date_v.get(), (self.product or {}).get("product_id"), self.qty_v.get(),
                self.unit_v.get(), self.lab_v.get(), self.ovh_v.get(), self.notes_v.get(),
                tuple((l["component_id"], l.get("unit_name"), round(_f(l.get("qty_used")), 4))
                      for l in self.lines))

    def _mark_clean(self):
        self._clean_sig = self._sig()

    def _is_dirty(self):
        if self.view_only:
            return False
        if not self.entry_id and not self.lines:
            return False
        return self._sig() != getattr(self, "_clean_sig", None)


# ════════════════════════════════════════════════════════════
#  Production report
# ════════════════════════════════════════════════════════════
class ProductionReportView:
    TABS = (("production_register", "Production register"),
            ("production_materials", "Material usage (planned vs used)"),
            ("production_cost_trend", "Cost of 1 unit by month"))

    def __init__(self, parent):
        from modules import report_center as RC
        self.RC = RC
        self.page = K.Page(parent, "📊  Production Report",
                           "What was made in the period and what it cost, the materials planned "
                           "against really used, and how the cost of one unit changes month by month. "
                           "Only confirmed production entries count.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.results = {}
        bar = K.card(self.page.body, C, None, fill="x", pady=(0, 6))
        row = tk.Frame(bar, bg=C["card_bg"])
        row.pack(fill="x", padx=10, pady=(4, 6))
        today = date.today()
        self.quick_v = tk.StringVar(value="This month")
        self.from_v = tk.StringVar(value=today.replace(day=1).isoformat())
        self.to_v = tk.StringVar(value=today.isoformat())
        self.find_v = tk.StringVar()
        cb = K.combo(row, C, "Period", self.quick_v, ["Today", "This week", "This month", "Last month",
                                                      "This quarter", "This year", "Last year", "Custom"], 12)
        cb.bind("<<ComboboxSelected>>", lambda e: self._quick())
        K.date_entry(row, C, "From", self.from_v)
        K.date_entry(row, C, "To", self.to_v)
        fe = K.entry(row, C, "Product (code or name)", self.find_v, 22)
        fe.bind("<Return>", lambda e: self.run())
        bf = tk.Frame(row, bg=C["card_bg"])
        bf.pack(side="left", pady=(14, 0))
        K.button(bf, C, "▶ Show  [F5]", self.run, primary=True)
        K.button(bf, C, "📊 Excel", self.export_excel)
        K.button(bf, C, "📄 PDF", self.export_pdf)
        self.frame.bind_all("<F5>", self._f5, add="+")
        self.nb = ttk.Notebook(self.page.body)
        self.nb.pack(fill="both", expand=True)
        self.tabs = {}
        for rid, title in self.TABS:
            tab = tk.Frame(self.nb, bg=C["card_bg"])
            self.nb.add(tab, text="  %s  " % title)
            summ = tk.StringVar()
            tk.Label(tab, textvariable=summ, font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                     fg=C["primary"], anchor="w", justify="left").pack(fill="x", padx=12, pady=(8, 2))
            wrap = tk.Frame(tab, bg=C["card_bg"])
            wrap.pack(fill="both", expand=True, padx=10, pady=4)
            tree = ttk.Treeview(wrap, show="headings", height=14)
            ys = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
            xs = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
            ys.pack(side="right", fill="y")
            xs.pack(side="bottom", fill="x")
            tree.pack(side="left", fill="both", expand=True)
            tree.tag_configure("total", font=("Segoe UI", 9, "bold"))
            tree.tag_configure("hi", foreground=C.get("danger", "#DC2626"))
            tree.tag_configure("sub", font=("Segoe UI", 9, "bold"))
            notes = tk.StringVar()
            tk.Label(tab, textvariable=notes, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"], anchor="w", justify="left", wraplength=1000).pack(
                         fill="x", padx=12, pady=(0, 8))
            self.tabs[rid] = {"tree": tree, "summary": summ, "notes": notes}
        self.run()

    def _f5(self, event=None):
        try:
            if self.frame.winfo_exists() and self.frame.winfo_ismapped() and \
                    event.widget.winfo_toplevel() is self.frame.winfo_toplevel():
                self.run()
                return "break"
        except Exception:
            pass
        return None

    def _quick(self):
        try:
            from ui.report_center import quick_range
            f, t = quick_range(self.quick_v.get())
        except Exception:
            f = t = None
        if f and t:
            self.from_v.set(f.isoformat())
            self.to_v.set(t.isoformat())
            self.run()

    def _iso(self, v):
        try:
            return PR._iso(v)
        except ValueError:
            return None

    def run(self):
        f, t = self._iso(self.from_v.get()), self._iso(self.to_v.get())
        if not f or not t:
            self.page.say("⚠ Type the dates like %s." % date.today().isoformat(), ok=False)
            return
        if not perm.can("reports", "view"):
            self.page.say("⚠ Your user type can't run reports.", ok=False)
            return
        for rid, _title in self.TABS:
            try:
                res = self.RC.run(rid, date_from=f, date_to=t, product=self.find_v.get().strip())
            except Exception as e:
                self.results.pop(rid, None)
                self.tabs[rid]["summary"].set("⚠ Could not run: %s" % str(e)[:150])
                continue
            self.results[rid] = res
            self._render(rid, res)
        self.page.say("%s  →  %s" % (f, t))

    def _render(self, rid, res):
        RC = self.RC
        tab = self.tabs[rid]
        tree = tab["tree"]
        tree.delete(*tree.get_children())
        cols = res["columns"]
        tree["columns"] = [c["key"] for c in cols]
        for c in cols:
            tree.heading(c["key"], text=c["label"], anchor="e" if c["align"] == "e" else "w")
            tree.column(c["key"], width=c["width"], minwidth=40, anchor=c["align"],
                        stretch=c["kind"] == "text" and c["width"] >= 180)

        def cell(v, c):
            return RC.fmt(v, c["kind"]) if c["kind"] in RC.NUMERIC else ("" if v is None else v)
        for r in res["rows"]:
            st = r.get("_style")
            tree.insert("", "end", values=[cell(r.get(c["key"]), c) for c in cols],
                        tags=(st,) if st else ())
        if res.get("totals"):
            tree.insert("", "end", values=[cell(res["totals"].get(c["key"]), c) for c in cols],
                        tags=("total",))
        parts = []
        for label, val, kind in res.get("summary") or []:
            if kind == "money":
                parts.append("%s: %s" % (label, _money_sym(val)))
            else:
                parts.append("%s: %s" % (label, RC.fmt(val, kind) if kind in RC.NUMERIC else val))
        tab["summary"].set("   ·   ".join(parts))
        tab["notes"].set("   ".join("ℹ " + n for n in res.get("notes") or []))

    def current(self):
        try:
            idx = self.nb.index(self.nb.select())
        except Exception:
            idx = 0
        return self.TABS[idx][0]

    def _export(self, ext):
        rid = self.current()
        res = self.results.get(rid)
        if not res:
            messagebox.showinfo("Production Report", "Show the report first.", parent=self.frame)
            return None
        if not perm.allowed("reports", "export" if ext == "xlsx" else "print", parent=self.frame):
            return None
        base = res.get("title", "Production").split("(")[0].strip().replace(" ", "_")
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension="." + ext,
            filetypes=[("Excel", "*.xlsx")] if ext == "xlsx" else [("PDF", "*.pdf")],
            initialfile="%s_%s_%s.%s" % (base, self.from_v.get(), self.to_v.get(), ext))
        if not path:
            return None
        try:
            (self.RC.to_excel if ext == "xlsx" else self.RC.to_pdf)(res, path)
        except Exception as e:
            messagebox.showerror("Production Report", str(e)[:300], parent=self.frame)
            return None
        self.page.say("Saved " + os.path.basename(path))
        _open_file(path)
        return path

    def export_excel(self):
        return self._export("xlsx")

    def export_pdf(self):
        return self._export("pdf")
