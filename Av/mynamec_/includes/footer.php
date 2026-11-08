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
  © <?= date('Y') ?> <b><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></b> · <?= h(setting('CLUB_PLACE','Vettikkattiri')) ?><br>
  <span><?= h(t('developed_by')) ?> <b>anexpaikadan</b></span>
</footer>

<?php
// ── Bottom tab bar (phone): 5 tabs, centre raised button ──
$_tbUser = isset($user) ? $user : (function_exists('currentUser') ? currentUser() : null);
$_tbAdm  = $_tbUser && isAdminRole($_tbUser['role']);
$_tbCur  = isset($curRel) ? $curRel : basename($_SERVER['PHP_SELF']);
$_tabs = $_tbAdm
  ? array(array('dashboard.php',t('nav_home'),'house-door'), array('modules/members.php',t('nav_members'),'people'),
          array('admin.php',t('nav_admin'),'shield-lock','mid'), array('modules/events.php',t('nav_events'),'calendar-event'), array('more.php',t('nav_more'),'grid-3x3-gap'))
  : array(array('dashboard.php',t('nav_home'),'house-door'), array('modules/events.php',t('nav_events'),'calendar-event'),
          array('modules/market.php',t('nav_market'),'bag','mid'), array('modules/feed.php',t('nav_feed'),'lightning-charge'), array('more.php',t('nav_more'),'grid-3x3-gap'));
?>
<nav class="tabbar" id="bnav" aria-label="Quick navigation">
<?php foreach($_tabs as $_t): $_on = ($_tbCur === $_t[0]); $_mid = !empty($_t[3]); ?>
  <a href="<?= url($_t[0]) ?>" class="<?= $_mid ? 'mid' : '' ?><?= $_on ? ' on' : '' ?>"<?= $_on ? ' aria-current="page"' : '' ?>>
    <?php if($_mid): ?><span class="ring"><i class="bi bi-<?= $_t[2] ?>-fill" aria-hidden="true"></i></span>
    <?php else: ?><span class="pill"><i class="bi bi-<?= $_t[2] ?><?= $_on ? '-fill' : '' ?>" aria-hidden="true"></i></span><?php endif; ?>
    <span><?= h($_t[1]) ?></span>
  </a>
