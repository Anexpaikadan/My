<?php
// modules/certificate.php — Moments & Achievements System
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/upload_helper.php';
requireLogin();
$me      = currentUser();
$isAdmin = isAdminRole($me['role']) || isModuleAdmin('certificate', $me);
$uid     = $me['id'];
$pageTitle = 'Moments & Achievements — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');

// ── DB Setup ─────────────────────────────────────────────────────
try {
  db()->exec("CREATE TABLE IF NOT EXISTS achievements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT,
    member_name VARCHAR(150) NOT NULL,
    title VARCHAR(200) NOT NULL,
    category ENUM('sports','arts','education','club','special') DEFAULT 'sports',
    medal_type ENUM('gold','silver','bronze','special','participation') DEFAULT 'special',
    description TEXT,
    achievement_date DATE,
    image VARCHAR(500),
    status ENUM('active','inactive') DEFAULT 'active',
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )");
} catch(Exception $e){}
try { db()->exec("ALTER TABLE achievements ADD COLUMN status ENUM('active','inactive') DEFAULT 'active'"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE achievements ADD COLUMN member_id INT DEFAULT NULL"); } catch(Exception $e){}

$msg = null;
error_reporting(E_ALL);
ini_set('display_errors', '0'); // Log but don't display
ini_set('log_errors', '1');

// ── POST Handlers ─────────────────────────────────────────────────
if ($_SERVER['REQUEST_METHOD']==='POST') {

  if ($isAdmin && isset($_POST['save_achievement'])) {
    $img = handlePhotoUpload('ach_image','achievements');
    $mid = !empty($_POST['member_id']) ? (int)$_POST['member_id'] : null;
    // Auto-fill member name from users if ID selected
    $mname = trim($_POST['member_name']??'');
    if ($mid && !$mname) {
      $mu = db()->prepare("SELECT name FROM users WHERE id=?"); $mu->execute([$mid]); $mu=$mu->fetch();
      if ($mu) $mname = $mu['name'];
    }
    if (!empty($_POST['edit_id'])) {
      // Edit existing
      $eid = (int)$_POST['edit_id'];
      $oldImg = db()->prepare("SELECT image FROM achievements WHERE id=?")->execute([$eid]);
      if ($img) {
        db()->prepare("UPDATE achievements SET member_id=?,member_name=?,title=?,category=?,medal_type=?,description=?,achievement_date=?,status=?,image=? WHERE id=?")
           ->execute(array($mid,$mname,trim($_POST['title']),trim($_POST['category']),trim($_POST['medal_type']),trim($_POST['description']??''),$_POST['ach_date']??null,$_POST['ach_status']??'active',$img,$eid));
      } else {
        db()->prepare("UPDATE achievements SET member_id=?,member_name=?,title=?,category=?,medal_type=?,description=?,achievement_date=?,status=? WHERE id=?")
           ->execute(array($mid,$mname,trim($_POST['title']),trim($_POST['category']),trim($_POST['medal_type']),trim($_POST['description']??''),$_POST['ach_date']??null,$_POST['ach_status']??'active',$eid));
      }
      $msg = ['t'=>'ok','m'=>'✅ Achievement updated!'];
    } else {
      db()->prepare("INSERT INTO achievements(member_id,member_name,title,category,medal_type,description,achievement_date,image,status,created_by)VALUES(?,?,?,?,?,?,?,?,?,?)")
         ->execute(array($mid,$mname,trim($_POST['title']),trim($_POST['category']),trim($_POST['medal_type']),trim($_POST['description']??''),$_POST['ach_date']??null,$img,'active',$uid));
      $msg = ['t'=>'ok','m'=>'✅ Achievement added!'];
      $eid = (int)db()->lastInsertId();
    }
    // "Show on public website" switch
    require_once __DIR__ . '/../includes/site_schema.php'; site_tables();
    try { db()->prepare("UPDATE achievements SET show_public=? WHERE id=?")->execute(array(!empty($_POST['show_public']) ? 1 : 0, (int)$eid)); } catch(Exception $e){}
  }

  if ($isAdmin && isset($_POST['del_achievement'])) {
    require_once __DIR__ . '/../includes/sudo.php'; sudo_require();
    $eid = (int)$_POST['del_id'];
    db()->prepare("DELETE FROM achievements WHERE id=?")->execute([$eid]);
    $msg = ['t'=>'ok','m'=>'🗑 Achievement deleted.'];
  }

  // Share an achievement to the community feed (owner or admin)
  if (isset($_POST['share_ach_feed'])) {
    $eid = (int)$_POST['share_ach_id'];
    $own = db()->prepare("SELECT member_id FROM achievements WHERE id=?");
    $own->execute([$eid]); $ar = $own->fetch();
    if ($ar && ((int)$ar['member_id'] === (int)$uid || $isAdmin)) {
      $ffile = __DIR__.'/feed_hook.php';
      if (file_exists($ffile)) {
        require_once $ffile;
        if (function_exists('feed_add_achievement_post')) {
          $done = feed_add_achievement_post($eid);
          $msg = ['t'=>'ok','m'=>$done ? '📰 Shared to Community Feed!' : 'Already shared to feed earlier.'];
        }
      }
    } else {
      $msg = ['t'=>'err','m'=>'Not allowed.'];
    }
  }

  if ($isAdmin && isset($_POST['toggle_status'])) {
    $eid = (int)$_POST['tog_id'];
    db()->prepare("UPDATE achievements SET status=IF(status='active','inactive','active') WHERE id=?")->execute([$eid]);
    $msg = ['t'=>'ok','m'=>'✅ Visibility updated.'];
  }

  if (!empty($msg['m'])) { header('Location:'.url('modules/certificate.php').'?msg='.urlencode($msg['m']).'&mt='.$msg['t']); exit; }
}

if (isset($_GET['msg'])) $msg = ['t'=>$_GET['mt']??'ok','m'=>urldecode($_GET['msg'])];

// ── Filters ────────────────────────────────────────────────────────
$fCat   = $_GET['cat']??'';
$fMedal = $_GET['medal']??'';
$fSearch= trim($_GET['q']??'');
$fView  = $_GET['view']??'grid'; // grid or timeline

$where = ["1=1"];
$params= [];
if (!$isAdmin) { $where[]="a.status='active'"; }
$fMine  = isset($_GET['mine']) && $_GET['mine']==='1';
if ($fMine) { $where[]="a.member_id=?"; $params[]=$me['id']; }
// Get MY achievements count for badge
try {
    $myAchCount = (int)db()->prepare("SELECT COUNT(*) FROM achievements WHERE member_id=? AND status='active'")->execute([$me['id']]) ? db()->prepare("SELECT COUNT(*) FROM achievements WHERE member_id=? AND status='active'")->execute([$me['id']]) : 0;
    $myAchStmt = db()->prepare("SELECT COUNT(*) FROM achievements WHERE member_id=? AND status='active'");
    $myAchStmt->execute([$me['id']]);
    $myAchCount = (int)$myAchStmt->fetchColumn();
} catch(Exception $e){ $myAchCount = 0; }
if ($fCat)    { $where[]="category=?"; $params[]=$fCat; }
if ($fMedal)  { $where[]="medal_type=?"; $params[]=$fMedal; }
if ($fSearch) { $where[]="member_name LIKE ?"; $params[]="%$fSearch%"; }

$sql   = "SELECT a.*,u.profile_photo uphoto FROM achievements a LEFT JOIN users u ON u.id=a.member_id WHERE ".implode(' AND ',$where)." ORDER BY a.achievement_date DESC, a.created_at DESC";
try {
    $stmt  = db()->prepare($sql);
    $stmt->execute($params);
    $achievements = $stmt->fetchAll();
} catch(Exception $qe) {
    $achievements = [];
    $msg = ['t'=>'err','m'=>'Database error: '.h($qe->getMessage())];
}

// Members list for admin form
$members = [];
if ($isAdmin) {
  $members = db()->query("SELECT id,name FROM users WHERE status='active' ORDER BY name")->fetchAll();
}

// Edit mode
$editItem = null;
if ($isAdmin && isset($_GET['edit'])) {
  $es = db()->prepare("SELECT * FROM achievements WHERE id=?"); $es->execute([(int)$_GET['edit']]); $editItem = $es->fetch();
}

// Stats
$stats = array();
try {
  $statsRaw = db()->query("SELECT medal_type, COUNT(*) cnt FROM achievements WHERE status='active' GROUP BY medal_type")->fetchAll(PDO::FETCH_ASSOC);
  $stats = array();
  foreach($statsRaw as $sr) $stats[$sr['medal_type']] = $sr['cnt'];
} catch(Exception $e){ $stats = array(); }

$pageTitle = 'Moments & Achievements — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');
// Dynamic OG — personalized when viewing own achievements
$_og_mine = isset($_GET['mine']) && $_GET['mine']==='1';
if ($_og_mine) {
    // Get member's latest achievement for OG
    $_myAch = db()->prepare("SELECT * FROM achievements WHERE member_id=? AND status='active' ORDER BY achievement_date DESC LIMIT 1");
    $_myAch->execute([$me['id']]);
    $_myAch = $_myAch->fetch();
    $_ogImg = 'https://mynamecc.online/og_image.php';
    if ($_myAch && !empty($_myAch['image'])) {
        $_imgPath = (strpos($_myAch['image'],'/') !== false)
            ? $_myAch['image']
            : 'achievements/'.$_myAch['image'];
        $_ogImg = 'https://mynamecc.online/assets/uploads/'.$_imgPath;
    }
    $pageOG = [
        'title' => '🏆 '.$me['name'].' — Achievements | '.setting('CLUB_NAME','AASC'),
        'desc'  => '🎉 '.($me['name']).' has '.
                   (int)db()->prepare("SELECT COUNT(*) FROM achievements WHERE member_id=? AND status='active'")->execute([$me['id']])
                   .' achievements at '.setting('CLUB_NAME','Aishwarya Arts & Sports Club').', '.setting('CLUB_PLACE','Vettikkattiri'),
        'image' => $_ogImg,
        'url'   => 'https://mynamecc.online/modules/certificate.php?mine=1',
    ];
} else {
    $pageOG = [
        'title' => '🏆 Achievements — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club'),
        'desc'  => 'Member achievements and certificates — '.setting('CLUB_NAME','AASC').', '.setting('CLUB_PLACE','Vettikkattiri').', Kerala',
        'image' => 'https://mynamecc.online/og_image.php',
        'url'   => 'https://mynamecc.online/modules/certificate.php',
    ];
}
require_once __DIR__ . '/../includes/header.php';

