CREATE DATABASE IF NOT EXISTS sambhavana CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sambhavana;
CREATE TABLE users(
 id INT AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(100) NOT NULL,
 username VARCHAR(50) NOT NULL UNIQUE,   -- mobile for users, login id for collectors
 password VARCHAR(255) NOT NULL,
 role ENUM('admin','user','collector') NOT NULL DEFAULT 'user',
 status ENUM('pending','approved','rejected','blocked') NOT NULL DEFAULT 'pending',
 short_name VARCHAR(10) NULL,
 fund_id INT NULL,                        -- collectors only: the one fund they belong to
 reset_token CHAR(64) NULL,
 reset_expires DATETIME NULL,
 reset_requested TINYINT NOT NULL DEFAULT 0,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE funds(
 id INT AUTO_INCREMENT PRIMARY KEY,
 creator_id INT NOT NULL,
 title VARCHAR(200) NOT NULL,
 description TEXT,
 type ENUM('charity','festival','other') DEFAULT 'charity',
 start_date DATE,
 creator_details TEXT,
 target_amount DECIMAL(12,2) NULL,
 show_target TINYINT NOT NULL DEFAULT 0,
 reminders TINYINT NOT NULL DEFAULT 0,
 status ENUM('open','closed') NOT NULL DEFAULT 'open',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(creator_id) REFERENCES users(id)
);
CREATE TABLE contributions(
 id INT AUTO_INCREMENT PRIMARY KEY,
 fund_id INT NOT NULL,
 serial_no INT NOT NULL,
 name VARCHAR(120) NOT NULL,
 mobile VARCHAR(15) NULL,
 item_id INT NULL,                        -- fund_items.id when the entry is a product (Payasam × qty)
 qty INT NULL,
 amount DECIMAL(12,2) NOT NULL,
 cancelled TINYINT NOT NULL DEFAULT 0,
 created_by INT NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(fund_id,serial_no),
 FOREIGN KEY(fund_id) REFERENCES funds(id)
);
CREATE TABLE payments(
 id INT AUTO_INCREMENT PRIMARY KEY,
 contribution_id INT NOT NULL,
 amount DECIMAL(12,2) NOT NULL,
 received_by INT NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(contribution_id) REFERENCES contributions(id)
);
CREATE TABLE handovers(
 id INT AUTO_INCREMENT PRIMARY KEY,
 fund_id INT NOT NULL,
 collector_id INT NOT NULL,
 amount DECIMAL(12,2) NOT NULL,
 status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'approved',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(fund_id) REFERENCES funds(id)
);
CREATE TABLE fund_items(
 id INT AUTO_INCREMENT PRIMARY KEY,
 fund_id INT NOT NULL,
 name VARCHAR(100) NOT NULL,              -- e.g. Payasam
 price DECIMAL(12,2) NOT NULL,            -- e.g. 500 per unit
 active TINYINT NOT NULL DEFAULT 1,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(fund_id) REFERENCES funds(id)
);
