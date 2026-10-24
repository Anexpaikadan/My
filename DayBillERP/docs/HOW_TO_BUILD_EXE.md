# 🏗️ Building DayBillERP.exe (Windows)

This turns the DayBill ERP Python app into a single `DayBillERP.exe`
you can double-click — no Python needed on the final machine.

> ⚠️ The .exe **must be built on Windows.** It cannot be built on Mac/Linux.
> You only build it once; after that you can copy the .exe to any Windows PC.

---

## Easiest way — one click

1. **Unzip** the DayBill folder first (right-click the .zip ▸ *Extract All…*).
   Put it somewhere you can write, e.g. `C:\DayBill` — not inside
   *Program Files*, not inside the zip.
2. Python **3.10 – 3.14** must be installed (3.12 is best). When installing,
   tick **"Add python.exe to PATH"**. No Python? BUILD_EXE.bat opens the
   download page for you.
3. **Double-click `BUILD_EXE.bat`.** It:
   - finds Python by itself (the `py` launcher or `python`),
   - installs PyInstaller and every library DayBill needs,
   - builds **`dist\DayBillERP.exe`** with the DayBill icon,
   - **checks the new exe** can print: your designer templates (A4 + 80 mm),
     QR, barcodes, Arabic, receipt (`dist\logs\selftest.log`),
   - makes a **"DayBill ERP" icon on the Desktop and in the Start menu**,
   - writes everything it did to **`build_log.txt`**.
4. Wait 1–5 minutes. The `dist` folder opens when it is ready.

If something goes wrong the window says what to do and shows the last
lines of `build_log.txt` (send me a photo of it).

### Common problems

| Message | Fix |
|---|---|
| Python is not installed | Install Python 3.12, tick *Add python.exe to PATH*, run again |
| Libraries could not be installed | Internet needed the first time; run again |
| dist\DayBillERP.exe is open or locked | Close DayBill ERP, run again |
| Build did not make the exe | Antivirus removed it: Windows Security ▸ Virus & threat protection ▸ Exclusions ▸ add the DayBill folder |
| Old / blank icon in Explorer | Windows icon cache — BUILD_EXE.bat refreshes it; if still old, sign out and in |

---

## Manual way (command line)

```bat
cd C:\DayBill
py -m pip install pyinstaller pyinstaller-hooks-contrib -r requirements.txt
py -m PyInstaller --clean --noconfirm DayBillERP.spec
```

Result: `dist\DayBillERP.exe`

---

## Where the exe keeps its settings

`DayBillERP.exe` keeps **its own** settings in a `config` folder **next to
the exe** (`dist\config\db_config.json`, `app_settings.json`,
`license.json`) and error logs in `logs`. So the database settings,
language and product key are remembered after closing. (Before v5.18 the
exe saved them in a temporary folder and forgot them every time.)
If the exe sits in a folder you can't write to, it uses
`%LOCALAPPDATA%\DayBillERP` instead. Your own `config` folder is **not**
copied into the exe.

If the exe doesn't open at all, look in `dist\logs\startup_error.log`.

---

## Before the .exe will run

The .exe is just the program. It still needs the database:

1. **Create the database** — open `database\INSTALL_DayBillERP_AllInOne.sql` in SSMS and run it (F5).
   That ONE file makes the whole clean database (all tables + every update
   already inside — no other .sql file to run). Or, from the DayBill login:
   ⚙ Database Settings ▸ **Create New Database…** runs it for you.
2. **First launch** — double-click `DayBillERP.exe`, click ⚙ Database Settings,
   enter server `localhost\SQLEXPRESS`, database `DayBillERP`,
   Windows Authentication → Test Connection → Save & Connect.
3. **Login:** `admin` — the first time, DayBill asks you to set the admin password.

---

## Optional polish

- **App icon:** the DayBill logo icon is in `assets\app.ico` (window,
  taskbar, the .exe and the Desktop shortcut use it). To use your own logo,
  replace `assets\app_icon.png` (256×256) and run `py tools\make_icon.py`
  before building — it makes an .ico Windows shows correctly at every size.
- **Arabic invoices/payslips:** put an Arabic TTF (e.g. `Amiri-Regular.ttf`)
  in `modules\fonts\` before building so it's bundled in.

---

## Sharing the app

To run on another Windows PC, that PC needs:
- The `DayBillERP.exe`
- SQL Server (Express is free) + the `DayBillERP` database created from the .sql
- ODBC Driver 17/18/19 for SQL Server

The .exe itself bundles Python and all libraries, so Python does **not**
need to be installed on the other PC.
