# ============================================================
# DayBill ERP - MDI window manager
# ------------------------------------------------------------
# Turns the main content area into a desktop of child windows.
# Each child has a title bar with Minimize / Maximize-Restore /
# Close, can be dragged when floating, and appears as a button on
# the taskbar pinned to the bottom of the main window. Minimized
# windows collapse to that taskbar.
#
# Views are unchanged: open(key, title) returns a `body` Frame and
# the caller mounts the existing View into it exactly as before.
# ============================================================

import tkinter as tk


_GLYPHS = None


def caption_glyphs(widget):
    """Real Windows 10/11 caption icons when the font exists (Segoe
    Fluent Icons / Segoe MDL2 Assets), else plain Unicode look-alikes.
    -> (font, minimize, maximize, restore, close)"""
    global _GLYPHS
    if _GLYPHS is None:
        fams = ()
        try:
            from tkinter import font as tkfont
            fams = set(tkfont.families(widget))
        except Exception:
            pass
        for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if f in fams:
                _GLYPHS = ((f, 8), "\uE921", "\uE922", "\uE923", "\uE8BB")
                break
        else:
            _GLYPHS = (("Segoe UI Symbol", 10), "—", "☐", "❐", "✕")
    return _GLYPHS


def _norm(text):
    """letters/digits only, lower case (drops emoji and punctuation)"""
    import re
    return re.sub(r"[^\w]+", " ", str(text or ""), flags=re.U).replace("_", " ").strip().lower()


def dedupe_heading(body, title):
    """The window header already shows the page name and a sub-heading.
    Many pages also start with the same big title (and a line under it):
    hide that copy so the page shows its heading once."""
    want = _norm(title)
    if not want:
        return False
    try:
        from tkinter import font as tkfont
        body.update_idletasks()
        top = body.winfo_rooty()
    except Exception:
        return False

    def big(w):
        try:
            f = tkfont.Font(font=w.cget("font"))
            return abs(int(f.actual("size"))) >= 14
        except Exception:
            return False

    def hide(w):
        m = w.winfo_manager()
        if m == "pack":
            w.pack_forget()
        elif m == "grid":
            w.grid_remove()
        elif m == "place":
            w.place_forget()

    queue = [(body, 0)]
    while queue:
        w, depth = queue.pop(0)
        try:
            kids = w.winfo_children()
        except Exception:
            continue
        for i, ch in enumerate(kids):
            if depth < 5:
                queue.append((ch, depth + 1))
            try:
                if ch.winfo_class() != "Label" or not ch.winfo_ismapped():
                    continue
                if ch.winfo_rooty() - top > 150 or not big(ch):
                    continue
                txt = _norm(ch.cget("text"))
            except Exception:
                continue
            if not txt or not (txt == want or (want in txt and len(txt) <= len(want) + 14)
                               or (len(txt) >= 5 and txt in want)):
                continue
            # found the page's own title: hide it, its icon and the line under it
            parent = ch.master
            sibs = [k for k in parent.winfo_children() if k.winfo_ismapped()]
            j = sibs.index(ch) if ch in sibs else -1
            hide(ch)
            if j > 0:
                prev = sibs[j - 1]
                try:
                    if prev.winfo_class() == "Label" and not _norm(prev.cget("text")):
                        hide(prev)                       # 🧾 icon in front of it
                except Exception:
                    pass
            if 0 <= j < len(sibs) - 1:
                nxt = sibs[j + 1]
                try:
                    if nxt.winfo_class() == "Label" and not big(nxt) and _norm(nxt.cget("text")):
                        hide(nxt)                        # the sub-title line
                except Exception:
                    pass
            try:                                         # nothing left in that block
                if parent is not body and not any(k.winfo_manager() for k in parent.winfo_children()):
                    hide(parent)
            except Exception:
                pass
            return True
    return False


