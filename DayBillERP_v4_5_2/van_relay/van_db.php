<?php
// ============================================================
// DayBill Van Relay — settings + database (tables are made on first use)
// Used by van_api.php and check.php. Opening this file in a browser
// shows nothing (and .htaccess blocks it). (Was db.php before 5.23.2 — a new
// name, so PHP can never run an old saved copy right after an update.)
// ============================================================
if (!defined('RELAY_VERSION')) define('RELAY_VERSION', '5.23.2');

class RelayError extends Exception {}

// Every answer of the relay: never kept in any cache (browser, LiteSpeed, CDN).
function relay_headers($type) {
    if (headers_sent()) return;
    header('Content-Type: ' . $type);
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
    header('Pragma: no-cache');
    header('Expires: 0');
    header('X-LiteSpeed-Cache-Control: no-cache');
    header('X-Robots-Tag: noindex, nofollow');
}

// https as the visitor sees it (Hostinger's CDN / proxy talks to PHP over http
// and tells the real one in X-Forwarded-Proto).
function relay_is_https() {
    if (!empty($_SERVER['HTTPS']) && strtolower((string)$_SERVER['HTTPS']) !== 'off') return true;
    if ((string)($_SERVER['SERVER_PORT'] ?? '') === '443') return true;
    if (strtolower((string)($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '')) === 'https') return true;
    if (strtolower((string)($_SERVER['HTTP_X_FORWARDED_SSL'] ?? '')) === 'on') return true;
    if (stripos((string)($_SERVER['HTTP_CF_VISITOR'] ?? ''), 'https') !== false) return true;
    return false;
}

function relay_load_config() {
    static $ok = null;
    if ($ok !== null) return $ok;
    $f = __DIR__ . '/relay_config.php';
    if (!is_file($f)) return $ok = false;
    require_once $f;
    return $ok = defined('DB_DRIVER') && defined('SHOP_KEY');
}

// MySQL error number → plain words (never shows the user name or password)
function relay_db_hint($e) {
    $c = 0;
    if (preg_match('/\[(\d{4})\]/', $e->getMessage(), $m)) $c = (int)$m[1];
    switch ($c) {
        case 1045: return 'wrong database user name or password';
        case 1044: return 'the user has no rights on this database — add the user to the database in hPanel';
        case 1049: return 'database name not found';
        case 2002: case 2003: case 2005: return 'database host not found — use localhost';
        default: return $c ? 'MySQL error ' . $c : 'database error';
    }
}

function relay_db() {
    static $pdo = null;
    if ($pdo) return $pdo;
    if (!relay_load_config())
        throw new RelayError('Relay not set up: relay_config.php is missing. Make it in DayBill ▸ Mobile & Van ▸ Van (internet) ▸ Make upload folder, and upload it next to van_api.php.');
    try {
        if (DB_DRIVER === 'sqlite') {
            @mkdir(dirname(DB_SQLITE_FILE), 0700, true);
            $pdo = new PDO('sqlite:' . DB_SQLITE_FILE);
        } else {
            if (!extension_loaded('pdo_mysql')) throw new RelayError('PHP has no MySQL (pdo_mysql). hPanel ▸ Advanced ▸ PHP Configuration ▸ Extensions ▸ tick pdo_mysql.');
            $pdo = new PDO('mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4', DB_USER, DB_PASS,
                           [PDO::ATTR_TIMEOUT => 10]);
        }
    } catch (PDOException $e) {
        $pdo = null;
        throw new RelayError("The relay can't open its database (" . relay_db_hint($e) . '). Check DB_NAME, DB_USER and DB_PASS in relay_config.php.');
    }
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    relay_schema($pdo);
    return $pdo;
}

function relay_schema($pdo) {
    $big = DB_DRIVER === 'sqlite' ? 'TEXT' : 'LONGTEXT';
    $id = DB_DRIVER === 'sqlite' ? 'INTEGER PRIMARY KEY AUTOINCREMENT' : 'INT AUTO_INCREMENT PRIMARY KEY';
    $eng = DB_DRIVER === 'sqlite' ? '' : ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4';
    $pdo->exec("CREATE TABLE IF NOT EXISTS vr_vans (van_code VARCHAR(20) PRIMARY KEY, name VARCHAR(100),
        pin_hash VARCHAR(200), user_id INT, active INT DEFAULT 1, device_seq INT DEFAULT 0)$eng");
    $pdo->exec("CREATE TABLE IF NOT EXISTS vr_tokens (token VARCHAR(64) PRIMARY KEY, van_code VARCHAR(20),
        device VARCHAR(120), created_at VARCHAR(20), last_seen VARCHAR(20))$eng");
    $pdo->exec("CREATE TABLE IF NOT EXISTS vr_catalog (id INT PRIMARY KEY, version VARCHAR(20),
        body $big, updated_at VARCHAR(20))$eng");
    $pdo->exec("CREATE TABLE IF NOT EXISTS vr_docs (id $id, uid VARCHAR(64) UNIQUE, van_code VARCHAR(20),
        device VARCHAR(120), doc $big, status VARCHAR(20) DEFAULT 'new', result VARCHAR(400),
        created_at VARCHAR(20), done_at VARCHAR(20))$eng");
    $pdo->exec("CREATE TABLE IF NOT EXISTS vr_fails (van_code VARCHAR(20), at INT)$eng");
    // relays made by DayBill 5.23.0 before device_seq existed
    try { $pdo->query('SELECT device_seq FROM vr_vans LIMIT 1'); }
    catch (Throwable $e) { $pdo->exec('ALTER TABLE vr_vans ADD device_seq INT DEFAULT 0'); }
}
