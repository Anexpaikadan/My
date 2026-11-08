<?php
// Passkey re-check used by the pop-up in includes/footer.php
require_once __DIR__ . '/includes/config.php';
require_once __DIR__ . '/includes/lang.php';
require_once __DIR__ . '/includes/sudo.php';
header('Content-Type: application/json');
header('Cache-Control: no-store');
if (!isLoggedIn()) { echo json_encode(array('ok'=>false,'msg'=>'Please log in again.')); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { echo json_encode(array('ok'=>true,'fresh'=>sudo_fresh())); exit; }
if (!verifyCsrf()) { echo json_encode(array('ok'=>false,'msg'=>'Page expired. Reload and try again.')); exit; }
list($ok, $msg) = sudo_verify(preg_replace('/\D/', '', $_POST['passkey'] ?? ''));
echo json_encode(array('ok'=>$ok, 'msg'=>$msg));
