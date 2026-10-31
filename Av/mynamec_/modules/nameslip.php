<?php
// ============================================================
// modules/nameslip.php — School Book Cover Name Slip Generator
// Aishwarya Arts & Sports Club — PHP 7.3+ compatible
// Complete rebuild with all features
// ============================================================
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/upload_helper.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '📚 Name Slip Generator — Aishwarya Arts & Sports Club',
  'desc'  => 'Create school book cover name slips — AASC',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/nameslip.php',
];
requireLogin();
$me      = currentUser();
$isAdmin = isAdminRole($me['role']);
$uid     = $me['id'];
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$PLACE   = setting('CLUB_PLACE','Vettikkattiri, Malappuram · Kerala');
$pageTitle = 'Name Slip Generator — '.$CLUB;

// ── DB Setup ────────────────────────────────────────────────
try {
    db()->exec("CREATE TABLE IF NOT EXISTS name_slips (
        id             INT AUTO_INCREMENT PRIMARY KEY,
        student_name   VARCHAR(200) NOT NULL,
        school_name    VARCHAR(200) DEFAULT NULL,
        class_grade    VARCHAR(50)  DEFAULT NULL,
        division       VARCHAR(20)  DEFAULT NULL,
        roll_number    VARCHAR(30)  DEFAULT NULL,
        parent_name    VARCHAR(200) DEFAULT NULL,
        contact_number VARCHAR(20)  DEFAULT NULL,
        subject        VARCHAR(80)  DEFAULT 'General',
        academic_year  VARCHAR(20)  DEFAULT NULL,
        address        TEXT         DEFAULT NULL,
        photo          VARCHAR(500) DEFAULT NULL,
        template_id    INT          DEFAULT 1,
        created_by     INT          NOT NULL,
        status         ENUM('active','archived') DEFAULT 'active',
        created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_created_by (created_by),
        INDEX idx_subject (subject),
        INDEX idx_status (status)
    )");
} catch (Exception $e) {}
// safe alters
foreach ([
    "ALTER TABLE name_slips ADD COLUMN division VARCHAR(20) DEFAULT NULL",
    "ALTER TABLE name_slips ADD COLUMN roll_number VARCHAR(30) DEFAULT NULL",
    "ALTER TABLE name_slips ADD COLUMN academic_year VARCHAR(20) DEFAULT NULL",
    "ALTER TABLE name_slips ADD COLUMN address TEXT DEFAULT NULL",
    "ALTER TABLE name_slips ADD COLUMN status ENUM('active','archived') DEFAULT 'active'",
] as $c) { try { db()->exec($c); } catch (Exception $e) {} }


// ── Public QR scan redirect ───────────────────────────────────────
// QR on each slip links to nameslip.php?view=CREATOR_UID
// Scanning redirects to that member's profile
if (!empty($_GET['view'])) {
    $viewUid = (int)$_GET['view'];
    header('Location: '.url('modules/profile.php').'?id='.$viewUid); exit;
}

// ── AJAX ────────────────────────────────────────────────────
$_AJ = array_merge($_GET, $_POST);
if (!empty($_AJ['ax'])) {
    header('Content-Type: application/json');
    $ax  = trim($_AJ['ax']);
    $get = function($k,$d='') use ($_AJ){ return isset($_AJ[$k]) ? trim((string)$_AJ[$k]) : $d; };

    // ── SAVE ──
    if ($ax === 'save') {
        // Use the shared upload helper — saves to assets/uploads/nameslips/
        // Returns path like: nameslips/nameslips_1234567890_1234.jpg
        $photo = handlePhotoUpload('photo', 'nameslips');

        // Camera / crop: base64 image → save to same folder
        if (!$photo && !empty($_POST['photo_b64'])) {
            $b64 = trim($_POST['photo_b64']);
            if (strpos($b64,'data:image') === 0) {
                $imgd = base64_decode(substr($b64, strpos($b64,',')+1));
                if ($imgd) {
                    $dir = __DIR__.'/../assets/uploads/nameslips/';
                    if (!is_dir($dir)) mkdir($dir, 0755, true);
                    $fn  = 'nameslips_'.time().'_'.mt_rand(1000,9999).'.jpg';
                    if (file_put_contents($dir.$fn, $imgd) !== false) {
                        $photo = 'nameslips/'.$fn;
                    }
                }
            }
        }
        $sn = $get('student_name');
        if (!$sn) { echo json_encode(['ok'=>false,'msg'=>'Student name is required.']); exit; }
        $d = [$get('school_name'),$get('class_grade'),$get('division'),$get('roll_number'),
              $get('parent_name'),$get('contact_number'),$get('subject','General'),
              $get('academic_year'),$get('address'),(int)($get('template_id') ?: 1)];
        $eid = (int)$get('edit_id');
        if ($eid) {
            $sql = "UPDATE name_slips SET student_name=?,school_name=?,class_grade=?,division=?,roll_number=?,parent_name=?,contact_number=?,subject=?,academic_year=?,address=?,template_id=?";
            if ($photo) { $sql.=",photo=?"; $d[]=$photo; }
            $sql.=" WHERE id=?"; $d[]=$eid;
            db()->prepare($sql)->execute(array_merge([$sn],$d));
            echo json_encode(['ok'=>true,'id'=>$eid,'msg'=>'✅ Slip updated!']); exit;
        }
        if ($photo) {
            db()->prepare("INSERT INTO name_slips(student_name,school_name,class_grade,division,roll_number,parent_name,contact_number,subject,academic_year,address,template_id,photo,created_by)VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)")
               ->execute(array_merge([$sn],$d,[$photo,$uid]));
        } else {
            db()->prepare("INSERT INTO name_slips(student_name,school_name,class_grade,division,roll_number,parent_name,contact_number,subject,academic_year,address,template_id,created_by)VALUES(?,?,?,?,?,?,?,?,?,?,?,?)")
               ->execute(array_merge([$sn],$d,[$uid]));
        }
        echo json_encode(['ok'=>true,'id'=>(int)db()->lastInsertId(),'msg'=>'✅ Slip saved!']); exit;
    }

    // ── LOAD ──
    if ($ax === 'load') {
        $id = (int)$get('id');
        $r  = db()->prepare("SELECT * FROM name_slips WHERE id=? AND (created_by=? OR 1=?)");
        $r->execute([$id,$uid,$isAdmin?1:0]); $r=$r->fetch();
        if ($r && $r['photo']) {
            // Return both: base64 for offline/print, and direct URL for quick display
            $r['photo_b64'] = getMemberPhoto($r['photo']);
            $r['photo_url'] = photoUrl($r['photo']); // e.g. /av/assets/uploads/nameslips/...
        }
        echo json_encode(['ok'=>(bool)$r,'slip'=>$r]); exit;
    }

    // ── DELETE ──
    if ($ax === 'del' && ($isAdmin || true)) {
        $id = (int)$get('id');
        $r  = db()->prepare("SELECT photo,created_by FROM name_slips WHERE id=?"); $r->execute([$id]); $r=$r->fetch();
        if ($r && ((int)$r['created_by']===$uid || $isAdmin)) {
            if ($r['photo']) { $fp=__DIR__.'/../assets/uploads/'.$r['photo']; if(file_exists($fp)) unlink($fp); }
            db()->prepare("DELETE FROM name_slips WHERE id=?")->execute([$id]);
            echo json_encode(['ok'=>true]); exit;
        }
        echo json_encode(['ok'=>false,'msg'=>'Permission denied']); exit;
    }

    // ── BULK CSV ──
    if ($ax === 'bulk' && $isAdmin) {
        if (!empty($_FILES['f']['name']) && $_FILES['f']['error']===0) {
            $fh=fopen($_FILES['f']['tmp_name'],'r'); fgetcsv($fh); $n=0;
            $st=db()->prepare("INSERT INTO name_slips(student_name,school_name,class_grade,division,parent_name,contact_number,subject,template_id,created_by)VALUES(?,?,?,?,?,?,?,1,?)");
            while(($row=fgetcsv($fh))!==false){
                if(empty($row[0])) continue;
                $st->execute([trim($row[0]??''),trim($row[1]??''),trim($row[2]??''),trim($row[3]??''),trim($row[4]??''),trim($row[5]??''),trim($row[6]??'General'),$uid]);
                $n++;
            }
            fclose($fh);
            echo json_encode(['ok'=>true,'count'=>$n,'msg'=>"✅ $n slips imported!"]);
        } else echo json_encode(['ok'=>false,'msg'=>'Upload failed.']);
        exit;
    }
    echo json_encode(['ok'=>false,'msg'=>'Unknown action']); exit;
}

// ── List data ───────────────────────────────────────────────
$fQ   = trim($_GET['q']   ?? '');
$fSj  = trim($_GET['sj']  ?? '');
$fCls = trim($_GET['cls'] ?? '');
$pg   = max(1,(int)($_GET['pg']??1));
$pp   = 24;
$wh=[];$pr=[];
if (!$isAdmin) { $wh[]="created_by=?"; $pr[]=$uid; }
if ($fQ)  { $wh[]="(student_name LIKE ? OR school_name LIKE ?)"; $pr[]="%$fQ%"; $pr[]="%$fQ%"; }
if ($fSj) { $wh[]="subject=?"; $pr[]=$fSj; }
if ($fCls){ $wh[]="class_grade=?"; $pr[]=$fCls; }
$wh[]="status='active'";
$ws = implode(' AND ',$wh);
$cnt=db()->prepare("SELECT COUNT(*) FROM name_slips WHERE $ws"); $cnt->execute($pr); $total=(int)$cnt->fetchColumn();
$pages=max(1,ceil($total/$pp)); $offset=($pg-1)*$pp;
$ls=db()->prepare("SELECT * FROM name_slips WHERE $ws ORDER BY created_at DESC LIMIT $pp OFFSET $offset"); $ls->execute($pr); $slips=$ls->fetchAll();
try{ $stats=['total'=>(int)db()->query("SELECT COUNT(*) FROM name_slips")->fetchColumn(),'mine'=>(int)db()->prepare("SELECT COUNT(*) FROM name_slips WHERE created_by=?")->execute([$uid]) ? (int)db()->prepare("SELECT COUNT(*) FROM name_slips WHERE created_by=?")->execute([$uid]) : 0,'today'=>(int)db()->query("SELECT COUNT(*) FROM name_slips WHERE DATE(created_at)=CURDATE()")->fetchColumn()]; } catch(Exception $e){ $stats=['total'=>0,'mine'=>0,'today'=>0]; }
$cntMe=db()->prepare("SELECT COUNT(*) FROM name_slips WHERE created_by=?"); $cntMe->execute([$uid]); $stats['mine']=(int)$cntMe->fetchColumn();
try{ $sj_list=db()->query("SELECT DISTINCT subject FROM name_slips WHERE status='active' ORDER BY subject")->fetchAll(PDO::FETCH_COLUMN); }catch(Exception $e){ $sj_list=[]; }
?>
<?php
// Preload logo for slip header
$LOGO_B64 = getLogoB64();
$SLIP_PROFILE_BASE = rtrim(SITE_URL,'/').'/modules/nameslip.php?view=';
require_once __DIR__.'/../includes/header.php';
?>

<!-- Extra fonts for name slip designs -->
<link href="https://fonts.googleapis.com/css2?family=Pacifico&family=Fredoka+One&family=Nunito:wght@400;700;800;900&family=Dancing+Script:wght@700&family=Bebas+Neue&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.js"></script>

<style>
/* ═══════════════════════════════════════════
   NAME SLIP GENERATOR — COMPLETE MODULE CSS
   ═══════════════════════════════════════════ */
*{-webkit-tap-highlight-color:transparent}

/* ── App Shell ── */
.nsg{max-width:520px;margin:0 auto;padding-bottom:76px;min-height:calc(100vh - 66px)}

