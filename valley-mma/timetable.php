<?php
// Class timetable: a new timetable for every month, made from the batches. The admin picks the weekly
// holidays (e.g. Saturday and Sunday), sets the trainer of each class and can switch a class off or add
// one. Every class shows its students. Trainers see their own classes (all classes with that right).

require __DIR__ . '/includes/init.php';
$me = require_admin();
$isAdmin = !is_trainer();
$onlyMine = !$isAdmin && !trainer_can('all_classes');

$month = preg_match('/^\d{4}-\d{2}$/', get('month')) ? get('month') : date('Y-m');
$day = valid_date(get('day')) ? get('day') : '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!$isAdmin) { // trainers only look
        redirect('timetable.php');
    }
    $action = post('action');
    if ($action === 'create' && preg_match('/^\d{4}-\d{2}$/', post('month'))) {
        $m = post('month');
        if (timetable_month($m)) { // making it again replaces the classes of that month
            require_verify('timetable.php?month=' . $m);
        }
        $hol = implode('', array_intersect(['1', '2', '3', '4', '5', '6', '7'], (array)($_POST['holidays'] ?? [])));
        $n = timetable_create($m, $hol);
        set_setting('tt_holidays', $hol);
        flash('success', t('tt_created', date('F Y', strtotime($m . '-01')), $n));
        redirect('timetable.php?month=' . $m);
    }
    $date = valid_date(post('date')) ? post('date') : '';
    $back = 'timetable.php?day=' . $date;
    if ($action === 'class' && $date !== '') { // trainer / on-off / note of one class
        $s = q('SELECT * FROM class_sessions WHERE id = ?', [(int)post('id')])->fetch();
        if ($s) {
            $tid = (int)post('trainer_id') ?: null;
            if ($tid && trainer_name($tid) === '') {
                $tid = null;
            }
            $status = post('status') === 'off' ? 'off' : 'on';
            q('UPDATE class_sessions SET trainer_id = ?, status = ?, note = ? WHERE id = ?', [$tid, $status, mb_substr(trim(post('note')), 0, 200), $s['id']]);
            if (post('rest_of_month') === '1') { // same trainer for the later classes of this batch in the month
                q('UPDATE class_sessions SET trainer_id = ? WHERE batch_id = ? AND class_date > ? AND class_date <= ?',
                    [$tid, $s['batch_id'], $s['class_date'], date('Y-m-t', strtotime($s['class_date']))]);
            }
            flash('success', t('saved'));
        }
    } elseif ($action === 'add' && $date !== '') { // extra class
        $b = batch_by_id((int)post('batch_id'));
        if ($b) {
            q("INSERT INTO class_sessions (class_date, batch_id, trainer_id) VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE status = 'on'", [$date, $b['id'], $b['trainer_id'] ?: null]);
            flash('success', t('saved'));
        }
    } elseif ($action === 'remove' && $date !== '') {
        q('DELETE FROM class_sessions WHERE id = ? AND class_date = ?', [(int)post('id'), $date]);
        flash('success', t('removed'));
    } elseif ($action === 'day_off' && $date !== '') { // holiday for the whole day
        q("UPDATE class_sessions SET status = 'off' WHERE class_date = ?", [$date]);
        flash('success', t('saved'));
    }
    redirect($back);
}

$first = $month . '-01';
$last = date('Y-m-t', strtotime($first));
$tm = timetable_month($month);
$holidays = $tm['holidays'] ?? '';
$trainerF = $isAdmin ? ((int)get('trainer') ?: null) : ($onlyMine ? (int)$me['id'] : null);
$sessions = class_sessions($first, $last, $trainerF);
$leave = day_marks($first, $last)['leave'];
$monthName = date('F Y', strtotime($first));
$defHol = setting('tt_holidays', '7');

$title = t('class_timetable');
$active = 'timetable';
$back = $day !== '' ? 'timetable.php?month=' . substr($day, 0, 7) : ($isAdmin ? 'more.php' : 'trainer.php');
require __DIR__ . '/includes/header.php';
?>
<?php if ($day !== ''): // classes of one date
    $rows = class_sessions($day, $day, $onlyMine ? (int)$me['id'] : null)[$day] ?? [];
    $dayLeave = day_marks($day, $day)['leave'][$day] ?? null;
    $have = array_column($rows, 'batch_id');
