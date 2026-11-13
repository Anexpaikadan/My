<?php
// Events and fight nights (admin): create an event with photo, date, venue and fee; see who registered
// (members and visitors), confirm them, mark the fee as paid, message them and share the event on WhatsApp.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    $ev = $id ? q('SELECT * FROM events WHERE id = ?', [$id])->fetch() : null;
    $action = post('action');
    if ($action === 'delete') {
        require_verify('events.php?edit=' . $id);
        if ($ev) {
            delete_media($ev['image']);
            q('DELETE FROM events WHERE id = ?', [$id]);
            flash('success', t('deleted'));
        }
        redirect('events.php');
    }
    if ($action === 'reg' && $ev) { // change one registration
        $rid = (int)post('reg_id');
        $do = post('do');
        if ($do === 'remove') {
            require_verify('events.php?id=' . $id);
            q('DELETE FROM event_regs WHERE id = ? AND event_id = ?', [$rid, $id]);
        } elseif (in_array($do, ['registered', 'confirmed', 'cancelled'], true)) {
            q('UPDATE event_regs SET status = ? WHERE id = ? AND event_id = ?', [$do, $rid, $id]);
        } elseif ($do === 'paid' || $do === 'unpaid') {
            q('UPDATE event_regs SET paid = ? WHERE id = ? AND event_id = ?', [$do === 'paid' ? 1 : 0, $rid, $id]);
        }
        redirect('events.php?id=' . $id . '#regs');
    }
    if ($action === 'add_member' && $ev) { // the admin registers a member
        $m = q('SELECT id, name, phone, place FROM members WHERE id = ?', [(int)post('member_id')])->fetch();
        if ($m && !q('SELECT COUNT(*) FROM event_regs WHERE event_id = ? AND member_id = ?', [$id, $m['id']])->fetchColumn()) {
            q("INSERT INTO event_regs (event_id, member_id, name, phone, place, note, status) VALUES (?, ?, ?, ?, ?, ?, 'confirmed')",
                [$id, $m['id'], $m['name'], $m['phone'], (string)$m['place'], mb_substr(trim(post('note')), 0, 200)]);
            flash('success', t('ev_registered_name', $m['name']));
        }
        redirect('events.php?id=' . $id . '#regs');
    }
    // add / change the event
    $title = mb_substr(trim(post('title')), 0, 150);
    $date = valid_date(post('event_date')) ? post('event_date') : '';
    if ($title === '' || $date === '') {
        flash('danger', t('ev_fill'));
        redirect('events.php?edit=' . ($id ?: 'new'));
    }
    $image = $ev['image'] ?? '';
    $up = save_media_upload('image', 'events', 1400);
    if ($up === null) {
        flash('warning', t('err_photo'));
    } elseif ($up !== '') {
        delete_media($image);
        $image = $up;
    } elseif (post('remove_image') === '1') {
        delete_media($image);
        $image = '';
    }
    $vals = [$title, array_key_exists(post('kind'), EVENT_KINDS) ? post('kind') : 'event', $date,
        preg_match('/^\d{2}:\d{2}$/', post('start_time')) ? post('start_time') . ':00' : null, mb_substr(trim(post('venue')), 0, 200),
        mb_substr(trim(post('description')), 0, 4000), $image, max(0, num(post('fee'))), max(0, min(9999, (int)post('capacity'))),
        post('reg_open') === '1' ? 1 : 0, valid_date(post('reg_last')) ? post('reg_last') : null,
        post('allow_public') === '1' ? 1 : 0, post('show_public') === '1' ? 1 : 0];
    if ($ev) {
        $vals[] = $id;
        q('UPDATE events SET title = ?, kind = ?, event_date = ?, start_time = ?, venue = ?, description = ?, image = ?, fee = ?, capacity = ?,
           reg_open = ?, reg_last = ?, allow_public = ?, show_public = ? WHERE id = ?', $vals);
    } else {
        q('INSERT INTO events (title, kind, event_date, start_time, venue, description, image, fee, capacity, reg_open, reg_last, allow_public, show_public)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', $vals);
        $id = (int)db()->lastInsertId();
    }
    flash('success', t('ev_saved'));
    redirect('events.php?id=' . $id);
}

