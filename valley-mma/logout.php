<?php
// Logs out the admin (POST) or the member (POST with who=member).

require __DIR__ . '/includes/init.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    if (post('who') === 'member') {
        unset($_SESSION['member_id']);
        redirect('me.php');
    }
    unset($_SESSION['admin_id'], $_SESSION['admin_seen']);
    session_regenerate_id(true);
}
redirect('login.php');
