<?php require 'config.php';
[$f,$role]=fund_access($_GET['id']??0);$fid=$f['id'];$r=(int)($_GET['r']??1);
nav($f,$role,'reports');$mem=members($f);$d=($_GET['d']??'1')==='1';$R=['title'=>'','lines'=>[],'head'=>[],'rows'=>[],'foot'=>[]];
$cr=$pdo->prepare('SELECT name,username FROM users WHERE id=?');$cr->execute([$f['creator_id']]);$cr=$cr->fetch();
$msel=(int)($_GET['m']??$mem[0]['id']);$xls=isset($_GET['xls']);
$hasItems=(bool)fund_items($fid,true);

if($r===1){ // Fund report
 $R['title']='Fund Report: '.$f['title'];
 $R['lines']=['Type: '.$f['type'],'Start: '.$f['start_date'],'Description: '.$f['description'],'Creator: '.$cr['name'].' ('.$cr['username'].')','Creator details: '.$f['creator_details']];
 $R['head']=['Collector','Short'];
 foreach($mem as $m)if($m['role']==='collector')$R['rows'][]=[$m['name'],$m['short']];
}elseif($r===2){ // Contribution list
 $R['title']='Contribution List: '.$f['title'];
 $s=$pdo->prepare('SELECT c.*,MAX(fi.name) item_name,COALESCE(SUM(p.amount),0) paid,u.name uname,u.short_name FROM contributions c'.ITEM_JOIN.'LEFT JOIN payments p ON p.contribution_id=c.id JOIN users u ON u.id=c.created_by WHERE c.fund_id=? AND c.cancelled=0 GROUP BY c.id ORDER BY c.serial_no');$s->execute([$fid]);
 if($xls){ // full sheet with real numbers; same columns as the import template + extra
  $R['head']=['Sl','Name','Mobile','Amount','Paid','Item','Qty','Balance','By','Date'];
  foreach($s as $c)$R['rows'][]=[(int)$c['serial_no'],$c['name'],(string)$c['mobile'],(float)$c['amount'],(float)$c['paid'],(string)$c['item_name'],$c['qty']?(int)$c['qty']:'',(float)($c['amount']-$c['paid']),sn($c['uname'],$c['short_name']),date('d-m-Y',strtotime($c['created_at']))];
 }else{
  $R['head']=array_merge(['Sl','Name'],$hasItems?['Item']:[],$d?['Amount','Status','By']:['Amount','By']);
  foreach($s as $c){$b=$c['amount']-$c['paid'];$R['rows'][]=array_merge([$c['serial_no'],$c['name']],$hasItems?[item_label($c)]:[],[money($c['amount'])],$d?[$b<=0?'✅':'Bal '.money($b)]:[],[sn($c['uname'],$c['short_name'])]);}
 }
 [$t,$p,$b]=fund_totals($fid);$R['foot']=$d?["Total: ₹".money($t),"Paid: ₹".money($p),"Balance: ₹".money($b)]:["Total contribution: ₹".money($t)];
}elseif($r===3){ // Member-wise
 $R['title']='Member-wise Report: '.$f['title'];$R['head']=['Member','Contribution','Paid recd','Handed','Cash on hand'];
 foreach($mem as $m)$R['rows'][]=[$m['name'].' ('.$m['short'].')',money($m['contrib']),money($m['received']),money($m['handed']),money($m['cash'])];
}elseif($r===4){ // Member cash transactions
 $mm=null;foreach($mem as $m)if($m['id']==$msel)$mm=$m;if(!$mm)$mm=$mem[0];
 $R['title']='Cash Transactions: '.$mm['name'].' ('.$mm['short'].')';$R['head']=['Date','Details','Amount'];$tx=[];
 $s=$pdo->prepare('SELECT p.created_at,p.amount,c.serial_no,c.name FROM payments p JOIN contributions c ON c.id=p.contribution_id WHERE c.fund_id=? AND p.received_by=?');$s->execute([$fid,$mm['id']]);
 foreach($s as $x)$tx[]=[$x['created_at'],'#'.$x['serial_no'].' '.$x['name'],'+'.money($x['amount'])];
 $s=$pdo->prepare('SELECT h.created_at,h.amount,u.name FROM handovers h JOIN users u ON u.id=h.collector_id WHERE h.status=\'approved\' AND h.fund_id=?'.($mm['role']==='collector'?' AND h.collector_id=?':''));
 $s->execute($mm['role']==='collector'?[$fid,$mm['id']]:[$fid]);
 foreach($s as $x)$tx[]=[$x['created_at'],$mm['role']==='collector'?'Handed to creator':'Handover from '.$x['name'],($mm['role']==='collector'?'-':'+').money($x['amount'])];
 usort($tx,fn($a,$b)=>strcmp($a[0],$b[0]));$R['rows']=$tx;$R['foot']=['Cash on hand: ₹'.money($mm['cash'])];
}elseif($r===6){ // Product-wise
 $R['title']='Product Report: '.$f['title'];$R['head']=['Product','Price','Entries','Qty','Amount','Paid','Balance'];$tq=$ta=$tp=0;
 $s=$pdo->prepare('SELECT fi.name,fi.price,COUNT(c.id) n,COALESCE(SUM(c.qty),0) q,COALESCE(SUM(c.amount),0) amt,COALESCE(SUM(pp.paid),0) paid FROM fund_items fi LEFT JOIN contributions c ON c.item_id=fi.id AND c.cancelled=0 LEFT JOIN (SELECT contribution_id,SUM(amount) paid FROM payments GROUP BY contribution_id) pp ON pp.contribution_id=c.id WHERE fi.fund_id=? GROUP BY fi.id ORDER BY fi.id');$s->execute([$fid]);
 foreach($s as $x){$R['rows'][]=[$x['name'],money($x['price']),(int)$x['n'],(int)$x['q'],money($x['amt']),money($x['paid']),money($x['amt']-$x['paid'])];$tq+=$x['q'];$ta+=$x['amt'];$tp+=$x['paid'];}
 $o=$pdo->prepare('SELECT COUNT(*),COALESCE(SUM(amount),0) FROM contributions WHERE fund_id=? AND cancelled=0 AND item_id IS NULL');$o->execute([$fid]);[$on,$oa]=$o->fetch(PDO::FETCH_NUM);
 if($on)$R['rows'][]=['Other (any amount)','',$on,'',money($oa),'',''];
 $R['foot']=["Products qty: $tq","Products total: ₹".money($ta),"Paid: ₹".money($tp),"Balance: ₹".money($ta-$tp)];
}else{ // Collector -> creator payments
 $r=5;$R['title']='Collector to Creator Payments: '.$f['title'];$R['head']=['Collector','Received','Handed','Balance on hand'];$tr=$th=$tb=0;
 foreach($mem as $m)if($m['role']==='collector'){$R['rows'][]=[$m['name'].' ('.$m['short'].')',money($m['received']),money($m['handed']),money($m['cash'])];$tr+=$m['received'];$th+=$m['handed'];$tb+=$m['cash'];}
 $R['foot']=["Total received ₹".money($tr),"Handed to creator ₹".money($th),"Still with collectors ₹".money($tb)];
}
if($xls){ // Excel download of the report on screen; "1,234.00" becomes a number
 $num=fn($v)=>is_string($v)&&preg_match('/^[+-]?[\d,]+\.\d\d$/',$v)?(float)str_replace(',','',$v):$v;
 $out=[[$R['title']]];foreach($R['lines'] as $l)$out[]=[$l];$out[]=[];$out[]=$R['head'];
 foreach($R['rows'] as $row)$out[]=array_map($num,$row);
 if($R['foot']){$out[]=[];foreach($R['foot'] as $l)$out[]=[$l];}
 if($r===2)$out=array_merge([$R['head']],$R['rows']); // contributions: plain sheet, header row first (same columns as the import)
 xlsx_send($R['title'],$out);
}
// WhatsApp text
$txt="*{$R['title']}*\n";foreach($R['lines'] as $l)$txt.="$l\n";
if($R['rows'])$txt.="\n".implode(' | ',$R['head'])."\n";
foreach($R['rows'] as $row)$txt.=implode(' | ',$row)."\n";
if($R['foot'])$txt.="\n".implode("\n",$R['foot']);
head('Report');
$tabs=[1=>'Fund',2=>'Contributions',3=>'Members',4=>'Member cash',5=>'Handover']+($hasItems||$r===6?[6=>'Products']:[]);?>
<div class="noprint">
<div class="d-flex flex-wrap gap-1 my-2"><?php foreach($tabs as $k=>$v):?><a class="btn btn-sm btn-<?=$k===$r?'primary':'outline-primary'?>" href="reports.php?id=<?=$fid?>&r=<?=$k?>"><?=$v?></a><?php endforeach;?></div>
<?php if($r===4):?><form class="mb-2"><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="r" value="4">
<select class="form-select" name="m" onchange="this.form.submit()"><?php foreach($mem as $m):?><option value="<?=$m['id']?>" <?=$m['id']==$msel?'selected':''?>><?=e($m['name'])?></option><?php endforeach;?></select></form><?php endif;?>
<?php if($r===2):?><div class="btn-group btn-group-sm mb-2"><a class="btn btn-<?=$d?'primary':'outline-primary'?>" href="reports.php?id=<?=$fid?>&r=2&d=1">With paid &amp; balance</a><a class="btn btn-<?=!$d?'primary':'outline-primary'?>" href="reports.php?id=<?=$fid?>&r=2&d=0">Contribution only</a></div><?php endif;?>
<div class="mb-3"><button class="btn btn-danger btn-sm" onclick="window.print()">📄 PDF (Save as PDF)</button>
<a class="btn btn-primary btn-sm" target="_blank" href="<?=e(wa($txt))?>">WhatsApp Share</a>
<a class="btn btn-success btn-sm" href="reports.php?<?=e(http_build_query(['id'=>$fid,'r'=>$r,'d'=>$d?1:0,'m'=>$msel,'xls'=>1]))?>" download>📊 Excel</a></div></div>
<div class="card p-3"><h5><?=e($R['title'])?></h5>
<?php foreach($R['lines'] as $l)echo '<div class="small">'.e($l).'</div>';?>
<?php if($R['rows']):?><div class="table-responsive mt-2"><table class="table table-sm table-bordered mb-1"><thead class="table-light"><tr><?php foreach($R['head'] as $h)echo '<th>'.e($h).'</th>';?></tr></thead><tbody>
<?php foreach($R['rows'] as $row){echo '<tr>';foreach($row as $c)echo '<td>'.e($c).'</td>';echo '</tr>';}?></tbody></table></div><?php else:echo '<p class="text-muted mt-2">No data.</p>';endif;?>
<?php foreach($R['foot'] as $l)echo '<div><b>'.e($l).'</b></div>';?></div>
<?php foot();
