<?php
// Member app: the training plan of the month (this month and the next), set by the gym.

require __DIR__ . '/includes/init.php';

$m = member_user();
if (!$m) {
    redirect('me.php');
}
$month = get('month') === date('Y-m', strtotime('first day of next month')) ? get('month') : date('Y-m');
$isNext = $month !== date('Y-m');
$first = $month . '-01';
$last = date('Y-m-t', strtotime($first));
$plans = plan_range($first, $last);
$leave = day_marks($first, $last)['leave'];
$show = get('show') === 'list' ? 'list' : 'table';
$mq = $isNext ? 'month=' . $month . '&' : '';

$title = t('month_plan');
$bare = true;
$memberApp = true;
$publicPage = 'login';
require __DIR__ . '/includes/header.php';
?>
<div class="d-flex align-items-center gap-2 mb-3 pt-2">
  <a href="me.php" class="btn btn-light btn-back" aria-label="<?= e(t('back')) ?>"><i class="bi bi-arrow-left"></i></a>
  <h1 class="h5 mb-0 me-auto"><?= e(t('month_plan')) ?></h1>
</div>
<div class="btn-group w-100 mb-2">
  <a href="me_plan.php?show=<?= $show ?>" class="btn <?= $isNext ? 'btn-outline-primary' : 'btn-primary' ?>"><?= e(date('F')) ?></a>
  <a href="?month=<?= e(date('Y-m', strtotime('first day of next month'))) ?>&show=<?= $show ?>" class="btn <?= $isNext ? 'btn-primary' : 'btn-outline-primary' ?>"><?= e(date('F', strtotime('first day of next month'))) ?></a>
</div>
<div class="btn-group btn-group-sm w-100 mb-3">
  <a href="?<?= e($mq) ?>show=table" class="btn <?= $show === 'table' ? 'btn-dark' : 'btn-outline-dark' ?>"><i class="bi bi-calendar3"></i> <?= e(t('timetable')) ?></a>
  <a href="?<?= e($mq) ?>show=list" class="btn <?= $show === 'list' ? 'btn-dark' : 'btn-outline-dark' ?>"><i class="bi bi-list-ul"></i> <?= e(t('list')) ?></a>
</div>
<?php if ($show === 'table'): ?>
  <div class="card mb-3"><?= plan_timetable($month, $plans, $leave) ?></div>
  <p class="small-muted text-center"><i class="bi bi-arrows-move"></i> <?= e(t('timetable_scroll')) ?></p>
<?php endif; ?>
<?php foreach ($show === 'table' ? [] : $plans as $d => $p): if (!$isNext && $d < today()) continue; $isLeave = isset($leave[$d]); ?>
  <div class="card mb-2<?= $d === today() ? ' border border-primary' : '' ?>"><div class="card-body py-2 d-flex gap-3">
    <div class="plan-date<?= $d === today() ? ' on' : '' ?>"><b><?= e(date('d', strtotime($d))) ?></b><span><?= e(mb_substr(t('day' . date('N', strtotime($d))), 0, 3)) ?></span></div>
    <div class="small">
      <?php if ($d === today()): ?><div class="text-primary fw-bold"><?= e(t('today')) ?></div><?php endif; ?>
      <?php if ($isLeave): ?><div class="text-danger fw-semibold"><i class="bi bi-calendar-x"></i> <?= e(t('gym_leave')) ?>: <?= e($leave[$d]['title']) ?></div>
      <?php elseif (!$p['plan']): ?><div class="text-muted"><?= e(t('rest_day')) ?></div>
      <?php else: foreach (PLAN_SLOTS as $slot): if (!isset($p['plan'][$slot])) continue; ?>
        <div><span class="small-muted"><?= e(t('slot_' . $slot)) ?>:</span> <b><?= e($p['plan'][$slot]) ?></b></div>
      <?php endforeach; endif; ?>
    </div>
  </div></div>
<?php endforeach; ?>
<?php require __DIR__ . '/includes/footer.php';
