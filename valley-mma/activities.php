<?php
// Daily activity ("Valley daily"): weekly training plan – warm-up, primary, secondary, finisher, cool-down.

require __DIR__ . '/includes/init.php';
require_admin();

$slots = ['warmup', 'primary', 'secondary', 'finisher', 'cooldown'];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    foreach ($slots as $slot) {
        for ($d = 1; $d <= 7; $d++) {
            q('INSERT INTO activities (day_no, slot, activity) VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE activity = VALUES(activity)',
                [$d, $slot, mb_substr(trim((string)($_POST['a'][$slot][$d] ?? '')), 0, 200)]);
        }
    }
    flash('success', t('saved'));
    redirect('activities.php');
}
$week = [];
foreach (q('SELECT day_no, slot, activity FROM activities')->fetchAll() as $r) {
    $week[$r['slot']][(int)$r['day_no']] = $r['activity'];
}
$today = (int)date('N');
$edit = get('edit') === '1';

$title = t('daily_activity');
$active = 'activities';
$back = 'more.php';
$actions = $edit ? '' : '<a href="?edit=1" class="btn btn-primary"><i class="bi bi-pencil"></i> ' . e(t('edit')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<?php if ($edit): ?><form method="post"><?= csrf_field() ?><?php endif; ?>
<div class="card">
  <div class="card-header d-flex flex-wrap gap-2 align-items-center">
    <span class="me-auto fs-5 fw-bold"><?= e(setting('gym_name', 'Valley')) ?> – <?= e(t('week_plan')) ?></span>
    <?php if (!$edit) require __DIR__ . '/includes/export_buttons.php'; ?>
  </div>
  <div class="table-responsive<?= $edit ? '' : ' d-none d-lg-block d-print-block' ?>">
    <table class="table table-bordered week-table mb-0" id="reportTable" data-title="Valley daily - weekly training plan" data-landscape="1">
      <thead><tr><th></th>
        <?php for ($d = 1; $d <= 7; $d++): ?><th class="<?= $d === $today ? 'today-col' : '' ?>" data-en="<?= e(t_en('day' . $d)) ?>"><?= e(t('day' . $d)) ?></th><?php endfor; ?>
      </tr></thead>
      <tbody>
      <?php foreach ($slots as $slot): ?>
        <tr><th class="text-nowrap" data-en="<?= e(t_en('slot_' . $slot)) ?>"><?= e(t('slot_' . $slot)) ?></th>
          <?php for ($d = 1; $d <= 7; $d++): $v = $week[$slot][$d] ?? ''; ?>
            <td class="<?= $d === $today ? 'today-col' : '' ?>">
              <?php if ($edit): ?><textarea class="form-control form-control-sm" rows="2" name="a[<?= $slot ?>][<?= $d ?>]" maxlength="200"><?= e($v) ?></textarea>
              <?php else: ?><?= e($v) ?><?php endif; ?>
            </td>
          <?php endfor; ?>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
</div>
<?php if ($edit): ?>
  <div class="d-flex gap-2 mt-3"><button class="btn btn-primary btn-lg"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
    <a href="activities.php" class="btn btn-light btn-lg"><?= e(t('cancel')) ?></a></div>
</form>
<?php endif; ?>
<?php if (!$edit): ?>
<div class="mt-3 d-lg-none d-print-none">
  <?php for ($d = 1; $d <= 7; $d++): ?>
    <div class="card mb-2<?= $d === $today ? ' border border-primary' : '' ?>"><div class="card-body py-2">
      <div class="fw-bold mb-1"><?= e(t('day' . $d)) ?><?= $d === $today ? ' · <span class="text-primary">' . e(t('today')) . '</span>' : '' ?></div>
      <?php $any = false; foreach ($slots as $slot): if (($week[$slot][$d] ?? '') === '') continue; $any = true; ?>
        <div class="small"><span class="small-muted"><?= e(t('slot_' . $slot)) ?>:</span> <?= e($week[$slot][$d]) ?></div>
      <?php endforeach; if (!$any): ?><div class="small text-muted"><?= e(t('rest_day')) ?></div><?php endif; ?>
    </div></div>
  <?php endfor; ?>
</div>
<?php endif; ?>
<?php
$scripts = ['assets/vendor/jspdf.umd.min.js', 'assets/vendor/jspdf.plugin.autotable.min.js'];
require __DIR__ . '/includes/footer.php';
