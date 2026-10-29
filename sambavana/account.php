<?php require 'config.php';$u=require_login();
// Own account: change name, password (current password needed). Admin can also change the login username.
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $s=$pdo->prepare('SELECT password FROM users WHERE id=?');$s->execute([$u['id']]);
 $n=trim($_POST['name']??'');$un=trim($_POST['username']??'');$p1=$_POST['p1']??'';$p2=$_POST['p2']??'';
 if(!password_verify($_POST['current']??'',$s->fetchColumn()))flash('Current password is wrong / നിലവിലെ പാസ്‌വേഡ് തെറ്റാണ്','danger');
 elseif($n==='')flash('Enter name','danger');
 elseif($u['role']==='admin'&&!preg_match('/^[A-Za-z0-9_.]{4,50}$/',$un))flash('Username: 4+ letters/digits (no spaces)','danger');
 elseif($p1!==''&&strlen($p1)<6)flash('New password must be at least 6 characters','danger');
 elseif($p1!==$p2)flash('New passwords do not match','danger');
 else try{
  $pdo->prepare('UPDATE users SET name=?'.($u['role']==='admin'?',username=?':'').($p1!==''?',password=?':'').' WHERE id=?')
   ->execute(array_merge([mb_substr($n,0,100)],$u['role']==='admin'?[$un]:[],$p1!==''?[password_hash($p1,PASSWORD_DEFAULT)]:[],[$u['id']]));
  flash('Saved ✔'.($p1!==''?' Password changed.':''));
 }catch(PDOException $x){flash('Username already taken','danger');}
 redirect('account.php');
}
head('My account');?>
<a href="dashboard.php" class="small">← Back</a>
<h5 class="mt-2">👤 My account / എന്റെ അക്കൗണ്ട്</h5>
<div class="card p-3"><form method="post" autocomplete="off"><?=csrf_field()?>
<label class="small text-muted">Name / പേര്</label>
<input class="form-control mb-2" name="name" value="<?=e($u['name'])?>" maxlength="100" required>
<label class="small text-muted">Login username</label>
<input class="form-control mb-3" name="username" value="<?=e($u['username'])?>" <?=$u['role']==='admin'?'required':'readonly disabled'?>>
<label class="small text-muted">New password (leave empty to keep) / പുതിയ പാസ്‌വേഡ്</label>
<input class="form-control mb-2" type="password" name="p1" autocomplete="new-password" placeholder="min 6 characters">
<input class="form-control mb-3" type="password" name="p2" autocomplete="new-password" placeholder="Repeat new password">
<label class="small text-muted">Current password (required to save) / നിലവിലെ പാസ്‌വേഡ്</label>
<input class="form-control mb-3" type="password" name="current" autocomplete="current-password" required>
<button class="btn btn-primary w-100">Save / സേവ്</button></form></div>
<?php foot();
