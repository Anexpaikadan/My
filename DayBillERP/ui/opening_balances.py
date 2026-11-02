# ============================================================
# DayBill ERP - Opening Balances (v5.26)
# ------------------------------------------------------------
# One page to bring a shop into DayBill on its first day:
#   🏦 Accounts       cash in hand, bank, fixed assets, loans, capital …
#   📦 Opening stock  quantity + cost of every product (or import Excel)
#   👥 Customers      what each customer owes you (minus = advance)
#   🏭 Suppliers      what you owe each supplier
# Everything is posted on the OPENING DATE against Opening Balance
# Equity — the cards on top show what goes into the books.
# Type in the grid: double-click a cell (or press Enter / F2 / a digit),
# Enter = next row, Tab = next column, Esc = cancel. Then Save.
# ============================================================
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg


def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


def qty(n):
    try:
        x = float(n)
        return f"{x:,.3f}".rstrip("0").rstrip(".") if x % 1 else f"{x:,.0f}"
    except Exception:
        return "0"


def _num(s):
    t = str(s or "").strip().replace(",", "")
    if not t:
        return 0.0
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    v = float(t)
    return -v if neg else v


# ── a Treeview whose cells can be typed into ─────────────────
class CellEditor:
    """Edit chosen columns of a ttk.Treeview in place.
    on_commit(iid, column, text) → value string to show (raise ValueError
    to refuse)."""

    def __init__(self, tree, columns, on_commit):
        self.tree, self.columns, self.on_commit = tree, list(columns), on_commit
        self.entry = None
        tree.bind("<Double-1>", self._dbl, add="+")
        tree.bind("<Return>", lambda e: self.start(), add="+")
        tree.bind("<KP_Enter>", lambda e: self.start(), add="+")
        tree.bind("<F2>", lambda e: self.start(), add="+")
        tree.bind("<KeyPress>", self._key, add="+")

    def _dbl(self, e):
        col = self.tree.identify_column(e.x)
        iid = self.tree.identify_row(e.y)
        if not iid:
            return
        try:
            name = self.tree["columns"][int(col[1:]) - 1]
        except Exception:
            return
        self.tree.selection_set(iid)
        self.start(iid, name if name in self.columns else None)
        return "break"

    def _key(self, e):
        if self.entry is not None:
            return
        ch = e.char or ""
        if ch and (ch.isdigit() or ch in "-.("):
            self.start(initial=ch)
            return "break"

    def start(self, iid=None, column=None, initial=None):
        if self.entry is not None:
            self.commit()
        iid = iid or (self.tree.focus() or (self.tree.selection() or [None])[0])
        if not iid or iid in getattr(self.tree, "_locked_rows", set()):
            return "break"
        column = column or self.columns[0]
        self.tree.see(iid)
        self.tree.update_idletasks()
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return "break"
        x, y, w, h = bbox
        e = tk.Entry(self.tree, font=("Segoe UI", 10), justify="right", relief="solid", bd=1,
                     highlightthickness=1)
        e._no_date = True
        e._fixed_width = True
        e.place(x=x, y=y, width=w, height=h)
        cur = self.tree.set(iid, column)
        e.insert(0, initial if initial is not None else str(cur).replace(",", ""))
        if initial is None:
            e.select_range(0, "end")
        e.icursor("end")
        e.focus_set()
        self.entry, self.iid, self.column = e, iid, column
        e.bind("<Return>", lambda ev: self._move(1, 0))
        e.bind("<KP_Enter>", lambda ev: self._move(1, 0))
        e.bind("<Down>", lambda ev: self._move(1, 0))
        e.bind("<Up>", lambda ev: self._move(-1, 0))
        e.bind("<Tab>", lambda ev: self._move(0, 1))
        e.bind("<Shift-Tab>", lambda ev: self._move(0, -1))
        e.bind("<ISO_Left_Tab>", lambda ev: self._move(0, -1))
        e.bind("<Escape>", lambda ev: self.cancel())
        e.bind("<FocusOut>", lambda ev: self.commit())
        return "break"

    def commit(self):
        e = self.entry
        if e is None:
            return True
        text = e.get()
        self.entry = None
        try:
            shown = self.on_commit(self.iid, self.column, text)
            self.tree.set(self.iid, self.column, shown)
            ok = True
        except ValueError as ex:
            ok = False
            try:
                messagebox.showwarning("Opening balances", str(ex) or "Type a number.",
                                       parent=self.tree.winfo_toplevel())
            except Exception:
                pass
        try:
            e.destroy()
        except Exception:
            pass
        return ok

    def cancel(self):
        e, self.entry = self.entry, None
        if e is not None:
            e.destroy()
        self.tree.focus_set()
        return "break"

    def _move(self, drow, dcol):
        iid, col = self.iid, self.column
        if not self.commit():
            return "break"
        items = [i for i in self.tree.get_children()
                 if i not in getattr(self.tree, "_locked_rows", set())]
        ci = self.columns.index(col) if col in self.columns else 0
        if dcol:
            ci = (ci + dcol) % len(self.columns)
            if (dcol > 0 and ci == 0) or (dcol < 0 and ci == len(self.columns) - 1):
                drow = dcol
        try:
            ri = items.index(iid) + drow
        except ValueError:
            ri = 0
        if 0 <= ri < len(items):
            nxt = items[ri]
            self.tree.selection_set(nxt)
            self.tree.focus(nxt)
            self.start(nxt, self.columns[ci])
        else:
            self.tree.focus_set()
        return "break"


