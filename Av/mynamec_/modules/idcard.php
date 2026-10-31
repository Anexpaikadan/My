<?php
// ============================================================
// idcard.php — Member ID Card + Volunteer System
// Clean rebuild — PHP 8.3 safe
// ============================================================
require_once __DIR__ . '/../includes/config.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '🪪 ID Card — Aishwarya Arts & Sports Club',
  'desc'  => 'Digital membership ID card — AASC, Vettikkattiri',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/idcard.php',
];
requireLogin();
$me = currentUser();

$uid = isset($_GET['id']) ? (int)$_GET['id'] : $me['id'];
if ($uid !== $me['id'] && !(isAdminRole($me['role']) || isModuleAdmin('idcard', $me))) {
    header('Location: ' . url('dashboard.php')); exit;
}

// ── Create volunteer table ──────────────────────────────────
try {
    db()->exec("CREATE TABLE IF NOT EXISTS event_volunteers(
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_id INT NOT NULL,
        user_id  INT NOT NULL,
        status   ENUM('pending','approved','rejected') DEFAULT 'pending',
        approved_by INT DEFAULT NULL,
        qr_token VARCHAR(64) DEFAULT NULL,
        applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_at TIMESTAMP NULL DEFAULT NULL,
        UNIQUE KEY uq_ev(event_id,user_id)
    )");
} catch(Exception $e){}

// ── Admin: verify volunteer QR via AJAX ─────────────────────
if (isset($_GET['verify_vol']) && (isAdminRole($me['role']) || isModuleAdmin('idcard', $me))) {
    header('Content-Type: application/json');
    $token = trim($_GET['verify_vol']);
    try {
        $v = db()->prepare("SELECT ev.*,u.name mname,u.blood_group mblood,e.title etitle,e.event_date edate,e.location eloc
            FROM event_volunteers ev
            JOIN users u ON u.id=ev.user_id
            JOIN events e ON e.id=ev.event_id
            WHERE ev.qr_token=? AND ev.status='approved' LIMIT 1");
        $v->execute([$token]); $v = $v->fetch();
        if ($v) echo json_encode(['ok'=>true,'data'=>$v]);
        else     echo json_encode(['ok'=>false,'msg'=>'Invalid or unapproved QR code']);
    } catch(Exception $e){ echo json_encode(['ok'=>false,'msg'=>$e->getMessage()]); }
    exit;
}

// ── Apply as volunteer ───────────────────────────────────────
if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_POST['apply_vol'])) {
    $eid = (int)($_POST['event_id'] ?? 0);
    if ($eid) {
        try {
            $tok = bin2hex(random_bytes(16));
            db()->prepare("INSERT IGNORE INTO event_volunteers(event_id,user_id,qr_token) VALUES(?,?,?)")
               ->execute([$eid, $me['id'], $tok]);
        } catch(Exception $e){}
        header('Location: ' . url('modules/idcard.php') . '?tab=volunteer&applied=1'); exit;
    }
}

// ── Admin approve / reject ───────────────────────────────────
if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_POST['vol_action']) && (isAdminRole($me['role']) || isModuleAdmin('idcard', $me))) {
    $vid = (int)($_POST['vol_id'] ?? 0);
    $act = $_POST['vol_action'];
    if ($vid && in_array($act, ['approved','rejected'])) {
        db()->prepare("UPDATE event_volunteers SET status=?,approved_by=?,approved_at=NOW() WHERE id=?")
           ->execute([$act, $me['id'], $vid]);
    }
    header('Location: ' . url('modules/idcard.php') . '?tab=admin_vol'); exit;
}

