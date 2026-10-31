<?php
// modules/members.php — Members Directory with Role Separation
require_once __DIR__.'/../includes/config.php';
// OG tags for WhatsApp/Facebook share
$pageOG = [
  'title' => '👥 Members — Aishwarya Arts & Sports Club',
  'desc'  => 'Club members directory — Aishwarya Arts & Sports Club, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/members.php',
];
$isLoggedIn = isLoggedIn();
$user = $isLoggedIn ? currentUser() : null;
$pageTitle = 'Members — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');

// Fetch all active members grouped by role
$allMembers = db()->query("
    SELECT * FROM users WHERE status='active'
    ORDER BY FIELD(role,'president','vice_president','secretary','joint_secretary','treasurer','committee_member','member'), name
")->fetchAll();

// Separate into groups
$executives   = array_filter($allMembers, function($m){ return in_array($m['role'], array('president','vice_president','secretary','joint_secretary','treasurer')); });
$committee    = array_filter($allMembers, function($m){ return $m['role'] === 'committee_member'; });
$generalMembers = array_filter($allMembers, function($m){ return $m['role'] === 'member'; });

$pageOG = [
  'title' => '👥 Members — Aishwarya Arts & Sports Club',
  'desc'  => 'Our club members — Aishwarya Arts & Sports Club, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/members.php',
];
require_once __DIR__.'/../includes/header.php';

function renderMemberCard($m, $user, $size = 'normal') {
    $canSeePhoto = ($user && isAdminRole(($user ? $user['role'] : 'guest'))) || $m['privacy_photo'] !== 'private';
    $canSeePhone = ($user && isAdminRole(($user ? $user['role'] : 'guest'))) || $m['privacy_phone'] !== 'private';
    $photoB64 = $canSeePhoto ? getMemberPhoto($m['profile_photo']) : '';
    $wn = preg_replace('/\D/','',$m['whatsapp_number']);
    $isOwn = ($m['id'] === ($user ? $user['id'] : 0));

    $roleColors = [
        'president'       => '#B8860B',
        'vice_president'  => '#8B6914',
        'secretary'       => '#0F766E',
        'joint_secretary' => '#107D74',
        'treasurer'       => '#2E7D32',
        'committee_member'=> '#7B1FA2',
        'member'          => '#546E7A',
    ];
    $borderColor = $roleColors[$m['role']] ?? '#546E7A';

    if ($size === 'large') {
        // Executive card - larger
        echo '<a href="'.url('modules/profile.php').'?id='.$m['id'].'" style="display:block;text-decoration:none">';
        echo '<div style="background:#fff;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,.1);overflow:hidden;transition:all .22s;border-top:4px solid '.$borderColor.'" class="mc">';
        echo '<div style="padding:1.5rem 1.2rem;text-align:center">';
        if ($photoB64) {
            echo '<img src="'.$photoB64.'" style="width:90px;height:90px;border-radius:50%;object-fit:cover;border:3px solid '.$borderColor.';margin:0 auto .8rem;display:block" alt="">';
        } else {
            echo '<div style="width:90px;height:90px;border-radius:50%;background:'.($canSeePhoto?'#E6F4F2':'#F5F5F5').';border:3px solid '.$borderColor.';margin:0 auto .8rem;display:flex;align-items:center;justify-content:center;font-size:2rem">'.($canSeePhoto?'👤':'🔒').'</div>';
        }
        echo '<div style="font-weight:700;font-size:1rem;color:#10201F;margin-bottom:.2rem">'.h($m['name']).'</div>';
        echo '<div style="font-size:.75rem;color:#7A8DB5;margin-bottom:.5rem">'.h($m['committee_position']??roleLabel($m['role'])).'</div>';
        echo '<span style="display:inline-block;padding:.2rem .7rem;border-radius:20px;font-size:.65rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;background:'.$borderColor.'22;color:'.$borderColor.';border:1px solid '.$borderColor.'44">'.h(roleLabel($m['role'])).'</span>';
        if ($m['blood_group']) echo '<div style="font-size:.72rem;color:#B71C1C;font-weight:700;margin-top:.4rem">🩸 '.h($m['blood_group']).'</div>';
        echo '</div>';
        if ($canSeePhone) {
            echo '<div style="padding:.6rem 1.2rem;background:#F6F8F8;border-top:1px solid #E2E8E7;text-align:center">';
            echo '<a href="https://wa.me/'.$wn.'" target="_blank" style="color:#25D366;font-size:.78rem;font-weight:700;text-decoration:none">💬 '.h($m['whatsapp_number']).'</a>';
            echo '</div>';
        }
        echo '</div></a>';
    } else {
        // Normal member card
        echo '<a href="'.url('modules/profile.php').'?id='.$m['id'].'" style="display:block;text-decoration:none">';
        echo '<div style="background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.08);padding:1.1rem .9rem;text-align:center;border-top:3px solid '.$borderColor.';transition:all .2s" class="mc" data-n="'.strtolower(h($m['name'])).'">';
        if ($photoB64) {
            echo '<img src="'.$photoB64.'" style="width:64px;height:64px;border-radius:50%;object-fit:cover;border:2.5px solid '.$borderColor.';margin:0 auto .6rem;display:block" alt="">';
        } else {
            echo '<div style="width:64px;height:64px;border-radius:50%;background:'.($canSeePhoto?'#E6F4F2':'#F5F5F5').';border:2.5px solid '.$borderColor.';margin:0 auto .6rem;display:flex;align-items:center;justify-content:center;font-size:1.5rem">'.($canSeePhoto?'👤':'🔒').'</div>';
        }
        echo '<div style="font-weight:700;font-size:.88rem;color:#10201F;margin-bottom:.2rem">'.h($m['name']).'</div>';
        echo '<div style="font-size:.7rem;color:#7A8DB5;margin-bottom:.4rem">'.h($m['committee_position']??roleLabel($m['role'])).'</div>';
        if ($m['skill']) echo '<div style="font-size:.7rem;background:#E6F4F2;color:#0A1A1F;border-radius:20px;padding:.12rem .5rem;display:inline-block;margin-bottom:.3rem">'.h($m['skill']).'</div>';
        if ($m['blood_group']) echo '<div style="font-size:.68rem;color:#B71C1C;font-weight:700;margin-bottom:.3rem">🩸 '.h($m['blood_group']).'</div>';
        echo '</div></a>';
    }
}
?>

<div class="hero" style="padding:2rem 1.2rem 1.8rem">
  <h1>CLUB <span>MEMBERS</span></h1>
  <div class="hero-place"><?= count($allMembers) ?> Active Members · <?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></div>
</div>
<div class="red-bar"></div>

<div class="section">

  <!-- Search -->
  <div style="display:flex;gap:.6rem;margin-bottom:1.5rem;flex-wrap:wrap">
    <input type="text" id="msearch" style="flex:1;min-width:180px;padding:.68rem .9rem;border:2px solid #E2E8E7;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none;transition:border-color .18s" placeholder="🔍 Search any member…" oninput="searchMembers(this.value)">
    <a href="#executives" style="padding:.6rem 1rem;background:#B8860B22;color:#7a5a08;border:1px solid #B8860B44;border-radius:9px;font-size:.8rem;font-weight:700;text-decoration:none">⭐ Executive</a>
    <a href="#committee" style="padding:.6rem 1rem;background:#7B1FA222;color:#7B1FA2;border:1px solid #7B1FA244;border-radius:9px;font-size:.8rem;font-weight:700;text-decoration:none">🏛 Committee</a>
    <a href="#members" style="padding:.6rem 1rem;background:#0F766E22;color:#0F766E;border:1px solid #0F766E44;border-radius:9px;font-size:.8rem;font-weight:700;text-decoration:none">👥 Members</a>
  </div>

  <!-- ════ SECTION 1: EXECUTIVE COMMITTEE ════════════════════ -->
  <?php if(!empty($executives)): ?>
  <div id="executives" style="margin-bottom:2.5rem">
    <div style="display:flex;align-items:center;gap:.8rem;margin-bottom:1.2rem">
      <div style="background:linear-gradient(135deg,#B8860B,#DAA520);color:#fff;border-radius:10px;padding:.4rem .85rem;font-family:'Bebas Neue',sans-serif;font-size:.95rem;letter-spacing:.07em">⭐ EXECUTIVE COMMITTEE</div>
      <div style="flex:1;height:2px;background:linear-gradient(90deg,#B8860B,transparent)"></div>
      <span style="font-size:.75rem;color:#7A8DB5;font-weight:600"><?= count($executives) ?> Members</span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem">
      <?php foreach($executives as $m): renderMemberCard($m, $user, 'large'); endforeach; ?>
    </div>
  </div>
  <?php endif; ?>

  <!-- ════ SECTION 2: COMMITTEE MEMBERS — 3-COLUMN GRID ══════ -->
  <?php if(!empty($committee)): ?>
  <div id="committee" style="margin-bottom:2.5rem">
    <div style="display:flex;align-items:center;gap:.8rem;margin-bottom:1.2rem">
      <div style="background:linear-gradient(135deg,#4A148C,#7B1FA2);color:#fff;border-radius:10px;padding:.4rem .85rem;font-family:'Bebas Neue',sans-serif;font-size:.95rem;letter-spacing:.07em">🏛 COMMITTEE MEMBERS</div>
      <div style="flex:1;height:2px;background:linear-gradient(90deg,#7B1FA2,transparent)"></div>
      <span style="font-size:.75rem;color:#7A8DB5;font-weight:600"><?= count($committee) ?> Members</span>
    </div>
    <!-- 3-COLUMN LAYOUT as requested -->
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem" id="committeeGrid">
      <?php foreach($committee as $m): ?>
      <?php
        $canSeePhoto2 = ($user && isAdminRole(($user ? $user['role'] : 'guest'))) || $m['privacy_photo'] !== 'private';
        $canSeePhone2 = ($user && isAdminRole(($user ? $user['role'] : 'guest'))) || $m['privacy_phone'] !== 'private';
        $pb2 = $canSeePhoto2 ? getMemberPhoto($m['profile_photo']) : '';
        $wn2 = preg_replace('/\D/','',$m['whatsapp_number']);
      ?>
      <div class="mc" data-n="<?= h(strtolower($m['name'])) ?>" style="background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 3px 14px rgba(74,20,140,.12);border-top:3px solid #7B1FA2;transition:all .22s">
        <div style="padding:1.1rem;text-align:center">
          <?php if($pb2): ?>
          <img src="<?= $pb2 ?>" style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2.5px solid #7B1FA2;margin:0 auto .65rem;display:block" alt="">
          <?php else: ?>
          <div style="width:72px;height:72px;border-radius:50%;background:#F3E5F5;border:2.5px solid #7B1FA2;margin:0 auto .65rem;display:flex;align-items:center;justify-content:center;font-size:1.6rem"><?= $canSeePhoto2?'👤':'🔒' ?></div>
          <?php endif; ?>
          <div style="font-weight:700;font-size:.88rem;color:#10201F;margin-bottom:.2rem"><?= h($m['name']) ?></div>
          <div style="font-size:.7rem;color:#7A8DB5;margin-bottom:.4rem"><?= h($m['committee_position']??'Committee Member') ?></div>
          <?php if($m['committee_name']): ?><div style="font-size:.65rem;color:#7B1FA2;font-weight:700;margin-bottom:.35rem"><?= h($m['committee_name']) ?></div><?php endif; ?>
          <?php if($m['skill']): ?><div style="font-size:.67rem;background:#F3E5F5;color:#4A148C;border-radius:20px;padding:.1rem .5rem;display:inline-block;margin-bottom:.3rem"><?= h($m['skill']) ?></div><?php endif; ?>
          <?php if($m['blood_group']): ?><div style="font-size:.68rem;color:#B71C1C;font-weight:700;margin-bottom:.3rem">🩸 <?= h($m['blood_group']) ?></div><?php endif; ?>
        </div>
        <div style="padding:.5rem .9rem;background:#F3E5F5;border-top:1px solid #E1BEE7;display:flex;gap:.4rem;justify-content:center">
          <a href="<?= url('modules/profile.php') ?>?id=<?= $m['id'] ?>" style="font-size:.72rem;color:#4A148C;font-weight:700;text-decoration:none;padding:.25rem .6rem;background:rgba(123,31,162,.1);border-radius:6px">👤 Profile</a>
          <?php if($canSeePhone2): ?>
          <a href="https://wa.me/<?= $wn2 ?>" target="_blank" style="font-size:.72rem;color:#25D366;font-weight:700;text-decoration:none;padding:.25rem .6rem;background:rgba(37,211,102,.1);border-radius:6px">💬 Chat</a>
          <?php endif; ?>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
  <?php endif; ?>

  <!-- ════ SECTION 3: GENERAL MEMBERS ════════════════════════ -->
  <?php if(!empty($generalMembers)): ?>
  <div id="members">
    <div style="display:flex;align-items:center;gap:.8rem;margin-bottom:1.2rem">
      <div style="background:linear-gradient(135deg,#37474F,#546E7A);color:#fff;border-radius:10px;padding:.4rem .85rem;font-family:'Bebas Neue',sans-serif;font-size:.95rem;letter-spacing:.07em">👥 GENERAL MEMBERS</div>
      <div style="flex:1;height:2px;background:linear-gradient(90deg,#546E7A,transparent)"></div>
      <span style="font-size:.75rem;color:#7A8DB5;font-weight:600"><?= count($generalMembers) ?> Members</span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:.9rem" id="membersGrid">
      <?php foreach($generalMembers as $m): renderMemberCard($m, $user, 'normal'); endforeach; ?>
    </div>
  </div>
  <?php endif; ?>

  <?php if(empty($allMembers)): ?>
  <div style="background:#E6F4F2;color:#0A1A1F;border-left:4px solid #0F766E;padding:.8rem 1rem;border-radius:9px;font-size:.85rem;font-weight:600">
    ℹ️ No active members found.
  </div>
  <?php endif; ?>

</div>

<style>
.mc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.15)!important}
@media(max-width:600px){
  #committeeGrid{grid-template-columns:1fr 1fr!important}
}
@media(max-width:380px){
  #committeeGrid{grid-template-columns:1fr!important}
}
</style>

<script>
function searchMembers(q) {
  q = q.toLowerCase();
  document.querySelectorAll('.mc[data-n]').forEach(function(c) {
    c.parentElement.style.display = c.dataset.n.includes(q) ? '' : 'none';
  });
}
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
