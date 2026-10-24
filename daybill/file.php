<?php
// Serves an uploaded file to logged-in staff only (preview or download).

require __DIR__ . '/lib.php';
require_login();

$st = db()->prepare('SELECT original_name, stored_name, ext FROM job_files WHERE id = ?');
$st->execute([(int)($_GET['id'] ?? 0)]);
$f = $st->fetch();
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
