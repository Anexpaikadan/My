# ============================================================
# DayBill ERP - Printer service
# ------------------------------------------------------------
# Printer hardware used by every document print, the Printer
# Management screen and the designers. Windows printing uses
# pywin32; PDFs are drawn straight onto the printer page (pypdfium2)
# so it works WITHOUT a PDF reader and never shows a dialog. When that
# is not available it falls back to the PDF app's print / printto verb.
#
# Settings (config/app_settings.json via config.settings):
#   print_direct    : bool  - True = print on the default printer
#                             without asking; False = ask each time
#   default_printer : str
#   doc_printers    : {"sales_invoice": "EPSON TM-T20", ...}
#   print_copies    : int
#   print_margins_mm: [top, right, bottom, left]
# ============================================================

import os, sys, tempfile, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg

last_error = ""


def list_printers():
    """Installed printer names (Windows via win32print)."""
    try:
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]
    except Exception:
        return []


def default_printer():
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        return cfg.get("default_printer") or None


def set_windows_default(name):
    try:
        import win32print
        win32print.SetDefaultPrinter(name)
        return True
    except Exception:
        return False


def print_direct():
    """Settings ▸ Printing: print straight to the default printer (True)
    or ask which printer each time (False)."""
    v = cfg.get("print_direct", None)
    if v is None:                      # older installs: 'silent_print'
        return True
    return cfg.flag("print_direct", True)


def printer_for(doc_type):
    """Resolve which printer a document type should use."""
    mapping = cfg.get("doc_printers", {}) or {}
    if mapping.get(doc_type):
        return mapping.get(doc_type)
    # Settings ▸ Printing: per-kind default printers
    dt = str(doc_type or "").lower()
    if dt in ("pos_invoice", "pos", "receipt", "thermal"):
        key = "printer_pos"
    elif dt in ("report", "reports", "a4", "statement", "ledger"):
        key = "printer_a4"
    elif dt in ("dotmatrix",):
        key = "printer_dotmatrix"
    elif dt in ("labels",):
        key = "printer_labels"
    else:
        key = "printer_invoice"
    return (str(cfg.get(key, "") or "").strip() or cfg.get("default_printer")
            or default_printer())


def open_file(path):
    """Show a file in its normal app (PDF reader, Notepad) — no printing."""
    try:
        if os.name == "nt":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


# ── PDF → printer ────────────────────────────────────────────
def _gdi_print_pdf(pdf_path, printer_name, copies):
    """Draw each PDF page on the printer with Windows GDI. Needs pywin32 +
    pypdfium2 + pillow. Returns True / False (False = try another way)."""
    import win32print, win32ui
    import pypdfium2 as pdfium
    from PIL import ImageWin
    name = printer_name or win32print.GetDefaultPrinter()
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        for _ in range(max(1, int(copies or 1))):
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(name)
            try:
                pw = hdc.GetDeviceCaps(8)       # HORZRES  printable width px
                ph = hdc.GetDeviceCaps(10)      # VERTRES  printable height px
                dpi = max(96, hdc.GetDeviceCaps(88))   # LOGPIXELSX
                hdc.StartDoc(os.path.basename(pdf_path))
                for i in range(len(pdf)):
                    page = pdf[i]
                    w_pt, h_pt = page.get_size()
                    scale = min(300, dpi) / 72.0
                    img = page.render(scale=scale).to_pil()
                    # fit the page into the printable area, keep proportions;
                    # narrow receipts use the full paper width
                    iw, ih = img.size
                    ratio = min(pw / iw, ph / ih) if ih * pw / iw > ph else pw / iw
                    tw, th = int(iw * ratio), int(ih * ratio)
                    hdc.StartPage()
                    ImageWin.Dib(img).draw(hdc.GetHandleOutput(), (0, 0, tw, th))
                    hdc.EndPage()
                hdc.EndDoc()
            finally:
                hdc.DeleteDC()
        return True
    finally:
        try:
            pdf.close()
        except Exception:
            pass


