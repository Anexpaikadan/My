<?php
// fest_detail.php — loaded inside popup for each fest
// Shows entries, upload form, likes, prizes, share
require_once __DIR__.'/../includes/config.php';
require_once __DIR__ . '/../includes/extras.php';
requireLogin();
$me      = currentUser();
$isAdmin = isAdminRole($me['role']);
$uid     = (int)$me['id'];
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$PLACE   = setting('CLUB_PLACE','Vettikkattiri');
$SITE    = rtrim(SITE_URL,'/');

$fid = (int)($_GET['id'] ?? 0);
if (!$fid) { echo '<p>Not found</p>'; exit; }

$st = db()->prepare("SELECT * FROM fests WHERE id=?");
$st->execute([$fid]); $fest=$st->fetch();
if (!$fest) { echo '<p>Fest not found</p>'; exit; }

// Handle upload
$uploadMsg = null;
if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_FILES['entry_photo'])) {
    $ck=db()->prepare("SELECT id FROM fest_entries WHERE fest_id=? AND member_id=?");
    $ck->execute([$fid,$uid]);
    if ($ck->fetch()) {
        $uploadMsg=['err','Already submitted. Delete first.'];
    } else {
        $f=$_FILES['entry_photo'];
        $ext=strtolower(pathinfo($f['name'],PATHINFO_EXTENSION));
        if (!in_array($ext,['jpg','jpeg','png','webp'])) { $uploadMsg=['err','JPG/PNG/WebP only.']; }
        elseif ($f['size']>6*1024*1024) { $uploadMsg=['err','Max 6MB.']; }
        else {
            $dir=__DIR__.'/../assets/uploads/fests/'.$fid.'/';
            if (!is_dir($dir)) mkdir($dir,0755,true);
            $fn='entry_'.time().'_'.mt_rand(1000,9999).'.'.$ext;
            if (move_uploaded_file($f['tmp_name'],$dir.$fn)) {
                img_optimize($dir.$fn);
                $title2=trim($_POST['entry_title']??'');
                $ins=db()->prepare("INSERT INTO fest_entries(fest_id,member_id,image_path,title) VALUES(?,?,?,?)");
                $ins->execute([$fid,$uid,$fn,$title2]);
                $eid2=db()->lastInsertId();
                $ogDir=$dir.'og/'; if(!is_dir($ogDir))mkdir($ogDir,0755,true);
                $ogFn='entry_'.$eid2.'.'.$ext;
                copy($dir.$fn,$ogDir.$ogFn);
                db()->prepare("UPDATE fest_entries SET og_path=? WHERE id=?")->execute([$ogFn,$eid2]);
                $uploadMsg=['ok','✅ Submitted!'];
            } else { $uploadMsg=['err','Upload failed.']; }
        }
    }
}

// Load entries
$entries=db()->query("SELECT e.*,u.name member_name FROM fest_entries e JOIN users u ON u.id=e.member_id WHERE e.fest_id={$fid} ORDER BY e.like_count DESC, e.created_at ASC")->fetchAll();
$myEntry=db()->prepare("SELECT * FROM fest_entries WHERE fest_id=? AND member_id=?");
$myEntry->execute([$fid,$uid]); $myEntry=$myEntry->fetch();
$myLike=db()->prepare("SELECT entry_id FROM fest_likes WHERE fest_id=? AND voter_id=?");
$myLike->execute([$fid,$uid]); $myLikeRow=$myLike->fetch();
$myLikedId=$myLikeRow?(int)$myLikeRow['entry_id']:0;
$totalLikes=db()->prepare("SELECT COUNT(*) FROM fest_likes WHERE fest_id=?");
$totalLikes->execute([$fid]); $totalLikes=(int)$totalLikes->fetchColumn();
$canLike=$fest['voting_open']&&!$myLikedId;
$nowT=date('Y-m-d H:i:s');
?>
<div style="background:#fff;border-radius:24px 24px 0 0">

