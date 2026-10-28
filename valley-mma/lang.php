<?php
// Switches the language (English / Malayalam) and goes back to the previous page.

require __DIR__ . '/includes/init.php';

$l = get('l') === 'ml' ? 'ml' : 'en';
$_SESSION['lang'] = $l;
setcookie('vmma_lang', $l, ['expires' => time() + 365 * 86400, 'path' => '/', 'samesite' => 'Lax', 'secure' => is_https()]);
$back = (string)($_SERVER['HTTP_REFERER'] ?? '');
$host = (string)($_SERVER['HTTP_HOST'] ?? '');
redirect($back !== '' && parse_url($back, PHP_URL_HOST) === parse_url('//' . $host, PHP_URL_HOST) ? $back : 'index.php');
