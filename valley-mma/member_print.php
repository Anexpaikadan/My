<?php
// Printable join form (same layout as the paper form). Without ?id it prints an empty form.

require __DIR__ . '/includes/init.php';
require_admin();

$m = q('SELECT * FROM members WHERE id = ?', [(int)get('id')])->fetch() ?: [];
$v = fn($k) => e($m[$k] ?? '');
$box = fn(bool $on) => '<span class="box">' . ($on ? '✓' : '') . '</span>';
?><!doctype html>
<html lang="<?= e(lang()) ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e(t('join_form')) ?><?= $m ? ' – ' . e($m['name']) : '' ?></title>
<link rel="stylesheet" href="assets/print.css?v=4">
</head>
<body>
<div class="toolbar"><button onclick="window.print()">🖨 <?= e(t('print')) ?> / PDF</button> <a href="<?= $m ? 'member_view.php?id=' . (int)$m['id'] : 'members.php' ?>">← <?= e(t('back')) ?></a></div>
<div class="sheet form-sheet">
  <header class="brand">
    <div class="brand-name"><div class="b1"><?= e(setting('gym_name', 'VALLEY MMA')) ?></div><div class="b2"><?= e(setting('gym_tagline', 'FIGHT CLUB')) ?></div><div class="b3"><?= e(setting('gym_place', 'PANDIKKAD')) ?></div></div>
    <div class="phones">☎ <?= e(setting('phone1')) ?><br><?= e(setting('phone2')) ?></div>
  </header>
  <div class="top-row">
    <div>
      <p class="line"><span><?= e(t('date')) ?>:</span><b><?= e($m ? fdate($m['join_date']) : '') ?></b></p>
      <p class="line"><span><?= e(t('adm_no')) ?>:</span><b><?= $v('adm_no') ?></b></p>
    </div>
    <div class="photo-box"><?php if (!empty($m['photo'])): ?><img src="<?= e(photo_url($m)) ?>" alt=""><?php else: ?><?= e(t('photo')) ?><?php endif; ?></div>
  </div>
  <div class="sec"><?= e(t('client_info')) ?></div>
  <p class="line"><span><?= e(t('name')) ?>:</span><b><?= $v('name') ?></b><span><?= e(t('address')) ?>:</span><b><?= $v('address') ?></b></p>
  <p class="line"><span><?= e(t('place')) ?>:</span><b><?= $v('place') ?></b><span><?= e(t('city')) ?>:</span><b><?= $v('city') ?></b><span><?= e(t('district')) ?>:</span><b><?= $v('district') ?></b></p>
  <p class="line"><span><?= e(t('post')) ?>:</span><b><?= $v('post') ?></b><span><?= e(t('pin_code')) ?>:</span><b><?= $v('pin_code') ?></b><span><?= e(t('state')) ?>:</span><b><?= $v('state') ?></b></p>
  <p class="line"><span><?= e(t('occupation')) ?>:</span><b><?= $v('occupation') ?></b><span><?= e(t('phone_no')) ?>:</span><b><?= $v('phone') ?></b></p>
  <p class="line"><span><?= e(t('age')) ?>:</span><b class="s"><?= $v('age') ?></b><span><?= e(t('dob')) ?>:</span><b><?= e(!empty($m['dob']) ? fdate($m['dob']) : '') ?></b>
    <span><?= e(t('gender')) ?>: M <?= $box(($m['gender'] ?? '') === 'M') ?> F <?= $box(($m['gender'] ?? '') === 'F') ?></span>
    <span><?= e(t('height')) ?>:</span><b class="s"><?= $v('height_cm') ?></b><span><?= e(t('weight')) ?>:</span><b class="s"><?= $v('weight_kg') ?></b></p>

  <div class="sec"><?= e(t('health_screening')) ?></div>
  <table class="hq">
    <?php for ($i = 1; $i <= 8; $i++): $a = $m['hq' . $i] ?? null; ?>
      <tr><td><?= $i ?>. <?= e(t('hq' . $i)) ?></td>
        <td class="yn"><?= e(t('yes')) ?> <?= $box($a !== null && (int)$a === 1) ?></td>
        <td class="yn"><?= e(t('no')) ?> <?= $box($a !== null && (int)$a === 0) ?></td></tr>
    <?php endfor; ?>
  </table>
  <p class="line"><span><?= e(t('blood_group')) ?>:</span><b class="s"><?= $v('blood_group') ?></b><span>BMI:</span><b class="s"><?= $v('bmi') ?></b>
    <span><?= e(t('urea_creat_uric')) ?>:</span><b class="s"><?= $v('urea_creat_uric') ?></b><span>HbA1c:</span><b class="s"><?= $v('hba1c') ?></b></p>

  <div class="sec"><?= e(t('client_declaration')) ?></div>
  <p class="decl"><?= !empty($m['declaration']) ? '✓ ' : '' ?><?= e(t('declaration_text')) ?></p>
  <div class="signs">
    <div><?= e(t('client_sign')) ?><br><b><?= $v('name') ?></b></div>
    <div><?= e(t('trainer_sign')) ?><br><b><?= $v('trainer_name') ?></b></div>
  </div>
</div>
</body>
</html>
