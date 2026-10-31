<?php
// login.php — redirect to homepage with login modal
require_once __DIR__ . '/includes/config.php';
if (isLoggedIn()) { header('Location: ' . url('dashboard.php')); exit; }
// Redirect to index with hash to trigger login modal
header('Location: ' . url('index.php') . '?login=1');
exit;
