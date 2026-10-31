<?php
// henna_share.php
// MODE ?img=1&id=X  → serves static image file directly (NO DB, NO session)
// MODE ?id=X        → OG page for WhatsApp bot
// MODE (user)       → redirect to henna_fest.php

// ── OG page or user redirect ────────────────────────────────
ob_start();
if (session_status() === PHP_SESSION_NONE) session_start();
require_once __DIR__ . '/../includes/config.php';
ob_end_clean();

$SITE    = rtrim(SITE_URL, '/');
$CLUB    = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
$PLACE   = setting('CLUB_PLACE', 'Vettikkattiri');
$id      = (int)($_GET['id'] ?? 0);
$festUrl = $SITE . '/modules/henna_fest.php';

if (!$id) { header('Location: ' . $festUrl); exit; }

try {
    $st = db()->prepare("SELECT e.*, u.name member_name FROM henna_entries e JOIN users u ON u.id=e.member_id WHERE e.id=? AND e.status='active'");
    $st->execute([$id]);
    $entry = $st->fetch();
} catch(Exception $e){ $entry = null; }

if (!$entry) { header('Location: ' . $festUrl); exit; }

$memberName = $entry['member_name'];
$title      = $entry['title'] ? $entry['title'] : $memberName . "'s Mehandi Design";
// Direct static image URL — WhatsApp fetches .jpg directly (allowed by htaccess)
$ogExt = 'jpg';
foreach (['jpg','jpeg','png','webp'] as $_e) {
    if (file_exists(__DIR__ . '/../assets/uploads/henna/og/entry_' . $id . '.' . $_e)) {
        $ogExt = $_e; break;
    }
}
$imgUrl = $SITE . '/assets/uploads/henna/og/entry_' . $id . '.' . $ogExt;
$pageUrl    = $SITE . '/modules/henna_share.php?id=' . $id;
$ogTitle    = '🌿 ' . $memberName . ' — Henna Fest | ' . $CLUB;
$ogDesc     = '🎨 ' . $title . ' · Like this beautiful mehandi! — ' . $CLUB . ', ' . $PLACE;

// Real user → redirect
$ua    = isset($_SERVER['HTTP_USER_AGENT']) ? $_SERVER['HTTP_USER_AGENT'] : '';
$isBot = (bool)preg_match('/facebookexternalhit|Facebot|WhatsApp|Twitterbot|TelegramBot|LinkedInBot|Googlebot|bingbot|Slackbot|Discordbot|curl|python/i', $ua);
if (!$isBot) { header('Location: ' . $festUrl); exit; }

header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
?><!DOCTYPE html>
<html prefix="og: http://ogp.me/ns#">
<head>
<meta charset="UTF-8">
<meta property="og:type"             content="website">
<meta property="og:site_name"        content="<?= htmlspecialchars($CLUB) ?>">
<meta property="og:title"            content="<?= htmlspecialchars($ogTitle) ?>">
<meta property="og:description"      content="<?= htmlspecialchars($ogDesc) ?>">
<meta property="og:image"            content="<?= htmlspecialchars($imgUrl) ?>">
<meta property="og:image:secure_url" content="<?= htmlspecialchars($imgUrl) ?>">
<meta property="og:image:type"       content="image/jpeg">
<meta property="og:image:width"      content="800">
<meta property="og:image:height"     content="800">
<meta property="og:url"              content="<?= htmlspecialchars($pageUrl) ?>">
<meta name="twitter:card"            content="summary_large_image">
<meta name="twitter:image"           content="<?= htmlspecialchars($imgUrl) ?>">
<title><?= htmlspecialchars($ogTitle) ?></title>
</head>
<body>
<img src="<?= htmlspecialchars($imgUrl) ?>" alt="<?= htmlspecialchars($memberName) ?>">
 (https://www.instagram.com/blush.bee_ss?igsh=emlxMmF4aGtxMG11)
</body>
</html>
