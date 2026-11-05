-- Only if the app shows "Database update could not run by itself". Normally the app does this itself.
-- phpMyAdmin > select your database > SQL > paste > Go (once)
ALTER TABLE contributions ADD delivery ENUM('taken','sent') NULL, ADD delivered_at DATETIME NULL;
ALTER TABLE funds ADD color VARCHAR(7) NULL;
