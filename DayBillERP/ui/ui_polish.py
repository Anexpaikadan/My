# ============================================================
# DayBill ERP - UI Polish (automatic page beautifier)
# ------------------------------------------------------------
# beautify(container) walks the widget tree of any mounted view
# and retro-fits modern behaviour that a ttk.Style cannot reach:
#
#   tk.Button      hand cursor, flat relief, hover darken/restore
#   tk.Entry/Text/
#   Spinbox/Listbox  focus ring in the brand primary colour
#   ttk.Treeview   zebra striping (auto re-stripes as data reloads)
#                  + click-to-sort headings (numeric-aware)
#   tk.Label       hand cursor on labels that have click bindings
#
# It is idempotent (safe to call repeatedly), never overrides a
# widget's own explicit styling decisions, and skips widgets that
# manage their own hover (marked with `_polished`/own bindings kept
# via add="+").
#
# One integration point: main_window._load_module calls
# beautify(self.content) after each view mounts. That single hook
# upgrades every page in the app.
# ============================================================

import re
import tkinter as tk
from tkinter import ttk

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg


# ── colour helpers ─────────────────────────────────────────────
def _shade(hex_color, delta):
    try:
        h = str(hex_color).lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        f = lambda v: max(0, min(255, v + delta))
        return "#%02X%02X%02X" % (f(r), f(g), f(b))
    except Exception:
        return hex_color


def _is_hex(color):
    c = str(color)
    return c.startswith("#") and len(c) in (4, 7)


def _is_dark(hex_color):
    try:
        h = str(hex_color).lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) < 128
    except Exception:
        return False


# ── public entry point ─────────────────────────────────────────
def beautify(container):
    """Polish every widget below `container`. Safe to call repeatedly."""
    if container is None:
        return
    try:
        if not container.winfo_exists():
            return
    except Exception:
        return
    C = cfg.theme()
    _walk(container, C)


def enable_auto_polish(root):
    """App-wide automatic polish: every widget is processed the moment
    it appears on screen (<Map>), so dialogs and forms created at any
    time — product form, vouchers, HR, settings tabs — are covered
    without any per-screen hook. Idempotent; call once after the root
    window exists."""
    if getattr(root, "_auto_polish_on", False):
        return
    root._auto_polish_on = True

    def on_map(event):
        try:
            w = event.widget
            if isinstance(w, str):
                return                # internal/foreign widget — skip
            _polish_widget(w, cfg.theme())
        except Exception:
            pass                      # polish must never break the app

    root.bind_all("<Map>", on_map, add="+")


def _walk(widget, C):
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        try:
            _polish_widget(child, C)
        except Exception:
            pass                      # never let polish break a page
        _walk(child, C)


def _polish_widget(w, C):
    if getattr(w, "_polished", False):
        return
    cls = w.winfo_class()

    if cls == "Button":
        _polish_button(w, C)
        _enter_invokes(w)
    elif cls == "TButton":
        _enter_invokes(w)
    elif cls in ("Entry", "Spinbox"):
        _polish_field(w, C)
        _enter_advances(w)
        _select_all_on_focus(w)
        if cls == "Entry":
            _date_field(w)
            _smart_width(w)
    elif cls in ("TEntry", "TSpinbox"):
        _enter_advances(w)
        _select_all_on_focus(w)
    elif cls == "TCombobox":
        _enter_advances(w)
    elif cls in ("Text", "Listbox"):
        _polish_field(w, C)          # focus ring only; Enter stays native
    elif cls == "Treeview":
        _polish_tree(w, C)
    elif cls == "Label":
        _polish_label(w)
    w._polished = True


# ── ERP keyboard flow: Enter = next field (Excel-style) ────────
def _date_field(w):
    """A box that holds a date gets the calendar + shortcuts
    (ui/datefield.py). Checked now and once more after the screen filled
    its values in."""
    try:
        from ui.datefield import maybe_enhance
        if not maybe_enhance(w):
            w.after(450, lambda: maybe_enhance(w) if w.winfo_exists() else None)
    except Exception:
        pass


# ── form boxes sized for what goes in them (v5.25) ─────────────
# A pop-up form box that stretched across the whole column (a code, a
# quantity, a phone number as wide as a name) gets a sensible width from
# the label above it: codes medium, numbers short, names stay wide.
_SMART = (
    (re.compile(r"\b(e-?mail|name|address|street|description|notes?|remarks?|narration|"
                r"memo|path|folder|url|website|reason|details?|title|search|اسم|عنوان)"), None),
    (re.compile(r"\bdate\b|تاريخ"), 15),
    (re.compile(r"country code"), 6),
    (re.compile(r"postal|zip|building|بناء"), 10),
    (re.compile(r"barcode"), 18),
    (re.compile(r"iban|account (no|number)"), 26),
    (re.compile(r"\bvat\b|\btrn\b|tax (no|number)|\bcr\b|iqama|\bid (no|number)"), 20),
    (re.compile(r"phone|mobile|whatsapp|\bfax\b|جوال|هاتف"), 16),
    (re.compile(r"\bcode\b|\bno\.?$|number$|\bref\b|reference|cheque|check no|رمز|كود"), 14),
    (re.compile(r"\bdays?\b|terms|months?|\byears?\b|hours?"), 8),
    (re.compile(r"\bqty\b|quantity|\bpcs\b|كمية"), 10),
    (re.compile(r"price|cost|amount|total|rate|limit|balance|salary|allowance|"
                r"discount|deduction|loan|instal|%|percent|value|sar|مبلغ|سعر"), 14),
)


def _smart_rule(text):
    t = re.sub(r"[*:()]", " ", str(text or "")).strip().lower()
    if not t:
        return None
    for rx, width in _SMART:
        if rx.search(t):
            return width or None
    return None