// Medal config
$medals = [
  'gold'          => ['icon'=>'🥇','label'=>'Gold',    'bg'=>'linear-gradient(135deg,#f5d060,#c8922a,#e6b84a)','shadow'=>'rgba(200,146,42,.45)','text'=>'#5c3a00'],
  'silver'        => ['icon'=>'🥈','label'=>'Silver',  'bg'=>'linear-gradient(135deg,#d0d0d0,#8a8a8a,#c0c0c0)','shadow'=>'rgba(100,100,100,.35)','text'=>'#1a1a1a'],
  'bronze'        => ['icon'=>'🥉','label'=>'Bronze',  'bg'=>'linear-gradient(135deg,#d4935a,#8b4513,#c87941)','shadow'=>'rgba(139,69,19,.4)','text'=>'#3a1500'],
  'special'       => ['icon'=>'🏅','label'=>'Special', 'bg'=>'linear-gradient(135deg,#667eea,#764ba2,#a855f7)','shadow'=>'rgba(118,75,162,.4)','text'=>'#fff'],
  'participation' => ['icon'=>'🎖️','label'=>'Honor',  'bg'=>'linear-gradient(135deg,#0A14E0,#1A23C9,#0A14E0)','shadow'=>'rgba(10,20,224,.38)','text'=>'#fff'],
];
$cats = [
  'sports'    => ['icon'=>'⚽','label'=>'Sports',       'color'=>'#1b5e20','bg'=>'#e8f5e9'],
  'arts'      => ['icon'=>'🎭','label'=>'Arts',         'color'=>'#6a1b9a','bg'=>'#f3e5f5'],
  'education' => ['icon'=>'📚','label'=>'Education',    'color'=>'#0A14E0','bg'=>'#ECEEFF'],
  'club'      => ['icon'=>'🏛','label'=>'Club Activity','color'=>'#e65100','bg'=>'#fff3e0'],
  'special'   => ['icon'=>'⭐','label'=>'Special Award','color'=>'#b71c1c','bg'=>'#ffebee'],
];
?>

