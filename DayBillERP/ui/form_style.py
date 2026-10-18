# ============================================================
# DayBill ERP - Tally-style entry boxes (v6.8)
# ------------------------------------------------------------
# What a good web form (Tally) does, for every add / edit window:
#   • a grey example inside an empty box ("05X XXX XXXX")
#   • one clear border that turns blue while you type in the box
#   • a red * after the label of a box you must fill
#   • a short red note right under a wrong box (not only at the bottom)
#     — it goes away as soon as you fix the box
#   • Enter moves to the next box
#   • on Save: the first wrong box is shown (its page opens) and focused
# Settings ▸ System ▸ "Tally-style entry boxes" turns it off.
# ============================================================
import re
import tkinter as tk

try:
    from config import settings as cfg
except Exception:                                   # pragma: no cover
    cfg = None


def on():
    try:
        return bool(cfg.flag("ui_form_style", True))
    except Exception:
        return True


def _C():
    try:
        return cfg.theme()
    except Exception:
        return {"primary": "#2563EB", "danger": "#DC2626", "border": "#E2E6EE",
                "text_secondary": "#6B7280", "content_bg": "#F3F5F9", "success": "#16A34A"}


def edge(C=None):
    """Box border when not typing in it: clearly visible, not heavy."""
    C = C or _C()
    try:
        return cfg.mix(C.get("border", "#E2E6EE"), C.get("text_secondary", "#6B7280"), 0.30)
    except Exception:
        return "#B8BEC8"


def focus_tint(C=None):
    C = C or _C()
    try:
        return cfg.mix("#FFFFFF", C.get("primary", "#2563EB"), 0.05)
    except Exception:
        return "#F5F8FF"


# ── checks (Saudi formats) ───────────────────────────────────
def _digits(s):
    return re.sub(r"[\s\-()]", "", s or "")


def _ctry():
    """The company's country (v7.0): SA · AE · IN."""
    try:
        from modules import country as _c
        return _c.code()
    except Exception:
        return "SA"


def check_phone(s):
    d = _digits(s)
    c = _ctry()
    if re.fullmatch(r"(\+|00)\d{8,15}", d):
        return None
    if c == "AE":
        if re.fullmatch(r"0[2-9]\d{7,8}", d) or re.fullmatch(r"5\d{8}", d) \
                or re.fullmatch(r"971[2-9]\d{7,8}", d) or re.fullmatch(r"(800|600)\d{4,7}", d):
            return None
        return "Mobile: 05X XXX XXXX (10 digits) or +971 5X XXX XXXX"
    if c == "IN":
        if re.fullmatch(r"0?[6-9]\d{9}", d) or re.fullmatch(r"91[6-9]\d{9}", d) \
                or re.fullmatch(r"0\d{9,10}", d) or re.fullmatch(r"1800\d{6,7}", d):
            return None
        return "Mobile: 10 digits (98XXX XXXXX) or +91 98XXX XXXXX"
    if re.fullmatch(r"0[1-9]\d{8}", d) or re.fullmatch(r"5\d{8}", d) \
            or re.fullmatch(r"(\+|00)?966[1-9]\d{8}", d) \
            or re.fullmatch(r"(800\d{7}|9200\d{5})", d):
        return None
    return "Mobile: 05X XXX XXXX (10 digits) or +966 5X XXX XXXX"


def check_email(s):
    return None if re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", (s or "").strip()) \
        else "Email looks wrong — e.g. name@example.com"


def check_vat(s):
    """The tax number of the company's country: Saudi VAT No. (15 digits,
    3…3) · UAE TRN (15 digits, 100…) · India GSTIN (15 characters)."""
    c = _ctry()
    if c != "SA":
        try:
            from modules import country as _c
            ok, msg = _c.valid_tax_no(s, c)
            return None if ok else msg
        except Exception:
            return None
    d = _digits(s)
    if re.fullmatch(r"3\d{13}3", d):
        return None
    if not d.isdigit() or len(d) != 15:
        return "VAT number: 15 digits (you typed %d)" % len(d)
    return "VAT number must start and end with 3"


def check_cr(s):
    c = _ctry()
    if c == "IN":
        t = re.sub(r"\s+", "", str(s or "")).upper()
        if re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", t) or re.fullmatch(r"[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}", t) \
                or re.fullmatch(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", t):
            return None
        return "PAN: 10 characters (ABCDE1234F), or CIN / Udyam number"
    if c == "AE":
        return None                         # trade licence numbers differ by emirate
    d = _digits(s)
    return None if re.fullmatch(r"\d{10}", d) else "CR number: 10 digits (you typed %d)" % len(d)


def check_postal(s):
    c = _ctry()
    if c == "IN":
        return None if re.fullmatch(r"[1-9]\d{5}", _digits(s)) else "PIN code: 6 digits"
    if c == "AE":
        return None                         # P.O. Box numbers, any length
    return None if re.fullmatch(r"\d{5}", _digits(s)) else "Postal code: 5 digits"


def check_building(s):
    if _ctry() != "SA":
        return None
    return None if re.fullmatch(r"\d{4}", _digits(s)) else "Building number: 4 digits"


