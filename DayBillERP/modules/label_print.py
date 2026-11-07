# ============================================================
# DayBill ERP - print barcode labels at their TRUE size (v7.9.10)
# ------------------------------------------------------------
# The old way drew the label PDF as a smoothed picture stretched to the
# width of whatever paper the Windows driver was set to: on a driver left
# at 4×6 in (or a different label) the label came out blown up, the
# barcode ran off the sticker and the print spilled onto the next label.
#
# Three ways now (Print Labels ▸ ⚙ Printer setup), none of them scales:
#   driver  Windows driver, true size: the driver is told the label size
#           (one sticker = one page) and the label is drawn 1 : 1 in mm at
#           the printer's own dpi, pure black & white (sharp bar edges)
#   tspl    straight to TSC / XPrinter / Gprinter / most thermal label
#           printers: SIZE + GAP + the label as a 1-bit BITMAP (TSPL)
#   zpl     straight to Zebra-type printers: ^PW / ^LL + ^GFA graphic
# Shift X / Y (mm) nudge the print on the sticker; an alignment label
# (frame + cross) shows where it lands; Calibrate gap makes the printer
# measure the sticker gap (TSPL GAPDETECT / ZPL ~JC).
# ============================================================
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MODES = {"driver": "Windows driver — true size",
         "tspl": "Label printer direct — TSC · XPrinter · Gprinter (TSPL)",
         "zpl": "Label printer direct — Zebra (ZPL)"}
DEFAULTS = {"label_print_mode": "driver", "label_offset_x": 0.0, "label_offset_y": 0.0,
            "label_gap_mm": 2.0, "label_density": 8, "label_speed": 4, "label_dpi": 203}


def settings():
    """The label-printer settings of this PC (with defaults)."""
    from config import settings as cfg
    out = {}
    for k, d in DEFAULTS.items():
        v = cfg.get(k, d)
        try:
            v = type(d)(v) if not isinstance(d, str) else str(v or d)
        except (TypeError, ValueError):
            v = d
        out[k] = v
    if out["label_print_mode"] not in MODES:
        out["label_print_mode"] = "driver"
    return out


def save_settings(values):
    from config import settings as cfg
    for k, v in values.items():
        if k in DEFAULTS:
            cfg.set(k, v)
    try:
        cfg.save_settings()
    except Exception:
        pass


# ── PDF page → exact 1-bit picture ───────────────────────────────────
def raster(pdf_path, dpi=203, offset_mm=(0.0, 0.0)):
    """Every page of the label PDF as a black & white picture at exactly
    `dpi` (no smoothing: bars keep hard edges), shifted by offset_mm."""
    from PIL import Image
    pages = []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            for i in range(len(pdf)):
                img = pdf[i].render(scale=dpi / 72.0, no_smoothtext=True, no_smoothimage=True,
                                    no_smoothpath=True).to_pil()
                pages.append(img)
        finally:
            pdf.close()
    except ImportError:
        d = tempfile.mkdtemp()
        subprocess.run(["pdftoppm", "-r", str(int(dpi)), "-aa", "no", "-aaVector", "no", "-png",
                        pdf_path, os.path.join(d, "p")], check=True)
        for f in sorted(os.listdir(d)):
            pages.append(Image.open(os.path.join(d, f)))
    out = []
    dx = int(round(float(offset_mm[0] or 0) / 25.4 * dpi))
    dy = int(round(float(offset_mm[1] or 0) / 25.4 * dpi))
    for img in pages:
        bw = img.convert("L").point(lambda v: 255 if v >= 128 else 0, "1")   # threshold, no dither
        if dx or dy:
            moved = Image.new("1", bw.size, 255)
            moved.paste(bw, (dx, dy))
            bw = moved
        out.append(bw)
    return out


