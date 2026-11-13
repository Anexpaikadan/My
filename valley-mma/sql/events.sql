/* Events and fight nights: shown on the public page; members and visitors register */
CREATE TABLE IF NOT EXISTS events (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(150) NOT NULL,
  kind ENUM('fight','event','seminar','grading','camp','other') NOT NULL DEFAULT 'event',
  event_date DATE NOT NULL,
  start_time TIME NULL,
  venue VARCHAR(200) NOT NULL DEFAULT '',
  description TEXT NULL,
  /* media/events/… */
  image VARCHAR(200) NOT NULL DEFAULT '',
  fee DECIMAL(10,2) NOT NULL DEFAULT 0,
  capacity SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  reg_open TINYINT(1) NOT NULL DEFAULT 1,
  reg_last DATE NULL,
  /* visitors (not members) may register too */
  allow_public TINYINT(1) NOT NULL DEFAULT 1,
  show_public TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_date (event_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS event_regs (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  event_id INT UNSIGNED NOT NULL,
  member_id INT UNSIGNED NULL,
  name VARCHAR(100) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  place VARCHAR(100) NOT NULL DEFAULT '',
  /* weight class, category or a note from the person */
  note VARCHAR(200) NOT NULL DEFAULT '',
  status ENUM('registered','confirmed','cancelled') NOT NULL DEFAULT 'registered',
  paid TINYINT(1) NOT NULL DEFAULT 0,
  ip VARCHAR(45) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_event (event_id, status),
  KEY idx_member (member_id),
  CONSTRAINT fk_reg_event FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
  CONSTRAINT fk_reg_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
