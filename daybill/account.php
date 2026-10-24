<?php
// My account: every staff member can change their own password.

require __DIR__ . '/lib.php';
$user = require_login();

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $st = db()->prepare('SELECT password_hash FROM users WHERE id = ?');
    $st->execute([$user['id']]);
    $new = (string)($_POST['new'] ?? '');
    if (!password_verify((string)($_POST['current'] ?? ''), (string)$st->fetchColumn())) {
        $error = 'Current password is wrong.';
    } elseif (strlen($new) < 6) {
        $error = 'New password must be at least 6 characters.';
    } elseif ($new !== (string)($_POST['confirm'] ?? '')) {
        $error = 'The new passwords do not match.';
    } else {
        db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')->execute([password_hash($new, PASSWORD_DEFAULT), $user['id']]);
        session_regenerate_id(true);
        flash('Password changed.');
        redirect('settings.php');
    }
}

page_header('My account', true, 'en', 'settings.php');
?>
<div class="card">
  <h2>Change password</h2>
  <?php if ($error): ?><div class="alert err"><?= h($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <label>Current password<input type="password" name="current" required autocomplete="current-password"></label>
    <label>New password<input type="password" name="new" required minlength="6" autocomplete="new-password"></label>
    <label>Repeat new password<input type="password" name="confirm" required minlength="6" autocomplete="new-password"></label>
    <button class="btn primary block">Save password</button>
  </form>
</div>
<?php page_footer(); ?>
