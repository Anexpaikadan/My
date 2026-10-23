# ============================================================
# DayBill ERP - Transaction Connector (v6.9)
# ------------------------------------------------------------
# One bridge between ANY ledger line and the window that made it.
#
#   Ledger / statement line  ──►  journal_entries.source_type + source_id
#                            ──►  connector (Sales, Purchase, Receipt …)
#                            ──►  its own transaction window
#
# Every transaction window (opened from a ledger or from its own list)
# gets the same action bar:   ➕ New · ✏ Edit · 💾 Save · 🗑 Delete ·
# 📄 Voucher · ✖ Close  — each button follows the logged-in user's
# rights for THAT transaction type (Users & Rights matrix).
#
# Ledger ▸ "🔗 Connectors" shows every connector, the window it opens,
# your rights, and lets you choose what a double-click does per type:
#   Edit window  ·  View only  ·  Voucher lines
# (kept in settings as "txn_connector_modes").
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import permissions as perm


# ── the connectors (order = order in the chooser / New menu) ────
#   key: label, perm (RBAC module), window (what opens), doc (doc_edit kind),
#        sources (journal source_type values it owns), new (can create)
CONNECTORS = [
    ("sales", dict(label="Sales Invoice / POS Bill", perm="sales",
                   window="Sales Invoice window", doc="sales",
                   sources=("sales", "pos", "cogs"), new=True)),
    ("sales_return", dict(label="Sales Return", perm="sales_return",
                          window="Sales Return window", doc="sales_return",
                          sources=("sales_return", "cogs_return"), new=True)),
    ("purchase", dict(label="Purchase Invoice", perm="purchase",
                      window="Purchase Invoice window", doc="purchase",
                      sources=("purchase",), new=True)),
    ("purchase_return", dict(label="Purchase Return", perm="purchase_return",
                             window="Purchase Return window", doc="purchase_return",
                             sources=("purchase_return", "purchase_return_cost"),
                             new=True)),
    ("receipt", dict(label="Receipt (from customer)", perm="receipt",
                     window="Receipt window", doc=None,
                     sources=("receipt",), new=True)),
    ("payment", dict(label="Payment (to supplier)", perm="payment",
                     window="Supplier Payment window", doc=None,
                     sources=("payment",), new=True)),
    ("expense", dict(label="Expense / Asset purchase", perm="accounts",
                     window="Expense window", doc=None,
                     sources=("expense",), new=True)),
    ("consumption", dict(label="Consumable Entry (own use)", perm="consumption",
                         window="Consumable Entry window", doc="consumption",
                         sources=("consumption",), new=True)),
    ("journal", dict(label="Journal / Voucher", perm="journal",
                     window="Journal Entry window", doc=None,
                     sources=("manual", "adjustment", "transfer", "journal",
                              "voucher", ""), new=True)),
    ("opening", dict(label="Opening Balance", perm="accounts",
                     window="Voucher lines (Opening Balances)", doc=None,
                     sources=("opening_*",), new=False)),
    ("system", dict(label="Payroll / Stock / Year-end (automatic)", perm="journal",
                    window="Voucher lines (read only)", doc=None,
                    sources=("payroll", "salary_payment", "gosi_payment",
                             "stock_adjust", "opening_stock", "…"),
                    new=False)),
]
CONN = dict(CONNECTORS)

MODES = [("edit", "Edit window"), ("view", "View only"), ("voucher", "Voucher lines")]
MODE_LABEL = dict(MODES)
_SETTING = "txn_connector_modes"

# journal source_type → connector key (receipt / payment / expense fall back
# to "journal" when they were typed as a plain voucher, i.e. no source_id)
_SOURCE_TO_KEY = {}
for _k, _c in CONNECTORS:
    for _s in _c["sources"]:
        if not _s.endswith("*") and _s != "…":
            _SOURCE_TO_KEY[_s] = _k


# ============================================================
#  Rights + settings
# ============================================================
def can(key, action="view"):
    c = CONN.get(key)
    if not c:
        return False
    try:
        return perm.can(c["perm"], action)
    except Exception:
        return False


def rights(key):
    """{'view': bool, 'add': bool, 'edit': bool, 'delete': bool, 'print': bool}"""
    return {a: can(key, a) for a in ("view", "add", "edit", "delete", "print")}


def _say_not_allowed(key, action, parent=None):
    try:
        perm.allowed(CONN[key]["perm"], action, parent=parent)
    except Exception:
        messagebox.showwarning("Not allowed", "You don't have this right.", parent=parent)


def modes():
    m = cfg.get(_SETTING) or {}
    return dict(m) if isinstance(m, dict) else {}


def mode_for(key):
    m = modes().get(key, "edit")
    if key in ("opening", "system"):
        return "voucher"
    return m if m in MODE_LABEL else "edit"


