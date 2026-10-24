<?php
// Staff login (employees and admin).

require __DIR__ . '/lib.php';

if (current_user()) {
    redirect('staff.php');
}

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    // Simple brute-force brake: max 5 failed attempts per 5 minutes per session.
    $fails = array_filter($_SESSION['login_fails'] ?? [], fn($t) => $t > time() - 300);
    if (count($fails) >= 5) {
        $error = 'Too many attempts. Wait a few minutes.';
    } else {
        $st = db()->prepare('SELECT id, password_hash FROM users WHERE username = ? AND active = 1');
        $st->execute([trim((string)($_POST['username'] ?? ''))]);
        $row = $st->fetch();
        if ($row && password_verify((string)($_POST['password'] ?? ''), $row['password_hash'])) {
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)$row['id'];
            unset($_SESSION['login_fails']);
            redirect('staff.php');
        }
        $fails[] = time();
        $_SESSION['login_fails'] = $fails;
        $error = 'Wrong username or password.';
    }
}

page_header('Staff login');
?>
<div class="card narrow">
  <h1>Staff login</h1>
  <?php if ($error): ?><div class="alert err"><?= h($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <label>Username<input name="username" required autofocus autocomplete="username"></label>
    <label>Password<input name="password" type="password" required autocomplete="current-password"></label>
    <button class="btn primary block">Login</button>
  </form>
</div>
<?php page_footer(); ?>
