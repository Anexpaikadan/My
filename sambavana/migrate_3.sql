-- Run ONCE (after migrate_2.sql) in phpMyAdmin > SQL
ALTER TABLE users ADD reset_token CHAR(64) NULL, ADD reset_expires DATETIME NULL, ADD reset_requested TINYINT NOT NULL DEFAULT 0;
