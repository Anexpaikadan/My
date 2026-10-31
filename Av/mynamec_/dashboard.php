<?php
require_once __DIR__.'/includes/config.php';
requireLogin();
$user = currentUser();
$pageTitle = 'Home — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');

$stats = db()->query("SELECT COUNT(*) total,SUM(status='active') active,SUM(status='pending') pending,SUM(blood_group IS NOT NULL AND status='active') donors FROM users")->fetch();
// ── Notice board announcements ──────────────────────────────────
$notices = [];
try {
    $notices = db()->query("SELECT * FROM announcements
        WHERE (expires_at IS NULL OR expires_at >= CURDATE())
        ORDER BY is_pinned DESC, priority='emergency' DESC, priority='urgent' DESC, created_at DESC
        LIMIT 10")->fetchAll();
} catch(Exception $e){}
$annCatConf = array(
  'general'=>  array('em'=>'📣','color'=>'#0d47a1','bg'=>'rgba(13,71,161,.12)'),
  'match'=>    array('em'=>'⚽','color'=>'#a5d6a7','bg'=>'rgba(27,94,32,.18)'),
  'meeting'=>  array('em'=>'📋','color'=>'#cfd8dc','bg'=>'rgba(55,71,79,.18)'),
  'festival'=> array('em'=>'🎭','color'=>'#ce93d8','bg'=>'rgba(106,27,154,.18)'),
  'blood'=>    array('em'=>'🩸','color'=>'#ef9a9a','bg'=>'rgba(183,28,28,.18)'),
  'important'=>array('em'=>'⭐','color'=>'#ffcc80','bg'=>'rgba(230,81,0,.18)'),
);

// ── Ensure announcements columns exist ─────────────────
try { db()->exec("ALTER TABLE announcements ADD COLUMN category VARCHAR(40) DEFAULT 'general'"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE announcements ADD COLUMN expires_at DATE DEFAULT NULL"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE announcements ADD COLUMN priority ENUM('normal','urgent','emergency') DEFAULT 'normal'"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE announcements ADD COLUMN is_pinned TINYINT(1) DEFAULT 0"); } catch(Exception $e){}

// ── Notice Board announcements ─────────────────────────────
$notices = [];
try {
    $nstmt = db()->prepare("SELECT a.* FROM announcements a
        WHERE (a.expires_at IS NULL OR a.expires_at >= CURDATE())
        ORDER BY a.is_pinned DESC, a.created_at DESC LIMIT 10");
    $nstmt->execute(); $notices = $nstmt->fetchAll();
} catch(Exception $e){ $notices = []; }

// ── FIFA Prediction League data for dashboard ────────────────
$predLeague = ['active'=>false,'matches'=>[],'top3'=>[],'my'=>null,'upcoming'=>null];
try {
  // Check if table exists
  $tbl = db()->query("SHOW TABLES LIKE 'prediction_matches'")->fetch();
  if ($tbl) {
    $predLeague['active'] = true;
    // Top 3 leaderboard
    $predLeague['top3'] = db()->query("SELECT u.id,u.name,u.profile_photo,
      COALESCE(SUM(mp.points),0) AS pts,
      COUNT(CASE WHEN mp.points>0 THEN 1 END) AS correct
      FROM users u
      JOIN member_predictions mp ON mp.member_id=u.id
      GROUP BY u.id ORDER BY pts DESC, correct DESC LIMIT 3")->fetchAll();
    foreach($predLeague['top3'] as &$t3) {
      $t3['photo'] = $t3['profile_photo'] ? getMemberPhoto($t3['profile_photo']) : '';
    }
    // My stats
    $myP = db()->prepare("SELECT COALESCE(SUM(points),0) AS pts, COUNT(*) AS total FROM member_predictions WHERE member_id=?");
    $myP->execute([$user['id']]); $predLeague['my'] = $myP->fetch();
    // My rank
    $myRank = db()->prepare("SELECT COUNT(DISTINCT member_id)+1 AS rnk FROM (SELECT member_id,SUM(points) AS pts FROM member_predictions GROUP BY member_id HAVING pts > (SELECT COALESCE(SUM(points),0) FROM member_predictions WHERE member_id=?)) x");
    $myRank->execute([$user['id']]); $rnk=$myRank->fetch(); $predLeague['my']['rank'] = $rnk['rnk'] ?? 1;
    // Next upcoming match
    $predLeague['upcoming'] = db()->query("SELECT * FROM prediction_matches WHERE status='upcoming' ORDER BY match_date ASC LIMIT 1")->fetch();
    // Live match
    $predLeague['live'] = db()->query("SELECT * FROM prediction_matches WHERE status='live' LIMIT 1")->fetch();
  }
} catch(Exception $e){}

// ── Recent achievements for dashboard ──────────────────────
$recentAch = [];
try {
    $recentAch = db()->query("SELECT a.*,u.profile_photo uphoto FROM achievements a
        LEFT JOIN users u ON u.id=a.member_id
        WHERE a.status='active' ORDER BY a.achievement_date DESC, a.created_at DESC LIMIT 6")
        ->fetchAll();
} catch(Exception $e){}

$anns  = db()->query("SELECT a.*,u.name author,u.role author_role,u.profile_photo author_photo FROM announcements a JOIN users u ON u.id=a.posted_by ORDER BY a.is_pinned DESC,a.created_at DESC LIMIT 8")->fetchAll();
$evts  = db()->query("SELECT * FROM events WHERE event_date>=CURDATE() ORDER BY event_date LIMIT 3")->fetchAll();

$executives     = db()->query("SELECT * FROM users WHERE status='active' AND role IN('president','vice_president','secretary','joint_secretary','treasurer') ORDER BY FIELD(role,'president','vice_president','secretary','joint_secretary','treasurer')")->fetchAll();
$committeeMembers = db()->query("SELECT * FROM users WHERE status='active' AND role='committee_member' ORDER BY name LIMIT 9")->fetchAll();

$pendingCount = isAdminRole($user['role']) ? (int)db()->query("SELECT COUNT(*) FROM users WHERE status='pending'")->fetchColumn() : 0;
$logoB64 = getLogoB64();
$myPhoto = getMemberPhoto($user['profile_photo']);

// ── Active modules slider items ─────────────────────────────
$sliderItems = array();
try {
    $rows = db()->query("SELECT * FROM events WHERE event_date>=CURDATE() ORDER BY event_date LIMIT 5")->fetchAll();
    foreach($rows as $r) {
        $sliderItems[] = array(
            'type'=>'EVENT','title'=>$r['title'],
            'sub'=>date('d M Y',strtotime($r['event_date'])).(!empty($r['location'])?' · '.$r['location']:''),
            'emoji'=>'📅','color'=>'#0d47a1',
            'url'=>url('modules/events.php'),
            'img'=>!empty($r['thumbnail'])?url('assets/uploads/events/'.$r['thumbnail']):''
        );
    }
} catch(Exception $e){}
try {
    $rows = db()->query("SELECT * FROM cf_campaigns WHERE status='active' ORDER BY is_featured DESC,created_at DESC LIMIT 3")->fetchAll();
    foreach($rows as $r) {
        $sliderItems[] = array(
            'type'=>'CROWD FUNDING','title'=>$r['title'],
            'sub'=>'₹'.number_format($r['raised_amount']).' raised of ₹'.number_format($r['target_amount']),
            'emoji'=>'❤️','color'=>'#b71c1c',
            'url'=>url('modules/crowdfund.php').'?view=campaign&id='.$r['id'],
            'img'=>!empty($r['cover_image'])?url('assets/uploads/'.$r['cover_image']):''
        );
    }
} catch(Exception $e){}
try {
    $rows = db()->query("SELECT * FROM tournaments WHERE status='active' ORDER BY created_at DESC LIMIT 2")->fetchAll();
    foreach($rows as $r) {
        $sliderItems[] = array(
            'type'=>'FOOTBALL','title'=>$r['name']??'Football Tournament',
            'sub'=>'Active Tournament · View Fixtures & Results',
            'emoji'=>'⚽','color'=>'#1b5e20',
            'url'=>url('modules/football.php'),
            'img'=>!empty($r['banner'])?url('assets/uploads/tournaments/'.$r['banner']):''
        );
    }
} catch(Exception $e){}
try {
    $rows = db()->query("SELECT * FROM arts_festivals WHERE status='active' ORDER BY created_at DESC LIMIT 1")->fetchAll();
    foreach($rows as $r) {
        $sliderItems[] = array(
            'type'=>'ARTS FESTIVAL','title'=>$r['name']??'Arts Festival',
            'sub'=>'Arts & Cultural Programs · Click to see schedule',
            'emoji'=>'🎭','color'=>'#6a1b9a',
            'url'=>url('modules/arts_festival.php'),'img'=>''
        );
    }
} catch(Exception $e){}
try {
    $rows = db()->query("SELECT * FROM onam_events WHERE status='active' ORDER BY created_at DESC LIMIT 1")->fetchAll();
    foreach($rows as $r) {
        $sliderItems[] = array(
            'type'=>'ONAM','title'=>$r['name']??'Onam Celebration',
            'sub'=>'Onam Programs & Events · Join the celebration',
            'emoji'=>'🌸','color'=>'#f57f17',
            'url'=>url('modules/onam.php'),'img'=>''
        );
    }
} catch(Exception $e){}

if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_POST['post_ann']) && canPost($user['role'])) {
    $t=trim($_POST['ann_title']??'');$b=trim($_POST['ann_body']??'');$c=$_POST['ann_cat']??'general';
    if($t&&$b){db()->prepare('INSERT INTO announcements(title,body,category,posted_by)VALUES(?,?,?,?)')->execute([$t,$b,$c,$user['id']]);header('Location:'.url('dashboard.php').'?posted=1');exit;}
}

require_once __DIR__.'/includes/header.php';
?>

<!-- DASHBOARD APP SHELL -->
<style>
.db-shell{background:#f0f4fa;min-height:100vh;padding-bottom:2rem}

/* ── App Header ── */
.db-header{
  background:linear-gradient(145deg,#0d1b3e 0%,#1a3a6b 50%,#1565c0 100%);
  padding:1.4rem 1.2rem 1.5rem;position:relative;overflow:hidden;
}
.db-header::before{content:'';position:absolute;top:-40px;right:-30px;width:140px;height:140px;border-radius:50%;background:radial-gradient(circle,rgba(200,146,42,.22),transparent 70%)}
.db-header::after{content:'';position:absolute;bottom:-30px;left:-10px;right:-10px;height:60px;background:#f0f4fa;border-radius:50% 50% 0 0/40px 40px 0 0}
.db-hrow{display:flex;align-items:center;gap:.8rem;margin-bottom:1.1rem;position:relative;z-index:2}
.db-avatar{width:54px;height:54px;border-radius:50%;object-fit:cover;border:3px solid rgba(200,146,42,.8);background:rgba(255,255,255,.1);flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:1.4rem;overflow:hidden;box-shadow:0 4px 14px rgba(0,0,0,.25)}
.db-hinfo{flex:1;min-width:0}
.db-hgreeting{font-size:.72rem;color:rgba(255,255,255,.6);font-weight:600;letter-spacing:.05em}
.db-hname{font-family:'Playfair Display',serif;font-size:1.18rem;font-weight:700;color:#fff;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.db-hrole{font-size:.64rem;color:rgba(255,200,80,.95);font-weight:700;margin-top:.12rem;letter-spacing:.06em;text-transform:uppercase}
.db-notif{width:40px;height:40px;border-radius:50%;background:rgba(255,255,255,.14);border:1.5px solid rgba(255,255,255,.22);display:flex;align-items:center;justify-content:center;font-size:1.1rem;text-decoration:none;flex-shrink:0;transition:all .2s}
.db-notif:active{transform:scale(.9)}

/* Stats */
.db-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem;position:relative;z-index:2}
.db-stat{background:#fff;border-radius:16px;padding:.75rem .4rem;text-align:center;box-shadow:0 6px 18px rgba(0,0,0,.1);border-bottom:3px solid}
.db-stat-n{font-family:'Bebas Neue',sans-serif;font-size:1.6rem;line-height:1}
.db-stat-l{font-size:.55rem;text-transform:uppercase;letter-spacing:.08em;color:#94a3b8;font-weight:700;margin-top:.14rem}

/* ── Quick Nav Grid ── */
.db-qnav-wrap{padding:1.1rem 1rem .3rem}
.db-qnav-title{font-size:.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.65rem;display:flex;align-items:center;gap:.5rem}
.db-qnav-title::after{content:'';flex:1;height:1.5px;background:linear-gradient(90deg,#e0e7ff,transparent)}
.db-qnav{display:grid;grid-template-columns:repeat(4,1fr);gap:.55rem}
.db-qbtn{
  background:#fff;border-radius:18px;
  padding:.8rem .3rem .7rem;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.3rem;
  text-decoration:none;border:1.5px solid #eef2ff;
  box-shadow:0 3px 12px rgba(13,27,62,.06);
  transition:all .2s;position:relative;
  -webkit-tap-highlight-color:transparent;
}
.db-qbtn:active{transform:scale(.9);box-shadow:0 1px 4px rgba(0,0,0,.12)}
.db-qbtn-em{font-size:1.55rem;line-height:1;display:block}
.db-qbtn-lbl{font-size:.57rem;font-weight:800;color:#475569;text-align:center;line-height:1.25;letter-spacing:.01em}
.db-qbtn-badge{position:absolute;top:-.3rem;right:-.3rem;background:#e53935;color:#fff;border-radius:20px;padding:.05rem .38rem;font-size:.55rem;font-weight:900;border:2px solid #f0f4fa;box-shadow:0 2px 6px rgba(229,57,53,.35)}

/* ── Achievement strip ── */
.db-section{padding:.9rem 1rem .3rem}
.db-section-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:.65rem}
.db-section-title{font-size:.72rem;font-weight:800;color:#0d1b3e;text-transform:uppercase;letter-spacing:.1em;display:flex;align-items:center;gap:.4rem}
.db-section-more{font-size:.7rem;font-weight:700;color:#c8922a;text-decoration:none}
/* Collapsible dropdown section */
.db-collapse{margin:0 1rem 1.2rem;background:#fff;border-radius:16px;box-shadow:0 2px 12px rgba(13,27,62,.07);overflow:hidden}
.db-collapse-head{width:100%;display:flex;align-items:center;gap:.75rem;padding:.95rem 1rem;border:none;background:none;cursor:pointer;font-family:'DM Sans',sans-serif;text-align:left;-webkit-tap-highlight-color:transparent}
.dch-icon{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#7B1FA2,#9C27B0);display:flex;align-items:center;justify-content:center;font-size:1.3rem;flex-shrink:0}
.dch-txt{flex:1;min-width:0}
.dch-title{display:block;font-size:.92rem;font-weight:800;color:#0d1b3e;line-height:1.1}
.dch-sub{display:block;font-size:.66rem;color:#7A8DB5;margin-top:.12rem}
.dch-chev{font-size:1rem;color:#9aa7b8;transition:transform .25s;flex-shrink:0}
.db-collapse.open .dch-chev{transform:rotate(180deg)}
.db-collapse-body{max-height:0;overflow:hidden;transition:max-height .35s ease;padding:0 1rem}
.db-collapse.open .db-collapse-body{max-height:2500px;padding-bottom:1rem}
</style>

<div class="db-shell">
<!-- ── App Header ── -->
<div class="db-header">
  <div class="db-hrow">
    <?php
      $dAvatar = getMemberPhoto($user['profile_photo'] ?? '');
      $hour = (int)date('H');
      $greeting = $hour < 12 ? 'Good Morning' : ($hour < 17 ? 'Good Afternoon' : 'Good Evening');
    ?>
    <div class="db-avatar">
      <?php if($dAvatar): ?><img src="<?=$dAvatar?>" style="width:100%;height:100%;object-fit:cover"><?php else: ?>👤<?php endif; ?>
    </div>
    <div class="db-hinfo">
      <div class="db-hgreeting"><?=$greeting?> 👋</div>
      <div class="db-hname"><?= h($user['name']) ?></div>
      <div class="db-hrole"><?= h(str_replace('_',' ',ucwords($user['role']??'Member'))) ?></div>
    </div>
    <?php if(isAdminRole($user['role'])): ?>
    <a href="<?=url('admin.php')?>" class="db-notif" title="Admin Panel">🛡</a>
    <?php endif; ?>
  </div>

  <!-- Stats -->
  <div class="db-stats">
    <div class="db-stat" style="border-color:#0d47a1">
      <div class="db-stat-n" style="color:#0d47a1"><?= $stats['total'] ?></div>
      <div class="db-stat-l">Members</div>
    </div>
    <div class="db-stat" style="border-color:#1b5e20">
      <div class="db-stat-n" style="color:#1b5e20"><?= $stats['active'] ?></div>
      <div class="db-stat-l">Active</div>
    </div>
    <div class="db-stat" style="border-color:#c8922a">
      <div class="db-stat-n" style="color:#c8922a"><?= isset($sports_count) ? $sports_count : 5 ?></div>
      <div class="db-stat-l">Sports</div>
    </div>
    <div class="db-stat" style="border-color:#b71c1c">
      <div class="db-stat-n" style="color:#b71c1c"><?= $stats['donors'] ?></div>
      <div class="db-stat-l">Donors</div>
    </div>
  </div>
</div>

<!-- ── Community Feed Banner ── -->
<a href="<?= url('modules/feed.php') ?>" style="display:flex;align-items:center;gap:.85rem;margin:.7rem .8rem 0;padding:.85rem 1rem;border-radius:16px;background:linear-gradient(135deg,#1a237e,#1565c0 65%,#0288d1);box-shadow:0 5px 18px rgba(21,101,192,.28);text-decoration:none;position:relative;overflow:hidden">
  <span style="font-size:1.9rem;flex-shrink:0">📰</span>
  <div style="flex:1;min-width:0">
    <div style="font-size:.95rem;font-weight:900;color:#fff;line-height:1.1">Community Feed</div>
    <div style="font-size:.68rem;color:rgba(255,255,255,.78);margin-top:.1rem">See what members are sharing — posts, photos & videos</div>
  </div>
  <span style="flex-shrink:0;background:rgba(255,255,255,.2);color:#fff;font-size:.72rem;font-weight:800;padding:.4rem .8rem;border-radius:20px">Open →</span>
</a>

<!-- ── Quick Nav ── -->
<?php
// Build nav items
$isAdm = isAdminRole($user['role']);
$navItems = array(
    array('url'=>url('modules/feed.php'),        'em'=>'📰','label'=>'Feed',          'bg'=>'#e1f5fe','bc'=>'#4fc3f7','tc'=>'#01579b'),
    array('url'=>url('modules/market.php'),      'em'=>'🏪','label'=>'AV Market',      'bg'=>'#e3f2fd','bc'=>'#90caf9','tc'=>'#0d47a1'),
    array('url'=>url('modules/fixtures.php'),      'em'=>'📅🏟','label'=> 'World Cup Fixture 2026',      'bg'=>'#e3f2fd','bc'=>'#90caf9','tc'=>'#0d47a1'),
   
  array('url'=>url('modules/idcard.php'),      'em'=>'🪪','label'=>'ID Card',      'bg'=>'#e3f2fd','bc'=>'#90caf9','tc'=>'#0d47a1'),
  array('url'=>url('modules/nameslip.php'),    'em'=>'📚','label'=>'Name Slip',     'bg'=>'#e3f2fd','bc'=>'#90caf9','tc'=>'#0d47a1'),
  array('url'=>url('modules/prediction.php'),  'em'=>'⚽','label'=>'Prediction',    'bg'=>'#e8f5e9','bc'=>'#a5d6a7','tc'=>'#1b5e20'),
  array('url'=>url('modules/henna_fest.php'),  'em'=>'🌿','label'=>'Henna Fest',  'bg'=>'#fff3e0','bc'=>'#ffcc80','tc'=>'#8B3A0F'),
  array('url'=>url('modules/fest_manager.php'), 'em'=>'🎪','label'=>'Fests',   'bg'=>'#e8eaf6','bc'=>'#9fa8da','tc'=>'#1a237e'),
  array('url'=>url('modules/poster_maker.php'), 'em'=>'🎨','label'=>'AI Poster',   'bg'=>'#fff3e0','bc'=>'#ffcc80','tc'=>'#8B3A0F'),
  array('url'=>url('modules/crowdfund.php'),   'em'=>'❤️','label'=>'Crowd Fund',    'bg'=>'#fce4ec','bc'=>'#f48fb1','tc'=>'#880e4f'),
  array('url'=>url('modules/profile.php'),     'em'=>'👤','label'=>'Profile',      'bg'=>'#f3e5f5','bc'=>'#ce93d8','tc'=>'#6a1b9a'),
  array('url'=>url('modules/blood.php'),       'em'=>'🩸','label'=>'Blood Hub',    'bg'=>'#ffebee','bc'=>'#ef9a9a','tc'=>'#b71c1c'),
  array('url'=>url('modules/certificate.php'), 'em'=>'🏆','label'=>'Achievements', 'bg'=>'#fff8e1','bc'=>'#ffe082','tc'=>'#e65100'),
  array('url'=>url('modules/events.php'),      'em'=>'📅','label'=>'Events',       'bg'=>'#e8f5e9','bc'=>'#a5d6a7','tc'=>'#1b5e20'),
  array('url'=>url('modules/gallery.php'),     'em'=>'🖼️','label'=>'Gallery',      'bg'=>'#fce4ec','bc'=>'#f48fb1','tc'=>'#880e4f'),
  array('url'=>url('modules/football.php'),    'em'=>'⚽','label'=>'Football',     'bg'=>'#e8f5e9','bc'=>'#a5d6a7','tc'=>'#1b5e20'),
  array('url'=>url('modules/subscription.php'),'em'=>'💳','label'=>'Subscription', 'bg'=>'#e8eaf6','bc'=>'#9fa8da','tc'=>'#283593'),
  array('url'=>url('modules/members.php'),     'em'=>'👥','label'=>'Members',      'bg'=>'#e0f2f1','bc'=>'#80cbc4','tc'=>'#004d40'),
  array('url'=>url('modules/skills.php'),      'em'=>'🌟','label'=>'Skills',       'bg'=>'#fff8e1','bc'=>'#ffe082','tc'=>'#f57f17'),
  array('url'=>url('modules/donation.php'),    'em'=>'🤝','label'=>'Donation',     'bg'=>'#fce4ec','bc'=>'#f48fb1','tc'=>'#880e4f'),
  array('url'=>url('modules/groundfund.php'),  'em'=>'🏟️','label'=>'Ground Fund',  'bg'=>'#fff3e0','bc'=>'#ffcc80','tc'=>'#8B3A0F'),
  array('url'=>url('modules/election.php'),    'em'=>'🗳️','label'=>'Elections',    'bg'=>'#e8eaf6','bc'=>'#9fa8da','tc'=>'#1a237e'),
  array('url'=>url('contact.php'),             'em'=>'📞','label'=>'Contact',      'bg'=>'#e8eaf6','bc'=>'#9fa8da','tc'=>'#283593'),
);
if($isAdm){
  $navItems[] = array('url'=>url('admin.php'),  'em'=>'🛡','label'=>'Admin Panel', 'bg'=>'#e8eaf6','bc'=>'#7986cb','tc'=>'#1a237e');
  $navItems[] = array('url'=>url('modules/broadcast.php'),'em'=>'📢','label'=>'Broadcast','bg'=>'#e8f5e9','bc'=>'#a5d6a7','tc'=>'#1b5e20');
  $navItems[] = array('url'=>url('modules/admin_subscription.php'),'em'=>'🧾','label'=>'Subs Admin','bg'=>'#e8eaf6','bc'=>'#9fa8da','tc'=>'#283593');
  if(isSuperAdmin($user)) $navItems[] = array('url'=>url('modules/settings.php'),'em'=>'⚙️','label'=>'Settings','bg'=>'#eceff1','bc'=>'#90a4ae','tc'=>'#263238');
  $navItems[] = array('url'=>url('modules/onam.php'),'em'=>'🌸','label'=>'Onam','bg'=>'#fff8e1','bc'=>'#ffe082','tc'=>'#e65100');
  $navItems[] = array('url'=>url('modules/arts_festival.php'),'em'=>'🎭','label'=>'Arts Fest','bg'=>'#f3e5f5','bc'=>'#ce93d8','tc'=>'#6a1b9a');
}
$navItems[] = array('url'=>url('logout.php'), 'em'=>'🚪','label'=>'Logout','bg'=>'#ffebee','bc'=>'#ef9a9a','tc'=>'#b71c1c');
?>
<div class="db-qnav-wrap">
  <div class="db-qnav-title">Quick Access</div>
  <div class="db-qnav">
    <?php foreach($navItems as $nl): ?>
    <a href="<?=$nl['url']?>" class="db-qbtn" style="border-color:<?=$nl['bc']?>22;background:linear-gradient(145deg,#fff,<?=$nl['bg']?>)">
      <span class="db-qbtn-em"><?=$nl['em']?></span>
      <span class="db-qbtn-lbl" style="color:<?=$nl['tc']?>"><?=$nl['label']?></span>
    </a>
    <?php endforeach; ?>
  </div>
</div>

<!-- ── Recent Achievements ── -->
<?php if(!empty($recentAch)): ?>
<div class="db-section">
  <div class="db-section-head">
    <div class="db-section-title">🏆 Achievements</div>
    <a href="<?=url('modules/certificate.php')?>" class="db-section-more">View all →</a>
  </div>
  <div style="display:flex;gap:.6rem;overflow-x:auto;padding-bottom:.4rem;scrollbar-width:none;-webkit-overflow-scrolling:touch">
    <?php
    $achMedals=['gold'=>['🥇','linear-gradient(135deg,#f5d060,#c8922a)'],'silver'=>['🥈','linear-gradient(135deg,#d0d0d0,#888)'],'bronze'=>['🥉','linear-gradient(135deg,#d4935a,#8b4513)'],'special'=>['🏅','linear-gradient(135deg,#667eea,#764ba2)'],'participation'=>['🎖️','linear-gradient(135deg,#0d47a1,#1565c0)']];
    foreach($recentAch as $ra):
      $am = $achMedals[$ra['medal_type']] ?? $achMedals['special'];
      $aPhoto = !empty($ra['uphoto']) ? getMemberPhoto($ra['uphoto']) : '';
      $aImgUrl=''; if(!empty($ra['image'])) $aImgUrl=(strpos($ra['image'],'/')!==false)?url('assets/uploads/'.$ra['image']):url('assets/uploads/achievements/'.$ra['image']);
    ?>
    <a href="<?=url('modules/certificate.php')?>" style="flex-shrink:0;width:145px;border-radius:16px;overflow:hidden;text-decoration:none;box-shadow:0 4px 16px rgba(0,0,0,.1);background:#fff">
      <div style="height:82px;background:<?=$am[1]?>;position:relative;display:flex;align-items:center;justify-content:center">
        <?php if($aImgUrl): ?><img src="<?=$aImgUrl?>" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.45"><?php endif; ?>
        <span style="font-size:2.6rem;position:relative;z-index:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,.3))"><?=$am[0]?></span>
      </div>
      <div style="padding:.55rem .62rem">
        <div style="font-weight:800;font-size:.73rem;color:#0d1b3e;line-height:1.25;margin-bottom:.18rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden"><?=h($ra['title'])?></div>
        <div style="font-size:.62rem;color:#64748b;display:flex;align-items:center;gap:.3rem">
          <?php if($aPhoto): ?><img src="<?=$aPhoto?>" style="width:14px;height:14px;border-radius:50%;object-fit:cover"><?php endif; ?>
          <?=h(mb_strimwidth($ra['member_name'],0,16,'…'))?>
        </div>
      </div>
    </a>
    <?php endforeach; ?>
  </div>
</div>
<?php endif; ?>

<!-- ── DIGITAL NOTICE BOARD ── -->
<?php if(!empty($notices)): ?>
<div class="db-section">
  <div class="db-section-head">
    <div class="db-section-title">
      <span style="animation:noticePulse 2s ease-in-out infinite;display:inline-block">📢</span>
      Notice Board
    </div>
    <a href="<?=url('modules/events.php')?>" class="db-section-more">Events →</a>
  </div>

  <!-- Scrolling ticker -->
  <?php $urgentNotices = array_filter($notices, function($n){ return ($n['priority']??'normal')!=='normal'; }); ?>
  <?php if(!empty($urgentNotices)): ?>
  <div style="background:linear-gradient(135deg,#b71c1c,#c62828);border-radius:10px;padding:.5rem .8rem;margin-bottom:.65rem;display:flex;align-items:center;gap:.5rem;overflow:hidden">
    <span style="background:rgba(255,255,255,.2);color:#fff;border-radius:6px;padding:.15rem .5rem;font-size:.6rem;font-weight:800;white-space:nowrap;flex-shrink:0">🔴 ALERT</span>
    <div style="overflow:hidden;flex:1">
      <div style="display:flex;gap:2rem;animation:tickerScroll 18s linear infinite;white-space:nowrap">
        <?php foreach($urgentNotices as $un): ?>
        <span style="font-size:.75rem;color:#fff;font-weight:700"><?= h($un['title']) ?></span>
        <?php endforeach; ?>
        <?php foreach($urgentNotices as $un): ?>
        <span style="font-size:.75rem;color:#fff;font-weight:700"><?= h($un['title']) ?></span>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
  <?php endif; ?>

  <!-- Notice cards -->
  <div style="display:flex;flex-direction:column;gap:.5rem">
    <?php foreach($notices as $ni=>$n):
      if($ni >= 5) break;
      $nc = $annCatConf[$n['category']??'general'] ?? $annCatConf['general'];
      $isPin = $n['is_pinned'];
      $isPri = ($n['priority']??'normal');
      $borderClr = $isPri==='emergency'?'#b71c1c':($isPri==='urgent'?'#e65100':'rgba(255,255,255,.15)');
    ?>
    <div style="background:rgba(255,255,255,.09);border:1.5px solid <?=$borderClr?>;
         border-radius:12px;padding:.7rem .85rem;
         <?=$isPri==='emergency'?'animation:emergencyPulse 2s ease-in-out infinite':''?>
         position:relative;overflow:hidden">
      <?php if($isPin): ?>
      <div style="position:absolute;top:.45rem;right:.55rem;font-size:.75rem">📌</div>
      <?php endif; ?>
      <div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.28rem;flex-wrap:wrap">
        <span style="background:<?=$nc['bg']?>;color:<?=$nc['color']?>;border-radius:20px;
               padding:.1rem .55rem;font-size:.6rem;font-weight:800">
          <?=$nc['em']?> <?=ucfirst($n['category']??'General')?>
        </span>
        <?php if($isPri!=='normal'): ?>
        <span style="background:<?=$isPri==='emergency'?'rgba(183,28,28,.25)':'rgba(230,81,0,.2)'?>;
               color:<?=$isPri==='emergency'?'#ef9a9a':'#ffcc80'?>;
               border-radius:20px;padding:.1rem .55rem;font-size:.6rem;font-weight:800">
          <?=$isPri==='emergency'?'🚨 Emergency':'🔔 Urgent'?>
        </span>
        <?php endif; ?>
      </div>
      <div style="font-weight:700;font-size:.85rem;color:#fff;line-height:1.3;margin-bottom:.22rem"><?=h($n['title'])?></div>
      <?php if(!empty($n['body'])): ?>
      <div style="font-size:.74rem;color:rgba(255,255,255,.6);line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden"><?=h($n['body'])?></div>
      <?php endif; ?>
      <div style="font-size:.62rem;color:rgba(255,255,255,.35);margin-top:.28rem"><?=date('d M Y',strtotime($n['created_at']))?></div>
    </div>
    <?php endforeach; ?>
  </div>
</div>
<style>
@keyframes noticePulse{0%,100%{transform:scale(1)}50%{transform:scale(1.15)}}
@keyframes tickerScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes emergencyPulse{0%,100%{box-shadow:0 0 0 rgba(183,28,28,0)}50%{box-shadow:0 0 12px rgba(183,28,28,.5)}}
</style>
<?php endif; ?>

<!-- ② NOTICE BOARD ─────────────────────────────────────── -->
<?php if(!empty($notices)): ?>
<div class="db-section">
  <div class="db-section-head">
    <div class="db-section-title">
      <span style="animation:noticePulse 2s ease-in-out infinite;display:inline-block">📢</span>
      Notice Board
    </div>
    <?php
      $hasEmergency = false;
      foreach($notices as $n){ if(($n['priority']??'')=='emergency'){ $hasEmergency=true; break; } }
    ?>
    <?php if($hasEmergency): ?>
    <span style="background:#b71c1c;color:#fff;border-radius:20px;padding:.12rem .6rem;
           font-size:.6rem;font-weight:800;letter-spacing:.06em;
           animation:noticePulse 1.2s ease-in-out infinite">
      🚨 EMERGENCY
    </span>
    <?php endif; ?>
  </div>

  <!-- Scrolling ticker for urgent/emergency -->
  <?php $urgents = array_filter($notices, function($n){ return in_array($n['priority']??'normal',['urgent','emergency']); }); ?>
  <?php if(!empty($urgents)): ?>
  <div style="background:linear-gradient(135deg,#b71c1c,#c62828);border-radius:12px;
       padding:.55rem .9rem;margin-bottom:.7rem;overflow:hidden;position:relative">
    <div style="display:flex;align-items:center;gap:.6rem">
      <span style="background:rgba(255,255,255,.2);border-radius:6px;
             padding:.12rem .5rem;font-size:.6rem;font-weight:800;color:#fff;
             white-space:nowrap;letter-spacing:.06em">🔴 LIVE</span>
      <div style="overflow:hidden;flex:1">
        <div id="nbTicker" style="display:flex;gap:2rem;white-space:nowrap;
             animation:nbScroll 18s linear infinite">
          <?php foreach($urgents as $un): ?>
          <span style="font-size:.78rem;font-weight:700;color:#fff">
            <?= ($un['priority']=='emergency')?'🚨':'⚠️' ?>
            <?= h($un['title']) ?>
          </span>
          <?php endforeach; ?>
          <?php foreach($urgents as $un): ?> <!-- duplicate for seamless loop -->
          <span style="font-size:.78rem;font-weight:700;color:#fff">
            <?= ($un['priority']=='emergency')?'🚨':'⚠️' ?>
            <?= h($un['title']) ?>
          </span>
          <?php endforeach; ?>
        </div>
      </div>
    </div>
  </div>
  <?php endif; ?>

  <!-- Notice cards -->
  <div style="display:flex;flex-direction:column;gap:.5rem">
  <?php
  $noticeConf = [
    'general'   => ['em'=>'📋','color'=>'#0d47a1','bg'=>'#e3f2fd','border'=>'#90caf9'],
    'match'     => ['em'=>'⚽','color'=>'#1b5e20','bg'=>'#e8f5e9','border'=>'#a5d6a7'],
    'meeting'   => ['em'=>'🤝','color'=>'#e65100','bg'=>'#fff3e0','border'=>'#ffcc80'],
    'festival'  => ['em'=>'🎭','color'=>'#6a1b9a','bg'=>'#f3e5f5','border'=>'#ce93d8'],
    'blood'     => ['em'=>'🩸','color'=>'#b71c1c','bg'=>'#ffebee','border'=>'#ef9a9a'],
    'emergency' => ['em'=>'🚨','color'=>'#b71c1c','bg'=>'#ffebee','border'=>'#ef5350'],
    'urgent'    => ['em'=>'⚠️','color'=>'#e65100','bg'=>'#fff3e0','border'=>'#ffb74d'],
  ];
  foreach($notices as $ni=>$n):
    $cat = $noticeConf[$n['category']??'general'] ?? $noticeConf['general'];
    $priColor = $n['priority']=='emergency'?'#b71c1c':($n['priority']=='urgent'?'#e65100':'#0d47a1');
    $priLabel = $n['priority']=='emergency'?'🚨 Emergency':($n['priority']=='urgent'?'⚡ Urgent':'');
    $timeAgo = '';
    $diff = time() - strtotime($n['created_at']);
    if($diff < 3600) $timeAgo = floor($diff/60).'m ago';
    elseif($diff < 86400) $timeAgo = floor($diff/3600).'h ago';
    else $timeAgo = date('d M', strtotime($n['created_at']));
  ?>
  <div style="background:#fff;border-radius:14px;padding:.8rem .9rem;
       border-left:3.5px solid <?= $cat['border'] ?>;
       box-shadow:0 2px 10px rgba(0,0,0,.06);
       <?= $n['priority']=='emergency'?'box-shadow:0 3px 16px rgba(183,28,28,.15);':'' ?>
       position:relative">
    <?php if($n['is_pinned']): ?>
    <span style="position:absolute;top:.5rem;right:.6rem;font-size:.7rem">📌</span>
    <?php endif; ?>
    <div style="display:flex;align-items:flex-start;gap:.6rem">
      <!-- Icon -->
      <div style="width:36px;height:36px;border-radius:10px;flex-shrink:0;
           background:<?= $cat['bg'] ?>;display:flex;align-items:center;
           justify-content:center;font-size:1.1rem">
        <?= $cat['em'] ?>
      </div>
      <!-- Content -->
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;margin-bottom:.22rem">
          <?php if($priLabel): ?>
          <span style="font-size:.58rem;font-weight:800;color:#fff;
                 background:<?= $priColor ?>;border-radius:20px;padding:.06rem .45rem">
            <?= $priLabel ?>
          </span>
          <?php endif; ?>
          <span style="font-size:.62rem;font-weight:700;color:<?= $cat['color'] ?>;
                 background:<?= $cat['bg'] ?>;border-radius:20px;padding:.06rem .45rem">
            <?= h(ucfirst($n['category']??'General')) ?>
          </span>
        </div>
        <div style="font-weight:800;font-size:.88rem;color:#0d1b3e;line-height:1.3;
             margin-bottom:<?= $n['body']?'.28rem':'0' ?>">
          <?= h($n['title']) ?>
        </div>
        <?php if($n['body']): ?>
        <div style="font-size:.76rem;color:#64748b;line-height:1.5;
             display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">
          <?= h($n['body']) ?>
        </div>
        <?php endif; ?>
        <div style="display:flex;align-items:center;gap:.4rem;margin-top:.35rem">
          <span style="font-size:.62rem;color:#94a3b8"><?= $timeAgo ?></span>
          <?php if($n['expires_at']): ?>
          <span style="font-size:.6rem;color:#94a3b8">· Expires <?= date('d M',strtotime($n['expires_at'])) ?></span>
          <?php endif; ?>
        </div>
      </div>
    </div>
  </div>
  <?php endforeach; ?>
  </div>
</div>
<?php endif; ?>

<style>
@keyframes nbScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes noticePulse{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
</style>

<!-- ③ CLUB ACTIVITIES — full-width horizontal auto-slider -->
  <div style="margin-bottom:1.4rem">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.07em;color:#0D47A1;margin-bottom:.85rem;display:flex;align-items:center;gap:.5rem">
      🏟 CLUB ACTIVITIES
      <div style="flex:1;height:1.5px;background:linear-gradient(90deg,#0D47A1,transparent)"></div>
    </div>

    <?php
    // Build activity slides
    $actSlides = array();

    // 1. Active Events — use event thumbnail if exists
    try {
      $evRows = db()->query("SELECT * FROM events WHERE event_date>=CURDATE() ORDER BY event_date LIMIT 6")->fetchAll();
      foreach($evRows as $r) {
        $actSlides[] = array(
          'title'  => $r['title'],
          'sub'    => date('d M Y',strtotime($r['event_date'])).(!empty($r['location'])?' · '.$r['location']:''),
          'label'  => 'EVENT',
          'emoji'  => '📅',
          'color'  => '#0d47a1',
          'url'    => url('modules/events.php'),
          'img'    => !empty($r['thumbnail']) ? url('assets/uploads/events/'.$r['thumbnail']) : '',
          'live'   => true,
        );
      }
    } catch(Exception $e){}

    // 2. Active Crowdfunding campaigns
    try {
      $cfRows = db()->query("SELECT * FROM cf_campaigns WHERE status='active' ORDER BY is_featured DESC,created_at DESC LIMIT 3")->fetchAll();
      foreach($cfRows as $r) {
        $actSlides[] = array(
          'title'  => $r['title'],
          'sub'    => 'Raised ₹'.number_format($r['raised_amount']).' of ₹'.number_format($r['target_amount']),
          'label'  => 'CROWD FUNDING',
          'emoji'  => '❤️',
          'color'  => '#b71c1c',
          'url'    => url('modules/crowdfund.php').'?view=campaign&id='.$r['id'],
          'img'    => !empty($r['cover_image']) ? url('assets/uploads/'.$r['cover_image']) : '',
          'live'   => true,
        );
      }
    } catch(Exception $e){}

    // 3. Football
    try {
      $fbRows = db()->query("SELECT * FROM tournaments ORDER BY created_at DESC LIMIT 2")->fetchAll();
      foreach($fbRows as $r) {
        $actSlides[] = array(
          'title'  => $r['name'] ?? 'Football Tournament',
          'sub'    => 'View fixtures, results & standings',
          'label'  => 'FOOTBALL',
          'emoji'  => '⚽',
          'color'  => '#1b5e20',
          'url'    => url('modules/football.php'),
          'img'    => !empty($r['banner']) ? url('assets/uploads/tournaments/'.$r['banner']) : '',
          'live'   => ($r['status']==='active'),
        );
      }
    } catch(Exception $e){}

    // 4. Arts Festival
    try {
      $afRows = db()->query("SELECT * FROM arts_festivals ORDER BY created_at DESC LIMIT 1")->fetchAll();
      foreach($afRows as $r) {
        $actSlides[] = array(
          'title'  => $r['name'] ?? 'Arts Festival',
          'sub'    => 'Arts & Cultural Programs',
          'label'  => 'ARTS FESTIVAL',
          'emoji'  => '🎭',
          'color'  => '#6a1b9a',
          'url'    => url('modules/arts_festival.php'),
          'img'    => '',
          'live'   => ($r['status']==='active'),
        );
      }
    } catch(Exception $e){}

    // 5. Onam
    try {
      $onRows = db()->query("SELECT * FROM onam_events ORDER BY created_at DESC LIMIT 1")->fetchAll();
      foreach($onRows as $r) {
        $actSlides[] = array(
          'title'  => $r['name'] ?? 'Onam Celebration',
          'sub'    => 'Onam Programs & Cultural Events',
          'label'  => 'ONAM',
          'emoji'  => '🌸',
          'color'  => '#e65100',
          'url'    => url('modules/onam.php'),
          'img'    => '',
          'live'   => ($r['status']==='active'),
        );
      }
    } catch(Exception $e){}

    // Fallback static slides if nothing dynamic
    if(empty($actSlides)) {
      $actSlides = array(
        array('title'=>'Football Tournament','sub'=>'View fixtures, results & standings','label'=>'FOOTBALL','emoji'=>'⚽','color'=>'#1b5e20','url'=>url('modules/football.php'),'img'=>'','live'=>false),
        array('title'=>'Arts Festival','sub'=>'Arts & Cultural Programs','label'=>'ARTS FESTIVAL','emoji'=>'🎭','color'=>'#6a1b9a','url'=>url('modules/arts_festival.php'),'img'=>'','live'=>false),
        array('title'=>'Onam Celebration','sub'=>'Onam Programs & Cultural Events','label'=>'ONAM','emoji'=>'🌸','color'=>'#e65100','url'=>url('modules/onam.php'),'img'=>'','live'=>false),
        array('title'=>'Crowd Funding','sub'=>'Support our community campaigns','label'=>'CROWD FUNDING','emoji'=>'❤️','color'=>'#b71c1c','url'=>url('modules/crowdfund.php'),'img'=>'','live'=>false),
        array('title'=>'Club Elections','sub'=>'Nominations & Voting','label'=>'ELECTIONS','emoji'=>'🗳️','color'=>'#1a237e','url'=>url('modules/election.php'),'img'=>'','live'=>false),
      );
    }
    $actTotal = count($actSlides);
    ?>

    <!-- Slider container: full width, 56vw tall (portrait feel), max 360px -->
    <div id="actWrap" style="position:relative;overflow:hidden;border-radius:20px;width:100%;height:clamp(260px,56vw,360px);box-shadow:0 10px 36px rgba(0,0,0,.22)">

      <!-- Track -->
      <div id="actTrack" style="display:flex;height:100%;transition:transform .5s cubic-bezier(.4,0,.2,1)">
        <?php foreach($actSlides as $ai=>$as): ?>
        <div style="flex-shrink:0;width:100%;height:100%;position:relative;overflow:hidden">

          <?php if(!empty($as['img'])): ?>
          <!-- Real photo background -->
          <div class="act-bg" style="position:absolute;inset:0;background-image:url('<?= h($as['img']) ?>');background-size:cover;background-position:center;transition:transform 7s ease-in-out"></div>
          <!-- Scrim — stronger at bottom for readability -->
          <div style="position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,.1) 0%,transparent 30%,rgba(0,0,0,.75) 100%)"></div>
          <?php else: ?>
          <!-- Gradient when no photo -->
          <div style="position:absolute;inset:0;background:linear-gradient(155deg,<?= $as['color'] ?> 0%,<?= $as['color'] ?>bb 50%,#060810 100%)"></div>
          <div style="position:absolute;inset:0;background:radial-gradient(ellipse at 70% 25%,rgba(255,255,255,.1) 0%,transparent 55%)"></div>
          <!-- Big emoji watermark -->
          <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-55%);font-size:9rem;opacity:.16;line-height:1;pointer-events:none;filter:blur(1px)"><?= $as['emoji'] ?></div>
          <?php endif; ?>

          <!-- Top: slide counter + live badge -->
          <div style="position:absolute;top:.85rem;left:.85rem;right:.85rem;z-index:4;display:flex;align-items:center;justify-content:space-between">
            <?php if($as['live']): ?>
            <div style="display:inline-flex;align-items:center;gap:.3rem;background:rgba(183,28,28,.85);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-radius:20px;padding:.2rem .65rem">
              <span style="width:6px;height:6px;border-radius:50%;background:#ff5252;display:inline-block;animation:livePulse 1.2s ease-in-out infinite"></span>
              <span style="font-size:.58rem;font-weight:800;color:#fff;letter-spacing:.1em">LIVE</span>
            </div>
            <?php else: ?><div></div><?php endif; ?>
            <div style="background:rgba(0,0,0,.38);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-radius:20px;padding:.2rem .65rem">
              <span style="font-size:.62rem;font-weight:700;color:rgba(255,255,255,.9)"><?= ($ai+1) ?>&thinsp;/&thinsp;<?= $actTotal ?></span>
            </div>
          </div>

          <!-- Bottom overlay: label + title + sub + button -->
          <div style="position:absolute;bottom:0;left:0;right:0;z-index:4;padding:1.2rem 1.1rem 1.3rem">
            <!-- Category label pill -->
            <div style="display:inline-flex;align-items:center;gap:.35rem;background:rgba(255,255,255,.18);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.28);border-radius:25px;padding:.22rem .8rem;margin-bottom:.55rem">
              <span style="font-size:.78rem"><?= $as['emoji'] ?></span>
              <span style="font-size:.58rem;font-weight:900;letter-spacing:.14em;color:#fff;text-transform:uppercase"><?= h($as['label']) ?></span>
            </div>
            <!-- Title -->
            <div style="font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.3rem;color:#fff;line-height:1.2;margin-bottom:.35rem;text-shadow:0 2px 10px rgba(0,0,0,.5)"><?= h($as['title']) ?></div>
            <!-- Sub text -->
            <div style="font-size:.75rem;color:rgba(255,255,255,.8);margin-bottom:.9rem;line-height:1.4;text-shadow:0 1px 6px rgba(0,0,0,.4)"><?= h($as['sub']) ?></div>
            <!-- CTA button -->
            <a href="<?= h($as['url']) ?>" style="display:inline-flex;align-items:center;gap:.45rem;background:#fff;color:<?= $as['color'] ?>;border-radius:30px;padding:.52rem 1.3rem;font-family:'Inter',sans-serif;font-size:.8rem;font-weight:800;text-decoration:none;box-shadow:0 4px 18px rgba(0,0,0,.28)">
              View &amp; Navigate <span style="font-size:.9rem">→</span>
            </a>
          </div>

        </div>
        <?php endforeach; ?>
      </div>

      <!-- Dot indicators -->
      <?php if($actTotal>1): ?>
      <div id="actDots" style="position:absolute;bottom:.7rem;left:50%;transform:translateX(-50%);display:flex;gap:.4rem;z-index:6;align-items:center">
        <?php for($i=0;$i<$actTotal;$i++): ?>
        <button onclick="actGo(<?=$i?>)" id="actDot<?=$i?>" style="width:<?=$i===0?'22':'7'?>px;height:7px;border-radius:10px;border:none;background:<?=$i===0?'#fff':'rgba(255,255,255,.4)'?>;cursor:pointer;transition:all .35s;padding:0;display:block"></button>
        <?php endfor; ?>
      </div>
      <!-- Tap zones -->
      <div onclick="actPrev()" style="position:absolute;left:0;top:0;width:30%;height:100%;z-index:5;cursor:pointer"></div>
      <div onclick="actNext()" style="position:absolute;right:0;top:0;width:30%;height:100%;z-index:5;cursor:pointer"></div>
      <?php endif; ?>
    </div>
  </div>

<!-- ④ COMMITTEE (collapsible) -->
  <?php if(!empty($executives) || !empty($committeeMembers)):
    $execCount = count($executives ?? []);
    $comCount  = count($committeeMembers ?? []);
    $totalLeaders = $execCount + $comCount;
  ?>
  <div class="db-collapse" id="committeeWrap">
    <button class="db-collapse-head" onclick="toggleCollapse('committeeWrap')" aria-expanded="false">
      <span class="dch-icon">🏛️</span>
      <span class="dch-txt">
        <span class="dch-title">Club Leadership</span>
        <span class="dch-sub"><?= $totalLeaders ?> members · Executive &amp; Committee</span>
      </span>
      <span class="dch-chev">▾</span>
    </button>
    <div class="db-collapse-body">
    <div style="padding-top:.4rem">
    <?php if(!empty($executives)): ?>
    <h2 style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.06em;color:#B8860B;display:flex;align-items:center;gap:.6rem;margin-bottom:1rem">
      ⭐ EXECUTIVE COMMITTEE
      <div style="flex:1;height:2px;background:linear-gradient(90deg,#B8860B,transparent)"></div>
    </h2>
    <div style="display:flex;gap:1rem;overflow-x:auto;padding-bottom:.5rem;margin-bottom:1.5rem;scroll-snap-type:x mandatory">
      <?php foreach($executives as $m):
        $ep=$getMemberPhoto=$m['profile_photo']?getMemberPhoto($m['profile_photo']):'';
        $ep=getMemberPhoto($m['profile_photo']);
        $roleColors2=array('president'=>'#B8860B','vice_president'=>'#8B6914','secretary'=>'#0D47A1','joint_secretary'=>'#1565C0','treasurer'=>'#2E7D32');
        $rc2=$roleColors2[$m['role']]??'#546E7A';
      ?>
      <div style="flex-shrink:0;width:155px;scroll-snap-align:start">
        <a href="<?=url('modules/profile.php')?>?id=<?=$m['id']?>" style="display:block;text-decoration:none">
          <div style="background:#fff;border-radius:14px;padding:1.1rem .9rem;text-align:center;box-shadow:0 4px 18px rgba(0,0,0,.1);border-top:4px solid <?=$rc2?>">
            <?php if($ep): ?>
            <img src="<?=$ep?>" style="width:70px;height:70px;border-radius:50%;object-fit:cover;border:2.5px solid <?=$rc2?>;margin:0 auto .6rem;display:block" alt="">
            <?php else: ?>
            <div style="width:70px;height:70px;border-radius:50%;background:#E3F2FD;border:2.5px solid <?=$rc2?>;margin:0 auto .6rem;display:flex;align-items:center;justify-content:center;font-size:1.7rem">👤</div>
            <?php endif; ?>
            <div style="font-weight:700;font-size:.85rem;color:#0D1B3E;margin-bottom:.2rem"><?=h($m['name'])?></div>
            <div style="font-size:.68rem;color:#7A8DB5;margin-bottom:.35rem"><?=h($m['committee_position']??roleLabel($m['role']))?></div>
            <span style="display:inline-block;padding:.14rem .55rem;border-radius:20px;font-size:.62rem;font-weight:700;background:<?=$rc2?>22;color:<?=$rc2?>;border:1px solid <?=$rc2?>44"><?=h(roleLabel($m['role']))?></span>
          </div>
        </a>
      </div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
    <?php if(!empty($committeeMembers)): ?>
    <h2 style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.06em;color:#7B1FA2;display:flex;align-items:center;gap:.6rem;margin-bottom:1rem">
      🏛 COMMITTEE MEMBERS
      <div style="flex:1;height:2px;background:linear-gradient(90deg,#7B1FA2,transparent)"></div>
      <a href="<?=url('modules/members.php')?>#committee" style="font-family:'DM Sans',sans-serif;font-size:.75rem;font-weight:600;color:#7B1FA2;text-decoration:none">View all →</a>
    </h2>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.9rem" id="comGrid">
      <?php foreach($committeeMembers as $m): $cp=getMemberPhoto($m['profile_photo']); ?>
      <a href="<?=url('modules/profile.php')?>?id=<?=$m['id']?>" style="text-decoration:none;display:block">
        <div style="background:#fff;border-radius:12px;padding:.9rem;text-align:center;box-shadow:0 2px 10px rgba(74,20,140,.1);border-top:3px solid #7B1FA2;transition:all .2s" class="cmcard">
          <?php if($cp): ?>
          <img src="<?=$cp?>" style="width:58px;height:58px;border-radius:50%;object-fit:cover;border:2px solid #7B1FA2;margin:0 auto .55rem;display:block" alt="">
          <?php else: ?>
          <div style="width:58px;height:58px;border-radius:50%;background:#F3E5F5;border:2px solid #7B1FA2;margin:0 auto .55rem;display:flex;align-items:center;justify-content:center;font-size:1.3rem">👤</div>
          <?php endif; ?>
          <div style="font-weight:700;font-size:.8rem;color:#0D1B3E;margin-bottom:.15rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><?=h($m['name'])?></div>
          <div style="font-size:.65rem;color:#7A8DB5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><?=h($m['committee_position']??'Committee Member')?></div>
        </div>
      </a>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
    </div><!-- /padding -->
    </div><!-- /db-collapse-body -->
  </div><!-- /db-collapse -->
  <?php endif; ?>

  <!-- ⑤ MAIN GRID: FEED + SIDEBAR -->
  <div style="display:grid;grid-template-columns:1fr;gap:1.3rem" id="dashGrid">

    <!-- Feed -->
    <div>
      <h2 style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.06em;color:#0D47A1;display:flex;align-items:center;gap:.6rem;margin-bottom:1rem">
        📢 CLUB FEED
        <div style="flex:1;height:2px;background:linear-gradient(90deg,#B71C1C,transparent)"></div>
      </h2>
      <?php if(canPost($user['role'])): ?>
      <div style="background:#fff;border-radius:14px;padding:1.1rem;box-shadow:0 2px 10px rgba(13,71,161,.08);margin-bottom:1rem">
        <form method="POST" action="<?=url('dashboard.php')?>">
          <input type="text" name="ann_title" class="inp" placeholder="📢 Announcement title…" required style="margin-bottom:.5rem;font-weight:700">
          <textarea name="ann_body" class="inp" rows="2" placeholder="Share a club update, event or news…" required style="resize:vertical;margin-bottom:.5rem"></textarea>
          <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
            <select name="ann_cat" class="inp" style="flex:1;min-width:130px;max-width:180px">
              <option value="general">📢 General</option><option value="sports">⚽ Sports</option>
              <option value="cultural">🎭 Cultural</option><option value="charity">🤝 Charity</option>
              <option value="urgent">🚨 Urgent</option><option value="achievement">🏆 Achievement</option>
            </select>
            <button type="submit" name="post_ann" style="background:#0D47A1;color:#fff;border:none;border-radius:9px;padding:.6rem 1.1rem;font-family:'DM Sans',sans-serif;font-weight:700;font-size:.85rem;cursor:pointer">📤 Post</button>
          </div>
        </form>
      </div>
      <?php endif; ?>
      <?php if(empty($anns)): ?>
      <div style="background:#E3F2FD;color:#07225c;border-left:4px solid #0D47A1;padding:.8rem 1rem;border-radius:9px;font-size:.85rem">ℹ️ No announcements yet.</div>
      <?php else: foreach($anns as $a): $ap=getMemberPhoto($a['author_photo']); ?>
      <div style="background:#fff;border-radius:14px;border-left:4px solid <?=catColor($a['category'])?>;box-shadow:0 2px 10px rgba(0,0,0,.07);padding:1rem 1.1rem;margin-bottom:.9rem;<?=$a['is_pinned']?'border-left-color:#B71C1C;background:#FFF5F5':''?>">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.7rem;flex-wrap:wrap;gap:.4rem">
          <div style="display:flex;align-items:center;gap:.6rem">
            <?php if($ap): ?><img src="<?=$ap?>" style="width:32px;height:32px;border-radius:50%;object-fit:cover;border:2px solid #0D47A1;flex-shrink:0" alt=""><?php else: ?><div style="width:32px;height:32px;border-radius:50%;background:#E3F2FD;display:flex;align-items:center;justify-content:center;flex-shrink:0">👤</div><?php endif; ?>
            <div>
              <div style="font-weight:700;font-size:.83rem"><?=h($a['author'])?></div>
              <div style="font-size:.68rem;color:#9E9E9E"><?=h(roleLabel($a['author_role']))?> · <?=date('d M Y',strtotime($a['created_at']))?></div>
            </div>
          </div>
          <div style="display:flex;gap:.35rem;align-items:center">
            <span style="background:<?=catColor($a['category'])?>22;color:<?=catColor($a['category'])?>;border-radius:20px;padding:.14rem .5rem;font-size:.65rem;font-weight:700;text-transform:uppercase"><?=catIcon($a['category'])?> <?=h(ucfirst($a['category']))?></span>
            <?php if($a['is_pinned']): ?><span style="background:#FFEBEE;color:#B71C1C;border-radius:20px;padding:.1rem .45rem;font-size:.65rem;font-weight:700">📌</span><?php endif; ?>
          </div>
        </div>
        <div style="font-weight:700;font-size:.96rem;margin-bottom:.3rem"><?=h($a['title'])?></div>
        <div style="font-size:.85rem;color:#3D4F7C;line-height:1.55"><?=nl2br(h($a['body']))?></div>
      </div>
      <?php endforeach; endif; ?>
    </div>

    <!-- Sidebar -->
    <div>
      <!-- ⑥ MEMBER CARD — in sidebar, bottom of right column -->
      <div style="background:linear-gradient(135deg,#07225c,#0D47A1,#1565C0);border-radius:16px;padding:1.1rem;margin-bottom:.9rem;box-shadow:0 6px 22px rgba(13,71,161,.28);position:relative;overflow:hidden">
        <div style="position:absolute;bottom:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#B71C1C,#FFC107,#B71C1C)"></div>
        <div style="display:flex;align-items:center;gap:.75rem">
          <?php if($myPhoto): ?>
          <img src="<?=$myPhoto?>" style="width:52px;height:52px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,.55);flex-shrink:0" alt="">
          <?php else: ?>
          <div style="width:52px;height:52px;border-radius:50%;background:rgba(255,255,255,.12);border:2px solid rgba(255,255,255,.28);display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0">👤</div>
          <?php endif; ?>
          <div style="flex:1;min-width:0">
            <div style="font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.05em;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><?=h($user['name'])?></div>
            <div style="display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;margin-top:.18rem">
              <span style="background:rgba(255,193,7,.2);border:1px solid rgba(255,193,7,.38);color:#FFC107;border-radius:20px;padding:.1rem .5rem;font-size:.58rem;font-weight:700;text-transform:uppercase"><?=h(roleLabel($user['role']))?></span>
              <span style="font-size:.65rem;color:rgba(255,255,255,.5)">Blood: <b style="color:#EF9A9A"><?=h($user['blood_group']??'—')?></b></span>
              <span style="font-size:.65rem;color:rgba(255,255,255,.5)">ID: <b style="color:#fff">AV<?=str_pad($user['id'],4,'0',STR_PAD_LEFT)?></b></span>
            </div>
          </div>
          <a href="<?=url('modules/profile.php')?>" style="background:rgba(255,255,255,.12);color:#fff;border:1px solid rgba(255,255,255,.18);border-radius:8px;padding:.38rem .7rem;font-family:'DM Sans',sans-serif;font-weight:700;font-size:.73rem;text-decoration:none;flex-shrink:0;white-space:nowrap">✏️ Edit</a>
        </div>
      </div>

      <!-- Upcoming Events -->
      <?php if(!empty($evts)): ?>
      <div style="background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 2px 10px rgba(13,71,161,.08);margin-bottom:.8rem">
        <div style="background:linear-gradient(135deg,#0D47A1,#1565C0);padding:.8rem 1rem">
          <h3 style="color:#fff;font-size:.9rem;font-weight:700">📅 Upcoming Events</h3>
        </div>
        <div style="padding:.8rem">
          <?php foreach($evts as $ev): ?>
          <div style="padding:.55rem 0;border-bottom:1px solid #E8ECF4;display:flex;gap:.7rem;align-items:center">
            <div style="background:#E3F2FD;color:#07225c;border-radius:8px;padding:.28rem .45rem;text-align:center;min-width:38px;font-weight:700;font-size:.78rem;line-height:1.2;flex-shrink:0">
              <?=date('d',strtotime($ev['event_date']))?><br><span style="font-size:.58rem;text-transform:uppercase"><?=date('M',strtotime($ev['event_date']))?></span>
            </div>
            <div>
              <div style="font-weight:700;font-size:.82rem"><?=h($ev['title'])?></div>
              <?php if($ev['location']): ?><div style="font-size:.71rem;color:#9E9E9E">📍 <?=h($ev['location'])?></div><?php endif; ?>
            </div>
          </div>
          <?php endforeach; ?>
          <a href="<?=url('modules/events.php')?>" style="display:block;text-align:center;margin-top:.55rem;font-size:.76rem;font-weight:700;color:#0D47A1">View all →</a>
        </div>
      </div>
      <?php endif; ?>
    </div>
  </div>

  <!-- QR Scan Popup (admin only, no widget bar) -->
  <?php if(isAdminRole($user['role']) || canPost($user['role'])): ?>
  <div id="scanPopup" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:9000;flex-direction:column;align-items:center;justify-content:center;padding:1rem">
    <div style="width:100%;max-width:360px;background:#0d1b3e;border-radius:18px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.5)">
      <div style="background:#0d47a1;padding:.9rem 1.1rem;display:flex;align-items:center;justify-content:space-between">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:.95rem;letter-spacing:.1em;color:#fff">📷 SCAN VOLUNTEER QR</div>
        <button onclick="closeDashScan()" style="background:rgba(255,255,255,.15);border:none;color:#fff;width:30px;height:30px;border-radius:50%;cursor:pointer;font-size:1rem;display:flex;align-items:center;justify-content:center">✕</button>
      </div>
      <div style="position:relative;background:#000;width:100%">
        <video id="dashVideo" style="width:100%;display:block;max-height:280px;object-fit:cover" autoplay playsinline muted></video>
        <canvas id="dashCanvas" style="display:none"></canvas>
        <div id="dashFrame" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none">
          <div style="width:200px;height:200px;position:relative">
            <div style="position:absolute;top:0;left:0;width:28px;height:28px;border-top:3px solid #4fc3f7;border-left:3px solid #4fc3f7;border-radius:3px 0 0 0"></div>
            <div style="position:absolute;top:0;right:0;width:28px;height:28px;border-top:3px solid #4fc3f7;border-right:3px solid #4fc3f7;border-radius:0 3px 0 0"></div>
            <div style="position:absolute;bottom:0;left:0;width:28px;height:28px;border-bottom:3px solid #4fc3f7;border-left:3px solid #4fc3f7;border-radius:0 0 0 3px"></div>
            <div style="position:absolute;bottom:0;right:0;width:28px;height:28px;border-bottom:3px solid #4fc3f7;border-right:3px solid #4fc3f7;border-radius:0 0 3px 0"></div>
            <div style="position:absolute;left:8px;right:8px;height:2px;background:linear-gradient(90deg,transparent,#4fc3f7,transparent);animation:scanAnim 1.8s ease-in-out infinite;top:50%"></div>
          </div>
          <div style="position:absolute;bottom:12px;left:50%;transform:translateX(-50%);color:#4fc3f7;font-size:.68rem;font-weight:700;letter-spacing:.1em;white-space:nowrap">POINT AT QR CODE</div>
        </div>
      </div>
      <div id="dashResult" style="padding:.85rem 1rem;min-height:60px">
        <p style="color:rgba(255,255,255,.4);font-size:.78rem;text-align:center">Position the QR code inside the frame</p>
      </div>
      <div style="padding:0 1rem .9rem">
        <div style="font-size:.65rem;color:rgba(255,255,255,.28);text-align:center;margin-bottom:.4rem">— or paste token —</div>
        <input type="text" id="dashTokenInput" placeholder="Paste QR token here" style="width:100%;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);border-radius:8px;padding:.58rem .85rem;font-family:Inter,sans-serif;font-size:.85rem;color:#fff;outline:none;text-align:center" oninput="dashVerifyToken(this.value)">
      </div>
    </div>
  </div>
  <?php endif; ?>

</div>

<style>
@keyframes scanAnim{0%{top:10%;opacity:0}20%{opacity:1}80%{opacity:1}100%{top:85%;opacity:0}}
@keyframes livePulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}
#actTrack .act-bg{transform:scale(1)}
#actWrap::-webkit-scrollbar{display:none}
.inp{width:100%;padding:.68rem .9rem;border:2px solid #E8ECF4;border-radius:9px;font-family:'DM Sans',sans-serif;font-size:.9rem;color:#0D1B3E;background:#fff;outline:none;-webkit-appearance:none;transition:border-color .18s}
.inp:focus{border-color:#0D47A1;box-shadow:0 0 0 3px rgba(13,71,161,.1)}
select.inp{cursor:pointer}
.cmcard:hover{transform:translateY(-3px);box-shadow:0 6px 20px rgba(74,20,140,.15)!important}
@media(min-width:820px){#dashGrid{grid-template-columns:1fr 310px!important}}
@media(max-width:500px){#comGrid{grid-template-columns:1fr 1fr!important}}
</style>

<script>
/* ── Collapsible sections ──────────────────────── */
function toggleCollapse(id){
  var el=document.getElementById(id);
  if(!el)return;
  el.classList.toggle('open');
  var btn=el.querySelector('.db-collapse-head');
  if(btn)btn.setAttribute('aria-expanded', el.classList.contains('open')?'true':'false');
}

/* ── Active Slider ─────────────────────────────── */
var sliderTotal = <?= count($sliderItems) ?>;
var sliderIdx   = 0;
var sliderTimer = null;

function goSlide(n) {
  sliderIdx = (n + sliderTotal) % sliderTotal;
  var track = document.getElementById('liveSlider');
  if (track) track.style.transform = 'translateX(-' + (sliderIdx * 100) + '%)';
  // Update dots
  for (var i = 0; i < sliderTotal; i++) {
    var d = document.getElementById('dot' + i);
    if (!d) continue;
    d.style.width   = i === sliderIdx ? '22px' : '7px';
    d.style.background = i === sliderIdx ? '#fff' : 'rgba(255,255,255,.45)';
  }
  // Pan bg image slightly
  var bgs = document.querySelectorAll('.slide-bg');
  bgs.forEach(function(b, bi) {
    b.style.transform = bi === sliderIdx ? 'scale(1.05)' : 'scale(1)';
  });
}
function nextSlide() { clearInterval(sliderTimer); goSlide(sliderIdx + 1); startAutoSlide(); }
function prevSlide() { clearInterval(sliderTimer); goSlide(sliderIdx - 1); startAutoSlide(); }
function startAutoSlide() {
  if (sliderTotal <= 1) return;
  sliderTimer = setInterval(function() { goSlide(sliderIdx + 1); }, 4000);
}
if (sliderTotal > 0) { goSlide(0); startAutoSlide(); }

/* ── jsQR pre-load ─────────────────────────────── */
var dashJsqrReady = false;
(function(){
  var s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js';
  s.onload = function(){ dashJsqrReady = true; };
  s.onerror = function(){
    var s2 = document.createElement('script');
    s2.src = 'https://unpkg.com/jsqr@1.4.0/dist/jsQR.js';
    s2.onload = function(){ dashJsqrReady = true; };
    document.head.appendChild(s2);
  };
  document.head.appendChild(s);
})();

var dashStream = null, dashLoop = null;

function openDashScan(){
  var p = document.getElementById('scanPopup');
  if (!p) return;
  p.style.display = 'flex';
  document.body.style.overflow = 'hidden';
  startDashCamera();
}
function closeDashScan(){
  stopDashCamera();
  var p = document.getElementById('scanPopup');
  if (p) p.style.display = 'none';
  document.body.style.overflow = '';
  var ti = document.getElementById('dashTokenInput');
  if (ti) ti.value = '';
  var dr = document.getElementById('dashResult');
  if (dr) dr.innerHTML = '<p style="color:rgba(255,255,255,.4);font-size:.78rem;text-align:center">Position the QR code inside the frame</p>';
}
function resetDashScan(){
  var dr = document.getElementById('dashResult');
  if (dr) dr.innerHTML = '<p style="color:rgba(255,255,255,.4);font-size:.78rem;text-align:center">Position the QR code inside the frame</p>';
  var ti = document.getElementById('dashTokenInput');
  if (ti) ti.value = '';
  startDashCamera();
}
function startDashCamera(){
  var video = document.getElementById('dashVideo');
  if (!video) return;
  navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}},audio:false})
  .then(function(stream){
    dashStream = stream;
    video.srcObject = stream;
    video.style.display = 'block';
    video.onloadedmetadata = function(){
      video.play().then(function(){ waitDashJsqr(0); }).catch(function(){ waitDashJsqr(0); });
    };
    setTimeout(function(){ if(video.readyState>=2) waitDashJsqr(0); }, 1000);
  })
  .catch(function(err){
    var dr = document.getElementById('dashResult');
    var msg = '❌ Camera denied. Paste token below.';
    if (err.name==='NotAllowedError') msg = '🔒 Allow camera access in browser settings.';
    if (err.name==='NotFoundError')   msg = '📷 No camera found.';
    if (dr) dr.innerHTML = '<div style="color:#ff8a80;font-size:.8rem;padding:.5rem 0">'+msg+'</div>';
  });
}
function waitDashJsqr(t){
  if (t > 40) { var dr=document.getElementById('dashResult'); if(dr) dr.innerHTML='<div style="color:#ff8a80;font-size:.8rem">⚠️ QR library failed. Refresh.</div>'; return; }
  if (typeof jsQR !== 'undefined') { dashJsqrReady=true; startDashLoop(); var dr=document.getElementById('dashResult'); if(dr) dr.innerHTML='<p style="color:rgba(255,255,255,.4);font-size:.78rem;text-align:center">📷 Ready — point at QR code</p>'; }
  else setTimeout(function(){ waitDashJsqr(t+1); }, 200);
}
function startDashLoop(){
  var video=document.getElementById('dashVideo'), canvas=document.getElementById('dashCanvas');
  if (!canvas) return;
  var ctx=canvas.getContext('2d');
  if (dashLoop) { clearInterval(dashLoop); dashLoop=null; }
  dashLoop=setInterval(function(){
    if (!video||video.readyState<2||video.paused||video.videoWidth===0) return;
    try {
      canvas.width=video.videoWidth; canvas.height=video.videoHeight;
      ctx.drawImage(video,0,0,canvas.width,canvas.height);
      var d=ctx.getImageData(0,0,canvas.width,canvas.height);
      var code=jsQR(d.data,d.width,d.height,{inversionAttempts:'attemptBoth'});
      if (code&&code.data&&code.data.length>5) { clearInterval(dashLoop);dashLoop=null; dashVerifyToken(code.data); }
    } catch(e){}
  }, 200);
}
function stopDashCamera(){
  if (dashLoop) { clearInterval(dashLoop); dashLoop=null; }
  if (dashStream) { dashStream.getTracks().forEach(function(t){ t.stop(); }); dashStream=null; }
  var v=document.getElementById('dashVideo');
  if (v) { v.style.display='none'; v.srcObject=null; }
}
var dashVTimer=null;
function dashVerifyToken(val){
  clearTimeout(dashVTimer);
  if (!val||val.length<8) return;
  dashVTimer=setTimeout(function(){
    var t=val, m=val.match(/verify_vol=([a-f0-9]+)/);
    if (m) t=m[1];
    var dr=document.getElementById('dashResult');
    if (dr) dr.innerHTML='<p style="color:#90caf9;font-size:.8rem;text-align:center">⏳ Verifying…</p>';
    fetch('<?= url('modules/idcard.php') ?>?verify_vol='+encodeURIComponent(t))
    .then(function(r){return r.json();})
    .then(function(d){
      var dr=document.getElementById('dashResult');
      if (!dr) return;
      if (d.ok) {
        var dat=d.data;
        dr.innerHTML='<div style="background:rgba(0,230,118,.12);border:1.5px solid rgba(0,230,118,.35);border-radius:9px;padding:.8rem">'
          +'<div style="color:#00e676;font-weight:800;font-size:.9rem;margin-bottom:.5rem">✅ VALID VOLUNTEER</div>'
          +'<div style="font-size:.84rem;font-weight:700;color:#fff">'+dat.mname+'</div>'
          +'<div style="font-size:.74rem;color:rgba(255,255,255,.6);margin:.15rem 0">'+dat.etitle+'</div>'
          +'<div style="font-size:.74rem;color:rgba(255,255,255,.6)">'+dat.edate+'</div>'
          +(dat.mblood?'<div style="font-size:.74rem;color:#ff8a80;font-weight:700;margin-top:.2rem">🩸 '+dat.mblood+'</div>':'')
          +'<button onclick="resetDashScan()" style="margin-top:.6rem;background:rgba(255,255,255,.15);color:#fff;border:none;border-radius:7px;padding:.38rem .8rem;font-family:Inter,sans-serif;font-size:.74rem;font-weight:700;cursor:pointer">📷 Scan Next</button>'
          +'</div>';
      } else {
        dr.innerHTML='<div style="background:rgba(255,82,82,.12);border:1.5px solid rgba(255,82,82,.3);border-radius:9px;padding:.8rem;color:#ff5252;font-weight:700;font-size:.84rem">❌ '+(d.msg||'Invalid QR code')+'</div>';
      }
    }).catch(function(){ var dr=document.getElementById('dashResult'); if(dr) dr.innerHTML='<div style="color:#ff8a80;font-size:.8rem">Network error.</div>'; });
  }, 400);
}
/* ── Activity Slider ───────────────────────────── */
var actTotal = <?= $actTotal ?? 0 ?>;
var actIdx   = 0;
var actTimer = null;

function actGo(n) {
  actIdx = (n + actTotal) % actTotal;
  var track = document.getElementById('actTrack');
  if (track) track.style.transform = 'translateX(-' + (actIdx * 100) + '%)';
  for (var i = 0; i < actTotal; i++) {
    var d = document.getElementById('actDot' + i);
    if (!d) continue;
    d.style.width      = i === actIdx ? '22px' : '7px';
    d.style.background = i === actIdx ? '#fff' : 'rgba(255,255,255,.4)';
  }
  // Ken Burns on active bg
  document.querySelectorAll('.act-bg').forEach(function(bg, bi) {
    bg.style.transform = bi === actIdx ? 'scale(1.06)' : 'scale(1)';
  });
}
function actNext() { clearInterval(actTimer); actGo(actIdx + 1); actAutoPlay(); }
function actPrev() { clearInterval(actTimer); actGo(actIdx - 1); actAutoPlay(); }
function actAutoPlay() {
  if (actTotal <= 1) return;
  actTimer = setInterval(function() { actGo(actIdx + 1); }, 4500);
}
if (actTotal > 0) { actGo(0); actAutoPlay(); }

var _sp=document.getElementById('scanPopup');
if (_sp) { _sp.addEventListener('click',function(e){if(e.target===this)closeDashScan();}); }
document.addEventListener('keydown',function(e){ if(e.key==='Escape') closeDashScan(); });
</script>
<?php if($predLeague['active']): ?>
<!-- ══════════════════════════════════════════════
     FIFA WC 2026 PREDICTION LEAGUE — DASHBOARD CARD
     ══════════════════════════════════════════════ -->
<div style="padding:.7rem 1rem 0">

  <!-- Section header -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.65rem">
    <div style="display:flex;align-items:center;gap:.5rem">
      <span style="font-size:1.1rem">⚽</span>
      <span style="font-size:.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.12em">Prediction League</span>
    </div>
    <a href="<?= url('modules/prediction.php') ?>" style="font-size:.68rem;font-weight:700;color:#ffd700;text-decoration:none">View All →</a>
  </div>

  <!-- Main card -->
  <div style="background:linear-gradient(145deg,#050a1a,#0d2137);border-radius:18px;overflow:hidden;border:1.5px solid rgba(255,215,0,.2);box-shadow:0 6px 24px rgba(5,10,26,.5)">

    <!-- Live match banner (if any) -->
    <?php if(!empty($predLeague['live'])): $lv=$predLeague['live']; ?>
    <div style="background:linear-gradient(90deg,rgba(255,51,102,.18),rgba(255,51,102,.08));border-bottom:1px solid rgba(255,51,102,.25);padding:.55rem 1rem;display:flex;align-items:center;gap:.55rem">
      <span style="width:8px;height:8px;border-radius:50%;background:#ff3366;display:inline-block;animation:livePulse 1.2s infinite;flex-shrink:0"></span>
      <span style="font-size:.65rem;font-weight:800;color:#ff3366;letter-spacing:.08em;text-transform:uppercase">LIVE</span>
      <span style="font-size:.78rem;font-weight:700;color:#fff;flex:1">
        <?= h($lv['team1_flag']?:'')?> <?= h($lv['team1']) ?> vs <?= h($lv['team2_flag']?:'')?> <?= h($lv['team2']) ?>
      </span>
      <a href="<?= url('modules/prediction.php') ?>" style="font-size:.62rem;color:#ff3366;font-weight:800;text-decoration:none;border:1px solid rgba(255,51,102,.35);border-radius:20px;padding:.15rem .55rem">Watch →</a>
    </div>
    <?php endif; ?>

    <!-- My stats row -->
    <div style="display:grid;grid-template-columns:repeat(3,1fr);border-bottom:1px solid rgba(255,255,255,.06)">
      <div style="padding:.65rem .5rem;text-align:center;border-right:1px solid rgba(255,255,255,.06)">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:#ffd700;line-height:1"><?= (int)($predLeague['my']['pts']??0) ?></div>
        <div style="font-size:.52rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.08em;margin-top:.1rem">My Points</div>
      </div>
      <div style="padding:.65rem .5rem;text-align:center;border-right:1px solid rgba(255,255,255,.06)">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:#ffd700;line-height:1"><?= (int)($predLeague['my']['correct']??0) ?>/<?= (int)($predLeague['my']['total']??0) ?></div>
        <div style="font-size:.52rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.08em;margin-top:.1rem">Correct</div>
      </div>
      <div style="padding:.65rem .5rem;text-align:center">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:#ffd700;line-height:1">#<?= (int)($predLeague['my']['rank']??1) ?></div>
        <div style="font-size:.52rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.08em;margin-top:.1rem">My Rank</div>
      </div>
    </div>

    <!-- Leaderboard top 3 -->
    <?php if(!empty($predLeague['top3'])): ?>
    <div style="padding:.65rem .85rem .55rem">
      <div style="font-size:.58rem;font-weight:800;color:rgba(255,215,0,.5);letter-spacing:.12em;text-transform:uppercase;margin-bottom:.55rem">🏆 Top Predictors</div>
      <?php
      $medals = ['🥇','🥈','🥉'];
      $topBg  = [
        'linear-gradient(135deg,rgba(255,215,0,.12),rgba(255,215,0,.04))',
        'linear-gradient(135deg,rgba(192,192,192,.1),rgba(192,192,192,.03))',
        'linear-gradient(135deg,rgba(205,127,50,.1),rgba(205,127,50,.03))',
      ];
      foreach($predLeague['top3'] as $i=>$tp):
      ?>
      <div style="display:flex;align-items:center;gap:.65rem;padding:.5rem .6rem;border-radius:11px;margin-bottom:.35rem;background:<?= $topBg[$i] ?>;border:1px solid rgba(255,215,0,<?= $i===0?'.2':'.07' ?>)">
        <span style="font-size:1rem;flex-shrink:0"><?= $medals[$i] ?></span>
        <?php if($tp['photo']): ?>
          <img src="<?= $tp['photo'] ?>" style="width:32px;height:32px;border-radius:50%;object-fit:cover;border:1.5px solid rgba(255,215,0,.25);flex-shrink:0">
        <?php else: ?>
          <div style="width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,.08);border:1.5px solid rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;font-size:.85rem;flex-shrink:0">👤</div>
        <?php endif; ?>
        <div style="flex:1;min-width:0">
          <div style="font-size:.8rem;font-weight:800;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><?= h($tp['name']) ?></div>
          <div style="font-size:.6rem;color:rgba(255,255,255,.35)"><?= (int)$tp['correct'] ?> correct picks</div>
        </div>
        <div style="text-align:right;flex-shrink:0">
          <div style="font-family:'Bebas Neue',sans-serif;font-size:1.2rem;color:#ffd700;line-height:1"><?= (int)$tp['pts'] ?></div>
          <div style="font-size:.5rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.06em">pts</div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>

    <!-- Next match + predict button -->
    <?php if(!empty($predLeague['upcoming'])): $um=$predLeague['upcoming']; ?>
    <div style="padding:.55rem .85rem .8rem;border-top:1px solid rgba(255,255,255,.05)">
      <div style="font-size:.58rem;font-weight:800;color:rgba(255,255,255,.3);letter-spacing:.1em;text-transform:uppercase;margin-bottom:.45rem">⏳ Next Match</div>
      <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.55rem">
        <span style="font-size:1.5rem"><?= h($um['team1_flag']?:'🏳') ?></span>
        <div style="flex:1;text-align:center">
          <div style="font-size:.65rem;font-weight:800;color:#fff"><?= h($um['team1']) ?> vs <?= h($um['team2']) ?></div>
          <div style="font-size:.58rem;color:rgba(255,255,255,.3);margin-top:.1rem"><?= date('D d M · H:i',strtotime($um['match_date'])) ?></div>
        </div>
        <span style="font-size:1.5rem"><?= h($um['team2_flag']?:'🏳') ?></span>
      </div>
      <a href="<?= url('modules/prediction.php') ?>" style="display:flex;align-items:center;justify-content:center;gap:.5rem;width:100%;padding:.7rem;background:linear-gradient(135deg,#ffd700,#e6a800);color:#000;border-radius:11px;font-weight:900;font-size:.85rem;text-decoration:none;letter-spacing:.04em;box-shadow:0 4px 14px rgba(255,215,0,.25)">
        🎯 Make Your Prediction
      </a>
    </div>
    <?php elseif(empty($predLeague['live'])): ?>
    <div style="padding:.7rem .85rem .85rem;text-align:center">
      <a href="<?= url('modules/prediction.php') ?>" style="display:flex;align-items:center;justify-content:center;gap:.5rem;width:100%;padding:.7rem;background:linear-gradient(135deg,#ffd700,#e6a800);color:#000;border-radius:11px;font-weight:900;font-size:.85rem;text-decoration:none;letter-spacing:.04em">
        ⚽ Open Prediction League
      </a>
    </div>
    <?php endif; ?>

  </div>
</div>

<style>
@keyframes livePulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.3)}}
</style>
<?php endif; ?>

<?php
// ── Henna Fest Dashboard Section ──
$_dbHenna = false;
$_dbHEntries  = [];
$_dbHSettings = null;
$_dbHMyVote   = 0;
$_dbHPoster   = '';
$_dbHFestId   = 1;
try {
  if (db()->query("SHOW TABLES LIKE 'henna_entries'")->fetch()) {
    // Get settings - try henna_fest_settings first (working table)
    try {
      $_dbHSettings = db()->query("SELECT * FROM henna_fest_settings LIMIT 1")->fetch();
      $_dbHPoster   = $_dbHSettings['event_poster'] ?? '';
      $_dbHFestId   = 1;
    } catch(Exception $ex2) {}

    // Top 10 entries by likes
    $_dbHEntries = db()->query(
      "SELECT e.*,u.name member_name FROM henna_entries e
       JOIN users u ON u.id=e.member_id
       WHERE e.status='active'
       ORDER BY e.vote_count DESC, e.created_at ASC LIMIT 10"
    )->fetchAll();

    // My vote
    $_dbHMyVoteStmt = db()->prepare("SELECT entry_id FROM henna_votes WHERE voter_id=? LIMIT 1");
    $_dbHMyVoteStmt->execute([$user['id']]);
    $mv = $_dbHMyVoteStmt->fetchColumn();
    $_dbHMyVote = $mv ? (int)$mv : 0;

    $_dbHenna = !empty($_dbHEntries);
  }
} catch(Exception $ex){}
?>
<?php if($_dbHenna): ?>
<?php
$_dbHSiteUrl  = rtrim(SITE_URL, '/');
$_dbHVotingOn = $_dbHSettings ? (bool)$_dbHSettings['voting_open'] : false;
$_dbHTitle    = $_dbHSettings ? ($_dbHSettings['event_title'] ?? 'Henna Fest') : 'Henna Fest';
?>
<div style="margin:1rem;background:#fff;border-radius:18px;overflow:hidden;box-shadow:0 3px 16px rgba(139,58,15,.1);border:1.5px solid rgba(196,82,26,.12)">

  <!-- Section header -->
  <div style="background:linear-gradient(135deg,#2D1B0E,#8B3A0F);padding:.8rem 1rem;display:flex;align-items:center;justify-content:space-between">
    <div>
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:.08em;color:#fff">🌿 <?php echo h($_dbHTitle); ?></div>
      <div style="font-size:.62rem;color:rgba(255,255,255,.5)"><?php echo $_dbHVotingOn ? '❤️ Tap any photo to like!' : '🔒 Voting closed'; ?></div>
    </div>
    <a href="<?php echo url('modules/henna_fest.php'); ?>" style="background:#D4A017;color:#000;border:none;border-radius:10px;padding:.38rem .8rem;font-weight:800;font-size:.72rem;text-decoration:none">View All →</a>
  </div>

  <!-- Event Poster (if set) -->
  <?php if($_dbHPoster): ?>
  <div style="cursor:pointer" onclick="window.location='<?php echo url('modules/henna_fest.php'); ?>'">
    <img src="<?php echo h($_dbHSiteUrl.'/assets/uploads/henna/'.basename($_dbHPoster)); ?>"
         style="width:100%;max-height:200px;object-fit:cover;display:block" loading="lazy" alt="Fest Poster">
  </div>
  <?php endif; ?>

  <!-- Top 10 entries strip -->
  <div style="display:flex;gap:.6rem;padding:.75rem;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none">
    <?php foreach($_dbHEntries as $_dbHRank => $_dbHE):
      // Build correct image URL — check fest_id subfolder first, then root henna folder
      $_dbHFid    = (int)($_dbHE['fest_id'] ?? 1);
      $_dbHImgSub = $_dbHSiteUrl.'/assets/uploads/henna/'.$_dbHFid.'/'.basename($_dbHE['image_path']);
      $_dbHImgOld = $_dbHSiteUrl.'/assets/uploads/henna/'.basename($_dbHE['image_path']);
      // Use subfolder path (new uploads go here)
      $_dbHImgUrl = $_dbHImgSub;
      $_dbHIsOwn  = (int)$_dbHE['member_id'] === (int)$user['id'];
      $_dbHVotedThis = $_dbHMyVote === (int)$_dbHE['id'];
      $_dbHCanLike   = $_dbHVotingOn && !$_dbHMyVote && !$_dbHIsOwn;
      $_dbHBorder = $_dbHVotedThis ? '#C4521A' : ($rank===0 ? '#D4A017' : 'rgba(196,82,26,.12)');
    ?>
    <div style="flex-shrink:0;width:130px;border-radius:14px;overflow:hidden;background:#fff;border:2px solid <?php echo $_dbHBorder; ?>;box-shadow:0 2px 10px rgba(139,58,15,.1);cursor:pointer;position:relative"
         onclick="window.location='<?php echo url('modules/henna_fest.php'); ?>'">
      <!-- Rank badge for top 3 -->
      <?php if($_dbHRank < 3 && $_dbHE['vote_count'] > 0): ?>
      <div style="position:absolute;top:5px;left:5px;width:22px;height:22px;border-radius:50%;background:<?php echo $_dbHRank===0?'#D4A017':($_dbHRank===1?'#9e9e9e':'#cd7f32'); ?>;display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:900;color:<?php echo $_dbHRank===0?'#000':'#fff'; ?>;z-index:5;box-shadow:0 1px 4px rgba(0,0,0,.3)">
        <?php echo $_dbHRank+1; ?>
      </div>
      <?php endif; ?>
      <img src="<?php echo h($_dbHImgUrl); ?>"
           style="width:130px;height:155px;object-fit:cover;display:block" loading="lazy" alt=""
           onerror="this.src='<?php echo h($_dbHImgOld); ?>'">
      <div style="padding:.4rem .5rem">
        <div style="font-size:.63rem;font-weight:800;color:#8B3A0F;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><?php echo h($_dbHE['member_name']); ?></div>
        <div style="font-size:.68rem;color:<?php echo $_dbHVotedThis ? '#C4521A' : '#94a3b8'; ?>;font-weight:700">
          <?php echo $_dbHVotedThis ? '✅' : '❤️'; ?> <?php echo (int)$_dbHE['vote_count']; ?>
        </div>
      </div>
    </div>
    <?php endforeach; ?>
  </div>

  <!-- Footer link -->
  <div style="text-align:center;padding:.4rem .5rem .6rem;font-size:.68rem;color:#94a3b8">
    <a href="<?php echo url('modules/henna_fest.php'); ?>" style="color:#8B3A0F;font-weight:700;text-decoration:none">View all entries & submit yours →</a>
  </div>

</div>
<?php endif; ?>
<?php require_once __DIR__.'/includes/footer.php'; ?>
