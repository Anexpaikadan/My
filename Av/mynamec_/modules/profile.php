<?php
// modules/profile.php — Member Profile with Privacy & Role-Based Display
require_once __DIR__.'/../includes/config.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '👤 Member Profile — Aishwarya Arts & Sports Club',
  'desc'  => 'Member profile — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/profile.php',
];
requireLogin();
// Add blood availability columns if not exist
try { db()->exec("ALTER TABLE users ADD COLUMN blood_available TINYINT(1) DEFAULT 1"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE users ADD COLUMN blood_last_donated DATE DEFAULT NULL"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE users ADD COLUMN blood_unavail_reason VARCHAR(100) DEFAULT NULL"); } catch(Exception $e){}
$me = currentUser();

$viewId = isset($_GET['id']) ? (int)$_GET['id'] : $me['id'];
$isOwn  = ($viewId === $me['id']);
$isAdmin = isAdminRole($me['role']);

// ── AJAX handlers (must be before any HTML output) ────────────
if (!empty($_POST['ajax']) && $_SERVER['REQUEST_METHOD']==='POST') {
    header('Content-Type: application/json');
    $act = $_POST['action'] ?? '';
    if ($act === 'set_blood_avail') {
        $avail   = (int)($_POST['available'] ?? 1);
        $reason  = trim($_POST['reason'] ?? '');
        $lastDon = trim($_POST['last_donated'] ?? '');
        db()->prepare('UPDATE users SET blood_available=?,blood_unavail_reason=?,blood_last_donated=? WHERE id=?')
           ->execute([$avail, $avail ? null : ($reason ?: 'Unavailable'), $lastDon ?: null, $me['id']]);
        echo json_encode(['ok'=>true,'msg'=>'Blood donation status updated!']);
        exit;
    }
    if ($act === 'change_passkey') {
        $newKey = trim($_POST['passkey'] ?? '');
        if (strlen($newKey)!==6 || !ctype_digit($newKey)) {
            echo json_encode(['ok'=>false,'msg'=>'Must be 6 digits.']); exit;
        }
        $hash = password_hash($newKey, PASSWORD_DEFAULT);
        db()->prepare('UPDATE users SET passkey=?,passkey_set=1 WHERE id=?')->execute([$hash, $me['id']]);
        echo json_encode(['ok'=>true,'msg'=>'Passkey updated!']);
        exit;
    }
    echo json_encode(['ok'=>false,'msg'=>'Unknown action']); exit;
}

// Fetch profile
$s = db()->prepare('SELECT * FROM users WHERE id=? AND status="active"');
$s->execute([$viewId]);
$profile = $s->fetch();
if (!$profile) { header('Location:'.url('dashboard.php')); exit; }

// Ground Fund contribution for this member (if module tables exist)
$gfPledge = 0; $gfPaid = 0; $gfHasData = false;
try {
  $gp = db()->prepare("SELECT pledge_amount FROM gf_pledges WHERE member_id=?");
  $gp->execute([$profile['id']]); $gfPledge = (float)($gp->fetchColumn() ?: 0);
  $gpp = db()->prepare("SELECT COALESCE(SUM(amount),0) FROM gf_payments WHERE member_id=?");
  $gpp->execute([$profile['id']]); $gfPaid = (float)$gpp->fetchColumn();
  $gfHasData = ($gfPledge > 0 || $gfPaid > 0);
} catch (Exception $e) { $gfHasData = false; }
$gfBalance = max(0, $gfPledge - $gfPaid);
$gfPct = $gfPledge > 0 ? min(100, round(($gfPaid / $gfPledge) * 100)) : 0;

// Privacy check: can viewer see phone number?
$canSeePhone = $isOwn || $isAdmin || $profile['privacy_phone'] === 'public' ||
               ($profile['privacy_phone'] === 'members' && isLoggedIn());
// Can viewer see photo?
$canSeePhoto = $isOwn || $isAdmin || $profile['privacy_photo'] === 'public' ||
               ($profile['privacy_photo'] === 'members' && isLoggedIn());

$pageTitle = h($profile['name']) . ' — ' . setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$msg = '';