_BTN_HOVER = "#E9ECF2"
_CLOSE_HOVER = "#E81123"          # Windows close-button red
_GAP = 6                          # desktop margin around a maximized window (shows the shadow)


class MDIChild(tk.Frame):
    def __init__(self, manager, key, title, icon="", subtitle=""):
        C = manager.C
        try:                                   # v6.7: an edge you can see + soft shadow
            from ui.compact import strong_border, page_shadow
            edge = strong_border(C)
        except Exception:
            edge, page_shadow = C["border"], None
        super().__init__(manager.desktop, bg=C["card_bg"],
                         highlightbackground=edge, highlightthickness=1)
        self._shadow = page_shadow(self) if page_shadow else None
        self.manager = manager
        self.key = key
        self.title_text = title
        self.icon = icon or ""
        self.state = "max"          # 'max' | 'float' | 'min'
        self.prev_state = "max"
        self._float = None          # (x, y, w, h) when floating
        self._drag = None

        # ── page header: ONE slim line (v6.3) — icon · heading · sub-heading
        #    · window buttons. The buttons are packed first so a long title
        #    can never push them out.
        try:
            from ui.zoom import px
        except Exception:
            px = int
        bar_bg = C["card_bg"]
        bar = tk.Frame(self, bg=bar_bg)
        bar.pack(side="top", fill="x")
        self._bar = bar

        gf, g_min, g_max, g_res, g_close = caption_glyphs(self)
        self._g_max, self._g_res = g_max, g_res

        def tbtn(txt, cmd, hover, hover_fg):
            b = tk.Label(bar, text=txt, bg=bar_bg, fg="#374151",
                         font=gf, width=5, cursor="hand2")
            b.pack(side="right", fill="y")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(bg=hover, fg=hover_fg))
            b.bind("<Leave>", lambda e: b.config(bg=bar_bg, fg="#374151"))
            return b
        tbtn(g_close, self.ask_close, _CLOSE_HOVER, "white")
        self.max_btn = tbtn(g_res, self.toggle_max, _BTN_HOVER, "#111827")
        tbtn(g_min, self.minimize, _BTN_HOVER, "#111827")

        self.icon_lbl = tk.Label(bar, text=self.icon or "▣", bg=C.get("primary_light", "#EAF1FE"),
                                 fg=C["primary"], font=("Segoe UI Emoji", 10), width=2,
                                 padx=px(2), pady=0)
        self.icon_lbl.pack(side="left", padx=(px(10), px(8)), pady=px(4))
        tbox = tk.Frame(bar, bg=bar_bg)
        tbox.pack(side="left", fill="both", expand=True)
        self.title_lbl = tk.Label(tbox, text=title, bg=bar_bg, fg=C["text_primary"],
                                  font=("Segoe UI", 11, "bold"), anchor="w")
        self.title_lbl.pack(side="left")
        self.sub_lbl = tk.Label(tbox, text=subtitle or "", bg=bar_bg,
                                fg=C["text_secondary"], font=("Segoe UI", 9), anchor="w")
        if subtitle:
            self.sub_lbl.pack(side="left", padx=(px(10), 0))
        tk.Frame(self, bg=C["border"], height=1).pack(side="top", fill="x")

        # drag (only meaningful when floating)
        for w in (bar, tbox, self.title_lbl, self.sub_lbl, self.icon_lbl):
            w.bind("<Button-1>", self._drag_start, add="+")
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<Double-Button-1>", lambda e: self.toggle_max())

        # ── body (Views mount here) ──
        self.body = tk.Frame(self, bg=C["content_bg"])
        self.body.pack(side="top", fill="both", expand=True)

        self.bind("<Button-1>", lambda e: self.manager.focus(self), add="+")

    # ── drag ──
    def _drag_start(self, e):
        if self.state == "float":
            self._drag = (e.x_root, e.y_root)
            self.manager.focus(self)

    def _drag_move(self, e):
        if self.state != "float" or not self._drag:
            return
        dx = e.x_root - self._drag[0]
        dy = e.y_root - self._drag[1]
        x, y, w, h = self._float
        x = max(0, x + dx)
        y = max(0, y + dy)
        self._float = (x, y, w, h)
        self.place(x=x, y=y, width=w, height=h)
        self._drag = (e.x_root, e.y_root)

    # ── states ──
    def maximize(self):
        self.state = "max"
        self.max_btn.config(text=self._g_res)   # "restore down"
        self.place(x=_GAP, y=_GAP, relwidth=1, relheight=1,
                   width=-2 * _GAP, height=-2 * _GAP)
        self.lift()

    def floatify(self):
        self.state = "float"
        self.max_btn.config(text=self._g_max)   # "maximize"
        if not self._float:
            n = self.manager.cascade()
            dw = max(600, self.manager.desktop.winfo_width())
            dh = max(400, self.manager.desktop.winfo_height())
            w = max(560, min(1100, int(dw * 0.8)))
            h = max(360, min(720, int(dh * 0.82)))
            self._float = (min(30 + n, max(0, dw - w)), min(20 + n, max(0, dh - h)), w, h)
        x, y, w, h = self._float
        self.place_forget()
        self.place(x=x, y=y, width=w, height=h)
        self.lift()

    def toggle_max(self):
        if self.state == "max":
            self.floatify()
        else:
            self.maximize()
        self.manager.focus(self)

    def minimize(self):
        self.prev_state = self.state if self.state != "min" else self.prev_state
        self.state = "min"
        self.place_forget()
        self.manager.on_minimized(self)

    def restore(self):
        if self.state == "min":
            if self.prev_state == "float":
                self.floatify()
            else:
                self.maximize()
        self.manager.focus(self)

    def close(self):
        self.manager.close(self)

    def ask_close(self):
        """✕ on the window title bar: Yes / No first."""
        try:
            from ui.close_guard import _enabled, ask_close
            if _enabled() and not ask_close(self.winfo_toplevel(),
                                            "Close \"%s\"?\nهل تريد إغلاق هذه النافذة؟"
                                            % self.title_text):
                return
        except Exception:
            pass
        self.manager.close(self)


