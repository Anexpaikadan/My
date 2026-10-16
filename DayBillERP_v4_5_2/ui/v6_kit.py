# ============================================================
# DayBill ERP - small building blocks for the v6.0 pages
# (price lists, transfers, expiry, bank reconciliation, year-end,
#  debit notes, shifts, leave & attendance)
# Same look as the other pages: theme colours, cards, flat buttons,
# headings + one line saying what the page is for.
# ============================================================
import tkinter as tk
from tkinter import ttk

from config import settings as cfg


def money(v):
    try:
        return "{:,.2f}".format(float(v or 0))
    except (TypeError, ValueError):
        return "0.00"


def num(var, default=None):
    """Float from a StringVar / text (commas allowed) or default."""
    try:
        s = var.get() if hasattr(var, "get") else var
        s = str(s).replace(",", "").strip()
        return float(s) if s else default
    except (TypeError, ValueError):
        return default


class Page:
    """Header + scrolling-free body for a module page."""

    def __init__(self, parent, title, sub=""):
        self.C = C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        top = tk.Frame(self.frame, bg=C["content_bg"])
        top.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(top, text=title, font=("Segoe UI", 17, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")
        self.top_right = tk.Frame(top, bg=C["content_bg"])
        self.top_right.pack(side="right")
        if sub:
            tk.Label(self.frame, text=sub, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"], anchor="w", justify="left",
                     wraplength=1100).pack(fill="x", padx=22)
        self.status = tk.StringVar()
        self.status_lbl = tk.Label(self.frame, textvariable=self.status, font=("Segoe UI", 9, "bold"),
                                   bg=C["content_bg"], fg=C["primary"], anchor="w")
        self.status_lbl.pack(fill="x", padx=22, side="bottom", pady=(0, 6))
        self.body = tk.Frame(self.frame, bg=C["content_bg"])
        self.body.pack(fill="both", expand=True, padx=20, pady=(6, 4))

    def say(self, text, ok=True):
        self.status.set(text)
        try:
            self.status_lbl.configure(fg=self.C["primary"] if ok else self.C["danger"])
        except Exception:
            pass


def card(parent, C, title=None, **pack):
    c = tk.Frame(parent, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
    if pack:
        c.pack(**pack)
    if title:
        tk.Label(c, text=title, font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=12, pady=(8, 2))
    return c


def entry(parent, C, label, var, width=14, side="left", justify="left", **kw):
    f = tk.Frame(parent, bg=C["card_bg"])
    f.pack(side=side, padx=(0, 10), pady=2, anchor="n")
    tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
             fg=C["text_secondary"]).pack(anchor="w")
    e = tk.Entry(f, textvariable=var, width=width, font=("Segoe UI", 10), relief="solid", bd=1,
                 justify=justify, **kw)
    e.pack(anchor="w", ipady=2)
    e._fixed_width = True
    return e


def combo(parent, C, label, var, values, width=18, side="left"):
    f = tk.Frame(parent, bg=C["card_bg"])
    f.pack(side=side, padx=(0, 10), pady=2, anchor="n")
    tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
             fg=C["text_secondary"]).pack(anchor="w")
    cb = ttk.Combobox(f, textvariable=var, values=values, width=width, state="readonly")
    cb.pack(anchor="w", ipady=1)
    return cb


def date_entry(parent, C, label, var, side="left"):
    """A date box with the 📅 calendar when available (ui/datefield)."""
    f = tk.Frame(parent, bg=C["card_bg"])
    f.pack(side=side, padx=(0, 10), pady=2, anchor="n")
    tk.Label(f, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
             fg=C["text_secondary"]).pack(anchor="w")
    e = tk.Entry(f, textvariable=var, width=12, font=("Segoe UI", 10), relief="solid", bd=1)
    e.pack(anchor="w", ipady=2)
    e._fixed_width = True
    try:                                    # 📅 calendar + arrow keys (v5.25)
        from ui.datefield import DateBox
        DateBox(e, var)
    except Exception:
        pass
    return e


def button(parent, C, text, cmd, primary=False, danger=False, side="left", **kw):
    bg = C["primary"] if primary else (C.get("danger", "#DC2626") if danger else C["card_bg"])
    fg = "white" if (primary or danger) else C["text_primary"]
    b = tk.Button(parent, text=text, font=("Segoe UI", 9, "bold" if (primary or danger) else "normal"),
                  bg=bg, fg=fg, relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                  highlightthickness=0 if (primary or danger) else 1,
                  highlightbackground=C["border"], command=cmd, **kw)
    b.pack(side=side, padx=(0, 6))
    return b


def tree(parent, cols, height=10, pack=True):
    """cols = [(key, heading, width, anchor)] → Treeview with a scrollbar."""
    wrap = tk.Frame(parent)
    t = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings", height=height)
    for k, h, w, a in cols:
        t.heading(k, text=h, anchor="e" if a == "e" else ("w" if a == "w" else "center"))
        t.column(k, width=w, anchor=a, stretch=(a == "w"))
    sb = ttk.Scrollbar(wrap, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    if pack:
        wrap.pack(fill="both", expand=True, padx=10, pady=(4, 8))
    t._wrap = wrap
    return t


class ProductFinder(tk.Frame):
    """Type a code / name / barcode + Enter → pick from a short list.
    on_pick(product_row)."""

    def __init__(self, parent, C, on_pick, label="Product (code, name or barcode)", width=34):
        super().__init__(parent, bg=C["card_bg"])
        self.C, self.on_pick = C, on_pick
        tk.Label(self, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.var = tk.StringVar()
        self.entry = tk.Entry(self, textvariable=self.var, width=width, font=("Segoe UI", 10),
                              relief="solid", bd=1)
        self.entry.pack(anchor="w", ipady=2)
        self.entry._fixed_width = True
        self.entry.bind("<Return>", lambda e: self.find())
        self.entry.bind("<Down>", lambda e: self.find())
        self._pop = None
        self.picked = None

    def find(self):
        from modules import product_lookup as PL
        text = self.var.get().strip()
        rows = PL.search_products(text, limit=12) if text else []
        self._close()
        if not rows:
            self.bell()
            return "break"
        if len(rows) == 1:
            self._choose(rows[0])
            return "break"
        top = tk.Toplevel(self)
        top.overrideredirect(True)
        top._keep_size = True
        lb = tk.Listbox(top, height=min(10, len(rows)), width=60, font=("Segoe UI", 10),
                        activestyle="dotbox")
        for r in rows:
            lb.insert("end", "%s — %s   (stock %g)" % (r.get("product_code"), r.get("product_name_en"),
                                                       float(r.get("stock_quantity") or 0)))
        lb.pack(fill="both", expand=True)
        lb.selection_set(0)
        lb.focus_set()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        top.geometry("+%d+%d" % (x, y))
        lb.bind("<Return>", lambda e: self._choose(rows[lb.curselection()[0]]) if lb.curselection() else None)
        lb.bind("<Double-1>", lambda e: self._choose(rows[lb.curselection()[0]]) if lb.curselection() else None)
        lb.bind("<Escape>", lambda e: self._close())
        top.bind("<FocusOut>", lambda e: self.after(150, self._close))
        self._pop = top
        return "break"

    def _close(self):
        if self._pop is not None:
            try:
                self._pop.destroy()
            except Exception:
                pass
            self._pop = None

    def _choose(self, row):
        self._close()
        self.picked = row
        self.var.set("%s — %s" % (row.get("product_code"), row.get("product_name_en")))
        if self.on_pick:
            self.on_pick(row)

    def clear(self):
        self.picked = None
        self.var.set("")