def save_modes(new_modes):
    cfg.set(_SETTING, dict(new_modes))
    try:
        cfg.save_settings()
    except Exception:
        pass


# ============================================================
#  Resolve a ledger line → transaction
# ============================================================
def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _exists(sql, arg):
    try:
        return bool(db.fetchone(sql, (arg,)))
    except Exception:
        return False


def resolve(journal_id):
    """What a journal entry belongs to:
    {key, journal_id, number, date, source_type, source_id, doc_id, label}
    or None when the journal is gone."""
    try:
        je = db.fetchone(
            "SELECT journal_id, journal_number, entry_date, source_type, source_id, "
            "description_en FROM journal_entries WHERE journal_id=?",
            (int(journal_id),))
    except Exception:
        je = None
    if not je:
        return None
    src = str(je.get("source_type") or "").strip().lower()
    sid = je.get("source_id")
    key = _SOURCE_TO_KEY.get(src)
    if src.startswith("opening_"):
        key = "opening"
    elif key in ("receipt", "payment"):
        if not (sid and _exists("SELECT payment_id FROM payments WHERE payment_id=?", sid)):
            key = "journal"           # typed as a voucher → edit as a journal
    elif key == "expense":
        if not (sid and _exists("SELECT expense_id FROM expenses WHERE expense_id=?", sid)):
            key = "journal"
    elif key in ("sales", "sales_return", "purchase", "purchase_return", "consumption"):
        if not sid:
            key = "system"
    elif key is None:
        key = "system"
    return dict(key=key, journal_id=int(je["journal_id"]),
                number=str(je.get("journal_number") or ""),
                date=je.get("entry_date"), source_type=src,
                source_id=int(sid) if sid else None,
                doc_id=int(sid) if sid and key not in ("journal", "opening", "system")
                else None,
                description=je.get("description_en") or "",
                label=CONN[key]["label"])


def _txn_for_form(key, form):
    """Same dict for a window that was opened from its own list screen."""
    doc_id = None
    if key == "sales":
        doc_id = getattr(form, "invoice_id", None)
    elif key == "purchase":
        doc_id = getattr(form, "purchase_id", None)
    elif key in ("sales_return", "purchase_return"):
        doc_id = getattr(form, "return_id", None)
    elif key in ("receipt", "payment"):
        doc_id = getattr(form, "payment_id", None)
    elif key == "expense":
        doc_id = getattr(form, "expense_id", None)
    elif key == "consumption":
        doc_id = getattr(form, "entry_id", None)
    elif key == "journal":
        jid = getattr(form, "journal_id", None)
        return dict(key=key, journal_id=jid, doc_id=None, number="",
                    source_type="manual", source_id=None, label=CONN[key]["label"])
    return dict(key=key, journal_id=None, doc_id=doc_id, number="", source_type=key,
                source_id=doc_id, label=CONN[key]["label"])


def _number_of(txn):
    """Readable number of the transaction (invoice no., payment no. …)."""
    key, did = txn["key"], txn.get("doc_id")
    try:
        if CONN[key]["doc"] and did:
            from modules import doc_edit
            return doc_edit.info(CONN[key]["doc"], did)[0]
        if key in ("receipt", "payment") and did:
            r = db.fetchone("SELECT payment_number FROM payments WHERE payment_id=?",
                            (did,)) or {}
            return str(r.get("payment_number") or did)
        if key == "expense" and did:
            r = db.fetchone("SELECT reference FROM expenses WHERE expense_id=?",
                            (did,)) or {}
            return str(r.get("reference") or f"EXP-{did}")
        if txn.get("journal_id") and not txn.get("number"):
            r = db.fetchone("SELECT journal_number FROM journal_entries "
                            "WHERE journal_id=?", (txn["journal_id"],)) or {}
            return str(r.get("journal_number") or "")
    except Exception:
        pass
    return txn.get("number") or ""


def _payment_type(pid):
    try:
        r = db.fetchone("SELECT payment_type FROM payments WHERE payment_id=?",
                        (pid,)) or {}
        return r.get("payment_type") or "receipt"
    except Exception:
        return "receipt"


def _release_grab(parent):
    """A modal report (e.g. party statement) must let the opened window work."""
    try:
        top = parent.winfo_toplevel()
        if top.grab_current() is not None:
            top.grab_current().grab_release()
    except Exception:
        pass


def _watch(win, on_change):
    """Refresh the caller (ledger / list) when the window closes."""
    if not on_change or win is None:
        return
    try:
        win.bind("<Destroy>", lambda e, w=win: _safe(on_change)
                 if e.widget is w else None, add="+")
    except Exception:
        pass


def _safe(fn):
    try:
        fn()
    except Exception:
        pass


