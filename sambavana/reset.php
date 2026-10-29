<?php require 'config.php';
$tok=(string)($_GET['t']??$_POST['t']??'');
$s=$pdo->prepare("SELECT id,name FROM users WHERE reset_token=? AND reset_expires>NOW() AND role='user'");
$s->execute([hash('sha256',$tok)]);$usr=$tok===''?false:$s->fetch();
if(!$usr){head('Reset password');echo '<div class="alert alert-danger">This link is invalid or expired. Ask the admin for a new one.<br>ലിങ്ക് അസാധുവാണ് / കാലാവധി കഴിഞ്ഞു.</div><a href="forgot.php">Request a new link</a>';foot();exit;}
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $a=$_POST['p1']??'';$b=$_POST['p2']??'';
 if(strlen($a)<6)flash('Password must be at least 6 characters','danger');
 elseif($a!==$b)flash('Passwords do not match','danger');
 else{
  $pdo->prepare('UPDATE users SET password=?,reset_token=NULL,reset_expires=NULL,reset_requested=0 WHERE id=?')->execute([password_hash($a,PASSWORD_DEFAULT),$usr['id']]);
  flash('Password changed. Please login / പാസ്‌വേഡ് മാറ്റി, ലോഗിൻ ചെയ്യുക');redirect('index.php');
 }
 redirect('reset.php?t='.urlencode($tok));
}
head('Reset password');?>
<div class="text-center mb-3"><img src="logo.png" style="max-width:220px;width:70%" alt=""></div>
<div class="card p-3"><h5>New password</h5><p class="small text-muted">Hello <?=e($usr['name'])?></p>
<form method="post"><?=csrf_field()?><input type="hidden" name="t" value="<?=e($tok)?>">
<input class="form-control mb-2" type="password" name="p1" placeholder="New password (min 6)" required>
<input class="form-control mb-2" type="password" name="p2" placeholder="Repeat password" required>
<button class="btn btn-primary w-100">Change password</button></form></div>
<?php foot();
