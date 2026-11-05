-- Run ONCE on an existing database (phpMyAdmin > SQL)
ALTER TABLE handovers ADD status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'approved' AFTER amount;
