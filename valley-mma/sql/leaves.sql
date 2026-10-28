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
