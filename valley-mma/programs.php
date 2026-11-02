<?php
// Programs on the public page: photo, short text, details, who it is for, class time and trainer.
// Visitors tap a program to see the details and book a free trial for it.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    $old = $id ? q('SELECT * FROM programs WHERE id = ?', [$id])->fetch() : null;
    if (post('action') === 'delete') {
        require_verify('programs.php');
        if ($old) {
            delete_media($old['image']);
            q('DELETE FROM programs WHERE id = ?', [$id]);
            flash('success', t('deleted'));
        }
        redirect('programs.php');
    }
    $name = mb_substr(trim(post('name')), 0, 60);
    if ($name === '') {
        flash('danger', t('level_name_needed'));
        redirect('programs.php?edit=' . ($id ?: 'new'));
    }
    $image = $old['image'] ?? '';
    $up = save_media_upload('image', 'programs');
    if ($up === null) {
        flash('warning', t('err_photo'));
    } elseif ($up !== '') {
        delete_media($image);
        $image = $up;
    } elseif (post('remove_image') === '1') {
        delete_media($image);
        $image = '';
    }
    $vals = [$name, mb_substr(trim(post('short_text')), 0, 200), mb_substr(trim(post('details')), 0, 3000), mb_substr(trim(post('suitable_for')), 0, 150),
        mb_substr(trim(post('schedule')), 0, 200), mb_substr(trim(post('trainer')), 0, 100), mb_substr(trim(post('trainer_about')), 0, 300),
        $image, post('active') === '1' ? 1 : 0, (int)post('sort_order')];
    if ($old) {
        $vals[] = $id;
        q('UPDATE programs SET name = ?, short_text = ?, details = ?, suitable_for = ?, schedule = ?, trainer = ?, trainer_about = ?, image = ?, active = ?, sort_order = ? WHERE id = ?', $vals);
    } else {
        q('INSERT INTO programs (name, short_text, details, suitable_for, schedule, trainer, trainer_about, image, active, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', $vals);
    }
    flash('success', t('saved'));
    redirect('programs.php');
}

$editKey = get('edit');
$edit = $editKey === 'new' ? ['id' => 0, 'name' => '', 'short_text' => '', 'details' => '', 'suitable_for' => '', 'schedule' => '', 'trainer' => '', 'trainer_about' => '', 'image' => '', 'active' => 1, 'sort_order' => count(programs_list(true)) + 1]
    : ($editKey !== '' ? q('SELECT * FROM programs WHERE id = ?', [(int)$editKey])->fetch() : null);
$list = programs_list(true);