<style>
/* ══ ACHIEVEMENTS MODULE ══ */
.ach-hero{background:linear-gradient(135deg,#0B1033 0%,#121A5C 50%,#0A14E0 100%);padding:2.5rem 1.2rem 2rem;text-align:center;position:relative;overflow:hidden}
.ach-hero::before{content:'🏆';position:absolute;right:-1rem;top:-1rem;font-size:9rem;opacity:.07;transform:rotate(15deg)}
.ach-hero::after{content:'🥇';position:absolute;left:-1rem;bottom:-1rem;font-size:7rem;opacity:.07;transform:rotate(-15deg)}
.ach-hero h1{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.68rem;letter-spacing:.01em;color:#fff;margin-bottom:.3rem}
.ach-hero h1 span{color:#f5d060}
.ach-hero p{color:rgba(255,255,255,.62);font-size:.85rem}

/* Stats bar */
.ach-stats{display:flex;gap:.6rem;justify-content:center;flex-wrap:wrap;margin-top:1.2rem}
.ach-stat{background:rgba(255,255,255,.12);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.18);border-radius:12px;padding:.45rem 1rem;display:flex;align-items:center;gap:.4rem}
.ach-stat-num{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.04rem;color:#f5d060;line-height:1}
.ach-stat-lbl{font-size:.75rem;color:rgba(255,255,255,.6);font-weight:700;text-transform:uppercase;letter-spacing:.08em}

/* Filters */
.filter-bar{background:#fff;border-bottom:1px solid #E3E7F5;padding:.75rem 1rem;display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;position:sticky;top:60px;z-index:90;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.filter-pill{padding:.3rem .8rem;border-radius:20px;border:1.5px solid #ECEEFF;font-size:.75rem;font-weight:700;cursor:pointer;background:#fff;color:#0A14E0;transition:all .2s;white-space:nowrap;text-decoration:none;display:inline-block}
.filter-pill:hover,.filter-pill.on{background:#0A14E0;color:#fff;border-color:#0A14E0}
.filter-pill.gold-pill.on{background:linear-gradient(135deg,#c8922a,#e6b84a);border-color:#c8922a;color:#5c3a00}
.filter-pill.silver-pill.on{background:#8a8a8a;border-color:#8a8a8a;color:#fff}
.filter-pill.bronze-pill.on{background:#8b4513;border-color:#8b4513;color:#fff}

/* Achievement Cards */
.ach-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:1.2rem;padding:1.2rem}
@media(max-width:640px){.ach-grid{grid-template-columns:1fr;padding:.9rem}}

.ach-card{border-radius:18px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,.1);transition:all .3s;position:relative;background:#fff}
.ach-card:hover{transform:translateY(-6px);box-shadow:0 16px 48px rgba(0,0,0,.16)}
.ach-card.inactive-card{opacity:.55}

/* Card medal header */
.ach-medal-header{height:220px;position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}
.ach-medal-icon{font-size:4.5rem;z-index:2;filter:drop-shadow(0 4px 12px rgba(0,0,0,.3));animation:medalFloat 3s ease-in-out infinite}
@keyframes medalFloat{0%,100%{transform:translateY(0) rotate(-3deg)}50%{transform:translateY(-6px) rotate(3deg)}}
.ach-medal-header img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:1;z-index:3}
.ach-medal-header-overlay{position:absolute;inset:0;opacity:.85}

/* Card body */
.ach-card-body{padding:1.1rem 1.1rem 1.3rem}
.ach-member-row{display:flex;align-items:center;gap:.6rem;margin-bottom:.7rem}
.ach-member-photo{width:38px;height:38px;border-radius:50%;object-fit:cover;border:2px solid #ECEEFF;flex-shrink:0}
.ach-member-ph{width:38px;height:38px;border-radius:50%;background:#ECEEFF;border:2px solid #ECEEFF;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0}
.ach-member-name{font-weight:800;font-size:.9rem;color:#0B1033;line-height:1.2}
.ach-member-date{font-size:.75rem;color:#5d6b80}
.ach-title{font-family:'Playfair Display',serif;font-size:1rem;font-weight:700;color:#0B1033;margin-bottom:.45rem;line-height:1.35}
.ach-desc{font-size:.78rem;color:#64748b;line-height:1.55;margin-bottom:.7rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.ach-cat-badge{display:inline-flex;align-items:center;gap:.3rem;border-radius:20px;padding:.18rem .6rem;font-size:.75rem;font-weight:700;border:1px solid}
.ach-admin-btns{display:flex;gap:.35rem;margin-top:.75rem;padding-top:.65rem;border-top:1px solid #F5F7FF}
.ach-btn{padding:.3rem .7rem;border-radius:8px;border:none;font-size:.75rem;font-weight:700;cursor:pointer;transition:all .2s}

/* Timeline view */
.timeline{padding:1.2rem;max-width:680px;margin:0 auto}
.timeline-year{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.12rem;letter-spacing:.01em;color:#0A14E0;margin:1.5rem 0 .8rem;display:flex;align-items:center;gap:.6rem}
.timeline-year::after{content:'';flex:1;height:2px;background:linear-gradient(90deg,#0A14E0,transparent)}
.tl-item{display:flex;gap:1rem;margin-bottom:1.2rem;position:relative}
.tl-item::before{content:'';position:absolute;left:18px;top:38px;bottom:-14px;width:2px;background:linear-gradient(to bottom,#ECEEFF,transparent);z-index:0}
.tl-icon{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.3rem;flex-shrink:0;box-shadow:0 3px 12px rgba(0,0,0,.15);z-index:1;position:relative}
.tl-content{background:#fff;border-radius:14px;padding:.85rem 1rem;box-shadow:0 3px 14px rgba(0,0,0,.08);border-left:3px solid;flex:1}
.tl-content h4{font-weight:800;font-size:.9rem;color:#0B1033;margin-bottom:.2rem}
.tl-content .tl-sub{font-size:.75rem;color:#64748b;margin-bottom:.3rem}
.tl-content .tl-desc{font-size:.78rem;color:#64748b;line-height:1.5}

/* Admin form */
.ach-form-card{background:#fff;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,.09);overflow:hidden;margin-bottom:1.2rem}
.ach-form-header{padding:.85rem 1.1rem;display:flex;align-items:center;justify-content:space-between;cursor:pointer}
.fg2{display:grid;grid-template-columns:1fr 1fr;gap:.65rem;margin-bottom:.65rem}
@media(max-width:480px){.fg2{grid-template-columns:1fr}}
.inp2{width:100%;padding:.6rem .85rem;border:1.5px solid #ECEEFF;border-radius:9px;font-family:Inter,sans-serif;font-size:.86rem;color:#0B1033;outline:none;transition:border-color .2s;background:#f8fafc}
.inp2:focus{border-color:#0A14E0;background:#fff}
textarea.inp2{resize:vertical;min-height:70px}
.lbl2{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#64748b;display:block;margin-bottom:.28rem}
.btn-save{background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;border:none;border-radius:10px;padding:.7rem 1.6rem;font-family:Inter,sans-serif;font-weight:700;font-size:.88rem;cursor:pointer;box-shadow:0 4px 16px rgba(10,20,224,.3);transition:all .25s}
.btn-save:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(10,20,224,.4)}
</style>

<!-- HERO -->
<div class="ach-hero">
  <h1>🏆 MOMENTS & <span>ACHIEVEMENTS</span></h1>
  <p><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?> · Celebrating our members</p>
  <div class="ach-stats">
    <?php foreach(['gold'=>'🥇','silver'=>'🥈','bronze'=>'🥉','special'=>'🏅'] as $mk=>$mi):
      $cnt = $stats[$mk] ?? 0; if (!$cnt) continue;
    ?>
    <div class="ach-stat">
      <div class="ach-stat-num"><?=$cnt?></div>
      <div class="ach-stat-lbl"><?=$mi?> <?=ucfirst($mk)?></div>
    </div>
    <?php endforeach; ?>
    <div class="ach-stat">
      <div class="ach-stat-num"><?=count($achievements)?></div>
      <div class="ach-stat-lbl">Total</div>
    </div>
  </div>
</div>
<div class="red-bar"></div>

<?php if (!empty($msg['m'])): ?>
<div style="margin:1rem;background:<?=$msg['t']==='ok'?'#f0fdf4':'#fff0f0'?>;border:1.5px solid <?=$msg['t']==='ok'?'#bbf7d0':'#fecaca'?>;color:<?=$msg['t']==='ok'?'#166534':'#991b1b'?>;border-radius:10px;padding:.75rem 1rem;font-weight:700;font-size:.88rem">
  <?= h($msg['m']) ?>
</div>
<?php endif; ?>

<!-- ADMIN: ADD / EDIT FORM -->
<?php if ($isAdmin): ?>
<div class="ach-form-card" style="margin:1rem 1rem 0">
  <div class="ach-form-header" onclick="toggleForm()" style="background:linear-gradient(135deg,#0A14E0,#1A23C9)">
    <span style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#fff">
      <?= $editItem ? '✏️ EDIT ACHIEVEMENT' : '➕ ADD NEW ACHIEVEMENT' ?>
    </span>
    <span id="formArrow" style="color:rgba(255,255,255,.7);font-size:.8rem"><?= $editItem?'▲':'▼' ?></span>
  </div>
  <div id="achFormBody" style="display:<?= $editItem?'block':'none' ?>;padding:1.1rem">
    <form method="POST" action="<?=url('modules/certificate.php')?>" enctype="multipart/form-data">
      <?php if ($editItem): ?>
        <input type="hidden" name="edit_id" value="<?=$editItem['id']?>">
      <?php endif; ?>

      <div class="fg2">
        <div>
          <label class="lbl2">Select Member</label>
          <select name="member_id" class="inp2" onchange="fillName(this)">
            <option value="">— Type name below or select —</option>
            <?php foreach ($members as $m): ?>
            <option value="<?=$m['id']?>" <?=($editItem&&$editItem['member_id']==$m['id'])?'selected':''?>><?=h($m['name'])?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div>
          <label class="lbl2">Member Name *</label>
          <input type="text" name="member_name" class="inp2" required placeholder="Full name" value="<?=h($editItem['member_name']??'')?>">
        </div>
        <div>
          <label class="lbl2">Achievement Title *</label>
          <input type="text" name="title" class="inp2" required placeholder="e.g. Best Player – Football" value="<?=h($editItem['title']??'')?>">
        </div>
        <div>
          <label class="lbl2">Date</label>
          <input type="date" name="ach_date" class="inp2" value="<?=$editItem['achievement_date']??date('Y-m-d')?>">
        </div>
        <div>
          <label class="lbl2">Category</label>
          <select name="category" class="inp2">
            <?php foreach ($cats as $ck=>$cv): ?>
            <option value="<?=$ck?>" <?=($editItem['category']??'')===$ck?'selected':''?>><?=$cv['icon']?> <?=$cv['label']?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div>
          <label class="lbl2">Medal / Award Type</label>
          <select name="medal_type" class="inp2">
            <?php foreach ($medals as $mk=>$mv): ?>
            <option value="<?=$mk?>" <?=($editItem['medal_type']??'')===$mk?'selected':''?>><?=$mv['icon']?> <?=$mv['label']?></option>
            <?php endforeach; ?>
          </select>
        </div>
      </div>
      <div style="margin-bottom:.65rem">
        <label class="lbl2">Description</label>
        <textarea name="description" class="inp2" placeholder="Brief description of the achievement…"><?=h($editItem['description']??'')?></textarea>
      </div>
      <div style="margin-bottom:.9rem">
        <label class="lbl2">Photo / Certificate Image (optional)</label>
        <input type="file" name="ach_image" accept="image/*" style="width:100%;padding:.45rem;border:1.5px dashed #c7d2fe;border-radius:9px;font-size:.82rem">
      </div>
      <div class="form-check form-switch" style="margin-bottom:.9rem;display:flex;align-items:center;gap:.6rem;padding-left:0">
        <input class="form-check-input" type="checkbox" role="switch" name="show_public" value="1" id="achPub" style="width:2.8rem;height:1.5rem;margin:0;float:none"<?= (!$editItem || !isset($editItem['show_public']) || (int)$editItem['show_public'] === 1) ? ' checked' : '' ?>>
        <label class="form-check-label" for="achPub" style="font-weight:600">Show on public website</label>
      </div>
      <?php if ($editItem): ?>
      <div style="margin-bottom:.9rem;display:flex;align-items:center;gap:.5rem">
        <label class="lbl2" style="margin:0">Visibility:</label>
        <select name="ach_status" class="inp2" style="width:auto;min-width:120px">
          <option value="active" <?=($editItem['status']??'')==='active'?'selected':''?>>🟢 Public</option>
          <option value="inactive" <?=($editItem['status']??'')==='inactive'?'selected':''?>>🔴 Hidden</option>
        </select>
        <a href="<?=url('modules/certificate.php')?>" style="font-size:.78rem;color:#5d6b80;margin-left:.5rem">Cancel edit</a>
      </div>
      <?php endif; ?>
      <button type="submit" name="save_achievement" class="btn-save">
        <?= $editItem ? '💾 Update Achievement' : '🏆 Save Achievement' ?>
      </button>
    </form>
  </div>
</div>
<?php endif; ?>

<!-- MY ACHIEVEMENTS TAB -->
<div style="display:flex;align-items:center;gap:.5rem;padding:.6rem 1rem;background:#fff;border-bottom:1px solid #F5F7FF;overflow-x:auto;scrollbar-width:none">
  <a href="?<?= http_build_query(array_merge(array_diff_key($_GET,['mine'=>'']),[]) )?>"
     style="display:inline-flex;align-items:center;gap:.35rem;padding:.38rem .9rem;border-radius:20px;font-size:.78rem;font-weight:700;text-decoration:none;white-space:nowrap;border:1.5px solid;
     <?= !$fMine ? 'background:#0A14E0;color:#fff;border-color:#0A14E0' : 'background:#f8fafc;color:#64748b;border-color:#E3E7F5' ?>">
    🏆 All Achievements
  </a>
  <a href="?mine=1"
     style="display:inline-flex;align-items:center;gap:.35rem;padding:.38rem .9rem;border-radius:20px;font-size:.78rem;font-weight:700;text-decoration:none;white-space:nowrap;border:1.5px solid;
     <?= $fMine ? 'background:#0A14E0;color:#fff;border-color:#0A14E0' : 'background:#f8fafc;color:#64748b;border-color:#E3E7F5' ?>">
    ⭐ My Achievements
    <?php if($myAchCount > 0): ?>
    <span style="background:<?= $fMine ? 'rgba(255,255,255,.3)' : '#0A14E0' ?>;color:<?= $fMine ? '#fff' : '#fff' ?>;border-radius:20px;padding:.05rem .45rem;font-size:.75rem;font-weight:900"><?= $myAchCount ?></span>
    <?php endif; ?>
  </a>
</div>

<!-- FILTER BAR -->
<div class="filter-bar">
  <input type="text" id="searchQ" placeholder="🔍 Search member…" value="<?=h($fSearch)?>"
    style="padding:.38rem .85rem;border:1.5px solid #ECEEFF;border-radius:20px;font-size:16px;outline:none;min-width:0;flex:1;max-width:200px"
    oninput="filterCards()">
  <!-- Category pills -->
  <a href="?<?=http_build_query(array_merge($_GET,['cat'=>'','page'=>1]))?>" class="filter-pill <?=$fCat===''?'on':''?>">All</a>
  <?php foreach ($cats as $ck=>$cv): ?>
  <a href="?<?=http_build_query(array_merge($_GET,['cat'=>$ck]))?>" class="filter-pill <?=$fCat===$ck?'on':''?>"><?=$cv['icon']?> <?=$cv['label']?></a>
  <?php endforeach; ?>
  <!-- View toggle -->
  <div style="display:flex;gap:.3rem;margin-left:auto">
    <a href="?<?=http_build_query(array_merge($_GET,['view'=>'grid']))?>" class="filter-pill <?=$fView==='grid'?'on':''?>" title="Grid">⊞</a>
    <a href="?<?=http_build_query(array_merge($_GET,['view'=>'timeline']))?>" class="filter-pill <?=$fView==='timeline'?'on':''?>" title="Timeline">≡</a>
  </div>
</div>

<!-- Medal filter row -->
<div style="padding:.5rem 1rem;display:flex;gap:.4rem;overflow-x:auto;scrollbar-width:none;background:#f8fafc;border-bottom:1px solid #F5F7FF">
  <a href="?<?=http_build_query(array_merge($_GET,['medal'=>'']))?>" class="filter-pill <?=$fMedal===''?'on':''?>" style="font-size:.75rem">All Medals</a>
  <?php foreach ($medals as $mk=>$mv): ?>
  <a href="?<?=http_build_query(array_merge($_GET,['medal'=>$mk]))?>" class="filter-pill <?=$mk?>-pill <?=$fMedal===$mk?'on':''?>" style="font-size:.75rem"><?=$mv['icon']?> <?=$mv['label']?></a>
  <?php endforeach; ?>
</div>

<!-- EMPTY STATE -->
<?php if (empty($achievements)): ?>
<div style="text-align:center;padding:5rem 2rem;color:#5d6b80;background:#fff;min-height:300px">
  <div style="font-size:4.5rem;margin-bottom:1rem">🏆</div>
  <h3 style="font-size:1.1rem;color:#475569;margin-bottom:.4rem">No achievements yet</h3>
  <p style="font-size:.84rem">Member achievements and milestones will appear here.</p>
</div>

<!-- GRID VIEW -->
<?php elseif ($fView==='grid'): ?>
<div class="ach-grid" id="achGrid">
  <?php foreach ($achievements as $a):
    $m  = $medals[$a['medal_type']] ?? $medals['special'];
    $cv = $cats[$a['category']]     ?? $cats['special'];
    $photo = '';
    if (!empty($a['uphoto'])) $photo = getMemberPhoto($a['uphoto']);
  ?>
  <div class="ach-card <?= $a['status']==='inactive'?'inactive-card':'' ?>"
    data-name="<?=strtolower(h($a['member_name']))?>"
    data-cat="<?=h($a['category'])?>"
    data-medal="<?=h($a['medal_type'])?>">

    <!-- Medal header -->
    <?php $mStyle = isset($m['bg']) ? 'background:'.$m['bg'] : 'background:#0A14E0'; ?>
    <div class="ach-medal-header" style="<?=$mStyle?>">
      <?php if (!empty($a['image'])): ?>
      <?php
        $achImgUrl = (strpos($a['image'],'/') !== false)
          ? url('assets/uploads/'.$a['image'])
          : url('assets/uploads/achievements/'.$a['image']);
      ?>
      <img src="<?=$achImgUrl?>" alt="" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">
      <?php endif; ?>
      <?php if(empty($a['image'])): ?>
      <div class="ach-medal-header-overlay" style="background:<?=$m['bg']?>;opacity:.85"></div>
      <div class="ach-medal-icon"><?=$m['icon']?></div>
      <?php else: ?>
      <div style="position:absolute;bottom:0;left:0;right:0;height:50%;background:linear-gradient(transparent,rgba(0,0,0,.4));z-index:4"></div>
      <?php endif; ?>
      <?php if ($a['status']==='inactive'): ?>
      <div style="position:absolute;top:.5rem;right:.5rem;background:rgba(0,0,0,.5);color:#fff;border-radius:20px;padding:.15rem .55rem;font-size:.75rem;font-weight:700">Hidden</div>
      <?php endif; ?>
    </div>

    <!-- Body -->
    <div class="ach-card-body">
      <!-- Member row -->
      <div class="ach-member-row">
        <?php if ($photo): ?>
        <img src="<?=$photo?>" class="ach-member-photo" alt="">
        <?php else: ?>
        <div class="ach-member-ph">👤</div>
        <?php endif; ?>
        <div>
          <div class="ach-member-name"><?=h($a['member_name'])?></div>
          <div class="ach-member-date"><?= $a['achievement_date'] ? date('d M Y',strtotime($a['achievement_date'])) : '' ?></div>
        </div>
        <div style="margin-left:auto">
          <span class="ach-cat-badge" style="color:<?=$cv['color']?>;background:<?=$cv['bg']?>;border-color:<?=$cv['color']?>33"><?=$cv['icon']?> <?=$cv['label']?></span>
        </div>
      </div>

      <!-- Title -->
      <div class="ach-title"><?=h($a['title'])?></div>

      <!-- Description -->
      <?php if ($a['description']): ?>
      <div class="ach-desc"><?=h($a['description'])?></div>
      <?php endif; ?>

      <!-- Share button — show for own achievements -->
      <?php
        $achImgFull = '';
        if (!empty($a['image'])) {
          $achImgFull = (strpos($a['image'],'/') !== false)
            ? 'https://mynamecc.online/assets/uploads/'.$a['image']
            : 'https://mynamecc.online/assets/uploads/achievements/'.$a['image'];
        }
        $shareTitle = $a['title'].' — '.$a['member_name'];
        $shareDesc  = '🏆 '.$a['member_name'].' achieved '.h($a['title']).' | '.setting('CLUB_NAME','AASC').', '.setting('CLUB_PLACE','Vettikkattiri');
        $shareUrl   = 'https://mynamecc.online/modules/certificate.php?mine=1';
        $waMsg = '🏆 *'.setting('CLUB_NAME','Aishwarya Arts & Sports Club').'*'."\n"
                 . '📍 '.setting('CLUB_PLACE','Vettikkattiri')."\n"
                 . '━━━━━━━━━━━━━━━━━━━━━'."\n\n"
                 . '🎉 *Achievement Unlocked!*'."\n\n"
                 . '👤 *'.$a['member_name'].'*'."\n"
                 . '🏅 *'.$a['title'].'*'."\n"
                 . ($a['description'] ? '📝 '.$a['description']."\n" : '')
                 . ($a['achievement_date'] ? '📅 '.date('d M Y',strtotime($a['achievement_date']))."\n" : '')
                 . "\n🌐 https://mynamecc.online/modules/certificate.php?mine=1"
                 . ($achImgFull ? "\n".$achImgFull : '');
        $waUrl = 'https://wa.me/?text='.rawurlencode($waMsg);
      ?>
      <?php if ($a['member_id'] == $me['id'] || $isAdmin): ?>
      <div style="margin-top:.65rem;padding-top:.65rem;border-top:1px solid #F5F7FF">
        <div style="font-size:.75rem;font-weight:800;color:#5d6b80;letter-spacing:.08em;text-transform:uppercase;margin-bottom:.45rem">Share Achievement</div>
        <div style="display:flex;gap:.4rem;flex-wrap:wrap">
          <!-- WhatsApp Share -->
          <a href="<?= h($waUrl) ?>" target="_blank"
             style="display:inline-flex;align-items:center;gap:.3rem;padding:.38rem .75rem;background:#25d366;color:#fff;border-radius:8px;font-size:.75rem;font-weight:700;text-decoration:none">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="white"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
            WhatsApp
          </a>
          <!-- Copy Link -->
          <button onclick="copyAchLink('<?= h($shareUrl) ?>','<?= h(addslashes($shareTitle)) ?>')"
             style="display:inline-flex;align-items:center;gap:.3rem;padding:.38rem .75rem;background:#F5F7FF;color:#0A14E0;border:1px solid #ECEEFF;border-radius:8px;font-size:.75rem;font-weight:700;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif">
            🔗 Copy Link
          </button>
          <!-- Download Photo (if has image) -->
          <?php if($achImgFull): ?>
          <a href="<?= h($achImgFull) ?>" download target="_blank"
             style="display:inline-flex;align-items:center;gap:.3rem;padding:.38rem .75rem;background:#fff8e1;color:#e65100;border:1px solid #ffe082;border-radius:8px;font-size:.75rem;font-weight:700;text-decoration:none">
            📥 Photo
          </a>
          <!-- Native share WITH image -->
          <button onclick="shareAchImg('<?= h($achImgFull) ?>','<?= h(addslashes($shareDesc)) ?>','<?= h($shareUrl) ?>')"
             style="display:inline-flex;align-items:center;gap:.3rem;padding:.38rem .75rem;background:#e8f5e9;color:#1b5e20;border:1px solid #a5d6a7;border-radius:8px;font-size:.75rem;font-weight:700;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif">
            📤 Share Photo + Link
          </button>
          <?php endif; ?>
          <!-- Share to Community Feed -->
          <form method="POST" style="display:inline">
            <input type="hidden" name="share_ach_id" value="<?= (int)$a['id'] ?>">
            <button type="submit" name="share_ach_feed"
               style="display:inline-flex;align-items:center;gap:.3rem;padding:.38rem .75rem;background:#ECEEFF;color:#0A14E0;border:1px solid #B9BFFF;border-radius:8px;font-size:.75rem;font-weight:700;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif">
              📰 Share to Feed
            </button>
          </form>
        </div>
      </div>
      <?php endif; ?>

      <!-- Admin controls -->
      <?php if ($isAdmin): ?>
      <div class="ach-admin-btns" style="margin-top:.5rem">
        <a href="?edit=<?=$a['id']?>" class="ach-btn" style="background:#ECEEFF;color:#0A14E0">✏️ Edit</a>
        <form method="POST" style="display:inline" data-sudo data-confirm="Delete this achievement?">
          <input type="hidden" name="del_id" value="<?=$a['id']?>">
          <button type="submit" name="del_achievement" class="ach-btn" style="background:#ffebee;color:#b71c1c">🗑</button>
        </form>
        <form method="POST" style="display:inline">
          <input type="hidden" name="tog_id" value="<?=$a['id']?>">
          <button type="submit" name="toggle_status" class="ach-btn" style="background:#F5F7FF;color:#64748b" title="Toggle visibility">
            <?=$a['status']==='active'?'👁':'🙈'?>
          </button>
        </form>
      </div>
      <?php endif; ?>
    </div>
  </div>
  <?php endforeach; ?>
</div>

<!-- TIMELINE VIEW -->
<?php else: ?>
<div class="timeline" id="achTimeline">
  <?php
  $byYear = [];
  foreach ($achievements as $a) {
    $yr = $a['achievement_date'] ? date('Y',strtotime($a['achievement_date'])) : date('Y');
    $byYear[$yr][] = $a;
  }
  krsort($byYear);
  foreach ($byYear as $yr=>$items):
  ?>
  <div class="timeline-year"><?=$yr?></div>
  <?php foreach ($items as $a):
    $m  = $medals[$a['medal_type']] ?? $medals['special'];
    $cv = $cats[$a['category']]     ?? $cats['special'];
    $photo = '';
    if (!empty($a['uphoto'])) $photo = getMemberPhoto($a['uphoto']);
    $borderColor = str_replace(['linear-gradient(135deg,',')',',','#','0-9a-f ','   '], '', $m['bg']);
    // Extract first color from gradient for border
    preg_match('/#([0-9a-f]{6})/i', $m['bg'], $bm);
    $borderC = isset($bm[0]) ? $bm[0] : '#0A14E0';
  ?>
  <div class="tl-item" data-name="<?=strtolower(h($a['member_name']))?>" data-cat="<?=$a['category']?>">
    <?php $tiStyle = isset($m['bg']) ? 'background:'.$m['bg'] : 'background:#0A14E0'; ?>
    <div class="tl-icon" style="<?=$tiStyle?>">
      <span style="font-size:1.1rem"><?=$m['icon']?></span>
    </div>
    <div class="tl-content" style="border-left-color:<?=$borderC?>">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:.4rem;margin-bottom:.35rem;flex-wrap:wrap">
        <div style="display:flex;align-items:center;gap:.5rem">
          <?php if ($photo): ?><img src="<?=$photo?>" style="width:28px;height:28px;border-radius:50%;object-fit:cover;border:1.5px solid <?=$borderC?>"><?php endif; ?>
          <span style="font-weight:800;font-size:.85rem;color:#0B1033"><?=h($a['member_name'])?></span>
        </div>
        <div style="display:flex;align-items:center;gap:.35rem">
          <span class="ach-cat-badge" style="color:<?=$cv['color']?>;background:<?=$cv['bg']?>;border-color:<?=$cv['color']?>33;font-size:.75rem"><?=$cv['icon']?></span>
          <span style="font-size:.75rem;color:#94a3b8"><?=$a['achievement_date']?date('d M Y',strtotime($a['achievement_date'])):'—'?></span>
        </div>
      </div>
      <h4><?=h($a['title'])?></h4>
      <?php if ($a['description']): ?>
      <div class="tl-desc"><?=h($a['description'])?></div>
      <?php endif; ?>
      <?php if ($isAdmin): ?>
      <div style="display:flex;gap:.3rem;margin-top:.5rem">
        <a href="?edit=<?=$a['id']?>" class="ach-btn" style="background:#ECEEFF;color:#0A14E0;padding:.25rem .6rem;border-radius:7px;font-size:.75rem;font-weight:700;text-decoration:none">✏️</a>
        <form method="POST" style="display:inline" data-sudo data-confirm="Delete this achievement?">
          <input type="hidden" name="del_id" value="<?=$a['id']?>">
          <button name="del_achievement" style="background:#ffebee;color:#b71c1c;border:none;border-radius:7px;padding:.25rem .6rem;font-size:.75rem;font-weight:700;cursor:pointer">🗑</button>
        </form>
      </div>
      <?php endif; ?>
    </div>
  </div>
  <?php endforeach; endforeach; ?>
</div>
<?php endif; ?>

<script>
// Copy achievement link
function copyAchLink(url,title){
  var txt=title+'\n'+url;
  if(navigator.clipboard){navigator.clipboard.writeText(txt).then(function(){alert('🔗 Link copied!');});}
  else{prompt('Copy this link:',url);}
}

// Share achievement WITH the photo AND a link (native share sheet → WhatsApp/Instagram)
function shareAchImg(imgUrl,caption,link){
  var fullText = caption + (link ? '\n\n🌐 ' + link : '');
  if(!imgUrl){
    if(navigator.share){navigator.share({text:fullText, url:link||undefined});}
    else{window.open('https://wa.me/?text='+encodeURIComponent(fullText),'_blank');}
    return;
  }
  if(navigator.canShare){
    fetch(imgUrl).then(function(r){return r.blob();}).then(function(blob){
      var ext=(blob.type&&blob.type.indexOf('png')>-1)?'png':'jpg';
      var file=new File([blob],'achievement.'+ext,{type:blob.type||'image/jpeg'});
      if(navigator.canShare({files:[file]})){
        // share image + caption (link is inside the caption text so it travels with the photo)
        return navigator.share({files:[file],text:fullText,title:'Achievement'});
      } else {
        return navigator.share({text:fullText,url:link||undefined});
      }
    }).catch(function(){
      if(navigator.share) navigator.share({text:fullText,url:link||undefined});
      else window.open('https://wa.me/?text='+encodeURIComponent(fullText),'_blank');
    });
  } else {
    window.open('https://wa.me/?text='+encodeURIComponent(fullText),'_blank');
  }
}

// Toggle admin form
function toggleForm(){
  var b=document.getElementById('achFormBody');
  var a=document.getElementById('formArrow');
  if(b.style.display==='none'){b.style.display='block';if(a)a.textContent='▲';}
  else{b.style.display='none';if(a)a.textContent='▼';}
}

// Auto-fill member name from select
function fillName(sel){
  var opt = sel.options[sel.selectedIndex];
  var nameField = document.querySelector('[name="member_name"]');
  if(nameField && opt.value) nameField.value = opt.text;
}

// Live search/filter cards
function filterCards(){
  var q = (document.getElementById('searchQ').value||'').toLowerCase();
  document.querySelectorAll('#achGrid .ach-card, #achTimeline .tl-item').forEach(function(card){
    var name = card.dataset.name||'';
    card.style.display = (!q || name.indexOf(q)!==-1) ? '' : 'none';
  });
}
document.getElementById('searchQ')&&document.getElementById('searchQ').addEventListener('input',filterCards);
</script>

<?php require_once __DIR__ . '/../includes/footer.php'; ?>
