<?php
require_once __DIR__.'/includes/config.php';
require_once __DIR__.'/includes/whatsapp_otp.php';
require_once __DIR__.'/includes/wa_gateway.php';
requireAdmin();
$user=currentUser();$pageTitle='Admin — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$tab=isset($_GET['tab'])?$_GET['tab']:'pending';$msg='';
$roles=array('president'=>'President','vice_president'=>'VP','secretary'=>'Secretary','developer'=>'Developer','joint_secretary'=>'Joint Secretary','treasurer'=>'Treasurer','sports_committee'=>'Sports Committee','cultural_committee'=>'Cultural Committee','finance_committee'=>'Finance Committee','committee_member'=>'Committee Member','member'=>'Member');
$coms=array('Executive Committee','Sports Committee','Cultural Committee','Finance Committee','Charity Committee','Youth Committee','Women Committee');

// ════════ LOGIN HELP (reset passkey by phone number) ════════
try { db()->exec("CREATE TABLE IF NOT EXISTS login_resets(id INT AUTO_INCREMENT PRIMARY KEY,user_id INT NOT NULL,admin_id INT NOT NULL,action VARCHAR(30) NOT NULL,note VARCHAR(200),created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,INDEX(user_id))"); } catch(Exception $e){}
function lh_find_by_phone($raw) {
    $d = substr(preg_replace('/\D/', '', (string)$raw), -10);
    if (strlen($d) < 10) return null;
    $st = db()->prepare("SELECT * FROM users WHERE whatsapp_number LIKE ?"); $st->execute(array('%' . $d));
    foreach ($st->fetchAll() as $u) { if (substr(preg_replace('/\D/', '', $u['whatsapp_number']), -10) === $d) return $u; }
    return null;
}
function lh_log($uid, $adminId, $action, $note = '') {
    try { db()->prepare("INSERT INTO login_resets(user_id,admin_id,action,note) VALUES(?,?,?,?)")->execute(array($uid, $adminId, $action, mb_substr($note, 0, 200))); } catch(Exception $e){}
}
if ($_SERVER['REQUEST_METHOD']==='POST' && !empty($_POST['lh_act'])) {
    $tab = 'login';
    $lhId = (int)($_POST['uid'] ?? 0);
    $st = db()->prepare("SELECT * FROM users WHERE id=?"); $st->execute(array($lhId)); $lhU = $st->fetch();
    if (!verifyCsrf()) {
        $msg = array('t'=>'err','m'=>'Session expired — please try again.');
    } elseif (!$lhU) {
        $msg = array('t'=>'err','m'=>'Member not found.');
    } elseif ($lhU['role'] === 'developer' && !isSuperAdmin($user)) {
        $msg = array('t'=>'err','m'=>'Only the developer can change the developer account.');
    } else {
        $club = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
        $site = rtrim(defined('SITE_URL') ? SITE_URL : '', '/');
        switch ($_POST['lh_act']) {
          case 'set_passkey':
            $pk = preg_replace('/\D/', '', $_POST['new_passkey'] ?? '');
            if ($pk === '') $pk = str_pad((string)random_int(0, 999999), 6, '0', STR_PAD_LEFT);
            if (strlen($pk) !== 6) { $msg = array('t'=>'err','m'=>'The passkey must be exactly 6 digits.'); break; }
            if (preg_match('/^(\d)\1{5}$/', $pk) || in_array($pk, array('123456','654321','012345'), true)) { $msg = array('t'=>'err','m'=>'That passkey is too easy to guess. Choose another or leave it empty to generate one.'); break; }
            db()->prepare('UPDATE users SET passkey=?,passkey_set=1 WHERE id=?')->execute(array(password_hash($pk, PASSWORD_DEFAULT), $lhU['id']));
            lh_log($lhU['id'], $user['id'], 'set_passkey');
            $waText = "🔐 *{$club}*\n\nHello {$lhU['name']}, your login passkey was reset by the club admin.\n\nLogin phone: {$lhU['whatsapp_number']}\nNew passkey: *{$pk}*\n\nLog in at {$site} and change it in My Profile → Passkey. Do not share it with anyone.";
            $msg = array('t'=>'ok','m'=>'New passkey for '.$lhU['name'].': '.$pk.' — send it to the member now. It will not be shown again.',
                         'wa'=>makeWaLink($lhU['whatsapp_number'], $waText), 'waname'=>$lhU['name'], 'pk'=>$pk);
            break;
          case 'clear_passkey':
            db()->prepare('UPDATE users SET passkey=NULL,passkey_set=0 WHERE id=?')->execute(array($lhU['id']));
            lh_log($lhU['id'], $user['id'], 'clear_passkey');
            $waText = "🔐 *{$club}*\n\nHello {$lhU['name']}, your login passkey was cleared by the club admin.\nOpen {$site}, enter your phone number and create a new 6-digit passkey.";
            $msg = array('t'=>'ok','m'=>'Passkey cleared. '.$lhU['name'].' will create a new one at the next login.','wa'=>makeWaLink($lhU['whatsapp_number'], $waText),'waname'=>$lhU['name']);
            break;
          case 'clear_bio':
            $n = 0;
            try { $d = db()->prepare("DELETE FROM webauthn_credentials WHERE user_id=?"); $d->execute(array($lhU['id'])); $n = $d->rowCount(); } catch(Exception $e){}
            lh_log($lhU['id'], $user['id'], 'clear_bio', $n.' device(s)');
            $msg = array('t'=>'ok','m'=>'Removed '.$n.' fingerprint / Face ID login'.($n===1?'':'s').' for '.$lhU['name'].'.');
            break;
          case 'change_phone':
            $np = preg_replace('/\D/', '', $_POST['new_phone'] ?? '');
            if (strlen($np) === 10) $np = '91' . $np;
            if (strlen($np) < 11 || strlen($np) > 15) { $msg = array('t'=>'err','m'=>'Enter a valid mobile number.'); break; }
            $np = '+' . $np;
            $other = lh_find_by_phone($np);
            if ($other && (int)$other['id'] !== (int)$lhU['id']) { $msg = array('t'=>'err','m'=>'That number already belongs to '.$other['name'].'.'); break; }
            db()->prepare('UPDATE users SET whatsapp_number=? WHERE id=?')->execute(array($np, $lhU['id']));
            lh_log($lhU['id'], $user['id'], 'change_phone', $lhU['whatsapp_number'].' → '.$np);
            $msg = array('t'=>'ok','m'=>'Login phone for '.$lhU['name'].' changed to '.$np.'.');
            break;
          case 'activate':
            db()->prepare("UPDATE users SET status='active' WHERE id=?")->execute(array($lhU['id']));
            lh_log($lhU['id'], $user['id'], 'activate', 'was '.$lhU['status']);
            $msg = array('t'=>'ok','m'=>$lhU['name'].' can log in again (account active).');
            break;
          default:
            $msg = array('t'=>'err','m'=>'Unknown action.');
        }
    }
    $_GET['uid'] = $lhId;
}
if($_SERVER['REQUEST_METHOD']==='POST' && empty($_POST['lh_act'])){
    if(isset($_POST['approve'])){
        $appId = (int)$_POST['mid'];
        db()->prepare("UPDATE users SET status='active',approved_by=?,approved_at=NOW() WHERE id=?")->execute(array($user['id'],$appId));
        // Build WhatsApp welcome message link
        $appMember = db()->prepare("SELECT name,whatsapp_number FROM users WHERE id=?"); $appMember->execute(array($appId)); $appMember=$appMember->fetch();
        $waApproveUrl = null;
        if ($appMember && $appMember['whatsapp_number']) {
            $waApproveUrl = makeWaLink($appMember['whatsapp_number'], memberApprovedMessage($appMember['name']));
            if (wa_feature_on('approve') && wa_queue($appMember['whatsapp_number'], memberApprovedMessage($appMember['name']), 'approve')) $waApproveUrl = null; // sent automatically
        }
        $msg=array('t'=>'ok','m'=>'✅ Approved! '.$appMember['name'].' is now an active member.','wa'=>$waApproveUrl,'waname'=>$appMember['name']??'');
    }
    if(isset($_POST['reject'])){
        $rejId = (int)$_POST['mid'];
        $rejReason = trim(isset($_POST['reason'])?$_POST['reason']:'Not approved at this time.');
        db()->prepare("UPDATE users SET status='rejected',rejection_reason=? WHERE id=?")->execute(array($rejReason,$rejId));
        $rejMember = db()->prepare("SELECT name,whatsapp_number FROM users WHERE id=?"); $rejMember->execute(array($rejId)); $rejMember=$rejMember->fetch();
        $waRejectUrl = null;
        if ($rejMember && $rejMember['whatsapp_number']) {
            $waRejectUrl = makeWaLink($rejMember['whatsapp_number'], memberRejectedMessage($rejMember['name'],$rejReason));
        }
        $msg=array('t'=>'ok','m'=>'Application rejected.','wa'=>$waRejectUrl,'waname'=>$rejMember['name']??'','reject'=>true);
    }
    if(isset($_POST['upd'])){
        $editId=(int)$_POST['mid'];
        $curRoleQ=db()->prepare("SELECT role FROM users WHERE id=?");$curRoleQ->execute([$editId]);$curRole=$curRoleQ->fetchColumn();
        $newRole=$_POST['role'];
        // Locked Developer role cannot be changed; and Developer cannot be assigned from the panel
        if(isLockedRole($curRole)) $newRole=$curRole;
        if($newRole==='developer' && $curRole!=='developer') $newRole=$curRole;
        db()->prepare("UPDATE users SET role=?,committee_position=?,committee_name=?,blood_group=?,skill=?,status=? WHERE id=?")->execute(array($newRole,$_POST['cp'],$_POST['cn'],$_POST['bg'],$_POST['sk'],$_POST['st'],$editId));$msg=array('t'=>'ok','m'=>'✅ Updated!');
    }
    if(isset($_POST['deact'])){$id=(int)$_POST['mid'];if($id!==$user['id'])db()->prepare("UPDATE users SET status='inactive' WHERE id=?")->execute(array($id));$msg=array('t'=>'ok','m'=>'Deactivated.');}
    if(isset($_POST['addm'])){
        $p=normalisePhone(isset($_POST['phone'])?$_POST['phone']:'');
        $t=isset($_POST['st2'])?$_POST['st2']:'monthly';
        try{db()->prepare("INSERT INTO users(name,whatsapp_number,blood_group,role,committee_position,committee_name,skill,profession,status,subscription_type,subscription_date,subscription_expiry)VALUES(?,?,?,?,?,?,?,?,?,?,?,?)")
           ->execute(array(trim($_POST['name']),$p,isset($_POST['bg'])?$_POST['bg']:'',isset($_POST['role'])?$_POST['role']:'member',isset($_POST['cp'])?$_POST['cp']:'',isset($_POST['cn'])?$_POST['cn']:'',isset($_POST['sk'])?$_POST['sk']:'',isset($_POST['prof'])?$_POST['prof']:'','active',$t,date('Y-m-d'),$t==='annual'?date('Y-m-d',strtotime('+1 year')):date('Y-m-d',strtotime('+1 month'))));
        $msg=array('t'=>'ok','m'=>'✅ Member added!');}catch(PDOException $e){$msg=array('t'=>'err','m'=>$e->getMessage());}
    }
    if(isset($_POST['rsub'])){
        $uid=(int)$_POST['su'];$t=$_POST['st'];$paid=$_POST['po'];$amt=$t==='annual'?setting('FEE_ANNUAL',1000):setting('FEE_MONTHLY',100);
        $v=$t==='annual'?date('Y-m-d',strtotime($paid.' +1 year')):date('Y-m-d',strtotime($paid.' +1 month'));
        db()->prepare('INSERT INTO subscriptions(user_id,amount,payment_type,paid_on,valid_until,recorded_by)VALUES(?,?,?,?,?,?)')->execute(array($uid,$amt,$t,$paid,$v,$user['id']));
        db()->prepare('UPDATE users SET subscription_date=?,subscription_expiry=?,subscription_type=? WHERE id=?')->execute(array($paid,$v,$t,$uid));
        $msg=array('t'=>'ok','m'=>'✅ Subscription recorded!');
    }
    if(isset($_POST['adev'])){
        db()->prepare('INSERT INTO events(title,description,event_type,event_date,event_time,location,created_by)VALUES(?,?,?,?,?,?,?)')->execute(array(trim($_POST['et']),trim($_POST['ed']),$_POST['ety'],$_POST['edo'],isset($_POST['eti'])?$_POST['eti']:null,trim($_POST['el']),$user['id']));
        $msg=array('t'=>'ok','m'=>'✅ Event added!');
        if (wa_feature_on('events')) {
            $n = wa_queue_many(db()->query("SELECT whatsapp_number FROM users WHERE status='active' AND whatsapp_number<>''")->fetchAll(), wa_msg_event(array('title'=>trim($_POST['et']),'description'=>trim($_POST['ed']),'event_date'=>$_POST['edo'],'event_time'=>isset($_POST['eti'])?$_POST['eti']:'','location'=>trim(isset($_POST['el'])?$_POST['el']:''))), 'event');
            if ($n) $msg['m'] .= ' WhatsApp announcement queued for '.$n.' members.';
        }
    }
    if(isset($_POST['pann'])){db()->prepare('UPDATE announcements SET is_pinned=? WHERE id=?')->execute(array((int)$_POST['pv'],(int)$_POST['aid']));$msg=array('t'=>'ok','m'=>'Updated.');}
    if(isset($_POST['dann'])){db()->prepare('DELETE FROM announcements WHERE id=?')->execute(array((int)$_POST['aid']));$msg=array('t'=>'ok','m'=>'Deleted.');}
}

