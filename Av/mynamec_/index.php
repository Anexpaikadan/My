<?php
// ================================================================
// index.php — Public Homepage  |  PHP 7.3 + MySQL 5.7 safe
// ================================================================
require_once __DIR__ . '/includes/config.php';
require_once __DIR__ . '/includes/whatsapp_otp.php';

// ── Create tables safely (try/catch each ALTER separately) ──────
try { db()->exec("CREATE TABLE IF NOT EXISTS gallery_images(id INT AUTO_INCREMENT PRIMARY KEY,title VARCHAR(200),image_path VARCHAR(500) NOT NULL,category VARCHAR(80) DEFAULT 'general',is_active TINYINT(1) DEFAULT 1,is_hero TINYINT(1) DEFAULT 0,sort_order INT DEFAULT 0,uploaded_by INT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE gallery_images ADD COLUMN is_hero TINYINT(1) DEFAULT 0"); } catch(Exception $e){}
try { db()->exec("CREATE TABLE IF NOT EXISTS contact_messages(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(150) NOT NULL,email VARCHAR(200),phone VARCHAR(20),subject VARCHAR(200),message TEXT NOT NULL,is_read TINYINT(1) DEFAULT 0,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE events ADD COLUMN thumbnail VARCHAR(500) DEFAULT NULL"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE users ADD COLUMN passkey VARCHAR(255) DEFAULT NULL"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE users ADD COLUMN passkey_set TINYINT(1) DEFAULT 0"); } catch(Exception $e){}

// ── AJAX ────────────────────────────────────────────────────────
if (!empty($_POST['ajax'])) {
    header('Content-Type: application/json');
    $act = trim($_POST['action'] ?? '');

    // ── PASSKEY LOGIN ──────────────────────────────────────────────
    if ($act === 'login_passkey') {
        $raw = $_POST['phone'] ?? '';
        $ph  = normalisePhone($raw);
        $key = trim($_POST['passkey'] ?? '');
        if (strlen($key) !== 6 || !ctype_digit($key)) { echo json_encode(array('ok'=>false,'msg'=>'Passkey must be 6 digits.')); exit; }
        // Match by normalised phone OR raw digits
        $stmt = db()->prepare('SELECT * FROM users WHERE whatsapp_number=?');
        $stmt->execute(array($ph)); $row = $stmt->fetch();
        if (!$row) {
            $digits = preg_replace('/[^0-9]/','',$raw);
            $all = db()->query("SELECT * FROM users")->fetchAll();
            foreach ($all as $u) {
                if (preg_replace('/[^0-9]/','',$u['whatsapp_number']) === $digits) { $row = $u; break; }
            }
        }
        if (!$row) { echo json_encode(array('ok'=>false,'msg'=>'Phone number not registered.')); exit; }
        if ($row['status']==='pending')  { echo json_encode(array('ok'=>false,'msg'=>'Account pending approval.')); exit; }
        if ($row['status']==='rejected') { echo json_encode(array('ok'=>false,'msg'=>'Account rejected.')); exit; }
        if (empty($row['passkey'])) {
            echo json_encode(array('ok'=>false,'no_passkey'=>true,'msg'=>'No passkey set. Please create one.'));
            exit;
        }
        if (!password_verify($key, $row['passkey'])) {
            echo json_encode(array('ok'=>false,'msg'=>'Incorrect passkey. Try again.'));
            exit;
        }
        $_SESSION['user_id'] = $row['id'];
        echo json_encode(array('ok'=>true,'url'=>url('dashboard.php')));
        exit;
    }

    // ── CREATE / RESET PASSKEY ─────────────────────────────────────
    if ($act === 'set_passkey') {
        $ph    = normalisePhone($_POST['phone'] ?? '');
        $key   = trim($_POST['passkey'] ?? '');
        $name  = strtolower(trim($_POST['member_name'] ?? ''));
        if (strlen($ph) < 12) { echo json_encode(array('ok'=>false,'msg'=>'Enter your phone number.')); exit; }
        if (strlen($key) !== 6 || !ctype_digit($key)) { echo json_encode(array('ok'=>false,'msg'=>'Passkey must be exactly 6 digits.')); exit; }
        $row = db()->prepare('SELECT * FROM users WHERE whatsapp_number=?');
        $row->execute(array($ph)); $row = $row->fetch();
        if (!$row) { echo json_encode(array('ok'=>false,'msg'=>'Phone number not registered.')); exit; }
        if ($row['status']==='pending')  { echo json_encode(array('ok'=>false,'msg'=>'Account pending approval.')); exit; }
        // Verify name for security
        if (strtolower(trim($row['name'])) !== $name) {
            echo json_encode(array('ok'=>false,'msg'=>'Name does not match our records.'));
            exit;
        }
        $hash = password_hash($key, PASSWORD_DEFAULT);
        db()->prepare('UPDATE users SET passkey=?,passkey_set=1 WHERE id=?')->execute(array($hash,$row['id']));
        // Auto-login after setting passkey
        $_SESSION['user_id'] = $row['id'];
        echo json_encode(array('ok'=>true,'url'=>url('dashboard.php'),'msg'=>'Passkey set! Logging you in…'));
        exit;
    }

    // ── CHECK PHONE (first step) ───────────────────────────────────
    if ($act === 'check_phone') {
        $raw = $_POST['phone'] ?? '';
        $ph  = normalisePhone($raw);
        $stmt = db()->prepare('SELECT id,name,status,passkey_set FROM users WHERE whatsapp_number=?');
        $stmt->execute(array($ph)); $row = $stmt->fetch();
        if (!$row) {
            $digits = preg_replace('/\D/','',$raw);
            $all = db()->query("SELECT id,name,status,passkey_set,whatsapp_number FROM users")->fetchAll();
            foreach ($all as $u) {
                if (preg_replace('/\D/','',$u['whatsapp_number']) === $digits) { $row = $u; break; }
            }
        }
        if (!$row) { echo json_encode(array('ok'=>false,'msg'=>'Not registered. Apply to join first.')); exit; }
        if ($row['status']==='pending')  { echo json_encode(array('ok'=>false,'msg'=>'Account pending admin approval.')); exit; }
        if ($row['status']==='rejected') { echo json_encode(array('ok'=>false,'msg'=>'Account rejected. Contact Secretary.')); exit; }
        echo json_encode(array(
            'ok'          => true,
            'has_passkey' => !empty($row['passkey_set']),
            'name_hint'   => mb_strtoupper(mb_substr($row['name'],0,1)).'***',
        ));
        exit;
    }

    if ($act === 'register') {
        $name       = trim($_POST['name']       ?? '');
        $ph         = normalisePhone($_POST['phone'] ?? '');
        $blood      = trim($_POST['blood']      ?? '');
        $skill      = trim($_POST['skill']      ?? '');
        $profession = trim($_POST['profession'] ?? '');
        if (!$name || strlen($ph)<12) { echo json_encode(array('ok'=>false,'msg'=>'Name and WhatsApp number are required.')); exit; }
        $ex = db()->prepare('SELECT id FROM users WHERE whatsapp_number=?');
        $ex->execute(array($ph));
        if ($ex->fetch()) { echo json_encode(array('ok'=>false,'msg'=>'Already registered. Use Login tab.')); exit; }
        db()->prepare('INSERT INTO users(name,whatsapp_number,blood_group,skill,profession,status)VALUES(?,?,?,?,?,?)')->execute(array($name,$ph,$blood,$skill,$profession,'pending'));
        echo json_encode(array('ok'=>true));
        exit;
    }

    if ($act === 'contact') {
        $n = trim($_POST['name']    ?? '');
        $e = trim($_POST['email']   ?? '');
        $s = trim($_POST['subject'] ?? '');
        $m = trim($_POST['message'] ?? '');
        if (!$n||!$m) { echo json_encode(array('ok'=>false,'msg'=>'Name and message are required.')); exit; }
        db()->prepare('INSERT INTO contact_messages(name,email,subject,message)VALUES(?,?,?,?)')->execute(array($n,$e,$s,$m));
        echo json_encode(array('ok'=>true,'msg'=>'Message sent! We will get back to you soon.'));
        exit;
    }
    echo json_encode(array('ok'=>false,'msg'=>'Unknown action'));
    exit;
}

// ── Fetch page data ──────────────────────────────────────────────
$stats   = array('total'=>0,'active'=>0,'donors'=>0);
$events  = array();
$gallery = array();

try { $stats = db()->query("SELECT COUNT(*) total,SUM(status='active') active,SUM(blood_group IS NOT NULL AND status='active') donors FROM users")->fetch(); } catch(Exception $e){}
try { $events = db()->query("SELECT * FROM events ORDER BY event_date DESC LIMIT 8")->fetchAll(); } catch(Exception $e){}
try { $gallery = db()->query("SELECT * FROM gallery_images WHERE is_active=1 ORDER BY sort_order,created_at DESC LIMIT 16")->fetchAll(); } catch(Exception $e){ $gallery = []; }

