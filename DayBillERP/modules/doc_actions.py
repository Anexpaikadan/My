# ============================================================
# DayBill ERP - Shared document actions (delete / report)
# ------------------------------------------------------------
# One place for the cleanup every transaction delete needs, so
# Sales, Purchases, Returns, Vouchers, Expenses, and Payments all
# behave the same:
#   * remove the GL journal entries the document posted
#     (journal_lines cascade-delete with journal_entries)
#   * write an audit-log row
# Plus a tiny wrapper that turns any Treeview list into an
# Excel export / printable PDF report in two lines per module.
# ============================================================

from config.database import db


def delete_linked_journals(source_type, source_id):
    """Remove every journal entry a document created when it posted.
    journal_lines has ON DELETE CASCADE, so the header delete is enough."""
    try:
        db.execute(
            "DELETE FROM journal_entries WHERE source_type=? AND source_id=?",
            (source_type, int(source_id)))
        return True
    except Exception:
        return False


def remove_document_effects(source_type, source_id):
    """Before deleting a sales / POS bill, purchase or return: take its
    stock movements back out and remove every journal it posted
    (sale + cost of sales, return + cost reversal …)."""
    try:
        from modules import doc_posting
        kind = doc_posting.SOURCE_TO_KIND.get(source_type)
        if kind:
            doc_posting.remove(kind, int(source_id))
            return True
    except Exception:
        pass
    return delete_linked_journals(source_type, source_id)


def audit(action, entity, entity_id, detail=""):
    try:
        from modules import audit as _a
        _a.log(action, entity, entity_id, detail)
    except Exception:
        pass


def tree_rows(tree):
    """All rows of a ttk.Treeview as list-of-lists (what's on screen,
    i.e. respects the current filter)."""
    return [list(tree.item(i)["values"]) for i in tree.get_children()]


def shown_view(tree, headers, rows, col_align=None):
    """Only the columns shown on screen, in the screen order (v6.2 columns
    tool: hidden / moved columns are left out / moved in the file too)."""
    try:
        from ui.table_columns import export_view
        return export_view(tree, list(headers), rows, col_align)
    except Exception:
        return headers, rows, col_align


def export_tree_excel(parent, tree, name, headers, title=None, summary=None):
    from modules.report_export import export_excel
    headers, rows, _a = shown_view(tree, headers, tree_rows(tree))
    return export_excel(parent, name, headers, rows,
                        title=title, summary=summary)


def export_tree_pdf(parent, tree, name, headers, title=None, subtitle=None,
                    summary=None, col_align=None):
    from modules.report_export import export_pdf
    headers, rows, col_align = shown_view(tree, headers, tree_rows(tree), col_align)
    return export_pdf(parent, name, headers, rows, title=title,
                      subtitle=subtitle, summary=summary, col_align=col_align)
