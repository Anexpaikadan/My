# ============================================================
# DayBill ERP - Edit / delete saved documents (one set of rules)
# ------------------------------------------------------------
# Sales invoices / POS bills, purchases, sales & purchase returns can
# be corrected after they were CONFIRMED:
#
#   Edit    the document opens in its form; on Save the old stock
#           movement and journal are reversed and the new one posted
#           (doc_posting.sync) — nothing is ever doubled.
#   Delete  stock goes back, journals are removed, receipts / payments
#           settled on it become advances again, an audit row is kept.
#
# Not allowed when
#   • Settings ▸ Sales ▸ "Allow edit / delete of confirmed documents" is off
#   • the document's date is in a closed / locked financial year
#   • a sales invoice was already REPORTED / CLEARED to ZATCA
#     (the law wants a credit note = Sales Return instead)
#   • (edit only, v6.9.5) the document is cancelled, or it is a debit
#     note (its lines are amounts — delete it and make it again)
# ============================================================

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db

try:
    from config import settings as cfg
except Exception:                                  # pragma: no cover
    cfg = None

LABEL = {"sales": "Sales invoice", "purchase": "Purchase invoice",
         "sales_return": "Sales return", "purchase_return": "Purchase return",
         "consumption": "Consumable entry"}


def _row(kind, doc_id):
    from modules import doc_posting as dp
    k = dp.KINDS[kind]
    try:
        return db.fetchone(f"SELECT * FROM {k['table']} WHERE {k['id']}=?",
                           (int(doc_id),)) or {}
    except Exception:
        return {}


def info(kind, doc_id):
    """(number, status, date) of a document."""
    from modules import doc_posting as dp
    k = dp.KINDS[kind]
    r = _row(kind, doc_id)
    return (str(r.get(k["number"]) or doc_id),
            str(r.get(k["status"]) or "").lower(),
            r.get(k["date"]))


def allowed_posted():
    try:
        return cfg.flag("allow_edit_confirmed", True)
    except Exception:
        return True


def block_reason(kind, doc_id, action="edit"):
    """'' when the document may be edited / deleted, else why not."""
    if kind not in LABEL or not doc_id:
        return ""
    r = _row(kind, doc_id)
    if not r:
        return ""
    number, status, d = info(kind, doc_id)
    if status == "confirmed" and not allowed_posted():
        return (f"{number} is confirmed. Editing / deleting confirmed documents is "
                "switched off (Settings ▸ Sales ▸ Allow edit / delete of confirmed "
                "documents).")
    if status == "cancelled" and action == "edit":
        # v6.9.5: Edit + Save & Confirm brought a cancelled bill back (stock
        # out and books again) — cancelling "cannot be undone"
        return f"{number} is cancelled — it can't be changed."
    if kind == "sales" and action == "edit" and str(r.get("invoice_kind") or "").lower() == "debit":
        # v6.9.5: its lines are amounts, not items — the Sales Invoice window
        # showed it empty, and items typed there replaced the note's lines
        return (f"{number} is a debit note — it can't be changed in the Sales Invoice "
                "window. Delete it and make it again (Debit Notes).")
    if kind in ("sales", "sales_return"):
        z = str(r.get("zatca_status") or "").lower()
        if z in ("reported", "cleared"):
            return (f"{number} was already {z} to ZATCA — it can't be changed. "
                    "Make a Sales Return (credit note) for it instead.")
        if r.get("zatca_icv"):              # signed into the ZATCA Phase 2 chain
            return (f"{number} is already signed for ZATCA (e-invoicing) — it can't be "
                    "changed or deleted. Make a Sales Return (credit note) for it instead.")
    try:
        from modules import financial_year as fy
        msg = fy.guard_active(str(d)[:10]) if d else ""
        if msg:
            return msg
    except Exception:
        pass
    return ""


def ask_text(kind, doc_id, action="edit"):
    """Question shown before editing / deleting a CONFIRMED document
    ('' when it is a draft / cancelled one → no extra question)."""
    number, status, _d = info(kind, doc_id)
    if status != "confirmed":
        return ""
    what = LABEL.get(kind, "Document")
    if action == "delete":
        return (f"{what} {number} is CONFIRMED.\n\n"
                "Deleting it will:\n"
                "  • put the stock back\n"
                "  • remove its entries from the accounts\n"
                "  • turn money received / paid on it into an advance\n\n"
                "Delete it?")
    return (f"{what} {number} is CONFIRMED.\n\n"
            "You can change it. When you save, the old stock and account "
            "entries are reversed and the new ones posted automatically.\n\n"
            "Open it for editing?")


def confirm_delete(kind, doc_id, parent=None):
    """v6.9.3: deleting a CONFIRMED document is never one click — the user
    types its number. A draft / cancelled one: one Yes / No question."""
    number, status, _d = info(kind, doc_id)
    what = LABEL.get(kind, "Document")
    if status == "confirmed":
        from ui import danger
        return danger.confirm_typed(
            parent, "Delete " + what,
            (ask_text(kind, doc_id, "delete") or "%s %s is CONFIRMED." % (what, number))
            .replace("\n\nDelete it?", ""), word=number)
    from tkinter import messagebox
    return messagebox.askyesno("Delete " + what,
                               "Delete %s %s (%s)?" % (what.lower(), number, status or "draft"),
                               parent=parent)


def delete_document(kind, doc_id):
    """Remove a document completely (stock, journals, links, lines, header).
    Returns (True, number) or (False, error)."""
    from modules import doc_posting as dp
    from modules.doc_actions import audit
    k = dp.KINDS[kind]
    number, status, _d = info(kind, doc_id)
    try:
        with db.transaction():          # all of it goes, or nothing does (v5.27)
            dp.remove(kind, int(doc_id))
            db.execute(f"DELETE FROM {k['lines']} WHERE {k['id']}=?", (int(doc_id),))
            db.execute(f"DELETE FROM {k['table']} WHERE {k['id']}=?", (int(doc_id),))
            audit("delete", k["ref"], int(doc_id), f"{number} ({status})")
        return True, number
    except Exception as e:
        return False, str(e)[:300]
