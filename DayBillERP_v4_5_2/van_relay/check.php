<?php
// ============================================================
// DayBill Van Relay — CHECK PAGE (5.23.2)
// Open  https://your-relay-address/check.php  — and the http:// one.
// It finds what is wrong on the site: SSL certificate, redirect loop,
// old cached answers, .htaccess rules, missing files, database.
// It never shows the shop key, passwords or folder paths.
// ============================================================
require_once __DIR__ . '/van_db.php';
relay_headers('text/html; charset=utf-8');
@set_time_limit(40);

$ROWS = [];   // section => [[state, title, detail]]   state: ok | warn | bad | info
$FIX = [];    // what to do, in order
function row($sec, $st, $title, $detail = '') { global $ROWS; $ROWS[$sec][] = [$st, $title, $detail]; }
function fix($key, $text) { global $FIX; $FIX[$key] = $text; }
function h($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }

$host = strtolower((string)($_SERVER['HTTP_HOST'] ?? ''));
if (!preg_match('/^[a-z0-9.-]+(:\d{1,5})?$/', $host)) $host = '';
$dir = str_replace('\\', '/', dirname((string)($_SERVER['SCRIPT_NAME'] ?? '/check.php')));
$dir = rtrim($dir, '/') . '/';
$host_only = preg_replace('/:\d+$/', '', $host);

// ---------- 1. server ----------
$S = 'Server';
$soft = preg_split('#[ /]#', (string)($_SERVER['SERVER_SOFTWARE'] ?? ''))[0] ?: 'web server';
row($S, version_compare(PHP_VERSION, '7.1', '>=') ? 'ok' : 'bad', 'PHP ' . PHP_VERSION . ' on ' . $soft,
    version_compare(PHP_VERSION, '7.1', '>=') ? '' : 'PHP 7.1 or newer is needed.');
if (version_compare(PHP_VERSION, '7.1', '<')) fix('php', 'hPanel ▸ Advanced ▸ PHP Configuration: choose PHP 8.x for this website.');
$has_mysql = extension_loaded('pdo_mysql');
row($S, $has_mysql ? 'ok' : 'bad', 'MySQL for PHP (pdo_mysql)', $has_mysql ? '' : 'Not switched on.');
if (!$has_mysql) fix('pdo', 'hPanel ▸ Advanced ▸ PHP Configuration ▸ PHP extensions: tick pdo_mysql ▸ Save.');

// ---------- 2. files ----------
$S = 'Files';
$need = ['van_api.php' => 'the relay', 'api.php' => 'old address of the relay', 'van_db.php' => 'database part',
         'index.html' => 'the van app', 'app.js' => 'the van app', 'config.js' => 'van app settings',
         '.htaccess' => 'site rules', 'data/.htaccess' => 'protects the data folder'];
$missing = [];
foreach ($need as $f => $what) if (!is_file(__DIR__ . '/' . $f)) $missing[] = "$f ($what)";
row($S, $missing ? 'bad' : 'ok', $missing ? 'Missing: ' . implode(', ', $missing) : 'All relay and van-app files are here');
if ($missing) fix('files', 'Upload ALL files of the DayBill 5.23.2 relay into this folder (also .htaccess and the data folder — in File Manager turn on "show hidden files").');
$cfgjs = @file_get_contents(__DIR__ . '/config.js') ?: '';
if ($cfgjs && strpos($cfgjs, 'van_api.php') === false) {
    row($S, 'warn', 'config.js is the old one (talks to api.php)', 'Works, but upload the new config.js.');
    fix('files', 'Upload ALL files of the DayBill 5.23.2 relay into this folder (replace the old ones).');
}