def alignment_pdf(w_mm, h_mm, path=None):
    """A test label: frame 1 mm inside the edge, centre cross, the size."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    path = path or os.path.join(tempfile.gettempdir(), "daybill_label_alignment.pdf")
    c = canvas.Canvas(path, pagesize=(w_mm * mm, h_mm * mm))
    c.setLineWidth(0.8)
    c.rect(1 * mm, 1 * mm, (w_mm - 2) * mm, (h_mm - 2) * mm)
    cx, cy = w_mm / 2 * mm, h_mm / 2 * mm
    c.line(cx - 4 * mm, cy, cx + 4 * mm, cy)
    c.line(cx, cy - 4 * mm, cx, cy + 4 * mm)
    c.setFont("Helvetica-Bold", max(5, min(9, h_mm / 4)))
    c.drawCentredString(cx, cy + 5 * mm if h_mm > 20 else cy + 2.5 * mm, "%g x %g mm" % (w_mm, h_mm))
    c.setFont("Helvetica", max(5, min(7, h_mm / 5)))
    c.drawString(2 * mm, 2.2 * mm, "frame = 1 mm from the edge")
    c.showPage()
    c.save()
    return path


# ── printer languages ────────────────────────────────────────────────
def tspl_bytes(images, w_mm, h_mm, gap_mm=2.0, copies=1, density=8, speed=4):
    """TSPL job: label size, gap, then each label as a BITMAP (bit 0 = black)."""
    out = bytearray()
    out += ("SIZE %.1f mm,%.1f mm\r\nGAP %.1f mm,0 mm\r\nDIRECTION 1,0\r\nREFERENCE 0,0\r\n"
            "OFFSET 0 mm\r\nSET TEAR ON\r\nDENSITY %d\r\nSPEED %d\r\n"
            % (w_mm, h_mm, gap_mm, int(density), int(speed))).encode("ascii")
    for img in images:
        w, h = img.size
        wb = (w + 7) // 8
        data = img.tobytes()                       # PIL 1-bit: 1 = white, 0 = black
        out += b"CLS\r\n"
        out += ("BITMAP 0,0,%d,%d,0," % (wb, h)).encode("ascii") + data + b"\r\n"
        out += ("PRINT 1,%d\r\n" % max(1, int(copies))).encode("ascii")
    return bytes(out)


def zpl_bytes(images, w_mm, h_mm, dpi=203, copies=1):
    """ZPL job: print width / label length in dots, each label as ^GFA (1 = black)."""
    out = bytearray()
    for img in images:
        w, h = img.size
        wb = (w + 7) // 8
        inv = bytes(b ^ 0xFF for b in img.tobytes())  # ZPL: 1 = black
        hexdata = inv.hex().upper()
        out += ("^XA^PW%d^LL%d^LH0,0^FO0,0^GFA,%d,%d,%d,%s^FS^PQ%d^XZ\r\n"
                % (int(round(w_mm / 25.4 * dpi)), int(round(h_mm / 25.4 * dpi)),
                   len(inv), len(inv), wb, hexdata, max(1, int(copies)))).encode("ascii")
    return bytes(out)


def calibrate_bytes(mode):
    """Make the printer measure the sticker / gap length."""
    return b"GAPDETECT\r\n" if mode == "tspl" else b"~JC\r\n"


# ── Windows driver, true size ────────────────────────────────────────
def device_rect(w_mm, h_mm, dpi_x, dpi_y, phys_x=0, phys_y=0):
    """(x, y, width, height) in printer pixels for a label drawn 1 : 1 from
    the paper's corner (the printable area starts phys_x / phys_y in)."""
    return (-int(phys_x), -int(phys_y),
            int(round(w_mm / 25.4 * dpi_x)), int(round(h_mm / 25.4 * dpi_y)))


