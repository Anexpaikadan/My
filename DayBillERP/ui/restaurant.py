# ============================================================
# DayBill ERP - Restaurant screens (v7.0)
# ------------------------------------------------------------
#   TablesView           Restaurant ▸ Tables & Orders: every table by
#                        area (free / occupied / bill printed) with its
#                        order, guests, waiter, total and minutes open;
#                        takeaway and delivery orders on the right.
#                        Click a free table = new order, a busy one =
#                        open it in the POS. Right-click = more.
#   KotView              Restaurant ▸ Kitchen Orders (KOT): the kitchen
#                        screen — tickets new / preparing / ready, big
#                        text, minutes waiting, bump and reprint
#   RestaurantSetupView  Restaurant ▸ Restaurant Setup: areas, tables,
#                        kitchen stations + printers, which category goes
#                        to which station, order types, service charge
#   TablePicker / RunningOrders / ask_*   small windows the POS uses
# Data: modules/restaurant.py. The POS part: ui/restaurant_pos.py.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import weakref

from config import settings as cfg
from modules import restaurant as R

STATE_LOOK = {   # state: (background, border, text)
    "free": ("#E8F8EF", "#27AE60", "#145A32"),
    "occupied": ("#FDEBD0", "#E67E22", "#784212"),
    "billed": ("#D6EAF8", "#2E86C1", "#1B4F72"),
    "off": ("#F2F3F4", "#BFC9CA", "#909497"),
}
STATE_NAME = {"free": "Free", "occupied": "Occupied", "billed": "Bill printed"}
KOT_LOOK = {"new": "#C0392B", "preparing": "#D68910", "ready": "#1E8449", "served": "#7F8C8D"}
KOT_NEXT = {"new": "▶  Start cooking", "preparing": "✓  Ready", "ready": "🍽  Served"}

_LIVE = weakref.WeakSet()


def changed():
    """An order changed: open restaurant screens show it now."""
    for v in list(_LIVE):
        try:
            if v.frame.winfo_exists():
                v.reload()
        except Exception:
            pass


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ── the POS window and its restaurant strip ──────────────────
def pos_bar(widget):
    """The POS (opened when it is not open yet) → its restaurant strip."""
    from modules import permissions as perm
    if not perm.allowed("pos", "view", parent=widget):
        return None
    from ui import close_guard
    from ui.pos import POSWindow
    root = widget._root()
    pos = close_guard.single("pos", lambda: POSWindow(root))
    bar = getattr(pos, "_rest", None)
    if bar is None:
        messagebox.showwarning("POS", "The POS could not open the restaurant order.", parent=widget)
    return bar


def open_pos_bar():
    """The restaurant strip of the POS when the POS is open, else None."""
    try:
        from ui import close_guard
        win = close_guard._singles.get("pos")
        if win is not None and win.winfo_exists():
            obj = getattr(win, "_daybill_single_obj", None)
            return getattr(obj, "_rest", None)
    except Exception:
        pass
    return None


def _release(order_ids):
    """The POS shows one of these orders: save it and clear the POS first."""
    bar = open_pos_bar()
    if bar is not None and bar.order_id() in set(int(x) for x in order_ids if x):
        return bar.leave()
    return True


# ── small windows ────────────────────────────────────────────
def form_dialog(parent, title, fields, on_change=None, ok_text="OK", note=""):
    """A small form. fields: [dict(key, label, kind, value, values, width)]
    kind: entry | int | money | combo | combo_ro | check. → {key: value} or None."""
    C = cfg.theme()
    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=C["card_bg"])
    top.resizable(False, False)
    try:
        top.transient(parent.winfo_toplevel())
    except Exception:
        pass
    tk.Label(top, text=title, font=("Segoe UI", 12, "bold"), bg=C["primary"], fg="white",
             anchor="w", padx=14, pady=8).pack(fill="x")
    body = tk.Frame(top, bg=C["card_bg"])
    body.pack(fill="both", padx=16, pady=10)
    vars_, widgets = {}, {}
    for i, fd in enumerate(fields):
        kind = fd.get("kind", "entry")
        tk.Label(body, text=fd["label"], font=("Segoe UI", 10), bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=4)
        if kind == "check":
            v = tk.BooleanVar(value=bool(fd.get("value")))
            w = tk.Checkbutton(body, variable=v, bg=C["card_bg"], activebackground=C["card_bg"])
        else:
            v = tk.StringVar(value="" if fd.get("value") is None else str(fd.get("value")))
            if kind in ("combo", "combo_ro"):
                w = ttk.Combobox(body, textvariable=v, values=list(fd.get("values") or []),
                                 width=fd.get("width", 30), font=("Segoe UI", 11),
                                 state="readonly" if kind == "combo_ro" else "normal")
            else:
                w = tk.Entry(body, textvariable=v, width=fd.get("width", 32), font=("Segoe UI", 11),
                             relief="solid", bd=1)
        w.grid(row=i, column=1, sticky="w", pady=4)
        vars_[fd["key"]], widgets[fd["key"]] = v, w
        if on_change is not None and kind != "check":
            v.trace_add("write", lambda *a, k=fd["key"]: on_change(k, vars_))
    if note:
        tk.Label(body, text=note, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                 justify="left", wraplength=420).grid(row=len(fields), column=0, columnspan=2,
                                                      sticky="w", pady=(6, 0))
    res = {}
    err = tk.StringVar()
    tk.Label(top, textvariable=err, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
             fg=C["danger"]).pack(fill="x", padx=16)

    def ok(_e=None):
        out = {}
        for fd in fields:
            kind = fd.get("kind", "entry")
            v = vars_[fd["key"]].get()
            if kind == "int":
                try:
                    v = int(float(str(v).strip() or 0))
                except ValueError:
                    err.set("%s: type a whole number." % fd["label"])
                    return
            elif kind == "money":
                try:
                    v = float(str(v).replace(",", "").strip() or 0)
                except ValueError:
                    err.set("%s: type a number." % fd["label"])
                    return
            elif kind != "check":
                v = str(v).strip()
            if fd.get("required") and v in ("", None):
                err.set("Please fill in: %s" % fd["label"])
                return
            out[fd["key"]] = v
        res["v"] = out
        top.destroy()
    bar = tk.Frame(top, bg=C["card_bg"])
    bar.pack(fill="x", padx=16, pady=(4, 12))
    tk.Button(bar, text="Cancel", font=("Segoe UI", 10), relief="flat", padx=14, pady=6,
              bg=C["content_bg"], command=top.destroy).pack(side="left")
    tk.Button(bar, text=ok_text, font=("Segoe UI", 10, "bold"), relief="flat", padx=18, pady=6,
              bg=C["primary"], fg="white", command=ok).pack(side="right")
    top.bind("<Return>", ok)
    top.bind("<Escape>", lambda e: top.destroy())
    form_dialog.last = top
    if fields:
        try:
            widgets[fields[0]["key"]].focus_set()
        except Exception:
            pass
    try:
        top.grab_set()
    except Exception:
        pass
    top.wait_window()
    return res.get("v")


def ask_start_table(parent, trow):
    got = form_dialog(parent, "New order · Table %s" % trow.get("table_name", ""), [
        dict(key="guests", label="Guests", kind="int", value=min(2, int(trow.get("seats") or 2)), width=8),
        dict(key="waiter", label="Waiter", kind="combo", values=R.waiters())], ok_text="Start order")
    if got is None:
        return None
    return got["guests"] or None, got["waiter"] or None


