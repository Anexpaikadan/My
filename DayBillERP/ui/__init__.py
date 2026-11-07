# Saudi Arabia ERP - UI Package
# Unique Tk callback names (stops stale timers firing the wrong handler)
from ui import tk_safety as _tk_safety  # noqa: F401
# Message boxes stay over their window; ✕ asks before closing a window
from ui import close_guard as _close_guard  # noqa: F401
# Every table: right-click a heading / ☰ → show, hide, move, width (remembered)
from ui import table_columns as _table_columns  # noqa: F401
