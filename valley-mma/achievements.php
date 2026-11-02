<?php
// Member achievements (medals, titles, belts, fight wins …) with a photo. Public ones are shown in the
// "Our Champions" slider on the public page; all are shown on the member page and in the member app.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    $old = $id ? q('SELECT * FROM achievements WHERE id = ?', [$id])->fetch() : null;
    $back = post('back') === 'member' && (int)post('member_id') ? 'member_view.php?id=' . (int)post('member_id') . '#achievements' : 'achievements.php';
    if (post('action') === 'delete') {
        require_verify($back);
        if ($old) {
            delete_media($old['image']);
            q('DELETE FROM achievements WHERE id = ?', [$id]);
            flash('success', t('deleted'));
        }
        redirect($back);
    }
    $mid = (int)post('member_id') ?: null;
    $member = $mid ? q('SELECT id, name FROM members WHERE id = ?', [$mid])->fetch() : null;
    $athlete = mb_substr(trim(post('athlete')), 0, 100);
    if ($athlete === '' && $member) {
        $athlete = $member['name'];
    }
    $titleTxt = mb_substr(trim(post('title')), 0, 150);
    if ($titleTxt === '' || $athlete === '') {
        flash('danger', t('ach_fill'));
        redirect('achievements.php?edit=' . ($id ?: 'new') . ($mid ? '&member=' . $mid : ''));
    }
    $image = $old['image'] ?? '';
    $up = save_media_upload('image', 'achievements');
    if ($up === null) {
        flash('warning', t('err_photo'));
    } elseif ($up !== '') {
        delete_media($image);
        $image = $up;
    } elseif (post('remove_image') === '1') {
        delete_media($image);
        $image = '';
    }
    $vals = [$member ? $member['id'] : null, $athlete, $titleTxt, mb_substr(trim(post('event')), 0, 150), valid_date(post('ach_date')) ? post('ach_date') : null,
        mb_substr(trim(post('details')), 0, 3000), $image, post('show_public') === '1' ? 1 : 0, (int)post('sort_order')];
    if ($old) {
        $vals[] = $id;
        q('UPDATE achievements SET member_id = ?, athlete = ?, title = ?, event = ?, ach_date = ?, details = ?, image = ?, show_public = ?, sort_order = ? WHERE id = ?', $vals);
    } else {
        q('INSERT INTO achievements (member_id, athlete, title, event, ach_date, details, image, show_public, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', $vals);
    }
    flash('success', t('ach_saved', $athlete));
    redirect($back);
}

$members = q("SELECT id, name, adm_no FROM members WHERE status <> 'pending' ORDER BY name")->fetchAll();
$editKey = get('edit');
$edit = $editKey === 'new' ? ['id' => 0, 'member_id' => (int)get('member') ?: null, 'athlete' => '', 'title' => '', 'event' => '', 'ach_date' => today(), 'details' => '', 'image' => '', 'show_public' => 1, 'sort_order' => 0]
    : ($editKey !== '' ? q('SELECT * FROM achievements WHERE id = ?', [(int)$editKey])->fetch() : null);
$fromMember = get('from') === 'member' || ($edit && get('member'));
$list = $edit ? [] : q('SELECT a.*, m.adm_no FROM achievements a LEFT JOIN members m ON m.id = a.member_id ORDER BY a.ach_date IS NULL, a.ach_date DESC, a.id DESC')->fetchAll();