$pending=db()->query("SELECT * FROM users WHERE status='pending' ORDER BY created_at DESC")->fetchAll();
$allU=db()->query("SELECT * FROM users ORDER BY FIELD(status,'active','pending','inactive','rejected'),FIELD(role,'president','vice_president','secretary','joint_secretary','treasurer','committee_member','member'),name")->fetchAll();
$events=db()->query("SELECT e.*,u.name creator FROM events e JOIN users u ON u.id=e.created_by ORDER BY e.event_date DESC LIMIT 20")->fetchAll();
$subs=db()->query("SELECT s.*,u.name mn FROM subscriptions s JOIN users u ON u.id=s.user_id ORDER BY s.created_at DESC LIMIT 30")->fetchAll();
$anns=db()->query("SELECT a.*,u.name author FROM announcements a JOIN users u ON u.id=a.posted_by ORDER BY a.is_pinned DESC,a.created_at DESC")->fetchAll();

require_once __DIR__.'/includes/header.php';
?>
<style>
/* ── ADMIN APP SHELL ─────────────────────────────────── */
*{box-sizing:border-box}
.adm-shell{background:#F5F7FF;min-height:100vh}

/* Top header card */
.adm-header{
  background:linear-gradient(135deg,#0B1033 0%,#121A5C 60%,#0A14E0 100%);
  padding:1.4rem 1.2rem 1rem;
  position:relative;overflow:hidden;
}
.adm-header::before{content:'🛡';position:absolute;right:-.5rem;top:-.5rem;font-size:7rem;opacity:.07;transform:rotate(15deg)}
.adm-hrow{display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem}
.adm-hname{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.68rem;letter-spacing:.01em;color:rgba(255,255,255,.55)}
.adm-hrole{font-size:.72rem;color:rgba(255,255,255,.4);margin-top:.1rem}
.adm-havatar{width:40px;height:40px;border-radius:50%;border:2.5px solid rgba(200,146,42,.6);object-fit:cover;background:#121A5C;display:flex;align-items:center;justify-content:center;font-size:1.1rem;overflow:hidden}

/* Stats strip */
.adm-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem;margin-bottom:0;padding:0}
.adm-stat{
  background:rgba(255,255,255,.12);
  border:1px solid rgba(255,255,255,.15);
  border-radius:12px;
  padding:.6rem .4rem;
  text-align:center;
  backdrop-filter:blur(6px);
}
.adm-stat-n{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.28rem;color:#f5d060;line-height:1}
.adm-stat-l{font-size:.55rem;text-transform:uppercase;letter-spacing:.09em;color:rgba(255,255,255,.5);font-weight:700;margin-top:.12rem}

/* Nav grid */
.adm-nav{
  background:#fff;
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:0;
  border-bottom:1px solid #E3E7F5;
  position:sticky;top:60px;z-index:90;
  box-shadow:0 3px 14px rgba(0,0,0,.09);
  padding:.6rem .7rem;
  gap:.45rem;
}
.adm-tab{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:.18rem;padding:.7rem .25rem;min-height:78px;
  border-radius:14px;
  background:#f8fafc;
  border:1.5px solid #e8eef8;
  color:#475569;
  font-size:.68rem;font-weight:800;
  font-family:'Plus Jakarta Sans',sans-serif;
  text-decoration:none;
  text-align:center;
  transition:all .2s;
  position:relative;
  line-height:1.2;
  letter-spacing:.01em;
}
.adm-tab-em{line-height:1;display:block;margin-bottom:.2rem}
.adm-tab-em img{width:36px;height:36px;object-fit:contain;display:block;margin:0 auto;filter:drop-shadow(0 3px 3px rgba(11,16,51,.15))}
.adm-tab:active{transform:scale(.93)}
.adm-tab.on{
  background:linear-gradient(145deg,#0A14E0,#1A23C9);
  color:#fff;
  border-color:transparent;
  box-shadow:0 4px 16px rgba(10,20,224,.35);
}
.adm-tab.on .adm-tab-em{filter:drop-shadow(0 2px 4px rgba(0,0,0,.2))}
.adm-tab.red{background:#fff5f5;border-color:#ffd5d5;color:#c62828}
.adm-tab.red:active{background:#ffebee}
.adm-tab.green{background:#f0fdf4;border-color:#bbf7d0;color:#166534}
.adm-badge{
  position:absolute;top:-.35rem;right:-.35rem;
  background:#e53935;color:#fff;
  border-radius:20px;padding:.06rem .42rem;
  font-size:.56rem;font-weight:900;line-height:1.5;
  border:2px solid #fff;
  box-shadow:0 2px 6px rgba(229,57,53,.4);
}

/* Content wrap */
.adm-wrap{max-width:960px;margin:0 auto;padding:.9rem 1rem 5rem}

/* Section head */
.adm-head{display:flex;align-items:center;gap:.7rem;margin:1rem 0 .9rem;padding-bottom:.55rem;border-bottom:2px solid #E3E7F5}
.adm-head h2{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.0rem;letter-spacing:.01em;color:#0B1033}
.adm-head-line{flex:1;height:2px;background:linear-gradient(90deg,#c8922a 0%,transparent 100%)}
</style>

<div class="adm-shell">
<!-- ── Admin Header ── -->
<div class="adm-header">
  <div class="adm-hrow">
    <div>
      <div class="adm-hname"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></div>
      <div class="adm-hrole">🛡 Admin Panel · <?= h(ucwords(str_replace('_',' ',$user['role']))) ?></div>
    </div>
    <?php $ap = getMemberPhoto($user['profile_photo'] ?? ''); ?>
    <div class="adm-havatar">
      <?php if($ap): ?><img src="<?=$ap?>" style="width:100%;height:100%;object-fit:cover"><?php else: ?>👤<?php endif; ?>
    </div>
  </div>

  <!-- Stats -->
  <?php $totals = db()->query("SELECT COUNT(*) t,SUM(status='active') a,SUM(status='pending') p,SUM(status='inactive') i FROM users")->fetch(); ?>
  <div class="adm-stats">
    <div class="adm-stat">
      <div class="adm-stat-n"><?=$totals['t']?></div>
      <div class="adm-stat-l">Total</div>
    </div>
    <div class="adm-stat">
      <div class="adm-stat-n" style="color:#a5d6a7"><?=$totals['a']?></div>
      <div class="adm-stat-l">Active</div>
    </div>
    <div class="adm-stat">
      <div class="adm-stat-n" style="color:#ffcc80"><?=$totals['p']?></div>
      <div class="adm-stat-l">Pending</div>
    </div>
    <div class="adm-stat">
      <div class="adm-stat-n" style="color:#ef9a9a"><?=$totals['i']?></div>
      <div class="adm-stat-l">Inactive</div>
    </div>
  </div>
</div>
<div class="red-bar"></div>

<!-- ── Nav Grid ── -->
<div class="adm-nav">
  <a href="<?=url('admin.php')?>?tab=pending" class="adm-tab <?=$tab==='pending'?'on':''?>">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/pending.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Pending
    <?php if(count($pending)>0): ?><span class="adm-badge"><?=count($pending)?></span><?php endif; ?>
  </a>
  <a href="<?=url('admin.php')?>?tab=members" class="adm-tab <?=$tab==='members'?'on':''?>">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/members.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Members
  </a>
  <a href="<?=url('admin.php')?>?tab=add" class="adm-tab <?=$tab==='add'?'on':''?>">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/add.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Add Member
  </a>
  <a href="<?=url('admin.php')?>?tab=anns" class="adm-tab <?=$tab==='anns'?'on':''?>">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/broadcast.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Announce
  </a>
  <a href="<?=url('admin.php')?>?tab=events" class="adm-tab <?=$tab==='events'?'on':''?>">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/events.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Events
  </a>
  <a href="<?=url('admin.php')?>?tab=login" class="adm-tab <?=$tab==='login'?'on':''?>">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/idcard.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Login Help
  </a>
  <a href="<?=url('admin.php')?>?tab=reports" class="adm-tab <?=$tab==='reports'?'on':''?>">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/reports.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Reports
  </a>
  <a href="<?=url('modules/admin_subscription.php')?>" class="adm-tab">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/payments.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Subs
  </a>
  <?php if(isSuperAdmin($user)): ?>
  <a href="<?=url('modules/settings.php')?>" class="adm-tab">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/settings.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Settings
  </a>
  <?php endif; ?>
  <a href="<?=url('dashboard.php')?>" class="adm-tab">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/home.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Dashboard
  </a>
  <a href="<?=url('modules/blood.php')?>" class="adm-tab green">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/blood.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Blood Hub
  </a>
  <a href="<?=url('modules/certificate.php')?>" class="adm-tab">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/trophy.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Achieve
  </a>
  <a href="<?=url('logout.php')?>" class="adm-tab red">
    <span class="adm-tab-em"><img src="<?=url('assets/icons/3d/logout.webp')?>" alt="" width="36" height="36" loading="lazy"></span>Logout
  </a>
</div>

<div class="adm-wrap">
<?php if($msg): ?>
<div style="background:<?=$msg['t']==='ok'?'#f0fdf4':'#fff0f0'?>;border:1.5px solid <?=$msg['t']==='ok'?'#bbf7d0':'#fecaca'?>;color:<?=$msg['t']==='ok'?'#166534':'#991b1b'?>;border-radius:12px;padding:.85rem 1rem;margin-bottom:1rem;font-weight:600;font-size:.88rem;display:flex;align-items:center;flex-wrap:wrap;gap:.75rem">
  <span><?= h($msg['m']) ?></span>
  <?php if(!empty($msg['wa'])): ?>
  <a href="<?= h($msg['wa']) ?>" target="_blank"
    style="display:inline-flex;align-items:center;gap:.4rem;background:#0E7A3E;color:#fff;border-radius:10px;padding:.45rem 1.1rem;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.82rem;text-decoration:none;box-shadow:0 3px 12px rgba(37,211,102,.4);flex-shrink:0">
    <i class="fab fa-whatsapp"></i>
    📲 Send WhatsApp to <?= h($msg['waname'] ?? '') ?>
  </a>
  <span style="font-size:.76rem;opacity:.85">(Tap → WhatsApp opens → press Send)</span>
  <?php endif; ?>
</div>
<?php endif; ?>

<?php if($tab==='pending'):?>
<div class="adm-head"><h2>⏳ Pending Approvals</h2><div class="adm-head-line"></div></div>
<?php if(empty($pending)):?><div class="alert alert-ok">✅ No pending applications!</div>
<?php else:?><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1rem">
<?php foreach($pending as $p):?>
<div class="card">
  <div class="card-header" style="background:linear-gradient(135deg,#E65100,#BF360C)"><h3><span class="pending-dot"></span> <?=h($p['name'])?></h3></div>
  <div class="card-body">
    <div style="font-size:.82rem;margin-bottom:.8rem;display:grid;grid-template-columns:1fr 1fr;gap:.3rem">
      <div>📱 <?=h($p['whatsapp_number'])?></div><div>🩸 <?=h(isset($p['blood_group'])?$p['blood_group']:'—')?></div>
      <div>💼 <?=h(isset($p['skill'])?$p['skill']:'—')?></div><div>📅 <?=date('d M',strtotime($p['created_at']))?></div>
    </div>
    <div style="display:flex;gap:.5rem">
      <form method="POST" action="<?=url('admin.php')?>?tab=pending" style="flex:1"><input type="hidden" name="mid" value="<?=$p['id']?>"><button type="submit" name="approve" class="btn btn-green btn-sm btn-block">✅ Approve</button></form>
      <form method="POST" action="<?=url('admin.php')?>?tab=pending" style="flex:1" onsubmit="return confirm('Reject?')"><input type="hidden" name="mid" value="<?=$p['id']?>"><input type="hidden" name="reason" value="Not approved."><button type="submit" name="reject" class="btn btn-red btn-sm btn-block">❌ Reject</button></form>
    </div>
    <a href="<?=waLink($p['whatsapp_number'])?>" target="_blank" class="btn-wa" style="margin-top:.6rem;display:inline-flex;font-size:.76rem">💬 Contact</a>
  </div>
</div>
<?php endforeach;?></div><?php endif;?>

<?php elseif($tab==='members'):?>
<div class="adm-head"><h2>👥 All Members</h2><div class="adm-head-line"></div></div>
<div class="search-row"><input type="text" class="inp" id="ms" placeholder="Search…" oninput="ft()" style="flex:1;min-width:160px"><select class="inp" id="mr" onchange="ft()" style="max-width:155px"><option value="">All Roles</option><?php foreach($roles as $rv=>$rl):?><option value="<?=$rv?>"><?=$rl?></option><?php endforeach;?></select><select class="inp" id="mst" onchange="ft()" style="max-width:130px"><option value="">All Status</option><option value="active">Active</option><option value="pending">Pending</option><option value="inactive">Inactive</option></select></div>
<style>
.mcard{background:#fff;border-radius:14px;padding:.85rem 1rem;margin-bottom:.6rem;box-shadow:0 2px 10px rgba(0,0,0,.07);display:flex;align-items:center;gap:.75rem;transition:all .2s}
.mcard:hover{box-shadow:0 4px 18px rgba(10,20,224,.14);transform:translateY(-1px)}
.mcard-num{width:24px;font-size:.72rem;font-weight:700;color:#5d6b80;flex-shrink:0;text-align:center}
.mcard-photo{width:44px;height:44px;border-radius:50%;object-fit:cover;flex-shrink:0;background:#ECEEFF;display:flex;align-items:center;justify-content:center;font-size:1.2rem;border:2px solid #ECEEFF}
.mcard-photo img{width:44px;height:44px;border-radius:50%;object-fit:cover}
.mcard-info{flex:1;min-width:0}
.mcard-name{font-weight:800;font-size:.92rem;color:#0A14E0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-decoration:none;display:block}
.mcard-name:hover{color:#1A23C9}
.mcard-meta{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;margin-top:.2rem}
.mcard-blood{font-size:.72rem;font-weight:800;color:#b71c1c}
.mcard-role{font-size:.65rem;font-weight:700;padding:.1rem .45rem;border-radius:20px;background:#ECEEFF;color:#0A14E0}
.mcard-status-active{background:#e8f5e9;color:#2e7d32}
.mcard-status-pending{background:#fff8e1;color:#f57f17}
.mcard-status-inactive,.mcard-status-rejected{background:#ffebee;color:#b71c1c}
.mcard-wa{font-size:.7rem;color:#25d366;text-decoration:none;display:flex;align-items:center;gap:.2rem;margin-top:.15rem}
.mcard-pos{font-size:.68rem;color:#64748b;margin-top:.1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mcard-acts{display:flex;gap:.3rem;flex-shrink:0}
#mlist{display:none}
</style>

<div id="mcards">
<?php foreach($allU as $i=>$m):
  $mp = getMemberPhoto($m['profile_photo']??'');
  $statusCls = 'mcard-status-'.($m['status']??'inactive');
?>
<div class="mcard" data-n="<?=h(strtolower($m['name']))?>" data-p="<?=h($m['whatsapp_number'])?>" data-r="<?=h($m['role'])?>" data-s="<?=h($m['status'])?>">
  <div class="mcard-num"><?=$i+1?></div>
  <div class="mcard-photo">
    <?php if($mp): ?><img src="<?=$mp?>" alt=""><?php else: ?>👤<?php endif; ?>
  </div>
  <div class="mcard-info">
    <a href="<?=url('modules/profile.php')?>?id=<?=$m['id']?>" class="mcard-name"><?=h($m['name'])?></a>
    <div class="mcard-meta">
      <span class="mcard-blood"><?=h($m['blood_group']??'—')?></span>
      <span class="mcard-role"><?=h(roleLabel($m['role']))?></span>
      <span class="mcard-role <?=$statusCls?>"><?=h(ucfirst($m['status']??''))?></span>
    </div>
    <?php if(!empty($m['committee_position'])): ?>
    <div class="mcard-pos">📌 <?=h($m['committee_position'])?></div>
    <?php endif; ?>
    <a href="<?=waLink($m['whatsapp_number'])?>" target="_blank" class="mcard-wa">💬 <?=h($m['whatsapp_number'])?></a>
  </div>
  <div class="mcard-acts">
    <button class="btn btn-blue btn-sm" onclick="oe(<?=htmlspecialchars(json_encode($m))?>)" title="Edit">✏️</button>
    <?php if($m['id']!==$user['id']&&$m['status']==='active'):?>
    <form method="POST" action="<?=url('admin.php')?>?tab=members" onsubmit="return confirm('Deactivate?')" style="display:inline"><input type="hidden" name="mid" value="<?=$m['id']?>"><button type="submit" name="deact" class="btn btn-grey btn-sm" title="Deactivate">🚫</button></form>
    <?php endif; ?>
  </div>
</div>
<?php endforeach;?>
</div>
<div id="em" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2000;align-items:center;justify-content:center;padding:1rem">
  <div style="background:#fff;border-radius:14px;padding:1.4rem;max-width:460px;width:100%;max-height:90vh;overflow-y:auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem"><h3 style="color:#0A14E0">✏️ Edit Member</h3><button onclick="document.getElementById('em').style.display='none'" style="background:none;border:none;font-size:1.3rem;cursor:pointer">✕</button></div>
    <form method="POST" action="<?=url('admin.php')?>?tab=members"><input type="hidden" name="mid" id="ei"><input type="hidden" name="upd" value="1">
      <div class="g2">
        <div class="fg"><label class="lbl">Role</label><select name="role" id="er" class="inp"><?php foreach($roles as $rv=>$rl):?><option value="<?=$rv?>"><?=$rl?></option><?php endforeach;?></select></div>
        <div class="fg"><label class="lbl">Blood</label><select name="bg" id="eb" class="inp"><option value="">—</option><?php foreach(array('A+','A-','B+','B-','AB+','AB-','O+','O-') as $bg):?><option value="<?=$bg?>"><?=$bg?></option><?php endforeach;?></select></div>
        <div class="fg"><label class="lbl">Position</label><input type="text" name="cp" id="ep" class="inp" placeholder="e.g. Sports Head"></div>
        <div class="fg"><label class="lbl">Committee</label><select name="cn" id="ec" class="inp"><option value="">—</option><?php foreach($coms as $c):?><option><?=$c?></option><?php endforeach;?></select></div>
        <div class="fg"><label class="lbl">Skill</label><input type="text" name="sk" id="es" class="inp"></div>
        <div class="fg"><label class="lbl">Status</label><select name="st" id="est" class="inp"><option value="active">Active</option><option value="inactive">Inactive</option><option value="pending">Pending</option></select></div>
      </div>
      <button type="submit" class="btn btn-blue btn-block" style="margin-top:.8rem">💾 Save Changes</button>
    </form>
  </div>
</div>

<?php elseif($tab==='add'):?>
<h2 class="section-title">➕ Add Member <div class="title-bar"></div></h2>
<div class="card" style="max-width:560px"><div class="card-body">
<form method="POST" action="<?=url('admin.php')?>?tab=add">
  <div class="g2">
    <div class="fg"><label class="lbl">Name *</label><input type="text" name="name" class="inp" required value="<?= h($_GET['name'] ?? '') ?>"></div>
    <div class="fg"><label class="lbl">WhatsApp *</label><input type="tel" name="phone" class="inp" required placeholder="+91…" value="<?= h($_GET['phone'] ?? '') ?>"></div>
    <div class="fg"><label class="lbl">Blood</label><select name="bg" class="inp"><option value="">—</option><?php foreach(array('A+','A-','B+','B-','AB+','AB-','O+','O-') as $bg):?><option><?=$bg?></option><?php endforeach;?></select></div>
    <div class="fg"><label class="lbl">Role</label><select name="role" class="inp"><?php foreach($roles as $rv=>$rl):?><option value="<?=$rv?>"><?=$rl?></option><?php endforeach;?></select></div>
    <div class="fg"><label class="lbl">Position</label><input type="text" name="cp" class="inp" placeholder="e.g. Sports Head"></div>
    <div class="fg"><label class="lbl">Committee</label><select name="cn" class="inp"><option value="">—</option><?php foreach($coms as $c):?><option><?=$c?></option><?php endforeach;?></select></div>
    <div class="fg"><label class="lbl">Skill</label><input type="text" name="sk" class="inp"></div>
    <div class="fg"><label class="lbl">Profession</label><input type="text" name="prof" class="inp"></div>
    <div class="fg"><label class="lbl">Subscription</label><select name="st2" class="inp"><option value="monthly">Monthly ₹<?=setting('FEE_MONTHLY',100)?></option><option value="annual">Annual ₹<?=setting('FEE_ANNUAL',1000)?></option></select></div>
  </div>
  <button type="submit" name="addm" class="btn btn-blue mt-1">➕ Add Member</button>
</form>
</div></div>

<?php elseif($tab==='anns'):?>
<h2 class="section-title">📢 Announcements <div class="title-bar"></div></h2>
<div class="table-wrap"><table><thead><tr><th>Title</th><th>Category</th><th>Author</th><th>Date</th><th>Pinned</th><th>Actions</th></tr></thead><tbody>
<?php foreach($anns as $a):?><tr>
  <td><strong><?=h($a['title'])?></strong></td><td><?=catIcon($a['category'])?> <?=h(ucfirst($a['category']))?></td>
  <td><?=h($a['author'])?></td><td><?=date('d M Y',strtotime($a['created_at']))?></td><td><?=$a['is_pinned']?'📌':'—'?></td>
  <td><div style="display:flex;gap:.3rem">
    <form method="POST" action="<?=url('admin.php')?>?tab=anns"><input type="hidden" name="aid" value="<?=$a['id']?>"><input type="hidden" name="pv" value="<?=$a['is_pinned']?0:1?>"><button type="submit" name="pann" class="btn btn-blue btn-sm"><?=$a['is_pinned']?'Unpin':'📌'?></button></form>
    <form method="POST" action="<?=url('admin.php')?>?tab=anns" onsubmit="return confirm('Delete?')"><input type="hidden" name="aid" value="<?=$a['id']?>"><button type="submit" name="dann" class="btn btn-red btn-sm">🗑</button></form>
  </div></td>
</tr><?php endforeach;?>
</tbody></table></div>

<?php elseif($tab==='events'):?>
<h2 class="section-title">📅 Events <div class="title-bar"></div></h2>
<div class="card mb-2" style="max-width:560px"><div class="card-header"><h3>➕ Add Event</h3></div><div class="card-body">
<form method="POST" action="<?=url('admin.php')?>?tab=events" class="g2">
  <div class="fg"><label class="lbl">Title *</label><input type="text" name="et" class="inp" required></div>
  <div class="fg"><label class="lbl">Type</label><select name="ety" class="inp"><option value="football">Football</option><option value="cricket">Cricket</option><option value="kabaddi">Kabaddi</option><option value="charity">Charity</option><option value="cultural">Cultural</option><option value="meeting">Meeting</option><option value="other">Other</option></select></div>
  <div class="fg"><label class="lbl">Date *</label><input type="date" name="edo" class="inp" required value="<?=date('Y-m-d')?>"></div>
  <div class="fg"><label class="lbl">Time</label><input type="time" name="eti" class="inp"></div>
  <div class="fg"><label class="lbl">Location</label><input type="text" name="el" class="inp"></div>
  <div class="fg" style="grid-column:1/-1"><label class="lbl">Description</label><textarea name="ed" class="inp" rows="2"></textarea></div>
  <div><button type="submit" name="adev" class="btn btn-blue">➕ Add</button></div>
</form>
</div></div>
<div class="table-wrap"><table><thead><tr><th>Title</th><th>Type</th><th>Date</th><th>Location</th></tr></thead><tbody>
<?php foreach($events as $ev):?><tr><td><strong><?=h($ev['title'])?></strong></td><td><?=h(ucfirst($ev['event_type']))?></td><td><?=date('d M Y',strtotime($ev['event_date']))?></td><td><?=h(isset($ev['location'])?$ev['location']:'—')?></td></tr><?php endforeach;?>
</tbody></table></div>

<?php elseif($tab==='login'):?>
<?php
$lhQ = trim($_GET['q'] ?? '');
$lhSel = null; $lhList = array();
if (!empty($_GET['uid'])) { $st = db()->prepare("SELECT * FROM users WHERE id=?"); $st->execute(array((int)$_GET['uid'])); $lhSel = $st->fetch(); }
elseif ($lhQ !== '') {
    $digits = preg_replace('/\D/', '', $lhQ);
    if (strlen($digits) >= 4) { $st = db()->prepare("SELECT * FROM users WHERE REPLACE(REPLACE(REPLACE(whatsapp_number,'+',''),' ',''),'-','') LIKE ? ORDER BY name LIMIT 10"); $st->execute(array('%' . $digits . '%')); }
    else { $st = db()->prepare("SELECT * FROM users WHERE name LIKE ? ORDER BY name LIMIT 10"); $st->execute(array('%' . $lhQ . '%')); }
    $lhList = $st->fetchAll();
    if (count($lhList) === 1) { $lhSel = $lhList[0]; $lhList = array(); }
}
$lhBio = 0; $lhLog = array();
if ($lhSel) { try { $c = db()->prepare("SELECT COUNT(*) FROM webauthn_credentials WHERE user_id=?"); $c->execute(array($lhSel['id'])); $lhBio = (int)$c->fetchColumn(); } catch(Exception $e){} }
try {
    $lq = "SELECT r.*,u.name uname,a.name aname FROM login_resets r LEFT JOIN users u ON u.id=r.user_id LEFT JOIN users a ON a.id=r.admin_id";
    if ($lhSel) { $st = db()->prepare($lq . " WHERE r.user_id=? ORDER BY r.id DESC LIMIT 8"); $st->execute(array($lhSel['id'])); $lhLog = $st->fetchAll(); }
    else { $lhLog = db()->query($lq . " ORDER BY r.id DESC LIMIT 10")->fetchAll(); }
} catch(Exception $e){}
$lhActNames = array('set_passkey'=>'New passkey set','clear_passkey'=>'Passkey cleared','clear_bio'=>'Fingerprint removed','change_phone'=>'Phone changed','activate'=>'Account activated');
?>
<style>
.lh-card{background:#fff;border:1px solid #E3E7F5;border-radius:18px;padding:1rem 1.1rem;margin-bottom:.8rem;box-shadow:0 1px 2px rgba(11,16,51,.04),0 6px 18px rgba(11,16,51,.06)}
.lh-card h3{font-size:.95rem;font-weight:800;margin-bottom:.25rem;display:flex;align-items:center;gap:.5rem}
.lh-card h3 img{width:30px;height:30px}
.lh-card p{font-size:.84rem;color:#565D82;margin-bottom:.7rem}
.lh-row{display:flex;gap:.5rem;flex-wrap:wrap}
.lh-row .inp{flex:1;min-width:150px}
.lh-who{display:flex;gap:.85rem;align-items:center}
.lh-who img,.lh-who .ph{width:58px;height:58px;border-radius:50%;object-fit:cover;background:#ECEEFF;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.lh-who b{font-size:1.05rem;display:block}
.lh-chips{display:flex;gap:.35rem;flex-wrap:wrap;margin-top:.35rem}
.lh-chip{font-size:.72rem;font-weight:700;padding:.15rem .55rem;border-radius:999px;background:#ECEEFF;color:#070FA8}
.lh-chip.ok{background:#E7F8EE;color:#0E6B37}.lh-chip.bad{background:#FFECEC;color:#B80F0A}
.lh-grid{display:grid;gap:.8rem}
@media(min-width:760px){.lh-grid{grid-template-columns:1fr 1fr}}
.lh-pick{display:flex;align-items:center;justify-content:space-between;gap:.6rem;padding:.7rem .9rem;border:1px solid #E3E7F5;border-radius:14px;margin-bottom:.45rem;background:#fff;color:#0B1033;min-height:52px}
.lh-pick small{color:#565D82}
.lh-pk{font-size:2rem;font-weight:800;letter-spacing:.3em;text-align:center;padding:.6rem;border-radius:14px;background:#F5F7FF;border:1px dashed #A9B0FF;margin:.5rem 0}
.lh-log{font-size:.8rem;color:#3B4266}
.lh-log div{padding:.45rem 0;border-bottom:1px solid #EEF1FA}
</style>
<div class="adm-head"><h2>🔑 Login Help</h2><div class="adm-head-line"></div></div>

<div class="lh-card">
  <h3><img src="<?=url('assets/icons/3d/idcard.webp')?>" alt="" width="30" height="30">Find a member</h3>
  <p>Type the member's phone number (or name) to reset their login.</p>
  <form method="GET" class="lh-row">
    <input type="hidden" name="tab" value="login">
    <input class="inp" type="search" name="q" value="<?=h($lhQ)?>" placeholder="Phone number, e.g. 98765 43210" aria-label="Phone number or name" inputmode="tel" autofocus>
    <button class="btn btn-blue" type="submit">🔍 Find</button>
  </form>
</div>

<?php if(!empty($msg['pk'])): ?>
<div class="lh-card" style="border-color:#A9B0FF">
  <h3>New passkey for <?=h($msg['waname'])?></h3>
  <div class="lh-pk" aria-label="New passkey <?=h(implode(' ', str_split($msg['pk'])))?>"><?=h($msg['pk'])?></div>
  <div class="lh-row">
    <a class="btn btn-green" href="<?=h($msg['wa'])?>" target="_blank" rel="noopener">💬 Send to member on WhatsApp</a>
    <button type="button" class="btn btn-outline" onclick="navigator.clipboard&&navigator.clipboard.writeText('<?=h($msg['pk'])?>');this.textContent='Copied ✓'">📋 Copy passkey</button>
  </div>
  <p style="margin:.6rem 0 0">This passkey is shown only once. The member can change it later in My Profile.</p>
</div>
<?php endif; ?>

<?php if($lhQ !== '' && !$lhSel && empty($lhList)): ?>
<div class="alert alert-warn">No member found for “<?=h($lhQ)?>”.</div>
<?php endif; ?>

<?php foreach($lhList as $m): ?>
<a class="lh-pick" href="<?=url('admin.php')?>?tab=login&amp;uid=<?=(int)$m['id']?>"><span><b><?=h($m['name'])?></b><br><small><?=h($m['whatsapp_number'])?> · <?=h(ucfirst($m['status']))?></small></span><span aria-hidden="true">›</span></a>
<?php endforeach; ?>

<?php if($lhSel): $lhPh = getMemberPhoto($lhSel['profile_photo'] ?? ''); $canEdit = !($lhSel['role']==='developer' && !isSuperAdmin($user)); ?>
<div class="lh-card">
  <div class="lh-who">
    <?php if($lhPh): ?><img src="<?=$lhPh?>" alt=""><?php else: ?><span class="ph"><img src="<?=url('assets/icons/3d/profile.webp')?>" alt="" width="40" height="40" style="width:40px;height:40px"></span><?php endif; ?>
    <div style="min-width:0">
      <b><?=h($lhSel['name'])?></b>
      <span style="font-size:.88rem;color:#3B4266"><?=h($lhSel['whatsapp_number'])?> · <?=h(isset($roles[$lhSel['role']])?$roles[$lhSel['role']]:$lhSel['role'])?></span>
      <div class="lh-chips">
        <span class="lh-chip <?=$lhSel['status']==='active'?'ok':'bad'?>"><?=h(ucfirst($lhSel['status']))?></span>
        <span class="lh-chip <?=!empty($lhSel['passkey_set'])?'ok':'bad'?>"><?=!empty($lhSel['passkey_set'])?'Passkey set':'No passkey'?></span>
        <span class="lh-chip"><?=$lhBio?> fingerprint / Face ID</span>
      </div>
    </div>
  </div>
</div>

<?php if(!$canEdit): ?>
<div class="alert alert-warn">Only the developer can change the developer account.</div>
<?php else: ?>
<div class="lh-grid">
  <form method="POST" class="lh-card">
    <?=csrfField()?><input type="hidden" name="uid" value="<?=(int)$lhSel['id']?>"><input type="hidden" name="lh_act" value="set_passkey">
    <h3><img src="<?=url('assets/icons/3d/admin.webp')?>" alt="" width="30" height="30">Set a new passkey</h3>
    <p>Type 6 digits, or leave empty and we make one. You then send it to the member on WhatsApp.</p>
    <div class="lh-row">
      <input class="inp" name="new_passkey" inputmode="numeric" maxlength="6" pattern="[0-9]{6}" placeholder="Leave empty to generate" aria-label="New 6-digit passkey" autocomplete="off">
      <button class="btn btn-blue" type="submit">Set passkey</button>
    </div>
  </form>

  <form method="POST" class="lh-card" onsubmit="return confirm('Clear the passkey of <?=h(addslashes($lhSel['name']))?>? They will create a new one at the next login.')">
    <?=csrfField()?><input type="hidden" name="uid" value="<?=(int)$lhSel['id']?>"><input type="hidden" name="lh_act" value="clear_passkey">
    <h3><img src="<?=url('assets/icons/3d/pending.webp')?>" alt="" width="30" height="30">Let them choose a new passkey</h3>
    <p>Clears the passkey. At the next login the member enters their phone number and registered name, then picks a new passkey.</p>
    <button class="btn btn-outline" type="submit">Clear passkey</button>
  </form>

  <form method="POST" class="lh-card">
    <?=csrfField()?><input type="hidden" name="uid" value="<?=(int)$lhSel['id']?>"><input type="hidden" name="lh_act" value="change_phone">
    <h3><img src="<?=url('assets/icons/3d/subscription.webp')?>" alt="" width="30" height="30">Change login phone number</h3>
    <p>Use when the member has a new number. They log in with the new number and the same passkey.</p>
    <div class="lh-row">
      <input class="inp" name="new_phone" type="tel" inputmode="tel" placeholder="New mobile number" aria-label="New mobile number" required>
      <button class="btn btn-blue" type="submit">Change number</button>
    </div>
  </form>

  <form method="POST" class="lh-card" onsubmit="return confirm('Remove all fingerprint / Face ID logins of this member?')">
    <?=csrfField()?><input type="hidden" name="uid" value="<?=(int)$lhSel['id']?>"><input type="hidden" name="lh_act" value="clear_bio">
    <h3><img src="<?=url('assets/icons/3d/scan.webp')?>" alt="" width="30" height="30">Remove fingerprint / Face ID</h3>
    <p>For a lost or changed phone. The member can add it again from their new phone.</p>
    <button class="btn btn-outline" type="submit" <?=$lhBio?'':'disabled'?>>Remove <?=$lhBio?> device<?=$lhBio===1?'':'s'?></button>
  </form>

  <?php if($lhSel['status']!=='active'): ?>
  <form method="POST" class="lh-card">
    <?=csrfField()?><input type="hidden" name="uid" value="<?=(int)$lhSel['id']?>"><input type="hidden" name="lh_act" value="activate">
    <h3><img src="<?=url('assets/icons/3d/members.webp')?>" alt="" width="30" height="30">Allow login (activate account)</h3>
    <p>This account is <b><?=h($lhSel['status'])?></b>, so the member cannot log in.</p>
    <button class="btn btn-green" type="submit">Activate account</button>
  </form>
  <?php endif; ?>
</div>
<?php endif; ?>
<?php endif; ?>

<?php if(!empty($lhLog)): ?>
<div class="lh-card lh-log">
  <h3><img src="<?=url('assets/icons/3d/reports.webp')?>" alt="" width="30" height="30"><?= $lhSel ? 'History for this member' : 'Recent login changes' ?></h3>
  <?php foreach($lhLog as $l): ?>
  <div><b><?=h(isset($lhActNames[$l['action']])?$lhActNames[$l['action']]:$l['action'])?></b><?= !$lhSel ? ' · '.h($l['uname']) : '' ?><?= $l['note'] ? ' · '.h($l['note']) : '' ?><br>
    <span style="color:#565D82">by <?=h($l['aname'] ?: 'admin')?> · <?=date('d M Y, h:i a', strtotime($l['created_at']))?></span></div>
  <?php endforeach; ?>
</div>
<?php endif; ?>

<?php elseif($tab==='reports'):?>
<?php
$rev=(float)db()->query("SELECT COALESCE(SUM(amount),0) FROM subscriptions WHERE YEAR(paid_on)=YEAR(CURDATE())")->fetchColumn();
$bgC=db()->query("SELECT blood_group,COUNT(*) c FROM users WHERE status='active' AND blood_group IS NOT NULL GROUP BY blood_group")->fetchAll();
$comC=db()->query("SELECT committee_name,COUNT(*) c FROM users WHERE status='active' AND committee_name IS NOT NULL GROUP BY committee_name")->fetchAll();
$ac=(int)db()->query("SELECT COUNT(*) FROM users WHERE status='active'")->fetchColumn();
$pc=(int)db()->query("SELECT COUNT(*) FROM users WHERE status='pending'")->fetchColumn();
?>
<h2 class="section-title">📊 Reports <div class="title-bar"></div></h2>
<div class="stats-row">
  <div class="stat"><div class="stat-num">₹<?=number_format($rev)?></div><div class="stat-lbl">This Year Revenue</div></div>
  <div class="stat"><div class="stat-num"><?=$ac?></div><div class="stat-lbl">Active</div></div>
  <div class="stat"><div class="stat-num"><?=$pc?></div><div class="stat-lbl">Pending</div></div>
  <div class="stat"><div class="stat-num"><?=count($allU)?></div><div class="stat-lbl">Total</div></div>
</div>
<div class="g2 mt-2">
  <div class="card"><div class="card-header"><h3>🩸 Blood Groups</h3></div><div class="card-body"><?php foreach($bgC as $b):?><div style="display:flex;justify-content:space-between;padding:.38rem 0;border-bottom:1px solid #E3E7F5"><strong style="color:#B71C1C"><?=h($b['blood_group'])?></strong><span><?=$b['c']?></span></div><?php endforeach;?></div></div>
  <div class="card"><div class="card-header"><h3>🏛 Committees</h3></div><div class="card-body"><?php foreach($comC as $c):?><div style="display:flex;justify-content:space-between;padding:.38rem 0;border-bottom:1px solid #E3E7F5"><span style="font-size:.83rem"><?=h($c['committee_name'])?></span><strong style="color:#0A14E0"><?=$c['c']?></strong></div><?php endforeach;?></div></div>
</div>
<?php endif;?>
</main></div>
<script>
function ft(){var q=document.getElementById('ms').value.toLowerCase(),r=document.getElementById('mr').value,s=document.getElementById('mst').value;document.querySelectorAll('#mcards .mcard').forEach(function(row){var ok=(!q||row.dataset.n.indexOf(q)!==-1||row.dataset.p.indexOf(q)!==-1)&&(!r||row.dataset.r===r)&&(!s||row.dataset.s===s);row.style.display=ok?'flex':'none';});}
function oe(m){document.getElementById('ei').value=m.id;document.getElementById('er').value=m.role;document.getElementById('eb').value=m.blood_group||'';document.getElementById('ep').value=m.committee_position||'';document.getElementById('ec').value=m.committee_name||'';document.getElementById('es').value=m.skill||'';document.getElementById('est').value=m.status;document.getElementById('em').style.display='flex';}
document.getElementById('em')&&document.getElementById('em').addEventListener('click',function(e){if(e.target===this)this.style.display='none';});
</script></div></div>
<?php require_once __DIR__.'/includes/footer.php';?>
