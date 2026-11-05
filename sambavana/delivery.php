<?php require 'config.php';
// Product delivery: for each product entry, mark whether the contributor took it or it was sent to them
[$f,$role]=fund_access($_GET['id']??$_POST['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'home');
$tab=in_array($_GET['t']??'',['no','taken','sent'],true)?$_GET['t']:'no';
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $v=$_POST['v']??'';$v=isset(DELIVERY[$v])?$v:null;$t=in_array($_POST['t']??'',['no','taken','sent'],true)?$_POST['t']:'no';
 $s=$pdo->prepare('SELECT serial_no,name FROM contributions WHERE id=? AND fund_id=? AND item_id IS NOT NULL AND cancelled=0');$s->execute([(int)($_POST['cid']??0),$fid]);$c=$s->fetch();
 if(!$c)flash('Entry not found','danger');
 else{$pdo->prepare('UPDATE contributions SET delivery=?,delivered_at='.($v?'NOW()':'NULL').' WHERE id=?')->execute([$v,(int)$_POST['cid']]);
  flash('#'.$c['serial_no'].' '.$c['name'].': '.($v?DELIVERY[$v][0].' '.DELIVERY[$v][1]:'↩ marked not given'));}
 redirect("delivery.php?id=$fid&t=$t");
}
$cnt=['no'=>0,'taken'=>0,'sent'=>0];
$x=$pdo->prepare("SELECT COALESCE(delivery,'no') d,COUNT(*) n,COALESCE(SUM(qty),0) q FROM contributions WHERE fund_id=? AND cancelled=0 AND item_id IS NOT NULL GROUP BY d");$x->execute([$fid]);$qty=[];
foreach($x as $r){$cnt[$r['d']]=(int)$r['n'];$qty[$r['d']]=(int)$r['q'];}
$s=$pdo->prepare('SELECT c.*,fi.name item_name,(SELECT COALESCE(SUM(amount),0) FROM payments p WHERE p.contribution_id=c.id) paid FROM contributions c JOIN fund_items fi ON fi.id=c.item_id WHERE c.fund_id=? AND c.cancelled=0 AND '.($tab==='no'?'c.delivery IS NULL':'c.delivery=?').' ORDER BY '.($tab==='no'?'c.serial_no':'c.delivered_at DESC'));
$s->execute($tab==='no'?[$fid]:[$fid,$tab]);$rows=$s->fetchAll();
head('Delivery');?>
<style>
.seg{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;background:#e9eaee;border-radius:14px;padding:4px}
.seg a{text-align:center;border-radius:11px;padding:7px 2px;text-decoration:none;color:#444;font-weight:600;font-size:13px;line-height:1.25}
.seg a.on{background:#fff;color:var(--p);box-shadow:0 1px 3px rgba(0,0,0,.1)}
.seg a b{display:block;font-size:1.15rem}
.dv{background:#fff;border-radius:16px;padding:10px 12px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.dv .acts{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
.dv .acts .btn{padding:10px 4px}
</style>
<div class="seg mb-2 noprint">
<?php foreach(['no'=>'⏳ Not given','taken'=>'🤲 Taken','sent'=>'🚚 Sent'] as $k=>$v):?><a class="<?=$tab===$k?'on':''?>" href="delivery.php?id=<?=$fid?>&t=<?=$k?>"><b><?=$cnt[$k]?></b><?=$v?></a><?php endforeach;?>
</div>
<p class="small text-muted mb-2 px-1">Qty — not given <b><?=$qty['no']??0?></b> · taken <b><?=$qty['taken']??0?></b> · sent <b><?=$qty['sent']??0?></b></p>
<?php if($rows):?><input id="dq" class="form-control mb-2" type="search" placeholder="🔍 Search name or No. / തിരയുക" autocomplete="off"><?php endif;?>
<?php foreach($rows as $r):$bal=$r['amount']-$r['paid'];?>
<div class="dv" data-s="<?=e(mb_strtolower($r['name']).' '.$r['serial_no'].' '.$r['mobile'])?>">
<div class="d-flex justify-content-between gap-2"><a class="text-decoration-none" href="contribution.php?id=<?=$r['id']?>"><b>#<?=$r['serial_no']?></b> <?=nm($r['name'],$bal)?></a><?=bal_badge($bal)?></div>
<div class="small"><span class="itm" style="font-size:1rem"><?=e(item_label($r))?></span><?php if($r['delivered_at']):?> <span class="text-muted"><?=date('d M, g:i a',strtotime($r['delivered_at']))?></span><?php endif;?></div>
<form method="post" class="acts noprint"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="cid" value="<?=$r['id']?>"><input type="hidden" name="t" value="<?=$tab?>">
<?php if($tab==='no'):?><button name="v" value="taken" class="btn btn-primary">🤲 Taken / വാങ്ങി</button><button name="v" value="sent" class="btn btn-outline-primary">🚚 Sent / എത്തിച്ചു</button>
<?php else:?><button name="v" value="<?=$tab==='taken'?'sent':'taken'?>" class="btn btn-outline-primary"><?=$tab==='taken'?'🚚 Change to Sent':'🤲 Change to Taken'?></button><button name="v" value="" class="btn btn-outline-secondary">↩ Not given</button><?php endif;?>
</form></div>
<?php endforeach;if(!$rows)echo '<p class="text-muted text-center my-4">'.($tab==='no'?'Everything is given 🎉':'Nothing here yet.').'</p>';?>
<p id="none" class="text-muted text-center d-none">No match.</p>
<script>
var dq=document.getElementById('dq');if(dq)dq.oninput=function(){var v=dq.value.trim().toLowerCase(),n=0;document.querySelectorAll('.dv').forEach(function(el){var ok=!v||el.dataset.s.indexOf(v)>-1;el.style.display=ok?'':'none';if(ok)n++;});document.getElementById('none').classList.toggle('d-none',n>0);};
</script>
<?php foot();
