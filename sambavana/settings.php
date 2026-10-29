<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??$_POST['id']??0);if($role!=='creator'){http_response_code(403);die('Creator only');}
$fid=$f['id'];
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();$do=$_POST['do']??'';
 if($do==='settings'){
  $t=(float)($_POST['target']??0);
  $pdo->prepare('UPDATE funds SET target_amount=?,show_target=?,reminders=? WHERE id=?')->execute([$t>0?$t:null,isset($_POST['show_target'])?1:0,isset($_POST['reminders'])?1:0,$fid]);
  flash('Settings saved');
 }elseif($do==='details'){
  $ti=trim($_POST['title']??'');
  if($ti==='')flash('Title required','danger');
  else{$pdo->prepare('UPDATE funds SET title=?,description=?,creator_details=? WHERE id=?')->execute([mb_substr($ti,0,200),trim($_POST['description']??''),trim($_POST['creator_details']??''),$fid]);flash('Fund details saved');}
 }elseif($do==='close'||$do==='reopen'){
  $pdo->prepare('UPDATE funds SET status=? WHERE id=?')->execute([$do==='close'?'closed':'open',$fid]);
  flash($do==='close'?'Fund closed 🔒':'Fund reopened');
 }
 redirect("settings.php?id=$fid");
}
nav($f,$role,'home');head('Settings');
$cn=$pdo->prepare('SELECT name FROM users WHERE id=?');$cn->execute([$f['creator_id']]);$cn=$cn->fetchColumn();
$share="*{$f['title']}*\n{$f['description']}\n\nCreator: $cn";
if($f['show_target']&&$f['target_amount']>0)$share.="\nTarget: ₹".money($f['target_amount']);?>
<div class="card p-3 mb-3"><b class="mb-2"><i class="bi bi-sliders"></i> Options / ക്രമീകരണം</b>
<form method="post"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="do" value="settings">
<label class="small text-muted">🎯 Target amount ₹ (leave 0 for none)</label>
<input class="form-control mb-2" type="number" step="0.01" min="0" name="target" value="<?=e($f['target_amount']?(float)$f['target_amount']:0)?>">
<div class="form-check form-switch mb-2"><input class="form-check-input" type="checkbox" name="show_target" id="s1" <?=$f['show_target']?'checked':''?>><label class="form-check-label" for="s1">Show target progress (creator only)</label></div>
<div class="form-check form-switch mb-3"><input class="form-check-input" type="checkbox" name="reminders" id="s2" <?=$f['reminders']?'checked':''?>><label class="form-check-label" for="s2">Balance reminders (Pending button for all)</label></div>
<button class="btn btn-primary w-100">Save</button></form></div>
<div class="card p-3 mb-3"><b class="mb-2"><i class="bi bi-pencil-square"></i> Fund details</b>
<form method="post"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="do" value="details">
<input class="form-control mb-2" name="title" value="<?=e($f['title'])?>" maxlength="200" required>
<textarea class="form-control mb-2" name="description" rows="3" placeholder="Description / വിവരണം"><?=e($f['description'])?></textarea>
<textarea class="form-control mb-2" name="creator_details" rows="2" placeholder="Creator details (name, phone, place)"><?=e($f['creator_details'])?></textarea>
<button class="btn btn-outline-primary w-100">Save details</button></form></div>
<div class="d-grid gap-2 mb-3">
<a class="btn btn-success" target="_blank" href="<?=e(wa($share))?>"><i class="bi bi-whatsapp"></i> Share fund on WhatsApp</a>
<a class="btn btn-outline-primary" href="items.php?id=<?=$fid?>"><i class="bi bi-bag"></i> Products (e.g. Payasam ₹500)</a>
<a class="btn btn-outline-primary" href="import.php?id=<?=$fid?>"><i class="bi bi-file-earmark-excel"></i> Import entries from Excel</a>
<a class="btn btn-outline-primary" href="collectors.php?id=<?=$fid?>"><i class="bi bi-people"></i> Collectors</a></div>
<form method="post" onsubmit="return confirm('<?=$f['status']==='open'?'Close fund? Entries will be locked.':'Reopen fund?'?>')"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>">
<button name="do" value="<?=$f['status']==='open'?'close':'reopen'?>" class="btn btn-outline-<?=$f['status']==='open'?'danger':'success'?> w-100"><?=$f['status']==='open'?'🔒 Close fund':'🔓 Reopen fund'?></button></form>
<?php foot();
