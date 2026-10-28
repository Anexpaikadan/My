<?php
// New member join form / edit member (same fields as the paper join form) + plan and login password.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/member_form.php';
require_admin();

$id = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
$m = $id ? q('SELECT * FROM members WHERE id = ?', [$id])->fetch() : null;
if ($id && !$m) {
    redirect('members.php');
}
$plans = q('SELECT * FROM plans WHERE active = 1 OR id = ? ORDER BY sort_order, id', [$m['plan_id'] ?? 0])->fetchAll();
$plansById = array_column($plans, null, 'id');

$text = ['trainer_name' => 100, 'notes' => 500, 'adm_no' => 20]; // admin-only fields
$errors = [];

$d = $m ?: [
    'adm_no' => next_adm_no(), 'join_date' => today(), 'start_date' => today(), 'expiry_date' => '', 'state' => 'Kerala',
    'district' => 'Malappuram', 'plan_id' => $plans[0]['id'] ?? null, 'gender' => '', 'photo' => '', 'declaration' => 0,
];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    member_read_personal($d, $errors);
    foreach ($text as $k => $max) {
        $d[$k] = mb_substr(post($k), 0, $max);
    }
    foreach (['join_date', 'start_date', 'expiry_date'] as $k) {
        $d[$k] = post($k);
        if ($d[$k] !== '' && !valid_date($d[$k])) {
            $errors[] = t('err_date');
            $d[$k] = '';
        }
    }
    $d['plan_id'] = isset($plansById[(int)post('plan_id')]) ? (int)post('plan_id') : null;

    if ($d['join_date'] === '') {
        $d['join_date'] = today();
    }
    if ($d['adm_no'] === '') {
        $d['adm_no'] = next_adm_no();
    }
    if (q('SELECT COUNT(*) FROM members WHERE adm_no = ? AND id <> ?', [$d['adm_no'], $id])->fetchColumn()) {
        $errors[] = t('err_adm_no');
    }
    // Expiry: calculated from the plan when left empty.
    if ($d['plan_id'] && $d['start_date'] !== '' && $d['expiry_date'] === '') {
        $p = $plansById[$d['plan_id']];
        $d['expiry_date'] = plan_end($d['start_date'], (int)$p['duration_value'], $p['duration_unit']);
    }
    $pass = (string)($_POST['new_password'] ?? '');
    if ($pass !== '' && strlen($pass) < 4) {
        $errors[] = t('err_password_short');
    }

    if (!$errors) {
        member_save_photo($d, (string)($m['photo'] ?? ''), $errors);
    }

    if (!$errors) {
        $cols = array_merge(member_personal_cols(), array_keys($text), ['join_date', 'start_date', 'expiry_date', 'plan_id']);
        $vals = [];
        foreach ($cols as $c) {
            $v = $d[$c] ?? null;
            $vals[] = in_array($c, ['dob', 'start_date', 'expiry_date'], true) && $v === '' ? null : $v;
        }
        if ($pass !== '') {
            $cols[] = 'password_hash';
            $vals[] = password_hash($pass, PASSWORD_DEFAULT);
        } elseif (post('clear_password') === '1') {
            $cols[] = 'password_hash';
            $vals[] = null;
        }
        if ($id) {
            $vals[] = $id;
            q('UPDATE members SET ' . implode(', ', array_map(fn($c) => "$c = ?", $cols)) . ' WHERE id = ?', $vals);
            flash('success', t('member_saved'));
        } else {
            $cols[] = 'card_token';
            $vals[] = bin2hex(random_bytes(8));
            q('INSERT INTO members (' . implode(', ', $cols) . ') VALUES (' . implode(', ', array_fill(0, count($cols), '?')) . ')', $vals);
            $id = (int)db()->lastInsertId();
            flash('success', t('member_added', $d['name'], $d['adm_no']));
            if (post('go_pay') === '1') {
                redirect('payment_add.php?member=' . $id . '&new=1');
            }
        }
        redirect('member_view.php?id=' . $id);
    }
}

$title = $m ? t('edit_member') : t('new_member_form');
$active = $m ? 'members' : 'add_member';
$back = $m ? 'member_view.php?id=' . $id : 'members.php';
require __DIR__ . '/includes/header.php';

