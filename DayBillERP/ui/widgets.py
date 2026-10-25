# ============================================================
# Saudi Arabia ERP - Shared UI Widgets & Helpers
# Reusable components for all modules
# ============================================================

import tkinter as tk
from tkinter import ttk
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg
from config.language import t, is_rtl


# ─────────────────────────────────────────────────────────────
# TOAST NOTIFICATION (top-right popup)
# ─────────────────────────────────────────────────────────────
def show_toast(root, message: str, kind: str = "success", duration: int = 3000):
    """Show a floating toast notification."""
    C = cfg.theme()
    colors = {
        "success": (C["success"], "✅"),
        "error":   (C["danger"],  "❌"),
        "warning": (C["warning"], "⚠️"),
        "info":    (C["info"],    "ℹ️"),
    }
    color, icon = colors.get(kind, (C["info"], "ℹ️"))

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.configure(bg=color)

    tk.Label(toast, text=f"  {icon}  {message}  ",
             font=("Segoe UI", 10), bg=color, fg="white",
             padx=10, pady=10).pack()

    # Position: top-right
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    toast.update_idletasks()
    tw = toast.winfo_width()
    toast.geometry(f"+{sw - tw - 30}+30")

    toast.after(duration, toast.destroy)


# ─────────────────────────────────────────────────────────────
# CONFIRM DIALOG (styled)
# ─────────────────────────────────────────────────────────────
def confirm_dialog(title: str, message: str) -> bool:
    """Custom styled confirm dialog. Returns True if Yes."""
    import tkinter.messagebox as mb
    return mb.askyesno(title, message)


# ─────────────────────────────────────────────────────────────
# SECTION HEADER (used in forms)
# ─────────────────────────────────────────────────────────────
def section_header(parent, text: str, icon: str = ""):
    C = cfg.theme()
    tk.Frame(parent, bg=C["border"], height=1).pack(
        fill="x", padx=20, pady=(16, 0))
    f = tk.Frame(parent, bg=C["content_bg"])
    f.pack(fill="x", padx=20, pady=(8, 0))
    tk.Label(f, text=f"{icon}  {text}" if icon else text,
             font=("Segoe UI", 10, "bold"),
             bg=C["content_bg"], fg=C["primary"]).pack(side="left")
    return f


# ─────────────────────────────────────────────────────────────
# AMOUNT LABEL (formatted SAR)
# ─────────────────────────────────────────────────────────────
def format_sar(amount) -> str:
    try:
        return f"{float(amount):,.2f} SAR"
    except Exception:
        return "0.00 SAR"


# ─────────────────────────────────────────────────────────────
# STATUS BADGE
# ─────────────────────────────────────────────────────────────
def status_badge(parent, status: str) -> tk.Label:
    C = cfg.theme()
    configs = {
        "confirmed":  (C["success"], "#F0FDF4", "✅ Confirmed"),
        "draft":      (C["warning"], "#FFFBEB", "📝 Draft"),
        "cancelled":  (C["danger"],  "#FEF2F2", "❌ Cancelled"),
        "paid":       (C["success"], "#F0FDF4", "✅ Paid"),
        "unpaid":     (C["danger"],  "#FEF2F2", "⏳ Unpaid"),
        "partial":    (C["warning"], "#FFFBEB", "◑ Partial"),
        "reported":   (C["info"],    "#EFF6FF", "📤 Reported"),
        "cleared":    (C["success"], "#F0FDF4", "✅ Cleared"),
        "rejected":   (C["danger"],  "#FEF2F2", "❌ Rejected"),
        "pending":    (C["warning"], "#FFFBEB", "⏳ Pending"),
    }
    fg, bg, text = configs.get(status.lower(), (C["text_secondary"], C["border"], status))
    lbl = tk.Label(parent, text=text, font=("Segoe UI", 8, "bold"),
                   bg=bg, fg=fg, padx=8, pady=3, relief="flat")
    return lbl


