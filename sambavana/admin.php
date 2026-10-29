<?php require 'config.php';require_login(['admin']);
// Admin manages accounts. Deleting a user also deletes their funds (password confirmed).
$https=(!empty($_SERVER['HTTPS'])&&$_SERVER['HTTPS']!=='off')||($_SERVER['HTTP_X_FORWARDED_PROTO']??'')==='https';
$base=($https?'https':'http').'://'.$_SERVER['HTTP_HOST'].rtrim(dirname($_SERVER['SCRIPT_NAME']),'/').'/';
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();$id=(int)$_POST['id'];$do=$_POST['do']??'';
 if($do==='delete'){
  $ok=admin_pw_ok($_POST['pw']??'');
  $x=$pdo->prepare("SELECT name FROM users WHERE id=? AND role='user'");$x->execute([$id]);$x=$x->fetch();
  if($ok!==true)flash($ok,'danger');
  elseif(!$x)flash('User not found','danger');
  else try{$pdo->beginTransaction();delete_user($id);$pdo->commit();flash('Deleted user '.$x['name'].' and all their funds');}
  catch(Exception $e){if($pdo->inTransaction())$pdo->rollBack();flash('Could not delete, try again','danger');}
 }elseif($do==='link'){
  $x=$pdo->prepare("SELECT name,username FROM users WHERE id=? AND role='user'");$x->execute([$id]);$x=$x->fetch();
  if($x){$tok=bin2hex(random_bytes(32));
   $pdo->prepare('UPDATE users SET reset_token=?,reset_expires=DATE_ADD(NOW(),INTERVAL 24 HOUR) WHERE id=?')->execute([hash('sha256',$tok),$id]);
   $_SESSION['rlink']=[$x['name'],$x['username'],$base.'reset.php?t='.$tok];flash('Reset link created (valid 24 hours)');}
 }else{
  $st=['approve'=>'approved','reject'=>'rejected','block'=>'blocked'][$do]??null;
  if($st)$pdo->prepare("UPDATE users SET status=? WHERE id=? AND role='user'")->execute([$st,$id]);
 }
 redirect('admin.php');
}
$rl=$_SESSION['rlink']??null;unset($_SESSION['rlink']);
$rows=$pdo->query("SELECT id,name,username,status,reset_requested,created_at,(SELECT COUNT(*) FROM funds f WHERE f.creator_id=users.id) nf FROM users WHERE role='user' ORDER BY reset_requested DESC,FIELD(status,'pending','approved','blocked','rejected'),id DESC")->fetchAll();
nav_main('users');head('Admin');?>
<h5>Users / ഉപയോക്താക്കൾ</h5>
<?php if($rl):$m="സംഭാവന - Hello {$rl[0]}, set a new password using this link (valid 24 hours):\n{$rl[2]}";?>
<div class="alert alert-info"><b>Reset link for <?=e($rl[0])?></b> (shown only now)
<input readonly class="form-control form-control-sm my-2" value="<?=e($rl[2])?>" onclick="this.select()">
<a class="btn btn-sm btn-success" target="_blank" href="<?=e(wa($m,$rl[1]))?>">Send on WhatsApp</a></div><?php endif;?>
<?php foreach($rows as $r):?>
<div class="card p-2 mb-2"><div class="d-flex justify-content-between"><div><b><?=e($r['name'])?></b><br><small><?=e($r['username'])?> · <?=e($r['created_at'])?> · <?=$r['nf']?> fund<?=$r['nf']==1?'':'s'?></small></div>
<span class="text-end"><span class="badge bg-<?=['pending'=>'warning','approved'=>'success','blocked'=>'dark','rejected'=>'danger'][$r['status']]?>"><?=e($r['status'])?></span><?=$r['reset_requested']?'<br><span class="badge bg-info text-dark mt-1">🔑 reset requested</span>':''?></span></div>
<form method="post" class="mt-2 d-flex gap-1 flex-wrap"><?=csrf_field()?><input type="hidden" name="id" value="<?=$r['id']?>">
<?php if($r['status']!=='approved'):?><button name="do" value="approve" class="btn btn-sm btn-success">Approve</button><?php endif;?>
<?php if($r['status']==='pending'):?><button name="do" value="reject" class="btn btn-sm btn-danger">Reject</button><?php endif;?>
<?php if($r['status']==='approved'):?><button name="do" value="block" class="btn btn-sm btn-dark">Block</button><?php endif;?>
<?php if($r['status']!=='rejected'):?><button name="do" value="link" class="btn btn-sm btn-outline-primary">🔑 Reset link</button><?php endif;?>
<button type="button" class="btn btn-sm btn-outline-danger ms-auto" data-del="<?=$r['id']?>" data-what="<?=e('User: '.$r['name'].' ('.$r['username'].')'.($r['nf']?' — and '.$r['nf'].' fund(s) with all entries and payments':'').'. This cannot be undone.')?>"><i class="bi bi-trash3"></i> Delete</button>
</form></div>
<?php endforeach; if(!$rows)echo '<p class="text-muted">No users yet.</p>';
del_sheet('admin.php','delete');foot();