$title = t('achievements');
$active = 'achievements';
$back = $edit ? ($fromMember && $edit['member_id'] ? 'member_view.php?id=' . (int)$edit['member_id'] : 'achievements.php') : 'more.php';
$actions = $edit ? '' : '<a href="home.php#champions" class="btn btn-outline-primary" target="_blank"><i class="bi bi-box-arrow-up-right"></i> ' . e(t('open_public_page')) . '</a>'
    . '<a href="?edit=new" class="btn btn-primary"><i class="bi bi-plus-lg"></i> ' . e(t('add_achievement')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<?php if ($edit): $img = safe_img($edit['image']); ?>
<form method="post" enctype="multipart/form-data" class="card mb-3"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
  <?php if ($fromMember): ?><input type="hidden" name="back" value="member"><?php endif; ?>
  <div class="card-header fw-bold"><i class="bi bi-trophy-fill text-warning"></i> <?= e(t($edit['id'] ? 'edit_achievement' : 'add_achievement')) ?></div>
  <div class="card-body row g-3">
    <div class="col-md-4 text-center">
      <div class="prog-edit-img mb-2"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>><?php if ($img === ''): ?><i class="bi bi-image"></i><?php endif; ?></div>
      <input class="form-control form-control-sm" type="file" name="image" accept="image/*" aria-label="<?= e(t('change_photo')) ?>">
      <?php if ($img !== ''): ?><div class="form-check small mt-1 text-start"><input class="form-check-input" type="checkbox" name="remove_image" value="1" id="rmi"><label class="form-check-label" for="rmi"><?= e(t('remove_photo')) ?></label></div><?php endif; ?>
      <div class="form-text"><?= e(t('ach_photo_help')) ?></div>
    </div>
    <div class="col-md-8 row g-2 m-0 p-0">
      <div class="col-md-6"><label class="form-label small" for="acm"><?= e(t('member')) ?></label>
        <select class="form-select" id="acm" name="member_id" onchange="var n=document.getElementById('acn');if(this.value&&!n.dataset.typed)n.value=this.options[this.selectedIndex].dataset.name">
          <option value=""><?= e(t('not_a_member')) ?></option>
          <?php foreach ($members as $mm): ?><option value="<?= $mm['id'] ?>" data-name="<?= e($mm['name']) ?>"<?= (int)$edit['member_id'] === (int)$mm['id'] ? ' selected' : '' ?>><?= e($mm['name'] . ' (' . $mm['adm_no'] . ')') ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-md-6"><label class="form-label small" for="acn"><?= e(t('athlete_name')) ?> *</label>
        <input class="form-control" id="acn" name="athlete" maxlength="100" oninput="this.dataset.typed=1" value="<?= e($edit['athlete'] !== '' ? $edit['athlete'] : (string)(array_column($members, 'name', 'id')[(int)$edit['member_id']] ?? '')) ?>"></div>
      <div class="col-12"><label class="form-label small" for="act"><?= e(t('achievement')) ?> *</label>
        <input class="form-control" id="act" name="title" maxlength="150" required value="<?= e($edit['title']) ?>" placeholder="<?= e(t('achievement_ph')) ?>"></div>
      <div class="col-md-8"><label class="form-label small" for="ace"><?= e(t('event_place')) ?></label>
        <input class="form-control" id="ace" name="event" maxlength="150" value="<?= e($edit['event']) ?>" placeholder="<?= e(t('event_place_ph')) ?>"></div>
      <div class="col-md-4"><label class="form-label small" for="acd"><?= e(t('date')) ?></label>
        <input class="form-control" type="date" id="acd" name="ach_date" value="<?= e((string)$edit['ach_date']) ?>"></div>
      <div class="col-12"><label class="form-label small" for="acx"><?= e(t('details')) ?></label>
        <textarea class="form-control" id="acx" name="details" rows="3" maxlength="3000" placeholder="<?= e(t('ach_details_ph')) ?>"><?= e((string)$edit['details']) ?></textarea></div>
      <div class="col-8 d-flex align-items-center"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="show_public" value="1" id="acp"<?= $edit['show_public'] ? ' checked' : '' ?>>
        <label class="form-check-label" for="acp"><?= e(t('show_on_public')) ?></label></div></div>
      <div class="col-4"><label class="form-label small" for="aco"><?= e(t('sort_order')) ?></label><input class="form-control" type="number" id="aco" name="sort_order" value="<?= (int)$edit['sort_order'] ?>"></div>
    </div>
    <div class="col-12 d-flex gap-2"><a href="<?= e($back) ?>" class="btn btn-light"><?= e(t('cancel')) ?></a><button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
  </div>
</form>
<?php if ($edit['id']): ?>
  <form method="post" class="text-end mb-4" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
    <?php if ($fromMember): ?><input type="hidden" name="back" value="member"><input type="hidden" name="member_id" value="<?= (int)$edit['member_id'] ?>"><?php endif; ?>
    <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button></form>
<?php endif; ?>
<?php else: ?>
  <p class="small-muted"><?= e(t('achievements_help')) ?></p>
  <?php if (!$list): ?><div class="card card-body text-muted"><?= e(t('no_achievements')) ?></div><?php endif; ?>
  <div class="card"><div class="list-group list-group-flush">
    <?php foreach ($list as $a): $img = safe_img($a['image']); ?>
      <a href="?edit=<?= $a['id'] ?>" class="list-group-item list-group-item-action d-flex align-items-center gap-3">
        <span class="ach-thumb"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>><?php if ($img === ''): ?><i class="bi bi-trophy-fill"></i><?php endif; ?></span>
        <span class="me-auto"><span class="fw-semibold d-block"><?= e($a['title']) ?></span>
          <span class="small-muted"><?= e($a['athlete']) ?><?= $a['adm_no'] ? ' (' . e($a['adm_no']) . ')' : '' ?><?= $a['event'] !== '' ? ' · ' . e($a['event']) : '' ?><?= $a['ach_date'] ? ' · ' . e(fdate($a['ach_date'])) : '' ?></span></span>
        <span class="badge <?= $a['show_public'] ? 'bg-success' : 'text-bg-light border' ?>"><?= e(t($a['show_public'] ? 'public' : 'hidden')) ?></span>
      </a>
    <?php endforeach; ?>
  </div></div>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
