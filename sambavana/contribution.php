<?php require 'config.php';$u=require_login(['user','collector']);
$s=$pdo->prepare('SELECT c.*,fi.name item_name FROM contributions c'.ITEM_JOIN.'WHERE c.id=?');$s->execute([(int)($_GET['id']??0)]);$c=$s->fetch();
if(!$c){http_response_code(404);die('Not found');}
[$f,$role]=fund_access($c['fund_id']);nav($f,$role,'home');if($c['cancelled']){die('This entry was cancelled');}
$paid=function()use($pdo,$c){$q=$pdo->prepare('SELECT COALESCE(SUM(amount),0) FROM payments WHERE contribution_id=?');$q->execute([$c['id']]);return (float)$q->fetchColumn();};
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 if($f['status']==='closed'){flash('Fund is closed','danger');redirect('contribution.php?id='.$c['id']);}
 $a=(float)$_POST['amount'];$bal=$c['amount']-$paid();
 if($a<=0||$a>$bal)flash('Amount must be between 0 and balance ₹'.money($bal),'danger');
 else{$pdo->prepare('INSERT INTO payments(contribution_id,amount,received_by) VALUES(?,?,?)')->execute([$c['id'],$a,$u['id']]);flash('Payment added');}
 redirect('contribution.php?id='.$c['id']);
}
$pay=$pdo->prepare('SELECT p.*,u.name,u.short_name FROM payments p JOIN users u ON u.id=p.received_by WHERE contribution_id=? ORDER BY p.id');$pay->execute([$c['id']]);$pays=$pay->fetchAll();
$paidAmt=$paid();$bal=$c['amount']-$paidAmt;
$head="*{$f['title']}*\nReceipt #{$c['serial_no']}\nName: {$c['name']}\n".($c['item_name']?"Item: ".item_label($c)." (₹".money($c['amount']/$c['qty'])." each)\n":'');
$only=$head."Contribution: ₹".money($c['amount'])."\nThank you 🙏";
$full=$head."Total: ₹".money($c['amount'])."\nPaid: ₹".money($paidAmt)."\nBalance: ₹".money($bal).($bal<=0?' ✅':' ⏳')."\n";
if($pays){$full.="\nPayments:\n";foreach($pays as $i=>$p)$full.=($i+1).") ".date('d-m-Y',strtotime($p['created_at']))." – ₹".money($p['amount'])."\n";}
$full.="\nThank you 🙏";
head('Contribution #'.$c['serial_no']);?>
<div class="card p-3 my-2"><h5>#<?=$c['serial_no']?> <?=nm($c['name'],$bal)?></h5>
<?php if($c['item_name']):?><div class="mb-1"><span class="itm"><?=e(item_label($c))?></span> <small class="text-muted">₹<?=money($c['amount']/$c['qty'])?> each</small></div><?php endif;?>
<div>Total: <b>₹<?=money($c['amount'])?></b></div>
<div>Paid: <b class="text-success">₹<?=money($paidAmt)?></b></div>
<div>Balance: <?=bal_badge($bal)?></div></div>
<div class="card p-3 mb-2 noprint"><b class="small mb-2">Share on WhatsApp / ഷെയർ</b>
<div class="d-grid gap-2"><a class="btn btn-success" target="_blank" href="<?=e(wa($full,$c['mobile']))?>">With details (total, paid, balance, payments)</a>
<a class="btn btn-outline-primary" target="_blank" href="<?=e(wa($only,$c['mobile']))?>">Contribution only</a></div></div>
<?php if($bal>0&&$f['status']==='open'):?><div class="card p-3 mb-2 noprint"><form method="post" class="d-flex gap-2"><?=csrf_field()?>
<input class="form-control" type="number" step="0.01" min="1" max="<?=$bal?>" name="amount" placeholder="Payment ₹ / പണം" required>
<button class="btn btn-primary">Add</button></form></div><?php endif;?>
<?php if($role==='creator'&&$f['status']==='open'):?><a class="btn btn-sm btn-outline-primary mb-3 noprint" href="edit.php?id=<?=$c['id']?>">✏ Edit / Cancel entry</a><?php endif;?>
<h6>Payment history</h6>
<?php foreach($pays as $p):?><div class="card p-2 mb-1 small">₹<?=money($p['amount'])?> · <?=e($p['created_at'])?> · received by <?=e(sn($p['name'],$p['short_name']))?></div><?php endforeach;
if(!$pays)echo '<p class="text-muted small">No payments yet.</p>';
foot();
