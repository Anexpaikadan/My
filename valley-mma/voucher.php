<?php
// Printable voucher for an income, expense or transfer entry.

require __DIR__ . '/includes/init.php';
require_admin();

$r = q('SELECT e.*, c.name category, a.name account, ta.name to_account, ad.username created
        FROM acc_entries e LEFT JOIN acc_categories c ON c.id = e.category_id LEFT JOIN acc_accounts a ON a.id = e.account_id
        LEFT JOIN acc_accounts ta ON ta.id = e.to_account_id LEFT JOIN admins ad ON ad.id = e.created_by WHERE e.id = ?', [(int)get('id')])->fetch();
if (!$r) {
    redirect('ledger.php');
}
$head = ['income' => t('receipt_voucher'), 'expense' => t('payment_voucher'), 'transfer' => t('transfer_voucher')][$r['type']];
?><!doctype html>
<html lang="<?= e(lang()) ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($head) ?> V<?= (int)$r['voucher_no'] ?></title>
<link rel="stylesheet" href="assets/print.css?v=4">
</head>
<body>
<div class="toolbar">
  <button onclick="window.print()">🖨 <?= e(t('print')) ?> / PDF</button>
  <a href="entry_edit.php?id=<?= (int)$r['id'] ?>">✎ <?= e(t('edit')) ?></a>
  <a href="ledger.php">← <?= e(t('ledger')) ?></a>
  <a href="entry_edit.php?type=<?= e($r['type']) ?>">+ <?= e(t('add_' . $r['type'])) ?></a>
</div>
<div class="sheet receipt">
  <div class="head">
    <div class="brand-name"><div class="b1"><?= e(setting('gym_name', 'VALLEY MMA')) ?></div><div class="b2"><?= e(setting('gym_tagline', 'FIGHT CLUB')) ?></div><div class="b3"><?= e(setting('gym_place', 'PANDIKKAD')) ?></div></div>
    <div class="phones">☎ <?= e(setting('phone1')) ?><br><?= e(setting('phone2')) ?></div>
  </div>
  <div class="voucher-title"><?= e($head) ?></div>
  <div class="meta">
    <p class="line"><span><?= e(t('rec_no')) ?></span><b class="s">V<?= (int)$r['voucher_no'] ?></b><span style="margin-left:auto"><?= e(t('date')) ?>:</span><b class="s"><?= e(fdate($r['entry_date'])) ?></b></p>
    <?php if ($r['type'] !== 'transfer'): ?>
      <p class="line"><span><?= e($r['type'] === 'income' ? t('received_from') : t('paid_to')) ?>:</span><b><?= e($r['party']) ?></b></p>
    <?php endif; ?>
  </div>
  <table>
    <tr><th style="width:68%"><?= e(t('particulars')) ?></th><th><?= e(t('amount')) ?></th></tr>
    <tr><td class="r" style="text-align:left">
      <?= e($r['type'] === 'transfer' ? $r['account'] . ' → ' . $r['to_account'] : $r['category']) ?>
      <?php if ($r['description'] !== ''): ?><br><span style="font-weight:400"><?= e($r['description']) ?></span><?php endif; ?>
    </td><td class="amt"><?= money($r['amount']) ?></td></tr>
    <?php if ($r['type'] !== 'transfer'): ?><tr><td class="r" style="text-align:left;font-weight:400"><?= e(t('account')) ?>: <?= e($r['account']) ?><?= $r['ref_no'] !== '' ? ' · ' . e(t('ref_no')) . ': ' . e($r['ref_no']) : '' ?></td><td class="amt"></td></tr><?php endif; ?>
    <tr class="total"><td class="r"><?= e(t('total')) ?></td><td class="amt"><?= money($r['amount']) ?></td></tr>
  </table>
  <div class="foot">
    <div><?= e(t('prepared_by')) ?>: <?= e($r['created'] ?? '') ?><br><br><?= e(t('receiver_sign')) ?></div>
    <div style="text-align:center"><br><br><?= e(t('signature')) ?></div>
  </div>
</div>
</body>
</html>
