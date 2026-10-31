<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/upload_helper.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '🌸 Onam Celebration — Aishwarya Arts & Sports Club',
  'desc'  => 'Onam celebration events and programs — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/onam.php',
];
requireLogin();$user=currentUser();$isAdmin=isCulturalAdmin($user['role']);
$pageTitle='Onam Celebration — '.CLUB_NAME;

try {
db()->query("CREATE TABLE IF NOT EXISTS onam_events(id INT AUTO_INCREMENT PRIMARY KEY,year INT DEFAULT 0,theme VARCHAR(200),description TEXT,event_date DATE,venue VARCHAR(200),status ENUM('upcoming','active','completed') DEFAULT 'upcoming',created_by INT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
db()->query("CREATE TABLE IF NOT EXISTS onam_programs(id INT AUTO_INCREMENT PRIMARY KEY,onam_id INT,title VARCHAR(150),program_type VARCHAR(80),time_slot VARCHAR(50),participants TEXT,winner VARCHAR(100),created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
db()->query("CREATE TABLE IF NOT EXISTS onam_registrations(id INT AUTO_INCREMENT PRIMARY KEY,onam_id INT,program_id INT,user_id INT,team_name VARCHAR(100),status ENUM('registered','confirmed','participated') DEFAULT 'registered',UNIQUE KEY ur(program_id,user_id))");
} catch(Exception $e){}

$msg='';
if($isAdmin&&isset($_POST['create_onam'])){
    db()->prepare("INSERT INTO onam_events(year,theme,description,event_date,venue,created_by)VALUES(?,?,?,?,?,?)")
       ->execute(array((int)$_POST['oyear'],trim($_POST['otheme']),trim($_POST['odesc']??''),$_POST['odate'],trim($_POST['ovenue']??''),$user['id']));
    $msg=array('t'=>'ok','m'=>'✅ Onam celebration created!');
}
if($isAdmin&&isset($_POST['add_program'])){
    db()->prepare("INSERT INTO onam_programs(onam_id,title,program_type,time_slot,participants)VALUES(?,?,?,?,?)")
       ->execute(array((int)$_POST['oid'],trim($_POST['ptitle']),$_POST['ptype'],trim($_POST['ptime']??''),trim($_POST['ppart']??'')));
    $msg=array('t'=>'ok','m'=>'✅ Program added!');
}
if(isset($_POST['register_program'])){
    try {
        db()->prepare("INSERT INTO onam_registrations(onam_id,program_id,user_id,team_name)VALUES(?,?,?,?)")
           ->execute(array((int)$_POST['oid'],(int)$_POST['pid'],$user['id'],trim($_POST['team_name']??$user['name'])));
        $msg=array('t'=>'ok','m'=>'✅ Registered!');
    } catch(Exception $e){$msg=array('t'=>'warn','m'=>'Already registered.');}
}
if($isAdmin&&isset($_POST['set_winner'])){
    db()->prepare("UPDATE onam_programs SET winner=? WHERE id=?")->execute(array(trim($_POST['winner']),(int)$_POST['pid']));
    $msg=array('t'=>'ok','m'=>'✅ Winner updated!');
}

$onamEvents=db()->query("SELECT * FROM onam_events ORDER BY year DESC")->fetchAll();
require_once __DIR__ . '/../includes/header.php';
?>
<div class="hero" style="background:linear-gradient(135deg,#E65100,#FF8F00,#F9A825);padding:2rem 1.2rem 1.8rem">
  <h1>🌸 ONAM <span>CELEBRATION</span></h1>
  <div class="hero-place"><?= h(CLUB_NAME) ?> · Thrikkakara Appan's Blessings</div>
</div><div class="red-bar"></div>
<div class="section" style="max-width:960px">
<?php if($msg): ?><div class="alert alert-<?=$msg['t']==='ok'?'ok':'warn'?>"><?=$msg['m']?></div><?php endif;?>

<!-- Onam info banner -->
<div style="background:linear-gradient(135deg,#FFF8E1,#FFF3CD);border:1.5px solid #FFB300;border-radius:16px;padding:1.3rem;margin-bottom:1.5rem;text-align:center">
  <div style="font-size:2rem;margin-bottom:.4rem">🌸 🎊 🌺 🌟 🌸</div>
  <h2 style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;letter-spacing:.08em;color:#E65100;margin-bottom:.3rem">HAPPY ONAM!</h2>
  <p style="font-size:.85rem;color:#6D4C41">Celebrating the spirit of Kerala, unity and prosperity. Thrikkakara Appan's blessings to all!</p>
</div>

<?php if($isAdmin): ?>
<div class="card mb-3">
  <div class="card-header" style="background:linear-gradient(135deg,#E65100,#FF8F00)"><h3>➕ Create Onam Event</h3></div>
  <div class="card-body">
    <form method="POST" action="<?=url('modules/onam.php')?>">
      <div class="g2">
        <div class="fg"><label class="lbl">Year</label><input type="number" name="oyear" class="inp" value="<?=date('Y')?>" required></div>
        <div class="fg"><label class="lbl">Theme</label><input type="text" name="otheme" class="inp" placeholder="e.g. Samridhi - Prosperity"></div>
        <div class="fg"><label class="lbl">Event Date</label><input type="date" name="odate" class="inp" required></div>
        <div class="fg"><label class="lbl">Venue</label><input type="text" name="ovenue" class="inp"></div>
      </div>
      <div class="fg"><label class="lbl">Description</label><textarea name="odesc" class="inp" rows="2"></textarea></div>
      <button type="submit" name="create_onam" class="btn" style="background:#bf360c;color:#fff"><span aria-hidden="true">🌸</span> Create Onam Event</button>
    </form>
  </div>
</div>
<?php endif;?>

<?php if(empty($onamEvents)): ?>
<div style="text-align:center;padding:4rem;color:var(--t3)"><div style="font-size:4rem">🌸</div><h3 style="margin:.8rem 0 .4rem">No Onam events yet</h3><p style="font-size:.85rem">Onam celebration details will appear here.</p></div>
<?php else: foreach($onamEvents as $on):
  $programs=db()->prepare("SELECT p.*,(SELECT COUNT(*) FROM onam_registrations WHERE program_id=p.id) regc FROM onam_programs p WHERE p.onam_id=? ORDER BY p.created_at");
  $programs->execute(array($on['id']));$programs=$programs->fetchAll();
  $ptypes=array('pookalam'=>array('🌺','Pookalam (Floral Carpet)','#F3E5F5','#6A1B9A'),'thiruvathira'=>array('💃','Thiruvathira','#FCE4EC','#880E4F'),'vallamkali'=>array('🚣','Boat Race','#E6F4F2','#0F766E'),'onasadya'=>array('🍽️','Onam Sadya','#E8F5E9','#1B5E20'),'kabaddi'=>array('🤼','Kabaddi','#FFF3E0','#E65100'),'quiz'=>array('🧠','Quiz Competition','#F3E5F5','#4A148C'),'music'=>array('🎵','Music Program','#FCE4EC','#B71C1C'),'drama'=>array('🎭','Drama/Skit','#E8EAF6','#283593'),'other'=>array('🎉','Other','#F5F5F5','#424242'));
?>
<div class="card mb-3">
  <div class="card-header" style="background:linear-gradient(135deg,#E65100,#FF8F00);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
    <h3>🌸 Onam <?=$on['year']?><?php if($on['theme']): ?> — <?=h($on['theme'])?><?php endif;?></h3>
    <span style="background:rgba(255,255,255,.25);color:#fff;border-radius:20px;padding:.2rem .8rem;font-size:.7rem;font-weight:700"><?=strtoupper($on['status'])?></span>
  </div>
  <div class="card-body">
    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem;font-size:.8rem;color:var(--t2)">
      <?php if($on['event_date']): ?><span>📅 <?=date('d M Y',strtotime($on['event_date']))?></span><?php endif;?>
      <?php if($on['venue']): ?><span>📍 <?=h($on['venue'])?></span><?php endif;?>
    </div>
    <?php if($on['description']): ?><p style="font-size:.84rem;color:var(--t2);margin-bottom:1rem"><?=h($on['description'])?></p><?php endif;?>

    <?php if($isAdmin): ?>
    <details style="margin-bottom:1rem"><summary style="cursor:pointer;font-size:.8rem;font-weight:700;color:#E65100">➕ Add Program</summary>
    <form method="POST" action="<?=url('modules/onam.php')?>" style="margin-top:.7rem;padding:.9rem;background:#FFF3E0;border-radius:10px">
      <input type="hidden" name="oid" value="<?=$on['id']?>">
      <div class="g2">
        <div class="fg"><label class="lbl">Program Title</label><input type="text" name="ptitle" class="inp" required placeholder="e.g. Pookalam Competition"></div>
        <div class="fg"><label class="lbl">Type</label><select name="ptype" class="inp"><option value="pookalam">🌺 Pookalam</option><option value="thiruvathira">💃 Thiruvathira</option><option value="vallamkali">🚣 Vallamkali</option><option value="onasadya">🍽️ Onam Sadya</option><option value="kabaddi">🤼 Kabaddi</option><option value="quiz">🧠 Quiz</option><option value="music">🎵 Music</option><option value="drama">🎭 Drama</option><option value="other">🎉 Other</option></select></div>
        <div class="fg"><label class="lbl">Time</label><input type="text" name="ptime" class="inp" placeholder="e.g. 10:00 AM"></div>
        <div class="fg"><label class="lbl">Participants</label><input type="text" name="ppart" class="inp" placeholder="e.g. All women, Youth"></div>
      </div>
      <button type="submit" name="add_program" class="btn btn-sm" style="background:#E65100;color:#fff">➕ Add Program</button>
    </form></details>
    <?php endif;?>

    <!-- Programs grid -->
    <?php if(empty($programs)): ?>
    <div style="text-align:center;padding:1.5rem;color:var(--t3);font-size:.85rem">Programs will be announced soon.</div>
    <?php else:?>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.9rem">
    <?php foreach($programs as $prog):
      $pt=$ptypes[$prog['program_type']]??$ptypes['other'];
      $isReg=false;
      $rchk=db()->prepare("SELECT id FROM onam_registrations WHERE program_id=? AND user_id=?");
      $rchk->execute(array($prog['id'],$user['id']));$isReg=$rchk->fetch();
    ?>
    <div style="background:<?=$pt[2]?>;border-radius:12px;padding:1rem;border:1.5px solid <?=$pt[3]?>22">
      <div style="font-size:1.5rem;margin-bottom:.3rem"><?=$pt[0]?></div>
      <div style="font-weight:700;font-size:.88rem;color:<?=$pt[3]?>;margin-bottom:.2rem"><?=h($prog['title'])?></div>
      <?php if($prog['time_slot']): ?><div style="font-size:.7rem;color:var(--t3)">⏰ <?=h($prog['time_slot'])?></div><?php endif;?>
      <?php if($prog['participants']): ?><div style="font-size:.7rem;color:var(--t3)">👥 <?=h($prog['participants'])?></div><?php endif;?>
      <div style="font-size:.68rem;font-weight:700;color:var(--t3);margin:.3rem 0"><?=$prog['regc']?> registered</div>
      <?php if($prog['winner']): ?>
      <div style="background:#FFF9C4;border-radius:8px;padding:.3rem .6rem;margin-top:.4rem;font-size:.72rem;font-weight:700;color:#E65100">🏆 Winner: <?=h($prog['winner'])?></div>
      <?php endif;?>
      <?php if(!$isReg&&$on['status']!=='completed'): ?>
      <form method="POST" action="<?=url('modules/onam.php')?>" style="margin-top:.5rem">
        <input type="hidden" name="oid" value="<?=$on['id']?>"><input type="hidden" name="pid" value="<?=$prog['id']?>">
        <input type="text" name="team_name" class="inp" placeholder="Your name / team" style="margin-bottom:.35rem;font-size:.78rem;padding:.45rem .6rem">
        <button type="submit" name="register_program" class="btn btn-sm btn-block" style="background:<?=$pt[3]?>;color:#fff;font-size:.73rem">✅ Register</button>
      </form>
      <?php elseif($isReg): ?>
      <div style="margin-top:.5rem;text-align:center;font-size:.72rem;color:#2E7D32;font-weight:700">✅ Registered!</div>
      <?php endif;?>
      <?php if($isAdmin&&$on['status']==='active'&&!$prog['winner']): ?>
      <form method="POST" action="<?=url('modules/onam.php')?>" style="margin-top:.4rem;display:flex;gap:.3rem">
        <input type="hidden" name="pid" value="<?=$prog['id']?>">
        <input type="text" name="winner" class="inp" placeholder="Winner name" style="flex:1;font-size:.75rem;padding:.4rem .5rem">
        <button type="submit" name="set_winner" class="btn btn-sm" style="background:#E65100;color:#fff;padding:.4rem .6rem;font-size:.72rem">🏆</button>
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