# ============================================================
#  Open / edit / new / delete
# ============================================================
def open_txn(parent, journal_id, on_change=None, mode=None):
    """Double-click on a ledger line. mode None = the chosen connector mode."""
    txn = resolve(journal_id)
    if not txn:
        messagebox.showinfo("Transaction", "This entry no longer exists.", parent=parent)
        _safe(on_change) if on_change else None
        return None
    key = txn["key"]
    if not can(key, "view"):
        _say_not_allowed(key, "view", parent)
        return None
    mode = mode or mode_for(key)
    if mode == "edit" and not can(key, "edit"):
        mode = "view"              # no edit right → it opens read only
    _release_grab(parent)
    if mode == "voucher" or key in ("opening", "system"):
        return VoucherWindow(parent, txn, on_change)
    if mode == "view":
        return _open_view(parent, txn, on_change)
    return edit_txn(parent, txn, on_change)


def _open_view(parent, txn, on_change):
    key, did = txn["key"], txn["doc_id"]
    if key == "sales":
        from ui.invoices import InvoiceForm
        f = InvoiceForm(parent, invoice_id=did, view_only=True, on_save=on_change)
    elif key in ("sales_return", "purchase_return"):
        from ui.returns import ReturnForm
        f = ReturnForm(parent, mode=key.split("_")[0], return_id=did, view_only=True)
    elif key == "consumption":
        from ui.consumption import ConsumptionForm
        f = ConsumptionForm(parent, entry_id=did, on_save=on_change, view_only=True)
    else:
        # these windows have no read-only layout → show the voucher lines
        return VoucherWindow(parent, txn, on_change)
    _watch(getattr(f, "win", None), on_change)
    return f


def edit_txn(parent, txn, on_change=None):
    key, did = txn["key"], txn.get("doc_id")
    if key in ("opening", "system"):
        return VoucherWindow(parent, txn, on_change)
    if not can(key, "edit"):
        _say_not_allowed(key, "edit", parent)
        return None
    doc = CONN[key]["doc"]
    if doc and did:
        from modules import doc_edit
        why = doc_edit.block_reason(doc, did, "edit")
        if why:
            messagebox.showinfo(CONN[key]["label"],
                                why + "\n\nIt opens for viewing only.", parent=parent)
            return _open_view(parent, txn, on_change)
        q = doc_edit.ask_text(doc, did, "edit")
        if q and not messagebox.askyesno("Edit " + CONN[key]["label"], q, parent=parent):
            return None
    elif _locked(txn, parent, "Edit"):
        return None
    _release_grab(parent)
    f = None
    if key == "sales":
        from ui.invoices import InvoiceForm
        f = InvoiceForm(parent, invoice_id=did, on_save=on_change)
    elif key == "purchase":
        from ui.purchases import PurchaseForm
        f = PurchaseForm(parent, did, on_change)
    elif key in ("sales_return", "purchase_return"):
        from ui.returns import ReturnForm
        f = ReturnForm(parent, mode=key.split("_")[0], return_id=did)
    elif key in ("receipt", "payment"):
        from ui.payments import PaymentForm
        f = PaymentForm(parent, _payment_type(did), on_change, payment_id=did)
    elif key == "expense":
        from ui.expenses import ExpenseForm
        f = ExpenseForm(parent, on_saved=on_change, expense_id=did)
    elif key == "consumption":
        from ui.consumption import ConsumptionForm
        f = ConsumptionForm(parent, entry_id=did, on_save=on_change)
    elif key == "journal":          # v7.1: CR / BR / CP / BP / CT / JV in their own window
        from ui.multi_voucher import open_voucher
        f = open_voucher(parent, txn.get("journal_id"), on_change)
    _watch(getattr(f, "win", None), on_change)
    return f


def new_txn(parent, key, on_change=None):
    c = CONN.get(key)
    if not c or not c["new"]:
        return None
    if not can(key, "add"):
        _say_not_allowed(key, "add", parent)
        return None
    _release_grab(parent)
    f = None
    if key == "sales":
        from ui.invoices import InvoiceForm
        f = InvoiceForm(parent, invoice_id=None, on_save=on_change)
    elif key == "purchase":
        from ui.purchases import PurchaseForm
        f = PurchaseForm(parent, None, on_change)
    elif key in ("sales_return", "purchase_return"):
        flag = "allow_sales_return" if key == "sales_return" else "allow_purchase_return"
        if not cfg.flag(flag, True):
            messagebox.showwarning("Returns disabled",
                                   f"New {c['label'].lower()}s are turned off in Settings.",
                                   parent=parent)
            return None
        from ui.returns import ReturnForm
        f = ReturnForm(parent, mode=key.split("_")[0])
    elif key == "receipt":
        from ui.payments import PaymentForm
        f = PaymentForm(parent, "receipt", on_change)
    elif key == "payment":
        from ui.payments import PaymentForm
        f = PaymentForm(parent, "disbursement", on_change)
    elif key == "expense":
        from ui.expenses import ExpenseForm
        f = ExpenseForm(parent, on_saved=on_change)
    elif key == "consumption":
        from ui.consumption import ConsumptionForm
        f = ConsumptionForm(parent, on_save=on_change)
    elif key == "journal":
        from ui.accounting import JournalForm
        f = JournalForm(parent, on_save=on_change)
    _watch(getattr(f, "win", None), on_change)
    return f


