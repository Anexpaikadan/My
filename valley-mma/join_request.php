<?php
// One join request: chat on WhatsApp, send the join link with a password and free trial days,
// change the status (new, following, waiting, trial attended, joined, not interested), notes, delete.

require __DIR__ . '/includes/init.php';
require_admin();

const REQ_STATUS = ['new' => 'danger', 'following' => 'primary', 'waiting' => 'warning text-dark', 'trial' => 'info text-dark', 'joined' => 'success', 'not_interested' => 'secondary'];

$id = (int)(post('id') ?: get('id'));
$r = q('SELECT * FROM join_requests WHERE id = ?', [$id])->fetch();
if (!$r) {
    redirect('join_requests.php');
}
$back = 'join_request.php?id=' . $id;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = post('action');
    if ($action === 'delete') {
        require_verify($back);
        q('DELETE FROM join_requests WHERE id = ?', [$id]);
        flash('success', t('deleted'));
        redirect('join_requests.php');
    }
    if ($action === 'status') {
        $st = array_key_exists(post('status'), REQ_STATUS) ? post('status') : $r['status'];
        q('UPDATE join_requests SET status = ?, note = ?, updated_at = NOW() WHERE id = ?', [$st, mb_substr(trim(post('note')), 0, 1000), $id]);
        flash('success', t('saved'));
        redirect($back);
    }
    if ($action === 'invite') { // make the member (join link + password), optional free trial days
        $pass = (string)($_POST['password'] ?? '');
        $days = max(0, min(60, (int)post('trial_days')));
        $start = valid_date(post('trial_date')) ? post('trial_date') : today();
        if (strlen($pass) < 4) {
            flash('danger', t('err_password_short'));
            redirect($back);
        }
        $m = $r['member_id'] ? q('SELECT * FROM members WHERE id = ?', [$r['member_id']])->fetch() : null;
        if (!$m) {
            $digits = substr(preg_replace('/\D/', '', $r['phone']), -10);
            $m = q('SELECT * FROM members WHERE phone LIKE ? ORDER BY id DESC LIMIT 1', ['%' . $digits])->fetch() ?: null;
        }
        $hash = password_hash($pass, PASSWORD_DEFAULT);
        if ($m) { // already in the app: new password and join link
            q('UPDATE members SET password_hash = ?, invite_token = COALESCE(invite_token, ?) WHERE id = ?', [$hash, bin2hex(random_bytes(16)), $m['id']]);
            $mid = (int)$m['id'];
        } else {
            q("INSERT INTO members (adm_no, name, phone, place, join_date, password_hash, card_token, status, invite_token, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                [next_adm_no(), $r['name'], $r['phone'], $r['place'], today(), $hash, bin2hex(random_bytes(8)), bin2hex(random_bytes(16)),
                    mb_substr(t_en('from_trial_request') . ($r['program'] !== '' ? ' (' . $r['program'] . ')' : ''), 0, 500)]);
            $mid = (int)db()->lastInsertId();
        }
        if ($days > 0) { // free trial: active (can mark attendance) for these days, then approve with a payment
            $end = date('Y-m-d', strtotime($start . ' +' . ($days - 1) . ' day'));
            q("UPDATE members SET status = IF(status = 'inactive', status, 'active'), start_date = COALESCE(start_date, ?),
               expiry_date = IF(expiry_date IS NULL OR expiry_date < ?, ?, expiry_date), approved_at = COALESCE(approved_at, NOW()) WHERE id = ?",
                [$start, $end, $end, $mid]);
        }
        q("UPDATE join_requests SET member_id = ?, trial_date = ?, trial_days = ?, status = IF(status IN ('new', 'following'), 'waiting', status), updated_at = NOW() WHERE id = ?",
            [$mid, $days > 0 ? $start : null, $days, $id]);
        $_SESSION['invite_pass'][$mid] = $pass;
        flash('success', t('join_link_ready'));
        redirect($back . '#invite');
    }
}

$m = $r['member_id'] ? q('SELECT * FROM members WHERE id = ?', [$r['member_id']])->fetch() : null;
$pass = $m ? (string)($_SESSION['invite_pass'][$m['id']] ?? '') : '';
$inviteMsg = '';
if ($m && $m['invite_token']) {
    $inviteMsg = invite_text($m, $pass);
    if ($r['trial_days'] > 0) {
        $inviteMsg .= "\n\n" . t('wa_trial_days', (int)$r['trial_days'], fdate($r['trial_date']),
            fdate(date('Y-m-d', strtotime($r['trial_date'] . ' +' . ((int)$r['trial_days'] - 1) . ' day'))));
    }
    $inviteMsg .= "\n\n" . base_url() . 'rules.php';
}
$chat = wa_link($r['phone'], t('wa_trial_hello', $r['name'], gym_title()));

