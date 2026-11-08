# My projects

| Folder / file | What it is |
|---|---|
| [`daybill/`](daybill/) | **Daybill Print** – print shop app (PHP + MySQL) |
| [`aishwarya-club/`](aishwarya-club/) | **Aishwarya Club** – club website (PHP + MySQL) with dark / light themes |
| `sales-pos.html` | Sales POS page |

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

## Aishwarya Club

Club website in PHP + MySQL: public pages (`index.php`, `contact.php`), member login and dashboard, admin,
and modules for members, events, arts festival, elections, donations, crowdfunding, blood donors, gallery,
market, ID cards, certificates, WhatsApp broadcast and more.

- **Themes**: dark / light look for the public pages (`includes/theme.php`). Default set in
  Admin → Public Website → Sections → "Default look" (dark, light or auto); a visitor's choice is remembered on their phone.
- `includes/config.php` (database and keys) is not in the repository; add it on the server.
- WhatsApp setup: [`aishwarya-club/WHATSAPP_SETUP.md`](aishwarya-club/WHATSAPP_SETUP.md).
