<?php
// Member app: sign in with phone + password, see membership, payments, attendance and training plan,
// scan the attendance QR, pay by UPI.

require __DIR__ . '/includes/init.php';

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    if (post('action') === 'login') {
        if (too_many_attempts()) {
            $error = t('too_many');
        } else {
            $phone = clean_phone(post('phone'));
            $digits = substr(preg_replace('/\D/', '', $phone), -10);
            $found = null;
            foreach (q('SELECT id, phone, password_hash FROM members WHERE password_hash IS NOT NULL AND phone LIKE ?', ['%' . $digits])->fetchAll() as $row) {
                if (password_verify((string)($_POST['password'] ?? ''), $row['password_hash'])) {
                    $found = $row;
                    break;
                }
            }
            if ($found && strlen($digits) >= 10) {
                session_regenerate_id(true);
                $_SESSION['member_id'] = (int)$found['id'];
                redirect(get('next') === 'checkin' ? 'checkin.php' : 'me.php');
            }
            failed_attempt();
            $error = t('member_login_wrong');
        }
    } elseif (post('action') === 'password' && ($m = member_user())) {
        $new = (string)($_POST['new_password'] ?? '');
        if (!password_verify((string)($_POST['old_password'] ?? ''), (string)$m['password_hash'])) {
            flash('danger', t('old_password_wrong'));
        } elseif (strlen($new) < 4) {
            flash('danger', t('err_password_short'));
        } else {
            q('UPDATE members SET password_hash = ? WHERE id = ?', [password_hash($new, PASSWORD_DEFAULT), $m['id']]);
            flash('success', t('password_changed'));
        }
        redirect('me.php');
    }
}

$m = member_user();
$title = $m ? t('my_account') : t('member_login');
$bare = true;
$memberApp = true;
require __DIR__ . '/includes/header.php';

$brand = brand_html('', 'mb-3');

if (!$m): ?>
<div class="pt-4">
  <?= $brand ?>
  <?php if (!empty($_SESSION['pending_checkin'])): ?><div class="alert alert-info"><i class="bi bi-qr-code-scan"></i> <?= e(t('login_to_checkin')) ?></div><?php endif; ?>
  <div class="card"><div class="card-body p-4">
    <h1 class="h5 mb-3"><i class="bi bi-person-badge text-primary"></i> <?= e(t('member_login')) ?></h1>
    <?php if ($error): ?><div class="alert alert-danger py-2"><?= e($error) ?></div><?php endif; ?>
    <form method="post">
      <?= csrf_field() ?><input type="hidden" name="action" value="login">
      <div class="mb-3"><label class="form-label" for="ph"><?= e(t('phone_no')) ?></label>
        <input class="form-control form-control-lg" id="ph" name="phone" type="tel" inputmode="tel" autocomplete="username" required value="<?= e(post('phone')) ?>"></div>
      <div class="mb-4"><label class="form-label" for="pw"><?= e(t('password')) ?></label>
        <input class="form-control form-control-lg" id="pw" name="password" type="password" autocomplete="current-password" required></div>
      <button class="btn btn-primary btn-lg w-100"><i class="bi bi-box-arrow-in-right"></i> <?= e(t('login')) ?></button>
    </form>
    <p class="small-muted mt-3 mb-0"><?= e(t('member_no_password')) ?> <?= e(setting('phone1')) ?></p>
  </div></div>
  <div class="text-center mt-3">
    <a href="lang.php?l=en" class="btn btn-sm btn-light">English</a>
    <a href="lang.php?l=ml" class="btn btn-sm btn-light">മലയാളം</a>
    <a href="login.php" class="btn btn-sm btn-link"><?= e(t('admin_login')) ?></a>
  </div>
</div>
<?php
    require __DIR__ . '/includes/footer.php';
    exit;
endif;

