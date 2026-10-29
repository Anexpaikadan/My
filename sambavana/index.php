<?php require 'config.php';
if(me())redirect('dashboard.php');
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $s=$pdo->prepare('SELECT * FROM users WHERE username=?');$s->execute([trim($_POST['username'])]);$u=$s->fetch();
 if(!$u||!password_verify($_POST['password'],$u['password']))flash('Wrong username or password / തെറ്റായ വിവരങ്ങൾ','danger');
 elseif($u['status']==='pending')flash('Waiting for admin approval / അഡ്മിൻ അംഗീകാരത്തിനായി കാത്തിരിക്കുക','warning');
 elseif($u['status']!=='approved')flash('Account '.$u['status'],'danger');
 else{session_regenerate_id(true);$_SESSION['uid']=$u['id'];redirect('dashboard.php');}
}
head('Login');?>
<div class="text-center mb-3"><img src="logo.png" style="max-width:220px;width:70%" alt=""></div>
<div class="card p-3"><h5>Login / ലോഗിൻ</h5>
<form method="post"><?=csrf_field()?>
<input class="form-control mb-2" name="username" placeholder="Mobile / Username" required>
<input class="form-control mb-2" type="password" name="password" placeholder="Password / പാസ്‌വേഡ്" required>
<button class="btn btn-primary w-100">Login</button></form>
<a class="d-block mt-3 text-center small" href="forgot.php">Forgot password? / പാസ്‌വേഡ് മറന്നോ?</a>
<a class="d-block mt-2 text-center" href="signup.php">New user? Sign up / രജിസ്റ്റർ ചെയ്യുക</a></div>
<?php foot();
