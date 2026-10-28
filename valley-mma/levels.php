<?php
// Positions (levels): set up the levels by attendance days (e.g. Warm-up day 1–5, Beginner from day 6 …).
// Members move up automatically with their attendance; the admin can change the position of any member.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = post('action');
    $back = post('back') !== '' && preg_match('/^[a-z_]+\.php(\?[\w=&%#-]*)?$/', post('back')) ? post('back') : 'levels.php';
    if ($action === 'member_level') {
        $mid = (int)post('member_id');
        $auto = post('auto') === '1';
        if ($auto) {
            q('UPDATE members SET level_auto = 1 WHERE id = ?', [$mid]);
            $l = level_update($mid);
            if (!$l) {
                $l = level_by_id((int)q('SELECT level_id FROM members WHERE id = ?', [$mid])->fetchColumn());
            }
        } else {
            $l = level_by_id((int)post('level_id'));
            if ($l) {
                q('UPDATE members SET level_since = IF(level_id <=> ?, level_since, ?), level_id = ?, level_auto = 0 WHERE id = ?', [$l['id'], today(), $l['id'], $mid]);
            }
        }
        flash('success', t('position_saved', (string)q('SELECT name FROM members WHERE id = ?', [$mid])->fetchColumn(), $l['name'] ?? '–'));
        redirect($back);
    }
    if ($action === 'delete') {
        require_verify('levels.php');
        $id = (int)post('id');
        if (count(levels()) > 1) {
            q('UPDATE members SET level_auto = 1 WHERE level_id = ?', [$id]);
            q('DELETE FROM levels WHERE id = ?', [$id]);
            q("UPDATE levels SET from_day = 1 WHERE id = (SELECT id FROM (SELECT id FROM levels ORDER BY from_day LIMIT 1) x)");
            levels_recalc();
            flash('success', t('deleted'));
        }
        redirect('levels.php');
    }
    if ($action === 'recalc') {
        levels_recalc();
        flash('success', t('positions_updated'));
        redirect('levels.php');
    }
    // add / change a level
    $id = (int)post('id');
    $name = mb_substr(trim(post('name')), 0, 60);
    $from = max(1, min(9999, (int)post('from_day')));
    $color = preg_match('/^#[0-9a-fA-F]{6}$/', post('color')) ? post('color') : '#6C757D';
    $note = mb_substr(trim(post('note')), 0, 255);
    $taken = q('SELECT COUNT(*) FROM levels WHERE from_day = ? AND id <> ?', [$from, $id])->fetchColumn();
    if ($name === '' || $taken) {
        flash('danger', t($taken ? 'level_day_taken' : 'level_name_needed'));
        redirect('levels.php' . ($id ? '?edit=' . $id : ''));
    }
    if ($id) {
        q('UPDATE levels SET name = ?, from_day = ?, color = ?, note = ? WHERE id = ?', [$name, $from, $color, $note, $id]);
    } else {
        q('INSERT INTO levels (name, from_day, color, note) VALUES (?, ?, ?, ?)', [$name, $from, $color, $note]);
    }
    // The first level always starts on day 1.
    q("UPDATE levels SET from_day = 1 WHERE id = (SELECT id FROM (SELECT id FROM levels ORDER BY from_day LIMIT 1) x)");
    levels_recalc();
    flash('success', t('level_saved'));
    redirect('levels.php');
}