// Handle profile update (own only)
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $isOwn && isset($_POST['up'])) {
    $u=[]; $p=[];
    foreach(['skill','profession','email','name'] as $f) {
        if (isset($_POST[$f])) { $u[]="$f=?"; $p[]=trim($_POST[$f]); }
    }
    // Privacy settings
    if (isset($_POST['privacy_phone'])) { $u[]='privacy_phone=?'; $p[]=$_POST['privacy_phone']; }
    if (isset($_POST['privacy_photo'])) { $u[]='privacy_photo=?'; $p[]=$_POST['privacy_photo']; }

    if ($isAdmin && isset($_POST['blood_group'])) { $u[]='blood_group=?'; $p[]=$_POST['blood_group']; }

    // Photo upload — resize + crop to 400×400 square, delete old photo
    if (!empty($_FILES['photo']['name']) && $_FILES['photo']['error']===0) {
        $ext = strtolower(pathinfo($_FILES['photo']['name'], PATHINFO_EXTENSION));
        $allowed = array('jpg','jpeg','png','webp','gif');
        if (in_array($ext, $allowed) && $_FILES['photo']['size'] < 5000000) {
            $dir = __DIR__.'/../assets/uploads/profiles/';
            if (!is_dir($dir)) mkdir($dir, 0755, true);

            // Delete old photo if exists (check both old path and new path)
            $oldPhoto = $profile['profile_photo'] ?? '';
            if ($oldPhoto && $oldPhoto !== 'default.png') {
                // Try profiles/ subfolder first, then root uploads/
                $oldPaths = array(
                    __DIR__.'/../assets/uploads/profiles/' . basename($oldPhoto),
                    __DIR__.'/../assets/uploads/' . $oldPhoto,
                    __DIR__.'/../assets/uploads/' . basename($oldPhoto),
                );
                foreach ($oldPaths as $oldPath) {
                    if (file_exists($oldPath)) { unlink($oldPath); break; }
                }
            }

            // New filename always .jpg (after processing)
            $fn  = 'profiles/user_' . $me['id'] . '_' . time() . '.jpg';
            $dst = __DIR__.'/../assets/uploads/' . $fn;

            // Load source image based on type
            $src = $_FILES['photo']['tmp_name'];
            $info = @getimagesize($src);
            $mime = $info ? $info['mime'] : '';

            $srcImg = null;
            if ($mime === 'image/jpeg' || in_array($ext, array('jpg','jpeg'))) {
                $srcImg = @imagecreatefromjpeg($src);
            } elseif ($mime === 'image/png' || $ext === 'png') {
                $srcImg = @imagecreatefrompng($src);
            } elseif ($mime === 'image/webp' || $ext === 'webp') {
                $srcImg = function_exists('imagecreatefromwebp') ? @imagecreatefromwebp($src) : null;
            } elseif ($mime === 'image/gif' || $ext === 'gif') {
                $srcImg = @imagecreatefromgif($src);
            }

            if ($srcImg) {
                $ow = imagesx($srcImg);
                $oh = imagesy($srcImg);

                // Auto-rotate based on EXIF (JPEG only)
                if (function_exists('exif_read_data') && in_array($ext, array('jpg','jpeg'))) {
                    $exif = @exif_read_data($src);
                    $ori  = isset($exif['Orientation']) ? $exif['Orientation'] : 1;
                    if ($ori == 3) { $srcImg = imagerotate($srcImg, 180, 0); }
                    elseif ($ori == 6) { $srcImg = imagerotate($srcImg, -90, 0); $tmp=$ow;$ow=$oh;$oh=$tmp; }
                    elseif ($ori == 8) { $srcImg = imagerotate($srcImg, 90, 0);  $tmp=$ow;$ow=$oh;$oh=$tmp; }
                }

                // Center-crop to square then resize to 400x400
                $size   = min($ow, $oh);
                $cropX  = (int)(($ow - $size) / 2);
                $cropY  = (int)(($oh - $size) / 2);
                $target = 400;

                $out = imagecreatetruecolor($target, $target);

                // Handle transparency for PNG
                imagealphablending($out, false);
                imagesavealpha($out, true);
                $white = imagecolorallocate($out, 255, 255, 255);
                imagefilledrectangle($out, 0, 0, $target, $target, $white);

                imagecopyresampled($out, $srcImg, 0, 0, $cropX, $cropY, $target, $target, $size, $size);

                // Save as high-quality JPEG
                imagejpeg($out, $dst, 88);

                imagedestroy($srcImg);
                imagedestroy($out);

                $u[] = 'profile_photo=?';
                $p[] = $fn;
            } else {
                // GD failed — just save original file directly
                if (move_uploaded_file($src, $dst)) {
                    $u[] = 'profile_photo=?';
                    $p[] = $fn;
                }
            }
        }
    }
    if ($u) {
        $p[]=$me['id'];
        db()->prepare('UPDATE users SET '.implode(',',$u).' WHERE id=?')->execute($p);
        $msg=['t'=>'ok','m'=>'Profile updated!'];
        $profile=currentUser();
        $me=$profile;
    }
}

$logoB64  = getLogoB64();
$photoB64 = $canSeePhoto ? getMemberPhoto($profile['profile_photo']) : '';
$wn       = preg_replace('/\D/','',$profile['whatsapp_number']);

// Role color for header
$roleColors = [
    'president'       => 'linear-gradient(135deg,#B8860B,#DAA520)',
    'vice_president'  => 'linear-gradient(135deg,#8B6914,#C9A84C)',
    'secretary'       => 'linear-gradient(135deg,#07225c,#0D47A1)',
    'joint_secretary' => 'linear-gradient(135deg,#0a3880,#1565C0)',
    'treasurer'       => 'linear-gradient(135deg,#1B5E20,#2E7D32)',
    'committee_member'=> 'linear-gradient(135deg,#4A148C,#7B1FA2)',
    'member'          => 'linear-gradient(135deg,#37474F,#546E7A)',
];
$headerBg = $roleColors[$profile['role']] ?? $roleColors['member'];

