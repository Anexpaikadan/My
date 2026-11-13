<?php
// Training plan ("Valley daily"). Monthly plan: the admin sets the training of every date
// (warm-up, primary, secondary, finisher, cool-down). A date that is not set uses the weekly plan,
// which is kept as the standard week. Members see the month in the member app.

require __DIR__ . '/includes/init.php';
require_admin();

$slots = PLAN_SLOTS;
$view = get('view') === 'week' ? 'week' : 'month';
$month = preg_match('/^\d{4}-\d{2}$/', get('month')) ? get('month') : date('Y-m');
$day = valid_date(get('day')) ? get('day') : '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = post('action');
    if ($action === 'week') { // standard week
        foreach ($slots as $slot) {
            for ($d = 1; $d <= 7; $d++) {
                q('INSERT INTO activities (day_no, slot, activity) VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE activity = VALUES(activity)',
                    [$d, $slot, mb_substr(trim((string)($_POST['a'][$slot][$d] ?? '')), 0, 200)]);
            }
        }
        flash('success', t('saved'));
        redirect('activities.php?view=week');
    }
    $date = valid_date(post('date')) ? post('date') : '';
    $back = 'activities.php?month=' . substr($date ?: today(), 0, 7) . ($date ? '#d' . $date : '');
    if ($date !== '' && in_array($action, ['day', 'rest', 'reset'], true)) {
        // also for the same weekday in the rest of that month, when ticked
        $dates = [$date];
        if (post('same_weekday') === '1') {
            for ($d = date('Y-m-d', strtotime($date . ' +7 day')); substr($d, 0, 7) === substr($date, 0, 7); $d = date('Y-m-d', strtotime($d . ' +7 day'))) {
                $dates[] = $d;
            }
        }
        foreach ($dates as $d) {
            if ($action === 'reset') {
                q('DELETE FROM activity_days WHERE plan_date = ?', [$d]);
            } else {
                day_plan_save($d, $action === 'rest' ? [] : (array)($_POST['p'] ?? []));
            }
        }
        flash('success', t($action === 'reset' ? 'plan_reset_done' : 'plan_day_saved', fdate($date)) . (count($dates) > 1 ? ' (' . count($dates) . ' ' . t('days') . ')' : ''));
    } elseif ($action === 'reset_month' && preg_match('/^\d{4}-\d{2}$/', post('month'))) {
        require_verify('activities.php?month=' . post('month'));
        q('DELETE FROM activity_days WHERE plan_date BETWEEN ? AND ?', [post('month') . '-01', date('Y-m-t', strtotime(post('month') . '-01'))]);
        flash('success', t('plan_month_reset_done'));
        $back = 'activities.php?month=' . post('month');
    }
    redirect($back);
}

$first = $month . '-01';
$last = date('Y-m-t', strtotime($first));
$plans = plan_range($first, $last);
$leave = day_marks($first, $last)['leave'];
$monthName = date('F Y', strtotime($first));
$prev = date('Y-m', strtotime($first . ' -1 month'));
$next = date('Y-m', strtotime($first . ' +1 month'));
$editDay = $day !== '' ? plan_range($day, $day)[$day] : null;
$customCount = count(array_filter($plans, fn($p) => $p['custom']));

