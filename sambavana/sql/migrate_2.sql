-- Run ONCE (after migrate_1.sql) in phpMyAdmin > SQL
ALTER TABLE funds ADD target_amount DECIMAL(12,2) NULL, ADD show_target TINYINT NOT NULL DEFAULT 0, ADD reminders TINYINT NOT NULL DEFAULT 0, ADD status ENUM('open','closed') NOT NULL DEFAULT 'open';
ALTER TABLE contributions ADD mobile VARCHAR(15) NULL, ADD cancelled TINYINT NOT NULL DEFAULT 0;
