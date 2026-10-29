<?php
session_set_cookie_params(['httponly'=>true,'samesite'=>'Lax','secure'=>(!empty($_SERVER['HTTPS'])&&$_SERVER['HTTPS']!=='off')]);
session_start();
require __DIR__.'/db_config.php';
$pdo=new PDO('mysql:host='.DB_HOST.';dbname='.DB_NAME.';charset=utf8mb4',DB_USER,DB_PASS,
 [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);

function e($s){return htmlspecialchars((string)$s,ENT_QUOTES,'UTF-8');}
function money($n){return number_format((float)$n,2);}
function csrf_field(){if(empty($_SESSION['t']))$_SESSION['t']=bin2hex(random_bytes(32));return '<input type="hidden" name="_t" value="'.$_SESSION['t'].'">';}
function csrf_check(){if($_SERVER['REQUEST_METHOD']==='POST'&&!hash_equals($_SESSION['t']??'',$_POST['_t']??''))die('Invalid request');}
function redirect($u){header('Location: '.$u);exit;}
function flash($m,$t='success'){$_SESSION['flash']=[$m,$t];}
// First 2 letters; \X keeps Malayalam vowel signs with their letter (കൃ, സു)
function sn($name,$short){if($short)return $short;preg_match_all('/\X/u',trim((string)$name),$m);return mb_strtoupper(implode('',array_slice($m[0],0,2)));}
function wa($text,$to=null){$n=preg_replace('/\D/','',(string)$to);if(strlen($n)===10)$n='91'.$n;return 'https://wa.me/'.$n.'?text='.rawurlencode($text);}

function me(){
 global $pdo;static $u=false;
 if($u===false){$u=null;
  if(!empty($_SESSION['uid'])){$s=$pdo->prepare("SELECT * FROM users WHERE id=? AND status='approved'");$s->execute([$_SESSION['uid']]);$u=$s->fetch()?:null;}}
 return $u;
}
function require_login($roles=null){
 $u=me();if(!$u)redirect('index.php');
 if($roles&&!in_array($u['role'],$roles,true)){http_response_code(403);die('Access denied');}
 return $u;
}
// Per-fund authorization. Admin never passes. Returns [fund, 'creator'|'collector']
function fund_access($fid){
 global $pdo;$u=require_login(['user','collector']);
 $s=$pdo->prepare('SELECT * FROM funds WHERE id=?');$s->execute([(int)$fid]);$f=$s->fetch();
 if($f){
  if($u['role']==='user'&&$f['creator_id']==$u['id'])return [$f,'creator'];
  if($u['role']==='collector'&&$u['fund_id']==$f['id'])return [$f,'collector'];
 }
 http_response_code(403);die('Access denied');
}
function fund_totals($fid){
 global $pdo;
 $s=$pdo->prepare('SELECT COALESCE(SUM(amount),0) FROM contributions WHERE cancelled=0 AND fund_id=?');$s->execute([$fid]);$t=(float)$s->fetchColumn();
 $s=$pdo->prepare('SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN contributions c ON c.id=p.contribution_id WHERE c.fund_id=?');$s->execute([$fid]);$p=(float)$s->fetchColumn();
 return [$t,$p,$t-$p];
}
// Fixed-price products of a fund (e.g. Payasam ₹500). Contributions may be "item × qty".
function fund_items($fid,$all=false){
 global $pdo;$s=$pdo->prepare('SELECT * FROM fund_items WHERE fund_id=?'.($all?'':' AND active=1').' ORDER BY active DESC,id');$s->execute([$fid]);return $s->fetchAll();
}
function item_of($fid,$iid){
 global $pdo;$s=$pdo->prepare('SELECT * FROM fund_items WHERE id=? AND fund_id=?');$s->execute([(int)$iid,$fid]);return $s->fetch()?:null;
}
// "Payasam × 2" for a contribution row that has item_name/qty, else ''
function item_label($c){return !empty($c['item_name'])?$c['item_name'].' × '.(int)$c['qty']:'';}
function bal_badge($b){return $b<=0?'<span class="ok">✔ Paid</span>':'<span class="bal">Bal ₹'.money($b).'</span>';}
const ITEM_JOIN=' LEFT JOIN fund_items fi ON fi.id=c.item_id ';

// ---- Excel (.xlsx) and CSV, without extra libraries ----
function xlsx_col($ref){$n=0;foreach(str_split(preg_replace('/\d/','',$ref)) as $ch)$n=$n*26+ord($ch)-64;return $n-1;}
// Rows of the first sheet as arrays of strings
function xlsx_read($path){
 if(!class_exists('ZipArchive'))throw new Exception('Excel (.xlsx) not supported on this server, upload CSV');
 $z=new ZipArchive;if($z->open($path)!==true)throw new Exception('Not a valid .xlsx file');
 $ss=[];
 if(($x=$z->getFromName('xl/sharedStrings.xml'))!==false){$xml=simplexml_load_string($x);
  foreach($xml->si as $si){$t=isset($si->t)?(string)$si->t:'';foreach($si->r as $r)$t.=(string)$r->t;$ss[]=$t;}}
 $sheet='xl/worksheets/sheet1.xml';
 $wb=$z->getFromName('xl/workbook.xml');$rel=$z->getFromName('xl/_rels/workbook.xml.rels');
 if($wb&&$rel){$w=simplexml_load_string($wb);$first=$w->sheets->sheet[0]??null;
  if($first){$rid=(string)$first->attributes('http://schemas.openxmlformats.org/officeDocument/2006/relationships')['id'];
   foreach(simplexml_load_string($rel)->Relationship as $r)if((string)$r['Id']===$rid){$t=ltrim((string)$r['Target'],'/');$sheet=strpos($t,'xl/')===0?$t:'xl/'.$t;}}}
 $x=$z->getFromName($sheet);$z->close();
 if($x===false)throw new Exception('Sheet not found in the Excel file');
 $xml=simplexml_load_string($x);$rows=[];
 foreach($xml->sheetData->row as $row){$out=[];$i=0;
  foreach($row->c as $c){$col=isset($c['r'])?xlsx_col((string)$c['r']):$i;$t=(string)$c['t'];
   if($t==='s')$v=$ss[(int)$c->v]??'';elseif($t==='inlineStr'){$v=(string)$c->is->t;foreach($c->is->r as $r)$v.=(string)$r->t;}else $v=(string)$c->v;
   if($t===''&&is_numeric($v)&&stripos($v,'e')!==false)$v=rtrim(rtrim(sprintf('%.2f',(float)$v),'0'),'.'); // 9.87E9 -> 9870000000
   $out[$col]=$v;$i=$col+1;}
  if($out){$r=array_fill(0,max(array_keys($out))+1,'');foreach($out as $k=>$v)$r[$k]=$v;$rows[]=$r;}}
 return $rows;
}
function csv_read($path){
 $s=file_get_contents($path);if(strncmp($s,"\xEF\xBB\xBF",3)===0)$s=substr($s,3);
 if(!mb_check_encoding($s,'UTF-8'))$s=mb_convert_encoding($s,'UTF-8','Windows-1252');
 $first=strtok($s,"\n");$d=',';foreach([";","\t"] as $c)if(substr_count($first,$c)>substr_count($first,$d))$d=$c;
 $h=fopen('php://memory','r+');fwrite($h,$s);rewind($h);$rows=[];
 while(($r=fgetcsv($h,0,$d,'"','\\'))!==false)if($r!==[null])$rows[]=$r;
 fclose($h);return $rows;
}
// Send rows as a download. Numbers stay numbers so Excel can add them up.
function xlsx_send($name,$rows){
 if(!class_exists('ZipArchive')){header('Content-Type: text/csv; charset=utf-8');header('Content-Disposition: attachment; filename="'.$name.'.csv"');
  $o=fopen('php://output','w');fwrite($o,"\xEF\xBB\xBF");foreach($rows as $r)fputcsv($o,$r,',','"','\\');exit;}
 $x=fn($s)=>htmlspecialchars((string)$s,ENT_XML1|ENT_QUOTES,'UTF-8');$sd='';
 foreach($rows as $i=>$r){$sd.='<row r="'.($i+1).'">';
  foreach(array_values($r) as $j=>$v){$ref='';$n=$j;do{$ref=chr(65+$n%26).$ref;$n=intdiv($n,26)-1;}while($n>=0);$ref.=($i+1);$st=$i===0?' s="1"':'';
   $sd.=(is_int($v)||is_float($v))?'<c r="'.$ref.'"'.$st.'><v>'.$v.'</v></c>':'<c r="'.$ref.'" t="inlineStr"'.$st.'><is><t xml:space="preserve">'.$x($v).'</t></is></c>';}
  $sd.='</row>';}
 $ns='http://schemas.openxmlformats.org/';
 $files=['[Content_Types].xml'=>'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="'.$ns.'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
  '_rels/.rels'=>'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="'.$ns.'package/2006/relationships"><Relationship Id="rId1" Type="'.$ns.'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
  'xl/workbook.xml'=>'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="'.$ns.'spreadsheetml/2006/main" xmlns:r="'.$ns.'officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
  'xl/_rels/workbook.xml.rels'=>'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="'.$ns.'package/2006/relationships"><Relationship Id="rId1" Type="'.$ns.'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="'.$ns.'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
  'xl/styles.xml'=>'<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="'.$ns.'spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>',
  'xl/worksheets/sheet1.xml'=>'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="'.$ns.'spreadsheetml/2006/main"><sheetData>'.$sd.'</sheetData></worksheet>'];
 $tmp=tempnam(sys_get_temp_dir(),'xl');$z=new ZipArchive;$z->open($tmp,ZipArchive::OVERWRITE);foreach($files as $k=>$v)$z->addFromString($k,$v);$z->close();
 header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
 $fn=preg_replace('/[^\w\-]+/u','_',$name);header('Content-Disposition: attachment; filename="'.(preg_replace('/[^A-Za-z0-9_\-]+/','_',$fn)?:'report').'.xlsx"; filename*=UTF-8\'\''.rawurlencode($fn).'.xlsx');header('Content-Length: '.filesize($tmp));
 readfile($tmp);unlink($tmp);exit;
}

// Creator + collectors with contributed / received / handed / cash on hand
function members($f){
 global $pdo;$fid=$f['id'];
 $s=$pdo->prepare('SELECT id,name,short_name,0 AS o FROM users WHERE id=? UNION ALL SELECT id,name,short_name,1 FROM users WHERE role="collector" AND fund_id=? ORDER BY o,id');
 $s->execute([$f['creator_id'],$fid]);$rows=$s->fetchAll();
 $hs=$pdo->prepare('SELECT COALESCE(SUM(amount),0) FROM handovers WHERE status=\'approved\' AND fund_id=?');$hs->execute([$fid]);$handedAll=(float)$hs->fetchColumn();
 foreach($rows as &$m){
  $q=$pdo->prepare('SELECT COALESCE(SUM(amount),0) FROM contributions WHERE cancelled=0 AND fund_id=? AND created_by=?');$q->execute([$fid,$m['id']]);$m['contrib']=(float)$q->fetchColumn();
  $q=$pdo->prepare('SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN contributions c ON c.id=p.contribution_id WHERE c.fund_id=? AND p.received_by=?');$q->execute([$fid,$m['id']]);$m['received']=(float)$q->fetchColumn();
  $q=$pdo->prepare('SELECT COALESCE(SUM(amount),0) FROM handovers WHERE status=\'approved\' AND fund_id=? AND collector_id=?');$q->execute([$fid,$m['id']]);
  if($m['id']==$f['creator_id']){$m['role']='creator';$m['handed']=0;$m['cash']=$m['received']+$handedAll;}
  else{$m['role']='collector';$m['handed']=(float)$q->fetchColumn();$m['cash']=$m['received']-$m['handed'];}
  $m['short']=sn($m['name'],$m['short_name']);
 }
 return $rows;
}
$GLOBALS['NAV']=null;
function nav($f,$role,$active){
 global $pdo;$id=$f['id'];
 $items=[['home','🏠','Home',"fund.php?id=$id"],['entry','➕','Entry',"entry.php?id=$id"]];
 if($role==='creator'){$items[]=['reports','📊','Reports',"reports.php?id=$id"];$items[]=['transfer','💵','Transfer',"handover.php?id=$id"];$items[]=['team','👥','Collectors',"collectors.php?id=$id"];}
 else{$items[]=['reports','📤','Share',"reports.php?id=$id"];$items[]=['transfer','💵','Transfer',"handover.php?id=$id"];}
 if(!empty($f['reminders']))$items[]=['remind','🔔','Pending',"remind.php?id=$id"];
 $b=0;
 if($role==='creator'){$q=$pdo->prepare("SELECT COUNT(*) FROM handovers WHERE fund_id=? AND status='pending'");$q->execute([$id]);$b=(int)$q->fetchColumn();}
 $GLOBALS['NAV']=[$items,$active,$b];
}
function head($title){
 $u=me();$fl=$_SESSION['flash']??null;unset($_SESSION['flash']);
 echo '<!doctype html><html lang="ml"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#3513d6"><title>'.e($title).' - സംഭാവന</title>
<link rel="icon" href="logo.png"><link rel="manifest" href="manifest.json"><link rel="apple-touch-icon" href="icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="സംഭാവന"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;600;700&display=swap" rel="stylesheet"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
:root{--p:#3513d6;--g:#7ed957;--bs-link-color:#3513d6;--bs-link-hover-color:#2a0fae;--bs-body-font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans Malayalam","Nirmala UI","Kartika",sans-serif}
body{background:#f6f5fd;padding-bottom:84px;line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.small,small{font-size:.9em}
.form-control::placeholder{color:#8a8aa0}
.bal{background:#fdecee;color:#b02a37;border-radius:6px;padding:0 6px;font-weight:600;white-space:nowrap}
.ok{background:#e8f8e1;color:#2f7d14;border-radius:6px;padding:0 6px;font-weight:600;white-space:nowrap}
.itm{background:#ece8ff;color:#3513d6;border-radius:6px;padding:0 6px;font-size:.85em;white-space:nowrap}
.navbar{background:#fff;border-bottom:3px solid var(--g)}
.card{border:0;box-shadow:0 1px 4px #3513d614;border-radius:12px}
.btn-primary{--bs-btn-bg:#3513d6;--bs-btn-border-color:#3513d6;--bs-btn-hover-bg:#2a0fae;--bs-btn-hover-border-color:#2a0fae;--bs-btn-active-bg:#2a0fae;--bs-btn-active-border-color:#2a0fae}
.btn-outline-primary{--bs-btn-color:#3513d6;--bs-btn-border-color:#3513d6;--bs-btn-hover-bg:#3513d6;--bs-btn-hover-border-color:#3513d6;--bs-btn-active-bg:#3513d6;--bs-btn-active-border-color:#3513d6}
.btn-success{--bs-btn-bg:#7ed957;--bs-btn-border-color:#7ed957;--bs-btn-color:#10300a;--bs-btn-hover-bg:#6cc946;--bs-btn-hover-border-color:#6cc946;--bs-btn-hover-color:#10300a;--bs-btn-active-bg:#6cc946;--bs-btn-active-color:#10300a}
.text-success{color:#3a9a1c!important}
.bnav{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid #ddd;display:flex;padding-bottom:env(safe-area-inset-bottom);z-index:50}
.bnav a{flex:1;text-align:center;padding:6px 2px 5px;font-size:11px;color:#666;text-decoration:none;position:relative;border-top:3px solid transparent}
.bnav a span{display:block;font-size:20px;line-height:1.2}
.bnav a.on{color:var(--p);font-weight:700;border-top-color:var(--p)}
.bdg{position:absolute;top:2px;right:16%;background:#dc3545;color:#fff;border-radius:10px;padding:0 5px;font-size:10px}
@media print{.noprint{display:none!important}body{background:#fff;padding:0}}
</style></head><body>
<nav class="navbar noprint"><div class="container" style="max-width:820px"><a class="navbar-brand d-flex align-items-center gap-2 m-0" href="dashboard.php"><img src="logo.png" height="32" alt=""><b style="color:var(--p);font-size:16px">സംഭാവന</b></a>';
 echo '<div class="d-flex align-items-center gap-2"><button id="inst" type="button" class="btn btn-sm btn-primary d-none">📲 Install</button>';
 if($u)echo '<span class="small"><b>'.e($u['name']).'</b> · <a href="logout.php">Logout</a></span>';
 echo '</div></div></nav><div class="container py-3" style="max-width:820px">';
 if($fl)echo '<div class="alert alert-'.$fl[1].' noprint">'.e($fl[0]).'</div>';
}
function foot(){
 echo '</div>';
 if($n=$GLOBALS['NAV']){echo '<nav class="bnav noprint">';
  foreach($n[0] as $i){echo '<a class="'.($i[0]===$n[1]?'on':'').'" href="'.$i[3].'"><span>'.$i[1].'</span>'.$i[2].($i[0]==='transfer'&&$n[2]?'<b class="bdg">'.$n[2].'</b>':'').'</a>';}
  echo '</nav>';}
 echo '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script><script src="app.js"></script></body></html>';
}
