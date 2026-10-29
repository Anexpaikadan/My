-- സംഭാവന update: products (Payasam ₹500 × qty) + Malayalam fix
-- phpMyAdmin > select your database > SQL > paste all > Go. Run ONCE.
-- If you already ran migrate_4.sql and get "Duplicate column name 'item_id'", delete the ALTER TABLE contributions ADD line and run again.

-- 1. Malayalam fix (latin1 -> utf8mb4)
ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE funds CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE contributions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE payments CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE handovers CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. Products
CREATE TABLE IF NOT EXISTS fund_items(
 id INT AUTO_INCREMENT PRIMARY KEY,
 fund_id INT NOT NULL,
 name VARCHAR(100) NOT NULL,
 price DECIMAL(12,2) NOT NULL,
 active TINYINT NOT NULL DEFAULT 1,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(fund_id) REFERENCES funds(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
ALTER TABLE fund_items CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE contributions ADD item_id INT NULL AFTER mobile, ADD qty INT NULL AFTER item_id;
