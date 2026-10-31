<?php
ini_set('display_errors', 0);
error_reporting(E_ALL);

$configFile = __DIR__ . '/../includes/config.php';
if (!file_exists($configFile)) { die("Config missing"); }
require_once $configFile;

if (!function_exists('db'))         { die("db() missing"); }
if (!function_exists('requireLogin'))  { function requireLogin() { return true; } }
if (!function_exists('currentUser'))   { function currentUser() { return ['id'=>1,'name'=>'User','role'=>'user']; } }
if (!function_exists('isAdminRole'))   { function isAdminRole($r) { return false; } }
if (!function_exists('setting'))       { function setting($k,$d='') { return $d; } }
if (!function_exists('url'))           { function url($p) { return '/'.ltrim($p,'/'); } }
if (!function_exists('h'))             { function h($s) { return htmlspecialchars($s??'',ENT_QUOTES,'UTF-8'); } }

requireLogin();
$me      = currentUser();
// Module admin: Cultural Committee + Secretary + Developer
$isAdmin = isCulturalAdmin($me['role'] ?? '');
$uid     = (int)($me['id'] ?? 0);
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$PLACE   = setting('CLUB_PLACE','Vettikkattiri');
$SITE    = defined('SITE_URL') ? rtrim(SITE_URL,'/') : '';