<!-- Header -->
<div style="background:linear-gradient(135deg,#0B1033,#0A14E0);padding:.75rem 1rem;border-radius:24px 24px 0 0;display:flex;align-items:center;gap:.5rem">
  <div style="flex:1">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:.08em;color:#fff"><?= h($fest['title']) ?></div>
    <div style="font-size:.75rem;color:rgba(255,255,255,.55)"><?= count($entries) ?> entries · <?= $totalLikes ?> likes</div>
  </div>
  <?php if($isAdmin): ?>
  <button onclick="toggleFestVoting(<?= $fid ?>,this)" style="background:<?= $fest['voting_open']?'#b71c1c':'#2e7d32' ?>;color:#fff;border:none;border-radius:8px;padding:.35rem .7rem;font-size:.75rem;font-weight:700;cursor:pointer">
    <?= $fest['voting_open']?'🔒 Close':'🗳️ Open' ?>
  </button>
  <?php endif; ?>
  <button onclick="closeFestDetail()" style="background:rgba(255,255,255,.2);border:none;border-radius:50%;width:30px;height:30px;color:#fff;cursor:pointer;font-size:.9rem">✕</button>
</div>

<!-- Poster -->
<?php if($fest['poster_path']): ?>
<img src="<?= h(url('assets/uploads/fests/posters/'.basename($fest['poster_path']))) ?>" style="width:100%;max-height:220px;object-fit:cover;display:block">
<?php endif; ?>

<!-- Voting badge -->
<div style="text-align:center;padding:.4rem;font-size:.75rem;font-weight:700;letter-spacing:.06em;<?= $fest['voting_open']?'background:#e8f5e9;color:#2e7d32':'background:#ffebee;color:#b71c1c' ?>">
  <?php if($fest['voting_open']): ?>❤️ Liking is OPEN
  <?php elseif($fest['vote_start']&&$nowT<$fest['vote_start']): ?>⏳ Opens <?= date('d M, h:i A',strtotime($fest['vote_start'])) ?>
  <?php else: ?>🔒 Liking is CLOSED<?php endif; ?>
</div>

<!-- Prizes -->
<?php if($fest['prize_1']||$fest['prize_2']||$fest['prize_3']): ?>
<div style="background:linear-gradient(135deg,#fff8e1,#fff3e0);margin:.6rem;border-radius:12px;padding:.7rem .9rem;border:1.5px solid rgba(245,166,35,.25)">
  <div style="font-family:'Playfair Display',serif;font-size:.85rem;font-weight:700;color:#e65100;text-align:center;margin-bottom:.5rem">🏆 Prizes<?= $fest['sponsor_name']?' — Sponsored by '.$fest['sponsor_name']:'' ?></div>
  <?php
  $prizes=[['🥇',$fest['prize_1']],['🥈',$fest['prize_2']],['🥉',$fest['prize_3']]];
  $top3=array_slice($entries,0,3);
  foreach($prizes as $pi=>$pv): if(!$pv[1]) continue;
    $pw=$top3[$pi]??null;
  ?>
  <div style="display:flex;align-items:center;gap:.5rem;background:rgba(255,255,255,.6);border-radius:8px;padding:.35rem .6rem;margin-bottom:.25rem">
    <span style="font-size:1rem"><?= $pv[0] ?></span>
    <span style="font-size:.78rem;font-weight:600;color:#b45309;flex:1"><?= h($pv[1]) ?></span>
    <?php if($pw&&$pw['like_count']>0): ?>
    <span style="font-size:.75rem;color:#d97706;font-weight:700"><?= h($pw['member_name']) ?> · <?= $pw['like_count'] ?> ❤️</span>
    <?php else: ?><span style="font-size:.75rem;color:#666666">TBD</span><?php endif; ?>
  </div>
  <?php endforeach; ?>
</div>
<?php endif; ?>

