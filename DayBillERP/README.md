# DayBill ERP  v7.9.1

Billing, POS, inventory, accounts and HR for shops in 🇸🇦 Saudi Arabia, 🇦🇪 the UAE and 🇮🇳 India.
**VAT / GST by country · ZATCA Phase 1 & 2 · Arabic & English · Microsoft SQL Server · Windows**

## 🔧 v7.9.1 — update restart fixed

- After **Updates ▸ Install a new version**, DayBillERP.exe could stop with
  *"Failed to load Python DLL … _MEI… python3xx.dll"* instead of starting
  again. The new version now starts cleanly once the old one has closed.

## 🧾 v7.9 — new transaction header, payment area, grid design, designer options

- **Transaction header:** Sales, Sales Return, Purchase and Purchase Return
  show the bill in titled blocks (Bill · Customer · Contact · Details) with
  a balance card on the right: the party's balance, last bill and this
  counter's last bill.
- **Payment area in every transaction:** pick any cash or bank account
  (Main cash, Petty cash, each bank …), more than one if needed. Pay part
  of the bill and the rest stays on the party's account —
  *Total 200 · Paid 100 · On account 100*. The Cash Customer / Cash
  Supplier must pay in full.
- **▦ Grid design** (right-click any table heading): font, row height,
  colours, header text, width, alignment, show / hide and read only — for
  every table, Receipts / Payments and reports included.
- **Invoice Designer:** a document list with codes (SI · Sales Invoice,
  PI, SR, PR …); **Prints as** ★ Default / Design 2 / Design 3 (Print ▾ ▸
  Print design 2 / 3); page settings (lines per page, minimum lines, row
  gap, custom paper size, pre-printed letterhead, ask the printer every
  time, graphics or dot-matrix); sections (invoice header on page 1, page
  header / footer on every page, invoice footer on the last page); field
  formats (amount, qty, date, UPPER, in words), hide when empty / zero,
  italic, underline, box, colour, max length, lock position.

## 👤 v7.8 — party balance, customer typed on the bill, read-only columns

- **Balance and last bill** of the customer / supplier you pick (Sales,
  POS, Purchase, vouchers), and the last bill of this counter.
- **A customer who is not in the list:** type Name, VAT / GST No., Mobile
  and Address on the bill — they are printed on the invoice.
- **🔒 Read-only columns:** right-click a heading (Bar Code, Product, Qty,
  Rate) ▸ Read only — e.g. the Rate always comes from the product.

## 🍽 v7.7 — arrow keys, normal-size windows, POS picture menu, account groups

- **← → in the item grid.** ← at the start of a cell goes back (Rate → Qty →
  Product → Bar Code), → goes forward, ↑ ↓ move Qty / Rate between rows. In
  the other boxes of a transaction window ← goes back to the box before.
- **Normal-size windows.** Sales, purchase, return and order windows open as
  a big normal window, not full screen (Settings ▸ System to change). POS
  stays full screen.
- **POS picture menu** for restaurants / cafés and tailor shops: big product
  pictures by category, the bill beside them (Settings ▸ POS ▸ Screen layout).
- **Default account groups:** Cash-in-Hand, Bank Accounts, Sundry Debtors,
  Sundry Creditors, Duties & Taxes, Direct / Indirect Income and Expenses …
  (Chart of Accounts ▸ ⊕ Add default groups).
- **Product ▸ 🖨 Print at:** tick Warehouse 1 / Warehouse 2 / Kitchen 1 … and
  each item of a saved bill prints at its own station.
- **POS** opens full size inside a normal window with a **—** minimize
  button. The **Bar Code** column of every item grid and the POS bill shows
  the short 5-digit system barcode.

## ✨ v7.6 — UI/UX pass

- **Readable everywhere.** Buttons with white text on a light colour are
  darkened until they read (4.5:1); keyboard focus shows a ring in your
  brand colour; no tiny (under 9 pt) text in the new windows; Print Stations
  columns fit the screen.
- **Phone / PDT app.** Dark mode (follows the phone), every button at least
  44 px, the PDT keypad reaches every tile and list row (arrows + Enter),
  Esc / back closes pop-ups, a busy bar and a spinning Send while DayBill
  answers, pinch-zoom allowed, screen-reader names for icon buttons.

## 🧾 v7.5 — returns & orders, print stations, loyalty card, PDT receiving

- **Returns from a bill.** Sales / Purchase Return ▸ **📂 Load bill**: type the
  bill number or pick it from a searchable list (number or party), then pick
  the items — ✓ all or some, change quantities, 🔍 find an item. A return can
  never take back more than was sold minus earlier returns (checked on Save).
- **Orders into invoices.** New **Sales Order** (Sales ▸ Sales Orders).
  Sales Invoice ▸ **📥 Load Order** (quotation / sales order) and Purchase
  Invoice ▸ **📥 Load purchase order**: pick the order and its lines, change
  quantities or edit, then save. Partial delivery is counted on the order
  (◐ partial, the rest stays to load later; *Make invoice* from the order loads
  only what is left).
- **🔍 line** box on every transaction grid: jumps to the line with that code /
  name (Enter = next match).
