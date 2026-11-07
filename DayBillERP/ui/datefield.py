# ============================================================
# DayBill ERP - date fields: calendar + quick ranges + shortcuts
# ------------------------------------------------------------
# Every box that holds a date (2026-10-05, 05/10/2026 …) gets this
# automatically (ui/ui_polish.py finds them when they appear):
#
#   📅 in the box ............ click → calendar (Windows 11 style)
#   F4 · Alt+↓ · double-click  open the calendar
#   ↑ / ↓ .................... one day later / earlier
#   PgUp / PgDn .............. one month earlier / later
#   T = today · Y = yesterday
#   typing: 5 → the 5th of this month · 5/10 → 5 October · +3 / -7 days
#
# From / To boxes side by side work as a pair: their calendar also shows
# QUICK RANGES (Today, This week, This month, Last month, This year …).
# Picking a range fills both boxes and runs the report (Run / Refresh …).
# The box keeps its own date format.
# ============================================================
import re
import calendar
import tkinter as tk
from datetime import date, datetime, timedelta

_FORMATS = (  # (regex, strftime) — order matters
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "%Y/%m/%d"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "%d/%m/%Y"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "%d-%m-%Y"),
    (re.compile(r"^\d{2}/\d{2}/\d{2}$"), "%d/%m/%y"),
)
_RUN_WORDS = ("run", "refresh", "filter", "generate", "view", "show", "search",
              "load", "apply", "عرض", "تحديث", "بحث")


def date_format_of(text):
    """The strftime format a date string is written in, or None."""
    t = str(text or "").strip()
    for rx, fmt in _FORMATS:
        if rx.match(t):
            try:
                datetime.strptime(t, fmt)
                return fmt
            except ValueError:
                return None
    return None


def looks_like_date(text):
    return date_format_of(text) is not None


def parse(text, fmt=None, base=None):
    """A date from what the user typed, or None. Understands the box's
    format and shortcuts: t, y, 5, 5/10, 5/10/2026, +3, -7."""
    t = str(text or "").strip().lower()
    today = base or date.today()
    if not t:
        return None
    if t in ("t", "today", "اليوم"):
        return today
    if t in ("y", "yesterday", "أمس"):
        return today - timedelta(days=1)
    m = re.match(r"^([+-])\s*(\d{1,4})$", t)
    if m:
        n = int(m.group(2))
        return today + timedelta(days=n if m.group(1) == "+" else -n)
    for f in ([fmt] if fmt else []) + [x[1] for x in _FORMATS]:
        try:
            return datetime.strptime(t, f).date()
        except (ValueError, TypeError):
            pass
    parts = re.split(r"[/\-. ]", t)
    try:
        nums = [int(p) for p in parts if p]
    except ValueError:
        return None
    try:
        if len(nums) == 1 and 1 <= nums[0] <= 31:
            return date(today.year, today.month, nums[0])
        if len(nums) == 2:
            return date(today.year, nums[1], nums[0])
        if len(nums) == 3:
            d, mth, y = nums
            if d > 31:                         # 2026/10/5
                d, y = y, d
            if y < 100:
                y += 2000
            return date(y, mth, d)
    except ValueError:
        return None
    return None


def add_months(d, n):
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def ranges(today=None):
    """[(name, from, to)] quick ranges."""
    t = today or date.today()
    week0 = t - timedelta(days=(t.weekday() + 1) % 7)          # Sunday
    m0 = t.replace(day=1)
    lm_end = m0 - timedelta(days=1)
    q = (t.month - 1) // 3
    q0 = date(t.year, q * 3 + 1, 1)
    lq0 = add_months(q0, -3)
    return [
        ("Today", t, t),
        ("Yesterday", t - timedelta(days=1), t - timedelta(days=1)),
        ("This week", week0, t),
        ("Last week", week0 - timedelta(days=7), week0 - timedelta(days=1)),
        ("This month", m0, t),
        ("Last month", lm_end.replace(day=1), lm_end),
        ("Last 7 days", t - timedelta(days=6), t),
        ("Last 30 days", t - timedelta(days=29), t),
        ("This quarter", q0, t),
        ("Last quarter", lq0, q0 - timedelta(days=1)),
        ("This year", date(t.year, 1, 1), t),
        ("Last year", date(t.year - 1, 1, 1), date(t.year - 1, 12, 31)),
    ]


