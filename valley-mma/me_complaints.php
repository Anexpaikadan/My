<?php
// Member app: write a complaint or suggestion to the gym, see the gym's replies and answer them.

require __DIR__ . '/includes/init.php';

$m = member_user();
if (!$m) {
    redirect('me.php');
}
$id = (int)(post('id') ?: get('id'));
$c = $id ? q('SELECT * FROM complaints WHERE id = ? AND member_id = ?', [$id, $m['id']])->fetch() : null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $msg = mb_substr(trim(post('message')), 0, 3000);
    if ($msg === '') {
        redirect('me_complaints.php' . ($c ? '?id=' . $c['id'] : ''));
    }
    if ($c) { // reply in an existing complaint (opens it again when it was resolved)
        complaint_add_msg((int)$c['id'], false, $msg);
        if ($c['status'] === 'resolved') {
            q("UPDATE complaints SET status = 'open' WHERE id = ?", [$c['id']]);
        }
        redirect('me_complaints.php?id=' . $c['id']);
    }
    $subject = mb_substr(trim(post('subject')), 0, 150);
    $cat = array_key_exists(post('category'), COMPLAINT_CATS) ? post('category') : 'other';
    if ($subject === '') {
        $subject = mb_substr($msg, 0, 60);
    }
    q('INSERT INTO complaints (member_id, category, subject) VALUES (?, ?, ?)', [$m['id'], $cat, $subject]);
    $newId = (int)db()->lastInsertId();
    complaint_add_msg($newId, false, $msg);
    flash('success', t('complaint_sent'));
    redirect('me_complaints.php?id=' . $newId);
}

if ($c && $c['member_unread']) {
    q('UPDATE complaints SET member_unread = 0 WHERE id = ?', [$c['id']]);
}
$title = t('complaints');
$bare = true;
$memberApp = true;
require __DIR__ . '/includes/header.php';
?>
<div class="d-flex align-items-center gap-2 mb-3 pt-2">
  <a href="<?= $c ? 'me_complaints.php' : 'me.php' ?>" class="btn btn-light btn-back" aria-label="<?= e(t('back')) ?>"><i class="bi bi-arrow-left"></i></a>
  <h1 class="h5 mb-0 me-auto"><?= e($c ? $c['subject'] : t('complaints_suggestions')) ?></h1>
  <?php if ($c) echo complaint_badge($c['status']); ?>
</div>
<?= flashes() ?>

<?php if ($c):
    $msgs = q('SELECT * FROM complaint_msgs WHERE complaint_id = ? ORDER BY id', [$c['id']])->fetchAll(); ?>
  <div class="small-muted mb-2"><?= e(t('cc_' . $c['category'])) ?> · <?= e(fdate($c['created_at'])) ?></div>
  <div class="chat mb-3">
    <?php foreach ($msgs as $x): ?>
      <div class="chat-msg <?= $x['by_admin'] ? 'them' : 'me' ?>">
        <div class="chat-who"><?= e($x['by_admin'] ? gym_title() : t('you')) ?> · <?= e(date('d-m-Y H:i', strtotime($x['created_at']))) ?></div>
        <div class="chat-text"><?= nl2br(e($x['message'])) ?></div>
      </div>
    <?php endforeach; ?>
  </div>
  <form method="post" class="card mb-3"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $c['id'] ?>">
    <div class="card-body">
      <textarea class="form-control mb-2" name="message" rows="3" maxlength="3000" required placeholder="<?= e(t('reply_ph')) ?>"></textarea>
      <button class="btn btn-primary w-100"><i class="bi bi-send"></i> <?= e(t('send')) ?></button>
    </div>
  </form>
<?php else:
    $list = q('SELECT * FROM complaints WHERE member_id = ? ORDER BY updated_at DESC', [$m['id']])->fetchAll(); ?>
  <form method="post" class="card mb-3"><?= csrf_field() ?>
    <div class="card-header fw-bold"><i class="bi bi-pencil-square text-primary"></i> <?= e(t('new_complaint')) ?></div>
    <div class="card-body">
      <div class="d-flex flex-wrap gap-1 mb-2 cat-opt">
        <?php foreach (COMPLAINT_CATS as $k => $ic): ?>
          <input type="radio" class="btn-check" name="category" value="<?= $k ?>" id="cat<?= $k ?>"<?= $k === 'other' ? ' checked' : '' ?>>
          <label class="btn btn-sm btn-outline-primary" for="cat<?= $k ?>"><i class="bi <?= $ic ?>"></i> <?= e(t('cc_' . $k)) ?></label>
        <?php endforeach; ?>
      </div>
      <input class="form-control mb-2" name="subject" maxlength="150" placeholder="<?= e(t('subject')) ?>">
      <textarea class="form-control mb-2" name="message" rows="4" maxlength="3000" required placeholder="<?= e(t('complaint_ph')) ?>"></textarea>
      <button class="btn btn-primary w-100"><i class="bi bi-send"></i> <?= e(t('send_to_gym')) ?></button>
      <div class="form-text"><?= e(t('complaint_private')) ?></div>
    </div>
  </form>
  <h2 class="section-head"><?= e(t('my_complaints')) ?></h2>
  <div class="card mb-3"><div class="list-group list-group-flush">
    <?php if (!$list): ?><div class="list-group-item text-muted"><?= e(t('no_complaints')) ?></div><?php endif; ?>
    <?php foreach ($list as $x): ?>
      <a href="?id=<?= $x['id'] ?>" class="list-group-item list-group-item-action d-flex align-items-center gap-2">
        <i class="bi <?= COMPLAINT_CATS[$x['category']] ?? 'bi-chat-dots' ?> text-primary"></i>
        <span class="me-auto"><?php if ($x['member_unread']): ?><span class="badge bg-danger me-1"><?= e(t('new_reply')) ?></span><?php endif; ?><?= e($x['subject']) ?>
          <span class="d-block small-muted"><?= e(fdate($x['updated_at'])) ?></span></span>
        <?= complaint_badge($x['status']) ?>
      </a>
    <?php endforeach; ?>
  </div></div>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