def _locked(txn, parent, what):
    """Financial-year lock for payment / expense / journal (documents use
    doc_edit.block_reason)."""
    d = txn.get("date")
    if d is None and txn.get("journal_id"):
        try:
            d = (db.fetchone("SELECT entry_date FROM journal_entries WHERE journal_id=?",
                             (txn["journal_id"],)) or {}).get("entry_date")
        except Exception:
            d = None
    if not d:
        return False
    try:
        from modules import financial_year as fy
        msg = fy.guard_active(str(d)[:10])
    except Exception:
        msg = ""
    if msg:
        messagebox.showwarning(what, msg, parent=parent)
        return True
    return False


def delete_txn(parent, txn, on_change=None):
    """Delete a transaction with the same rules its own list screen uses.
    Returns True when it was deleted."""
    from modules.doc_actions import audit
    key, did = txn["key"], txn.get("doc_id")
    label = CONN[key]["label"]
    if key == "opening":
        messagebox.showwarning("Delete", "This is an opening balance.\n\nChange or clear "
                               "it in Accounts ▸ Opening Balances.", parent=parent)
        return False
    if key == "system":
        messagebox.showwarning("Delete", "This voucher was posted automatically "
                               f"({txn.get('source_type') or 'system'}).\n\nChange it "
                               "from the screen that made it (HR & Payroll, Stock, "
                               "Year-end).", parent=parent)
        return False
    if not can(key, "delete"):
        _say_not_allowed(key, "delete", parent)
        return False
    doc = CONN[key]["doc"]
    if key != "journal" and not did:
        messagebox.showinfo("Delete", "Nothing saved yet.", parent=parent)
        return False
    number = _number_of(txn)
    ok, msg = False, ""
    try:
        if doc:
            from modules import doc_edit
            why = doc_edit.block_reason(doc, did, "delete")
            if why:
                messagebox.showwarning("Delete " + label, why, parent=parent)
                return False
            # a confirmed document: type its number (v6.9.3); a draft: Yes / No
            if not doc_edit.confirm_delete(doc, did, parent):
                return False
            ok, msg = doc_edit.delete_document(doc, did)
        elif key in ("receipt", "payment"):
            if _locked(txn, parent, "Delete"):
                return False
            if not messagebox.askyesno("Delete " + label,
                                       f"Delete {label.lower()} {number}?\n"
                                       "Invoices it settled get their balance back.",
                                       parent=parent):
                return False
            ptype = _payment_type(did)
            from modules.doc_actions import delete_linked_journals
            from modules import allocation
            with db.transaction():
                delete_linked_journals("receipt" if ptype == "receipt" else "payment", did)
                allocation.release(did)
                db.execute("DELETE FROM payments WHERE payment_id=?", (did,))
                audit("delete", "payment", did, number)
            ok = True
        elif key == "expense":
            if _locked(txn, parent, "Delete"):
                return False
            if not messagebox.askyesno("Delete " + label,
                                       f"Delete expense {number}?\n"
                                       "Its posted journal entry is removed too.",
                                       parent=parent):
                return False
            from ui.expenses import _delete_expense_journals
            with db.transaction():
                db.execute("DELETE FROM expenses WHERE expense_id=?", (did,))
                _delete_expense_journals(did, None)
                audit("delete", "expense", did, number)
            ok = True
        elif key == "journal":
            jid = txn.get("journal_id")
            if not jid:
                messagebox.showinfo("Delete", "Nothing saved yet.", parent=parent)
                return False
            real = resolve(jid)
            if real and real["key"] != "journal":
                messagebox.showwarning(
                    "Delete Voucher",
                    f"{real['number']} was posted by a {real['label'].lower()}.\n\n"
                    "Delete that transaction instead — its voucher goes with it.",
                    parent=parent)
                return False
            if _locked(txn, parent, "Delete"):
                return False
            if not messagebox.askyesno("Delete Voucher",
                                       f"{number} is POSTED — deleting it changes "
                                       "account balances.\n\nDelete anyway?",
                                       parent=parent):
                return False
            db.execute("DELETE FROM journal_entries WHERE journal_id=?", (jid,))
            audit("delete", "voucher", jid, number)
            ok = True
    except Exception as e:
        ok, msg = False, str(e)[:300]
    if not ok:
        messagebox.showerror("Delete " + label, msg or "Not deleted.", parent=parent)
        return False
    _safe(on_change) if on_change else None
    return True