?>
  <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
    <a href="?day=<?= date('Y-m-d', strtotime($day . ' -1 day')) ?>" class="btn btn-sm btn-light" aria-label="<?= e(t('back')) ?>"><i class="bi bi-chevron-left"></i></a>
    <span class="fs-5 fw-bold"><?= e(t('day' . date('N', strtotime($day)))) ?>, <?= e(fdate($day)) ?></span>
    <a href="?day=<?= date('Y-m-d', strtotime($day . ' +1 day')) ?>" class="btn btn-sm btn-light me-auto" aria-label="Next"><i class="bi bi-chevron-right"></i></a>
    <?php if ($isAdmin && array_filter($rows, fn($r) => $r['status'] === 'on')): ?>
      <form method="post" onsubmit="return confirm(<?= e(json_encode(t('tt_day_off_confirm'))) ?>)"><?= csrf_field() ?><input type="hidden" name="action" value="day_off"><input type="hidden" name="date" value="<?= e($day) ?>">
        <button class="btn btn-sm btn-outline-secondary"><i class="bi bi-moon"></i> <?= e(t('tt_day_off')) ?></button></form>
    <?php endif; ?>
  </div>
  <?php if ($dayLeave): ?><div class="alert alert-danger"><i class="bi bi-calendar-x"></i> <?= e(t('gym_leave')) ?>: <?= e($dayLeave['title']) ?></div><?php endif; ?>
  <?php if (!$rows): ?><div class="card card-body text-muted mb-3"><?= e(t('tt_no_classes')) ?></div><?php endif; ?>
  <?php foreach ($rows as $r): $students = class_students((int)$r['batch_id'], $day); $present = count(array_filter($students, fn($s) => $s['check_in']));
      $canMark = $day <= today() && $r['status'] === 'on' && trainer_can('attendance') && ($isAdmin || !$onlyMine || (int)$r['trainer_id'] === (int)$me['id']); ?>
    <div class="card mb-3<?= $r['status'] === 'off' ? ' opacity-75' : '' ?>" id="c<?= $r['id'] ?>">
      <div class="card-header d-flex flex-wrap align-items-center gap-2">
        <span class="batch-ico"><i class="bi bi-clock-history"></i></span>
        <div class="me-auto"><div class="fw-bold"><?= e($r['batch_name']) ?></div><div class="small fw-normal"><?= e(time_text($r['start_time']) . ' – ' . time_text($r['end_time'])) ?>
          · <i class="bi bi-person-badge"></i> <?= e(trainer_name($r['trainer_id'] !== null ? (int)$r['trainer_id'] : null) ?: t('no_trainer')) ?></div></div>
        <?php if ($r['status'] === 'off'): ?><span class="badge bg-secondary"><?= e(t('tt_off')) ?></span><?php else: ?><span class="badge bg-success"><?= $present ?> / <?= count($students) ?> <?= e(t('present')) ?></span><?php endif; ?>
      </div>
      <?php if ($r['note'] !== ''): ?><div class="card-body py-2 small border-bottom"><i class="bi bi-sticky"></i> <?= e($r['note']) ?></div><?php endif; ?>
      <?php if ($isAdmin): ?>
      <form method="post" class="card-body border-bottom py-2"><?= csrf_field() ?><input type="hidden" name="action" value="class"><input type="hidden" name="id" value="<?= $r['id'] ?>"><input type="hidden" name="date" value="<?= e($day) ?>">
        <div class="row g-2 align-items-end">
          <div class="col-7 col-md-4"><label class="form-label small mb-0" for="tr<?= $r['id'] ?>"><?= e(t('trainer')) ?></label>
            <select class="form-select form-select-sm" id="tr<?= $r['id'] ?>" name="trainer_id"><option value=""><?= e(t('no_trainer')) ?></option>
              <?php foreach (trainers() as $tr): ?><option value="<?= $tr['id'] ?>"<?= (int)$r['trainer_id'] === (int)$tr['id'] ? ' selected' : '' ?>><?= e($tr['full_name'] ?: $tr['username']) ?></option><?php endforeach; ?></select></div>
          <div class="col-5 col-md-3"><label class="form-label small mb-0" for="st<?= $r['id'] ?>"><?= e(t('status')) ?></label>
            <select class="form-select form-select-sm" id="st<?= $r['id'] ?>" name="status"><option value="on"><?= e(t('tt_on')) ?></option><option value="off"<?= $r['status'] === 'off' ? ' selected' : '' ?>><?= e(t('tt_off')) ?></option></select></div>
          <div class="col-12 col-md-5"><label class="form-label small mb-0" for="nt<?= $r['id'] ?>"><?= e(t('note')) ?></label>
            <input class="form-control form-control-sm" id="nt<?= $r['id'] ?>" name="note" maxlength="200" value="<?= e($r['note']) ?>" placeholder="<?= e(t('tt_note_ph')) ?>"></div>
          <div class="col-12 d-flex flex-wrap align-items-center gap-2">
            <div class="form-check small me-auto"><input class="form-check-input" type="checkbox" name="rest_of_month" value="1" id="rm<?= $r['id'] ?>"><label class="form-check-label" for="rm<?= $r['id'] ?>"><?= e(t('tt_rest_of_month')) ?></label></div>
            <button class="btn btn-sm btn-primary"><i class="bi bi-check2"></i> <?= e(t('save')) ?></button>
            <button class="btn btn-sm btn-outline-danger" name="action" value="remove" aria-label="<?= e(t('delete')) ?>" onclick="return confirm(<?= e(json_encode(t('tt_remove_confirm'))) ?>)"><i class="bi bi-trash"></i></button>
          </div>
        </div>
      </form>
      <?php endif; ?>
      <?php if ($r['status'] === 'on'): ?>
      <form method="post" action="attendance.php"><?= csrf_field() ?><input type="hidden" name="action" value="manual"><input type="hidden" name="date" value="<?= e($day) ?>"><input type="hidden" name="back" value="class">
        <div class="list-group list-group-flush">
          <?php if (!$students): ?><div class="list-group-item small-muted"><?= e(t('tt_no_students')) ?></div><?php endif; ?>
          <?php foreach ($students as $s): ?>
            <label class="list-group-item d-flex align-items-center gap-2">
              <?php if ($canMark): ?><input class="form-check-input fs-5 m-0" type="checkbox" name="members[]" value="<?= $s['id'] ?>"<?= $s['check_in'] ? ' checked disabled' : '' ?>><?php endif; ?>
              <img src="<?= e(photo_url($s)) ?>" class="avatar" alt="" loading="lazy">
              <span class="me-auto"><span class="fw-semibold d-block"><?= e($s['name']) ?></span><span class="small-muted"><?= e($s['adm_no']) ?> <?= level_badge(level_by_id($s['level_id'] !== null ? (int)$s['level_id'] : null)) ?></span></span>
              <?php if ($s['check_in']): ?><span class="badge bg-success"><i class="bi bi-check2"></i> <?= e(substr($s['check_in'], 0, 5)) ?></span><?php endif; ?>
              <?php if (trainer_can('contact')): ?><a class="btn btn-sm btn-light" href="tel:<?= e(clean_phone($s['phone'])) ?>" aria-label="<?= e(t('call')) ?>"><i class="bi bi-telephone-fill"></i></a><?php endif; ?>
              <?php if ($isAdmin): ?><a class="btn btn-sm btn-light" href="member_view.php?id=<?= $s['id'] ?>" aria-label="<?= e(t('member')) ?>"><i class="bi bi-chevron-right"></i></a><?php endif; ?>
            </label>
          <?php endforeach; ?>
        </div>
        <?php if ($canMark && $students && $present < count($students)): ?><div class="card-body py-2"><button class="btn btn-primary w-100"><i class="bi bi-check2-all"></i> <?= e(t('mark_selected')) ?></button></div><?php endif; ?>
      </form>
      <?php endif; ?>
    </div>
  <?php endforeach; ?>
  <?php if ($isAdmin && ($free = array_filter(batches(), fn($b) => !in_array($b['id'], $have)))): ?>
    <form method="post" class="card card-body mb-4"><?= csrf_field() ?><input type="hidden" name="action" value="add"><input type="hidden" name="date" value="<?= e($day) ?>">
      <label class="form-label small" for="addB"><?= e(t('tt_add_class')) ?></label>
      <div class="input-group"><select class="form-select" id="addB" name="batch_id"><?php foreach ($free as $b): ?><option value="<?= $b['id'] ?>"><?= e(batch_label($b)) ?></option><?php endforeach; ?></select>
        <button class="btn btn-outline-primary"><i class="bi bi-plus-lg"></i> <?= e(t('add')) ?></button></div>
    </form>
  <?php endif; ?>

