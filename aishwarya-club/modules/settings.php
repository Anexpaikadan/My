<?php
require_once __DIR__ . '/../includes/config.php';
if(file_exists(__DIR__.'/../includes/whatsapp_otp.php'))
    require_once __DIR__ . '/../includes/whatsapp_otp.php';
require_once __DIR__ . '/../includes/wa_gateway.php';
requireLogin();
$me = currentUser();
if (!canAccessSettings($me)) { header('Location: '.url('dashboard.php').'?err=access'); exit; }

// ════════════ DATABASE BACKUP (.sql download) — Developer only ════════════
if (isset($_GET['export_sql'])) {
    // Build a full SQL dump in pure PHP (mysqldump not available on shared hosting)
    @set_time_limit(300);
    $dbName = defined('DB_NAME') ? DB_NAME : '';
    $fname  = 'backup_'.preg_replace('/[^a-z0-9_]/i','',$dbName).'_'.date('Y-m-d_His').'.sql';
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="'.$fname.'"');
    header('Pragma: no-cache');

    $pdo = db();
    echo "-- ".setting('CLUB_NAME','Club')." database backup\n";
    echo "-- Database: ".$dbName."\n";
    echo "-- Generated: ".date('Y-m-d H:i:s')."\n";
    echo "-- ----------------------------------------------------\n\n";
    echo "SET FOREIGN_KEY_CHECKS=0;\n";
    echo "SET NAMES utf8mb4;\n\n";

    // list all tables
    $tables = $pdo->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN);
    foreach ($tables as $tbl) {
        // structure
        $create = $pdo->query("SHOW CREATE TABLE `$tbl`")->fetch(PDO::FETCH_ASSOC);
        $createSql = $create['Create Table'] ?? ($create['Create View'] ?? '');
        echo "-- ----------------------------\n-- Table: `$tbl`\n-- ----------------------------\n";
        echo "DROP TABLE IF EXISTS `$tbl`;\n";
        echo $createSql.";\n\n";

        // data (in batches to stay light on memory)
        $count = (int)$pdo->query("SELECT COUNT(*) FROM `$tbl`")->fetchColumn();
        if ($count > 0) {
            $cols = $pdo->query("SELECT * FROM `$tbl` LIMIT 1")->fetch(PDO::FETCH_ASSOC);
            $colNames = '`'.implode('`,`', array_keys($cols)).'`';
            $offset = 0; $batch = 200;
            while ($offset < $count) {
                $rows = $pdo->query("SELECT * FROM `$tbl` LIMIT $offset,$batch")->fetchAll(PDO::FETCH_ASSOC);
                foreach ($rows as $row) {
                    $vals = array();
                    foreach ($row as $v) {
                        if ($v === null) $vals[] = 'NULL';
                        else $vals[] = $pdo->quote($v);
                    }
                    echo "INSERT INTO `$tbl` ($colNames) VALUES (".implode(',', $vals).");\n";
                }
                $offset += $batch;
                flush();
            }
            echo "\n";
        }
    }
    echo "SET FOREIGN_KEY_CHECKS=1;\n";
    exit;
}

// ── Create settings table ───────────────────────────────────────
try {
    db()->exec("CREATE TABLE IF NOT EXISTS club_settings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        setting_key   VARCHAR(100) NOT NULL UNIQUE,
        setting_value TEXT,
        setting_group VARCHAR(50) DEFAULT 'general',
        label         VARCHAR(150),
        type          VARCHAR(30) DEFAULT 'text',
        updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )");
} catch(Exception $e){}

// ── Create activities table ─────────────────────────────────────
try {
    db()->exec("CREATE TABLE IF NOT EXISTS club_activities (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name        VARCHAR(150) NOT NULL,
        emoji       VARCHAR(10) DEFAULT '🏆',
        description TEXT,
        reg_link    VARCHAR(500),
        info_url    VARCHAR(500),
        color       VARCHAR(20) DEFAULT '#0A14E0',
        is_active   TINYINT(1) DEFAULT 1,
        sort_order  INT DEFAULT 0,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )");
} catch(Exception $e){}

