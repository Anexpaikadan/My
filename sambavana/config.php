<?php
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
function sn($name,$short){return $short?:mb_strtoupper(mb_substr($name,0,2));}
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
<link rel="icon" href="logo.png"><link rel="manifest" href="manifest.json"><link rel="apple-touch-icon" href="icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="സംഭാവന"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
:root{--p:#3513d6;--g:#7ed957;--bs-link-color:#3513d6;--bs-link-hover-color:#2a0fae}
body{background:#f6f5fd;padding-bottom:84px}
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