- **🍳 Print Stations** (System ▸ Print Stations): ＋ Kitchen, ＋ Warehouse,
  ＋ Tailor, ＋ Other — Kitchen 1, Kitchen 2, Warehouse 1, Tailor Ahmed … each
  with its own printer, template (80 / 58 mm roll, A5, A4), copies and what it
  prints for (Sales Invoice, POS bill, Sales Order). Categories (or single
  products) go to a station; a station with no categories takes the rest. The
  Sales Invoice has **Send to** (e.g. the tailor) — every item goes there.
  Test print, print a sale again, recent prints. Restaurant TABLE orders keep
  their kitchen tickets (Restaurant ▸ Setup ▸ Kitchen stations: printer,
  58 / 80 mm, copies, categories).
- **💳 Customer loyalty QR card** (Customers ▸ Loyalty QR card): send it on
  WhatsApp or print it; scanning it at the POS or Sales Invoice picks the
  customer (price list + points). Optional: WhatsApp the points after each bill
  (Cloud API).
- **📦 PDT ▸ Receive PO**: pick an open purchase order, scan what came
  (✔ ok · ⚠ short · ✖ missing · ➕ more · ★ not on the order), save as a
  **draft purchase** or a **confirmed purchase invoice** (stock in), close the
  order if items will not come, WhatsApp the supplier what is missing.
- **Mobile ▸ Listen on**: all networks, only the shop Wi-Fi address, or this PC.

## 📱 v7.4 — QR sign-in for every user and employee (sent on WhatsApp)

- **Users ▸ 📱 QR sign-in…** makes a personal QR for the selected user:
  **💬 Send on WhatsApp** (the link; with the WhatsApp Cloud API the staff
  card PDF goes too), **🖨 Staff card (PDF)** to print, **📋 Copy link**,
  **⛔ Turn off**. Choose how long it is valid (never, 7 / 30 / 90 days, 1 year)
  and where it works (phone app, desktop sign-in or both).
- **The person opens it:** tapping the WhatsApp link (or scanning the QR with
  the phone camera) on the shop Wi-Fi opens DayBill Mobile **signed in as
  them**, with their modules. At the desktop login they scan the QR card with
  the barcode scanner — signed in, no password typing. The phone app's sign-in
  screen also has **📷 Sign in with my QR**.
- **Each employee:** HR ▸ Employee ▸ *Sign-in* — pick the employee's DayBill
  user or **➕ Make a user for this employee** (user name = employee code), then
  **📱 QR sign-in…**. The employee's mobile number is used for WhatsApp.
- **📱 QR for all users…** makes everyone a new QR and saves all staff cards in
  one folder (and sends them with the WhatsApp Cloud API).
- Safe: only a hash of the key is kept; a new QR stops the old one at once;
  expired / turned-off QRs and switched-off users are refused; 5 wrong codes
  lock QR sign-in for 5 minutes; every QR sign-in is in the login history.
  The Users list shows each user's QR state.

## 💲 v7.3 — PDT Price Change

- **💲 Price Change on the PDT.** Scan an item: the new-price box opens at
  once. Type the shelf price (with VAT) — old → new, cost and margin show
  while you type (red when below cost). Pick a reason, and the number on the
  line is how many new shelf labels to print.
- Save changes the price of that unit (a carton alone, or the piece and the
  product), in the shop's price mode (with or without VAT). Below cost is
  refused unless **Allow below cost** is ticked. Every change goes into the
  audit log (old → new, reason, device), and a price someone changed in the
  meantime is noted.
- New labels print on the label printer (or wait in Mobile ▸ Inbox ▸ 🖨 Print
  PDF); the phone can open the PDF.
- Mobile ▸ Wi-Fi: *Price Change from the PDT waits for approval in the Inbox*
  lets the owner approve new prices first. Give the module in Mobile ▸ Users.

## 📱 v7.2 — PDT: purchase orders, barcode labels, offer posters · Database Tool

- **📝 Purchase Order on the PDT.** Pick the supplier, scan items (cost shown
  and editable), or press **⚠ Low stock** to add everything at or under its
  reorder level (items bought from that supplier first). Save makes an open
  Purchase Order in DayBill (no stock, no journal) and offers **💬 WhatsApp**
  to send it to the supplier. **📋 Orders** lists the latest orders.
- **🔖 Barcode Labels on the PDT.** Scan the shelf, set how many labels, pick
  the label design: DayBill prints them on the PC's label printer (or keeps the
  PDF in Mobile ▸ Inbox ▸ 🖨 Print PDF). Products without a barcode get one.
  The phone can open the PDF too.
- **🎨 Offer Poster on the PDT.** Scan the products, choose % off, new price,
  amount off, buy X get Y or price only, headline (English / Arabic), dates,
  size (A4, A5, A4 landscape, square post) and design: DayBill draws a
  printable poster PDF with old and new prices, can **start the offer in POS**
  at the same time, and gives the ChatGPT / Gemini prompt as well. Offers ▸
  Poster prompt has the same **🖨 Printable poster (PDF)** button.
- Users get the new modules in Mobile ▸ Users (PO / Labels / Poster).
- **Database Tool ▸ Convert** follows the TO company's country: VAT 15 %
  (Saudi), 5 % (UAE) or the GST slabs (India 5 / 12 / 18 / 28 / 3 / nil), prices
  before tax get each product's own rate, its currency, VAT No. / TRN / GSTIN
  checks, GST state from the GSTIN or a State / Emirate column, HSN codes.
  New: **📗 Open Excel / CSV export** as FROM (each sheet / file a table) and
  **🧾 Verify** — DayBill compared with the old data (counts, stock value,
  opening balances), also shown right after converting.

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
