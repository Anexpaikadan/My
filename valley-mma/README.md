# Valley MMA Fight Club – membership management

Mobile-friendly membership app for **Valley MMA Fight Club, Pandikkad**, built with PHP, MySQL, Bootstrap 5 and JavaScript.
It has English and Malayalam (switch at any time), and you can install it on a phone as an app.

## Features

| Area | What it does |
|---|---|
| **Dashboard** | In sections – *Today* (present, collection, expense, birthdays), *Members* (total, active, expired, expiring soon, absent, pending balance) and *This month* (income, expense, profit/loss, balance). Every tile opens the matching list. Quick buttons: new member, record payment, add expense, attendance QR, reminders |
| **Navigation** | Phone: bottom bar (Home, Members, Attendance, Accounts, More) and a *More* page with every part of the app as tiles in sections. Desktop: sidebar grouped in Members / Money / Gym. Back button on inner pages |
| **Accounts** | Cash, bank and UPI accounts with opening balance. Income, expense and transfer vouchers with categories (rent, electricity, salary, equipment …, editable). Membership payments are counted as income automatically. Ledger with filters, opening/closing and running balance; printable vouchers; reports: profit & loss, monthly summary, cash book – all with print / PDF / Excel |
| **Invite & approve** | *Invite new member*: enter phone + password → a personal link is made → *Send on WhatsApp*. The member opens the link, logs in and fills the join form (photo, details, health questions, declaration). The member then shows as *Waiting for approval*; the admin approves with a payment or activates for some days (7 by default). Members can be **deactivated** and activated again |
| **Attendance rules** | Deactivated and not-approved members cannot mark attendance in any way (QR scan, ID card, by hand). Optional: block expired members too (Settings) |
| **Password check** | Every money change (payments, income, expense, transfers, accounts setup, plan prices, free days) and every delete (member, payment, entry, attendance, admin, backup) opens a pop-up asking for the admin password again. Editing member details does not ask |
| **Members** | Add, edit, delete, search (name, phone, admission no.), filter by status and plan. The join form has every field of the paper form: photo, client information, gender M/F, height/weight (BMI is calculated), the 8 health-screening Yes/No questions, blood group, urea/creatinine/uric, HbA1c, declaration, trainer. Printable join form (filled or empty) and a member ID card with a QR code |
| **Plans** | Monthly, 3 months, 6 months, yearly (or any number of days/months). Change price and duration. Send one plan or all plans on WhatsApp |
| **Payments** | Admission fee, plan (renews the membership automatically), other fee, total, paid, balance. Cash / UPI / card / bank, UPI QR code for the exact amount. Payment history and a printable receipt in the same layout as the paper receipt, with a WhatsApp button that sends the receipt link |
| **Alerts** | Members expiring soon, expired members and pending balances, each with a WhatsApp reminder that includes the UPI ID, UPI number and a pay link. Birthdays (today and next 7 days) with a WhatsApp wish. Absent members (active but not came for N days, set in Settings) with a WhatsApp follow-up |
| **Attendance** | 1) The admin phone shows today's QR code (dated, optionally changing every few minutes). Members scan it with their phone camera and are marked present. 2) The admin scans member ID cards (front/back camera). 3) Mark by hand. The order of these 3 ways and the default one are set in Settings. Monthly attendance sheet |
| **Daily activity** | Weekly training plan (warm-up, primary, secondary, finisher, cool down) – editable. Today's plan is shown on the dashboard and in the member app |
| **Reports** | Daily, monthly and yearly income (cash / online split), active and expired members, payment history, pending balances, monthly attendance. Every report: **Print**, **PDF** download, **Excel (CSV)** |
| **Member app** | Members log in with phone + password (the admin sets or changes it). They see their plan, expiry, days left, attendance calendar, receipts and today's training, scan the attendance QR and pay by UPI |
| **Backup** | Download a full backup (ZIP: data + photos) or data only (SQL). **Automatic backup every day** on the server (the newest 14 are kept, number can be changed). Restore from a saved backup or an uploaded file; a copy of the current data is saved first, and backups from older app versions are upgraded automatically. Downloads, restore and delete ask for the admin password. The dashboard reminds you when no backup was downloaded for 7 days |
| **Security** | Admin login with `password_hash()`, session login that lasts 7 days (`login_days` in config.php), CSRF protection on every form, PDO prepared statements, input checks, login lock after 8 wrong tries, private member photos, signed QR codes and receipt links |

Colours and logo come from the DAYbill logo (blue `#360DD9`, green `#7ED957`, dark `#1A1A1A`).

## Install on XAMPP (Windows PC)