// ---------- 3. settings + database ----------
$S = 'Settings and database';
$db_ok = false;
if (!is_file(__DIR__ . '/relay_config.php')) {
    row($S, 'bad', 'relay_config.php is missing', 'It holds the database details and the shop key.');
    fix('config', 'Make relay_config.php: DayBill ▸ Mobile & Van ▸ Van (internet) ▸ “Make upload folder…” (type the MySQL details) and upload relay_config.php from that folder.');
} else {
    relay_load_config();
    $key_ok = defined('SHOP_KEY') && strlen((string)SHOP_KEY) >= 24 && strpos((string)SHOP_KEY, 'CHANGE-ME') !== 0;
    row($S, $key_ok ? 'ok' : 'bad', $key_ok ? 'relay_config.php found · shop key set' : 'relay_config.php found · shop key NOT set',
        $key_ok ? '' : 'SHOP_KEY must be the long key that DayBill made.');
    if (!$key_ok) fix('key', 'Use the relay_config.php that DayBill made (Make upload folder…) — it has the right shop key.');
    try {
        $pdo = relay_db();
        $db_ok = true;
        row($S, 'ok', 'Database opens · tables ready', defined('DB_DRIVER') && DB_DRIVER === 'sqlite' ? 'Test mode (SQLite).' : 'MySQL');
        $c = $pdo->query('SELECT version, updated_at FROM vr_catalog WHERE id=1')->fetch();
        $vans = (int)$pdo->query('SELECT COUNT(*) n FROM vr_vans WHERE active=1')->fetch()['n'];
        $wait = (int)$pdo->query("SELECT COUNT(*) n FROM vr_docs WHERE status='new'")->fetch()['n'];
        if ($c) row($S, 'ok', 'DayBill has synced — product list from ' . $c['updated_at'] . ' (UTC)');
        else {
            row($S, 'warn', 'DayBill has not synced yet', 'No product list here yet.');
            fix('sync', 'DayBill ▸ Mobile & Van ▸ Van (internet): type this address ▸ Test connection ▸ Sync now.');
        }
        row($S, $vans ? 'ok' : 'warn', $vans . ' van(s) can sign in', $vans ? '' : 'Tick 🚚 Van for the driver in DayBill (Users & modules), give a van code + PIN ▸ Save ▸ Sync now.');
        row($S, 'info', $wait . ' van bill(s) waiting for DayBill');
    } catch (RelayError $e) {
        row($S, 'bad', 'Database: ' . $e->getMessage());
        fix('db', 'hPanel ▸ Databases ▸ MySQL: check the database name, user and password; then make relay_config.php again in DayBill (Make upload folder…) with the right details.');
    } catch (Throwable $e) {
        row($S, 'bad', 'Database error', get_class($e));
        fix('db', 'hPanel ▸ Databases ▸ MySQL: check the database; then make relay_config.php again in DayBill.');
    }
}

