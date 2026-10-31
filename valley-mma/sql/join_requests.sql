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
