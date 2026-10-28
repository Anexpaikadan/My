<?php
// Dashboard in sections (Today, Members, Money). Every tile opens the page with those details.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/accounts.php';
$me = require_admin();

$today = today();
$monthStart = date('Y-m-01');
$soon = date('Y-m-d', strtotime('+' . (int)setting('expiry_days', '7') . ' day'));
$absentDays = max(1, (int)setting('absent_days', '7'));

$total = (int)q('SELECT COUNT(*) FROM members')->fetchColumn();
$activeCount = (int)q("SELECT COUNT(*) FROM members WHERE status = 'active' AND expiry_date >= ?", [$today])->fetchColumn();
$byStatus = q('SELECT status, COUNT(*) FROM members GROUP BY status')->fetchAll(PDO::FETCH_KEY_PAIR);
$pending = (int)($byStatus['pending'] ?? 0);
$inactive = (int)($byStatus['inactive'] ?? 0);
$expired = (int)($byStatus['active'] ?? 0) - $activeCount;
$todayPay = q('SELECT COUNT(*) c, COALESCE(SUM(paid), 0) s FROM payments WHERE pay_date = ?', [$today])->fetch();
$expiring = q("SELECT * FROM members WHERE status = 'active' AND expiry_date BETWEEN ? AND ? ORDER BY expiry_date", [$today, $soon])->fetchAll();
$present = (int)q('SELECT COUNT(*) FROM attendance WHERE att_date = ?', [$today])->fetchColumn();
$due = (float)q('SELECT COALESCE(SUM(b), 0) FROM (SELECT SUM(total - paid) b FROM payments GROUP BY member_id HAVING b > 0) x')->fetchColumn();
$absent = (int)q("SELECT COUNT(*) FROM members WHERE status = 'active' AND expiry_date >= ? AND id NOT IN (SELECT member_id FROM attendance WHERE att_date > ?)",
    [$today, date('Y-m-d', strtotime("-$absentDays day"))])->fetchColumn();
$birthdays = q("SELECT * FROM members WHERE dob IS NOT NULL AND DATE_FORMAT(dob, '%m-%d') = ?", [date('m-d')])->fetchAll();
$month = acc_totals($monthStart, $today);
$todayAcc = acc_totals($today, $today);
$cash = acc_balance();
$recent = q('SELECT p.*, m.name FROM payments p JOIN members m ON m.id = p.member_id ORDER BY p.id DESC LIMIT 5')->fetchAll();
$work = q('SELECT slot, activity FROM activities WHERE day_no = ?', [(int)date('N')])->fetchAll(PDO::FETCH_KEY_PAIR);

$title = t('dashboard');
$active = 'dashboard';
require __DIR__ . '/includes/header.php';

