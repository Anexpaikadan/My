-- Run ONCE in phpMyAdmin > (select your database) > SQL
-- Fixes Malayalam showing as ????? : tables were created as latin1, change them to utf8mb4.
-- Text that was already saved as ????? cannot be recovered; edit/retype it after running this.
ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE funds CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE contributions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE payments CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE handovers CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE fund_items CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
