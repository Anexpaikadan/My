/* Valley MMA Fight Club – database tables */
/* install.php runs this file and accounts.sql. To set up by hand, import database.sql in phpMyAdmin instead. */

CREATE TABLE IF NOT EXISTS admins (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  full_name VARCHAR(100) NOT NULL DEFAULT '',
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(50) NOT NULL PRIMARY KEY,
  v TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS plans (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  duration_value INT UNSIGNED NOT NULL DEFAULT 1,
  duration_unit ENUM('day','month') NOT NULL DEFAULT 'month',
  price DECIMAL(10,2) NOT NULL DEFAULT 0,
  description VARCHAR(500) NOT NULL DEFAULT '',
  active TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS members (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  adm_no VARCHAR(20) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  photo VARCHAR(100) NOT NULL DEFAULT '',
  address VARCHAR(255) NOT NULL DEFAULT '',
  place VARCHAR(100) NOT NULL DEFAULT '',
  city VARCHAR(100) NOT NULL DEFAULT '',
  district VARCHAR(100) NOT NULL DEFAULT '',
  post VARCHAR(100) NOT NULL DEFAULT '',
  pin_code VARCHAR(10) NOT NULL DEFAULT '',
  state VARCHAR(100) NOT NULL DEFAULT '',
  occupation VARCHAR(100) NOT NULL DEFAULT '',
  dob DATE NULL,
  age TINYINT UNSIGNED NULL,
  gender ENUM('','M','F') NOT NULL DEFAULT '',
  height_cm DECIMAL(5,1) NULL,
  weight_kg DECIMAL(5,1) NULL,
  blood_group VARCHAR(5) NOT NULL DEFAULT '',
  bmi DECIMAL(4,1) NULL,
  urea_creat_uric VARCHAR(50) NOT NULL DEFAULT '',
  hba1c VARCHAR(20) NOT NULL DEFAULT '',
  /* Health screening questions 1-8: 1 = yes, 0 = no, NULL = not answered */
  hq1 TINYINT(1) NULL, hq2 TINYINT(1) NULL, hq3 TINYINT(1) NULL, hq4 TINYINT(1) NULL,
  hq5 TINYINT(1) NULL, hq6 TINYINT(1) NULL, hq7 TINYINT(1) NULL, hq8 TINYINT(1) NULL,
  health_notes VARCHAR(500) NOT NULL DEFAULT '',
  declaration TINYINT(1) NOT NULL DEFAULT 0,
  trainer_name VARCHAR(100) NOT NULL DEFAULT '',
  join_date DATE NOT NULL,
  plan_id INT UNSIGNED NULL,
  start_date DATE NULL,
  expiry_date DATE NULL,
  password_hash VARCHAR(255) NULL,
  card_token CHAR(16) NOT NULL,
  /* pending = invited, waiting for admin approval; inactive = deactivated by admin (cannot mark attendance) */
  status ENUM('pending','active','inactive') NOT NULL DEFAULT 'active',
  invite_token CHAR(32) NULL,
  details_at DATETIME NULL,
  approved_at DATETIME NULL,
  /* Position (level): changes by attendance when level_auto = 1, or set by the admin */
  level_id INT UNSIGNED NULL,
  level_auto TINYINT(1) NOT NULL DEFAULT 1,
  level_since DATE NULL,
  notes VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_card (card_token),
  KEY idx_phone (phone),
  KEY idx_status (status),
  KEY idx_expiry (expiry_date),
  KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payments (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  receipt_no INT UNSIGNED NOT NULL UNIQUE,
  member_id INT UNSIGNED NOT NULL,
  plan_id INT UNSIGNED NULL,
  pay_date DATE NOT NULL,
  admission_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
  plan_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
  other_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
  other_note VARCHAR(100) NOT NULL DEFAULT '',
  total DECIMAL(10,2) NOT NULL DEFAULT 0,
  paid DECIMAL(10,2) NOT NULL DEFAULT 0,
  method ENUM('cash','upi','card','bank') NOT NULL DEFAULT 'cash',
  upi_ref VARCHAR(50) NOT NULL DEFAULT '',
  period_start DATE NULL,
  period_end DATE NULL,
  /* membership before this payment, restored when the payment is deleted */
  prev_plan_id INT UNSIGNED NULL,
  prev_start DATE NULL,
  prev_expiry DATE NULL,
  note VARCHAR(255) NOT NULL DEFAULT '',
  created_by INT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_member (member_id),
  KEY idx_date (pay_date),
  CONSTRAINT fk_pay_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS attendance (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  member_id INT UNSIGNED NOT NULL,
  att_date DATE NOT NULL,
  check_in TIME NOT NULL,
  method ENUM('qr','card','manual') NOT NULL DEFAULT 'manual',
  UNIQUE KEY uq_member_day (member_id, att_date),
  KEY idx_date (att_date),
  CONSTRAINT fk_att_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* Weekly training plan ("Valley daily"): day 1 = Monday … 7 = Sunday */
CREATE TABLE IF NOT EXISTS activities (
  day_no TINYINT UNSIGNED NOT NULL,
  slot ENUM('warmup','primary','secondary','finisher','cooldown') NOT NULL,
  activity VARCHAR(200) NOT NULL DEFAULT '',
  PRIMARY KEY (day_no, slot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_attempts (
  ip VARCHAR(45) NOT NULL,
  tried_at DATETIME NOT NULL,
  KEY idx_ip (ip, tried_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO settings (k, v) VALUES
  ('gym_name', 'VALLEY MMA'),
  ('gym_tagline', 'FIGHT CLUB'),
  ('gym_place', 'PANDIKKAD'),
  ('phone1', '+91 8075 112 402'),
  ('phone2', '+91 7012 613 829'),
  ('upi_id', ''),
  ('upi_name', 'Valley MMA Fight Club'),
  ('upi_phone', ''),
  ('country_code', '91'),
  ('expiry_days', '7'),
  ('admission_fee', '500'),
  ('default_lang', 'en'),
  ('att_default', 'qr'),
  ('att_order', 'qr,card,manual'),
  ('att_camera', 'environment'),
  ('att_refresh', '0'),
  ('att_block_expired', '0'),
  ('trial_days', '7'),
  ('auto_backup', '1'),
  ('backup_keep', '14'),
  ('schema_version', '5');

INSERT IGNORE INTO plans (id, name, duration_value, duration_unit, price, description, sort_order) VALUES
  (1, 'Monthly', 1, 'month', 1500, 'MMA, boxing, kickboxing and fitness training', 1),
  (2, '3 Months', 3, 'month', 4000, 'MMA, boxing, kickboxing and fitness training', 2),
  (3, '6 Months', 6, 'month', 7500, 'MMA, boxing, kickboxing and fitness training', 3),
  (4, 'Yearly', 12, 'month', 14000, 'MMA, boxing, kickboxing and fitness training', 4);

INSERT IGNORE INTO activities (day_no, slot, activity) VALUES
  (1, 'warmup', ''), (1, 'primary', 'Full body - HIIT / EMOM / AMRAP'), (1, 'secondary', 'Tec. Sparring'), (1, 'finisher', 'Batch drills'), (1, 'cooldown', ''),
  (2, 'warmup', ''), (2, 'primary', 'Shadow'), (2, 'secondary', 'Updation'), (2, 'finisher', 'Neck'), (2, 'cooldown', ''),
  (3, 'warmup', ''), (3, 'primary', 'Sprint / agility / cross country'), (3, 'secondary', 'Bag STD'), (3, 'finisher', 'Abs'), (3, 'cooldown', ''),
  (4, 'warmup', ''), (4, 'primary', 'Upper body'), (4, 'secondary', 'Pad work'), (4, 'finisher', 'Wrist'), (4, 'cooldown', ''),
  (5, 'warmup', ''), (5, 'primary', 'Lower body'), (5, 'secondary', 'Bag A / Bag B'), (5, 'finisher', 'Neck'), (5, 'cooldown', ''),
  (6, 'warmup', ''), (6, 'primary', 'Strategic shadow / swimming'), (6, 'secondary', 'Batch drills'), (6, 'finisher', 'Abs'), (6, 'cooldown', ''),
  (7, 'warmup', ''), (7, 'primary', ''), (7, 'secondary', ''), (7, 'finisher', ''), (7, 'cooldown', '');
