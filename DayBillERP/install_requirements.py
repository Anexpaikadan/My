#!/usr/bin/env python3
# ============================================================
#  DayBill ERP - One-File Setup / Installer
#  Run this ONCE on a new PC to install everything the app needs.
#
#  HOW TO RUN (Windows):
#     1. Make sure Python 3.10+ is installed (python.org).
#     2. Double-click this file, OR open a command window here and run:
#            py install_requirements.py
#     3. Wait until it says "ALL DONE".
#     4. Then start the app with:  py main.py
# ============================================================

import os
import sys
import subprocess
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
NO_PAUSE = "--no-pause" in sys.argv          # INSTALL.bat carries on by itself

APP_NAME = "DayBill ERP"
MIN_PY = (3, 10)

# (import_name, pip_package, required?, what it's for)
PACKAGES = [
    # ---- REQUIRED (app won't run without these) ----
    ("pyodbc",            "pyodbc",            True,  "Connect to SQL Server database"),
    ("PIL",               "pillow",            True,  "Logo & image handling"),
    ("openpyxl",          "openpyxl",          True,  "Excel import / export"),
    ("reportlab",         "reportlab",         True,  "PDF invoices, reports & labels"),
    ("qrcode",            "qrcode",            True,  "ZATCA QR codes on invoices"),
    ("barcode",           "python-barcode",    True,  "Barcode generation (Code128, EAN-13)"),

    ("bcrypt",            "bcrypt",            True,  "Secure password hashing for users (required v6.0)"),
    ("cryptography",      "cryptography",      True,  "ZATCA Phase 2 signing"),
    ("lxml",              "lxml",              True,  "ZATCA XML"),
    ("requests",          "requests",          True,  "ZATCA / Wathq / updates over the internet"),
    ("certifi",           "certifi",           True,  "Secure (HTTPS) connection to ZATCA"),

    # ---- OPTIONAL (only if you use these features) ----
    ("win32print",        "pywin32",           False, "Printing & printer list (Windows only)"),
    ("pypdfium2",         "pypdfium2",         False, "Print PDFs directly on the printer (no PDF reader needed)"),
    ("speech_recognition","SpeechRecognition", False, "Voice product search (optional)"),
    ("pyaudio",           "pyaudio",           False, "Microphone for voice search (optional)"),
    ("arabic_reshaper",   "arabic-reshaper",   False, "Better Arabic text shaping in PDFs"),
    ("bidi",              "python-bidi",       False, "Right-to-left Arabic layout in PDFs"),
]

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; OFF = "\033[0m"


def color(txt, c):
    # Colors may not show in every console; that's fine.
    return f"{c}{txt}{OFF}"


def line(ch="-", n=60):
    print(ch * n)


def check_python():
    print(color(f"\n  {APP_NAME} — Setup\n", CYAN))
    line("=")
    v = sys.version_info
    print(f"  Python version: {v.major}.{v.minor}.{v.micro}")
    if (v.major, v.minor) < MIN_PY:
        print(color(f"  ✗ Python {MIN_PY[0]}.{MIN_PY[1]}+ is required. "
                    f"Please install a newer Python from python.org.", RED))
        return False
    print(color("  ✓ Python version OK", GREEN))
    return True


def _pins():
    """requirements.txt → {package name: 'name>=x,<y'} (the versions DayBill
    is tested with — a newer major version must never be installed)."""
    out = {}
    try:
        with open(os.path.join(HERE, "requirements.txt"), encoding="utf-8") as f:
            for raw in f:
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                spec = line.split(";", 1)[0].strip()
                name = spec
                for ch in "<>=!~ ":
                    name = name.split(ch, 1)[0]
                out[name.lower()] = spec
    except Exception:
        pass
    return out


PINS = _pins()


def pip_install(pkg):
    """Install one package (at the tested version) with pip. True on success."""
    spec = PINS.get(pkg.lower(), pkg)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", spec],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return True
    except Exception:
        return False


def pause(msg="  Press Enter to exit..."):
    if not NO_PAUSE:
        input(msg)


def is_installed(import_name):
    try:
        importlib.import_module(import_name)
        return True
    except Exception:
        return False


def ensure_pip():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return True
    except Exception:
        print(color("  pip not found — trying to install it...", YEL))
        try:
            subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            return True
        except Exception:
            print(color("  ✗ Could not set up pip. Reinstall Python with pip enabled.", RED))
            return False


def main():
    if not check_python():
        pause("\n  Press Enter to exit...")
        return
    line("=")
    print("  Checking and installing required libraries...\n")

    if not ensure_pip():
        pause("\n  Press Enter to exit...")
        return

    # Upgrade pip quietly first (helps avoid build errors)
    subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    # Everything at the tested versions in one go; the list below then
    # checks each library and retries one by one if this step failed.
    req = os.path.join(HERE, "requirements.txt")
    if os.path.exists(req):
        print("  Installing requirements.txt (tested versions) ...")
        subprocess.call([sys.executable, "-m", "pip", "install", "-r", req],
                        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        print()

    on_windows = sys.platform.startswith("win")
    failed_required = []
    failed_optional = []
    skipped = []

    for import_name, pip_name, required, purpose in PACKAGES:
        # pywin32 only makes sense on Windows
        if pip_name == "pywin32" and not on_windows:
            skipped.append((pip_name, "not on Windows"))
            continue

        tag = "REQUIRED" if required else "optional"
        print(f"  [{tag:8}] {pip_name:18} — {purpose}")

        if is_installed(import_name):
            print(color("             already installed ✓\n", GREEN))
            continue

        print("             installing...", end="", flush=True)
        ok = pip_install(pip_name)
        if ok and is_installed(import_name):
            print(color("  done ✓\n", GREEN))
        elif ok:
            # installed but import name differs / needs restart
            print(color("  installed (restart may be needed) ✓\n", GREEN))
        else:
            print(color("  FAILED ✗\n", RED))
            (failed_required if required else failed_optional).append(pip_name)

    # ---- Summary ----
    line("=")
    print(color("\n  SUMMARY\n", CYAN))
    if not failed_required:
        print(color("  ✓ All REQUIRED libraries are installed.", GREEN))
    else:
        print(color("  ✗ Some REQUIRED libraries failed:", RED))
        for p in failed_required:
            print(color(f"      - {p}", RED))
        print(color("    Try running this installer again, or install manually:", YEL))
        print(f"      {sys.executable} -m pip install " + " ".join(failed_required))

    if failed_optional:
        print(color("\n  ⚠ Optional libraries that didn't install "
                    "(features still work without them):", YEL))
        for p in failed_optional:
            print(f"      - {p}")
        if "pyaudio" in failed_optional:
            print("        (pyaudio is only needed for voice search; safe to ignore.)")

    if skipped:
        for p, why in skipped:
            print(color(f"\n  • Skipped {p} ({why}).", YEL))

    line("=")
    print("\n  NEXT STEPS:")
    print("   1. Make sure SQL Server is running.")
    print("   2. New shop: DayBill login > Database Settings > Create New Database")
    print("      (or run database\\INSTALL_DayBillERP_AllInOne.sql in SSMS).")
    print("   3. Start the app:   py main.py   (or the DayBill icon on the desktop)")
    if not failed_required:
        print(color("\n  ALL DONE — you're ready to run DayBill ERP.\n", GREEN))
    else:
        print(color("\n  Fix the REQUIRED items above, then run the app.\n", YEL))

    pause()
    if failed_required:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Cancelled.")
    except Exception as e:
        print(color(f"\n  Unexpected error: {e}", RED))
        pause()
        sys.exit(1)