1. Copy the `valley-mma` folder to `C:\xampp\htdocs\`.
2. Start **Apache** and **MySQL** in the XAMPP control panel.
3. Open <http://localhost/valley-mma/install.php>, choose the admin username and password,
   keep "Add sample data" ticked if you want test data, and press **Install**.
4. Delete `install.php`, then open <http://localhost/valley-mma/>.

**Or with phpMyAdmin:** create a database `valley_mma` and import one file:
- `sql/valley_mma_clean.sql` – **clean start** (all tables, settings, plans, training plan, accounts; no members), or
- `sql/database.sql` – the same **with sample data** for testing.

Log in with **admin / admin123** and change the password at once in *Settings*.

Sample member login (member app): phone **9847012345**, password **member123**.

## Updating an existing installation

Copy the new files over the old ones but keep your `config.php`. The new accounts tables are
added automatically the first time a page is opened.

## Phones and the attendance QR (important on XAMPP)

The attendance QR code and WhatsApp links contain the app address. Phones **cannot open `localhost`**, so:

1. Connect the PC and the phones to the **same Wi-Fi**.
2. Open *Attendance*: if the QR uses `localhost`, a red box shows this PC's Wi-Fi address
   (e.g. `http://192.168.1.10/valley-mma/`) – press **Use this address**. (Also in *Settings → App address*.)
3. Allow Apache through the Windows firewall if phones cannot open that address.

Members scan the QR with the normal **phone camera**, or in the member app. If scanning does not work on a phone,
open **More → Scanner test** (or `scan_test.php`) on that phone: it checks every step and says what to fix. Without https the live camera inside
the browser is blocked by phones, so the app offers **Take a photo of the QR** instead – it works everywhere.
With https (hosting) the live scanner works too.

## Install on hosting (Hostinger, cPanel, …)

1. Create a MySQL database and user in the control panel.
2. Upload the `valley-mma` folder and put the database name, user, password and host in `config.php`.
3. Open `https://your-domain/valley-mma/install.php`, then delete `install.php`.
4. Turn on SSL (HTTPS) for the domain. The camera scanner in the browser and "Install app" need HTTPS.
   You can then remove the `#` in front of the HTTPS lines in `.htaccess`.

Requirements: PHP 8.0+ with PDO MySQL and GD (ZIP for photo backups), MySQL 5.7+ or MariaDB 10.3+.

## First settings

In **Settings**: gym name and phone numbers, **UPI ID** (e.g. `valleymma@okaxis`), UPI number and name,
admission fee, how many days before expiry the alerts start, default language, attendance options
and admin accounts.

## Install as a phone app

- **Admin:** open the site in Chrome on the phone → menu → *Install app* (or the *Install app on phone* button in the side menu).
- **Members:** send them the member app link (member page → WhatsApp → *Send app login link*). They open
  it, log in and tap *Install app* (iPhone: Share → *Add to Home Screen*).

## Daily use

- **New member (invite):** *Invite new member* → phone + password → *Send link on WhatsApp*. When the member has filled the form: *Members → Waiting* → open → *Approve with payment* (or *Activate days*).
- **New member (at the desk):** *Add member* → fill in the join form → save → record the first payment (admission fee + plan).
- **Stop a member:** member page → *Deactivate*. They cannot mark attendance until you press *Activate*.
- **Renewal:** *Expiry alerts* → *Renew*, or *Record payment*. The new period starts the day after the old expiry.
- **Attendance:** open *Attendance* on the admin phone and leave the QR on screen (*Full screen*).
  Each member scans it once a day; the first time they log in.
- **Reminders:** *Expiry alerts* → *Remind* opens WhatsApp with the message, UPI ID and pay link ready.
- **Expenses:** *Accounts* → *Add expense* (or the quick button on the dashboard). Choose the category and whether it was paid from cash or bank.
- **Bank deposit:** *Accounts* → *Transfer* (Cash → Bank).
- **First time in Accounts:** *Accounts setup* → enter the opening balance of cash and bank, and check which account UPI / card payments go into.
- **Backup:** *Backup* → *Full backup* every week; keep the file on Google Drive or a pen drive.

## Folders

```
valley-mma/
  config.php            database settings
  install.php           one-time installer (delete after use)
  index.php             dashboard
  members.php, member_edit.php, member_view.php, member_print.php, member_card.php
  member_invite.php, member_action.php, join.php (member fills the join form from the WhatsApp link)
  plans.php
  payments.php, payment_add.php, receipt.php, pay.php (public UPI page)
  alerts.php
  attendance.php, attendance_monthly.php, checkin.php (QR target)
  activities.php        weekly training plan
  reports.php
  accounts.php, ledger.php, entry_edit.php, voucher.php, acc_reports.php, acc_settings.php
  more.php              all pages as tiles (phone)
  settings.php, backup.php
  me.php                member app
  login.php, logout.php, lang.php, photo.php, manifest.php, sw.js, offline.html
  includes/             init.php (helpers), accounts.php, header/nav/footer, lang.php (English + Malayalam), sql_tools.php
  assets/               style.css, print.css, app.js, attendance.js, qr.js, icons, vendor libraries
  sql/                  valley_mma_clean.sql (clean, for phpMyAdmin), database.sql (with sample data),
                        schema.sql, accounts.sql, sample_data.sql (used by install.php)
  uploads/photos/       member photos (not web-accessible)
  backups/              backups saved on the server (not web-accessible)
```

Bundled libraries (in `assets/vendor`, so the app also works without internet on XAMPP):
Bootstrap 5.3.8, Bootstrap Icons 1.13.2, jsQR 1.4.0 (QR scanning), jsPDF 2.5.2 + AutoTable 3.8.4, qrcode-generator 1.4.4.

PDF reports use English text because the PDF font has no Malayalam letters. Use **Print → Save as PDF**
for a Malayalam PDF.