# ============================================================
#  The action bar on every transaction window
# ============================================================
def attach(form, key, on_change=None, view_only=None, compact=False):
    """Put the connector bar on a transaction window. Called by every form
    at the end of its __init__ (safe to call twice — it attaches once).
    compact=True: the window has its own Save / Delete / Close toolbar
    (Tally-style Sales Invoice) → the bar adds only rights, New, Voucher."""
    win = getattr(form, "win", None)
    if win is None or getattr(win, "_txn_bar", None) is not None:
        return None
    if on_change is None:
        on_change = (getattr(form, "on_save", None) or getattr(form, "on_saved", None))
    if view_only is None:
        view_only = bool(getattr(form, "view_only", False))
    try:
        bar = TxnBar(win, form, key, on_change, view_only, compact=compact)
        win._txn_bar = bar
        return bar
    except Exception:
        return None


def _title_band(win):
    """The window's coloured title line (first packed frame, full width),
    or None. v6.9: the connector buttons sit IN it — one header line."""
    C = cfg.theme()
    plain = {str(C.get("content_bg", "")).upper(), str(C.get("card_bg", "")).upper()}
    for fr in win.pack_slaves()[:2]:
        try:
            if fr.winfo_class() != "Frame" or str(fr.cget("bg")).upper() in plain:
                continue
            if fr.pack_info().get("fill") in ("x", "both"):
                return fr
        except Exception:
            continue
    return None


def _tip(widget, text):
    """Small hover tip (why a button is greyed out)."""
    box = {}

    def show(_e=None):
        try:
            t = tk.Toplevel(widget)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            tk.Label(t, text=text, font=("Segoe UI", 8), bg="#111827", fg="white",
                     padx=6, pady=2).pack()
            t.geometry("+%d+%d" % (widget.winfo_rootx(),
                                   widget.winfo_rooty() + widget.winfo_height() + 2))
            box["t"] = t
        except Exception:
            pass

    def hide(_e=None):
        try:
            box.pop("t").destroy()
        except Exception:
            pass
    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")


