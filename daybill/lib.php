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

if (PHP_SAPI !== 'cli' && !defined('DAYBILL_NO_SESSION') && session_status() === PHP_SESSION_NONE) {
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
        $v = (int)$pdo->query("SELECT v FROM settings WHERE k = 'schema_version' LIMIT 1")->fetchColumn();
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
    if ($v < 4) {
        // Multiple shops: the existing shop becomes shop 1, its first admin becomes super admin.
        $pdo->exec("CREATE TABLE IF NOT EXISTS shops (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, slug VARCHAR(40) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL,
            active TINYINT(1) NOT NULL DEFAULT 1, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
        $name = (string)($pdo->query("SELECT v FROM settings WHERE k = 'shop_name'")->fetchColumn() ?: 'Main shop');
        $pdo->prepare("INSERT IGNORE INTO shops (id, slug, name) VALUES (1, 'main', ?)")->execute([$name]);
        $pdo->exec('ALTER TABLE settings ADD COLUMN shop_id INT UNSIGNED NOT NULL DEFAULT 1 FIRST, DROP PRIMARY KEY, ADD PRIMARY KEY (shop_id, k)');
        $pdo->exec("UPDATE settings SET shop_id = 0 WHERE k = 'schema_version'");
        $pdo->exec("ALTER TABLE users ADD COLUMN shop_id INT UNSIGNED NULL AFTER id,
            MODIFY role ENUM('super','admin','employee') NOT NULL DEFAULT 'employee'");
        $pdo->exec('UPDATE users SET shop_id = 1');
        $pdo->exec("UPDATE users SET role = 'super', shop_id = NULL WHERE role = 'admin' ORDER BY id LIMIT 1");
        $pdo->exec('ALTER TABLE jobs ADD COLUMN shop_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id, ADD KEY idx_shop (shop_id, status)');
        $pdo->exec("UPDATE settings SET v = '4' WHERE shop_id = 0 AND k = 'schema_version'");
    }
    if ($v < 5) {
        // Layouts (N pages per sheet, photo sheets): keep the customer's original next to the print-ready file.
        $pdo->exec("ALTER TABLE job_files ADD COLUMN layout VARCHAR(40) NOT NULL DEFAULT '' AFTER page_range,
            ADD COLUMN orig_name VARCHAR(100) NOT NULL DEFAULT '' AFTER stored_name,
            ADD COLUMN orig_ext VARCHAR(10) NOT NULL DEFAULT '' AFTER orig_name");
        $pdo->exec("UPDATE settings SET v = '5' WHERE shop_id = 0 AND k = 'schema_version'");
    }
    if ($v < 6) {
        // Photo print tool: photo items are marked so they get photo prices and the photo printer.
        $pdo->exec("ALTER TABLE job_files ADD COLUMN kind VARCHAR(10) NOT NULL DEFAULT '' AFTER layout");
        $pdo->exec("UPDATE settings SET v = '6' WHERE shop_id = 0 AND k = 'schema_version'");
    }
}

function h($s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

// Settings pages can be shown inside a sheet (a panel sliding up, ?sheet=1): no app bars there.
function in_sheet(): bool
{
    return ($_GET['sheet'] ?? '') === '1';
}

// Hidden field that keeps a GET form inside its sheet.
function sheet_field(): string
{
    return in_sheet() ? '<input type="hidden" name="sheet" value="1">' : '';
}

function redirect(string $url): void
{
    // Stay inside the sheet after saving a settings page.
    if (in_sheet() && preg_match('/^(admin|account|shops|qr)\.php/', $url)) {
        $url .= (strpos($url, '?') === false ? '?' : '&') . 'sheet=1';
    }
    header('Location: ' . $url);
    exit;
}

// Popup (bottom sheet) on the same page: sheet_start('opt1', 'Options') … sheet_end()
function sheet_start(string $id, string $title, string $class = ''): string
{
    return '<dialog class="sheet ' . h($class) . '" id="' . h($id) . '"><div class="sheet-head"><span class="grip"></span><b>' . h($title)
        . '</b><button type="button" class="sheet-x" aria-label="Close">✕</button></div><div class="sheet-body">';
}

function sheet_end(): string
{
    return '</div></dialog>';
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

// ---- Shops ----------------------------------------------------------
// Every order, employee and setting belongs to a shop. The current shop comes from
// the logged-in user (super admins choose one), the ?shop= link (customers) or the
// agent key (print agent).

function shop_id(?int $set = null): int
{
    static $id = 0;
    if ($set !== null) {
        $id = $set;
        setting('', '', true); // reload settings for this shop
    }
    return $id;
}

function shop(): ?array
{
    static $cache = [];
    $id = shop_id();
    if (!array_key_exists($id, $cache)) {
        $st = db()->prepare('SELECT * FROM shops WHERE id = ?');
        $st->execute([$id]);
        $cache[$id] = $st->fetch() ?: null;
    }
    return $cache[$id];
}

function all_shops(bool $activeOnly = false): array
{
    return db()->query('SELECT * FROM shops' . ($activeOnly ? ' WHERE active = 1' : '') . ' ORDER BY name')->fetchAll();
}

function shop_by_slug(string $slug): ?array
{
    $st = db()->prepare('SELECT * FROM shops WHERE slug = ? AND active = 1');
    $st->execute([$slug]);
    return $st->fetch() ?: null;
}

// Link to this shop's customer page (used for the QR code and the app manifest).
function shop_url(string $page = 'index.php'): string
{
    $s = shop();
    return base_url() . $page . ($s ? '?shop=' . rawurlencode($s['slug']) : '');
}

const DEFAULT_SETTINGS = [
    'print_mode' => 'agent', 'printer_bw' => '', 'printer_color' => '', 'printer_map' => '{}',
    'papers_enabled' => 'A4,A3', 'papers_custom' => '', 'colors_enabled' => 'bw,color', 'sides_enabled' => 'single,double',
    'pricing' => '{"A4":{"bw":{"single":[1,2,1],"double":[1,2,1]},"color":{"single":[1,5,3],"double":[1,5,3]}},"A3":{"bw":{"single":[1,4,2],"double":[1,4,2]},"color":{"single":[1,10,6],"double":[1,10,6]}}}',
    'currency' => 'SR', 'default_lang' => 'en', 'retention_days' => '2', 'auto_complete' => '1',
    'layouts_enabled' => 'nup2,nup4,photo4,passport',
    'photo_enabled' => '0', 'photo_paper' => 'A4', 'photo_sizes' => 'passport,photo4x6,photo10x15', 'photo_price_mode' => 'photo',
];

// Creates a shop with default settings and its first admin. Returns the shop id.
function create_shop(string $name, string $slug, string $adminUser, string $adminPass, string $adminName = ''): int
{
    $pdo = db();
    $pdo->prepare('INSERT INTO shops (slug, name) VALUES (?, ?)')->execute([$slug, $name]);
    $id = (int)$pdo->lastInsertId();
    $ins = $pdo->prepare('INSERT INTO settings (shop_id, k, v) VALUES (?, ?, ?)');
    foreach (DEFAULT_SETTINGS + ['shop_name' => $name, 'agent_key' => bin2hex(random_bytes(20))] as $k => $v) {
        $ins->execute([$id, $k, $v]);
    }
    if ($adminUser !== '') {
        $pdo->prepare("INSERT INTO users (shop_id, username, full_name, password_hash, role) VALUES (?, ?, ?, ?, 'admin')")
            ->execute([$id, $adminUser, $adminName, password_hash($adminPass, PASSWORD_DEFAULT)]);
    }
    return $id;
}

function valid_slug(string $slug): bool
{
    return (bool)preg_match('/^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$/', $slug);
}

function valid_username(string $u): bool
{
    return (bool)preg_match('/^[A-Za-z0-9_.-]{3,50}$/', $u);
}

// ---- Auth ---------------------------------------------------------

function current_user(): ?array
{
    static $user = false;
    if ($user === false) {
        $user = null;
        if (!empty($_SESSION['uid'])) {
            $st = db()->prepare('SELECT u.id, u.shop_id, u.username, u.full_name, u.role FROM users u
                                 LEFT JOIN shops s ON s.id = u.shop_id
                                 WHERE u.id = ? AND u.active = 1 AND (u.role = \'super\' OR s.active = 1)');
            $st->execute([$_SESSION['uid']]);
            $user = $st->fetch() ?: null;
            if (!$user) {
                unset($_SESSION['uid']);
            }
        }
    }
    return $user;
}

function is_super(?array $u = null): bool
{
    $u = $u ?? current_user();
    return $u !== null && $u['role'] === 'super';
}

function require_login(): array
{
    $u = current_user();
    if (!$u) {
        redirect('login.php');
    }
    if (is_super($u)) {
        // Super admins work in the shop they picked (Settings → Shops), or the first one.
        $sid = (int)($_SESSION['shop_id'] ?? 0);
        $ids = array_map('intval', array_column(all_shops(), 'id'));
        if (!in_array($sid, $ids, true)) {
            $sid = $ids[0] ?? 0;
            $_SESSION['shop_id'] = $sid;
        }
        shop_id($sid);
        if ($sid === 0 && !in_array(basename($_SERVER['SCRIPT_NAME'] ?? ''), ['shops.php', 'account.php', 'settings.php'], true)) {
            redirect('shops.php'); // no shop yet: create one first
        }
    } else {
        shop_id((int)$u['shop_id']);
    }
    return $u;
}

function require_admin(): array
{
    $u = require_login();
    if (!in_array($u['role'], ['admin', 'super'], true)) {
        http_response_code(403);
        exit('Admins only.');
    }
    return $u;
}

function require_super(): array
{
    $u = require_login();
    if (!is_super($u)) {
        http_response_code(403);
        exit('Super admin only.');
    }
    return $u;
}

// ---- Settings (key/value per shop; shop 0 = whole system) ---------

function setting(string $key, string $default = '', bool $reload = false): string
{
    static $cache = null;
    if ($cache === null || $reload) {
        $cache = [];
        $st = db()->prepare('SELECT k, v FROM settings WHERE shop_id = ?');
        $st->execute([shop_id()]);
        foreach ($st as $row) {
            $cache[$row['k']] = $row['v'];
        }
    }
    return $cache[$key] ?? $default;
}

function save_setting(string $key, string $value): void
{
    $st = db()->prepare('INSERT INTO settings (shop_id, k, v) VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)');
    $st->execute([shop_id(), $key, $value]);
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

// ---- Layouts (Settings → Layouts) -----------------------------------
// The print-ready PDF is made in the browser by assets/layout.js; these are the choices.

const BUILTIN_LAYOUTS = [
    'nup2'     => ['type' => 'nup', 'n' => 2, 'label' => '2 pages on one sheet'],
    'nup4'     => ['type' => 'nup', 'n' => 4, 'label' => '4 pages on one sheet'],
    'nup8'     => ['type' => 'nup', 'n' => 8, 'label' => '8 pages on one sheet'],
    'photo2'   => ['type' => 'grid', 'n' => 2, 'label' => '2 photos on one sheet'],
    'photo4'   => ['type' => 'grid', 'n' => 4, 'label' => '4 photos on one sheet'],
    'photo8'   => ['type' => 'grid', 'n' => 8, 'label' => '8 photos on one sheet'],
    'passport' => ['type' => 'size', 'w' => 35, 'h' => 45, 'label' => 'Passport photo 3.5 × 4.5 cm'],
    'photo4x6' => ['type' => 'size', 'w' => 40, 'h' => 60, 'label' => 'Photo 4 × 6 cm'],
    'photo5x5' => ['type' => 'size', 'w' => 51, 'h' => 51, 'label' => 'Photo 5 × 5 cm (2 × 2 in)'],
    'photo10x15' => ['type' => 'size', 'w' => 102, 'h' => 152, 'label' => 'Photo 10 × 15 cm (4 × 6 in)'],
    'photo13x18' => ['type' => 'size', 'w' => 127, 'h' => 178, 'label' => 'Photo 13 × 18 cm (5 × 7 in)'],
];

// ---- Photo print tool (Settings → Photo print) -----------------------
const PHOTO_PAPERS = ['A4', 'A5', 'A6', 'Letter', '10x15 cm', '13x18 cm'];

function photo_enabled(): bool
{
    return setting('photo_enabled', '0') === '1' && photo_sizes();
}

function photo_paper(): string
{
    $p = setting('photo_paper', 'A4');
    return in_array($p, PHOTO_PAPERS, true) ? $p : 'A4';
}

// Exact photo sizes the tool offers (built-in sizes and the shop's own sizes).
function photo_sizes(): array
{
    $sizes = array_filter(all_layouts(), fn($L) => $L['type'] === 'size');
    return array_intersect_key($sizes, array_flip(csv_setting('photo_sizes', 'passport,photo4x6,photo10x15')));
}

// "passport:8" → valid code for the photo tool, or ''.
function clean_photo_layout(string $code): string
{
    [$id, $pieces] = array_pad(explode(':', $code, 2), 2, '');
    return isset(photo_sizes()[$id]) && (int)$pieces >= 1 ? $id . ':' . min(500, (int)$pieces) : '';
}

// Price of a photo item: per photo or per sheet (Settings → Photo print); null = normal colour page prices.
function photo_price(array $f): ?float
{
    $price = setting('photo_price', '');
    if ($price === '') {
        return null;
    }
    $count = setting('photo_price_mode', 'photo') === 'sheet'
        ? max(1, (int)$f['pages_total'])
        : max(1, (int)(explode(':', (string)$f['layout'])[1] ?? 1));
    return round($count * (int)$f['copies'] * max(0, (float)$price), 2);
}

// Built-in layouts plus the shop's own photo sizes ("Visa photo = 30x40", one per line).
function all_layouts(): array
{
    $all = BUILTIN_LAYOUTS;
    foreach (preg_split('/\R/', setting('layouts_custom', '')) as $line) {
        if (preg_match('/^\s*(.{1,40}?)\s*=\s*(\d{1,3}(?:\.\d)?)\s*[x×*]\s*(\d{1,3}(?:\.\d)?)\s*$/u', $line, $m)) {
            $w = (float)$m[2];
            $h = (float)$m[3];
            if ($w >= 10 && $h >= 10 && $w <= 280 && $h <= 400) {
                $id = 'sz' . str_replace('.', '_', $m[2] . 'x' . $m[3]);
                $all[$id] = ['type' => 'size', 'w' => $w, 'h' => $h, 'label' => $m[1] . ' ' . $m[2] . ' × ' . $m[3] . ' mm'];
            }
        }
    }
    return $all;
}

function enabled_layouts(): array
{
    $all = all_layouts();
    return array_intersect_key($all, array_flip(csv_setting('layouts_enabled', '')));
}

// Validates a layout code ("nup4", "passport:8"); '' = normal printing.
function clean_layout(string $code): string
{
    [$id, $pieces] = array_pad(explode(':', $code, 2), 2, '');
    $L = enabled_layouts()[$id] ?? null;
    if (!$L) {
        return '';
    }
    return $L['type'] === 'size' ? $id . ':' . max(0, min(200, (int)$pieces)) : $id;
}

function layout_def(string $code): ?array
{
    return all_layouts()[explode(':', $code)[0]] ?? null;
}

function layout_label(string $code): string
{
    $L = layout_def($code);
    if (!$L) {
        return '';
    }
    $pieces = (int)(explode(':', $code)[1] ?? 0);
    return $L['label'] . ($L['type'] === 'size' ? ' – ' . ($pieces ? $pieces . ' pcs' : 'full sheet') : '');
}

// Exact-size photos must not be shrunk by the printer driver.
function print_scale(array $f): string
{
    return (layout_def((string)($f['layout'] ?? ''))['type'] ?? '') === 'size' ? 'noscale' : 'fit';
}

// Optional fixed price per sheet for a layout (photo sheets); null = normal page prices.
function layout_price(string $code): ?float
{
    $prices = json_decode(setting('layout_prices', '{}'), true);
    $v = is_array($prices) ? ($prices[explode(':', $code)[0]] ?? '') : '';
    return $v === '' || $v === null ? null : max(0, (float)$v);
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
    if (($f['kind'] ?? '') === 'photo' && ($pp = photo_price($f)) !== null) {
        return $pp;
    }
    $lp = ($f['layout'] ?? '') !== '' && ($f['kind'] ?? '') !== 'photo' ? layout_price((string)$f['layout']) : null;
    if ($lp !== null) {
        return round(max(1, (int)$f['pages_total']) * (int)$f['copies'] * $lp, 2);
    }
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

// After a file is printed: an order with every file printed becomes "done" by itself
// (Settings → Shop settings → complete automatically), otherwise "printing".
// Returns true when the order was completed now.
function update_job_status(int $jobId): bool
{
    $pdo = db();
    $st = $pdo->prepare('SELECT * FROM job_files WHERE job_id = ?');
    $st->execute([$jobId]);
    $files = $st->fetchAll();
    if (!$files) {
        return false;
    }
    $printed = count(array_filter($files, fn($f) => $f['status'] === 'printed'));
    if ($printed === count($files) && setting('auto_complete', '1') === '1') {
        $total = array_sum(array_map('file_price', $files));
        $up = $pdo->prepare("UPDATE jobs SET status = 'done', amount = IF(amount > 0, amount, ?) WHERE id = ? AND status IN ('new','printing')");
        $up->execute([$total, $jobId]);
        return $up->rowCount() === 1;
    }
    $pdo->prepare("UPDATE jobs SET status = 'printing' WHERE id = ? AND status = 'new'")->execute([$jobId]);
    return false;
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
    $st = db()->prepare('SELECT f.id, f.stored_name, f.orig_name FROM job_files f JOIN jobs j ON j.id = f.job_id
                         WHERE j.shop_id = ? AND j.created_at < (NOW() - INTERVAL ? DAY) AND f.stored_name <> \'\'');
    $st->execute([shop_id(), $days]);
    $upd = db()->prepare('UPDATE job_files SET stored_name = \'\', orig_name = \'\' WHERE id = ?');
    foreach ($st as $row) {
        foreach ([$row['stored_name'], $row['orig_name']] as $name) {
            if ($name !== '') {
                @unlink(cfg('upload_dir') . '/' . $name);
                @unlink(cfg('upload_dir') . '/' . $name . '.pdf');
            }
        }
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
    $sheet = in_sheet();
    echo '<!doctype html><html lang="' . h($lang) . '" dir="' . ($rtl ? 'rtl' : 'ltr') . '"' . ($sheet ? ' class="in-sheet"' : '') . '><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        . '<title>' . h($title) . ' – ' . h($shop) . '</title>'
        . '<meta name="theme-color" content="#ffffff">'
        . '<link rel="manifest" href="manifest.php' . ($staff ? '?app=staff' : (shop() ? '?shop=' . h(rawurlencode(shop()['slug'])) : '')) . '">'
        . '<link rel="icon" type="image/png" href="assets/icons/favicon.png">'
        . '<link rel="apple-touch-icon" href="assets/icons/apple-touch-icon.png">'
        . '<meta name="apple-mobile-web-app-capable" content="yes">'
        . '<meta name="mobile-web-app-capable" content="yes">'
        . '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
        . '<meta name="apple-mobile-web-app-title" content="' . h($staff ? 'Print Staff' : $shop) . '">'
        . '<link rel="stylesheet" href="assets/style.css?v=11">'
        . '<style>' . theme_css() . '</style>'
        . '<script>addEventListener("pagereveal",function(e){var v=e.viewTransition;if(v){v.ready.catch(function(){});v.finished.catch(function(){});}});</script>'
        . '<script src="assets/app.js?v=8" defer></script></head>'
        . '<body class="' . ($u && !$sheet ? 'has-tabs' : '') . '">';
    if ($sheet) { // inside a sheet: the sheet shows the title and the close button
        echo '<main class="wrap">';
        return;
    }
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
    if ($u && is_super($u) && shop()) {
        echo '<a class="shop-chip" href="shops.php" title="Change shop">🏬 ' . h(shop()['name']) . ' ▾</a>';
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
    if ($u && !in_sheet()) {
        $page = basename($_SERVER['SCRIPT_NAME'] ?? '');
        $tab = fn(string $href, array $pages, string $icon, string $label) =>
            '<a href="' . $href . '" class="' . (in_array($page, $pages, true) ? 'on' : '') . '"><span>' . $icon . '</span>' . $label . '</a>';
        echo '<nav class="tabbar">'
            . $tab('staff.php', ['staff.php', 'job.php'], '🖨️', 'Jobs')
            . ($u['role'] !== 'employee' ? $tab('qr.php', ['qr.php'], '▦', 'QR code') : '')
            . $tab('settings.php', ['settings.php', 'admin.php', 'account.php', 'shops.php'], '⚙️', 'Settings')
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
