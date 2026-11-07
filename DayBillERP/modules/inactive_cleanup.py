# ============================================================
# DayBill ERP - Delete Inactive Transactions (v7.12.0)
# Clears old DRAFT and CANCELLED documents only. Confirmed documents are
# never touched. Each one goes through doc_edit.delete_document (stock,
# journals, lines and header together, and an audit-log line), and the
# same rules as the Delete button apply: ZATCA-signed bills, a closed
# financial year … are skipped, with the reason.
# ============================================================
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

STATUSES = ("draft", "cancelled")


def kinds():
    from modules import doc_edit
    return list(doc_edit.LABEL.items())          # [(kind, label)]


def find(before, kind_keys=None, statuses=STATUSES):
    """Draft / cancelled documents dated before `before` (YYYY-MM-DD):
    [{kind, label, id, number, date, status, total}]"""
    from modules import doc_posting as dp
    from modules import doc_edit
    out = []
    sts = [s for s in statuses if s in STATUSES]
    if not sts:
        return out
    for kind, label in doc_edit.LABEL.items():
        if kind_keys and kind not in kind_keys:
            continue
        k = dp.KINDS.get(kind)
        if not k:
            continue
        sql = ("SELECT %s AS id, %s AS number, %s AS d, %s AS st FROM %s WHERE %s < ? AND "
               "LOWER(ISNULL(%s,'')) IN (%s) ORDER BY %s"
               % (k["id"], k["number"], k["date"], k["status"], k["table"], k["date"],
                  k["status"], ",".join("?" * len(sts)), k["date"]))
        try:
            rows = db.fetchall(sql, tuple([str(before)[:10]] + sts)) or []
        except Exception:
            rows = []
        for r in rows:
            out.append(dict(kind=kind, label=label, id=r["id"], number=str(r["number"] or r["id"]),
                            date=str(r["d"] or "")[:10], status=str(r["st"] or "").lower()))
    return out


def delete(items):
    """Delete the found documents → (deleted [(label, number)],
    skipped [(label, number, why)])."""
    from modules import doc_edit
    done, skipped = [], []
    for it in items:
        if it.get("status") not in STATUSES:              # never a confirmed one
            skipped.append((it["label"], it["number"], "not a draft / cancelled document"))
            continue
        why = doc_edit.block_reason(it["kind"], it["id"], "delete")
        if why:
            skipped.append((it["label"], it["number"], why))
            continue
        ok, msg = doc_edit.delete_document(it["kind"], it["id"])
        if ok:
            done.append((it["label"], it["number"]))
        else:
            skipped.append((it["label"], it["number"], msg))
    return done, skipped