// ---------- 4. https and http, tested from the server itself ----------
$S = 'https and http (tested from your server, like DayBill does)';
$cache_marks = ['x-origin-cache-status', 'x-cdn-cache-status', 'x-litespeed-cache', 'x-cache', 'x-proxy-cache', 'cf-cache-status', 'x-hcdn-cache-status'];
function probe($url) {
    $o = ['code' => 0, 'loc' => '', 'err' => '', 'errno' => 0, 'relay' => false, 'hdr' => []];
    $head = ''; $body = '';
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_HEADER => true, CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_TIMEOUT => 10, CURLOPT_CONNECTTIMEOUT => 6, CURLOPT_USERAGENT => 'DayBill-Relay-Check',
            CURLOPT_HTTPHEADER => ['Cache-Control: no-cache', 'Pragma: no-cache']]);
        $raw = curl_exec($ch);
        if ($raw === false) { $o['err'] = curl_error($ch); $o['errno'] = curl_errno($ch); return $o; }
        $hs = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
        $o['code'] = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $head = substr($raw, 0, $hs); $body = substr($raw, $hs);
    } elseif (ini_get('allow_url_fopen')) {
        $ctx = stream_context_create(['http' => ['method' => 'GET', 'follow_location' => 0, 'ignore_errors' => true,
            'timeout' => 10, 'header' => "Cache-Control: no-cache\r\nUser-Agent: DayBill-Relay-Check\r\n"]]);
        $body = @file_get_contents($url, false, $ctx);
        $hl = function_exists('http_get_last_response_headers') ? (http_get_last_response_headers() ?: []) : ($http_response_header ?? []);
        if ($body === false && !$hl) { $e = error_get_last(); $o['err'] = $e ? $e['message'] : 'no answer'; $o['errno'] = -1; return $o; }
        if ($hl && preg_match('#^HTTP/\S+\s+(\d+)#', $hl[0], $m)) $o['code'] = (int)$m[1];
        $head = implode("\n", $hl);
    } else {
        $o['err'] = 'this server cannot test itself (no curl)'; $o['errno'] = -2; return $o;
    }
    foreach (preg_split("/\r?\n/", $head) as $l) {
        $p = strpos($l, ':');
        if ($p) $o['hdr'][strtolower(trim(substr($l, 0, $p)))] = trim(substr($l, $p + 1));
    }
    $o['loc'] = $o['hdr']['location'] ?? '';
    $j = json_decode((string)$body, true);
    $o['relay'] = is_array($j) && ($j['app'] ?? '') === 'DayBill Van Relay';
    return $o;
}
function abs_url($base, $loc) {
    if ($loc === '' || preg_match('#^https?://#i', $loc)) return $loc;
    $p = parse_url($base);
    $root = $p['scheme'] . '://' . $p['host'] . (isset($p['port']) ? ':' . $p['port'] : '');
    if ($loc[0] === '/') return $root . $loc;
    return preg_replace('#[^/]*$#', '', $base) . $loc;
}
function strip_t($u) { return preg_replace('/([?&])_=\d+&?/', '$1', rtrim($u, '?&')); }
$cached = function ($hdr) use ($cache_marks) {
    foreach ($cache_marks as $k) if (isset($hdr[$k]) && stripos($hdr[$k], 'hit') !== false) return $k . ': ' . $hdr[$k];
    return '';
};
$https_state = 'unknown';
$loop_cached = false;
if ($host) {
    $t = (string)round(microtime(true) * 1000);
    foreach (['https', 'http'] as $sch) {
        $url = $sch . '://' . $host . $dir . 'van_api.php?a=ping&_=' . $t;
        $nice = $sch . '://' . $host . $dir;
        $p = probe($url);
        $hit = $cached($p['hdr']);
        if ($p['errno']) {
            $ssl = in_array($p['errno'], [35, 51, 53, 54, 58, 59, 60, 64, 66, 77, 80, 82, 83, 90, 91], true)
                   || stripos($p['err'], 'ssl') !== false || stripos($p['err'], 'certificate') !== false;
            if ($p['errno'] === -2) { row($S, 'info', $nice . ' — ' . $p['err']); continue; }
            row($S, $sch === 'https' ? 'bad' : 'warn', $nice . ' — ' . ($ssl ? 'SSL certificate problem' : 'no answer'), $p['err']);
            if ($sch === 'https') {
                $https_state = $ssl ? 'ssl' : 'down';
                fix('ssl', 'hPanel ▸ Websites ▸ your site ▸ Security ▸ SSL: the line for ' . $host_only . ' must say “Active”. If not, press Install SSL for ' . $host_only . ' (free) and wait 10–30 minutes.');
            }
            continue;
        }
        $to = abs_url($url, $p['loc']);
        if ($p['relay'] && $p['code'] === 200) {
            row($S, 'ok', $nice . ' works ✔', 'The relay answers.');
            if ($sch === 'https') $https_state = 'ok';
        } elseif ($p['code'] >= 300 && $p['code'] < 400 && strip_t($to) === strip_t($url)) {
            row($S, 'bad', $nice . ' — redirects to ITSELF (' . $p['code'] . ') → endless loop',
                $hit ? 'This is an OLD saved answer (' . $hit . ').' : 'Something in front of this folder sends it back to the same address.');
            if ($sch === 'https') $https_state = 'loop';
            if ($hit) {
                $loop_cached = true;
                fix('cache', 'Clear Hostinger\'s saved answers: hPanel ▸ Websites ▸ your site ▸ Performance ▸ CDN ▸ Flush cache (or turn the CDN off for this site — the van relay does not need it) AND Advanced ▸ Cache Manager ▸ Purge All. Wait 2 minutes, then press F5 on this page.');
            }
            fix('force', 'hPanel ▸ Security ▸ SSL: turn “Force HTTPS” OFF for ' . $host_only . ' (DayBill and the van app already use the https address — no forcing needed). Remove any https redirect lines from the .htaccess files listed below.');
        } elseif ($p['code'] >= 300 && $p['code'] < 400) {
            $good = $sch === 'http' && stripos($to, 'https://') === 0;
            row($S, $good ? 'info' : 'warn', $nice . ' — sends visitors to ' . strip_t($to), $hit ? '(' . $hit . ')' : '');
        } else {
            row($S, 'bad', $nice . ' — answers ' . $p['code'] . ' but not as the relay', $hit ? '(' . $hit . ')' : 'Another page answers at this address.');
            if ($sch === 'https') $https_state = 'other';
        }
    }
    // the old addresses (DayBill 5.23.0 / 5.23.1): a saved loop there no longer matters
    if ($https_state === 'ok') {
        foreach (['api.php?a=ping' => 'old relay address', '' => 'old phone address'] as $path => $what) {
            $u = 'https://' . $host . $dir . $path;
            $p = probe($u);
            $to = abs_url($u, $p['loc']);
            if ($p['code'] >= 300 && $p['code'] < 400 && strip_t($to) === strip_t($u)) {
                $hit = $cached($p['hdr']);
                row($S, 'info', $u . ' (' . $what . ') still has an old saved loop answer' . ($hit ? ' (' . $hit . ')' : ''),
                    'Not a problem: DayBill 5.23.2 uses van_api.php and the vans open ' . 'https://' . $host . $dir . 'van.html. It clears by itself (or hPanel ▸ CDN ▸ Flush cache).');
            }
        }
    }
    $fwd = (string)($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '');
    $raw_https = !empty($_SERVER['HTTPS']) && strtolower((string)$_SERVER['HTTPS']) !== 'off';
    if (relay_is_https() && !$raw_https)
        row($S, 'info', 'Your site sits behind a proxy / CDN: PHP sees http, the visitor uses https (X-Forwarded-Proto: ' . h($fwd ?: '?') . ').',
            'So never use a “RewriteCond %{HTTPS} off” rule in .htaccess here — it loops for ever.');
} else {
    row($S, 'info', 'Could not read the site address');
}

