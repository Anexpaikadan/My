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
