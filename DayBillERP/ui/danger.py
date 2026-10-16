# ============================================================
# DayBill ERP - dangerous actions need a right AND a typed word (v6.9.3)
# ------------------------------------------------------------
# Actions that change many records or cannot be undone (Clear Stock,
# year close / reopen, restore a backup, regenerate payroll, bulk price
# changes, disconnect ZATCA …) must never happen on one click:
#
#   if not danger.gate(win, "stock_adjustment", "approve",
#                      "Clear Stock", "Every product of this branch goes to 0.",
#                      word="CLEAR"):
#       return
#   … do it …
#   danger.audit("clear", "stock", None, "all products of branch 2")
#
# gate() = the user right (refused with the usual message) + the user
# must type the word exactly (not case sensitive) + a "cannot be undone"
# warning. Every refusal and every confirmed action is written to the
# Audit Log.
# ============================================================

from tkinter import messagebox, simpledialog


def need(module, action, parent=None):
    """The user right; shows the usual 'not allowed' message when missing."""
    try:
        from modules import permissions as perm
        return bool(perm.allowed(module, action, parent=parent))
    except Exception:
        return False


def confirm_typed(parent, title, message, word="YES"):
    """True only when the user types `word`. Cancel / anything else = False."""
    w = str(word or "YES").strip().upper()
    try:
        got = simpledialog.askstring(
            "⚠ " + title,
            "%s\n\nThis cannot be undone.\n\nType  %s  to go ahead:" % (message, w),
            parent=parent)
    except Exception:
        got = None
    if got is None:
        return False
    if str(got).strip().upper() != w:
        messagebox.showinfo(title, "Not done — the word did not match.", parent=parent)
        return False
    return True


def audit(action, entity, entity_id=None, detail=""):
    try:
        from modules.doc_actions import audit as _a
        _a(action, entity, entity_id, str(detail or "")[:300])
    except Exception:
        try:
            from modules import audit as _au
            _au.log(action, entity, entity_id, str(detail or "")[:300])
        except Exception:
            pass


def gate(parent, module, action, title, message, word="YES"):
    """Right + typed confirmation. Logs refusals and confirmations."""
    if not need(module, action, parent):
        audit("refused", module, None, "%s (%s.%s missing)" % (title, module, action))
        return False
    if not confirm_typed(parent, title, message, word):
        return False
    audit("confirmed", module, None, title)
    return True
