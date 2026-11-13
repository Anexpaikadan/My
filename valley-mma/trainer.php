<?php
// Trainer home: today's classes, the coming classes, my batches with their students, my password.

require __DIR__ . '/includes/init.php';
$me = require_admin();
if (!is_trainer()) {
    redirect('trainers.php');
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && post('action') === 'password') {
    $row = q('SELECT password_hash FROM admins WHERE id = ?', [$me['id']])->fetch();
    $new = (string)($_POST['new_password'] ?? '');
    if (!password_verify((string)($_POST['old_password'] ?? ''), $row['password_hash'])) {
        flash('danger', t('old_password_wrong'));
    } elseif (strlen($new) < 6) {
        flash('danger', t('err_admin_password'));
    } else {
        q('UPDATE admins SET password_hash = ? WHERE id = ?', [password_hash($new, PASSWORD_DEFAULT), $me['id']]);
        flash('success', t('password_changed'));
    }
    redirect('trainer.php');
}

$today = today();
$todayClasses = class_sessions($today, $today, (int)$me['id'])[$today] ?? [];
$coming = class_sessions(date('Y-m-d', strtotime('+1 day')), date('Y-m-d', strtotime('+7 day')), (int)$me['id']);
$myBatches = array_values(array_filter(batches(), fn($b) => (int)$b['trainer_id'] === (int)$me['id']));
$monthCount = (int)q("SELECT COUNT(*) FROM class_sessions WHERE trainer_id = ? AND status = 'on' AND class_date BETWEEN ? AND ?", [$me['id'], date('Y-m-01'), date('Y-m-t')])->fetchColumn();
$plan = day_plan($today);

$title = t('my_classes');
$active = 'trainer';
require __DIR__ . '/includes/header.php';
?>
<div class="hello card mb-3"><div class="card-body d-flex align-items-center gap-3">
  <div class="me-auto"><div class="small opacity-75"><?= e(t('day' . date('N'))) ?>, <?= e(fdate($today)) ?></div>
    <div class="fs-5 fw-bold"><?= e(t('hello_admin', $me['full_name'] !== '' ? $me['full_name'] : $me['username'])) ?></div>
    <div class="small opacity-75"><?= e(t('trainer')) ?> · <?= $monthCount ?> <?= e(t('classes_this_month')) ?></div></div>
  <?php if (trainer_can('attendance')): ?><a href="attendance.php" class="btn btn-accent btn-lg d-none d-sm-inline-flex align-items-center gap-2"><i class="bi bi-qr-code"></i> <?= e(t('attendance')) ?></a><?php endif; ?>
</div></div>

<h2 class="section-head"><?= e(t('classes_today')) ?></h2>
<?php if (!$todayClasses): ?><div class="card card-body text-muted mb-3"><?= e(t('no_classes_today')) ?></div><?php endif; ?>
<?php foreach ($todayClasses as $c): $students = class_students((int)$c['batch_id'], $today); $present = count(array_filter($students, fn($s) => $s['check_in'])); ?>
  <a href="timetable.php?day=<?= e($today) ?>#c<?= $c['id'] ?>" class="card mb-2 text-decoration-none text-reset batch-card<?= $c['status'] === 'off' ? ' opacity-50' : '' ?>"><div class="card-body d-flex align-items-center gap-3">
    <span class="batch-ico"><i class="bi bi-clock-history"></i></span>
    <div class="me-auto"><div class="fw-bold"><?= e($c['batch_name']) ?></div><div class="small"><?= e(time_text($c['start_time']) . ' – ' . time_text($c['end_time'])) ?><?= $c['note'] !== '' ? ' · ' . e($c['note']) : '' ?></div></div>
    <?php if ($c['status'] === 'off'): ?><span class="badge bg-secondary"><?= e(t('tt_off')) ?></span><?php else: ?><span class="badge bg-success fs-6"><?= $present ?> / <?= count($students) ?></span><?php endif; ?>
    <i class="bi bi-chevron-right text-muted"></i>
  </div></a>
<?php endforeach; ?>

<?php if ($plan): ?>
<div class="card mb-3 mt-3"><div class="card-header"><i class="bi bi-lightning-charge-fill text-primary"></i> <?= e(t('todays_training')) ?></div>
  <div class="card-body py-2">
    <?php foreach (PLAN_SLOTS as $slot): if (!isset($plan[$slot])) continue; ?>
      <div class="d-flex py-1 border-bottom"><span class="small-muted flex-shrink-0" style="width:8.5rem"><?= e(t('slot_' . $slot)) ?></span><span class="fw-semibold"><?= e($plan[$slot]) ?></span></div>
    <?php endforeach; ?>
  </div></div>
