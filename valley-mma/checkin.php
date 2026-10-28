<?php
// Opened when a member scans the attendance QR code shown on the admin phone.
// The member signs in once on their phone; after that every scan marks them present.

require __DIR__ . '/includes/init.php';

$d = get('d');
$k = get('k');
$error = '';

if ($d !== '' || $k !== '') {
    $ok = $d === today();
    if ($ok) {
        $ok = false;
        foreach ([0, 1, 2] as $back) { // the code changed a moment ago: still accept it
            if (hash_equals(att_key($d, att_slot($back)), $k)) {
                $ok = true;
                break;
            }
        }
    }
    if (!$ok) {
        $error = $d !== today() ? t('qr_old') : t('qr_invalid');
    } else {
        $_SESSION['pending_checkin'] = $d;
    }
}

$m = member_user();
if (!$m && !$error && !empty($_SESSION['pending_checkin'])) {
    redirect('me.php?next=checkin');
}

$result = null;
$block = '';
if (!$error) {
    if (!$m || ($_SESSION['pending_checkin'] ?? '') !== today()) {
        redirect('me.php'); // opened without scanning today's code
    }
    unset($_SESSION['pending_checkin']);
    // Deactivated / not yet approved members (and expired ones when blocked in Settings) are not marked.
    $block = attendance_block($m);
    if ($block !== '') {
        $error = t($block);
    } else {
        $st = q('INSERT IGNORE INTO attendance (member_id, att_date, check_in, method) VALUES (?, ?, ?, ?)', [$m['id'], today(), date('H:i:s'), 'qr']);
        $result = $st->rowCount() > 0 ? 'new' : 'again';
    }
}
$time = $m ? (string)q('SELECT check_in FROM attendance WHERE member_id = ? AND att_date = ?', [$m['id'], today()])->fetchColumn() : '';
$monthCount = $m ? (int)q('SELECT COUNT(*) FROM attendance WHERE member_id = ? AND att_date >= ?', [$m['id'], date('Y-m-01')])->fetchColumn() : 0;
$status = $m ? member_status($m['expiry_date']) : 'none';

$title = t('attendance');
$bare = true;
$memberApp = true;
require __DIR__ . '/includes/header.php';
?>
<div class="text-center pt-4">
  <?php if ($error): ?>
    <div class="checkin-big text-danger mb-3"><i class="bi bi-x-circle-fill"></i></div>
    <h1 class="h4"><?= e($error) ?></h1>
    <p><?= e($block !== '' ? t('ask_at_desk') : t('scan_again')) ?></p>
  <?php else: ?>
    <div class="checkin-big text-success mb-3"><i class="bi bi-check-circle-fill"></i></div>
    <h1 class="h3 mb-1"><?= e($result === 'new' ? t('welcome_present') : t('already_marked')) ?></h1>
    <div class="fs-4 fw-bold"><?= e($m['name']) ?></div>
    <div class="small-muted mb-3"><?= e(fdate(today())) ?> · <?= e(substr($time, 0, 5)) ?></div>
    <div class="card mb-3"><div class="card-body">
      <div class="d-flex justify-content-around">
        <div><div class="fs-3 fw-bold text-primary"><?= $monthCount ?></div><div class="small-muted"><?= e(t('days_this_month')) ?></div></div>
        <div><div class="fs-6 fw-bold mt-2"><?= e(fdate($m['expiry_date'])) ?></div><div class="small-muted"><?= e(t('expiry_date')) ?></div></div>
      </div>
    </div></div>
    <?php if ($status === 'expired'): ?>
      <div class="alert alert-danger"><?= e(t('membership_expired_on', fdate($m['expiry_date']))) ?> <?= e(t('please_renew')) ?></div>
      <?php if (setting('upi_id') !== ''): ?><a href="pay.php" class="btn btn-accent btn-lg w-100 mb-2"><i class="bi bi-phone"></i> <?= e(t('pay_by_upi')) ?></a><?php endif; ?>
    <?php elseif ($status === 'expiring'): ?>
      <div class="alert alert-warning"><?= e(left_text(days_left($m['expiry_date']))) ?> – <?= e(t('please_renew')) ?></div>
    <?php endif; ?>
  <?php endif; ?>
  <a href="me.php" class="btn btn-primary btn-lg w-100"><i class="bi bi-person-circle"></i> <?= e(t('my_account')) ?></a>
</div>
<?php require __DIR__ . '/includes/footer.php';
