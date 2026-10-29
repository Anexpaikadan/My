<?php require 'config.php';$u=require_login();
if($u['role']==='admin')redirect('admin.php');
if($u['role']==='collector')redirect('fund.php?id='.(int)$u['fund_id']);
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $t=trim($_POST['title']);
 if($t==='')flash('Title required','danger');
 else{
  $type=in_array($_POST['type'],['charity','festival','other'])?$_POST['type']:'other';
  $pdo->prepare('INSERT INTO funds(creator_id,title,description,type,start_date,creator_details) VALUES(?,?,?,?,?,?)')
   ->execute([$u['id'],$t,trim($_POST['description']),$type,$_POST['start_date']?:date('Y-m-d'),trim($_POST['creator_details'])]);
  redirect('fund.php?id='.$pdo->lastInsertId());
 }
}
$s=$pdo->prepare('SELECT * FROM funds WHERE creator_id=? ORDER BY id DESC');$s->execute([$u['id']]);$funds=$s->fetchAll();
head('My Funds');?>
<div class="d-flex justify-content-between align-items-center mb-2"><h5 class="m-0">My Funds / എന്റെ ഫണ്ടുകൾ</h5>
<button class="btn btn-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#nf">+ New Fund</button></div>
<div id="nf" class="collapse card p-3 mb-3"><form method="post"><?=csrf_field()?>
<input class="form-control mb-2" name="title" placeholder="Fund title / ഫണ്ടിന്റെ പേര്" required>
<select class="form-select mb-2" name="type"><option value="charity">Charity / ചാരിറ്റി</option><option value="festival">Festival / ഉത്സവം</option><option value="other">Other</option></select>
<input class="form-control mb-2" type="date" name="start_date" value="<?=date('Y-m-d')?>">
<textarea class="form-control mb-2" name="description" rows="3" placeholder="Description / വിവരണം"></textarea>
<textarea class="form-control mb-2" name="creator_details" rows="2" placeholder="Creator details (name, phone, place)"></textarea>
<button class="btn btn-primary w-100">Create Fund</button></form></div>
<?php foreach($funds as $f): [$t,$p,$b]=fund_totals($f['id']);?>
<a href="fund.php?id=<?=$f['id']?>" class="card p-3 mb-2 text-decoration-none text-dark">
<b><?=e($f['title'])?></b><small class="text-muted"><?=e($f['type'])?> · <?=e($f['start_date'])?></small>
<div class="small mt-1">Total ₹<?=money($t)?> · Paid ₹<?=money($p)?> · Balance ₹<?=money($b)?></div></a>
<?php endforeach; if(!$funds)echo '<p class="text-muted">No funds yet. Create one.</p>';
foot();
