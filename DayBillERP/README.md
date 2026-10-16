# 🇸🇦 DayBill ERP  v6.9

Billing, POS, inventory, accounts and HR for Saudi shops.
**ZATCA Phase 1 & 2 · Arabic & English · Microsoft SQL Server · Windows**

---

## 🚀 Install (new PC)

1. Install **SQL Server Express** (free) and **ODBC Driver 18 for SQL Server**
   (https://aka.ms/downloadmsodbcsql).
2. Install **Python 3.12** from python.org — tick *Add python.exe to PATH*.
3. Double-click **`INSTALL.bat`**. It installs the libraries, can create the
   database for you, and puts a DayBill icon on the desktop.
4. Start DayBill (desktop icon, or `py main.py`). Sign in as **admin** — you set
   the password at the first sign-in — then fill **Settings ▸ Company**.

Making the database by hand instead: run `database\INSTALL_DayBillERP_AllInOne.sql`
in SSMS (F5), or DayBill login ▸ ⚙ Database Settings ▸ **Create New Database…**.
It is clean (no sample data) and safe to run again — it never deletes data.

Building one `DayBillERP.exe` + a setup file for shops: `BUILD_EXE.bat`
(see `docs/HOW_TO_BUILD_EXE.md`).

---

## 🗂️ Folders

```
DayBillERP/
├── main.py                     start DayBill
├── dbtool.py                   start the Database Tool (pick FROM / TO, reset a
│                               password, bring another program's data in)
├── INSTALL.bat                 one-click install (libraries, database, shortcut)
├── DayBill_Database_Tool.bat   Database Tool shortcut
├── BUILD_EXE.bat · DayBillERP.spec   build DayBillERP.exe (+ setup file)
├── requirements.txt · install_requirements.py
├── config/      settings, database connection, version (your settings are
│                kept here as *.json — made on first start)
├── ui/          every screen and window
├── modules/     business logic (posting, ZATCA, reports, printing, payroll …)
├── locales/     English / Arabic text
├── assets/      icon, logo, fonts
├── database/
│   ├── INSTALL_DayBillERP_AllInOne.sql   new database — ONE file
│   ├── patches/    updates for older databases (applied automatically)
│   └── tools/      by hand only: reset a password, repair, units reset
├── mobile/      phone / PDT / van web app (served by DayBill)
├── van_relay/   files for your web host (van sales relay)
├── claude_connector/   lets the Claude desktop app read your reports
├── tools/       for developers: installer script, icon, version info
├── docs/        setup guide, build guide, mobile guide, CHANGELOG
└── extras/      not needed to run DayBill (Android app source)
```

---

## 🔐 Users & rights

Sign in as `admin` (password set at first sign-in), then make a user for each
person in **Users & Rights** with a user type (Cashier, Sales, Manager …).
Every screen and every New / Edit / Delete button follows those rights.

## 📒 Ledger → transaction

Accounts ▸ Account Ledger (or a customer / supplier statement): double-click a
line to open its transaction; right-click for Open · Edit · Delete · Voucher ·
New. **🔗 Connectors** shows which window each kind of line opens and lets you
choose what a double-click does.

## 🌐 Language

**🌐 العربية** (top right) switches to Arabic (right-to-left); **🌐 English** back.

## 📊 ZATCA

| Feature             | Phase 1 | Phase 2 |
|---------------------|---------|---------|
| QR code (TLV)       | ✅      | ✅      |
| UUID per invoice    | ✅      | ✅      |
| XML UBL 2.1         | ✅      | ✅      |
| Cryptographic stamp | ❌      | ✅      |
| Real-time reporting | ❌      | ✅      |

## 🔤 Arabic in PDFs

Put an Arabic TTF font (e.g. `Amiri-Regular.ttf`) in `modules/fonts/` or
install one on Windows; `arabic-reshaper` and `python-bidi` are installed by
INSTALL.bat.

## 📞 VAT rates

| Type         | Code | Rate |
|--------------|------|------|
| Standard     | S    | 15%  |
| Zero-rated   | Z    | 0%   |
| Exempt       | E    | 0%   |
| Out of scope | O    | —    |

---

What changed in each version: `docs/CHANGELOG.md`.