def check_iban(s):
    d = _digits(s).upper()
    c = _ctry()
    if c == "AE":
        return None if re.fullmatch(r"AE\d{21}", d) else "IBAN: AE + 21 digits (23 in all)"
    if c == "IN":
        return None                         # India: account no. + IFSC, no IBAN
    return None if re.fullmatch(r"SA\d{22}", d) else "IBAN: SA + 22 digits (24 in all)"


def check_number(s):
    try:
        float((s or "").replace(",", ""))
        return None
    except ValueError:
        return "Numbers only — e.g. 1500.00"


def check_days(s):
    return None if re.fullmatch(r"\d{1,4}", (s or "").strip()) else "Whole days — e.g. 30"


CHECKS = {"phone": check_phone, "email": check_email, "vat": check_vat, "cr": check_cr,
          "postal": check_postal, "building": check_building, "iban": check_iban,
          "number": check_number, "days": check_days}

_HINTS_SA = {"phone": "05X XXX XXXX", "email": "name@example.com", "vat": "3XXXXXXXXXXXXX3",
             "cr": "10 digits", "postal": "12345", "building": "1234",
             "iban": "SA00 0000 0000 0000 0000 0000", "number": "0.00", "days": "30"}
_HINTS_BY = {
    "AE": {"phone": "05X XXX XXXX", "vat": "100XXXXXXXXXXXX", "cr": "Trade licence no.",
           "postal": "P.O. Box", "building": "", "iban": "AE00 0000 0000 0000 0000 000"},
    "IN": {"phone": "98XXX XXXXX", "vat": "27ABCDE1234F1Z5", "cr": "ABCDE1234F", "postal": "400001",
           "building": "", "iban": ""},
}


class _Hints(dict):
    """The grey example in a box — the company's country decides (v7.0)."""
    def get(self, k, default=None):
        d = _HINTS_BY.get(_ctry(), {})
        if k in d:
            return d[k] or default
        return _HINTS_SA.get(k, default)

    def __getitem__(self, k):
        return self.get(k)


HINTS = _Hints(_HINTS_SA)


def guess_check(label, kind=None):
    """Which check fits a box, from its kind / label words."""
    lab = (label or "").lower()
    if "email" in lab or "بريد" in lab:
        return "email"
    if "iban" in lab:
        return "iban"
    if "postal" in lab or "الرمز البريدي" in lab:
        return "postal"
    if "building" in lab or "رقم المبنى" in lab:
        return "building"
    if re.search(r"\bcr\b|commercial reg|السجل التجاري", lab):
        return "cr"
    if kind in ("phone", "vat", "number", "days"):
        return kind
    if "vat" in lab:
        return "vat"
    if "phone" in lab or "mobile" in lab or "جوال" in lab:
        return "phone"
    return None


# ── the look ─────────────────────────────────────────────────
def style_entry(e, C=None):
    """One clear 1 px border that turns blue (and a light blue fill)
    while typing in the box."""
    if getattr(e, "_fs_styled", False):
        return
    C = C or _C()
    try:
        e._fs_bg = e.cget("bg")
        e.configure(relief="flat", bd=0, highlightthickness=1,
                    highlightbackground=edge(C), highlightcolor=C["primary"])
        e._fs_styled = True
    except tk.TclError:
        return
    tint = focus_tint(C)

    def fin(_e=None):
        try:
            if str(e.cget("state")) == "normal" and str(e._fs_bg).lower() in ("white", "#ffffff"):
                e.configure(bg=tint)
        except tk.TclError:
            pass

    def fout(_e=None):
        try:
            e.configure(bg=e._fs_bg)
        except tk.TclError:
            pass
    e.bind("<FocusIn>", fin, add="+")
    e.bind("<FocusOut>", fout, add="+")


def placeholder(e, var, text, rtl=False, C=None):
    """A grey example inside the empty box (it is never part of the value)."""
    if not text or str(e.cget("state")) != "normal":
        return None
    C = C or _C()
    try:
        font = e.cget("font")
    except tk.TclError:
        font = ("Segoe UI", 10)
    ph = tk.Label(e, text=text, fg="#9AA1AC", bg=e.cget("bg"), font=font,
                  bd=0, padx=0, pady=0, cursor="xterm")
    e._fs_hint = ph

    def show(*_a):
        try:
            if not e.winfo_exists():
                return
            empty = not var.get()
            if empty and e.focus_get() is not e:
                ph.configure(bg=e.cget("bg"))
                if rtl:
                    ph.place(relx=1.0, x=-4, rely=0.5, anchor="e")
                else:
                    ph.place(x=3, rely=0.5, anchor="w")
            else:
                ph.place_forget()
        except (tk.TclError, KeyError):
            pass
    ph.bind("<Button-1>", lambda _e: e.focus_set())
    e.bind("<FocusIn>", lambda _e: ph.place_forget(), add="+")
    e.bind("<FocusOut>", lambda _e: e.after_idle(show), add="+")
    try:
        var.trace_add("write", lambda *_a: e.after_idle(show))
    except Exception:
        pass
    e.after_idle(show)
    return ph


