<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/upload_helper.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '🎭 Arts Festival — Aishwarya Arts & Sports Club',
  'desc'  => 'Arts and cultural festival programs — AASC, Vettikkattiri',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/arts_festival.php',
];
requireLogin();$user=currentUser();$isAdmin=isCulturalAdmin($user['role']);
$pageTitle='Arts Festival — '.CLUB_NAME;

try {
db()->query("CREATE TABLE IF NOT EXISTS arts_festivals(id INT AUTO_INCREMENT PRIMARY KEY,title VARCHAR(200),description TEXT,event_date DATE,venue VARCHAR(200),status ENUM('upcoming','active','completed') DEFAULT 'upcoming',created_by INT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
db()->query("CREATE TABLE IF NOT EXISTS arts_programs(id INT AUTO_INCREMENT PRIMARY KEY,festival_id INT,title VARCHAR(150),category ENUM('music','dance','drama','painting','poetry','quiz','other'),time_slot VARCHAR(50),age_group VARCHAR(50),prize VARCHAR(100),winner VARCHAR(100),reg_count INT DEFAULT 0)");
} catch(Exception $e){}

$msg='';
if($isAdmin&&isset($_POST['create_festival'])){
    db()->prepare("INSERT INTO arts_festivals(title,description,event_date,venue,created_by)VALUES(?,?,?,?,?)")
       ->execute(array(trim($_POST['ftitle']),trim($_POST['fdesc']??''),$_POST['fdate'],trim($_POST['fvenue']??''),$user['id']));
    $msg=array('t'=>'ok','m'=>'✅ Arts Festival created!');
}
if($isAdmin&&isset($_POST['add_arts_program'])){
    db()->prepare("INSERT INTO arts_programs(festival_id,title,category,time_slot,age_group,prize)VALUES(?,?,?,?,?,?)")
       ->execute(array((int)$_POST['fid'],trim($_POST['aptitle']),$_POST['apcat'],trim($_POST['aptime']??''),trim($_POST['apage']??''),trim($_POST['apprize']??'')));
    $msg=array('t'=>'ok','m'=>'✅ Program added!');
}
if(isset($_POST['register_arts'])){
    $pid=(int)$_POST['pid'];
    db()->prepare("UPDATE arts_programs SET reg_count=reg_count+1 WHERE id=?")->execute(array($pid));
    $msg=array('t'=>'ok','m'=>'✅ Registration submitted! Contact Secretary for confirmation.');
}
if($isAdmin&&isset($_POST['set_arts_winner'])){
    db()->prepare("UPDATE arts_programs SET winner=? WHERE id=?")->execute(array(trim($_POST['awinner']),(int)$_POST['pid']));
    $msg=array('t'=>'ok','m'=>'✅ Winner set!');
}

$festivals=db()->query("SELECT * FROM arts_festivals ORDER BY created_at DESC")->fetchAll();
require_once __DIR__ . '/../includes/header.php';
?>
<div class="hero" style="background:linear-gradient(135deg,#4A148C,#7B1FA2,#9C27B0);padding:2rem 1.2rem 1.8rem">
  <h1>🎭 ARTS <span>FESTIVAL</span></h1>
  <div class="hero-place"><?= h(CLUB_NAME) ?> · Celebrating Culture &amp; Talent</div>
</div><div class="red-bar"></div>
<div class="section" style="max-width:960px">
<?php if($msg): ?><div class="alert alert-<?=$msg['t']==='ok'?'ok':'warn'?>"><?=$msg['m']?></div><?php endif;?>

<?php if($isAdmin): ?>
<div class="card mb-3">
  <div class="card-header" style="background:linear-gradient(135deg,#4A148C,#7B1FA2)"><h3>➕ Create Arts Festival</h3></div>
  <div class="card-body">
    <form method="POST" action="<?=url('modules/arts_festival.php')?>">
      <div class="g2">
        <div class="fg"><label class="lbl">Festival Name *</label><input type="text" name="ftitle" class="inp" required placeholder="e.g. AASC Kalolsavam 2025"></div>
        <div class="fg"><label class="lbl">Date</label><input type="date" name="fdate" class="inp"></div>
        <div class="fg"><label class="lbl">Venue</label><input type="text" name="fvenue" class="inp"></div>
      </div>
      <div class="fg"><label class="lbl">Description</label><textarea name="fdesc" class="inp" rows="2"></textarea></div>
      <button type="submit" name="create_festival" class="btn" style="background:#7B1FA2;color:#fff">🎭 Create Festival</button>
    </form>
  </div>
</div>
<?php endif;?>

<?php if(empty($festivals)): ?>
<div style="text-align:center;padding:4rem;color:var(--t3)"><div style="font-size:4rem">🎭</div><h3 style="margin:.8rem 0 .4rem">No arts festivals yet</h3><p style="font-size:.85rem">Festival announcements will appear here.</p></div>
<?php else: foreach($festivals as $fst):
  $progs=db()->prepare("SELECT * FROM arts_programs WHERE festival_id=? ORDER BY category,created_at");
  $progs->execute(array($fst['id']));$progs=$progs->fetchAll();
  $catColors=array('music'=>array('🎵','#FCE4EC','#880E4F'),'dance'=>array('💃','#F3E5F5','#6A1B9A'),'drama'=>array('🎭','#E8EAF6','#283593'),'painting'=>array('🎨','#E3F2FD','#0D47A1'),'poetry'=>array('📝','#E8F5E9','#1B5E20'),'quiz'=>array('🧠','#FFF3E0','#E65100'),'other'=>array('🌟','#F5F5F5','#424242'));
?>
<div class="card mb-3">
  <div class="card-header" style="background:linear-gradient(135deg,#4A148C,#7B1FA2)"><h3>🎭 <?=h($fst['title'])?></h3></div>
  <div class="card-body">
    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem;font-size:.8rem;color:var(--t2)">
      <?php if($fst['event_date']): ?><span>📅 <?=date('d M Y',strtotime($fst['event_date']))?></span><?php endif;?>
      <?php if($fst['venue']): ?><span>📍 <?=h($fst['venue'])?></span><?php endif;?>
      <span style="background:#F3E5F5;color:#6A1B9A;border-radius:20px;padding:.15rem .6rem;font-size:.68rem;font-weight:700"><?=strtoupper($fst['status'])?></span>
    </div>
    <?php if($fst['description']): ?><p style="font-size:.84rem;color:var(--t2);margin-bottom:1rem"><?=h($fst['description'])?></p><?php endif;?>

    <?php if($isAdmin): ?>
    <details style="margin-bottom:1rem"><summary style="cursor:pointer;font-size:.8rem;font-weight:700;color:#7B1FA2">➕ Add Program</summary>
    <form method="POST" action="<?=url('modules/arts_festival.php')?>" style="margin-top:.7rem;padding:.9rem;background:#F3E5F5;border-radius:10px">
      <input type="hidden" name="fid" value="<?=$fst['id']?>">
      <div class="g2">
        <div class="fg"><label class="lbl">Program Name</label><input type="text" name="aptitle" class="inp" required></div>
        <div class="fg"><label class="lbl">Category</label><select name="apcat" class="inp"><option value="music">🎵 Music</option><option value="dance">💃 Dance</option><option value="drama">🎭 Drama</option><option value="painting">🎨 Painting</option><option value="poetry">📝 Poetry</option><option value="quiz">🧠 Quiz</option><option value="other">🌟 Other</option></select></div>
        <div class="fg"><label class="lbl">Time Slot</label><input type="text" name="aptime" class="inp" placeholder="e.g. 10:00 AM"></div>
        <div class="fg"><label class="lbl">Age Group</label><input type="text" name="apage" class="inp" placeholder="e.g. Under 18, Open"></div>
        <div class="fg"><label class="lbl">Prize</label><input type="text" name="apprize" class="inp" placeholder="e.g. ₹500 + Trophy"></div>
      </div>
      <button type="submit" name="add_arts_program" class="btn btn-sm" style="background:#7B1FA2;color:#fff">➕ Add</button>
    </form></details>
    <?php endif;?>

    <?php if(empty($progs)): ?>
    <div style="text-align:center;padding:1.5rem;color:var(--t3);font-size:.85rem">Programs will be announced soon.</div>
    <?php else:?>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.9rem">
    <?php foreach($progs as $prog):$ct=$catColors[$prog['category']]??$catColors['other'];?>
    <div style="background:<?=$ct[1]?>;border-radius:12px;padding:1rem;border:1.5px solid <?=$ct[2]?>22">
      <div style="font-size:1.4rem;margin-bottom:.3rem"><?=$ct[0]?></div>
      <div style="font-weight:700;font-size:.88rem;color:<?=$ct[2]?>;margin-bottom:.2rem"><?=h($prog['title'])?></div>
      <div style="font-size:.68rem;color:var(--t3)"><?=h(ucfirst($prog['category']))?><?php if($prog['age_group']): ?> · <?=h($prog['age_group'])?><?php endif;?></div>
      <?php if($prog['time_slot']): ?><div style="font-size:.68rem;color:var(--t3)">⏰ <?=h($prog['time_slot'])?></div><?php endif;?>
      <?php if($prog['prize']): ?><div style="font-size:.7rem;font-weight:700;color:#E65100;margin:.3rem 0">🏆 <?=h($prog['prize'])?></div><?php endif;?>
      <div style="font-size:.65rem;color:var(--t3);margin-bottom:.4rem"><?=$prog['reg_count']?> registered</div>
      <?php if($prog['winner']): ?><div style="background:#FFF9C4;border-radius:8px;padding:.28rem .5rem;font-size:.7rem;font-weight:700;color:#E65100">🥇 <?=h($prog['winner'])?></div><?php endif;?>
      <?php if($fst['status']!=='completed'): ?>
      <form method="POST" action="<?=url('modules/arts_festival.php')?>" style="margin-top:.5rem">
        <input type="hidden" name="fid" value="<?=$fst['id']?>"><input type="hidden" name="pid" value="<?=$prog['id']?>">
        <button type="submit" name="register_arts" class="btn btn-sm btn-block" style="background:<?=$ct[2]?>;color:#fff;font-size:.73rem">✅ Register</button>
      </form>
      <?php endif;?>
      <?php if($isAdmin&&!$prog['winner']&&$fst['status']==='active'): ?>
      <form method="POST" action="<?=url('modules/arts_festival.php')?>" style="margin-top:.4rem;display:flex;gap:.3rem">
        <input type="hidden" name="pid" value="<?=$prog['id']?>">
        <input type="text" name="awinner" class="inp" placeholder="Winner" style="flex:1;font-size:.72rem;padding:.38rem .5rem">
        <button type="submit" name="set_arts_winner" class="btn btn-sm" style="background:#7B1FA2;color:#fff;font-size:.72rem">🏆</button>
      </form>
      <?php endif;?>
    </div>
    <?php endforeach;?>
    </div>
    <?php endif;?>
  </div>
</div>
<?php endforeach;endif;?>
</div>
<?php require_once __DIR__ . '/../includes/footer.php';?>
