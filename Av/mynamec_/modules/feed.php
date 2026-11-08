<?php
// ============================================================
// modules/feed.php — Member Social Feed (Facebook/Instagram style)
// Aishwarya Arts & Sports Club — PHP 7.3+ compatible
// Posts (photo/video/link) · Likes · Comments · Auto-reload
// ============================================================
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/upload_helper.php';
$me      = currentUser();              // null for guests
$isGuest = !$me;
$isAdmin = $me ? isAdminRole($me['role']) : false;
$uid     = $me ? (int)$me['id'] : 0;
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$PLACE   = setting('CLUB_PLACE','Vettikkattiri, Malappuram · Kerala');
$pageTitle = 'Community Feed — '.$CLUB;

// ── Reusable: let other modules push a post into the feed ───
// Safe to call from anywhere AFTER config.php is loaded.
if (!function_exists('feed_add_market_post')) {
    function feed_add_market_post($itemId){
        try {
            // Avoid duplicates: one feed post per market item
            db()->exec("CREATE TABLE IF NOT EXISTS feed_posts (
                id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, body TEXT DEFAULT NULL,
                media_type ENUM('none','image','video','link','market') DEFAULT 'none',
                media_url VARCHAR(700) DEFAULT NULL, link_url VARCHAR(700) DEFAULT NULL,
                link_title VARCHAR(300) DEFAULT NULL, link_thumb VARCHAR(700) DEFAULT NULL,
                ref_type VARCHAR(30) DEFAULT NULL, ref_id INT DEFAULT NULL,
                status ENUM('active','hidden') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user (user_id), INDEX idx_status (status), INDEX idx_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            // add columns if table predates this
            try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_type VARCHAR(30) DEFAULT NULL"); } catch(Exception $e){}
            try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_id INT DEFAULT NULL"); } catch(Exception $e){}
            try { db()->exec("ALTER TABLE feed_posts MODIFY media_type ENUM('none','image','video','link','market') DEFAULT 'none'"); } catch(Exception $e){}

            $dup = db()->prepare("SELECT id FROM feed_posts WHERE ref_type='market' AND ref_id=?");
            $dup->execute([$itemId]);
            if ($dup->fetch()) return false; // already posted

            $it = db()->prepare("SELECT m.*, (SELECT image_path FROM market_images WHERE item_id=m.id ORDER BY sort_order LIMIT 1) AS thumb
                                 FROM market_items m WHERE m.id=? AND m.status='active'");
            $it->execute([$itemId]);
            $row = $it->fetch();
            if (!$row) return false;

            $thumb = $row['thumb'] ? rtrim(SITE_URL,'/').'/assets/uploads/market/'.$row['thumb'] : '';
            $price = trim((string)$row['price']);
            $body  = '🏪 New in AV Market: '.$row['title']
                   . ($price !== '' ? ' — ₹'.$price : '')
                   . (!empty($row['description']) ? "\n".mb_substr($row['description'],0,140) : '');
            $linkUrl = rtrim(SITE_URL,'/').'/modules/market.php?view=item&id='.$itemId;

            db()->prepare("INSERT INTO feed_posts(user_id,body,media_type,media_url,link_url,link_title,link_thumb,ref_type,ref_id)
                           VALUES(?,?,?,?,?,?,?,?,?)")
               ->execute([(int)$row['user_id'], $body, 'market', '', $linkUrl, $row['title'], $thumb, 'market', $itemId]);
            return true;
        } catch (Exception $e) { return false; }
    }
}

// ── DB Setup ────────────────────────────────────────────────
try {
    db()->exec("CREATE TABLE IF NOT EXISTS feed_posts (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        user_id     INT NOT NULL,
        body        TEXT DEFAULT NULL,
        media_type  ENUM('none','image','video','link','market') DEFAULT 'none',
        media_url   VARCHAR(700) DEFAULT NULL,
        link_url    VARCHAR(700) DEFAULT NULL,
        link_title  VARCHAR(300) DEFAULT NULL,
        link_thumb  VARCHAR(700) DEFAULT NULL,
        ref_type    VARCHAR(30) DEFAULT NULL,
        ref_id      INT DEFAULT NULL,
        status      ENUM('active','hidden') DEFAULT 'active',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user (user_id),
        INDEX idx_status (status),
        INDEX idx_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_type VARCHAR(30) DEFAULT NULL"); } catch(Exception $e){}
    try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_id INT DEFAULT NULL"); } catch(Exception $e){}
    try { db()->exec("ALTER TABLE feed_posts ADD COLUMN thumb_url VARCHAR(700) DEFAULT NULL"); } catch(Exception $e){}
    try { db()->exec("ALTER TABLE feed_posts ADD COLUMN pinned TINYINT(1) DEFAULT 0"); } catch(Exception $e){}
    try { db()->exec("ALTER TABLE feed_posts MODIFY media_type ENUM('none','image','video','videofile','link','market') DEFAULT 'none'"); } catch(Exception $e){}
    db()->exec("CREATE TABLE IF NOT EXISTS feed_likes (
        id       INT AUTO_INCREMENT PRIMARY KEY,
        post_id  INT NOT NULL,
        user_id  INT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_like (post_id,user_id),
        INDEX idx_post (post_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    db()->exec("CREATE TABLE IF NOT EXISTS feed_comments (
        id       INT AUTO_INCREMENT PRIMARY KEY,
        post_id  INT NOT NULL,
        user_id  INT NOT NULL,
        body     TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_post (post_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (Exception $e) {}

// ── Auto-cleanup: delete feed posts older than 6 months ──────
// Protects pinned posts and market-linked posts. Runs at most once
// per day (tracked via a tiny settings flag) so it's lightweight.
try {
    $FEED_KEEP_MONTHS = 6;  // change this number to keep posts longer/shorter
    db()->exec("CREATE TABLE IF NOT EXISTS feed_meta (k VARCHAR(50) PRIMARY KEY, v VARCHAR(100)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $lastRun = db()->query("SELECT v FROM feed_meta WHERE k='last_cleanup'")->fetchColumn();
    $today = date('Y-m-d');
    if ($lastRun !== $today) {
        // Find old posts (not pinned, not market) to remove
        $old = db()->prepare("SELECT id, media_url, thumb_url FROM feed_posts
            WHERE created_at < DATE_SUB(NOW(), INTERVAL ? MONTH)
              AND pinned = 0
              AND (ref_type IS NULL OR ref_type <> 'market')");
        $old->execute([$FEED_KEEP_MONTHS]);
        $oldRows = $old->fetchAll();
        foreach ($oldRows as $op) {
            // delete the image / thumbnail files from disk
            foreach (['media_url','thumb_url'] as $f) {
                if (!empty($op[$f])) {
                    $fp = __DIR__.'/../assets/uploads/'.$op[$f];
                    if (is_file($fp)) @unlink($fp);
                }
            }
            $pid = (int)$op['id'];
            db()->prepare("DELETE FROM feed_posts WHERE id=?")->execute([$pid]);
            db()->prepare("DELETE FROM feed_likes WHERE post_id=?")->execute([$pid]);
            db()->prepare("DELETE FROM feed_comments WHERE post_id=?")->execute([$pid]);
        }
        // mark as run today
        db()->prepare("INSERT INTO feed_meta(k,v) VALUES('last_cleanup',?)
                       ON DUPLICATE KEY UPDATE v=?")->execute([$today,$today]);
    }
} catch (Exception $e) {}

// ── Helpers ─────────────────────────────────────────────────
function feed_time_ago($ts){
    $t = strtotime($ts); $d = time()-$t;
    if($d<60) return 'just now';
    if($d<3600) return floor($d/60).'m';
    if($d<86400) return floor($d/3600).'h';
    if($d<604800) return floor($d/86400).'d';
    return date('M j', $t);
}
// Extract a YouTube/Vimeo video ID and build a thumbnail
function feed_video_info($url){
    $url = trim($url);
    // YouTube — covers watch, youtu.be, embed, shorts, live, ?v= anywhere
    if (preg_match('~(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})~', $url, $m)) {
        $id = $m[1];
        return ['type'=>'youtube','id'=>$id,
                'thumb'=>'https://i.ytimg.com/vi/'.$id.'/hqdefault.jpg',
                'embed'=>'https://www.youtube.com/embed/'.$id];
    }
    // Vimeo — fetch real thumbnail via oEmbed (best effort)
    if (preg_match('~vimeo\.com/(?:video/)?(\d+)~', $url, $m)) {
        $vid = $m[1]; $thumb = '';
        $oe = @file_get_contents('https://vimeo.com/api/oembed.json?url='.urlencode('https://vimeo.com/'.$vid));
        if ($oe) { $j = json_decode($oe, true); if (!empty($j['thumbnail_url'])) $thumb = $j['thumbnail_url']; }
        return ['type'=>'vimeo','id'=>$vid,'thumb'=>$thumb,'embed'=>'https://player.vimeo.com/video/'.$vid];
    }
    // Instagram reel/post — branded card (no public thumbnail without API token)
    if (preg_match('~instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)~', $url, $m)) {
        return ['type'=>'instagram','id'=>$m[1],'thumb'=>'','embed'=>rtrim($url,'/').'/embed'];
    }
    // Facebook video / watch / reel — branded card + embed player
    if (preg_match('~(?:facebook\.com|fb\.watch|fb\.com)/~', $url)) {
        $embed = 'https://www.facebook.com/plugins/video.php?href='.urlencode($url).'&show_text=false';
        return ['type'=>'facebook','id'=>'','thumb'=>'','embed'=>$embed];
    }
    return null;
}

// ── AJAX ────────────────────────────────────────────────────
$_AJ = array_merge($_GET, $_POST);
if (!empty($_AJ['ax'])) {
    header('Content-Type: application/json');
    $ax  = trim($_AJ['ax']);
    $get = function($k,$d='') use ($_AJ){ return isset($_AJ[$k]) ? trim((string)$_AJ[$k]) : $d; };

    // Write actions require login — guests can only read (fetch, comments, check_new)
    $writeActions = ['post','like','comment','del_comment','del_post','pin'];
    if (in_array($ax, $writeActions, true) && $isGuest) {
        echo json_encode(['ok'=>false,'guest'=>true,'msg'=>'Please log in to do that.']); exit;
    }

    // ── CREATE POST ──
    if ($ax === 'post') {
        $body = $get('body');
        $mediaType = 'none'; $mediaUrl = null;
        $linkUrl = null; $linkTitle = null; $linkThumb = null; $thumbUrl = null;

        // ── Daily image limit: max 2 image posts per member per day ──
        $DAILY_IMAGE_LIMIT = 2;
        $bringingImage = (!empty($_FILES['image']['name']) && $_FILES['image']['error']===0)
                       || (!empty($_POST['image_b64']) && strpos($_POST['image_b64'],'data:image')===0);
        if ($bringingImage) {
            $cntSt = db()->prepare("SELECT COUNT(*) FROM feed_posts
                WHERE user_id=? AND media_type='image' AND DATE(created_at)=CURDATE()");
            $cntSt->execute([$uid]);
            $todayImgs = (int)$cntSt->fetchColumn();
            if ($todayImgs >= $DAILY_IMAGE_LIMIT) {
                echo json_encode(['ok'=>false,'msg'=>'Daily limit reached: you can post '.$DAILY_IMAGE_LIMIT.' images per day. Try text or a video link, or post more tomorrow.']);
                exit;
            }
        }

        $dir = __DIR__.'/../assets/uploads/feed/';
        if (!is_dir($dir)) mkdir($dir, 0755, true);

        // ── VIDEO FILE upload (Instagram/Facebook style) ──
        // Browser sends the video file + a base64 thumbnail (first frame)
        if (!empty($_FILES['video']['name']) && $_FILES['video']['error']===0) {
            $vext = strtolower(pathinfo($_FILES['video']['name'], PATHINFO_EXTENSION));
            if (in_array($vext, ['mp4','webm','mov','m4v','ogg']) && $_FILES['video']['size'] <= 50*1024*1024) {
                $vfn = 'feedvid_'.time().'_'.mt_rand(1000,9999).'.'.$vext;
                if (move_uploaded_file($_FILES['video']['tmp_name'], $dir.$vfn)) {
                    $mediaType = 'videofile';
                    $mediaUrl  = 'feed/'.$vfn;
                    // Save the generated thumbnail
                    if (!empty($_POST['thumb_b64']) && strpos($_POST['thumb_b64'],'data:image')===0) {
                        $tb = base64_decode(substr($_POST['thumb_b64'], strpos($_POST['thumb_b64'],',')+1));
                        if ($tb) {
                            $tfn = 'feedthumb_'.time().'_'.mt_rand(1000,9999).'.jpg';
                            if (file_put_contents($dir.$tfn, $tb) !== false) $thumbUrl = 'feed/'.$tfn;
                        }
                    }
                }
            } else {
                echo json_encode(['ok'=>false,'msg'=>'Video must be mp4/webm/mov and under 50MB.']); exit;
            }
        }

        // ── Image upload (multipart) OR base64 (resized client-side) ──
        if ($mediaType==='none') {
            $photo = handlePhotoUpload('image', 'feed');
            if (!$photo && !empty($_POST['image_b64'])) {
                $b64 = trim($_POST['image_b64']);
                if (strpos($b64,'data:image') === 0) {
                    $imgd = base64_decode(substr($b64, strpos($b64,',')+1));
                    if ($imgd && strlen($imgd) < 6*1024*1024) {
                        $fn  = 'feed_'.time().'_'.mt_rand(1000,9999).'.jpg';
                        if (file_put_contents($dir.$fn, $imgd) !== false) $photo = 'feed/'.$fn;
                    }
                }
            }
            if ($photo) { $mediaType='image'; $mediaUrl=$photo; }
        }

        // ── Video / link (YouTube, Vimeo, or generic) ──
        if ($mediaType==='none') {
            $vurl = $get('video_url');
            if ($vurl) {
                $vi = feed_video_info($vurl);
                if ($vi) {
                    $mediaType='video'; $linkUrl=$vurl; $linkThumb=$vi['thumb'];
                    $linkTitle = $get('link_title');
                    // If platform gave no thumbnail but browser captured one, use it
                    if (!$linkThumb && !empty($_POST['thumb_b64']) && strpos($_POST['thumb_b64'],'data:image')===0) {
                        $tb = base64_decode(substr($_POST['thumb_b64'], strpos($_POST['thumb_b64'],',')+1));
                        if ($tb) { $tfn='feedthumb_'.time().'_'.mt_rand(1000,9999).'.jpg';
                            if (file_put_contents($dir.$tfn,$tb)!==false){ $thumbUrl='feed/'.$tfn; } }
                    }
                } else {
                    $mediaType='link'; $linkUrl=$vurl; $linkTitle=$get('link_title');
                }
            }
        }

        if ($body==='' && $mediaType==='none') { echo json_encode(['ok'=>false,'msg'=>'Write something or add media.']); exit; }

        db()->prepare("INSERT INTO feed_posts(user_id,body,media_type,media_url,link_url,link_title,link_thumb,thumb_url) VALUES(?,?,?,?,?,?,?,?)")
           ->execute([$uid,$body,$mediaType,$mediaUrl,$linkUrl,$linkTitle,$linkThumb,$thumbUrl]);
        echo json_encode(['ok'=>true,'id'=>(int)db()->lastInsertId(),'msg'=>'Posted!']); exit;
    }

    // ── TOGGLE LIKE ──
    if ($ax === 'like') {
        $pid = (int)$get('post_id');
        $ex = db()->prepare("SELECT id FROM feed_likes WHERE post_id=? AND user_id=?");
        $ex->execute([$pid,$uid]);
        if ($ex->fetch()) {
            db()->prepare("DELETE FROM feed_likes WHERE post_id=? AND user_id=?")->execute([$pid,$uid]);
            $liked = false;
        } else {
            db()->prepare("INSERT IGNORE INTO feed_likes(post_id,user_id) VALUES(?,?)")->execute([$pid,$uid]);
            $liked = true;
        }
        $c = db()->prepare("SELECT COUNT(*) FROM feed_likes WHERE post_id=?"); $c->execute([$pid]);
        echo json_encode(['ok'=>true,'liked'=>$liked,'count'=>(int)$c->fetchColumn()]); exit;
    }

    // ── ADD COMMENT ──
    if ($ax === 'comment') {
        $pid = (int)$get('post_id'); $cb = $get('body');
        if ($cb==='') { echo json_encode(['ok'=>false,'msg'=>'Empty comment']); exit; }
        db()->prepare("INSERT INTO feed_comments(post_id,user_id,body) VALUES(?,?,?)")->execute([$pid,$uid,$cb]);
        $cid = (int)db()->lastInsertId();
        $c = db()->prepare("SELECT COUNT(*) FROM feed_comments WHERE post_id=?"); $c->execute([$pid]);
        echo json_encode(['ok'=>true,'id'=>$cid,'count'=>(int)$c->fetchColumn(),
            'author'=>$me['name'],'photo'=>($me['profile_photo']?getMemberPhoto($me['profile_photo']):''),
            'body'=>$cb,'ago'=>'just now']); exit;
    }

    // ── LOAD COMMENTS ──
    if ($ax === 'comments') {
        $pid = (int)$get('post_id');
        $st = db()->prepare("SELECT c.*,u.name author,u.profile_photo uphoto FROM feed_comments c
            JOIN users u ON u.id=c.user_id WHERE c.post_id=? ORDER BY c.created_at ASC");
        $st->execute([$pid]); $rows=$st->fetchAll();
        $out=[];
        foreach($rows as $r){
            $out[]=['id'=>(int)$r['id'],'author'=>$r['author'],
                'photo'=>($r['uphoto']?getMemberPhoto($r['uphoto']):''),
                'body'=>$r['body'],'ago'=>feed_time_ago($r['created_at']),
                'mine'=>((int)$r['user_id']===$uid || $isAdmin)];
        }
        echo json_encode(['ok'=>true,'comments'=>$out]); exit;
    }

    // ── DELETE COMMENT ──
    if ($ax === 'del_comment') {
        $cid=(int)$get('id');
        $r=db()->prepare("SELECT user_id FROM feed_comments WHERE id=?"); $r->execute([$cid]); $r=$r->fetch();
        if($r && ((int)$r['user_id']===$uid || $isAdmin)){
            db()->prepare("DELETE FROM feed_comments WHERE id=?")->execute([$cid]);
            echo json_encode(['ok'=>true]); exit;
        }
        echo json_encode(['ok'=>false,'msg'=>'Not allowed']); exit;
    }

    // ── DELETE POST ──
    if ($ax === 'del_post') {
        $pid=(int)$get('id');
        $r=db()->prepare("SELECT user_id,media_url FROM feed_posts WHERE id=?"); $r->execute([$pid]); $r=$r->fetch();
        if($r && ((int)$r['user_id']===$uid || $isAdmin)){
            if($r['media_url']){ $fp=__DIR__.'/../assets/uploads/'.$r['media_url']; if(file_exists($fp)) @unlink($fp); }
            db()->prepare("DELETE FROM feed_posts WHERE id=?")->execute([$pid]);
            db()->prepare("DELETE FROM feed_likes WHERE post_id=?")->execute([$pid]);
            db()->prepare("DELETE FROM feed_comments WHERE post_id=?")->execute([$pid]);
            echo json_encode(['ok'=>true]); exit;
        }
        echo json_encode(['ok'=>false,'msg'=>'Not allowed']); exit;
    }

    // ── PIN / UNPIN (admin only) ──
    if ($ax === 'pin') {
        if (!$isAdmin) { echo json_encode(['ok'=>false,'msg'=>'Admins only']); exit; }
        $pid=(int)$get('id');
        $r=db()->prepare("SELECT pinned FROM feed_posts WHERE id=?"); $r->execute([$pid]); $r=$r->fetch();
        if(!$r){ echo json_encode(['ok'=>false,'msg'=>'Not found']); exit; }
        $new = $r['pinned'] ? 0 : 1;
        db()->prepare("UPDATE feed_posts SET pinned=? WHERE id=?")->execute([$new,$pid]);
        echo json_encode(['ok'=>true,'pinned'=>(bool)$new]); exit;
    }
    if ($ax === 'fetch') {
        $before = (int)$get('before', 0); // post id cursor; 0 = newest
        $q      = $get('q', '');           // search query
        $limit  = 8;
        $pr = [];
        $pinnedPosts = [];
        // Pinned-first only on the first page AND when not searching
        if ($before == 0 && $q === '') {
            $pinSt = db()->prepare("SELECT p.*, u.name author, u.profile_photo uphoto, u.role urole,
                (SELECT COUNT(*) FROM feed_likes l WHERE l.post_id=p.id) likes,
                (SELECT COUNT(*) FROM feed_comments c WHERE c.post_id=p.id) comments,
                (SELECT COUNT(*) FROM feed_likes l WHERE l.post_id=p.id AND l.user_id=?) liked
                FROM feed_posts p JOIN users u ON u.id=p.user_id
                WHERE p.status='active' AND p.pinned=1 ORDER BY p.id DESC");
            $pinSt->execute([$uid]);
            $pinnedPosts = $pinSt->fetchAll();
        }
        $wh = "p.status='active'";
        if ($q === '') { $wh .= " AND p.pinned=0"; }   // when searching, include pinned in normal results
        if ($before > 0) { $wh .= " AND p.id < ?"; $pr[] = $before; }
        if ($q !== '') {
            $wh .= " AND (p.body LIKE ? OR u.name LIKE ? OR p.link_title LIKE ?)";
            $like = '%'.$q.'%';
            $pr[] = $like; $pr[] = $like; $pr[] = $like;
        }
        $sql = "SELECT p.*, u.name author, u.profile_photo uphoto, u.role urole,
                (SELECT COUNT(*) FROM feed_likes l WHERE l.post_id=p.id) likes,
                (SELECT COUNT(*) FROM feed_comments c WHERE c.post_id=p.id) comments,
                (SELECT COUNT(*) FROM feed_likes l WHERE l.post_id=p.id AND l.user_id=?) liked
                FROM feed_posts p JOIN users u ON u.id=p.user_id
                WHERE $wh ORDER BY p.id DESC LIMIT $limit";
        $st = db()->prepare($sql);
        $st->execute(array_merge([$uid], $pr));
        $rows = array_merge($pinnedPosts, $st->fetchAll());
        $posts = [];
        foreach($rows as $r){
            $posts[] = [
                'id'=>(int)$r['id'],
                'author'=>$r['author'],
                'role'=>$r['urole'],
                'photo'=>($r['uphoto']?getMemberPhoto($r['uphoto']):''),
                'body'=>$r['body'],
                'media_type'=>$r['media_type'],
                'media_url'=>($r['media_url']?photoUrl($r['media_url']):''),
                'thumb_url'=>(!empty($r['thumb_url'])?photoUrl($r['thumb_url']):''),
                'link_url'=>$r['link_url'],
                'link_title'=>$r['link_title'],
                'link_thumb'=>$r['link_thumb'],
                'likes'=>(int)$r['likes'],
                'comments'=>(int)$r['comments'],
                'liked'=>((int)$r['liked']>0),
                'pinned'=>((int)$r['pinned']>0),
                'ago'=>feed_time_ago($r['created_at']),
                'mine'=>((int)$r['user_id']===$uid || $isAdmin)
            ];
        }
        // has_more is based only on the non-pinned page fetch
        $nonPinnedCount = count($rows) - count($pinnedPosts);
        // newest id (for the auto-poll "any new posts?" check)
        $newest = db()->query("SELECT MAX(id) FROM feed_posts WHERE status='active'")->fetchColumn();
        echo json_encode(['ok'=>true,'posts'=>$posts,'newest'=>(int)$newest,'has_more'=>$nonPinnedCount===$limit]); exit;
    }

    // ── CHECK NEW (lightweight poll) ──
    if ($ax === 'check_new') {
        $since = (int)$get('since',0);
        $c = db()->prepare("SELECT COUNT(*) FROM feed_posts WHERE status='active' AND id>?");
        $c->execute([$since]);
        echo json_encode(['ok'=>true,'new'=>(int)$c->fetchColumn()]); exit;
    }

    echo json_encode(['ok'=>false,'msg'=>'Unknown action']); exit;
}

$MY_PHOTO = ($me && $me['profile_photo']) ? getMemberPhoto($me['profile_photo']) : '';

// ── Rich link preview when sharing a specific post (?post=ID) ──
$sharePostId = (int)($_GET['post'] ?? 0);
if ($sharePostId > 0) {
    try {
        $sp = db()->prepare("SELECT p.*, u.name author FROM feed_posts p JOIN users u ON u.id=p.user_id
                             WHERE p.id=? AND p.status='active'");
        $sp->execute([$sharePostId]);
        $spr = $sp->fetch();
        if ($spr) {
            $snippet = trim((string)$spr['body']);
            if ($snippet === '') $snippet = 'Shared a post on the community feed';
            if (mb_strlen($snippet) > 160) $snippet = mb_substr($snippet,0,157).'…';
            // pick preview image: post image, then thumbnail, then link thumb, then logo
            $ogImg = '';
            if (!empty($spr['media_url']))      $ogImg = rtrim(SITE_URL,'/').'/assets/uploads/'.$spr['media_url'];
            elseif (!empty($spr['thumb_url']))  $ogImg = rtrim(SITE_URL,'/').'/assets/uploads/'.$spr['thumb_url'];
            elseif (!empty($spr['link_thumb'])) $ogImg = $spr['link_thumb'];
            else                                $ogImg = 'https://mynamecc.online/assets/logo.jpg';
            $pageTitle = $spr['author'].' · '.$CLUB;
            $pageOG = [
                'title' => $spr['author'].' on '.$CLUB.' Feed',
                'desc'  => $snippet,
                'image' => $ogImg,
                'url'   => rtrim(SITE_URL,'/').'/modules/feed.php?post='.$sharePostId,
            ];
        }
    } catch (Exception $e) {}
}
require_once __DIR__.'/../includes/header.php';
?>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">

<style>
.fd{max-width:600px;margin:0 auto;padding-bottom:80px;font-family:'Nunito','DM Sans',sans-serif}

/* Header */
.fd-bar{background:linear-gradient(135deg,#1a237e,#1A23C9 70%);padding:.6rem .9rem;display:flex;align-items:center;gap:.6rem;border-bottom:2px solid #ffc107;position:sticky;top:0;z-index:500}
.fd-back{width:34px;height:34px;background:rgba(255,255,255,.15);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;border:none;text-decoration:none;flex-shrink:0;font-size:.85rem}
.fd-bar h1{flex:1;font-size:1rem;font-weight:900;color:#fff;margin:0;line-height:1.1}
.fd-bar p{font-size:.75rem;color:rgba(255,255,255,.7);margin:0}
.fd-search-btn{width:34px;height:34px;background:rgba(255,255,255,.15);border-radius:50%;border:none;color:#fff;cursor:pointer;font-size:.85rem;flex-shrink:0}
.fd-searchbar{display:none;align-items:center;gap:.5rem;background:#fff;padding:.5rem .8rem;border-bottom:1px solid #eceff4;position:sticky;top:52px;z-index:490}
.fd-searchbar.on{display:flex}
.fd-search-ic{color:#546e7a;font-size:.85rem}
.fd-searchbar input{flex:1;border:none;background:#f1f3f6;border-radius:20px;padding:.55rem .9rem;font-family:inherit;font-size:.88rem;outline:none}
.fd-search-clear{background:none;border:none;color:#546e7a;font-size:1rem;cursor:pointer;flex-shrink:0}
.fd-search-info{text-align:center;padding:.6rem;font-size:.78rem;color:#546e7a;font-weight:700}

/* Composer */
.fd-comp{background:#fff;margin:.7rem;border-radius:16px;box-shadow:0 2px 12px rgba(26,35,126,.08);overflow:hidden}
.fd-comp-top{display:flex;gap:.6rem;padding:.85rem .9rem .5rem;align-items:flex-start}
.fd-av{width:42px;height:42px;border-radius:50%;object-fit:cover;flex-shrink:0;background:#ECEEFF;display:flex;align-items:center;justify-content:center;font-weight:900;color:#1A23C9;font-size:1rem}
.fd-comp textarea{flex:1;border:none;outline:none;resize:none;font-family:inherit;font-size:.95rem;color:#1a237e;min-height:46px;padding-top:.5rem;background:none}
.fd-prev{position:relative;margin:0 .9rem;border-radius:12px;overflow:hidden;display:none}
.fd-prev img{width:100%;display:block;max-height:340px;object-fit:cover}
.fd-prev .fd-prev-x{position:absolute;top:8px;right:8px;width:30px;height:30px;border-radius:50%;background:rgba(0,0,0,.6);color:#fff;border:none;cursor:pointer;font-size:1rem}
.fd-link-prev{margin:.5rem .9rem;border:1px solid #e3e7ff;border-radius:12px;overflow:hidden;display:none;background:#f8f9ff}
.fd-link-prev img{width:100%;max-height:200px;object-fit:cover;display:block}
.fd-link-prev .lp-meta{padding:.5rem .7rem;font-size:.78rem;color:#546e7a}
.fd-video-input{display:none;margin:.4rem .9rem}
.fd-video-input input{width:100%;padding:.6rem .8rem;border:2px solid #e3e7ff;border-radius:10px;font-family:inherit;font-size:.85rem;outline:none}
.fd-comp-actions{display:flex;align-items:center;gap:.3rem;padding:.5rem .7rem;border-top:1px solid #f0f2fa;flex-wrap:wrap}
.fd-act-btn{display:flex;align-items:center;gap:.35rem;padding:.45rem .7rem;border:none;background:none;border-radius:9px;cursor:pointer;font-family:inherit;font-size:.78rem;font-weight:800;color:#546e7a;transition:background .15s}
.fd-act-btn:active{background:#eceff1}
.fd-act-btn.ph{color:#2e7d32}
.fd-act-btn.vid{color:#c62828}
.fd-post-btn{margin-left:auto;padding:.5rem 1.3rem;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;border:none;border-radius:10px;font-family:inherit;font-weight:800;font-size:.85rem;cursor:pointer}
.fd-post-btn:disabled{opacity:.5}

/* New posts pill */
.fd-newpill{position:fixed;top:108px;left:50%;transform:translateX(-50%) translateY(-12px);z-index:600;background:#1A23C9;color:#fff;border:none;border-radius:22px;padding:.5rem 1.1rem;font-family:inherit;font-weight:800;font-size:.82rem;cursor:pointer;box-shadow:0 5px 18px rgba(26,35,201,.4);opacity:0;transition:all .25s;pointer-events:none}
.fd-newpill.on{opacity:1;transform:translateX(-50%) translateY(0);pointer-events:auto}

/* Post card */
.fd-post{background:#fff;margin:.7rem;border-radius:16px;box-shadow:0 2px 12px rgba(26,35,126,.07);overflow:hidden;animation:fdIn .3s ease}
@keyframes fdIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.fd-ph{display:flex;align-items:center;gap:.6rem;padding:.8rem .9rem .5rem}
.fd-ph .fd-meta{flex:1;min-width:0}
.fd-ph .fd-name{font-size:.92rem;font-weight:800;color:#1a237e;line-height:1.1}
.fd-ph .fd-sub{font-size:.75rem;color:#546e7a}
.fd-badge{font-size:.75rem;font-weight:800;color:#1A23C9;background:#ECEEFF;padding:.1rem .4rem;border-radius:6px;text-transform:uppercase;letter-spacing:.04em;margin-left:.3rem}
.fd-menu{background:none;border:none;color:#546e7a;font-size:1.2rem;cursor:pointer;padding:.2rem .5rem;flex-shrink:0}
.fd-menu-wrap{position:relative;flex-shrink:0}
.fd-menu-drop{display:none;position:absolute;top:100%;right:0;background:#fff;border-radius:10px;box-shadow:0 6px 22px rgba(0,0,0,.16);border:1px solid #eceff4;min-width:150px;z-index:50;overflow:hidden}
.fd-menu-drop.on{display:block}
.fd-menu-drop button{display:block;width:100%;text-align:left;border:none;background:none;padding:.6rem .9rem;font-family:inherit;font-size:.82rem;font-weight:700;color:#37474f;cursor:pointer}
.fd-menu-drop button:active{background:#f0f2fa}
.fd-pinned{border:1.5px solid #ffd54f;box-shadow:0 2px 14px rgba(255,193,7,.18)}
.fd-pin-strip{padding:.4rem .9rem 0}
.fd-pin-badge{font-size:.75rem;font-weight:800;color:#e65100;background:#fff8e1;padding:.18rem .5rem;border-radius:8px;letter-spacing:.03em}
.fd-body{padding:0 .9rem .6rem;font-size:.92rem;color:#37474f;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.fd-media img{width:100%;display:block;max-height:520px;object-fit:cover}
.fd-video{position:relative;width:100%;background:#000;cursor:pointer}
.fd-video img{width:100%;display:block;max-height:420px;object-fit:cover;opacity:.92}
.fd-video .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.fd-video .play span{width:62px;height:62px;border-radius:50%;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;font-size:1.6rem}
.fd-video iframe{width:100%;aspect-ratio:16/9;border:none;display:block}
.fd-linkcard{margin:0 .9rem .6rem;border:1px solid #e3e7ff;border-radius:12px;overflow:hidden;text-decoration:none;display:block;background:#f8f9ff}
.fd-linkcard img{width:100%;max-height:220px;object-fit:cover;display:block}
.fd-linkcard .lc-t{padding:.55rem .75rem;font-size:.82rem;font-weight:700;color:#1A23C9;word-break:break-word}
.fd-linkcard.fd-market{border-color:#a5d6a7;background:#f1f8e9}
.fd-linkcard.fd-market .lc-t{color:#1b5e20}
.fd-linkcard.fd-vidlink .fd-vidlink-ph{height:160px;background:linear-gradient(135deg,#37474f,#1a237e);display:flex;align-items:center;justify-content:center}
.fd-linkcard.fd-vidlink .fd-vidlink-ph span{width:58px;height:58px;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:1.5rem;color:#fff}

/* Instagram / Facebook branded video posters */
.fd-ig,.fd-fb{display:block;position:relative;min-height:200px;text-decoration:none;overflow:hidden}
.fd-ig img,.fd-fb img{width:100%;display:block;max-height:420px;object-fit:cover}
.fd-brand-ov{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.4rem}
.fd-ig .fd-brand-ov{background:linear-gradient(135deg,#feda75,#fa7e1e,#d62976,#962fbf,#4f5bd5)}
.fd-fb .fd-brand-ov{background:linear-gradient(135deg,#1877f2,#0a3d91)}
.fd-ig img + .fd-brand-ov,.fd-fb img + .fd-brand-ov{background:rgba(0,0,0,.32)}
.fd-brand-logo{width:54px;height:54px;border-radius:16px;background:rgba(255,255,255,.95);display:flex;align-items:center;justify-content:center;font-size:1.8rem;font-weight:900;color:#d62976;box-shadow:0 3px 12px rgba(0,0,0,.25)}
.fd-fb .fd-brand-logo{color:#1877f2;font-family:Georgia,serif}
.fd-brand-name{color:#fff;font-weight:800;font-size:.9rem;text-shadow:0 1px 4px rgba(0,0,0,.4)}
.fd-ig .play,.fd-fb .play{position:static;display:flex}
.fd-ig .play span,.fd-fb .play span{width:50px;height:50px;border-radius:50%;background:rgba(255,255,255,.25);border:2px solid rgba(255,255,255,.7);display:flex;align-items:center;justify-content:center;font-size:1.3rem;color:#fff;margin-top:.2rem}
.fd-stat{display:flex;align-items:center;justify-content:space-between;padding:.4rem .95rem;font-size:.75rem;color:#546e7a}
.fd-actions{display:flex;border-top:1px solid #f0f2fa;border-bottom:1px solid #f0f2fa}
.fd-a{flex:1;display:flex;align-items:center;justify-content:center;gap:.4rem;padding:.6rem;border:none;background:none;cursor:pointer;font-family:inherit;font-size:.82rem;font-weight:800;color:#546e7a;transition:background .12s}
.fd-a:active{background:#f5f6fa}
.fd-a.liked{color:#e53935}
.fd-comments{padding:.5rem .9rem .2rem;display:none}
.fd-comments.on{display:block}
.fd-c{display:flex;gap:.5rem;margin-bottom:.5rem}
.fd-c .fd-c-bub{background:#f0f2fa;border-radius:14px;padding:.4rem .7rem;flex:1;min-width:0}
.fd-c .fd-c-name{font-size:.75rem;font-weight:800;color:#1a237e}
.fd-c .fd-c-body{font-size:.82rem;color:#37474f;word-break:break-word}
.fd-c .fd-c-meta{font-size:.75rem;color:#546e7a;margin-top:.1rem;display:flex;gap:.6rem;align-items:center}
.fd-c-del{background:none;border:none;color:#ef9a9a;font-size:.75rem;cursor:pointer;font-weight:800}
.fd-c-form{display:flex;gap:.5rem;align-items:center;padding:.4rem 0 .6rem}
.fd-c-form input{flex:1;border:1.5px solid #e3e7ff;border-radius:18px;padding:.5rem .85rem;font-family:inherit;font-size:.85rem;outline:none}
.fd-c-form button{background:#1A23C9;color:#fff;border:none;border-radius:50%;width:34px;height:34px;cursor:pointer;flex-shrink:0;font-size:.85rem}
.fd-guest{background:#fff;margin:.7rem;border-radius:16px;box-shadow:0 2px 12px rgba(26,35,126,.08);padding:1.1rem;text-align:center}
.fd-guest-ic{font-size:1.8rem;display:block;margin-bottom:.3rem}
.fd-guest-txt{font-size:.85rem;color:#546e7a;font-weight:700;margin-bottom:.7rem}
.fd-guest-btn{display:inline-block;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;text-decoration:none;padding:.6rem 1.4rem;border-radius:11px;font-weight:800;font-size:.85rem}
.fd-av-sm{width:30px;height:30px;border-radius:50%;object-fit:cover;flex-shrink:0;background:#ECEEFF;display:flex;align-items:center;justify-content:center;font-weight:900;color:#1A23C9;font-size:.75rem}

.fd-empty{text-align:center;padding:3rem 1rem;color:#546e7a}
.fd-empty .ei{font-size:2.6rem;display:block;margin-bottom:.6rem;opacity:.6}
.fd-loader{text-align:center;padding:1.4rem;color:#546e7a;font-size:.82rem}
.fd-spin{width:26px;height:26px;border:3px solid #e3e7ff;border-top-color:#1A23C9;border-radius:50%;animation:fdspin .7s linear infinite;margin:0 auto .5rem}
@keyframes fdspin{to{transform:rotate(360deg)}}

.fd-toast{position:fixed;bottom:90px;left:50%;transform:translateX(-50%) translateY(20px);background:#1A23C9;color:#fff;padding:.6rem 1.2rem;border-radius:22px;font-weight:700;font-size:.82rem;z-index:9999;opacity:0;transition:all .28s;box-shadow:0 5px 18px rgba(26,35,201,.4);pointer-events:none}
.fd-toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.fd-toast.err{background:#c62828}

/* lightbox */
.fd-lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:9500;align-items:center;justify-content:center;padding:1rem}
.fd-lb.on{display:flex}
.fd-lb img{max-width:100%;max-height:90vh;border-radius:8px}
.fd-lb-x{position:absolute;top:1rem;right:1rem;width:42px;height:42px;border-radius:50%;background:rgba(255,255,255,.15);color:#fff;border:none;font-size:1.3rem;cursor:pointer}
</style>

<div class="fd">
  <div class="fd-bar">
    <a href="<?= $isGuest ? url('index.php') : url('dashboard.php') ?>" class="fd-back" aria-label="Back"><i class="fas fa-arrow-left" aria-hidden="true"></i></a>
    <h1>🏛️ Community Feed</h1>
    <button class="fd-search-btn" onclick="toggleSearch()" aria-label="Search"><i class="fas fa-search"></i></button>
  </div>

  <div class="fd-searchbar" id="fdSearchbar">
    <i class="fas fa-search fd-search-ic"></i>
    <input type="search" id="fdSearch" placeholder="Search posts or people…" oninput="onSearchInput()">
    <button class="fd-search-clear" id="fdSearchClear" onclick="clearSearch()" style="display:none">✕</button>
  </div>

  <!-- Composer (members only) -->
  <?php if(!$isGuest): ?>
  <div class="fd-comp">
    <div class="fd-comp-top">
      <?php if($MY_PHOTO): ?><img class="fd-av" src="<?= $MY_PHOTO ?>" alt=""><?php else: ?>
      <div class="fd-av"><?= h(strtoupper(substr($me['name'],0,1))) ?></div><?php endif; ?>
      <textarea id="cBody" placeholder="Share something with the club…" oninput="autoGrow(this)"></textarea>
    </div>
    <div class="fd-prev" id="cPrev"><button class="fd-prev-x" onclick="clearImg()">✕</button><img id="cPrevImg" src="" alt=""></div>
    <div class="fd-video-input" id="cVidWrap">
      <input type="url" id="cVid" placeholder="Paste YouTube / Instagram / Facebook / video link…" oninput="previewLink()">
    </div>
    <div class="fd-link-prev" id="cLinkPrev"><img id="cLinkThumb" src="" alt=""><div class="lp-meta" id="cLinkMeta"></div></div>
    <div class="fd-comp-actions">
      <button class="fd-act-btn ph" onclick="document.getElementById('cFile').click()"><i class="fas fa-image"></i> Photo</button>
      <button class="fd-act-btn vid" onclick="toggleVid()"><i class="fas fa-video"></i> Video</button>
      <button class="fd-post-btn" id="cPost" onclick="submitPost()">Post</button>
    </div>
    <input type="file" id="cFile" accept="image/*" style="display:none" onchange="onImg(this)">
    <input type="hidden" id="cImgB64">
  </div>
  <?php else: ?>
  <div class="fd-guest">
    <span class="fd-guest-ic">👋</span>
    <div class="fd-guest-txt">You're viewing the club feed as a guest.</div>
    <a class="fd-guest-btn" href="<?= url('index.php') ?>">Log in to post, like & comment</a>
  </div>
  <?php endif; ?>

  <button class="fd-newpill" id="newPill" onclick="loadNew()">↑ New posts</button>

  <div id="feedList"></div>
  <div class="fd-loader" id="feedLoader" style="display:none"><div class="fd-spin"></div>Loading…</div>
  <div id="feedEnd"></div>
</div>

<div class="fd-toast" id="fdToast"></div>
<div class="fd-lb" id="fdLb"><button class="fd-lb-x" onclick="closeLb()">✕</button><img id="fdLbImg" src="" alt=""></div>

<script>
var SELF = <?= json_encode(url('modules/feed.php')) ?>;
var ME_NAME = <?= json_encode($me['name'] ?? '') ?>;
var ME_PHOTO = <?= json_encode($MY_PHOTO) ?>;
var IS_GUEST = <?= $isGuest ? 'true' : 'false' ?>;
var IS_ADMIN = <?= $isAdmin ? 'true' : 'false' ?>;
var LOGIN_URL = <?= json_encode(url('index.php')) ?>;
function needLogin(){ if(confirm('Please log in to do that. Go to login?')) location.href=LOGIN_URL; }
var MAX_DIM = 1280;      // client-side resize target
var newestSeen = 0;      // highest post id loaded
var oldestLoaded = 0;    // lowest post id (cursor for infinite scroll)
var loading = false, hasMore = true;

function toast(m,e){var t=document.getElementById('fdToast');t.textContent=m;t.className='fd-toast on'+(e?' err':'');setTimeout(function(){t.className='fd-toast';},2600);}
function autoGrow(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,200)+'px';}
function esc(s){var d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
function avatar(photo,name,sm){
  if(photo) return '<img class="fd-av'+(sm?'-sm':'')+'" src="'+photo+'" alt="">';
  return '<div class="fd-av'+(sm?'-sm':'')+'">'+esc((name||'?').charAt(0).toUpperCase())+'</div>';
}

// ── Image: resize client-side then store base64 ──
function onImg(inp){
  if(!inp.files[0]) return;
  var f=inp.files[0];
  var r=new FileReader();
  r.onload=function(e){
    var img=new Image();
    img.onload=function(){
      var w=img.width,h=img.height;
      if(w>h && w>MAX_DIM){h=h*MAX_DIM/w;w=MAX_DIM;}
      else if(h>=w && h>MAX_DIM){w=w*MAX_DIM/h;h=MAX_DIM;}
      var c=document.createElement('canvas');c.width=w;c.height=h;
      c.getContext('2d').drawImage(img,0,0,w,h);
      var b64=c.toDataURL('image/jpeg',0.82);
      document.getElementById('cImgB64').value=b64;
      document.getElementById('cPrevImg').src=b64;
      document.getElementById('cPrev').style.display='block';
      // clear video if image chosen
      document.getElementById('cVid').value='';
      document.getElementById('cLinkPrev').style.display='none';
    };
    img.src=e.target.result;
  };
  r.readAsDataURL(f);
  inp.value='';
}
function clearImg(){document.getElementById('cImgB64').value='';document.getElementById('cPrev').style.display='none';}
function toggleVid(){
  var w=document.getElementById('cVidWrap');
  w.style.display=w.style.display==='block'?'none':'block';
  if(w.style.display==='block'){clearImg();document.getElementById('cVid').focus();}
}
function ytId(url){
  var m=(url||'').match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/|v\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m?m[1]:null;
}
function previewLink(){
  var url=document.getElementById('cVid').value.trim();
  var lp=document.getElementById('cLinkPrev');
  var thumb=document.getElementById('cLinkThumb');
  var id=ytId(url);
  if(id){
    thumb.style.display='block';
    thumb.setAttribute('data-step','0');
    thumb.onerror=function(){ytThumbFallback(thumb,id);};
    thumb.src='https://i.ytimg.com/vi/'+id+'/hqdefault.jpg';
    document.getElementById('cLinkMeta').textContent='▶ YouTube video';
    lp.style.display='block';
  } else if(/instagram\.com/.test(url)){
    thumb.onerror=null;thumb.src='';thumb.style.display='none';
    document.getElementById('cLinkMeta').textContent='📷 Instagram video — will show branded card';
    lp.style.display='block';
  } else if(/facebook\.com|fb\.watch|fb\.com/.test(url)){
    thumb.onerror=null;thumb.src='';thumb.style.display='none';
    document.getElementById('cLinkMeta').textContent='📘 Facebook video — will play inline';
    lp.style.display='block';
  } else if(url){
    thumb.onerror=null;thumb.src='';thumb.style.display='none';
    document.getElementById('cLinkMeta').textContent='🎬 '+url;
    lp.style.display='block';
  } else lp.style.display='none';
}

// ── Submit post ──
function submitPost(){
  var body=document.getElementById('cBody').value.trim();
  var img=document.getElementById('cImgB64').value;
  var vid=document.getElementById('cVid').value.trim();
  if(!body && !img && !vid){toast('Write something or add media',true);return;}
  var btn=document.getElementById('cPost');btn.disabled=true;btn.textContent='Posting…';
  var fd=new FormData();
  fd.append('ax','post');fd.append('body',body);
  if(img) fd.append('image_b64',img);
  if(vid && !img) fd.append('video_url',vid);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    btn.disabled=false;btn.textContent='Post';
    if(res.ok){
      document.getElementById('cBody').value='';autoGrow(document.getElementById('cBody'));
      clearImg();document.getElementById('cVid').value='';
      document.getElementById('cLinkPrev').style.display='none';
      document.getElementById('cVidWrap').style.display='none';
      toast('Posted!');
      loadNew();
    } else toast(res.msg||'Error',true);
  }).catch(function(){btn.disabled=false;btn.textContent='Post';toast('Network error',true);});
}

// ── Render a post ──
function renderPost(p){
  var media='';
  if(p.media_type==='image' && p.media_url){
    media='<div class="fd-media"><img src="'+p.media_url+'" loading="lazy" onclick="openLb(this.src)"></div>';
  } else if(p.media_type==='video'){
    var id=ytId(p.link_url||'');
    var url=p.link_url||'';
    if(id){
      // YouTube — real thumbnail with fallback chain
      var thumb = p.link_thumb || ('https://i.ytimg.com/vi/'+id+'/hqdefault.jpg');
      media='<div class="fd-video" data-embed="https://www.youtube.com/embed/'+id+'?autoplay=1" onclick="playVid(this)">'
        +'<img src="'+thumb+'" loading="lazy" onerror="ytThumbFallback(this,\''+id+'\')">'
        +'<div class="play"><span>▶</span></div></div>';
    } else if(/instagram\.com/.test(url)){
      // Instagram — branded gradient card (no public thumbnail available)
      media='<a class="fd-video fd-ig" href="'+esc(url)+'" target="_blank" rel="noopener">'
        +(p.link_thumb?'<img src="'+esc(p.link_thumb)+'" loading="lazy">':'')
        +'<div class="fd-brand-ov"><div class="fd-brand-logo">📷</div>'
        +'<div class="fd-brand-name">Instagram</div>'
        +'<div class="play"><span>▶</span></div></div></a>';
    } else if(/facebook\.com|fb\.watch|fb\.com/.test(url)){
      // Facebook — embed player inline, branded poster before play
      var fbEmbed='https://www.facebook.com/plugins/video.php?href='+encodeURIComponent(url)+'&show_text=false&autoplay=true';
      media='<div class="fd-video fd-fb" data-embed="'+fbEmbed+'" onclick="playVid(this)">'
        +(p.link_thumb?'<img src="'+esc(p.link_thumb)+'" loading="lazy">':'')
        +'<div class="fd-brand-ov"><div class="fd-brand-logo">f</div>'
        +'<div class="fd-brand-name">Facebook Video</div>'
        +'<div class="play"><span>▶</span></div></div></div>';
    } else if(url){
      // Generic video link (mp4 etc.)
      media='<a class="fd-linkcard fd-vidlink" href="'+esc(url)+'" target="_blank" rel="noopener">'
        +(p.link_thumb?'<img src="'+esc(p.link_thumb)+'">':'<div class="fd-vidlink-ph"><span>▶</span></div>')
        +'<div class="lc-t">🎬 '+esc(p.link_title||url)+'</div></a>';
    }
  } else if(p.media_type==='link' && p.link_url){
    media='<a class="fd-linkcard" href="'+esc(p.link_url)+'" target="_blank" rel="noopener">'
      +(p.link_thumb?'<img src="'+esc(p.link_thumb)+'">':'')
      +'<div class="lc-t">🔗 '+esc(p.link_title||p.link_url)+'</div></a>';
  } else if(p.media_type==='market' && p.link_url){
    media='<a class="fd-linkcard fd-market" href="'+esc(p.link_url)+'">'
      +(p.link_thumb?'<img src="'+esc(p.link_thumb)+'">':'')
      +'<div class="lc-t">🏪 '+esc(p.link_title||'View in Market')+' <span style="float:right;color:#1b5e20">View →</span></div></a>';
  }
  var roleBadge = (p.role && p.role!=='member') ? '<span class="fd-badge">'+esc(p.role)+'</span>' : '';
  var pinBadge = p.pinned ? '<span class="fd-pin-badge">📌 Pinned</span>' : '';
  // Menu: pin (admin) + delete (owner/admin)
  var menuItems='';
  if(IS_ADMIN) menuItems+='<button onclick="togglePin('+p.id+',this)">'+(p.pinned?'📌 Unpin':'📌 Pin to top')+'</button>';
  if(p.mine)   menuItems+='<button onclick="delPost('+p.id+',this)" style="color:#c62828">🗑 Delete</button>';
  var menu = menuItems ? '<div class="fd-menu-wrap"><button class="fd-menu" onclick="toggleMenu(this)">⋯</button><div class="fd-menu-drop">'+menuItems+'</div></div>' : '';
  // Determine the best shareable image for this post
  var shareImg = '';
  if(p.media_type==='image' && p.media_url) shareImg=p.media_url;
  else if(p.media_type==='videofile' && p.thumb_url) shareImg=p.thumb_url;
  else if(p.link_thumb) shareImg=p.link_thumb;
  return '<div class="fd-post'+(p.pinned?' fd-pinned':'')+'" id="post-'+p.id+'" data-id="'+p.id+'"'
    +' data-img="'+esc(shareImg)+'" data-body="'+esc(p.body||'')+'" data-author="'+esc(p.author||'')+'">'
    +(pinBadge?'<div class="fd-pin-strip">'+pinBadge+'</div>':'')
    +'<div class="fd-ph">'+avatar(p.photo,p.author)
      +'<div class="fd-meta"><div class="fd-name">'+esc(p.author)+roleBadge+'</div>'
      +'<div class="fd-sub">'+p.ago+'</div></div>'+menu+'</div>'
    +(p.body?'<div class="fd-body">'+esc(p.body)+'</div>':'')
    +media
    +'<div class="fd-stat"><span id="lc-'+p.id+'">'+(p.likes?('❤️ '+p.likes):'')+'</span>'
      +'<span id="cc-'+p.id+'">'+(p.comments?(p.comments+' comments'):'')+'</span></div>'
    +'<div class="fd-actions">'
      +'<button class="fd-a'+(p.liked?' liked':'')+'" id="like-'+p.id+'" onclick="toggleLike('+p.id+')">'+(p.liked?'❤️':'🤍')+' Like</button>'
      +'<button class="fd-a" onclick="toggleComments('+p.id+')">💬 Comment</button>'
      +'<button class="fd-a" onclick="sharePost('+p.id+')">↗ Share</button>'
    +'</div>'
    +'<div class="fd-comments" id="cm-'+p.id+'"><div class="fd-c-list" id="cl-'+p.id+'"></div>'
      +(IS_GUEST ? '' :
        '<div class="fd-c-form">'+avatar(ME_PHOTO,ME_NAME,true)
        +'<input type="text" id="ci-'+p.id+'" placeholder="Write a comment…" onkeydown="if(event.key===\'Enter\')addComment('+p.id+')">'
        +'<button onclick="addComment('+p.id+')">➤</button></div>')
    +'</div>'
  +'</div>';
}

// ── Like ──
function toggleLike(id){
  if(IS_GUEST){needLogin();return;}
  var btn=document.getElementById('like-'+id);
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'like',post_id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok)return;
      btn.classList.toggle('liked',res.liked);
      btn.innerHTML=(res.liked?'❤️':'🤍')+' Like';
      document.getElementById('lc-'+id).textContent=res.count?('❤️ '+res.count):'';
    });
}

// ── Comments ──
function toggleComments(id){
  var box=document.getElementById('cm-'+id);
  box.classList.toggle('on');
  if(box.classList.contains('on')) loadComments(id);
}
function loadComments(id){
  var list=document.getElementById('cl-'+id);
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'comments',post_id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok)return;
      list.innerHTML=res.comments.map(function(c){return commentHtml(id,c);}).join('');
    });
}
function commentHtml(pid,c){
  var del=c.mine?'<button class="fd-c-del" onclick="delComment('+c.id+','+pid+',this)">Delete</button>':'';
  return '<div class="fd-c">'+avatar(c.photo,c.author,true)
    +'<div class="fd-c-bub"><div class="fd-c-name">'+esc(c.author)+'</div>'
    +'<div class="fd-c-body">'+esc(c.body)+'</div>'
    +'<div class="fd-c-meta"><span>'+c.ago+'</span>'+del+'</div></div></div>';
}
function addComment(id){
  var inp=document.getElementById('ci-'+id);var b=inp.value.trim();if(!b)return;
  inp.value='';
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'comment',post_id:id,body:b})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok){toast(res.msg||'Error',true);return;}
      document.getElementById('cl-'+id).insertAdjacentHTML('beforeend',
        commentHtml(id,{id:res.id,author:res.author,photo:res.photo,body:res.body,ago:res.ago,mine:true}));
      document.getElementById('cc-'+id).textContent=res.count+' comments';
    });
}
function delComment(cid,pid,el){
  if(!confirm('Delete comment?'))return;
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'del_comment',id:cid})})
    .then(function(r){return r.json();}).then(function(res){
      if(res.ok){el.closest('.fd-c').remove();}
    });
}

// ── Delete post ──
function delPost(id,el){
  if(!confirm('Delete this post?'))return;
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'del_post',id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(res.ok){var p=document.getElementById('post-'+id);if(p)p.remove();toast('Deleted');}
      else toast(res.msg||'Error',true);
    });
}

// ── Post menu (⋯) ──
function toggleMenu(btn){
  var drop=btn.nextElementSibling;
  var open=drop.classList.contains('on');
  document.querySelectorAll('.fd-menu-drop.on').forEach(function(d){d.classList.remove('on');});
  if(!open) drop.classList.add('on');
}
document.addEventListener('click',function(e){
  if(!e.target.closest('.fd-menu-wrap')) document.querySelectorAll('.fd-menu-drop.on').forEach(function(d){d.classList.remove('on');});
});

// ── Pin / unpin (admin) ──
function togglePin(id,el){
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'pin',id:id})})
    .then(function(r){return r.json();}).then(function(res){
      if(!res.ok){toast(res.msg||'Error',true);return;}
      toast(res.pinned?'📌 Pinned to top':'Unpinned');
      setTimeout(function(){loadNew();},500);
    }).catch(function(){toast('Network error',true);});
}

// ── Share ──
function sharePost(id){
  var post=document.getElementById('post-'+id);
  if(!post){ _shareLinkOnly(id); return; }
  var img=post.getAttribute('data-img')||'';
  var body=post.getAttribute('data-body')||'';
  var author=post.getAttribute('data-author')||'';
  var link=SELF+'?post='+id;
  var clubName=<?= json_encode($CLUB) ?>;
  var captionParts=[];
  if(body) captionParts.push(body);
  if(author) captionParts.push('Posted by '+author);
  captionParts.push(clubName);
  var caption=captionParts.join('\n');
  var captionWithLink=caption+'\n'+link;

  // If there's an image, try to share it as a real file (shows photo in WhatsApp/Instagram)
  if(img && navigator.canShare){
    toast('Preparing image…');
    fetch(img).then(function(r){return r.blob();}).then(function(blob){
      var ext=(blob.type&&blob.type.indexOf('png')>-1)?'png':'jpg';
      var file=new File([blob],'club-post.'+ext,{type:blob.type||'image/jpeg'});
      if(navigator.canShare({files:[file]})){
        return navigator.share({files:[file],text:caption,title:'Club Post'});
      } else {
        return _shareTextLink(caption,link);
      }
    }).catch(function(){ _shareTextLink(caption,link); });
    return;
  }
  // No image — share text + link
  _shareTextLink(caption,link);
}
// Share text + link via native sheet, else WhatsApp, else copy
function _shareTextLink(text,link){
  if(navigator.share){
    navigator.share({text:text,url:link,title:'Club Post'}).catch(function(){});
  } else {
    window.open('https://wa.me/?text='+encodeURIComponent(text),'_blank');
  }
}
function _shareLinkOnly(id){
  var u=SELF+'?post='+id;
  if(navigator.share){navigator.share({title:'Club post',url:u}).catch(function(){});}
  else if(navigator.clipboard){navigator.clipboard.writeText(u).then(function(){toast('Link copied!');});}
  else{window.open('https://wa.me/?text='+encodeURIComponent(u),'_blank');}
}

// ── Video play ──
function playVid(el){
  var embed=el.getAttribute('data-embed');
  el.outerHTML='<iframe class="fd-video" src="'+embed+'" allow="autoplay;encrypted-media" allowfullscreen></iframe>';
}
// YouTube thumbnail fallback: try mq, then sd, then default 0.jpg
function ytThumbFallback(img,id){
  var step=img.getAttribute('data-step')||'0';
  if(step==='0'){img.setAttribute('data-step','1');img.src='https://i.ytimg.com/vi/'+id+'/mqdefault.jpg';}
  else if(step==='1'){img.setAttribute('data-step','2');img.src='https://i.ytimg.com/vi/'+id+'/sddefault.jpg';}
  else if(step==='2'){img.setAttribute('data-step','3');img.src='https://i.ytimg.com/vi/'+id+'/0.jpg';}
  else{img.onerror=null;img.style.display='none';img.parentNode.style.minHeight='180px';img.parentNode.style.background='#1a1a1a';}
}

// ── Lightbox ──
function openLb(src){document.getElementById('fdLbImg').src=src;document.getElementById('fdLb').classList.add('on');}
function closeLb(){document.getElementById('fdLb').classList.remove('on');}

// ── Feed loading ──
var searchQ = '';   // current search query ('' = normal feed)
function fetchFeed(before){
  var params={ax:'fetch',before:before||0};
  if(searchQ) params.q=searchQ;
  return fetch(SELF,{method:'POST',body:new URLSearchParams(params)})
    .then(function(r){return r.json();});
}
function loadInitial(){
  loading=true;document.getElementById('feedLoader').style.display='block';
  fetchFeed(0).then(function(res){
    loading=false;document.getElementById('feedLoader').style.display='none';
    if(!res.ok)return;
    var list=document.getElementById('feedList');
    if(res.posts.length===0){
      list.innerHTML=searchQ
        ? '<div class="fd-empty"><span class="ei">🔍</span><p>No posts match "'+esc(searchQ)+'"</p></div>'
        : '<div class="fd-empty"><span class="ei">📭</span><p>No posts yet. Be the first to share!</p></div>';
      hasMore=false;return;
    }
    list.innerHTML=(searchQ?'<div class="fd-search-info">🔍 Results for "'+esc(searchQ)+'"</div>':'')
      +res.posts.map(renderPost).join('');
    newestSeen=res.newest;
    var c=calcCursor(res.posts); if(c)oldestLoaded=c;
    hasMore=res.has_more;
  });
}
// Cursor = lowest id among NON-pinned posts (pinned have high ids but shouldn't affect paging)
function calcCursor(posts){
  var min=0;
  posts.forEach(function(p){ if(!p.pinned){ if(min===0||p.id<min) min=p.id; } });
  return min;
}
function loadMore(){
  if(loading||!hasMore)return;
  loading=true;document.getElementById('feedLoader').style.display='block';
  fetchFeed(oldestLoaded).then(function(res){
    loading=false;document.getElementById('feedLoader').style.display='none';
    if(!res.ok||!res.posts.length){hasMore=false;return;}
    document.getElementById('feedList').insertAdjacentHTML('beforeend',res.posts.map(renderPost).join(''));
    var c=calcCursor(res.posts); if(c)oldestLoaded=c;
    hasMore=res.has_more;
  });
}
// New posts above — reload fresh top
function loadNew(){
  document.getElementById('newPill').classList.remove('on');
  fetchFeed(0).then(function(res){
    if(!res.ok)return;
    var list=document.getElementById('feedList');
    list.innerHTML=res.posts.map(renderPost).join('');
    newestSeen=res.newest;
    var c=calcCursor(res.posts); if(c)oldestLoaded=c;
    hasMore=res.has_more;
    window.scrollTo({top:0,behavior:'smooth'});
  });
}

// ── Search ──
var searchTimer=null;
function toggleSearch(){
  var bar=document.getElementById('fdSearchbar');
  bar.classList.toggle('on');
  if(bar.classList.contains('on')){ document.getElementById('fdSearch').focus(); }
  else { clearSearch(); }
}
function onSearchInput(){
  var v=document.getElementById('fdSearch').value.trim();
  document.getElementById('fdSearchClear').style.display=v?'block':'none';
  clearTimeout(searchTimer);
  searchTimer=setTimeout(function(){
    searchQ=v;
    oldestLoaded=0;hasMore=true;
    document.getElementById('feedList').innerHTML='';
    loadInitial();
  },350);
}
function clearSearch(){
  document.getElementById('fdSearch').value='';
  document.getElementById('fdSearchClear').style.display='none';
  if(searchQ!==''){
    searchQ='';oldestLoaded=0;hasMore=true;
    document.getElementById('feedList').innerHTML='';
    loadInitial();
  }
}

// ── Auto-poll for new posts (every 25s) ──
setInterval(function(){
  if(newestSeen===0||searchQ!=='')return;
  fetch(SELF,{method:'POST',body:new URLSearchParams({ax:'check_new',since:newestSeen})})
    .then(function(r){return r.json();}).then(function(res){
      if(res.ok && res.new>0){
        var pill=document.getElementById('newPill');
        pill.textContent='↑ '+res.new+' new post'+(res.new>1?'s':'');
        pill.classList.add('on');
      }
    }).catch(function(){});
}, 25000);

// ── Infinite scroll ──
window.addEventListener('scroll',function(){
  if(window.innerHeight+window.scrollY >= document.body.offsetHeight-600) loadMore();
});

loadInitial();

// If opened via a shared link (?post=ID), highlight that post once loaded
(function(){
  var m=location.search.match(/[?&]post=(\d+)/);
  if(!m) return;
  var pid=m[1];
  var tries=0;
  var iv=setInterval(function(){
    tries++;
    var el=document.getElementById('post-'+pid);
    if(el){
      clearInterval(iv);
      el.scrollIntoView({behavior:'smooth',block:'center'});
      el.style.boxShadow='0 0 0 3px #1A23C9';
      el.style.transition='box-shadow .4s';
      setTimeout(function(){el.style.boxShadow='';},2500);
    }
    if(tries>20) clearInterval(iv);
  },300);
})();
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
