<?php
// Attendance: today's QR code (members scan it with their phone), scanning member ID cards with the
// admin phone, marking by hand, and today's list. The order of these tabs is set in Settings.

require __DIR__ . '/includes/init.php';
require_admin();

function mark(int $memberId, string $date, string $method): bool
{
    $st = q('INSERT IGNORE INTO attendance (member_id, att_date, check_in, method) VALUES (?, ?, ?, ?)',
        [$memberId, $date, $date === today() ? date('H:i:s') : '00:00:00', $method]);
    return $st->rowCount() > 0;
}

function today_list(): array
{
    return q('SELECT a.id, a.check_in, a.method, m.id member_id, m.name, m.adm_no, m.photo, m.expiry_date
              FROM attendance a JOIN members m ON m.id = a.member_id WHERE a.att_date = ? ORDER BY a.check_in DESC', [today()])->fetchAll();
}

$action = post('action') ?: get('action');

if ($action === 'token') { // new QR when it changes every few minutes
    header('Content-Type: application/json');
    echo json_encode(['url' => att_url(), 'count' => count(today_list())]);
    exit;
}
if ($action === 'card') { // admin scanned a member ID card
    header('Content-Type: application/json');
    $code = preg_replace('/^VMMA:/', '', post('code'));
    $m = q('SELECT * FROM members WHERE card_token = ?', [$code])->fetch();
    if (!$m) {
        echo json_encode(['ok' => false, 'msg' => t('card_unknown')]);
        exit;
    }
    $new = mark((int)$m['id'], today(), 'card');
    $st = member_status($m['expiry_date']);
    echo json_encode([
        'ok' => true, 'new' => $new, 'name' => $m['name'], 'adm_no' => $m['adm_no'], 'photo' => photo_url($m),
        'msg' => $new ? t('marked_present') : t('already_marked'),
        'status' => $st, 'status_text' => $st === 'expired' ? t('membership_expired_on', fdate($m['expiry_date'])) : t('valid_till') . ' ' . fdate($m['expiry_date']),
    ], JSON_UNESCAPED_UNICODE);
    exit;
}
if ($action === 'manual') {
    $date = valid_date(post('date')) && post('date') <= today() ? post('date') : today();
    $ids = array_map('intval', (array)($_POST['members'] ?? [post('member_id')]));
    $n = 0;
    foreach (array_filter($ids) as $mid) {
        $n += mark($mid, $date, 'manual') ? 1 : 0;
    }
    flash('success', t('n_marked', $n, fdate($date)));
    redirect(post('back') === 'member' ? 'member_view.php?id=' . (int)post('member_id') : 'attendance.php?tab=manual&date=' . $date);
}
if ($action === 'remove') {
    q('DELETE FROM attendance WHERE id = ?', [(int)post('id')]);
    flash('success', t('removed'));
    redirect('attendance.php?tab=list');
}
if ($action === 'list') {
    header('Content-Type: application/json');
    echo json_encode(array_map(fn($r) => ['name' => $r['name'], 'time' => substr($r['check_in'], 0, 5)], today_list()), JSON_UNESCAPED_UNICODE);
    exit;
}

$order = array_values(array_unique(array_merge(
    array_intersect(explode(',', setting('att_order', 'qr,card,manual')), ['qr', 'card', 'manual']),
    ['qr', 'card', 'manual']
)));
$tab = in_array(get('tab'), ['qr', 'card', 'manual', 'list'], true) ? get('tab') : (in_array(setting('att_default'), $order, true) ? setting('att_default') : $order[0]);
$tabs = array_merge($order, ['list']);
$labels = ['qr' => ['bi-qr-code', t('show_qr')], 'card' => ['bi-upc-scan', t('scan_card')], 'manual' => ['bi-hand-index', t('mark_manually')], 'list' => ['bi-list-check', t('today_list')]];
$today = today_list();
$mdate = valid_date(get('date')) && get('date') <= today() ? get('date') : today();
$present = q('SELECT member_id FROM attendance WHERE att_date = ?', [$mdate])->fetchAll(PDO::FETCH_COLUMN);
$all = q('SELECT id, name, adm_no, phone, photo, expiry_date FROM members ORDER BY (expiry_date >= CURDATE()) DESC, name')->fetchAll();

$title = t('attendance');
$active = 'attendance';
$actions = '<a href="attendance_monthly.php" class="btn btn-outline-primary"><i class="bi bi-calendar3"></i> ' . e(t('monthly_attendance')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<ul class="nav nav-pills mb-3 gap-1 flex-nowrap overflow-auto" role="tablist">
  <?php foreach ($tabs as $k): ?>
    <li class="nav-item"><button class="nav-link text-nowrap<?= $tab === $k ? ' active' : '' ?>" data-bs-toggle="tab" data-bs-target="#t-<?= $k ?>" type="button" data-tab="<?= $k ?>">
      <i class="bi <?= $labels[$k][0] ?>"></i> <?= e($labels[$k][1]) ?><?= $k === 'list' ? ' <span class="badge bg-success" id="todayCount">' . count($today) . '</span>' : '' ?></button></li>
  <?php endforeach; ?>
</ul>

<div class="tab-content">
  <div class="tab-pane fade<?= $tab === 'qr' ? ' show active' : '' ?>" id="t-qr">
    <div class="card"><div class="card-body text-center" id="qrPanel">
      <div class="fs-5 fw-bold"><?= e(gym_title()) ?></div>
      <div class="fs-4 fw-bold text-primary mb-2"><i class="bi bi-calendar-event"></i> <?= e(t('day' . date('N'))) ?>, <?= e(fdate(today())) ?></div>
      <div class="qr-box border mb-2" id="attQr" data-qr="<?= e(att_url()) ?>" data-refresh="<?= (int)setting('att_refresh', '0') ?>"></div>
      <p class="mb-2"><?= e(t('qr_help')) ?></p>
      <div class="fs-5"><i class="bi bi-people-fill text-success"></i> <?= e(t('present_today')) ?>: <b id="qrCount"><?= count($today) ?></b></div>
      <div class="small text-success mt-1" id="qrLast"><?= $today ? e($today[0]['name'] . ' · ' . substr($today[0]['check_in'], 0, 5)) : '' ?></div>
      <div class="d-flex gap-2 justify-content-center mt-3 flex-wrap">
        <button type="button" class="btn btn-dark" id="qrFull"><i class="bi bi-arrows-fullscreen"></i> <?= e(t('full_screen')) ?></button>
        <a class="btn btn-outline-primary" href="<?= e(att_url()) ?>" target="_blank" rel="noopener"><i class="bi bi-box-arrow-up-right"></i> <?= e(t('test_link')) ?></a>
      </div>
      <?php if (!is_https()): ?><p class="small text-muted mt-3 mb-0"><i class="bi bi-info-circle"></i> <?= e(t('https_note')) ?></p><?php endif; ?>
    </div></div>
  </div>

  <div class="tab-pane fade<?= $tab === 'card' ? ' show active' : '' ?>" id="t-card">
    <div class="card"><div class="card-body text-center">
      <div class="d-flex gap-2 justify-content-center mb-3 flex-wrap">
        <button type="button" class="btn btn-primary btn-lg" id="scanStart"><i class="bi bi-camera-video"></i> <?= e(t('start_camera')) ?></button>
        <button type="button" class="btn btn-outline-dark btn-lg d-none" id="scanFlip" data-facing="<?= e(setting('att_camera', 'environment')) ?>"><i class="bi bi-arrow-repeat"></i> <?= e(t('switch_camera')) ?></button>
        <button type="button" class="btn btn-outline-danger btn-lg d-none" id="scanStop"><i class="bi bi-stop-circle"></i> <?= e(t('stop')) ?></button>
      </div>
      <div id="reader"></div>
      <div id="scanResult" class="scan-result mt-3"></div>
      <p class="small-muted mt-2 mb-0"><?= e(t('scan_card_help')) ?></p>
    </div></div>
  </div>

  <div class="tab-pane fade<?= $tab === 'manual' ? ' show active' : '' ?>" id="t-manual">
    <form method="post" class="card">
      <?= csrf_field() ?><input type="hidden" name="action" value="manual">
      <div class="card-header d-flex flex-wrap gap-2 align-items-center">
        <input class="form-control w-auto" type="date" name="date" value="<?= e($mdate) ?>" max="<?= today() ?>" onchange="location.href='attendance.php?tab=manual&date='+this.value">
        <input class="form-control" style="max-width:260px" type="search" placeholder="<?= e(t('search_ph')) ?>" data-filter="#manualList .list-group-item">
        <button class="btn btn-primary ms-auto"><i class="bi bi-check2-all"></i> <?= e(t('mark_selected')) ?></button>
      </div>
      <div class="list-group list-group-flush" id="manualList">
        <?php foreach ($all as $m): $is = in_array($m['id'], $present); $st = member_status($m['expiry_date']); ?>
          <label class="list-group-item d-flex align-items-center gap-2<?= $st === 'expired' ? ' row-expired' : '' ?>" data-text="<?= e(mb_strtolower($m['name'] . ' ' . $m['adm_no'] . ' ' . $m['phone'])) ?>">
            <input class="form-check-input fs-4 m-0" type="checkbox" name="members[]" value="<?= $m['id'] ?>"<?= $is ? ' checked disabled' : '' ?>>
            <img src="<?= e(photo_url($m)) ?>" class="avatar" alt="" loading="lazy">
            <span class="me-auto"><span class="fw-semibold d-block"><?= e($m['name']) ?></span><span class="small-muted"><?= e($m['adm_no']) ?></span></span>
            <?= $is ? '<span class="badge bg-success">' . e(t('present')) . '</span>' : status_badge($m['expiry_date']) ?>
          </label>
        <?php endforeach; ?>
      </div>
    </form>
  </div>

  <div class="tab-pane fade<?= $tab === 'list' ? ' show active' : '' ?>" id="t-list">
    <div class="card">
      <div class="list-group list-group-flush">
        <?php if (!$today): ?><div class="p-4 text-center text-muted"><?= e(t('no_attendance')) ?></div><?php endif; ?>
        <?php foreach ($today as $a): ?>
          <div class="list-group-item d-flex align-items-center gap-2">
            <img src="<?= e(photo_url($a)) ?>" class="avatar" alt="" loading="lazy">
            <a class="me-auto text-dark text-decoration-none" href="member_view.php?id=<?= $a['member_id'] ?>"><span class="fw-semibold d-block"><?= e($a['name']) ?></span>
              <span class="small-muted"><?= e(substr($a['check_in'], 0, 5)) ?> · <?= e(t('via_' . $a['method'])) ?></span></a>
            <?= member_status($a['expiry_date']) === 'expired' ? status_badge($a['expiry_date']) : '' ?>
            <form method="post" onsubmit="return confirm(<?= e(json_encode(t('confirm_delete'))) ?>)"><?= csrf_field() ?>
              <input type="hidden" name="action" value="remove"><input type="hidden" name="id" value="<?= $a['id'] ?>">
              <button class="btn btn-sm btn-outline-danger"><i class="bi bi-x-lg"></i></button></form>
          </div>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
</div>
<script>window.VM_ATT = <?= json_encode(['csrf' => csrf_token(), 'ok' => t('marked_present'), 'camErr' => t('camera_error'), 'facing' => setting('att_camera', 'environment')], JSON_UNESCAPED_UNICODE) ?>;</script>
<?php
$scripts = ['assets/vendor/qrcode.js', 'assets/qr.js', 'assets/vendor/html5-qrcode.min.js', 'assets/attendance.js?v=3'];
require __DIR__ . '/includes/footer.php';
