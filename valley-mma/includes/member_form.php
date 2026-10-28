<?php
// Member join-form fields shared by the admin form (member_edit.php) and the member's own form (join.php):
// personal details, health screening, declaration and photo.

// Text fields a member can fill in themself, with their maximum length.
function member_text_fields(): array
{
    return ['name' => 100, 'phone' => 20, 'address' => 255, 'place' => 100, 'city' => 100, 'district' => 100, 'post' => 100,
        'pin_code' => 10, 'state' => 100, 'occupation' => 100, 'blood_group' => 5, 'urea_creat_uric' => 50, 'hba1c' => 20,
        'health_notes' => 500];
}

// Columns saved from member_read_personal().
function member_personal_cols(): array
{
    return array_merge(array_keys(member_text_fields()), ['dob', 'gender', 'age', 'height_cm', 'weight_kg', 'bmi',
        'hq1', 'hq2', 'hq3', 'hq4', 'hq5', 'hq6', 'hq7', 'hq8', 'declaration', 'photo']);
}

function member_read_personal(array &$d, array &$errors): void
{
    foreach (member_text_fields() as $k => $max) {
        $d[$k] = mb_substr(post($k), 0, $max);
    }
    $d['phone'] = clean_phone($d['phone']);
    $d['dob'] = post('dob');
    if ($d['dob'] !== '' && (!valid_date($d['dob']) || $d['dob'] > today())) {
        $errors[] = t('err_date');
        $d['dob'] = '';
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
    if ($d['name'] === '') {
        $errors[] = t('err_name');
    }
    if (!preg_match('/^\+?\d{10,15}$/', $d['phone'])) {
        $errors[] = t('err_phone');
    }
}

// New photo, or photo removed. $oldPhoto is the file name saved before.
function member_save_photo(array &$d, string $oldPhoto, array &$errors): void
{
    if (!empty($_FILES['photo']['name'])) {
        $photo = save_photo($_FILES['photo']);
        if ($photo === null) {
            $errors[] = t('err_photo');
            return;
        }
        if ($oldPhoto !== '' && is_file(cfg('photo_dir') . '/' . $oldPhoto)) {
            unlink(cfg('photo_dir') . '/' . $oldPhoto);
        }
        $d['photo'] = $photo;
    } elseif (post('remove_photo') === '1' && $oldPhoto !== '') {
        @unlink(cfg('photo_dir') . '/' . $oldPhoto);
        $d['photo'] = '';
    }
}

function member_photo_html(array $d): void
{
?>
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
<?php
}

// Client information, health screening and declaration sections. The declaration card is left open
// (the caller adds more fields and closes it with "</div></div>").
function member_personal_html(array $d): void
{
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
<?php
}