class MDIManager:
    def __init__(self, desktop, taskbar, theme):
        self.desktop = desktop
        self.taskbar = taskbar
        self.C = theme
        self.windows = {}      # key -> MDIChild
        self.buttons = {}      # key -> taskbar button frame
        self.active = None
        self._casc = 0
        self.on_focus = None        # main window: keep the menu highlight in step

    def cascade(self):
        self._casc = (self._casc + 24) % 160
        return self._casc

    # ── open / focus ──
    def open(self, key, title, icon="", subtitle=""):
        """Return a fresh body Frame to mount a View into, or None if the
        window already exists (it is restored & focused instead)."""
        if key in self.windows:
            self.windows[key].restore()
            return None
        child = MDIChild(self, key, title, icon, subtitle)
        self.windows[key] = child
        self._add_button(key, title, icon)
        child.maximize()
        self.focus(child)
        return child.body

    def focus(self, child):
        self.active = child
        try:
            child.lift()
        except Exception:
            pass
        self._refresh_buttons()
        if self.on_focus:
            try:
                self.on_focus(child.key)
            except Exception:
                pass

    def on_minimized(self, child):
        if self.active is child:
            self.active = None
        # focus the next visible window, if any
        for c in reversed(list(self.windows.values())):
            if c.state != "min":
                self.focus(c)
                break
        self._refresh_buttons()

    def close(self, child):
        key = child.key
        try:
            child.place_forget()
            child.destroy()
        except Exception:
            pass
        self.windows.pop(key, None)
        btn = self.buttons.pop(key, None)
        if btn:
            btn.destroy()
        if self.active is child:
            self.active = None
            for c in reversed(list(self.windows.values())):
                if c.state != "min":
                    self.focus(c)
                    break
        self._refresh_buttons()

    # ── taskbar (Windows 11 style: flat buttons, blue underline = active) ──
    def _add_button(self, key, title, icon=""):
        C = self.C
        bg = self.taskbar.cget("bg")
        b = tk.Frame(self.taskbar, bg=bg, cursor="hand2")
        b.pack(side="left", padx=2, pady=(3, 0), fill="y")
        top = tk.Frame(b, bg=bg)
        top.pack(side="top", fill="both", expand=True)
        lbl = tk.Label(top, text=((icon + "  ") if icon else "") + title[:22], bg=bg,
                       fg=C["text_primary"], font=("Segoe UI", 9), padx=10, cursor="hand2")
        lbl.pack(side="left", fill="y")
        x = tk.Label(top, text="✕", bg=bg, fg=C["text_secondary"],
                     font=("Segoe UI", 8), padx=4, cursor="hand2")
        x.pack(side="right", fill="y")
        line = tk.Frame(b, bg=bg, height=3)
        line.pack(side="bottom", fill="x", padx=12)
        for w in (b, top, lbl):
            w.bind("<Button-1>", lambda e, k=key: self._on_task(k))
        x.bind("<Button-1>", lambda e, k=key: self.windows[k].ask_close()
               if k in self.windows else None)
        x.bind("<Enter>", lambda e: x.config(fg=C["danger"]))
        x.bind("<Leave>", lambda e: x.config(fg=C["text_secondary"]))
        b._lbl, b._top, b._x, b._line = lbl, top, x, line
        b._full = ((icon + "  ") if icon else "") + title[:22]
        b._short = ((icon + " ") if icon else "") + title[:10]
        b._tiny = icon or title[:3]
        self.buttons[key] = b
        if not getattr(self.taskbar, "_fit_bound", False):
            self.taskbar._fit_bound = True
            self.taskbar.bind("<Configure>", lambda e: self._fit_taskbar(), add="+")

    def _on_task(self, key):
        ch = self.windows.get(key)
        if not ch:
            return
        if ch.state == "min":
            ch.restore()
        elif self.active is ch:
            ch.minimize()
        else:
            self.focus(ch)

    def _fit_taskbar(self):
        """Many open windows: shorten the taskbar buttons so all fit."""
        try:
            avail = self.taskbar.winfo_width() - 60 - getattr(self, "reserve_right", 0)
            if avail <= 0 or not self.buttons:
                return
            for mode in ("_full", "_short", "_tiny"):
                for b in self.buttons.values():
                    b._lbl.config(text=getattr(b, mode),
                                  padx=5 if mode == "_tiny" else 10)
                    if mode == "_tiny":
                        b._x.pack_forget()         # icon only; close from the window
                    elif not b._x.winfo_manager():
                        b._x.pack(side="right", fill="y")
                self.taskbar.update_idletasks()
                need = sum(b.winfo_reqwidth() + 4 for b in self.buttons.values())
                if need <= avail:
                    break
        except Exception:
            pass

    def _refresh_buttons(self):
        C = self.C
        base = self.taskbar.cget("bg")
        for key, b in self.buttons.items():
            ch = self.windows.get(key)
            active = (ch is self.active and ch and ch.state != "min")
            minimized = bool(ch and ch.state == "min")
            bg = C.get("primary_light", "#EAF1FE") if active else base
            try:
                for w in (b, b._top, b._lbl, b._x):
                    w.config(bg=bg)
                b._lbl.config(fg=C["primary"] if active else
                              (C["text_secondary"] if minimized else C["text_primary"]),
                              font=("Segoe UI", 9, "bold" if active else "normal"))
                b._line.config(bg=C["primary"] if active else
                               (C["border"] if not minimized else base))
            except Exception:
                pass
        try:
            self.taskbar.after_idle(self._fit_taskbar)
        except Exception:
            pass
