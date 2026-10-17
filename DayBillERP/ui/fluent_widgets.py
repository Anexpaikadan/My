# ============================================================
# DayBill ERP — Fluent-style UI toolkit (Tkinter)
# ------------------------------------------------------------
# Small, dependency-free widgets used to give dense Tkinter forms a
# more modern, "Fluent/Zoho/ERPNext" feel: pill-shaped buttons, on/off
# switches, a single-open accordion, toast notifications, and simple
# red-border validation. Canvas-drawn where Tkinter has no native
# rounded-corner / shadow support — true CSS box-shadows aren't
# possible in Tk, so these approximate with flat color + soft borders.
# ============================================================

import tkinter as tk


# ── Rounded pill button (canvas-based) ─────────────────────────
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, bg="#2563EB", fg="white",
                 hover_bg=None, width=110, height=34, radius=8,
                 font=("Segoe UI", 10, "bold"), outline="", disabled=False):
        bgparent = parent["bg"] if isinstance(parent, (tk.Frame, tk.Canvas)) \
            else "#FFFFFF"
        try:                         # grows with the app Text size, so the text fits
            from ui.zoom import px
            width, height, radius = px(width), px(height), px(radius)
        except Exception:
            pass
        super().__init__(parent, width=width, height=height, bg=bgparent,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.bg = bg
        self.hover_bg = hover_bg or self._darken(bg)
        self.fg = fg
        self.radius = radius
        self.w = width
        self.h = height
        self.text = text
        self.font = font
        self.outline = outline
        self.disabled = disabled
        self._draw(bg)
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)
        self.bind("<Button-1>", self._click)

    @staticmethod
    def _darken(hexcolor, amt=0.12):
        try:
            hexcolor = hexcolor.lstrip("#")
            r, g, b = (int(hexcolor[i:i + 2], 16) for i in (0, 2, 4))
            r, g, b = (max(0, int(c * (1 - amt))) for c in (r, g, b))
            return "#%02x%02x%02x" % (r, g, b)
        except Exception:
            return hexcolor

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r,
               x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r,
               x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, fillcolor):
        self.delete("all")
        col = "#C9CDD4" if self.disabled else fillcolor
        self._round_rect(1, 1, self.w - 1, self.h - 1, self.radius,
                         fill=col, outline=self.outline)
        self.create_text(self.w // 2, self.h // 2, text=self.text,
                         fill=("#8A93A1" if self.disabled else self.fg),
                         font=self.font)

    def _hover_on(self, _e=None):
        try:
            if not self.disabled and self.winfo_exists():
                self._draw(self.hover_bg)
        except tk.TclError:
            pass

    def _hover_off(self, _e=None):
        try:
            if not self.disabled and self.winfo_exists():
                self._draw(self.bg)
        except tk.TclError:
            pass

    def _click(self, _e=None):
        if not self.disabled and self.command:
            self.command()

    def set_disabled(self, val=True):
        self.disabled = val
        self._draw(self.bg)