def _label_widget(w):
    """The label just before this box in its frame (label-above forms)."""
    try:
        sibs = w.master.winfo_children()
        i = sibs.index(w)
    except Exception:
        return None
    for k in reversed(sibs[:i]):
        try:
            cls = k.winfo_class()
        except Exception:
            continue
        if cls in ("Label", "TLabel"):
            return k
        if cls in ("Entry", "TEntry", "TCombobox", "Text", "Spinbox"):
            return None                     # another box comes first
    return None


def _label_for(w):
    k = _label_widget(w)
    try:
        return str(k.cget("text")) if k is not None else ""
    except Exception:
        return ""


_ARABIC = re.compile(r"[\u0600-\u06FF]")


def _label_on_right(w):
    """Arabic labels sit on the right — their box goes right too."""
    k = _label_widget(w)
    if k is None:
        return False
    try:
        if _ARABIC.search(str(k.cget("text"))) and not re.search(r"[A-Za-z]{3}", str(k.cget("text"))):
            return True
        if k.winfo_manager() == "pack" and str(k.pack_info().get("anchor")) in ("e", "ne", "se"):
            return True
    except Exception:
        pass
    return False


def _smart_width(w):
    try:
        if getattr(w, "_fixed_width", False) or getattr(w, "_smart_done", False):
            return
        w._smart_done = True
        top = w.winfo_toplevel()
        if not isinstance(top, tk.Toplevel) or getattr(top, "_keep_size", False) \
                or getattr(top, "_no_zoom", False) or getattr(top, "_no_smart_width", False):
            return
        mgr = w.winfo_manager()
        if mgr == "pack":
            info = w.pack_info()
            if info.get("fill") not in ("x", "both") or info.get("side") not in ("top", None):
                return
        elif mgr == "grid":
            if not set("ew") <= set(str(w.grid_info().get("sticky", ""))):
                return
        else:
            return
        width = _smart_rule(_label_for(w))
        if not width:
            return
        rtl = _label_on_right(w)
        w.config(width=width)
        if mgr == "pack":
            w.pack_configure(fill="none", expand=False, anchor="e" if rtl else "w")
        else:
            w.grid_configure(sticky="e" if rtl else "w")
    except Exception:
        pass


def _has_return_binding(w):
    try:
        return bool(str(w.bind("<Return>")))
    except Exception:
        return True                   # unsure -> don't interfere


def _window_ok(w):
    """The window of `w` when it has its own Enter = OK (login, shift,
    print box …) — the field then lets Enter through to it. While the
    next field is still empty Enter keeps moving there (user name →
    password)."""
    try:
        top = w.winfo_toplevel()
        if top is w or not isinstance(top, tk.Toplevel) or not top.bind("<Return>"):
            return None
        nxt = w.tk_focusNext()
        if nxt is not None and nxt is not w and nxt.winfo_toplevel() is top \
                and nxt.winfo_class() in ("Entry", "TEntry") and not str(nxt.get()).strip():
            return None
        return top
    except Exception:
        return None


def _enter_to_window(event, top):
    """Let Enter reach the window's OK: None for Enter; numpad Enter is
    replayed as Enter when the window binds only <Return>."""
    if event.keysym == "KP_Enter" and not top.bind("<KP_Enter>"):
        try:
            event.widget.event_generate("<Return>")
        except Exception:
            pass
        return "break"
    return None


def _enter_advances(w):
    """Enter (and numpad Enter) moves to the next field, like Excel.
    Widgets that already bind <Return> keep their own behaviour —
    their Enter handler stays first priority, we never stack on it.
    In a window with its own Enter = OK the field steps aside."""
    if _has_return_binding(w):
        return

    def advance(event, wd=w):
        top = _window_ok(wd)
        if top is not None:
            return _enter_to_window(event, top)
        try:
            nxt = wd.tk_focusNext()
            if nxt:
                nxt.focus_set()
                try:
                    nxt.select_range(0, "end")     # ready to overtype
                except Exception:
                    pass
        except Exception:
            pass
        return "break"

    w.bind("<Return>", advance)
    w.bind("<KP_Enter>", advance)


def _enter_invokes(w):
    """A focused button should fire on Enter, not just Space."""
    if _has_return_binding(w):
        return

    def fire(event, wd=w):
        try:
            wd.invoke()
        except Exception:
            pass
        return "break"

    w.bind("<Return>", fire)
    w.bind("<KP_Enter>", fire)


def _select_all_on_focus(w):
    """Entering a field selects its content so typing replaces it —
    standard ERP data-entry behaviour."""
    def sel(event, wd=w):
        try:
            wd.select_range(0, "end")
            wd.icursor("end")
        except Exception:
            pass

    w.bind("<FocusIn>", sel, add="+")


# ── readable coloured buttons (v7.6, WCAG 4.5:1) ──────────────
def _rel_lum(hex_color):
    h = str(hex_color).lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    """WCAG contrast ratio of two #RRGGBB colours (1 … 21)."""
    la, lb = _rel_lum(a), _rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def readable_bg(bg, fg, C=None, target=4.5):
    """A button with white text on a light colour (bright green Save,
    or a theme whose accent is white) is hard to read: give back a
    darker shade of the same colour that reaches 4.5:1. Anything that
    already passes, or has dark text, is returned unchanged."""
    try:
        if not (_is_hex(bg) and _is_hex(fg)) or _rel_lum(fg) < 0.7:
            return bg
        if contrast(bg, fg) >= target:
            return bg
        if _rel_lum(bg) > 0.8:                     # white on white: use the brand colour
            prim = (C or cfg.theme()).get("primary", "#2563EB")
            if _is_hex(prim) and contrast(prim, fg) >= target:
                return prim
        h = str(bg).lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        r, g, b_ = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        for step in range(1, 20):
            k = 1 - step * 0.05
            col = "#%02X%02X%02X" % (int(r * k), int(g * k), int(b_ * k))
            if contrast(col, fg) >= target:
                return col
    except Exception:
        pass
    return bg