<!-- My entry / Upload -->
<div style="background:#fff;margin:.6rem;border-radius:12px;border:1.5px solid #E3E7F5;overflow:hidden">
  <div style="background:linear-gradient(135deg,#0B1033,#0A14E0);padding:.6rem .9rem;font-family:'Bebas Neue',sans-serif;font-size:.95rem;letter-spacing:.08em;color:#fff">
    📸 <?= $myEntry?'MY ENTRY':'SUBMIT YOUR ENTRY' ?>
  </div>
  <div style="padding:.8rem">
    <?php if($uploadMsg): ?>
    <div style="padding:.5rem .8rem;border-radius:8px;margin-bottom:.6rem;font-size:.78rem;font-weight:600;<?= $uploadMsg[0]==='ok'?'background:#e8f5e9;color:#2e7d32':'background:#ffebee;color:#b71c1c' ?>"><?= $uploadMsg[1] ?></div>
    <?php endif; ?>
    <?php if($myEntry): ?>
    <img src="<?= h($SITE.'/assets/uploads/fests/'.$fid.'/'.basename($myEntry['image_path'])) ?>" style="width:100%;max-height:180px;object-fit:cover;border-radius:10px;margin-bottom:.5rem">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;color:#0B1033;text-align:center"><?= (int)$myEntry['like_count'] ?> <span style="font-size:.75rem;color:#64748b;font-family:'Plus Jakarta Sans',sans-serif">LIKES</span></div>
    <div style="display:flex;gap:.4rem;margin-top:.5rem">
      <button onclick="shareEntry(<?= $myEntry['id'] ?>,<?= $fid ?>,'<?= h(addslashes($me['name'])) ?>','<?= h(addslashes($fest['title'])) ?>','<?= $fest['sponsor_name']?h(addslashes($fest['sponsor_name'])):'' ?>')" style="flex:1;background:#25d366;color:#fff;border:none;border-radius:8px;padding:.5rem;font-weight:700;cursor:pointer;font-size:.78rem">💚 Share</button>
      <button onclick="deleteEntry(<?= $myEntry['id'] ?>,<?= $fid ?>)" style="background:#ffebee;color:#b71c1c;border:1px solid #ffcdd2;border-radius:8px;padding:.5rem .8rem;font-weight:700;cursor:pointer;font-size:.78rem">🗑️</button>
    </div>
    <?php else: ?>
    <form method="POST" enctype="multipart/form-data">
      <input type="text" name="entry_title" class="inp" placeholder="Title (optional)" style="margin-bottom:.5rem">
      <div onclick="document.getElementById('ep_<?= $fid ?>').click()" style="border:2px dashed rgba(11,16,51,.25);border-radius:10px;padding:1.2rem;text-align:center;cursor:pointer;background:#f8faff;margin-bottom:.5rem">
        <div id="ep_preview_<?= $fid ?>" style="display:none"><img id="ep_img_<?= $fid ?>" style="max-height:140px;border-radius:8px;max-width:100%"></div>
        <div id="ep_ph_<?= $fid ?>">📸 <strong>Tap to select photo</strong><br><small>Gallery or Camera</small></div>
      </div>
      <input type="file" id="ep_<?= $fid ?>" name="entry_photo" accept="image/*" style="display:none" onchange="previewEntryPhoto(this,<?= $fid ?>)">
      <button type="submit" style="width:100%;background:linear-gradient(135deg,#0B1033,#0A14E0);color:#fff;border:none;border-radius:10px;padding:.65rem;font-weight:700;cursor:pointer;font-size:.85rem">🎪 Submit Entry</button>
    </form>
    <?php endif; ?>
  </div>
</div>

<!-- Entries grid -->
<?php if(!empty($entries)): ?>
<div style="padding:.4rem .8rem .2rem;font-family:'Playfair Display',serif;font-size:.95rem;font-weight:700;color:#0B1033">🏆 All Entries</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem;padding:.4rem .8rem .8rem">
<?php foreach($entries as $rank=>$entry):
  $imgU=$SITE.'/assets/uploads/fests/'.$fid.'/'.basename($entry['image_path']);
  $isMine=$entry['member_id']==$uid;
  $isLiked=$myLikedId===(int)$entry['id'];
  $canLikeThis=$fest['voting_open']&&!$myLikedId&&!$isMine;