// [link, icon, colour, number, label, small text]
$groups = [
    'today' => [
        ['attendance.php?tab=list', 'bi-calendar-check-fill', 'ico-green', $present, t('present_today'), t('of_active', $activeCount)],
        ['payments.php?from=' . $today . '&to=' . $today, 'bi-cash-stack', 'ico-blue', money($todayPay['s']), t('todays_collection'), t('n_payments', (int)$todayPay['c'])],
        ['ledger.php?type=expense&from=' . $today . '&to=' . $today, 'bi-receipt-cutoff', 'ico-red', money($todayAcc['expense']), t('todays_expense'), ''],
        ['alerts.php?tab=birthdays', 'bi-cake2-fill', 'ico-amber', count($birthdays), t('birthdays_today'), ''],
    ],
    'sec_members' => [
        ['members.php', 'bi-people-fill', 'ico-blue', $total, t('total_members'), ''],
        ['members.php?status=active', 'bi-person-check-fill', 'ico-green', $activeCount, t('active_members'), ''],
        ['members.php?status=expired', 'bi-person-x-fill', 'ico-red', $expired, t('expired_memberships'), ''],
        ['alerts.php', 'bi-hourglass-split', 'ico-amber', count($expiring), t('expiring_soon'), t('within_days', (int)setting('expiry_days', '7'))],
        ['alerts.php?tab=absent', 'bi-person-dash-fill', 'ico-dark', $absent, t('absent_members'), t('not_came_days', $absentDays)],
        ['reports.php?r=balance', 'bi-exclamation-diamond-fill', 'ico-red', money($due), t('pending_balance'), ''],
        ['members.php?status=pending', 'bi-person-fill-exclamation', 'ico-blue', $pending, t('waiting_approval'), t('invited_members')],
        ['members.php?status=inactive', 'bi-slash-circle', 'ico-dark', $inactive, t('st_inactive'), t('cannot_attend')],
    ],
    'this_month' => [
        ['ledger.php?type=income&from=' . $monthStart, 'bi-arrow-down-left-circle-fill', 'ico-green', money($month['income']), t('acc_income'), ''],
        ['ledger.php?type=expense&from=' . $monthStart, 'bi-arrow-up-right-circle-fill', 'ico-red', money($month['expense']), t('acc_expense'), ''],
        ['acc_reports.php?r=pl', 'bi-graph-up-arrow', 'ico-blue', money(abs($month['profit'])), $month['profit'] >= 0 ? t('profit') : t('loss'), ''],
        ['accounts.php', 'bi-wallet2', 'ico-dark', money($cash), t('total_balance'), t('cash_and_bank')],
    ],
];
?>
<div class="hello card mb-3"><div class="card-body d-flex align-items-center gap-3">
  <div class="me-auto">
    <div class="small opacity-75"><?= e(t('day' . date('N'))) ?>, <?= e(fdate($today)) ?></div>
    <div class="fs-5 fw-bold"><?= e(t('hello_admin', $me['full_name'] !== '' ? $me['full_name'] : $me['username'])) ?></div>
  </div>
  <a href="attendance.php" class="btn btn-accent btn-lg d-none d-sm-inline-flex align-items-center gap-2"><i class="bi bi-qr-code"></i> <?= e(t('attendance_qr')) ?></a>
</div></div>

<?php $lastDl = setting('last_download'); if ($lastDl === '' || strtotime($lastDl) < strtotime('-7 day')): ?>
  <a href="backup.php" class="alert alert-warning d-flex align-items-center gap-2 text-decoration-none mb-3">
    <i class="bi bi-cloud-arrow-down-fill fs-4"></i><span class="me-auto"><?= e($lastDl === '' ? t('never_downloaded') : t('backup_reminder', fdate($lastDl))) ?></span><i class="bi bi-chevron-right"></i></a>
<?php endif; ?>
<div class="quick-row mb-4">
  <a href="member_invite.php" class="quick tap"><span class="qi bg-primary"><i class="bi bi-person-plus-fill"></i></span><span><?= e(t('new_member')) ?></span></a>
  <a href="payment_add.php" class="quick tap"><span class="qi" style="background:var(--vm-green);color:#10260a"><i class="bi bi-cash-coin"></i></span><span><?= e(t('record_payment')) ?></span></a>
  <a href="entry_edit.php?type=expense" class="quick tap"><span class="qi bg-danger"><i class="bi bi-dash-circle-fill"></i></span><span><?= e(t('add_expense')) ?></span></a>
  <a href="attendance.php" class="quick tap"><span class="qi bg-dark"><i class="bi bi-qr-code"></i></span><span><?= e(t('attendance_qr')) ?></span></a>
  <a href="alerts.php" class="quick tap"><span class="qi" style="background:#25D366"><i class="bi bi-whatsapp"></i></span><span><?= e(t('send_reminders')) ?></span></a>
</div>

