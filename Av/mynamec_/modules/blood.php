<?php
// modules/blood.php — PHP 7.3+ compatible
require_once __DIR__ . '/../includes/config.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '🩸 Blood Hub — Aishwarya Arts & Sports Club',
  'desc'  => 'Find blood donors by blood group — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/blood.php',
];
requireLogin();
$user = currentUser();
$pageTitle = 'Blood Hub — ' . setting('CLUB_NAME','Aishwarya Arts & Sports Club');

// Add blood availability columns if not exist
try { db()->exec("ALTER TABLE users ADD COLUMN blood_available TINYINT(1) DEFAULT 1"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE users ADD COLUMN blood_last_donated DATE DEFAULT NULL"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE users ADD COLUMN blood_unavail_reason VARCHAR(100) DEFAULT NULL"); } catch(Exception $e){}

$bg  = isset($_GET['bg']) ? $_GET['bg'] : '';
$msg = '';

// Submit blood request + build WhatsApp notification links
$waNotifyLinks = array();
$reqBloodGroup = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['req_blood'])) {
    $reqBG       = trim($_POST['need_bg'] ?? '');
    $reqPatient  = trim($_POST['patient']  ?? '');
    $reqHospital = trim($_POST['hospital'] ?? '');
    $reqUrgency  = in_array($_POST['urgency']??'', ['high','medium','low']) ? $_POST['urgency'] : 'high';

    if ($reqBG) {
        db()->prepare('INSERT INTO blood_requests(requested_by,blood_group,patient_name,hospital,urgency)VALUES(?,?,?,?,?)')
           ->execute(array($user['id'], $reqBG, $reqPatient, $reqHospital, $reqUrgency));

        // Build notification message
        $urgEmoji = $reqUrgency==='high' ? '🚨' : ($reqUrgency==='medium' ? '⚠️' : 'ℹ️');
        $notifMsg = $urgEmoji." *BLOOD REQUEST — ".strtoupper($reqBG)."*

"
            . "📍 Club: ".setting('CLUB_NAME','Aishwarya Arts & Sports Club')."
"
            . "🩸 Blood Group: *".$reqBG."*
"
            . ($reqPatient  ? "🏥 Patient: *".$reqPatient."*
"  : "")
            . ($reqHospital ? "📍 Hospital: *".$reqHospital."*
" : "")
            . "⚡ Urgency: ".ucfirst($reqUrgency)."
"
            . "📞 Requested by: ".$user['name']."

"
            . "Please contact: ".setting('CLUB_PHONE','')."
"
            . "If you can donate, reply to this message.

"
            . "— ".setting('CLUB_NAME','Aishwarya Arts & Sports Club');

        // Find all matching available donors
        $donorStmt = db()->prepare("SELECT name, whatsapp_number FROM users
            WHERE status='active' AND blood_group=? AND id != ?
            AND blood_available=1
            AND (blood_last_donated IS NULL OR DATEDIFF(CURDATE(),blood_last_donated)>=90)");
        $donorStmt->execute(array($reqBG, $user['id']));
        $notifyDonors = $donorStmt->fetchAll();

        // Also notify admin/secretary
        $admins = db()->query("SELECT name,whatsapp_number FROM users
            WHERE status='active' AND role IN ('president','secretary','vice_president','treasurer')
            AND whatsapp_number IS NOT NULL")->fetchAll();

        foreach (array_merge($notifyDonors, $admins) as $nd) {
            $wn = preg_replace('/\D/', '', $nd['whatsapp_number'] ?? '');
            if ($wn) {
                $waNotifyLinks[] = array(
                    'name' => $nd['name'],
                    'link' => 'https://wa.me/'.$wn.'?text='.rawurlencode($notifMsg),
                );
            }
        }

        $reqBloodGroup = $reqBG;
        $donorCount = count($notifyDonors);
        $msg = array(
            't' => 'ok',
            'm' => '✅ Blood request submitted! '
                .($donorCount > 0
                    ? 'Found '.$donorCount.' matching donor(s). Tap the buttons below to notify them on WhatsApp.'
                    : 'No matching donors found right now. Admin has been notified.'),
        );
    }
}

// Secretary WhatsApp broadcast links
$broadcastLinks = array();
$broadcastMsg   = '';
if (isAdminRole($user['role']) && !empty($bg)) {
    $dstmt = db()->prepare("SELECT * FROM users WHERE status='active' AND blood_group=? ORDER BY name");
    $dstmt->execute(array($bg));
    $donorList = $dstmt->fetchAll();
    $broadcastMsg = urlencode(
        "🚨 *EMERGENCY BLOOD REQUEST*\n\n" .
        "*" . setting('CLUB_NAME','Aishwarya Arts & Sports Club') . "*\n" .
        "━━━━━━━━━━━━━━━━━━\n" .
        "🩸 Blood Group Needed: *{$bg}*\n" .
        "⚠️ Urgency: High\n" .
        "📞 Contact: " . setting('CLUB_PHONE','') . "\n" .
        "━━━━━━━━━━━━━━━━━━\n" .
        "Please respond if you can donate.\n" .
        "— " . setting('CLUB_NAME','Aishwarya Arts & Sports Club')
    );
    foreach ($donorList as $d) {
        $wn = preg_replace('/\D/', '', $d['whatsapp_number']);
        $broadcastLinks[] = array(
            'name'  => $d['name'],
            'phone' => $d['whatsapp_number'],
            'wn'    => $wn,
            'link'  => 'https://wa.me/' . $wn . '?text=' . $broadcastMsg,
        );
    }
}

// Blood group counts
$bgCountsRaw = db()->query("SELECT blood_group, COUNT(*) total,
    SUM(blood_available=1 AND (blood_last_donated IS NULL OR DATEDIFF(CURDATE(),blood_last_donated)>=90)) available
    FROM users WHERE status='active' AND blood_group IS NOT NULL GROUP BY blood_group")->fetchAll();
$bgCounts = array();
$bgAvail   = array();
foreach ($bgCountsRaw as $r) {
    $bgCounts[$r['blood_group']] = (int)$r['total'];
    $bgAvail[$r['blood_group']]  = (int)$r['available'];
}

// Donors list
$q = "SELECT id,name,whatsapp_number,blood_group,skill,role,privacy_phone,blood_available,blood_last_donated,blood_unavail_reason FROM users WHERE status='active' AND blood_group IS NOT NULL";
$p = array();
if ($bg) { $q .= " AND blood_group=?"; $p[] = $bg; }
$q .= " ORDER BY blood_group, name";
$stmt = db()->prepare($q);
$stmt->execute($p);
$donors = $stmt->fetchAll();

require_once __DIR__ . '/../includes/header.php';
?>

<style>
/* ══ BLOOD HUB APP ══════════════════════════════════════ */
.bh-shell{background:#f5f6fa;min-height:100vh;padding-bottom:5rem}

/* Header */
.bh-header{background:linear-gradient(145deg,#7f0000,#b71c1c,#c62828);
  padding:1.4rem 1.2rem 3.5rem;position:relative;overflow:hidden}
.bh-header::before{content:'🩸';position:absolute;right:-1rem;top:-1rem;
  font-size:9rem;opacity:.08}
.bh-title{font-family:'Bebas Neue',sans-serif;font-size:1.9rem;
  letter-spacing:.1em;color:#fff;line-height:1}
.bh-title span{color:#ffcdd2;font-size:1rem;font-weight:400;
  font-family:'Inter',sans-serif;letter-spacing:.05em;display:block;margin-top:.2rem}
.bh-hstats{display:flex;gap:.6rem;margin-top:1rem}
.bh-hstat{background:rgba(255,255,255,.15);backdrop-filter:blur(8px);
  border:1px solid rgba(255,255,255,.2);border-radius:12px;
  padding:.5rem .8rem;text-align:center;flex:1}
.bh-hstat-n{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;
  color:#fff;line-height:1}
.bh-hstat-l{font-size:.55rem;color:rgba(255,255,255,.6);
  text-transform:uppercase;letter-spacing:.09em;font-weight:700}

/* Floating blood group card */
.bh-bg-card{background:#fff;border-radius:20px 20px 0 0;
  margin-top:-2rem;position:relative;z-index:2;
  padding:1.2rem 1rem .5rem;
  box-shadow:0 -4px 20px rgba(0,0,0,.1)}

/* Blood group grid */
.bh-bg-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;
  margin-bottom:.5rem}
.bh-bg-btn{border-radius:14px;padding:.75rem .4rem;text-align:center;
  cursor:pointer;border:2px solid #fecdd3;background:#fff;
  transition:all .2s;-webkit-tap-highlight-color:transparent;position:relative}
.bh-bg-btn:active{transform:scale(.94)}
.bh-bg-btn.on{background:linear-gradient(145deg,#b71c1c,#c62828);
  border-color:transparent;box-shadow:0 4px 16px rgba(183,28,28,.4)}
.bh-bg-btn.has-donors{border-color:#ef9a9a;background:#fff5f5}
.bh-bg-group{font-family:'Bebas Neue',sans-serif;font-size:1.4rem;
  color:#b71c1c;line-height:1}
.bh-bg-btn.on .bh-bg-group{color:#fff}
.bh-bg-count{font-size:.6rem;color:#94a3b8;font-weight:700;margin-top:.15rem}
.bh-bg-btn.on .bh-bg-count{color:rgba(255,255,255,.7)}
.bh-avail-dot{width:7px;height:7px;border-radius:50%;background:#4caf50;
  display:inline-block;margin-right:.2rem}

/* Search bar */
.bh-search{display:flex;align-items:center;gap:.6rem;
  background:#fff;border-radius:14px;padding:.7rem 1rem;
  box-shadow:0 2px 10px rgba(0,0,0,.07);margin:.9rem 1rem .7rem;
  border:1.5px solid #f0f0f0}
.bh-search input{flex:1;border:none;outline:none;font-family:'Inter',sans-serif;
  font-size:.88rem;color:#0d1b3e;background:transparent}
.bh-search input::placeholder{color:#bcc4cf}

/* Donor cards */
.bh-donors{padding:0 1rem}
.bh-donor{background:#fff;border-radius:16px;padding:.9rem 1rem;
  margin-bottom:.55rem;box-shadow:0 2px 12px rgba(0,0,0,.07);
  display:grid;grid-template-columns:auto 1fr auto;
  gap:.75rem;align-items:center;
  border-left:4px solid #4caf50;
  transition:all .2s;-webkit-tap-highlight-color:transparent}
.bh-donor.unavail{border-left-color:#ef5350}
.bh-donor:active{transform:scale(.98)}

/* Blood badge */
.bh-blood-badge{width:46px;height:46px;border-radius:12px;
  background:linear-gradient(145deg,#ffebee,#ffcdd2);
  border:2px solid #ef9a9a;
  display:flex;align-items:center;justify-content:center;flex-shrink:0}
.bh-blood-badge.unavail{background:#f5f5f5;border-color:#e0e0e0}
.bh-blood-text{font-family:'Bebas Neue',sans-serif;font-size:1.1rem;
  color:#b71c1c;line-height:1}
.bh-blood-badge.unavail .bh-blood-text{color:#9e9e9e}

/* Donor info */
.bh-dname{font-weight:800;font-size:.9rem;color:#0d1b3e;
  margin-bottom:.3rem;line-height:1.25}
.bh-dmeta{display:flex;align-items:center;gap:.35rem;flex-wrap:wrap}
.bh-role-badge{font-size:.58rem;font-weight:800;color:#fff;
  background:#0d47a1;border-radius:20px;padding:.1rem .5rem;
  white-space:nowrap}
.bh-status{display:inline-flex;align-items:center;gap:.22rem;
  font-size:.63rem;font-weight:700;border-radius:20px;
  padding:.1rem .5rem;border:1px solid}
.bh-status.avail{color:#1b5e20;background:#e8f5e9;border-color:#a5d6a7}
.bh-status.unavail{color:#b71c1c;background:#ffebee;border-color:#ef9a9a}
.bh-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.bh-date{font-size:.6rem;color:#94a3b8}

/* WA Emergency button */
.bh-wa-btn{flex-shrink:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:.18rem;
  background:linear-gradient(145deg,#25d366,#1ebe5d);
  color:#fff;border-radius:12px;padding:.6rem .7rem;
  text-decoration:none;box-shadow:0 3px 12px rgba(37,211,102,.4);
  min-width:54px;transition:all .2s}
.bh-wa-btn:active{transform:scale(.93)}
.bh-wa-btn i{font-size:1.15rem}
.bh-wa-btn span{font-size:.58rem;font-weight:800;letter-spacing:.02em}
.bh-private{font-size:.7rem;color:#bcc4cf;padding:.4rem}

/* Secretary broadcast panel */
.bh-broadcast{background:linear-gradient(135deg,#e8f5e9,#f1f8e9);
  border:2px solid #4caf50;border-radius:16px;
  padding:1rem 1.1rem;margin:0 1rem .9rem}
.bh-broadcast-title{font-family:'Bebas Neue',sans-serif;font-size:1rem;
  letter-spacing:.06em;color:#1b5e20;margin-bottom:.7rem}
.bh-wa-chip{display:inline-flex;align-items:center;gap:.3rem;
  background:#25d366;color:#fff;border-radius:20px;
  padding:.35rem .85rem;font-size:.74rem;font-weight:700;
  text-decoration:none;margin:.2rem;
  box-shadow:0 2px 8px rgba(37,211,102,.3)}

/* Alert */
.bh-alert{margin:0 1rem .9rem;border-radius:14px;
  padding:.85rem 1rem;font-size:.84rem;font-weight:600;
  display:flex;align-items:flex-start;gap:.6rem}
.bh-alert.ok{background:#e8f5e9;border:1.5px solid #a5d6a7;color:#1b5e20}
.bh-alert.err{background:#ffebee;border:1.5px solid #ef9a9a;color:#b71c1c}
.bh-alert.info{background:#e3f2fd;border:1.5px solid #90caf9;color:#0d47a1}

/* Request form */
.bh-form-card{background:#fff;border-radius:20px;
  overflow:hidden;margin:0 1rem;
  box-shadow:0 4px 20px rgba(0,0,0,.1)}
.bh-form-head{background:linear-gradient(135deg,#b71c1c,#c62828);
  padding:.9rem 1.1rem;display:flex;align-items:center;gap:.6rem;cursor:pointer}
.bh-form-title{font-family:'Bebas Neue',sans-serif;font-size:1rem;
  letter-spacing:.07em;color:#fff}
.bh-form-body{padding:1.1rem}
.bh-fg2{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.65rem}
.bh-inp{width:100%;padding:.65rem .9rem;border:1.5px solid #e8ecf4;
  border-radius:12px;font-family:'Inter',sans-serif;font-size:.88rem;
  color:#0d1b3e;outline:none;transition:border-color .2s;background:#f8fafc}
.bh-inp:focus{border-color:#b71c1c;background:#fff}
.bh-lbl{font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:#64748b;display:block;margin-bottom:.28rem}
.bh-submit{width:100%;padding:.85rem;background:linear-gradient(135deg,#b71c1c,#c62828);
  color:#fff;border:none;border-radius:14px;
  font-family:'Inter',sans-serif;font-weight:800;font-size:.92rem;
  cursor:pointer;box-shadow:0 6px 22px rgba(183,28,28,.4);
  display:flex;align-items:center;justify-content:center;gap:.5rem;
  transition:all .25s}
.bh-submit:active{transform:scale(.97)}

/* Section label */
.bh-sec-lbl{font-size:.68rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.12em;color:#94a3b8;margin:.9rem 1rem .5rem;
  display:flex;align-items:center;gap:.5rem}
.bh-sec-lbl::after{content:'';flex:1;height:1.5px;
  background:linear-gradient(90deg,#e0e7ff,transparent)}
</style>

<div class="bh-shell">

<!-- ── App Header ── -->
<div class="bh-header">
  <div class="bh-title">
    🩸 Blood Hub
    <span><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?> · Emergency Network</span>
  </div>
  <?php
    $totalDonors = 0; $availDonors = 0;
    foreach($bgCounts as $bg2=>$cnt){ $totalDonors += $cnt; }
    foreach($bgAvail as $bg2=>$cnt){ $availDonors += $cnt; }
    $totalReqs = 0;
    try { $totalReqs = db()->query("SELECT COUNT(*) FROM blood_requests")->fetchColumn(); } catch(Exception $e){}
  ?>
  <div class="bh-hstats">
    <div class="bh-hstat">
      <div class="bh-hstat-n"><?= $totalDonors ?></div>
      <div class="bh-hstat-l">Donors</div>
    </div>
    <div class="bh-hstat">
      <div class="bh-hstat-n" style="color:#a5d6a7"><?= $availDonors ?></div>
      <div class="bh-hstat-l">Available</div>
    </div>
    <div class="bh-hstat">
      <div class="bh-hstat-n" style="color:#ef9a9a"><?= $totalReqs ?></div>
      <div class="bh-hstat-l">Requests</div>
    </div>
    <div class="bh-hstat">
      <div class="bh-hstat-n"><?= count($bgCounts) ?></div>
      <div class="bh-hstat-l">Groups</div>
    </div>
  </div>
</div>

<!-- ── Blood Group Filter ── -->
<div class="bh-bg-card">
  <div style="font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;color:#b71c1c;margin-bottom:.75rem;display:flex;align-items:center;gap:.4rem">
    <span style="width:8px;height:8px;border-radius:50%;background:#b71c1c;animation:pulse 1.8s infinite"></span>
    Select Blood Group
  </div>
  <div class="bh-bg-grid">
    <div onclick="location='<?= url('modules/blood.php') ?>'"
      class="bh-bg-btn <?= !$bg?'on':'' ?> <?= $totalDonors>0?'has-donors':'' ?>">
      <div class="bh-bg-group">ALL</div>
      <div class="bh-bg-count"><?= $totalDonors ?> donors</div>
    </div>
    <?php foreach(array('A+','A-','B+','B-','AB+','AB-','O+','O-') as $g):
      $cnt  = $bgCounts[$g] ?? 0;
      $avl  = $bgAvail[$g]  ?? 0;
    ?>
    <div onclick="location='<?= url('modules/blood.php') ?>?bg=<?= urlencode($g) ?>'"
      class="bh-bg-btn <?= $bg===$g?'on':'' ?> <?= $cnt>0?'has-donors':'' ?>">
      <div class="bh-bg-group"><?= $g ?></div>
      <div class="bh-bg-count">
        <?php if($avl > 0): ?><span class="bh-avail-dot"></span><?= $avl ?>✓/<?php endif; ?><?= $cnt ?>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
</div>

<!-- ── Messages ── -->
<?php if($msg): ?>
<div class="bh-alert <?= $msg['t']==='ok'?'ok':'err' ?>">
  <span style="font-size:1.2rem"><?= $msg['t']==='ok'?'✅':'❌' ?></span>
  <div>
    <div><?= h($msg['m']) ?></div>
    <?php if(!empty($waNotifyLinks)): ?>
    <div style="margin-top:.75rem">
      <div style="font-size:.7rem;font-weight:700;color:#166534;margin-bottom:.5rem">📲 TAP TO NOTIFY DONORS:</div>
      <div style="display:flex;flex-wrap:wrap;gap:.35rem">
        <?php foreach($waNotifyLinks as $wl): ?>
        <a href="<?= h($wl['link']) ?>" target="_blank" class="bh-wa-chip">
          <i class="fab fa-whatsapp"></i> <?= h($wl['name']) ?>
        </a>
        <?php endforeach; ?>
      </div>
      <div style="font-size:.7rem;color:#4caf50;margin-top:.5rem">💡 Tap name → WhatsApp opens → press Send</div>
    </div>
    <?php endif; ?>
  </div>
</div>
<?php endif; ?>

<!-- ── Secretary Broadcast ── -->
<?php if(isAdminRole($user['role']) && !empty($bg) && !empty($broadcastLinks)): ?>
<div class="bh-broadcast">
  <div class="bh-broadcast-title">📤 SEND TO ALL <?= h($bg) ?> DONORS (<?= count($broadcastLinks) ?>)</div>
  <div>
    <?php foreach($broadcastLinks as $d): ?>
    <a href="<?= $d['link'] ?>" target="_blank" class="bh-wa-chip">
      <i class="fab fa-whatsapp"></i> <?= h($d['name']) ?>
    </a>
    <?php endforeach; ?>
  </div>
</div>
<?php elseif(isAdminRole($user['role']) && !empty($bg)): ?>
<div class="bh-alert err">❌ No <?= h($bg) ?> donors found.</div>
<?php elseif(isAdminRole($user['role'])): ?>
<div class="bh-alert info">ℹ️ Select a blood group to send emergency WhatsApp to all matching donors.</div>
<?php endif; ?>

<!-- ── Donor count ── -->
<?php if($bg): ?>
<div class="bh-sec-lbl">🩸 <?= h($bg) ?> Donors (<?= count($donors) ?>)
  <a href="<?= url('modules/blood.php') ?>" style="font-size:.68rem;color:#b71c1c;font-weight:700;text-decoration:none;margin-left:.3rem">× Clear</a>
</div>
<?php else: ?>
<div class="bh-sec-lbl">All Donors (<?= count($donors) ?>)</div>
<?php endif; ?>

<!-- ── Search ── -->
<div class="bh-search" style="margin:0 1rem .7rem">
  <i class="fas fa-search" style="color:#bcc4cf;font-size:.9rem"></i>
  <input type="text" id="dsearch" placeholder="Search donor name…" oninput="filterDonors(this.value)">
</div>

<!-- ── Donor Cards ── -->
<div class="bh-donors" id="dtb">
  <?php if(empty($donors)): ?>
  <div style="background:#fff;border-radius:16px;padding:2.5rem;text-align:center;color:#94a3b8">
    <div style="font-size:2.5rem;margin-bottom:.5rem">🩸</div>
    <div style="font-weight:700;font-size:.9rem">No donors found</div>
    <div style="font-size:.78rem;margin-top:.3rem">Members can add their blood group in Profile</div>
  </div>
  <?php else: foreach($donors as $d):
    $isAvail = isset($d['blood_available']) ? (bool)$d['blood_available'] : true;
    if($isAvail && !empty($d['blood_last_donated']) && (time()-strtotime($d['blood_last_donated'])) < 90*86400) $isAvail=false;
    $canPhone = isAdminRole($user['role']) || (isset($d['privacy_phone']) && $d['privacy_phone'] !== 'private');
    $wn  = preg_replace('/\D/', '', $d['whatsapp_number']);
    $em  = urlencode('🩸 Emergency — Need '.$d['blood_group'].' blood urgently. Contact: '.setting('CLUB_PHONE',''));
    $rl  = ucwords(str_replace('_',' ',$d['role']??'Member'));
  ?>
  <div class="bh-donor <?= $isAvail?'':'unavail' ?>" data-n="<?= h(strtolower($d['name'])) ?>">
    <!-- Blood badge -->
    <div class="bh-blood-badge <?= $isAvail?'':'unavail' ?>">
      <span class="bh-blood-text"><?= h($d['blood_group']) ?></span>
    </div>
    <!-- Info -->
    <div>
      <a href="<?= url('modules/profile.php') ?>?id=<?= $d['id'] ?>" style="text-decoration:none">
        <div class="bh-dname"><?= h($d['name']) ?></div>
      </a>
      <div class="bh-dmeta">
        <span class="bh-role-badge"><?= h($rl) ?></span>
        <span class="bh-status <?= $isAvail?'avail':'unavail' ?>">
          <span class="bh-dot" style="background:<?= $isAvail?'#4caf50':'#ef5350' ?>"></span>
          <?= $isAvail ? 'Available' : h($d['blood_unavail_reason']??'Unavailable') ?>
        </span>
        <?php if(!empty($d['blood_last_donated'])): ?>
        <span class="bh-date">Last: <?= date('d M Y',strtotime($d['blood_last_donated'])) ?></span>
        <?php endif; ?>
      </div>
    </div>
    <!-- WA Button -->
    <?php if($canPhone): ?>
    <a href="https://wa.me/<?= $wn ?>?text=<?= $em ?>" target="_blank" class="bh-wa-btn">
      <i class="fab fa-whatsapp"></i>
      <span>Emergency</span>
    </a>
    <?php else: ?>
    <div class="bh-private">🔒</div>
    <?php endif; ?>
  </div>
  <?php endforeach; endif; ?>
</div>

<!-- ── Submit Request Form ── -->
<div style="height:.8rem"></div>
<div class="bh-form-card">
  <div class="bh-form-head" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
    <span style="font-size:1.3rem">🚑</span>
    <span class="bh-form-title">Submit Emergency Blood Request</span>
    <i class="fas fa-chevron-down" style="color:rgba(255,255,255,.7);margin-left:auto;font-size:.85rem"></i>
  </div>
  <div class="bh-form-body">
    <form method="POST" action="<?= url('modules/blood.php') ?>">
      <div class="bh-fg2">
        <div>
          <label class="bh-lbl">Blood Group *</label>
          <select name="need_bg" class="bh-inp" required>
            <option value="">— Select —</option>
            <?php foreach(array('A+','A-','B+','B-','AB+','AB-','O+','O-') as $g): ?>
            <option value="<?= $g ?>" <?= (isset($_POST['need_bg'])&&$_POST['need_bg']===$g)?'selected':'' ?>><?= $g ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div>
          <label class="bh-lbl">Urgency</label>
          <select name="urgency" class="bh-inp">
            <option value="high">🔴 High</option>
            <option value="medium">🟡 Medium</option>
            <option value="low">🟢 Low</option>
          </select>
        </div>
        <div>
          <label class="bh-lbl">Patient Name</label>
          <input type="text" name="patient" class="bh-inp" placeholder="Patient name">
        </div>
        <div>
          <label class="bh-lbl">Hospital</label>
          <input type="text" name="hospital" class="bh-inp" placeholder="Hospital name">
        </div>
      </div>
      <button type="submit" name="req_blood" class="bh-submit">
        <i class="fas fa-heart-pulse"></i> Submit Blood Request
      </button>
    </form>
  </div>
</div>

</div><!-- /bh-shell -->

<style>
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.7)}}
</style>
<script>
function filterDonors(q){
  q=(q||'').toLowerCase();
  document.querySelectorAll('#dtb .bh-donor').forEach(function(c){
    c.style.display=(!q||c.dataset.n.indexOf(q)!==-1)?'':'none';
  });
}
function sendToAll(){
  <?php if(!empty($broadcastLinks)): ?>
  var links=<?= json_encode(array_column($broadcastLinks,'link')) ?>;
  var i=0;
  function next(){if(i<links.length){window.open(links[i],'_blank');i++;setTimeout(next,800);}}
  next();
  <?php endif; ?>
}
</script>

<?php require_once __DIR__ . '/../includes/footer.php'; ?>
