# DayBill ERP  v8.3.0

Billing, POS, inventory, accounts and HR for shops in 🇸🇦 Saudi Arabia, 🇦🇪 the UAE and 🇮🇳 India.
**VAT / GST by country · ZATCA Phase 1 & 2 · Arabic & English · Microsoft SQL Server · Windows**

## ⚡ v8.3.0 — Quick Product Entry (many products, one line each)

A new, fast way to add products — **Inventory ▸ Masters ▸ ⚡ Quick Product
Entry**, the side menu (Inventory ▸ ⚡ Quick Product Entry), or the
**⚡ Quick Entry** button on the Products page. The full Product window
(＋ New) is unchanged.

- **The top line is the new product**: Code (automatic, next free code) ·
  **Product Name** · **Unit** · **Category** · **Purchase Price** ·
  **Sales Price**.
- **Enter goes to the next box.** On Unit and Category, typing the start is
  enough (`bo` → Box); a category that does not exist yet is added.
- **Enter on Sales Price** asks *"Save this product?"* — **Yes is the
  default**, so Enter again saves. The product appears at the top of the
  list (green), and the cursor is back on Product Name for the next line.
  Unit and Category stay as they were, for a row of similar products.
- It warns (still lets you save) when the sales price is below the purchase
  price or the same name already exists. The margin % shows while you type.
- **The list**: *All products* (newest first) or *New only* — a blank list
  that fills line by line with what you add here. Search box above it.
- **Change a product**: Enter or double-click a row → it loads into the top
  line (button says *Update*); Enter through to Sales Price → Yes → updated
  (name, unit, category, purchase and sales price; the base unit too).
- Esc clears the line, Ctrl+S saves, ↓ from Product Name goes to the list.
- New products are saved exactly like the Excel import: next code, system
  barcode, base unit, VAT 15 % (standard), stock tracking on, listed in sales
  and purchase, price history. Rights: *Products ▸ Add* to add, *Edit* to
  change.

## 🎨 v8.2.0 — DayBill 8 design in every window