# ── tk.Button: hover + cursor + flatten ────────────────────────
def _polish_button(w, C):
    try:
        bg, fg = w.cget("bg"), w.cget("fg")
        fg = "#FFFFFF" if str(fg).lower() == "white" else fg
        nb = readable_bg(bg, fg, C)
        if nb != bg:
            w.config(bg=nb)
    except Exception:
        pass
    try:                                   # keyboard focus ring in the brand colour
        if str(w.cget("highlightcolor")).lower() in ("black", "#000000", "systemwindowframe"):
            w.config(highlightcolor=C.get("primary", "#2563EB"))
    except Exception:
        pass
    try:
        if not str(w.cget("cursor")):
            w.config(cursor="hand2")
        if str(w.cget("relief")) == "raised":       # untouched default look
            w.config(relief="flat", bd=0, padx=max(10, int(w.cget("padx") or 0)),
                     pady=max(6, int(w.cget("pady") or 0)))
    except Exception:
        pass

    def on_enter(e=None, wd=w):
        try:
            bg = wd.cget("bg")
            if not _is_hex(bg):
                return
            wd._hover_restore = bg
            wd.config(bg=_shade(bg, 18 if _is_dark(bg) else -14))
        except Exception:
            pass

    def on_leave(e=None, wd=w):
        try:
            restore = getattr(wd, "_hover_restore", None)
            if restore:
                wd.config(bg=restore)
                wd._hover_restore = None
        except Exception:
            pass

    w.bind("<Enter>", on_enter, add="+")
    w.bind("<Leave>", on_leave, add="+")


# ── input fields: focus ring in brand colour ───────────────────
def _polish_field(w, C):
    """Windows 11 field: flat, thin light-grey border, blue when focused."""
    primary = C.get("primary", "#2563EB")
    border = C.get("field_border", C.get("border", "#E3E0F4"))
    try:
        rel = str(w.cget("relief"))
        if rel in ("sunken", "solid", "groove", "ridge"):
            bd = int(str(w.cget("bd") or 1))
            w.config(relief="flat", bd=max(1, min(bd, 2)))
        if int(str(w.cget("highlightthickness") or 0)) == 0:
            w.config(highlightthickness=1)
        w.config(highlightcolor=primary, highlightbackground=border)
    except Exception:
        pass


# ── clickable labels get the hand cursor ───────────────────────
def _polish_label(w):
    try:
        if not str(w.cget("cursor")) and w.bind("<Button-1>"):
            w.config(cursor="hand2")
    except Exception:
        pass


# ── Treeview: zebra stripes (self-healing) + sortable headings ──
_STRIPE_TAG = "uipolish_odd"
_RESTRIPE_MS = 900


def _polish_tree(tree, C):
    card = C.get("card_bg", "#FFFFFF")
    stripe = _shade(card, -7)
    try:
        tree.tag_configure(_STRIPE_TAG, background=stripe)
    except Exception:
        return
    _attach_sort(tree)
    _stripe_now(tree)
    _schedule_restripe(tree)


def _stripe_now(tree):
    try:
        for i, iid in enumerate(tree.get_children("")):
            tags = [t for t in tree.item(iid, "tags") if t != _STRIPE_TAG]
            if i % 2:
                tags.append(_STRIPE_TAG)     # appended LAST: view tags win
            tree.item(iid, tags=tuple(tags))
        tree._stripe_sig = (len(tree.get_children("")),
                            tree.get_children("")[:1])
    except Exception:
        pass


def _schedule_restripe(tree):
    """Re-stripe when the row set changes (views reload data freely)."""
    def tick():
        try:
            if not tree.winfo_exists():
                return                        # widget gone — stop loop
            kids = tree.get_children("")
            sig = (len(kids), kids[:1])
            if sig != getattr(tree, "_stripe_sig", None):
                _stripe_now(tree)
            tree.after(_RESTRIPE_MS, tick)
        except Exception:
            pass
    tree.after(_RESTRIPE_MS, tick)


def _attach_sort(tree):
    """Click-to-sort on headings that don't already have a command."""
    try:
        cols = tree.cget("columns")
    except Exception:
        return
    if not cols:
        return
    for col in cols:
        try:
            existing = tree.heading(col, "command")
            if existing:                      # view has its own behaviour
                continue
            tree.heading(col, command=lambda c=col, t=tree: _sort_by(t, c, False))
        except Exception:
            pass


def _sort_by(tree, col, descending):
    try:
        rows = [(tree.set(iid, col), iid) for iid in tree.get_children("")]

        def key(pair):
            v = pair[0].replace(",", "").replace("%", "").strip()
            try:
                return (0, float(v))
            except ValueError:
                return (1, pair[0].lower())

        rows.sort(key=key, reverse=descending)
        for idx, (_, iid) in enumerate(rows):
            tree.move(iid, "", idx)
        tree.heading(col, command=lambda c=col, t=tree: _sort_by(t, c, not descending))
        # ▲ / ▼ on the sorted column (Windows Explorer style)
        base = getattr(tree, "_sort_base", None)
        if base is None:
            base = {}
            for c in tree.cget("columns"):
                base[c] = str(tree.heading(c, "text")).rstrip(" ▲▼")
            tree._sort_base = base
        for c, txt in base.items():
            tree.heading(c, text=txt + ((" ▼" if descending else " ▲") if c == col else ""))
        _stripe_now(tree)
    except Exception:
        pass


# ── bonus: lightweight toast for new code to use ───────────────
def toast(root, message, kind="info", ms=2200):
    """Non-blocking notification. kind: info | success | warning | danger."""
    C = cfg.theme()
    colors = {"info": C.get("primary"), "success": C.get("success"),
              "warning": C.get("warning"), "danger": C.get("danger")}
    bg = colors.get(kind, C.get("primary"))
    try:
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        lbl = tk.Label(win, text=message, bg=bg, fg="white",
                       font=("Segoe UI", 10, "bold"), padx=18, pady=10)
        lbl.pack()
        win.update_idletasks()
        x = root.winfo_rootx() + root.winfo_width() - win.winfo_width() - 24
        y = root.winfo_rooty() + root.winfo_height() - win.winfo_height() - 40
        win.geometry("+%d+%d" % (x, y))
        win.after(ms, win.destroy)
    except Exception:
        pass


