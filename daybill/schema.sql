-- Daybill Print database schema (MySQL / MariaDB)
-- install.php runs this automatically; you can also import it in phpMyAdmin.

CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(50)  NOT NULL UNIQUE,
  full_name     VARCHAR(100) NOT NULL DEFAULT '',
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('admin','employee') NOT NULL DEFAULT 'employee',
  active        TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS jobs (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code          VARCHAR(10)  NOT NULL UNIQUE,
  customer_name VARCHAR(100) NOT NULL DEFAULT '',
  phone         VARCHAR(30)  NOT NULL DEFAULT '',
  note          VARCHAR(500) NOT NULL DEFAULT '',
  status        ENUM('new','printing','done','cancelled') NOT NULL DEFAULT 'new',
  handled_by    INT UNSIGNED NULL,
  amount        DECIMAL(10,2) NOT NULL DEFAULT 0,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_status (status, created_at),
  CONSTRAINT fk_jobs_user FOREIGN KEY (handled_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS job_files (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_id        INT UNSIGNED NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  stored_name   VARCHAR(100) NOT NULL,
  ext           VARCHAR(10)  NOT NULL,
  size_bytes    INT UNSIGNED NOT NULL DEFAULT 0,
  pages_total   INT UNSIGNED NOT NULL DEFAULT 0,
  copies        INT UNSIGNED NOT NULL DEFAULT 1,
  paper         VARCHAR(30)  NOT NULL DEFAULT 'A4',
  color         ENUM('bw','color') NOT NULL DEFAULT 'bw',
  sides         ENUM('single','double') NOT NULL DEFAULT 'single',
  orientation   ENUM('portrait','landscape') NOT NULL DEFAULT 'portrait',
  page_range    VARCHAR(100) NOT NULL DEFAULT '',
  price         DECIMAL(10,2) NULL,
  printer       VARCHAR(200) NOT NULL DEFAULT '',
  status        ENUM('pending','queued','sending','printed','failed') NOT NULL DEFAULT 'pending',
  print_count   INT UNSIGNED NOT NULL DEFAULT 0,
  queued_at     DATETIME NULL,
  last_error    VARCHAR(500) NOT NULL DEFAULT '',
  printed_at    DATETIME NULL,
  printed_by    INT UNSIGNED NULL,
  KEY idx_job (job_id),
  CONSTRAINT fk_files_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_files_user FOREIGN KEY (printed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(50)  NOT NULL PRIMARY KEY,
  v TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO settings (k, v) VALUES
  ('schema_version', '3'),
  ('shop_name', 'Daybill Print'),
  ('print_mode', 'local'),
  ('printer_bw', ''),
  ('printer_color', ''),
  ('printer_map', '{}'),
  ('papers_enabled', 'A4,A3'),
  ('papers_custom', ''),
  ('colors_enabled', 'bw,color'),
  ('sides_enabled', 'single,double'),
  ('pricing', '{"A4":{"bw":{"single":[1,2,1],"double":[1,2,1]},"color":{"single":[1,5,3],"double":[1,5,3]}},"A3":{"bw":{"single":[1,4,2],"double":[1,4,2]},"color":{"single":[1,10,6],"double":[1,10,6]}}}'),
  ('currency', 'SR'),
  ('default_lang', 'en'),
  ('retention_days', '2');
