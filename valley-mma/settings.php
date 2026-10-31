<?php
// Settings: gym details, UPI payment, alerts, language, attendance options and admin accounts.

require __DIR__ . '/includes/init.php';
$me = require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $a = post('action');
    if ($a === 'gym') {
        $fields = ['gym_name' => 40, 'gym_tagline' => 40, 'gym_place' => 40, 'phone1' => 30, 'phone2' => 30, 'upi_id' => 80,
            'upi_name' => 80, 'upi_phone' => 20];
        foreach ($fields as $k => $max) {
            set_setting($k, mb_substr(post($k), 0, $max));
        }
        if (post('upi_id') !== '' && !preg_match('/^[\w.\-]{2,}@[\w.\-]{2,}$/', post('upi_id'))) {
            flash('warning', t('upi_id_check'));
        }
        set_setting('country_code', preg_replace('/\D/', '', post('country_code')) ?: '91');
        $appUrl = post('app_url');
        if ($appUrl === '' || valid_app_url($appUrl)) {
            set_setting('app_url', $appUrl === '' ? '' : rtrim($appUrl, '/') . '/');
        } else {
            flash('danger', t('app_url_bad'));
        }
        set_setting('admission_fee', (string)num(post('admission_fee')));
        set_setting('expiry_days', (string)max(1, min(60, (int)post('expiry_days'))));
        set_setting('absent_days', (string)max(1, min(60, (int)post('absent_days'))));
        set_setting('default_lang', post('default_lang') === 'ml' ? 'ml' : 'en');
        flash('success', t('saved'));
    } elseif ($a === 'share') { // photo and text shown by WhatsApp under every app link
        set_setting('og_on', post('og_on') === '1' ? '1' : '0');
        set_setting('og_title', mb_substr(trim(post('og_title')), 0, 90));
        set_setting('og_text', mb_substr(trim(post('og_text')), 0, 200));
        $old = setting('og_img');
        if (!empty($_FILES['og_img']['name'])) {
            $f = save_photo($_FILES['og_img'], 1200, __DIR__ . '/media');
            if ($f === null) {
                flash('danger', t('err_photo'));
            } else {
                set_setting('og_img', $f);
                if ($old !== '') {
                    @unlink(__DIR__ . '/media/' . $old);
                }
            }
        } elseif (post('og_default') === '1' && $old !== '') {
            @unlink(__DIR__ . '/media/' . $old);
            set_setting('og_img', '');
        }
        flash('success', t('saved'));
    } elseif ($a === 'attendance') {
        $order = array_values(array_intersect((array)($_POST['order'] ?? []), ['qr', 'card', 'manual']));
        set_setting('att_order', implode(',', array_unique(array_merge($order, ['qr', 'card', 'manual']))));
        set_setting('att_default', in_array(post('att_default'), ['qr', 'card', 'manual'], true) ? post('att_default') : 'qr');
        set_setting('att_camera', post('att_camera') === 'user' ? 'user' : 'environment');
        set_setting('att_refresh', (string)max(0, min(60, (int)post('att_refresh'))));
        set_setting('att_block_expired', post('att_block_expired') === '1' ? '1' : '0');
        set_setting('trial_days', (string)max(1, min(366, (int)post('trial_days'))));
        flash('success', t('saved'));
    } elseif ($a === 'password') {
        $row = q('SELECT password_hash FROM admins WHERE id = ?', [$me['id']])->fetch();
        $new = (string)($_POST['new_password'] ?? '');
        if (!password_verify((string)($_POST['old_password'] ?? ''), $row['password_hash'])) {
            flash('danger', t('old_password_wrong'));
        } elseif (strlen($new) < 6) {
            flash('danger', t('err_admin_password'));
        } elseif ($new !== (string)($_POST['new_password2'] ?? '')) {
            flash('danger', t('passwords_differ'));
        } else {
            q('UPDATE admins SET password_hash = ? WHERE id = ?', [password_hash($new, PASSWORD_DEFAULT), $me['id']]);
            flash('success', t('password_changed'));
        }
    } elseif (in_array($a, ['add_admin', 'admin_password', 'delete_admin'], true) && !verify_ok()) {
        flash('danger', t('verify_wrong'));
    } elseif ($a === 'add_admin') {
        $u = post('username');
        $p = (string)($_POST['password'] ?? '');
        if (!preg_match('/^[A-Za-z0-9_.-]{3,50}$/', $u)) {
            flash('danger', t('err_username'));
        } elseif (strlen($p) < 6) {
            flash('danger', t('err_admin_password'));
        } elseif (q('SELECT COUNT(*) FROM admins WHERE username = ?', [$u])->fetchColumn()) {
            flash('danger', t('username_taken'));
        } else {
            q('INSERT INTO admins (username, full_name, password_hash) VALUES (?, ?, ?)', [$u, mb_substr(post('full_name'), 0, 100), password_hash($p, PASSWORD_DEFAULT)]);
            flash('success', t('saved'));
        }
    } elseif ($a === 'admin_password') {
        $p = (string)($_POST['password'] ?? '');
        if (strlen($p) < 6) {
            flash('danger', t('err_admin_password'));
        } else {
            q('UPDATE admins SET password_hash = ? WHERE id = ?', [password_hash($p, PASSWORD_DEFAULT), (int)post('id')]);
            flash('success', t('password_changed'));
        }
    } elseif ($a === 'delete_admin' && (int)post('id') !== (int)$me['id']) {
        q('DELETE FROM admins WHERE id = ?', [(int)post('id')]);
        flash('success', t('removed'));
    }
    redirect('settings.php#' . $a);
}

