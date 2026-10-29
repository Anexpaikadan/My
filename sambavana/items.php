<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??$_POST['id']??0);if($role!=='creator'){http_response_code(403);die('Creator only');}
$fid=$f['id'];nav($f,$role,'home');
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();$do=$_POST['do']??'add';
 $n=trim($_POST['name']??'');$pr=(float)($_POST['price']??0);
 if($do==='add'){
  if($n===''||$pr<=0)flash('Enter product name and price','danger');
  else{$pdo->prepare('INSERT INTO fund_items(fund_id,name,price) VALUES(?,?,?)')->execute([$fid,mb_substr($n,0,100),$pr]);flash('Product added: '.$n.' ₹'.money($pr));}
 }else{
  $it=item_of($fid,$_POST['iid']??0);
  if(!$it)flash('Not found','danger');
  elseif($do==='save'){
   if($n===''||$pr<=0)flash('Enter product name and price','danger');
   else{$pdo->prepare('UPDATE fund_items SET name=?,price=? WHERE id=?')->execute([mb_substr($n,0,100),$pr,$it['id']]);flash('Saved (old entries keep their amount)');}
  }elseif($do==='toggle'){$pdo->prepare('UPDATE fund_items SET active=1-active WHERE id=?')->execute([$it['id']]);flash($it['active']?'Hidden from new entries':'Shown in new entries');}
  elseif($do==='delete'){
   $u=$pdo->prepare('SELECT COUNT(*) FROM contributions WHERE item_id=?');$u->execute([$it['id']]);
   if($u->fetchColumn()>0)flash('Product has entries — hide it instead of deleting','danger');
   else{$pdo->prepare('DELETE FROM fund_items WHERE id=?')->execute([$it['id']]);flash('Deleted');}
  }
 }
 redirect("items.php?id=$fid");
}
$s=$pdo->prepare('SELECT fi.*,COUNT(c.id) n,COALESCE(SUM(c.qty),0) q,COALESCE(SUM(c.amount),0) amt FROM fund_items fi LEFT JOIN contributions c ON c.item_id=fi.id AND c.cancelled=0 WHERE fi.fund_id=? GROUP BY fi.id ORDER BY fi.active DESC,fi.id');
$s->execute([$fid]);$items=$s->fetchAll();
head('Products');?>
<h5 class="mt-2">Products / ഇനങ്ങൾ</h5>
<p class="small text-muted">Fixed-price contributions, e.g. <b>Payasam ₹500</b>. In a new entry pick the product and the number (qty); the amount is filled automatically.<br>
നിശ്ചിത തുകയുള്ള ഇനങ്ങൾ (ഉദാ: പായസം ₹500). എൻട്രിയിൽ ഇനവും എണ്ണവും തിരഞ്ഞെടുത്താൽ തുക തനിയെ വരും.</p>
<div class="card p-3 mb-3"><form method="post" class="row g-2"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="do" value="add">
<div class="col-7"><input class="form-control" name="name" placeholder="Product (e.g. Payasam / പായസം)" maxlength="100" required></div>
<div class="col-5"><input class="form-control" type="number" step="0.01" min="1" name="price" placeholder="Price ₹" inputmode="decimal" required></div>
<div class="col-12"><button class="btn btn-primary w-100">＋ Add product</button></div></form></div>
<?php foreach($items as $it):?>
<div class="card p-2 mb-2<?=$it['active']?'':' opacity-75'?>">
<div class="d-flex justify-content-between"><span><b><?=e($it['name'])?></b> · ₹<?=money($it['price'])?> <?=$it['active']?'':'<span class="badge bg-secondary">hidden</span>'?></span>
<small class="text-muted"><?=$it['n']?> entries · qty <?=$it['q']?> · ₹<?=money($it['amt'])?></small></div>
<form method="post" class="d-flex gap-1 mt-2 flex-wrap"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="iid" value="<?=$it['id']?>">
<input class="form-control form-control-sm" style="max-width:160px" name="name" value="<?=e($it['name'])?>" maxlength="100">
<input class="form-control form-control-sm" style="max-width:100px" type="number" step="0.01" min="1" name="price" value="<?=e($it['price'])?>">
<button name="do" value="save" class="btn btn-sm btn-outline-primary">Save</button>
<button name="do" value="toggle" class="btn btn-sm btn-outline-secondary" formnovalidate><?=$it['active']?'Hide':'Show'?></button>
<?php if(!$it['n']):?><button name="do" value="delete" class="btn btn-sm btn-outline-danger" formnovalidate onclick="return confirm('Delete product?')">Delete</button><?php endif;?>
</form></div>
<?php endforeach; if(!$items)echo '<p class="text-muted">No products yet. Normal entries (any amount) still work.</p>';
foot();
