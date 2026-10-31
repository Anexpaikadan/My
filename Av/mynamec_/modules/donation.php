<?php
require_once __DIR__ . '/../includes/config.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '🤝 Donations — Aishwarya Arts & Sports Club',
  'desc'  => 'Support our club — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/donation.php',
];
requireLogin();$user=currentUser();$isAdmin=isFinanceAdmin($user['role']);
$pageTitle='Donations — '.CLUB_NAME;

try {
db()->query("CREATE TABLE IF NOT EXISTS donation_campaigns(id INT AUTO_INCREMENT PRIMARY KEY,title VARCHAR(200),description TEXT,goal_amount DECIMAL(10,2) DEFAULT 0,raised_amount DECIMAL(10,2) DEFAULT 0,start_date DATE,end_date DATE,status ENUM('active','completed','paused') DEFAULT 'active',upi_id VARCHAR(100),created_by INT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
db()->query("CREATE TABLE IF NOT EXISTS donations(id INT AUTO_INCREMENT PRIMARY KEY,campaign_id INT,donor_id INT,amount DECIMAL(10,2),payment_method ENUM('cash','upi','bank','other') DEFAULT 'upi',upi_ref VARCHAR(100),message TEXT,status ENUM('pending','verified') DEFAULT 'pending',donated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
} catch(Exception $e){}

$msg='';
if($isAdmin&&isset($_POST['create_campaign'])){
    db()->prepare("INSERT INTO donation_campaigns(title,description,goal_amount,start_date,end_date,upi_id,created_by)VALUES(?,?,?,?,?,?,?)")
       ->execute(array(trim($_POST['ctitle']),trim($_POST['cdesc']??''),(float)$_POST['cgoal'],$_POST['cstart'],$_POST['cend'],trim($_POST['cupi']??''),$user['id']));
    $msg=array('t'=>'ok','m'=>'✅ Campaign created!');
}
if(isset($_POST['donate'])){
    $cid=(int)$_POST['cid'];$amt=(float)$_POST['amount'];$method=$_POST['method']??'upi';$ref=trim($_POST['upi_ref']??'');$note=trim($_POST['message']??'');
    if($amt>=1){
        db()->prepare("INSERT INTO donations(campaign_id,donor_id,amount,payment_method,upi_ref,message)VALUES(?,?,?,?,?,?)")
           ->execute(array($cid,$user['id'],$amt,$method,$ref,$note));
        db()->prepare("UPDATE donation_campaigns SET raised_amount=raised_amount+? WHERE id=?")->execute(array($amt,$cid));
        $msg=array('t'=>'ok','m'=>'✅ Thank you for your donation! Secretary will verify shortly.');
    }
}
if($isAdmin&&isset($_POST['verify_donation'])){
    db()->prepare("UPDATE donations SET status='verified' WHERE id=?")->execute(array((int)$_POST['did']));
    $msg=array('t'=>'ok','m'=>'✅ Donation verified!');
}

$campaigns=db()->query("SELECT * FROM donation_campaigns ORDER BY created_at DESC")->fetchAll();
require_once __DIR__ . '/../includes/header.php';
?>
<div class="hero" style="background:linear-gradient(135deg,#1B5E20,#2E7D32);padding:2rem 1.2rem 1.8rem">
  <h1>❤️ DONATE &amp; <span>SUPPORT</span></h1>
  <div class="hero-place">Help build a better <?= h(CLUB_PLACE) ?> community</div>
</div><div class="red-bar"></div>
<div class="section" style="max-width:900px">
<?php if($msg): ?><div class="alert alert-<?=$msg['t']==='ok'?'ok':'error'?>"><?=$msg['m']?></div><?php endif;?>

<?php if($isAdmin): ?>
<div class="card mb-3">
  <div class="card-header" style="background:linear-gradient(135deg,#1B5E20,#2E7D32)"><h3>➕ Create Donation Campaign</h3></div>
  <div class="card-body">
    <form method="POST" action="<?=url('modules/donation.php')?>">
      <div class="g2">
        <div class="fg"><label class="lbl">Campaign Title *</label><input type="text" name="ctitle" class="inp" required placeholder="e.g. Ground Renovation Fund"></div>
        <div class="fg"><label class="lbl">Goal Amount (₹)</label><input type="number" name="cgoal" class="inp" min="0" step="100" value="10000"></div>
        <div class="fg"><label class="lbl">Start Date</label><input type="date" name="cstart" class="inp" value="<?=date('Y-m-d')?>"></div>
        <div class="fg"><label class="lbl">End Date</label><input type="date" name="cend" class="inp" value="<?=date('Y-m-d',strtotime('+30 days'))?>"></div>
        <div class="fg"><label class="lbl">UPI ID</label><input type="text" name="cupi" class="inp" placeholder="name@upi"></div>
      </div>
      <div class="fg"><label class="lbl">Description</label><textarea name="cdesc" class="inp" rows="2" placeholder="What will donations be used for?"></textarea></div>
      <button type="submit" name="create_campaign" class="btn btn-green">❤️ Create Campaign</button>
    </form>
  </div>
</div>
<?php endif;?>

<?php if(empty($campaigns)): ?>
<div style="text-align:center;padding:4rem;color:var(--t3)"><div style="font-size:4rem">❤️</div><h3 style="margin:.8rem 0 .4rem">No active campaigns</h3><p style="font-size:.85rem">Donation campaigns will appear here.</p></div>
<?php else: foreach($campaigns as $camp):
  $pct=$camp['goal_amount']>0?min(100,round(($camp['raised_amount']/$camp['goal_amount'])*100)):0;
  $donations=db()->prepare("SELECT d.*,u.name dname FROM donations d JOIN users u ON u.id=d.donor_id WHERE d.campaign_id=? ORDER BY d.donated_at DESC");
  $donations->execute(array($camp['id']));$donations=$donations->fetchAll();
  $sbc=array('active'=>array('#E8F5E9','#1B5E20'),'completed'=>array('#E6F4F2','#0A1A1F'),'paused'=>array('#FFF8E1','#E65100'));
  $sc=$sbc[$camp['status']]??array('#F5F5F5','#555');
?>
<div class="card mb-3">
  <div class="card-header" style="background:linear-gradient(135deg,#1B5E20,#2E7D32);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
    <h3>❤️ <?=h($camp['title'])?></h3>
    <span style="background:<?=$sc[0]?>;color:<?=$sc[1]?>;border-radius:20px;padding:.2rem .8rem;font-size:.7rem;font-weight:700"><?=strtoupper($camp['status'])?></span>
  </div>
  <div class="card-body">
    <?php if($camp['description']): ?><p style="font-size:.84rem;color:var(--t2);margin-bottom:1rem"><?=h($camp['description'])?></p><?php endif;?>
    <!-- Progress bar -->
    <div style="background:#E8F5E9;border-radius:12px;padding:1rem;margin-bottom:1.2rem">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
        <div><span style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:#2E7D32">₹<?=number_format($camp['raised_amount'])?></span><span style="font-size:.72rem;color:var(--t3)"> raised of ₹<?=number_format($camp['goal_amount'])?></span></div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:#1B5E20"><?=$pct?>%</div>
      </div>
      <div style="background:#C8E6C9;border-radius:8px;height:10px;overflow:hidden">
        <div style="background:linear-gradient(90deg,#2E7D32,#4CAF50);height:10px;border-radius:8px;width:<?=$pct?>%;transition:width 1s ease"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:.4rem;font-size:.7rem;color:var(--t3)">
        <span><?=count($donations)?> donors</span>
        <span>📅 Ends <?=date('d M Y',strtotime($camp['end_date']))?></span>
      </div>
    </div>

    <!-- Donate form -->
    <?php if($camp['status']==='active'): ?>
    <div style="background:#F6F8F8;border-radius:12px;padding:1.1rem;margin-bottom:1.2rem">
      <h4 style="font-size:.88rem;font-weight:700;color:#1B5E20;margin-bottom:.8rem">💚 Make a Donation</h4>
      <?php if($camp['upi_id']): ?>
      <div style="background:#E8F5E9;border-radius:8px;padding:.6rem .9rem;margin-bottom:.7rem;font-size:.8rem;display:flex;align-items:center;gap:.5rem">
        <span>📱 UPI:</span><strong><?=h($camp['upi_id'])?></strong>
        <span style="color:var(--t3);font-size:.7rem">Pay and enter reference below</span>
      </div>
      <?php endif;?>
      <form method="POST" action="<?=url('modules/donation.php')?>">
        <input type="hidden" name="cid" value="<?=$camp['id']?>">
        <div class="g2">
          <div class="fg"><label class="lbl">Amount (₹) *</label><input type="number" name="amount" class="inp" min="10" step="10" placeholder="e.g. 500" required></div>
          <div class="fg"><label class="lbl">Method</label><select name="method" class="inp"><option value="upi">📱 UPI/GPay</option><option value="cash">💵 Cash</option><option value="bank">🏦 Bank Transfer</option></select></div>
          <div class="fg"><label class="lbl">UPI Ref / Transaction ID</label><input type="text" name="upi_ref" class="inp" placeholder="Optional reference"></div>
          <div class="fg"><label class="lbl">Message</label><input type="text" name="message" class="inp" placeholder="Optional note"></div>
        </div>
        <button type="submit" name="donate" class="btn btn-green">❤️ Donate Now</button>
      </form>
    </div>
    <?php endif;?>

    <!-- Recent donors -->
    <?php if(!empty($donations)): ?>
    <h4 style="font-size:.8rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:.6rem">Recent Donors</h4>
    <?php foreach(array_slice($donations,0,5) as $d): ?>
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.5rem .7rem;background:#F6F8F8;border-radius:8px;margin-bottom:.35rem;font-size:.82rem">
      <div><strong><?=h($d['dname'])?></strong><?php if($d['message']): ?> <span style="color:var(--t3);font-size:.75rem">— <?=h($d['message'])?></span><?php endif;?></div>
      <div style="display:flex;align-items:center;gap:.5rem">
        <strong style="color:#2E7D32">₹<?=number_format($d['amount'])?></strong>
        <?php if($d['status']==='pending'): ?><span style="font-size:.65rem;background:#FFF8E1;color:#E65100;border-radius:20px;padding:.1rem .4rem;font-weight:700">Pending</span><?php else: ?><span style="font-size:.65rem;color:#2E7D32;font-weight:700">✅</span><?php endif;?>
        <?php if($isAdmin&&$d['status']==='pending'): ?>
        <form method="POST" action="<?=url('modules/donation.php')?>" style="display:inline"><input type="hidden" name="did" value="<?=$d['id']?>"><button type="submit" name="verify_donation" class="btn btn-green btn-sm" style="padding:.25rem .5rem;font-size:.68rem">Verify</button></form>
        <?php endif;?>
      </div>
    </div>
    <?php endforeach;?>
    <?php endif;?>
  </div>
</div>
<?php endforeach;endif;?>
</div>
<?php require_once __DIR__ . '/../includes/footer.php';?>
