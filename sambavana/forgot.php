<?php require 'config.php';
if(me())redirect('dashboard.php');
$sent=false;
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $m=preg_replace('/\D/','',$_POST['mobile']??'');$m=substr($m,-10);
 if(strlen($m)===10)$pdo->prepare("UPDATE users SET reset_requested=1 WHERE username=? AND role='user'")->execute([$m]);
 $sent=true; // same answer whether or not the number exists
}
head('Forgot password');?>
<div class="text-center mb-3"><img src="logo.png" style="max-width:220px;width:70%" alt=""></div>
<div class="card p-3"><h5>Forgot password / പാസ്‌വേഡ് മറന്നോ?</h5>
<?php if($sent):?><div class="alert alert-success">Request sent. If this mobile number is registered, the admin will send you a reset link (WhatsApp).<br>അഡ്മിൻ റീസെറ്റ് ലിങ്ക് അയച്ചുതരും.</div>
<?php else:?><form method="post"><?=csrf_field()?>
<input class="form-control mb-2" name="mobile" placeholder="Your registered mobile (10 digits)" inputmode="numeric" maxlength="13" required>
<button class="btn btn-primary w-100">Ask admin for reset link</button></form><?php endif;?>
<a class="d-block mt-3 text-center" href="index.php">Back to login</a></div>
<?php foot();
