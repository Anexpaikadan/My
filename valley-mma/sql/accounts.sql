-- Valley MMA Fight Club – accounts module (income, expense, cash / bank accounts).
-- Part of schema.sql for new installs; older installs get it automatically on the next page load.

CREATE TABLE IF NOT EXISTS acc_accounts (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(60) NOT NULL,
  kind ENUM('cash','bank','upi') NOT NULL DEFAULT 'cash',
  opening_balance DECIMAL(12,2) NOT NULL DEFAULT 0,
  active TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS acc_categories (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(60) NOT NULL,
  type ENUM('income','expense') NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Membership payments are not copied here: the ledger reads them from the payments table.
CREATE TABLE IF NOT EXISTS acc_entries (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  voucher_no INT UNSIGNED NOT NULL,
  entry_date DATE NOT NULL,
  type ENUM('income','expense','transfer') NOT NULL,
  category_id INT UNSIGNED NULL,
  account_id INT UNSIGNED NOT NULL,
  to_account_id INT UNSIGNED NULL,
  amount DECIMAL(12,2) NOT NULL,
  party VARCHAR(100) NOT NULL DEFAULT '',
  description VARCHAR(255) NOT NULL DEFAULT '',
  ref_no VARCHAR(50) NOT NULL DEFAULT '',
  created_by INT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_date (entry_date),
  KEY idx_cat (category_id),
  KEY idx_acc (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO acc_accounts (id, name, kind, opening_balance, sort_order) VALUES
  (1, 'Cash', 'cash', 0, 1),
  (2, 'Bank / UPI', 'bank', 0, 2);

INSERT IGNORE INTO acc_categories (id, name, type, sort_order) VALUES
  (1, 'Membership fees', 'income', 1),
  (2, 'Personal training', 'income', 2),
  (3, 'Equipment sale', 'income', 3),
  (4, 'Events / tournaments', 'income', 4),
  (5, 'Other income', 'income', 9),
  (20, 'Rent', 'expense', 1),
  (21, 'Electricity', 'expense', 2),
  (22, 'Water', 'expense', 3),
  (23, 'Trainer salary', 'expense', 4),
  (24, 'Staff salary', 'expense', 5),
  (25, 'Equipment', 'expense', 6),
  (26, 'Maintenance / repairs', 'expense', 7),
  (27, 'Cleaning', 'expense', 8),
  (28, 'Internet / phone', 'expense', 9),
  (29, 'Marketing', 'expense', 10),
  (30, 'Tournament fees', 'expense', 11),
  (31, 'Other expense', 'expense', 19);

-- Which account receives membership payments, by payment method.
INSERT IGNORE INTO settings (k, v) VALUES
  ('acc_fee_category', '1'),
  ('acc_map_cash', '1'),
  ('acc_map_upi', '2'),
  ('acc_map_card', '2'),
  ('acc_map_bank', '2'),
  ('absent_days', '7');
