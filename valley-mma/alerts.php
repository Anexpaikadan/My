<?php
// Expiry alerts: memberships ending soon and expired ones, with WhatsApp reminders that include the UPI details.

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

$title = t('expiry_alerts');
$active = 'alerts';
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

<ul class="nav nav-pills mb-3 gap-1" role="tablist">
  <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#aSoon" type="button"><i class="bi bi-hourglass-split"></i> <?= e(t('expiring_soon')) ?> <span class="badge bg-warning text-dark"><?= count($expiring) ?></span></button></li>
  <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#aExp" type="button"><i class="bi bi-x-octagon"></i> <?= e(t('st_expired')) ?> <span class="badge bg-danger"><?= count($expired) ?></span></button></li>
  <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#aBal" type="button"><i class="bi bi-exclamation-diamond"></i> <?= e(t('pending_balance')) ?> <span class="badge bg-secondary"><?= count($balances) ?></span></button></li>
</ul>
<div class="tab-content">
  <div class="tab-pane fade show active card" id="aSoon"><?php $list($expiring, 'expiring'); ?></div>
  <div class="tab-pane fade card" id="aExp"><?php $list($expired, 'expired'); ?></div>
  <div class="tab-pane fade card" id="aBal"><?php $list($balances, 'balance'); ?></div>
</div>
<p class="small-muted mt-3"><i class="bi bi-info-circle"></i> <?= e(t('wa_tip')) ?></p>
<?php require __DIR__ . '/includes/footer.php';