// Invited member who has not filled the join form yet: send them to it.
if ($m['status'] === 'pending' && !$m['details_at'] && $m['invite_token']) {
    redirect('join.php?t=' . $m['invite_token']);
}
$block = attendance_block($m);
$balance = member_balance((int)$m['id']);
$plan = $m['plan_id'] ? q('SELECT * FROM plans WHERE id = ?', [$m['plan_id']])->fetch() : null;
$st = member_status($m['expiry_date']);
$dl = days_left($m['expiry_date']);
$month = date('Y-m');
$days = q('SELECT DAY(att_date) FROM attendance WHERE member_id = ? AND att_date >= ? AND att_date < ?',
    [$m['id'], $month . '-01', date('Y-m-d', strtotime($month . '-01 +1 month'))])->fetchAll(PDO::FETCH_COLUMN);
$todayIn = in_array((int)date('j'), array_map('intval', $days), true);
$payments = q('SELECT id, receipt_no, pay_date, paid FROM payments WHERE member_id = ? ORDER BY pay_date DESC, id DESC LIMIT 10', [$m['id']])->fetchAll();
$week = [];
foreach (q('SELECT day_no, slot, activity FROM activities')->fetchAll() as $r) {
    $week[(int)$r['day_no']][$r['slot']] = $r['activity'];
}
$dow = (int)date('N');
$marks = day_marks($month . '-01', date('Y-m-t'), (int)$m['id']);
$freeze = current_freeze((int)$m['id']);
$leaves = q('SELECT * FROM gym_leaves WHERE to_date >= ? AND from_date <= ? ORDER BY from_date', [today(), date('Y-m-d', strtotime('+14 day'))])->fetchAll();
$progress = levels() && $m['status'] !== 'pending' ? level_progress($m) : null;
$unread = (int)q('SELECT COUNT(*) FROM complaints WHERE member_id = ? AND member_unread = 1', [$m['id']])->fetchColumn();
$payAmount = $balance > 0 ? $balance : ($st !== 'active' && $plan ? (float)$plan['price'] : 0);
?>
<div class="d-flex align-items-center gap-3 mb-3 pt-2">
  <img src="<?= e(photo_url($m)) ?>" class="avatar" style="width:64px;height:64px" alt="">
  <div class="me-auto"><div class="fw-bold fs-5"><?= e($m['name']) ?></div><div class="small-muted"><?= e($m['adm_no']) ?> · <?= e(gym_title()) ?></div></div>
  <a href="lang.php?l=<?= lang() === 'en' ? 'ml' : 'en' ?>" class="btn btn-sm btn-light"><?= lang() === 'en' ? 'മല' : 'EN' ?></a>
</div>
<?= flashes() ?>

<div class="card mb-3 text-white" style="background:linear-gradient(135deg,#C8160E,#1A1A1A)"><div class="card-body">
  <div class="d-flex justify-content-between align-items-start">
    <div><div class="small opacity-75"><?= e(t('plan')) ?></div><div class="fs-5 fw-bold"><?= e($plan['name'] ?? '–') ?></div></div>
    <?= status_badge($m['expiry_date'], $m['status']) ?>
  </div>
  <div class="d-flex justify-content-between mt-3">
    <div><div class="small opacity-75"><?= e(t('expiry_date')) ?></div><div class="fw-bold"><?= e(fdate($m['expiry_date'])) ?></div></div>
    <div class="text-end"><div class="small opacity-75"><?= e($dl < 0 ? t('st_expired') : t('days_left_label')) ?></div><div class="fs-4 fw-bold" style="color:#E8261C"><?= $m['expiry_date'] ? abs($dl) : '–' ?></div></div>
  </div>
</div></div>

<?php if ($m['status'] === 'pending'): ?>
  <div class="alert alert-info"><i class="bi bi-hourglass-split"></i> <?= e(t('join_waiting_help')) ?>
    <?php if ($m['invite_token']): ?><a href="join.php?t=<?= e($m['invite_token']) ?>&edit=1" class="d-block mt-1"><?= e(t('join_edit')) ?></a><?php endif; ?></div>
