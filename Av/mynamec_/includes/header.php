<?php
// header.php — PHP 7.3 compatible, includes ALL CSS needed by all pages
require_once __DIR__.'/config.php';
$user         = currentUser();
$logoB64      = getLogoB64();
$userPhotoB64 = ($user && !empty($user['profile_photo']) && $user['profile_photo'] !== 'default.png')
                  ? getMemberPhoto($user['profile_photo']) : '';
$isAdmin  = (isset($isAdmin) && $isAdmin) ? true : ($user && isAdminRole($user['role']));
$canPost  = $user && canPost($user['role']);
$curPage  = basename($_SERVER['PHP_SELF']);
$pendingBadge = 0;
if ($isAdmin) {
    try { $pendingBadge = (int)db()->query("SELECT COUNT(*) FROM users WHERE status='pending'")->fetchColumn(); } catch(Exception $e){}
}
?><!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<meta name="theme-color" content="#07225c">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aishwarya">
<link rel="apple-touch-icon" href="/assets/logo.jpg">
<link rel="manifest" href="/manifest.php">
<title><?= h(isset($pageTitle) ? $pageTitle : setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></title>
<?php if(defined('LOGO_URL')): ?><link rel="icon" href="<?= h(LOGO_URL) ?>"><?php endif; ?>
<?php
// ── OG / WhatsApp meta tags ───────────────────────────────────
// Each page sets $pageOG array before including header.php
// Fallback: club name + logo for all pages
$_club      = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$_place     = setting('CLUB_PLACE','Vettikkattiri');
$_logo_url  = 'https://mynamecc.online/assets/logo.jpg';  // hardcoded public URL
$_site_url  = rtrim(defined('SITE_URL') ? SITE_URL : 'https://mynamecc.online', '/');
// Build current page full URL
$_cur_path  = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '';
$_cur_url   = $_site_url . $_cur_path;
// Resolve per-page values
$_og_title  = isset($pageOG['title']) ? $pageOG['title']
            : (isset($pageTitle) && $pageTitle ? $pageTitle . ' — ' . $_club : $_club . ' · ' . $_place);
$_og_desc   = isset($pageOG['desc'])  ? $pageOG['desc']
            : $_club . ', ' . $_place . ', Malappuram, Kerala — Members portal';
$_og_img    = isset($pageOG['image']) ? $pageOG['image'] : $_logo_url;
$_og_url    = isset($pageOG['url'])   ? $pageOG['url']   : $_cur_url;
?>
<meta property="og:type"         content="website">
<meta property="og:site_name"    content="<?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?>">
<meta property="og:title"        content="<?= h($_og_title) ?>">
<meta property="og:description"  content="<?= h($_og_desc) ?>">
<meta property="og:image"        content="<?= h($_og_img) ?>">
<meta property="og:image:width"  content="400">
<meta property="og:image:height" content="400">
<meta property="og:url"          content="<?= h($_og_url) ?>">
<meta name="twitter:card"        content="summary">
<meta name="twitter:title"       content="<?= h($_og_title) ?>">
<meta name="twitter:description" content="<?= h($_og_desc) ?>">
<meta name="twitter:image"       content="<?= h($_og_img) ?>">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600;700&family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,600&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
/* ════ RESET ════ */
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'DM Sans',sans-serif;background:#F0F4FA;color:#0D1B3E;line-height:1.6;padding-top:66px}
a{text-decoration:none;color:inherit}
img{display:block;max-width:100%}
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-thumb{background:#0D47A1;border-radius:3px}

/* ════ COLOUR TOKENS ════ */
:root{
  --blue:#0D47A1; --blue2:#1565C0; --navy:#07225c;
  --red:#B71C1C;  --gold:#D4A017;  --gold2:#FFC107;
  --green:#1B5E20; --purple:#7B1FA2;
  --t2:#3D4F7C;   --t3:#55678F; /* 5.6:1 on white (was 3.3:1) */
  --focus:#FFC107; --focus-dark:#0D47A1;
  --bg:#F0F4FA;   --card:#fff;
  --border:#E8ECF4;
  --shadow:0 2px 12px rgba(13,71,161,.09);
  --shadow-lg:0 8px 32px rgba(13,71,161,.15);
  --radius:14px; --radius-sm:9px;
}

/* ════ NAVBAR ════ */
.navbar{
  position:fixed;top:0;left:0;right:0;z-index:900;
  background:linear-gradient(135deg,#07225c 0%,#0D47A1 100%);
  border-bottom:3px solid var(--gold2);
  height:66px;display:flex;align-items:center;
  box-shadow:0 4px 20px rgba(7,34,92,.4);
}
.nav-wrap{
  width:100%;max-width:1280px;margin:0 auto;
  padding:0 1rem;display:flex;align-items:center;gap:.5rem;
}
/* Brand */
.nav-brand{display:flex;align-items:center;gap:.65rem;flex-shrink:0;margin-right:auto}
.nav-brand-logo{width:42px;height:42px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,193,7,.6);background:#fff}
.nav-brand-ph{width:42px;height:42px;border-radius:50%;background:rgba(255,255,255,.15);border:2px solid rgba(255,193,7,.4);display:flex;align-items:center;justify-content:center;font-size:1.1rem}
.nav-brand-name{font-family:'Bebas Neue',sans-serif;font-size:1.05rem;letter-spacing:.1em;color:#fff;line-height:1.2}
.nav-brand-sub{font-size:.64rem;color:rgba(255,255,255,.72);letter-spacing:.14em;text-transform:uppercase}
/* Links */
.nav-links{display:none;list-style:none;gap:.1rem;align-items:center;margin:0;padding:0}
.nav-links a{color:rgba(255,255,255,.82);font-size:.83rem;font-weight:600;padding:.44rem .8rem;border-radius:8px;transition:all .2s;white-space:nowrap;display:flex;align-items:center;gap:.35rem}
.nav-links a:hover,.nav-links a.on{background:rgba(255,255,255,.15);color:#fff}
.nav-links a.on{color:var(--gold2)}
/* Dropdown */
.nav-dd{position:relative}
.nav-dd-btn{color:rgba(255,255,255,.82);font-size:.83rem;font-weight:600;padding:.44rem .8rem;border-radius:8px;transition:all .2s;white-space:nowrap;background:none;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;display:flex;align-items:center;gap:.35rem}
.nav-dd-btn:hover{background:rgba(255,255,255,.15);color:#fff}
.nav-dd-btn.admin-btn{color:rgba(255,180,180,.9)}
.nav-drop{display:none;position:absolute;top:calc(100% + .5rem);left:0;background:#fff;border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,.18);min-width:220px;padding:.4rem;z-index:99;border:1px solid var(--border)}
.nav-drop.right{left:auto;right:0}
.nav-drop.open{display:block}
.nav-drop a{display:flex;align-items:center;gap:.65rem;padding:.55rem .85rem;border-radius:8px;font-size:.84rem;font-weight:500;color:var(--t2);transition:all .2s}
.nav-drop a:hover{background:#F0F4FA;color:var(--blue)}
.nav-drop a .di{width:28px;height:28px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:.85rem;flex-shrink:0}
.nav-drop-sep{height:1px;background:var(--border);margin:.3rem 0}
.nav-drop .admin-link{color:var(--red)}
.nav-drop .admin-link:hover{background:#FFEBEE}
/* Right */
.nav-right{display:flex;align-items:center;gap:.45rem;flex-shrink:0;margin-left:.4rem}
.nav-avatar-btn{width:36px;height:36px;border-radius:50%;cursor:pointer;border:2px solid rgba(255,193,7,.5)}
.nav-avatar-ph{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.15);border:2px solid rgba(255,193,7,.4);display:flex;align-items:center;justify-content:center;font-size:.9rem;cursor:pointer}
.nav-badge{position:absolute;top:-4px;right:-4px;width:17px;height:17px;background:var(--red);border-radius:50%;font-size:.55rem;font-weight:700;color:#fff;display:flex;align-items:center;justify-content:center;border:2px solid #07225c}
/* Hamburger */
.hb{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:5px;background:none;border:none;cursor:pointer;width:44px;height:44px;padding:0;border-radius:10px;flex-shrink:0}
.hb span{width:23px;height:2.5px;background:#fff;border-radius:2px;display:block;transition:all .25s}
.hb.open span:nth-child(1){transform:rotate(45deg) translate(5px,5px)}
.hb.open span:nth-child(2){opacity:0}
.hb.open span:nth-child(3){transform:rotate(-45deg) translate(5px,-5px)}
@media(min-width:880px){.nav-links{display:flex}.hb{display:none}}

/* ════ MOBILE DRAWER ════ */
.mob-ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:1000}
.mob-dr{
  position:fixed;top:0;left:0;bottom:0;width:285px;max-width:88vw;
  background:linear-gradient(180deg,#07225c 0%,#091a38 100%);
  z-index:1001;transform:translateX(-100%);transition:transform .3s ease;
  overflow-y:auto;border-right:2px solid rgba(212,160,23,.2);
}
.mob-dr{visibility:hidden;transition:transform .3s ease,visibility .3s}
.mob-dr.open{transform:translateX(0);visibility:visible}
.mob-head{display:flex;align-items:center;justify-content:space-between;padding:.9rem 1rem;background:rgba(0,0,0,.28);border-bottom:1px solid rgba(255,255,255,.07)}
.mob-cls{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);color:#fff;border-radius:10px;min-width:44px;min-height:44px;padding:.35rem .65rem;cursor:pointer;font-size:.9rem}
.mob-sec{padding:.55rem 1rem .1rem;font-size:.66rem;font-weight:700;letter-spacing:.15em;color:rgba(255,255,255,.6);text-transform:uppercase;margin-top:.3rem}
.mob-a{display:flex;align-items:center;gap:.7rem;min-height:46px;padding:.6rem 1rem;color:rgba(255,255,255,.82);font-size:.87rem;font-weight:500;border-left:3px solid transparent;transition:all .15s}
.mob-a.on{background:rgba(255,255,255,.08);border-left-color:var(--gold2);color:#fff;font-weight:700}
.mob-a:hover{background:rgba(255,255,255,.06);border-left-color:var(--gold2);color:#fff}
.mob-a .em{width:22px;text-align:center;font-size:.95rem}
.mob-badge{background:var(--red);color:#fff;font-size:.6rem;font-weight:700;padding:.1rem .4rem;border-radius:20px;margin-left:auto}
.mob-user{display:flex;align-items:center;gap:.75rem;padding:.85rem 1rem;background:rgba(255,255,255,.05);border-bottom:1px solid rgba(255,255,255,.07)}

/* ════ PAGE CONTENT WRAPPER ════ */
.page-wrap{min-height:calc(100vh - 66px)}

/* ════ OLD-STYLE CSS — used by existing pages ════ */
.hero{background:linear-gradient(135deg,#07225c 0%,#0D47A1 55%,#1565C0 100%);padding:2.2rem 1.2rem 1.8rem;text-align:center;color:#fff;position:relative;overflow:hidden}
.hero h1{font-family:'Bebas Neue',sans-serif;font-size:clamp(1.8rem,5vw,2.8rem);letter-spacing:.08em;color:#fff;margin-bottom:.3rem}
.hero h1 span{color:var(--gold2)}
.hero-place{font-size:.72rem;color:rgba(255,255,255,.55);letter-spacing:.18em;text-transform:uppercase;font-weight:600;margin-bottom:.35rem}
.hero-tagline{font-size:.9rem;color:rgba(255,255,255,.7);font-style:italic}
.red-bar{height:4px;background:repeating-linear-gradient(90deg,var(--gold) 0,var(--gold) 10px,var(--red) 10px,var(--red) 20px,var(--blue) 20px,var(--blue) 30px,var(--gold2) 30px,var(--gold2) 40px)}
.section{max-width:960px;margin:0 auto;padding:1.4rem 1rem 2rem}
.section-lg{max-width:1180px;margin:0 auto;padding:1.4rem 1rem 2rem}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin-bottom:1.5rem}
.stat{background:#fff;border-radius:var(--radius);padding:1rem .5rem;text-align:center;box-shadow:var(--shadow);border-top:3px solid var(--blue)}
.stat-num{font-family:'Bebas Neue',sans-serif;font-size:1.9rem;color:var(--blue);line-height:1}
.stat-lbl{font-size:.65rem;color:var(--t3);text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin-top:.2rem}
@media(max-width:500px){.stats-row{grid-template-columns:1fr 1fr}}
/* Cards */
.card{background:#fff;border-radius:var(--radius);box-shadow:var(--shadow);border:1px solid var(--border)}
.card-header{padding:1rem 1.3rem;border-bottom:1px solid var(--border)}
.card-header h3{font-family:'Bebas Neue',sans-serif;font-size:1.2rem;letter-spacing:.06em;color:var(--blue);margin:0}
.card-body{padding:1.2rem 1.3rem}
.card-header-blue{background:linear-gradient(135deg,#07225c,var(--blue));color:#fff;padding:1rem 1.3rem;border-radius:var(--radius) var(--radius) 0 0}
.card-header-blue h3{color:#fff;margin:0;font-family:'Bebas Neue',sans-serif;font-size:1.2rem;letter-spacing:.06em}
/* Alerts */
.alert{border-radius:var(--radius-sm);padding:.75rem 1rem;font-size:.88rem;font-weight:500;margin-bottom:.9rem;line-height:1.45}
.alert-ok{background:#f0fdf4;color:#166534;border-left:4px solid #16a34a}
.alert-err,.alert-error{background:#fff0f0;color:#991b1b;border-left:4px solid #dc2626}
.alert-warn{background:#fffbeb;color:#92400e;border-left:4px solid #f59e0b}
.alert-info{background:#eff6ff;color:#1e40af;border-left:4px solid #3b82f6}
/* Buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.4rem;padding:.58rem 1.1rem;border-radius:var(--radius-sm);font-family:'DM Sans',sans-serif;font-weight:600;font-size:.85rem;cursor:pointer;border:none;transition:all .2s;white-space:nowrap}
.btn-blue{background:var(--blue);color:#fff}.btn-blue:hover{background:#0a3a8a;transform:translateY(-1px);box-shadow:0 6px 18px rgba(13,71,161,.3)}
.btn-green{background:#2e7d32;color:#fff}.btn-green:hover{background:var(--green)}
.btn-red{background:var(--red);color:#fff}.btn-red:hover{background:#c62828}
.btn-gold{background:var(--gold);color:#fff}.btn-gold:hover{background:var(--gold2);color:#000}
.btn-outline{background:transparent;border:1.5px solid var(--border);color:var(--t2)}.btn-outline:hover{border-color:var(--blue);color:var(--blue)}
.btn-sm{padding:.35rem .75rem;font-size:.78rem}
.btn-block{width:100%}
.btn:disabled{opacity:.55;cursor:not-allowed;transform:none!important}
/* Forms */
.lbl{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--t2);display:block;margin-bottom:.35rem}
.inp{width:100%;padding:.7rem .9rem;border:2px solid var(--border);border-radius:var(--radius-sm);font-family:'DM Sans',sans-serif;font-size:1rem;color:#0D1B3E;background:#fff;outline:none;transition:border-color .18s;-webkit-appearance:none}
.inp:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(13,71,161,.09)}
.inp::placeholder{color:#6E7A93}
.fg{margin-bottom:.85rem}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem}
@media(max-width:500px){.g2,.g3{grid-template-columns:1fr}}
/* Misc */
.pending-dot{display:inline-block;width:8px;height:8px;background:var(--red);border-radius:50%;margin-right:.4rem;animation:blink 1s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.mb-1{margin-bottom:.5rem}.mb-2{margin-bottom:1rem}.mb-3{margin-bottom:1.5rem}
.text-center{text-align:center}
/* Popup modal */
.popup-ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2000;align-items:center;justify-content:center;padding:1rem;backdrop-filter:blur(5px)}
.popup-ov.show{display:flex}
.popup-box{background:#fff;border-radius:18px;width:100%;max-width:480px;box-shadow:0 24px 70px rgba(0,0,0,.22);overflow:hidden;animation:popIn .28s ease both;max-height:90vh;display:flex;flex-direction:column}
@keyframes popIn{from{opacity:0;transform:scale(.88) translateY(20px)}to{opacity:1;transform:scale(1) translateY(0)}}
.popup-bar{height:4px;background:linear-gradient(90deg,var(--gold),var(--blue),var(--gold2));flex-shrink:0}
.popup-head{display:flex;align-items:center;justify-content:space-between;padding:1.1rem 1.4rem .6rem;flex-shrink:0}
.popup-head h3{font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.07em;color:var(--blue);margin:0}
.popup-close{background:rgba(0,0,0,.06);border:none;width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:.9rem;color:var(--t2);display:flex;align-items:center;justify-content:center;transition:all .2s}
.popup-close:hover{background:#FFEBEE;color:var(--red)}
.popup-body{padding:1.1rem 1.4rem 1.4rem;overflow-y:auto}
.form-msg{display:none;border-radius:8px;padding:.65rem .95rem;font-size:.84rem;font-weight:500;margin-bottom:.85rem;line-height:1.45}
.form-msg.ok{display:block;background:#f0fdf4;border:1px solid #bbf7d0;color:#166534}
.form-msg.err{display:block;background:#fff0f0;border:1px solid #fecaca;color:#991b1b}
/* ════ UX / ACCESSIBILITY LAYER ════ */
.skip-link{position:absolute;left:.75rem;top:-100px;z-index:3000;background:#fff;color:var(--navy);font-weight:700;padding:.7rem 1rem;border-radius:10px;box-shadow:var(--shadow-lg)}
.skip-link:focus{top:.75rem}
:focus{outline:none}
:focus-visible{outline:3px solid var(--focus-dark);outline-offset:2px;border-radius:6px}
.navbar :focus-visible,.mob-dr :focus-visible,footer :focus-visible{outline-color:var(--focus)}
.inp:focus-visible{outline:none}
.nav-dd-btn[aria-expanded="true"]{background:rgba(255,255,255,.15);color:#fff}
.nav-avatar-wrap{background:none;border:none;padding:4px;margin:0;cursor:pointer;border-radius:50%;display:flex;align-items:center;justify-content:center;min-width:44px;min-height:44px}
.nav-avatar-wrap .nav-avatar-btn,.nav-avatar-wrap .nav-avatar-ph{cursor:inherit}
/* Comfortable tap targets on touch screens */
@media (pointer:coarse){
  .btn{min-height:44px}
  .btn-sm{min-height:40px}
  .nav-drop a{min-height:44px}
}
.btn:active:not(:disabled){transform:scale(.98)}
/* Respect "reduce motion" system setting */
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}
}
.page-wrap{padding-left:env(safe-area-inset-left,0px);padding-right:env(safe-area-inset-right,0px)}
.page-wrap:focus{outline:none}
</style>
  <script>
  // Register service worker
  if('serviceWorker' in navigator){
    window.addEventListener('load',function(){
      navigator.serviceWorker.register('/sw.js').catch(function(){});
    });
  }
  // PWA install prompt — capture it
  window._pwaPrompt = null;
  window.addEventListener('beforeinstallprompt', function(e){
    e.preventDefault();
    window._pwaPrompt = e;
    // Show button if exists
    var btn = document.getElementById('pwaInstallBtn');
    if(btn) btn.style.display = 'flex';
  });
  </script>
</head>
<body>
<a href="#main" class="skip-link">Skip to content</a>

<!-- ════ NAVBAR ════ -->
<nav class="navbar" aria-label="Main">
<div class="nav-wrap">

  <!-- Brand -->
  <a href="<?= url('dashboard.php') ?>" class="nav-brand">
    <?php if($logoB64): ?>
      <img src="<?= $logoB64 ?>" class="nav-brand-logo" alt="" width="42" height="42">
    <?php else: ?>
      <div class="nav-brand-ph" aria-hidden="true">⚜</div>
    <?php endif; ?>
    <div>
      <div class="nav-brand-name"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></div>
      <div class="nav-brand-sub"><?= h(setting('CLUB_PLACE','Vettikkattiri')) ?> · Kerala</div>
    </div>
  </a>

  <!-- Desktop Nav -->
  <ul class="nav-links" id="desktopNav">
    <li><a href="<?= url('dashboard.php') ?>" class="<?= $curPage==='dashboard.php'?'on':'' ?>"<?= $curPage==='dashboard.php'?' aria-current="page"':'' ?>><i aria-hidden="true" class="fas fa-home"></i> Home</a></li>
    <li><a href="<?= url('modules/members.php') ?>" class="<?= $curPage==='members.php'?'on':'' ?>"<?= $curPage==='members.php'?' aria-current="page"':'' ?>><i aria-hidden="true" class="fas fa-users"></i> Members</a></li>
    <li><a href="<?= url('modules/events.php') ?>" class="<?= $curPage==='events.php'?'on':'' ?>"<?= $curPage==='events.php'?' aria-current="page"':'' ?>><i aria-hidden="true" class="fas fa-calendar"></i> Events</a></li>
    <li><a href="<?= url('modules/blood.php') ?>" class="<?= $curPage==='blood.php'?'on':'' ?>"<?= $curPage==='blood.php'?' aria-current="page"':'' ?>><i aria-hidden="true" class="fas fa-tint"></i> Blood</a></li>
    <li><a href="<?= url('modules/market.php') ?>" class="<?= $curPage==='market.php'?'on':'' ?>"<?= $curPage==='market.php'?' aria-current="page"':'' ?>><i aria-hidden="true" class="fas fa-store"></i> Market</a></li>

    <!-- Activities dropdown -->
    <li class="nav-dd">
      <button type="button" class="nav-dd-btn" aria-haspopup="true" aria-expanded="false" aria-controls="ddAct" onclick="toggleDrop('ddAct')"><i aria-hidden="true" class="fas fa-star"></i> Activities <i aria-hidden="true" class="fas fa-chevron-down" style="font-size:.6rem"></i></button>
      <div class="nav-drop" id="ddAct">
        <a href="<?= url('modules/football.php') ?>"><div class="di" aria-hidden="true" style="background:#e8f5e9">⚽</div> Football Tournament</a>
        <a href="<?= url('modules/arts_festival.php') ?>"><div class="di" aria-hidden="true" style="background:#f3e5f5">🎭</div> Arts Festival</a>
        <a href="<?= url('modules/onam.php') ?>"><div class="di" aria-hidden="true" style="background:#fff8e1">🌸</div> Onam Celebration</a>
        <a href="<?= url('modules/henna_fest.php') ?>"><div class="di" aria-hidden="true" style="background:#fff3e0">🌿</div> Henna Fest</a>
        <a href="<?= url('modules/election.php') ?>"><div class="di" aria-hidden="true" style="background:#e3f2fd">🗳️</div> Elections</a>
        <a href="<?= url('modules/donation.php') ?>"><div class="di" aria-hidden="true" style="background:#fce4ec">💚</div> Donations</a>
        <a href="<?= url('modules/crowdfund.php') ?>"><div class="di" aria-hidden="true" style="background:#fce4ec">❤️</div> Crowd Funding</a>
        <a href="<?= url('modules/market.php') ?>"><div class="di" aria-hidden="true" style="background:#e8f5e9">🛍️</div> Mini Market</a>
        <?php if(isSuperAdmin($user)): ?><a href="<?= url('modules/settings.php') ?>"><div class="di" aria-hidden="true" style="background:#e8eaf6">⚙️</div> Club Settings</a><?php endif; ?>
      </div>
    </li>

    <!-- My Account dropdown -->
    <li class="nav-dd">
      <button type="button" class="nav-dd-btn" aria-haspopup="true" aria-expanded="false" aria-controls="ddMe" onclick="toggleDrop('ddMe')"><i aria-hidden="true" class="fas fa-user-circle"></i> My Account <i aria-hidden="true" class="fas fa-chevron-down" style="font-size:.6rem"></i></button>
      <div class="nav-drop" id="ddMe">
        <a href="<?= url('modules/profile.php') ?>"><div class="di" aria-hidden="true" style="background:#e3f2fd">👤</div> My Profile</a>
        <a href="<?= url('modules/idcard.php') ?>"><div class="di" aria-hidden="true" style="background:#e8f5e9">🪪</div> ID Card</a>
        <a href="<?= url('modules/nameslip.php') ?>"><div class="di" aria-hidden="true" style="background:#e3f2fd">📚</div> Name Slip</a>
        <a href="<?= url('modules/certificate.php') ?>"><div class="di" aria-hidden="true" style="background:#fff8e1">🏅</div> Certificate</a>
        <a href="<?= url('modules/subscription.php') ?>"><div class="di" aria-hidden="true" style="background:#fce4ec">💳</div> Subscription</a>
        <div class="nav-drop-sep"></div>
        <a href="<?= url('modules/skills.php') ?>"><div class="di" aria-hidden="true" style="background:#e8f5e9">⭐</div> Talents</a>
        <a href="<?= url('modules/gallery.php') ?>"><div class="di" aria-hidden="true" style="background:#f3e5f5">📸</div> Gallery</a>
        <a href="<?= url('index.php') ?>"><div class="di" aria-hidden="true" style="background:#e3f2fd">🌐</div> Public Site</a>
      </div>
    </li>

    <?php if($isAdmin): ?>
    <!-- Admin dropdown -->
    <li class="nav-dd" style="position:relative">
      <button type="button" class="nav-dd-btn admin-btn" aria-haspopup="true" aria-expanded="false" aria-controls="ddAdmin" onclick="toggleDrop('ddAdmin')">
        <i aria-hidden="true" class="fas fa-shield-alt"></i> Admin
        <?php if($pendingBadge): ?><span style="background:#ef5350;color:#fff;font-size:.6rem;padding:.08rem .4rem;border-radius:20px;font-weight:700"><?= $pendingBadge ?></span><?php endif; ?>
        <i aria-hidden="true" class="fas fa-chevron-down" style="font-size:.6rem"></i>
      </button>
      <div class="nav-drop" id="ddAdmin">
        <a href="<?= url('admin.php') ?>" class="admin-link">
          <div class="di" aria-hidden="true" style="background:#ffebee">🛡️</div> Admin Panel
          <?php if($pendingBadge): ?><span style="background:#ef5350;color:#fff;font-size:.6rem;padding:.08rem .4rem;border-radius:20px;font-weight:700;margin-left:auto"><?= $pendingBadge ?></span><?php endif; ?>
        </a>
        <a href="<?= url('modules/admin_subscriptions.php') ?>" class="admin-link"><div class="di" aria-hidden="true" style="background:#fff8e1">💰</div> Subscriptions</a>
        <a href="<?= url('modules/gallery.php') ?>"><div class="di" aria-hidden="true" style="background:#e3f2fd">📸</div> Manage Gallery</a>
        <a href="<?= url('modules/crowdfund.php') ?>"><div class="di" aria-hidden="true" style="background:#fce4ec">❤️</div> Crowd Funding</a>
        <?php if(isSuperAdmin($user)): ?><a href="<?= url('modules/settings.php') ?>"><div class="di" aria-hidden="true" style="background:#e8eaf6">⚙️</div> Club Settings</a><?php endif; ?>
        <a href="<?= url('modules/broadcast.php') ?>"><div class="di" aria-hidden="true" style="background:#e8f5e9">📢</div> WA Broadcast</a>
      </div>
    </li>
    <?php endif; ?>
  </ul>

  <!-- Right side -->
  <div class="nav-right">
    <!-- User avatar with dropdown -->
    <?php if($user): ?>
    <div class="nav-dd" style="position:relative">
      <button type="button" class="nav-avatar-wrap" aria-label="Account menu for <?= h($user['name']) ?>" aria-haspopup="true" aria-expanded="false" aria-controls="ddUser" onclick="toggleDrop('ddUser')">
      <?php if($userPhotoB64): ?>
        <img src="<?= $userPhotoB64 ?>" class="nav-avatar-btn" alt="" width="36" height="36" style="object-fit:cover">
      <?php else: ?>
        <span class="nav-avatar-ph" aria-hidden="true">👤</span>
      <?php endif; ?>
      </button>
      <div class="nav-drop right" id="ddUser">
        <div style="padding:.55rem .85rem .25rem;font-size:.83rem;font-weight:700;color:#0D1B3E"><?= h($user['name']) ?></div>
        <div style="padding:0 .85rem .55rem;font-size:.71rem;color:var(--t3)"><?= h(roleLabel($user['role'])) ?></div>
        <div class="nav-drop-sep"></div>
        <a href="<?= url('modules/profile.php') ?>"><div class="di" aria-hidden="true" style="background:#e3f2fd">👤</div> My Profile</a>
        <a href="<?= url('logout.php') ?>" style="color:var(--red)"><div class="di" aria-hidden="true" style="background:#ffebee">🚪</div> Logout</a>
      </div>
    </div>
    <?php endif; ?>
    <button type="button" class="hb" id="hbBtn" onclick="openDrawer()" aria-label="Open menu" aria-expanded="false" aria-controls="mobDr"><span></span><span></span><span></span></button>
  </div>

</div>
</nav>

<!-- ════ MOBILE DRAWER ════ -->
<div class="mob-ov" id="mobOv" onclick="closeDrawer()"></div>
<div class="mob-dr" id="mobDr" role="dialog" aria-modal="true" aria-label="Menu" aria-hidden="true">
  <div class="mob-head">
    <div style="display:flex;align-items:center;gap:.6rem">
      <?php if($logoB64): ?><img src="<?= $logoB64 ?>" style="width:32px;height:32px;border-radius:50%;border:1.5px solid rgba(212,160,23,.5);object-fit:cover" alt=""><?php endif; ?>
      <span style="font-family:'Bebas Neue',sans-serif;font-size:.9rem;letter-spacing:.09em;color:#fff">AASC Menu</span>
    </div>
    <button type="button" class="mob-cls" onclick="closeDrawer()" aria-label="Close menu">✕</button>
  </div>

  <?php if($user): ?>
  <a href="<?= url('modules/profile.php') ?>" class="mob-user" onclick="closeDrawer()">
    <?php if($userPhotoB64): ?><img src="<?= $userPhotoB64 ?>" style="width:38px;height:38px;border-radius:50%;object-fit:cover;border:2px solid rgba(212,160,23,.4)" alt=""><?php else: ?><div style="width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.12);border:2px solid rgba(212,160,23,.4);display:flex;align-items:center;justify-content:center;font-size:1rem">👤</div><?php endif; ?>
    <div><div style="color:#fff;font-weight:700;font-size:.88rem"><?= h($user['name']) ?></div><div style="color:rgba(255,255,255,.42);font-size:.66rem"><?= h(roleLabel($user['role'])) ?></div></div>
  </a>
  <?php endif; ?>

  <?php
  $navGroups = array(
    'Main' => array(
      array('dashboard.php','🏠','Home'),
      array('modules/members.php','👥','Members'),
      array('modules/events.php','📅','Events'),
      array('modules/blood.php','🩸','Blood Hub'),
      array('modules/skills.php','⭐','Talents'),
      array('modules/gallery.php','📸','Gallery'),
      array('modules/market.php','🛍️','Mini Market'),
    ),
    'My Account' => array(
      array('modules/profile.php','👤','My Profile'),
      array('modules/idcard.php','🪪','My ID Card'),
      array('modules/nameslip.php','📚','Name Slip'),
      array('modules/certificate.php','🏅','Certificate'),
      array('modules/subscription.php','💳','Subscription'),
    ),
    'Club Activities' => array(
      array('modules/football.php','⚽','Football Tournament'),
      array('modules/arts_festival.php','🎭','Arts Festival'),
      array('modules/onam.php','🌸','Onam Celebration'),
      array('modules/henna_fest.php','🌿','Henna Fest'),
      array('modules/election.php','🗳️','Elections'),
      array('modules/donation.php','💚','Donations'),
      array('modules/crowdfund.php','❤️','Crowd Funding'),
    ),
    'More' => array(
      array('index.php','🌐','Public Website'),
    ),
  );
  foreach($navGroups as $sec => $links):
  ?>
  <div class="mob-sec"><?= $sec ?></div>
  <?php foreach($links as $lnk): ?>
  <?php $_on = ($curPage === basename($lnk[0])); ?>
  <a href="<?= url($lnk[0]) ?>" onclick="closeDrawer()" class="mob-a<?= $_on?' on':'' ?>"<?= $_on?' aria-current="page"':'' ?>>
    <span class="em" aria-hidden="true"><?= $lnk[1] ?></span><?= $lnk[2] ?>
  </a>
  <?php endforeach; endforeach; ?>

  <?php if($isAdmin): ?>
  <div class="mob-sec" style="color:rgba(255,120,120,.5);margin-top:.3rem">Admin</div>
  <a href="<?= url('admin.php') ?>" onclick="closeDrawer()" class="mob-a" style="color:#ef9a9a">
    <span class="em" aria-hidden="true">🛡️</span>Admin Panel
    <?php if($pendingBadge): ?><span class="mob-badge"><?= $pendingBadge ?></span><?php endif; ?>
  </a>
  <a href="<?= url('modules/admin_subscriptions.php') ?>" onclick="closeDrawer()" class="mob-a" style="color:#ef9a9a"><span class="em" aria-hidden="true">💰</span>Subscription Mgmt</a>
  <a href="<?= url('modules/settings.php') ?>" onclick="closeDrawer()" class="mob-a" style="color:#ef9a9a"><span class="em" aria-hidden="true">⚙️</span>Club Settings</a>
  <a href="<?= url('modules/broadcast.php') ?>" onclick="closeDrawer()" class="mob-a" style="color:#ef9a9a"><span class="em" aria-hidden="true">📢</span>WA Broadcast</a>
  <?php endif; ?>

  <div style="padding:.8rem 1rem;border-top:1px solid rgba(255,255,255,.07);margin-top:.5rem">
    <a href="<?= url('logout.php') ?>" style="display:flex;align-items:center;gap:.7rem;padding:.62rem 1rem;color:rgba(255,100,100,.85);font-size:.87rem;font-weight:700;background:rgba(183,28,28,.1);border-radius:10px;border:1px solid rgba(183,28,28,.2)">
      <span aria-hidden="true">🚪</span>Logout
    </a>
  </div>
</div>

<main class="page-wrap" id="main" tabindex="-1">

<script>
// ── Dropdown ──
var _dropIds = ['ddAct','ddMe','ddAdmin','ddUser'];
function _setDrop(d, open) {
  var el = document.getElementById(d); if (!el) return;
  el.classList.toggle('open', open);
  var b = document.querySelector('[aria-controls="'+d+'"]');
  if (b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
}
function closeDrops() { _dropIds.forEach(function(d){ _setDrop(d, false); }); }
function toggleDrop(id) {
  var el = document.getElementById(id); if (!el) return;
  var willOpen = !el.classList.contains('open');
  closeDrops();
  _setDrop(id, willOpen);
}
document.addEventListener('click', function(e) {
  if (!e.target.closest('.nav-dd')) closeDrops();
});
// ── Drawer ──
function openDrawer() {
  var dr = document.getElementById('mobDr'), hb = document.getElementById('hbBtn');
  document.getElementById('mobOv').style.display = 'block';
  dr.classList.add('open'); dr.setAttribute('aria-hidden','false');
  hb.classList.add('open'); hb.setAttribute('aria-expanded','true');
  document.body.style.overflow = 'hidden';
  var c = dr.querySelector('.mob-cls'); if (c) setTimeout(function(){ c.focus(); }, 50);
}
function closeDrawer() {
  var dr = document.getElementById('mobDr'), hb = document.getElementById('hbBtn');
  if (!dr.classList.contains('open')) return;
  document.getElementById('mobOv').style.display = 'none';
  dr.classList.remove('open'); dr.setAttribute('aria-hidden','true');
  hb.classList.remove('open'); hb.setAttribute('aria-expanded','false');
  document.body.style.overflow = '';
  if (hb.offsetParent !== null) hb.focus();
}
// ── Popup helpers ──
function openPopup(id) { document.getElementById(id).classList.add('show'); document.body.style.overflow='hidden'; }
function closePopup(id) { document.getElementById(id).classList.remove('show'); document.body.style.overflow=''; }
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.popup-ov.show').forEach(function(p) { p.classList.remove('show'); });
    closeDrops();
    closeDrawer();
    document.body.style.overflow = '';
  }
});
// ── AJAX form helper ──
function ajaxPost(url, data, cb) {
  var fd = new FormData();
  fd.append('ajax','1');
  Object.keys(data).forEach(function(k){ fd.append(k, data[k]); });
  fetch(url, {method:'POST', body:fd})
    .then(function(r){ return r.json(); })
    .then(cb)
    .catch(function(){ cb({ok:false,msg:'Network error. Please try again.'}); });
}
</script>
