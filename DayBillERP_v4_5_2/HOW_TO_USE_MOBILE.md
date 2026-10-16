# DayBill Mobile — phones, PDT scanners and van sales

**One app for everyone.** Each user sees only the modules you tick for them:

| Module | What it does | Stock / books |
|---|---|---|
| 📥 Goods In | scan what arrived from a supplier | makes a **draft purchase** — the office checks prices and presses Confirm → stock goes in |
| 📤 Goods Out | damaged, expired, own use, transfer out | stock goes out at once (+ journal) |
| 🧮 Stock Count | scan every item on the shelf | the counted qty **becomes** the stock (difference posted) |
| ⚖ Stock Adjust | + / − a quantity with a note | stock changes at once (+ journal) |
| 🔎 Product Info | scan → price, stock in boxes + pieces, barcodes, last purchase | — |
| 🏷 Price Check | scan → big price with VAT, offer | — |
| 🚚 Van Sales | sell from the van, **works with no signal** | each bill becomes a sales invoice in DayBill (stock out, cash/credit, VAT) |

Scanning works the same as on the PC: a piece, box, carton, extra barcode,
product code or scale label → the product **with its unit**.

---

## A. In the shop (same Wi-Fi) — PDT and phones

1. **DayBill on the shop PC** ▸ Sidebar ▸ Inventory ▸ **📱 Mobile, PDT & Van**
   ▸ tab *Phones & PDT* ▸ **▶ Start**. Tick *Start automatically when DayBill opens*.
2. Tab **Users & modules** ▸ pick a user ▸ tick his modules (e.g. Ali: Goods In,
   Stock Count; Sara: Price Check) ▸ **Save**.
3. On the PDT / phone: connect to the **shop Wi-Fi** ▸ open **Chrome** ▸ type the
   address shown in DayBill (e.g. `http://192.168.1.10:8090`) or scan its QR ▸
   ⋮ menu ▸ **Add to Home screen**.
4. Sign in with the **DayBill user name + password**. Only his modules show.
5. PDT: press the **scan button** — the code goes into the app by itself
   (keyboard / "wedge" mode is the factory setting on most PDTs).
   Phones: use the DayBill Android app for the 📷 camera.

The phone can't open it? Press **🛡 Allow in Windows Firewall** on the same tab
(once), and check the phone is on the same Wi-Fi (not mobile data).

Keep DayBill open on the shop PC while the devices work. If the Wi-Fi drops,
the documents wait on the device and go by themselves when it is back.

**Office checks (optional):** tick *Goods Out / Stock Count / Stock Adjust wait
for approval* — then they appear in the **📥 Inbox** tab: ✔ Approve / ✖ Reject.
Goods In always comes as a draft purchase (Inbox ▸ 📂 Open in DayBill).

---

## B. Van sales over the internet (Hostinger)

```
Van phone  ⇄  your Hostinger site (DayBill Van Relay)  ⇄  DayBill on the shop PC
```
The van sells with **no signal**: products, prices and customers are on the
phone. Bills go up when there is internet; DayBill collects them at every sync.
Nothing on the shop PC is opened to the internet.

**Set up once**
1. Hostinger ▸ Databases ▸ **MySQL Databases** ▸ create a database + user.
2. DayBill ▸ Mobile & Van ▸ tab **Van (internet)** ▸ **📁 Make upload folder…** ▸
   *First time* ▸ type the database details. DayBill makes
   **daybill_van_upload.zip** (the relay, the van app and a new secret
   **shop key**, saved in DayBill too).
3. Hostinger ▸ **File Manager** ▸ open the folder of your sub-domain (e.g.
   `van.yourshop.com`) ▸ **Upload** the zip ▸ right-click ▸ **Extract** here ▸
   delete the zip. `relay_config.php` inside is private (shop key + DB password)
   — the `.htaccess` that comes with it blocks it from the web.
4. DayBill: type the address (`https://van.yourshop.com/`) ▸ **Test connection** ▸
   **Sync now**. Set *Auto sync every 5 minutes*.
   Something wrong? **🌐 Check page** (`…/check.php`) shows what and how to fix it.
5. Users & modules ▸ the driver ▸ tick **🚚 Van Sales**, van code `VAN1`, PIN ▸
   Save ▸ **Sync now** (the relay learns the van).
6. Van phone: Chrome ▸ the **Van phones open** address (`…/van.html`, or scan the
   QR in DayBill) ▸ Add to Home screen ▸ sign in with **van code + PIN**.
   It downloads the products at once.

**New DayBill version?** 📁 Make upload folder… ▸ **Update files only** ▸ upload +
Extract the zip over the old files (the site keeps its relay_config.php).

**https / http:** the relay works with both; no "Force HTTPS" or redirect rule is
needed (behind Hostinger's CDN such a rule loops). Vans should use **https** —
the app then opens even with no signal. If https is broken but http works,
DayBill offers http for now and goes back to https by itself when it works.

**Every day**
* Morning: open the app with signal ▸ **⟳ Sync now** (fresh prices + customers).
* Sell: **＋ New bill** ▸ scan / search ▸ customer (cash or credit) ▸ **✔ Save** ▸
  🖨 Print / 💬 WhatsApp / 📄 PDF.
* Each bill shows *waiting* → *↑ sent to the shop* → *✓ in DayBill*.
* Bill numbers are unique per phone (`VAN1-2-00015`).

**Printing in the van**
* DayBill Android app + **Bluetooth printer** (58/80 mm): pair the printer in
  Android Settings ▸ Bluetooth ▸ in the app press Print ▸ choose it once.
* Chrome (no app): install **RawBT** from the Play Store — Print sends the bill
  to it; or 📄 PDF / 💬 WhatsApp.
* The Bluetooth receipt is printed in English with the ZATCA QR (cheap printers
  cannot print Arabic text); the screen, PDF and WhatsApp copy show Arabic.

---

## C. The Android app (APK) — optional, recommended for phones

Same app plus the 📷 camera, PDT scan-button broadcasts (Zebra DataWedge,
Urovo, Honeywell, Newland, iData, Sunmi…) and the Bluetooth printer.
Build it free on GitHub — see `android_app/README_ANDROID.md`.
First start: type the shop address or the van relay address (or scan the QR
on the DayBill screen).

---

## Good to know
* **ZATCA:** the van prints a simplified-invoice QR (seller, VAT no., time,
  total, VAT) at once. When DayBill books the bill it signs and reports it
  (Phase 2) like every other bill — sync at least daily (B2C reports are due
  within 24 hours). Note: a phone with no signal cannot sign, so the *paper*
  van bill carries the basic QR, not the signed Phase-2 QR. If your shop is
  already in Phase 2, reprint / WhatsApp the bill from DayBill after it is
  booked when a customer needs the signed copy, or ask your ZATCA adviser.
* The shop-Wi-Fi server is for the **local network only** — do not open its port
  on the router. Vans use the Hostinger relay.
* A document sent twice (weak signal) is never booked twice.
* Remove a user's access: untick the modules / *Mobile access ON* ▸ Save — the
  device is signed out. For vans also press Sync now.
