<?php
// Member ID card with a QR code. The admin scans it on the Attendance page to mark the member present.

require __DIR__ . '/includes/init.php';
require_admin();

$m = q('SELECT * FROM members WHERE id = ?', [(int)get('id')])->fetch();
if (!$m) {
    redirect('members.php');
}
?><!doctype html>
<html lang="<?= e(lang()) ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e(t('id_card')) ?> – <?= e($m['name']) ?></title>
<link rel="stylesheet" href="assets/print.css?v=4">
</head>
<body>
<div class="toolbar">
  <button onclick="window.print()">🖨 <?= e(t('print')) ?> / PDF</button>
  <a href="member_view.php?id=<?= (int)$m['id'] ?>">← <?= e(t('back')) ?></a>
</div>
<div class="sheet idcard">
  <div class="left">
    <img src="<?= e(photo_url($m)) ?>" alt="">
    <div class="no"><?= e($m['adm_no']) ?></div>
  </div>
  <div class="right">
    <div class="b1"><?= e(setting('gym_name', 'VALLEY MMA')) ?></div>
    <div class="b2"><?= e(setting('gym_tagline', 'FIGHT CLUB')) ?> · <?= e(setting('gym_place', 'PANDIKKAD')) ?></div>
    <div class="nm"><?= e($m['name']) ?></div>
    <div class="ph"><?= e($m['phone']) ?><?= $m['blood_group'] ? ' · ' . e($m['blood_group']) : '' ?></div>
    <div class="qr"><div data-qr="VMMA:<?= e($m['card_token']) ?>"></div><div><?= e(t('scan_for_attendance')) ?><br><?= e(setting('phone1')) ?></div></div>
  </div>
</div>
<script src="assets/vendor/qrcode.js"></script>
<script src="assets/qr.js"></script>
</body>
</html>
