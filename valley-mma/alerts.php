<?php
// Alerts: memberships ending soon, expired, pending balances (WhatsApp reminders with UPI details),
// birthdays (WhatsApp wishes) and active members who have not come for some days (follow-up).

require __DIR__ . '/includes/init.php';
require_admin();

$days = max(1, min(90, (int)get('days', setting('expiry_days', '7'))));
$today = today();
$soon = date('Y-m-d', strtotime("+$days day"));
$sql = 'SELECT m.*, p.name plan_name, p.price plan_price,
        (SELECT COALESCE(SUM(total - paid), 0) FROM payments WHERE member_id = m.id) balance
        FROM members m LEFT JOIN plans p ON p.id = m.plan_id ';
$expiring = q($sql . 'WHERE m.expiry_date BETWEEN ? AND ? ORDER BY m.expiry_date', [$today, $soon])->fetchAll();
$expired = q($sql . 'WHERE m.expiry_date < ? AND m.expiry_date >= ? ORDER BY m.expiry_date DESC', [$today, date('Y-m-d', strtotime('-' . max(1, (int)get('back', '90')) . ' day'))])->fetchAll();
$balances = q($sql . 'HAVING balance > 0 ORDER BY balance DESC')->fetchAll();
$absentDays = max(1, (int)setting('absent_days', '7'));
$absent = q('SELECT m.*, (SELECT MAX(att_date) FROM attendance WHERE member_id = m.id) last_seen FROM members m
             WHERE m.expiry_date >= ? AND m.id NOT IN (SELECT member_id FROM attendance WHERE att_date > ?) ORDER BY last_seen',
    [$today, date('Y-m-d', strtotime("-$absentDays day"))])->fetchAll();
// Birthdays today and in the next 7 days (also across the new year).
$bdays = [];
foreach (q('SELECT * FROM members WHERE dob IS NOT NULL')->fetchAll() as $m) {
    $next = date('Y') . substr($m['dob'], 4);
    if (!valid_date($next)) { // 29 Feb in a normal year
        $next = date('Y') . '-03-01';
    }
    if ($next < $today) {
        $next = date('Y', strtotime('+1 year')) . substr($m['dob'], 4);
    }
    $in = days_left($next);
    if ($in >= 0 && $in <= 7) {
        $m['in_days'] = $in;
        $m['turns'] = (int)substr($next, 0, 4) - (int)substr($m['dob'], 0, 4);
        $bdays[] = $m;
    }
}
usort($bdays, fn($a, $b) => $a['in_days'] <=> $b['in_days']);
$tab = in_array(get('tab'), ['soon', 'expired', 'balance', 'birthdays', 'absent'], true) ? get('tab') : 'soon';

$title = t('expiry_alerts');
$active = 'alerts';
$back = 'index.php';
require __DIR__ . '/includes/header.php';

$list = function (array $rows, string $kind) {
    if (!$rows) {
        echo '<div class="p-4 text-center text-muted">' . e(t('nothing_here')) . '</div>';
        return;
    }
    echo '<div class="list-group list-group-flush">';
    foreach ($rows as $m) {
        $dl = days_left($m['expiry_date']);
        $amount = $kind === 'balance' ? (float)$m['balance'] : (float)$m['balance'] + (float)($m['plan_price'] ?? 0);
        $text = $kind === 'balance'
            ? t('wa_balance', $m['name'], money($m['balance']), gym_title()) . upi_text((float)$m['balance'])
            : reminder_text($m, $amount);
        $cls = $kind === 'expired' ? 'row-expired' : ($kind === 'expiring' ? 'row-expiring' : '');
        echo '<div class="list-group-item d-flex flex-wrap align-items-center gap-2 ' . $cls . '">'
            . '<img src="' . e(photo_url($m)) . '" class="avatar" alt="" loading="lazy">'
            . '<a href="member_view.php?id=' . $m['id'] . '" class="me-auto text-decoration-none text-dark" style="min-width:150px">'
            . '<div class="fw-semibold">' . e($m['name']) . ' <span class="small-muted">' . e($m['adm_no']) . '</span></div>'
            . '<div class="small-muted">' . e($m['plan_name'] ?? '–') . ' · ' . e(fdate($m['expiry_date'])) . ' · '
            . '<b class="' . ($dl < 0 ? 'text-danger' : 'text-warning-emphasis') . '">'
            . e($dl < 0 ? t('expired_days_ago', -$dl) : ($dl === 0 ? t('expires_today') : left_text($dl))) . '</b>'
            . ($m['balance'] > 0 ? ' · <span class="text-danger">' . e(t('balance')) . ' ' . money($m['balance']) . '</span>' : '')
            . '</div></a>'
            . '<div class="d-flex gap-2">'
            . '<a class="btn btn-whatsapp" target="_blank" rel="noopener" data-sent href="' . e(wa_link($m['phone'], $text)) . '"><i class="bi bi-whatsapp"></i> ' . e(t('remind')) . '</a>'
            . '<a class="btn btn-accent" href="payment_add.php?member=' . $m['id'] . '"><i class="bi bi-arrow-repeat"></i> ' . e(t('renew')) . '</a>'
            . '</div></div>';
    }
    echo '</div>';
};
?>
<form class="d-flex flex-wrap gap-2 align-items-center mb-3 filters" method="get">
  <label for="days" class="small-muted"><?= e(t('expiring_within')) ?></label>
  <select class="form-select w-auto" id="days" name="days" onchange="this.form.submit()">
    <?php foreach ([3, 5, 7, 10, 15, 30] as $d): ?><option value="<?= $d ?>"<?= $d === $days ? ' selected' : '' ?>><?= e(t('n_days', $d)) ?></option><?php endforeach; ?>
  </select>
  <?php if (setting('upi_id') === ''): ?>
    <div class="alert alert-warning py-1 px-2 mb-0 small"><i class="bi bi-exclamation-triangle"></i> <?= e(t('upi_not_set')) ?> <a href="settings.php"><?= e(t('settings')) ?></a></div>
  <?php endif; ?>
