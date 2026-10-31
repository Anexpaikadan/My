<?php
// ================================================================
// wa_gateway.php — send WhatsApp messages from the server
//
// Providers (Club Settings → WhatsApp):
//   off  : nothing is sent automatically (the old wa.me tap-to-send links still work)
//   gowa : self-hosted GOWA server (github.com/aldinokemal/go-whatsapp-web-multidevice)
//          POST {url}/send/message  {"phone":"91xxxxxxxxxx@s.whatsapp.net","message":"…"}  Basic Auth
//   meta : official WhatsApp Cloud API (graph.facebook.com) — needs approved templates
//
// Messages to many people go through a queue (wa_queue) and are sent slowly by
// modules/wa_worker.php (hosting cron job, or automatically while members use the site).
// OTP codes are stored hashed in wa_otps and are never sent to the browser.
// ================================================================
require_once __DIR__ . '/config.php';

if (!function_exists('wa_cfg')) {

function wa_tables() {
    static $done = false; if ($done) return; $done = true;
    try {
        db()->exec("CREATE TABLE IF NOT EXISTS wa_queue(id INT AUTO_INCREMENT PRIMARY KEY,phone VARCHAR(30) NOT NULL,message TEXT NOT NULL,
            kind VARCHAR(30) DEFAULT 'notice',status VARCHAR(12) DEFAULT 'pending',attempts INT DEFAULT 0,last_error VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,sent_at DATETIME NULL,INDEX(status))");
        db()->exec("CREATE TABLE IF NOT EXISTS wa_log(id INT AUTO_INCREMENT PRIMARY KEY,phone VARCHAR(30),kind VARCHAR(30),ok TINYINT(1),
            info VARCHAR(255),created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
        db()->exec("CREATE TABLE IF NOT EXISTS wa_otps(id INT AUTO_INCREMENT PRIMARY KEY,phone VARCHAR(30) NOT NULL,purpose VARCHAR(20) NOT NULL,
            code_hash VARCHAR(255) NOT NULL,attempts INT DEFAULT 0,used TINYINT(1) DEFAULT 0,ip VARCHAR(45),
            expires_at DATETIME NOT NULL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,INDEX(phone),INDEX(ip))");
    } catch (Exception $e) {}
}

// ── Settings (club_settings rows with keys wa_*) ──
function wa_cfg($key, $default = '') {
    static $c = null;
    if ($c === null) {
        $c = array();
        try {
            foreach (db()->query("SELECT setting_key,setting_value FROM club_settings WHERE setting_key LIKE 'wa\\_%'")->fetchAll() as $r) {
                $c[$r['setting_key']] = $r['setting_value'];
            }
        } catch (Exception $e) {}
    }
    return (isset($c[$key]) && $c[$key] !== '') ? $c[$key] : $default;
}
function wa_provider() {
    $p = wa_cfg('wa_provider', 'off');
    if ($p === 'gowa' && wa_cfg('wa_gowa_url') !== '') return 'gowa';
    if ($p === 'meta' && wa_cfg('wa_meta_token') !== '' && wa_cfg('wa_meta_phone_id') !== '') return 'meta';
    return 'off';
}
function wa_enabled()            { return wa_provider() !== 'off'; }
function wa_feature_on($feature) { return wa_enabled() && wa_cfg('wa_on_' . $feature, '1') === '1'; }

// Digits with country code, e.g. "+91 98765 43210" → "919876543210"
function wa_digits($phone) {
    $d = preg_replace('/\D/', '', (string)$phone);
    $cc = preg_replace('/\D/', '', wa_cfg('wa_country', '91'));
    if (strlen($d) === 10) $d = $cc . $d;
    if (strlen($d) === 11 && $d[0] === '0') $d = $cc . substr($d, 1);
    return $d;
}
function wa_mask($phone) { $d = wa_digits($phone); return strlen($d) > 4 ? str_repeat('•', max(0, strlen($d) - 6)) . substr($d, -4) : $d; }

function wa_log($phone, $kind, $ok, $info) {
    wa_tables();
    try { db()->prepare("INSERT INTO wa_log(phone,kind,ok,info) VALUES(?,?,?,?)")->execute(array(wa_digits($phone), $kind, $ok ? 1 : 0, mb_substr((string)$info, 0, 250))); } catch (Exception $e) {}
}

// ── Low-level HTTP ──
function wa_http($method, $url, $headers, $body = null, $basic = null) {
    if (!function_exists('curl_init')) return array(0, 'PHP cURL is not enabled on this hosting');
    $ch = curl_init($url);
    curl_setopt_array($ch, array(CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_CUSTOMREQUEST => $method, CURLOPT_HTTPHEADER => $headers));
    if ($basic) curl_setopt($ch, CURLOPT_USERPWD, $basic);
    if ($body !== null) curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
    $res = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    if ($res === false) { $err = curl_error($ch); curl_close($ch); return array(0, $err); }
    curl_close($ch);
    return array($code, $res);
}
function wa_gowa_auth() {
    $u = wa_cfg('wa_gowa_user'); $p = wa_cfg('wa_gowa_pass');
    return ($u !== '' || $p !== '') ? $u . ':' . $p : null;
}
function wa_gowa_headers() {
    $h = array('Content-Type: application/json', 'Accept: application/json');
    if (wa_cfg('wa_gowa_device') !== '') $h[] = 'X-Device-Id: ' . wa_cfg('wa_gowa_device');
    return $h;
}

// ── Send one message right now. $kind: otp | notice ; $vars used by Meta templates ──
// Returns array(ok bool, info string)
function wa_send_now($phone, $text, $kind = 'notice', $vars = array()) {
    $to = wa_digits($phone);
    if (strlen($to) < 11) { wa_log($to, $kind, false, 'Bad phone number'); return array(false, 'Bad phone number'); }
    $prov = wa_provider();
    if ($prov === 'gowa') {
        $base = rtrim(wa_cfg('wa_gowa_url'), '/');
        list($code, $res) = wa_http('POST', $base . '/send/message', wa_gowa_headers(),
            json_encode(array('phone' => $to . '@s.whatsapp.net', 'message' => $text)), wa_gowa_auth());
        $j = json_decode((string)$res, true);
        $ok = $code >= 200 && $code < 300 && (!is_array($j) || !isset($j['code']) || strtoupper($j['code']) === 'SUCCESS');
        $info = $ok ? 'Sent' : ('HTTP ' . $code . ' ' . (is_array($j) && isset($j['message']) ? $j['message'] : mb_substr((string)$res, 0, 160)));
    } elseif ($prov === 'meta') {
        $url = 'https://graph.facebook.com/v21.0/' . rawurlencode(wa_cfg('wa_meta_phone_id')) . '/messages';
        $lang = wa_cfg('wa_meta_lang', 'en');
        if ($kind === 'otp' && wa_cfg('wa_meta_tpl_otp') !== '') {
            $code6 = isset($vars['code']) ? $vars['code'] : '';
            $payload = array('messaging_product' => 'whatsapp', 'to' => $to, 'type' => 'template', 'template' => array(
                'name' => wa_cfg('wa_meta_tpl_otp'), 'language' => array('code' => $lang),
                'components' => array(
                    array('type' => 'body', 'parameters' => array(array('type' => 'text', 'text' => $code6))),
                    array('type' => 'button', 'sub_type' => 'url', 'index' => '0', 'parameters' => array(array('type' => 'text', 'text' => $code6))),
                )));
        } elseif ($kind !== 'otp' && wa_cfg('wa_meta_tpl_notice') !== '') {
            // Utility template with one {{1}} variable: Meta does not allow new lines inside variables
            $flat = trim(preg_replace('/\s*\n+\s*/u', ' · ', strip_tags($text)));
            $payload = array('messaging_product' => 'whatsapp', 'to' => $to, 'type' => 'template', 'template' => array(
                'name' => wa_cfg('wa_meta_tpl_notice'), 'language' => array('code' => $lang),
                'components' => array(array('type' => 'body', 'parameters' => array(array('type' => 'text', 'text' => mb_substr($flat, 0, 1000)))))));
        } else {
            // Plain text only reaches people who messaged the club number in the last 24 hours
            $payload = array('messaging_product' => 'whatsapp', 'to' => $to, 'type' => 'text', 'text' => array('body' => $text));
        }
        list($code, $res) = wa_http('POST', $url, array('Content-Type: application/json', 'Authorization: Bearer ' . wa_cfg('wa_meta_token')), json_encode($payload));
        $j = json_decode((string)$res, true);
        $ok = $code >= 200 && $code < 300 && !empty($j['messages']);
        $info = $ok ? 'Sent' : ('HTTP ' . $code . ' ' . (isset($j['error']['message']) ? $j['error']['message'] : mb_substr((string)$res, 0, 160)));
    } else {
        return array(false, 'WhatsApp sending is off');
    }
    wa_log($to, $kind, $ok, $info);
    return array($ok, $info);
}

// Connection check for the settings page
function wa_status() {
    $prov = wa_provider();
    if ($prov === 'gowa') {
        list($code, $res) = wa_http('GET', rtrim(wa_cfg('wa_gowa_url'), '/') . '/app/status', wa_gowa_headers(), null, wa_gowa_auth());
        $j = json_decode((string)$res, true);
        if ($code === 401) return array(false, 'Wrong username or password for the GOWA server');
        if ($code < 200 || $code >= 300) return array(false, 'Cannot reach GOWA (' . ($code ?: $res) . ')');
        $r = isset($j['results']) ? $j['results'] : array();
        if (!empty($r['is_logged_in'])) return array(true, 'Connected as ' . (isset($r['jid']) ? preg_replace('/@.*/', '', $r['jid']) : 'WhatsApp'));
        return array(false, 'GOWA is running but WhatsApp is not logged in — open the GOWA page and scan the QR code');
    }
    if ($prov === 'meta') {
        list($code, $res) = wa_http('GET', 'https://graph.facebook.com/v21.0/' . rawurlencode(wa_cfg('wa_meta_phone_id')) . '?fields=display_phone_number,verified_name',
            array('Authorization: Bearer ' . wa_cfg('wa_meta_token')));
        $j = json_decode((string)$res, true);
        if ($code >= 200 && $code < 300 && isset($j['display_phone_number'])) return array(true, 'Connected: ' . $j['display_phone_number'] . (isset($j['verified_name']) ? ' (' . $j['verified_name'] . ')' : ''));
        return array(false, isset($j['error']['message']) ? $j['error']['message'] : 'Cannot reach Meta (' . $code . ')');
    }
    return array(false, 'WhatsApp sending is off');
}

// ── Queue: for messages to many people ──
function wa_queue($phone, $text, $kind = 'notice') {
    if (!wa_enabled()) return false;
    $to = wa_digits($phone); if (strlen($to) < 11) return false;
    wa_tables();
    try { db()->prepare("INSERT INTO wa_queue(phone,message,kind) VALUES(?,?,?)")->execute(array($to, $text, $kind)); return true; } catch (Exception $e) { return false; }
}
// $users: rows with whatsapp_number. Returns how many were queued.
function wa_queue_many($users, $text, $kind = 'notice') {
    $n = 0; $seen = array();
    foreach ($users as $u) {
        $d = wa_digits(isset($u['whatsapp_number']) ? $u['whatsapp_number'] : '');
        if (isset($seen[$d])) continue; $seen[$d] = 1;
        if (wa_queue($d, $text, $kind)) $n++;
    }
    return $n;
}
function wa_queue_pending() {
    if (!wa_enabled()) return 0;
    wa_tables();
    try { return (int)db()->query("SELECT COUNT(*) FROM wa_queue WHERE status='pending'")->fetchColumn(); } catch (Exception $e) { return 0; }
}
// Send up to $max queued messages, waiting between them (protects the number from bans)
function wa_process_queue($max = 10) {
    if (!wa_enabled()) return array('sent' => 0, 'failed' => 0);
    wa_tables();
    $gap = max(1, min(30, (int)wa_cfg('wa_delay', '4')));
    $sent = 0; $failed = 0;
    try {
        $rows = db()->query("SELECT * FROM wa_queue WHERE status='pending' ORDER BY id LIMIT " . (int)$max)->fetchAll();
    } catch (Exception $e) { $rows = array(); }
    foreach ($rows as $i => $q) {
        // claim the row so two workers never send it twice
        $cl = db()->prepare("UPDATE wa_queue SET status='sending',attempts=attempts+1 WHERE id=? AND status='pending'");
        $cl->execute(array($q['id'])); if (!$cl->rowCount()) continue;
        if ($i > 0) sleep($gap);
        list($ok, $info) = wa_send_now($q['phone'], $q['message'], $q['kind']);
        if ($ok) { db()->prepare("UPDATE wa_queue SET status='sent',sent_at=NOW(),last_error=NULL WHERE id=?")->execute(array($q['id'])); $sent++; }
        else {
            $st = ((int)$q['attempts'] + 1) >= 3 ? 'failed' : 'pending';
            db()->prepare("UPDATE wa_queue SET status=?,last_error=? WHERE id=?")->execute(array($st, mb_substr($info, 0, 250), $q['id'])); $failed++;
        }
    }
    return array('sent' => $sent, 'failed' => $failed);
}

// ── One-time codes ──
// Returns array(ok bool, message for the user)
function wa_otp_send($phone, $purpose) {
    if (!wa_feature_on('otp')) return array(false, 'WhatsApp codes are not enabled.');
    wa_tables();
    $to = wa_digits($phone); $ip = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '';
    $q = db()->prepare("SELECT COUNT(*) FROM wa_otps WHERE phone=? AND created_at > (NOW() - INTERVAL 60 SECOND)"); $q->execute(array($to));
    if ((int)$q->fetchColumn() > 0) return array(false, 'Please wait a minute before asking for another code.');
    $q = db()->prepare("SELECT COUNT(*) FROM wa_otps WHERE phone=? AND created_at > (NOW() - INTERVAL 1 HOUR)"); $q->execute(array($to));
    if ((int)$q->fetchColumn() >= 5) return array(false, 'Too many codes for this number. Try again in an hour.');
    $q = db()->prepare("SELECT COUNT(*) FROM wa_otps WHERE ip=? AND created_at > (NOW() - INTERVAL 1 HOUR)"); $q->execute(array($ip));
    if ((int)$q->fetchColumn() >= 15) return array(false, 'Too many requests. Try again later.');
    $code = str_pad((string)random_int(0, 999999), 6, '0', STR_PAD_LEFT);
    $mins = 10;
    db()->prepare("UPDATE wa_otps SET used=1 WHERE phone=? AND purpose=? AND used=0")->execute(array($to, $purpose));
    db()->prepare("INSERT INTO wa_otps(phone,purpose,code_hash,ip,expires_at) VALUES(?,?,?,?,NOW() + INTERVAL $mins MINUTE)")
        ->execute(array($to, $purpose, password_hash($code, PASSWORD_DEFAULT), $ip));
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $text = "*{$code}* is your {$club} code.\n\nValid for {$mins} minutes. Do not share it with anyone — club staff will never ask for it.";
    list($ok, $info) = wa_send_now($to, $text, 'otp', array('code' => $code));
    if (!$ok) return array(false, 'Could not send the WhatsApp code right now. Please try again later.');
    return array(true, 'We sent a 6-digit code to WhatsApp ' . wa_mask($to) . '.');
}
function wa_otp_check($phone, $purpose, $code) {
    wa_tables();
    $to = wa_digits($phone); $code = preg_replace('/\D/', '', (string)$code);
    if (strlen($code) !== 6) return false;
    $q = db()->prepare("SELECT * FROM wa_otps WHERE phone=? AND purpose=? AND used=0 AND expires_at>=NOW() ORDER BY id DESC LIMIT 1");
    $q->execute(array($to, $purpose)); $row = $q->fetch();
    if (!$row) return false;
    if ((int)$row['attempts'] >= 5) { db()->prepare("UPDATE wa_otps SET used=1 WHERE id=?")->execute(array($row['id'])); return false; }
    if (!password_verify($code, $row['code_hash'])) { db()->prepare("UPDATE wa_otps SET attempts=attempts+1 WHERE id=?")->execute(array($row['id'])); return false; }
    db()->prepare("UPDATE wa_otps SET used=1 WHERE id=?")->execute(array($row['id']));
    return true;
}

// ── Message texts ──
function wa_site() { return rtrim(defined('SITE_URL') ? SITE_URL : '', '/'); }
function wa_msg_event($ev) {
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $t = "📅 *New event — {$club}*\n\n*" . $ev['title'] . "*\n";
    if (!empty($ev['event_date'])) $t .= "🗓 " . date('D, d M Y', strtotime($ev['event_date'])) . (!empty($ev['event_time']) ? ' · ' . $ev['event_time'] : '') . "\n";
    if (!empty($ev['location'])) $t .= "📍 " . $ev['location'] . "\n";
    if (!empty($ev['description'])) $t .= "\n" . mb_strimwidth($ev['description'], 0, 300, '…') . "\n";
    return $t . "\nDetails: " . wa_site() . "/modules/events.php";
}
function wa_msg_blood($bg, $patient, $hospital, $urgency) {
    $u = strtolower((string)$urgency) === 'high' ? '🚨 *URGENT* ' : '';
    return "🩸 {$u}*Blood needed: {$bg}*\n\nPatient: {$patient}\nHospital: {$hospital}\n\nIf you can donate, please open: " . wa_site() . "/modules/blood.php";
}
function wa_msg_fee($name, $validUntil) {
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $days = (int)floor((strtotime($validUntil) - strtotime(date('Y-m-d'))) / 86400);
    $when = $days > 1 ? "in {$days} days" : ($days === 1 ? 'tomorrow' : 'today');
    return "💳 Hello {$name}, your {$club} membership ends {$when} (" . date('d M Y', strtotime($validUntil)) . ").\n\nRenew here: " . wa_site() . "/modules/subscription.php";
}

// Once a day: queue fee reminders 7 days, 1 day and 0 days before expiry
function wa_daily_jobs() {
    if (!wa_feature_on('fees')) return 0;
    $today = date('Y-m-d');
    if (wa_cfg('wa_last_daily') === $today) return 0;
    try {
        db()->prepare("INSERT INTO club_settings(setting_key,setting_value,setting_group) VALUES('wa_last_daily',?,'whatsapp') ON DUPLICATE KEY UPDATE setting_value=?")->execute(array($today, $today));
        // dates from PHP (the database clock may use another time zone)
        $st = db()->prepare("SELECT u.name,u.whatsapp_number,MAX(r.valid_until) vu FROM subscription_requests r JOIN users u ON u.id=r.user_id
            WHERE r.status='approved' AND u.status='active' GROUP BY u.id,u.name,u.whatsapp_number HAVING vu IN (?,?,?)");
        $st->execute(array($today, date('Y-m-d', strtotime('+1 day')), date('Y-m-d', strtotime('+7 days'))));
        $rows = $st->fetchAll();
    } catch (Exception $e) { return 0; }
    $n = 0;
    foreach ($rows as $r) { if (wa_queue($r['whatsapp_number'], wa_msg_fee($r['name'], $r['vu']), 'fee')) $n++; }
    return $n;
}

}
