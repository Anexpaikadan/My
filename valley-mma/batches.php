<?php
// Batches (class times): morning, evening … with days, time, trainer and capacity. Members are put in a
// batch; open a batch to see its members, who came today (and who was late), move members and send
// them a WhatsApp message.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    $action = post('action');
    if ($action === 'delete') {
        require_verify('batches.php?edit=' . $id);
        q('UPDATE members SET batch_id = NULL WHERE batch_id = ?', [$id]);
        q('DELETE FROM batches WHERE id = ?', [$id]);
        flash('success', t('deleted'));
        redirect('batches.php');
    }
    if ($action === 'move') { // put the ticked members into a batch (or none)
        $ids = array_filter(array_map('intval', (array)($_POST['ids'] ?? [])));
        $to = (int)post('to') ?: null;
        foreach ($ids as $mid) {
            q('UPDATE members SET batch_id = ? WHERE id = ?', [$to, $mid]);
        }
        flash($ids ? 'success' : 'warning', $ids ? t('batch_moved', count($ids), $to ? batch_by_id($to)['name'] ?? '' : t('no_batch')) : t('select_members_first'));
        redirect(post('back') !== '' && preg_match('/^batches\.php(\?[\w=&]*)?$/', post('back')) ? post('back') : 'batches.php');
    }
    $name = mb_substr(trim(post('name')), 0, 60);
    $start = preg_match('/^\d{2}:\d{2}$/', post('start_time')) ? post('start_time') . ':00' : '';
    $end = preg_match('/^\d{2}:\d{2}$/', post('end_time')) ? post('end_time') . ':00' : '';
    $days = implode('', array_intersect(['1', '2', '3', '4', '5', '6', '7'], (array)($_POST['days'] ?? [])));
    if ($name === '' || $start === '' || $end === '' || $days === '') {
        flash('danger', t('batch_fill'));
        redirect('batches.php?edit=' . ($id ?: 'new'));
    }
    $vals = [$name, $start, $end, $days, mb_substr(trim(post('trainer')), 0, 100), max(0, min(999, (int)post('capacity'))),
        mb_substr(trim(post('note')), 0, 200), post('show_public') === '1' ? 1 : 0, post('active') === '1' ? 1 : 0, (int)post('sort_order')];
    if ($id) {
        $vals[] = $id;
        q('UPDATE batches SET name = ?, start_time = ?, end_time = ?, days = ?, trainer = ?, capacity = ?, note = ?, show_public = ?, active = ?, sort_order = ? WHERE id = ?', $vals);
    } else {
        q('INSERT INTO batches (name, start_time, end_time, days, trainer, capacity, note, show_public, active, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', $vals);
        $id = (int)db()->lastInsertId();
    }
    flash('success', t('saved'));
    redirect('batches.php?id=' . $id);
}

$all = batches(true);
$today = today();
$counts = q("SELECT batch_id, COUNT(*) FROM members WHERE status = 'active' AND expiry_date >= ? GROUP BY batch_id", [$today])->fetchAll(PDO::FETCH_KEY_PAIR);
$presentBy = q("SELECT m.batch_id, COUNT(*) FROM attendance a JOIN members m ON m.id = a.member_id WHERE a.att_date = ? GROUP BY m.batch_id", [$today])->fetchAll(PDO::FETCH_KEY_PAIR);
$editKey = get('edit');
$edit = $editKey === 'new' ? ['id' => 0, 'name' => '', 'start_time' => '06:00:00', 'end_time' => '07:30:00', 'days' => '123456', 'trainer' => '', 'capacity' => 0, 'note' => '', 'show_public' => 1, 'active' => 1, 'sort_order' => count($all) + 1]
    : ($editKey !== '' ? batch_by_id((int)$editKey) : null);
$view = !$edit && get('id') !== '' ? (get('id') === 'none' ? ['id' => 0, 'name' => t('no_batch')] : batch_by_id((int)get('id'))) : null;