$editKey = get('edit');
$edit = $editKey === 'new' ? ['id' => 0, 'title' => '', 'kind' => 'fight', 'event_date' => date('Y-m-d', strtotime('+14 day')), 'start_time' => '18:00:00', 'venue' => '',
    'description' => '', 'image' => '', 'fee' => 0, 'capacity' => 0, 'reg_open' => 1, 'reg_last' => null, 'allow_public' => 1, 'show_public' => 1]
    : ($editKey !== '' ? q('SELECT * FROM events WHERE id = ?', [(int)$editKey])->fetch() : null);
$view = !$edit && get('id') !== '' ? q('SELECT * FROM events WHERE id = ?', [(int)get('id')])->fetch() : null;

$title = $view ? $view['title'] : t('events');
$active = 'events';
$back = $edit || $view ? 'events.php' : 'more.php';
$actions = $view ? '<a href="?edit=' . $view['id'] . '" class="btn btn-outline-primary"><i class="bi bi-pencil"></i> ' . e(t('edit')) . '</a>'
    : ($edit ? '' : '<a href="?edit=new" class="btn btn-primary"><i class="bi bi-plus-lg"></i> ' . e(t('add_event')) . '</a>');
require __DIR__ . '/includes/header.php';
?>
<?php if ($edit): $img = safe_img($edit['image']); ?>
<form method="post" enctype="multipart/form-data" class="card mb-3" style="max-width:760px"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
  <div class="card-header fw-bold"><i class="bi bi-<?= $edit['id'] ? 'pencil' : 'plus-circle' ?>"></i> <?= e(t($edit['id'] ? 'edit_event' : 'add_event')) ?></div>
  <div class="card-body row g-3">
    <div class="col-12"><label class="form-label small" for="evt"><?= e(t('ev_title')) ?> *</label>
      <input class="form-control" id="evt" name="title" maxlength="150" required value="<?= e($edit['title']) ?>" placeholder="<?= e(t('ev_title_ph')) ?>"></div>
    <div class="col-12"><label class="form-label small d-block"><?= e(t('ev_kind')) ?></label>
      <div class="d-flex flex-wrap gap-1 cat-opt">
        <?php foreach (EVENT_KINDS as $k => $ic): ?>
          <input type="radio" class="btn-check" name="kind" value="<?= $k ?>" id="ek<?= $k ?>"<?= $edit['kind'] === $k ? ' checked' : '' ?>>
          <label class="btn btn-sm btn-outline-primary" for="ek<?= $k ?>"><i class="bi <?= $ic ?>"></i> <?= e(t('evk_' . $k)) ?></label>
        <?php endforeach; ?>
      </div></div>
    <div class="col-6"><label class="form-label small" for="evd"><?= e(t('date')) ?> *</label><input class="form-control" type="date" id="evd" name="event_date" required value="<?= e($edit['event_date']) ?>"></div>
    <div class="col-6"><label class="form-label small" for="evs"><?= e(t('time')) ?></label><input class="form-control" type="time" id="evs" name="start_time" value="<?= e(substr((string)$edit['start_time'], 0, 5)) ?>"></div>
    <div class="col-12"><label class="form-label small" for="evv"><?= e(t('ev_venue')) ?></label><input class="form-control" id="evv" name="venue" maxlength="200" value="<?= e($edit['venue']) ?>" placeholder="<?= e(t('ev_venue_ph')) ?>"></div>
    <div class="col-12"><label class="form-label small" for="evx"><?= e(t('details')) ?></label>
      <textarea class="form-control" id="evx" name="description" rows="4" maxlength="4000" placeholder="<?= e(t('ev_details_ph')) ?>"><?= e((string)$edit['description']) ?></textarea></div>
    <div class="col-md-5">
      <label class="form-label small d-block"><?= e(t('photos')) ?></label>
      <div class="ev-edit-img mb-2"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>><?php if ($img === ''): ?><i class="bi bi-image"></i><?php endif; ?></div>
      <input class="form-control form-control-sm" type="file" name="image" accept="image/*">
      <?php if ($img !== ''): ?><div class="form-check small mt-1"><input class="form-check-input" type="checkbox" name="remove_image" value="1" id="rmi"><label class="form-check-label" for="rmi"><?= e(t('remove_photo')) ?></label></div><?php endif; ?>
      <div class="form-text"><?= e(t('ev_photo_help')) ?></div>
    </div>
    <div class="col-md-7 row g-2 m-0 p-0 align-content-start">
      <div class="col-6"><label class="form-label small" for="evf"><?= e(t('ev_fee')) ?> (₹)</label><input class="form-control" type="number" min="0" step="0.01" id="evf" name="fee" value="<?= e((string)(float)$edit['fee']) ?>"><div class="form-text"><?= e(t('ev_fee_help')) ?></div></div>
      <div class="col-6"><label class="form-label small" for="evc"><?= e(t('capacity')) ?></label><input class="form-control" type="number" min="0" max="9999" id="evc" name="capacity" value="<?= (int)$edit['capacity'] ?>"><div class="form-text"><?= e(t('capacity_help')) ?></div></div>
      <div class="col-12"><label class="form-label small" for="evl"><?= e(t('ev_reg_last')) ?></label><input class="form-control" type="date" id="evl" name="reg_last" value="<?= e((string)$edit['reg_last']) ?>"></div>
      <div class="col-12 d-grid gap-1">
        <div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="reg_open" value="1" id="evro"<?= $edit['reg_open'] ? ' checked' : '' ?>><label class="form-check-label" for="evro"><?= e(t('ev_reg_open')) ?></label></div>
        <div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="allow_public" value="1" id="evap"<?= $edit['allow_public'] ? ' checked' : '' ?>><label class="form-check-label" for="evap"><?= e(t('ev_allow_public')) ?></label></div>
        <div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="show_public" value="1" id="evsp"<?= $edit['show_public'] ? ' checked' : '' ?>><label class="form-check-label" for="evsp"><?= e(t('show_on_public')) ?></label></div>
      </div>
    </div>
    <div class="col-12 d-flex gap-2"><a href="events.php<?= $edit['id'] ? '?id=' . (int)$edit['id'] : '' ?>" class="btn btn-light"><?= e(t('cancel')) ?></a><button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
  </div>
