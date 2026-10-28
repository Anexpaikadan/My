<?php
// Gym leave days (gym closed): write the notice, share it on WhatsApp (group or each member), see it on the calendar.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    if (post('action') === 'delete') {
        require_verify('leaves.php');
        q('DELETE FROM gym_leaves WHERE id = ?', [$id]);
        flash('success', t('deleted'));
        redirect('leaves.php');
    }
    $from = valid_date(post('from_date')) ? post('from_date') : '';
    $to = valid_date(post('to_date')) ? post('to_date') : $from;
    $title = mb_substr(trim(post('title')), 0, 150);
    $msg = mb_substr(trim(post('message')), 0, 2000);
    if ($from === '' || $title === '') {
        flash('danger', t('leave_fill'));
        redirect('leaves.php' . ($id ? '?edit=' . $id : ''));
    }
    if ($to < $from) {
        [$from, $to] = [$to, $from];
    }
    if ($id) {
        q('UPDATE gym_leaves SET from_date = ?, to_date = ?, title = ?, message = ? WHERE id = ?', [$from, $to, $title, $msg, $id]);
    } else {
        q('INSERT INTO gym_leaves (from_date, to_date, title, message) VALUES (?, ?, ?, ?)', [$from, $to, $title, $msg]);
        $id = (int)db()->lastInsertId();
    }
    flash('success', t('leave_saved'));
    redirect('leaves.php?share=' . $id . '#leave-' . $id);
}

$edit = get('edit') ? q('SELECT * FROM gym_leaves WHERE id = ?', [(int)get('edit')])->fetch() : null;
$shareId = (int)get('share');
$upcoming = q('SELECT * FROM gym_leaves WHERE to_date >= ? ORDER BY from_date', [today()])->fetchAll();
$past = q('SELECT * FROM gym_leaves WHERE to_date < ? ORDER BY from_date DESC LIMIT 30', [today()])->fetchAll();
$members = q("SELECT id, name, phone FROM members WHERE status = 'active' AND expiry_date >= ? ORDER BY name", [today()])->fetchAll();

$month = preg_match('/^\d{4}-\d{2}$/', get('month')) ? get('month') : date('Y-m');
$marks = day_marks($month . '-01', date('Y-m-t', strtotime($month . '-01')));
$links = array_map(fn($l) => 'leaves.php?edit=' . $l['id'] . '&month=' . $month . '#leaveForm', $marks['leave']);
$prev = date('Y-m', strtotime($month . '-01 -1 month'));
$next = date('Y-m', strtotime($month . '-01 +1 month'));

$title = t('gym_leaves');
$active = 'leaves';
$back = 'more.php';
require __DIR__ . '/includes/header.php';

$card = function (array $l, bool $open) use ($members, $month): void { ?>
  <div class="card mb-3<?= $open ? ' border border-danger' : '' ?>" id="leave-<?= $l['id'] ?>">
    <div class="card-body">
      <div class="d-flex flex-wrap align-items-start gap-2">
        <div class="me-auto">
          <h3 class="h6 mb-1"><i class="bi bi-calendar-x text-primary"></i> <?= e($l['title']) ?></h3>
          <div class="small fw-semibold"><?= e(date_range_text($l['from_date'], $l['to_date'])) ?></div>
          <?php if ($l['from_date'] <= today() && $l['to_date'] >= today()): ?><span class="badge bg-danger"><?= e(t('closed_today')) ?></span><?php endif; ?>
        </div>
        <a href="?edit=<?= $l['id'] ?>&month=<?= e($month) ?>#leaveForm" class="btn btn-sm btn-light"><i class="bi bi-pencil"></i> <?= e(t('edit')) ?></a>
        <form method="post" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?>
          <input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= $l['id'] ?>">
          <button class="btn btn-sm btn-outline-danger" aria-label="<?= e(t('delete')) ?>"><i class="bi bi-trash"></i></button></form>
      </div>
      <?php if (trim((string)$l['message']) !== ''): ?><p class="small mb-2 mt-2" style="white-space:pre-line"><?= e($l['message']) ?></p><?php endif; ?>
      <?php $text = leave_text($l); ?>
      <textarea class="visually-hidden" tabindex="-1" aria-hidden="true" id="lt<?= $l['id'] ?>"><?= e($text) ?></textarea>
      <div class="d-flex flex-wrap gap-2 mt-2">
        <a class="btn btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link('', $text)) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('share_whatsapp_group')) ?></a>
        <button type="button" class="btn btn-outline-secondary" data-copy="#lt<?= $l['id'] ?>"><i class="bi bi-copy"></i> <?= e(t('copy_text')) ?></button>
        <?php if ($l['to_date'] >= today()): ?>
        <button type="button" class="btn btn-outline-success" data-bs-toggle="collapse" data-bs-target="#lm<?= $l['id'] ?>"><i class="bi bi-people"></i> <?= e(t('send_each_member')) ?> (<?= count($members) ?>)</button>
        <?php endif; ?>
      </div>
      <?php if ($l['to_date'] >= today()): ?>
      <div class="collapse<?= $open ? ' show' : '' ?>" id="lm<?= $l['id'] ?>"><div class="list-group list-group-flush mt-2 border rounded">
        <?php if (!$members): ?><div class="list-group-item text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
        <?php foreach ($members as $mm): ?>
          <div class="list-group-item d-flex align-items-center gap-2"><span class="me-auto"><?= e($mm['name']) ?></span>
            <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" data-sent href="<?= e(wa_link($mm['phone'], t('wa_hello', $mm['name']) . "\n\n" . $text)) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('send')) ?></a></div>
        <?php endforeach; ?>
      </div></div>
      <?php endif; ?>
    </div>
  </div>
