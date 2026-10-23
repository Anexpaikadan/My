# DayBill ERP  v7.1.0

Billing, POS, inventory, accounts and HR for shops in 🇸🇦 Saudi Arabia, 🇦🇪 the UAE and 🇮🇳 India.
**VAT / GST by country · ZATCA Phase 1 & 2 · Arabic & English · Microsoft SQL Server · Windows**

## 💸 v7.1 — multi-line vouchers (cash and bank in one window)

- **Receipt · Payment · Contra · Journal** in one window (Accounts ▸
  Vouchers ▸ New, ⭐ Cash / Bank Receipt, Cash / Bank Payment, Contra, F6 / F7).
  Add as many lines as you need; **each line picks its own cash or bank
  account**, so one window takes cash from one customer and a cheque from
  another.
- Saved as **separate CR + BR (CP + BP)** vouchers, each with its own number,
  or tick off *Separate* for one voucher. The next numbers show before you save.
- Type a name, code or account: customers, suppliers and the chart of accounts
  drop down as a tree. The **party balance** shows while you type, before →
  after this voucher.
- Bank lines take **cheque no. / date**; payment lines take **input VAT**
  (+VAT fills the standard rate). Live Cash / Bank / Total and amount in words.
- **Journal:** Debit / Credit lines with customers and suppliers too, the open
  difference is suggested on the next line, **⚖ Balance** (Ctrl+B) puts it on
  the selected line.
- **Templates** (monthly rent, salaries …) and **↺ Copy last**. Keys: Enter
  next field / add line, double-click change a line, Delete remove, Ctrl+D
  duplicate, Alt+↑/↓ move, Ctrl+S save. Edit from the Vouchers list opens the
  same window with the voucher's lines.

## 🌍 v7.0 — countries and business modules

- **New Company** (Login ▸ ⚙ Database Settings ▸ 🆕 Create New Company…): pick the
  country, state / emirate, tax number, currency symbol and the business modules;
  DayBill makes the database and sets it up for that country.
- **Saudi Arabia**: VAT 15 %, ZATCA QR / Phase 2, VAT return — as before.
- **UAE**: VAT 5 %, TRN, AED, VAT 201 return with sales by emirate and imports
  under reverse charge.
- **India**: GST 5 / 18 / 40 % (+ nil, exempt, zero rated), GSTIN check, HSN / SAC,
  place of supply → CGST + SGST or IGST on their own accounts, ₹ with lakh /
  crore, GSTR-3B (with Rule 88A set-off), GSTR-1 (B2B, B2CL, B2CS, CDNR, HSN,
  documents), April–March year, round-off to the rupee.
- **Business modules**: Restaurant (tables, dine-in / takeaway / delivery, KOT,
  kitchen screen, recipes that use up ingredients), Textiles (size / colour
  variants, Ctrl+G sizes grid, metre / yard), Production (bill of materials,
  production entries, finished-goods cost), Supermarket, Retail.
- **Accounts**: chart of accounts as a tree of groups and ledgers; every
  account picker drops down as a searchable tree.

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
Actions that change many records at once (Clear Stock, year close / reopen,
restore a backup, make the payroll again, disconnect ZATCA …) need their
right **and** a typed word; deleting a confirmed bill asks you to type its
number.

## 🏷 Barcodes

Every product has its own **5-digit system barcode** (10001, 10002 …) made by
DayBill, and can have a **manual barcode** — the one printed on the packet,
typed or scanned in the Product window. Both scan in every barcode box (Sales,
Purchase, Returns, POS, Price check) and the product search finds them.
**Print Barcode Labels** shows both and prints the one you choose (system,
manual, or manual else system); Box / Carton units have their own codes.

## ☰ Columns, fonts, product facts

Right-click any column heading (or ☰ at its top-right) in a report, a list or
a Sales / Purchase grid: show / hide and move columns, **➕ More columns** —
Profit, Profit %, Product cost, PLU No, Stock, Stock value, Unit 1 / 2 / 3,
Multi barcode, Arabic name, Category, Brand … — and **Font** (size, design,
bold) for that table or every table. Excel / PDF / print follow the columns on
screen. The Product window shows a live **Product summary** (price with /
without VAT, cost, profit, profit %, stock, PLU, units, barcodes) on every page.

## ⌨ Keys, favourites, after Save

- **F1** anywhere (Help ▸ ⌨ Keyboard Shortcuts) lists every key. F2 Sales,
  F3 POS, F4 Purchases, F6 Cash Receipt, F7 Cash Payment, F8 Products,
  F9 Ledger, F11 Stock, F12 Reports, Ctrl+N new in the open screen. In every
  transaction window: Ctrl+S save, Ctrl+N new, Ctrl+Delete delete, Ctrl+J
  voucher lines, Esc close.
- **⭐ Favourites** at the top of the side menu: Cash Payment, Cash Receipt,
  Ledger, Stock, Sales, POS, Add Product, Sales Return, Purchase, Purchase
  Return. Right-click any menu item to add it; right-click a favourite to
  remove or move it.
- **After Save the window stays open** for the next entry (the saved number
  shows in it). Settings ▸ System ▸ *After saving an entry*: start a new
  entry (default) · show the saved entry · close the window.
- Every journal carries a **voucher type**: SI sales, POS, SR sales return,
  PI purchase, PR purchase return, CR / BR cash / bank receipt, CP / BP cash /
  bank payment, JV journal, CE consumable entry … (Report Center ▸ Voucher
  Types).
- **🍞 Consumable Entry** (Inventory): stock the shop uses itself — staff /
  room food, bakery or kitchen production, shop supplies, samples, damaged.
  Stock goes out at cost and the expense is booked (CE voucher).

## 📒 Ledger → transaction

Accounts ▸ Account Ledger (or a customer / supplier statement): double-click a
line to open its transaction; right-click for Open · Edit · Delete · Voucher ·
New. **🔗 Connectors** shows which window each kind of line opens and lets you
choose what a double-click does.

## ⭐ Loyalty points

Settings ▸ Customer ▸ **⭐ Loyalty points**: customers earn points on every
bill (default 1 point per 10 SAR) and spend them as a discount — Sales
Invoice ▸ **⭐ Pts** box, POS ▸ **⭐ Points (F10)**. Customers ▸ ⭐ Points shows
the history; Report Center ▸ ⭐ Loyalty Points lists every customer.

## 🌐 Online forms (Tally or Jotform)

Customers and suppliers register — and rate their visit — on their phone.
Settings ▸ Online forms: choose **Tally** or **Jotform**, paste the API key and
the three form links (Customer registration, Supplier registration, How was
your visit?). Answers wait in Customers ▸ 🌐 Online forms until you review them.

The shop's three Tally forms are live (paste these links in Settings):

| Form | Link |
|------|------|
| Customer registration · تسجيل عميل | https://tally.so/r/4aXjl5 |
| Supplier registration · تسجيل مورد | https://tally.so/r/OQ10Ma |
| How was your visit? · كيف كانت زيارتك؟ | https://tally.so/r/4aXjVr |

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
