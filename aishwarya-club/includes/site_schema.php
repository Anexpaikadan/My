<?php
// ================================================================
// site_schema.php — tables for the public website (created automatically)
//   club_activities  : programs (photo, suitable for, time, contact person)
//   site_packages    : fee packages (price cards)
//   site_timings     : timing rows (sun / moon)
//   site_rules       : rule sections (one rule per line)
//   enquiries        : "Join the club" requests from the website
// Existing tables only get new columns; nothing is removed.
// ================================================================
require_once __DIR__ . '/config.php';
if (!function_exists('site_tables')) {

function site_tables() {
    static $done = false; if ($done) return; $done = true;
    $q = function ($sql) { try { db()->exec($sql); } catch (Exception $e) {} };
    $q("CREATE TABLE IF NOT EXISTS club_activities(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(150) NOT NULL,emoji VARCHAR(10) DEFAULT '🏆',
        description TEXT,reg_link VARCHAR(500),info_url VARCHAR(500),color VARCHAR(20) DEFAULT '#E30613',is_active TINYINT(1) DEFAULT 1,
        sort_order INT DEFAULT 0,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
    foreach (array("photo VARCHAR(300) NULL","suitable_for VARCHAR(200) NULL","time_text VARCHAR(120) NULL","contact_person VARCHAR(150) NULL",
                   "name_ml VARCHAR(150) NULL","description_ml TEXT NULL") as $col) $q("ALTER TABLE club_activities ADD COLUMN $col");
    $q("CREATE TABLE IF NOT EXISTS site_packages(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(120) NOT NULL,price VARCHAR(40) NOT NULL,
        duration VARCHAR(80),note VARCHAR(250),popular TINYINT(1) DEFAULT 0,sort_order INT DEFAULT 0,is_active TINYINT(1) DEFAULT 1)");
    $q("CREATE TABLE IF NOT EXISTS site_timings(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(120) NOT NULL,days VARCHAR(120),
        time_text VARCHAR(60) NOT NULL,icon VARCHAR(10) DEFAULT 'sun',sort_order INT DEFAULT 0)");
    $q("CREATE TABLE IF NOT EXISTS site_rules(id INT AUTO_INCREMENT PRIMARY KEY,title VARCHAR(150) NOT NULL,body TEXT NOT NULL,sort_order INT DEFAULT 0)");
    $q("CREATE TABLE IF NOT EXISTS enquiries(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(150) NOT NULL,place VARCHAR(150),phone VARCHAR(30) NOT NULL,
        interest VARCHAR(150),ip VARCHAR(45),status VARCHAR(20) DEFAULT 'new',note VARCHAR(250),created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,INDEX(status),INDEX(ip))");
    // "show on public page" switches and shop offer price
    $q("ALTER TABLE gallery_images ADD COLUMN show_public TINYINT(1) DEFAULT 1");
    $q("ALTER TABLE achievements ADD COLUMN show_public TINYINT(1) DEFAULT 1");
    $q("ALTER TABLE market_items ADD COLUMN old_price DECIMAL(10,2) NULL");
    $q("ALTER TABLE market_items ADD COLUMN show_public TINYINT(1) DEFAULT 1");
}

// Club WhatsApp / phone used by the public site
function site_whatsapp() {
    $n = function_exists('site_cfg') ? site_cfg('site_whatsapp', '') : '';
    if ($n === '') $n = setting('CLUB_PHONE', '');
    $d = preg_replace('/\D/', '', $n);
    if (strlen($d) === 10) $d = '91' . $d;
    return $d;
}

}
