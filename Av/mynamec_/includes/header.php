<?php
// ================================================================
// header.php — app shell for every member page (PHP 7.3 compatible)
// Design: dark "ink" app frame + glass, teal primary, coral accent,
//         light content surface. Tokens below; old token names are
//         mapped to the new palette so every module picks it up.
// ================================================================
require_once __DIR__.'/config.php';
require_once __DIR__.'/icons.php';
$user         = currentUser();
$logoB64      = getLogoB64();
$userPhotoB64 = ($user && !empty($user['profile_photo']) && $user['profile_photo'] !== 'default.png')
                  ? getMemberPhoto($user['profile_photo']) : '';
$isAdmin  = (isset($isAdmin) && $isAdmin) ? true : ($user && isAdminRole($user['role']));
$canPost  = $user && canPost($user['role']);
$curPage  = basename($_SERVER['PHP_SELF']);
$isHome   = ($curPage === 'dashboard.php');
$pendingBadge = 0;
if ($isAdmin) {
    try { $pendingBadge = (int)db()->query("SELECT COUNT(*) FROM users WHERE status='pending'")->fetchColumn(); } catch(Exception $e){}
}
// Title shown in the top bar on sub-pages
$_barTitle = isset($pageTitle) && $pageTitle ? trim(preg_split('/\s+[—|·-]\s+/u', $pageTitle)[0]) : '';
if (!$_barTitle) {
    foreach (array_merge(app_modules(), admin_modules()) as $_m) { if (basename($_m[0]) === $curPage) { $_barTitle = $_m[1]; break; } }
}
// 3D icon of the current module (shown in its page banner)
$_modImg = '';
foreach (array_merge(app_modules(), admin_modules()) as $_m) { if (basename($_m[0]) === $curPage) { $_modImg = url('assets/icons/3d/'.$_m[5].'.webp'); break; } }
$_club  = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$_place = setting('CLUB_PLACE','Vettikkattiri');

