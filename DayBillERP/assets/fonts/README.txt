ARABIC FONTS (optional)
=======================
Invoices already render Arabic on Windows automatically, using
Tahoma / Arial / Segoe UI (every Windows PC has these).

For nicer Arabic typography you can OPTIONALLY drop a font here:

  assets/fonts/Amiri-Regular.ttf
  assets/fonts/Amiri-Bold.ttf
       (or Cairo-Regular.ttf / Cairo-Bold.ttf
        or NotoNaskhArabic-Regular.ttf / NotoNaskhArabic-Bold.ttf)

The app checks this folder FIRST, so a bundled font wins over the
Windows defaults. Amiri is free (SIL OFL): https://github.com/alif-type/amiri

To fetch Amiri automatically, run:
  python assets/fonts/get_amiri.py
