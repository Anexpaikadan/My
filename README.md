# My projects

| Folder / file | What it is |
|---|---|
| [`daybill/`](daybill/) | **Daybill Print** – print shop app (PHP + MySQL) |
| `sales-pos.html` | Sales POS page |
| [`Av/mynamec_/`](Av/mynamec_/) | **Aishwarya Arts & Sports Club** – members portal (PHP + MySQL), mynamecc.online |

## Daybill Print

A web app for print shops. Customers scan the shop's QR code, upload their files and choose the options;
staff see the order, check it and print it on the shop printer.

**Customers (phone, English / Arabic)**
- Upload PDF, photos, Word, Excel, PowerPoint; choose copies, paper size, colour, sides, pages.
- Amount to pay shown at once (pages are counted on the phone).
- Layouts: 2 / 4 / 8 pages on one sheet, photo sheets, passport photos.
- **Photo studio**: several photos, each with its own size and number; crop editor (move, zoom, rotate,
  mirror, face guide, brightness, contrast, colour); photos arranged on the paper automatically with a live preview.
- Order code to show at the counter; optional shop PIN keypad.

**Staff**
- Order list with sound for new orders; open an order, change options and price, press **OK – Print**.
- Sheet previews of photo orders; status changes to printed / completed automatically.
- Several printers (by paper size and colour, photo printer).

**Admin**
- Several shops, each with its own admin and employees; a super admin manages all shops.
- Employees, customer options, prices (e.g. pages 1–2 = 2 SR, each extra page 1 SR), layouts, photo print,
  app colour, QR code poster.
- **Order check** per shop: staff check, shop PIN, or print at once.

**Printing**
- Local (XAMPP on the shop PC), cloud hosting + print agent on the shop PC (one-file PC tool), or browser printing.
- HTTPS is always required. Installable as an app (PWA).

Setup, hosting and printer details: [`daybill/README.md`](daybill/README.md).

## Aishwarya Arts & Sports Club (`Av/mynamec_/`)

Members portal for the club in Vettikkattiri: public homepage, WhatsApp OTP / passkey login, dashboard,
admin panel and modules (football, predictions, arts festival, henna fest, elections, blood donors,
crowdfunding, ID cards, certificates, gallery, subscriptions…).

**Setup:** in `includes/config.php` fill in `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS` (kept as placeholders in git),
and the football-data.org token in `modules/prediction_sync.php`.

**UI/UX pass (shared header + footer, used by every member page):**
- Pinch-zoom allowed again; no auto-zoom on iPhone when typing (inputs are 16px).
- Clearer text: grey labels, placeholders, menu headings and bottom-bar labels now meet 4.5:1 contrast.
- Bigger tap targets (44px): menu, close buttons, avatar, social icons, bottom bar, buttons on phones.
- Keyboard and screen reader: "Skip to content" link, visible focus ring, menus report open/closed,
  Escape closes menus and the drawer, current page is marked, decorative emoji hidden from readers.
- Mobile menu highlights the page you are on.
- Faster: Font Awesome loaded once (the duplicate JS copy is gone), duplicate PWA tags removed.
- Honours the phone's "reduce motion" setting; safe-area padding for notched phones.