def _pal():
    try:
        from config import settings as cfg
        C = cfg.theme()
    except Exception:
        C = {}
    return {"p": C.get("primary", "#2563EB"), "pl": C.get("primary_light", "#EAF1FE"),
            "tx": C.get("text_primary", "#111827"), "mu": C.get("text_secondary", "#4B5563"),
            "bd": C.get("border", "#E2E6EE"), "card": C.get("card_bg", "#FFFFFF"),
            "bg": C.get("content_bg", "#F3F5F9")}


# ── one date box ────────────────────────────────────────────────
class DateBox:
    def __init__(self, entry, var=None, on_pick=None):
        self.entry = entry
        self.on_pick = on_pick
        self.var = var
        if self.var is None:
            name = str(entry.cget("textvariable") or "")
            if name:
                self.var = tk.StringVar(master=entry, name=name)
        self.fmt = date_format_of(self.get()) or "%Y-%m-%d"
        self.popup = None
        entry._datebox = self
        self._icon()
        b = entry.bind
        b("<Up>", lambda e: self.step(days=1), add="+")
        b("<Down>", lambda e: self.step(days=-1), add="+")
        b("<Prior>", lambda e: self.step(months=-1), add="+")
        b("<Next>", lambda e: self.step(months=1), add="+")
        b("<Alt-Down>", lambda e: self.open(), add="+")
        b("<F4>", lambda e: self.open(), add="+")
        b("<Double-Button-1>", lambda e: self.open(), add="+")
        b("<KeyPress>", self._key, add="+")
        b("<FocusOut>", lambda e: self.normalize(), add="+")
        b("<Return>", lambda e: self.normalize(), add="+")
        b("<KP_Enter>", lambda e: self.normalize(), add="+")
        _REG.append(self)

    # value
    def get(self):
        try:
            return self.var.get() if self.var is not None else self.entry.get()
        except Exception:
            return ""

    def set(self, d, fire=True):
        txt = d.strftime(self.fmt)
        try:
            if self.var is not None:
                self.var.set(txt)
            else:
                st = str(self.entry.cget("state"))
                self.entry.configure(state="normal")
                self.entry.delete(0, "end")
                self.entry.insert(0, txt)
                self.entry.configure(state=st)
        except Exception:
            return
        try:
            self.entry.event_generate("<<DateChanged>>")
        except Exception:
            pass
        if fire and self.on_pick:
            try:
                self.on_pick()
            except Exception:
                pass

    def date(self):
        return parse(self.get(), self.fmt)

    # looks
    def _icon(self):
        e = self.entry
        try:
            if int(e.cget("width")) < 13:
                e.configure(width=13)
        except Exception:
            pass
        try:
            bg = e.cget("background")
        except Exception:
            bg = "white"
        P = _pal()
        lab = tk.Label(e.master, text="📅", font=("Segoe UI Emoji", 9), bg=bg,
                       fg=P["p"], cursor="hand2", padx=1, pady=0, bd=0)
        lab.place(in_=e, relx=1.0, x=-3, rely=0.5, anchor="e")
        lab.lift(e)
        lab.bind("<Button-1>", lambda ev: self.open())
        lab._polished = True
        self.icon = lab

    # keys
    def _key(self, ev):
        ch = (ev.char or "").lower()
        if ch == "t":
            self.set(date.today()); self.entry.icursor("end")
            return "break"
        if ch == "y":
            self.set(date.today() - timedelta(days=1)); self.entry.icursor("end")
            return "break"
        return None

    def step(self, days=0, months=0):
        d = self.date() or date.today()
        d = add_months(d, months) + timedelta(days=days)
        self.set(d)
        try:
            self.entry.icursor("end")
        except Exception:
            pass
        return "break"

    def normalize(self):
        t = self.get().strip()
        if not t or date_format_of(t) == self.fmt:
            return
        d = parse(t, self.fmt)
        if d:
            self.set(d)

    # pair (From / To)
    def partner(self):
        """The other box of a From/To pair (same row), or None."""
        mine = [b for b in _alive() if b is not self]
        for up in (self.entry.master, getattr(self.entry.master, "master", None)):
            if up is None:
                continue
            near = [b for b in mine if b.entry.master is up or getattr(b.entry.master, "master", None) is up]
            if len(near) == 1:
                return near[0]
            if len(near) > 1:
                return None
        return None

    def pair(self):
        """(from_box, to_box) when this box is part of a pair."""
        o = self.partner()
        if o is None:
            return None
        try:
            a = (self.entry.winfo_rooty(), self.entry.winfo_rootx())
            b = (o.entry.winfo_rooty(), o.entry.winfo_rootx())
        except Exception:
            a, b = 0, 1
        return (self, o) if a <= b else (o, self)

    def run_report(self):
        """After a quick range: press the report's Run / Refresh button."""
        w = self.entry.master
        for _ in range(3):
            if w is None:
                break
            for ch in _descendants(w):
                try:
                    if ch.winfo_class() in ("Button", "TButton") and ch.winfo_ismapped():
                        txt = str(ch.cget("text")).lower()
                        if any(k in txt for k in _RUN_WORDS) and str(ch.cget("state")) != "disabled":
                            ch.invoke()
                            return True
                except Exception:
                    pass
            w = getattr(w, "master", None)
        return False

    def open(self):
        try:
            if self.popup is not None and self.popup.winfo_exists():
                self.popup.close()
                return "break"
        except Exception:
            pass
        try:
            self.popup = CalendarPopup(self)
        except Exception:
            self.popup = None
        return "break"


