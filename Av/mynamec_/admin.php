<?php
require_once __DIR__.'/includes/config.php';
require_once __DIR__.'/includes/whatsapp_otp.php';
requireAdmin();
$user=currentUser();$pageTitle='Admin — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$tab=isset($_GET['tab'])?$_GET['tab']:'pending';$msg='';
$roles=array('president'=>'President','vice_president'=>'VP','secretary'=>'Secretary','developer'=>'Developer','joint_secretary'=>'Joint Secretary','treasurer'=>'Treasurer','sports_committee'=>'Sports Committee','cultural_committee'=>'Cultural Committee','finance_committee'=>'Finance Committee','committee_member'=>'Committee Member','member'=>'Member');
$coms=array('Executive Committee','Sports Committee','Cultural Committee','Finance Committee','Charity Committee','Youth Committee','Women Committee');

if($_SERVER['REQUEST_METHOD']==='POST'){
    if(isset($_POST['approve'])){
        $appId = (int)$_POST['mid'];
        db()->prepare("UPDATE users SET status='active',approved_by=?,approved_at=NOW() WHERE id=?")->execute(array($user['id'],$appId));
        // Build WhatsApp welcome message link
        $appMember = db()->prepare("SELECT name,whatsapp_number FROM users WHERE id=?"); $appMember->execute(array($appId)); $appMember=$appMember->fetch();
        $waApproveUrl = null;
        if ($appMember && $appMember['whatsapp_number']) {
            $waApproveUrl = makeWaLink($appMember['whatsapp_number'], memberApprovedMessage($appMember['name']));
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
.adm-shell{background:#F3F6F5;min-height:100vh}

/* Top header card */
.adm-header{
  background:linear-gradient(135deg,#10201F 0%,#0E2A31 60%,#0F766E 100%);
  padding:1.4rem 1.2rem 1rem;
  position:relative;overflow:hidden;
}
.adm-header::before{content:'🛡';position:absolute;right:-.5rem;top:-.5rem;font-size:7rem;opacity:.07;transform:rotate(15deg)}
.adm-hrow{display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem}
.adm-hname{font-family:'Bebas Neue',sans-serif;font-size:.85rem;letter-spacing:.12em;color:rgba(255,255,255,.55)}
.adm-hrole{font-size:.72rem;color:rgba(255,255,255,.4);margin-top:.1rem}
.adm-havatar{width:40px;height:40px;border-radius:50%;border:2.5px solid rgba(200,146,42,.6);object-fit:cover;background:#0E2A31;display:flex;align-items:center;justify-content:center;font-size:1.1rem;overflow:hidden}

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
.adm-stat-n{font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:#f5d060;line-height:1}
.adm-stat-l{font-size:.55rem;text-transform:uppercase;letter-spacing:.09em;color:rgba(255,255,255,.5);font-weight:700;margin-top:.12rem}

/* Nav grid */
.adm-nav{
  background:#fff;
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:0;
  border-bottom:1px solid #E2E8E7;
  position:sticky;top:60px;z-index:90;
  box-shadow:0 3px 14px rgba(0,0,0,.09);
  padding:.6rem .7rem;
  gap:.45rem;
}
.adm-tab{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:.18rem;padding:.55rem .25rem;
  border-radius:14px;
  background:#f8fafc;
  border:1.5px solid #e8eef8;
  color:#475569;
  font-size:.58rem;font-weight:800;
  font-family:'Plus Jakarta Sans',sans-serif;
  text-decoration:none;
  text-align:center;
  transition:all .2s;
  position:relative;
  line-height:1.2;
  letter-spacing:.01em;
}
.adm-tab-em{font-size:1.3rem;line-height:1;display:block;margin-bottom:.05rem}
.adm-tab:active{transform:scale(.93)}
.adm-tab.on{
  background:linear-gradient(145deg,#0F766E,#107D74);
  color:#fff;
  border-color:transparent;
  box-shadow:0 4px 16px rgba(15,118,110,.35);
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
.adm-head{display:flex;align-items:center;gap:.7rem;margin:1rem 0 .9rem;padding-bottom:.55rem;border-bottom:2px solid #E2E8E7}
.adm-head h2{font-family:'Bebas Neue',sans-serif;font-size:1.25rem;letter-spacing:.06em;color:#10201F}
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
    <span class="adm-tab-em">⏳</span>Pending
    <?php if(count($pending)>0): ?><span class="adm-badge"><?=count($pending)?></span><?php endif; ?>
  </a>
  <a href="<?=url('admin.php')?>?tab=members" class="adm-tab <?=$tab==='members'?'on':''?>">
    <span class="adm-tab-em">👥</span>Members
  </a>
  <a href="<?=url('admin.php')?>?tab=add" class="adm-tab <?=$tab==='add'?'on':''?>">
    <span class="adm-tab-em">➕</span>Add Member
  </a>
  <a href="<?=url('admin.php')?>?tab=anns" class="adm-tab <?=$tab==='anns'?'on':''?>">
    <span class="adm-tab-em">📢</span>Announce
  </a>
  <a href="<?=url('admin.php')?>?tab=events" class="adm-tab <?=$tab==='events'?'on':''?>">
    <span class="adm-tab-em">📅</span>Events
  </a>
  <a href="<?=url('admin.php')?>?tab=reports" class="adm-tab <?=$tab==='reports'?'on':''?>">
    <span class="adm-tab-em">📊</span>Reports
  </a>
  <a href="<?=url('modules/admin_subscriptions.php')?>" class="adm-tab">
    <span class="adm-tab-em">💳</span>Subs
  </a>
  <?php if(isSuperAdmin($user)): ?>
  <a href="<?=url('modules/settings.php')?>" class="adm-tab">
    <span class="adm-tab-em">⚙️</span>Settings
  </a>
  <?php endif; ?>
  <a href="<?=url('dashboard.php')?>" class="adm-tab">
    <span class="adm-tab-em">🏠</span>Dashboard
  </a>
  <a href="<?=url('modules/blood.php')?>" class="adm-tab green">
    <span class="adm-tab-em">🩸</span>Blood Hub
  </a>
  <a href="<?=url('modules/certificate.php')?>" class="adm-tab">
    <span class="adm-tab-em">🏆</span>Achieve
  </a>
  <a href="<?=url('logout.php')?>" class="adm-tab red">
    <span class="adm-tab-em">🚪</span>Logout
  </a>
</div>

<div class="adm-wrap">
<?php if($msg): ?>
<div style="background:<?=$msg['t']==='ok'?'#f0fdf4':'#fff0f0'?>;border:1.5px solid <?=$msg['t']==='ok'?'#bbf7d0':'#fecaca'?>;color:<?=$msg['t']==='ok'?'#166534':'#991b1b'?>;border-radius:12px;padding:.85rem 1rem;margin-bottom:1rem;font-weight:600;font-size:.88rem;display:flex;align-items:center;flex-wrap:wrap;gap:.75rem">
  <span><?= h($msg['m']) ?></span>
  <?php if(!empty($msg['wa'])): ?>
  <a href="<?= h($msg['wa']) ?>" target="_blank"
    style="display:inline-flex;align-items:center;gap:.4rem;background:#25d366;color:#fff;border-radius:10px;padding:.45rem 1.1rem;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.82rem;text-decoration:none;box-shadow:0 3px 12px rgba(37,211,102,.4);flex-shrink:0">
    <i class="fab fa-whatsapp"></i>
    📲 Send WhatsApp to <?= h($msg['waname'] ?? '') ?>
  </a>
  <span style="font-size:.72rem;opacity:.65">(Tap → WhatsApp opens → press Send)</span>
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
.mcard:hover{box-shadow:0 4px 18px rgba(15,118,110,.14);transform:translateY(-1px)}
.mcard-num{width:24px;font-size:.72rem;font-weight:700;color:#5d6b80;flex-shrink:0;text-align:center}
.mcard-photo{width:44px;height:44px;border-radius:50%;object-fit:cover;flex-shrink:0;background:#E6F4F2;display:flex;align-items:center;justify-content:center;font-size:1.2rem;border:2px solid #E0F2EF}
.mcard-photo img{width:44px;height:44px;border-radius:50%;object-fit:cover}
.mcard-info{flex:1;min-width:0}
.mcard-name{font-weight:800;font-size:.92rem;color:#0F766E;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-decoration:none;display:block}
.mcard-name:hover{color:#107D74}
.mcard-meta{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;margin-top:.2rem}
.mcard-blood{font-size:.72rem;font-weight:800;color:#b71c1c}
.mcard-role{font-size:.65rem;font-weight:700;padding:.1rem .45rem;border-radius:20px;background:#E6F4F2;color:#0F766E}
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
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem"><h3 style="color:#0F766E">✏️ Edit Member</h3><button onclick="document.getElementById('em').style.display='none'" style="background:none;border:none;font-size:1.3rem;cursor:pointer">✕</button></div>
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
    <div class="fg"><label class="lbl">Name *</label><input type="text" name="name" class="inp" required></div>
    <div class="fg"><label class="lbl">WhatsApp *</label><input type="tel" name="phone" class="inp" required placeholder="+91…"></div>
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
  <div class="card"><div class="card-header"><h3>🩸 Blood Groups</h3></div><div class="card-body"><?php foreach($bgC as $b):?><div style="display:flex;justify-content:space-between;padding:.38rem 0;border-bottom:1px solid #E2E8E7"><strong style="color:#B71C1C"><?=h($b['blood_group'])?></strong><span><?=$b['c']?></span></div><?php endforeach;?></div></div>
  <div class="card"><div class="card-header"><h3>🏛 Committees</h3></div><div class="card-body"><?php foreach($comC as $c):?><div style="display:flex;justify-content:space-between;padding:.38rem 0;border-bottom:1px solid #E2E8E7"><span style="font-size:.83rem"><?=h($c['committee_name'])?></span><strong style="color:#0F766E"><?=$c['c']?></strong></div><?php endforeach;?></div></div>
</div>
<?php endif;?>
</main></div>
<script>
function ft(){var q=document.getElementById('ms').value.toLowerCase(),r=document.getElementById('mr').value,s=document.getElementById('mst').value;document.querySelectorAll('#mcards .mcard').forEach(function(row){var ok=(!q||row.dataset.n.indexOf(q)!==-1||row.dataset.p.indexOf(q)!==-1)&&(!r||row.dataset.r===r)&&(!s||row.dataset.s===s);row.style.display=ok?'flex':'none';});}
function oe(m){document.getElementById('ei').value=m.id;document.getElementById('er').value=m.role;document.getElementById('eb').value=m.blood_group||'';document.getElementById('ep').value=m.committee_position||'';document.getElementById('ec').value=m.committee_name||'';document.getElementById('es').value=m.skill||'';document.getElementById('est').value=m.status;document.getElementById('em').style.display='flex';}
document.getElementById('em')&&document.getElementById('em').addEventListener('click',function(e){if(e.target===this)this.style.display='none';});
</script></div></div>
<?php require_once __DIR__.'/includes/footer.php';?>
