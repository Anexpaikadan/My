-- Daybill Print database schema (MySQL / MariaDB)
-- install.php runs this automatically and then creates the first shop.

CREATE TABLE IF NOT EXISTS shops (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  slug          VARCHAR(40)  NOT NULL UNIQUE,
  name          VARCHAR(100) NOT NULL,
  active        TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  shop_id       INT UNSIGNED NULL,
  username      VARCHAR(50)  NOT NULL UNIQUE,
  full_name     VARCHAR(100) NOT NULL DEFAULT '',
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('super','admin','employee') NOT NULL DEFAULT 'employee',
  active        TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS jobs (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  shop_id       INT UNSIGNED NOT NULL DEFAULT 1,
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
  KEY idx_shop (shop_id, status),
  CONSTRAINT fk_jobs_user FOREIGN KEY (handled_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS job_files (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_id        INT UNSIGNED NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  stored_name   VARCHAR(100) NOT NULL,
  orig_name     VARCHAR(100) NOT NULL DEFAULT '',
  orig_ext      VARCHAR(10)  NOT NULL DEFAULT '',
  ext           VARCHAR(10)  NOT NULL,
  size_bytes    INT UNSIGNED NOT NULL DEFAULT 0,
  pages_total   INT UNSIGNED NOT NULL DEFAULT 0,
  copies        INT UNSIGNED NOT NULL DEFAULT 1,
  paper         VARCHAR(30)  NOT NULL DEFAULT 'A4',
  color         ENUM('bw','color') NOT NULL DEFAULT 'bw',
  sides         ENUM('single','double') NOT NULL DEFAULT 'single',
  orientation   ENUM('portrait','landscape') NOT NULL DEFAULT 'portrait',
  page_range    VARCHAR(100) NOT NULL DEFAULT '',
  layout        VARCHAR(40)  NOT NULL DEFAULT '',
  kind          VARCHAR(10)  NOT NULL DEFAULT '',
  previews      TINYINT UNSIGNED NOT NULL DEFAULT 0,
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
  shop_id INT UNSIGNED NOT NULL DEFAULT 0,
  k       VARCHAR(50)  NOT NULL,
  v       TEXT NOT NULL,
  PRIMARY KEY (shop_id, k)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO settings (shop_id, k, v) VALUES (0, 'schema_version', '7');
