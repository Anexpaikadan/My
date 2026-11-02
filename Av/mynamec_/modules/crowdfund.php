<?php
// ============================================================
// modules/crowdfund.php — ❤️ CrowdFund & Charity
// Aishwarya Arts & Sports Club — PHP 7.3+ compatible
// ============================================================
$pageOG = [
  'title' => '❤️ Crowd Funding — Aishwarya Arts & Sports Club',
  'desc'  => 'Support our community campaigns — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/crowdfund.php',
];
require_once __DIR__ . '/../includes/config.php';
$me      = currentUser();           // null for guests
$isGuest = !$me;
// Module admin: Finance Committee + Secretary + Developer
$isAdmin = $me ? (isFinanceAdmin($me['role']) || isModuleAdmin('crowdfund', $me)) : false;
$uid     = $me ? (int)$me['id'] : 0;
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$PLACE   = setting('CLUB_PLACE','Vettikkattiri');
$SITE    = rtrim(SITE_URL,'/');

// ── Tables ──────────────────────────────────────────────────
try { db()->exec("CREATE TABLE IF NOT EXISTS cf_campaigns(
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(300) NOT NULL,
  description TEXT,
  story TEXT,
  category ENUM('charity','medical','education','sports','arts','disaster','other') DEFAULT 'charity',
  target_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
  raised_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
  donor_count INT DEFAULT 0,
  cover_image VARCHAR(500),
  organizer_name VARCHAR(200),
  organizer_phone VARCHAR(20),
  upi_id VARCHAR(200),
  deadline DATE,
  status ENUM('pending','active','paused','completed','rejected') DEFAULT 'pending',
  is_featured TINYINT(1) DEFAULT 0,
  created_by INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS cf_donations(
  id INT AUTO_INCREMENT PRIMARY KEY,
  campaign_id INT NOT NULL,
  donor_id INT,
  donor_name VARCHAR(200) NOT NULL,
  donor_phone VARCHAR(20),
  amount DECIMAL(10,2) NOT NULL,
  payment_method VARCHAR(30) DEFAULT 'upi',
  upi_ref VARCHAR(200),
  screenshot VARCHAR(500),
  message TEXT,
  status ENUM('pending','verified','rejected') DEFAULT 'pending',
  receipt_no VARCHAR(50),
  donated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS cf_updates(
  id INT AUTO_INCREMENT PRIMARY KEY,
  campaign_id INT NOT NULL,
  title VARCHAR(200),
  body TEXT,
  posted_by INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

// ── Upload helper ────────────────────────────────────────────
function cfUp($field, $sub='crowdfund') {
  if (empty($_FILES[$field]) || $_FILES[$field]['error']!==0) return null;
  $ext = strtolower(pathinfo($_FILES[$field]['name'],PATHINFO_EXTENSION));
  if (!in_array($ext,['jpg','jpeg','png','webp'])) return null;
  if ($_FILES[$field]['size'] > 8*1024*1024) return null;
  $dir = __DIR__.'/../assets/uploads/'.$sub.'/';
  if (!is_dir($dir)) mkdir($dir,0755,true);
  $fn = $sub.'_'.time().'_'.mt_rand(1000,9999).'.'.$ext;
  if (!move_uploaded_file($_FILES[$field]['tmp_name'],$dir.$fn)) return null;
  img_optimize($dir.$fn); return $sub.'/'.$fn;
}

// ── ACTIONS ─────────────────────────────────────────────────
$flash = null;
$act   = $_POST['act'] ?? '';

// Save campaign (create/edit)
if ($act === 'save_campaign' && $isAdmin) { require_once __DIR__ . '/../includes/sudo.php'; sudo_require(); 
  $cid    = (int)($_POST['cid'] ?? 0);
  $title  = trim($_POST['title'] ?? '');
  $desc   = trim($_POST['description'] ?? '');
  $story  = trim($_POST['story'] ?? '');
  $cat    = $_POST['category'] ?? 'charity';
  $target = (float)($_POST['target'] ?? 0);
  $dl     = $_POST['deadline'] ?? null;
  $upi    = trim($_POST['upi_id'] ?? '');
  $oname  = trim($_POST['organizer_name'] ?? $me['name']);
  $ophone = trim($_POST['organizer_phone'] ?? '');
  $status = $isAdmin ? ($_POST['status'] ?? 'active') : 'pending';
  $feat   = $isAdmin && isset($_POST['is_featured']) ? 1 : 0;
  $cover  = cfUp('cover_image');

  if (!$title || $target <= 0) {
    $flash = ['err','Title and target amount are required.'];
  } else {
    if ($cid > 0) {
      $old = db()->prepare("SELECT cover_image FROM cf_campaigns WHERE id=?");
      $old->execute([$cid]); $old = $old->fetch();
      if (!$cover) $cover = $old['cover_image'] ?? null;
      db()->prepare("UPDATE cf_campaigns SET title=?,description=?,story=?,category=?,target_amount=?,deadline=?,upi_id=?,organizer_name=?,organizer_phone=?,status=?,is_featured=?,cover_image=? WHERE id=?")
         ->execute([$title,$desc,$story,$cat,$target,$dl?:null,$upi,$oname,$ophone,$status,$feat,$cover,$cid]);
      $flash = ['ok','✅ Campaign updated!'];
    } else {
      db()->prepare("INSERT INTO cf_campaigns(title,description,story,category,target_amount,deadline,upi_id,organizer_name,organizer_phone,cover_image,status,is_featured,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)")
         ->execute([$title,$desc,$story,$cat,$target,$dl?:null,$upi,$oname,$ophone,$cover,$status,$feat,$uid]);
      $cid = (int)db()->lastInsertId();
      $flash = ['ok','✅ Campaign '.($isAdmin?'created & live!':'submitted for approval!')];
      if (!$isAdmin) { header('Location: '.url('modules/crowdfund.php').'?flash=submitted'); exit; }
    }
    header('Location: '.url('modules/crowdfund.php').'?view=campaign&id='.$cid.'&flash=saved'); exit;
  }
}

// Admin: status change
if ($isAdmin && in_array($act,['approve','pause','complete','reject'])) {
  $cid = (int)($_POST['cid'] ?? 0);
  $map = ['approve'=>'active','pause'=>'paused','complete'=>'completed','reject'=>'rejected'];
  db()->prepare("UPDATE cf_campaigns SET status=? WHERE id=?")->execute([$map[$act],$cid]);
  header('Location: '.url('modules/crowdfund.php').'?view=campaign&id='.$cid.'&flash=status'); exit;
}

// Delete campaign
if ($isAdmin && $act === 'del_campaign') { require_once __DIR__ . '/../includes/sudo.php'; sudo_require(); 
  $cid = (int)($_POST['cid'] ?? 0);
  if ($cid > 0) {
    try { db()->prepare("DELETE FROM cf_donations WHERE campaign_id=?")->execute([$cid]); } catch(Exception $e){}
    try { db()->prepare("DELETE FROM cf_updates WHERE campaign_id=?")->execute([$cid]); } catch(Exception $e){}
    db()->prepare("DELETE FROM cf_campaigns WHERE id=?")->execute([$cid]);
  }
  header('Location: '.url('modules/crowdfund.php').'?flash=deleted'); exit;
}

// Post update
if ($isAdmin && $act === 'post_update') {
  $cid   = (int)($_POST['cid'] ?? 0);
  $utit  = trim($_POST['utitle'] ?? '');
  $ubody = trim($_POST['ubody'] ?? '');
  if ($utit && $ubody) {
    db()->prepare("INSERT INTO cf_updates(campaign_id,title,body,posted_by) VALUES(?,?,?,?)")->execute([$cid,$utit,$ubody,$uid]);
  }
  header('Location: '.url('modules/crowdfund.php').'?view=campaign&id='.$cid.'#updates'); exit;
}

// Donate
if ($act === 'donate') {
  $cid    = (int)($_POST['cid'] ?? 0);
  $amount = (float)($_POST['amount'] ?? 0);
  $method = $_POST['method'] ?? 'upi';
  $ref    = trim($_POST['upi_ref'] ?? '');
  $domsg  = trim($_POST['message'] ?? '');
  $anon   = isset($_POST['anonymous']) ? 1 : 0;
  // Donor name/phone: members use their account; guests type their own
  $typedName  = trim($_POST['donor_name'] ?? '');
  $typedPhone = trim($_POST['donor_phone'] ?? '');
  if ($anon) {
    $dname = 'Anonymous';
  } elseif ($me) {
    $dname = $me['name'];
  } else {
    $dname = $typedName !== '' ? $typedName : 'Well-wisher';
  }
  $dphone = $me ? ($me['whatsapp_number'] ?? '') : $typedPhone;
  $ss     = cfUp('screenshot','cf_receipts');
  $recNo  = 'AASC-'.date('Ymd').'-'.strtoupper(substr(md5(uniqid()),0,6));

  if ($amount < 1) {
    $flash = ['err','Enter a valid amount.'];
  } elseif (!$me && !$anon && $typedName === '') {
    $flash = ['err','Please enter your name (or tick anonymous).'];
  } elseif (!$ss && $method !== 'cash') {
    $flash = ['err','📷 Please upload a payment screenshot so the admin can verify your donation. (Only cash donations can skip this.)'];
  } else {
    db()->prepare("INSERT INTO cf_donations(campaign_id,donor_id,donor_name,donor_phone,amount,payment_method,upi_ref,screenshot,message,status,receipt_no) VALUES(?,?,?,?,?,?,?,?,?,?,?)")
       ->execute([$cid,($uid?:null),$dname,$dphone,$amount,$method,$ref,$ss,$domsg,'pending',$recNo]);
    $flash = ['ok','✅ Donation recorded! Receipt: <b>'.$recNo.'</b>. Admin will verify soon.'];
  }
}

// Admin verify/reject donation
if ($isAdmin && in_array($act,['verify_donation','reject_donation'])) { require_once __DIR__ . '/../includes/sudo.php'; sudo_require(); 
  $did = (int)($_POST['did'] ?? 0);
  if ($act === 'verify_donation') {
    $don = db()->prepare("SELECT * FROM cf_donations WHERE id=?"); $don->execute([$did]); $don=$don->fetch();
    if ($don && $don['status']==='pending') {
      // capture progress BEFORE this donation
      $cBefore = db()->prepare("SELECT raised_amount,target_amount,title FROM cf_campaigns WHERE id=?");
      $cBefore->execute([$don['campaign_id']]); $cBefore=$cBefore->fetch();
      $before = ($cBefore && $cBefore['target_amount']>0) ? ($cBefore['raised_amount']/$cBefore['target_amount'])*100 : 0;

      db()->prepare("UPDATE cf_donations SET status='verified' WHERE id=?")->execute([$did]);
      db()->prepare("UPDATE cf_campaigns SET raised_amount=raised_amount+?,donor_count=donor_count+1 WHERE id=?")->execute([$don['amount'],$don['campaign_id']]);

      // WhatsApp thank-you to the donor (auto-sends if UltraMsg configured)
      if (!empty($don['donor_phone']) && function_exists('waNotify')) {
        $tcamp = $cBefore['title'] ?? 'our campaign';
        $thx = "🙏 Thank you, ".$don['donor_name']."!\n\n"
             . "Your donation of ₹".number_format($don['amount'],2)." to \"".$tcamp."\" has been verified.\n"
             . "Receipt: ".$don['receipt_no']."\n\n"
             . "With gratitude,\n".$CLUB." · ".$PLACE;
        try { waNotify($don['donor_phone'], $thx); } catch (Exception $e) {}
      }

      // progress AFTER — celebrate crossing a milestone
      if ($cBefore && $cBefore['target_amount']>0) {
        $after = (($cBefore['raised_amount']+$don['amount'])/$cBefore['target_amount'])*100;
        $milestones = [100,75,50,25];
        foreach ($milestones as $ms) {
          if ($before < $ms && $after >= $ms) {
            $emoji = $ms>=100 ? '🎉🏆' : ($ms>=75 ? '🔥' : ($ms>=50 ? '💪' : '🌱'));
            $body  = $ms>=100
              ? $emoji.' GOAL REACHED! "'.$cBefore['title'].'" has hit 100% of its target. Thank you to everyone who donated! ❤️'
              : $emoji.' "'.$cBefore['title'].'" is now '.$ms.'% funded! Help us reach the goal — every donation counts.';
            $link = rtrim(SITE_URL,'/').'/modules/crowdfund.php?view=campaign&id='.$don['campaign_id'];
            try {
              db()->prepare("INSERT INTO feed_posts(user_id,body,media_type,link_url,link_title,ref_type,ref_id)
                             VALUES(?,?,?,?,?,?,?)")
                 ->execute([$uid,$body,'link',$link,'View Campaign','cf_milestone',$don['campaign_id']]);
            } catch (Exception $e) {}
            break; // only the highest milestone crossed
          }
        }
      }
    }
  } else {
    db()->prepare("UPDATE cf_donations SET status='rejected' WHERE id=?")->execute([$did]);
  }
  $back = $_POST['back'] ?? '';
  if ($back === 'pending') { header('Location: '.url('modules/crowdfund.php').'?view=pending'); exit; }
  header('Location: '.url('modules/crowdfund.php').'?view=campaign&id='.($_POST['cid']??0)); exit;
}

// Flash from redirect
if (isset($_GET['flash'])) {
  $flmap = ['submitted'=>['ok','Campaign submitted for review!'],'deleted'=>['ok','Campaign deleted.'],'saved'=>['ok','Saved!'],'status'=>['ok','Status updated.']];
  if (isset($flmap[$_GET['flash']])) $flash = $flmap[$_GET['flash']];
}

// ── FETCH DATA ───────────────────────────────────────────────
$view   = $_GET['view'] ?? 'list';
$campId = (int)($_GET['id'] ?? 0);
$camp = $donations = $cfupdates = $myDon = null;

if ($view === 'campaign' && $campId) {
  $st = db()->prepare("SELECT * FROM cf_campaigns WHERE id=?"); $st->execute([$campId]); $camp=$st->fetch();
  if (!$camp) { $view='list'; }
  else {
    // Per-campaign rich link preview (WhatsApp/Facebook)
    $ogImg = $camp['cover_image'] ? $SITE.'/assets/uploads/'.$camp['cover_image'] : 'https://mynamecc.online/og_image.php';
    $ogDesc = $camp['description'] ?: ('Support this campaign — '.$CLUB);
    if (mb_strlen($ogDesc) > 160) $ogDesc = mb_substr($ogDesc,0,157).'…';
    $pageOG = [
      'title' => '❤️ '.$camp['title'].' — '.$CLUB,
      'desc'  => $ogDesc,
      'image' => $ogImg,
      'url'   => $SITE.'/modules/crowdfund.php?view=campaign&id='.$campId,
    ];
    $donations = db()->prepare("SELECT * FROM cf_donations WHERE campaign_id=? ORDER BY donated_at DESC"); $donations->execute([$campId]); $donations=$donations->fetchAll();
    $cfupdates = db()->prepare("SELECT u.*,m.name poster FROM cf_updates u LEFT JOIN users m ON m.id=u.posted_by WHERE u.campaign_id=? ORDER BY u.created_at DESC"); $cfupdates->execute([$campId]); $cfupdates=$cfupdates->fetchAll();
    $myDon     = $uid ? (function() use($campId,$uid){ $q=db()->prepare("SELECT * FROM cf_donations WHERE campaign_id=? AND donor_id=? ORDER BY donated_at DESC"); $q->execute([$campId,$uid]); return $q->fetchAll(); })() : [];
    // Top donors by total verified amount
    $topDonors = db()->prepare("SELECT donor_name, SUM(amount) total, COUNT(*) cnt
      FROM cf_donations WHERE campaign_id=? AND status='verified'
      GROUP BY donor_name ORDER BY total DESC LIMIT 5");
    $topDonors->execute([$campId]); $topDonors = $topDonors->fetchAll();
  }
}

if ($view === 'edit' && $campId && $isAdmin) {
  $st = db()->prepare("SELECT * FROM cf_campaigns WHERE id=?"); $st->execute([$campId]); $editCamp=$st->fetch();
}

$campaigns = db()->query("SELECT * FROM cf_campaigns ORDER BY is_featured DESC, created_at DESC")->fetchAll();
$totalRaised = (float)db()->query("SELECT COALESCE(SUM(raised_amount),0) FROM cf_campaigns WHERE status='active'")->fetchColumn();
$activeCnt   = (int)db()->query("SELECT COUNT(*) FROM cf_campaigns WHERE status='active'")->fetchColumn();
$totalDonors = (int)db()->query("SELECT COUNT(DISTINCT donor_id) FROM cf_donations WHERE status='verified'")->fetchColumn();

$pendingDons = [];
if ($isAdmin) {
  $pd = db()->query("SELECT d.*,c.title camp_title,c.id camp_id FROM cf_donations d JOIN cf_campaigns c ON c.id=d.campaign_id WHERE d.status='pending' ORDER BY d.donated_at DESC");
  $pendingDons = $pd ? $pd->fetchAll() : [];
}

$pageTitle = '❤️ Crowd Funding — '.$CLUB;
require_once __DIR__.'/../includes/header.php';
?>
<style>
:root{--cf1:#121A5C;--cf2:#0A14E0;--cfa:#D4A017;--cfg:#1b5e20;--cfr:#b71c1c}
.cfw{max-width:680px;margin:0 auto;padding-bottom:3rem}

/* Hero */
.cf-hero{background:linear-gradient(135deg,#0a1f3d,#121A5C 50%,#1A23C9);padding:1.8rem 1rem 1.4rem;text-align:center;color:#fff}
.cf-hero h1{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.6rem;letter-spacing:.01em;margin-bottom:.2rem}
.cf-hero p{font-size:.75rem;color:rgba(255,255,255,.55)}

/* Stats bar */
.cf-stats{display:grid;grid-template-columns:repeat(3,1fr);background:var(--cf1);border-bottom:3px solid var(--cfa)}
.cf-stat{padding:.65rem .5rem;text-align:center;border-right:1px solid rgba(255,255,255,.08)}
.cf-stat:last-child{border-right:none}
.cf-stat-n{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.2rem;color:var(--cfa);line-height:1}
.cf-stat-l{font-size:.62rem;color:rgba(255,255,255,.8);text-transform:uppercase;letter-spacing:.1em}

/* Pending bar */
.pending-bar{background:linear-gradient(135deg,#b71c1c,#c62828);color:#fff;padding:.75rem 1rem;display:flex;align-items:center;justify-content:space-between;gap:.7rem}
.pending-bar a{background:#fff;color:#b71c1c;padding:.38rem .9rem;border-radius:8px;font-weight:700;font-size:.78rem;text-decoration:none;flex-shrink:0}

/* Campaign card */
.cf-card{background:#fff;border-radius:16px;box-shadow:0 3px 16px rgba(0,0,0,.08);border:1px solid rgba(0,0,0,.07);overflow:hidden;margin-bottom:1rem}
.cf-cover{height:180px;position:relative;overflow:hidden;background:#F5F7FF}
.cf-cover img{width:100%;height:100%;object-fit:cover}
.cf-cover-ph{height:100%;display:flex;align-items:center;justify-content:center;font-size:3rem;background:linear-gradient(135deg,rgba(26,58,107,.06),rgba(26,58,107,.03))}
.cf-cat-badge{position:absolute;top:.6rem;left:.6rem;padding:.18rem .6rem;border-radius:20px;font-size:.62rem;font-weight:700;color:#fff}
.cf-feat{position:absolute;top:.6rem;right:.6rem;background:var(--cfa);color:#fff;padding:.18rem .6rem;border-radius:20px;font-size:.62rem;font-weight:700}
/* Admin delete on card */
.cf-del-btn{position:absolute;bottom:.6rem;right:.6rem;background:rgba(183,28,28,.9);color:#fff;border:none;border-radius:8px;padding:.3rem .65rem;font-size:.68rem;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:.25rem}

.cf-body{padding:1rem}
.cf-title{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.92rem;letter-spacing:.01em;color:var(--cf1);margin-bottom:.3rem;line-height:1.25}
.cf-desc{font-size:.8rem;color:#4a5568;line-height:1.55;margin-bottom:.8rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

/* Progress */
.cf-prog-wrap{margin-bottom:.75rem}
.cf-prog-bar{height:7px;background:#E3E7F5;border-radius:10px;overflow:hidden;margin-bottom:.4rem}
.cf-prog-fill{height:100%;border-radius:10px;background:linear-gradient(90deg,#1b5e20,#4caf50);transition:width 1.2s}
.cf-prog-row{display:flex;justify-content:space-between;align-items:baseline}
.cf-raised{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.96rem;color:var(--cfg);letter-spacing:.01em}
.cf-target{font-size:.7rem;color:#8a93a8}
.cf-pct{font-size:.75rem;font-weight:700;color:var(--cfg)}

.cf-meta{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.8rem}
.cf-chip{font-size:.68rem;color:#4a5568;background:#F5F7FF;padding:.2rem .6rem;border-radius:20px;display:flex;align-items:center;gap:.25rem}

/* Status badges */
.st{display:inline-block;padding:.18rem .65rem;border-radius:20px;font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em}
.st-active{background:#e8f5e9;color:#1b5e20}.st-pending{background:#fff8e1;color:#e65100}
.st-completed{background:#ECEEFF;color:#0A14E0}.st-rejected{background:#ffebee;color:#b71c1c}
.st-paused{background:#f3e5f5;color:#7b1fa2}

/* Buttons */
.btn-cf{display:flex;align-items:center;justify-content:center;gap:.35rem;padding:.6rem 1rem;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.84rem;cursor:pointer;border:none;text-decoration:none;transition:all .2s}
.btn-cf-primary{background:var(--cf1);color:#fff;flex:1}
.btn-cf-primary:hover{background:var(--cf2)}
.btn-cf-outline{background:transparent;border:1.5px solid var(--cf1);color:var(--cf1)}
.btn-cf-outline:hover{background:var(--cf1);color:#fff}
.btn-cf-red{background:var(--cfr);color:#fff}
.btn-cf-red:hover{background:#c62828}
.btn-cf-green{background:#2e7d32;color:#fff}
.btn-cf-wa{background:#25d366;color:#fff}

/* Detail */
.cf-detail-img{width:100%;max-height:260px;object-fit:cover;border-radius:14px;margin-bottom:1rem}
.cf-big-prog{background:#fff;border-radius:14px;padding:1.2rem;box-shadow:0 3px 14px rgba(0,0,0,.08);border:1px solid rgba(0,0,0,.07);margin-bottom:1rem}
.cf-amt-big{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.76rem;color:var(--cfg);line-height:1;letter-spacing:.01em}
.cf-bar-big{height:12px;background:#E3E7F5;border-radius:10px;overflow:hidden;margin:.9rem 0}
.cf-bar-fill{height:100%;border-radius:10px;background:linear-gradient(90deg,#1b5e20,#4caf50,#81c784)}

/* Quick stats */
.cf-qs{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-bottom:.8rem}
.cf-qs-box{background:#F7F8FF;border-radius:10px;padding:.6rem .4rem;text-align:center}
.cf-qs-n{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.0rem;color:var(--cf1);line-height:1}
.cf-qs-l{font-size:.58rem;color:#5f6880;text-transform:uppercase;letter-spacing:.08em}

/* UPI box */
.upi-box{background:#F5F7FF;border:2px dashed rgba(10,20,224,.2);border-radius:12px;padding:1rem;text-align:center;margin-bottom:1rem}
.upi-id{font-weight:700;font-size:.9rem;color:var(--cf1);word-break:break-all}
.copy-btn{background:var(--cf1);color:#fff;border:none;border-radius:7px;padding:.35rem .8rem;font-size:.75rem;font-weight:700;cursor:pointer;margin-top:.5rem}

/* Donate form */
.cf-donate{background:#fff;border-radius:14px;padding:1.2rem;box-shadow:0 3px 14px rgba(0,0,0,.08);border:1px solid rgba(0,0,0,.07);margin-bottom:1rem}
.amt-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.4rem;margin-bottom:.7rem}
.amt-btn{border:2px solid #E3E7F5;background:#F7F8FF;border-radius:8px;padding:.5rem;font-weight:700;font-size:.84rem;cursor:pointer;transition:all .2s}
.amt-btn.on,.amt-btn:hover{border-color:var(--cf1);background:rgba(26,58,107,.06);color:var(--cf1)}

/* Tabs */
.cf-tabs{display:flex;border-bottom:2px solid #E3E7F5;margin-bottom:1rem;overflow-x:auto;scrollbar-width:none}
.cf-tab{padding:.6rem .95rem;font-size:.8rem;font-weight:600;color:#5f6880;cursor:pointer;border-bottom:2.5px solid transparent;margin-bottom:-2px;white-space:nowrap;transition:all .2s}
.cf-tab.on{color:var(--cf1);border-bottom-color:var(--cf1)}

/* Donors */
.donor-row{display:flex;align-items:center;gap:.7rem;padding:.6rem 0;border-bottom:1px solid #F5F7FF}
.donor-av{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,var(--cf1),var(--cf2));color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.82rem;flex-shrink:0}
.don-badge{display:inline-block;font-size:.6rem;padding:.1rem .42rem;border-radius:20px;font-weight:700}
.db-pending{background:#fff8e1;color:#e65100}.db-verified{background:#e8f5e9;color:#1b5e20}.db-rejected{background:#ffebee;color:#b71c1c}

/* Admin */
.admin-panel{background:#fff;border-radius:14px;border:1.5px solid rgba(11,16,51,.15);overflow:hidden;margin-bottom:1rem}
.admin-panel-head{background:linear-gradient(135deg,#0B1033,#0A14E0);padding:.7rem 1rem;display:flex;align-items:center;gap:.5rem}
.admin-panel-head h3{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.8rem;letter-spacing:.01em;color:#fff;margin:0}
.admin-panel-body{padding:1rem}
.admin-btns{display:flex;gap:.4rem;flex-wrap:wrap}
.admin-btns form{display:inline}

/* Category colors */
.cat-charity{background:#b71c1c}.cat-medical{background:#c62828}.cat-education{background:#121A5C}
.cat-sports{background:#1b5e20}.cat-arts{background:#7b1fa2}.cat-disaster{background:#e65100}.cat-other{background:#455a64}

/* Form card */
.cf-form-card{background:#fff;border-radius:14px;box-shadow:0 3px 14px rgba(0,0,0,.08);border:1px solid rgba(0,0,0,.07);padding:1.3rem;margin-bottom:1rem}

/* Toast */
.cf-toast{position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%) translateY(40px);background:var(--cf1);color:#fff;padding:.6rem 1.2rem;border-radius:25px;font-size:.8rem;font-weight:700;z-index:9999;opacity:0;transition:all .3s;white-space:nowrap}
.cf-toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.cf-toast.g{background:#2e7d32}.cf-toast.e{background:#b71c1c}

.empty-cf{text-align:center;padding:2.5rem 1rem;color:#5f6880}
</style>

<div class="cf-hero">
  <h1>❤️ CROWD FUNDING & CHARITY</h1>
  <p><?php echo h($CLUB); ?> · Together we help <?php echo h($PLACE); ?></p>
  <button onclick="openHowTo()" style="margin-top:.7rem;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.4);color:#fff;border-radius:22px;padding:.42rem 1.1rem;font-size:.78rem;font-weight:700;cursor:pointer;font-family:inherit">❓ How to Donate</button>
</div>
<div style="height:4px;background:repeating-linear-gradient(90deg,#D4A017 0,#D4A017 10px,#B71C1C 10px,#B71C1C 20px,#0A14E0 20px,#0A14E0 30px,#F5C842 30px,#F5C842 40px)"></div>
<div class="cf-stats">
  <div class="cf-stat"><div class="cf-stat-n">₹<?php echo number_format($totalRaised); ?></div><div class="cf-stat-l">Total Raised</div></div>
  <div class="cf-stat"><div class="cf-stat-n"><?php echo $activeCnt; ?></div><div class="cf-stat-l">Active</div></div>
  <div class="cf-stat"><div class="cf-stat-n"><?php echo $totalDonors; ?></div><div class="cf-stat-l">Donors</div></div>
</div>

<?php if($isAdmin && count($pendingDons)>0 && $view==='list'): ?>
<div class="pending-bar">
  <div>
    <div style="font-weight:700;font-size:.88rem">🔔 <?php echo count($pendingDons); ?> donation<?php echo count($pendingDons)>1?'s':''; ?> waiting approval</div>
    <div style="font-size:.72rem;color:rgba(255,255,255,.75)">Verify payment screenshots</div>
  </div>
  <a href="?view=pending">✅ Review →</a>
</div>
<?php endif; ?>

<div class="cfw" style="padding:1rem">

<?php if($flash): ?>
<div style="padding:.55rem .9rem;border-radius:10px;margin-bottom:.8rem;font-size:.82rem;font-weight:600;<?php echo $flash[0]==='ok'?'background:#e8f5e9;color:#1b5e20':'background:#ffebee;color:#b71c1c'; ?>">
  <?php echo $flash[1]; ?>
</div>
<?php endif; ?>

<?php
/* ═══════ CAMPAIGN DETAIL ═══════ */
if ($view==='campaign' && !empty($camp)):
  $pct  = $camp['target_amount']>0 ? min(100,round(($camp['raised_amount']/$camp['target_amount'])*100)) : 0;
  $days = $camp['deadline'] ? max(0,ceil((strtotime($camp['deadline'])-time())/86400)) : null;
  $upiId = $camp['upi_id'] ?: '';
  $catIcons=['charity'=>'❤️','medical'=>'🏥','education'=>'📚','sports'=>'⚽','arts'=>'🎭','disaster'=>'🆘','other'=>'🌟'];
?>
<a href="<?php echo url('modules/crowdfund.php'); ?>" style="display:inline-flex;align-items:center;gap:.3rem;font-size:.8rem;font-weight:700;color:var(--cf1);text-decoration:none;margin-bottom:.8rem">← All Campaigns</a>

<?php if($camp['cover_image']): ?>
<img src="<?php echo url('assets/uploads/'.$camp['cover_image']); ?>" class="cf-detail-img" alt="">
<?php else: ?>
<div style="width:100%;height:140px;border-radius:14px;background:linear-gradient(135deg,rgba(26,58,107,.08),rgba(26,58,107,.04));display:flex;align-items:center;justify-content:center;font-size:3.5rem;margin-bottom:1rem"><?php echo $catIcons[$camp['category']]??'❤️'; ?></div>
<?php endif; ?>

<div style="margin-bottom:.5rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
  <span class="st st-<?php echo $camp['status']; ?>"><?php echo ucfirst($camp['status']); ?></span>
  <span class="cf-chip"><?php echo $catIcons[$camp['category']]??''; ?> <?php echo ucfirst($camp['category']); ?></span>
  <?php if($camp['is_featured']): ?><span style="background:var(--cfa);color:#fff;font-size:.62rem;font-weight:700;padding:.18rem .6rem;border-radius:20px">⭐ Featured</span><?php endif; ?>
</div>

<h2 style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.28rem;letter-spacing:.01em;color:var(--cf1);margin-bottom:.5rem;line-height:1.2"><?php echo h($camp['title']); ?></h2>

<!-- Big progress -->
<div class="cf-big-prog">
  <div class="cf-amt-big">₹<?php echo number_format($camp['raised_amount']); ?></div>
  <div style="font-size:.78rem;color:#5f6880">raised of ₹<?php echo number_format($camp['target_amount']); ?> goal</div>
  <div class="cf-bar-big"><div class="cf-bar-fill" style="width:<?php echo $pct; ?>%"></div></div>
  <div class="cf-qs">
    <div class="cf-qs-box"><div class="cf-qs-n"><?php echo $pct; ?>%</div><div class="cf-qs-l">Funded</div></div>
    <div class="cf-qs-box"><div class="cf-qs-n"><?php echo $camp['donor_count']; ?></div><div class="cf-qs-l">Donors</div></div>
    <div class="cf-qs-box"><div class="cf-qs-n"><?php echo $days!==null?$days:'∞'; ?></div><div class="cf-qs-l">Days Left</div></div>
  </div>
  <div style="display:flex;gap:.5rem">
    <button class="btn-cf btn-cf-wa" onclick="shareWA()" style="flex:1">💬 Share on WhatsApp</button>
    <button class="btn-cf btn-cf-outline" onclick="copyLink()" style="flex:0 0 auto">🔗 Copy</button>
  </div>
</div>

<!-- Tabs -->
<div class="cf-tabs">
  <div class="cf-tab on" onclick="cftab('story',this)">📖 Story</div>
  <?php if(!empty($cfupdates)): ?><div class="cf-tab" onclick="cftab('updates',this)">📢 Updates (<?php echo count($cfupdates); ?>)</div><?php endif; ?>
  <div class="cf-tab" onclick="cftab('donors',this)">👥 Donors (<?php echo count($donations); ?>)</div>
  <?php if($isAdmin): ?><div class="cf-tab" onclick="cftab('admin',this)" style="color:#b71c1c">🛡️ Admin</div><?php endif; ?>
</div>
<?php if($isAdmin): ?>
<form method="POST" style="padding:0 0 .8rem" data-confirm="DELETE this campaign permanently? All donations will also be removed. This cannot be undone!" data-sudo>
  <input type="hidden" name="act" value="del_campaign">
  <input type="hidden" name="cid" value="<?php echo $campId; ?>">
  <button type="submit" style="width:100%;background:#b71c1c;color:#fff;border:none;border-radius:10px;padding:.55rem;font-size:.82rem;font-weight:800;cursor:pointer;letter-spacing:.02em">
    🗑️ Delete This Campaign
  </button>
</form>
<?php endif; ?>

<!-- Story -->
<div id="tab-story">
  <?php if($camp['description']): ?><div style="font-size:.88rem;color:#4a5568;line-height:1.75;margin-bottom:.8rem"><?php echo nl2br(h($camp['description'])); ?></div><?php endif; ?>
  <?php if($camp['story']): ?><div style="font-size:.85rem;color:#555;line-height:1.8;background:#F7F8FF;border-radius:12px;padding:1.1rem;border-left:4px solid var(--cf1);margin-bottom:.8rem"><?php echo nl2br(h($camp['story'])); ?></div><?php endif; ?>
  <?php if($camp['organizer_name']): ?>
  <div style="display:flex;align-items:center;gap:.75rem;background:#fff;border-radius:12px;padding:.9rem;border:1px solid #E3E7F5">
    <div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--cf1),var(--cf2));color:#fff;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">👤</div>
    <div>
      <div style="font-weight:700;font-size:.88rem"><?php echo h($camp['organizer_name']); ?></div>
      <div style="font-size:.73rem;color:#5f6880">Organizer<?php if($camp['organizer_phone']): ?> · <?php echo h($camp['organizer_phone']); ?><?php endif; ?></div>
    </div>
  </div>
  <?php endif; ?>
</div>

<!-- Updates -->
<?php if(!empty($cfupdates)): ?>
<div id="tab-updates" style="display:none">
  <?php foreach($cfupdates as $up): ?>
  <div style="background:#fff;border-radius:12px;padding:1rem;border-left:4px solid var(--cf1);box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:.7rem">
    <div style="font-weight:700;font-size:.9rem;margin-bottom:.25rem"><?php echo h($up['title']); ?></div>
    <div style="font-size:.82rem;color:#4a5568;line-height:1.65"><?php echo nl2br(h($up['body'])); ?></div>
    <div style="font-size:.68rem;color:#5f6880;margin-top:.4rem"><?php echo h($up['poster']??'Admin'); ?> · <?php echo date('d M Y',strtotime($up['created_at'])); ?></div>
  </div>
  <?php endforeach; ?>
</div>
<?php endif; ?>

<!-- Donors -->
<div id="tab-donors" style="display:none">
  <?php if(!empty($topDonors)): ?>
  <div style="background:linear-gradient(135deg,#fffaf0,#fff3e0);border:1px solid #ffe0b2;border-radius:14px;padding:1rem;margin-bottom:1rem">
    <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.84rem;letter-spacing:.01em;color:#c8922a;margin-bottom:.7rem">🏆 TOP DONORS</div>
    <?php foreach($topDonors as $ti=>$td): 
      $medal = $ti===0?'🥇':($ti===1?'🥈':($ti===2?'🥉':'⭐')); ?>
    <div style="display:flex;align-items:center;gap:.7rem;padding:.45rem 0;<?php echo $ti<count($topDonors)-1?'border-bottom:1px dashed #f0e2c0':''; ?>">
      <div style="font-size:1.1rem;width:24px;text-align:center"><?php echo $medal; ?></div>
      <div style="flex:1;min-width:0;font-weight:700;font-size:.86rem;color:#0B1033;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><?php echo h($td['donor_name']); ?></div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.92rem;color:#1b5e20">₹<?php echo number_format($td['total']); ?></div>
        <?php if($td['cnt']>1): ?><div style="font-size:.62rem;color:#5f6880"><?php echo $td['cnt']; ?> donations</div><?php endif; ?>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
  <div style="font-size:.72rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.6rem">All Donors</div>
  <?php endif; ?>
  <?php foreach($donations as $don): ?>
  <div class="donor-row">
    <div class="donor-av"><?php echo strtoupper(substr($don['donor_name'],0,1)); ?></div>
    <div style="flex:1;min-width:0">
      <div style="font-weight:700;font-size:.85rem"><?php echo h($don['donor_name']); ?></div>
      <div style="font-size:.7rem;color:#5f6880"><?php echo date('d M Y',strtotime($don['donated_at'])); ?> · <?php echo ucfirst($don['payment_method']); ?></div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.88rem;color:var(--cfg)">₹<?php echo number_format($don['amount']); ?></div>
      <span class="don-badge db-<?php echo $don['status']; ?>"><?php echo ucfirst($don['status']); ?></span>
      <?php if($isAdmin && $don['status']==='pending'): ?>
      <div style="display:flex;gap:.25rem;margin-top:.25rem;justify-content:flex-end">
        <form method="POST" style="display:inline" data-sudo><input type="hidden" name="act" value="verify_donation"><input type="hidden" name="did" value="<?php echo $don['id']; ?>"><input type="hidden" name="cid" value="<?php echo $campId; ?>"><button style="background:#2e7d32;color:#fff;border:none;border-radius:6px;padding:.22rem .5rem;font-size:.65rem;font-weight:700;cursor:pointer">✅</button></form>
        <form method="POST" style="display:inline" data-sudo><input type="hidden" name="act" value="reject_donation"><input type="hidden" name="did" value="<?php echo $don['id']; ?>"><input type="hidden" name="cid" value="<?php echo $campId; ?>"><button style="background:#b71c1c;color:#fff;border:none;border-radius:6px;padding:.22rem .5rem;font-size:.65rem;font-weight:700;cursor:pointer">✗</button></form>
      </div>
      <?php endif; ?>
    </div>
  </div>
  <?php endforeach; ?>
  <?php if(empty($donations)): ?><div class="empty-cf"><div style="font-size:1.8rem;margin-bottom:.4rem">🙏</div><p>No donations yet. Be the first!</p></div><?php endif; ?>

  <!-- My donations -->
  <?php if(!empty($myDon)): ?>
  <div style="margin-top:1rem;padding:.9rem;background:#F7F8FF;border-radius:12px;border:1px solid #E3E7F5">
    <div style="font-size:.72rem;font-weight:800;color:#5f6880;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.6rem">Your Donations</div>
    <?php foreach($myDon as $md): ?>
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.4rem 0;border-bottom:1px solid #F5F7FF;font-size:.82rem">
      <div><div style="font-weight:700">₹<?php echo number_format($md['amount']); ?></div><div style="font-size:.68rem;color:#5f6880"><?php echo h($md['receipt_no']); ?></div></div>
      <span class="don-badge db-<?php echo $md['status']; ?>"><?php echo ucfirst($md['status']); ?></span>
    </div>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>
</div>

<!-- Admin tab -->
<?php if($isAdmin): ?>
<div id="tab-admin" style="display:none">
  <div class="admin-panel">
    <div class="admin-panel-head"><span>🛡️</span><h3>ADMIN CONTROLS</h3></div>
    <div class="admin-panel-body">
      <!-- Status -->
      <div style="margin-bottom:.9rem">
        <div style="font-size:.7rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.5rem">Campaign Status</div>
        <div class="admin-btns">
          <?php foreach(['approve'=>['✅ Approve','#2e7d32'],'pause'=>['⏸ Pause','#7b1fa2'],'complete'=>['🏁 Complete','#0A14E0'],'reject'=>['✗ Reject','#b71c1c']] as $a=>[$lbl,$bg]): ?>
          <form method="POST"><input type="hidden" name="act" value="<?php echo $a; ?>"><input type="hidden" name="cid" value="<?php echo $campId; ?>"><button style="background:<?php echo $bg; ?>;color:#fff;border:none;border-radius:8px;padding:.42rem .85rem;font-size:.75rem;font-weight:700;cursor:pointer"><?php echo $lbl; ?></button></form>
          <?php endforeach; ?>
        </div>
      </div>
      <!-- Edit & Delete -->
      <div style="display:flex;gap:.5rem;margin-bottom:.6rem">
        <a href="?view=edit&id=<?php echo $campId; ?>" style="flex:1;background:#455a64;color:#fff;border:none;border-radius:9px;padding:.52rem;font-size:.8rem;font-weight:700;text-align:center;text-decoration:none;display:flex;align-items:center;justify-content:center;gap:.3rem">✏️ Edit Campaign</a>
        <form method="POST" style="flex:1" data-confirm="DELETE this campaign? This cannot be undone!" data-sudo>
          <input type="hidden" name="act" value="del_campaign">
          <input type="hidden" name="cid" value="<?php echo $campId; ?>">
          <button style="width:100%;background:#b71c1c;color:#fff;border:none;border-radius:9px;padding:.52rem;font-size:.8rem;font-weight:700;cursor:pointer">🗑️ Delete Campaign</button>
        </form>
      </div>
      <!-- Download PDF report -->
      <a href="<?php echo url('modules/cf_report.php'); ?>?id=<?php echo $campId; ?>" style="display:flex;align-items:center;justify-content:center;gap:.4rem;width:100%;background:linear-gradient(135deg,#1b5e20,#2e7d32);color:#fff;border-radius:9px;padding:.55rem;font-size:.82rem;font-weight:800;text-decoration:none;margin-bottom:.9rem">📄 Download Funding Report (PDF)</a>
      <!-- Post update -->
      <div style="font-size:.7rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.5rem">Post Campaign Update</div>
      <form method="POST">
        <input type="hidden" name="act" value="post_update">
        <input type="hidden" name="cid" value="<?php echo $campId; ?>">
        <input type="text" name="utitle" class="inp" placeholder="Update title" required style="margin-bottom:.5rem">
        <textarea name="ubody" class="inp" rows="3" placeholder="What's new?" required style="margin-bottom:.5rem;resize:vertical"></textarea>
        <button style="width:100%;background:linear-gradient(135deg,#0B1033,#0A14E0);color:#fff;border:none;border-radius:9px;padding:.55rem;font-weight:700;cursor:pointer;font-size:.82rem">📢 Post Update</button>
      </form>
    </div>
  </div>
</div>
<?php endif; ?>

<!-- Donate Form -->
<?php if($camp['status']==='active'): ?>
<div class="cf-donate">
  <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.0rem;letter-spacing:.01em;color:var(--cf1);margin-bottom:.3rem">💖 MAKE A DONATION</div>
  <p style="font-size:.74rem;color:#8a93a8;margin-bottom:.9rem">3 quick steps — choose amount, pay, confirm.</p>
  <form method="POST" enctype="multipart/form-data" id="donateForm" onsubmit="return validateDonate()">
    <input type="hidden" name="act" value="donate">
    <input type="hidden" name="cid" value="<?php echo $campId; ?>">

    <?php if($isGuest): ?>
    <!-- STEP 0: who's donating (guests) -->
    <div style="font-size:.72rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem">👤 Your Details</div>
    <input type="text" name="donor_name" id="donorName" class="inp" placeholder="Your name" style="margin-bottom:.6rem">
    <input type="tel" name="donor_phone" id="donorPhone" class="inp" placeholder="WhatsApp number (for thank-you receipt)" style="margin-bottom:.9rem">
    <?php endif; ?>

    <!-- STEP 1: amount -->
    <div style="font-size:.72rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem">1️⃣ Choose Amount</div>
    <div class="amt-grid">
      <?php foreach([100,250,500,1000,2500,5000] as $qa): ?>
      <button type="button" class="amt-btn" onclick="setAmt(<?php echo $qa; ?>)">₹<?php echo $qa; ?></button>
      <?php endforeach; ?>
    </div>
    <input type="number" name="amount" id="amtInp" class="inp" placeholder="Or enter custom amount (₹)" min="1" required style="margin-bottom:.9rem" oninput="onAmtChange()">

    <!-- STEP 2: pay -->
    <?php if($upiId): ?>
    <div style="font-size:.72rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem">2️⃣ Pay <span id="payAmtLbl" style="color:var(--cf1)"></span></div>
    <div style="background:#f8f9ff;border:1px solid #e3e8f7;border-radius:12px;padding:1rem .85rem;margin-bottom:.9rem;text-align:center">

      <!-- (a) QR code -->
      <div style="font-size:.78rem;font-weight:800;color:#0B1033;margin-bottom:.5rem">📷 Step 1 — Scan this QR</div>
      <img id="upiQr" src="" alt="UPI QR" style="width:185px;height:185px;border-radius:12px;display:block;margin:0 auto .8rem;border:1px solid #e3e8f7;background:#fff;padding:6px">

      <!-- (b) Copy UPI ID -->
      <div style="border-top:1px dashed #d8e0ee;padding-top:.7rem;margin-bottom:.6rem">
        <div style="font-size:.74rem;font-weight:800;color:#0B1033;margin-bottom:.3rem">📋 Step 2 — or Copy UPI ID</div>
        <div class="upi-id" style="font-size:.84rem;font-weight:800;color:#0B1033;word-break:break-all;margin-bottom:.4rem"><?php echo h($upiId); ?></div>
        <button type="button" class="copy-btn" onclick="copyTxt('<?php echo h($upiId); ?>')">📋 Copy UPI ID</button>
      </div>

      <!-- (c) Open Google Pay -->
      <div style="border-top:1px dashed #d8e0ee;padding-top:.7rem">
        <div style="font-size:.74rem;font-weight:800;color:#0B1033;margin-bottom:.45rem">📲 Step 3 — or Open Google Pay</div>
        <a id="payNowBtn" href="#" onclick="return openGpay()"
           style="display:flex;align-items:center;justify-content:center;gap:.45rem;width:100%;padding:.7rem;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;border:none;border-radius:10px;font-weight:800;font-size:.88rem;text-decoration:none;box-shadow:0 4px 12px rgba(26,35,201,.3)">
          📲 Open Google Pay
        </a>
      </div>
    </div>
    <?php endif; ?>

    <!-- STEP 3: confirm -->
    <div style="font-size:.72rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem">3️⃣ Confirm Your Payment</div>
    <select name="method" class="inp" style="margin-bottom:.6rem">
      <option value="gpay">Google Pay</option>
      <option value="upi">UPI / QR Code</option>
      <option value="cash">Cash (handed to organizer)</option>
    </select>
    <input type="text" name="upi_ref" class="inp" placeholder="Transaction ID / UPI Ref (helps verify faster)" style="margin-bottom:.6rem">
    <div id="ssBox" style="border:2px dashed rgba(10,20,224,.35);border-radius:10px;padding:.85rem;text-align:center;margin-bottom:.6rem;cursor:pointer;background:#f8f9ff" onclick="document.getElementById('ssF').click()">
      <input type="file" name="screenshot" id="ssF" accept="image/*" style="display:none" onchange="prvSS(this)">
      <div id="ssPrompt" style="font-size:.8rem;color:#c62828;font-weight:700">📷 Add payment screenshot <span style="color:#5f6880;font-weight:400">(tap to choose from gallery)</span></div>
      <img id="ssPrev" style="display:none;max-height:70px;border-radius:6px;margin-top:.3rem">
    </div>
    <textarea name="message" class="inp" rows="2" placeholder="Leave a message of support (optional)" style="margin-bottom:.6rem;resize:none"></textarea>
    <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;margin-bottom:.7rem;cursor:pointer">
      <input type="checkbox" name="anonymous"> Donate anonymously
    </label>
    <button type="submit" style="width:100%;padding:.75rem;background:linear-gradient(135deg,var(--cf1),var(--cf2));color:#fff;border:none;border-radius:10px;font-weight:700;font-size:.9rem;cursor:pointer">❤️ Confirm Donation</button>
    <p style="font-size:.72rem;color:#5f6880;text-align:center;margin-top:.5rem">🔒 An admin verifies every donation. You'll get a receipt number. Funds go directly to the organizer's UPI.</p>
  </form>
</div>
<?php endif; ?>

<?php
/* ═══════ EDIT FORM ═══════ */
elseif ($view==='edit' && $isAdmin && !empty($editCamp)):
?>
<a href="?view=campaign&id=<?php echo $editCamp['id']; ?>" style="display:inline-flex;align-items:center;gap:.3rem;font-size:.8rem;font-weight:700;color:var(--cf1);text-decoration:none;margin-bottom:.8rem">← Back</a>
<div class="cf-form-card">
  <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.96rem;letter-spacing:.01em;color:var(--cf1);margin-bottom:1rem">✏️ EDIT CAMPAIGN</div>
  <form method="POST" enctype="multipart/form-data" data-sudo>
    <input type="hidden" name="act" value="save_campaign">
    <input type="hidden" name="cid" value="<?php echo $editCamp['id']; ?>">
    <div class="fg"><label class="lbl">Title *</label><input type="text" name="title" class="inp" required value="<?php echo h($editCamp['title']); ?>"></div>
    <div class="fg"><label class="lbl">Category</label>
      <select name="category" class="inp">
        <?php foreach(['charity'=>'❤️ Charity','medical'=>'🏥 Medical','education'=>'📚 Education','sports'=>'⚽ Sports','arts'=>'🎭 Arts','disaster'=>'🆘 Disaster','other'=>'🌟 Other'] as $v=>$l): ?>
        <option value="<?php echo $v; ?>" <?php echo $editCamp['category']===$v?'selected':''; ?>><?php echo $l; ?></option>
        <?php endforeach; ?>
      </select>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">Target (₹) *</label><input type="number" name="target" class="inp" required value="<?php echo $editCamp['target_amount']; ?>" min="100"></div>
      <div class="fg"><label class="lbl">Deadline</label><input type="date" name="deadline" class="inp" value="<?php echo $editCamp['deadline']??''; ?>"></div>
    </div>
    <div class="fg"><label class="lbl">UPI ID</label><input type="text" name="upi_id" class="inp" value="<?php echo h($editCamp['upi_id']??''); ?>"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">Organizer Name</label><input type="text" name="organizer_name" class="inp" value="<?php echo h($editCamp['organizer_name']??''); ?>"></div>
      <div class="fg"><label class="lbl">Organizer Phone</label><input type="text" name="organizer_phone" class="inp" value="<?php echo h($editCamp['organizer_phone']??''); ?>"></div>
    </div>
    <div class="fg"><label class="lbl">Short Description</label><textarea name="description" class="inp" rows="2" style="resize:none"><?php echo h($editCamp['description']??''); ?></textarea></div>
    <div class="fg"><label class="lbl">Full Story</label><textarea name="story" class="inp" rows="4" style="resize:vertical"><?php echo h($editCamp['story']??''); ?></textarea></div>
    <div class="fg"><label class="lbl">Status</label>
      <select name="status" class="inp">
        <?php foreach(['active','pending','paused','completed','rejected'] as $s): ?>
        <option value="<?php echo $s; ?>" <?php echo $editCamp['status']===$s?'selected':''; ?>><?php echo ucfirst($s); ?></option>
        <?php endforeach; ?>
      </select>
    </div>
    <div class="fg"><label class="lbl">Cover Image <span style="font-size:.7rem;color:#5f6880">(leave empty to keep current)</span></label>
      <div style="border:2px dashed rgba(10,20,224,.2);border-radius:10px;padding:1rem;text-align:center;background:#f8f9ff;cursor:pointer" onclick="document.getElementById('covF').click()">
        <input type="file" name="cover_image" id="covF" accept="image/*" style="display:none" onchange="prvCov(this)">
        <?php if($editCamp['cover_image']): ?><img src="<?php echo url('assets/uploads/'.$editCamp['cover_image']); ?>" style="max-height:90px;border-radius:7px;margin-bottom:.4rem;display:block;margin:0 auto .4rem"><?php endif; ?>
        <img id="covPrev" style="display:none;max-height:90px;border-radius:7px;margin:0 auto .4rem">
        <div style="font-size:.78rem;color:#5f6880">📷 Upload cover image</div>
      </div>
    </div>
    <label style="display:flex;align-items:center;gap:.5rem;font-size:.84rem;margin-bottom:.8rem;cursor:pointer;font-weight:600;color:var(--cfa)">
      <input type="checkbox" name="is_featured" <?php echo $editCamp['is_featured']?'checked':''; ?>> ⭐ Feature this campaign
    </label>
    <div style="display:flex;gap:.5rem">
      <button type="submit" style="flex:1;padding:.7rem;background:linear-gradient(135deg,var(--cf1),var(--cf2));color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer">💾 Save Changes</button>
      <a href="?view=campaign&id=<?php echo $editCamp['id']; ?>" style="padding:.7rem 1rem;background:#E3E7F5;color:#4a5568;border-radius:10px;font-weight:600;text-decoration:none;display:flex;align-items:center">Cancel</a>
    </div>
  </form>
</div>

<?php
/* ═══════ CREATE FORM ═══════ */
elseif ($view==='create' && $isAdmin):
?>
<a href="?" style="display:inline-flex;align-items:center;gap:.3rem;font-size:.8rem;font-weight:700;color:var(--cf1);text-decoration:none;margin-bottom:.8rem">← Back</a>
<div class="cf-form-card">
  <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.96rem;letter-spacing:.01em;color:var(--cf1);margin-bottom:1rem">➕ CREATE CAMPAIGN</div>
  <form method="POST" enctype="multipart/form-data" data-sudo>
    <input type="hidden" name="act" value="save_campaign">
    <div class="fg"><label class="lbl">Campaign Title *</label><input type="text" name="title" class="inp" required placeholder="e.g. Medical Aid for Rajan Family"></div>
    <div class="fg"><label class="lbl">Category</label>
      <select name="category" class="inp">
        <?php foreach(['charity'=>'❤️ Charity','medical'=>'🏥 Medical','education'=>'📚 Education','sports'=>'⚽ Sports','arts'=>'🎭 Arts','disaster'=>'🆘 Disaster','other'=>'🌟 Other'] as $v=>$l): ?>
        <option value="<?php echo $v; ?>"><?php echo $l; ?></option>
        <?php endforeach; ?>
      </select>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">Target Amount (₹) *</label><input type="number" name="target" class="inp" required placeholder="50000" min="100"></div>
      <div class="fg"><label class="lbl">Deadline</label><input type="date" name="deadline" class="inp" min="<?php echo date('Y-m-d'); ?>"></div>
    </div>
    <div class="fg"><label class="lbl">UPI ID</label><input type="text" name="upi_id" class="inp" placeholder="organizer@upi"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div class="fg"><label class="lbl">Organizer Name</label><input type="text" name="organizer_name" class="inp" value="<?php echo h($me['name']); ?>"></div>
      <div class="fg"><label class="lbl">Phone</label><input type="text" name="organizer_phone" class="inp" value="<?php echo h($me['whatsapp_number']??''); ?>"></div>
    </div>
    <div class="fg"><label class="lbl">Short Description</label><textarea name="description" class="inp" rows="2" style="resize:none" placeholder="Brief summary…"></textarea></div>
    <div class="fg"><label class="lbl">Full Story</label><textarea name="story" class="inp" rows="5" style="resize:vertical" placeholder="Tell the full story…"></textarea></div>
    <div class="fg"><label class="lbl">Cover Image</label>
      <div style="border:2px dashed rgba(10,20,224,.2);border-radius:10px;padding:1rem;text-align:center;background:#f8f9ff;cursor:pointer" onclick="document.getElementById('covF2').click()">
        <input type="file" name="cover_image" id="covF2" accept="image/*" style="display:none" onchange="prvCov2(this)">
        <img id="covPrev2" style="display:none;max-height:90px;border-radius:7px;margin:0 auto .4rem">
        <div id="covPh2" style="font-size:.78rem;color:#5f6880">📷 Upload cover image</div>
      </div>
    </div>
    <?php if($isAdmin): ?>
    <div class="fg"><label class="lbl">Status</label>
      <select name="status" class="inp">
        <option value="active" selected>Active</option>
        <option value="pending">Pending</option>
      </select>
    </div>
    <label style="display:flex;align-items:center;gap:.5rem;font-size:.84rem;margin-bottom:.8rem;cursor:pointer;font-weight:600;color:var(--cfa)">
      <input type="checkbox" name="is_featured"> ⭐ Feature this campaign
    </label>
    <?php endif; ?>
    <button type="submit" style="width:100%;padding:.75rem;background:linear-gradient(135deg,var(--cf1),var(--cf2));color:#fff;border:none;border-radius:10px;font-weight:700;font-size:.88rem;cursor:pointer">🚀 Submit Campaign</button>
    <?php if(!$isAdmin): ?><p style="font-size:.74rem;color:#5f6880;text-align:center;margin-top:.5rem">Your campaign will be reviewed by admin before going live.</p><?php endif; ?>
  </form>
</div>

<?php
/* ═══════ PENDING DONATIONS ═══════ */
elseif ($view==='pending' && $isAdmin):
?>
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem;flex-wrap:wrap;gap:.5rem">
  <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.04rem;letter-spacing:.01em;color:var(--cf1)">💳 DONATION APPROVALS</div>
  <a href="?" style="font-size:.78rem;font-weight:700;color:var(--cf1);text-decoration:none">← Back</a>
</div>

<?php if(empty($pendingDons)): ?>
<div class="empty-cf"><div style="font-size:2.5rem;margin-bottom:.5rem">✅</div><p>All clear! No pending donations.</p></div>
<?php else: ?>
<?php foreach($pendingDons as $pd2): ?>
<div style="background:#fff;border-radius:14px;border:1.5px solid #ffe0b2;padding:1rem;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:.75rem">
  <div style="display:flex;align-items:center;gap:.65rem;margin-bottom:.6rem">
    <div style="width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,var(--cf1),var(--cf2));color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0"><?php echo strtoupper(substr($pd2['donor_name'],0,1)); ?></div>
    <div>
      <div style="font-weight:700;font-size:.9rem"><?php echo h($pd2['donor_name']); ?></div>
      <div style="font-size:.7rem;color:#5f6880"><?php echo date('d M Y, g:i A',strtotime($pd2['donated_at'])); ?></div>
    </div>
    <div style="margin-left:auto;text-align:right">
      <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.12rem;color:var(--cfg)">₹<?php echo number_format($pd2['amount']); ?></div>
      <div style="font-size:.65rem;color:#5f6880"><?php echo ucfirst($pd2['payment_method']); ?></div>
    </div>
  </div>
  <div style="background:#F7F8FF;border-radius:8px;padding:.5rem .75rem;font-size:.8rem;margin-bottom:.6rem">
    <span style="color:#5f6880">Campaign:</span> <span style="font-weight:700"><?php echo h($pd2['camp_title']); ?></span>
  </div>
  <?php if($pd2['upi_ref']): ?><div style="font-size:.78rem;color:#4a5568;margin-bottom:.4rem">Ref: <span style="font-weight:700"><?php echo h($pd2['upi_ref']); ?></span></div><?php endif; ?>
  <?php if($pd2['message']): ?><div style="font-size:.78rem;color:#4a5568;font-style:italic;margin-bottom:.4rem">"<?php echo h($pd2['message']); ?>"</div><?php endif; ?>
  <?php if($pd2['screenshot']): ?>
  <div style="margin-bottom:.6rem">
    <a href="<?php echo url('assets/uploads/'.$pd2['screenshot']); ?>" target="_blank"><img src="<?php echo url('assets/uploads/'.$pd2['screenshot']); ?>" style="max-height:90px;border-radius:8px;object-fit:cover"></a>
  </div>
  <?php endif; ?>
  <div style="display:flex;gap:.4rem">
    <form method="POST" style="flex:1" data-sudo><input type="hidden" name="act" value="verify_donation"><input type="hidden" name="did" value="<?php echo $pd2['id']; ?>"><input type="hidden" name="cid" value="<?php echo $pd2['camp_id']; ?>"><input type="hidden" name="back" value="pending"><button style="width:100%;background:#2e7d32;color:#fff;border:none;border-radius:9px;padding:.55rem;font-weight:700;cursor:pointer;font-size:.82rem">✅ Verify</button></form>
    <form method="POST" style="flex:1" data-sudo><input type="hidden" name="act" value="reject_donation"><input type="hidden" name="did" value="<?php echo $pd2['id']; ?>"><input type="hidden" name="cid" value="<?php echo $pd2['camp_id']; ?>"><input type="hidden" name="back" value="pending"><button style="width:100%;background:#b71c1c;color:#fff;border:none;border-radius:9px;padding:.55rem;font-weight:700;cursor:pointer;font-size:.82rem">✗ Reject</button></form>
  </div>
</div>
<?php endforeach; ?>
<?php endif; ?>

<?php
/* ═══════ CAMPAIGN LIST ═══════ */
else:
  $catIcons=['charity'=>'❤️','medical'=>'🏥','education'=>'📚','sports'=>'⚽','arts'=>'🎭','disaster'=>'🆘','other'=>'🌟'];
  $catColors=['charity'=>'#b71c1c','medical'=>'#c62828','education'=>'#121A5C','sports'=>'#1b5e20','arts'=>'#7b1fa2','disaster'=>'#e65100','other'=>'#455a64'];
?>

<!-- Filter tabs -->
<div style="display:flex;gap:.4rem;overflow-x:auto;scrollbar-width:none;margin-bottom:.9rem;padding-bottom:.2rem">
  <button class="cf-ftab on" onclick="cfFilter('all',this)">All</button>
  <button class="cf-ftab" onclick="cfFilter('active',this)">✅ Active</button>
  <button class="cf-ftab" onclick="cfFilter('completed',this)">🏁 Completed</button>
  <?php if($isAdmin): ?><button class="cf-ftab" onclick="cfFilter('pending',this)">⏳ Pending</button><?php endif; ?>
</div>
<style>.cf-ftab{padding:.32rem .75rem;border-radius:20px;font-size:.72rem;font-weight:700;cursor:pointer;border:1.5px solid rgba(26,58,107,.2);color:#64748b;background:#fff;white-space:nowrap;flex-shrink:0}.cf-ftab.on{background:var(--cf1);color:#fff;border-color:var(--cf1)}</style>

<?php if(empty($campaigns)): ?>
<div class="empty-cf"><div style="font-size:2.5rem;margin-bottom:.5rem">❤️</div><p>No campaigns yet.</p></div>
<?php else: ?>
<?php foreach($campaigns as $c2):
  $pct2 = $c2['target_amount']>0 ? min(100,round(($c2['raised_amount']/$c2['target_amount'])*100)) : 0;
  $days2 = $c2['deadline'] ? max(0,ceil((strtotime($c2['deadline'])-time())/86400)) : null;
?>
<div class="cf-card cf-card-item" data-status="<?php echo $c2['status']; ?>">
  <div class="cf-cover">
    <?php if($c2['cover_image']): ?>
    <img src="<?php echo url('assets/uploads/'.$c2['cover_image']); ?>" alt="" loading="lazy">
    <?php else: ?>
    <div class="cf-cover-ph"><?php echo $catIcons[$c2['category']]??'❤️'; ?></div>
    <?php endif; ?>
    <div class="cf-cat-badge cat-<?php echo $c2['category']; ?>"><?php echo $catIcons[$c2['category']]??''; ?> <?php echo ucfirst($c2['category']); ?></div>
    <?php if($c2['is_featured']): ?><div class="cf-feat">⭐ Featured</div><?php endif; ?>
    <!-- Admin delete directly on card -->
    <?php if($isAdmin): ?>
    <form method="POST" style="position:absolute;bottom:.6rem;right:.6rem" onsubmit="return confirm('Delete «<?php echo addslashes(h($c2['title'])); ?>»?')" data-sudo>
      <input type="hidden" name="act" value="del_campaign">
      <input type="hidden" name="cid" value="<?php echo $c2['id']; ?>">
      <button type="submit" class="cf-del-btn">🗑️ Delete</button>
    </form>
    <?php endif; ?>
  </div>
  <div class="cf-body">
    <span class="st st-<?php echo $c2['status']; ?>" style="margin-bottom:.5rem;display:inline-block"><?php echo ucfirst($c2['status']); ?></span>
    <div class="cf-title"><?php echo h($c2['title']); ?></div>
    <?php if($c2['description']): ?><div class="cf-desc"><?php echo h($c2['description']); ?></div><?php endif; ?>
    <div class="cf-prog-wrap">
      <div class="cf-prog-bar"><div class="cf-prog-fill" style="width:<?php echo $pct2; ?>%"></div></div>
      <div class="cf-prog-row">
        <div><span class="cf-raised">₹<?php echo number_format($c2['raised_amount']); ?></span> <span class="cf-target">of ₹<?php echo number_format($c2['target_amount']); ?></span></div>
        <span class="cf-pct"><?php echo $pct2; ?>%</span>
      </div>
    </div>
    <div class="cf-meta">
      <span class="cf-chip">👥 <?php echo $c2['donor_count']; ?> donors</span>
      <?php if($days2!==null): ?><span class="cf-chip">⏰ <?php echo $days2; ?> days left</span><?php endif; ?>
      <?php if($c2['organizer_name']): ?><span class="cf-chip">👤 <?php echo h($c2['organizer_name']); ?></span><?php endif; ?>
    </div>
    <div style="display:flex;gap:.5rem">
      <a href="?view=campaign&id=<?php echo $c2['id']; ?>" class="btn-cf btn-cf-primary">❤️ View & Donate</a>
      <?php if($isAdmin): ?>
      <a href="?view=edit&id=<?php echo $c2['id']; ?>" class="btn-cf btn-cf-outline" style="flex:0 0 auto;padding:.6rem .85rem">✏️</a>
      <?php endif; ?>
    </div>
  </div>
</div>
<?php endforeach; ?>
<?php endif; ?>

<!-- New Campaign button (admin only) -->
<?php if($isAdmin): ?>
<div style="text-align:center;margin-top:.5rem">
  <a href="?view=create" style="display:inline-flex;align-items:center;gap:.5rem;background:linear-gradient(135deg,var(--cf1),var(--cf2));color:#fff;padding:.72rem 1.8rem;border-radius:25px;font-weight:800;font-size:.86rem;text-decoration:none;box-shadow:0 4px 16px rgba(26,58,107,.3)">
    ➕ Start a Campaign
  </a>
</div>
<?php endif; ?>

<?php endif; ?>
</div>

<div class="cf-toast" id="cft"></div>

<!-- How to Donate modal -->
<div id="howToOv" onclick="if(event.target===this)closeHowTo()" style="display:none;position:fixed;inset:0;background:rgba(13,27,62,.7);z-index:10000;align-items:flex-end;justify-content:center;padding:0">
  <div style="background:#fff;width:100%;max-width:480px;border-radius:22px 22px 0 0;max-height:88vh;overflow-y:auto;animation:howUp .3s ease">
    <div style="background:linear-gradient(150deg,#0B1033,#1A23C9);padding:1.3rem 1.2rem;text-align:center;position:relative;border-radius:22px 22px 0 0">
      <button onclick="closeHowTo()" style="position:absolute;top:.8rem;right:.9rem;width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,.2);border:none;color:#fff;font-size:1rem;cursor:pointer">✕</button>
      <div style="font-size:1.9rem">❤️</div>
      <div style="font-family:'Playfair Display',serif;font-size:1.25rem;font-weight:800;color:#fff;margin-top:.2rem">How to Donate</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.7);margin-top:.2rem">5 easy steps · 100% secure</div>
    </div>
    <div style="padding:1rem 1.2rem 1.4rem">
      <?php
        $howSteps = [
          ['1','📂 Open a Campaign','Tap the campaign you want to support and read its story.','#0A14E0'],
          ['2','💰 Choose Amount','Tap a quick amount (₹100, ₹250…) or type your own.','#0A14E0'],
          ['3','📲 Pay with Google Pay','Tap “Pay with Google Pay” — it opens with the amount filled in. Confirm & pay. (Or scan the QR.)','#7b1fa2'],
          ['4','📷 Add Screenshot & Confirm','Come back, upload your payment screenshot, then tap “Confirm Donation”.','#2e7d32'],
          ['5','✅ Get Your Receipt','You get a receipt number. An admin verifies it and adds it to the total.','#c8922a'],
        ];
        foreach($howSteps as [$n,$t,$d,$c]):
      ?>
      <div style="display:flex;gap:.85rem;padding:.7rem 0;border-bottom:1px dashed #E3E7F5;align-items:flex-start">
        <div style="flex-shrink:0;width:36px;height:36px;border-radius:11px;background:<?php echo $c; ?>;color:#fff;font-weight:800;font-size:1rem;display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',serif"><?php echo $n; ?></div>
        <div style="flex:1">
          <div style="font-weight:800;font-size:.92rem;color:#0B1033"><?php echo $t; ?></div>
          <div style="font-size:.8rem;color:#5a6680;line-height:1.5;margin-top:.1rem"><?php echo $d; ?></div>
        </div>
      </div>
      <?php endforeach; ?>
      <div style="display:flex;gap:.6rem;align-items:flex-start;background:linear-gradient(135deg,#e8f5e9,#f1f8e9);border:1px solid #c5e1c8;border-radius:14px;padding:.8rem .9rem;margin-top:.9rem">
        <span style="font-size:1.2rem">🔒</span>
        <div style="font-size:.76rem;color:#2e5234;line-height:1.5;font-weight:600">Payment goes securely through Google Pay — the website never sees your bank details or PIN. Every donation is verified by an admin.</div>
      </div>
    </div>
  </div>
</div>
<style>@keyframes howUp{from{transform:translateY(100%)}to{transform:translateY(0)}}</style>

<script>
var CFURL = "<?php echo url('modules/crowdfund.php'); ?>";
function openHowTo(){document.getElementById('howToOv').style.display='flex';document.body.style.overflow='hidden';}
function closeHowTo(){document.getElementById('howToOv').style.display='none';document.body.style.overflow='';}
var CFSITE= "<?php echo $SITE; ?>";
var CFCAMP= <?php echo ($campId && !empty($camp)) ? json_encode($camp['title']) : 'null'; ?>;
var CFDESC= <?php echo ($campId && !empty($camp)) ? json_encode($camp['description'] ?: '') : 'null'; ?>;
var CFIMG = <?php echo ($campId && !empty($camp) && $camp['cover_image']) ? json_encode($SITE.'/assets/uploads/'.$camp['cover_image']) : 'null'; ?>;

function toast(m,t){var e=document.getElementById('cft');e.textContent=m;e.className='cf-toast on'+(t==='g'?' g':t==='e'?' e':'');setTimeout(function(){e.className='cf-toast'},2800);}

function cftab(id,el){
  ['story','updates','donors','admin'].forEach(function(t){
    var el2=document.getElementById('tab-'+t);
    if(el2) el2.style.display='none';
  });
  var t=document.getElementById('tab-'+id);
  if(t) t.style.display='block';
  document.querySelectorAll('.cf-tab').forEach(function(b){b.classList.remove('on');});
  el.classList.add('on');
}

function cfFilter(st,el){
  document.querySelectorAll('.cf-ftab').forEach(function(b){b.classList.remove('on');});
  el.classList.add('on');
  document.querySelectorAll('.cf-card-item').forEach(function(c){
    c.style.display=(st==='all'||c.dataset.status===st)?'block':'none';
  });
}

function setAmt(a){document.getElementById('amtInp').value=a;document.querySelectorAll('.amt-btn').forEach(function(b){b.classList.remove('on');if(parseInt(b.textContent.replace('₹',''))===a)b.classList.add('on');});onAmtChange();}

// UPI payment config (from PHP)
var CF_UPI  = <?php echo json_encode($upiId ?? ''); ?>;
var CF_PAYEE= <?php echo json_encode($camp['organizer_name'] ?? ($CLUB)); ?>;
var CF_NOTE = <?php echo json_encode($camp['title'] ?? ''); ?>;

function buildUpiUrl(amt){
  var u='upi://pay?pa='+encodeURIComponent(CF_UPI)
       +'&pn='+encodeURIComponent(CF_PAYEE)
       +'&cu=INR&tn='+encodeURIComponent(CF_NOTE);
  if(amt&&amt>0) u+='&am='+amt;
  return u;
}
function onAmtChange(){
  if(!CF_UPI) return;
  var amt=parseFloat(document.getElementById('amtInp').value)||0;
  var lbl=document.getElementById('payAmtLbl');
  if(lbl) lbl.textContent=amt>0?('₹'+amt):'';
  // QR always shown — with amount if entered, otherwise just the UPI ID
  var qr=document.getElementById('upiQr');
  if(qr){
    qr.src='https://api.qrserver.com/v1/create-qr-code/?size=200x200&data='+encodeURIComponent(buildUpiUrl(amt));
    qr.style.display='block';
  }
}
// Show the QR as soon as the page loads
document.addEventListener('DOMContentLoaded',function(){ if(document.getElementById('upiQr')) onAmtChange(); });
function openUpiApp(){
  var amt=parseFloat(document.getElementById('amtInp').value)||0;
  if(amt<1){toast('Enter an amount first','e');document.getElementById('amtInp').focus();return false;}
  window.location.href=buildUpiUrl(amt);
  // remind to confirm after returning
  setTimeout(function(){toast('After paying, complete step 3 to confirm 🙏','g');},1500);
  return false;
}
// Open Google Pay directly (falls back to any UPI app if GPay not installed)
function openGpay(){
  var amt=parseFloat(document.getElementById('amtInp').value)||0;
  if(amt<1){toast('Enter an amount first','e');document.getElementById('amtInp').focus();return false;}
  if(!CF_UPI){toast('No UPI ID set for this campaign','e');return false;}
  // Standard UPI intent — Android shows the app chooser (GPay/PhonePe/Paytm).
  // This behaves like a normal payment (the tez:// scheme was unreliable).
  var params='pa='+encodeURIComponent(CF_UPI)
            +'&pn='+encodeURIComponent(CF_PAYEE)
            +'&cu=INR'
            +'&am='+amt
            +'&tn='+encodeURIComponent(CF_NOTE);
  var upi='upi://pay?'+params;
  toast('Opening UPI app for ₹'+amt+' 🙏','g');
  window.location.href=upi;
  setTimeout(function(){toast('After paying, complete step 3 to confirm 🙏','g');},3000);
  return false;
}

function prvSS(i){if(!i.files||!i.files[0])return;var r=new FileReader();r.onload=function(e){document.getElementById('ssPrev').src=e.target.result;document.getElementById('ssPrev').style.display='block';document.getElementById('ssPrompt').style.display='none';};r.readAsDataURL(i.files[0]);}
// Require screenshot before confirming (cash donations exempt)
function validateDonate(){
  var amt=parseFloat(document.getElementById('amtInp').value)||0;
  if(amt<1){toast('Enter a valid amount','e');return false;}
  var anon=document.querySelector('#donateForm input[name="anonymous"]');
  var nameF=document.getElementById('donorName');
  if(nameF && (!anon||!anon.checked) && nameF.value.trim()===''){
    toast('Please enter your name','e');nameF.focus();return false;
  }
  var method=document.querySelector('#donateForm select[name="method"]');
  var isCash = method && method.value==='cash';
  var ss=document.getElementById('ssF');
  if(!isCash && (!ss.files || !ss.files[0])){
    toast('Please add a payment screenshot first','e');
    var box=document.getElementById('ssBox');
    if(box){box.style.borderColor='#c62828';box.style.background='#fff5f5';box.scrollIntoView({behavior:'smooth',block:'center'});}
    return false;
  }
  return true;
}
function prvCov(i){if(!i.files||!i.files[0])return;var r=new FileReader();r.onload=function(e){document.getElementById('covPrev').src=e.target.result;document.getElementById('covPrev').style.display='block';};r.readAsDataURL(i.files[0]);}
function prvCov2(i){if(!i.files||!i.files[0])return;var r=new FileReader();r.onload=function(e){document.getElementById('covPrev2').src=e.target.result;document.getElementById('covPrev2').style.display='block';document.getElementById('covPh2').style.display='none';};r.readAsDataURL(i.files[0]);}

function copyTxt(t){
  if(navigator.clipboard){navigator.clipboard.writeText(t).then(function(){toast('Copied!','g');});}
  else{var i=document.createElement('input');i.value=t;document.body.appendChild(i);i.select();document.execCommand('copy');document.body.removeChild(i);toast('Copied!','g');}
}
function copyLink(){copyTxt(window.location.href);}

function shareWA(){
  var url=window.location.href;
  var title=CFCAMP||'Crowd Funding Campaign';
  var desc=CFDESC?('\n\n'+CFDESC):'';
  var caption='❤️ '+title+desc+'\n\n🤝 Support this campaign:\n'+url;
  // Try to share WITH the cover image (native share sheet → WhatsApp/Instagram)
  if(CFIMG && navigator.canShare){
    toast('Preparing image…');
    fetch(CFIMG).then(function(r){return r.blob();}).then(function(blob){
      var ext=(blob.type&&blob.type.indexOf('png')>-1)?'png':'jpg';
      var file=new File([blob],'campaign.'+ext,{type:blob.type||'image/jpeg'});
      if(navigator.canShare({files:[file]})){
        return navigator.share({files:[file],text:caption,title:title});
      } else {
        return _cfShareText(caption,url,title);
      }
    }).catch(function(){ _cfShareText(caption,url,title); });
    return;
  }
  _cfShareText(caption,url,title);
}
function _cfShareText(caption,url,title){
  if(navigator.share){ navigator.share({text:caption,url:url,title:title}).catch(function(){}); }
  else{ window.open('https://wa.me/?text='+encodeURIComponent(caption),'_blank'); }
}
</script>
<?php require_once __DIR__.'/../includes/footer.php'; ?>
