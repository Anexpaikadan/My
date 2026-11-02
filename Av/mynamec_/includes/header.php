<?php
// ================================================================
// header.php — app shell for every member/admin page (light theme)
// Bootstrap 5.3 + Bootstrap Icons (local) + assets/css/club.css
// Phone: dark top bar + 5-tab bottom bar (footer.php). Desktop: dark sidebar.
// ================================================================
require_once __DIR__.'/config.php';
require_once __DIR__ . '/extras.php';
require_once __DIR__.'/icons.php';
require_once __DIR__.'/lang.php';
require_once __DIR__.'/og.php';
lang_current();   // handles ?setlang= before any output
$user         = currentUser();
$logoB64      = getLogoB64();
$userPhotoB64 = ($user && !empty($user['profile_photo']) && $user['profile_photo'] !== 'default.png')
                  ? getMemberPhoto($user['profile_photo']) : '';
$isAdmin  = (isset($isAdmin) && $isAdmin) ? true : ($user && isAdminRole($user['role']));
$canPost  = $user && canPost($user['role']);
$curPage  = basename($_SERVER['PHP_SELF']);
$curRel   = (strpos($_SERVER['PHP_SELF'], '/modules/') !== false ? 'modules/' : '') . $curPage;
$isHome   = ($curPage === 'dashboard.php');
$pendingBadge = 0;
if ($isAdmin) {
    try { $pendingBadge = (int)db()->query("SELECT COUNT(*) FROM users WHERE status='pending'")->fetchColumn(); } catch(Exception $e){}
}
// Title shown in the top bar
$_barTitle = isset($pageTitle) && $pageTitle ? trim(preg_split('/\s+[—|·-]\s+/u', $pageTitle)[0]) : '';
$_allMods  = array_merge(app_modules(), admin_modules());
foreach ($_allMods as $_m) { if ($_m[0] === $curRel) { $_barTitle = app_label($_m[0], $_m[1]); break; } }
$_meta     = app_meta($curRel);
$_club     = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$_place    = setting('CLUB_PLACE','Vettikkattiri');
$_lang     = lang_current();
?><!DOCTYPE html>
<html lang="<?= $_lang ?>">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<meta name="theme-color" content="#0B1033">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aishwarya">
<link rel="manifest" href="<?= url('manifest.php') ?>">
<link rel="apple-touch-icon" href="<?= url('assets/icons/app/apple-touch-icon.png') ?>">
<link rel="icon" type="image/png" href="<?= url('assets/icons/app/favicon-64.png') ?>">
<title><?= h($_barTitle ? $_barTitle . ' · ' . $_club : $_club) ?></title>
<?= og_tags(isset($pageOG) && is_array($pageOG) ? $pageOG : array()) ?>
<link rel="stylesheet" href="<?= url('assets/vendor/bootstrap/css/bootstrap.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/vendor/bootstrap-icons/bootstrap-icons.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/vendor/fontawesome/css/all.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/css/club.css') ?>?v=3">
<script>
window._pwaPrompt = null;
window.addEventListener('beforeinstallprompt', function(e){ e.preventDefault(); window._pwaPrompt = e; var b=document.getElementById('pwaInstallBtn'); if(b) b.style.display='flex'; });
if ('serviceWorker' in navigator) { window.addEventListener('load', function(){ navigator.serviceWorker.register('/sw.js').catch(function(){}); }); }
</script>
</head>
<body class="app" data-mod-icon="<?= $isHome ? '' : h($_meta[0]) ?>">
<?= icon_sprite() ?>
<a href="#main" class="skip-link">Skip to content</a>

