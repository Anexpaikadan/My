<?php
// modules/fest_manager.php — 🎪 Fest Manager
// Admin creates fests → members join, upload, vote
// Each fest has poster, prizes, sponsor, voting window
// PHP 7.3+ compatible — Aishwarya Arts & Sports Club

require_once __DIR__ . '/../includes/config.php';
requireLogin();
$me      = currentUser();
$isAdmin = isAdminRole($me['role']);
$uid     = (int)$me['id'];
$CLUB    = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
$PLACE   = setting('CLUB_PLACE', 'Vettikkattiri');
$SITE    = rtrim(SITE_URL, '/');

// ── Auto-create tables ──────────────────────────────────────
try { db()->exec("CREATE TABLE IF NOT EXISTS fests (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  slug          VARCHAR(100) NOT NULL UNIQUE,
  title         VARCHAR(200) NOT NULL,
  description   TEXT DEFAULT '',
  poster_path   VARCHAR(500) DEFAULT '',
  prize_1       VARCHAR(300) DEFAULT '',
  prize_2       VARCHAR(300) DEFAULT '',
  prize_3       VARCHAR(300) DEFAULT '',
  sponsor_name  VARCHAR(200) DEFAULT '',
  sponsor_logo  VARCHAR(500) DEFAULT '',
  join_link     VARCHAR(500) DEFAULT '',
  voting_open   TINYINT(1) DEFAULT 0,
  vote_start    DATETIME DEFAULT NULL,
  vote_end      DATETIME DEFAULT NULL,
  status        ENUM('active','closed','draft') DEFAULT 'active',
  created_by    INT NOT NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS fest_entries (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  fest_id     INT NOT NULL,
  member_id   INT NOT NULL,
  image_path  VARCHAR(500) NOT NULL,
  og_path     VARCHAR(500) DEFAULT '',
  title       VARCHAR(200) DEFAULT '',
  like_count  INT DEFAULT 0,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY one_per_fest (fest_id, member_id)
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS fest_likes (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  fest_id    INT NOT NULL,
  entry_id   INT NOT NULL,
  voter_id   INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY one_like (fest_id, voter_id)
)"); } catch(Exception $e){}

// ── Current fest from URL ───────────────────────────────────
$festId   = (int)($_GET['fest'] ?? 0);
$view     = $_GET['view'] ?? 'list'; // list | fest | admin_edit

// ── AJAX ───────────────────────────────────────────────────
if (!empty($_POST['action'])) {
  header('Content-Type: application/json');
  $act = $_POST['action'];

  // Like entry
  if ($act === 'like') {
    $eid = (int)($_POST['entry_id'] ?? 0);
    $fid = (int)($_POST['fest_id']  ?? 0);
    $st  = db()->prepare("SELECT * FROM fests WHERE id=?"); $st->execute([$fid]); $fest=$st->fetch();
    if (!$fest || !$fest['voting_open']) { echo json_encode(['ok'=>false,'msg'=>'Liking is closed.']); exit; }
    $ck = db()->prepare("SELECT id FROM fest_likes WHERE fest_id=? AND voter_id=?");
    $ck->execute([$fid,$uid]); 
    if ($ck->fetch()) { echo json_encode(['ok'=>false,'msg'=>'You already liked an entry!']); exit; }
    $own = db()->prepare("SELECT id FROM fest_entries WHERE id=? AND member_id=?");
    $own->execute([$eid,$uid]);
    if ($own->fetch()) { echo json_encode(['ok'=>false,'msg'=>"Can't like your own entry!"]); exit; }
    db()->prepare("INSERT INTO fest_likes(fest_id,entry_id,voter_id) VALUES(?,?,?)")->execute([$fid,$eid,$uid]);
    db()->prepare("UPDATE fest_entries SET like_count=like_count+1 WHERE id=?")->execute([$eid]);
    echo json_encode(['ok'=>true,'msg'=>'❤️ Liked!']); exit;
  }

  // Delete entry
  if ($act === 'delete_entry') {
    $eid = (int)($_POST['entry_id'] ?? 0);
    $st  = db()->prepare("SELECT * FROM fest_entries WHERE id=? AND member_id=?");
    $st->execute([$eid,$uid]); $entry=$st->fetch();
    if (!$entry) { echo json_encode(['ok'=>false,'msg'=>'Not found']); exit; }
    $fid = $entry['fest_id'];
    db()->prepare("DELETE FROM fest_likes WHERE entry_id=?")->execute([$eid]);
    $p = __DIR__.'/../assets/uploads/fests/'.$fid.'/'.basename($entry['image_path']);
    if (file_exists($p)) unlink($p);
    $og = __DIR__.'/../assets/uploads/fests/'.$fid.'/og/'.basename($entry['og_path']);
    if (file_exists($og)) unlink($og);
    db()->prepare("DELETE FROM fest_entries WHERE id=?")->execute([$eid]);
    echo json_encode(['ok'=>true]); exit;
  }

  // Admin: toggle voting
  if ($act === 'toggle_voting' && $isAdmin) {
    $fid = (int)($_POST['fest_id'] ?? 0);
    $st  = db()->prepare("SELECT voting_open FROM fests WHERE id=?"); $st->execute([$fid]); $r=$st->fetch();
    if (!$r) { echo json_encode(['ok'=>false]); exit; }
    $new = $r['voting_open'] ? 0 : 1;
    db()->prepare("UPDATE fests SET voting_open=? WHERE id=?")->execute([$new,$fid]);
    echo json_encode(['ok'=>true,'open'=>(bool)$new]); exit;
  }

  // Admin: save/create fest
  if ($act === 'save_fest' && $isAdmin) {
    $fid   = (int)($_POST['fest_id'] ?? 0);
    $title = trim($_POST['title'] ?? '');
    if (!$title) { echo json_encode(['ok'=>false,'msg'=>'Title required']); exit; }
    $slug  = preg_replace('/[^a-z0-9]+/','-',strtolower($title)).'-'.time();
    $data  = [
      'title'       => $title,
      'description' => trim($_POST['description'] ?? ''),
      'prize_1'     => trim($_POST['prize_1'] ?? ''),
      'prize_2'     => trim($_POST['prize_2'] ?? ''),
      'prize_3'     => trim($_POST['prize_3'] ?? ''),
      'sponsor_name'=> trim($_POST['sponsor_name'] ?? ''),
      'join_link'   => trim($_POST['join_link'] ?? ''),
      'vote_start'  => !empty($_POST['vote_start']) ? $_POST['vote_start'].':00' : null,
      'vote_end'    => !empty($_POST['vote_end'])   ? $_POST['vote_end'].':00'   : null,
    ];

    // Handle poster upload
    $posterPath = '';
    if (!empty($_FILES['poster']['tmp_name'])) {
      $pf = $_FILES['poster'];
      $ext = strtolower(pathinfo($pf['name'],PATHINFO_EXTENSION));
      if (in_array($ext,['jpg','jpeg','png','webp']) && $pf['size'] < 8*1024*1024) {
        $dir = __DIR__.'/../assets/uploads/fests/posters/';
        if (!is_dir($dir)) mkdir($dir,0755,true);
        $fn = 'poster_'.time().'.'.$ext;
        if (move_uploaded_file($pf['tmp_name'],$dir.$fn)) $posterPath = $fn;
      }
    }

    // Handle sponsor logo upload
    $sponsorLogo = '';
    if (!empty($_FILES['sponsor_logo']['tmp_name'])) {
      $sf = $_FILES['sponsor_logo'];
      $ext2 = strtolower(pathinfo($sf['name'],PATHINFO_EXTENSION));
      if (in_array($ext2,['jpg','jpeg','png','webp']) && $sf['size'] < 2*1024*1024) {
        $dir2 = __DIR__.'/../assets/uploads/fests/sponsors/';
        if (!is_dir($dir2)) mkdir($dir2,0755,true);
        $fn2 = 'sponsor_'.time().'.'.$ext2;
        if (move_uploaded_file($sf['tmp_name'],$dir2.$fn2)) $sponsorLogo = $fn2;
      }
    }

    if ($fid) {
      // Update existing
      $st = db()->prepare("SELECT poster_path,sponsor_logo FROM fests WHERE id=?");
      $st->execute([$fid]); $old=$st->fetch();
      if (!$posterPath) $posterPath = $old['poster_path'] ?? '';
      if (!$sponsorLogo) $sponsorLogo = $old['sponsor_logo'] ?? '';
      db()->prepare("UPDATE fests SET title=?,description=?,prize_1=?,prize_2=?,prize_3=?,sponsor_name=?,sponsor_logo=?,join_link=?,vote_start=?,vote_end=?,poster_path=? WHERE id=?")
        ->execute([$data['title'],$data['description'],$data['prize_1'],$data['prize_2'],$data['prize_3'],$data['sponsor_name'],$sponsorLogo,$data['join_link'],$data['vote_start'],$data['vote_end'],$posterPath,$fid]);
      echo json_encode(['ok'=>true,'msg'=>'✅ Fest updated!','id'=>$fid]); exit;
    } else {
      // Create new
      db()->prepare("INSERT INTO fests(slug,title,description,prize_1,prize_2,prize_3,sponsor_name,sponsor_logo,join_link,vote_start,vote_end,poster_path,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)")
        ->execute([$slug,$data['title'],$data['description'],$data['prize_1'],$data['prize_2'],$data['prize_3'],$data['sponsor_name'],$sponsorLogo,$data['join_link'],$data['vote_start'],$data['vote_end'],$posterPath,$uid]);
      $newFid = db()->lastInsertId();
      echo json_encode(['ok'=>true,'msg'=>'✅ Fest created!','id'=>$newFid]); exit;
    }
  }

  // Admin: delete fest
  if ($act === 'delete_fest' && $isAdmin) {
    $fid = (int)($_POST['fest_id'] ?? 0);
    db()->prepare("DELETE FROM fest_likes WHERE fest_id=?")->execute([$fid]);
    db()->prepare("DELETE FROM fest_entries WHERE fest_id=?")->execute([$fid]);
    db()->prepare("DELETE FROM fests WHERE id=?")->execute([$fid]);
    echo json_encode(['ok'=>true]); exit;
  }

  echo json_encode(['ok'=>false,'msg'=>'Unknown']); exit;
}

// ── Entry upload ────────────────────────────────────────────
$uploadMsg = null;
if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_FILES['entry_photo']) && $festId) {
  $st = db()->prepare("SELECT * FROM fests WHERE id=? AND status='active'");
  $st->execute([$festId]); $fest=$st->fetch();
  if (!$fest) { $uploadMsg=['err','Fest not found.']; }
  else {
    $ck = db()->prepare("SELECT id FROM fest_entries WHERE fest_id=? AND member_id=?");
    $ck->execute([$festId,$uid]);
    if ($ck->fetch()) {
      $uploadMsg=['err','You already submitted. Delete first to re-upload.'];
    } else {
      $f   = $_FILES['entry_photo'];
      $ext = strtolower(pathinfo($f['name'],PATHINFO_EXTENSION));
      if (!in_array($ext,['jpg','jpeg','png','webp'])) {
        $uploadMsg=['err','JPG/PNG/WebP only.'];
      } elseif ($f['size']>6*1024*1024) {
        $uploadMsg=['err','Max 6MB.'];
      } else {
        $dir = __DIR__.'/../assets/uploads/fests/'.$festId.'/';
        if (!is_dir($dir)) mkdir($dir,0755,true);
        $fn = 'entry_'.time().'_'.mt_rand(1000,9999).'.'.$ext;
        if (move_uploaded_file($f['tmp_name'],$dir.$fn)) {
          $title2 = trim($_POST['entry_title']??'');
          $db2 = db()->prepare("INSERT INTO fest_entries(fest_id,member_id,image_path,title) VALUES(?,?,?,?)");
          $db2->execute([$festId,$uid,$fn,$title2]);
          $newEid = db()->lastInsertId();
          // Save og copy
          $ogDir = $dir.'og/';
          if (!is_dir($ogDir)) mkdir($ogDir,0755,true);
          $ogFn  = 'entry_'.$newEid.'.'.$ext;
          copy($dir.$fn, $ogDir.$ogFn);
          db()->prepare("UPDATE fest_entries SET og_path=? WHERE id=?")->execute([$ogFn,$newEid]);
          $uploadMsg=['ok','✅ Entry submitted!'];
        } else {
          $uploadMsg=['err','Upload failed.'];
        }
      }
    }
  }
}

// ── Load fests ──────────────────────────────────────────────
$allFests = db()->query("SELECT f.*,(SELECT COUNT(*) FROM fest_entries WHERE fest_id=f.id) cnt FROM fests ORDER BY created_at DESC")->fetchAll();

$pageTitle = '🎪 Fest Manager — '.$CLUB;
$pageOG = ['title'=>$pageTitle,'desc'=>'Club fests — '.$CLUB,'image'=>$SITE.'/og_image.php','url'=>$SITE.'/modules/fest_manager.php'];
require_once __DIR__.'/../includes/header.php';
?>
<style>
:root{--fm1:#0B1033;--fm2:#0A14E0;--gold:#f5a623}
.fm-wrap{max-width:580px;margin:0 auto;padding-bottom:4rem}
.fm-hero{background:linear-gradient(135deg,#0B1033,#0A14E0,#1A23C9);padding:1.6rem 1rem 1.2rem;text-align:center}
.fm-hero h1{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.44rem;color:#fff;letter-spacing:.01em;margin-bottom:.2rem}
.fm-hero p{font-size:.72rem;color:rgba(255,255,255,.6)}
.fest-card{background:#fff;margin:.6rem .8rem;border-radius:16px;overflow:hidden;box-shadow:0 3px 16px rgba(11,16,51,.1);border:1.5px solid rgba(11,16,51,.1);cursor:pointer;transition:all .15s}
.fest-card:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(11,16,51,.15)}
.fest-poster{width:100%;height:160px;object-fit:cover;display:block}
.fest-poster-placeholder{width:100%;height:160px;background:linear-gradient(135deg,#0B1033,#0A14E0);display:flex;align-items:center;justify-content:center;font-size:3rem}
.fest-info{padding:.75rem 1rem}
.fest-title{font-family:'Playfair Display',serif;font-size:1.1rem;font-weight:700;color:#0B1033;margin-bottom:.2rem}
.fest-meta{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin-bottom:.4rem}
.fest-badge{font-size:.62rem;font-weight:700;padding:.18rem .55rem;border-radius:20px;letter-spacing:.06em}
.badge-active{background:#ECEEFF;color:#1A23C9}
.badge-open{background:#e8f5e9;color:#2e7d32}
.badge-closed{background:#ffebee;color:#b71c1c}
.fest-actions{display:flex;gap:.4rem;padding:0 1rem .75rem}
.fb{padding:.42rem .85rem;border:none;border-radius:8px;font-size:.72rem;font-weight:700;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif}
.fb-enter{background:linear-gradient(135deg,#0B1033,#0A14E0);color:#fff;flex:1}
.fb-share{background:#25d366;color:#fff}
.fb-edit{background:#fff3e0;color:#e65100;border:1px solid #ffe0b2}
/* Entry grid */
.eg{display:grid;grid-template-columns:1fr 1fr;gap:.5rem;padding:.5rem .8rem}
.ec{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.08);border:1.5px solid #E3E7F5;position:relative;cursor:pointer}
.ec img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block}
.ec-info{padding:.4rem .5rem .5rem}
.ec-name{font-size:.7rem;font-weight:800;color:#0B1033}
.ec-likes{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;color:#e53935}
.like-btn{padding:.28rem .6rem;border:none;border-radius:7px;font-size:.68rem;font-weight:800;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif}
.like-can{background:linear-gradient(135deg,#e53935,#b71c1c);color:#fff}
.like-done{background:#fce4ec;color:#c62828}
.like-no{background:#f5f5f5;color:#666666}
/* Admin form */
.af{background:#fff;margin:.7rem .8rem;border-radius:16px;box-shadow:0 3px 16px rgba(11,16,51,.1);border:1.5px solid rgba(11,16,51,.1);overflow:hidden}
.af-head{background:linear-gradient(135deg,#0B1033,#0A14E0);padding:.75rem 1rem;display:flex;align-items:center;gap:.5rem}
.af-head h3{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#fff;margin:0}
.af-body{padding:1rem}
/* Upload area */
.upload-area{border:2px dashed rgba(11,16,51,.25);border-radius:12px;padding:1.2rem;text-align:center;cursor:pointer;background:#f8faff;transition:all .2s;margin-bottom:.5rem}
.upload-area:hover{border-color:#0A14E0;background:#ECEEFF}
/* Toast */
.fmtoast{position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%) translateY(40px);background:#0B1033;color:#fff;padding:.6rem 1.2rem;border-radius:25px;font-size:.8rem;font-weight:700;z-index:9999;opacity:0;transition:all .3s;white-space:nowrap}
.fmtoast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.fmtoast.ok{background:#2e7d32}
.fmtoast.err{background:#b71c1c}
/* Popup */
.fpopup{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:8000;align-items:flex-end;justify-content:center}
.fpopup-inner{background:#fff;width:100%;max-width:520px;border-radius:24px 24px 0 0;max-height:92vh;overflow-y:auto;animation:slideUp .3s ease}
@keyframes slideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
</style>

<div class="fm-wrap">
<div class="fm-hero">
  <h1>🎪 FEST MANAGER</h1>
  <p><?= h($CLUB) ?> · All events & competitions</p>
</div>

<?php if($isAdmin): ?>
<!-- Create new fest button -->
<div style="padding:.7rem .8rem .3rem;display:flex;justify-content:flex-end">
  <button onclick="openCreateFest()" style="background:linear-gradient(135deg,#0B1033,#0A14E0);color:#fff;border:none;border-radius:12px;padding:.55rem 1.1rem;font-weight:800;font-size:.8rem;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif;display:flex;align-items:center;gap:.4rem">
    ＋ Create New Fest
  </button>
</div>
<?php endif; ?>

<!-- Fest list -->
<?php if(empty($allFests)): ?>
<div style="text-align:center;padding:3rem 1rem;color:#5d6b80">
  <div style="font-size:3rem;margin-bottom:.6rem" aria-hidden="true">🎪</div>
  <p>No fests yet. <?= $isAdmin ? 'Create the first one!' : 'Check back soon!' ?></p>
</div>
<?php else: ?>
<?php foreach($allFests as $f): ?>
<div class="fest-card" onclick="openFest(<?= $f['id'] ?>)">
  <?php if($f['poster_path']): ?>
  <img class="fest-poster" src="<?= h(url('assets/uploads/fests/posters/'.basename($f['poster_path']))) ?>" alt="">
  <?php else: ?>
  <div class="fest-poster-placeholder">🎪</div>
  <?php endif; ?>
  <div class="fest-info">
    <div class="fest-title"><?= h($f['title']) ?></div>
    <div class="fest-meta">
      <span class="fest-badge badge-active"><?= (int)$f['cnt'] ?> entries</span>
      <?php if($f['voting_open']): ?>
      <span class="fest-badge badge-open">🗳️ Voting Open</span>
      <?php else: ?>
      <span class="fest-badge badge-closed">🔒 Voting Closed</span>
      <?php endif; ?>
      <?php if($f['sponsor_name']): ?>
      <span class="fest-badge" style="background:#fff3e0;color:#e65100">🏅 <?= h($f['sponsor_name']) ?></span>
      <?php endif; ?>
    </div>
    <?php if($f['description']): ?>
    <p style="font-size:.72rem;color:#64748b;margin:.2rem 0"><?= h(mb_substr($f['description'],0,80)) ?>...</p>
    <?php endif; ?>
  </div>
  <div class="fest-actions" onclick="event.stopPropagation()">
    <button class="fb fb-enter" onclick="openFest(<?= $f['id'] ?>)">🎪 Enter / View</button>
    <button class="fb fb-share" onclick="shareFest(<?= $f['id'] ?>, '<?= h(addslashes($f['title'])) ?>', '<?= $f['poster_path'] ? h($SITE.'/assets/uploads/fests/posters/'.basename($f['poster_path'])) : '' ?>')">💚</button>
    <?php if($isAdmin): ?>
    <button class="fb fb-edit" onclick="editFest(<?= $f['id'] ?>)">✏️</button>
    <?php endif; ?>
  </div>
</div>
<?php endforeach; ?>
<?php endif; ?>
</div>

<!-- Admin Create/Edit Form -->
<?php if($isAdmin): ?>
<div class="fpopup" id="festForm" onclick="if(event.target===this)closeFestForm()">
<div class="fpopup-inner">
  <div class="af-head" style="border-radius:0">
    <span>🎪</span>
    <h3 id="formTitle">CREATE NEW FEST</h3>
    <button onclick="closeFestForm()" style="margin-left:auto;background:rgba(255,255,255,.2);border:none;border-radius:50%;width:28px;height:28px;color:#fff;cursor:pointer;font-size:.9rem">✕</button>
  </div>
  <div class="af-body">
    <input type="hidden" id="edit_fest_id" value="">

    <div class="fg"><label class="lbl">Fest Title *</label>
      <input type="text" id="f_title" class="inp" placeholder="e.g. Eid Mehandi Fest 2026"></div>
    <div class="fg"><label class="lbl">Description</label>
      <textarea id="f_desc" class="inp" rows="2" placeholder="Short description..."></textarea></div>

    <!-- Poster upload -->
    <div class="fg"><label class="lbl">Event Poster</label>
      <div class="upload-area" onclick="document.getElementById('f_poster').click()">
        <div id="posterPreviewWrap" style="display:none"><img id="posterPreviewImg" style="max-height:120px;border-radius:8px;max-width:100%;margin-bottom:.4rem"></div>
        <div id="posterPlaceholder">🖼️ <strong>Tap to upload poster</strong><br><small>JPG/PNG · Max 8MB</small></div>
      </div>
      <input type="file" id="f_poster" accept="image/*" style="display:none" onchange="previewFestImage(this,'posterPreviewImg','posterPreviewWrap','posterPlaceholder')">
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">🥇 1st Prize</label><input type="text" id="f_p1" class="inp" placeholder="Prize description"></div>
      <div class="fg"><label class="lbl">🥈 2nd Prize</label><input type="text" id="f_p2" class="inp" placeholder="Prize description"></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">🥉 3rd Prize</label><input type="text" id="f_p3" class="inp" placeholder="Prize description"></div>
      <div class="fg"><label class="lbl">🏅 Sponsor Name</label><input type="text" id="f_sponsor" class="inp" placeholder="e.g. Blush Bee"></div>
    </div>

    <!-- Sponsor logo -->
    <div class="fg"><label class="lbl">Sponsor Logo (optional)</label>
      <div class="upload-area" onclick="document.getElementById('f_slogo').click()" style="padding:.7rem">
        <div id="slogoPreviewWrap" style="display:none"><img id="slogoPreviewImg" style="max-height:60px;border-radius:6px;margin-bottom:.3rem"></div>
        <div id="slogoPlaceholder">🏅 Tap to upload sponsor logo</div>
      </div>
      <input type="file" id="f_slogo" accept="image/*" style="display:none" onchange="previewFestImage(this,'slogoPreviewImg','slogoPreviewWrap','slogoPlaceholder')">
    </div>

    <div class="fg"><label class="lbl">WhatsApp Group Link</label>
      <input type="text" id="f_join" class="inp" placeholder="https://chat.whatsapp.com/..."></div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">⏰ Voting Starts</label><input type="datetime-local" id="f_vstart" class="inp"></div>
      <div class="fg"><label class="lbl">⏰ Voting Ends</label><input type="datetime-local" id="f_vend" class="inp"></div>
    </div>

    <button onclick="saveFest()" class="btn btn-block" style="background:linear-gradient(135deg,#0B1033,#0A14E0);color:#fff;margin-top:.3rem">
      💾 Save Fest
    </button>
    <div id="formMsg" style="text-align:center;padding:.5rem;font-size:.78rem;display:none"></div>
  </div>
</div>
</div>
<?php endif; ?>

<!-- Fest Detail Popup -->
<div class="fpopup" id="festDetailPopup" onclick="if(event.target===this)closeFestDetail()">
<div class="fpopup-inner" id="festDetailInner">
  <div style="text-align:center;padding:2rem;color:#94a3b8">Loading...</div>
</div>
</div>

<div class="fmtoast" id="fmToast"></div>

<script>
var SELF  = '<?= url('modules/fest_manager.php') ?>';
var CLUB  = <?= json_encode($CLUB) ?>;
var PLACE = <?= json_encode($PLACE) ?>;
var SITE  = <?= json_encode($SITE) ?>;
var IS_ADMIN = <?= $isAdmin ? 'true' : 'false' ?>;
var currentFestId = 0;

function toast(msg,type){
  var el=document.getElementById('fmToast');
  el.textContent=msg;
  el.className='fmtoast on'+(type==='ok'?' ok':type==='err'?' err':'');
  setTimeout(function(){el.className='fmtoast'},2800);
}

// ── Open Fest Detail ──────────────────────────────────────
function openFest(festId){
  currentFestId = festId;
  document.getElementById('festDetailPopup').style.display='flex';
  document.body.style.overflow='hidden';
  document.getElementById('festDetailInner').innerHTML='<div style="text-align:center;padding:2rem">⏳ Loading...</div>';
  loadFestDetail(festId);
}
function closeFestDetail(){
  document.getElementById('festDetailPopup').style.display='none';
  document.body.style.overflow='';
}

function loadFestDetail(festId){
  fetch(SITE+'/modules/fest_detail.php?id='+festId+'&uid=<?= $uid ?>')
    .then(function(r){return r.text();})
    .then(function(html){
      document.getElementById('festDetailInner').innerHTML=html;
    }).catch(function(){
      document.getElementById('festDetailInner').innerHTML='<div style="padding:2rem;text-align:center;color:#b71c1c">❌ Failed to load</div>';
    });
}

// ── Share Fest ────────────────────────────────────────────
function shareFest(id, title, posterUrl){
  var msg = '🎪 *'+title+'*\n📍 '+PLACE+'\n🏛️ '+CLUB+'\n\n👉 '+SITE+'/modules/fest_manager.php?view=fest&fest='+id;
  if(posterUrl){
    // Generate share card
    var canvas=document.createElement('canvas');
    canvas.width=800;canvas.height=800;
    var ctx=canvas.getContext('2d');
    var img=new Image();
    img.crossOrigin='anonymous';
    img.onload=function(){
      // Draw poster full
      ctx.drawImage(img,0,0,800,800);
      // Dark bar
      ctx.fillStyle='rgba(0,0,0,0.55)';
      ctx.fillRect(0,728,800,72);
      // Club name
      ctx.font='bold 26px DM Sans,sans-serif';
      ctx.fillStyle='#fff';
      ctx.textBaseline='middle';
      ctx.fillText(CLUB,20,752);
      ctx.font='18px DM Sans,sans-serif';
      ctx.fillStyle='rgba(255,255,255,0.7)';
      ctx.fillText('🎪 '+title+' · '+SITE,20,776);
      canvas.toBlob(function(blob){
        var file=new File([blob],'fest_'+id+'.jpg',{type:'image/jpeg'});
        if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){
          navigator.share({files:[file],text:msg});
        } else {
          var a=document.createElement('a');a.href=canvas.toDataURL();a.download='fest_'+id+'.jpg';a.click();
          setTimeout(function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');},600);
        }
      },'image/jpeg',0.92);
    };
    img.onerror=function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');};
    img.src=posterUrl;
  } else {
    window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');
  }
}

// ── Admin: Create/Edit Fest Form ──────────────────────────
function openCreateFest(){
  document.getElementById('edit_fest_id').value='';
  document.getElementById('formTitle').textContent='CREATE NEW FEST';
  document.getElementById('f_title').value='';
  document.getElementById('f_desc').value='';
  document.getElementById('f_p1').value='';
  document.getElementById('f_p2').value='';
  document.getElementById('f_p3').value='';
  document.getElementById('f_sponsor').value='';
  document.getElementById('f_join').value='';
  document.getElementById('f_vstart').value='';
  document.getElementById('f_vend').value='';
  document.getElementById('festForm').style.display='flex';
  document.body.style.overflow='hidden';
}

function editFest(id){
  // Load fest data via AJAX then populate form
  fetch(SITE+'/modules/fest_manager.php?get_fest='+id)
    .then(function(r){return r.json();})
    .then(function(d){
      document.getElementById('edit_fest_id').value=id;
      document.getElementById('formTitle').textContent='EDIT FEST';
      document.getElementById('f_title').value=d.title||'';
      document.getElementById('f_desc').value=d.description||'';
      document.getElementById('f_p1').value=d.prize_1||'';
      document.getElementById('f_p2').value=d.prize_2||'';
      document.getElementById('f_p3').value=d.prize_3||'';
      document.getElementById('f_sponsor').value=d.sponsor_name||'';
      document.getElementById('f_join').value=d.join_link||'';
      if(d.vote_start) document.getElementById('f_vstart').value=d.vote_start.slice(0,16);
      if(d.vote_end)   document.getElementById('f_vend').value=d.vote_end.slice(0,16);
      if(d.poster_path){
        document.getElementById('posterPreviewImg').src=SITE+'/assets/uploads/fests/posters/'+d.poster_path;
        document.getElementById('posterPreviewWrap').style.display='block';
        document.getElementById('posterPlaceholder').style.display='none';
      }
      document.getElementById('festForm').style.display='flex';
      document.body.style.overflow='hidden';
    });
}

function closeFestForm(){
  document.getElementById('festForm').style.display='none';
  document.body.style.overflow='';
}

function previewFestImage(input,imgId,wrapId,phId){
  if(!input.files||!input.files[0]) return;
  var r=new FileReader();
  r.onload=function(e){
    document.getElementById(imgId).src=e.target.result;
    document.getElementById(wrapId).style.display='block';
    document.getElementById(phId).style.display='none';
  };
  r.readAsDataURL(input.files[0]);
}

function saveFest(){
  var fd=new FormData();
  fd.append('action','save_fest');
  fd.append('fest_id',document.getElementById('edit_fest_id').value||'0');
  fd.append('title',document.getElementById('f_title').value);
  fd.append('description',document.getElementById('f_desc').value);
  fd.append('prize_1',document.getElementById('f_p1').value);
  fd.append('prize_2',document.getElementById('f_p2').value);
  fd.append('prize_3',document.getElementById('f_p3').value);
  fd.append('sponsor_name',document.getElementById('f_sponsor').value);
  fd.append('join_link',document.getElementById('f_join').value);
  fd.append('vote_start',document.getElementById('f_vstart').value||'');
  fd.append('vote_end',document.getElementById('f_vend').value||'');
  var pf=document.getElementById('f_poster');
  if(pf&&pf.files&&pf.files[0]) fd.append('poster',pf.files[0]);
  var sf=document.getElementById('f_slogo');
  if(sf&&sf.files&&sf.files[0]) fd.append('sponsor_logo',sf.files[0]);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      toast(res.msg,'ok');
      setTimeout(function(){location.reload();},1000);
    } else { toast(res.msg||'Error','err'); }
  });
}
</script>
<?php
// ── Get fest JSON for edit ──────────────────────────────────
if (isset($_GET['get_fest']) && $isAdmin) {
  header('Content-Type: application/json');
  $fid = (int)$_GET['get_fest'];
  $st  = db()->prepare("SELECT * FROM fests WHERE id=?"); $st->execute([$fid]);
  echo json_encode($st->fetch());
  exit;
}

require_once __DIR__.'/../includes/footer.php';
