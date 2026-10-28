<?php
// Admin login.

require __DIR__ . '/includes/init.php';

if (admin()) {
    redirect('index.php');
}
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    if (too_many_attempts()) {
        $error = t('too_many');
    } else {
        $u = q('SELECT * FROM admins WHERE username = ?', [post('username')])->fetch();
        if ($u && password_verify((string)($_POST['password'] ?? ''), $u['password_hash'])) {
            session_regenerate_id(true);
            $_SESSION['admin_id'] = (int)$u['id'];
            $_SESSION['admin_seen'] = time();
            if (password_needs_rehash($u['password_hash'], PASSWORD_DEFAULT)) {
                q('UPDATE admins SET password_hash = ? WHERE id = ?', [password_hash($_POST['password'], PASSWORD_DEFAULT), $u['id']]);
            }
            $to = (string)($_SESSION['after_login'] ?? '');
            unset($_SESSION['after_login']);
            redirect(preg_match('#^/[^/\\\\]#', $to) ? $to : 'index.php');
        }
        failed_attempt();
        $error = t('login_wrong');
    }
}
$title = t('admin_login');
$bare = true;
require __DIR__ . '/includes/header.php';
?>
<div class="login-wrap text-center pt-4">
  <div class="logo-text dark mb-4">
    <span class="l1"><?= e(setting('gym_name', 'VALLEY MMA')) ?></span>
    <span class="l2"><?= e(setting('gym_tagline', 'FIGHT CLUB')) ?></span>
    <span class="l3"><?= e(setting('gym_place', 'PANDIKKAD')) ?></span>
  </div>
  <div class="card text-start">
    <div class="card-body p-4">
      <h1 class="h5 mb-3"><i class="bi bi-shield-lock-fill text-primary"></i> <?= e(t('admin_login')) ?></h1>
      <?php if ($error): ?><div class="alert alert-danger py-2"><?= e($error) ?></div><?php endif; ?>
      <form method="post" autocomplete="on">
        <?= csrf_field() ?>
        <div class="mb-3">
          <label class="form-label" for="u"><?= e(t('username')) ?></label>
          <input class="form-control form-control-lg" id="u" name="username" required autocomplete="username" value="<?= e(post('username')) ?>" autofocus>
        </div>
        <div class="mb-4">
          <label class="form-label" for="p"><?= e(t('password')) ?></label>
          <input class="form-control form-control-lg" id="p" type="password" name="password" required autocomplete="current-password">
        </div>
        <button class="btn btn-primary btn-lg w-100"><i class="bi bi-box-arrow-in-right"></i> <?= e(t('login')) ?></button>
      </form>
    </div>
  </div>
  <a href="me.php" class="btn btn-accent btn-lg w-100 mt-3"><i class="bi bi-person-badge"></i> <?= e(t('member_login')) ?></a>
  <div class="mt-3">
    <a href="lang.php?l=en" class="btn btn-sm btn-light">English</a>
    <a href="lang.php?l=ml" class="btn btn-sm btn-light">മലയാളം</a>
  </div>
  <img src="assets/daybill-logo.png" alt="DAYbill Solution" width="80" class="mt-4 rounded bg-white">
</div>
<?php require __DIR__ . '/includes/footer.php';
