# Valley MMA Fight Club – membership management

Mobile-friendly membership app for **Valley MMA Fight Club, Pandikkad**, built with PHP, MySQL, Bootstrap 5 and JavaScript.
It has English and Malayalam (switch at any time), and you can install it on a phone as an app.

## Features

| Area | What it does |
|---|---|
| **Dashboard** | Total / active / expired members, today's payments, memberships expiring soon, present today, pending balance, this month's income, today's training, large quick buttons |
| **Members** | Add, edit, delete, search (name, phone, admission no.), filter by status and plan. The join form has every field of the paper form: photo, client information, gender M/F, height/weight (BMI is calculated), the 8 health-screening Yes/No questions, blood group, urea/creatinine/uric, HbA1c, declaration, trainer. Printable join form (filled or empty) and a member ID card with a QR code |
| **Plans** | Monthly, 3 months, 6 months, yearly (or any number of days/months). Change price and duration. Send one plan or all plans on WhatsApp |
| **Payments** | Admission fee, plan (renews the membership automatically), other fee, total, paid, balance. Cash / UPI / card / bank, UPI QR code for the exact amount. Payment history and a printable receipt in the same layout as the paper receipt, with a WhatsApp button that sends the receipt link |
| **Expiry alerts** | Members expiring soon, expired members and pending balances, each with a WhatsApp reminder that includes the UPI ID, UPI number and a pay link |
| **Attendance** | 1) The admin phone shows today's QR code (dated, optionally changing every few minutes). Members scan it with their phone camera and are marked present. 2) The admin scans member ID cards (front/back camera). 3) Mark by hand. The order of these 3 ways and the default one are set in Settings. Monthly attendance sheet |
| **Daily activity** | Weekly training plan (warm-up, primary, secondary, finisher, cool down) – editable. Today's plan is shown on the dashboard and in the member app |
| **Reports** | Daily, monthly and yearly income (cash / online split), active and expired members, payment history, pending balances, monthly attendance. Every report: **Print**, **PDF** download, **Excel (CSV)** |
| **Member app** | Members log in with phone + password (the admin sets or changes it). They see their plan, expiry, days left, attendance calendar, receipts and today's training, scan the attendance QR and pay by UPI |
| **Backup** | Download a full backup (ZIP: data + photos) or data only (SQL), keep backups on the server, restore a backup |
| **Security** | Admin login with `password_hash()`, session login, CSRF protection on every form, PDO prepared statements, input checks, login lock after 8 wrong tries, private member photos, signed QR codes and receipt links |

Colours and logo come from the DAYbill logo (blue `#360DD9`, green `#7ED957`, dark `#1A1A1A`).

## Install on XAMPP (Windows PC)

1. Copy the `valley-mma` folder to `C:\xampp\htdocs\`.
2. Start **Apache** and **MySQL** in the XAMPP control panel.
3. Open <http://localhost/valley-mma/install.php>, choose the admin username and password,
   keep "Add sample data" ticked if you want test data, and press **Install**.
4. Delete `install.php`, then open <http://localhost/valley-mma/>.

**Or with phpMyAdmin:** create a database `valley_mma`, import `sql/database.sql` and log in with
**admin / admin123**. Change the password at once in *Settings*.

Sample member login (member app): phone **9847012345**, password **member123**.

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

- **New member:** *Add member* → fill in the join form → save → record the first payment (admission fee + plan).
- **Renewal:** *Expiry alerts* → *Renew*, or *Record payment*. The new period starts the day after the old expiry.
- **Attendance:** open *Attendance* on the admin phone and leave the QR on screen (*Full screen*).
  Each member scans it once a day; the first time they log in.
- **Reminders:** *Expiry alerts* → *Remind* opens WhatsApp with the message, UPI ID and pay link ready.
- **Backup:** *Backup* → *Full backup* every week; keep the file on Google Drive or a pen drive.

## Folders

```
valley-mma/
  config.php            database settings
  install.php           one-time installer (delete after use)
  index.php             dashboard
  members.php, member_edit.php, member_view.php, member_print.php, member_card.php
  plans.php
  payments.php, payment_add.php, receipt.php, pay.php (public UPI page)
  alerts.php
  attendance.php, attendance_monthly.php, checkin.php (QR target)
  activities.php        weekly training plan
  reports.php
  settings.php, backup.php
  me.php                member app
  login.php, logout.php, lang.php, photo.php, manifest.php, sw.js, offline.html
  includes/             init.php (helpers), header/nav/footer, lang.php (English + Malayalam), sql_tools.php
  assets/               style.css, print.css, app.js, attendance.js, qr.js, icons, vendor libraries
  sql/                  schema.sql, sample_data.sql, database.sql (complete file for phpMyAdmin)
  uploads/photos/       member photos (not web-accessible)
  backups/              backups saved on the server (not web-accessible)
```

Bundled libraries (in `assets/vendor`, so the app also works without internet on XAMPP):
Bootstrap 5.3.8, Bootstrap Icons 1.13.2, html5-qrcode 2.3.8, jsPDF 2.5.2 + AutoTable 3.8.4, qrcode-generator 1.4.4.

PDF reports use English text because the PDF font has no Malayalam letters. Use **Print → Save as PDF**
for a Malayalam PDF.
