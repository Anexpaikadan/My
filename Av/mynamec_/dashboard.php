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

<?php
// ── View data ──
$hr = (int)date('G');
$greet = $hr < 12 ? 'Good morning' : ($hr < 17 ? 'Good afternoon' : 'Good evening');
$isAdm = isAdminRole($user['role']);
$catConf = array(
  'general'=>array('Notice','megaphone','teal'),'match'=>array('Match','ball','lime'),'meeting'=>array('Meeting','clipboard','slate'),
  'festival'=>array('Festival','masks','violet'),'blood'=>array('Blood','droplet','rose'),'important'=>array('Important','star','amber'),
);
$groups = array();
foreach (app_modules() as $m) { $groups[$m[4]][] = $m; }
?>
<style>
/* ═══ Dashboard: dark glass launcher ═══ */
body{background:var(--surface)}
.dk{color:var(--text);position:relative;background:var(--surface)}
.hero-card{position:relative;overflow:hidden;color:#fff;border-radius:26px;padding:1.1rem 1rem 1rem;margin-bottom:.4rem;
  background:radial-gradient(60% 90% at 100% 0%,rgba(255,255,255,.18),transparent 60%),var(--brand-grad);box-shadow:0 18px 40px -20px rgba(10,20,224,.7)}
.hero-card .club-logo{position:absolute;right:-26px;bottom:-26px;width:150px;height:150px;border-radius:50%;opacity:.16;object-fit:cover}
.dk-in{max-width:1100px;margin:0 auto;padding:1rem 1rem 1.5rem}
.glass{background:#fff;border:1px solid var(--line);border-radius:22px;box-shadow:var(--sh-1)}
.hero-card .glass{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.28);box-shadow:none;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.hi{display:flex;align-items:center;gap:.85rem;padding:.4rem .1rem 1rem}
.hi img,.hi .ph{width:56px;height:56px;border-radius:50%;object-fit:cover;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;border:2px solid rgba(255,255,255,.85)}
.hi small{display:block;font-size:.82rem;color:rgba(255,255,255,.9);font-weight:600}
.hi b{font-size:1.25rem;font-weight:800;letter-spacing:-.02em;line-height:1.2}
.hi .role{display:inline-block;margin-top:.25rem;font-size:.72rem;font-weight:700;color:var(--primary-dark);background:#fff;padding:.14rem .6rem;border-radius:999px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem}
.kpi{padding:.75rem .4rem;text-align:center}
.kpi b{display:block;font-size:1.45rem;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.kpi span{font-size:.68rem;font-weight:700;color:rgba(255,255,255,.92);text-transform:uppercase;letter-spacing:.05em}
.kpi.warn{background:#fff!important}.kpi.warn b{color:var(--accent-ink)}.kpi.warn span{color:var(--accent-ink)}
.dk-h{display:flex;align-items:center;justify-content:space-between;margin:1.1rem .1rem .6rem}
.dk-h h2{font-size:.8rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--text-3)}
.dk-h a{font-size:.8rem;font-weight:700;color:var(--primary);padding:.3rem .2rem}
/* app grid */
.apps{display:grid;grid-template-columns:repeat(4,1fr);gap:.9rem .4rem;padding:1rem .5rem}
@media(min-width:620px){.apps{grid-template-columns:repeat(6,1fr)}}
@media(min-width:900px){.apps{grid-template-columns:repeat(8,1fr)}}
.app{display:flex;flex-direction:column;align-items:center;gap:.45rem;font-size:.75rem;font-weight:600;color:var(--text-2);text-align:center;line-height:1.2;padding:.2rem 0;border-radius:16px;position:relative}
.app .appic{width:62px;height:62px;border-radius:20px}
.app .appic .app-img{width:44px;height:44px}
.app .badge{position:absolute;top:-4px;right:calc(50% - 36px);min-width:20px;height:20px;padding:0 5px;border-radius:10px;background:var(--accent);color:#fff;font-size:.68rem;font-weight:800;display:flex;align-items:center;justify-content:center;border:2px solid #fff;z-index:2}
/* activity slider */
.slides{display:flex;gap:.7rem;overflow-x:auto;scroll-snap-type:x mandatory;padding:.1rem .1rem .4rem;scrollbar-width:none}
.slides::-webkit-scrollbar{display:none}
.slide{flex:0 0 86%;max-width:420px;height:190px;border-radius:22px;scroll-snap-align:start;position:relative;overflow:hidden;color:#fff;display:flex;flex-direction:column;justify-content:flex-end;padding:1rem;box-shadow:var(--sh-1)}
.slide img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.slide::before{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(11,16,51,.05) 20%,rgba(11,16,51,.9));z-index:1}
.slide>*{position:relative;z-index:2}
.slide .type{font-size:.68rem;font-weight:800;letter-spacing:.1em;color:#fff;background:var(--accent);align-self:flex-start;padding:.1rem .5rem;border-radius:6px}
.slide b{font-size:1.08rem;font-weight:800;line-height:1.25;margin:.15rem 0}
.slide span{font-size:.8rem;color:rgba(255,255,255,.82)}
/* light content area */
.lt{background:var(--surface);color:var(--text);position:relative}
.lt-in{max-width:1100px;margin:0 auto;padding:1.3rem 1rem 1.5rem;display:grid;gap:1rem}
@media(min-width:900px){.lt-in{grid-template-columns:1.6fr 1fr;align-items:start}}
.panel{background:#fff;border:1px solid var(--line);border-radius:22px;box-shadow:var(--sh-1);overflow:hidden}
.panel-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.95rem 1.1rem;border-bottom:1px solid var(--line)}
.panel-h h3{font-size:1rem;font-weight:800;letter-spacing:-.01em;display:flex;align-items:center;gap:.5rem}
.panel-h a{font-size:.8rem;font-weight:700;color:var(--primary)}
.panel-b{padding:.9rem 1.1rem}
.note{display:flex;gap:.75rem;padding:.8rem 0;border-bottom:1px solid var(--line)}
.note:last-child{border-bottom:0}
.note .tile{width:40px;height:40px;border-radius:13px;flex-shrink:0}
.note .tile .ic{width:20px;height:20px}
.note b{display:block;font-size:.92rem;line-height:1.3}
.note p{font-size:.84rem;color:var(--text-2);margin-top:.15rem;white-space:pre-line}
.note small{font-size:.74rem;color:var(--text-3)}
.pill{display:inline-block;font-size:.66rem;font-weight:800;padding:.1rem .5rem;border-radius:999px;margin-left:.3rem;vertical-align:middle}
.pill.urgent{background:#FFF4E5;color:#9A3412}.pill.emergency{background:#FDECEC;color:#B91C1C}.pill.pin{background:var(--primary-soft);color:var(--primary-dark)}
.ev{display:flex;gap:.75rem;align-items:center;padding:.6rem 0;border-bottom:1px solid var(--line)}
.ev:last-child{border-bottom:0}
.ev .date{width:46px;height:50px;border-radius:14px;background:var(--primary-soft);color:var(--primary-dark);display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:800;line-height:1;flex-shrink:0}
.ev .date small{font-size:.62rem;text-transform:uppercase;margin-top:.15rem}
.ev b{font-size:.9rem;display:block}.ev span{font-size:.78rem;color:var(--text-3)}
.mcard{border-radius:22px;padding:1.1rem;color:#fff;position:relative;overflow:hidden;background:var(--brand-grad);box-shadow:0 14px 30px -18px rgba(10,20,224,.7)}
.mcard .row{display:flex;align-items:center;gap:.8rem}
.mcard img,.mcard .ph{width:56px;height:56px;border-radius:18px;object-fit:cover;background:rgba(255,255,255,.12);display:flex;align-items:center;justify-content:center}
.mcard b{font-size:1.05rem;font-weight:800}
.mcard .meta{display:flex;gap:.9rem;margin-top:.9rem;font-size:.78rem;color:rgba(255,255,255,.8)}
.mcard .meta strong{display:block;color:#fff;font-size:.95rem}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:.6rem}
.person{text-align:center;font-size:.76rem}
.person img,.person .ph{width:56px;height:56px;border-radius:18px;object-fit:cover;margin:0 auto .35rem;background:var(--primary-soft);color:var(--primary);display:flex;align-items:center;justify-content:center}
.person b{display:block;font-size:.8rem;line-height:1.25}
.person span{color:var(--text-3);font-size:.7rem}
.ach{display:flex;gap:.6rem;overflow-x:auto;scrollbar-width:none;padding-bottom:.2rem}
.ach-i{flex:0 0 150px;border-radius:18px;background:var(--surface);border:1px solid var(--line);overflow:hidden}
.ach-i img,.ach-i .ph{width:100%;height:96px;object-fit:cover;background:linear-gradient(145deg,#FFF1C7,#FFD873);display:flex;align-items:center;justify-content:center;color:#fff}
.ach-i div{padding:.55rem .65rem}
.ach-i b{font-size:.8rem;display:block;line-height:1.25}
.ach-i span{font-size:.72rem;color:var(--text-3)}
.empty{text-align:center;color:var(--text-3);font-size:.88rem;padding:1rem .5rem}
details.post summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:.5rem;font-weight:700;color:var(--primary);font-size:.88rem;min-height:44px}
details.post summary::-webkit-details-marker{display:none}
.sec-gap{grid-column:1/-1}
</style>

<div class="dk">
 <div class="dk-in">
  <div class="hero-card">
  <?php if($logoB64): ?><img class="club-logo" src="<?= $logoB64 ?>" alt=""><?php endif; ?>
  <!-- Greeting -->
  <div class="hi">
    <?php if($myPhoto): ?><img src="<?= $myPhoto ?>" alt=""><?php else: ?><span class="ph"><?= app_img('profile',38) ?></span><?php endif; ?>
    <div style="min-width:0">
      <small><?= $greet ?></small>
      <b><?= h($user['name']) ?></b><br>
      <span class="role"><?= h(roleLabel($user['role'])) ?></span>
    </div>
  </div>

  <!-- Key numbers -->
  <div class="kpis">
    <a href="<?= url('modules/members.php') ?>" class="kpi glass"><b><?= (int)($stats['total']??0) ?></b><span>Members</span></a>
    <a href="<?= url('modules/members.php') ?>" class="kpi glass"><b><?= (int)($stats['active']??0) ?></b><span>Active</span></a>
    <a href="<?= url('modules/blood.php') ?>" class="kpi glass"><b><?= (int)($stats['donors']??0) ?></b><span>Donors</span></a>
    <?php if($isAdm): ?>
    <a href="<?= url('admin.php') ?>" class="kpi glass<?= $pendingCount?' warn':'' ?>"><b><?= (int)$pendingCount ?></b><span>Pending</span></a>
    <?php else: ?>
    <a href="<?= url('modules/events.php') ?>" class="kpi glass"><b><?= count($evts) ?></b><span>Events</span></a>
    <?php endif; ?>
  </div>

  </div>

  <!-- Activity slider -->
  <?php if(!empty($sliderItems)): ?>
  <div class="dk-h"><h2>Happening now</h2></div>
  <div class="slides" tabindex="0" role="region" aria-label="Happening now">
    <?php foreach($sliderItems as $si): ?>
    <a class="slide" href="<?= h($si['url']) ?>" style="background:linear-gradient(145deg,<?= h($si['color']) ?>,#0B1033)">
      <?php if(!empty($si['img'])): ?><img src="<?= h($si['img']) ?>" alt="" loading="lazy" onerror="this.remove()"><?php endif; ?>
      <span class="type"><?= h($si['type']) ?></span>
      <b><?= h($si['title']) ?></b>
      <span><?= h($si['sub']) ?></span>
    </a>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>

  <!-- App launcher -->
  <?php foreach($groups as $gname => $items): ?>
  <div class="dk-h"><h2><?= h($gname) ?></h2></div>
  <div class="apps glass">
    <?php foreach($items as $m): ?>
    <a class="app" href="<?= url($m[0]) ?>"><span class="appic"><?= app_img($m[5],44) ?></span><?= h($m[1]) ?></a>
    <?php endforeach; ?>
  </div>
  <?php endforeach; ?>

  <?php if($isAdm): ?>
  <div class="dk-h"><h2>Admin</h2></div>
  <div class="apps glass">
    <?php foreach(admin_modules() as $m):
      if ($m[0]==='modules/settings.php' && !isSuperAdmin($user)) continue; ?>
    <a class="app" href="<?= url($m[0]) ?>"><span class="appic"><?= app_img($m[5],44) ?></span><?= h($m[1]) ?>
      <?php if($m[0]==='admin.php' && $pendingCount): ?><span class="badge" aria-label="<?= (int)$pendingCount ?> waiting"><?= (int)$pendingCount ?></span><?php endif; ?></a>
    <?php endforeach; ?>
    <?php if(canPost($user['role'])): ?>
    <button type="button" class="app" onclick="openDashScan()" style="background:none;border:0;cursor:pointer;font-family:inherit;font-size:.75rem;font-weight:600;color:var(--text-2)"><span class="appic"><?= app_img('scan',44) ?></span>Scan QR</button>
    <?php endif; ?>
  </div>
  <?php endif; ?>
 </div>

 <!-- ═══ Light content sheet ═══ -->
 <div class="lt">
  <div class="lt-in">
   <div style="display:grid;gap:1rem">
    <!-- Notice board -->
    <section class="panel" aria-labelledby="nbH">
      <div class="panel-h"><h3 id="nbH"><?= ic('megaphone') ?> Notice board</h3></div>
      <div class="panel-b">
        <?php if(canPost($user['role'])): ?>
        <details class="post">
          <summary><?= ic('plus','ic-sm') ?> Post a notice</summary>
          <form method="POST" style="margin:.4rem 0 .8rem">
            <?php if(function_exists('csrfField')) echo csrfField(); ?>
            <div class="fg"><label class="lbl" for="annTitle">Title</label><input type="text" id="annTitle" name="ann_title" class="inp" required></div>
            <div class="fg"><label class="lbl" for="annBody">Message</label><textarea id="annBody" name="ann_body" class="inp" rows="3" required></textarea></div>
            <div style="display:flex;gap:.6rem;flex-wrap:wrap">
              <select name="ann_cat" class="inp" aria-label="Notice category" style="flex:1;min-width:150px">
                <?php foreach($catConf as $ck=>$cv): ?><option value="<?= $ck ?>"><?= $cv[0] ?></option><?php endforeach; ?>
              </select>
              <button type="submit" name="post_ann" class="btn btn-blue"><?= ic('megaphone','ic-sm') ?> Post</button>
            </div>
          </form>
        </details>
        <?php endif; ?>
        <?php if(isset($_GET['posted'])): ?><div class="alert alert-ok" role="status">Notice posted.</div><?php endif; ?>
        <?php if(empty($notices)): ?>
          <div class="empty">No notices right now.</div>
        <?php else: foreach($notices as $n):
          $cc = isset($catConf[$n['category']??'']) ? $catConf[$n['category']] : $catConf['general'];
          $pr = $n['priority'] ?? 'normal'; ?>
          <article class="note">
            <span class="tile tone-<?= $pr==='emergency'?'rose':($pr==='urgent'?'amber':$cc[2]) ?>"><?= ic($cc[1]) ?></span>
            <div style="min-width:0">
              <b><?= h($n['title']) ?>
                <?php if(!empty($n['is_pinned'])): ?><span class="pill pin">Pinned</span><?php endif; ?>
                <?php if($pr==='urgent'||$pr==='emergency'): ?><span class="pill <?= $pr ?>"><?= ucfirst($pr) ?></span><?php endif; ?></b>
              <p><?= h($n['body']) ?></p>
              <small><?= h($cc[0]) ?> · <?= date('d M Y', strtotime($n['created_at'])) ?></small>
            </div>
          </article>
        <?php endforeach; endif; ?>
      </div>
    </section>

    <!-- Achievements -->
    <?php if(!empty($recentAch)): ?>
    <section class="panel" aria-labelledby="achH">
      <div class="panel-h"><h3 id="achH"><?= ic('trophy') ?> Recent achievements</h3><a href="<?= url('modules/certificate.php') ?>">See all</a></div>
      <div class="panel-b"><div class="ach">
        <?php foreach($recentAch as $ra):
          $aImg=''; if(!empty($ra['image'])) $aImg=(strpos($ra['image'],'/')!==false)?url('assets/uploads/'.$ra['image']):url('assets/uploads/achievements/'.$ra['image']); ?>
        <div class="ach-i">
          <?php if($aImg): ?><img src="<?= h($aImg) ?>" alt="" loading="lazy"><?php else: ?><span class="ph"><?= ic('trophy','ic-lg') ?></span><?php endif; ?>
          <div><b><?= h($ra['title']) ?></b><span><?= h($ra['member_name'] ?? '') ?></span></div>
        </div>
        <?php endforeach; ?>
      </div></div>
    </section>
    <?php endif; ?>

    <!-- Committee -->
    <?php if(!empty($executives) || !empty($committeeMembers)): ?>
    <section class="panel" aria-labelledby="comH">
      <div class="panel-h"><h3 id="comH"><?= ic('users') ?> Committee</h3><a href="<?= url('modules/members.php') ?>">All members</a></div>
      <div class="panel-b"><div class="people">
        <?php foreach(array_merge($executives, $committeeMembers) as $m): $ph = getMemberPhoto($m['profile_photo']); ?>
        <div class="person">
          <?php if($ph): ?><img src="<?= $ph ?>" alt="" loading="lazy"><?php else: ?><span class="ph"><?= ic('user') ?></span><?php endif; ?>
          <b><?= h($m['name']) ?></b><span><?= h(!empty($m['committee_position']) ? $m['committee_position'] : roleLabel($m['role'])) ?></span>
        </div>
        <?php endforeach; ?>
      </div></div>
    </section>
    <?php endif; ?>
   </div>

   <div style="display:grid;gap:1rem">
    <!-- Member card -->
    <a class="mcard" href="<?= url('modules/idcard.php') ?>" aria-label="Open my ID card">
      <div class="row">
        <?php if($myPhoto): ?><img src="<?= $myPhoto ?>" alt=""><?php else: ?><span class="ph"><?= ic('user','ic-lg') ?></span><?php endif; ?>
        <div style="min-width:0"><b><?= h($user['name']) ?></b><br><span style="font-size:.8rem;color:rgba(255,255,255,.8)"><?= h(roleLabel($user['role'])) ?></span></div>
        <span style="margin-left:auto"><?= ic('idcard') ?></span>
      </div>
      <div class="meta">
        <div>Member ID<strong>AV<?= str_pad($user['id'],4,'0',STR_PAD_LEFT) ?></strong></div>
        <div>Blood<strong><?= h($user['blood_group'] ?: '—') ?></strong></div>
        <div>Status<strong><?= h(ucfirst($user['status'] ?? 'active')) ?></strong></div>
      </div>
    </a>

    <!-- Upcoming events -->
    <section class="panel" aria-labelledby="evH">
      <div class="panel-h"><h3 id="evH"><?= ic('calendar') ?> Upcoming events</h3><a href="<?= url('modules/events.php') ?>">View all</a></div>
      <div class="panel-b">
        <?php if(empty($evts)): ?><div class="empty">No upcoming events.</div><?php else: foreach($evts as $ev): ?>
        <div class="ev">
          <div class="date"><?= date('d',strtotime($ev['event_date'])) ?><small><?= date('M',strtotime($ev['event_date'])) ?></small></div>
          <div><b><?= h($ev['title']) ?></b><?php if(!empty($ev['location'])): ?><span><?= h($ev['location']) ?></span><?php endif; ?></div>
        </div>
        <?php endforeach; endif; ?>
      </div>
    </section>
   </div>
  </div>
 </div>
</div>

  <!-- QR Scan Popup (admin only, no widget bar) -->
  <?php if(isAdminRole($user['role']) || canPost($user['role'])): ?>
  <div id="scanPopup" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:9000;flex-direction:column;align-items:center;justify-content:center;padding:1rem">
    <div style="width:100%;max-width:360px;background:#0B1033;border-radius:18px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.5)">
      <div style="background:#0A14E0;padding:.9rem 1.1rem;display:flex;align-items:center;justify-content:space-between">
        <div style="font-weight:800;font-size:.95rem;color:#fff">Scan volunteer QR</div>
        <button type="button" onclick="closeDashScan()" aria-label="Close scanner" style="background:rgba(255,255,255,.15);border:none;color:#fff;width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:1rem;display:flex;align-items:center;justify-content:center">✕</button>
      </div>
      <div style="position:relative;background:#000;width:100%">
        <video id="dashVideo" style="width:100%;display:block;max-height:280px;object-fit:cover" autoplay playsinline muted></video>
        <canvas id="dashCanvas" style="display:none"></canvas>
        <div id="dashFrame" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none">
          <div style="width:200px;height:200px;position:relative">
            <div style="position:absolute;top:0;left:0;width:28px;height:28px;border-top:3px solid #A9B0FF;border-left:3px solid #A9B0FF;border-radius:3px 0 0 0"></div>
            <div style="position:absolute;top:0;right:0;width:28px;height:28px;border-top:3px solid #A9B0FF;border-right:3px solid #A9B0FF;border-radius:0 3px 0 0"></div>
            <div style="position:absolute;bottom:0;left:0;width:28px;height:28px;border-bottom:3px solid #A9B0FF;border-left:3px solid #A9B0FF;border-radius:0 0 0 3px"></div>
            <div style="position:absolute;bottom:0;right:0;width:28px;height:28px;border-bottom:3px solid #A9B0FF;border-right:3px solid #A9B0FF;border-radius:0 0 3px 0"></div>
            <div style="position:absolute;left:8px;right:8px;height:2px;background:linear-gradient(90deg,transparent,#A9B0FF,transparent);animation:scanAnim 1.8s ease-in-out infinite;top:50%"></div>
          </div>
          <div style="position:absolute;bottom:12px;left:50%;transform:translateX(-50%);color:#A9B0FF;font-size:.68rem;font-weight:700;letter-spacing:.1em;white-space:nowrap">POINT AT QR CODE</div>
        </div>
      </div>
      <div id="dashResult" style="padding:.85rem 1rem;min-height:60px">
        <p style="color:rgba(255,255,255,.75);font-size:.8rem;text-align:center">Position the QR code inside the frame</p>
      </div>
      <div style="padding:0 1rem .9rem">
        <div style="font-size:.65rem;color:rgba(255,255,255,.65);text-align:center;margin-bottom:.4rem">— or paste token —</div>
        <input type="text" id="dashTokenInput" placeholder="Paste QR token here" style="width:100%;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);border-radius:8px;padding:.58rem .85rem;font-family:Inter,sans-serif;font-size:.85rem;color:#fff;outline:none;text-align:center" oninput="dashVerifyToken(this.value)">
      </div>
    </div>
  </div>
  <?php endif; ?>

<script>
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


var _sp=document.getElementById('scanPopup');
if (_sp) { _sp.addEventListener('click',function(e){ if(e.target===this) closeDashScan(); }); }
document.addEventListener('keydown',function(e){ if(e.key==='Escape' && typeof closeDashScan==='function') closeDashScan(); });
</script>
<?php require_once __DIR__.'/includes/footer.php'; ?>
