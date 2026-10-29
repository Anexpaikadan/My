<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??0);$u=me();$fid=$f['id'];nav($f,$role,'home');
$q=trim($_GET['q']??'');
$items=fund_items($fid,true);$it=(int)($_GET['item']??0);
$sql='SELECT c.*,MAX(fi.name) item_name,COALESCE(SUM(p.amount),0) paid,u.name uname,u.short_name FROM contributions c'.ITEM_JOIN.'LEFT JOIN payments p ON p.contribution_id=c.id JOIN users u ON u.id=c.created_by WHERE c.fund_id=? AND c.cancelled=0';
$args=[$fid];
if($it>0){$sql.=' AND c.item_id=?';$args[]=$it;}
if($q!==''){$sql.=' AND (c.name LIKE ? OR c.serial_no=?)';$args[]="%$q%";$args[]=ctype_digit($q)?(int)$q:-1;}
$s=$pdo->prepare($sql.' GROUP BY c.id ORDER BY c.serial_no DESC');$s->execute($args);$rows=$s->fetchAll();
[$t,$p,$b]=fund_totals($fid);$mem=members($f);
$pend=0;if($role==='creator'){$x=$pdo->prepare("SELECT COUNT(*) FROM handovers WHERE fund_id=? AND status='pending'");$x->execute([$fid]);$pend=(int)$x->fetchColumn();}
$cn=$pdo->prepare('SELECT name FROM users WHERE id=?');$cn->execute([$f['creator_id']]);$cn=$cn->fetchColumn();
$share="*{$f['title']}*\n{$f['description']}\n\nCreator: $cn";
if($f['show_target']&&$f['target_amount']>0)$share.="\nTarget: ₹".money($f['target_amount']);
head($f['title']);?>
<?php if($role==='creator'):?><a class="small" href="dashboard.php">← All funds</a><?php endif;?>
<h5 class="mt-1"><?=e($f['title'])?></h5>
<p class="text-muted small mb-2"><?=nl2br(e($f['description']))?></p>
<?php if($role==='creator'):?><a class="btn btn-sm btn-success mb-3 noprint" target="_blank" href="<?=e(wa($share))?>">WhatsApp: share fund</a><?php endif;?>
<?php if($pend):?><a href="handover.php?id=<?=$fid?>" class="alert alert-warning d-block py-2 text-decoration-none">💵 <?=$pend?> transfer request(s) waiting for your approval</a><?php endif;?>
<?php if($role==='creator'):?>
<button class="btn btn-sm btn-outline-primary mb-3 noprint" data-bs-toggle="collapse" data-bs-target="#st">⚙ Settings</button>
<div id="st" class="collapse card p-3 mb-3 noprint">
<form method="post" action="settings.php"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="do" value="settings">
<label class="small text-muted">🎯 Target amount ₹ (leave 0 for none)</label>
<input class="form-control mb-2" type="number" step="0.01" min="0" name="target" value="<?=e($f['target_amount']??0)?>">
<div class="form-check form-switch mb-2"><input class="form-check-input" type="checkbox" name="show_target" id="s1" <?=$f['show_target']?'checked':''?>><label class="form-check-label" for="s1">Show target progress (creator only)</label></div>
<div class="form-check form-switch mb-3"><input class="form-check-input" type="checkbox" name="reminders" id="s2" <?=$f['reminders']?'checked':''?>><label class="form-check-label" for="s2">Balance reminders (all users)</label></div>
<button class="btn btn-primary w-100">Save settings</button></form>
<div class="d-grid gap-2 mt-2"><a class="btn btn-outline-primary" href="items.php?id=<?=$fid?>">🛍 Products (e.g. Payasam ₹500)</a><a class="btn btn-outline-success" href="import.php?id=<?=$fid?>">📥 Import entries from Excel</a></div><hr>
<form method="post" action="settings.php" onsubmit="return confirm('<?=$f['status']==='open'?'Close fund? Entries will be locked.':'Reopen fund?'?>')"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>">
<button name="do" value="<?=$f['status']==='open'?'close':'reopen'?>" class="btn btn-outline-<?=$f['status']==='open'?'danger':'success'?> w-100"><?=$f['status']==='open'?'🔒 Close fund':'🔓 Reopen fund'?></button></form></div>
<?php endif;?>
<?php if($f['status']==='closed'):?><div class="alert alert-secondary py-2">🔒 Fund closed — entries locked. Transfers and reports still work.</div><?php endif;?>
<?php if($role==='creator'&&$f['show_target']&&$f['target_amount']>0):$pc=(int)min(100,round($p/$f['target_amount']*100));?>
<div class="card p-2 mb-3"><div class="d-flex justify-content-between small"><span>🎯 Target ₹<?=money($f['target_amount'])?></span><b><?=$pc?>%</b></div>
<div class="progress" style="height:10px"><div class="progress-bar bg-success" style="width:<?=$pc?>%"></div></div>
<div class="small text-muted mt-1">Collected ₹<?=money($p)?> · Promised ₹<?=money($t)?> · To go ₹<?=money(max(0,$f['target_amount']-$p))?></div></div>
<?php endif;?>
<div class="row g-2 text-center mb-3">
<div class="col-4"><div class="card p-2"><small>Contribution</small><b>₹<?=money($t)?></b></div></div>
<div class="col-4"><div class="card p-2"><small>Paid</small><b class="text-success">₹<?=money($p)?></b></div></div>
<div class="col-4"><div class="card p-2"><small>Balance</small><b class="text-danger">₹<?=money($b)?></b></div></div></div>
<?php if($items):$is=$pdo->prepare('SELECT fi.id,fi.name,COUNT(c.id) n,COALESCE(SUM(c.qty),0) q,COALESCE(SUM(c.amount),0) amt FROM fund_items fi LEFT JOIN contributions c ON c.item_id=fi.id AND c.cancelled=0 WHERE fi.fund_id=? GROUP BY fi.id HAVING n>0 OR MAX(fi.active)=1 ORDER BY fi.id');$is->execute([$fid]);?>
<div class="card p-2 mb-3"><b class="small px-1">Products / ഇനങ്ങൾ<?php if($role==='creator'):?> · <a href="items.php?id=<?=$fid?>">manage</a><?php endif;?></b>
<div class="d-flex flex-wrap gap-2 p-1"><?php foreach($is as $x):?><a href="fund.php?id=<?=$fid?>&item=<?=$x['id']?>" class="text-decoration-none"><span class="itm"><?=e($x['name'])?> × <?=$x['q']?></span> <small class="text-muted">₹<?=money($x['amt'])?></small></a><?php endforeach;?></div></div>
<?php endif;?>
<div class="card p-2 mb-3"><b class="small px-1">Members / അംഗങ്ങൾ</b>
<div class="table-responsive"><table class="table table-sm mb-0 small"><thead><tr><th>Member</th><th class="text-end">Contribution</th><th class="text-end">Paid</th><th class="text-end">Cash on hand</th></tr></thead><tbody>
<?php foreach($mem as $m):?><tr><td><?=e($m['name'])?> <span class="text-muted">(<?=e($m['short'])?><?=$m['role']==='creator'?' · creator':''?>)</span></td><td class="text-end"><?=money($m['contrib'])?></td><td class="text-end"><?=money($m['received'])?></td><td class="text-end"><b><?=money($m['cash'])?></b></td></tr><?php endforeach;?>
</tbody></table></div></div>
<form class="d-flex gap-1 mb-2 noprint"><input type="hidden" name="id" value="<?=$fid?>"><input class="form-control" name="q" value="<?=e($q)?>" placeholder="Search name or number / തിരയുക">
<?php if($items):?><select class="form-select" name="item" style="max-width:40%"><option value="0">All</option><?php foreach($items as $x):?><option value="<?=$x['id']?>" <?=$it==$x['id']?'selected':''?>><?=e($x['name'])?></option><?php endforeach;?></select><?php endif;?><button class="btn btn-outline-primary">🔍</button></form>
<?php foreach($rows as $r):$bal=$r['amount']-$r['paid'];?>
<a href="contribution.php?id=<?=$r['id']?>" class="card p-2 mb-1 text-decoration-none text-dark">
<div class="d-flex justify-content-between"><span><b>#<?=$r['serial_no']?></b> <?=e($r['name'])?></span>
<span><?=bal_badge($bal)?></span></div>
<small class="text-muted"><?php if($r['item_name']):?><span class="itm"><?=e(item_label($r))?></span> <?php endif;?>₹<?=money($r['amount'])?> · Paid ₹<?=money($r['paid'])?> · <?=e(sn($r['uname'],$r['short_name']))?></small></a>
<?php endforeach; if(!$rows)echo '<p class="text-muted">No contributions found.</p>';
foot();
