<?php
// DayBill Van Relay — settings. Copy this file to  relay_config.php  and fill it in.
// relay_config.php is private: never share it (it holds the shop key and the DB password).

// 1) MySQL database (Hostinger ▸ Databases ▸ MySQL Databases ▸ create one)
define('DB_DRIVER', 'mysql');                 // 'mysql' on Hostinger ('sqlite' only for testing)
define('DB_HOST', 'localhost');
define('DB_NAME', 'u123456789_daybillvan');
define('DB_USER', 'u123456789_van');
define('DB_PASS', 'CHANGE-ME');
define('DB_SQLITE_FILE', __DIR__ . '/data/relay.sqlite');

// 2) Shop key: a long random secret. Type the SAME key in DayBill ▸ Mobile & Van ▸ Van (internet).
define('SHOP_KEY', 'CHANGE-ME-to-a-long-random-key-40-characters');
