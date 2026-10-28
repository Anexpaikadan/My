<?php
// Complaints and suggestions from members (member app) and written by the admin. Open one to reply.

require __DIR__ . '/includes/init.php';
require_admin();

$members = q("SELECT id, name, adm_no FROM members WHERE status <> 'pending' ORDER BY name")->fetchAll();
if ($_SERVER['REQUEST_METHOD'] === 'POST') { // the admin writes a complaint (for a member, or a general one)
    $subject = mb_substr(trim(post('subject')), 0, 150);
    $msg = mb_substr(trim(post('message')), 0, 3000);
    $cat = array_key_exists(post('category'), COMPLAINT_CATS) ? post('category') : 'other';
    $mid = (int)post('member_id') ?: null;
    if ($subject === '' || $msg === '') {
        flash('danger', t('complaint_fill'));
        redirect('complaints.php?new=1');
    }
    q('INSERT INTO complaints (member_id, category, subject, by_admin) VALUES (?, ?, ?, 1)', [$mid, $cat, $subject]);
    $id = (int)db()->lastInsertId();
    complaint_add_msg($id, true, $msg);
    if (!$mid) {
        q('UPDATE complaints SET member_unread = 0 WHERE id = ?', [$id]);
    }
    flash('success', t('complaint_saved'));
    redirect('complaint.php?id=' . $id);
}

$tab = in_array(get('tab'), ['open', 'progress', 'resolved', 'all'], true) ? get('tab') : 'open';
$counts = q('SELECT status, COUNT(*) FROM complaints GROUP BY status')->fetchAll(PDO::FETCH_KEY_PAIR);
$rows = q('SELECT c.*, m.name, m.adm_no, (SELECT COUNT(*) FROM complaint_msgs x WHERE x.complaint_id = c.id) msgs
           FROM complaints c LEFT JOIN members m ON m.id = c.member_id'
    . ($tab === 'all' ? '' : ' WHERE c.status = ?') . ' ORDER BY c.admin_unread DESC, c.updated_at DESC LIMIT 200', $tab === 'all' ? [] : [$tab])->fetchAll();

$title = t('complaints');
$active = 'complaints';
$back = 'more.php';
$actions = '<button class="btn btn-primary" data-bs-toggle="collapse" data-bs-target="#newC"><i class="bi bi-plus-lg"></i> ' . e(t('new_complaint')) . '</button>';
require __DIR__ . '/includes/header.php';
?>
<form method="post" class="card mb-3 collapse<?= get('new') ? ' show' : '' ?>" id="newC"><?= csrf_field() ?>
  <div class="card-body">
    <div class="row g-2">
      <div class="col-md-6"><label class="form-label small" for="cm"><?= e(t('member')) ?></label>
        <select class="form-select" id="cm" name="member_id"><option value=""><?= e(t('general_no_member')) ?></option>
          <?php foreach ($members as $mm): ?><option value="<?= $mm['id'] ?>"<?= (int)get('member') === (int)$mm['id'] ? ' selected' : '' ?>><?= e($mm['name'] . ' (' . $mm['adm_no'] . ')') ?></option><?php endforeach; ?></select></div>
      <div class="col-md-6"><label class="form-label small" for="cc"><?= e(t('category')) ?></label>
        <select class="form-select" id="cc" name="category"><?php foreach (COMPLAINT_CATS as $k => $ic): ?><option value="<?= $k ?>"><?= e(t('cc_' . $k)) ?></option><?php endforeach; ?></select></div>
      <div class="col-12"><label class="form-label small" for="cs"><?= e(t('subject')) ?></label><input class="form-control" id="cs" name="subject" maxlength="150" required></div>
      <div class="col-12"><label class="form-label small" for="ct"><?= e(t('details')) ?></label><textarea class="form-control" id="ct" name="message" rows="3" maxlength="3000" required></textarea></div>
    </div>
    <button class="btn btn-primary w-100 mt-3"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
  </div>
</form>

<ul class="nav nav-pills mb-3 flex-nowrap overflow-auto">
  <?php foreach (['open', 'progress', 'resolved', 'all'] as $k): ?>
    <li class="nav-item"><a class="nav-link text-nowrap<?= $tab === $k ? ' active' : '' ?>" href="?tab=<?= $k ?>"><?= e(t($k === 'all' ? 'all' : 'cs_' . $k)) ?>
      <?php if ($k !== 'all'): ?><span class="badge <?= $tab === $k ? 'bg-light text-dark' : 'text-bg-light border' ?>"><?= (int)($counts[$k] ?? 0) ?></span><?php endif; ?></a></li>
  <?php endforeach; ?>
</ul>
<div class="card"><div class="list-group list-group-flush">
  <?php if (!$rows): ?><div class="list-group-item text-muted p-4 text-center"><?= e(t('no_complaints')) ?></div><?php endif; ?>
  <?php foreach ($rows as $c): ?>
    <a href="complaint.php?id=<?= $c['id'] ?>" class="list-group-item list-group-item-action d-flex gap-2 align-items-start">
      <i class="bi <?= COMPLAINT_CATS[$c['category']] ?? 'bi-chat-dots' ?> fs-4 text-primary"></i>
      <div class="me-auto">
        <div class="fw-semibold"><?php if ($c['admin_unread']): ?><span class="badge bg-danger me-1"><?= e(t('new')) ?></span><?php endif; ?><?= e($c['subject']) ?></div>
        <div class="small-muted"><?= e($c['name'] ?? t('general_no_member')) ?> · <?= e(t('cc_' . $c['category'])) ?> · <?= e(fdate($c['updated_at'])) ?> · <i class="bi bi-chat"></i> <?= (int)$c['msgs'] ?>
          <?= $c['by_admin'] ? ' · ' . e(t('by_admin')) : '' ?></div>
      </div>
      <?= complaint_badge($c['status']) ?>
    </a>
  <?php endforeach; ?>
</div></div>
<?php require __DIR__ . '/includes/footer.php';