$levels = levels();
$edit = get('edit') ? level_by_id((int)get('edit')) : null;
$counts = q("SELECT level_id, COUNT(*) FROM members WHERE status = 'active' GROUP BY level_id")->fetchAll(PDO::FETCH_KEY_PAIR);
$filter = (int)get('level');
$who = get('who', 'active');
$where = $who === 'all' ? "m.status <> 'pending'" : "m.status = 'active' AND m.expiry_date >= CURDATE()";
$args = [];
if ($filter) {
    $where .= ' AND m.level_id = ?';
    $args[] = $filter;
}
$members = q("SELECT m.id, m.name, m.adm_no, m.photo, m.level_id, m.level_auto, m.level_since,
              (SELECT COUNT(*) FROM attendance a WHERE a.member_id = m.id) days
              FROM members m WHERE $where ORDER BY days DESC, m.name", $args)->fetchAll();

$title = t('positions');
$active = 'levels';
$back = 'more.php';
require __DIR__ . '/includes/header.php';
?>
<div class="alert alert-light border small"><i class="bi bi-info-circle text-primary"></i> <?= e(t('levels_help')) ?></div>
<div class="row g-3">
  <div class="col-lg-5">
    <div class="card mb-3">
      <div class="card-header fw-bold d-flex align-items-center"><span class="me-auto"><i class="bi bi-award-fill text-primary"></i> <?= e(t('positions')) ?></span>
        <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="recalc">
          <button class="btn btn-sm btn-light" title="<?= e(t('recalc_help')) ?>"><i class="bi bi-arrow-repeat"></i> <?= e(t('recalc')) ?></button></form></div>
      <div class="list-group list-group-flush">
        <?php foreach ($levels as $i => $l): ?>
          <div class="list-group-item">
            <div class="d-flex align-items-center gap-2">
              <span class="level-step" style="background:<?= e($l['color']) ?>"><?= $i + 1 ?></span>
              <div class="me-auto"><div class="fw-bold"><?= e($l['name']) ?></div>
                <div class="small-muted"><?= e(level_range($l)) ?><?= $l['note'] !== '' ? ' · ' . e($l['note']) : '' ?></div></div>
              <a href="?level=<?= $l['id'] ?>" class="badge text-bg-light border text-decoration-none fs-6"><?= (int)($counts[$l['id']] ?? 0) ?></a>
              <a href="?edit=<?= $l['id'] ?>#levelForm" class="btn btn-sm btn-light" aria-label="<?= e(t('edit')) ?>"><i class="bi bi-pencil"></i></a>
              <?php if (count($levels) > 1): ?>
              <form method="post" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= $l['id'] ?>">
                <button class="btn btn-sm btn-outline-danger" aria-label="<?= e(t('delete')) ?>"><i class="bi bi-trash"></i></button></form>
              <?php endif; ?>
            </div>
          </div>
        <?php endforeach; ?>
      </div>
    </div>

    <form method="post" class="card mb-3" id="levelForm"><?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)($edit['id'] ?? 0) ?>">
      <div class="card-header fw-bold"><i class="bi bi-<?= $edit ? 'pencil' : 'plus-circle' ?>"></i> <?= e(t($edit ? 'edit_level' : 'add_level')) ?></div>
      <div class="card-body">
        <div class="row g-2">
          <div class="col-8"><label class="form-label small" for="lvn"><?= e(t('level_name')) ?></label>
            <input class="form-control" id="lvn" name="name" maxlength="60" required value="<?= e($edit['name'] ?? '') ?>" placeholder="<?= e(t('level_name_ph')) ?>"></div>
          <div class="col-4"><label class="form-label small" for="lvc"><?= e(t('colour')) ?></label>
            <input class="form-control form-control-color w-100" type="color" id="lvc" name="color" value="<?= e($edit['color'] ?? '#7048E8') ?>"></div>
          <div class="col-12"><label class="form-label small" for="lvd"><?= e(t('level_from_day')) ?></label>
            <div class="input-group"><span class="input-group-text"><?= e(t('attendance_day')) ?></span>
              <input class="form-control" type="number" id="lvd" name="from_day" min="1" max="9999" required value="<?= e((string)($edit['from_day'] ?? '')) ?>"></div>
            <div class="form-text"><?= e(t('level_from_day_help')) ?></div></div>
          <div class="col-12"><label class="form-label small" for="lvo"><?= e(t('level_note')) ?></label>
            <input class="form-control" id="lvo" name="note" maxlength="255" value="<?= e($edit['note'] ?? '') ?>" placeholder="<?= e(t('level_note_ph')) ?>"></div>
        </div>
        <div class="d-flex gap-2 mt-3">
          <?php if ($edit): ?><a href="levels.php" class="btn btn-light"><?= e(t('cancel')) ?></a><?php endif; ?>
          <button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
        </div>
      </div>
    </form>
  </div>

  <div class="col-lg-7">
    <div class="card">
      <div class="card-header">
        <form class="d-flex flex-wrap gap-2" method="get">
          <select class="form-select form-select-sm w-auto" name="level" onchange="this.form.submit()">
            <option value="0"><?= e(t('all_positions')) ?></option>
            <?php foreach ($levels as $l): ?><option value="<?= $l['id'] ?>"<?= $filter === (int)$l['id'] ? ' selected' : '' ?>><?= e($l['name']) ?></option><?php endforeach; ?>
          </select>
          <select class="form-select form-select-sm w-auto" name="who" onchange="this.form.submit()">
            <option value="active"<?= $who === 'active' ? ' selected' : '' ?>><?= e(t('active_members')) ?></option>
            <option value="all"<?= $who === 'all' ? ' selected' : '' ?>><?= e(t('all_members')) ?></option>
          </select>
          <span class="ms-auto align-self-center small-muted"><?= count($members) ?> <?= e(t('members')) ?></span>
        </form>
      </div>
      <div class="list-group list-group-flush">
        <?php if (!$members): ?><div class="list-group-item text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
        <?php foreach ($members as $mm): $p = level_progress($mm); ?>
          <div class="list-group-item">
            <div class="d-flex align-items-center gap-2 mb-1">
              <img src="<?= e(photo_url($mm)) ?>" class="avatar" alt="">
              <a href="member_view.php?id=<?= $mm['id'] ?>" class="fw-semibold me-auto text-decoration-none"><?= e($mm['name']) ?></a>
              <span class="badge <?= $mm['level_auto'] ? 'text-bg-light border' : 'bg-dark' ?>"><?= e(t($mm['level_auto'] ? 'level_auto' : 'level_manual')) ?></span>
              <button type="button" class="btn btn-sm btn-light" data-bs-toggle="collapse" data-bs-target="#lc<?= $mm['id'] ?>" aria-label="<?= e(t('change')) ?>"><i class="bi bi-arrow-left-right"></i></button>
            </div>
            <?= level_progress_html($p) ?>
            <form method="post" class="collapse mt-2" id="lc<?= $mm['id'] ?>"><?= csrf_field() ?>
              <input type="hidden" name="action" value="member_level"><input type="hidden" name="member_id" value="<?= $mm['id'] ?>">
              <input type="hidden" name="back" value="levels.php?level=<?= $filter ?>&who=<?= e($who) ?>">
              <?php require __DIR__ . '/includes/level_fields.php'; ?>
            </form>
          </div>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
