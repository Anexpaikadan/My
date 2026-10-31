<?php
// modules/webauthn.php — Fingerprint / Face ID login via WebAuthn (pure PHP, openssl)
require_once __DIR__ . '/../includes/config.php';
header('Content-Type: application/json');

// Catch ANY error/fatal and return it as JSON (so the client never gets blank output)
error_reporting(E_ALL);
ini_set('display_errors','0');
set_error_handler(function($no,$str,$file,$line){
  if (!(error_reporting() & $no)) return false;
  echo json_encode(['ok'=>false,'msg'=>'PHP error: '.$str.' (line '.$line.')']);
  exit;
});
set_exception_handler(function($e){
  echo json_encode(['ok'=>false,'msg'=>'Exception: '.$e->getMessage()]);
  exit;
});
register_shutdown_function(function(){
  $e = error_get_last();
  if ($e && in_array($e['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR])) {
    echo json_encode(['ok'=>false,'msg'=>'Fatal: '.$e['message'].' (line '.$e['line'].')']);
  }
});

// Credentials table
try {
  db()->exec("CREATE TABLE IF NOT EXISTS webauthn_credentials(
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    cred_id VARCHAR(255) NOT NULL,
    public_key TEXT NOT NULL,
    sign_count BIGINT DEFAULT 0,
    device_label VARCHAR(120) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cred (cred_id),
    INDEX idx_user (user_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (Exception $e) {}

// ── helpers ──
function b64url_encode($d){ return rtrim(strtr(base64_encode($d),'+/','-_'),'='); }
function b64url_decode($d){ $d=strtr($d,'-_','+/'); $pad=strlen($d)%4; if($pad) $d.=str_repeat('=',4-$pad); return base64_decode($d); }
function wa_rpid(){ $h=$_SERVER['HTTP_HOST'] ?? 'mynamecc.online'; return preg_replace('/:\d+$/','',$h); }
function wa_origin(){ $h=$_SERVER['HTTP_HOST'] ?? 'mynamecc.online'; return 'https://'.$h; }

$act = $_POST['act'] ?? $_GET['act'] ?? '';

// ════════════ 1) REGISTER — start (must be logged in) ════════════
if ($act === 'reg_begin') {
  $me = currentUser();
  if (!$me) { echo json_encode(['ok'=>false,'msg'=>'Please log in first.']); exit; }
  $challenge = random_bytes(32);
  $_SESSION['wa_challenge'] = $challenge;
  $_SESSION['wa_reg_uid']   = (int)$me['id'];
  echo json_encode([
    'ok'=>true,
    'options'=>[
      'challenge'=>b64url_encode($challenge),
      'rp'=>['name'=>setting('CLUB_NAME','Club'),'id'=>wa_rpid()],
      'user'=>['id'=>b64url_encode((string)$me['id']),'name'=>$me['whatsapp_number'] ?: ('user'.$me['id']),'displayName'=>$me['name']],
      'pubKeyCredParams'=>[['type'=>'public-key','alg'=>-7],['type'=>'public-key','alg'=>-257]],
      'authenticatorSelection'=>['authenticatorAttachment'=>'platform','userVerification'=>'required','residentKey'=>'preferred'],
      'timeout'=>60000,
      'attestation'=>'none'
    ]
  ]); exit;
}

// ════════════ 2) REGISTER — finish (store public key) ════════════
if ($act === 'reg_finish') {
  $uid = (int)($_SESSION['wa_reg_uid'] ?? 0);
  if (!$uid) { echo json_encode(['ok'=>false,'msg'=>'Session expired. Try again.']); exit; }
  $credId   = $_POST['cred_id'] ?? '';
  $clientJSON = b64url_decode($_POST['client_data'] ?? '');
  $attObj   = b64url_decode($_POST['att_obj'] ?? '');
  if (!$credId || !$clientJSON || !$attObj) { echo json_encode(['ok'=>false,'msg'=>'Invalid data']); exit; }

  // verify challenge + origin from clientDataJSON
  $client = json_decode($clientJSON, true);
  $expect = b64url_encode($_SESSION['wa_challenge'] ?? '');
  if (!$client || ($client['type']??'')!=='webauthn.create') { echo json_encode(['ok'=>false,'msg'=>'Bad type. Try again.']); exit; }
  if (empty($_SESSION['wa_challenge'])) { echo json_encode(['ok'=>false,'msg'=>'Session expired (challenge lost). Please reload and try again.']); exit; }
  if (($client['challenge']??'') !== $expect) { echo json_encode(['ok'=>false,'msg'=>'Challenge mismatch. Reload page and retry.']); exit; }
  $gotOrigin = $client['origin']??'';
  if ($gotOrigin !== wa_origin()) { echo json_encode(['ok'=>false,'msg'=>'Origin mismatch: got '.$gotOrigin.' expected '.wa_origin()]); exit; }

  // Parse attestationObject (CBOR) to extract the COSE public key from authData
  $pub = wa_extract_pubkey_from_attestation($attObj);
  if (!$pub) { echo json_encode(['ok'=>false,'msg'=>'Could not read key from device. Your phone may use a key type not yet supported.']); exit; }

  try {
    db()->prepare("INSERT INTO webauthn_credentials(user_id,cred_id,public_key,device_label)
      VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE public_key=VALUES(public_key)")
      ->execute([$uid,$credId,$pub, substr($_SERVER['HTTP_USER_AGENT']??'device',0,110)]);
    // verify it actually saved
    $chk = db()->prepare("SELECT COUNT(*) FROM webauthn_credentials WHERE user_id=? AND cred_id=?");
    $chk->execute([$uid,$credId]);
    if ((int)$chk->fetchColumn() < 1) { echo json_encode(['ok'=>false,'msg'=>'Save did not persist. DB issue.']); exit; }
    echo json_encode(['ok'=>true,'msg'=>'✅ Fingerprint enabled! You can now log in with your fingerprint.']);
  } catch (Exception $e) { echo json_encode(['ok'=>false,'msg'=>'Save failed: '.$e->getMessage()]); }
  exit;
}

// ════════════ 3) LOGIN — start ════════════
if ($act === 'login_begin') {
  $raw = preg_replace('/[^0-9]/','',$_POST['phone'] ?? '');
  if (strlen($raw) < 10) { echo json_encode(['ok'=>false,'msg'=>'Enter your phone number']); exit; }
  $rawLast10 = substr($raw, -10); // compare last 10 digits (ignores country code)
  // find user by phone digits (match last 10 digits, with or without country code)
  $row = null;
  foreach (db()->query("SELECT id,whatsapp_number FROM users")->fetchAll() as $u) {
    $uDigits = preg_replace('/[^0-9]/','',$u['whatsapp_number']);
    if ($uDigits===$raw || substr($uDigits,-10)===$rawLast10) { $row=$u; break; }
  }
  if (!$row) { echo json_encode(['ok'=>false,'msg'=>'Phone not registered']); exit; }
  $creds = db()->prepare("SELECT cred_id FROM webauthn_credentials WHERE user_id=?");
  $creds->execute([$row['id']]); $creds=$creds->fetchAll();
  if (!$creds) { echo json_encode(['ok'=>false,'no_bio'=>true,'msg'=>'No fingerprint set up for this account.']); exit; }
  $challenge = random_bytes(32);
  $_SESSION['wa_challenge'] = $challenge;
  $_SESSION['wa_login_uid'] = (int)$row['id'];
  $allow = array_map(function($c){ return ['type'=>'public-key','id'=>$c['cred_id']]; }, $creds);
  echo json_encode(['ok'=>true,'options'=>[
    'challenge'=>b64url_encode($challenge),
    'rpId'=>wa_rpid(),
    'allowCredentials'=>$allow,
    'userVerification'=>'required',
    'timeout'=>60000
  ]]); exit;
}

// ════════════ 4) LOGIN — finish (verify signature) ════════════
if ($act === 'login_finish') {
  $uid = (int)($_SESSION['wa_login_uid'] ?? 0);
  if (!$uid) { echo json_encode(['ok'=>false,'msg'=>'Session expired']); exit; }
  $credId    = $_POST['cred_id'] ?? '';
  $clientJSON= b64url_decode($_POST['client_data'] ?? '');
  $authData  = b64url_decode($_POST['auth_data'] ?? '');
  $sig       = b64url_decode($_POST['signature'] ?? '');
  if (!$credId || !$clientJSON || !$authData || !$sig) { echo json_encode(['ok'=>false,'msg'=>'Invalid data']); exit; }

  // verify client data
  $client = json_decode($clientJSON, true);
  $expect = b64url_encode($_SESSION['wa_challenge'] ?? '');
  if (!$client || ($client['type']??'')!=='webauthn.get') { echo json_encode(['ok'=>false,'msg'=>'Bad type']); exit; }
  if (($client['challenge']??'') !== $expect) { echo json_encode(['ok'=>false,'msg'=>'Challenge mismatch']); exit; }
  if (($client['origin']??'') !== wa_origin()) { echo json_encode(['ok'=>false,'msg'=>'Origin mismatch']); exit; }

  // fetch stored public key for this credential + user
  $c = db()->prepare("SELECT public_key FROM webauthn_credentials WHERE cred_id=? AND user_id=?");
  $c->execute([$credId,$uid]); $pem = $c->fetchColumn();
  if (!$pem) { echo json_encode(['ok'=>false,'msg'=>'Credential not found']); exit; }

  // signed data = authData || SHA256(clientDataJSON)
  $signedData = $authData . hash('sha256', $clientJSON, true);
  $okSig = openssl_verify($signedData, $sig, $pem, OPENSSL_ALGO_SHA256);
  if ($okSig !== 1) { echo json_encode(['ok'=>false,'msg'=>'Fingerprint verification failed']); exit; }

  // success — log in
  $st = db()->prepare("SELECT status FROM users WHERE id=?"); $st->execute([$uid]); $status=$st->fetchColumn();
  if ($status==='pending')  { echo json_encode(['ok'=>false,'msg'=>'Account pending approval']); exit; }
  if ($status==='rejected') { echo json_encode(['ok'=>false,'msg'=>'Account rejected']); exit; }
  $_SESSION['user_id'] = $uid;
  unset($_SESSION['wa_challenge'],$_SESSION['wa_login_uid']);
  echo json_encode(['ok'=>true,'url'=>url('dashboard.php')]); exit;
}

echo json_encode(['ok'=>false,'msg'=>'Unknown action']); exit;


// ═══════════════ CBOR / COSE helpers ═══════════════
// Extract authData from attestationObject and convert COSE EC2 (P-256) public key to PEM.
function wa_extract_pubkey_from_attestation($attObj) {
  $off = 0;
  $d = wa_cbor_decode($attObj, $off);
  if (!is_array($d) || !isset($d['authData'])) return null;
  $authData = $d['authData'];
  // authData: rpIdHash(32) + flags(1) + signCount(4) + attestedCredData...
  if (strlen($authData) < 37) return null;
  $p = 37;
  // attestedCredentialData: aaguid(16) + credIdLen(2) + credId + COSE key
  $p += 16;
  $credIdLen = (ord($authData[$p])<<8) | ord($authData[$p+1]); $p += 2;
  $p += $credIdLen;
  $cose = substr($authData, $p);
  $o = 0;
  $map = wa_cbor_decode($cose, $o);
  if (!is_array($map)) return null;
  // COSE: 1=kty,3=alg,-1=crv,-2=x,-3=y
  if (!isset($map[-2]) || !isset($map[-3])) return null;
  $x = $map[-2]; $y = $map[-3];
  if (strlen($x)!==32 || strlen($y)!==32) return null;
  return wa_ec_pubkey_to_pem($x,$y);
}

// Minimal CBOR decoder (enough for WebAuthn attestation + COSE key)
function wa_cbor_decode($data,&$off){
  $b = ord($data[$off]); $off++;
  $major = $b >> 5; $info = $b & 0x1f;
  $val = wa_cbor_len($data,$off,$info);
  switch($major){
    case 0: return $val;                      // uint
    case 1: return -1-$val;                    // negative int
    case 2: $s=substr($data,$off,$val); $off+=$val; return $s; // bytes
    case 3: $s=substr($data,$off,$val); $off+=$val; return $s; // text
    case 4: $a=[]; for($i=0;$i<$val;$i++){$a[]=wa_cbor_decode($data,$off);} return $a;
    case 5: $m=[]; for($i=0;$i<$val;$i++){$k=wa_cbor_decode($data,$off);$v=wa_cbor_decode($data,$off);$m[$k]=$v;} return $m;
    case 7: return $val;
    default: return null;
  }
}
function wa_cbor_len($data,&$off,$info){
  if ($info < 24) return $info;
  if ($info==24){ $v=ord($data[$off]); $off+=1; return $v; }
  if ($info==25){ $v=(ord($data[$off])<<8)|ord($data[$off+1]); $off+=2; return $v; }
  if ($info==26){ $v=(ord($data[$off])<<24)|(ord($data[$off+1])<<16)|(ord($data[$off+2])<<8)|ord($data[$off+3]); $off+=4; return $v; }
  if ($info==27){ $hi=(ord($data[$off])<<24)|(ord($data[$off+1])<<16)|(ord($data[$off+2])<<8)|ord($data[$off+3]); $lo=(ord($data[$off+4])<<24)|(ord($data[$off+5])<<16)|(ord($data[$off+6])<<8)|ord($data[$off+7]); $off+=8; return ($hi*4294967296)+$lo; }
  return 0;
}
// Build a P-256 EC public key PEM from raw x,y (32 bytes each) — DER wrapping
function wa_ec_pubkey_to_pem($x,$y){
  // uncompressed point: 0x04 || x || y
  $point = "\x04".$x.$y;
  // SubjectPublicKeyInfo DER for prime256v1
  $algo = hex2bin('301306072a8648ce3d020106082a8648ce3d030107');
  $bitstr = "\x03".wa_der_len(strlen($point)+1)."\x00".$point;
  $seq = $algo.$bitstr;
  $der = "\x30".wa_der_len(strlen($seq)).$seq;
  $pem = "-----BEGIN PUBLIC KEY-----\n".chunk_split(base64_encode($der),64,"\n")."-----END PUBLIC KEY-----\n";
  return $pem;
}
function wa_der_len($n){
  if ($n < 128) return chr($n);
  if ($n < 256) return "\x81".chr($n);
  return "\x82".chr($n>>8).chr($n&0xff);
}
