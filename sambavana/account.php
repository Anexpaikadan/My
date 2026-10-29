<?php require 'config.php';$u=require_login();
// Own account: change name, password (current password needed). Admin can also change the login username.
if($_SERVER['REQUEST_METHOD']==='POST'&&($_POST['do']??'')==='newfund'&&$u['role']==='user'){csrf_check();
 $t=trim($_POST['title']??'');
 if($t===''){flash('Title required','danger');redirect('account.php#new');}
 $type=in_array($_POST['type']??'',['charity','festival','other'],true)?$_POST['type']:'other';
 $pdo->prepare('INSERT INTO funds(creator_id,title,description,type,start_date,creator_details) VALUES(?,?,?,?,?,?)')
  ->execute([$u['id'],mb_substr($t,0,200),trim($_POST['description']??''),$type,($_POST['start_date']??'')?:date('Y-m-d'),trim($_POST['creator_details']??'')]);
 flash('Fund created ✔ Add products or the first contribution.');redirect('fund.php?id='.$pdo->lastInsertId());
}
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
nav_main('account');head('My account');?>
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
<?php if($u['role']==='user'):$fs=$pdo->prepare('SELECT id,title,status FROM funds WHERE creator_id=? ORDER BY id DESC');$fs->execute([$u['id']]);$fs=$fs->fetchAll();?>
<h6 class="fw-bold mt-4 mb-2"><i class="bi bi-collection"></i> My funds / എന്റെ ഫണ്ടുകൾ (<?=count($fs)?>)</h6>
<div class="card mb-3"><?php foreach($fs as $x):?><a class="d-flex justify-content-between align-items-center p-2 px-3 border-bottom text-decoration-none text-dark" href="fund.php?id=<?=$x['id']?>"><span><?=e($x['title'])?> <?=$x['status']==='closed'?'<span class="badge bg-secondary">closed</span>':''?></span><i class="bi bi-chevron-right text-muted"></i></a><?php endforeach;if(!$fs)echo '<p class="text-muted p-3 mb-0">No funds yet.</p>';?></div>
<div id="new" class="card p-3" style="scroll-margin-top:70px"><b class="mb-2"><i class="bi bi-plus-circle"></i> Create new fund / പുതിയ ഫണ്ട്</b>
<form method="post"><?=csrf_field()?><input type="hidden" name="do" value="newfund">
<input id="nft" class="form-control form-control-lg mb-2" name="title" placeholder="Fund title / ഫണ്ടിന്റെ പേര്" maxlength="200" required>
<select class="form-select mb-2" name="type"><option value="charity">Charity / ചാരിറ്റി</option><option value="festival">Festival / ഉത്സവം</option><option value="other">Other</option></select>
<input class="form-control mb-2" type="date" name="start_date" value="<?=date('Y-m-d')?>">
<textarea class="form-control mb-2" name="description" rows="3" placeholder="Description / വിവരണം"></textarea>
<textarea class="form-control mb-2" name="creator_details" rows="2" placeholder="Creator details (name, phone, place)"></textarea>
<button class="btn btn-primary btn-lg w-100">Create Fund</button></form></div>
<script>function nfo(){if(location.hash==='#new'){document.getElementById('new').scrollIntoView();setTimeout(function(){document.getElementById('nft').focus();},300);}}nfo();window.addEventListener('hashchange',nfo);</script>
<?php endif;?>
<a class="btn btn-outline-danger w-100 mt-3" href="logout.php"><i class="bi bi-box-arrow-right"></i> Logout / ലോഗൗട്ട്</a>
<?php foot();