require_once __DIR__.'/../includes/header.php';
?>

<div class="section" style="max-width:900px">

<?php if($msg): ?>
<div class="alert alert-ok">✅ <?= h($msg['m']) ?></div>
<?php endif; ?>

<!-- ── ROLE-SPECIFIC PROFILE HEADER (app style) ────────────── -->
<div class="pf-card" style="border-radius:22px;overflow:hidden;margin-bottom:1.3rem;box-shadow:0 10px 36px rgba(13,27,62,.16);animation:pfIn .5s ease">

  <!-- Colored header based on role -->
  <div style="background:<?= $headerBg ?>;padding:1.8rem 1.5rem 4rem;position:relative;overflow:hidden">
    <div style="position:absolute;top:-30px;right:-25px;width:170px;height:170px;border-radius:50%;background:rgba(255,255,255,.07);animation:pfFloat 7s ease-in-out infinite"></div>
    <div style="position:absolute;bottom:-45px;left:-25px;width:130px;height:130px;border-radius:50%;background:rgba(255,255,255,.05);animation:pfFloat 9s ease-in-out infinite reverse"></div>

    <!-- Role badge top -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;position:relative">
      <span style="background:rgba(0,0,0,.28);color:rgba(255,255,255,.95);border-radius:20px;padding:.3rem 1rem;font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;backdrop-filter:blur(4px)">
        <?= h(roleLabel($profile['role'])) ?>
      </span>
      <?php if($isOwn): ?>
      <a href="<?= url('modules/idcard.php') ?>" style="background:rgba(255,193,7,.25);color:#FFC107;border:1px solid rgba(255,193,7,.45);border-radius:20px;padding:.3rem 1rem;font-size:.68rem;font-weight:800;text-decoration:none;backdrop-filter:blur(4px)">
        🪪 My ID
      </a>
      <?php endif; ?>
    </div>
  </div>

  <!-- Photo + Info overlapping white card -->
  <div style="background:#fff;padding:0 1.4rem 1.4rem;position:relative">
    <div style="display:flex;flex-direction:column;align-items:center;text-align:center;margin-top:-3rem;margin-bottom:1rem">

      <!-- Profile Photo (centered, app-style) -->
      <div style="position:relative;flex-shrink:0;margin-bottom:.7rem">
        <?php if($photoB64): ?>
        <img src="<?= $photoB64 ?>" style="width:104px;height:104px;border-radius:50%;object-fit:cover;border:5px solid #fff;box-shadow:0 8px 22px rgba(0,0,0,.22);display:block" alt="">
        <?php else: ?>
        <div style="width:104px;height:104px;border-radius:50%;background:linear-gradient(135deg,#E3F2FD,#BBDEFB);border:5px solid #fff;display:flex;align-items:center;justify-content:center;font-size:2.6rem;box-shadow:0 8px 22px rgba(0,0,0,.18)">
          <?php if(!$canSeePhoto && !$isOwn): ?>🔒<?php else: ?>👤<?php endif; ?>
        </div>
        <?php endif; ?>
        <?php if($profile['privacy_photo'] === 'private' && !$isOwn && !$isAdmin): ?>
        <div style="position:absolute;bottom:4px;right:4px;background:#B71C1C;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:.68rem;border:2px solid #fff">🔒</div>
        <?php else: ?>
        <div style="position:absolute;bottom:6px;right:6px;background:#2E7D32;border-radius:50%;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:.6rem;border:2px solid #fff;color:#fff">✓</div>
        <?php endif; ?>
      </div>

      <div style="width:100%">
        <h1 style="font-family:'Bebas Neue',sans-serif;font-size:1.7rem;letter-spacing:.04em;color:#0D1B3E;margin-bottom:.15rem;line-height:1.1"><?= h($profile['name']) ?></h1>
        <?php if($profile['committee_position']): ?>
        <div style="font-size:.86rem;color:#3D4F7C;font-weight:700"><?= h($profile['committee_position']) ?></div>
        <?php endif; ?>
        <?php if($profile['committee_name']): ?>
        <div style="font-size:.74rem;color:#7A8DB5"><?= h($profile['committee_name']) ?></div>
        <?php endif; ?>
        <?php if($isOwn): ?>
        <button onclick="document.getElementById('editSection').style.display=document.getElementById('editSection').style.display==='none'?'block':'none';document.getElementById('editSection').scrollIntoView({behavior:'smooth'})" style="margin-top:.7rem;background:linear-gradient(135deg,#0d47a1,#1565c0);color:#fff;border:none;border-radius:22px;padding:.5rem 1.4rem;font-size:.8rem;font-weight:800;cursor:pointer;font-family:'DM Sans',sans-serif;box-shadow:0 4px 12px rgba(21,101,192,.3)">✏️ Edit Profile</button>
        <button id="bioEnrollBtn" onclick="pfBioEnroll()" style="display:none;margin-top:.5rem;margin-left:.4rem;background:#fff;border:1.5px solid #1565c0;color:#1565c0;border-radius:22px;padding:.5rem 1.2rem;font-size:.8rem;font-weight:800;cursor:pointer;font-family:'DM Sans',sans-serif">👆 Enable Fingerprint Login</button>
        <script>
        (function(){ if(window.PublicKeyCredential){ var b=document.getElementById('bioEnrollBtn'); if(b)b.style.display='inline-block'; } })();
        var PF_WA='<?= url('modules/webauthn.php') ?>';
        function pf_b64ToBuf(s){s=s.replace(/-/g,'+').replace(/_/g,'/');var p=s.length%4;if(p)s+='='.repeat(4-p);var b=atob(s),a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return a.buffer;}
        function pf_bufToB64(buf){var b=new Uint8Array(buf),s='';for(var i=0;i<b.length;i++)s+=String.fromCharCode(b[i]);return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');}
        function pfBioEnroll(){
          if(!window.PublicKeyCredential){ alert('This phone/browser does not support fingerprint login. Use Chrome or Safari and make sure the site is HTTPS.'); return; }
          if(!window.isSecureContext){ alert('Fingerprint needs a secure (HTTPS) connection. Open https://mynamecc.online'); return; }
          alert('Starting setup… your fingerprint prompt will appear next.');
          fetch(PF_WA,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'act=reg_begin'})
            .then(function(r){return r.text();})
            .then(function(txt){
              var d;
              try { d=JSON.parse(txt); } catch(e){ alert('Server error (not JSON):\n'+txt.substring(0,200)); return; }
              if(!d.ok){ alert('Could not start: '+(d.msg||'unknown')); return; }
              var o=d.options; o.challenge=pf_b64ToBuf(o.challenge); o.user.id=pf_b64ToBuf(o.user.id);
              navigator.credentials.create({publicKey:o}).then(function(cred){
                var body='act=reg_finish&cred_id='+encodeURIComponent(cred.id)+'&client_data='+encodeURIComponent(pf_bufToB64(cred.response.clientDataJSON))+'&att_obj='+encodeURIComponent(pf_bufToB64(cred.response.attestationObject));
                fetch(PF_WA,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body})
                  .then(function(r){return r.text();})
                  .then(function(t2){ try{ alert(JSON.parse(t2).msg); }catch(e){ alert('Save error:\n'+t2.substring(0,200)); } });
              }).catch(function(err){ alert('Fingerprint prompt failed: '+(err&&err.name?err.name:'')+' — '+(err&&err.message?err.message:err)); });
            })
            .catch(function(err){ alert('Network error reaching server: '+err); });
        }
        </script>
        <?php endif; ?>
      </div>
    </div>

    <!-- Info Grid - app-style tiles -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.65rem">

      <!-- Blood Group -->
      <div class="pf-tile" style="background:linear-gradient(135deg,#fff5f5,#ffebee);border:1px solid #ffcdd2">
        <div class="pf-tile-l" style="color:#B71C1C">🩸 Blood Group</div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:#B71C1C;line-height:1"><?= h($profile['blood_group'] ?? '—') ?></div>
      </div>

      <!-- WhatsApp -->
      <div class="pf-tile" style="background:linear-gradient(135deg,#f1faf3,#e8f5e9);border:1px solid <?= $canSeePhone ? '#a5d6a7' : '#e0e0e0' ?>">
        <div class="pf-tile-l" style="color:<?= $canSeePhone ? '#2E7D32':'#9E9E9E' ?>">💬 WhatsApp</div>
        <?php if($canSeePhone): ?>
        <a href="https://wa.me/<?= $wn ?>" target="_blank" style="font-size:.8rem;color:#2E7D32;font-weight:800;text-decoration:none"><?= h($profile['whatsapp_number']) ?></a>
        <?php else: ?>
        <div style="font-size:.8rem;color:#9E9E9E;font-weight:700">🔒 Private</div>
        <?php endif; ?>
      </div>

      <!-- Skill -->
      <div class="pf-tile" style="background:linear-gradient(135deg,#f3f7ff,#e3f2fd);border:1px solid #bbdefb">
        <div class="pf-tile-l" style="color:#0D47A1">⭐ Skill</div>
        <div style="font-size:.84rem;font-weight:700;color:#0D1B3E"><?= h($profile['skill'] ?? '—') ?></div>
      </div>

      <!-- Member ID -->
      <div class="pf-tile" style="background:linear-gradient(135deg,#faf4ff,#f3e5f5);border:1px solid #e1bee7">
        <div class="pf-tile-l" style="color:#7B1FA2">🆔 Member ID</div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.2rem;color:#7B1FA2">AV<?= str_pad($profile['id'],4,'0',STR_PAD_LEFT) ?></div>
      </div>

      <?php if($profile['profession']): ?>
      <div class="pf-tile" style="background:linear-gradient(135deg,#fff8f0,#fff3e0);border:1px solid #ffe0b2">
        <div class="pf-tile-l" style="color:#E65100">💼 Profession</div>
        <div style="font-size:.82rem;font-weight:700;color:#0D1B3E"><?= h($profile['profession']) ?></div>
      </div>
      <?php endif; ?>

      <div class="pf-tile" style="background:linear-gradient(135deg,#f1faf3,#e8f5e9);border:1px solid #a5d6a7">
        <div class="pf-tile-l" style="color:#2E7D32">📋 Status</div>
        <div style="font-size:.84rem;font-weight:800;color:#2E7D32">✓ Active</div>
      </div>
    </div>

    <!-- Action Buttons -->
    <div style="display:flex;gap:.6rem;margin-top:1.1rem;flex-wrap:wrap">
      <?php if($isOwn): ?>
      <a href="<?= url('modules/idcard.php') ?>" class="btn btn-blue" style="text-decoration:none;flex:1;text-align:center;border-radius:12px">
        🪪 My ID Card
      </a>
      <?php endif; ?>
      <?php if($canSeePhone && !$isOwn): ?>
      <a href="https://wa.me/<?= $wn ?>" target="_blank" class="btn btn-green" style="text-decoration:none;flex:1;text-align:center;border-radius:12px">
        💬 Send WhatsApp
      </a>
      <?php endif; ?>
      <?php if(!$isOwn): ?>
      <a href="<?= url('modules/members.php') ?>" class="btn btn-grey" style="text-decoration:none;flex:1;text-align:center;border-radius:12px">
        ← Members
      </a>
      <?php endif; ?>
    </div>
  </div>