</form>

<ul class="nav nav-pills mb-3 gap-1 flex-nowrap overflow-auto" role="tablist">
  <?php foreach ([
      'soon' => ['bi-hourglass-split', t('expiring_soon'), count($expiring), 'bg-warning text-dark'],
      'expired' => ['bi-x-octagon', t('st_expired'), count($expired), 'bg-danger'],
      'balance' => ['bi-exclamation-diamond', t('pending_balance'), count($balances), 'bg-secondary'],
      'birthdays' => ['bi-cake2', t('birthdays'), count($bdays), 'bg-warning text-dark'],
      'absent' => ['bi-person-dash', t('absent_members'), count($absent), 'bg-dark'],
  ] as $k => [$ic, $label, $n, $bc]): ?>
    <li class="nav-item"><button class="nav-link text-nowrap<?= $tab === $k ? ' active' : '' ?>" data-bs-toggle="tab" data-bs-target="#a-<?= $k ?>" type="button"><i class="bi <?= $ic ?>"></i> <?= e($label) ?> <span class="badge <?= $bc ?>"><?= $n ?></span></button></li>
  <?php endforeach; ?>
</ul>
<div class="tab-content">
  <div class="tab-pane fade card<?= $tab === 'soon' ? ' show active' : '' ?>" id="a-soon"><?php $list($expiring, 'expiring'); ?></div>
  <div class="tab-pane fade card<?= $tab === 'expired' ? ' show active' : '' ?>" id="a-expired"><?php $list($expired, 'expired'); ?></div>
  <div class="tab-pane fade card<?= $tab === 'balance' ? ' show active' : '' ?>" id="a-balance"><?php $list($balances, 'balance'); ?></div>
  <div class="tab-pane fade card<?= $tab === 'birthdays' ? ' show active' : '' ?>" id="a-birthdays">
    <div class="list-group list-group-flush">
      <?php if (!$bdays): ?><div class="p-4 text-center text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
      <?php foreach ($bdays as $m): ?>
        <div class="list-group-item d-flex flex-wrap align-items-center gap-2">
          <img src="<?= e(photo_url($m)) ?>" class="avatar" alt="" loading="lazy">
          <a href="member_view.php?id=<?= $m['id'] ?>" class="me-auto text-decoration-none text-dark" style="min-width:150px">
            <div class="fw-semibold"><?= e($m['name']) ?> <span class="small-muted"><?= e($m['adm_no']) ?></span></div>
            <div class="small-muted"><?= e(fdate($m['dob'])) ?> · <b class="<?= $m['in_days'] === 0 ? 'text-success' : '' ?>"><?= e($m['in_days'] === 0 ? t('today') : t('in_n_days', $m['in_days'])) ?></b> · <?= e(t('turns_age', $m['turns'])) ?></div></a>
          <a class="btn btn-whatsapp" target="_blank" rel="noopener" data-sent href="<?= e(wa_link($m['phone'], t('wa_birthday', $m['name'], gym_title()))) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('wish')) ?></a>
        </div>
      <?php endforeach; ?>
    </div>
  </div>
  <div class="tab-pane fade card<?= $tab === 'absent' ? ' show active' : '' ?>" id="a-absent">
    <div class="card-header small-muted fw-normal"><?= e(t('absent_help', $absentDays)) ?></div>
    <div class="list-group list-group-flush">
      <?php if (!$absent): ?><div class="p-4 text-center text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
      <?php foreach ($absent as $m): ?>
        <div class="list-group-item d-flex flex-wrap align-items-center gap-2">
          <img src="<?= e(photo_url($m)) ?>" class="avatar" alt="" loading="lazy">
          <a href="member_view.php?id=<?= $m['id'] ?>" class="me-auto text-decoration-none text-dark" style="min-width:150px">
            <div class="fw-semibold"><?= e($m['name']) ?> <span class="small-muted"><?= e($m['adm_no']) ?></span></div>
            <div class="small-muted"><?= e(t('last_came')) ?>: <b><?= $m['last_seen'] ? e(fdate($m['last_seen'])) . ' (' . e(t('n_days', -days_left($m['last_seen']))) . ')' : e(t('never')) ?></b></div></a>
          <a class="btn btn-whatsapp" target="_blank" rel="noopener" data-sent href="<?= e(wa_link($m['phone'], t('wa_absent', $m['name'], gym_title()))) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('follow_up')) ?></a>
          <a class="btn btn-outline-secondary" href="tel:<?= e(clean_phone($m['phone'])) ?>" aria-label="<?= e(t('phone')) ?>"><i class="bi bi-telephone"></i></a>
        </div>
      <?php endforeach; ?>
    </div>
  </div>
</div>
<p class="small-muted mt-3"><i class="bi bi-info-circle"></i> <?= e(t('wa_tip')) ?></p>
<?php require __DIR__ . '/includes/footer.php';
