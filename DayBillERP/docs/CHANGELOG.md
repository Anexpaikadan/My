# DayBill ERP — version history

Newest first. The short guide is in the main README.md.

## 🔧 v7.9.2 — update fixes

- The 7.9.1 zip held a test update_daybill.bat. During an update the new
  files are copied over the running helper, so Windows went on with the
  test's last line ("cannot find C:\Python314\pythonw.exe"). Removed it,
  and an update can no longer bring the helper, update_staging,
  update_backup_*, logs, backups or __pycache__ (app_update._skip; robocopy
  /XF update_daybill.bat /XD update_staging update_backup_*).
- On a PC running DayBillERP.exe, Updates refuses a source .zip without a
  DayBillERP.exe inside (the exe never reads the .py files next to it, so
  nothing would change) and says to build / pick the new DayBillERP.exe.

## 🔧 v7.9.1 — update restart fixed

- Updates ▸ Install a new version: the helper (update_daybill.bat) inherited
  the one-file exe's own environment variables (_PYI_APPLICATION_HOME_DIR,
  _PYI_ARCHIVE_FILE, _PYI_PARENT_PROCESS_LEVEL, TCL / TK paths), so the new
  DayBillERP.exe looked for python3xx.dll in the old, already deleted
  _MEI… folder ("Failed to load Python DLL"). The helper now gets a clean
  environment (app_update.clean_env, PYINSTALLER_RESET_ENVIRONMENT=1),
  clears them again before it starts DayBill, waits for both processes of
  the old exe (launcher + Python) and retries a locked file for a short
  time instead of 30 s per try.

## 🧾 v7.9.0 — transaction header, payment area, grid design, Invoice Designer options

- Sales, Sales Return, Purchase and Purchase Return: the header is rebuilt
  as titled blocks (ui/doc_header) with a balance card — the party's
  ledger balance in big figures (red = owes, green = in credit), their last
  bill and this counter's last bill; the Cash Customer shows "No account".
- Payment area (ui/pay_panel) on Purchase, Sales Return and Purchase
  Return: up to four rows of [cash / bank account][amount], every cash and
  bank account of the chart in the list, "Pay all" / "All on account", and
  the line "Total · Paid · On account / Change". The Sales window's Cash /
  Card boxes each got their account. Split rows are kept in
  payment_tenders and posted per account; the unpaid part goes to the
  party ledger (posting.post_purchase others, post_sales_return /
  post_purchase_return paid). A walk-in party must pay in full.
- ▦ Grid design (ui/table_columns): per table font, size, bold, row
  height, row / alternate / header colours, grid-line colour, header text,
  width, alignment, show / hide, order and read only; "font for every
  table"; Receipts / Payments lists and reports have it too.
- Invoice Designer (modules/design_options, patch zzz_v790_designer):
  document list with codes; ★ Default / Design 2 / Design 3 per document
  (report_templates.design_slot) and Print ▾ ▸ Print design 2 / 3; page
  settings in report_templates.page_json — lines per page, minimum lines
  (blank rows), row gap, Custom paper W × H, pre-printed paper, ask the
  printer every time, graphics or text (dot-matrix) printing; sections —
  a field can print on every page (page header / footer) or only on page 1
  / the last page, with guides on the canvas; field settings — format
  (amount, no-decimal amount, qty, date, long date, UPPER / lower / Title,
  amount in words), text after the value, max length, hide when empty /
  zero, italic, underline, box, colour, lock position.

## 👤 v7.8.0 — party balance & last bill, customer typed on the bill, read-only columns

- Sales window (L.Bill line under the grid), POS (customer strip), Purchase
  (under the supplier) and vouchers: the party's ledger balance (Dr / Cr),
  their last bill (number, date, amount) and the last bill of this counter;
  the Cash Customer shows the counter's last bill (modules/party_info).
- A customer who is not in Customers: Name, VAT / TRN / GSTIN, Mobile and
  Address typed in the Sales window are kept on the bill (snapshot columns,
  new sales_invoices.customer_phone — patch zzz_v780_party_snapshot) and
  printed in "Bill To". A customer from the list fills the boxes (they can
  be changed for one bill). POS: Name + tax no. boxes; Purchase: supplier
  name + tax no. The tax number is checked against the country's format
  before saving.
- Columns tool: Bar Code, Product, Qty and Rate of the item grid can be made
  🔒 read only (right-click the heading, or Columns… ▸ Read only) — kept per
  window type on this PC; Enter / arrows skip a read-only cell. POS ▤
  Columns: Qty / Rate read only (pad, + / −, line window).

## 🍽 v7.7.0 — arrow keys, normal-size windows, POS picture menu, account groups, Print at

- Item grid of Sales / Purchase / Returns / Quotations / Orders: ← at the start
  of a cell goes back one cell (Rate → Qty → Product → Bar Code → the row
  above), → at the end of Bar Code / Qty / Rate goes forward; ↑ ↓ move
  Qty / Rate between rows; a number typed is kept. In every other box of a
  transaction window ← at the start goes back to the box before
  (ui/invoice_grid, ui/ui_polish).
- Transaction windows open as a big normal window (94 % of the desktop,
  centred); Settings ▸ System ▸ "Open … full size" brings the old way back.
  The POS keeps its own full screen.
- POS picture menu (Settings ▸ POS ▸ Screen layout: Auto / Classic / Picture):
  automatic for restaurant / café and textiles / tailor companies — category
  chips, big picture tiles (initials on a category colour when there is no
  picture), pages, the bill and totals beside them.
- Chart of Accounts: 29 default groups (patch zzz_v770_account_groups);
  DayBill's own ledgers filed under them, ledgers you moved stay put, codes
  unchanged; ⊕ Add default groups runs it again.
- Product form ▸ 🖨 Print at: tick the warehouses / kitchens a product prints
  at (more than one allowed); nothing ticked = its category's station or the
  station that takes the rest.
- POS opens full size INSIDE a normal window (title bar stays) and has a
  — minimize button on its bar; it has its own taskbar button, F3 brings
  it back.
- Item grids (sales, purchase, returns, orders) and the POS bill show the
  5-digit system barcode in the Bar Code column — short, the same as on the
  label, and searchable with 🔍 line. The scanned barcode is still saved.
  Settings ▸ Sales ▸ "Bar Code column … shows" switches back.

## ✨ v7.6.0 — UI/UX pass (desktop + phone / PDT app)

- Desktop: any button with white text on a light colour is darkened until it
  reads at 4.5:1 (the bright green Save; themes whose accent is white get the
  brand colour); keyboard focus ring in the brand colour (ui/ui_polish).
- No text under 9 pt in the voucher window, connector bar, QR sign-in and
  return pickers; Print Stations columns fit (narrow columns fixed, text
  columns share the rest), empty-state hint, readable document names.
- QR sign-in / loyalty card notes turn red on a failure, green on success;
  QR ⛔ Turn off shows in the danger colour.
- Phone / PDT app: all text 4.5:1 or better (new colour tokens), dark mode
  (follows the phone), every tap target 44 px or more, larger check boxes,
  bottom bar stays on the bottom edge, pinch-zoom allowed.
- PDT keypad: tiles are buttons, list rows / unit chips / cost can be reached
  with the arrow keys and pressed with Enter; Enter presses the focused button
  when nothing was scanned; Esc / back key closes pop-up sheets and the
  camera, focus goes back where it was.
- Screen readers: icon-only buttons are named (Back, Less, More, Delete,
  Edit, Scan with camera), boxes with only a grey example get a name, labels
  are tied to their boxes, the toast is a live region, lang / dir follow
  Arabic.
- Feedback: thin busy bar while DayBill answers, Send / Sign in spin and
  cannot be pressed twice; reduced-motion respected.

## 🧾 v7.5.0 — returns & orders, print stations, loyalty card, PDT receiving

- Returns: pick the bill (search), pick items / all, quantities limited to
  sold − returned (modules/doc_links, ui/doc_pick).
- Sales Order document; Load Order into Sales / Purchase Invoice; partial
  delivery counted (delivered_qty); re-saving an order keeps it.
- 🔍 find-a-line box on the item grid.
- Print stations (kitchens, warehouses, tailors) with printer, template, copies,
  category / product routing, Send to on the invoice, reprint, log.
- Customer loyalty QR card (POS / invoice scan, WhatsApp, card PDF, points
  message after a sale).
- PDT Receive PO → draft or confirmed purchase invoice, PO partial / received.
- Mobile server Listen-on setting.

## 📱 v7.4.0 — QR sign-in for users and employees

- Personal QR sign-in per user (modules/qr_login, table user_qr_keys): phone app
  (link / camera / PDT scan) and desktop login (scanner), validity, phone /
  desktop choice, turn off, login history, lock after wrong codes.
- Sent on WhatsApp (link, or staff card PDF with the Cloud API); printable
  staff card; QR for all users.
- HR employees: linked DayBill user (employees.user_id), make a user for an
  employee, QR from the employee form.

## 💲 v7.3.0 — PDT Price Change

- PDT module **Price Change**: scan, type the new shelf price (with VAT), live
  margin, reason, new labels printed; per unit; prices with or without VAT;
  below-cost guard; audit log; "changed meanwhile" note; optional owner
  approval in the Mobile Inbox.

## 📱 v7.2.0 — PDT purchase orders, labels and posters · smarter Convert

- **PDT ▸ 📝 Purchase Order:** supplier, scanned items with cost, ⚠ Low stock
  fill, saved as an open Purchase Order; WhatsApp text for the supplier; my
  orders list.
- **PDT ▸ 🔖 Barcode Labels:** label design, copies per item; printed on the
  PC's label printer or kept for Mobile ▸ Inbox ▸ 🖨 Print PDF; barcodes made
  for products without one; the PDF opens on the phone.
- **PDT ▸ 🎨 Offer Poster:** % off / new price / amount off / buy X get Y /
  price only, dates, 4 sizes, 5 designs; printable poster PDF (modules/poster_pdf)
  with old and new prices; optional offer started in POS; AI prompt too.
- **Offers ▸ 🖨 Printable poster (PDF)** on the desktop.
- **Mobile Center:** new module columns, Inbox ▸ 🖨 Print PDF, Purchase Orders
  open from the Inbox, settings for label / poster auto printing.
- **Database Tool ▸ Convert:** country rules (VAT / GST rates, currency, tax
  number checks, GST state, HSN), Excel / CSV exports as a source, Verify after
  converting.
- Fix (v7.1 window): the Cash Customer / Cash Supplier booked straight to the
  cash account no longer hides Cash from the journal and voucher lists.
- Fix: a label line with 0 copies prints nothing (it printed one).

## 💸 v7.1.0 — multi-line Cash / Bank vouchers and Journal

- **One voucher window, many lines:** Receipt, Payment, Contra (cash ↔ bank)
  and Journal. Every receipt / payment line has its own cash or bank account,
  so cash and bank are mixed in one window.
- **Separate CR + BR / CP + BP** vouchers on save (each numbered in its own
  series) or one voucher; the numbers it will take show before saving.
- Customers, suppliers and ledgers in one type-ahead tree; party balance before
  → after the voucher; cheque no. / date on bank lines; input VAT on payment
  lines (Indian GST splits into CGST / SGST input); Cash / Bank / Total and
  amount in words.
- **Journal:** party lines, live difference, suggested balancing amount,
  ⚖ Balance (Ctrl+B), line narration.
- **Templates** kept in the company database and **Copy last voucher**.
- Editing a CR / BR / CP / BP / CT / JV opens it in the same window; changing a
  bank line to cash turns a BR into a CR with a CR number.
- New ⭐ favourite / menu items: Bank Payment, Bank Receipt, Contra.

## 🌍 v7.0.0 — countries, business modules, account groups

- **Countries.** Each company is Saudi Arabia, the UAE or India (kept in its own
  database, so every PC behaves the same). Currency symbol, VAT / GST, tax
  number (VAT No. / TRN / GSTIN, checked as typed), regions / emirates / GST
  states, financial year, number grouping and amount in words follow it.
- **New Company wizard** on the login's Database Settings: company → country →
  business → create. It runs the installer, then sets the tax categories, tax
  accounts, financial year and options for the country.
