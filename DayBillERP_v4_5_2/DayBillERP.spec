# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# DayBill ERP - PyInstaller build spec
# Build with:  BUILD_EXE.bat   (or:  py -m PyInstaller --clean --noconfirm DayBillERP.spec)
# Produces:    dist\DayBillERP.exe  (one file, DayBill icon)
#
# Every path below is taken from THIS file's folder (SPECPATH), so the
# build works from any "current folder" (Run as administrator, other
# drive, shortcut…).
# ============================================================
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

HERE = os.path.abspath(SPECPATH)


def P(*parts):
    return os.path.join(HERE, *parts)


def opt(src, dest):
    """Bundle a file / folder only when it exists (a missing optional
    folder must never stop the build)."""
    return [(P(src), dest)] if os.path.exists(P(src)) else []


datas = []
datas += opt('locales', 'locales')                     # translations
datas += opt('database', 'database')                   # auto-applied DB updates
datas += opt('assets', 'assets')                       # icon, logo, fonts
datas += opt('modules/fonts', 'modules/fonts')         # Arabic fonts (if added)
datas += opt('mobile', 'mobile')                       # DayBill Mobile app (phones / PDT / van)
datas += opt('van_relay', 'van_relay')                 # Hostinger van relay (upload folder)
# NOTE: the config folder is NOT bundled — your db_config.json /
# app_settings.json / license.json stay on YOUR PC. DayBillERP.exe keeps
# its own settings in a "config" folder next to the exe.
for pkg in ('barcode', 'reportlab', 'qrcode', 'certifi'):   # fonts / data / ZATCA HTTPS certs
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

# all DayBill code (some screens are imported only when opened)
hidden = []
for pkg in ('ui', 'modules', 'config'):
    try:
        hidden += collect_submodules(pkg)
    except Exception:
        pass
# ReportLab loads its barcode types BY NAME at run time (code93, code39,
# usps, …). Without these the exe failed: "No module named
# 'reportlab.graphics.barcode.code93'" on Preview / Print with a QR.
for pkg in ('reportlab', 'qrcode', 'barcode', 'arabic_reshaper', 'bidi'):
    try:
        hidden += collect_submodules(pkg)
    except Exception:
        pass
hidden += [
    'pyodbc',
    'reportlab', 'reportlab.graphics.barcode', 'reportlab.graphics.barcode.code128',
    'reportlab.graphics.barcode.qr', 'reportlab.graphics.barcode.eanbc',
    'qrcode', 'qrcode.image.pil',
    'PIL', 'PIL._tkinter_finder', 'PIL.ImageTk',
    'arabic_reshaper', 'bidi', 'bidi.algorithm',
    'openpyxl', 'cryptography', 'lxml', 'lxml.etree', 'certifi', 'bcrypt', 'requests',
    'barcode', 'barcode.writer',
    'win32print', 'win32ui', 'win32api', 'win32con', 'pywintypes', 'pypdfium2',
]

block_cipher = None

a = Analysis(
    [P('main.py')],
    pathex=[HERE],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['claude_connector', 'tools', 'pytest', 'IPython', 'matplotlib',
              'numpy', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

ICON = P('assets', 'app.ico')
VERSION = P('tools', 'version_info.txt')

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DayBillERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # UPX breaks the icon / trips antivirus on some PCs
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICON] if os.path.exists(ICON) else None,
    version=VERSION if os.path.exists(VERSION) else None,
)