class TxnBar:
    def __init__(self, win, form, key, on_change, view_only, txn=None,
                 compact=False, voucher_btn=True):
        self.win, self.form, self.key = win, form, key
        self.on_change, self.view_only = on_change, view_only
        self._txn = txn
        C = cfg.theme()
        self.C = C
        r = rights(key)
        own = compact                # the form has its own Save / Delete toolbar
        band = _title_band(win)
        in_band = band is not None
        if in_band:
            # one header line: title on the left, actions on the right.
            # The form keeps its own Save (footer) and Esc / ✕ closes it.
            host = tk.Frame(band, bg=band["bg"])
            host.pack(side="right", padx=8)
            inner = host
        else:
            bar = tk.Frame(win, bg=C.get("primary_light", C["card_bg"]),
                           highlightbackground=C["border"], highlightthickness=1)
            bar.pack(side="top", fill="x")
            inner = tk.Frame(bar, bg=bar["bg"])
            inner.pack(fill="x", padx=10, pady=4)
        self.frame = inner
        win._txn_bar = self
        words = {"add": "add", "edit": "change", "delete": "delete", "view": "open"}

        def btn(text, cmd, ok, fg=None, need=None):
            b = tk.Button(inner, text=text, font=("Segoe UI", 8 if in_band else 9, "bold"),
                          bg=C["card_bg"], fg=fg or C["text_primary"], relief="flat",
                          padx=8 if in_band else 10, pady=0 if in_band else 2,
                          cursor="hand2" if ok else "arrow",
                          highlightthickness=1, highlightbackground=C["border"],
                          command=cmd if ok else (lambda: None),
                          state="normal" if ok else "disabled")
            b.pack(side="right", padx=(4, 0), pady=3 if in_band else 0)
            if not ok and need:
                _tip(b, "Your user type can't %s %s — ask the administrator "
                        "(Users & Rights)." % (words.get(need, need), CONN[key]["label"].lower()))
            return b

        # buttons first (right side), so a narrow window never hides them
        if not in_band and not own:
            # like ✕: asks first when the form has unsaved lines
            from ui import close_guard as _cg
            btn("✖ Close", lambda: _cg.request_close(win), True)
        if key not in ("opening", "system"):
            if not own:
                btn("🗑 Delete", self.delete, r["delete"], fg=C.get("danger", "#DC2626"),
                    need="delete")
            if (not in_band and not own and form is not None and hasattr(form, "_save")
                    and not view_only):
                btn("💾 Save", self.save, r["edit"] or r["add"],
                    fg=C.get("success", "#16A34A"), need="edit")
            if view_only:
                btn("✏ Edit", self.edit, r["edit"], need="edit")
            btn("➕ New", self.new, CONN[key]["new"] and r["add"], need="add")
        if voucher_btn:
            btn("📄 Voucher", self.voucher, r["view"], need="view")
        self._bind_keys(r)
        if not in_band:
            tk.Label(inner, text="🔗 " + CONN[key]["label"], font=("Segoe UI", 9, "bold"),
                     bg=inner["bg"], fg=C["text_primary"]).pack(side="left")
            tk.Label(inner, text="  " + " ".join(
                         ("✔" if r[a] else "✖") + a.title()
                         for a in ("view", "add", "edit", "delete")),
                     font=("Segoe UI", 8), bg=inner["bg"],
                     fg=C["text_secondary"]).pack(side="left")

    def _bind_keys(self, r):
        """v6.9.3: the same keys in every transaction window (ui/shortcuts.TXN).
        A key the window already uses for itself is left alone."""
        win, key, form = self.win, self.key, self.form

        def bind(seqs, fn, ok=True):
            if not ok:
                return
            for seq in seqs:
                try:
                    if not win.bind(seq):
                        win.bind(seq, lambda e, f=fn: (f(), "break")[1])
                except Exception:
                    pass
        editable = (form is not None and hasattr(form, "_save") and not self.view_only
                    and key not in ("opening", "system"))
        bind(("<Control-s>", "<Control-S>"), self.save, editable and (r["edit"] or r["add"]))
        bind(("<Control-n>",), self.new, CONN[key]["new"] and r["add"])
        bind(("<Control-e>",), self.edit, self.view_only and r["edit"])
        bind(("<Control-Delete>",), self.delete,
             key not in ("opening", "system") and r["delete"] and not self.view_only)
        bind(("<Control-j>",), self.voucher, r["view"])

        def help_():
            from ui import shortcuts
            shortcuts.show(win, "transaction")
        bind(("<F1>",), help_)

        # Esc = ✕ (ui/close_guard.py) — but a cell editor / dropdown that
        # handles Esc itself keeps it, and unsaved lines ask first
        try:
            from ui import close_guard as _cg
            if not win.bind("<Escape>"):
                _cg.bind_escape(win)
        except Exception:
            pass

    # current transaction (the form may have saved a new one meanwhile)
    def txn(self):
        if self.form is not None:
            t = _txn_for_form(self.key, self.form)
            if self._txn:
                t["journal_id"] = t.get("journal_id") or self._txn.get("journal_id")
                t["date"] = self._txn.get("date")
            return t
        return dict(self._txn or {})

    def save(self):
        f = self.form
        try:
            doc = CONN[self.key]["doc"]
            if doc:
                did = self.txn().get("doc_id")
                status = ""
                if did:
                    from modules import doc_edit
                    status = doc_edit.info(doc, did)[1]
                # keep the document's state: a confirmed one stays confirmed
                f._save(confirm=(status == "confirmed"))
            else:
                f._save()
        except Exception as e:
            messagebox.showerror("Save", str(e)[:300], parent=self.win)

    def delete(self):
        t = self.txn()
        if delete_txn(self.win, t, self.on_change):
            _safe(self.win.destroy)

    def edit(self):
        t = self.txn()
        parent = self.win.master or self.win
        # close this view like ✕ (asks only when something is unsaved);
        # kept open → no second window
        from ui import close_guard as _cg
        if not _cg.request_close(self.win, quiet=True):
            return
        edit_txn(parent, t, self.on_change)

    def new(self):
        new_txn(self.win.master or self.win, self.key, self.on_change)

    def voucher(self):
        t = self.txn()
        if not t.get("journal_id"):
            t["journal_id"] = _main_journal(t)
        if not t.get("journal_id"):
            messagebox.showinfo("Voucher", "No posted voucher yet (draft or not saved).",
                                parent=self.win)
            return
        VoucherWindow(self.win, t, self.on_change, bar=False)


def _main_journal(txn):
    srcs = [s for s in CONN[txn["key"]]["sources"] if not s.endswith("*")]
    did = txn.get("doc_id")
    if not did or not srcs:
        return None
    try:
        q = ",".join("?" * len(srcs))
        r = db.fetchone(f"SELECT TOP 1 journal_id FROM journal_entries WHERE "
                        f"source_id=? AND source_type IN ({q}) ORDER BY journal_id",
                        tuple([did] + srcs))
        return (r or {}).get("journal_id")
    except Exception:
        return None


