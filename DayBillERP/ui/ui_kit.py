# ============================================================
# DayBill ERP - UI Kit (global modern styling)
# ------------------------------------------------------------
# apply_modern_theme(root) restyles EVERY form field in the app at
# once — all ttk widgets (Combobox, Entry, Treeview, Notebook,
# Spinbox, Checkbutton, Radiobutton, Scrollbar, Button) through a
# single ttk.Style, plus modern defaults for classic tk widgets via
# root.option_add. Call it once after the root window exists.
#
# Existing screens that set their own colors/relief still win (these
# are defaults); unstyled fields pick up the modern look automatically.
# ============================================================

import tkinter as tk
from tkinter import ttk

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg


def apply_modern_theme(root):
    C = cfg.theme()
    primary = C.get("primary", "#3A1FD6")
    accent = C.get("accent", "#7ED957")
    card = C.get("card_bg", "#FFFFFF")
    content = C.get("content_bg", "#F6F5FD")
    text = C.get("text_primary", "#1A1438")
    muted = C.get("text_secondary", "#6B7280")
    border = C.get("border", "#E3E0F4")
    field_bg = "#FFFFFF"
    field_focus = primary
    fborder = C.get("field_border", border)
    FONT = ("Segoe UI", 10)
    FONT_BOLD = ("Segoe UI", 10, "bold")

    # ── classic tk widget defaults (apply app-wide) ──
    # Only affect widgets that don't set these explicitly.
    opt = root.option_add
    opt("*Font", "{Segoe UI} 10")
    opt("*Entry.relief", "flat")
    opt("*Entry.borderWidth", 1)
    opt("*Entry.highlightThickness", 1)
    opt("*Entry.highlightColor", field_focus)
    opt("*Entry.highlightBackground", fborder)
    opt("*Entry.background", field_bg)
    opt("*Entry.foreground", text)
    opt("*Entry.insertBackground", primary)
    opt("*Entry.font", "{Segoe UI} 11")
    opt("*Spinbox.relief", "flat")
    opt("*Spinbox.borderWidth", 1)
    opt("*Spinbox.highlightThickness", 1)
    opt("*Spinbox.highlightColor", field_focus)
    opt("*Spinbox.highlightBackground", fborder)
    opt("*Text.relief", "flat")
    opt("*Text.borderWidth", 1)
    opt("*Text.highlightThickness", 1)
    opt("*Text.highlightColor", field_focus)
    opt("*Text.highlightBackground", fborder)
    opt("*Listbox.relief", "flat")
    opt("*Listbox.borderWidth", 1)
    opt("*Listbox.highlightThickness", 1)
    opt("*Listbox.highlightColor", field_focus)
    opt("*Listbox.highlightBackground", fborder)
    opt("*Listbox.font", "{Segoe UI} 10")
    opt("*Listbox.activeStyle", "none")
    # cards / chips drawn with a 1-px highlight border never turn black
    for _cls in ("Frame", "Label", "Canvas", "Labelframe"):
        opt(f"*{_cls}.highlightColor", border)

    # ── ttk styling (restyles all themed widgets globally) ──
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Entry / Spinbox / Combobox field look
    for name in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(name, fieldbackground=field_bg, background=field_bg,
                        foreground=text, bordercolor=fborder, relief="flat",
                        lightcolor=field_bg, darkcolor=field_bg,
                        arrowcolor=primary, padding=6, borderwidth=1)
        style.map(name,
                  bordercolor=[("focus", field_focus)],
                  fieldbackground=[("readonly", field_bg), ("disabled", content)],
                  foreground=[("disabled", muted)])
    style.configure("TCombobox", arrowsize=14)
    root.option_add("*TCombobox*Listbox.background", field_bg)
    root.option_add("*TCombobox*Listbox.foreground", text)
    root.option_add("*TCombobox*Listbox.selectBackground", primary)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*TCombobox*Listbox.font", "{Segoe UI} 10")

    # Buttons
    style.configure("TButton", background=primary, foreground="white",
                    relief="flat", padding=(14, 7), font=FONT_BOLD,
                    borderwidth=0, focuscolor=_shade(primary, 40))
    style.map("TButton",
              background=[("active", _shade(primary, -16)), ("pressed", _shade(primary, -28))],
              foreground=[("disabled", "#FFFFFFAA")])
    style.configure("Ghost.TButton", background=card, foreground=text,
                    bordercolor=border, borderwidth=1)
    style.map("Ghost.TButton", background=[("active", content)])

    # Checkbutton / Radiobutton
    for name in ("TCheckbutton", "TRadiobutton"):
        style.configure(name, background=card, foreground=text, font=FONT,
                        focuscolor=primary)
        style.map(name, foreground=[("disabled", muted)])

    # Notebook (tabs)
    style.configure("TNotebook", background=content, borderwidth=0)
    style.configure("TNotebook.Tab", background=content, foreground=muted,
                    padding=(16, 8), font=FONT_BOLD, borderwidth=0,
                    lightcolor=content, bordercolor=border)
    style.map("TNotebook.Tab",
              background=[("selected", card)],
              foreground=[("selected", primary)])

    # Treeview (tables) — Windows 11 look: light-grey bold headings,
    # thin grid line under the heading, light-blue selected row.
    heading_bg = C.get("heading_bg", content)
    select_bg = C.get("select_bg", C.get("primary_light", "#EAF1FE"))
    style.configure("Treeview", background=card, fieldbackground=card,
                    foreground=text, rowheight=30, borderwidth=1,
                    bordercolor=border, lightcolor=card, darkcolor=border,
                    font=("Segoe UI", 10))
    style.configure("Treeview.Heading", background=heading_bg, foreground="#374151",
                    font=("Segoe UI", 9, "bold"), relief="flat", padding=(8, 7),
                    bordercolor=border, lightcolor=heading_bg, darkcolor=border)
    style.map("Treeview",
              background=[("selected", select_bg)],
              foreground=[("selected", C.get("select_fg", "white"))])
    style.map("Treeview.Heading", background=[("active", _shade(heading_bg, -10))])

    # Scrollbars — Windows 11: slim grey bar, no arrow buttons
    try:
        from ui.zoom import px as _px
    except Exception:
        _px = lambda n: n
    thumb = C.get("scroll_thumb", "#C4CAD4")
    for orient, o in (("Vertical.TScrollbar", "Vertical"), ("Horizontal.TScrollbar", "Horizontal")):
        try:
            style.layout(orient, [(o + ".Scrollbar.trough", {"sticky": "nswe", "children": [
                (o + ".Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        except Exception:
            pass
        style.configure(orient, background=thumb, troughcolor=content,
                        bordercolor=content, arrowcolor=muted, relief="flat",
                        borderwidth=0, lightcolor=thumb, darkcolor=thumb,
                        gripcount=0, width=_px(10), arrowsize=_px(10))
        style.map(orient, background=[("active", "#9AA3B2"), ("pressed", "#7D8594")],
                  lightcolor=[("active", "#9AA3B2"), ("pressed", "#7D8594")],
                  darkcolor=[("active", "#9AA3B2"), ("pressed", "#7D8594")])

    # Menus (right-click menus, ▾ menus) — white, light hover, no 3-D edge
    for k, v in (("*Menu.background", card), ("*Menu.foreground", text),
                 ("*Menu.activeBackground", C.get("primary_light", "#EAF1FE")),
                 ("*Menu.activeForeground", text), ("*Menu.relief", "flat"),
                 ("*Menu.activeBorderWidth", 0), ("*Menu.borderWidth", 1),
                 ("*Menu.font", "{Segoe UI} 10"), ("*Menu.selectColor", primary)):
        try:
            opt(k, v)
        except Exception:
            pass

    # Progressbar + LabelFrame
    style.configure("TProgressbar", background=primary, troughcolor=content,
                    borderwidth=0)
    style.configure("TLabelframe", background=card, bordercolor=border,
                    relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=card, foreground=primary,
                    font=FONT_BOLD)

    # ── v2 named styles (semantic variants for all screens) ──
    danger = C.get("danger", "#DC2626")
    success = C.get("success", "#5FB840")
    warning = C.get("warning", "#D97706")

    style.configure("Danger.TButton", background=danger, foreground="white")
    style.map("Danger.TButton",
              background=[("active", _shade(danger, -16)),
                          ("pressed", _shade(danger, -28))])
    style.configure("Success.TButton", background=success, foreground="white")
    style.map("Success.TButton",
              background=[("active", _shade(success, -16)),
                          ("pressed", _shade(success, -28))])
    style.configure("Warning.TButton", background=warning, foreground="white")
    style.map("Warning.TButton",
              background=[("active", _shade(warning, -16))])

    style.configure("Title.TLabel", background=content, foreground=text,
                    font=("Segoe UI", 18, "bold"))
    style.configure("H2.TLabel", background=content, foreground=text,
                    font=("Segoe UI", 13, "bold"))
    style.configure("Muted.TLabel", background=content, foreground=muted,
                    font=("Segoe UI", 9))
    style.configure("Card.TFrame", background=card)

    # Notebook tab hover feedback
    style.map("TNotebook.Tab",
              background=[("selected", card), ("active", _shade(content, -8))],
              foreground=[("selected", primary), ("active", text)])

    # Slightly airier default paddings
    style.configure("Treeview", rowheight=30)
    style.configure("TCombobox", padding=(8, 6))
    style.configure("TEntry", padding=(8, 6))

    # ── Excel-style keyboard flow for ALL forms in ALL modules ──
    # Enter / numpad-Enter -> next field; Enter on buttons invokes;
    # widgets with their own <Return> handler keep first priority.
    try:
        from ui.ui_polish import enable_form_flow, enable_windows_behaviour
        enable_form_flow(root)
        enable_windows_behaviour(root)      # wheel, right-click, Ctrl+A, tables
    except Exception:
        pass

    return style


def _shade(hex_color, delta):
    """Lighten (+) or darken (−) a #RRGGBB color by delta (0-255)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        f = lambda v: max(0, min(255, v + delta))
        return f"#{f(r):02X}{f(g):02X}{f(b):02X}"
    except Exception:
        return hex_color


# ── optional factory helpers for new screens ──────────────────────
def modern_entry(parent, textvariable=None, bg="#FFFFFF", **kw):
    C = cfg.theme()
    return tk.Entry(parent, textvariable=textvariable, font=("Segoe UI", 11),
                    bg=bg, fg=C.get("text_primary", "#1A1438"), relief="solid",
                    bd=1, highlightthickness=1, highlightcolor=C.get("primary"),
                    highlightbackground=C.get("border", "#E3E0F4"), **kw)


def field(parent, label, textvariable=None, **kw):
    """Label-over-input field group, modern spacing."""
    C = cfg.theme()
    wrap = tk.Frame(parent, bg=parent["bg"])
    tk.Label(wrap, text=label, font=("Segoe UI", 9), bg=parent["bg"],
             fg=C.get("text_secondary", "#6B7280")).pack(anchor="w", pady=(0, 3))
    e = modern_entry(wrap, textvariable, **kw)
    e.pack(fill="x", ipady=5)
    wrap.entry = e
    return wrap


# ── Windows 11 action buttons (colour tile, shortcut on top) ──────
def key_style(color, key="", label="", bold=True):
    """Options for a coloured two-line action button:
            F9
            Save Draft
    Works for tk.Button / tk.Menubutton (and print_menu.print_button)."""
    return dict(text=f"{key}\n{label}" if key else label,
                font=("Segoe UI", 9, "bold" if bold else "normal"),
                bg=color, fg="white", activebackground=_shade(color, -22),
                activeforeground="white", relief="flat", bd=0, padx=16, pady=4,
                justify="left", anchor="w", cursor="hand2", highlightthickness=0)


def key_button(parent, color, key, label, command, **kw):
    opts = key_style(color, key, label)
    opts.update(kw)
    return tk.Button(parent, command=command, **opts)


def ghost_key_style(key="", label=""):
    C = cfg.theme()
    return dict(text=f"{key}\n{label}" if key else label, font=("Segoe UI", 9),
                bg=C.get("card_bg", "#FFFFFF"), fg=C.get("text_primary", "#111827"),
                activebackground=C.get("content_bg", "#F3F5F9"), relief="flat", bd=0,
                padx=16, pady=4, justify="left", anchor="w", cursor="hand2",
                highlightthickness=1, highlightbackground=C.get("field_border", "#CDD4DF"))


def total_box(parent, label, var, big_font=16):
    """Solid blue 'Total' box (white text) like the invoice mock-up."""
    C = cfg.theme()
    bg = C.get("primary", "#2563EB")
    f = tk.Frame(parent, bg=bg, padx=14, pady=4)
    tk.Label(f, text=label, font=("Segoe UI", 8, "bold"), bg=bg,
             fg=_shade(bg, 150) if False else "#DCE8FF").pack(anchor="w")
    tk.Label(f, textvariable=var, font=("Segoe UI", big_font, "bold"), bg=bg,
             fg="white").pack(anchor="e")
    return f


def slim_key_style(color, key="", label="", bold=True):
    """v6.9: one-line action button ('F9  Save Draft') — half the height
    of key_style's two-line button; same colours."""
    st = key_style(color, "", ("%s  %s" % (key, label)).strip() if key else label, bold)
    st.update(pady=3, padx=12, justify="center", anchor="center")
    return st


def slim_ghost_key_style(key="", label=""):
    st = ghost_key_style("", ("%s  %s" % (key, label)).strip() if key else label)
    st.update(pady=3, padx=12, justify="center", anchor="center")
    return st


def total_strip(parent, cells, total, C=None):
    """v6.9: document totals on ONE slim line:
        Qty 98   Gross 1,316.40   …        [ NET TOTAL (SAR)  1,513.86 ]
    cells = [(label, key, colour or None)], total = (label, key).
    Returns {key: StringVar} (the same keys the forms already use)."""
    C = C or cfg.theme()
    out = {}
    row = tk.Frame(parent, bg=C["card_bg"])
    row.pack(fill="x", padx=10, pady=3)
    bg = C.get("primary", "#2563EB")
    box = tk.Frame(row, bg=bg, padx=12, pady=2)
    box.pack(side="right")
    tk.Label(box, text=total[0], font=("Segoe UI", 8, "bold"), bg=bg,
             fg="#DCE8FF").pack(side="left", padx=(0, 10))
    out[total[1]] = tk.StringVar(value="0.00")
    tk.Label(box, textvariable=out[total[1]], font=("Segoe UI", 14, "bold"), bg=bg,
             fg="white").pack(side="left")
    for i, (label, key, colour) in enumerate(cells):
        tk.Label(row, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C.get("text_secondary", "#6B7280")).pack(side="left", padx=(0 if i == 0 else 16, 4))
        out[key] = tk.StringVar(value="0.00")
        tk.Label(row, textvariable=out[key], font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                 fg=colour or C.get("text_primary", "#111827")).pack(side="left")
    return out


def fit_columns(tree, min_width=50):
    """Keep every column of a table on screen: when the table is narrower
    than its columns, all columns shrink in proportion (never below
    min_width); when it is wider, they grow back to their set widths and
    the stretch columns take the rest."""
    try:
        from ui.zoom import raw_column, px
    except Exception:
        raw_column, px = None, (lambda n: n)
    cols = list(tree["columns"])
    base = {c: int(tree.column(c, "width")) for c in cols}
    tree._fit_base = base

    def on_conf(e=None):
        try:
            avail = tree.winfo_width() - 4
            if avail < 100:
                return
            total = sum(base.values()) or 1
            f = min(1.0, avail / total)
            lo = px(min_width)
            for c in cols:
                w = max(lo, int(base[c] * f))
                if raw_column:
                    raw_column(tree, c, width=w)
                else:
                    tree.column(c, width=w)
        except Exception:
            pass
    tree.bind("<Configure>", lambda e: tree.after_idle(on_conf), add="+")
    tree.after_idle(on_conf)
    return on_conf