$title = $view ? $view['name'] : t('batches');
$active = 'batches';
$back = $edit || $view ? 'batches.php' : 'attendance.php';
$actions = $edit || $view ? '' : '<a href="?edit=new" class="btn btn-primary"><i class="bi bi-plus-lg"></i> ' . e(t('add_batch')) . '</a>';
if ($view && $view['id']) {
    $actions = '<a href="?edit=' . $view['id'] . '" class="btn btn-outline-primary"><i class="bi bi-pencil"></i> ' . e(t('edit')) . '</a>';
}
require __DIR__ . '/includes/header.php';
?>
<?php if ($edit): ?>
<form method="post" class="card mb-3" style="max-width:720px"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
  <div class="card-header fw-bold"><i class="bi bi-<?= $edit['id'] ? 'pencil' : 'plus-circle' ?>"></i> <?= e(t($edit['id'] ? 'edit_batch' : 'add_batch')) ?></div>
  <div class="card-body row g-3">
    <div class="col-12"><label class="form-label small" for="bn"><?= e(t('name')) ?> *</label>
      <input class="form-control" id="bn" name="name" maxlength="60" required value="<?= e($edit['name']) ?>" placeholder="<?= e(t('batch_name_ph')) ?>">
      <div class="d-flex flex-wrap gap-1 mt-1 cat-opt"><?php foreach (['batch_morning', 'batch_evening', 'batch_night', 'batch_kids', 'batch_ladies', 'batch_fighters'] as $k): ?>
        <button type="button" class="btn btn-sm btn-light" onclick="document.getElementById('bn').value=this.textContent"><?= e(t($k)) ?></button><?php endforeach; ?></div></div>
    <div class="col-6"><label class="form-label small" for="bs"><?= e(t('start_time')) ?> *</label><input class="form-control" type="time" id="bs" name="start_time" required value="<?= e(substr($edit['start_time'], 0, 5)) ?>"></div>
    <div class="col-6"><label class="form-label small" for="be"><?= e(t('end_time')) ?> *</label><input class="form-control" type="time" id="be" name="end_time" required value="<?= e(substr($edit['end_time'], 0, 5)) ?>"></div>
    <div class="col-12"><label class="form-label small d-block"><?= e(t('days')) ?> *</label>
      <div class="btn-group flex-wrap" role="group">
        <?php for ($d = 1; $d <= 7; $d++): ?>
          <input type="checkbox" class="btn-check" name="days[]" value="<?= $d ?>" id="bd<?= $d ?>"<?= str_contains($edit['days'], (string)$d) ? ' checked' : '' ?>>
          <label class="btn btn-outline-primary" for="bd<?= $d ?>"><?= e(mb_substr(t('day' . $d), 0, 3)) ?></label>
        <?php endfor; ?>
      </div></div>
    <div class="col-md-6"><label class="form-label small" for="bt"><?= e(t('trainer')) ?></label><input class="form-control" id="bt" name="trainer" maxlength="100" value="<?= e($edit['trainer']) ?>" placeholder="<?= e(t('trainer_ph')) ?>"></div>
    <div class="col-6 col-md-3"><label class="form-label small" for="bc"><?= e(t('capacity')) ?></label><input class="form-control" type="number" min="0" max="999" id="bc" name="capacity" value="<?= (int)$edit['capacity'] ?>"><div class="form-text"><?= e(t('capacity_help')) ?></div></div>
    <div class="col-6 col-md-3"><label class="form-label small" for="bo"><?= e(t('sort_order')) ?></label><input class="form-control" type="number" id="bo" name="sort_order" value="<?= (int)$edit['sort_order'] ?>"></div>
    <div class="col-12"><label class="form-label small" for="bx"><?= e(t('note')) ?></label><input class="form-control" id="bx" name="note" maxlength="200" value="<?= e($edit['note']) ?>" placeholder="<?= e(t('batch_note_ph')) ?>"></div>
    <div class="col-12 d-flex flex-wrap gap-4">
      <div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="show_public" value="1" id="bp"<?= $edit['show_public'] ? ' checked' : '' ?>><label class="form-check-label" for="bp"><?= e(t('show_on_public')) ?></label></div>
      <div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="active" value="1" id="ba"<?= $edit['active'] ? ' checked' : '' ?>><label class="form-check-label" for="ba"><?= e(t('st_active')) ?></label></div>
    </div>
    <div class="col-12 d-flex gap-2"><a href="batches.php<?= $edit['id'] ? '?id=' . (int)$edit['id'] : '' ?>" class="btn btn-light"><?= e(t('cancel')) ?></a><button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
  </div>
</form>
<?php if ($edit['id']): ?>
  <form method="post" style="max-width:720px" class="text-end mb-4" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
    <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button><div class="form-text"><?= e(t('batch_delete_help')) ?></div></form>
<?php endif; ?>

