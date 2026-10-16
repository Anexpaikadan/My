# ============================================================
# Saudi Arabia Billing ERP - Main Entry Point
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings, language
from config.database import db
import ui.tk_safety  # noqa: F401  (unique Tk callback names)
from ui.login_window import LoginWindow


def _declare_dpi_awareness():
    """Windows only. MUST run before the first Tk() is created.

    Without this, on any display running above 100% scaling (125%,
    150% — the default on most laptops and many POS touch monitors),
    Windows silently bitmap-scales the whole app. Tkinter then computes
    widget positions in one pixel space while Windows draws them in
    another, so every custom-positioned popup — the product search
    dropdown under a grid cell, barcode/company search results, the
    login financial-year list, print dialogs — lands off from the
    field it belongs to. Declaring DPI-awareness up front makes
    Windows report real physical pixels, so Tk's own coordinate math
    (winfo_rootx/rooty, .geometry(), .bbox()) lines up with what is
    actually drawn. Safe no-op on non-Windows platforms."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            # Per-monitor v2 — best result on modern Windows (10 1703+)
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()        # system DPI
    except Exception:
        pass


def _app_icon(root):
    """DayBill logo as the icon of every window + the Windows taskbar."""
    here = os.path.dirname(os.path.abspath(__file__))
    ico = os.path.join(here, "assets", "app.ico")
    png = os.path.join(here, "assets", "app_icon.png")
    if sys.platform == "win32":
        try:        # own taskbar group → Windows shows OUR icon, not python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "DayBill.ERP.Desktop")
        except Exception:
            pass
        try:
            if os.path.exists(ico):
                root.iconbitmap(default=ico)          # all windows / dialogs
        except Exception:
            pass
    try:
        if os.path.exists(png):
            img = tk.PhotoImage(file=png)
            root.iconphoto(True, img)                  # True = also new windows
            root._daybill_icon = img                   # keep a reference
    except Exception:
        pass


def main():
    _declare_dpi_awareness()

    # Load settings & language
    settings.load_settings()
    lang = settings.get("language", "en")
    language.load_language(lang)

    # Create root window (hidden initially)
    root = tk.Tk()
    root.withdraw()
    _app_icon(root)

    # Text size for the whole app (Settings ▸ System ▸ Text size, default
    # 125 %). The layouts were tuned at 1 pixel per point (100 %); ui/zoom
    # grows fonts AND the pixel sizes that go with them (table rows and
    # columns, dialog windows). Relies on _declare_dpi_awareness() above so
    # popups stay anchored correctly on high-DPI Windows displays.
    from ui import zoom
    zoom.apply(root)

    # Apply ttk theme
    style = ttk.Style(root)
    style.theme_use("clam")

    # Launch login window
    login = LoginWindow(root)
    root.wait_window(login.window)

    # If login succeeded, launch main app
    if login.login_success:
        root.deiconify()
        from ui.main_window import MainWindow
        app = MainWindow(root, current_user=login.current_user)
        root.mainloop()
    else:
        root.destroy()


def _startup_crash(exc):
    """DayBillERP.exe has no console window: a crash at start-up used to
    close it silently ("the exe does nothing"). Log it and say so."""
    import traceback
    txt = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    path = ""
    try:
        from config.paths import log_file
        path = log_file("startup_error.log")
        from datetime import datetime
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n[%s]\n%s" % (datetime.now(), txt))
    except Exception:
        pass
    try:
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("DayBill ERP could not start",
                             "%s\n\n%s" % (str(exc)[:400],
                                             ("Details saved in:\n" + path) if path else ""))
        r.destroy()
    except Exception:
        print(txt)


if __name__ == "__main__":
    if "--dbtool" in sys.argv:            # v6.1: DayBill Database Tool
        try:
            from ui.dbtool_window import main as _dbtool
            _dbtool()
        except Exception as _e:
            _startup_crash(_e)
        sys.exit(0)
    if "--selftest" in sys.argv:          # BUILD_EXE.bat checks the new exe
        try:
            from modules import selftest
            _ok, _txt = selftest.run()
            print(_txt)
        except Exception as _e:
            _ok = False
            print("selftest crashed:", _e)
        sys.exit(0 if _ok else 1)
    try:
        main()
    except SystemExit:
        raise
    except Exception as _e:
        _startup_crash(_e)