# ================================================================
# GLOBAL FORM FLOW — Excel-style keyboard discipline, app-wide
# ----------------------------------------------------------------
# enable_form_flow(root) installs class-level bindings so that in
# EVERY form of EVERY module (customers, products, accounting,
# vouchers, settings, HR, expenses, reports ...):
#
#   Enter / numpad-Enter  ->  move focus to the next field
#                             (Excel-style), selecting its text
#   Enter on a button     ->  invokes it (like clicking)
#   Focus into an entry   ->  selects existing text (type-over)
#
# PRIORITY RULE: a widget that defines its OWN <Return> binding
# (invoice grid cells, search boxes, login) always wins — the
# global flow steps aside. Numpad Enter on such widgets replays
# their <Return> behaviour, so KP_Enter == Return everywhere.
#
# Call once after the root window exists (apply_modern_theme does).
# Rebinding is idempotent.
# ================================================================

_FLOW_CLASSES = ("Entry", "Spinbox", "TEntry", "TSpinbox", "TCombobox")


def enable_form_flow(root):
    def _advance(event):
        w = event.widget
        try:
            if w.bind("<Return>"):            # widget owns Enter — step aside
                return
            top = _window_ok(w)               # window's own Enter = OK
            if top is not None:
                return _enter_to_window(event, top)
            nxt = w.tk_focusNext()
            if nxt is not None:
                nxt.focus_set()
                try:
                    nxt.select_range(0, "end")
                    nxt.icursor("end")
                except Exception:
                    pass
            return "break"
        except Exception:
            return

    def _kp_enter(event):
        w = event.widget
        try:
            if w.bind("<KP_Enter>"):          # widget handles numpad itself
                return
            if w.bind("<Return>"):            # replay its own Enter behaviour
                w.event_generate("<Return>")
                return "break"
            top = _window_ok(w)               # window's own Enter = OK
            if top is not None:
                return _enter_to_window(event, top)
        except Exception:
            pass
        return _advance(event)

    def _select_all(event):
        try:
            event.widget.select_range(0, "end")
        except Exception:
            pass

    def _invoke_button(event):
        try:
            event.widget.invoke()
            return "break"
        except Exception:
            return

    for cls in _FLOW_CLASSES:
        try:
            root.bind_class(cls, "<Return>", _advance)
            root.bind_class(cls, "<KP_Enter>", _kp_enter)
        except Exception:
            pass
    for cls in ("Entry", "TEntry", "Spinbox", "TSpinbox"):
        try:
            root.bind_class(cls, "<FocusIn>", _select_all, add="+")
        except Exception:
            pass
    for cls in ("Button", "TButton", "Checkbutton", "TCheckbutton"):
        try:
            root.bind_class(cls, "<Return>", _invoke_button)
            root.bind_class(cls, "<KP_Enter>", _invoke_button)
        except Exception:
            pass


# ================================================================
# WINDOWS-APP BEHAVIOUR — app-wide, installed once on the root
# ----------------------------------------------------------------
#   Mouse wheel      scrolls the panel / list under the pointer
#                    (scrollable forms, settings pages, lists)
#   Right-click      Cut / Copy / Paste / Select All on every text box
#   Ctrl+A           selects all text in a box
#   Tables           Ctrl+C copies the selected rows, right-click →
#                    Copy rows / Copy table / Export to Excel,
#                    Enter opens the row (same as double-click),
#                    Home / End jump to the first / last row
# Widgets with their own binding for a key keep their behaviour.
# ================================================================
_WIN_BEHAVIOUR = {"interps": set()}


def enable_windows_behaviour(root):
    # bind_all / bind_class are per Tk interpreter — install only once
    try:
        key = str(root.tk)
    except Exception:
        key = "default"
    if key in _WIN_BEHAVIOUR["interps"]:
        return
    _WIN_BEHAVIOUR["interps"].add(key)
    try:
        root.bind_all("<MouseWheel>", _on_wheel, add="+")
        root.bind_all("<Button-4>", _on_wheel, add="+")
        root.bind_all("<Button-5>", _on_wheel, add="+")
    except Exception:
        pass
    _patch_geometry()
    try:
        root.bind_all("<Map>", _center_new_window, add="+")
    except Exception:
        pass
    try:
        root.after_idle(lambda: win11_frame(root))      # the main window too
    except Exception:
        pass
    for cls in ("Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text"):
        try:
            root.bind_class(cls, "<Button-3>", _edit_menu, add="+")
        except Exception:
            pass
    for cls in ("Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox"):
        try:
            root.bind_class(cls, "<Control-a>", _select_all_entry)
            root.bind_class(cls, "<Control-A>", _select_all_entry)
        except Exception:
            pass
    try:
        root.bind_class("Text", "<Control-a>", _select_all_text)
        root.bind_class("Treeview", "<Control-c>", _tree_copy, add="+")
        root.bind_class("Treeview", "<Control-C>", _tree_copy, add="+")
        root.bind_class("Treeview", "<Button-3>", _tree_menu, add="+")
        root.bind_class("Treeview", "<Return>", _tree_enter, add="+")
        root.bind_class("Treeview", "<KP_Enter>", _tree_enter, add="+")
        root.bind_class("Treeview", "<Home>", lambda e: _tree_jump(e.widget, 0), add="+")
        root.bind_class("Treeview", "<End>", lambda e: _tree_jump(e.widget, -1), add="+")
    except Exception:
        pass


# ── dialogs open centred over their window (unless placed by code) ──
def _patch_geometry():
    if getattr(tk.Wm, "_daybill_geo_patch", False):
        return
    orig = tk.Wm.wm_geometry

    def wm_geometry(self, newGeometry=None):
        if newGeometry and "+" in str(newGeometry) or (newGeometry and "-" in str(newGeometry)[1:]):
            try:
                self._daybill_placed = True
            except Exception:
                pass
        return orig(self, newGeometry)
    tk.Wm.wm_geometry = wm_geometry
    tk.Wm.geometry = wm_geometry
    tk.Wm._daybill_geo_patch = True


