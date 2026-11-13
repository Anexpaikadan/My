<?php
// Trainers (admin only): a login for each trainer with a role and rights – what the trainer may do in
// the app. A trainer sees only their own page (classes and students) plus what the rights allow.

require __DIR__ . '/includes/init.php';
$me = require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    $old = $id ? q("SELECT * FROM admins WHERE id = ? AND role = 'trainer'", [$id])->fetch() : null;
    require_verify('trainers.php' . ($id ? '?edit=' . $id : '?edit=new')); // logins and rights: ask the admin password
    if (post('action') === 'delete') {
        if ($old) {
            q('UPDATE batches SET trainer_id = NULL WHERE trainer_id = ?', [$id]);
            q('UPDATE class_sessions SET trainer_id = NULL WHERE trainer_id = ?', [$id]);
            q('DELETE FROM admins WHERE id = ?', [$id]);
            flash('success', t('deleted'));
        }
        redirect('trainers.php');
    }
    $name = mb_substr(trim(post('full_name')), 0, 100);
    $user = trim(post('username'));
    $pass = (string)($_POST['password'] ?? '');
    $rights = implode(',', array_intersect(array_keys(TRAINER_RIGHTS), (array)($_POST['rights'] ?? [])));
    $err = '';
    if ($name === '') {
        $err = t('level_name_needed');
    } elseif (!preg_match('/^[A-Za-z0-9_.-]{3,50}$/', $user)) {
        $err = t('err_username');
    } elseif (q('SELECT COUNT(*) FROM admins WHERE username = ? AND id <> ?', [$user, $id])->fetchColumn()) {
        $err = t('err_username_taken');
    } elseif ((!$old || $pass !== '') && strlen($pass) < 6) {
        $err = t('err_admin_password');
    }
    if ($err !== '') {
        flash('danger', $err);
        redirect('trainers.php?edit=' . ($id ?: 'new'));
    }
    $phone = clean_phone(post('phone'));
    $about = mb_substr(trim(post('about')), 0, 300);
    $active = post('active') === '1' ? 1 : 0;
    if ($old) {
        q('UPDATE admins SET full_name = ?, username = ?, phone = ?, about = ?, rights = ?, active = ? WHERE id = ?', [$name, $user, $phone, $about, $rights, $active, $id]);
        if ($pass !== '') {
            q('UPDATE admins SET password_hash = ? WHERE id = ?', [password_hash($pass, PASSWORD_DEFAULT), $id]);
        }
    } else {
        q("INSERT INTO admins (username, full_name, password_hash, role, phone, about, rights, active) VALUES (?, ?, ?, 'trainer', ?, ?, ?, ?)",
            [$user, $name, password_hash($pass, PASSWORD_DEFAULT), $phone, $about, $rights, $active]);
        $id = (int)db()->lastInsertId();
    }
    // batches this trainer takes
    $mine = array_map('intval', (array)($_POST['batches'] ?? []));
    q('UPDATE batches SET trainer_id = NULL WHERE trainer_id = ?', [$id]);
    foreach ($mine as $bid) {
        q('UPDATE batches SET trainer_id = ?, trainer = ? WHERE id = ?', [$id, $name, $bid]);
    }
    if ($pass !== '') {
        $_SESSION['trainer_pass'][$id] = $pass; // shown once, for the WhatsApp message
    }
    flash('success', t('trainer_saved', $name));
    redirect('trainers.php?done=' . $id);
}

$list = trainers(true);
$editKey = get('edit');
$edit = $editKey === 'new' ? ['id' => 0, 'full_name' => '', 'username' => '', 'phone' => '', 'about' => '', 'rights' => 'attendance,contact', 'active' => 1]
    : ($editKey !== '' ? q("SELECT * FROM admins WHERE id = ? AND role = 'trainer'", [(int)$editKey])->fetch() : null);
$done = (int)get('done');
$classCounts = q('SELECT trainer_id, COUNT(*) FROM class_sessions WHERE class_date BETWEEN ? AND ? AND status = \'on\' GROUP BY trainer_id', [date('Y-m-01'), date('Y-m-t')])->fetchAll(PDO::FETCH_KEY_PAIR);
$batchesBy = [];
foreach (batches(true) as $b) {
    if ($b['trainer_id']) {
        $batchesBy[(int)$b['trainer_id']][] = $b['name'];
    }
}

