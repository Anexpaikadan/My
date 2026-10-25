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
