<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'transfer');
$mem=members($f);$cols=array_values(array_filter($mem,fn($m)=>$m['role']==='collector'));
$pendOf=function($cid)use($pdo,$fid){$q=$pdo->prepare("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE fund_id=? AND collector_id=? AND status='pending'");$q->execute([$fid,$cid]);return (float)$q->fetchColumn();};
$cashOf=function($cid)use($cols){foreach($cols as $m)if($m['id']==$cid)return $m['cash'];return null;};
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();$do=$_POST['do']??'';$a=(float)($_POST['amount']??0);
 if($role==='collector'&&$do==='request'){
  $avail=$cashOf($u['id'])-$pendOf($u['id']);
  if($a<=0||$a>$avail)flash('Amount must be between 0 and ₹'.money($avail).' (cash on hand minus pending requests)','danger');
  else{$pdo->prepare("INSERT INTO handovers(fund_id,collector_id,amount,status) VALUES(?,?,?,'pending')")->execute([$fid,$u['id'],$a]);flash('Sent to creator for approval ✔');}
 }elseif($role==='creator'&&$do==='direct'){
  $cid=(int)$_POST['collector'];$cash=$cashOf($cid);
  if($cash===null||$a<=0||$a>$cash)flash('Invalid collector or amount exceeds cash on hand','danger');
  else{$pdo->prepare("INSERT INTO handovers(fund_id,collector_id,amount,status) VALUES(?,?,?,'approved')")->execute([$fid,$cid,$a]);flash('Transfer recorded');}
 }elseif($role==='creator'&&in_array($do,['approve','reject'])){
  $h=$pdo->prepare("SELECT * FROM handovers WHERE id=? AND fund_id=? AND status='pending'");$h->execute([(int)$_POST['hid'],$fid]);$h=$h->fetch();
  if(!$h)flash('Request not found','danger');
  elseif($do==='approve'&&$h['amount']>($cashOf($h['collector_id'])??0))flash('Amount exceeds collector cash on hand','danger');
  else{$pdo->prepare('UPDATE handovers SET status=? WHERE id=?')->execute([$do==='approve'?'approved':'rejected',$h['id']]);flash($do==='approve'?'Approved ✔':'Rejected');}
 }
 redirect("handover.php?id=$fid");
}
$sql='SELECT h.*,u.name FROM handovers h JOIN users u ON u.id=h.collector_id WHERE h.fund_id=?'.($role==='collector'?' AND h.collector_id=?':'').' ORDER BY h.id DESC';
$hs=$pdo->prepare($sql);$hs->execute($role==='collector'?[$fid,$u['id']]:[$fid]);$hist=$hs->fetchAll();
$badge=['pending'=>'warning','approved'=>'success','rejected'=>'danger'];
head('Transfer');?>
<h5>Fund Transfer / ഫണ്ട് കൈമാറ്റം</h5>
<?php if($role==='collector'):$cash=$cashOf($u['id']);$pn=$pendOf($u['id']);?>
<div class="card p-3 mb-3"><div>Cash on hand: <b>₹<?=money($cash)?></b></div><div class="small text-muted">Pending approval: ₹<?=money($pn)?></div>
<form method="post" class="mt-2"><?=csrf_field()?><input type="hidden" name="do" value="request">
<input class="form-control mb-2" type="number" step="0.01" min="1" name="amount" placeholder="Amount to transfer to creator ₹" required>
<button class="btn btn-primary w-100">Send for creator approval</button></form></div>
<?php else:?>
<?php foreach($hist as $r)if($r['status']==='pending'):?>
<div class="card p-2 mb-2 border border-warning"><div><b><?=e($r['name'])?></b> → Creator · <b>₹<?=money($r['amount'])?></b></div><small class="text-muted"><?=e($r['created_at'])?></small>
<form method="post" class="d-flex gap-1 mt-1"><?=csrf_field()?><input type="hidden" name="hid" value="<?=$r['id']?>">
<button name="do" value="approve" class="btn btn-sm btn-success">✔ Approve</button><button name="do" value="reject" class="btn btn-sm btn-outline-danger">✖ Reject</button></form></div>
<?php endif;?>
<?php foreach($cols as $m):?><div class="card p-2 mb-1 small"><b><?=e($m['name'])?></b> (<?=e($m['short'])?>) · Received ₹<?=money($m['received'])?> · Transferred ₹<?=money($m['handed'])?> · <b>On hand ₹<?=money($m['cash'])?></b></div><?php endforeach;?>
<?php if($cols):?><div class="card p-3 my-3"><b class="small mb-2">Record a transfer directly</b><form method="post"><?=csrf_field()?><input type="hidden" name="do" value="direct">
<select class="form-select mb-2" name="collector"><?php foreach($cols as $m):?><option value="<?=$m['id']?>"><?=e($m['name'])?> (on hand ₹<?=money($m['cash'])?>)</option><?php endforeach;?></select>
<input class="form-control mb-2" type="number" step="0.01" min="1" name="amount" placeholder="Amount ₹" required>
<button class="btn btn-primary w-100">Record</button></form></div><?php else:echo '<p class="text-muted">Add collectors first.</p>';endif;?>
<?php endif;?>
<h6 class="mt-3">History</h6>
<?php foreach($hist as $r):?><div class="card p-2 mb-1 small d-flex flex-row justify-content-between"><span><?=e($r['name'])?> → Creator · <b>₹<?=money($r['amount'])?></b><br><span class="text-muted"><?=e($r['created_at'])?></span></span><span class="badge bg-<?=$badge[$r['status']]?> align-self-center"><?=e($r['status'])?></span></div><?php endforeach;
if(!$hist)echo '<p class="text-muted small">Nothing yet.</p>';
foot();
