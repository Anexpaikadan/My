<?php
require_once __DIR__.'/../includes/config.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '⭐ Talents & Skills — Aishwarya Arts & Sports Club',
  'desc'  => 'Member talents directory — AASC, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/skills.php',
];
requireLogin();$pageTitle='Talents — '.CLUB_NAME;
$all=db()->query("SELECT * FROM users WHERE status='active' AND skill IS NOT NULL AND skill!='' ORDER BY skill,name")->fetchAll();
$grouped=[];foreach($all as $m)$grouped[$m['skill']][]=$m;
$icons=['Program Developer'=>'💻','Designer'=>'🎨','Teacher'=>'📚','Doctor'=>'🩺','Engineer'=>'⚙️','Electrician'=>'⚡','Carpenter'=>'🔨','Plumber'=>'🔧','Driver'=>'🚗','Farmer'=>'🌾'];
require_once __DIR__.'/../includes/header.php';
?>
<div class="hero" style="padding:2.2rem 1.2rem 1.8rem"><h1>VILLAGE <span>TALENTS</span></h1><div class="hero-place">Skills &amp; professionals of <?=h(CLUB_PLACE)?></div></div><div class="red-bar"></div>
<div class="section">
  <div style="display:flex;gap:.6rem;margin-bottom:1rem;flex-wrap:wrap">
    <input type="text" class="inp" id="nf" style="flex:1;min-width:160px" placeholder="Search name…">
    <select class="inp" id="sf" style="min-width:150px;max-width:200px"><option value="">All Skills</option>
      <?php foreach(array_keys($grouped) as $sk):?><option><?=h($sk)?></option><?php endforeach;?></select>
  </div>
  <?php foreach($grouped as $skill=>$members):?>
  <h2 class="section-title" style="font-size:1.2rem"><?=$icons[$skill]??'🌟'?> <?=h($skill)?> <small style="font-family:'DM Sans';font-weight:400;font-size:.78rem;color:var(--t3)">(<?=count($members)?>)</small><div class="title-bar"></div></h2>
  <div class="member-grid mb-2">
  <?php foreach($members as $m):$mp=getMemberPhoto($m['profile_photo']);$wn=preg_replace('/\D/','',$m['whatsapp_number']);?>
  <div class="member-card" data-s="<?=h(strtolower($skill))?>" data-n="<?=h(strtolower($m['name']))?>">
    <?php if($mp):?><img src="<?=$mp?>" class="member-avatar" alt=""><?php else:?><div class="member-avatar" style="display:flex;align-items:center;justify-content:center;font-size:2rem;background:#E3F2FD">👤</div><?php endif;?>
    <div class="member-name"><?=h($m['name'])?></div>
    <div class="member-pos"><?=h($m['profession']??$m['skill'])?></div>
    <span class="role-badge role-<?=h($m['role'])?>"><?=h(roleLabel($m['role']))?></span>
    <?php if($m['blood_group']):?><div style="font-size:.7rem;color:#B71C1C;font-weight:700;margin-top:.25rem">🩸 <?=h($m['blood_group'])?></div><?php endif;?>
    <div style="margin-top:.7rem;display:flex;gap:.35rem;justify-content:center">
      <a href="<?=url('modules/profile.php')?>?id=<?=$m['id']?>" class="btn btn-outline-blue btn-sm">👤</a>
      <a href="https://wa.me/<?=$wn?>" target="_blank" class="btn-wa" style="font-size:.73rem;padding:.3rem .65rem">💬</a>
    </div>
  </div>
  <?php endforeach;?>
  </div>
  <?php endforeach;?>
  <?php if(empty($all)):?><div class="alert alert-info">No talent profiles yet.</div><?php endif;?>
</div>
<script>
var nf=document.getElementById('nf'),sf=document.getElementById('sf');
function af(){var n=nf.value.toLowerCase(),s=sf.value.toLowerCase();document.querySelectorAll('.member-card[data-s]').forEach(function(r){r.style.display=(!n||r.dataset.n.includes(n))&&(!s||r.dataset.s===s)?'':'none';});}
nf.addEventListener('input',af);sf.addEventListener('change',af);
</script>
<?php require_once __DIR__.'/../includes/footer.php';?>