def _keep_footer_visible(container, depth=0):
    """Save/Cancel bars packed at the bottom AFTER an expanding body lose
    their space first when the window is short. Moving them before the
    body in the packing order changes nothing when there is room, and keeps
    the buttons on screen when there is not."""
    try:
        slaves = container.pack_slaves()
        first_exp = None
        for s in slaves:
            info = s.pack_info()
            if first_exp is None:
                if str(info.get("expand")) in ("1", "true", "True") and info.get("side") == "top":
                    first_exp = s
                continue
            side = info.get("side")
            if side in ("left", "right"):
                break                      # columns after the body: layout would change
            if side == "bottom":
                opts = {k: v for k, v in info.items() if k not in ("in", "before", "after")}
                s.pack_forget()
                s.pack(before=first_exp, **opts)
        if depth < 2:
            for s in container.pack_slaves():
                if isinstance(s, (tk.Frame, ttk.Frame)) and str(s.pack_info().get("expand")) in ("1", "true", "True"):
                    _keep_footer_visible(s, depth + 1)
    except Exception:
        pass


_CAPTION = 32          # Windows title bar + frame (100 % scaling)


def _raw_geo(w, geo):
    """Sizes here come from winfo_… (real screen pixels): set them as they
    are — the app Text size (ui/zoom.py) must not grow them a second time."""
    try:
        w._daybill_placed = True
    except Exception:
        pass
    try:
        from ui.zoom import raw_geometry
        return raw_geometry(w, geo)
    except Exception:
        return w.geometry(geo)


def _work_area(w):
    """(x0, y0, x1, y1) of the desktop without the Windows taskbar."""
    try:
        import sys as _s
        if _s.platform.startswith("win"):
            import ctypes
            from ctypes import wintypes
            r = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0):
                if r.right - r.left > 200 and r.bottom - r.top > 200:
                    return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
    return 0, 0, sw, sh - 40


def _max_client(w):
    """Largest client size that fits on screen with its title bar."""
    x0, y0, x1, y1 = _work_area(w)
    return (x1 - x0) - 16, (y1 - y0) - _CAPTION - 8


def _popup_cap(w):
    """Normal pop-up size limit (ui/zoom.py) — like the Product window."""
    try:
        from ui.zoom import popup_cap
        return popup_cap(w)
    except Exception:
        mw, mh = _max_client(w)
        return int(mw * 0.86), int(mh * 0.91)


def _limits(w, rw=0, rh=0):
    """How big a window may open: document windows (sales, purchase …)
    up to the whole desktop; every other pop-up up to the normal size —
    a bit more only when its fields really need it (never maximized)."""
    mw, mh = _max_client(w)
    if getattr(w, "_doc_window", False):
        return mw, mh
    cw, ch = _popup_cap(w)
    return (min(mw, max(cw, rw)), min(mh, max(ch, rh)))


def _fit_size(w):
    """New (width, height) so every field and button shows, or None when
    the window already fits. Never shrinks; capped to the screen."""
    try:
        w.update_idletasks()
        cw, ch = w.winfo_width(), w.winfo_height()
        rw, rh = w.winfo_reqwidth(), w.winfo_reqheight()
        if cw <= 1 or ch <= 1:
            return None
        mw, mh = _limits(w, rw, rh)
        nh = max(ch, min(rh, mh))
        nw = cw
        if rw > cw + 4 and cw < 900:       # big grid screens scroll sideways
            nw = max(cw, min(rw, int(cw * 1.3), mw))
        if nw == cw and nh == ch:
            return None
        return nw, nh
    except Exception:
        return None


def _clamp_xy(w, x, y, ww, wh):
    x0, y0, x1, y1 = _work_area(w)
    x = max(x0, min(x, x1 - ww - 16))
    y = max(y0, min(y, y1 - wh - _CAPTION - 8))
    return x, y


def _fit_to_content(w):
    """A dialog opened with a fixed size that is too small for its fields
    (buttons cut off at the bottom) grows to show everything."""
    size = _fit_size(w)
    if not size:
        return False
    try:
        nw, nh = size
        x, y = _clamp_xy(w, w.winfo_x(), w.winfo_y(), nw, nh)
        _raw_geo(w, f"{nw}x{nh}+{x}+{y}")
        return True
    except Exception:
        return False


def _maximize(w):
    """Big windows (invoice, purchase … forms) on a small screen open
    maximized — 100 % of the screen, like a Windows app."""
    try:
        w.state("zoomed")
        return
    except Exception:
        pass
    try:
        x0, y0, x1, y1 = _work_area(w)
        mw, mh = _max_client(w)
        _raw_geo(w, f"{mw}x{mh}+{x0}+{y0}")
    except Exception:
        pass