$title = t('daily_activity');
$active = 'activities';
$back = $day !== '' ? 'activities.php?month=' . substr($day, 0, 7) : 'more.php';
require __DIR__ . '/includes/header.php';
?>
<?php if ($editDay !== null): // one date ?>
<form method="post" class="card mb-3" style="max-width:640px"><?= csrf_field() ?><input type="hidden" name="date" value="<?= e($day) ?>">
  <div class="card-header fw-bold"><i class="bi bi-calendar-event text-primary"></i> <?= e(t('day' . date('N', strtotime($day)))) ?>, <?= e(fdate($day)) ?>
    <span class="badge <?= $editDay['custom'] ? 'bg-primary' : 'text-bg-light border' ?> ms-1"><?= e(t($editDay['custom'] ? 'plan_set_for_date' : 'plan_from_week')) ?></span></div>
  <div class="card-body">
    <?php if (isset($leave[$day])): ?><div class="alert alert-danger py-2 small"><i class="bi bi-calendar-x"></i> <?= e(t('gym_leave')) ?>: <?= e($leave[$day]['title']) ?></div><?php endif; ?>
    <?php foreach ($slots as $slot): ?>
      <label class="form-label small mb-0" for="p_<?= $slot ?>"><?= e(t('slot_' . $slot)) ?></label>
      <input class="form-control mb-2" id="p_<?= $slot ?>" name="p[<?= $slot ?>]" maxlength="200" value="<?= e($editDay['plan'][$slot] ?? '') ?>">
    <?php endforeach; ?>
    <div class="form-check mb-3"><input class="form-check-input" type="checkbox" name="same_weekday" value="1" id="sw">
      <label class="form-check-label" for="sw"><?= e(t('plan_same_weekday', t('day' . date('N', strtotime($day))), date('F', strtotime($day)))) ?></label></div>
    <div class="d-grid gap-2">
      <button class="btn btn-primary btn-lg" name="action" value="day"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-secondary flex-fill" name="action" value="rest"><i class="bi bi-moon"></i> <?= e(t('rest_day')) ?></button>
        <?php if ($editDay['custom']): ?><button class="btn btn-outline-secondary flex-fill" name="action" value="reset"><i class="bi bi-arrow-counterclockwise"></i> <?= e(t('plan_use_week')) ?></button><?php endif; ?>
      </div>
    </div>
  </div>
</form>

<?php elseif ($view === 'week'): // standard week (used for dates that are not set) ?>
<ul class="nav nav-pills mb-3">
  <li class="nav-item"><a class="nav-link" href="activities.php"><i class="bi bi-calendar3"></i> <?= e(t('month_plan')) ?></a></li>
  <li class="nav-item"><a class="nav-link active" href="?view=week"><i class="bi bi-calendar-week"></i> <?= e(t('week_plan')) ?></a></li>
</ul>
<p class="small-muted"><?= e(t('week_plan_help')) ?></p>
<?php $week = [];
foreach (q('SELECT day_no, slot, activity FROM activities')->fetchAll() as $r) {
    $week[$r['slot']][(int)$r['day_no']] = $r['activity'];
} ?>
<form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="week">
  <?php for ($d = 1; $d <= 7; $d++): ?>
    <div class="card mb-2"><div class="card-body py-2">
      <div class="fw-bold mb-1"><?= e(t('day' . $d)) ?></div>
      <div class="row g-2">
        <?php foreach ($slots as $slot): ?>
          <div class="col-md"><input class="form-control form-control-sm" name="a[<?= $slot ?>][<?= $d ?>]" maxlength="200" value="<?= e($week[$slot][$d] ?? '') ?>" placeholder="<?= e(t('slot_' . $slot)) ?>" aria-label="<?= e(t('slot_' . $slot)) ?>"></div>
        <?php endforeach; ?>
      </div>
    </div></div>
  <?php endfor; ?>
  <button class="btn btn-primary btn-lg w-100 mt-2 mb-4"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
</form>

<?php else: // month ?>
<ul class="nav nav-pills mb-3">
  <li class="nav-item"><a class="nav-link active" href="activities.php"><i class="bi bi-calendar3"></i> <?= e(t('month_plan')) ?></a></li>
  <li class="nav-item"><a class="nav-link" href="?view=week"><i class="bi bi-calendar-week"></i> <?= e(t('week_plan')) ?></a></li>