// ---------- 5. .htaccess rules (this folder and the folders above it) ----------
$S = '.htaccess rules';
function scan_ht($file) {
    $o = ['exists' => false, 'engine' => false, 'rules' => []];
    if (!@is_file($file) || !@is_readable($file)) return $o;
    $o['exists'] = true;
    foreach ((@file($file) ?: []) as $i => $l) {
        $t = trim($l);
        if ($t === '' || $t[0] === '#') continue;
        if (preg_match('/^RewriteEngine\s+on\b/i', $t)) $o['engine'] = true;
        if (preg_match('/%\{HTTPS\}|%\{SERVER_PORT\}|X-Forwarded-Proto|^Redirect(Match|Permanent)?\s.*https:|^RewriteRule\s.*https:/i', $t))
            $o['rules'][] = 'line ' . ($i + 1) . ': ' . substr($t, 0, 140);
    }
    return $o;
}
$me = scan_ht(__DIR__ . '/.htaccess');
if (!$me['exists']) {
    row($S, 'bad', 'This folder has no .htaccess', 'Upload the .htaccess of the 5.23.2 relay (File Manager ▸ show hidden files).');
    fix('files', 'Upload ALL files of the DayBill 5.23.2 relay into this folder (also .htaccess — in File Manager turn on "show hidden files").');
} elseif ($me['rules']) {
    row($S, 'bad', 'This folder\'s .htaccess has an https redirect rule (it loops on Hostinger)', implode("\n", $me['rules']));
    fix('ht', 'Replace .htaccess in this folder with the one from DayBill 5.23.2 (it has no redirect rule).');
} else {
    row($S, $me['engine'] ? 'ok' : 'warn', $me['engine'] ? 'This folder\'s .htaccess is the new one (no redirect, shields this folder)' : 'This folder\'s .htaccess is old',
        $me['engine'] ? '' : 'Upload the 5.23.2 .htaccess — it stops the main site\'s rules from reaching this folder.');
    if (!$me['engine']) fix('ht', 'Replace .htaccess in this folder with the one from DayBill 5.23.2.');
}
$d = __DIR__;
for ($up = 1; $up <= 4; $up++) {
    $p = dirname($d);
    if ($p === $d) break;
    $d = $p;
    $o = scan_ht($d . '/.htaccess');
    if (!$o['exists'] || !$o['rules']) continue;
    $where = $up . ' folder' . ($up > 1 ? 's' : '') . ' up' . (basename($d) === 'public_html' ? ' (public_html — your main site)' : '');
    if ($me['engine'] && !$me['rules'])
        row($S, 'info', 'The .htaccess ' . $where . ' has an https redirect rule — this folder\'s .htaccess stops it ✔', implode("\n", $o['rules']));
    else {
        row($S, 'warn', 'The .htaccess ' . $where . ' has an https redirect rule that also hits this folder', implode("\n", $o['rules']));
        fix('ht', 'Replace .htaccess in this folder with the one from DayBill 5.23.2 — it stops the main site\'s https rule from reaching the relay.');
    }
}