def print_pdf(pdf_path, printer_name=None, copies=None, silent=None):
    """Send a PDF to a printer. Returns True when it was handed over."""
    global last_error
    last_error = ""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
    try:
        copies = max(1, int(copies or cfg.get("print_copies", 1) or 1))
    except (TypeError, ValueError):
        copies = 1
    if os.name == "nt":
        # 1) straight onto the printer (no PDF reader needed, no dialog)
        try:
            if _gdi_print_pdf(pdf_path, printer_name, copies):
                return True
        except Exception as e:
            last_error = str(e)[:200]
        # 2) the PDF reader's own print verbs
        try:
            import win32api
            for _ in range(copies):
                if printer_name:
                    win32api.ShellExecute(0, "printto", pdf_path,
                                          f'"{printer_name}"', ".", 0)
                else:
                    win32api.ShellExecute(0, "print", pdf_path, None, ".", 0)
            return True
        except Exception as e:
            last_error = str(e)[:200]
        try:
            for _ in range(copies):
                os.startfile(pdf_path, "print")
            return True
        except Exception as e:
            last_error = ("No program can print PDF files on this PC. Install "
                          "pypdfium2 (py -m pip install pypdfium2) or a PDF "
                          "reader. (%s)" % str(e)[:120])
            return False
    # Linux / macOS: CUPS
    try:
        cmd = ["lp", "-n", str(copies)] + (["-d", printer_name] if printer_name else [])
        r = subprocess.run(cmd + [pdf_path], capture_output=True, timeout=30)
        if r.returncode == 0:
            return True
        last_error = (r.stderr or b"").decode(errors="replace")[:200]
    except Exception as e:
        last_error = str(e)[:200]
    return open_file(pdf_path)


# ── plain text → dot-matrix printer ──────────────────────────
ESC_INIT, ESC_DRAFT = b"\x1b@", b"\x1bx\x00"
CONDENSED_ON, CONDENSED_OFF, FORM_FEED = b"\x1b\x0f", b"\x12", b"\x0c"


def text_bytes(text, width=80):
    data = ESC_INIT + ESC_DRAFT
    if int(width or 80) >= 132:
        data += CONDENSED_ON
    data += str(text).replace("\r\n", "\n").replace("\n", "\r\n").encode(
        "cp437", errors="replace")
    if int(width or 80) >= 132:
        data += CONDENSED_OFF
    return data + FORM_FEED


def print_raw(data, printer_name=None):
    """Raw bytes (ESC/P, ESC/POS) to a printer (silent, no dialog)."""
    global last_error
    printer_name = printer_name or default_printer()
    try:
        import win32print
        h = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(h, 1, ("DayBill", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, data)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
        return True
    except Exception as e:
        last_error = str(e)[:200]
        return False


def print_text(text, printer_name=None, width=80, copies=1, name="document"):
    """Dot-matrix print of fixed-width text. Raw to the printer first;
    otherwise Notepad prints the .txt on that printer. Returns True/False."""
    global last_error
    try:
        copies = max(1, int(copies or 1))
    except (TypeError, ValueError):
        copies = 1
    data = text_bytes(text, width)
    if os.name == "nt":
        if all(print_raw(data, printer_name) for _ in range(copies)):
            return True
        path = save_text(text, name)
        try:
            for _ in range(copies):
                if printer_name:
                    subprocess.Popen(["notepad.exe", "/pt", path, printer_name])
                else:
                    subprocess.Popen(["notepad.exe", "/p", path])
            return True
        except Exception as e:
            last_error = str(e)[:200]
            return False
    try:
        path = os.path.join(tempfile.gettempdir(), f"{name}.prn")
        with open(path, "wb") as fh:
            fh.write(data)
        cmd = ["lp", "-o", "raw", "-n", str(copies)] + (["-d", printer_name] if printer_name else [])
        r = subprocess.run(cmd + [path], capture_output=True, timeout=30)
        if r.returncode == 0:
            return True
        last_error = (r.stderr or b"").decode(errors="replace")[:200]
    except Exception as e:
        last_error = str(e)[:200]
    return False


def save_text(text, name="document"):
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(name))
    path = os.path.join(tempfile.gettempdir(), f"{safe}.txt")
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(str(text))
    return path


def test_print(printer_name=None):
    """Print a one-page test sheet to confirm the printer works."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    path = os.path.join(tempfile.gettempdir(), "daybill_testprint.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, 760, "DayBill ERP — Printer Test")
    c.setFont("Helvetica", 11)
    c.drawString(40, 735, f"Printer: {printer_name or default_printer()}")
    c.drawString(40, 718, "If you can read this, printing works correctly.")
    c.showPage()
    c.save()
    return print_pdf(path, printer_name, copies=1)