// ── Tables ──────────────────────────────────────────────────
try { db()->exec("CREATE TABLE IF NOT EXISTS henna_fests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL DEFAULT 'Henna Fest',
  description TEXT DEFAULT '',
  poster_path VARCHAR(500) DEFAULT '',
  prize_1 VARCHAR(300) DEFAULT '',
  prize_2 VARCHAR(300) DEFAULT '',
  prize_3 VARCHAR(300) DEFAULT '',
  sponsor_name VARCHAR(200) DEFAULT '',
  join_link VARCHAR(500) DEFAULT '',
  voting_open TINYINT(1) DEFAULT 0,
  vote_start DATETIME DEFAULT NULL,
  vote_end DATETIME DEFAULT NULL,
  likes_per_member TINYINT DEFAULT 3,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS henna_entries (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fest_id INT NOT NULL DEFAULT 1,
  member_id INT NOT NULL,
  title VARCHAR(200) DEFAULT '',
  image_path VARCHAR(500) NOT NULL,
  og_path VARCHAR(500) DEFAULT '',
  vote_count INT DEFAULT 0,
  status ENUM('active','hidden') DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

// votes table — NO unique constraint on voter so 3 likes allowed
// unique on (fest_id, voter_id, entry_id) so same entry can't be liked twice
try { db()->exec("CREATE TABLE IF NOT EXISTS henna_votes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fest_id INT NOT NULL DEFAULT 1,
  voter_id INT NOT NULL,
  entry_id INT NOT NULL,
  voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY one_per_entry (fest_id, voter_id, entry_id)
)"); } catch(Exception $e){}

// Safe schema migrations
try {
  if (!db()->query("SHOW COLUMNS FROM henna_votes LIKE 'fest_id'")->fetch())
    db()->exec("ALTER TABLE henna_votes ADD COLUMN fest_id INT NOT NULL DEFAULT 1 AFTER id");
} catch(Exception $e){}
try {
  if (!db()->query("SHOW COLUMNS FROM henna_entries LIKE 'fest_id'")->fetch())
    db()->exec("ALTER TABLE henna_entries ADD COLUMN fest_id INT NOT NULL DEFAULT 1 AFTER id");
} catch(Exception $e){}
try {
  if (!db()->query("SHOW COLUMNS FROM henna_entries LIKE 'og_path'")->fetch())
    db()->exec("ALTER TABLE henna_entries ADD COLUMN og_path VARCHAR(500) DEFAULT '' AFTER image_path");
} catch(Exception $e){}
try {
  if (!db()->query("SHOW COLUMNS FROM henna_fests LIKE 'likes_per_member'")->fetch())
    db()->exec("ALTER TABLE henna_fests ADD COLUMN likes_per_member TINYINT DEFAULT 3");
} catch(Exception $e){}

// FIX: Drop any unique key that would block multiple likes per member
// Find and drop every unique index on henna_votes that does NOT include entry_id
try {
  $allKeys = db()->query("SHOW INDEX FROM henna_votes WHERE Non_unique=0")->fetchAll();
  $keyNames = [];
  foreach ($allKeys as $k) { $keyNames[$k['Key_name']][] = $k['Column_name']; }
  foreach ($keyNames as $kname => $cols) {
    if ($kname === 'PRIMARY') continue;
    // If this unique key does NOT include entry_id, it's the old blocking key — drop it
    if (!in_array('entry_id', $cols)) {
      try { db()->exec("ALTER TABLE henna_votes DROP INDEX `{$kname}`"); } catch(Exception $e2){}
    }
  }
} catch(Exception $e){}
// Add correct unique key if missing
try {
  $check = db()->query("SHOW INDEX FROM henna_votes WHERE Key_name='one_per_entry'")->fetchAll();
  if (empty($check)) {
    db()->exec("ALTER TABLE henna_votes ADD UNIQUE KEY one_per_entry (fest_id, voter_id, entry_id)");
  }
} catch(Exception $e){}

// Seed
try {
  if (!db()->query("SELECT COUNT(*) FROM henna_fests")->fetchColumn()) {
    try {
      $old = db()->query("SELECT * FROM henna_fest_settings LIMIT 1")->fetch();
      if ($old) {
        db()->prepare("INSERT INTO henna_fests(title,prize_1,prize_2,prize_3,join_link,poster_path,voting_open) VALUES(?,?,?,?,?,?,?)")
           ->execute([$old['event_title']??'Henna Fest',$old['prize_1']??'',$old['prize_2']??'',$old['prize_3']??'',$old['join_link']??'',$old['event_poster']??'',$old['voting_open']??0]);
      } else {
        db()->exec("INSERT INTO henna_fests(title) VALUES('Henna Fest 2026')");
      }
    } catch(Exception $e2) {
      db()->exec("INSERT INTO henna_fests(title) VALUES('Henna Fest 2026')");
    }
  }
} catch(Exception $e){}

// Load fest
$festId   = (int)($_GET['fest'] ?? 0);
$allFests = [];
try { $allFests = db()->query("SELECT * FROM henna_fests ORDER BY created_at DESC")->fetchAll(); } catch(Exception $e){}
if (!$festId && !empty($allFests)) $festId = (int)$allFests[0]['id'];
$fest = null;
foreach ($allFests as $f) { if ((int)$f['id']===$festId) { $fest=$f; break; } }
if (!$fest && !empty($allFests)) { $fest=$allFests[0]; $festId=(int)$fest['id']; }

// Auto schedule
if ($fest && !empty($fest['vote_start']) && !empty($fest['vote_end'])) {
  $now = date('Y-m-d H:i:s');
  if ($now>=$fest['vote_start'] && $now<=$fest['vote_end'] && !$fest['voting_open']) {
    db()->prepare("UPDATE henna_fests SET voting_open=1 WHERE id=?")->execute([$festId]);
    $fest['voting_open']=1;
  } elseif ($now>$fest['vote_end'] && $fest['voting_open']) {
    db()->prepare("UPDATE henna_fests SET voting_open=0 WHERE id=?")->execute([$festId]);
    $fest['voting_open']=0;
  }
}

$votingOpen      = $fest ? (bool)$fest['voting_open'] : false;
$eventTitle      = $fest ? $fest['title'] : 'Henna Fest';
$likesPerMember  = $fest ? max(1,(int)($fest['likes_per_member']??3)) : 3;

// ── AJAX ────────────────────────────────────────────────────
if (!empty($_POST['action'])) {
  header('Content-Type: application/json');
  $act = $_POST['action'];
  $fid = (int)($_POST['fest_id'] ?? $festId);

  if ($act === 'vote') {
    $st=db()->prepare("SELECT voting_open,likes_per_member FROM henna_fests WHERE id=?");
    $st->execute([$fid]); $fr=$st->fetch();
    if (!$fr||!$fr['voting_open']) { echo json_encode(['ok'=>false,'msg'=>'Liking is closed.']); exit; }
    $eid = (int)($_POST['entry_id'] ?? 0);
    $lpm = max(1,(int)($fr['likes_per_member']??3));

    // Check already liked THIS entry
    $ck2=db()->prepare("SELECT id FROM henna_votes WHERE fest_id=? AND voter_id=? AND entry_id=?");
    $ck2->execute([$fid,$uid,$eid]);
    if ($ck2->fetch()) { echo json_encode(['ok'=>false,'msg'=>'You already liked this entry!']); exit; }

    // Check total likes used this fest
    $used=db()->prepare("SELECT COUNT(*) FROM henna_votes WHERE fest_id=? AND voter_id=?");
    $used->execute([$fid,$uid]); $usedCount=(int)$used->fetchColumn();
    if ($usedCount>=$lpm) { echo json_encode(['ok'=>false,'msg'=>"You've used all {$lpm} likes! You cannot like more."]); exit; }

    // Can't like own entry
    $own=db()->prepare("SELECT id FROM henna_entries WHERE id=? AND member_id=?");
    $own->execute([$eid,$uid]);
    if ($own->fetch()) { echo json_encode(['ok'=>false,'msg'=>'Cannot like your own entry!']); exit; }

    db()->prepare("INSERT INTO henna_votes(fest_id,voter_id,entry_id) VALUES(?,?,?)")->execute([$fid,$uid,$eid]);
    db()->prepare("UPDATE henna_entries SET vote_count=vote_count+1 WHERE id=?")->execute([$eid]);

    $remaining = $lpm - $usedCount - 1;
    $msg = $remaining > 0 ? "❤️ Liked! ({$remaining} like".($remaining>1?'s':'')." remaining)" : "❤️ Liked! (All {$lpm} likes used)";
    echo json_encode(['ok'=>true,'msg'=>$msg,'remaining'=>$remaining]); exit;
  }

  if ($act === 'delete_entry') {
    $eid=(int)($_POST['entry_id']??0);
    $st=db()->prepare("SELECT * FROM henna_entries WHERE id=? AND member_id=?");
    $st->execute([$eid,$uid]); $entry=$st->fetch();
    if (!$entry) { echo json_encode(['ok'=>false,'msg'=>'Not found']); exit; }
    db()->prepare("DELETE FROM henna_votes WHERE entry_id=?")->execute([$eid]);
    $path=__DIR__.'/../assets/uploads/henna/'.$entry['fest_id'].'/'.basename($entry['image_path']);
    if (file_exists($path)) @unlink($path);
    $ogPath=__DIR__.'/../assets/uploads/henna/'.$entry['fest_id'].'/og/'.basename($entry['og_path']??'');
    if (file_exists($ogPath)) @unlink($ogPath);
    db()->prepare("DELETE FROM henna_entries WHERE id=?")->execute([$eid]);
    echo json_encode(['ok'=>true]); exit;
  }

  if ($act === 'toggle_voting' && $isAdmin) {
    $st=db()->prepare("SELECT voting_open FROM henna_fests WHERE id=?");
    $st->execute([$fid]); $r=$st->fetch();
    $new=$r['voting_open']?0:1;
    db()->prepare("UPDATE henna_fests SET voting_open=? WHERE id=?")->execute([$new,$fid]);
    echo json_encode(['ok'=>true,'open'=>(bool)$new]); exit;
  }

  if ($act === 'save_fest' && $isAdmin) {
    $title=trim($_POST['title']??'');
    if (!$title) { echo json_encode(['ok'=>false,'msg'=>'Title required']); exit; }
    $poster='';
    if (!empty($_FILES['poster']['tmp_name'])) {
      $pf=$_FILES['poster']; $ext=strtolower(pathinfo($pf['name'],PATHINFO_EXTENSION));
      if (in_array($ext,['jpg','jpeg','png','webp'])&&$pf['size']<8*1024*1024) {
        $dir=__DIR__.'/../assets/uploads/henna/posters/';
        if(!is_dir($dir))@mkdir($dir,0755,true);
        $fn='poster_'.time().'.'.$ext;
        if(@move_uploaded_file($pf['tmp_name'],$dir.$fn)) $poster=$fn;
      }
    }
    $lpm = max(1,min(10,(int)($_POST['likes_per_member']??3)));
    if ($fid>0) {
      $old2=db()->prepare("SELECT poster_path FROM henna_fests WHERE id=?");
      $old2->execute([$fid]); $old2=$old2->fetch();
      if(!$poster) $poster=$old2['poster_path']??'';
      db()->prepare("UPDATE henna_fests SET title=?,description=?,prize_1=?,prize_2=?,prize_3=?,sponsor_name=?,join_link=?,poster_path=?,vote_start=?,vote_end=?,likes_per_member=? WHERE id=?")
         ->execute([trim($_POST['title']),trim($_POST['description']??''),trim($_POST['prize_1']??''),trim($_POST['prize_2']??''),trim($_POST['prize_3']??''),trim($_POST['sponsor_name']??''),trim($_POST['join_link']??''),$poster,!empty($_POST['vote_start'])?$_POST['vote_start'].':00':null,!empty($_POST['vote_end'])?$_POST['vote_end'].':00':null,$lpm,$fid]);
      echo json_encode(['ok'=>true,'msg'=>'Fest updated!','id'=>$fid]); exit;
    } else {
      db()->prepare("INSERT INTO henna_fests(title,description,prize_1,prize_2,prize_3,sponsor_name,join_link,poster_path,vote_start,vote_end,likes_per_member) VALUES(?,?,?,?,?,?,?,?,?,?,?)")
         ->execute([trim($_POST['title']),trim($_POST['description']??''),trim($_POST['prize_1']??''),trim($_POST['prize_2']??''),trim($_POST['prize_3']??''),trim($_POST['sponsor_name']??''),trim($_POST['join_link']??''),$poster,!empty($_POST['vote_start'])?$_POST['vote_start'].':00':null,!empty($_POST['vote_end'])?$_POST['vote_end'].':00':null,$lpm]);
      $nid=(int)db()->lastInsertId();
      echo json_encode(['ok'=>true,'msg'=>'Fest created!','id'=>$nid]); exit;
    }
  }

  if ($act === 'delete_fest' && $isAdmin) {
    db()->prepare("DELETE FROM henna_votes WHERE fest_id=?")->execute([$fid]);
    db()->prepare("DELETE FROM henna_entries WHERE fest_id=?")->execute([$fid]);
    db()->prepare("DELETE FROM henna_fests WHERE id=?")->execute([$fid]);
    echo json_encode(['ok'=>true]); exit;
  }

  if ($act === 'admin_delete' && $isAdmin) {
    $eid=(int)($_POST['entry_id']??0);
    $st=db()->prepare("SELECT * FROM henna_entries WHERE id=?");
    $st->execute([$eid]); $entry=$st->fetch();
    if ($entry) {
      db()->prepare("DELETE FROM henna_votes WHERE entry_id=?")->execute([$eid]);
      $path=__DIR__.'/../assets/uploads/henna/'.$entry['fest_id'].'/'.basename($entry['image_path']);
      if(file_exists($path))@unlink($path);
      db()->prepare("DELETE FROM henna_entries WHERE id=?")->execute([$eid]);
    }
    echo json_encode(['ok'=>true]); exit;
  }

  // Admin: reset all likes for a fest
  if ($act === 'reset_likes' && $isAdmin) {
    $fid2 = (int)($_POST['fest_id'] ?? $festId);
    // Remove all votes for this fest
    db()->prepare("DELETE FROM henna_votes WHERE fest_id=?")->execute([$fid2]);
    // Reset all vote counts to 0
    db()->prepare("UPDATE henna_entries SET vote_count=0 WHERE fest_id=?")->execute([$fid2]);
    echo json_encode(['ok'=>true,'msg'=>'All likes cleared!']); exit;
  }

  echo json_encode(['ok'=>false,'msg'=>'Unknown']); exit;
}

if (isset($_GET['get_fest']) && $isAdmin) {
  header('Content-Type: application/json');
  $st=db()->prepare("SELECT * FROM henna_fests WHERE id=?");
  $st->execute([(int)$_GET['get_fest']]);
  echo json_encode($st->fetch()?:[]);
  exit;
}

// Upload
$uploadMsg=null;
if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_FILES['henna_photo']) && $festId) {
  $ck=db()->prepare("SELECT id FROM henna_entries WHERE fest_id=? AND member_id=?");
  $ck->execute([$festId,$uid]);
  if ($ck->fetch()) {
    $uploadMsg=['err','Already submitted. Delete first.'];
  } else {
    $f=$_FILES['henna_photo'];
    $ext=strtolower(pathinfo($f['name'],PATHINFO_EXTENSION));
    if (!in_array($ext,['jpg','jpeg','png','webp'])) { $uploadMsg=['err','JPG/PNG/WebP only.']; }
    elseif ($f['size']>12*1024*1024) { $uploadMsg=['err','Max 12MB.']; }
    else {
      $dir=__DIR__.'/../assets/uploads/henna/'.$festId.'/';
      if(!is_dir($dir))@mkdir($dir,0755,true);
      $fn='entry_'.time().'_'.mt_rand(1000,9999).'.'.$ext;
      if(@move_uploaded_file($f['tmp_name'],$dir.$fn)){
        $t2=trim($_POST['entry_title']??'');
        $ins=db()->prepare("INSERT INTO henna_entries(fest_id,member_id,image_path,title) VALUES(?,?,?,?)");
        $ins->execute([$festId,$uid,$fn,$t2]);
        $eid2=(int)db()->lastInsertId();
        $ogDir=$dir.'og/'; if(!is_dir($ogDir))@mkdir($ogDir,0755,true);
        $ogFn='entry_'.$eid2.'.'.$ext;
        @copy($dir.$fn,$ogDir.$ogFn);
        db()->prepare("UPDATE henna_entries SET og_path=? WHERE id=?")->execute([$ogFn,$eid2]);
        $uploadMsg=['ok','✅ Entry submitted!'];
      } else { $uploadMsg=['err','Upload failed.']; }
    }
  }
}

// Load data
$entries=[];
if ($festId) {
  try { $entries=db()->query("SELECT e.*,u.name member_name FROM henna_entries e JOIN users u ON u.id=e.member_id WHERE e.fest_id={$festId} AND e.status='active' ORDER BY e.vote_count DESC, e.created_at ASC")->fetchAll(); } catch(Exception $e){}
}
$myEntry=null;
if ($festId) {
  $st=db()->prepare("SELECT * FROM henna_entries WHERE fest_id=? AND member_id=?");
  $st->execute([$festId,$uid]); $myEntry=$st->fetch();
}

// My likes for this fest
$myLikesUsed=0;
$myLikedEntryIds=[];
if ($festId) {
  $st2=db()->prepare("SELECT entry_id FROM henna_votes WHERE fest_id=? AND voter_id=?");
  $st2->execute([$festId,$uid]);
  $myVotes=$st2->fetchAll();
  $myLikesUsed=count($myVotes);
  $myLikedEntryIds=array_column($myVotes,'entry_id');
}

$likesRemaining = max(0,$likesPerMember - $myLikesUsed);
$totalVotes=0;
if ($festId) try { $totalVotes=(int)db()->query("SELECT COUNT(*) FROM henna_votes WHERE fest_id={$festId}")->fetchColumn(); } catch(Exception $e){}
$totalEntries=count($entries);
$pageTitle='🌿 '.h($eventTitle).' — '.h($CLUB);

require_once __DIR__.'/../includes/header.php';
?>
<style>
:root{--h1:#8B3A0F;--h2:#C4521A;--hg1:#2D5016;--hg2:#4A7C24;--gold:#D4A017;--cream:#FFF8F0}
.hfw{max-width:560px;margin:0 auto;padding-bottom:3rem}
.hf-hero{background:linear-gradient(135deg,#2D1B0E,#5C2A0F 40%,#8B3A0F 70%,#C4521A);padding:1.5rem 1rem 1rem;text-align:center}
.hf-hero h1{font-family:'Playfair Display',serif;font-size:1.5rem;color:#fff;margin-bottom:.15rem;font-weight:700}
.hf-hero p{font-size:.72rem;color:rgba(255,255,255,.6)}
.fest-tabs{display:flex;gap:.4rem;overflow-x:auto;background:#2D1B0E;padding:.4rem .6rem;scrollbar-width:none}
.fest-tab{flex-shrink:0;padding:.35rem .75rem;border-radius:20px;font-size:.68rem;font-weight:700;cursor:pointer;border:1.5px solid rgba(212,160,23,.3);color:rgba(255,255,255,.6);background:transparent;font-family:'DM Sans',sans-serif;white-space:nowrap}
.fest-tab.active{background:var(--gold);color:#000;border-color:var(--gold)}
/* Likes counter bar */
.likes-bar{background:#2D1B0E;padding:.5rem .9rem;display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid var(--gold)}
.likes-dots{display:flex;gap:.35rem;align-items:center}
.like-dot{width:22px;height:22px;border-radius:50%;border:2px solid rgba(212,160,23,.5);display:flex;align-items:center;justify-content:center;font-size:.7rem;transition:all .2s}
.like-dot.used{background:var(--h2);border-color:var(--h2)}
.like-dot.avail{background:rgba(255,255,255,.08);border-color:rgba(212,160,23,.6)}
.hf-stats{display:grid;grid-template-columns:repeat(3,1fr);background:#2D1B0E;border-bottom:3px solid var(--gold)}
.hf-stat{padding:.55rem .5rem;text-align:center;border-right:1px solid rgba(255,255,255,.1)}
.hf-stat:last-child{border-right:none}
.hf-stat-n{font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:var(--gold);line-height:1}
.hf-stat-l{font-size:.56rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.08em}
.vbadge{text-align:center;padding:.45rem;font-size:.72rem;font-weight:700;letter-spacing:.06em}
.vo{background:#e8f5e9;color:#2e7d32}.vc{background:#ffebee;color:#b71c1c}
.prizes-wrap{background:linear-gradient(135deg,var(--cream),#FFF0E0);margin:.7rem;border-radius:14px;padding:.8rem .9rem;border:1.5px solid rgba(196,82,26,.2)}
.prize-row{display:flex;align-items:center;gap:.5rem;padding:.35rem .5rem;border-radius:8px;margin-bottom:.25rem;background:rgba(255,255,255,.7)}
.card{background:#fff;margin:.7rem;border-radius:14px;box-shadow:0 3px 16px rgba(139,58,15,.1);border:1.5px solid rgba(196,82,26,.15);overflow:hidden}
.card-head{background:linear-gradient(135deg,var(--h1),var(--h2));padding:.7rem 1rem;display:flex;align-items:center;gap:.5rem}
.card-head h3{font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.08em;color:#fff;margin:0}
.eg{display:grid;grid-template-columns:1fr 1fr;gap:.5rem;padding:.4rem .7rem}
.ec{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(139,58,15,.1);border:1.5px solid rgba(196,82,26,.1);position:relative;cursor:pointer}
.ec img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block}
.ec-info{padding:.4rem .5rem .5rem}
.ec-name{font-size:.68rem;font-weight:800;color:var(--h1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:.15rem}
.vrow{display:flex;align-items:center;justify-content:space-between}
.vc2{font-family:'Bebas Neue',sans-serif;font-size:1rem;color:var(--h1);line-height:1}
.vl{font-size:.52rem;color:#94a3b8;text-transform:uppercase}
.bv{padding:.28rem .6rem;border:none;border-radius:7px;font-family:'DM Sans',sans-serif;font-size:.65rem;font-weight:800;cursor:pointer}
.bv-can{background:linear-gradient(135deg,var(--hg1),var(--hg2));color:#fff}
.bv-done{background:#fce4ec;color:#c62828}
.bv-no{background:#f0f0f0;color:#999}
.ea{display:flex;gap:.3rem;padding:0 .5rem .5rem}
.bs{flex:1;padding:.3rem;background:#25d366;color:#fff;border:none;border-radius:7px;font-size:.62rem;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.2rem}
.bd{padding:.3rem .4rem;background:#ffebee;color:#b71c1c;border:1px solid #ffcdd2;border-radius:7px;font-size:.62rem;font-weight:700;cursor:pointer}
.rb{position:absolute;top:6px;left:6px;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.7rem;z-index:5}
.r1{background:var(--gold);color:#000}.r2{background:#9e9e9e;color:#fff}.r3{background:#cd7f32;color:#fff}
/* liked checkmark on image */
.liked-badge{position:absolute;top:5px;right:5px;background:#c62828;border-radius:50%;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:.65rem;color:#fff;z-index:5}
.admin-box{background:#fff;margin:.7rem;border-radius:14px;box-shadow:0 3px 16px rgba(7,34,92,.1);border:1.5px solid rgba(7,34,92,.1);overflow:hidden}
.admin-head{background:linear-gradient(135deg,#07225c,#0d47a1);padding:.7rem 1rem;display:flex;align-items:center;gap:.5rem}
.admin-head h3{font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.08em;color:#fff;margin:0}
.popup{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:8000;align-items:flex-end;justify-content:center}
.popup-in{background:#fff;width:100%;max-width:520px;border-radius:24px 24px 0 0;max-height:93vh;overflow-y:auto;animation:su .3s ease}
@keyframes su{from{transform:translateY(100%)}to{transform:translateY(0)}}
.toast{position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%) translateY(40px);background:var(--h1);color:#fff;padding:.6rem 1.2rem;border-radius:25px;font-size:.8rem;font-weight:700;z-index:9999;opacity:0;transition:all .3s;white-space:nowrap}
.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.g{background:#2e7d32}.toast.e{background:#b71c1c}
.fbtn{padding:.25rem .7rem;border:1.5px solid rgba(139,58,15,.25);background:#fff;color:#8B3A0F;border-radius:20px;font-size:.68rem;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif}
.fbtn.active{background:linear-gradient(135deg,#8B3A0F,#C4521A);color:#fff;border-color:transparent}
.uarea{border:2px dashed rgba(196,82,26,.3);border-radius:10px;padding:1rem;text-align:center;cursor:pointer;background:#FFF8F0;margin-bottom:.5rem}
.empty{text-align:center;padding:2rem 1rem;color:#94a3b8}
</style>

<div class="hfw">
<div class="hf-hero">
  <span style="font-size:2rem;display:block;margin-bottom:.3rem">🌿</span>
  <h1><?php echo h($eventTitle); ?></h1>
  <p><?php echo h($CLUB); ?> · <?php echo h($PLACE); ?></p>
</div>

<?php if(count($allFests)>1||$isAdmin): ?>
<div class="fest-tabs">
  <?php foreach($allFests as $ft): ?>
  <button class="fest-tab<?php echo (int)$ft['id']===$festId?' active':''; ?>" onclick="switchFest(<?php echo (int)$ft['id']; ?>)">
    <?php echo h(mb_substr($ft['title'],0,22)); ?>
  </button>
  <?php endforeach; ?>
  <?php if($isAdmin): ?>
  <button class="fest-tab" onclick="openFF(0)" style="border-color:#D4A017;color:#D4A017">＋ New Fest</button>
  <?php endif; ?>
</div>
<?php elseif($isAdmin): ?>
<div style="text-align:right;padding:.4rem .8rem">
  <button onclick="openFF(0)" style="background:var(--gold);color:#000;border:none;border-radius:10px;padding:.38rem .85rem;font-size:.72rem;font-weight:800;cursor:pointer">＋ New Fest</button>
</div>
<?php endif; ?>

<?php if($fest): ?>

<?php if(!empty($fest['poster_path'])): ?>
<img src="<?php echo h(url('assets/uploads/henna/posters/'.basename($fest['poster_path']))); ?>" style="width:100%;max-height:280px;object-fit:cover;display:block">
<?php endif; ?>

<!-- Stats -->
<div class="hf-stats">
  <div class="hf-stat"><div class="hf-stat-n"><?php echo $totalEntries; ?></div><div class="hf-stat-l">Entries</div></div>
  <div class="hf-stat"><div class="hf-stat-n"><?php echo $totalVotes; ?></div><div class="hf-stat-l">Total Likes</div></div>
  <div class="hf-stat">
    <div class="hf-stat-n"><?php echo $votingOpen ? '❤️' : '🔒'; ?></div>
    <div class="hf-stat-l"><?php echo $votingOpen ? 'Open' : 'Closed'; ?></div>
  </div>
</div>

<!-- Voting status -->
<div class="vbadge <?php echo $votingOpen?'vo':'vc'; ?>">
  <?php
  if ($votingOpen) echo '❤️ Liking is OPEN';
  elseif (!empty($fest['vote_start']) && date('Y-m-d H:i:s')<$fest['vote_start']) echo '⏳ Opens '.date('d M Y, h:i A',strtotime($fest['vote_start']));
  else echo '🔒 Liking is CLOSED';
  ?>
</div>

<!-- My likes counter -->
<?php if($votingOpen): ?>
<div class="likes-bar">
  <div>
    <div style="font-size:.72rem;font-weight:700;color:#fff">Your Likes</div>
    <div style="font-size:.6rem;color:rgba(255,255,255,.5)"><?php echo $likesRemaining; ?> of <?php echo $likesPerMember; ?> remaining</div>
  </div>
  <div class="likes-dots">
    <?php for($i=0;$i<$likesPerMember;$i++): ?>
    <div class="like-dot <?php echo $i<$myLikesUsed?'used':'avail'; ?>"><?php echo $i<$myLikesUsed?'❤️':''; ?></div>
    <?php endfor; ?>
  </div>
</div>
<?php endif; ?>

<!-- Prizes -->
<?php if(!empty($fest['prize_1'])||!empty($fest['prize_2'])||!empty($fest['prize_3'])): ?>
<div class="prizes-wrap">
  <div style="font-family:'Playfair Display',serif;font-size:.88rem;font-weight:700;color:var(--h1);text-align:center;margin-bottom:.5rem">
    🏆 Prizes<?php if(!empty($fest['sponsor_name'])) echo ' — <span style="color:#e91e63">'.h($fest['sponsor_name']).'</span>'; ?>
  </div>
  <?php
  $prs=[$fest['prize_1']??'',$fest['prize_2']??'',$fest['prize_3']??''];
  $mds=['🥇','🥈','🥉']; $top3=array_slice($entries,0,3);
  foreach($prs as $pi=>$pn): if(!$pn) continue; $pw=$top3[$pi]??null;
  ?>
  <div class="prize-row">
    <span style="font-size:1.1rem"><?php echo $mds[$pi]; ?></span>
    <span style="font-size:.8rem;font-weight:600;color:var(--h1);flex:1"><?php echo h($pn); ?></span>
    <?php if($pw&&$pw['vote_count']>0): ?>
    <span style="font-size:.68rem;color:var(--h2);font-weight:700">— <?php echo h($pw['member_name']); ?> (<?php echo $pw['vote_count']; ?> ❤️)</span>
    <?php else: ?><span style="font-size:.65rem;color:#ccc">TBD</span><?php endif; ?>
  </div>
  <?php endforeach; ?>
  <?php if(!empty($fest['join_link'])): ?>
  <a href="<?php echo h($fest['join_link']); ?>" target="_blank" style="display:flex;align-items:center;justify-content:center;gap:.4rem;margin-top:.5rem;padding:.5rem;background:linear-gradient(135deg,#25d366,#128c7e);color:#fff;border-radius:10px;font-size:.78rem;font-weight:800;text-decoration:none">
    💬 Join Fest Group
  </a>
  <?php endif; ?>
</div>
<?php endif; ?>

<!-- Upload / My Entry -->
<div class="card">
  <div class="card-head">
    <span style="font-size:1.1rem">📸</span>
    <h3><?php echo $myEntry?'MY ENTRY':'SUBMIT YOUR ENTRY'; ?></h3>
    <?php if($isAdmin): ?>
    <button onclick="openFF(<?php echo $festId; ?>)" style="margin-left:auto;background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:8px;padding:.28rem .6rem;font-size:.65rem;font-weight:700;cursor:pointer">✏️ Edit</button>
    <?php endif; ?>
  </div>
  <div style="padding:.85rem">
    <?php if($uploadMsg): ?>
    <div style="padding:.45rem .8rem;border-radius:8px;margin-bottom:.6rem;font-size:.76rem;font-weight:600;<?php echo $uploadMsg[0]==='ok'?'background:#e8f5e9;color:#2e7d32':'background:#ffebee;color:#b71c1c'; ?>">
      <?php echo $uploadMsg[1]; ?>
    </div>
    <?php endif; ?>
    <?php if($myEntry): ?>
    <div style="text-align:center">
      <?php $myImgUrl=$SITE.'/assets/uploads/henna/'.$festId.'/'.basename($myEntry['image_path']); ?>
      <img src="<?php echo h($myImgUrl); ?>" style="width:100%;max-height:200px;object-fit:cover;border-radius:10px;border:2px solid rgba(196,82,26,.2);margin-bottom:.5rem">
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;color:var(--h1)">
        <?php echo (int)$myEntry['vote_count']; ?> <span style="font-size:.6rem;color:var(--h2);font-family:'DM Sans',sans-serif">LIKES</span>
      </div>
      <div style="display:flex;gap:.5rem;margin-top:.6rem;justify-content:center">
        <?php $shareEid=(int)$myEntry['id']; $shareName=h(addslashes($me['name']??'')); $shareEvt=h(addslashes($eventTitle)); $shareSpon=h(addslashes($fest['sponsor_name']??'')); ?>
        <button onclick="shareEntry(<?php echo $shareEid; ?>,<?php echo $festId; ?>,'<?php echo $shareName; ?>','<?php echo $shareEvt; ?>','<?php echo $shareSpon; ?>')" style="background:#25d366;color:#fff;border:none;border-radius:10px;padding:.5rem 1rem;font-weight:700;cursor:pointer;font-size:.78rem">💚 Share</button>
        <button onclick="delEntry(<?php echo $shareEid; ?>)" style="background:#ffebee;color:#b71c1c;border:1px solid #ffcdd2;border-radius:10px;padding:.5rem .8rem;font-weight:700;cursor:pointer;font-size:.78rem">🗑️</button>
      </div>
    </div>
    <?php else: ?>
    <form method="POST" enctype="multipart/form-data">
      <div class="fg"><label class="lbl">Title (optional)</label><input type="text" name="entry_title" class="inp" placeholder="e.g. Bridal Mehandi Design"></div>
      <div class="fg"><label class="lbl">Your Mehandi Photo *</label>
        <div class="uarea" onclick="document.getElementById('hpi').click()">
          <div id="pp" style="display:none"><img id="pi" style="max-height:160px;border-radius:8px;max-width:100%"></div>
          <div id="ph"><div style="font-size:1.8rem">🌿</div><div style="font-size:.8rem;font-weight:600;color:var(--h1)">Tap to select photo</div><div style="font-size:.65rem;color:#94a3b8">Gallery or Camera</div></div>
        </div>
        <input type="file" id="hpi" name="henna_photo" accept="image/*" style="display:none" onchange="prvPhoto(this)">
      </div>
      <button type="submit" style="width:100%;padding:.65rem;background:linear-gradient(135deg,var(--h1),var(--h2));color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;font-size:.85rem">🌿 Submit Entry</button>
    </form>
    <?php endif; ?>
  </div>
</div>

<!-- All Entries -->
<?php if(!empty($entries)): ?>
<div style="padding:.4rem .7rem .2rem;display:flex;align-items:center;justify-content:space-between">
  <div style="font-family:'Playfair Display',serif;font-size:.95rem;font-weight:700;color:var(--h1)">🌸 All Entries</div>
  <div style="display:flex;gap:.3rem">
    <button onclick="fe('likes')" id="fb-likes" class="fbtn active">❤️ Top</button>
    <button onclick="fe('new')" id="fb-new" class="fbtn">🆕 New</button>
  </div>
</div>
<div class="eg">
<?php foreach($entries as $rank=>$entry):
  $eImg     = $SITE.'/assets/uploads/henna/'.$festId.'/'.basename($entry['image_path']);
  $eIsMine  = $entry['member_id']==$uid;
  $eIsLiked = in_array((string)$entry['id'],$myLikedEntryIds) || in_array((int)$entry['id'],$myLikedEntryIds);
  $eCanVote = $votingOpen && $likesRemaining>0 && !$eIsMine && !$eIsLiked;
  $eRankCls = $rank===0?'r1':($rank===1?'r2':($rank===2?'r3':''));
  $eName    = h(addslashes($entry['member_name']));
  $eEvt     = h(addslashes($eventTitle));
  $eSpon    = h(addslashes($fest['sponsor_name']??''));
  $eBorder  = $eIsLiked?'#c62828':($rank===0?'var(--gold)':($rank===1?'#9e9e9e':($rank===2?'#cd7f32':'rgba(196,82,26,.1)')));
?>
<div class="ec hfec" data-likes="<?php echo (int)$entry['vote_count']; ?>" data-ts="<?php echo strtotime($entry['created_at']); ?>" style="border-color:<?php echo $eBorder; ?>"
  onclick="opop(<?php echo (int)$entry['id']; ?>,'<?php echo $eName; ?>','<?php echo h($eImg); ?>',<?php echo (int)$entry['vote_count']; ?>,<?php echo $eIsMine?'true':'false'; ?>,<?php echo $eIsLiked?'true':'false'; ?>,<?php echo $eCanVote?'true':'false'; ?>,'<?php echo $eEvt; ?>','<?php echo $eSpon; ?>')">
  <?php if($rank<3&&$entry['vote_count']>0): ?>
  <div class="rb <?php echo $eRankCls; ?>"><?php echo $rank===0?'🥇':($rank===1?'🥈':'🥉'); ?></div>
  <?php endif; ?>
  <?php if($eIsLiked): ?>
  <div class="liked-badge">❤️</div>
  <?php endif; ?>
  <img src="<?php echo h($eImg); ?>" loading="lazy" alt="">
  <div class="ec-info">
    <div class="ec-name"><?php echo h($entry['member_name']); ?></div>
    <div class="vrow">
      <div><div class="vc2"><?php echo (int)$entry['vote_count']; ?></div><div class="vl">likes</div></div>
      <?php if($eIsMine): ?>
      <button class="bv bv-no">Mine</button>
      <?php elseif($eIsLiked): ?>
      <button class="bv bv-done">❤️</button>
      <?php elseif($eCanVote): ?>
      <button class="bv bv-can" onclick="event.stopPropagation();cv(<?php echo (int)$entry['id']; ?>,<?php echo $festId; ?>,this)">❤️</button>
      <?php else: ?>
      <button class="bv bv-no"><?php echo $votingOpen&&$likesRemaining<=0?'No likes left':'🔒'; ?></button>
      <?php endif; ?>
    </div>
  </div>
  <div class="ea">
    <button class="bs" onclick="event.stopPropagation();shareEntry(<?php echo (int)$entry['id']; ?>,<?php echo $festId; ?>,'<?php echo $eName; ?>','<?php echo $eEvt; ?>','<?php echo $eSpon; ?>')">Share</button>
    <?php if($eIsMine||$isAdmin): ?>
    <?php $delFn=($isAdmin&&!$eIsMine)?'adDel':'delEntry'; ?>
    <button class="bd" onclick="event.stopPropagation();<?php echo $delFn; ?>(<?php echo (int)$entry['id']; ?>)">🗑️</button>
    <?php endif; ?>
  </div>
</div>
<?php endforeach; ?>
</div>
<?php else: ?>
<div class="empty"><span style="font-size:2rem;display:block;margin-bottom:.5rem">🌿</span><p>No entries yet.</p></div>
<?php endif; ?>

<!-- Admin Panel -->
<?php if($isAdmin): ?>
<div class="admin-box">
  <div class="admin-head"><span>🛡️</span><h3>ADMIN</h3></div>
  <div style="padding:.85rem">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:.65rem;background:#f8fafc;border-radius:10px;border:1px solid #e8ecf4;margin-bottom:.7rem">
      <div><div style="font-weight:700;font-size:.85rem">Liking Status</div>
      <div style="font-size:.68rem;color:#64748b" id="vtxt"><?php echo $votingOpen?'🟢 OPEN':'🔴 CLOSED'; ?></div></div>
      <button onclick="tvote(this,<?php echo $festId; ?>)" style="background:<?php echo $votingOpen?'#b71c1c':'#2e7d32'; ?>;color:#fff;border:none;border-radius:8px;padding:.42rem .9rem;font-weight:700;cursor:pointer;font-size:.75rem">
        <?php echo $votingOpen?'🔒 Close':'🗳️ Open'; ?>
      </button>
    </div>
    <div style="display:flex;gap:.4rem">
      <button onclick="openFF(<?php echo $festId; ?>)" style="flex:1;background:linear-gradient(135deg,#07225c,#0d47a1);color:#fff;border:none;border-radius:10px;padding:.5rem;font-weight:700;cursor:pointer;font-size:.75rem">✏️ Edit Fest</button>
      <button onclick="openFF(0)" style="flex:1;background:var(--gold);color:#000;border:none;border-radius:10px;padding:.5rem;font-weight:800;cursor:pointer;font-size:.75rem">＋ New Fest</button>
      <?php $spUrl=$fest['poster_path']?h($SITE.'/assets/uploads/henna/posters/'.basename($fest['poster_path'])):''; $spEvt=h(addslashes($eventTitle)); ?>
      <button onclick="sfest(<?php echo $festId; ?>,'<?php echo $spEvt; ?>','<?php echo $spUrl; ?>')" style="flex:1;background:#25d366;color:#fff;border:none;border-radius:10px;padding:.5rem;font-weight:700;cursor:pointer;font-size:.75rem">💚 Share</button>
    </div>
    <div style="margin-top:.5rem">
      <button onclick="resetLikes(<?php echo $festId; ?>)" style="width:100%;background:#fff3e0;color:#e65100;border:1.5px solid #ffcc02;border-radius:10px;padding:.48rem;font-weight:700;cursor:pointer;font-size:.75rem">🔄 Reset All Likes This Season</button>
    </div>
    <div style="font-size:.62rem;color:#94a3b8;margin-top:.3rem;text-align:center">Clears all votes and resets like counts to zero</div>
    </div>
  </div>
</div>
<?php endif; ?>

<?php else: ?>
<div class="empty"><span style="font-size:2rem;display:block;margin-bottom:.5rem">🎪</span><p>No fests yet.</p></div>
<?php endif; ?>
</div>

<!-- Entry Popup -->
<div class="popup" id="epop" onclick="if(event.target===this)cpop()">
<div class="popup-in">
  <div style="display:flex;align-items:center;justify-content:space-between;padding:.6rem 1rem;border-bottom:1px solid #f0f0f0">
    <div style="font-family:'Playfair Display',serif;font-size:.95rem;font-weight:700;color:var(--h1)">🌿 Entry</div>
    <button onclick="cpop()" style="background:#f5f5f5;border:none;border-radius:50%;width:30px;height:30px;cursor:pointer">✕</button>
  </div>
  <div style="background:#1a1a1a;min-height:200px">
    <img id="popImg" src="" style="width:100%;max-height:55vh;object-fit:contain;display:block">
  </div>
  <div style="padding:.8rem 1rem">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">
      <div id="popName" style="font-family:'Playfair Display',serif;font-size:1.1rem;font-weight:700;color:var(--h1)"></div>
      <div><span id="popVotes" style="font-family:'Bebas Neue',sans-serif;font-size:1.8rem;color:var(--h1)"></span> <span style="font-size:.6rem;color:#94a3b8">❤️</span></div>
    </div>
    <div id="popVoteWrap" style="margin-bottom:.6rem"></div>
    <button id="popShareBtn" style="width:100%;padding:.65rem;background:linear-gradient(135deg,#25d366,#128c7e);color:#fff;border:none;border-radius:12px;font-weight:800;font-size:.88rem;cursor:pointer">💚 Share on WhatsApp</button>
    <button onclick="cpop()" style="width:100%;padding:.5rem;margin-top:.4rem;background:#f5f5f5;color:#64748b;border:none;border-radius:10px;font-weight:600;font-size:.82rem;cursor:pointer">Close</button>
  </div>
</div>
</div>

<!-- Fest Form Popup -->
<?php if($isAdmin): ?>
<div class="popup" id="ffpop" onclick="if(event.target===this)cff()">
<div class="popup-in">
  <div style="background:linear-gradient(135deg,#07225c,#0d47a1);padding:.7rem 1rem;border-radius:24px 24px 0 0;display:flex;align-items:center">
    <span style="font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.08em;color:#fff;flex:1" id="ffTitle">CREATE FEST</span>
    <button onclick="cff()" style="background:rgba(255,255,255,.2);border:none;border-radius:50%;width:28px;height:28px;color:#fff;cursor:pointer">✕</button>
  </div>
  <div style="padding:1rem">
    <input type="hidden" id="ff_id">
    <div class="fg"><label class="lbl">Title *</label><input type="text" id="ff_t" class="inp" placeholder="e.g. Eid Mehandi Fest 2026"></div>
    <div class="fg"><label class="lbl">Description</label><textarea id="ff_d" class="inp" rows="2"></textarea></div>
    <div class="fg"><label class="lbl">Event Poster</label>
      <div class="uarea" onclick="document.getElementById('ff_p').click()">
        <div id="ff_pp" style="display:none"><img id="ff_pi" style="max-height:100px;border-radius:6px;max-width:100%"></div>
        <div id="ff_ph">🖼️ Upload poster (JPG/PNG)</div>
      </div>
      <input type="file" id="ff_p" accept="image/*" style="display:none" onchange="pfv(this,'ff_pi','ff_pp','ff_ph')">
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">🥇 1st Prize</label><input type="text" id="ff_p1" class="inp"></div>
      <div class="fg"><label class="lbl">🥈 2nd Prize</label><input type="text" id="ff_p2" class="inp"></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">🥉 3rd Prize</label><input type="text" id="ff_p3" class="inp"></div>
      <div class="fg"><label class="lbl">🏅 Sponsor</label><input type="text" id="ff_s" class="inp" placeholder="e.g. Blush Bee"></div>
    </div>
    <div class="fg"><label class="lbl">WhatsApp Group Link</label><input type="text" id="ff_j" class="inp" placeholder="https://chat.whatsapp.com/..."></div>
    <!-- Likes per member setting -->
    <div class="fg">
      <label class="lbl">❤️ Likes Per Member</label>
      <div style="display:flex;gap:.5rem;align-items:center">
        <input type="number" id="ff_lpm" class="inp" value="3" min="1" max="10" style="width:80px;text-align:center;font-family:'Bebas Neue',sans-serif;font-size:1.2rem">
        <div style="font-size:.7rem;color:#64748b">likes per member<br><span style="color:#8B3A0F">Default: 3</span></div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">⏰ Liking Starts</label><input type="datetime-local" id="ff_vs" class="inp"></div>
      <div class="fg"><label class="lbl">⏰ Liking Ends</label><input type="datetime-local" id="ff_ve" class="inp"></div>
    </div>
    <button onclick="saveff()" style="width:100%;padding:.65rem;background:linear-gradient(135deg,#07225c,#0d47a1);color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;font-size:.85rem;margin-top:.3rem">💾 Save Fest</button>
  </div>
</div>
</div>
<?php endif; ?>

<div class="toast" id="ht"></div>

<script>
var SELF  = "<?php echo url('modules/henna_fest.php'); ?>";
var CLUB  = <?php echo json_encode($CLUB); ?>;
var PLACE = <?php echo json_encode($PLACE); ?>;
var SITE  = <?php echo json_encode($SITE); ?>;
var FID   = <?php echo $festId ?: 0; ?>;
var LPM   = <?php echo $likesPerMember; ?>;         // likes per member
var LUSED = <?php echo $myLikesUsed; ?>;             // likes used so far
var LREM  = <?php echo $likesRemaining; ?>;          // likes remaining

function toast(m,t){var e=document.getElementById('ht');e.textContent=m;e.className='toast on'+(t==='g'?' g':t==='e'?' e':'');setTimeout(function(){e.className='toast'},2800);}
function switchFest(id){window.location.href=SELF+'?fest='+id;}
function prvPhoto(i){if(!i.files||!i.files[0])return;var r=new FileReader();r.onload=function(e){document.getElementById('pi').src=e.target.result;document.getElementById('pp').style.display='block';document.getElementById('ph').style.display='none';};r.readAsDataURL(i.files[0]);}

function cv(eid,fid,btn){
  btn.disabled=true;btn.textContent='⏳';
  var fd=new FormData();fd.append('action','vote');fd.append('entry_id',eid);fd.append('fest_id',fid);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      LUSED++;LREM=LPM-LUSED;
      toast(res.msg,'g');
      // Update dots
      updateLikeDots();
      setTimeout(function(){location.reload();},1200);
    } else {
      toast(res.msg,'e');btn.disabled=false;btn.textContent='❤️';
    }
  });
}

function updateLikeDots(){
  var dots=document.querySelectorAll('.like-dot');
  dots.forEach(function(d,i){
    if(i<LUSED){d.classList.add('used');d.classList.remove('avail');d.textContent='❤️';}
    else{d.classList.remove('used');d.classList.add('avail');d.textContent='';}
  });
  var remEl=document.querySelector('.likes-bar div div:last-child');
  if(remEl) remEl.textContent=LREM+' of '+LPM+' remaining';
}

function delEntry(id){if(!confirm('Delete your entry?'))return;var fd=new FormData();fd.append('action','delete_entry');fd.append('entry_id',id);fd.append('fest_id',FID);fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){if(res.ok){toast('Deleted');setTimeout(function(){location.reload();},700);}else toast(res.msg,'e');});}
function adDel(id){if(!confirm('Delete entry?'))return;var fd=new FormData();fd.append('action','admin_delete');fd.append('entry_id',id);fd.append('fest_id',FID);fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){if(res.ok){toast('Deleted');setTimeout(function(){location.reload();},700);}});}
function tvote(btn,fid){var fd=new FormData();fd.append('action','toggle_voting');fd.append('fest_id',fid);fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){if(res.ok){var o=res.open;btn.textContent=o?'🔒 Close':'🗳️ Open';btn.style.background=o?'#b71c1c':'#2e7d32';document.getElementById('vtxt').textContent=o?'🟢 OPEN':'🔴 CLOSED';toast(o?'Liking OPEN!':'Liking CLOSED',o?'g':'');}});}
function fe(m){document.querySelectorAll('.fbtn').forEach(function(b){b.classList.remove('active');});document.getElementById('fb-'+m).classList.add('active');var g=document.querySelector('.eg');if(!g)return;var cs=Array.from(g.querySelectorAll('.hfec'));cs.sort(function(a,b){return m==='likes'?parseInt(b.dataset.likes||0)-parseInt(a.dataset.likes||0):parseInt(b.dataset.ts||0)-parseInt(a.dataset.ts||0);});cs.forEach(function(c){g.appendChild(c);});}

function opop(id,name,img,votes,isMine,isLiked,canVote,evt,spon){
  document.getElementById('popImg').src=img;
  document.getElementById('popName').textContent=name;
  document.getElementById('popVotes').textContent=votes;
  var vw=document.getElementById('popVoteWrap');
  if(isMine){
    vw.innerHTML='<div style="text-align:center;padding:.3rem;font-size:.78rem;color:#94a3b8">This is your entry</div>';
  } else if(isLiked){
    vw.innerHTML='<button style="width:100%;padding:.6rem;background:#fce4ec;color:#c62828;border:2px solid #ef9a9a;border-radius:10px;font-weight:800;font-size:.85rem">❤️ You liked this!</button>';
  } else if(canVote){
    vw.innerHTML='<button onclick="cv('+id+','+FID+',this);cpop()" style="width:100%;padding:.65rem;background:linear-gradient(135deg,var(--h1),var(--h2));color:#fff;border:none;border-radius:10px;font-weight:800;font-size:.9rem;cursor:pointer">❤️ Like This Design ('+LREM+' left)</button>';
  } else if(LREM<=0&&!isMine){
    vw.innerHTML='<button style="width:100%;padding:.6rem;background:#f5f5f5;color:#999;border:none;border-radius:10px;font-size:.82rem">All '+LPM+' likes used</button>';
  } else {
    vw.innerHTML='<button style="width:100%;padding:.6rem;background:#f5f5f5;color:#999;border:none;border-radius:10px;font-size:.82rem">🔒 Liking closed</button>';
  }
  document.getElementById('popShareBtn').onclick=function(){shareEntry(id,FID,name,evt,spon);};
  document.getElementById('epop').style.display='flex';
  document.body.style.overflow='hidden';
}
function cpop(){document.getElementById('epop').style.display='none';document.body.style.overflow='';}

function shareEntry(eid,fid,name,evt,spon){
  toast('Preparing…');
  var cv2=document.createElement('canvas'),ctx=cv2.getContext('2d');
  // Try webp first, fallback to jpg
  var ogUrl=SITE+'/assets/uploads/henna/'+fid+'/og/entry_'+eid+'.webp';
  fetch(ogUrl).then(function(r){
    if(!r.ok) throw new Error('not found');
    return r.blob();
  }).catch(function(){
    return fetch(SITE+'/assets/uploads/henna/'+fid+'/og/entry_'+eid+'.jpg');
  }).then(function(r){
    return r instanceof Response ? r.blob() : r;
  }).then(function(blob){
    var u=URL.createObjectURL(blob),img=new Image();
    img.onload=function(){
      cv2.width=img.width;cv2.height=img.height;var W=img.width,H=img.height;
      ctx.drawImage(img,0,0,W,H);URL.revokeObjectURL(u);
      var bH=Math.round(H*.10),bY=H-bH;
      var bg=ctx.createLinearGradient(0,bY,W,bY+bH);
      bg.addColorStop(0,'rgba(45,27,14,.88)');bg.addColorStop(1,'rgba(92,42,15,.88)');
      ctx.fillStyle=bg;ctx.fillRect(0,bY,W,bH);
      ctx.fillStyle='rgba(212,160,23,.8)';ctx.fillRect(0,bY,W,3);
      var logo=new Image();logo.crossOrigin='anonymous';
      logo.onload=function(){wm(logo);};logo.onerror=function(){wm(null);};
      logo.src=SITE+'/assets/logo.png';
      function wm(lg){
        if(lg){var lS=Math.round(bH*.72),lX=Math.round(W*.03),lY=bY+(bH-lS)/2;ctx.save();ctx.beginPath();ctx.arc(lX+lS/2,lY+lS/2,lS/2,0,Math.PI*2);ctx.clip();ctx.fillStyle='#fff';ctx.fillRect(lX,lY,lS,lS);ctx.drawImage(lg,lX,lY,lS,lS);ctx.restore();}
        var tX=Math.round(W*.16),f1=Math.round(bH*.36),f2=Math.round(bH*.24);
        ctx.font='bold '+f1+'px DM Sans,sans-serif';ctx.fillStyle='#fff';ctx.textBaseline='middle';
        ctx.fillText(CLUB,tX,bY+bH*.34);
        ctx.font=f2+'px DM Sans,sans-serif';ctx.fillStyle='rgba(255,255,255,.72)';
        ctx.fillText('🌿 '+name+' · '+evt+(spon?' · 🏅 '+spon:''),tX,bY+bH*.72);
        cv2.toBlob(function(b){
          var file=new File([b],'HennaFest.jpg',{type:'image/jpeg'});
          var link=SITE+'/modules/henna_share.php?id='+eid;
          var msg='🌿 *'+evt+'*\n'
              +'🎨 Design by *'+name+'*\n'
              +'📍 '+PLACE+'\n'
              +'🏛️ '+CLUB+'\n\n'
              +'📢 *HOW TO PARTICIPATE:*\n'
              +'1️⃣ *Step 1:* Open Henna Fest on website\n'
              +'2️⃣ *Step 2:* Upload your mehandi photo\n'
              +'3️⃣ *Step 3:* Get votes from club members\n'
              +'4️⃣ *Step 4:* Top 3 win prizes! 🏆\n\n'
              +'❤️ Click the link below to like this design:\n'
              +link+'\n\n'
              +'📢 *Follow and support:*\n'
              +'https://www.instagram.com/blush.bee_ss?igsh=emlxMmF4aGtxMG11';
          if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],text:msg});}
          else{var a=document.createElement('a');a.href=cv2.toDataURL('image/jpeg',.92);a.download='HennaFest.jpg';a.click();setTimeout(function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');},700);}
        },'image/jpeg',.92);
      }
    };
    img.onerror=function(){URL.revokeObjectURL(u);toast('Photo not found','e');};
    img.src=u;
  }).catch(function(){toast('Error loading photo','e');});
}

function sfest(fid,title,pUrl){
  var msg='🌿 *'+title+'*\n'
      +'📍 '+PLACE+'\n'
      +'🏛️ '+CLUB+'\n\n'
      +'📢 *HOW TO PARTICIPATE:*\n'
      +'1️⃣ *Step 1:* Open Henna Fest on website\n'
      +'2️⃣ *Step 2:* Upload your mehandi photo\n'
      +'3️⃣ *Step 3:* Get votes from club members\n'
      +'4️⃣ *Step 4:* Top 3 win prizes! 🏆\n\n'
      +'👉 Join/Vote here: '+SITE+'/modules/henna_fest.php?fest='+fid+'\n\n'
      +'📢 *Follow and support:*\n'
      +'https://www.instagram.com/blush.bee_ss?igsh=emlxMmF4aGtxMG11';
  if(!pUrl){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');return;}
  fetch(pUrl).then(function(r){return r.blob();}).then(function(blob){
    var file=new File([blob],'fest.jpg',{type:'image/jpeg'});
    if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],text:msg});}
    else{var a=document.createElement('a');a.href=pUrl;a.download='fest.jpg';a.click();setTimeout(function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');},600);}
  }).catch(function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');});
}

function pfv(i,imgId,wId,phId){if(!i.files||!i.files[0])return;var r=new FileReader();r.onload=function(e){document.getElementById(imgId).src=e.target.result;document.getElementById(wId).style.display='block';document.getElementById(phId).style.display='none';};r.readAsDataURL(i.files[0]);}
function openFF(fid){
  document.getElementById('ff_id').value=fid||'';
  document.getElementById('ffTitle').textContent=fid?'EDIT FEST':'CREATE FEST';
  if(fid){
    fetch(SELF+'?get_fest='+fid).then(function(r){return r.json();}).then(function(d){
      document.getElementById('ff_t').value=d.title||'';
      document.getElementById('ff_d').value=d.description||'';
      document.getElementById('ff_p1').value=d.prize_1||'';
      document.getElementById('ff_p2').value=d.prize_2||'';
      document.getElementById('ff_p3').value=d.prize_3||'';
      document.getElementById('ff_s').value=d.sponsor_name||'';
      document.getElementById('ff_j').value=d.join_link||'';
      document.getElementById('ff_lpm').value=d.likes_per_member||3;
      if(d.vote_start)document.getElementById('ff_vs').value=d.vote_start.slice(0,16);
      if(d.vote_end)document.getElementById('ff_ve').value=d.vote_end.slice(0,16);
      if(d.poster_path){document.getElementById('ff_pi').src=SITE+'/assets/uploads/henna/posters/'+d.poster_path;document.getElementById('ff_pp').style.display='block';document.getElementById('ff_ph').style.display='none';}
    });
  } else {
    ['ff_t','ff_d','ff_p1','ff_p2','ff_p3','ff_s','ff_j','ff_vs','ff_ve'].forEach(function(id){document.getElementById(id).value='';});
    document.getElementById('ff_lpm').value=3;
  }
  document.getElementById('ffpop').style.display='flex';document.body.style.overflow='hidden';
}
function cff(){document.getElementById('ffpop').style.display='none';document.body.style.overflow='';}
function resetLikes(fid){
  if(!confirm('Reset ALL likes for this fest?\nThis will clear all votes and set like counts to zero.\nThis cannot be undone!')) return;
  var fd=new FormData();
  fd.append('action','reset_likes');
  fd.append('fest_id',fid);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      toast('🔄 '+res.msg,'g');
      setTimeout(function(){location.reload();},900);
    } else toast(res.msg,'e');
  });
}

function saveff(){
  var fd=new FormData();fd.append('action','save_fest');
  fd.append('fest_id',document.getElementById('ff_id').value||'0');
  fd.append('title',document.getElementById('ff_t').value);
  fd.append('description',document.getElementById('ff_d').value);
  fd.append('prize_1',document.getElementById('ff_p1').value);
  fd.append('prize_2',document.getElementById('ff_p2').value);
  fd.append('prize_3',document.getElementById('ff_p3').value);
  fd.append('sponsor_name',document.getElementById('ff_s').value);
  fd.append('join_link',document.getElementById('ff_j').value);
  fd.append('likes_per_member',document.getElementById('ff_lpm').value||3);
  fd.append('vote_start',document.getElementById('ff_vs').value||'');
  fd.append('vote_end',document.getElementById('ff_ve').value||'');
  var pf=document.getElementById('ff_p');if(pf&&pf.files&&pf.files[0])fd.append('poster',pf.files[0]);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){toast(res.msg,'g');setTimeout(function(){window.location.href=SELF+'?fest='+res.id;},1000);}
    else toast(res.msg||'Error','e');
  });
}
</script>
<?php require_once __DIR__.'/../includes/footer.php'; ?>
