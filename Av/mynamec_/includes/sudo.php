<?php
// ================================================================
// sudo.php — ask an admin for their login passkey again before a
// delete or a money change. Once confirmed, it stays valid for 5 minutes.
//
// Server side (in a module, before deleting / changing money):
//     require_once __DIR__ . '/../includes/sudo.php';
//     sudo_require();            // stops the request if not confirmed
// Page side: give the form or link  data-sudo  — footer.php shows the
// passkey pop-up first, then sends the form / opens the link.
// For fetch() calls:  sudoThen(function(){ ...fetch... });
// ================================================================
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/extras.php';
if (!function_exists('sudo_fresh')) {

define('SUDO_WINDOW', 300);   // seconds

function sudo_fresh() {
    return !empty($_SESSION['sudo_at']) && (time() - (int)$_SESSION['sudo_at']) < SUDO_WINDOW
        && (int)($_SESSION['sudo_uid'] ?? 0) === (int)($_SESSION['user_id'] ?? -1);
}

// Check a passkey for the logged-in user. Max 5 wrong tries per 10 minutes.
function sudo_verify($passkey) {
    if (!isLoggedIn()) return array(false, 'Please log in again.');
    $now = time();
    $tries = isset($_SESSION['sudo_fail']) ? array_filter((array)$_SESSION['sudo_fail'], function($t) use ($now){ return $t > $now - 600; }) : array();
    if (count($tries) >= 5) return array(false, 'Too many wrong tries. Wait 10 minutes.');
    $u = currentUser();
    $ok = $u && !empty($u['passkey']) && preg_match('/^\d{4,8}$/', (string)$passkey) && password_verify((string)$passkey, $u['passkey']);
    if (!$ok) { $tries[] = $now; $_SESSION['sudo_fail'] = array_values($tries); return array(false, function_exists('t') ? t('sudo_wrong') : 'Wrong passkey.'); }
    $_SESSION['sudo_fail'] = array();
    $_SESSION['sudo_at'] = $now; $_SESSION['sudo_uid'] = (int)$u['id'];
    return array(true, '');
}

// Stop the request when the passkey was not confirmed in the last 5 minutes.
function sudo_require() {
    if (sudo_fresh()) return;
    $ajax = !empty($_POST['ajax']) || !empty($_GET['ajax'])
         || (isset($_SERVER['HTTP_ACCEPT']) && strpos($_SERVER['HTTP_ACCEPT'], 'application/json') !== false)
         || (isset($_SERVER['HTTP_X_REQUESTED_WITH']));
    if ($ajax) {
        if (!headers_sent()) header('Content-Type: application/json');
        echo json_encode(array('ok'=>false, 'sudo'=>true, 'msg'=>'Please confirm your passkey and try again.'));
        exit;
    }
    http_response_code(403);
    $back = isset($_SERVER['HTTP_REFERER']) ? $_SERVER['HTTP_REFERER'] : url('dashboard.php');
    echo '<!DOCTYPE html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<title>Confirm passkey</title><body style="font-family:system-ui;padding:2rem;max-width:480px;margin:auto">'
       . '<h1 style="font-size:1.3rem">Please confirm your passkey</h1><p>For safety, deleting and money changes need your login passkey again. Go back and try once more.</p>'
       . '<p><a href="' . htmlspecialchars($back, ENT_QUOTES) . '">← Go back</a></p></body>';
    exit;
}

}