</form>
<?php if ($edit['id']): ?>
  <form method="post" style="max-width:760px" class="text-end mb-4" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
    <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button></form>
<?php endif; ?>

<?php elseif ($view): // one event: details, share, registrations
    $eid = (int)$view['id'];
    $regs = q("SELECT r.*, m.adm_no FROM event_regs r LEFT JOIN members m ON m.id = r.member_id WHERE r.event_id = ? ORDER BY r.status = 'cancelled', r.id", [$eid])->fetchAll();
    $activeRegs = array_filter($regs, fn($r) => $r['status'] !== 'cancelled');
    $paidCount = count(array_filter($activeRegs, fn($r) => $r['paid']));
    $img = safe_img($view['image']);
    $closed = event_closed($view);
    $shareText = event_text($view);
    $members = q("SELECT id, name, adm_no FROM members WHERE status = 'active' AND id NOT IN (SELECT member_id FROM event_regs WHERE event_id = ? AND member_id IS NOT NULL) ORDER BY name", [$eid])->fetchAll();
?>
<div class="row g-3">
  <div class="col-lg-5">
    <div class="card mb-3 overflow-hidden">
      <?php if ($img !== ''): ?><img src="<?= e($img) ?>" alt="" class="w-100" style="max-height:260px;object-fit:cover"><?php endif; ?>
      <div class="card-body">
        <span class="badge bg-dark mb-2"><i class="bi <?= EVENT_KINDS[$view['kind']] ?>"></i> <?= e(t('evk_' . $view['kind'])) ?></span>
        <?php if ($closed !== ''): ?><span class="badge bg-secondary mb-2"><?= e(t($closed)) ?></span><?php else: ?><span class="badge bg-success mb-2"><?= e(t('ev_reg_open_short')) ?></span><?php endif; ?>
        <?php if (!$view['show_public']): ?><span class="badge text-bg-light border mb-2"><?= e(t('hidden')) ?></span><?php endif; ?>
        <div class="mb-1"><i class="bi bi-clock text-primary"></i> <?= e(event_when($view)) ?></div>
        <?php if ($view['venue'] !== ''): ?><div class="mb-1"><i class="bi bi-geo-alt text-primary"></i> <?= e($view['venue']) ?></div><?php endif; ?>
        <?php if ((float)$view['fee'] > 0): ?><div class="mb-1"><i class="bi bi-cash-coin text-primary"></i> <?= e(t('ev_fee')) ?>: <b><?= money($view['fee']) ?></b></div><?php endif; ?>
        <?php if (trim((string)$view['description']) !== ''): ?><p class="small mt-2 mb-0" style="white-space:pre-line"><?= e($view['description']) ?></p><?php endif; ?>
      </div>
    </div>
    <div class="row g-2 mb-3">
      <div class="col-6"><div class="card stat"><div><div class="lbl"><?= e(t('ev_registered')) ?></div><div class="num"><?= count($activeRegs) ?><?= $view['capacity'] ? '<small class="fs-6 text-muted"> / ' . (int)$view['capacity'] . '</small>' : '' ?></div></div></div></div>
      <?php if ((float)$view['fee'] > 0): ?><div class="col-6"><div class="card stat"><div><div class="lbl"><?= e(t('ev_fee_paid')) ?></div><div class="num"><?= $paidCount ?></div><div class="sub"><?= money($paidCount * (float)$view['fee']) ?></div></div></div></div><?php endif; ?>
    </div>
    <textarea class="visually-hidden" id="evShare" tabindex="-1" aria-hidden="true"><?= e($shareText) ?></textarea>
    <div class="d-grid gap-2 mb-3">
      <a class="btn btn-whatsapp btn-lg" href="<?= e(wa_link('', $shareText)) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(t('ev_share')) ?></a>
      <div class="d-flex gap-2"><button type="button" class="btn btn-outline-secondary flex-fill" data-copy="#evShare"><i class="bi bi-copy"></i> <?= e(t('copy_text')) ?></button>
        <a class="btn btn-outline-primary flex-fill" href="event.php?id=<?= $eid ?>" target="_blank"><i class="bi bi-box-arrow-up-right"></i> <?= e(t('ev_public_page')) ?></a></div>
    </div>
  </div>

  <div class="col-lg-7" id="regs">
    <div class="card mb-3">
      <div class="card-header d-flex align-items-center gap-2"><i class="bi bi-people-fill text-primary"></i><span class="me-auto"><?= e(t('ev_registrations')) ?> · <?= count($activeRegs) ?></span>
        <button type="button" class="btn btn-sm btn-outline-primary" data-bs-toggle="collapse" data-bs-target="#addReg"><i class="bi bi-plus-lg"></i> <?= e(t('member')) ?></button></div>
      <form method="post" class="collapse border-bottom p-3" id="addReg"><?= csrf_field() ?><input type="hidden" name="action" value="add_member"><input type="hidden" name="id" value="<?= $eid ?>">
        <select class="form-select mb-2" name="member_id" required aria-label="<?= e(t('member')) ?>"><option value=""><?= e(t('choose_member')) ?></option>
          <?php foreach ($members as $mm): ?><option value="<?= $mm['id'] ?>"><?= e($mm['name'] . ' (' . $mm['adm_no'] . ')') ?></option><?php endforeach; ?></select>
        <input class="form-control mb-2" name="note" maxlength="200" placeholder="<?= e(t('ev_note_ph')) ?>">
        <button class="btn btn-primary w-100"><?= e(t('ev_register')) ?></button>
      </form>
      <div class="list-group list-group-flush">
        <?php if (!$regs): ?><div class="list-group-item text-muted"><?= e(t('ev_no_regs')) ?></div><?php endif; ?>
        <?php foreach ($regs as $r): $cancel = $r['status'] === 'cancelled'; ?>
          <div class="list-group-item<?= $cancel ? ' opacity-50' : '' ?>">
            <div class="d-flex align-items-start gap-2">
              <span class="req-ava"><?= e(mb_strtoupper(mb_substr($r['name'], 0, 1))) ?></span>
              <div class="me-auto"><div class="fw-semibold"><?php if ($r['member_id']): ?><a href="member_view.php?id=<?= $r['member_id'] ?>" class="text-decoration-none"><?= e($r['name']) ?></a> <span class="small-muted"><?= e((string)$r['adm_no']) ?></span><?php else: ?><?= e($r['name']) ?> <span class="badge text-bg-light border"><?= e(t('ev_visitor')) ?></span><?php endif; ?></div>
                <div class="small-muted"><?= e($r['phone']) ?><?= $r['place'] !== '' ? ' · ' . e($r['place']) : '' ?><?= $r['note'] !== '' ? ' · ' . e($r['note']) : '' ?></div>
                <div class="mt-1"><span class="badge <?= ['registered' => 'bg-warning text-dark', 'confirmed' => 'bg-success', 'cancelled' => 'bg-secondary'][$r['status']] ?>"><?= e(t('evs_' . $r['status'])) ?></span>
                  <?php if ((float)$view['fee'] > 0): ?><span class="badge <?= $r['paid'] ? 'bg-success' : 'text-bg-light border' ?>"><?= e(t($r['paid'] ? 'ev_paid' : 'ev_not_paid')) ?></span><?php endif; ?></div></div>
              <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" data-sent aria-label="WhatsApp"
                 href="<?= e(wa_link($r['phone'], t('wa_event_confirm', $r['name'], $view['title'], event_when($view), $view['venue'] !== '' ? $view['venue'] : gym_title()))) ?>"><i class="bi bi-whatsapp"></i></a>
            </div>
            <form method="post" class="d-flex flex-wrap gap-1 mt-2"><?= csrf_field() ?><input type="hidden" name="action" value="reg"><input type="hidden" name="id" value="<?= $eid ?>"><input type="hidden" name="reg_id" value="<?= $r['id'] ?>">
              <?php if ($r['status'] !== 'confirmed'): ?><button class="btn btn-sm btn-outline-success" name="do" value="confirmed"><i class="bi bi-check2"></i> <?= e(t('ev_confirm')) ?></button><?php endif; ?>
              <?php if ((float)$view['fee'] > 0): ?><button class="btn btn-sm btn-outline-primary" name="do" value="<?= $r['paid'] ? 'unpaid' : 'paid' ?>"><i class="bi bi-cash"></i> <?= e(t($r['paid'] ? 'ev_mark_unpaid' : 'ev_mark_paid')) ?></button><?php endif; ?>
              <?php if (!$cancel): ?><button class="btn btn-sm btn-outline-secondary" name="do" value="cancelled"><?= e(t('cancel')) ?></button>
              <?php else: ?><button class="btn btn-sm btn-outline-secondary" name="do" value="registered"><?= e(t('ev_restore')) ?></button><?php endif; ?>
            </form>
          </div>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
