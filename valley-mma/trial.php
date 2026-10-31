<?php
// "Book your free trial" form on the public home page posts here: the request is saved for the admin
// (Join requests) and the visitor can also send it to the gym on WhatsApp.

require_once __DIR__ . '/includes/init.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    redirect('home.php');
}
csrf_check();
$name = mb_substr(trim(post('name')), 0, 100);
$place = mb_substr(trim(post('place')), 0, 100);
$phone = clean_phone(post('phone'));
$program = mb_substr(trim(post('program')), 0, 60);
$ip = $_SERVER['REMOTE_ADDR'] ?? '';
$error = '';
if (post('website') !== '') { // hidden field: only robots fill it
    redirect('home.php');
}
if ($name === '' || !preg_match('/^\+?\d{10,15}$/', $phone)) {
    $error = t('trial_fill');
} elseif ((int)q('SELECT COUNT(*) FROM join_requests WHERE ip = ? AND created_at > NOW() - INTERVAL 1 HOUR', [$ip])->fetchColumn() >= 5) {
    $error = t('too_many');
}
if ($error === '') {
    $digits = substr(preg_replace('/\D/', '', $phone), -10);
    $same = q("SELECT id FROM join_requests WHERE phone LIKE ? AND status NOT IN ('joined', 'not_interested') ORDER BY id DESC LIMIT 1", ['%' . $digits])->fetch();
    if ($same) { // asked again: update the open request instead of a second one
        q("UPDATE join_requests SET name = ?, place = ?, program = ?, status = IF(status = 'waiting', 'new', status), updated_at = NOW() WHERE id = ?",
            [$name, $place, $program, $same['id']]);
    } else {
        q('INSERT INTO join_requests (name, place, phone, program, ip) VALUES (?, ?, ?, ?, ?)', [$name, $place, $phone, $program, $ip]);
    }
}
$wa = wa_link(pub_wa_phone(), t('wa_trial_request', gym_title(), $name, $place, $phone, $program !== '' ? $program : '–'));

$title = t('book_free_trial');
$bare = true;
$publicPage = 'home';
require __DIR__ . '/includes/header.php';
?>
<div class="pub-wrap pt-4 text-center">
  <img src="assets/logo.png" alt="<?= e(gym_title()) ?>" width="612" height="106" style="width:220px;height:auto" class="mb-4">
  <?php if ($error !== ''): ?>
    <div class="pub-card mb-3"><i class="bi bi-exclamation-triangle-fill text-warning fs-1"></i><p class="mt-2 mb-3"><?= e($error) ?></p>
      <a href="home.php#trial" class="btn btn-primary w-100"><?= e(t('back')) ?></a></div>
  <?php else: ?>
    <div class="pub-card mb-3">
      <i class="bi bi-check-circle-fill text-success" style="font-size:3.5rem"></i>
      <h1 class="h4 mt-2"><?= e(t('trial_thanks', $name)) ?></h1>
      <p class="mb-3" style="color:#c9c5c5"><?= e(t('trial_saved_help')) ?></p>
      <a href="<?= e($wa) ?>" id="trialWa" class="btn btn-whatsapp btn-lg w-100" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(t('trial_send_whatsapp')) ?></a>
    </div>
    <a href="home.php" class="btn btn-outline-light w-100"><i class="bi bi-house-door"></i> <?= e(t('home')) ?></a>
    <script>setTimeout(function () { var a = document.getElementById('trialWa'); if (a) a.click(); }, 1200);</script>
  <?php endif; ?>
</div>
<?php require __DIR__ . '/includes/footer.php';