<!-- ════ SIDEBAR (desktop) ════ -->
<nav class="side" aria-label="Main menu">
  <a class="brand" href="<?= url('dashboard.php') ?>">
    <?php if($logoB64): ?><img src="<?= $logoB64 ?>" alt="" width="44" height="44"><?php endif; ?>
    <span><b><?= h($_club) ?></b><br><small style="color:var(--muted)"><?= h($_place) ?></small></span>
  </a>
  <?php
  $_sideGroups = array('Home' => array(array('dashboard.php','Home'), array('more.php','More')));
  foreach (app_modules() as $_m) { $_sideGroups[$_m[4]][] = array($_m[0], $_m[1]); }
  if ($isAdmin) { foreach (admin_modules() as $_m) { if ($_m[0]==='modules/settings.php' && !isSuperAdmin($user)) continue; $_sideGroups['Admin'][] = array($_m[0], $_m[1]); } }
  foreach ($_sideGroups as $_g => $_items): ?>
    <div class="grp"><?= h($_g === 'Home' ? t('nav_home') : ($_g === 'Admin' ? t('nav_admin') : $_g)) ?></div>
    <?php foreach ($_items as $_it): $_on = ($_it[0] === $curRel); $_mm = app_meta($_it[0]); ?>
      <a class="it<?= $_on ? ' on' : '' ?>" href="<?= url($_it[0]) ?>"<?= $_on ? ' aria-current="page"' : '' ?>><i class="bi bi-<?= $_mm[0] ?>" aria-hidden="true"></i><?= h(app_label($_it[0], $_it[1])) ?>
        <?php if($_it[0]==='admin.php' && $pendingBadge): ?><span class="badge rounded-pill text-bg-danger ms-auto"><?= $pendingBadge ?></span><?php endif; ?></a>
    <?php endforeach; ?>
  <?php endforeach; ?>
  <div class="grp"></div>
  <a class="it" href="<?= url('index.php') ?>"><i class="bi bi-globe2" aria-hidden="true"></i><?= h(t('nav_website')) ?></a>
  <a class="it" href="<?= url('logout.php') ?>"><i class="bi bi-box-arrow-right" aria-hidden="true"></i><?= h(t('nav_logout')) ?></a>
</nav>

<!-- ════ TOP BAR ════ -->
<header class="topbar">
  <div class="in">
    <?php if (!$isHome): ?>
      <a class="tb-btn" href="<?= url('dashboard.php') ?>" id="barBack" aria-label="<?= h(t('nav_back')) ?>"><i class="bi bi-chevron-left" aria-hidden="true"></i></a>
    <?php else: ?>
      <?php if($logoB64): ?><img class="logo only-phone" src="<?= $logoB64 ?>" alt="" width="38" height="38"><?php endif; ?>
    <?php endif; ?>
    <div class="ttl"><?= h($_barTitle ?: $_club) ?></div>
    <a class="lang" href="<?= h(lang_url($_lang === 'ml' ? 'en' : 'ml')) ?>" aria-label="<?= h(t('lang_label')) ?>" lang="<?= $_lang === 'ml' ? 'en' : 'ml' ?>"><?= h(t('lang_switch')) ?></a>
    <?php if($isAdmin): ?>
      <a class="tb-btn" href="<?= url('admin.php') ?>" aria-label="<?= h(t('nav_admin')) ?><?= $pendingBadge ? ', '.$pendingBadge.' waiting' : '' ?>"><i class="bi bi-shield-lock" aria-hidden="true"></i><?php if($pendingBadge): ?><span class="bdg" aria-hidden="true"><?= $pendingBadge ?></span><?php endif; ?></a>
    <?php endif; ?>
    <?php if($user): ?>
      <a class="tb-btn" href="<?= url('modules/profile.php') ?>" aria-label="<?= h(t('nav_account')) ?>">
        <?php if($userPhotoB64): ?><img src="<?= $userPhotoB64 ?>" alt="" width="32" height="32" style="width:32px;height:32px;border-radius:50%;object-fit:cover"><?php else: ?><i class="bi bi-person-circle" aria-hidden="true"></i><?php endif; ?>
      </a>
    <?php endif; ?>
  </div>
</header>

<main class="page-wrap" id="main" tabindex="-1">

<script>
// Back button: go back inside the app when we came from it
(function(){ var b=document.getElementById('barBack'); if(!b) return;
  b.addEventListener('click',function(e){ try{ if(document.referrer && new URL(document.referrer).origin===location.origin && history.length>1){ e.preventDefault(); history.back(); } }catch(err){} });
})();
// Older modules: pop-ups and helpers
function openPopup(id){ var p=document.getElementById(id); if(!p) return; p.classList.add('show'); document.body.style.overflow='hidden'; }
function closePopup(id){ var p=document.getElementById(id); if(!p) return; p.classList.remove('show'); document.body.style.overflow=''; }
function toggleDrop(){} function closeDrops(){} function openDrawer(){ location.href='<?= url('more.php') ?>'; } function closeDrawer(){}
document.addEventListener('keydown', function(e){ if (e.key==='Escape') { document.querySelectorAll('.popup-ov.show').forEach(function(p){ p.classList.remove('show'); }); document.body.style.overflow=''; } });
function ajaxPost(url, data, cb){
  var fd=new FormData(); fd.append('ajax','1'); Object.keys(data).forEach(function(k){ fd.append(k, data[k]); });
  fetch(url,{method:'POST',body:fd}).then(function(r){return r.json();}).then(cb).catch(function(){ cb({ok:false,msg:'Network error. Please try again.'}); });
}
</script>
