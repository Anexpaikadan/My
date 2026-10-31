<?php
require_once __DIR__ . '/includes/config.php';

// AJAX contact form
if (!empty($_POST['ajax']) && ($_POST['action']??'')==='contact') {
    header('Content-Type: application/json');
    $n=trim($_POST['name']??''); $e=trim($_POST['email']??'');
    $s=trim($_POST['subject']??''); $m=trim($_POST['message']??'');
    if (!$n||!$m){ echo json_encode(['ok'=>false,'msg'=>'Name and message are required.']); exit; }
    try { db()->prepare('INSERT INTO contact_messages(name,email,subject,message)VALUES(?,?,?,?)')->execute([$n,$e,$s,$m]); echo json_encode(['ok'=>true,'msg'=>'Message sent! We will get back to you soon. 🙏']); } catch(Exception $ex){ echo json_encode(['ok'=>false,'msg'=>'Database error. Please try WhatsApp instead.']); }
    exit;
}

$logo = getLogoB64();
$wa   = preg_replace('/\D/','',CLUB_PHONE);
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Contact Us | <?= h(CLUB_NAME) ?></title>
<?php if(defined('LOGO_URL')): ?><link rel="icon" href="<?= h(LOGO_URL) ?>"><?php endif; ?>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>
:root{--primary:#1a3a6b;--accent:#c8922a;--accent2:#e6b84a;--text:#1a1a2e;--text2:#4a5568;--text3:#8a9bae;--border:rgba(0,0,0,.08);--shadow:0 4px 24px rgba(0,0,0,.09);--radius:14px}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:#fff;color:var(--text);line-height:1.65}
a{text-decoration:none;color:inherit}
/* Kerala stripe */
.kstrip{height:4px;background:repeating-linear-gradient(90deg,#c8922a 0,#c8922a 10px,#b71c1c 10px,#b71c1c 20px,#1a3a6b 20px,#1a3a6b 30px,#e6b84a 30px,#e6b84a 40px)}
/* Nav */
.top-bar{background:var(--primary);padding:.6rem 1.5rem;display:flex;align-items:center;justify-content:space-between}
.nav-brand{display:flex;align-items:center;gap:.65rem;color:#fff}
.nav-logo-img{width:38px;height:38px;border-radius:50%;object-fit:cover;border:2px solid rgba(200,146,42,.5)}
.nav-logo-ph{width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.15);border:2px solid rgba(200,146,42,.4);display:flex;align-items:center;justify-content:center;font-size:.95rem}
.brand-name{font-family:'Playfair Display',serif;font-size:.95rem;font-weight:700;line-height:1.2;color:#fff}
.brand-sub{font-size:.58rem;color:rgba(255,255,255,.5);letter-spacing:.1em}
.back-btn{display:inline-flex;align-items:center;gap:.4rem;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.85);padding:.42rem 1rem;border-radius:8px;font-size:.84rem;font-weight:600;transition:all .2s}
.back-btn:hover{background:rgba(255,255,255,.22);color:#fff}
/* Hero */
.contact-hero{background:linear-gradient(135deg,#1a3a6b 0%,#0d47a1 60%,#1565c0 100%);padding:4.5rem 1.5rem;text-align:center;color:#fff;position:relative;overflow:hidden}
.contact-hero::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 70% 30%,rgba(200,146,42,.15),transparent 60%)}
.contact-hero h1{font-family:'Playfair Display',serif;font-size:clamp(2rem,4vw,2.8rem);font-weight:700;position:relative}
.contact-hero p{font-size:1rem;color:rgba(255,255,255,.72);max-width:500px;margin:.7rem auto 0;position:relative}
/* Form card */
.form-card{background:#fff;border-radius:var(--radius);box-shadow:var(--shadow);border:1px solid var(--border);padding:2rem}
label.flbl{font-size:.75rem;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem;display:block}
.finp{width:100%;background:#f7f9fc;border:1.5px solid rgba(0,0,0,.1);border-radius:10px;padding:.78rem 1rem;font-family:'Inter',sans-serif;font-size:.9rem;color:var(--text);outline:none;transition:all .25s;margin-bottom:1rem}
.finp:focus{border-color:var(--primary);background:#fff;box-shadow:0 0 0 3px rgba(26,58,107,.1)}
.finp::placeholder{color:#bcc4cf}
textarea.finp{resize:vertical;min-height:130px}
.btn-send{width:100%;padding:.85rem;background:var(--primary);color:#fff;border:none;border-radius:10px;font-family:'Inter',sans-serif;font-weight:700;font-size:.95rem;cursor:pointer;transition:all .25s;display:flex;align-items:center;justify-content:center;gap:.5rem}
.btn-send:hover:not(:disabled){background:#0d47a1;transform:translateY(-1px);box-shadow:0 8px 24px rgba(26,58,107,.3)}
.btn-send:disabled{opacity:.55;cursor:not-allowed}
.alert-box{border-radius:9px;padding:.75rem 1rem;font-size:.86rem;font-weight:500;margin-bottom:1rem;display:none;line-height:1.45}
.alert-box.err{background:#fff0f0;border:1px solid #fecaca;color:#991b1b;display:block}
.alert-box.ok{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;display:block}
/* Info cards */
.info-card{background:#f7f9fc;border:1px solid var(--border);border-radius:var(--radius);padding:1.4rem;display:flex;align-items:flex-start;gap:1rem;margin-bottom:1rem;transition:all .25s}
.info-card:hover{background:#fff;box-shadow:var(--shadow);transform:translateX(4px)}
.info-icon{width:44px;height:44px;border-radius:10px;background:linear-gradient(135deg,var(--primary),#0d47a1);display:flex;align-items:center;justify-content:center;color:#fff;font-size:1rem;flex-shrink:0}
.info-lbl{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--text3);margin-bottom:.18rem}
.info-val{font-weight:600;font-size:.9rem;color:var(--text)}
.info-val a{color:var(--primary);transition:color .2s}
.info-val a:hover{color:var(--accent)}
/* WA button */
.btn-wa{display:inline-flex;align-items:center;justify-content:center;gap:.55rem;width:100%;padding:.85rem;background:#25d366;color:#fff;border:none;border-radius:10px;font-family:'Inter',sans-serif;font-weight:700;font-size:.95rem;cursor:pointer;transition:all .25s;margin-top:.5rem}
.btn-wa:hover{background:#1ebe5d;transform:translateY(-1px);box-shadow:0 8px 24px rgba(37,211,102,.3)}
/* Map */
.map-wrap{border-radius:var(--radius);overflow:hidden;border:1px solid var(--border);box-shadow:var(--shadow);height:340px}
.map-wrap iframe{width:100%;height:100%;border:none}
/* Footer */
.mini-footer{background:var(--primary);color:rgba(255,255,255,.5);text-align:center;padding:1.2rem;font-size:.78rem}
.mini-footer b{color:var(--accent2)}
/* Reveal */
.rv{opacity:0;transform:translateY(24px);transition:opacity .6s ease,transform .6s ease}
.rv.in{opacity:1;transform:translateY(0)}
.rl{opacity:0;transform:translateX(-24px);transition:opacity .65s ease,transform .65s ease}
.rl.in{opacity:1;transform:translateX(0)}
.rr{opacity:0;transform:translateX(24px);transition:opacity .65s ease,transform .65s ease}
.rr.in{opacity:1;transform:translateX(0)}
/* WA float */
.wa-float{position:fixed;bottom:1.5rem;right:1.5rem;width:52px;height:52px;border-radius:50%;background:#25d366;color:#fff;display:flex;align-items:center;justify-content:center;font-size:1.4rem;z-index:900;box-shadow:0 6px 22px rgba(37,211,102,.42);transition:all .22s;border:none;cursor:pointer;text-decoration:none}
.wa-float:hover{background:#1ebe5d;transform:scale(1.1);color:#fff}
</style>
</head>
<body>
<a href="https://wa.me/<?= h($wa) ?>" target="_blank" class="wa-float"><i class="fab fa-whatsapp"></i></a>
<div class="kstrip"></div>

<!-- Top bar nav -->
<div class="top-bar">
  <a href="<?= url('index.php') ?>" class="nav-brand">
    <?php if($logo): ?><img src="<?= $logo ?>" class="nav-logo-img" alt=""><?php else: ?><div class="nav-logo-ph">⚜</div><?php endif; ?>
    <div><div class="brand-name">Aishwarya A&S Club</div><div class="brand-sub">Vettikkattiri · Kerala</div></div>
  </a>
  <a href="<?= url('index.php') ?>" class="back-btn"><i class="fas fa-arrow-left"></i> Back to Home</a>
</div>

<!-- Hero -->
<div class="contact-hero">
  <h1>Get In Touch</h1>
  <p>We'd love to hear from you. Reach out for membership, events or any queries about <?= h(CLUB_NAME) ?>.</p>
</div>

<!-- Main content -->
<div class="container py-5" style="max-width:1100px">
  <div class="row g-4 align-items-start">

    <!-- Contact Form -->
    <div class="col-lg-6 rl">
      <div class="form-card">
        <h3 style="font-family:'Playfair Display',serif;font-size:1.5rem;color:var(--primary);margin-bottom:.3rem">Send a Message</h3>
        <p style="font-size:.86rem;color:var(--text3);margin-bottom:1.5rem">Fill the form and we'll reply on WhatsApp shortly.</p>
        <div class="alert-box" id="contactAlert"></div>
        <div id="contactFormWrap">
          <label class="flbl">Your Name *</label>
          <input type="text"  class="finp" id="cName" placeholder="Full name">
          <label class="flbl">Email Address</label>
          <input type="email" class="finp" id="cEmail" placeholder="your@email.com">
          <label class="flbl">Subject</label>
          <input type="text"  class="finp" id="cSubject" placeholder="What is this about?">
          <label class="flbl">Message *</label>
          <textarea           class="finp" id="cMsg" placeholder="Write your message here…"></textarea>
          <button class="btn-send" id="btnSend" onclick="sendContact()">
            <i class="fas fa-paper-plane"></i> Send Message
          </button>
        </div>
        <div id="contactSuccess" style="display:none;text-align:center;padding:2rem 0">
          <div style="font-size:3rem;margin-bottom:.8rem">✅</div>
          <h5 style="font-family:'Playfair Display',serif;color:var(--primary);margin-bottom:.4rem">Message Sent!</h5>
          <p style="font-size:.88rem;color:var(--text2)">Thank you for reaching out. We'll get back to you soon via WhatsApp.</p>
          <button onclick="document.getElementById('contactSuccess').style.display='none';document.getElementById('contactFormWrap').style.display='block'" style="margin-top:1rem;background:none;border:1.5px solid var(--primary);color:var(--primary);border-radius:8px;padding:.5rem 1.2rem;font-family:'Inter',sans-serif;font-weight:600;cursor:pointer">Send Another</button>
        </div>
      </div>
    </div>

    <!-- Right: Info + Map -->
    <div class="col-lg-6 rr">
      <!-- Contact info cards -->
      <div class="info-card">
        <div class="info-icon"><i class="fas fa-map-marker-alt"></i></div>
        <div><div class="info-lbl">Location</div><div class="info-val"><?= h(CLUB_PLACE) ?>, Kerala, India</div></div>
      </div>
      <div class="info-card">
        <div class="info-icon"><i class="fab fa-whatsapp"></i></div>
        <div><div class="info-lbl">WhatsApp</div><div class="info-val"><a href="https://wa.me/<?= h($wa) ?>" target="_blank"><?= h(CLUB_PHONE) ?></a></div></div>
      </div>
      <div class="info-card">
        <div class="info-icon"><i class="fab fa-whatsapp"></i></div>
        <div><div class="info-lbl">WhatsApp Group</div><div class="info-val"><a href="<?= h(CLUB_WA_GROUP) ?>" target="_blank">Join Our Community Group →</a></div></div>
      </div>
      <div class="info-card">
        <div class="info-icon"><i class="fas fa-users"></i></div>
        <div><div class="info-lbl">Member Portal</div><div class="info-val"><a href="<?= url('login.php') ?>">Login / Apply to Join →</a></div></div>
      </div>

      <!-- WhatsApp direct button -->
      <a href="https://wa.me/<?= h($wa) ?>" target="_blank" class="btn-wa">
        <i class="fab fa-whatsapp" style="font-size:1.15rem"></i> Chat Directly on WhatsApp
      </a>

      <!-- Map -->
      <div class="map-wrap mt-4">
        <iframe
          src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3914.1234567890!2d76.0000000!3d11.0000000!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zVmV0dGlra2F0dGlyaSwgS2VyYWxh!5e0!3m2!1sen!2sin!4v1700000000000!5m2!1sen!2sin"
          allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade">
        </iframe>
      </div>
    </div>

  </div>
</div>

<div class="kstrip"></div>
<div class="mini-footer">© <?= date('Y') ?> <b><?= h(CLUB_NAME) ?></b> · <?= h(CLUB_PLACE) ?> · All rights reserved</div>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script>
function sendContact() {
  var n=$('#cName').val().trim(), e=$('#cEmail').val().trim();
  var s=$('#cSubject').val().trim(), m=$('#cMsg').val().trim();
  if (!n||!m) { showA('err','<i class="fas fa-exclamation-circle me-1"></i>Name and message are required.'); return; }
  showA('ok','<i class="fas fa-spinner fa-spin me-1"></i>Sending…');
  $('#btnSend').prop('disabled',true);
  $.ajax({
    url:'', method:'POST',
    data:{ajax:'1',action:'contact',name:n,email:e,subject:s,message:m},
    dataType:'json',
    success:function(d){
      if(d.ok){ $('#contactFormWrap').hide(); $('#contactSuccess').show(); $('#contactAlert').hide(); }
      else { $('#btnSend').prop('disabled',false); showA('err','<i class="fas fa-times-circle me-1"></i>'+d.msg); }
    },
    error:function(){ $('#btnSend').prop('disabled',false); showA('err','Network error. Please try WhatsApp.'); }
  });
}
function showA(type,msg){ $('#contactAlert').removeClass('err ok').addClass(type).html(msg).show(); }

// Reveal animations
var obs=new IntersectionObserver(function(e){e.forEach(function(x){if(x.isIntersecting)$(x.target).addClass('in');});},{threshold:.1});
$('.rv,.rl,.rr').each(function(){obs.observe(this);});
</script>
</body>
</html>