# ── the page ──────────────────────────────────────────────────
class OpeningBalancesView:
    TABS = (("accounts", "Accounts", "🏦"), ("stock", "Opening Stock", "📦"),
            ("customer", "Customers", "👥"), ("supplier", "Suppliers", "🏭"))

    def __init__(self, parent, tab="accounts"):
        from modules import opening_balances as OB
        self.OB = OB
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        try:
            from modules import permissions as perm
            self.can_edit = perm.can("accounts", "edit")
        except Exception:
            self.can_edit = True
        self.data = {}            # tab -> {iid: row dict}
        self.changed = {}         # tab -> set(iid)
        self._top(C)
        self.cards = tk.Frame(self.frame, bg=C["content_bg"])
        self.cards.pack(fill="x", padx=20, pady=(8, 0))
        from ui.fluent_widgets import PageNav
        host = tk.Frame(self.frame, bg=C["content_bg"])
        host.pack(fill="both", expand=True, padx=20, pady=(8, 12))
        self.nav = PageNav(host, C)
        self.nav.frame.pack(fill="both", expand=True)
        self.pages, self.trees, self.editors, self.search = {}, {}, {}, {}
        self.foot = {}
        for key, title, icon in self.TABS:
            pg = self.nav.add_page(title, icon, key=key)
            self.pages[key] = pg
            self._build_tab(key, pg, C)
        self.nav.show(tab if tab in self.pages else "accounts")
        self.refresh()

    # ── top: date + cards ──
    def _top(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(bar, text="Opening date", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.date_var = tk.StringVar(value=self.OB.opening_date())
        e = tk.Entry(bar, textvariable=self.date_var, width=13, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        e.pack(side="left", padx=(6, 6))
        try:
            from ui.datefield import enhance
            enhance(e, self.date_var)
        except Exception:
            pass
        tk.Button(bar, text="Use this date", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                  fg=C["primary"], relief="flat", padx=10, pady=4, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=self._apply_date,
                  state="normal" if self.can_edit else "disabled").pack(side="left")
        tk.Label(bar, text="The day you start using DayBill — every opening is booked on it.",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=10)
        tk.Button(bar, text="📊 Opening report", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=12, pady=5,
                  cursor="hand2", command=self._report).pack(side="right")
        tk.Button(bar, text="➜ Move to Owner's Capital", font=("Segoe UI", 9),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=10, pady=5,
                  cursor="hand2", highlightthickness=1, highlightbackground=C["border"],
                  state="normal" if self.can_edit else "disabled",
                  command=self.to_capital).pack(side="right", padx=(0, 8))

    def _cards_render(self):
        C = self.C
        for w in self.cards.winfo_children():
            w.destroy()
        s = self.OB.summary()
        diff = s["accounts_dr"] - s["accounts_cr"]
        items = (("Accounts (Dr − Cr)", money(diff), C["text_primary"]),
                 ("Opening stock", f"{money(s['stock_value'])}  ·  {s['stock_items']} items", "#0E7490"),
                 ("Customers owe you", money(s["receivable"]), "#1D4ED8"),
                 ("You owe suppliers", money(s["payable"]), "#B45309"),
                 ("Opening Balance Equity (owner's capital)", money(self.OB.equity_balance()),
                  "#047857"))
        for label, val, col in items:
            card = tk.Frame(self.cards, bg=C["card_bg"], highlightthickness=1,
                            highlightbackground=C["border"])
            card.pack(side="left", padx=(0, 10))
            tk.Label(card, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(6, 0))
            tk.Label(card, text=val, font=("Segoe UI", 12, "bold"), bg=C["card_bg"],
                     fg=col).pack(anchor="w", padx=12, pady=(0, 6))

    # ── one tab ──
    COLS = {
        "accounts": [("code", "Code", 80, "w"), ("name", "Account", 260, "w"),
                     ("type", "Type", 90, "w"), ("debit", "Debit", 120, "e"),
                     ("credit", "Credit", 120, "e")],
        "stock": [("code", "Code", 70, "w"), ("name", "Product", 200, "w"),
                  ("unit", "Unit", 55, "w"), ("stock", "Stock now", 80, "e"),
                  ("opening", "Opening qty", 95, "e"), ("cost", "Cost", 80, "e"),
                  ("value", "Value", 95, "e"), ("untracked", "No movement", 95, "e")],
        "customer": [("code", "Code", 90, "w"), ("name", "Customer", 280, "w"),
                     ("phone", "Phone", 130, "w"), ("opening", "Owes you", 130, "e")],
        "supplier": [("code", "Code", 90, "w"), ("name", "Supplier", 280, "w"),
                     ("phone", "Phone", 130, "w"), ("opening", "You owe", 130, "e")],
    }
    EDIT = {"accounts": ("debit", "credit"), "stock": ("opening", "cost"),
            "customer": ("opening",), "supplier": ("opening",)}
    TIPS = {
        "accounts": "Cash in hand, bank, fixed assets (Dr) · loans, VAT owed, capital (Cr). "
                    "Customers, suppliers and stock have their own tabs.",
        "stock": "Quantity in the base unit and cost of ONE base unit. "
                 "'No movement' = stock on the product with nothing behind it.",
        "customer": "What each customer owes you on the opening date (minus = advance they paid).",
        "supplier": "What you owe each supplier on the opening date (minus = advance you paid).",
    }

    def _build_tab(self, key, pg, C):
        top = tk.Frame(pg, bg=C["content_bg"])
        top.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(top, text="🔍", bg=C["content_bg"]).pack(side="left")
        sv = tk.StringVar()
        se = tk.Entry(top, textvariable=sv, width=26, font=("Segoe UI", 10), relief="solid", bd=1)
        se.pack(side="left", padx=(4, 10))
        se._no_date = True
        sv.trace_add("write", lambda *a, k=key: self._fill(k))
        self.search[key] = sv
        tk.Label(top, text=self.TIPS[key], font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"], wraplength=640, justify="left").pack(side="left")

        bottom = tk.Frame(pg, bg=C["content_bg"])
        bottom.pack(side="bottom", fill="x", padx=10, pady=(2, 8))
        lbl = tk.Label(pg, text="", font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                       fg=C["text_primary"], anchor="w")
        lbl.pack(side="bottom", fill="x", padx=12, pady=(4, 0))
        self.foot[key] = lbl
        state = "normal" if self.can_edit else "disabled"
        tk.Button(bottom, text="💾  Save", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=18, pady=6, cursor="hand2", state=state,
                  command=lambda k=key: self.save(k)).pack(side="right")
        tk.Button(bottom, text="↺ Undo changes", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=10, pady=6, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=lambda k=key: self.reload(k)).pack(side="right", padx=(0, 8))
        tk.Button(bottom, text="📥 Excel", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=10, pady=6, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=lambda k=key: self.export(k)).pack(side="right", padx=(0, 8))
        if key == "stock":
            tk.Button(bottom, text="📂 Import Excel…", font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", padx=10, pady=6, cursor="hand2",
                      highlightthickness=1, highlightbackground=C["border"], state=state,
                      command=self.import_stock).pack(side="right", padx=(0, 8))
            self.untracked_btn = tk.Button(
                bottom, text="", font=("Segoe UI", 9, "bold"), bg="#FEF3C7", fg="#92400E",
                relief="flat", padx=10, pady=6, cursor="hand2", state=state,
                command=self.fix_untracked)
            self.untracked_btn.pack(side="left")

        cols = self.COLS[key]
        wrap = tk.Frame(pg, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=10)
        tv = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings", selectmode="browse")
        for cid, txt, w, a in cols:
            tv.heading(cid, text=txt + (" ✎" if cid in self.EDIT[key] else ""))
            tv.column(cid, width=w, anchor=a, stretch=True,
                      minwidth=120 if cid == "name" else 55)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        try:
            from ui.ui_kit import fit_columns
            fit_columns(tv)
        except Exception:
            pass
        tv.tag_configure("changed", background="#FEF9C3")
        tv.tag_configure("warn", foreground="#B45309")
        tv._locked_rows = set()
        self.trees[key] = tv
        if self.can_edit:
            self.editors[key] = CellEditor(tv, self.EDIT[key],
                                           lambda iid, col, text, k=key: self._commit(k, iid, col, text))

    # ── data ──
    def refresh(self):
        for key, _t, _i in self.TABS:
            self.reload(key)
        self._cards_render()

    def reload(self, key):
        OB = self.OB
        if key == "accounts":
            rows = OB.account_rows()
        elif key == "stock":
            rows = OB.stock_rows()
        else:
            rows = OB.party_rows(key)
        self.data[key] = {"r%d" % (r["id"] if r.get("id") is not None else i): dict(r)
                          for i, r in enumerate(rows)}
        self.changed[key] = set()
        self._fill(key)

    def _values(self, key, r):
        if key == "accounts":
            return (r["code"], r["name"], r["type"], money(r["debit"]) if r["debit"] else "",
                    money(r["credit"]) if r["credit"] else "")
        if key == "stock":
            return (r["code"], r["name"], r["unit"], qty(r["stock"]),
                    qty(r["opening"]) if r["opening"] else "", money(r["cost"]),
                    money(r["value"]) if r["value"] else "",
                    qty(r["untracked"]) if abs(r["untracked"]) > 1e-6 else "")
        return (r["code"], r["name"], r["phone"], money(r["opening"]) if r["opening"] else "")

    def _fill(self, key):
        tv = self.trees[key]
        q = self.search[key].get().strip().lower() if key in self.search else ""
        for i in tv.get_children():
            tv.delete(i)
        for iid, r in self.data.get(key, {}).items():
            if q and q not in (str(r.get("code")) + " " + str(r.get("name"))).lower():
                continue
            tags = []
            if iid in self.changed.get(key, ()):
                tags.append("changed")
            if key == "stock" and abs(r.get("untracked") or 0) > 1e-6:
                tags.append("warn")
            tv.insert("", "end", iid=iid, values=self._values(key, r), tags=tags)
        self._foot(key)

    def _foot(self, key):
        rows = list(self.data.get(key, {}).values())
        n = len(self.changed.get(key, ()))
        ch = f"   ·   {n} changed — press Save" if n else ""
        if key == "accounts":
            dr = sum(r["debit"] for r in rows)
            cr = sum(r["credit"] for r in rows)
            d = dr - cr
            side = "Cr" if d > 0 else "Dr"
            txt = (f"Debit {money(dr)}   Credit {money(cr)}   →  Opening Balance Equity "
                   f"{money(abs(d))} {side}" if abs(d) >= 0.005 else
                   f"Debit {money(dr)}   Credit {money(cr)}   ✔ balanced")
        elif key == "stock":
            v = sum(r["value"] for r in rows)
            k = sum(1 for r in rows if r["opening"])
            txt = f"{k} products  ·  opening stock value {money(v)}"
            u = sum(1 for r in rows if abs(r["untracked"]) > 1e-6)
            if hasattr(self, "untracked_btn"):
                if u:
                    self.untracked_btn.config(text=f"⚠ Book stock with no movement ({u})")
                    if not self.untracked_btn.winfo_ismapped():
                        self.untracked_btn.pack(side="left")
                else:
                    self.untracked_btn.pack_forget()
        else:
            t = sum(r["opening"] for r in rows)
            k = sum(1 for r in rows if r["opening"])
            txt = f"{k} with an opening balance  ·  total {money(t)}"
        self.foot[key].config(text=txt + ch)

    def _commit(self, key, iid, col, text):
        r = self.data[key][iid]
        try:
            v = _num(text)
        except ValueError:
            raise ValueError("Type a number, e.g. 1500 or 1,500.00")
        if key == "accounts":
            v = abs(v)
            r[col] = round(v, 2)
            other = "credit" if col == "debit" else "debit"
            if v:
                r[other] = 0.0           # one side per account
                self.trees[key].set(iid, other, "")
            shown = money(v) if v else ""
        elif key == "stock":
            if col == "cost" and v < 0:
                raise ValueError("Cost cannot be below zero.")
            r[col] = round(v, 4 if col == "opening" else 2)
            r["value"] = round(r["opening"] * r["cost"], 2)
            self.trees[key].set(iid, "value", money(r["value"]) if r["value"] else "")
            shown = (qty(v) if v else "") if col == "opening" else money(v)
        else:
            r["opening"] = round(v, 2)
            shown = money(v) if v else ""
        self.changed[key].add(iid)
        tags = set(self.trees[key].item(iid, "tags") or ())
        tags.add("changed")
        self.trees[key].item(iid, tags=tuple(tags))
        self._foot(key)
        return shown

    # ── save ──
    def save(self, key):
        if not self.can_edit:
            messagebox.showwarning("Opening balances", "You don't have the right to change "
                                   "opening balances (Users & Rights ▸ Accounts ▸ Edit).")
            return False
        ed = self.editors.get(key)
        if ed is not None and ed.entry is not None and not ed.commit():
            return False
        OB = self.OB
        when = OB.opening_date()
        n = 0
        try:
            if key == "accounts":
                amounts = {r["id"]: (r["debit"], r["credit"]) for r in self.data[key].values()
                           if r["debit"] or r["credit"]}
                jid = OB.save_account_openings(amounts, when)
                if not jid and amounts:
                    raise RuntimeError(OB.last_error or "The opening entry could not be posted.")
                n = len(amounts)
            elif key == "stock":
                for iid in sorted(self.changed[key]):
                    r = self.data[key][iid]
                    OB.set_opening_stock(r["id"], r["opening"], r["cost"] or None, when)
                    n += 1
            else:
                for iid in sorted(self.changed[key]):
                    r = self.data[key][iid]
                    OB.set_party_opening(key, r["id"], r["opening"])
                    n += 1
        except Exception as e:
            messagebox.showerror("Opening balances", str(e)[:300])
            return False
        try:
            from modules import audit
            audit.log("opening_balances", key, None, f"{n} saved")
        except Exception:
            pass
        self.reload(key)
        self._cards_render()
        try:
            from ui.fluent_widgets import show_toast
            show_toast(self.frame.winfo_toplevel(), f"✓ Opening balances saved ({n})")
        except Exception:
            pass
        return True

    def _apply_date(self):
        d = self.date_var.get().strip()
        try:
            self.OB.set_opening_date(d)
        except ValueError as e:
            messagebox.showwarning("Opening date", str(e))
            return
        self.refresh()
        try:
            from ui.fluent_widgets import show_toast
            show_toast(self.frame.winfo_toplevel(), f"✓ Opening date {d}")
        except Exception:
            pass

    def to_capital(self):
        amt = self.OB.equity_balance()
        if abs(amt) < 0.005:
            messagebox.showinfo("Owner's Capital", "Opening Balance Equity is zero — nothing to move.")
            return None
        if not messagebox.askyesno(
                "Owner's Capital",
                f"Move {money(amt)} from Opening Balance Equity to Owner's Capital (3100)?\n\n"
                f"Do this once all openings are entered (you can move again later)."):
            return None
        jid = self.OB.move_equity_to_capital()
        if not jid:
            messagebox.showwarning("Owner's Capital", self.OB.last_error or "Not posted.")
            return None
        self._cards_render()
        return jid

    def fix_untracked(self):
        rows = [r for r in self.data.get("stock", {}).values() if abs(r["untracked"]) > 1e-6]
        if not rows:
            return 0
        if not messagebox.askyesno(
                "Stock with no movement",
                f"{len(rows)} product(s) have stock with no purchase, sale or opening "
                f"behind it (typed in before, or imported).\n\nBook that stock as opening "
                f"stock at its cost? The stock quantity stays the same; the stock card and "
                f"the Inventory account are brought in line."):
            return 0
        n = self.OB.add_untracked_stock(self.OB.opening_date())
        self.reload("stock")
        self._cards_render()
        return n

    def import_stock(self, path=None):
        """Excel with Code (or Barcode), Qty and optional Cost columns."""
        path = path or filedialog.askopenfilename(
            filetypes=[("Excel", "*.xlsx")], title="Opening stock — Excel file")
        if not path:
            return 0
        try:
            import openpyxl
            ws = openpyxl.load_workbook(path, data_only=True).active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as e:
            messagebox.showerror("Import", str(e)[:200])
            return 0
        head_i, cols = None, {}
        for i, row in enumerate(rows[:15]):
            names = [str(c or "").strip().lower() for c in row]
            if any("code" in n or "barcode" in n for n in names) and \
                    any(n.startswith(("qty", "quantity", "stock", "opening")) for n in names):
                head_i = i
                for j, n in enumerate(names):
                    if "barcode" in n:
                        cols.setdefault("barcode", j)
                    elif "code" in n:
                        cols.setdefault("code", j)
                    elif n.startswith(("qty", "quantity", "opening", "stock")):
                        cols.setdefault("qty", j)
                    elif "cost" in n or "price" in n:
                        cols.setdefault("cost", j)
                break
        if head_i is None:
            messagebox.showwarning("Import", "Put a header row with 'Code' and 'Qty' "
                                   "(and 'Cost' if you like).")
            return 0
        from modules.product_lookup import norm_code
        by_code = {norm_code(r["code"]): iid for iid, r in self.data["stock"].items()}
        bar = {}
        try:
            from config.database import db
            for r in db.fetchall("SELECT product_id, barcode FROM product_units WHERE "
                                 "ISNULL(barcode,'')<>''") or []:
                bar[str(r["barcode"]).strip()] = "r%d" % r["product_id"]
            for r in db.fetchall("SELECT product_id, barcode FROM products WHERE "
                                 "ISNULL(barcode,'')<>''") or []:
                bar.setdefault(str(r["barcode"]).strip(), "r%d" % r["product_id"])
        except Exception:
            pass
        n, missing = 0, []
        for row in rows[head_i + 1:]:
            def cell(k):
                j = cols.get(k)
                return row[j] if j is not None and j < len(row) else None
            code, bc = cell("code"), cell("barcode")
            if code in (None, "") and bc in (None, ""):
                continue
            iid = by_code.get(norm_code(code)) if code not in (None, "") else None
            if not iid and bc not in (None, ""):
                iid = bar.get(str(bc).strip())
            if not iid and code not in (None, ""):          # a barcode in the Code column
                iid = bar.get(str(code).strip())
            if not iid or iid not in self.data["stock"]:
                missing.append(str(code or bc))
                continue
            try:
                q_ = _num(cell("qty"))
                c_ = _num(cell("cost")) if cell("cost") not in (None, "") else None
            except ValueError:
                missing.append(str(code or bc))
                continue
            r = self.data["stock"][iid]
            r["opening"] = round(q_, 4)
            if c_ is not None and c_ > 0:
                r["cost"] = round(c_, 2)
            r["value"] = round(r["opening"] * r["cost"], 2)
            self.changed["stock"].add(iid)
            n += 1
        self._fill("stock")
        self.nav.show("stock")
        msg = f"{n} product(s) filled in — check them, then press Save."
        if missing:
            msg += f"\n\nNot found ({len(missing)}): " + ", ".join(missing[:12]) + \
                   (" …" if len(missing) > 12 else "")
        messagebox.showinfo("Import", msg)
        return n

    def export(self, key, path=None):
        from modules.report_export import export_excel
        cols = self.COLS[key]
        rows = [list(self._values(key, r)) for r in self.data.get(key, {}).values()]
        title = dict((k, t) for k, t, _i in self.TABS)[key]
        return export_excel(self.frame, "Opening_" + title.replace(" ", "_"),
                            [c[1] for c in cols], rows, title="Opening balances — " + title,
                            summary=[("Opening date", self.OB.opening_date())], path=path)

    def _report(self):
        mw = getattr(self.frame.winfo_toplevel(), "_daybill_main", None)
        if mw is not None and hasattr(mw, "_open_report"):
            mw._open_report("opening_balances")
