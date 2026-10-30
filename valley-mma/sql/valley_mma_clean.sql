/* =====================================================================
   VALLEY MMA FIGHT CLUB – PANDIKKAD
   Clean database: all tables + default settings. No sample members.

   HOW TO USE (phpMyAdmin / XAMPP)
     1. Create a database named  valley_mma  (collation utf8mb4_unicode_ci)
     2. Open it → Import → choose this file → Go
     3. Open the app and log in:   admin / admin123
     4. Change the password at once: Settings → Change my password

   Safe to import again: existing tables and data are not touched.
   ===================================================================== */

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;


/* =====================================================================
   1. ADMIN LOGIN
   ===================================================================== */

CREATE TABLE IF NOT EXISTS admins (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(50)  NOT NULL UNIQUE,
  full_name     VARCHAR(100) NOT NULL DEFAULT '',
  password_hash VARCHAR(255) NOT NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* Wrong-password lock (8 tries in 15 minutes) */
CREATE TABLE IF NOT EXISTS login_attempts (
  ip       VARCHAR(45) NOT NULL,
  tried_at DATETIME    NOT NULL,
  KEY idx_ip (ip, tried_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


/* =====================================================================
   2. SETTINGS (changed later in the app: Settings page)
   ===================================================================== */

CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(50) NOT NULL PRIMARY KEY,
  v TEXT        NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


/* =====================================================================
   3. MEMBERSHIP PLANS
   ===================================================================== */

CREATE TABLE IF NOT EXISTS plans (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name           VARCHAR(100)  NOT NULL,
  duration_value INT UNSIGNED  NOT NULL DEFAULT 1,
  duration_unit  ENUM('day','month') NOT NULL DEFAULT 'month',
  price          DECIMAL(10,2) NOT NULL DEFAULT 0,
  description    VARCHAR(500)  NOT NULL DEFAULT '',
  active         TINYINT(1)    NOT NULL DEFAULT 1,
  sort_order     INT           NOT NULL DEFAULT 0,
  created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


/* =====================================================================
   4. MEMBERS (join form fields + membership + login)
   ===================================================================== */

CREATE TABLE IF NOT EXISTS members (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  adm_no          VARCHAR(20)  NOT NULL UNIQUE,
  name            VARCHAR(100) NOT NULL,
  phone           VARCHAR(20)  NOT NULL,
  photo           VARCHAR(100) NOT NULL DEFAULT '',

  /* Client information */
  address         VARCHAR(255) NOT NULL DEFAULT '',
  place           VARCHAR(100) NOT NULL DEFAULT '',
  city            VARCHAR(100) NOT NULL DEFAULT '',
  district        VARCHAR(100) NOT NULL DEFAULT '',
  post            VARCHAR(100) NOT NULL DEFAULT '',
  pin_code        VARCHAR(10)  NOT NULL DEFAULT '',
  state           VARCHAR(100) NOT NULL DEFAULT '',
  occupation      VARCHAR(100) NOT NULL DEFAULT '',
  dob             DATE NULL,
  age             TINYINT UNSIGNED NULL,
  gender          ENUM('','M','F') NOT NULL DEFAULT '',
  height_cm       DECIMAL(5,1) NULL,
  weight_kg       DECIMAL(5,1) NULL,

  /* Health */
  blood_group     VARCHAR(5)   NOT NULL DEFAULT '',
  bmi             DECIMAL(4,1) NULL,
  urea_creat_uric VARCHAR(50)  NOT NULL DEFAULT '',
  hba1c           VARCHAR(20)  NOT NULL DEFAULT '',
  hq1 TINYINT(1) NULL,   /* health questions 1-8:      */
  hq2 TINYINT(1) NULL,   /* 1 = yes, 0 = no,           */
  hq3 TINYINT(1) NULL,   /* NULL = not answered        */
  hq4 TINYINT(1) NULL,
  hq5 TINYINT(1) NULL,
  hq6 TINYINT(1) NULL,
  hq7 TINYINT(1) NULL,
  hq8 TINYINT(1) NULL,
  health_notes    VARCHAR(500) NOT NULL DEFAULT '',
  declaration     TINYINT(1)   NOT NULL DEFAULT 0,
  trainer_name    VARCHAR(100) NOT NULL DEFAULT '',

  /* Membership */
  join_date       DATE NOT NULL,
  plan_id         INT UNSIGNED NULL,
  start_date      DATE NULL,
  expiry_date     DATE NULL,

  /* Member app login, ID card QR, status */
  password_hash   VARCHAR(255) NULL,
  card_token      CHAR(16) NOT NULL,
  status          ENUM('pending','active','inactive') NOT NULL DEFAULT 'active',  /* pending = invited, waiting for approval; inactive = deactivated */
  invite_token    CHAR(32) NULL,
  details_at      DATETIME NULL,
  rules_accepted_at DATETIME NULL,
  approved_at     DATETIME NULL,
  /* Position (level): changes by attendance when level_auto = 1, or set by the admin */
  level_id        INT UNSIGNED NULL,
  level_auto      TINYINT(1) NOT NULL DEFAULT 1,
  level_since     DATE NULL,
  /* old students: attendance days before the app (counted for the position) */
  att_opening     SMALLINT UNSIGNED NOT NULL DEFAULT 0,

  notes           VARCHAR(500) NOT NULL DEFAULT '',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uq_card (card_token),
  KEY idx_phone  (phone),
  KEY idx_status (status),
  KEY idx_expiry (expiry_date),
  KEY idx_name   (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


/* =====================================================================
   5. PAYMENTS (receipts)
   ===================================================================== */

CREATE TABLE IF NOT EXISTS payments (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  receipt_no    INT UNSIGNED  NOT NULL UNIQUE,
  /* opening = old balance of an old student (paid 0) */
  kind          ENUM('normal','opening') NOT NULL DEFAULT 'normal',
  member_id     INT UNSIGNED  NOT NULL,
  plan_id       INT UNSIGNED  NULL,
  pay_date      DATE          NOT NULL,
  admission_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
  plan_fee      DECIMAL(10,2) NOT NULL DEFAULT 0,
  other_fee     DECIMAL(10,2) NOT NULL DEFAULT 0,
  other_note    VARCHAR(100)  NOT NULL DEFAULT '',
  total         DECIMAL(10,2) NOT NULL DEFAULT 0,
  paid          DECIMAL(10,2) NOT NULL DEFAULT 0,
  method        ENUM('cash','upi','card','bank') NOT NULL DEFAULT 'cash',
  upi_ref       VARCHAR(50)   NOT NULL DEFAULT '',
  period_start  DATE NULL,
  period_end    DATE NULL,
  prev_plan_id  INT UNSIGNED NULL,   /* membership before this payment,  */
  prev_start    DATE NULL,           /* put back when the payment is     */
  prev_expiry   DATE NULL,           /* deleted                          */
  note          VARCHAR(255)  NOT NULL DEFAULT '',
  created_by    INT UNSIGNED  NULL,
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_member (member_id),
  KEY idx_date   (pay_date),
  CONSTRAINT fk_pay_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


/* =====================================================================
   6. ATTENDANCE (one row per member per day)
   ===================================================================== */

CREATE TABLE IF NOT EXISTS attendance (
  id        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  member_id INT UNSIGNED NOT NULL,
  att_date  DATE NOT NULL,
  check_in  TIME NOT NULL,
  method    ENUM('qr','card','manual') NOT NULL DEFAULT 'manual',
  UNIQUE KEY uq_member_day (member_id, att_date),
  KEY idx_date (att_date),
  CONSTRAINT fk_att_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


/* =====================================================================
   7. WEEKLY TRAINING PLAN ("Valley daily")  day 1 = Monday … 7 = Sunday
   ===================================================================== */

CREATE TABLE IF NOT EXISTS activities (
  day_no   TINYINT UNSIGNED NOT NULL,
  slot     ENUM('warmup','primary','secondary','finisher','cooldown') NOT NULL,
  activity VARCHAR(200) NOT NULL DEFAULT '',
  PRIMARY KEY (day_no, slot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


/* =====================================================================
   8. ACCOUNTS (cash / bank, income & expense)
   Membership payments count as income automatically – not copied here.
   ===================================================================== */

CREATE TABLE IF NOT EXISTS acc_accounts (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name            VARCHAR(60)   NOT NULL,
  kind            ENUM('cash','bank','upi') NOT NULL DEFAULT 'cash',
  opening_balance DECIMAL(12,2) NOT NULL DEFAULT 0,
  active          TINYINT(1)    NOT NULL DEFAULT 1,
  sort_order      INT           NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS acc_categories (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(60) NOT NULL,
  type       ENUM('income','expense') NOT NULL,
  active     TINYINT(1)  NOT NULL DEFAULT 1,
  sort_order INT         NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS acc_entries (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  voucher_no    INT UNSIGNED  NOT NULL,
  entry_date    DATE          NOT NULL,
  type          ENUM('income','expense','transfer') NOT NULL,
  category_id   INT UNSIGNED  NULL,
  account_id    INT UNSIGNED  NOT NULL,
  to_account_id INT UNSIGNED  NULL,     /* only for transfers */
  amount        DECIMAL(12,2) NOT NULL,
  party         VARCHAR(100)  NOT NULL DEFAULT '',
  description   VARCHAR(255)  NOT NULL DEFAULT '',
  ref_no        VARCHAR(50)   NOT NULL DEFAULT '',
  created_by    INT UNSIGNED  NULL,
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_date (entry_date),
  KEY idx_cat  (category_id),
  KEY idx_acc  (account_id)
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





/* =====================================================================
   DEFAULT DATA
   ===================================================================== */

/* Admin login: admin / admin123  – change it after the first login! */
INSERT IGNORE INTO admins (id, username, full_name, password_hash) VALUES
  (1, 'admin', 'Admin', '$2y$10$CVXY22uV3LDS3ukVMDSFsOWqvPFb.cIbm8teAIWfdamzQzv1r4oAW');

/* Gym details, UPI, alerts, attendance, backup */
INSERT IGNORE INTO settings (k, v) VALUES
  ('gym_name',          'VALLEY MMA'),
  ('gym_tagline',       'FIGHT CLUB'),
  ('gym_place',         'PANDIKKAD'),
  ('phone1',            '+91 8075 112 402'),
  ('phone2',            '+91 7012 613 829'),
  ('upi_id',            ''),
  ('upi_name',          'Valley MMA Fight Club'),
  ('upi_phone',         ''),
  ('country_code',      '91'),
  ('admission_fee',     '500'),
  ('expiry_days',       '7'),
  ('absent_days',       '7'),
  ('trial_days',        '7'),
  ('default_lang',      'en'),
  ('att_default',       'qr'),
  ('att_order',         'qr,card,manual'),
  ('att_camera',        'environment'),
  ('att_refresh',       '0'),
  ('att_block_expired', '0'),
  ('auto_backup',       '1'),
  ('backup_keep',       '14'),
  ('acc_fee_category',  '1'),
  ('acc_map_cash',      '1'),
  ('acc_map_upi',       '2'),
  ('acc_map_card',      '2'),
  ('acc_map_bank',      '2'),
  ('schema_version',    '7');

/* Membership plans (change prices in the app: Plans) */
INSERT IGNORE INTO plans (id, name, duration_value, duration_unit, price, description, sort_order) VALUES
  (1, 'Monthly',   1, 'month',  1500, 'MMA, boxing, kickboxing and fitness training', 1),
  (2, '3 Months',  3, 'month',  4000, 'MMA, boxing, kickboxing and fitness training', 2),
  (3, '6 Months',  6, 'month',  7500, 'MMA, boxing, kickboxing and fitness training', 3),
  (4, 'Yearly',   12, 'month', 14000, 'MMA, boxing, kickboxing and fitness training', 4);

/* Weekly training plan */
INSERT IGNORE INTO activities (day_no, slot, activity) VALUES
  (1, 'warmup', ''), (1, 'primary', 'Full body - HIIT / EMOM / AMRAP'),  (1, 'secondary', 'Tec. Sparring'), (1, 'finisher', 'Batch drills'), (1, 'cooldown', ''),
  (2, 'warmup', ''), (2, 'primary', 'Shadow'),                           (2, 'secondary', 'Updation'),      (2, 'finisher', 'Neck'),         (2, 'cooldown', ''),
  (3, 'warmup', ''), (3, 'primary', 'Sprint / agility / cross country'), (3, 'secondary', 'Bag STD'),       (3, 'finisher', 'Abs'),          (3, 'cooldown', ''),
  (4, 'warmup', ''), (4, 'primary', 'Upper body'),                       (4, 'secondary', 'Pad work'),      (4, 'finisher', 'Wrist'),        (4, 'cooldown', ''),
  (5, 'warmup', ''), (5, 'primary', 'Lower body'),                       (5, 'secondary', 'Bag A / Bag B'), (5, 'finisher', 'Neck'),         (5, 'cooldown', ''),
  (6, 'warmup', ''), (6, 'primary', 'Strategic shadow / swimming'),      (6, 'secondary', 'Batch drills'),  (6, 'finisher', 'Abs'),          (6, 'cooldown', ''),
  (7, 'warmup', ''), (7, 'primary', ''),                                 (7, 'secondary', ''),              (7, 'finisher', ''),             (7, 'cooldown', '');

/* Money accounts (enter opening balances in the app: Accounts → Accounts setup) */
INSERT IGNORE INTO acc_accounts (id, name, kind, opening_balance, sort_order) VALUES
  (1, 'Cash',       'cash', 0, 1),
  (2, 'Bank / UPI', 'bank', 0, 2);

/* Income and expense categories */
INSERT IGNORE INTO acc_categories (id, name, type, sort_order) VALUES
  (1,  'Membership fees',       'income',  1),
  (2,  'Personal training',     'income',  2),
  (3,  'Equipment sale',        'income',  3),
  (4,  'Events / tournaments',  'income',  4),
  (5,  'Other income',          'income',  9),
  (20, 'Rent',                  'expense', 1),
  (21, 'Electricity',           'expense', 2),
  (22, 'Water',                 'expense', 3),
  (23, 'Trainer salary',        'expense', 4),
  (24, 'Staff salary',          'expense', 5),
  (25, 'Equipment',             'expense', 6),
  (26, 'Maintenance / repairs', 'expense', 7),
  (27, 'Cleaning',              'expense', 8),
  (28, 'Internet / phone',      'expense', 9),
  (29, 'Marketing',             'expense', 10),
  (30, 'Tournament fees',       'expense', 11),
  (31, 'Other expense',         'expense', 19);

SET FOREIGN_KEY_CHECKS = 1;

/* Done. 11 tables. Log in with admin / admin123. */