?>
<div style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.08);border:1.5px solid <?= $isLiked?'#e53935':($rank===0?'#f5a623':($rank===1?'#9e9e9e':($rank===2?'#cd7f32':'#E3E7F5'))) ?>;position:relative">
  <?php if($rank<3&&$entry['like_count']>0): ?>
  <div style="position:absolute;top:6px;left:6px;width:24px;height:24px;border-radius:50%;background:<?= ['#f5a623','#9e9e9e','#cd7f32'][$rank] ?>;display:flex;align-items:center;justify-content:center;font-size:.75rem;z-index:5;box-shadow:0 2px 6px rgba(0,0,0,.2)"><?= ['🥇','🥈','🥉'][$rank] ?></div>
  <?php endif; ?>
  <img src="<?= h($imgU) ?>" style="width:100%;aspect-ratio:3/4;object-fit:cover;display:block" loading="lazy">
  <div style="padding:.4rem .5rem .5rem">
    <div style="font-size:.75rem;font-weight:800;color:#0B1033;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><?= h($entry['member_name']) ?></div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-top:.2rem">
      <div><span style="font-family:'Bebas Neue',sans-serif;font-size:1rem;color:#e53935"><?= (int)$entry['like_count'] ?></span><span style="font-size:.75rem;color:#5d6b80;margin-left:2px">❤️</span></div>
      <?php if($isMine): ?>
      <button style="padding:.25rem .5rem;background:#f1f5f9;color:#64748b;border:none;border-radius:6px;font-size:.75rem;font-weight:700">Mine</button>
      <?php elseif($isLiked): ?>
      <button style="padding:.25rem .5rem;background:#fce4ec;color:#c62828;border:none;border-radius:6px;font-size:.75rem;font-weight:700">✅ Liked</button>
      <?php elseif($canLikeThis): ?>
      <button onclick="likeEntry(<?= $entry['id'] ?>,<?= $fid ?>,this)" style="padding:.25rem .55rem;background:linear-gradient(135deg,#e53935,#b71c1c);color:#fff;border:none;border-radius:6px;font-size:.75rem;font-weight:800;cursor:pointer">❤️ Like</button>
      <?php else: ?>
      <button style="padding:.25rem .5rem;background:#f5f5f5;color:#666666;border:none;border-radius:6px;font-size:.75rem">🔒</button>
      <?php endif; ?>
    </div>
  </div>
</div>
<?php endforeach; ?>
</div>
<?php else: ?>
<div style="text-align:center;padding:2rem;color:#5d6b80"><div style="font-size:2.5rem;margin-bottom:.5rem">🎪</div>No entries yet. Be first!</div>
<?php endif; ?>
</div>

<script>
var SITE='<?= $SITE ?>';
var CLUB='<?= h(addslashes($CLUB)) ?>';
var PLACE='<?= h(addslashes($PLACE)) ?>';
var SELF2='<?= url('modules/fest_detail.php') ?>';

function previewEntryPhoto(input,fid){
  if(!input.files||!input.files[0]) return;
  var r=new FileReader();
  r.onload=function(e){
    document.getElementById('ep_img_'+fid).src=e.target.result;
    document.getElementById('ep_preview_'+fid).style.display='block';
    document.getElementById('ep_ph_'+fid).style.display='none';
  };
  r.readAsDataURL(input.files[0]);
}

function likeEntry(eid,fid,btn){
  btn.disabled=true; btn.textContent='⏳';
  var fd=new FormData();
  fd.append('action','like'); fd.append('entry_id',eid); fd.append('fest_id',fid);
  fetch('<?= url('modules/fest_manager.php') ?>',{method:'POST',body:fd})
    .then(function(r){return r.json();})
    .then(function(res){
      if(res.ok){ location.reload(); }
      else { alert(res.msg); btn.disabled=false; btn.textContent='❤️ Like'; }
    });
}

function deleteEntry(eid,fid){
  if(!confirm('Delete your entry?')) return;
  var fd=new FormData();
  fd.append('action','delete_entry'); fd.append('entry_id',eid); fd.append('fest_id',fid);
  fetch('<?= url('modules/fest_manager.php') ?>',{method:'POST',body:fd})
    .then(function(r){return r.json();})
    .then(function(res){ if(res.ok) location.reload(); });
}