def ask_delivery(parent, order=None):
    """Delivery details. The phone fills the name and address of a
    customer we delivered to before. → open_order() fields or None."""
    o = order or {}

    def look(key, vs):
        if key != "phone":
            return
        hit = R.delivery_lookup(vs["phone"].get())
        if hit:
            if not vs["customer_name"].get().strip():
                vs["customer_name"].set(hit.get("customer_name") or "")
            if not vs["address"].get().strip():
                vs["address"].set(hit.get("address") or "")
    got = form_dialog(parent, "Delivery order", [
        dict(key="phone", label="Phone", value=o.get("customer_phone"), width=20),
        dict(key="customer_name", label="Customer name", value=o.get("customer_name"), required=True),
        dict(key="address", label="Address", value=o.get("delivery_address"), width=44),
        dict(key="driver", label="Driver", kind="combo", value=o.get("driver_name"), values=R.waiters())],
        on_change=look, ok_text="Save",
        note="Type the phone first: a customer we delivered to before is filled in.")
    return got


def ask_details(parent, o):
    """✎ the order's guests, waiter and customer. → update_order() fields."""
    t = o.get("order_type")
    f = []
    if t == "Dine-in":
        f.append(dict(key="guests", label="Guests", kind="int", value=o.get("guests") or "", width=8))
    f.append(dict(key="waiter_name", label="Waiter", kind="combo", value=o.get("waiter_name"),
                  values=R.waiters()))
    f.append(dict(key="customer_phone", label="Phone", value=o.get("customer_phone"), width=20))
    f.append(dict(key="customer_name", label="Customer name", value=o.get("customer_name")))
    if t == "Delivery":
        f.append(dict(key="delivery_address", label="Address", value=o.get("delivery_address"), width=44))
        f.append(dict(key="driver_name", label="Driver", kind="combo", value=o.get("driver_name"),
                      values=R.waiters()))
    f.append(dict(key="notes", label="Order note", value=o.get("notes"), width=44))
    return form_dialog(parent, "Order #%s · %s" % (o.get("order_no"), t), f, ok_text="Save")


