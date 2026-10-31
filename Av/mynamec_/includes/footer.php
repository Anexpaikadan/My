</main><!-- /page-wrap -->

<?php
// Load social links from DB
$_socials = [];
try {
    $srows = db()->query("SELECT setting_key,setting_value FROM club_settings WHERE setting_group='social' AND setting_value!='' ORDER BY setting_key")->fetchAll();
    foreach($srows as $sr) $_socials[$sr['setting_key']] = $sr['setting_value'];
} catch(Exception $e){}

// Social icon map
$_socialIcons = [
    'social_whatsapp'   => ['icon'=>'fab fa-whatsapp',  'bg'=>'#25d366','label'=>'WhatsApp'],
    'social_wa_group'   => ['icon'=>'fab fa-whatsapp',  'bg'=>'#128c7e','label'=>'WA Group'],
    'social_facebook'   => ['icon'=>'fab fa-facebook-f','bg'=>'#1877f2','label'=>'Facebook'],
    'social_instagram'  => ['icon'=>'fab fa-instagram', 'bg'=>'linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888)','label'=>'Instagram'],
    'social_youtube'    => ['icon'=>'fab fa-youtube',   'bg'=>'#ff0000','label'=>'YouTube'],
    'social_twitter'    => ['icon'=>'fab fa-x-twitter', 'bg'=>'#000000','label'=>'X/Twitter'],
    'social_telegram'   => ['icon'=>'fab fa-telegram',  'bg'=>'#0088cc','label'=>'Telegram'],
    'social_linkedin'   => ['icon'=>'fab fa-linkedin-in','bg'=>'#0077b5','label'=>'LinkedIn'],
    'social_tiktok'     => ['icon'=>'fab fa-tiktok',    'bg'=>'#010101','label'=>'TikTok'],
    'social_website'    => ['icon'=>'fas fa-globe',     'bg'=>'#0d47a1','label'=>'Website'],
];
?>

<footer style="background:#07225c;color:rgba(255,255,255,.72);padding:2rem 1rem 1.2rem;margin-top:2rem">
  <div style="max-width:960px;margin:0 auto">
    <!-- Club info + social row -->
    <div style="display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:1.2rem;margin-bottom:1.2rem">
      <div>
        <div style="font-weight:700;font-size:.95rem;color:rgba(255,255,255,.9);margin-bottom:.2rem"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></div>
        <div style="font-size:.78rem;color:rgba(255,255,255,.7)"><?= h(setting('CLUB_PLACE','Vettikkattiri')) ?>, Kerala, India</div>
      </div>
      <!-- Social Icons -->
      <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center">
        <?php
        // Always show WhatsApp if phone set
        $phone = setting('CLUB_PHONE','');
        if ($phone) {
            $wa = 'https://wa.me/'.preg_replace('/\D/','',$phone);
            echo '<a href="'.h($wa).'" target="_blank" rel="noopener" aria-label="WhatsApp" style="width:44px;height:44px;border-radius:50%;background:#25d366;color:#fff;display:flex;align-items:center;justify-content:center;font-size:.9rem;flex-shrink:0" title="WhatsApp"><i class="fab fa-whatsapp" aria-hidden="true"></i></a>';
        }
        // Dynamic social links from settings
        foreach($_socialIcons as $key=>$info) {
            if (!empty($_socials[$key])) {
                $bg = $info['bg'];
                $bgStyle = strpos($bg,'gradient')!==false ? "background:$bg" : "background:$bg";
                echo '<a href="'.h($_socials[$key]).'" target="_blank" rel="noopener" aria-label="'.$info['label'].'" style="width:44px;height:44px;border-radius:50%;'.$bgStyle.';color:#fff;display:flex;align-items:center;justify-content:center;font-size:.9rem;flex-shrink:0" title="'.$info['label'].'"><i class="'.$info['icon'].'" aria-hidden="true"></i></a>';
            }
        }
        ?>
        <a href="<?= url('index.php') ?>" style="display:inline-flex;align-items:center;min-height:44px;font-size:.78rem;color:rgba(255,255,255,.75);padding:.25rem .8rem;border:1px solid rgba(255,255,255,.12);border-radius:6px;text-decoration:none"><span aria-hidden="true">🌐</span>&nbsp;Site</a>
      </div>
    </div>
    <!-- Copyright -->
    <div style="border-top:1px solid rgba(255,255,255,.1);padding-top:.8rem;font-size:.74rem;text-align:center">
      © <?= date('Y') ?> <strong style="color:rgba(255,255,255,.75)"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></strong> · All rights reserved
    </div>
  </div>
