/* Monthly class timetable: one row per class (batch on a date) with its trainer.
   Trainers are logins in the admins table with role 'trainer' and limited rights. */
CREATE TABLE IF NOT EXISTS timetable_months (
  month CHAR(7) NOT NULL PRIMARY KEY,
  /* weekly holidays of that month: 1 = Monday … 7 = Sunday, e.g. '67' */
  holidays VARCHAR(7) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS class_sessions (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  class_date DATE NOT NULL,
  batch_id INT UNSIGNED NOT NULL,
  trainer_id INT UNSIGNED NULL,
  status ENUM('on','off') NOT NULL DEFAULT 'on',
  note VARCHAR(200) NOT NULL DEFAULT '',
  UNIQUE KEY uq_class (class_date, batch_id),
  KEY idx_trainer (trainer_id, class_date),
  CONSTRAINT fk_cs_batch FOREIGN KEY (batch_id) REFERENCES batches (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
