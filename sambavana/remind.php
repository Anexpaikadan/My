<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??0);$fid=$f['id'];nav($f,$role,'remind');
head('Pending balances');
if(!$f['reminders']){echo '<div class="alert alert-secondary">Balance reminders are off. Creator can turn them on in Settings.</div>';foot();exit;}
$s=$pdo->prepare('SELECT c.*,COALESCE(SUM(p.amount),0) paid FROM contributions c LEFT JOIN payments p ON p.contribution_id=c.id WHERE c.fund_id=? AND c.cancelled=0 GROUP BY c.id HAVING c.amount>paid ORDER BY c.serial_no');
$s->execute([$fid]);$rows=$s->fetchAll();$tot=0;$list="*{$f['title']}* – Pending balances\n\n";
foreach($rows as $r){$b=$r['amount']-$r['paid'];$tot+=$b;$list.="#{$r['serial_no']} {$r['name']} – ₹".money($b)."\n";}
$list.="\nTotal pending: ₹".money($tot);?>
<h5>🔔 Pending balances / ബാക്കി</h5>
<?php if($rows):?><div class="d-flex justify-content-between align-items-center mb-2"><b class="text-danger">₹<?=money($tot)?> (<?=count($rows)?>)</b>
<a class="btn btn-sm btn-success" target="_blank" href="<?=e(wa($list))?>">Share full list</a></div>
<?php foreach($rows as $r):$b=$r['amount']-$r['paid'];
$m="Hello {$r['name']}, a gentle reminder for *{$f['title']}*.\nContribution: ₹".money($r['amount'])."\nPaid: ₹".money($r['paid'])."\nBalance: ₹".money($b)."\nKindly pay the balance. Thank you 🙏";?>
<div class="card p-2 mb-1 d-flex flex-row justify-content-between align-items-center"><span><b>#<?=$r['serial_no']?></b> <?=e($r['name'])?><br><small class="text-muted">Total ₹<?=money($r['amount'])?> · Paid ₹<?=money($r['paid'])?> · <?=$r['mobile']?e($r['mobile']):'no mobile'?></small></span>
<span class="text-end"><b class="text-danger">₹<?=money($b)?></b><br><a class="btn btn-sm btn-success mt-1" target="_blank" href="<?=e(wa($m,$r['mobile']))?>">Remind</a></span></div>
<?php endforeach;else:echo '<p class="text-muted">No pending balances 🎉</p>';endif;
foot();
