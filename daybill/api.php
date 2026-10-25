<?php
// API for the shop-PC print agent (print mode "agent", used on cloud hosting).
// Authenticated with the shop's agent key (Settings → Printing), sent as the X-Agent-Key header.
// The key also tells which shop the agent prints for.

define('DAYBILL_NO_SESSION', true); // the agent sends no cookies; don't create a session file per request
require __DIR__ . '/lib.php';
require_once __DIR__ . '/printer.php';

header('Content-Type: application/json');

function out(array $data, int $code = 200): void
{
    http_response_code($code);
    echo json_encode($data);
    exit;
}

$given = (string)($_SERVER['HTTP_X_AGENT_KEY'] ?? '');
$st = db()->prepare("SELECT s.shop_id, s.v FROM settings s JOIN shops sh ON sh.id = s.shop_id
                     WHERE s.k = 'agent_key' AND s.v = ? AND sh.active = 1");
$st->execute([$given]);
$row = $st->fetch();
if ($given === '' || !$row || !hash_equals((string)$row['v'], $given)) {
    out(['error' => 'Invalid agent key'], 403);
}
shop_id((int)$row['shop_id']);
if (time() - (int)setting('agent_seen', '0') > 15) {
    save_setting('agent_seen', (string)time());
}

$pdo = db();
$sid = shop_id();
$action = (string)($_GET['action'] ?? '');

// A file of this shop with the given status, or null.
function shop_file(int $fileId, string $status): ?array
{
    $st = db()->prepare('SELECT f.* FROM job_files f JOIN jobs j ON j.id = f.job_id WHERE f.id = ? AND j.shop_id = ? AND f.status = ?');
    $st->execute([$fileId, shop_id(), $status]);
    return $st->fetch() ?: null;
}

if ($action === 'next') {
    // Long polling: the request waits (up to ?wait= seconds) until staff press Print,
    // so the agent starts printing within a second instead of polling every few seconds.
    $wait = max(0, min(25, (int)($_GET['wait'] ?? 0)));
    @set_time_limit($wait + 20);
    $until = microtime(true) + $wait;
    $claim = $pdo->prepare("UPDATE job_files SET status = 'sending', queued_at = NOW() WHERE id = ? AND status = 'queued'");
    $requeue = $pdo->prepare("UPDATE job_files f JOIN jobs j ON j.id = f.job_id SET f.status = 'queued'
                              WHERE j.shop_id = ? AND f.status = 'sending' AND f.queued_at < (NOW() - INTERVAL 5 MINUTE)");
    $queued = $pdo->prepare("SELECT f.* FROM job_files f JOIN jobs j ON j.id = f.job_id
                             WHERE j.shop_id = ? AND f.status = 'queued' AND f.stored_name <> '' ORDER BY f.queued_at, f.id LIMIT 5");
    do {
        // Files the agent claimed but never reported (agent crashed) go back to the queue.
        $requeue->execute([$sid]);
        $queued->execute([$sid]);
        foreach ($queued->fetchAll() as $f) {
            $claim->execute([$f['id']]);
            if ($claim->rowCount() === 1) {
                out(['job' => [
                    'id' => (int)$f['id'], 'name' => $f['original_name'], 'ext' => $f['ext'],
                    'copies' => (int)$f['copies'], 'paper' => $f['paper'], 'color' => $f['color'], 'sides' => $f['sides'],
                    'orientation' => $f['orientation'], 'page_range' => $f['page_range'], 'printer' => printer_for($f),
                    'scale' => print_scale($f),
                ]]);
            }
        }
        if (connection_aborted()) {
            exit;
        }
        usleep(700000);
    } while (microtime(true) < $until);
    out(['job' => null]);
}

if ($action === 'file') {
    $f = shop_file((int)($_GET['id'] ?? 0), 'sending');
    $path = $f ? cfg('upload_dir') . '/' . $f['stored_name'] : '';
    if (!$f || $f['stored_name'] === '' || !is_file($path)) {
        out(['error' => 'File not found'], 404);
    }
    header('Content-Type: application/octet-stream');
    header('Content-Length: ' . filesize($path));
    readfile($path);
    exit;
}

if ($action === 'result' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $f = shop_file((int)($_POST['id'] ?? 0), 'sending');
    if ($f && ($_POST['ok'] ?? '') === '1') {
        $pdo->prepare("UPDATE job_files SET status = 'printed', print_count = print_count + 1, last_error = '', printed_at = NOW()
                       WHERE id = ?")->execute([$f['id']]);
        update_job_status((int)$f['job_id']);
    } elseif ($f) {
        $pdo->prepare("UPDATE job_files SET status = 'failed', last_error = ? WHERE id = ?")
            ->execute([mb_substr('Print agent: ' . (string)($_POST['error'] ?? 'unknown error'), 0, 500), $f['id']]);
    }
    out(['ok' => true]);
}

if ($action === 'printers' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    // Printers installed on the shop PC, offered in Admin and on the order page.
    $names = array_filter(array_map(fn($n) => mb_substr(trim(str_replace(',', ' ', (string)$n)), 0, 200),
        (array)($_POST['names'] ?? [])), 'strlen');
    save_setting('printers_detected', implode(',', array_slice(array_unique($names), 0, 50)));
    out(['ok' => true]);
}

if ($action === 'ping') {
    out(['ok' => true, 'shop' => setting('shop_name', shop()['name'] ?? 'Daybill Print')]);
}

out(['error' => 'Unknown action'], 400);
