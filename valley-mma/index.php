<?php
// Dashboard: member counts, today's payments, expiring memberships and today's training.

require __DIR__ . '/includes/init.php';
require_admin();

$today = today();
$soon = date('Y-m-d', strtotime('+' . (int)setting('expiry_days', '7') . ' day'));

$total = (int)q('SELECT COUNT(*) FROM members')->fetchColumn();
$activeCount = (int)q('SELECT COUNT(*) FROM members WHERE expiry_date >= ?', [$today])->fetchColumn();
$expired = (int)q('SELECT COUNT(*) FROM members WHERE expiry_date < ? OR expiry_date IS NULL', [$today])->fetchColumn();
$todayPay = q('SELECT COUNT(*) c, COALESCE(SUM(paid), 0) s FROM payments WHERE pay_date = ?', [$today])->fetch();
$expiring = q('SELECT * FROM members WHERE expiry_date BETWEEN ? AND ? ORDER BY expiry_date', [$today, $soon])->fetchAll();
$present = (int)q('SELECT COUNT(*) FROM attendance WHERE att_date = ?', [$today])->fetchColumn();
$due = (float)q('SELECT COALESCE(SUM(b), 0) FROM (SELECT SUM(total - paid) b FROM payments GROUP BY member_id HAVING b > 0) x')->fetchColumn();
$month = (float)q('SELECT COALESCE(SUM(paid), 0) FROM payments WHERE pay_date >= ?', [date('Y-m-01')])->fetchColumn();
$recent = q('SELECT p.*, m.name FROM payments p JOIN members m ON m.id = p.member_id ORDER BY p.id DESC LIMIT 6')->fetchAll();
$work = q('SELECT slot, activity FROM activities WHERE day_no = ?', [(int)date('N')])->fetchAll(PDO::FETCH_KEY_PAIR);

$title = t('dashboard');
$active = 'dashboard';
require __DIR__ . '/includes/header.php';

$stats = [
    ['members.php', 'bi-people-fill', 'ico-blue', $total, t('total_members')],
    ['members.php?status=active', 'bi-person-check-fill', 'ico-green', $activeCount, t('active_members')],
    ['members.php?status=expired', 'bi-person-x-fill', 'ico-red', $expired, t('expired_memberships')],
    ['payments.php?from=' . $today . '&to=' . $today, 'bi-cash-stack', 'ico-dark', money($todayPay['s']), t('todays_payments') . ' (' . $todayPay['c'] . ')'],
    ['alerts.php', 'bi-hourglass-split', 'ico-amber', count($expiring), t('expiring_soon')],
    ['attendance.php?tab=list', 'bi-calendar-check-fill', 'ico-green', $present, t('present_today')],
    ['reports.php?r=balance', 'bi-exclamation-diamond-fill', 'ico-red', money($due), t('pending_balance')],
    ['reports.php?r=income&period=monthly', 'bi-graph-up-arrow', 'ico-blue', money($month), t('this_month_income')],
];
?>
<div class="row g-3 mb-4">
  <?php foreach ($stats as [$href, $icon, $cls, $num, $label]): ?>
    <div class="col-6 col-md-4 col-xl-3">
      <a href="<?= e($href) ?>" class="card stat">
        <div class="ico <?= $cls ?>"><i class="bi <?= $icon ?>"></i></div>
        <div><div class="num"><?= e((string)$num) ?></div><div class="lbl"><?= e($label) ?></div></div>
      </a>
    </div>
  <?php endforeach; ?>
</div>

<div class="row g-2 g-md-3 mb-4">
  <div class="col-6 col-md-3"><a href="member_edit.php" class="btn btn-primary big-btn w-100"><i class="bi bi-person-plus-fill"></i><?= e(t('new_member')) ?></a></div>
  <div class="col-6 col-md-3"><a href="payment_add.php" class="btn btn-accent big-btn w-100"><i class="bi bi-cash-coin"></i><?= e(t('record_payment')) ?></a></div>
  <div class="col-6 col-md-3"><a href="attendance.php" class="btn btn-dark big-btn w-100"><i class="bi bi-qr-code"></i><?= e(t('attendance_qr')) ?></a></div>
  <div class="col-6 col-md-3"><a href="alerts.php" class="btn btn-warning big-btn w-100"><i class="bi bi-whatsapp"></i><?= e(t('send_reminders')) ?></a></div>
</div>

<div class="row g-3">
  <div class="col-lg-6">
    <div class="card h-100">
      <div class="card-header d-flex align-items-center"><i class="bi bi-hourglass-split text-warning me-2"></i><?= e(t('expiring_soon')) ?>
        <a href="alerts.php" class="ms-auto small"><?= e(t('view_all')) ?></a></div>
      <div class="list-group list-group-flush">
        <?php if (!$expiring): ?><div class="p-3 text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
        <?php foreach (array_slice($expiring, 0, 6) as $m): $dl = days_left($m['expiry_date']); ?>
          <div class="list-group-item d-flex align-items-center gap-2">
            <img src="<?= e(photo_url($m)) ?>" class="avatar" alt="">
            <a href="member_view.php?id=<?= $m['id'] ?>" class="me-auto text-decoration-none text-dark">
              <div class="fw-semibold"><?= e($m['name']) ?></div>
              <div class="small-muted"><?= e(fdate($m['expiry_date'])) ?> · <?= e($dl === 0 ? t('today') : left_text($dl)) ?></div>
            </a>
            <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], reminder_text($m))) ?>"><i class="bi bi-whatsapp"></i></a>
          </div>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
  <div class="col-lg-6">
    <div class="card mb-3">
      <div class="card-header d-flex align-items-center"><i class="bi bi-lightning-charge-fill text-primary me-2"></i><?= e(t('todays_training')) ?> – <?= e(t('day' . date('N'))) ?>
        <a href="activities.php" class="ms-auto small"><?= e(t('week_plan')) ?></a></div>
      <div class="card-body py-2">
        <?php $any = false; foreach (['warmup', 'primary', 'secondary', 'finisher', 'cooldown'] as $slot): if (($work[$slot] ?? '') === '') continue; $any = true; ?>
          <div class="d-flex py-1 border-bottom"><span class="small-muted" style="width:9rem"><?= e(t('slot_' . $slot)) ?></span><span class="fw-semibold"><?= e($work[$slot]) ?></span></div>
        <?php endforeach; if (!$any): ?><div class="text-muted py-2"><?= e(t('rest_day')) ?></div><?php endif; ?>
      </div>
    </div>
    <div class="card">
      <div class="card-header d-flex align-items-center"><i class="bi bi-receipt text-success me-2"></i><?= e(t('recent_payments')) ?>
        <a href="payments.php" class="ms-auto small"><?= e(t('view_all')) ?></a></div>
      <div class="list-group list-group-flush">
        <?php if (!$recent): ?><div class="p-3 text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
        <?php foreach ($recent as $p): ?>
          <a href="receipt.php?id=<?= $p['id'] ?>" class="list-group-item list-group-item-action d-flex">
            <div class="me-auto"><div class="fw-semibold"><?= e($p['name']) ?></div><div class="small-muted">#<?= $p['receipt_no'] ?> · <?= e(fdate($p['pay_date'])) ?></div></div>
            <div class="fw-bold text-success"><?= money($p['paid']) ?></div>
          </a>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