def enter_moves_next(e):
    """Enter → next box (only where Enter does nothing else)."""
    try:
        if e.bind("<Return>"):
            return
    except tk.TclError:
        return

    def nxt(_e):
        try:
            w = e.tk_focusNext()
            if w is not None:
                w.focus_set()
        except Exception:
            pass
    e.bind("<Return>", nxt, add="+")
    e.bind("<KP_Enter>", nxt, add="+")


# ── a box with its note line ─────────────────────────────────
class Box:
    """Everything one form box needs for the Tally behaviour."""

    def __init__(self, cell, entry, var, label, required=False, check=None, rtl=False):
        self.cell, self.entry, self.var, self.label = cell, entry, var, label
        self.required, self.check, self.rtl = required, check, rtl
        self.note = None
        self._bad = False
        try:
            var.trace_add("write", lambda *_a: self._typed())
        except Exception:
            pass
        entry.bind("<FocusOut>", lambda _e: self.live(), add="+")

    def value(self):
        try:
            return (self.var.get() or "").strip()
        except Exception:
            return ""

    def active(self):
        try:
            return self.entry.winfo_exists() and str(self.entry.cget("state")) == "normal"
        except tk.TclError:
            return False

    def problem(self):
        v = self.value()
        if not v:
            return "Please fill this in" if self.required else None
        fn = CHECKS.get(self.check) if self.check else None
        return fn(v) if fn else None

    def show(self, msg, kind="error"):
        C = _C()
        col = C["danger"] if kind == "error" else C.get("success", "#16A34A")
        try:
            if self.note is None:
                self.note = tk.Label(self.cell, text="", font=("Segoe UI", 8),
                                     bg=self.cell.cget("bg"), anchor="e" if self.rtl else "w",
                                     justify="right" if self.rtl else "left")
            self.note.configure(text=msg, fg=col)
            if not self.note.winfo_manager():
                self.note.pack(anchor="e" if self.rtl else "w", pady=(1, 0))
            if kind == "error":
                self.entry.configure(highlightbackground=col, highlightcolor=col)
                self._bad = True
        except tk.TclError:
            pass

    def clear(self):
        C = _C()
        try:
            if self.note is not None and self.note.winfo_manager():
                self.note.pack_forget()
            if getattr(self.entry, "_fs_styled", False):
                self.entry.configure(highlightbackground=edge(C), highlightcolor=C["primary"])
        except tk.TclError:
            pass
        self._bad = False

    def _typed(self):
        if self._bad:                    # fixed while typing → note goes away
            if not self.problem():
                self.clear()

    def live(self):
        """Leaving a box: a format note at once (empty required boxes are
        only flagged on Save, like Tally)."""
        if not self.active():
            return
        v = self.value()
        msg = self.problem() if v else None
        if msg:
            self.show(msg)
        elif self._bad:
            self.clear()


def register(win, box):
    try:
        win = win.winfo_toplevel()
        if not hasattr(win, "_fs_boxes"):
            win._fs_boxes = []
        win._fs_boxes.append(box)
    except Exception:
        pass


def boxes(win):
    try:
        return [b for b in getattr(win.winfo_toplevel(), "_fs_boxes", []) if b.active()]
    except Exception:
        return []


def validate(win, pagenav=None, focus=True):
    """Check every box of the window. Wrong boxes get their red note;
    the first one is shown (its page opened) and focused.
    Returns [(label, message), …] — empty when all is fine."""
    bad = []
    for b in boxes(win):
        msg = b.problem()
        if msg:
            b.show(msg)
            bad.append((b, msg))
        elif b._bad:
            b.clear()
    if bad and focus:
        goto(bad[0][0].entry, pagenav)
    return [(b.label, m) for b, m in bad]


def goto(entry, pagenav=None):
    try:
        if pagenav is not None:
            for p in getattr(pagenav, "pages", []):
                page = p.get("page") if isinstance(p, dict) else None
                w = entry
                while w is not None:
                    if w is page:
                        pagenav.show_page(page)
                        break
                    w = w.master
        entry.focus_set()
        entry.icursor("end")
    except Exception:
        pass


def _custom(w, opt):
    """True when the code set this option (not the Tk default)."""
    try:
        cfgt = w.configure(opt)
        return str(cfgt[-1]) != str(cfgt[-2])
    except (tk.TclError, IndexError):
        return False


def polish(win):
    """Any window: give its plain boxes the clear border + blue focus.
    (Forms built with form_kit get the full set: hints, notes, checks.)"""
    if not on():
        return
    C = _C()
    try:
        from ui.compact import _all
    except Exception:
        return
    for w in _all(win):
        try:
            if w.winfo_class() != "Entry" or getattr(w, "_fs_styled", False):
                continue
            if str(w.cget("relief")) not in ("solid", "sunken") or int(float(w.cget("bd"))) > 2:
                continue
            if _custom(w, "highlightthickness") or _custom(w, "highlightbackground"):
                continue                          # the window draws its own border
            if w.winfo_class() == "Entry" and w.master.winfo_class() == "Treeview":
                continue
            style_entry(w, C)
        except (tk.TclError, ValueError, AttributeError):
            continue
