<?php
// Payment receipt (same layout as the paper receipt). Admins open it by id; members open it from
// the WhatsApp link, which carries a signature (k) so other receipts cannot be guessed.

require __DIR__ . '/includes/init.php';

$id = (int)get('id');
$isAdmin = admin() !== null;
if (!$isAdmin && !hash_equals(sign('receipt' . $id), get('k'))) {
    $member = member_user();
    $own = $member && q('SELECT COUNT(*) FROM payments WHERE id = ? AND member_id = ?', [$id, $member['id']])->fetchColumn();
    if (!$own) {
        redirect('login.php');
    }
}
$p = q('SELECT p.*, m.name, m.address, m.place, m.adm_no, m.phone, m.expiry_date, pl.name plan_name, pl.duration_value, pl.duration_unit
        FROM payments p JOIN members m ON m.id = p.member_id LEFT JOIN plans pl ON pl.id = p.plan_id WHERE p.id = ?', [$id])->fetch();
if (!$p) {
    http_response_code(404);
    exit('Not found');
}
$balance = member_balance((int)$p['member_id']);
$months = $p['plan_id'] && $p['duration_unit'] === 'month' ? (int)$p['duration_value'] : 0;
$inBoxes = in_array($months, [1, 3, 6], true);
$link = base_url() . 'receipt.php?id=' . $id . '&k=' . sign('receipt' . $id);
$waText = t('wa_receipt', $p['name'], gym_title(), $p['receipt_no'], money($p['paid']), fdate($p['pay_date']))
    . ($p['period_end'] ? "\n" . t('valid_till') . ': ' . fdate($p['period_end']) : '')
    . ($balance > 0 ? "\n" . t('balance') . ': ' . money($balance) : '')
    . "\n\n" . t('receipt') . ': ' . $link
    . ($balance > 0 ? upi_text($balance) : '');
$addr = implode(', ', array_filter([$p['address'], $p['place']]));
$amt = fn($n) => $n > 0 ? money($n) : '';
?><!doctype html>
<html lang="<?= e(lang()) ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e(t('receipt')) ?> #<?= (int)$p['receipt_no'] ?></title>
<?= og_tags(t('receipt') . ' #' . (int)$p['receipt_no']) ?>
<link rel="stylesheet" href="assets/print.css?v=4">
</head>
<body>
<div class="toolbar">
  <button onclick="window.print()">🖨 <?= e(t('print')) ?> / PDF</button>
  <?php if ($isAdmin): ?>
    <a class="wa" href="<?= e(wa_link($p['phone'], $waText)) ?>" target="_blank" rel="noopener">WhatsApp</a>
    <a href="member_view.php?id=<?= (int)$p['member_id'] ?>">← <?= e(t('back')) ?></a>
    <a href="payment_add.php?edit=<?= (int)$p['id'] ?>">✎ <?= e(t('edit')) ?> / <?= e(t('delete')) ?></a>
    <a href="payment_add.php">+ <?= e(t('record_payment')) ?></a>
  <?php elseif (member_user()): ?>
    <a href="me.php">← <?= e(t('back')) ?></a>
  <?php endif; ?>
</div>
<div class="sheet receipt">
  <div class="head">
    <div class="brand-name"><div class="b1"><?= e(setting('gym_name', 'VALLEY MMA')) ?></div><div class="b2"><?= e(setting('gym_tagline', 'FIGHT CLUB')) ?></div><div class="b3"><?= e(setting('gym_place', 'PANDIKKAD')) ?></div></div>
    <div class="phones">☎ <?= e(setting('phone1')) ?><br><?= e(setting('phone2')) ?></div>
  </div>
  <div class="meta">
    <p class="line"><span><?= e(t('rec_no')) ?></span><b class="s"><?= (int)$p['receipt_no'] ?></b><span style="margin-left:auto"><?= e(t('date')) ?>:</span><b class="s"><?= e(fdate($p['pay_date'])) ?></b></p>
    <p class="line"><span><?= e(t('name')) ?>:</span><b><?= e($p['name']) ?></b></p>
    <p class="line"><span><?= e(t('address')) ?>:</span><b><?= e($addr) ?></b><span><?= e(t('adm_no')) ?>:</span><b class="s"><?= e($p['adm_no']) ?></b></p>
  </div>
  <table>
    <tr><th style="width:68%"><?= e(t('particulars')) ?></th><th><?= e(t('amount')) ?></th></tr>
    <tr><td class="r"><?= e(t('admission_fee')) ?></td><td class="amt"><?= $amt((float)$p['admission_fee']) ?></td></tr>
  </table>
  <table class="months">
    <tr>
      <td><?= e(t('one_month')) ?></td><td class="v"><?= $months === 1 ? money($p['plan_fee']) : '' ?></td>
      <td><?= e(t('three_months')) ?></td><td class="v"><?= $months === 3 ? money($p['plan_fee']) : '' ?></td>
      <td><?= e(t('six_months')) ?></td><td class="v"><?= $months === 6 ? money($p['plan_fee']) : '' ?></td>
    </tr>
  </table>
  <table>
    <?php if ($p['plan_id'] && !$inBoxes): ?>
      <tr><td class="r" style="width:68%"><?= e($p['plan_name']) ?></td><td class="amt"><?= money($p['plan_fee']) ?></td></tr>
    <?php endif; ?>
    <?php if ($p['period_start']): ?>
      <tr><td class="r" style="width:68%;font-weight:400"><?= e(t('period')) ?>: <?= e(fdate($p['period_start'])) ?> – <?= e(fdate($p['period_end'])) ?></td><td class="amt"></td></tr>
    <?php endif; ?>
    <tr><td class="r" style="width:68%"><?= e(t('other_fee')) ?><?= $p['other_note'] !== '' ? ' (' . e($p['other_note']) . ')' : '' ?></td><td class="amt"><?= $amt((float)$p['other_fee']) ?></td></tr>
    <tr class="total"><td class="r"><?= e(t('total')) ?></td><td class="amt"><?= money($p['total']) ?></td></tr>
    <tr><td class="r"><?= e(t('paid')) ?> (<?= e(t('m_' . $p['method'])) ?><?= $p['upi_ref'] !== '' ? ' · ' . e($p['upi_ref']) : '' ?>)</td><td class="amt"><?= money($p['paid']) ?></td></tr>
    <tr><td class="r"><?= e(t('balance_due')) ?></td><td class="amt"><?= money(max(0, $balance)) ?></td></tr>
  </table>
  <div class="foot">
    <div class="upi">
      <?php if ($balance > 0 && setting('upi_id') !== ''): ?>
        <div data-qr="<?= e(upi_link($balance, t_en('balance') . ' ' . $p['adm_no'])) ?>"></div>
        <div><?= e(t('scan_to_pay')) ?><br><b><?= e(setting('upi_id')) ?></b></div>
      <?php elseif ($p['note'] !== ''): ?>
        <div><?= e($p['note']) ?></div>
      <?php else: ?>
        <span class="paid-stamp"><?= e(t('thank_you')) ?></span>
      <?php endif; ?>
    </div>
    <div style="text-align:center"><br><br><?= e(t('signature')) ?></div>
  </div>
</div>
<script src="assets/vendor/qrcode.js"></script>
<script src="assets/qr.js"></script>
</body>
</html>
