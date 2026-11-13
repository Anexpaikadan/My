<?php
// Public page of one event / fight night: photo, date, venue, details and registration.
// A logged-in member registers with one tap; visitors fill in name, place and WhatsApp number.

require_once __DIR__ . '/includes/init.php';

$id = (int)(post('id') ?: get('id'));
$ev = q('SELECT * FROM events WHERE id = ?', [$id])->fetch();
if (!$ev || (!$ev['show_public'] && !admin())) {
    redirect('home.php');
}
$me = member_user();
$mine = $me ? q('SELECT * FROM event_regs WHERE event_id = ? AND member_id = ?', [$id, $me['id']])->fetch() : null;
$closed = event_closed($ev);
$error = '';
$done = get('done') === '1';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    $note = mb_substr(trim(post('note')), 0, 200);
    if (post('website') !== '') { // hidden field: only robots fill it
        redirect('event.php?id=' . $id);
    }
    if ($me && post('action') === 'cancel' && $mine) {
        q("UPDATE event_regs SET status = 'cancelled' WHERE id = ?", [$mine['id']]);
        redirect('event.php?id=' . $id);
    }
    if ($closed !== '') {
        $error = t($closed);
    } elseif ($me) {
        if ($me['status'] !== 'active') {
            $error = t('ev_members_only_active');
        } elseif ($mine) {
            q("UPDATE event_regs SET status = 'registered', note = ? WHERE id = ?", [$note, $mine['id']]);
        } else {
            q('INSERT INTO event_regs (event_id, member_id, name, phone, place, note, ip) VALUES (?, ?, ?, ?, ?, ?, ?)',
                [$id, $me['id'], $me['name'], $me['phone'], (string)$me['place'], $note, $ip]);
        }
    } else {
        $name = mb_substr(trim(post('name')), 0, 100);
        $phone = clean_phone(post('phone'));
        if (!$ev['allow_public']) {
            $error = t('ev_members_only');
        } elseif ($name === '' || !preg_match('/^\+?\d{10,15}$/', $phone)) {
            $error = t('trial_fill');
        } elseif ((int)q('SELECT COUNT(*) FROM event_regs WHERE ip = ? AND created_at > NOW() - INTERVAL 1 HOUR', [$ip])->fetchColumn() >= 8) {
            $error = t('too_many');
        } else {
            $digits = substr(preg_replace('/\D/', '', $phone), -10);
            $same = q('SELECT id FROM event_regs WHERE event_id = ? AND phone LIKE ?', [$id, '%' . $digits])->fetch();
            if ($same) {
                q("UPDATE event_regs SET name = ?, place = ?, note = ?, status = IF(status = 'cancelled', 'registered', status) WHERE id = ?",
                    [$name, mb_substr(trim(post('place')), 0, 100), $note, $same['id']]);
            } else {
                q('INSERT INTO event_regs (event_id, name, phone, place, note, ip) VALUES (?, ?, ?, ?, ?, ?)',
                    [$id, $name, $phone, mb_substr(trim(post('place')), 0, 100), $note, $ip]);
            }
        }
    }
    if ($error === '') {
        redirect('event.php?id=' . $id . '&done=1');
    }
}

$img = safe_img($ev['image']);
$registered = $mine && $mine['status'] !== 'cancelled';
$count = (int)q("SELECT COUNT(*) FROM event_regs WHERE event_id = ? AND status <> 'cancelled'", [$id])->fetchColumn();
$wa = wa_link(pub_wa_phone(), t('wa_event_ask', $ev['title']));

$title = $ev['title'];
$bare = true;
$publicPage = 'home';
if ($img !== '') { // this event's photo in WhatsApp link previews
    $GLOBALS['vm_og_image'] = $img;
}
require __DIR__ . '/includes/header.php';
?>
<div class="ev-hero<?= $img === '' ? ' noimg' : '' ?>"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>>
  <a href="home.php#events" class="btn btn-dark btn-back ev-back" aria-label="<?= e(t('back')) ?>"><i class="bi bi-arrow-left"></i></a>
  <?php if ($img === ''): ?><i class="bi <?= EVENT_KINDS[$ev['kind']] ?>"></i><?php endif; ?>