<?php else: // month ?>
  <div class="card mb-3">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center">
      <a href="?month=<?= date('Y-m', strtotime($first . ' -1 month')) ?>" class="btn btn-sm btn-light" aria-label="<?= e(t('back')) ?>"><i class="bi bi-chevron-left"></i></a>
      <span class="fs-5 fw-bold"><?= e($monthName) ?></span>
      <a href="?month=<?= date('Y-m', strtotime($first . ' +1 month')) ?>" class="btn btn-sm btn-light me-auto" aria-label="Next"><i class="bi bi-chevron-right"></i></a>
      <?php if ($isAdmin && trainers()): ?>
        <form method="get" class="d-print-none"><input type="hidden" name="month" value="<?= e($month) ?>">
          <select class="form-select form-select-sm" name="trainer" onchange="this.form.submit()" aria-label="<?= e(t('trainer')) ?>"><option value=""><?= e(t('all_trainers')) ?></option>
            <?php foreach (trainers() as $tr): ?><option value="<?= $tr['id'] ?>"<?= $trainerF === (int)$tr['id'] ? ' selected' : '' ?>><?= e($tr['full_name'] ?: $tr['username']) ?></option><?php endforeach; ?></select></form>
      <?php endif; ?>
      <button type="button" class="btn btn-sm btn-outline-secondary d-print-none" onclick="window.print()"><i class="bi bi-printer"></i> <?= e(t('print')) ?></button>
    </div>
    <?php if (!$tm): ?>
      <div class="card-body text-center py-4"><i class="bi bi-calendar-plus text-primary" style="font-size:2.5rem"></i>
        <p class="mt-2 mb-0"><?= e(t($isAdmin ? 'tt_not_made' : 'tt_not_made_trainer', $monthName)) ?></p></div>
    <?php else: ?>
      <div class="card-body py-2 small-muted d-print-none"><?= e(t($isAdmin ? 'tt_help' : 'tt_help_trainer')) ?>
        <?php if ($holidays !== ''): ?> · <?= e(t('weekly_holidays')) ?>: <b><?= e(implode(', ', array_map(fn($d) => t('day' . $d), str_split($holidays)))) ?></b><?php endif; ?></div>
      <?= class_timetable_html($month, $sessions, $holidays, $leave, fn($d) => 'timetable.php?day=' . $d) ?>
    <?php endif; ?>
  </div>
  <?php if ($isAdmin): ?>
    <form method="post" class="card mb-4 d-print-none"<?= $tm ? ' data-verify="' . e(t('tt_again_confirm', $monthName)) . '"' : '' ?>><?= csrf_field() ?>
      <input type="hidden" name="action" value="create"><input type="hidden" name="month" value="<?= e($month) ?>">
      <div class="card-header fw-bold"><i class="bi bi-calendar-plus text-primary"></i> <?= e(t($tm ? 'tt_create_again' : 'tt_create', $monthName)) ?></div>
      <div class="card-body">
        <label class="form-label small d-block"><?= e(t('weekly_holidays')) ?></label>
        <div class="btn-group flex-wrap mb-2" role="group">
          <?php $sel = $tm ? $holidays : $defHol; for ($d = 1; $d <= 7; $d++): ?>
            <input type="checkbox" class="btn-check" name="holidays[]" value="<?= $d ?>" id="h<?= $d ?>"<?= str_contains($sel, (string)$d) ? ' checked' : '' ?>>
            <label class="btn btn-outline-primary" for="h<?= $d ?>"><?= e(mb_substr(t('day' . $d), 0, 3)) ?></label>
          <?php endfor; ?>
        </div>
        <div class="form-text mb-3"><?= e(t('tt_create_help')) ?></div>
        <?php if (!batches()): ?><div class="alert alert-warning small"><?= e(t('tt_need_batches')) ?> <a href="batches.php"><?= e(t('batches')) ?></a></div><?php endif; ?>
        <button class="btn btn-primary btn-lg w-100"><i class="bi bi-magic"></i> <?= e(t($tm ? 'tt_create_again' : 'tt_create', $monthName)) ?></button>
      </div>
    </form>
  <?php endif; ?>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
