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
    ("Ctrl+Shift+Z", "Day Close / Z-Report"),
    ("Ctrl+W / Ctrl+F4", "Close the open screen"),
    ("Ctrl+Tab / Ctrl+Shift+Tab", "Next / previous open screen"),
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
    ("Vouchers (Receipt · Payment · Contra · Journal)", [
        ("Enter", "Next field / add the line"), ("Insert", "Add the line"),
        ("F2", "Party / account box"), ("Double-click / F2 on a line", "Change the line"),
        ("Delete", "Remove the line"), ("Ctrl+D", "Duplicate the line"),
        ("Alt+↑ / Alt+↓", "Move the line"), ("Ctrl+B", "⚖ Balance the journal"),
        ("Ctrl+S", "Save"), ("Esc", "Cancel changing a line / close"),
    ]),
    ("Sales Invoice", [
        ("F2", "Find a product"), ("F3", "Find a customer"), ("F4", "Barcode box"),
        ("F5", "Recalculate totals"), ("F6", "Bill discount"), ("F7", "Tax details"),
        ("F8", "Cash received box"), ("F9", "Save as draft"), ("F10", "Save & print"),
        ("F11", "Dot-matrix print"), ("F12", "PDF"), ("Ctrl+S", "Save"),
        ("Ctrl+End", "Last row of the grid"), ("Ctrl+M", "Voice search"),
        ("Ctrl+G", "Sizes & colours grid (Textiles shops)"),
        ("Enter", "Next field / add the item"), ("Delete", "Remove the line"),
        ("Space", "Change the unit of the line (in the grid)"),
        ("Hold Ctrl", "Show the item's stock / cost box"),
        ("⭐ Pts box", "Spend loyalty points (when on)"), ("Esc", "Close (asks when not saved)"),
    ]),
    ("POS (cashier)", [
        ("F1", "Save (cash / card window)"), ("F2", "Save & print"), ("F3", "New bill"),
        ("F6", "Hold the bill"), ("F7", "Retrieve a held bill"), ("F8", "Price check"),
        ("F9", "Shift: open / close"), ("F10", "⭐ Spend loyalty points"),
        ("Space", "Change the unit of the selected line"), ("Esc", "Clear the scan box"),
        ("Ctrl+G", "Sizes & colours grid (Textiles shops)"),
        ("Enter", "Add the scanned / typed item"),
    ]),
    ("POS — Restaurant (when the Restaurant module is on)", [
        ("F4", "Send to Kitchen (KOT): only new or changed items"),
        ("F5", "Print Bill for the guest (before payment)"),
        ("F6", "Hold: keep the order on its table / as takeaway"),
        ("F7", "Running orders: open one"), ("F11", "Kitchen note for the line (no onion …)"),
        ("F12", "Tables: a free one starts an order, a busy one opens it"),
        ("Delete Bill", "Cancel the order (the kitchen gets a CANCEL ticket)"),
    ]),
    ("Purchase / Sales Return / Purchase Return", [
        ("F6", "Barcode box"), ("F9", "Save as draft"), ("F10", "Save & confirm"),
        ("Ctrl+S", "Save"), ("Enter", "Next field / add the item"),
        ("Delete", "Remove the line"), ("Space", "Change the unit (grid)"), ("Esc", "Close"),
        ("Ctrl+G", "Sizes & colours grid (Purchase, Textiles shops)"),
    ]),
    ("Quotation / Purchase Order", [
        ("F9 / Ctrl+S", "Save"), ("Ctrl+P", "Print"), ("Delete", "Remove the line"),
        ("Esc", "Close"),
    ]),
    ("Receipt / Payment (from the Payments screen)", [
        ("F9 / Ctrl+S", "Save"), ("Space", "Tick / untick an invoice"),
        ("Enter / F2", "Type the amount paid on an invoice"), ("Esc", "Close"),
    ]),
    ("Voucher (CR · BR · CP · BP · JV) / Journal / Expense", [
        ("Ctrl+S", "Save"), ("F9", "Save (Expense)"), ("Enter", "Next field"),
        ("Delete", "Remove a journal line"), ("Esc", "Close"),
    ]),
    ("Product window", [
        ("Product summary (right)", "Live price with / without VAT, cost, profit, profit %, stock, "
                                    "PLU, units 1-3, barcodes"),
    ]),
    ("Product / Customer / Supplier form", [
        ("Ctrl+S / F4", "Save"), ("F5", "Save & print (product)"),
        ("Ctrl+D", "Duplicate the product"), ("Ctrl+P", "Print the barcode label"),
        ("Ctrl+B", "Make a barcode"), ("Alt+1 … Alt+9", "Go to page 1 … 9 of the form"),
        ("Ctrl+Tab", "Next page of the form"), ("Esc", "Close"),
    ]),
    ("Products list", [
        ("Insert", "New product"), ("F2 / Enter", "Edit"), ("Delete", "Delete"),
        ("F5", "Reload"), ("Ctrl+F", "Search"),
    ]),
    ("Date boxes", [
        ("Up / Down", "Day before / after"), ("PgUp / PgDn", "Month before / after"),
        ("Alt+Down / F4", "Calendar"),
    ]),
    ("Reports", [
        ("Enter (in a filter) / F5", "Run the report"),
    ]),
    ("Sizes & colours grid (Textiles)", [
        ("Arrows", "Next box up / down / left / right"), ("Enter", "Next box"),
        ("Ctrl+Enter / F9", "Add the quantities to the bill"), ("Esc", "Close"),
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
    ("Lists and tables (everywhere)", [
        ("Right-click a heading / ☰", "Columns: show / hide, ➕ More columns (profit, profit %, cost, "
                                      "PLU, stock, units 1-3, multi barcode …), font size and design"),
        ("Drag a heading / its edge", "Move the column / change its width"),
        ("Double-click / Enter", "Open / edit"), ("Delete", "Delete (asks first; follows your rights)"),
        ("Ctrl+N", "New"), ("Ctrl+C", "Copy the selected rows"), ("Ctrl+A", "Select all"),
        ("Home / End", "First / last row"),
    ]),
    ("Any field", [
        ("Enter", "Next field (or the window's OK)"), ("Esc", "Close the window "
                                                      "(a list / editor first)"),
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
