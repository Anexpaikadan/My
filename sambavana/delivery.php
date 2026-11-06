<?php require __DIR__.'/inc/config.php';
// Product given: mark each product entry വാങ്ങി (taken) with one tap
[$f,$role]=fund_access($_GET['id']??$_POST['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'home');
$tab=($_GET['t']??'')==='taken'?'taken':'no';
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $v=($_POST['v']??'')==='taken'?'taken':null;$t=($_POST['t']??'')==='taken'?'taken':'no';
 $s=$pdo->prepare('SELECT serial_no,name FROM contributions WHERE id=? AND fund_id=? AND item_id IS NOT NULL AND cancelled=0');$s->execute([(int)($_POST['cid']??0),$fid]);$c=$s->fetch();
 if(!$c)flash('Entry not found','danger');
 else{$pdo->prepare('UPDATE contributions SET delivery=?,delivered_at='.($v?'NOW()':'NULL').' WHERE id=?')->execute([$v,(int)$_POST['cid']]);
  flash('#'.$c['serial_no'].' '.$c['name'].': '.($v?'✔ വാങ്ങി':'↩ വാങ്ങിയില്ല'));}
 redirect("delivery.php?id=$fid&t=$t");
}
$cnt=['no'=>0,'taken'=>0];$qty=['no'=>0,'taken'=>0];
$x=$pdo->prepare("SELECT IF(delivery IS NULL,'no','taken') d,COUNT(*) n,COALESCE(SUM(qty),0) q FROM contributions WHERE fund_id=? AND cancelled=0 AND item_id IS NOT NULL GROUP BY d");$x->execute([$fid]);
foreach($x as $r){$cnt[$r['d']]=(int)$r['n'];$qty[$r['d']]=(int)$r['q'];}
$s=$pdo->prepare('SELECT c.*,fi.name item_name,(SELECT COALESCE(SUM(amount),0) FROM payments p WHERE p.contribution_id=c.id) paid FROM contributions c JOIN fund_items fi ON fi.id=c.item_id WHERE c.fund_id=? AND c.cancelled=0 AND c.delivery IS '.($tab==='no'?'NULL':'NOT NULL').' ORDER BY '.($tab==='no'?'c.serial_no':'c.delivered_at DESC'));
$s->execute([$fid]);$rows=$s->fetchAll();
head('Product given');?>
<style>
.seg{display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#e9eaee;border-radius:14px;padding:4px}
.seg a{text-align:center;border-radius:11px;padding:7px 2px;text-decoration:none;color:#444;font-weight:600;font-size:14px;line-height:1.25}
.seg a.on{background:#fff;color:var(--p);box-shadow:0 1px 3px rgba(0,0,0,.1)}
.seg a b{display:block;font-size:1.2rem}
.dv{background:#fff;border-radius:16px;padding:10px 12px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,.07);display:flex;align-items:center;gap:10px}
.dv .btn{flex:none;padding:10px 14px}
</style>
<div class="seg mb-2 noprint">
<a class="<?=$tab==='no'?'on':''?>" href="delivery.php?id=<?=$fid?>&t=no"><b><?=$cnt['no']?></b><i class="bi bi-hourglass-split" aria-hidden="true"></i> വാങ്ങിയില്ല</a>
<a class="<?=$tab==='taken'?'on':''?>" href="delivery.php?id=<?=$fid?>&t=taken"><b><?=$cnt['taken']?></b><i class="bi bi-check2-circle" aria-hidden="true"></i> വാങ്ങി</a>
</div>
<p class="small text-muted mb-2 px-1">Qty — വാങ്ങിയില്ല <b><?=$qty['no']?></b> · വാങ്ങി <b><?=$qty['taken']?></b></p>
<?php if($rows):?><input id="dq" class="form-control mb-2" type="search" placeholder="Search name or No. / തിരയുക" aria-label="Search" autocomplete="off"><?php endif;?>
<?php foreach($rows as $r):$bal=$r['amount']-$r['paid'];?>
<div class="dv" data-s="<?=e(mb_strtolower($r['name']).' '.$r['serial_no'].' '.$r['mobile'])?>">
<a class="flex-grow-1 min-w-0 text-decoration-none text-dark" href="contribution.php?id=<?=$r['id']?>"><b>#<?=$r['serial_no']?></b> <?=nm($r['name'],$bal,$r['amount'])?><br>
<span class="itm"><?=e(item_label($r))?></span> <?=bal_badge($bal)?><?php if($r['delivered_at']):?><br><small class="text-muted"><?=date('d M, g:i a',strtotime($r['delivered_at']))?></small><?php endif;?></a>
<form method="post" class="noprint"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="cid" value="<?=$r['id']?>"><input type="hidden" name="t" value="<?=$tab?>">
<?php if($tab==='no'):?><button name="v" value="taken" class="btn btn-primary"><i class="bi bi-check2-circle" aria-hidden="true"></i> വാങ്ങി</button><?php else:?><button name="v" value="" class="btn btn-outline-secondary btn-sm"><i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i> Undo</button><?php endif;?>
</form></div>
<?php endforeach;if(!$rows)echo '<p class="text-muted text-center my-4">'.($tab==='no'?'Everyone has taken it':'Nothing here yet.').'</p>';?>
<p id="none" class="text-muted text-center d-none">No match.</p>
<script>
var dq=document.getElementById('dq');if(dq)dq.oninput=function(){var v=dq.value.trim().toLowerCase(),n=0;document.querySelectorAll('.dv').forEach(function(el){var ok=!v||el.dataset.s.indexOf(v)>-1;el.style.display=ok?'':'none';if(ok)n++;});document.getElementById('none').classList.toggle('d-none',n>0);};
</script>
<?php foot();