- **India GST.** CGST + SGST inside the state (UTGST in Union Territories), IGST
  to other states and abroad, by place of supply (on the Sales Invoice, else the
  customer's state). Output / Input CGST, SGST, IGST accounts. HSN / SAC on
  products. Bills show the place of supply, HSN and each tax head; Bill of
  Supply when nothing is taxed. GSTR-3B and GSTR-1 (B2B, B2CL, B2CS, CDNR, HSN,
  documents issued) in the Reports Center.
- **UAE VAT.** 5 %, TRN, AED, VAT 201 (boxes 1a–14, sales by emirate of the
  branch, imports under reverse charge, expenses).
- **Saudi Arabia** works as before; the ZATCA screens and the VAT return show
  only for Saudi companies.
- **Business modules** (Settings ▸ Company ▸ Country & business):
  Restaurant — tables & orders, KOT to kitchen stations, kitchen screen,
  pre-bill, service charge, recipes that take ingredients out when a dish is
  sold, restaurant reports. Textiles — size / colour variants with their own
  barcodes, Ctrl+G sizes grid in Sales, Purchase and POS, Metre / Yard,
  stock by size & colour, textile reports. Production — bill of materials /
  recipes editor with cost roll-up, production entries (materials out at
  cost, finished goods in at cost), production reports.
- **Chart of accounts as a tree.** Every ledger sits under a group; New Group /
  New Ledger under the selected group; the next free code is filled in and the
  type comes from the group; accounts drop down as a tree in the Journal,
  Ledger and reports.
- **Type-to-search everywhere in reports.** Product, customer / supplier,
  account and category boxes drop the matches down as you type.
- Fix: a 0 % product (nil / zero rated) was taxed at 15 % on the invoice.

## 🏷 v6.9.5 — 5-digit system barcode, manual barcode, labels

- **System barcode for every product.** Each product has its own 5-digit
  number made by DayBill (10001, 10002 … up to 99999; Settings ▸ Barcode ▸
  First System Barcode moves the start). It is never typed or changed and
  never repeats any barcode or product code. The barcode on the packet
  (typed or scanned) is the product's **Barcode (manual)** — a separate box.
- **Both scan everywhere.** The system barcode and the manual barcode find
  the product in every barcode box — Sales, Purchase, Sales / Purchase
  Return, Quotation, POS, Price check, stock screens, labels — and in the
  product search (Products list, the Product window's search bar, the
  product drop-down of every grid). The system barcode rings up one piece;
  a Box / Carton has its own code.
- **Print Barcode Labels**: the list shows a **Manual barcode** and a
  **System barcode** column (▶ marks the one that prints) and **Print**
  chooses system barcode (default), manual barcode, or manual else system
  (also Settings ▸ Barcode ▸ Labels print). Rows without that barcode are
  left out and named. The label designer has new **System Barcode No.** and
  **Manual Barcode No.** fields, so one label can show both numbers. Checked
  to the PDF and the label printer.
- **Product window**: Barcode (manual) + System barcode on the Basic page,
  "System barcode" in the Product summary, "System Barcode" in ☰ ▸ More
  columns of every product list and report. New unit barcodes are 5 digits
  (the 6-digit default moves to 5 once; a length you chose stays).
- **Existing products** get their system barcode in the update
  `database/patches/zzz_v695_patch.sql` (in product order, skipping numbers
  already used as a barcode or product code); every old barcode still scans,
  so labels already printed keep working.
- **Fixed**: changing a saved product's Sales Price left the old price on its
  base unit, which sales and labels use. The base unit now follows the
  product's Sales Price and Purchase Price.

## ☰ v6.9.4 — columns tool with profit, PLU, units and barcodes; fonts; new Product window

- **More columns in every report, list and transaction grid.** Right-click a
  column heading (or ☰): **➕ More columns** offers Profit, Profit %, Product
  cost, Last purchase cost, Sale price, PLU No, Stock, Stock value, Reorder
  level, Unit 1 / 2 / 3 (name × size = price), Barcode, Multi barcode (every
  barcode of the product and its units), Arabic name, Category, Brand, VAT %
  and Location. They start hidden; tick the ones you want. In the Report
  Center they are on every product report (item-wise sales and purchases,
  item details, stock, stock movement, low / dead stock, stock by branch,
  expiry, stock transactions) with totals; on the Products, Stock and Low
  stock lists; and in the Sales, Purchase, Return and Quotation grids
  (Profit %, PLU, Units 1-3, Multi barcode, Arabic name, Category, Stock
  value). Excel, PDF and print take exactly the columns on screen, extra
  columns included. Cost, profit and stock value show only for users with
  the purchase or reports right (a cashier never sees them).
- **Profit the right way.** Profit = amount without VAT − cost of the base
  units (2 boxes of 12 = 24 × cost); on purchases it is what the goods sell
  for at today's price without VAT − what they cost. Profit % = profit ÷ sale.
  Before, the grid took the price with VAT and the cost of one piece per box.
- **Font size and font design per table.** ☰ ▸ Font: size (8 – 18, A+ / A−),
  design (Segoe UI, Tahoma, Arial, Calibri, Verdana, Cambria, Consolas,
  Courier New, Times New Roman), bold rows; "Use this font for every table";
  also in Columns… . Bold total / heading rows follow the new size.
- **New Product window** — designed in Figma ("DayBill ERP — Product window
  v6.9.4"): a slim title strip with the code ("Next code F004") and the
  Active switch; sales price, unit and VAT also on the Basic page (the same
  boxes as Price & VAT); the Basic page fits without cut-off boxes; a
  **Product summary** on the right of every page follows what you type —
  price with / without VAT, cost, profit and profit % (red "Loss — below
  cost"), stock, PLU, units 1-3 and every barcode. The margin on Price & VAT
  updates by itself and uses the price without VAT. Switches follow their
  value everywhere (Active on the title strip = Active on Stock).

## 💾 v6.9.3 — stay open after Save, shortcut keys, favourites, consumable entry, voucher types, rights

- **Entry windows stay open after Save.** Sales Invoice, Purchase, Sales /
  Purchase Return, Quotation / Purchase Order, Receipt / Payment, Cash /
  Bank vouchers, Expense, Journal, Consumable Entry, Product, Customer,
  Supplier and Stock Adjustment no longer close: the same window starts the
  next entry at the same place and size, and shows "✔ Saved <number>".
  Editing a saved entry stays on that entry. Settings ▸ System ▸ *After
  saving an entry*: start a new entry (default) · show the saved entry ·
  close the window (the old way). Save & Print and Hold already stayed open.
- **Shortcut keys everywhere, all listed in Help.** F1 (Help ▸ ⌨ Keyboard
  Shortcuts) opens one searchable list. Main window: F2 Sales, F3 POS,
  F4 Purchases, F5 refresh, F6 new Cash Receipt, F7 new Cash Payment,
  F8 Products, F9 Ledger, F11 Stock, F12 Reports, Ctrl+N new in the open
  screen, Ctrl+L / I / E / R / P / J, Ctrl+Shift+N product, Ctrl+Shift+C
  consumable, Ctrl+Shift+J journal voucher, Ctrl+Shift+Z day close, Ctrl+W
  close screen, Ctrl+Tab next screen. Every transaction window: Ctrl+S save,
  Ctrl+N new, Ctrl+E edit, Ctrl+Delete delete, Ctrl+J voucher lines, Esc
  close. A window's own keys always win.
- **⭐ Favourites** at the top of the side menu, per user: Cash Payment, Cash
  Receipt, Ledger, Stock, Sales, POS, Add Product, Sales Return, Purchase,
  Purchase Return. Right-click any menu item to add it; right-click a
  favourite to remove it, move it up / down or reset the list. A favourite
  the user has no right to is not shown.
- **🍞 Consumable Entry** (Inventory ▸ Consumable Entry, Ctrl+Shift+C): stock
  the shop uses itself — staff / room food, a production unit (bakery,
  kitchen), shop supplies, samples, damaged / expired. Stock goes out at
  average cost; the journal debits the purpose's expense (new accounts 5460
  Staff Food & Welfare, 5470 Production Materials Used, 5480 Shop Supplies
  Used, 5490 Samples & Tasting; damaged → 5160) and credits Inventory.
  Draft, edit, delete, ledger double-click and its own user right
  (copied from Stock Adjustment for existing user types).
- **Voucher types on every journal**, Tally style: SI sales invoice, POS,
  SR sales return, DN debit note, COS cost of sales, PI purchase, PR purchase
  return, CR / BR cash / bank receipt, CP / BP cash / bank payment, EX
  expense, CT contra, JV journal, OB opening, ADJ stock adjustment, CE
  consumable, PY payroll, SAL salary, GOSI, EOS, LN loan, DC day close, SH
  shift. Cash or bank is decided by the account the money went through. New
  journals are numbered per type (CR-000015). Shown in the ledger, the
  voucher list (filter by type), the journal list, Day Book and Journal
  Register; new report Voucher Type Summary. Old journals get their type by
  the update.
- **User rights checked on every screen and button**, and one-click mass
  changes are gone: Clear Stock (stock-adjustment approve right + type
  CLEAR), year close / reopen (type the year), restore a backup and the DB
  Tool (full-access user + typed name), make the payroll again / delete a
  payroll month, connect ZATCA production / disconnect ZATCA — each needs
  its right and a typed word, and is written to the Audit Log. Settings,
  bulk rate change and posting missing cost of sales check their right
  first. Deleting a
  CONFIRMED bill, purchase, return or consumable entry asks you to type its
  number (a draft is one Yes / No). Users cannot give themselves or others
  more rights than they have. After 5 wrong passwords the sign-in waits a
  minute.
- **Pop-up windows**: Esc closes every dialog (a cell editor or open list
  first); ✕ / Esc / Close ask "close without saving?" only when something
  is not saved; a modal dialog stays above its window and gives the focus
  back when it closes; the POS, calculator, price check and the same bill
  open once (the second time brings the open one to the front); Enter = OK
  in small dialogs, numpad Enter too.
- New update `database/patches/zzz_v693_patch.sql` (voucher types,
  consumable tables and accounts, rights).

## ⭐ v6.9.2 — loyalty points, VAT the ZATCA way

- **Loyalty points** (Settings ▸ Customer ▸ ⭐ Loyalty points; off until you
  switch it on). A named customer earns 1 point per *N* SAR on every
  confirmed bill (default 1 point per 10 SAR); 1 point is worth a set amount
  when spent (default 0.10 SAR, at least 50 points at a time). Spend them in
  the Sales Invoice window (⭐ Pts box next to Bill Disc — the balance shows
  beside it) or in the POS (⭐ Points button / F10). Points are a discount
  spread over the lines **before VAT**, so taxable, VAT, the ZATCA e-invoice
  and the books stay right. A sales return takes its points back; editing,
  cancelling or deleting a bill never counts its points twice. The cash /
  walk-in customer collects nothing. Customers ▸ ⭐ Points shows every
  movement and gives / takes points by hand (users with the right to edit
  customers); Report Center ▸ Sales ▸ ⭐ Loyalty Points lists earned, spent
  and balances. New update `database/patches/zzz_v692_patch.sql`.
- **VAT the ZATCA way on every bill**: each line's taxable amount in
  halalas, then VAT worked out once per VAT rate on the bill total (the same
  rule the ZATCA XML and the Phase 2 QR use), half-up rounding everywhere.
  Sales Invoice, POS, van sales, Sales / Purchase Return, Purchase,
  Quotation / PO, mobile goods-in and debit notes now all agree with the
  e-invoice; the screen shows exactly what Save stores (also with a bill
  discount). Before, a van sale could print 44.71 VAT where the e-invoice
  said 44.73.
- **Part returns of discounted lines**: returning 1 of 3 items from a line
  with a discount (for example its share of a bill discount or points) now
  gives back one third of that discount — it kept the whole discount and
  refunded too little.
- **Online forms live**: the shop's Tally forms are published (links in
  README ▸ Online forms).
- **Mobile / van — checked on a real server, hardened**: a document with an
  unknown product, a zero / negative / huge quantity or price, a date in a
  closed financial year, a van total more than 1.00 from its lines, or a
  credit bill without a customer is refused as a whole (it waits in the
  Inbox with the reason) — before, it could be saved half (no journal, lines
  dropped, VAT broken). A small van rounding difference is spread before
  VAT. Van credit bills follow the customer's credit limit. A bill whose
  journal cannot be posted is not kept. One bad relay document no longer
  stops every later van sync. Bad requests get a clear 400. Phone sign-in:
  5 wrong passwords lock it for 5 minutes (logged in Login history), a
  password change or switching mobile access off signs the phone out, and a
  document id cannot be reused by another user; a document sent again after
  a failure is tried again. Van sales no longer count as cash in the office
  till's Day Close. The phone app works VAT out exactly like DayBill, so the
  printed van bill matches the books.
- **Payroll** (real-server test of every HR screen): a loan is not taken
  from months before its date; months in a closed financial year cannot be
  made, changed, reopened or deleted, and a payroll whose journal fails is
  not saved silently; paying GOSI approves a draft month first (a re-make
  could lose or double it); an unpaid-leave day also marked absent is
  deducted once; the end-of-service window shows the real day rate of leave
  pay; a second final settlement is refused.
- **ZATCA Phase 1 + 2** (670+ checks, signing / sending run end to end
  against a local test Fatoora server; every hash also checked with the
  ZATCA SDK method): **Protect keys** failed on every SQL Server (a locked
  secret is longer than its column) — fixed by this update; a bill that
  cannot be signed while connected now shows as *fix* with the reason
  instead of silently dropping out of Phase 2; the default zero-rated reason
  is **VATEX-SA-35** medicines (SA-36 is *qualifying metals* — a shop that
  had chosen the old "medicines" SA-36 label is moved to SA-35 once);
  simplified credit notes not signed yet print the Phase 1 QR; bills are
  held as *fix* (no counter used) when the shop details became wrong after
  connecting.
- **Shifts**: closing a shift that was already closed (two windows / PCs)
  says so instead of reporting a close that changed nothing. Rejecting a
  mobile document needs the same right as approving it.

## ↩ v6.9.1 — returns on account settle their bill

- **Returns on account come off the bill**: a sales / purchase return made
  from a bill and put on the customer's / supplier's account (Payment Type
  *credit*) now reduces what is still open on that bill. The bill shows
  Partial / Paid correctly, the Receipt / Payment window asks only for what is
  still owed, and the dashboard / connector "unpaid" totals agree with the
  ledger. Editing or deleting the return gives the bill its balance back.
  Returns saved before this update are linked once, automatically
  (`database/patches/zzz_v691_patch.sql`), never more than the bill still had
  open.
- **Payment Type picked for you**: *Load* in a return window sets *credit*
  when the original bill is still open, otherwise money back the way the bill
  was paid. You can still change it.
- **Checked end to end on a real SQL Server 2022**: purchase → sale with bill
  discount → sales / purchase return → quotation → invoice → return on account
  → receipt → supplier payment → re-save → delete; trial balance, stock value
  = Inventory account, all 57 reports.

## 🧹 v6.9.0 — clean final product, ledger ↔ transactions, Database Tool FROM / TO

- **Ledger → transaction**: double-click any line in Account Ledger or a
  customer / supplier statement to open the document that made it (sales,
  POS, returns, purchase, receipt, payment, expense, journal). Right-click:
  Open · Edit · Delete · Voucher · New ▸. The ledger refreshes after a save.
- **Connector bar on every transaction window**: ➕ New · ✏ Edit · 💾 Save ·
  🗑 Delete · 📄 Voucher · ✖ Close — each follows the user's rights for that
  transaction type (Users & Rights). Ledger ▸ 🔗 Connectors shows every
  connector, your rights, and what a double-click opens (edit / view / voucher).
- **Database Tool**: FROM and TO boxes at the top of every page (they did
  not work before); double-click a database for a menu; ⇄ swap; databases the
  list could not inspect are checked live. Copy one DayBill company into
  another (built-in DayBill map). An *is_active* column is never taken as
  "Inactive" any more (it made every converted product inactive).
- **Simple windows**: one slim title line on every form and dialog.
- **Bigger item area in every item window** (Sales, Purchase, Sales /
  Purchase Return, Quotation, Purchase Order): the sales header is two rows
  (was five), the totals two rows (was seven), one-line buttons with the status
  in the same line, no title line above the grid. At 1366 × 768 the sales
  window shows about 11 item rows instead of 4. The grid's total row and hint
  line can no longer be cut off.
- **Clean folders**: `docs/` (guides), `database/patches/` (automatic updates),
  `database/tools/` (repair scripts by hand), `extras/` (Android app source).
  Removed an unused module. Wrong menu items fixed (Customer / Supplier
  Ledger, Credit Note, Closing Balance).
- **One-click install**: INSTALL.bat installs the exact library versions from
  requirements.txt (certifi added), can create the database and makes a
  desktop shortcut.
- **Database installer fixed** (tested on SQL Server 2022): a new database got
  no company row, no ZATCA counter column and no Opening Balance Equity
  setting because some patches ran before the table they change existed;
  re-running it with sqlcmd failed (QUOTED_IDENTIFIER). New
  `zzz_v690_patch.sql` repairs databases made by the older installer.
- **Online forms from Jotform too**: Settings ▸ Online forms ▸ *Forms from*
  Tally or Jotform (API key, EU account, the three form links). Answers are
  read by question title exactly as for Tally; the feedback form's hidden
  boxes are `bill` and `branch`. Ready-made Jotform forms: Customer
  registration, Supplier registration, How was your visit?. The Tally and
  Jotform API keys are now kept locked to the PC like the other keys.
- **Sales / purchase windows**: editing a saved invoice without a due date put
  the word "None" in the date box and saving it failed; saved lines showed
  stock 0 in Stock Details (now today's stock); purchase discount "−0.00".
- **Bill discount is saved (spread before VAT)**: the sales invoice's Bill
  Disc and Round boxes changed only the total on the screen — the saved
  invoice, journal, print and ZATCA kept the old total. Now the amount is
  spread over the lines in proportion to their value, before VAT: each line's
  taxable amount and VAT are worked out again, so screen, invoice, journal,
  QR and ZATCA all show the same total (e.g. 342.90 − 2.90 = 340.00 →
  taxable 295.65 + VAT 44.35). A reopened invoice carries the discount in its
  lines. POS bills with automatic round-off are spread the same way.
- **Several companies on one server (important fix)**: the automatic
  database updates ran the "USE DayBillERP" line at the top of each patch,
  which switched the whole DayBill session to the database called DayBillERP.
  A company with any other database name had its updates — and that
  session's work — go to DayBillERP instead. Updates now always stay on the
  company's own database; databases that missed updates get them on the next
  start.
- **Bugs fixed**: the salesman list on the sales invoice was always empty;
  supplier aging ignored purchase returns made from a bill; sales / purchase
  windows logged a database error for a warehouses table that does not exist.

## 📊 Accounts, Stock & Reports (v5.7)

**One rule for every document** (sales invoice, POS bill, purchase, sales
return, purchase return):

| Status     | Stock          | Accounts (journal)                       |
|------------|----------------|------------------------------------------|
| Draft      | no change      | nothing posted                           |
| Confirmed  | moves (base units, Box = 12 pcs) | posted + cost of sales |
| Cancelled / Deleted | reversed | removed                             |

Editing a saved document re-syncs it (old stock + journal reversed first,
so nothing is ever doubled). Sales post **Cost of Goods Sold** at average
cost; purchase returns go back out of **Inventory**; overpaid cash (change)
and round-off are handled; stock adjustments / counts post to
**5160 Stock Adjustment**. If something can't post, the user sees why.

**Reports Center** (sidebar ▸ Reports Center, menu ▸ Reports, F5 = Run):
VAT Return (with returns + expense VAT), VAT Detail, Trial Balance, Profit &
Loss, Balance Sheet, Cash Book, Bank Book, General Ledger, Day Book, Journal
Register, Customer / Supplier Balances, Expenses, Receipts & Payments ·
Sales Register, Item-wise Sales & Profit, Category / Customer-wise Sales,
Daily Sales, Bill-wise Profit, POS Bills, POS Summary, Sales Returns ·
Purchase Register, Item / Supplier-wise Purchases, Purchase Returns ·
Stock, Stock Valuation, Stock Movement, Item Ledger, Low Stock, Dead Stock.
Every report: date range + quick ranges, filters, totals, Excel, PDF, Print.

After updating an old database, open **Profit & Loss ▸ Post missing cost of
sales** once so older sales get their cost entries.

## 🌐 v6.8.0 — Tally-style entry boxes and online forms

**Entry boxes (every add / edit window):**
- A grey example sits inside an empty box (`05X XXX XXXX`, `name@example.com`, `3XXXXXXXXXXXXX3`).
- Each box has one clear border, which turns blue while you type in it.
- Must-fill boxes have a red `*`.
- A wrong box gets a short red note right under it, which goes away as soon as you fix it. The note shows when you leave the box (mobile, email, VAT, CR, postal code, building number, IBAN, numbers, days). An empty must-fill box is flagged on **Save**.
- **Save** opens the page of the first wrong box and puts the cursor in it.
- **Enter** moves to the next box.
- Turn it off in Settings ▸ System ▸ *Tally-style entry boxes*.

**Online forms (Tally, free plan is enough):**
1. In Tally, make the forms. DayBill reads the answers by question title, in English or English · Arabic:
   - *Customer registration*: Customer type, Name (English), Name (Arabic), Mobile, Email, VAT number, CR number, Building number, Street, District, City, Postal code.
   - *Supplier registration*: Company name, Contact person, Mobile, Email, VAT number, CR number, City, Full address, IBAN, Payment terms.
   - *How was your visit?*: Your rating, What was good?, Comment, Mobile, plus hidden fields `bill` and `branch`.
2. Tally ▸ Settings ▸ API keys ▸ **Create API key**.
3. DayBill ▸ Settings ▸ **Online forms**: paste the key and the three form links. The key stays only in this PC's `app_settings.json`.
4. Customers (or Suppliers) ▸ **🌐 Online forms** ▸ *Check for new answers* (F5), or turn on the automatic hourly check.
5. Choose an answer and press **✚ Review and add**. The normal Customer / Supplier window opens filled in; check it and press Save. If the mobile or VAT number is already in DayBill, you are asked first, and the answer is linked to the existing record instead of making a second one.
6. Feedback tab:
   - Stars, comment and bill number for each answer.
   - The 30-day average.
   - 1–2 star answers in red, with a WhatsApp reply button.
7. Settings ▸ Online forms ▸ *Rate your visit QR* prints a small QR under "Thank you" on POS receipts. It opens the feedback form with the bill number filled in.
8. **🔗 Share form** gives you the link and a QR to print, or sends the link on WhatsApp.

Database: `database/zz_v680_patch.sql` (table `online_form_entries`), applied automatically.

## 🪟 v6.7.0 — minimum headers, clear window edges and shadows

Designed in Figma: **DayBill ERP — UI 6.7 (compact headers, elevation)** — tokens, elevation
styles, compact field / button / title-strip components, before / after of the Purchase window.

- **Purchase and Return windows**: every header field on ONE row — about 250 px above the
  item grid becomes about 90 px, so many more item lines fit. The "Find" line under the
  number is a 🔍 button next to ▲▼ now (click it to show the find box).
- **Sales invoice and Quotation**: tighter header (less padding, lower combo boxes).
- **Every window's title strip** is slimmer (40–48 → 30 px).
- **Clear edges**: page windows inside DayBill, dialogs and pop-up lists / calendars /
  messages get a 1 px border you can see (#9EA5AF in the DayBill theme, follows every theme);
  page windows get a soft shadow; on Windows 11 dialogs keep the system shadow with the
  stronger edge and frameless pop-ups get a drop shadow.
- Settings ▸ System ▸ "Compact window headers + clear window edges and shadows" — on by
  default; off brings back the old look.

## 👔 v6.6.0 — HR & Payroll by the Saudi Labour Law (2025)

**Pay** — overtime hour = hourly actual wage + 50 % of the hourly basic (art. 107), from
attendance (hours above the day, every hour on a day off). **Ramadan**: Muslim staff work
6 hours a day (art. 98) — hours above 6 are overtime (Ramadan dates built in, Settings ▸ HR
can move them; untick "Ramadan hours" on the employee if it does not apply). Sick leave
paid 30 days full, 60 days ¾, 30 days unpaid in a year (art. 117). Absent / unpaid days
off the salary.

**Leave** — annual leave earned from the join date (21 days a year, 30 after 5 years) and
carried on; the 2025 law days: marriage 5, a father 3 (within 7 days), bereavement 5 / 3
for a brother or sister, maternity 12 weeks, Hajj once after 2 years.

**Payroll months** — ⚙ Generate (again, safely) → ✏ change a line → **① Approve → ② Pay
salaries → ③ Pay GOSI** (the next step is the blue button), ↩ Reopen. One **📤 Print /
export** menu: print, Excel, payslip PDF, payslips on WhatsApp, WPS / Mudad bank file.
Loans are paid out and taken back in the books.

**Final settlement** — end-of-service award (art. 84; resignation shares art. 85), unused
leave (art. 111), loans taken back, **notice not given** (60 days by the shop / 30 by the
employee, arts. 75–76: paid or taken off), **art. 77 compensation** when the shop ends it
without a valid reason (rest of a fixed contract, or 15 days a year; at least 2 months'
wage). **Unpaid leave over 20 days does not count as service** (art. 116). A clear
breakdown on screen and a PDF to sign.

**Employees** — documents with alerts (Iqama, passport, insurance, contract), **probation**
(90 days, up to 180 — 2025) with an alert before it ends, **resignation** dates (can be
withdrawn for 7 days; accepted by law after 30 days without an answer, or up to 60 if the
shop delays it), IBAN and Iqama checked while typing.

## 🩺 v6.5.0 — ZATCA readiness · evening report in Arabic + PDF template · WhatsApp message count

**🩺 ZATCA readiness** (ZATCA screen)
- **Do you have to connect?** ZATCA's 25th wave (Governor decision, July 2026): taxable
  sales over **187,500 SAR** in any year 2022–2025 → Phase 2 from **1 February 2027**.
  DayBill adds up your taxable sales per year (credit notes taken off) and says if you
  are in, and how many days are left. A start-up message reminds you until you connect.
- **Data check** before connecting (and 🩺 Check after): shop details, B2B customers with a
  VAT number but no full national address (their tax invoices would be REJECTED), wrong
  customer VAT numbers, products without a VAT category, certificate end date, bills
  waiting > 24 hours, rejected bills.
- **How to fix**: click a rejected / waiting bill — ZATCA's message (e.g. BR-KSA-37) in
  simple words with what to do.

**📲 Evening report**
- In **English or Arabic** (Settings ▸ WhatsApp ▸ Evening report language).
- **Cloud API**: WhatsApp only delivers a typed message when the owner wrote to the shop
  number in the last 24 hours. Approve a template in Meta (header: document; body
  {{1}} date, {{2}} sales, {{3}} summary) and type its name in Settings ▸ WhatsApp ▸
  Evening report template — the report then goes every day as a **PDF**.
- From Day Close / Settings a failed Cloud API send opens WhatsApp with the report.

**📊 WhatsApp Cloud API count** — since 1 October 2026 Meta charges every Cloud API
message (also replies inside 24 hours). Settings ▸ WhatsApp shows the messages of this
month and last month, by type, and the cost at your price per message. WhatsApp app
mode stays free. The "missing items" list to a supplier now opens WhatsApp (free).

**Also**: Claude Haiku 5.5 for names / spelling (an older saved model moves over by
itself) · Arabic menu names for Stock Count and Price Updates.

## 📦 v6.4.0 — supplier orders · phone stock count · price updates · cashier watch · evening report · cloud backup

**📤 One-tap supplier orders** (Smart Insights ▸ Reorder)
- **Make & send POs**: the reorder plan becomes one SAVED Purchase Order per supplier
  (in the unit you buy in, last price, VAT) and each PDF goes to its supplier on
  WhatsApp (Cloud API: sent by itself; WhatsApp app: the chat opens).
  **Make POs (check first)** saves them as drafts to look at first.
- **📦 Receive (scan)** (Purchase Orders ▸ right-click / button): scan every item that
  came (a Box barcode = one box) → ordered / received / difference: ✔ OK, ⚠ short,
  ✖ missing, ➕ more, ★ not on the order. **All came as ordered** in one click,
  double-click to fix a number. **Tell supplier what is missing** (WhatsApp).
  **Make Purchase Invoice** with what really came; the order is marked received.

**🧮 Stock Count (phone)** (Inventory ▸ Stock Count)
- **Today's list**: a few items every day by ABC — A (best sellers) every 7 days,
  B every 30, C every 90 (Settings ▸ Inventory), never-counted first.
- Phones (DayBill Mobile ▸ Stock Count ▸ 📋 Today's list) or the PC type the count.
- **✅ To approve**: the owner sees system / counted / difference / value (⚠ big
  differences) and approves — untick a line = count it again. Turn approval off
  in Settings ▸ Inventory to apply counts at once (old way).
- **📜 History**: every count, accuracy %, loss / gain in SAR.

**📈 Price Updates** (Inventory ▸ Price Updates) — the last purchase cost more than
the one before and the price was not changed since: the new price that keeps
your old margin (rounded up to 0.25, Settings ▸ Purchase), Box / Carton prices by
the same ratio. Tick → ✔ Apply; shelf labels wait in **Price Change Labels**. After
a purchase is confirmed a note says "Cost went up on N item(s)".

**👀 Cashier Watch** (Reports ▸ Sales & POS) — per cashier: bills, sales, discounts,
returns, items removed before payment, bills cleared, documents deleted, cash
short / over — with a warning when one cashier is far above the others or the
cash is short more than 20 SAR (Settings ▸ POS). The POS now logs removed lines
and cleared bills.

**📲 Owner's evening report on WhatsApp** — sales (vs the same day last week),
payments, returns, expenses, cash short / over, best 5 items, stock alerts,
cashier warnings, cloud backup state. Automatic at a set time (Settings ▸
WhatsApp ▸ Send the owner's evening report automatically), or **Day Close ▸ 📲
Owner report**, or Settings ▸ WhatsApp ▸ send now.

**☁ Nightly cloud backup** (Settings ▸ Backup) — DayBill makes a backup, zips it and
puts it in your Google Drive / OneDrive / Dropbox folder (found by itself); the
cloud app uploads it. Keeps the newest 14. If the PC was off at the time, it runs
5 minutes after DayBill opens. A message when the last copy is more than 2 days
old. Turn the evening jobs on only on ONE PC (the main PC).

## 🤖 v6.3.0 — AI inventory management · Claude connector (36 tools) · slimmer header

**More room for every page** — the header is slimmer: top bar 58 → 44, each
window's title is ONE line (name · sub-title · — ☐ ✕), taskbar 38 → 32.

**AI inventory engine** (`modules/inventory_ai.py`, read-only, worked out from
your own sales, purchases, batches and branches)
- **Stock health score** (0–100) + **What to do now** in order: items out / running
  out in 3 days, best sellers (A) running low, expired batches, items below cost,
  minus stock, stock that will expire before it sells, branch transfers, money
  stuck, overstock, product data to fix.
- **Forecast**: sells / day (last 14 days 60 % + last 30 days 40 %), trend ▲▼,
  days of stock left, **run-out date**, status.
- **Reorder plan** per supplier (unit you buy in, last price, total).
- **ABC**: A = first 80 % of sales (by sales, profit or qty), B, C; A items at risk.
- **Expiry**: batches near expiry and **how much will NOT sell in time** at the
  current speed (first expiry first) → sell first / discount now / write off.
- **Branch transfers**: one branch short, another with double what it needs →
  move instead of buying.
- **Bought together** (market basket): items in the same bill → shelf / combos.
- **Supplier prices** per product (per base unit), cheapest supplier, trend.
- **Data check**: no barcode, stock without cost, no price, minus stock, a barcode
  on 2+ products, no category / Arabic name / VAT, selling items without a reorder level.

**🤖 Smart Insights** (Reports & Compliance ▸ Smart Insights) — health score
card + tabs: Reorder · **Forecast** · **ABC** · **Expiry** · Not selling · Price ·
**Together** · **Branches** (2+ branches) · **Data** · Trends · Today.
- **💬 Ask AI**: ask in plain words (English or Arabic) — "what should I order this
  week?", "ايش الأصناف اللي بتخلص؟" — Claude answers with DayBill's own numbers
  (it calls the engine above as tools). Needs the API key (Settings ▸ AI). Sends
  stock and sales figures, product and supplier names — never customer names.
  Nothing is changed.
- **🔌 Claude desktop**: installs / updates the Claude connector on this PC.

**Claude connector** (`claude_connector`, still read-only) — 12 new tools
(`inventory_health`, `stock_forecast`, `reorder_plan`, `abc_analysis`,
`expiry_alerts`, `branch_transfers`, `bought_together`, `supplier_prices`,
`data_check`, `price_check`, `sales_trends`, `daily_briefing`) → **36 tools**,
plus **7 ready-made prompts** in Claude (+ ▸ DayBill ERP): Daily stock check ·
What to order this week · Weekly business review · Expiry & dead stock clean-up ·
Price & margin check · Fix product data · Month-end VAT check.
Run `INSTALL_CLAUDE_CONNECTOR.bat` again to update.

## 🎨 v6.2.1 — Reports Center: report list on top (full-width tables) · 🎨 Theme

**Reports Center — the report list moved from the left to the top**
- Four group buttons across the top: 📒 Accounts & VAT · 🧾 Sales & POS ·
  🛒 Purchases · 📦 Inventory. Click one → a drop-down with **all the reports of
  that group**. The open report's group is marked and has ● in its list.
- 🔍 **Find a report…** (top right): type → the matching reports drop down
  under the box; ↓ and Enter, or a click, opens one; Esc closes.
- The report table now uses the **full page width** (no list on the left).
- A cleaner page: group + report name with **Excel · PDF · Print · ☰ Columns**
  on the same line, one filter line ending with **▶ Run**, the totals in one
  strip with the period and row count on the right. Table colours follow the theme.

**🎨 Theme** (top bar, next to Aa ▾)
- A picture of every theme; click one → the **whole app changes at once** (no
  restart) and it is remembered. Themes: DayBill Blue, Saudi Green, Corporate
  Blue, **Teal**, **Graphite**, **Maroon**, **Desert Sand**, Purple (classic).
- **My own colour…** — pick any colour; DayBill makes the side menu, buttons,
  selection and tables from it (a very light colour is made darker so white text
  stays readable).
- Also in Settings ▸ System ▸ Theme. Fixed: a theme chosen there only changed
  after a restart.

## 📑 v6.2.0 — Every register, Input / Output VAT, and a Columns tool on every table

**New reports** (Reports menu, Reports Center, and Accounts / Inventory ▸ Reports)
- **Output VAT Register (Sales VAT)** — every sales invoice, POS bill, credit /
  debit note and sales return: type (tax invoice / simplified / POS / credit
  note), customer VAT No., standard 15 %, zero-rated, exempt, out-of-scope,
  output VAT, total. Its VAT total = VAT Return box 6.
- **Input VAT Register (Purchase VAT)** — every purchase invoice (import when the
  supplier is outside KSA), purchase return and expense with VAT: supplier
  invoice #, supplier VAT No., standard / zero / exempt, input VAT. Its VAT
  total = VAT Return boxes 7 + 8.
- **Sales Register — item details** and **Purchase Register — item details** —
  every line (product, qty, unit, rate, discount, net, VAT %, VAT, total;
  purchases also batch and expiry).
- Sales / Sales Return / Purchase / Purchase Return Registers now also show
  **VAT No.** and **Discount** (the Sales Register also the document type).
- Already there: VAT Return, VAT Detail Register, Stock Report, Stock Valuation,
  Stock Movement, Item Ledger, Low / Dead Stock, Stock Transactions, Stock by
  Branch, Expiry, Day Book, Trial Balance, P&L, Balance Sheet … (50 reports).

**Columns tool — on every table** (reports, entry grids, transaction lists, masters)
- **Right-click any column heading**: Hide column · Width… · Fit width to text ·
  Move left / right · Show / hide columns · Fit all · **Columns…** · Reset.
- **☰** appears at the top-right corner of a table when the mouse is on the
  headings — same menu. Reports Center has a **☰ Columns** button.
- **Drag a column edge** = new width; **double-click the edge** = fit to text.
- **Drag a heading onto another heading** = move the column there.
- **Columns…** window: tick to show, ▲ ▼ to move, width in pixels, Fit, Reset.
- Remembered **per table on this PC** (`config\table_layouts.json`, kept by
  updates); each report and each entry form (sales, purchase, returns …) has its
  own. Widths are saved at 100 % so they follow Settings ▸ Text size.
- **Excel / PDF / Print / Copy** use the columns you see, in your order and
  widths.
- Entry grids: Product can't be hidden; hide Bar Code → the cursor goes to
  Product; hide Rate → Enter goes on to the next row; the totals row follows.
- The POS cart keeps its own column setting (POS ▸ Settings).

## 🛠 v6.1.0 — DayBill Database Tool: bring another program's data into DayBill

Start it from the Start menu (**DayBill Database Tool**), `DayBill_Database_Tool.bat`,
or `DayBillERP.exe --dbtool` (from source: `python dbtool.py`).

**1. Server & databases** — 🔍 Find the SQL Server, list every database
(`✓ DayBill` / `✗ another program`), pick **FROM** (the other program) and
**TO** (a DayBill database), or 🆕 make a new DayBill database. A SQLite file
(e.g. Aronium POS) can be opened as FROM too.
*Restore the other program's .bak under a NEW name first* (login ▸ Database
Settings ▸ ♻ Restore), never over your DayBill database.

**2. Reset password**
- DayBill database: 🔑 *Ask a new password at the next sign-in* (they sign in
  with any password, then choose one) or *Set a new password now*.
- Another program's database: its sign-in table is found, the password is
  never shown — only how it is kept (md5, sha256, bcrypt, plain …). A new
  password is set **in the same format** after you tick "I am the owner …";
  a backup of that database is made first and it is logged. Formats that
  can't be set safely (Argon2, ASP.NET, encrypted) are refused.

**3. Convert to DayBill** — 🔎 *Read the old database*:
- **Microsoft RMS** (Item / Alias / Department / Customer / Supplier) and
  **SAP Business One** (OITM / OCRD / OITB) are recognised by their tables.
- Any other program: DayBill **guesses** the tables and columns from their
  names (English, Arabic, short forms like ItmNo, CustNo, SalePrice) and from
  the values (barcodes with check digit, prices, Arabic text, VAT numbers),
  shows how sure it is (green / orange / red) with example values — change any
  column by hand. 💾 *Save map*: the next database with the same tables opens
  with your map.
- 👁 *Preview* (rows exactly as they will be in DayBill) → ✔ *Check* (how many
  new / updated, stock value, what customers owe, what we owe suppliers, every
  problem with a code: duplicate code, barcode clash, minus stock, old 5 % VAT,
  bad VAT number …; export them to CSV) → ⬇ *Convert* (your name + "I am the
  owner" tick; a backup of the DayBill database is made first).
- What comes: categories, products (code, barcode — a 13-digit item code is
  also its barcode, names AR/EN, unit, sell price incl. VAT, cost, VAT
  S/Z/E), extra barcodes, customers, suppliers, **opening stock** and
  **opening balances** (posted against Opening Balance Equity — *Close
  openings to capital* when done). Old invoices are not copied; old
  passwords are never copied.
- Safe to run again: products and parties are updated by code, opening stock
  and balances are replaced — never doubled. A log (who, from where, every
  problem) is kept in `logs\dbtool_*.txt`.

## 🔑 v6.0.2 — Other ways in: find the server, pick DayBill's database, reset a password

- **🔍 Find** (Database Settings, next to Server): tries the SQL Servers
  installed on this PC, the usual names (`localhost\SQLEXPRESS`,
  `localhost`, LocalDB) and the servers that answer on the network (the
  server PC of a till), with the sign-in settings shown — the ones that let
  DayBill in are listed in the Server box.
- **🗂 List** marks every database: `✓ DayBill` (listed first) or
  `✗ other program`. Signing in to another program's database now offers
  to **switch to the DayBill database** found on the same server.
- **🔑 Forgot password?** (login screen):
  1. another administrator: System ▸ Users & Rights → 🔑 Reset Password;
  2. nobody can sign in: run the query shown there (📋 Copy) — or the file
     `database\RESET_user_password.sql` — in SQL Server Management Studio.
     Then sign in as that user with **any** password: DayBill asks for a new
     one first. The query changes **nothing** on a database that isn't
     DayBill's.
- A SQL password saved on another PC (settings copied) can't be opened here
  — the connection message now says so: type it again in Database Settings.

## 🛟 v6.0.1 — Safe restore: another program's backup can't replace your data

- **♻ Restore Database (.bak)** (Database Settings) now looks inside the
  backup first (it is opened once in a throw-away database and checked):
  - a backup of **another program** is never put over an existing
    database — "'DayBillERP' was NOT changed". To keep that program's data
    on the server, type a NEW name (e.g. `OldSoftware`) and restore again;
    DayBill stays on its own database.
  - before a database is replaced, a **safety copy** is saved in the backup
    folder: `<name>_<date>_before_restore.bak`.
- **Sign in** on a database that is not DayBill's (another program's or an
  empty one) now says so and opens Database Settings — it used to show
  "Database connection failed … 'user_id'". **Save** in Database Settings
  warns the same way. DayBill never runs its updates on such a database.
- **Got the 'user_id' message?** Database Settings → 🗂 List → pick your
  DayBill database → Save. If the other backup went INTO your DayBill
  database, restore your newest DayBill backup from `C:\DayBillERP\Backups`
  (`DayBillERP_YYYYMMDD_HHMM.bak` from before the wrong restore).

## 🚀 v6.0.0 — Safe saves, ZATCA Wave 25, better checkout, branches & expiry, books & HR

Before you start: **Updates ▸ Apply All Updates** happens by itself at the
next start (new database patch `zz_v600_patch.sql`). Nothing else to do.

**Safety (every PC, every save)**
- **All-or-nothing saves**: a bill, purchase, return, receipt, expense,
  product, stock adjustment or payroll run is saved whole — or, if anything
  fails half-way (power, network, a duplicate barcode), nothing is kept and
  the screen says so. No more half-posted stock or journals; two tills can't
  take the same bill number or ZATCA counter.
- **Passwords**: always salted (bcrypt). Old SHA-256 passwords are upgraded
  automatically the next time that user signs in. 5 wrong passwords lock the
  user name for 60 seconds — also after closing DayBill or on another PC.
- **Secrets locked to the PC**: the SQL password and the AI / Wathq / relay /
  WhatsApp keys are stored encrypted with Windows (DPAPI), not in plain text.

**ZATCA — ready for Wave 25 (1 February 2027)**
- **One e-invoicing unit per till**: ZATCA ▸ Connect ▸ tick *Connect THIS till
  only*. Each till then has its own counter (ICV) and hash chain; tills not
  connected on their own keep using the shop-wide unit (as before). The
  background sender sends every document with the unit that signed it.
- **🔒 Protect keys** (ZATCA screen): the private key and certificate secrets
  are encrypted by SQL Server itself; every DayBill PC keeps signing. Write
  down the **recovery code** — needed only when the database moves to another
  SQL Server.
- **➕ Debit notes** (Sales ▸ Debit Notes): raise the amount of an invoice
  already issued (ZATCA type 383, with the invoice number and the reason).
- **24-hour warning**: the dashboard, ZATCA screen and Day Close show bills not
  yet reported after 20 hours (ZATCA wants simplified invoices within 24 h).
- ZATCA answers: reporting **409** = already reported (counted once, noted);
  clearance **208** = already cleared; clearance **409** = a real conflict →
  shown as rejected for a look (was counted as success).
- A bill paid **cash + card** (+ STC Pay …) tells ZATCA every payment means.
- The new **Unified Number (700…)** is sent with ZATCA scheme 700.
- Every new XML was checked with the ZATCA SDK-parity validator.

**VAT return** (Reports ▸ VAT Report)
- Box 2 (citizen health / education), Box 4 (exports to customers outside
  KSA), Box 8 (imports from foreign suppliers with VAT) are filled from the
  books; Box 9 (reverse charge), Box 14 (corrections) and Box 15 (credit
  brought forward — suggested from the last saved refund return) are typed in.
  Box 16 = 13 + 14 − 15. Out-of-scope sales are no longer added to Box 5.

**POS & selling**
- **More ways to pay**: STC Pay, Tabby, Tamara (+ Apple Pay, bank transfer,
  gift voucher — Settings ▸ POS) next to Cash and Card. Each goes to its own
  account (Tabby / Tamara → *BNPL receivable 1260*, paid by the provider
  later). Day Close lists the bills by way of payment.
- **Cashier shifts** (POS ▸ Shift F9): opening cash → bills → count the drawer
  at the end (blind count). Short / over is kept (Reports ▸ Cashier Shifts).
  Settings ▸ POS can require a shift before the first sale.
- **💲 Price lists** (Inventory ▸ Price Lists): VIP −5 %, restaurants at the
  wholesale price, fixed prices per product. Give a customer a list
  (Customer ▸ Contact & Credit); the POS and the invoice's **Price Category**
  box follow the customer (the box used to do nothing).
- **📴 Keeps selling when the server is briefly gone**: if a POS bill can't
  reach SQL Server (network / server PC restarting), the cashier can keep it
  on the till (receipt marked PROVISIONAL, its own number OFF-T<till>-00001 —
  never used by another till); every minute the POS sends the kept bills —
  same number, time and tenders, with stock, books, shift and ZATCA. Closing
  the shift and Day Close warn while bills are still kept on the PC. Sales on
  account still need the server. (Settings ▸ POS.)
- **💡 Suggest** on a Purchase Order fills it with the products at / below
  their reorder level (for the chosen supplier).

**Stock**
- **Stock per branch** + **🔁 Stock Transfers** (Inventory): move goods between
  branches; every sale / purchase / count belongs to the branch of the till.
  A one-branch shop sees no change. Report: Stock by Branch.
- **⏰ Batches & expiry**: tick *Track expiry dates* on a product, type the
  batch and expiry in Purchase ▸ ⏰ Expiry dates. Sales take the batch that
  expires first; returns, transfers and edits follow. The dashboard warns
  before goods expire; **Write off** takes expired batches out (loss posted).

**Books**
- **🏦 Bank Reconciliation**: tick the lines on the bank statement until the
  difference is 0.00, then Finish.
- **📅 Year-End Closing**: closing a year now posts the closing entry
  (profit → Retained Earnings), checks ZATCA and drafts first, and can be
  reopened. The P&L of a closed year still shows its real figures.

**HR & payroll**
- GOSI **old / new system** per employee (new law from 3 July 2024: pension
  9 → 11 % in 0.5-point steps each July to 2028). All rates are settings
  (Settings ▸ HR & Payroll) — a new GOSI decision needs no new version.
- **🌴 Leave** (annual 21 / 30 days after 5 years, sick, unpaid, Hajj …) and
  **🕘 Attendance** (present / late / absent, in / out, hours). Absent days and
  unpaid leave are taken off the payroll run.

**Program**
- **Updates ▸ 📦 Install a new version…**: pick the new DayBill zip — DayBill
  checks it, keeps a backup of the old version, copies the new one and
  restarts. Settings, database settings and the product key are kept.
- **BUILD_EXE.bat** also makes a one-file **Setup.exe** when Inno Setup 6 is
  installed (`tools/DayBillERP_Setup.iss`).
- `requirements.txt` pins the library versions DayBill is tested with;
  bcrypt is required.
- The Updates screen and the start-up use **one** database-update engine.
- **Fixed**: purchase lines took the unit's **selling** price instead of the
  cost when a product had units; Purchase Orders were priced at the selling
  price.

---

## 📒 v5.26.0 — Accounting update: opening balances, aging, day report, exports

- **🏁 Accounts ▸ Opening Balances** (new page; also Inventory ▸ Opening Stock):
  one place for the first day — **Accounts** (cash in hand, bank, fixed
  assets, loans, capital …), **Opening stock** (quantity + cost per product,
  or **Import Excel** with Code / Qty / Cost), **Customers** and
  **Suppliers**. Type straight into the grid, then Save. Everything is
  posted on the **opening date** against Opening Balance Equity; changing an
  amount re-posts it (never doubles). **Move to Owner's Capital** closes
  Opening Balance Equity into capital.
- Stock that sat on a product with nothing behind it (typed in or imported)
  is found and can be booked as opening stock in one click, so the stock
  card, Stock Movement and the Inventory account always agree.
- Product **Excel import**: the Opening Stock column now becomes real opening
  stock (stock card + books) and never overwrites the stock of a product that
  already has purchases / sales. A saved product's stock can't be typed over
  in the product window any more (it undid sales made meanwhile);
  **Duplicate** no longer copies the stock.
- **New reports** (Reports Center + Accounts ▸ Reports): Cash & Bank Balances,
  Day Report (sales, returns, purchases, expenses, received, paid, cash in /
  out and closing cash & bank per day), Receivable Aging, Payable Aging,
  Customer / Supplier Outstanding Bills, Expense Summary (all expenses in the
  books, per month), Opening Balances, Stock Transactions (every in / out).
- **Aging fixed**: balances come from each party's ledger (same as the Trial
  Balance), aged against the payment terms — a receipt / payment settled
  against bills closes those bills, the rest goes oldest bill first (Not due /
  1-30 / 31-60 / 61-90 / 90+), advances in their own column. Before, draft
  and cancelled invoices were counted and advances showed as owed.
  Double-click a party → its open bills.
- **Customer / Supplier statements** come from the ledger: opening balance,
  invoices, POS bills on account, receipts, returns, expenses on credit and
  journal vouchers — closing = what they really owe.
- Customer Balances no longer shows the Cash Customer (its ledger is the
  Cash account); entries posted straight to Accounts Receivable / Payable are
  moved to the right customer / supplier once on start-up, and a customer
  without a ledger gets one automatically on the first credit sale.
- **Excel / PDF from every screen**: Excel amounts are real numbers (SUM
  works), columns sized, company name on top; PDFs fit the page (landscape
  for wide tables), print Arabic correctly, right-align numbers, page numbers,
  long headings and names wrap instead of running into the next column.
  Tested: every export button on the accounting screens + all 43 reports.
- **Fixed after a full independent check of the books** (a test shop with
  openings, purchases, sales, POS, returns, receipts, payments, expenses,
  a journal and a stock adjustment — 310 checks, every report vs hand sums):
  - Receipts, payments and expenses by **card / mada / cheque** now go to the
    **Bank** account, like card sales and refunds already did (card went to
    "Card / POS Clearing", cheque to Cash).
  - **Day Close**: "Card / mada on bills" shows the card sales (it showed 0).
  - **Counter cash in drawer** also takes off cash purchases (and adds cash
    refunds from suppliers).
  - **Stock Movement**: opening stock is in the Opening column (it showed as
    "Adj. in" for this year).
  - **Cash & Bank Balances / Day Report**: the opening cash and bank are the
    start balance, not "money in" on the opening day.
  - Correcting the **cost of opening stock** keeps the average cost right, so
    Stock Valuation = the Inventory account.
  - A **purchase return at a price different from the cost**: the goods leave
    Inventory at their cost and the difference goes to Cost of Goods Sold
    (Inventory and Stock Valuation stayed apart before).
  - **Aging / Outstanding Bills** follow the receipts you settled against
    bills on the payment screen (and returns made from a bill); money not tied
    to a bill settles the oldest bills.
  - Opening Balances report shows what was moved to Owner's Capital.
  - Vouchers list: entries made by documents (POS, cost of sales …) and
    opening balances can't be deleted there — change the document or the
    Opening Balances page instead.

---

## 🪟 v5.25.0 — Windows 11 look, calendar on every date, folding menu, normal-size pop-ups

- **📅 Calendar on every date box** (reports, lists, statements, vouchers,
  expenses, day close, HR …): click 📅 or press **Alt+↓ / F4**. From / To
  boxes also get **Quick range**: Today, Yesterday, This / Last week,
  This / Last month, Last 7 / 30 days, This / Last quarter, This / Last year
  — picking one fills both dates and runs the report.
  Keys in a date box: **↑ / ↓** = next / previous day, **PgUp / PgDn** =
  month, **T** = today, **Y** = yesterday. Typing shortcuts: `5` = the 5th of
  this month, `5/10` = 5 October, `+3` = in 3 days, `-7` = a week ago.
- **☰ Side menu folds to icons** (button left of the search box, or click the
  logo). Each icon opens its pages; the page you are on is lit. Remembered
  (Settings ▸ System).
- **Pop-up windows open at a normal size**, like the Product window — in the
  middle, never full screen (at most 86 % × 91 % of the desktop). Only
  Sales / Purchase / Return / Quotation windows still open big (their item
  grid needs the room).
- **Customer and Supplier forms** are now pages like the Product window:
  Basic & Tax · Address · Contact & Credit (Payment). New **Save & New**,
  **F4** = Save, **Alt+1/2/3** = page. Supplier form now also has Address,
  Arabic city and Arabic contact person.
- **Boxes sized for what goes in them** in every form: codes medium, numbers
  and amounts short, phone / VAT medium, names and addresses wide. Boxes
  can't take more letters than the database holds (VAT 15, phone 20 …).
- **Product code: at most 8 characters** (Settings ▸ Inventory ▸ Product Code
  Maximum Length; 0 = no limit), medium box. New codes always fit. Old
  products with longer codes still open and save.
- **Windows 11 look:** white title bar with round corners (Settings ▸ System),
  slim scrollbars without arrows, flat menus, page tabs with a blue line.

---

## 🧩 v5.24.1 — New Product window: normal size, pages, simple order

- Opens as a normal window in the middle of the screen (860×500 at 100 %
  text, grows with the Text size) — not full screen. Minimum 720×460.
  Remembers the size you leave it at (old full-screen sizes are not reused).
- **Pages instead of scrolling:** Basic · Price & VAT · Stock ·
  Units & Barcodes · More (Suppliers, Stock history, Sales, Purchases,
  Images, Notes). Each page is two columns and fits without a scrollbar.
- Simple order: Basic = type, code, names, alias / list-in | category,
  barcode, brand. Price & VAT = sales price, unit, VAT | cost & margin.
  Stock = inventory + stock limits | weight scale + active / POS favourite.
- Removed duplicates and clutter: the Currency box (shop currency is used),
  the read-only "Units & Rates Summary" and "Multi Rates" tables (the Units
  table shows and edits the same), long help text. Edit-only actions (Multi
  Barcodes, QR, Print barcode, Duplicate, Delete) are in one **More ▾** menu.
- Fixed: the selected **Product** button's text was invisible.
- Fixed (all dialogs): with Text size above 100 %, windows that size
  themselves to their content were made bigger a second time (could fill the
  screen); rounded buttons now grow with the text, so their labels fit.

---

## 🎨 v5.24.0 — Bigger text, new main window, one-file database install

- **Bigger, clearer letters everywhere.** The screens were drawn at 1 pixel
  per font point (a "9" font was 9 px tall). New **Text size** for the whole
  app — default **125 %** — in the top bar (**Aa ▾**: 100 / 112 / 125 / 140 /
  160 %) or Settings ▸ System ▸ Text size. Table rows, table columns and
  dialog windows grow with the text, so nothing is cut off. The POS screen
  keeps its own size setting (Settings ▸ POS ▸ Screen size).
- **New main window** (like the design you sent):
  - sidebar: DayBill logo, **DayBill ERP** + sub name *Billing & Inventory
    Management* (change it in Settings ▸ System), **🔍 Search menu…** (type
    "stock", "bill", "vat"… ▸ Enter), bigger menu, and at the bottom
    *DayBill ERP · Simple • Fast • Reliable · Version 5.24.0*
  - top bar: search anything (Ctrl+K), date + time (wide screens), Aa ▾,
    POS, language, alerts, user
  - every page: **heading + sub-heading** (one line saying what the page is
    for); the page's own copy of the same title is hidden, so it shows once
  - darker grey for small text (easier to read)
- **Database:** the one-file installer is now
  **database\INSTALL_DayBillERP_AllInOne.sql** (all tables + every patch, clean
  starting data) with **database\README_DATABASE.txt**. Create New Database…
  in DayBill finds it there. The base schema moved to tools/sql_base/.
- One version number for the app (config/version.py): sidebar, About, login,
  Updates show 5.24.0 (Updates showed "v1.7.0" before).
- A page that hits an error while opening now says so in plain words (it
  used to show "Coming in next steps…").
- Customer save error *"cannot access local variable 'messagebox'"*: that was
  fixed in 5.14 — a PC that still shows it runs an old copy; install this one.
- The release zip no longer contains config/app_settings.json, so unzipping an
  update over your DayBill folder never replaces your settings (DayBill makes
  the file itself). Note: the 5.23.2 zip carried a test copy — if you unzipped
  it over your folder, check Settings once (branch/counter, setup flags).

---

## 🔧 v5.23.2 — Van relay works over https and http (new relay files)

- **Why https looped:** the 5.23.0 `.htaccess` forced https. Behind Hostinger's
  CDN the relay sees http, so it sent every https visit back to itself — and the
  site **saved (cached)** that answer for `api.php` and `/`. Removing the line
  (5.23.1) did not clear the saved answer.
- **Fix from DayBill's side — nothing to change in hPanel:**
  - new addresses that were never saved: `van_api.php` (relay), `van_db.php`,
    `van.html` (phone address). `api.php` stays as the old name.
  - every call has a fresh address (`…&_=time`) and the relay answers
    "never cache" (browser, LiteSpeed, CDN).
  - the new `.htaccess` has no redirect and stops the main site's rules
    (WordPress / Force HTTPS in `public_html`) from reaching the relay folder.
- **`check.php`** — open it on your relay: SSL, redirect loop, saved answers,
  `.htaccess` rules (this folder and the main site), files, database, last sync,
  with "What to do" in order. No passwords or keys are shown.
- **DayBill ▸ Mobile & Van ▸ Van (internet):**
  - *Van phones open* address + QR (`…/van.html`), 🌐 *Check page* button.
  - *Test connection* explains loop / SSL / missing files in plain words; when
    https is broken but http works it asks "Use http for now?", and goes back to
    https by itself when https works.
  - *Make upload folder* also makes **daybill_van_upload.zip** (upload ▸ Extract),
    with **Update files only** (keeps the site's relay_config.php).
- Phone app: no cached answers; the offline app installs even if one old
  address of the site still loops. Android app: a web address gets https.
- Tested on a real Apache + PHP + .htaccess behind a caching SSL proxy
  (like Hostinger's CDN): the user's loop reproduced, then fixed without purging.

---

## 🔧 v5.23.1 — Van relay: "Relay answered 301" fixed

- The `.htaccess` in the upload folder forced https itself; on Hostinger
  (HTTPS is handled before your site) that made an endless redirect loop —
  DayBill showed *Relay answered 301*, phones "too many redirects".
  The new `.htaccess` has no redirect; turn HTTPS on in hPanel ▸ Security ▸ SSL.
- DayBill now follows a normal redirect (http → https, moved folder), keeps the
  real address, and explains a redirect loop / missing api.php in plain words.

---

## 📱 v5.23.0 — Mobile, PDT scanners & Van sales (one app)

Sidebar ▸ Inventory ▸ **📱 Mobile, PDT & Van**. Full guide: **HOW_TO_USE_MOBILE.md**.

- **One app, modules per user:** Goods In · Goods Out · Stock Count ·
  Stock Adjust · Product Info · Price Check · Van Sales. Tick them per DayBill
  user (Users & modules); the device shows only those.
- **Shop Wi-Fi:** DayBill runs a small server (▶ Start, port 8090). PDTs and
  phones open the shown address in Chrome (QR on screen) ▸ Add to Home screen ▸
  sign in with their DayBill user. PDT scan button works as is (wedge mode).
- **Stock:** Goods Out / Count / Adjust change stock + post to the books (or
  wait in the 📥 Inbox for approval). Goods In makes a draft purchase for the
  office to confirm. Every document is booked once, even if sent twice;
  documents wait on the device when the Wi-Fi drops.
- **Van sales over the internet** through your **Hostinger** site: the van
  sells offline (catalogue on the phone), bills go up when there is signal,
  DayBill collects them every few minutes (Van (internet) ▸ Sync / auto sync)
  and books them as sales invoices (channel VAN). *📁 Make upload folder* builds
  the relay + app + private config. The shop PC is never opened to the internet.
- **Printing:** Bluetooth 58/80 mm printer (Android app or RawBT), PDF,
  WhatsApp — with the ZATCA QR.
- **Android app** (`android_app/`): WebView app with camera scan, PDT scanner
  broadcasts and Bluetooth printing; build the APK free on GitHub Actions.

---

## 🔢 v5.22.2 — Product code always unique · system barcodes locked

**Product code**
- A new product gets the **last created product's code + 1** (1005 → 1006,
  P0012 → P0013, ITM-0099 → ITM-0100). Tick *Manual* to type your own.
- Codes are unique **in any format**: `P1`, `p 001` and `P0001` count as the
  same code, and a code may not be the same as any barcode. Save shows
  which product already uses it. Excel import treats them the same way
  (`imp 01` updates IMP1 instead of making a second product).

**Barcodes — made by DayBill only**
- Every product and every unit gets a **6-digit** barcode in order
  (100001, 100002 …). Settings ▸ Barcode ▸ *First Auto Barcode* sets
  where numbers start (e.g. 543210 → 543210, 543211 …).
- The barcode boxes on the product form and in the Units manager are
  **read-only** (grey): the new form already shows the barcode the
  product will get. Ctrl+B / ⚡ no longer change it.
- A barcode printed by the maker goes into **🏷 Extra barcodes** of that
  unit — it scans exactly like the system code. Products made from a
  supplier invoice (AI) and from Excel import do this by themselves.
- Scanning a system code, a maker's barcode or a product code gives the
  product with its unit in every scan box.
- To type barcodes yourself again: untick *System Barcodes Are Made By
  DayBill Only* in Settings ▸ Barcode.

---

## 🔢 v5.22.1 — 6-digit barcodes for every new product and unit

- Saving a new product: the product **and each unit** (PCs, Pack, Box,
  Carton…) left without a barcode get their own **6-digit** code —
  100001, 100002, 100003… in order. The product's main barcode is its
  piece (PCs) code.
- Every new code is checked against all product barcodes, unit barcodes
  and extra barcodes, so it is never used twice (a gap in the numbers is
  filled when the top is reached).
- The same rule is used by Ctrl+B, the ⚙ generate buttons, the Units
  manager, AI-created products, *⚡ Make the missing barcodes* and the
  label printer.
- Settings ▸ Products & Barcodes ▸ Barcode ▸ *Barcode Length* is now 6.
  Shops still on the old default (13) move to 6 once; type 13 to go
  back to EAN-13. Codes you already have never change.
- 6-digit codes print as Code 128 on labels and scan everywhere (POS,
  Sales, Purchase, Stock, Price Check…).

---

## 🏷 v5.22.0 — Barcodes for every unit, label printing, invoice designer, settings

**One barcode answer everywhere.** Scan a code in *any* box — POS barcode
or search, Sales / Purchase / Returns / Quotes grid (barcode **or** product
cell), Stock Adjustment, Stock Count, Offers, Label printing, Price Check —
and you get the product **with its unit**:
unit barcode (PCs / Box / Carton) → extra barcode → product barcode →
product code → weighing-scale label (PLU + weight / price). Arabic digits
and the stray Enter/Tab some scanners send are ignored.

**Every product and every unit has its own barcode**
- Settings ▸ Products & Barcodes ▸ Barcode: *⚡ Make the missing barcodes
  now* — fills every product and unit at once (codes follow Prefix /
  Length / Check Digit; existing codes never change). The product and its
  piece share one code; Box, Carton… get their own.
- New products: *Create Barcodes Automatically (Product + Every Unit)*.
- Fixed: on SQL Server the second unit saved **without** a barcode (or a
  second unit removed from a product) failed with *Violation of UNIQUE KEY
  constraint 'UQ_product_unit_barcode'*. The patch
  `zz_barcode_unique_patch.sql` (runs by itself at start-up) keeps real
  barcodes unique and allows any number of blanks.

**Print Barcode Labels** (Sidebar ▸ Inventory ▸ Print Barcode Labels, or
Products ▸ Print labels, or the product's 🖨 Print Barcodes)
- Scan or type a name; the drop-down lists each **unit** with its price
  and barcode. Scan again = +1 copy. *Every unit* adds PCs + Box + Carton.
- Copies: − / + / type / *Set for all* / *= Stock* (one label per item in
  stock, per unit). ＋ Category adds a whole category.
- Pick a **design**: 4 ready designs are added once — *Price tag 40×30 ·
  big price*, *Shelf 58×40 · Arabic + offer*, *Small 38×25*, *A4 sheet 3×8
  (70×37)* — or your own from the Label Designer (✏ Edit design). Live
  preview of the real label.
- New label fields: Price incl. VAT, Unit, Offer (HALF PRICE…), Offer
  Price, Old Price (struck through), "incl. 15% VAT", Shop name; text
  alignment left / centre / right. Labels show the price WITH VAT even
  when prices are kept without VAT, and the offer price while an offer runs.
- Rows without a barcode are red; *⚡ Make missing barcodes* fixes them.
- **Purchases ▸ 🏷 Labels**: labels for the goods just received — each
  line's unit, copies = quantity.
- A4 sheets always fit the paper (a 3 × 70 mm sheet no longer runs off
  the right edge).

**Price Check** — POS **F8** (or System ▸ Barcode & Labels ▸ Price Check):
scan anything to see the name, price with VAT for that unit, the offer,
stock in units (e.g. *13 (1 Box + 1 PCs)*) and every other unit — nothing
is added to the bill.

**Stock screens scan too**
- Stock Adjustment: scan a Box → product chosen, quantity 12 pieces; scan
  again → 24.
- Physical Stock Count: scan each item → +1 counted (a Box adds its
  pieces). Counts are kept while you search (before, searching cleared
  them).

**Invoice Designer — every element prints**
- VAT amount, VAT %, amount, # and other narrow columns never print as
  "4.…" or blank: the font shrinks to fit; column titles too.
- Adding a column (e.g. *VAT Amount*) to an old one-block table keeps the
  table — both print together.
- Columns drawn past the paper edge (e.g. on 80 mm) are squeezed in.
- New elements land in a free spot instead of on top of each other.
- Save asks "Use THIS design when printing?" (★ default).
- Built-in 80 mm receipt: **VAT of each item** column (Settings ▸ Tax ▸
  *Print VAT Of Each Item On The Receipt*); 58 mm shows it on a 2nd line.

**Settings** — pages grouped the way a shop owner looks for them (Sales &
POS, Purchase, Products & Barcodes, Tax, Customers & Suppliers, Printing,
Accounts & Year, Alerts & WhatsApp, Security & Backup, AI). Only the open
group unfolds, so every page fits on a 1366×768 screen.

---

## 🔐 v5.21.0 — ZATCA Phase 2 (e-invoicing integration) — easy connect

**Sidebar ▸ Reports & Compliance ▸ ZATCA** — rebuilt from scratch.

**Connect once, in 3 steps on one page**
1. *Shop details* exactly as on the VAT certificate / national address
   (Arabic + English name, VAT no., CR no., building no. 4 digits, street,
   district, city, postal code 5 digits) — each field shows ✓ / ✗ live.
2. *Where*: **Sandbox** (test only — OTP 123345 filled in for you),
   **Simulation** (practice with your real VAT no.) or **Production**.
3. *OTP* from the Fatoora portal (fatoora.zatca.gov.sa ▸ Onboard new solution
   unit ▸ Generate OTP, valid 1 hour) → **🔐 Connect to ZATCA**.
   DayBill then does everything by itself, with a live step list: makes its
   key + certificate request (CSR) → compliance certificate → sends ZATCA's
   **6 test documents** (standard + simplified invoice, credit note, debit
   note) → production certificate → *Connected*.

**After that, automatically**
- Every **POS bill / Sales invoice / Sales return** is put in the ZATCA
  chain the moment it is saved: invoice counter (ICV), previous invoice hash
  (PIH), UBL 2.1 XML.
- **B2C (simplified)**: signed at once (ECDSA secp256k1, XAdES) — the
  receipt prints the **Phase 2 QR (tags 1-9)** straight away; *reported*
  to ZATCA in the background.
- **B2B (customer with a VAT no.)**: *cleared* by ZATCA; the QR from ZATCA's
  cleared invoice is printed. Printing before clearance warns you.
- **Credit notes** (returns) carry the original invoice + reason and print
  their QR too. Offer discounts go into the XML as line discounts.
- **No internet?** Bills are still signed and printed; they wait and are sent
  when the internet is back (tries every 2 minutes).
- **Missing data** (e.g. a B2B customer without postal code) is held **out**
  of the chain with a plain reason ("✋ Fix needed") — fix it, press
  *Send again*. ZATCA rejections show ZATCA's message.
- A signed document **can't be edited or deleted** any more (POS, Sales,
  Returns) — make a Sales Return (credit note) instead.

**ZATCA screen when connected:** unit, certificate end date, documents
signed; tiles *Waiting / Reported / Cleared / Need a fix / Rejected* (click =
filter); list with ZATCA's message; **Send now**, auto-send on/off,
**Send again (after a fix)**, **View / Save XML**, zero-rated reason
(VATEX), **Reconnect / renew**, **Disconnect**.

**How it was checked:** the hash, signed properties and QR are identical to
ZATCA SDK 238-R3.4.8 outputs on its own sample invoices; the CSR has the
same structure as the SDK's; every document type (and 60 random invoices
with decimal quantities, discounts, zero-rated lines, rounding, credit
notes) passes an independent ZATCA validator (XSD + EN 16931 + all KSA
business rules + signature + QR + hash chain); the full connect → sign →
report / clear flow was run against a local Fatoora stand-in.
**Please test in Sandbox, then Simulation, before Production** — best on a test
database (Create New Database…), because signed bills are locked in every mode.

- New: `modules/zatca/phase2.py` (XML, hash, signing, QR, Fatoora API),
  `modules/zatca/egs.py` (connect, chain, queue), `ui/zatca.py`,
  `ui/zatca_sender.py`; database `database/zz_zatca2_patch.sql`
  (`zatca_egs` + ZATCA columns on sales_invoices / sales_returns).
  The old, incorrect Phase 2 code (api_client / signing / xml_generator)
  is removed. Sales ▸ Export XML now gives the real ZATCA XML.
- `DayBillERP.exe --selftest` also checks ZATCA Phase 2 signing.

## 🏷 v5.20.0 — Offers & Promotions + poster prompt

**Sales ▸ Offers & Promotions** (also Products ▸ 🏷 Make Offer, and the
Inventory ▸ Masters ▸ Schemes menu).

- **Deals:** −X % · ½ Half price · Special price per item · SAR off each
  item · **Buy X get Y** (1+1, 1+2, 2+1, 3+1 … the Y items free, half
  price or % off) · optional "only from qty N".
- **Products:** type a name / code, **scan a barcode**, or add a whole
  category. Special price: type each offer price, or *Fill* "10 % less".
- **When:** start + end date and time (quick: Today, 3 days, 1 week,
  Weekend, This month, No end), days of the week, happy hours
  (e.g. 16:00–20:00, may pass midnight). Use in POS and / or Sales invoice.
  Pause / Run, Copy, Delete. The list shows *Running now / Starts … /
  Ended / Paused* and how many bills + discount each offer gave.
- **Automatic at the till:** POS and the Sales invoice give the discount by
  themselves (green line with 🏷 −20 % / BUY 1 GET 1 FREE …). Buy-X-get-Y
  tells the cashier *"add 1 more, it is FREE"*. A price typed by hand
  replaces the offer on that line. A re-opened saved bill keeps the offer
  it was sold with. A returned item is refunded at the offer price.
- **The bill shows it:** each offer line prints *Offer: −20 %  −4.60*, and
  the receipt ends with **YOU SAVED 62.10 SAR / وفّرت 62.10 ريال**.
  The discount is saved on the bill line (offer_id / offer_text) and VAT
  is worked out on what the customer really pays.
- **🎨 Poster prompt:** one click builds a ready prompt (shop name EN/AR,
  headline, products with was / NOW prices, dates, footer) — choose
  size (A4 print, Instagram post, story, window banner, shelf tag),
  language (EN+AR / EN / AR) and style. **Copy**, or **Open ChatGPT**
  (prompt filled in) / **Open Gemini** (paste with Ctrl+V).
- New database tables: `offers`, `offer_items` (+ 2 columns on
  `sales_invoice_lines`) — `database/zz_offers_patch.sql`, added
  automatically at start-up and in INSTALL_DayBillERP_AllInOne.sql.

## 🔳 v5.19.1 — QR code missing on printed invoices

**Why it happened:** the ZATCA QR is built from the company VAT number
(Settings ▸ Company). When that number is empty, or not a real Saudi VAT
number (15 digits, starts and ends with 3), DayBill leaves the QR off —
a QR with a wrong VAT number fails the ZATCA scan — but it did this
**silently**. A new clean database (v5.19.0) starts with an EMPTY VAT
number, so its invoices had no QR. A number typed with spaces
(`300 123 456 700 003`) or Arabic digits (`٣٠٠…`) was also refused.

- **Fixed:** VAT numbers typed with spaces, dashes or Arabic digits now
  work — Settings ▸ Company saves them as 15 plain digits.
- **The app now says why** when a sales / POS invoice prints without the
  QR (once per run, and in the status bar every time):
  VAT number empty / wrong · Settings ▸ POS ▸ *Print QR Code* off ·
  Print & Invoice ▸ *ZATCA QR code* off · your own designer template has
  no QR box · dot-matrix printing (text only).
- **Settings ▸ Company ▸ Save** warns *"Saved — but no QR code yet"* when
  the VAT number is wrong (Saudi shops only).
- **Invoice Designer ▸ Preview** shows a red *NO QR – set company VAT
  number* box where the QR goes (never on a real customer print).
- Setup Checklist ▸ VAT now uses the same 15-digit rule.

## ✅ v5.19.0 — Final: clean installer, welcome window once, folding menu

- **Side bar pages fold under their headings.** SALES, PURCHASE,
  INVENTORY, ACCOUNTS, HR & PAYROLL, REPORTS, ADMINISTRATION show as
  headings only (▸). Click a heading to open its pages (▾); opening
  another heading folds the first one; click the open heading again to
  fold it. The whole menu fits on the screen with no scrolling.
  Opening a page from the dashboard or search opens its heading, and the
  heading you used last is open again at the next login.
- **"Welcome to DayBill ERP" opens only once** — on a brand-new
  installation whose company is still empty. Finish, Skip or ✕ all
  count; it never opens again at login, and never on a shop that is
  already set up. Help ▸ Setup Wizard still opens it any time.
- **One clean full SQL file for a new installation:**
  `INSTALL_DayBillERP_AllInOne.sql` — every table, view, procedure and
  index, plus only the starting data a new shop needs (admin user, roles,
  chart of accounts, default accounts, VAT S/Z/E/O, Cash Customer, Cash
  Supplier, Main Branch + Counter 1, numbering, print templates). No test
  company, VAT number or sample data. Every table / index / starting row
  is guarded, so running it again on an existing database is safe. At the
  end it prints a short check (tables, accounts, users, products).
  Arabic text in the starting data is stored as Unicode (N'…').

## 📒 v5.18.2 — Excel / Print fix in report screens

- **Fixed:** Account Ledger ▸ Excel / Print said *"not enough values to
  unpack (expected 2, got 1)"*. The same bug was in Aging ▸ Excel, Audit
  Log ▸ Excel and Financial Reports ▸ Excel. The export now accepts both
  kinds of summary line those screens send.
- Checked: every Excel / PDF / Print button in 36 screens was clicked
  and wrote its file with no error.

## 🖨️ v5.18.1 — Preview / Print with your own template in the exe

- **Fixed:** in DayBillERP.exe, Invoice Designer ▸ Preview / Print said
  *"No module named 'reportlab.graphics.barcode.code93'"*, and printing
  silently used the standard layout instead of your template. ReportLab
  loads its barcode types by name, and the old build left them out.
  DayBillERP.spec now bundles all of ReportLab.
- QR / barcode can never stop a page again: if ReportLab's QR is missing,
  the QR is drawn with the qrcode library instead.
- If your own template can't be used, printing now **tells you why**
  instead of quietly printing the standard layout.
- **BUILD_EXE.bat checks the new exe** (`DayBillERP.exe --selftest`):
  designer template A4 + 80 mm, QR, barcodes, Arabic, built-in invoice
  and receipt, Excel, Windows printing. Result in `dist\logs\selftest.log`.

## 🏗️ v5.18.0 — BUILD_EXE.bat works on every PC + Desktop icon

- **BUILD_EXE.bat rewritten:**
  - It runs from its own folder (Run as administrator / other drive no
    longer breaks it).
  - It has Windows line endings, finds Python by itself (`py -3.12/3.13/3.11…`
    or `python`) and installs with `python -m pip` / `python -m PyInstaller`,
    so it no longer fails with "pip / pyinstaller is not recognized".
  - It installs every library (pywin32 + pypdfium2 for printing too) and
    checks them.
  - It closes a running DayBillERP.exe and checks the exe was really made.
  - It makes a **"DayBill ERP" icon on the Desktop and in the Start menu**
    and refreshes the Windows icon cache.
  - Clear messages for every problem, and a full **build_log.txt**.
- **Icon fixed:** `assets\app.ico` now has proper bitmap sizes (16–128) and
  PNG 256. Windows showed a blank / default icon with the old one.
  `tools\make_icon.py` rebuilds it from `assets\app_icon.png`.
- **DayBillERP.spec:** works from any folder, bundles every DayBill screen,
  no UPX, and Windows "Details" (name, version). Your own config files are
  not copied into the exe.
- **The exe remembers its settings:** database settings, language and the
  product key are saved in `config\` next to DayBillERP.exe. Before, they
  went into a temp folder and were forgotten on every start.
- **The exe no longer closes silently** if it can't start: it shows the error
  and writes `logs\startup_error.log`.

## ↩ v5.17.0 — Returns in POS, ✕ per line, hold Ctrl

- **Return / take off in POS:** press **−** then scan (or tap the purple
  **↩ Return (−)** button, or type `-` + Enter in Barcode, then scan / tap /
  search).
  - Product **on the bill** → 1 taken off (the line goes at 0). Good for
    "please remove this one" in a 50-item bill.
  - Product **not on the bill** → a red **↩ RETURN** line (qty −1, money back).
    Buy 3 and return 1 in the same bill: the TOTAL is sale − return.
  - Save: sold lines → POS sales invoice; returned lines → **Sales Return
    (credit note)**, stock back in, VAT reversed, linked to the invoice.
  - Customer pays more → Cash / Card window for the difference (cash + card
    works). Customer gets money back → "Give back X SAR in CASH / by CARD?".
    A customer with an account → credit note on the account.
  - Cash drawer / bank move only by the money that really changed hands.
- **✕ on every bill line** (click = remove; also the Delete key). Can be
  turned off in ▤ Columns.
- **Keypad:** the number shows on the Qty / Rate key. Works both ways:
  *Qty → 5 → Enter*, or *5 → Qty*. After Rate it goes back to Qty. Clear
  wipes what was typed; Clear again goes back to Qty. With no line selected,
  it works on the last line. A RETURN line stays a return.
- **Hold Ctrl** (POS and every transaction window): box with each unit's
  **box qty**, sale, **purchase price**, profit and stock. Let go of Ctrl and it
  closes. Ctrl+C / Ctrl+V don't open it.
- **Status bar:** POS shows *Last bill no. = amount*, today's bills, and the
  user · database · financial year. The main window shows user · database ·
  year at the bottom. Sales / purchase / return windows show *Last invoice /
  purchase / return no. = amount* under the grid.
- Card refunds now come out of the same account card sales go into.

## 🛒 v5.16.1 — POS medium size

- POS is **Medium** size by default: fonts, buttons and rows are about 15%
  smaller. ⚙ ▸ POS Settings ▸ **Screen size: Small / Medium / Large**
  (Touchscreen mode always stays Large).
- The product **Search** box is slim now (normal text size, low height).
- POS not full screen: the window always fits the screen.

## 🛒 v5.16.0 — Old POS back, safe windows

- **POS:** the previous (v5.14) screen is back by request. It now has only
  **Cash** and **Card** buttons, and both open the **Cash + Card** window
  (mixed payment). There's a big **SAVE [F1]**, plus Save+Print, Delete Bill,
  Hold / Retrieve (shows how many are held) / New / 🖨 Last Bill.
  +, −, Remove Line, Edit Line (unit / qty / price window) and ▤ Columns are
  still there. Totals are packed so nothing is cut off on a 1366×768 screen.
- **Empty bill:** Save / Cash / Card with no products shows "No products in
  the bill" and the POS stays open.
- **Message boxes** now always open over the window you are working in, so
  an error never sends the POS / form behind the main window.
- **Closing windows:** the title-bar ✕ asks *Close this window? Yes / No*
  (big windows; small pickers close at once). POS warns when the bill
  isn't saved. Settings key `confirm_close_windows` turns it off.
- **Closing DayBill:** two questions (Close? → Are you sure?).
- **Sales / purchase product search:** the drop-down shows **8 products**
  (scroll for more), with a Code column. Row height follows Windows
  display scaling, so it no longer shows only 2.

## 🔑 v5.15.1 — Easy activation

- Help ▸ 🔑 Product Key has **one box**: type the licence code (like
  `K7QF-2MXR-9TPL`) and press **Activate**. A full DB1-… key pasted in the
  same box activates offline.
- The DayBill licence server is built in, so the customer types no server
  link. It can still be changed under ⚙ Server.
- **Fixed:** "getaddrinfo failed" when Windows can't find the server name
  but Chrome can. DayBill now asks Google / Cloudflare DNS for the address and
  connects securely.
- The window doesn't freeze while it connects. Errors show in red inside the
  window with a clear message.
- **WhatsApp** button sends the Installation ID to your dealer.
- Trial PCs don't call the server in the background.

## 🛒 v5.15.0 — New POS screen (1366×768)

- **New look** that fits a 1366×768 screen: navy top bar, customer strip,
  white bill grid, quick-product tiles, totals + PAID / BALANCE / CHANGE,
  keypad.
- **Only Cash and Card** buttons, and a **big Save (F1)** with Save + Print (F2).
- **Tap Cash or Card** to open a payment window with a number pad and
  **Cash + Card fields**. Example: total 40, type 20 in Cash and Card fills
  20 by itself. Change is shown, and quick cash buttons are 10 / 20 / 50 / 100…
  Accounts: cash goes to the Cash account, card goes to the Bank account.
  If a real customer is chosen, any rest stays on their account.
- **+ / −** quantity buttons. **Double-click a line** to change its **unit**
  (Piece / Box / Carton, each with its own price), quantity and price.
  The window also shows stock in that unit and a live line total.
- Bottom bar: **big Hold (F6)** and **Retrieve (F7)** (shows how many are held),
  **Clear (F3)**, **🖨 Last bill**, **Delete bill**, and today's bills.
- **▤ Columns** button: tick which columns the bill grid shows
  (#, Code, Item, Arabic name, Qty, Unit, Rate, VAT, Amount).
- Reports (POS Summary, daily sales) split a cash + card bill correctly.
- New database patch `zz_pos_split_patch.sql` (runs by itself).

## 🧾 v5.14.0 — Excel grids, big POS search, invoice designer columns

- **Fixed:** saving a customer showed "cannot access local variable
  'messagebox'…" (the customer WAS saved, but the window stayed open — a
  second Save made a duplicate). Same risky pattern removed from suppliers,
  inventory and products.
- **Excel-style cell lines** in every transaction grid: sales invoice,
  purchase, sales / purchase returns, quotation, purchase order, POS cart,
  journal voucher. Light-blue selected row.
- **POS:** the product search box takes all the free width of the top bar
  (Customer moved to a slim strip below). Results are a table: Code ·
  Product · Arabic name · Unit · Stock · Purchase price · Sales price;
  out of stock in red, low stock in orange. Settings ▸ POS ▸ "Show purchase
  price in the product search list" hides the cost from cashiers.
- **Invoice Designer:**
  - Every item column is its own element (No., Code, Barcode, Item,
    Item Arabic, Qty, Unit, Price, Discount, Amount, VAT %, VAT, Total):
    drag sideways to move, drag the ◢ corner to resize (the next columns
    move along, like Excel), English + Arabic header text, align, font,
    bold, cell borders, striped rows, "Fit columns to the table width".
  - Item column prints the **English name on the first line and the
    Arabic name on the second line**.
  - Old one-block tables print the new way too; "✂ Split into separate
    columns" turns them into columns in the designer.
  - Signatures / stamp drawn low on the page stay at the page bottom; totals,
    QR and words follow the items (per element: Auto / Moves with items /
    Stays at the bottom). Long lists continue on the next page.
  - **💾 Save to file / 📂 Open file** — keep a design on your PC (or a USB)
    and use it on another PC or database.
  - **⇄ Copy to…** — the same design for Sales Return, Quotation, Purchase …
    (can be made the default there; the title changes to that document).
  - Printed bills now fill the Barcode column from the product.

## ✨ v5.13.0 — Product AI

Products window:
- **✨ Translate to Arabic** (#9) — English name → Arabic name. Offline
  grocery dictionary at once (حليب المراعي طازج 1 لتر); with an AI key the
  online AI gives a proper shelf-label translation. The Arabic name is
  filled automatically when it is empty.
- **⚠ Duplicate finder** (#3) — while typing a new product: "Looks like an
  existing product: P10 Almarai Fresh Milk 2L" (same barcode, or the same
  name even when spelled differently — "2 Litre" = "2L"; a different size is
  not a duplicate). Asks again before saving.
- **💡 Auto-fill** (#4) — new product: category, VAT, unit, Box = 12 and
  brand copied from the most similar products (✓ Apply).
- **🧹 Clean-up** (#13, toolbar) — checks all products: price 10× too high /
  low, selling below cost, price 0, VAT different from its category,
  duplicates, same barcode on two products, no barcode, missing Arabic name,
  no category; ✨ spelling check with AI. Tick and **Fix selected** — nothing
  changes until you approve.
- **🧾 Supplier Invoice (AI)** (#11, toolbar) — choose the supplier's PDF or
  a photo: AI reads supplier, invoice no., date and every line; lines are
  matched to your products (barcode, then name); new items become products
  (Arabic name, category, VAT, PCs + Box/Carton unit, selling price =
  cost + 25 %), then a Purchase Invoice opens filled in — check and Save.

Settings ▸ ✨ AI: paste a Claude API key (console.anthropic.com), "Save &
test". Duplicate finder, auto-fill and clean-up work without internet or a
key. Only product names / the chosen invoice file are sent to the AI.

## 📄 v5.12.2 — A4 PDF: bottom block sits on the footer

- A4 sales / POS invoice: totals, QR, amount in words, payment, bank,
  terms and signatures are placed at the BOTTOM of the page just above
  the footer (not floating under the items).
- Long invoices fill each page; the last page always carries a few item
  lines together with the totals (never a totals-only page).
- Purchase, returns, quotations, purchase orders: totals + notes sit just
  above the signature lines; page 2+ repeats the column header and shows
  "Page n". (Before, a long purchase could print totals over the
  signatures.)

## ✅ v5.12.1 — ZATCA Phase 1 QR verified

- Every printed sales invoice / POS bill carries the Phase 1 QR (TLV tags
  1-5: seller name, VAT number, date-time, total incl. VAT, VAT), built from
  the SAVED invoice at print time — so it always matches the printed bill,
  also after an edit and for old / imported invoices. A Phase 2 (signed) QR
  is used instead when the invoice has one.
- Fixed: 80mm receipts had the QR drawn below the paper edge (fixed page
  height) — the receipt is now exactly as long as its content, any number
  of lines.
- Title: "SIMPLIFIED TAX INVOICE / فاتورة ضريبية مبسطة" for B2C bills,
  "TAX INVOICE / فاتورة ضريبية" when the customer has a VAT number
  (Arabic now prints correctly on the receipt).
- No QR is printed when the company VAT number is missing or not a valid
  15-digit Saudi number (was a fake number before). Set it in Company
  Settings.
- Tested by scanning the printed PDFs (A4, 80mm, designer templates A4 /
  80mm, 30-line bill, edited bill, old bill): 93/93.

## 🏬 v5.12 — Many counters (tills), branches, product key

**Counters.** One SQL Server database on the shop LAN, one shared stock, many
billing / POS PCs.
- Administration ▸ **Branches & Counters**: add counters (C1, C2 …) and
  branches. On each PC press **🖥 Use on THIS PC** — or pick it in the
  "Which counter is this PC?" box that shows once on a new PC.
- The top bar shows this PC's branch · counter (click to change).
- Every new sale, POS bill, return, purchase, receipt / payment and expense
  is stamped with the counter. An edit made at another counter keeps the
  original counter. Old data goes to Counter 1.
- **Day Close**: pick a counter to see that drawer's bills, cash, card,
  refunds, paid-out and **expected cash in THIS drawer** ("All counters" =
  whole shop, as before).
- Reports ▸ Sales ▸ **Counter & Branch-wise Sales**.
- Branches are ready for later (the branch table and the reports already
  group by branch; stock is still one shared stock).
- ZATCA Phase 2: each counter that sends invoices needs its own EGS
  onboarding (CSID) when you go live with Phase 2.

**Product key.**
- First start: **30-day free trial** (full app; 1 branch, 2 counters).
- After the trial, or when a key expires / is blocked, DayBill is
  **read-only**: everything opens, prints and exports, but nothing new is
  saved. Users / Settings still work so the key can be entered.
- Help ▸ **🔑 Product Key**: copy the **Installation ID**, send it to your
  dealer, paste the key he sends, press Activate. One key per database — all
  counter PCs share it. The key sets the number of branches / counters and
  the expiry date.
- Optional online: enter the dealer's licence server and the order code,
  press **Activate online**. The app checks the server every few days (no
  internet = keeps working); the dealer can renew, add counters or block.
- The app holds only the PUBLIC key — keys can't be made from the app.

## ✏ v5.11 — Edit/delete saved bills, assets with VAT, Smart Insights

- **Edit or delete CONFIRMED documents** — sales invoices / POS bills,
  purchases, sales & purchase returns (new ✏ Edit in the Returns list),
  manual vouchers (✏ Edit in Vouchers) and expenses (✏ Edit / double-click).
  On save the old stock + account entries are reversed and the new ones
  posted; delete puts the stock back, removes the entries and turns money
  received / paid on it into an advance. Blocked when the bill was already
  reported to ZATCA (make a Sales Return), when its date is in a closed
  financial year, or when Settings ▸ Sales ▸ "Allow edit / delete of
  confirmed documents" is off. Every delete is in the Audit Log.
- **Expenses & Assets**: 🪑 New Asset (shop furniture, equipment,
  computers, vehicles) → Fixed Assets account, input VAT into the VAT
  Return, not in Profit & Loss. VAT rate 15 / 5 / 0 / No VAT, "amount
  includes VAT" tick (VAT worked out for you), supplier + invoice number,
  cash / bank / card or on credit. Run `database\expense_vat_patch.sql`
  (automatic on start).
- **Balance Sheet** (Reports and Accounting tab): Current assets, Fixed
  assets, Liabilities with VAT netted into one line, Equity + profit to
  date, customers / suppliers rolled into Receivable / Payable, balance check.
- **Products**: History ▸ Stock shows every stock movement (item ledger);
  Sales / Purchase history show the status; stock no longer shows as
  "1.23e+05"; the form always shows its VAT and category.
- **Multi-unit barcodes**: scanning a Box / Carton barcode in Sales,
  Purchase, Return and Quotation now picks that unit and its price (it
  only worked in POS before).
- **Weighing scale**: each scale label is its own line (two packs of meat
  = two lines); price-labels ring up EXACTLY the printed amount; the
  PLU Manager formats now match what the scanner reads.
- **Re-opening a saved invoice never changes its total**, and money taken
  at the till is kept apart from later receipts (no double posting).
- **🤖 Smart Insights** (Reports ▸ Smart Insights, and a card on the
  Dashboard): what to reorder and how much (with one-click draft Purchase
  Orders per supplier), items not selling, items priced below cost, week
  vs week trends, busiest day / hour, and things to check today.
  Works offline on your own data.
- **App icon**: the DayBill logo on every window, the taskbar and the .exe.

## 🪟 v5.10 — New Windows 10/11 look (UI only)

- **New colours**: navy side menu, blue buttons, light-grey page, white
  windows. The old purple look is still in Settings ▸ System ▸ Theme
  ("purple").
- **Side menu**: DayBill ERP logo block, section names, the open screen
  shows as a blue bar, mouse wheel scrolls the menu.
- **Top bar**: 🔍 *Search anything…* (**Ctrl+K**) — type a screen or report
  name (e.g. "trial", "customer") and press Enter; 🔔 alerts with a count
  (low stock + invoices due); user name / role menu (Settings, Log out).
- **Windows**: white title bar with icon, real Windows — ☐ ✕ buttons, a
  thin frame; taskbar at the bottom with a blue line under the active
  window (names shorten when many are open).
- **Dashboard**: coloured tiles (blue / green / orange / purple).
- **Tables**: light-grey headings, blue selected row. **Fields**: flat
  with a thin grey border, blue when typing.
- **Dialogs**: white header with a dark title (no more coloured band),
  always open inside the screen — never behind the Windows taskbar. Big
  forms (sales / purchase / return / quotation) open **maximized** on
  small screens (1366×768).
- **Invoice / Purchase / Return / Quotation forms**: colour action
  buttons with the key on top (F9 Save Draft, F10 Print / Save & Confirm,
  Hold, Teller, Esc Cancel) and a blue TOTAL box.
- **Pages** keep their buttons on screen: on a small monitor the table
  gets shorter, the button bar never gets cut.
- **Invoice Designer** now fits the screen: opens at *Fit Page* (whole A4
  page visible), page scrolls when you zoom in, Properties panel scrolls,
  white toolbar. Same for the Barcode / Label Designer.

## 🖨 v5.9 — Printing, Invoice Designer, Chart of Accounts

- **Every document prints three ways** — sales invoice, POS bill, sales
  return, purchase, purchase return, quotation, purchase order, receipt,
  payment (form and list): **🖨 Print** (default layout, F10) ·
  **Dot-matrix** (F11) · **PDF** (F12, saved in Documents\DayBill PDF and
  opened). The same menu has **Print to…** (choose printer) and **Print
  previous** (reprint the last one).
- **Default printer switch** — Settings ▸ Printing / Printer Management:
  "Print on the default printer without asking". Untick it and a small
  box asks for the printer and copies each time.
- PDFs print straight to the printer without a PDF reader when
  `pypdfium2` is installed (install_requirements.py adds it).
- **Invoice Designer** (System ▸ Invoice Designer): pick the document,
  ＋ New → name, paper (A4 / 80 mm), "start with the ready layout".
  ★ Set Default = used by 🖨 Print. Preview / Print / PDF use your latest
  real document. "Use the default printer" tick per template. Long
  invoices continue on the next page; totals follow the table.
- **Label Designer**: ＋ New with label sizes (roll or A4 sticker sheet),
  name · price · barcode placed to fit, sheet columns / rows, 🖨 Test Print
  and 🖨 Print Labels.
- **Chart of accounts**: standard Saudi retail accounts added (fixed
  assets, capital, drawings, retained earnings, 3400 Opening Balance
  Equity, other income, water, internet, maintenance, bank charges,
  government fees, …) and every account sits under its group. Customer /
  supplier opening balances and new-product opening stock now post to the
  books, so Trial Balance and Customer Balances include them.
- Removed files the app no longer used (old template designer, old print
  dialog, fluent invoice window, quick product form, old schema SQL,
  sample-products SQL). "Create New Database…" now builds the new
  company's tables inside that database.

## 🧩 v5.8 — Payments, Quotations, WhatsApp, Price Labels, Settings

- **Receipts / payments settle invoices**: tick the invoices (or ⚡ Auto,
  oldest first), type a part amount with double-click; the rest stays as an
  advance. Invoice lists show 💰 Receive / 💰 Pay Supplier.
- **Sales Quotation** and **Purchase Order** (Inventory ▸ Transactions):
  print, WhatsApp, and one click to turn them into an invoice.
- **WhatsApp** (Settings ▸ WhatsApp): free via the WhatsApp app (you press
  Send) or automatic with the Cloud API. Buttons on invoices, quotations,
  POs, receipts, statements and Day Close.
- **Price Change Labels** (Inventory ▸ Labels): every price change or new
  product is listed until its shelf label is printed.
- **Windows-style behaviour everywhere**: dialogs open centred and grow to
  fit their fields (Save/Cancel never cut off on small screens), mouse wheel
  scrolls what is under the pointer, right-click Cut/Copy/Paste, Ctrl+A,
  Ctrl+C copies a table, right-click a table ▸ Export to Excel, Enter opens
  the selected row, Home/End.
- **Settings**: every option shown now works (unused ones were removed).
  New: printed date/time format, financial-year start for "This year",
  default VAT rate for new products, POS touchscreen mode and product
  pictures, PLU file export for the scale, password expiry, start-up alerts
  (low stock, invoices due), backup messages, auto-print receipts.

---