<?php endif; ?>

<h2 class="section-head mt-4"><?= e(t('classes_next_days')) ?></h2>
<div class="card mb-3"><div class="list-group list-group-flush">
  <?php if (!$coming): ?><div class="list-group-item text-muted"><?= e(t('tt_no_classes')) ?></div><?php endif; ?>
  <?php foreach ($coming as $d => $rows): foreach ($rows as $c): if ($c['status'] === 'off') continue; ?>
    <a href="timetable.php?day=<?= e($d) ?>" class="list-group-item list-group-item-action d-flex align-items-center gap-3">
      <span class="plan-date"><b><?= e(date('d', strtotime($d))) ?></b><span><?= e(mb_substr(t('day' . date('N', strtotime($d))), 0, 3)) ?></span></span>
      <span class="me-auto"><span class="fw-semibold d-block"><?= e($c['batch_name']) ?></span><span class="small-muted"><?= e(time_text($c['start_time']) . ' – ' . time_text($c['end_time'])) ?></span></span>
      <i class="bi bi-chevron-right text-muted"></i></a>
  <?php endforeach; endforeach; ?>
</div></div>
<a href="timetable.php" class="btn btn-outline-primary w-100 mb-4"><i class="bi bi-calendar3"></i> <?= e(t('class_timetable')) ?></a>

<?php if ($myBatches): ?>
<h2 class="section-head"><?= e(t('my_batches')) ?></h2>
<?php foreach ($myBatches as $b): $students = class_students((int)$b['id'], $today); ?>
  <div class="card mb-2"><div class="card-header d-flex align-items-center gap-2" data-bs-toggle="collapse" data-bs-target="#mb<?= $b['id'] ?>" role="button">
    <span class="me-auto"><b><?= e($b['name']) ?></b><span class="d-block small fw-normal"><?= e(batch_time($b)) ?> · <?= e(batch_days($b)) ?></span></span>
    <span class="badge text-bg-light border"><i class="bi bi-people"></i> <?= count($students) ?></span><i class="bi bi-chevron-down"></i></div>
    <div class="collapse" id="mb<?= $b['id'] ?>"><div class="list-group list-group-flush">
      <?php foreach ($students as $s): ?>
        <div class="list-group-item d-flex align-items-center gap-2"><img src="<?= e(photo_url($s)) ?>" class="avatar" alt="" loading="lazy">
          <span class="me-auto"><span class="fw-semibold d-block"><?= e($s['name']) ?></span><span class="small-muted"><?= e($s['adm_no']) ?> <?= level_badge(level_by_id($s['level_id'] !== null ? (int)$s['level_id'] : null)) ?></span></span>
          <?php if (trainer_can('contact')): ?>
            <a class="btn btn-sm btn-light" href="tel:<?= e(clean_phone($s['phone'])) ?>" aria-label="<?= e(t('call')) ?>"><i class="bi bi-telephone-fill"></i></a>
            <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link($s['phone'], t('wa_hello_short', $s['name']))) ?>" aria-label="WhatsApp"><i class="bi bi-whatsapp"></i></a>
          <?php endif; ?></div>
      <?php endforeach; ?>
      <?php if (!$students): ?><div class="list-group-item small-muted"><?= e(t('tt_no_students')) ?></div><?php endif; ?>
    </div></div></div>
<?php endforeach; ?>
<?php endif; ?>

<details class="card my-4"><summary class="card-header"><i class="bi bi-key"></i> <?= e(t('change_password')) ?></summary>
  <form method="post" class="card-body"><?= csrf_field() ?><input type="hidden" name="action" value="password">
    <input class="form-control mb-2" type="password" name="old_password" placeholder="<?= e(t('old_password')) ?>" autocomplete="current-password" required>
    <input class="form-control mb-2" type="password" name="new_password" placeholder="<?= e(t('new_password')) ?>" autocomplete="new-password" minlength="6" required>
    <button class="btn btn-primary w-100"><?= e(t('save')) ?></button>
  </form></details>
<?php require __DIR__ . '/includes/footer.php';