def _gdi_true_size(pdf_path, printer, w_mm, h_mm, copies, s):
    import win32print, win32ui, win32gui
    from PIL import ImageWin
    name = printer or win32print.GetDefaultPrinter()
    dm = None
    try:                                      # one sticker = one page
        h = win32print.OpenPrinter(name)
        try:
            dm = win32print.GetPrinter(h, 2)["pDevMode"]
        finally:
            win32print.ClosePrinter(h)
        dm.PaperSize = 256                     # DMPAPER_USER
        dm.PaperWidth = int(round(w_mm * 10))  # 0.1 mm
        dm.PaperLength = int(round(h_mm * 10))
        dm.Orientation = 1
        dm.Fields |= 0x2 | 0x4 | 0x8 | 0x1     # paper size / length / width, orientation
    except Exception:
        dm = None
    hraw = win32gui.CreateDC("WINSPOOL", name, dm)
    dc = win32ui.CreateDCFromHandle(hraw)
    try:
        dpi_x, dpi_y = dc.GetDeviceCaps(88), dc.GetDeviceCaps(90)
        phys_x, phys_y = dc.GetDeviceCaps(112), dc.GetDeviceCaps(113)
        pages = raster(pdf_path, dpi_x, (s["label_offset_x"], s["label_offset_y"]))
        x, y, tw, th = device_rect(w_mm, h_mm, dpi_x, dpi_y, phys_x, phys_y)
        dc.StartDoc("DayBill labels")
        for _ in range(max(1, int(copies or 1))):
            for img in pages:
                dc.StartPage()
                ImageWin.Dib(img.convert("RGB")).draw(dc.GetHandleOutput(), (x, y, x + tw, y + th))
                dc.EndPage()
        dc.EndDoc()
    finally:
        dc.DeleteDC()
    return True


def print_label_pdf(pdf_path, printer=None, copies=1, w_mm=None, h_mm=None):
    """Print a label PDF the label way (never stretched). Returns True when
    handed over; printer_service.last_error says why not."""
    from modules import printer_service as ps
    s = settings()
    if not w_mm or not h_mm:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(pdf_path)
            w_pt, h_pt = pdf[0].get_size()
            pdf.close()
            w_mm, h_mm = w_pt / 72 * 25.4, h_pt / 72 * 25.4
        except Exception:
            w_mm, h_mm = 50.0, 30.0
    mode = s["label_print_mode"]
    try:
        if mode in ("tspl", "zpl"):
            imgs = raster(pdf_path, s["label_dpi"], (s["label_offset_x"], s["label_offset_y"]))
            data = tspl_bytes(imgs, w_mm, h_mm, s["label_gap_mm"], copies, s["label_density"],
                              s["label_speed"]) if mode == "tspl" else \
                zpl_bytes(imgs, w_mm, h_mm, s["label_dpi"], copies)
            return send_raw(data, printer)
        if os.name == "nt":
            return _gdi_true_size(pdf_path, printer, w_mm, h_mm, copies, s)
        cmd = ["lp", "-n", str(max(1, int(copies))), "-o", "media=Custom.%gx%gmm" % (w_mm, h_mm),
               "-o", "print-scaling=none"] + (["-d", printer] if printer else [])
        r = subprocess.run(cmd + [pdf_path], capture_output=True, timeout=30)
        if r.returncode != 0:
            ps.last_error = (r.stderr or b"").decode(errors="replace")[:200]
        return r.returncode == 0
    except Exception as e:
        ps.last_error = str(e)[:200]
        return False


def printer_fn_for(template):
    """For print_menu.send_pdf(printer_fn=…): label rolls print at true size;
    A4 sticker sheets (None) go through the normal A4 printing."""
    t = template or {}
    if not t or t.get("paper_mode") == "a4sheet":     # no design (simple A4 sheet) / sticker sheet
        return None
    w_mm, h_mm = float(t.get("label_width_mm") or 50), float(t.get("label_height_mm") or 25)
    return lambda pth, prn, copies=1: print_label_pdf(pth, prn, copies, w_mm, h_mm)


def send_raw(data, printer=None):
    from modules import printer_service as ps
    if os.name == "nt":
        return ps.print_raw(data, printer)
    try:
        cmd = ["lp", "-o", "raw"] + (["-d", printer] if printer else [])
        r = subprocess.run(cmd, input=data, capture_output=True, timeout=30)
        if r.returncode != 0:
            ps.last_error = (r.stderr or b"").decode(errors="replace")[:200]
        return r.returncode == 0
    except Exception as e:
        ps.last_error = str(e)[:200]
        return False
