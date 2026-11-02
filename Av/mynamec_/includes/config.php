<?php
// ============================================================
//  config.php — PHP 7.3+ compatible (works on all Hostinger)
// ============================================================
define('DB_HOST',    'YOUR_DB_HOST');
define('DB_NAME',    'YOUR_DB_NAME');
define('DB_USER',    'YOUR_DB_USER');
define('DB_PASS',    'YOUR_DB_PASSWORD'); // real value lives only on the server
define('DB_CHARSET', 'utf8mb4');

// ── Static defaults (fallbacks if DB not available) ───────────
define('SITE_URL',     'https://mynamecc.online/');
define('LOGO_URL',     'https://mynamecc.online/assets/logo.jpg');
define('ULTRAMSG_TOKEN',    'YOUR_TOKEN');
define('ULTRAMSG_INSTANCE', 'YOUR_INSTANCE');
define('OTP_EXPIRY_MIN',  10);
date_default_timezone_set('Asia/Kolkata');

// ── Auto BASE URL — PHP 7.3 compatible (no str_ends_with) ────
if (!defined('BASE')) {
    $script = str_replace('\\', '/', isset($_SERVER['SCRIPT_NAME']) ? $_SERVER['SCRIPT_NAME'] : '/index.php');
    $dir    = rtrim(dirname($script), '/');
    // Remove /modules suffix — PHP 7.3 compatible
    if (substr($dir, -8) === '/modules') {
        $dir = dirname($dir);
    }
    define('BASE', ($dir === '/' ? '' : $dir));
}
function url($p) { return BASE . '/' . ltrim($p, '/'); }

// ── Logo base64 ───────────────────────────────────────────────
function getLogoB64() {
    static $b = null;
    if ($b === null) {
        $paths = [
            __DIR__ . '/../assets/logo.jpg',
            __DIR__ . '/assets/logo.jpg',
            dirname(__DIR__) . '/assets/logo.jpg',
        ];
        $b = '';
        foreach ($paths as $p) {
            if (file_exists($p)) {
                $b = 'data:image/jpeg;base64,' . base64_encode(file_get_contents($p));
                break;
            }
        }
    }
    return $b;
}

// ── Member photo base64 ───────────────────────────────────────
function getMemberPhoto($filename) {
    if (!$filename || $filename === 'default.png') return '';
    $paths = array(
        __DIR__ . '/../assets/uploads/' . $filename,
        __DIR__ . '/assets/uploads/' . $filename,
        dirname(__DIR__) . '/assets/uploads/' . $filename,
        // Also check profiles/ subfolder with just basename (legacy support)
        __DIR__ . '/../assets/uploads/profiles/' . basename($filename),
    );
    foreach ($paths as $p) {
        if (file_exists($p)) {
            $ext  = strtolower(pathinfo($p, PATHINFO_EXTENSION));
            $mime = in_array($ext, ['png','gif']) ? 'image/' . $ext : 'image/jpeg';
            return 'data:' . $mime . ';base64,' . base64_encode(file_get_contents($p));
        }
    }
    return '';
}

// ════════════════════════════════════════════════════════════
//  SESSION — persistent login on Hostinger shared hosting
//  Own session folder so other sites' garbage-collection can't
//  delete our files early (the real cause of forced re-login).
//  Cookie window slides forward on every visit while logged in.
// ════════════════════════════════════════════════════════════
if (session_status() === PHP_SESSION_NONE) {
    // Own session folder (next to includes/) — survives shared GC
    $sessPath = dirname(__DIR__) . '/sessions';
    if (!is_dir($sessPath)) { @mkdir($sessPath, 0700, true); }
    if (is_dir($sessPath) && is_writable($sessPath)) {
        session_save_path($sessPath);
    }

    $lifetime = 60 * 60 * 24 * 30; // ← CHANGE LOGIN DURATION HERE (30 days)

    ini_set('session.gc_maxlifetime', $lifetime);
    ini_set('session.cookie_httponly', 1);
    ini_set('session.cookie_secure',   1);
    ini_set('session.cookie_lifetime', $lifetime);

    session_set_cookie_params(array(
        'lifetime' => $lifetime,
        'path'     => '/',
        'secure'   => true,
        'httponly' => true,
        'samesite' => 'Lax',   // lets shared/WhatsApp links send the cookie
    ));

    session_start();

    // Slide the window forward on each visit while logged in
    if (!empty($_SESSION['user_id'])) {
        setcookie(session_name(), session_id(), array(
            'expires'  => time() + $lifetime,
            'path'     => '/',
            'secure'   => true,
            'httponly' => true,
            'samesite' => 'Lax',
        ));
    }
}

