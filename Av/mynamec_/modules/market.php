<?php
ini_set('display_errors', 0);
error_reporting(E_ALL);

$configFile = __DIR__ . '/../includes/config.php';
if (!file_exists($configFile)) { die("Config missing"); }
require_once $configFile;

if (!function_exists('db'))           { die("db() missing"); }
if (!function_exists('requireLogin')) { function requireLogin() { return true; } }
if (!function_exists('currentUser'))  { function currentUser() { return ['id'=>1,'name'=>'User','role'=>'user']; } }
if (!function_exists('isAdminRole'))  { function isAdminRole($r) { return false; } }
if (!function_exists('setting'))      { function setting($k,$d='') { return $d; } }
if (!function_exists('url'))          { function url($p) { return '/'.ltrim($p,'/'); } }
if (!function_exists('h'))            { function h($s) { return htmlspecialchars($s??'',ENT_QUOTES,'UTF-8'); } }

// Public page — login only required for posting/liking
$me      = function_exists('currentUser') ? currentUser() : null;
$isAdmin = ($me && function_exists('isAdminRole')) ? (isAdminRole($me['role'] ?? '') || isModuleAdmin('market', $me)) : false;
$uid     = $me ? (int)($me['id'] ?? 0) : 0;
$isLoggedIn = $uid > 0;
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$SITE    = defined('SITE_URL') ? rtrim(SITE_URL,'/') : '';
$SELF    = url('modules/market.php');

// ── Posting permission ───────────────────────────────────────
// Subscription requirement removed — any logged-in member can post.
$hasActiveSub = $isLoggedIn;

// ── Categories ───────────────────────────────────────────────
$CATS = [
  'cakes'     => ['🍰','Cakes & Bakery'],
  'food'      => ['🍲','Homemade Food'],
  'scrap'     => ['♻️','Scrap Items'],
  'electronics'=>['📱','Electronics'],
  'furniture' => ['🪑','Furniture'],
  'vehicles'  => ['🚗','Vehicles'],
  'rentals'   => ['🏠','Rentals'],
  'mehndi'    => ['✋','Mehndi Artist'],
  'beauty'    => ['💄','Beauty Services'],
  'repair'    => ['🔧','Repair Services'],
  'handmade'  => ['🎁','Handmade Products'],
  'jobs'      => ['💼','Jobs & Requirements'],
  'fashion'   => ['👕','Fashion'],
  'others'    => ['🛍️','Others'],
];

// ── Subcategories (per category) ─────────────────────────────
$SUBCATS = [
  'cakes'      => ['Birthday','Wedding','Cupcakes','Custom','Pastries'],
  'food'       => ['Veg','Non-Veg','Snacks','Pickles','Sweets','Catering'],
  'scrap'      => ['Metal','Plastic','Paper','E-Waste','Other'],
  'electronics'=> ['Mobile','Laptop','TV','Audio','Accessories','Other'],
  'furniture'  => ['Sofa','Bed','Table','Chair','Wardrobe','Other'],
  'vehicles'   => ['Car','Bike','Scooter','Auto','Cycle','Spare Parts'],
  'rentals'    => ['Hourly','Daily','Weekly','Monthly','Yearly'],
  'mehndi'     => ['Bridal','Party','Arabic','Simple'],
  'beauty'     => ['Bridal','Hair','Skin','Makeup','Spa'],
  'repair'     => ['Mobile','AC / Fridge','Plumbing','Electrical','Vehicle'],
  'handmade'   => ['Jewelry','Decor','Art','Gifts','Other'],
  'jobs'       => ['Full-Time','Part-Time','Daily Wage','Wanted','Freelance'],
  'fashion'    => ['Men','Women','Kids','Footwear','Accessories'],
  'others'     => [],
];