<?php elseif ($m['status'] === 'inactive'): ?>
  <div class="alert alert-dark"><i class="bi bi-slash-circle"></i> <?= e(t('you_are_inactive')) ?> <?= e(setting('phone1')) ?></div>
<?php endif; ?>
<?php foreach ($leaves as $l): ?>
  <div class="alert alert-danger"><div class="fw-bold"><i class="bi bi-calendar-x"></i> <?= e($l['title']) ?></div>
    <div class="small"><?= e(t('wa_gym_closed', date_range_text($l['from_date'], $l['to_date']))) ?></div>
    <?php if (trim((string)$l['message']) !== ''): ?><div class="small mt-1" style="white-space:pre-line"><?= e($l['message']) ?></div><?php endif; ?></div>
<?php endforeach; ?>
<?php if ($freeze && $m['status'] === 'active'): ?>
  <div class="alert alert-info"><i class="bi bi-snow"></i> <b><?= e(t('freeze_title')) ?>: <?= e(t('fr_' . $freeze['reason'])) ?></b>
    <div class="small"><?= e(date_range_text($freeze['from_date'], $freeze['to_date'])) ?><?= $freeze['extended'] ? ' · ' . e(t('freeze_extended_yes')) : '' ?></div></div>
<?php endif; ?>
<div class="d-grid gap-2 mb-3">
  <?php if ($block !== ''): ?>
    <?php if ($m['status'] === 'active' && $block !== 'att_no_frozen'): // expired and attendance blocked in Settings ?>
      <div class="alert alert-warning mb-0 text-center"><?= e(t($block)) ?></div>
    <?php endif; ?>
  <?php elseif ($todayIn): ?>
    <div class="alert alert-success mb-0 text-center"><i class="bi bi-check-circle-fill"></i> <?= e(t('present_today_member')) ?></div>
  <?php else: ?>
    <button type="button" class="btn btn-accent btn-lg big-btn" id="meScan"><i class="bi bi-qr-code-scan"></i><?= e(t('scan_attendance_qr')) ?></button>
  <?php endif; ?>
  <div id="reader" class="d-none"></div>
  <div id="mePhotoWrap" class="d-none">
    <label class="btn btn-accent btn-lg big-btn w-100" for="mePhoto"><i class="bi bi-camera-fill"></i><?= e(t('photo_scan')) ?></label>
    <input type="file" id="mePhoto" accept="image/*" capture="environment" class="d-none">
    <div class="small-muted text-center mt-1"><?= e(t('photo_scan_help')) ?></div>
  </div>
  <div id="mePhotoReader" class="d-none"></div>
  <div id="meScanMsg" class="small text-center text-danger"></div>
  <?php if ($payAmount > 0 && setting('upi_id') !== ''): ?>
    <a href="pay.php?a=<?= e(number_format($payAmount, 2, '.', '')) ?>" class="btn btn-primary btn-lg"><i class="bi bi-phone"></i> <?= e(t('pay_by_upi')) ?> <?= money($payAmount) ?></a>
  <?php endif; ?>
  <?php if ($balance > 0): ?><div class="text-center text-danger fw-semibold"><?= e(t('balance_due')) ?>: <?= money($balance) ?></div><?php endif; ?>
</div>

<div class="card mb-3"><div class="card-header"><i class="bi bi-calendar-check text-success"></i> <?= e(t('attendance_this_month')) ?>: <?= count($days) ?> <?= e(t('days')) ?></div>
  <div class="card-body">
    <?= month_calendar($month, array_map('intval', $days), $marks['leave'], $marks['freeze'][(int)$m['id']] ?? []) ?>
  </div>
</div>

<?php if ($progress): ?>
<div class="card mb-3"><div class="card-header"><i class="bi bi-award-fill text-primary"></i> <?= e(t('my_position')) ?></div>
  <div class="card-body"><?= level_progress_html($progress) ?>
    <?php if ($progress['level']['note'] !== ''): ?><div class="small-muted mt-1"><?= e($progress['level']['note']) ?></div><?php endif; ?></div>
