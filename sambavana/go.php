<?php require 'config.php';$u=require_login(['user','collector']);
// App-icon shortcuts (long-press the icon): New entry / Add payment in the fund used last
$to=($_GET['to']??'')==='pay'?'pay.php':'entry.php';
if($u['role']==='collector')$fid=(int)$u['fund_id'];
else{$s=$pdo->prepare("SELECT id FROM funds WHERE creator_id=? AND status='open' ORDER BY id=? DESC,id DESC LIMIT 1");$s->execute([$u['id'],(int)($_COOKIE['lastfund']??0)]);$fid=(int)$s->fetchColumn();}
if(!$fid){flash('No open fund yet — create one in Account','warning');redirect('dashboard.php');}
redirect("$to?id=$fid");