<?php endforeach; ?>
</nav>
<script src="<?= url('assets/vendor/bootstrap/js/bootstrap.bundle.min.js') ?>"></script>
<script src="<?= url('assets/js/motion.js') ?>?v=1" defer></script>
<script>
// Emoji used as icons at the start of buttons, links, tabs, labels and headings are decorative:
// hide them from screen readers so they read "Save", not "floppy disk Save".
(function(){
  var re = /^(\s*)((?:\p{Extended_Pictographic}|\p{Regional_Indicator}|[\u200d\ufe0f\u20e3])+)\s*/u;
  function fix(root){
    (root || document).querySelectorAll('button,a,h1,h2,h3,h4,label,legend,summary,th,.btn,.tab,.chip,[role=tab],[role=button]').forEach(function(el){
      var n = el.firstChild;
      while (n && n.nodeType === 3 && !n.textContent.trim()) n = n.nextSibling;
      if (!n || n.nodeType !== 3) return;
      var m = n.textContent.match(re); if (!m) return;
      // keep the emoji readable when it is the only content and the control has no other name
      if (!el.textContent.slice(m[0].length).trim() && !el.getAttribute('aria-label') && !el.getAttribute('title')) return;
      var sp = document.createElement('span'); sp.setAttribute('aria-hidden','true'); sp.textContent = m[2] + ' ';
      n.textContent = n.textContent.slice(m[0].length);
      el.insertBefore(sp, n);
    });
  }
  try { fix(); } catch(e) {}
})();
</script>
<script>
// wide tables that scroll sideways can be scrolled with the keyboard too
document.querySelectorAll('.table-wrap').forEach(function(w){ if(w.scrollWidth > w.clientWidth + 2){ w.tabIndex = 0; w.setAttribute('role','region'); if(!w.hasAttribute('aria-label')) w.setAttribute('aria-label','Table (scroll sideways)'); } });
</script>

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
  // Module banner: same look everywhere — icon, emoji removed from the title
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
      var ico = document.body.getAttribute('data-mod-icon');
      if (ico && !hero.querySelector('.hero-ic')) {
        var sp2 = document.createElement('span'); sp2.className = 'hero-ic'; sp2.setAttribute('aria-hidden','true');
        sp2.innerHTML = '<i class="bi bi-' + ico.replace(/[^a-z0-9-]/g,'') + '"></i>';
        t.parentNode.insertBefore(sp2, t);
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

<?php
// WhatsApp queue: send a few waiting messages in the background while members use the site
require_once __DIR__ . '/wa_gateway.php';
if (!empty($_SESSION['user_id']) && wa_enabled() && (wa_queue_pending() > 0 || (wa_feature_on('fees') && wa_cfg('wa_last_daily') !== date('Y-m-d')))): ?>
<script>try{fetch('<?= url('modules/wa_worker.php') ?>?lazy=1',{credentials:'same-origin',keepalive:true}).catch(function(){});}catch(e){}</script>
<?php endif; ?>

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
    '<button type="button" id="pushEnableBtn" style="width:100%;min-height:48px;padding:.65rem;background:#E30613;color:#fff;border:none;border-radius:.6rem;font-weight:800;font-size:.9rem;cursor:pointer;margin-bottom:.4rem">🔔 Enable Notifications</button>' +
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
<?php if(!empty($user)): ?>
<!-- Passkey check before deleting or changing money (includes/sudo.php) -->
<div class="modal fade" id="mSudo" tabindex="-1" aria-labelledby="mSudoT" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm"><div class="modal-content" style="border-radius:1rem">
    <form id="sudoForm" autocomplete="off">
      <div class="modal-body text-center p-4">
        <span class="d-inline-flex align-items-center justify-content-center rounded-circle mb-2" style="width:56px;height:56px;background:var(--brand);color:#fff;font-size:1.5rem" aria-hidden="true"><i class="bi bi-shield-lock-fill"></i></span>
        <h2 class="fs-5 fw-bold mb-1" id="mSudoT"><?= h(t('sudo_title')) ?></h2>
        <p class="small text-2 mb-3"><?= h(t('sudo_sub')) ?></p>
        <label class="visually-hidden" for="sudoKey">Passkey</label>
        <input class="form-control form-control-lg text-center" id="sudoKey" type="password" inputmode="numeric" pattern="[0-9]*" maxlength="8" autocomplete="current-password" style="letter-spacing:.4em;font-size:1.4rem">
        <div class="small mt-2" id="sudoMsg" role="alert" style="color:var(--brand-dark);min-height:1.2em"></div>
        <div class="d-grid gap-2 mt-2">
          <button type="submit" class="btn btn-brand"><?= h(t('sudo_btn')) ?></button>
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal"><?= h(t('close')) ?></button>
        </div>
      </div>
    </form>
  </div></div>
</div>
<script>
(function(){
  var API = <?= json_encode(url('sudo.php')) ?>, CSRF = <?= json_encode(csrfToken()) ?>;
  var el = document.getElementById('mSudo'), md = bootstrap.Modal.getOrCreateInstance(el), next = null, freshUntil = 0;
  var key = document.getElementById('sudoKey'), msg = document.getElementById('sudoMsg');
  el.addEventListener('shown.bs.modal', function(){ key.value = ''; msg.textContent = ''; key.focus(); });
  // run fn() now if the passkey was confirmed in the last few minutes, otherwise ask first
  window.sudoThen = function(fn){
    if(Date.now() < freshUntil){ fn(); return; }
    fetch(API, {credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){
      if(d.fresh){ freshUntil = Date.now() + 240000; fn(); } else { next = fn; md.show(); }
    }).catch(function(){ next = fn; md.show(); });
  };
  document.getElementById('sudoForm').addEventListener('submit', function(e){
    e.preventDefault();
    var fd = new FormData(); fd.append('passkey', key.value); fd.append('_csrf', CSRF);
    fetch(API, {method:'POST', body:fd, credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){
      if(!d.ok){ msg.textContent = d.msg || 'Error'; key.value = ''; key.focus(); return; }
      freshUntil = Date.now() + 240000; var fn = next; next = null; md.hide(); if(fn) setTimeout(fn, 150);
    }).catch(function(){ msg.textContent = 'Network error'; });
  });
  // <form data-sudo> and <a data-sudo> / <button data-sudo> ask first
  document.addEventListener('submit', function(e){
    var f = e.target; if(!f.hasAttribute || f._sudoOk) return;
    // data-sudo-fields="fee_monthly,fee_annual": ask only when one of these fields was changed
    var only = f.getAttribute('data-sudo-fields');
    if(only){ var changed = only.split(',').some(function(n){ var x = f.elements[n.trim()]; return x && x.value !== x.defaultValue; }); if(!changed) return; }
    else if(!f.hasAttribute('data-sudo')) return;
    var sub = e.submitter || null; e.preventDefault();
    var conf = f.getAttribute('data-confirm'); if(conf && !confirm(conf)) return;
    sudoThen(function(){ f._sudoOk = true; if(f.requestSubmit) f.requestSubmit(sub && sub.form === f ? sub : undefined); else f.submit(); f._sudoOk = false; });
  }, true);
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[data-sudo],button[data-sudo]:not([type=submit])'); if(!a || a._sudoOk) return;
    e.preventDefault(); e.stopImmediatePropagation();
    var conf = a.getAttribute('data-confirm'); if(conf && !confirm(conf)) return;
    sudoThen(function(){ if(a.tagName === 'A' && a.href){ location.href = a.href; } else { a._sudoOk = true; a.click(); a._sudoOk = false; } });
  }, true);
})();
</script>
<?php endif; ?>
</body>
</html>