</div>
<div class="pub-wrap ev-page">
  <span class="ev-kind static"><i class="bi <?= EVENT_KINDS[$ev['kind']] ?>"></i> <?= e(t('evk_' . $ev['kind'])) ?></span>
  <h1 class="ev-h"><?= e($ev['title']) ?></h1>
  <div class="info-rows">
    <div class="info-row"><i class="bi bi-calendar-event"></i><span><small><?= e(t('date')) ?></small><b><?= e(event_when($ev)) ?></b></span></div>
    <?php if ($ev['venue'] !== ''): ?><div class="info-row"><i class="bi bi-geo-alt-fill"></i><span><small><?= e(t('ev_venue')) ?></small><b><?= e($ev['venue']) ?></b></span></div><?php endif; ?>
    <?php if ((float)$ev['fee'] > 0): ?><div class="info-row"><i class="bi bi-cash-coin"></i><span><small><?= e(t('ev_fee')) ?></small><b><?= money($ev['fee']) ?></b></span></div><?php endif; ?>
    <div class="info-row"><i class="bi bi-people-fill"></i><span><small><?= e(t('ev_registered')) ?></small><b><?= $count ?><?= $ev['capacity'] ? ' / ' . (int)$ev['capacity'] : '' ?></b></span></div>
  </div>
  <?php if (trim((string)$ev['description']) !== ''): ?><p class="ev-desc"><?= nl2br(e($ev['description'])) ?></p><?php endif; ?>

  <?php if ($done && $error === ''): ?>
    <div class="pub-card mb-3 pop-in"><i class="bi bi-check-circle-fill text-success" style="font-size:3rem"></i>
      <h2 class="h5 mt-2"><?= e(t('ev_done')) ?></h2><p class="mb-0" style="color:#c9c5c5"><?= e(t('ev_done_help')) ?></p></div>
  <?php endif; ?>
  <?php if ($error !== ''): ?><div class="alert alert-danger"><?= e($error) ?></div><?php endif; ?>

  <?php if ($registered): ?>
    <div class="pub-card mb-3 text-start"><div class="d-flex align-items-center gap-2"><i class="bi bi-patch-check-fill text-success fs-3"></i>
      <div class="me-auto"><b><?= e(t('ev_you_registered')) ?></b><div class="small" style="color:#c9c5c5"><?= e(t('evs_' . $mine['status'])) ?><?= $mine['note'] !== '' ? ' · ' . e($mine['note']) : '' ?></div></div></div>
      <?php if ($closed === ''): ?><form method="post" class="mt-2"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="cancel">
        <button class="btn btn-sm btn-outline-light"><?= e(t('ev_cancel_mine')) ?></button></form><?php endif; ?>
    </div>
  <?php elseif ($closed !== ''): ?>
    <div class="pub-card mb-3"><i class="bi bi-lock-fill"></i> <?= e(t($closed)) ?></div>
  <?php elseif ($me): ?>
    <form method="post" class="pub-card mb-3 text-start"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>">
      <div class="fw-bold mb-2"><?= e(t('ev_register_as', $me['name'])) ?></div>
      <input class="form-control form-control-lg mb-2" name="note" maxlength="200" placeholder="<?= e(t('ev_note_ph')) ?>">
      <button class="btn btn-primary btn-lg w-100 trial-btn"><i class="bi bi-lightning-charge-fill"></i> <?= e(t('ev_register')) ?></button>
    </form>
  <?php elseif ($ev['allow_public']): ?>
    <form method="post" class="pub-card mb-3 text-start" id="register"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>">
      <div class="fw-bold fs-5 mb-2"><i class="bi bi-lightning-charge-fill text-primary"></i> <?= e(t('ev_register')) ?></div>
      <div class="d-none"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
      <label class="form-label small" for="rn"><?= e(t('name')) ?> *</label>
      <input class="form-control form-control-lg mb-2" id="rn" name="name" maxlength="100" required autocomplete="name" value="<?= e(post('name')) ?>">
      <label class="form-label small" for="rp"><?= e(t('place')) ?></label>
      <input class="form-control form-control-lg mb-2" id="rp" name="place" maxlength="100" value="<?= e(post('place')) ?>">
      <label class="form-label small" for="rw"><?= e(t('whatsapp_number')) ?> *</label>
      <input class="form-control form-control-lg mb-2" id="rw" name="phone" type="tel" inputmode="tel" required pattern="[+0-9 ]{10,16}" placeholder="9XXXXXXXXX" value="<?= e(post('phone')) ?>">
      <label class="form-label small" for="ro"><?= e(t('ev_note')) ?></label>
      <input class="form-control form-control-lg mb-3" id="ro" name="note" maxlength="200" placeholder="<?= e(t('ev_note_ph')) ?>" value="<?= e(post('note')) ?>">
      <button class="btn btn-primary btn-lg w-100 trial-btn"><i class="bi bi-send"></i> <?= e(t('ev_register')) ?></button>
      <div class="small mt-2 text-center" style="color:#b5b1b1"><?= e(t('ev_member_login')) ?> <a href="me.php" class="text-white"><?= e(t('login')) ?></a></div>
    </form>
  <?php else: ?>
    <div class="pub-card mb-3"><?= e(t('ev_members_only')) ?> <a href="me.php" class="btn btn-primary w-100 mt-2"><?= e(t('member_login')) ?></a></div>
  <?php endif; ?>
  <a href="<?= e($wa) ?>" class="btn btn-whatsapp w-100 mb-2" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(t('ev_ask_whatsapp')) ?></a>
  <a href="<?= e(wa_link('', event_text($ev))) ?>" class="btn btn-outline-light w-100" target="_blank" rel="noopener"><i class="bi bi-share"></i> <?= e(t('ev_share_friends')) ?></a>
</div>
<?php require __DIR__ . '/includes/footer.php';
