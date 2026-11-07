# ============================================================
# DayBill ERP - Tk callback-name safety
# ------------------------------------------------------------
# Tkinter names every Python callback it gives to Tcl as
# "<id of a temporary object><function name>". When a window closes
# while one of its after() timers is still pending, the callback is
# freed but the timer still holds the NAME. A later callback created
# at the same memory address (every lambda is called "<lambda>") gets
# the SAME name — so the old timer fires the WRONG function, e.g.
# "missing 1 required positional argument: 'e'", or worse, runs a
# key handler nobody pressed.
#
# Fix: add a never-repeating counter to each name. A stale timer then
# just finds no command (harmless) instead of hitting a new callback.
# Imported once by the ui package, before any window is created.
# ============================================================

import itertools
import tkinter as _tk

_counter = itertools.count(1)


def _register(self, func, subst=None, needcleanup=1):
    f = _tk.CallWrapper(func, subst, self).__call__
    name = repr(id(f))
    try:
        func = func.__func__
    except AttributeError:
        pass
    try:
        name = name + func.__name__
    except AttributeError:
        pass
    name = "%s_%d" % (name, next(_counter))
    self.tk.createcommand(name, f)
    if needcleanup:
        if self._tclCommands is None:
            self._tclCommands = []
        self._tclCommands.append(name)
    return name


if not getattr(_tk.Misc, "_daybill_safe_register", False):
    _tk.Misc._register = _register
    _tk.Misc.register = _register
    _tk.Misc._daybill_safe_register = True


# ── v7.21.3: old variable traces on new Tcl/Tk (9.x) ─────────
# var.trace("w", cb) uses Tcl's old "trace variable" command, which
# Tcl 9 removed → "bad option "variable": must be add, info, or remove"
# (seen when POS opens). Every DayBill call now uses trace_add; this
# keeps any old-style call (plugins, older files) working too.
_MODES = {"w": "write", "r": "read", "u": "unset", "a": "array"}


def _old_trace(self, mode, callback):
    modes = tuple(_MODES.get(m, m) for m in str(mode) if m in _MODES) or ("write",)
    return self.trace_add(modes, callback)


def _old_vdelete(self, mode, cbname):
    modes = tuple(_MODES.get(m, m) for m in str(mode) if m in _MODES) or ("write",)
    try:
        self.trace_remove(modes, cbname)
    except Exception:
        pass


if not getattr(_tk.Variable, "_daybill_safe_trace", False):
    _tk.Variable.trace = _old_trace
    _tk.Variable.trace_variable = _old_trace
    _tk.Variable.trace_vdelete = _old_vdelete
    _tk.Variable._daybill_safe_trace = True
