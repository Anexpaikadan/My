<?php
// Scanner test: open on a phone to see why the QR scanner does not open (old files, no https,
// camera blocked or not allowed, …). No login needed; shows nothing private.

require __DIR__ . '/includes/init.php';

$title = t('scan_test');
$bare = true;
$memberApp = !admin();
require __DIR__ . '/includes/header.php';
?>
<div class="pt-3">
  <div class="d-flex align-items-center gap-2 mb-3">
    <a href="<?= admin() ? 'attendance.php' : 'me.php' ?>" class="btn btn-light btn-back" aria-label="<?= e(t('back')) ?>"><i class="bi bi-arrow-left"></i></a>
    <h1 class="h4 mb-0"><i class="bi bi-bug text-primary"></i> <?= e(t('scan_test')) ?></h1>
  </div>
  <p class="small-muted"><?= e(t('scan_test_help')) ?></p>

  <div class="card mb-3"><ul class="list-group list-group-flush" id="checks">
    <li class="list-group-item d-flex gap-2" data-check="version"><span class="ic">…</span><span class="me-auto"><?= e(t('chk_version')) ?> <b><?= e(APP_VERSION) ?></b></span><span class="small-muted res"></span></li>
    <li class="list-group-item d-flex gap-2" data-check="https"><span class="ic">…</span><span class="me-auto"><?= e(t('chk_https')) ?></span><span class="small-muted res"></span></li>
    <li class="list-group-item d-flex gap-2" data-check="api"><span class="ic">…</span><span class="me-auto"><?= e(t('chk_api')) ?></span><span class="small-muted res"></span></li>
    <li class="list-group-item d-flex gap-2" data-check="policy"><span class="ic">…</span><span class="me-auto"><?= e(t('chk_policy')) ?></span><span class="small-muted res"></span></li>
    <li class="list-group-item d-flex gap-2" data-check="lib"><span class="ic">…</span><span class="me-auto"><?= e(t('chk_lib')) ?></span><span class="small-muted res"></span></li>
    <li class="list-group-item d-flex gap-2" data-check="camera"><span class="ic">…</span><span class="me-auto"><?= e(t('chk_camera')) ?></span><span class="small-muted res"></span></li>
  </ul></div>

  <div class="d-grid gap-2 mb-2">
    <button type="button" class="btn btn-primary btn-lg" id="tStart"><i class="bi bi-camera-video"></i> <?= e(t('start_camera_test')) ?></button>
    <label class="btn btn-outline-primary btn-lg mb-0" for="tPhoto"><i class="bi bi-camera-fill"></i> <?= e(t('photo_test')) ?></label>
    <input type="file" id="tPhoto" accept="image/*" capture="environment" class="d-none">
  </div>
  <div id="reader" class="mb-2"></div>
  <div id="tPhotoReader" class="d-none"></div>
  <div id="tOut"></div>

  <div class="card mt-3"><div class="card-body small">
    <div><b><?= e(t('app_url_label')) ?>:</b> <span class="text-break"><?= e(base_url()) ?></span></div>
    <div><b><?= e(t('this_page')) ?>:</b> <span class="text-break" id="tHere"></span></div>
    <div class="small-muted mt-2"><?= e(t('scan_test_share')) ?></div>
  </div></div>
</div>
<script>window.VM_TEST = <?= json_encode([
    'server' => APP_VERSION,
    'ok' => t('chk_ok'), 'bad' => t('chk_bad'),
    'oldFiles' => t('chk_old_files'), 'noHttps' => t('chk_no_https'), 'noApi' => t('chk_no_api'),
    'blocked' => t('chk_blocked'), 'noLib' => t('chk_no_lib'), 'press' => t('chk_press_start'),
    'camOk' => t('chk_camera_ok'), 'denied' => t('cam_denied'), 'notFound' => t('cam_not_found'),
    'busy' => t('cam_busy'), 'other' => t('cam_other'), 'read' => t('qr_read'), 'attOk' => t('qr_is_attendance'),
    'otherSite' => t('qr_other_address'), 'noQr' => t('no_qr_in_photo'),
], JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) ?>;</script>
<?php
$scripts = ['assets/vendor/jsQR.js', 'assets/qrscan.js?v=1', 'assets/scan_test.js?v=3'];
require __DIR__ . '/includes/footer.php';
