<?php
// Invite a new member: admin enters phone + password, the app makes a personal link to send on WhatsApp.
// The member opens it, logs in, fills the join form; then the admin approves (payment or N active days).

require __DIR__ . '/includes/init.php';
require_admin();

$errors = [];
$dup = false;
$phone = clean_phone(post('phone'));
$name = mb_substr(post('name'), 0, 100);
$pass = (string)($_POST['password'] ?? '');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!preg_match('/^\+?\d{10,15}$/', $phone)) {
        $errors[] = t('err_phone');
    }
    if (strlen($pass) < 4) {
        $errors[] = t('err_password_short');
    }
    $digits = substr(preg_replace('/\D/', '', $phone), -10);
    $same = $digits !== '' ? q('SELECT id, name, status FROM members WHERE phone LIKE ? LIMIT 1', ['%' . $digits])->fetch() : null;
    if ($same && post('again') !== '1') {
        $errors[] = t('phone_exists', $same['name']);
        $dup = true;
    }
    if (!$errors) {
        $token = bin2hex(random_bytes(16));
        q("INSERT INTO members (adm_no, name, phone, join_date, password_hash, card_token, status, invite_token)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            [next_adm_no(), $name !== '' ? $name : $phone, $phone, today(), password_hash($pass, PASSWORD_DEFAULT), bin2hex(random_bytes(8)), $token]);
        $id = (int)db()->lastInsertId();
        // The password is shown once so it can go into the WhatsApp message.
        $_SESSION['invite_pass'][$id] = $pass;
        redirect('member_invite.php?done=' . $id);
    }
}

$done = (int)get('done');
$m = $done ? q("SELECT * FROM members WHERE id = ? AND status = 'pending'", [$done])->fetch() : null;
$shownPass = $m ? ($_SESSION['invite_pass'][$done] ?? '') : '';

$title = t('invite_member');
$active = 'add_member';
$back = 'members.php';
require __DIR__ . '/includes/header.php';
?>
<div style="max-width:620px">
<?php if ($m): $link = invite_link($m); $msg = invite_text($m, $shownPass); ?>
  <div class="card mb-3"><div class="card-body text-center p-4">
    <div class="checkin-big text-success mb-2"><i class="bi bi-person-check-fill"></i></div>
    <h2 class="h5"><?= e(t('invite_ready')) ?></h2>
    <p class="mb-1"><b><?= e($m['phone']) ?></b> · <?= e($m['adm_no']) ?></p>
    <?php if ($shownPass !== ''): ?><p class="small-muted"><?= e(t('password')) ?>: <b><?= e($shownPass) ?></b></p><?php endif; ?>
    <div class="input-group mb-3">
      <input class="form-control" id="invLink" value="<?= e($link) ?>" readonly>
      <button class="btn btn-outline-primary" type="button" data-copy="#invLink" aria-label="Copy"><i class="bi bi-copy"></i></button>
    </div>
    <a class="btn btn-whatsapp btn-lg w-100 mb-2" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], $msg)) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('send_invite_whatsapp')) ?></a>
    <div class="d-flex gap-2">
      <a href="member_view.php?id=<?= $m['id'] ?>" class="btn btn-light flex-fill"><?= e(t('open_member')) ?></a>
      <a href="member_invite.php" class="btn btn-outline-primary flex-fill"><i class="bi bi-plus-lg"></i> <?= e(t('invite_another')) ?></a>
    </div>
  </div></div>
  <p class="small-muted"><i class="bi bi-info-circle"></i> <?= e(t('invite_next_steps')) ?></p>
<?php else: ?>
  <?php if ($errors): ?><div class="alert alert-danger"><?= implode('<br>', array_map('e', $errors)) ?></div><?php endif; ?>
  <p class="small-muted"><?= e(t('invite_help')) ?></p>
  <form method="post" class="card"><div class="card-body d-grid gap-3">
    <?= csrf_field() ?>
    <div><label class="form-label" for="phone"><?= e(t('phone_no')) ?> (WhatsApp) *</label>
      <input class="form-control form-control-lg" id="phone" name="phone" type="tel" inputmode="tel" required value="<?= e($phone) ?>" placeholder="98XXXXXXXX" autofocus></div>
    <div><label class="form-label" for="password"><?= e(t('password')) ?> *</label>
      <div class="input-group input-group-lg">
        <input class="form-control" id="password" name="password" type="text" required minlength="4" value="<?= e($pass !== '' ? $pass : (string)random_int(100000, 999999)) ?>" autocomplete="off">
        <button class="btn btn-outline-secondary" type="button" data-random-pass="#password" aria-label="<?= e(t('new_password')) ?>"><i class="bi bi-arrow-repeat"></i></button>
      </div>
      <div class="small-muted mt-1"><?= e(t('invite_pass_hint')) ?></div></div>
    <div><label class="form-label" for="name"><?= e(t('name')) ?> <span class="small-muted">(<?= e(t('optional')) ?>)</span></label>
      <input class="form-control" id="name" name="name" value="<?= e($name) ?>" maxlength="100"></div>
    <?php if ($dup): ?>
      <div class="form-check"><input class="form-check-input" type="checkbox" name="again" value="1" id="again"><label class="form-check-label" for="again"><?= e(t('invite_anyway')) ?></label></div>
    <?php endif; ?>
    <button class="btn btn-primary btn-lg"><i class="bi bi-link-45deg"></i> <?= e(t('create_invite')) ?></button>
  </div></form>
  <div class="text-center mt-3"><a href="member_edit.php" class="small"><?= e(t('or_fill_full_form')) ?></a></div>
<?php endif; ?>
</div>
<?php require __DIR__ . '/includes/footer.php';