</div>
<style>
@keyframes pfIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes pfFloat{0%,100%{transform:translate(0,0)}50%{transform:translate(12px,-10px)}}
.pf-tile{border-radius:14px;padding:.7rem .65rem;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.25rem;min-height:74px;transition:transform .2s}
.pf-tile:active{transform:scale(.96)}
.pf-tile-l{font-size:.6rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
</style>

<!-- ── GROUND FUND CONTRIBUTION CARD ───────────────────────── -->
<?php if($gfHasData): ?>
<div style="background:#fff;border-radius:18px;padding:1.1rem 1.2rem;margin-bottom:1.3rem;box-shadow:0 6px 24px rgba(13,27,62,.1);animation:pfIn .5s .1s both">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem">
    <div style="display:flex;align-items:center;gap:.5rem">
      <span style="font-size:1.4rem">🏟️</span>
      <div>
        <div style="font-weight:800;font-size:.95rem;color:#0D1B3E;line-height:1.1">Ground Fund</div>
        <div style="font-size:.68rem;color:#8a93a8">Contribution to club ground</div>
      </div>
    </div>
    <a href="<?= url('modules/groundfund.php') ?>" style="font-size:.7rem;font-weight:700;color:#0d47a1;text-decoration:none">View all →</a>
  </div>

  <!-- Paid / Pledge / Balance tiles -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.55rem;margin-bottom:.9rem">
    <div style="background:linear-gradient(135deg,#f1faf3,#e8f5e9);border:1px solid #a5d6a7;border-radius:12px;padding:.6rem;text-align:center">
      <div style="font-size:.56rem;font-weight:800;color:#2E7D32;text-transform:uppercase">Paid</div>
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.35rem;color:#1b5e20">₹<?= number_format($gfPaid) ?></div>
    </div>
    <div style="background:linear-gradient(135deg,#f3f7ff,#e3f2fd);border:1px solid #bbdefb;border-radius:12px;padding:.6rem;text-align:center">
      <div style="font-size:.56rem;font-weight:800;color:#0D47A1;text-transform:uppercase">Pledged</div>
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.35rem;color:#0d47a1">₹<?= number_format($gfPledge) ?></div>
    </div>
    <div style="background:linear-gradient(135deg,<?= $gfBalance>0?'#fff8f0,#fff3e0':'#f1faf3,#e8f5e9' ?>);border:1px solid <?= $gfBalance>0?'#ffe0b2':'#a5d6a7' ?>;border-radius:12px;padding:.6rem;text-align:center">
      <div style="font-size:.56rem;font-weight:800;color:<?= $gfBalance>0?'#E65100':'#2E7D32' ?>;text-transform:uppercase">Balance</div>
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.35rem;color:<?= $gfBalance>0?'#e65100':'#1b5e20' ?>"><?= $gfBalance>0?'₹'.number_format($gfBalance):'✓ Paid' ?></div>
    </div>
  </div>

  <?php if($gfPledge > 0): ?>
  <!-- Progress bar -->
  <div style="height:8px;background:#eef1f6;border-radius:5px;overflow:hidden">
    <div style="height:100%;width:<?= $gfPct ?>%;background:linear-gradient(90deg,#1b5e20,#4caf50);border-radius:5px;transition:width 1s"></div>
  </div>
  <div style="font-size:.66rem;color:#8a93a8;text-align:right;margin-top:.25rem"><?= $gfPct ?>% of pledge paid</div>
  <?php endif; ?>
</div>
<?php endif; ?>

<!-- ── EDIT SECTION (own profile only) ─────────────────────── -->
<?php if($isOwn): ?>
<div id="editSection" style="display:none">
<div class="card">
  <div class="card-header"><h3>✏️ Edit My Profile</h3></div>
  <div class="card-body">
    <form method="POST" action="<?= url('modules/profile.php') ?>" enctype="multipart/form-data">
      <div class="g2">
        <div class="fg">
          <label class="lbl">Profile Photo</label>
          <input type="file" name="photo" class="inp" accept="image/jpeg,image/png,image/webp" style="padding:.6rem" onchange="prevPhoto(this)">
          <div style="font-size:.68rem;color:var(--t3);margin-top:.25rem">Max 3MB · JPG/PNG/WebP</div>
        </div>
        <div class="fg">
          <label class="lbl">Full Name *</label>
          <input type="text" name="name" class="inp" value="<?= h($profile['name']??'') ?>" placeholder="Your full name" required>
        </div>
        <div class="fg">
          <label class="lbl">Skill / Speciality</label>
          <input type="text" name="skill" class="inp" value="<?= h($profile['skill']??'') ?>" placeholder="e.g. Developer">
        </div>
        <div class="fg">
          <label class="lbl">Profession</label>
          <input type="text" name="profession" class="inp" value="<?= h($profile['profession']??'') ?>" placeholder="e.g. Teacher">
        </div>
        <div class="fg">
          <label class="lbl">Email</label>
          <input type="email" name="email" class="inp" value="<?= h($profile['email']??'') ?>">
        </div>
        <?php if($isAdmin): ?>
        <div class="fg">
          <label class="lbl">Blood Group</label>
          <select name="blood_group" class="inp">
            <option value="">—</option>
            <?php foreach(['A+','A-','B+','B-','AB+','AB-','O+','O-'] as $bg): ?>
            <option value="<?= $bg ?>" <?= $profile['blood_group']===$bg?'selected':'' ?>><?= $bg ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <?php endif; ?>
      </div>

      <!-- Privacy Settings -->
      <div style="margin-top:.8rem;padding:.9rem;background:#F8F9FC;border-radius:12px;margin-bottom:.8rem">
        <h4 style="font-size:.82rem;font-weight:700;color:#3D4F7C;margin-bottom:.7rem;text-transform:uppercase;letter-spacing:.06em">🔒 Privacy Settings</h4>
        <div class="g2">
          <div class="fg">
            <label class="lbl">Who can see my phone?</label>
            <select name="privacy_phone" class="inp">
              <option value="public"  <?= $profile['privacy_phone']==='public' ?'selected':'' ?>>🌐 Everyone</option>
              <option value="members" <?= $profile['privacy_phone']==='members'?'selected':'' ?>>👥 Members Only</option>
              <option value="private" <?= $profile['privacy_phone']==='private'?'selected':'' ?>>🔒 Private (Hidden)</option>
            </select>
          </div>
          <div class="fg">
            <label class="lbl">Who can see my photo?</label>
            <select name="privacy_photo" class="inp">
              <option value="public"  <?= $profile['privacy_photo']==='public' ?'selected':'' ?>>🌐 Everyone</option>
              <option value="members" <?= $profile['privacy_photo']==='members'?'selected':'' ?>>👥 Members Only</option>
              <option value="private" <?= $profile['privacy_photo']==='private'?'selected':'' ?>>🔒 Private (Hidden)</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Blood Donation Availability -->
      <?php if(!empty($profile['blood_group'])): ?>
      <div style="margin-top:1.5rem;padding:1.2rem;background:#fff5f5;border-radius:12px;border:1.5px solid #ffcdd2">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.07em;color:#b71c1c;margin-bottom:.85rem">🩸 BLOOD DONATION STATUS</div>
        <p style="font-size:.8rem;color:#64748b;margin-bottom:.85rem">Set whether you are available to donate blood</p>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.85rem">
          <button type="button" id="btnBldAvail" onclick="setBldAvail(1)"
            style="flex:1;padding:.6rem .9rem;border-radius:10px;font-family:'Inter',sans-serif;font-weight:700;font-size:.82rem;cursor:pointer;border:2px solid;transition:all .2s;background:<?= $bAvail?'#e8f5e9':'#f8fafc' ?>;border-color:<?= $bAvail?'#4caf50':'#e0e7ff' ?>;color:<?= $bAvail?'#1b5e20':'#64748b' ?>">
            ✅ Available to Donate
          </button>
          <button type="button" id="btnBldUnavail" onclick="showUnavailForm()"
            style="flex:1;padding:.6rem .9rem;border-radius:10px;font-family:'Inter',sans-serif;font-weight:700;font-size:.82rem;cursor:pointer;border:2px solid;transition:all .2s;background:<?= !$bAvail?'#ffebee':'#f8fafc' ?>;border-color:<?= !$bAvail?'#ef5350':'#e0e7ff' ?>;color:<?= !$bAvail?'#b71c1c':'#64748b' ?>">
            ❌ Not Available
          </button>
        </div>
        <div id="unavailForm" style="display:<?= !$bAvail?'block':'none' ?>;margin-bottom:.75rem">
          <select id="unavailReason" style="width:100%;padding:.6rem .85rem;border:1.5px solid #ffcdd2;border-radius:9px;font-family:'Inter',sans-serif;font-size:.85rem;margin-bottom:.6rem;background:#fff;color:#1e293b">
            <option value="Recently Donated" <?= ($profile['blood_unavail_reason']??'')==='Recently Donated'?'selected':'' ?>>Recently Donated</option>
            <option value="Abroad" <?= ($profile['blood_unavail_reason']??'')==='Abroad'?'selected':'' ?>>Currently Abroad</option>
            <option value="Unwell" <?= ($profile['blood_unavail_reason']??'')==='Unwell'?'selected':'' ?>>Health Issue / Unwell</option>
            <option value="Medication" <?= ($profile['blood_unavail_reason']??'')==='Medication'?'selected':'' ?>>On Medication</option>
            <option value="Unavailable" <?= ($profile['blood_unavail_reason']??'')==='Unavailable'?'selected':'' ?>>Other Reason</option>
          </select>
          <button type="button" onclick="setBldAvail(0)" style="width:100%;padding:.6rem;background:#b71c1c;color:#fff;border:none;border-radius:9px;font-family:'Inter',sans-serif;font-weight:700;font-size:.84rem;cursor:pointer">Save Status</button>
        </div>
        <div>
          <label style="font-size:.74rem;font-weight:700;color:#64748b;display:block;margin-bottom:.3rem">Last Donation Date (optional)</label>
          <input type="date" id="lastDonDate" value="<?= h($profile['blood_last_donated']??'') ?>"
            style="width:100%;padding:.58rem .9rem;border:1.5px solid #e0e7ff;border-radius:9px;font-family:'Inter',sans-serif;font-size:.85rem;margin-bottom:.5rem">
          <p style="font-size:.72rem;color:#94a3b8">If set, system auto-marks unavailable for 90 days after donation</p>
        </div>
        <div id="bldMsg" style="font-size:.82rem;text-align:center;min-height:1.2em;margin-top:.4rem"></div>
      </div>
      <?php endif; ?>

      <!-- Change Passkey -->
      <div style="margin-top:1.5rem;padding:1.2rem;background:#f8fafc;border-radius:12px;border:1.5px solid #e0e7ff">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.07em;color:#0d47a1;margin-bottom:.75rem">🔑 CHANGE PASSKEY</div>
        <p style="font-size:.8rem;color:#64748b;margin-bottom:.8rem">Choose a new 6-digit passkey for login</p>
        <div style="display:flex;justify-content:center;gap:.55rem;margin-bottom:.75rem" id="profPkDots">
          <?php for($i=0;$i<6;$i++): ?><div style="width:13px;height:13px;border-radius:50%;background:#e0e7ff;border:2px solid #c7d2fe;transition:all .2s" class="ppk-dot"></div><?php endfor; ?>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;max-width:250px;margin:0 auto .85rem">
          <?php foreach(array('1','2','3','4','5','6','7','8','9','del','0','ok') as $pk): ?>
          <button type="button" onclick="profPkTap('<?= $pk ?>')" style="background:<?= $pk==='ok'?'#0d47a1':($pk==='del'?'#fff0f0':'#f4f6fb') ?>;border:1.5px solid <?= $pk==='ok'?'#0d47a1':($pk==='del'?'#fecaca':'#e0e7ff') ?>;border-radius:10px;padding:.6rem;font-size:1.1rem;font-weight:700;color:<?= $pk==='ok'?'#fff':($pk==='del'?'#b71c1c':'#0d1b3e') ?>;cursor:pointer;font-family:Inter,sans-serif"><?= $pk==='del'?'⌫':($pk==='ok'?'✓':$pk) ?></button>
          <?php endforeach; ?>
        </div>
        <div id="pkChgMsg" style="font-size:.82rem;text-align:center;min-height:1.2em"></div>
      </div>

      <button type="submit" name="up" class="btn btn-blue">💾 Save Changes</button>
      <script>
      // Blood availability
    function setBldAvail(avail){
      var reason = avail ? '' : (document.getElementById('unavailReason').value || 'Unavailable');
      var lastDon = document.getElementById('lastDonDate').value || '';
      var m = document.getElementById('bldMsg');
      m.style.color='#0d47a1'; m.textContent='Saving…';
      fetch('',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:'ajax=1&action=set_blood_avail&available='+avail+'&reason='+encodeURIComponent(reason)+'&last_donated='+encodeURIComponent(lastDon)})
      .then(function(r){return r.json();}).then(function(r){
        m.style.color=r.ok?'#16a34a':'#dc2626'; m.textContent=r.ok?'✅ '+r.msg:'❌ '+r.msg;
        // Update button styles
        if(avail){
          document.getElementById('btnBldAvail').style.background='#e8f5e9';document.getElementById('btnBldAvail').style.borderColor='#4caf50';document.getElementById('btnBldAvail').style.color='#1b5e20';
          document.getElementById('btnBldUnavail').style.background='#f8fafc';document.getElementById('btnBldUnavail').style.borderColor='#e0e7ff';document.getElementById('btnBldUnavail').style.color='#64748b';
          document.getElementById('unavailForm').style.display='none';
        } else {
          document.getElementById('btnBldUnavail').style.background='#ffebee';document.getElementById('btnBldUnavail').style.borderColor='#ef5350';document.getElementById('btnBldUnavail').style.color='#b71c1c';
          document.getElementById('btnBldAvail').style.background='#f8fafc';document.getElementById('btnBldAvail').style.borderColor='#e0e7ff';document.getElementById('btnBldAvail').style.color='#64748b';
        }
      }).catch(function(){m.style.color='#dc2626';m.textContent='Error. Try again.';});
    }
    function showUnavailForm(){
      document.getElementById('unavailForm').style.display='block';
    }
    var _ppk='';
      function ppkDots(v){var d=document.querySelectorAll('.ppk-dot');d.forEach(function(x,i){x.style.background=i<v.length?'#0d47a1':'#e0e7ff';x.style.borderColor=i<v.length?'#0d47a1':'#c7d2fe';x.style.transform=i<v.length?'scale(1.18)':'scale(1)';})}
      function profPkTap(d){
        if(d==='del'){_ppk=_ppk.slice(0,-1);ppkDots(_ppk);}
        else if(d==='ok'){
          if(_ppk.length<6){document.querySelectorAll('.ppk-dot').forEach(function(x){x.style.background='#ef5350';x.style.borderColor='#ef5350';});return;}
          var m=document.getElementById('pkChgMsg');
          m.style.color='#0d47a1';m.textContent='Saving…';
          fetch('',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'ajax=1&action=change_passkey&passkey='+encodeURIComponent(_ppk)})
          .then(function(r){return r.json();}).then(function(r){
            m.style.color=r.ok?'#16a34a':'#dc2626';m.textContent=r.ok?'✅ '+r.msg:'❌ '+r.msg;
            _ppk='';ppkDots('');
          }).catch(function(){m.style.color='#dc2626';m.textContent='Network error.';});
        } else {
          if(_ppk.length>=6)return;_ppk+=d;ppkDots(_ppk);
          if(_ppk.length===6)setTimeout(function(){profPkTap('ok');},160);
        }
      }
      </script>
    </form>
  </div>
