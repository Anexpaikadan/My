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

<footer class="app-foot">
  <div class="af-in">
    <div>
      <div class="af-name"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></div>
      <div class="af-place"><?= h(setting('CLUB_PLACE','Vettikkattiri')) ?>, Kerala, India</div>
    </div>
    <div class="af-social">
      <?php
      $phone = setting('CLUB_PHONE','');
      if ($phone) {
          echo '<a href="'.h('https://wa.me/'.preg_replace('/\D/','',$phone)).'" target="_blank" rel="noopener" aria-label="WhatsApp" class="af-ic" style="background:#25d366"><i class="fab fa-whatsapp" aria-hidden="true"></i></a>';
      }
      foreach($_socialIcons as $key=>$info) {
          if (!empty($_socials[$key])) {
              echo '<a href="'.h($_socials[$key]).'" target="_blank" rel="noopener" aria-label="'.h($info['label']).'" class="af-ic" style="background:'.$info['bg'].'"><i class="'.$info['icon'].'" aria-hidden="true"></i></a>';
          }
      }
      ?>
      <a href="<?= url('index.php') ?>" class="af-site"><?= ic('globe','ic-sm') ?> Website</a>
    </div>
  </div>
  <div class="af-copy">© <?= date('Y') ?> <?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?> · All rights reserved · <b>anexpaikadan</b></div>
</footer>

