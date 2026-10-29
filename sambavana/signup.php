<?php require 'config.php';
if($_SERVER['REQUEST_METHOD']==='POST'){csrf_check();
 $n=trim($_POST['name']);$m=trim($_POST['mobile']);$p=$_POST['password'];
 if($n===''||!preg_match('/^\d{10}$/',$m)||strlen($p)<6)flash('Enter name, 10-digit mobile, password (6+)','danger');
 else try{
  $pdo->prepare("INSERT INTO users(name,username,password,role,status) VALUES(?,?,?,'user','pending')")->execute([$n,$m,password_hash($p,PASSWORD_DEFAULT)]);
  flash('Registered. Wait for admin approval / അഡ്മിൻ അംഗീകരിച്ച ശേഷം ലോഗിൻ ചെയ്യാം');redirect('index.php');
 }catch(PDOException $x){flash('Mobile already registered','danger');}
}
head('Sign up');?>
<div class="text-center mb-3"><img src="logo.png" style="max-width:220px;width:70%" alt=""></div>
<div class="card p-3"><h5>Sign up / രജിസ്റ്റർ</h5>
<form method="post"><?=csrf_field()?>
<input class="form-control mb-2" name="name" placeholder="Name / പേര്" required>
<input class="form-control mb-2" name="mobile" placeholder="Mobile (10 digits)" inputmode="numeric" maxlength="10" required>
<input class="form-control mb-2" type="password" name="password" placeholder="Password (min 6)" required>
<button class="btn btn-primary w-100">Sign up</button></form>
<a class="d-block mt-3 text-center" href="index.php">Back to login</a></div>
<?php foot();
