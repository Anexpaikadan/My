<?php
// Monthly attendance: one row per member, one column per day, with totals. Export to PDF / Excel / print.

require __DIR__ . '/includes/init.php';
require_admin();

$month = preg_match('/^\d{4}-\d{2}$/', get('month')) ? get('month') : date('Y-m');
$first = $month . '-01';
$daysIn = (int)date('t', strtotime($first));
$last = $month . '-' . $daysIn;
$memberId = (int)get('member');
$who = get('who', 'all');

$where = $memberId ? 'WHERE m.id = ?' : ($who === 'active' ? 'WHERE m.status = \'active\' AND m.expiry_date >= ?' : 'WHERE (m.expiry_date >= ? OR m.id IN (SELECT member_id FROM attendance WHERE att_date BETWEEN ? AND ?))');
$args = $memberId ? [$memberId] : ($who === 'active' ? [$first] : [$first, $first, $last]);
$members = q("SELECT m.id, m.name, m.adm_no FROM members m $where ORDER BY m.name", $args)->fetchAll();
$grid = [];
foreach (q('SELECT member_id, DAY(att_date) d FROM attendance WHERE att_date BETWEEN ? AND ?', [$first, $last])->fetchAll() as $r) {
    $grid[(int)$r['member_id']][(int)$r['d']] = true;
}
$perDay = array_fill(1, $daysIn, 0);
foreach ($members as $m) {
    foreach ($grid[$m['id']] ?? [] as $d => $_) {
        $perDay[$d]++;
    }
}
$marks = day_marks($first, $last);
$leaveDay = fn(int $d) => isset($marks['leave'][sprintf('%s-%02d', $month, $d)]);
$monthName = date('F Y', strtotime($first));

$title = t('monthly_attendance');
$active = 'attendance';
$back = 'attendance.php';
$actions = '<a href="attendance.php" class="btn btn-outline-primary"><i class="bi bi-qr-code"></i> ' . e(t('attendance')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<form class="card card-body mb-3 filters" method="get">
  <div class="row g-2">
    <div class="col-6 col-md-3"><input class="form-control" type="month" name="month" value="<?= e($month) ?>" onchange="this.form.submit()"></div>
    <div class="col-6 col-md-3"><select class="form-select" name="who" onchange="this.form.submit()">
      <option value="all"<?= $who === 'all' ? ' selected' : '' ?>><?= e(t('all_members')) ?></option>
      <option value="active"<?= $who === 'active' ? ' selected' : '' ?>><?= e(t('active_members')) ?></option></select></div>
    <?php if ($memberId): ?><div class="col-12 col-md-3"><a class="btn btn-light w-100" href="?month=<?= e($month) ?>"><?= e(t('show_all')) ?></a></div><?php endif; ?>
  </div>
</form>
<div class="card">
  <div class="card-header d-flex flex-wrap gap-2 align-items-center">
    <span class="me-auto"><?= e($monthName) ?> · <?= count($members) ?> <?= e(t('members')) ?></span>
    <?php require __DIR__ . '/includes/export_buttons.php'; ?>
  </div>
  <div class="table-responsive">
    <table class="table table-bordered att-grid mb-0" id="reportTable" data-title="Attendance <?= e($monthName) ?>" data-landscape="1">
      <thead><tr><th class="sticky" data-en="Member"><?= e(t('member')) ?></th>
        <?php for ($d = 1; $d <= $daysIn; $d++): $we = date('N', strtotime("$month-$d")) == 7; ?><th class="<?= $leaveDay($d) ? 'l' : ($we ? 'we' : '') ?>"<?= $leaveDay($d) ? ' title="' . e($marks['leave'][sprintf('%s-%02d', $month, $d)]['title']) . '"' : '' ?>><?= $d ?></th><?php endfor; ?>
        <th data-en="Days"><?= e(t('days')) ?></th></tr></thead>
      <tbody>
      <?php foreach ($members as $m): $cnt = count($grid[$m['id']] ?? []); ?>
        <tr><td class="sticky"><a href="member_view.php?id=<?= $m['id'] ?>"><?= e($m['name']) ?></a></td>
          <?php for ($d = 1; $d <= $daysIn; $d++): $on = isset($grid[$m['id']][$d]); $we = date('N', strtotime("$month-$d")) == 7;
            $lv = !$on && $leaveDay($d); $fz = !$on && !$lv && isset($marks['freeze'][$m['id']][sprintf('%s-%02d', $month, $d)]); ?>
            <td class="<?= $on ? 'p' : ($lv ? 'l' : ($fz ? 'f' : ($we ? 'we' : ''))) ?>"<?= $on ? ' data-en="P"' : '' ?>><?= $on ? '✓' : ($lv ? 'L' : ($fz ? 'F' : '')) ?></td>
          <?php endfor; ?>
          <td class="fw-bold"><?= $cnt ?></td></tr>
      <?php endforeach; ?>
      </tbody>
      <tfoot><tr class="fw-bold"><td class="sticky" data-en="Present"><?= e(t('present')) ?></td>
        <?php for ($d = 1; $d <= $daysIn; $d++): ?><td><?= $perDay[$d] ?: '' ?></td><?php endfor; ?>
        <td><?= array_sum($perDay) ?></td></tr></tfoot>
    </table>
  </div>
  <div class="card-footer cal-legend"><span><i class="p"></i>✓ <?= e(t('present')) ?></span><span><i class="l"></i>L <?= e(t('gym_leave')) ?></span>
    <span><i class="f"></i>F <?= e(t('frozen')) ?></span><a href="leaves.php?month=<?= e($month) ?>" class="ms-auto small"><i class="bi bi-calendar-x"></i> <?= e(t('gym_leaves')) ?></a></div>
</div>
<?php
$scripts = ['assets/vendor/jspdf.umd.min.js', 'assets/vendor/jspdf.plugin.autotable.min.js'];
require __DIR__ . '/includes/footer.php';
