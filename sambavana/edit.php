<?php require 'config.php';require_login(['user']);
$s=$pdo->prepare('SELECT * FROM contributions WHERE id=?');$s->execute([(int)($_GET['id']??$_POST['id']??0)]);$c=$s->fetch();
if(!$c){http_response_code(404);die('Not found');}
[$f,$role]=fund_access($c['fund_id']);
if($role!=='creator'||$f['status']!=='open'||$c['cancelled']){http_response_code(403);die('Not allowed');}
nav($f,$role,'home');
$q=$pdo->prepare('SELECT COALESCE(SUM(amount),0) FROM payments WHERE contribution_id=?');$q->execute([$c['id']]);$paid=(float)$q->fetchColumn();
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 if(($_POST['do']??'')==='cancel'){
  if($paid>0)flash('Cannot cancel an entry that has payments. Edit it instead.','danger');
  else{$pdo->prepare('UPDATE contributions SET cancelled=1 WHERE id=?')->execute([$c['id']]);flash('Entry #'.$c['serial_no'].' cancelled');redirect('fund.php?id='.$f['id']);}
 }else{
  $n=trim($_POST['name']);$a=(float)$_POST['amount'];$m=preg_replace('/\D/','',$_POST['mobile']??'');$m=$m===''?null:substr($m,-10);
  if($n===''||$a<=0||$a<$paid||($m!==null&&strlen($m)!==10))flash('Check values (amount cannot be less than paid ₹'.money($paid).')','danger');
  else{$pdo->prepare('UPDATE contributions SET name=?,mobile=?,amount=? WHERE id=?')->execute([$n,$m,$a,$c['id']]);flash('Updated');redirect('contribution.php?id='.$c['id']);}
 }
 redirect('edit.php?id='.$c['id']);
}
head('Edit entry');?>
<a href="contribution.php?id=<?=$c['id']?>" class="small">← Back</a>
<h5 class="mt-1">Edit #<?=$c['serial_no']?></h5>
<div class="card p-3 mb-3"><form method="post"><?=csrf_field()?><input type="hidden" name="id" value="<?=$c['id']?>">
<label class="small text-muted">Name</label><input class="form-control mb-2" name="name" value="<?=e($c['name'])?>" required>
<label class="small text-muted">Mobile (optional)</label><input class="form-control mb-2" name="mobile" value="<?=e($c['mobile'])?>" inputmode="numeric">
<label class="small text-muted">Contribution ₹ (paid so far ₹<?=money($paid)?>)</label><input class="form-control mb-3" type="number" step="0.01" min="<?=max(1,$paid)?>" name="amount" value="<?=e($c['amount'])?>" required>
<button class="btn btn-primary w-100">Save changes</button></form></div>
<?php if($paid==0):?><form method="post" onsubmit="return confirm('Cancel this entry?')"><?=csrf_field()?><input type="hidden" name="id" value="<?=$c['id']?>"><input type="hidden" name="do" value="cancel">
<button class="btn btn-outline-danger w-100">🗑 Cancel this entry</button></form>
<?php else:?><p class="small text-muted">Entries with payments cannot be cancelled; correct the name or amount instead.</p><?php endif;?>
<?php foot();
