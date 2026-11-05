സംഭാവന (Sambhavana) - fund collection app (PHP + MySQL)

NEW INSTALL: import schema.sql in phpMyAdmin, then put your database details in db_config.php.
UPDATE (existing DB): upload all files. New columns are added by the app itself on the next login (migrate_6.sql only if the app asks for it).
  (this update needs migrate_4.sql and migrate_5.sql), upload all files, and keep your own db_config.php values.

Products (e.g. Payasam ₹500): Fund > Settings > Products. In a new entry choose the product
  and the number (qty); the amount is price × qty. Changing a price later does not change old entries.
Excel import: Fund > Settings > Import entries from Excel. Download the template,
  fill Name, Mobile, Amount, Paid, Item, Qty, upload (.xlsx or .csv), check the preview, then Import.
Excel export: Reports > any report > 📊 Excel.
Malayalam shows as ????? : the database tables are latin1. Run migrate_5.sql once (phpMyAdmin, your
  database selected > SQL). Text already saved as ????? is lost and must be typed again.
Fund colours: every fund has its own colour (first red, second green, ...). Change it in Fund > Settings > Fund colour.
Product given: Fund > Product given, or the Product box on a receipt: one button ✔ വാങ്ങി (taken), Undo to remove.