// ── PDO ───────────────────────────────────────────────────────
function db() {
    static $pdo = null;
    if ($pdo === null) {
        try {
            $pdo = new PDO(
                'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=' . DB_CHARSET,
                DB_USER, DB_PASS,
                array(
                    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES   => false,
                )
            );
        } catch (PDOException $e) {
            die('<div style="font:14px sans-serif;padding:2rem;color:#B71C1C;background:#FFEBEE;border-radius:8px;margin:1rem">
                <b>Database Error</b><br>Cannot connect to MySQL.<br>
                Edit <code>includes/config.php</code> with your DB credentials.<br><br>
                <code>' . htmlspecialchars($e->getMessage()) . '</code></div>');
        }
    }
    return $pdo;
}

// ── Auth ──────────────────────────────────────────────────────

// ── Club Settings: load from DB, override config defaults ──────
define('CLUB_NAME',    'Aishwarya Arts & Sports Club');
define('CLUB_PLACE',   'Vettikkattiri');
define('CLUB_TAGLINE', 'Unity · Sports · Culture · Community');
define('CLUB_PHONE',   '+919876543210');
define('CLUB_WA_GROUP','https://chat.whatsapp.com/YOUR_GROUP_LINK');
define('FEE_MONTHLY',  100);
define('FEE_ANNUAL',   1000);

function setting($const, $default='') {
    static $cache = null;
    if ($cache === null) {
        $cache = array();
        $keyMap = array(
            'club_name'    => 'CLUB_NAME',
            'club_place'   => 'CLUB_PLACE',
            'club_tagline' => 'CLUB_TAGLINE',
            'club_phone'   => 'CLUB_PHONE',
            'club_wa_group'=> 'CLUB_WA_GROUP',
            'fee_monthly'  => 'FEE_MONTHLY',
            'fee_annual'   => 'FEE_ANNUAL',
            'upi_id'       => 'UPI_ID',
            'bank_name'    => 'BANK_NAME',
            'account_name' => 'ACCOUNT_NAME',
            'account_no'   => 'ACCOUNT_NO',
            'ifsc'         => 'IFSC',
        );
        try {
            $rows = db()->query("SELECT setting_key,setting_value FROM club_settings")->fetchAll(PDO::FETCH_ASSOC);
            foreach ($rows as $r) {
                if (!empty($r['setting_value'])) {
                    $mapped = isset($keyMap[$r['setting_key']]) ? $keyMap[$r['setting_key']] : strtoupper($r['setting_key']);
                    $cache[$mapped] = $r['setting_value'];
                }
            }
        } catch(Exception $e){}
    }
    if (isset($cache[$const])) return $cache[$const];
    if ($default !== '') return $default;
    return defined($const) ? constant($const) : '';
}

function isLoggedIn() { return !empty($_SESSION['user_id']); }

function currentUser() {
    if (!isLoggedIn()) return null;
    $s = db()->prepare('SELECT * FROM users WHERE id=?');
    $s->execute(array($_SESSION['user_id']));
    return $s->fetch() ?: null;
}

function requireLogin() {
    if (!isLoggedIn()) { header('Location:' . url('index.php')); exit; }
}

function requireAdmin() {
    requireLogin();
    $u = currentUser();
    // Full club admins: developer + secretary (legacy callers use this for the Admin Panel)
    if (!isFullAdmin($u)) {
        header('Location:' . url('dashboard.php') . '?err=access'); exit;
    }
}

// ── Helpers ───────────────────────────────────────────────────
function h($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function waLink($p) { return 'https://wa.me/' . preg_replace('/\D/', '', $p); }
function generateOTP() { return str_pad((string)random_int(0, 999999), 6, '0', STR_PAD_LEFT); }

// Phone normalise — PHP 7.3 compatible (no str_starts_with)
function normalisePhone($raw) {
    $raw = trim($raw);
    if (substr($raw, 0, 1) === '+') return $raw;
    return '+91' . ltrim($raw, '0');
}

// ── Role helpers — PHP 7.3 compatible (no match()) ───────────
function roleLabel($r) {
    $map = array(
        'president'          => 'President',
        'vice_president'     => 'Vice President',
        'secretary'          => 'Secretary',
        'developer'          => 'Developer (Super Admin)',
        'guest_admin'        => 'Guest Admin',
        'joint_secretary'    => 'Joint Secretary',
        'treasurer'          => 'Treasurer',
        'sports_committee'   => 'Sports Committee',
        'cultural_committee' => 'Cultural Committee',
        'finance_committee'  => 'Finance Committee',
        'committee_member'   => 'Committee Member',
        'member'             => 'Member',
    );
    return isset($map[$r]) ? $map[$r] : 'Member';
}

function isAdminRole($r) {
    return in_array($r, array('secretary','developer','guest_admin'));
}

// ═══════════════════════════════════════════════════════════════
//  STRUCTURED PERMISSION SYSTEM
//  developer = Super Admin (locked, can do everything incl. Settings & roles)
//  secretary = Admin (everything EXCEPT Settings & role management)
//  guest_admin = temporary admin, scoped to assigned modules, with expiry
//  module admin = any member assigned to specific module(s)
// ═══════════════════════════════════════════════════════════════

// Super admin — only the Developer. Locked role.
function isSuperAdmin($user = null) {
    if ($user === null) { $user = function_exists('currentUser') ? currentUser() : null; }
    return $user && ($user['role'] ?? '') === 'developer';
}
// Can this user change roles / assign module admins / open Settings? → Developer ONLY
function canManageRoles($user = null) {
    return isSuperAdmin($user);
}
function canAccessSettings($user = null) {
    return isSuperAdmin($user);
}
// Full club admin (Admin Panel: approvals etc.) → developer + secretary
function isFullAdmin($user = null) {
    if ($user === null) { $user = function_exists('currentUser') ? currentUser() : null; }
    if (!$user) return false;
    return in_array($user['role'] ?? '', array('developer','secretary'));
}
// A role that can NEVER be changed/removed by anyone
function isLockedRole($role) {
    return $role === 'developer';
}

// Require full admin (Admin Panel). Developer + Secretary.
function requireFullAdmin() {
    requireLogin();
    if (!isFullAdmin(currentUser())) { header('Location:'.url('dashboard.php').'?err=access'); exit; }
}
// Require super admin (Settings, role management). Developer only.
function requireSuperAdmin() {
    requireLogin();
    if (!isSuperAdmin(currentUser())) { header('Location:'.url('dashboard.php').'?err=access'); exit; }
}

function canPost($r) {
    return in_array($r, array('president','vice_president','secretary','developer','guest_admin','joint_secretary','treasurer','sports_committee','cultural_committee','finance_committee'));
}

function catIcon($c) {
    $map = array(
        'sports'      => '⚽',
        'cultural'    => '🎭',
        'charity'     => '🤝',
        'urgent'      => '🚨',
        'achievement' => '🏆',
    );
    return isset($map[$c]) ? $map[$c] : '📢';
}

function catColor($c) {
    $map = array(
        'sports'      => '#1565C0',
        'cultural'    => '#7B1FA2',
        'charity'     => '#2E7D32',
        'urgent'      => '#C62828',
        'achievement' => '#F57F17',
    );
    return isset($map[$c]) ? $map[$c] : '#37474F';
}

// Sports pages admin (football)
function isSportsAdmin($r) {
    return in_array($r, array('secretary','developer','sports_committee'));
}
// Cultural/arts pages admin (arts festival, onam)
function isCulturalAdmin($r) {
    return in_array($r, array('secretary','developer','cultural_committee'));
}
// Finance pages admin (crowdfund, donation, subscription)
function isFinanceAdmin($r) {
    return in_array($r, array('secretary','developer','finance_committee','treasurer'));
}
// Per-module admin: true if user is a full club admin, OR assigned to this module
// (assignment may be permanent or a guest-admin with an expiry date).
function isModuleAdmin($module, $user = null) {
    if ($user === null) { $user = function_exists('currentUser') ? currentUser() : null; }
    if (!$user) return false;
    // Developer + Secretary always have access to all modules
    if (isFullAdmin($user)) return true;
    static $cache = null;
    if ($cache === null) {
        $cache = array();
        try {
            db()->exec("CREATE TABLE IF NOT EXISTS module_admins(
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                module VARCHAR(80) NOT NULL,
                added_by INT NOT NULL,
                expires_at DATETIME DEFAULT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY one_mod(user_id,module))");
            try { db()->exec("ALTER TABLE module_admins ADD COLUMN expires_at DATETIME DEFAULT NULL"); } catch (Exception $e) {}
            // Read assignments. Works whether or not expires_at exists.
            $rows = array();
            try {
                try { db()->exec("DELETE FROM module_admins WHERE expires_at IS NOT NULL AND expires_at < NOW()"); } catch (Exception $e) {}
                $rows = db()->query("SELECT user_id,module FROM module_admins WHERE expires_at IS NULL OR expires_at >= NOW()")->fetchAll();
            } catch (Exception $e) {
                $rows = db()->query("SELECT user_id,module FROM module_admins")->fetchAll();
            }
            foreach ($rows as $r) { $cache[$r['module']][(int)$r['user_id']] = true; }
        } catch (Exception $e) {}
    }
    return !empty($cache[$module][(int)$user['id']]);
}
// ── Photo optimiser: called after every upload ────────────────
// Shrinks big photos to max 1200px on the long side and re-saves JPG at 80% quality
// (PNG/WebP keep their format). Safe: if GD is missing or anything fails, the original file stays.
function img_optimize($path, $max = 1200, $quality = 80) {
    if (!is_file($path) || !function_exists('getimagesize') || !function_exists('imagecreatetruecolor')) return false;
    $info = @getimagesize($path); if (!$info) return false;
    list($w, $h) = $info; $type = $info[2];
    if (!in_array($type, array(IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_WEBP), true)) return false;
    if ($type === IMAGETYPE_JPEG && function_exists('exif_read_data')) { $exif = @exif_read_data($path); } else { $exif = null; }
    $src = $type === IMAGETYPE_JPEG ? @imagecreatefromjpeg($path) : ($type === IMAGETYPE_PNG ? @imagecreatefrompng($path) : (function_exists('imagecreatefromwebp') ? @imagecreatefromwebp($path) : false));
    if (!$src) return false;
    // phone photos: apply the camera rotation so they are not shown sideways
    if (!empty($exif['Orientation'])) {
        $o = (int)$exif['Orientation'];
        if ($o === 3) $src = imagerotate($src, 180, 0); elseif ($o === 6) $src = imagerotate($src, -90, 0); elseif ($o === 8) $src = imagerotate($src, 90, 0);
        $w = imagesx($src); $h = imagesy($src);
    }
    $scale = min(1, $max / max($w, $h));
    $nw = max(1, (int)round($w * $scale)); $nh = max(1, (int)round($h * $scale));
    $dst = imagecreatetruecolor($nw, $nh);
    if ($type !== IMAGETYPE_JPEG) { imagealphablending($dst, false); imagesavealpha($dst, true); }
    imagecopyresampled($dst, $src, 0, 0, 0, 0, $nw, $nh, $w, $h);
    $tmp = $path . '.tmp';
    $ok = $type === IMAGETYPE_JPEG ? imagejpeg($dst, $tmp, $quality) : ($type === IMAGETYPE_PNG ? imagepng($dst, $tmp, 7) : imagewebp($dst, $tmp, $quality));
    imagedestroy($src); imagedestroy($dst);
    if ($ok && filesize($tmp) > 0 && ($scale < 1 || filesize($tmp) < filesize($path) || !empty($exif['Orientation']))) { @rename($tmp, $path); return true; }
    @unlink($tmp); return false;
}

// Add member columns that some pages need, if an older database lacks them (runs once per request, only where called)
function ensure_user_columns() {
    static $done = false; if ($done) return; $done = true;
    try { $have = db()->query("SHOW COLUMNS FROM users")->fetchAll(PDO::FETCH_COLUMN); } catch (Exception $e) { return; }
    $want = array(
        'privacy_phone'    => "VARCHAR(10) DEFAULT 'members'",
        'privacy_photo'    => "VARCHAR(10) DEFAULT 'members'",
        'rejection_reason' => "VARCHAR(255) NULL",
        'approved_by'      => "INT NULL",
        'approved_at'      => "DATETIME NULL",
    );
    foreach ($want as $col => $def) {
        if (!in_array($col, $have, true)) { try { db()->exec("ALTER TABLE users ADD COLUMN $col $def"); } catch (Exception $e) {} }
    }
}

// CSRF
function csrfToken() {
    if (empty($_SESSION['_csrf'])) $_SESSION['_csrf'] = bin2hex(random_bytes(32));
    return $_SESSION['_csrf'];
}
function csrfField() {
    return '<input type="hidden" name="_csrf" value="'.csrfToken().'">';
}
function verifyCsrf() {
    $t = isset($_POST['_csrf']) ? $_POST['_csrf'] : (isset($_SERVER['HTTP_X_CSRF_TOKEN']) ? $_SERVER['HTTP_X_CSRF_TOKEN'] : '');
    return !empty($t) && hash_equals(csrfToken(), $t);
}
?>