</div>
</div>
<?php endif; ?>

</div><!-- /section -->

<style>
:root{--t3:#7A8DB5}
.fg{margin-bottom:.9rem}
.lbl{display:block;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#4A5E8A;margin-bottom:.38rem}
.inp{width:100%;padding:.68rem .9rem;border:2px solid #E8ECF4;border-radius:9px;font-family:'DM Sans',sans-serif;font-size:.9rem;color:#0D1B3E;background:#fff;outline:none;-webkit-appearance:none;transition:border-color .18s}
.inp:focus{border-color:#0D47A1;box-shadow:0 0 0 3px rgba(13,71,161,.1)}
select.inp{cursor:pointer}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}
@media(max-width:500px){.g2{grid-template-columns:1fr}}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.4rem;padding:.65rem 1.2rem;border-radius:9px;font-family:'DM Sans',sans-serif;font-weight:700;font-size:.86rem;cursor:pointer;border:2px solid transparent;transition:all .2s;text-decoration:none}
.btn-blue{background:#0D47A1;color:#fff;border-color:#0D47A1}.btn-blue:hover{background:#0a3880}
.btn-green{background:#25D366;color:#fff}.btn-green:hover{background:#128C7E}
.btn-grey{background:#F4F6FB;color:#4A5E8A;border-color:#E8ECF4}.btn-grey:hover{background:#E8ECF4}
.btn-sm{padding:.36rem .75rem;font-size:.76rem}
.card{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(13,71,161,.1);border:1px solid #E8ECF4;overflow:hidden}
.card-header{background:linear-gradient(135deg,#0D47A1,#1565C0);color:#fff;padding:.9rem 1.1rem}
.card-header h3{font-size:.95rem;font-weight:700}
.card-body{padding:1.2rem}
.alert-ok{background:#E8F5E9;color:#1B5E20;border-left:4px solid #4CAF50;padding:.75rem 1rem;border-radius:9px;margin-bottom:.9rem;font-size:.84rem;font-weight:600}
</style>

<script>
function prevPhoto(input) {
  // Preview not needed here since it's not on the ID card page
}
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