$title = $r['name'];
$active = 'requests';
$back = 'join_requests.php';
require __DIR__ . '/includes/header.php';
?>
<div class="row g-3">
  <div class="col-lg-5">
    <div class="card mb-3"><div class="card-body">
      <div class="d-flex align-items-center gap-3 mb-3">
        <span class="req-ava big"><?= e(mb_strtoupper(mb_substr($r['name'], 0, 1))) ?></span>
        <div class="me-auto"><div class="fw-bold fs-5"><?= e($r['name']) ?></div>
          <div class="small-muted"><?= e($r['place']) ?><?= $r['program'] !== '' ? ' · ' . e($r['program']) : '' ?></div>
          <div class="small-muted"><?= e(t('requested_on', fdate($r['created_at']))) ?></div></div>
        <span class="badge bg-<?= REQ_STATUS[$r['status']] ?>"><?= e(t('rq_' . $r['status'])) ?></span>
      </div>
      <div class="d-grid gap-2">
        <a class="btn btn-whatsapp btn-lg" href="<?= e($chat) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(t('chat_whatsapp')) ?></a>
        <a class="btn btn-light" href="tel:<?= e(clean_phone($r['phone'])) ?>"><i class="bi bi-telephone-fill"></i> <?= e($r['phone']) ?></a>
        <?php if ($m): ?><a class="btn btn-outline-primary" href="member_view.php?id=<?= $m['id'] ?>"><i class="bi bi-person-badge"></i> <?= e(t('open_member')) ?> · <?= e($m['adm_no']) ?></a><?php endif; ?>
      </div>
    </div></div>

    <form method="post" class="card mb-3"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="status">
      <div class="card-header fw-bold"><i class="bi bi-flag-fill text-primary"></i> <?= e(t('status')) ?></div>
      <div class="card-body">
        <div class="d-flex flex-wrap gap-1 mb-3 cat-opt">
          <?php foreach (REQ_STATUS as $k => $cls): ?>
            <input type="radio" class="btn-check" name="status" value="<?= $k ?>" id="rs<?= $k ?>"<?= $r['status'] === $k ? ' checked' : '' ?>>
            <label class="btn btn-sm btn-outline-primary" for="rs<?= $k ?>"><?= e(t('rq_' . $k)) ?></label>
          <?php endforeach; ?>
        </div>
        <label class="form-label small" for="rnote"><?= e(t('notes')) ?></label>
        <textarea class="form-control mb-2" id="rnote" name="note" rows="3" maxlength="1000" placeholder="<?= e(t('request_note_ph')) ?>"><?= e($r['note']) ?></textarea>
        <button class="btn btn-primary w-100"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
      </div>
    </form>
    <?php if (in_array($r['status'], ['joined', 'not_interested'], true)): ?>
      <form method="post" class="mb-3" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="delete">
        <button class="btn btn-outline-danger w-100"><i class="bi bi-trash"></i> <?= e(t('delete_request')) ?></button></form>
    <?php endif; ?>
  </div>

  <div class="col-lg-7">
    <div class="card mb-3" id="invite"><div class="card-header fw-bold"><i class="bi bi-link-45deg text-primary"></i> <?= e(t('send_join_link')) ?></div>
      <div class="card-body">
        <?php if ($inviteMsg !== ''): ?>
          <div class="alert alert-success small mb-3">
            <div class="fw-semibold mb-1"><i class="bi bi-check-circle-fill"></i> <?= e(t('join_link_ready')) ?></div>
            <div><?= e(t('phone_no')) ?>: <b><?= e($m['phone']) ?></b><?= $pass !== '' ? ' · ' . e(t('password')) . ': <b>' . e($pass) . '</b>' : '' ?></div>
            <?php if ($r['trial_days'] > 0): ?><div><?= e(t('free_trial')) ?>: <b><?= e(t('n_days', (int)$r['trial_days'])) ?></b> · <?= e(t('from_date')) ?> <?= e(fdate($r['trial_date'])) ?></div><?php endif; ?>
          </div>
          <a class="btn btn-whatsapp btn-lg w-100 mb-3<?= $pass !== '' ? ' pulse' : '' ?>" href="<?= e(wa_link($m['phone'], $inviteMsg)) ?>" target="_blank" rel="noopener" data-sent><i class="bi bi-whatsapp"></i> <?= e(t('send_link_whatsapp')) ?></a>
          <p class="small-muted"><?= e(t('send_again_help')) ?></p>
        <?php else: ?>
          <p class="small-muted"><?= e(t('send_join_link_help')) ?></p>
        <?php endif; ?>
        <form method="post"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="invite">
          <div class="row g-2">
            <div class="col-12"><label class="form-label small" for="ipw"><?= e(t('password')) ?></label>
              <div class="input-group"><input class="form-control" id="ipw" name="password" value="<?= e((string)random_int(100000, 999999)) ?>" minlength="4" required>
                <button class="btn btn-outline-secondary" type="button" data-random-pass="#ipw" aria-label="New"><i class="bi bi-shuffle"></i></button></div></div>
            <div class="col-6"><label class="form-label small" for="itd"><?= e(t('trial_from')) ?></label>
              <input class="form-control" type="date" id="itd" name="trial_date" value="<?= e($r['trial_date'] ?: today()) ?>"></div>
            <div class="col-6"><label class="form-label small" for="itn"><?= e(t('free_trial_days')) ?></label>
              <input class="form-control" type="number" id="itn" name="trial_days" min="0" max="60" value="<?= (int)($r['trial_days'] ?: 1) ?>"></div>
            <div class="col-12 form-text mt-0"><?= e(t('trial_days_help')) ?></div>
          </div>
          <button class="btn btn-primary w-100 mt-2"><i class="bi bi-link-45deg"></i> <?= e(t($inviteMsg !== '' ? 'make_new_link' : 'make_join_link')) ?></button>
        </form>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