$title = t('trainers');
$active = 'trainers';
$back = $edit ? 'trainers.php' : 'more.php';
$actions = $edit ? '' : '<a href="?edit=new" class="btn btn-primary"><i class="bi bi-plus-lg"></i> ' . e(t('add_trainer')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<?php if ($edit): $has = explode(',', (string)$edit['rights']); ?>
<form method="post" class="card mb-3" style="max-width:720px" data-verify="<?= e(t('verify_admin')) ?>"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
  <div class="card-header fw-bold"><i class="bi bi-person-badge-fill text-primary"></i> <?= e(t($edit['id'] ? 'edit_trainer' : 'add_trainer')) ?></div>
  <div class="card-body row g-3">
    <div class="col-md-6"><label class="form-label small" for="tn"><?= e(t('name')) ?> *</label><input class="form-control" id="tn" name="full_name" maxlength="100" required value="<?= e($edit['full_name']) ?>"></div>
    <div class="col-md-6"><label class="form-label small" for="tp"><?= e(t('phone')) ?> (WhatsApp)</label><input class="form-control" id="tp" name="phone" inputmode="tel" value="<?= e($edit['phone']) ?>"></div>
    <div class="col-12"><label class="form-label small" for="ta"><?= e(t('trainer_about')) ?></label><input class="form-control" id="ta" name="about" maxlength="300" value="<?= e($edit['about']) ?>" placeholder="<?= e(t('trainer_about_ph')) ?>"></div>
    <div class="col-md-6"><label class="form-label small" for="tu"><?= e(t('username')) ?> *</label><input class="form-control" id="tu" name="username" maxlength="50" required pattern="[A-Za-z0-9_.\-]{3,50}" autocomplete="off" value="<?= e($edit['username']) ?>"></div>
    <div class="col-md-6"><label class="form-label small" for="tw"><?= e(t($edit['id'] ? 'new_password' : 'password')) ?><?= $edit['id'] ? '' : ' *' ?></label>
      <div class="input-group"><input class="form-control" id="tw" name="password" minlength="6" autocomplete="new-password"<?= $edit['id'] ? '' : ' required value="' . e((string)random_int(100000, 999999)) . '"' ?> placeholder="<?= e($edit['id'] ? t('leave_empty_keep') : '') ?>">
        <button class="btn btn-outline-secondary" type="button" data-random-pass="#tw" aria-label="New"><i class="bi bi-shuffle"></i></button></div></div>
    <div class="col-12">
      <label class="form-label small d-block fw-bold"><?= e(t('trainer_rights')) ?></label>
      <div class="small-muted mb-2"><?= e(t('trainer_rights_help')) ?></div>
      <?php foreach (TRAINER_RIGHTS as $r => $ic): ?>
        <div class="form-check form-switch mb-1"><input class="form-check-input" type="checkbox" role="switch" name="rights[]" value="<?= $r ?>" id="r_<?= $r ?>"<?= in_array($r, $has, true) ? ' checked' : '' ?>>
          <label class="form-check-label" for="r_<?= $r ?>"><i class="bi <?= $ic ?> text-primary"></i> <?= e(t('tr_' . $r)) ?> <span class="small-muted d-block"><?= e(t('tr_' . $r . '_help')) ?></span></label></div>
      <?php endforeach; ?>
      <div class="alert alert-light border small mt-2 mb-0"><i class="bi bi-shield-lock"></i> <?= e(t('trainer_never')) ?></div>
    </div>
    <?php if (batches(true)): ?>
    <div class="col-12"><label class="form-label small d-block fw-bold"><?= e(t('trainer_batches')) ?></label>
      <div class="d-flex flex-wrap gap-1 cat-opt">
        <?php foreach (batches(true) as $b): ?>
          <input type="checkbox" class="btn-check" name="batches[]" value="<?= $b['id'] ?>" id="tb<?= $b['id'] ?>"<?= $edit['id'] && (int)$b['trainer_id'] === (int)$edit['id'] ? ' checked' : '' ?>>
          <label class="btn btn-sm btn-outline-primary" for="tb<?= $b['id'] ?>"><?= e($b['name'] . ' · ' . time_text($b['start_time'])) ?></label>
        <?php endforeach; ?>
      </div><div class="form-text"><?= e(t('trainer_batches_help')) ?></div></div>
    <?php endif; ?>
    <div class="col-12"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="active" value="1" id="tact"<?= $edit['active'] ? ' checked' : '' ?>><label class="form-check-label" for="tact"><?= e(t('trainer_can_login')) ?></label></div></div>
    <div class="col-12 d-flex gap-2"><a href="trainers.php" class="btn btn-light"><?= e(t('cancel')) ?></a><button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
  </div>
</form>
<?php if ($edit['id']): ?>
  <form method="post" style="max-width:720px" class="text-end mb-4" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
    <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button></form>
<?php endif; ?>
<?php else: ?>
  <p class="small-muted"><?= e(t('trainers_help')) ?></p>
  <?php if (!$list): ?><div class="card card-body text-muted"><?= e(t('no_trainers')) ?></div><?php endif; ?>
  <div class="row g-2">
    <?php foreach ($list as $tr): $pw = (string)($_SESSION['trainer_pass'][$tr['id']] ?? ''); $nm = $tr['full_name'] !== '' ? $tr['full_name'] : $tr['username']; ?>
      <div class="col-md-6"><div class="card h-100<?= $done === (int)$tr['id'] ? ' border border-success' : '' ?><?= $tr['active'] ? '' : ' opacity-50' ?>"><div class="card-body">
        <div class="d-flex align-items-start gap-2 mb-2">
          <span class="req-ava big"><?= e(mb_strtoupper(mb_substr($nm, 0, 1))) ?></span>
          <div class="me-auto"><div class="fw-bold"><?= e($nm) ?></div><div class="small-muted"><i class="bi bi-person"></i> <?= e($tr['username']) ?><?= $tr['phone'] !== '' ? ' · ' . e($tr['phone']) : '' ?></div>
            <?php if ($tr['about'] !== ''): ?><div class="small-muted"><?= e($tr['about']) ?></div><?php endif; ?></div>
          <a href="?edit=<?= $tr['id'] ?>" class="btn btn-sm btn-light" aria-label="<?= e(t('edit')) ?>"><i class="bi bi-pencil"></i></a>
        </div>
        <div class="small mb-1"><i class="bi bi-clock-history text-primary"></i> <?= e(implode(', ', $batchesBy[(int)$tr['id']] ?? []) ?: t('no_batch')) ?> · <?= (int)($classCounts[$tr['id']] ?? 0) ?> <?= e(t('classes_this_month')) ?></div>
        <div class="d-flex flex-wrap gap-1 mb-2"><?php foreach (array_filter(explode(',', $tr['rights'])) as $r): if (!isset(TRAINER_RIGHTS[$r])) continue; ?><span class="badge text-bg-light border"><i class="bi <?= TRAINER_RIGHTS[$r] ?>"></i> <?= e(t('tr_' . $r)) ?></span><?php endforeach; ?>
          <?php if (!$tr['active']): ?><span class="badge bg-secondary"><?= e(t('login_off')) ?></span><?php endif; ?></div>
        <?php if ($tr['phone'] !== ''): ?>
          <a class="btn btn-sm btn-whatsapp<?= $pw !== '' ? ' pulse' : '' ?>" target="_blank" rel="noopener" href="<?= e(wa_link($tr['phone'], t('wa_trainer_login', $nm, gym_title(), base_url() . 'login.php', $tr['username'], $pw !== '' ? $pw : t('pass_from_gym')))) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('send_login')) ?></a>
        <?php endif; ?>
        <?php if ($pw !== ''): ?><span class="small-muted ms-1"><?= e(t('password')) ?>: <b><?= e($pw) ?></b></span><?php endif; ?>
      </div></div></div>
    <?php endforeach; ?>
  </div>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
