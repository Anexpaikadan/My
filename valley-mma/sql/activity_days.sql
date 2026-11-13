/* Monthly training plan: the plan of one date. A date with no rows here uses the weekly plan (activities). */
CREATE TABLE IF NOT EXISTS activity_days (
  plan_date DATE NOT NULL,
  slot ENUM('warmup','primary','secondary','finisher','cooldown') NOT NULL,
  activity VARCHAR(200) NOT NULL DEFAULT '',
  PRIMARY KEY (plan_date, slot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
