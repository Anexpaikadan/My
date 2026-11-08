<?php
// ============================================================
// push_notify.php — Web Push Notification System
// ============================================================
require_once __DIR__ . '/includes/config.php';

define('VAPID_PUBLIC',  'BPtQ21rs0CVf06l96ac3-SGEZCtWrMhgU11llT4YoVT3HMRRqELNKowuLmIlWrbzBMjmeJTTZF58pc6e5VtY9t8');
define('VAPID_PRIVATE', '5mbWgIq6VtLXQJ20YvcyG8aNrc3EjiAiNCub7Sc8998');
define('VAPID_SUBJECT', 'mailto:admin@mynamecc.online');

// ── Tables ──────────────────────────────────────────────────
try { db()->exec("CREATE TABLE IF NOT EXISTS push_subscriptions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  endpoint VARCHAR(1000) NOT NULL,
  p256dh VARCHAR(500) NOT NULL,
  auth VARCHAR(200) NOT NULL,
  device VARCHAR(50) DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY one_endpoint (user_id, endpoint(200))
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS push_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sent_by INT NOT NULL,
  title VARCHAR(200) NOT NULL,
  body TEXT NOT NULL,
  url VARCHAR(500) DEFAULT '/',
  sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  total_sent INT DEFAULT 0
)"); } catch(Exception $e){}

header('Content-Type: application/json');
$act = $_POST['action'] ?? $_GET['action'] ?? '';

// ── SUBSCRIBE ────────────────────────────────────────────────
if ($act === 'subscribe') {
  requireLogin();
  $me   = currentUser();
  $uid  = (int)$me['id'];
  $ep   = trim($_POST['endpoint'] ?? '');
  $p256 = trim($_POST['p256dh']   ?? '');
  $auth = trim($_POST['auth']     ?? '');
  $dev  = trim($_POST['device']   ?? '');
  if (!$ep || !$p256 || !$auth) { echo json_encode(['ok'=>false,'msg'=>'Missing data']); exit; }
  try {
    db()->prepare("INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth,device) VALUES(?,?,?,?,?)
      ON DUPLICATE KEY UPDATE p256dh=VALUES(p256dh),auth=VALUES(auth),device=VALUES(device)")
       ->execute([$uid,$ep,$p256,$auth,$dev]);
    echo json_encode(['ok'=>true,'msg'=>'Subscribed!']); exit;
  } catch(Exception $e){ echo json_encode(['ok'=>false,'msg'=>$e->getMessage()]); exit; }
}

// ── UNSUBSCRIBE ──────────────────────────────────────────────
if ($act === 'unsubscribe') {
  requireLogin();
  $me  = currentUser(); $uid=(int)$me['id'];
  $ep  = trim($_POST['endpoint'] ?? '');
  db()->prepare("DELETE FROM push_subscriptions WHERE user_id=? AND endpoint=?")->execute([$uid,$ep]);
  echo json_encode(['ok'=>true]); exit;
}

// ── SEND ─────────────────────────────────────────────────────
if ($act === 'send') {
  requireLogin();
  $me = currentUser();
  if (!isAdminRole($me['role'])) { echo json_encode(['ok'=>false,'msg'=>'Admin only']); exit; }

  $title  = trim($_POST['title']  ?? '');
  $body   = trim($_POST['body']   ?? '');
  $url    = trim($_POST['url']    ?? '/');
  $target = $_POST['target']      ?? 'all';
  $uid2   = (int)($_POST['user_id'] ?? 0);
  if (!$title || !$body) { echo json_encode(['ok'=>false,'msg'=>'Title and body required']); exit; }

  if ($target === 'specific' && $uid2) {
    $st = db()->prepare("SELECT * FROM push_subscriptions WHERE user_id=?");
    $st->execute([$uid2]); $subs = $st->fetchAll();
  } else {
    $subs = db()->query("SELECT * FROM push_subscriptions")->fetchAll();
  }

  $payload = json_encode([
    'title' => $title,
    'body'  => $body,
    'icon'  => rtrim(SITE_URL,'/').'/assets/logo.jpg',
    'badge' => rtrim(SITE_URL,'/').'/assets/logo.jpg',
    'url'   => strpos($url,'http')===0 ? $url : rtrim(SITE_URL,'/').$url,
  ]);

  $sent=0; $failed=0;
  foreach ($subs as $sub) {
    $ok = vapidSend($sub['endpoint'], $sub['p256dh'], $sub['auth'], $payload);
    if ($ok) { $sent++; } else {
      $failed++;
      db()->prepare("DELETE FROM push_subscriptions WHERE id=?")->execute([$sub['id']]);
    }
  }

  try {
    db()->prepare("INSERT INTO push_log(sent_by,title,body,url,total_sent) VALUES(?,?,?,?,?)")
       ->execute([(int)$me['id'],$title,$body,$url,$sent]);
  } catch(Exception $e){}

  echo json_encode(['ok'=>true,'sent'=>$sent,'failed'=>$failed]); exit;
}

// ── STATS ────────────────────────────────────────────────────
if ($act === 'stats') {
  requireLogin();
  $me = currentUser();
  if (!isAdminRole($me['role'])) { echo json_encode(['ok'=>false]); exit; }
  $total = (int)db()->query("SELECT COUNT(DISTINCT user_id) FROM push_subscriptions")->fetchColumn();
  try {
    $logs = db()->query("SELECT pl.*,u.name sender FROM push_log pl JOIN users u ON u.id=pl.sent_by ORDER BY pl.sent_at DESC LIMIT 10")->fetchAll();
  } catch(Exception $e){ $logs=[]; }
  echo json_encode(['ok'=>true,'subscribers'=>$total,'logs'=>$logs]); exit;
}

// ── CHECK ────────────────────────────────────────────────────
if ($act === 'check') {
  requireLogin();
  $me  = currentUser(); $uid=(int)$me['id'];
  $ep  = trim($_POST['endpoint'] ?? '');
  $ck  = db()->prepare("SELECT id FROM push_subscriptions WHERE user_id=? AND endpoint=?");
  $ck->execute([$uid,$ep]);
  echo json_encode(['ok'=>true,'subscribed'=>(bool)$ck->fetch()]); exit;
}

echo json_encode(['ok'=>false,'msg'=>'Unknown action']); exit;

// ═══════════════════════════════════════════════════════════
// VAPID Push Sender
// ═══════════════════════════════════════════════════════════
function vapidSend($endpoint, $p256dh, $auth, $payload) {
  $aud = parse_url($endpoint, PHP_URL_SCHEME).'://'.parse_url($endpoint, PHP_URL_HOST);
  $exp = time() + 43200;

  // Build JWT
  $jwtHeader  = b64ue(json_encode(['typ'=>'JWT','alg'=>'ES256']));
  $jwtPayload = b64ue(json_encode(['aud'=>$aud,'exp'=>$exp,'sub'=>VAPID_SUBJECT]));
  $jwtUnsigned= $jwtHeader.'.'.$jwtPayload;

  // Build EC private key PEM from raw bytes
  $privRaw = b64ud(VAPID_PRIVATE);
  // PKCS8 format
  $oidSeq  = "\x30\x13\x06\x07\x2a\x86\x48\xce\x3d\x02\x01\x06\x08\x2a\x86\x48\xce\x3d\x03\x01\x07";
  $ecPriv  = "\x30\x25\x02\x01\x01\x04\x20".$privRaw;
  $pkcs8   = "\x30\x41\x02\x01\x00".$oidSeq."\x04\x27".$ecPriv;
  $pem     = "-----BEGIN PRIVATE KEY-----\n".chunk_split(base64_encode($pkcs8),64,"\n")."-----END PRIVATE KEY-----";

  $privKey = openssl_pkey_get_private($pem);
  if (!$privKey) {
    // Try alternate format
    return vapidSendSimple($endpoint, $payload);
  }

  $sig = '';
  if (!openssl_sign($jwtUnsigned, $sig, $privKey, OPENSSL_ALGO_SHA256)) {
    return vapidSendSimple($endpoint, $payload);
  }
  if (PHP_MAJOR_VERSION < 8) openssl_free_key($privKey);

  $jwt = $jwtUnsigned.'.'.b64ue(derToRS($sig));

  $headers = [
    'Authorization: vapid t='.$jwt.',k='.VAPID_PUBLIC,
    'Content-Type: application/json',
    'TTL: 86400',
    'Content-Length: '.strlen($payload),
  ];

  return curlPost($endpoint, $payload, $headers);
}

// Fallback: send without body encryption (works for some push services)
function vapidSendSimple($endpoint, $payload) {
  return curlPost($endpoint, $payload, [
    'Content-Type: application/json',
    'TTL: 86400',
    'Content-Length: '.strlen($payload),
  ]);
}

function curlPost($url, $body, $headers) {
  $ch = curl_init($url);
  curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => $body,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER     => $headers,
    CURLOPT_TIMEOUT        => 15,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_FOLLOWLOCATION => true,
  ]);
  $resp = curl_exec($ch);
  $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
  $err  = curl_error($ch);
  curl_close($ch);
  // 201 = created, 200 = ok, 202 = accepted
  return ($code >= 200 && $code < 300);
}

// Convert DER-encoded ECDSA signature to raw R|S (64 bytes)
function derToRS($der) {
  $offset = 3;
  if (strlen($der) > 2 && ord($der[1]) === 0x81) $offset = 4;
  $rLen = ord($der[$offset]);
  $r    = substr($der, $offset+1, $rLen);
  $sOff = $offset+2+$rLen;
  $sLen = ord($der[$sOff]);
  $s    = substr($der, $sOff+1, $sLen);
  $r = str_pad(ltrim($r,"\x00"), 32, "\x00", STR_PAD_LEFT);
  $s = str_pad(ltrim($s,"\x00"), 32, "\x00", STR_PAD_LEFT);
  return $r.$s;
}

function b64ue($data) { return rtrim(strtr(base64_encode($data),'+/','-_'),'='); }
function b64ud($data) { return base64_decode(strtr($data,'-_','+/').str_repeat('=',(4-strlen($data)%4)%4)); }