<?php foreach ($groups as $sec => $tiles): ?>
  <h2 class="section-head"><?= e(t($sec)) ?><?= $sec === 'this_month' ? ' · ' . e(date('M Y')) : '' ?></h2>
  <div class="row g-2 g-md-3 mb-4">
    <?php foreach ($tiles as [$href, $icon, $cls, $num, $label, $sub]): ?>
      <div class="col-6 col-md-4 col-xl-3">
        <a href="<?= e($href) ?>" class="card stat tap">
          <div class="ico <?= $cls ?>"><i class="bi <?= $icon ?>"></i></div>
          <div class="min-w-0"><div class="num"><?= e((string)$num) ?></div><div class="lbl"><?= e($label) ?></div><?php if ($sub !== ''): ?><div class="sub"><?= e($sub) ?></div><?php endif; ?></div>
          <i class="bi bi-chevron-right go"></i>
        </a>
      </div>
    <?php endforeach; ?>
  </div>
<?php endforeach; ?>

<div class="row g-3">
  <div class="col-lg-6">
    <?php if ($birthdays): ?>
      <div class="card mb-3 border border-warning">
        <div class="card-header"><i class="bi bi-cake2-fill text-warning me-2"></i><?= e(t('birthdays_today')) ?></div>
        <div class="list-group list-group-flush">
          <?php foreach ($birthdays as $m): ?>
            <div class="list-group-item d-flex align-items-center gap-2">
              <img src="<?= e(photo_url($m)) ?>" class="avatar" alt="">
              <a href="member_view.php?id=<?= $m['id'] ?>" class="me-auto text-dark text-decoration-none fw-semibold"><?= e($m['name']) ?></a>
              <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], t('wa_birthday', $m['name'], gym_title()))) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('wish')) ?></a>
            </div>
          <?php endforeach; ?>
        </div>
      </div>
    <?php endif; ?>
    <div class="card mb-3">
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
            <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], reminder_text($m))) ?>" aria-label="WhatsApp"><i class="bi bi-whatsapp"></i></a>
            <a class="btn btn-sm btn-accent" href="payment_add.php?member=<?= $m['id'] ?>" aria-label="<?= e(t('renew')) ?>"><i class="bi bi-arrow-repeat"></i></a>
          </div>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
  <div class="col-lg-6">
    <a href="activities.php" class="card mb-3 text-decoration-none text-dark tap-card">
      <div class="card-header d-flex align-items-center"><i class="bi bi-lightning-charge-fill text-primary me-2"></i><?= e(t('todays_training')) ?> – <?= e(t('day' . date('N'))) ?>
        <i class="bi bi-chevron-right ms-auto"></i></div>
      <div class="card-body py-2">
        <?php $any = false; foreach (['warmup', 'primary', 'secondary', 'finisher', 'cooldown'] as $slot): if (($work[$slot] ?? '') === '') continue; $any = true; ?>
          <div class="d-flex py-1 border-bottom"><span class="small-muted flex-shrink-0" style="width:9rem"><?= e(t('slot_' . $slot)) ?></span><span class="fw-semibold"><?= e($work[$slot]) ?></span></div>
        <?php endforeach; if (!$any): ?><div class="text-muted py-2"><?= e(t('rest_day')) ?></div><?php endif; ?>
      </div>
    </a>
    <div class="card mb-3">
      <div class="card-header d-flex align-items-center"><i class="bi bi-receipt text-success me-2"></i><?= e(t('recent_payments')) ?>
        <a href="payments.php" class="ms-auto small"><?= e(t('view_all')) ?></a></div>
      <div class="list-group list-group-flush">
        <?php if (!$recent): ?><div class="p-3 text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
        <?php foreach ($recent as $p): ?>
          <a href="receipt.php?id=<?= $p['id'] ?>" class="list-group-item list-group-item-action d-flex align-items-center">
            <div class="me-auto"><div class="fw-semibold"><?= e($p['name']) ?></div><div class="small-muted">#<?= $p['receipt_no'] ?> · <?= e(fdate($p['pay_date'])) ?></div></div>
            <div class="fw-bold text-success me-2"><?= money($p['paid']) ?></div><i class="bi bi-chevron-right text-muted"></i>
          </a>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
