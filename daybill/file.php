<?php
// Serves an uploaded file to logged-in staff of the same shop (preview or download).
// ?orig=1 gives the customer's original file when a layout made a print-ready PDF from it.

require __DIR__ . '/lib.php';
require_login();

$st = db()->prepare('SELECT f.original_name, f.stored_name, f.ext, f.orig_name, f.orig_ext, f.previews FROM job_files f
                     JOIN jobs j ON j.id = f.job_id WHERE f.id = ? AND j.shop_id = ?');
$st->execute([(int)($_GET['id'] ?? 0), shop_id()]);
$f = $st->fetch();
// ?pv=N: picture of sheet N (photo items)
if ($f && isset($_GET['pv']) && (int)$_GET['pv'] >= 0 && (int)$_GET['pv'] < (int)$f['previews'] && $f['stored_name'] !== '') {
    $f['stored_name'] .= '.p' . (int)$_GET['pv'] . '.jpg';
    $f['ext'] = 'jpg';
    $f['original_name'] = 'sheet-' . ((int)$_GET['pv'] + 1) . '.jpg';
} elseif ($f && isset($_GET['orig']) && $f['orig_name'] !== '') {
    $f['stored_name'] = $f['orig_name'];
    $f['ext'] = $f['orig_ext'];
}
$path = $f && $f['stored_name'] !== '' ? cfg('upload_dir') . '/' . $f['stored_name'] : '';
if (!$path || !is_file($path)) {
    http_response_code(404);
    exit('File not found.');
}

$types = [
    'pdf' => 'application/pdf', 'jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'png' => 'image/png',
    'txt' => 'text/plain; charset=utf-8',
];
$inline = !isset($_GET['dl']) && isset($types[$f['ext']]);
$name = str_replace(['"', "\r", "\n"], '', $f['original_name']);

header('Content-Type: ' . ($types[$f['ext']] ?? 'application/octet-stream'));
header('Content-Length: ' . filesize($path));
header('Content-Disposition: ' . ($inline ? 'inline' : 'attachment') . '; filename="' . $name
    . '"; filename*=UTF-8\'\'' . rawurlencode($f['original_name']));
header('X-Content-Type-Options: nosniff');
header('Cache-Control: private, no-store');
readfile($path);
