<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/extras.php';
$pageOG = [
  'title' => '📸 Gallery — Aishwarya Arts & Sports Club',
  'desc'  => 'Photo gallery of club events and activities — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/gallery.php',
];
requireLogin();
$me = currentUser();
$isAdmin = isAdminRole($me['role']) || canPost($me['role']);

// Auto-create tables
try {
    db()->exec("CREATE TABLE IF NOT EXISTS gallery_images(id INT AUTO_INCREMENT PRIMARY KEY,title VARCHAR(200),description TEXT,image_path VARCHAR(500) NOT NULL,category VARCHAR(80) DEFAULT 'general',is_active TINYINT(1) DEFAULT 1,is_hero TINYINT(1) DEFAULT 0,sort_order INT DEFAULT 0,uploaded_by INT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
} catch(Exception $e){}
try { db()->exec("ALTER TABLE gallery_images ADD COLUMN position VARCHAR(30) DEFAULT 'center 20%'"); } catch(Exception $e){}

$msg = '';

// Upload photo
if ($isAdmin && isset($_POST['upload_photo'])) {
    $title = trim($_POST['title'] ?? '');
    $desc  = trim($_POST['description'] ?? '');
    $cat   = trim($_POST['category'] ?? 'general');
    $hero  = isset($_POST['is_hero']) ? 1 : 0;
    $pos   = $_POST['img_position'] ?? 'center 20%';

    if (isset($_FILES['photo']) && $_FILES['photo']['error'] === 0) {
        $ext = strtolower(pathinfo($_FILES['photo']['name'], PATHINFO_EXTENSION));
        if (!in_array($ext, ['jpg','jpeg','png','webp','gif'])) {
            $msg = ['err','Only JPG, PNG, WebP, GIF allowed.'];
        } elseif ($_FILES['photo']['size'] > 5*1024*1024) {
            $msg = ['err','File too large. Max 5MB.'];
        } else {
            $uploadDir = __DIR__ . '/../assets/uploads/gallery/';
            if (!is_dir($uploadDir)) mkdir($uploadDir, 0755, true);
            $fname = 'gal_' . time() . '_' . mt_rand(1000,9999) . '.' . $ext;
            if (move_uploaded_file($_FILES['photo']['tmp_name'], $uploadDir . $fname)) {
                img_optimize($uploadDir . $fname);
                db()->prepare("INSERT INTO gallery_images(title,description,image_path,category,is_hero,uploaded_by,position) VALUES(?,?,?,?,?,?,?)")
                   ->execute([$title, $desc, 'gallery/'.$fname, $cat, $hero, $me['id'], $pos]);
                // If marked as hero, also add to hero_sliders
                if ($hero) {
                    try {
                        db()->exec("CREATE TABLE IF NOT EXISTS hero_sliders(id INT AUTO_INCREMENT PRIMARY KEY,title VARCHAR(200),subtitle VARCHAR(300),image_url VARCHAR(500),is_active TINYINT(1) DEFAULT 1,sort_order INT DEFAULT 0)");
                        $imgUrl = url('assets/uploads/gallery/'.$fname);
                        db()->prepare("INSERT INTO hero_sliders(title,subtitle,image_url,is_active) VALUES(?,?,?,1)")
                           ->execute([$title ?: CLUB_NAME, $desc ?: CLUB_TAGLINE, $imgUrl]);
                    } catch(Exception $e2){}
                }
                $msg = ['ok','✅ Photo uploaded successfully!'];
            } else {
                $msg = ['err','Upload failed. Check folder permissions.'];
            }
        }
    } else {
        $msg = ['err','Please select a photo to upload.'];
    }
}

// Delete photo
if ($isAdmin && isset($_POST['delete_photo'])) {
    require_once __DIR__ . '/../includes/sudo.php'; sudo_require();
    $pid = (int)$_POST['pid'];
    $row = db()->prepare("SELECT image_path FROM gallery_images WHERE id=?");
    $row->execute([$pid]); $row = $row->fetch();
    if ($row) {
        $f = __DIR__ . '/../assets/uploads/' . $row['image_path'];
        if (file_exists($f)) unlink($f);
        db()->prepare("DELETE FROM gallery_images WHERE id=?")->execute([$pid]);
        $msg = ['ok','🗑️ Photo deleted.'];
    }
}

// Toggle active
if ($isAdmin && isset($_POST['toggle_active'])) {
    $pid = (int)$_POST['pid'];
    db()->prepare("UPDATE gallery_images SET is_active = 1-is_active WHERE id=?")->execute([$pid]);
    $msg = ['ok','Updated.'];
}

// Toggle "show on public website"
if ($isAdmin && isset($_POST['toggle_public'])) {
    require_once __DIR__ . '/../includes/site_schema.php'; site_tables();
    db()->prepare("UPDATE gallery_images SET show_public = 1-IFNULL(show_public,1) WHERE id=?")->execute([(int)$_POST['pid']]);
    $msg = ['ok','Website setting updated.'];
}

// Toggle hero
if ($isAdmin && isset($_POST['toggle_hero'])) {
    $pid = (int)$_POST['pid'];
    db()->prepare("UPDATE gallery_images SET is_hero = 1-is_hero WHERE id=?")->execute([$pid]);
    $msg = ['ok','Homepage background updated.'];
}

// Fetch all
$cats     = ['general','football','cricket','onam','thiruvathira','kabaddi','arts','music','drama','donation','cricket','other'];
$filter   = $_GET['cat'] ?? 'all';
$where    = $filter === 'all' ? '' : "AND category=".db()->quote($filter);
$photos   = db()->query("SELECT g.*,u.name uploader FROM gallery_images g LEFT JOIN users u ON u.id=g.uploaded_by WHERE 1=1 $where ORDER BY g.sort_order,g.created_at DESC")->fetchAll();
$allCats  = db()->query("SELECT DISTINCT category FROM gallery_images WHERE is_active=1")->fetchAll(PDO::FETCH_COLUMN);

$pageTitle = 'Gallery — ' . CLUB_NAME;
require_once __DIR__ . '/../includes/header.php';
?>

<style>
.gal-page{max-width:1200px;margin:0 auto;padding:1.5rem 1rem}
.gal-hero{background:linear-gradient(135deg,#121A5C,#0A14E0);padding:2.5rem 1.5rem;text-align:center;color:#fff;margin-bottom:0}
.gal-hero h1{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:2.0rem;letter-spacing:.01em;margin-bottom:.3rem}
.gal-hero p{font-size:.9rem;color:rgba(255,255,255,.65)}

/* Upload card */
.upload-card{background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.09);border:1px solid rgba(0,0,0,.07);padding:1.5rem;margin-bottom:2rem}
.upload-area{border:2px dashed rgba(10,20,224,.25);border-radius:12px;padding:2rem;text-align:center;cursor:pointer;transition:all .25s;background:#f8f9ff;position:relative;overflow:hidden}
.upload-area:hover{border-color:#0A14E0;background:#eef1ff}
.upload-area input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.upload-preview{display:none;width:100%;height:200px;object-fit:contain;border-radius:10px;margin-top:.8rem}

/* Filter tabs */
.cat-tabs{display:flex;gap:.5rem;flex-wrap:wrap;margin:1.5rem 0}
.cat-tab{display:inline-block;padding:.38rem .9rem;border-radius:30px;font-size:.78rem;font-weight:700;border:1.5px solid rgba(0,0,0,.1);color:#666;transition:all .22s;cursor:pointer}
.cat-tab:hover,.cat-tab.on{background:#0A14E0;color:#fff;border-color:#0A14E0}

/* Gallery grid */
.gal-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem}
@media(max-width:480px){.gal-grid{grid-template-columns:repeat(2,1fr);gap:.6rem}}
.gal-item{position:relative;border-radius:12px;overflow:hidden;aspect-ratio:1;box-shadow:0 2px 12px rgba(0,0,0,.1);cursor:pointer;background:#F5F7FF}
.gal-item img{width:100%;height:100%;object-fit:cover;transition:transform .4s}
.gal-item:hover img{transform:scale(1.07)}
.gal-overlay{position:absolute;inset:0;background:linear-gradient(transparent 40%,rgba(0,0,0,.75));opacity:0;transition:opacity .3s;display:flex;flex-direction:column;justify-content:flex-end;padding:.8rem}
.gal-item:hover .gal-overlay{opacity:1}
.gal-caption{color:#fff;font-size:.78rem;font-weight:700;line-height:1.3}
.gal-meta{font-size:.65rem;color:rgba(255,255,255,.6);margin-top:.15rem}
/* Admin badges */
.badge-hero{position:absolute;top:.5rem;left:.5rem;background:#D4A017;color:#fff;font-size:.62rem;font-weight:700;padding:.18rem .5rem;border-radius:20px;z-index:3}
.badge-hidden{position:absolute;top:.5rem;left:.5rem;background:rgba(0,0,0,.55);color:#fff;font-size:.62rem;font-weight:700;padding:.18rem .5rem;border-radius:20px;z-index:3}
.admin-actions{position:absolute;top:.5rem;right:.5rem;display:flex;gap:.25rem;z-index:3;opacity:0;transition:opacity .2s}
.gal-item:hover .admin-actions{opacity:1}
.act-btn{width:28px;height:28px;border-radius:50%;border:none;cursor:pointer;font-size:.75rem;display:flex;align-items:center;justify-content:center;transition:all .2s}
.act-del{background:rgba(183,28,28,.85);color:#fff}
.act-hide{background:rgba(0,0,0,.6);color:#fff}
.act-star{background:rgba(212,160,23,.85);color:#fff}
/* Lightbox */
.lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:9999;align-items:center;justify-content:center}
.lb.on{display:flex}
.lb-img{max-width:90vw;max-height:85vh;border-radius:12px;object-fit:contain}
.lb-close{position:absolute;top:1rem;right:1rem;width:42px;height:42px;background:rgba(255,255,255,.15);border:none;border-radius:50%;color:#fff;font-size:1.2rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
.lb-info{position:absolute;bottom:1.5rem;left:50%;transform:translateX(-50%);text-align:center;color:#fff}
.lb-info h4{font-size:1rem;font-weight:700;margin-bottom:.2rem}
.lb-info p{font-size:.8rem;color:rgba(255,255,255,.6)}
.lb-prev,.lb-next{position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.15);border:none;color:#fff;width:44px;height:44px;border-radius:50%;font-size:1.1rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s}
.lb-prev{left:1rem}.lb-next{right:1rem}
.lb-prev:hover,.lb-next:hover{background:rgba(255,255,255,.28)}
/* Empty */
.gal-empty{text-align:center;padding:4rem 1rem;color:#5f6880}
.gal-empty div{font-size:3.5rem;margin-bottom:1rem}
</style>

<!-- Hero bar -->
<div class="gal-hero">
  <h1>📸 PHOTO GALLERY</h1>
  <p><?= h(CLUB_NAME) ?> · Capturing memories from every event in <?= h(CLUB_PLACE) ?></p>
</div>
<div style="height:4px;background:repeating-linear-gradient(90deg,#D4A017 0,#D4A017 10px,#B71C1C 10px,#B71C1C 20px,#0A14E0 20px,#0A14E0 30px,#F5C842 30px,#F5C842 40px)"></div>

<div class="gal-page">

<?php if($msg): ?>
<div class="alert alert-<?= $msg[0]==='ok'?'ok':'warn' ?>" style="margin-bottom:1rem"><?= $msg[1] ?></div>
<?php endif; ?>

<!-- ── UPLOAD (Admin only) ── -->
<?php if($isAdmin): ?>
<div class="upload-card">
  <h3 style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.12rem;letter-spacing:.01em;color:#121A5C;margin-bottom:1.2rem">📤 Upload Photos</h3>
  <form method="POST" action="<?= url('modules/gallery.php') ?>" enctype="multipart/form-data">
    <div class="row g-3">
      <div class="col-md-8">
        <div class="upload-area" id="uploadArea" onclick="document.getElementById('photoFile').click()">
          <input type="file" name="photo" id="photoFile" accept="image/*" onchange="previewPhoto(this)" style="display:none">
          <div id="uploadPrompt">
            <div style="font-size:2.5rem;margin-bottom:.5rem">📷</div>
            <div style="font-weight:700;color:#121A5C;margin-bottom:.25rem">Click to Upload Photo</div>
            <div style="font-size:.78rem;color:#5f6880">JPG, PNG, WebP · Max 5MB</div>
          </div>
          <img id="previewImg" class="upload-preview" alt="Preview">
        </div>
      </div>
      <div class="col-md-4">
        <div class="mb-2">
          <label style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#4a5568;display:block;margin-bottom:.3rem">Photo Title</label>
          <input type="text" name="title" class="form-control" placeholder="e.g. Onam 2024 Pookalam" style="border-radius:8px;font-size:.88rem">
        </div>
        <div class="mb-2">
          <label style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#4a5568;display:block;margin-bottom:.3rem">Category</label>
          <select name="category" class="form-select" aria-label="Photo category" style="border-radius:8px;font-size:.88rem">
            <option value="general">General</option>
            <option value="football">Football</option>
            <option value="cricket">Cricket</option>
            <option value="kabaddi">Kabaddi</option>
            <option value="onam">Onam</option>
            <option value="thiruvathira">Thiruvathira</option>
            <option value="arts">Arts Festival</option>
            <option value="music">Music</option>
            <option value="drama">Drama</option>
            <option value="donation">Donation</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div class="mb-2">
          <label style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#4a5568;display:block;margin-bottom:.3rem">Description</label>
          <textarea name="description" class="form-control" rows="2" placeholder="Brief description…" style="border-radius:8px;font-size:.88rem;resize:none"></textarea>
        </div>
        <div class="mb-3">
          <div class="form-check">
            <input type="checkbox" name="is_hero" id="isHero" class="form-check-input" value="1">
              <div style="margin-top:.6rem">
                <label class="lbl" style="font-size:.65rem;margin-bottom:.25rem;display:block">🎯 Photo Focus (for hero slider)</label>
                <select name="img_position" class="inp" aria-label="Image position" style="padding:.4rem .7rem;font-size:.8rem">
                  <option value="center 20%">👤 Top — Show faces (recommended)</option>
                  <option value="center 40%">🎯 Upper-middle</option>
                  <option value="center center">⬛ Center of image</option>
                  <option value="center bottom">⬇️ Bottom</option>
                  <option value="center top">⬆️ Top edge</option>
                </select>
              </div>
            <label class="form-check-label" for="isHero" style="font-size:.84rem;font-weight:600;color:#8a6116">
              ⭐ Use as homepage background slider
            </label>
          </div>
        </div>
        <button type="submit" name="upload_photo" class="btn btn-primary w-100" style="border-radius:8px;font-weight:700;background:#121A5C;border-color:#121A5C;color:#fff">
          <i class="fas fa-upload me-1"></i> Upload Photo
        </button>
      </div>
    </div>
  </form>
</div>
<?php endif; ?>

<!-- ── CATEGORY FILTER ── -->
<div class="cat-tabs">
  <a href="?cat=all"  class="cat-tab <?= $filter==='all'?'on':'' ?>">All (<?= count($photos) ?>)</a>
  <?php foreach($allCats as $c): ?>
  <a href="?cat=<?= urlencode($c) ?>" class="cat-tab <?= $filter===$c?'on':'' ?>"><?= h(ucfirst($c)) ?></a>
  <?php endforeach; ?>
</div>

<!-- ── GALLERY GRID ── -->
<?php if(empty($photos)): ?>
<div class="gal-empty">
  <div>🖼️</div>
  <h4 style="color:#121A5C">No photos yet</h4>
  <?php if($isAdmin): ?><p>Upload photos using the form above.</p><?php else: ?><p>Gallery photos will appear here soon.</p><?php endif; ?>
</div>
<?php else: ?>
<div class="gal-grid" id="galGrid">
  <?php foreach($photos as $i=>$p):
    $src = url('assets/uploads/' . $p['image_path']);
  ?>
  <div class="gal-item" data-src="<?= h($src) ?>" data-title="<?= h($p['title']??'') ?>" data-cat="<?= h($p['category']) ?>" data-i="<?= $i ?>" onclick="openLB(<?= $i ?>)">
    <img src="<?= h($src) ?>" alt="<?= h($p['title']??'Photo') ?>" loading="lazy">
    <!-- Badges -->
    <?php if($p['is_hero']): ?><span class="badge-hero">⭐ Homepage</span><?php endif; ?>
    <?php if(!$p['is_active'] && $isAdmin): ?><span class="badge-hidden">Hidden</span><?php elseif($isAdmin && isset($p['show_public']) && (int)$p['show_public'] === 0): ?><span class="badge-hidden">Not on website</span><?php endif; ?>
    <!-- Overlay -->
    <div class="gal-overlay">
      <div class="gal-caption"><?= h($p['title']??'') ?></div>
      <div class="gal-meta"><?= h(ucfirst($p['category'])) ?> · <?= date('d M Y',strtotime($p['created_at'])) ?></div>
    </div>
    <!-- Admin actions -->
    <?php if($isAdmin): ?>
    <div class="admin-actions">
      <form method="POST" action="<?= url('modules/gallery.php') ?>" style="display:inline" onclick="event.stopPropagation()">
        <input type="hidden" name="pid" value="<?= $p['id'] ?>">
        <button type="submit" name="toggle_hero" class="act-btn act-star" title="Toggle homepage" onclick="return confirm('Toggle homepage background?')">⭐</button>
      </form>
      <form method="POST" action="<?= url('modules/gallery.php') ?>" style="display:inline" onclick="event.stopPropagation()">
        <input type="hidden" name="pid" value="<?= $p['id'] ?>">
        <button type="submit" name="toggle_active" class="act-btn act-hide" title="Show/Hide">👁</button>
      </form>
      <form method="POST" action="<?= url('modules/gallery.php') ?>" style="display:inline" onclick="event.stopPropagation()">
        <input type="hidden" name="pid" value="<?= $p['id'] ?>">
        <button type="submit" name="toggle_public" class="act-btn act-hide" title="<?= (isset($p['show_public']) && (int)$p['show_public'] === 0) ? 'Show on public website' : 'Hide from public website' ?>">🌐</button>
      </form>
      <form method="POST" action="<?= url('modules/gallery.php') ?>" style="display:inline" onclick="event.stopPropagation()" data-sudo data-confirm="Delete this photo?">
        <input type="hidden" name="pid" value="<?= $p['id'] ?>">
        <button type="submit" name="delete_photo" class="act-btn act-del" title="Delete">🗑</button>
      </form>
    </div>
    <?php endif; ?>
  </div>
  <?php endforeach; ?>
</div>
<?php endif; ?>
</div><!-- /gal-page -->

<!-- ── LIGHTBOX ── -->
<div class="lb" id="lb" onclick="if(event.target===this)closeLB()">
  <button class="lb-close" onclick="closeLB()">✕</button>
  <button class="lb-prev" onclick="lbNav(-1);event.stopPropagation()">‹</button>
  <img class="lb-img" id="lbImg" src="" alt="">
  <button class="lb-next" onclick="lbNav(1);event.stopPropagation()">›</button>
  <div class="lb-info">
    <h4 id="lbTitle"></h4>
    <p id="lbCat"></p>
  </div>
</div>

<script>
// Preview upload
function previewPhoto(inp) {
  if (!inp.files || !inp.files[0]) return;
  var url = URL.createObjectURL(inp.files[0]);
  var img = document.getElementById('previewImg');
  var prompt = document.getElementById('uploadPrompt');
  img.src = url;
  img.style.display = 'block';
  prompt.style.display = 'none';
  document.getElementById('uploadArea').style.border = '2px solid #0A14E0';
}

// Lightbox
var items = [].slice.call(document.querySelectorAll('.gal-item'));
var lbIdx = 0;
function openLB(i) {
  lbIdx = i;
  updateLB();
  document.getElementById('lb').classList.add('on');
  document.body.style.overflow = 'hidden';
}
function closeLB() {
  document.getElementById('lb').classList.remove('on');
  document.body.style.overflow = '';
}
function lbNav(dir) {
  lbIdx = (lbIdx + dir + items.length) % items.length;
  updateLB();
}
function updateLB() {
  var el = items[lbIdx];
  if (!el) return;
  document.getElementById('lbImg').src = el.dataset.src;
  document.getElementById('lbTitle').textContent = el.dataset.title || '';
  document.getElementById('lbCat').textContent = el.dataset.cat || '';
}
document.addEventListener('keydown', function(e) {
  if (!document.getElementById('lb').classList.contains('on')) return;
  if (e.key === 'Escape') closeLB();
  if (e.key === 'ArrowLeft')  lbNav(-1);
  if (e.key === 'ArrowRight') lbNav(1);
});
</script>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
