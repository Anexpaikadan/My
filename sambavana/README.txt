സംഭാവന (Sambhavana) - fund collection app (PHP + MySQL)

FOLDERS
 sambavana/
  index.php, dashboard.php, fund.php, ...   pages (open these in the browser)
  go.php                                   app-icon shortcuts (New entry / Add payment)
  manifest.json, sw.js                     install-as-app settings (must stay here)
  assets/css/app.css                       design
  assets/js/app.js                         app behaviour (loading bar, no double save, offline check)
  assets/img/                              logo, app icons, shortcut icons
  inc/config.php                           shared code (database, helpers, header/footer)
  inc/db_config.php                        YOUR DATABASE LOGIN - edit this
  sql/                                     database files (blocked from the browser)

NEW INSTALL
 1. phpMyAdmin: select the empty database > Import > sql/sambavana_clean.sql (admin / Admin@123)
 2. Put your database details in inc/db_config.php
 3. Upload the whole sambavana folder to public_html/

UPDATE (existing database)
 Upload all files. New database columns are added by the app itself on the next login.
 Only if the app shows "Database update could not run by itself": run sql/migrate_6.sql once.
 Malayalam shows as ?????: run sql/migrate_5.sql once.

APP ICON SHORTCUTS (Android, Chrome)
 Long-press the app icon: New entry / Add payment (opens the fund used last).
 After an update: remove the app from the home screen, open the site in Chrome, menu > Install app.

FEATURES
 Products (e.g. Payasam ₹500 × qty): Fund > Products. Product taken: Fund > Product given (✔ വാങ്ങി).
 Excel import: Fund > Settings > Import entries from Excel. Excel export: Reports > 📊 Excel.
 Fund colour: Fund > Settings > Fund colour (new funds get one automatically).