// ── OG / WhatsApp share tags (pages may set $pageOG before including) ──
$_logo_url  = defined('LOGO_URL') ? LOGO_URL : '';
$_site_url  = rtrim(defined('SITE_URL') ? SITE_URL : '', '/');
$_cur_url   = $_site_url . (isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '');
$_og_title  = isset($pageOG['title']) ? $pageOG['title'] : ($_barTitle ? $_barTitle . ' — ' . $_club : $_club . ' · ' . $_place);
$_og_desc   = isset($pageOG['desc'])  ? $pageOG['desc']  : $_club . ', ' . $_place . ', Kerala — Members portal';
$_og_img    = isset($pageOG['image']) ? $pageOG['image'] : $_logo_url;
$_og_url    = isset($pageOG['url'])   ? $pageOG['url']   : $_cur_url;
?><!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<meta name="theme-color" content="#0A14E0">
<meta name="color-scheme" content="light">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aishwarya">
<link rel="apple-touch-icon" href="/assets/logo.jpg">
<link rel="manifest" href="/manifest.php">
<title><?= h($_barTitle ? $_barTitle . ' · ' . $_club : $_club) ?></title>
<?php if($_logo_url): ?><link rel="icon" href="<?= h($_logo_url) ?>"><?php endif; ?>
<meta property="og:type"        content="website">
<meta property="og:site_name"   content="<?= h($_club) ?>">
<meta property="og:title"       content="<?= h($_og_title) ?>">
<meta property="og:description" content="<?= h($_og_desc) ?>">
<meta property="og:image"       content="<?= h($_og_img) ?>">
<meta property="og:url"         content="<?= h($_og_url) ?>">
<meta name="twitter:card"       content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Bebas+Neue&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
/* ═══════════ TOKENS ═══════════ */
:root{
  /* new palette */
  /* logo colours: red #FA0500 / blue #000AFC, tuned for readable text */
  --ink:#0B1033; --ink-2:#121A5C; --ink-3:#1A2380;
  --primary:#0A14E0; --primary-dark:#070FA8; --primary-light:#A9B0FF; --primary-soft:#ECEEFF;
  --accent:#E30613; --accent-ink:#B80F0A; --accent-light:#FFB3B0; --accent-soft:#FFECEC;
  --brand-grad:linear-gradient(105deg,#D9050F 0%,#8A0A8E 50%,#0A14E0 100%);
  --surface:#F5F7FF; --card:#FFFFFF; --line:#E3E7F5;
  --text:#0B1033; --text-2:#3B4266; --text-3:#565D82;
  --ok:#15803D; --danger:#C0392B; --warn:#B45309;
  --glass:rgba(255,255,255,.07); --glass-line:rgba(255,255,255,.12);
  --r-lg:22px; --r:16px; --r-sm:12px;
  --sh-1:0 1px 2px rgba(10,26,31,.05),0 4px 16px rgba(10,26,31,.06);
  --sh-2:0 12px 40px rgba(10,26,31,.16);
  --font:'Plus Jakarta Sans',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --bar-h:60px;
  /* old names → new palette (modules use these) */
  --blue:var(--primary); --blue2:var(--primary-dark); --navy:var(--ink);
  --red:var(--danger); --gold:var(--accent); --gold2:var(--accent-light);
  --green:var(--ok); --purple:#6D28D9;
  --t2:var(--text-2); --t3:var(--text-3);
  --bg:var(--surface); --border:var(--line);
  --shadow:var(--sh-1); --shadow-lg:var(--sh-2);
  --radius:var(--r); --radius-sm:var(--r-sm);
  --focus:var(--accent-light); --focus-dark:var(--primary);
}
@view-transition{navigation:auto}

/* ═══════════ BASE ═══════════ */
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{font-family:var(--font);background:var(--surface);color:var(--text);line-height:1.6;
  padding-top:calc(var(--bar-h) + env(safe-area-inset-top,0px));-webkit-tap-highlight-color:transparent}
a{text-decoration:none;color:inherit}
img{display:block;max-width:100%}
button,input,select,textarea{font-family:inherit}
.ic{width:22px;height:22px;flex-shrink:0;display:inline-block;vertical-align:middle}
.ic-sm{width:18px;height:18px}.ic-lg{width:28px;height:28px}
::-webkit-scrollbar{width:6px;height:6px}::-webkit-scrollbar-thumb{background:#c3c8e6;border-radius:6px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.skip-link{position:absolute;left:.75rem;top:-100px;z-index:3000;background:#fff;color:var(--ink);font-weight:700;padding:.7rem 1rem;border-radius:12px;box-shadow:var(--sh-2)}
.skip-link:focus{top:.75rem}
:focus{outline:none}
:focus-visible{outline:3px solid var(--primary);outline-offset:2px;border-radius:8px}
.appbar :focus-visible,.hero :focus-visible,.hero-card :focus-visible{outline-color:#fff}
.inp:focus-visible{outline:none}

/* ═══════════ TOP APP BAR (glass) ═══════════ */
.appbar,.navbar{position:fixed;top:0;left:0;right:0;z-index:900;
  padding-top:env(safe-area-inset-top,0px);
  background:var(--brand-grad);box-shadow:0 6px 20px -10px rgba(10,20,224,.6);color:#fff}
.bar-in{height:var(--bar-h);max-width:1200px;margin:0 auto;padding:0 .6rem;display:flex;align-items:center;gap:.35rem}
.bar-btn{width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center;
  background:transparent;border:0;color:#fff;cursor:pointer;position:relative;transition:background .15s}
.bar-btn:hover{background:rgba(255,255,255,.16)}
.bar-btn:active{transform:scale(.94)}
.bar-brand{display:flex;align-items:center;gap:.6rem;min-width:0;margin-right:auto;padding-left:.25rem}
.bar-logo{width:38px;height:38px;border-radius:50%;box-shadow:0 0 0 2px rgba(255,255,255,.8);object-fit:cover;background:#fff;flex-shrink:0}
.bar-name{font-weight:800;font-size:.98rem;letter-spacing:-.01em;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-sub{font-size:.7rem;color:rgba(255,255,255,.88);font-weight:500}
.bar-title{font-weight:700;font-size:1.02rem;margin-right:auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.bar-links{display:none;gap:.15rem;margin:0 .5rem}
.bar-links a{display:flex;align-items:center;gap:.4rem;color:rgba(255,255,255,.9);font-size:.86rem;font-weight:600;padding:.5rem .8rem;border-radius:12px;transition:all .15s}
.bar-links a:hover{color:#fff;background:rgba(255,255,255,.14)}
.bar-links a.on{color:#fff;background:rgba(255,255,255,.22)}
.bar-links .ic{width:18px;height:18px}
@media(min-width:960px){.bar-links{display:flex}}
.dot-badge{position:absolute;top:6px;right:6px;min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:#fff;color:var(--accent-ink);font-size:.66rem;font-weight:800;display:flex;align-items:center;justify-content:center}
.bar-avatar{width:34px;height:34px;border-radius:12px;object-fit:cover}
.bar-avatar-ph{width:34px;height:34px;border-radius:12px;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center}
/* account popover */
.nav-dd{position:relative}
.nav-drop{display:none;position:absolute;top:calc(100% + .5rem);right:0;background:#fff;color:var(--text);border-radius:18px;box-shadow:var(--sh-2);min-width:230px;padding:.45rem;z-index:99;border:1px solid var(--line)}
.nav-drop.open{display:block;animation:pop .16s ease-out}
.nav-drop a{display:flex;align-items:center;gap:.7rem;padding:.6rem .75rem;border-radius:12px;font-size:.9rem;font-weight:600;color:var(--text-2);min-height:44px}
.nav-drop a:hover{background:var(--surface);color:var(--primary)}
.nav-drop-sep{height:1px;background:var(--line);margin:.35rem .3rem}
.nav-drop .who{padding:.55rem .75rem .45rem}
.nav-drop .who b{display:block;font-size:.92rem}
.nav-drop .who span{font-size:.75rem;color:var(--text-3)}
@keyframes pop{from{opacity:0;transform:translateY(-4px) scale(.98)}to{opacity:1;transform:none}}

/* ═══════════ SIDE DRAWER (dark glass) ═══════════ */
.mob-ov{position:fixed;inset:0;background:rgba(11,16,51,.45);backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px);z-index:1000;opacity:0;visibility:hidden;transition:opacity .25s,visibility .25s}
.mob-ov.show{opacity:1;visibility:visible}
.drawer{position:fixed;top:0;left:0;bottom:0;width:320px;max-width:88vw;z-index:1001;
  background:#fff;color:var(--text);box-shadow:var(--sh-2);transform:translateX(-102%);visibility:hidden;transition:transform .3s cubic-bezier(.2,.8,.2,1),visibility .3s;
  overflow-y:auto;padding:calc(env(safe-area-inset-top,0px) + .6rem) .75rem calc(env(safe-area-inset-bottom,0px) + 1rem)}
.drawer.open{transform:none;visibility:visible}
.dr-head{display:flex;align-items:center;justify-content:space-between;padding:.2rem .2rem .7rem}
.drawer .bar-btn{color:var(--text)}.drawer .bar-btn:hover{background:var(--surface)}
.dr-user{display:flex;align-items:center;gap:.75rem;padding:.8rem;border-radius:18px;background:var(--brand-grad);color:#fff;margin-bottom:.4rem}
.dr-user img,.dr-user .ph{width:44px;height:44px;border-radius:50%;object-fit:cover;background:rgba(255,255,255,.2);border:2px solid rgba(255,255,255,.7);display:flex;align-items:center;justify-content:center}
.dr-user b{display:block;font-size:.95rem}
.dr-user span{font-size:.75rem;color:rgba(255,255,255,.9)}
.dr-sec{font-size:.7rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--text);padding:1.1rem .5rem .5rem;font-size:.82rem!important}
.dr-sec::after{content:'';display:block;width:30px;height:3px;border-radius:3px;margin-top:.3rem;background:var(--brand-grad)}
.dr-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem}
.dr-a{display:flex;flex-direction:column;align-items:center;gap:.4rem;padding:.65rem .25rem;border-radius:16px;font-size:.74rem;font-weight:600;color:var(--text-2);text-align:center;line-height:1.2;transition:background .15s;min-height:100px;justify-content:center}
.dr-a .app-img{width:46px;height:46px}
.dr-a:hover{background:var(--surface)}
.dr-a.on{background:var(--primary-soft);color:var(--primary-dark)}
.dr-logout{display:flex;align-items:center;justify-content:center;gap:.55rem;margin-top:1rem;padding:.8rem;border-radius:16px;background:var(--accent-soft);border:1px solid #FFD0CE;color:var(--accent-ink);font-weight:700;font-size:.9rem;min-height:48px}

/* ═══════════ APP ICONS: white tile + 3D picture ═══════════ */
.appic{width:56px;height:56px;border-radius:18px;background:#fff;display:flex;align-items:center;justify-content:center;position:relative;
  border:1px solid var(--line);box-shadow:0 1px 1px rgba(11,16,51,.04),0 8px 18px -10px rgba(10,20,224,.35);transition:transform .15s}
.appic::before{content:'';position:absolute;inset:0;border-radius:inherit;background:linear-gradient(160deg,rgba(227,6,19,.06),rgba(10,20,224,.07));pointer-events:none}
.appic .app-img{width:40px;height:40px;object-fit:contain;position:relative;filter:drop-shadow(0 3px 3px rgba(11,16,51,.15))}
a:active .appic,button:active .appic{transform:scale(.92)}
/* line-icon tiles (notices etc.) */
.tile{width:52px;height:52px;border-radius:17px;display:flex;align-items:center;justify-content:center;position:relative;color:#fff;
  background:linear-gradient(145deg,var(--t1),var(--t2c));box-shadow:0 8px 20px -8px var(--t1),inset 0 1px 0 rgba(255,255,255,.35)}
.tile::after{content:'';position:absolute;inset:0;border-radius:inherit;background:linear-gradient(180deg,rgba(255,255,255,.28),rgba(255,255,255,0) 55%);pointer-events:none}
.tile .ic{width:26px;height:26px;position:relative;z-index:1;filter:drop-shadow(0 1px 1px rgba(0,0,0,.25))}
.tone-teal{--t1:#14B8A6;--t2c:#0F766E}.tone-coral{--t1:#FB8A7B;--t2c:#E1503F}.tone-violet{--t1:#A78BFA;--t2c:#6D28D9}
.tone-amber{--t1:#FBBF24;--t2c:#D97706}.tone-rose{--t1:#FB7185;--t2c:#BE123C}.tone-sky{--t1:#38BDF8;--t2c:#0369A1}
.tone-lime{--t1:#84CC16;--t2c:#3F8F0E}.tone-slate{--t1:#94A3B8;--t2c:#475569}

/* ═══════════ PAGE + SHARED COMPONENTS ═══════════ */
.page-wrap{min-height:calc(100vh - var(--bar-h));padding-left:env(safe-area-inset-left,0px);padding-right:env(safe-area-inset-right,0px)}
.page-wrap:focus{outline:none}
/* page header ("hero") used by modules */
.hero{position:relative;overflow:hidden;color:#fff;text-align:center;padding:2rem 1.2rem 2.2rem;
  background:radial-gradient(70% 120% at 0% 0%,rgba(255,255,255,.16),transparent 55%),var(--brand-grad)}
.hero h1{font-family:var(--font);font-weight:800;font-size:clamp(1.6rem,5vw,2.4rem);letter-spacing:-.02em;color:#fff;margin-bottom:.3rem}
.hero h1 span{color:#fff}
.hero-place{font-size:.74rem;color:rgba(255,255,255,.9);letter-spacing:.14em;text-transform:uppercase;font-weight:700;margin-bottom:.35rem}
.hero-tagline{font-size:.92rem;color:rgba(255,255,255,.8)}
.red-bar{height:4px;background:var(--brand-grad)}
.section{max-width:980px;margin:0 auto;padding:1.2rem 1rem 2rem}
.section-lg{max-width:1200px;margin:0 auto;padding:1.2rem 1rem 2rem}
.section-title{font-weight:800;font-size:1.1rem;letter-spacing:-.01em;color:var(--text);margin:1rem 0 .6rem}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin-bottom:1.3rem}
.stat{background:var(--card);border-radius:var(--r);padding:1rem .5rem;text-align:center;box-shadow:var(--sh-1);border:1px solid var(--line)}
.stat-num{font-weight:800;font-size:1.7rem;color:var(--primary);line-height:1;letter-spacing:-.02em}
.stat-lbl{font-size:.7rem;color:var(--text-3);text-transform:uppercase;letter-spacing:.06em;font-weight:700;margin-top:.3rem}
@media(max-width:520px){.stats-row{grid-template-columns:1fr 1fr}}
.card{background:var(--card);border-radius:var(--r-lg);box-shadow:var(--sh-1);border:1px solid var(--line);overflow:hidden}
.card-header{padding:1rem 1.2rem;border-bottom:1px solid var(--line)}
.card-header h3,.card-header-blue h3{font-family:var(--font);font-weight:800;font-size:1.05rem;letter-spacing:-.01em;color:var(--text);margin:0}
.card-body{padding:1.15rem 1.2rem}
.card-header-blue{background:var(--brand-grad);color:#fff;padding:1rem 1.2rem}
.card-header-blue h3{color:#fff}
.mb-3{margin-bottom:1rem}.mb-1{margin-bottom:.5rem}.mb-2{margin-bottom:1rem}.text-center{text-align:center}
/* alerts */
.alert{border-radius:var(--r-sm);padding:.8rem 1rem;font-size:.9rem;font-weight:500;margin-bottom:.9rem;line-height:1.45;border:1px solid transparent}
.alert-ok{background:#ECFDF3;color:#166534;border-color:#BBF7D0}
.alert-err,.alert-error{background:#FEF2F2;color:#991B1B;border-color:#FECACA}
.alert-warn{background:#FFFBEB;color:#92400E;border-color:#FDE68A}
.alert-info{background:var(--primary-soft);color:var(--primary-dark);border-color:#CDD2FF}
/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.45rem;min-height:44px;padding:.6rem 1.15rem;border-radius:14px;
  font-family:var(--font);font-weight:700;font-size:.9rem;cursor:pointer;border:1.5px solid transparent;transition:transform .1s,box-shadow .15s,background .15s;white-space:nowrap;text-decoration:none}
.btn:active:not(:disabled){transform:scale(.97)}
.btn-blue,.btn-primary{background:var(--primary);color:#fff;box-shadow:0 8px 18px -10px var(--primary)}
.btn-blue:hover,.btn-primary:hover{background:var(--primary-dark)}
.btn-green{background:var(--ok);color:#fff}.btn-green:hover{background:#166534}
.btn-red{background:var(--danger);color:#fff}.btn-red:hover{background:#a5301f}
.btn-gold,.btn-accent{background:var(--accent);color:#fff}.btn-gold:hover,.btn-accent:hover{background:var(--accent-ink)}
.btn-outline{background:var(--card);border-color:var(--line);color:var(--text-2)}.btn-outline:hover{border-color:var(--primary);color:var(--primary)}
.btn-sm{min-height:38px;padding:.4rem .85rem;font-size:.82rem;border-radius:12px}
.btn-block{width:100%}
.btn:disabled{opacity:.55;cursor:not-allowed}
@media (pointer:coarse){.btn-sm{min-height:42px}.nav-drop a{min-height:46px}}
/* forms */
.lbl{font-size:.78rem;font-weight:700;color:var(--text-2);display:block;margin-bottom:.4rem}
.inp{width:100%;min-height:46px;padding:.7rem .95rem;border:1.5px solid var(--line);border-radius:var(--r-sm);font-family:var(--font);font-size:1rem;color:var(--text);background:#fff;outline:none;transition:border-color .15s,box-shadow .15s;-webkit-appearance:none;appearance:none}
textarea.inp{min-height:96px}
select.inp{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='none' stroke='%23565D82' stroke-width='2'%3E%3Cpath d='m2 4 4 4 4-4'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right .9rem center;padding-right:2.4rem}
.inp:focus{border-color:var(--primary);box-shadow:0 0 0 4px rgba(10,20,224,.12)}
.inp::placeholder{color:#6B7194}
.fg{margin-bottom:.9rem}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem}
@media(max-width:520px){.g2,.g3{grid-template-columns:1fr}}
.pending-dot{display:inline-block;width:8px;height:8px;background:var(--accent);border-radius:50%;margin-right:.4rem;animation:blink 1.2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
/* popups: bottom sheet on phones, dialog on desktop */
.popup-ov{display:none;position:fixed;inset:0;background:rgba(11,16,51,.5);z-index:2000;align-items:flex-end;justify-content:center;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
.popup-ov.show{display:flex}
.popup-box{background:#fff;width:100%;max-width:520px;border-radius:24px 24px 0 0;box-shadow:var(--sh-2);overflow:hidden;max-height:92vh;display:flex;flex-direction:column;animation:sheetUp .28s cubic-bezier(.2,.8,.2,1) both;padding-bottom:env(safe-area-inset-bottom,0px)}
@media(min-width:640px){.popup-ov{align-items:center;padding:1rem}.popup-box{border-radius:24px;animation:pop .2s ease-out both}}
@keyframes sheetUp{from{transform:translateY(100%)}to{transform:none}}
.popup-bar{height:5px;width:44px;border-radius:5px;background:#d3d8ee;margin:.6rem auto 0;flex-shrink:0}
@media(min-width:640px){.popup-bar{display:none}}
.popup-head{display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.3rem .5rem;flex-shrink:0}
.popup-head h3{font-family:var(--font);font-weight:800;font-size:1.15rem;color:var(--text);margin:0}
.popup-close{background:var(--surface);border:none;width:44px;height:44px;border-radius:14px;cursor:pointer;color:var(--text-2);display:flex;align-items:center;justify-content:center}
.popup-close:hover{background:var(--accent-soft);color:var(--accent-ink)}
.popup-body{padding:.9rem 1.3rem 1.4rem;overflow-y:auto}
.form-msg{display:none;border-radius:12px;padding:.7rem .95rem;font-size:.86rem;font-weight:500;margin-bottom:.85rem;line-height:1.45}
.form-msg.ok{display:block;background:#ECFDF3;border:1px solid #BBF7D0;color:#166534}
.form-msg.err{display:block;background:#FEF2F2;border:1px solid #FECACA;color:#991B1B}
/* ═══ Unified page banner for every module ═══ */
.hero,.ft-hero,.bh-header,.bc-hero,.ach-hero,.cf-hero,.ev-header,.fm-hero,.gal-hero,.gf-hero,.mk-hero,.adm-header{
  background:radial-gradient(70% 120% at 0% 0%,rgba(255,255,255,.16),transparent 55%),radial-gradient(60% 90% at 100% 100%,rgba(0,0,0,.18),transparent 60%),var(--brand-grad)!important;
  color:#fff!important;position:relative;overflow:hidden;border-radius:0 0 30px 30px;box-shadow:0 18px 36px -24px rgba(10,20,224,.8)}
.hero-ic{display:block;width:78px;height:78px;object-fit:contain;margin:0 auto .55rem;filter:drop-shadow(0 10px 14px rgba(0,0,0,.28))}
.ph-left .hero-ic{margin-left:0}
.ph-title{font-family:var(--font)!important;font-weight:800!important;text-transform:uppercase;letter-spacing:.01em!important;
  font-size:clamp(1.45rem,6.2vw,2.2rem)!important;line-height:1.08!important;color:#fff!important}
.ph-title span:not(.ph-sub){color:#fff!important}
.ph-title::after{content:'';display:block;width:52px;height:4px;border-radius:4px;background:#fff;margin:.6rem auto 0}
.ph-left .ph-title::after{margin-left:0}
.ph-title .ph-sub{display:block;text-transform:none;font-weight:600;font-size:.82rem;letter-spacing:0;opacity:.92;margin-top:.35rem}
.bc-hero-icon,.mk-hero-icon{display:none!important}
/* section headings inside modules */
.section-title,.adm-head h2,.scard-title,.bh-sec-lbl{font-family:var(--font)!important;font-weight:800!important;text-transform:uppercase;letter-spacing:.02em!important;color:var(--text)!important}
.section-title::after,.adm-head h2::after{content:'';display:block;width:40px;height:4px;border-radius:4px;margin-top:.4rem;background:var(--brand-grad)}
.adm-head-line{display:none}
/* table helper */
.tbl-wrap{overflow-x:auto;border-radius:var(--r);border:1px solid var(--line);background:#fff}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}
}
</style>
<script>
window._pwaPrompt = null;
window.addEventListener('beforeinstallprompt', function(e){
  e.preventDefault(); window._pwaPrompt = e;
  var btn = document.getElementById('pwaInstallBtn'); if (btn) btn.style.display = 'flex';
});
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function(){ navigator.serviceWorker.register('/sw.js').catch(function(){}); });
}
</script>
</head>
<body<?= $_modImg ? ' data-mod-img="'.h($_modImg).'"' : '' ?>>
<?= icon_sprite() ?>
<a href="#main" class="skip-link">Skip to content</a>

<!-- ════ TOP APP BAR ════ -->
<header class="appbar navbar" role="banner">
<div class="bar-in">
  <?php if (!$isHome): ?>
    <a class="bar-btn" href="<?= url('dashboard.php') ?>" id="barBack" aria-label="Back"><?= ic('back') ?></a>
    <div class="bar-title"><?= h($_barTitle ?: $_club) ?></div>
  <?php else: ?>
    <a href="<?= url('dashboard.php') ?>" class="bar-brand" aria-label="<?= h($_club) ?> — home">
      <?php if($logoB64): ?><img src="<?= $logoB64 ?>" class="bar-logo" alt="" width="36" height="36"><?php endif; ?>
      <span style="min-width:0"><span class="bar-name"><?= h($_club) ?></span><br><span class="bar-sub"><?= h($_place) ?> · Kerala</span></span>
    </a>
  <?php endif; ?>

  <nav class="bar-links" aria-label="Main">
    <?php foreach (array(array('dashboard.php','Home','home'),array('modules/feed.php','Feed','bolt'),array('modules/events.php','Events','calendar'),array('modules/members.php','Members','users'),array('modules/market.php','Market','store')) as $l): $on = ($curPage === basename($l[0])); ?>
      <a href="<?= url($l[0]) ?>" class="<?= $on?'on':'' ?>"<?= $on?' aria-current="page"':'' ?>><?= ic($l[2]) ?><?= $l[1] ?></a>
    <?php endforeach; ?>
  </nav>

  <?php if($isAdmin): ?>
    <a class="bar-btn" href="<?= url('admin.php') ?>" aria-label="Admin panel<?= $pendingBadge ? ', '.$pendingBadge.' waiting for approval' : '' ?>">
      <?= ic('shield') ?><?php if($pendingBadge): ?><span class="dot-badge" aria-hidden="true"><?= $pendingBadge ?></span><?php endif; ?>
    </a>
  <?php endif; ?>

  <?php if($user): ?>
  <div class="nav-dd">
    <button type="button" class="bar-btn" aria-label="Account menu" aria-haspopup="true" aria-expanded="false" aria-controls="ddUser" onclick="toggleDrop('ddUser')">
      <?php if($userPhotoB64): ?><img src="<?= $userPhotoB64 ?>" class="bar-avatar" alt="" width="34" height="34"><?php else: ?><span class="bar-avatar-ph"><?= ic('user','ic-sm') ?></span><?php endif; ?>
    </button>
    <div class="nav-drop" id="ddUser">
      <div class="who"><b><?= h($user['name']) ?></b><span><?= h(roleLabel($user['role'])) ?></span></div>
      <div class="nav-drop-sep"></div>
      <a href="<?= url('modules/profile.php') ?>"><?= ic('user') ?> My Profile</a>
      <a href="<?= url('modules/idcard.php') ?>"><?= ic('idcard') ?> My ID Card</a>
      <a href="<?= url('index.php') ?>"><?= ic('globe') ?> Public website</a>
      <div class="nav-drop-sep"></div>
      <a href="<?= url('logout.php') ?>" style="color:var(--danger)"><?= ic('logout') ?> Log out</a>
    </div>
  </div>
  <?php endif; ?>

  <button type="button" class="bar-btn" id="hbBtn" onclick="openDrawer()" aria-label="Open menu" aria-expanded="false" aria-controls="mobDr"><?= ic('menu') ?></button>
</div>
</header>

<!-- ════ SIDE DRAWER ════ -->
<div class="mob-ov" id="mobOv" onclick="closeDrawer()"></div>
<aside class="drawer mob-dr" id="mobDr" role="dialog" aria-modal="true" aria-label="Menu" aria-hidden="true">
  <div class="dr-head">
    <span style="font-weight:800;font-size:1rem">Menu</span>
    <button type="button" class="bar-btn mob-cls" onclick="closeDrawer()" aria-label="Close menu"><?= ic('x') ?></button>
  </div>
  <?php if($user): ?>
  <a href="<?= url('modules/profile.php') ?>" class="dr-user">
    <?php if($userPhotoB64): ?><img src="<?= $userPhotoB64 ?>" alt=""><?php else: ?><span class="ph"><?= ic('user') ?></span><?php endif; ?>
    <span><b><?= h($user['name']) ?></b><span><?= h(roleLabel($user['role'])) ?></span></span>
  </a>
  <?php endif; ?>
  <?php
  $_groups = array();
  $_groups['Home'] = array(array('dashboard.php','Home','home','teal','Home','home'));
  foreach (app_modules() as $m) { $_groups[$m[4]][] = $m; }
  if ($isAdmin) { $_groups['Admin'] = admin_modules(); }
  $_groups['Home'][] = array('index.php','Website','globe','slate','Home','website');
  foreach ($_groups as $sec => $items):
  ?>
  <div class="dr-sec"><?= h($sec) ?></div>
  <div class="dr-grid">
    <?php foreach ($items as $m): $on = ($curPage === basename($m[0])); ?>
    <a href="<?= url($m[0]) ?>" class="dr-a<?= $on?' on':'' ?>"<?= $on?' aria-current="page"':'' ?>>
      <span class="appic" style="width:60px;height:60px;border-radius:19px"><?= app_img($m[5],46) ?></span>
      <?= h($m[1]) ?><?php if($m[0]==='admin.php' && $pendingBadge): ?> <span class="sr-only">(<?= $pendingBadge ?> waiting)</span><?php endif; ?>
    </a>
    <?php endforeach; ?>
  </div>
  <?php endforeach; ?>
  <a href="<?= url('logout.php') ?>" class="dr-logout"><?= ic('logout') ?> Log out</a>
</aside>

<main class="page-wrap" id="main" tabindex="-1">

<script>
// ── Back button: go back inside the app when we came from it ──
(function(){
  var b = document.getElementById('barBack'); if (!b) return;
  b.addEventListener('click', function(e){
    try { if (document.referrer && new URL(document.referrer).origin === location.origin && history.length > 1) { e.preventDefault(); history.back(); } } catch(err){}
  });
})();
// ── Popover menus ──
var _dropIds = ['ddUser'];
function _setDrop(d, open) {
  var el = document.getElementById(d); if (!el) return;
  el.classList.toggle('open', open);
  var b = document.querySelector('[aria-controls="'+d+'"]'); if (b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
}
function closeDrops(){ _dropIds.forEach(function(d){ _setDrop(d,false); }); }
function toggleDrop(id){ var el=document.getElementById(id); if(!el) return; var o=!el.classList.contains('open'); closeDrops(); _setDrop(id,o); }
document.addEventListener('click', function(e){ if (!e.target.closest('.nav-dd')) closeDrops(); });
// ── Drawer ──
function openDrawer(){
  var dr=document.getElementById('mobDr'), hb=document.getElementById('hbBtn');
  document.getElementById('mobOv').classList.add('show');
  dr.classList.add('open'); dr.setAttribute('aria-hidden','false'); hb.setAttribute('aria-expanded','true');
  document.body.style.overflow='hidden';
  setTimeout(function(){ var c=dr.querySelector('.mob-cls'); if(c) c.focus(); }, 60);
}
function closeDrawer(){
  var dr=document.getElementById('mobDr'), hb=document.getElementById('hbBtn');
  if (!dr.classList.contains('open')) return;
  document.getElementById('mobOv').classList.remove('show');
  dr.classList.remove('open'); dr.setAttribute('aria-hidden','true'); hb.setAttribute('aria-expanded','false');
  document.body.style.overflow=''; hb.focus();
}
// swipe left to close the drawer
(function(){ var dr=document.getElementById('mobDr'), x0=null;
  dr.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;},{passive:true});
  dr.addEventListener('touchend',function(e){ if(x0!==null && x0-e.changedTouches[0].clientX>60) closeDrawer(); x0=null; },{passive:true});
})();
// ── Popups ──
function openPopup(id){ var p=document.getElementById(id); if(!p) return; p.classList.add('show'); document.body.style.overflow='hidden'; }
function closePopup(id){ var p=document.getElementById(id); if(!p) return; p.classList.remove('show'); document.body.style.overflow=''; }
document.addEventListener('keydown', function(e){
  if (e.key === 'Escape') {
    document.querySelectorAll('.popup-ov.show').forEach(function(p){ p.classList.remove('show'); });
    closeDrops(); closeDrawer(); document.body.style.overflow='';
  }
});
// ── AJAX helper ──
function ajaxPost(url, data, cb){
  var fd=new FormData(); fd.append('ajax','1');
  Object.keys(data).forEach(function(k){ fd.append(k, data[k]); });
  fetch(url,{method:'POST',body:fd}).then(function(r){return r.json();}).then(cb)
    .catch(function(){ cb({ok:false,msg:'Network error. Please try again.'}); });
}
</script>
