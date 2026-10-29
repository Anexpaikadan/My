<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??0);if($role!=='creator'){http_response_code(403);die('Creator only');}
$fid=$f['id'];nav($f,$role,'team');$new=$_SESSION['newcol']??null;unset($_SESSION['newcol']);
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $do=$_POST['do']??'add';
 if($do!=='add'){
  $x=$pdo->prepare("SELECT * FROM users WHERE id=? AND role='collector' AND fund_id=?");$x->execute([(int)$_POST['uid'],$fid]);$x=$x->fetch();
  if(!$x)flash('Not found','danger');
  elseif($do==='block'||$do==='unblock'){$pdo->prepare('UPDATE users SET status=? WHERE id=?')->execute([$do==='block'?'blocked':'approved',$x['id']]);flash($do==='block'?'Collector blocked':'Collector unblocked');}
  elseif($do==='reset'){$pw=$_POST['password']??'';
   if(strlen($pw)<4)flash('Enter a new password (4+ characters)','danger');
   else{$pdo->prepare('UPDATE users SET password=? WHERE id=?')->execute([password_hash($pw,PASSWORD_DEFAULT),$x['id']]);$_SESSION['newcol']=[$x['name'],$x['username'],$pw];flash('Password reset');}}
  redirect("collectors.php?id=$fid");
 }
 $n=trim($_POST['name']);$sh=mb_strtoupper(trim($_POST['short']));$un=trim($_POST['username']);$pw=$_POST['password'];
 if($n===''||$sh===''||!preg_match('/^[A-Za-z0-9_.]{4,30}$/',$un)||strlen($pw)<4)flash('Fill all fields (username 4+ letters/digits, password 4+)','danger');
 else try{
  $pdo->prepare("INSERT INTO users(name,username,password,role,status,short_name,fund_id) VALUES(?,?,?,'collector','approved',?,?)")
   ->execute([$n,$un,password_hash($pw,PASSWORD_DEFAULT),mb_substr($sh,0,10),$fid]);
  $_SESSION['newcol']=[$n,$un,$pw];flash('Collector added');
 }catch(PDOException $x){flash('Username already taken','danger');}
 redirect("collectors.php?id=$fid");
}
$cols=$pdo->prepare("SELECT * FROM users WHERE role='collector' AND fund_id=? ORDER BY id");$cols->execute([$fid]);$cols=$cols->fetchAll();
$base=(isset($_SERVER['HTTPS'])?'https':'http').'://'.$_SERVER['HTTP_HOST'].rtrim(dirname($_SERVER['SCRIPT_NAME']),'/').'/';
head('Collectors');?>
<a href="fund.php?id=<?=$fid?>" class="small">← <?=e($f['title'])?></a><h5 class="mt-2">Collectors / കളക്ടർമാർ</h5>
<?php if($new):$m="*{$f['title']}* - Collector login\nName: {$new[0]}\nLink: {$base}\nUsername: {$new[1]}\nPassword: {$new[2]}";?>
<div class="alert alert-info">Share now — password cannot be shown again.<br><b><?=e($new[1])?></b> / <b><?=e($new[2])?></b><br>
<a class="btn btn-sm btn-success mt-2" target="_blank" href="<?=e(wa($m))?>">Share on WhatsApp</a></div><?php endif;?>
<div class="card p-3 mb-3"><form method="post"><?=csrf_field()?>
<input class="form-control mb-2" name="name" placeholder="Collector name" required>
<input class="form-control mb-2" name="short" placeholder="Short name (e.g. JP)" maxlength="10" required>
<input class="form-control mb-2" name="username" placeholder="Username" required>
<input class="form-control mb-2" name="password" placeholder="Password" required>
<button class="btn btn-primary w-100">Add Collector</button></form></div>
<?php foreach($cols as $c):$act=$c['status']==='approved';?><div class="card p-2 mb-2"><div class="d-flex justify-content-between"><span><b><?=e($c['name'])?></b> <small class="text-muted">(<?=e(sn($c['name'],$c['short_name']))?>) · <?=e($c['username'])?></small></span><span class="badge bg-<?=$act?'success':'dark'?>"><?=$act?'active':'blocked'?></span></div>
<form method="post" class="d-flex gap-1 mt-2 flex-wrap"><?=csrf_field()?><input type="hidden" name="uid" value="<?=$c['id']?>">
<input class="form-control form-control-sm" style="max-width:140px" name="password" placeholder="New password">
<button name="do" value="reset" class="btn btn-sm btn-outline-primary">Reset password</button>
<button name="do" value="<?=$act?'block':'unblock'?>" class="btn btn-sm btn-outline-<?=$act?'danger':'success'?>"><?=$act?'Block':'Unblock'?></button></form></div><?php endforeach;
foot();
