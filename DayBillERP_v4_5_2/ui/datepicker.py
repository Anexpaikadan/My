# ============================================================
# DayBill ERP - Date Picker (kept for older screens)
# attach_datepicker(entry, var, on_pick) now makes the entry a full
# date box (ui/datefield.py): 📅 calendar, quick ranges for From/To
# pairs, ↑/↓ and PgUp/PgDn, T = today, typing shortcuts.
# ============================================================
from datetime import date

from ui.datefield import enhance, parse as _parse_any


def _parse(s):
    return _parse_any(s) or date.today()


def attach_datepicker(entry, var, on_pick=None):
    enhance(entry, var, on_pick)
    return entry
