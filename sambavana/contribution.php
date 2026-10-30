<?php require 'config.php';$u=require_login(['user','collector']);
$s=$pdo->prepare('SELECT c.*,fi.name item_name FROM contributions c'.ITEM_JOIN.'WHERE c.id=?');$s->execute([(int)($_GET['id']??$_POST['id']??0)]);$c=$s->fetch();
if(!$c){http_response_code(404);die('Not found');}
[$f,$role]=fund_access($c['fund_id']);nav($f,$role,'home');if($c['cancelled']){die('This entry was cancelled');}
$open=$f['status']==='open';$cid=$c['id'];
$paid=function()use($pdo,$cid){$q=$pdo->prepare('SELECT COALESCE(SUM(amount),0) FROM payments WHERE contribution_id=?');$q->execute([$cid]);return (float)$q->fetchColumn();};
// Creator only: correct or remove a payment
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();$do=$_POST['do']??'';
 $back="contribution.php?id=$cid";
 if($role!=='creator'||!$open){flash('Only the fund creator can change payments (fund must be open)','danger');redirect($back);}
 $p=$pdo->prepare('SELECT * FROM payments WHERE id=? AND contribution_id=?');$p->execute([(int)($_POST['pid']??0),$cid]);$p=$p->fetch();
 if(!$p){flash('Payment not found','danger');redirect($back);}
 $new=$do==='pdel'?0:round((float)($_POST['amount']??0),2);$diff=$p['amount']-$new;
 // the person who received it must still have that cash (not already handed over)
 $cash=null;foreach(members($f) as $m)if($m['id']==$p['received_by'])$cash=$m['cash'];
 if($do==='pedit'&&$new<=0)flash('Enter an amount (or delete the payment)','danger');
 elseif($do==='pedit'&&$paid()-$p['amount']+$new>$c['amount']+0.001)flash('Paid would be more than the contribution ₹'.money($c['amount']),'danger');
 elseif($diff>0&&$cash!==null&&$cash-$diff<-0.001)flash('Cannot: that money was already transferred to the creator. Change the transfer first.','danger');
 elseif($do==='pdel'){$pdo->prepare('DELETE FROM payments WHERE id=?')->execute([$p['id']]);flash('Payment ₹'.money($p['amount']).' deleted');}
 elseif($do==='pedit'){$pdo->prepare('UPDATE payments SET amount=? WHERE id=?')->execute([$new,$p['id']]);flash('Payment changed: ₹'.money($p['amount']).' → ₹'.money($new));}
 redirect($back);
}
$pay=$pdo->prepare('SELECT p.*,u.name,u.short_name FROM payments p JOIN users u ON u.id=p.received_by WHERE contribution_id=? ORDER BY p.id');$pay->execute([$cid]);$pays=$pay->fetchAll();
$paidAmt=$paid();$bal=$c['amount']-$paidAmt;$pc=$c['amount']>0?(int)min(100,round($paidAmt/$c['amount']*100)):0;
$head="*{$f['title']}*\nReceipt #{$c['serial_no']}\nName: {$c['name']}\n".($c['item_name']?"Item: ".item_label($c)." (₹".money($c['amount']/$c['qty'])." each)\n":'');
$only=$head."Contribution: ₹".money($c['amount'])."\nThank you 🙏";
$full=$head."Total: ₹".money($c['amount'])."\nPaid: ₹".money($paidAmt)."\nBalance: ₹".money($bal).($bal<=0?' ✅':' ⏳')."\n";
if($pays){$full.="\nPayments:\n";foreach($pays as $i=>$p)$full.=($i+1).") ".date('d-m-Y',strtotime($p['created_at']))." – ₹".money($p['amount'])."\n";}
$full.="\nThank you 🙏";
$cr=$role==='creator'&&$open;
head('#'.$c['serial_no'].' '.$c['name']);?>
<style>
.ph{border-radius:20px;padding:16px;background:#fff;box-shadow:0 2px 10px #3513d61a}
.ph .sum{display:grid;grid-template-columns:repeat(3,1fr);text-align:center;margin-top:12px}
.ph .sum small{display:block;color:#666;font-size:12px}.ph .sum b{font-size:1.1rem}
.tl{position:relative;padding-left:22px}
.tl:before{content:"";position:absolute;left:8px;top:6px;bottom:6px;width:2px;background:#e3dff7}
.tl .pt{position:relative;background:#fff;border-radius:14px;padding:10px 12px;margin-bottom:8px;box-shadow:0 1px 4px #3513d614;display:flex;align-items:center;gap:8px}
.tl .pt:before{content:"";position:absolute;left:-19px;top:16px;width:12px;height:12px;border-radius:50%;background:var(--g);border:2px solid #fff;box-shadow:0 0 0 2px #7ed95766}
</style>
<div class="ph mb-3">
<div class="d-flex justify-content-between align-items-start gap-2"><div><span class="text-muted small">No. <?=$c['serial_no']?><?=$c['mobile']?' · '.e($c['mobile']):''?></span><h5 class="m-0"><?=nm($c['name'],$bal)?></h5>
<?php if($c['item_name']):?><span class="itm"><?=e(item_label($c))?></span> <small class="text-muted">₹<?=money($c['amount']/$c['qty'])?> each</small><?php endif;?></div>
<?=bal_badge($bal)?></div>
<div class="progress mt-3" style="height:8px"><div class="progress-bar bg-success" style="width:<?=$pc?>%"></div></div>
<div class="sum"><div><small>Total</small><b>₹<?=money($c['amount'])?></b></div><div><small>Paid</small><b class="text-success">₹<?=money($paidAmt)?></b></div><div><small>Balance</small><b class="text-danger">₹<?=money(max(0,$bal))?></b></div></div>
</div>
<div class="d-grid gap-2 mb-3 noprint">
<?php if($bal>0&&$open):?><a class="btn btn-primary btn-lg" href="pay.php?id=<?=$f['id']?>&c=<?=$cid?>"><i class="bi bi-cash-coin"></i> Add payment / പണം ചേർക്കുക</a><?php endif;?>
<div class="d-flex gap-2"><a class="btn btn-success flex-fill" target="_blank" href="<?=e(wa($full,$c['mobile']))?>"><i class="bi bi-whatsapp"></i> Receipt</a>
<a class="btn btn-outline-success flex-fill" target="_blank" href="<?=e(wa($only,$c['mobile']))?>"><i class="bi bi-whatsapp"></i> Contribution only</a></div>
<?php if($cr):?><a class="btn btn-outline-primary" href="edit.php?id=<?=$cid?>"><i class="bi bi-pencil"></i> Edit / cancel entry</a><?php endif;?></div>
<h6 class="fw-bold">Payments / പണമടവുകൾ (<?=count($pays)?>)</h6>
<?php if($pays):?><div class="tl"><?php foreach($pays as $p):?>
<div class="pt"><span class="flex-grow-1"><b>₹<?=money($p['amount'])?></b><br><small class="text-muted"><?=date('d M Y, g:i a',strtotime($p['created_at']))?> · by <?=e(sn($p['name'],$p['short_name']))?></small></span>
<?php if($cr):?><button type="button" class="btn btn-sm btn-light rounded-circle" data-pe="<?=$p['id']?>" data-a="<?=(float)$p['amount']?>" aria-label="Edit"><i class="bi bi-pencil"></i></button>
<button type="button" class="btn btn-sm btn-light rounded-circle text-danger" data-pd="<?=$p['id']?>" data-a="<?=money($p['amount'])?>" aria-label="Delete"><i class="bi bi-trash3"></i></button><?php endif;?></div>
<?php endforeach;?></div><?php else:echo '<p class="text-muted small">No payments yet.</p>';endif;?>
<?php if($cr&&$pays):?>
<div class="modal fade sheet" id="pe" tabindex="-1" aria-hidden="true"><div class="modal-dialog"><div class="modal-content"><div class="grab"></div>
<form method="post"><?=csrf_field()?><input type="hidden" name="id" value="<?=$cid?>"><input type="hidden" name="pid" id="peid"><input type="hidden" name="do" id="pedo">
<div class="modal-header border-0 pb-0"><h5 class="modal-title" id="pet"></h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
<div class="modal-body"><div id="pebox"><label class="small text-muted">Correct amount ₹</label><input id="pea" class="form-control form-control-lg" type="number" step="0.01" min="1" name="amount" inputmode="decimal"></div>
<div id="pdbox" class="alert alert-danger mb-0"></div></div>
<div class="modal-footer border-0 pt-0"><button class="btn btn-lg w-100" id="pes"></button></div></form></div></div></div>
<script>
window.addEventListener('load',function(){var m=new bootstrap.Modal(document.getElementById('pe')),a=document.getElementById('pea');
 function show(id,edit,amt){document.getElementById('peid').value=id;document.getElementById('pedo').value=edit?'pedit':'pdel';
  document.getElementById('pet').textContent=edit?'Edit payment':'Delete payment?';
  document.getElementById('pebox').style.display=edit?'':'none';a.required=edit;a.value=edit?amt:'';
  var d=document.getElementById('pdbox');d.style.display=edit?'none':'';d.textContent='Delete payment of ₹'+amt+'? The balance will go up by this amount.';
  var b=document.getElementById('pes');b.className='btn btn-lg w-100 '+(edit?'btn-primary':'btn-danger');b.textContent=edit?'Save change':'Delete payment';m.show();}
 document.querySelectorAll('[data-pe]').forEach(function(b){b.onclick=function(){show(b.dataset.pe,true,b.dataset.a);};});
 document.querySelectorAll('[data-pd]').forEach(function(b){b.onclick=function(){show(b.dataset.pd,false,b.dataset.a);};});
});
</script>
<?php endif;
foot();
