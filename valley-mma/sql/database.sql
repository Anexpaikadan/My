/* ===================================================================== */
/* Valley MMA Fight Club – complete database (tables + sample data + admin) */

/* phpMyAdmin (XAMPP): create a database "valley_mma" (utf8mb4_unicode_ci), */
/* open it, then Import this file. (Or take away the comment marks around the two lines below to create it here.) */
/* Login after import:  admin / admin123   (change it in Settings!) */
/* Sample member login: phone 9847012345 / member123  (invited member waiting: 9645012399 / member123) */

/* No sample data wanted? Use install.php instead (it has a checkbox), */
/* or delete the "sample data" part at the end of this file before importing. */
/* ===================================================================== */
/* CREATE DATABASE IF NOT EXISTS valley_mma CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; */
/* USE valley_mma; */

SET NAMES utf8mb4;

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
  rules_accepted_at DATETIME NULL,
  approved_at DATETIME NULL,
  /* Position (level): changes by attendance when level_auto = 1, or set by the admin */
  level_id INT UNSIGNED NULL,
  level_auto TINYINT(1) NOT NULL DEFAULT 1,
  level_since DATE NULL,
  /* old students: attendance days before the app (counted for the position) */
  att_opening SMALLINT UNSIGNED NOT NULL DEFAULT 0,
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
  /* opening = old balance of an old student (paid 0) */
  kind ENUM('normal','opening') NOT NULL DEFAULT 'normal',
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
  ('schema_version', '8');

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

/* Membership payments are not copied here: the ledger reads them from the payments table. */
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

/* Gym leave days (gym closed: holidays, festivals …) and member freezes (accident, injury, travel …) */

