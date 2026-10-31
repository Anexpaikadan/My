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
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<?php $pageTitle = isset($pageTitle) ? $pageTitle : setting('CLUB_NAME','Aishwarya Arts & Sports Club').' · '.setting('CLUB_PLACE','Vettikkattiri'); ?>
<title><?= h($pageTitle) ?></title>
<meta name="description" content="<?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club').', '.setting('CLUB_PLACE','Vettikkattiri').', Kerala — sports, arts and community service. Events, gallery and member portal.') ?>">
<link rel="manifest" href="/manifest.php">
<meta name="theme-color" content="#07225c">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aishwarya">
<link rel="apple-touch-icon" href="/assets/logo.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Playfair+Display:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
/* ══════════════════════════════════════════
   AASC — Public Homepage  |  Clean Build
   ══════════════════════════════════════════ */
:root{
  --p:#1a3a6b; --p2:#0d47a1;
  --a:#c8922a; --a2:#e6b84a;
  --r:#b71c1c; --g:#1b5e20;
  --tx:#1a1a2e; --t2:#4a5568; --t3:#5f6f86; /* 5.1:1 (was 2.9:1) */
  --a-tx:#8a6116; /* gold for small text on light bg, 5.2:1 */
  --bd:rgba(0,0,0,.08);
  --sh:0 4px 24px rgba(0,0,0,.09);
  --sh2:0 12px 48px rgba(0,0,0,.14);
  --rad:14px; --rad-s:8px;
  --tr:.28s cubic-bezier(.4,0,.2,1);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;color:var(--tx);background:#fff;overflow-x:hidden;line-height:1.65}
a{text-decoration:none;color:inherit}
img{display:block;max-width:100%}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:var(--a);border-radius:3px}