</div>
<?php endif; ?>

<a href="me_complaints.php" class="card card-body mb-3 d-flex flex-row align-items-center gap-2 text-decoration-none text-reset">
  <i class="bi bi-chat-left-text-fill text-primary fs-4"></i><span class="me-auto fw-semibold"><?= e(t('complaints_suggestions')) ?>
    <span class="d-block small-muted fw-normal"><?= e(t('complaints_member_help')) ?></span></span>
  <?php if ($unread): ?><span class="badge bg-danger"><?= $unread ?> <?= e(t('new_reply')) ?></span><?php endif; ?><i class="bi bi-chevron-right"></i></a>

<div class="card mb-3"><div class="card-header"><i class="bi bi-lightning-charge-fill text-primary"></i> <?= e(t('todays_training')) ?> – <?= e(t('day' . $dow)) ?></div>
  <div class="card-body py-2">
    <?php $any = false; foreach (['warmup', 'primary', 'secondary', 'finisher', 'cooldown'] as $slot): if (($week[$dow][$slot] ?? '') === '') continue; $any = true; ?>
      <div class="d-flex py-1 border-bottom"><span class="small-muted" style="width:8.5rem"><?= e(t('slot_' . $slot)) ?></span><span class="fw-semibold"><?= e($week[$dow][$slot]) ?></span></div>
    <?php endforeach; if (!$any): ?><div class="text-muted py-1"><?= e(t('rest_day')) ?></div><?php endif; ?>
  </div>
</div>

<div class="card mb-3"><div class="card-header"><i class="bi bi-receipt"></i> <?= e(t('my_payments')) ?></div>
  <div class="list-group list-group-flush">
    <?php if (!$payments): ?><div class="p-3 text-muted"><?= e(t('no_payments')) ?></div><?php endif; ?>
    <?php foreach ($payments as $p): ?>
      <a href="receipt.php?id=<?= $p['id'] ?>" class="list-group-item list-group-item-action d-flex"><span class="me-auto">#<?= $p['receipt_no'] ?> · <?= e(fdate($p['pay_date'])) ?></span><b><?= money($p['paid']) ?></b></a>
    <?php endforeach; ?>
  </div>
</div>

<details class="card mb-3"><summary class="card-header"><i class="bi bi-key"></i> <?= e(t('change_password')) ?></summary>
  <form method="post" class="card-body"><?= csrf_field() ?><input type="hidden" name="action" value="password">
    <input class="form-control mb-2" type="password" name="old_password" placeholder="<?= e(t('old_password')) ?>" autocomplete="current-password" required>
    <input class="form-control mb-2" type="password" name="new_password" placeholder="<?= e(t('new_password')) ?>" autocomplete="new-password" minlength="4" required>
    <button class="btn btn-primary w-100"><?= e(t('save')) ?></button>
  </form>
</details>

<div class="d-flex gap-2 mb-4">
  <button type="button" class="btn btn-outline-primary flex-fill d-none" data-install><i class="bi bi-phone"></i> <?= e(t('install_app')) ?></button>
  <form method="post" action="logout.php" class="flex-fill"><?= csrf_field() ?><input type="hidden" name="who" value="member">
    <button class="btn btn-outline-secondary w-100"><i class="bi bi-box-arrow-right"></i> <?= e(t('logout')) ?></button></form>
</div>
<script>window.VM_ME = <?= json_encode(['camErr' => t('camera_use_photo'), 'wrong' => t('not_attendance_qr'), 'noQr' => t('no_qr_in_photo')], JSON_UNESCAPED_UNICODE) ?>;</script>
<?php
$scripts = ['assets/vendor/jsQR.js', 'assets/qrscan.js?v=1'];
require __DIR__ . '/includes/footer.php';