<?php
$_curFile = basename($_SERVER['PHP_SELF']);
$_bnUser  = isset($user) ? $user : (function_exists('currentUser') ? currentUser() : null);
$_bnLogd  = !empty($_bnUser['id']);
$_bnName  = ($_bnLogd && !empty($_bnUser['name'])) ? explode(' ',$_bnUser['name'])[0] : 'Login';
$_bnTabs  = array(
  array('dashboard.php',        'Home',   'home'),
  array('modules/events.php',   'Events', 'calendar'),
  array('modules/feed.php',     'Feed',   'bolt'),
  array('modules/market.php',   'Market', 'store'),
  array($_bnLogd ? 'modules/profile.php' : 'login.php', $_bnName, 'user'),
);
?>
<style>
.app-foot{background:var(--ink);border-top:4px solid transparent;border-image:var(--brand-grad) 1;color:rgba(255,255,255,.78);padding:1.6rem 1rem 1rem;margin-top:2rem}
.af-in{max-width:1200px;margin:0 auto;display:flex;flex-wrap:wrap;gap:1rem;align-items:center;justify-content:space-between}
.af-name{font-weight:800;color:#fff;font-size:.98rem}
.af-place{font-size:.8rem}
.af-social{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center}
.af-ic{width:44px;height:44px;border-radius:14px;color:#fff;display:flex;align-items:center;justify-content:center;font-size:1rem}
.af-site{display:inline-flex;align-items:center;gap:.4rem;min-height:44px;padding:0 .9rem;border-radius:14px;border:1px solid rgba(255,255,255,.18);color:#fff;font-size:.84rem;font-weight:600}
.af-copy{max-width:1200px;margin:1rem auto 0;padding-top:.8rem;border-top:1px solid rgba(255,255,255,.1);text-align:center;font-size:.78rem}
.af-copy b{color:#fff}
/* bottom tab bar (glass) */
#bnav{position:fixed;left:.6rem;right:.6rem;bottom:calc(.55rem + env(safe-area-inset-bottom,0px));z-index:990;
  height:66px;border-radius:24px;display:flex;align-items:center;justify-content:space-around;padding:0 .3rem;
  background:rgba(255,255,255,.92);backdrop-filter:saturate(180%) blur(18px);-webkit-backdrop-filter:saturate(180%) blur(18px);
  border:1px solid var(--line);box-shadow:0 14px 34px -12px rgba(11,16,51,.35);max-width:560px;margin:0 auto}
.bn{flex:1;min-width:0;height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
  color:var(--text-3);font-size:.68rem;font-weight:700;border-radius:18px;position:relative;transition:color .15s}
.bn .ic{width:23px;height:23px;transition:transform .2s}
.bn span{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:0 2px}
.bn.on{color:var(--primary)}
.bn.on .ic{color:var(--primary);transform:translateY(-1px)}
.bn.on::after{content:'';position:absolute;bottom:4px;width:5px;height:5px;border-radius:50%;background:var(--accent)}
.bn:active .ic{transform:scale(.88)}
.bn-mid{flex:0 0 auto;width:58px;height:58px;margin:0 .15rem;border-radius:50%;color:#fff;
  background:var(--brand-grad);box-shadow:0 10px 24px -8px rgba(10,20,224,.7),0 0 0 4px #fff;transform:translateY(-14px)}
.bn-mid span{display:none}
.bn-mid .ic{width:26px;height:26px}
.bn-mid.on{color:#fff}.bn-mid.on::after{display:none}.bn-mid.on .ic{color:#fff}
body{padding-bottom:calc(86px + env(safe-area-inset-bottom,0px))!important}
@media(min-width:960px){#bnav{display:none}body{padding-bottom:0!important}}
</style>
<nav id="bnav" aria-label="Quick navigation">
<?php foreach($_bnTabs as $t): $on = ($_curFile === basename($t[0])); $mid = ($t[2]==='bolt'); ?>
  <a href="<?= url($t[0]) ?>" class="bn<?= $mid?' bn-mid':'' ?><?= $on?' on':'' ?>"<?= $on?' aria-current="page"':'' ?><?= $mid?' aria-label="Feed"':'' ?>><?= ic($t[2]) ?><span><?= h($t[1]) ?></span></a>
<?php endforeach; ?>
</nav>
<!-- ══════════════════ /BOTTOM NAV ══════════════════ -->

<!-- Accessibility helper: connect each form label to the field right after it,
     and give icon-only buttons/links a name from their title -->
<script>
(function(){
  var n=0, CTRL=/^(INPUT|SELECT|TEXTAREA)$/;
  document.querySelectorAll('label:not([for])').forEach(function(l){
    if (l.querySelector('input,select,textarea')) return;
    var c=l.nextElementSibling;
    if (!c || !CTRL.test(c.tagName) || c.type==='hidden') return;
    if (!c.id) c.id='fld-auto-'+(++n);
    l.htmlFor=c.id;
  });
  // Module banner: same look everywhere — 3D icon, emoji removed from the title
  var hero = document.querySelector('.hero,.ft-hero,.bh-header,.bc-hero,.ach-hero,.cf-hero,.ev-header,.fm-hero,.gal-hero,.gf-hero,.mk-hero,.adm-header');
  if (hero) {
    var t = hero.querySelector('h1,.bh-title,.ev-htitle,.adm-hname');
    if (t) {
      var tn = t.firstChild;
      while (tn && tn.nodeType === 3 && !tn.nodeValue.trim()) tn = tn.nextSibling;
      if (tn && tn.nodeType === 3) {
        try { tn.nodeValue = tn.nodeValue.replace(/^\s*(?:\p{Extended_Pictographic}|\uFE0F|\u200D|\s)+/u, ''); } catch(e) {}
      }
      t.classList.add('ph-title');
      if (t.matches('.bh-title,.ev-htitle')) { var sp = t.querySelector('span'); if (sp) sp.classList.add('ph-sub'); }
      var img = document.body.getAttribute('data-mod-img');
      if (img && !hero.querySelector('.hero-ic')) {
        var im = new Image(); im.src = img; im.alt = ''; im.className = 'hero-ic'; im.width = 78; im.height = 78;
        t.parentNode.insertBefore(im, t);
      }
      if (getComputedStyle(t).textAlign !== 'center') t.parentNode.classList.add('ph-left');
    }
  }
  // Clickable cards/tabs built from <div onclick>: make them reachable and usable by keyboard
  document.querySelectorAll('div[onclick],span[onclick],li[onclick],td[onclick],img[onclick]').forEach(function(el){
    var oc=el.getAttribute('onclick')||'';
    if (/event\.target|stopPropagation/.test(oc)) return;          // backdrop "click outside" handlers
    if (el.querySelector('a[href],button,input,select,textarea')) return; // would nest controls
    if (!el.hasAttribute('role')) el.setAttribute('role','button');
    if (!el.hasAttribute('tabindex')) el.tabIndex=0;
    el.addEventListener('keydown',function(e){
      if (e.target!==el) return;
      if (e.key==='Enter'||e.key===' '){ e.preventDefault(); el.click(); }
    });
  });
  document.querySelectorAll('button,a[href]').forEach(function(b){
    if (b.getAttribute('aria-label') || (b.textContent||'').trim()) return;
    if (b.querySelector('img[alt]:not([alt=""])')) return;
    var t=b.getAttribute('title'); if (t) b.setAttribute('aria-label',t);
  });
})();
</script>

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
    '<div id="pushTitle" style="font-size:1.05rem;font-weight:800;color:#0B1033;margin-bottom:.4rem">Stay Updated!</div>' +
    '<div style="font-size:.88rem;color:#475569;line-height:1.6;margin-bottom:1rem">Get notified about club events and announcements on your phone.</div>' +
    '<button type="button" id="pushEnableBtn" style="width:100%;min-height:48px;padding:.65rem;background:#0A14E0;color:#fff;border:none;border-radius:14px;font-weight:800;font-size:.9rem;cursor:pointer;margin-bottom:.4rem">🔔 Enable Notifications</button>' +
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
  el.style.cssText='position:fixed;bottom:96px;left:50%;transform:translateX(-50%);background:#0B1033;color:#fff;padding:.6rem 1.2rem;border-radius:25px;font-size:.8rem;font-weight:700;z-index:9999;white-space:nowrap;box-shadow:0 4px 14px rgba(0,0,0,.2)';
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
</body>
</html>