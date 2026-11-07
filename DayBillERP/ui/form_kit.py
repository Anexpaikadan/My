# ============================================================
# DayBill ERP - pop-up form kit (v5.25)
# ------------------------------------------------------------
# The same window for every add / edit form, like the Product window:
#   • a normal-size window in the middle of the screen (never full
#     screen), grows with Settings ▸ Text size, remembers the size the
#     user leaves it at
#   • pages (tabs) instead of one long scrolling form
#   • boxes sized for what goes in them: codes medium, numbers short,
#     names wide — and they can't take more letters than the database
#     column holds
# ============================================================
import re
import tkinter as tk

from config import settings as cfg

# box width (characters) for each kind of value
WIDTH = {"code": 12, "short": 8, "number": 12, "phone": 16, "vat": 18,
         "days": 6, "country": 6}


def popup(title, base=(820, 480), minsize=(700, 440), geom_key=None,
          parent=None, modal=True):
    """A pop-up form window (normal size, centred, remembered).
    base / minsize are at 100 % text size — they grow with Text size."""
    win = tk.Toplevel()
    win.withdraw()                          # no flash while building
    win.title(title)
    win._keep_size = True                   # its own size: never auto-grown / maximized
    try:
        if parent is not None:
            win.transient(parent.winfo_toplevel())
    except Exception:
        pass
    win.minsize(*minsize)
    saved = saved_geometry(win, geom_key, minsize)
    if saved:                               # real screen pixels: not grown again
        win._no_zoom = True
        win.geometry(saved)
        win._no_zoom = False
    else:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = base
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
    win.resizable(True, True)
    win.after(10, win.deiconify)
    if geom_key:
        win.bind("<Destroy>", lambda e, w=win, k=geom_key:
                 remember(w, k) if e.widget is w else None, add="+")
    if modal:
        try:
            win.grab_set()
        except Exception:
            pass
    return win


def saved_geometry(win, key, minsize=(600, 420)):
    """The size/position the user last left this window at, if it still
    fits on this screen."""
    if not key:
        return None
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", str(cfg.get(key, "") or ""))
    if not m:
        return None
    w, h, x, y = map(int, m.groups())
    if (minsize[0] * 0.8 <= w <= sw - 40 and minsize[1] * 0.8 <= h <= sh - 60
            and 0 <= x < sw - 100 and 0 <= y < sh - 100):
        return f"{w}x{h}+{x}+{y}"
    return None


def remember(win, key):
    try:
        if key and win.state() == "normal" and win.winfo_width() > 200:
            cfg.set(key, "%dx%d+%d+%d" % (win.winfo_width(), win.winfo_height(),
                                          win.winfo_x(), win.winfo_y()))
            cfg.save_settings()
    except Exception:
        pass


def header(win, C, text, right_text=""):
    """Slim title strip at the top (shown white, Windows 11 style)."""
    hdr = tk.Frame(win, bg=C["primary"], height=40)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    lbl = tk.Label(hdr, text=text, font=("Segoe UI", 12, "bold"),
                   bg=C["primary"], fg="white")
    lbl.pack(side="left", padx=16)
    if right_text:
        tk.Label(hdr, text=right_text, font=("Segoe UI", 9),
                 bg=C["primary"], fg="#DCE6FF").pack(side="right", padx=16)
    return hdr, lbl


def two_cols(page, C):
    page.columnconfigure(0, weight=1, uniform="fk")
    page.columnconfigure(1, weight=1, uniform="fk")
    page.rowconfigure(0, weight=1)
    left = tk.Frame(page, bg=C["content_bg"])
    right = tk.Frame(page, bg=C["content_bg"])
    left.grid(row=0, column=0, sticky="nsew", padx=(4, 6), pady=(6, 8))
    right.grid(row=0, column=1, sticky="nsew", padx=(6, 4), pady=(6, 8))
    return left, right


