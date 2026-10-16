# ============================================================
# DayBill ERP - keyboard shortcuts: one list for the whole app (v6.9.3)
# ------------------------------------------------------------
#   GLOBAL   keys of the main window (they never fire while you type in
#            a field when they are Ctrl keys, and never inside another
#            window such as the POS or an invoice)
#   TXN      the SAME keys in every transaction window (Sales, Purchase,
#            Returns, Receipt / Payment, Expense, Journal, Consumable …),
#            bound by ui/txn_connector.TxnBar
#   WINDOWS  each window's own keys (Sales Invoice, POS …)
# Help ▸ ⌨ Keyboard Shortcuts (F1) shows all of them — ShortcutHelp.
# ============================================================

import tkinter as tk
from tkinter import ttk

GLOBAL = [
    ("F1", "Keyboard shortcuts (this list)"),
    ("F2", "Sales Invoices"),
    ("F3", "POS (cashier)"),
    ("F4", "Purchases"),
    ("F5", "Refresh the open screen (Reports: run)"),
    ("F6", "New Cash Receipt (CR)"),
    ("F7", "New Cash Payment (CP)"),
    ("F8", "Products"),
    ("F9", "Account Ledger"),
    ("F11", "Stock / Inventory"),
    ("F12", "Reports Center"),
    ("Ctrl+N", "New … in the open screen (invoice, purchase, product, customer …)"),
    ("Ctrl+K", "Search the menu"),
    ("Ctrl+L", "Account Ledger"),
    ("Ctrl+I", "Stock / Inventory"),
    ("Ctrl+E", "Expenses"),
    ("Ctrl+R", "Sales Returns"),
    ("Ctrl+Shift+R", "Purchase Returns"),
    ("Ctrl+P", "Receipts & Payments"),
    ("Ctrl+J", "Vouchers (journal entries)"),
    ("Ctrl+Shift+N", "Add Product"),
    ("Ctrl+Shift+C", "New Consumable Entry (staff food, bakery …)"),
    ("Ctrl+Shift+J", "New Journal Voucher (JV)"),
    ("Ctrl+Z", "Day Close / Z-Report (not while typing)"),
    ("Right-click a menu item", "Add it to ⭐ Favourites (right-click a favourite: remove / move)"),
]

TXN = [
    ("Ctrl+S", "Save"),
    ("Ctrl+N", "New (same kind of transaction)"),
    ("Ctrl+E", "Edit (a window opened for viewing)"),
    ("Ctrl+Delete", "Delete this transaction (asks first; follows your rights)"),
    ("Ctrl+J", "Voucher lines (the journal entry: SI, CR, CP …)"),
    ("Esc", "Close (asks when something is not saved)"),
    ("F1", "Keyboard shortcuts"),
]

WINDOWS = [
    ("Sales Invoice", [
        ("F9", "Save as draft"), ("F10", "Print (choose the format)"),
        ("Ctrl+S", "Save & confirm"), ("Esc", "Cancel / close"),
        ("Enter", "Next field / add the item"), ("Delete", "Remove the line"),
        ("Space", "Change the unit of the line (in the grid)"),
        ("⭐ Pts box", "Spend loyalty points (when on)"),
    ]),
    ("POS (cashier)", [
        ("F1", "Save (cash / card window)"), ("F2", "Save & print"), ("F3", "New bill"),
        ("F6", "Hold the bill"), ("F7", "Retrieve a held bill"), ("F8", "Price check"),
        ("F9", "Shift: open / close"), ("F10", "⭐ Spend loyalty points"),
        ("Space", "Change the unit of the selected line"), ("Esc", "Clear the scan box"),
        ("Enter", "Add the scanned / typed item"),
    ]),
    ("Purchase / Returns / Quotation / Purchase Order", [
        ("Ctrl+S", "Save"), ("Enter", "Next field / add the item"),
        ("Delete", "Remove the line"), ("Esc", "Close"),
    ]),
    ("Receipt / Payment / Voucher (CR · BR · CP · BP · JV)", [
        ("Ctrl+S", "Save"), ("Enter", "Next field"), ("Esc", "Close"),
    ]),
    ("Consumable Entry", [
        ("Enter", "Add the item"), ("Delete", "Remove the line"),
        ("Ctrl+S", "Save (stock out + expense posted)"), ("Ctrl+D", "Save as draft"),
        ("Esc", "Close"),
    ]),
    ("Account Ledger / Statements", [
        ("Double-click / Enter", "Open the transaction of the line"),
        ("Right-click", "Open · Edit · Delete · Voucher · New"),
    ]),
    ("Lists (products, customers, suppliers …)", [
        ("Double-click / Enter", "Open / edit"), ("Delete", "Delete (asks first; follows your rights)"),
        ("Ctrl+N", "New"),
    ]),
]