# ============================================================
#  Read-only voucher window (journal lines)
# ============================================================
class VoucherWindow:
    def __init__(self, parent, txn, on_change=None, bar=True):
        C = cfg.theme()
        self.txn, self.on_change = txn, on_change
        self.win = tk.Toplevel(parent)
        self.win.title(f"Voucher {txn.get('number') or ''}".strip())
        self.win.configure(bg=C["content_bg"])
        self.win.geometry("760x460")
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        hdr = tk.Frame(self.win, bg=C["primary"], height=40)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"📄  {txn['label']}  ·  {txn.get('number') or ''}",
                 font=("Segoe UI", 12, "bold"), bg=C["primary"],
                 fg="white").pack(side="left", padx=16)
        if bar:
            self.form = None
            self.view_only = True
            TxnBar(self.win, None, txn["key"], on_change, True, txn=txn,
                   voucher_btn=False)
        info = tk.Frame(self.win, bg=C["content_bg"])
        info.pack(fill="x", padx=16, pady=(8, 4))
        h = {}
        try:
            h = db.fetchone("SELECT * FROM journal_entries WHERE journal_id=?",
                            (txn["journal_id"],)) or {}
        except Exception:
            pass
        d = h.get("entry_date")
        dtxt = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")[:10]
        tk.Label(info, text=f"Date: {dtxt}     Source: "
                            f"{(h.get('source_type') or '—').replace('_', ' ')}     "
                            f"Ref: {h.get('reference') or ''}",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        tk.Label(info, text=h.get("description_en") or "", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(anchor="w")
        wrap = tk.Frame(self.win, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        cols = ("acct", "desc", "debit", "credit")
        tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for cid, txt, w, anc in (("acct", "Account", 240, "w"),
                                 ("desc", "Description", 240, "w"),
                                 ("debit", "Debit", 110, "e"),
                                 ("credit", "Credit", 110, "e")):
            tree.heading(cid, text=txt)
            tree.column(cid, width=w, anchor=anc)
        tree.pack(fill="both", expand=True)
        dr = cr = 0.0
        try:
            rows = db.fetchall(
                "SELECT a.account_code, a.account_name_en, jl.description, jl.debit, "
                "jl.credit FROM journal_lines jl JOIN accounts a "
                "ON a.account_id=jl.account_id WHERE jl.journal_id=? "
                "ORDER BY jl.line_number", (txn["journal_id"],)) or []
        except Exception:
            rows = []
        for r in rows:
            dr += _f(r["debit"]); cr += _f(r["credit"])
            tree.insert("", "end", values=(
                f"{r['account_code']} · {r['account_name_en']}", r.get("description") or "",
                f"{_f(r['debit']):,.2f}" if _f(r["debit"]) else "",
                f"{_f(r['credit']):,.2f}" if _f(r["credit"]) else ""))
        tree.insert("", "end", values=("", "Total", f"{dr:,.2f}", f"{cr:,.2f}"))


# ============================================================
#  "🔗 Connectors" — see and choose
# ============================================================
class ConnectorChooser:
    def __init__(self, parent, on_saved=None):
        C = cfg.theme()
        self.on_saved = on_saved
        self.win = tk.Toplevel(parent)
        self.win.title("Transaction Connectors")
        self.win.configure(bg=C["content_bg"])
        self.win.geometry("1120x560")
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        hdr = tk.Frame(self.win, bg=C["primary"], height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="🔗  Transaction Connectors — what a ledger line opens",
                 font=("Segoe UI", 12, "bold"), bg=C["primary"],
                 fg="white").pack(side="left", padx=16)
        tk.Label(self.win, text="Every ledger line is connected to the window that made "
                                "it. Choose what a double-click opens for each type. "
                                "Buttons in each window follow your user rights.",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"],
                 wraplength=940, justify="left").pack(anchor="w", padx=16, pady=(8, 4))

        grid = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        grid.pack(fill="both", expand=True, padx=16, pady=4)
        heads = ["Transaction type", "Ledger source codes", "Opens", "View", "Add",
                 "Edit", "Delete", "Double-click opens"]
        for c, h in enumerate(heads):
            tk.Label(grid, text=h, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                     fg=C["text_primary"]).grid(row=0, column=c, sticky="w",
                                                 padx=8, pady=(8, 4))
        self.vars = {}
        cur = modes()
        for i, (key, c) in enumerate(CONNECTORS, start=1):
            r = rights(key)
            tk.Label(grid, text=c["label"], font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_primary"]).grid(row=i, column=0, sticky="w", padx=8, pady=3)
            tk.Label(grid, text=", ".join(s or "(blank)" for s in c["sources"]),
                     font=("Consolas", 8), bg=C["card_bg"], wraplength=230,
                     justify="left", fg=C["text_secondary"]).grid(
                         row=i, column=1, sticky="w", padx=8)
            tk.Label(grid, text=c["window"], font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_primary"]).grid(row=i, column=2, sticky="w", padx=8)
            for j, a in enumerate(("view", "add", "edit", "delete")):
                tk.Label(grid, text="✔" if r[a] else "✖", font=("Segoe UI", 10, "bold"),
                         bg=C["card_bg"], fg=C.get("success", "#16A34A") if r[a]
                         else C.get("danger", "#DC2626")).grid(row=i, column=3 + j, padx=6)
            if key in ("opening", "system"):
                tk.Label(grid, text="Voucher lines (fixed)", font=("Segoe UI", 9),
                         bg=C["card_bg"], fg=C["text_secondary"]).grid(
                             row=i, column=7, sticky="w", padx=8)
                continue
            v = tk.StringVar(value=MODE_LABEL.get(cur.get(key, "edit"), "Edit window"))
            cb = ttk.Combobox(grid, textvariable=v, state="readonly", width=16,
                              values=[lbl for _m, lbl in MODES])
            cb.grid(row=i, column=7, sticky="w", padx=8)
            self.vars[key] = v

        foot = tk.Frame(self.win, bg=C["content_bg"])
        foot.pack(fill="x", padx=16, pady=10)
        tk.Label(foot, text="Rights are set in Users & Rights (module per type: Sales, "
                            "Purchase, Receipt, Payment, Accounts = expenses, Journal).",
                 font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        tk.Button(foot, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  relief="flat", padx=14, pady=5, highlightthickness=1,
                  highlightbackground=C["border"],
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(foot, text="💾 Save choice", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=5,
                  command=self._save).pack(side="right")

    def _save(self):
        back = {lbl: m for m, lbl in MODES}
        save_modes({k: back.get(v.get(), "edit") for k, v in self.vars.items()})
        if self.on_saved:
            _safe(self.on_saved)
        self.win.destroy()


# ============================================================
#  Wire a Treeview (ledger / statement) to the connector
# ============================================================
def bind_tree(tree, journal_of, on_change=None):
    """Double-click / Enter opens, right-click shows Open · Edit · Delete ·
    Voucher · New ▸ …   journal_of(iid) → journal_id or None."""
    def current():
        sel = tree.selection() or ((tree.focus(),) if tree.focus() else ())
        return journal_of(sel[0]) if sel else None

    def do_open(_e=None, mode=None):
        jid = current()
        if jid:
            open_txn(tree, jid, on_change, mode=mode)
        return "break"

    def do_edit():
        jid = current()
        t = resolve(jid) if jid else None
        if t:
            if not can(t["key"], "view"):
                return _say_not_allowed(t["key"], "view", tree)
            edit_txn(tree, t, on_change)

    def do_delete():
        jid = current()
        t = resolve(jid) if jid else None
        if t:
            delete_txn(tree, t, on_change)

    menu = tk.Menu(tree, tearoff=0)

    def popup(e):
        iid = tree.identify_row(e.y)
        if iid:
            tree.selection_set(iid)
            tree.focus(iid)
        jid = current()
        t = resolve(jid) if jid else None
        menu.delete(0, "end")
        if t:
            k = t["key"]
            menu.add_command(label=f"🔗 {t['label']}  {t.get('number') or ''}",
                             state="disabled")
            menu.add_separator()
            menu.add_command(label="👁  Open  (Enter / double-click)",
                             command=lambda: do_open(),
                             state="normal" if can(k, "view") else "disabled")
            if k not in ("opening", "system"):
                menu.add_command(label="✏  Edit", command=do_edit,
                                 state="normal" if can(k, "edit") else "disabled")
                menu.add_command(label="🗑  Delete", command=do_delete,
                                 state="normal" if can(k, "delete") else "disabled")
            menu.add_command(label="📄  Voucher lines",
                             command=lambda: do_open(mode="voucher"),
                             state="normal" if can(k, "view") else "disabled")
            menu.add_separator()
        sub = tk.Menu(menu, tearoff=0)
        for k, c in CONNECTORS:
            if c["new"]:
                sub.add_command(label=c["label"],
                                command=lambda k=k: new_txn(tree, k, on_change),
                                state="normal" if can(k, "add") else "disabled")
        menu.add_cascade(label="➕  New", menu=sub)
        menu.add_separator()
        menu.add_command(label="🔗  Connectors…",
                         command=lambda: ConnectorChooser(tree))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    tree.bind("<Double-1>", do_open)
    tree.bind("<Return>", do_open)
    tree.bind("<Delete>", lambda e: do_delete())
    tree.bind("<Button-3>", popup)
    return dict(open=do_open, edit=do_edit, delete=do_delete, current=current)


def new_menu(parent, button, on_change=None):
    """'➕ New ▾' menu for a toolbar button."""
    m = tk.Menu(button, tearoff=0)
    for k, c in CONNECTORS:
        if c["new"]:
            m.add_command(label=c["label"],
                          command=lambda k=k: new_txn(parent, k, on_change),
                          state="normal" if can(k, "add") else "disabled")
    try:
        m.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
    finally:
        m.grab_release()
