<?php require 'config.php';
// Fund dashboard: totals, option buttons, search contributors (tap one to open it and add a payment)
[$f,$role]=fund_access($_GET['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'home');
$q=trim($_GET['q']??'');
$items=fund_items($fid,true);$it=(int)($_GET['item']??0);
$sql='SELECT c.*,MAX(fi.name) item_name,COALESCE(SUM(p.amount),0) paid,u.name uname,u.short_name FROM contributions c'.ITEM_JOIN.'LEFT JOIN payments p ON p.contribution_id=c.id JOIN users u ON u.id=c.created_by WHERE c.fund_id=? AND c.cancelled=0';
$args=[$fid];
if($it>0){$sql.=' AND c.item_id=?';$args[]=$it;}
if($q!==''){$sql.=' AND (c.name LIKE ? OR c.serial_no=? OR c.mobile LIKE ?)';$args[]="%$q%";$args[]=ctype_digit($q)?(int)$q:-1;$args[]=ctype_digit($q)&&strlen($q)>=4?"%$q%":'-';}
$s=$pdo->prepare($sql.' GROUP BY c.id ORDER BY c.serial_no DESC');$s->execute($args);$rows=$s->fetchAll();
[$t,$p,$b]=fund_totals($fid);
$pend=0;if($role==='creator'){$x=$pdo->prepare("SELECT COUNT(*) FROM handovers WHERE fund_id=? AND status='pending'");$x->execute([$fid]);$pend=(int)$x->fetchColumn();}
$open=$f['status']==='open';
// option buttons: [icon, label, malayalam, link, style]
$opt=[];
if($open)$opt[]=['bi-plus-circle-fill','New contribution','പുതിയ സംഭാവന',"entry.php?id=$fid",'main'];
$opt[]=['bi-search','Search contributor','തിരയുക','#search','js'];
if($f['reminders'])$opt[]=['bi-bell','Pending','ബാക്കി',"remind.php?id=$fid",''];
$opt[]=[$role==='creator'?'bi-bar-chart-line':'bi-share',$role==='creator'?'Report':'Share','റിപ്പോർട്ട്',"reports.php?id=$fid",''];
$opt[]=['bi-cash-coin','Transfer','കൈമാറ്റം',"handover.php?id=$fid",''];
if($role==='creator'){
 $opt[]=['bi-people','Collectors','കളക്ടർമാർ',"collectors.php?id=$fid",''];
 $opt[]=['bi-bag','Products','ഇനങ്ങൾ',"items.php?id=$fid",''];
 if($open)$opt[]=['bi-file-earmark-excel','Import Excel','എക്സൽ',"import.php?id=$fid",''];
 $opt[]=['bi-gear','Settings','ക്രമീകരണം',"settings.php?id=$fid",''];
}
head($f['title']);?>
<style>
.st{border-radius:16px;padding:12px 6px;text-align:center;background:#fff;box-shadow:0 1px 4px #3513d614}
.st small{display:block;color:#666}
.st b{font-size:1.15rem}
.st.c{background:linear-gradient(135deg,#3513d6,#6a3df0);color:#fff}.st.c small{color:#ffffffcc}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.tile{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:96px;padding:10px 4px;border-radius:16px;background:#fff;box-shadow:0 1px 4px #3513d614;color:#222;text-decoration:none;text-align:center;font-size:13px;font-weight:600;line-height:1.25}
.tile i{font-size:26px;color:var(--p);width:46px;height:46px;border-radius:14px;background:#ece8ff;display:flex;align-items:center;justify-content:center}
.tile small{font-weight:400;color:#777;font-size:11px}
.tile.main{grid-column:span 3;flex-direction:row;min-height:64px;background:var(--p);color:#fff;font-size:16px;gap:12px}
.tile.main i{background:#ffffff26;color:#fff}.tile.main small{color:#ffffffcc;font-size:12px}
#search{scroll-margin-top:70px}
</style>
<?php if($pend):?><a href="handover.php?id=<?=$fid?>" class="alert alert-warning d-block py-2 text-decoration-none">💵 <?=$pend?> transfer request(s) waiting for your approval</a><?php endif;?>
<?php if(!$open):?><div class="alert alert-secondary py-2">🔒 Fund closed — entries locked. Transfers and reports still work.</div><?php endif;?>
<div class="row g-2 mb-3">
<div class="col-4"><div class="st c"><small>Contribution</small><b>₹<?=money($t)?></b></div></div>
<div class="col-4"><div class="st"><small>Paid</small><b class="text-success">₹<?=money($p)?></b></div></div>
<div class="col-4"><div class="st"><small>Balance</small><b class="text-danger">₹<?=money($b)?></b></div></div></div>
<?php if($role==='creator'&&$f['show_target']&&$f['target_amount']>0):$pc=(int)min(100,round($p/$f['target_amount']*100));?>
<div class="card p-2 mb-3"><div class="d-flex justify-content-between small"><span>🎯 Target ₹<?=money($f['target_amount'])?></span><b><?=$pc?>%</b></div>
<div class="progress" style="height:10px"><div class="progress-bar bg-success" style="width:<?=$pc?>%"></div></div>
<div class="small text-muted mt-1">To go ₹<?=money(max(0,$f['target_amount']-$p))?></div></div>
<?php endif;?>
<div class="tiles mb-3 noprint">
<?php foreach($opt as $o):?><a class="tile <?=$o[4]==='main'?'main':''?>" href="<?=$o[3]?>"<?=$o[4]==='js'?' data-search':''?>><i class="bi <?=$o[0]?>"></i><span><?=$o[1]?><br><small><?=$o[2]?></small></span></a><?php endforeach;?>
</div>
<div id="search" class="card p-2 mb-2"><form class="d-flex gap-1 noprint"><input type="hidden" name="id" value="<?=$fid?>">
<input id="sq" class="form-control" name="q" value="<?=e($q)?>" type="search" placeholder="Name, No. or mobile / തിരയുക" enterkeyhint="search">
<?php if($items):?><select class="form-select" name="item" style="max-width:34%" onchange="this.form.submit()"><option value="0">All</option><?php foreach($items as $x):?><option value="<?=$x['id']?>" <?=$it==$x['id']?'selected':''?>><?=e($x['name'])?></option><?php endforeach;?></select><?php endif;?>
<button class="btn btn-primary" aria-label="Search"><i class="bi bi-search"></i></button></form>
<small class="text-muted px-1 pt-1"><?=count($rows)?> contributor<?=count($rows)==1?'':'s'?><?=$q!==''||$it?' found · <a href="fund.php?id='.$fid.'#search">show all</a>':''?> · tap a name to open it and add payment</small></div>
<?php foreach($rows as $r):$bal=$r['amount']-$r['paid'];?>
<a href="contribution.php?id=<?=$r['id']?>" class="card p-2 mb-1 text-decoration-none text-dark">
<div class="d-flex justify-content-between"><span><b>#<?=$r['serial_no']?></b> <?=nm($r['name'],$bal)?></span>
<span><?=bal_badge($bal)?></span></div>
<small class="text-muted"><?php if($r['item_name']):?><span class="itm"><?=e(item_label($r))?></span> <?php endif;?>₹<?=money($r['amount'])?> · Paid ₹<?=money($r['paid'])?> · <?=e(sn($r['uname'],$r['short_name']))?></small></a>
<?php endforeach; if(!$rows)echo '<p class="text-muted">No contributions found.</p>';?>
<script>
document.querySelectorAll('[data-search]').forEach(function(a){a.onclick=function(e){e.preventDefault();var s=document.getElementById('search');s.scrollIntoView({behavior:'smooth'});setTimeout(function(){document.getElementById('sq').focus();},350);};});
<?php if($q!==''||$it):?>document.getElementById('search').scrollIntoView();<?php endif;?>
</script>
<?php foot();