// ---------- the order to fix things ----------
$order = ['ssl', 'cache', 'force', 'files', 'ht', 'php', 'pdo', 'config', 'key', 'db', 'sync'];
$todo = [];
foreach ($order as $k) if (isset($FIX[$k])) $todo[] = $FIX[$k];
$bad = 0; $warn = 0;
foreach ($ROWS as $rs) foreach ($rs as $r) { if ($r[0] === 'bad') $bad++; if ($r[0] === 'warn') $warn++; }
$addr_https = 'https://' . ($host ?: 'your-address') . $dir;
$addr_http = 'http://' . ($host ?: 'your-address') . $dir;
?><!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>DayBill Relay Check</title>
<style>
:root{--bg:#f4f6fb;--card:#fff;--ink:#1f2937;--mute:#6b7280;--line:#e5e7eb;--ok:#15803d;--okb:#dcfce7;--warn:#b45309;--warnb:#fef3c7;--bad:#b91c1c;--badb:#fee2e2;--info:#1d4ed8;--infob:#dbeafe;--pri:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#111827;--ink:#e5e7eb;--mute:#9ca3af;--line:#1f2937;--okb:#052e16;--warnb:#3b2a05;--badb:#3f0d0d;--infob:#0b1f4a;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171;--info:#93c5fd}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:6px 0 2px}.sub{color:var(--mute);font-size:13px;margin-bottom:14px;word-break:break-all}
.sum{border-radius:12px;padding:14px 16px;margin-bottom:14px;font-weight:600}
.sum.ok{background:var(--okb);color:var(--ok)}.sum.bad{background:var(--badb);color:var(--bad)}.sum.warn{background:var(--warnb);color:var(--warn)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-bottom:12px}
.card h2{font-size:15px;margin:2px 0 8px;color:var(--mute);font-weight:600}
.r{display:flex;gap:10px;padding:7px 0;border-top:1px solid var(--line)}.r:first-of-type{border-top:0}
.b{flex:0 0 auto;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:700}
.b.ok{background:var(--okb);color:var(--ok)}.b.warn{background:var(--warnb);color:var(--warn)}.b.bad{background:var(--badb);color:var(--bad)}.b.info{background:var(--infob);color:var(--info)}
.t{min-width:0}.t b{font-weight:600;word-break:break-word}.d{color:var(--mute);font-size:13px;white-space:pre-wrap;word-break:break-word}
ol{margin:4px 0 4px 20px;padding:0}ol li{margin:6px 0}
code{background:var(--bg);padding:1px 5px;border-radius:5px;font-size:13px;overflow-wrap:anywhere}
.foot{color:var(--mute);font-size:12px;margin:14px 0 30px}
</style></head><body><div class="wrap">
<h1>DayBill Van Relay — check</h1>
<div class="sub">Relay <?= h(RELAY_VERSION) ?> · <?= h($addr_https) ?> · <?= h(gmdate('Y-m-d H:i')) ?> UTC</div>
<?php if ($bad): ?><div class="sum bad">✖ <?= $bad ?> problem<?= $bad > 1 ? 's' : '' ?> found — see “What to do” below.</div>
<?php elseif ($warn): ?><div class="sum warn">⚠ Works, with <?= $warn ?> thing<?= $warn > 1 ? 's' : '' ?> to look at.</div>
<?php else: ?><div class="sum ok">✔ Everything is fine on the server.</div><?php endif; ?>

<?php if ($todo): ?><div class="card"><h2>What to do (in this order)</h2><ol>
<?php foreach ($todo as $t): ?><li><?= h($t) ?></li><?php endforeach; ?>
<li>Then press F5 on this page. When all is green: DayBill ▸ Mobile &amp; Van ▸ Van (internet) ▸ address <code><?= h($addr_https) ?></code> ▸ Test connection ▸ Sync now.</li>
</ol></div>
<?php else: ?><div class="card"><h2>Next</h2>DayBill ▸ Mobile &amp; Van ▸ Van (internet) ▸ address <code><?= h($https_state === 'ok' ? $addr_https : $addr_http) ?></code> ▸ Test connection ▸ Sync now.</div><?php endif; ?>

<?php foreach ($ROWS as $sec => $rs): ?><div class="card"><h2><?= h($sec) ?></h2>
<?php foreach ($rs as [$st, $title, $detail]): ?><div class="r"><span class="b <?= $st ?>"><?= ['ok' => '✔', 'warn' => '!', 'bad' => '✖', 'info' => 'i'][$st] ?></span><div class="t"><b><?= h($title) ?></b><?php if ($detail !== ''): ?><div class="d"><?= h($detail) ?></div><?php endif; ?></div></div>
<?php endforeach; ?></div>
<?php endforeach; ?>
<div class="card" id="br"><h2>From this browser</h2><div class="r"><span class="b info">…</span><div class="t"><b>Testing…</b></div></div></div>
<div class="foot">This page shows no passwords and no shop key. You may keep it on the site or delete check.php after the van works.</div>
</div>
<script>
(async () => {
  const box = document.getElementById("br"), rows = [];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const paint = () => { box.innerHTML = "<h2>From this browser</h2>" + rows.map(([s, t, d]) =>
    `<div class="r"><span class="b ${s}">${{ok: "✔", warn: "!", bad: "✖", info: "i"}[s]}</span><div class="t"><b>${esc(t)}</b>${d ? `<div class="d">${esc(d)}</div>` : ""}</div></div>`).join(""); };
  const add = (s, t, d) => { rows.push([s, t, d || ""]); paint(); };
  const base = location.href.split("#")[0].replace(/check\.php.*$/, "");
  const page = location.protocol.replace(":", "");
  async function ping(b) {
    try {
      const r = await fetch(b + "van_api.php?a=ping&_=" + Date.now(), { cache: "no-store" });
      let j = {}; try { j = await r.json(); } catch (e) {}
      return { ok: j.app === "DayBill Van Relay", status: r.status, j, r };
    } catch (e) { return { ok: false, err: e.message || "no answer" }; }
  }
  add(page === "https" ? "ok" : "warn", "This page is open with " + page + "://",
      page === "https" ? "" : "Vans need https: the app opens with no signal only on https.");
  const me = await ping(base);
  if (me.ok) {
    add(me.j.problem ? "warn" : "ok", "The relay answers here (" + page + ")", me.j.problem ? "⚠ " + me.j.problem : "");
    const hs = ["x-origin-cache-status", "x-cdn-cache-status", "x-litespeed-cache", "x-cache", "cf-cache-status", "x-via", "via"]
      .map(k => [k, me.r.headers.get(k)]).filter(x => x[1]);
    if (hs.length) add("info", "Cache / CDN in front of the site", hs.map(x => x[0] + ": " + x[1]).join("  ·  "));
  } else add("bad", "The relay does not answer here", me.err || ("HTTP " + me.status));
  if (page === "http") {
    const s = await ping(base.replace(/^http:/, "https:"));
    if (s.ok) add("ok", "https works too ✔ — use " + base.replace(/^http:/, "https:"));
    else add("bad", "https:// does not work from this browser",
             "Redirect loop or SSL certificate problem. Do the steps in “What to do”, then press F5.");
  }
  for (const [f, what] of [["relay_config.php", "settings file"], ["data/", "data folder"]]) {
    try {
      const r = await fetch(base + f + (f.endsWith("/") ? "" : "?_=" + Date.now()), { cache: "no-store" });
      const txt = await r.text();
      if (r.status === 403 || r.status === 404) add("ok", "The " + what + " is closed to the internet");
      else if (f.endsWith(".php") && r.ok && !txt.trim()) add("warn", "The " + what + " can be opened (shows nothing)", "Upload the 5.23.2 .htaccess so it is blocked.");
      else add("bad", "The " + what + " is open to the internet (" + r.status + ")", "Upload the 5.23.2 .htaccess now.");
    } catch (e) { add("info", "Could not test the " + what); }
  }
})();
</script>
</body></html>
