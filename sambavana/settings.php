<?php require 'config.php';
[$f,$role]=fund_access($_POST['id']??0);if($role!=='creator'){http_response_code(403);die('Creator only');}
csrf_check();$fid=$f['id'];$do=$_POST['do']??'';
if($do==='settings'){
 $t=(float)($_POST['target']??0);
 $pdo->prepare('UPDATE funds SET target_amount=?,show_target=?,reminders=? WHERE id=?')->execute([$t>0?$t:null,isset($_POST['show_target'])?1:0,isset($_POST['reminders'])?1:0,$fid]);
 flash('Settings saved');
}elseif($do==='close'||$do==='reopen'){
 $pdo->prepare('UPDATE funds SET status=? WHERE id=?')->execute([$do==='close'?'closed':'open',$fid]);
 flash($do==='close'?'Fund closed 🔒':'Fund reopened');
}
redirect("fund.php?id=$fid");