def _place_window(w, placed):
    """Runs just after a window appears: keep its buttons visible, grow it
    to fit, and centre it over its parent — ONE geometry change (Tk ignores
    a move made inside the <Map> event itself). Windows larger than the
    screen (or nearly) open maximized; nothing ever hides behind the
    taskbar."""
    try:
        if not w.winfo_exists():
            return
        _restyle_header(w)
        _keep_footer_visible(w)
        if getattr(w, "_keep_size", False):
            return                 # the window sets its own size (e.g. Product form)
        size = _fit_size(w)
        ww, wh = size or (w.winfo_width(), w.winfo_height())
        if getattr(w, "_doc_window", False):
            # sales / purchase / return / quotation: the item grid needs
            # the room — on a small screen they open maximized
            mw, mh = _max_client(w)
            try:
                resizable = any(w.resizable())
            except Exception:
                resizable = True
            if resizable and (ww >= mw * 0.94 or wh >= mh * 0.97):
                w._daybill_max = True
                _maximize(w)
                return
        else:
            # every other pop-up: a normal window (like the Product window)
            mw, mh = _limits(w, w.winfo_reqwidth(), w.winfo_reqheight())
        ww, wh = min(ww, mw), min(wh, mh)
        if placed:
            x, y = _clamp_xy(w, w.winfo_x(), w.winfo_y(), ww, wh)
            if size or (x, y) != (w.winfo_x(), w.winfo_y()) or \
                    (ww, wh) != (w.winfo_width(), w.winfo_height()):
                _raw_geo(w, f"{ww}x{wh}+{x}+{y}")
            return
        master = w.master.winfo_toplevel() if w.master is not None else None
        if master is not None and master is not w and master.winfo_ismapped():
            cx = master.winfo_rootx() + master.winfo_width() // 2
            cy = master.winfo_rooty() + master.winfo_height() // 2
        else:
            x0, y0, x1, y1 = _work_area(w)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        x, y = _clamp_xy(w, cx - ww // 2, cy - (wh + _CAPTION) // 2, ww, wh)
        _raw_geo(w, f"{ww}x{wh}+{x}+{y}")
    except Exception:
        pass




def fit_page(container, depth=0):
    """Pages inside the main window: rows packed BELOW the expanding table
    (button bars, totals) are re-anchored to the bottom edge, so on a
    small screen the table gets shorter instead of the buttons being cut
    off. When there is room the layout looks exactly the same."""
    if depth > 6 or container is None:
        return
    try:
        slaves = container.pack_slaves()
        infos = [sl.pack_info() for sl in slaves]
    except Exception:
        return
    try:
        exp = [i for i, inf in enumerate(infos)
               if str(inf.get("expand")) in ("1", "true", "True")]
        if (len(exp) == 1 and exp[0] < len(slaves) - 1
                and all(inf.get("side") in ("top", None) for inf in infos)):
            k = exp[0]
            anchor_w = slaves[k]
            for sl in reversed(slaves[k + 1:]):
                inf = sl.pack_info()
                opts = {kk: v for kk, v in inf.items()
                        if kk not in ("in", "before", "after", "side")}
                sl.pack_forget()
                sl.pack(side="bottom", before=anchor_w, **opts)
    except Exception:
        pass
    try:
        for sl in container.pack_slaves():
            if sl.winfo_class() in ("Frame", "TFrame", "Labelframe", "TLabelframe") and \
                    str(sl.pack_info().get("expand")) in ("1", "true", "True"):
                fit_page(sl, depth + 1)
    except Exception:
        pass

# ── Windows 11 look for dialog header bands ─────────────────────
# Dialogs were built with a coloured band at the top (white text on
# the brand colour). They now get a white header with dark bold title,
# a hairline under it — like a Windows 10/11 dialog — without touching
# each screen. The band's own colour is kept on the title when it had
# a meaning (red = payment, green = WhatsApp …).
_HEADER_EXTRA = {"#3A1FD6", "#2A14A8", "#128C7E", "#075E54"}


def _font_info(w):
    try:
        f = w.cget("font")
        size = abs(int(w.tk.call("font", "actual", f, "-size")))
        bold = str(w.tk.call("font", "actual", f, "-weight")) == "bold"
        return size, bold
    except Exception:
        return 10, False


def _lum(c, w=None):
    """Brightness 0..255 of a colour — '#RRGGBB' or a name like 'white'."""
    try:
        h = str(c).lstrip("#")
        if str(c).startswith("#") and len(h) == 6:
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        else:
            r, g, b = ((v >> 8) for v in (w or tk._default_root).winfo_rgb(c))
        return 0.299 * r + 0.587 * g + 0.114 * b
    except Exception:
        return 0


def _restyle_header(win):
    if getattr(win, "_hdr_restyled", False) or getattr(win, "_keep_header", False):
        return
    C = cfg.theme()
    if str(C.get("card_bg", "#FFFFFF")).upper() != "#FFFFFF":
        return                              # dark theme keeps its bands
    colors = {str(C.get(k, "")).upper() for k in
              ("primary", "primary_dark", "danger", "success", "info", "sidebar_bg")}
    colors |= _HEADER_EXTRA
    try:
        cands = list(win.pack_slaves()[:3])
        if len(win.pack_slaves()) == 1:     # one wrapper frame around it all
            cands += list(win.pack_slaves()[0].pack_slaves()[:2])
    except Exception:
        return
    for fr in cands:
        try:
            if fr.winfo_class() != "Frame":
                continue
            bg = str(fr.cget("bg")).upper()
            if bg not in colors:
                continue
            info = fr.pack_info()
            if info.get("side") not in ("top", None) or info.get("fill") not in ("x", "both"):
                continue
            if fr.winfo_reqheight() > 96:
                continue
            kids = fr.winfo_children()
            if not any(k.winfo_class() == "Label" and _lum(k.cget("fg"), k) > 170
                       for k in _descendants(fr)):
                continue
            _recolor_header(fr, bg, C)
            win._hdr_restyled = True
            return
        except Exception:
            continue


def _descendants(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        out.extend(_descendants(c))
    return out


def _recolor_header(fr, orig, C):
    white = C.get("card_bg", "#FFFFFF")
    text = C.get("text_primary", "#111827")
    muted = C.get("text_secondary", "#6B7280")
    keep = orig not in {str(C.get("primary", "")).upper(),
                        str(C.get("primary_dark", "")).upper(),
                        str(C.get("sidebar_bg", "")).upper(), "#3A1FD6", "#2A14A8"}
    title_done = False
    fr.config(bg=white)
    for w in _descendants(fr):
        try:
            cls = w.winfo_class()
            wbg = str(w.cget("bg")).upper()
        except Exception:
            continue
        try:
            if wbg == orig or wbg in ("#3A1FD6", "#2A14A8"):
                if cls in ("Frame", "Canvas", "Label", "Checkbutton", "Radiobutton", "Button"):
                    w.config(bg=white)
            if cls == "Label":
                if _lum(w.cget("fg"), w) > 170:
                    size, bold = _font_info(w)
                    if (bold or size >= 12) and not title_done:
                        w.config(fg=orig if keep else text)
                        title_done = True
                    elif bold or size >= 11:
                        w.config(fg=text)
                    else:
                        w.config(fg=muted)
            elif cls in ("Checkbutton", "Radiobutton"):
                if _lum(w.cget("fg"), w) > 170:
                    w.config(fg=text, activebackground=white, activeforeground=text,
                             selectcolor=white)
            elif cls == "Button" and str(w.cget("bg")).upper() == str(white).upper():
                if _lum(w.cget("fg"), w) > 170:
                    w.config(fg=text, activebackground=C.get("content_bg", "#F3F5F9"),
                             activeforeground=text)
        except Exception:
            pass
    # hairline under the header, like a Windows dialog
    try:
        line = tk.Frame(fr.master, bg=C.get("border", "#E2E6EE"), height=1)
        line.pack(fill="x", after=fr)
    except Exception:
        pass


# ── Windows 11 window frame ─────────────────────────────────────
# Rounded corners, a title bar in the app's own colour (white, or dark
# for a dark theme) and a thin border — set through the Windows DWM.
# Windows 10 and other systems simply ignore it.
_DWM = {"rounded": 33, "caption": 35, "text": 36, "border": 34, "dark": 20}


def _colorref(c):
    h = str(c).lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return r | (g << 8) | (b << 16)


def win11_frame(w):
    """Give a window the Windows 11 look (Settings ▸ System ▸
    Windows 11 window frame). Returns True when it was applied."""
    import sys as _s
    if not _s.platform.startswith("win"):
        return False
    try:
        if not cfg.flag("win11_frame", True) or getattr(w, "_win11_done", False):
            return False
        import ctypes
        w.update_idletasks()
        try:
            hwnd = int(w.wm_frame(), 16)
        except Exception:
            hwnd = ctypes.windll.user32.GetParent(w.winfo_id())
        if not hwnd:
            return False
        C = cfg.theme()
        card = C.get("card_bg", "#FFFFFF")
        dwm = ctypes.windll.dwmapi

        def put(attr, value):
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), ctypes.c_uint(attr),
                                             ctypes.byref(v), ctypes.sizeof(v))
        put(_DWM["dark"], 1 if _is_dark(card) else 0)
        put(_DWM["rounded"], 2)                                    # round corners
        put(_DWM["caption"], _colorref(card))                      # title bar = app colour
        put(_DWM["text"], _colorref(C.get("text_primary", "#111827")))
        try:                                                       # v6.7: an edge you can see
            from ui.compact import strong_border
            edge = strong_border(C)
        except Exception:
            edge = C.get("border", "#E2E6EE")
        put(_DWM["border"], _colorref(edge))
        w._win11_done = True
        return True
    except Exception:
        return False