# ─────────────────────────────────────────────────────────────
# SCROLLABLE FRAME
# ─────────────────────────────────────────────────────────────
class ScrollableFrame(tk.Frame):
    def __init__(self, parent, **kwargs):
        C = cfg.theme()
        super().__init__(parent, bg=C["content_bg"], **kwargs)

        canvas = tk.Canvas(self, bg=C["content_bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(canvas, bg=C["content_bg"])
        win_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        self.inner.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Mouse wheel — only while the pointer is over THIS area, so other
        # screens/lists keep their own scrolling.
        def _wheel(e):
            try:
                if canvas.bbox("all") and canvas.bbox("all")[3] > canvas.winfo_height():
                    step = -1 * (e.delta // 120) if e.delta else (-1 if e.num == 4 else 1)
                    canvas.yview_scroll(step, "units")
            except tk.TclError:
                pass

        def _on(_e):
            canvas.bind_all("<MouseWheel>", _wheel)
            canvas.bind_all("<Button-4>", _wheel)
            canvas.bind_all("<Button-5>", _wheel)

        def _off(_e):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    canvas.unbind_all(seq)
                except tk.TclError:
                    pass
        self.bind("<Enter>", _on)
        self.bind("<Leave>", _off)
        self.canvas = canvas


# ─────────────────────────────────────────────────────────────
# FORM FIELD (label + entry, used inside forms)
# ─────────────────────────────────────────────────────────────
class FormField:
    def __init__(self, parent, label: str, key: str,
                 var_dict: dict, state: str = "normal",
                 required: bool = False, rtl: bool = False,
                 width: int = None):
        C = cfg.theme()
        lbl_text = f"{label} *" if required else label
        tk.Label(parent, text=lbl_text,
                 font=("Segoe UI", 9, "bold" if required else "normal"),
                 bg=C["content_bg"],
                 fg=C["primary"] if required else C["text_secondary"],
                 anchor="e" if rtl else "w").pack(fill="x")

        var = tk.StringVar()
        var_dict[key] = var

        opts = dict(
            textvariable=var,
            font=("Segoe UI", 10),
            bg="white" if state == "normal" else C["content_bg"],
            fg=C["text_primary"],
            relief="solid", bd=1, state=state,
            justify="right" if rtl else "left"
        )
        if width:
            opts["width"] = width

        e = tk.Entry(parent, **opts)
        e.pack(fill="x", ipady=6, pady=(3, 0))
        self.var = var
        self.entry = e


# ─────────────────────────────────────────────────────────────
# PAGINATION BAR
# ─────────────────────────────────────────────────────────────
class PaginationBar(tk.Frame):
    def __init__(self, parent, total: int = 0, per_page: int = 50,
                 on_page_change=None):
        C = cfg.theme()
        super().__init__(parent, bg=C["content_bg"])
        self.total        = total
        self.per_page     = per_page
        self.current_page = 1
        self.on_change    = on_page_change
        self._build(C)

    def _build(self, C):
        self.info_var = tk.StringVar()
        tk.Label(self, textvariable=self.info_var,
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")

        btn_frame = tk.Frame(self, bg=C["content_bg"])
        btn_frame.pack(side="right")

        def btn(text, cmd):
            tk.Button(btn_frame, text=text,
                      font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat",
                      padx=8, pady=4, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=cmd).pack(side="left", padx=2)

        btn("⟨ Prev", self._prev)
        self.page_label = tk.Label(btn_frame, text="1",
                                    font=("Segoe UI", 9, "bold"),
                                    bg=C["primary_light"], fg=C["primary"],
                                    padx=10, pady=4)
        self.page_label.pack(side="left", padx=2)
        btn("Next ⟩", self._next)
        self._update_info()

    def _update_info(self):
        pages = max(1, -(-self.total // self.per_page))  # ceiling div
        start = (self.current_page - 1) * self.per_page + 1
        end   = min(self.current_page * self.per_page, self.total)
        self.info_var.set(f"Showing {start}–{end} of {self.total}")
        self.page_label.config(text=f"{self.current_page} / {pages}")

    def _prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._update_info()
            if self.on_change:
                self.on_change(self.current_page)

    def _next(self):
        pages = -(-self.total // self.per_page)
        if self.current_page < pages:
            self.current_page += 1
            self._update_info()
            if self.on_change:
                self.on_change(self.current_page)

    def update_total(self, total: int):
        self.total = total
        self.current_page = 1
        self._update_info()


# ── Logo loader ────────────────────────────────────────────────
# Caches PhotoImage references so they aren't garbage-collected.
_logo_cache = {}

def load_logo(max_width=240, max_height=120):
    """
    Return a Tk PhotoImage of the DayBill logo scaled to fit the box,
    or None if the file/Pillow is unavailable. Caller must keep a
    reference (we cache here so it survives).
    """
    key = (max_width, max_height)
    if key in _logo_cache:
        return _logo_cache[key]
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return None
    img = None
    # Prefer Pillow for clean scaling; fall back to Tk subsample.
    try:
        from PIL import Image, ImageTk
        im = Image.open(path)
        im.thumbnail((max_width, max_height), Image.LANCZOS)
        img = ImageTk.PhotoImage(im)
    except Exception:
        try:
            raw = tk.PhotoImage(file=path)
            # integer subsample to fit width
            fw = max(1, raw.width() // max_width)
            fh = max(1, raw.height() // max_height)
            factor = max(fw, fh, 1)
            img = raw.subsample(factor, factor) if factor > 1 else raw
        except Exception:
            img = None
    if img is not None:
        _logo_cache[key] = img
    return img
