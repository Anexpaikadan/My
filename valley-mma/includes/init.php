<?php
// Shared start-up for every page: config, session, database, language and helpers.

declare(strict_types=1);

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
    // Members stay signed in on their phone for 30 days so they can scan the attendance QR quickly.
    $life = 30 * 24 * 3600;
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
    }
    return $pdo;
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
    return '₹' . number_format((float)$n, ((float)$n == floor((float)$n)) ? 0 : 2);
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

function base_url(): string
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
            if (time() - ($_SESSION['admin_seen'] ?? 0) > 12 * 3600) { // 12 hours without use
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
    return $a;
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

// active / expiring / expired / none
function member_status(?string $expiry): string
{
    if (!$expiry) {
        return 'none';
    }
    if ($expiry < today()) {
        return 'expired';
    }
    $soon = date('Y-m-d', strtotime('+' . (int)setting('expiry_days', '7') . ' day'));
    return $expiry <= $soon ? 'expiring' : 'active';
}

function status_badge(?string $expiry): string
{
    $s = member_status($expiry);
    $cls = ['active' => 'success', 'expiring' => 'warning text-dark', 'expired' => 'danger', 'none' => 'secondary'][$s];
    $label = $s === 'expiring' ? 'active' : $s;
    $extra = $s === 'expiring' ? ' <i class="bi bi-hourglass-split"></i>' : '';
    return '<span class="badge bg-' . $cls . '" data-en="' . e(t_en('st_' . $label)) . '">' . e(t('st_' . $label)) . $extra . '</span>';
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
        q('UPDATE members SET plan_id = ?, start_date = ?, expiry_date = ? WHERE id = ?',
            [$p['plan_id'], $p['period_start'], $p['period_end'], $memberId]);
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
    if (!$m || $m['expiry_date'] !== $p['period_end']) {
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

function reminder_text(array $m, float $amount = 0): string
{
    $s = member_status($m['expiry_date']);
    $msg = $s === 'expired'
        ? t('wa_expired', $m['name'], gym_title(), fdate($m['expiry_date']))
        : t('wa_expiring', $m['name'], gym_title(), fdate($m['expiry_date']));
    return $msg . upi_text($amount);
}