_REG = []


def _alive():
    out = []
    for b in list(_REG):
        try:
            if b.entry.winfo_exists():
                out.append(b)
                continue
        except Exception:
            pass
        _REG.remove(b)
    return out


def _descendants(w):
    out = []
    try:
        for ch in w.winfo_children():
            out.append(ch)
            out.extend(_descendants(ch))
    except Exception:
        pass
    return out


# ── the calendar ────────────────────────────────────────────────
class CalendarPopup(tk.Toplevel):
    def __init__(self, box):
        super().__init__(box.entry)
        self.box = box
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        P = self.P = _pal()
        self.configure(bg=P["bd"])
        cur = box.date() or date.today()
        self.sel = cur
        self.y, self.m = cur.year, cur.month
        self.pair = box.pair()
        self._owner = box.entry.winfo_toplevel()
        self._rootbind = None
        self._build()
        self._place()
        try:
            self._rootbind = self._owner.bind("<Button-1>", self._outside, add="+")
        except Exception:
            self._rootbind = None
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<Left>", lambda e: self._move(-1))
        self.bind("<Right>", lambda e: self._move(1))
        self.bind("<Up>", lambda e: self._move(-7))
        self.bind("<Down>", lambda e: self._move(7))
        self.bind("<Prior>", lambda e: self._month(-1))
        self.bind("<Next>", lambda e: self._month(1))
        self.bind("<Return>", lambda e: self.pick(self.sel))
        self.focus_force()

    def _outside(self, ev):
        try:
            name = str(ev.widget)
            if name == str(self) or name.startswith(str(self) + "."):
                return
            if ev.widget in (self.box.entry, getattr(self.box, "icon", None)):
                return
        except Exception:
            pass
        self.close()

    def _build(self):
        P = self.P
        for w in self.winfo_children():
            w.destroy()
        outer = tk.Frame(self, bg=P["card"])
        outer.pack(padx=1, pady=1)
        if self.pair:
            self._build_ranges(outer)
        cal = tk.Frame(outer, bg=P["card"])
        cal.pack(side="left", padx=10, pady=8, anchor="n")
        hdr = tk.Frame(cal, bg=P["card"]); hdr.pack(fill="x")
        title = "%s %d" % (calendar.month_name[self.m], self.y)
        tk.Label(hdr, text=title, font=("Segoe UI", 11, "bold"), bg=P["card"],
                 fg=P["tx"]).pack(side="left", padx=(2, 12))
        nav = tk.Frame(hdr, bg=P["card"]); nav.pack(side="right")
        for txt, cmd in (("«", lambda: self._month(-12)), ("‹", lambda: self._month(-1)),
                         ("›", lambda: self._month(1)), ("»", lambda: self._month(12))):
            b = tk.Label(nav, text=txt, font=("Segoe UI", 11, "bold"), bg=P["card"], fg=P["mu"],
                         width=2, cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(bg=P["pl"]))
            b.bind("<Leave>", lambda e, w=b: w.config(bg=P["card"]))
            b._polished = True
        grid = tk.Frame(cal, bg=P["card"]); grid.pack(pady=(6, 0))
        names = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
        for c, n in enumerate(names):
            tk.Label(grid, text=n, font=("Segoe UI", 8, "bold"), bg=P["card"], fg=P["mu"],
                     width=4).grid(row=0, column=c, pady=(0, 2))
        today = date.today()
        first = date(self.y, self.m, 1)
        start = first - timedelta(days=(first.weekday() + 1) % 7)
        lo, hi = self._range_marks()
        for i in range(42):
            d = start + timedelta(days=i)
            r, c = 1 + i // 7, i % 7
            other = d.month != self.m
            is_sel = d == self.sel
            in_rng = lo is not None and lo <= d <= hi
            bg = P["p"] if is_sel else (P["pl"] if in_rng else P["card"])
            fg = "white" if is_sel else ("#9CA3AF" if other else (P["p"] if d == today else P["tx"]))
            lab = tk.Label(grid, text=str(d.day), width=4, pady=3, bg=bg, fg=fg, cursor="hand2",
                           font=("Segoe UI", 9, "bold" if (is_sel or d == today) else "normal"),
                           highlightthickness=1 if d == today and not is_sel else 0,
                           highlightbackground=P["p"])
            lab.grid(row=r, column=c, padx=1, pady=1)
            lab.bind("<Button-1>", lambda e, dd=d: self.pick(dd))
            if not is_sel:
                lab.bind("<Enter>", lambda e, w=lab: w.config(bg=P["pl"]))
                lab.bind("<Leave>", lambda e, w=lab, b0=bg: w.config(bg=b0))
            lab._polished = True
        ft = tk.Frame(cal, bg=P["card"]); ft.pack(fill="x", pady=(8, 0))
        for txt, d in (("Today", today), ("Yesterday", today - timedelta(days=1)),
                       ("1st of month", today.replace(day=1))):
            b = tk.Label(ft, text=txt, font=("Segoe UI", 8, "bold"), bg=P["pl"], fg=P["p"],
                         padx=8, pady=3, cursor="hand2")
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e, dd=d: self.pick(dd))
            b._polished = True
        tk.Label(cal, text="↑↓ day · PgUp/PgDn month · T today", font=("Segoe UI", 7),
                 bg=P["card"], fg="#9CA3AF").pack(anchor="w", pady=(6, 0))

    def _range_marks(self):
        if not self.pair:
            return None, None
        a, b = self.pair[0].date(), self.pair[1].date()
        if a and b and a <= b:
            return a, b
        return None, None

    def _build_ranges(self, outer):
        P = self.P
        side = tk.Frame(outer, bg=P["bg"])
        side.pack(side="left", fill="y")
        tk.Label(side, text="Quick range", font=("Segoe UI", 8, "bold"), bg=P["bg"],
                 fg=P["mu"]).pack(anchor="w", padx=10, pady=(10, 4))
        a, b = self.pair[0].date(), self.pair[1].date()
        for name, f, t in ranges():
            on = (a, b) == (f, t)
            lab = tk.Label(side, text=name, font=("Segoe UI", 9, "bold" if on else "normal"),
                           bg=P["p"] if on else P["bg"], fg="white" if on else P["tx"],
                           anchor="w", padx=12, pady=3, cursor="hand2", width=13)
            lab.pack(fill="x", padx=4, pady=0)
            lab.bind("<Button-1>", lambda e, ff=f, tt=t: self.pick_range(ff, tt))
            if not on:
                lab.bind("<Enter>", lambda e, w=lab: w.config(bg=P["pl"]))
                lab.bind("<Leave>", lambda e, w=lab: w.config(bg=P["bg"]))
            lab._polished = True

    def _place(self):
        self.update_idletasks()
        e = self.box.entry
        try:
            x, y = e.winfo_rootx(), e.winfo_rooty() + e.winfo_height() + 2
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if x + w > sw - 4:
                x = max(4, sw - w - 4)
            if y + h > sh - 40:
                y = max(4, e.winfo_rooty() - h - 2)
            self.geometry("+%d+%d" % (x, y))
        except Exception:
            pass

    def _month(self, n):
        d = add_months(date(self.y, self.m, 1), n)
        self.y, self.m = d.year, d.month
        self._build()

    def _move(self, n):
        self.sel = self.sel + timedelta(days=n)
        self.y, self.m = self.sel.year, self.sel.month
        self._build()

    def pick(self, d):
        self.box.set(d)
        self.close()

    def pick_range(self, f, t):
        a, b = self.pair
        a.set(f, fire=False)
        b.set(t, fire=False)
        for bx in (a, b):
            if bx.on_pick:
                try:
                    bx.on_pick()
                except Exception:
                    pass
                break
        self.close()
        try:
            a.run_report()
        except Exception:
            pass

    def close(self):
        try:
            if self._rootbind is not None:
                _unbind_one(self._owner, "<Button-1>", self._rootbind)
        except Exception:
            pass
        try:
            self.box.popup = None
            self.destroy()
        except Exception:
            pass
        try:
            self.box.entry.focus_set()
        except Exception:
            pass


