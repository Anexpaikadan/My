<?php
// Sends a member photo to the admin, or to the member themself.

require __DIR__ . '/includes/init.php';

$f = basename(get('f'));
$allowed = admin() !== null;
if (!$allowed && ($m = member_user())) {
    $allowed = $m['photo'] === $f;
}
$path = cfg('photo_dir') . '/' . $f;
if (!$allowed || !preg_match('/^[a-f0-9]{20}\.jpg$/', $f) || !is_file($path)) {
    http_response_code(404);
    exit;
}
header('Content-Type: image/jpeg');
header('Cache-Control: private, max-age=86400');
header('Content-Length: ' . filesize($path));
readfile($path);