def all_rows():
    """[(area, key, what), …] for the help window and printing."""
    rows = [("Everywhere (main window)", k, w) for k, w in GLOBAL]
    rows += [("Every transaction window", k, w) for k, w in TXN]
    for area, keys in WINDOWS:
        rows += [(area, k, w) for k, w in keys]
    return rows


_open = {}


class ShortcutHelp:
    """Help ▸ ⌨ Keyboard Shortcuts. One window: pressing F1 again brings it
    to the front. Type in the box to find a key or an action."""

    def __init__(self, parent, area=None):
        old = _open.get("win")
        try:
            if old is not None and old.winfo_exists():
                old.deiconify()
                old.lift()
                old.focus_force()
                if area:
                    _open["obj"].find.set(area)
                return
        except Exception:
            pass
        from config import settings as cfg
        C = cfg.theme()
        w = self.win = tk.Toplevel(parent)
        _open.update(win=w, obj=self)
        w.title("Keyboard Shortcuts")
        w.geometry("760x560")
        w.configure(bg=C["content_bg"])
        try:
            w.transient(parent.winfo_toplevel())
        except Exception:
            pass
        band = tk.Frame(w, bg=C["primary"])
        band.pack(fill="x")
        tk.Label(band, text="⌨  Keyboard Shortcuts", font=("Segoe UI", 11, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=12, pady=6)
        tk.Label(band, text="F1 anywhere opens this list", font=("Segoe UI", 8),
                 bg=C["primary"], fg="white").pack(side="right", padx=12)
        top = tk.Frame(w, bg=C["content_bg"])
        top.pack(fill="x", padx=12, pady=8)
        tk.Label(top, text="Find", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.find = tk.StringVar(value=area or "")
        e = tk.Entry(top, textvariable=self.find, font=("Segoe UI", 10), relief="solid", bd=1,
                     width=40)
        e.pack(side="left", padx=6)
        self.find.trace_add("write", lambda *a: self._fill())
        wrap = tk.Frame(w, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tree = ttk.Treeview(wrap, columns=("key", "what"), show="tree headings")
        self.tree.heading("#0", text="Window")
        self.tree.heading("key", text="Key")
        self.tree.heading("what", text="What it does")
        self.tree.column("#0", width=230)
        self.tree.column("key", width=150)
        self.tree.column("what", width=340)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tk.Button(w, text="Close  [Esc]", font=("Segoe UI", 9), relief="flat", padx=12,
                  cursor="hand2", command=w.destroy).pack(side="right", padx=12, pady=(0, 10))
        w.bind("<Escape>", lambda ev: w.destroy())
        w.bind("<F1>", lambda ev: "break")
        self._fill()
        e.focus_set()

    def _fill(self):
        q = self.find.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        groups = {}
        for area, key, what in all_rows():
            if q and q not in ("%s %s %s" % (area, key, what)).lower():
                continue
            if area not in groups:
                groups[area] = self.tree.insert("", "end", text=area, open=True)
            self.tree.insert(groups[area], "end", text="", values=(key, what))


def show(parent, area=None):
    try:
        ShortcutHelp(parent, area)
    except Exception:
        pass
    return "break"
