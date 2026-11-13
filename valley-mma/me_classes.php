<?php
// Member app: my class timetable – the classes of my batch this month and next, with trainer and holidays.

require __DIR__ . '/includes/init.php';

$m = member_user();
if (!$m) {
    redirect('me.php');
}
$batch = batch_by_id($m['batch_id'] !== null ? (int)$m['batch_id'] : null);
$nextMonth = date('Y-m', strtotime('first day of next month'));
$month = get('month') === $nextMonth ? $nextMonth : date('Y-m');
$first = $month . '-01';
$last = date('Y-m-t', strtotime($first));
$tm = timetable_month($month);
$sessions = $batch ? class_sessions($first, $last, null, (int)$batch['id']) : [];
$leave = day_marks($first, $last)['leave'];

$title = t('class_timetable');
$bare = true;
$memberApp = true;
$publicPage = 'login';
require __DIR__ . '/includes/header.php';
?>
<div class="d-flex align-items-center gap-2 mb-3 pt-2">
  <a href="me.php" class="btn btn-light btn-back" aria-label="<?= e(t('back')) ?>"><i class="bi bi-arrow-left"></i></a>
  <h1 class="h5 mb-0 me-auto"><?= e(t('class_timetable')) ?></h1>
</div>
<?php if (!$batch): ?>
  <div class="card card-body text-muted"><?= e(t('no_batch_member')) ?></div>
<?php else: ?>
  <div class="card mb-3"><div class="card-body d-flex align-items-center gap-3">
    <span class="batch-ico"><i class="bi bi-clock-history"></i></span>
    <div><div class="fw-bold"><?= e($batch['name']) ?></div><div class="small"><?= e(batch_time($batch)) ?> · <?= e(batch_days($batch)) ?></div></div>
  </div></div>
  <div class="btn-group w-100 mb-3">
    <a href="me_classes.php" class="btn <?= $month === $nextMonth ? 'btn-outline-primary' : 'btn-primary' ?>"><?= e(date('F')) ?></a>
    <a href="?month=<?= e($nextMonth) ?>" class="btn <?= $month === $nextMonth ? 'btn-primary' : 'btn-outline-primary' ?>"><?= e(date('F', strtotime($nextMonth . '-01'))) ?></a>
  </div>
  <?php if (!$tm): ?>
    <div class="card card-body text-center text-muted"><i class="bi bi-calendar-plus fs-1"></i><div class="mt-2"><?= e(t('tt_not_made_trainer', date('F Y', strtotime($first)))) ?></div></div>
  <?php else: ?>
    <div class="card mb-2"><?= class_timetable_html($month, $sessions, (string)$tm['holidays'], $leave) ?></div>
    <p class="small-muted text-center"><i class="bi bi-arrows-move"></i> <?= e(t('timetable_scroll')) ?></p>
    <h2 class="section-head mt-3"><?= e(t('classes_next_days')) ?></h2>
    <div class="card mb-3"><div class="list-group list-group-flush">
      <?php $n = 0; foreach ($sessions as $d => $rows): foreach ($rows as $c): if ($d < today() || $c['status'] === 'off' || $n >= 8) continue; $n++; ?>
        <div class="list-group-item d-flex align-items-center gap-3">
          <span class="plan-date<?= $d === today() ? ' on' : '' ?>"><b><?= e(date('d', strtotime($d))) ?></b><span><?= e(mb_substr(t('day' . date('N', strtotime($d))), 0, 3)) ?></span></span>
          <span class="me-auto"><span class="fw-semibold d-block"><?= e(time_text($c['start_time']) . ' – ' . time_text($c['end_time'])) ?></span>
            <span class="small-muted"><i class="bi bi-person-badge"></i> <?= e(trainer_name($c['trainer_id'] !== null ? (int)$c['trainer_id'] : null) ?: '–') ?><?= $c['note'] !== '' ? ' · ' . e($c['note']) : '' ?></span></span>
        </div>
      <?php endforeach; endforeach; if (!$n): ?><div class="list-group-item text-muted"><?= e(t('tt_no_classes')) ?></div><?php endif; ?>
    </div></div>
  <?php endif; ?>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