$f = fn($k) => e($d[$k] ?? '');
?>
<?php if ($errors): ?><div class="alert alert-danger"><?= implode('<br>', array_map('e', array_unique($errors))) ?></div><?php endif; ?>
<form method="post" enctype="multipart/form-data" class="needs-validation" novalidate>
  <?= csrf_field() ?>
  <input type="hidden" name="id" value="<?= $id ?>">

  <div class="card mb-3"><div class="card-body">
    <div class="d-flex flex-wrap gap-3 align-items-start">
      <div class="flex-grow-1 row g-3" style="min-width:240px">
        <div class="col-6"><label class="form-label" for="join_date"><?= e(t('date')) ?></label>
          <input class="form-control" type="date" id="join_date" name="join_date" value="<?= $f('join_date') ?>"></div>
        <div class="col-6"><label class="form-label" for="adm_no"><?= e(t('adm_no')) ?></label>
          <input class="form-control" id="adm_no" name="adm_no" value="<?= $f('adm_no') ?>" maxlength="20"></div>
      </div>
<?php member_photo_html($d); ?>
    </div>
  </div></div>

<?php member_personal_html($d); ?>
    <div class="row g-3"><div class="col-md-6"><label class="form-label" for="trainer_name"><?= e(t('trainer_name')) ?></label>
      <input class="form-control" id="trainer_name" name="trainer_name" value="<?= $f('trainer_name') ?>"></div></div>
  </div></div>

  <div class="card mb-3"><div class="card-body">
    <span class="section-title"><?= e(t('membership')) ?></span>
    <div class="row g-3">
      <div class="col-md-4"><label class="form-label" for="plan_id"><?= e(t('plan')) ?></label>
        <select class="form-select" id="plan_id" name="plan_id" data-plan-select>
          <option value=""><?= e(t('no_plan')) ?></option>
          <?php foreach ($plans as $p): ?>
            <option value="<?= $p['id'] ?>" data-v="<?= (int)$p['duration_value'] ?>" data-u="<?= e($p['duration_unit']) ?>"<?= (int)($d['plan_id'] ?? 0) === (int)$p['id'] ? ' selected' : '' ?>><?= e($p['name']) ?> – <?= money($p['price']) ?></option>
          <?php endforeach; ?>
        </select></div>
      <div class="col-6 col-md-4"><label class="form-label" for="start_date"><?= e(t('start_date')) ?></label>
        <input class="form-control" type="date" id="start_date" name="start_date" value="<?= $f('start_date') ?>" data-plan-start></div>
      <div class="col-6 col-md-4"><label class="form-label" for="expiry_date"><?= e(t('expiry_date')) ?></label>
        <input class="form-control" type="date" id="expiry_date" name="expiry_date" value="<?= $f('expiry_date') ?>" data-plan-end></div>
      <div class="col-12 small-muted"><?= e(t('expiry_hint')) ?></div>
    </div>
  </div></div>

  <div class="card mb-3"><div class="card-body">
    <span class="section-title"><?= e(t('member_login')) ?></span>
    <div class="row g-3 align-items-end">
      <div class="col-md-6"><label class="form-label" for="new_password"><?= e($m && $m['password_hash'] ? t('change_password') : t('set_password')) ?></label>
        <input class="form-control" type="text" id="new_password" name="new_password" autocomplete="new-password" minlength="4" placeholder="<?= e(t('password_ph')) ?>"></div>
      <?php if ($m && $m['password_hash']): ?>
        <div class="col-md-6"><div class="form-check"><input class="form-check-input" type="checkbox" name="clear_password" value="1" id="cp"><label class="form-check-label" for="cp"><?= e(t('remove_login')) ?></label></div></div>
      <?php endif; ?>
      <div class="col-12 small-muted"><?= e(t('member_login_hint')) ?></div>
      <div class="col-12"><label class="form-label" for="notes"><?= e(t('notes')) ?></label>
        <input class="form-control" id="notes" name="notes" value="<?= $f('notes') ?>" maxlength="500"></div>
    </div>
  </div></div>

  <div class="d-flex flex-wrap gap-2 align-items-center mb-5">
    <button class="btn btn-primary btn-lg px-4"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
    <?php if (!$m): ?>
      <div class="form-check ms-2"><input class="form-check-input" type="checkbox" name="go_pay" value="1" id="gp" checked><label class="form-check-label" for="gp"><?= e(t('go_to_payment')) ?></label></div>
    <?php endif; ?>
    <a href="<?= $m ? 'member_view.php?id=' . $id : 'members.php' ?>" class="btn btn-light btn-lg ms-auto"><?= e(t('cancel')) ?></a>
  </div>
</form>
<?php require __DIR__ . '/includes/footer.php';
