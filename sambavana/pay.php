<?php require 'config.php';
// Add payment: pick a contributor, enter the amount; it is added to what they paid before.
[$f,$role]=fund_access($_GET['id']??$_POST['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'pay');
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $s=$pdo->prepare('SELECT c.*,(SELECT COALESCE(SUM(amount),0) FROM payments WHERE contribution_id=c.id) paid FROM contributions c WHERE c.id=? AND c.fund_id=? AND c.cancelled=0');
 $s->execute([(int)($_POST['cid']??0),$fid]);$c=$s->fetch();$a=round((float)($_POST['amount']??0),2);
 if($f['status']!=='open'){flash('Fund is closed','danger');redirect("pay.php?id=$fid");}
 if(!$c){flash('Choose a contributor','danger');redirect("pay.php?id=$fid");}
 $bal=$c['amount']-$c['paid'];
 if($a<=0||$a>$bal+0.001){flash('Amount must be between 1 and balance ₹'.money($bal),'danger');redirect("pay.php?id=$fid&c={$c['id']}");}
 $pdo->prepare('INSERT INTO payments(contribution_id,amount,received_by) VALUES(?,?,?)')->execute([$c['id'],$a,$u['id']]);
 $nb=$bal-$a;$msg="₹".money($a)." received from #{$c['serial_no']} {$c['name']} ✔ ".($nb>0?'Balance ₹'.money($nb):'Fully paid');
 flash($msg);
 redirect(isset($_POST['next'])?"pay.php?id=$fid":"contribution.php?id={$c['id']}");
}
$all=($_GET['all']??'')==='1';
$s=$pdo->prepare('SELECT c.id,c.serial_no,c.name,c.mobile,c.amount,c.qty,MAX(fi.name) item_name,COALESCE(SUM(p.amount),0) paid FROM contributions c'.ITEM_JOIN.'LEFT JOIN payments p ON p.contribution_id=c.id WHERE c.fund_id=? AND c.cancelled=0 GROUP BY c.id'.($all?'':' HAVING c.amount>paid').' ORDER BY c.serial_no');
$s->execute([$fid]);$rows=$s->fetchAll();
$sel=(int)($_GET['c']??0);
head('Add payment');
if($f['status']!=='open'){echo '<div class="alert alert-secondary">🔒 This fund is closed. Payments are locked.</div>';foot();exit;}?>
<style>
.pick{display:flex;align-items:center;gap:10px;padding:10px 12px;background:#fff;border-radius:14px;margin-bottom:6px;box-shadow:0 1px 4px #3513d614;cursor:pointer;border:2px solid transparent}
.pick:active{transform:scale(.98)}
.pick.on{border-color:var(--p);background:#f6f4ff}
.pick .no{width:40px;height:40px;border-radius:12px;background:#ece8ff;color:var(--p);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex:none}
#sq{border-radius:14px}
.sum{display:grid;grid-template-columns:repeat(3,1fr);text-align:center;background:#f6f4ff;border-radius:14px;padding:8px 4px}
.sum small{display:block;color:#666;font-size:12px}
.amt{font-size:2rem;font-weight:800;text-align:center;color:var(--p);border-radius:14px}
.calc{border-radius:14px;padding:10px 12px;background:#e8f8e1;color:#1b5e20;font-weight:600}
.calc.bad{background:#fdecee;color:#b02a37}
</style>
<div class="position-sticky pt-1 pb-2" style="top:59px;z-index:20;background:#f6f5fd">
<input id="sq" class="form-control form-control-lg" type="search" placeholder="🔍 Search name, No. or mobile / തിരയുക" autocomplete="off" enterkeyhint="search">
<div class="d-flex justify-content-between align-items-center mt-1 small"><span class="text-muted"><span id="cnt"><?=count($rows)?></span> <?=$all?'contributors':'with balance'?></span>
<a href="pay.php?id=<?=$fid?>&all=<?=$all?0:1?>"><?=$all?'Only with balance':'Show all'?></a></div></div>
<div id="list"><?php foreach($rows as $r):$b=$r['amount']-$r['paid'];?>
<div class="pick" data-id="<?=$r['id']?>" data-s="<?=e(mb_strtolower($r['name']).' #'.$r['serial_no'].' '.$r['serial_no'].' '.$r['mobile'])?>" data-n="<?=e('#'.$r['serial_no'].' '.$r['name'])?>" data-i="<?=e(item_label($r))?>" data-t="<?=(float)$r['amount']?>" data-p="<?=(float)$r['paid']?>">
<span class="no">#<?=$r['serial_no']?></span><span class="flex-grow-1 min-w-0"><b><?=nm($r['name'],$b)?></b><br><small class="text-muted"><?=$r['item_name']?'<span class="itm">'.e(item_label($r)).'</span> ':''?>₹<?=money($r['amount'])?> · Paid ₹<?=money($r['paid'])?></small></span><?=bal_badge($b)?></div>
<?php endforeach;?></div>
<p id="none" class="text-muted text-center <?=$rows?'d-none':''?>">No contributor found.</p>

<div class="modal fade sheet" id="pm" tabindex="-1" aria-hidden="true"><div class="modal-dialog"><div class="modal-content"><div class="grab"></div>
<form method="post" autocomplete="off"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="cid" id="cid">
<div class="modal-header border-0 pb-0"><div><h5 class="modal-title m-0" id="pn"></h5><small class="itm" id="pi"></small></div><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
<div class="modal-body">
<div class="sum mb-3"><div><small>Total</small><b id="vt"></b></div><div><small>Paid</small><b class="text-success" id="vp"></b></div><div><small>Balance</small><b class="text-danger" id="vb"></b></div></div>
<label class="small text-muted">Payment now ₹ / ഇപ്പോൾ നൽകുന്നത്</label>
<input id="amt" class="form-control amt mb-2" type="number" step="0.01" min="1" name="amount" inputmode="decimal" placeholder="0" required>
<div class="d-flex flex-wrap gap-1 mb-3"><?php foreach([100,200,500,1000] as $v)echo '<button type="button" class="btn btn-sm btn-outline-primary rounded-pill chip" data-v="'.$v.'">+₹'.$v.'</button>';?><button type="button" class="btn btn-sm btn-outline-success rounded-pill" id="full">Full balance</button></div>
<div id="calc" class="calc d-none"></div></div>
<div class="modal-footer border-0 pt-0 d-grid gap-2">
<button class="btn btn-primary btn-lg" id="sv"><i class="bi bi-check2-circle"></i> Save payment / സേവ്</button>
<button name="next" value="1" class="btn btn-outline-primary">Save &amp; next payment</button></div>
</form></div></div></div>
<script>
window.addEventListener('load',function(){
 var m=new bootstrap.Modal(document.getElementById('pm')),a=document.getElementById('amt'),cur=null,
  fmt=function(n){return '₹'+n.toLocaleString('en-US',{maximumFractionDigits:2});};
 function calc(){var c=document.getElementById('calc'),x=parseFloat(a.value)||0;if(!cur||x<=0){c.classList.add('d-none');return;}
  var bal=cur.t-cur.p,np=cur.p+x;c.classList.remove('d-none');
  if(x>bal+0.001){c.className='calc bad';c.textContent='⚠ More than balance '+fmt(bal);}
  else{c.className='calc';c.textContent='Paid '+fmt(cur.p)+' + '+fmt(x)+' = '+fmt(np)+' · '+(bal-x>0.001?'Balance after '+fmt(bal-x):'Fully paid ✅');}}
 function open(el){document.querySelectorAll('.pick.on').forEach(function(x){x.classList.remove('on');});el.classList.add('on');
  cur={t:parseFloat(el.dataset.t),p:parseFloat(el.dataset.p)};document.getElementById('cid').value=el.dataset.id;
  document.getElementById('pn').textContent=el.dataset.n;var pi=document.getElementById('pi');pi.textContent=el.dataset.i;pi.style.display=el.dataset.i?'':'none';
  document.getElementById('vt').textContent=fmt(cur.t);document.getElementById('vp').textContent=fmt(cur.p);document.getElementById('vb').textContent=fmt(cur.t-cur.p);
  a.value='';a.max=cur.t-cur.p;calc();m.show();}
 document.querySelectorAll('.pick').forEach(function(el){el.onclick=function(){open(el);};});
 document.getElementById('pm').addEventListener('shown.bs.modal',function(){a.focus();});
 a.oninput=calc;
 document.querySelectorAll('.chip').forEach(function(b){b.onclick=function(){a.value=((parseFloat(a.value)||0)+parseFloat(b.dataset.v));calc();};});
 document.getElementById('full').onclick=function(){if(cur){a.value=Math.round((cur.t-cur.p)*100)/100;calc();}};
 var q=document.getElementById('sq');q.oninput=function(){var v=q.value.trim().toLowerCase(),n=0;
  document.querySelectorAll('.pick').forEach(function(el){var ok=!v||el.dataset.s.indexOf(v)>-1;el.style.display=ok?'':'none';if(ok)n++;});
  document.getElementById('cnt').textContent=n;document.getElementById('none').classList.toggle('d-none',n>0);};
 var s=document.querySelector('.pick[data-id="<?=$sel?>"]');if(s){s.scrollIntoView({block:'center'});open(s);}
});
</script>
<?php foot();
