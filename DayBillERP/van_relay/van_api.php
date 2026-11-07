<?php
// ============================================================
// DayBill Van Relay 5.23.2 — the meeting point on your Hostinger site
// ------------------------------------------------------------
//  Van phone  ⇄  this relay (van_api.php)  ⇄  DayBill on the shop PC
//  • DayBill sends the product list, prices, customers and the van
//    users (PIN hashes) here, and collects the vans' bills.
//  • Vans sign in with van code + PIN, download the list, and send
//    bills when they have signal. A bill is never stored twice.
//  The shop PC does not need to be reachable from the internet.
//  api.php is the old name of this file (kept for older DayBill / phones).
//  Something wrong?  Open  check.php  in the same folder.
// ============================================================
require_once __DIR__ . '/van_db.php';
relay_headers('application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Authorization, Content-Type, X-Shop-Key, Cache-Control, Pragma');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') { http_response_code(204); exit; }

function out($data, $code = 200) { http_response_code($code); echo json_encode($data, JSON_UNESCAPED_UNICODE); exit; }
function fail($msg, $code = 400) { out(['error' => $msg], $code); }
function now() { return gmdate('Y-m-d H:i:s'); }
function body() {
    $raw = file_get_contents('php://input');
    if (strlen($raw) > 20000000) fail('Too big', 413);
    $j = json_decode($raw ?: '{}', true);
    return is_array($j) ? $j : [];
}
function header_val($name) {
    $k = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
    if (!empty($_SERVER[$k])) return $_SERVER[$k];
    if ($name === 'Authorization' && !empty($_SERVER['REDIRECT_HTTP_AUTHORIZATION'])) return $_SERVER['REDIRECT_HTTP_AUTHORIZATION'];
    if (function_exists('getallheaders')) { foreach (getallheaders() as $h => $v) if (strcasecmp($h, $name) === 0) return $v; }
    return '';
}
function shop_only() {
    $k = header_val('X-Shop-Key');
    if (!defined('SHOP_KEY') || !SHOP_KEY || strpos(SHOP_KEY, 'CHANGE-ME') === 0) fail('Set SHOP_KEY in relay_config.php', 500);
    if (!hash_equals(SHOP_KEY, (string)$k)) fail('Wrong shop key', 401);
}
function van_user($pdo) {
    $tok = trim(str_ireplace('Bearer', '', header_val('Authorization')));
    if (!$tok) fail('Please sign in again', 401);
    $st = $pdo->prepare('SELECT t.van_code, v.name, v.active FROM vr_tokens t JOIN vr_vans v ON v.van_code=t.van_code WHERE t.token=?');
    $st->execute([$tok]);
    $u = $st->fetch();
    if (!$u || !$u['active']) fail('Please sign in again', 401);
    $pdo->prepare('UPDATE vr_tokens SET last_seen=? WHERE token=?')->execute([now(), $tok]);
    return $u;
}
function catalog_row($pdo) {
    $r = $pdo->query('SELECT version, body FROM vr_catalog WHERE id=1')->fetch();
    return $r ? $r : null;
}

