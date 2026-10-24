<?php
// Shared helpers: config, database, sessions, auth, CSRF, settings.

declare(strict_types=1);

$CONFIG = require __DIR__ . '/config.php';

function cfg(string $key)
{
    global $CONFIG;
    return $CONFIG[$key] ?? null;
}

function is_https(): bool
{
    return (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || ($_SERVER['SERVER_PORT'] ?? '') == 443
        || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
}

if (PHP_SAPI !== 'cli' && cfg('force_https') && !is_https()) {
    $host = preg_replace('/:\d+$/', '', $_SERVER['HTTP_HOST'] ?? 'localhost');
    header('Location: https://' . $host . ($_SERVER['REQUEST_URI'] ?? '/'), true, 301);
    exit;
}

if (PHP_SAPI !== 'cli' && session_status() === PHP_SESSION_NONE) {
    session_name('daybill_sid');
    session_set_cookie_params([
        'lifetime' => 0,
        'path'     => '/',
        'secure'   => is_https(),
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
    session_start();
}

function db(): PDO
{
    static $pdo = null;
    if ($pdo === null) {
        $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
            cfg('db_host'), cfg('db_port'), cfg('db_name'));
        $pdo = new PDO($dsn, cfg('db_user'), cfg('db_pass'), [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]);
    }
    return $pdo;
}

function h($s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

function redirect(string $url): void
{
    header('Location: ' . $url);
    exit;
}

function base_url(): string
{
    $scheme = is_https() ? 'https' : 'http';
    $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
    $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    return $scheme . '://' . $host . $dir . '/';
}

// ---- CSRF ---------------------------------------------------------

function csrf_token(): string
{
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
}

function csrf_check(): void
{
    if (!hash_equals($_SESSION['csrf'] ?? '', (string)($_POST['csrf'] ?? ''))) {
        http_response_code(400);
        exit('Session expired. Please go back and try again.');
    }
}

// ---- Auth ---------------------------------------------------------

function current_user(): ?array
{
    static $user = false;
    if ($user === false) {
        $user = null;
        if (!empty($_SESSION['uid'])) {
            $st = db()->prepare('SELECT id, username, full_name, role FROM users WHERE id = ? AND active = 1');
            $st->execute([$_SESSION['uid']]);
            $user = $st->fetch() ?: null;
            if (!$user) {
                unset($_SESSION['uid']);
            }
        }
    }
    return $user;
}

function require_login(): array
{
    $u = current_user();
    if (!$u) {
        redirect('login.php');
    }
    return $u;
}

function require_admin(): array
{
    $u = require_login();
    if ($u['role'] !== 'admin') {
        http_response_code(403);
        exit('Admins only.');
    }
    return $u;
}

// ---- Settings (key/value table) -----------------------------------

function setting(string $key, string $default = ''): string
{
    static $cache = null;
    if ($cache === null) {
        $cache = [];
        foreach (db()->query('SELECT k, v FROM settings') as $row) {
            $cache[$row['k']] = $row['v'];
        }
    }
    return $cache[$key] ?? $default;
}

function save_setting(string $key, string $value): void
{
    $st = db()->prepare('INSERT INTO settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)');
    $st->execute([$key, $value]);
}

// ---- Print options ------------------------------------------------

const PAPER_SIZES = ['A4', 'A3', 'A5', 'Letter', 'Legal'];
const ALLOWED_EXT = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'];

function clean_options(array $in): array
{
    $copies = max(1, min(999, (int)($in['copies'] ?? 1)));
    $paper = in_array($in['paper'] ?? '', PAPER_SIZES, true) ? $in['paper'] : 'A4';
    $color = ($in['color'] ?? '') === 'color' ? 'color' : 'bw';
    $sides = ($in['sides'] ?? '') === 'double' ? 'double' : 'single';
    $orient = ($in['orientation'] ?? '') === 'landscape' ? 'landscape' : 'portrait';
    $range = preg_replace('/\s+/', '', (string)($in['page_range'] ?? ''));
    if (!preg_match('/^(\d+(-\d+)?)(,\d+(-\d+)?)*$/', $range)) {
        $range = ''; // empty = all pages
    }
    return [
        'copies' => $copies, 'paper' => $paper, 'color' => $color,
        'sides' => $sides, 'orientation' => $orient, 'page_range' => $range,
    ];
}

// Number of pages that will be printed per copy, given total pages and a range.
function pages_selected(int $total, string $range): int
{
    if ($range === '') {
        return max(1, $total);
    }
    $pages = [];
    foreach (explode(',', $range) as $part) {
        [$a, $b] = array_pad(explode('-', $part), 2, null);
        $a = (int)$a;
        $b = $b === null ? $a : (int)$b;
        if ($b < $a) {
            [$a, $b] = [$b, $a];
        }
        if ($total > 0) {
            $b = min($b, $total);
        }
        for ($i = $a; $i <= $b && count($pages) < 10000; $i++) {
            $pages[$i] = true;
        }
    }
    return max(1, count($pages));
}

function estimate_price(array $f): float
{
    $per = (float)setting($f['color'] === 'color' ? 'price_color' : 'price_bw', '0');
    return pages_selected((int)$f['pages_total'], (string)$f['page_range']) * (int)$f['copies'] * $per;
}

// Rough PDF page count without external tools.
function pdf_page_count(string $path): int
{
    $data = @file_get_contents($path);
    if ($data === false) {
        return 0;
    }
    if (preg_match_all('/\/Type\s*\/Pages\b[^>]*?\/Count\s+(\d+)/s', $data, $m)) {
        return (int)max($m[1]);
    }
    return preg_match_all('/\/Type\s*\/Page\b(?!s)/', $data);
}

function format_bytes(int $b): string
{
    if ($b >= 1048576) {
        return round($b / 1048576, 1) . ' MB';
    }
    return max(1, (int)round($b / 1024)) . ' KB';
}

// Delete files of jobs older than the retention period.
function cleanup_old_files(): void
{
    $days = (int)setting('retention_days', '2');
    if ($days <= 0) {
        return;
    }
    $st = db()->prepare('SELECT f.id, f.stored_name FROM job_files f JOIN jobs j ON j.id = f.job_id
                         WHERE j.created_at < (NOW() - INTERVAL ? DAY) AND f.stored_name <> \'\'');
    $st->execute([$days]);
    $upd = db()->prepare('UPDATE job_files SET stored_name = \'\' WHERE id = ?');
    foreach ($st as $row) {
        @unlink(cfg('upload_dir') . '/' . $row['stored_name']);
        @unlink(cfg('upload_dir') . '/' . $row['stored_name'] . '.pdf');
        $upd->execute([$row['id']]);
    }
}

// ---- Layout -------------------------------------------------------

function page_header(string $title, bool $staff = false): void
{
    $shop = setting('shop_name', 'Daybill Print');
    $u = $staff ? current_user() : null;
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width, initial-scale=1">'
        . '<title>' . h($title) . ' – ' . h($shop) . '</title>'
        . '<link rel="stylesheet" href="assets/style.css"></head><body>';
    echo '<header class="top"><div class="wrap"><a class="brand" href="' . ($staff ? 'staff.php' : 'index.php') . '">🖨️ ' . h($shop) . '</a>';
    if ($u) {
        echo '<nav><a href="staff.php">Jobs</a>';
        if ($u['role'] === 'admin') {
            echo '<a href="admin.php">Admin</a><a href="qr.php">QR code</a>';
        }
        echo '<a href="logout.php">Logout (' . h($u['username']) . ')</a></nav>';
    }
    echo '</div></header><main class="wrap">';
}

function page_footer(): void
{
    echo '</main></body></html>';
}

function flash(?string $msg = null, string $type = 'ok'): string
{
    if ($msg !== null) {
        $_SESSION['flash'] = [$msg, $type];
        return '';
    }
    if (empty($_SESSION['flash'])) {
        return '';
    }
    [$m, $t] = $_SESSION['flash'];
    unset($_SESSION['flash']);
    return '<div class="alert ' . h($t) . '">' . h($m) . '</div>';
}