# ── On/off toggle switch (canvas-based, bound to a BooleanVar) ─
class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable, on_color="#27AE60",
                 off_color="#C9CDD4", command=None, width=42, height=22):
        bgparent = parent["bg"] if isinstance(parent, (tk.Frame, tk.Canvas)) \
            else "#FFFFFF"
        try:                         # grows with the app Text size, so the text fits
            from ui.zoom import px
            width, height = px(width), px(height)
        except Exception:
            pass
        super().__init__(parent, width=width, height=height, bg=bgparent,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.var = variable
        self.on_color = on_color
        self.off_color = off_color
        self.command = command
        self.w, self.h = width, height
        self._draw()
        self.bind("<Button-1>", self._toggle)
        try:                 # v6.9.4: follows its variable (two switches, one value)
            self._trace = variable.trace_add("write", lambda *_a: self._redraw())
            self.bind("<Destroy>", lambda e: self._untrace() if e.widget is self else None, add="+")
        except Exception:
            self._trace = None

    def _redraw(self):
        try:
            if self.winfo_exists():
                self._draw()
        except Exception:
            pass

    def _untrace(self):
        try:
            if self._trace:
                self.var.trace_remove("write", self._trace)
                self._trace = None
        except Exception:
            pass

    def _draw(self):
        self.delete("all")
        on = bool(self.var.get())
        track = self.on_color if on else self.off_color
        r = self.h / 2
        pts = [r, 2, self.w - r, 2, self.w - r, 2, self.w - 2, 2,
               self.w - 2, self.h - 2, self.w - r, self.h - 2,
               r, self.h - 2, 2, self.h - 2, 2, 2, r, 2]
        self.create_oval(2, 2, self.h - 2, self.h - 2, fill=track, outline="")
        self.create_oval(self.w - self.h + 2, 2, self.w - 2, self.h - 2,
                         fill=track, outline="")
        self.create_rectangle(r, 2, self.w - r, self.h - 2, fill=track,
                              outline="")
        kx = self.w - self.h + 3 if on else 3
        self.create_oval(kx, 3, kx + self.h - 6, self.h - 3,
                         fill="white", outline="#E1E4E9")

    def _toggle(self, _e=None):
        self.var.set(not bool(self.var.get()))
        self._draw()
        if self.command:
            self.command()

    def refresh(self):
        self._draw()


def labeled_toggle(parent, text, variable, C, command=None, font_size=10):
    """Row: [switch]  Label — the common pairing used throughout forms."""
    row = tk.Frame(parent, bg=C["content_bg"])
    sw = ToggleSwitch(row, variable, command=command)
    sw.pack(side="left")
    tk.Label(row, text=text, font=("Segoe UI", font_size), bg=C["content_bg"],
             fg=C["text_primary"]).pack(side="left", padx=(8, 0))
    return row, sw


# ── Accordion (single section open at a time) ──────────────────
class Accordion:
    def __init__(self, parent, C):
        self.parent = parent
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.sections = []          # (header_frame, body_frame, chevron_lbl)

    def add_section(self, title, icon="▸", expanded=False):
        C = self.C
        card = tk.Frame(self.frame, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))
        header = tk.Frame(card, bg=C["card_bg"], cursor="hand2")
        header.pack(fill="x")
        chevron = tk.Label(header, text="▾" if expanded else "▸",
                           font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                           fg=C["primary"])
        chevron.pack(side="left", padx=(14, 4), pady=10)
        tk.Label(header, text=f"{icon}  {title}", font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(side="left", pady=10)
        body_wrap = tk.Frame(card, bg=C["card_bg"])
        body = tk.Frame(body_wrap, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        idx = len(self.sections)

        def toggle(_e=None, i=idx):
            self._set_expanded(i, i != self._expanded_idx())

        header.bind("<Button-1>", toggle)
        chevron.bind("<Button-1>", toggle)
        self.sections.append({"card": card, "header": header,
                              "body_wrap": body_wrap, "body": body,
                              "chevron": chevron, "expanded": False})
        if expanded:
            self._set_expanded(idx, True)
        return body

    def _expanded_idx(self):
        for i, s in enumerate(self.sections):
            if s["expanded"]:
                return i
        return -1

    def _set_expanded(self, idx, val):
        for i, s in enumerate(self.sections):
            want = val if i == idx else False
            if want and not s["expanded"]:
                s["body_wrap"].pack(fill="both", expand=True)
                s["chevron"].configure(text="▾")
            elif not want and s["expanded"]:
                s["body_wrap"].pack_forget()
                s["chevron"].configure(text="▸")
            s["expanded"] = want

    def expand(self, idx):
        self._set_expanded(idx, True)


# ── Page navigation (header tabs that switch a single body area) ──
class PageNav:
    """A horizontal header nav bar + one shared body area. Clicking a
    nav button shows only that page's frame — a cleaner 'separate
    pages' feel than a stacked accordion, while still keeping only one
    section's content on screen at a time."""

    def __init__(self, parent, C):
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.nav_bar = tk.Frame(self.frame, bg=C["card_bg"],
                                highlightbackground=C["border"],
                                highlightthickness=1)
        self.nav_bar.pack(fill="x")
        self.body_host = tk.Frame(self.frame, bg=C["card_bg"],
                                  highlightbackground=C["border"],
                                  highlightthickness=1)
        self.body_host.pack(fill="both", expand=True)
        self.pages = []          # [{"key","btn","page"}]
        self._active = None

    def add_page(self, title, icon, key=None):
        """A page tab — Windows 11 style: the open page is marked with a
        blue line under its name. Alt+1…9 / Ctrl+Tab switch pages."""
        C = self.C
        key = key or title
        cell = tk.Frame(self.nav_bar, bg=C["card_bg"])
        cell.pack(side="right" if self._rtl() else "left")
        btn = tk.Button(cell, text=f"{icon}  {title}",
                        font=("Segoe UI", 10, "bold"), relief="flat",
                        bg=C["card_bg"], fg=C["text_secondary"],
                        activebackground=C["content_bg"], bd=0,
                        padx=16, pady=8, cursor="hand2")
        btn.pack(fill="x")
        bar = tk.Frame(cell, bg=C["card_bg"], height=3)
        bar.pack(fill="x", padx=12)
        page = tk.Frame(self.body_host, bg=C["content_bg"])
        entry = {"key": key, "btn": btn, "page": page, "bar": bar}
        btn.configure(command=lambda k=key: self.show(k))
        self.pages.append(entry)
        self._bind_keys()
        if self._active is None:
            self.show(key)
        return page

    @staticmethod
    def _rtl():
        try:
            from config.language import is_rtl
            return is_rtl()
        except Exception:
            return False

    def _bind_keys(self):
        """Alt+1 … Alt+9 open page 1…9; Ctrl+Tab / Ctrl+Shift+Tab next / back."""
        if getattr(self, "_keys_bound", False):
            return
        try:
            top = self.frame.winfo_toplevel()
        except Exception:
            return
        self._keys_bound = True
        for i in range(1, 10):
            top.bind("<Alt-Key-%d>" % i, lambda e, n=i: self._go(n - 1), add="+")
        top.bind("<Control-Tab>", lambda e: self.step(1), add="+")
        try:
            top.bind("<Control-ISO_Left_Tab>", lambda e: self.step(-1), add="+")
        except Exception:
            pass
        top.bind("<Control-Shift-Tab>", lambda e: self.step(-1), add="+")

    def _go(self, i):
        if 0 <= i < len(self.pages):
            self.show(self.pages[i]["key"])
            return "break"

    def step(self, d):
        keys = [e["key"] for e in self.pages]
        if not keys:
            return "break"
        i = keys.index(self._active) if self._active in keys else 0
        self.show(keys[(i + d) % len(keys)])
        return "break"

    def show(self, key):
        C = self.C
        for e in self.pages:
            active = e["key"] == key
            if active:
                e["page"].pack(fill="both", expand=True, padx=2, pady=2)
                e["btn"].configure(bg=C["card_bg"], fg=C["primary"],
                                   font=("Segoe UI", 10, "bold"))
                if e.get("bar") is not None:
                    e["bar"].configure(bg=C["primary"])
            else:
                e["page"].pack_forget()
                e["btn"].configure(bg=C["card_bg"], fg=C["text_secondary"],
                                   font=("Segoe UI", 10, "normal"))
                if e.get("bar") is not None:
                    e["bar"].configure(bg=C["card_bg"])
        self._active = key
        try:
            self.frame.event_generate("<<PageChanged>>")
        except Exception:
            pass

    def page_index(self, page_widget):
        for i, e in enumerate(self.pages):
            if e["page"] is page_widget:
                return i
        return -1

    def show_page(self, page_widget):
        i = self.page_index(page_widget)
        if i >= 0:
            self.show(self.pages[i]["key"])
def show_toast(win, message, kind="success", ms=2200):
    colors = {"success": ("#27AE60", "white"), "error": ("#E74C3C", "white"),
             "info": ("#2E86AB", "white")}
    bg, fg = colors.get(kind, colors["info"])
    try:
        t = tk.Toplevel(win)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        try:
            t.attributes("-alpha", 0.0)
        except Exception:
            pass
        frame = tk.Frame(t, bg=bg)
        frame.pack()
        tk.Label(frame, text=message, font=("Segoe UI", 10, "bold"), bg=bg,
                 fg=fg, padx=18, pady=10,
                 wraplength=max(240, int(win.winfo_width() * 0.6))).pack()
        win.update_idletasks()
        t.update_idletasks()
        tw, th = t.winfo_reqwidth(), t.winfo_reqheight()
        wx = win.winfo_rootx() + win.winfo_width() - tw - 20      # inside the window
        wy = win.winfo_rooty() + win.winfo_height() - th - 70
        wx = min(wx, t.winfo_screenwidth() - tw - 8)
        t.geometry(f"+{max(wx, 0)}+{max(wy, 0)}")

        def fade_in(a=0.0):
            a = min(1.0, a + 0.2)
            try:
                t.attributes("-alpha", a)
                if a < 1.0:
                    t.after(15, lambda: fade_in(a))
            except Exception:
                pass

        def fade_out(a=1.0):
            a = max(0.0, a - 0.15)
            try:
                t.attributes("-alpha", a)
                if a > 0:
                    t.after(20, lambda: fade_out(a))
                else:
                    t.destroy()
            except Exception:
                try:
                    t.destroy()
                except Exception:
                    pass

        fade_in()
        t.after(ms, fade_out)
    except Exception:
        pass    # non-critical — never let a toast crash the save flow


# ── Validation: red-border highlighting ─────────────────────────
def _is_ttk(widget):
    try:
        from tkinter import ttk
        return isinstance(widget, ttk.Widget)
    except Exception:
        return False


def _invalid_style_for(widget):
    """Return (and lazily create) an 'Invalid.<Class>' ttk style with a
    red field background/border so validation is visible even though
    ttk widgets don't support highlightthickness/highlightbackground."""
    from tkinter import ttk
    cls = widget.winfo_class()             # e.g. "TCombobox", "TEntry"
    name = "Invalid.%s" % cls
    style = ttk.Style()
    try:
        style.configure(name, fieldbackground="#FDEDEC",
                        bordercolor="#E74C3C", lightcolor="#E74C3C",
                        darkcolor="#E74C3C")
        style.map(name, fieldbackground=[("readonly", "#FDEDEC")])
    except Exception:
        pass
    return name


def mark_invalid(widget):
    try:
        if _is_ttk(widget):
            widget._normal_style = widget.cget("style") or ""
            widget.configure(style=_invalid_style_for(widget))
        else:
            widget.configure(highlightthickness=2, highlightbackground="#E74C3C",
                             highlightcolor="#E74C3C")
    except Exception:
        pass


def clear_invalid(widget):
    try:
        if _is_ttk(widget):
            widget.configure(style=getattr(widget, "_normal_style", ""))
        else:
            widget.configure(highlightthickness=1, highlightbackground="#D7DBE0",
                             highlightcolor="#D7DBE0")
    except Exception:
        pass


# ── Enter / Shift+Enter field navigation ─────────────────────────
def bind_enter_navigation(win):
    """Enter -> next field, Shift+Enter -> previous field. Only acts on
    plain Entry/Combobox/Checkbutton widgets so Text boxes, Treeviews,
    and widgets with their own Enter behavior (e.g. barcode lookup)
    keep working exactly as before."""
    SIMPLE = (tk.Entry, tk.Checkbutton)
    try:
        from tkinter import ttk
        SIMPLE = SIMPLE + (ttk.Entry, ttk.Combobox)
    except Exception:
        pass

    def go_next(event):
        w = event.widget
        if isinstance(w, SIMPLE):
            w.tk_focusNext().focus_set()
            return "break"

    def go_prev(event):
        w = event.widget
        if isinstance(w, SIMPLE):
            w.tk_focusPrev().focus_set()
            return "break"

    win.bind_class("Entry", "<Return>", go_next, add="+")
    win.bind_class("TEntry", "<Return>", go_next, add="+")
    win.bind_class("TCombobox", "<Return>", go_next, add="+")
    win.bind("<Shift-Return>", go_prev)