def _center_new_window(e):
    w = e.widget
    try:
        if not isinstance(w, tk.Toplevel) or getattr(w, "_daybill_centred", False):
            return
        w._daybill_centred = True
        try:                               # Esc closes it (ui/close_guard.py)
            from ui import close_guard as _cg
            _cg.on_map(w)
        except Exception:
            pass
        try:                               # v6.7: clear edge + shadow, slim title strip
            from ui import compact as _cp
            w.after_idle(lambda: w.winfo_exists() and _cp.edges(w))
            if not w.overrideredirect():
                def _slim():
                    if not w.winfo_exists():
                        return
                    form = getattr(w, "_form", None)
                    if form is not None:
                        _cp.doc_form(form)
                    elif _cp.on():
                        _cp.strip(w)
                    try:                   # v6.8: Tally-style boxes everywhere
                        from ui import form_style as _fs
                        _fs.polish(w)
                    except Exception:
                        pass
                # a timer, not after_idle: forms call update_idletasks() while
                # they are still being built
                w.after(120, _slim)
                w.after(450, _slim)
        except Exception:
            pass
        if w.overrideredirect():
            return                         # popups, calendars, toasts
        win11_frame(w)
        try:
            if w.state() == "zoomed" or w.attributes("-fullscreen"):
                return
        except Exception:
            pass
        def _run():
            # runs twice: just after the window appears, and again once
            # forms that keep building (update() mid-build, own centring)
            # are finished — the last word on size/position is ours
            try:
                if not w.winfo_exists():
                    return
                try:
                    zoomed = w.state() == "zoomed"
                except Exception:
                    zoomed = False
                if getattr(w, "_daybill_max", False) or zoomed:
                    _restyle_header(w)
                    _keep_footer_visible(w)
                    if not zoomed:
                        _maximize(w)
                    return
                _place_window(w, getattr(w, "_daybill_placed", False))
            except Exception:
                pass
        w.after_idle(_run)
        w.after(260, _run)
    except Exception:
        pass


_NATIVE_WHEEL = ("Treeview", "Listbox", "Text")


def _on_wheel(e):
    try:
        top = e.widget.winfo_toplevel() if not isinstance(e.widget, str) else None
        if top is None:
            return
        w = top.winfo_containing(e.x_root, e.y_root)
        if w is None:
            return
        num = getattr(e, "num", 0)
        if num == 4:
            step = -1
        elif num == 5:
            step = 1
        else:
            step = -1 if getattr(e, "delta", 0) > 0 else 1
        try:
            focus = w.focus_get()
        except Exception:
            focus = None
        node = w
        while node is not None:
            cls = node.winfo_class()
            if cls == "TCombobox":
                return
            if cls in _NATIVE_WHEEL:
                # the widget's own binding already scrolls it when it has
                # focus (Windows) or is under the pointer (Linux)
                if node is focus or num in (4, 5):
                    return
                node.yview_scroll(step * 3, "units")
                return
            if cls == "Canvas":
                try:
                    if node.cget("yscrollcommand"):
                        first, last = node.yview()
                        if not (first <= 0.0 and last >= 1.0):
                            node.yview_scroll(step, "units")
                        return
                except Exception:
                    pass
            node = node.master
    except Exception:
        pass


