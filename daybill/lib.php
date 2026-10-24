<?php
// Shared helpers: config, database, sessions, auth, CSRF, settings.

declare(strict_types=1);

$CONFIG = require __DIR__ . '/config.php';

function cfg(string $key)
{
    global $CONFIG;
    return $CONFIG[$key] ?? null;
}

require_once __DIR__ . '/https.php';

if (PHP_SAPI !== 'cli' && session_status() === PHP_SESSION_NONE) {
    session_name('daybill_sid');
    session_set_cookie_params([
        'lifetime' => 0,
        'path'     => '/',
        'secure'   => true,
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
        migrate($pdo);
    }
    return $pdo;
}

// Upgrades databases created by older versions of the app.
function migrate(PDO $pdo): void
{
    try {
        $v = (int)$pdo->query("SELECT v FROM settings WHERE k = 'schema_version'")->fetchColumn();
    } catch (PDOException $e) {
        exit('Database not installed yet – open install.php first.');
    }
    if ($v < 2) {
        $pdo->exec('ALTER TABLE settings MODIFY v TEXT NOT NULL');
        $pdo->exec("ALTER TABLE job_files
            MODIFY paper VARCHAR(30) NOT NULL DEFAULT 'A4',
            MODIFY status ENUM('pending','queued','sending','printed','failed') NOT NULL DEFAULT 'pending',
            ADD COLUMN price DECIMAL(10,2) NULL AFTER page_range,
            ADD COLUMN queued_at DATETIME NULL AFTER print_count");
        $pdo->exec("INSERT INTO settings (k, v) VALUES ('schema_version', '2') ON DUPLICATE KEY UPDATE v = '2'");
    }
    if ($v < 3) {
        $pdo->exec("ALTER TABLE job_files ADD COLUMN printer VARCHAR(200) NOT NULL DEFAULT '' AFTER price");
        $pdo->exec("INSERT INTO settings (k, v) VALUES ('schema_version', '3') ON DUPLICATE KEY UPDATE v = '3'");
    }
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
    $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
    $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    return 'https://' . $host . $dir . '/';
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

function setting(string $key, string $default = '', bool $reload = false): string
{
    static $cache = null;
    if ($cache === null || $reload) {
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
    setting($key, '', true);
}

// ---- Print options ------------------------------------------------

const BUILTIN_PAPERS = ['A4', 'A3', 'A5', 'A6', 'A2', 'Letter', 'Legal', 'Tabloid', 'Statement'];
const ALLOWED_EXT = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'];
const COLORS = ['bw', 'color'];
const SIDES = ['single', 'double'];

function csv_setting(string $key, string $default): array
{
    return array_values(array_filter(array_map('trim', explode(',', setting($key, $default))), 'strlen'));
}

// Built-in sizes plus any custom sizes the admin added (e.g. "Photo 4x6").
function all_papers(): array
{
    return array_values(array_unique(array_merge(BUILTIN_PAPERS, csv_setting('papers_custom', ''))));
}

function enabled_papers(): array
{
    $on = array_values(array_intersect(all_papers(), csv_setting('papers_enabled', 'A4')));
    return $on ?: ['A4'];
}

function enabled_colors(): array
{
    return array_values(array_intersect(COLORS, csv_setting('colors_enabled', 'bw,color'))) ?: ['bw'];
}

function enabled_sides(): array
{
    return array_values(array_intersect(SIDES, csv_setting('sides_enabled', 'single,double'))) ?: ['single'];
}

function pick(string $value, array $allowed): string
{
    return in_array($value, $allowed, true) ? $value : $allowed[0];
}

// Validates print options; only offered (enabled) choices are accepted.
function clean_options(array $in): array
{
    $copies = max(1, min(999, (int)($in['copies'] ?? 1)));
    $range = preg_replace('/\s+/', '', (string)($in['page_range'] ?? ''));
    if (!preg_match('/^(\d+(-\d+)?)(,\d+(-\d+)?)*$/', $range)) {
        $range = ''; // empty = all pages
    }
    return [
        'copies'      => $copies,
        'paper'       => pick((string)($in['paper'] ?? ''), enabled_papers()),
        'color'       => pick((string)($in['color'] ?? ''), enabled_colors()),
        'sides'       => pick((string)($in['sides'] ?? ''), enabled_sides()),
        'orientation' => ($in['orientation'] ?? '') === 'landscape' ? 'landscape' : 'portrait',
        'page_range'  => $range,
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

// ---- Pricing ------------------------------------------------------
// Each paper/colour/sides combination has a rule:
//   [first N pages, fixed price for those N pages, price for each extra page]
// e.g. [2, 2, 1] = pages 1–2 cost 2 SR, every page after that costs 1 SR.

const DEFAULT_RULE = [1, 1.0, 1.0];

function pricing_table(): array
{
    $t = json_decode(setting('pricing', '{}'), true);
    return is_array($t) ? $t : [];
}

function price_rule(string $paper, string $color, string $sides): array
{
    $r = pricing_table()[$paper][$color][$sides] ?? null;
    if (!is_array($r) || count($r) !== 3) {
        return DEFAULT_RULE;
    }
    return [max(0, (int)$r[0]), max(0, (float)$r[1]), max(0, (float)$r[2])];
}

function rule_price(array $rule, int $pages): float
{
    [$n, $base, $extra] = $rule;
    return round($base + max(0, $pages - $n) * $extra, 2);
}

// Price calculated from the rules (ignores a staff override).
function auto_price(array $f): float
{
    $pages = pages_selected((int)$f['pages_total'], (string)$f['page_range']) * (int)$f['copies'];
    return rule_price(price_rule($f['paper'], $f['color'], $f['sides']), $pages);
}

// Price to charge: staff override if set, otherwise calculated.
function file_price(array $f): float
{
    return isset($f['price']) && $f['price'] !== null ? (float)$f['price'] : auto_price($f);
}

function money(float $v): string
{
    $s = number_format($v, 2);
    return (substr($s, -3) === '.00' ? substr($s, 0, -3) : $s) . ' ' . setting('currency', 'SR');
}

// Largest /Count of a /Type /Pages dictionary, i.e. the root of the page tree.
function pdf_tree_count(string $data): int
{
    $max = 0;
    if (preg_match_all('/<<[^<>]*\/Type\s*\/Pages\b[^<>]*>>/', $data, $m)) {
        foreach ($m[0] as $dict) {
            if (preg_match('/\/Count\s+(\d+)/', $dict, $c)) {
                $max = max($max, (int)$c[1]);
            }
        }
    }
    if (!$max && preg_match_all('/\/Type\s*\/Pages\b[^>]*?\/Count\s+(\d+)/s', $data, $m)) {
        $max = (int)max($m[1]);
    }
    return $max;
}

// Page count without external tools. Newer PDFs keep the page tree inside
// compressed object streams (/ObjStm), so those are inflated and searched too.
function pdf_page_count(string $path): int
{
    $data = @file_get_contents($path);
    if ($data === false) {
        return 0;
    }
    $inflated = '';
    $offset = 0;
    while (preg_match('/stream\r?\n/', $data, $m, PREG_OFFSET_CAPTURE, $offset)) {
        $start = $m[0][1] + strlen($m[0][0]);
        $end = strpos($data, 'endstream', $start);
        if ($end === false) {
            break;
        }
        $dict = substr($data, max(0, $m[0][1] - 400), min(400, $m[0][1]));
        $dict = substr($dict, (int)strrpos($dict, 'obj'));
        if (strpos($dict, '/ObjStm') !== false && strpos($dict, '/FlateDecode') !== false) {
            $raw = rtrim(substr($data, $start, $end - $start), "\r\n");
            $out = @gzuncompress($raw);
            if ($out === false) {
                $out = @gzinflate(substr($raw, 2));
            }
            if ($out !== false) {
                $inflated .= $out . "\n";
            }
        }
        $offset = $end + 9;
    }
    $all = $data . "\n" . $inflated;
    return pdf_tree_count($all) ?: preg_match_all('/\/Type\s*\/Page\b(?!s)/', $all);
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

// ---- Customer language (English / Arabic) ------------------------

function lang(): string
{
    static $lang = null;
    if ($lang === null) {
        $want = $_GET['lang'] ?? $_COOKIE['daybill_lang'] ?? setting('default_lang', 'en');
        $lang = $want === 'ar' ? 'ar' : 'en';
        if (isset($_GET['lang']) && PHP_SAPI !== 'cli') {
            setcookie('daybill_lang', $lang, ['expires' => time() + 31536000, 'path' => '/',
                'secure' => true, 'samesite' => 'Lax']);
        }
    }
    return $lang;
}

function t(string $key, ...$args): string
{
    static $dict = null;
    if ($dict === null) {
        $dict = require __DIR__ . '/lang.php';
    }
    $s = $dict[lang()][$key] ?? $dict['en'][$key] ?? $key;
    return $args ? vsprintf($s, $args) : $s;
}

// ---- App colours (Settings → App colour) ---------------------------

const DEFAULT_COLORS = ['#360dd9', '#7ed957']; // DAYbill logo purple + green

function valid_hex(string $c): bool
{
    return (bool)preg_match('/^#[0-9a-f]{6}$/i', $c);
}

function app_colors(): array
{
    $p = strtolower(setting('color_primary', DEFAULT_COLORS[0]));
    $a = strtolower(setting('color_accent', DEFAULT_COLORS[1]));
    return [valid_hex($p) ? $p : DEFAULT_COLORS[0], valid_hex($a) ? $a : DEFAULT_COLORS[1]];
}

// Mixes a colour with white (amount > 0) or black (amount < 0).
function mix_hex(string $hex, float $amount): string
{
    $rgb = sscanf($hex, '#%02x%02x%02x');
    $to = $amount >= 0 ? 255 : 0;
    $k = abs($amount);
    return vsprintf('#%02x%02x%02x', array_map(fn($c) => (int)round($c + ($to - $c) * $k), $rgb));
}

function luminance(string $hex): float
{
    [$r, $g, $b] = array_map(function ($c) {
        $c /= 255;
        return $c <= 0.03928 ? $c / 12.92 : (($c + 0.055) / 1.055) ** 2.4;
    }, sscanf($hex, '#%02x%02x%02x'));
    return 0.2126 * $r + 0.7152 * $g + 0.0722 * $b;
}

// CSS variables for the chosen colours, incl. tints and readable text colours.
function theme_css(): string
{
    [$p, $a] = app_colors();
    $dark = fn(string $c) => luminance($c) > 0.18 ? mix_hex($c, -0.55) : mix_hex($c, -0.2);
    $vars = [
        '--primary' => $p, '--accent' => $a,
        '--on-primary' => luminance($p) > 0.45 ? '#111111' : '#ffffff',
        '--p-50' => mix_hex($p, 0.95), '--p-100' => mix_hex($p, 0.9), '--p-200' => mix_hex($p, 0.72),
        '--p-300' => mix_hex($p, 0.6), '--p-dark' => $dark($p),
        '--a-50' => mix_hex($a, 0.88), '--a-200' => mix_hex($a, 0.6), '--a-dark' => $dark($a),
    ];
    $css = '';
    foreach ($vars as $k => $v) {
        $css .= "$k:$v;";
    }
    return ':root{' . $css . '}';
}

// ---- Layout (installable app shell) --------------------------------

/**
 * @param string $back  URL for a "‹" back button (sub-pages); '' shows the shop name instead.
 */
function page_header(string $title, bool $staff = false, string $lang = 'en', string $back = ''): void
{
    global $LAYOUT_STAFF;
    $LAYOUT_STAFF = $staff;
    $shop = setting('shop_name', 'Daybill Print');
    $u = $staff ? current_user() : null;
    $rtl = $lang === 'ar';
    echo '<!doctype html><html lang="' . h($lang) . '" dir="' . ($rtl ? 'rtl' : 'ltr') . '"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        . '<title>' . h($title) . ' – ' . h($shop) . '</title>'
        . '<meta name="theme-color" content="#ffffff">'
        . '<link rel="manifest" href="manifest.php' . ($staff ? '?app=staff' : '') . '">'
        . '<link rel="icon" type="image/png" href="assets/icons/favicon.png">'
        . '<link rel="apple-touch-icon" href="assets/icons/apple-touch-icon.png">'
        . '<meta name="apple-mobile-web-app-capable" content="yes">'
        . '<meta name="mobile-web-app-capable" content="yes">'
        . '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
        . '<meta name="apple-mobile-web-app-title" content="' . h($staff ? 'Print Staff' : $shop) . '">'
        . '<link rel="stylesheet" href="assets/style.css?v=7">'
        . '<style>' . theme_css() . '</style>'
        . '<script src="assets/app.js?v=6" defer></script></head>'
        . '<body class="' . ($u ? 'has-tabs' : '') . '">';
    echo '<header class="top"><div class="wrap">';
    if ($back !== '') {
        echo '<a class="back-btn" href="' . h($back) . '" aria-label="Back">' . ($rtl ? '›' : '‹') . '</a>'
            . '<span class="title">' . h($title) . '</span>';
    } else {
        echo '<a class="brand" href="' . ($staff ? 'staff.php' : 'index.php') . '">'
            . '<img class="logo" src="assets/logo.png" alt="' . h($shop) . '" width="120" height="38"></a>';
    }
    if (!$staff && basename($_SERVER['SCRIPT_NAME'] ?? '') === 'index.php') {
        echo '<nav class="lang"><button type="button" class="install-chip hidden" data-install>⬇ ' . h(t('install_app')) . '</button>'
            . ($rtl ? '<a href="?lang=en">English</a>' : '<a href="?lang=ar">العربية</a>') . '</nav>';
    }
    echo '</div></header><main class="wrap">';
}

// "Install app" box: install button (Android/Chrome/Edge) or Add-to-Home-Screen steps (iPhone).
function install_box(bool $showHelp = true): string
{
    return '<div class="install-box">'
        . '<button type="button" class="btn primary block hidden" data-install>⬇ ' . h(t('install_app')) . '</button>'
        . '<div class="hidden muted" data-install-ios>📱 ' . h(t('install_ios')) . '</div>'
        . ($showHelp ? '<div class="hidden muted" data-install-other>💻 ' . h(t('install_other')) . '</div>' : '')
        . '<div class="hidden ok-text" data-installed>✓ ' . h(t('installed')) . '</div>'
        . '</div>';
}

function page_footer(): void
{
    global $LAYOUT_STAFF;
    echo '</main>';
    $u = $LAYOUT_STAFF ? current_user() : null;
    if ($u) {
        $page = basename($_SERVER['SCRIPT_NAME'] ?? '');
        $tab = fn(string $href, array $pages, string $icon, string $label) =>
            '<a href="' . $href . '" class="' . (in_array($page, $pages, true) ? 'on' : '') . '"><span>' . $icon . '</span>' . $label . '</a>';
        echo '<nav class="tabbar">'
            . $tab('staff.php', ['staff.php', 'job.php'], '🖨️', 'Jobs')
            . ($u['role'] === 'admin' ? $tab('qr.php', ['qr.php'], '▦', 'QR code') : '')
            . $tab('settings.php', ['settings.php', 'admin.php', 'account.php'], '⚙️', 'Settings')
            . '</nav>';
    }
    echo '</body></html>';
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