$title = t('programs_admin');
$active = 'programs';
$back = $edit ? 'programs.php' : 'more.php';
$actions = $edit ? '' : '<a href="home.php#programs" class="btn btn-outline-primary" target="_blank"><i class="bi bi-box-arrow-up-right"></i> ' . e(t('open_public_page')) . '</a>'
    . '<a href="?edit=new" class="btn btn-primary"><i class="bi bi-plus-lg"></i> ' . e(t('add_program')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<?php if ($edit): $img = safe_img($edit['image']); ?>
<form method="post" enctype="multipart/form-data" class="card mb-3"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
  <div class="card-header fw-bold"><i class="bi bi-<?= $edit['id'] ? 'pencil' : 'plus-circle' ?>"></i> <?= e(t($edit['id'] ? 'edit_program' : 'add_program')) ?></div>
  <div class="card-body row g-3">
    <div class="col-md-4 text-center">
      <div class="prog-edit-img mb-2"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>><?php if ($img === ''): ?><i class="bi bi-image"></i><?php endif; ?></div>
      <input class="form-control form-control-sm" type="file" name="image" accept="image/*" aria-label="<?= e(t('change_photo')) ?>">
      <?php if ($img !== ''): ?><div class="form-check small mt-1 text-start"><input class="form-check-input" type="checkbox" name="remove_image" value="1" id="rmi"><label class="form-check-label" for="rmi"><?= e(t('remove_photo')) ?></label></div><?php endif; ?>
      <div class="form-text"><?= e(t('program_photo_help')) ?></div>
    </div>
    <div class="col-md-8 row g-2 m-0 p-0">
      <div class="col-8"><label class="form-label small" for="pgn"><?= e(t('name')) ?> *</label><input class="form-control" id="pgn" name="name" maxlength="60" required value="<?= e($edit['name']) ?>" placeholder="MMA"></div>
      <div class="col-4"><label class="form-label small" for="pgo"><?= e(t('sort_order')) ?></label><input class="form-control" type="number" id="pgo" name="sort_order" value="<?= (int)$edit['sort_order'] ?>"></div>
      <div class="col-12"><label class="form-label small" for="pgs"><?= e(t('short_text')) ?></label><input class="form-control" id="pgs" name="short_text" maxlength="200" value="<?= e($edit['short_text']) ?>" placeholder="<?= e(t('short_text_ph')) ?>"></div>
      <div class="col-12"><label class="form-label small" for="pgd"><?= e(t('details')) ?></label><textarea class="form-control" id="pgd" name="details" rows="5" maxlength="3000" placeholder="<?= e(t('program_details_ph')) ?>"><?= e((string)$edit['details']) ?></textarea></div>
      <div class="col-md-6"><label class="form-label small" for="pgf"><?= e(t('suitable_for')) ?></label><input class="form-control" id="pgf" name="suitable_for" maxlength="150" value="<?= e($edit['suitable_for']) ?>" placeholder="<?= e(t('suitable_for_ph')) ?>"></div>
      <div class="col-md-6"><label class="form-label small" for="pgt"><?= e(t('class_time')) ?></label><input class="form-control" id="pgt" name="schedule" maxlength="200" value="<?= e($edit['schedule']) ?>" placeholder="<?= e(t('class_time_ph')) ?>"></div>
      <div class="col-md-6"><label class="form-label small" for="pgr"><?= e(t('trainer')) ?></label><input class="form-control" id="pgr" name="trainer" maxlength="100" value="<?= e($edit['trainer']) ?>" placeholder="<?= e(t('trainer_ph')) ?>"></div>
      <div class="col-md-6"><label class="form-label small" for="pga"><?= e(t('trainer_about')) ?></label><input class="form-control" id="pga" name="trainer_about" maxlength="300" value="<?= e($edit['trainer_about']) ?>" placeholder="<?= e(t('trainer_about_ph')) ?>"></div>
      <div class="col-12"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="active" value="1" id="pgac"<?= $edit['active'] ? ' checked' : '' ?>><label class="form-check-label" for="pgac"><?= e(t('show_on_public')) ?></label></div></div>
    </div>
    <div class="col-12 d-flex gap-2"><a href="programs.php" class="btn btn-light"><?= e(t('cancel')) ?></a><button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
  </div>
</form>
<?php if ($edit['id']): ?>
  <form method="post" class="text-end mb-4" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
    <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button></form>
<?php endif; ?>
<?php else: ?>
  <p class="small-muted"><?= e(t('programs_help')) ?></p>
  <?php if (!$list): ?><div class="card card-body text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
  <div class="row g-2">
    <?php foreach ($list as $p): $img = safe_img($p['image']); ?>
      <div class="col-6 col-md-4 col-lg-3"><a href="?edit=<?= $p['id'] ?>" class="card h-100 text-decoration-none text-reset<?= $p['active'] ? '' : ' opacity-50' ?>">
        <div class="prod-thumb"><?php if ($img !== ''): ?><img src="<?= e($img) ?>" alt="" loading="lazy"><?php else: ?><i class="bi bi-fire"></i><?php endif; ?></div>
        <div class="card-body p-2"><div class="fw-bold"><?= e($p['name']) ?></div>
          <div class="small-muted small"><?= e($p['trainer'] !== '' ? $p['trainer'] : t('no_trainer_yet')) ?><?= $p['active'] ? '' : ' · ' . e(t('hidden')) ?></div></div>
      </a></div>
    <?php endforeach; ?>
  </div>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
