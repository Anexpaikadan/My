<?php require __DIR__.'/inc/config.php';
// Fund dashboard: totals, option buttons, search contributors (tap one to open it and add a payment)
[$f,$role]=fund_access($_GET['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'home');
$q=trim($_GET['q']??'');
$items=fund_items($fid,true);$it=(int)($_GET['item']??0);
$dv=$_GET['dv']??'';
$sql='SELECT c.*,MAX(fi.name) item_name,COALESCE(SUM(p.amount),0) paid,u.name uname,u.short_name FROM contributions c'.ITEM_JOIN.'LEFT JOIN payments p ON p.contribution_id=c.id JOIN users u ON u.id=c.created_by WHERE c.fund_id=? AND c.cancelled=0';
$args=[$fid];
if($it>0){$sql.=' AND c.item_id=?';$args[]=$it;}
if($dv==='no')$sql.=' AND c.item_id IS NOT NULL AND c.delivery IS NULL';elseif($dv==='taken')$sql.=' AND c.delivery IS NOT NULL';
if($q!==''){$sql.=' AND (c.name LIKE ? OR c.serial_no=? OR c.mobile LIKE ?)';$args[]="%$q%";$args[]=ctype_digit($q)?(int)$q:-1;$args[]=ctype_digit($q)&&strlen($q)>=4?"%$q%":'-';}
$s=$pdo->prepare($sql.' GROUP BY c.id ORDER BY c.serial_no DESC');$s->execute($args);$rows=$s->fetchAll();
[$t,$p,$b]=fund_totals($fid);
$pend=0;if($role==='creator'){$x=$pdo->prepare("SELECT COUNT(*) FROM handovers WHERE fund_id=? AND status='pending'");$x->execute([$fid]);$pend=(int)$x->fetchColumn();}
$open=$f['status']==='open';
// option buttons: [icon, label, malayalam, link, style]
$opt=[];
if($open){$opt[]=['bi-plus-circle-fill','New contribution','പുതിയ സംഭാവന',"entry.php?id=$fid",'main'];$opt[]=['bi-cash-coin','Add payment','പണം സ്വീകരിക്കുക',"pay.php?id=$fid",'main pay'];}
$opt[]=['bi-search','Search contributor','തിരയുക','#search','js'];
if($items){$dq=$pdo->prepare('SELECT COUNT(*) FROM contributions WHERE fund_id=? AND cancelled=0 AND item_id IS NOT NULL AND delivery IS NULL');$dq->execute([$fid]);$dn=(int)$dq->fetchColumn();
 $opt[]=['bi-box-seam','Product given'.($dn?" ($dn)":''),'വാങ്ങി',"delivery.php?id=$fid",''];}
if($f['reminders'])$opt[]=['bi-bell','Pending','ബാക്കി',"remind.php?id=$fid",''];
$opt[]=[$role==='creator'?'bi-bar-chart-line':'bi-share',$role==='creator'?'Report':'Share','റിപ്പോർട്ട്',"reports.php?id=$fid",''];
$opt[]=['bi-arrow-left-right','Transfer','കൈമാറ്റം',"handover.php?id=$fid",''];
if($role==='creator'){
 $opt[]=['bi-people','Collectors','കളക്ടർമാർ',"collectors.php?id=$fid",''];
 $opt[]=['bi-bag','Products','ഇനങ്ങൾ',"items.php?id=$fid",''];
 $opt[]=['bi-gear','Settings','ക്രമീകരണം',"settings.php?id=$fid",''];
}
head($f['title']);?>
<style>
.hero{border-radius:20px;padding:16px;background:linear-gradient(135deg,var(--p),var(--p2));color:#fff;box-shadow:0 8px 20px rgba(var(--prgb),.25)}
.hero small{color:#ffffffcc}.hero .big{font-size:1.9rem;font-weight:800;line-height:1.15}
.hero .progress{height:7px;background:#ffffff40}.hero .progress-bar{background:#fff!important}
.hero .row2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.hero .row2 div{background:#ffffff26;border-radius:12px;padding:6px 10px}.hero .row2 b{display:block;font-size:1.1rem}
.tiles{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.tile{grid-column:span 2;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:96px;padding:10px 4px;border-radius:18px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.07);color:#222;text-decoration:none;text-align:center;font-size:13px;font-weight:600;line-height:1.25}
.tile i{font-size:26px;color:var(--p);width:46px;height:46px;border-radius:14px;background:var(--pl);display:flex;align-items:center;justify-content:center}
.tile small{font-weight:400;color:#5f6670;font-size:12px}
.tile.main{grid-column:span 3;min-height:108px;background:var(--p);color:#fff;font-size:15px}
.tile.main.pay{background:#fff;color:var(--pd);box-shadow:inset 0 0 0 2px var(--p)}
.tile.main.pay i{background:var(--pl);color:var(--p)}.tile.main.pay small{color:var(--pd)}
.tile.main i{background:#ffffff26;color:#fff}.tile.main small{color:#ffffffcc;font-size:12px}
#search{scroll-margin-top:70px}
</style>
<?php if($pend):?><a href="handover.php?id=<?=$fid?>" class="alert alert-warning d-block py-2 text-decoration-none"><i class="bi bi-cash-coin" aria-hidden="true"></i> <?=$pend?> transfer request(s) waiting for your approval</a><?php endif;?>
<?php if(!$open):?><div class="alert alert-secondary py-2"><i class="bi bi-lock-fill" aria-hidden="true"></i> Fund closed — entries locked. Transfers and reports still work.</div><?php endif;?>
<?php $pa=$t>0?(int)min(100,round($p/$t*100)):0;?><div class="hero mb-3">
<small>Total contribution / ആകെ സംഭാവന</small><div class="big">₹<?=money($t)?></div>
<div class="progress mt-2"><div class="progress-bar" style="width:<?=$pa?>%"></div></div>
<div class="row2"><div><small>Paid / ലഭിച്ചത്</small><b>₹<?=money($p)?></b></div><div><small>Balance / ബാക്കി</small><b>₹<?=money($b)?></b></div></div></div>
<?php if($role==='creator'&&$f['show_target']&&$f['target_amount']>0):$pc=(int)min(100,round($p/$f['target_amount']*100));?>
<div class="card p-2 mb-3"><div class="d-flex justify-content-between small"><span><i class="bi bi-bullseye" aria-hidden="true"></i> Target ₹<?=money($f['target_amount'])?></span><b><?=$pc?>%</b></div>
<div class="progress" style="height:10px"><div class="progress-bar bg-success" style="width:<?=$pc?>%"></div></div>
<div class="small text-muted mt-1">To go ₹<?=money(max(0,$f['target_amount']-$p))?></div></div>
<?php endif;?>
<div class="tiles mb-3 noprint">
<?php foreach($opt as $o):?><a class="tile <?=$o[4]!=='js'?$o[4]:''?>" href="<?=$o[3]?>"<?=$o[4]==='js'?' data-search':''?>><i class="bi <?=$o[0]?>"></i><span><?=$o[1]?><br><small><?=$o[2]?></small></span></a><?php endforeach;?>
</div>
<div id="search" class="card p-2 mb-2"><form class="noprint"><input type="hidden" name="id" value="<?=$fid?>">
<div class="d-flex gap-1"><input id="sq" class="form-control form-control-lg flex-grow-1" style="min-width:0" name="q" value="<?=e($q)?>" type="search" placeholder="Search / തിരയുക" aria-label="Search contributors" enterkeyhint="search">
<button class="btn btn-primary px-3" aria-label="Search"><i class="bi bi-search"></i></button></div>
<?php if($items):?><div class="d-flex gap-1 mt-1"><select class="form-select" name="item" aria-label="Product" onchange="this.form.submit()"><option value="0">All</option><?php foreach($items as $x):?><option value="<?=$x['id']?>" <?=$it==$x['id']?'selected':''?>><?=e($x['name'])?></option><?php endforeach;?></select><select class="form-select" name="dv" aria-label="Product taken" onchange="this.form.submit()"><option value="">വാങ്ങി?</option><?php foreach(['no'=>'വാങ്ങിയില്ല','taken'=>'വാങ്ങി'] as $k=>$v):?><option value="<?=$k?>" <?=$dv===$k?'selected':''?>><?=$v?></option><?php endforeach;?></select></div><?php endif;?></form>
<small class="text-muted px-1 pt-1"><?=count($rows)?> contributor<?=count($rows)==1?'':'s'?><?=$q!==''||$it||$dv?' found · <a href="fund.php?id='.$fid.'#search">show all</a>':''?> · tap a name to open it and add payment</small></div>
<?php foreach($rows as $r):$bal=$r['amount']-$r['paid'];?>
<a href="contribution.php?id=<?=$r['id']?>" class="card p-2 mb-1 text-decoration-none text-dark">
<div class="d-flex justify-content-between"><span><b>#<?=$r['serial_no']?></b> <?=nm($r['name'],$bal)?></span>
<span><?=bal_badge($bal)?></span></div>
<small class="text-muted"><?php if($r['item_name']):?><span class="itm"><?=e(item_label($r))?></span> <?=dl_badge($r)?> <?php endif;?>₹<?=money($r['amount'])?> · Paid ₹<?=money($r['paid'])?> · <?=e(sn($r['uname'],$r['short_name']))?></small></a>
<?php endforeach; if(!$rows)echo '<p class="text-muted">No contributions found.</p>';?>
<script>
document.querySelectorAll('[data-search]').forEach(function(a){a.onclick=function(e){e.preventDefault();var s=document.getElementById('search');s.scrollIntoView({behavior:'smooth'});setTimeout(function(){document.getElementById('sq').focus();},350);};});
<?php if($q!==''||$it||$dv):?>document.getElementById('search').scrollIntoView();<?php endif;?>
</script>
<?php foot();
