# ============================================================
# DayBill ERP - Message Templates (v7.12.0)
# Ready-made WhatsApp / SMS / e-mail texts. The list is kept on the
# Masters page (Other ▸ Message Templates); the WhatsApp send window
# offers them in a "Template" box.
#
# Words in {braces} are filled in when the message is made:
#   {customer} {shop} {number} {date} {total} {vat} {due} {balance}
#   (the older names {name} and {company} work too)
# ============================================================
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

FIELDS = ("customer", "shop", "number", "date", "total", "vat", "due", "balance")


class _Safe(dict):
    def __missing__(self, key):
        return "{%s}" % key


def ready():
    try:
        db.fetchall("SELECT template_id FROM message_templates WHERE 1=0")
        return True
    except Exception:
        return False


def rows(channel=None, purpose=None):
    if not ready():
        return []
    sql = "SELECT * FROM message_templates WHERE ISNULL(is_active,1)=1"
    params = []
    if channel:
        sql += " AND channel=?"
        params.append(channel)
    if purpose:
        sql += " AND (purpose=? OR purpose IS NULL OR purpose='other')"
        params.append(purpose)
    sql += " ORDER BY template_name"
    try:
        return [dict(r) for r in (db.fetchall(sql, tuple(params)) or [])]
    except Exception:
        return []


def render(body, ctx=None):
    """The template with its {words} filled from ctx; a word with no value
    stays as it is so the user sees what is missing."""
    ctx = dict(ctx or {})
    ctx.setdefault("customer", ctx.get("name", ""))
    ctx.setdefault("shop", ctx.get("company", ""))
    ctx.setdefault("balance", ctx.get("due", ""))
    ctx.setdefault("due", ctx.get("balance", ""))
    text = str(body or "").replace("\\n", "\n")
    try:
        return text.format_map(_Safe({k: ("" if v is None else v) for k, v in ctx.items()}))
    except Exception:
        return text
