<?php
// ================================================================
// index.php — Public Homepage  |  PHP 7.3 + MySQL 5.7 safe
// ================================================================
require_once __DIR__ . '/includes/config.php';
require_once __DIR__ . '/includes/whatsapp_otp.php';
require_once __DIR__ . '/includes/wa_gateway.php';
require_once __DIR__ . '/includes/lang.php';
require_once __DIR__ . '/includes/og.php';
require_once __DIR__ . '/includes/site_schema.php';
lang_current();

// Find a member by phone number however it was typed or stored
function _homeFindUser($raw) {
    $st = db()->prepare('SELECT * FROM users WHERE whatsapp_number=?');
    $st->execute(array(normalisePhone($raw))); $row = $st->fetch();
    if ($row) return $row;
    $d = substr(preg_replace('/\D/', '', (string)$raw), -10);
    if (strlen($d) < 10) return null;
    $st = db()->prepare("SELECT * FROM users WHERE whatsapp_number LIKE ?");
    $st->execute(array('%' . $d));
    foreach ($st->fetchAll() as $u) { if (substr(preg_replace('/\D/', '', $u['whatsapp_number']), -10) === $d) return $u; }
    return null;
}

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
        $row = _homeFindUser($_POST['phone'] ?? '');
        if (!$row) { echo json_encode(array('ok'=>false,'msg'=>'Phone number not registered.')); exit; }
        if ($row['status']!=='active')  { echo json_encode(array('ok'=>false,'msg'=>'Account is not active yet.')); exit; }
        if (wa_feature_on('otp')) {
            // Verified by a code sent to the member's WhatsApp
            if (!wa_otp_check($row['whatsapp_number'], 'passkey', $_POST['otp'] ?? '')) {
                echo json_encode(array('ok'=>false,'msg'=>'Wrong or expired WhatsApp code. Ask for a new code.'));
                exit;
            }
        } elseif (strtolower(trim($row['name'])) !== $name) {
            // Verify name for security (when WhatsApp codes are not set up)
            echo json_encode(array('ok'=>false,'msg'=>'Name does not match our records.'));
            exit;
        }
        $hash = password_hash($key, PASSWORD_DEFAULT);
        db()->prepare('UPDATE users SET passkey=?,passkey_set=1 WHERE id=?')->execute(array($hash,$row['id']));
        // Auto-login after setting passkey
        if (function_exists('session_regenerate_id')) @session_regenerate_id(true);
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
            'wa_otp'      => wa_feature_on('otp'),
            'name_hint'   => mb_strtoupper(mb_substr($row['name'],0,1)).'***',
        ));
        exit;
    }

    // ── WhatsApp code: send (login or passkey reset) ───────────────
    if ($act === 'send_otp') {
        $purpose = (($_POST['purpose'] ?? '') === 'passkey') ? 'passkey' : 'login';
        if (!wa_feature_on('otp')) { echo json_encode(array('ok'=>false,'msg'=>'WhatsApp codes are not set up yet. Ask the club admin.')); exit; }
        $row = _homeFindUser($_POST['phone'] ?? '');
        if (!$row) { echo json_encode(array('ok'=>false,'msg'=>'Phone number not registered.')); exit; }
        if ($row['status'] !== 'active') { echo json_encode(array('ok'=>false,'msg'=>'Account is not active yet. Contact the Secretary.')); exit; }
        list($ok, $m) = wa_otp_send($row['whatsapp_number'], $purpose);
        echo json_encode(array('ok'=>$ok, 'msg'=>$m)); exit;
    }

    // ── WhatsApp code: log in ───────────────────────────────────────
    if ($act === 'login_otp') {
        if (!wa_feature_on('otp')) { echo json_encode(array('ok'=>false,'msg'=>'WhatsApp codes are not set up.')); exit; }
        $row = _homeFindUser($_POST['phone'] ?? '');
        if (!$row || $row['status'] !== 'active' || !wa_otp_check($row['whatsapp_number'], 'login', $_POST['otp'] ?? '')) {
            echo json_encode(array('ok'=>false,'msg'=>'Wrong or expired code. Try again or ask for a new code.')); exit;
        }
        if (function_exists('session_regenerate_id')) @session_regenerate_id(true);
        $_SESSION['user_id'] = $row['id'];
        echo json_encode(array('ok'=>true,'url'=>url('dashboard.php'))); exit;
    }

    // ── "Join the club" enquiry from the public website ───────────
    if ($act === 'enquiry') {
        site_tables();
        // spam: hidden honeypot field must stay empty; pretend success for bots
        if (trim($_POST['website'] ?? '') !== '') { echo json_encode(array('ok'=>true,'wa'=>'')); exit; }
        $name  = mb_substr(trim($_POST['name'] ?? ''), 0, 150);
        $place = mb_substr(trim($_POST['place'] ?? ''), 0, 150);
        $phone = preg_replace('/\D/', '', $_POST['phone'] ?? '');
        $int   = mb_substr(trim($_POST['interest'] ?? ''), 0, 150);
        if ($name === '') { echo json_encode(array('ok'=>false,'msg'=>t('form_err_name'))); exit; }
        if (strlen($phone) === 12 && substr($phone, 0, 2) === '91') $phone = substr($phone, 2);
        if (strlen($phone) !== 10) { echo json_encode(array('ok'=>false,'msg'=>t('form_err_phone'))); exit; }
        $ip = $_SERVER['REMOTE_ADDR'] ?? '';
        $c = db()->prepare("SELECT COUNT(*) FROM enquiries WHERE ip=? AND created_at > (NOW() - INTERVAL 1 HOUR)"); $c->execute(array($ip));
        if ((int)$c->fetchColumn() >= 5) { echo json_encode(array('ok'=>false,'msg'=>t('form_err_limit'))); exit; }
        db()->prepare("INSERT INTO enquiries(name,place,phone,interest,ip) VALUES(?,?,?,?,?)")->execute(array($name, $place, '+91' . $phone, $int, $ip));
        $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
        $msg = "Hello {$club}, I would like to join the club.\n\nName: {$name}\nPlace: {$place}\nWhatsApp: +91 {$phone}" . ($int !== '' ? "\nInterested in: {$int}" : '');
        $to = site_whatsapp();
        echo json_encode(array('ok'=>true,'wa'=> $to ? 'https://wa.me/' . $to . '?text=' . rawurlencode($msg) : ''));
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
// ── Public website data (Admin → Public Website edits all of this) ──
site_tables();
$P = function($k, $d = '') { return site_cfg($k, $d); };
$Pml = function($k, $d = '') { return tset(site_cfg($k, $d), site_cfg($k . '_ml', '')); };   // English / Malayalam text
$Pon = function($k) {                                                                         // section switch (falls back to the old Homepage switches)
    $old = array('about'=>'home_about_show','programs'=>'home_activities_show','achievements'=>'home_achievements_show','gallery'=>'home_gallery_show',
                 'events'=>'home_events_show','notices'=>'home_notices_show','committee'=>'home_committee_show');
    $v = site_cfg('pub_show_' . $k, '');
    if ($v === '' && isset($old[$k])) $v = site_cfg($old[$k], '1');
    return $v !== '0';
};
$Ptitle = function($k) use ($Pml) { $v = $Pml('pub_title_' . $k, ''); return $v !== '' ? $v : t('sec_' . $k); };
$heroPhoto = $P('hero_photo', '');
if ($heroPhoto === '' && !empty($heroSlides[0]['img'])) $heroPhoto = $heroSlides[0]['img'];
elseif ($heroPhoto !== '') $heroPhoto = url($heroPhoto);
$heroTitleP = $Pml('hero_title', $clubName);
$heroSubP   = $Pml('hero_subtitle', $clubTag);
$aboutPts   = array_values(array_filter(array_map('trim', explode("\n", $Pml('about_points',
    "Football, cricket and sports for all ages\nArts festival, Onam and cultural programs\nBlood donors ready to help in emergencies\nCharity and help for families in need")))));
$programs = array();
try { $programs = db()->query("SELECT * FROM club_activities WHERE is_active=1 ORDER BY sort_order,id")->fetchAll(); } catch(Exception $e){}
$pubAch2 = array_values(array_filter($pubAch, function($a){ return !isset($a['show_public']) || (int)$a['show_public'] === 1; }));
$galPub = array();
try { $galPub = db()->query("SELECT * FROM gallery_images WHERE is_active=1 AND (show_public IS NULL OR show_public=1) ORDER BY sort_order,created_at DESC LIMIT 12")->fetchAll(); } catch(Exception $e){}
$packages = array();
try { $packages = db()->query("SELECT * FROM site_packages WHERE is_active=1 ORDER BY sort_order,id")->fetchAll(); } catch(Exception $e){}
if (empty($packages)) {
    $packages = array(
        array('name'=>'Monthly','price'=>'₹'.number_format((int)setting('FEE_MONTHLY', 100)),'duration'=>t('per_month'),'note'=>'Full club access','popular'=>0),
        array('name'=>'Annual','price'=>'₹'.number_format((int)setting('FEE_ANNUAL', 1000)),'duration'=>t('per_year'),'note'=>'Best value · priority entry','popular'=>1),
    );
}
$timings = array(); $rules = array();
try { $timings = db()->query("SELECT * FROM site_timings ORDER BY sort_order,id")->fetchAll(); } catch(Exception $e){}
try { $rules = db()->query("SELECT * FROM site_rules ORDER BY sort_order,id")->fetchAll(); } catch(Exception $e){}
$products = array();
try {
    $products = db()->query("SELECT m.* FROM market_items m WHERE m.status='active' AND (m.show_public IS NULL OR m.show_public=1) ORDER BY m.featured DESC, m.created_at DESC LIMIT 8")->fetchAll();
    foreach ($products as &$pr) {
        $st = db()->prepare("SELECT image_path FROM market_images WHERE item_id=? ORDER BY sort_order,id LIMIT 6"); $st->execute(array($pr['id']));
        $pr['imgs'] = array_map(function($r){ $ip = ltrim($r['image_path'], '/'); return url('assets/uploads/' . (strpos($ip, '/') === false ? 'market/' . $ip : $ip)); }, $st->fetchAll());
    }
    unset($pr);
} catch(Exception $e){}
$siteWa    = site_whatsapp();
$sitePhone = preg_replace('/[^\d+]/', '', $P('site_phone', setting('CLUB_PHONE', '')));
$siteAddr  = $Pml('site_address', $clubPlace . ', Kerala');
$siteMap   = $P('site_map', '');
$siteInsta = $P('social_instagram', '');
$joinOptions = array_values(array_filter(array_map('trim', explode(',', $Pml('join_options', 'Football,Cricket,Arts,Blood donor,Volunteer')))));
$userNow   = $_pLoggedIn ? currentUser() : null;
$isAdminNow = $userNow && isAdminRole($userNow['role']);
// price text: "500" → "₹500"; "₹500 or Free" stays as written; empty → on request
$num   = function($v){ return (float)preg_replace('/[^\d.]/', '', (string)$v); };
$money = function($v){ $v = trim((string)$v); if ($v === '') return 'On request'; return is_numeric($v) ? '₹' . number_format((float)$v, (floor($v) == $v) ? 0 : 2) : $v; };
?>
<!DOCTYPE html>
<html lang="<?= lang_current() ?>">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title><?= h($clubName . ' · ' . $clubPlace) ?></title>
<?= og_tags() ?>
<link rel="manifest" href="<?= url('manifest.php') ?>">
<meta name="theme-color" content="#0B1033">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aishwarya">
<link rel="apple-touch-icon" href="<?= url('assets/icons/app/apple-touch-icon.png') ?>">
<link rel="icon" type="image/png" href="<?= url('assets/icons/app/favicon-64.png') ?>">
<link rel="stylesheet" href="<?= url('assets/vendor/bootstrap/css/bootstrap.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/vendor/bootstrap-icons/bootstrap-icons.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/vendor/fontawesome/css/all.min.css') ?>">
<link rel="stylesheet" href="<?= url('assets/css/club.css') ?>?v=5">
<style>
/* login pop-up (logic unchanged; classes renamed so they don't clash with Bootstrap) */
.overlay{display:none;position:fixed;inset:0;z-index:2000;background:rgba(5,8,25,.7);align-items:flex-end;justify-content:center}
.overlay.show{display:flex}
.lgn{background:var(--dark);color:#fff;width:100%;max-width:440px;border-radius:1.2rem 1.2rem 0 0;box-shadow:var(--sh-dark);overflow:hidden;max-height:94vh;display:flex;flex-direction:column;padding-bottom:env(safe-area-inset-bottom,0px);border:1px solid rgba(255,255,255,.08)}
@media(min-width:600px){.overlay{align-items:center;padding:1rem}.lgn{border-radius:1.2rem}}
.lgn-bar{height:5px;width:44px;border-radius:5px;background:rgba(255,255,255,.25);margin:.6rem auto 0;flex-shrink:0}
.lgn-head{display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.2rem .6rem}
.lgn-head h3{font-weight:900;text-transform:uppercase;font-style:italic;font-size:1.2rem;margin:0}
.lgn-x{background:rgba(255,255,255,.08);border:0;width:44px;height:44px;border-radius:.8rem;color:#fff;display:flex;align-items:center;justify-content:center}
.lgn-tabs{display:flex;gap:.3rem;margin:0 1.2rem;padding:.3rem;background:var(--page-dark);border-radius:2rem}
.mtab{flex:1;min-height:44px;border:0;border-radius:2rem;background:none;font-weight:700;font-size:.9rem;color:var(--muted)}
.mtab.on{background:var(--brand);color:#fff}
.lgn-body{padding:1.1rem 1.2rem 1.3rem;overflow-y:auto}
.mpanel{display:none}.mpanel.on{display:block}
.flbl{font-size:.85rem;font-weight:700;display:block;margin-bottom:.35rem}
.finp{width:100%;min-height:52px;background:var(--page-dark);border:1.5px solid rgba(255,255,255,.15);border-radius:.8rem;padding:.7rem 1rem;font-size:1rem;color:#fff;margin-bottom:.9rem}
.finp:focus{outline:none;border-color:var(--accent-text);box-shadow:0 0 0 .2rem rgba(143,151,255,.25)}
.finp::placeholder{color:#8d8a8a}
select.finp option{color:#000}
.frow{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
.fbtn{width:100%;min-height:52px;border:0;border-radius:.6rem;font-weight:800;font-size:1rem;display:flex;align-items:center;justify-content:center;gap:.5rem}
.fbtn-p{background:var(--brand);color:#fff;box-shadow:0 8px 24px -8px rgba(227,6,19,.8)}
.fbtn-g{background:var(--wa);color:#0B1033}
.fbtn:disabled{opacity:.55}
.fmsg{border-radius:.7rem;padding:.7rem .95rem;font-size:.9rem;margin-bottom:.9rem;display:none}
.fmsg.ok{display:block;background:rgba(21,128,61,.18);border:1px solid rgba(21,128,61,.6);color:#c8f5d6}
.fmsg.err{display:block;background:rgba(227,6,19,.15);border:1px solid rgba(227,6,19,.6);color:#ffd5d3}
.fhint{font-size:.82rem;color:var(--muted);text-align:center;margin-top:.8rem}
.fback{background:none;border:0;color:var(--muted);font-weight:700;font-size:.88rem;min-height:40px;margin-bottom:.4rem}
.success-panel{text-align:center;padding:.5rem 0 .8rem}.success-em{font-size:3rem;margin-bottom:.6rem}
.num-keypad{display:grid;grid-template-columns:repeat(3,1fr);gap:.55rem;max-width:300px;margin:0 auto}
.num-keypad button{background:var(--page-dark);border:1px solid rgba(255,255,255,.12);border-radius:1rem;min-height:58px;font-size:1.35rem;font-weight:800;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1}
.num-keypad button:active{background:var(--brand)}
.num-keypad button span{font-size:.75rem;letter-spacing:.1em;color:var(--muted);margin-top:.15rem}
.num-keypad .pk-del{color:var(--brand-text)}
.num-keypad .pk-ok{background:var(--brand);border-color:var(--brand)}
.pk-dot{width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,.2)}
.pk-dot.filled{background:#fff}.pk-dot.err{background:var(--brand)}
@keyframes pkShake{0%,100%{transform:translateX(0)}25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}
#iosSheet{display:none;position:fixed;inset:0;z-index:2100;background:rgba(5,8,25,.6);align-items:flex-end;justify-content:center;color:#0B1033}
#iosSheet.open{display:flex}
#iosSheet>div{max-height:92vh;overflow-y:auto}
.lgn{--p:var(--brand);--p-soft:rgba(227,6,19,.25);--t2:var(--muted);--t3:var(--muted);--tx:#fff;--line:rgba(255,255,255,.15)}
.otp-wrap{display:flex;gap:.4rem;justify-content:center;margin:.6rem 0 1.1rem}
.otp-cell{width:46px;height:54px;background:var(--page-dark);border:1.5px solid rgba(255,255,255,.15);border-radius:.8rem;text-align:center;font-size:1.3rem;font-weight:800;color:#fff;outline:none}
.otp-cell:focus{border-color:var(--accent-text)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
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
</script>
</head>
<body class="pub" data-bs-no-jquery>
<?= icon_sprite() ?>
<a href="#main" class="skip-link">Skip to content</a>
<?php include 'av-splash.php'; ?>

<!-- ══ TOP BAR ══ -->
<header class="pub-top">
  <div class="in">
    <a href="#top" class="d-flex align-items-center gap-2 text-decoration-none" aria-label="<?= h($clubName) ?> — top of page">
      <?php if($logo): ?><img class="logo" src="<?= $logo ?>" alt="" width="44" height="44"><?php endif; ?>
      <span class="d-none d-sm-block"><span class="name d-block"><?= h($clubName) ?></span><span class="sub"><?= h($clubPlace) ?> · Kerala</span></span>
    </a>
    <nav class="d-none d-lg-flex ms-3" aria-label="Sections">
      <?php if($Pon('programs') && $programs): ?><a href="#programs"><?= h($Ptitle('programs')) ?></a><?php endif; ?>
      <?php if($Pon('events')): ?><a href="#events"><?= h($Ptitle('events')) ?></a><?php endif; ?>
      <?php if($Pon('fees')): ?><a href="#fees"><?= h($Ptitle('fees')) ?></a><?php endif; ?>
      <?php if($Pon('contact')): ?><a href="#contact"><?= h($Ptitle('contact')) ?></a><?php endif; ?>
    </nav>
    <a class="lang" href="<?= h(lang_url(lang_current() === 'ml' ? 'en' : 'ml')) ?>" lang="<?= lang_current() === 'ml' ? 'en' : 'ml' ?>" aria-label="<?= h(t('lang_label')) ?>"><i class="bi bi-translate" aria-hidden="true"></i><?= h(t('lang_switch')) ?></a>
  </div>
</header>

<main id="main" tabindex="-1">
<!-- ══ 1. HERO ══ -->
<section class="hero-pub" id="top" aria-labelledby="heroH">
  <div class="wrap">
    <div class="hero-photo">
      <?php if($heroPhoto): ?><img src="<?= h($heroPhoto) ?>" alt="<?= h($clubName) ?>" width="1200" height="750" fetchpriority="high">
      <?php elseif($logo): ?><img src="<?= $logo ?>" alt="<?= h($clubName) ?>" width="640" height="400" style="object-fit:contain;padding:1.5rem;background:#fff"><?php endif; ?>
    </div>
    <h1 class="h-big" id="heroH"><?= h($heroTitleP) ?></h1>
    <p class="lead2"><?= h($heroSubP) ?></p>
    <div class="hero-btns">
      <button type="button" class="btn btn-brand btn-lg btn-glow" data-bs-toggle="modal" data-bs-target="#mJoin"><i class="bi bi-person-plus-fill" aria-hidden="true"></i><?= h(t('hero_join')) ?></button>
      <div class="row2">
        <?php if($siteWa): ?><a class="btn btn-line" href="https://wa.me/<?= h($siteWa) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp" aria-hidden="true"></i><?= h(t('hero_whatsapp')) ?></a><?php endif; ?>
        <?php if($sitePhone): ?><a class="btn btn-line" href="tel:<?= h($sitePhone) ?>"><i class="bi bi-telephone-fill" aria-hidden="true"></i><?= h(t('hero_call')) ?></a><?php endif; ?>
      </div>
    </div>
  </div>
</section>

<?php if($Pon('about') && $aboutPts): ?>
<!-- ══ 2. ABOUT ══ -->
<section aria-labelledby="aboutH"><div class="wrap">
  <h2 class="h-sec" id="aboutH"><?= h($Ptitle('about')) ?></h2>
  <ul class="pt-list">
    <?php foreach($aboutPts as $pt): ?><li class="pt-box"><i class="bi bi-check-circle-fill" aria-hidden="true"></i><span><?= h($pt) ?></span></li><?php endforeach; ?>
  </ul>
</div></section>
<?php endif; ?>

<?php if($Pon('programs') && $programs): ?>
<!-- ══ 3. PROGRAMS ══ -->
<section class="sec-alt" id="programs" aria-labelledby="progH"><div class="wrap">
  <h2 class="h-sec" id="progH"><?= h($Ptitle('programs')) ?></h2>
  <div class="pgrid">
    <?php foreach($programs as $i => $pg): $pName = tset($pg['name'], $pg['name_ml'] ?? ''); $pDesc = tset($pg['description'] ?? '', $pg['description_ml'] ?? ''); ?>
    <button type="button" class="pcard" data-prog="<?= $i ?>" aria-label="<?= h($pName) ?> — <?= h(t('more_details')) ?>">
      <span class="ph d-block">
        <?php if(!empty($pg['photo'])): ?><img src="<?= h(url($pg['photo'])) ?>" alt="" loading="lazy" width="400" height="400"><?php else: ?><span class="em" aria-hidden="true"><?= h($pg['emoji'] ?: '🏆') ?></span><?php endif; ?>
        <span class="nm"><?= h($pName) ?></span>
      </span>
      <span class="bd d-block"><?php if($pDesc): ?><p><?= h($pDesc) ?></p><?php endif; ?><span class="more"><?= h(t('more_details')) ?> →</span></span>
    </button>
    <?php endforeach; ?>
  </div>
</div></section>
<?php endif; ?>

<?php
// sliders: achievements (gold), gallery, events
$sliders = array();
if ($Pon('achievements') && $pubAch2) {
  $medal = array('gold'=>'🥇','silver'=>'🥈','bronze'=>'🥉');
  $sliders['achievements'] = array('gold', array_map(function($a) use ($medal) {
    $img = ''; if (!empty($a['image'])) $img = (strpos($a['image'],'/')!==false) ? url('assets/uploads/'.$a['image']) : url('assets/uploads/achievements/'.$a['image']);
    return array('t'=>$a['title'], 's'=>trim(($a['member_name'] ?? '') . (!empty($a['achievement_date']) ? ' · '.date('M Y', strtotime($a['achievement_date'])) : ''), ' ·'),
                 'd'=>$a['description'] ?? '', 'img'=>$img, 'em'=>isset($medal[$a['medal_type'] ?? '']) ? $medal[$a['medal_type']] : '🏆', 'tag'=>ucfirst($a['medal_type'] ?? ''));
  }, $pubAch2));
}
if ($Pon('gallery') && $galPub) {
  $sliders['gallery'] = array('', array_map(function($g){ return array('t'=>$g['title'] ?: 'Photo', 's'=>ucfirst($g['category'] ?? ''), 'd'=>'', 'img'=>url('assets/uploads/'.$g['image_path']), 'em'=>'📷', 'tag'=>''); }, $galPub));
}
if ($Pon('events') && $upEvents) {
  $sliders['events'] = array('', array_map(function($e){
    $d = (int)ceil((strtotime($e['event_date'])-strtotime('today'))/86400);
    return array('t'=>$e['title'], 's'=>date('D, d M Y', strtotime($e['event_date'])).(!empty($e['event_time'])?' · '.$e['event_time']:'').(!empty($e['location'])?' · '.$e['location']:''),
                 'd'=>$e['description'] ?? '', 'img'=>!empty($e['thumbnail']) ? url('assets/uploads/events/'.$e['thumbnail']) : '', 'em'=>'📅',
                 'tag'=>$d===0 ? t('today') : ($d===1 ? t('tomorrow') : sprintf(t('days_left'), $d)));
  }, array_slice($upEvents, 0, 9)));
}
$slJson = array();
foreach ($sliders as $key => $sl): $slJson[$key] = $sl[1]; ?>
<!-- ══ 4. <?= strtoupper($key) ?> ══ -->
<section<?= $key==='gallery' ? ' class="sec-alt"' : '' ?> id="<?= $key ?>" aria-labelledby="h_<?= $key ?>"><div class="wrap">
  <h2 class="h-sec" id="h_<?= $key ?>"<?= $sl[0]==='gold' ? ' style="--brand:var(--gold)"' : '' ?>><?= h($Ptitle($key)) ?></h2>
  <div class="sl <?= $sl[0] ?>" data-slider>
    <div class="sl-track" tabindex="0" role="region" aria-label="<?= h($Ptitle($key)) ?>">
      <?php foreach($sl[1] as $j => $it): ?>
      <button type="button" class="sl-card" data-item="<?= $key ?>:<?= $j ?>">
        <span class="ph d-block"><?php if($it['img']): ?><img src="<?= h($it['img']) ?>" alt="" loading="lazy" width="600" height="450"><?php else: ?><span class="em" aria-hidden="true"><?= $it['em'] ?></span><?php endif; ?></span>
        <span class="bd d-block">
          <?php if($it['tag']): ?><small class="tag fw-bold text-uppercase" style="color:<?= $sl[0]==='gold' ? 'var(--gold)' : 'var(--brand-text)' ?>"><?= h($it['tag']) ?></small><?php endif; ?>
          <b><?= h($it['t']) ?></b><?php if($it['s']): ?><small><?= h($it['s']) ?></small><?php endif; ?>
        </span>
      </button>
      <?php endforeach; ?>
    </div>
    <?php if(count($sl[1]) > 1): ?>
    <div class="sl-ctrl">
      <button type="button" class="sl-arrow" data-dir="-1" aria-label="<?= h(t('previous')) ?>"><i class="bi bi-chevron-left" aria-hidden="true"></i></button>
      <div class="sl-dots" aria-hidden="true"><?php foreach($sl[1] as $j => $it): ?><span class="sl-dot<?= $j===0?' on':'' ?>"></span><?php endforeach; ?></div>
      <button type="button" class="sl-arrow" data-dir="1" aria-label="<?= h(t('next')) ?>"><i class="bi bi-chevron-right" aria-hidden="true"></i></button>
    </div>
    <?php endif; ?>
  </div>
</div></section>
<?php endforeach; ?>

<?php if($Pon('fees') && $packages): ?>
<!-- ══ 5. FEES ══ -->
<section id="fees" aria-labelledby="feesH"><div class="wrap">
  <h2 class="h-sec" id="feesH"><?= h($Ptitle('fees')) ?></h2>
  <div class="fgrid">
    <?php foreach($packages as $pk): ?>
    <div class="fee<?= !empty($pk['popular']) ? ' pop' : '' ?>">
      <?php if(!empty($pk['popular'])): ?><span class="badge-pop"><?= h(t('most_popular')) ?></span><?php endif; ?>
      <div class="nm"><?= h($pk['name']) ?></div>
      <div class="pr"><?= h($pk['price']) ?></div>
      <?php if(!empty($pk['duration'])): ?><div class="du"><?= h($pk['duration']) ?></div><?php endif; ?>
      <?php if(!empty($pk['note'])): ?><p><?= h($pk['note']) ?></p><?php endif; ?>
    </div>
    <?php endforeach; ?>
  </div>
  <button type="button" class="btn btn-brand w-100 mt-3" data-bs-toggle="modal" data-bs-target="#mJoin"><?= h(t('join_now')) ?></button>
</div></section>
<?php endif; ?>

<?php if($Pon('timings') && $timings): ?>
<!-- ══ 6. TIMINGS ══ -->
<section class="sec-alt" id="timings" aria-labelledby="tmH"><div class="wrap">
  <h2 class="h-sec" id="tmH"><?= h($Ptitle('timings')) ?></h2>
  <div class="tm">
    <?php foreach($timings as $tm): ?>
    <div class="tm-row"><i class="bi bi-<?= ($tm['icon'] ?? 'sun') === 'moon' ? 'moon-stars-fill' : 'sun-fill' ?>" aria-hidden="true"></i>
      <div><span class="nm"><?= h($tm['name']) ?></span><?php if(!empty($tm['days'])): ?><small><?= h($tm['days']) ?></small><?php endif; ?></div>
      <span class="tt"><?= h($tm['time_text']) ?></span></div>
    <?php endforeach; ?>
  </div>
</div></section>
<?php endif; ?>

<?php if($Pon('rules') && $rules): ?>
<!-- ══ 7. RULES ══ -->
<section id="rules" aria-labelledby="ruH"><div class="wrap">
  <h2 class="h-sec" id="ruH"><?= h($Ptitle('rules')) ?></h2>
  <?php foreach($rules as $ru): $lines = array_values(array_filter(array_map('trim', explode("\n", $ru['body'])))); ?>
  <div class="rule-box"><h3><?= h($ru['title']) ?></h3><ol><?php foreach($lines as $ln): ?><li><?= h($ln) ?></li><?php endforeach; ?></ol></div>
  <?php endforeach; ?>
</div></section>
<?php endif; ?>

<?php if($Pon('shop') && $products): ?>
<!-- ══ 8. SHOP ══ -->
<section class="sec-alt" id="shop" aria-labelledby="shopH"><div class="wrap">
  <h2 class="h-sec" id="shopH"><?= h($Ptitle('shop')) ?></h2>
  <div class="shop-grid">
    <?php foreach($products as $k => $pr): $offer = !empty($pr['old_price']) && $num($pr['price']) > 0 && (float)$pr['old_price'] > $num($pr['price']); ?>
    <button type="button" class="prod" data-prod="<?= $k ?>">
      <?php if($offer): ?><span class="tag-offer"><?= h(t('offer')) ?></span><?php endif; ?>
      <span class="ph d-block"><?php if(!empty($pr['imgs'][0])): ?><img src="<?= h($pr['imgs'][0]) ?>" alt="" loading="lazy" width="400" height="400"><?php else: ?><span class="d-flex h-100 align-items-center justify-content-center fs-1" aria-hidden="true">🛍️</span><?php endif; ?></span>
      <span class="bd d-block"><span class="nm d-block"><?= h($pr['title']) ?></span>
        <span class="price"><?= h($money($pr['price'])) ?><?php if($offer): ?><s><?= h($money($pr['old_price'])) ?></s><?php endif; ?></span></span>
    </button>
    <?php endforeach; ?>
  </div>
  <a class="btn btn-line w-100 mt-3" href="<?= url('modules/market.php') ?>"><?= h(t('see_all')) ?> →</a>
</div></section>
<?php endif; ?>

<?php if($Pon('notices') && !empty($homeNotices)): ?>
<section id="notices" aria-labelledby="ntH"><div class="wrap">
  <h2 class="h-sec" id="ntH"><?= h($Ptitle('notices')) ?></h2>
  <?php foreach(array_slice($homeNotices,0,5) as $hn): $pr = $hn['priority'] ?? 'normal'; ?>
  <div class="nt<?= $pr!=='normal' ? ' urgent' : '' ?>"><b><?= h($hn['title']) ?></b><p><?= h(mb_strimwidth($hn['body'],0,240,'…')) ?></p><small class="text-2"><?= date('d M Y', strtotime($hn['created_at'])) ?></small></div>
  <?php endforeach; ?>
</div></section>
<?php endif; ?>

<?php if($Pon('committee') && !empty($committee)):
  $roleLbl = array('president'=>'President','vice_president'=>'Vice President','secretary'=>'Secretary','joint_secretary'=>'Jt. Secretary','treasurer'=>'Treasurer','committee_member'=>'Committee'); ?>
<section class="sec-alt" id="committee" aria-labelledby="cmH"><div class="wrap">
  <h2 class="h-sec" id="cmH"><?= h($Ptitle('committee')) ?></h2>
  <div class="people">
    <?php foreach($committee as $cm): $ph = !empty($cm['profile_photo']) ? getMemberPhoto($cm['profile_photo']) : ''; ?>
    <div class="person"><?php if($ph): ?><img src="<?= $ph ?>" alt="" loading="lazy"><?php else: ?><span class="ph" aria-hidden="true"><i class="bi bi-person"></i></span><?php endif; ?>
      <b><?= h($cm['name']) ?></b><small><?= h(!empty($cm['committee_position']) ? $cm['committee_position'] : ($roleLbl[$cm['role']] ?? 'Committee')) ?></small></div>
    <?php endforeach; ?>
  </div>
</div></section>
<?php endif; ?>

<?php if($Pon('contact')): ?>
<!-- ══ 9. CONTACT ══ -->
<section id="contact" aria-labelledby="ctH"><div class="wrap">
  <h2 class="h-sec" id="ctH"><?= h($Ptitle('contact')) ?></h2>
  <div class="row g-3">
    <div class="col-lg-5">
      <div class="ct-box">
        <div class="ct-row"><i class="bi bi-geo-alt-fill" aria-hidden="true"></i><div><small class="text-2 d-block"><?= h(t('address')) ?></small><span style="white-space:pre-line"><?= h($siteAddr) ?></span></div></div>
        <?php if($sitePhone): ?><div class="ct-row"><i class="bi bi-telephone-fill" aria-hidden="true"></i><div><small class="text-2 d-block"><?= h(t('phone')) ?></small><a href="tel:<?= h($sitePhone) ?>"><?= h($sitePhone) ?></a></div></div><?php endif; ?>
        <div class="d-grid gap-2 mt-2">
          <?php if($siteWa): ?><a class="btn btn-wa" href="https://wa.me/<?= h($siteWa) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp" aria-hidden="true"></i><?= h(t('hero_whatsapp')) ?></a><?php endif; ?>
          <?php if($sitePhone): ?><a class="btn btn-line" href="tel:<?= h($sitePhone) ?>"><i class="bi bi-telephone" aria-hidden="true"></i><?= h(t('hero_call')) ?></a><?php endif; ?>
          <?php if($siteInsta): ?><a class="btn btn-line" href="<?= h($siteInsta) ?>" target="_blank" rel="noopener"><i class="bi bi-instagram" aria-hidden="true"></i><?= h(t('instagram')) ?></a><?php endif; ?>
          <?php if($siteMap && !preg_match('#/maps/embed#', $siteMap)): ?><a class="btn btn-line" href="<?= h($siteMap) ?>" target="_blank" rel="noopener"><i class="bi bi-map" aria-hidden="true"></i><?= h(t('open_map')) ?></a><?php endif; ?>
        </div>
      </div>
    </div>
    <?php if($siteMap && preg_match('#^https://(www\.)?google\.[a-z.]+/maps/embed#', $siteMap)): ?>
    <div class="col-lg-7"><iframe class="map" src="<?= h($siteMap) ?>" loading="lazy" referrerpolicy="no-referrer-when-downgrade" title="Map: <?= h($clubName) ?>"></iframe></div>
    <?php endif; ?>
  </div>
</div></section>
<?php endif; ?>
</main>

<!-- ══ 10. FOOTER ══ -->
<footer class="pub-foot"><div class="wrap">
  <button type="button" id="pwaNavBtn" class="btn btn-line btn-sm mb-3" onclick="pwaNavInstall()"><i class="bi bi-download" aria-hidden="true"></i>Install app</button><br>
  © <?= date('Y') ?> <?= h($clubName) ?> · <?= h($clubPlace) ?>
  <?php $ft = $Pml('footer_text', ''); if($ft !== ''): ?><br><span style="white-space:pre-line"><?= h($ft) ?></span><?php endif; ?>
  <br><span class="dev"><i class="bi bi-code-slash" aria-hidden="true"></i><?= h(t('developed_by')) ?> <b class="text-white">anexpaikadan</b></span>
</div></footer>

<!-- ══ POP-UPS ══ -->
<div class="modal fade modal-dark" id="mDetail" tabindex="-1" aria-labelledby="mDetailT" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable"><div class="modal-content">
    <div class="modal-header"><h3 class="modal-title fw-bold text-uppercase fst-italic fs-5" id="mDetailT"></h3><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="<?= h(t('close')) ?>"></button></div>
    <div class="modal-body" id="mDetailB"></div>
    <div class="modal-footer" id="mDetailF"></div>
  </div></div>
</div>

<div class="modal fade modal-dark" id="mJoin" tabindex="-1" aria-labelledby="mJoinT" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-fullscreen-sm-down"><div class="modal-content">
    <div class="modal-header"><h3 class="modal-title fw-bold text-uppercase fst-italic fs-5" id="mJoinT"><?= h(t('form_title')) ?></h3><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="<?= h(t('close')) ?>"></button></div>
    <div class="modal-body">
      <form id="joinForm" novalidate>
        <p class="text-2 small"><?= h(t('form_sub')) ?></p>
        <div class="alert alert-danger py-2 d-none" id="joinErr" role="alert"></div>
        <div class="mb-3"><label class="form-label" for="jName"><?= h(t('form_name')) ?> *</label><input class="form-control" id="jName" name="name" autocomplete="name" required></div>
        <div class="mb-3"><label class="form-label" for="jPlace"><?= h(t('form_place')) ?></label><input class="form-control" id="jPlace" name="place" autocomplete="address-level2"></div>
        <div class="mb-3"><label class="form-label" for="jPhone"><?= h(t('form_whatsapp')) ?> *</label><input class="form-control" id="jPhone" name="phone" type="tel" inputmode="numeric" autocomplete="tel-national" maxlength="14" placeholder="98765 43210" required></div>
        <div class="hp" aria-hidden="true"><label for="jWeb">Website</label><input id="jWeb" name="website" tabindex="-1" autocomplete="off"></div>
        <?php if($joinOptions): ?>
        <fieldset class="mb-3"><legend class="form-label"><?= h(t('form_interest')) ?></legend>
          <div class="d-flex flex-wrap gap-2" id="jChips"><?php foreach($joinOptions as $op): ?><button type="button" class="chip" aria-pressed="false" data-v="<?= h($op) ?>"><?= h($op) ?></button><?php endforeach; ?></div>
        </fieldset>
        <?php endif; ?>
        <button type="submit" class="btn btn-brand btn-lg w-100" id="jSend"><i class="bi bi-send-fill" aria-hidden="true"></i><?= h(t('form_send')) ?></button>
        <?php if(!$_pLoggedIn): ?><button type="button" class="btn btn-link w-100 mt-2 text-white" onclick="bootstrap.Modal.getInstance(document.getElementById('mJoin')).hide();openModal('login')"><?= h(t('form_member_login')) ?></button><?php endif; ?>
      </form>
      <div class="thanks d-none" id="joinThanks" role="status">
        <i class="bi bi-check-circle-fill" aria-hidden="true"></i>
        <h4 class="fw-bold mt-2"><?= h(t('form_thanks')) ?></h4>
        <p class="text-2"><?= h(t('form_thanks_sub')) ?></p>
        <a class="btn btn-wa w-100 d-none" id="joinWa" target="_blank" rel="noopener"><i class="bi bi-whatsapp" aria-hidden="true"></i><?= h(t('form_open_wa')) ?></a>
      </div>
    </div>
  </div></div>
</div>

<!-- ══ BOTTOM NAV ══ -->
<nav class="bnav3" aria-label="Quick links">
  <a href="#top" class="on" aria-current="page"><span class="pill"><i class="bi bi-house-door-fill" aria-hidden="true"></i></span><?= h(t('nav_home')) ?></a>
  <a href="<?= url('modules/market.php') ?>" class="mid"><span class="ring"><i class="bi bi-bag-fill" aria-hidden="true"></i></span><?= h(t('nav_market')) ?></a>
  <?php if($isAdminNow): ?>
    <a href="<?= url('dashboard.php') ?>"><span class="pill"><i class="bi bi-speedometer2" aria-hidden="true"></i></span><?= h(t('nav_dashboard')) ?></a>
  <?php elseif($_pLoggedIn): ?>
    <a href="<?= url('dashboard.php') ?>"><span class="pill"><i class="bi bi-person-circle" aria-hidden="true"></i></span><?= h(t('nav_account')) ?></a>
  <?php else: ?>
    <button type="button" id="openLogin"><span class="pill"><i class="bi bi-box-arrow-in-right" aria-hidden="true"></i></span><?= h(t('nav_login')) ?></button>
  <?php endif; ?>
</nav>
<!-- ══════════════════ LOGIN MODAL ══════════════════ -->
<div class="overlay" id="loginOverlay" onclick="if(event.target===this)closeModal()">
<div class="lgn" role="dialog" aria-modal="true" aria-labelledby="mTitle">
  <div class="lgn-bar"></div>
  <div class="lgn-head">
    <h3 id="mTitle">Member Portal</h3>
    <button type="button" class="lgn-x" onclick="closeModal()" aria-label="Close"><i class="bi bi-x-lg" aria-hidden="true"></i></button>
  </div>
  <div class="lgn-tabs" role="tablist" aria-label="Login or apply">
    <button type="button" class="mtab on" id="tLogin"    role="tab" aria-selected="true"  aria-controls="pLogin"    onclick="switchTab('login')"><span aria-hidden="true">🔐</span> Login</button>
    <button type="button" class="mtab"    id="tRegister" role="tab" aria-selected="false" aria-controls="pRegister" onclick="switchTab('register')"><span aria-hidden="true">✍️</span> Apply to Join</button>
  </div>
  <div class="lgn-body">

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
        <button type="button" class="fbtn" id="btnBioLogin" onclick="bioLogin()" style="display:none;width:100%;margin-top:.5rem;background:transparent;border:1.5px solid var(--accent-text);color:#fff;font-weight:800">
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
        <p style="text-align:center;font-size:.8rem;color:var(--t3);margin-top:-.2rem">Still stuck? Ask the club secretary to reset your login.</p>
        <p class="wa-only" style="text-align:center;font-size:.86rem;display:none">
          <a href="#" onclick="showOtpLogin();return false" style="color:var(--p);font-weight:700;display:inline-block;padding:.4rem">💬 Get a login code on WhatsApp instead</a>
        </p>
      </div>

      <!-- STEP 2c: Log in with a WhatsApp code -->
      <div id="stepOtp" style="display:none">
        <button type="button" class="fback" onclick="backStep('stepPhone')">← Change Number</button>
        <div style="text-align:center;margin:.3rem 0 1rem">
          <div style="font-size:1.6rem;margin-bottom:.3rem" aria-hidden="true">💬</div>
          <div style="font-weight:800;font-size:1rem">Enter the WhatsApp code</div>
          <div id="otpInfo" style="font-size:.85rem;color:var(--t3);margin-top:.25rem" role="status">We will send a 6-digit code to your WhatsApp.</div>
        </div>
        <label class="flbl" for="otpCode">6-digit code</label>
        <input type="text" class="finp" id="otpCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]*" placeholder="••••••" style="text-align:center;letter-spacing:.5em;font-size:1.3rem;font-weight:800">
        <button type="button" class="fbtn fbtn-p" id="btnOtpLogin" onclick="doOtpLogin()">Log in</button>
        <button type="button" class="fback" id="btnOtpResend" onclick="sendOtp('login')" style="display:block;margin:.6rem auto 0">Send the code again</button>
      </div>

      <!-- STEP 2b: No passkey — create one -->
      <div id="stepCreatePasskey" style="display:none">
        <button type="button" class="fback" onclick="backStep('stepPhone')">← Change Number</button>
        <div style="text-align:center;margin:.3rem 0 1rem">
          <div style="font-size:1.6rem;margin-bottom:.4rem" aria-hidden="true">🔑</div>
          <div style="font-weight:700;font-size:.95rem;color:var(--p)">Create Your Passkey</div>
          <div style="font-size:.78rem;color:var(--t3);margin-top:.25rem">You'll use this 6-digit code every time you login</div>
        </div>
        <!-- Verification: WhatsApp code when the gateway is set up, otherwise the registered name -->
        <div class="wa-only" style="display:none">
          <button type="button" class="fbtn fbtn-g" id="btnPkOtp" onclick="sendOtp('passkey')" style="margin-bottom:.6rem">💬 Send code to my WhatsApp</button>
          <div id="pkOtpInfo" style="font-size:.84rem;color:var(--t3);text-align:center;margin-bottom:.6rem" role="status"></div>
          <label class="flbl" for="pkOtp">6-digit WhatsApp code</label>
          <input type="text" class="finp" id="pkOtp" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]*" placeholder="••••••" style="text-align:center;letter-spacing:.4em;font-weight:800">
        </div>
        <div class="name-only">
          <label class="flbl" for="pkName">Your Registered Name (for verification)</label>
          <input type="text" class="finp" id="pkName" placeholder="Enter your full name as registered" autocomplete="name">
        </div>
        <!-- New passkey dots -->
        <div style="display:flex;justify-content:center;gap:.55rem;margin:1rem 0 .5rem" id="newPkDots" aria-hidden="true">
          <div class="pk-dot"></div><div class="pk-dot"></div><div class="pk-dot"></div>
          <div class="pk-dot"></div><div class="pk-dot"></div><div class="pk-dot"></div>
        </div>
        <div style="text-align:center;font-size:.75rem;color:var(--t3);margin-bottom:.8rem">Choose a 6-digit passkey</div>
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
    <div id="pwaIosHint" style="display:none;text-align:center;font-size:.75rem;color:#3B4266;padding:.4rem;background:#f0fdf4;border-radius:8px;border:1px solid #bbf7d0">
      📲 Tap <strong>Share</strong> then <strong>"Add to Home Screen"</strong> to install
    </div>
  </div>
</div>
</div>


<script src="<?= url('assets/vendor/bootstrap/js/bootstrap.bundle.min.js') ?>"></script>
<script src="<?= url('assets/js/motion.js') ?>?v=1" defer></script>
<script src="<?= url('assets/js/mini.js') ?>"></script>
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

/* 2. MODAL TRIGGERS */
$('#openLogin').on('click', function(){ openModal('login'); });
$('#loginOverlay').on('click', function(e){ if(e.target === this) closeModal(); });
$(document).on('keydown', function(e){ if(e.key === 'Escape'){ closeModal(); $('#iosSheet').removeClass('open'); } });
if(window.location.search.indexOf('login=1') !== -1){ setTimeout(function(){ openModal('login'); }, 400); }

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
// WhatsApp codes (set up in Club Settings → WhatsApp)
var WA_OTP = <?= wa_feature_on('otp') ? 'true' : 'false' ?>;
function waUi(){ $('.wa-only').toggle(WA_OTP); $('.name-only').toggle(!WA_OTP); }
waUi();
var otpTimer = null;
function otpCooldown(btnSel){
  var b=$(btnSel), left=60; b.prop('disabled',true);
  clearInterval(otpTimer);
  otpTimer=setInterval(function(){ left--; b.text(left>0?('Send again in '+left+'s'):(btnSel==='#btnPkOtp'?'💬 Send code again':'Send the code again')); if(left<=0){ clearInterval(otpTimer); b.prop('disabled',false); } },1000);
}
window.sendOtp = function(purpose){
  var info = purpose==='passkey' ? '#pkOtpInfo' : '#otpInfo';
  $(info).text('Sending…');
  $.ajax({ url:'', method:'POST', data:{ ajax:'1', action:'send_otp', purpose:purpose, phone:currentPhone }, dataType:'json',
    success:function(d){
      $(info).text(d.msg);
      if(d.ok){ otpCooldown(purpose==='passkey'?'#btnPkOtp':'#btnOtpResend'); $(purpose==='passkey'?'#pkOtp':'#otpCode').val('').trigger('focus'); }
    },
    error:function(){ $(info).text('Network error. Try again.'); }
  });
};
window.showOtpLogin = function(){
  $('#stepPasskey,#stepCreatePasskey').hide(); $('#loginMsg').hide();
  $('#stepOtp').show(); sendOtp('login');
};
window.doOtpLogin = function(){
  var c=$('#otpCode').val().replace(/\D/g,'');
  if(c.length!==6){ showMsg('#loginMsg','err','Enter the 6-digit code from WhatsApp.'); return; }
  $('#btnOtpLogin').prop('disabled',true);
  showMsg('#loginMsg','ok','<i class="fas fa-spinner fa-spin me-1"></i>Checking…');
  $.ajax({ url:'', method:'POST', data:{ ajax:'1', action:'login_otp', phone:currentPhone, otp:c }, dataType:'json',
    success:function(d){
      $('#btnOtpLogin').prop('disabled',false);
      if(d.ok){ showMsg('#loginMsg','ok','<i class="fas fa-check-circle me-1"></i>Welcome back!'); setTimeout(function(){ window.location.href=d.url; },600); }
      else showMsg('#loginMsg','err','<i class="fas fa-times-circle me-1"></i>'+d.msg);
    },
    error:function(){ $('#btnOtpLogin').prop('disabled',false); showMsg('#loginMsg','err','Network error.'); }
  });
};
$('#otpCode').on('input', function(){ var v=this.value.replace(/\D/g,'').slice(0,6); this.value=v; if(v.length===6) doOtpLogin(); });
$('#pkOtp').on('input', function(){ this.value=this.value.replace(/\D/g,'').slice(0,6); });

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
        if (typeof d.wa_otp !== 'undefined') { WA_OTP = !!d.wa_otp; waUi(); }
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
  $('#stepPasskey,#stepCreatePasskey,#stepName,#stepOtp').hide();
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
  var name = $('#pkName').val().trim(), otp = $('#pkOtp').val().replace(/\D/g,'');
  if (WA_OTP && otp.length !== 6){ showMsg('#loginMsg','err','Tap “Send code to my WhatsApp” and enter the 6-digit code first.'); pkNewVal=''; updateDots('newPkDots',''); return; }
  if (!WA_OTP && !name){ showMsg('#loginMsg','err','Enter your registered name.'); return; }
  showMsg('#loginMsg','ok','<i class="fas fa-spinner fa-spin me-1"></i>Creating passkey…');
  $.ajax({ url:'', method:'POST',
    data:{ ajax:'1', action:'set_passkey', phone:currentPhone, passkey:pkNewVal, member_name:name, otp:otp },
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
  $('#pkName').val(''); $('#pkOtp').val(''); $('#pkOtpInfo').text('');
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
</script>
<script>
/* ══ PUBLIC SITE: sliders, detail pop-ups, shop, join form ══ */
(function(){
var T = <?= json_encode(array('suitable'=>t('suitable_for'),'time'=>t('time'),'contact'=>t('contact_person'),'join'=>t('join_now'),
  'enq'=>t('enquire_whatsapp'),'prev'=>t('previous'),'next'=>t('next'),'errNet'=>t('form_err_net'),'errName'=>t('form_err_name'),'errPhone'=>t('form_err_phone')), JSON_UNESCAPED_UNICODE) ?>;
var PROGS = <?= json_encode(array_map(function($p){ return array(
  'n'=>tset($p['name'], $p['name_ml'] ?? ''), 'd'=>tset($p['description'] ?? '', $p['description_ml'] ?? ''), 'em'=>$p['emoji'] ?: '🏆',
  'img'=>!empty($p['photo']) ? url($p['photo']) : '', 's'=>$p['suitable_for'] ?? '', 't'=>$p['time_text'] ?? '', 'c'=>$p['contact_person'] ?? '',
  'link'=>$p['reg_link'] ?? ''); }, $programs), JSON_UNESCAPED_UNICODE) ?>;
var ITEMS = <?= json_encode($slJson, JSON_UNESCAPED_UNICODE) ?>;
var PRODS = <?= json_encode(array_map(function($p) use ($money, $num){
  $old = !empty($p['old_price']) && $num($p['price']) > 0 && (float)$p['old_price'] > $num($p['price']);
  return array('n'=>$p['title'], 'd'=>$p['description'] ?? '', 'imgs'=>$p['imgs'], 'p'=>$money($p['price']),
    'o'=>$old ? $money($p['old_price']) : '', 'url'=>rtrim(SITE_URL, '/') . '/modules/market.php?p=item&id=' . (int)$p['id']); }, $products), JSON_UNESCAPED_UNICODE) ?>;
var WA = <?= json_encode($siteWa) ?>;
var CLUB = <?= json_encode($clubName, JSON_UNESCAPED_UNICODE) ?>;

function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
var mEl = document.getElementById('mDetail'), mod = mEl ? bootstrap.Modal.getOrCreateInstance(mEl) : null;
function showDetail(title, body, foot){
  document.getElementById('mDetailT').textContent = title;
  document.getElementById('mDetailB').innerHTML = body;
  var f = document.getElementById('mDetailF'); f.innerHTML = foot || ''; f.classList.toggle('d-none', !foot);
  mod.show();
}
function row(icon, label, val){ return val ? '<div class="mrow"><i class="bi bi-' + icon + '" aria-hidden="true"></i><div><small>' + esc(label) + '</small><b>' + esc(val) + '</b></div></div>' : ''; }
function photo(src, em){ return src ? '<img class="m-photo" src="' + esc(src) + '" alt="">' : (em ? '<div class="m-photo d-flex align-items-center justify-content-center" style="font-size:4.5rem" aria-hidden="true">' + em + '</div>' : ''); }
function joinBtn(){ return '<button type="button" class="btn btn-brand w-100" data-open-join>' + esc(T.join) + '</button>'; }

/* programs */
document.querySelectorAll('[data-prog]').forEach(function(b){
  b.addEventListener('click', function(){
    var p = PROGS[+b.getAttribute('data-prog')]; if(!p) return;
    showDetail(p.n, photo(p.img, p.em) + (p.d ? '<p>' + esc(p.d) + '</p>' : '') + row('people-fill', T.suitable, p.s) + row('clock-fill', T.time, p.t) + row('person-badge-fill', T.contact, p.c),
      p.link ? '<a class="btn btn-brand w-100" href="' + esc(p.link) + '" target="_blank" rel="noopener">' + esc(T.join) + '</a>' : joinBtn());
  });
});
/* slider cards */
document.querySelectorAll('[data-item]').forEach(function(b){
  b.addEventListener('click', function(){
    var k = b.getAttribute('data-item').split(':'), it = (ITEMS[k[0]] || [])[+k[1]]; if(!it) return;
    showDetail(it.t, photo(it.img, it.em) + (it.tag ? '<span class="badge rounded-pill text-bg-light mb-2">' + esc(it.tag) + '</span>' : '') + (it.s ? '<p class="text-2 mb-2">' + esc(it.s) + '</p>' : '') + (it.d ? '<p style="white-space:pre-line">' + esc(it.d) + '</p>' : ''), '');
  });
});
/* shop */
document.querySelectorAll('[data-prod]').forEach(function(b){
  b.addEventListener('click', function(){
    var p = PRODS[+b.getAttribute('data-prod')]; if(!p) return;
    var id = 'pc' + Date.now(), ph = '';
    if(p.imgs.length > 1){
      ph = '<div id="' + id + '" class="carousel slide mb-3" data-bs-ride="false"><div class="carousel-inner rounded-4">';
      p.imgs.forEach(function(s, i){ ph += '<div class="carousel-item' + (i ? '' : ' active') + '"><img class="m-photo mb-0" src="' + esc(s) + '" alt="' + esc(p.n) + ' ' + (i+1) + '"></div>'; });
      ph += '</div><button class="carousel-control-prev" type="button" data-bs-target="#' + id + '" data-bs-slide="prev"><span class="carousel-control-prev-icon" aria-hidden="true"></span><span class="visually-hidden">' + esc(T.prev) + '</span></button>'
          + '<button class="carousel-control-next" type="button" data-bs-target="#' + id + '" data-bs-slide="next"><span class="carousel-control-next-icon" aria-hidden="true"></span><span class="visually-hidden">' + esc(T.next) + '</span></button></div>';
    } else ph = photo(p.imgs[0] || '', '🛍️');
    var price = '<div class="price fs-4 mb-2">' + esc(p.p) + (p.o ? ' <s>' + esc(p.o) + '</s>' : '') + '</div>';
    var msg = 'Hello ' + CLUB + ', I am interested in: ' + p.n + '\nPrice: ' + p.p + '\n' + p.url;
    showDetail(p.n, ph + price + (p.d ? '<p style="white-space:pre-line">' + esc(p.d) + '</p>' : ''),
      WA ? '<a class="btn btn-wa w-100" target="_blank" rel="noopener" href="https://wa.me/' + WA + '?text=' + encodeURIComponent(msg) + '"><i class="bi bi-whatsapp" aria-hidden="true"></i>' + esc(T.enq) + '</a>' : '<a class="btn btn-brand w-100" href="' + esc(p.url) + '">' + esc(p.n) + ' →</a>');
    var c = document.getElementById(id); if(c) bootstrap.Carousel.getOrCreateInstance(c);
  });
});
/* buttons inside pop-ups that open the join form */
document.addEventListener('click', function(e){
  var j = e.target.closest && e.target.closest('[data-open-join]'); if(!j) return;
  mEl.addEventListener('hidden.bs.modal', function once(){ mEl.removeEventListener('hidden.bs.modal', once); bootstrap.Modal.getOrCreateInstance(document.getElementById('mJoin')).show(); });
  mod.hide();
});

/* sliders: arrows, dots, auto-slide every 4s (pauses on touch / hover / focus; off for reduced motion) */
var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
document.querySelectorAll('[data-slider]').forEach(function(sl){
  var tr = sl.querySelector('.sl-track'), cards = tr.querySelectorAll('.sl-card'), dots = sl.querySelectorAll('.sl-dot'), paused = false, timer;
  function step(){ return cards.length > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : tr.clientWidth; }
  function idx(){ return Math.round(tr.scrollLeft / step()); }
  function go(i){ var n = cards.length; if(!n) return; i = (i + n) % n; tr.scrollTo({left: cards[i].offsetLeft - cards[0].offsetLeft, behavior: reduce ? 'auto' : 'smooth'}); }
  sl.querySelectorAll('.sl-arrow').forEach(function(a){ a.addEventListener('click', function(){ go(idx() + (+a.getAttribute('data-dir'))); }); });
  tr.addEventListener('scroll', function(){ var i = Math.min(idx(), dots.length - 1); dots.forEach(function(d, j){ d.classList.toggle('on', j === i); }); }, {passive:true});
  function pause(){ paused = true; } function resume(){ paused = false; }
  ['touchstart','mouseenter','focusin'].forEach(function(ev){ sl.addEventListener(ev, pause, {passive:true}); });
  ['mouseleave','focusout'].forEach(function(ev){ sl.addEventListener(ev, resume); });
  sl.addEventListener('touchend', function(){ setTimeout(resume, 6000); }, {passive:true});
  if(!reduce && cards.length > 1){
    timer = setInterval(function(){
      if(paused || document.hidden) return;
      var r = tr.getBoundingClientRect(); if(r.bottom < 0 || r.top > innerHeight) return;
      var atEnd = tr.scrollLeft + tr.clientWidth >= tr.scrollWidth - 4;
      go(atEnd ? 0 : idx() + 1);
    }, 4000);
  }
});

/* join form: chips, validation, save, thank-you, WhatsApp */
var chosen = [];
document.querySelectorAll('#jChips .chip').forEach(function(c){
  c.addEventListener('click', function(){
    var on = c.getAttribute('aria-pressed') !== 'true'; c.setAttribute('aria-pressed', on ? 'true' : 'false');
    var v = c.getAttribute('data-v'); chosen = chosen.filter(function(x){ return x !== v; }); if(on) chosen.push(v);
  });
});
var jf = document.getElementById('joinForm');
if(jf) jf.addEventListener('submit', function(e){
  e.preventDefault();
  var err = document.getElementById('joinErr'), btn = document.getElementById('jSend');
  function fail(m, f){ err.textContent = m; err.classList.remove('d-none'); if(f){ f.setAttribute('aria-invalid','true'); f.focus(); } }
  err.classList.add('d-none'); jf.querySelectorAll('[aria-invalid]').forEach(function(x){ x.removeAttribute('aria-invalid'); });
  var nm = document.getElementById('jName'), ph = document.getElementById('jPhone'), digits = ph.value.replace(/\D/g, '');
  if(digits.length === 12 && digits.indexOf('91') === 0) digits = digits.slice(2);
  if(!nm.value.trim()) return fail(T.errName, nm);
  if(digits.length !== 10) return fail(T.errPhone, ph);
  var fd = new FormData(jf); fd.append('ajax', '1'); fd.append('action', 'enquiry'); fd.append('interest', chosen.join(', ')); fd.set('phone', digits);
  btn.disabled = true;
  fetch(location.pathname, {method:'POST', body:fd, credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){
    btn.disabled = false;
    if(!d.ok) return fail(d.msg || T.errNet);
    jf.classList.add('d-none'); document.getElementById('joinThanks').classList.remove('d-none');
    var wa = document.getElementById('joinWa');
    if(d.wa){ wa.href = d.wa; wa.classList.remove('d-none'); setTimeout(function(){ window.open(d.wa, '_blank', 'noopener'); }, 900); }
  }).catch(function(){ btn.disabled = false; fail(T.errNet); });
});
var mj = document.getElementById('mJoin');
if(mj) mj.addEventListener('hidden.bs.modal', function(){
  if(!document.getElementById('joinThanks').classList.contains('d-none')){
    jf.reset(); jf.classList.remove('d-none'); document.getElementById('joinThanks').classList.add('d-none');
    chosen = []; document.querySelectorAll('#jChips .chip').forEach(function(c){ c.setAttribute('aria-pressed','false'); });
  }
});
if(location.hash === '#join' && mj) bootstrap.Modal.getOrCreateInstance(mj).show();

/* bottom bar: highlight Home only near the top */
var home = document.querySelector('.bnav3 a[href="#top"]');
if(home) window.addEventListener('scroll', function(){ var top = scrollY < 400; home.classList.toggle('on', top); if(top) home.setAttribute('aria-current','page'); else home.removeAttribute('aria-current'); }, {passive:true});
})();
</script>
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
        <div style="font-size:.75rem;color:#64748b">Aishwarya Arts &amp; Sports Club</div>
        <div style="font-size:.75rem;color:#5d6b80;margin-top:.1rem">mynamecc.online</div>
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
          <div style="font-size:.75rem;color:#64748b">The square with arrow — Safari bottom bar</div>
        </div>
        <span style="font-size:1.3rem;margin-left:auto">⬆️</span>
      </div>

      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#f8faff;border-radius:12px;margin-bottom:.45rem;border:1.5px solid #1565c0">
        <div style="width:36px;height:36px;background:#1565c0;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0">2️⃣</div>
        <div>
          <div style="font-size:.82rem;font-weight:800;color:#1565c0">Add to Home Screen</div>
          <div style="font-size:.75rem;color:#64748b">Scroll down in the menu &amp; tap it</div>
        </div>
        <span style="font-size:1.3rem;margin-left:auto">➕</span>
      </div>

      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#e8f5e9;border-radius:12px;margin-bottom:.7rem;border:1.5px solid #2e7d32">
        <div style="width:36px;height:36px;background:#2e7d32;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0">3️⃣</div>
        <div>
          <div style="font-size:.82rem;font-weight:800;color:#2e7d32">Tap Add — Installed! 🎉</div>
          <div style="font-size:.75rem;color:#64748b">App icon saved to home screen</div>
        </div>
        <span style="font-size:1.3rem;margin-left:auto">✅</span>
      </div>

      <!-- Animated bounce arrow pointing down to Safari toolbar -->
      <div style="text-align:center;margin-top:.3rem">
        <div style="font-size:2rem;animation:bounce 1s infinite">⬇️</div>
        <div style="font-size:.75rem;color:#e65100;font-weight:700;background:#fff3e0;display:inline-block;padding:.3rem .8rem;border-radius:20px;border:1px solid #ffe082">
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
        <div><div style="font-size:.78rem;font-weight:700;color:#1a1a1a">Tap ⋮ menu in Chrome</div><div style="font-size:.75rem;color:#64748b">Top right corner of browser</div></div>
      </div>
      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#f8faff;border-radius:12px;margin-bottom:.45rem;border:1px solid #e8ecf4">
        <div style="width:32px;height:32px;background:#1565c0;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">📲</div>
        <div><div style="font-size:.78rem;font-weight:700;color:#1a1a1a">Tap "Add to Home screen"</div><div style="font-size:.75rem;color:#64748b">Or "Install app" if shown</div></div>
      </div>
      <div style="display:flex;align-items:center;gap:.7rem;padding:.6rem .7rem;background:#e8f5e9;border-radius:12px;margin-bottom:.8rem;border:1px solid #c8e6c9">
        <div style="width:32px;height:32px;background:#2e7d32;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">✅</div>
        <div><div style="font-size:.78rem;font-weight:700;color:#1a1a1a">Tap "Add" — Done!</div><div style="font-size:.75rem;color:#64748b">App appears on home screen</div></div>
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
