<?php require 'config.php';
// Add many contributions at once from Excel (.xlsx) or CSV, to a running fund. Upload -> check (preview) -> import.
[$f,$role]=fund_access($_GET['id']??$_POST['id']??0);if($role!=='creator'){http_response_code(403);die('Creator only');}
$u=me();$fid=$f['id'];nav($f,$role,'entry');$GLOBALS['BACK']="settings.php?id=$fid";
$items=fund_items($fid,true);$byName=[];foreach($items as $it)$byName[mb_strtolower(trim($it['name']))]=$it;
if(isset($_GET['template'])){
 $rows=[['Name','Mobile','Amount','Paid','Item','Qty']];
 if($items){$it=$items[0];$rows[]=['Raman K','9876543210','',(float)$it['price'],$it['name'],1];$rows[]=['സുരേഷ്','','',0,$it['name'],2];}
 $rows[]=['Mary Joseph','9847000000',1000,500,'',''];
 xlsx_send('Import template - '.$f['title'],$rows);
}
if($f['status']==='closed'){head('Import');echo '<div class="alert alert-secondary">🔒 This fund is closed. Reopen it in Settings to import entries.</div>';foot();exit;}
$num=fn($v)=>trim(str_replace([',','₹','Rs.','Rs',' '],'',(string)$v));
// Which column is which: header names in English or Malayalam; no header row = default order
function import_cols($row){
 $alias=['name'=>['name','contributor','പേര്'],'mobile'=>['mobile','phone','mobileno','whatsapp','മൊബൈൽ','ഫോൺ'],
  'amount'=>['amount','contribution','total','തുക','സംഭാവന'],'paid'=>['paid','payment','paidnow','നൽകിയത്','അടച്ചത്'],
  'item'=>['item','product','type','ഇനം'],'qty'=>['qty','quantity','number','nos','count','എണ്ണം']];
 $map=[];
 foreach($row as $i=>$h){$k=preg_replace('/[^\p{L}\p{M}\p{N}]+/u','',mb_strtolower((string)$h));
  foreach($alias as $col=>$names)if(!isset($map[$col])&&in_array($k,$names,true))$map[$col]=$i;}
 return isset($map['name'])?[$map,true]:[['name'=>0,'mobile'=>1,'amount'=>2,'paid'=>3,'item'=>4,'qty'=>5],false];
}
$key='imp'.$fid;$prev=$_SESSION[$key]??null;
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();$do=$_POST['do']??'';
 if($do==='clear'){unset($_SESSION[$key]);redirect("import.php?id=$fid");}
 if($do==='confirm'){
  $ok=array_values(array_filter($prev['rows']??[],fn($r)=>!$r['err']));
  if(!$ok){flash('Nothing to import','danger');redirect("import.php?id=$fid");}
  try{$pdo->beginTransaction();
   $s=$pdo->prepare('SELECT COALESCE(MAX(serial_no),0) FROM contributions WHERE fund_id=? FOR UPDATE');$s->execute([$fid]);$sl=(int)$s->fetchColumn();$first=$sl+1;
   $ins=$pdo->prepare('INSERT INTO contributions(fund_id,serial_no,name,mobile,item_id,qty,amount,created_by) VALUES(?,?,?,?,?,?,?,?)');
   $pay=$pdo->prepare('INSERT INTO payments(contribution_id,amount,received_by) VALUES(?,?,?)');
   foreach($ok as $r){$ins->execute([$fid,++$sl,$r['name'],$r['mobile'],$r['item_id'],$r['qty'],$r['amount'],$u['id']]);
    if($r['paid']>0)$pay->execute([$pdo->lastInsertId(),$r['paid'],$u['id']]);}
   $pdo->commit();unset($_SESSION[$key]);
   flash('Imported '.count($ok).' entries (No. '.$first.' to '.$sl.') ✔');redirect("fund.php?id=$fid");
  }catch(Exception $x){if($pdo->inTransaction())$pdo->rollBack();flash('Import failed, nothing was saved. Try again.','danger');redirect("import.php?id=$fid");}
 }
 // upload: read + check every row, keep the result in the session for the preview
 $fl=$_FILES['file']??null;$ext=strtolower(pathinfo($fl['name']??'',PATHINFO_EXTENSION));
 try{
  if(!$fl||$fl['error']!==UPLOAD_ERR_OK)throw new Exception('Choose a file');
  if($fl['size']>5*1024*1024)throw new Exception('File too big (max 5 MB)');
  if($ext==='xls')throw new Exception('Old .xls format: in Excel use Save As → "Excel Workbook (.xlsx)" or CSV');
  if(!in_array($ext,['xlsx','csv','txt'],true))throw new Exception('Upload an Excel .xlsx or .csv file');
  $rows=$ext==='xlsx'?xlsx_read($fl['tmp_name']):csv_read($fl['tmp_name']);
  $rows=array_values(array_filter($rows,fn($r)=>implode('',array_map('trim',array_map('strval',$r)))!==''));
  if(!$rows)throw new Exception('The file is empty');
  [$c,$hasHead]=import_cols($rows[0]);if($hasHead)array_shift($rows);
  if(count($rows)>3000)throw new Exception('Max 3000 rows at a time');
  $ex=$pdo->prepare('SELECT LOWER(name) n,amount FROM contributions WHERE fund_id=? AND cancelled=0');$ex->execute([$fid]);$have=[];foreach($ex as $x)$have[$x['n'].'|'.(float)$x['amount']]=1;
  $out=[];
  foreach($rows as $i=>$r){$g=fn($k)=>isset($c[$k])?trim((string)($r[$c[$k]]??'')):'';
   $o=['line'=>$i+($hasHead?2:1),'name'=>mb_substr($g('name'),0,120),'mobile'=>null,'item_id'=>null,'item'=>'','qty'=>null,'amount'=>0,'paid'=>0,'err'=>'','warn'=>''];
   $mob=preg_replace('/\D/','',$g('mobile'));if($mob!==''){if(strlen($mob)>10&&preg_match('/^(91|0)/',$mob))$mob=substr($mob,-10);$o['mobile']=$mob;}
   $amt=$num($g('amount'));$pd=$num($g('paid'));$it=$g('item');$q=$num($g('qty'));
   if($o['name']==='')$o['err']='Name missing';
   elseif($o['mobile']!==null&&strlen($o['mobile'])!==10)$o['err']='Mobile must be 10 digits';
   elseif($it!==''&&!isset($byName[mb_strtolower($it)]))$o['err']='Unknown product "'.$it.'" (add it in Products first)';
   elseif($q!==''&&(!ctype_digit($q)||(int)$q<1))$o['err']='Qty must be a whole number';
   elseif($amt!==''&&!is_numeric($amt))$o['err']='Amount is not a number';
   elseif($pd!==''&&(!is_numeric($pd)||$pd<0))$o['err']='Paid is not a number';
   if(!$o['err']){
    if($it!==''){$P=$byName[mb_strtolower($it)];$o['item_id']=(int)$P['id'];$o['item']=$P['name'];$o['qty']=$q===''?1:(int)$q;$calc=round($P['price']*$o['qty'],2);
     if($amt===''||(float)$amt==0)$o['amount']=$calc;else{$o['amount']=(float)$amt;if(abs($o['amount']-$calc)>0.001)$o['warn']='Price × qty = ₹'.money($calc);}}
    else $o['amount']=(float)$amt;
    $o['paid']=$pd===''?0:round((float)$pd,2);
    if($o['amount']<=0)$o['err']='Amount missing';
    elseif($o['paid']>$o['amount'])$o['err']='Paid is more than amount';
    elseif(isset($have[mb_strtolower($o['name']).'|'.$o['amount']]))$o['warn']=trim($o['warn'].' Same name & amount already in fund');
   }
   $out[]=$o;}
  $_SESSION[$key]=$prev=['file'=>$fl['name'],'rows'=>$out];
 }catch(Exception $x){flash($x->getMessage(),'danger');}
 redirect("import.php?id=$fid");
}
head('Import from Excel');?>
<h5 class="mt-2">📥 Import from Excel / എക്സൽ വഴി ചേർക്കുക</h5>
<?php if(!$prev):?>
<div class="card p-3 mb-3"><ol class="small mb-2 ps-3">
<li>Download the template, fill one contributor per row. / ടെംപ്ലേറ്റ് ഡൗൺലോഡ് ചെയ്ത് ഓരോ വരിയിലും ഒരാളെ ചേർക്കുക.</li>
<li>Columns: <b>Name</b>, Mobile, <b>Amount</b>, Paid, Item, Qty. For a product (e.g. <?=e($items[0]['name']??'Payasam')?>) write the product name and qty — amount can be left empty.</li>
<li>Upload, check the preview, then press Import. New numbers continue after the last entry.</li></ol>
<a class="btn btn-outline-success mb-3" href="import.php?id=<?=$fid?>&template=1" download>⬇ Download Excel template</a>
<form method="post" enctype="multipart/form-data"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="do" value="upload">
<label class="small fw-bold">Step 1: choose the Excel file / ഫയൽ തിരഞ്ഞെടുക്കുക</label>
<input id="xf" class="form-control mb-2" type="file" name="file" accept=".xlsx,.csv" required>
<button id="xb" class="btn btn-primary w-100">⬆ Upload &amp; check</button></form></div>
<script>document.getElementById('xf').onchange=function(){if(this.files.length){var b=document.getElementById('xb');b.textContent='⏳ Checking…';b.disabled=true;this.form.submit();}};</script>
<?php if($items):?><p class="small text-muted">Products in this fund: <?php foreach($items as $it)echo '<span class="itm">'.e($it['name']).' ₹'.money($it['price']).'</span> ';?></p><?php endif;?>
<?php else:$ok=array_filter($prev['rows'],fn($r)=>!$r['err']);$bad=count($prev['rows'])-count($ok);$sum=array_sum(array_column($ok,'amount'));$paid=array_sum(array_column($ok,'paid'));?>
<div class="alert alert-warning py-2 small mb-2"><b>Step 2: not saved yet.</b> Check the list below, then press <b>✔ Import</b>.<br>ഇതുവരെ സേവ് ആയിട്ടില്ല — ലിസ്റ്റ് നോക്കി <b>Import</b> അമർത്തുക.</div>
<div class="card p-3 mb-2"><div class="small text-muted"><?=e($prev['file'])?></div>
<div><b class="text-success"><?=count($ok)?> ready</b><?php if($bad):?> · <b class="text-danger"><?=$bad?> with errors (skipped)</b><?php endif;?></div>
<div class="small">Total ₹<?=money($sum)?> · Paid ₹<?=money($paid)?> · Balance ₹<?=money($sum-$paid)?></div>
<div class="d-flex gap-2 mt-2">
<?php if($ok):?><div class="flex-grow-1"><form method="post" onsubmit="this.querySelector('button').disabled=true"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="do" value="confirm"><button class="btn btn-primary btn-lg w-100">✔ Import <?=count($ok)?> entries / ചേർക്കുക</button></form></div><?php endif;?>
<form method="post"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><button name="do" value="clear" class="btn btn-outline-secondary">Cancel</button></form></div></div>
<div class="table-responsive"><table class="table table-sm table-bordered small bg-white"><thead class="table-light"><tr><th>Row</th><th>Name</th><th>Mobile</th><th>Item</th><th class="text-end">Amount</th><th class="text-end">Paid</th><th>Check</th></tr></thead><tbody>
<?php foreach($prev['rows'] as $r):?><tr class="<?=$r['err']?'table-danger':($r['warn']?'table-warning':'')?>"><td><?=$r['line']?></td><td><?=e($r['name'])?></td><td><?=e($r['mobile'])?></td><td><?=$r['item']!==''?e($r['item'].' × '.$r['qty']):''?></td><td class="text-end"><?=money($r['amount'])?></td><td class="text-end"><?=money($r['paid'])?></td><td><?=$r['err']?'✖ '.e($r['err']):($r['warn']?'⚠ '.e($r['warn']):'✔')?></td></tr><?php endforeach;?>
</tbody></table></div>
<?php if($ok):?><div class="position-sticky noprint py-2" style="bottom:70px;z-index:40"><form method="post" onsubmit="this.querySelector('button').disabled=true"><?=csrf_field()?><input type="hidden" name="id" value="<?=$fid?>"><input type="hidden" name="do" value="confirm"><button class="btn btn-primary btn-lg w-100">✔ Import <?=count($ok)?> entries / ചേർക്കുക</button></form></div><?php endif;?>
<?php endif;
foot();
