/* Batches (class times): morning batch, evening batch … Members belong to one batch. */
CREATE TABLE IF NOT EXISTS batches (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(60) NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  /* days of the week: 1 = Monday … 7 = Sunday, e.g. '123456' */
  days VARCHAR(7) NOT NULL DEFAULT '123456',
  trainer VARCHAR(100) NOT NULL DEFAULT '',
  trainer_id INT UNSIGNED NULL,
  capacity SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  note VARCHAR(200) NOT NULL DEFAULT '',
  show_public TINYINT(1) NOT NULL DEFAULT 1,
  active TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  KEY idx_active (active, start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO batches (id, name, start_time, end_time, days, sort_order) VALUES
  (1, 'Morning Batch', '06:00:00', '07:30:00', '123456', 1),
  (2, 'Evening Batch', '17:00:00', '18:30:00', '123456', 2),
  (3, 'Night Batch', '19:00:00', '20:30:00', '123456', 3);
