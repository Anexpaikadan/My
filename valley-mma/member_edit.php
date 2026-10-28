<?php
// New member join form / edit member (same fields as the paper join form) + plan and login password.

require __DIR__ . '/includes/init.php';
require_admin();

$id = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
$m = $id ? q('SELECT * FROM members WHERE id = ?', [$id])->fetch() : null;
if ($id && !$m) {
    redirect('members.php');
}
$plans = q('SELECT * FROM plans WHERE active = 1 OR id = ? ORDER BY sort_order, id', [$m['plan_id'] ?? 0])->fetchAll();
$plansById = array_column($plans, null, 'id');

$text = ['name' => 100, 'phone' => 20, 'address' => 255, 'place' => 100, 'city' => 100, 'district' => 100, 'post' => 100,
    'pin_code' => 10, 'state' => 100, 'occupation' => 100, 'blood_group' => 5, 'urea_creat_uric' => 50, 'hba1c' => 20,
    'health_notes' => 500, 'trainer_name' => 100, 'notes' => 500, 'adm_no' => 20];
$errors = [];

$d = $m ?: [
    'adm_no' => next_adm_no(), 'join_date' => today(), 'start_date' => today(), 'expiry_date' => '', 'state' => 'Kerala',
    'district' => 'Malappuram', 'plan_id' => $plans[0]['id'] ?? null, 'gender' => '', 'photo' => '', 'declaration' => 0,
];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    foreach ($text as $k => $max) {
        $d[$k] = mb_substr(post($k), 0, $max);
    }
    $d['phone'] = clean_phone($d['phone']);
    foreach (['join_date', 'dob', 'start_date', 'expiry_date'] as $k) {
        $d[$k] = post($k);
        if ($d[$k] !== '' && !valid_date($d[$k])) {
            $errors[] = t('err_date');
            $d[$k] = '';
        }
    }
    $d['gender'] = in_array(post('gender'), ['M', 'F'], true) ? post('gender') : '';
    $d['age'] = post('age') !== '' ? min(120, max(1, (int)post('age'))) : null;
    if ($d['dob'] !== '' && $d['age'] === null) {
        $d['age'] = (new DateTime($d['dob']))->diff(new DateTime())->y ?: null;
    }
    $d['height_cm'] = post('height_cm') !== '' ? min(300, num(post('height_cm'))) : null;
    $d['weight_kg'] = post('weight_kg') !== '' ? min(400, num(post('weight_kg'))) : null;
    $d['bmi'] = $d['height_cm'] && $d['weight_kg'] ? round($d['weight_kg'] / (($d['height_cm'] / 100) ** 2), 1) : null;
    for ($i = 1; $i <= 8; $i++) {
        $v = post('hq' . $i);
        $d['hq' . $i] = $v === '1' ? 1 : ($v === '0' ? 0 : null);
    }
    $d['declaration'] = post('declaration') === '1' ? 1 : 0;
    $d['plan_id'] = isset($plansById[(int)post('plan_id')]) ? (int)post('plan_id') : null;

    if ($d['name'] === '') {
        $errors[] = t('err_name');
    }
    if (!preg_match('/^\+?\d{10,15}$/', $d['phone'])) {
        $errors[] = t('err_phone');
    }
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
        if (!empty($_FILES['photo']['name'])) {
            $photo = save_photo($_FILES['photo']);
            if ($photo === null) {
                $errors[] = t('err_photo');
            } else {
                if (($m['photo'] ?? '') !== '' && is_file(cfg('photo_dir') . '/' . $m['photo'])) {
                    unlink(cfg('photo_dir') . '/' . $m['photo']);
                }
                $d['photo'] = $photo;
            }
        } elseif (post('remove_photo') === '1' && ($m['photo'] ?? '') !== '') {
            @unlink(cfg('photo_dir') . '/' . $m['photo']);
            $d['photo'] = '';
        }
    }

    if (!$errors) {
        $cols = array_merge(array_keys($text), ['join_date', 'dob', 'start_date', 'expiry_date', 'gender', 'age', 'height_cm',
            'weight_kg', 'bmi', 'hq1', 'hq2', 'hq3', 'hq4', 'hq5', 'hq6', 'hq7', 'hq8', 'declaration', 'plan_id', 'photo']);
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
require __DIR__ . '/includes/header.php';

$yn = function (int $i) use ($d) {
    $v = $d['hq' . $i] ?? null;
    $out = '<div class="btn-group yn-group" role="group">';
    foreach (['1' => t('yes'), '0' => t('no')] as $val => $label) {
        $chk = $v !== null && (string)(int)$v === (string)$val ? ' checked' : '';
        $cls = $val === '1' ? 'btn-outline-danger' : 'btn-outline-success';
        $out .= '<input type="radio" class="btn-check" name="hq' . $i . '" id="hq' . $i . '_' . $val . '" value="' . $val . '"' . $chk . '>'
            . '<label class="btn ' . $cls . '" for="hq' . $i . '_' . $val . '">' . e($label) . '</label>';
    }
    return $out . '</div>';
};
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
      <div class="text-center">
        <label class="photo-pick" for="photo" title="<?= e(t('photo')) ?>">
          <?php if (($d['photo'] ?? '') !== ''): ?><img src="<?= e(photo_url($d)) ?>" alt="" id="photoPreview">
          <?php else: ?><span id="photoPreviewWrap"><i class="bi bi-camera fs-2 d-block"></i><?= e(t('photo')) ?></span><?php endif; ?>
        </label>
        <input type="file" id="photo" name="photo" accept="image/*" class="d-none" data-preview>
        <?php if (($d['photo'] ?? '') !== ''): ?>
          <div class="form-check small mt-1"><input class="form-check-input" type="checkbox" name="remove_photo" value="1" id="rp"><label class="form-check-label" for="rp"><?= e(t('remove_photo')) ?></label></div>
        <?php endif; ?>
      </div>
    </div>
  </div></div>

  <div class="card mb-3"><div class="card-body">
    <span class="section-title"><?= e(t('client_info')) ?></span>
    <div class="row g-3">
      <div class="col-md-6"><label class="form-label" for="name"><?= e(t('name')) ?> *</label>
        <input class="form-control" id="name" name="name" value="<?= $f('name') ?>" required maxlength="100"></div>
      <div class="col-md-6"><label class="form-label" for="phone"><?= e(t('phone_no')) ?> *</label>
        <input class="form-control" id="phone" name="phone" type="tel" inputmode="tel" value="<?= $f('phone') ?>" required pattern="\+?[0-9 ]{10,17}"></div>
      <div class="col-12"><label class="form-label" for="address"><?= e(t('address')) ?></label>
        <input class="form-control" id="address" name="address" value="<?= $f('address') ?>" maxlength="255"></div>
      <div class="col-6 col-md-4"><label class="form-label" for="place"><?= e(t('place')) ?></label>
        <input class="form-control" id="place" name="place" value="<?= $f('place') ?>"></div>
      <div class="col-6 col-md-4"><label class="form-label" for="city"><?= e(t('city')) ?></label>
        <input class="form-control" id="city" name="city" value="<?= $f('city') ?>"></div>
      <div class="col-6 col-md-4"><label class="form-label" for="district"><?= e(t('district')) ?></label>
        <input class="form-control" id="district" name="district" value="<?= $f('district') ?>"></div>
      <div class="col-6 col-md-4"><label class="form-label" for="post"><?= e(t('post')) ?></label>
        <input class="form-control" id="post" name="post" value="<?= $f('post') ?>"></div>
      <div class="col-6 col-md-4"><label class="form-label" for="pin_code"><?= e(t('pin_code')) ?></label>
        <input class="form-control" id="pin_code" name="pin_code" value="<?= $f('pin_code') ?>" inputmode="numeric" maxlength="10"></div>
      <div class="col-6 col-md-4"><label class="form-label" for="state"><?= e(t('state')) ?></label>
        <input class="form-control" id="state" name="state" value="<?= $f('state') ?>"></div>
      <div class="col-md-6"><label class="form-label" for="occupation"><?= e(t('occupation')) ?></label>
        <input class="form-control" id="occupation" name="occupation" value="<?= $f('occupation') ?>"></div>
      <div class="col-6 col-md-3"><label class="form-label" for="dob"><?= e(t('dob')) ?></label>
        <input class="form-control" type="date" id="dob" name="dob" value="<?= $f('dob') ?>" max="<?= today() ?>" data-age-target="age"></div>
      <div class="col-6 col-md-3"><label class="form-label" for="age"><?= e(t('age')) ?></label>
        <input class="form-control" type="number" id="age" name="age" value="<?= $f('age') ?>" min="1" max="120"></div>
      <div class="col-12 col-md-4"><label class="form-label d-block"><?= e(t('gender')) ?></label>
        <div class="btn-group w-100" role="group">
          <input type="radio" class="btn-check" name="gender" id="gM" value="M"<?= ($d['gender'] ?? '') === 'M' ? ' checked' : '' ?>><label class="btn btn-outline-primary" for="gM"><?= e(t('male')) ?> (M)</label>
          <input type="radio" class="btn-check" name="gender" id="gF" value="F"<?= ($d['gender'] ?? '') === 'F' ? ' checked' : '' ?>><label class="btn btn-outline-primary" for="gF"><?= e(t('female')) ?> (F)</label>
        </div></div>
      <div class="col-4 col-md-3"><label class="form-label" for="height_cm"><?= e(t('height')) ?> (cm)</label>
        <input class="form-control" type="number" step="0.1" id="height_cm" name="height_cm" value="<?= $f('height_cm') ?>" data-bmi></div>
      <div class="col-4 col-md-3"><label class="form-label" for="weight_kg"><?= e(t('weight')) ?> (kg)</label>
        <input class="form-control" type="number" step="0.1" id="weight_kg" name="weight_kg" value="<?= $f('weight_kg') ?>" data-bmi></div>
      <div class="col-4 col-md-2"><label class="form-label" for="bmi">BMI</label>
        <input class="form-control" id="bmi" value="<?= $f('bmi') ?>" readonly tabindex="-1"></div>
    </div>
  </div></div>

  <div class="card mb-3"><div class="card-body">
    <span class="section-title"><?= e(t('health_screening')) ?></span>
    <?php for ($i = 1; $i <= 8; $i++): ?>
      <div class="d-flex flex-wrap align-items-center gap-2 py-2 border-bottom">
        <div class="me-auto" style="flex:1 1 260px"><?= $i ?>. <?= e(t('hq' . $i)) ?></div>
        <?= $yn($i) ?>
      </div>
    <?php endfor; ?>
    <div class="row g-3 mt-1">
      <div class="col-6 col-md-3"><label class="form-label" for="blood_group"><?= e(t('blood_group')) ?></label>
        <select class="form-select" id="blood_group" name="blood_group"><option value=""></option>
          <?php foreach (['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] as $bg): ?><option<?= ($d['blood_group'] ?? '') === $bg ? ' selected' : '' ?>><?= $bg ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-6 col-md-3"><label class="form-label" for="urea_creat_uric"><?= e(t('urea_creat_uric')) ?></label>
        <input class="form-control" id="urea_creat_uric" name="urea_creat_uric" value="<?= $f('urea_creat_uric') ?>"></div>
      <div class="col-6 col-md-3"><label class="form-label" for="hba1c">HbA1c</label>
        <input class="form-control" id="hba1c" name="hba1c" value="<?= $f('hba1c') ?>"></div>
      <div class="col-12"><label class="form-label" for="health_notes"><?= e(t('health_notes')) ?></label>
        <input class="form-control" id="health_notes" name="health_notes" value="<?= $f('health_notes') ?>" maxlength="500"></div>
    </div>
  </div></div>

  <div class="card mb-3"><div class="card-body">
    <span class="section-title"><?= e(t('client_declaration')) ?></span>
    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" name="declaration" value="1" id="decl"<?= !empty($d['declaration']) ? ' checked' : '' ?>>
      <label class="form-check-label" for="decl"><?= e(t('declaration_text')) ?></label>
    </div>
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