def section(parent, C, text, icon=""):
    tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=14, pady=(6, 0))
    tk.Label(parent, text=f"{icon}  {text}" if icon else text,
             font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
             fg=C["primary"]).pack(anchor="w", padx=14, pady=(3, 2))


def grid(parent, C, cols=2):
    g = tk.Frame(parent, bg=C["content_bg"])
    g.pack(fill="x", padx=14, pady=(4, 0))
    for i in range(cols):
        g.columnconfigure(i, weight=1, uniform="fkg%d" % cols)
    return g


def field(parent, C, row, col, label, var, *, kind=None, width=None,
          required=False, rtl=False, maxlen=None, state="normal",
          colspan=1, hint=None, check=None):
    """Label + box in a grid cell. kind = 'code' | 'short' | 'number' |
    'phone' | 'vat' | 'days' | 'country' → a box of that size (not
    stretched); no kind = full width of the cell (names, streets …).
    v6.8 (Tally style): hint = grey example in the empty box; check =
    'phone' | 'email' | 'vat' | 'cr' | 'postal' | 'building' | 'iban' |
    'number' | 'days' (guessed from kind / label when not given) → a red
    note under the box when it is wrong."""
    from ui import form_style as FS
    tally = FS.on()
    cell = tk.Frame(parent, bg=C["content_bg"])
    cell.grid(row=row, column=col, columnspan=colspan, sticky="ew",
              padx=(0, 10) if col == 0 else (10, 0), pady=(0, 8))
    if tally:                       # label, then a red * for "must fill"
        lrow = tk.Frame(cell, bg=C["content_bg"])
        lrow.pack(anchor="e" if rtl else "w")
        lab = tk.Label(lrow, text=label, font=("Segoe UI", 9, "bold"),
                       bg=C["content_bg"], fg=C["text_primary"])
        lab.pack(side="right" if rtl else "left")
        if required:                # the * after the words (RTL: to their left)
            tk.Label(lrow, text="*", font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                     fg=C["danger"]).pack(side="right" if rtl else "left",
                                          padx=(0, 2) if rtl else (2, 0))
    else:
        tk.Label(cell, text=label + (" *" if required else ""),
                 font=("Segoe UI", 9, "bold" if required else "normal"),
                 bg=C["content_bg"],
                 fg=C["primary"] if required else C["text_secondary"]).pack(
                     anchor="e" if rtl else "w")
    w = width or WIDTH.get(kind or "", None)
    e = tk.Entry(cell, textvariable=var, font=("Segoe UI", 10), relief="solid",
                 bd=1, bg="white" if state == "normal" else C["content_bg"],
                 fg=C["text_primary"], justify="right" if rtl else "left",
                 state=state, width=w or 8)
    e._fixed_width = bool(w)
    if w:
        e.pack(anchor="e" if rtl else "w", ipady=4, pady=(2, 0))
    else:
        e.pack(fill="x", ipady=4, pady=(2, 0))
    if maxlen:
        limit_length(e, maxlen)
    if tally:
        FS.style_entry(e, C)
        chk = check if check is not None else FS.guess_check(label, kind)
        if chk == "":
            chk = None
        FS.placeholder(e, var, hint if hint is not None else FS.HINTS.get(chk or ""),
                       rtl=rtl, C=C)
        FS.enter_moves_next(e)
        if state == "normal":
            box = FS.Box(cell, e, var, label, required=required, check=chk, rtl=rtl)
            e._fs_box = box
            FS.register(cell, box)
    return cell, e


def limit_length(entry, n):
    """The box takes at most n characters (typing / pasting more is
    blocked). An old longer value can still be shortened."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return
    if n <= 0:
        return

    def ok(new, old):
        return len(new) <= n or len(new) < len(old)
    try:
        vcmd = entry.register(ok)
        entry.configure(validate="key", validatecommand=(vcmd, "%P", "%s"))
        entry._max_len = n
    except Exception:
        pass
