# ============================================================
# DayBill ERP - ZATCA background sender
# ------------------------------------------------------------
# Sends the waiting e-invoices (report B2C / clear B2B) one by one.
# The network call runs in a thread; every database read / write stays
# in the Tk main thread (root.after), so the shared DB connection is
# never used from two threads. No internet → tries again in 2 minutes.
# ============================================================

import threading
import queue

_S = {"root": None, "job": None, "busy": False, "listeners": [], "last": ""}
_Q = queue.Queue()

IDLE_MS = 60000          # check for new waiting documents every minute
OFFLINE_MS = 120000      # no internet: try again in 2 minutes
NEXT_MS = 400            # more waiting: send the next one straight away


def start(root):
    _S["root"] = root
    _schedule(4000)


def kick():
    """A document was just signed — send soon."""
    if _S["root"] is not None and not _S["busy"]:
        _schedule(300)


def on_change(fn):
    """fn(text) is called after every answer from ZATCA (screen refresh)."""
    if fn not in _S["listeners"]:
        _S["listeners"].append(fn)


def off_change(fn):
    try:
        _S["listeners"].remove(fn)
    except ValueError:
        pass


def _schedule(ms):
    root = _S["root"]
    if root is None:
        return
    try:
        if _S["job"]:
            root.after_cancel(_S["job"])
    except Exception:
        pass
    try:
        _S["job"] = root.after(ms, _tick)
    except Exception:
        _S["job"] = None


def _tick():
    _S["job"] = None
    if _S["busy"]:
        return
    try:
        from modules.zatca import egs
        e = egs.active()
        if e and not e.get("auto_send", 1):
            _schedule(IDLE_MS)
            return
        if not egs.any_connected():                  # v6.0: any till's unit
            _schedule(IDLE_MS)
            return
        items = egs.next_items(1)
        if items:
            e = egs.unit_for(items[0], e)            # the unit that signed it (DB part)
    except Exception:
        _schedule(IDLE_MS)
        return
    if not items:
        _schedule(IDLE_MS)
        return
    item = items[0]
    _S["busy"] = True

    def work():
        try:
            st, d = egs.send_one(e, item)
        except Exception as ex:
            st, d = 0, {"message": str(ex)[:300]}
        _Q.put((item, st, d))
    threading.Thread(target=work, daemon=True).start()
    _S["root"].after(300, _poll)


def _poll():
    try:
        item, st, d = _Q.get_nowait()
    except queue.Empty:
        _S["root"].after(300, _poll)
        return
    _S["busy"] = False
    try:
        from modules.zatca import egs
        new = egs.apply_result(item, st, d)
    except Exception as ex:
        new = "waiting"
        st = 0
    _S["last"] = new
    for fn in list(_S["listeners"]):
        try:
            fn(new)
        except Exception:
            pass
    _schedule(OFFLINE_MS if (new == "waiting" and st == 0) else NEXT_MS)
