<?php
// ================================================================
// wa_worker.php — sends queued WhatsApp messages (events, approvals, blood, fees)
//
// 1) Best: a hosting cron job every minute:
//      curl -s "https://YOUR-SITE/modules/wa_worker.php?key=CRON_KEY" >/dev/null
//    (the exact line is shown in Club Settings → WhatsApp)
// 2) Fallback: pages call this with ?lazy=1 while members use the site
//    (a few messages at a time).
// ================================================================
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/wa_gateway.php';
header('Content-Type: application/json');
header('Cache-Control: no-store');

if (!wa_enabled()) { echo json_encode(array('ok' => false, 'msg' => 'off')); exit; }

$key = isset($_GET['key']) ? (string)$_GET['key'] : '';
$cronKey = wa_cfg('wa_cron_key');
$isCron = $cronKey !== '' && $key !== '' && hash_equals($cronKey, $key);

if (!$isCron) {
    // lazy mode: only for logged-in visitors, at most once every 50 seconds, 3 messages
    if (empty($_GET['lazy']) || !isLoggedIn()) { http_response_code(403); echo json_encode(array('ok' => false)); exit; }
    $last = (int)wa_cfg('wa_last_lazy', '0');
    if (time() - $last < 50) { echo json_encode(array('ok' => true, 'skipped' => true)); exit; }
    try {
        db()->prepare("INSERT INTO club_settings(setting_key,setting_value,setting_group) VALUES('wa_last_lazy',?,'whatsapp') ON DUPLICATE KEY UPDATE setting_value=?")
            ->execute(array((string)time(), (string)time()));
    } catch (Exception $e) {}
}

ignore_user_abort(true);
@set_time_limit(150);
$daily = wa_daily_jobs();
$r = wa_process_queue($isCron ? 12 : 3);
echo json_encode(array('ok' => true, 'queued_reminders' => $daily, 'sent' => $r['sent'], 'failed' => $r['failed'], 'left' => wa_queue_pending()));