The Figma file ([DayBill ERP — Redesign v8](https://www.figma.com/design/bnHMQhG6oq5TAqa0ddEkYn) ▸ Screens)
now has a template for each kind of window — **Master form** (Product),
**Report** (Sales Register), **Entry** (Receipt Voucher) and **List**
(Customers) — next to Dashboard, Sales Invoice, POS and Login. Every window
in the app follows them:

- **Old colours gone everywhere**: the purple brand, the flat teal / green /
  orange buttons and the old greys left in 42 more screens now use the
  DayBill 8 colours (155 places). Print designs (barcode labels, report
  designer, print settings) keep their own colours.
- **One main button per window**: action buttons follow the Figma roles —
  the main action (Save, Save & Confirm) is the blue button, Delete is red,
  everything else (Save Draft, Save & New, Save & Print, Print, Cancel …) is
  white with a border. Master forms (Product, Customer, Supplier) and all
  transaction windows (Purchase, Returns, Quotations / Orders, vouchers …).
- **Report and list tools**: Excel, PDF, Print, Export, Import, Refresh,
  Filter, Columns … are white buttons everywhere; the page's own Run / Show /
  New button stays blue.
- **Purchase, Sales / Purchase Return, Quotation, Sales / Purchase Order**:
  the header fields, the item grid and the totals sit in white cards on the
  grey page, like the Sales Invoice.
- **Group boxes** (Tk LabelFrames) have a thin light border and grey bold
  titles instead of the 3-D groove.
- **Tables** everywhere: alternate rows in the light heading grey (#F7F9FC).
- **Buttons** are a little taller (Figma button height) and bold.
- Window title bands of every pop-up and form are white with dark text (as
  before, now with the new colours).

Checked: all 73 list / report pages and 33 entry forms open without errors
(test run with no database).

## 🎨 v8.1.0 — Sales Invoice and POS in the DayBill 8 design

Matches the Sales Invoice and POS screens in Figma
([DayBill ERP — Redesign v8](https://www.figma.com/design/bnHMQhG6oq5TAqa0ddEkYn) ▸ Screens).

**Sales Invoice**
- White window header: icon, title, a short hint line and the bill number as a
  blue pill (was a solid blue band). Compact mode leaves it as it is.
- The header fields, item grid and totals sit in white cards on the grey page.
- Toolbar: quiet bordered buttons; **Save** is the one blue button; Delete
  and Close are red.
- Fields are flat white boxes with a light border and a blue ring on focus.
- Header block titles (BILL · CUSTOMER · …) in grey CAPS, more spacing — also
  on Purchase and Returns (shared header).
- Item grid: 32 px rows, grey headings.
- Bottom buttons: Teller, Hold, Save Draft, Print ▾ and Cancel are white with
  a border; **Save & Confirm** is the blue button. Same keys as before.

**POS**
- Light screen instead of the dark teal one: white top bar and customer strip,
  grey page, white bill card.
- Barcode / search / customer fields are bordered white boxes; Bill No sits in
  a light-blue panel.
- Category tabs are pills (the open one blue); quick-product tiles are light
  green / amber / red by stock, with dark text.
- Bill table: grey headings, light-blue selected row, thin lines.
- TOTAL in a navy box; totals in a white panel.
- Keypad and action keys are white with a border; Qty / Rate light blue when
  active; Cash green, Card blue, Enter navy; SAVE green, Save+Print blue,
  Shift purple, Delete Bill light red. Same keys and shortcuts as before.
- Pop-ups (product details, unit / price, payment, held sales) use the same
  navy and blue colours.

## 🎨 v8.0.0 — DayBill 8: new look for the whole app

Designed in Figma first — **[DayBill ERP — Redesign v8](https://www.figma.com/design/bnHMQhG6oq5TAqa0ddEkYn)**
(colour tokens, text styles, components, and the Dashboard, Sales Invoice, POS
and Login screens) — then built into the app.

- **New default theme "DayBill 8"**: ink-navy side menu, indigo-blue accent
  (#2952E3), soft grey page (#F4F6FA), white cards with a thin border, darker
  slate text. Every screen picks it up.
- **The v7 look is still there**: Settings ▸ System ▸ Theme ▸ **DayBill Blue (v7)**.
- **Dashboard KPI cards redesigned**: white card, short coloured accent bar,
  CAPS title, big value, soft square icon.
- **Tables**: rows 32 px high, muted CAPS-style headings on a lighter header.
- **Buttons and fields**: roomier padding (16 × 8); new white **Secondary**
  button style with a border; Ghost buttons turn blue on hover.
- **Top bar 52 px** and taskbar 34 px, like the Figma shell.
- Colours that were written straight into 31 screens now use the new palette.

## 🩹 v7.21.2 — fix: Save & Print on a new product

- **Fixed: "bad window path name … mdichild.!frame3"** in Print Barcode after
  saving a new product with Save & Print (also Multi Barcode and Save & New):
  the product list refreshes on Save and rebuilds the window the form came
  from — the barcode window now opens on the main window.

## 🩹 v7.21.1 — fix: saving a new product

- **Fixed: "Cannot insert the value NULL into column 'product_id'"** when a
  new product was saved (v7.20 had moved the line that reads the new
  product's number under the "Show details after save" option).
- Checked every v7.19–v7.21 change again: the Sales Invoice print question
  now uses the bill number shown on screen; all 25 Settings pages open and
  save.

## ⌨ v7.21.0 — the item grid works like Polosys

- **Enter goes like Polosys**: Bar Code → (product found) **Qty → Rate →
  Unit Price → next line**. Disc %, Disc, Gross and Total start 🔒 read only —
  untick them in Grid design and Enter stops there too.
- **Typing in a cell like Polosys**: the cell itself becomes the box — same
  size, same font (Qty bold 12) and alignment, light-yellow with a blue edge,
  the value selected so typing replaces it.
- **No more squeezed columns**: Product is never narrower than 180 px and Bar
  Code 90 px (a saved width of 20 is put right); when the columns are wider
  than the window a **horizontal scroll bar** appears and the totals line
  scrolls with it. Grid design ▸ Reset gives the normal widths back.
- Fixed: "bad cursor spec ('size_we',)" error pop-ups when the mouse was on a
  column edge (they broke typing in the grid).

## ⚙ v7.20.0 — Bill settings panel, Polosys look, new Settings page

- **⚙ Settings on the Sales Invoice** opens a small panel of ticks (like
  Polosys) instead of the big Settings page: Qty after barcode, Duplication
  message, Ask before removing an item, Block zero figure entry, Allow price /
  discount edit, Barcode mandatory, stock / cost in the search, last prices
  box, below-cost warning · Initial focus to customer, Not set default
  customer, Hold salesman, Set default Cash Received, Enable transaction date,
  Round off, Print after save, Show print confirmation, Allow negative stock ·
  Qty decimal point. ✔ Apply saves them (Settings right). They are also on
  Settings ▸ Sales & POS ▸ **Bill entry**.
- **The bill grid looks like Polosys**: light-blue alternate rows, Qty bold
  size 12, Rate red, Profit bold blue, the totals line in red italic. Change
  it in Grid design; Reset brings this look back.
- **Grid design from anywhere in a table**: right-click any cell of a list,
  report or entry grid (a payment / receipt / journal grid shows only its own
  columns — account, party, amount …), the bill's row menu ▸ Grid design, or
  **Ctrl+Shift+G** — besides double-clicking the top-left corner.
- **New reports** (Accounts ▸ Reports): **Bank Flow** (bank / card accounts
  day by day) and **Daily Account Statement** (one account day by day).
- **Product window options** (Settings ▸ Products & Barcodes ▸ Product form):
  names in CAPITALS, details after Save, Markup % → sales price, purchase
  price with VAT.
- **Settings page redesigned**: a clear side menu (groups, the open page
  marked, ↑ ↓ keys), each page with its own header, options in two cards —
  **Values** and **Switches** (click anywhere on a row, or Space, to turn it
  on / off; On / Off shown), search highlights what matched and counts it,
  "● Unsaved changes" next to Save, Ctrl+F finds a setting.

## ▦ v7.19.0 — Grid design like Polosys

- **Double-click the top-left corner** of any grid (the **#** heading on a
  bill) to open **Grid design** — in sales, purchase, returns, orders **and
  every report and list**. Right-click a heading ▸ Grid design still works.
- One row per column, like Polosys: **Visible · Header text · Width · Align ·
  🔒 Read only · Bold · Colour · Size · ▲▼ order**. The table: font, size,
  bold, row height and the 6 colours (alternate rows, header back / text,
  grid lines, back, text).
- **Bold / Colour / Size per column** (e.g. Qty size 12, Rate red, Total bold)
  — in bills and reports. Right-click the Colour box = back to normal.
- **🔒 Read only decides where Enter goes**: Enter stops at every column that
  is shown and not read only, in the order on screen — Qty → Rate → Disc % →
  Disc → Unit Price → next line. Tick Read only (or hide the column) and Enter
  skips it. Move a column with ▲▼ and Enter follows the new order.
- **Gross and Total** start read only. Untick them and you can type the line
  value — the **Rate is worked out** (the line discount stays). A rate has 2
  decimals, so DayBill tells you when the total comes out a little different.

## 🏷 v7.18.3 — Barcode Print extras, designer item order

- **Barcode Print**: a row of extras for the whole list — **Pack date**,
  **Expiry** (a date, or +30 = 30 days after the pack date), **Note 1–4** —
  and **Print labels # … to …** to re-print part of the list. The Label
  Designer has the new fields Pack Date, Note 1–4 and Item alias name.
- **Invoice Designer ▸ Item order on the print**: as entered · by code · by
  name · group-wise (category, then name).

## ✨ v7.18.2 — no flicker after Save

- After **Save** the next blank entry is built behind the saved one and takes
  its place in one step — same size, same place, the cursor ready. The screen
  no longer flashes (sales, purchase, returns, vouchers, entries).

## 💬 v7.18.1 — quieter pop-ups

- **Saved / Confirmed** shows as a small green note at the bottom-right that
  goes away by itself — no OK to press (sales, purchase, returns, vouchers,
  stock journal, expenses, packing slips).
- The **last prices** of a product: one small strip at the bottom-right of
  the bill (last 3 purchases · last 3 sales) instead of two big boxes over the
  grid. It is not on top of other programs and closes by itself after 7 s,
  with Esc or ✕. Settings ▸ Sales ▸ "Show last prices box" turns it off.
- Sales Invoice remembers the **Print After Save** tick.

## 🔑 v7.18.0 — Authorisation, Branch Transfer Out / In, Bookings

- **🔑 Authorisation** (Settings ▸ Users & Security): a manager's user name +
  password is asked on **Save & Confirm** of a sale when the bill is above a
  total, a discount is above a %, or an item is sold below cost. Users whose
  type has **Sales ▸ Approve** are not asked. Each approval goes in the Audit
  Log (who asked, who approved, why).
- **🚚 Branch Transfer Out / In** (Inventory ▸ Transactions): tick **Two steps**
  — the goods leave the branch now and wait *in transit* until the other
  branch presses **📥 Received**. Reports ▸ Inventory ▸ **Goods in Transit**.
- **💰 Booking**: the Sales Order window has **💰 Advance** — the customer's
  advance as a receipt on his account (it settles the bill later).
  Reports ▸ Sales Analysis ▸ **Bookings & Advances**. Sales Estimate =
  Quotation (Inventory ▸ Transactions).
- No database change.

## 🔧 v7.17.1 — fixes found on the shop PC

- Packing Slip list: ＋ New always shows (the page heading no longer takes its room).
- Ctrl+N works on the Packing Slip, Load Request and Reminders pages.
- A page opened from the menu while a bill is open comes to the front.
- ◀ ▶ hand the keyboard (Esc …) to the window they open.

## 🔐 v7.17.0 — User rights, date rules, label tools, grid tool

- **Users & Rights ▸ User Rights**: rights in groups (Sales · Purchase ·
  Inventory · Accounts · HR · System) — each group has **tick / clear this
  group**; a grey line under a right says which screens it covers.
- **Settings ▸ Financial Year**: *Allow back-dated documents* and *Allow
  post-dated documents*, each with a day limit (0 = no limit). Users with
  full access are never limited.
- **Print Barcode Labels**: **📄 From a bill…** (purchase / sales invoice,
  purchase order, sales return, stock journal entry — one label per piece in
  its unit), **🔢 List / range…** (1001, 1005, 2001-2020), **Start at label #**
  (skip the used labels of a half-used A4 sheet).
- **Item grid** (sales, purchase, returns, quotations): right-click a line —
  ➕ insert a line above (**Insert**), ⧉ duplicate (**Ctrl+Shift+D**), ▲ ▼ move
  (**Alt+↑ / Alt+↓**), ✕ remove, ⤓ last line. The Sales Invoice tool bar has
  ➕ Insert Line, and its ❌ Close asks first when lines are unsaved.
- **System menu**: User Types & Rights, Branches & Counters, Financial Year,
  Exchange Rates, Headers & Footers.
- No database change.

## 📊 v7.16.0 — Cost centre on every document, 12 more reports

- **🎯 Cost centre** box on the Sales Invoice (Details), Purchase Invoice and
  Expense windows too — every journal line they post carries it, also after
  an edit. Reports ▸ Accounts & VAT ▸ Cost Centre Report.
- **New reports**
  - Inventory: Product List (Price List) · Item-wise Summary (every movement
    per item: purchase, sale, returns, opening, transfers, damage, excess,
    shortage, own use) · Inventory Transaction Summary · Daily Stock Balance
  - Sales Analysis: Net Sales (day by day) · Sales & Sales Return Register ·
    Sales Order Summary · Sales Quotation Summary · Day-wise Sales with Profit
  - Purchases: Purchase Order Summary
  - Accounts & VAT: Income Report · Cash Summary (day × kind of entry)
- Database: `database/patches/zzzz_v7160_cost_centre_docs_patch.sql` — runs by itself.

## ◀ ▶ v7.15.0 — Browse documents, cost centres

- **◀ ▶** on the tool bar of every transaction window (Sales Invoice, Purchase,
  returns, Receipt / Payment, Journal vouchers, Consumable Entry, Stock
  Journal) and **Ctrl+PgUp / Ctrl+PgDn**: the previous / next document of the
  same kind opens in its place. In a new (empty) window ◀ opens the newest one.
- **🎯 Cost centre** box on Receipt / Payment / Contra / Journal vouchers
  (Masters ▸ Cost Centres) and **Reports ▸ Accounts & VAT ▸ Cost Centre
  Report** — income and expenses of each cost centre, account by account.
- Database: `database/patches/zzzz_v7150_cost_centre_patch.sql` — runs by itself.

## 🪟 v7.14.0 — Windows like a desktop ERP

- **Window size**: pages open at their own size (not full screen), centred,
  each next one a step down-right. Move or resize a window (drag the ◢
  corner) and it opens the same way next time. Double-click the title =
  full size / back. **Windows ▸ Open windows full size** = the old way.
  Dashboard and POS always open full size.
- **Title bar**: the window in front has a blue line and blue title; the
  others are grey.
- **Transaction windows** (sales, purchase, returns, vouchers, stock
  journal …) open inside the work area, stay in front of DayBill, and are
  listed in the Windows menu. **Close All** closes them too — a window with
  unsaved lines asks first.
- **One tool bar** in every transaction window, under the title:
  💾 Save · ✏ Edit · 🗑 Delete · ➕ New · 🖨 Print · 📄 Voucher · 📥 Import /
  Load · ✖ Close.
- **⭐ Favourites bar**: ☰ folds the side bar into a narrow bar — every
  favourite with its icon and name (right-click to remove / move), 📂 Menu
  (all pages), 🔍 Search, 🔒 Lock, Exit. **Ctrl+B** hides / shows the side bar.
- **Windows menu**: Cascade, Tile Vertically / Horizontally, Maximize All,
  Minimize All, Close All, Side bar, Tool Bar, Reset window sizes, Counter
  Change, Change Password, Lock — and the open windows (✓ = in front).
- **Status line** (bottom right): user · database · year · branch / counter
  · date and time.
- No database change.

## 🔗 v7.13.0 — Delivery note → invoice, card commission

- **Packing Slip ▸ 🧾 Make Invoice** — opens a Sales Invoice with the slip's
  customer and items (the packed quantity). When the invoice is saved, the
  slip shows the invoice number and turns **Delivered**; Reports ▸ Delivery
  Notes not Invoiced drops it.
- **Load Request ▸ ✔ All loaded** — every line loaded in full in one click.
- **Reports ▸ Accounts & VAT ▸ Card Sales & Bank Commission** — money into
  each bank card / card machine account (Accounts ▸ Masters) and the bank's
  commission on it.
- No database change.

## 📦 v7.12.0 — Delivery notes, load requests, export, 19 reports, system tools

- **Sales ▸ 📦 Packing Slips / Delivery** — what was packed and delivered
  (PS-202611-000001): customer, vehicle, driver, packages, a remark per line.
  Type a Sales Invoice or Sales Order number and press **📂 Load** to bring
  its items. No stock moves, no accounts — the invoice does that.
- **Inventory ▸ 🚚 Item Load Requests** (LR-…) — salesman, route, vehicle,
  needed-by date; double-click a line for the loaded quantity.
- **Sales Export** — Inventory ▸ Transactions ▸ Sales Export, or tick
  **Export 0% VAT** on the Sales Invoice: every line Z / 0 % with the ZATCA
  reason *VATEX-SA-32 Export of goods*.
- **Purchase Return ▸ 📥 Import items** from Excel / CSV (Code or Barcode,
  Qty, optional Rate).
- **19 new reports** (Reports ▸ Sales Analysis, Purchases, Accounts & VAT):
  salesman sales & collection, salesman incentive, route / brand / section /
  party-category sales, party month-wise sales & purchases, customer visits,
  offer sales, pending sales / purchase orders, credit purchase summary,
  month-wise ledger, income & expense, transaction analysis, daily cash &
  bank, delivery notes not invoiced, load requests.
- **System**: 🔒 Lock Screen (Ctrl+Shift+L), Change Counter, ⏰ Reminders
  (shown when you sign in), 💬 Message Templates (the WhatsApp window has a
  Template box), 💳 Bank Cards and Card Machines (Accounts ▸ Masters),
  🧹 Delete Inactive Transactions (old drafts and cancelled documents only —
  type DELETE to confirm).
- **Windows**: Tile Vertically / Horizontally, Cascade, Maximize All, Close All.
- Database: `database/patches/zzzz_v7120_polosys_rest_patch.sql` — runs by itself.

## 📒 v7.11.0 — Stock Journal: Damage, Excess, Shortage

- **Inventory ▸ 📒 Stock Journal** (or Inventory ▸ Transactions ▸ Stock
  Journal in the top menu): **Damage Entry**, **Excess Stock (add)** and
  **Shortage Stock (less)** — each its own numbered document
  (DMG-202611-000001, EXS-…, SHT-…) with items, quantity, unit, a reason
  (Expired, Broken, Theft, Found on count …) and a remark per line.
- **Save** (Ctrl+S) moves the stock at its average cost and posts the books;
  **Save draft** (Ctrl+D) moves nothing. Edit and delete reverse the stock and
  the journal first, like every other document.

  | Entry | Stock | Journal (voucher) |
  |---|---|---|
  | Damage | out | Dr 5165 Damaged Stock Written Off · Cr Inventory (DMG) |
  | Shortage | out | Dr 5166 Stock Shortage · Cr Inventory (SHT) |
  | Excess | in | Dr Inventory · Cr 4320 Stock Excess (Gain) (EXS) |

- The window shows the **stock now** of every line and warns when an entry
  takes stock below zero. **🖨 Print** (Ctrl+P) any entry.
- **Reports ▸ Inventory ▸ Stock Journal Register**; the stock card and Stock
  Transactions show Damage / Excess / Shortage. A ledger line of an entry
  opens the entry. Rights: **Users & Rights ▸ Stock Journal** (each role
  starts with its Stock Adjustment rights).
- Database: `database/patches/zzzz_v7110_stock_journal_patch.sql` (new
  tables, accounts 5165 / 5166 / 4320 if missing, rights) — runs by itself.

## 🗂 v7.10.0 — Masters

- **One Masters page** (Inventory ▸ 🗂 Masters, or Inventory / Accounts ▸
  Masters in the top menu): **Brands · Sections · Group Categories · Units
  of Measure · Tax Categories · Sales Routes · Salesmen · Vehicles · Party
  Categories · Cost Centres · Currencies & Exchange Rates · General
  Master** (your own lists: colours, sizes, reasons …). The menu items that
  only said *"planned for an upcoming build"* now open these lists.
- Every list: search, ＋ New (Insert), 💾 Save (Ctrl+S), 🗑 Delete, Active
  on / off. **A row in use is never deleted** — untick Active and it stays on
  old bills but is no longer offered.
- **Salesmen:** code, mobile, sign-in user, vehicle, commission %, monthly
  target, ✓ the routes he covers. The **Sales Invoice saves the salesman**
  of every bill (and the customer's route); a customer's own salesman is
  picked for you. With no salesmen in the list the box shows the users, as
  before.
- **Customer ▸ Contact & Credit:** Route / Area, Category, Salesman.
- **Product:** a **Section** box next to Brand; the unit boxes offer the
  **Units of Measure** list (a unit added in the product joins the list).
- **Tax Categories:** the code and rate of a category that products use are
  locked — make a new category for a new rate.
- **Currencies:** the shop's own currency is ★ (rate 1); every rate change
  is kept in the history.
- 🩹 **Fix:** opening a product and saving it no longer clears its brand.
- Database: `database/patches/zzzz_v7100_masters_patch.sql` (new tables and
  columns only — runs by itself at the next start).

## 🏷 v7.9.10 — labels print at their true size

- Labels were drawn as a picture **stretched to the width of the printer
  driver's paper**: with the driver on a bigger paper the label came out
  blown up — the barcode ran off the sticker (no scan) and the print
  spilled onto the next label. Now every label roll prints **1 : 1 in mm**
  in pure black & white.
- **Print Labels ▸ ⚙ Printer setup:** *Windows driver — true size* (the
  driver is told the label size: one sticker = one page), or **straight
  to the label printer**: TSC / XPrinter / Gprinter (TSPL) or Zebra (ZPL)
  — size and gap go to the printer itself. **Shift right / down** (mm),
  **🎯 Print alignment label** (frame 1 mm inside the sticker),
  **📏 Calibrate gap**, darkness, speed, dpi.
- Same printing for Test Print, price-change labels and phone (PDT)
  label jobs. A4 sticker sheets keep normal A4 printing.

## 🔍 v7.9.9 — more labels, server on the network, faster database

- **17 label designs, 21 sizes:** new Clothing tag (40×60 hang tag),
  Pharmacy (batch, MFG, EXP, MRP), Price per kg, QR label, Premium black,
  Arabic first, Sale tag; new sizes 35×25, 40×20, 50×40, 62×29 (Brother),
  100×70, 40×60, 100×150 and A4 sheets 3×7, 4×10, 5×13. Each design is
  offered only in sizes that fit it; all 536 combinations scan.
- **The server shows on other PCs:** 🔍 Find also asks your subnet and
  looks for port 1433 on every PC of the network (works without SQL
  Browser), and offers the server as `IP,port`.
- **🩺 Check connection** (Database Settings): name → Browser → port →
  sign-in → speed, with the fix for the step that fails.
- **⚡ Speed up database:** refreshes statistics, tidies fragmented
  indexes. See docs/MULTI_COUNTER_SETUP.md ▸ Fast database.

## ▮ v7.9.8 — barcodes that scan, shop name on every label

- **Barcodes scan reliably:** drawn as sharp vector bars, each bar a whole
  number of printer dots, with a quiet zone on both sides. Before, the
  barcode was a shrunk picture that blurred on a 203-dpi printer.
- **Barcode prints:** *System barcode (short — scans best)* — the gallery's
  default —, *Product barcode*, or *As chosen on the Print screen*; digits
  under the bars can be switched off. A 13-digit packet barcode that is too
  long for a small space prints as EAN-13.
- **Shop name** on every gallery design; the gallery's buttons open the
  design for editing (move, resize, recolour, delete any field). Shelf
  designs are offered from 58 mm wide.

## 🏷 v7.9.7 — barcode label gallery

- **🎨 Gallery** (Barcode Labels ▸ Label Designer): Modern, Classic, Minimal,
  Big price, **Expiry date** (EXP badge, MFG, batch), **Barcode** (framed),
  **Shelf** (stripe, EN + AR name, big price), **Shelf offer** (red band, old
  price struck), Mini, Jewellery — pick a size, see it, make a template or
  put it on the current one. Six of them are added as ready templates;
  **Modern 50×30 is the ★ default**, and the gallery can set the default
  design and size.
- **Change the size → every field resizes** (positions, widths, heights,
  fonts; a wider label keeps its letter size). "Resize all fields with the
  label" can be switched off.
- **Design tools:** box / frame, colour band, line; text colour, a band
  behind text, "EXP " style prefixes, serif type.
- Barcodes use the width of their space; the designer zooms the label to fit.

## 📐 v7.9.6 — item grid review (UI/UX Pro Max)

- All default columns fit a 1366-px screen again (no sideways scroll); the
  Bar Code column shows full barcodes; Product takes any extra width.
- A discount above the line value or 100 %, or a Unit Price above the Rate
  when prices can't be typed, is corrected **with a message saying why**.

## 🧾 v7.9.5 — discounts and more columns in the item grid

- **Disc % and Disc** after Rate in Sales, Purchase, both returns,
  quotations and orders: type a % or an amount, the other follows (a %
  follows the qty, an amount stays). **Unit Price** can be typed too —
  below the rate it becomes the discount. Settings ▸ Sales ▸ Allow
  Discount Edit and 🔒 read only are respected.
- **More columns** (right-click a heading ▸ tick): Code, System Barcode,
  Brand, Location, Reorder Lvl, VAT %, Sale Price, Last Cost, Total excl. VAT.
- Purchase saves its line discounts (a reopened bill keeps its total).

## 🎨 v7.9.4 — UI/UX review of the v7.9 windows

- **Readable in every theme** (WCAG 4.5 : 1): balance card, payment line,
  table headings and buttons — the dark theme no longer has dark text on
  dark buttons or headings.
- **Balance card in words:** OWES US · IN CREDIT · WE OWE · ADVANCE PAID ·
  SETTLED, not only red / green.
- **Payment area:** problems show right at the payment area; a document
  opened to view only can't be changed there; bigger ✕ with a tip.
- Grid design ▲ ▼ and small buttons are 24 px or more with tips; no 7 pt
  text in the Invoice Designer.

## 🖥 v7.9.3 — several counters on one server

- **Guide:** [docs/MULTI_COUNTER_SETUP.md](docs/MULTI_COUNTER_SETUP.md) — server
  PC, counter PCs, Branches & Counters, what is shared, troubleshooting. Also
  inside DayBill: login ▸ ⚙ Database Settings ▸ **📖 Several counters — guide**.
- **🛡 Allow SQL Server in Firewall** (Database Settings, on the server PC):
  opens TCP 1433 / UDP 1434 for the shop network and shows the address the
  counters type in *Server*.

## 🔧 v7.9.2 — update fixes

- Fixed *"Windows cannot find 'C:\Python314\pythonw.exe'"* at the end of an
  update (a test file had gone into the 7.9.1 zip).
- **Running DayBillERP.exe?** Update with the new **DayBillERP.exe** (build it
  with BUILD_EXE.bat from the zip), not with the source .zip — the exe does
  not change from source files, so Updates now refuses the .zip there.

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