def ask_note(parent, current, qty, choices, item=""):
    """Kitchen note for a line. → (text, how many) or None."""
    C = cfg.theme()
    top = tk.Toplevel(parent)
    top.title("Kitchen note")
    top.configure(bg=C["card_bg"])
    top.resizable(False, False)
    try:
        top.transient(parent.winfo_toplevel())
    except Exception:
        pass
    tk.Label(top, text="📝  Note for the kitchen — %s" % item, font=("Segoe UI", 12, "bold"),
             bg=C["primary"], fg="white", anchor="w", padx=14, pady=8).pack(fill="x")
    v = tk.StringVar(value=current or "")
    e = tk.Entry(top, textvariable=v, font=("Segoe UI", 14), width=36, relief="solid", bd=1)
    e.pack(padx=16, pady=(12, 6), ipady=4)
    grid = tk.Frame(top, bg=C["card_bg"])
    grid.pack(padx=16, pady=4)

    def add(txt):
        cur = v.get().strip()
        parts = [p.strip() for p in cur.split(",") if p.strip()]
        if txt not in parts:
            parts.append(txt)
        v.set(", ".join(parts))
        e.icursor("end")
    for i, ch in enumerate(choices):
        tk.Button(grid, text=ch, font=("Segoe UI", 10, "bold"), bg="#EAF2F8", relief="flat", padx=8,
                  cursor="hand2", command=lambda c=ch: add(c)).grid(row=i // 4, column=i % 4,
                                                                     sticky="ew", padx=3, pady=3, ipady=4)
    cnt = tk.StringVar(value=("%g" % qty))
    whole = abs(qty - round(qty)) < 1e-9 and qty > 1
    if whole:
        row = tk.Frame(top, bg=C["card_bg"])
        row.pack(fill="x", padx=16, pady=(6, 0))
        tk.Label(row, text="For how many of the %g?" % qty, font=("Segoe UI", 10), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        tk.Spinbox(row, from_=1, to=int(qty), textvariable=cnt, width=5,
                   font=("Segoe UI", 11)).pack(side="left", padx=8)
    res = {}

    def ok(_e=None):
        n = None
        if whole:
            try:
                n = max(1, min(int(float(cnt.get())), int(qty)))
            except ValueError:
                n = None
        res["v"] = (v.get().strip(), n)
        top.destroy()
    bar = tk.Frame(top, bg=C["card_bg"])
    bar.pack(fill="x", padx=16, pady=12)
    tk.Button(bar, text="Cancel", font=("Segoe UI", 10), relief="flat", padx=14, pady=6,
              bg=C["content_bg"], command=top.destroy).pack(side="left")
    tk.Button(bar, text="Clear note", font=("Segoe UI", 10), relief="flat", padx=14, pady=6,
              bg=C["content_bg"], command=lambda: v.set("")).pack(side="left", padx=6)
    tk.Button(bar, text="Save note", font=("Segoe UI", 10, "bold"), relief="flat", padx=18, pady=6,
              bg=C["primary"], fg="white", command=ok).pack(side="right")
    top.bind("<Return>", ok)
    top.bind("<Escape>", lambda ev: top.destroy())
    e.focus_set()
    try:
        top.grab_set()
    except Exception:
        pass
    top.wait_window()
    return res.get("v")


# ── a scrolling area of tiles ────────────────────────────────
class Flow:
    """Tiles in rows (as many as fit the width), in sections."""

    def __init__(self, parent, bg, tile_w=160):
        self.bg, self.tile_w = bg, tile_w
        wrap = tk.Frame(parent, bg=bg)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=bg, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<Enter>", lambda e: self._wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._wheel(False))
        self.sections = []
        self._cols_now = 0

    def _wheel(self, on):
        try:
            if on:
                self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(
                    int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units"))
                self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
                self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
            else:
                for s in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    self.canvas.unbind_all(s)
        except Exception:
            pass

    def cols(self):
        w = self.canvas.winfo_width()
        if w < 50:
            w = 900
        return max(1, (w - 16) // (self.tile_w + 10))

    def _resize(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)
        if self.cols() != self._cols_now:
            self.layout()

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.sections = []

    def section(self, title=None, fg="#333333"):
        if title:
            tk.Label(self.inner, text=title, font=("Segoe UI", 11, "bold"), bg=self.bg, fg=fg,
                     anchor="w").pack(fill="x", padx=8, pady=(10, 2))
        f = tk.Frame(self.inner, bg=self.bg)
        f.pack(fill="x", padx=4, anchor="w")
        self.sections.append((f, []))
        return f

    def add(self, tile):
        self.sections[-1][1].append(tile)

    def layout(self):
        n = self._cols_now = self.cols()
        for f, tiles in self.sections:
            for c in range(max(n, 1)):
                f.grid_columnconfigure(c, minsize=self.tile_w, uniform="t")
            for i, t in enumerate(tiles):
                t.grid(row=i // n, column=i % n, padx=5, pady=5, sticky="nsew")

    def message(self, text):
        self.clear()
        tk.Label(self.inner, text=text, font=("Segoe UI", 12), bg=self.bg, fg="#7F8C8D",
                 justify="center").pack(pady=60, padx=20)


def _bind_all(w, seq, fn):
    w.bind(seq, fn)
    for ch in w.winfo_children():
        _bind_all(ch, seq, fn)


def table_tile(parent, r, on_click, on_menu=None, free_only=False, big=True):
    """One table: name, guests, order no., waiter, total, minutes."""
    state = r.get("state") or "free"
    look = "off" if (free_only and state != "free") else state
    bg, border, fg = STATE_LOOK[look]
    t = tk.Frame(parent, bg=bg, highlightbackground=border, highlightthickness=2, cursor="hand2")
    top = tk.Frame(t, bg=bg)
    top.pack(fill="x", padx=8, pady=(6, 0))
    tk.Label(top, text=str(r.get("table_name")), font=("Segoe UI", 15 if big else 12, "bold"),
             bg=bg, fg=fg).pack(side="left")
    people = r.get("guests") if state != "free" else r.get("seats")
    if people:
        tk.Label(top, text="👥 %s" % people, font=("Segoe UI", 9), bg=bg, fg=fg).pack(side="right")
    if state == "free":
        tk.Label(t, text="Free · %s seats" % (r.get("seats") or ""), font=("Segoe UI", 9),
                 bg=bg, fg=fg).pack(anchor="w", padx=8, pady=(0, 8))
    else:
        sub = "#%s" % r.get("order_no")
        if r.get("waiter_name"):
            sub += " · %s" % r["waiter_name"]
        tk.Label(t, text=sub, font=("Segoe UI", 9), bg=bg, fg=fg).pack(anchor="w", padx=8)
        tk.Label(t, text=R.money(r.get("running_total")), font=("Segoe UI", 11, "bold"),
                 bg=bg, fg=fg).pack(anchor="w", padx=8)
        mins = int(r.get("minutes") or 0)
        tk.Label(t, text="⏱ %s" % _mins(mins) + ("   BILL PRINTED" if state == "billed" else ""),
                 font=("Segoe UI", 9, "bold" if state == "billed" or mins >= 90 else "normal"),
                 bg=bg, fg="#C0392B" if mins >= 90 and state != "billed" else fg).pack(
                     anchor="w", padx=8, pady=(0, 6))
    if not (free_only and state != "free"):
        _bind_all(t, "<Button-1>", lambda e, rr=r: on_click(rr))
    if on_menu is not None:
        _bind_all(t, "<Button-3>", lambda e, rr=r: on_menu(rr, e))
    return t


def _mins(m):
    m = int(m or 0)
    return "%d min" % m if m < 60 else "%d h %02d min" % (m // 60, m % 60)


def fill_board(flow, rows, on_click, on_menu=None, free_only=False, big=True):
    flow.clear()
    if not rows:
        flow.message("No tables yet.\nAdd them in Restaurant ▸ Restaurant Setup.")
        return
    area = object()
    for r in rows:
        if r.get("area_name") != area:
            area = r.get("area_name")
            flow.section(area or "Tables")
        flow.add(table_tile(flow.sections[-1][0], r, on_click, on_menu, free_only, big))
    flow.layout()


def pick_table(parent, free_only=True):
    """Pick a free table (then guests + waiter). → (table_id, guests,
    waiter) or None."""
    C = cfg.theme()
    top = tk.Toplevel(parent)
    top.title("Pick a table")
    top.configure(bg=C["content_bg"])
    top.geometry("820x540")
    try:
        top.transient(parent.winfo_toplevel())
    except Exception:
        pass
    tk.Label(top, text="Pick a free table", font=("Segoe UI", 12, "bold"), bg=C["primary"],
             fg="white", anchor="w", padx=14, pady=8).pack(fill="x")
    res = {}
    flow = Flow(top, C["content_bg"], 140)

    def click(r):
        got = ask_start_table(top, r)
        if got is None:
            return
        res["v"] = (r["table_id"], got[0], got[1])
        top.destroy()
    fill_board(flow, R.table_board(), click, free_only=free_only, big=False)
    tk.Button(top, text="Cancel", font=("Segoe UI", 10), relief="flat", padx=14, pady=6,
              command=top.destroy).pack(side="bottom", pady=8)
    top.bind("<Escape>", lambda e: top.destroy())
    pick_table.last = top
    try:
        top.grab_set()
    except Exception:
        pass
    top.wait_window()
    return res.get("v")


class TablePicker:
    """POS F12: the tables. A free table starts an order, a busy one
    opens it; New Takeaway / New Delivery / Running orders below."""

    def __init__(self, parent, bar):
        C = cfg.theme()
        self.bar = bar
        w = self.win = tk.Toplevel(parent)
        w.title("Tables")
        w.configure(bg=C["content_bg"])
        w.geometry("900x600")
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass
        tk.Label(w, text="🍽  Tables — tap a free table for a new order, a busy one to open it",
                 font=("Segoe UI", 12, "bold"), bg=C["primary"], fg="white", anchor="w",
                 padx=14, pady=8).pack(fill="x")
        foot = tk.Frame(w, bg=C["content_bg"])
        foot.pack(side="bottom", fill="x", padx=10, pady=8)
        for txt, cmd in (("＋ New Takeaway", self._takeaway), ("🛵 New Delivery", self._delivery),
                         ("📋 Running orders (F7)", self._running)):
            tk.Button(foot, text=txt, font=("Segoe UI", 11, "bold"), bg=C["primary"], fg="white",
                      relief="flat", padx=14, pady=6, cursor="hand2", command=cmd).pack(side="left", padx=4)
        tk.Button(foot, text="Close", font=("Segoe UI", 11), relief="flat", padx=14, pady=6,
                  command=w.destroy).pack(side="right")
        self.flow = Flow(w, C["content_bg"], 150)
        fill_board(self.flow, R.table_board(), self._click)
        w.bind("<Escape>", lambda e: w.destroy())

    def _click(self, r):
        if r.get("state") == "free":
            got = ask_start_table(self.win, r)
            if got is None:
                return
            self.win.destroy()
            self.bar.start_table(r["table_id"], got[0], got[1])
        else:
            self.win.destroy()
            self.bar.open_order(r["order_id"])

    def _takeaway(self):
        self.win.destroy()
        self.bar.start_order("Takeaway")

    def _delivery(self):
        d = ask_delivery(self.win)
        if d is None:
            return
        self.win.destroy()
        self.bar.start_order("Delivery", **d)

    def _running(self):
        self.win.destroy()
        RunningOrders(self.bar.pos.win, self.bar)


ORDER_COLS = (("no", "#", 50, "center"), ("type", "Type", 80, "w"), ("table", "Table", 70, "w"),
              ("who", "Customer / waiter", 200, "w"), ("total", "Total", 100, "e"),
              ("mins", "Open", 80, "e"), ("status", "Status", 100, "w"))


def _order_values(o):
    who = " · ".join(x for x in (o.get("customer_name"), o.get("customer_phone"),
                                 o.get("waiter_name")) if x)
    return ("#%s" % o["order_no"], o.get("order_type") or "", o.get("table_name") or "", who,
            R.money(o.get("running_total"), sym=False), _mins(o.get("minutes")),
            R.STATUS_LABEL.get(o.get("status"), o.get("status")))


def _order_tree(parent, height=12):
    tv = ttk.Treeview(parent, columns=[c[0] for c in ORDER_COLS], show="headings", height=height)
    for k, h, w, a in ORDER_COLS:
        tv.heading(k, text=h)
        tv.column(k, width=w, anchor=a, stretch=(k == "who"))
    return tv


class RunningOrders:
    """POS F7: every order not paid yet."""

    def __init__(self, parent, bar):
        C = cfg.theme()
        self.bar = bar
        w = self.win = tk.Toplevel(parent)
        w.title("Running orders")
        w.configure(bg=C["content_bg"])
        w.geometry("760x460")
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass
        tk.Label(w, text="📋  Running orders (not paid yet)", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white", anchor="w", padx=14, pady=8).pack(fill="x")
        foot = tk.Frame(w, bg=C["content_bg"])
        foot.pack(side="bottom", fill="x", padx=10, pady=8)
        tk.Button(foot, text="Open in POS", font=("Segoe UI", 11, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=16, pady=6, command=self._open).pack(side="left")
        tk.Button(foot, text="🍽 Tables", font=("Segoe UI", 11), relief="flat", padx=14, pady=6,
                  command=self._tables).pack(side="left", padx=6)
        tk.Button(foot, text="Close", font=("Segoe UI", 11), relief="flat", padx=14, pady=6,
                  command=w.destroy).pack(side="right")
        self.tree = _order_tree(w, 14)
        self.tree.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        for o in R.running(dine_in=True):
            self.tree.insert("", "end", iid=str(o["order_id"]), values=_order_values(o))
        kids = self.tree.get_children()
        if kids:
            self.tree.selection_set(kids[0])
            self.tree.focus(kids[0])
        self.tree.bind("<Double-1>", lambda e: self._open())
        self.tree.bind("<Return>", lambda e: self._open())
        w.bind("<Escape>", lambda e: w.destroy())
        self.tree.focus_set()

    def _open(self):
        s = self.tree.selection()
        if not s:
            return
        self.win.destroy()
        self.bar.open_order(int(s[0]))

    def _tables(self):
        self.win.destroy()
        TablePicker(self.bar.pos.win, self.bar)


def _print_kots(ids):
    if ids and R.flag("rest_kot_print"):
        for k in ids:
            try:
                R.print_kot(k)
            except Exception:
                pass


def cancel_order(parent, o):
    """Ask, then cancel a running order (CANCEL ticket for the kitchen)."""
    reason = simpledialog.askstring(
        "Cancel order", "Cancel order %s?\nItems already sent to the kitchen get a CANCEL ticket.\n\n"
        "Why (optional):" % R.summary(o, short=True), parent=parent)
    if reason is None:
        return False
    bar = open_pos_bar()
    if bar is not None and bar.order_id() == o["order_id"]:
        return bar.delete_bill(ask=False, reason=reason or "Cancelled")
    try:
        _print_kots(R.cancel(o["order_id"], reason or "Cancelled"))
    except (R.OrderClosed, ValueError) as e:
        messagebox.showwarning("Cancel order", str(e), parent=parent)
        return False
    changed()
    return True


# ════════════════════════════════════════════════════════════
#  Tables & Orders
# ════════════════════════════════════════════════════════════
class TablesView:
    REFRESH_MS = 20000

    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(top, text="🍽  Tables & Orders", font=("Segoe UI", 16, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Label(top, text="  tap a free table for a new order, a busy one to open it in the POS · "
                      "right-click for more", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=20, pady=(2, 6))
        for txt, cmd, primary in (("＋  New Takeaway", self.new_takeaway, True),
                                  ("🛵  New Delivery", self.new_delivery, True),
                                  ("⇄  Transfer table", self.transfer, False),
                                  ("⧉  Merge tables", self.merge, False),
                                  ("↻  Refresh", self.reload, False)):
            tk.Button(bar, text=txt, font=("Segoe UI", 10, "bold"),
                      bg=C["primary"] if primary else C["card_bg"],
                      fg="white" if primary else C["text_primary"], relief="flat",
                      padx=12, pady=5, cursor="hand2", command=cmd).pack(side="left", padx=(0, 6))
        leg = tk.Frame(bar, bg=C["content_bg"])
        leg.pack(side="right")
        for st in ("free", "occupied", "billed"):
            bg, border, fg = STATE_LOOK[st]
            tk.Label(leg, text="  %s  " % STATE_NAME[st], font=("Segoe UI", 9, "bold"), bg=bg, fg=fg,
                     highlightbackground=border, highlightthickness=1).pack(side="left", padx=3)
        self.sum_var = tk.StringVar()
        tk.Label(self.frame, textvariable=self.sum_var, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"], anchor="w").pack(fill="x", padx=20)
        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=20, pady=(4, 14))
        side = tk.Frame(body, bg=C["card_bg"], width=420, highlightbackground=C["border"],
                        highlightthickness=1)
        side.pack(side="right", fill="y", padx=(10, 0))
        side.pack_propagate(False)
        tk.Label(side, text="🛵  Takeaway & Delivery", font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"], anchor="w").pack(fill="x", padx=10, pady=(8, 4))
        sb = tk.Frame(side, bg=C["card_bg"])
        sb.pack(side="bottom", fill="x", padx=10, pady=8)
        tk.Button(sb, text="Open in POS", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=10, pady=4, command=self._open_selected).pack(side="left")
        tk.Button(sb, text="Cancel order", font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
                  bg=C["content_bg"], command=self._cancel_selected).pack(side="right")
        self.tree = _order_tree(side, 10)
        self.tree["displaycolumns"] = ("no", "type", "who", "total", "mins", "status")
        for k, w in (("no", 40), ("type", 72), ("who", 95), ("total", 70), ("mins", 55), ("status", 70)):
            self.tree.column(k, width=w, minwidth=30, stretch=(k == "who"))
        self.tree.pack(fill="both", expand=True, padx=10)
        self.tree.bind("<Double-1>", lambda e: self._open_selected())
        left = tk.Frame(body, bg=C["content_bg"])
        left.pack(side="left", fill="both", expand=True)
        self.flow = Flow(left, C["content_bg"], 150)
        self.frame.refresh = self.reload
        self.frame.new_record = self.new_takeaway
        _LIVE.add(self)
        if not R.ready():
            self.flow.message("The restaurant tables are not in this database yet.\n"
                              "Close DayBill and open it again to update the database.")
            return
        self.reload()
        self.frame.after(self.REFRESH_MS, self._auto)

    def _auto(self):
        try:
            if not self.frame.winfo_exists():
                return
            if self.frame.winfo_ismapped():
                self.reload()
            self.frame.after(self.REFRESH_MS, self._auto)
        except Exception:
            pass

    def reload(self):
        rows = R.table_board()
        self.rows = rows
        fill_board(self.flow, rows, self._click, self._menu)
        self.tree.delete(*self.tree.get_children())
        others = R.running(dine_in=False)
        for o in others:
            self.tree.insert("", "end", iid=str(o["order_id"]), values=_order_values(o))
        n = {s: sum(1 for r in rows if r["state"] == s) for s in STATE_NAME}
        tot = sum(_f(r.get("running_total")) for r in rows if r.get("order_id")) + \
            sum(_f(o.get("running_total")) for o in others)
        self.sum_var.set("%d free · %d occupied · %d bill printed · %d takeaway / delivery · "
                         "open orders %s" % (n["free"], n["occupied"], n["billed"], len(others),
                                             R.money(tot)))

    # actions
    def _click(self, r):
        if r.get("state") == "free":
            got = ask_start_table(self.frame, r)
            if got is None:
                return
            bar = pos_bar(self.frame)
            if bar is not None:
                bar.start_table(r["table_id"], got[0], got[1])
        else:
            bar = pos_bar(self.frame)
            if bar is not None:
                bar.open_order(r["order_id"])
        self.reload()

    def _menu(self, r, event):
        m = tk.Menu(self.frame, tearoff=0, font=("Segoe UI", 10))
        if r.get("state") == "free":
            m.add_command(label="Start an order", command=lambda: self._click(r))
        else:
            o = R.get_order(r["order_id"]) or {}
            m.add_command(label="Open in POS", command=lambda: self._click(r))
            m.add_command(label="Print the bill", command=lambda: self._print_bill(r["order_id"]))
            m.add_command(label="Move to another table…", command=lambda: self.transfer(r["order_id"]))
            m.add_command(label="Merge into another table…", command=lambda: self.merge(r["order_id"]))
            m.add_separator()
            m.add_command(label="Cancel order…", command=lambda: cancel_order(self.frame, o) and self.reload())
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _print_bill(self, order_id):
        bar = pos_bar(self.frame)
        if bar is not None and bar.open_order(order_id):
            bar.print_bill()
        self.reload()

    def _sel_order(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _open_selected(self):
        oid = self._sel_order()
        if not oid:
            return
        bar = pos_bar(self.frame)
        if bar is not None:
            bar.open_order(oid)
        self.reload()

    def _cancel_selected(self):
        oid = self._sel_order()
        if oid and cancel_order(self.frame, R.get_order(oid) or {"order_id": oid}):
            self.reload()

    def new_takeaway(self):
        bar = pos_bar(self.frame)
        if bar is not None:
            bar.start_order("Takeaway")
        self.reload()

    def new_delivery(self):
        d = ask_delivery(self.frame)
        if d is None:
            return
        bar = pos_bar(self.frame)
        if bar is not None:
            bar.start_order("Delivery", **d)
        self.reload()

    @staticmethod
    def _label(r):
        return "%s  —  #%s%s  %s" % (r["table_name"], r.get("order_no"),
                                    (" · %s" % r["waiter_name"]) if r.get("waiter_name") else "",
                                    R.money(r.get("running_total")))

    def transfer(self, order_id=None, to_table_id=None):
        """Move a table's order to a free table."""
        rows = R.table_board()
        busy = [r for r in rows if r.get("order_id")]
        free = [r for r in rows if r["state"] == "free"]
        if order_id and to_table_id:
            got = {"src": order_id, "dst": to_table_id}
        else:
            if not busy or not free:
                messagebox.showinfo("Transfer table", "You need a table with an order and a free table.",
                                    parent=self.frame)
                return False
            sl = [self._label(r) for r in busy]
            dl = [r["table_name"] + ("  (%s)" % r["area_name"] if r.get("area_name") else "") for r in free]
            pre = next((self._label(r) for r in busy if r["order_id"] == order_id), sl[0])
            g = form_dialog(self.frame, "Transfer table", [
                dict(key="src", label="Move the order of", kind="combo_ro", values=sl, value=pre, width=40),
                dict(key="dst", label="To the free table", kind="combo_ro", values=dl, value=dl[0], width=40)],
                ok_text="Move")
            if not g:
                return False
            got = {"src": busy[sl.index(g["src"])]["order_id"], "dst": free[dl.index(g["dst"])]["table_id"]}
        if not _release([got["src"]]):
            return False
        try:
            R.transfer(got["src"], got["dst"])
        except (ValueError, R.OrderClosed) as e:
            messagebox.showwarning("Transfer table", str(e), parent=self.frame)
            return False
        self.reload()
        return True

    def merge(self, order_id=None, into_order_id=None):
        """Two tables, one bill: the first table's items move to the second."""
        busy = [r for r in R.table_board() if r.get("order_id")]
        if order_id and into_order_id:
            got = {"src": order_id, "dst": into_order_id}
        else:
            if len(busy) < 2:
                messagebox.showinfo("Merge tables", "You need two tables with an order.", parent=self.frame)
                return False
            sl = [self._label(r) for r in busy]
            pre = next((self._label(r) for r in busy if r["order_id"] == order_id), sl[0])
            g = form_dialog(self.frame, "Merge tables", [
                dict(key="src", label="Move the items of", kind="combo_ro", values=sl, value=pre, width=40),
                dict(key="dst", label="Into the order of", kind="combo_ro", values=sl,
                     value=next(x for x in sl if x != pre), width=40)], ok_text="Merge",
                note="The first table becomes free; the kitchen tickets go with the items.")
            if not g:
                return False
            if g["src"] == g["dst"]:
                messagebox.showwarning("Merge tables", "Pick two different tables.", parent=self.frame)
                return False
            got = {"src": busy[sl.index(g["src"])]["order_id"], "dst": busy[sl.index(g["dst"])]["order_id"]}
        if not _release([got["src"], got["dst"]]):
            return False
        try:
            R.merge(got["src"], got["dst"])
        except (ValueError, R.OrderClosed) as e:
            messagebox.showwarning("Merge tables", str(e), parent=self.frame)
            return False
        self.reload()
        return True


# ════════════════════════════════════════════════════════════
#  Kitchen Orders (KOT) — the kitchen screen
# ════════════════════════════════════════════════════════════
class KotView:
    REFRESH_MS = 15000
    SHOW = (("Waiting (new, preparing, ready)", ("new", "preparing", "ready"), False),
            ("New only", ("new",), False), ("Preparing", ("preparing",), False),
            ("Ready", ("ready",), False), ("Served today", ("served",), True),
            ("All of today", R.KOT_FLOW, True))

    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(top, text="🧾  Kitchen Orders (KOT)", font=("Segoe UI", 16, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Label(top, text="  tap the button on a ticket when it moves on: start → ready → served",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"]).pack(side="left")
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=20, pady=(2, 6))
        tk.Label(bar, text="Station", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.stations = [(None, "All stations")] + [(s["station_id"], s["station_name"])
                                                    for s in R.stations()]
        self.st_var = tk.StringVar(value=self.stations[0][1])
        cb = ttk.Combobox(bar, textvariable=self.st_var, state="readonly", width=18,
                          values=[n for _i, n in self.stations], font=("Segoe UI", 10))
        cb.pack(side="left", padx=(4, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self.reload())
        tk.Label(bar, text="Show", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.show_var = tk.StringVar(value=self.SHOW[0][0])
        cb2 = ttk.Combobox(bar, textvariable=self.show_var, state="readonly", width=28,
                           values=[s[0] for s in self.SHOW], font=("Segoe UI", 10))
        cb2.pack(side="left", padx=(4, 12))
        cb2.bind("<<ComboboxSelected>>", lambda e: self.reload())
        tk.Button(bar, text="↻  Refresh", font=("Segoe UI", 10, "bold"), bg=C["card_bg"], relief="flat",
                  padx=12, pady=4, cursor="hand2", command=self.reload).pack(side="left")
        self.sum_var = tk.StringVar()
        tk.Label(bar, textvariable=self.sum_var, font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="right")
        self.flow = Flow(self.frame, "#1C2833", 290)
        self.frame.refresh = self.reload
        _LIVE.add(self)
        if not R.ready():
            self.flow.message("The restaurant tables are not in this database yet.")
            return
        self.reload()
        self.frame.after(self.REFRESH_MS, self._auto)

    def _auto(self):
        try:
            if not self.frame.winfo_exists():
                return
            if self.frame.winfo_ismapped():
                self.reload()
            self.frame.after(self.REFRESH_MS, self._auto)
        except Exception:
            pass

    def _filter(self):
        sid = next((i for i, n in self.stations if n == self.st_var.get()), None)
        show = next((s for s in self.SHOW if s[0] == self.show_var.get()), self.SHOW[0])
        return sid, show[1], show[2]

    def reload(self):
        sid, statuses, today = self._filter()
        rows = R.kots(statuses, sid, today_only=today)
        self.rows = rows
        self.flow.clear()
        if not rows:
            self.flow.message("No kitchen tickets here. 👍")
            self.sum_var.set("")
            return
        self.flow.section()
        for k in rows:
            self.flow.add(self._tile(self.flow.sections[-1][0], k))
        self.flow.layout()
        n = {s: sum(1 for k in rows if k["status"] == s) for s in R.KOT_FLOW}
        self.sum_var.set("%d new · %d preparing · %d ready" % (n["new"], n["preparing"], n["ready"]))

    def _tile(self, parent, k):
        st = k.get("status") or "new"
        head = KOT_LOOK.get(st, "#7F8C8D")
        t = tk.Frame(parent, bg="white", highlightbackground=head, highlightthickness=3)
        h = tk.Frame(t, bg=head)
        h.pack(fill="x")
        tk.Label(h, text="KOT %s" % k["kot_no"], font=("Segoe UI", 15, "bold"), bg=head,
                 fg="white").pack(side="left", padx=8, pady=4)
        mins = int(k.get("minutes") or 0)
        tk.Label(h, text="⏱ %s" % _mins(mins), font=("Segoe UI", 12, "bold"), bg=head,
                 fg="#FDEBD0" if mins >= 15 and st != "served" else "white").pack(side="right", padx=8)
        tk.Label(t, text=R.kot_head(k), font=("Segoe UI", 15, "bold"), bg="white", fg="#17202A",
                 anchor="w").pack(fill="x", padx=8, pady=(4, 0))
        sub = "%s #%s · %s" % (k.get("order_type") or "", k.get("order_no"), k.get("station_name") or "")
        if k.get("waiter_name"):
            sub += " · %s" % k["waiter_name"]
        tk.Label(t, text=sub, font=("Segoe UI", 9), bg="white", fg="#566573", anchor="w").pack(fill="x", padx=8)
        if k.get("kot_note"):
            tk.Label(t, text=k["kot_note"], font=("Segoe UI", 11, "bold"), bg="white",
                     fg="#C0392B", anchor="w").pack(fill="x", padx=8)
        ttk.Separator(t).pack(fill="x", padx=6, pady=4)
        for ln in k.get("lines") or []:
            q = _f(ln.get("quantity"))
            name = "%s × %s" % (R._qty(q), ln.get("product_name") or "")
            if q < 0:
                tk.Label(t, text="CANCEL  " + name, font=("Segoe UI", 13, "bold overstrike"), bg="white",
                         fg="#C0392B", anchor="w", wraplength=270, justify="left").pack(fill="x", padx=8)
            else:
                tk.Label(t, text=name, font=("Segoe UI", 13, "bold"), bg="white", fg="#17202A",
                         anchor="w", wraplength=270, justify="left").pack(fill="x", padx=8)
            if ln.get("kitchen_note"):
                tk.Label(t, text="   * " + ln["kitchen_note"], font=("Segoe UI", 11, "italic"),
                         bg="white", fg="#AF601A", anchor="w", wraplength=260,
                         justify="left").pack(fill="x", padx=8)
        foot = tk.Frame(t, bg="white")
        foot.pack(fill="x", side="bottom", padx=6, pady=6)
        if st != "served":
            txt = "✓  Seen" if R.is_cancel_only(k) else KOT_NEXT.get(st, "Next")
            tk.Button(foot, text=txt, font=("Segoe UI", 12, "bold"), bg=head, fg="white", relief="flat",
                      cursor="hand2", command=lambda kid=k["kot_id"]: self.bump(kid)).pack(
                          side="left", fill="x", expand=True, ipady=4)
        else:
            tk.Label(foot, text="Served", font=("Segoe UI", 10, "bold"), bg="white",
                     fg="#7F8C8D").pack(side="left")
        tk.Button(foot, text="🖨", font=("Segoe UI Emoji", 12), bg="#EAEDED", relief="flat", cursor="hand2",
                  command=lambda kid=k["kot_id"]: self.reprint(kid)).pack(side="right", padx=(6, 0), ipady=2)
        return t

    def bump(self, kot_id):
        R.bump(kot_id)
        self.reload()

    def reprint(self, kot_id):
        ok, msg = R.print_kot(kot_id)
        if not ok:
            messagebox.showwarning("Reprint", msg, parent=self.frame)
        self.reload()


# ════════════════════════════════════════════════════════════
#  Restaurant Setup
# ════════════════════════════════════════════════════════════
NO_AREA = "(no area)"
NOT_SENT = "Not sent to the kitchen"


class RestaurantSetupView:
    def __init__(self, parent):
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(top, text="⚙  Restaurant Setup", font=("Segoe UI", 16, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Label(top, text="  areas and tables · kitchen stations and printers · order types and "
                      "service charge", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        if not R.ready():
            tk.Label(self.frame, text="The restaurant tables are not in this database yet.\n"
                     "Close DayBill and open it again to update the database.", font=("Segoe UI", 12),
                     bg=C["content_bg"], fg=C["text_secondary"]).pack(pady=60)
            return
        self.nb = ttk.Notebook(self.frame)
        self.nb.pack(fill="both", expand=True, padx=20, pady=(4, 14))
        self._tab_tables()
        self._tab_kitchen()
        self._tab_options()
        self.frame.refresh = self.reload

    def reload(self):
        self._load_areas()
        self._load_tables()
        self._load_stations()
        self._load_cats()

    # helpers
    def _page(self, title):
        f = tk.Frame(self.nb, bg=self.C["card_bg"])
        self.nb.add(f, text="  %s  " % title)
        return f

    def _btns(self, parent, items):
        b = tk.Frame(parent, bg=self.C["card_bg"])
        b.pack(fill="x", pady=(6, 0))
        for txt, cmd in items:
            tk.Button(b, text=txt, font=("Segoe UI", 9, "bold"), bg=self.C["primary"] if txt.startswith("＋")
                      else self.C["content_bg"], fg="white" if txt.startswith("＋") else self.C["text_primary"],
                      relief="flat", padx=10, pady=4, cursor="hand2", command=cmd).pack(side="left", padx=(0, 6))
        return b

    def _tree(self, parent, cols, height=12, mode="browse"):
        tv = ttk.Treeview(parent, columns=[c[0] for c in cols], show="headings", height=height,
                          selectmode=mode)
        for k, h, w in cols:
            tv.heading(k, text=h)
            tv.column(k, width=w, anchor="w")
        tv.pack(fill="both", expand=True)
        return tv

    def _err(self, e):
        messagebox.showwarning("Restaurant Setup", str(e), parent=self.frame)

    # ── areas & tables ───────────────────────────────────────
    def _tab_tables(self):
        C = self.C
        p = self._page("Areas & Tables")
        left = tk.Frame(p, bg=C["card_bg"], width=300)
        left.pack(side="left", fill="y", padx=(12, 6), pady=12)
        left.pack_propagate(False)
        tk.Label(left, text="Areas (Hall, Family, Terrace …)", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"], anchor="w").pack(fill="x")
        self.area_tv = self._tree(left, (("name", "Area", 170), ("n", "Tables", 60)), 14)
        self.area_tv.bind("<Double-1>", lambda e: self.edit_area())
        self._btns(left, (("＋ Add", self.add_area), ("✎ Rename", self.edit_area), ("🗑 Delete", self.delete_area)))
        right = tk.Frame(p, bg=C["card_bg"])
        right.pack(side="left", fill="both", expand=True, padx=(6, 12), pady=12)
        tk.Label(right, text="Tables", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"], anchor="w").pack(fill="x")
        self.table_tv = self._tree(right, (("name", "Table", 120), ("area", "Area", 140), ("seats", "Seats", 60),
                                           ("sort", "Order", 60), ("active", "In use", 70),
                                           ("now", "Now", 160)), 14)
        self.table_tv.bind("<Double-1>", lambda e: self.edit_table())
        self._btns(right, (("＋ Add table", self.add_table), ("＋ Add tables 1 – 20", self.add_many),
                           ("✎ Edit", self.edit_table), ("🗑 Delete", self.delete_table)))
        self._load_areas()
        self._load_tables()

    def _load_areas(self):
        self.areas = R.areas()
        cnt = {}
        for t in R.tables(active_only=True):
            cnt[t.get("area_id")] = cnt.get(t.get("area_id"), 0) + 1
        self.area_tv.delete(*self.area_tv.get_children())
        for a in self.areas:
            self.area_tv.insert("", "end", iid=str(a["area_id"]),
                                values=(a["area_name"] + ("" if a.get("is_active") else "  (off)"),
                                        cnt.get(a["area_id"], 0)))

    def _load_tables(self):
        board = {r["table_id"]: r for r in R.table_board()}
        self.table_tv.delete(*self.table_tv.get_children())
        for t in R.tables(active_only=False):
            b = board.get(t["table_id"]) or {}
            now = ("#%s · %s" % (b["order_no"], STATE_NAME.get(b["state"], "")) if b.get("order_id")
                   else ("Free" if t.get("is_active") else ""))
            self.table_tv.insert("", "end", iid=str(t["table_id"]), values=(
                t["table_name"], t.get("area_name") or "", t.get("seats"), t.get("sort_order"),
                "Yes" if t.get("is_active") else "No", now))

    def _area_names(self):
        return [NO_AREA] + [a["area_name"] for a in self.areas if a.get("is_active")]

    def _area_id(self, name):
        return next((a["area_id"] for a in self.areas if a["area_name"] == name), None)

    def add_area(self, name=None):
        if name is None:
            g = form_dialog(self.frame, "New area", [dict(key="name", label="Area name", required=True),
                                                     dict(key="sort", label="Order", kind="int", value=len(self.areas) + 1, width=6)])
            if not g:
                return None
            name, sort = g["name"], g["sort"]
        else:
            sort = len(self.areas) + 1
        try:
            aid = R.save_area(None, name, sort)
        except ValueError as e:
            return self._err(e)
        self._load_areas()
        return aid

    def edit_area(self):
        s = self.area_tv.selection()
        if not s:
            return
        a = next(x for x in self.areas if x["area_id"] == int(s[0]))
        g = form_dialog(self.frame, "Area", [dict(key="name", label="Area name", value=a["area_name"], required=True),
                                             dict(key="sort", label="Order", kind="int", value=a.get("sort_order"), width=6),
                                             dict(key="active", label="In use", kind="check", value=a.get("is_active"))])
        if not g:
            return
        try:
            R.save_area(a["area_id"], g["name"], g["sort"], g["active"])
        except ValueError as e:
            return self._err(e)
        self._load_areas()
        self._load_tables()

    def delete_area(self):
        s = self.area_tv.selection()
        if not s:
            return
        if not messagebox.askyesno("Delete area", "Delete this area?\nIts tables stay, without an area.",
                                   parent=self.frame):
            return
        R.delete_area(int(s[0]))
        self._load_areas()
        self._load_tables()

    def _table_form(self, title, t=None):
        t = t or {}
        return form_dialog(self.frame, title, [
            dict(key="name", label="Table name / number", value=t.get("table_name"), required=True, width=14),
            dict(key="area", label="Area", kind="combo_ro", values=self._area_names(),
                 value=t.get("area_name") or NO_AREA),
            dict(key="seats", label="Seats", kind="int", value=t.get("seats") or 4, width=6),
            dict(key="sort", label="Order", kind="int", value=t.get("sort_order") or 0, width=6),
            dict(key="active", label="In use", kind="check", value=t.get("is_active", True))])

    def add_table(self):
        g = self._table_form("New table")
        if not g:
            return
        try:
            R.save_table(None, g["name"], self._area_id(g["area"]), g["seats"], g["sort"], g["active"])
        except ValueError as e:
            return self._err(e)
        self._load_tables()
        self._load_areas()
        changed()

    def edit_table(self):
        s = self.table_tv.selection()
        if not s:
            return
        t = R.table(int(s[0]))
        g = self._table_form("Table %s" % t["table_name"], t)
        if not g:
            return
        try:
            R.save_table(t["table_id"], g["name"], self._area_id(g["area"]), g["seats"], g["sort"], g["active"])
        except ValueError as e:
            return self._err(e)
        self._load_tables()
        self._load_areas()
        changed()

    def delete_table(self):
        s = self.table_tv.selection()
        if not s:
            return
        if not messagebox.askyesno("Delete table", "Delete this table?", parent=self.frame):
            return
        try:
            how = R.delete_table(int(s[0]))
        except ValueError as e:
            return self._err(e)
        if how == "off":
            messagebox.showinfo("Delete table", "This table has old orders, so it is switched off "
                                "(not deleted). Reports still show it.", parent=self.frame)
        self._load_tables()
        self._load_areas()
        changed()

    def add_many(self, first=None, last=None, prefix="", area=None, seats=4):
        if first is None:
            g = form_dialog(self.frame, "Add many tables", [
                dict(key="first", label="From number", kind="int", value=1, width=6),
                dict(key="last", label="To number", kind="int", value=20, width=6),
                dict(key="prefix", label="Name before the number", value="", width=8),
                dict(key="area", label="Area", kind="combo_ro", values=self._area_names(), value=NO_AREA),
                dict(key="seats", label="Seats", kind="int", value=4, width=6)], ok_text="Add tables",
                note="Example: from 1 to 20 with 'T' before the number makes T1 … T20. "
                     "Tables that are already there are skipped.")
            if not g:
                return None
            first, last, prefix, area, seats = g["first"], g["last"], g["prefix"], g["area"], g["seats"]
        try:
            n = R.add_tables(first, last, prefix, self._area_id(area) if area else None, seats)
        except ValueError as e:
            return self._err(e)
        self._load_tables()
        self._load_areas()
        changed()
        return n

    # ── kitchen ──────────────────────────────────────────────
    def _printers(self):
        try:
            from modules import printer_service as ps
            return ps.list_printers() or []
        except Exception:
            return []

    def _tab_kitchen(self):
        C = self.C
        p = self._page("Kitchen & Printers")
        up = tk.Frame(p, bg=C["card_bg"])
        up.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(up, text="Kitchen stations — each prints its own ticket (KOT)", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"], anchor="w").pack(fill="x")
        self.st_tv = self._tree(up, (("name", "Station", 160), ("printer", "Printer", 260),
                                     ("paper", "Paper", 70), ("copies", "Copies", 60), ("sort", "Order", 60)), 5)
        self.st_tv.bind("<Double-1>", lambda e: self.edit_station())
        self._btns(up, (("＋ Add station", self.add_station), ("✎ Edit", self.edit_station),
                        ("🗑 Delete", self.delete_station)))
        mid = tk.Frame(p, bg=C["card_bg"])
        mid.pack(fill="x", padx=12, pady=8)
        tk.Label(mid, text="Default kitchen printer", font=("Segoe UI", 10), bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.kp_var = tk.StringVar(value=str(R.setting("rest_kitchen_printer") or ""))
        ttk.Combobox(mid, textvariable=self.kp_var, values=[""] + self._printers(), width=34,
                     font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w")
        tk.Label(mid, text="Paper", font=("Segoe UI", 10), bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=0, column=2, sticky="w", padx=(14, 6))
        self.kpaper_var = tk.StringVar(value="58 mm" if str(R.setting("rest_kot_paper")) == "58" else "80 mm")
        ttk.Combobox(mid, textvariable=self.kpaper_var, values=["80 mm", "58 mm"], state="readonly",
                     width=7).grid(row=0, column=3, sticky="w")
        self.kprint_var = tk.BooleanVar(value=R.flag("rest_kot_print"))
        tk.Checkbutton(mid, text="Print kitchen tickets (KOT)", variable=self.kprint_var, bg=C["card_bg"],
                       activebackground=C["card_bg"], font=("Segoe UI", 10)).grid(row=0, column=4, padx=14)
        tk.Button(mid, text="Save", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white", relief="flat",
                  padx=14, pady=3, command=self.save_kitchen).grid(row=0, column=5)
        tk.Label(mid, text="A station without its own printer prints on the default kitchen printer. "
                 "With no printer at all the ticket opens on the screen as a PDF.",
                 font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"]).grid(
                     row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))
        low = tk.Frame(p, bg=C["card_bg"])
        low.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        tk.Label(low, text="Which items go to which station (by product category)", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"], anchor="w").pack(fill="x")
        row = tk.Frame(low, bg=C["card_bg"])
        row.pack(side="bottom", fill="x", pady=(6, 0))
        tk.Label(row, text="Send the selected categories to", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.goto_var = tk.StringVar()
        self.goto_cb = ttk.Combobox(row, textvariable=self.goto_var, state="readonly", width=30)
        self.goto_cb.pack(side="left", padx=6)
        tk.Button(row, text="Set", font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white", relief="flat",
                  padx=12, command=self.set_categories).pack(side="left")
        self.cat_tv = self._tree(low, (("cat", "Category", 240), ("goes", "Goes to", 260)), 8, mode="extended")
        self._load_stations()
        self._load_cats()

    def _choices(self):
        d = R.default_station()
        out = [("default", "Default station (%s)" % d["station_name"])]
        out += [(s["station_id"], s["station_name"]) for s in R.stations()]
        out.append((None, NOT_SENT))
        return out

    def _load_stations(self):
        self.st_tv.delete(*self.st_tv.get_children())
        for s in R.stations(active_only=False):
            self.st_tv.insert("", "end", iid=str(s["station_id"]), values=(
                s["station_name"] + ("" if s.get("is_active") else "  (off)"),
                s.get("printer_name") or "(default kitchen printer)", "%s mm" % s.get("paper_mm"),
                s.get("copies"), s.get("sort_order")))
        ch = self._choices()
        self.goto_cb.configure(values=[n for _k, n in ch])
        if not self.goto_var.get():
            self.goto_var.set(ch[0][1])

    def _load_cats(self):
        cmap = R.category_map()
        by = {s["station_id"]: s["station_name"] for s in R.stations(active_only=False)}
        d = R.default_station()["station_name"]
        self.cat_tv.delete(*self.cat_tv.get_children())
        for c in R.categories():
            cid = c["category_id"]
            if cid in cmap:
                goes = NOT_SENT if cmap[cid] is None else by.get(cmap[cid], d)
            else:
                goes = "Default station (%s)" % d
            self.cat_tv.insert("", "end", iid=str(cid), values=(c["category_name_en"], goes))

    def _station_form(self, title, s=None):
        s = s or {}
        return form_dialog(self.frame, title, [
            dict(key="name", label="Station name", value=s.get("station_name"), required=True),
            dict(key="printer", label="Printer", kind="combo", values=[""] + self._printers(),
                 value=s.get("printer_name") or "", width=34),
            dict(key="paper", label="Paper", kind="combo_ro", values=["80 mm", "58 mm"],
                 value="58 mm" if int(s.get("paper_mm") or 80) == 58 else "80 mm", width=8),
            dict(key="copies", label="Copies", kind="int", value=s.get("copies") or 1, width=6),
            dict(key="sort", label="Order", kind="int", value=s.get("sort_order") or 0, width=6),
            dict(key="active", label="In use", kind="check", value=s.get("is_active", True))],
            note="Leave the printer empty to use the default kitchen printer.")

    def add_station(self):
        g = self._station_form("New kitchen station")
        if not g:
            return
        try:
            R.save_station(None, g["name"], g["printer"], 58 if g["paper"].startswith("58") else 80,
                           g["copies"], g["sort"], g["active"])
        except ValueError as e:
            return self._err(e)
        self._load_stations()
        self._load_cats()

    def edit_station(self):
        s = self.st_tv.selection()
        if not s:
            return
        st = next(x for x in R.stations(active_only=False) if x["station_id"] == int(s[0]))
        g = self._station_form("Station %s" % st["station_name"], st)
        if not g:
            return
        try:
            R.save_station(st["station_id"], g["name"], g["printer"], 58 if g["paper"].startswith("58") else 80,
                           g["copies"], g["sort"], g["active"])
        except ValueError as e:
            return self._err(e)
        self._load_stations()
        self._load_cats()

    def delete_station(self):
        s = self.st_tv.selection()
        if not s:
            return
        if not messagebox.askyesno("Delete station", "Delete this station?\nIts categories go to the "
                                   "default station.", parent=self.frame):
            return
        R.delete_station(int(s[0]))
        self._load_stations()
        self._load_cats()

    def set_categories(self):
        sel = self.cat_tv.selection()
        if not sel:
            messagebox.showinfo("Categories", "Select one or more categories first.", parent=self.frame)
            return
        key = next((k for k, n in self._choices() if n == self.goto_var.get()), "default")
        for cid in sel:
            R.set_category_station(int(cid), key)
        self._load_cats()

    def save_kitchen(self):
        R.set_setting("rest_kitchen_printer", self.kp_var.get().strip())
        R.set_setting("rest_kot_paper", "58" if self.kpaper_var.get().startswith("58") else "80")
        R.set_setting("rest_kot_print", bool(self.kprint_var.get()))
        try:
            from ui.ui_polish import toast
            toast(self.frame.winfo_toplevel(), "Kitchen settings saved.", kind="success")
        except Exception:
            pass

    # ── options ──────────────────────────────────────────────
    def _tab_options(self):
        C = self.C
        p = self._page("Order Types & Service")
        box = tk.Frame(p, bg=C["card_bg"])
        box.pack(fill="both", expand=True, padx=20, pady=16)

        def head(t):
            tk.Label(box, text=t, font=("Segoe UI", 11, "bold"), bg=C["card_bg"], fg=C["text_primary"],
                     anchor="w").pack(fill="x", pady=(10, 2))

        def small(t):
            tk.Label(box, text=t, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                     anchor="w", justify="left", wraplength=760).pack(fill="x")
        head("Order types you use")
        row = tk.Frame(box, bg=C["card_bg"])
        row.pack(fill="x")
        on = R.order_types()
        self.type_vars = {}
        for t in R.ORDER_TYPES:
            v = self.type_vars[t] = tk.BooleanVar(value=t in on)
            tk.Checkbutton(row, text=t, variable=v, bg=C["card_bg"], activebackground=C["card_bg"],
                           font=("Segoe UI", 10)).pack(side="left", padx=(0, 16))
        head("Service charge for dine-in")
        row = tk.Frame(box, bg=C["card_bg"])
        row.pack(fill="x")
        self.svc_var = tk.StringVar(value="%g" % R.service_pct())
        tk.Entry(row, textvariable=self.svc_var, width=6, font=("Segoe UI", 11), relief="solid",
                 bd=1).pack(side="left")
        tk.Label(row, text=" %   (0 = no service charge)", font=("Segoe UI", 10), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        small("It is added to dine-in bills as its own line. %s is added on it at the same rate as the "
              "food, so the bill and the tax report stay right. The cashier can take it off one bill with "
              "the 'Service' button in the POS. Check that a service charge is allowed in your country "
              "before you switch it on." % self._tax())
        head("POS")
        self.counter_var = tk.BooleanVar(value=R.flag("rest_counter_as_takeaway"))
        tk.Checkbutton(box, text="A POS bill without a table is a Takeaway order (its items go to the kitchen)",
                       variable=self.counter_var, bg=C["card_bg"], activebackground=C["card_bg"],
                       font=("Segoe UI", 10), anchor="w").pack(fill="x")
        self.clear_var = tk.BooleanVar(value=R.flag("rest_clear_after_kot"))
        tk.Checkbutton(box, text="After Send to Kitchen on a dine-in order, clear the POS for the next table",
                       variable=self.clear_var, bg=C["card_bg"], activebackground=C["card_bg"],
                       font=("Segoe UI", 10), anchor="w").pack(fill="x")
        head("Quick kitchen notes (comma between them)")
        self.notes_var = tk.StringVar(value=str(R.setting("rest_note_choices") or ""))
        tk.Entry(box, textvariable=self.notes_var, width=90, font=("Segoe UI", 10), relief="solid",
                 bd=1).pack(anchor="w")
        tk.Button(box, text="Save", font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white", relief="flat",
                  padx=20, pady=6, command=self.save_options).pack(anchor="w", pady=16)

    @staticmethod
    def _tax():
        try:
            from modules import country
            return country.tax_name()
        except Exception:
            return "VAT"

    def save_options(self):
        types = [t for t in R.ORDER_TYPES if self.type_vars[t].get()]
        if not types:
            return self._err("Keep at least one order type.")
        try:
            pct = float(self.svc_var.get().replace("%", "").strip() or 0)
        except ValueError:
            return self._err("Service charge: type a number like 10.")
        if pct < 0 or pct > 50:
            return self._err("Service charge must be between 0 and 50 %.")
        R.set_setting("rest_order_types", ",".join(types))
        R.set_setting("rest_service_charge_pct", pct)
        R.set_setting("rest_counter_as_takeaway", bool(self.counter_var.get()))
        R.set_setting("rest_clear_after_kot", bool(self.clear_var.get()))
        R.set_setting("rest_note_choices", self.notes_var.get().strip())
        try:
            from ui.ui_polish import toast
            toast(self.frame.winfo_toplevel(), "Saved. Close and open the POS to see the new order types.",
                  kind="success")
        except Exception:
            pass
        return True
