<?php require 'config.php';require_login(['admin']);
// Admin: list of all funds; delete a fund with everything in it (password confirmed)
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 if(($_POST['do']??'')==='delete'){
  $ok=admin_pw_ok($_POST['pw']??'');
  $x=$pdo->prepare('SELECT title FROM funds WHERE id=?');$x->execute([(int)$_POST['id']]);$x=$x->fetch();
  if($ok!==true)flash($ok,'danger');
  elseif(!$x)flash('Fund not found','danger');
  else try{$pdo->beginTransaction();delete_fund($_POST['id']);$pdo->commit();flash('Deleted fund: '.$x['title']);}
  catch(Exception $e){if($pdo->inTransaction())$pdo->rollBack();flash('Could not delete, try again','danger');}
 }
 redirect('admin_funds.php');
}
$rows=$pdo->query("SELECT f.id,f.title,f.type,f.status,f.created_at,u.name,u.username,
 (SELECT COUNT(*) FROM contributions c WHERE c.fund_id=f.id AND c.cancelled=0) n,
 (SELECT COUNT(*) FROM users k WHERE k.role='collector' AND k.fund_id=f.id) nc
 FROM funds f JOIN users u ON u.id=f.creator_id ORDER BY f.id DESC")->fetchAll();
nav_main('funds');head('Funds');?>
<h5>All funds / എല്ലാ ഫണ്ടുകളും <span class="badge bg-secondary"><?=count($rows)?></span></h5>
<?php foreach($rows as $r):?>
<div class="card p-2 mb-2"><div class="d-flex justify-content-between gap-2"><div class="min-w-0"><b><?=e($r['title'])?></b><br>
<small class="text-muted"><?=e($r['name'])?> (<?=e($r['username'])?>) · <?=e(ucfirst($r['type']))?> · <?=date('d-m-Y',strtotime($r['created_at']))?></small><br>
<small><?=$r['n']?> entries · <?=$r['nc']?> collectors</small></div>
<div class="text-end"><span class="badge bg-<?=$r['status']==='open'?'success':'secondary'?>"><?=e($r['status'])?></span><br>
<button type="button" class="btn btn-sm btn-outline-danger mt-2" data-del="<?=$r['id']?>" data-what="<?=e('Fund: '.$r['title'].' (by '.$r['name'].') — '.$r['n'].' entries, payments, products, transfers and '.$r['nc'].' collector logins. This cannot be undone.')?>"><i class="bi bi-trash3"></i> Delete</button></div></div></div>
<?php endforeach; if(!$rows)echo '<p class="text-muted">No funds yet.</p>';
del_sheet('admin_funds.php','delete');foot();