CREATE TABLE IF NOT EXISTS gym_leaves (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  from_date DATE NOT NULL,
  to_date DATE NOT NULL,
  title VARCHAR(150) NOT NULL,
  message TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_dates (from_date, to_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* While frozen the member cannot mark attendance; the membership expiry is moved on by the frozen days. */
CREATE TABLE IF NOT EXISTS member_freezes (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  member_id INT UNSIGNED NOT NULL,
  from_date DATE NOT NULL,
  to_date DATE NOT NULL,
  days SMALLINT UNSIGNED NOT NULL,
  extended TINYINT(1) NOT NULL DEFAULT 1,
  reason ENUM('injury','travel','illness','other') NOT NULL DEFAULT 'other',
  note VARCHAR(255) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_member (member_id, from_date),
  CONSTRAINT fk_freeze_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* Member positions (levels) that change with attendance, and complaints / suggestions */

/* A member is in the level with the highest from_day not above their attendance days. */
CREATE TABLE IF NOT EXISTS levels (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(60) NOT NULL,
  from_day SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  color VARCHAR(7) NOT NULL DEFAULT '#6C757D',
  note VARCHAR(255) NOT NULL DEFAULT '',
  UNIQUE KEY uq_from_day (from_day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO levels (id, name, from_day, color, note) VALUES
  (1, 'Warm-up', 1, '#F08C00', 'First 5 days: warm-up, stretching, basic movements'),
  (2, 'Beginner', 6, '#2F9E44', 'Stance, guard, basic punches and kicks'),
  (3, 'Intermediate', 31, '#1971C2', 'Combinations, pad work, light sparring'),
  (4, 'Advanced', 91, '#C8160E', 'Full training and sparring');

CREATE TABLE IF NOT EXISTS complaints (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  member_id INT UNSIGNED NULL,
  category ENUM('equipment','trainer','cleanliness','timing','payment','suggestion','other') NOT NULL DEFAULT 'other',
  subject VARCHAR(150) NOT NULL,
  status ENUM('open','progress','resolved') NOT NULL DEFAULT 'open',
  by_admin TINYINT(1) NOT NULL DEFAULT 0,
  admin_unread TINYINT(1) NOT NULL DEFAULT 0,
  member_unread TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_status (status, updated_at),
  KEY idx_member (member_id),
  CONSTRAINT fk_comp_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS complaint_msgs (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  complaint_id INT UNSIGNED NOT NULL,
  by_admin TINYINT(1) NOT NULL DEFAULT 0,
  admin_id INT UNSIGNED NULL,
  message TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_complaint (complaint_id),
  CONSTRAINT fk_cmsg_comp FOREIGN KEY (complaint_id) REFERENCES complaints (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* Fight shop: products shown on the public shop page (enquiry on WhatsApp) */
CREATE TABLE IF NOT EXISTS products (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  category VARCHAR(60) NOT NULL DEFAULT '',
  price DECIMAL(10,2) NOT NULL DEFAULT 0,
  sale_price DECIMAL(10,2) NULL,
  description TEXT NULL,
  /* JSON list of image files in media/products */
  images TEXT NULL,
  in_stock TINYINT(1) NOT NULL DEFAULT 1,
  active TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_active (active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* Free trial / join requests from the public home page */
CREATE TABLE IF NOT EXISTS join_requests (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  place VARCHAR(100) NOT NULL DEFAULT '',
  phone VARCHAR(20) NOT NULL,
  program VARCHAR(60) NOT NULL DEFAULT '',
  /* new → following / waiting → trial (trial attended) → joined, or not_interested */
  status ENUM('new','following','waiting','trial','joined','not_interested') NOT NULL DEFAULT 'new',
  trial_date DATE NULL,
  trial_days SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  member_id INT UNSIGNED NULL,
  note VARCHAR(1000) NOT NULL DEFAULT '',
  ip VARCHAR(45) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_status (status, created_at),
  KEY idx_ip (ip, created_at)
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

/* Which account receives membership payments, by payment method. */
INSERT IGNORE INTO settings (k, v) VALUES
  ('acc_fee_category', '1'),
  ('acc_map_cash', '1'),
  ('acc_map_upi', '2'),
  ('acc_map_card', '2'),
  ('acc_map_bank', '2'),
  ('absent_days', '7');

/* Default admin: admin / admin123 */
INSERT IGNORE INTO admins (id, username, full_name, password_hash) VALUES
  (1, 'admin', 'Admin', '$2y$10$CVXY22uV3LDS3ukVMDSFsOWqvPFb.cIbm8teAIWfdamzQzv1r4oAW');

/* --------------------------------------------------------------------- */
/* Sample data */
/* --------------------------------------------------------------------- */

INSERT INTO members (id, adm_no, name, phone, gender, place, city, district, post, pin_code, state, occupation, dob, age, height_cm, weight_kg, blood_group, bmi, hq1, hq2, hq3, hq4, hq5, hq6, hq7, hq8, declaration, trainer_name, join_date, plan_id, start_date, expiry_date, password_hash, card_token) VALUES
  (1, 'VM001', 'Muhammed Shafi', '9847012345', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Student', '1998-04-12', 28, 175, 72, 'B+', 23.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 200 DAY, 1, CURDATE() - INTERVAL 10 DAY, CURDATE() + INTERVAL 20 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '15196325a32fe8de'),
  (2, 'VM002', 'Arjun Krishnan', '9895123456', 'M', 'Manjeri', 'Manjeri', 'Malappuram', 'Manjeri', '676521', 'Kerala', 'Engineer', '1995-09-03', 31, 170, 68, 'O+', 23.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 180 DAY, 2, CURDATE() - INTERVAL 87 DAY, CURDATE() + INTERVAL 3 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '6e37d8de303e450c'),
  (3, 'VM003', 'Fathima Rinsha', '9744234567', 'F', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Teacher', '2001-01-20', 25, 160, 55, 'A+', 21.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 95 DAY, 1, CURDATE() - INTERVAL 35 DAY, CURDATE() - INTERVAL 5 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '7e25994dddaa9ca0'),
  (4, 'VM004', 'Rahul Das', '9605345678', 'M', 'Wandoor', 'Wandoor', 'Malappuram', 'Wandoor', '676521', 'Kerala', 'Driver', '1993-07-15', 33, 178, 80, 'AB+', 25.2, 0,0,0,1,0,0,0,1, 1, 'Coach Anees', CURDATE() - INTERVAL 62 DAY, 3, CURDATE() - INTERVAL 62 DAY, CURDATE() + INTERVAL 120 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '0a605956ca2e1738'),
  (5, 'VM005', 'Ajmal P', '9562456789', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Business', '1997-11-30', 29, 172, 74, 'B-', 25, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 400 DAY, 4, CURDATE() - INTERVAL 115 DAY, CURDATE() + INTERVAL 250 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '88afdef230f754c4'),
  (6, 'VM006', 'Nihal K', '9946567890', 'M', 'Melattur', 'Melattur', 'Malappuram', 'Melattur', '676521', 'Kerala', 'Student', '2004-03-08', 22, 168, 61, 'O-', 21.6, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 29 DAY, 1, CURDATE() - INTERVAL 29 DAY, CURDATE() + INTERVAL 1 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '0300f03d052a13dc'),
  (7, 'VM007', 'Anjali Menon', '9037678901', 'F', 'Perinthalmanna', 'Perinthalmanna', 'Malappuram', 'Perinthalmanna', '676521', 'Kerala', 'Nurse', '1999-06-25', 27, 158, 52, 'A-', 20.8, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 120 DAY, 2, CURDATE() - INTERVAL 120 DAY, CURDATE() - INTERVAL 30 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '4c599ba2293abf02'),
  (8, 'VM008', 'Shahid Ali', '8086789012', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Electrician', '2000-12-01', 26, 174, 77, 'B+', 25.4, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 15 DAY, 1, CURDATE() - INTERVAL 15 DAY, CURDATE() + INTERVAL 15 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '37c92bff142ea3ee'),
  (9, 'VM009', 'Vishnu Prasad', '7012890123', 'M', 'Karuvarakundu', 'Karuvarakundu', 'Malappuram', 'Karuvarakundu', '676521', 'Kerala', 'Police', '1996-02-14', 30, 180, 85, 'O+', 26.2, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 150 DAY, 1, CURDATE() - INTERVAL 24 DAY, CURDATE() + INTERVAL 6 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '89ede8e708770d57'),
  (10, 'VM010', 'Sanju Thomas', '9446901234', 'M', 'Nilambur', 'Nilambur', 'Malappuram', 'Nilambur', '676521', 'Kerala', 'Shop owner', '1994-10-10', 32, 169, 70, 'A+', 24.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 90 DAY, 1, CURDATE() - INTERVAL 90 DAY, CURDATE() - INTERVAL 60 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '70d8a703575d7e6b'),
  (11, 'VM011', 'Adil Rahman', '8129012345', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Student', '2006-05-05', 20, 165, 58, 'B+', 21.3, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 20 DAY, 2, CURDATE() - INTERVAL 20 DAY, CURDATE() + INTERVAL 70 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '7924413444a02ac3'),
  (12, 'VM012', 'Sneha Raj', '9539123456', 'F', 'Manjeri', 'Manjeri', 'Malappuram', 'Manjeri', '676521', 'Kerala', 'Accountant', '2002-08-18', 24, 162, 57, 'O+', 21.7, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 2 DAY, 1, CURDATE() - INTERVAL 2 DAY, CURDATE() + INTERVAL 28 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '4214737ce705c7a7');

INSERT INTO payments (receipt_no, member_id, plan_id, pay_date, admission_fee, plan_fee, other_fee, other_note, total, paid, method, upi_ref, period_start, period_end, note) VALUES
  (1001, 1, 1, CURDATE() - INTERVAL 10 DAY, 0, 1500, 0, '', 1500, 1500, 'cash', '', CURDATE() - INTERVAL 10 DAY, CURDATE() + INTERVAL 20 DAY, ''),
  (1002, 2, 2, CURDATE() - INTERVAL 87 DAY, 0, 4000, 0, '', 4000, 4000, 'upi', 'UPI4002', CURDATE() - INTERVAL 87 DAY, CURDATE() + INTERVAL 3 DAY, ''),
  (1003, 3, 1, CURDATE() - INTERVAL 35 DAY, 0, 1500, 0, '', 1500, 1500, 'cash', '', CURDATE() - INTERVAL 35 DAY, CURDATE() - INTERVAL 5 DAY, ''),
  (1004, 4, 3, CURDATE() - INTERVAL 62 DAY, 500, 7500, 0, '', 8000, 8000, 'upi', 'UPI4004', CURDATE() - INTERVAL 62 DAY, CURDATE() + INTERVAL 120 DAY, ''),
  (1005, 5, 4, CURDATE() - INTERVAL 115 DAY, 0, 14000, 0, '', 14000, 14000, 'cash', '', CURDATE() - INTERVAL 115 DAY, CURDATE() + INTERVAL 250 DAY, ''),
  (1006, 6, 1, CURDATE() - INTERVAL 29 DAY, 500, 1500, 0, '', 2000, 2000, 'upi', 'UPI4006', CURDATE() - INTERVAL 29 DAY, CURDATE() + INTERVAL 1 DAY, ''),
  (1007, 7, 2, CURDATE() - INTERVAL 120 DAY, 500, 4000, 0, '', 4500, 4500, 'cash', '', CURDATE() - INTERVAL 120 DAY, CURDATE() - INTERVAL 30 DAY, ''),
  (1008, 8, 1, CURDATE() - INTERVAL 15 DAY, 500, 1500, 0, '', 2000, 1000, 'upi', 'UPI4008', CURDATE() - INTERVAL 15 DAY, CURDATE() + INTERVAL 15 DAY, ''),
  (1009, 9, 1, CURDATE() - INTERVAL 24 DAY, 0, 1500, 0, '', 1500, 1500, 'cash', '', CURDATE() - INTERVAL 24 DAY, CURDATE() + INTERVAL 6 DAY, ''),
  (1010, 10, 1, CURDATE() - INTERVAL 90 DAY, 500, 1500, 0, '', 2000, 2000, 'upi', 'UPI4010', CURDATE() - INTERVAL 90 DAY, CURDATE() - INTERVAL 60 DAY, ''),
  (1011, 11, 2, CURDATE() - INTERVAL 20 DAY, 500, 4000, 0, '', 4500, 4500, 'cash', '', CURDATE() - INTERVAL 20 DAY, CURDATE() + INTERVAL 70 DAY, ''),
  (1012, 12, 1, CURDATE(), 500, 1500, 0, '', 2000, 2000, 'upi', 'UPI4012', CURDATE() - INTERVAL 2 DAY, CURDATE() + INTERVAL 28 DAY, ''),
  (1013, 1, NULL, CURDATE(), 0, 0, 300, 'Gloves', 300, 300, 'upi', 'UPI4999', NULL, NULL, 'Boxing gloves'),
  (1014, 8, NULL, CURDATE(), 0, 0, 0, '', 0, 500, 'cash', '', NULL, NULL, 'Balance payment');

INSERT IGNORE INTO attendance (member_id, att_date, check_in, method) VALUES
  (1, CURDATE() - INTERVAL 1 DAY, '07:34:00', 'qr'),
  (1, CURDATE(), '18:47:00', 'card'),
  (2, CURDATE() - INTERVAL 3 DAY, '19:15:00', 'manual'),
  (2, CURDATE() - INTERVAL 2 DAY, '08:28:00', 'qr'),
  (2, CURDATE(), '08:54:00', 'manual'),
  (3, CURDATE() - INTERVAL 6 DAY, '17:43:00', 'qr'),
  (3, CURDATE() - INTERVAL 5 DAY, '06:56:00', 'card'),
  (4, CURDATE() - INTERVAL 8 DAY, '07:24:00', 'manual'),
  (4, CURDATE() - INTERVAL 7 DAY, '18:37:00', 'qr'),
  (4, CURDATE() - INTERVAL 5 DAY, '18:03:00', 'manual'),
  (4, CURDATE() - INTERVAL 4 DAY, '07:16:00', 'qr'),
  (4, CURDATE() - INTERVAL 3 DAY, '18:29:00', 'card'),
  (4, CURDATE() - INTERVAL 1 DAY, '18:55:00', 'qr'),
  (4, CURDATE(), '07:08:00', 'card'),
  (5, CURDATE() - INTERVAL 10 DAY, '19:05:00', 'card'),
  (5, CURDATE() - INTERVAL 9 DAY, '08:18:00', 'manual'),
  (5, CURDATE() - INTERVAL 7 DAY, '08:44:00', 'card'),
  (5, CURDATE() - INTERVAL 6 DAY, '19:57:00', 'manual'),
  (5, CURDATE() - INTERVAL 4 DAY, '19:23:00', 'card'),
  (5, CURDATE() - INTERVAL 3 DAY, '08:36:00', 'manual'),
  (5, CURDATE() - INTERVAL 2 DAY, '19:49:00', 'qr'),
  (5, CURDATE(), '19:15:00', 'manual'),
  (6, CURDATE() - INTERVAL 13 DAY, '17:-27:00', 'manual'),
  (6, CURDATE() - INTERVAL 12 DAY, '06:-14:00', 'qr'),
  (6, CURDATE() - INTERVAL 11 DAY, '17:-1:00', 'card'),
  (6, CURDATE() - INTERVAL 9 DAY, '17:25:00', 'qr'),
  (6, CURDATE() - INTERVAL 8 DAY, '06:38:00', 'card'),
  (6, CURDATE() - INTERVAL 6 DAY, '06:04:00', 'qr'),
  (6, CURDATE() - INTERVAL 5 DAY, '17:17:00', 'card'),
  (6, CURDATE() - INTERVAL 3 DAY, '17:43:00', 'qr'),
  (6, CURDATE() - INTERVAL 2 DAY, '06:56:00', 'card'),
  (6, CURDATE() - INTERVAL 1 DAY, '17:09:00', 'manual'),
  (8, CURDATE() - INTERVAL 14 DAY, '08:-26:00', 'qr'),
  (8, CURDATE() - INTERVAL 13 DAY, '19:-13:00', 'card'),
  (8, CURDATE() - INTERVAL 11 DAY, '19:13:00', 'qr'),
  (8, CURDATE() - INTERVAL 10 DAY, '08:26:00', 'card'),
  (8, CURDATE() - INTERVAL 9 DAY, '19:39:00', 'manual'),
  (8, CURDATE() - INTERVAL 7 DAY, '19:05:00', 'card'),
  (8, CURDATE() - INTERVAL 6 DAY, '08:18:00', 'manual'),
  (8, CURDATE() - INTERVAL 4 DAY, '08:44:00', 'card'),
  (8, CURDATE() - INTERVAL 3 DAY, '19:57:00', 'manual'),
  (8, CURDATE() - INTERVAL 1 DAY, '19:23:00', 'card'),
  (8, CURDATE(), '08:36:00', 'manual'),
  (9, CURDATE() - INTERVAL 20 DAY, '17:-37:00', 'card'),
  (9, CURDATE() - INTERVAL 19 DAY, '06:-24:00', 'manual'),
  (9, CURDATE() - INTERVAL 18 DAY, '17:-11:00', 'qr'),
  (9, CURDATE() - INTERVAL 16 DAY, '17:-45:00', 'manual'),
  (9, CURDATE() - INTERVAL 15 DAY, '06:-32:00', 'qr'),
  (9, CURDATE() - INTERVAL 13 DAY, '06:-6:00', 'manual'),
  (9, CURDATE() - INTERVAL 12 DAY, '17:07:00', 'qr'),
  (9, CURDATE() - INTERVAL 10 DAY, '17:33:00', 'manual'),
  (9, CURDATE() - INTERVAL 9 DAY, '06:46:00', 'qr'),
  (9, CURDATE() - INTERVAL 8 DAY, '17:59:00', 'card'),
  (9, CURDATE() - INTERVAL 6 DAY, '17:25:00', 'qr'),
  (9, CURDATE() - INTERVAL 5 DAY, '06:38:00', 'card'),
  (9, CURDATE() - INTERVAL 3 DAY, '06:04:00', 'qr'),
  (9, CURDATE() - INTERVAL 2 DAY, '17:17:00', 'card'),
  (9, CURDATE(), '17:43:00', 'qr'),
  (11, CURDATE() - INTERVAL 20 DAY, '19:-23:00', 'qr'),
  (11, CURDATE() - INTERVAL 18 DAY, '19:-57:00', 'manual'),
  (11, CURDATE() - INTERVAL 17 DAY, '08:-44:00', 'qr'),
  (11, CURDATE() - INTERVAL 16 DAY, '19:-31:00', 'card'),
  (11, CURDATE() - INTERVAL 14 DAY, '19:-5:00', 'qr'),
  (11, CURDATE() - INTERVAL 13 DAY, '08:08:00', 'card'),
  (11, CURDATE() - INTERVAL 11 DAY, '08:34:00', 'qr'),
  (11, CURDATE() - INTERVAL 10 DAY, '19:47:00', 'card'),
  (11, CURDATE() - INTERVAL 8 DAY, '19:13:00', 'qr'),
  (11, CURDATE() - INTERVAL 7 DAY, '08:26:00', 'card'),
  (11, CURDATE() - INTERVAL 6 DAY, '19:39:00', 'manual'),
  (11, CURDATE() - INTERVAL 4 DAY, '19:05:00', 'card'),
  (11, CURDATE() - INTERVAL 3 DAY, '08:18:00', 'manual'),
  (11, CURDATE() - INTERVAL 1 DAY, '08:44:00', 'card'),
  (11, CURDATE(), '19:57:00', 'manual'),
  (12, CURDATE() - INTERVAL 2 DAY, '06:38:00', 'card'),
  (12, CURDATE(), '06:04:00', 'qr');

/* Accounts: opening balances and some income / expense entries */
UPDATE acc_accounts SET opening_balance = 5000 WHERE id = 1;
UPDATE acc_accounts SET opening_balance = 20000 WHERE id = 2;
INSERT INTO acc_entries (voucher_no, entry_date, type, category_id, account_id, to_account_id, amount, party, description, ref_no) VALUES
  (1, CURDATE() - INTERVAL 25 DAY, 'expense', 20, 2, NULL, 12000, 'Building owner', 'Gym hall rent', 'UPI8812'),
  (2, CURDATE() - INTERVAL 20 DAY, 'expense', 21, 1, NULL, 2350, 'KSEB', 'Electricity bill', ''),
  (3, CURDATE() - INTERVAL 18 DAY, 'expense', 25, 2, NULL, 4800, 'Sports shop Manjeri', '2 punching bags', 'INV-221'),
  (4, CURDATE() - INTERVAL 15 DAY, 'income', 2, 1, NULL, 3000, 'Rahul Das', 'Personal training – 10 sessions', ''),
  (5, CURDATE() - INTERVAL 12 DAY, 'expense', 27, 1, NULL, 600, 'Cleaner', 'Cleaning – 2 weeks', ''),
  (6, CURDATE() - INTERVAL 10 DAY, 'transfer', NULL, 1, 2, 5000, '', 'Cash deposited in bank', ''),
  (7, CURDATE() - INTERVAL 5 DAY, 'income', 3, 1, NULL, 1200, 'Adil Rahman', 'Gloves and hand wraps', ''),
  (8, CURDATE() - INTERVAL 3 DAY, 'expense', 28, 2, NULL, 799, 'Jio', 'Internet', ''),
  (9, CURDATE() - INTERVAL 1 DAY, 'expense', 23, 2, NULL, 15000, 'Coach Anees', 'Trainer salary', 'UPI9921'),
  (10, CURDATE(), 'expense', 31, 1, NULL, 250, 'Shop', 'Drinking water cans', '');

/* A member with a birthday today, for the dashboard */
UPDATE members SET dob = CONCAT('2002-', DATE_FORMAT(CURDATE(), '%m-%d')) WHERE id = 12 AND DATE_FORMAT(CURDATE(), '%m-%d') <> '02-29';

/* An invited member who filled the join form (waiting for approval) and a deactivated member */
INSERT INTO members (id, adm_no, name, phone, gender, place, city, district, pin_code, state, occupation, dob, age, height_cm, weight_kg, bmi,
  hq1, hq2, hq3, hq4, hq5, hq6, hq7, hq8, declaration, join_date, password_hash, card_token, status, invite_token, details_at) VALUES
  (13, 'VM013', 'Faisal Babu', '9645012399', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', '676521', 'Kerala', 'Student', '2005-02-10', 21, 171, 64, 21.9,
   0, 0, 0, 0, 0, 0, 0, 0, 1, CURDATE(), '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', 'a1b2c3d4e5f60713', 'pending', 'c0ffee00c0ffee00c0ffee00c0ffee13', NOW());
UPDATE members SET status = 'inactive', notes = 'Deactivated: stopped coming' WHERE id = 10;

/* Gym leave and a member freeze */
INSERT INTO gym_leaves (from_date, to_date, title, message) VALUES
  (CURDATE() + INTERVAL 5 DAY, CURDATE() + INTERVAL 6 DAY, 'Festival holiday', 'Gym will be closed for the festival. Classes start again the next day as usual.');
INSERT INTO member_freezes (member_id, from_date, to_date, days, extended, reason, note) VALUES
  (4, CURDATE() - INTERVAL 3 DAY, CURDATE() + INTERVAL 4 DAY, 8, 1, 'injury', 'Knee injury, doctor rest');

/* Positions from attendance */
UPDATE members m SET level_id = (SELECT l.id FROM levels l WHERE l.from_day <= GREATEST(1, (SELECT COUNT(*) FROM attendance a WHERE a.member_id = m.id))
  ORDER BY l.from_day DESC LIMIT 1), level_since = CURDATE() WHERE m.level_auto = 1;

/* Complaints */
INSERT INTO complaints (id, member_id, category, subject, status, admin_unread, member_unread, created_at, updated_at) VALUES
  (1, 2, 'equipment', 'Punching bag chain is loose', 'progress', 0, 1, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 1 DAY),
  (2, 8, 'timing', 'Morning batch at 6 am please', 'open', 1, 0, NOW() - INTERVAL 3 HOUR, NOW() - INTERVAL 3 HOUR);
INSERT INTO complaint_msgs (complaint_id, by_admin, message, created_at) VALUES
  (1, 0, 'The chain of the big punching bag near the window is loose and makes noise.', NOW() - INTERVAL 2 DAY),
  (1, 1, 'Thank you, we have ordered a new chain. It will be fixed this week.', NOW() - INTERVAL 1 DAY),
  (2, 0, 'Can we have a 6 am batch? 7 am is late for people going to work.', NOW() - INTERVAL 3 HOUR);

/* Free trial requests */
INSERT INTO join_requests (name, place, phone, program, status, created_at, updated_at) VALUES
  ('Rinshad K', 'Wandoor', '9876512345', 'MMA', 'new', NOW() - INTERVAL 2 HOUR, NOW() - INTERVAL 2 HOUR),
  ('Akhil Raj', 'Manjeri', '9876523456', 'Boxing', 'following', NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 1 DAY);
