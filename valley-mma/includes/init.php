<?php
// Shared start-up for every page: config, session, database, language and helpers.

declare(strict_types=1);

// App version: shown in the app (More, login, Scanner test). Must match window.VM_JS in assets/app.js.
const APP_VERSION = '3.9';

$CONFIG = require __DIR__ . '/../config.php';
date_default_timezone_set($CONFIG['timezone'] ?? 'Asia/Kolkata');

function cfg(string $key)
{
    global $CONFIG;
    return $CONFIG[$key] ?? null;
}

function is_https(): bool
{
    return (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https';
}

if (PHP_SAPI !== 'cli' && session_status() === PHP_SESSION_NONE) {
    // Admins and members stay signed in for "login_days" (config.php, default 7 days).
    $life = max(1, (int)(cfg('login_days') ?? 7)) * 24 * 3600;
    ini_set('session.gc_maxlifetime', (string)$life);
    session_name('vmma_sid');
    session_set_cookie_params([
        'lifetime' => $life,
        'path'     => '/',
        'secure'   => is_https(),
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
    session_start();
    header('X-Frame-Options: SAMEORIGIN');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: same-origin');
}

function db(): PDO
{
    static $pdo = null;
    if ($pdo === null) {
        $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', cfg('db_host'), cfg('db_port'), cfg('db_name'));
        try {
            $pdo = new PDO($dsn, cfg('db_user'), cfg('db_pass'), [
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES   => false,
            ]);
            $pdo->query('SELECT 1 FROM settings LIMIT 1');
        } catch (PDOException $e) {
            http_response_code(500);
            exit('<p style="font-family:sans-serif">Database not ready. Check config.php and open <a href="install.php">install.php</a>.</p>');
        }
        // Use the app time zone for CURDATE()/NOW() in queries too.
        $pdo->exec("SET time_zone = '" . (new DateTime())->format('P') . "'");
        migrate($pdo);
    }
    return $pdo;
}

// Brings databases from older versions of the app up to date.
function migrate(PDO $pdo): void
{
    $v = (int)$pdo->query("SELECT v FROM settings WHERE k = 'schema_version'")->fetchColumn();
    if ($v >= 5) {
        return;
    }
    if ($v < 2) {
        migrate_v2($pdo);
    }
    if ($v < 3) {
        migrate_v3($pdo);
    }
    require_once __DIR__ . '/sql_tools.php';
    run_sql($pdo, file_get_contents(__DIR__ . '/../sql/leaves.sql'));
    // v5: positions (levels) by attendance, complaints
    $cols = $pdo->query("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'members'")
        ->fetchAll(PDO::FETCH_COLUMN);
    if (!in_array('level_id', $cols, true)) {
        $pdo->exec('ALTER TABLE members ADD COLUMN level_id INT UNSIGNED NULL AFTER approved_at,
            ADD COLUMN level_auto TINYINT(1) NOT NULL DEFAULT 1 AFTER level_id, ADD COLUMN level_since DATE NULL AFTER level_auto');
    }
    run_sql($pdo, file_get_contents(__DIR__ . '/../sql/levels.sql'));
    $pdo->exec(LEVEL_RECALC_SQL . ', level_since = CURDATE() WHERE m.level_auto = 1 AND m.level_id IS NULL');
    $pdo->exec("INSERT INTO settings (k, v) VALUES ('schema_version', '5') ON DUPLICATE KEY UPDATE v = '5'");
}

// Sets level_id from the attendance days (add a WHERE).
const LEVEL_RECALC_SQL = 'UPDATE members m SET level_id = (SELECT l.id FROM levels l WHERE l.from_day <= GREATEST(1,
    (SELECT COUNT(*) FROM attendance a WHERE a.member_id = m.id)) ORDER BY l.from_day DESC LIMIT 1)';

function migrate_v3(PDO $pdo): void
{
    $cols = $pdo->query("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'members'")
        ->fetchAll(PDO::FETCH_COLUMN);
    if (!in_array('status', $cols, true)) {
        $pdo->exec("ALTER TABLE members ADD COLUMN status ENUM('pending','active','inactive') NOT NULL DEFAULT 'active' AFTER card_token,
            ADD COLUMN invite_token CHAR(32) NULL AFTER status, ADD COLUMN details_at DATETIME NULL AFTER invite_token,
            ADD COLUMN approved_at DATETIME NULL AFTER details_at, ADD KEY idx_status (status)");
    }
    $pdo->exec("INSERT IGNORE INTO settings (k, v) VALUES ('att_block_expired', '0'), ('trial_days', '7')");
    $pdo->exec("INSERT INTO settings (k, v) VALUES ('schema_version', '3') ON DUPLICATE KEY UPDATE v = '3'");
}

function migrate_v2(PDO $pdo): void
{
    require_once __DIR__ . '/sql_tools.php';
    $cols = $pdo->query("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'payments'")
        ->fetchAll(PDO::FETCH_COLUMN);
    if (!in_array('prev_expiry', $cols, true)) {
        $pdo->exec('ALTER TABLE payments ADD COLUMN prev_plan_id INT UNSIGNED NULL AFTER period_end,
            ADD COLUMN prev_start DATE NULL AFTER prev_plan_id, ADD COLUMN prev_expiry DATE NULL AFTER prev_start');
    }
    run_sql($pdo, file_get_contents(__DIR__ . '/../sql/accounts.sql'));
}

function q(string $sql, array $params = []): PDOStatement
{
    $st = db()->prepare($sql);
    $st->execute($params);
    return $st;
}

// ---- Settings -----------------------------------------------------

function setting(string $k, string $default = ''): string
{
    if (!isset($GLOBALS['vm_settings'])) {
        $GLOBALS['vm_settings'] = q('SELECT k, v FROM settings')->fetchAll(PDO::FETCH_KEY_PAIR);
    }
    return isset($GLOBALS['vm_settings'][$k]) ? (string)$GLOBALS['vm_settings'][$k] : $default;
}

function set_setting(string $k, string $v): void
{
    q('INSERT INTO settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)', [$k, $v]);
    unset($GLOBALS['vm_settings']);
}

function app_secret(): string
{
    $s = setting('app_secret');
    if ($s === '') {
        $s = bin2hex(random_bytes(32));
        set_setting('app_secret', $s);
    }
    return $s;
}

function sign(string $data, int $len = 20): string
{
    return substr(hash_hmac('sha256', $data, app_secret()), 0, $len);
}

// ---- Language -----------------------------------------------------

function lang(): string
{
    static $l = null;
    if ($l === null) {
        $l = $_SESSION['lang'] ?? ($_COOKIE['vmma_lang'] ?? '');
        if (!in_array($l, ['en', 'ml'], true)) {
            $l = PHP_SAPI === 'cli' ? 'en' : setting('default_lang', 'en');
        }
        if (!in_array($l, ['en', 'ml'], true)) {
            $l = 'en';
        }
    }
    return $l;
}

function t(string $key, ...$args): string
{
    static $L = null;
    if ($L === null) {
        $L = require __DIR__ . '/lang.php';
    }
    $s = $L[lang()][$key] ?? $L['en'][$key] ?? $key;
    return $args ? vsprintf($s, $args) : $s;
}

// English text of a key, for PDF export (the PDF font has no Malayalam letters).
function t_en(string $key): string
{
    static $L = null;
    if ($L === null) {
        $L = require __DIR__ . '/lang.php';
    }
    return $L['en'][$key] ?? $key;
}

// ---- Output helpers -----------------------------------------------

function e($s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

function money($n): string
{
    $n = (float)$n;
    $a = abs($n);
    return ($n < 0 ? '−' : '') . '₹' . number_format($a, $a == floor($a) ? 0 : 2);
}

function fdate(?string $d): string
{
    return $d ? date('d-m-Y', strtotime($d)) : '–';
}

function today(): string
{
    return date('Y-m-d');
}

function redirect(string $url): void
{
    header('Location: ' . $url);
    exit;
}

function flash(string $type, string $msg): void
{
    $_SESSION['flash'][] = [$type, $msg];
}

function flashes(): string
{
    $out = '';
    foreach ($_SESSION['flash'] ?? [] as [$type, $msg]) {
        $out .= '<div class="alert alert-' . e($type) . ' alert-dismissible fade show" role="alert">' . e($msg)
            . '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>';
    }
    unset($_SESSION['flash']);
    return $out;
}

// Address used in QR codes and WhatsApp links. Set "app_url" in Settings when the admin opens the app as
// http://localhost/… (phones cannot open "localhost"); otherwise the address in the browser is used.
function base_url(): string
{
    $set = PHP_SAPI === 'cli' ? '' : setting('app_url');
    if ($set !== '') {
        return rtrim($set, '/') . '/';
    }
    return detected_url();
}

function detected_url(): string
{
    $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    return (is_https() ? 'https' : 'http') . '://' . ($_SERVER['HTTP_HOST'] ?? 'localhost') . $dir . '/';
}

// ---- Security -----------------------------------------------------

function csrf_token(): string
{
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(16));
    }
    return $_SESSION['csrf'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf" value="' . e(csrf_token()) . '">';
}

function csrf_check(): void
{
    if ($_SERVER['REQUEST_METHOD'] === 'POST'
        && !hash_equals(csrf_token(), (string)($_POST['csrf'] ?? $_SERVER['HTTP_X_CSRF'] ?? ''))) {
        http_response_code(400);
        exit('Session expired. Go back, reload the page and try again.');
    }
}

function admin(): ?array
{
    static $a = false;
    if ($a === false) {
        $a = null;
        if (!empty($_SESSION['admin_id'])) {
            if (time() - ($_SESSION['admin_seen'] ?? 0) > max(1, (int)(cfg('login_days') ?? 7)) * 86400) {
                unset($_SESSION['admin_id']);
            } else {
                $_SESSION['admin_seen'] = time();
                $a = q('SELECT id, username, full_name FROM admins WHERE id = ?', [$_SESSION['admin_id']])->fetch() ?: null;
            }
        }
    }
    return $a;
}

function require_admin(): array
{
    $a = admin();
    if (!$a) {
        $_SESSION['after_login'] = $_SERVER['REQUEST_URI'] ?? '';
        redirect('login.php');
    }
    csrf_check();
    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        require_once __DIR__ . '/backup_lib.php';
        auto_backup_if_due();
    }
    return $a;
}

// Money changes and deletes need the admin password again (pop-up in the page, field "verify_password").
function verify_ok(): bool
{
    $a = admin();
    if (!$a || too_many_attempts()) {
        return false;
    }
    $hash = (string)q('SELECT password_hash FROM admins WHERE id = ?', [$a['id']])->fetchColumn();
    if (password_verify((string)($_POST['verify_password'] ?? ''), $hash)) {
        return true;
    }
    failed_attempt();
    return false;
}

// Stops the action and goes back when the password is wrong.
function require_verify(string $back): void
{
    if (!verify_ok()) {
        flash('danger', t(too_many_attempts() ? 'too_many' : 'verify_wrong'));
        redirect($back);
    }
}

function member_user(): ?array
{
    if (empty($_SESSION['member_id'])) {
        return null;
    }
    return q('SELECT * FROM members WHERE id = ?', [$_SESSION['member_id']])->fetch() ?: null;
}

function too_many_attempts(): bool
{
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    q('DELETE FROM login_attempts WHERE tried_at < NOW() - INTERVAL 15 MINUTE');
    return (int)q('SELECT COUNT(*) FROM login_attempts WHERE ip = ?', [$ip])->fetchColumn() >= 8;
}

function failed_attempt(): void
{
    q('INSERT INTO login_attempts (ip, tried_at) VALUES (?, NOW())', [$_SERVER['REMOTE_ADDR'] ?? '']);
}

// True when phones cannot open this address (localhost / 127.0.0.1).
function is_local_url(string $url): bool
{
    $h = strtolower(trim((string)parse_url($url, PHP_URL_HOST), '[]'));
    return in_array($h, ['localhost', '127.0.0.1', '::1'], true) || str_ends_with($h, '.localhost');
}

// This computer's address on the Wi-Fi / LAN, for the attendance QR (XAMPP). '' when not found.
function lan_url(): string
{
    $ips = [];
    $cands = [$_SERVER['SERVER_ADDR'] ?? '', gethostbyname((string)gethostname())];
    // The interface used to reach the internet (a UDP "connect" sends nothing).
    $sock = @stream_socket_client('udp://8.8.8.8:53', $errno, $errstr, 1);
    if ($sock) {
        $cands[] = (string)preg_replace('/:\d+$/', '', (string)stream_socket_get_name($sock, false));
        fclose($sock);
    }
    foreach ($cands as $ip) {
        if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4) && !str_starts_with($ip, '127.')) {
            $ips[] = $ip;
        }
    }
    if (!$ips) {
        return '';
    }
    $port = (int)($_SERVER['SERVER_PORT'] ?? 80);
    $https = is_https();
    $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    return ($https ? 'https' : 'http') . '://' . $ips[0] . (($https && $port !== 443) || (!$https && $port !== 80) ? ':' . $port : '') . $dir . '/';
}

function valid_app_url(string $url): bool
{
    return (bool)filter_var($url, FILTER_VALIDATE_URL) && preg_match('#^https?://#i', $url);
}

// ---- Navigation ---------------------------------------------------

// Menu sections: [link, text key, icon, active key]. Used by the sidebar and the "More" page.
function nav_sections(): array
{
    return [
        'sec_members' => [
            ['members.php', 'members', 'bi-people-fill', 'members'],
            ['member_invite.php', 'invite_member', 'bi-person-plus-fill', 'add_member'],
            ['member_edit.php', 'add_member', 'bi-person-vcard-fill', 'add_member'],
            ['plans.php', 'plans', 'bi-card-checklist', 'plans'],
            ['attendance.php', 'attendance', 'bi-qr-code-scan', 'attendance'],
            ['alerts.php', 'alerts', 'bi-bell-fill', 'alerts'],
            ['levels.php', 'positions', 'bi-award-fill', 'levels'],
            ['complaints.php', 'complaints', 'bi-chat-left-text-fill', 'complaints'],
        ],
        'sec_money' => [
            ['payments.php', 'payments', 'bi-cash-coin', 'payments'],
            ['accounts.php', 'accounts', 'bi-wallet2', 'accounts'],
            ['reports.php', 'reports', 'bi-bar-chart-fill', 'reports'],
        ],
        'sec_gym' => [
            ['activities.php', 'daily_activity', 'bi-calendar-week', 'activities'],
            ['leaves.php', 'gym_leaves', 'bi-calendar-x', 'leaves'],
            ['settings.php', 'settings', 'bi-gear-fill', 'settings'],
            ['backup.php', 'backup', 'bi-cloud-arrow-down-fill', 'backup'],
        ],
    ];
}

// ---- Input --------------------------------------------------------

function post(string $k, string $default = ''): string
{
    return trim((string)($_POST[$k] ?? $default));
}

function get(string $k, string $default = ''): string
{
    return trim((string)($_GET[$k] ?? $default));
}

function valid_date(string $d): bool
{
    $x = DateTime::createFromFormat('Y-m-d', $d);
    return $x && $x->format('Y-m-d') === $d;
}

function num(string $s): float
{
    return max(0, round((float)str_replace(',', '', $s), 2));
}

function clean_phone(string $p): string
{
    return preg_replace('/[^0-9+]/', '', $p);
}

// ---- Membership ---------------------------------------------------

// Last day of a membership that starts on $start: 1 month from 27 Oct = 27 Oct … 26 Nov.
function plan_end(string $start, int $value, string $unit): string
{
    $d = new DateTime($start);
    if ($unit === 'day') {
        $d->modify('+' . max(1, $value) . ' day');
    } else {
        $day = (int)$d->format('j');
        $d->modify('first day of this month')->modify('+' . max(1, $value) . ' month');
        $d->setDate((int)$d->format('Y'), (int)$d->format('n'), min($day, (int)$d->format('t')));
    }
    return $d->modify('-1 day')->format('Y-m-d');
}

function plan_duration(array $p): string
{
    $v = (int)$p['duration_value'];
    if ($p['duration_unit'] === 'day') {
        return t($v === 1 ? 'n_day' : 'n_days', $v);
    }
    if ($v % 12 === 0) {
        return t($v === 12 ? 'n_year' : 'n_years', $v / 12);
    }
    return t($v === 1 ? 'n_month' : 'n_months', $v);
}

// pending / inactive / active / expiring / expired / none
function member_status(?string $expiry, string $status = 'active'): string
{
    if ($status === 'pending' || $status === 'inactive') {
        return $status;
    }
    if (!$expiry) {
        return 'none';
    }
    if ($expiry < today()) {
        return 'expired';
    }
    $soon = date('Y-m-d', strtotime('+' . (int)setting('expiry_days', '7') . ' day'));
    return $expiry <= $soon ? 'expiring' : 'active';
}

function status_badge(?string $expiry, string $status = 'active'): string
{
    $s = member_status($expiry, $status);
    $cls = ['active' => 'success', 'expiring' => 'warning text-dark', 'expired' => 'danger', 'none' => 'secondary',
        'pending' => 'info text-dark', 'inactive' => 'dark'][$s];
    $label = $s === 'expiring' ? 'active' : $s;
    $extra = $s === 'expiring' ? ' <i class="bi bi-hourglass-split"></i>' : '';
    return '<span class="badge bg-' . $cls . '" data-en="' . e(t_en('st_' . $label)) . '">' . e(t('st_' . $label)) . $extra . '</span>';
}

// Can this member mark attendance today? Returns '' when yes, otherwise the reason (text key).
function attendance_block(array $m): string
{
    $st = $m['status'] ?? 'active';
    if ($st === 'inactive') {
        return 'att_no_inactive';
    }
    if ($st === 'pending') {
        return 'att_no_pending';
    }
    if (isset($m['id']) && in_array((int)$m['id'], frozen_ids(), true)) {
        return 'att_no_frozen';
    }
    if (setting('att_block_expired', '0') === '1' && member_status($m['expiry_date']) === 'expired') {
        return 'att_no_expired';
    }
    return '';
}

function days_left(?string $expiry): int
{
    return $expiry ? (int)floor((strtotime($expiry) - strtotime(today())) / 86400) : 0;
}

function left_text(int $days): string
{
    return t($days === 1 ? 'day_left' : 'days_left', $days);
}

function member_balance(int $id): float
{
    return (float)q('SELECT COALESCE(SUM(total - paid), 0) FROM payments WHERE member_id = ?', [$id])->fetchColumn();
}

function next_adm_no(): string
{
    $n = (int)q("SELECT COALESCE(MAX(CAST(SUBSTRING(adm_no, 3) AS UNSIGNED)), 0) FROM members WHERE adm_no LIKE 'VM%'")->fetchColumn();
    return sprintf('VM%03d', $n + 1);
}

function next_receipt_no(): int
{
    return max(1001, (int)q('SELECT COALESCE(MAX(receipt_no), 0) + 1 FROM payments')->fetchColumn());
}

// Sets the member's plan and dates from their latest plan payment (after a payment is added).
function sync_membership(int $memberId): void
{
    $p = q('SELECT plan_id, period_start, period_end FROM payments
            WHERE member_id = ? AND period_end IS NOT NULL ORDER BY period_end DESC, id DESC LIMIT 1', [$memberId])->fetch();
    if ($p) {
        // Freezes in or after this period still move the expiry on.
        $frozen = (int)q('SELECT COALESCE(SUM(days), 0) FROM member_freezes WHERE member_id = ? AND extended = 1 AND from_date >= ?',
            [$memberId, $p['period_start']])->fetchColumn();
        q('UPDATE members SET plan_id = ?, start_date = ?, expiry_date = DATE_ADD(?, INTERVAL ? DAY) WHERE id = ?',
            [$p['plan_id'], $p['period_start'], $p['period_end'], $frozen, $memberId]);
    }
}

// Deletes a payment. When it was the plan payment now in use, the membership goes back to the
// latest other plan payment, or to the dates the member had before this payment.
function delete_payment(array $p): void
{
    q('DELETE FROM payments WHERE id = ?', [$p['id']]);
    if (!$p['period_end']) {
        return;
    }
    $m = q('SELECT expiry_date FROM members WHERE id = ?', [$p['member_id']])->fetch();
    $frozen = (int)q('SELECT COALESCE(SUM(days), 0) FROM member_freezes WHERE member_id = ? AND extended = 1 AND from_date >= ?',
        [$p['member_id'], $p['period_start']])->fetchColumn();
    if (!$m || $m['expiry_date'] !== date('Y-m-d', strtotime($p['period_end'] . " +$frozen day"))) {
        return;
    }
    $other = (int)q('SELECT COUNT(*) FROM payments WHERE member_id = ? AND period_end IS NOT NULL', [$p['member_id']])->fetchColumn();
    if ($other) {
        sync_membership((int)$p['member_id']);
    } else {
        q('UPDATE members SET plan_id = ?, start_date = ?, expiry_date = ? WHERE id = ?',
            [$p['prev_plan_id'], $p['prev_start'], $p['prev_expiry'], $p['member_id']]);
    }
}

// ---- Positions (levels) by attendance -------------------------------

function levels(bool $fresh = false): array
{
    static $all = null;
    if ($all === null || $fresh) {
        $all = q('SELECT * FROM levels ORDER BY from_day')->fetchAll();
    }
    return $all;
}

function level_by_id(?int $id): ?array
{
    foreach (levels() as $l) {
        if ((int)$l['id'] === (int)$id) {
            return $l;
        }
    }
    return null;
}

function level_for_days(int $days): ?array
{
    $found = levels()[0] ?? null;
    foreach (levels() as $l) {
        if ((int)$l['from_day'] <= max(1, $days)) {
            $found = $l;
        }
    }
    return $found;
}

function level_next(?array $level): ?array
{
    foreach (levels() as $l) {
        if ($level && (int)$l['from_day'] > (int)$level['from_day']) {
            return $l;
        }
    }
    return null;
}

function att_days(int $memberId): int
{
    return (int)q('SELECT COUNT(*) FROM attendance WHERE member_id = ?', [$memberId])->fetchColumn();
}

// "Day 1–5" / "Day 91+"
function level_range(array $l): string
{
    $next = level_next($l);
    return $next ? t('level_days', (int)$l['from_day'], (int)$next['from_day'] - 1) : t('level_days_plus', (int)$l['from_day']);
}

// After attendance changes: moves an automatic member to the level of their attendance days.
// Returns the new level when it changed.
function level_update(int $memberId): ?array
{
    $m = q('SELECT level_id, level_auto FROM members WHERE id = ?', [$memberId])->fetch();
    if (!$m || !(int)$m['level_auto']) {
        return null;
    }
    $l = level_for_days(att_days($memberId));
    if (!$l || (int)$l['id'] === (int)$m['level_id']) {
        return null;
    }
    q('UPDATE members SET level_id = ?, level_since = ? WHERE id = ?', [$l['id'], today(), $memberId]);
    return $l;
}

function levels_recalc(): void
{
    q(LEVEL_RECALC_SQL . ' WHERE m.level_auto = 1');
}

function level_badge(?array $l, string $extra = ''): string
{
    if (!$l) {
        return '';
    }
    return '<span class="badge level-badge ' . e($extra) . '" style="background:' . e($l['color']) . '" data-en="' . e($l['name']) . '"><i class="bi bi-award-fill"></i> ' . e($l['name']) . '</span>';
}

// Where a member is: level, next level, attendance days, day number inside the level, days still needed.
function level_progress(array $m): array
{
    $days = att_days((int)$m['id']);
    $l = level_by_id(isset($m['level_id']) ? (int)$m['level_id'] : null) ?? level_for_days($days);
    $next = level_next($l);
    $out = ['level' => $l, 'next' => $next, 'days' => $days, 'auto' => (int)($m['level_auto'] ?? 1) === 1, 'pct' => 100, 'left' => 0, 'day_in' => 0, 'len' => 0];
    if ($l && $next) {
        $len = (int)$next['from_day'] - (int)$l['from_day'];
        $in = max(0, $days - (int)$l['from_day'] + 1);
        $out['len'] = $len;
        $out['day_in'] = min($in, $len);
        $out['left'] = max(0, (int)$next['from_day'] - $days);
        $out['pct'] = $len > 0 ? (int)round(min($in, $len) * 100 / $len) : 100;
    }
    return $out;
}

function level_progress_html(array $p): string
{
    if (!$p['level']) {
        return '';
    }
    $h = '<div class="d-flex align-items-center gap-2 mb-1">' . level_badge($p['level']) . '<span class="small-muted">' . e(level_range($p['level'])) . '</span>'
        . '<span class="ms-auto small fw-semibold">' . e(t('att_days_total', $p['days'])) . '</span></div>';
    if ($p['next']) {
        $h .= '<div class="progress" role="progressbar" style="height:.6rem" aria-valuenow="' . $p['pct'] . '" aria-valuemin="0" aria-valuemax="100">'
            . '<div class="progress-bar" style="width:' . $p['pct'] . '%;background:' . e($p['level']['color']) . '"></div></div>'
            . '<div class="small mt-1">' . ($p['day_in'] > 0 ? e(t('level_day_of', $p['day_in'], $p['len'], $p['level']['name'])) . ' · ' : '')
            . e(t('level_left', $p['left'], $p['next']['name'])) . '</div>';
    } else {
        $h .= '<div class="small mt-1">' . e(t('level_top')) . '</div>';
    }
    return $h;
}

function level_text(array $m, array $l): string
{
    $next = level_next($l);
    return t('wa_level', $m['name'], $l['name'], gym_title()) . ($l['note'] !== '' ? "\n" . $l['note'] : '')
        . ($next ? "\n" . t('wa_level_next', $next['name'], (int)$next['from_day']) : '');
}

// ---- Complaints ---------------------------------------------------

const COMPLAINT_CATS = ['equipment' => 'bi-tools', 'trainer' => 'bi-person-badge', 'cleanliness' => 'bi-droplet', 'timing' => 'bi-clock',
    'payment' => 'bi-cash-coin', 'suggestion' => 'bi-lightbulb', 'other' => 'bi-chat-dots'];

function complaint_badge(string $status): string
{
    $cls = ['open' => 'bg-danger', 'progress' => 'bg-warning text-dark', 'resolved' => 'bg-success'][$status] ?? 'bg-secondary';
    return '<span class="badge ' . $cls . '">' . e(t('cs_' . $status)) . '</span>';
}

function complaint_add_msg(int $complaintId, bool $byAdmin, string $msg): void
{
    q('INSERT INTO complaint_msgs (complaint_id, by_admin, admin_id, message) VALUES (?, ?, ?, ?)',
        [$complaintId, (int)$byAdmin, $byAdmin ? (admin()['id'] ?? null) : null, $msg]);
    q('UPDATE complaints SET updated_at = NOW(), admin_unread = ?, member_unread = ? WHERE id = ?',
        [$byAdmin ? 0 : 1, $byAdmin ? 1 : 0, $complaintId]);
}

function complaints_unread_admin(): int
{
    return (int)q('SELECT COUNT(*) FROM complaints WHERE admin_unread = 1')->fetchColumn();
}

// ---- Gym leave days and member freezes ------------------------------

const FREEZE_REASONS = ['injury' => 'bi-bandaid', 'travel' => 'bi-airplane', 'illness' => 'bi-thermometer-half', 'other' => 'bi-snow'];

function day_count(string $from, string $to): int
{
    return (int)((strtotime($to) - strtotime($from)) / 86400) + 1;
}

// Members frozen on a day (one query per day, kept for the request).
function frozen_ids(string $date = ''): array
{
    static $cache = [];
    $date = $date !== '' ? $date : today();
    return $cache[$date] ??= array_map('intval',
        q('SELECT DISTINCT member_id FROM member_freezes WHERE ? BETWEEN from_date AND to_date', [$date])->fetchAll(PDO::FETCH_COLUMN));
}

function current_freeze(int $memberId): ?array
{
    $f = q('SELECT * FROM member_freezes WHERE member_id = ? AND to_date >= ? ORDER BY from_date LIMIT 1', [$memberId, today()])->fetch();
    return $f ?: null;
}

// Leave and freeze days between two dates: ['leave' => [date => row], 'freeze' => [member_id => [date => row]]].
function day_marks(string $first, string $last, int $memberId = 0): array
{
    $out = ['leave' => [], 'freeze' => []];
    foreach (q('SELECT * FROM gym_leaves WHERE from_date <= ? AND to_date >= ? ORDER BY from_date', [$last, $first])->fetchAll() as $l) {
        for ($d = max($l['from_date'], $first); $d <= min($l['to_date'], $last); $d = date('Y-m-d', strtotime($d . ' +1 day'))) {
            $out['leave'][$d] = $l;
        }
    }
    $sql = 'SELECT * FROM member_freezes WHERE from_date <= ? AND to_date >= ?' . ($memberId ? ' AND member_id = ?' : '');
    foreach (q($sql, $memberId ? [$last, $first, $memberId] : [$last, $first])->fetchAll() as $f) {
        for ($d = max($f['from_date'], $first); $d <= min($f['to_date'], $last); $d = date('Y-m-d', strtotime($d . ' +1 day'))) {
            $out['freeze'][(int)$f['member_id']][$d] = $f;
        }
    }
    return $out;
}

function date_range_text(string $from, string $to): string
{
    $n = day_count($from, $to);
    return ($from === $to ? fdate($from) : fdate($from) . ' – ' . fdate($to)) . ' (' . t($n === 1 ? 'n_day' : 'n_days', $n) . ')';
}

function leave_text(array $l): string
{
    $msg = '*' . gym_title() . "*\n\n📢 *" . $l['title'] . "*\n" . t('wa_gym_closed', date_range_text($l['from_date'], $l['to_date']));
    if (trim((string)$l['message']) !== '') {
        $msg .= "\n\n" . trim($l['message']);
    }
    $phones = trim(setting('phone1') . '  ' . setting('phone2'));
    return $msg . ($phones !== '' ? "\n\n📞 " . $phones : '');
}

function freeze_text(array $m, array $f): string
{
    $msg = t('wa_freeze', $m['name'], gym_title(), t('fr_' . $f['reason']), date_range_text($f['from_date'], $f['to_date']));
    $exp = q('SELECT expiry_date FROM members WHERE id = ?', [$m['id']])->fetchColumn();
    if ($f['extended'] && $exp) {
        $msg .= "\n" . t('wa_freeze_extended', fdate($exp));
    }
    return $msg;
}

// Adds or changes a freeze. With $extend the membership expiry moves on by the frozen days.
function freeze_save(array $m, string $from, string $to, string $reason, string $note, bool $extend, ?array $old = null): int
{
    $days = day_count($from, $to);
    $shift = ($extend ? $days : 0) - ($old && $old['extended'] ? (int)$old['days'] : 0);
    if ($old) {
        q('UPDATE member_freezes SET from_date = ?, to_date = ?, days = ?, extended = ?, reason = ?, note = ? WHERE id = ?',
            [$from, $to, $days, (int)$extend, $reason, $note, $old['id']]);
        $id = (int)$old['id'];
    } else {
        q('INSERT INTO member_freezes (member_id, from_date, to_date, days, extended, reason, note) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [$m['id'], $from, $to, $days, (int)$extend, $reason, $note]);
        $id = (int)db()->lastInsertId();
    }
    if ($shift !== 0) {
        q('UPDATE members SET expiry_date = DATE_ADD(expiry_date, INTERVAL ? DAY) WHERE id = ? AND expiry_date IS NOT NULL', [$shift, $m['id']]);
    }
    return $id;
}

function freeze_delete(array $f): void
{
    q('DELETE FROM member_freezes WHERE id = ?', [$f['id']]);
    if ($f['extended']) {
        q('UPDATE members SET expiry_date = DATE_SUB(expiry_date, INTERVAL ? DAY) WHERE id = ? AND expiry_date IS NOT NULL', [(int)$f['days'], $f['member_id']]);
    }
}

// Month calendar (Mon–Sun) with present, gym leave and freeze days. $links: date => url for admin changes.
function month_calendar(string $month, array $present, array $leave, array $freeze, array $links = [], bool $legend = true): string
{
    $first = $month . '-01';
    $n = (int)date('t', strtotime($first));
    $h = '<div class="cal">';
    for ($i = 1; $i <= 7; $i++) {
        $h .= '<div class="cal-h">' . e(mb_substr(t('day' . $i), 0, 2)) . '</div>';
    }
    $h .= str_repeat('<div></div>', (int)date('N', strtotime($first)) - 1);
    for ($d = 1; $d <= $n; $d++) {
        $date = sprintf('%s-%02d', $month, $d);
        $cls = in_array($d, $present, true) ? 'p' : (isset($leave[$date]) ? 'l' : (isset($freeze[$date]) ? 'f' : ''));
        if ($date === today()) {
            $cls .= ' today';
        }
        $tip = isset($leave[$date]) ? $leave[$date]['title'] : (isset($freeze[$date]) ? t('frozen') . ': ' . t('fr_' . $freeze[$date]['reason']) : '');
        $tag = isset($links[$date]) ? 'a href="' . e($links[$date]) . '"' : 'div';
        $h .= '<' . $tag . ' class="cal-d ' . $cls . '"' . ($tip !== '' ? ' title="' . e($tip) . '"' : '') . '>' . $d . '</' . strtok($tag, ' ') . '>';
    }
    if (!$legend) {
        return $h . '</div>';
    }
    return $h . '</div><div class="cal-legend"><span><i class="p"></i>' . e(t('present')) . '</span><span><i class="l"></i>' . e(t('gym_leave'))
        . '</span><span><i class="f"></i>' . e(t('frozen')) . '</span></div>';
}

// ---- Attendance QR ------------------------------------------------

// Time slot of the attendance QR: changes every N minutes when "att_refresh" is set, otherwise once a day.
function att_slot(int $offset = 0): int
{
    $min = (int)setting('att_refresh', '0');
    return $min > 0 ? intdiv(time(), $min * 60) - $offset : 0;
}

function att_url(): string
{
    $d = today();
    return base_url() . 'checkin.php?d=' . $d . '&k=' . att_key($d, att_slot());
}

function att_key(string $date, int $slot): string
{
    return sign('att|' . $date . '|' . $slot, 16);
}

// ---- Photos -------------------------------------------------------

// Saves an uploaded photo as a resized JPEG (also removes anything hidden in the file). Returns the file name.
function save_photo(array $file): ?string
{
    if (($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK || $file['size'] > 8 * 1024 * 1024) {
        return null;
    }
    $info = @getimagesize($file['tmp_name']);
    if (!$info || !in_array($info[2], [IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_WEBP, IMAGETYPE_GIF], true)) {
        return null;
    }
    $data = file_get_contents($file['tmp_name']);
    $src = $data !== false && function_exists('imagecreatefromstring') ? @imagecreatefromstring($data) : false;
    if (!$src) {
        return null;
    }
    if ($info[2] === IMAGETYPE_JPEG && function_exists('exif_read_data')) {
        $o = (int)(@exif_read_data($file['tmp_name'])['Orientation'] ?? 1);
        $rot = [3 => 180, 6 => -90, 8 => 90][$o] ?? 0;
        if ($rot) {
            $src = imagerotate($src, $rot, 0);
        }
    }
    $w = imagesx($src);
    $h = imagesy($src);
    $scale = min(1, 600 / max($w, $h));
    $nw = max(1, (int)round($w * $scale));
    $nh = max(1, (int)round($h * $scale));
    $dst = imagecreatetruecolor($nw, $nh);
    imagefill($dst, 0, 0, imagecolorallocate($dst, 255, 255, 255));
    imagecopyresampled($dst, $src, 0, 0, 0, 0, $nw, $nh, $w, $h);
    $dir = cfg('photo_dir');
    if (!is_dir($dir)) {
        mkdir($dir, 0775, true);
    }
    $name = bin2hex(random_bytes(10)) . '.jpg';
    imagejpeg($dst, $dir . '/' . $name, 85);
    return $name;
}

function photo_url(array $m): string
{
    return $m['photo'] !== '' ? 'photo.php?f=' . rawurlencode($m['photo']) : 'assets/avatar.svg';
}

// ---- WhatsApp & UPI -----------------------------------------------

function wa_phone(string $phone): string
{
    $d = preg_replace('/\D/', '', $phone);
    $cc = setting('country_code', '91');
    if (strlen($d) === 11 && $d[0] === '0') {
        $d = substr($d, 1);
    }
    if (strlen($d) === 10) {
        $d = $cc . $d;
    }
    return $d;
}

function wa_link(string $phone, string $text): string
{
    $p = $phone === '' ? '' : wa_phone($phone);
    return 'https://wa.me/' . $p . '?text=' . rawurlencode($text);
}

function upi_link(float $amount = 0, string $note = ''): string
{
    $id = setting('upi_id');
    if ($id === '') {
        return '';
    }
    $q = ['pa' => $id, 'pn' => setting('upi_name', setting('gym_name')), 'cu' => 'INR'];
    if ($amount > 0) {
        $q['am'] = number_format($amount, 2, '.', '');
    }
    if ($note !== '') {
        $q['tn'] = mb_substr($note, 0, 60);
    }
    return 'upi://pay?' . http_build_query($q, '', '&', PHP_QUERY_RFC3986);
}

function gym_title(): string
{
    return trim(setting('gym_name', 'VALLEY MMA') . ' ' . setting('gym_tagline', 'FIGHT CLUB'));
}

// The Valley MMA logo (image) with tagline and place, on its dark background.
function brand_html(string $href = '', string $extra = ''): string
{
    $tag = $href !== '' ? 'a href="' . e($href) . '"' : 'div';
    $end = $href !== '' ? 'a' : 'div';
    return '<' . $tag . ' class="brand-logo ' . e($extra) . '"><img src="assets/logo.png" alt="' . e(setting('gym_name', 'VALLEY MMA')) . '" width="612" height="106">'
        . '<span class="l2">' . e(setting('gym_tagline', 'FIGHT CLUB')) . '</span>'
        . '<span class="l3">' . e(setting('gym_place', 'PANDIKKAD')) . '</span></' . $end . '>';
}

// Lines about paying by UPI for WhatsApp messages.
function upi_text(float $amount = 0): string
{
    $lines = [];
    if (setting('upi_id') !== '') {
        $lines[] = t('wa_upi_id') . ': ' . setting('upi_id');
    }
    if (setting('upi_phone') !== '') {
        $lines[] = t('wa_upi_phone') . ': ' . setting('upi_phone');
    }
    if ($amount > 0 && setting('upi_id') !== '') {
        $lines[] = t('wa_pay_link') . ': ' . base_url() . 'pay.php?a=' . number_format($amount, 2, '.', '');
    }
    return $lines ? "\n\n" . implode("\n", $lines) : '';
}

function plan_text(array $p): string
{
    return '🥊 ' . gym_title() . "\n" . $p['name'] . ' – ' . plan_duration($p) . "\n"
        . t('price') . ': ' . money($p['price'])
        . ($p['description'] !== '' ? "\n" . $p['description'] : '');
}

function invite_link(array $m): string
{
    return base_url() . 'join.php?t=' . rawurlencode((string)$m['invite_token']);
}

// WhatsApp message with the personal join link (password only when the admin just set it).
function invite_text(array $m, string $pass = ''): string
{
    return t('wa_invite', gym_title(), invite_link($m), $m['phone'], $pass !== '' ? $pass : t('pass_from_gym'));
}

function reminder_text(array $m, float $amount = 0): string
{
    $s = member_status($m['expiry_date']);
    $msg = $s === 'expired'
        ? t('wa_expired', $m['name'], gym_title(), fdate($m['expiry_date']))
        : t('wa_expiring', $m['name'], gym_title(), fdate($m['expiry_date']));
    return $msg . upi_text($amount);
}
