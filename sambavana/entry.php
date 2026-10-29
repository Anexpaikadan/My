<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'entry');
if($f['status']==='closed'){head('Entry');echo '<div class="alert alert-secondary">🔒 This fund is closed. Creator can reopen it in Settings.</div>';foot();exit;}
$err='';$v=['name'=>'','mobile'=>'','amount'=>'','pay'=>''];
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 foreach($v as $k=>$_)$v[$k]=trim($_POST[$k]??'');
 $mob=preg_replace('/\D/','',$v['mobile']);$mob=$mob===''?null:substr($mob,-10);
 $amt=(float)$v['amount'];$pay=(float)($v['pay']===''?0:$v['pay']);
 if($v['name']==='')$err='Enter contributor name / പേര് നൽകുക';
 elseif($mob!==null&&strlen($mob)!==10)$err='Mobile must be 10 digits';
 elseif($amt<=0)$err='Enter contribution amount / തുക നൽകുക';
 elseif($pay<0||$pay>$amt)$err='Payment cannot be more than the contribution';
 else try{
  $pdo->beginTransaction();
  $s=$pdo->prepare('SELECT COALESCE(MAX(serial_no),0)+1 FROM contributions WHERE fund_id=? FOR UPDATE');$s->execute([$fid]);$sl=(int)$s->fetchColumn();
  $pdo->prepare('INSERT INTO contributions(fund_id,serial_no,name,mobile,amount,created_by) VALUES(?,?,?,?,?,?)')->execute([$fid,$sl,$v['name'],$mob,$amt,$u['id']]);
  $cid=$pdo->lastInsertId();
  if($pay>0)$pdo->prepare('INSERT INTO payments(contribution_id,amount,received_by) VALUES(?,?,?)')->execute([$cid,$pay,$u['id']]);
  $pdo->commit();
  if(isset($_POST['next'])){flash("Saved: No. $sl ✔ — add next");redirect("entry.php?id=$fid");}
  flash("Saved: No. $sl — share the receipt below");redirect("contribution.php?id=$cid");
 }catch(Exception $x){if($pdo->inTransaction())$pdo->rollBack();$err='Could not save, try again';}
}
$n=$pdo->prepare('SELECT COALESCE(MAX(serial_no),0)+1 FROM contributions WHERE fund_id=?');$n->execute([$fid]);$next=(int)$n->fetchColumn();
$r=$pdo->prepare('SELECT c.*,COALESCE(SUM(p.amount),0) paid FROM contributions c LEFT JOIN payments p ON p.contribution_id=c.id WHERE c.fund_id=? AND c.cancelled=0 GROUP BY c.id ORDER BY c.id DESC LIMIT 8');$r->execute([$fid]);$rows=$r->fetchAll();
head('Entry');?>
<style>
#em .modal-dialog{position:fixed;left:0;right:0;bottom:0;margin:0 auto;width:100%;max-width:820px}
#em .modal-content{border:0;border-radius:20px 20px 0 0;max-height:92vh;overflow-y:auto}
#em.fade .modal-dialog{transform:translateY(100%);transition:transform .3s ease}
#em.show .modal-dialog{transform:none}
#em .grab{width:44px;height:5px;border-radius:3px;background:#d0d0dc;margin:8px auto 0}
#em .bigamt{font-size:1.6rem;font-weight:700;color:var(--p)}
</style>
<div class="d-flex justify-content-between align-items-center mb-2"><h5 class="m-0">Entries / എൻട്രികൾ</h5>
<button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#em">＋ New entry</button></div>
<p class="small text-muted">Recent / അവസാനത്തെ എൻട്രികൾ</p>
<?php foreach($rows as $x):$bal=$x['amount']-$x['paid'];?>
<a href="contribution.php?id=<?=$x['id']?>" class="card p-2 mb-1 text-decoration-none text-dark"><div class="d-flex justify-content-between"><span><b>#<?=$x['serial_no']?></b> <?=e($x['name'])?></span><span><?=$bal<=0?'✅':'☑️ ₹'.money($bal)?></span></div>
<small class="text-muted">₹<?=money($x['amount'])?> · Paid ₹<?=money($x['paid'])?></small></a>
<?php endforeach; if(!$rows)echo '<p class="text-muted">No entries yet.</p>';?>

<div class="modal fade" id="em" tabindex="-1" aria-hidden="true"><div class="modal-dialog"><div class="modal-content">
<div class="grab"></div>
<form method="post" autocomplete="off"><?=csrf_field()?>
<div class="modal-header border-0 pb-0"><div><h5 class="modal-title m-0">New Contribution</h5><small class="text-muted">പുതിയ സംഭാവന · No. <b><?=$next?></b></small></div>
<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
<div class="modal-body">
<?php if($err):?><div class="alert alert-danger py-2"><?=e($err)?></div><?php endif;?>
<label class="small text-muted">Contributor name / പേര്</label>
<input id="nm" class="form-control form-control-lg mb-2" name="name" value="<?=e($v['name'])?>" required>
<label class="small text-muted">Mobile (optional) / മൊബൈൽ</label>
<input class="form-control mb-3" name="mobile" value="<?=e($v['mobile'])?>" inputmode="numeric" maxlength="13" placeholder="For WhatsApp receipt & reminder">
<label class="small text-muted">Contribution amount ₹ / സംഭാവന</label>
<input id="amt" class="form-control bigamt mb-1" type="number" step="0.01" min="1" name="amount" value="<?=e($v['amount'])?>" inputmode="decimal" placeholder="0" required>
<div class="d-flex flex-wrap gap-1 mb-3"><?php foreach([100,200,500,1000,2000] as $c)echo '<button type="button" class="btn btn-sm btn-outline-primary chip" data-v="'.$c.'">₹'.$c.'</button>';?></div>
<label class="small text-muted">Payment now ₹ / ഇപ്പോൾ നൽകിയത്</label>
<div class="input-group mb-1"><input id="pay" class="form-control form-control-lg" type="number" step="0.01" min="0" name="pay" value="<?=e($v['pay'])?>" inputmode="decimal" placeholder="0">
<button type="button" id="full" class="btn btn-outline-success">Full</button></div>
<div id="pv" class="small mb-1"></div>
</div>
<div class="modal-footer border-0 pt-0 d-grid gap-2">
<button class="btn btn-primary btn-lg">Save / സേവ്</button>
<button name="next" value="1" class="btn btn-outline-primary">Save &amp; add next</button></div>
</form></div></div></div>
<script>
window.addEventListener('load',function(){
 var el=document.getElementById('em'),m=new bootstrap.Modal(el);m.show();
 var a=document.getElementById('amt'),p=document.getElementById('pay'),pv=document.getElementById('pv');
 function upd(){var x=parseFloat(a.value)||0,y=parseFloat(p.value)||0,b=x-y;
  if(y>x){pv.className='small text-danger';pv.textContent='⚠ Payment is more than the contribution';}
  else if(x>0){pv.className='small fw-bold '+(b>0?'text-danger':'text-success');pv.textContent=b>0?'Balance ₹'+b.toFixed(2):'Fully paid ✅';}
  else pv.textContent='';}
 a.oninput=p.oninput=upd;
 document.querySelectorAll('.chip').forEach(function(c){c.onclick=function(){a.value=c.dataset.v;upd();};});
 document.getElementById('full').onclick=function(){p.value=a.value;upd();};
 el.addEventListener('shown.bs.modal',function(){document.getElementById('nm').focus();});
 upd();
});
</script>
<?php foot();