<?php elseif ($view): // one batch: members, today's attendance, move, WhatsApp
    $bid = (int)$view['id'];
    $members = q('SELECT m.*, a.check_in FROM members m LEFT JOIN attendance a ON a.member_id = m.id AND a.att_date = ?
                  WHERE ' . ($bid ? 'm.batch_id = ?' : 'm.batch_id IS NULL') . " AND m.status <> 'pending' ORDER BY a.check_in IS NULL, m.name", $bid ? [$today, $bid] : [$today])->fetchAll();
    $activeList = array_filter($members, fn($mm) => $mm['status'] === 'active' && $mm['expiry_date'] >= $today);
    $present = array_filter($members, fn($mm) => $mm['check_in']);
    $isDay = $bid && str_contains($view['days'], (string)date('N'));
?>
  <?php if ($bid): ?>
  <div class="row g-2 mb-3">
    <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('time')) ?></div><div class="fw-bold"><?= e(batch_time($view)) ?></div><div class="small-muted"><?= e(batch_days($view)) ?></div></div></div></div>
    <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('members')) ?></div><div class="fw-bold"><?= count($activeList) ?><?= $view['capacity'] ? ' / ' . (int)$view['capacity'] : '' ?></div>
      <?php if ($view['capacity'] && count($activeList) >= $view['capacity']): ?><div class="small text-danger"><?= e(t('batch_full')) ?></div><?php endif; ?></div></div></div>
    <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('present_today')) ?></div><div class="fw-bold"><?= count($present) ?></div><div class="small-muted"><?= e($isDay ? t('class_today') : t('no_class_today')) ?></div></div></div></div>
    <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('trainer')) ?></div><div class="fw-bold"><?= e($view['trainer'] !== '' ? $view['trainer'] : '–') ?></div></div></div></div>
  </div>
  <?php endif; ?>
  <form method="post" id="moveForm" class="card"><?= csrf_field() ?><input type="hidden" name="action" value="move"><input type="hidden" name="back" value="batches.php?id=<?= $bid ?: 'none' ?>">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center">
      <div class="form-check mb-0 me-auto"><input class="form-check-input" type="checkbox" id="selAll" onclick="document.querySelectorAll('.bulk-cb').forEach(c => c.checked = this.checked)">
        <label class="form-check-label small" for="selAll"><?= e(t('select_all')) ?> · <?= count($members) ?></label></div>
      <select class="form-select form-select-sm w-auto" name="to" aria-label="<?= e(t('move_to')) ?>">
        <?php foreach ($all as $b): if ((int)$b['id'] === $bid) continue; ?><option value="<?= $b['id'] ?>"><?= e($b['name']) ?></option><?php endforeach; ?>
        <?php if ($bid): ?><option value="0"><?= e(t('no_batch')) ?></option><?php endif; ?>
      </select>
      <button class="btn btn-sm btn-outline-primary"><i class="bi bi-arrow-left-right"></i> <?= e(t('move_to')) ?></button>
      <?php if ($bid && $activeList): ?><button type="button" class="btn btn-sm btn-whatsapp" data-bs-toggle="collapse" data-bs-target="#batchWa"><i class="bi bi-whatsapp"></i> <?= e(t('message_batch')) ?></button><?php endif; ?>
    </div>
    <?php if ($bid && $activeList): ?>
    <div class="collapse border-bottom" id="batchWa"><div class="card-body">
      <textarea class="form-control mb-2" id="batchMsg" rows="3" maxlength="1000"><?= e(t('wa_batch_default', $view['name'], batch_time($view))) ?></textarea>
      <div class="small-muted mb-2"><?= e(t('message_batch_help')) ?></div>
      <div class="d-flex flex-wrap gap-2" id="batchWaList">
        <a class="btn btn-sm btn-success" target="_blank" rel="noopener" data-wa-to=""><i class="bi bi-people-fill"></i> <?= e(t('share_whatsapp_group')) ?></a>
        <?php foreach ($activeList as $mm): ?><a class="btn btn-sm btn-outline-success" target="_blank" rel="noopener" data-sent data-wa-to="<?= e(wa_phone($mm['phone'])) ?>" data-wa-name="<?= e($mm['name']) ?>"><i class="bi bi-whatsapp"></i> <?= e($mm['name']) ?></a><?php endforeach; ?>
      </div>
    </div></div>
    <?php endif; ?>
    <div class="list-group list-group-flush">
      <?php if (!$members): ?><div class="list-group-item text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
      <?php foreach ($members as $mm): $late = $mm['check_in'] ? late_minutes($bid ? $view : null, $today, $mm['check_in']) : 0; ?>
        <div class="list-group-item d-flex align-items-center gap-2">
          <input class="form-check-input bulk-cb mt-0" type="checkbox" name="ids[]" value="<?= $mm['id'] ?>" aria-label="<?= e($mm['name']) ?>">
          <img src="<?= e(photo_url($mm)) ?>" class="avatar" alt="">
          <a href="member_view.php?id=<?= $mm['id'] ?>" class="me-auto text-decoration-none"><span class="fw-semibold"><?= e($mm['name']) ?></span>
            <span class="d-block small-muted"><?= e($mm['adm_no']) ?> · <?= status_badge($mm['expiry_date'], $mm['status']) ?></span></a>
          <?php if ($mm['check_in']): ?>
            <span class="badge <?= $late ? 'bg-warning text-dark' : 'bg-success' ?>"><i class="bi bi-check2"></i> <?= e(substr($mm['check_in'], 0, 5)) ?><?= $late ? ' · ' . e(t('late_min', $late)) : '' ?></span>
          <?php elseif ($isDay && $mm['status'] === 'active'): ?><span class="badge text-bg-light border"><?= e(t('not_yet')) ?></span><?php endif; ?>
        </div>
      <?php endforeach; ?>
    </div>
  </form>
  <script>
  (function () {
    var msg = document.getElementById('batchMsg');
    if (!msg) return;
    document.querySelectorAll('[data-wa-to]').forEach(function (a) {
      var upd = function () {
        var txt = (a.dataset.waName ? <?= json_encode(t('wa_hello_short')) ?>.replace('%s', a.dataset.waName) + '\n\n' : '') + msg.value;
        a.href = window.vmWa ? window.vmWa('https://wa.me/' + a.dataset.waTo + '?text=' + encodeURIComponent(txt)) : 'https://wa.me/' + a.dataset.waTo + '?text=' + encodeURIComponent(txt);
      };
      upd(); msg.addEventListener('input', upd);
    });
  })();
  </script>