// ── Tables ───────────────────────────────────────────────────
try { db()->exec("CREATE TABLE IF NOT EXISTS market_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(200) NOT NULL,
  category VARCHAR(50) NOT NULL DEFAULT 'others',
  description TEXT DEFAULT '',
  price VARCHAR(100) DEFAULT '',
  location VARCHAR(200) DEFAULT '',
  whatsapp VARCHAR(20) DEFAULT '',
  instagram VARCHAR(100) DEFAULT '',
  status ENUM('pending','active','sold','inactive') DEFAULT 'pending',
  featured TINYINT(1) DEFAULT 0,
  views INT DEFAULT 0,
  shares INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

// Geo columns for Google Maps pin (safe if already present)
try { db()->exec("ALTER TABLE market_items ADD COLUMN IF NOT EXISTS lat DECIMAL(10,7) NULL, ADD COLUMN IF NOT EXISTS lng DECIMAL(10,7) NULL, ADD COLUMN IF NOT EXISTS subcategory VARCHAR(50) NULL"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS market_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  item_id INT NOT NULL,
  image_path VARCHAR(500) NOT NULL,
  sort_order TINYINT DEFAULT 0
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS market_favorites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  item_id INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY one_fav (user_id, item_id)
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS market_reports (
  id INT AUTO_INCREMENT PRIMARY KEY,
  item_id INT NOT NULL,
  user_id INT NOT NULL,
  reason VARCHAR(300) DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

// ── AJAX / POST handlers ─────────────────────────────────────
if (!empty($_POST['action'])) {
  header('Content-Type: application/json');
  $act = $_POST['action'];
  // Require login for all actions except 'shared' counter
  if (!$isLoggedIn && $act !== 'shared') {
    echo json_encode(['ok'=>false,'msg'=>'login_required']); exit;
  }

  // Toggle favorite
  if ($act === 'fav') {
    $iid = (int)($_POST['item_id'] ?? 0);
    $ck = db()->prepare("SELECT id FROM market_favorites WHERE user_id=? AND item_id=?");
    $ck->execute([$uid,$iid]);
    if ($ck->fetch()) {
      db()->prepare("DELETE FROM market_favorites WHERE user_id=? AND item_id=?")->execute([$uid,$iid]);
      echo json_encode(['ok'=>true,'faved'=>false]); exit;
    } else {
      db()->prepare("INSERT IGNORE INTO market_favorites(user_id,item_id) VALUES(?,?)")->execute([$uid,$iid]);
      echo json_encode(['ok'=>true,'faved'=>true]); exit;
    }
  }

  // Report post
  if ($act === 'report') {
    $iid = (int)($_POST['item_id'] ?? 0);
    $reason = trim($_POST['reason'] ?? '');
    $ck = db()->prepare("SELECT id FROM market_reports WHERE user_id=? AND item_id=?");
    $ck->execute([$uid,$iid]);
    if ($ck->fetch()) { echo json_encode(['ok'=>false,'msg'=>'Already reported']); exit; }
    db()->prepare("INSERT INTO market_reports(item_id,user_id,reason) VALUES(?,?,?)")->execute([$iid,$uid,$reason]);
    echo json_encode(['ok'=>true,'msg'=>'Reported. Admin will review.']); exit;
  }

  // Track share count
  if ($act === 'shared') {
    $iid = (int)($_POST['item_id'] ?? 0);
    db()->prepare("UPDATE market_items SET shares=shares+1 WHERE id=?")->execute([$iid]);
    echo json_encode(['ok'=>true]); exit;
  }

  // Delete item (owner or admin)
  if ($act === 'delete') {
    $iid = (int)($_POST['item_id'] ?? 0);
    $st = db()->prepare("SELECT * FROM market_items WHERE id=?");
    $st->execute([$iid]); $item = $st->fetch();
    if (!$item || ((int)$item['user_id'] !== $uid && !$isAdmin)) {
      echo json_encode(['ok'=>false,'msg'=>'Not allowed']); exit;
    }
    $imgs = db()->prepare("SELECT image_path FROM market_images WHERE item_id=?");
    $imgs->execute([$iid]);
    foreach ($imgs->fetchAll() as $img) {
      $p = __DIR__.'/../assets/uploads/market/'.$img['image_path'];
      if (file_exists($p)) @unlink($p);
    }
    db()->prepare("DELETE FROM market_images WHERE item_id=?")->execute([$iid]);
    db()->prepare("DELETE FROM market_favorites WHERE item_id=?")->execute([$iid]);
    db()->prepare("DELETE FROM market_reports WHERE item_id=?")->execute([$iid]);
    db()->prepare("DELETE FROM market_items WHERE id=?")->execute([$iid]);
    echo json_encode(['ok'=>true]); exit;
  }

  // Owner: share own active listing to the community feed
  if ($act === 'share_feed') {
    $iid = (int)($_POST['item_id'] ?? 0);
    $st = db()->prepare("SELECT user_id,status FROM market_items WHERE id=?");
    $st->execute([$iid]); $r = $st->fetch();
    if (!$r || ((int)$r['user_id'] !== $uid && !$isAdmin)) { echo json_encode(['ok'=>false,'msg'=>'Not allowed']); exit; }
    if ($r['status'] !== 'active') { echo json_encode(['ok'=>false,'msg'=>'Only active items can be shared']); exit; }
    $ffile = __DIR__.'/feed_hook.php';
    if (file_exists($ffile)) {
      require_once $ffile;
      if (function_exists('feed_add_market_post')) {
        $done = feed_add_market_post($iid);
        echo json_encode(['ok'=>true,'already'=>!$done,'msg'=>$done?'📰 Shared to Feed!':'Already shared earlier']); exit;
      }
    }
    echo json_encode(['ok'=>false,'msg'=>'Feed not available']); exit;
  }

  // Toggle status (owner)
  if ($act === 'setstatus') {
    $iid    = (int)($_POST['item_id'] ?? 0);
    $status = $_POST['status'] ?? '';
    if (!in_array($status,['active','sold','inactive'])) { echo json_encode(['ok'=>false]); exit; }
    $st = db()->prepare("SELECT user_id FROM market_items WHERE id=?");
    $st->execute([$iid]); $r = $st->fetch();
    if (!$r || ((int)$r['user_id'] !== $uid && !$isAdmin)) { echo json_encode(['ok'=>false]); exit; }
    db()->prepare("UPDATE market_items SET status=? WHERE id=?")->execute([$status,$iid]);
    echo json_encode(['ok'=>true,'status'=>$status]); exit;
  }

  // Admin: approve / feature / reject
  if ($act === 'admin_approve' && $isAdmin) {
    $iid = (int)($_POST['item_id'] ?? 0);
    db()->prepare("UPDATE market_items SET status='active' WHERE id=?")->execute([$iid]);
    $ffile = __DIR__.'/feed_hook.php';
    if (file_exists($ffile)) { require_once $ffile; if (function_exists('feed_add_market_post')) feed_add_market_post($iid); }
    echo json_encode(['ok'=>true]); exit;
  }
  if ($act === 'admin_feature' && $isAdmin) {
    $iid = (int)($_POST['item_id'] ?? 0);
    $st = db()->prepare("SELECT featured FROM market_items WHERE id=?");
    $st->execute([$iid]); $r = $st->fetch();
    $new = $r ? ($r['featured'] ? 0 : 1) : 1;
    db()->prepare("UPDATE market_items SET featured=? WHERE id=?")->execute([$new,$iid]);
    echo json_encode(['ok'=>true,'featured'=>(bool)$new]); exit;
  }
  if ($act === 'admin_reject' && $isAdmin) {
    $iid = (int)($_POST['item_id'] ?? 0);
    db()->prepare("UPDATE market_items SET status='inactive' WHERE id=?")->execute([$iid]);
    echo json_encode(['ok'=>true]); exit;
  }

  echo json_encode(['ok'=>false,'msg'=>'Unknown']); exit;
}

// ── VIEW COUNTER ─────────────────────────────────────────────
$viewId = (int)($_GET['view'] ?? 0);
if ($viewId) {
  db()->prepare("UPDATE market_items SET views=views+1 WHERE id=?")->execute([$viewId]);
  exit;
}

// ── THUMB URL for share ──────────────────────────────────────
if (isset($_GET['get_thumb'])) {
  header('Content-Type: application/json');
  $tid = (int)$_GET['get_thumb'];
  $st  = db()->prepare("SELECT image_path FROM market_images WHERE item_id=? ORDER BY sort_order LIMIT 1");
  $st->execute([$tid]); $row = $st->fetch();
  if ($row) {
    echo json_encode(['img' => $SITE.'/assets/uploads/market/'.$row['image_path']]);
  } else {
    echo json_encode(['img' => null]);
  }
  exit;
}

// ── HANDLE SAVE (new / edit) ─────────────────────────────────
$saveMsg = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['save_item'])) {
  if (!$isLoggedIn) {
    header('Location: '.url('login.php').'?redirect='.urlencode($_SERVER['REQUEST_URI'])); exit;
  }
  if (!$hasActiveSub) {
    $saveMsg = ['err', 'Active subscription required to post items. Please renew your membership.'];
    goto done_save;
  }
  $iid   = (int)($_POST['item_id'] ?? 0);
  $title = trim($_POST['title'] ?? '');
  $cat   = $_POST['category'] ?? 'others';
  $sub   = trim($_POST['subcategory'] ?? '');
  $desc  = trim($_POST['description'] ?? '');
  $price = trim($_POST['price'] ?? '');
  $loc   = trim($_POST['location'] ?? '');
  $lat   = ($_POST['lat'] ?? '') !== '' ? (float)$_POST['lat'] : null;
  $lng   = ($_POST['lng'] ?? '') !== '' ? (float)$_POST['lng'] : null;
  $wa    = preg_replace('/\D/','',$_POST['whatsapp']??'');
  $insta = trim($_POST['instagram'] ?? '');

  if (!$title) { $saveMsg=['err','Title is required']; }
  elseif (!array_key_exists($cat,$CATS)) { $cat='others'; }
  else {
    $allowedSubs = $SUBCATS[$cat] ?? [];
    if ($sub !== '' && !in_array($sub,$allowedSubs,true)) $sub='';
    if ($iid) {
      // Edit — verify ownership
      $own = db()->prepare("SELECT user_id FROM market_items WHERE id=?");
      $own->execute([$iid]); $own = $own->fetch();
      if (!$own || ((int)$own['user_id']!==$uid && !$isAdmin)) {
        $saveMsg=['err','Not allowed']; goto done_save;
      }
      db()->prepare("UPDATE market_items SET title=?,category=?,subcategory=?,description=?,price=?,location=?,lat=?,lng=?,whatsapp=?,instagram=?,updated_at=NOW() WHERE id=?")
         ->execute([$title,$cat,$sub,$desc,$price,$loc,$lat,$lng,$wa,$insta,$iid]);
    } else {
      // New post — pending until admin approves (or auto-active if admin)
      $initStatus = $isAdmin ? 'active' : 'pending';
      db()->prepare("INSERT INTO market_items(user_id,title,category,subcategory,description,price,location,lat,lng,whatsapp,instagram,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)")
         ->execute([$uid,$title,$cat,$sub,$desc,$price,$loc,$lat,$lng,$wa,$insta,$initStatus]);
      $iid = (int)db()->lastInsertId();
      $feed_publish_iid = ($initStatus === 'active') ? $iid : 0;
    }
    // Upload images (max 3)
    $existCount = (int)db()->query("SELECT COUNT(*) FROM market_images WHERE item_id={$iid}")->fetchColumn();
    $dir = __DIR__.'/../assets/uploads/market/';
    if (!is_dir($dir)) @mkdir($dir,0755,true);
    $uploaded = 0;
    for ($fi=1; $fi<=3; $fi++) {
      if ($existCount + $uploaded >= 3) break;
      $fk = 'image'.$fi;
      if (empty($_FILES[$fk]['tmp_name'])) continue;
      $f = $_FILES[$fk]; $ext = strtolower(pathinfo($f['name'],PATHINFO_EXTENSION));
      if (!in_array($ext,['jpg','jpeg','png','webp'])||$f['size']>8*1024*1024) continue;
      $fn = 'mkt_'.$iid.'_'.time().'_'.$fi.'.'.$ext;
      if (@move_uploaded_file($f['tmp_name'],$dir.$fn)) {
        db()->prepare("INSERT INTO market_images(item_id,image_path,sort_order) VALUES(?,?,?)")
           ->execute([$iid,$fn,$existCount+$uploaded]);
        $uploaded++;
      }
    }
    $saveMsg=['ok', $iid ? 'Post updated!' : ($isAdmin ? 'Post published!' : 'Post submitted for review!')];
    // Push to community feed once active (thumbnail now exists)
    if (!empty($feed_publish_iid)) {
        $ffile = __DIR__.'/feed_hook.php';
        if (file_exists($ffile)) { require_once $ffile; if (function_exists('feed_add_market_post')) feed_add_market_post($feed_publish_iid); }
    }
  }
  done_save:;
}

// ── Delete image ─────────────────────────────────────────────
if (isset($_GET['del_img'])) {
  $imgId = (int)$_GET['del_img'];
  $st = db()->prepare("SELECT mi.image_path, m.user_id FROM market_images mi JOIN market_items m ON m.id=mi.item_id WHERE mi.id=?");
  $st->execute([$imgId]); $r = $st->fetch();
  if ($r && ((int)$r['user_id']===$uid||$isAdmin)) {
    $p=__DIR__.'/../assets/uploads/market/'.$r['image_path'];
    if(file_exists($p))@unlink($p);
    db()->prepare("DELETE FROM market_images WHERE id=?")->execute([$imgId]);
  }
  header('Location: '.$_SERVER['HTTP_REFERER']); exit;
}

// ── Page routing ─────────────────────────────────────────────
$page   = $_GET['p'] ?? 'browse';  // browse | item | mine | new | edit | admin
$itemId = (int)($_GET['id'] ?? 0);
$editId = (int)($_GET['edit'] ?? 0);

if ($editId) { $page = 'edit'; $itemId = $editId; }
if (isset($_GET['new'])) $page = 'new';
// Guard: not logged in → redirect to login
if (($page==='new'||$page==='edit'||$page==='mine') && !$isLoggedIn) {
  header('Location: '.url('login.php').'?redirect='.urlencode($_SERVER['REQUEST_URI'])); exit;
}
// Guard: non-subscriber trying to post → show wall instead
if (($page==='new'||$page==='edit') && !$hasActiveSub) $page = 'sub_wall';
if (isset($_GET['mine'])) $page = 'mine';
if (isset($_GET['admin_panel']) && $isAdmin) $page = 'admin';

// Load item for detail/edit
$item = null; $itemImgs = [];
if (in_array($page,['item','edit']) && $itemId) {
  $st = db()->prepare("SELECT m.*,u.name seller_name,u.profile_photo seller_photo FROM market_items m JOIN users u ON u.id=m.user_id WHERE m.id=?");
  $st->execute([$itemId]); $item = $st->fetch();
  if ($item) {
    $itemImgs = db()->prepare("SELECT * FROM market_images WHERE item_id=? ORDER BY sort_order");
    $itemImgs->execute([$itemId]); $itemImgs = $itemImgs->fetchAll();
    // Increment view
    db()->prepare("UPDATE market_items SET views=views+1 WHERE id=?")->execute([$itemId]);
  }
}

// Browse: filters
$search   = trim($_GET['q'] ?? '');
$filterCat= $_GET['cat'] ?? '';
$filterSub= $_GET['sub'] ?? '';
$sort     = $_GET['sort'] ?? 'latest';
$filterStatus = $_GET['status'] ?? 'active';

$where = ["m.status IN ('active','sold')"];
$params = [];
if ($search) { $where[] = "(m.title LIKE ? OR m.description LIKE ?)"; $params[]="%$search%"; $params[]="%$search%"; }
if ($filterCat && array_key_exists($filterCat,$CATS)) { $where[] = "m.category=?"; $params[]=$filterCat; }
if ($filterSub !== '') { $where[] = "m.subcategory=?"; $params[]=$filterSub; }
$whereStr = implode(' AND ',$where);
$orderBy = match($sort) {
  'popular' => "m.status='sold' ASC, m.views DESC",
  'price_asc' => "m.status='sold' ASC, CAST(NULLIF(REGEXP_REPLACE(m.price,\"[^0-9.]\",\"\"),'') AS DECIMAL) ASC",
  'price_desc'=> "m.status='sold' ASC, CAST(NULLIF(REGEXP_REPLACE(m.price,\"[^0-9.]\",\"\"),'') AS DECIMAL) DESC",
  default   => "m.status='sold' ASC, m.featured DESC, m.created_at DESC",
};
$items = [];
try {
  $st = db()->prepare("SELECT m.*,u.name seller_name,u.profile_photo seller_photo,
    (SELECT image_path FROM market_images WHERE item_id=m.id ORDER BY sort_order LIMIT 1) thumb
    FROM market_items m JOIN users u ON u.id=m.user_id
    WHERE {$whereStr} ORDER BY {$orderBy} LIMIT 60");
  $st->execute($params); $items = $st->fetchAll();
} catch(Exception $e){}

// My items
$myItems = [];
if ($page === 'mine') {
  try {
    $myItems = db()->query("SELECT m.*,(SELECT image_path FROM market_images WHERE item_id=m.id ORDER BY sort_order LIMIT 1) thumb FROM market_items m WHERE m.user_id={$uid} ORDER BY m.created_at DESC")->fetchAll();
  } catch(Exception $e){}
}

// Favorites
$myFavIds = [];
try {
  $fst = db()->query("SELECT item_id FROM market_favorites WHERE user_id={$uid}");
  $myFavIds = array_column($fst->fetchAll(),'item_id');
} catch(Exception $e){}

// Admin pending
$pendingItems = [];
if ($isAdmin && $page === 'admin') {
  try {
    $pendingItems = db()->query("SELECT m.*,u.name seller_name,(SELECT image_path FROM market_images WHERE item_id=m.id LIMIT 1) thumb FROM market_items m JOIN users u ON u.id=m.user_id WHERE m.status='pending' ORDER BY m.created_at DESC")->fetchAll();
  } catch(Exception $e){}
}

$pageTitle = '🛍️ Mini Market — '.$CLUB;
require_once __DIR__.'/../includes/header.php';
?>
<style>
:root{--mk1:#1B5E20;--mk2:#2E7D32;--mk3:#4CAF50;--mkgold:#F9A825;--mkbg:#F1F8E9}
*{box-sizing:border-box}
.mkw{max-width:600px;margin:0 auto;padding-bottom:calc(5rem + env(safe-area-inset-bottom))}
/* Hero */
.mk-hero{background:linear-gradient(135deg,#1B5E20,#2E7D32 55%,#43A047);padding:.7rem 1rem}
.mk-hero-row{display:flex;align-items:center;gap:.6rem;max-width:600px;margin:0 auto}
.mk-hero-icon{font-size:1.7rem;line-height:1;flex-shrink:0}
.mk-hero-txt{flex:1;min-width:0}
.mk-hero h1{font-family:'Playfair Display',serif;font-size:1.15rem;color:#fff;margin:0;font-weight:700;line-height:1.1}
.mk-hero p{font-size:.6rem;color:rgba(255,255,255,.7);margin:0;letter-spacing:.05em}
.mk-hero-link{flex-shrink:0;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);color:#fff;text-decoration:none;font-size:.68rem;font-weight:800;padding:.35rem .7rem;border-radius:18px;white-space:nowrap}
.mk-tagline{display:none}
/* Top bar */
.mk-topbar{background:#fff;padding:.55rem .8rem;display:flex;gap:.45rem;align-items:center;box-shadow:0 1px 6px rgba(0,0,0,.06);position:sticky;top:0;z-index:100}
.mk-search{flex:1;padding:.55rem .9rem;border:none;background:#f1f3f6;border-radius:22px;font-size:.85rem;font-family:'Plus Jakarta Sans',sans-serif;outline:none;transition:box-shadow .15s}
.mk-search:focus{box-shadow:0 0 0 2px var(--mk3)}
.mk-post-btn{flex-shrink:0;background:linear-gradient(135deg,var(--mk1),var(--mk2));color:#fff;border:none;border-radius:22px;padding:.5rem 1rem;font-size:.78rem;font-weight:800;cursor:pointer;white-space:nowrap;font-family:'Plus Jakarta Sans',sans-serif;box-shadow:0 3px 10px rgba(27,94,32,.25)}
/* Categories scroll */
.mk-cats{display:flex;gap:.45rem;overflow-x:auto;padding:.6rem .7rem;background:#fff;border-bottom:1px solid #f0f0f0;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.mk-cats::-webkit-scrollbar{display:none}
.mk-cat{position:relative;flex-shrink:0;padding:.44rem .85rem;border-radius:20px;font-size:.72rem;font-weight:700;cursor:pointer;border:1.5px solid #eceff3;color:#566;background:#f5f7fa;font-family:'Plus Jakarta Sans',sans-serif;white-space:nowrap;text-decoration:none;display:flex;align-items:center;gap:.25rem;transition:transform .18s cubic-bezier(.34,1.56,.64,1),background .2s,color .2s,box-shadow .2s,border-color .2s;animation:catIn .4s both;will-change:transform}
.mk-cat:active{transform:scale(.91)}
.mk-cat:hover{border-color:#cfe3d0;background:#eef6ef;color:var(--mk1)}
.mk-cat.active{background:linear-gradient(135deg,var(--mk1),var(--mk3));color:#fff;border-color:transparent;box-shadow:0 5px 14px rgba(27,94,32,.32);transform:translateY(-1px)}
@keyframes catIn{from{opacity:0;transform:translateY(9px) scale(.95)}to{opacity:1;transform:none}}
.mk-cat:nth-child(1){animation-delay:.02s}.mk-cat:nth-child(2){animation-delay:.05s}.mk-cat:nth-child(3){animation-delay:.08s}.mk-cat:nth-child(4){animation-delay:.11s}.mk-cat:nth-child(5){animation-delay:.14s}.mk-cat:nth-child(6){animation-delay:.17s}.mk-cat:nth-child(7){animation-delay:.2s}.mk-cat:nth-child(8){animation-delay:.23s}.mk-cat:nth-child(n+9){animation-delay:.26s}
/* Subcategory filter bar (browse) */
.mk-subbar{display:flex;gap:.4rem;overflow-x:auto;padding:.15rem .7rem .55rem;background:#fff;border-bottom:1px solid #f0f0f0;scrollbar-width:none;animation:subIn .35s both}
.mk-subbar::-webkit-scrollbar{display:none}
@keyframes subIn{from{opacity:0;transform:translateY(-7px)}to{opacity:1;transform:none}}
.mk-subchip{flex-shrink:0;padding:.32rem .72rem;border-radius:14px;font-size:.66rem;font-weight:700;border:1.5px solid #e3eee4;background:#fff;color:#5a7a5c;cursor:pointer;text-decoration:none;white-space:nowrap;transition:transform .15s,background .2s,color .2s,box-shadow .2s}
.mk-subchip:active{transform:scale(.92)}
.mk-subchip.on{background:var(--mk2);color:#fff;border-color:transparent;box-shadow:0 3px 9px rgba(46,125,50,.3)}
/* Subcategory chips (post form) */
.sub-chips{display:flex;flex-wrap:wrap;gap:.4rem}
.sub-chip{padding:.44rem .82rem;border-radius:12px;font-size:.74rem;font-weight:700;border:1.5px solid #e0e0e0;background:#fff;color:#555;cursor:pointer;transition:transform .15s cubic-bezier(.34,1.56,.64,1),background .2s,color .2s,border-color .2s,box-shadow .2s;font-family:'Plus Jakarta Sans',sans-serif;animation:catIn .3s both}
.sub-chip:active{transform:scale(.9)}
.sub-chip.on{background:linear-gradient(135deg,var(--mk1),var(--mk2));color:#fff;border-color:transparent;box-shadow:0 4px 12px rgba(27,94,32,.3);transform:translateY(-1px)}
/* Sort bar */
.mk-sortbar{display:flex;gap:.3rem;padding:.4rem .7rem;background:#fff;border-bottom:1px solid #f0f0f0;overflow-x:auto;scrollbar-width:none;align-items:center}
.mk-sort{flex-shrink:0;padding:.26rem .6rem;border-radius:12px;font-size:.65rem;font-weight:700;cursor:pointer;border:none;color:#666666;background:transparent;font-family:'Plus Jakarta Sans',sans-serif;text-decoration:none}
.mk-sort.active{background:var(--mk2);color:#fff}
/* Cards grid */
.mk-grid{display:grid;grid-template-columns:1fr 1fr;gap:.55rem;padding:.6rem .55rem}
.mk-card{background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.08);border:1.5px solid #f0f0f0;cursor:pointer;position:relative;text-decoration:none;display:block;color:inherit}
.mk-card:active{transform:scale(.98)}
.mk-card-img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#f5f5f5}
.mk-card-img-placeholder{width:100%;aspect-ratio:1;background:linear-gradient(135deg,#e8f5e9,#f1f8e9);display:flex;align-items:center;justify-content:center;font-size:2.5rem}
.mk-badge{position:absolute;top:6px;left:6px;padding:.15rem .45rem;border-radius:20px;font-size:.55rem;font-weight:800;letter-spacing:.04em}
.badge-active{background:#e8f5e9;color:#2e7d32}
.badge-sold{background:#ffebee;color:#b71c1c}
.mk-card-sold .mk-card-img,.mk-card-sold .mk-card-img-placeholder{opacity:.55;filter:grayscale(.4)}
.mk-card-sold .mk-card-price{text-decoration:line-through;opacity:.6}
.badge-inactive{background:#f5f5f5;color:#666666}
.badge-pending{background:#fff3e0;color:#e65100}
.badge-featured{position:absolute;top:6px;right:6px;background:var(--mkgold);color:#000;padding:.15rem .4rem;border-radius:20px;font-size:.55rem;font-weight:800}
.mk-fav-btn{position:absolute;bottom:calc(50% + 4px);right:6px;background:rgba(255,255,255,.92);border:none;border-radius:50%;width:26px;height:26px;font-size:.8rem;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.15)}
.mk-card-body{padding:.45rem .5rem .55rem}
.mk-card-title{font-size:.75rem;font-weight:800;color:#1a1a1a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:.15rem}
.mk-card-price{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;color:var(--mk1);line-height:1;margin-bottom:.1rem}
.mk-card-price-free{font-size:.7rem;color:#2E7D32;font-weight:700}
.mk-card-meta{font-size:.58rem;color:#5d6b80;display:flex;align-items:center;gap:.3rem;flex-wrap:wrap}
.mk-card-seller{display:flex;align-items:center;gap:.3rem;margin-top:.3rem;padding-top:.3rem;border-top:1px solid #f5f5f5}
.mk-card-seller img{width:18px;height:18px;border-radius:50%;object-fit:cover}
.mk-card-seller-name{font-size:.6rem;color:#64748b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Item detail */
.mk-detail{max-width:600px;margin:0 auto}
.mk-slider{position:relative;background:#000;overflow:hidden}
.mk-slides{display:flex;transition:transform .3s ease}
.mk-slide{flex-shrink:0;width:100%}
.mk-slide img{width:100%;max-height:340px;object-fit:contain;display:block}
.mk-dots{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);display:flex;gap:.3rem}
.mk-dot{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.5);cursor:pointer}
.mk-dot.on{background:#fff}
.mk-slider-btn{position:absolute;top:50%;transform:translateY(-50%);background:rgba(0,0,0,.4);color:#fff;border:none;border-radius:50%;width:32px;height:32px;font-size:.9rem;cursor:pointer;z-index:5}
.mk-slider-btn.prev{left:6px}.mk-slider-btn.next{right:6px}
.mk-detail-body{padding:.9rem .9rem 0}
.mk-detail-title{font-family:'Playfair Display',serif;font-size:1.3rem;font-weight:700;color:#1a1a1a;margin-bottom:.25rem}
.mk-detail-price{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.44rem;color:var(--mk1);line-height:1;margin-bottom:.5rem}
.mk-detail-desc{font-size:.82rem;color:#444;line-height:1.6;margin-bottom:.8rem;white-space:pre-wrap}
.mk-info-row{display:flex;align-items:center;gap:.45rem;padding:.38rem 0;border-bottom:1px solid #f5f5f5;font-size:.78rem;color:#555}
.mk-info-icon{font-size:.9rem;flex-shrink:0;width:22px}
.mk-seller-box{background:var(--mkbg);border-radius:12px;padding:.7rem .8rem;margin:.8rem 0;display:flex;align-items:center;gap:.65rem;border:1.5px solid rgba(27,94,32,.15)}
.mk-action-btns{display:flex;flex-direction:column;gap:.45rem;padding:.8rem .9rem}
.btn-wa{background:linear-gradient(135deg,#25d366,#128c7e);color:#fff;border:none;border-radius:12px;padding:.65rem;font-size:.88rem;font-weight:800;cursor:pointer;width:100%;display:flex;align-items:center;justify-content:center;gap:.4rem;text-decoration:none}
.btn-insta{background:linear-gradient(135deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);color:#fff;border:none;border-radius:12px;padding:.55rem;font-size:.82rem;font-weight:700;cursor:pointer;width:100%;display:flex;align-items:center;justify-content:center;gap:.4rem;text-decoration:none}
.btn-share{background:#f1f8e9;color:var(--mk1);border:1.5px solid rgba(27,94,32,.2);border-radius:12px;padding:.55rem;font-size:.82rem;font-weight:700;cursor:pointer;width:100%;display:flex;align-items:center;justify-content:center;gap:.4rem}
.btn-fav-d{background:#fff;border:1.5px solid #e0e0e0;border-radius:12px;padding:.48rem;font-size:.82rem;font-weight:700;cursor:pointer;flex:1;display:flex;align-items:center;justify-content:center;gap:.3rem}
.btn-report{background:#fff;border:1px solid #ffcdd2;border-radius:12px;padding:.38rem;font-size:.72rem;color:#e53935;cursor:pointer;flex:1;display:flex;align-items:center;justify-content:center;gap:.3rem}
/* Form */
.mk-form{padding:.8rem}
.fg{margin-bottom:.75rem}
.lbl{display:block;font-size:.72rem;font-weight:700;color:#555;margin-bottom:.3rem}
.inp{width:100%;padding:.52rem .7rem;border:1.5px solid #e0e0e0;border-radius:10px;font-size:.82rem;font-family:'Plus Jakarta Sans',sans-serif;outline:none;background:#fff}
.inp:focus{border-color:var(--mk3)}
select.inp{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M6 8L1 3h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right .7rem center;padding-right:2rem}
textarea.inp{resize:vertical;min-height:90px}
.img-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-bottom:.5rem}
.img-slot{aspect-ratio:1;border:2px dashed #ddd;border-radius:10px;overflow:hidden;position:relative;background:#fafafa;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.5rem;color:#666666}
.img-slot img{width:100%;height:100%;object-fit:cover;position:absolute;inset:0}
.img-slot .del-img{position:absolute;top:3px;right:3px;background:rgba(183,28,28,.85);color:#fff;border:none;border-radius:50%;width:20px;height:20px;font-size:.6rem;cursor:pointer;display:flex;align-items:center;justify-content:center;z-index:5}
/* My items */
.mk-myitem{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.07);border:1.5px solid #f0f0f0;margin-bottom:.6rem;display:flex;gap:.5rem;overflow:hidden}
.mk-myitem-img{width:80px;height:80px;object-fit:cover;flex-shrink:0}
.mk-myitem-img-ph{width:80px;height:80px;background:var(--mkbg);display:flex;align-items:center;justify-content:center;font-size:1.8rem;flex-shrink:0}
.mk-myitem-body{flex:1;padding:.5rem .5rem .5rem 0;min-width:0}
.mk-myitem-title{font-size:.8rem;font-weight:800;color:#1a1a1a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:.2rem}
.mk-myitem-actions{display:flex;gap:.3rem;margin-top:.35rem;flex-wrap:wrap}
.mk-myitem-btn{padding:.22rem .5rem;border-radius:7px;font-size:.62rem;font-weight:700;cursor:pointer;border:1px solid #ddd;background:#fff;color:#555;font-family:'Plus Jakarta Sans',sans-serif}
/* Status badges */
.sb{padding:.18rem .55rem;border-radius:20px;font-size:.6rem;font-weight:800;display:inline-block}
.sb-active{background:#e8f5e9;color:#2e7d32}
.sb-sold{background:#ffebee;color:#b71c1c}
.sb-inactive{background:#f5f5f5;color:#666666}
.sb-pending{background:#fff3e0;color:#e65100}
/* Nav */
.mk-nav{display:flex;background:#fff;border-bottom:2px solid var(--mk3)}
.mk-nav-btn{flex:1;padding:.55rem .3rem;text-align:center;font-size:.65rem;font-weight:700;color:#666666;cursor:pointer;border:none;background:transparent;font-family:'Plus Jakarta Sans',sans-serif;border-bottom:2px solid transparent;margin-bottom:-2px}
.mk-nav-btn.active{color:var(--mk1);border-bottom-color:var(--mk1)}
/* Top sub-nav (under header) */
.mk-topnav{display:flex;background:#fff;border-bottom:1px solid #eef0f2;box-shadow:0 2px 6px rgba(0,0,0,.05)}
.mk-topnav .mk-nav-btn{text-decoration:none;color:#666666;line-height:1.25;border-top:2px solid transparent;border-bottom:none;margin:0;transition:color .2s,background .2s}
.mk-topnav .mk-nav-btn.active{color:var(--mk1);border-top-color:var(--mk1);background:#f4faf4}
.mk-topnav .mk-nav-btn:active{background:#eef6ef}
.mk-topnav .mk-nav-sell{color:#fff;background:linear-gradient(135deg,var(--mk1),var(--mk2))}
.mk-topnav .mk-nav-sell.active{color:#fff;background:linear-gradient(135deg,var(--mk1),var(--mk2));border-top-color:transparent}
/* Toast */
.toast{position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%) translateY(40px);background:var(--mk1);color:#fff;padding:.6rem 1.2rem;border-radius:25px;font-size:.8rem;font-weight:700;z-index:9999;opacity:0;transition:all .3s;white-space:nowrap;pointer-events:none}
.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.g{background:#2e7d32}.toast.e{background:#b71c1c}
/* Related */
.mk-related{padding:.6rem .55rem .2rem}
/* Admin */
.adm-card{background:#fff;border-radius:12px;border:1.5px solid #e0e0e0;padding:.7rem .8rem;margin-bottom:.5rem;display:flex;gap:.6rem;align-items:center}
.empty{text-align:center;padding:2.5rem 1rem;color:#5d6b80}
.back-btn{display:flex;align-items:center;gap:.3rem;padding:.5rem .8rem;font-size:.8rem;color:var(--mk1);font-weight:700;cursor:pointer;background:none;border:none;font-family:'Plus Jakarta Sans',sans-serif}
</style>

<div class="mkw">
<div class="mk-hero">
  <div class="mk-hero-row">
    <span class="mk-hero-icon">🛍️</span>
    <div class="mk-hero-txt">
      <h1>Mini Market</h1>
      <p>Buy • Sell • Connect</p>
    </div>
    <?php if($isLoggedIn): ?>
    <a href="<?php echo $SELF.'?mine'; ?>" class="mk-hero-link">My Listings</a>
    <?php endif; ?>
  </div>
</div>

<!-- Market sub-nav (top, under header) -->
<div class="mk-topnav">
  <a href="<?php echo $SELF; ?>" class="mk-nav-btn<?php echo $page==='browse'?' active':''; ?>">🛍️<br>Browse</a>
  <a href="<?php echo $isLoggedIn ? $SELF.'?mine' : url('login.php').'?redirect='.urlencode($SELF.'?mine'); ?>" class="mk-nav-btn<?php echo $page==='mine'?' active':''; ?>">📦<br>My Posts</a>
  <?php
  if(!$isLoggedIn){ $navSellHref=url('login.php').'?redirect='.urlencode($SELF.'?new'); $navSellIcon='🔑'; }
  else{ $navSellHref=$SELF.'?new'; $navSellIcon='＋'; }
  ?>
  <a href="<?php echo $navSellHref; ?>" class="mk-nav-btn mk-nav-sell<?php echo ($page==='new'||$page==='edit')?' active':''; ?>"><?php echo $navSellIcon; ?><br>Sell</a>
  <a href="<?php echo $SELF.'?p=browse&sort=popular'; ?>" class="mk-nav-btn<?php echo $sort==='popular'?' active':''; ?>">🔥<br>Top</a>
  <?php if($isAdmin): ?>
  <a href="<?php echo $SELF.'?admin_panel=1'; ?>" class="mk-nav-btn<?php echo $page==='admin'?' active':''; ?>">🛡️<br>Admin</a>
  <?php endif; ?>
</div>

<?php if ($saveMsg): ?>
<div style="padding:.55rem .9rem;font-size:.8rem;font-weight:700;<?php echo $saveMsg[0]==='ok'?'background:#e8f5e9;color:#2e7d32':'background:#ffebee;color:#b71c1c'; ?>">
  <?php echo $saveMsg[0]==='ok'?'✅':'❌'; ?> <?php echo h($saveMsg[1]); ?>
</div>
<?php endif; ?>

<?php // ─── ITEM DETAIL PAGE ───────────────────────────────────
if ($page==='item' && $item): ?>
<div class="mk-detail">
  <button onclick="history.back()" class="back-btn">← Back</button>

  <?php if(!empty($itemImgs)): ?>
  <div class="mk-slider" id="sldr">
    <div class="mk-slides" id="sldTrack">
      <?php foreach($itemImgs as $img): ?>
      <div class="mk-slide">
        <img src="<?php echo h($SITE.'/assets/uploads/market/'.$img['image_path']); ?>" loading="lazy">
      </div>
      <?php endforeach; ?>
    </div>
    <?php if(count($itemImgs)>1): ?>
    <button class="mk-slider-btn prev" onclick="slide(-1)">‹</button>
    <button class="mk-slider-btn next" onclick="slide(1)">›</button>
    <div class="mk-dots">
      <?php for($i=0;$i<count($itemImgs);$i++): ?>
      <div class="mk-dot<?php echo $i===0?' on':''; ?>" onclick="slideTo(<?php echo $i; ?>)" id="dot<?php echo $i; ?>"></div>
      <?php endfor; ?>
    </div>
    <?php endif; ?>
  </div>
  <?php else: ?>
  <div style="background:#e8f5e9;height:200px;display:flex;align-items:center;justify-content:center;font-size:4rem">
    <?php echo $CATS[$item['category']][0]??'🛍️'; ?>
  </div>
  <?php endif; ?>

  <div class="mk-detail-body">
    <?php
    $statusMap=['active'=>['badge-active','Active'],'sold'=>['badge-sold','Sold Out'],'inactive'=>['badge-inactive','Inactive'],'pending'=>['badge-pending','Pending']];
    $sc=$statusMap[$item['status']]??['badge-inactive','Unknown'];
    ?>
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem;margin-bottom:.4rem">
      <span class="mk-badge <?php echo $sc[0]; ?>" style="position:static;display:inline-block"><?php echo $sc[1]; ?></span>
      <?php if($item['featured']): ?><span style="background:var(--mkgold);color:#000;padding:.15rem .45rem;border-radius:20px;font-size:.55rem;font-weight:800">⭐ Featured</span><?php endif; ?>
    </div>
    <div class="mk-detail-title"><?php echo h($item['title']); ?></div>
    <?php if($item['price']): ?>
    <div class="mk-detail-price">₹<?php echo h($item['price']); ?></div>
    <?php else: ?>
    <div style="font-size:.75rem;color:#4CAF50;font-weight:700;margin-bottom:.5rem">Free / Price on request</div>
    <?php endif; ?>

    <?php if($item['description']): ?>
    <div class="mk-detail-desc"><?php echo h($item['description']); ?></div>
    <?php endif; ?>

    <?php
    $hasGeo = (isset($item['lat'],$item['lng']) && $item['lat']!==null && $item['lng']!==null && $item['lat']!=='' && $item['lng']!=='');
    if ($hasGeo) {
      $mapUrl = 'https://www.google.com/maps?q='.urlencode($item['lat'].','.$item['lng']);
    } elseif (!empty($item['location'])) {
      $mapUrl = 'https://www.google.com/maps/search/?api=1&query='.urlencode($item['location']);
    } else { $mapUrl=''; }
    $locLabel = $item['location'] ?: ($hasGeo ? 'View on map' : '');
    ?>
    <?php if($locLabel): ?>
    <a href="<?php echo h($mapUrl); ?>" target="_blank" rel="noopener" class="mk-info-row" style="text-decoration:none;color:#1A23C9">
      <span class="mk-info-icon">📍</span>
      <span style="flex:1"><?php echo h($locLabel); ?></span>
      <span style="font-size:.72rem;color:#1A23C9;font-weight:800">🗺️ Map ›</span>
    </a>
    <?php endif; ?>
    <div class="mk-info-row"><span class="mk-info-icon"><?php echo $CATS[$item['category']][0]??'🛍️'; ?></span><?php echo $CATS[$item['category']][1]??'Others'; ?><?php if(!empty($item['subcategory'])): ?> <span style="margin-left:.45rem;background:#e8f5e9;color:var(--mk1);padding:.12rem .5rem;border-radius:10px;font-size:.62rem;font-weight:800">🔖 <?php echo h($item['subcategory']); ?></span><?php endif; ?></div>
    <div class="mk-info-row"><span class="mk-info-icon">👁️</span><?php echo (int)$item['views']; ?> views · <?php echo (int)$item['shares']; ?> shares · <?php echo date('d M Y',strtotime($item['created_at'])); ?></div>

    <!-- Seller -->
    <div class="mk-seller-box">
      <?php $sph=$item['seller_photo']?$SITE.'/'.ltrim($item['seller_photo'],'/'):null; ?>
      <?php if($sph): ?><img src="<?php echo h($sph); ?>" style="width:42px;height:42px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid rgba(27,94,32,.2)"><?php else: ?><div style="width:42px;height:42px;border-radius:50%;background:rgba(27,94,32,.15);display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0">👤</div><?php endif; ?>
      <div style="flex:1;min-width:0">
        <div style="font-size:.82rem;font-weight:800;color:var(--mk1)"><?php echo h($item['seller_name']); ?></div>
        <div style="font-size:.62rem;color:#5d6b80">Seller</div>
      </div>
    </div>
  </div>

  <div class="mk-action-btns">
    <?php if($item['whatsapp']): ?>
    <?php $waMsg=urlencode("Hi, I saw your listing *{$item['title']}* on Mini Market ({$CLUB}). Is it still available?"); ?>
    <a href="https://wa.me/91<?php echo h($item['whatsapp']); ?>?text=<?php echo $waMsg; ?>" target="_blank" class="btn-wa">
      💬 WhatsApp Seller
    </a>
    <?php endif; ?>
    <?php if($item['instagram']): ?>
    <a href="https://instagram.com/<?php echo h(ltrim($item['instagram'],'@')); ?>" target="_blank" class="btn-insta">
      📸 Instagram
    </a>
    <?php endif; ?>

    <div style="display:flex;gap:.4rem">
      <button onclick="mkShare(<?php echo $itemId; ?>,'<?php echo h(addslashes($item['title'])); ?>')" class="btn-share" style="flex:1">🔗 Share</button>
      <button onclick="mkFav(<?php echo $itemId; ?>,this)" class="btn-fav-d" id="favBtn">
        <?php echo in_array($itemId,$myFavIds)?'❤️ Saved':'🤍 Save'; ?>
      </button>
    </div>

    <div style="display:flex;gap:.4rem">
      <?php if((int)$item['user_id']===$uid||$isAdmin): ?>
      <a href="<?php echo $SELF.'?edit='.$itemId; ?>" style="flex:1;padding:.42rem;background:#ECEEFF;color:#1A23C9;border:1px solid #D6DAFF;border-radius:10px;font-size:.75rem;font-weight:700;text-align:center;text-decoration:none">✏️ Edit</a>
      <?php endif; ?>
      <button onclick="mkReport(<?php echo $itemId; ?>)" class="btn-report" style="flex:<?php echo ((int)$item['user_id']===$uid||$isAdmin)?'1':'2'; ?>">⚑ Report</button>
    </div>

    <?php if($isAdmin): ?>
    <div style="background:#f8fafc;border-radius:10px;padding:.6rem;border:1px solid #e2e8f0">
      <div style="font-size:.7rem;font-weight:700;color:#64748b;margin-bottom:.4rem">🛡️ Admin Actions</div>
      <div style="display:flex;gap:.35rem;flex-wrap:wrap">
        <?php if($item['status']==='pending'): ?>
        <button onclick="adm('admin_approve',<?php echo $itemId; ?>,this)" style="background:#e8f5e9;color:#2e7d32;border:1px solid #c8e6c9;border-radius:8px;padding:.3rem .6rem;font-size:.7rem;font-weight:700;cursor:pointer">✅ Approve</button>
        <?php endif; ?>
        <button onclick="adm('admin_feature',<?php echo $itemId; ?>,this)" style="background:#fffde7;color:#f57f17;border:1px solid #fff176;border-radius:8px;padding:.3rem .6rem;font-size:.7rem;font-weight:700;cursor:pointer"><?php echo $item['featured']?'★ Unfeature':'⭐ Feature'; ?></button>
        <button onclick="adm('admin_reject',<?php echo $itemId; ?>,this)" style="background:#ffebee;color:#b71c1c;border:1px solid #ffcdd2;border-radius:8px;padding:.3rem .6rem;font-size:.7rem;font-weight:700;cursor:pointer">🚫 Reject</button>
      </div>
    </div>
    <?php endif; ?>
  </div>

  <!-- Related -->
  <?php
  $related=[];
  try {
    $rs=db()->prepare("SELECT m.*,(SELECT image_path FROM market_images WHERE item_id=m.id LIMIT 1) thumb FROM market_items m WHERE m.category=? AND m.id!=? AND m.status='active' ORDER BY RAND() LIMIT 4");
    $rs->execute([$item['category'],$itemId]); $related=$rs->fetchAll();
  } catch(Exception $e){}
  if(!empty($related)):
  ?>
  <div class="mk-related">
    <div style="font-family:'Playfair Display',serif;font-size:.9rem;font-weight:700;color:var(--mk1);margin-bottom:.5rem">🛍️ Similar Items</div>
    <div class="mk-grid" style="padding:0">
      <?php foreach($related as $ri): ?>
      <a href="<?php echo $SELF.'?p=item&id='.(int)$ri['id']; ?>" class="mk-card">
        <?php if($ri['thumb']): ?>
        <img class="mk-card-img" src="<?php echo h($SITE.'/assets/uploads/market/'.$ri['thumb']); ?>" loading="lazy">
        <?php else: ?>
        <div class="mk-card-img-placeholder"><?php echo $CATS[$ri['category']][0]??'🛍️'; ?></div>
        <?php endif; ?>
        <div class="mk-card-body">
          <div class="mk-card-title"><?php echo h($ri['title']); ?></div>
          <?php if($ri['price']): ?><div class="mk-card-price">₹<?php echo h($ri['price']); ?></div><?php else: ?><div class="mk-card-price-free">Free</div><?php endif; ?>
        </div>
      </a>
      <?php endforeach; ?>
    </div>
  </div>
  <?php endif; ?>
</div>

<?php // ─── NEW / EDIT POST FORM ───────────────────────────────
elseif ($page==='new' || $page==='edit'):
  $fi = ($page==='edit'&&$item) ? $item : null;
  $existImgs = $fi ? $itemImgs : [];
?>
<div style="background:linear-gradient(135deg,var(--mk1),var(--mk2));padding:.65rem .9rem;display:flex;align-items:center;gap:.5rem">
  <button onclick="history.back()" style="background:rgba(255,255,255,.2);border:none;border-radius:50%;width:28px;height:28px;color:#fff;cursor:pointer">←</button>
  <span style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#fff"><?php echo $fi?'EDIT POST':'NEW POST'; ?></span>
</div>
<form method="POST" enctype="multipart/form-data" class="mk-form">
  <input type="hidden" name="save_item" value="1">
  <input type="hidden" name="item_id" value="<?php echo $fi?(int)$fi['id']:0; ?>">

  <div class="fg">
    <label class="lbl">📝 Title *</label>
    <input type="text" name="title" class="inp" value="<?php echo h($fi['title']??''); ?>" placeholder="e.g. Homemade Chocolate Cake" required>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
    <div class="fg">
      <label class="lbl">🏷️ Category *</label>
      <select name="category" id="catSel" class="inp" onchange="updateSubcats()">
        <?php foreach($CATS as $k=>$v): ?>
        <option value="<?php echo $k; ?>" <?php echo ($fi['category']??'others')===$k?'selected':''; ?>><?php echo $v[0].' '.$v[1]; ?></option>
        <?php endforeach; ?>
      </select>
    </div>
    <div class="fg">
      <label class="lbl">💰 Price (optional)</label>
      <input type="text" name="price" class="inp" value="<?php echo h($fi['price']??''); ?>" placeholder="₹500 or Free">
    </div>
  </div>

  <div class="fg" id="subWrap" style="display:none">
    <label class="lbl">🔖 Type / Option</label>
    <input type="hidden" name="subcategory" id="subVal" value="<?php echo h($fi['subcategory']??''); ?>">
    <div id="subChips" class="sub-chips"></div>
  </div>

  <div class="fg">
    <label class="lbl">📄 Description</label>
    <textarea name="description" class="inp" placeholder="Describe your item or service..."><?php echo h($fi['description']??''); ?></textarea>
  </div>

  <div class="fg">
    <label class="lbl">📍 Location (optional)</label>
    <input type="text" name="location" id="locInput" class="inp" value="<?php echo h($fi['location']??''); ?>" placeholder="e.g. Vettikkattiri">
    <input type="hidden" name="lat" id="locLat" value="<?php echo h($fi['lat']??''); ?>">
    <input type="hidden" name="lng" id="locLng" value="<?php echo h($fi['lng']??''); ?>">
    <div style="display:flex;gap:.4rem;margin-top:.45rem">
      <button type="button" onclick="useMyLocation(this)" style="flex:1;padding:.5rem;background:#e8f5e9;color:var(--mk1);border:1.5px solid #c8e6c9;border-radius:10px;font-size:.74rem;font-weight:800;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif">📡 Use My Location</button>
      <button type="button" onclick="pickOnMap()" style="flex:1;padding:.5rem;background:#ECEEFF;color:#1A23C9;border:1.5px solid #D6DAFF;border-radius:10px;font-size:.74rem;font-weight:800;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif">🗺️ Pick on Map</button>
    </div>
    <div id="locStatus" style="font-size:.64rem;color:#5d6b80;margin-top:.35rem"><?php echo (isset($fi['lat'])&&$fi['lat']!==null&&$fi['lat']!=='')?'📍 GPS pin saved — buyers can open it in Google Maps.':'Tap “Use My Location” to attach a Google Maps pin.'; ?></div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
    <div class="fg">
      <label class="lbl">💬 WhatsApp Number</label>
      <input type="tel" name="whatsapp" class="inp" value="<?php echo h($fi['whatsapp']??''); ?>" placeholder="9876543210">
    </div>
    <div class="fg">
      <label class="lbl">📸 Instagram ID</label>
      <input type="text" name="instagram" class="inp" value="<?php echo h(ltrim($fi['instagram']??'','@')); ?>" placeholder="@username">
    </div>
  </div>

  <div class="fg">
    <label class="lbl">🖼️ Photos (Max 3)</label>
    <?php if(!empty($existImgs)): ?>
    <div class="img-grid" style="margin-bottom:.5rem">
      <?php foreach($existImgs as $ei): ?>
      <div class="img-slot">
        <img src="<?php echo h($SITE.'/assets/uploads/market/'.$ei['image_path']); ?>">
        <a href="<?php echo $SELF.'?del_img='.(int)$ei['id'].'&edit='.$itemId; ?>" class="del-img" onclick="return confirm('Remove this photo?')">✕</a>
      </div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
    <?php $slots = max(0,3-count($existImgs)); ?>
    <?php if($slots>0): ?>
    <div class="img-grid">
      <?php for($s=1;$s<=$slots;$s++): ?>
      <div class="img-slot" onclick="document.getElementById('fi<?php echo $s; ?>').click()">
        <div id="fip<?php echo $s; ?>" style="display:none"><img id="fii<?php echo $s; ?>" style="width:100%;height:100%;object-fit:cover;position:absolute;inset:0"></div>
        <span id="fih<?php echo $s; ?>">＋</span>
        <input type="file" id="fi<?php echo $s; ?>" name="image<?php echo $s; ?>" accept="image/*" style="display:none" onchange="prevImg(this,<?php echo $s; ?>)">
      </div>
      <?php endfor; ?>
    </div>
    <div style="font-size:.62rem;color:#5d6b80;margin-top:.3rem"><?php echo $slots; ?> slot<?php echo $slots>1?'s':''; ?> available · JPG/PNG/WebP · Max 8MB each</div>
    <?php endif; ?>
  </div>

  <button type="submit" style="width:100%;padding:.7rem;background:linear-gradient(135deg,var(--mk1),var(--mk2));color:#fff;border:none;border-radius:12px;font-weight:800;font-size:.9rem;cursor:pointer;margin-top:.3rem">
    <?php echo $fi?'💾 Update Post':'🛍️ '.($isAdmin?'Publish Post':'Submit for Review'); ?>
  </button>
</form>

<?php // ─── SUBSCRIPTION WALL ─────────────────────────────────
elseif ($page==='sub_wall'): ?>
<div style="background:linear-gradient(135deg,#b71c1c,#c62828);padding:.65rem .9rem;display:flex;align-items:center;gap:.5rem">
  <button onclick="history.back()" style="background:rgba(255,255,255,.2);border:none;border-radius:50%;width:28px;height:28px;color:#fff;cursor:pointer">←</button>
  <span style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#fff">🔒 SUBSCRIPTION REQUIRED</span>
</div>
<div style="padding:2rem 1.2rem;text-align:center">
  <div style="font-size:3.5rem;margin-bottom:.8rem">🛍️</div>
  <div style="font-family:'Playfair Display',serif;font-size:1.3rem;font-weight:700;color:#b71c1c;margin-bottom:.5rem">Subscribers Only</div>
  <div style="font-size:.85rem;color:#555;line-height:1.6;margin-bottom:1.2rem">
    Posting items on <strong>Mini Market</strong> is exclusive to active club members.<br>Renew your subscription to start selling!
  </div>
  <div style="background:#fff8f0;border:1.5px solid #ffcc80;border-radius:14px;padding:1rem;margin-bottom:1.2rem;text-align:left">
    <div style="font-size:.78rem;font-weight:700;color:#e65100;margin-bottom:.5rem">✅ With active subscription you can:</div>
    <div style="font-size:.75rem;color:#555;line-height:1.9">
      🛍️ Post items to sell or give away<br>
      🔧 Offer your services to members<br>
      📢 Post requirements &amp; wanted items<br>
      💬 Connect via WhatsApp &amp; Instagram<br>
      ⭐ Get featured on homepage
    </div>
  </div>
  <a href="<?php echo url('modules/subscription.php'); ?>" style="display:block;padding:.75rem;background:linear-gradient(135deg,#1B5E20,#2E7D32);color:#fff;border-radius:14px;font-weight:800;font-size:.95rem;text-decoration:none;box-shadow:0 4px 16px rgba(27,94,32,.3);margin-bottom:.6rem">
    💳 Subscribe Now
  </a>
  <a href="<?php echo $SELF; ?>" style="display:block;font-size:.78rem;color:#94a3b8;text-decoration:none">← Browse Market</a>
</div>

<?php // ─── MY ITEMS ───────────────────────────────────────────
elseif ($page==='mine'):
$grps = ['active'=>[],'pending'=>[],'sold'=>[],'inactive'=>[]];
foreach($myItems as $mi) { $grps[$mi['status']??'inactive'][] = $mi; }
?>
<div style="background:linear-gradient(135deg,var(--mk1),var(--mk2));padding:.65rem .9rem;display:flex;align-items:center;justify-content:space-between">
  <span style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#fff">MY ITEMS</span>
  <?php if($hasActiveSub): ?>
  <a href="<?php echo $SELF.'?new'; ?>" style="background:rgba(255,255,255,.2);color:#fff;border:none;border-radius:20px;padding:.3rem .75rem;font-size:.72rem;font-weight:800;text-decoration:none">＋ New Post</a>
  <?php else: ?>
  <a href="<?php echo $SELF.'?sub_wall=1'; ?>" style="background:rgba(183,28,28,.6);color:#fff;border:none;border-radius:20px;padding:.3rem .75rem;font-size:.72rem;font-weight:800;text-decoration:none">🔒 Subscribe to Post</a>
  <?php endif; ?>
</div>
<div style="padding:.7rem .7rem .3rem">
<?php if(empty($myItems)): ?>
<div class="empty">
  <div style="font-size:2.5rem;margin-bottom:.5rem">🛍️</div>
  <p>No posts yet.</p>
  <a href="<?php echo $SELF.'?new'; ?>" style="display:inline-block;margin-top:.5rem;background:var(--mk1);color:#fff;padding:.5rem 1.2rem;border-radius:20px;font-size:.8rem;font-weight:800;text-decoration:none">＋ Create First Post</a>
</div>
<?php else:
  $grpLabels=['active'=>'✅ Active','pending'=>'⏳ Pending Review','sold'=>'💰 Sold','inactive'=>'⏸️ Inactive'];
  foreach($grpLabels as $gk=>$gl):
    if(empty($grps[$gk])) continue;
?>
<div style="font-size:.72rem;font-weight:800;color:var(--mk1);margin:.6rem 0 .35rem;letter-spacing:.04em"><?php echo $gl; ?> (<?php echo count($grps[$gk]); ?>)</div>
<?php foreach($grps[$gk] as $mi):
  $catEm=$CATS[$mi['category']][0]??'🛍️';
  $miImg=$mi['thumb']?$SITE.'/assets/uploads/market/'.$mi['thumb']:null;
?>
<div class="mk-myitem">
  <?php if($miImg): ?>
  <img class="mk-myitem-img" src="<?php echo h($miImg); ?>">
  <?php else: ?>
  <div class="mk-myitem-img-ph"><?php echo $catEm; ?></div>
  <?php endif; ?>
  <div class="mk-myitem-body">
    <div class="mk-myitem-title"><?php echo h($mi['title']); ?></div>
    <div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.15rem">
      <span class="sb sb-<?php echo $mi['status']; ?>"><?php echo ucfirst($mi['status']); ?></span>
      <?php if($mi['price']): ?><span style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.72rem;color:var(--mk1)">₹<?php echo h($mi['price']); ?></span><?php endif; ?>
    </div>
    <div style="font-size:.58rem;color:#5d6b80">👁 <?php echo (int)$mi['views']; ?> views · <?php echo date('d M',strtotime($mi['created_at'])); ?></div>
    <div class="mk-myitem-actions">
      <a href="<?php echo $SELF.'?p=item&id='.(int)$mi['id']; ?>" class="mk-myitem-btn">👁 View</a>
      <a href="<?php echo $SELF.'?edit='.(int)$mi['id']; ?>" class="mk-myitem-btn" style="color:#1A23C9;border-color:#D6DAFF">✏️ Edit</a>
      <?php if($mi['status']==='active'): ?>
      <button onclick="shareToFeed(<?php echo (int)$mi['id']; ?>,this)" class="mk-myitem-btn" style="color:#01579b;border-color:#81d4fa">📰 Share to Feed</button>
      <?php endif; ?>
      <?php if($mi['status']!=='sold'): ?>
      <button onclick="setStatus(<?php echo (int)$mi['id']; ?>,'sold',this)" class="mk-myitem-btn" style="color:#b71c1c;border-color:#ffcdd2">💰 Sold</button>
      <?php endif; ?>
      <?php if($mi['status']==='active'): ?>
      <button onclick="setStatus(<?php echo (int)$mi['id']; ?>,'inactive',this)" class="mk-myitem-btn">⏸️ Hide</button>
      <?php elseif($mi['status']==='inactive'||$mi['status']==='sold'): ?>
      <button onclick="setStatus(<?php echo (int)$mi['id']; ?>,'active',this)" class="mk-myitem-btn" style="color:#2e7d32;border-color:#c8e6c9">▶️ Activate</button>
      <?php endif; ?>
      <button onclick="mkDel(<?php echo (int)$mi['id']; ?>)" class="mk-myitem-btn" style="color:#b71c1c;border-color:#ffcdd2">🗑️</button>
    </div>
  </div>
</div>
<?php endforeach; endforeach; endif; ?>
</div>

<?php // ─── ADMIN PANEL ────────────────────────────────────────
elseif ($page==='admin' && $isAdmin):
$allStats=[];
try {
  $allStats['total']=(int)db()->query("SELECT COUNT(*) FROM market_items")->fetchColumn();
  $allStats['active']=(int)db()->query("SELECT COUNT(*) FROM market_items WHERE status='active'")->fetchColumn();
  $allStats['pending']=(int)db()->query("SELECT COUNT(*) FROM market_items WHERE status='pending'")->fetchColumn();
  $allStats['sellers']=(int)db()->query("SELECT COUNT(DISTINCT user_id) FROM market_items WHERE status='active'")->fetchColumn();
} catch(Exception $e){}
$allAdmItems=[];
try { $allAdmItems=db()->query("SELECT m.*,u.name seller_name,(SELECT image_path FROM market_images WHERE item_id=m.id LIMIT 1) thumb FROM market_items m JOIN users u ON u.id=m.user_id ORDER BY m.created_at DESC LIMIT 50")->fetchAll(); } catch(Exception $e){}
?>
<div style="background:linear-gradient(135deg,#0B1033,#0A14E0);padding:.65rem .9rem">
  <span style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#fff">🛡️ ADMIN — MINI MARKET</span>
</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);background:#fff;border-bottom:2px solid #e0e0e0">
  <?php foreach(['total'=>['📦','Total'],'active'=>['✅','Active'],'pending'=>['⏳','Pending'],'sellers'=>['👤','Sellers']] as $sk=>$sv): ?>
  <div style="padding:.55rem .3rem;text-align:center;border-right:1px solid #f0f0f0">
    <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.04rem;color:var(--mk1)"><?php echo $allStats[$sk]??0; ?></div>
    <div style="font-size:.55rem;color:#5d6b80"><?php echo $sv[1]; ?></div>
  </div>
  <?php endforeach; ?>
</div>
<div style="padding:.7rem .7rem .3rem">
<?php if(!empty($pendingItems)): ?>
<div style="font-size:.72rem;font-weight:800;color:#e65100;margin-bottom:.4rem">⏳ PENDING APPROVAL (<?php echo count($pendingItems); ?>)</div>
<?php foreach($pendingItems as $pi): ?>
<div class="adm-card">
  <?php if($pi['thumb']): ?><img src="<?php echo h($SITE.'/assets/uploads/market/'.$pi['thumb']); ?>" style="width:56px;height:56px;border-radius:8px;object-fit:cover;flex-shrink:0"><?php else: ?><div style="width:56px;height:56px;border-radius:8px;background:var(--mkbg);display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0"><?php echo $CATS[$pi['category']][0]??'🛍️'; ?></div><?php endif; ?>
  <div style="flex:1;min-width:0">
    <div style="font-size:.8rem;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><?php echo h($pi['title']); ?></div>
    <div style="font-size:.65rem;color:#5d6b80"><?php echo h($pi['seller_name']); ?> · <?php echo $CATS[$pi['category']][1]??'Others'; ?></div>
    <div style="display:flex;gap:.3rem;margin-top:.35rem">
      <button onclick="adm('admin_approve',<?php echo (int)$pi['id']; ?>,this)" style="background:#e8f5e9;color:#2e7d32;border:1px solid #c8e6c9;border-radius:7px;padding:.25rem .55rem;font-size:.65rem;font-weight:700;cursor:pointer">✅ Approve</button>
      <a href="<?php echo $SELF.'?p=item&id='.(int)$pi['id']; ?>" style="background:#ECEEFF;color:#1A23C9;border:1px solid #D6DAFF;border-radius:7px;padding:.25rem .55rem;font-size:.65rem;font-weight:700;text-decoration:none">👁 View</a>
      <button onclick="adm('admin_reject',<?php echo (int)$pi['id']; ?>,this)" style="background:#ffebee;color:#b71c1c;border:1px solid #ffcdd2;border-radius:7px;padding:.25rem .55rem;font-size:.65rem;font-weight:700;cursor:pointer">🚫 Reject</button>
    </div>
  </div>
</div>
<?php endforeach; endif; ?>

<div style="font-size:.72rem;font-weight:800;color:#555;margin:.7rem 0 .4rem">ALL POSTS</div>
<?php foreach($allAdmItems as $ai): ?>
<div class="adm-card">
  <?php if($ai['thumb']): ?><img src="<?php echo h($SITE.'/assets/uploads/market/'.$ai['thumb']); ?>" style="width:44px;height:44px;border-radius:8px;object-fit:cover;flex-shrink:0"><?php else: ?><div style="width:44px;height:44px;border-radius:8px;background:var(--mkbg);display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0"><?php echo $CATS[$ai['category']][0]??'🛍️'; ?></div><?php endif; ?>
  <div style="flex:1;min-width:0">
    <div style="font-size:.75rem;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><?php echo h($ai['title']); ?></div>
    <div style="font-size:.6rem;color:#5d6b80"><?php echo h($ai['seller_name']); ?> · <span class="sb sb-<?php echo $ai['status']; ?>"><?php echo ucfirst($ai['status']); ?></span></div>
  </div>
  <div style="display:flex;gap:.25rem;flex-shrink:0">
    <a href="<?php echo $SELF.'?p=item&id='.(int)$ai['id']; ?>" style="background:#f5f5f5;border:none;border-radius:7px;padding:.28rem .5rem;font-size:.65rem;color:#555;text-decoration:none">👁</a>
    <button onclick="adm('admin_feature',<?php echo (int)$ai['id']; ?>,this)" style="background:#fffde7;border:none;border-radius:7px;padding:.28rem .5rem;font-size:.65rem;cursor:pointer" title="Feature"><?php echo $ai['featured']?'★':'☆'; ?></button>
    <button onclick="mkDel(<?php echo (int)$ai['id']; ?>)" style="background:#ffebee;border:none;border-radius:7px;padding:.28rem .5rem;font-size:.65rem;color:#b71c1c;cursor:pointer">🗑️</button>
  </div>
</div>
<?php endforeach; ?>
</div>

<?php // ─── BROWSE (default) ───────────────────────────────────
else: ?>

<div class="mk-topbar">
  <input class="mk-search" type="search" placeholder="🔍 Search items..." value="<?php echo h($search); ?>" onkeydown="if(event.key==='Enter')doSearch(this.value)">
  <?php if(!$isLoggedIn): ?>
  <button class="mk-post-btn" onclick="window.location='<?php echo url('login.php').'?redirect='.urlencode($SELF.'?new'); ?>'" style="background:linear-gradient(135deg,#555,#333)">🔑 Login to Sell</button>
  <?php elseif($hasActiveSub): ?>
  <button class="mk-post-btn" onclick="window.location='<?php echo $SELF.'?new'; ?>'">＋ Sell</button>
  <?php else: ?>
  <button class="mk-post-btn" onclick="window.location='<?php echo $SELF.'?sub_wall=1'; ?>'" style="background:linear-gradient(135deg,#b71c1c,#e53935)">🔒 Sell</button>
  <?php endif; ?>
</div>

<div class="mk-cats">
  <a href="<?php echo $SELF; ?>" class="mk-cat<?php echo !$filterCat?' active':''; ?>">🛍️ All</a>
  <?php foreach($CATS as $k=>$v): ?>
  <a href="<?php echo $SELF.'?cat='.$k.($search?'&q='.urlencode($search):''); ?>" class="mk-cat<?php echo $filterCat===$k?' active':''; ?>"><?php echo $v[0].' '.$v[1]; ?></a>
  <?php endforeach; ?>
</div>

<?php if($filterCat && !empty($SUBCATS[$filterCat])): ?>
<div class="mk-subbar">
  <a href="<?php echo $SELF.'?cat='.$filterCat.($search?'&q='.urlencode($search):''); ?>" class="mk-subchip<?php echo $filterSub===''?' on':''; ?>">All</a>
  <?php foreach($SUBCATS[$filterCat] as $sopt): ?>
  <a href="<?php echo $SELF.'?cat='.$filterCat.'&sub='.urlencode($sopt).($search?'&q='.urlencode($search):''); ?>" class="mk-subchip<?php echo $filterSub===$sopt?' on':''; ?>"><?php echo h($sopt); ?></a>
  <?php endforeach; ?>
</div>
<?php endif; ?>

<div class="mk-sortbar">
  <span style="font-size:.68rem;color:#666;flex-shrink:0">Sort:</span>
  <?php foreach(['latest'=>'🆕 Latest','popular'=>'🔥 Popular','price_asc'=>'💰 Low','price_desc'=>'💸 High'] as $sk=>$sl): ?>
  <a href="<?php echo $SELF.'?sort='.$sk.($filterCat?'&cat='.$filterCat:'').($search?'&q='.urlencode($search):''); ?>" class="mk-sort<?php echo $sort===$sk?' active':''; ?>"><?php echo $sl; ?></a>
  <?php endforeach; ?>
  <?php if($isAdmin): ?>
  <a href="<?php echo $SELF.'?admin_panel=1'; ?>" style="margin-left:auto" class="mk-sort">🛡️ Admin</a>
  <?php endif; ?>
</div>

<?php if(!empty($items)): ?>
<div class="mk-grid">
  <?php foreach($items as $ci):
    $ciImg = $ci['thumb'] ? $SITE.'/assets/uploads/market/'.$ci['thumb'] : null;
    $isFaved = in_array((string)$ci['id'],$myFavIds)||in_array((int)$ci['id'],$myFavIds);
    $statusMap2=['active'=>['badge-active','Active'],'sold'=>['badge-sold','Sold Out'],'inactive'=>['badge-inactive','Off'],'pending'=>['badge-pending','Pending']];
    $sc2=$statusMap2[$ci['status']]??['badge-inactive',''];
    $sph2=$ci['seller_photo']?$SITE.'/'.ltrim($ci['seller_photo'],'/'):null;
  ?>
  <div class="mk-card<?php echo $ci['status']==='sold'?' mk-card-sold':''; ?>" onclick="window.location='<?php echo $SELF.'?p=item&id='.(int)$ci['id']; ?>'">
    <?php if($ciImg): ?>
    <img class="mk-card-img" src="<?php echo h($ciImg); ?>" loading="lazy">
    <?php else: ?>
    <div class="mk-card-img-placeholder"><?php echo $CATS[$ci['category']][0]??'🛍️'; ?></div>
    <?php endif; ?>
    <span class="mk-badge <?php echo $sc2[0]; ?>"><?php echo $sc2[1]; ?></span>
    <?php if($ci['featured']): ?><span class="badge-featured">⭐</span><?php endif; ?>
    <button class="mk-fav-btn" onclick="event.stopPropagation();mkFav(<?php echo (int)$ci['id']; ?>,this)"><?php echo $isFaved?'❤️':'🤍'; ?></button>
    <div class="mk-card-body">
      <div class="mk-card-title"><?php echo h($ci['title']); ?></div>
      <?php if(!empty($ci['subcategory'])): ?><div style="display:inline-block;background:#eef6ef;color:var(--mk1);font-size:.55rem;font-weight:800;padding:.1rem .42rem;border-radius:8px;margin-bottom:.18rem">🔖 <?php echo h($ci['subcategory']); ?></div><?php endif; ?>
      <?php if($ci['price']): ?><div class="mk-card-price">₹<?php echo h($ci['price']); ?></div><?php else: ?><div class="mk-card-price-free">Free / On Request</div><?php endif; ?>
      <div class="mk-card-meta">
        <span><?php echo $CATS[$ci['category']][0]??''; ?></span>
        <span>👁 <?php echo (int)$ci['views']; ?></span>
        <span><?php echo date('d M',strtotime($ci['created_at'])); ?></span>
      </div>
      <div class="mk-card-seller">
        <?php if($sph2): ?><img src="<?php echo h($sph2); ?>" onerror="this.style.display='none'"><?php endif; ?>
        <div class="mk-card-seller-name"><?php echo h($ci['seller_name']); ?></div>
      </div>
    </div>
  </div>
  <?php endforeach; ?>
</div>
<?php else: ?>
<div class="empty">
  <div style="font-size:3rem;margin-bottom:.5rem">🛍️</div>
  <p><?php echo $search?'No results for "'.h($search).'"':'No items yet. Be the first to sell!'; ?></p>
  <a href="<?php echo $SELF.'?new'; ?>" style="display:inline-block;margin-top:.6rem;background:var(--mk1);color:#fff;padding:.5rem 1.2rem;border-radius:20px;font-size:.8rem;font-weight:800;text-decoration:none">＋ Post Something</a>
</div>
<?php endif; ?>

<?php endif; // end page routing ?>

</div><!-- /mkw -->

<div class="toast" id="mkt"></div>

<script>
var SELF='<?php echo $SELF; ?>';
var SITE='<?php echo $SITE; ?>';
var CLUBNAME=<?php echo json_encode($CLUB); ?>;
var LOGIN='<?php echo url('login.php'); ?>';
var IS_LOGGED=<?php echo $isLoggedIn?'true':'false'; ?>;
var SUBCATS=<?php echo json_encode($SUBCATS); ?>;

// ── Dynamic subcategory chips on the post form ──
function updateSubcats(){
  var sel=document.getElementById('catSel');
  var wrap=document.getElementById('subWrap');
  var box=document.getElementById('subChips');
  var val=document.getElementById('subVal');
  if(!sel||!wrap||!box||!val)return;
  var list=SUBCATS[sel.value]||[];
  if(!list.length){wrap.style.display='none';box.innerHTML='';val.value='';return;}
  if(val.value&&list.indexOf(val.value)<0)val.value='';
  wrap.style.display='block';
  box.innerHTML='';
  list.forEach(function(opt){
    var b=document.createElement('button');
    b.type='button';
    b.className='sub-chip'+(val.value===opt?' on':'');
    b.textContent=opt;
    b.onclick=function(){
      val.value=(val.value===opt)?'':opt;
      Array.prototype.forEach.call(box.children,function(c){
        c.classList.toggle('on',c.textContent===val.value);
      });
    };
    box.appendChild(b);
  });
}
updateSubcats();

function toast(m,t){var e=document.getElementById('mkt');e.textContent=m;e.className='toast on'+(t==='g'?' g':t==='e'?' e':'');setTimeout(function(){e.className='toast'},2800);}
function doSearch(q){window.location=SELF+'?q='+encodeURIComponent(q);}

// Slider
var _si=0,_sc=<?php echo count($itemImgs ?? []); ?>;
var _autoTimer=null;
function slide(d){_si=Math.max(0,Math.min(_sc-1,_si+d));slideTo(_si);resetAuto();}
function slideTo(i){
  _si=i;
  var t=document.getElementById('sldTrack');
  if(t) t.style.transform='translateX(-'+(_si*100)+'%)';
  document.querySelectorAll('.mk-dot').forEach(function(d,j){d.classList.toggle('on',j===_si);});
}
function resetAuto(){
  if(_autoTimer) clearInterval(_autoTimer);
  if(_sc>1){
    _autoTimer=setInterval(function(){
      _si=(_si+1)%_sc;
      slideTo(_si);
    },3000); // auto-slide every 3s
  }
}
// Start auto-slide
if(_sc>1) resetAuto();

// Swipe on slider
(function(){
  var sl=document.getElementById('sldr'),sx=0,sy=0;
  if(!sl)return;
  sl.addEventListener('touchstart',function(e){sx=e.touches[0].clientX;sy=e.touches[0].clientY;},{passive:true});
  sl.addEventListener('touchend',function(e){
    var dx=e.changedTouches[0].clientX-sx;
    var dy=e.changedTouches[0].clientY-sy;
    if(Math.abs(dx)>Math.abs(dy)&&Math.abs(dx)>40){slide(dx<0?1:-1);}
  },{passive:true});
})();

// Fullscreen/lightbox on tap image
(function(){
  var sl=document.getElementById('sldr');
  if(!sl)return;
  sl.addEventListener('click',function(e){
    if(e.target.tagName==='IMG'){
      var src=e.target.src;
      var ov=document.createElement('div');
      ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.95);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:zoom-out';
      var im=document.createElement('img');
      im.src=src;im.style.cssText='max-width:100%;max-height:100%;object-fit:contain;border-radius:4px';
      // swipe to close
      var ty=0;
      ov.addEventListener('touchstart',function(e){ty=e.touches[0].clientY;},{passive:true});
      ov.addEventListener('touchend',function(e){if(Math.abs(e.changedTouches[0].clientY-ty)>60)document.body.removeChild(ov);},{passive:true});
      ov.addEventListener('click',function(){document.body.removeChild(ov);});
      ov.appendChild(im);document.body.appendChild(ov);
    }
  });
})();

// Favorites
function mkFav(id,btn){
  var fd=new FormData();fd.append('action','fav');fd.append('item_id',id);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.msg==='login_required'){toast('🔑 Login to save items','e');setTimeout(function(){window.location=LOGIN+'?redirect='+encodeURIComponent(window.location.href);},1000);return;}
    if(res.ok){
      var f=res.faved;
      btn.textContent=f?'❤️':'🤍';
      toast(f?'❤️ Saved!':'Removed from saved',f?'g':'');
      var fb=document.getElementById('favBtn');
      if(fb)fb.textContent=f?'❤️ Saved':'🤍 Save';
    }
  });
}

// ── Change listing status: active / sold / inactive ──
function setStatus(id,status,btn){
  var labels={sold:'Mark this item as SOLD?',inactive:'Hide this item from the market?',active:'Make this item active again?'};
  if(!confirm(labels[status]||'Change status?'))return;
  if(btn){btn.disabled=true;}
  var fd=new FormData();fd.append('action','setstatus');fd.append('item_id',id);fd.append('status',status);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(btn){btn.disabled=false;}
    if(res.msg==='login_required'){toast('🔑 Please log in','e');return;}
    if(res.ok){
      var msg=status==='sold'?'💰 Marked as Sold':status==='inactive'?'⏸️ Hidden from market':'▶️ Item is active';
      toast(msg,'g');
      setTimeout(function(){location.reload();},700);
    } else {
      toast('Could not update','e');
    }
  }).catch(function(){if(btn)btn.disabled=false;toast('Network error','e');});
}

// ── Delete a listing ──
function mkDel(id){
  if(!confirm('Delete this listing permanently? This cannot be undone.'))return;
  var fd=new FormData();fd.append('action','delete');fd.append('item_id',id);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.msg==='login_required'){toast('🔑 Please log in','e');return;}
    if(res.ok){toast('🗑️ Listing deleted','g');setTimeout(function(){location.reload();},700);}
    else{toast(res.msg||'Could not delete','e');}
  }).catch(function(){toast('Network error','e');});
}

// ── Share own listing to the community feed ──
function shareToFeed(id,btn){
  if(btn){btn.disabled=true;btn.textContent='Sharing…';}
  var fd=new FormData();fd.append('action','share_feed');fd.append('item_id',id);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(btn){btn.disabled=false;btn.textContent='📰 Share to Feed';}
    if(res.msg==='login_required'){toast('🔑 Please log in','e');return;}
    if(res.ok){toast(res.msg,'g');}
    else{toast(res.msg||'Could not share','e');}
  }).catch(function(){if(btn){btn.disabled=false;btn.textContent='📰 Share to Feed';}toast('Network error','e');});
}

// Share
function mkShare(id,title){
  var link=SITE+'/modules/market.php?p=item&id='+id;
  var msg='🛍️ *'+title+'*\n🏪 Mini Market — '+CLUBNAME+'\n\n👉 View & Buy:\n'+link;
  var fd=new FormData();fd.append('action','shared');fd.append('item_id',id);
  fetch(SELF,{method:'POST',body:fd});
  fetch(SELF+'?get_thumb='+id)
    .then(function(r){return r.json();})
    .then(function(res){
      if(res.img){_buildShareImg(res.img,title,msg,link);}
      else{_shareText(msg,link,title);}
    }).catch(function(){_shareText(msg,link,title);});
}
function _shareText(msg,link,title){
  if(navigator.share){navigator.share({title:title,text:msg,url:link});}
  else if(navigator.clipboard){navigator.clipboard.writeText(link);toast('🔗 Link copied!','g');}
  else{window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');}
}
function _buildShareImg(imgUrl,title,msg,link){
  // Fetch ALL images as blobs to avoid CORS canvas taint
  Promise.all([
    fetch(imgUrl).then(function(r){return r.blob();}),
    fetch(SITE+'/assets/logo.png').then(function(r){return r.blob();}).catch(function(){return null;})
  ]).then(function(blobs){
    var prodBlob=blobs[0], logoBlob=blobs[1];
    var prodUrl=URL.createObjectURL(prodBlob);
    var logoUrl=logoBlob?URL.createObjectURL(logoBlob):null;

    var img=new Image();
    img.onload=function(){
      var maxW=1080;
      var W=img.width,H=img.height;
      if(W>maxW){H=Math.round(H*(maxW/W));W=maxW;}

      // Create canvas at 2× for sharpness
      var cv=document.createElement('canvas');
      cv.width=W*2; cv.height=H*2;
      var ctx=cv.getContext('2d');
      ctx.scale(2,2);
      ctx.imageSmoothingEnabled=true;
      ctx.imageSmoothingQuality='high';
      ctx.drawImage(img,0,0,W,H);
      URL.revokeObjectURL(prodUrl);

      // Watermark bar
      var bH=Math.round(H*0.14), bY=H-bH;
      var grad=ctx.createLinearGradient(0,bY,W,bY+bH);
      grad.addColorStop(0,'rgba(18,78,18,0.96)');
      grad.addColorStop(1,'rgba(38,108,38,0.96)');
      ctx.fillStyle=grad; ctx.fillRect(0,bY,W,bH);
      ctx.fillStyle='rgba(249,168,37,1)';
      ctx.fillRect(0,bY,W,Math.max(3,Math.round(bH*0.04)));

      if(logoUrl){
        var logo=new Image();
        logo.onload=function(){
          _drawWM(ctx,logo,W,H,bH,bY,title);
          URL.revokeObjectURL(logoUrl);
          _exportShare(cv,msg,link,title);
        };
        logo.onerror=function(){
          URL.revokeObjectURL(logoUrl);
          _drawWM(ctx,null,W,H,bH,bY,title);
          _exportShare(cv,msg,link,title);
        };
        logo.src=logoUrl;
      } else {
        _drawWM(ctx,null,W,H,bH,bY,title);
        _exportShare(cv,msg,link,title);
      }
    };
    img.onerror=function(){URL.revokeObjectURL(prodUrl);_shareText(msg,link,title);};
    img.src=prodUrl;
  }).catch(function(){_shareText(msg,link,title);});
}

function _drawWM(ctx,logo,W,H,bH,bY,title){
  var pad=Math.round(W*0.03);
  var lS=Math.round(bH*0.74);
  var lX=pad, lY=bY+(bH-lS)/2;

  if(logo){
    // Draw logo into a big offscreen then downscale = crisp
    var oc=document.createElement('canvas');
    var OS=lS*6; // 6× oversampling
    oc.width=OS; oc.height=OS;
    var ox=oc.getContext('2d');
    ox.imageSmoothingEnabled=true;
    ox.imageSmoothingQuality='high';
    // White filled circle
    ox.beginPath(); ox.arc(OS/2,OS/2,OS/2,0,Math.PI*2);
    ox.fillStyle='#fff'; ox.fill();
    // Clip logo inside circle
    ox.save();
    ox.beginPath(); ox.arc(OS/2,OS/2,OS/2,0,Math.PI*2); ox.clip();
    ox.drawImage(logo,0,0,OS,OS);
    ox.restore();
    // Paint downscaled onto main canvas
    ctx.imageSmoothingEnabled=true;
    ctx.imageSmoothingQuality='high';
    ctx.drawImage(oc,lX,lY,lS,lS);
    // White border ring
    ctx.beginPath(); ctx.arc(lX+lS/2,lY+lS/2,lS/2-1,0,Math.PI*2);
    ctx.strokeStyle='rgba(255,255,255,0.7)';
    ctx.lineWidth=Math.max(1.5,lS*0.035);
    ctx.stroke();
  }

  var tX = logo ? lX+lS+Math.round(W*0.025) : pad;
  var f1=Math.round(bH*0.41);
  var f2=Math.round(bH*0.27);

  // Club name
  ctx.font='700 '+f1+'px "DM Sans",Arial,sans-serif';
  ctx.fillStyle='#ffffff';
  ctx.textBaseline='middle';
  ctx.shadowColor='rgba(0,0,0,0.4)'; ctx.shadowBlur=4;
  var cname=CLUBNAME;
  var maxTW=W-tX-pad;
  while(ctx.measureText(cname).width>maxTW&&cname.length>6)cname=cname.slice(0,-1);
  ctx.fillText(cname,tX,bY+bH*0.31);

  // Mini Market · title
  ctx.font=f2+'px "DM Sans",Arial,sans-serif';
  ctx.fillStyle='rgba(255,255,255,0.85)';
  ctx.shadowBlur=2;
  var t2=title&&title.length>22?title.slice(0,20)+'…':title||'';
  ctx.fillText('🛍️ Mini Market'+(t2?'  ·  '+t2:''),tX,bY+bH*0.74);
  ctx.shadowBlur=0;
}

function _exportShare(cv,msg,link,title){
  cv.toBlob(function(blob){
    var file=new File([blob],'MiniMarket.jpg',{type:'image/jpeg'});
    if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){
      navigator.share({files:[file],text:msg});
    } else {
      var a=document.createElement('a');
      a.href=cv.toDataURL('image/jpeg',0.90);
      a.download='MiniMarket.jpg'; a.click();
      setTimeout(function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');},800);
    }
  },'image/jpeg',0.90);
}

// ── Location capture (GPS) ──
function _setPin(lat,lng,autoName){
  document.getElementById('locLat').value=lat;
  document.getElementById('locLng').value=lng;
  var st=document.getElementById('locStatus');
  if(st)st.textContent='📍 Pin saved ('+lat+', '+lng+'). Edit the place name above if you like.';
  if(autoName){
    var inp=document.getElementById('locInput');
    if(inp&&!inp.value.trim()){
      fetch('https://nominatim.openstreetmap.org/reverse?format=json&zoom=16&lat='+lat+'&lon='+lng)
        .then(function(r){return r.json();})
        .then(function(d){
          if(d&&d.address){
            var a=d.address;
            var name=a.suburb||a.village||a.town||a.neighbourhood||a.city_district||a.city||a.county||'';
            if(name)inp.value=name;
          }
        }).catch(function(){});
    }
  }
}
function useMyLocation(btn){
  if(!navigator.geolocation){toast('GPS not supported — use Pick on Map','e');return;}
  var st=document.getElementById('locStatus');
  if(st)st.textContent='📡 Getting your location…';
  if(btn)btn.disabled=true;
  function ok(pos){
    if(btn)btn.disabled=false;
    var lat=pos.coords.latitude.toFixed(7), lng=pos.coords.longitude.toFixed(7);
    _setPin(lat,lng,true);
    toast('📍 Location captured!','g');
  }
  function fail(err,triedLow){
    // err.code: 1=denied 2=unavailable 3=timeout
    if(err && err.code===1){
      if(btn)btn.disabled=false;
      if(st)st.textContent='🚫 GPS blocked — opening map to set it manually.';
      toast('🚫 GPS blocked — pick on map','e');
      pickOnMap();
      return;
    }
    if(!triedLow){ // retry once without high accuracy
      navigator.geolocation.getCurrentPosition(ok,function(e){fail(e,true);},{enableHighAccuracy:false,timeout:12000,maximumAge:60000});
      return;
    }
    if(btn)btn.disabled=false;
    if(st)st.textContent='⚠️ Couldn’t get GPS — opening map instead.';
    toast('⚠️ Pick on map','e');
    pickOnMap();
  }
  navigator.geolocation.getCurrentPosition(ok,function(e){fail(e,false);},{enableHighAccuracy:true,timeout:10000,maximumAge:0});
}

// ── Tap-on-map picker (Leaflet + OpenStreetMap, no API key) ──
var _lf=null,_lfMarker=null,_lfPick=null;
function _loadLeaflet(cb){
  if(window.L){cb();return;}
  if(!document.getElementById('lfcss')){
    var c=document.createElement('link');c.id='lfcss';c.rel='stylesheet';
    c.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(c);
  }
  var s=document.createElement('script');
  s.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  s.onload=cb;s.onerror=function(){toast('Map failed to load (no internet?)','e');};
  document.head.appendChild(s);
}
function pickOnMap(){
  _loadLeaflet(function(){
    var ov=document.getElementById('lfmodal');
    if(!ov){
      ov=document.createElement('div');ov.id='lfmodal';
      ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:10000;display:flex;align-items:flex-end;justify-content:center';
      ov.innerHTML=''
        +'<div style="background:#fff;width:100%;max-width:600px;border-radius:18px 18px 0 0;overflow:hidden">'
        +'<div style="padding:.7rem .9rem;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(135deg,#1B5E20,#2E7D32)">'
        +'<span style="color:#fff;font-weight:800;font-size:.85rem">📍 Tap the map to drop a pin</span>'
        +'<button type="button" onclick="_closeMap()" style="background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:50%;width:28px;height:28px;cursor:pointer">✕</button>'
        +'</div>'
        +'<div id="lfmap" style="height:60vh;width:100%"></div>'
        +'<div style="display:flex;gap:.5rem;padding:.7rem .9rem">'
        +'<button type="button" onclick="_mapLocate()" style="flex:1;padding:.6rem;background:#e8f5e9;color:#1B5E20;border:1.5px solid #c8e6c9;border-radius:10px;font-weight:800;font-size:.8rem;cursor:pointer">📡 My GPS</button>'
        +'<button type="button" onclick="_confirmMap()" style="flex:2;padding:.6rem;background:linear-gradient(135deg,#1B5E20,#2E7D32);color:#fff;border:none;border-radius:10px;font-weight:800;font-size:.8rem;cursor:pointer">✅ Use this spot</button>'
        +'</div></div>';
      document.body.appendChild(ov);
    }
    ov.style.display='flex';
    var clat=parseFloat(document.getElementById('locLat').value)||11.1265;
    var clng=parseFloat(document.getElementById('locLng').value)||76.2165; // Vettikkattiri (46G8+HJM) default
    var hasPin=!!document.getElementById('locLat').value;
    setTimeout(function(){
      if(!_lf){
        _lf=L.map('lfmap').setView([clat,clng],hasPin?16:15);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(_lf);
        _lf.on('click',function(e){_dropPin(e.latlng.lat,e.latlng.lng);});
      } else {
        _lf.setView([clat,clng],hasPin?16:15);
      }
      _lf.invalidateSize();
      if(hasPin){_dropPin(clat,clng);}
    },120);
  });
}
function _dropPin(lat,lng){
  _lfPick={lat:lat,lng:lng};
  if(_lfMarker){_lfMarker.setLatLng([lat,lng]);}
  else{_lfMarker=L.marker([lat,lng],{draggable:true}).addTo(_lf);
    _lfMarker.on('dragend',function(e){var p=e.target.getLatLng();_lfPick={lat:p.lat,lng:p.lng};});}
}
function _mapLocate(){
  if(!navigator.geolocation){toast('GPS not supported','e');return;}
  navigator.geolocation.getCurrentPosition(function(pos){
    var la=pos.coords.latitude,ln=pos.coords.longitude;
    _lf.setView([la,ln],16);_dropPin(la,ln);
  },function(){toast('GPS blocked — just tap the map','e');},{enableHighAccuracy:true,timeout:10000});
}
function _confirmMap(){
  if(!_lfPick){toast('Tap the map first','e');return;}
  _setPin(_lfPick.lat.toFixed(7),_lfPick.lng.toFixed(7),true);
  toast('📍 Location set!','g');
  _closeMap();
}
function _closeMap(){var ov=document.getElementById('lfmodal');if(ov)ov.style.display='none';}

// Image preview
function prevImg(inp,n){
  if(!inp.files||!inp.files[0])return;
  var r=new FileReader();
  r.onload=function(e){
    document.getElementById('fii'+n).src=e.target.result;
    document.getElementById('fip'+n).style.display='block';
    document.getElementById('fih'+n).style.display='none';
  };
  r.readAsDataURL(inp.files[0]);
}
</script>
<?php require_once __DIR__.'/../includes/footer.php'; ?>