// ── Helper: get/set setting ──────────────────────────────────────
function getSetting($key, $default='') {
    try {
        $r = db()->prepare("SELECT setting_value FROM club_settings WHERE setting_key=?");
        $r->execute([$key]); $r = $r->fetch();
        return $r ? $r['setting_value'] : $default;
    } catch(Exception $e){ return $default; }
}
function saveSetting($key, $value, $group='general', $label='', $type='text') {
    try {
        db()->prepare("INSERT INTO club_settings(setting_key,setting_value,setting_group,label,type)
            VALUES(?,?,?,?,?) ON DUPLICATE KEY UPDATE setting_value=?, updated_at=NOW()")
           ->execute([$key,$value,$group,$label,$type,$value]);
    } catch(Exception $e){}
}

$msg = null;

// ── Role / Approval AJAX ─────────────────────────────────────────
if(!empty($_POST['action'])){
  header('Content-Type: application/json');
  $act=$_POST['action'];
  if($act==='set_role'){
    $u2=(int)($_POST['uid']??0);$r2=trim($_POST['role']??'');
    $ok=['president','vice_president','secretary','developer','guest_admin','joint_secretary','treasurer','sports_committee','cultural_committee','finance_committee','committee_member','member'];
    if(!$u2||!in_array($r2,$ok)){echo json_encode(['ok'=>false,'msg'=>'Invalid']);exit;}
    // Protect the locked Developer (Super Admin) role — cannot be changed or removed by anyone
    $tgt=db()->prepare("SELECT role FROM users WHERE id=?");$tgt->execute([$u2]);$tgtRole=$tgt->fetchColumn();
    if(isLockedRole($tgtRole)){echo json_encode(['ok'=>false,'msg'=>'🔒 Developer (Super Admin) role is locked and cannot be changed.']);exit;}
    if($r2==='developer'){echo json_encode(['ok'=>false,'msg'=>'The Developer role cannot be assigned from here for security.']);exit;}
    if($u2===(int)$me['id']&&in_array($r2,['member','committee_member'])){echo json_encode(['ok'=>false,'msg'=>'Cannot demote yourself!']);exit;}
    db()->prepare("UPDATE users SET role=? WHERE id=?")->execute([$r2,$u2]);
    echo json_encode(['ok'=>true]);exit;
  }
  if($act==='set_module_admin'){
    $u2=(int)($_POST['uid']??0);$mod=trim($_POST['module']??'');$rem=!empty($_POST['remove']);
    $days=(int)($_POST['expiry_days']??0); // 0 = permanent
    if(!$u2||!$mod){echo json_encode(['ok'=>false,'msg'=>'Missing data']);exit;}
    // Ensure table + column exist (in case it was created by an older version)
    try {
      db()->exec("CREATE TABLE IF NOT EXISTS module_admins(id INT AUTO_INCREMENT PRIMARY KEY,user_id INT NOT NULL,module VARCHAR(80) NOT NULL,added_by INT NOT NULL,expires_at DATETIME DEFAULT NULL,added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE KEY one_mod(user_id,module))");
      try { db()->exec("ALTER TABLE module_admins ADD COLUMN expires_at DATETIME DEFAULT NULL"); } catch(Exception $e){}
    } catch(Exception $e){}
    try {
      if($rem){db()->prepare("DELETE FROM module_admins WHERE user_id=? AND module=?")->execute([$u2,$mod]);}
      else{
        $exp=$days>0?date('Y-m-d H:i:s',strtotime("+{$days} days")):null;
        db()->prepare("INSERT INTO module_admins(user_id,module,added_by,expires_at) VALUES(?,?,?,?)
          ON DUPLICATE KEY UPDATE expires_at=VALUES(expires_at)")->execute([$u2,$mod,(int)$me['id'],$exp]);
      }
      echo json_encode(['ok'=>true]);exit;
    } catch(Exception $e){ echo json_encode(['ok'=>false,'msg'=>'DB: '.$e->getMessage()]);exit; }
  }
  if($act==='approve_user'){
    $u2=(int)($_POST['uid']??0);
    if(!$u2){echo json_encode(['ok'=>false,'msg'=>'Invalid']);exit;}
    db()->prepare("UPDATE users SET status='active',approved_by=?,approved_at=NOW() WHERE id=?")->execute([(int)$me['id'],$u2]);
    // Get member details for WhatsApp notification
    $appMember=db()->prepare("SELECT name,whatsapp_number FROM users WHERE id=?");
    $appMember->execute([$u2]);$appMember=$appMember->fetch();
    $waUrl=null;
    if($appMember && !empty($appMember['whatsapp_number'])){
      $waUrl=makeWaLink($appMember['whatsapp_number'],memberApprovedMessage($appMember['name']));
      if(wa_feature_on('approve') && wa_queue($appMember['whatsapp_number'],memberApprovedMessage($appMember['name']),'approve')) $waUrl=null; // sent automatically
    }
    echo json_encode(['ok'=>true,'name'=>$appMember['name']??'','wa'=>$waUrl]);exit;
  }
  if($act==='reject_user'){
    $u2=(int)($_POST['uid']??0);$reason=trim($_POST['reason']??'');
    if(!$u2){echo json_encode(['ok'=>false,'msg'=>'Invalid']);exit;}
    db()->prepare("UPDATE users SET status='rejected',rejection_reason=? WHERE id=?")->execute([$reason,$u2]);
    // Get member details for WhatsApp notification
    $rejMember=db()->prepare("SELECT name,whatsapp_number FROM users WHERE id=?");
    $rejMember->execute([$u2]);$rejMember=$rejMember->fetch();
    $waUrl=null;
    if($rejMember && !empty($rejMember['whatsapp_number'])){
      $waUrl=makeWaLink($rejMember['whatsapp_number'],memberRejectedMessage($rejMember['name'],$reason));
    }
    echo json_encode(['ok'=>true,'name'=>$rejMember['name']??'','wa'=>$waUrl]);exit;
  }
  if($act==='wa_status'){ list($ok,$m)=wa_status(); echo json_encode(['ok'=>$ok,'msg'=>$m]);exit; }
  if($act==='wa_test'){
    $ph=trim($_POST['phone']??'');
    if(strlen(preg_replace('/\D/','',$ph))<10){ echo json_encode(['ok'=>false,'msg'=>'Enter a WhatsApp number']);exit; }
    list($ok,$m)=wa_send_now($ph,"✅ Test message from ".setting('CLUB_NAME','Aishwarya Arts & Sports Club')." website.\nWhatsApp sending works!",'test');
    echo json_encode(['ok'=>$ok,'msg'=>$ok?'Test message sent — check WhatsApp.':$m]);exit;
  }
  if($act==='wa_run'){ @set_time_limit(150); wa_daily_jobs(); $r=wa_process_queue(10); echo json_encode(['ok'=>true,'msg'=>'Sent '.$r['sent'].', failed '.$r['failed'].', waiting '.wa_queue_pending()]);exit; }
  if($act==='wa_retry'){ try{db()->exec("UPDATE wa_queue SET status='pending',attempts=0 WHERE status='failed'");}catch(Exception $e){} echo json_encode(['ok'=>true,'msg'=>'Failed messages moved back to the queue']);exit; }
  echo json_encode(['ok'=>false,'msg'=>'Unknown']);exit;
}

// ── Handle POST ──────────────────────────────────────────────────
if ($_SERVER['REQUEST_METHOD']==='POST') {
    $act = $_POST['act'] ?? '';

    // Save WhatsApp sending settings
    if ($act === 'save_whatsapp') {
        $prov = in_array($_POST['wa_provider'] ?? 'off', array('off','gowa','meta'), true) ? $_POST['wa_provider'] : 'off';
        saveSetting('wa_provider', $prov, 'whatsapp');
        $url = trim($_POST['wa_gowa_url'] ?? '');
        if ($url !== '' && !preg_match('#^https?://#i', $url)) $url = 'http://' . $url;
        saveSetting('wa_gowa_url', rtrim($url, '/'), 'whatsapp');
        foreach (array('wa_gowa_user','wa_gowa_device','wa_meta_phone_id','wa_meta_tpl_otp','wa_meta_tpl_notice') as $f) saveSetting($f, trim($_POST[$f] ?? ''), 'whatsapp');
        // secrets: an empty box keeps the saved value
        foreach (array('wa_gowa_pass','wa_meta_token') as $f) { $v = trim($_POST[$f] ?? ''); if ($v !== '') saveSetting($f, $v, 'whatsapp'); }
        saveSetting('wa_meta_lang', preg_replace('/[^a-zA-Z_]/', '', $_POST['wa_meta_lang'] ?? 'en') ?: 'en', 'whatsapp');
        saveSetting('wa_country', preg_replace('/\D/', '', $_POST['wa_country'] ?? '91') ?: '91', 'whatsapp');
        saveSetting('wa_delay', (string)max(2, min(30, (int)($_POST['wa_delay'] ?? 4))), 'whatsapp');
        foreach (array('otp','approve','events','blood','fees') as $f) saveSetting('wa_on_'.$f, isset($_POST['wa_on_'.$f]) ? '1' : '0', 'whatsapp');
        if (!empty($_POST['wa_new_key']) || getSetting('wa_cron_key') === '') saveSetting('wa_cron_key', bin2hex(random_bytes(16)), 'whatsapp');
        $msg = ['t'=>'ok','m'=>'WhatsApp settings saved. Use “Check connection” and “Send test message” below.'];
    }

    // Save social media links
    if ($act === 'save_social') {
        $socials = array('social_facebook','social_instagram','social_youtube','social_twitter','social_telegram','social_linkedin','social_tiktok','social_website','social_wa_group');
        foreach ($socials as $sk) {
            $val = trim($_POST[$sk] ?? '');
            if ($val) {
                saveSetting($sk, $val, 'social', $sk, 'url');
            } else {
                try { db()->prepare("DELETE FROM club_settings WHERE setting_key=?")->execute(array($sk)); } catch(Exception $e){}
            }
        }
        $msg = array('t'=>'ok','m'=>'Social media links saved!');
    }

    // Save club info
    if ($act === 'save_club') {
        foreach (array('fee_monthly','fee_annual') as $_ff) {   // fee change → confirm passkey
            if (isset($_POST[$_ff]) && trim($_POST[$_ff]) !== (string)getSetting($_ff, setting(strtoupper($_ff), ''))) { require_once __DIR__ . '/../includes/sudo.php'; sudo_require(); }
        }
        $fields = ['club_name','club_place','club_tagline','club_phone','club_wa_group',
                   'club_wa_number','fee_monthly','fee_annual','hero_title','hero_subtitle'];
        foreach ($fields as $f) {
            if (isset($_POST[$f])) saveSetting($f, trim($_POST[$f]), 'club');
        }
        $msg = ['t'=>'ok','m'=>'Club settings saved!'];
    }

    // Save homepage settings (every field here is used by index.php)
    if ($act === 'save_home') {
        $text = array('hero_badge','hero_title','hero_subtitle','hero_cta_text','home_about_title','home_about_text',
                      'home_join_title','home_join_text','footer_text');
        foreach ($text as $f) { if (isset($_POST[$f])) saveSetting($f, trim($_POST[$f]), 'homepage'); }
        // switches: an unticked box is not sent, so store 0 for it
        foreach (array('home_stats_show','home_about_show','home_activities_show','home_events_show','home_notices_show',
                       'home_committee_show','home_achievements_show','home_gallery_show','home_join_show') as $f) {
            saveSetting($f, isset($_POST[$f]) ? '1' : '0', 'homepage');
        }
        foreach (array('home_primary_color'=>'#0A14E0','home_accent_color'=>'#E30613') as $f=>$def) {
            $v = trim($_POST[$f] ?? '');
            saveSetting($f, preg_match('/^#[0-9a-fA-F]{6}$/', $v) ? $v : $def, 'homepage');
        }
        $font = $_POST['home_font'] ?? '';
        saveSetting('home_font', in_array($font, array('Plus Jakarta Sans','Poppins','Manrope','Outfit'), true) ? $font : 'Plus Jakarta Sans', 'homepage');
        $msg = ['t'=>'ok','m'=>'Homepage settings saved — open the website to see them.'];
    }

    // Save activity
    if ($act === 'save_activity') {
        $id   = (int)($_POST['act_id'] ?? 0);
        $name = trim($_POST['act_name'] ?? '');
        $emoji= trim($_POST['act_emoji'] ?? '🏆');
        $desc = trim($_POST['act_desc'] ?? '');
        $reg  = trim($_POST['act_reg'] ?? '');
        $info = trim($_POST['act_info'] ?? '');
        $col  = trim($_POST['act_color'] ?? '#0A14E0');
        $active = isset($_POST['act_active']) ? 1 : 0;
        if ($name) {
            if ($id) {
                db()->prepare("UPDATE club_activities SET name=?,emoji=?,description=?,reg_link=?,info_url=?,color=?,is_active=? WHERE id=?")
                   ->execute([$name,$emoji,$desc,$reg,$info,$col,$active,$id]);
            } else {
                db()->prepare("INSERT INTO club_activities(name,emoji,description,reg_link,info_url,color,is_active) VALUES(?,?,?,?,?,?,?)")
                   ->execute([$name,$emoji,$desc,$reg,$info,$col,1]);
            }
            $msg = ['t'=>'ok','m'=>'Activity saved!'];
        }
    }

    // Delete activity
    if ($act === 'del_activity' && isset($_POST['act_id'])) { require_once __DIR__ . '/../includes/sudo.php'; sudo_require(); 
        db()->prepare("DELETE FROM club_activities WHERE id=?")->execute([(int)$_POST['act_id']]);
        $msg = ['t'=>'ok','m'=>'Activity deleted.'];
    }

    // Toggle activity
    if ($act === 'toggle_activity' && isset($_POST['act_id'])) {
        db()->prepare("UPDATE club_activities SET is_active=1-is_active WHERE id=?")->execute([(int)$_POST['act_id']]);
        $msg = ['t'=>'ok','m'=>'Activity updated.'];
    }
}

// ── Load current settings ────────────────────────────────────────
$settings = [];
try {
    $rows = db()->query("SELECT setting_key, setting_value FROM club_settings")->fetchAll();
    foreach ($rows as $r) $settings[$r['setting_key']] = $r['setting_value'];
} catch(Exception $e){}

// Defaults from config.php
$s = function($key, $def='') use ($settings) { return $settings[$key] ?? $def; };

$activities = [];
try {
    $activities = db()->query("SELECT * FROM club_activities ORDER BY sort_order,id")->fetchAll();
} catch(Exception $e){}

$pageTitle = 'Settings — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');
// Load data for roles tab
$_allUsers=[];
try{$_allUsers=db()->query("SELECT id,name,role FROM users ORDER BY name")->fetchAll();}catch(Exception $e){}
try{db()->exec("CREATE TABLE IF NOT EXISTS module_admins(id INT AUTO_INCREMENT PRIMARY KEY,user_id INT NOT NULL,module VARCHAR(80) NOT NULL,added_by INT NOT NULL,expires_at DATETIME DEFAULT NULL,added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE KEY one_mod(user_id,module))");}catch(Exception $e){}
try{db()->exec("ALTER TABLE module_admins ADD COLUMN expires_at DATETIME DEFAULT NULL");}catch(Exception $e){}
$_modAdmins=[];
try{$rows=db()->query("SELECT ma.user_id,ma.module,u.name FROM module_admins ma JOIN users u ON u.id=ma.user_id")->fetchAll();foreach($rows as $r)$_modAdmins[$r['module']][]=(['uid'=>(int)$r['user_id'],'name'=>$r['name']]);}catch(Exception $e){}
$_pending=[];
try{$_pending=db()->query("SELECT id,name,whatsapp_number,created_at FROM users WHERE status='pending' ORDER BY created_at DESC")->fetchAll();}catch(Exception $e){}
require_once __DIR__ . '/../includes/header.php';
?>

<div style="max-width:700px;margin:0 auto;padding:1rem">

  <!-- Header -->
  <div class="hero" style="margin:-1rem -1rem 1.2rem">
    <h1>Club Settings</h1>
    <div class="hero-place">Website, club info, activities and roles</div>
  </div>
  </div>

  <?php if($msg): ?>
  <div style="background:<?= $msg['t']==='ok'?'#f0fdf4':'#fff0f0' ?>;border:1.5px solid <?= $msg['t']==='ok'?'#bbf7d0':'#fecaca' ?>;color:<?= $msg['t']==='ok'?'#16a34a':'#dc2626' ?>;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem;font-weight:700;font-size:.88rem">
    <?= $msg['t']==='ok'?'✅':'❌' ?> <?= h($msg['m']) ?>
  </div>
  <?php endif; ?>

  <!-- Tab Pills -->
  <div style="display:flex;background:#fff;border-radius:12px;padding:.3rem;gap:.2rem;box-shadow:0 2px 10px rgba(0,0,0,.07);margin-bottom:1.2rem;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none">
    <button class="stab on" onclick="switchStab('club',this)">🏛 Club Info</button>
    <button class="stab" onclick="switchStab('home',this)">🎨 Homepage</button>
    <button class="stab" onclick="switchStab('acts',this)">🏟 Activities</button>
    <button class="stab" onclick="switchStab('fees',this)">💳 Fees</button>
    <button class="stab" onclick="switchStab('social',this)">📱 Social</button>
    <button class="stab" onclick="switchStab('wa',this)">💬 WhatsApp</button>
    <button class="stab" onclick="switchStab('roles',this)">👥 Roles</button>
    <button class="stab" onclick="switchStab('notif',this)">🔔 Notify</button>
    <button class="stab" onclick="switchStab('backup',this)">💾 Backup</button>
  </div>

  <style>
  .stab{flex:1 0 auto;white-space:nowrap;min-height:40px;text-align:center;padding:.52rem .6rem;border-radius:9px;font-size:.75rem;font-weight:700;cursor:pointer;transition:all .2s;color:#64748b;border:none;background:none;font-family:'Plus Jakarta Sans',sans-serif}
  .stab.on{background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;box-shadow:0 3px 10px rgba(10,20,224,.28)}
  .stab-panel{display:none}.stab-panel.on{display:block}
  .scard{background:#fff;border-radius:14px;padding:1.2rem;box-shadow:0 3px 14px rgba(0,0,0,.07);border:1px solid #e2e8f0;margin-bottom:1rem}
  .scard-title{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#0A14E0;margin-bottom:1rem;display:flex;align-items:center;gap:.5rem}
  .scard-title::after{content:'';flex:1;height:1.5px;background:linear-gradient(90deg,#0A14E0,transparent)}
  .srow{margin-bottom:.85rem}
  .slbl{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#475569;display:block;margin-bottom:.35rem}
  .sinp{width:100%;padding:.65rem .9rem;border:1.5px solid #e2e8f0;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.88rem;color:#1e293b;background:#f8fafc;outline:none;transition:border-color .18s}
  .sinp:focus{border-color:#0A14E0;background:#fff}
  textarea.sinp{resize:vertical;min-height:70px}
  .sbtn{display:inline-flex;align-items:center;gap:.4rem;padding:.68rem 1.3rem;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.86rem;cursor:pointer;border:none;transition:all .2s}
  .sbtn-blue{background:#0A14E0;color:#fff;box-shadow:0 4px 14px rgba(10,20,224,.28)}.sbtn-blue:hover{background:#1A23C9;transform:translateY(-1px)}
  .sbtn-red{background:#b71c1c;color:#fff}.sbtn-red:hover{background:#c62828}
  .sbtn-green{background:#1b5e20;color:#fff}.sbtn-green:hover{background:#2e7d32}
  .sbtn-grey{background:#f1f5f9;color:#475569;border:1.5px solid #e2e8f0}.sbtn-grey:hover{background:#e2e8f0}
  .sbtn-sm{padding:.38rem .75rem;font-size:.75rem}
  .act-card{background:#fff;border-radius:12px;border:1.5px solid #e2e8f0;padding:.9rem 1rem;margin-bottom:.6rem;display:flex;align-items:center;gap:.75rem}
  .act-card.inactive{opacity:.55}
  .color-row{display:grid;grid-template-columns:repeat(5,1fr);gap:.4rem}
  .color-swatch{width:100%;aspect-ratio:1;border-radius:8px;cursor:pointer;border:2px solid transparent;transition:all .18s}
  .color-swatch.sel{border-color:#0A14E0;transform:scale(1.12)}
  .hint-txt{font-size:.75rem;color:#5d6b80;margin-top:.3rem}
  /* ── Roles tab styles ── */
  .ra-section{background:#fff;border-radius:12px;border:1px solid #e2e8f0;margin-bottom:.5rem;overflow:hidden}
  .ra-head{display:flex;align-items:center;gap:.5rem;padding:.65rem .8rem;cursor:pointer;-webkit-tap-highlight-color:transparent;user-select:none;background:#fff}
  .ra-head h4{font-size:.82rem;font-weight:800;color:#1a1a1a;margin:0;flex:1}
  .ra-head .ra-count{font-size:.75rem;font-weight:700;background:#fee2e2;color:#b71c1c;padding:.12rem .45rem;border-radius:20px}
  .ra-head .ra-arr{font-size:.75rem;color:#5d6b80;flex-shrink:0;transition:transform .2s}
  .ra-body{display:none;padding:.1rem .8rem .8rem}
  .ra-body.open{display:block}
  .ra-search{width:100%;padding:.38rem .6rem;border:1.5px solid #e0e0e0;border-radius:8px;font-size:.76rem;font-family:'Plus Jakarta Sans',sans-serif;outline:none;margin-bottom:.5rem;background:#f8fafc;box-sizing:border-box}
  .ra-search:focus{border-color:#0A14E0}
  .mr{display:flex;align-items:center;gap:.4rem;padding:.38rem .3rem;border-bottom:1px solid #f5f5f5;cursor:pointer}
  .mr:last-child{border-bottom:none}
  .mr-av{width:28px;height:28px;border-radius:50%;color:#fff;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;flex-shrink:0}
  .mr-info{flex:1;min-width:0}
  .mr-name{font-size:.75rem;font-weight:700;color:#1a1a1a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .mr-badge{font-size:.75rem;font-weight:700;color:#fff;padding:.08rem .38rem;border-radius:20px;display:inline-block}
  .rpicker-sheet{display:none;position:fixed;inset:0;z-index:8000;background:rgba(0,0,0,.55);align-items:flex-end;justify-content:center}
  .rpicker-sheet.open{display:flex!important}
  .rpicker-inner{background:#fff;width:100%;max-width:520px;border-radius:20px 20px 0 0;padding:1rem;max-height:80vh;overflow-y:auto}
  .rp-item{display:flex;align-items:center;gap:.55rem;padding:.5rem;border-radius:10px;cursor:pointer;border:1.5px solid #e0e0e0;margin-bottom:.3rem}
  .rp-item.sel{border-color:#0A14E0;background:#ECEEFF}
  .rp-dot{width:16px;height:16px;border-radius:50%;border:2px solid #e0e0e0;flex-shrink:0}
  .rp-item.sel .rp-dot{background:#0A14E0;border-color:#0A14E0}
  .mod-row{border:1px solid #e2e8f0;border-radius:10px;padding:.5rem .6rem;margin-bottom:.4rem}
  .mod-admins{display:flex;gap:.25rem;flex-wrap:wrap;margin-bottom:.35rem}
  .mod-tag{display:inline-flex;align-items:center;gap:.2rem;background:#dbeafe;border-radius:20px;padding:.12rem .45rem;font-size:.75rem;font-weight:700;color:#1A23C9}
  .mod-tag button{background:none;border:none;color:#1A23C9;cursor:pointer;font-size:.75rem;padding:0;line-height:1}
  .ap-row{display:flex;align-items:center;gap:.45rem;padding:.45rem .3rem;border-bottom:1px solid #f5f5f5}
  .ap-row:last-child{border-bottom:none}
  </style>

  <!-- ══ TAB: CLUB INFO ══ -->
  <div class="stab-panel on" id="stab-club">
    <form method="POST">
      <input type="hidden" name="act" value="save_club">

      <div class="scard">
        <div class="scard-title">🏛 Club Identity</div>
        <div class="srow">
          <label class="slbl">Club Name</label>
          <input class="sinp" name="club_name" value="<?= h($s('club_name', setting('CLUB_NAME','Aishwarya Arts & Sports Club'))) ?>" placeholder="Aishwarya Arts &amp; Sports Club">
        </div>
        <div class="srow">
          <label class="slbl">Place / Location</label>
          <input class="sinp" name="club_place" value="<?= h($s('club_place', setting('CLUB_PLACE','Vettikkattiri'))) ?>" placeholder="Vettikkattiri">
        </div>
        <div class="srow">
          <label class="slbl">Tagline / Motto</label>
          <input class="sinp" name="club_tagline" value="<?= h($s('club_tagline', setting('CLUB_TAGLINE',''))) ?>" placeholder="Unity · Sports · Culture · Community">
        </div>
      </div>

      <div class="scard">
        <div class="scard-title">📱 Contact & WhatsApp</div>
        <div class="srow">
          <label class="slbl">Club Phone Number (with country code)</label>
          <input class="sinp" name="club_phone" value="<?= h($s('club_phone', setting('CLUB_PHONE',''))) ?>" placeholder="+919876543210" type="tel">
          <p class="hint-txt">Used for emergency contact and WhatsApp links</p>
        </div>
        <div class="srow">
          <label class="slbl">WhatsApp Group Link</label>
          <input class="sinp" name="club_wa_group" value="<?= h($s('club_wa_group', setting('CLUB_WA_GROUP','#'))) ?>" placeholder="https://chat.whatsapp.com/...">
          <p class="hint-txt">Members join your club WhatsApp group via this link</p>
        </div>
        <div class="srow">
          <label class="slbl">Secretary / Admin WhatsApp Number</label>
          <input class="sinp" name="club_wa_number" value="<?= h($s('club_wa_number','')) ?>" placeholder="+919876543210" type="tel">
          <p class="hint-txt">Receives notifications and requests</p>
        </div>
      </div>

      <button type="submit" class="sbtn sbtn-blue" style="width:100%">💾 Save Club Settings</button>
    </form>
  </div>

  <!-- ══ TAB: HOMEPAGE ══ -->
  <div class="stab-panel" id="stab-home">
    <style>
    .sw{display:flex;align-items:center;justify-content:space-between;gap:1rem;min-height:54px;padding:.4rem 0;border-bottom:1px solid #eef2f1;cursor:pointer}
    .sw:last-child{border-bottom:0}
    .sw b{font-size:.9rem;color:#0B1033;display:block}.sw small{font-size:.78rem;color:#565D82}
    .sw input{position:absolute;opacity:0;width:1px;height:1px}
    .sw .tg{flex-shrink:0;width:50px;height:30px;border-radius:30px;background:#cbd5d3;position:relative;transition:background .2s}
    .sw .tg::after{content:'';position:absolute;top:3px;left:3px;width:24px;height:24px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.25);transition:transform .2s}
    .sw input:checked + .tg{background:#0A14E0}
    .sw input:checked + .tg::after{transform:translateX(20px)}
    .sw input:focus-visible + .tg{outline:3px solid #0A14E0;outline-offset:2px}
    .clr{display:flex;align-items:center;gap:.7rem}
    .clr input[type=color]{width:52px;height:46px;border:1px solid #e2e8f0;border-radius:12px;padding:3px;background:#fff;cursor:pointer}
    </style>
    <form method="POST">
      <input type="hidden" name="act" value="save_home">
      <a href="<?= url('index.php') ?>" target="_blank" rel="noopener" class="sbtn sbtn-grey" style="width:100%;justify-content:center;margin-bottom:1rem">👁 Open the website in a new tab</a>

      <div class="scard">
        <div class="scard-title">🎯 Top banner (hero)</div>
        <div class="srow"><label class="slbl" for="hBadge">Small label above the title</label>
          <input class="sinp" id="hBadge" name="hero_badge" value="<?= h($s('hero_badge','')) ?>" placeholder="<?= h(setting('CLUB_PLACE','Vettikkattiri')) ?> · Kerala"></div>
        <div class="srow"><label class="slbl" for="hTitle">Title</label>
          <input class="sinp" id="hTitle" name="hero_title" value="<?= h($s('hero_title','')) ?>" placeholder="<?= h(setting('CLUB_NAME','Club name')) ?>"></div>
        <div class="srow"><label class="slbl" for="hSub">Subtitle</label>
          <textarea class="sinp" id="hSub" name="hero_subtitle" rows="2" placeholder="<?= h(setting('CLUB_TAGLINE','')) ?>"><?= h($s('hero_subtitle','')) ?></textarea></div>
        <div class="srow"><label class="slbl" for="hCta">Login button text</label>
          <input class="sinp" id="hCta" name="hero_cta_text" value="<?= h($s('hero_cta_text','')) ?>" placeholder="Member login"></div>
        <p class="hint-txt">Banner photos: in <a href="<?= url('modules/gallery.php') ?>" style="color:#0A14E0;font-weight:700">Gallery</a>, tick “Use as homepage background” when uploading. Empty fields use the club name and tagline.</p>
      </div>

      <div class="scard">
        <div class="scard-title">📐 Sections on the homepage</div>
        <?php
        $toggles = array(
          'home_stats_show'        => array('Numbers bar','Members, active members, events, donors'),
          'home_about_show'        => array('About us','Text you write below'),
          'home_activities_show'   => array('Club activities','From the Activities tab (active ones only)'),
          'home_events_show'       => array('Upcoming events','From Events'),
          'home_notices_show'      => array('Notice board','Latest notices posted on the dashboard'),
          'home_committee_show'    => array('Committee','President, secretary, treasurer and committee'),
          'home_achievements_show' => array('Achievements','From Certificates & achievements'),
          'home_gallery_show'      => array('Gallery','Latest gallery photos'),
          'home_join_show'         => array('“Join the club” box','Shown to visitors who are not logged in'),
        );
        foreach ($toggles as $k=>$t): $on = $s($k,'1') !== '0'; ?>
        <label class="sw"><span><b><?= $t[0] ?></b><small><?= $t[1] ?></small></span>
          <input type="checkbox" name="<?= $k ?>" value="1" <?= $on?'checked':'' ?>><span class="tg" aria-hidden="true"></span></label>
        <?php endforeach; ?>
      </div>

      <div class="scard">
        <div class="scard-title">📝 About us</div>
        <div class="srow"><label class="slbl" for="hAbT">Heading</label>
          <input class="sinp" id="hAbT" name="home_about_title" value="<?= h($s('home_about_title','')) ?>" placeholder="Uniting <?= h(setting('CLUB_PLACE','our village')) ?> through sports, arts and service"></div>
        <div class="srow"><label class="slbl" for="hAbX">Text</label>
          <textarea class="sinp" id="hAbX" name="home_about_text" rows="4" placeholder="Tell visitors about the club"><?= h($s('home_about_text','')) ?></textarea></div>
      </div>

      <div class="scard">
        <div class="scard-title">🤝 “Join the club” box</div>
        <div class="srow"><label class="slbl" for="hJT">Heading</label>
          <input class="sinp" id="hJT" name="home_join_title" value="<?= h($s('home_join_title','')) ?>" placeholder="Be part of the club"></div>
        <div class="srow"><label class="slbl" for="hJX">Text</label>
          <textarea class="sinp" id="hJX" name="home_join_text" rows="2" placeholder="Apply in one minute…"><?= h($s('home_join_text','')) ?></textarea></div>
      </div>

      <div class="scard">
        <div class="scard-title">🎨 Look</div>
        <div class="srow"><label class="slbl" for="hPri">Main colour</label>
          <div class="clr"><input type="color" id="hPri" name="home_primary_color" value="<?= h($s('home_primary_color','#0A14E0')) ?>"><span class="hint-txt">Buttons, links, highlights</span></div></div>
        <div class="srow"><label class="slbl" for="hAcc">Accent colour</label>
          <div class="clr"><input type="color" id="hAcc" name="home_accent_color" value="<?= h($s('home_accent_color','#E30613')) ?>"><span class="hint-txt">Login button and labels</span></div></div>
        <div class="srow"><label class="slbl" for="hFont">Font</label>
          <select class="sinp" id="hFont" name="home_font">
            <?php foreach(array('Plus Jakarta Sans','Poppins','Manrope','Outfit') as $f): ?><option <?= $s('home_font','Plus Jakarta Sans')===$f?'selected':'' ?>><?= $f ?></option><?php endforeach; ?>
          </select></div>
        <button type="button" class="sbtn sbtn-grey sbtn-sm" onclick="document.getElementById('hPri').value='#0A14E0';document.getElementById('hAcc').value='#E30613';document.getElementById('hFont').value='Plus Jakarta Sans'">Reset to default look</button>
      </div>

      <div class="scard">
        <div class="scard-title">📄 Footer</div>
        <div class="srow"><label class="slbl" for="hFoot">Footer text</label>
          <textarea class="sinp" id="hFoot" name="footer_text" rows="2" placeholder="Uniting the village through sports, arts and community service."><?= h($s('footer_text','')) ?></textarea></div>
      </div>

      <button type="submit" class="sbtn sbtn-blue" style="width:100%;justify-content:center;min-height:50px">💾 Save homepage settings</button>
    </form>
  </div>

  <!-- ══ TAB: ACTIVITIES ══ -->
  <div class="stab-panel" id="stab-acts">
    <div class="scard">
      <div class="scard-title">🏟 Club Activities</div>
      <p style="font-size:.82rem;color:#64748b;margin-bottom:1rem">Add custom activities with registration links. These appear in navigation and homepage.</p>

      <!-- Existing activities -->
      <?php if(!empty($activities)): ?>
      <div id="actsList" style="margin-bottom:1rem">
        <?php foreach($activities as $act): ?>
        <div class="act-card <?= !$act['is_active']?'inactive':'' ?>">
          <div style="font-size:1.6rem;flex-shrink:0"><?= h($act['emoji']) ?></div>
          <div style="flex:1;min-width:0">
            <div style="font-weight:700;font-size:.9rem;color:#0B1033"><?= h($act['name']) ?></div>
            <?php if($act['description']): ?><div style="font-size:.75rem;color:#64748b;margin-top:.1rem"><?= h(mb_strimwidth($act['description'],0,60,'…')) ?></div><?php endif; ?>
            <div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.35rem">
              <?php if($act['reg_link']): ?>
              <a href="<?= h($act['reg_link']) ?>" target="_blank" style="font-size:.75rem;color:#0A14E0;text-decoration:none;background:#ECEEFF;padding:.1rem .45rem;border-radius:20px">🔗 Reg Link</a>
              <?php endif; ?>
              <?php if($act['info_url']): ?>
              <a href="<?= h($act['info_url']) ?>" target="_blank" style="font-size:.75rem;color:#6a1b9a;text-decoration:none;background:#f3e5f5;padding:.1rem .45rem;border-radius:20px">ℹ️ Info URL</a>
              <?php endif; ?>
              <span style="font-size:.75rem;background:<?= $act['is_active']?'#e8f5e9':'#f1f5f9' ?>;color:<?= $act['is_active']?'#1b5e20':'#64748b' ?>;padding:.1rem .45rem;border-radius:20px"><?= $act['is_active']?'● Active':'○ Hidden' ?></span>
            </div>
          </div>
          <div style="display:flex;gap:.35rem;flex-shrink:0">
            <button class="sbtn sbtn-grey sbtn-sm" onclick="editAct(<?= htmlspecialchars(json_encode($act)) ?>)" title="Edit">✏️</button>
            <form method="POST" style="display:inline">
              <input type="hidden" name="act" value="toggle_activity">
              <input type="hidden" name="act_id" value="<?= $act['id'] ?>">
              <button type="submit" class="sbtn sbtn-grey sbtn-sm" title="Toggle"><?= $act['is_active']?'👁':'🙈' ?></button>
            </form>
            <form method="POST" style="display:inline" data-confirm="Delete this activity?" data-sudo>
              <input type="hidden" name="act" value="del_activity">
              <input type="hidden" name="act_id" value="<?= $act['id'] ?>">
              <button type="submit" class="sbtn sbtn-red sbtn-sm" title="Delete">🗑</button>
            </form>
          </div>
        </div>
        <?php endforeach; ?>
      </div>
      <?php endif; ?>

      <!-- Add / Edit Activity Form -->
      <div style="background:#f8faff;border:1.5px solid #ECEEFF;border-radius:12px;padding:1rem" id="actForm">
        <div style="font-weight:700;font-size:.9rem;color:#0A14E0;margin-bottom:.85rem" id="actFormTitle">➕ Add New Activity</div>
        <form method="POST" id="actFormEl">
          <input type="hidden" name="act" value="save_activity">
          <input type="hidden" name="act_id" id="actId" value="0">
          <div style="display:grid;grid-template-columns:60px 1fr;gap:.5rem;margin-bottom:.6rem">
            <div>
              <label class="slbl">Emoji</label>
              <input class="sinp" name="act_emoji" id="actEmoji" value="🏆" maxlength="4" style="text-align:center;font-size:1.3rem;padding:.4rem">
            </div>
            <div>
              <label class="slbl">Activity Name *</label>
              <input class="sinp" name="act_name" id="actName" placeholder="e.g. Football Tournament" required>
            </div>
          </div>
          <div class="srow">
            <label class="slbl">Description</label>
            <textarea class="sinp" name="act_desc" id="actDesc" rows="2" placeholder="Short description of this activity"></textarea>
          </div>
          <div class="srow">
            <label class="slbl">🔗 Registration Link (optional)</label>
            <input class="sinp" name="act_reg" id="actReg" placeholder="https://forms.google.com/... or WhatsApp link">
            <p class="hint-txt">Members click this to register for the activity</p>
          </div>
          <div class="srow">
            <label class="slbl">ℹ️ Info / Details URL (optional)</label>
            <input class="sinp" name="act_info" id="actInfo" placeholder="Link to schedule, rules, fixtures etc.">
          </div>
          <div class="srow">
            <label class="slbl">Card Colour</label>
            <div style="display:flex;align-items:center;gap:.75rem">
              <input type="color" name="act_color" id="actColor" value="#0A14E0"
                style="width:44px;height:36px;border:none;border-radius:7px;cursor:pointer;padding:0">
              <div class="color-row" style="flex:1">
                <?php foreach(['#0A14E0','#b71c1c','#1b5e20','#6a1b9a','#e65100','#00838f','#c8922a','#37474f'] as $c): ?>
                <div style="width:28px;height:28px;background:<?= $c ?>;border-radius:6px;cursor:pointer;border:2px solid transparent;transition:all .15s"
                  onclick="document.getElementById('actColor').value='<?= $c ?>'"></div>
                <?php endforeach; ?>
              </div>
            </div>
          </div>
          <div style="display:flex;gap:.5rem">
            <button type="submit" class="sbtn sbtn-green" style="flex:1">💾 Save Activity</button>
            <button type="button" class="sbtn sbtn-grey" onclick="clearActForm()">✕ Clear</button>
          </div>
        </form>
      </div>

      <!-- Default activity shortcuts -->
      <div style="margin-top:1rem">
        <div style="font-size:.76rem;font-weight:700;color:#64748b;margin-bottom:.5rem;text-transform:uppercase;letter-spacing:.08em">Quick Add Common Activities</div>
        <div style="display:flex;flex-wrap:wrap;gap:.4rem">
          <?php
          $presets = [
            ['⚽','Football Tournament','#1b5e20'],
            ['🎭','Arts Festival','#6a1b9a'],
            ['🌸','Onam Celebration','#e65100'],
            ['🏏','Cricket Tournament','#b71c1c'],
            ['🏐','Volleyball League','#0A14E0'],
            ['🎤','Talent Show','#c8922a'],
            ['🩸','Blood Donation Camp','#b71c1c'],
            ['🏃','Sports Day','#1b5e20'],
            ['🎊','Annual Fest','#6a1b9a'],
            ['📚','Quiz Competition','#0A14E0'],
          ];
          foreach($presets as $p):
          ?>
          <button type="button" onclick="quickAct('<?= addslashes($p[0]) ?>','<?= addslashes($p[1]) ?>','<?= $p[2] ?>')"
            style="background:#f8fafc;border:1.5px solid #e2e8f0;border-radius:20px;padding:.3rem .75rem;font-size:.75rem;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:.3rem;transition:all .18s"
            onmouseover="this.style.borderColor='#0A14E0';this.style.color='#0A14E0'"
            onmouseout="this.style.borderColor='#e2e8f0';this.style.color=''">
            <?= $p[0] ?> <?= $p[1] ?>
          </button>
          <?php endforeach; ?>
        </div>
      </div>
    </div>
  </div>

  <!-- ══ TAB: FEES ══ -->
  <div class="stab-panel" id="stab-fees">
    <form method="POST" data-sudo-fields="fee_monthly,fee_annual">
      <input type="hidden" name="act" value="save_club">
      <div class="scard">
        <div class="scard-title">💳 Membership Fees</div>
        <div class="srow">
          <label class="slbl">Monthly Fee (₹)</label>
          <input class="sinp" name="fee_monthly" type="number" value="<?= h($s('fee_monthly', setting('FEE_MONTHLY',100))) ?>" min="0" step="10">
        </div>
        <div class="srow">
          <label class="slbl">Annual Fee (₹)</label>
          <input class="sinp" name="fee_annual" type="number" value="<?= h($s('fee_annual', setting('FEE_ANNUAL',1000))) ?>" min="0" step="100">
          <p class="hint-txt">Annual fee shown to members on subscription page</p>
        </div>
        <div style="background:#ECEEFF;border-radius:10px;padding:.85rem 1rem;margin-top:.5rem">
          <div style="font-size:.82rem;font-weight:700;color:#0A14E0;margin-bottom:.3rem">💡 Note</div>
          <div style="font-size:.78rem;color:#1A23C9;line-height:1.6">After saving fees here, also update <code>setting('FEE_MONTHLY',100))</code> and <code>setting('FEE_ANNUAL',1000))</code> in <code>/av/includes/config.php</code> to match. The settings table overrides display values.</div>
        </div>
      </div>
      <div class="scard">
        <div class="scard-title">🏦 Payment Details</div>
        <div class="srow">
          <label class="slbl">UPI ID</label>
          <input class="sinp" name="upi_id" value="<?= h($s('upi_id','')) ?>" placeholder="yourname@upi">
        </div>
        <div class="srow">
          <label class="slbl">Bank Name</label>
          <input class="sinp" name="bank_name" value="<?= h($s('bank_name','')) ?>" placeholder="State Bank of India">
        </div>
        <div class="srow">
          <label class="slbl">Account Name</label>
          <input class="sinp" name="account_name" value="<?= h($s('account_name','')) ?>" placeholder="Aishwarya Arts & Sports Club">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem">
          <div class="srow">
            <label class="slbl">Account Number</label>
            <input class="sinp" name="account_no" value="<?= h($s('account_no','')) ?>" placeholder="XXXXXXXXXX">
          </div>
          <div class="srow">
            <label class="slbl">IFSC Code</label>
            <input class="sinp" name="ifsc" value="<?= h($s('ifsc','')) ?>" placeholder="SBIN0001234">
          </div>
        </div>
      </div>
      <button type="submit" class="sbtn sbtn-blue" style="width:100%">💾 Save Fee & Payment Settings</button>
    </form>
  </div>

</div>

  <!-- ══ TAB: SOCIAL MEDIA ══ -->
  <div class="stab-panel" id="stab-social">
    <form method="POST">
      <input type="hidden" name="act" value="save_social">
      <div class="scard">
        <div class="scard-title">📱 Social Media Links</div>
        <p style="font-size:.8rem;color:#64748b;margin-bottom:1rem">Add links below. Icons appear automatically in the website footer. Leave blank to hide.</p>

        <?php
        $socDef = array(
          'social_wa_group'  => array('label'=>'WhatsApp Group Link','ph'=>'https://chat.whatsapp.com/...','icon'=>'fab fa-whatsapp','bg'=>'#128c7e'),
          'social_facebook'  => array('label'=>'Facebook Page','ph'=>'https://facebook.com/yourpage','icon'=>'fab fa-facebook-f','bg'=>'#1877f2'),
          'social_instagram' => array('label'=>'Instagram Profile','ph'=>'https://instagram.com/yourprofile','icon'=>'fab fa-instagram','bg'=>'#e1306c'),
          'social_youtube'   => array('label'=>'YouTube Channel','ph'=>'https://youtube.com/@channel','icon'=>'fab fa-youtube','bg'=>'#ff0000'),
          'social_twitter'   => array('label'=>'X / Twitter Profile','ph'=>'https://x.com/yourprofile','icon'=>'fab fa-x-twitter','bg'=>'#000'),
          'social_telegram'  => array('label'=>'Telegram Channel','ph'=>'https://t.me/yourchannel','icon'=>'fab fa-telegram','bg'=>'#0088cc'),
          'social_linkedin'  => array('label'=>'LinkedIn Page','ph'=>'https://linkedin.com/company/...','icon'=>'fab fa-linkedin-in','bg'=>'#0077b5'),
          'social_tiktok'    => array('label'=>'TikTok Profile','ph'=>'https://tiktok.com/@profile','icon'=>'fab fa-tiktok','bg'=>'#010101'),
          'social_website'   => array('label'=>'Official Website','ph'=>'https://yourwebsite.com','icon'=>'fas fa-globe','bg'=>'#0A14E0'),
        );
        foreach($socDef as $skey=>$sinfo):
          $curSocVal = $s($skey,'');
        ?>
        <div style="display:flex;align-items:center;gap:.65rem;margin-bottom:.75rem">
          <div style="width:36px;height:36px;border-radius:50%;background:<?= $sinfo['bg'] ?>;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <i class="<?= $sinfo['icon'] ?>" style="color:#fff;font-size:.85rem"></i>
          </div>
          <div style="flex:1">
            <label class="slbl" style="margin-bottom:.25rem"><?= h($sinfo['label']) ?></label>
            <input class="sinp" name="<?= $skey ?>" value="<?= h($curSocVal) ?>" placeholder="<?= h($sinfo['ph']) ?>">
          </div>
        </div>
        <?php endforeach; ?>

        <div style="background:#ECEEFF;border-radius:10px;padding:.85rem 1rem;margin-top:.5rem;font-size:.78rem;color:#1A23C9;line-height:1.6">
          💡 Save → icons appear in footer instantly. Leave blank to remove icon. WhatsApp personal chat uses Club Phone from Club Info.
        </div>
      </div>
      <button type="submit" class="sbtn sbtn-blue" style="width:100%">💾 Save Social Links</button>
    </form>
  </div>

  <!-- ═══ ROLES TAB ═══ -->
  <!-- ══ TAB: WHATSAPP SENDING ══ -->
  <?php
  if (getSetting('wa_cron_key') === '') { saveSetting('wa_cron_key', bin2hex(random_bytes(16)), 'whatsapp'); $settings['wa_cron_key'] = getSetting('wa_cron_key'); }
  $waProv = $s('wa_provider','off');
  wa_tables();
  $waPending = 0; $waFailed = 0; $waLog = array();
  try {
    $waPending = (int)db()->query("SELECT COUNT(*) FROM wa_queue WHERE status='pending'")->fetchColumn();
    $waFailed  = (int)db()->query("SELECT COUNT(*) FROM wa_queue WHERE status='failed'")->fetchColumn();
    $waLog     = db()->query("SELECT * FROM wa_log ORDER BY id DESC LIMIT 15")->fetchAll();
  } catch (Exception $e) {}
  $waCron = rtrim(defined('SITE_URL') ? SITE_URL : '', '/') . '/modules/wa_worker.php?key=' . getSetting('wa_cron_key');
  ?>
  <div class="stab-panel" id="stab-wa">
    <style>
    .wa-prov{display:grid;gap:.6rem}
    .wa-opt{display:flex;gap:.8rem;align-items:flex-start;padding:.9rem 1rem;border:1.5px solid #e3e7f5;border-radius:16px;cursor:pointer;background:#fff}
    .wa-opt input{margin-top:.25rem;width:20px;height:20px;accent-color:#0A14E0;flex-shrink:0}
    .wa-opt b{display:block;font-size:.95rem;color:#0B1033}.wa-opt small{font-size:.8rem;color:#565D82}
    .wa-opt:has(input:checked){border-color:#0A14E0;background:#F3F4FF}
    .wa-box{display:none}.wa-box.on{display:block}
    .wa-status{display:flex;align-items:center;gap:.6rem;padding:.8rem 1rem;border-radius:14px;background:#F5F7FF;border:1px solid #e3e7f5;font-size:.88rem;font-weight:600;color:#3B4266}
    .wa-dot{width:12px;height:12px;border-radius:50%;background:#94a3b8;flex-shrink:0}
    .wa-dot.ok{background:#15803D}.wa-dot.bad{background:#E30613}
    .wa-row{display:flex;gap:.5rem;flex-wrap:wrap}
    .wa-row .sinp{flex:1;min-width:180px}
    .wa-code{font-family:ui-monospace,Consolas,monospace;font-size:.78rem;background:#0B1033;color:#fff;border-radius:12px;padding:.75rem .9rem;word-break:break-all;white-space:pre-wrap}
    .wa-log{width:100%;border-collapse:collapse;font-size:.8rem}
    .wa-log td,.wa-log th{padding:.45rem .4rem;border-bottom:1px solid #eef1fa;text-align:left;vertical-align:top}
    .wa-log th{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:#565D82}
    .wa-steps{padding-left:1.2rem;font-size:.88rem;color:#3B4266;line-height:1.6}
    .wa-steps li{margin-bottom:.45rem}
    .wa-steps code{background:#F0F2FF;padding:.05rem .35rem;border-radius:6px;font-size:.82rem}
    </style>

    <div class="scard">
      <div class="scard-title">📶 Connection</div>
      <div class="wa-status" id="waStatus" role="status"><span class="wa-dot" id="waDot"></span><span id="waStatusTxt"><?= $waProv==='off' ? 'Sending is off — choose GOWA or Meta below.' : 'Press “Check connection”.' ?></span></div>
      <div class="wa-row" style="margin-top:.7rem">
        <button type="button" class="sbtn sbtn-grey" onclick="waCall('wa_status')">🔄 Check connection</button>
      </div>
    </div>

    <form method="POST">
      <input type="hidden" name="act" value="save_whatsapp">
      <div class="scard">
        <div class="scard-title">💬 How should the website send WhatsApp?</div>
        <div class="wa-prov">
          <label class="wa-opt"><input type="radio" name="wa_provider" value="off" <?= $waProv==='off'?'checked':'' ?> onchange="waShow()"><span><b>Off</b><small>Nothing is sent automatically. Admins keep using the tap-to-send WhatsApp links.</small></span></label>
          <label class="wa-opt"><input type="radio" name="wa_provider" value="gowa" <?= $waProv==='gowa'?'checked':'' ?> onchange="waShow()"><span><b>GOWA — free, self-hosted (recommended)</b><small>Your own GOWA server with a club WhatsApp number. Free; needs a small always-on server.</small></span></label>
          <label class="wa-opt"><input type="radio" name="wa_provider" value="meta" <?= $waProv==='meta'?'checked':'' ?> onchange="waShow()"><span><b>Meta WhatsApp Cloud API — official</b><small>No ban risk and no server, but Meta charges per OTP / alert message and needs approved templates.</small></span></label>
        </div>
      </div>

      <div class="scard wa-box" id="waGowa">
        <div class="scard-title">🖥 GOWA server</div>
        <div class="srow"><label class="slbl" for="waUrl">Server address</label>
          <input class="sinp" id="waUrl" name="wa_gowa_url" value="<?= h($s('wa_gowa_url','')) ?>" placeholder="https://wa.yourclub.in  or  http://1.2.3.4:3000" inputmode="url"></div>
        <div class="g2">
          <div class="srow"><label class="slbl" for="waUser">Username</label>
            <input class="sinp" id="waUser" name="wa_gowa_user" value="<?= h($s('wa_gowa_user','')) ?>" autocomplete="off"></div>
          <div class="srow"><label class="slbl" for="waPass">Password</label>
            <input class="sinp" id="waPass" name="wa_gowa_pass" type="password" value="" autocomplete="new-password" placeholder="<?= $s('wa_gowa_pass','')!=='' ? '•••••• saved — leave empty to keep' : 'From --basic-auth' ?>"></div>
        </div>
        <div class="srow"><label class="slbl" for="waDev">Device ID (optional)</label>
          <input class="sinp" id="waDev" name="wa_gowa_device" value="<?= h($s('wa_gowa_device','')) ?>" placeholder="Leave empty if GOWA has only one WhatsApp number"></div>
      </div>

      <div class="scard wa-box" id="waMeta">
        <div class="scard-title">🔵 Meta Cloud API</div>
        <div class="srow"><label class="slbl" for="waTok">Access token</label>
          <input class="sinp" id="waTok" name="wa_meta_token" type="password" value="" autocomplete="new-password" placeholder="<?= $s('wa_meta_token','')!=='' ? '•••••• saved — leave empty to keep' : 'Permanent token from Meta Business' ?>"></div>
        <div class="srow"><label class="slbl" for="waPid">Phone number ID</label>
          <input class="sinp" id="waPid" name="wa_meta_phone_id" value="<?= h($s('wa_meta_phone_id','')) ?>" inputmode="numeric"></div>
        <div class="g2">
          <div class="srow"><label class="slbl" for="waTo">OTP template name</label>
            <input class="sinp" id="waTo" name="wa_meta_tpl_otp" value="<?= h($s('wa_meta_tpl_otp','')) ?>" placeholder="e.g. login_code"></div>
          <div class="srow"><label class="slbl" for="waTn">Notice template name</label>
            <input class="sinp" id="waTn" name="wa_meta_tpl_notice" value="<?= h($s('wa_meta_tpl_notice','')) ?>" placeholder="e.g. club_notice ({{1}} = message)"></div>
        </div>
        <div class="srow"><label class="slbl" for="waLang">Template language code</label>
          <input class="sinp" id="waLang" name="wa_meta_lang" value="<?= h($s('wa_meta_lang','en')) ?>" style="max-width:140px"></div>
      </div>

      <div class="scard">
        <div class="scard-title">📨 What to send</div>
        <?php foreach (array(
            'otp'=>array('Login & passkey reset codes (optional)','Off = members log in with their passkey as usual. On = they can also get a 6-digit code on WhatsApp'),
            'approve'=>array('Membership approved','Welcome message when an admin approves a member'),
            'events'=>array('New events','Announcement to all active members when an event is added'),
            'blood'=>array('Blood requests','Message to available donors of the same blood group'),
            'fees'=>array('Fee reminders','7 days, 1 day and on the day a membership ends')) as $k=>$t): $on = $s('wa_on_'.$k, $k==='otp' ? '0' : '1')!=='0'; ?>
        <label class="sw"><span><b><?= $t[0] ?></b><small><?= $t[1] ?></small></span>
          <input type="checkbox" name="wa_on_<?= $k ?>" value="1" <?= $on?'checked':'' ?>><span class="tg" aria-hidden="true"></span></label>
        <?php endforeach; ?>
        <div class="g2" style="margin-top:.8rem">
          <div class="srow"><label class="slbl" for="waCc">Country code</label>
            <input class="sinp" id="waCc" name="wa_country" value="<?= h($s('wa_country','91')) ?>" inputmode="numeric"></div>
          <div class="srow"><label class="slbl" for="waDelay">Seconds between messages</label>
            <input class="sinp" id="waDelay" name="wa_delay" type="number" min="2" max="30" value="<?= h($s('wa_delay','4')) ?>"></div>
        </div>
        <p class="hint-txt">A few seconds between messages keeps the club number safe from WhatsApp spam limits.</p>
      </div>

      <button type="submit" class="sbtn sbtn-blue" style="width:100%;justify-content:center;min-height:50px;margin-bottom:1rem">💾 Save WhatsApp settings</button>

      <div class="scard">
        <div class="scard-title">🧪 Send a test message</div>
        <div class="wa-row">
          <input class="sinp" id="waTestPh" type="tel" inputmode="tel" placeholder="Your WhatsApp number" aria-label="WhatsApp number for the test">
          <button type="button" class="sbtn sbtn-green" onclick="waCall('wa_test',{phone:document.getElementById('waTestPh').value})">📤 Send test</button>
        </div>
        <p class="hint-txt">Save first, then test. The result appears in the log below.</p>
      </div>

      <div class="scard">
        <div class="scard-title">📬 Message queue</div>
        <p style="font-size:.88rem;color:#3B4266;margin-bottom:.6rem">Waiting: <b><?= $waPending ?></b> · Failed: <b><?= $waFailed ?></b></p>
        <div class="wa-row" style="margin-bottom:.8rem">
          <button type="button" class="sbtn sbtn-grey" onclick="waCall('wa_run')">▶ Send waiting messages now</button>
          <?php if($waFailed): ?><button type="button" class="sbtn sbtn-grey" onclick="waCall('wa_retry')">↻ Retry failed</button><?php endif; ?>
        </div>
        <label class="slbl" for="waCronLine">Cron job (every minute) — paste in your hosting control panel</label>
        <div class="wa-code" id="waCronLine">curl -s "<?= h($waCron) ?>" &gt;/dev/null</div>
        <label style="display:flex;gap:.5rem;align-items:center;margin-top:.6rem;font-size:.82rem;color:#565D82"><input type="checkbox" name="wa_new_key" value="1"> Make a new secret key when I save (old cron line stops working)</label>
        <p class="hint-txt">Without a cron job, waiting messages still go out a few at a time while members use the website.</p>
      </div>
    </form>

    <div class="scard">
      <div class="scard-title">🧾 Recent messages</div>
      <?php if(empty($waLog)): ?><p class="hint-txt">Nothing sent yet.</p><?php else: ?>
      <div style="overflow-x:auto" tabindex="0" role="region" aria-label="Recent WhatsApp messages">
      <table class="wa-log"><thead><tr><th>Time</th><th>To</th><th>Type</th><th>Result</th></tr></thead><tbody>
      <?php foreach($waLog as $l): ?>
        <tr><td><?= date('d M H:i', strtotime($l['created_at'])) ?></td><td><?= h(wa_mask($l['phone'])) ?></td><td><?= h($l['kind']) ?></td>
            <td style="color:<?= $l['ok']?'#166534':'#B80F0A' ?>;font-weight:600"><?= $l['ok']?'✓ ':'✗ ' ?><?= h($l['info']) ?></td></tr>
      <?php endforeach; ?></tbody></table></div>
      <?php endif; ?>
    </div>

    <details class="scard">
      <summary class="scard-title" style="cursor:pointer;margin:0">📘 Setup steps (GOWA)</summary>
      <ol class="wa-steps" style="margin-top:.8rem">
        <li>Get a <b>separate SIM</b> for the club and install WhatsApp on a phone with it. Do not use a personal number.</li>
        <li>Rent a small Linux server (VPS) or use a free cloud tier, and install <b>Docker</b> on it.</li>
        <li>On the server run:<br><code>docker run -d --name whatsapp --restart always -p 3000:3000 -v whatsapp-storages:/app/storages aldinokemal2104/go-whatsapp-web-multidevice rest --basic-auth=club:CHOOSE-A-STRONG-PASSWORD</code></li>
        <li>Best: put it behind HTTPS (for example a sub-domain like <code>wa.yourclub.in</code> with Caddy or Nginx). Otherwise use <code>http://SERVER-IP:3000</code>.</li>
        <li>Open that address in a browser, log in with the username and password from step 3, and <b>scan the QR code</b> with the club phone (WhatsApp → Linked devices).</li>
        <li>Here: choose <b>GOWA</b>, fill in the address, username and password, and <b>Save</b>.</li>
        <li>Press <b>Check connection</b>, then <b>Send test</b> to your own number.</li>
        <li>In your hosting control panel → <b>Cron Jobs</b>, add the cron line above to run every minute.</li>
        <li>Turn on the messages you want under “What to send”. Members will now see “Get a code on WhatsApp” when they log in or forget their passkey.</li>
      </ol>
    </details>
  </div>

  <script>
  function waShow(){
    var v=(document.querySelector('input[name=wa_provider]:checked')||{}).value;
    document.getElementById('waGowa').classList.toggle('on',v==='gowa');
    document.getElementById('waMeta').classList.toggle('on',v==='meta');
  }
  waShow();
  function waCall(action,extra){
    var fd=new FormData(); fd.append('action',action);
    if(extra) Object.keys(extra).forEach(function(k){ fd.append(k,extra[k]); });
    var dot=document.getElementById('waDot'), txt=document.getElementById('waStatusTxt');
    dot.className='wa-dot'; txt.textContent='Working…';
    document.getElementById('waStatus').scrollIntoView({behavior:'smooth',block:'center'});
    fetch(location.pathname,{method:'POST',body:fd,credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){
      dot.className='wa-dot '+(d.ok?'ok':'bad'); txt.textContent=d.msg||(d.ok?'Done':'Failed');
    }).catch(function(){ dot.className='wa-dot bad'; txt.textContent='Network error'; });
  }
  </script>

  <div class="stab-panel" id="stab-roles">
    <?php
    $RC=['secretary'=>'#0B1033','developer'=>'#6a1b9a','president'=>'#b71c1c',
         'vice_president'=>'#c62828','joint_secretary'=>'#1A23C9','treasurer'=>'#2e7d32',
         'sports_committee'=>'#e65100','cultural_committee'=>'#7b1fa2',
         'finance_committee'=>'#1b5e20','committee_member'=>'#37474f','member'=>'#78909c'];
    $RL=['developer'=>['Developer','🛠️','Super admin'],
         'secretary'=>['Secretary','👑','Super admin'],
         'president'=>['President','🏅','Can post'],
         'vice_president'=>['Vice President','🏅','Can post'],
         'joint_secretary'=>['Joint Secretary','📋','Can post'],
         'treasurer'=>['Treasurer','💰','Finance admin'],
         'sports_committee'=>['Sports Committee','⚽','Sports pages'],
         'cultural_committee'=>['Cultural Committee','🎭','Cultural pages'],
         'finance_committee'=>['Finance Committee','💳','Finance pages'],
         'committee_member'=>['Committee Member','👥','No extra access'],
         'member'=>['Member','👤','Regular']];
    $mods=['football'=>['⚽','Football'],
           'arts_festival'=>['🎭','Arts Festival'],'onam'=>['🌸','Onam'],
           'crowdfund'=>['❤️','Crowd Fund'],
           'donation'=>['💚','Donations'],'election'=>['🗳️','Elections'],
           'blood'=>['🩸','Blood Hub'],'gallery'=>['📸','Gallery'],
           'events'=>['📅','Events'],'market'=>['🛍️','Market'],
           'groundfund'=>['🏟️','Ground Fund'],'certificate'=>['🏆','Achievements'],
           'subscription'=>['💳','Subscription'],'idcard'=>['🪪','ID Card']];
    usort($_allUsers,function($a,$b){
      $o=['developer'=>0,'secretary'=>1,'president'=>2,'vice_president'=>3,
          'sports_committee'=>4,'cultural_committee'=>5,'finance_committee'=>6,
          'joint_secretary'=>7,'treasurer'=>8,'committee_member'=>9,'member'=>10];
      $oa=$o[$a['role']]??10;$ob=$o[$b['role']]??10;
      return $oa!==$ob?$oa-$ob:strcmp($a['name'],$b['name']);
    });
    ?>

    <!-- ① Assign Role -->
    <div class="ra-section">
      <div class="ra-head" onclick="toggleRa('assign')">
        <span style="font-size:1rem">🔑</span>
        <h4>Assign Role</h4>
        <span class="ra-arr" id="arr-assign">▲</span>
      </div>
      <div class="ra-body open" id="ra-assign">
        <input class="ra-search" id="assignSearch" placeholder="🔍 Search member..." oninput="assignFilter(this.value)">
        <div style="max-height:300px;overflow-y:auto">
        <?php foreach($_allUsers as $u):
          $rc=$RC[$u['role']]??'#78909c';
          $rl=($RL[$u['role']]??['Member','👤',''])[0];
          $ri=($RL[$u['role']]??['Member','👤',''])[1];
        ?>
        <div class="mr" data-n="<?php echo h(strtolower($u['name'])); ?>"
             onclick="openRP(<?php echo (int)$u['id']; ?>,'<?php echo h(addslashes($u['name'])); ?>','<?php echo $u['role']; ?>')">
          <div class="mr-av" style="background:<?php echo $rc; ?>"><?php echo h(mb_substr($u['name'],0,1)); ?></div>
          <div class="mr-info">
            <div class="mr-name"><?php echo h($u['name']); ?></div>
            <span class="mr-badge" style="background:<?php echo $rc; ?>"><?php echo $ri; ?> <?php echo $rl; ?></span>
          </div>
          <span style="font-size:.75rem;color:#666666">›</span>
        </div>
        <?php endforeach; ?>
        </div>
      </div>
    </div>

    <!-- ② Module Admins -->
    <div class="ra-section">
      <div class="ra-head" onclick="toggleRa('mods')">
        <span style="font-size:1rem">🔧</span>
        <h4>Module Admins</h4>
        <span class="ra-arr" id="arr-mods">▼</span>
      </div>
      <div class="ra-body" id="ra-mods">
        <?php foreach($mods as $mod=>$mi):
          $curAdm=$_modAdmins[$mod]??[];
          $curIds=array_column($curAdm,'uid');
        ?>
        <div class="mod-row">
          <div style="display:flex;align-items:center;gap:.35rem;margin-bottom:.3rem">
            <span><?php echo $mi[0]; ?></span>
            <span style="font-size:.78rem;font-weight:700;flex:1"><?php echo $mi[1]; ?></span>
          </div>
          <?php if(!empty($curAdm)): ?>
          <div class="mod-admins">
            <?php foreach($curAdm as $ca): ?>
            <div class="mod-tag"><?php echo h($ca['name']); ?>
              <button onclick="rmMod(<?php echo (int)$ca['uid']; ?>,'<?php echo $mod; ?>',this)">✕</button>
            </div>
            <?php endforeach; ?>
          </div>
          <?php endif; ?>
          <div style="position:relative">
            <input class="ra-search" placeholder="🔍 Search to add..." oninput="modSrch(this,'<?php echo $mod; ?>')" style="margin:0">
            <div id="mdd_<?php echo $mod; ?>" style="display:none;position:absolute;top:100%;left:0;right:0;background:#fff;border:1.5px solid #e0e0e0;border-radius:8px;max-height:140px;overflow-y:auto;z-index:50;box-shadow:0 4px 12px rgba(0,0,0,.1)"></div>
          </div>
        </div>
        <?php endforeach; ?>
      </div>
    </div>

    <!-- ③ Pending Approvals -->
    <div class="ra-section">
      <div class="ra-head" onclick="toggleRa('pend')">
        <span style="font-size:1rem">⏳</span>
        <h4>Pending Approvals</h4>
        <?php if(!empty($_pending)): ?><span class="ra-count"><?php echo count($_pending); ?></span><?php endif; ?>
        <span class="ra-arr" id="arr-pend">▼</span>
      </div>
      <div class="ra-body" id="ra-pend">
        <?php if(empty($_pending)): ?>
        <div style="text-align:center;padding:.8rem;font-size:.78rem;color:#5d6b80">✅ No pending approvals</div>
        <?php else: foreach($_pending as $p): ?>
        <div class="ap-row" id="apr_<?php echo (int)$p['id']; ?>">
          <div style="width:30px;height:30px;border-radius:50%;background:#e65100;color:#fff;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;flex-shrink:0">
            <?php echo h(mb_substr($p['name'],0,1)); ?>
          </div>
          <div style="flex:1;min-width:0">
            <div style="font-size:.75rem;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><?php echo h($p['name']); ?></div>
            <div style="font-size:.75rem;color:#94a3b8"><?php echo h($p['whatsapp_number']); ?> · <?php echo date('d M',strtotime($p['created_at'])); ?></div>
          </div>
          <div style="display:flex;gap:.3rem">
            <button onclick="doApprove(<?php echo (int)$p['id']; ?>)" style="background:#e8f5e9;color:#2e7d32;border:1px solid #c8e6c9;border-radius:7px;padding:.28rem .55rem;font-size:.75rem;font-weight:700;cursor:pointer">✅ Approve</button>
            <button onclick="doReject(<?php echo (int)$p['id']; ?>)" style="background:#ffebee;color:#b71c1c;border:1px solid #ffcdd2;border-radius:7px;padding:.28rem .55rem;font-size:.75rem;font-weight:700;cursor:pointer">❌ Reject</button>
          </div>
        </div>
        <?php endforeach; endif; ?>
      </div>
    </div>
  </div><!-- /stab-roles -->

  <!-- ═══ NOTIFY TAB ═══ -->
  <div class="stab-panel" id="stab-notif">
    <?php
    $pushStats=['subscribers'=>0,'logs'=>[]];
    try{
      $pushStats['subscribers']=(int)db()->query("SELECT COUNT(DISTINCT user_id) FROM push_subscriptions")->fetchColumn();
      $pushStats['logs']=db()->query("SELECT pl.*,u.name sender FROM push_log pl JOIN users u ON u.id=pl.sent_by ORDER BY pl.sent_at DESC LIMIT 5")->fetchAll();
    }catch(Exception $e){}
    ?>
    <div class="scard">
      <div class="scard-title">🔔 Send Push Notification</div>
      <div style="background:#ECEEFF;border-radius:10px;padding:.65rem .8rem;margin-bottom:.8rem;display:flex;align-items:center;gap:.5rem">
        <span style="font-size:1.2rem">📱</span>
        <div>
          <div style="font-size:.82rem;font-weight:700;color:#1A23C9"><?php echo $pushStats['subscribers']; ?> subscribers</div>
          <div style="font-size:.75rem;color:#64748b">Members with notifications enabled</div>
        </div>
      </div>
      <div class="fg">
        <label class="slbl">Notification Title *</label>
        <input type="text" id="ntitle" class="sinp" placeholder="e.g. New Event Announced!">
      </div>
      <div class="fg">
        <label class="slbl">Message *</label>
        <textarea id="nbody" class="sinp" rows="2" placeholder="e.g. Football tournament this Friday at 4PM..."></textarea>
      </div>
      <div class="fg">
        <label class="slbl">Link (optional)</label>
        <input type="text" id="nurl" class="sinp" placeholder="/modules/events.php" value="/">
      </div>
      <div class="fg">
        <label class="slbl">Send To</label>
        <select id="ntarget" class="sinp">
          <option value="all">All Members</option>
        </select>
      </div>
      <button onclick="sendNotif()" style="width:100%;padding:.65rem;background:linear-gradient(135deg,#0B1033,#1A23C9);color:#fff;border:none;border-radius:10px;font-weight:800;font-size:.9rem;cursor:pointer">
        🔔 Send Notification
      </button>
    </div>

    <!-- Notification History -->
    <?php if(!empty($pushStats['logs'])): ?>
    <div class="scard">
      <div class="scard-title">📋 Recent Notifications</div>
      <?php foreach($pushStats['logs'] as $log): ?>
      <div style="padding:.5rem .3rem;border-bottom:1px solid #f5f5f5">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.15rem">
          <div style="font-size:.78rem;font-weight:700;color:#1a1a1a"><?php echo h($log['title']); ?></div>
          <span style="font-size:.75rem;background:#ECEEFF;color:#1A23C9;padding:.1rem .4rem;border-radius:20px;font-weight:700"><?php echo (int)$log['total_sent']; ?> sent</span>
        </div>
        <div style="font-size:.75rem;color:#64748b"><?php echo h($log['body']); ?></div>
        <div style="font-size:.75rem;color:#5d6b80;margin-top:.15rem"><?php echo h($log['sender']); ?> · <?php echo date('d M Y H:i',strtotime($log['sent_at'])); ?></div>
      </div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
  </div><!-- /stab-notif -->

  <!-- ═══ DATABASE BACKUP ═══ -->
  <div class="stab-panel" id="stab-backup">
    <div style="background:#fff;border:1px solid #E3E7F5;border-radius:14px;padding:1.4rem">
      <div style="font-size:1.05rem;font-weight:800;color:#0B1033;margin-bottom:.4rem">💾 Database Backup</div>
      <p style="font-size:.86rem;color:#64748b;line-height:1.6;margin-bottom:1.1rem">
        Download a complete backup of your website database as a <b>.sql</b> file. This includes every table, all members, settings, events, donations, and other data. Keep these backups safe — you can restore them later if anything goes wrong.
      </p>
      <a href="?export_sql=1" style="display:inline-flex;align-items:center;gap:.6rem;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;padding:.8rem 1.6rem;border-radius:10px;font-weight:800;font-size:.92rem;text-decoration:none;box-shadow:0 6px 20px rgba(10,20,224,.3)">
        ⬇️ Download Database Backup (.sql)
      </a>
      <div style="margin-top:1.2rem;padding:.85rem 1rem;background:#fff8e1;border:1px solid #ffe082;border-radius:10px;font-size:.8rem;color:#7a5c00;line-height:1.6">
        <b>💡 Tips:</b><br>
        • Download a backup before any big change or update.<br>
        • Store the file somewhere safe (Google Drive, your computer).<br>
        • To restore: import the .sql file via Hostinger → phpMyAdmin.
      </div>
      <div style="margin-top:.9rem;font-size:.75rem;color:#5d6b80">
        Backup file name: <span style="font-family:monospace">backup_<?= h(defined('DB_NAME')?DB_NAME:'database') ?>_<?= date('Y-m-d') ?>.sql</span>
      </div>
    </div>
  </div><!-- /stab-backup -->

  <!-- Role Picker Sheet -->
  <div class="rpicker-sheet" id="rpSheet" onclick="if(event.target===this)closeRP()">
    <div class="rpicker-inner">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem;padding-bottom:.6rem;border-bottom:1px solid #f0f0f0">
        <div id="rpAv" style="width:36px;height:36px;border-radius:50%;color:#fff;display:flex;align-items:center;justify-content:center;font-size:.85rem;font-weight:700;flex-shrink:0;background:#888"></div>
        <div style="flex:1"><div id="rpNm" style="font-size:.88rem;font-weight:800"></div><div id="rpCr" style="font-size:.75rem;color:#94a3b8"></div></div>
        <button onclick="closeRP()" style="background:#f1f5f9;border:none;border-radius:50%;width:28px;height:28px;cursor:pointer">✕</button>
      </div>
      <?php foreach($RL as $rv=>$ri): ?>
      <div class="rp-item" id="rpi_<?php echo $rv; ?>" onclick="pickRP('<?php echo $rv; ?>')">
        <span style="font-size:1rem"><?php echo $ri[1]; ?></span>
        <div style="flex:1"><div style="font-size:.78rem;font-weight:700"><?php echo $ri[0]; ?></div><div style="font-size:.75rem;color:#5d6b80"><?php echo $ri[2]; ?></div></div>
        <div class="rp-dot"></div>
      </div>
      <?php endforeach; ?>
      <div id="rpSave" style="display:none;margin-top:.6rem">
        <div id="rpPrev" style="background:#fff8e1;border:1.5px solid #ffe082;border-radius:8px;padding:.45rem .7rem;font-size:.75rem;color:#e65100;font-weight:600;margin-bottom:.4rem"></div>
        <button onclick="saveRP()" style="width:100%;padding:.6rem;background:#0A14E0;color:#fff;border:none;border-radius:10px;font-weight:800;cursor:pointer">✅ Save</button>
      </div>
    </div>
  </div>

<script>
// Tab switching
function switchStab(name, btn) {
  document.querySelectorAll('.stab-panel').forEach(function(p){ p.classList.remove('on'); });
  document.querySelectorAll('.stab').forEach(function(b){ b.classList.remove('on'); });
  document.getElementById('stab-'+name).classList.add('on');
  btn.classList.add('on');
}

// Activity form
function editAct(a) {
  document.getElementById('actId').value    = a.id;
  document.getElementById('actEmoji').value = a.emoji;
  document.getElementById('actName').value  = a.name;
  document.getElementById('actDesc').value  = a.description || '';
  document.getElementById('actReg').value   = a.reg_link || '';
  document.getElementById('actInfo').value  = a.info_url || '';
  document.getElementById('actColor').value = a.color || '#0A14E0';
  document.getElementById('actFormTitle').textContent = '✏️ Edit Activity: ' + a.name;
  document.getElementById('actForm').scrollIntoView({behavior:'smooth'});
}
function clearActForm() {
  document.getElementById('actId').value    = '0';
  document.getElementById('actEmoji').value = '🏆';
  document.getElementById('actName').value  = '';
  document.getElementById('actDesc').value  = '';
  document.getElementById('actReg').value   = '';
  document.getElementById('actInfo').value  = '';
  document.getElementById('actColor').value = '#0A14E0';
  document.getElementById('actFormTitle').textContent = '➕ Add New Activity';
}
function quickAct(emoji, name, color) {
  clearActForm();
  document.getElementById('actEmoji').value = emoji;
  document.getElementById('actName').value  = name;
  document.getElementById('actColor').value = color;
  document.getElementById('actForm').scrollIntoView({behavior:'smooth'});
  document.getElementById('actName').focus();
}

// Colour picker
function pickColor(c) {
  document.querySelector('[name=home_primary_color]').value = c;
  document.getElementById('priColorTxt').value = c;
  document.querySelectorAll('.color-swatch').forEach(function(s){ s.classList.remove('sel'); });
  event.target.classList.add('sel');
}

// Toggle switch visual update
document.querySelectorAll('input[type=checkbox]').forEach(function(cb){
  cb.addEventListener('change', function(){
    var track = this.nextElementSibling;
    var thumb = track.nextElementSibling;
    if(track && thumb){
      track.style.background = this.checked ? '#0A14E0' : '#cbd5e0';
      thumb.style.left       = this.checked ? '22px' : '2px';
    }
  });
});
// ── Roles Tab JS ──────────────────────────────────────────────
var _ud=<?php echo json_encode(array_map(function($u){return['id'=>(int)$u['id'],'name'=>$u['name'],'role'=>$u['role']];}, $_allUsers)); ?>;
var _rl=<?php echo json_encode(array_map(function($r){return $r[0];},$RL)); ?>;
var _rc={'secretary':'#0B1033','developer':'#6a1b9a','president':'#b71c1c','vice_president':'#c62828','joint_secretary':'#1A23C9','treasurer':'#2e7d32','sports_committee':'#e65100','cultural_committee':'#7b1fa2','finance_committee':'#1b5e20','committee_member':'#37474f','member':'#78909c'};
var _rUid=0,_rName='',_rOld='',_rNew='';

function toggleRa(id){
  var b=document.getElementById('ra-'+id);
  var a=document.getElementById('arr-'+id);
  if(b.classList.contains('open')){b.classList.remove('open');if(a)a.textContent='▼';}
  else{b.classList.add('open');if(a)a.textContent='▲';}
}
function assignFilter(q){
  q=q.toLowerCase();
  document.querySelectorAll('#ra-assign .mr').forEach(function(r){
    r.style.display=(!q||r.dataset.n.includes(q))?'':'none';
  });
}
function openRP(uid,name,role){
  _rUid=uid;_rName=name;_rOld=role;_rNew='';
  var rc=_rc[role]||'#888';
  document.getElementById('rpAv').textContent=name.charAt(0);
  document.getElementById('rpAv').style.background=rc;
  document.getElementById('rpNm').textContent=name;
  document.getElementById('rpCr').textContent='Current: '+(_rl[role]||role);
  document.querySelectorAll('.rp-item').forEach(function(el){el.classList.remove('sel');el.querySelector('.rp-dot').style.cssText='';});
  var cur=document.getElementById('rpi_'+role);
  if(cur){cur.classList.add('sel');cur.querySelector('.rp-dot').style.background=rc;cur.querySelector('.rp-dot').style.borderColor=rc;}
  document.getElementById('rpSave').style.display='none';
  document.getElementById('rpSheet').classList.add('open');
  document.body.style.overflow='hidden';
}
function closeRP(){document.getElementById('rpSheet').classList.remove('open');document.body.style.overflow='';}
function pickRP(rv){
  _rNew=rv;
  document.querySelectorAll('.rp-item').forEach(function(el){el.classList.remove('sel');el.querySelector('.rp-dot').style.cssText='';});
  var rc=_rc[rv]||'#0A14E0';
  var el=document.getElementById('rpi_'+rv);
  if(el){el.classList.add('sel');el.querySelector('.rp-dot').style.background=rc;el.querySelector('.rp-dot').style.borderColor=rc;}
  document.getElementById('rpPrev').textContent='Change '+_rName+': '+(_rl[_rOld]||_rOld)+' → '+(_rl[rv]||rv);
  document.getElementById('rpSave').style.display='block';
}
function saveRP(){
  if(!_rUid||!_rNew)return;
  var fd=new FormData();fd.append('action','set_role');fd.append('uid',_rUid);fd.append('role',_rNew);
  fetch(window.location.href,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      showToast('✅ Role updated!','g');
      var mr=document.querySelector('.mr[onclick*="openRP('+_rUid+',"]');
      if(mr){var rc=_rc[_rNew]||'#78909c';var rl=_rl[_rNew]||_rNew;mr.querySelector('.mr-av').style.background=rc;var badge=mr.querySelector('.mr-badge');if(badge){badge.style.background=rc;badge.textContent=rl;}}
      _ud.forEach(function(u){if(u.id===_rUid)u.role=_rNew;});
      closeRP();
    }else showToast('❌ '+(res.msg||'Error'),'e');
  });
}
function modSrch(inp,mod){
  var q=inp.value.toLowerCase();
  var dd=document.getElementById('mdd_'+mod);
  if(!q){dd.style.display='none';return;}
  var matches=_ud.filter(function(u){return u.name.toLowerCase().includes(q);}).slice(0,6);
  if(!matches.length){dd.style.display='none';return;}
  dd.innerHTML='';
  matches.forEach(function(u){
    var d=document.createElement('div');
    d.style.cssText='padding:.4rem .6rem;cursor:pointer;font-size:.75rem;border-bottom:1px solid #f0f0f0';
    d.textContent=u.name+' ('+(_rl[u.role]||u.role)+')';
    d.onmousedown=d.ontouchstart=function(e){if(e)e.preventDefault();addMod(u.id,u.name,mod,inp,dd);};
    dd.appendChild(d);
  });
  dd.style.display='block';
}
function addMod(uid,name,mod,inp,dd){
  dd.style.display='none';inp.value='';
  var days=prompt('Make '+name+' admin of "'+mod+'".\n\nEnter number of days (e.g. 7, 30) for a TEMPORARY Guest Admin,\nor enter 0 for PERMANENT module admin:','0');
  if(days===null)return; // cancelled
  days=parseInt(days)||0;
  var fd=new FormData();fd.append('action','set_module_admin');fd.append('uid',uid);fd.append('module',mod);fd.append('expiry_days',days);
  fetch(window.location.href,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){showToast('✅ '+name+(days>0?' added for '+days+' days':' added (permanent)'),'g');setTimeout(function(){location.reload();},900);}
    else showToast('❌ '+(res.msg||'Error'),'e');
  });
}
function rmMod(uid,mod,btn){
  var fd=new FormData();fd.append('action','set_module_admin');fd.append('uid',uid);fd.append('module',mod);fd.append('remove','1');
  fetch(window.location.href,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){showToast('Removed','');btn.closest('.mod-tag').remove();}
  });
}
function doApprove(uid){
  if(!confirm('Approve this member?'))return;
  var fd=new FormData();fd.append('action','approve_user');fd.append('uid',uid);
  fetch(window.location.href,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      showToast('✅ Approved: '+res.name,'g');
      var row=document.getElementById('apr_'+uid);if(row)row.remove();
      // Open WhatsApp to notify member
      if(res.wa){
        setTimeout(function(){window.open(res.wa,'_blank');},600);
      }
    } else showToast('❌ Error','e');
  });
}
function doReject(uid){
  var reason=prompt('Rejection reason (optional):');
  if(reason===null)return; // cancelled
  var fd=new FormData();fd.append('action','reject_user');fd.append('uid',uid);fd.append('reason',reason||'');
  fetch(window.location.href,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      showToast('Rejected: '+res.name,'');
      var row=document.getElementById('apr_'+uid);if(row)row.remove();
      if(res.wa){
        setTimeout(function(){window.open(res.wa,'_blank');},600);
      }
    }
  });
}
function sendNotif(){
  var title = document.getElementById('ntitle').value.trim();
  var body  = document.getElementById('nbody').value.trim();
  var url   = document.getElementById('nurl').value.trim() || '/';
  var target= document.getElementById('ntarget').value;
  if(!title||!body){ showToast('Title and message required','e'); return; }
  var btn = event.target; btn.disabled=true; btn.textContent='Sending...';
  var fd=new FormData();
  fd.append('action','send'); fd.append('title',title);
  fd.append('body',body); fd.append('url',url); fd.append('target',target);
  fetch('/push_notify.php',{method:'POST',body:fd})
    .then(function(r){return r.json();})
    .then(function(res){
      btn.disabled=false; btn.textContent='🔔 Send Notification';
      if(res.ok){
        showToast('✅ Sent to '+res.sent+' devices!','g');
        document.getElementById('ntitle').value='';
        document.getElementById('nbody').value='';
        setTimeout(function(){location.reload();},1500);
      } else showToast('❌ '+(res.msg||'Error'),'e');
    }).catch(function(){btn.disabled=false;btn.textContent='🔔 Send Notification';showToast('❌ Network error','e');});
}

function showToast(msg,t){
  var el=document.getElementById('stToast');
  if(!el){el=document.createElement('div');el.id='stToast';el.style.cssText='position:fixed;bottom:80px;left:50%;transform:translateX(-50%) translateY(40px);padding:.55rem 1.2rem;border-radius:25px;font-size:.8rem;font-weight:700;z-index:9999;opacity:0;transition:all .3s;white-space:nowrap;color:#fff';document.body.appendChild(el);}
  el.textContent=msg;el.style.background=t==='g'?'#2e7d32':t==='e'?'#b71c1c':'#0A14E0';
  el.style.opacity='1';el.style.transform='translateX(-50%) translateY(0)';
  setTimeout(function(){el.style.opacity='0';el.style.transform='translateX(-50%) translateY(40px)';},2500);
}
</script>

<?php require_once __DIR__ . '/../includes/footer.php'; ?>