def _unbind_one(w, seq, funcid):
    """Remove only OUR handler (tkinter's unbind(seq, id) drops every
    handler of that event on the widget)."""
    script = w.bind(seq) or ""
    keep = "\n".join(l for l in script.split("\n") if funcid not in l)
    w.bind(seq, keep)
    try:
        w.deletecommand(funcid)
    except Exception:
        pass


# ── public ──────────────────────────────────────────────────────
def enhance(entry, var=None, on_pick=None):
    """Turn an Entry into a date box (safe to call twice)."""
    box = getattr(entry, "_datebox", None)
    if box is not None:
        if on_pick and not box.on_pick:
            box.on_pick = on_pick
        return box
    return DateBox(entry, var, on_pick)


def maybe_enhance(entry):
    """Called for every Entry that appears: if it holds a date and can be
    edited, it becomes a date box. Entries can opt out with _no_date."""
    try:
        if getattr(entry, "_datebox", None) is not None or getattr(entry, "_no_date", False):
            return False
        if str(entry.cget("state")) in ("disabled", "readonly"):
            return False
        if str(entry.cget("show") or ""):
            return False
        top = entry.winfo_toplevel()
        if getattr(top, "_no_zoom", False) and "pos" in str(top.title()).lower():
            return False                       # the POS keeps its own fields
        if looks_like_date(entry.get()):
            enhance(entry)
            return True
        if not str(entry.get()).strip() and _date_label(entry):
            enhance(entry)                     # empty box under a "… Date" label
            return True
    except Exception:
        pass
    return False


_DATE_LABEL = re.compile(r"\bdate\b|\bdob\b|birth|expiry|valid until|تاريخ", re.I)
_NOT_DATE = re.compile(r"format|update|time\b", re.I)


def _date_label(entry):
    """The label just before the box (label-above forms) names a date."""
    try:
        sibs = entry.master.winfo_children()
        i = sibs.index(entry)
    except Exception:
        return False
    for k in reversed(sibs[:i]):
        try:
            cls = k.winfo_class()
        except Exception:
            continue
        if cls in ("Label", "TLabel"):
            try:
                txt = str(k.cget("text"))
            except Exception:
                return False
            return bool(_DATE_LABEL.search(txt)) and not _NOT_DATE.search(txt)
        if cls in ("Entry", "TEntry", "TCombobox", "Text", "Spinbox"):
            return False
    return False