def _edit_menu(e):
    w = e.widget
    try:
        if w.bind("<Button-3>"):
            return                     # the screen has its own menu
    except Exception:
        return
    try:
        state = str(w.cget("state"))
    except Exception:
        state = "normal"
    editable = state not in ("disabled", "readonly")
    m = tk.Menu(w, tearoff=0)

    def gen(ev):
        try:
            w.focus_set()
            w.event_generate(ev)
        except Exception:
            pass

    def sel_all():
        try:
            w.focus_set()
            if w.winfo_class() == "Text":
                w.tag_add("sel", "1.0", "end-1c")
            else:
                w.select_range(0, "end")
                w.icursor("end")
        except Exception:
            pass

    def clear():
        try:
            if w.winfo_class() == "Text":
                w.delete("1.0", "end")
            else:
                w.delete(0, "end")
        except Exception:
            pass
    m.add_command(label="Cut", accelerator="Ctrl+X", command=lambda: gen("<<Cut>>"),
                  state="normal" if editable else "disabled")
    m.add_command(label="Copy", accelerator="Ctrl+C", command=lambda: gen("<<Copy>>"))
    m.add_command(label="Paste", accelerator="Ctrl+V", command=lambda: gen("<<Paste>>"),
                  state="normal" if editable else "disabled")
    m.add_separator()
    m.add_command(label="Select All", accelerator="Ctrl+A", command=sel_all)
    m.add_command(label="Clear", command=clear, state="normal" if editable else "disabled")
    try:
        m.tk_popup(e.x_root, e.y_root)
    finally:
        try:
            m.grab_release()
        except Exception:
            pass


def _select_all_entry(e):
    try:
        e.widget.select_range(0, "end")
        e.widget.icursor("end")
    except Exception:
        pass
    return "break"


def _select_all_text(e):
    try:
        e.widget.tag_add("sel", "1.0", "end-1c")
    except Exception:
        pass
    return "break"


def _tree_rows(tree, only_selected):
    cols = list(tree.tk.splitlist(tree.cget("columns")))
    try:                                # only the columns on screen, in that order
        from ui.table_columns import shown_columns
        shown = shown_columns(tree)
    except Exception:
        shown = cols
    idx = [cols.index(c) for c in shown if c in cols] or list(range(len(cols)))
    ids = tree.selection() if only_selected else tree.get_children("")
    rows = []
    for iid in ids:
        vals = list(tree.item(iid, "values"))
        rows.append([str(vals[i]) if i < len(vals) else "" for i in idx])
    heads = [str(tree.heading(cols[i], "text")).rstrip(" ▲▼") for i in idx]
    try:
        from ui.table_columns import ShownList
        heads = ShownList(heads)
    except Exception:
        pass
    return heads, rows


def _tree_copy(e, whole=False):
    tree = e.widget if hasattr(e, "widget") else e
    try:
        heads, rows = _tree_rows(tree, not whole)
        if not rows:
            return
        text = "\n".join(["\t".join(heads)] + ["\t".join(r) for r in rows]) if whole \
            else "\n".join("\t".join(r) for r in rows)
        tree.clipboard_clear()
        tree.clipboard_append(text)
    except Exception:
        pass
    return "break"


def _tree_menu(e):
    tree = e.widget
    try:
        if tree.bind("<Button-3>"):
            return                     # the screen has its own menu
        if not tree.cget("columns"):
            return
    except Exception:
        return
    row = tree.identify_row(e.y)
    if row and row not in tree.selection():
        tree.selection_set(row)
        tree.focus(row)
    m = tk.Menu(tree, tearoff=0)
    if tree.bind("<Double-1>") and row:
        m.add_command(label="Open", accelerator="Enter", command=lambda: _tree_enter(e))
        m.add_separator()
    m.add_command(label="Copy row(s)", accelerator="Ctrl+C",
                  command=lambda: _tree_copy(tree),
                  state="normal" if tree.selection() else "disabled")
    m.add_command(label="Copy whole table", command=lambda: _tree_copy(tree, whole=True))
    m.add_command(label="Export to Excel…", command=lambda: _tree_export(tree))
    try:
        from ui import table_columns as _tc
        if not _tc._off(tree):
            m.add_separator()
            m.add_command(label="Columns…   (show, hide, order, width)",
                          command=lambda: _tc.ColumnsDialog(tree))
    except Exception:
        pass
    try:
        m.tk_popup(e.x_root, e.y_root)
    finally:
        try:
            m.grab_release()
        except Exception:
            pass


def _tree_export(tree):
    try:
        heads, rows = _tree_rows(tree, False)
        from modules.report_export import export_excel
        title = ""
        try:
            title = tree.winfo_toplevel().title()
        except Exception:
            pass
        export_excel(tree, (title or "Export").replace(" ", "_")[:40], heads, rows,
                     title=title or None)
    except Exception:
        pass


def _tree_enter(e):
    tree = e.widget
    try:
        if tree.bind("<Return>") or not tree.bind("<Double-1>"):
            return
        iid = tree.focus() or (tree.selection() or [None])[0]
        if not iid:
            return
        tree.see(iid)
        tree.update_idletasks()
        bbox = tree.bbox(iid)
        if not bbox:
            return
        x, y = bbox[0] + 5, bbox[1] + max(2, bbox[3] // 2)
        for _ in range(2):             # two quick clicks = the row's double-click
            tree.event_generate("<ButtonPress-1>", x=x, y=y)
            tree.event_generate("<ButtonRelease-1>", x=x, y=y)
        return "break"
    except Exception:
        return


def _tree_jump(tree, index):
    try:
        kids = tree.get_children("")
        if not kids:
            return
        iid = kids[index]
        tree.selection_set(iid)
        tree.focus(iid)
        tree.see(iid)
        return "break"
    except Exception:
        return