</ul>
<div class="card mb-3">
  <div class="card-header d-flex flex-wrap gap-2 align-items-center">
    <a href="?month=<?= $prev ?>" class="btn btn-sm btn-light" aria-label="<?= e(t('back')) ?>"><i class="bi bi-chevron-left"></i></a>
    <span class="fs-5 fw-bold"><?= e($monthName) ?></span>
    <a href="?month=<?= $next ?>" class="btn btn-sm btn-light me-auto" aria-label="Next"><i class="bi bi-chevron-right"></i></a>
    <?php require __DIR__ . '/includes/export_buttons.php'; ?>
  </div>
  <div class="card-body py-2 small-muted"><?= e(t('month_plan_help')) ?></div>
  <div class="table-responsive d-none d-lg-block d-print-block">
    <table class="table table-bordered week-table mb-0" id="reportTable" data-title="Valley daily - <?= e($monthName) ?>" data-landscape="1">
      <thead><tr><th data-en="Date"><?= e(t('date')) ?></th>
        <?php foreach ($slots as $slot): ?><th data-en="<?= e(t_en('slot_' . $slot)) ?>"><?= e(t('slot_' . $slot)) ?></th><?php endforeach; ?><th class="no-export"></th></tr></thead>
      <tbody>
      <?php foreach ($plans as $d => $p): $isLeave = isset($leave[$d]); ?>
        <tr class="<?= $d === today() ? 'today-row' : '' ?>"><th class="text-nowrap" data-en="<?= e(date('d-m D', strtotime($d))) ?>"><?= e(date('d', strtotime($d))) ?> <?= e(mb_substr(t('day' . date('N', strtotime($d))), 0, 3)) ?></th>
          <?php if ($isLeave): ?><td colspan="5" class="text-danger" data-en="Gym leave"><?= e(t('gym_leave')) ?>: <?= e($leave[$d]['title']) ?></td>
          <?php elseif (!$p['plan']): ?><td colspan="5" class="text-muted" data-en="Rest day"><?= e(t('rest_day')) ?></td>
          <?php else: foreach ($slots as $slot): ?><td><?= e($p['plan'][$slot] ?? '') ?></td><?php endforeach; endif; ?>
          <td class="no-export text-nowrap"><a href="?day=<?= $d ?>" class="btn btn-sm btn-light" aria-label="<?= e(t('edit')) ?>"><i class="bi bi-pencil"></i></a><?= $p['custom'] ? ' <i class="bi bi-dot text-primary fs-4 align-middle" title="' . e(t('plan_set_for_date')) . '"></i>' : '' ?></td></tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
</div>
<div class="d-lg-none d-print-none">
  <?php foreach ($plans as $d => $p): $isLeave = isset($leave[$d]); ?>
    <a href="?day=<?= $d ?>" id="d<?= $d ?>" class="card mb-2 text-decoration-none text-reset<?= $d === today() ? ' border border-primary' : '' ?>"><div class="card-body py-2 d-flex gap-3">
      <div class="plan-date<?= $d === today() ? ' on' : '' ?>"><b><?= e(date('d', strtotime($d))) ?></b><span><?= e(mb_substr(t('day' . date('N', strtotime($d))), 0, 3)) ?></span></div>
      <div class="me-auto small">
        <?php if ($isLeave): ?><div class="text-danger fw-semibold"><i class="bi bi-calendar-x"></i> <?= e($leave[$d]['title']) ?></div>
        <?php elseif (!$p['plan']): ?><div class="text-muted"><?= e(t('rest_day')) ?></div>
        <?php else: foreach ($slots as $slot): if (!isset($p['plan'][$slot])) continue; ?>
          <div><span class="small-muted"><?= e(t('slot_' . $slot)) ?>:</span> <?= e($p['plan'][$slot]) ?></div>
        <?php endforeach; endif; ?>
      </div>
      <div class="text-nowrap"><?= $p['custom'] ? '<span class="badge bg-primary">' . e(t('plan_set_short')) . '</span> ' : '' ?><i class="bi bi-pencil text-muted"></i></div>
    </div></a>
  <?php endforeach; ?>
</div>
<?php if ($customCount): ?>
  <form method="post" class="text-end my-3 d-print-none" data-verify="<?= e(t('plan_month_reset_confirm', $monthName)) ?>"><?= csrf_field() ?>
    <input type="hidden" name="action" value="reset_month"><input type="hidden" name="month" value="<?= e($month) ?>">
    <button class="btn btn-sm btn-outline-danger"><i class="bi bi-arrow-counterclockwise"></i> <?= e(t('plan_month_reset')) ?></button></form>
<?php endif; ?>
<?php endif; ?>
<?php
$scripts = ['assets/vendor/jspdf.umd.min.js', 'assets/vendor/jspdf.plugin.autotable.min.js'];
require __DIR__ . '/includes/footer.php';