</footer>

<!-- ══════════════════ BOTTOM NAV APP ══════════════════ -->
<?php
$_curFile = basename($_SERVER['PHP_SELF']);
$_curUri  = $_SERVER['REQUEST_URI'] ?? '';
$_bnUser  = isset($user) ? $user : (function_exists('currentUser') ? currentUser() : null);
$_bnLogd  = !empty($_bnUser['id']);
$_base    = defined('SITE_URL') ? rtrim(SITE_URL,'/') : '';

// Compute all values as variables — NO PHP logic inside HTML attributes
$_bnHome    = $_base.'/dashboard.php';
$_bnFeed    = $_base.'/modules/feed.php';
$_bnMkt     = $_base.'/modules/market.php';
$_bnProf    = $_bnLogd ? $_base.'/modules/profile.php' : $_base.'/login.php';
$_bnOnHome  = strpos($_curUri,'dashboard') !== false;
$_bnOnFeed  = strpos($_curUri,'feed')      !== false;
$_bnOnMkt   = strpos($_curUri,'market')    !== false;
$_bnOnProf  = (strpos($_curUri,'profile')  !== false || strpos($_curUri,'login') !== false);
$_bnPhOk    = $_bnLogd && !empty($_bnUser['profile_photo']) && $_bnUser['profile_photo'] !== 'default.png';
$_bnPhUrl   = $_bnPhOk ? $_base.'/'.ltrim($_bnUser['profile_photo'],'/') : '';
$_bnName    = ($_bnLogd && !empty($_bnUser['name'])) ? explode(' ',$_bnUser['name'])[0] : 'Login';
if(!function_exists('_bnOn')){function _bnOn($s){return false;}} // dummy — not needed anymore
?>
<style>
#bnav{position:fixed;bottom:0;left:0;right:0;z-index:990;background:rgba(255,255,255,.92);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-top:1px solid #eceff4;display:flex;align-items:flex-end;justify-content:space-around;box-shadow:0 -4px 24px rgba(13,71,161,.08);padding:.35rem .3rem calc(.35rem + env(safe-area-inset-bottom,0px))}
.bn{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:.4rem .05rem .3rem;font-size:.68rem;font-weight:700;color:#5f6b7e;min-height:52px;text-decoration:none;cursor:pointer;border:none;background:transparent;font-family:'DM Sans',sans-serif;position:relative;-webkit-tap-highlight-color:transparent;gap:.15rem;min-width:0;transition:color .15s;letter-spacing:.02em}
.bn-ico{font-size:1.35rem;line-height:1;display:flex;align-items:center;justify-content:center;transition:transform .18s}
.bn:active .bn-ico{transform:scale(.88)}
.bn:focus-visible{outline:3px solid #0D47A1;outline-offset:-3px;border-radius:12px}
.bn-feed{color:#1565C0}
.bn.on{color:#0D47A1}
.bn.on .bn-ico{transform:translateY(-1px)}
.bn.on::before{content:'';position:absolute;top:-1px;left:30%;right:30%;height:3px;background:linear-gradient(90deg,#0D47A1,#1565C0);border-radius:0 0 4px 4px}
.bn-prof-img{width:26px;height:26px;border-radius:50%;object-fit:cover;display:block;border:2px solid #e3e7ff}
.bn.on .bn-prof-img{border-color:#0D47A1}
/* Raised center Feed button */
.bn-feed{flex:0 0 auto;margin:0 .2rem}
.bn-feed .bn-ico{width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#1a237e,#1565C0 70%);color:#fff;font-size:1.5rem;margin-top:-22px;box-shadow:0 6px 18px rgba(21,101,192,.45);border:3px solid #fff}
.bn-feed{color:#1565C0}
.bn-feed.on::before{display:none}
.bn-feed.on .bn-ico{background:linear-gradient(135deg,#0d47a1,#0288d1);transform:none}
body{padding-bottom:calc(64px + env(safe-area-inset-bottom,0px))!important}
</style>
<nav id="bnav" aria-label="Quick navigation">

<button type="button" class="bn" onclick="history.back()" aria-label="Go back">
  <span class="bn-ico" aria-hidden="true"><i class="fas fa-arrow-left"></i></span>
  <span>Back</span>
</button>

<a href="<?php echo h($_bnHome); ?>" class="bn<?php echo $_bnOnHome?' on':''; ?>"<?php echo $_bnOnHome?' aria-current="page"':''; ?>>
  <span class="bn-ico" aria-hidden="true"><i class="fas fa-house"></i></span>
  <span>Home</span>
</a>

<a href="<?php echo h($_bnFeed); ?>" class="bn bn-feed<?php echo $_bnOnFeed?' on':''; ?>"<?php echo $_bnOnFeed?' aria-current="page"':''; ?>>
  <span class="bn-ico" aria-hidden="true"><i class="fas fa-bolt"></i></span>
  <span>Feed</span>
</a>

<a href="<?php echo h($_bnMkt); ?>" class="bn<?php echo $_bnOnMkt?' on':''; ?>"<?php echo $_bnOnMkt?' aria-current="page"':''; ?>>
  <span class="bn-ico" aria-hidden="true"><i class="fas fa-store"></i></span>
  <span>Market</span>
</a>

<a href="<?php echo h($_bnProf); ?>" class="bn<?php echo $_bnOnProf?' on':''; ?>"<?php echo $_bnOnProf?' aria-current="page"':''; ?>>
  <?php if($_bnPhOk): ?>
  <span class="bn-ico" aria-hidden="true"><img class="bn-prof-img" alt="" width="26" height="26" src="<?php echo h($_bnPhUrl); ?>" onerror="this.outerHTML='<i class=\'fas fa-user\'></i>'"></span>
  <?php else: ?>
  <span class="bn-ico" aria-hidden="true"><i class="fas fa-<?php echo $_bnLogd?'user':'right-to-bracket'; ?>"></i></span>
  <?php endif; ?>
  <span><?php echo h($_bnName); ?></span>
</a>

</nav>
<!-- ══════════════════ /BOTTOM NAV ══════════════════ -->

<!-- Push Notification JS -->
<script>
var PUSH_KEY = 'BPtQ21rs0CVf06l96ac3-SGEZCtWrMhgU11llT4YoVT3HMRRqELNKowuLmIlWrbzBMjmeJTTZF58pc6e5VtY9t8';
var PUSH_URL = '/push_notify.php';

function u8(k){
  var p='='.repeat((4-k.length%4)%4);
  var b=(k+p).replace(/-/g,'+').replace(/_/g,'/');
  var r=atob(b);var a=new Uint8Array(r.length);
  for(var i=0;i<r.length;i++)a[i]=r.charCodeAt(i);return a;
}

function doSubscribe(onDone){
  navigator.serviceWorker.register('/sw.js')
    .then(function(){return navigator.serviceWorker.ready;})
    .then(function(sw){
      return sw.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:u8(PUSH_KEY)});
    }).then(function(sub){
      var j=sub.toJSON();
      var fd=new FormData();
      fd.append('action','subscribe');
      fd.append('endpoint',j.endpoint);
      fd.append('p256dh',j.keys.p256dh);
      fd.append('auth',j.keys.auth);
      fd.append('device',/iphone|ipad|ipod/i.test(navigator.userAgent)?'ios':'android');
      return fetch(PUSH_URL,{method:'POST',body:fd}).then(function(r){return r.json();});
    }).then(function(res){
      if(onDone) onDone(res.ok);
    }).catch(function(e){
      console.log('Push subscribe error:',e);
      if(onDone) onDone(false);
    });
}

function showPushPopup(){
  // Don't show if already asked on this device
  if(localStorage.getItem('push_asked_v2')) return;

  var modal = document.createElement('div');
  modal.id = 'pushModal';
  modal.setAttribute('role','dialog'); modal.setAttribute('aria-modal','true'); modal.setAttribute('aria-labelledby','pushTitle');
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem';
  modal.innerHTML =
    '<div style="background:#fff;border-radius:20px;padding:1.5rem;max-width:320px;width:100%;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,.3)">' +
    '<div style="font-size:2.5rem;margin-bottom:.5rem" aria-hidden="true">🔔</div>' +
    '<div id="pushTitle" style="font-size:1.05rem;font-weight:800;color:#07225c;margin-bottom:.4rem">Stay Updated!</div>' +
    '<div style="font-size:.88rem;color:#475569;line-height:1.6;margin-bottom:1rem">Get notified about club events and announcements on your phone.</div>' +
    '<button type="button" id="pushEnableBtn" style="width:100%;min-height:48px;padding:.65rem;background:linear-gradient(135deg,#07225c,#1565c0);color:#fff;border:none;border-radius:12px;font-weight:800;font-size:.9rem;cursor:pointer;margin-bottom:.4rem">🔔 Enable Notifications</button>' +
    '<button type="button" id="pushLaterBtn" style="width:100%;min-height:44px;padding:.5rem;background:#f1f5f9;border:none;border-radius:10px;font-size:.88rem;color:#475569;cursor:pointer">Maybe Later</button>' +
    '</div>';

  document.body.appendChild(modal);
  document.getElementById('pushEnableBtn').focus();

  document.getElementById('pushEnableBtn').onclick = function(){
    modal.remove();
    localStorage.setItem('push_asked_v2','1');
    Notification.requestPermission().then(function(perm){
      if(perm === 'granted'){
        doSubscribe(function(ok){
          if(ok) showPushToast('🔔 Notifications enabled!');
        });
      }
    });
  };

  document.getElementById('pushLaterBtn').onclick = function(){
    modal.remove();
    localStorage.setItem('push_asked_v2','1');
  };
}

function showPushToast(msg){
  var el=document.createElement('div');
  el.textContent=msg;
  el.setAttribute('role','status');
  el.style.cssText='position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#07225c;color:#fff;padding:.6rem 1.2rem;border-radius:25px;font-size:.8rem;font-weight:700;z-index:9999;white-space:nowrap;box-shadow:0 4px 14px rgba(0,0,0,.2)';
  document.body.appendChild(el);
  setTimeout(function(){el.remove();},3000);
}

// Register SW
if('serviceWorker' in navigator){
  navigator.serviceWorker.register('/sw.js').catch(function(){});
}

<?php if(!empty($_SESSION['user_id'])): ?>
window.addEventListener('load', function(){
  if(!('PushManager' in window)) return;

  // Already permission granted → silently re-subscribe (new phone scenario)
  if(Notification.permission === 'granted'){
    doSubscribe(null);
    return;
  }

  // Permission not yet asked → show popup after 3 seconds
  if(Notification.permission === 'default'){
    setTimeout(showPushPopup, 3000);
  }
});
<?php endif; ?>
</script>
<footer style="
  text-align:center;
  padding:14px 12px;
  font-size:13px;
  color:#6b7280;
  border-top:1px solid #eee;
  line-height:1.4;
  word-wrap:break-word;
">
  © 2026 · All rights reserved ·
  <span style="color:#111; font-weight:600; display:inline-block;">
    anexpaikadan
  </span>
</footer>
</body>
</html>