$a = (string)($_GET['a'] ?? '');
try {
    // ---------- open: answers even when the database is not ready ----------
    if ($a === 'ping' || $a === '') {
        $o = ['ok' => true, 'app' => 'DayBill Van Relay', 'v' => RELAY_VERSION, 'shop' => '', 'shop_ar' => '',
              'catalog' => null, 'https' => relay_is_https()];
        try {
            $c = catalog_row(relay_db());
            if ($c) {
                $co = json_decode($c['body'], true)['company'] ?? [];
                $o['shop'] = $co['company_name_en'] ?? '';
                $o['shop_ar'] = $co['company_name_ar'] ?? '';
                $o['catalog'] = $c['version'];
            }
        } catch (RelayError $e) { $o['problem'] = $e->getMessage(); }
        out($o);
    }
    $pdo = relay_db();
    switch ($a) {

    // ---------- van phone ----------
    case 'login':
        $b = body();
        $code = strtoupper(trim($b['van_code'] ?? ''));
        $since = time() - 600;
        $st = $pdo->prepare('SELECT COUNT(*) n FROM vr_fails WHERE van_code=? AND at>?');
        $st->execute([$code, $since]);
        if ((int)$st->fetch()['n'] >= 8) fail('Too many wrong PINs — wait 10 minutes.', 429);
        $st = $pdo->prepare('SELECT * FROM vr_vans WHERE van_code=? AND active=1');
        $st->execute([$code]);
        $v = $st->fetch();
        $ok = false;
        if ($v && strpos((string)$v['pin_hash'], '$') !== false) {
            [$salt, $h] = explode('$', $v['pin_hash'], 2);
            $ok = hash_equals($h, hash('sha256', $salt . (string)($b['pin'] ?? '')));
        }
        if (!$ok) {
            $pdo->prepare('INSERT INTO vr_fails (van_code, at) VALUES (?,?)')->execute([$code, time()]);
            fail('Wrong van code or PIN.');
        }
        $pdo->prepare('UPDATE vr_vans SET device_seq=COALESCE(device_seq,0)+1 WHERE van_code=?')->execute([$code]);
        $st = $pdo->prepare('SELECT device_seq FROM vr_vans WHERE van_code=?');
        $st->execute([$code]);
        $devno = (int)$st->fetch()['device_seq'];
        $tok = bin2hex(random_bytes(24));
        $pdo->prepare('INSERT INTO vr_tokens (token, van_code, device, created_at, last_seen) VALUES (?,?,?,?,?)')
            ->execute([$tok, $code, substr((string)($b['device'] ?? ''), 0, 120), now(), now()]);
        $c = catalog_row($pdo);
        $cat = $c ? json_decode($c['body'], true) : [];
        out(['token' => $tok, 'user' => $v['name'] ?: $code, 'user_id' => (int)$v['user_id'], 'van_code' => $code, 'device_no' => $devno,
             'modules' => ['van'], 'module_list' => [['key' => 'van', 'en' => 'Van Sales', 'ar' => 'مبيعات السيارة', 'icon' => '🚚']],
             'company' => $cat['company'] ?? new stdClass(), 'settings' => $cat['settings'] ?? new stdClass()]);

    case 'logout':
        $tok = trim(str_ireplace('Bearer', '', header_val('Authorization')));
        $pdo->prepare('DELETE FROM vr_tokens WHERE token=?')->execute([$tok]);
        out(['ok' => true]);

    case 'catalog':
        van_user($pdo);
        $c = catalog_row($pdo);
        if (!$c) fail('The shop has not sent the product list yet (DayBill ▸ Mobile & Van ▸ Sync).');
        header('Content-Type: application/json; charset=utf-8');
        echo $c['body'];
        exit;

    case 'submit':
        $u = van_user($pdo);
        $b = body();
        $doc = $b['doc'] ?? $b;
        $uid = substr(trim((string)($doc['uid'] ?? '')), 0, 64);
        if (!$uid || ($doc['type'] ?? '') !== 'van_sale') fail('Bad bill');
        $st = $pdo->prepare('SELECT status, result FROM vr_docs WHERE uid=?');
        $st->execute([$uid]);
        if ($old = $st->fetch()) out(['status' => $old['status'] === 'new' ? 'sent' : $old['status'], 'result' => $old['result'] ?: 'Already received', 'duplicate' => true]);
        $pdo->prepare('INSERT INTO vr_docs (uid, van_code, device, doc, status, created_at) VALUES (?,?,?,?,?,?)')
            ->execute([$uid, $u['van_code'], substr((string)($b['device'] ?? ''), 0, 120), json_encode($doc, JSON_UNESCAPED_UNICODE), 'new', now()]);
        out(['status' => 'sent', 'result' => 'Received — goes into DayBill at the next shop sync.']);

    case 'docs':
        $u = van_user($pdo);
        $st = $pdo->prepare('SELECT uid AS doc_uid, status, result, created_at FROM vr_docs WHERE van_code=? ORDER BY id DESC LIMIT 200');
        $st->execute([$u['van_code']]);
        $rows = $st->fetchAll();
        foreach ($rows as &$r) if ($r['status'] === 'new') $r['status'] = 'sent';
        out(['items' => $rows]);

    // ---------- DayBill (shop PC) ----------
    case 'shop_ping':
        shop_only();
        $n = $pdo->query("SELECT COUNT(*) n FROM vr_docs WHERE status='new'")->fetch()['n'];
        out(['ok' => true, 'waiting' => (int)$n, 'v' => RELAY_VERSION, 'https' => relay_is_https()]);

    case 'shop_push':
        shop_only();
        $b = body();
        if (isset($b['catalog'])) {
            $body = json_encode($b['catalog'], JSON_UNESCAPED_UNICODE);
            $pdo->prepare('DELETE FROM vr_catalog WHERE id=1')->execute();
            $pdo->prepare('INSERT INTO vr_catalog (id, version, body, updated_at) VALUES (1,?,?,?)')
                ->execute([(string)($b['catalog']['version'] ?? ''), $body, now()]);
        }
        if (isset($b['vans'])) {
            $pdo->beginTransaction();
            $pdo->exec('UPDATE vr_vans SET active=0');
            foreach ($b['vans'] as $v) {
                $code = strtoupper(trim($v['van_code'] ?? ''));
                if (!$code) continue;
                $up = $pdo->prepare('UPDATE vr_vans SET name=?, pin_hash=?, user_id=?, active=1 WHERE van_code=?');
                $up->execute([(string)($v['name'] ?? $code), (string)($v['pin_hash'] ?? ''), (int)($v['user_id'] ?? 0), $code]);
                if ($up->rowCount() === 0)
                    $pdo->prepare('INSERT INTO vr_vans (van_code, name, pin_hash, user_id, active, device_seq) VALUES (?,?,?,?,1,0)')
                        ->execute([$code, (string)($v['name'] ?? $code), (string)($v['pin_hash'] ?? ''), (int)($v['user_id'] ?? 0)]);
            }
            $pdo->exec('DELETE FROM vr_tokens WHERE van_code NOT IN (SELECT van_code FROM vr_vans WHERE active=1)');
            $pdo->commit();
        }
        out(['ok' => true]);

    case 'shop_pull':
        shop_only();
        $rows = $pdo->query("SELECT uid, van_code, device, doc FROM vr_docs WHERE status='new' ORDER BY id LIMIT 200")->fetchAll();
        foreach ($rows as &$r) $r['doc'] = json_decode($r['doc'], true);
        out(['items' => $rows]);

    case 'shop_ack':
        shop_only();
        $b = body();
        $st = $pdo->prepare('UPDATE vr_docs SET status=?, result=?, done_at=? WHERE uid=?');
        foreach (($b['results'] ?? []) as $r) $st->execute([substr((string)$r['status'], 0, 20), substr((string)($r['result'] ?? ''), 0, 400), now(), (string)$r['uid']]);
        $pdo->exec("DELETE FROM vr_docs WHERE status='applied' AND done_at < '" . gmdate('Y-m-d H:i:s', time() - 90 * 86400) . "'");
        $pdo->prepare('DELETE FROM vr_fails WHERE at < ?')->execute([time() - 86400]);
        out(['ok' => true]);

    default:
        fail('Unknown action', 404);
    }
} catch (RelayError $e) {
    fail($e->getMessage(), 500);
} catch (Throwable $e) {
    fail('Relay error: ' . $e->getMessage(), 500);
}