/* ── Header Bar ── */
.nsg-bar{
  background:linear-gradient(135deg,#1a237e 0%,#1565c0 60%,#0288d1 100%);
  padding:.9rem 1rem;display:flex;align-items:center;gap:.75rem;
  border-bottom:3px solid #ffc107;margin-bottom:0;
}
.nsg-back{width:36px;height:36px;background:rgba(255,255,255,.15);border-radius:10px;display:flex;align-items:center;justify-content:center;color:#fff;border:none;cursor:pointer;font-size:.9rem;text-decoration:none;flex-shrink:0}
.nsg-head{flex:1}
.nsg-head h1{font-size:.92rem;font-weight:800;color:#fff;margin:0;line-height:1.2}
.nsg-head p{font-size:.6rem;color:rgba(255,255,255,.65);margin:0}
.nsg-pills{display:flex;gap:.4rem;flex-shrink:0}
.nsg-pill{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);border-radius:20px;padding:.2rem .6rem;font-size:.65rem;font-weight:800;color:#fff}

/* ── Stats row ── */
.nsg-stats{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border-bottom:1px solid #e8ecf4}
.nsg-stat{padding:.6rem .5rem;text-align:center}
.nsg-stat-n{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;color:#1565c0;line-height:1}
.nsg-stat-l{font-size:.58rem;color:#90a4ae;font-weight:700;letter-spacing:.05em;text-transform:uppercase}

/* ── Bottom Nav ── */
.nsg-nav{
  position:fixed;bottom:calc(62px + env(safe-area-inset-bottom,0px));left:50%;transform:translateX(-50%);
  width:100%;max-width:520px;background:#fff;
  border-top:1.5px solid #e8ecf4;display:flex;z-index:700;
  box-shadow:0 -4px 20px rgba(26,35,126,.08);
}
.nsg-ni{flex:1;display:flex;flex-direction:column;align-items:center;padding:.46rem .2rem .38rem;cursor:pointer;border:none;background:none;font-family:'DM Sans',sans-serif;position:relative}
.nsg-ni .ic{font-size:1.2rem;line-height:1;transition:transform .2s}
.nsg-ni .lb{font-size:.55rem;font-weight:700;color:#b0bec5;margin-top:.15rem;letter-spacing:.04em;text-transform:uppercase}
.nsg-ni.on .lb{color:#1565c0}
.nsg-ni.on .ic{transform:translateY(-2px)}
.nsg-ni.on::after{content:'';position:absolute;top:0;left:22%;right:22%;height:2.5px;background:#1565c0;border-radius:0 0 3px 3px}

/* ── Screens ── */
.nsg-scr{display:none}
.nsg-scr.on{display:block;animation:nsgIn .22s ease}
@keyframes nsgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ═══ FORM SCREEN ═══ */
.nsg-form{padding:.8rem}

.nsg-sh{font-size:.68rem;font-weight:800;color:#1565c0;letter-spacing:.1em;text-transform:uppercase;
        margin:.85rem 0 .45rem;display:flex;align-items:center;gap:.4rem}

.nsg-fi{margin-bottom:.65rem}
.nsg-fi label{display:block;font-size:.67rem;font-weight:700;color:#607d8b;letter-spacing:.06em;text-transform:uppercase;margin-bottom:.22rem}
.nsg-fi input,.nsg-fi select,.nsg-fi textarea{
  width:100%;padding:.7rem .9rem;border:2px solid #e3e7ff;border-radius:12px;
  font-family:'DM Sans',sans-serif;font-size:.9rem;color:#1a237e;background:#fff;
  outline:none;transition:border-color .15s,box-shadow .15s;-webkit-appearance:none;
}
.nsg-fi input:focus,.nsg-fi select:focus,.nsg-fi textarea:focus{
  border-color:#1565c0;box-shadow:0 0 0 3px rgba(21,101,192,.1);
}
.nsg-fi textarea{resize:none;height:58px;font-size:.85rem}
.nsg-r2{display:grid;grid-template-columns:1fr 1fr;gap:.55rem}
.nsg-r3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.45rem}

/* ── Photo Upload ── */
.photo-area{display:flex;gap:.75rem;align-items:flex-start;margin-bottom:.7rem;position:relative}
.photo-drop{
  width:86px;height:100px;border-radius:14px;border:2.5px dashed #90caf9;
  background:#e3f2fd;display:flex;flex-direction:column;align-items:center;
  justify-content:center;flex-shrink:0;cursor:pointer;overflow:hidden;position:relative;
  transition:all .2s;
}
.photo-drop.has{border-style:solid;border-color:#1565c0;box-shadow:0 0 0 3px rgba(21,101,192,.12)}
.photo-drop img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:12px}
.photo-drop .pd-icon{font-size:1.8rem;margin-bottom:.2rem;display:block}
.photo-drop .pd-txt{font-size:.52rem;color:#90caf9;font-weight:700;text-align:center;padding:0 .3rem}
.photo-drop .pd-badge{
  position:absolute;bottom:-1px;left:0;right:0;background:rgba(21,101,192,.85);
  color:#fff;font-size:.48rem;font-weight:800;text-align:center;padding:.15rem 0;
  letter-spacing:.05em;text-transform:uppercase;
}
.photo-btns{display:flex;flex-direction:column;gap:.4rem;flex:1}
.pab{display:flex;align-items:center;gap:.5rem;padding:.55rem .85rem;border-radius:10px;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;font-size:.78rem;font-weight:700;transition:all .15s;-webkit-tap-highlight-color:transparent}
.pab:active{transform:scale(.95)}
.pab-cam{background:#1565c0;color:#fff}
.pab-upl{background:#e3f2fd;color:#1565c0}
.pab-del{background:#ffebee;color:#c62828;display:none}

/* ── Subject Picker ── */
.subj-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.45rem}
.sj-btn{
  border:2px solid #e3e7ff;border-radius:12px;padding:.55rem .3rem;
  background:#fff;cursor:pointer;transition:all .2s;
  display:flex;flex-direction:column;align-items:center;gap:.28rem;
  -webkit-tap-highlight-color:transparent;
}
.sj-btn:active{transform:scale(.94)}
.sj-btn.on{transform:scale(1.05);box-shadow:0 4px 14px rgba(0,0,0,.12)}
.sj-btn .sji{font-size:1.5rem;line-height:1}
.sj-btn .sjl{font-size:.6rem;font-weight:800;color:#546e7a;text-align:center}

/* ── Template Picker ── */
.tpl-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem}
.tp-btn{
  border:2px solid #e3e7ff;border-radius:12px;overflow:hidden;
  cursor:pointer;transition:all .2s;-webkit-tap-highlight-color:transparent;
  position:relative;
}
.tp-btn:active{transform:scale(.94)}
.tp-btn.on{border-color:#1565c0;box-shadow:0 0 0 3px rgba(21,101,192,.2)}
.tp-preview{height:72px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.2rem;padding:.4rem}
.tp-preview .tp-name-line{height:6px;border-radius:3px;width:70%;opacity:.8}
.tp-preview .tp-field-line{height:3px;border-radius:2px;width:88%;opacity:.4}
.tp-preview .tp-field-line2{height:3px;border-radius:2px;width:65%;opacity:.3}
.tp-label{font-size:.55rem;font-weight:800;text-align:center;padding:.22rem .3rem;border-top:1px solid rgba(0,0,0,.06);letter-spacing:.04em}

/* ── Save Bar ── */
.nsg-save-bar{
  position:sticky;bottom:76px;padding:.7rem .8rem;
  background:linear-gradient(to top,#F0F4FA 55%,transparent);
  display:flex;gap:.5rem;
}
.btn-primary{
  flex:1;padding:.82rem;background:linear-gradient(135deg,#0d47a1,#1565c0);
  color:#fff;border:none;border-radius:13px;font-family:'DM Sans',sans-serif;
  font-size:.9rem;font-weight:800;cursor:pointer;letter-spacing:.02em;
  display:flex;align-items:center;justify-content:center;gap:.45rem;
  box-shadow:0 5px 18px rgba(13,71,161,.3);transition:transform .15s;
}
.btn-primary:active{transform:scale(.97)}
.btn-primary:disabled{opacity:.6;transform:none}
.btn-sec{
  padding:.82rem .9rem;background:#fff;color:#1565c0;
  border:2px solid #c5cae9;border-radius:13px;cursor:pointer;
  font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:700;
  transition:all .15s;
}

/* ═══ PREVIEW SCREEN ═══ */
.nsg-prev{padding:.8rem}
.prev-tpl-bar{
  display:flex;gap:.4rem;overflow-x:auto;padding:.5rem;
  background:#fff;border-radius:13px;margin-bottom:.75rem;
  box-shadow:0 2px 10px rgba(26,35,126,.07);
}
.prev-tpl-bar::-webkit-scrollbar{display:none}
.ptb{
  min-width:46px;height:36px;border-radius:8px;border:2px solid #e3e7ff;
  flex-shrink:0;cursor:pointer;transition:all .18s;display:flex;align-items:center;
  justify-content:center;font-size:.55rem;font-weight:800;letter-spacing:.04em;
  padding:.1rem .3rem;text-align:center;line-height:1.2;
}
.ptb.on{border-color:#1565c0;box-shadow:0 0 0 2px rgba(21,101,192,.2)}

/* Download actions */
.dl-actions{display:grid;grid-template-columns:repeat(3,1fr);gap:.45rem;margin-top:.8rem}
.dl-btn{
  padding:.65rem .4rem;border:none;border-radius:11px;
  font-family:'DM Sans',sans-serif;font-size:.72rem;font-weight:800;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:.3rem;transition:all .15s;
}
.dl-btn:active{transform:scale(.95)}
.dl-btn .db-icon{font-size:1.3rem}
.dl-print{background:#0d47a1;color:#fff}
.dl-print4{background:#1b5e20;color:#fff}
.dl-pdf{background:#c62828;color:#fff}
.dl-png{background:#6a1b9a;color:#fff}
.dl-png2{background:#e65100;color:#fff}

/* ═══ SLIP CARD DESIGNS ═══ */
/* Common */
.nsc{
  width:100%;border-radius:16px;overflow:hidden;position:relative;
  font-family:'DM Sans',sans-serif;
  box-shadow:0 6px 24px rgba(0,0,0,.15);
}
.nsc-inner{display:flex;gap:.7rem;align-items:flex-start;padding:.8rem .9rem .75rem}
.nsc-photo{
  width:78px;height:92px;border-radius:12px;overflow:hidden;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:1.8rem;
}
.nsc-photo img{width:100%;height:100%;object-fit:cover}
.nsc-body{flex:1;min-width:0}
.nsc-name{font-family:'Pacifico',cursive;line-height:1.15;margin-bottom:.3rem;word-break:break-word}
.nsc-subj-badge{
  display:inline-flex;align-items:center;gap:.3rem;
  padding:.2rem .55rem;border-radius:20px;font-size:.62rem;font-weight:800;
  letter-spacing:.04em;margin-bottom:.35rem;
}
.nsc-row{font-size:.72rem;margin-bottom:.2rem;display:flex;align-items:baseline;gap:.25rem;color:#444}
.nsc-row .rk{font-weight:800;min-width:50px;flex-shrink:0}
.nsc-row .rd{flex:1;border-bottom:1px dotted rgba(0,0,0,.15);min-height:1px;margin:0 .15rem .1rem;align-self:flex-end}
.nsc-row .rv{font-weight:700;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nsc-footer{display:flex;align-items:center;justify-content:space-between;padding:.5rem .9rem;border-top:1px solid rgba(0,0,0,.07)}
.nsc-school{font-size:.62rem;font-weight:700;font-style:italic;opacity:.7}
.nsc-qr{width:36px;height:36px;border-radius:6px;overflow:hidden;flex-shrink:0;background:#fff;display:flex;align-items:center;justify-content:center}
.nsc-qr img{width:100%;height:100%;display:block}
/* decorative corner lines */
.nsc-corner{position:absolute;width:12px;height:12px;border-color:rgba(255,255,255,.5);border-style:solid}
.nsc-corner.tl{top:6px;left:6px;border-width:2px 0 0 2px}
.nsc-corner.tr{top:6px;right:6px;border-width:2px 2px 0 0}
.nsc-corner.bl{bottom:6px;left:6px;border-width:0 0 2px 2px}
.nsc-corner.br{bottom:6px;right:6px;border-width:0 2px 2px 0}

/* ── Template 1: Classic School ── */
.t1 .nsc-header{padding:.65rem .9rem;display:flex;align-items:center;gap:.6rem}
.t1 .nsc-header-logo{width:30px;height:30px;border-radius:8px;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:.9rem;flex-shrink:0}
.t1 .nsc-header-title{font-size:.72rem;font-weight:800;color:#fff;letter-spacing:.08em;text-transform:uppercase;line-height:1.2}
.t1 .nsc-header-sub{font-size:.56rem;color:rgba(255,255,255,.7);margin-top:.06rem}
.t1 .nsc-name{font-size:1.7rem;color:#1a237e}
.t1 .nsc-row{color:#37474f}
.t1 .nsc-row .rk{color:#1a237e}
.t1 .nsc-footer{background:#f3f4ff}

/* ── Template 2: Modern Colorful ── */
.t2{border:none}
.t2 .color-stripe{height:8px}
.t2 .nsc-name{font-size:1.75rem}
.t2 .nsc-photo{border-radius:50%;border:3px solid #fff;box-shadow:0 4px 14px rgba(0,0,0,.15)}
.t2 .nsc-inner{padding:.85rem .9rem .7rem}
.t2 .nsc-footer{background:rgba(255,255,255,.5)}

/* ── Template 3: Cartoon Kids ── */
.t3{border:4px solid}
.t3 .nsc-name{font-family:'Fredoka One',cursive;font-size:1.8rem}
.t3 .nsc-photo{border-radius:50%;border:4px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.2)}
.t3 .bubbles{position:absolute;top:4px;right:8px;font-size:.9rem;opacity:.4;letter-spacing:.1rem}

/* ── Template 4: Minimal Premium ── */
.t4{background:#fff;border:2px solid}
.t4 .t4-top{height:5px}
.t4 .nsc-name{font-family:'Nunito',sans-serif;font-size:1.7rem;font-weight:900}
.t4 .nsc-photo{border-radius:10px;border:2px solid #e8ecf4}
.t4 .nsc-row{color:#455a64;font-size:.7rem}
.t4 .nsc-row .rk{color:#1565c0}
.t4 .nsc-footer{background:#f8f9ff}

/* ── Template 5: Sports Theme ── */
.t5{color:#fff}
.t5 .jersey-header{padding:.6rem .9rem;display:flex;align-items:center;gap:.5rem;border-bottom:2px solid rgba(255,255,255,.2)}
.t5 .j-num{font-family:'Bebas Neue',sans-serif;font-size:1.6rem;line-height:1;color:#ffd54f}
.t5 .j-title{font-family:'Bebas Neue',sans-serif;font-size:.9rem;letter-spacing:.12em;color:#fff}
.t5 .j-badge{margin-left:auto;background:rgba(255,255,255,.15);border-radius:20px;padding:.2rem .55rem;font-size:.6rem;font-weight:800;letter-spacing:.06em}
.t5 .nsc-name{font-family:'Bebas Neue',sans-serif;font-size:2rem;letter-spacing:.05em;color:#ffd54f;text-shadow:0 2px 8px rgba(0,0,0,.3)}
.t5 .nsc-photo{border:3px solid rgba(255,255,255,.35);box-shadow:0 4px 14px rgba(0,0,0,.3)}
.t5 .nsc-row{color:rgba(255,255,255,.7);font-size:.7rem}
.t5 .nsc-row .rk{color:#a5d6a7}
.t5 .nsc-footer{background:rgba(0,0,0,.15);border-top-color:rgba(255,255,255,.1)}
.t5 .nsc-school{color:rgba(255,255,255,.5)}

/* ── Template 6: Arts Theme ── */
.t6{border:3px solid #e91e63}
.t6 .art-top{height:6px;background:linear-gradient(90deg,#e91e63,#9c27b0,#2196f3,#4caf50,#ffc107,#ff5722)}
.t6 .nsc-name{font-family:'Pacifico',cursive;font-size:1.65rem}
.t6 .nsc-photo{border-radius:50%;border:3px solid #e91e63}
.t6 .art-dec{position:absolute;top:8px;right:8px;font-size:1.4rem;opacity:.25;letter-spacing:.05rem}
.t6 .nsc-footer{background:#fff3f9}

/* ── Subject theme overrides ── */
/* Applied via JS */

/* ═══ LIST SCREEN ═══ */
.nsg-list{padding:.75rem}
.list-search-row{display:flex;gap:.45rem;margin-bottom:.6rem}
.list-search-row input{
  flex:1;padding:.62rem .85rem;border:2px solid #e3e7ff;border-radius:11px;
  font-family:'DM Sans',sans-serif;font-size:.87rem;outline:none;background:#fff;
  color:#1a237e;
}
.list-search-row input:focus{border-color:#1565c0}
.list-filter-row{display:flex;gap:.35rem;overflow-x:auto;padding-bottom:.3rem;margin-bottom:.7rem}
.list-filter-row::-webkit-scrollbar{display:none}
.lfc{padding:.3rem .7rem;border-radius:20px;border:2px solid #e3e7ff;background:#fff;
     font-size:.7rem;font-weight:800;color:#90a4ae;cursor:pointer;white-space:nowrap;flex-shrink:0;transition:all .15s}
.lfc.on{background:#1565c0;color:#fff;border-color:#1565c0}
.slip-cards{display:grid;grid-template-columns:1fr 1fr;gap:.55rem}
.sc{background:#fff;border-radius:13px;border:2px solid #e3e7ff;overflow:hidden;transition:all .18s;cursor:pointer}
.sc:active{transform:scale(.97)}
.sc .sc-top{height:46px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;position:relative}
.sc .sc-top img{width:42px;height:42px;object-fit:cover;border-radius:50%;border:2px solid #fff}
.sc .sc-sj{position:absolute;top:3px;right:4px;font-size:.52rem;font-weight:800;padding:.1rem .4rem;border-radius:10px;color:#fff}
.sc .sc-body{padding:.55rem .65rem}
.sc .sc-name{font-size:.82rem;font-weight:800;color:#1a237e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc .sc-meta{font-size:.65rem;color:#90a4ae;margin-top:.12rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc .sc-acts{display:flex;gap:.3rem;margin-top:.45rem}
.sca{flex:1;padding:.3rem .2rem;border:none;border-radius:7px;cursor:pointer;font-size:.65rem;font-weight:700;text-align:center;transition:all .15s;font-family:'DM Sans',sans-serif}
.sca:active{transform:scale(.92)}
.sca-v{background:#e3f2fd;color:#1565c0}
.sca-e{background:#fff8e1;color:#f57f17}
.sca-d{background:#ffebee;color:#c62828}
.sca-p{background:#e8f5e9;color:#2e7d32}
.empty-state{grid-column:1/-1;text-align:center;padding:2.5rem 1rem;color:#b0bec5}
.empty-state .ei{display:block;font-size:2.5rem;margin-bottom:.6rem;opacity:.5}
.empty-state p{font-size:.8rem}

/* ── Crop Modal ── */
.crop-modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:9500;flex-direction:column}
.crop-modal.on{display:flex}
.crop-hdr{display:flex;align-items:center;justify-content:space-between;padding:.7rem 1rem;background:#111;flex-shrink:0}
.crop-hdr h4{color:#fff;font-size:.9rem;font-weight:700;margin:0}
.crop-hdr-btns{display:flex;gap:.5rem}
.crop-vp{flex:1;overflow:hidden;background:#000;display:flex;align-items:center;justify-content:center;position:relative}
.crop-vp img{max-width:100%;max-height:100%;display:block}
.crop-ftr{padding:.85rem 1rem;background:#111;display:flex;gap:.6rem;flex-shrink:0}
.crop-btn{flex:1;padding:.72rem;border:none;border-radius:11px;font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:800;cursor:pointer;transition:all .15s}
.crop-btn:active{transform:scale(.96)}
.crop-ok{background:#1565c0;color:#fff}
.crop-cancel{background:rgba(255,255,255,.12);color:#fff}
.crop-ratio-row{display:flex;gap:.4rem;padding:.5rem 1rem 0;background:#111;flex-shrink:0}
.crop-ratio-btn{flex:1;padding:.35rem;border:1.5px solid rgba(255,255,255,.2);border-radius:8px;background:rgba(255,255,255,.08);color:rgba(255,255,255,.7);font-size:.7rem;font-weight:700;cursor:pointer;text-align:center;transition:all .15s}
.crop-ratio-btn.on{border-color:#1565c0;background:#1565c0;color:#fff}

/* ── Camera modal ── */
.cam-modal{display:none;position:fixed;inset:0;background:#000;z-index:9000;flex-direction:column}
.cam-modal.on{display:flex}
.cam-hdr{display:flex;align-items:center;justify-content:space-between;padding:.7rem 1rem;background:#111}
.cam-hdr h4{color:#fff;font-size:.88rem;font-weight:700;margin:0}
.cam-hdr button{background:rgba(255,255,255,.12);border:none;color:#fff;width:32px;height:32px;border-radius:8px;cursor:pointer;font-size:.9rem;display:flex;align-items:center;justify-content:center}
.cam-vp{flex:1;position:relative;overflow:hidden;background:#000}
.cam-vp video{width:100%;height:100%;object-fit:cover}
.cam-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none}
.cam-oval{width:160px;height:200px;border:2.5px solid rgba(255,255,255,.7);border-radius:50%;box-shadow:0 0 0 9999px rgba(0,0,0,.45)}
.cam-ftr{padding:1.1rem;background:#111;display:flex;align-items:center;justify-content:center;gap:1.2rem}
.cam-shoot{width:64px;height:64px;background:#fff;border:none;border-radius:50%;cursor:pointer;font-size:1.5rem;box-shadow:0 0 0 4px rgba(255,255,255,.25);transition:transform .15s;display:flex;align-items:center;justify-content:center}
.cam-shoot:active{transform:scale(.9)}
.cam-flip{width:44px;height:44px;background:rgba(255,255,255,.12);border:none;border-radius:50%;color:#fff;font-size:1rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
.cam-cvs{display:none}

/* ── Drag position overlay ── */
.photo-drag-hint{font-size:.58rem;color:#90caf9;text-align:center;margin-top:.2rem}

/* ── Toast ── */
.nsg-toast{
  position:fixed;bottom:calc(148px + env(safe-area-inset-bottom,0px));left:50%;transform:translateX(-50%) translateY(20px);
  background:#1565c0;color:#fff;padding:.6rem 1.2rem;border-radius:25px;
  font-size:.8rem;font-weight:700;z-index:9999;opacity:0;transition:all .28s;
  white-space:nowrap;box-shadow:0 5px 18px rgba(21,101,192,.4);pointer-events:none;
}
.nsg-toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.nsg-toast.err{background:#c62828}

/* ── Bulk upload ── */
.bulk-drop{border:2px dashed #90caf9;border-radius:14px;padding:1.8rem 1rem;text-align:center;cursor:pointer;background:#e3f2fd;transition:all .2s;margin-bottom:.7rem}
.bulk-drop:hover{border-color:#1565c0;background:#bbdefb}
</style>

<?php
// Subject configuration
$SUBJ = [
  'General'         => ['icon'=>'📄','color'=>'#455a64','bg'=>'#eceff1','badge_bg'=>'#90a4ae','badge_fg'=>'#fff'],
  'Science'         => ['icon'=>'🔬','color'=>'#0d47a1','bg'=>'#e3f2fd','badge_bg'=>'#1565c0','badge_fg'=>'#fff'],
  'Mathematics'     => ['icon'=>'📐','color'=>'#1a237e','bg'=>'#e8eaf6','badge_bg'=>'#3949ab','badge_fg'=>'#fff'],
  'English'         => ['icon'=>'📚','color'=>'#4a148c','bg'=>'#f3e5f5','badge_bg'=>'#7b1fa2','badge_fg'=>'#fff'],
  'Social Science'  => ['icon'=>'🌍','color'=>'#1b5e20','bg'=>'#e8f5e9','badge_bg'=>'#2e7d32','badge_fg'=>'#fff'],
  'Arabic'          => ['icon'=>'☪️','color'=>'#004d40','bg'=>'#e0f2f1','badge_bg'=>'#00695c','badge_fg'=>'#fff'],
  'Malayalam'       => ['icon'=>'🌺','color'=>'#b71c1c','bg'=>'#ffebee','badge_bg'=>'#c62828','badge_fg'=>'#fff'],
  'Computer Science'=> ['icon'=>'💻','color'=>'#311b92','bg'=>'#ede7f6','badge_bg'=>'#4527a0','badge_fg'=>'#fff'],
  'Hindi'           => ['icon'=>'🇮🇳','color'=>'#bf360c','bg'=>'#fbe9e7','badge_bg'=>'#d84315','badge_fg'=>'#fff'],
];
// Template config
$TPLS = [
  1=>['label'=>'Classic','name_color'=>'#1a237e','bg'=>'linear-gradient(135deg,#f8f9ff,#e8eaf6)','header'=>'#1565c0'],
  2=>['label'=>'Modern','name_color'=>'#0d47a1','bg'=>'#fff','header'=>null],
  3=>['label'=>'Cartoon','name_color'=>'#e91e63','bg'=>'linear-gradient(145deg,#fff9c4,#f3e5f5)','header'=>null],
  4=>['label'=>'Minimal','name_color'=>'#1565c0','bg'=>'#fff','header'=>null],
  5=>['label'=>'Sports','name_color'=>'#ffd54f','bg'=>'linear-gradient(145deg,#1b5e20,#2e7d32)','header'=>null],
  6=>['label'=>'Arts','name_color'=>'#e91e63','bg'=>'linear-gradient(145deg,#fff8e1,#fce4ec)','header'=>null],
];
?>

<div class="nsg">

  <!-- Header -->
  <div class="nsg-bar">
    <a href="<?= url('dashboard.php') ?>" class="nsg-back"><i class="fas fa-arrow-left"></i></a>
    <div class="nsg-head">
      <h1>📚 Book Name Slip Generator</h1>
      <p><?= h($CLUB) ?> · <?= h($PLACE) ?></p>
    </div>
    <div class="nsg-pills">
      <span class="nsg-pill"><?= $stats['total'] ?> Slips</span>
    </div>
  </div>

  <!-- Stats -->
  <div class="nsg-stats">
    <div class="nsg-stat"><div class="nsg-stat-n"><?= $stats['total'] ?></div><div class="nsg-stat-l">Total</div></div>
    <div class="nsg-stat"><div class="nsg-stat-n"><?= $stats['mine'] ?></div><div class="nsg-stat-l">Mine</div></div>
    <div class="nsg-stat"><div class="nsg-stat-n"><?= $stats['today'] ?></div><div class="nsg-stat-l">Today</div></div>
  </div>

  <!-- ═══ SCREEN: FORM ═══ -->
  <div class="nsg-scr on" id="scr-form">
    <div class="nsg-form">

      <!-- Photo Upload -->
      <div class="nsg-sh">📷 Student Photo</div>
      <div class="photo-area">
        <div>
          <div class="photo-drop" id="pDrop" onclick="document.getElementById('pFile').click()">
            <span class="pd-icon">👤</span>
            <span class="pd-txt">Tap to add photo</span>
          </div>
          <div class="photo-drag-hint">Drag photo to reposition</div>
        </div>
        <div class="photo-btns">
          <button type="button" class="pab pab-cam" id="openCamBtn" onclick="openCam()">
            <i class="fas fa-camera"></i> Camera
          </button>
          <label class="pab pab-upl" for="pFile">
            <i class="fas fa-image"></i> Gallery
          </label>
          <button type="button" class="pab pab-del" id="delPhotoBtn" onclick="clearPhoto()">
            <i class="fas fa-trash"></i> Remove
          </button>
        </div>
        <input type="file" id="pFile" accept="image/*" style="display:none" onchange="onPhotoFile(this)">
        <input type="hidden" id="f_photo_b64">
        <input type="hidden" id="f_photo_x" value="50">
        <input type="hidden" id="f_photo_y" value="50">
      </div>

      <!-- Student Info -->
      <div class="nsg-sh">👤 Student Details</div>
      <div class="nsg-fi">
        <label>Full Name *</label>
        <input type="text" id="f_name" placeholder="e.g. Fathima Zahra, Arjun Nair" oninput="updatePreview()">
      </div>
      <div class="nsg-fi">
        <label>School Name</label>
        <input type="text" id="f_school" placeholder="e.g. Govt. High School, Vettikkattiri" oninput="updatePreview()">
      </div>
      <div class="nsg-r2">
        <div class="nsg-fi"><label>Class / Std</label><input type="text" id="f_class" placeholder="5th" oninput="updatePreview()"></div>
        <div class="nsg-fi"><label>Division</label><input type="text" id="f_div" placeholder="A" oninput="updatePreview()"></div>
      </div>
      <div class="nsg-fi"><label>📞 Phone Number</label><input type="tel" id="f_contact" placeholder="+91 XXXXX XXXXX" oninput="updatePreview()"></div>


      <!-- Subject -->
      <div class="nsg-sh">📖 Subject</div>
      <div class="subj-grid" id="subjGrid">
        <?php foreach($SUBJ as $sid=>$sc): ?>
        <div class="sj-btn <?= $sid==='General'?'on':'' ?>"
             data-id="<?= h($sid) ?>"
             style="<?= $sid==='General'?'border-color:'.$sc['color'].';background:'.$sc['bg']:'' ?>"
             onclick="pickSubj('<?= h($sid) ?>')">
          <span class="sji"><?= $sc['icon'] ?></span>
          <span class="sjl"><?= h(strlen($sid)>9 ? substr($sid,0,7).'…' : $sid) ?></span>
        </div>
        <?php endforeach; ?>
      </div>
      <input type="hidden" id="f_subj" value="General">

      <!-- Template -->
      <div class="nsg-sh">🎨 Template Style</div>
      <div class="tpl-grid" id="tplGrid">
        <?php
        $tpl_configs = [
          1=>['bg'=>'linear-gradient(145deg,#29b6f6,#b3e5fc)','bar'=>'#0277bd','text'=>'🐦 Sky'],
          2=>['bg'=>'linear-gradient(180deg,#87ceeb,#66bb6a)','bar'=>'#1b5e20','text'=>'🌿 Jungle'],
          3=>['bg'=>'linear-gradient(150deg,#0a0015,#1565c0)','bar'=>'#90caf9','text'=>'🚀 Space'],
          4=>['bg'=>'#fff','bar'=>'#1565c0','text'=>'✏️ School'],
          5=>['bg'=>'linear-gradient(150deg,#ff8f00,#fff8e1)','bar'=>'#bf360c','text'=>'🌺 Kerala'],
          6=>['bg'=>'#fff','bar'=>'#e91e63','text'=>'🎨 Art'],
        ];
        foreach($tpl_configs as $tid=>$t): ?>
        <div class="tp-btn <?= $tid===1?'on':'' ?>" data-id="<?= $tid ?>" onclick="pickTpl(<?= $tid ?>)">
          <div class="tp-preview" style="background:<?= $t['bg'] ?>">
            <div class="tp-name-line" style="background:<?= $t['bar'] ?>"></div>
            <div class="tp-field-line" style="background:<?= $t['bar'] ?>"></div>
            <div class="tp-field-line2" style="background:<?= $t['bar'] ?>"></div>
          </div>
          <div class="tp-label" style="color:<?= $t['bar'] ?>;background:<?= is_string($t['bg'])&&strlen($t['bg'])<20 ? $t['bg'] : '#fff' ?>"><?= $t['text'] ?></div>
        </div>
        <?php endforeach; ?>
      </div>
      <input type="hidden" id="f_tpl" value="1">
      <input type="hidden" id="f_edit_id" value="">

      <div class="nsg-save-bar">
        <button class="btn-primary" id="saveBtn" onclick="doSave()">
          <i class="fas fa-save"></i> <span id="saveTxt">Save Slip</span>
        </button>
        <button class="btn-sec" onclick="doReset()"><i class="fas fa-redo"></i></button>
      </div>

    </div>
  </div>

  <!-- ═══ SCREEN: PREVIEW ═══ -->
  <div class="nsg-scr" id="scr-prev">
    <div class="nsg-prev">

      <!-- Mini template bar -->
      <div class="prev-tpl-bar" id="prevTplBar">
        <?php foreach($tpl_configs as $tid=>$t): ?>
        <div class="ptb <?= $tid===1?'on':'' ?>" data-id="<?= $tid ?>"
             style="background:<?= $t['bg'] ?>;color:<?= $t['bar'] ?>"
             onclick="pickTpl(<?= $tid ?>)"><?= $t['text'] ?></div>
        <?php endforeach; ?>
      </div>

      <!-- Live slip display -->
      <div id="slipStage" style="width:100%;overflow:hidden;border-radius:16px;box-shadow:0 8px 28px rgba(0,0,0,.12)"></div>

      <!-- Download actions -->
      <div class="dl-actions">
        <button class="dl-btn dl-print" onclick="printSlip(1)"><span class="db-icon">🖨️</span>Print</button>
        <button class="dl-btn dl-print4" onclick="printSlip(4)"><span class="db-icon">📋</span>4/Page</button>
        <button class="dl-btn dl-pdf" onclick="printSlip(1)"><span class="db-icon">📄</span>PDF</button>
        <button class="dl-btn dl-png" onclick="downloadPNG()"><span class="db-icon">🖼️</span>Image</button>
        <button class="dl-btn dl-png2" onclick="printSlip(8)"><span class="db-icon">📑</span>8/Sheet</button>
      </div>

    </div>
  </div>

  <!-- ═══ SCREEN: ALL SLIPS ═══ -->
  <div class="nsg-scr" id="scr-list">
    <div class="nsg-list">
      <div class="list-search-row">
        <input type="text" id="listQ" placeholder="🔍 Search name, school..." oninput="filterCards()">
        <button onclick="printAllVisible()" style="padding:.6rem .8rem;background:#1b5e20;color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;font-size:.75rem;font-family:'DM Sans',sans-serif;white-space:nowrap;display:flex;align-items:center;gap:.3rem"><i class="fas fa-print"></i> All</button>
        <?php if($isAdmin): ?>
        <button onclick="showScr('bulk')" style="padding:.6rem .8rem;background:#1565c0;color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;font-size:.75rem;font-family:'DM Sans',sans-serif;white-space:nowrap"><i class="fas fa-upload"></i></button>
        <?php endif; ?>
      </div>
      <div class="list-filter-row" id="fRow">
        <div class="lfc on" data-f="" onclick="setF('')">All</div>
        <?php foreach($sj_list as $s): ?><div class="lfc" data-f="<?= h($s) ?>" onclick="setF('<?= h($s) ?>')"><?= h($s) ?></div><?php endforeach; ?>
      </div>
      <div class="slip-cards" id="slipCards">
        <?php if(empty($slips)): ?>
        <div class="empty-state"><span class="ei">📚</span><p>No slips yet. Create the first one!</p></div>
        <?php else: foreach($slips as $sl):
          $sc2 = $SUBJ[$sl['subject']] ?? $SUBJ['General'];
          $ph2 = $sl['photo'] ? photoUrl($sl['photo']) : ''; // direct URL, faster than base64
        ?>
        <div class="sc" data-nm="<?= h(strtolower($sl['student_name'])) ?>" data-sj="<?= h($sl['subject']) ?>" data-id="<?= $sl['id'] ?>">
          <div class="sc-top" style="background:<?= $sc2['bg'] ?>">
            <?php if($ph2): ?><img src="<?= $ph2 ?>" alt=""><?php else: ?><span><?= $sc2['icon'] ?></span><?php endif; ?>
            <span class="sc-sj" style="background:<?= $sc2['badge_bg'] ?>"><?= h($sl['subject']) ?></span>
          </div>
          <div class="sc-body">
            <div class="sc-name"><?= h($sl['student_name']) ?></div>
            <div class="sc-meta">🏫 <?= h($sl['school_name']?:'—') ?> · Std <?= h($sl['class_grade']?:'?') ?><?= $sl['division']?' '.h($sl['division']):'' ?><?= $sl['roll_number']?' · #'.h($sl['roll_number']):'' ?></div>
            <div class="sc-acts">
              <div class="sca sca-v" onclick="loadPrev(<?= $sl['id'] ?>)">👁 View</div>
              <?php if($isAdmin || (int)$sl['created_by']===$uid): ?>
              <div class="sca sca-e" onclick="loadEdit(<?= $sl['id'] ?>)">✏️ Edit</div>
              <?php endif; ?>
              <div class="sca sca-p" onclick="quickPrint(<?= $sl['id'] ?>)">🖨</div>
              <?php if($isAdmin || (int)$sl['created_by']===$uid): ?>
              <div class="sca sca-d" onclick="delSlip(<?= $sl['id'] ?>,this)">🗑</div>
              <?php endif; ?>
            </div>
          </div>
        </div>
        <?php endforeach; endif; ?>
      </div>
      <?php if($pages>1): ?>
      <div style="display:flex;gap:.4rem;justify-content:center;padding:.9rem;flex-wrap:wrap">
        <?php for($p=1;$p<=$pages;$p++): ?>
        <a href="?pg=<?=$p?>&q=<?=urlencode($fQ)?>&sj=<?=urlencode($fSj)?>"
           style="width:30px;height:30px;border-radius:7px;border:2px solid #e3e7ff;background:<?=$p===$pg?'#1565c0':'#fff'?>;color:<?=$p===$pg?'#fff':'#283593'?>;font-size:.78rem;font-weight:700;display:flex;align-items:center;justify-content:center;text-decoration:none"><?=$p?></a>
        <?php endfor; ?>
      </div>
      <?php endif; ?>
    </div>
  </div>

  <!-- ═══ SCREEN: BULK ═══ -->
  <?php if($isAdmin): ?>
  <div class="nsg-scr" id="scr-bulk">
    <div style="padding:.8rem">
      <div class="bulk-drop" onclick="document.getElementById('bulkFile').click()" id="bulkZone">
        <div style="font-size:2.4rem;margin-bottom:.5rem">📊</div>
        <div style="font-weight:800;color:#1565c0;font-size:.9rem;margin-bottom:.3rem">Upload CSV File</div>
        <div style="font-size:.72rem;color:#90a4ae;margin-bottom:.5rem">Name | School | Class | Division | Parent | Contact | Subject</div>
        <div style="background:#fff;border:1px solid #bbdefb;border-radius:8px;padding:.5rem .8rem;display:inline-block;font-size:.68rem;font-family:monospace;color:#1565c0">
          Fathima,Govt HS,7th,A,Ibrahim,+919876543210,Arabic
        </div>
      </div>
      <input type="file" id="bulkFile" accept=".csv" style="display:none" onchange="doBulk(this)">
      <div id="bulkMsg" style="display:none;padding:.75rem;border-radius:10px;font-size:.84rem;font-weight:700;margin-bottom:.7rem"></div>
      <button onclick="dlCSVTpl()" style="width:100%;padding:.78rem;background:#1565c0;color:#fff;border:none;border-radius:12px;font-weight:800;font-size:.85rem;cursor:pointer;font-family:'DM Sans',sans-serif;display:flex;align-items:center;justify-content:center;gap:.5rem"><i class="fas fa-download"></i> Download CSV Template</button>
    </div>
  </div>
  <?php endif; ?>

</div><!-- end .nsg -->

<!-- Bottom nav -->
<div class="nsg-nav">
  <button class="nsg-ni on" id="bn-form" onclick="showScr('form')">
    <span class="ic">✏️</span><span class="lb">New Slip</span>
  </button>
  <button class="nsg-ni" id="bn-prev" onclick="showScr('prev')">
    <span class="ic">👁️</span><span class="lb">Preview</span>
  </button>
  <button class="nsg-ni" id="bn-list" onclick="showScr('list')">
    <span class="ic">📋</span><span class="lb">All Slips</span>
  </button>
  <?php if($isAdmin): ?>
  <button class="nsg-ni" id="bn-bulk" onclick="showScr('bulk')">
    <span class="ic">📤</span><span class="lb">Bulk</span>
  </button>
  <?php endif; ?>
</div>

<!-- Crop Modal -->
<div class="crop-modal" id="cropModal">
  <div class="crop-hdr">
    <h4>✂️ Crop Photo</h4>
    <div class="crop-hdr-btns">
      <button onclick="cropRotate(-90)" style="background:rgba(255,255,255,.12);border:none;color:#fff;padding:.3rem .6rem;border-radius:7px;cursor:pointer;font-size:.8rem">↺ Rotate</button>
      <button onclick="cropFlip()" style="background:rgba(255,255,255,.12);border:none;color:#fff;padding:.3rem .6rem;border-radius:7px;cursor:pointer;font-size:.8rem">⇄ Flip</button>
    </div>
  </div>
  <div class="crop-ratio-row">
    <button class="crop-ratio-btn on" onclick="setCropRatio(1,1,this)">1:1 Square</button>
    <button class="crop-ratio-btn" onclick="setCropRatio(4,5,this)">4:5 Portrait</button>
    <button class="crop-ratio-btn" onclick="setCropRatio(3,4,this)">3:4</button>
    <button class="crop-ratio-btn" onclick="setCropRatio(NaN,NaN,this)">Free</button>
  </div>
  <div class="crop-vp">
    <img id="cropImg" src="" alt="crop">
  </div>
  <div class="crop-ftr">
    <button class="crop-btn crop-cancel" onclick="closeCropModal()">Cancel</button>
    <button class="crop-btn crop-ok" onclick="applyCrop()">✅ Use This Photo</button>
  </div>
</div>

<!-- Camera modal -->
<div class="cam-modal" id="camModal">
  <div class="cam-hdr">
    <h4>📸 Capture Photo</h4>
    <button onclick="closeCam()">✕</button>
  </div>
  <div class="cam-vp">
    <video id="camVid" autoplay playsinline muted></video>
    <div class="cam-overlay"><div class="cam-oval"></div></div>
  </div>
  <canvas class="cam-cvs" id="camCvs"></canvas>
  <div class="cam-ftr">
    <button class="cam-flip" onclick="flipCam()" title="Flip">🔄</button>
    <button class="cam-shoot" onclick="shoot()">📸</button>
    <div style="width:44px"></div>
  </div>
</div>

<!-- Toast -->
<div class="nsg-toast" id="nsgToast"></div>

<!-- hidden print output -->
<div id="printOut" style="display:none"></div>

<script>
// ══════════════════════════════════
//  NAME SLIP GENERATOR — JS
// ══════════════════════════════════
var SELF = <?= json_encode(url('modules/nameslip.php')) ?>;
var CLUB = <?= json_encode($CLUB) ?>;
var PLACE= <?= json_encode($PLACE) ?>;
var LOGO = <?= json_encode(defined('LOGO_URL')?LOGO_URL:'') ?>;
var LOGO_B64 = <?= json_encode($LOGO_B64 ?? '') ?>;
var PROFILE_BASE = <?= json_encode($SLIP_PROFILE_BASE) ?>;
var ME_NAME = <?= json_encode($me['name'] ?? '') ?>;
var ME_ID= <?= $uid ?>;

// ── Subject config ──
var SUBJ = {
  'General':         {icon:'📄',color:'#455a64',bg:'#eceff1',bb:'#90a4ae',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#eceff1,#fff)',border:'#90a4ae'},
  'Science':         {icon:'🔬',color:'#0d47a1',bg:'#e3f2fd',bb:'#1565c0',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#e3f2fd,#f0f8ff)',border:'#42a5f5',
                      deco:'⚗️🧬🔭',pattern:'radial-gradient(circle at 80% 20%,rgba(21,101,192,.08) 0%,transparent 50%)'},
  'Mathematics':     {icon:'📐',color:'#1a237e',bg:'#e8eaf6',bb:'#3949ab',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#e8eaf6,#f5f5ff)',border:'#7986cb',
                      deco:'📐➗∑',pattern:'repeating-linear-gradient(45deg,rgba(57,73,171,.04) 0px,rgba(57,73,171,.04) 1px,transparent 1px,transparent 20px)'},
  'English':         {icon:'📚',color:'#4a148c',bg:'#f3e5f5',bb:'#7b1fa2',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#f3e5f5,#fce4ec)',border:'#ba68c8',
                      deco:'📖✍️🔤',pattern:''},
  'Social Science':  {icon:'🌍',color:'#1b5e20',bg:'#e8f5e9',bb:'#2e7d32',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#e8f5e9,#f1f8e9)',border:'#66bb6a',
                      deco:'🗺️🏛️🌐',pattern:''},
  'Arabic':          {icon:'☪️',color:'#004d40',bg:'#e0f2f1',bb:'#00695c',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#e0f2f1,#e8f5e9)',border:'#4db6ac',
                      deco:'☪️🕌📿',pattern:''},
  'Malayalam':       {icon:'🌺',color:'#b71c1c',bg:'#ffebee',bb:'#c62828',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#ffebee,#fff3e0)',border:'#ef9a9a',
                      deco:'🌺🐘🎭',pattern:''},
  'Computer Science':{icon:'💻',color:'#311b92',bg:'#ede7f6',bb:'#4527a0',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#ede7f6,#e8eaf6)',border:'#9575cd',
                      deco:'💻⌨️🖥️',pattern:'linear-gradient(rgba(69,39,160,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(69,39,160,.04) 1px,transparent 1px)'},
  'Hindi':           {icon:'🇮🇳',color:'#bf360c',bg:'#fbe9e7',bb:'#d84315',bf:'#fff',
                      card_bg:'linear-gradient(135deg,#fbe9e7,#fff8e1)',border:'#ff8a65',
                      deco:'🇮🇳📜🎵',pattern:''},
};

// ── Template backgrounds ──
var TPL_BG = {
  1:'linear-gradient(135deg,#f8f9ff,#e8eaf6)',
  2:'linear-gradient(160deg,#e3f2fd 0%,#fff 60%)',
  3:'linear-gradient(145deg,#fff9c4,#f3e5f5)',
  4:'#fff',
  5:'linear-gradient(145deg,#1b5e20,#2e7d32,#388e3c)',
  6:'linear-gradient(145deg,#fff8e1,#fce4ec)'
};

// ── State ──
var ST = {
  subj:'General', tpl:1,
  photo:'', photoX:50, photoY:50,
  cam:null, facing:'user',
  dragging:false, dragStartX:0, dragStartY:0
};

// ══ SCREENS ══════════════════════════════
function showScr(n) {
  document.querySelectorAll('.nsg-scr').forEach(function(s){ s.classList.remove('on'); });
  document.querySelectorAll('.nsg-ni').forEach(function(b){ b.classList.remove('on'); });
  var sc=document.getElementById('scr-'+n), bn=document.getElementById('bn-'+n);
  if(sc) sc.classList.add('on');
  if(bn) bn.classList.add('on');
  if(n==='prev') buildAndRender();
  window.scrollTo(0,0);
}

// ══ TOAST ════════════════════════════════
function toast(msg,type){
  var el=document.getElementById('nsgToast');
  el.textContent=msg; el.className='nsg-toast on'+(type==='err'?' err':'');
  setTimeout(function(){el.className='nsg-toast';},2800);
}

// ══ SUBJECT ══════════════════════════════
function pickSubj(id){
  ST.subj=id;
  document.getElementById('f_subj').value=id;
  document.querySelectorAll('#subjGrid .sj-btn').forEach(function(b){
    var bid=b.getAttribute('data-id'), cfg=SUBJ[bid]||SUBJ['General'];
    if(bid===id){b.classList.add('on');b.style.borderColor=cfg.color;b.style.background=cfg.bg;}
    else{b.classList.remove('on');b.style.borderColor='#e3e7ff';b.style.background='#fff';}
  });
  updatePreview();
}

// ══ TEMPLATE ═════════════════════════════
function pickTpl(tid){
  ST.tpl=tid;
  document.getElementById('f_tpl').value=tid;
  document.querySelectorAll('#tplGrid .tp-btn, #prevTplBar .ptb').forEach(function(b){
    b.classList.toggle('on', parseInt(b.getAttribute('data-id'))===tid);
  });
  updatePreview();
}

// ══ PHOTO ════════════════════════════════
function onPhotoFile(inp){
  if(!inp.files[0]) return;
  var r=new FileReader();
  r.onload=function(e){ openCropModal(e.target.result); };
  r.readAsDataURL(inp.files[0]);
  // Reset input so same file can be re-selected
  inp.value='';
}
function setPhoto(b64){
  ST.photo=b64;
  document.getElementById('f_photo_b64').value=b64;
  var d=document.getElementById('pDrop');
  d.innerHTML='<img src="'+b64+'" alt="" style="width:100%;height:100%;object-fit:cover;object-position:'+ST.photoX+'% '+ST.photoY+'%"><div class="pd-badge">Drag to reposition</div>';
  d.classList.add('has');
  document.getElementById('delPhotoBtn').style.display='flex';
  setupPhotoDrag();
  updatePreview();
}
function clearPhoto(){
  ST.photo=''; ST.photoX=50; ST.photoY=50;
  document.getElementById('f_photo_b64').value='';
  var d=document.getElementById('pDrop');
  d.innerHTML='<span class="pd-icon">👤</span><span class="pd-txt">Tap to add photo</span>';
  d.classList.remove('has');
  document.getElementById('delPhotoBtn').style.display='none';
  updatePreview();
}

// ── Drag to reposition photo ──
function setupPhotoDrag(){
  var d=document.getElementById('pDrop');
  var img=d.querySelector('img');
  if(!img) return;
  function onStart(e){
    e.preventDefault(); ST.dragging=true;
    var t=e.touches?e.touches[0]:e;
    ST.dragStartX=t.clientX; ST.dragStartY=t.clientY;
  }
  function onMove(e){
    if(!ST.dragging) return;
    e.preventDefault();
    var t=e.touches?e.touches[0]:e;
    var dx=(t.clientX-ST.dragStartX)/d.offsetWidth*100;
    var dy=(t.clientY-ST.dragStartY)/d.offsetHeight*100;
    ST.photoX=Math.max(0,Math.min(100,ST.photoX-dx));
    ST.photoY=Math.max(0,Math.min(100,ST.photoY-dy));
    img.style.objectPosition=ST.photoX+'% '+ST.photoY+'%';
    ST.dragStartX=t.clientX; ST.dragStartY=t.clientY;
  }
  function onEnd(){ ST.dragging=false; updatePreview(); }
  d.removeEventListener('mousedown',onStart); d.addEventListener('mousedown',onStart);
  d.removeEventListener('touchstart',onStart); d.addEventListener('touchstart',onStart,{passive:false});
  document.removeEventListener('mousemove',onMove); document.addEventListener('mousemove',onMove);
  document.removeEventListener('touchmove',onMove); document.addEventListener('touchmove',onMove,{passive:false});
  document.removeEventListener('mouseup',onEnd); document.addEventListener('mouseup',onEnd);
  document.removeEventListener('touchend',onEnd); document.addEventListener('touchend',onEnd);
}

// ══ READ FORM ════════════════════════════
function getFormData(){
  return {
    name:    v('f_name'),    school:  v('f_school'),
    cls:     v('f_class'),   div:     v('f_div'),
    contact: v('f_contact'), subj:    ST.subj,
    tpl:     ST.tpl,         photo:   ST.photo,
    px:      ST.photoX,      py:      ST.photoY
  };
}
function v(id){ var el=document.getElementById(id); return el?(el.value||'').trim():''; }
function e(s){ var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

// ══ BUILD SLIP — LANDSCAPE BOOK NAME LABEL (exact reference style)
// Layout: full-bleed cartoon BG, BIG photo LEFT (40%), name+fields RIGHT
// No frosted box — text directly on BG. School stamp bottom right.
// Fields show dotted lines with values filled in
// ════════════════════════════════════════════════════════════════
function buildSlip(d, forPrint, w){
  var cfg  = SUBJ[d.subj]||SUBJ['General'];
  var name = d.name    || 'Student Name';
  var sch  = d.school  || '';
  var cls  = d.cls     || '';
  var dv   = d.div     || '';
  var sub  = d.subj    || 'General';
  var ph   = d.contact || '';
  var tpl  = d.tpl     || 1;
  var px   = (d.px||50)+'%', py=(d.py||50)+'%';
  // Landscape: wider than tall — ~380×220px
  var W    = forPrint ? (w||380)+'px' : '100%';

  var photoEl = d.photo
    ? '<img src="'+d.photo+'" style="width:100%;height:100%;object-fit:cover;object-position:'+px+' '+py+';display:block">'
    : '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:2.5rem;color:rgba(0,0,0,.15)">👤</div>';

  var clubLogo = LOGO_B64
    ? '<img src="'+LOGO_B64+'" style="width:18px;height:18px;border-radius:50%;object-fit:cover;flex-shrink:0">'
    : '';

  var qrLink = PROFILE_BASE + <?= $uid ?>;
  var qrSrc  = 'https://api.qrserver.com/v1/create-qr-code/?size=100x100&data='+encodeURIComponent(qrLink)+'&margin=2';

  // ── Field row: "Std ............. 7   Div. ......... A" ──
  // Field row pair: "Std  10   Div.  A" — NO DOTS
  function frow2(l1,v1,l2,v2,tc){
    var t=tc||'#222';
    return '<div style="font-size:.8rem;font-weight:700;color:'+t+';margin-bottom:.3rem;display:flex;align-items:center;gap:.45rem;font-family:Nunito,sans-serif">'
      +'<span style="font-weight:900;flex-shrink:0">'+e(l1)+'</span>'
      +'<span style="font-weight:900;flex-shrink:0">'+e(v1||'—')+'</span>'
      +(l2?'<span style="opacity:.3;flex-shrink:0">·</span>'
           +'<span style="font-weight:900;flex-shrink:0;margin-left:.2rem">'+e(l2)+'</span>'
           +'<span style="font-weight:900;flex-shrink:0">'+e(v2||'—')+'</span>':'')
    +'</div>';
  }
  // Single field row — hidden completely when value is empty
  function frow(label,value,tc){
    if(!value) return '';
    var t=tc||'#222';
    return '<div style="font-size:.8rem;font-weight:700;color:'+t+';margin-bottom:.28rem;display:flex;align-items:center;gap:.45rem;font-family:Nunito,sans-serif">'
      +'<span style="font-weight:900;flex-shrink:0">'+e(label)+'</span>'
      +'<span style="font-weight:900;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+e(value)+'</span>'
    +'</div>';
  }
  // Footer: school name ONLY — no logo
  function schoolLine(sch,tc){
    if(!sch) return '';
    var t=tc||'#333';
    return '<div style="display:flex;align-items:center;gap:.3rem;">'
      +'<span style="font-size:.68rem;font-weight:900;color:'+t+';letter-spacing:.14em;text-transform:uppercase;font-family:DM Sans,sans-serif;border-bottom:1.5px solid '+t+';padding-bottom:.05rem">'+sch.toUpperCase()+'</span>'
    +'</div>';
  }

  // Header bar: club logo + club name
  function clubHeader(bgColor, txtColor){
    return '<div style="position:absolute;top:0;left:0;right:0;z-index:10;display:flex;align-items:center;gap:.45rem;padding:.32rem .75rem;background:'+bgColor+';border-radius:16px 16px 0 0">'
      +(LOGO_B64?'<img src="'+LOGO_B64+'" style="width:24px;height:24px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,.5);flex-shrink:0">':'<div style="width:24px;height:24px;border-radius:50%;background:rgba(255,255,255,.25);flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:.6rem">🏛</div>')
      +'<span style="font-size:.6rem;font-weight:900;color:'+txtColor+';letter-spacing:.07em;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+e(CLUB)+'</span>'
    +'</div>';
  }

  // Right panel (name + fields) — used in all templates
  function rightPanel(nameSty, fieldTc, bgPanel){
    var panel = bgPanel
      ? 'background:'+bgPanel+';border-radius:12px;padding:.55rem .7rem .5rem;'
      : 'padding:.55rem .5rem .5rem 0;';
    return '<div style="flex:1;min-width:0;display:flex;flex-direction:column;justify-content:space-between;'+panel+'">'
      // Name
      +'<div style="font-family:Pacifico,cursive;'+nameSty+';line-height:1.1;margin-bottom:.32rem;word-break:break-word;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">'+e(name)+'</div>'
      // Fields
      +frow2('Std',cls,'Div.',dv,fieldTc)
            +frow('Subject',sub+' '+cfg.icon,fieldTc)
      // School at bottom
      +'<div style="margin-top:auto;padding-top:.2rem">'
        +schoolLine(sch,fieldTc)
      +'</div>'
    +'</div>';
  }

  // ═══════════════════════════════════════════════════════════
  // TEMPLATE 1 — 🐦 Blue Sky & Birds  (Image 1 & 5 style)
  // Sky blue BG, white cloud wave panel right, big round photo left
  // ═══════════════════════════════════════════════════════════
  if(tpl===1){
    return '<div style="width:'+W+';height:220px;background:linear-gradient(145deg,#29b6f6,#4fc3f7,#b3e5fc);border-radius:16px;overflow:hidden;position:relative;font-family:DM Sans,sans-serif;box-shadow:0 6px 24px rgba(41,182,246,.35)">'
      // Polka dots on left
      +'<div style="position:absolute;top:12px;left:10px;width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,.35)"></div>'
      +'<div style="position:absolute;top:32px;left:22px;width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.25)"></div>'
      +'<div style="position:absolute;top:55px;left:8px;width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.3)"></div>'
      +'<div style="position:absolute;bottom:18px;left:14px;width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.28)"></div>'
      +'<div style="position:absolute;bottom:35px;left:28px;width:5px;height:5px;border-radius:50%;background:rgba(255,255,255,.22)"></div>'
      // Bird characters
      +'<div style="position:absolute;top:10px;left:45%;font-size:1.8rem;opacity:.55;transform:scaleX(-1)">🐦</div>'
      +'<div style="position:absolute;bottom:14px;right:8px;font-size:1.5rem;opacity:.5">🐦</div>'
      // White cloud wave panel (right 60%)
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:62%;background:#fff;border-radius:55% 0 0 50% / 50% 0 0 50%;"></div>'
      +clubHeader('rgba(0,105,148,.75)','#fff')
      // Big round photo — left side
      +'<div style="position:absolute;left:14px;top:calc(50% + 16px);transform:translateY(-50%);z-index:4">'
        +'<div style="width:130px;height:130px;border-radius:50%;overflow:hidden;border:5px solid #fff;box-shadow:0 4px 18px rgba(0,0,0,.2);background:#e3f2fd">'+photoEl+'</div>'
      +'</div>'
      // Right content area
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:58%;display:flex;flex-direction:column;justify-content:center;padding:2.0rem .9rem .5rem .5rem;z-index:5">'
        +'<div style="font-family:Pacifico,cursive;font-size:1.25rem;color:#0277bd;line-height:1.1;margin-bottom:.3rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+e(name)+'</div>'
        +frow2('Std',cls,'Div.',dv,'#1a237e')
                +frow('Subject',sub+' '+cfg.icon,'#1a237e')
        +frow('Phone',ph,'#1a237e')
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-top:.18rem">'
          +schoolLine(sch,'#0288d1')
          +'<div style="width:50px;height:50px;flex-shrink:0;border-radius:8px;overflow:hidden;background:#f0f0f0;border:1px solid #e0e0e0"><img src="'+qrSrc+'" width="50" height="50" style="display:block"></div>'
        +'</div>'
      +'</div>'
    +'</div>';
  }

  // ═══════════════════════════════════════════════════════════
  // TEMPLATE 2 — 🌿 Jungle Garden  (Image 3 style)
  // Full jungle scene BG, large organic-framed photo left
  // ═══════════════════════════════════════════════════════════
  if(tpl===2){
    return '<div style="width:'+W+';height:220px;background:linear-gradient(180deg,#87ceeb 0%,#b2ebf2 45%,#a5d6a7 65%,#66bb6a 82%,#388e3c 100%);border-radius:16px;overflow:hidden;position:relative;font-family:DM Sans,sans-serif;box-shadow:0 6px 24px rgba(56,142,60,.35)">'
      // Tree canopy top
      +'<div style="position:absolute;top:-5px;left:-10px;width:95px;height:65px;border-radius:50%;background:linear-gradient(135deg,#1b5e20,#2e7d32);opacity:.85"></div>'
      +'<div style="position:absolute;top:-8px;left:15px;width:70px;height:55px;border-radius:50%;background:linear-gradient(135deg,#2e7d32,#388e3c);opacity:.75"></div>'
      +'<div style="position:absolute;top:-3px;left:35px;width:55px;height:48px;border-radius:50%;background:#43a047;opacity:.65"></div>'
      +'<div style="position:absolute;top:-5px;right:-5px;width:75px;height:55px;border-radius:50%;background:linear-gradient(135deg,#1b5e20,#2e7d32);opacity:.8"></div>'
      +'<div style="position:absolute;top:-2px;right:15px;width:55px;height:42px;border-radius:50%;background:#388e3c;opacity:.7"></div>'
      // Honey hive right
      +'<div style="position:absolute;right:6px;top:24px;font-size:1.8rem;opacity:.65">🍯</div>'
      // Grass bottom
      +'<div style="position:absolute;bottom:0;left:0;right:0;height:30px;background:linear-gradient(180deg,#4caf50,#2e7d32);border-radius:55% 55% 0 0 / 60% 60% 0 0"></div>'
      // Small flowers
      +'<div style="position:absolute;bottom:6px;left:10px;font-size:.7rem;opacity:.7">🌸</div>'
      +'<div style="position:absolute;bottom:5px;left:30px;font-size:.65rem;opacity:.6">🌼</div>'
      +clubHeader('rgba(27,94,32,.75)','#fff')
      // Big organic photo frame left
      +'<div style="position:absolute;left:12px;top:calc(50% + 16px);transform:translateY(-50%);z-index:4">'
        +'<div style="width:115px;height:130px;border-radius:42% 58% 55% 45% / 48% 48% 52% 52%;overflow:hidden;border:5px solid #ff9800;box-shadow:0 4px 16px rgba(255,152,0,.4);background:#ffe0b2">'+photoEl+'</div>'
      +'</div>'
      // Right sky panel — white with slight opacity
      +'<div style="position:absolute;right:0;top:14px;bottom:32px;width:57%;background:rgba(255,255,255,.82);border-radius:14px 0 0 14px;z-index:3"></div>'
      // Right content
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:57%;display:flex;flex-direction:column;justify-content:center;padding:2.0rem .8rem .5rem .6rem;z-index:5">'
        +'<div style="font-family:Fredoka One,cursive;font-size:1.3rem;color:#1b5e20;line-height:1.1;margin-bottom:.3rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+e(name)+'</div>'
        +frow2('Std',cls,'Div.',dv,'#1b5e20')
                +frow('Subject',sub+' '+cfg.icon,'#1b5e20')
        +frow('Phone',ph,'#1b5e20')
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-top:.18rem">'
          +schoolLine(sch,'#2e7d32')
          +'<div style="width:50px;height:50px;flex-shrink:0;border-radius:8px;overflow:hidden;background:#fff;border:1.5px solid #a5d6a7"><img src="'+qrSrc+'" width="50" height="50" style="display:block"></div>'
        +'</div>'
      +'</div>'
    +'</div>';
  }

  // ═══════════════════════════════════════════════════════════
  // TEMPLATE 3 — 🚀 Space Adventure
  // Dark starry BG, round photo in planet ring, neon fields
  // ═══════════════════════════════════════════════════════════
  if(tpl===3){
    return '<div style="width:'+W+';height:220px;background:linear-gradient(150deg,#0a0015 0%,#1a0033 40%,#0d1b6b 80%,#1565c0 100%);border-radius:16px;overflow:hidden;position:relative;font-family:DM Sans,sans-serif;box-shadow:0 6px 28px rgba(21,101,192,.5)">'
      // Stars
      +'<div style="position:absolute;top:8px;left:40%;width:2px;height:2px;border-radius:50%;background:#fff;opacity:.8"></div>'
      +'<div style="position:absolute;top:15px;left:52%;width:3px;height:3px;border-radius:50%;background:#ffd54f;opacity:.9"></div>'
      +'<div style="position:absolute;top:5px;right:15%;width:2px;height:2px;border-radius:50%;background:#fff;opacity:.7"></div>'
      +'<div style="position:absolute;top:22px;left:60%;width:2px;height:2px;border-radius:50%;background:#fff;opacity:.6"></div>'
      +'<div style="position:absolute;bottom:30px;right:10%;width:2px;height:2px;border-radius:50%;background:#fff;opacity:.5"></div>'
      // Space characters
      +'<div style="position:absolute;right:8px;top:12px;font-size:1.8rem;opacity:.55;transform:rotate(-25deg)">🚀</div>'
      +'<div style="position:absolute;bottom:18px;right:12px;font-size:1.3rem;opacity:.45">🪐</div>'
      +'<div style="position:absolute;top:18px;left:38%;font-size:1rem;opacity:.4">✨</div>'
      +clubHeader('rgba(10,0,21,.8)','#e3f2fd')
      // Big photo with planet-ring effect
      +'<div style="position:absolute;left:12px;top:calc(50% + 16px);transform:translateY(-50%);z-index:4">'
        +'<div style="position:relative;width:130px;height:130px">'
          +'<div style="position:absolute;inset:-6px;border-radius:50%;border:3px solid rgba(100,181,246,.4);box-shadow:0 0 20px rgba(100,181,246,.25)"></div>'
          +'<div style="width:130px;height:130px;border-radius:50%;overflow:hidden;border:4px solid #90caf9;box-shadow:0 0 0 2px rgba(144,202,249,.2),0 4px 18px rgba(0,0,0,.5);background:#0d1b6b">'+photoEl+'</div>'
        +'</div>'
      +'</div>'
      // Right content
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:57%;display:flex;flex-direction:column;justify-content:center;padding:2.0rem .85rem .5rem .5rem;z-index:5">'
        +'<div style="font-family:Bebas Neue,cursive;font-size:1.4rem;letter-spacing:.1em;color:#e3f2fd;line-height:1.05;margin-bottom:.32rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 0 14px rgba(100,181,246,.4)">'+e(name)+'</div>'
        +frow2('Class',cls,'Div.',dv,'rgba(255,255,255,.75)')
        +frow('Roll No.',roll,'rgba(255,255,255,.7)')
        +frow('Subject',sub+' '+cfg.icon,'rgba(255,255,255,.7)')
        +frow('Phone',ph,'rgba(255,255,255,.65)')
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-top:.18rem">'
          +schoolLine(sch,'rgba(255,255,255,.65)')
          +'<div style="width:50px;height:50px;flex-shrink:0;border-radius:8px;overflow:hidden;background:rgba(255,255,255,.1);border:1px solid rgba(100,181,246,.4)"><img src="'+qrSrc+'" width="50" height="50" style="display:block;opacity:.85"></div>'
        +'</div>'
      +'</div>'
    +'</div>';
  }

  // ═══════════════════════════════════════════════════════════
  // TEMPLATE 4 — 🦋 Colorful Stationery  (Image 4 style)
  // White BG, colorful blobs corners, stationery icons, fancy photo frame
  // ═══════════════════════════════════════════════════════════
  if(tpl===4){
    return '<div style="width:'+W+';height:220px;background:#fff;border-radius:16px;overflow:hidden;position:relative;font-family:DM Sans,sans-serif;box-shadow:0 6px 22px rgba(0,0,0,.14)">'
      // Colorful blobs
      +'<div style="position:absolute;top:-15px;left:-15px;width:90px;height:80px;border-radius:50%;background:#4dd0e1;opacity:.5"></div>'
      +'<div style="position:absolute;top:-10px;right:-10px;width:70px;height:65px;border-radius:50%;background:#f48fb1;opacity:.45"></div>'
      +'<div style="position:absolute;bottom:-12px;left:8px;width:75px;height:65px;border-radius:50%;background:#aed581;opacity:.5"></div>'
      +'<div style="position:absolute;bottom:-8px;right:55px;width:55px;height:50px;border-radius:50%;background:#ffb74d;opacity:.45"></div>'
      // Stationery decoration
      +'<div style="position:absolute;top:6px;left:14px;font-size:1rem;opacity:.5;transform:rotate(-20deg)">✏️</div>'
      +'<div style="position:absolute;top:4px;left:40%;font-size:.9rem;opacity:.45;transform:rotate(15deg)">📏</div>'
      +'<div style="position:absolute;top:8px;right:8px;font-size:.85rem;opacity:.4">🖌️</div>'
      +'<div style="position:absolute;bottom:6px;right:55px;font-size:.8rem;opacity:.4">✂️</div>'
      +clubHeader('rgba(0,0,0,.07)','#333')
      // Fancy shaped photo frame (image 4 style — tooth/badge shape)
      +'<div style="position:absolute;left:14px;top:calc(50% + 16px);transform:translateY(-50%);z-index:4">'
        +'<div style="position:relative;width:118px;height:130px">'
          +'<div style="position:absolute;inset:0;border-radius:48% 52% 50% 50% / 42% 42% 58% 58%;border:5px solid #29b6f6;background:#e3f2fd;overflow:hidden;box-shadow:0 0 0 3px rgba(41,182,246,.25),0 4px 16px rgba(41,182,246,.25)">'+photoEl+'</div>'
          // Leaf decorations bottom
          +'<div style="position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);font-size:1.2rem;opacity:.8">🍃🍃</div>'
        +'</div>'
      +'</div>'
      // Right content
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:57%;display:flex;flex-direction:column;justify-content:center;padding:2.0rem .85rem .5rem .5rem;z-index:5">'
        +'<div style="font-family:Dancing Script,cursive;font-size:1.45rem;font-weight:700;color:#1565c0;line-height:1.1;margin-bottom:.32rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+e(name)+'</div>'
        +frow2('Class',cls,'Div.',dv,'#333')
                +frow('Subject',sub+' '+cfg.icon,'#333')
        +frow('Phone',ph,'#555')
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-top:.18rem">'
          +schoolLine(sch,'#555')
          +'<div style="width:50px;height:50px;flex-shrink:0;border-radius:8px;overflow:hidden;background:#f5f5f5;border:1.5px solid #e0e0e0"><img src="'+qrSrc+'" width="50" height="50" style="display:block"></div>'
        +'</div>'
      +'</div>'
    +'</div>';
  }

  // ═══════════════════════════════════════════════════════════
  // TEMPLATE 5 — 🌺 Kerala / Warm Saffron
  // Warm orange gradient wave, Playfair name, cultural feel
  // ═══════════════════════════════════════════════════════════
  if(tpl===5){
    return '<div style="width:'+W+';height:220px;background:linear-gradient(150deg,#ff8f00 0%,#ffa000 35%,#ffb300 60%,#fff8e1 100%);border-radius:16px;overflow:hidden;position:relative;font-family:DM Sans,sans-serif;box-shadow:0 6px 22px rgba(255,143,0,.35)">'
      // Dot decorations
      +'<div style="position:absolute;top:12px;left:12px;width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.4)"></div>'
      +'<div style="position:absolute;top:28px;left:24px;width:5px;height:5px;border-radius:50%;background:rgba(255,255,255,.3)"></div>'
      +'<div style="position:absolute;bottom:16px;left:10px;width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.35)"></div>'
      +'<div style="position:absolute;bottom:32px;left:25px;width:4px;height:4px;border-radius:50%;background:rgba(255,255,255,.28)"></div>'
      // Cultural decorations
      +'<div style="position:absolute;top:10px;left:42%;font-size:1.4rem;opacity:.5">🌺</div>'
      +'<div style="position:absolute;bottom:12px;right:10px;font-size:1.2rem;opacity:.45">🌸</div>'
      +'<div style="position:absolute;top:14px;right:10px;font-size:1rem;opacity:.4">🪔</div>'
      // White right panel (wave cut)
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:60%;background:#fff;border-radius:55% 0 0 50% / 50% 0 0 50%;"></div>'
      +clubHeader('rgba(191,54,12,.2)','#bf360c')
      // Big round photo on orange side
      +'<div style="position:absolute;left:12px;top:calc(50% + 16px);transform:translateY(-50%);z-index:4">'
        +'<div style="width:128px;height:128px;border-radius:50%;overflow:hidden;border:5px solid #fff;box-shadow:0 0 0 3px rgba(255,193,7,.4),0 4px 18px rgba(0,0,0,.25);background:#ffe0b2">'+photoEl+'</div>'
      +'</div>'
      // Right content
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:56%;display:flex;flex-direction:column;justify-content:center;padding:2.0rem .85rem .5rem .4rem;z-index:5">'
        +'<div style="font-family:Playfair Display,serif;font-size:1.25rem;font-weight:700;color:#bf360c;line-height:1.1;margin-bottom:.32rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+e(name)+'</div>'
        +frow2('Std',cls,'Div.',dv,'#bf360c')
                +frow('Subject',sub+' '+cfg.icon,'#bf360c')
        +frow('Phone',ph,'#bf360c')
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-top:.18rem">'
          +schoolLine(sch,'#e65100')
          +'<div style="width:50px;height:50px;flex-shrink:0;border-radius:8px;overflow:hidden;background:#fff;border:2px solid #ffb300"><img src="'+qrSrc+'" width="50" height="50" style="display:block"></div>'
        +'</div>'
      +'</div>'
    +'</div>';
  }

  // ═══════════════════════════════════════════════════════════
  // TEMPLATE 6 — 🎨 Art Splash
  // White BG, rainbow top stripe, colorful paint splashes, big heart-circle photo
  // ═══════════════════════════════════════════════════════════
  if(tpl===6){
    return '<div style="width:'+W+';height:220px;background:#fff;border-radius:16px;overflow:hidden;position:relative;font-family:DM Sans,sans-serif;border:3px solid #ff4081;box-shadow:0 6px 22px rgba(255,64,129,.25)">'
      // Rainbow stripe
      +'<div style="position:absolute;top:0;left:0;right:0;height:6px;background:linear-gradient(90deg,#f44336,#ff9800,#ffeb3b,#4caf50,#2196f3,#9c27b0)"></div>'
      // Paint splash blobs
      +'<div style="position:absolute;top:8px;left:-8px;width:65px;height:55px;border-radius:50% 60% 55% 65%;background:#f8bbd0;opacity:.65;transform:rotate(-15deg)"></div>'
      +'<div style="position:absolute;bottom:10px;left:-3px;width:50px;height:42px;border-radius:55% 50% 60% 45%;background:#c8e6c9;opacity:.6;transform:rotate(-8deg)"></div>'
      +'<div style="position:absolute;bottom:8px;right:52px;width:38px;height:32px;border-radius:50% 65% 50% 60%;background:#fff9c4;opacity:.7;transform:rotate(18deg)"></div>'
      // Art icons
      +'<div style="position:absolute;top:10px;left:38%;font-size:1.2rem;opacity:.5">🎨</div>'
      +'<div style="position:absolute;bottom:10px;right:8px;font-size:.9rem;opacity:.45">✏️</div>'
      +'<div style="position:absolute;top:10px;right:10px;font-size:.85rem;opacity:.4">🖌️</div>'
      +clubHeader('rgba(255,255,255,.9)','#880e4f')
      // Big round photo
      +'<div style="position:absolute;left:12px;top:calc(50% + 16px);transform:translateY(-50%);z-index:4">'
        +'<div style="width:126px;height:126px;border-radius:50%;overflow:hidden;border:5px solid #ff4081;box-shadow:0 0 0 3px rgba(255,64,129,.2),0 4px 16px rgba(255,64,129,.3);background:#fce4ec">'+photoEl+'</div>'
      +'</div>'
      // Right content
      +'<div style="position:absolute;right:0;top:0;bottom:0;width:57%;display:flex;flex-direction:column;justify-content:center;padding:2.0rem .85rem .5rem .4rem;z-index:5">'
        +'<div style="font-family:Nunito,sans-serif;font-size:1.35rem;font-weight:900;color:#e91e63;line-height:1.1;margin-bottom:.3rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+e(name)+'</div>'
        +frow2('Class',cls,'Div.',dv,'#880e4f')
                +frow('Subject',sub+' '+cfg.icon,'#880e4f')
        +frow('Phone',ph,'#880e4f')
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-top:.18rem">'
          +schoolLine(sch,'#e91e63')
          +'<div style="width:50px;height:50px;flex-shrink:0;border-radius:8px;overflow:hidden;background:#fff;border:2px solid #f48fb1"><img src="'+qrSrc+'" width="50" height="50" style="display:block"></div>'
        +'</div>'
      +'</div>'
    +'</div>';
  }

  return '';
}


// ── Color helper (lighten) ──
function adjustColor(hex,amt){
  try{
    var r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
    r=Math.min(255,r+amt); g=Math.min(255,g+amt); b=Math.min(255,b+amt);
    return '#'+r.toString(16).padStart(2,'0')+g.toString(16).padStart(2,'0')+b.toString(16).padStart(2,'0');
  }catch(x){return hex;}
}

// ══ PREVIEW ══════════════════════════════
function updatePreview(){
  var d=getFormData();
  var html=buildSlip(d,false,null);
  var el=document.getElementById('slipStage');
  if(el) el.innerHTML=html;
}
function buildAndRender(){ updatePreview(); }

// ══ SAVE ═════════════════════════════════
function doSave(){
  var d=getFormData();
  if(!d.name){toast('⚠️ Student name is required','err');return;}
  var fd=new FormData();
  fd.append('ax','save');
  fd.append('edit_id', v('f_edit_id'));
  fd.append('student_name', d.name);
  fd.append('school_name',  d.school);
  fd.append('class_grade',  d.cls);
  fd.append('division',     d.div);
  fd.append('contact_number', d.contact);
  fd.append('subject',      d.subj);
  fd.append('template_id',  d.tpl);
  if(d.photo) fd.append('photo_b64', d.photo);
  var btn=document.getElementById('saveBtn');
  btn.disabled=true; document.getElementById('saveTxt').textContent='Saving…';
  fetch(SELF,{method:'POST',body:fd})
    .then(function(r){return r.json();})
    .then(function(res){
      btn.disabled=false;
      document.getElementById('saveTxt').textContent=v('f_edit_id')?'Update Slip':'Save Slip';
      if(res.ok){toast(res.msg);setTimeout(function(){location.reload();},900);}
      else toast(res.msg,'err');
    })
    .catch(function(){btn.disabled=false;document.getElementById('saveTxt').textContent='Save Slip';toast('Network error','err');});
}

// ══ RESET ════════════════════════════════
function doReset(){
  ['f_name','f_school','f_class','f_div','f_contact']
    .forEach(function(id){var el=document.getElementById(id);if(el)el.value='';});
  document.getElementById('f_edit_id').value='';
  clearPhoto(); pickSubj('General'); pickTpl(1);
  document.getElementById('saveTxt').textContent='Save Slip';
  toast('Form cleared');
}

// ══ LOAD ═════════════════════════════════
function loadEdit(id){
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'load',id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok||!res.slip) return;
      var s=res.slip;
      set('f_name',s.student_name); set('f_school',s.school_name);
      set('f_class',s.class_grade); set('f_div',s.division);
      set('f_contact',s.contact_number);
      set('f_edit_id',s.id);
      if(s.photo_b64) setPhoto(s.photo_b64); else if(s.photo_url) setPhoto(s.photo_url); else clearPhoto();
      pickSubj(s.subject||'General');
      pickTpl(parseInt(s.template_id)||1);
      document.getElementById('saveTxt').textContent='Update Slip';
      showScr('form'); toast('Editing slip…');
    });
}
function loadPrev(id){
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'load',id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok||!res.slip) return;
      var s=res.slip;
      set('f_name',s.student_name); set('f_school',s.school_name);
      set('f_class',s.class_grade); set('f_div',s.division);
      set('f_contact',s.contact_number);
      ST.photo=s.photo_b64||s.photo_url||''; ST.subj=s.subject||'General'; ST.tpl=parseInt(s.template_id)||1;
      showScr('prev');
    });
}
function quickPrint(id){
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'load',id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok||!res.slip) return;
      var s=res.slip;
      set('f_name',s.student_name); set('f_school',s.school_name);
      set('f_class',s.class_grade); set('f_div',s.division);
      set('f_roll',s.roll_number);  set('f_parent',s.parent_name);
      ST.photo=s.photo_b64||s.photo_url||''; ST.subj=s.subject||'General'; ST.tpl=parseInt(s.template_id)||1;
      setTimeout(function(){ printSlip(1); },200);
    });
}
function set(id,v){var el=document.getElementById(id);if(el)el.value=v||'';}

// ══ DELETE ═══════════════════════════════
function delSlip(id,btn){
  if(!confirm('Delete this slip permanently?')) return;
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'del',id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(res.ok){btn.closest('.sc').remove();toast('Deleted');}
      else toast(res.msg||'Error','err');
    });
}

// ══ FILTER ═══════════════════════════════
var _flt='';
function setF(f){
  _flt=f;
  document.querySelectorAll('#fRow .lfc').forEach(function(c){c.classList.toggle('on',c.getAttribute('data-f')===f);});
  filterCards();
}
function filterCards(){
  var q=(document.getElementById('listQ').value||'').toLowerCase();
  document.querySelectorAll('#slipCards .sc').forEach(function(c){
    var nm=c.getAttribute('data-nm')||'', sj=c.getAttribute('data-sj')||'';
    c.style.display=((!q||nm.includes(q))&&(!_flt||sj===_flt))?'':'none';
  });
}

// ══ PRINT ════════════════════════════════
function getPrintCSS(){
  return '@import url("https://fonts.googleapis.com/css2?family=Pacifico&family=Fredoka+One&family=Nunito:wght@400;700;800;900&family=Bebas+Neue&family=DM+Sans:wght@400;700;800&display=swap");'
    +'*{box-sizing:border-box;margin:0;padding:0;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}'
    +'body{font-family:"DM Sans",sans-serif;background:#fff;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}'
    +'@media print{body{margin:0}*{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}';
}

function printSlip(count){
  var d=getFormData();
  var sw,all='',layout,pageCSS='';

  if(count===1){
    sw=760;
    var slipHtml=buildSlip(d,true,sw);
    all=slipHtml;
    pageCSS='@page{size:A4 portrait;margin:8mm}.slip-wrap{width:100%!important;min-height:270mm!important;height:auto!important}';
    layout='display:block;width:100%;min-height:100vh;padding:0;margin:0';
  } else if(count<=4){
    sw=360;
    var slipHtml=buildSlip(d,true,sw);
    for(var i=0;i<4;i++) all+=slipHtml;
    pageCSS='@page{size:A4 portrait;margin:8mm}.slip-wrap{height:130mm!important;overflow:hidden}';
    layout='display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:5mm;padding:0;margin:0;height:calc(297mm - 16mm);width:calc(210mm - 16mm)';
  } else {
    sw=340;
    var slipHtml=buildSlip(d,true,sw);
    for(var i=0;i<8;i++) all+=slipHtml;
    pageCSS='@page{size:A4 landscape;margin:6mm}.slip-wrap{height:95mm!important;overflow:hidden}';
    layout='display:grid;grid-template-columns:1fr 1fr 1fr 1fr;grid-template-rows:1fr 1fr;gap:4mm;padding:0;margin:0;height:calc(210mm - 12mm);width:calc(297mm - 12mm)';
  }
  var w=window.open('','_blank');
  w.document.write('<!DOCTYPE html><html><head><meta charset="UTF-8"><style>'+getPrintCSS()+pageCSS+'body{'+layout+'}</style></head><body>'+all+'</body></html>');
  w.document.close(); w.focus(); setTimeout(function(){w.print();},800);
}

// ══ IMAGE DOWNLOAD ════════════════════════
function downloadPNG(){
  if(typeof html2canvas==='undefined'){
    // Load html2canvas dynamically
    var sc=document.createElement('script');
    sc.src='https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
    sc.onload=function(){ doDownloadPNG(); };
    document.head.appendChild(sc);
  } else { doDownloadPNG(); }
}
function doDownloadPNG(){
  var el=document.getElementById('slipStage');
  if(!el||!el.children[0]){toast('Preview the slip first','err');return;}
  toast('Generating image…');
  html2canvas(el.children[0],{scale:3,useCORS:true,backgroundColor:null}).then(function(canvas){
    var a=document.createElement('a');
    a.href=canvas.toDataURL('image/png');
    a.download='nameslip_'+(v('f_name')||'student').replace(/\s+/g,'_')+'.png';
    a.click(); toast('✅ Image downloaded!');
  }).catch(function(err){ toast('Image error: '+err.message,'err'); });
}

// ══ CROP MODAL ════════════════════════════
var cropperInstance = null;

function openCropModal(imgSrc){
  var modal = document.getElementById('cropModal');
  var img   = document.getElementById('cropImg');
  // Destroy previous cropper if exists
  if(cropperInstance){ cropperInstance.destroy(); cropperInstance=null; }
  img.src = imgSrc;
  modal.classList.add('on');
  // Init Cropper.js after image loads
  img.onload = function(){
    cropperInstance = new Cropper(img, {
      aspectRatio: 1,          // default 1:1 (square)
      viewMode: 1,
      dragMode: 'move',
      autoCropArea: 0.85,
      restore: false,
      guides: true,
      center: true,
      highlight: false,
      cropBoxMovable: true,
      cropBoxResizable: true,
      toggleDragModeOnDblclick: false,
      background: true,
      responsive: true,
    });
  };
}

function closeCropModal(){
  if(cropperInstance){ cropperInstance.destroy(); cropperInstance=null; }
  document.getElementById('cropModal').classList.remove('on');
}

function applyCrop(){
  if(!cropperInstance){ closeCropModal(); return; }
  var canvas = cropperInstance.getCroppedCanvas({
    width:  600,
    height: 600,
    imageSmoothingEnabled: true,
    imageSmoothingQuality: 'high',
    fillColor: '#fff',
  });
  var b64 = canvas.toDataURL('image/jpeg', 0.92);
  closeCropModal();
  setPhoto(b64);
  toast('✅ Photo cropped!');
}

function setCropRatio(w, h, btn){
  document.querySelectorAll('.crop-ratio-btn').forEach(function(b){ b.classList.remove('on'); });
  btn.classList.add('on');
  if(cropperInstance){
    cropperInstance.setAspectRatio(isNaN(w) ? NaN : w/h);
  }
}

function cropRotate(deg){
  if(cropperInstance) cropperInstance.rotate(deg);
}

function cropFlip(){
  if(cropperInstance){
    var data = cropperInstance.getData();
    cropperInstance.scaleX(data.scaleX === -1 ? 1 : -1);
  }
}

// ══ CAMERA ═══════════════════════════════
function openCam(){
  document.getElementById('camModal').classList.add('on');
  startStream();
}
function startStream(){
  if(ST.cam){ST.cam.getTracks().forEach(function(t){t.stop()});ST.cam=null;}
  navigator.mediaDevices.getUserMedia({video:{facingMode:ST.facing},audio:false})
    .then(function(stream){
      ST.cam=stream;
      var vid=document.getElementById('camVid');
      vid.srcObject=stream; vid.play();
    })
    .catch(function(err){ toast('Camera: '+err.message,'err'); closeCam(); });
}
function flipCam(){ ST.facing=ST.facing==='user'?'environment':'user'; startStream(); }
function closeCam(){
  if(ST.cam){ST.cam.getTracks().forEach(function(t){t.stop()});ST.cam=null;}
  document.getElementById('camModal').classList.remove('on');
}
function shoot(){
  var v=document.getElementById('camVid'), c=document.getElementById('camCvs');
  c.width=v.videoWidth||640; c.height=v.videoHeight||480;
  c.getContext('2d').drawImage(v,0,0);
  var b64=c.toDataURL('image/jpeg',0.92);
  closeCam();
  // Open crop modal with captured photo
  setTimeout(function(){ openCropModal(b64); }, 200);
}

// ══ PRINT ALL VISIBLE SLIPS ══════════════
// Loads all currently visible slip cards and prints them on one sheet
function printAllVisible(){
  var cards = [];
  document.querySelectorAll('#slipCards .sc').forEach(function(c){
    if(c.style.display!=='none') cards.push(c.getAttribute('data-id'));
  });
  if(!cards.length){ toast('No slips visible to print','err'); return; }
  toast('Loading '+cards.length+' slips…');

  var loaded = 0, slipHTMLs = new Array(cards.length);

  function tryPrint(){
    if(loaded < cards.length) return;
    // determine columns: 1=1col, 2-4=2col, 5+=3col
    var cols = cards.length===1?1:cards.length<=4?2:cards.length<=9?3:4;
    var sw   = cols===1?340:cols===2?270:cols===3?220:190;
    var grid = 'display:grid;grid-template-columns:repeat('+cols+',1fr);gap:10px;padding:12px;align-items:start;';
    var all  = slipHTMLs.join('');
    var win  = window.open('','_blank');
    win.document.write('<!DOCTYPE html><html><head><meta charset="UTF-8">'+
      '<link href="https://fonts.googleapis.com/css2?family=Pacifico&family=Fredoka+One&family=Nunito:wght@400;700;800;900&family=Dancing+Script:wght@700&family=Bebas+Neue&family=DM+Sans:wght@400;700;800&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">'+
      '<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:"DM Sans",sans-serif;'+grid+'}'+
      '@media print{body{margin:0}@page{margin:6mm}}</style></head><body>'+all+'</body></html>');
    win.document.close(); win.focus();
    setTimeout(function(){ win.print(); }, 900);
  }

  cards.forEach(function(id, idx){
    fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'load',id:id})})
      .then(function(r){return r.json();})
      .then(function(res){
        if(res.ok && res.slip){
          var s=res.slip;
          // Rebuild form-like data object from slip
          var d={
            name:s.student_name, school:s.school_name,
            cls:s.class_grade,   div:s.division,
            contact:s.contact_number,
            subj:s.subject||'General', tpl:parseInt(s.template_id)||1,
            photo:s.photo_b64||s.photo_url||'',
            px:50, py:50
          };
          slipHTMLs[idx] = buildSlip(d, true, null);
        } else {
          slipHTMLs[idx] = '';
        }
        loaded++;
        tryPrint();
      })
      .catch(function(){ slipHTMLs[idx]=''; loaded++; tryPrint(); });
  });
}

// ══ BULK ═════════════════════════════════
function doBulk(inp){
  var fd=new FormData(); fd.append('ax','bulk'); fd.append('f',inp.files[0]);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    var el=document.getElementById('bulkMsg'); el.style.display='block';
    if(res.ok){el.style.cssText='display:block;padding:.75rem;border-radius:10px;font-size:.84rem;font-weight:700;background:#e8f5e9;color:#1b5e20;border:1px solid #a5d6a7';el.textContent=res.msg;setTimeout(function(){location.reload();},1200);}
    else{el.style.cssText='display:block;padding:.75rem;border-radius:10px;font-size:.84rem;font-weight:700;background:#ffebee;color:#c62828;border:1px solid #ffcdd2';el.textContent=res.msg;}
  });
}
function dlCSVTpl(){
  var c='Name,School,Class,Division,Parent Name,Contact Number,Subject\n'+
        'Fathima Zahra,Govt. High School Vettikkattiri,7th,A,Ibrahim PK,+919876543210,Arabic\n'+
        'Arjun Nair,St. Marys High School,10th,B,Rajesh Nair,+919876543211,Mathematics\n'+
        'Pihu Sharma,Delhi Public School,5th,C,Rahul Sharma,+919876543212,English\n';
  var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([c],{type:'text/csv'}));
  a.download='nameslip_template.csv';a.click();
}

// ══ INIT ═════════════════════════════════
document.addEventListener('DOMContentLoaded',function(){
  pickSubj('General'); pickTpl(1); updatePreview();

  // Drag-drop photo file on drop zone
  var dz=document.getElementById('pDrop');
  dz.addEventListener('dragover',function(e){e.preventDefault();dz.style.borderColor='#1565c0';});
  dz.addEventListener('dragleave',function(){dz.style.borderColor='';});
  dz.addEventListener('drop',function(e){
    e.preventDefault(); dz.style.borderColor='';
    var file=e.dataTransfer.files[0];
    if(file&&file.type.startsWith('image/')){
      var r=new FileReader(); r.onload=function(ev){openCropModal(ev.target.result);}; r.readAsDataURL(file);
    }
  });
});
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