$admins = q('SELECT id, username, full_name, created_at FROM admins ORDER BY id')->fetchAll();
$order = array_values(array_unique(array_merge(array_intersect(explode(',', setting('att_order', 'qr,card,manual')), ['qr', 'card', 'manual']), ['qr', 'card', 'manual'])));
$attLabels = ['qr' => t('show_qr'), 'card' => t('scan_card'), 'manual' => t('mark_manually')];
$s = fn($k, $d = '') => e(setting($k, $d));

$title = t('settings');
$active = 'settings';
$back = 'more.php';
require __DIR__ . '/includes/header.php';
?>
<div class="row g-3">
  <div class="col-lg-7">
    <form method="post" class="card mb-3" id="gym"><?= csrf_field() ?><input type="hidden" name="action" value="gym">
      <div class="card-header"><i class="bi bi-building"></i> <?= e(t('gym_details')) ?></div>
      <div class="card-body row g-3">
        <div class="col-md-4"><label class="form-label"><?= e(t('gym_name')) ?></label><input class="form-control" name="gym_name" value="<?= $s('gym_name') ?>" maxlength="40"></div>
        <div class="col-6 col-md-4"><label class="form-label"><?= e(t('tagline')) ?></label><input class="form-control" name="gym_tagline" value="<?= $s('gym_tagline') ?>" maxlength="40"></div>
        <div class="col-6 col-md-4"><label class="form-label"><?= e(t('place')) ?></label><input class="form-control" name="gym_place" value="<?= $s('gym_place') ?>" maxlength="40"></div>
        <div class="col-6"><label class="form-label"><?= e(t('phone')) ?> 1</label><input class="form-control" name="phone1" value="<?= $s('phone1') ?>"></div>
        <div class="col-6"><label class="form-label"><?= e(t('phone')) ?> 2</label><input class="form-control" name="phone2" value="<?= $s('phone2') ?>"></div>
        <div class="col-12"><label class="form-label" for="app_url"><?= e(t('app_url_label')) ?></label>
          <input class="form-control" id="app_url" name="app_url" value="<?= $s('app_url') ?>" placeholder="<?= e(detected_url()) ?>" inputmode="url">
          <div class="small-muted mt-1"><?= e(t('app_url_hint')) ?><?php if (is_local_url(detected_url()) && lan_url() !== ''): ?> <?= e(t('app_url_suggest')) ?> <code><?= e(lan_url()) ?></code><?php endif; ?></div></div>
      </div>
      <div class="card-header border-top"><i class="bi bi-phone"></i> <?= e(t('upi_payment')) ?></div>
      <div class="card-body row g-3">
        <div class="col-md-6"><label class="form-label"><?= e(t('upi_id')) ?></label><input class="form-control" name="upi_id" value="<?= $s('upi_id') ?>" placeholder="valleymma@okaxis" data-upi-input></div>
        <div class="col-md-6"><label class="form-label"><?= e(t('upi_phone')) ?></label><input class="form-control" name="upi_phone" value="<?= $s('upi_phone') ?>" placeholder="9XXXXXXXXX" inputmode="tel"></div>
        <div class="col-md-6"><label class="form-label"><?= e(t('upi_name')) ?></label><input class="form-control" name="upi_name" value="<?= $s('upi_name') ?>"></div>
        <div class="col-md-6 text-center"><?php if (setting('upi_id') !== ''): ?><div class="qr-box border" style="max-width:150px" data-qr="<?= e(upi_link()) ?>"></div><div class="small-muted"><?= e(t('test_scan')) ?></div><?php endif; ?></div>
      </div>
      <div class="card-header border-top"><i class="bi bi-sliders"></i> <?= e(t('general')) ?></div>
      <div class="card-body row g-3">
        <div class="col-6 col-md-3"><label class="form-label"><?= e(t('admission_fee')) ?> (₹)</label><input class="form-control" type="number" min="0" step="0.01" name="admission_fee" value="<?= $s('admission_fee', '0') ?>"></div>
        <div class="col-6 col-md-3"><label class="form-label"><?= e(t('alert_days')) ?></label><input class="form-control" type="number" min="1" max="60" name="expiry_days" value="<?= $s('expiry_days', '7') ?>"></div>
        <div class="col-6 col-md-3"><label class="form-label"><?= e(t('absent_days_label')) ?></label><input class="form-control" type="number" min="1" max="60" name="absent_days" value="<?= $s('absent_days', '7') ?>"></div>
        <div class="col-6 col-md-3"><label class="form-label"><?= e(t('country_code')) ?></label><input class="form-control" name="country_code" value="<?= $s('country_code', '91') ?>" inputmode="numeric"></div>
        <div class="col-6 col-md-3"><label class="form-label"><?= e(t('default_language')) ?></label>
          <select class="form-select" name="default_lang"><option value="en">English</option><option value="ml"<?= setting('default_lang') === 'ml' ? ' selected' : '' ?>>മലയാളം</option></select></div>
      </div>
      <div class="card-footer bg-transparent"><button class="btn btn-primary btn-lg"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
    </form>

    <form method="post" class="card mb-3" id="attendance"><?= csrf_field() ?><input type="hidden" name="action" value="attendance">
      <div class="card-header"><i class="bi bi-qr-code-scan"></i> <?= e(t('attendance_settings')) ?></div>
      <div class="card-body">
        <label class="form-label"><?= e(t('att_order')) ?></label>
        <ul class="list-group mb-3" id="attOrder">
          <?php foreach ($order as $k): ?>
            <li class="list-group-item d-flex align-items-center gap-2"><input type="hidden" name="order[]" value="<?= $k ?>">
              <i class="bi bi-grip-vertical text-muted"></i><span class="me-auto"><?= e($attLabels[$k]) ?></span>
              <button type="button" class="btn btn-sm btn-light" data-move="up" aria-label="Up"><i class="bi bi-arrow-up"></i></button>
              <button type="button" class="btn btn-sm btn-light" data-move="down" aria-label="Down"><i class="bi bi-arrow-down"></i></button></li>
          <?php endforeach; ?>
        </ul>
        <div class="row g-3">
          <div class="col-md-4"><label class="form-label"><?= e(t('att_default')) ?></label>
            <select class="form-select" name="att_default"><?php foreach ($attLabels as $k => $l): ?><option value="<?= $k ?>"<?= setting('att_default', 'qr') === $k ? ' selected' : '' ?>><?= e($l) ?></option><?php endforeach; ?></select></div>
          <div class="col-md-4"><label class="form-label"><?= e(t('att_camera')) ?></label>
            <select class="form-select" name="att_camera"><option value="environment"><?= e(t('camera_back')) ?></option><option value="user"<?= setting('att_camera') === 'user' ? ' selected' : '' ?>><?= e(t('camera_front')) ?></option></select></div>
          <div class="col-md-4"><label class="form-label"><?= e(t('att_refresh')) ?></label>
            <select class="form-select" name="att_refresh"><?php foreach ([0, 1, 2, 5, 10, 30] as $n): ?><option value="<?= $n ?>"<?= (int)setting('att_refresh', '0') === $n ? ' selected' : '' ?>><?= e($n ? t('every_n_min', $n) : t('once_a_day')) ?></option><?php endforeach; ?></select></div>
          <div class="col-md-4"><label class="form-label"><?= e(t('trial_days_label')) ?></label>
            <input class="form-control" type="number" min="1" max="366" name="trial_days" value="<?= $s('trial_days', '7') ?>"></div>
          <div class="col-md-8 d-flex align-items-end"><div class="form-check form-switch">
            <input class="form-check-input" type="checkbox" role="switch" name="att_block_expired" value="1" id="abe"<?= setting('att_block_expired') === '1' ? ' checked' : '' ?>>
            <label class="form-check-label" for="abe"><?= e(t('att_block_expired_label')) ?></label></div></div>
          <div class="col-12 small-muted"><i class="bi bi-info-circle"></i> <?= e(t('att_rules_hint')) ?></div>
        </div>
      </div>
      <div class="card-footer bg-transparent"><button class="btn btn-primary"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
    </form>
  </div>

  <div class="col-lg-5">
    <form method="post" enctype="multipart/form-data" class="card mb-3" id="share"><?= csrf_field() ?><input type="hidden" name="action" value="share">
      <div class="card-header d-flex align-items-center gap-2"><i class="bi bi-whatsapp text-success"></i><span class="me-auto"><?= e(t('link_preview')) ?></span>
        <div class="form-check form-switch mb-0"><input class="form-check-input" type="checkbox" role="switch" name="og_on" value="1" id="ogOn"<?= og_on() ? ' checked' : '' ?>>
          <label class="form-check-label small" for="ogOn"><?= e(t('show')) ?></label></div></div>
      <div class="card-body">
        <p class="small-muted"><?= e(t('link_preview_help')) ?></p>
        <div class="wa-preview mb-3">
          <img src="<?= e(og_image_path()) ?>" alt="">
          <div class="p-2"><div class="fw-semibold small"><?= e(og_title('')) ?></div><div class="small-muted" style="font-size:.75rem"><?= e(og_text()) ?></div>
            <div class="small-muted" style="font-size:.7rem"><?= e(parse_url(base_url(), PHP_URL_HOST)) ?></div></div>
        </div>
        <label class="form-label small" for="ogImg"><?= e(t('change_photo')) ?></label>
        <input class="form-control mb-1" type="file" id="ogImg" name="og_img" accept="image/*">
        <div class="form-text mt-0 mb-2"><?= e(t('link_preview_photo_help')) ?></div>
        <?php if (setting('og_img') !== ''): ?><div class="form-check small mb-2"><input class="form-check-input" type="checkbox" name="og_default" value="1" id="ogDef"><label class="form-check-label" for="ogDef"><?= e(t('use_default_photo')) ?></label></div><?php endif; ?>
        <label class="form-label small" for="ogTitle"><?= e(t('heading')) ?></label>
        <input class="form-control mb-2" id="ogTitle" name="og_title" maxlength="90" value="<?= e(setting('og_title')) ?>" placeholder="<?= e(gym_title()) ?>">
        <label class="form-label small" for="ogText"><?= e(t('content')) ?></label>
        <input class="form-control" id="ogText" name="og_text" maxlength="200" value="<?= e(setting('og_text')) ?>" placeholder="<?= e(pub('pub_hero_text')) ?>">
      </div>
      <div class="card-footer bg-transparent"><button class="btn btn-primary"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
    </form>

    <form method="post" class="card mb-3" id="password"><?= csrf_field() ?><input type="hidden" name="action" value="password">
      <div class="card-header"><i class="bi bi-key"></i> <?= e(t('change_my_password')) ?> (<?= e($me['username']) ?>)</div>
      <div class="card-body d-grid gap-2">
        <input class="form-control" type="password" name="old_password" placeholder="<?= e(t('old_password')) ?>" autocomplete="current-password" required>
        <input class="form-control" type="password" name="new_password" placeholder="<?= e(t('new_password')) ?>" autocomplete="new-password" minlength="6" required>
        <input class="form-control" type="password" name="new_password2" placeholder="<?= e(t('repeat_password')) ?>" autocomplete="new-password" minlength="6" required>
        <button class="btn btn-primary"><?= e(t('save')) ?></button>
      </div>
    </form>

    <div class="card mb-3" id="add_admin">
      <div class="card-header"><i class="bi bi-shield-lock"></i> <?= e(t('admins')) ?></div>
      <ul class="list-group list-group-flush">
        <?php foreach ($admins as $a): ?>
          <li class="list-group-item">
            <div class="d-flex align-items-center gap-2"><i class="bi bi-person-circle"></i><b class="me-auto"><?= e($a['username']) ?></b><span class="small-muted"><?= e($a['full_name']) ?></span>
              <?php if ((int)$a['id'] !== (int)$me['id']): ?>
                <form method="post" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete_admin"><input type="hidden" name="id" value="<?= $a['id'] ?>"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
              <?php endif; ?></div>
            <?php if ((int)$a['id'] !== (int)$me['id']): ?>
              <form method="post" class="input-group input-group-sm mt-2" data-verify="<?= e(t('verify_admin')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="admin_password"><input type="hidden" name="id" value="<?= $a['id'] ?>">
                <input class="form-control" type="password" name="password" placeholder="<?= e(t('new_password')) ?>" minlength="6" required autocomplete="new-password"><button class="btn btn-outline-primary"><?= e(t('change')) ?></button></form>
            <?php endif; ?>
          </li>
        <?php endforeach; ?>
      </ul>
      <form method="post" class="card-body d-grid gap-2 border-top" data-verify="<?= e(t('verify_admin')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="add_admin">
        <div class="small fw-semibold"><?= e(t('add_admin')) ?></div>
        <input class="form-control" name="username" placeholder="<?= e(t('username')) ?>" required pattern="[A-Za-z0-9_.\-]{3,50}" autocomplete="off">
        <input class="form-control" name="full_name" placeholder="<?= e(t('name')) ?>">
        <input class="form-control" type="password" name="password" placeholder="<?= e(t('password')) ?>" minlength="6" required autocomplete="new-password">
        <button class="btn btn-outline-primary"><i class="bi bi-plus-lg"></i> <?= e(t('add_admin')) ?></button>
      </form>
    </div>

    <div class="card mb-3"><div class="card-body d-grid gap-2">
      <a href="member_print.php" target="_blank" class="btn btn-outline-secondary"><i class="bi bi-printer"></i> <?= e(t('print_blank_form')) ?></a>
      <a href="me.php" target="_blank" class="btn btn-outline-secondary"><i class="bi bi-box-arrow-up-right"></i> <?= e(t('member_app_link')) ?></a>
      <div class="small-muted"><?= e(t('member_app_hint')) ?> <code><?= e(base_url()) ?>me.php</code></div>
    </div></div>
  </div>
</div>
<?php
$scripts = ['assets/vendor/qrcode.js', 'assets/qr.js'];
require __DIR__ . '/includes/footer.php';
