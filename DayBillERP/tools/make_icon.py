# ============================================================
# DayBill ERP - build assets/app.ico from assets/app_icon.png
# ------------------------------------------------------------
# Windows Explorer, the taskbar and the .exe resource use the SMALL
# sizes (16/24/32/48). Those must be classic 32-bit bitmaps; only the
# 256 size may be PNG. (An .ico with PNG in every size shows a blank /
# default icon on many PCs.)   Run:  py tools\make_icon.py
# ============================================================
import io, os, struct, sys
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "assets", "app_icon.png")
OUT = os.path.join(HERE, "assets", "app.ico")
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def _bmp_entry(img):
    """32-bit BGRA DIB (bottom-up) + 1-bit AND mask, as an ICO image."""
    w, h = img.size
    px = img.convert("RGBA").tobytes("raw", "BGRA")
    rows = [px[y * w * 4:(y + 1) * w * 4] for y in range(h)]
    xor = b"".join(reversed(rows))
    mask_row = ((w + 31) // 32) * 4
    alpha = img.convert("RGBA").split()[3].tobytes()
    mask = bytearray()
    for y in reversed(range(h)):
        row = bytearray(mask_row)
        for x in range(w):
            if alpha[y * w + x] < 128:
                row[x // 8] |= 0x80 >> (x % 8)
        mask += row
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0,
                         len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + bytes(mask)


def build(src=SRC, out=OUT):
    base = Image.open(src).convert("RGBA")
    entries = []
    for s in SIZES:
        im = base.resize((s, s), Image.LANCZOS)
        if s >= 256:
            buf = io.BytesIO(); im.save(buf, "PNG"); data = buf.getvalue()
        else:
            data = _bmp_entry(im)
        entries.append((s, data))
    head = struct.pack("<HHH", 0, 1, len(entries))
    off = 6 + 16 * len(entries)
    dirs, blobs = b"", b""
    for s, data in entries:
        dirs += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), off)
        off += len(data)
        blobs += data
    with open(out, "wb") as f:
        f.write(head + dirs + blobs)
    return out


if __name__ == "__main__":
    print("Wrote", build(*sys.argv[1:3]))
