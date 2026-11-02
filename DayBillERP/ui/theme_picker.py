# ============================================================
# DayBill ERP - 🎨 Theme picker (v6.2.1)
# ------------------------------------------------------------
# Top bar ▸ 🎨 Theme: a small window with a picture of every theme
# (side menu, top bar, a table, a button in its colours). Click one →
# the whole app changes at once (no restart) and it is remembered.
# "My own colour…" makes a theme from any colour you pick.
# Also in Settings ▸ System ▸ Theme.
# ============================================================

import tkinter as tk
from tkinter import colorchooser

from config import settings as cfg

TILE_W, TILE_H = 150, 86
PER_ROW = 3


def preview(canvas, t, w=TILE_W, h=TILE_H):
    """A tiny picture of the app in theme t."""
    c = canvas
    c.delete("all")
    sb = 34
    c.create_rectangle(0, 0, w, h, fill=t["content_bg"], outline="")
    c.create_rectangle(0, 0, sb, h, fill=t["sidebar_bg"], outline="")          # side menu
    for i, y in enumerate((14, 26, 38, 50, 62)):
        if i == 1:
            c.create_rectangle(4, y - 4, sb - 4, y + 5, fill=t.get("sidebar_active", t["primary"]),
                               outline="")
        c.create_line(8, y, sb - 9, y, fill=t.get("sidebar_text", "#FFFFFF") if i == 1
                      else t.get("sidebar_muted", "#9AA3C7"), width=2)
    c.create_rectangle(sb, 0, w, 15, fill=t.get("topbar_bg", "#FFFFFF"), outline="")  # top bar
    c.create_line(sb, 15, w, 15, fill=t["border"])
    c.create_rectangle(w - 34, 4, w - 6, 11, fill=t["primary"], outline="")
    x0, y0, x1, y1 = sb + 7, 21, w - 7, h - 7                                # a card with a table
    c.create_rectangle(x0, y0, x1, y1, fill=t["card_bg"], outline=t["border"])
    c.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y0 + 11, fill=t.get("heading_bg", t["content_bg"]),
                       outline="")
    for k in range(3):
        yy = y0 + 18 + k * 9
        c.create_line(x0 + 6, yy, x1 - 30, yy, fill=t["text_secondary"])
    c.create_rectangle(x1 - 26, y1 - 14, x1 - 5, y1 - 5, fill=t["primary"], outline="")


class ThemePicker:
    def __init__(self, anchor, on_apply=None):
        self.anchor, self.on_apply = anchor, on_apply
        cur = cfg.get("theme") or "daybill"
        top = self.win = tk.Toplevel(anchor)
        top.title("Theme")
        top.configure(bg="#FFFFFF")
        top.resizable(False, False)
        try:
            top.transient(anchor.winfo_toplevel())
        except Exception:
            pass
        tk.Label(top, text="🎨  Theme — whole app", font=("Segoe UI", 13, "bold"),
                 bg="#FFFFFF", fg="#111827").pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(top, text="Click a theme: the app changes at once and keeps it.",
                 font=("Segoe UI", 9), bg="#FFFFFF", fg="#6B7280").pack(anchor="w", padx=16, pady=(2, 8))
        grid = tk.Frame(top, bg="#FFFFFF")
        grid.pack(padx=12)
        self.tiles = {}
        for i, (key, name) in enumerate(cfg.theme_choices()):
            t = cfg.THEMES.get(key)
            if t is None:
                continue
            on = key == cur
            box = tk.Frame(grid, bg=t["primary"] if on else "#E5E7EB", padx=2, pady=2, cursor="hand2")
            box.grid(row=i // PER_ROW, column=i % PER_ROW, padx=5, pady=5)
            inner = tk.Frame(box, bg="#FFFFFF", cursor="hand2")
            inner.pack()
            cv = tk.Canvas(inner, width=TILE_W, height=TILE_H, highlightthickness=0, bd=0,
                           cursor="hand2")
            cv.pack()
            preview(cv, t)
            lb = tk.Label(inner, text=("✓  " if on else "") + name, font=("Segoe UI", 9, "bold" if on else "normal"),
                          bg="#FFFFFF", fg=t["primary"] if on else "#374151", cursor="hand2")
            lb.pack(fill="x", pady=(3, 4))
            for w in (box, inner, cv, lb):
                w.bind("<Button-1>", lambda e, k=key: self.pick(k))
            self.tiles[key] = box
        bar = tk.Frame(top, bg="#F3F4F6")
        bar.pack(fill="x", pady=(10, 0))
        tk.Button(bar, text="🎨  My own colour…", font=("Segoe UI", 9, "bold"), relief="flat",
                  bg="#FFFFFF", fg="#111827", bd=0, padx=12, pady=5, cursor="hand2",
                  highlightthickness=1, highlightbackground="#D1D5DB",
                  command=self.own_colour).pack(side="left", padx=12, pady=8)
        tk.Button(bar, text="Close", font=("Segoe UI", 9), relief="flat", bg="#FFFFFF",
                  fg="#111827", bd=0, padx=14, pady=5, cursor="hand2", highlightthickness=1,
                  highlightbackground="#D1D5DB", command=self.close).pack(side="right", padx=12, pady=8)
        top.bind("<Escape>", lambda e: self.close())
        try:
            top.update_idletasks()
            sw = top.winfo_screenwidth()
            x = min(anchor.winfo_rootx() + anchor.winfo_width() - top.winfo_reqwidth(),
                    sw - top.winfo_reqwidth() - 10)
            y = anchor.winfo_rooty() + anchor.winfo_height() + 6
            top.geometry("+%d+%d" % (max(0, x), max(0, y)))
        except Exception:
            pass
        top.focus_set()

    def pick(self, key, custom=None):
        try:
            if custom:
                cfg.set_theme("custom", custom)
            else:
                cfg.set_theme(key)
            cfg.save_settings()
        except Exception:
            pass
        self.close()
        if self.on_apply:
            try:
                self.on_apply()
            except Exception:
                pass

    def own_colour(self):
        start = cfg.get("theme_custom_color") or cfg.theme().get("primary", "#2563EB")
        try:
            rgb, hx = colorchooser.askcolor(color=start, title="Main colour of the app",
                                            parent=self.win)
        except Exception:
            hx = None
        if hx:
            self.pick("custom", hx)

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass
