<?php
require_once __DIR__ . '/includes/config.php';
require_once __DIR__ . '/includes/icons.php';
require_once __DIR__ . '/includes/lang.php';
require_once __DIR__ . '/includes/og.php';
require_once __DIR__ . '/includes/theme.php';
require_once __DIR__ . '/includes/site_schema.php';
lang_current();

// AJAX contact form
if (!empty($_POST['ajax']) && ($_POST['action'] ?? '') === 'contact') {
    header('Content-Type: application/json');
    // spam: hidden field must stay empty
    if (trim($_POST['website'] ?? '') !== '') { echo json_encode(['ok'=>true]); exit; }
    $n = mb_substr(trim($_POST['name'] ?? ''), 0, 150);    $e = mb_substr(trim($_POST['email'] ?? ''), 0, 200);
    $s = mb_substr(trim($_POST['subject'] ?? ''), 0, 200); $m = mb_substr(trim($_POST['message'] ?? ''), 0, 4000);
    if ($n === '' || $m === '') { echo json_encode(['ok'=>false,'msg'=>t('ct_err')]); exit; }
    try { db()->prepare('INSERT INTO contact_messages(name,email,subject,message)VALUES(?,?,?,?)')->execute([$n,$e,$s,$m]); echo json_encode(['ok'=>true]); }
    catch (Exception $ex) { echo json_encode(['ok'=>false,'msg'=>'Database error. Please try WhatsApp instead.']); }
    exit;
}

$logo      = getLogoB64();
$clubName  = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
$clubPlace = setting('CLUB_PLACE', 'Vettikkattiri');
$siteWa    = site_whatsapp();
$sitePhone = preg_replace('/[^\d+]/', '', site_cfg('site_phone', setting('CLUB_PHONE', '')));
$siteAddr  = tset(site_cfg('site_address', $clubPlace . ', Kerala, India'), site_cfg('site_address_ml', ''));
$siteMap   = site_cfg('site_map', '');
$siteInsta = site_cfg('social_instagram', '');
$waGroup   = defined('CLUB_WA_GROUP') && strpos(CLUB_WA_GROUP, 'YOUR_GROUP') === false ? CLUB_WA_GROUP : '';
$isEmbed   = (bool)preg_match('#^https://(www\.)?google\.[a-z.]+/maps/embed#', $siteMap);
?>
<!DOCTYPE html>
<html lang="<?= lang_current() ?>">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title><?= h(t('sec_contact') . ' · ' . $clubName) ?></title>
<?= og_tags(array('title' => t('sec_contact') . ' · ' . $clubName, 'url' => rtrim(SITE_URL, '/') . '/contact.php')) ?>
<link rel="manifest" href="<?= url('manifest.php') ?>">
<?= theme_head() ?><link rel="apple-touch-icon" href="<?= url('assets/icons/app/apple-touch-icon.png') ?>">
<link rel="icon" type="image/png" href="<?= url('assets/icons/app/favicon-64.png') ?>">
<link rel="stylesheet" href="<?= url('assets/vendor/bootstrap/css/bootstrap.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/vendor/bootstrap-icons/bootstrap-icons.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/css/club.css') ?>?v=6">
<style>
.cf-card{background:var(--dark);border:1px solid rgba(255,255,255,.08);border-radius:var(--r-card);padding:1.2rem}
.cf-card .form-control{min-height:52px;background:var(--page-dark);border:1.5px solid rgba(255,255,255,.15);color:#fff;font-size:1rem;border-radius:.8rem}
.cf-card .form-control:focus{border-color:var(--accent-text);box-shadow:0 0 0 .2rem rgba(143,151,255,.25)}
.cf-card .form-control::placeholder{color:#8d8a8a}
.cf-card textarea.form-control{min-height:140px}
</style>
</head>
<body class="pub" data-bs-no-jquery>
<a href="#main" class="skip-link">Skip to content</a>

<header class="pub-top">
  <div class="in">
    <a href="<?= url('index.php') ?>" class="d-flex align-items-center gap-2 text-decoration-none" aria-label="<?= h($clubName) ?> — <?= h(t('nav_home')) ?>">
      <?php if($logo): ?><img class="logo" src="<?= $logo ?>" alt="" width="44" height="44"><?php endif; ?>
      <span><span class="name d-block"><?= h($clubName) ?></span><span class="sub"><?= h($clubPlace) ?> · Kerala</span></span>
    </a>
    <a class="lang" href="<?= h(lang_url(lang_current() === 'ml' ? 'en' : 'ml')) ?>" lang="<?= lang_current() === 'ml' ? 'en' : 'ml' ?>" aria-label="<?= h(t('lang_label')) ?>"><i class="bi bi-translate" aria-hidden="true"></i><?= h(t('lang_switch')) ?></a>
    <?= theme_button() ?>
  </div>
</header>

<main id="main" tabindex="-1">
<section aria-labelledby="ctH"><div class="wrap">
  <h1 class="h-sec h-big" id="ctH"><?= h(t('sec_contact')) ?></h1>
  <div class="row g-3">
    <div class="col-lg-6">
      <div class="cf-card">
        <h2 class="fw-bold fs-5 text-uppercase mb-1"><?= h(t('ct_title')) ?></h2>
        <p class="text-2 small mb-3"><?= h(t('ct_sub')) ?></p>
        <div class="alert alert-danger py-2 d-none" id="cfErr" role="alert"></div>
        <form id="cfForm" novalidate>
          <div class="mb-3"><label class="form-label" for="cName"><?= h(t('form_name')) ?> *</label><input class="form-control" id="cName" name="name" autocomplete="name" required></div>
          <div class="mb-3"><label class="form-label" for="cEmail"><?= h(t('ct_email')) ?></label><input class="form-control" id="cEmail" name="email" type="email" autocomplete="email"></div>
          <div class="mb-3"><label class="form-label" for="cSubject"><?= h(t('ct_subject')) ?></label><input class="form-control" id="cSubject" name="subject"></div>
          <div class="mb-3"><label class="form-label" for="cMsg"><?= h(t('ct_message')) ?> *</label><textarea class="form-control" id="cMsg" name="message" required></textarea></div>
          <div class="hp" aria-hidden="true"><label for="cWeb">Website</label><input id="cWeb" name="website" tabindex="-1" autocomplete="off"></div>
          <button type="submit" class="btn btn-brand btn-lg w-100" id="cfSend"><i class="bi bi-send-fill" aria-hidden="true"></i><?= h(t('ct_send')) ?></button>
        </form>
        <div class="thanks d-none" id="cfThanks" role="status">
          <i class="bi bi-check-circle-fill" aria-hidden="true"></i>
          <h3 class="fw-bold fs-5 mt-2"><?= h(t('ct_sent')) ?></h3>
          <p class="text-2"><?= h(t('ct_sent_sub')) ?></p>
          <button type="button" class="btn btn-line" id="cfAgain"><?= h(t('ct_again')) ?></button>
        </div>
      </div>
    </div>
    <div class="col-lg-6">
      <div class="ct-box">
        <div class="ct-row"><i class="bi bi-geo-alt-fill" aria-hidden="true"></i><div><small class="text-2 d-block"><?= h(t('address')) ?></small><span style="white-space:pre-line"><?= h($siteAddr) ?></span></div></div>
        <?php if($sitePhone): ?><div class="ct-row"><i class="bi bi-telephone-fill" aria-hidden="true"></i><div><small class="text-2 d-block"><?= h(t('phone')) ?></small><a href="tel:<?= h($sitePhone) ?>"><?= h($sitePhone) ?></a></div></div><?php endif; ?>
        <?php if($waGroup): ?><div class="ct-row"><i class="bi bi-people-fill" aria-hidden="true"></i><div><small class="text-2 d-block"><?= h(t('ct_group')) ?></small><a href="<?= h($waGroup) ?>" target="_blank" rel="noopener"><?= h(t('ct_group_join')) ?> →</a></div></div><?php endif; ?>
        <div class="ct-row"><i class="bi bi-person-badge-fill" aria-hidden="true"></i><div><small class="text-2 d-block"><?= h(t('ct_portal')) ?></small><a href="<?= url('index.php') ?>?login=1"><?= h(t('ct_portal_go')) ?> →</a></div></div>
        <div class="d-grid gap-2 mt-2">
          <?php if($siteWa): ?><a class="btn btn-wa" href="https://wa.me/<?= h($siteWa) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp" aria-hidden="true"></i><?= h(t('hero_whatsapp')) ?></a><?php endif; ?>
          <?php if($sitePhone): ?><a class="btn btn-line" href="tel:<?= h($sitePhone) ?>"><i class="bi bi-telephone" aria-hidden="true"></i><?= h(t('hero_call')) ?></a><?php endif; ?>
          <?php if($siteInsta): ?><a class="btn btn-line" href="<?= h($siteInsta) ?>" target="_blank" rel="noopener"><i class="bi bi-instagram" aria-hidden="true"></i><?= h(t('instagram')) ?></a><?php endif; ?>
          <?php if($siteMap && !$isEmbed): ?><a class="btn btn-line" href="<?= h($siteMap) ?>" target="_blank" rel="noopener"><i class="bi bi-map" aria-hidden="true"></i><?= h(t('open_map')) ?></a><?php endif; ?>
        </div>
      </div>
      <?php if($isEmbed): ?><iframe class="map mt-3" src="<?= h($siteMap) ?>" loading="lazy" referrerpolicy="no-referrer-when-downgrade" title="Map: <?= h($clubName) ?>"></iframe><?php endif; ?>
    </div>
  </div>
</div></section>
</main>

<footer class="pub-foot"><div class="wrap">
  © <?= date('Y') ?> <?= h($clubName) ?> · <?= h($clubPlace) ?>
  <br><span class="dev"><i class="bi bi-code-slash" aria-hidden="true"></i><?= h(t('developed_by')) ?> <b class="text-white">anexpaikadan</b></span>
</div></footer>

<nav class="bnav3" aria-label="Quick links">
  <a href="<?= url('index.php') ?>"><span class="pill"><i class="bi bi-house-door-fill" aria-hidden="true"></i></span><?= h(t('nav_home')) ?></a>
  <a href="<?= url('modules/market.php') ?>" class="mid"><span class="ring"><i class="bi bi-bag-fill" aria-hidden="true"></i></span><?= h(t('nav_market')) ?></a>
  <?php if(isLoggedIn()): ?>
    <a href="<?= url('dashboard.php') ?>"><span class="pill"><i class="bi bi-person-circle" aria-hidden="true"></i></span><?= h(t('nav_account')) ?></a>
  <?php else: ?>
    <a href="<?= url('index.php') ?>?login=1"><span class="pill"><i class="bi bi-box-arrow-in-right" aria-hidden="true"></i></span><?= h(t('nav_login')) ?></a>
  <?php endif; ?>
</nav>

<script>
(function(){
  var f = document.getElementById('cfForm'), err = document.getElementById('cfErr'), btn = document.getElementById('cfSend');
  var ERR = <?= json_encode(t('ct_err'), JSON_UNESCAPED_UNICODE) ?>, NET = <?= json_encode(t('form_err_net'), JSON_UNESCAPED_UNICODE) ?>;
  function fail(m){ err.textContent = m; err.classList.remove('d-none'); }
  f.addEventListener('submit', function(e){
    e.preventDefault(); err.classList.add('d-none');
    if(!f.name.value.trim()){ fail(ERR); f.name.focus(); return; }
    if(!f.message.value.trim()){ fail(ERR); f.message.focus(); return; }
    var fd = new FormData(f); fd.append('ajax', '1'); fd.append('action', 'contact');
    btn.disabled = true;
    fetch(location.pathname, {method:'POST', body:fd, credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){
      btn.disabled = false;
      if(!d.ok) return fail(d.msg || NET);
      f.reset(); f.classList.add('d-none'); document.getElementById('cfThanks').classList.remove('d-none');
    }).catch(function(){ btn.disabled = false; fail(NET); });
  });
  document.getElementById('cfAgain').addEventListener('click', function(){
    document.getElementById('cfThanks').classList.add('d-none'); f.classList.remove('d-none'); f.name.focus();
  });
})();
</script>
<script src="<?= url('assets/js/motion.js') ?>?v=1" defer></script>
</body>
</html>