<?php else: // all batches ?>
  <p class="small-muted"><?= e(t('batches_help')) ?></p>
  <div class="row g-2">
    <?php foreach ($all as $b): $n = (int)($counts[$b['id']] ?? 0); $pct = $b['capacity'] ? min(100, (int)round($n * 100 / $b['capacity'])) : 0;
      $now = date('H:i:s'); $running = $b['active'] && str_contains($b['days'], (string)date('N')) && $now >= $b['start_time'] && $now <= $b['end_time']; ?>
      <div class="col-md-6 col-lg-4"><a href="?id=<?= $b['id'] ?>" class="card h-100 text-decoration-none text-reset batch-card<?= $b['active'] ? '' : ' opacity-50' ?>">
        <div class="card-body">
          <div class="d-flex align-items-start gap-2 mb-2">
            <span class="batch-ico"><i class="bi bi-<?= (int)substr($b['start_time'], 0, 2) < 12 ? 'sunrise' : ((int)substr($b['start_time'], 0, 2) < 18 ? 'sun' : 'moon-stars') ?>-fill"></i></span>
            <div class="me-auto"><div class="fw-bold"><?= e($b['name']) ?></div><div class="small"><?= e(batch_time($b)) ?> · <?= e(batch_days($b)) ?></div>
              <?php if ($b['trainer'] !== ''): ?><div class="small-muted small"><i class="bi bi-person-badge"></i> <?= e($b['trainer']) ?></div><?php endif; ?></div>
            <?php if ($running): ?><span class="badge bg-danger"><?= e(t('running_now')) ?></span><?php elseif (!$b['active']): ?><span class="badge text-bg-light border"><?= e(t('hidden')) ?></span><?php endif; ?>
          </div>
          <div class="d-flex justify-content-between small mb-1"><span><i class="bi bi-people"></i> <?= $n ?><?= $b['capacity'] ? ' / ' . (int)$b['capacity'] : '' ?> <?= e(t('members')) ?></span>
            <span><i class="bi bi-calendar-check"></i> <?= (int)($presentBy[$b['id']] ?? 0) ?> <?= e(t('today')) ?></span></div>
          <?php if ($b['capacity']): ?><div class="progress" style="height:.45rem"><div class="progress-bar<?= $pct >= 100 ? ' bg-danger' : '' ?>" style="width:<?= $pct ?>%"></div></div><?php endif; ?>
        </div></a></div>
    <?php endforeach; ?>
    <?php $none = (int)q("SELECT COUNT(*) FROM members WHERE status = 'active' AND expiry_date >= ? AND batch_id IS NULL", [$today])->fetchColumn(); ?>
    <div class="col-md-6 col-lg-4"><a href="?id=none" class="card h-100 text-decoration-none text-reset border-dashed"><div class="card-body d-flex align-items-center gap-2">
      <span class="batch-ico muted"><i class="bi bi-question-lg"></i></span><div class="me-auto"><div class="fw-bold"><?= e(t('no_batch')) ?></div><div class="small-muted small"><?= e(t('no_batch_help')) ?></div></div>
      <span class="badge <?= $none ? 'bg-warning text-dark' : 'text-bg-light border' ?>"><?= $none ?></span></div></a></div>
  </div>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