</div>

<?php else: // list
    $upcoming = events_upcoming(false, 100);
    $past = q("SELECT e.*, (SELECT COUNT(*) FROM event_regs r WHERE r.event_id = e.id AND r.status <> 'cancelled') regs FROM events e WHERE e.event_date < ? ORDER BY e.event_date DESC LIMIT 30", [today()])->fetchAll();
    $row = function (array $ev): void { $img = safe_img($ev['image']); ?>
      <a href="?id=<?= $ev['id'] ?>" class="list-group-item list-group-item-action d-flex align-items-center gap-3">
        <span class="ev-thumb"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>><b><?= date('d', strtotime($ev['event_date'])) ?></b><?= e(date('M', strtotime($ev['event_date']))) ?></span>
        <span class="me-auto"><span class="fw-semibold d-block"><?= e($ev['title']) ?></span>
          <span class="small-muted"><?= e(t('evk_' . $ev['kind'])) ?><?= $ev['venue'] !== '' ? ' · ' . e($ev['venue']) : '' ?><?= $ev['show_public'] ? '' : ' · ' . e(t('hidden')) ?></span></span>
        <span class="badge text-bg-light border"><i class="bi bi-people"></i> <?= (int)$ev['regs'] ?></span>
      </a>
    <?php }; ?>
  <p class="small-muted"><?= e(t('events_help')) ?></p>
  <h2 class="section-head"><?= e(t('ev_upcoming')) ?></h2>
  <div class="card mb-3"><div class="list-group list-group-flush">
    <?php if (!$upcoming): ?><div class="list-group-item text-muted"><?= e(t('ev_none')) ?></div><?php endif; ?>
    <?php foreach ($upcoming as $ev) $row($ev); ?>
  </div></div>
  <?php if ($past): ?>
    <details><summary class="section-head"><?= e(t('ev_past')) ?> (<?= count($past) ?>)</summary>
      <div class="card mb-3"><div class="list-group list-group-flush"><?php foreach ($past as $ev) $row($ev); ?></div></div></details>
  <?php endif; ?>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