// ── Load user + subscription ─────────────────────────────────
try {
    // Check subscription_requests (approved) first, then subscriptions table
    $stmt = db()->prepare("SELECT u.*,
        COALESCE(
          (SELECT valid_until FROM subscription_requests
           WHERE user_id=u.id AND status='approved' AND valid_until>=CURDATE()
           ORDER BY valid_until DESC LIMIT 1),
          (SELECT valid_until FROM subscriptions
           WHERE user_id=u.id AND valid_until>=CURDATE()
           ORDER BY valid_until DESC LIMIT 1)
        ) AS sub_expiry
        FROM users u WHERE u.id=? LIMIT 1");
    $stmt->execute([$uid]); $user = $stmt->fetch();
} catch(Exception $e){
    $stmt = db()->prepare("SELECT * FROM users WHERE id=? LIMIT 1");
    $stmt->execute([$uid]); $user = $stmt->fetch();
}
if (!$user) { header('Location: ' . url('dashboard.php')); exit; }

$logoB64  = getLogoB64();
$photoB64 = getMemberPhoto($user['profile_photo'] ?? '');

$memberId = 'AV' . str_pad($user['id'], 4, '0', STR_PAD_LEFT);

// Subscription — ONLY show if active
$expiry    = !empty($user['sub_expiry']) ? $user['sub_expiry'] : null;
$hasActive = $expiry && strtotime($expiry) >= time();
$isExpired = $expiry && strtotime($expiry) < time();
$expiryFmt = $hasActive ? date('d M Y', strtotime($expiry)) : null;

$isActive  = $user['status'] === 'active';

$roleMap = ['president'=>'PRESIDENT','vice_president'=>'VICE PRESIDENT','secretary'=>'SECRETARY',
            'joint_secretary'=>'JOINT SECRETARY','treasurer'=>'TREASURER',
            'committee_member'=>'COMMITTEE MEMBER','member'=>'MEMBER'];
$roleLbl = $roleMap[$user['role']] ?? 'MEMBER';

// Role colour (text, light bg, border)
$rclr = match($user['role'] ?? '') {
    'president'        => ['#6A1B9A','#F3E5F5','#BA68C8'],
    'vice_president'   => ['#4527A0','#EDE7F6','#9575CD'],
    'secretary'        => ['#0A14E0','#ECEEFF','#A9B0FF'],
    'joint_secretary'  => ['#1A23C9','#ECEEFF','#B9BFFF'],
    'treasurer'        => ['#1B5E20','#E8F5E9','#81C784'],
    'committee_member' => ['#E65100','#FFF3E0','#FFCC80'],
    default            => ['#B71C1C','#FFEBEE','#EF9A9A'],
};

$profileUrl = SITE_URL . '/modules/profile.php?id=' . $user['id'];

// ── Volunteer data ───────────────────────────────────────────
$myVols = [];
try {
    $mv = db()->prepare("SELECT ev.*,e.title etitle,e.event_date edate,e.location eloc
        FROM event_volunteers ev JOIN events e ON e.id=ev.event_id
        WHERE ev.user_id=? AND ev.status='approved' ORDER BY e.event_date DESC");
    $mv->execute([$me['id']]); $myVols = $mv->fetchAll();
} catch(Exception $e){}

$myPending = [];
try {
    $mp = db()->prepare("SELECT ev.*,e.title etitle FROM event_volunteers ev JOIN events e ON e.id=ev.event_id WHERE ev.user_id=? AND ev.status='pending'");
    $mp->execute([$me['id']]); $myPending = $mp->fetchAll();
} catch(Exception $e){}

$upEvents = [];
try {
    $upEvents = db()->query("SELECT * FROM events WHERE event_date>=CURDATE() ORDER BY event_date LIMIT 8")->fetchAll();
} catch(Exception $e){}

$pendingVols = [];
if ((isAdminRole($me['role']) || isModuleAdmin('idcard', $me))) {
    try {
        $pv = db()->query("SELECT ev.*,u.name mname,u.blood_group mblood,u.role mrole,e.title etitle,e.event_date edate
            FROM event_volunteers ev JOIN users u ON u.id=ev.user_id JOIN events e ON e.id=ev.event_id
            WHERE ev.status='pending' ORDER BY ev.applied_at DESC");
        $pendingVols = $pv->fetchAll();
    } catch(Exception $e){}
}

$tab = $_GET['tab'] ?? 'card';
?>
<!DOCTYPE html>
<html lang="en">
<!-- OG meta for WhatsApp share -->
<head>
<meta property="og:type"        content="website">
<meta property="og:site_name"   content="Aishwarya Arts & Sports Club">
<meta property="og:title"       content="🪪 ID Card — Aishwarya Arts & Sports Club">
<meta property="og:description" content="Digital membership ID card — Aishwarya Arts & Sports Club, Vettikkattiri, Kerala">
<meta property="og:image"       content="<?= defined('LOGO_URL') ? LOGO_URL : 'https://mynamecc.online/assets/logo.jpg' ?>">
<meta property="og:image:width"  content="400">
<meta property="og:image:height" content="400">
<meta property="og:url"         content="<?= rtrim(defined('SITE_URL')?SITE_URL:'https://mynamecc.online', '/') . '/modules/idcard.php' ?>">
<meta name="twitter:card"       content="summary">
<meta name="twitter:image"      content="<?= defined('LOGO_URL') ? LOGO_URL : 'https://mynamecc.online/assets/logo.jpg' ?>">
</head>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>ID Card — <?= h($user['name']) ?> | <?= h(CLUB_NAME) ?></title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700;800;900&family=Montserrat:wght@700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{font-family:'Plus Jakarta Sans',sans-serif;background:#eef2f8;min-height:100vh;color:#1e293b}
body{padding:1.1rem 1rem 3rem;display:flex;flex-direction:column;align-items:center;gap:1rem}

.topbar{width:100%;max-width:600px;display:flex;align-items:center;justify-content:space-between}
.back{color:#475569;font-size:.82rem;font-weight:600;padding:.38rem .9rem;border:1.5px solid #cbd5e0;border-radius:8px;text-decoration:none;background:#fff;transition:all .18s}
.back:hover{border-color:#0A14E0;color:#0A14E0}

/* ── Tab bar ── */
.tabs{display:flex;background:#fff;border-radius:12px;padding:.3rem;gap:.2rem;box-shadow:0 2px 10px rgba(0,0,0,.08);width:100%;max-width:600px}
.tab-btn{flex:1;text-align:center;padding:.52rem .3rem;border-radius:9px;font-size:.75rem;font-weight:700;cursor:pointer;transition:all .2s;color:#64748b;border:none;background:none;font-family:'Plus Jakarta Sans',sans-serif;line-height:1.3}
.tab-btn.on{background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;box-shadow:0 3px 10px rgba(10,20,224,.3)}

.alert-ok{background:#f0fdf4;border:1.5px solid #bbf7d0;color:#16a34a;border-radius:10px;padding:.75rem 1rem;font-size:.86rem;font-weight:700;text-align:center;width:100%;max-width:600px}

/* ══════════════════════════════════════════
   ID CARD  — fixed 514×324px, JS-scaled
   ══════════════════════════════════════════ */
.card-viewport{width:100%;max-width:600px;display:flex;justify-content:center}
.card-scaler{position:relative;transform-origin:top center}

#idCard{
  width:514px; height:324px;
  background:#fff;
  border-radius:18px;
  overflow:hidden;
  position:relative;
  box-shadow:0 20px 60px rgba(0,0,0,.2), 0 0 0 1px rgba(0,0,0,.07);
}

/* Top 5-colour stripe */
.c-stripe-top{
  position:absolute;top:0;left:0;right:0;height:6px;z-index:20;
  background:linear-gradient(90deg,
    #b71c1c 0%,#d32f2f 18%,#ef5350 28%,
    #e8eef7 34%,#e8eef7 38%,
    #1A23C9 44%,#0A14E0 62%,#121A5C 80%,
    #b71c1c 100%);
}

/* Header — blue left, diagonal red right */
.c-header{
  position:absolute;top:6px;left:0;right:0;height:50px;z-index:10;
  overflow:hidden;
}
.c-hdr-blue{position:absolute;inset:0;background:linear-gradient(135deg,#0A14E0 0%,#1A23C9 100%)}
.c-hdr-red{position:absolute;top:0;right:0;bottom:0;width:42%;background:#c62828;clip-path:polygon(22% 0,100% 0,100% 100%,0 100%)}
.c-hdr-inner{position:absolute;inset:0;display:flex;align-items:center;gap:9px;padding:0 13px;z-index:5}
.c-logo{width:34px;height:34px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,.55);background:#fff;flex-shrink:0}
.c-logo-ph{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.18);border:2px solid rgba(255,255,255,.38);display:flex;align-items:center;justify-content:center;font-size:.88rem;color:#fff;flex-shrink:0}
.c-club{flex:1;min-width:0}
.c-club-name{font-family:'Bebas Neue',sans-serif;font-size:.82rem;letter-spacing:.12em;color:#fff;line-height:1;white-space:nowrap;overflow:hidden}
.c-club-sub{font-size:.5rem;color:rgba(255,255,255,.48);letter-spacing:.1em;text-transform:uppercase}
.c-mid{font-family:'Bebas Neue',sans-serif;font-size:.88rem;letter-spacing:.1em;color:#fff;background:rgba(0,0,0,.25);padding:.15rem .65rem;border-radius:20px;border:1px solid rgba(255,255,255,.22);flex-shrink:0}

/* White body */
.c-body{position:absolute;top:56px;left:0;right:0;bottom:32px;background:#fff;display:flex;overflow:hidden}

/* Left col */
.c-left{
  width:110px;flex-shrink:0;
  background:linear-gradient(170deg,#f8faff 0%,#eef2fa 100%);
  border-right:1px solid #e2e8f5;
  display:flex;flex-direction:column;align-items:center;
  padding:8px 6px 6px;gap:5px;
}
.c-photo{width:74px;height:82px;border-radius:9px;overflow:hidden;flex-shrink:0;
  border:2.5px solid #fff;box-shadow:0 3px 12px rgba(10,20,224,.18);
  background:linear-gradient(135deg,#ECEEFF,#D6DAFF)}
.c-photo img{width:100%;height:100%;object-fit:cover}
.c-photo-ph{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center}
.c-photo-ph-i{font-size:2rem;opacity:.3}
.c-memid{font-family:'Bebas Neue',sans-serif;font-size:.95rem;letter-spacing:.11em;color:#0A14E0;text-align:center;line-height:1}
.c-qr{width:62px;height:62px;border-radius:7px;background:#fff;padding:3px;
  box-shadow:0 2px 10px rgba(0,0,0,.13);border:1px solid #dde5f0;flex-shrink:0;overflow:hidden}
#mainQR{width:56px;height:56px;display:block}
#mainQR img,#mainQR canvas{width:56px!important;height:56px!important;display:block!important}
.c-qr-lbl{font-size:.42rem;color:#5d6b80;letter-spacing:.09em;text-transform:uppercase;text-align:center}

/* Right col */
.c-right{flex:1;padding:9px 12px 7px;display:flex;flex-direction:column;gap:4px;min-width:0;background:#fff}
.c-name{font-family:'Montserrat',sans-serif;font-size:1.28rem;font-weight:900;color:#0B1033;line-height:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.01em}
.c-badges{display:flex;align-items:center;gap:.35rem;flex-wrap:wrap}
.c-badge-role{display:inline-flex;align-items:center;gap:4px;padding:.18rem .62rem;border-radius:20px}
.c-badge-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.c-badge-txt{font-size:.57rem;font-weight:800;letter-spacing:.12em}
.c-badge-status{display:inline-flex;align-items:center;gap:4px;padding:.16rem .58rem;border-radius:20px}
.c-sep{height:1px;background:#f1f5f9;margin:2px 0}
.c-grid{display:grid;grid-template-columns:1fr 1fr;gap:3px 8px;flex:1}
.c-lbl{font-size:.44rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#5d6b80;margin-bottom:1px;line-height:1}
.c-val{font-size:.7rem;font-weight:700;color:#1e293b;line-height:1.2}
.c-val.blood{font-size:.88rem;font-weight:900;color:#dc2626}
.c-val.sub{color:#0A14E0;font-size:.67rem}
.c-val.exp{color:#dc2626;font-size:.58rem}
.c-val.nosub{color:#5d6b80;font-size:.58rem;font-style:italic;font-weight:500}
.c-full{grid-column:1/-1}
.c-sep-grid{grid-column:1/-1;height:1px;background:#f1f5f9;margin:1px 0}

/* Bottom accent line */
.c-accent-line{position:absolute;bottom:32px;left:0;right:0;height:2.5px;z-index:11;
  background:linear-gradient(90deg,#b71c1c,#ef5350,#fff8,#1A23C9,#0A14E0)}

/* Footer — red left diagonal, blue right */
.c-footer{position:absolute;bottom:0;left:0;right:0;height:32px;z-index:10;overflow:hidden}
.c-ftr-red{position:absolute;inset:0;background:#c62828}
.c-ftr-blue{position:absolute;top:0;right:0;bottom:0;width:60%;background:#0A14E0;clip-path:polygon(12% 0,100% 0,100% 100%,0 100%)}
.c-ftr-inner{position:absolute;inset:0;display:flex;align-items:center;justify-content:space-between;padding:0 14px;z-index:5}
.c-ftr-name{font-family:'Bebas Neue',sans-serif;font-size:.76rem;letter-spacing:.1em;color:#fff}
.c-ftr-role{font-family:'Bebas Neue',sans-serif;font-size:.7rem;letter-spacing:.12em;color:rgba(255,255,255,.85)}

/* ── Buttons ── */
.btns{display:flex;gap:.6rem;flex-wrap:wrap;justify-content:center;width:100%;max-width:600px}
.xbtn{flex:1;min-width:120px;display:inline-flex;align-items:center;justify-content:center;gap:.42rem;
  padding:.72rem 1rem;border-radius:10px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.84rem;
  cursor:pointer;border:none;transition:all .2s;text-decoration:none}
.xbtn:hover{transform:translateY(-2px)}
.xbtn-dl{background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;box-shadow:0 5px 16px rgba(10,20,224,.32)}
.xbtn-wa{background:linear-gradient(135deg,#1b5e20,#2e7d32);color:#fff;box-shadow:0 5px 16px rgba(27,94,32,.3)}
.xbtn-bk{background:#fff;color:#475569;border:1.5px solid #e2e8f0}
.hint{font-size:.72rem;color:#5d6b80;text-align:center;max-width:440px;width:100%}

/* ── Volunteer section ── */
.vsec{width:100%;max-width:600px}
.vsec-title{font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:.07em;color:#0A14E0;
  margin-bottom:.75rem;display:flex;align-items:center;gap:.6rem}
.vsec-title::after{content:'';flex:1;height:1.5px;background:linear-gradient(90deg,#0A14E0,transparent)}

/* Volunteer card */
.vol-card-wrap{background:linear-gradient(140deg,#0A14E0 0%,#1a237e 40%,#b71c1c 100%);
  border-radius:14px;padding:1.15rem;color:#fff;position:relative;overflow:hidden;margin-bottom:.75rem}
.vol-card-wrap::before{content:'VOLUNTEER';position:absolute;right:-10px;top:50%;
  transform:translateY(-50%) rotate(90deg);font-family:'Bebas Neue',sans-serif;
  font-size:2.8rem;letter-spacing:.15em;color:rgba(255,255,255,.05);pointer-events:none}
.vol-sub{font-size:.6rem;font-weight:700;letter-spacing:.15em;color:rgba(255,255,255,.45);text-transform:uppercase;margin-bottom:.2rem}
.vol-event{font-weight:900;font-size:1rem;margin-bottom:.35rem;line-height:1.25}
.vol-meta{font-size:.73rem;color:rgba(255,255,255,.65);margin-bottom:.75rem}
.vol-row{display:flex;align-items:center;gap:.85rem}
.vol-qr-box{width:66px;height:66px;background:#fff;border-radius:8px;padding:3px;flex-shrink:0;overflow:hidden}
.vol-info-name{font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:.06em}
.vol-info-sub{font-size:.68rem;color:rgba(255,255,255,.55);margin-top:.15rem}
.vol-dl-btn{display:inline-flex;align-items:center;gap:.38rem;background:rgba(255,255,255,.15);
  color:#fff;border:1px solid rgba(255,255,255,.28);border-radius:8px;
  padding:.4rem .9rem;font-size:.74rem;font-weight:700;cursor:pointer;
  margin-top:.65rem;font-family:'Plus Jakarta Sans',sans-serif;transition:all .2s}
.vol-dl-btn:hover{background:rgba(255,255,255,.25)}

.pend-card{background:#fff;border-radius:12px;padding:.9rem 1rem;box-shadow:0 2px 10px rgba(0,0,0,.07);
  border:1px solid #e2e8f0;margin-bottom:.6rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem}
.form-card{background:#fff;border-radius:14px;padding:1.1rem;box-shadow:0 3px 14px rgba(0,0,0,.07);border:1px solid #e2e8f0;margin-bottom:.75rem}
.flbl{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#475569;display:block;margin-bottom:.35rem}
.fsel{width:100%;padding:.65rem .9rem;border:1.5px solid #e2e8f0;border-radius:9px;
  font-family:'Plus Jakarta Sans',sans-serif;font-size:.88rem;color:#1e293b;background:#f8fafc;outline:none;margin-bottom:.75rem}
.fsel:focus{border-color:#0A14E0}
.sbtn{display:inline-flex;align-items:center;justify-content:center;gap:.4rem;width:100%;padding:.68rem 1rem;
  border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.86rem;cursor:pointer;border:none;transition:all .2s}
.sbtn-blue{background:#0A14E0;color:#fff}.sbtn-blue:hover{background:#1A23C9;transform:translateY(-1px)}
.sbtn-sm{padding:.38rem .78rem;font-size:.75rem;width:auto}
.sbtn-green{background:#1b5e20;color:#fff}.sbtn-red{background:#b71c1c;color:#fff}
.badge-pend{background:#fffbeb;border:1px solid #fde68a;color:#d97706;border-radius:20px;padding:.18rem .65rem;font-size:.66rem;font-weight:700}
.empty{text-align:center;padding:2rem;color:#5d6b80;font-size:.88rem}
.empty div{font-size:2.5rem;margin-bottom:.5rem}

/* Admin scan */
.scan-box{background:#0B1033;border-radius:14px;padding:1.2rem;text-align:center;color:#fff;width:100%;max-width:600px}
.scan-inp{width:100%;background:rgba(255,255,255,.1);border:1.5px solid rgba(255,255,255,.2);
  border-radius:9px;padding:.68rem 1rem;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;
  color:#fff;outline:none;text-align:center;letter-spacing:.1em;margin:.75rem 0}
.scan-inp::placeholder{color:rgba(255,255,255,.3)}
.scan-res{background:#fff;border-radius:10px;padding:1rem;margin-top:.75rem;display:none;text-align:left}
.scan-res.show{display:block}

/* Admin pending list */
.adm-row{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;
  gap:.5rem;padding:.72rem 0;border-bottom:1px solid #f1f5f9}
.adm-row:last-child{border:none}

/* Loading overlay */
.dl-ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:9999;
  align-items:center;justify-content:center;flex-direction:column;gap:.85rem}
.dl-ov.on{display:flex}
.spin{width:42px;height:42px;border:3.5px solid rgba(255,255,255,.2);border-top-color:#fff;border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
</style>
</head>
<body>

<div class="dl-ov" id="dlOv"><div class="spin"></div><p style="color:#fff;font-size:.88rem;font-weight:600">Generating…</p></div>

<div class="topbar">
  <a href="<?= url('dashboard.php') ?>" class="back">← Dashboard</a>
  <span style="font-size:.71rem;color:#94a3b8;font-weight:600;letter-spacing:.07em">MEMBER ID CARD</span>
</div>

<?php if(isset($_GET['applied'])): ?>
<div class="alert-ok">✅ Volunteer application submitted! Waiting for admin approval.</div>
<?php endif; ?>

<!-- Tab bar -->
<div class="tabs">
  <button class="tab-btn <?= $tab==='card'?'on':'' ?>" onclick="showTab('card',this)">🪪 ID Card</button>
  <button class="tab-btn <?= $tab==='volunteer'?'on':'' ?>" onclick="showTab('volunteer',this)">🙋 Volunteer</button>
  <?php if((isAdminRole($me['role']) || isModuleAdmin('idcard', $me))): ?>
  <button class="tab-btn <?= $tab==='admin_vol'?'on':'' ?>" onclick="showTab('admin_vol',this)">🛡 Approve<?php if(!empty($pendingVols)): ?> <span style="background:#ef5350;color:#fff;border-radius:20px;padding:0 .4rem;font-size:.6rem"><?= count($pendingVols) ?></span><?php endif; ?></button>
  <button class="tab-btn <?= $tab==='scan'?'on':'' ?>" onclick="showTab('scan',this)">📷 Scan</button>
  <?php endif; ?>
</div>

<!-- ══════ TAB: ID CARD ══════ -->
<div id="tab-card" style="display:<?= $tab==='card'?'contents':'none' ?>">

  <!-- Card viewport — JS scales the 514x324 card to fit screen -->
  <div class="card-viewport">
    <div class="card-scaler" id="cardScaler">
      <div id="idCard">
        <div class="c-stripe-top"></div>

        <!-- Header -->
        <div class="c-header">
          <div class="c-hdr-blue"></div>
          <div class="c-hdr-red"></div>
          <div class="c-hdr-inner">
            <?php if($logoB64): ?><img src="<?= $logoB64 ?>" class="c-logo" alt=""><?php else: ?><div class="c-logo-ph">⚜</div><?php endif; ?>
            <div class="c-club">
              <div class="c-club-name"><?= h(CLUB_NAME) ?></div>
              <div class="c-club-sub"><?= h(CLUB_PLACE) ?> · Kerala · India</div>
            </div>
            <div class="c-mid"><?= h($memberId) ?></div>
          </div>
        </div>

        <!-- Body -->
        <div class="c-body">
          <!-- Left -->
          <div class="c-left">
            <div class="c-photo">
              <?php if($photoB64): ?><img src="<?= $photoB64 ?>" alt=""><?php else: ?><div class="c-photo-ph"><div class="c-photo-ph-i">👤</div></div><?php endif; ?>
            </div>
            <div class="c-memid"><?= h($memberId) ?></div>
            <div class="c-qr"><div id="mainQR"></div></div>
            <div class="c-qr-lbl">Scan · Profile</div>
          </div>
          <!-- Right -->
          <div class="c-right">
            <div class="c-name"><?= h(mb_strtoupper($user['name'])) ?></div>
            <div class="c-badges">
              <div class="c-badge-role" style="background:<?= $rclr[1] ?>;border:1.5px solid <?= $rclr[2] ?>">
                <div class="c-badge-dot" style="background:<?= $rclr[0] ?>"></div>
                <span class="c-badge-txt" style="color:<?= $rclr[0] ?>"><?= h($roleLbl) ?></span>
              </div>
              <div class="c-badge-status" style="background:<?= $isActive?'#f0fdf4':'#fff0f0' ?>;border:1.5px solid <?= $isActive?'#bbf7d0':'#fecaca' ?>">
                <div class="c-badge-dot" style="background:<?= $isActive?'#16a34a':'#dc2626' ?>;<?= $isActive?'animation:pulse 1.5s ease-in-out infinite':'' ?>"></div>
                <span class="c-badge-txt" style="color:<?= $isActive?'#15803d':'#dc2626' ?>"><?= $isActive?'ACTIVE':'INACTIVE' ?></span>
              </div>
            </div>
            <div class="c-sep"></div>
            <div class="c-grid">
              <div>
                <div class="c-lbl">Blood Group</div>
                <div class="c-val blood"><?= h($user['blood_group'] ?: '—') ?></div>
              </div>
              <div>
                <div class="c-lbl">Skill / Sport</div>
                <div class="c-val"><?= h($user['skill'] ?: '—') ?></div>
              </div>
              <?php if(!empty($user['committee_position'])): ?>
              <div class="c-sep-grid"></div>
              <div>
                <div class="c-lbl">Position</div>
                <div class="c-val"><?= h($user['committee_position']) ?></div>
              </div>
              <div>
                <div class="c-lbl">Committee</div>
                <div class="c-val"><?= h($user['committee_name'] ?? '—') ?></div>
              </div>
              <?php endif; ?>
              <div class="c-sep-grid"></div>
              <div class="c-full">
                <div class="c-lbl">Subscription Valid Until</div>
                <?php if($expiryFmt): ?>
                  <div class="c-val sub">✅ <?= h($expiryFmt) ?></div>
                <?php elseif($isExpired): ?>
                  <div class="c-val exp">⚠️ Expired — Please Renew</div>
                <?php else: ?>
                  <div class="c-val nosub">No active subscription</div>
                <?php endif; ?>
              </div>
            </div>
          </div>
        </div>

        <div class="c-accent-line"></div>
        <!-- Footer -->
        <div class="c-footer">
          <div class="c-ftr-red"></div>
          <div class="c-ftr-blue"></div>
          <div class="c-ftr-inner">
            <div class="c-ftr-name"><?= h(mb_strtoupper($user['name'])) ?></div>
            <div class="c-ftr-role"><?= h($roleLbl) ?></div>
          </div>
        </div>
      </div><!-- /idCard -->
    </div><!-- /cardScaler -->
  </div><!-- /card-viewport -->

  <div class="btns">
    <button class="xbtn xbtn-dl" onclick="dlCard()">
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
      Download PNG
    </button>
    <button class="xbtn xbtn-wa" onclick="waShare()">
      <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
      WhatsApp
    </button>
    <a href="<?= url('dashboard.php') ?>" class="xbtn xbtn-bk">← Back</a>
  </div>
  <p class="hint">QR links to your profile · Download saves high-quality PNG</p>
</div>

<!-- ══════ TAB: VOLUNTEER ══════ -->
<div id="tab-volunteer" style="display:<?= $tab==='volunteer'?'contents':'none' ?>;flex-direction:column;align-items:center;gap:.75rem;width:100%;max-width:600px">

  <?php if(!empty($myVols)): ?>
  <div class="vsec">
    <div class="vsec-title">✅ MY VOLUNTEER CARDS</div>
    <?php foreach($myVols as $vi=>$vol):
      $vqid = 'vqr_'.$vol['id'];
      $vcid = 'vcard_'.$vol['id'];
    ?>
    <div class="vol-card-wrap" id="<?= $vcid ?>">
      <div class="vol-sub">🙋 VOLUNTEER — <?= h(CLUB_NAME) ?></div>
      <div class="vol-event"><?= h($vol['etitle']) ?></div>
      <div class="vol-meta">📅 <?= date('d M Y',strtotime($vol['edate'])) ?><?php if(!empty($vol['eloc'])): ?> · 📍 <?= h($vol['eloc']) ?><?php endif; ?></div>
      <div class="vol-row">
        <div class="vol-qr-box"><div id="<?= $vqid ?>"></div></div>
        <div style="display:flex;align-items:center;gap:.75rem;flex:1">
          <?php if($photoB64): ?>
          <img src="<?= $photoB64 ?>" style="width:54px;height:54px;border-radius:50%;object-fit:cover;border:2.5px solid rgba(255,255,255,.5);flex-shrink:0;box-shadow:0 3px 10px rgba(0,0,0,.3)">
          <?php else: ?>
          <div style="width:54px;height:54px;border-radius:50%;background:rgba(255,255,255,.15);border:2.5px solid rgba(255,255,255,.3);display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0">👤</div>
          <?php endif; ?>
          <div>
            <div class="vol-info-name"><?= h(mb_strtoupper($user['name'])) ?></div>
            <div class="vol-info-sub"><?= h($memberId) ?> · <?= h($roleLbl) ?></div>
            <div style="font-size:.6rem;color:rgba(255,255,255,.4);margin-top:.15rem">Scan QR for admin verification</div>
          </div>
        </div>
      </div>
    </div>
    <button onclick="dlVolCard('<?= $vcid ?>')" style="display:flex;align-items:center;justify-content:center;gap:.45rem;width:100%;padding:.72rem;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;border:none;border-radius:10px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.86rem;cursor:pointer;transition:all .2s;margin-bottom:1rem;box-shadow:0 4px 14px rgba(10,20,224,.3)">
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
      Download Volunteer Card
    </button>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>

  <?php if(!empty($myPending)): ?>
  <div class="vsec">
    <div class="vsec-title">⏳ PENDING APPLICATIONS</div>
    <?php foreach($myPending as $p): ?>
    <div class="pend-card">
      <div>
        <div style="font-weight:700;font-size:.9rem"><?= h($p['etitle']) ?></div>
        <div style="font-size:.74rem;color:#64748b;margin-top:.18rem">Awaiting admin approval</div>
      </div>
      <span class="badge-pend">⏳ Pending</span>
    </div>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>

  <div class="vsec">
    <div class="vsec-title">➕ APPLY AS VOLUNTEER</div>
    <?php if(!empty($upEvents)): ?>
    <div class="form-card">
      <form method="POST">
        <label class="flbl">Select Upcoming Event</label>
        <select name="event_id" class="fsel" required>
          <option value="">— Choose an upcoming event —</option>
          <?php foreach($upEvents as $ev): ?>
          <option value="<?= $ev['id'] ?>"><?= h($ev['title']) ?> · <?= date('d M Y',strtotime($ev['event_date'])) ?></option>
          <?php endforeach; ?>
        </select>
        <button type="submit" name="apply_vol" class="sbtn sbtn-blue">🙋 Submit Volunteer Application</button>
      </form>
      <p style="font-size:.74rem;color:#5d6b80;margin-top:.65rem">Admin will review. Once approved, your volunteer QR card appears above.</p>
    </div>
    <?php else: ?>
    <div class="empty"><div>📅</div>No upcoming events to volunteer for.</div>
    <?php endif; ?>
  </div>
</div>

<!-- ══════ TAB: ADMIN APPROVE ══════ -->
<?php if((isAdminRole($me['role']) || isModuleAdmin('idcard', $me))): ?>
<div id="tab-admin_vol" style="display:<?= $tab==='admin_vol'?'contents':'none' ?>;flex-direction:column;align-items:center;gap:.75rem;width:100%;max-width:600px">
  <div class="vsec">
    <div class="vsec-title">⏳ PENDING APPROVALS</div>
    <?php if(empty($pendingVols)): ?>
    <div class="empty"><div>✅</div>No pending volunteer applications.</div>
    <?php else: ?>
    <div class="form-card" style="padding:.75rem 1rem">
      <?php foreach($pendingVols as $pv): ?>
      <div class="adm-row">
        <div>
          <div style="font-weight:700;font-size:.88rem"><?= h($pv['mname']) ?></div>
          <div style="font-size:.74rem;color:#64748b;margin:.12rem 0"><?= h($pv['etitle']) ?> · <?= date('d M Y',strtotime($pv['edate'])) ?></div>
          <?php if($pv['mblood']): ?><div style="font-size:.68rem;color:#dc2626;font-weight:700">🩸 <?= h($pv['mblood']) ?></div><?php endif; ?>
        </div>
        <div style="display:flex;gap:.4rem">
          <form method="POST"><input type="hidden" name="vol_id" value="<?= $pv['id'] ?>"><button type="submit" name="vol_action" value="approved" class="sbtn sbtn-green sbtn-sm">✅ Approve</button></form>
          <form method="POST"><input type="hidden" name="vol_id" value="<?= $pv['id'] ?>"><button type="submit" name="vol_action" value="rejected" class="sbtn sbtn-red sbtn-sm">✗ Reject</button></form>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
  </div>
</div>

<!-- ══════ TAB: QR SCAN ══════ -->
<div id="tab-scan" style="display:<?= $tab==='scan'?'flex':'none' ?>;flex-direction:column;align-items:center;width:100%;max-width:600px;gap:.85rem">
  <div class="scan-box">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:.12em;margin-bottom:.2rem">📷 VOLUNTEER QR VERIFY</div>
    <div style="font-size:.78rem;color:rgba(255,255,255,.45);margin-bottom:.85rem">Use camera to scan volunteer QR code</div>

    <!-- Camera scanner -->
    <div id="camWrap" style="position:relative;width:100%;max-width:280px;margin:0 auto">
      <video id="camVideo" style="width:100%;border-radius:12px;display:none;background:#000" autoplay playsinline muted></video>
      <canvas id="camCanvas" style="display:none"></canvas>
      <!-- Scan frame overlay -->
      <div id="scanFrame" style="display:none;position:absolute;inset:0;border-radius:12px;pointer-events:none">
        <div style="position:absolute;top:15%;left:15%;right:15%;bottom:15%;border:2.5px solid #4fc3f7;border-radius:8px;box-shadow:0 0 0 9999px rgba(0,0,0,.45)"></div>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#4fc3f7;font-size:.72rem;font-weight:700;letter-spacing:.1em;text-shadow:0 1px 4px rgba(0,0,0,.8);white-space:nowrap;top:78%">POINT AT QR CODE</div>
      </div>
    </div>

    <button id="btnCamera" onclick="startCamera()" style="background:#1A23C9;color:#fff;border:none;border-radius:9px;padding:.65rem 1.4rem;font-family:Inter,sans-serif;font-weight:700;font-size:.86rem;cursor:pointer;display:inline-flex;align-items:center;gap:.45rem;margin:.6rem 0">
      <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>
      Open Camera to Scan
    </button>
    <button id="btnStop" onclick="stopCamera()" style="display:none;background:rgba(255,255,255,.1);color:#fff;border:1px solid rgba(255,255,255,.2);border-radius:9px;padding:.55rem 1.2rem;font-family:Inter,sans-serif;font-weight:700;font-size:.82rem;cursor:pointer;margin-bottom:.5rem">
      ✕ Stop Camera
    </button>

    <div style="color:rgba(255,255,255,.3);font-size:.74rem;margin:.4rem 0">— or paste token manually —</div>
    <input type="text" class="scan-inp" id="scanInp" placeholder="PASTE QR TOKEN HERE" oninput="doScan(this.value)">
    <div id="scanRes" class="scan-res"></div>
  </div>
</div>
<?php endif; ?>

<script>
// ── Tab switching ──────────────────────────────────────────
function showTab(name, btn) {
  var panels = document.querySelectorAll('[id^="tab-"]');
  panels.forEach(function(p) {
    p.style.display = 'none';
  });
  var active = document.getElementById('tab-' + name);
  if (active) {
    active.style.display = (name === 'card' || name === 'volunteer' || name === 'admin_vol') ? 'contents' : 'flex';
    if (name === 'volunteer' || name === 'admin_vol') {
      active.style.display = 'flex';
      active.style.flexDirection = 'column';
      active.style.alignItems = 'center';
      active.style.gap = '.75rem';
      active.style.width = '100%';
      active.style.maxWidth = '600px';
    }
  }
  document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('on'); });
  if (btn) btn.classList.add('on');
}

// ── Scale card to fit screen width ────────────────────────
function scaleCard() {
  var scaler = document.getElementById('cardScaler');
  var card   = document.getElementById('idCard');
  if (!scaler || !card) return;
  var avail = Math.min(514, window.innerWidth - 32);
  var scale = avail / 514;
  scaler.style.transform = 'scale(' + scale + ')';
  scaler.style.transformOrigin = 'top center';
  scaler.style.width = '514px';
  scaler.style.height = '324px';
  // Adjust wrapper height so buttons sit below card
  var viewport = document.querySelector('.card-viewport');
  if (viewport) viewport.style.height = Math.round(324 * scale) + 'px';
}
scaleCard();
window.addEventListener('resize', scaleCard);

// ── Generate main profile QR ──────────────────────────────
(function(){
  var el = document.getElementById('mainQR');
  if (!el) return;
  new QRCode(el, {
    text: '<?= addslashes($profileUrl) ?>',
    width: 56, height: 56,
    colorDark: '#0B1033', colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.M
  });
})();

// ── Generate volunteer QRs ────────────────────────────────
<?php foreach($myVols as $vol): ?>
(function(){
  var el = document.getElementById('<?= 'vqr_'.$vol['id'] ?>');
  if (!el) return;
  var url = '<?= addslashes(url('modules/idcard.php')) ?>?verify_vol=<?= urlencode($vol['qr_token']) ?>';
  new QRCode(el, {text:url, width:60, height:60, colorDark:'#0B1033', colorLight:'#ffffff', correctLevel:QRCode.CorrectLevel.M});
})();
<?php endforeach; ?>

// ── Download ID Card PNG ──────────────────────────────────
function dlCard() {
  var ov     = document.getElementById('dlOv');
  var card   = document.getElementById('idCard');
  var scaler = document.getElementById('cardScaler');
  ov.classList.add('on');

  // Temporarily reset scale to 1:1 for full-res capture
  var oldTr = scaler.style.transform;
  scaler.style.transform = 'scale(1)';
  scaler.style.transformOrigin = 'top left';

  setTimeout(function(){
    html2canvas(card, {
      scale: 4,
      useCORS: true,
      allowTaint: true,
      backgroundColor: '#ffffff',
      logging: false,
      width: 514,
      height: 324
    }).then(function(canvas){
      // Restore scale
      scaler.style.transform = oldTr;
      scaler.style.transformOrigin = 'top center';
      ov.classList.remove('on');
      var a = document.createElement('a');
      a.download = '<?= h($memberId) ?>_<?= h(preg_replace('/\s+/','_',$user['name'])) ?>_IDCard.png';
      a.href = canvas.toDataURL('image/png', 1.0);
      a.click();
    }).catch(function(e){
      scaler.style.transform = oldTr;
      ov.classList.remove('on');
      console.error(e);
      alert('Download failed. Please try again.');
    });
  }, 150);
}

// ── Download Volunteer Card ───────────────────────────────
function dlVolCard(id) {
  var ov = document.getElementById('dlOv');
  ov.classList.add('on');
  var card = document.getElementById(id);
  html2canvas(card, {scale:3, useCORS:true, allowTaint:true, logging:false})
  .then(function(canvas){
    ov.classList.remove('on');
    var a = document.createElement('a');
    a.download = '<?= h($memberId) ?>_VolunteerCard.png';
    a.href = canvas.toDataURL('image/png', 1.0);
    a.click();
  }).catch(function(){ ov.classList.remove('on'); alert('Download failed.'); });
}

// ── WhatsApp share ────────────────────────────────────────
function waShare() {
  var msg = '🪪 *<?= addslashes(mb_strtoupper(h($user['name']))) ?>*\n'
          + '<?= addslashes($roleLbl) ?> — <?= addslashes(CLUB_NAME) ?>\n'
          + 'ID: <?= $memberId ?>\n'
          <?php if($expiryFmt): ?>+ 'Valid: <?= addslashes($expiryFmt) ?>\n'<?php endif; ?>
          + 'Profile: <?= addslashes($profileUrl) ?>';
  window.open('https://wa.me/?text=' + encodeURIComponent(msg), '_blank');
}

// ── Admin QR Scan (paste token) ──────────────────────────
var scanTmr = null;
function doScan(v) {
  clearTimeout(scanTmr);
  if (v.length < 8) return;
  scanTmr = setTimeout(function(){ verifyToken(v); }, 500);
}

function verifyToken(token) {
  // Extract token from full URL if needed
  var t = token;
  var m = token.match(/verify_vol=([a-f0-9]+)/);
  if (m) t = m[1];

  var res = document.getElementById('scanRes');
  res.innerHTML = '<p style="color:#64748b;font-size:.82rem;padding:.5rem 0">⏳ Verifying…</p>';
  res.classList.add('show');

  fetch('?verify_vol=' + encodeURIComponent(t))
  .then(function(r){ return r.json(); })
  .then(function(d){
    if (d.ok) {
      var dat = d.data;
      res.innerHTML = '<div style="background:#f0fdf4;border:2px solid #16a34a;border-radius:10px;padding:1rem">'
        + '<div style="color:#16a34a;font-weight:900;font-size:1rem;margin-bottom:.6rem">✅ VALID VOLUNTEER</div>'
        + '<div style="display:flex;align-items:center;gap:.75rem">'
        + '<div style="font-size:2.5rem">🙋</div>'
        + '<div><div style="font-size:.92rem;font-weight:800;color:#0B1033">' + dat.mname + '</div>'
        + '<div style="font-size:.75rem;color:#475569;margin:.15rem 0">📅 ' + dat.etitle + '</div>'
        + '<div style="font-size:.75rem;color:#475569">' + dat.edate + '</div>'
        + (dat.mblood ? '<div style="font-size:.78rem;color:#dc2626;font-weight:700;margin-top:.2rem">🩸 Blood: ' + dat.mblood + '</div>' : '')
        + '</div></div></div>';
    } else {
      res.innerHTML = '<div style="background:#fff0f0;border:2px solid #dc2626;border-radius:10px;padding:.85rem;color:#dc2626;font-weight:700">❌ ' + (d.msg || 'Invalid or expired QR code') + '</div>';
    }
    stopCamera();
  }).catch(function(){
    res.innerHTML = '<div style="color:#dc2626;font-size:.82rem">Network error. Try again.</div>';
  });
}

// ── Camera QR Scanner ─────────────────────────────────────
var camStream = null;
var scanLoop  = null;
var jsqrReady = false;

// Pre-load jsQR immediately
(function(){
  var s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js';
  s.onload = function(){ jsqrReady = true; console.log('jsQR loaded'); };
  s.onerror = function(){
    // Fallback CDN
    var s2 = document.createElement('script');
    s2.src = 'https://unpkg.com/jsqr@1.4.0/dist/jsQR.js';
    s2.onload = function(){ jsqrReady = true; };
    document.head.appendChild(s2);
  };
  document.head.appendChild(s);
})();

function startCamera() {
  var video  = document.getElementById('camVideo');
  var frame  = document.getElementById('scanFrame');
  var btnCam = document.getElementById('btnCamera');
  var btnStp = document.getElementById('btnStop');
  var res    = document.getElementById('scanRes');

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    res.innerHTML = '<div style="background:#fff0f0;border:1.5px solid #fecaca;border-radius:8px;padding:.75rem;color:#dc2626;font-size:.82rem">❌ Camera not supported. Use Chrome on Android or Safari on iPhone. Or paste token below.</div>';
    res.classList.add('show');
    return;
  }

  // Request camera — prefer back camera on mobile
  var constraints = {
    video: {
      facingMode: { ideal: 'environment' },
      width:  { ideal: 1280 },
      height: { ideal: 720 }
    },
    audio: false
  };

  navigator.mediaDevices.getUserMedia(constraints)
  .then(function(stream) {
    camStream = stream;
    video.srcObject = stream;
    video.setAttribute('playsinline', true);
    video.setAttribute('muted', true);
    video.style.display = 'block';
    frame.style.display = 'block';
    btnCam.style.display = 'none';
    btnStp.style.display = 'inline-flex';
    if (res) { res.classList.remove('show'); res.innerHTML = ''; }

    video.onloadedmetadata = function() {
      video.play().then(function(){
        // Wait for jsQR then start scanning
        waitForJsQR(0);
      });
    };
  })
  .catch(function(err) {
    console.error('Camera error:', err);
    var msg = 'Camera access denied.';
    if (err.name === 'NotAllowedError') msg = '🔒 Camera permission denied. Please allow camera access in browser settings.';
    else if (err.name === 'NotFoundError') msg = '📷 No camera found on this device.';
    else if (err.name === 'NotReadableError') msg = '📷 Camera is in use by another app. Close it and try again.';
    res.innerHTML = '<div style="background:#fff0f0;border:1.5px solid #fecaca;border-radius:8px;padding:.75rem;color:#dc2626;font-size:.82rem">❌ ' + msg + '<br><br>You can paste the QR token in the field below instead.</div>';
    res.classList.add('show');
  });
}

function waitForJsQR(tries) {
  if (tries > 30) {
    console.error('jsQR failed to load');
    return;
  }
  if (typeof jsQR !== 'undefined') {
    jsqrReady = true;
    startScanLoop();
  } else {
    setTimeout(function(){ waitForJsQR(tries + 1); }, 200);
  }
}

function startScanLoop() {
  var video  = document.getElementById('camVideo');
  var canvas = document.getElementById('camCanvas');
  if (!video || !canvas) return;
  var ctx = canvas.getContext('2d');
  var frameEl = document.getElementById('scanFrame');
  var border  = frameEl ? frameEl.querySelector('div') : null;

  scanLoop = setInterval(function() {
    if (!video || video.readyState < 2 || video.paused || video.videoWidth === 0) return;

    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    try {
      var imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      var code = jsQR(imgData.data, imgData.width, imgData.height, {
        inversionAttempts: 'attemptBoth'
      });
      if (code && code.data && code.data.length > 0) {
        console.log('QR detected:', code.data);
        // Visual flash
        if (border) border.style.borderColor = '#00e676';
        setTimeout(function(){ if(border) border.style.borderColor = '#4fc3f7'; }, 600);
        // Stop loop and verify
        clearInterval(scanLoop); scanLoop = null;
        verifyToken(code.data);
      }
    } catch(e){ console.error('jsQR error:', e); }
  }, 250);
}

function stopCamera() {
  if (scanLoop) { clearInterval(scanLoop); scanLoop = null; }
  if (camStream) {
    camStream.getTracks().forEach(function(t){ t.stop(); });
    camStream = null;
  }
  var video  = document.getElementById('camVideo');
  var frame  = document.getElementById('scanFrame');
  var btnCam = document.getElementById('btnCamera');
  var btnStp = document.getElementById('btnStop');
  if (video)  { video.style.display = 'none'; video.srcObject = null; }
  if (frame)  frame.style.display = 'none';
  if (btnCam) { btnCam.style.display = 'inline-flex'; btnCam.style.alignItems = 'center'; }
  if (btnStp) btnStp.style.display = 'none';
}

// Stop camera when switching tabs
document.querySelectorAll('.tab-btn').forEach(function(b){
  b.addEventListener('click', stopCamera);
});
</script>
</body>
</html>