<?php };
?>
<div class="row g-3">
  <div class="col-lg-5">
    <form method="post" class="card mb-3" id="leaveForm"><?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)($edit['id'] ?? 0) ?>">
      <div class="card-header fw-bold"><i class="bi bi-<?= $edit ? 'pencil' : 'plus-circle' ?>"></i> <?= e(t($edit ? 'edit_leave' : 'add_leave')) ?></div>
      <div class="card-body">
        <div class="row g-2 mb-2">
          <div class="col-6"><label class="form-label small" for="lf"><?= e(t('from_date')) ?></label>
            <input class="form-control" type="date" id="lf" name="from_date" required value="<?= e($edit['from_date'] ?? date('Y-m-d', strtotime('+1 day'))) ?>"></div>
          <div class="col-6"><label class="form-label small" for="lto"><?= e(t('to_date')) ?></label>
            <input class="form-control" type="date" id="lto" name="to_date" required value="<?= e($edit['to_date'] ?? date('Y-m-d', strtotime('+1 day'))) ?>"></div>
        </div>
        <label class="form-label small" for="ltitle"><?= e(t('leave_title')) ?></label>
        <input class="form-control mb-1" id="ltitle" name="title" maxlength="150" required value="<?= e($edit['title'] ?? '') ?>" placeholder="<?= e(t('leave_title_ph')) ?>">
        <div class="d-flex flex-wrap gap-1 mb-2 cat-opt">
          <?php foreach (['lv_holiday', 'lv_festival', 'lv_rain', 'lv_maintenance', 'lv_event'] as $k): ?>
            <button type="button" class="btn btn-sm btn-light" onclick="document.getElementById('ltitle').value=this.textContent"><?= e(t($k)) ?></button>
          <?php endforeach; ?>
        </div>
        <label class="form-label small" for="lmsg"><?= e(t('leave_message')) ?></label>
        <textarea class="form-control mb-3" id="lmsg" name="message" rows="4" maxlength="2000" placeholder="<?= e(t('leave_message_ph')) ?>"><?= e($edit['message'] ?? '') ?></textarea>
        <div class="d-flex gap-2">
          <?php if ($edit): ?><a href="leaves.php?month=<?= e($month) ?>" class="btn btn-light"><?= e(t('cancel')) ?></a><?php endif; ?>
          <button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save_and_share')) ?></button>
        </div>
      </div>
    </form>

    <div class="card mb-3">
      <div class="card-header d-flex align-items-center gap-2">
        <a href="?month=<?= $prev ?>" class="btn btn-sm btn-light" aria-label="<?= e(t('back')) ?>"><i class="bi bi-chevron-left"></i></a>
        <span class="me-auto ms-auto fw-bold"><?= e(date('F Y', strtotime($month . '-01'))) ?></span>
        <a href="?month=<?= $next ?>" class="btn btn-sm btn-light" aria-label="Next"><i class="bi bi-chevron-right"></i></a>
      </div>
      <div class="card-body">
        <?= month_calendar($month, [], $marks['leave'], [], $links, false) ?>
        <div class="cal-legend"><span><i class="l"></i><?= e(t('gym_leave')) ?></span><span class="small-muted"><?= e(t('tap_leave_to_change')) ?></span></div>
      </div>
    </div>
  </div>

  <div class="col-lg-7">
    <h2 class="section-head"><?= e(t('upcoming_leaves')) ?></h2>
    <?php if (!$upcoming): ?><div class="card card-body text-muted mb-3"><?= e(t('no_leaves')) ?></div><?php endif; ?>
    <?php foreach ($upcoming as $l) $card($l, $l['id'] == $shareId); ?>
    <?php if ($past): ?>
      <details class="mb-3"><summary class="section-head"><?= e(t('past_leaves')) ?> (<?= count($past) ?>)</summary>
        <?php foreach ($past as $l) $card($l, false); ?>
      </details>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