function toggleFestVoting(fid,btn){
  var fd=new FormData();
  fd.append('action','toggle_voting'); fd.append('fest_id',fid);
  fetch('<?= url('modules/fest_manager.php') ?>',{method:'POST',body:fd})
    .then(function(r){return r.json();})
    .then(function(res){
      if(res.ok){ location.reload(); }
    });
}

// Share entry — watermark with club name + fest name + sponsor
function shareEntry(eid,fid,name,festTitle,sponsorName){
  var canvas=document.createElement('canvas');
  var ctx=canvas.getContext('2d');

  // Load entry photo via fetch blob
  fetch(SITE+'/assets/uploads/fests/'+fid+'/og/entry_'+eid+'.jpg')
    .then(function(r){return r.blob();})
    .then(function(blob){
      var url2=URL.createObjectURL(blob);
      var img=new Image();
      img.onload=function(){
        canvas.width=img.width; canvas.height=img.height;
        var W=img.width,H=img.height;
        ctx.drawImage(img,0,0,W,H);
        URL.revokeObjectURL(url2);

        // Bottom watermark bar
        var barH=Math.round(H*0.10);
        var barY=H-barH;
        // Gradient bar
        var barGrad=ctx.createLinearGradient(0,barY,W,barY+barH);
        barGrad.addColorStop(0,'rgba(11,16,51,0.85)');
        barGrad.addColorStop(1,'rgba(10,20,224,0.85)');
        ctx.fillStyle=barGrad;
        ctx.fillRect(0,barY,W,barH);

        // Load logo
        var logo=new Image();
        logo.crossOrigin='anonymous';
        logo.onload=function(){
          var lS=Math.round(barH*0.72);
          var lX=Math.round(W*0.03);
          var lY=barY+(barH-lS)/2;
          // Logo in circle
          ctx.save();
          ctx.beginPath();ctx.arc(lX+lS/2,lY+lS/2,lS/2,0,Math.PI*2);ctx.clip();
          ctx.fillStyle='#fff';ctx.fillRect(lX,lY,lS,lS);
          ctx.drawImage(logo,lX,lY,lS,lS);
          ctx.restore();
          drawWatermarkText();
        };
        logo.onerror=function(){ drawWatermarkText(); };
        logo.src=SITE+'/assets/logo.png';

        function drawWatermarkText(){
          var tX=Math.round(W*0.16);
          var f1=Math.round(barH*0.36);
          var f2=Math.round(barH*0.25);
          ctx.font='bold '+f1+'px DM Sans,sans-serif';
          ctx.fillStyle='#fff'; ctx.textBaseline='middle';
          ctx.fillText(CLUB,tX,barY+barH*0.35);
          ctx.font=f2+'px DM Sans,sans-serif';
          ctx.fillStyle='rgba(255,255,255,0.75)';
          var sub='🌿 '+name+' · '+festTitle;
          if(sponsorName) sub+=' · 🏅 '+sponsorName;
          ctx.fillText(sub,tX,barY+barH*0.72);

          // Share
          canvas.toBlob(function(b){
            var file=new File([b],'fest_'+eid+'.jpg',{type:'image/jpeg'});
            var link=SITE+'/modules/fest_entry.php?id='+eid+'&fest='+fid;
            var msg='🎪 *'+festTitle+'*\n'
              +'🌿 Design by *'+name+'*\n'
              +'📍 '+PLACE+'\n'
              +'🏛️ '+CLUB+'\n\n'
              +'❤️ Like this entry!\n\n'
              +link;
            if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){
              navigator.share({files:[file],title:name+' — '+festTitle,text:msg});
            } else {
              var a=document.createElement('a');a.href=canvas.toDataURL('image/jpeg',0.92);
              a.download='fest_entry_'+eid+'.jpg';a.click();
              setTimeout(function(){window.open('https://wa.me/?text='+encodeURIComponent(msg),'_blank');},700);
            }
          },'image/jpeg',0.92);
        }
      };
      img.onerror=function(){URL.revokeObjectURL(url2);alert('Photo not found');};
      img.src=url2;
    }).catch(function(){ alert('Could not load photo'); });
}
</script>
