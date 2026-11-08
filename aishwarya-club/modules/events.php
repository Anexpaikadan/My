<?php
require_once __DIR__.'/../includes/config.php';
require_once __DIR__.'/../includes/wa_gateway.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '📅 Events — Aishwarya Arts & Sports Club',
  'desc'  => 'Upcoming events and programs — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/events.php',
];
requireLogin();
$user = currentUser();
$isAdmin = isAdminRole($user['role']) || isModuleAdmin('events', $user);
$uid = (int)$user['id'];
$pageTitle = 'Events — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');

// RSVP table
try {
  db()->exec("CREATE TABLE IF NOT EXISTS event_rsvps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    response ENUM('going','maybe','no') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_rsvp (event_id,user_id),
    INDEX idx_ev (event_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (Exception $e) {}

// RSVP submit (AJAX)
if (isset($_POST['ax']) && $_POST['ax']==='rsvp') {
  header('Content-Type: application/json');
  $eid = (int)($_POST['event_id'] ?? 0);
  $resp = $_POST['response'] ?? '';
  if (!$eid || !in_array($resp,['going','maybe','no'])) { echo json_encode(['ok'=>false]); exit; }
  db()->prepare("INSERT INTO event_rsvps(event_id,user_id,response) VALUES(?,?,?)
    ON DUPLICATE KEY UPDATE response=VALUES(response)")->execute([$eid,$uid,$resp]);
  // counts
  $c = db()->prepare("SELECT response,COUNT(*) n FROM event_rsvps WHERE event_id=? GROUP BY response");
  $c->execute([$eid]); $counts=['going'=>0,'maybe'=>0,'no'=>0];
  foreach($c->fetchAll() as $r){ $counts[$r['response']]=(int)$r['n']; }
  echo json_encode(['ok'=>true,'counts'=>$counts,'mine'=>$resp]); exit;
}

// Helper: get RSVP data for an event
function ev_rsvp_data($eid,$uid){
  $c = db()->prepare("SELECT response,COUNT(*) n FROM event_rsvps WHERE event_id=? GROUP BY response");
  $c->execute([$eid]); $counts=['going'=>0,'maybe'=>0,'no'=>0];
  foreach($c->fetchAll() as $r){ $counts[$r['response']]=(int)$r['n']; }
  $m = db()->prepare("SELECT response FROM event_rsvps WHERE event_id=? AND user_id=?");
  $m->execute([$eid,$uid]); $mine = $m->fetchColumn();
  return ['counts'=>$counts,'mine'=>$mine ?: ''];
}

// Delete event (admin)
if ($isAdmin && isset($_POST['del_event'])) { require_once __DIR__ . '/../includes/sudo.php'; sudo_require(); 
    db()->prepare("DELETE FROM events WHERE id=?")->execute([(int)$_POST['eid']]);
    header('Location:'.url('modules/events.php').'?msg=deleted'); exit;
}

// Create event (admin or events module-admin) — AJAX
if ($isAdmin && isset($_POST['ajax']) && $_POST['ajax']==='add_event') {
    header('Content-Type: application/json');
    $t = trim($_POST['title'] ?? '');
    $dt= $_POST['edate'] ?? '';
    if (!$t || !$dt) { echo json_encode(['ok'=>false,'msg'=>'Title and date required']); exit; }
    try {
        db()->prepare("INSERT INTO events(title,description,event_type,event_date,event_time,location,created_by) VALUES(?,?,?,?,?,?,?)")
          ->execute([$t, trim($_POST['descr']??''), $_POST['etype']??'other', $dt, (($_POST['etime'] ?? '') ?: null), trim($_POST['eloc']??''), $uid]);
        $waN = 0;
        if (wa_feature_on('events')) {
            $waN = wa_queue_many(db()->query("SELECT whatsapp_number FROM users WHERE status='active' AND whatsapp_number<>''")->fetchAll(), wa_msg_event(array('title'=>$t,'description'=>trim($_POST['descr']??''),'event_date'=>$dt,'event_time'=>$_POST['etime']??'','location'=>trim($_POST['eloc']??''))), 'event');
        }
        echo json_encode(['ok'=>true,'msg'=>'✅ Event created!'.($waN?' WhatsApp announcement queued for '.$waN.' members.':'')]); exit;
    } catch (Exception $e) { echo json_encode(['ok'=>false,'msg'=>'Error: '.$e->getMessage()]); exit; }
}

$ft  = $_GET['type'] ?? '';
$msg = $_GET['msg']  ?? '';
$q   = "SELECT e.*,u.name creator FROM events e JOIN users u ON u.id=e.created_by";
$p   = [];
if ($ft) { $q .= " WHERE e.event_type=?"; $p[] = $ft; }
$q .= " ORDER BY e.event_date DESC";
$stmt = db()->prepare($q); $stmt->execute($p); $events = $stmt->fetchAll();

$upcoming = array_values(array_filter($events, function($e){ return strtotime($e['event_date']) >= strtotime('today'); }));
$past     = array_values(array_filter($events, function($e){ return strtotime($e['event_date']) <  strtotime('today'); }));

// Type config
$types = [
  ''          => ['em'=>'✨','label'=>'All',      'color'=>'#0A14E0','bg'=>'#ECEEFF'],
  'football'  => ['em'=>'⚽','label'=>'Football', 'color'=>'#1b5e20','bg'=>'#e8f5e9'],
  'cricket'   => ['em'=>'🏏','label'=>'Cricket',  'color'=>'#e65100','bg'=>'#fff3e0'],
  'charity'   => ['em'=>'🤝','label'=>'Charity',  'color'=>'#880e4f','bg'=>'#fce4ec'],
  'cultural'  => ['em'=>'🎭','label'=>'Cultural', 'color'=>'#6a1b9a','bg'=>'#f3e5f5'],
  'meeting'   => ['em'=>'📋','label'=>'Meeting',  'color'=>'#37474f','bg'=>'#eceff1'],
];

require_once __DIR__.'/../includes/header.php';
?>
<style>
/* ══ EVENTS APP ══════════════════════════════════════════ */
.ev-shell{background:#F5F7FF;min-height:100vh;padding-bottom:5rem}

/* Header */
.ev-header{
  background:linear-gradient(145deg,#0B1033,#121A5C,#0A14E0);
  padding:1.4rem 1.2rem 3.2rem;position:relative;overflow:hidden}
.ev-header::before{content:'📅';position:absolute;right:-1rem;top:-1rem;font-size:9rem;opacity:.07}
.ev-htitle{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.52rem;letter-spacing:.01em;color:#fff}
.ev-htitle span{color:#B9BFFF;font-family:'Plus Jakarta Sans',sans-serif;font-size:.82rem;font-weight:600;
  letter-spacing:.04em;display:block;margin-top:.2rem}
.ev-hstats{display:flex;gap:.55rem;margin-top:1rem}
.ev-hstat{background:rgba(255,255,255,.14);backdrop-filter:blur(8px);
  border:1px solid rgba(255,255,255,.2);border-radius:12px;
  padding:.5rem .8rem;text-align:center;flex:1}
.ev-hstat-n{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.2rem;color:#fff;line-height:1}
.ev-hstat-l{font-size:.75rem;color:rgba(255,255,255,.6);text-transform:uppercase;letter-spacing:.09em;font-weight:700}

/* Filter pills */
.ev-filters{background:#fff;border-radius:20px 20px 0 0;margin-top:-1.8rem;
  position:relative;z-index:2;padding:1rem 1rem .6rem;
  box-shadow:0 -4px 20px rgba(0,0,0,.08)}
.ev-filter-row{display:flex;gap:.4rem;overflow-x:auto;scrollbar-width:none;padding-bottom:.2rem}
.ev-filter-row::-webkit-scrollbar{display:none}
.ev-pill{display:inline-flex;align-items:center;gap:.28rem;padding:.42rem .9rem;
  border-radius:20px;border:1.5px solid #ECEEFF;background:#f8fafc;
  color:#475569;font-size:.75rem;font-weight:700;text-decoration:none;
  white-space:nowrap;transition:all .22s;flex-shrink:0}
.ev-pill:active{transform:scale(.93)}
.ev-pill.on{color:#fff;border-color:transparent;box-shadow:0 3px 12px rgba(0,0,0,.18)}

/* Section label */
.ev-sec{padding:.9rem 1rem .45rem;display:flex;align-items:center;gap:.6rem}
.ev-sec-title{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.88rem;letter-spacing:.01em;color:#0B1033}
.ev-sec-line{flex:1;height:2px;background:linear-gradient(90deg,#c8922a,transparent);border-radius:2px}
.ev-sec-count{font-size:.75rem;font-weight:700;color:#5d6b80;background:#F5F7FF;
  border-radius:20px;padding:.1rem .55rem}

/* Event cards */
.ev-cards{padding:0 1rem;display:flex;flex-direction:column;gap:.7rem}
.ev-card{background:#fff;border-radius:18px;overflow:hidden;
  box-shadow:0 3px 14px rgba(0,0,0,.08);position:relative;
  transition:all .25s;-webkit-tap-highlight-color:transparent;
  animation:evSlideIn .4s ease both}
.ev-card:active{transform:scale(.98)}
@keyframes evSlideIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.ev-card:nth-child(1){animation-delay:.05s}
.ev-card:nth-child(2){animation-delay:.1s}
.ev-card:nth-child(3){animation-delay:.15s}
.ev-card:nth-child(4){animation-delay:.2s}
.ev-card:nth-child(5){animation-delay:.25s}

.ev-card-top{height:7px}
.ev-card-body{padding:.9rem 1rem}
.ev-card-row1{display:flex;align-items:center;justify-content:space-between;margin-bottom:.55rem}
.ev-type-pill{display:inline-flex;align-items:center;gap:.28rem;font-size:.75rem;
  font-weight:800;border-radius:20px;padding:.12rem .6rem;letter-spacing:.04em}
.ev-countdown{font-size:.75rem;font-weight:800;display:inline-flex;align-items:center;gap:.25rem}
.ev-countdown.today{color:#b71c1c;animation:pulseFade 1.5s ease-in-out infinite}
.ev-countdown.soon{color:#e65100}
.ev-countdown.normal{color:#64748b}
@keyframes pulseFade{0%,100%{opacity:1}50%{opacity:.5}}
.ev-title{font-family:'Playfair Display',serif;font-size:1.05rem;font-weight:700;
  color:#0B1033;line-height:1.3;margin-bottom:.4rem}
.ev-desc{font-size:.8rem;color:#64748b;line-height:1.55;margin-bottom:.6rem;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ev-meta{display:flex;flex-direction:column;gap:.22rem}
.ev-meta-row{display:flex;align-items:center;gap:.4rem;font-size:.75rem;color:#64748b}
.ev-meta-icon{width:20px;height:20px;border-radius:6px;display:flex;align-items:center;
  justify-content:center;font-size:.75rem;flex-shrink:0;background:#F5F7FF}

/* Admin actions */
.ev-admin-bar{border-top:1px solid #F5F7FF;padding:.6rem 1rem;
  display:flex;justify-content:flex-end;gap:.4rem}
.ev-del-btn{background:#fff5f5;border:1.5px solid #fecaca;color:#b71c1c;
  border-radius:8px;padding:.3rem .75rem;font-size:.75rem;font-weight:700;cursor:pointer;
  display:inline-flex;align-items:center;gap:.3rem;transition:all .2s}
.ev-del-btn:hover{background:#ffebee}

/* Past events */
.ev-past{padding:0 1rem}
.ev-past-row{background:#F1F3F9;border-radius:12px;padding:.72rem .9rem;
  margin-bottom:.45rem;display:grid;grid-template-columns:1fr auto;
  gap:.5rem;align-items:center;box-shadow:0 1px 6px rgba(0,0,0,.05)}
.ev-past-title{font-weight:700;font-size:.85rem;color:#0B1033;margin-bottom:.18rem}
.ev-past-meta{font-size:.75rem;color:#5d6b80;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}
.ev-past-date{font-size:.75rem;font-weight:700;color:#475569;text-align:right}

/* Empty state */
.ev-empty{text-align:center;padding:3rem 1.5rem;background:#fff;
  border-radius:16px;margin:0 1rem}

/* Add FAB */
.ev-fab{position:fixed;bottom:calc(74px + env(safe-area-inset-bottom,0px));right:1.1rem;z-index:900;
  background:linear-gradient(135deg,#0A14E0,#1A23C9);
  color:#fff;height:50px;padding:0 1.2rem 0 1rem;border-radius:26px;
  display:flex;align-items:center;justify-content:center;gap:.45rem;font-size:.88rem;font-weight:800;
  font-family:'Plus Jakarta Sans',sans-serif;letter-spacing:.01em;
  text-decoration:none;box-shadow:0 8px 24px rgba(10,20,224,.45);
  transition:all .22s;animation:fabIn .4s ease}
.ev-fab .fab-plus{font-size:1.3rem;line-height:1;margin-top:-1px}
.ev-fab:active{transform:scale(.93)}
@keyframes fabIn{from{opacity:0;transform:translateY(20px) scale(.8)}to{opacity:1;transform:translateY(0) scale(1)}}
.ev-rsvp{border-top:1px solid #F5F7FF;margin-top:.7rem;padding-top:.7rem}
.ev-rsvp-q{font-size:.75rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.45rem}
.ev-rsvp-btns{display:flex;gap:.4rem}
.ev-rsvp-b{flex:1;display:flex;flex-direction:column;align-items:center;gap:.1rem;padding:.5rem .2rem;border:1.5px solid #E3E7F5;background:#fff;border-radius:11px;font-family:inherit;font-size:.75rem;font-weight:800;color:#64748b;cursor:pointer;transition:all .15s}
.ev-rsvp-b .rc{font-size:.75rem;opacity:.7;min-height:.7rem}
.ev-rsvp-b:active{transform:scale(.94)}
.ev-rsvp-b.going.on{background:#e8f5e9;border-color:#66bb6a;color:#1b5e20}
.ev-rsvp-b.maybe.on{background:#fff8e1;border-color:#ffca28;color:#e65100}
.ev-rsvp-b.no.on{background:#ffebee;border-color:#ef9a9a;color:#b71c1c}
.ev-rsvp-admin{margin-top:.5rem;font-size:.75rem;color:#556274;background:#F7F8FF;border-radius:8px;padding:.4rem .6rem}
</style>

<div class="ev-shell">
<?php if($isAdmin): ?>
<div style="padding:.8rem 1rem 0">
  <button onclick="evOpenCreate()" style="width:100%;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;border:none;border-radius:12px;padding:.8rem;font-size:.9rem;font-weight:800;cursor:pointer;font-family:inherit;box-shadow:0 4px 14px rgba(10,20,224,.3)">➕ Create New Event</button>
</div>
<?php endif; ?>

<!-- Header -->
<div class="ev-header">
  <div class="ev-htitle">
    📅 Club Events
    <span><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?> · <?= h(setting('CLUB_PLACE','Vettikkattiri')) ?></span>
  </div>
  <div class="ev-hstats">
    <div class="ev-hstat">
      <div class="ev-hstat-n"><?= count($upcoming) ?></div>
      <div class="ev-hstat-l">Upcoming</div>
    </div>
    <div class="ev-hstat">
      <div class="ev-hstat-n" style="color:#ffcc80"><?= count($past) ?></div>
      <div class="ev-hstat-l">Past</div>
    </div>
    <div class="ev-hstat">
      <div class="ev-hstat-n" style="color:#a5d6a7"><?= count($events) ?></div>
      <div class="ev-hstat-l">Total</div>
    </div>
  </div>
</div>

<!-- Filter pills -->
<div class="ev-filters">
  <div class="ev-filter-row">
    <?php foreach($types as $tv=>$ti): ?>
    <a href="<?= url('modules/events.php') ?>?type=<?= urlencode($tv) ?>"
       class="ev-pill <?= $ft===$tv?'on':'' ?>"
       style="<?= $ft===$tv?'background:'.$ti['color'].';' : '' ?>">
      <?= $ti['em'] ?> <?= $ti['label'] ?>
    </a>
    <?php endforeach; ?>
  </div>
</div>

<?php if($msg==='deleted'): ?>
<div style="margin:.7rem 1rem;background:#e8f5e9;border:1.5px solid #a5d6a7;
     color:#1b5e20;border-radius:12px;padding:.7rem 1rem;font-weight:700;font-size:.84rem">
  🗑 Event deleted successfully.
</div>
<?php endif; ?>

<!-- Upcoming -->
<div class="ev-sec">
  <span style="font-size:1.1rem">🔥</span>
  <div class="ev-sec-title">Upcoming</div>
  <div class="ev-sec-line"></div>
  <div class="ev-sec-count"><?= count($upcoming) ?></div>
</div>

<?php if(empty($upcoming)): ?>
<div class="ev-empty">
  <div style="font-size:3rem;margin-bottom:.6rem">📅</div>
  <div style="font-weight:700;color:#475569;margin-bottom:.3rem">No upcoming events</div>
  <div style="font-size:.8rem;color:#5d6b80">Stay tuned for announcements</div>
</div>
<?php else: ?>
<div class="ev-cards">
<?php foreach($upcoming as $idx=>$ev):
  $diff  = ceil((strtotime($ev['event_date']) - time()) / 86400);
  $ti    = $types[$ev['event_type']] ?? $types[''];
  $cdClass = $diff===0 ? 'today' : ($diff<=3 ? 'soon' : 'normal');
  $cdTxt   = $diff===0 ? '🔥 Today' : ($diff===1 ? '⚡ Tomorrow' : "In {$diff}d");
?>
<div class="ev-card" style="animation-delay:<?= $idx*0.07 ?>s">
  <div class="ev-card-top" style="background:<?= $ti['color'] ?>"></div>
  <div class="ev-card-body">
    <!-- Row 1: type + countdown -->
    <div class="ev-card-row1">
      <span class="ev-type-pill" style="background:<?= $ti['bg'] ?>;color:<?= $ti['color'] ?>">
        <?= $ti['em'] ?> <?= h(ucfirst($ev['event_type'])) ?>
      </span>
      <span class="ev-countdown <?= $cdClass ?>">
        <?= $cdTxt ?>
      </span>
    </div>
    <!-- Title -->
    <div class="ev-title"><?= h($ev['title']) ?></div>
    <!-- Description -->
    <?php if($ev['description']): ?>
    <div class="ev-desc"><?= h($ev['description']) ?></div>
    <?php endif; ?>
    <!-- Meta -->
    <div class="ev-meta">
      <div class="ev-meta-row">
        <div class="ev-meta-icon">📅</div>
        <span><?= date('d M Y (l)', strtotime($ev['event_date'])) ?>
          <?php if($ev['event_time']): ?> · <?= date('g:i A', strtotime($ev['event_time'])) ?><?php endif; ?>
        </span>
      </div>
      <?php if($ev['location']): ?>
      <div class="ev-meta-row">
        <div class="ev-meta-icon">📍</div>
        <span><?= h($ev['location']) ?></span>
      </div>
      <?php endif; ?>
      <?php if($ev['creator']): ?>
      <div class="ev-meta-row">
        <div class="ev-meta-icon">👤</div>
        <span>By <?= h($ev['creator']) ?></span>
      </div>
      <?php endif; ?>
    </div>

    <!-- RSVP -->
    <?php $rd = ev_rsvp_data($ev['id'],$uid); ?>
    <div class="ev-rsvp" data-eid="<?= $ev['id'] ?>">
      <div class="ev-rsvp-q">Are you coming?</div>
      <div class="ev-rsvp-btns">
        <button class="ev-rsvp-b going<?= $rd['mine']==='going'?' on':'' ?>" onclick="doRsvp(<?= $ev['id'] ?>,'going',this)">✅ Going <span class="rc"><?= $rd['counts']['going'] ?: '' ?></span></button>
        <button class="ev-rsvp-b maybe<?= $rd['mine']==='maybe'?' on':'' ?>" onclick="doRsvp(<?= $ev['id'] ?>,'maybe',this)">🤔 Maybe <span class="rc"><?= $rd['counts']['maybe'] ?: '' ?></span></button>
        <button class="ev-rsvp-b no<?= $rd['mine']==='no'?' on':'' ?>" onclick="doRsvp(<?= $ev['id'] ?>,'no',this)">❌ Can't <span class="rc"><?= $rd['counts']['no'] ?: '' ?></span></button>
      </div>
      <?php if($isAdmin): ?>
      <div class="ev-rsvp-admin">👥 <b class="goingN"><?= $rd['counts']['going'] ?></b> going · <span class="maybeN"><?= $rd['counts']['maybe'] ?></span> maybe</div>
      <?php endif; ?>
    </div>
  </div>
  <?php if($isAdmin): ?>
  <div class="ev-admin-bar">
    <form method="POST" data-confirm="Delete this event?" data-sudo>
      <input type="hidden" name="eid" value="<?= $ev['id'] ?>">
      <button type="submit" name="del_event" class="ev-del-btn">
        🗑 Remove
      </button>
    </form>
  </div>
  <?php endif; ?>
</div>
<?php endforeach; ?>
</div>
<?php endif; ?>

<!-- Past Events -->
<?php if(!empty($past)): ?>
<div class="ev-sec" style="margin-top:.8rem">
  <span style="font-size:1rem">⏱</span>
  <div class="ev-sec-title" style="opacity:.7">Past Events</div>
  <div class="ev-sec-line"></div>
  <div class="ev-sec-count"><?= count($past) ?></div>
</div>
<div class="ev-past">
  <?php foreach($past as $ev):
    $ti = $types[$ev['event_type']] ?? $types[''];
  ?>
  <div class="ev-past-row">
    <div>
      <div class="ev-past-title"><?= h($ev['title']) ?></div>
      <div class="ev-past-meta">
        <span style="background:<?= $ti['bg'] ?>;color:<?= $ti['color'] ?>;
              border-radius:20px;padding:.06rem .5rem;font-size:.75rem;font-weight:700">
          <?= $ti['em'] ?> <?= h(ucfirst($ev['event_type'])) ?>
        </span>
        <?php if($ev['location']): ?>
        <span>📍 <?= h($ev['location']) ?></span>
        <?php endif; ?>
      </div>
    </div>
    <div>
      <div class="ev-past-date"><?= date('d M', strtotime($ev['event_date'])) ?></div>
      <div style="font-size:.75rem;color:#5d6b80;text-align:right"><?= date('Y', strtotime($ev['event_date'])) ?></div>
      <?php if($isAdmin): ?>
      <form method="POST" style="margin-top:.3rem" data-confirm="Delete?" data-sudo>
        <input type="hidden" name="eid" value="<?= $ev['id'] ?>">
        <button type="submit" name="del_event"
          style="background:#fff5f5;border:1px solid #fecaca;color:#b71c1c;
                 border-radius:6px;padding:.18rem .45rem;font-size:.75rem;font-weight:700;cursor:pointer">
          🗑
        </button>
      </form>
      <?php endif; ?>
    </div>
  </div>
  <?php endforeach; ?>
</div>
<?php endif; ?>

</div><!-- /ev-shell -->

<!-- Add Event FAB (admin) -->
<?php if($isAdmin): ?>
<button class="ev-fab" onclick="evOpenCreate()"><span class="fab-plus">＋</span> New Event</button>

<!-- Create Event modal -->
<div id="evOv" onclick="if(event.target===this)evCloseCreate()" style="display:none;position:fixed;inset:0;background:rgba(13,27,62,.6);z-index:10000;align-items:flex-end;justify-content:center">
  <div style="background:#fff;width:100%;max-width:480px;border-radius:22px 22px 0 0;padding:1.2rem 1.2rem 1.6rem;animation:evSlide .3s ease">
    <h3 style="font-size:1.1rem;color:#0B1033;margin-bottom:.9rem">➕ New Event</h3>
    <input type="text" id="evTitle" placeholder="Event title *" style="width:100%;padding:.7rem .8rem;border:1.5px solid #E3E7F5;border-radius:11px;font-size:16px;box-sizing:border-box;margin-bottom:.55rem;font-family:inherit">
    <select id="evType" style="width:100%;padding:.7rem .8rem;border:1.5px solid #E3E7F5;border-radius:11px;font-size:16px;box-sizing:border-box;margin-bottom:.55rem;font-family:inherit">
      <option value="football">⚽ Football</option><option value="cricket">🏏 Cricket</option><option value="kabaddi">🤼 Kabaddi</option>
      <option value="charity">🤝 Charity</option><option value="cultural">🎭 Cultural</option><option value="meeting">📋 Meeting</option><option value="other">📌 Other</option>
    </select>
    <div style="display:flex;gap:.5rem">
      <input type="date" id="evDate" value="<?= date('Y-m-d') ?>" style="flex:1;padding:.7rem .8rem;border:1.5px solid #E3E7F5;border-radius:11px;font-size:.9rem;box-sizing:border-box;margin-bottom:.55rem;font-family:inherit">
      <input type="time" id="evTime" style="flex:1;padding:.7rem .8rem;border:1.5px solid #E3E7F5;border-radius:11px;font-size:16px;box-sizing:border-box;margin-bottom:.55rem;font-family:inherit">
    </div>
    <input type="text" id="evLoc" placeholder="Location" style="width:100%;padding:.7rem .8rem;border:1.5px solid #E3E7F5;border-radius:11px;font-size:16px;box-sizing:border-box;margin-bottom:.55rem;font-family:inherit">
    <textarea id="evDescr" rows="2" placeholder="Description (optional)" style="width:100%;padding:.7rem .8rem;border:1.5px solid #E3E7F5;border-radius:11px;font-size:16px;box-sizing:border-box;margin-bottom:.7rem;font-family:inherit;resize:none"></textarea>
    <div style="display:flex;gap:.5rem">
      <button onclick="evSaveCreate()" style="flex:1;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;border:none;border-radius:11px;padding:.75rem;font-weight:800;cursor:pointer">Create Event</button>
      <button onclick="evCloseCreate()" style="background:#eceff1;color:#546e7a;border:none;border-radius:11px;padding:.75rem 1.1rem;font-weight:700;cursor:pointer">Cancel</button>
    </div>
  </div>
</div>
<style>@keyframes evSlide{from{transform:translateY(100%)}to{transform:translateY(0)}}</style>
<?php endif; ?>

<script>
var EV_SELF = <?= json_encode(url('modules/events.php')) ?>;
var EV_ADMIN = <?= $isAdmin ? 'true':'false' ?>;
function evOpenCreate(){var o=document.getElementById('evOv');if(o){o.style.display='flex';document.body.style.overflow='hidden';}}
function evCloseCreate(){var o=document.getElementById('evOv');if(o){o.style.display='none';document.body.style.overflow='';}}
function evSaveCreate(){
  var t=document.getElementById('evTitle').value.trim();
  var d=document.getElementById('evDate').value;
  if(!t||!d){alert('Title and date are required');return;}
  var fd=new URLSearchParams({ajax:'add_event',title:t,etype:document.getElementById('evType').value,edate:d,etime:document.getElementById('evTime').value,eloc:document.getElementById('evLoc').value,descr:document.getElementById('evDescr').value});
  fetch(EV_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){evCloseCreate();location.reload();}else alert(res.msg||'Error');
  }).catch(function(){alert('Error creating event');});
}
function doRsvp(eid, resp, btn){
  var wrap = btn.closest('.ev-rsvp');
  fetch(EV_SELF,{method:'POST',body:new URLSearchParams({ax:'rsvp',event_id:eid,response:resp})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok)return;
      // update button states
      wrap.querySelectorAll('.ev-rsvp-b').forEach(function(b){b.classList.remove('on');});
      btn.classList.add('on');
      // update counts
      wrap.querySelector('.ev-rsvp-b.going .rc').textContent = res.counts.going||'';
      wrap.querySelector('.ev-rsvp-b.maybe .rc').textContent = res.counts.maybe||'';
      wrap.querySelector('.ev-rsvp-b.no .rc').textContent = res.counts.no||'';
      if(EV_ADMIN){
        var g=wrap.querySelector('.goingN'), m=wrap.querySelector('.maybeN');
        if(g)g.textContent=res.counts.going; if(m)m.textContent=res.counts.maybe;
      }
    });
}
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
