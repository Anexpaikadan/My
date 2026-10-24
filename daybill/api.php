<?php
// API for the shop-PC print agent (print mode "agent", used on cloud hosting).
// Authenticated with the agent key shown in Admin, sent as the X-Agent-Key header.

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

$key = setting('agent_key', '');
if ($key === '' || !hash_equals($key, (string)($_SERVER['HTTP_X_AGENT_KEY'] ?? ''))) {
    out(['error' => 'Invalid agent key'], 403);
}
if (time() - (int)setting('agent_seen', '0') > 15) {
    save_setting('agent_seen', (string)time());
}

$pdo = db();
$action = (string)($_GET['action'] ?? '');

if ($action === 'next') {
    // Long polling: the request waits (up to ?wait= seconds) until staff press Print,
    // so the agent starts printing within a second instead of polling every few seconds.
    $wait = max(0, min(25, (int)($_GET['wait'] ?? 0)));
    @set_time_limit($wait + 20);
    $until = microtime(true) + $wait;
    $claim = $pdo->prepare("UPDATE job_files SET status = 'sending', queued_at = NOW() WHERE id = ? AND status = 'queued'");
    do {
        // Files the agent claimed but never reported (agent crashed) go back to the queue.
        $pdo->exec("UPDATE job_files SET status = 'queued' WHERE status = 'sending' AND queued_at < (NOW() - INTERVAL 5 MINUTE)");
        $rows = $pdo->query("SELECT * FROM job_files WHERE status = 'queued' AND stored_name <> '' ORDER BY queued_at, id LIMIT 5")->fetchAll();
        foreach ($rows as $f) {
            $claim->execute([$f['id']]);
            if ($claim->rowCount() === 1) {
                out(['job' => [
                    'id' => (int)$f['id'], 'name' => $f['original_name'], 'ext' => $f['ext'],
                    'copies' => (int)$f['copies'], 'paper' => $f['paper'], 'color' => $f['color'], 'sides' => $f['sides'],
                    'orientation' => $f['orientation'], 'page_range' => $f['page_range'], 'printer' => printer_for($f),
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
    $st = $pdo->prepare("SELECT stored_name FROM job_files WHERE id = ? AND status = 'sending'");
    $st->execute([(int)($_GET['id'] ?? 0)]);
    $name = (string)$st->fetchColumn();
    $path = cfg('upload_dir') . '/' . $name;
    if ($name === '' || !is_file($path)) {
        out(['error' => 'File not found'], 404);
    }
    header('Content-Type: application/octet-stream');
    header('Content-Length: ' . filesize($path));
    readfile($path);
    exit;
}

if ($action === 'result' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)($_POST['id'] ?? 0);
    if (($_POST['ok'] ?? '') === '1') {
        $pdo->prepare("UPDATE job_files SET status = 'printed', print_count = print_count + 1, last_error = '', printed_at = NOW()
                       WHERE id = ? AND status = 'sending'")->execute([$id]);
    } else {
        $pdo->prepare("UPDATE job_files SET status = 'failed', last_error = ? WHERE id = ? AND status = 'sending'")
            ->execute([mb_substr('Print agent: ' . (string)($_POST['error'] ?? 'unknown error'), 0, 500), $id]);
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
    out(['ok' => true, 'shop' => setting('shop_name', 'Daybill Print')]);
}

out(['error' => 'Unknown action'], 400);
