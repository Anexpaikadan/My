-- Run ONCE (after migrate_3.sql) in phpMyAdmin > SQL : products / fixed-price items (e.g. Payasam ₹500)
CREATE TABLE fund_items(
 id INT AUTO_INCREMENT PRIMARY KEY,
 fund_id INT NOT NULL,
 name VARCHAR(100) NOT NULL,
 price DECIMAL(12,2) NOT NULL,
 active TINYINT NOT NULL DEFAULT 1,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(fund_id) REFERENCES funds(id)
);
ALTER TABLE contributions ADD item_id INT NULL AFTER mobile, ADD qty INT NULL AFTER item_id;
