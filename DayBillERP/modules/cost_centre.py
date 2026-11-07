# ============================================================
# DayBill ERP - cost centre on documents (v7.16.0)
# The voucher, expense or purchase says which cost centre it is for
# (Masters ▸ Cost Centres); every journal line it posts carries it, so
# Reports ▸ Cost Centre Report shows income and costs per cost centre.
#
#   ready()                       the database has the columns
#   choices()                     {label: id} of the active cost centres
#   label(cid)
#   stamp(source_types, source_id, cid)   journals of a document
#   doc_stamp(table, idcol, doc_id, source_types)  from the doc's own column
# ============================================================
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


def ready():
    try:
        from modules import masters as M
        return M.ready("cost_centers") and M.col_ok("journal_lines", "cost_center_id")
    except Exception:
        return False


def doc_ready(table):
    try:
        from modules import masters as M
        return ready() and M.col_ok(table, "cost_center_id")
    except Exception:
        return False


def choices(include=None):
    try:
        from modules import masters as M
        return {l: i for i, l in M.choices("cost_centers", include=include)}
    except Exception:
        return {}


def label(cid):
    try:
        from modules import masters as M
        return M.label_of("cost_centers", cid) if cid else ""
    except Exception:
        return ""


def stamp(source_types, source_id, cid):
    if not source_id or not ready():
        return
    sts = [s for s in (source_types or []) if s]
    if not sts:
        return
    q = ",".join("?" * len(sts))
    try:
        db.execute("UPDATE journal_entries SET cost_center_id=? WHERE source_id=? AND source_type "
                   "IN (%s)" % q, tuple([cid, int(source_id)] + sts))
        db.execute("UPDATE journal_lines SET cost_center_id=? WHERE journal_id IN (SELECT "
                   "journal_id FROM journal_entries WHERE source_id=? AND source_type IN (%s))"
                   % q, tuple([cid, int(source_id)] + sts))
    except Exception:
        pass


def doc_stamp(table, idcol, doc_id, source_types):
    """The document's own cost_center_id → its journals (after a re-post)."""
    if not doc_ready(table):
        return
    try:
        cid = db.execute_scalar("SELECT cost_center_id FROM %s WHERE %s=?" % (table, idcol),
                                (int(doc_id),))
    except Exception:
        return
    stamp(source_types, doc_id, cid)


def save_doc(table, idcol, doc_id, cid):
    if not doc_ready(table) or not doc_id:
        return
    try:
        db.execute("UPDATE %s SET cost_center_id=? WHERE %s=?" % (table, idcol), (cid, int(doc_id)))
    except Exception:
        pass


def of_doc(table, idcol, doc_id):
    if not doc_ready(table) or not doc_id:
        return None
    try:
        return db.execute_scalar("SELECT cost_center_id FROM %s WHERE %s=?" % (table, idcol),
                                 (int(doc_id),))
    except Exception:
        return None
