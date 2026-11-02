<?php
require_once __DIR__ . '/../includes/config.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '🗳️ Elections — Aishwarya Arts & Sports Club',
  'desc'  => 'Club elections and voting — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/election.php',
];
requireLogin();
$me = currentUser();
$isAdmin = isAdminRole($me['role']);

// Create tables
try {
    db()->query("CREATE TABLE IF NOT EXISTS elections (id INT AUTO_INCREMENT PRIMARY KEY,title VARCHAR(200) NOT NULL,description TEXT,start_date DATE,end_date DATE,status ENUM('upcoming','active','completed') DEFAULT 'upcoming',created_by INT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
    db()->query("CREATE TABLE IF NOT EXISTS election_candidates (id INT AUTO_INCREMENT PRIMARY KEY,election_id INT NOT NULL,user_id INT NOT NULL,post VARCHAR(100),bio TEXT,votes INT DEFAULT 0)");
    db()->query("CREATE TABLE IF NOT EXISTS election_votes (id INT AUTO_INCREMENT PRIMARY KEY,election_id INT NOT NULL,voter_id INT NOT NULL,candidate_id INT NOT NULL,voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE KEY uv(election_id,voter_id))");
} catch(Exception $e) {}

$msg = '';

if ($isAdmin && isset($_POST['create_election'])) {
    db()->prepare("INSERT INTO elections(title,description,start_date,end_date,status,created_by)VALUES(?,?,?,?,'upcoming',?)")
       ->execute(array(trim($_POST['title']),trim($_POST['desc']??''),$_POST['start'],$_POST['end'],$me['id']));
    $msg = array('t'=>'ok','m'=>'✅ Election created!');
}
if ($isAdmin && isset($_POST['add_candidate'])) {
    db()->prepare("INSERT INTO election_candidates(election_id,user_id,post,bio)VALUES(?,?,?,?)")
       ->execute(array((int)$_POST['eid'],(int)$_POST['uid'],trim($_POST['post']),trim($_POST['bio']??'')));
    $msg = array('t'=>'ok','m'=>'✅ Candidate added!');
}
if ($isAdmin && isset($_POST['update_status'])) {
    db()->prepare("UPDATE elections SET status=? WHERE id=?")->execute(array($_POST['new_status'],(int)$_POST['eid']));
    $msg = array('t'=>'ok','m'=>'✅ Status updated!');
}
if (isset($_POST['cast_vote'])) {
    try {
        $eid=(int)$_POST['eid'];$cid=(int)$_POST['cid'];
        db()->prepare("INSERT INTO election_votes(election_id,voter_id,candidate_id)VALUES(?,?,?)")->execute(array($eid,$me['id'],$cid));
        db()->prepare("UPDATE election_candidates SET votes=votes+1 WHERE id=?")->execute(array($cid));
        $msg = array('t'=>'ok','m'=>'✅ Vote cast!');
    } catch(Exception $e) { $msg = array('t'=>'warn','m'=>'⚠️ Already voted in this election.'); }
}

$elections = db()->query("SELECT * FROM elections ORDER BY created_at DESC")->fetchAll();
$members   = db()->query("SELECT id,name,role FROM users WHERE status='active' ORDER BY name")->fetchAll();
$pageTitle = 'Elections — '.CLUB_NAME;
require_once __DIR__ . '/../includes/header.php';
?>
<div class="hero" style="padding:2rem 1.2rem 1.8rem;background:linear-gradient(135deg,#0B1033,#0A14E0)">
  <h1>🗳️ CLUB <span>ELECTIONS</span></h1>
  <div class="hero-place">Democratic leadership · <?= h(CLUB_NAME) ?></div>
</div><div class="red-bar"></div>
<div class="section" style="max-width:960px">
<?php if($msg): ?><div class="alert alert-<?=$msg['t']==='ok'?'ok':'warn'?>"><?=$msg['m']?></div><?php endif; ?>

<?php if($isAdmin): ?>
<div class="card mb-3">
  <div class="card-header"><h3>➕ Create New Election</h3></div>
  <div class="card-body">
    <form method="POST" action="<?= url('modules/election.php') ?>">
      <div class="g2">
        <div class="fg"><label class="lbl">Title *</label><input type="text" name="title" class="inp" required placeholder="e.g. Committee Election 2025"></div>
        <div class="fg"><label class="lbl">Start Date</label><input type="date" name="start" class="inp" value="<?=date('Y-m-d')?>"></div>
        <div class="fg"><label class="lbl">End Date</label><input type="date" name="end" class="inp" value="<?=date('Y-m-d',strtotime('+7 days'))?>"></div>
      </div>
      <div class="fg"><label class="lbl">Description</label><textarea name="desc" class="inp" rows="2"></textarea></div>
      <button type="submit" name="create_election" class="btn btn-blue">🗳️ Create Election</button>
    </form>
  </div>
</div>
<?php endif; ?>

<?php if(empty($elections)): ?>
<div style="text-align:center;padding:3rem;color:var(--t3)"><div style="font-size:3rem;margin-bottom:.8rem">🗳️</div><strong>No elections yet.</strong></div>
<?php else: foreach($elections as $el):
  $cands=db()->prepare("SELECT ec.*,u.name,u.profile_photo FROM election_candidates ec JOIN users u ON u.id=ec.user_id WHERE ec.election_id=? ORDER BY ec.votes DESC");
  $cands->execute(array($el['id']));$cands=$cands->fetchAll();
  $vr=db()->prepare("SELECT id FROM election_votes WHERE election_id=? AND voter_id=?");
  $vr->execute(array($el['id'],$me['id']));$voted=$vr->fetch();
  $total=array_sum(array_column($cands,'votes'));
  $sc=array('upcoming'=>array('#FFF8E1','#E65100'),'active'=>array('#E8F5E9','#1B5E20'),'completed'=>array('#ECEEFF','#0B1033'));
  $c=$sc[$el['status']]??array('#F5F5F5','#555');
?>
<div class="card mb-3">
  <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
    <h3>🗳️ <?=h($el['title'])?></h3>
    <div style="display:flex;gap:.5rem;align-items:center">
      <span style="background:<?=$c[0]?>;color:<?=$c[1]?>;border-radius:20px;padding:.2rem .8rem;font-size:.7rem;font-weight:700"><?=strtoupper($el['status'])?></span>
      <?php if($isAdmin): ?>
      <form method="POST" style="display:inline" action="<?=url('modules/election.php')?>">
        <input type="hidden" name="eid" value="<?=$el['id']?>">
        <select name="new_status" class="inp" style="width:auto;padding:.3rem .6rem;font-size:.75rem" onchange="this.form.submit()">
          <option value="upcoming" <?=$el['status']==='upcoming'?'selected':''?>>Upcoming</option>
          <option value="active" <?=$el['status']==='active'?'selected':''?>>Active</option>
          <option value="completed" <?=$el['status']==='completed'?'selected':''?>>Completed</option>
        </select>
        <input type="hidden" name="update_status" value="1">
      </form>
      <?php endif; ?>
    </div>
  </div>
  <div class="card-body">
    <?php if($el['description']): ?><p style="font-size:.85rem;color:var(--t2);margin-bottom:.8rem"><?=h($el['description'])?></p><?php endif; ?>
    <p style="font-size:.74rem;color:var(--t3);margin-bottom:1rem">📅 <?=date('d M Y',strtotime($el['start_date']))?> → <?=date('d M Y',strtotime($el['end_date']))?> · <?=$total?> total votes</p>

    <?php if($isAdmin): ?>
    <details style="margin-bottom:1rem"><summary style="cursor:pointer;font-size:.8rem;font-weight:700;color:var(--blue)">➕ Add Candidate</summary>
    <form method="POST" action="<?=url('modules/election.php')?>" style="margin-top:.7rem;padding:.9rem;background:#F7F8FF;border-radius:10px">
      <input type="hidden" name="eid" value="<?=$el['id']?>">
      <div class="g2">
        <div class="fg"><label class="lbl">Member</label><select name="uid" class="inp" required><option value="">— Select —</option><?php foreach($members as $m): ?><option value="<?=$m['id']?>"><?=h($m['name'])?> · <?=h(roleLabel($m['role']))?></option><?php endforeach;?></select></div>
        <div class="fg"><label class="lbl">Running For</label><input type="text" name="post" class="inp" placeholder="e.g. President" required></div>
      </div>
      <div class="fg"><label class="lbl">Bio</label><textarea name="bio" class="inp" rows="2"></textarea></div>
      <button type="submit" name="add_candidate" class="btn btn-blue btn-sm">➕ Add Candidate</button>
    </form></details>
    <?php endif; ?>

    <?php if(empty($cands)): ?>
    <div style="text-align:center;padding:1.5rem;color:var(--t3);font-size:.85rem">No candidates yet.</div>
    <?php else: ?>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem">
    <?php foreach($cands as $c2):
      $cp=getMemberPhoto($c2['profile_photo']);
      $pct=$total>0?round(($c2['votes']/$total)*100):0;
    ?>
    <div style="background:#F7F8FF;border-radius:14px;padding:1.1rem;text-align:center;border:2px solid #E3E7F5">
      <?php if($cp): ?><img src="<?=$cp?>" style="width:56px;height:56px;border-radius:50%;object-fit:cover;border:2.5px solid #0A14E0;margin:0 auto .5rem;display:block" alt=""><?php else: ?><div style="width:56px;height:56px;border-radius:50%;background:#ECEEFF;margin:0 auto .5rem;display:flex;align-items:center;justify-content:center;font-size:1.4rem">👤</div><?php endif;?>
      <div style="font-weight:700;font-size:.9rem;margin-bottom:.15rem"><?=h($c2['name'])?></div>
      <div style="font-size:.7rem;color:var(--t3);margin-bottom:.5rem"><?=h($c2['post'])?></div>
      <?php if($c2['bio']): ?><div style="font-size:.72rem;color:var(--t2);margin-bottom:.6rem;line-height:1.4"><?=h($c2['bio'])?></div><?php endif;?>
      <div style="background:#ECEEFF;border-radius:8px;padding:.5rem;margin-bottom:.6rem">
        <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.04rem;color:#0A14E0"><?=$c2['votes']?></div>
        <div style="font-size:.62rem;color:var(--t3);margin-bottom:.3rem">votes · <?=$pct?>%</div>
        <div style="background:#D6DAFF;border-radius:4px;height:5px"><div style="background:#0A14E0;height:5px;border-radius:4px;width:<?=$pct?>%"></div></div>
      </div>
      <?php if($el['status']==='active'&&!$voted): ?>
      <form method="POST" action="<?=url('modules/election.php')?>">
        <input type="hidden" name="eid" value="<?=$el['id']?>"><input type="hidden" name="cid" value="<?=$c2['id']?>">
        <button type="submit" name="cast_vote" class="btn btn-blue btn-sm btn-block" onclick="return confirm('Vote for <?=h($c2['name'])?>?')">🗳️ Vote</button>
      </form>
      <?php elseif($voted&&$el['status']==='active'): ?><div style="font-size:.72rem;color:#2E7D32;font-weight:700">✅ You Voted</div>
      <?php endif;?>
    </div>
    <?php endforeach;?>
    </div>
    <?php endif;?>
  </div>
</div>
<?php endforeach; endif; ?>
</div>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