// ── Committee leaders (president, vp, secretary, treasurer)
$committee = [];
try {
    $cstmt = db()->prepare("SELECT id,name,role,committee_position,committee_name,profile_photo
        FROM users WHERE status='active'
        AND role IN ('president','vice_president','secretary','joint_secretary','treasurer','committee_member')
        ORDER BY CASE role
            WHEN 'president' THEN 1 WHEN 'vice_president' THEN 2
            WHEN 'secretary' THEN 3 WHEN 'joint_secretary' THEN 4
            WHEN 'treasurer' THEN 5 ELSE 6 END, name ASC LIMIT 20");
    $cstmt->execute(); $committee = $cstmt->fetchAll();
} catch(Exception $e){ $committee = []; }

// ── Notice board for homepage
$homeNotices = [];
try {
    $homeNotices = db()->query("SELECT * FROM announcements
        WHERE (expires_at IS NULL OR expires_at >= CURDATE())
        ORDER BY is_pinned DESC, created_at DESC LIMIT 8")->fetchAll();
} catch(Exception $e){ $homeNotices = []; }

// Recent public achievements (shows on homepage)
$pubAch = [];
try {
    $paStmt = db()->prepare("SELECT a.*,u.profile_photo uphoto FROM achievements a
        LEFT JOIN users u ON u.id=a.member_id
        WHERE a.status='active' ORDER BY a.achievement_date DESC, a.created_at DESC LIMIT 8");
    $paStmt->execute(); $pubAch = $paStmt->fetchAll();
} catch(Exception $e){ $pubAch = []; }

// ── Hero slides: real photos first, then fallback gradients ──────
$heroSlides = array();
try {
    $hp = db()->query("SELECT * FROM gallery_images WHERE is_active=1 AND is_hero=1 ORDER BY sort_order,created_at DESC LIMIT 6")->fetchAll();
    foreach ($hp as $row) {
        // Use club name if title is empty or looks like a filename
        $slideTitle = $row['title'] ?? '';
        if (empty($slideTitle) || preg_match('/\.(jpg|jpeg|png|webp|gif)/i', $slideTitle) || preg_match('/^gal_/', $slideTitle)) {
            $slideTitle = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
        }
        $heroSlides[] = array(
            'title'    => $slideTitle,
            'subtitle' => setting('CLUB_TAGLINE','Unity · Sports · Culture · Community'),
            'img'      => url('assets/uploads/'.$row['image_path']),
            'grad'     => ''
        );
    }
} catch(Exception $e){}

if (empty($heroSlides)) {
    $heroSlides = array(
        array('title'=>setting('CLUB_NAME','Aishwarya Arts & Sports Club'),             'subtitle'=>setting('CLUB_TAGLINE','Unity · Sports · Culture · Community'),                               'img'=>'','grad'=>'135deg,#07225c,#1a3a6b,#0d47a1'),
        array('title'=>'Football Tournament', 'subtitle'=>'Competing with passion, winning with pride','img'=>'','grad'=>'135deg,#0a1f0a,#1b5e20,#2e7d32'),
        array('title'=>'Onam Celebrations',   'subtitle'=>'Preserving the rich heritage of Kerala',   'img'=>'','grad'=>'135deg,#2c1400,#6d2d00,#bf360c'),
        array('title'=>'Arts & Culture',      'subtitle'=>'Celebrating talent from our community',    'img'=>'','grad'=>'135deg,#1a0533,#4a148c,#7b1fa2'),
    );
}

// ── Gallery items ───────────────────────────────────────────────
$galItems = array();
foreach ($gallery as $g) {
    $galItems[] = array('type'=>'img','src'=>url('assets/uploads/'.$g['image_path']),'title'=>$g['title'] ?? '');
}
$placeholders = array(
    array('⚽','Football'),array('🌸','Onam'),array('🏏','Cricket'),
    array('💃','Thiruvathira'),array('🤼','Kabaddi'),array('🎭','Drama'),
    array('🏆','Trophy'),array('🎵','Music'),array('🎨','Arts'),array('🚣','Vallamkali')
);
while (count($galItems) < 10) {
    $p = $placeholders[count($galItems) % count($placeholders)];
    $galItems[] = array('type'=>'emoji','em'=>$p[0],'title'=>$p[1]);
}

// ── Active modules ───────────────────────────────────────────────
$activeModules = array();
try {
    $ft = db()->query("SELECT * FROM tournaments WHERE sport='football' AND status IN('upcoming','ongoing') ORDER BY created_at DESC LIMIT 1")->fetch();
    if ($ft) {
        $fts = db()->prepare("SELECT *,(wins*3+draws) pts FROM tournament_teams WHERE tournament_id=? ORDER BY (wins*3+draws) DESC,(goals_for-goals_against) DESC LIMIT 6");
        $fts->execute(array($ft['id'])); $ftTeams = $fts->fetchAll();
        $activeModules[] = array('type'=>'football','data'=>$ft,'teams'=>$ftTeams);
    }
} catch(Exception $e){}
try {
    $onam = db()->query("SELECT * FROM onam_events WHERE status IN('upcoming','active') ORDER BY event_date DESC LIMIT 1")->fetch();
    if ($onam) {
        $op = db()->prepare("SELECT * FROM onam_programs WHERE onam_id=? ORDER BY created_at LIMIT 8");
        $op->execute(array($onam['id'])); $onamProgs = $op->fetchAll();
        $activeModules[] = array('type'=>'onam','data'=>$onam,'programs'=>$onamProgs);
    }
} catch(Exception $e){}
try {
    $arts = db()->query("SELECT * FROM arts_festivals WHERE status IN('upcoming','active') ORDER BY event_date DESC LIMIT 1")->fetch();
    if ($arts) {
        $ap = db()->prepare("SELECT * FROM arts_programs WHERE festival_id=? ORDER BY created_at LIMIT 8");
        $ap->execute(array($arts['id'])); $artsProgs = $ap->fetchAll();
        $activeModules[] = array('type'=>'arts','data'=>$arts,'programs'=>$artsProgs);
    }
} catch(Exception $e){}
try {
    $cfCamps = db()->query("SELECT * FROM cf_campaigns WHERE status='active' ORDER BY is_featured DESC,created_at DESC LIMIT 3")->fetchAll();
    if (!empty($cfCamps)) {
        $activeModules[] = array('type'=>'crowdfund','campaigns'=>$cfCamps);
    }
} catch(Exception $e){}

$logo = getLogoB64();
$wa   = preg_replace('/\D/', '', setting('CLUB_PHONE','+919876543210'));
require_once __DIR__.'/includes/icons.php';
// ── Homepage settings (Club Settings → Homepage) ─────────────────
$HS = array();
try { foreach (db()->query("SELECT setting_key,setting_value FROM club_settings")->fetchAll() as $r) $HS[$r['setting_key']] = $r['setting_value']; } catch(Exception $e){}
$hs  = function($k, $d = '') use ($HS) { return (isset($HS[$k]) && $HS[$k] !== '') ? $HS[$k] : $d; };
$hon = function($k) use ($HS) { return !isset($HS[$k]) || $HS[$k] !== '0'; };   // sections are on unless switched off
$hexOk = function($c, $d) { return preg_match('/^#[0-9a-fA-F]{6}$/', (string)$c) ? $c : $d; };
$homePrimary = $hexOk($hs('home_primary_color'), '#0A14E0');
$homeAccent  = $hexOk($hs('home_accent_color'),  '#E30613');
$homeFonts   = array('Plus Jakarta Sans','Poppins','Manrope','Outfit');
$homeFont    = in_array($hs('home_font'), $homeFonts, true) ? $hs('home_font') : 'Plus Jakarta Sans';
$clubName    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$clubPlace   = setting('CLUB_PLACE','Vettikkattiri');
$clubTag     = setting('CLUB_TAGLINE','Unity · Sports · Culture · Community');
$heroTitle   = $hs('hero_title', $clubName);
$heroSub     = $hs('hero_subtitle', $clubTag);
$heroBadge   = $hs('hero_badge', $clubPlace . ' · Kerala');
$clubActs = array();
try { $clubActs = db()->query("SELECT * FROM club_activities WHERE is_active=1 ORDER BY sort_order,id")->fetchAll(); } catch(Exception $e){}
$upEvents = array_values(array_filter(isset($events) ? $events : array(), function($e){ return strtotime($e['event_date']) >= strtotime('today'); }));
usort($upEvents, function($a,$b){ return strcmp($a['event_date'],$b['event_date']); });
$_pLoggedIn = !empty($_SESSION['user_id']);
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<?php $pageTitle = isset($pageTitle) ? $pageTitle : $clubName.' · '.$clubPlace; ?>
<title><?= h($pageTitle) ?></title>
<meta name="description" content="<?= h($clubName.', '.$clubPlace.', Kerala — '.$clubTag.'. Events, gallery and member portal.') ?>">
<meta property="og:title" content="<?= h($clubName) ?>">
<meta property="og:description" content="<?= h($heroSub) ?>">
<?php if(defined('LOGO_URL')): ?><meta property="og:image" content="<?= h(LOGO_URL) ?>"><link rel="icon" href="<?= h(LOGO_URL) ?>"><?php endif; ?>
<link rel="manifest" href="/manifest.php">
<meta name="theme-color" content="#0A14E0">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aishwarya">
<link rel="apple-touch-icon" href="/assets/logo.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=<?= urlencode($homeFont) ?>:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
:root{
  --ink:#0B1033; --ink-2:#121A5C;
  --p:<?= $homePrimary ?>; --p2:color-mix(in srgb,var(--p) 80%,#000); --p-soft:color-mix(in srgb,var(--p) 10%,#fff);
  --a:<?= $homeAccent ?>; --a-light:color-mix(in srgb,var(--a) 45%,#fff);
  --a-tx:color-mix(in srgb,var(--a) 62%,#000);
  --surface:#F5F7FF; --line:#E3E7F5; --tx:#0B1033; --t2:#3B4266; --t3:#565D82;
  --glass:rgba(255,255,255,.08); --glass-line:rgba(255,255,255,.14);
  --rad:20px; --rad-s:14px; --sh:0 1px 2px rgba(11,16,51,.05),0 6px 20px rgba(11,16,51,.07); --sh2:0 18px 50px rgba(11,16,51,.2);
  --tr:.25s cubic-bezier(.2,.8,.2,1);
  --brand:linear-gradient(105deg,var(--a) 0%,color-mix(in srgb,var(--a) 50%,var(--p)) 50%,var(--p) 100%);
  --font:'<?= h($homeFont) ?>',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{font-family:var(--font);color:var(--tx);background:var(--surface);line-height:1.6;overflow-x:hidden;-webkit-tap-highlight-color:transparent}
a{text-decoration:none;color:inherit}
img{display:block;max-width:100%}
button,input,select,textarea{font-family:inherit}
.ic{width:22px;height:22px;flex-shrink:0;display:inline-block;vertical-align:middle}.ic-sm{width:18px;height:18px}.ic-lg{width:28px;height:28px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.skip-link{position:absolute;left:.75rem;top:-100px;z-index:20000;background:#fff;color:var(--ink);font-weight:700;padding:.7rem 1rem;border-radius:12px}
.skip-link:focus{top:.75rem}
:focus{outline:none}
:focus-visible{outline:3px solid var(--p);outline-offset:2px;border-radius:8px}
.dark :focus-visible,#mainNav :focus-visible,#footer :focus-visible,.lb-ov :focus-visible,#pub-bnav :focus-visible{outline-color:#FFB3B0}
.wrap{max-width:1160px;margin:0 auto;padding:0 1rem}

/* ═══ Top bar ═══ */
.navbar{position:fixed;top:0;left:0;right:0;z-index:1000;padding-top:env(safe-area-inset-top,0px);color:#fff;transition:background var(--tr),border-color var(--tr)}
.navbar.scrolled,.navbar.solid{background:var(--brand);box-shadow:0 6px 20px -10px rgba(10,20,224,.6)}
.nav-inner{max-width:1160px;margin:0 auto;height:64px;padding:0 .75rem;display:flex;align-items:center;gap:.4rem}
.nav-brand{display:flex;align-items:center;gap:.6rem;margin-right:auto;min-width:0}
.nav-logo{width:42px;height:42px;border-radius:50%;object-fit:cover;background:#fff;box-shadow:0 0 0 2px rgba(255,255,255,.85)}
.nav-club-name{font-weight:800;font-size:1rem;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nav-club-sub{font-size:.72rem;color:rgba(255,255,255,.75)}
.nav-links{display:none;list-style:none;gap:.15rem}
.nav-links a{display:block;font-size:.88rem;font-weight:600;color:rgba(255,255,255,.82);padding:.5rem .85rem;border-radius:12px}
.nav-links a:hover,.nav-links a.on{color:#fff;background:rgba(255,255,255,.1)}
@media(min-width:900px){.nav-links{display:flex}.hb{display:none!important}}
.btn-login{display:inline-flex;align-items:center;gap:.45rem;min-height:42px;padding:0 1.1rem;border-radius:14px;border:0;cursor:pointer;font-weight:800;font-size:.88rem;color:#fff;background:var(--brand);box-shadow:0 8px 20px -10px var(--p),inset 0 0 0 1.5px rgba(255,255,255,.55)}
.btn-login:active{transform:scale(.97)}
.hb{width:44px;height:44px;border-radius:14px;border:0;background:transparent;color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer}
.hb .x{display:none}.hb.open .m{display:none}.hb.open .x{display:inline-block}
.mob-menu{display:none;position:absolute;top:calc(100% + .4rem);left:.6rem;right:.6rem;background:rgba(11,16,51,.96);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1px solid var(--glass-line);border-radius:22px;padding:.5rem;box-shadow:var(--sh2)}
.mob-menu.open{display:block;animation:pop .18s ease-out}
.mob-menu a{display:flex;align-items:center;gap:.75rem;min-height:50px;padding:0 .8rem;border-radius:14px;font-weight:600;color:#fff}
.mob-menu a:hover{background:var(--glass)}
.mob-menu .btn-login{width:100%;justify-content:center;margin-top:.4rem;min-height:50px}
@keyframes pop{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}

/* ═══ Hero ═══ */
#hero{position:relative;min-height:min(100svh,820px);display:flex;align-items:flex-end;color:#fff;overflow:hidden;background:var(--ink)}
.hslide{position:absolute;inset:0;opacity:0;visibility:hidden;transition:opacity 1.1s ease,visibility 1.1s}
.hslide.on{opacity:1;visibility:visible}
.hslide-bg{position:absolute;inset:0;background-size:cover;background-position:center;transform:scale(1.04);transition:transform 7s ease}
.hslide.on .hslide-bg{transform:scale(1)}
.hero-shade{position:absolute;inset:0;z-index:2;background:radial-gradient(80% 60% at 0% 0%,color-mix(in srgb,var(--p) 55%,transparent),transparent 60%),radial-gradient(60% 50% at 100% 30%,color-mix(in srgb,var(--a) 35%,transparent),transparent 60%),linear-gradient(180deg,rgba(11,16,51,.35) 0%,rgba(11,16,51,.55) 45%,rgba(11,16,51,.96) 100%)}
.hcontent{position:relative;z-index:3;width:100%;max-width:1160px;margin:0 auto;padding:110px 1.1rem 3.2rem}
.hbadge{display:inline-flex;align-items:center;gap:.4rem;font-size:.76rem;font-weight:700;letter-spacing:.06em;color:#fff;background:var(--glass);border:1px solid var(--glass-line);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);padding:.35rem .85rem;border-radius:999px;margin-bottom:1rem}
.hbadge i{width:8px;height:8px;border-radius:50%;background:var(--a);box-shadow:0 0 0 4px color-mix(in srgb,var(--a) 30%,transparent)}
.htitle{font-weight:800;font-size:clamp(2.2rem,7vw,4.4rem);line-height:1.04;letter-spacing:-.035em;max-width:14ch;margin-bottom:.9rem}
.hsub{font-size:clamp(1rem,2.4vw,1.2rem);color:rgba(255,255,255,.86);max-width:560px;margin-bottom:1.6rem}
.hcta{display:flex;gap:.7rem;flex-wrap:wrap}
.btn-hero-p,.btn-hero-s{display:inline-flex;align-items:center;gap:.5rem;min-height:52px;padding:0 1.4rem;border-radius:16px;font-weight:800;font-size:.95rem;cursor:pointer;border:0;transition:transform .12s}
.btn-hero-p{color:#fff;background:var(--brand);box-shadow:0 14px 30px -12px var(--p),inset 0 0 0 1.5px rgba(255,255,255,.5)}
.btn-hero-s{color:#fff;background:var(--glass);border:1px solid var(--glass-line);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
.btn-hero-p:active,.btn-hero-s:active{transform:scale(.97)}
.hdots{position:absolute;right:1.1rem;bottom:1.4rem;z-index:4;display:flex;gap:.4rem}
.hdot{width:9px;height:9px;border-radius:9px;border:0;background:rgba(255,255,255,.45);cursor:pointer;transition:width .3s,background .3s;position:relative;padding:0}
.hdot::after{content:'';position:absolute;inset:-14px -6px}
.hdot.on{width:26px;background:#fff}

/* ═══ Stats ═══ */
.stats-bar{position:relative;z-index:5;max-width:1160px;margin:-1.6rem auto 0;padding:0 1rem;display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem}
.stat-card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:.9rem .4rem;text-align:center;box-shadow:var(--sh)}
.stat-num{display:block;font-weight:800;font-size:1.6rem;letter-spacing:-.03em;line-height:1.1;color:var(--p2)}
.stat-lbl{font-size:.7rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em}
@media(max-width:420px){.stat-num{font-size:1.3rem}.stat-lbl{font-size:.62rem}}

/* ═══ Sections ═══ */
.sec{padding:3.6rem 0}
.sec.dark{background:radial-gradient(70% 60% at 0% 0%,color-mix(in srgb,var(--p) 35%,transparent),transparent 60%),radial-gradient(60% 60% at 100% 100%,color-mix(in srgb,var(--a) 22%,transparent),transparent 60%),var(--ink);color:#fff}
.sec.white{background:#fff}
.eyebrow{display:inline-block;padding-left:.9rem;position:relative;font-size:.74rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--a-tx);margin-bottom:.5rem}
.eyebrow::before{content:'';position:absolute;left:0;top:.2em;bottom:.2em;width:4px;border-radius:4px;background:var(--brand)}
.dark .eyebrow{color:#FFB3B0}
.sec-title{font-weight:800;font-size:clamp(1.6rem,4vw,2.4rem);letter-spacing:-.03em;line-height:1.12;margin-bottom:.6rem}
.sec-sub{font-size:1rem;color:var(--t2);max-width:620px}
.dark .sec-sub{color:rgba(255,255,255,.8)}
.sec-head{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:1rem;margin-bottom:1.6rem}
.link-more{display:inline-flex;align-items:center;gap:.3rem;font-weight:700;font-size:.9rem;color:var(--p2);min-height:44px}
.dark .link-more{color:#A9B0FF}
.cgrid{display:grid;gap:1rem}
.g-2{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.g-3{grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.g-p{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--rad);box-shadow:var(--sh);overflow:hidden}
.gcard{background:var(--glass);border:1px solid var(--glass-line);border-radius:var(--rad);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
/* about */
.about{display:grid;gap:1.6rem;align-items:center}
@media(min-width:860px){.about{grid-template-columns:1.1fr 1fr}}
.about p{white-space:pre-line;color:var(--t2);font-size:1.02rem}
.pillars{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}
.pillar{padding:1rem;border-radius:18px;background:var(--surface);border:1px solid var(--line)}
.pillar .tile{margin-bottom:.6rem}
.pillar b{display:block;font-size:.95rem}
.pillar span{font-size:.82rem;color:var(--t3)}
/* app icons with 3D pictures */
.appic{width:56px;height:56px;border-radius:18px;background:#fff;display:flex;align-items:center;justify-content:center;border:1px solid var(--line);box-shadow:0 8px 18px -10px rgba(10,20,224,.35);margin-bottom:.6rem}
.appic .app-img{width:40px;height:40px;object-fit:contain;filter:drop-shadow(0 3px 3px rgba(11,16,51,.15))}
/* app tiles */
.tile{width:48px;height:48px;border-radius:16px;display:flex;align-items:center;justify-content:center;color:#fff;position:relative;background:linear-gradient(145deg,var(--t1),var(--t2c));box-shadow:0 8px 18px -8px var(--t2c),inset 0 1px 0 rgba(255,255,255,.35)}
.tile .ic{width:24px;height:24px;position:relative;z-index:1}
.tile::after{content:'';position:absolute;inset:0;border-radius:inherit;background:linear-gradient(180deg,rgba(255,255,255,.28),transparent 55%)}
.tone-teal{--t1:#14B8A6;--t2c:#0A14E0}.tone-coral{--t1:#FB8A7B;--t2c:#E1503F}.tone-violet{--t1:#A78BFA;--t2c:#6D28D9}
.tone-amber{--t1:#FBBF24;--t2c:#D97706}.tone-rose{--t1:#FB7185;--t2c:#BE123C}.tone-sky{--t1:#38BDF8;--t2c:#0369A1}.tone-lime{--t1:#84CC16;--t2c:#3F8F0E}
/* activities */
.act{padding:1.2rem;display:flex;flex-direction:column;gap:.55rem;height:100%}
.act-em{width:52px;height:52px;border-radius:17px;display:flex;align-items:center;justify-content:center;font-size:1.6rem;background:color-mix(in srgb,var(--c) 22%,transparent);border:1px solid color-mix(in srgb,var(--c) 45%,transparent)}
.act b{font-size:1.05rem}
.act p{font-size:.88rem;color:rgba(255,255,255,.8);flex:1}
.act-links{display:flex;gap:.5rem;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:.35rem;min-height:40px;padding:0 .9rem;border-radius:12px;font-size:.82rem;font-weight:700}
.chip-a{background:#fff;color:var(--ink)}.chip-g{border:1px solid var(--glass-line);color:#fff}
/* events */
.ev{display:flex;gap:1rem;padding:1rem;align-items:flex-start}
.ev-date{width:62px;flex-shrink:0;text-align:center;border-radius:16px;padding:.5rem 0;background:var(--p-soft);color:var(--p2);font-weight:800;line-height:1}
.ev-date b{display:block;font-size:1.6rem;letter-spacing:-.03em}
.ev-date small{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em}
.ev h3{font-size:1.02rem;font-weight:800;line-height:1.3}
.ev p{font-size:.86rem;color:var(--t2);margin-top:.2rem}
.ev .meta{display:flex;flex-wrap:wrap;gap:.6rem;font-size:.8rem;color:var(--t3);margin-top:.45rem}
.ev .meta span{display:inline-flex;align-items:center;gap:.25rem}
.soon{display:inline-block;font-size:.7rem;font-weight:800;padding:.12rem .5rem;border-radius:999px;background:#FDECE9;color:#9A2D1F;margin-left:.3rem}
/* notices */
.note{padding:1rem 1.1rem;display:flex;gap:.8rem}
.note b{display:block;font-size:.98rem}
.note p{font-size:.88rem;color:rgba(255,255,255,.82);white-space:pre-line;margin-top:.15rem}
.note small{font-size:.76rem;color:rgba(255,255,255,.65)}
.pill{display:inline-block;font-size:.68rem;font-weight:800;padding:.1rem .5rem;border-radius:999px;margin-left:.3rem;background:#FFE4DE;color:#8A2416;vertical-align:middle}
/* people */
.person{text-align:center;padding:1rem .6rem}
.person img,.person .ph{width:78px;height:78px;border-radius:24px;object-fit:cover;margin:0 auto .6rem;background:var(--p-soft);color:var(--p2);display:flex;align-items:center;justify-content:center}
.person b{display:block;font-size:.92rem;line-height:1.25}
.person span{font-size:.78rem;color:var(--t3)}
/* achievements */
.ach-row{display:flex;gap:.8rem;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:.4rem;scrollbar-width:none}
.ach-row::-webkit-scrollbar{display:none}
.ach{flex:0 0 220px;scroll-snap-align:start;cursor:pointer;text-align:left;border:0;padding:0;color:inherit;font:inherit}
.ach .img{height:150px;background:linear-gradient(145deg,#FBBF24,#D97706);display:flex;align-items:center;justify-content:center;font-size:2.6rem}
.ach .img img{width:100%;height:100%;object-fit:cover}
.ach .body{padding:.8rem .9rem}
.ach b{display:block;font-size:.92rem;line-height:1.3}
.ach span{font-size:.78rem;color:rgba(255,255,255,.72)}
/* gallery */
.gal{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem}
@media(min-width:640px){.gal{grid-template-columns:repeat(4,1fr)}}
.gal-cell{aspect-ratio:1;border-radius:18px;overflow:hidden;position:relative;cursor:pointer;background:var(--surface);border:1px solid var(--line)}
.gal-cell img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
.gal-cell:hover img{transform:scale(1.05)}
.gal-cell-ph{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.3rem;font-size:2rem;color:var(--t3)}
.gal-cell-ph span{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
/* join CTA */
.join{border-radius:28px;padding:2rem 1.4rem;color:#fff;text-align:center;position:relative;overflow:hidden;
  background:radial-gradient(80% 100% at 0% 0%,color-mix(in srgb,var(--p) 70%,transparent),transparent 60%),radial-gradient(80% 100% at 100% 100%,color-mix(in srgb,var(--a) 50%,transparent),transparent 60%),var(--ink)}
.join p{color:rgba(255,255,255,.85);max-width:520px;margin:0 auto 1.3rem}
.join .hcta{justify-content:center}
.empty{color:var(--t3);text-align:center;padding:1.4rem;font-size:.95rem}
.dark .empty{color:rgba(255,255,255,.72)}

/* ═══ Footer ═══ */
#footer{background:var(--ink);border-top:4px solid transparent;border-image:var(--brand) 1;color:rgba(255,255,255,.8);padding:2.6rem 0 1.2rem}
.foot{display:grid;gap:1.6rem}
@media(min-width:760px){.foot{grid-template-columns:1.4fr 1fr 1fr 1.2fr}}
.foot h2{font-size:.76rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.65);margin-bottom:.6rem}
.foot a.fl{display:flex;align-items:center;min-height:40px;font-size:.92rem;color:rgba(255,255,255,.88)}
.foot a.fl:hover{color:#fff}
.foot-brand{display:flex;align-items:center;gap:.7rem;margin-bottom:.7rem}
.foot-brand img{width:48px;height:48px;border-radius:50%;object-fit:cover;background:#fff}
.foot-brand b{display:block;color:#fff}
.sicons{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.8rem}
.sicon{width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:1rem}
.foot-btm{border-top:1px solid rgba(255,255,255,.1);margin-top:1.8rem;padding-top:1rem;text-align:center;font-size:.8rem;color:rgba(255,255,255,.72)}
.foot-btm b{color:#fff}

/* ═══ Login modal (logic unchanged) ═══ */
.overlay{display:none;position:fixed;inset:0;z-index:10002;background:rgba(5,14,17,.6);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);align-items:flex-end;justify-content:center}
.overlay.show{display:flex}
.modal{background:#fff;width:100%;max-width:440px;border-radius:26px 26px 0 0;box-shadow:var(--sh2);overflow:hidden;max-height:94vh;display:flex;flex-direction:column;animation:sheetUp .3s cubic-bezier(.2,.8,.2,1) both;padding-bottom:env(safe-area-inset-bottom,0px)}
@media(min-width:600px){.overlay{align-items:center;padding:1rem}.modal{border-radius:26px;animation:pop .2s ease-out both}}
@keyframes sheetUp{from{transform:translateY(100%)}to{transform:none}}
.modal-bar{height:5px;width:44px;border-radius:5px;background:#d5dedc;margin:.6rem auto 0;flex-shrink:0}
.modal-head{display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.3rem .6rem;flex-shrink:0}
.modal-head h3{font-weight:800;font-size:1.25rem;letter-spacing:-.02em;color:var(--tx);margin:0}
.modal-x{background:var(--surface);border:none;width:44px;height:44px;border-radius:14px;cursor:pointer;color:var(--t2);display:flex;align-items:center;justify-content:center}
.modal-tabs{display:flex;gap:.3rem;margin:0 1.3rem;padding:.3rem;background:var(--surface);border-radius:16px;flex-shrink:0}
.mtab{flex:1;min-height:44px;border:0;border-radius:12px;background:none;font-weight:700;font-size:.88rem;color:var(--t3);cursor:pointer}
.mtab.on{background:#fff;color:var(--tx);box-shadow:var(--sh)}
.modal-body{padding:1.2rem 1.3rem 1.4rem;overflow-y:auto}
.mpanel{display:none}.mpanel.on{display:block}
.flbl{font-size:.8rem;font-weight:700;color:var(--t2);display:block;margin-bottom:.4rem}
.finp{width:100%;min-height:50px;background:#fff;border:1.5px solid var(--line);border-radius:14px;padding:.7rem 1rem;font-size:1rem;color:var(--tx);outline:none;margin-bottom:.9rem;transition:border-color .15s,box-shadow .15s}
.finp:focus{border-color:var(--p);box-shadow:0 0 0 4px var(--p-soft)}
.finp::placeholder{color:#6B7194}
.frow{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
.otp-wrap{display:flex;gap:.4rem;justify-content:center;margin:.6rem 0 1.1rem}
.otp-cell{width:46px;height:54px;border:1.5px solid var(--line);border-radius:14px;text-align:center;font-size:1.3rem;font-weight:800;color:var(--tx);outline:none}
.otp-cell:focus{border-color:var(--p);box-shadow:0 0 0 4px var(--p-soft)}
.fbtn{width:100%;min-height:52px;padding:.8rem;border:none;border-radius:16px;font-weight:800;font-size:.98rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.5rem;transition:transform .12s}
.fbtn:active:not(:disabled){transform:scale(.98)}
.fbtn-p{background:var(--ink);color:#fff}
.fbtn-g{background:var(--p);color:#fff}
.fbtn:disabled{opacity:.55;cursor:not-allowed}
.fmsg{border-radius:12px;padding:.75rem 1rem;font-size:.88rem;font-weight:500;margin-bottom:.9rem;display:none;line-height:1.45}
.fmsg.ok{background:#ECFDF3;border:1px solid #BBF7D0;color:#166534;display:block}
.fmsg.err{background:#FEF2F2;border:1px solid #FECACA;color:#991B1B;display:block}
.fhint{font-size:.8rem;color:var(--t3);text-align:center;margin-top:.8rem;line-height:1.5}
.fback{background:none;border:none;color:var(--t2);font-size:.86rem;font-weight:600;cursor:pointer;min-height:40px;margin-bottom:.4rem}
.success-panel{text-align:center;padding:.5rem 0 .8rem}.success-em{font-size:3rem;margin-bottom:.6rem}
.num-keypad{display:grid;grid-template-columns:repeat(3,1fr);gap:.55rem;max-width:300px;margin:0 auto}
.num-keypad button{background:var(--surface);border:1px solid var(--line);border-radius:18px;min-height:58px;font-size:1.35rem;font-weight:700;color:var(--tx);cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1;transition:transform .08s,background .1s}
.num-keypad button:active{background:var(--ink);color:#fff;transform:scale(.95)}
.num-keypad button span{font-size:.55rem;font-weight:700;letter-spacing:.1em;color:var(--t3);margin-top:.15rem}
.num-keypad .pk-del{background:#FDECE9;color:#9A2D1F;border-color:#F8D3CC}
.num-keypad .pk-ok{background:var(--p);color:#fff;border-color:var(--p)}
.pk-dot{width:14px;height:14px;border-radius:50%;background:var(--line);transition:all .15s}
.pk-dot.filled{background:var(--ink);transform:scale(1.15)}
.pk-dot.err{background:#E1503F}
@keyframes pkShake{0%,100%{transform:translateX(0)}25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}

/* ═══ Lightbox ═══ */
.lb-ov{display:none;position:fixed;inset:0;z-index:10002;background:rgba(5,10,12,.96);align-items:center;justify-content:center;flex-direction:column}
.lb-ov.on{display:flex}
.lb-img-wrap{width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:64px 12px 110px}
.lb-img-wrap img{max-width:100%;max-height:100%;object-fit:contain;border-radius:14px}
.lb-close{position:fixed;top:calc(env(safe-area-inset-top,0px) + 1rem);right:1rem;width:46px;height:46px;border-radius:15px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);color:#fff;font-size:1.1rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
.lb-caption{position:fixed;bottom:1.2rem;left:50%;transform:translateX(-50%);color:rgba(255,255,255,.8);font-size:.88rem;max-width:90vw;text-align:center}
.lb-login-hint{position:fixed;bottom:3.4rem;left:50%;transform:translateX(-50%)}
.lb-login-hint button{background:#fff;color:var(--ink);border:none;border-radius:14px;min-height:46px;padding:0 1.2rem;font-weight:800;cursor:pointer;display:inline-flex;align-items:center;gap:.45rem}
.lb-swipe-hint{position:fixed;top:calc(env(safe-area-inset-top,0px) + 1.4rem);left:50%;transform:translateX(-50%);color:rgba(255,255,255,.72);font-size:.75rem}
@media(min-width:600px){.lb-swipe-hint{display:none}}

/* ═══ Install sheet ═══ */
#iosSheet{display:none;position:fixed;inset:0;z-index:10003;background:rgba(5,14,17,.55);align-items:flex-end;justify-content:center}
#iosSheet.open{display:flex}
#iosSheet>div{animation:sheetUp .28s ease both;max-height:92vh;overflow-y:auto}

@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}
}
</style>
<script>
// Modal functions - plain JS, no jQuery dependency
function openModal(tab){
  var ov=document.getElementById('loginOverlay');
  if(!ov)return;
  ov.classList.add('show');
  document.body.style.overflow='hidden';
  // Switch tab
  var isL=(tab||'login')==='login';
  var pl=document.getElementById('pLogin'),pr=document.getElementById('pRegister');
  var tl=document.getElementById('tLogin'),tr=document.getElementById('tRegister');
  var mt=document.getElementById('mTitle');
  if(pl)pl.classList.toggle('on',isL);
  if(pr)pr.classList.toggle('on',!isL);
  if(tl)tl.classList.toggle('on',isL);
  if(tr)tr.classList.toggle('on',!isL);
  if(mt)mt.textContent=isL?'Member Portal':'Apply to Join';
  if(isL)setTimeout(function(){var p=document.getElementById('loginPhone');if(p)p.focus();},300);
}
function closeModal(){
  var ov=document.getElementById('loginOverlay');
  if(!ov)return;
  ov.classList.remove('show');
  document.body.style.overflow='';
}
function toggleMob(){
  var hb=document.getElementById('hb'),m=document.getElementById('mobMenu');
  var open=!m.classList.contains('open');
  hb.classList.toggle('open',open); m.classList.toggle('open',open);
  hb.setAttribute('aria-expanded',open?'true':'false');
  hb.setAttribute('aria-label',open?'Close menu':'Open menu');
}
function closeMob(){
  var hb=document.getElementById('hb');
  hb.classList.remove('open'); document.getElementById('mobMenu').classList.remove('open');
  hb.setAttribute('aria-expanded','false'); hb.setAttribute('aria-label','Open menu');
}
function heroMove(d){
  if(typeof _heroMove==='function')_heroMove(d);
}
function heroGo(i){
  if(typeof _heroGo==='function')_heroGo(i);
}
</script>
</head>
<body>
<?= icon_sprite() ?>
<a href="#main" class="skip-link">Skip to content</a>
<?php include 'av-splash.php'; ?>

<!-- ══════════════════ TOP BAR ══════════════════ -->
<nav class="navbar" id="mainNav" aria-label="Main">
<div class="nav-inner">
  <a href="#hero" class="nav-brand" aria-label="<?= h($clubName) ?> — home">
    <?php if($logo): ?><img src="<?= $logo ?>" class="nav-logo" alt="" width="40" height="40"><?php endif; ?>
    <span style="min-width:0"><span class="nav-club-name"><?= h($clubName) ?></span><br><span class="nav-club-sub"><?= h($clubPlace) ?> · Kerala</span></span>
  </a>
  <ul class="nav-links" id="navLinks">
    <li><a href="#hero" class="on" id="nl-home" aria-current="true">Home</a></li>
    <?php if($hon('home_events_show')): ?><li><a href="#events">Events</a></li><?php endif; ?>
    <?php if($hon('home_gallery_show')): ?><li><a href="#gallery">Gallery</a></li><?php endif; ?>
    <li><a href="<?= url('modules/market.php') ?>">Market</a></li>
    <li><a href="<?= url('contact.php') ?>">Contact</a></li>
  </ul>
  <?php if($_pLoggedIn): ?>
    <a class="btn-login" href="<?= url('dashboard.php') ?>"><?= ic('home','ic-sm') ?> Dashboard</a>
  <?php else: ?>
    <button type="button" class="btn-login" id="openLogin"><?= ic('login','ic-sm') ?> Login</button>
  <?php endif; ?>
  <button type="button" class="hb" id="hb" onclick="toggleMob()" aria-label="Open menu" aria-expanded="false" aria-controls="mobMenu"><span class="m"><?= ic('menu') ?></span><span class="x"><?= ic('x') ?></span></button>
</div>
<div class="mob-menu" id="mobMenu">
  <a href="#hero" onclick="closeMob()"><?= ic('home') ?> Home</a>
  <?php if($hon('home_events_show')): ?><a href="#events" onclick="closeMob()"><?= ic('calendar') ?> Events</a><?php endif; ?>
  <?php if($hon('home_gallery_show')): ?><a href="#gallery" onclick="closeMob()"><?= ic('image') ?> Gallery</a><?php endif; ?>
  <a href="<?= url('modules/market.php') ?>" onclick="closeMob()"><?= ic('store') ?> Mini Market</a>
  <a href="<?= url('contact.php') ?>" onclick="closeMob()"><?= ic('phone') ?> Contact</a>
  <?php if(!$_pLoggedIn): ?><button type="button" class="btn-login" onclick="closeMob();openModal('login')"><?= ic('login','ic-sm') ?> Member login</button><?php endif; ?>
</div>
</nav>

<!-- ══════════════════ LOGIN MODAL ══════════════════ -->
<div class="overlay" id="loginOverlay" onclick="if(event.target===this)closeModal()">
<div class="modal" role="dialog" aria-modal="true" aria-labelledby="mTitle">
  <div class="modal-bar"></div>
  <div class="modal-head">
    <h3 id="mTitle">Member Portal</h3>
    <button type="button" class="modal-x" onclick="closeModal()" aria-label="Close"><i class="fas fa-times" aria-hidden="true"></i></button>
  </div>
  <div class="modal-tabs" role="tablist" aria-label="Login or apply">
    <button type="button" class="mtab on" id="tLogin"    role="tab" aria-selected="true"  aria-controls="pLogin"    onclick="switchTab('login')"><span aria-hidden="true">🔐</span> Login</button>
    <button type="button" class="mtab"    id="tRegister" role="tab" aria-selected="false" aria-controls="pRegister" onclick="switchTab('register')"><span aria-hidden="true">✍️</span> Apply to Join</button>
  </div>
  <div class="modal-body">

    <!-- LOGIN PANEL — Phone + Passkey -->
    <div class="mpanel on" id="pLogin" role="tabpanel" aria-labelledby="tLogin">
      <div class="fmsg" id="loginMsg" role="alert" aria-live="assertive"></div>

      <!-- STEP 1: Phone number (username) with remember -->
      <div id="stepPhone">
        <label class="flbl" for="loginPhone"><span aria-hidden="true">📱</span> Phone Number (Username)</label>
        <input type="tel" class="finp" id="loginPhone" placeholder="98765 43210" maxlength="10" inputmode="numeric"
          autocomplete="username" oninput="this.value=this.value.replace(/\D/g,'')">
        <div style="display:flex;align-items:center;gap:.5rem;margin:.4rem 0 .8rem">
          <input type="checkbox" id="rememberPhone" style="width:16px;height:16px;accent-color:var(--p);cursor:pointer">
          <label for="rememberPhone" style="font-size:.78rem;color:var(--t2);cursor:pointer;user-select:none">Remember my number</label>
        </div>
        <button type="button" class="fbtn fbtn-p" id="btnNext" onclick="doCheckPhone()">
          Next →
        </button>
        <button type="button" class="fbtn" id="btnBioLogin" onclick="bioLogin()" style="display:none;width:100%;margin-top:.5rem;background:#fff;border:1.5px solid #1565c0;color:#1565c0;font-weight:800">
          <i class="fas fa-fingerprint"></i> Login with Fingerprint / Face ID
        </button>
        <p class="fhint">Enter your registered 10-digit mobile number.</p>
      </div>

      <!-- STEP 2a: Enter Passkey (number keypad) -->
      <div id="stepPasskey" style="display:none">
        <button type="button" class="fback" onclick="backStep('stepPhone')">← Change Number</button>
        <div style="text-align:center;margin-bottom:.9rem">
          <div id="loginNameHint" style="font-size:.82rem;color:var(--t2);margin-bottom:.25rem"></div>
          <div style="font-size:.85rem;color:var(--t3)">Enter your 6-digit passkey <span class="sr-only">— type the numbers or use the keypad</span></div>
        </div>
        <!-- Passkey display dots -->
        <div style="display:flex;justify-content:center;gap:.55rem;margin-bottom:1.2rem" id="pkDots" aria-hidden="true">
          <div class="pk-dot"></div><div class="pk-dot"></div><div class="pk-dot"></div>
          <div class="pk-dot"></div><div class="pk-dot"></div><div class="pk-dot"></div>
        </div>
        <!-- Number keypad -->
        <div class="num-keypad" id="loginKeypad" role="group" aria-label="Passkey keypad">
          <button type="button" onclick="pkTap(\'1\')">1</button>
          <button type="button" onclick="pkTap(\'2\')">2<span>ABC</span></button>
          <button type="button" onclick="pkTap(\'3\')">3<span>DEF</span></button>
          <button type="button" onclick="pkTap(\'4\')">4<span>GHI</span></button>
          <button type="button" onclick="pkTap(\'5\')">5<span>JKL</span></button>
          <button type="button" onclick="pkTap(\'6\')">6<span>MNO</span></button>
          <button type="button" onclick="pkTap(\'7\')">7<span>PQRS</span></button>
          <button type="button" onclick="pkTap(\'8\')">8<span>TUV</span></button>
          <button type="button" onclick="pkTap(\'9\')">9<span>WXYZ</span></button>
          <button type="button" onclick="pkTap('del')" class="pk-del" style="font-size:1.1rem" aria-label="Delete last digit">⌫</button>
          <button type="button" onclick="pkTap(\'0\')">0</button>
          <button type="button" onclick="pkTap('ok')" class="pk-ok" aria-label="Log in">✓</button>
        </div>
        <p style="text-align:center;font-size:.76rem;margin-top:.7rem">
          <a href="#" onclick="showSetPasskey();return false" style="color:var(--p);display:inline-block;padding:.5rem">Forgot passkey? Reset it</a>
        </p>
      </div>

      <!-- STEP 2b: No passkey — create one -->
      <div id="stepCreatePasskey" style="display:none">
        <button type="button" class="fback" onclick="backStep('stepPhone')">← Change Number</button>
        <div style="text-align:center;margin:.3rem 0 1rem">
          <div style="font-size:1.6rem;margin-bottom:.4rem" aria-hidden="true">🔑</div>
          <div style="font-weight:700;font-size:.95rem;color:var(--p)">Create Your Passkey</div>
          <div style="font-size:.78rem;color:var(--t3);margin-top:.25rem">You'll use this 6-digit code every time you login</div>
        </div>
        <!-- Name verify field -->
        <label class="flbl" for="pkName">Your Registered Name (for verification)</label>
        <input type="text" class="finp" id="pkName" placeholder="Enter your full name as registered" autocomplete="name">
        <!-- New passkey dots -->
        <div style="display:flex;justify-content:center;gap:.55rem;margin:1rem 0 .5rem" id="newPkDots" aria-hidden="true">
          <div class="pk-dot"></div><div class="pk-dot"></div><div class="pk-dot"></div>
          <div class="pk-dot"></div><div class="pk-dot"></div><div class="pk-dot"></div>
        </div>
        <div style="text-align:center;font-size:.74rem;color:var(--t3);margin-bottom:.8rem">Choose a 6-digit passkey</div>
        <!-- Keypad for new passkey -->
        <div class="num-keypad" id="createKeypad" role="group" aria-label="New passkey keypad">
          <button type="button" onclick="pkNewTap(\'1\')">1</button>
          <button type="button" onclick="pkNewTap(\'2\')">2<span>ABC</span></button>
          <button type="button" onclick="pkNewTap(\'3\')">3<span>DEF</span></button>
          <button type="button" onclick="pkNewTap(\'4\')">4<span>GHI</span></button>
          <button type="button" onclick="pkNewTap(\'5\')">5<span>JKL</span></button>
          <button type="button" onclick="pkNewTap(\'6\')">6<span>MNO</span></button>
          <button type="button" onclick="pkNewTap(\'7\')">7<span>PQRS</span></button>
          <button type="button" onclick="pkNewTap(\'8\')">8<span>TUV</span></button>
          <button type="button" onclick="pkNewTap(\'9\')">9<span>WXYZ</span></button>
          <button type="button" onclick="pkNewTap('del')" class="pk-del" aria-label="Delete last digit">⌫</button>
          <button type="button" onclick="pkNewTap(\'0\')">0</button>
          <button type="button" onclick="pkNewTap('ok')" class="pk-ok" aria-label="Save passkey">✓</button>
        </div>
      </div>

    </div>

    <!-- REGISTER PANEL -->
    <div class="mpanel" id="pRegister" role="tabpanel" aria-labelledby="tRegister">
      <div class="fmsg" id="regMsg" role="alert" aria-live="assertive"></div>
      <div id="regForm">
        <label class="flbl" for="rName">Full Name *</label>
        <input type="text" class="finp" id="rName" placeholder="Your full name" autocomplete="name" required>
        <label class="flbl" for="rPhone">WhatsApp Number *</label>
        <input type="tel" class="finp" id="rPhone" placeholder="98765 43210" maxlength="10" inputmode="numeric" autocomplete="tel-national" required>
        <div class="frow">
          <div>
            <label class="flbl" for="rBlood">Blood Group</label>
            <select class="finp" id="rBlood" style="margin-bottom:0">
              <option value="">— Select —</option>
              <?php foreach(array('A+','A-','B+','B-','AB+','AB-','O+','O-') as $bg): ?>
              <option><?= $bg ?></option>
              <?php endforeach; ?>
            </select>
          </div>
          <div>
            <label class="flbl" for="rSkill">Skill / Sport</label>
            <input type="text" class="finp" id="rSkill" placeholder="e.g. Football" style="margin-bottom:0">
          </div>
        </div>
        <div style="margin-top:.9rem">
          <label class="flbl" for="rProfession">Profession / Occupation</label>
          <input type="text" class="finp" id="rProfession" placeholder="e.g. Teacher, Engineer, Business…">
        </div>
        <button type="button" class="fbtn fbtn-g" id="btnReg" onclick="doRegister()">
          <i class="fas fa-user-plus"></i> Submit Application
        </button>
        <p class="fhint">Secretary will review and activate your account via WhatsApp.</p>
      </div>
      <div id="regSuccess" style="display:none">
        <div class="success-panel">
          <div class="success-em" aria-hidden="true">🎉</div>
          <h4 style="font-family:'Playfair Display',serif;color:var(--p);margin-bottom:.5rem">Application Submitted!</h4>
          <p style="font-size:.87rem;color:var(--t2);line-height:1.65">The Secretary will review and activate your account. You'll receive a WhatsApp message when approved.</p>
          <button class="fbtn fbtn-p" style="margin-top:1.2rem;max-width:160px;margin-left:auto;margin-right:auto" onclick="closeModal()"><i class="fas fa-check"></i> Done</button>
        </div>
      </div>
    </div>

  </div>

  <!-- Add to Home Screen button -->
  <div style="padding:.5rem 1rem .7rem">
    <button type="button" id="pwaInstallBtn" onclick="pwaInstall()" style="display:none;width:100%;min-height:44px;padding:.52rem;background:linear-gradient(135deg,#1B5E20,#2E7D32);color:#fff;border:none;border-radius:12px;font-weight:800;font-size:.8rem;cursor:pointer;align-items:center;justify-content:center;gap:.4rem">
      📲 Add to Home Screen
    </button>
    <div id="pwaIosHint" style="display:none;text-align:center;font-size:.7rem;color:#64748b;padding:.4rem;background:#f0fdf4;border-radius:8px;border:1px solid #bbf7d0">
      📲 Tap <strong>Share</strong> then <strong>"Add to Home Screen"</strong> to install
    </div>
  </div>
</div>
</div>


<!-- ══════════════════ HERO ══════════════════ -->
<main id="main" tabindex="-1" style="outline:none">
<section id="hero" aria-roledescription="carousel" aria-label="Highlights">
  <?php foreach($heroSlides as $i=>$sl): ?>
  <div class="hslide <?= $i===0?'on':'' ?>" data-idx="<?= $i ?>" role="group" aria-roledescription="slide" aria-label="<?= ($i+1).' of '.count($heroSlides) ?>"<?= $i===0?'':' aria-hidden="true"' ?>>
    <div class="hslide-bg" style="<?= !empty($sl['img']) ? "background-image:url('".h($sl['img'])."')" : 'background:linear-gradient('.h($sl['grad']).')' ?>"></div>
  </div>
  <?php endforeach; ?>
  <div class="hero-shade"></div>
  <div class="hcontent">
    <div class="hbadge"><i aria-hidden="true"></i><?= h($heroBadge) ?></div>
    <h1 class="htitle"><?= h($heroTitle) ?></h1>
    <p class="hsub"><?= h($heroSub) ?></p>
    <div class="hcta">
      <?php if($_pLoggedIn): ?>
        <a class="btn-hero-p" href="<?= url('dashboard.php') ?>"><?= ic('home') ?> Open dashboard</a>
      <?php else: ?>
        <button type="button" class="btn-hero-p" onclick="openModal('login')"><?= ic('login') ?> <?= h($hs('hero_cta_text','Member login')) ?></button>
        <button type="button" class="btn-hero-s" onclick="openModal('register')"><?= ic('plus') ?> Join the club</button>
      <?php endif; ?>
    </div>
  </div>
  <?php if(count($heroSlides) > 1): ?>
  <div class="hdots" id="heroDots">
    <?php foreach($heroSlides as $i=>$sl): ?>
    <button type="button" class="hdot <?= $i===0?'on':'' ?>" data-idx="<?= $i ?>" onclick="heroGo(<?= $i ?>)" aria-label="Show slide <?= $i+1 ?>"<?= $i===0?' aria-current="true"':'' ?>></button>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>
</section>

<?php if($hon('home_stats_show')): ?>
<div class="stats-bar" aria-label="Club in numbers">
  <div class="stat-card"><span class="stat-num" data-target="<?= (int)($stats['total']??0) ?>"><?= (int)($stats['total']??0) ?></span><span class="stat-lbl">Members</span></div>
  <div class="stat-card"><span class="stat-num" data-target="<?= (int)($stats['active']??0) ?>"><?= (int)($stats['active']??0) ?></span><span class="stat-lbl">Active</span></div>
  <div class="stat-card"><span class="stat-num" data-target="<?= count($upEvents) ?>"><?= count($upEvents) ?></span><span class="stat-lbl">Events</span></div>
  <div class="stat-card"><span class="stat-num" data-target="<?= (int)($stats['donors']??0) ?>"><?= (int)($stats['donors']??0) ?></span><span class="stat-lbl">Donors</span></div>
</div>
<?php endif; ?>

<?php if($hon('home_about_show')): ?>
<!-- ══ ABOUT ══ -->
<section class="sec" id="about" aria-labelledby="aboutH">
  <div class="wrap about">
    <div>
      <span class="eyebrow">About us</span>
      <h2 class="sec-title" id="aboutH"><?= h($hs('home_about_title', 'Uniting '.$clubPlace.' through sports, arts and service')) ?></h2>
      <p><?= h($hs('home_about_text', $clubName.' brings people of '.$clubPlace.' together — football and games, arts and festivals, blood donation and community help. Join us and be part of it.')) ?></p>
    </div>
    <div class="pillars">
      <div class="pillar"><span class="appic"><?= app_img('football') ?></span><b>Sports</b><span>Tournaments and training</span></div>
      <div class="pillar"><span class="appic"><?= app_img('arts') ?></span><b>Arts &amp; culture</b><span>Festivals and talent</span></div>
      <div class="pillar"><span class="appic"><?= app_img('blood') ?></span><b>Blood donors</b><span>Help when it matters</span></div>
      <div class="pillar"><span class="appic"><?= app_img('donations') ?></span><b>Community</b><span>Charity and support</span></div>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if($hon('home_activities_show') && !empty($clubActs)): ?>
<!-- ══ ACTIVITIES (Club Settings → Activities) ══ -->
<section class="sec dark" id="activities" aria-labelledby="actH">
  <div class="wrap">
    <div class="sec-head"><div><span class="eyebrow">What we do</span><h2 class="sec-title" id="actH">Club activities</h2></div></div>
    <div class="cgrid g-3">
      <?php foreach($clubActs as $ca): $c = preg_match('/^#[0-9a-fA-F]{6}$/',(string)$ca['color']) ? $ca['color'] : '#14B8A6'; ?>
      <article class="gcard act" style="--c:<?= h($c) ?>">
        <div class="act-em" aria-hidden="true"><?= h($ca['emoji'] ?: '🏆') ?></div>
        <b><?= h($ca['name']) ?></b>
        <?php if(!empty($ca['description'])): ?><p><?= h($ca['description']) ?></p><?php endif; ?>
        <div class="act-links">
          <?php if(!empty($ca['reg_link'])): ?><a class="chip chip-a" href="<?= h($ca['reg_link']) ?>" target="_blank" rel="noopener">Register</a><?php endif; ?>
          <?php if(!empty($ca['info_url'])): ?><a class="chip chip-g" href="<?= h($ca['info_url']) ?>" target="_blank" rel="noopener">Details</a><?php endif; ?>
        </div>
      </article>
      <?php endforeach; ?>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if($hon('home_events_show')): ?>
<!-- ══ EVENTS ══ -->
<section class="sec" id="events" aria-labelledby="evH">
  <div class="wrap">
    <div class="sec-head"><div><span class="eyebrow">Coming up</span><h2 class="sec-title" id="evH">Upcoming events</h2></div>
      <a class="link-more" href="<?= $_pLoggedIn ? url('modules/events.php') : '#' ?>"<?= $_pLoggedIn ? '' : ' onclick="openModal(\'login\');return false"' ?>>All events <?= ic('next','ic-sm') ?></a></div>
    <?php if(empty($upEvents)): ?>
      <div class="card empty">No upcoming events right now. Check back soon.</div>
    <?php else: ?>
    <div class="cgrid g-2">
      <?php foreach(array_slice($upEvents,0,6) as $ev): $d = (int)ceil((strtotime($ev['event_date'])-strtotime('today'))/86400); ?>
      <article class="card ev">
        <div class="ev-date"><b><?= date('d',strtotime($ev['event_date'])) ?></b><small><?= date('M',strtotime($ev['event_date'])) ?></small></div>
        <div style="min-width:0">
          <h3><?= h($ev['title']) ?><?php if($d<=1): ?><span class="soon"><?= $d===0?'Today':'Tomorrow' ?></span><?php elseif($d<=7): ?><span class="soon">In <?= $d ?> days</span><?php endif; ?></h3>
          <?php if(!empty($ev['description'])): ?><p><?= h(mb_strimwidth($ev['description'],0,120,'…')) ?></p><?php endif; ?>
          <div class="meta">
            <?php if(!empty($ev['event_time'])): ?><span><?= ic('calendar','ic-sm') ?><?= h($ev['event_time']) ?></span><?php endif; ?>
            <?php if(!empty($ev['location'])): ?><span><?= ic('map','ic-sm') ?><?= h($ev['location']) ?></span><?php endif; ?>
          </div>
        </div>
      </article>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
  </div>
</section>
<?php endif; ?>

<?php if($hon('home_notices_show') && !empty($homeNotices)): ?>
<!-- ══ NOTICE BOARD ══ -->
<section class="sec dark" id="notices" aria-labelledby="nbH">
  <div class="wrap">
    <div class="sec-head"><div><span class="eyebrow">Latest</span><h2 class="sec-title" id="nbH">Notice board</h2></div></div>
    <div class="cgrid g-2">
      <?php foreach(array_slice($homeNotices,0,6) as $hn): $pr = $hn['priority'] ?? 'normal'; ?>
      <article class="gcard note">
        <span class="tile <?= $pr==='emergency'?'tone-rose':($pr==='urgent'?'tone-amber':'tone-teal') ?>"><?= ic('megaphone') ?></span>
        <div style="min-width:0">
          <b><?= h($hn['title']) ?><?php if(!empty($hn['is_pinned'])): ?><span class="pill">Pinned</span><?php endif; ?><?php if($pr==='urgent'||$pr==='emergency'): ?><span class="pill"><?= ucfirst($pr) ?></span><?php endif; ?></b>
          <p><?= h(mb_strimwidth($hn['body'],0,220,'…')) ?></p>
          <small><?= date('d M Y', strtotime($hn['created_at'])) ?></small>
        </div>
      </article>
      <?php endforeach; ?>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if($hon('home_committee_show') && !empty($committee)):
  $roleLbl = array('president'=>'President','vice_president'=>'Vice President','secretary'=>'Secretary','joint_secretary'=>'Jt. Secretary','treasurer'=>'Treasurer','committee_member'=>'Committee'); ?>
<!-- ══ COMMITTEE ══ -->
<section class="sec white" id="committee" aria-labelledby="comH">
  <div class="wrap">
    <div class="sec-head"><div><span class="eyebrow">Club leadership</span><h2 class="sec-title" id="comH">Our committee</h2></div></div>
    <div class="cgrid g-p">
      <?php foreach($committee as $cm): $photo = !empty($cm['profile_photo']) ? getMemberPhoto($cm['profile_photo']) : ''; ?>
      <div class="card person">
        <?php if($photo): ?><img src="<?= $photo ?>" alt="" loading="lazy"><?php else: ?><span class="ph"><?= ic('user','ic-lg') ?></span><?php endif; ?>
        <b><?= h($cm['name']) ?></b>
        <span><?= h(!empty($cm['committee_position']) ? $cm['committee_position'] : (isset($roleLbl[$cm['role']]) ? $roleLbl[$cm['role']] : 'Committee')) ?></span>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if($hon('home_achievements_show') && !empty($pubAch)):
  $medal = array('gold'=>'🥇','silver'=>'🥈','bronze'=>'🥉'); ?>
<!-- ══ ACHIEVEMENTS ══ -->
<section class="sec dark" id="achievements" aria-labelledby="achH">
  <div class="wrap">
    <div class="sec-head"><div><span class="eyebrow">Proud moments</span><h2 class="sec-title" id="achH">Achievements</h2></div></div>
    <div class="ach-row" tabindex="0" role="region" aria-label="Achievements">
      <?php foreach($pubAch as $pa):
        $pUrl=''; if(!empty($pa['image'])) $pUrl=(strpos($pa['image'],'/')!==false)?url('assets/uploads/'.$pa['image']):url('assets/uploads/achievements/'.$pa['image']);
        $md = isset($medal[$pa['medal_type'] ?? '']) ? $medal[$pa['medal_type']] : '🏆'; ?>
      <button type="button" class="gcard ach" <?php if($pUrl): ?>onclick="openLB('<?= addslashes(h($pUrl)) ?>','<?= addslashes(h($pa['title'])) ?>')"<?php endif; ?>>
        <div class="img"><?php if($pUrl): ?><img src="<?= h($pUrl) ?>" alt="" loading="lazy"><?php else: ?><span aria-hidden="true"><?= $md ?></span><?php endif; ?></div>
        <div class="body"><b><?= $md ?> <?= h($pa['title']) ?></b><span><?= h($pa['member_name'] ?? '') ?><?= !empty($pa['achievement_date']) ? ' · '.date('M Y',strtotime($pa['achievement_date'])) : '' ?></span></div>
      </button>
      <?php endforeach; ?>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if($hon('home_gallery_show')): ?>
<!-- ══ GALLERY ══ -->
<section class="sec" id="gallery" aria-labelledby="galH">
  <div class="wrap">
    <div class="sec-head"><div><span class="eyebrow">Moments</span><h2 class="sec-title" id="galH">Gallery</h2><p class="sec-sub">Memories from every event in <?= h($clubPlace) ?>.</p></div>
      <?php if(!$_pLoggedIn): ?><a class="link-more" href="#" onclick="openModal('login');return false">Log in for full gallery <?= ic('next','ic-sm') ?></a><?php else: ?><a class="link-more" href="<?= url('modules/gallery.php') ?>">Full gallery <?= ic('next','ic-sm') ?></a><?php endif; ?></div>
    <div class="gal">
      <?php foreach(array_slice($galItems,0,10) as $gi): $isImg = ($gi['type']==='img'); ?>
      <div class="gal-cell" <?php if($isImg): ?>role="button" tabindex="0" aria-label="View photo: <?= h($gi['title']) ?>" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}" onclick="openLB('<?= addslashes(h($gi['src'])) ?>','<?= addslashes(h($gi['title'])) ?>')"<?php endif; ?>>
        <?php if($isImg): ?><img src="<?= h($gi['src']) ?>" alt="<?= h($gi['title']) ?>" loading="lazy" onerror="this.parentNode.innerHTML='<div class=gal-cell-ph>🖼️</div>'">
        <?php else: ?><div class="gal-cell-ph"><span aria-hidden="true"><?= $gi['em'] ?></span><span><?= h($gi['title']) ?></span></div><?php endif; ?>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if($hon('home_join_show') && !$_pLoggedIn): ?>
<!-- ══ JOIN ══ -->
<section class="sec" style="padding-top:0" aria-labelledby="joinH">
  <div class="wrap">
    <div class="join">
      <h2 class="sec-title" id="joinH"><?= h($hs('home_join_title','Be part of the club')) ?></h2>
      <p><?= h($hs('home_join_text','Apply in one minute. The secretary approves your membership and you get access to events, the members portal and your digital ID card.')) ?></p>
      <div class="hcta">
        <button type="button" class="btn-hero-p" onclick="openModal('register')"><?= ic('plus') ?> Apply to join</button>
        <?php if($wa): ?><a class="btn-hero-s" href="https://wa.me/<?= h($wa) ?>" target="_blank" rel="noopener"><?= ic('whatsapp') ?> WhatsApp us</a><?php endif; ?>
      </div>
    </div>
  </div>
</section>
<?php endif; ?>
</main>

<!-- ══════════════════ FOOTER ══════════════════ -->
<footer id="footer">
<div class="wrap">
  <div class="foot">
    <div>
      <div class="foot-brand"><?php if($logo): ?><img src="<?= $logo ?>" alt="" width="46" height="46"><?php endif; ?><span><b><?= h($clubName) ?></b><?= h($clubTag) ?></span></div>
      <p style="font-size:.92rem;white-space:pre-line"><?= h($hs('footer_text', 'Uniting '.$clubPlace.' through sports, arts and community service.')) ?></p>
      <div class="sicons">
        <?php if($wa): ?><a href="https://wa.me/<?= h($wa) ?>" target="_blank" rel="noopener" class="sicon" aria-label="WhatsApp" style="background:#1DA851"><i class="fab fa-whatsapp" aria-hidden="true"></i></a><?php endif; ?>
        <?php
        $footSocials = array();
        foreach ($HS as $k=>$v) { if (strpos($k,'social_')===0 && $v!=='') $footSocials[$k] = $v; }
        $footIconMap = array(
          'social_wa_group'=>array('fab fa-whatsapp','#128c7e','WhatsApp group'),'social_facebook'=>array('fab fa-facebook-f','#1877f2','Facebook'),
          'social_instagram'=>array('fab fa-instagram','#C13584','Instagram'),'social_youtube'=>array('fab fa-youtube','#D90000','YouTube'),
          'social_twitter'=>array('fab fa-x-twitter','#000','X / Twitter'),'social_telegram'=>array('fab fa-telegram','#0077b5','Telegram'),
          'social_linkedin'=>array('fab fa-linkedin-in','#0a66c2','LinkedIn'),'social_tiktok'=>array('fab fa-tiktok','#010101','TikTok'),
          'social_website'=>array('fas fa-globe','#0A14E0','Website'));
        foreach($footIconMap as $fk=>$fi): if(empty($footSocials[$fk])) continue; ?>
        <a href="<?= h($footSocials[$fk]) ?>" target="_blank" rel="noopener" class="sicon" aria-label="<?= h($fi[2]) ?>" style="background:<?= $fi[1] ?>"><i class="<?= $fi[0] ?>" aria-hidden="true"></i></a>
        <?php endforeach; ?>
      </div>
    </div>
    <div>
      <h2>Explore</h2>
      <a class="fl" href="#hero">Home</a>
      <?php if($hon('home_events_show')): ?><a class="fl" href="#events">Events</a><?php endif; ?>
      <?php if($hon('home_gallery_show')): ?><a class="fl" href="#gallery">Gallery</a><?php endif; ?>
      <a class="fl" href="<?= url('modules/market.php') ?>">Mini Market</a>
      <a class="fl" href="<?= url('contact.php') ?>">Contact</a>
    </div>
    <div>
      <h2>Members</h2>
      <?php if($_pLoggedIn): ?>
        <a class="fl" href="<?= url('dashboard.php') ?>">Dashboard</a>
      <?php else: ?>
        <a class="fl" href="#" role="button" onclick="openModal('login');return false">Login</a>
        <a class="fl" href="#" role="button" onclick="openModal('register');return false">Apply to join</a>
      <?php endif; ?>
      <a class="fl" href="<?= url('modules/blood.php') ?>">Blood Hub</a>
      <a class="fl" href="<?= url('modules/crowdfund.php') ?>">Donate</a>
    </div>
    <div>
      <h2>Contact</h2>
      <p style="display:flex;gap:.5rem;align-items:center;min-height:40px"><?= ic('map','ic-sm') ?><?= h($clubPlace) ?>, Kerala</p>
      <p style="display:flex;gap:.5rem;align-items:center;min-height:40px"><?= ic('phone','ic-sm') ?><?= h(setting('CLUB_PHONE','')) ?></p>
      <?php if($wa): ?><a href="https://wa.me/<?= h($wa) ?>" target="_blank" rel="noopener" class="btn-login" style="margin-top:.5rem"><?= ic('whatsapp','ic-sm') ?> Chat on WhatsApp</a><?php endif; ?>
    </div>
  </div>
  <div class="foot-btm">© <?= date('Y') ?> <b><?= h($clubName) ?></b> · <?= h($clubPlace) ?> · Kerala · All rights reserved · <b>anexpaikadan</b></div>
</div>
</footer>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script>
$(function(){

/* UTILITY */
function showMsg(sel, type, msg){
  var el=$(sel);
  el.removeClass('ok err').addClass(type).html(msg).show();
}

/* ═══════════════════════════════════════════════════════
   AISHWARYA CLUB — MAIN JS
═══════════════════════════════════════════════════════ */

/* 1. MODAL FUNCTIONS — defined first so all callers can use them */
function resetModal(){
  $('#stepPhone').show(); $('#stepOTP').hide();
  $('#loginPhone').val('');
  $('.otp-cell').val('');
  $('#loginMsg').hide().removeClass('ok err');
  $('#regMsg').hide().removeClass('ok err');
  $('#regForm').show(); $('#regSuccess').hide();
}

function switchTab(tab){
  var isL = tab === 'login';
  $('#pLogin').toggleClass('on', isL);
  $('#pRegister').toggleClass('on', !isL);
  $('#tLogin').toggleClass('on', isL).attr('aria-selected', isL ? 'true' : 'false');
  $('#tRegister').toggleClass('on', !isL).attr('aria-selected', isL ? 'false' : 'true');
  $('#mTitle').text(isL ? 'Member Portal' : 'Apply to Join');
}

var _modalReturnFocus = null;
function openModal(tab){
  _modalReturnFocus = document.activeElement;
  $('#loginOverlay').addClass('show');
  $('body').css('overflow','hidden');
  switchTab(tab || 'login');
  setTimeout(function(){ $(tab === 'register' ? '#rName' : '#loginPhone').trigger('focus'); }, 300);
}

function closeModal(){
  if(!$('#loginOverlay').hasClass('show')) return;
  $('#loginOverlay').removeClass('show');
  $('body').css('overflow','');
  resetModal();
  if(_modalReturnFocus && _modalReturnFocus.focus) _modalReturnFocus.focus();
}

// Passkey: let people type digits on a keyboard as well as tapping the keypad
document.addEventListener('keydown', function(e){
  if(!$('#loginOverlay').hasClass('show')) return;
  var t = e.target;
  if(t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA')) return;
  var fn = $('#stepPasskey').is(':visible') ? window.pkTap : ($('#stepCreatePasskey').is(':visible') ? window.pkNewTap : null);
  if(typeof fn !== 'function') return;
  if(/^[0-9]$/.test(e.key)){ e.preventDefault(); fn(e.key); }
  else if(e.key === 'Backspace'){ e.preventDefault(); fn('del'); }
  else if(e.key === 'Enter' && t.tagName !== 'BUTTON'){ e.preventDefault(); fn('ok'); }
});

// Expose to global scope for inline onclick="" handlers
window.openModal  = openModal;
window.closeModal = closeModal;
window.switchTab  = switchTab;

/* 2. NAVBAR SCROLL */
$(window).on('scroll', function(){
  $('#mainNav').toggleClass('scrolled', $(this).scrollTop() > 60);
  var cur = 'hero';
  var secs = ['hero','events','gallery'];
  for(var i = 0; i < secs.length; i++){
    var el = $('#' + secs[i]);
    if(el.length && $(window).scrollTop() >= el.offset().top - 140) cur = secs[i];
  }
  $('#navLinks a').removeClass('on').removeAttr('aria-current');
  $('#navLinks a[href="#'+cur+'"]').addClass('on').attr('aria-current','true');
});

/* 3. SMOOTH SCROLL */
$('a[href^="#"]').on('click', function(e){
  var t = $($(this).attr('href'));
  if(t.length){ e.preventDefault(); $('html,body').animate({scrollTop: t.offset().top - 66}, 500); }
});

/* 4. MOBILE MENU */
window.toggleMob = function(){
  var open = !$('#mobMenu').hasClass('open');
  $('#hb').toggleClass('open', open).attr({'aria-expanded': open ? 'true' : 'false', 'aria-label': open ? 'Close menu' : 'Open menu'});
  $('#mobMenu').toggleClass('open', open);
};
window.closeMob  = function(){ $('#hb').removeClass('open').attr({'aria-expanded':'false','aria-label':'Open menu'}); $('#mobMenu').removeClass('open'); };

/* 5. MODAL TRIGGERS */
$('#openLogin').on('click', function(){ openModal('login'); });
$('#loginOverlay').on('click', function(e){ if(e.target === this) closeModal(); });
$(document).on('keydown', function(e){ if(e.key === 'Escape'){ closeModal(); closeMob(); $('#iosSheet').removeClass('open'); } });

// Auto-open if redirected with ?login=1
if(window.location.search.indexOf('login=1') !== -1){
  setTimeout(function(){ openModal('login'); }, 400);
}

/* 6. OTP CELLS */
var cells = $('.otp-cell').toArray();
$(cells).each(function(i){
  $(this).on('input', function(e){
    var v = e.target.value.replace(/[^0-9]/g,'');
    e.target.value = v ? v[0] : '';
    if(v && i < 5) cells[i+1].focus();
  }).on('keydown', function(e){
    if(e.key==='Backspace' && !this.value && i>0){ $(cells[i-1]).val('').focus(); }
    if(e.key==='ArrowLeft'  && i>0) cells[i-1].focus();
    if(e.key==='ArrowRight' && i<5) cells[i+1].focus();
    if(e.key==='Enter') { if(typeof doVerify==='function') doVerify(); }
  }).on('paste', function(e){
    e.preventDefault();
    var t = ((e.originalEvent.clipboardData||window.clipboardData).getData('text')).replace(/[^0-9]/g,'');
    t.slice(0,6).split('').forEach(function(ch,j){ if(cells[j]) cells[j].value=ch; });
    cells[Math.min(t.length,5)].focus();
  });
});
function getOTP(){ return $.map(cells, function(b){ return b.value; }).join(''); }

/* 7. HERO SLIDER */
var hIdx=0, hTotal=<?= count($heroSlides) ?>, hTimer, hPaused=false;
// No auto-advance for people who asked their phone to reduce motion
var hReduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function heroSchedule(){
  clearTimeout(hTimer);
  if(hTotal > 1 && !hReduce && !hPaused) hTimer = setTimeout(function(){ heroGo(hIdx+1); }, 6000);
}
function heroGo(n){
  hIdx = (n + hTotal) % hTotal;
  $('.hslide').removeClass('on').attr('aria-hidden','true');
  $('.hdot').removeClass('on').removeAttr('aria-current');
  $('.hslide[data-idx="'+hIdx+'"]').addClass('on').removeAttr('aria-hidden');
  $('.hdot[data-idx="'+hIdx+'"]').addClass('on').attr('aria-current','true');
  heroSchedule();
}
window.heroMove = function(d){ heroGo(hIdx + d); };
window.heroGo   = heroGo;
// Pause while the pointer or keyboard focus is on the slider
$('#hero').on('mouseenter focusin', function(){ hPaused = true; clearTimeout(hTimer); })
          .on('mouseleave focusout', function(e){
            if(e.type === 'focusout' && this.contains(e.relatedTarget)) return;
            hPaused = false; heroSchedule();
          });
heroSchedule();

/* 8. STATS COUNT-UP */
var statsDone = false;
function runStats(){
  if(statsDone) return; statsDone = true;
  $('.stat-num').each(function(){
    var el=$(this), target=parseInt(el.data('target'))||parseInt(el.text())||0, current=0;
    var step = Math.max(1, Math.ceil(target/60));
    var timer = setInterval(function(){
      current = Math.min(current+step, target);
      el.text(current);
      if(current >= target) clearInterval(timer);
    }, 25);
  });
}
var statsObs = new IntersectionObserver(function(entries){
  entries.forEach(function(e){ if(e.isIntersecting) runStats(); });
}, {threshold:0.3});
var statsBar = document.querySelector('.stats-bar');
if(statsBar) statsObs.observe(statsBar);

/* 9. SCROLL REVEAL */
var revObs = new IntersectionObserver(function(entries){
  entries.forEach(function(e){ if(e.isIntersecting) e.target.classList.add('in'); });
}, {threshold:0.08, rootMargin:'0px 0px -40px 0px'});
document.querySelectorAll('.rv,.rl,.rr').forEach(function(el){ revObs.observe(el); });
setTimeout(function(){
  document.querySelectorAll('.rv,.rl,.rr').forEach(function(el){ el.classList.add('in'); });
}, 400);

/* ──────────────────────────────────────────────────────── */
var pkVal = '';      // current passkey being entered
var pkNewVal = '';   // new passkey being created
var currentPhone = '';

// Load remembered phone
(function(){
  var saved = localStorage.getItem('av_phone');
  if (saved) {
    $('#loginPhone').val(saved);
    $('#rememberPhone').prop('checked', true);
  }
})();

// Step 1: Check phone
window.doCheckPhone = function(){
  var raw = $('#loginPhone').val().replace(/\D/g,'');
  if (raw.length < 10){ showMsg('#loginMsg','err','Enter a valid 10-digit number.'); return; }
  currentPhone = raw;
  // Remember phone
  if ($('#rememberPhone').is(':checked')) {
    localStorage.setItem('av_phone', raw);
  } else {
    localStorage.removeItem('av_phone');
  }
  $('#btnNext').prop('disabled',true);
  showMsg('#loginMsg','ok','<i class="fas fa-spinner fa-spin me-1"></i>Checking…');
  $.ajax({ url:'', method:'POST',
    data:{ ajax:'1', action:'check_phone', phone:raw },
    dataType:'json',
    success: function(d){
      $('#btnNext').prop('disabled',false);
      if (d.ok) {
        $('#loginMsg').hide();
        pkVal = '';
        updateDots('pkDots', pkVal);
        if (d.has_passkey) {
          // Show passkey entry
          $('#loginNameHint').text('Welcome back, ' + d.name_hint);
          $('#stepPhone').hide();
          $('#stepPasskey').show();
        } else {
          // No passkey yet — create one
          $('#stepPhone').hide();
          $('#stepCreatePasskey').show();
        }
      } else {
        showMsg('#loginMsg','err','<i class="fas fa-times-circle me-1"></i>'+d.msg);
      }
    },
    error: function(){ $('#btnNext').prop('disabled',false); showMsg('#loginMsg','err','Network error.'); }
  });
};
$('#loginPhone').on('keydown', function(e){ if(e.key==='Enter') doCheckPhone(); });

// ── WebAuthn fingerprint / Face ID login ──
var WA_URL = '<?= url('modules/webauthn.php') ?>';
function waB64urlToBuf(s){ s=s.replace(/-/g,'+').replace(/_/g,'/'); var p=s.length%4; if(p)s+='='.repeat(4-p); var bin=atob(s); var b=new Uint8Array(bin.length); for(var i=0;i<bin.length;i++)b[i]=bin.charCodeAt(i); return b.buffer; }
function waBufToB64url(buf){ var b=new Uint8Array(buf),s=''; for(var i=0;i<b.length;i++)s+=String.fromCharCode(b[i]); return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,''); }
if(window.PublicKeyCredential){ var _bb=document.getElementById('btnBioLogin'); if(_bb) _bb.style.display='block'; }
window.bioLogin = function(){
  var raw=$('#loginPhone').val().replace(/\D/g,'');
  if(raw.length<10){ showMsg('#loginMsg','err','Enter your phone number first.'); return; }
  showMsg('#loginMsg','ok','<i class="fas fa-fingerprint me-1"></i>Touch your fingerprint sensor…');
  $.ajax({url:WA_URL,method:'POST',data:{act:'login_begin',phone:raw},dataType:'json',success:function(d){
    if(!d.ok){ showMsg('#loginMsg','err','<i class="fas fa-times-circle me-1"></i>'+d.msg); return; }
    var o=d.options; o.challenge=waB64urlToBuf(o.challenge);
    if(o.allowCredentials) o.allowCredentials=o.allowCredentials.map(function(c){return {type:c.type,id:waB64urlToBuf(c.id)};});
    navigator.credentials.get({publicKey:o}).then(function(cred){
      var payload={ act:'login_finish', cred_id:cred.id,
        client_data:waBufToB64url(cred.response.clientDataJSON),
        auth_data:waBufToB64url(cred.response.authenticatorData),
        signature:waBufToB64url(cred.response.signature) };
      $.ajax({url:WA_URL,method:'POST',data:payload,dataType:'json',success:function(r){
        if(r.ok){ showMsg('#loginMsg','ok','<i class="fas fa-check-circle me-1"></i>Welcome back!'); setTimeout(function(){ window.location.href=r.url; },700); }
        else showMsg('#loginMsg','err','<i class="fas fa-times-circle me-1"></i>'+r.msg);
      }});
    }).catch(function(){ showMsg('#loginMsg','err','Fingerprint cancelled or failed.'); });
  }});
};

// Back to phone step
window.backStep = function(target){
  $('#stepPasskey,#stepCreatePasskey,#stepName').hide();
  $('#'+target).show();
  $('#loginMsg').hide();
  pkVal=''; pkNewVal='';
  updateDots('pkDots', '');
  updateDots('newPkDots', '');
};

// Update passkey dots display
function updateDots(containerId, val) {
  var dots = $('#'+containerId+' .pk-dot');
  dots.each(function(i){
    $(this).toggleClass('filled', i < val.length);
    $(this).removeClass('err');
  });
}

// Shake dots on error
function shakeDots(containerId) {
  var wrap = $('#'+containerId);
  wrap.css('animation','pkShake .3s ease-in-out');
  $('#'+containerId+' .pk-dot').addClass('err');
  setTimeout(function(){ wrap.css('animation',''); },350);
}

// Login keypad tap
window.pkTap = function(d) {
  if (d === 'del') {
    pkVal = pkVal.slice(0,-1);
    updateDots('pkDots', pkVal);
  } else if (d === 'ok') {
    if (pkVal.length < 6){ shakeDots('pkDots'); return; }
    doLoginPasskey();
  } else {
    if (pkVal.length >= 6) return;
    pkVal += d;
    updateDots('pkDots', pkVal);
    if (pkVal.length === 6) {
      setTimeout(doLoginPasskey, 150);
    }
  }
};

// Submit passkey login
function doLoginPasskey(){
  showMsg('#loginMsg','ok','<i class="fas fa-spinner fa-spin me-1"></i>Verifying…');
  $.ajax({ url:'', method:'POST',
    data:{ ajax:'1', action:'login_passkey', phone:currentPhone, passkey:pkVal },
    dataType:'json',
    success: function(d){
      if (d.ok) {
        showMsg('#loginMsg','ok','<i class="fas fa-check-circle me-1"></i>Login successful!');
        setTimeout(function(){ window.location.href = d.url; }, 700);
      } else {
        pkVal='';
        updateDots('pkDots','');
        shakeDots('pkDots');
        showMsg('#loginMsg','err','<i class="fas fa-times-circle me-1"></i>'+d.msg);
      }
    },
    error: function(){ showMsg('#loginMsg','err','Network error.'); }
  });
}

// Create passkey keypad
window.pkNewTap = function(d){
  if (d === 'del') {
    pkNewVal = pkNewVal.slice(0,-1);
    updateDots('newPkDots', pkNewVal);
  } else if (d === 'ok') {
    if (pkNewVal.length < 6){ shakeDots('newPkDots'); return; }
    doSetPasskey();
  } else {
    if (pkNewVal.length >= 6) return;
    pkNewVal += d;
    updateDots('newPkDots', pkNewVal);
    if (pkNewVal.length === 6) {
      setTimeout(doSetPasskey, 150);
    }
  }
};

// Submit create passkey
function doSetPasskey(){
  var name = $('#pkName').val().trim();
  if (!name){ showMsg('#loginMsg','err','Enter your registered name.'); return; }
  showMsg('#loginMsg','ok','<i class="fas fa-spinner fa-spin me-1"></i>Creating passkey…');
  $.ajax({ url:'', method:'POST',
    data:{ ajax:'1', action:'set_passkey', phone:currentPhone, passkey:pkNewVal, member_name:name },
    dataType:'json',
    success: function(d){
      if (d.ok) {
        showMsg('#loginMsg','ok','<i class="fas fa-check-circle me-1"></i>'+d.msg);
        setTimeout(function(){ window.location.href = d.url; }, 800);
      } else {
        pkNewVal='';
        updateDots('newPkDots','');
        shakeDots('newPkDots');
        showMsg('#loginMsg','err','<i class="fas fa-times-circle me-1"></i>'+d.msg);
      }
    },
    error: function(){ showMsg('#loginMsg','err','Network error.'); }
  });
}

// Show reset passkey (from forgot passkey link)
window.showSetPasskey = function(){
  $('#stepPasskey').hide();
  pkNewVal='';
  updateDots('newPkDots','');
  $('#pkName').val('');
  $('#stepCreatePasskey').show();
};

// Legacy backPhone for any other references
window.backPhone = function(){ backStep('stepPhone'); };

/* ── Register ── */
window.doRegister=function(){
  var name=$('#rName').val().trim(),phone=$('#rPhone').val().replace(/\D/g,'');
  var blood=$('#rBlood').val(),skill=$('#rSkill').val().trim(),prof=$('#rProfession').val().trim();
  if(!name||phone.length<10){showMsg('#regMsg','err','<i class="fas fa-exclamation-circle me-1"></i>Name and WhatsApp number are required.');return;}
  showMsg('#regMsg','ok','<i class="fas fa-spinner fa-spin me-1"></i>Submitting…');
  $('#btnReg').prop('disabled',true);
  $.ajax({url:'',method:'POST',data:{ajax:'1',action:'register',name:name,phone:phone,blood:blood,skill:skill,profession:prof},dataType:'json',
    success:function(d){
      if(d.ok){$('#regForm').hide();$('#regSuccess').show();$('#regMsg').hide();}
      else{$('#btnReg').prop('disabled',false);showMsg('#regMsg','err','<i class="fas fa-times-circle me-1"></i>'+d.msg);}
    },
    error:function(){$('#btnReg').prop('disabled',false);showMsg('#regMsg','err','Network error. Try again.');}
  });
};


});// end $(function)
</script>

<!-- ══ GALLERY LIGHTBOX ══ -->
<div class="lb-ov" id="lbOv" onclick="if(event.target===this)closeLB()" role="dialog" aria-modal="true" aria-label="Photo viewer">
  <div class="lb-swipe-hint" aria-hidden="true">Tap outside to close</div>
  <button type="button" class="lb-close" onclick="closeLB()" aria-label="Close photo">✕</button>
  <div class="lb-img-wrap">
    <img id="lbImg" src="" alt="">
  </div>
  <div class="lb-login-hint">
    <button type="button" onclick="closeLB();openModal('login')"><i class="fas fa-sign-in-alt" aria-hidden="true"></i> Login to see all photos</button>
  </div>
  <div class="lb-caption" id="lbCaption"></div>
</div>

<script>
// Lightbox
function openLB(src, title) {
  var ov = document.getElementById('lbOv');
  var img = document.getElementById('lbImg');
  var cap = document.getElementById('lbCaption');
  img.src = src;
  cap.textContent = title || '';
  img.alt = title || 'Club photo';
  window._lbReturn = document.activeElement;
  ov.classList.add('on');
  document.body.style.overflow = 'hidden';
  setTimeout(function(){ ov.querySelector('.lb-close').focus(); }, 50);
}
function closeLB() {
  var ov = document.getElementById('lbOv');
  if (!ov.classList.contains('on')) return;
  ov.classList.remove('on');
  if (window._lbReturn && window._lbReturn.focus) window._lbReturn.focus();
  document.getElementById('lbImg').src = '';
  document.body.style.overflow = '';
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeLB();
});
// Touch swipe to close on mobile
(function(){
  var startY = 0;
  var ov = document.getElementById('lbOv');
  ov.addEventListener('touchstart', function(e){ startY = e.touches[0].clientY; }, {passive:true});
  ov.addEventListener('touchend', function(e){
    var dy = e.changedTouches[0].clientY - startY;
    if (Math.abs(dy) > 80) closeLB(); // swipe up or down to close
  }, {passive:true});
})();

</script>

<!-- ══ PUBLIC BOTTOM NAV ══ -->
<style>
#pub-bnav{position:fixed;left:.6rem;right:.6rem;bottom:calc(.55rem + env(safe-area-inset-bottom,0px));z-index:9999;max-width:520px;margin:0 auto;
  height:66px;border-radius:24px;display:flex;align-items:center;justify-content:space-around;padding:0 .3rem;
  background:rgba(255,255,255,.92);backdrop-filter:saturate(180%) blur(18px);-webkit-backdrop-filter:saturate(180%) blur(18px);border:1px solid var(--line);box-shadow:0 14px 34px -12px rgba(11,16,51,.35)}
.pbn{flex:1;min-width:0;height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;border:0;background:none;cursor:pointer;
  color:var(--t3);font-size:.7rem;font-weight:700;border-radius:18px}
.pbn .ic{width:23px;height:23px}
.pbn:active .ic{transform:scale(.88)}
.pbn-mid{flex:0 0 auto;width:58px;height:58px;margin:0 .15rem;border-radius:50%;color:#fff;transform:translateY(-14px);background:var(--brand);box-shadow:0 10px 24px -8px var(--p),0 0 0 4px #fff}
.pbn-mid span{display:none}
body{padding-bottom:calc(86px + env(safe-area-inset-bottom,0px))!important}
@media(min-width:900px){#pub-bnav{display:none}body{padding-bottom:0!important}}
</style>
<nav id="pub-bnav" aria-label="Quick links">
  <a href="#hero" class="pbn"><?= ic('home') ?><span>Home</span></a>
  <a href="<?= h(url('modules/events.php')) ?>" class="pbn"><?= ic('calendar') ?><span>Events</span></a>
  <?php if($_pLoggedIn): ?>
  <a href="<?= h(url('dashboard.php')) ?>" class="pbn pbn-mid" aria-label="Dashboard"><?= ic('layout') ?><span>Dashboard</span></a>
  <?php else: ?>
  <button type="button" class="pbn pbn-mid" onclick="openModal('login')" aria-label="Member login"><?= ic('login') ?><span>Login</span></button>
  <?php endif; ?>
  <button type="button" class="pbn" id="pwaNavBtn" onclick="pwaNavInstall()"><?= ic('install') ?><span>Install</span></button>
  <a href="<?= h(url('modules/market.php')) ?>" class="pbn"><?= ic('store') ?><span>Market</span></a>
</nav>

<!-- Install Sheet - iOS + Android -->
<div id="iosSheet" role="dialog" aria-modal="true" aria-label="Install the app" onclick="if(event.target===this)this.classList.remove('open')">
  <div style="background:#fff;width:100%;max-width:480px;border-radius:24px 24px 0 0;padding-bottom:env(safe-area-inset-bottom,16px);overflow:hidden">

    <!-- Handle -->
    <div style="display:flex;justify-content:center;padding:.7rem 0 0">
      <div style="width:40px;height:4px;background:#e0e0e0;border-radius:4px"></div>
    </div>

    <!-- App card -->
    <div style="display:flex;align-items:center;gap:.85rem;padding:1rem 1.2rem .8rem">
      <img src="/assets/logo.jpg" alt="" width="60" height="60" style="width:60px;height:60px;border-radius:14px;object-fit:cover;box-shadow:0 3px 10px rgba(0,0,0,.15);flex-shrink:0">
      <div>
        <div style="font-size:1.1rem;font-weight:800;color:#07225c">Aishwarya</div>
        <div style="font-size:.72rem;color:#64748b">Aishwarya Arts &amp; Sports Club</div>
        <div style="font-size:.65rem;color:#5d6b80;margin-top:.1rem">mynamecc.online</div>
      </div>
    </div>

    <div style="height:1px;background:#f0f0f0;margin:0 1.2rem"></div>

    <!-- iOS steps -->
    <div id="stepsIos" style="padding:.9rem 1.2rem">
      <div style="font-size:.8rem;font-weight:800;color:#1a1a1a;margin-bottom:.7rem">📱 iPhone / iPad — 3 easy steps:</div>

      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#f8faff;border-radius:12px;margin-bottom:.45rem;border:1.5px solid #07225c">
        <div style="width:36px;height:36px;background:#07225c;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0">1️⃣</div>
        <div>
          <div style="font-size:.82rem;font-weight:800;color:#07225c">Tap Share ⬆️</div>
          <div style="font-size:.65rem;color:#64748b">The square with arrow — Safari bottom bar</div>
        </div>
        <span style="font-size:1.3rem;margin-left:auto">⬆️</span>
      </div>

      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#f8faff;border-radius:12px;margin-bottom:.45rem;border:1.5px solid #1565c0">
        <div style="width:36px;height:36px;background:#1565c0;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0">2️⃣</div>
        <div>
          <div style="font-size:.82rem;font-weight:800;color:#1565c0">Add to Home Screen</div>
          <div style="font-size:.65rem;color:#64748b">Scroll down in the menu &amp; tap it</div>
        </div>
        <span style="font-size:1.3rem;margin-left:auto">➕</span>
      </div>

      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#e8f5e9;border-radius:12px;margin-bottom:.7rem;border:1.5px solid #2e7d32">
        <div style="width:36px;height:36px;background:#2e7d32;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0">3️⃣</div>
        <div>
          <div style="font-size:.82rem;font-weight:800;color:#2e7d32">Tap Add — Installed! 🎉</div>
          <div style="font-size:.65rem;color:#64748b">App icon saved to home screen</div>
        </div>
        <span style="font-size:1.3rem;margin-left:auto">✅</span>
      </div>

      <!-- Animated bounce arrow pointing down to Safari toolbar -->
      <div style="text-align:center;margin-top:.3rem">
        <div style="font-size:2rem;animation:bounce 1s infinite">⬇️</div>
        <div style="font-size:.72rem;color:#e65100;font-weight:700;background:#fff3e0;display:inline-block;padding:.3rem .8rem;border-radius:20px;border:1px solid #ffe082">
          Tap the Share button in Safari below
        </div>
      </div>
      <style>@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(6px)}}</style>
    </div>

    <!-- Android steps -->
    <div id="stepsAndroid" style="padding:.9rem 1.2rem;display:none">
      <div style="font-size:.8rem;font-weight:800;color:#1a1a1a;margin-bottom:.7rem">🤖 Android — How to install:</div>
      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#f8faff;border-radius:12px;margin-bottom:.45rem;border:1px solid #e8ecf4">
        <div style="width:32px;height:32px;background:#07225c;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">⋮</div>
        <div><div style="font-size:.78rem;font-weight:700;color:#1a1a1a">Tap ⋮ menu in Chrome</div><div style="font-size:.65rem;color:#64748b">Top right corner of browser</div></div>
      </div>
      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#f8faff;border-radius:12px;margin-bottom:.45rem;border:1px solid #e8ecf4">
        <div style="width:32px;height:32px;background:#1565c0;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">📲</div>
        <div><div style="font-size:.78rem;font-weight:700;color:#1a1a1a">Tap "Add to Home screen"</div><div style="font-size:.65rem;color:#64748b">Or "Install app" if shown</div></div>
      </div>
      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#e8f5e9;border-radius:12px;margin-bottom:.8rem;border:1px solid #c8e6c9">
        <div style="width:32px;height:32px;background:#2e7d32;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">✅</div>
        <div><div style="font-size:.78rem;font-weight:700;color:#1a1a1a">Tap "Add" — Done!</div><div style="font-size:.65rem;color:#64748b">App appears on home screen</div></div>
      </div>
    </div>

    <div style="padding:0 1.2rem .9rem">
      <button type="button" onclick="document.getElementById('iosSheet').classList.remove('open')" style="width:100%;min-height:44px;padding:.62rem;background:#f1f5f9;border:none;border-radius:12px;font-size:.85rem;font-weight:700;cursor:pointer;color:#555">
        Maybe Later
      </button>
    </div>

  </div>
</div>

<script>
// Capture install prompt early
window._pwaPrompt = null;
window.addEventListener('beforeinstallprompt', function(e){
  e.preventDefault();
  window._pwaPrompt = e;
});

// Hide button if already installed as app
(function(){
  var standalone = window.navigator.standalone===true ||
                   window.matchMedia('(display-mode: standalone)').matches;
  if(standalone){
    var b=document.getElementById('pwaNavBtn');
    if(b) b.style.display='none';
  }
})();

function pwaNavInstall(){
  var isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);

  if(!isIos && window._pwaPrompt){
    // Android Chrome — DIRECT native install, no sheet needed
    window._pwaPrompt.prompt();
    window._pwaPrompt.userChoice.then(function(r){
      window._pwaPrompt = null;
      if(r.outcome==='accepted'){
        document.getElementById('pwaNavBtn').style.display='none';
      } else {
        // User said no — show manual sheet as fallback
        showInstallSheet(false);
      }
    });
    return; // Don't show sheet, prompt handles it
  }

  // iOS or Android without prompt — show sheet
  showInstallSheet(isIos);
}

function showInstallSheet(isIos){
  var stepsIos = document.getElementById('stepsIos');
  var stepsAnd = document.getElementById('stepsAndroid');
  if(stepsIos) stepsIos.style.display = isIos ? 'block' : 'none';
  if(stepsAnd) stepsAnd.style.display = isIos ? 'none' : 'block';
  var sh = document.getElementById('iosSheet');
  sh.classList.add('open');
  var b = sh.querySelector('button'); if (b) setTimeout(function(){ b.focus(); }, 50);
}
</script>
<!-- ══ /PUBLIC BOTTOM NAV ══ -->
<script>
// ── PWA ──
if('serviceWorker' in navigator){
  window.addEventListener('load',function(){
    navigator.serviceWorker.register('/sw.js')
      .catch(function(){});
  });
}
// Capture install prompt (Android Chrome)
window._pwaPrompt=null;
window.addEventListener('beforeinstallprompt',function(e){
  e.preventDefault();
  window._pwaPrompt=e;
  var btn=document.getElementById('pwaInstallBtn');
  if(btn){btn.style.display='flex';}
});
// iOS hint
(function(){
  var isIos=/iphone|ipad|ipod/i.test(navigator.userAgent.toLowerCase());
  var isStandalone=window.navigator.standalone===true;
  if(isIos&&!isStandalone){
    var hint=document.getElementById('pwaIosHint');
    if(hint) hint.style.display='block';
  }
})();
function pwaInstall(){
  if(window._pwaPrompt){
    window._pwaPrompt.prompt();
    window._pwaPrompt.userChoice.then(function(r){
      window._pwaPrompt=null;
      if(r.outcome==='accepted'){
        var btn=document.getElementById('pwaInstallBtn');
        if(btn) btn.style.display='none';
      }
    });
  }
}
</script>
</body>
</html>
