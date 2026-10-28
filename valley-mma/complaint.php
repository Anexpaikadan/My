<?php
// One complaint: the messages, reply, change the status, send the reply to the member on WhatsApp.

require __DIR__ . '/includes/init.php';
require_admin();

$id = (int)(post('id') ?: get('id'));
$c = q('SELECT c.*, m.name, m.phone, m.adm_no FROM complaints c LEFT JOIN members m ON m.id = c.member_id WHERE c.id = ?', [$id])->fetch();
if (!$c) {
    redirect('complaints.php');
}
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (post('action') === 'delete') {
        require_verify('complaint.php?id=' . $id);
        q('DELETE FROM complaints WHERE id = ?', [$id]);
        flash('success', t('deleted'));
        redirect('complaints.php');
    }
    $msg = mb_substr(trim(post('message')), 0, 3000);
    $status = in_array(post('status'), ['open', 'progress', 'resolved'], true) ? post('status') : $c['status'];
    if ($msg !== '') {
        complaint_add_msg($id, true, $msg);
        if (!$c['member_id']) {
            q('UPDATE complaints SET member_unread = 0 WHERE id = ?', [$id]);
        }
    }
    if ($status !== $c['status']) {
        q('UPDATE complaints SET status = ?, updated_at = NOW(), member_unread = ? WHERE id = ?', [$status, $c['member_id'] ? 1 : 0, $id]);
    }
    flash('success', t('saved'));
    redirect('complaint.php?id=' . $id . ($msg !== '' && $c['phone'] ? '&sent=1' : '') . '#reply');
}
if ($c['admin_unread']) {
    q('UPDATE complaints SET admin_unread = 0 WHERE id = ?', [$id]);
}
$msgs = q('SELECT x.*, a.username FROM complaint_msgs x LEFT JOIN admins a ON a.id = x.admin_id WHERE x.complaint_id = ? ORDER BY x.id', [$id])->fetchAll();
$lastAdmin = null;
foreach ($msgs as $x) {
    if ($x['by_admin']) {
        $lastAdmin = $x;
    }
}

$title = t('complaint') . ' #' . $id;
$active = 'complaints';
$back = 'complaints.php?tab=' . $c['status'];
require __DIR__ . '/includes/header.php';
?>
<div class="card mb-3"><div class="card-body">
  <div class="d-flex gap-2 align-items-start">
    <i class="bi <?= COMPLAINT_CATS[$c['category']] ?? 'bi-chat-dots' ?> fs-3 text-primary"></i>
    <div class="me-auto">
      <h2 class="h5 mb-1"><?= e($c['subject']) ?></h2>
      <div class="small-muted"><?= e(t('cc_' . $c['category'])) ?> · <?= e(fdate($c['created_at'])) ?>
        · <?php if ($c['member_id']): ?><a href="member_view.php?id=<?= $c['member_id'] ?>"><?= e($c['name']) ?></a><?php else: ?><?= e(t('general_no_member')) ?><?php endif; ?></div>
    </div>
    <?= complaint_badge($c['status']) ?>
  </div>
</div></div>

<div class="chat mb-3">
  <?php foreach ($msgs as $x): ?>
    <div class="chat-msg <?= $x['by_admin'] ? 'me' : 'them' ?>">
      <div class="chat-who"><?= e($x['by_admin'] ? t('gym') . ($x['username'] ? ' (' . $x['username'] . ')' : '') : ($c['name'] ?? t('member'))) ?> · <?= e(date('d-m-Y H:i', strtotime($x['created_at']))) ?></div>
      <div class="chat-text"><?= nl2br(e($x['message'])) ?></div>
    </div>
  <?php endforeach; ?>
</div>

<?php if ($c['phone'] && $lastAdmin): ?>
  <a class="btn btn-whatsapp w-100 mb-3<?= get('sent') ? ' pulse' : '' ?>" target="_blank" rel="noopener" data-sent
     href="<?= e(wa_link($c['phone'], t('wa_complaint_reply', $c['name'], $c['subject'], t('cs_' . (get('sent') ? q('SELECT status FROM complaints WHERE id = ?', [$id])->fetchColumn() : $c['status'])), $lastAdmin['message'], base_url() . 'me_complaints.php?id=' . $id))) ?>">
    <i class="bi bi-whatsapp"></i> <?= e(t('send_reply_whatsapp')) ?></a>
<?php endif; ?>

<form method="post" class="card mb-3" id="reply"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>">
  <div class="card-body">
    <label class="form-label small" for="rm"><?= e(t('reply')) ?></label>
    <textarea class="form-control mb-2" id="rm" name="message" rows="3" maxlength="3000" placeholder="<?= e(t('reply_ph')) ?>"></textarea>
    <div class="d-flex flex-wrap gap-1 mb-3 cat-opt">
      <?php foreach (['open', 'progress', 'resolved'] as $k): ?>
        <input type="radio" class="btn-check" name="status" value="<?= $k ?>" id="st<?= $k ?>"<?= $c['status'] === $k ? ' checked' : '' ?>>
        <label class="btn btn-sm btn-outline-primary" for="st<?= $k ?>"><?= e(t('cs_' . $k)) ?></label>
      <?php endforeach; ?>
    </div>
    <button class="btn btn-primary w-100"><i class="bi bi-send"></i> <?= e(t('save_reply')) ?></button>
  </div>
</form>
<form method="post" class="text-end" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="delete">
  <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button></form>
<?php require __DIR__ . '/includes/footer.php';
