<?php
// ============================================================
// modules/creative_studio.php — Creative Studio v2
// AI Sticker · Troll · Meme · Poster · GIF Creator
// Aishwarya Arts & Sports Club — PHP 7.3+ compatible
// v2 — Native app-shell UI + GIF, comments, follow, history
// BUILD: CS-2
// ============================================================
require_once __DIR__ . '/../includes/config.php';
@date_default_timezone_set('Asia/Kolkata');

$pageOG = [
  'title' => '🎨 Creative Studio — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club'),
  'desc'  => 'Make stickers, GIFs, memes & posters. Create, share & follow creators in the club.',
  'image' => rtrim(defined('SITE_URL')?SITE_URL:'https://mynamecc.online','/').'/og_image.php',
  'url'   => rtrim(defined('SITE_URL')?SITE_URL:'https://mynamecc.online','/').'/modules/creative_studio.php',
];
requireLogin();
$me      = currentUser();
$uid     = (int)$me['id'];
$isAdmin = isAdminRole($me['role']) || isModuleAdmin('creative_studio', $me);
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$LOGO    = getLogoB64();
$pageTitle = '🎨 Creative Studio — '.$CLUB;

// ── DB Setup ─────────────────────────────────────────────────
foreach ([
"CREATE TABLE IF NOT EXISTS cs_designs (
  id INT AUTO_INCREMENT PRIMARY KEY, member_id INT NOT NULL,
  title VARCHAR(160) DEFAULT 'Untitled', category VARCHAR(60) DEFAULT 'General', kind VARCHAR(30) DEFAULT 'sticker',
  canvas_json LONGTEXT, thumb MEDIUMTEXT, width INT DEFAULT 1080, height INT DEFAULT 1080,
  is_public TINYINT(1) DEFAULT 0, likes INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(member_id), INDEX(is_public)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
"CREATE TABLE IF NOT EXISTS cs_likes (design_id INT NOT NULL, member_id INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY uniq_like (design_id, member_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
"CREATE TABLE IF NOT EXISTS cs_comments (id INT AUTO_INCREMENT PRIMARY KEY, design_id INT NOT NULL, member_id INT NOT NULL,
  body VARCHAR(500) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX(design_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
"CREATE TABLE IF NOT EXISTS cs_follows (follower_id INT NOT NULL, author_id INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY uniq_f (follower_id, author_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
"CREATE TABLE IF NOT EXISTS cs_downloads (id INT AUTO_INCREMENT PRIMARY KEY, member_id INT NOT NULL, design_id INT DEFAULT NULL,
  title VARCHAR(160) DEFAULT '', fmt VARCHAR(12) DEFAULT 'png', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX(member_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
] as $sql) { try { db()->exec($sql); } catch (Exception $e) {} }

// ── AJAX action router ───────────────────────────────────────
$ax = array_merge($_GET, $_POST);
if (!empty($ax['action'])) {
  header('Content-Type: application/json');
  $act = trim($ax['action']);
  $writes = ['save','delete','visibility','like','comment_add','follow_toggle','log_download'];
  if (in_array($act, $writes, true) && !verifyCsrf()) { echo json_encode(['ok'=>false,'msg'=>'Bad token, refresh']); exit; }
  try {
    if ($act === 'save') {
      $id=(int)($ax['id']??0); $title=mb_substr(trim($ax['title']??'Untitled'),0,160); if($title==='')$title='Untitled';
      $cat=mb_substr(trim($ax['category']??'General'),0,60); $kind=mb_substr(trim($ax['kind']??'sticker'),0,30);
      $json=(string)($ax['canvas_json']??''); $thumb=(string)($ax['thumb']??'');
      $w=max(1,(int)($ax['width']??1080)); $hh=max(1,(int)($ax['height']??1080)); $pub=!empty($ax['is_public'])?1:0;
      if (strlen($json)>14000000){ echo json_encode(['ok'=>false,'msg'=>'Design too large']); exit; }
      if ($id>0){
        $o=db()->prepare("SELECT member_id FROM cs_designs WHERE id=?"); $o->execute([$id]); $r=$o->fetch();
        if(!$r||(int)$r['member_id']!==$uid){ echo json_encode(['ok'=>false,'msg'=>'Not your design']); exit; }
        db()->prepare("UPDATE cs_designs SET title=?,category=?,kind=?,canvas_json=?,thumb=?,width=?,height=?,is_public=? WHERE id=? AND member_id=?")
          ->execute([$title,$cat,$kind,$json,$thumb,$w,$hh,$pub,$id,$uid]);
        echo json_encode(['ok'=>true,'id'=>$id]); exit;
      } else {
        db()->prepare("INSERT INTO cs_designs (member_id,title,category,kind,canvas_json,thumb,width,height,is_public) VALUES (?,?,?,?,?,?,?,?,?)")
          ->execute([$uid,$title,$cat,$kind,$json,$thumb,$w,$hh,$pub]);
        echo json_encode(['ok'=>true,'id'=>(int)db()->lastInsertId()]); exit;
      }
    }
    if ($act === 'mine') {
      $s=db()->prepare("SELECT id,title,category,kind,thumb,is_public,likes,width,height,updated_at FROM cs_designs WHERE member_id=? ORDER BY updated_at DESC LIMIT 200");
      $s->execute([$uid]); echo json_encode(['ok'=>true,'rows'=>$s->fetchAll()]); exit;
    }
    if ($act === 'explore' || $act === 'following') {
      $follow = ($act==='following');
      $sql="SELECT d.id,d.title,d.category,d.kind,d.thumb,d.likes,d.member_id,u.name AS author,u.profile_photo AS photo,
            (SELECT COUNT(*) FROM cs_likes l WHERE l.design_id=d.id AND l.member_id=?) liked,
            (SELECT COUNT(*) FROM cs_comments c WHERE c.design_id=d.id) comments
            FROM cs_designs d JOIN users u ON u.id=d.member_id WHERE d.is_public=1 ";
      $params=[$uid];
      if($follow){ $sql.="AND d.member_id IN (SELECT author_id FROM cs_follows WHERE follower_id=?) "; $params[]=$uid; }
      $sql.="ORDER BY d.created_at DESC LIMIT 80";
      $s=db()->prepare($sql); $s->execute($params); echo json_encode(['ok'=>true,'rows'=>$s->fetchAll()]); exit;
    }
    if ($act === 'load' || $act === 'detail') {
      $id=(int)($ax['id']??0);
      $s=db()->prepare("SELECT d.*,u.name AS author,u.profile_photo AS photo FROM cs_designs d JOIN users u ON u.id=d.member_id WHERE d.id=?");
      $s->execute([$id]); $row=$s->fetch();
      if(!$row){ echo json_encode(['ok'=>false,'msg'=>'Not found']); exit; }
      if((int)$row['member_id']!==$uid && (int)$row['is_public']!==1){ echo json_encode(['ok'=>false,'msg'=>'Private design']); exit; }
      $row['mine']=((int)$row['member_id']===$uid)?1:0;
      $lk=db()->prepare("SELECT COUNT(*) c FROM cs_likes WHERE design_id=? AND member_id=?"); $lk->execute([$id,$uid]); $row['liked']=(int)$lk->fetch()['c'];
      $fl=db()->prepare("SELECT COUNT(*) c FROM cs_follows WHERE follower_id=? AND author_id=?"); $fl->execute([$uid,(int)$row['member_id']]); $row['following']=(int)$fl->fetch()['c'];
      if($act==='load'){ unset($row['thumb']); }
      echo json_encode(['ok'=>true,'design'=>$row]); exit;
    }
    if ($act === 'comments') {
      $id=(int)($ax['id']??0);
      $s=db()->prepare("SELECT c.id,c.body,c.created_at,u.name AS author FROM cs_comments c JOIN users u ON u.id=c.member_id WHERE c.design_id=? ORDER BY c.id DESC LIMIT 100");
      $s->execute([$id]); echo json_encode(['ok'=>true,'rows'=>$s->fetchAll()]); exit;
    }
    if ($act === 'comment_add') {
      $id=(int)($ax['id']??0); $body=mb_substr(trim($ax['body']??''),0,500);
      if($body===''){ echo json_encode(['ok'=>false,'msg'=>'Empty']); exit; }
      db()->prepare("INSERT INTO cs_comments (design_id,member_id,body) VALUES (?,?,?)")->execute([$id,$uid,$body]);
      echo json_encode(['ok'=>true]); exit;
    }
    if ($act === 'follow_toggle') {
      $author=(int)($ax['author_id']??0);
      if($author===$uid){ echo json_encode(['ok'=>false,'msg'=>'Cannot follow yourself']); exit; }
      $c=db()->prepare("SELECT 1 FROM cs_follows WHERE follower_id=? AND author_id=?"); $c->execute([$uid,$author]);
      if($c->fetch()){ db()->prepare("DELETE FROM cs_follows WHERE follower_id=? AND author_id=?")->execute([$uid,$author]); $f=0; }
      else { db()->prepare("INSERT IGNORE INTO cs_follows (follower_id,author_id) VALUES (?,?)")->execute([$uid,$author]); $f=1; }
      echo json_encode(['ok'=>true,'following'=>$f]); exit;
    }
    if ($act === 'delete') {
      $id=(int)($ax['id']??0);
      db()->prepare("DELETE FROM cs_designs WHERE id=? AND member_id=?")->execute([$id,$uid]);
      db()->prepare("DELETE FROM cs_likes WHERE design_id=?")->execute([$id]);
      db()->prepare("DELETE FROM cs_comments WHERE design_id=?")->execute([$id]);
      echo json_encode(['ok'=>true]); exit;
    }
    if ($act === 'visibility') {
      $id=(int)($ax['id']??0); $pub=!empty($ax['is_public'])?1:0;
      db()->prepare("UPDATE cs_designs SET is_public=? WHERE id=? AND member_id=?")->execute([$pub,$id,$uid]);
      echo json_encode(['ok'=>true,'is_public'=>$pub]); exit;
    }
    if ($act === 'like') {
      $id=(int)($ax['id']??0);
      $c=db()->prepare("SELECT 1 FROM cs_likes WHERE design_id=? AND member_id=?"); $c->execute([$id,$uid]);
      if($c->fetch()){ db()->prepare("DELETE FROM cs_likes WHERE design_id=? AND member_id=?")->execute([$id,$uid]); $liked=0; }
      else { db()->prepare("INSERT IGNORE INTO cs_likes (design_id,member_id) VALUES (?,?)")->execute([$id,$uid]); $liked=1; }
      $cnt=db()->prepare("SELECT COUNT(*) c FROM cs_likes WHERE design_id=?"); $cnt->execute([$id]); $cc=(int)$cnt->fetch()['c'];
      db()->prepare("UPDATE cs_designs SET likes=? WHERE id=?")->execute([$cc,$id]);
      echo json_encode(['ok'=>true,'liked'=>$liked,'likes'=>$cc]); exit;
    }
    if ($act === 'log_download') {
      $id=(int)($ax['id']??0)?:null; $title=mb_substr(trim($ax['title']??''),0,160); $fmt=mb_substr(trim($ax['fmt']??'png'),0,12);
      db()->prepare("INSERT INTO cs_downloads (member_id,design_id,title,fmt) VALUES (?,?,?,?)")->execute([$uid,$id,$title,$fmt]);
      echo json_encode(['ok'=>true]); exit;
    }
    if ($act === 'downloads') {
      $s=db()->prepare("SELECT title,fmt,created_at FROM cs_downloads WHERE member_id=? ORDER BY id DESC LIMIT 60");
      $s->execute([$uid]); echo json_encode(['ok'=>true,'rows'=>$s->fetchAll()]); exit;
    }
    echo json_encode(['ok'=>false,'msg'=>'Unknown action']); exit;
  } catch (Exception $e) { echo json_encode(['ok'=>false,'msg'=>'Server error']); exit; }
}

require_once __DIR__ . '/../includes/header.php';
?>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Bebas+Neue&family=Sora:wght@400;600;700;800;900&family=Baloo+Chettan+2:wght@500;700;800&family=Anek+Malayalam:wght@500;700;800&family=Noto+Sans+Malayalam:wght@500;700&display=swap" rel="stylesheet">
<style>
/* immersive app: hide site chrome */
body.cs-app{padding-bottom:0!important;overflow:hidden}
body.cs-app .navbar,body.cs-app #bnav,body.cs-app footer{display:none!important}
:root{--cs-bg:#070b16;--cs-panel:#0f1830;--cs-panel2:#16213d;--cs-line:rgba(255,255,255,.09);--cs-gold:#ffd34d;--cs-teal:#1fd6b5;--cs-txt:#eaf0ff;--cs-mut:rgba(234,240,255,.55)}
.cs-app-shell{position:fixed;inset:0;z-index:60;display:flex;flex-direction:column;background:var(--cs-bg);color:var(--cs-txt);font-family:'Sora',system-ui,sans-serif}
/* top bar */
.cs-appbar{flex:0 0 auto;display:flex;align-items:center;gap:.5rem;padding:.55rem .7rem;padding-top:calc(.55rem + env(safe-area-inset-top,0px));background:linear-gradient(180deg,#0c1428,#0a1020);border-bottom:1px solid var(--cs-line)}
.cs-appbar .bk{background:rgba(255,255,255,.08);border:none;color:#fff;width:34px;height:34px;border-radius:10px;font-size:1.1rem;cursor:pointer}
.cs-appbar h1{font-family:'Bebas Neue',sans-serif;font-size:1.12rem;letter-spacing:.07em;margin:0;color:#fff;flex:1}
.cs-appbar .ab{background:rgba(255,255,255,.08);border:none;color:#fff;height:34px;padding:0 .7rem;border-radius:10px;font-weight:800;font-size:.78rem;cursor:pointer;display:inline-flex;align-items:center;gap:.3rem}
.cs-appbar .ab.g{background:linear-gradient(135deg,#ffd34d,#e6a800);color:#1a1300}
/* main */
.cs-main{flex:1 1 auto;position:relative;overflow:hidden}
.cs-screen{position:absolute;inset:0;overflow-y:auto;-webkit-overflow-scrolling:touch;opacity:0;transform:translateX(12px);pointer-events:none;transition:opacity .22s,transform .22s}
.cs-screen.on{opacity:1;transform:none;pointer-events:auto}
.cs-screen.edit{display:flex;flex-direction:column;overflow:hidden}
/* bottom tabs */
.cs-tabbar{flex:0 0 auto;display:flex;background:rgba(10,16,32,.96);backdrop-filter:blur(12px);border-top:1px solid var(--cs-line);padding-bottom:env(safe-area-inset-bottom,0px)}
.cs-tabbar button{flex:1;background:none;border:none;color:var(--cs-mut);padding:.45rem .2rem .5rem;font-size:.6rem;font-weight:700;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:.15rem}
.cs-tabbar button .ic{font-size:1.2rem}
.cs-tabbar button.on{color:var(--cs-gold)}
.cs-tabbar .fab{position:relative}
.cs-tabbar .fab .ic{background:linear-gradient(135deg,#ffd34d,#e6a800);color:#1a1300;width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-top:-16px;box-shadow:0 6px 18px rgba(255,211,77,.4);font-size:1.5rem}
/* editor */
.cs-stage{flex:1 1 auto;display:flex;align-items:center;justify-content:center;background:repeating-conic-gradient(#10182e 0 25%,#0b1124 0 50%) 50%/26px 26px;padding:10px;overflow:auto}
#csCanvasWrap{box-shadow:0 10px 40px rgba(0,0,0,.5);max-width:100%}
#csObjBar{display:none;gap:.35rem;flex-wrap:wrap;padding:.45rem .6rem;background:var(--cs-panel2);border-top:1px solid var(--cs-line);flex:0 0 auto}
#csObjBar .mini{background:rgba(255,255,255,.07);border:1px solid var(--cs-line);color:#fff;border-radius:8px;padding:.4rem .55rem;font-size:.85rem;cursor:pointer}
.cs-toolbar{flex:0 0 auto;display:flex;gap:.4rem;overflow-x:auto;padding:.55rem;background:var(--cs-panel);border-top:1px solid var(--cs-line);-webkit-overflow-scrolling:touch}
.cs-tool{flex:0 0 auto;width:62px;background:var(--cs-panel2);border:1px solid var(--cs-line);border-radius:12px;padding:.5rem .2rem;color:var(--cs-txt);cursor:pointer;text-align:center;font-size:.58rem;font-weight:700}
.cs-tool .ic{font-size:1.2rem;display:block;margin-bottom:.12rem}
.cs-tool:active{transform:scale(.93)}
/* buttons */
.cs-btn{border:none;border-radius:10px;padding:.5rem .8rem;font-family:'Sora',sans-serif;font-weight:800;font-size:.78rem;cursor:pointer;display:inline-flex;align-items:center;gap:.3rem}
.cs-btn.g{background:linear-gradient(135deg,#ffd34d,#e6a800);color:#1a1300}
.cs-btn.t{background:linear-gradient(135deg,#1fd6b5,#0e9e86);color:#022}
.cs-btn.w{background:linear-gradient(135deg,#25d366,#128c7e);color:#fff}
.cs-btn.d{background:rgba(255,255,255,.08);color:#fff;border:1px solid var(--cs-line)}
.cs-btn.danger{background:rgba(255,70,90,.15);color:#ff8a98;border:1px solid rgba(255,70,90,.3)}
/* sheets */
.cs-sheet{position:fixed;left:0;right:0;bottom:0;z-index:80;background:var(--cs-panel);border-top:2px solid var(--cs-gold);border-radius:20px 20px 0 0;padding:.5rem 1rem 1.5rem;transform:translateY(110%);transition:transform .26s cubic-bezier(.2,.8,.2,1);max-height:80vh;overflow:auto;max-width:1100px;margin:0 auto}
.cs-sheet.on{transform:translateY(0)}
.cs-sheet .grab{width:42px;height:5px;border-radius:3px;background:rgba(255,255,255,.25);margin:.2rem auto .7rem}
.cs-sheet h3{margin:.1rem 0 .7rem;font-size:.95rem;display:flex;align-items:center;gap:.4rem}
.cs-sheet h3 .x{margin-left:auto;background:rgba(255,255,255,.08);border:none;color:#fff;width:30px;height:30px;border-radius:50%;font-size:1rem;cursor:pointer}
.cs-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:75;display:none}
.cs-backdrop.on{display:block}
.cs-row{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center}
.cs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(70px,1fr));gap:.45rem}
.cs-chip{background:var(--cs-panel2);border:1px solid var(--cs-line);border-radius:10px;padding:.55rem;text-align:center;cursor:pointer;font-size:.72rem;font-weight:700}
.cs-emoji{font-size:1.6rem;background:var(--cs-panel2);border:1px solid var(--cs-line);border-radius:10px;padding:.35rem;cursor:pointer;text-align:center}
.cs-field{display:flex;flex-direction:column;gap:.2rem;font-size:.72rem;color:var(--cs-mut)}
.cs-field input,.cs-field select,.cs-input{background:var(--cs-panel2);border:1px solid var(--cs-line);color:#fff;border-radius:8px;padding:.5rem;font-family:'Sora',sans-serif}
.cs-color{width:38px;height:34px;border-radius:8px;border:1px solid var(--cs-line);padding:0;background:none}
input[type=range]{accent-color:var(--cs-gold)}
/* gallery */
.cs-gal{display:grid;grid-template-columns:repeat(2,1fr);gap:.7rem;padding:.8rem .7rem 1.4rem}
@media(min-width:620px){.cs-gal{grid-template-columns:repeat(3,1fr)}}
.cs-card{background:var(--cs-panel);border:1px solid var(--cs-line);border-radius:14px;overflow:hidden}
.cs-card .thumb{width:100%;aspect-ratio:1;object-fit:contain;background:#0b1124;display:block;cursor:pointer}
.cs-card .meta{padding:.5rem .6rem}.cs-card .meta b{font-size:.8rem;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cs-card .meta small{color:var(--cs-mut);font-size:.66rem}
.cs-card .acts{display:flex;gap:.3rem;padding:0 .6rem .6rem;flex-wrap:wrap}
.cs-card .acts button{flex:1;font-size:.66rem;padding:.4rem;border-radius:8px;border:1px solid var(--cs-line);background:rgba(255,255,255,.06);color:#fff;cursor:pointer;font-weight:700}
.cs-seg{display:flex;gap:.3rem;padding:.7rem .7rem 0}
.cs-seg button{flex:1;padding:.5rem;border-radius:10px;border:1px solid var(--cs-line);background:var(--cs-panel);color:var(--cs-mut);font-weight:800;font-size:.76rem;cursor:pointer}
.cs-seg button.on{background:linear-gradient(135deg,#ffd34d,#e6a800);color:#1a1300;border-color:transparent}
.cs-note{font-size:.72rem;color:var(--cs-mut);line-height:1.5;background:var(--cs-panel2);border:1px dashed var(--cs-line);border-radius:10px;padding:.6rem .7rem}
.cs-empty{text-align:center;color:var(--cs-mut);padding:2.4rem 1rem;font-size:.85rem}
.cs-toast{position:fixed;bottom:90px;left:50%;transform:translateX(-50%);background:#10182e;color:#fff;border:1px solid var(--cs-gold);padding:.6rem 1rem;border-radius:30px;font-size:.8rem;font-weight:700;z-index:200;opacity:0;transition:opacity .25s;pointer-events:none;max-width:90%;text-align:center}
.cs-toast.on{opacity:1}
/* detail overlay */
#csDetail{position:fixed;inset:0;z-index:90;background:var(--cs-bg);display:none;flex-direction:column}
#csDetail.on{display:flex}
#csDetail .dhead{display:flex;align-items:center;gap:.5rem;padding:.6rem .7rem;padding-top:calc(.6rem + env(safe-area-inset-top,0px));border-bottom:1px solid var(--cs-line)}
#csDetail .dbody{flex:1;overflow-y:auto;padding:.8rem}
#csDetail img.big{width:100%;border-radius:14px;background:#0b1124;display:block;margin-bottom:.8rem}
.cs-cmt{background:var(--cs-panel);border:1px solid var(--cs-line);border-radius:10px;padding:.5rem .65rem;margin-bottom:.4rem}
.cs-cmt b{font-size:.74rem;color:var(--cs-gold)}.cs-cmt p{margin:.15rem 0 0;font-size:.82rem}
.cs-spin{width:26px;height:26px;border:3px solid rgba(255,255,255,.2);border-top-color:var(--cs-gold);border-radius:50%;animation:csspin .8s linear infinite;margin:1.6rem auto}
@keyframes csspin{to{transform:rotate(360deg)}}
.malayalam{font-family:'Anek Malayalam','Noto Sans Malayalam',sans-serif}
</style>

<div class="cs-app-shell" id="csShell">
  <div class="cs-appbar">
    <button class="bk" onclick="csExit()" title="Back to club">‹</button>
    <h1 id="csAppTitle">Creative Studio</h1>
    <button class="ab" onclick="csOpenSheet('sheetExport')">⬇️</button>
    <button class="ab g" onclick="csOpenSave()">💾 Save</button>
  </div>

  <div class="cs-main">
    <!-- EDITOR -->
    <div class="cs-screen edit on" id="scr-editor">
      <div class="cs-stage"><div id="csCanvasWrap"><canvas id="csCanvas"></canvas></div></div>
      <div id="csObjBar">
        <button class="mini" onclick="csObj('front')">⬆️</button>
        <button class="mini" onclick="csObj('back')">⬇️</button>
        <button class="mini" onclick="csObj('dup')">⧉</button>
        <button class="mini" onclick="csObj('center')">⊕</button>
        <button class="mini" onclick="csObj('flip')">↔️</button>
        <input type="color" class="cs-color" id="csObjColor" onchange="csObjColorChange(this.value)">
        <button class="mini" id="csBgRmBtn" onclick="csOpenSheet('sheetBg')" style="display:none">✂️</button>
        <button class="mini danger" onclick="csObj('del')">🗑️</button>
      </div>
      <div class="cs-toolbar">
        <button class="cs-tool" onclick="csOpenSheet('sheetSize')"><span class="ic">📐</span>Size</button>
        <button class="cs-tool" onclick="csAddText()"><span class="ic">🅣</span>Text</button>
        <button class="cs-tool" onclick="csOpenSheet('sheetEmoji')"><span class="ic">😀</span>Sticker</button>
        <button class="cs-tool" onclick="document.getElementById('csImgInput').click()"><span class="ic">🖼️</span>Image</button>
        <button class="cs-tool" onclick="csOpenSheet('sheetShape')"><span class="ic">⬛</span>Shape</button>
        <button class="cs-tool" onclick="csOpenSheet('sheetBubble')"><span class="ic">💬</span>Bubble</button>
        <button class="cs-tool" onclick="csAddLogo()"><span class="ic">🏆</span>Logo</button>
        <button class="cs-tool" onclick="csOpenSheet('sheetQR')"><span class="ic">🔳</span>QR</button>
        <button class="cs-tool" onclick="csOpenSheet('sheetCanvasBg')"><span class="ic">🎨</span>BG</button>
        <button class="cs-tool" onclick="csOpenSheet('sheetGif')"><span class="ic">🎞️</span>GIF</button>
        <button class="cs-tool" onclick="csOpenSheet('sheetAI')"><span class="ic">✨</span>AI</button>
      </div>
      <input type="file" id="csImgInput" accept="image/*" style="display:none" onchange="csAddImageFile(this.files[0])">
    </div>

    <!-- TEMPLATES -->
    <div class="cs-screen" id="scr-templates">
      <div class="cs-row" id="csTplCats" style="padding:.7rem .7rem 0"></div>
      <div class="cs-gal" id="csTplGrid" style="grid-template-columns:repeat(2,1fr)"></div>
    </div>

    <!-- EXPLORE -->
    <div class="cs-screen" id="scr-explore">
      <div class="cs-seg"><button class="on" id="segAll" onclick="csExploreMode('explore',this)">🌍 All</button><button id="segFollow" onclick="csExploreMode('following',this)">👥 Following</button></div>
      <div id="csExplore" class="cs-gal"></div>
    </div>

    <!-- MINE -->
    <div class="cs-screen" id="scr-mine"><div id="csMine" class="cs-gal"></div></div>

    <!-- ME / PROFILE -->
    <div class="cs-screen" id="scr-me">
      <div style="padding:1rem .9rem">
        <div style="display:flex;align-items:center;gap:.7rem;margin-bottom:1rem">
          <div style="width:54px;height:54px;border-radius:50%;background:linear-gradient(135deg,#ffd34d,#e6a800);display:flex;align-items:center;justify-content:center;font-size:1.5rem">🎨</div>
          <div><b style="font-size:1rem"><?= h($me['name'] ?? 'Member') ?></b><br><small style="color:var(--cs-mut)">Creative Studio</small></div>
        </div>
        <h3 style="font-size:.85rem;margin:.4rem 0">⬇️ Download history</h3>
        <div id="csHistory"></div>
      </div>
    </div>
  </div>

  <div class="cs-tabbar">
    <button class="on" data-scr="editor" onclick="csTab('editor',this)"><span class="ic">🖌️</span>Editor</button>
    <button data-scr="templates" onclick="csTab('templates',this)"><span class="ic">🧩</span>Templates</button>
    <button class="fab" data-scr="editor" onclick="csNew();csTab('editor',null,'editor')"><span class="ic">＋</span></button>
    <button data-scr="explore" onclick="csTab('explore',this)"><span class="ic">🌍</span>Explore</button>
    <button data-scr="mine" onclick="csTab('mine',this)"><span class="ic">🗂️</span>Mine</button>
    <button data-scr="me" onclick="csTab('me',this)"><span class="ic">👤</span>Me</button>
  </div>
</div>

<!-- DETAIL -->
<div id="csDetail">
  <div class="dhead"><button class="cs-appbar bk" style="background:rgba(255,255,255,.08);border:none;color:#fff;width:34px;height:34px;border-radius:10px;font-size:1.1rem" onclick="csCloseDetail()">‹</button>
    <b id="csDetTitle" style="flex:1;font-size:.92rem"></b>
    <button class="cs-btn d" id="csFollowBtn" onclick="csFollow()">＋ Follow</button>
  </div>
  <div class="dbody" id="csDetBody"></div>
</div>

<div class="cs-backdrop" id="csBackdrop" onclick="csCloseSheets()"></div>

<!-- SHEETS -->
<div class="cs-sheet" id="sheetSize"><div class="grab"></div><h3>📐 Canvas Size<button class="x" onclick="csCloseSheets()">×</button></h3><div class="cs-grid" id="csSizeGrid"></div></div>
<div class="cs-sheet" id="sheetEmoji"><div class="grab"></div><h3>😀 Stickers & Emoji<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-row" style="margin-bottom:.5rem"><input id="csEmojiSearch" class="cs-input" placeholder="emoji or image URL…" style="flex:1"><button class="cs-btn t" onclick="csAddEmojiInput()">Add</button></div>
  <div class="cs-grid" id="csEmojiGrid"></div></div>
<div class="cs-sheet" id="sheetShape"><div class="grab"></div><h3>⬛ Shapes<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-grid">
    <div class="cs-chip" onclick="csAddShape('rect')">▭ Box</div><div class="cs-chip" onclick="csAddShape('round')">▢ Rounded</div>
    <div class="cs-chip" onclick="csAddShape('circle')">⬤ Circle</div><div class="cs-chip" onclick="csAddShape('triangle')">▲ Triangle</div>
    <div class="cs-chip" onclick="csAddShape('star')">★ Star</div><div class="cs-chip" onclick="csAddShape('line')">▬ Line</div>
    <div class="cs-chip" onclick="csAddShape('heart')">❤ Heart</div><div class="cs-chip" onclick="csAddShape('badge')">🏵 Badge</div></div></div>
<div class="cs-sheet" id="sheetBubble"><div class="grab"></div><h3>💬 Speech Bubbles<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-grid"><div class="cs-chip" onclick="csAddBubble('oval')">💬 Oval</div><div class="cs-chip" onclick="csAddBubble('rect')">🗨 Rounded</div>
    <div class="cs-chip" onclick="csAddBubble('think')">💭 Thought</div><div class="cs-chip" onclick="csAddBubble('burst')">💥 Burst</div></div></div>
<div class="cs-sheet" id="sheetCanvasBg"><div class="grab"></div><h3>🎨 Background<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-row" style="margin-bottom:.6rem"><button class="cs-btn d" onclick="csSetBg('transparent')">▣ Transparent</button>
    <button class="cs-btn d" onclick="csSetBg('#ffffff')">⬜ White</button><button class="cs-btn d" onclick="csSetBg('#070b16')">⬛ Dark</button>
    <label class="cs-field">Pick<input type="color" class="cs-color" value="#1565c0" onchange="csSetBg(this.value)"></label></div>
  <div class="cs-grid" id="csBgGrad"></div></div>
<div class="cs-sheet" id="sheetQR"><div class="grab"></div><h3>🔳 QR Code<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-field" style="margin-bottom:.5rem">Link or text<input id="csQRtext" class="cs-input" placeholder="https://mynamecc.online"></div>
  <button class="cs-btn t" onclick="csAddQR()">Add QR</button></div>
<div class="cs-sheet" id="sheetGif"><div class="grab"></div><h3>🎞️ Animated GIF<button class="x" onclick="csCloseSheets()">×</button></h3>
  <p class="cs-note" style="margin-bottom:.6rem">Pick an animation — your whole design becomes an animated sticker (GIF).</p>
  <div class="cs-grid">
    <div class="cs-chip" onclick="csExportGIF('pulse')">💗 Pulse</div><div class="cs-chip" onclick="csExportGIF('bounce')">🏀 Bounce</div>
    <div class="cs-chip" onclick="csExportGIF('shake')">🤳 Shake</div><div class="cs-chip" onclick="csExportGIF('spin')">🌀 Spin</div>
    <div class="cs-chip" onclick="csExportGIF('flash')">⚡ Flash</div><div class="cs-chip" onclick="csExportGIF('slide')">➡️ Slide</div></div>
  <div id="csGifStatus" style="margin-top:.7rem;text-align:center;font-size:.8rem;color:var(--cs-mut)"></div></div>
<div class="cs-sheet" id="sheetAI"><div class="grab"></div><h3>✨ AI Generate<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-field" style="margin-bottom:.5rem">Describe your sticker / poster<input id="csAIPrompt" class="cs-input" placeholder="cartoon football mascot, gold & blue"></div>
  <button class="cs-btn g" onclick="csAIPrompt()">💡 Build a prompt</button>
  <div id="csAIOut" class="cs-note" style="display:none;margin-top:.6rem"></div>
  <p class="cs-note" style="margin-top:.6rem">Text→image AI needs an image API key (OpenAI / Stability / Replicate) — wired as a server hook. Until added, this builds a prompt to paste into any AI tool, then drop the result in via <b>Image</b>.</p></div>
<div class="cs-sheet" id="sheetBg"><div class="grab"></div><h3>✂️ Remove Background<button class="x" onclick="csCloseSheets()">×</button></h3>
  <p class="cs-note" style="margin-bottom:.6rem">Select an image first. Erases pixels near the corner colour — best for plain backgrounds.</p>
  <div class="cs-field" style="margin-bottom:.6rem">Strength <span id="csBgVal">28</span><input type="range" id="csBgThresh" min="6" max="90" value="28" oninput="document.getElementById('csBgVal').textContent=this.value"></div>
  <div class="cs-row"><button class="cs-btn t" onclick="csRemoveBg()">✂️ Erase</button><button class="cs-btn d" onclick="csRestoreImg()">↺ Undo</button></div></div>
<div class="cs-sheet" id="sheetExport"><div class="grab"></div><h3>⬇️ Download & Share<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-field" style="margin-bottom:.5rem">Quality<select id="csExpScale" class="cs-input"><option value="2">HD (2×)</option><option value="3">Ultra (3×)</option><option value="1">Standard</option></select></div>
  <div class="cs-grid"><div class="cs-chip" onclick="csExport('png')">PNG<br><small>transparent</small></div><div class="cs-chip" onclick="csExport('jpg')">JPG</div>
    <div class="cs-chip" onclick="csExport('webp')">WebP</div><div class="cs-chip" onclick="csExport('pdf')">PDF</div><div class="cs-chip" onclick="csShareWA()">🟢 WhatsApp</div></div></div>
<div class="cs-sheet" id="sheetSave"><div class="grab"></div><h3>💾 Save Design<button class="x" onclick="csCloseSheets()">×</button></h3>
  <div class="cs-field" style="margin-bottom:.5rem">Title<input id="csSaveTitle" class="cs-input" placeholder="My sticker"></div>
  <div class="cs-row" style="margin-bottom:.5rem"><label class="cs-field" style="flex:1">Category
    <select id="csSaveCat" class="cs-input"><option>Football</option><option>Cricket</option><option>World Cup Prediction</option><option>Club Events</option><option>Festivals</option><option>Birthday</option><option>Congratulations</option><option>Troll</option><option>Motivational</option><option>General</option></select></label>
    <label class="cs-field" style="flex:1">Type<select id="csSaveKind" class="cs-input"><option value="sticker">Sticker</option><option value="troll">Troll</option><option value="meme">Meme</option><option value="poster">Poster</option></select></label></div>
  <label class="cs-row" style="gap:.5rem;margin-bottom:.7rem;font-size:.8rem"><input type="checkbox" id="csSavePublic"> Share publicly to Explore</label>
  <button class="cs-btn g" style="width:100%;justify-content:center" onclick="csSave()">💾 Save</button></div>

<div class="cs-toast" id="csToast"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.0/fabric.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gif.js/0.2.0/gif.js"></script>
<script>
var CS_SELF=<?= json_encode(url('modules/creative_studio.php')) ?>;
var CS_CSRF=<?= json_encode(csrfToken()) ?>;
var CS_LOGO=<?= json_encode($LOGO) ?>;
var CS_CLUB=<?= json_encode($CLUB) ?>;
var CS_SITE=<?= json_encode(rtrim(defined('SITE_URL')?SITE_URL:'https://mynamecc.online','/')) ?>;
var CS_DASH=<?= json_encode(url('dashboard.php')) ?>;
var csCurrentId=0, csDetId=0, csDetAuthor=0, csGifWorker=null;

function csToast(m){var t=document.getElementById('csToast');t.textContent=m;t.classList.add('on');clearTimeout(t._t);t._t=setTimeout(function(){t.classList.remove('on');},2300);}
function csPost(a,d){var fd=new FormData();fd.append('action',a);for(var k in d){fd.append(k,d[k]);}return fetch(CS_SELF,{method:'POST',headers:{'X-CSRF-Token':CS_CSRF},body:fd}).then(function(r){return r.json();});}
function csGet(a,p){var q=CS_SELF+'?action='+a;if(p){for(var k in p){q+='&'+k+'='+encodeURIComponent(p[k]);}}return fetch(q).then(function(r){return r.json();});}
function csOpenSheet(id){csCloseSheets();document.getElementById(id).classList.add('on');document.getElementById('csBackdrop').classList.add('on');}
function csCloseSheets(){document.querySelectorAll('.cs-sheet.on').forEach(function(s){s.classList.remove('on');});document.getElementById('csBackdrop').classList.remove('on');}
function csExit(){document.body.classList.remove('cs-app');window.location.href=CS_DASH;}
var CS_TITLES={editor:'Creative Studio',templates:'Templates',explore:'Explore',mine:'My Designs',me:'My Profile'};
function csTab(scr,btn,force){
  document.querySelectorAll('.cs-tabbar button').forEach(function(b){b.classList.remove('on');});
  document.querySelectorAll('.cs-tabbar button[data-scr="'+scr+'"]').forEach(function(b){if(!b.classList.contains('fab'))b.classList.add('on');});
  if(btn)btn.classList.add('on');
  document.querySelectorAll('.cs-screen').forEach(function(s){s.classList.remove('on');});
  document.getElementById('scr-'+scr).classList.add('on');
  document.getElementById('csAppTitle').textContent=CS_TITLES[scr]||'Creative Studio';
  if(scr==='mine')csLoadMine(); if(scr==='explore')csLoadExplore(); if(scr==='me')csLoadHistory();
  if(scr==='editor')setTimeout(csFit,60);
}

// ── Fabric ──
var SIZES=[{n:'Sticker',w:1080,h:1080,k:'sticker'},{n:'IG Post',w:1080,h:1080,k:'meme'},{n:'IG Story',w:1080,h:1920,k:'poster'},{n:'WA Status',w:1080,h:1920,k:'poster'},{n:'FB Post',w:1200,h:1200,k:'meme'},{n:'Banner',w:1600,h:900,k:'poster'},{n:'A4 Poster',w:1240,h:1754,k:'poster'},{n:'Cover',w:1640,h:624,k:'poster'}];
var canvas,curKind='sticker',curW=1080,curH=1080;
function csFit(){
  var stage=document.querySelector('.cs-stage'); if(!stage)return;
  var maxW=stage.clientWidth-20, maxH=stage.clientHeight-12;
  var scale=Math.min(maxW/curW,maxH/curH,1); if(!(scale>0))scale=0.3;
  document.getElementById('csCanvasWrap').style.width=(curW*scale)+'px';
  canvas.setZoom(scale);canvas.setWidth(curW*scale);canvas.setHeight(curH*scale);canvas.requestRenderAll();
}
function csInit(){
  canvas=new fabric.Canvas('csCanvas',{backgroundColor:'#ffffff',preserveObjectStacking:true});
  csSetSize(1080,1080,'sticker',false);
  canvas.on('selection:created',csSel);canvas.on('selection:updated',csSel);canvas.on('selection:cleared',csSelClear);
  window.addEventListener('resize',csFit);
}
function csSetSize(w,h,k,keep){curW=w;curH=h;curKind=k||curKind;canvas.setWidth(w);canvas.setHeight(h);if(!keep){canvas.clear();canvas.setBackgroundColor('#ffffff',canvas.renderAll.bind(canvas));}csFit();}
function csSel(){var o=canvas.getActiveObject();if(!o)return;document.getElementById('csObjBar').style.display='flex';document.getElementById('csBgRmBtn').style.display=(o.type==='image')?'inline-block':'none';try{document.getElementById('csObjColor').value=(o.fill&&typeof o.fill==='string')?o.fill:'#ffffff';}catch(e){}}
function csSelClear(){document.getElementById('csObjBar').style.display='none';}
function csObj(op){var o=canvas.getActiveObject();if(!o)return;
  if(op==='del'){if(o._objects){o.forEachObject(function(x){canvas.remove(x);});}canvas.remove(o);canvas.discardActiveObject();}
  else if(op==='front')canvas.bringToFront(o);else if(op==='back')canvas.sendToBack(o);else if(op==='center')canvas.centerObject(o);
  else if(op==='flip')o.set('flipX',!o.flipX);else if(op==='dup'){o.clone(function(c){c.set({left:(o.left||0)+24,top:(o.top||0)+24});canvas.add(c);canvas.setActiveObject(c);});}
  canvas.requestRenderAll();}
function csObjColorChange(v){var o=canvas.getActiveObject();if(o){o.set('fill',v);canvas.requestRenderAll();}}

function csAddText(){var t=new fabric.IText('Tap to edit',{left:curW/2,top:curH/2,originX:'center',originY:'center',fontFamily:'Anton',fontSize:Math.round(curW*0.09),fill:'#fff',stroke:'#000',strokeWidth:Math.round(curW*0.004),textAlign:'center',shadow:'rgba(0,0,0,.4) 0 3px 8px'});canvas.add(t).setActiveObject(t);canvas.requestRenderAll();csOpenSheet('sheetTextStyle');}
function csAddEmojiInput(){var v=document.getElementById('csEmojiSearch').value.trim();if(!v)return;if(/^https?:\/\//i.test(v))csAddImageURL(v);else csAddEmoji(v);csCloseSheets();}
function csAddEmoji(e){var t=new fabric.Text(e,{left:curW/2,top:curH/2,originX:'center',originY:'center',fontSize:Math.round(curW*0.22)});canvas.add(t).setActiveObject(t);canvas.requestRenderAll();}
function csAddImageFile(f){if(!f)return;var rd=new FileReader();rd.onload=function(){csAddImageURL(rd.result);};rd.readAsDataURL(f);}
function csAddImageURL(src){fabric.Image.fromURL(src,function(img){if(!img){csToast('Could not load image');return;}var s=Math.min(curW*0.7/img.width,curH*0.7/img.height,1);img.set({left:curW/2,top:curH/2,originX:'center',originY:'center',scaleX:s,scaleY:s});img._origSrc=src;canvas.add(img).setActiveObject(img);canvas.requestRenderAll();},{crossOrigin:'anonymous'});csCloseSheets();}
function csAddLogo(){if(!CS_LOGO){csToast('No club logo set');return;}fabric.Image.fromURL(CS_LOGO,function(img){var s=(curW*0.18)/img.width;img.set({left:curW-curW*0.13,top:curH-curW*0.13,originX:'center',originY:'center',scaleX:s,scaleY:s,opacity:.95});canvas.add(img).setActiveObject(img);canvas.requestRenderAll();});}
function csAddShape(kind){var c=curW*0.32,opt={left:curW/2,top:curH/2,originX:'center',originY:'center',fill:'#1fd6b5'},o;
  if(kind==='rect')o=new fabric.Rect(Object.assign({width:c,height:c*0.7},opt));else if(kind==='round')o=new fabric.Rect(Object.assign({width:c,height:c*0.7,rx:30,ry:30},opt));
  else if(kind==='circle')o=new fabric.Circle(Object.assign({radius:c/2},opt));else if(kind==='triangle')o=new fabric.Triangle(Object.assign({width:c,height:c},opt));
  else if(kind==='line')o=new fabric.Rect(Object.assign({width:c,height:Math.max(8,curW*0.012)},opt));else if(kind==='star')o=csStar(c/2,opt);
  else if(kind==='heart')o=csHeart(c,opt);else if(kind==='badge')o=csStar(c/2,Object.assign({},opt,{fill:'#ffd34d'}),12);
  if(o){canvas.add(o).setActiveObject(o);canvas.requestRenderAll();}csCloseSheets();}
function csStar(r,opt,pts){pts=pts||5;var a=Math.PI/pts,p=[];for(var i=0;i<2*pts;i++){var rad=(i%2===0)?r:r*0.45;p.push({x:rad*Math.sin(i*a),y:-rad*Math.cos(i*a)});}return new fabric.Polygon(p,opt);}
function csHeart(c,opt){var path='M 0 -'+(c*0.25)+' C -'+(c*0.5)+' -'+(c*0.75)+', -'+(c*0.95)+' -'+(c*0.1)+', 0 '+(c*0.55)+' C '+(c*0.95)+' -'+(c*0.1)+', '+(c*0.5)+' -'+(c*0.75)+', 0 -'+(c*0.25)+' Z';return new fabric.Path(path,Object.assign({fill:'#ff4d6d'},opt));}
function csAddBubble(kind){var w=curW*0.5,h=curW*0.36,opt={left:curW/2,top:curH/2,originX:'center',originY:'center',fill:'#fff',stroke:'#111',strokeWidth:6},o;
  if(kind==='rect')o=new fabric.Rect(Object.assign({width:w,height:h,rx:40,ry:40},opt));else if(kind==='oval')o=new fabric.Ellipse(Object.assign({rx:w/2,ry:h/2},opt));
  else if(kind==='think')o=new fabric.Ellipse(Object.assign({rx:w/2,ry:h/2},opt));else if(kind==='burst')o=csStar(w/2,Object.assign({},opt,{fill:'#fff3b0'}),12);
  canvas.add(o).setActiveObject(o);canvas.requestRenderAll();csCloseSheets();}
function csAddQR(){var txt=document.getElementById('csQRtext').value.trim()||CS_SITE;var tmp=document.createElement('div');new QRCode(tmp,{text:txt,width:480,height:480,correctLevel:QRCode.CorrectLevel.M});setTimeout(function(){var img=tmp.querySelector('img')||tmp.querySelector('canvas');var src=img.tagName==='IMG'?img.src:img.toDataURL('image/png');csAddImageURL(src);},180);}
function csSetBg(v){if(v==='transparent'){canvas.setBackgroundColor('',canvas.renderAll.bind(canvas));canvas.backgroundColor='';}else canvas.setBackgroundColor(v,canvas.renderAll.bind(canvas));csCloseSheets();}
function csSetGrad(c1,c2){canvas.setBackgroundColor(new fabric.Gradient({type:'linear',coords:{x1:0,y1:0,x2:0,y2:curH},colorStops:[{offset:0,color:c1},{offset:1,color:c2}]}),canvas.renderAll.bind(canvas));csCloseSheets();}

function csRemoveBg(){var o=canvas.getActiveObject();if(!o||o.type!=='image'){csToast('Select an image first');return;}var el=o._element;if(!el){csToast('Not ready');return;}
  var th=parseInt(document.getElementById('csBgThresh').value,10),w=el.naturalWidth||el.width,h=el.naturalHeight||el.height;
  var cv=document.createElement('canvas');cv.width=w;cv.height=h;var ctx=cv.getContext('2d');
  try{ctx.drawImage(el,0,0,w,h);}catch(e){csToast('Image blocks editing (CORS)');return;}
  var d;try{d=ctx.getImageData(0,0,w,h);}catch(e){csToast('Image blocks editing (CORS)');return;}
  var px=d.data,corners=[[0,0],[w-1,0],[0,h-1],[w-1,h-1]].map(function(c){var i=(c[1]*w+c[0])*4;return[px[i],px[i+1],px[i+2]];}),lim=th*th*3;
  for(var i=0;i<px.length;i+=4){var r=px[i],g=px[i+1],b=px[i+2],hit=false;for(var c=0;c<corners.length;c++){var cc=corners[c],dr=r-cc[0],dg=g-cc[1],db=b-cc[2];if(dr*dr+dg*dg+db*db<lim){hit=true;break;}}if(hit)px[i+3]=0;}
  ctx.putImageData(d,0,0);if(!o._origSrc)o._origSrc=el.src;o.setElement(cv);o.set('dirty',true);canvas.requestRenderAll();csToast('✂️ Done');csCloseSheets();}
function csRestoreImg(){var o=canvas.getActiveObject();if(!o||o.type!=='image'||!o._origSrc)return;fabric.util.loadImage(o._origSrc,function(img){o.setElement(img);o.set('dirty',true);canvas.requestRenderAll();csToast('↺ Restored');},null,'anonymous');}

function csAIPrompt(){var p=document.getElementById('csAIPrompt').value.trim()||'club mascot sticker';var styles=['vibrant sticker, thick white outline, transparent background','flat vector cartoon','bold comic style','glossy 3D render','clean anime style'];var st=styles[Math.floor(Math.random()*styles.length)];var full=p+', '+st+', '+CS_CLUB+' theme, gold and blue colours, high detail, centered, no text';var out=document.getElementById('csAIOut');out.style.display='block';out.innerHTML='<b>Copy into any AI image tool:</b><br><br>'+full.replace(/</g,'&lt;')+'<br><br><button class="cs-btn t" onclick="csCopy(\''+full.replace(/'/g,"\\'")+'\')">📋 Copy</button>';}
function csCopy(t){if(navigator.clipboard)navigator.clipboard.writeText(t).then(function(){csToast('Copied');});}

// ── export ──
function csExport(type){var scale=parseFloat(document.getElementById('csExpScale').value)*Math.max(1,1080/curW);csCloseSheets();canvas.discardActiveObject();var z=canvas.getZoom();
  if(type==='pdf'){var ob=canvas.backgroundColor;canvas.setBackgroundColor('#ffffff',function(){});canvas.renderAll();var url=canvas.toDataURL({format:'png',multiplier:scale/z});canvas.setBackgroundColor(ob,function(){});var jsPDF=window.jspdf.jsPDF;var pdf=new jsPDF({orientation:curW>=curH?'l':'p',unit:'px',format:[curW,curH]});pdf.addImage(url,'PNG',0,0,curW,curH);pdf.save('creative-studio.pdf');csToast('📄 PDF');csLogDl('pdf');return;}
  var fmt=type==='png'?'png':(type==='webp'?'webp':'jpeg'),bg=(type==='png')?null:'#ffffff';
  if(bg){var o2=canvas.backgroundColor;canvas.setBackgroundColor(bg,function(){});canvas.renderAll();}
  var url=canvas.toDataURL({format:fmt,quality:0.95,multiplier:scale/z});if(bg){canvas.setBackgroundColor(o2||'',function(){});canvas.renderAll();}
  csDownload(url,'creative-studio.'+(type==='jpg'?'jpg':type));csToast('⬇️ Downloaded');csLogDl(type);}
function csDownload(url,name){var a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();document.body.removeChild(a);}
function csLogDl(fmt){csPost('log_download',{id:csCurrentId,title:document.getElementById('csSaveTitle').value||curKind,fmt:fmt});}
function csShareWA(){csCloseSheets();canvas.discardActiveObject();var z=canvas.getZoom(),scale=2*Math.max(1,1080/curW);canvas.toCanvasElement(scale/z).toBlob(function(blob){if(!blob){csToast('Export failed');return;}var file=new File([blob],'creative.png',{type:'image/png'});var cap='🎨 Made with '+CS_CLUB+' Creative Studio';if(navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],text:cap}).catch(function(){});}else{csDownload(URL.createObjectURL(blob),'creative.png');csToast('Saved — share in WhatsApp');}csLogDl('png');},'image/png');}

// ── GIF ──
function csEnsureGifWorker(cb){if(csGifWorker){cb(csGifWorker);return;}fetch('https://cdnjs.cloudflare.com/ajax/libs/gif.js/0.2.0/gif.worker.js').then(function(r){return r.text();}).then(function(t){csGifWorker=URL.createObjectURL(new Blob([t],{type:'application/javascript'}));cb(csGifWorker);}).catch(function(){cb(null);});}
function csExportGIF(preset){
  var st=document.getElementById('csGifStatus');st.textContent='Rendering frames…';
  canvas.discardActiveObject();var z=canvas.getZoom();
  var out=Math.min(480,curW),sc=out/curW,outH=Math.round(curH*sc);
  var base=canvas.toCanvasElement((out/curW)/z); // base frame image
  csEnsureGifWorker(function(worker){
    if(!worker){st.textContent='GIF engine failed to load';return;}
    var gif=new GIF({workers:2,quality:12,width:out,height:outH,workerScript:worker,transparent:null});
    var N=14;
    for(var f=0;f<N;f++){
      var t=f/N, cv=document.createElement('canvas');cv.width=out;cv.height=outH;var c=cv.getContext('2d');
      c.clearRect(0,0,out,outH);c.save();c.translate(out/2,outH/2);
      var s=1,dx=0,dy=0,rot=0,al=1;
      if(preset==='pulse')s=1+0.12*Math.sin(t*Math.PI*2);
      else if(preset==='bounce')dy=-outH*0.08*Math.abs(Math.sin(t*Math.PI*2));
      else if(preset==='shake')dx=out*0.04*Math.sin(t*Math.PI*4);
      else if(preset==='spin')rot=t*Math.PI*2;
      else if(preset==='flash')al=0.55+0.45*Math.abs(Math.sin(t*Math.PI*2));
      else if(preset==='slide')dx=out*(0.5-Math.min(0.5,t))*2*(1-t);
      c.translate(dx,dy);c.rotate(rot);c.scale(s,s);c.globalAlpha=al;
      c.drawImage(base,-out/2,-outH/2,out,outH);c.restore();
      gif.addFrame(cv,{copy:true,delay:80});
    }
    gif.on('progress',function(p){st.textContent='Encoding… '+Math.round(p*100)+'%';});
    gif.on('finished',function(blob){st.textContent='✅ Ready!';var file=new File([blob],'sticker.gif',{type:'image/gif'});
      if(navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],text:'🎬 '+CS_CLUB}).catch(function(){csDownload(URL.createObjectURL(blob),'sticker.gif');});}
      else{csDownload(URL.createObjectURL(blob),'sticker.gif');}
      csLogDl('gif');setTimeout(csCloseSheets,800);});
    gif.render();
  });
}

// ── save ──
function csOpenSave(){var ti=document.getElementById('csSaveTitle');if(!ti.value)ti.value='My '+curKind;csOpenSheet('sheetSave');}
function csSave(){var z=canvas.getZoom();canvas.discardActiveObject();canvas.requestRenderAll();var json=JSON.stringify(canvas.toJSON());var thumb=canvas.toDataURL({format:'jpeg',quality:0.6,multiplier:(400/curW)/z});csToast('Saving…');
  csPost('save',{id:csCurrentId,title:document.getElementById('csSaveTitle').value,category:document.getElementById('csSaveCat').value,kind:document.getElementById('csSaveKind').value,canvas_json:json,thumb:thumb,width:curW,height:curH,is_public:document.getElementById('csSavePublic').checked?1:0}).then(function(r){if(r.ok){csCurrentId=r.id;csToast('✅ Saved');csCloseSheets();}else csToast(r.msg||'Save failed');}).catch(function(){csToast('Save failed');});}
function csNew(){csCurrentId=0;canvas.clear();canvas.setBackgroundColor('#ffffff',canvas.renderAll.bind(canvas));}

// ── galleries ──
function csEsc(s){var d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML;}
function csCardHTML(d,mine){var pub=parseInt(d.is_public||0,10)===1;
  var h='<div class="cs-card"><img class="thumb" src="'+(d.thumb||'')+'" onclick="csOpenDetail('+d.id+')"><div class="meta"><b>'+csEsc(d.title)+'</b><small>'+csEsc(d.category||d.kind)+' · ❤ '+(d.likes||0)+(d.author?' · '+csEsc(d.author):'')+'</small></div><div class="acts">';
  if(mine){h+='<button onclick="csOpen('+d.id+')">✏️ Edit</button><button onclick="csVis('+d.id+','+(pub?0:1)+')">'+(pub?'🌍':'🔒')+'</button><button onclick="csDel('+d.id+')">🗑️</button>';}
  else{h+='<button onclick="csOpenDetail('+d.id+')">👁 View</button><button onclick="csLike('+d.id+',this)">'+(parseInt(d.liked||0,10)?'❤':'🤍')+' '+(d.likes||0)+'</button><button onclick="csOpen('+d.id+')">✏️ Remix</button>';}
  h+='</div></div>';return h;}
function csSkel(el){el.innerHTML='<div class="cs-spin" style="grid-column:1/-1"></div>';}
function csLoadMine(){var el=document.getElementById('csMine');csSkel(el);csGet('mine').then(function(r){if(!r.ok||!r.rows.length){el.innerHTML='<div class="cs-empty">No saved designs yet. Tap ＋ to create!</div>';return;}el.innerHTML=r.rows.map(function(d){return csCardHTML(d,true);}).join('');});}
var csExpMode='explore';
function csExploreMode(m,btn){csExpMode=m;document.getElementById('segAll').classList.toggle('on',m==='explore');document.getElementById('segFollow').classList.toggle('on',m==='following');csLoadExplore();}
function csLoadExplore(){var el=document.getElementById('csExplore');csSkel(el);csGet(csExpMode).then(function(r){if(!r.ok||!r.rows.length){el.innerHTML='<div class="cs-empty">'+(csExpMode==='following'?'Follow some creators to see their work here.':'No public designs yet. Save one as Public!')+'</div>';return;}el.innerHTML=r.rows.map(function(d){return csCardHTML(d,false);}).join('');});}
function csLoadHistory(){var el=document.getElementById('csHistory');csSkel(el);csGet('downloads').then(function(r){if(!r.ok||!r.rows.length){el.innerHTML='<div class="cs-empty">No downloads yet.</div>';return;}el.innerHTML=r.rows.map(function(d){return '<div class="cs-cmt"><b>'+csEsc(d.title||'Design')+'</b><p>'+String(d.fmt).toUpperCase()+' · '+csEsc(d.created_at)+'</p></div>';}).join('');});}

function csOpen(id){csGet('load',{id:id}).then(function(r){if(!r.ok){csToast(r.msg||'Cannot open');return;}var d=r.design;csCurrentId=d.mine?parseInt(d.id,10):0;curW=parseInt(d.width,10);curH=parseInt(d.height,10);curKind=d.kind;canvas.setWidth(curW);canvas.setHeight(curH);canvas.loadFromJSON(d.canvas_json,function(){csFit();canvas.requestRenderAll();});document.getElementById('csSaveTitle').value=d.title+(d.mine?'':' (remix)');csCloseDetail();csTab('editor',null,'editor');document.querySelector('.cs-tabbar button[data-scr="editor"]').classList.add('on');csToast(d.mine?'Opened':'Remix — Save to keep');});}
function csVis(id,pub){csPost('visibility',{id:id,is_public:pub}).then(function(r){if(r.ok){csToast(pub?'Now public':'Now private');csLoadMine();}});}
function csDel(id){if(!confirm('Delete this design?'))return;csPost('delete',{id:id}).then(function(r){if(r.ok){csToast('Deleted');csLoadMine();}});}
function csLike(id,btn){csPost('like',{id:id}).then(function(r){if(r.ok){btn.innerHTML=(r.liked?'❤':'🤍')+' '+r.likes;}});}

// ── detail (view + comments + follow) ──
function csOpenDetail(id){csDetId=id;document.getElementById('csDetail').classList.add('on');var b=document.getElementById('csDetBody');b.innerHTML='<div class="cs-spin"></div>';
  csGet('detail',{id:id}).then(function(r){if(!r.ok){b.innerHTML='<div class="cs-empty">'+(r.msg||'Unavailable')+'</div>';return;}var d=r.design;csDetAuthor=parseInt(d.member_id,10);
    document.getElementById('csDetTitle').textContent=d.title;
    var fb=document.getElementById('csFollowBtn');fb.style.display=d.mine==1?'none':'inline-flex';fb.textContent=d.following?'✓ Following':'＋ Follow';fb.className='cs-btn '+(d.following?'t':'d');
    b.innerHTML='<img class="big" src="'+(d.thumb||'')+'">'+
      '<div class="cs-row" style="justify-content:space-between;margin-bottom:.6rem"><div><b>'+csEsc(d.title)+'</b><br><small style="color:var(--cs-mut)">by '+csEsc(d.author)+' · '+csEsc(d.category)+'</small></div>'+
      '<button class="cs-btn '+(d.liked?'w':'d')+'" id="csDetLike" onclick="csDetLike()">'+(d.liked?'❤':'🤍')+' '+d.likes+'</button></div>'+
      '<div class="cs-row" style="margin-bottom:.8rem"><button class="cs-btn g" onclick="csOpen('+d.id+')">✏️ Remix this</button></div>'+
      '<h3 style="font-size:.85rem">💬 Comments</h3><div id="csCmts"></div>'+
      '<div class="cs-row" style="margin-top:.6rem"><input id="csCmtInput" class="cs-input" placeholder="Add a comment…" style="flex:1"><button class="cs-btn t" onclick="csAddComment()">Send</button></div>';
    csLoadComments();
  });}
function csCloseDetail(){document.getElementById('csDetail').classList.remove('on');}
function csDetLike(){csPost('like',{id:csDetId}).then(function(r){if(r.ok){var b=document.getElementById('csDetLike');b.className='cs-btn '+(r.liked?'w':'d');b.innerHTML=(r.liked?'❤':'🤍')+' '+r.likes;}});}
function csFollow(){csPost('follow_toggle',{author_id:csDetAuthor}).then(function(r){if(r.ok){var fb=document.getElementById('csFollowBtn');fb.textContent=r.following?'✓ Following':'＋ Follow';fb.className='cs-btn '+(r.following?'t':'d');csToast(r.following?'Following':'Unfollowed');}else csToast(r.msg||'Failed');});}
function csLoadComments(){csGet('comments',{id:csDetId}).then(function(r){var el=document.getElementById('csCmts');if(!el)return;if(!r.ok||!r.rows.length){el.innerHTML='<div class="cs-empty" style="padding:1rem">No comments yet.</div>';return;}el.innerHTML=r.rows.map(function(c){return '<div class="cs-cmt"><b>'+csEsc(c.author)+'</b><p>'+csEsc(c.body)+'</p></div>';}).join('');});}
function csAddComment(){var i=document.getElementById('csCmtInput'),v=i.value.trim();if(!v)return;csPost('comment_add',{id:csDetId,body:v}).then(function(r){if(r.ok){i.value='';csLoadComments();}else csToast(r.msg||'Failed');});}

// ── templates ──
var TEMPLATES=[
 {cat:'World Cup Prediction',name:'Match Day',w:1080,h:1080,bg:['#07225c','#0d47a1'],items:[{t:'text',s:'MATCH DAY',f:'Anton',size:120,fill:'#ffd34d',y:0.28,stroke:'#000',sw:5},{t:'text',s:'⚽ PREDICT & WIN',f:'Bebas Neue',size:70,fill:'#fff',y:0.5},{t:'text',s:'FIFA WC 2026',f:'Sora',size:54,fill:'#1fd6b5',y:0.66}]},
 {cat:'Football',name:'Goal!',w:1080,h:1080,bg:['#11998e','#38ef7d'],items:[{t:'emoji',s:'⚽',size:340,y:0.34},{t:'text',s:'GOAL!!!',f:'Anton',size:150,fill:'#fff',y:0.7,stroke:'#000',sw:6}]},
 {cat:'Birthday',name:'Happy Birthday',w:1080,h:1080,bg:['#7b2ff7','#f107a3'],items:[{t:'emoji',s:'🎂',size:260,y:0.3},{t:'text',s:'HAPPY BIRTHDAY',f:'Bebas Neue',size:96,fill:'#ffd34d',y:0.62,stroke:'#000',sw:3},{t:'text',s:'From all of us 🎉',f:'Sora',size:46,fill:'#fff',y:0.76}]},
 {cat:'Congratulations',name:'Congrats',w:1080,h:1080,bg:['#fc4a1a','#f7b733'],items:[{t:'emoji',s:'🏆',size:300,y:0.32},{t:'text',s:'CONGRATS!',f:'Anton',size:130,fill:'#fff',y:0.68,stroke:'#000',sw:5}]},
 {cat:'Festivals',name:'Greetings',w:1080,h:1920,bg:['#0f2027','#2c5364'],items:[{t:'emoji',s:'🪔',size:300,y:0.3},{t:'text',s:'WARM WISHES',f:'Bebas Neue',size:110,fill:'#ffd34d',y:0.58},{t:'text',s:CS_CLUB,f:'Sora',size:44,fill:'#fff',y:0.7}]},
 {cat:'Troll',name:'Reaction',w:1080,h:1080,bg:['#222','#000'],items:[{t:'text',s:'WHEN YOU SEE IT',f:'Anton',size:84,fill:'#fff',y:0.16,stroke:'#000',sw:4},{t:'emoji',s:'😂',size:360,y:0.52},{t:'text',s:'😂😂😂',f:'Sora',size:90,fill:'#fff',y:0.86}]},
 {cat:'Club Events',name:'Event Poster',w:1240,h:1754,bg:['#1565c0','#07225c'],items:[{t:'text',s:'CLUB EVENT',f:'Anton',size:150,fill:'#ffd34d',y:0.16,stroke:'#000',sw:4},{t:'text',s:'📅 Date · 📍 Venue',f:'Sora',size:50,fill:'#fff',y:0.84},{t:'text',s:CS_CLUB,f:'Bebas Neue',size:60,fill:'#1fd6b5',y:0.92}]},
 {cat:'Motivational',name:'Push',w:1080,h:1080,bg:['#0f2027','#203a43'],items:[{t:'text',s:'STAY\nFOCUSED',f:'Anton',size:130,fill:'#fff',y:0.42,stroke:'#000',sw:3},{t:'text',s:'— '+CS_CLUB,f:'Sora',size:40,fill:'#ffd34d',y:0.74}]}
];
var TPL_CAT='All';
function csBuildTemplates(){var cats=['All'].concat(TEMPLATES.map(function(t){return t.cat;}).filter(function(v,i,a){return a.indexOf(v)===i;}));
  document.getElementById('csTplCats').innerHTML=cats.map(function(c){return '<button class="cs-btn '+(c===TPL_CAT?'g':'d')+'" onclick="TPL_CAT=\''+c+'\';csBuildTemplates()">'+c+'</button>';}).join('');
  var list=TEMPLATES.filter(function(t){return TPL_CAT==='All'||t.cat===TPL_CAT;});
  document.getElementById('csTplGrid').innerHTML=list.map(function(t){var idx=TEMPLATES.indexOf(t);return '<div class="cs-card" onclick="csApplyTpl('+idx+')" style="cursor:pointer"><div style="aspect-ratio:1;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(135deg,'+t.bg[0]+','+t.bg[1]+')"><div style="font-size:2rem">🧩</div><b style="font-size:.8rem;color:#fff;margin-top:.3rem">'+t.name+'</b></div><div class="meta"><small>'+t.cat+'</small></div></div>';}).join('');}
function csApplyTpl(i){var t=TEMPLATES[i];csCurrentId=0;curW=t.w;curH=t.h;curKind=(t.h>t.w?'poster':'meme');canvas.setWidth(curW);canvas.setHeight(curH);canvas.clear();
  canvas.setBackgroundColor(new fabric.Gradient({type:'linear',coords:{x1:0,y1:0,x2:0,y2:curH},colorStops:[{offset:0,color:t.bg[0]},{offset:1,color:t.bg[1]}]}),canvas.renderAll.bind(canvas));
  t.items.forEach(function(it){if(it.t==='text'){canvas.add(new fabric.IText(it.s,{left:curW/2,top:curH*it.y,originX:'center',originY:'center',fontFamily:it.f,fontSize:it.size,fill:it.fill,textAlign:'center',stroke:it.stroke||'',strokeWidth:it.sw||0,shadow:'rgba(0,0,0,.35) 0 3px 7px'}));}else if(it.t==='emoji'){canvas.add(new fabric.Text(it.s,{left:curW/2,top:curH*it.y,originX:'center',originY:'center',fontSize:it.size}));}});
  csTab('editor',null,'editor');document.querySelector('.cs-tabbar button[data-scr="editor"]').classList.add('on');csFit();canvas.requestRenderAll();csToast('Template added!');}

// text style sheet
document.addEventListener('DOMContentLoaded',function(){var ss=document.createElement('div');ss.className='cs-sheet';ss.id='sheetTextStyle';
  ss.innerHTML='<div class="grab"></div><h3>🅣 Text Style<button class="x" onclick="csCloseSheets()">×</button></h3>'+
  '<div class="cs-field" style="margin-bottom:.5rem">Font<select class="cs-input" onchange="csTextFont(this.value)">'+['Anton','Bebas Neue','Sora','Baloo Chettan 2','Anek Malayalam','Noto Sans Malayalam','Impact','Georgia'].map(function(f){return '<option value="'+f+'">'+f+'</option>';}).join('')+'</select></div>'+
  '<div class="cs-row" style="margin-bottom:.5rem"><label class="cs-field">Colour<input type="color" class="cs-color" value="#ffffff" onchange="csTextSet(\'fill\',this.value)"></label><label class="cs-field">Outline<input type="color" class="cs-color" value="#000000" onchange="csTextSet(\'stroke\',this.value)"></label></div>'+
  '<div class="cs-field" style="margin-bottom:.5rem">Size<input type="range" min="20" max="320" value="100" oninput="csTextSet(\'fontSize\',parseInt(this.value,10))"></div>'+
  '<div class="cs-row"><button class="cs-btn d" onclick="csTextSet(\'fontWeight\',\'900\')">Bold</button><button class="cs-btn d" onclick="csTextAlign()">Align</button></div>'+
  '<p class="cs-note malayalam" style="margin-top:.6rem">മലയാളം — choose an Anek/Noto Malayalam font, then type.</p>';document.body.appendChild(ss);});
function csTextFont(f){var o=canvas.getActiveObject();if(o){o.set('fontFamily',f);canvas.requestRenderAll();}}
function csTextSet(k,v){var o=canvas.getActiveObject();if(o){o.set(k,v);canvas.requestRenderAll();}}
function csTextAlign(){var o=canvas.getActiveObject();if(!o)return;var a=['left','center','right'],n=a[(a.indexOf(o.textAlign)+1)%3];o.set('textAlign',n);canvas.requestRenderAll();}

function csBuildSheets(){
  document.getElementById('csSizeGrid').innerHTML=SIZES.map(function(s){return '<div class="cs-chip" onclick="csSetSize('+s.w+','+s.h+',\''+s.k+'\',true);csFit();csCloseSheets()">'+s.n+'<br><small>'+s.w+'×'+s.h+'</small></div>';}).join('');
  var em='😀😂🤣😍😎🥳🤩😭😡🤔👍👎🙏👏💪🔥✨⭐🏆⚽🏏🥇🎉🎊❤️💛💙💚🧡💜🖤🤍🌹🌸🌟💥💢💫🎯🎁🎈🪅👑🦁🐯⚡🌈☀️🌙🎵🎶📣✅❌💯🆕🇮🇳';
  document.getElementById('csEmojiGrid').innerHTML=Array.from(em).map(function(e){return '<div class="cs-emoji" onclick="csAddEmoji(\''+e+'\');csCloseSheets()">'+e+'</div>';}).join('');
  var grads=[['#ffd34d','#e6a800'],['#1fd6b5','#0e9e86'],['#1565c0','#07225c'],['#ff4d6d','#c9184a'],['#7b2ff7','#311b92'],['#11998e','#38ef7d'],['#fc4a1a','#f7b733'],['#0f2027','#2c5364']];
  document.getElementById('csBgGrad').innerHTML=grads.map(function(g){return '<div class="cs-chip" style="background:linear-gradient(135deg,'+g[0]+','+g[1]+');height:48px" onclick="csSetGrad(\''+g[0]+'\',\''+g[1]+'\')"></div>';}).join('');
  csBuildTemplates();
}
window.addEventListener('load',function(){document.body.classList.add('cs-app');csInit();csBuildSheets();setTimeout(csFit,120);});
</script>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
