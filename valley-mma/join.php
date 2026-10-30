<?php
// Personal join link sent on WhatsApp (join.php?t=…). The new member logs in with their phone and the
// password from the admin, fills the join form and waits for the admin to approve and activate them.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/member_form.php';

$token = get('t');
$m = preg_match('/^[a-f0-9]{32}$/', $token) ? q("SELECT * FROM members WHERE invite_token = ?", [$token])->fetch() : null;
$errors = [];
$me = member_user();
$loggedIn = $m && $me && (int)$me['id'] === (int)$m['id'];

if ($m && $_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    if (post('action') === 'login') {
        if (too_many_attempts()) {
            $errors[] = t('too_many');
        } elseif ($m['password_hash'] && password_verify((string)($_POST['password'] ?? ''), $m['password_hash'])) {
            session_regenerate_id(true);
            $_SESSION['member_id'] = (int)$m['id'];
            redirect('join.php?t=' . $token);
        } else {
            failed_attempt();
            $errors[] = t('member_login_wrong');
        }
    } elseif (post('action') === 'details' && $loggedIn && $m['status'] === 'pending') {
        $d = $m;
        member_read_personal($d, $errors);
        if (!$d['declaration']) {
            $errors[] = t('err_declaration');
        }
        if (post('rules_ok') !== '1') {
            $errors[] = t('err_rules');
        }
        if (!$errors) {
            member_save_photo($d, (string)$m['photo'], $errors);
        }
        if (!$errors) {
            $cols = member_personal_cols();
            $vals = array_map(fn($c) => $c === 'dob' && ($d[$c] ?? '') === '' ? null : ($d[$c] ?? null), $cols);
            $vals[] = $m['id'];
            q('UPDATE members SET ' . implode(', ', array_map(fn($c) => "$c = ?", $cols)) . ', details_at = NOW(), rules_accepted_at = NOW() WHERE id = ?', $vals);
            redirect('join.php?t=' . $token . '&sent=1');
        }
        $m = $d;
    }
}

$title = t('join_title');
$bare = true;
$memberApp = true;
require __DIR__ . '/includes/header.php';
?>
<div class="pt-3"><?= brand_html('', 'mb-3') ?></div>

<?php if (!$m || $m['status'] !== 'pending'): ?>
  <div class="card"><div class="card-body text-center p-4">
    <div class="checkin-big text-<?= $m ? 'success' : 'danger' ?> mb-2"><i class="bi <?= $m ? 'bi-check-circle-fill' : 'bi-x-circle-fill' ?>"></i></div>
    <p class="fs-5"><?= e($m ? t('join_already_active') : t('join_link_invalid')) ?></p>
    <a href="me.php" class="btn btn-primary btn-lg w-100"><i class="bi bi-person-circle"></i> <?= e(t('member_login')) ?></a>
  </div></div>

<?php elseif (!$loggedIn): ?>
  <div class="card"><div class="card-body p-4">
    <h1 class="h5 mb-1"><i class="bi bi-person-plus-fill text-primary"></i> <?= e(t('join_title')) ?></h1>
    <p class="small-muted"><?= e(t('join_login_help')) ?></p>
    <?php if ($errors): ?><div class="alert alert-danger py-2"><?= implode('<br>', array_map('e', $errors)) ?></div><?php endif; ?>
    <form method="post">
      <?= csrf_field() ?><input type="hidden" name="action" value="login">
      <div class="mb-3"><label class="form-label"><?= e(t('phone_no')) ?></label>
        <input class="form-control form-control-lg" value="<?= e($m['phone']) ?>" readonly></div>
      <div class="mb-4"><label class="form-label" for="pw"><?= e(t('password')) ?></label>
        <input class="form-control form-control-lg" id="pw" name="password" type="password" inputmode="numeric" autocomplete="current-password" required autofocus></div>
      <button class="btn btn-primary btn-lg w-100"><i class="bi bi-box-arrow-in-right"></i> <?= e(t('continue')) ?></button>
    </form>
  </div></div>
  <div class="text-center mt-3"><a href="lang.php?l=en" class="btn btn-sm btn-light">English</a> <a href="lang.php?l=ml" class="btn btn-sm btn-light">മലയാളം</a></div>

<?php elseif ($m['details_at'] && get('edit') !== '1'): ?>
  <div class="card"><div class="card-body text-center p-4">
    <div class="checkin-big text-primary mb-2"><i class="bi bi-hourglass-split"></i></div>
    <h1 class="h5"><?= e(get('sent') === '1' ? t('join_sent') : t('join_waiting')) ?></h1>
    <p><?= e(t('join_waiting_help')) ?></p>
    <p class="small-muted mb-3"><?= e(setting('phone1')) ?> · <?= e(setting('phone2')) ?></p>
    <a href="join.php?t=<?= e($token) ?>&edit=1" class="btn btn-outline-primary w-100 mb-2"><i class="bi bi-pencil"></i> <?= e(t('join_edit')) ?></a>
    <a href="me.php" class="btn btn-light w-100"><?= e(t('my_account')) ?></a>
  </div></div>

<?php else: ?>
  <h1 class="h5"><?= e(t('join_fill', $m['name'] !== $m['phone'] ? ' ' . $m['name'] : '')) ?></h1>
  <p class="small-muted"><?= e(t('join_fill_help')) ?></p>
  <?php if ($errors): ?><div class="alert alert-danger"><?= implode('<br>', array_map('e', array_unique($errors))) ?></div><?php endif; ?>
  <form method="post" enctype="multipart/form-data" id="joinForm">
    <?= csrf_field() ?><input type="hidden" name="action" value="details">
    <div class="card mb-3"><div class="card-body d-flex align-items-center gap-3">
      <?php member_photo_html($m); ?>
      <div class="small-muted"><?= e(t('join_photo_help')) ?></div>
    </div></div>
    <?php if ($m['name'] === $m['phone']) { $m['name'] = ''; } member_personal_html($m); ?>
    </div></div>
    <button type="button" class="btn btn-primary btn-lg w-100 mb-5" id="joinNext"><i class="bi bi-send"></i> <?= e(t('join_submit')) ?></button>

    <div class="modal fade" id="rulesModal" tabindex="-1" aria-labelledby="rulesTitle" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable"><div class="modal-content pub-modal">
        <div class="modal-header"><h2 class="modal-title h5" id="rulesTitle"><i class="bi bi-journal-check"></i> <?= e(pub('pub_rules_title')) ?></h2>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button></div>
        <div class="modal-body"><p class="small mb-2"><?= e(t('rules_read_first')) ?></p><?= rules_html() ?></div>
        <div class="modal-footer d-block">
          <div class="form-check mb-2"><input class="form-check-input" type="checkbox" name="rules_ok" value="1" id="rulesOk">
            <label class="form-check-label fw-semibold" for="rulesOk"><?= e(t('rules_agree', pub('pub_rules_title'))) ?></label></div>
          <button class="btn btn-primary btn-lg w-100" id="rulesGo" disabled><i class="bi bi-check2-circle"></i> <?= e(t('agree_and_send')) ?></button>
        </div>
      </div></div>
    </div>
  </form>
  <script>
  (function () {
    var f = document.getElementById('joinForm'), ok = document.getElementById('rulesOk'), go = document.getElementById('rulesGo');
    ok.addEventListener('change', function () { go.disabled = !ok.checked; });
    document.getElementById('joinNext').addEventListener('click', function () {
      if (!f.reportValidity()) return; // first fill the form, then read and accept the rules
      bootstrap.Modal.getOrCreateInstance(document.getElementById('rulesModal')).show();
    });
  })();
  </script>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