/* ── Kerala Stripe ── */
.kstripe{height:4px;background:repeating-linear-gradient(90deg,#c8922a 0,#c8922a 10px,#b71c1c 10px,#b71c1c 20px,#1a3a6b 20px,#1a3a6b 30px,#e6b84a 30px,#e6b84a 40px)}

/* ══ NAVBAR ══ */
.navbar{position:fixed;top:4px;left:0;right:0;z-index:1000;
  background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border-bottom:2px solid rgba(200,146,42,.3);height:62px;display:flex;align-items:center;
  transition:all .3s ease;box-shadow:0 2px 20px rgba(0,0,0,.1)}
.navbar.scrolled{box-shadow:var(--sh)}
.nav-inner{width:100%;max-width:1200px;margin:0 auto;padding:0 1.4rem;display:flex;align-items:center;gap:.5rem}
.nav-brand{display:flex;align-items:center;gap:.65rem;flex-shrink:0;margin-right:auto}
.nav-logo{width:40px;height:40px;border-radius:50%;object-fit:cover;border:2px solid var(--a);background:#f5f5f5}
.nav-logo-ph{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--p),var(--p2));border:2px solid var(--a);display:flex;align-items:center;justify-content:center;font-size:1rem;color:#fff}
.nav-club{line-height:1.2}
.nav-club-name{font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.09em;color:#1a3a6b}
.nav-club-sub{font-size:.62rem;color:#5f6f86;letter-spacing:.1em;text-transform:uppercase}
.nav-links{display:none;list-style:none;gap:.1rem;align-items:center;margin:0;padding:0}
.nav-links a{font-size:.84rem;font-weight:600;color:#4a5568;padding:.42rem .8rem;border-radius:8px;transition:all .25s;white-space:nowrap;text-decoration:none}
.nav-links a:hover,.nav-links a.on{color:var(--p);background:rgba(26,58,107,.08)}
.btn-login{background:var(--p);color:#fff;border:none;border-radius:var(--rad-s);padding:.46rem 1.15rem;font-family:'Inter',sans-serif;font-size:.84rem;font-weight:700;cursor:pointer;transition:all var(--tr);display:inline-flex;align-items:center;gap:.4rem;white-space:nowrap}
.btn-login:hover{background:var(--p2);transform:translateY(-1px);box-shadow:0 6px 18px rgba(26,58,107,.3)}
.hb{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:4.5px;background:none;border:none;cursor:pointer;width:44px;height:44px;padding:0;border-radius:10px;flex-shrink:0}
.hb span{width:22px;height:2px;background:var(--p);border-radius:2px;display:block;transition:all .25s}
.hb.open span:nth-child(1){transform:rotate(45deg) translate(4.5px,4.5px)}
.hb.open span:nth-child(2){opacity:0}
.hb.open span:nth-child(3){transform:rotate(-45deg) translate(4.5px,-4.5px)}
@media(min-width:860px){.nav-links{display:flex}.hb{display:none}}

/* Mobile menu */
.mob-menu{display:none;position:absolute;top:100%;left:0;right:0;background:#fff;border-bottom:1px solid var(--bd);padding:.8rem 1.4rem 1.1rem;box-shadow:var(--sh)}
.mob-menu.open{display:block}
.mob-menu a{display:block;font-size:.95rem;font-weight:500;color:var(--t2);padding:.8rem .4rem;border-bottom:1px solid rgba(0,0,0,.05);transition:color var(--tr)}
.mob-menu a:hover{color:var(--p)}
.mob-menu .btn-login{width:100%;justify-content:center;margin-top:.8rem}

/* ══ LOGIN MODAL ══ */
.overlay{display:none;position:fixed;inset:0;z-index:10002;background:rgba(10,20,40,.6);backdrop-filter:blur(8px);align-items:center;justify-content:center;padding:1rem}
.overlay.show{display:flex}
.modal{background:#fff;border-radius:20px;width:100%;max-width:430px;box-shadow:0 30px 80px rgba(0,0,0,.25);overflow:hidden;max-height:92vh;display:flex;flex-direction:column;animation:mpop .3s cubic-bezier(.34,1.56,.64,1) both}
@keyframes mpop{from{opacity:0;transform:scale(.85) translateY(24px)}to{opacity:1;transform:scale(1) translateY(0)}}
.modal-bar{height:4px;background:linear-gradient(90deg,var(--a),var(--p),var(--a2));flex-shrink:0}
.modal-head{display:flex;align-items:center;justify-content:space-between;padding:1.2rem 1.4rem .75rem;flex-shrink:0}
.modal-head h3{font-family:'Playfair Display',serif;font-size:1.35rem;color:var(--p);margin:0}
.modal-x{background:rgba(0,0,0,.06);border:none;width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:.9rem;color:var(--t2);display:flex;align-items:center;justify-content:center;transition:all var(--tr)}
.modal-x:hover{background:rgba(183,28,28,.12);color:var(--r)}
.modal-tabs{display:flex;padding:0 1.4rem;border-bottom:2px solid rgba(0,0,0,.06);flex-shrink:0}
.mtab{flex:1;padding:.68rem .5rem;text-align:center;font-size:.84rem;font-weight:600;color:var(--t3);cursor:pointer;border-bottom:2.5px solid transparent;margin-bottom:-2px;transition:all var(--tr)}
.mtab.on{color:var(--p);border-bottom-color:var(--p)}
.modal-body{padding:1.35rem 1.4rem 1.5rem;overflow-y:auto}
.mpanel{display:none}.mpanel.on{display:block}
/* Form elements */
.flbl{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--t2);display:block;margin-bottom:.35rem}
.finp{width:100%;background:#f7f9fc;border:1.5px solid rgba(0,0,0,.1);border-radius:10px;padding:.72rem .95rem;font-family:'Inter',sans-serif;font-size:1rem;color:var(--tx);outline:none;transition:all var(--tr);margin-bottom:.9rem}
.finp:focus{border-color:var(--p);background:#fff;box-shadow:0 0 0 3px rgba(26,58,107,.09)}
.finp::placeholder{color:#6E7A93}
.frow{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
/* OTP */
.otp-wrap{display:flex;gap:.4rem;justify-content:center;margin:.6rem 0 1.1rem}
.otp-cell{width:44px;height:52px;border:1.5px solid rgba(0,0,0,.12);border-radius:10px;text-align:center;font-size:1.25rem;font-weight:700;color:var(--p);font-family:'Inter',sans-serif;outline:none;background:#f7f9fc;transition:all var(--tr)}
.otp-cell:focus{border-color:var(--p);background:#fff;box-shadow:0 0 0 3px rgba(26,58,107,.09)}
/* Buttons */
.fbtn{width:100%;padding:.82rem;border:none;border-radius:10px;font-family:'Inter',sans-serif;font-weight:700;font-size:.92rem;cursor:pointer;transition:all var(--tr);display:flex;align-items:center;justify-content:center;gap:.5rem}
.fbtn-p{background:var(--p);color:#fff}.fbtn-p:hover:not(:disabled){background:var(--p2);transform:translateY(-1px);box-shadow:0 8px 24px rgba(26,58,107,.3)}
.fbtn-g{background:linear-gradient(135deg,#2e7d32,#1b5e20);color:#fff}.fbtn-g:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 8px 24px rgba(27,94,32,.3)}
.fbtn:disabled{opacity:.55;cursor:not-allowed}
.fmsg{border-radius:9px;padding:.7rem 1rem;font-size:.83rem;font-weight:500;margin-bottom:.9rem;display:none;line-height:1.45}
.fmsg.ok{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;display:block}
.fmsg.err{background:#fff0f0;border:1px solid #fecaca;color:#991b1b;display:block}
.fhint{font-size:.75rem;color:var(--t3);text-align:center;margin-top:.75rem;line-height:1.5}
.fhint a{color:var(--p);font-weight:600}
.fback{background:none;border:none;color:var(--t3);font-size:.8rem;cursor:pointer;padding:.2rem 0;font-family:'Inter',sans-serif;text-decoration:underline;transition:color var(--tr)}
.fback:hover{color:var(--p)}
.success-panel{text-align:center;padding:.5rem 0 .8rem}
.success-em{font-size:3.5rem;margin-bottom:.8rem}

/* ══ HERO SLIDER ══ */
/* ══ PAGE ANIMATIONS ══ */
@keyframes fadeInUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeInLeft{from{opacity:0;transform:translateX(-30px)}to{opacity:1;transform:translateX(0)}}
@keyframes fadeInRight{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:translateX(0)}}
@keyframes scaleIn{from{opacity:0;transform:scale(.92)}to{opacity:1;transform:scale(1)}}
@keyframes slideDown{from{opacity:0;transform:translateY(-20px)}to{opacity:1;transform:translateY(0)}}
@keyframes countUp{from{opacity:0}to{opacity:1}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
@keyframes floatUp{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}

.anim-fade-up{opacity:0;transform:translateY(30px);transition:opacity .7s ease,transform .7s ease}
.anim-fade-left{opacity:0;transform:translateX(-30px);transition:opacity .7s ease,transform .7s ease}
.anim-fade-right{opacity:0;transform:translateX(30px);transition:opacity .7s ease,transform .7s ease}
.anim-scale{opacity:0;transform:scale(.92);transition:opacity .6s ease,transform .6s ease}
.anim-visible{opacity:1!important;transform:none!important}

/* Hero content animations */
.hbadge{display:inline-block;background:rgba(200,146,42,.2);border:1px solid rgba(200,146,42,.5);color:#f5d060 !important;border-radius:30px;padding:.3rem 1rem;font-size:.7rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.2rem}
.htitle{font-family:'Playfair Display',Georgia,serif;font-size:clamp(2.2rem,5.5vw,4rem);font-weight:700;line-height:1.14;margin-bottom:.9rem;text-shadow:0 2px 12px rgba(0,0,0,.3);color:#fff}
.hsub{font-size:clamp(.95rem,2.3vw,1.15rem);color:rgba(255,255,255,.75);line-height:1.65;max-width:560px;margin:0 auto 2rem}
.hcta{display:flex;gap:.85rem;flex-wrap:wrap;justify-content:center}

/* Stats bar */
.stat-num{animation:fadeInUp .6s both}

/* Section titles */
.sec-label{animation:slideDown .5s both}
.sec-title{}

/* Cards hover lift */
.ev-card,.gal-cell,.stat{transition:transform .25s,box-shadow .25s}
.ev-card:hover{transform:translateY(-6px)!important;box-shadow:0 16px 40px rgba(0,0,0,.18)!important}

/* Floating logo */
.hero-logo-wrap img{animation:floatUp 3s ease-in-out infinite}

#hero{position:relative;height:100vh;min-height:600px;overflow:hidden}
.hslide{position:absolute;inset:0;opacity:0;visibility:hidden;transition:opacity 1.1s ease,visibility 1.1s;display:flex;align-items:center;justify-content:center}
.hslide.on{opacity:1;visibility:visible;z-index:2}
.hslide-bg{position:absolute;inset:0;background-size:cover;background-position:center}
.hslide-ov{position:absolute;inset:0;background:linear-gradient(160deg,rgba(5,15,40,.78) 0%,rgba(5,15,40,.42) 60%,rgba(5,15,40,.6) 100%)}
.hcontent{position:relative;z-index:3;text-align:center;color:#fff;padding:80px 1.5rem 2rem;max-width:800px;width:100%}
.hbadge{display:inline-block;background:rgba(200,146,42,.2);border:1px solid rgba(200,146,42,.5);color:var(--a2);border-radius:30px;padding:.3rem 1rem;font-size:.7rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.2rem}
.htitle{font-family:'Playfair Display',Georgia,serif;font-size:clamp(2.2rem,5.5vw,4rem);font-weight:700;line-height:1.14;margin-bottom:.9rem;text-shadow:0 2px 12px rgba(0,0,0,.3)}
.hsub{font-size:clamp(.95rem,2.3vw,1.15rem);color:rgba(255,255,255,.75);line-height:1.65;max-width:560px;margin:0 auto 2rem}
.hcta{display:flex;gap:.85rem;flex-wrap:wrap;justify-content:center}
.btn-hero-p{background:var(--a);color:#1a1a2e;border:none;border-radius:10px;padding:.82rem 2rem;font-family:'Inter',sans-serif;font-weight:700;font-size:.92rem;cursor:pointer;transition:all var(--tr)}
.btn-hero-p:hover{background:var(--a2);color:var(--tx);transform:translateY(-2px);box-shadow:0 8px 24px rgba(200,146,42,.4)}
.btn-hero-s{background:rgba(255,255,255,.12);border:1.5px solid rgba(255,255,255,.35);color:#fff;border-radius:10px;padding:.8rem 2rem;font-family:'Inter',sans-serif;font-weight:600;font-size:.92rem;cursor:pointer;transition:all var(--tr)}
.btn-hero-s:hover{background:rgba(255,255,255,.22);transform:translateY(-2px)}
/* Dots */
.hdots{position:absolute;bottom:1.8rem;left:50%;transform:translateX(-50%);display:flex;gap:.5rem;z-index:10}
.hdot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.38);border:none;cursor:pointer;transition:all .4s;padding:0}
.hdot.on{background:var(--a2);width:24px;border-radius:4px}
/* Arrows */
.harr{position:absolute;top:50%;transform:translateY(-50%);z-index:10;background:rgba(255,255,255,.12);border:1.5px solid rgba(255,255,255,.25);color:#fff;width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all var(--tr);font-size:1rem;backdrop-filter:blur(4px)}
.harr:hover{background:rgba(255,255,255,.25)}
.harr-l{left:1.2rem}.harr-r{right:1.2rem}

/* ══ STATS BAR ══ */
.stats-bar{
  display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem;
  padding:.85rem 1rem 1.1rem;
  background:linear-gradient(135deg,#0d1b3e,#1a3a6b);
  position:relative;z-index:1;
}
.stat-card{
  background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.12);
  border-radius:14px;
  padding:.7rem .4rem;
  text-align:center;
  backdrop-filter:blur(6px);
  transition:transform .2s;
}
.stat-card:active{transform:scale(.95)}
.stat-num{
  font-family:'Bebas Neue',sans-serif;
  font-size:1.8rem;line-height:1;
  color:#f5d060;
  display:block;
}
.stat-icon{font-size:1.1rem;display:block;margin-bottom:.15rem}
.stat-lbl{
  font-size:.66rem;color:rgba(255,255,255,.8);
  text-transform:uppercase;letter-spacing:.09em;
  font-weight:700;margin-top:.18rem;display:block;
}
.stat-sep{display:none}

/* ══ SECTIONS ══ */
.sec{padding:5rem 0}
.sec-bg{background:#fafbff}
.sec-label{display:inline-block;font-size:.68rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--a-tx);background:rgba(200,146,42,.1);border:1px solid rgba(200,146,42,.25);padding:.28rem .9rem;border-radius:30px;margin-bottom:.85rem}
.sec-title{font-family:'Playfair Display',serif;font-size:clamp(1.85rem,3.5vw,2.7rem);font-weight:700;color:var(--p);line-height:1.2;margin-bottom:.5rem}
.sec-rule{width:48px;height:3px;background:linear-gradient(90deg,var(--a),var(--a2));border-radius:2px;margin:.75rem 0}
.sec-sub{font-size:.95rem;color:var(--t2);line-height:1.7;max-width:500px}
/* Reveal */
/* Scroll reveal - visible by default, animate when .in added */
.rv{opacity:1;transform:none;transition:opacity .65s ease,transform .65s ease}
.rl{opacity:1;transform:none;transition:opacity .65s ease,transform .65s ease}
.rr{opacity:1;transform:none;transition:opacity .65s ease,transform .65s ease}
/* scroll reveal disabled - always visible */
.rv.in,.rl.in,.rr.in{opacity:1!important;transform:none!important}

/* ══ EVENTS ══ */
.ev-track-wrap{overflow:hidden;position:relative}
.ev-track{display:flex;gap:20px;transition:transform .55s cubic-bezier(.4,0,.2,1)}
.ev-card{flex-shrink:0;width:290px;background:#fff;border-radius:var(--rad);box-shadow:var(--sh);border:1px solid var(--bd);overflow:hidden;transition:all var(--tr)}
.ev-card:hover{transform:translateY(-6px);box-shadow:var(--sh2);border-color:rgba(26,58,107,.1)}
.ev-thumb{height:175px;overflow:hidden;position:relative;background:#f0f4f8}
.ev-thumb img{width:100%;height:100%;object-fit:cover;transition:transform .5s ease}
.ev-card:hover .ev-thumb img{transform:scale(1.07)}
.ev-ph{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.4rem}
.ev-badge{position:absolute;top:.7rem;left:.7rem;font-size:.63rem;font-weight:700;padding:.2rem .6rem;border-radius:20px;text-transform:uppercase;letter-spacing:.06em;color:#fff}
.ev-body{padding:1.15rem 1.2rem 1.3rem}
.ev-date{font-size:.72rem;font-weight:700;color:var(--a-tx);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.42rem;display:flex;align-items:center;gap:.3rem}
.ev-title{font-family:'Playfair Display',serif;font-size:1rem;font-weight:700;color:var(--tx);margin-bottom:.4rem;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ev-desc{font-size:.81rem;color:var(--t2);line-height:1.6;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:.85rem}
.ev-more{display:inline-flex;align-items:center;gap:.4rem;font-size:.81rem;font-weight:600;color:var(--p);padding:.4rem .85rem;border:1.5px solid rgba(26,58,107,.2);border-radius:var(--rad-s);transition:all var(--tr)}
.ev-more:hover{background:var(--p);color:#fff;border-color:var(--p)}
/* Slider controls */
.sl-ctrl{display:flex;align-items:center;justify-content:center;gap:.75rem;margin-top:1.8rem}
.sl-btn{width:44px;height:44px;border-radius:50%;background:#fff;border:1.5px solid var(--bd);color:var(--t2);cursor:pointer;font-size:.9rem;display:flex;align-items:center;justify-content:center;transition:all var(--tr);box-shadow:0 2px 8px rgba(0,0,0,.06)}
.sl-btn:hover{background:var(--p);color:#fff;border-color:var(--p)}
.sl-dots{display:flex;gap:.42rem;align-items:center}
.sl-dot{width:7px;height:7px;border-radius:50%;background:rgba(0,0,0,.15);cursor:pointer;border:none;transition:all .3s;padding:0}
.sl-dot.on{background:var(--p);width:20px;border-radius:4px}

/* ══ GALLERY ══ */
.gal-wrap{overflow:hidden;position:relative;border-radius:var(--rad)}
.gal-wrap::before,.gal-wrap::after{content:'';position:absolute;top:0;bottom:0;width:60px;z-index:3;pointer-events:none}
.gal-wrap::before{left:0;background:linear-gradient(to right,#fff 30%,transparent)}
.gal-wrap::after{right:0;background:linear-gradient(to left,#fff 30%,transparent)}
.gal-track{display:flex;gap:12px;animation:galscroll 30s linear infinite;width:max-content}
.gal-track:hover{animation-play-state:paused}
@keyframes galscroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
.gal-cell{width:185px;height:185px;border-radius:var(--rad);overflow:hidden;flex-shrink:0;position:relative;cursor:pointer;border:1px solid var(--bd);background:#f0f4f8}
.gal-cell img{width:100%;height:100%;object-fit:cover;transition:transform .4s}
.gal-cell:hover img{transform:scale(1.08)}
.gal-cell-ph{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.5rem;background:linear-gradient(135deg,#f0f4f8,#e8edf5)}
.gal-cell-ov{position:absolute;inset:0;background:rgba(26,58,107,.6);opacity:0;transition:opacity .3s;display:flex;align-items:center;justify-content:center;color:#fff;font-size:1.4rem}
.gal-cell:hover .gal-cell-ov{opacity:1}
@media(max-width:576px){.gal-cell{width:155px;height:155px}}

/* ══ MODULE SECTIONS ══ */
.mod-sec{padding:5rem 0;position:relative;overflow:hidden}
.mod-bg{position:absolute;inset:0;background-size:cover;background-position:center;filter:brightness(.22)}
.mod-inner{position:relative;z-index:2;max-width:1180px;margin:0 auto;padding:0 1.5rem}
.mod-label{display:inline-block;font-size:.67rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--a2);background:rgba(200,146,42,.12);border:1px solid rgba(200,146,42,.28);padding:.28rem .9rem;border-radius:30px;margin-bottom:.85rem}
.mod-title{font-family:'Playfair Display',serif;font-size:clamp(1.9rem,4vw,2.8rem);font-weight:700;color:#fff;line-height:1.2;margin-bottom:.5rem}
.mod-rule{width:50px;height:3px;background:linear-gradient(90deg,var(--a),var(--a2));border-radius:2px;margin:.75rem 0 1.2rem}
.mod-sub{font-size:.95rem;color:rgba(255,255,255,.65);line-height:1.65;max-width:500px;margin-bottom:1.8rem}
.mod-btn{display:inline-flex;align-items:center;gap:.5rem;padding:.78rem 1.8rem;border-radius:10px;font-family:'Inter',sans-serif;font-weight:700;font-size:.9rem;transition:all var(--tr);border:none;cursor:pointer;text-decoration:none}
.mod-btn:hover{transform:translateY(-3px)}
/* Dark cards */
.dk-card{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);border-radius:var(--rad);padding:1rem;transition:all var(--tr);backdrop-filter:blur(4px)}
.dk-card:hover{background:rgba(255,255,255,.13);border-color:rgba(200,146,42,.35);transform:translateY(-4px)}
/* Football table */
.ft-tbl{width:100%;border-collapse:collapse;font-size:.84rem}
.ft-tbl thead th{background:rgba(0,0,0,.35);color:#a5d6a7;padding:.62rem .8rem;text-align:left;font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em}
.ft-tbl tbody td{padding:.6rem .8rem;color:rgba(255,255,255,.82);border-bottom:1px solid rgba(255,255,255,.06)}
.ft-tbl tbody tr:first-child td{color:#ffd700;font-weight:700}
/* Progress */
.prog-bar{background:rgba(255,255,255,.15);border-radius:8px;height:8px;overflow:hidden;margin:.4rem 0}
.prog-fill{height:100%;border-radius:8px;background:linear-gradient(90deg,var(--a),var(--a2));transition:width 1.5s ease}
/* Program chips */
.prog-chip{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.13);border-radius:10px;padding:.6rem .85rem;font-size:.82rem;font-weight:600;color:#fff;transition:all .22s;display:flex;align-items:center;gap:.5rem}
.prog-chip:hover{background:rgba(200,146,42,.2);border-color:rgba(200,146,42,.4)}

/* ══ FOOTER ══ */
#footer{background:var(--p);color:rgba(255,255,255,.65)}
.foot-inner{max-width:1200px;margin:0 auto;padding:3rem 1.5rem 1.5rem}
.foot-logo{display:flex;align-items:center;gap:.65rem;margin-bottom:1rem}
.foot-logo img{width:44px;height:44px;border-radius:50%;border:2px solid rgba(200,146,42,.4);object-fit:cover}
.foot-logo-ph{width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.1);border:2px solid rgba(200,146,42,.35);display:flex;align-items:center;justify-content:center;font-size:1.05rem}
.foot-name{font-family:'Playfair Display',serif;font-size:.95rem;color:#fff;font-weight:700}
.foot-tag{font-size:.72rem;color:rgba(255,255,255,.72);letter-spacing:.07em}
.foot-col h5{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:rgba(255,255,255,.72);margin-bottom:.75rem}
.foot-col a{display:block;font-size:.88rem;color:rgba(255,255,255,.82);padding:.45rem 0;transition:all .2s}
.foot-col a:hover{color:var(--a2);padding-left:.22rem}
.foot-col p{font-size:.88rem;color:rgba(255,255,255,.82);margin:.1rem 0}
.sicon{width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.14);color:rgba(255,255,255,.65);display:flex;align-items:center;justify-content:center;font-size:.88rem;transition:all .22s}
.sicon:hover{background:var(--a);border-color:var(--a);color:#fff;transform:translateY(-2px)}
.foot-btm{border-top:1px solid rgba(255,255,255,.07);padding:1.2rem 1.5rem;text-align:center;font-size:.76rem;color:rgba(255,255,255,.72);max-width:1200px;margin:0 auto}

/* WA float */
.wa-float{position:fixed;bottom:1.5rem;right:1.5rem;width:50px;height:50px;border-radius:50%;background:#25d366;color:#fff;display:flex;align-items:center;justify-content:center;font-size:1.35rem;z-index:900;box-shadow:0 6px 22px rgba(37,211,102,.42);transition:all .22s;border:none;cursor:pointer;text-decoration:none}
.wa-float:hover{background:#1ebe5d;transform:scale(1.1);color:#fff}
@media(max-width:576px){.sec{padding:3.8rem 0}.mod-sec{padding:3.8rem 0}}

/* ══ GALLERY LIGHTBOX ══ */
.lb-ov{display:none;position:fixed;inset:0;z-index:10002;background:rgba(0,0,0,.96);align-items:center;justify-content:center;flex-direction:column;padding:0}
.lb-ov.on{display:flex}
.lb-img-wrap{position:relative;width:100%;height:100%;display:flex;align-items:center;justify-content:center;padding:60px 0 80px}
.lb-img-wrap img{max-width:100%;max-height:100%;object-fit:contain;border-radius:8px;box-shadow:0 24px 80px rgba(0,0,0,.8);transition:opacity .2s}
.lb-close{position:fixed;top:1rem;right:1rem;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.12);border:1.5px solid rgba(255,255,255,.2);color:#fff;font-size:1.15rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;z-index:9001}
.lb-close:hover{background:rgba(255,255,255,.25)}
.lb-caption{position:fixed;bottom:1.2rem;left:50%;transform:translateX(-50%);color:rgba(255,255,255,.7);font-size:.84rem;font-weight:500;text-align:center;letter-spacing:.04em;max-width:90vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;z-index:9001}

/* ── PASSKEY KEYPAD ── */
.num-keypad{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;max-width:280px;margin:0 auto}
.num-keypad button{background:#f4f6fb;border:1.5px solid #e0e7ff;border-radius:12px;min-height:54px;padding:.7rem .4rem;font-size:1.25rem;font-weight:700;color:#0d1b3e;cursor:pointer;justify-content:center;transition:all .15s;display:flex;flex-direction:column;align-items:center;gap:0;line-height:1;font-family:'Inter',sans-serif}
.num-keypad button:active{background:#0d47a1;color:#fff;border-color:#0d47a1;transform:scale(.94)}
.num-keypad button span{font-size:.55rem;font-weight:600;letter-spacing:.08em;color:#5f6f86;margin-top:.12rem;display:block}
.num-keypad button:active span{color:rgba(255,255,255,.65)}
.num-keypad .pk-del{background:#fff0f0;border-color:#fecaca;color:#b71c1c}
.num-keypad .pk-del:active{background:#b71c1c;color:#fff;border-color:#b71c1c}
.num-keypad .pk-ok{background:linear-gradient(135deg,#0d47a1,#1565c0);color:#fff;border-color:#0d47a1}
.pk-dot{width:14px;height:14px;border-radius:50%;background:#e0e7ff;border:2px solid #c7d2fe;transition:all .2s}
.pk-dot.filled{background:#0d47a1;border-color:#0d47a1;transform:scale(1.18)}
.pk-dot.err{background:#ef5350;border-color:#ef5350}
@keyframes pkShake{0%,100%{transform:translateX(0)}25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}

.lb-login-hint{position:fixed;bottom:3.5rem;left:50%;transform:translateX(-50%);z-index:9001}
.lb-login-hint button{background:var(--p);color:#fff;border:none;border-radius:8px;padding:.55rem 1.3rem;font-family:'Inter',sans-serif;font-size:.84rem;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:.45rem;transition:all .2s}
.lb-login-hint button:hover{background:var(--p2);transform:translateY(-2px)}
/* Touch/swipe indicator on mobile */
.lb-swipe-hint{position:fixed;top:1rem;left:50%;transform:translateX(-50%);color:rgba(255,255,255,.72);font-size:.72rem;letter-spacing:.06em;z-index:9001;pointer-events:none}
@media(min-width:600px){.lb-swipe-hint{display:none}}
/* ══ UX / ACCESSIBILITY LAYER ══ */
.skip-link{position:absolute;left:.75rem;top:-100px;z-index:20000;background:#fff;color:var(--p);font-weight:700;padding:.7rem 1rem;border-radius:10px;box-shadow:var(--sh2)}
.skip-link:focus{top:.75rem}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
:focus{outline:none}
:focus-visible{outline:3px solid var(--p2);outline-offset:2px;border-radius:6px}
#hero :focus-visible,#footer :focus-visible,.lb-ov :focus-visible,.mod-sec :focus-visible{outline-color:#ffc107}
.finp:focus-visible,.otp-cell:focus-visible{outline:none}
.mtab{background:none;border:0;border-bottom:2.5px solid transparent;font-family:inherit;min-height:44px}
.mtab.on{border-bottom-color:var(--p)}
.btn-login{min-height:40px}
/* Bigger tap area for slider dots without changing their look */
.hdot{position:relative}.hdot::after{content:'';position:absolute;inset:-14px -6px}
.sl-dot{position:relative}.sl-dot::after{content:'';position:absolute;inset:-14px -6px}
.gal-wrap:focus-within .gal-track{animation-play-state:paused}
/* Footer grid (the markup uses Bootstrap class names, but Bootstrap is not loaded) */
#footer .row{display:grid;grid-template-columns:1fr 1fr;gap:1.6rem 1.2rem}
#footer .row>.col-sm-12{grid-column:1/-1}
@media(min-width:768px){#footer .row{grid-template-columns:4fr 2fr 2fr 3fr;gap:2rem}#footer .row>.col-sm-12{grid-column:auto}}
/* Install-the-app sheet (had no styles, so it always showed at the page bottom) */
#iosSheet{display:none;position:fixed;inset:0;z-index:10003;background:rgba(10,20,40,.55);align-items:flex-end;justify-content:center}
#iosSheet.open{display:flex}
#iosSheet>div{animation:sheetUp .28s ease both;max-height:92vh;overflow-y:auto}
@keyframes sheetUp{from{transform:translateY(100%)}to{transform:none}}
/* Respect the phone's "reduce motion" setting */
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}
  .gal-track{animation:none!important}
  .gal-wrap{overflow-x:auto}
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
<a href="#main" class="skip-link">Skip to content</a>

<!-- ══════════════════ NAVBAR ══════════════════ -->
<?php include 'av-splash.php'; ?>

<nav class="navbar" id="mainNav" style="top:4px" aria-label="Main">
<div class="nav-inner">
  <a href="#hero" class="nav-brand" aria-label="<?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?> — home">
    <?php if($logo): ?><img src="<?= $logo ?>" class="nav-logo" alt="" width="40" height="40"><?php else: ?><div class="nav-logo-ph" aria-hidden="true">⚜</div><?php endif; ?>
    <div class="nav-club">
      <div class="nav-club-name"><?= h(setting('CLUB_NAME','Aishwarya A&S Club')) ?></div>
      <div class="nav-club-sub"><?= h(setting('CLUB_PLACE','Vettikkattiri')) ?> · Kerala</div>
    </div>
  </a>
  <ul class="nav-links" id="navLinks">
    <li><a href="#hero" class="on" id="nl-home" aria-current="true">Home</a></li>
    <li><a href="#events" id="nl-events">Events</a></li>
    <li><a href="#gallery" id="nl-gallery">Gallery</a></li>
    <li><a href="<?= url('modules/market.php') ?>"><span aria-hidden="true">🛍️</span> Market</a></li>
    <li><a href="<?= url('contact.php') ?>">Contact</a></li>
  </ul>
  <div style="display:flex;align-items:center;gap:.5rem">
    <button type="button" class="btn-login" id="openLogin"><i class="fas fa-sign-in-alt" aria-hidden="true"></i> Login</button>
    <button type="button" class="hb" id="hb" onclick="toggleMob()" aria-label="Open menu" aria-expanded="false" aria-controls="mobMenu"><span></span><span></span><span></span></button>
  </div>
</div>
<div class="mob-menu" id="mobMenu">
  <a href="#hero"    onclick="closeMob()"><span aria-hidden="true">🏠</span> Home</a>
  <a href="#events"  onclick="closeMob()"><span aria-hidden="true">📅</span> Events</a>
  <a href="#gallery" onclick="closeMob()"><span aria-hidden="true">🖼️</span> Gallery</a>
  <a href="<?= url('modules/market.php') ?>" onclick="closeMob()"><span aria-hidden="true">🛍️</span> Mini Market</a>
  <a href="<?= url('contact.php') ?>" onclick="closeMob()"><span aria-hidden="true">📞</span> Contact</a>
  <button type="button" class="btn-login" onclick="closeMob();openModal('login')"><i class="fas fa-sign-in-alt" aria-hidden="true"></i> Member Login</button>
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


<!-- ══════════════════ HERO SLIDER ══════════════════ -->
<main id="main" tabindex="-1" style="outline:none">
<section id="hero" style="height:100vh!important;min-height:600px;position:relative;overflow:hidden" aria-roledescription="carousel" aria-label="Highlights">
  <?php foreach($heroSlides as $i=>$sl): ?>
  <div class="hslide <?= $i===0?'on':'' ?>" data-idx="<?= $i ?>" role="group" aria-roledescription="slide" aria-label="<?= ($i+1).' of '.count($heroSlides) ?>"<?= $i===0?'':' aria-hidden="true"' ?>>
    <div class="hslide-bg" style="<?php
      if (!empty($sl['img'])):
        echo "background-image:url('".h($sl['img'])."');background-size:cover;background-position:center";
      else:
        echo "background:linear-gradient(".$sl['grad'].")";
      endif;
    ?>"></div>
    <div class="hslide-ov"></div>
    <div class="hcontent">
      <div class="hbadge"><span aria-hidden="true">🏆</span> <?= h(setting('CLUB_PLACE','Vettikkattiri')) ?> · Kerala</div>
      <?php $_ht = $i===0 ? 'h1' : 'h2'; ?><<?= $_ht ?> class="htitle"><?= h($sl['title']) ?></<?= $_ht ?>>
      <p class="hsub"><?= h($sl['subtitle']) ?></p>
      <div class="hcta">
        <button type="button" class="btn-hero-p" onclick="openModal('login')"><span aria-hidden="true">🔐</span> Member Login</button>
      </div>
    </div>
  </div>
  <?php endforeach; ?>
  <button type="button" class="harr harr-l" onclick="heroMove(-1)" aria-label="Previous slide"><i class="fas fa-chevron-left" aria-hidden="true"></i></button>
  <button type="button" class="harr harr-r" onclick="heroMove(1)" aria-label="Next slide"><i class="fas fa-chevron-right" aria-hidden="true"></i></button>
  <div class="hdots" id="heroDots">
    <?php foreach($heroSlides as $i=>$sl): ?>
    <button type="button" class="hdot <?= $i===0?'on':'' ?>" data-idx="<?= $i ?>" onclick="heroGo(<?= $i ?>)" aria-label="Show slide <?= $i+1 ?>"<?= $i===0?' aria-current="true"':'' ?>></button>
    <?php endforeach; ?>
  </div>
</section>

<!-- Stats Bar -->
<div class="stats-bar">
  <div class="stat-card">
    <span class="stat-icon" aria-hidden="true">👥</span>
    <span class="stat-num" data-target="<?=(int)($stats['total']??0)?>"><?=(int)($stats['total']??0)?></span>
    <span class="stat-lbl">Members</span>
  </div>
  <div class="stat-card">
    <span class="stat-icon" aria-hidden="true">✅</span>
    <span class="stat-num" data-target="<?=(int)($stats['active']??0)?>"><?=(int)($stats['active']??0)?></span>
    <span class="stat-lbl">Active</span>
  </div>
  <div class="stat-card">
    <span class="stat-icon" aria-hidden="true">⚽</span>
    <span class="stat-num" data-target="5">5</span>
    <span class="stat-lbl">Sports</span>
  </div>
  <div class="stat-card">
    <span class="stat-icon" aria-hidden="true">🩸</span>
    <span class="stat-num" data-target="<?=(int)($stats['donors']??0)?>"><?=(int)($stats['donors']??0)?></span>
    <span class="stat-lbl">Donors</span>
  </div>
</div>
</div>

<!-- EVENTS -->
<section id="events" style="padding:3rem 0;background:#f8fafc">
<div class="container" style="max-width:1200px;padding:0 1rem">
  <div style="text-align:center;margin-bottom:1.8rem">
    <h2 style="font-family:'Playfair Display',serif;font-size:clamp(1.6rem,3vw,2.2rem);font-weight:700;color:#0d1b3e">Club <span style="color:var(--a-tx)">Events</span></h2>
  </div>
  <?php
  $upEv = array_filter($events??[], function($e){ return strtotime($e['event_date'])>=strtotime('today'); });
  $tconf = ['football'=>['⚽','#1b5e20','#e8f5e9'],'cricket'=>['🏏','#e65100','#fff3e0'],'charity'=>['🤝','#880e4f','#fce4ec'],'cultural'=>['🎭','#6a1b9a','#f3e5f5'],'meeting'=>['📋','#37474f','#eceff1']];
  if(empty($upEv)): ?>
  <div style="text-align:center;padding:2rem;color:#5d6b80"><div style="font-size:2.5rem">📅</div><div>No upcoming events. Check back soon!</div></div>
  <?php else: ?>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:1rem">
  <?php foreach(array_slice(array_values($upEv),0,6) as $ev):
    $diff=ceil((strtotime($ev['event_date'])-time())/86400);
    $tc=$tconf[$ev['event_type']]??['📅','#0d47a1','#e3f2fd'];
    $cd=$diff===0?'🔥 Today':($diff===1?'⚡ Tomorrow':"In {$diff}d");
    $cc=$diff<=1?'#b71c1c':($diff<=7?'#e65100':'#475569');
  ?>
  <div style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);border-top:4px solid <?=$tc[1]?>">
    <div style="padding:.85rem 1rem">
      <div style="display:flex;justify-content:space-between;margin-bottom:.5rem">
        <span style="background:<?=$tc[2]?>;color:<?=$tc[1]?>;border-radius:20px;padding:.08rem .55rem;font-size:.64rem;font-weight:800"><?=$tc[0]?> <?=h(ucfirst($ev['event_type']??''))?></span>
        <span style="font-size:.7rem;font-weight:800;color:<?=$cc?>"><?=$cd?></span>
      </div>
      <div style="font-weight:700;font-size:.95rem;color:#0d1b3e;margin-bottom:.3rem"><?=h($ev['title'])?></div>
      <?php if($ev['description']??''): ?><div style="font-size:.77rem;color:#64748b;margin-bottom:.45rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden"><?=h($ev['description'])?></div><?php endif; ?>
      <div style="font-size:.73rem;color:#64748b">📅 <?=date('d M Y',strtotime($ev['event_date']))?><?php if($ev['event_time']??''): ?> · <?=date('g:i A',strtotime($ev['event_time']))?><?php endif; ?></div>
      <?php if($ev['location']??''): ?><div style="font-size:.73rem;color:#64748b;margin-top:.15rem">📍 <?=h($ev['location'])?></div><?php endif; ?>
    </div>
  </div>
  <?php endforeach; ?>
  </div>
  <?php endif; ?>
  <div style="text-align:center;margin-top:1.4rem">
    <a href="<?=url('modules/events.php')?>" style="display:inline-flex;align-items:center;gap:.4rem;background:#0d47a1;color:#fff;border-radius:25px;padding:.5rem 1.3rem;font-size:.82rem;font-weight:700;text-decoration:none">📅 View All Events →</a>
  </div>
</div>
</section>

<!-- ══ DIGITAL NOTICE BOARD ══ -->
<?php if(!empty($homeNotices)): ?>
<section style="padding:3.5rem 0;background:#0d1b3e;position:relative;overflow:hidden">
  <div style="position:absolute;inset:0;opacity:.04;background:repeating-linear-gradient(45deg,#fff 0,#fff 1px,transparent 0,transparent 50%);background-size:20px 20px"></div>
  <div class="container" style="max-width:1200px;position:relative;z-index:1">

    <!-- Header -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.4rem;padding:0 .5rem">
      <div>
        <div style="display:inline-flex;align-items:center;gap:.45rem;background:rgba(200,146,42,.15);
             border:1px solid rgba(200,146,42,.35);border-radius:30px;
             padding:.28rem 1rem;margin-bottom:.6rem">
          <span style="width:7px;height:7px;border-radius:50%;background:#f5d060;
                 animation:nbPulse 1.5s ease-in-out infinite;display:inline-block"></span>
          <span style="font-size:.67rem;font-weight:700;letter-spacing:.16em;
                 text-transform:uppercase;color:#e6b84a">Live Notices</span>
        </div>
        <h2 style="font-family:'Playfair Display',serif;font-size:clamp(1.6rem,3.5vw,2.2rem);
             font-weight:700;color:#fff;line-height:1.2">
          📢 Digital <span style="color:#f5d060">Notice Board</span>
        </h2>
      </div>
    </div>

    <!-- Ticker for urgent/emergency -->
    <?php $urgHN = array_filter($homeNotices, function($n){ return in_array($n['priority']??'',['urgent','emergency']); });
    if(!empty($urgHN)): ?>
    <div style="background:linear-gradient(135deg,#b71c1c,#c62828);
         border-radius:14px;padding:.6rem 1rem;margin-bottom:1.1rem;
         display:flex;align-items:center;gap:.75rem;overflow:hidden">
      <span style="background:rgba(255,255,255,.2);border-radius:6px;
             padding:.14rem .55rem;font-size:.62rem;font-weight:800;
             color:#fff;white-space:nowrap;letter-spacing:.07em">🔴 URGENT</span>
      <div style="overflow:hidden;flex:1">
        <div style="display:flex;gap:2.5rem;white-space:nowrap;
             animation:nbScroll 16s linear infinite">
          <?php foreach(array_merge(array_values($urgHN),array_values($urgHN)) as $un): ?>
          <span style="font-size:.8rem;font-weight:700;color:#fff">
            <?= ($un['priority']=='emergency')?'🚨':'⚡' ?> <?= h($un['title']) ?>
          </span>
          <?php endforeach; ?>
        </div>
      </div>
    </div>
    <?php endif; ?>

    <!-- Notice cards grid -->
    <?php
    $hnConf = [
      'general'  => ['em'=>'📋','c'=>'#90caf9','bg'=>'rgba(144,202,249,.12)'],
      'match'    => ['em'=>'⚽','c'=>'#a5d6a7','bg'=>'rgba(165,214,167,.12)'],
      'meeting'  => ['em'=>'🤝','c'=>'#ffcc80','bg'=>'rgba(255,204,128,.12)'],
      'festival' => ['em'=>'🎭','c'=>'#ce93d8','bg'=>'rgba(206,147,216,.12)'],
      'blood'    => ['em'=>'🩸','c'=>'#ef9a9a','bg'=>'rgba(239,154,154,.12)'],
      'emergency'=> ['em'=>'🚨','c'=>'#ef5350','bg'=>'rgba(239,83,80,.15)'],
      'urgent'   => ['em'=>'⚠️','c'=>'#ffb74d','bg'=>'rgba(255,183,77,.12)'],
    ];
    ?>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:.85rem">
    <?php foreach($homeNotices as $hn):
      $hc = $hnConf[$hn['category']??'general'] ?? $hnConf['general'];
      $hdiff = time() - strtotime($hn['created_at']);
      $hago  = $hdiff<3600?floor($hdiff/60).'m ago':($hdiff<86400?floor($hdiff/3600).'h ago':date('d M',strtotime($hn['created_at'])));
    ?>
    <div style="background:<?= $hc['bg'] ?>;border:1px solid rgba(255,255,255,.1);
         border-radius:16px;padding:.9rem 1rem;
         transition:all .25s;cursor:default;
         <?= $hn['priority']=='emergency'?'border-color:rgba(239,83,80,.4);':''?>">
      <!-- Top row -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.55rem">
        <div style="display:flex;align-items:center;gap:.4rem">
          <span style="font-size:1.15rem"><?= $hc['em'] ?></span>
          <span style="font-size:.62rem;font-weight:800;color:<?= $hc['c'] ?>;
                 text-transform:uppercase;letter-spacing:.07em">
            <?= h($hn['category']??'General') ?>
          </span>
          <?php if($hn['is_pinned']): ?>
          <span style="font-size:.7rem">📌</span>
          <?php endif; ?>
        </div>
        <span style="font-size:.62rem;color:rgba(255,255,255,.4)"><?= $hago ?></span>
      </div>
      <!-- Title -->
      <div style="font-weight:800;font-size:.92rem;color:#fff;line-height:1.35;
           margin-bottom:<?= $hn['body']?'.35rem':'0' ?>">
        <?= h($hn['title']) ?>
      </div>
      <?php if($hn['body']): ?>
      <div style="font-size:.76rem;color:rgba(255,255,255,.6);line-height:1.55;
           display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">
        <?= h($hn['body']) ?>
      </div>
      <?php endif; ?>
      <?php if($hn['expires_at']): ?>
      <div style="margin-top:.45rem;font-size:.62rem;color:rgba(255,255,255,.35)">
        Expires: <?= date('d M Y', strtotime($hn['expires_at'])) ?>
      </div>
      <?php endif; ?>
    </div>
    <?php endforeach; ?>
    </div>

  </div>
</section>
<style>
@keyframes nbScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes nbPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.7)}}
</style>
<?php endif; ?>




<!-- ══ COMMITTEE / LEADERSHIP ══ -->
<?php if(!empty($committee)): ?>
<section style="padding:4rem 0 3.5rem;background:#fff">
  <div class="container" style="max-width:1200px">

    <!-- Section header -->
    <div style="text-align:center;margin-bottom:2rem" class="rv">
      <div style="display:inline-flex;align-items:center;gap:.45rem;
           background:rgba(13,71,161,.08);border:1px solid rgba(13,71,161,.2);
           border-radius:30px;padding:.28rem 1rem;margin-bottom:.7rem">
        <span style="font-size:.67rem;font-weight:700;letter-spacing:.16em;
               text-transform:uppercase;color:#0d47a1">Club Leadership</span>
      </div>
      <h2 style="font-family:'Playfair Display',serif;font-size:clamp(1.7rem,3.5vw,2.3rem);
           font-weight:700;color:#0d1b3e;line-height:1.2;margin-bottom:.4rem">
        Our <span style="color:#c8922a">Committee</span>
      </h2>
      <p style="font-size:.88rem;color:#64748b;max-width:400px;margin:0 auto">
        <?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?> · <?= h(setting('CLUB_PLACE','Vettikkattiri')) ?>, Kerala
      </p>
    </div>

    <!-- Leader cards grid -->
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));
         gap:1rem;padding:0 .5rem">
    <?php
    $roleConf = [
      'president'       => ['label'=>'President',       'color'=>'#b71c1c','bg'=>'#ffebee','border'=>'#ef9a9a','icon'=>'👑'],
      'vice_president'  => ['label'=>'Vice President',  'color'=>'#e65100','bg'=>'#fff3e0','border'=>'#ffcc80','icon'=>'⭐'],
      'secretary'       => ['label'=>'Secretary',       'color'=>'#0d47a1','bg'=>'#e3f2fd','border'=>'#90caf9','icon'=>'📋'],
      'joint_secretary' => ['label'=>'Jt. Secretary',   'color'=>'#1565c0','bg'=>'#e3f2fd','border'=>'#90caf9','icon'=>'📝'],
      'treasurer'       => ['label'=>'Treasurer',       'color'=>'#1b5e20','bg'=>'#e8f5e9','border'=>'#a5d6a7','icon'=>'💰'],
      'committee_member'=> ['label'=>'Committee',       'color'=>'#37474f','bg'=>'#eceff1','border'=>'#b0bec5','icon'=>'🤝'],
    ];
    foreach($committee as $ci=>$cm):
      $rc  = $roleConf[$cm['role']] ?? $roleConf['committee_member'];
      $pos = !empty($cm['committee_position']) ? $cm['committee_position'] : $rc['label'];
      $photo = !empty($cm['profile_photo']) ? getMemberPhoto($cm['profile_photo']) : '';
    ?>
    <div style="text-align:center;animation:cmFadeIn .5s <?= $ci*0.08 ?>s both"
         class="rv">
      <!-- Photo circle -->
      <div style="position:relative;display:inline-block;margin-bottom:.65rem">
        <div style="width:90px;height:90px;border-radius:50%;overflow:hidden;
             border:3px solid <?= $rc['border'] ?>;
             box-shadow:0 4px 18px rgba(0,0,0,.12);
             margin:0 auto;
             background:<?= $rc['bg'] ?>;
             display:flex;align-items:center;justify-content:center">
          <?php if($photo): ?>
          <img src="<?= $photo ?>" alt="<?= h($cm['name']) ?>"
               style="width:100%;height:100%;object-fit:cover;display:block">
          <?php else: ?>
          <span style="font-size:2rem;opacity:.6"><?= $rc['icon'] ?></span>
          <?php endif; ?>
        </div>
        <!-- Role badge -->
        <div style="position:absolute;bottom:-4px;left:50%;transform:translateX(-50%);
             background:<?= $rc['color'] ?>;color:#fff;
             border-radius:20px;padding:.1rem .5rem;
             font-size:.54rem;font-weight:800;letter-spacing:.04em;
             white-space:nowrap;border:2px solid #fff;
             box-shadow:0 2px 6px rgba(0,0,0,.15)">
          <?= $rc['icon'] ?> <?= h($rc['label']) ?>
        </div>
      </div>
      <!-- Name -->
      <div style="font-weight:800;font-size:.82rem;color:#0d1b3e;
           line-height:1.3;margin-bottom:.18rem;padding:0 .25rem">
        <?= h($cm['name']) ?>
      </div>
      <!-- Position if different from role -->
      <?php if(!empty($cm['committee_position']) && $cm['committee_position'] !== $rc['label']): ?>
      <div style="font-size:.66rem;color:#64748b;line-height:1.3">
        <?= h($cm['committee_position']) ?>
      </div>
      <?php endif; ?>
    </div>
    <?php endforeach; ?>
    </div>

  </div>
</section>
<style>
@keyframes cmFadeIn{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
</style>
<?php endif; ?>

<!-- ══ ACHIEVEMENTS SECTION ══ -->
<?php if(!empty($pubAch)): ?>
<!-- Achievement lightbox -->
<div id="achLB" style="display:none;position:fixed;inset:0;z-index:9500;background:rgba(0,0,0,.95);align-items:center;justify-content:center;flex-direction:column;padding:1rem" onclick="if(event.target===this)closeAchLB()">
  <button onclick="closeAchLB()" style="position:fixed;top:1rem;right:1rem;background:rgba(255,255,255,.15);border:1.5px solid rgba(255,255,255,.25);color:#fff;width:44px;height:44px;border-radius:50%;font-size:1.1rem;cursor:pointer">✕</button>
  <img id="achLBImg" src="" alt="" style="max-width:96vw;max-height:75vh;object-fit:contain;border-radius:12px;box-shadow:0 24px 80px rgba(0,0,0,.8)">
  <div id="achLBInfo" style="margin-top:1rem;text-align:center;max-width:420px">
    <div id="achLBMedal" style="font-size:2rem;margin-bottom:.4rem"></div>
    <div id="achLBTitle" style="font-weight:800;font-size:1rem;color:#fff;margin-bottom:.3rem"></div>
    <div id="achLBMember" style="font-size:.82rem;color:rgba(255,255,255,.55)"></div>
    <div id="achLBDate" style="font-size:.72rem;color:rgba(255,255,255,.35);margin-top:.2rem"></div>
  </div>
</div>

<section style="padding:4rem 0;background:linear-gradient(180deg,#0d1b3e 0%,#1a3a6b 100%);overflow:hidden">
  <div class="container" style="max-width:1200px">
    <div style="text-align:center;margin-bottom:2rem" class="rv">
      <div style="display:inline-flex;align-items:center;gap:.5rem;background:rgba(200,146,42,.15);border:1px solid rgba(200,146,42,.35);border-radius:30px;padding:.28rem 1rem;margin-bottom:.75rem">
        <span style="font-size:.68rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:#e6b84a">🏆 Club Achievements</span>
      </div>
      <h2 style="font-family:'Playfair Display',serif;font-size:clamp(1.7rem,3.5vw,2.4rem);font-weight:700;color:#fff;line-height:1.2;margin-bottom:.5rem">
        Celebrating Our <span style="color:#f5d060">Members</span>
      </h2>
      <p style="font-size:.9rem;color:rgba(255,255,255,.55);max-width:440px;margin:0 auto"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?> · Pride & Recognition</p>
    </div>

    <!-- Achievement cards grid -->
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:.85rem;padding:0 .5rem 1.2rem" id="achHomeGrid">
      <?php
      $achM=['gold'=>['🥇','linear-gradient(135deg,#f5d060,#c8922a,#e6b84a)','#5c3a00'],'silver'=>['🥈','linear-gradient(135deg,#d0d0d0,#8a8a8a,#c0c0c0)','#1a1a1a'],'bronze'=>['🥉','linear-gradient(135deg,#d4935a,#8b4513,#c87941)','#3a1500'],'special'=>['🏅','linear-gradient(135deg,#667eea,#764ba2,#a855f7)','#fff'],'participation'=>['🎖️','linear-gradient(135deg,#0d47a1,#1565c0,#1976d2)','#fff']];
      $achCats=['sports'=>'⚽','arts'=>'🎭','education'=>'📚','club'=>'🏛','special'=>'⭐'];
      foreach($pubAch as $paidx=>$pa):
        $pm  = $achM[$pa['medal_type']] ?? $achM['special'];
        $ppho= !empty($pa['uphoto']) ? getMemberPhoto($pa['uphoto']) : '';
        $pUrl= '';
        if(!empty($pa['image'])) $pUrl = (strpos($pa['image'],'/')!==false) ? url('assets/uploads/'.$pa['image']) : url('assets/uploads/achievements/'.$pa['image']);
        $catIcon = $achCats[$pa['category']] ?? '🏆';
      ?>
      <div class="ach-hp-card"
        data-img="<?=htmlspecialchars($pUrl,ENT_QUOTES)?>"
        data-medal="<?=$pm[0]?>"
        data-title="<?=htmlspecialchars($pa['title'],ENT_QUOTES)?>"
        data-member="<?=htmlspecialchars($pa['member_name'],ENT_QUOTES)?>"
        data-date="<?= $pa['achievement_date'] ? date('d M Y',strtotime($pa['achievement_date'])) : '' ?>"
        style="border-radius:16px;overflow:hidden;cursor:pointer;position:relative;aspect-ratio:3/4;box-shadow:0 8px 28px rgba(0,0,0,.3);transition:all .3s"
        onmouseover="this.style.transform='translateY(-5px) scale(1.02)';this.style.boxShadow='0 16px 48px rgba(0,0,0,.5)'"
        onmouseout="this.style.transform='';this.style.boxShadow='0 8px 28px rgba(0,0,0,.3)'">
        <!-- Background: photo or gradient -->
        <?php if($pUrl): ?>
        <img src="<?=$pUrl?>" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">
        <div style="position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,.1) 0%,transparent 35%,rgba(0,0,0,.85) 100%)"></div>
        <?php else: ?>
        <div style="position:absolute;inset:0;background:<?=$pm[1]?>"></div>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-55%);font-size:5rem;opacity:.2"><?=$pm[0]?></div>
        <?php endif; ?>
        <!-- Top badge -->
        <div style="position:absolute;top:.65rem;left:.65rem;display:flex;gap:.3rem;align-items:center">
          <span style="background:rgba(0,0,0,.4);backdrop-filter:blur(6px);color:#fff;border-radius:20px;padding:.18rem .6rem;font-size:.6rem;font-weight:800;display:flex;align-items:center;gap:.25rem">
            <?=$pm[0]?> <?=strtoupper($pa['medal_type'])?>
          </span>
        </div>
        <!-- Tap hint -->
        <div style="position:absolute;top:.65rem;right:.65rem;background:rgba(255,255,255,.15);border-radius:20px;padding:.2rem .5rem;font-size:.58rem;color:rgba(255,255,255,.7)">👁 Tap</div>
        <!-- Bottom info -->
        <div style="position:absolute;bottom:0;left:0;right:0;padding:.8rem .85rem">
          <div style="font-weight:800;font-size:.82rem;color:#fff;line-height:1.3;margin-bottom:.3rem;text-shadow:0 1px 4px rgba(0,0,0,.5)"><?=h($pa['title'])?></div>
          <div style="display:flex;align-items:center;gap:.35rem">
            <?php if($ppho): ?><img src="<?=$ppho?>" style="width:20px;height:20px;border-radius:50%;object-fit:cover;border:1.5px solid rgba(200,146,42,.6)"><?php endif; ?>
            <span style="font-size:.7rem;color:rgba(255,255,255,.75);font-weight:600"><?=h(mb_strimwidth($pa['member_name'],0,22,'…'))?></span>
            <span style="margin-left:auto;font-size:.68rem;color:rgba(255,255,255,.4)"><?=$catIcon?></span>
          </div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>

    <div style="text-align:center;margin-top:.5rem">
      <?php if(isLoggedIn()): ?>
      <a href="<?=url('modules/certificate.php')?>" style="display:inline-flex;align-items:center;gap:.5rem;background:linear-gradient(135deg,#c8922a,#e6b84a);color:#0d1b3e;border-radius:10px;padding:.65rem 1.6rem;font-family:'Inter',sans-serif;font-weight:700;font-size:.88rem;text-decoration:none;box-shadow:0 6px 22px rgba(200,146,42,.35)">🏆 View All Achievements</a>
      <?php else: ?>
      <button onclick="openModal('login')" style="background:linear-gradient(135deg,#c8922a,#e6b84a);color:#0d1b3e;border:none;border-radius:10px;padding:.65rem 1.6rem;font-family:'Inter',sans-serif;font-weight:700;font-size:.88rem;cursor:pointer;box-shadow:0 6px 22px rgba(200,146,42,.35)">🔐 Login to See All Achievements</button>
      <?php endif; ?>
    </div>
  </div>
</section>
<script>
// Achievement card click via delegated event
document.addEventListener('DOMContentLoaded',function(){
document.getElementById('achHomeGrid')&&document.getElementById('achHomeGrid').addEventListener('click',function(e){
  var card=e.target.closest('.ach-hp-card'); if(!card) return;
  var d=card.dataset;
  document.getElementById('achLBImg').src=d.img||'';
  document.getElementById('achLBImg').style.display=d.img?'block':'none';
  document.getElementById('achLBMedal').textContent=d.medal||'🏆';
  document.getElementById('achLBTitle').textContent=d.title||'';
  document.getElementById('achLBMember').textContent=d.member||'';
  document.getElementById('achLBDate').textContent=d.date||'';
  document.getElementById('achLB').style.display='flex';
  document.body.style.overflow='hidden';
});
});
function closeAchLB(){
  document.getElementById('achLB').style.display='none';
  document.body.style.overflow='';
}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeAchLB();});
</script>
<?php endif; ?>

<section id="gallery" class="sec">
<div class="container" style="max-width:1200px">
  <div class="text-center mb-4 rv">
    <div class="sec-label">Gallery</div>
    <h2 class="sec-title">Club <span style="color:var(--a-tx)">Moments</span></h2>
    <div class="sec-rule" style="margin:.75rem auto"></div>
    <p class="sec-sub" style="margin:0 auto .3rem">Memories from every event in <?= h(setting('CLUB_PLACE','Vettikkattiri')) ?></p>
    <p style="font-size:.78rem;color:var(--t3)"><i class="fas fa-hand-pointer" aria-hidden="true"></i> Hover to pause · Login to view full gallery</p>
  </div>
  <div class="gal-wrap rv">
    <div class="gal-track" id="galTrack">
      <?php
      // Double for seamless infinite loop
      $galAll = array_merge($galItems, $galItems);
      foreach($galAll as $gi):
      ?>
      <?php $isImg = ($gi['type']==='img'); $galIdx = array_search($gi, $galAll); ?>
      <div class="gal-cell" <?php if($isImg): ?>role="button" tabindex="0" aria-label="View photo: <?= h($gi['title']) ?>" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}" onclick="openLB('<?= addslashes(h($gi['src'])) ?>','<?= addslashes(h($gi['title'])) ?>')" style="cursor:pointer"<?php endif; ?>>
        <?php if($isImg): ?>
          <img src="<?= h($gi['src']) ?>" alt="<?= h($gi['title']) ?>" loading="lazy" onerror="this.parentNode.innerHTML='<div class=gal-cell-ph><div style=font-size:2rem>🖼️</div></div>'">
          <div class="gal-cell-ov" aria-hidden="true"><i class="fas fa-expand-alt"></i></div>
        <?php else: ?>
          <div class="gal-cell-ph">
            <div style="font-size:2.4rem"><?= $gi['em'] ?></div>
            <span style="font-size:.7rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.08em"><?= h($gi['title']) ?></span>
          </div>
        <?php endif; ?>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
  <div class="text-center mt-4 rv">
    <button onclick="openModal('login')" style="display:inline-flex;align-items:center;gap:.5rem;font-size:.86rem;font-weight:600;color:var(--p);background:rgba(26,58,107,.07);border:1.5px solid rgba(26,58,107,.14);padding:.65rem 1.4rem;border-radius:var(--rad-s);transition:all .25s;cursor:pointer;font-family:'Inter',sans-serif" onmouseover="this.style.background='var(--p)';this.style.color='#fff'" onmouseout="this.style.background='rgba(26,58,107,.07)';this.style.color='var(--p)'">
      <i class="fas fa-sign-in-alt"></i> Login to View Full Gallery
    </button>
  </div>
</div>
</section>

<!-- ══════════════════ HENNA FEST ══════════════════ -->
<?php
$_hShow = false;
$_hEntries = [];
$_hSettings = null;
$_hSiteUrl = rtrim(SITE_URL,'/');
$_hLoggedIn = !empty($_SESSION['user_id']);
$_hUid = $_hLoggedIn ? (int)$_SESSION['user_id'] : 0;
$_hMyVote = 0;
try {
  if (db()->query("SHOW TABLES LIKE 'henna_entries'")->fetch()) {
    $_hSettings = db()->query("SELECT * FROM henna_fest_settings LIMIT 1")->fetch();
    if ($_hSettings) {
      $_hEntries = db()->query("SELECT e.*,u.name member_name,u.profile_photo FROM henna_entries e JOIN users u ON u.id=e.member_id WHERE e.status='active' ORDER BY e.vote_count DESC, e.created_at ASC LIMIT 10")->fetchAll();
      if ($_hLoggedIn) {
        $mvs = db()->prepare("SELECT entry_id FROM henna_votes WHERE voter_id=? LIMIT 1");
        $mvs->execute([$_hUid]); $mv = $mvs->fetchColumn();
        $_hMyVote = $mv ? (int)$mv : 0;
      }
      $_hShow = true;
    }
  }
} catch(Exception $ex){}
?>
<?php if($_hShow):
  $_hTitle   = $_hSettings['event_title'] ?? 'Henna Fest';
  $_hVoting  = (bool)($_hSettings['voting_open'] ?? 0);
  $_hPoster  = $_hSettings['event_poster'] ?? '';
  $_hSponsor = $_hSettings['sponsor_name'] ?? '';
  $_hPrizes  = [$_hSettings['prize_1']??'',$_hSettings['prize_2']??'',$_hSettings['prize_3']??''];
  $_hClub    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
  $_hPlace   = setting('CLUB_PLACE','Vettikkattiri');
?>
<div class="kstripe"></div>
<section style="background:linear-gradient(160deg,#0d0800,#2D1B0E 30%,#4a1e0a 65%,#6b2c0f);padding:2rem .9rem 1.5rem">
<div style="max-width:560px;margin:0 auto">
  <div style="text-align:center;margin-bottom:1.2rem">
    <div style="font-size:2rem;margin-bottom:.25rem">&#127807;</div>
    <h2 style="font-family:'Playfair Display',serif;font-size:1.5rem;font-weight:700;color:#FFE082;margin:0 0 .2rem"><?php echo h($_hTitle); ?></h2>
    <p style="font-size:.7rem;color:rgba(255,255,255,.45);margin:0"><?php echo h($_hClub); ?> &middot; <?php echo h($_hPlace); ?></p>
    <?php if($_hSponsor): ?><div style="display:inline-block;margin-top:.35rem;background:rgba(255,105,180,.12);border:1px solid rgba(255,105,180,.3);border-radius:20px;padding:.18rem .65rem;font-size:.66rem;color:#ff69b4;font-weight:700">&#127885; <?php echo h($_hSponsor); ?></div><?php endif; ?>
  </div>
  <?php if($_hPoster): ?>
  <div style="border-radius:14px;overflow:hidden;margin-bottom:1rem;box-shadow:0 4px 20px rgba(0,0,0,.5);border:2px solid rgba(212,160,23,.3)">
    <img src="<?php echo h($_hSiteUrl.'/assets/uploads/henna/'.basename($_hPoster)); ?>" style="width:100%;max-height:260px;object-fit:cover;display:block" loading="lazy">
  </div>
  <?php endif; ?>
  <div style="text-align:center;margin-bottom:.8rem;padding:.4rem;border-radius:10px;font-size:.7rem;font-weight:700;<?php echo $_hVoting ? 'background:rgba(46,125,50,.25);color:#81c784;border:1px solid rgba(46,125,50,.35)' : 'background:rgba(183,28,28,.2);color:#ef9a9a;border:1px solid rgba(183,28,28,.3)'; ?>">
    <?php echo $_hVoting ? '&#10084; Liking is OPEN' : '&#128274; Liking is closed'; ?>
  </div>
  <?php if(array_filter($_hPrizes)):
    $top3h = array_slice($_hEntries,0,3);
    $mdls  = ['&#127941;','&#129352;','&#129353;'];
    $clrs  = ['#D4A017','#9e9e9e','#cd7f32'];
  ?>
  <div style="display:flex;gap:.45rem;margin-bottom:.9rem;overflow-x:auto;scrollbar-width:none">
    <?php foreach($_hPrizes as $pi=>$pn): if(!$pn) continue; $pw=$top3h[$pi]??null; ?>
    <div style="flex-shrink:0;min-width:130px;background:rgba(255,255,255,.06);border-radius:12px;padding:.5rem .65rem;border:1px solid rgba(212,160,23,.2)">
      <div style="font-size:.85rem;margin-bottom:.15rem"><?php echo $mdls[$pi]; ?></div>
      <div style="font-size:.7rem;font-weight:700;color:#FFE082;margin-bottom:.1rem"><?php echo h($pn); ?></div>
      <?php if($pw && $pw['vote_count']>0): ?>
      <div style="font-size:.6rem;color:rgba(255,255,255,.45)"><?php echo h($pw['member_name']); ?> &middot; <?php echo (int)$pw['vote_count']; ?> &#10084;</div>
      <?php else: ?><div style="font-size:.6rem;color:rgba(255,255,255,.25)">TBD</div><?php endif; ?>
    </div>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>
  <div style="font-family:'Bebas Neue',sans-serif;font-size:.82rem;letter-spacing:.12em;color:rgba(255,255,255,.4);margin-bottom:.5rem">&#127942; TOP ENTRIES</div>
  <?php if(!empty($_hEntries)): ?>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
    <?php foreach($_hEntries as $_hr=>$_hE):
      $_hFid2 = (int)($_hE['fest_id']??1);
      $_hImg  = $_hSiteUrl.'/assets/uploads/henna/'.$_hFid2.'/'.basename($_hE['image_path']);
      $_hImgO = $_hSiteUrl.'/assets/uploads/henna/'.basename($_hE['image_path']);
      $_hPhot = $_hE['profile_photo'] ? $_hSiteUrl.'/'.ltrim($_hE['profile_photo'],'/') : '';
      $_hMine = $_hUid && (int)$_hE['member_id']===$_hUid;
      $_hLkd  = $_hMyVote && $_hMyVote===(int)$_hE['id'];
      $_hCan  = $_hLoggedIn && $_hVoting && !$_hMyVote && !$_hMine;
      $_hBord = $_hLkd?'#C4521A':($_hr===0?'#D4A017':($_hr===1?'#9e9e9e':($_hr===2?'#cd7f32':'rgba(255,255,255,.08)')));
      $_hRBg  = $_hr===0?'#D4A017':($_hr===1?'#9e9e9e':'#cd7f32');
      $_hRClr = $_hr===0?'#000':'#fff';
      $eN = addslashes(h($_hE['member_name']));
      $eCan = $_hCan?'true':'false';
      $eLkd = $_hLkd?'true':'false';
    ?>
    <div style="border-radius:14px;overflow:hidden;background:rgba(255,255,255,.06);border:2px solid <?php echo $_hBord; ?>;cursor:pointer;position:relative"
         onclick="hPop(<?php echo (int)$_hE['id']; ?>,'<?php echo $eN; ?>','<?php echo h($_hImg); ?>','<?php echo h($_hImgO); ?>',<?php echo (int)$_hE['vote_count']; ?>,'<?php echo h($_hPhot); ?>',<?php echo $eLkd; ?>,<?php echo $eCan; ?>)">
      <div style="position:relative">
        <img src="<?php echo h($_hImg); ?>" style="width:100%;aspect-ratio:3/4;object-fit:cover;display:block" onerror="this.src='<?php echo h($_hImgO); ?>'" loading="lazy">
        <div style="position:absolute;top:5px;right:5px;background:rgba(255,255,255,.92);border-radius:20px;padding:.15rem .4rem;display:flex;align-items:center;gap:.15rem">
          <span style="font-size:.58rem">&#10084;</span><span style="font-size:.62rem;font-weight:800;color:#C4521A"><?php echo (int)$_hE['vote_count']; ?></span>
        </div>
        <?php if($_hr < 3 && $_hE['vote_count'] > 0): ?>
        <div style="position:absolute;top:5px;left:5px;background:<?php echo $_hRBg; ?>;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:900;color:<?php echo $_hRClr; ?>"><?php echo $_hr+1; ?></div>
        <?php endif; ?>
      </div>
      <div style="padding:.4rem .45rem;display:flex;align-items:center;gap:.3rem;background:rgba(0,0,0,.22)">
        <?php if($_hPhot): ?>
        <img src="<?php echo h($_hPhot); ?>" style="width:22px;height:22px;border-radius:50%;object-fit:cover;flex-shrink:0;border:1px solid rgba(255,255,255,.2)" onerror="this.style.display='none'">
        <?php else: ?>
        <div style="width:22px;height:22px;border-radius:50%;background:rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;font-size:.65rem;flex-shrink:0">&#127774;</div>
        <?php endif; ?>
        <div style="font-size:.62rem;font-weight:800;color:#FFE082;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><?php echo h($_hE['member_name']); ?></div>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
  <?php else: ?>
  <div style="text-align:center;padding:1.2rem;background:rgba(255,255,255,.05);border-radius:14px;border:1.5px dashed rgba(212,160,23,.3);margin-bottom:.8rem">
    <div style="font-size:1.5rem;margin-bottom:.3rem">&#127807;</div>
    <div style="font-size:.8rem;color:rgba(255,255,255,.5)">No entries yet. Be the first!</div>
  </div>
  <?php endif; ?>
  <div style="text-align:center;margin-top:1rem">
    <a href="<?php echo url('modules/henna_fest.php'); ?>" style="display:inline-flex;align-items:center;gap:.5rem;background:linear-gradient(135deg,#D4A017,#8B6914);color:#000;padding:.62rem 1.5rem;border-radius:25px;font-weight:800;font-size:.8rem;text-decoration:none;box-shadow:0 4px 16px rgba(212,160,23,.35)">
      &#127807; View All &amp; Submit Entry
    </a>
  </div>
</div>
</section>

<!-- Entry Popup -->
<div id="hPopEl" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:4000;align-items:flex-end;justify-content:center" onclick="if(event.target===this)hClose()">
<div style="background:#1a0d05;width:100%;max-width:520px;border-radius:24px 24px 0 0;max-height:92vh;overflow-y:auto">
  <div style="background:linear-gradient(135deg,#2D1B0E,#8B3A0F);padding:.65rem 1rem;border-radius:24px 24px 0 0;display:flex;align-items:center;gap:.5rem">
    <div id="hPopAv" style="width:34px;height:34px;border-radius:50%;overflow:hidden;flex-shrink:0;background:rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center"></div>
    <div style="flex:1;min-width:0"><div id="hPopNm" style="font-family:'Playfair Display',serif;font-size:.9rem;font-weight:700;color:#FFE082;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></div><div style="font-size:.6rem;color:rgba(255,255,255,.4)"><?php echo h($_hTitle); ?></div></div>
    <div style="text-align:right;flex-shrink:0"><div id="hPopVt" style="font-family:'Bebas Neue',sans-serif;font-size:1.5rem;color:#D4A017;line-height:1"></div><div style="font-size:.52rem;color:rgba(255,255,255,.4)">LIKES</div></div>
    <button onclick="hClose()" style="background:rgba(255,255,255,.15);border:none;border-radius:50%;width:28px;height:28px;color:#fff;cursor:pointer;flex-shrink:0">&#10005;</button>
  </div>
  <div style="background:#000"><img id="hPopIm" src="" style="width:100%;max-height:60vh;object-fit:contain;display:block"></div>
  <div style="padding:.8rem 1rem">
    <div id="hPopLW" style="margin-bottom:.55rem"></div>
    <button onclick="hShare()" style="width:100%;padding:.62rem;background:linear-gradient(135deg,#25d366,#128c7e);color:#fff;border:none;border-radius:12px;font-weight:800;font-size:.86rem;cursor:pointer">&#128154; Share on WhatsApp</button>
    <button onclick="hClose()" style="width:100%;padding:.48rem;margin-top:.35rem;background:rgba(255,255,255,.07);color:rgba(255,255,255,.55);border:none;border-radius:10px;font-size:.8rem;cursor:pointer">Close</button>
  </div>
</div>
</div>
<script>
var _hSelf = "<?php echo url('modules/henna_fest.php'); ?>";
var _hSite = "<?php echo $_hSiteUrl; ?>";
var _hClub2= <?php echo json_encode($_hClub); ?>;
var _hPlc  = <?php echo json_encode($_hPlace); ?>;
var _hTtl  = <?php echo json_encode($_hTitle); ?>;
var _hSpn  = <?php echo json_encode($_hSponsor); ?>;
var _hLgn  = <?php echo $_hLoggedIn ? 'true' : 'false'; ?>;
var _hCId=0,_hCNm='',_hCIm='',_hCIo='';
function hPop(id,nm,im,imo,lk,ph,lkd,can){
  _hCId=id;_hCNm=nm;_hCIm=im;_hCIo=imo;
  document.getElementById('hPopIm').src=im;
  document.getElementById('hPopIm').onerror=function(){this.src=imo;};
  document.getElementById('hPopNm').textContent=nm;
  document.getElementById('hPopVt').textContent=lk;
  var av=document.getElementById('hPopAv');
  av.innerHTML=ph?'<img src="'+ph+'" style="width:100%;height:100%;object-fit:cover">':'<span style="font-size:1.1rem">&#127774;</span>';
  var lw=document.getElementById('hPopLW');
  if(!_hLgn){
    lw.innerHTML='<button onclick="hClose();setTimeout(function(){openModal(\'login\');},200)" style="width:100%;padding:.6rem;background:linear-gradient(135deg,#8B3A0F,#C4521A);color:#fff;border:none;border-radius:12px;font-weight:800;cursor:pointer">&#10084; Login to Like</button>';
  } else if(lkd){
    lw.innerHTML='<button style="width:100%;padding:.6rem;background:rgba(196,82,26,.2);color:#C4521A;border:2px solid #C4521A;border-radius:12px;font-weight:800;font-size:.85rem">&#10003; You liked this!</button>';
  } else if(can){
    lw.innerHTML='<button onclick="hLike('+id+',this)" style="width:100%;padding:.62rem;background:linear-gradient(135deg,#8B3A0F,#C4521A);color:#fff;border:none;border-radius:12px;font-weight:800;font-size:.88rem;cursor:pointer">&#10084; Like This Design</button>';
  } else {
    lw.innerHTML='<button style="width:100%;padding:.6rem;background:rgba(255,255,255,.06);color:rgba(255,255,255,.4);border:none;border-radius:12px;font-size:.82rem">&#128274; Liking closed</button>';
  }
  document.getElementById('hPopEl').style.display='flex';
  document.body.style.overflow='hidden';
}
function hClose(){document.getElementById('hPopEl').style.display='none';document.body.style.overflow='';}
function hLike(eid,btn){
  btn.disabled=true;btn.textContent='...';
  var fd=new FormData();fd.append('action','vote');fd.append('entry_id',eid);
  fetch(_hSelf,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){btn.textContent='&#10003; Liked!';btn.style.background='rgba(196,82,26,.2)';btn.style.color='#C4521A';btn.style.border='2px solid #C4521A';setTimeout(function(){location.reload();},1200);}
    else{alert(res.msg);btn.disabled=false;btn.textContent='&#10084; Like This Design';}
  });
}
function hShare(){
  var og=_hSite+'/assets/uploads/henna/og/entry_'+_hCId+'.jpg';
  var cv=document.createElement('canvas'),ctx=cv.getContext('2d');
  fetch(og).then(function(r){return r.blob();}).then(function(blob){
    var u=URL.createObjectURL(blob),img=new Image();
    img.onload=function(){
      cv.width=img.width;cv.height=img.height;var W=img.width,H=img.height;
      ctx.drawImage(img,0,0,W,H);URL.revokeObjectURL(u);
      var bH=Math.round(H*.10),bY=H-bH;
      var bg=ctx.createLinearGradient(0,bY,W,bY+bH);bg.addColorStop(0,'rgba(45,27,14,.88)');bg.addColorStop(1,'rgba(92,42,15,.88)');
      ctx.fillStyle=bg;ctx.fillRect(0,bY,W,bH);ctx.fillStyle='rgba(212,160,23,.8)';ctx.fillRect(0,bY,W,3);
      var logo=new Image();logo.crossOrigin='anonymous';
      logo.onload=function(){wm(logo);};logo.onerror=function(){wm(null);};
      logo.src=_hSite+'/assets/logo.png';
      function wm(lg){
        if(lg){var lS=Math.round(bH*.72),lX=Math.round(W*.03),lY=bY+(bH-lS)/2;ctx.save();ctx.beginPath();ctx.arc(lX+lS/2,lY+lS/2,lS/2,0,Math.PI*2);ctx.clip();ctx.fillStyle='#fff';ctx.fillRect(lX,lY,lS,lS);ctx.drawImage(lg,lX,lY,lS,lS);ctx.restore();}
        var tX=Math.round(W*.16),f1=Math.round(bH*.36),f2=Math.round(bH*.24);
        ctx.font='bold '+f1+'px DM Sans,sans-serif';ctx.fillStyle='#fff';ctx.textBaseline='middle';ctx.fillText(_hClub2,tX,bY+bH*.34);
        ctx.font=f2+'px DM Sans,sans-serif';ctx.fillStyle='rgba(255,255,255,.72)';
        ctx.fillText('&#127807; '+_hCNm+' · '+_hTtl+(_hSpn?' · &#127885; '+_hSpn:''),tX,bY+bH*.72);
        cv.toBlob(function(b){
          var file=new File([b],'HennaFest.jpg',{type:'image/jpeg'});
          var link=_hSite+'/modules/henna_share.php?id='+_hCId;
          var msg='&#127807; '+_hTtl+'\n&#127752; by '+_hCNm+'\n'+_hClub2+', '+_hPlc+'\n\n&#10084; Like this!\n'+link;
          if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],text:msg});}
          else{var a=document.createElement('a');a.href=cv.toDataURL('image/jpeg',.92);a.download='HennaFest.jpg';a.click();setTimeout(function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');},700);}
        },'image/jpeg',.92);
      }
    };
    img.onerror=function(){URL.revokeObjectURL(u);window.open(_hSelf,'_blank');};
    img.src=u;
  }).catch(function(){window.open(_hSelf,'_blank');});
}
</script>
<?php endif; ?>

</main>
<!-- ══════════════════ FOOTER ══════════════════ -->
<div class="kstripe" aria-hidden="true"></div>
<footer id="footer">
<div class="foot-inner">
  <div class="row g-4">
    <!-- Brand -->
    <div class="col-sm-12 col-md-4">
      <div class="foot-logo">
        <?php if($logo): ?><img src="<?= $logo ?>" alt="" width="44" height="44"><?php else: ?><div class="foot-logo-ph" aria-hidden="true">⚜</div><?php endif; ?>
        <div><div class="foot-name"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></div><div class="foot-tag"><?= h(setting('CLUB_TAGLINE','Unity · Sports · Culture · Community')) ?></div></div>
      </div>
      <p style="font-size:.88rem;color:rgba(255,255,255,.78);line-height:1.7">Uniting <?= h(setting('CLUB_PLACE','Vettikkattiri')) ?> through sports, arts and community service.</p>
      <div style="display:flex;gap:.55rem;margin-top:.9rem">
        <?php
        // WhatsApp personal
        if($wa): ?>
        <a href="https://wa.me/<?= h($wa) ?>" target="_blank" rel="noopener" class="sicon" title="WhatsApp" aria-label="WhatsApp" style="background:#25d366;border-color:#25d366;color:#fff"><i class="fab fa-whatsapp" aria-hidden="true"></i></a>
        <?php endif; ?>
        <?php
        // Dynamic social icons from DB
        $footSocials = array();
        try {
            $fsrows = db()->query("SELECT setting_key,setting_value FROM club_settings WHERE setting_group='social' AND setting_value IS NOT NULL AND setting_value != ''")->fetchAll();
            foreach($fsrows as $fsr) $footSocials[$fsr['setting_key']] = $fsr['setting_value'];
        } catch(Exception $e){}
        $footIconMap = array(
            'social_wa_group'  => array('icon'=>'fab fa-whatsapp',  'color'=>'#128c7e','title'=>'WhatsApp Group'),
            'social_facebook'  => array('icon'=>'fab fa-facebook-f','color'=>'#1877f2','title'=>'Facebook'),
            'social_instagram' => array('icon'=>'fab fa-instagram', 'color'=>'#e1306c','title'=>'Instagram'),
            'social_youtube'   => array('icon'=>'fab fa-youtube',   'color'=>'#ff0000','title'=>'YouTube'),
            'social_twitter'   => array('icon'=>'fab fa-x-twitter', 'color'=>'#000',   'title'=>'X/Twitter'),
            'social_telegram'  => array('icon'=>'fab fa-telegram',  'color'=>'#0088cc','title'=>'Telegram'),
            'social_linkedin'  => array('icon'=>'fab fa-linkedin-in','color'=>'#0077b5','title'=>'LinkedIn'),
            'social_tiktok'    => array('icon'=>'fab fa-tiktok',    'color'=>'#010101','title'=>'TikTok'),
            'social_website'   => array('icon'=>'fas fa-globe',     'color'=>'#0d47a1','title'=>'Website'),
        );
        foreach($footIconMap as $fkey=>$finfo):
            if(empty($footSocials[$fkey])) continue;
        ?>
        <a href="<?= h($footSocials[$fkey]) ?>" target="_blank" rel="noopener" class="sicon" title="<?= h($finfo['title']) ?>" aria-label="<?= h($finfo['title']) ?>" style="background:<?= $finfo['color'] ?>;border-color:<?= $finfo['color'] ?>;color:#fff"><i class="<?= $finfo['icon'] ?>" aria-hidden="true"></i></a>
        <?php endforeach; ?>
      </div>
    </div>
    <!-- Quick Links -->
    <div class="col-6 col-md-2 offset-md-1">
      <div class="foot-col">
        <h5>Quick Links</h5>
        <a href="#hero">Home</a>
        <a href="#events">Events</a>
        <a href="#gallery">Gallery</a>
        <a href="<?= url('contact.php') ?>">Contact</a>
        <a href="#" role="button" onclick="openModal('login');return false">Member Login</a>
      </div>
    </div>
    <!-- Member -->
    <div class="col-6 col-md-2">
      <div class="foot-col">
        <h5>Members</h5>
        <a href="#" role="button" onclick="openModal('login');return false">Login</a>
        <a href="#" role="button" onclick="openModal('register');return false">Apply to Join</a>
        <a href="<?= url('dashboard.php') ?>">Dashboard</a>
        <a href="<?= url('modules/blood.php') ?>">Blood Hub</a>
        <a href="<?= url('modules/crowdfund.php') ?>">Donate</a>
      </div>
    </div>
    <!-- Contact -->
    <div class="col-sm-12 col-md-3">
      <div class="foot-col">
        <h5>Contact</h5>
        <p><i class="fas fa-map-marker-alt" aria-hidden="true" style="color:var(--a2);margin-right:.4rem"></i><?= h(setting('CLUB_PLACE','Vettikkattiri')) ?>, Kerala</p>
        <p style="margin-top:.4rem"><i class="fab fa-whatsapp" aria-hidden="true" style="color:#25d366;margin-right:.4rem"></i><?= h(setting('CLUB_PHONE','+919876543210')) ?></p>
        <a href="https://wa.me/<?= h($wa) ?>" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:.45rem;margin-top:.9rem;background:#157a3f;color:#fff;min-height:44px;padding:.52rem 1.1rem;border-radius:8px;font-size:.82rem;font-weight:700;transition:all .22s"><i class="fab fa-whatsapp" aria-hidden="true"></i> Chat on WhatsApp</a>
      </div>
    </div>
  </div>
</div>
<div class="foot-btm">© <?= date('Y') ?> <b style="color:var(--a2)"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></b> · <?= h(setting('CLUB_PLACE','Vettikkattiri')) ?> · Kerala · All rights reserved</div>
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
<?php
$_pLoggedIn  = !empty($_SESSION['user_id']);
$_pMarketUrl = url('modules/market.php');
$_pDashUrl   = url('dashboard.php');
$_pfeedUrl   = url('modules/feed.php');

?>
<style>
#pub-bnav{
  position:fixed;bottom:0;left:0;right:0;z-index:9999;
  background:#fff;border-top:1px solid #ececec;
  display:flex;align-items:stretch;
  box-shadow:0 -2px 16px rgba(0,0,0,.08);
  padding-bottom:env(safe-area-inset-bottom,0px)
}
.pbn{
  flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  min-height:58px;padding:.5rem .2rem .42rem;
  font-size:.7rem;font-weight:700;
  color:#fff;text-decoration:none;cursor:pointer;
  border:none;gap:.18rem;background:none;
  -webkit-tap-highlight-color:transparent;
  font-family:inherit;line-height:1;
  transition:transform .15s ease
}
.pbn:active{transform:scale(.9)}
.pbn span:last-child{color:#333}
.pbn:focus-visible{outline:3px solid var(--p2);outline-offset:-3px;border-radius:12px}

/* Icon chip — consistent size for all tabs */
.pbn-ico{
  font-size:1.25rem;line-height:1;
  width:38px;height:38px;
  display:flex;align-items:center;justify-content:center;
  border-radius:12px;color:#fff;
  transition:transform .2s ease
}
.pbn:active .pbn-ico{transform:translateY(-2px)}

/* Gradient backgrounds per tab */
.pbn-login   .pbn-ico{background:linear-gradient(135deg,#07225c,#1565C0)}
.pbn-install .pbn-ico{background:linear-gradient(135deg,#6a1b9a,#8e24aa)}
.pbn-feed    .pbn-ico{background:linear-gradient(135deg,#e65100,#fb8c00)}
.pbn-mkt     .pbn-ico{background:linear-gradient(135deg,#1B5E20,#2E7D32)}

/* Sparkle feed icon — gentle float + scale */
.pbn-feed .pbn-ico{animation:feedFloat 2.2s ease-in-out infinite}
@keyframes feedFloat{
  0%,100%{transform:translateY(0) scale(1)}
  50%{transform:translateY(-3px) scale(1.08)}
}

/* Install icon — subtle attention pulse */
.pbn-install .pbn-ico{animation:instPulse 2.5s ease-in-out infinite}
@keyframes instPulse{
  0%,100%{box-shadow:0 0 0 0 rgba(142,36,170,.45)}
  50%{box-shadow:0 0 0 6px rgba(142,36,170,0)}
}

body{padding-bottom:calc(70px + env(safe-area-inset-bottom,0px))!important}
</style>

<nav id="pub-bnav" aria-label="Quick links">
  <?php if($_pLoggedIn): ?>
  <a href="<?php echo h($_pDashUrl); ?>" class="pbn pbn-login">
    <span class="pbn-ico" aria-hidden="true">&#127968;</span>
    <span>Dashboard</span>
  </a>
  <?php else: ?>
  <button type="button" class="pbn pbn-login" onclick="openModal('login')">
    <span class="pbn-ico" aria-hidden="true">&#128273;</span>
    <span>Login</span>
  </button>
  <?php endif; ?>

  <button type="button" class="pbn pbn-install" id="pwaNavBtn" onclick="pwaNavInstall()">
    <span class="pbn-ico" aria-hidden="true">&#128242;</span>
    <span>Install</span>
  </button>

  <a href="<?php echo h($_pfeedUrl); ?>" class="pbn pbn-feed">
    <span class="pbn-ico" aria-hidden="true">&#x2728;</span>
    <span>Feed</span>
  </a>

  <a href="<?php echo h($_pMarketUrl); ?>" class="pbn pbn-mkt">
    <span class="pbn-ico" aria-hidden="true">&#128717;</span>
    <span>Market</span>
  </a>
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
