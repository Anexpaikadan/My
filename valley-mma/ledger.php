<?php
// Ledger: all income, expense and transfer entries (membership payments included) with filters,
// opening / closing balance and a running balance. Print / PDF / Excel.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/accounts.php';
require_admin();

$f = [
    'from' => valid_date(get('from')) ? get('from') : date('Y-m-01'),
    'to' => valid_date(get('to')) ? get('to') : today(),
    'type' => in_array(get('type'), ['income', 'expense', 'transfer'], true) ? get('type') : '',
    'category' => (int)get('category') ?: '',
    'account' => (int)get('account') ?: '',
    's' => get('s'),
];
$rows = acc_ledger($f);
$acc = (int)$f['account'];
// Running balance only makes sense when every entry of the account(s) is listed.
$running = !$f['type'] && !$f['category'] && $f['s'] === '';
$opening = $running ? acc_balance($acc, $f['from']) : 0;
$in = $out = 0;
$bal = $opening;
foreach ($rows as &$r) {
    $eff = acc_effect($r, $acc);
    if ($r['type'] === 'transfer' && !$acc) {
        $r['in'] = $r['out'] = 0;
    } else {
        $r['in'] = $eff > 0 ? $eff : ($r['type'] === 'income' ? (float)$r['amount'] : 0);
        $r['out'] = $eff < 0 ? -$eff : ($r['type'] === 'expense' ? (float)$r['amount'] : 0);
    }
    $in += $r['in'];
    $out += $r['out'];
    $bal += $r['in'] - $r['out'];
    $r['bal'] = $bal;
}
unset($r);
$accounts = acc_accounts(true);
$cats = acc_categories(null, true);
$accName = $acc ? (array_column($accounts, 'name', 'id')[$acc] ?? '') : t('all_accounts');

$title = t('ledger');
$active = 'accounts';
$back = 'accounts.php';
$actions = '<a href="entry_edit.php?type=income" class="btn btn-accent"><i class="bi bi-plus-lg"></i> <span class="d-none d-sm-inline">' . e(t('acc_income')) . '</span></a>'
    . '<a href="entry_edit.php?type=expense" class="btn btn-danger"><i class="bi bi-dash-lg"></i> <span class="d-none d-sm-inline">' . e(t('acc_expense')) . '</span></a>';
require __DIR__ . '/includes/header.php';
?>
<form class="card card-body mb-3 filters" method="get">
  <div class="row g-2">
    <div class="col-6 col-md-2"><input class="form-control" type="date" name="from" value="<?= e($f['from']) ?>" aria-label="<?= e(t('from')) ?>"></div>
    <div class="col-6 col-md-2"><input class="form-control" type="date" name="to" value="<?= e($f['to']) ?>" aria-label="<?= e(t('to')) ?>"></div>
    <div class="col-6 col-md-2"><select class="form-select" name="account" aria-label="<?= e(t('account')) ?>"><option value=""><?= e(t('all_accounts')) ?></option>
      <?php foreach ($accounts as $a): ?><option value="<?= $a['id'] ?>"<?= $acc === (int)$a['id'] ? ' selected' : '' ?>><?= e($a['name']) ?></option><?php endforeach; ?></select></div>
    <div class="col-6 col-md-2"><select class="form-select" name="type" aria-label="<?= e(t('type')) ?>"><option value=""><?= e(t('all_types')) ?></option>
      <?php foreach (['income', 'expense', 'transfer'] as $k): ?><option value="<?= $k ?>"<?= $f['type'] === $k ? ' selected' : '' ?>><?= e(t('acc_' . $k)) ?></option><?php endforeach; ?></select></div>
    <div class="col-6 col-md-2"><select class="form-select" name="category" aria-label="<?= e(t('category')) ?>"><option value=""><?= e(t('all_categories')) ?></option>
      <?php foreach ($cats as $c): ?><option value="<?= $c['id'] ?>"<?= (int)$f['category'] === (int)$c['id'] ? ' selected' : '' ?>><?= e($c['name']) ?> (<?= e(t('acc_' . $c['type'])) ?>)</option><?php endforeach; ?></select></div>
    <div class="col-6 col-md-2"><input class="form-control" type="search" name="s" value="<?= e($f['s']) ?>" placeholder="<?= e(t('search')) ?>"></div>
    <div class="col-12 d-flex gap-2 flex-wrap">
      <button class="btn btn-dark"><i class="bi bi-funnel"></i> <?= e(t('show')) ?></button>
      <?php foreach ([[today(), today(), t('today')], [date('Y-m-01'), today(), t('this_month')],
          [date('Y-m-01', strtotime('first day of last month')), date('Y-m-t', strtotime('first day of last month')), t('last_month')],
          [date('Y-01-01'), today(), t('this_year')]] as [$a, $b, $l]): ?>
        <a class="btn btn-sm btn-light align-self-center" href="?<?= e(http_build_query(array_merge($f, ['from' => $a, 'to' => $b]))) ?>"><?= e($l) ?></a>
      <?php endforeach; ?>
    </div>
  </div>
</form>

<div class="row g-3 mb-3">
  <?php if ($running): ?><div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('opening_balance')) ?></div><div class="num"><?= money($opening) ?></div></div></div></div><?php endif; ?>
  <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e($acc ? t('money_in') : t('acc_income')) ?></div><div class="num text-success"><?= money($in) ?></div></div></div></div>
  <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e($acc ? t('money_out') : t('acc_expense')) ?></div><div class="num text-danger"><?= money($out) ?></div></div></div></div>
  <?php if ($running): ?><div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('closing_balance')) ?></div><div class="num text-primary"><?= money($bal) ?></div></div></div></div><?php endif; ?>
</div>

<div class="card">
  <div class="card-header d-flex flex-wrap gap-2 align-items-center">
    <span class="me-auto"><?= e($accName) ?> · <?= e(fdate($f['from'])) ?> – <?= e(fdate($f['to'])) ?> (<?= count($rows) ?>)</span>
    <?php require __DIR__ . '/includes/export_buttons.php'; ?>
  </div>
  <div class="table-responsive">
    <table class="table table-hover table-cards" id="reportTable" data-title="Ledger <?= e(($acc ? $accName . ' ' : '') . fdate($f['from']) . ' - ' . fdate($f['to'])) ?>">
      <thead><tr><th data-en="Date"><?= e(t('date')) ?></th><th data-en="No"><?= e(t('voucher_no')) ?></th><th data-en="Particulars"><?= e(t('particulars')) ?></th>
        <th data-en="Account"><?= e(t('account')) ?></th><th class="text-end" data-en="In"><?= e(t('money_in')) ?></th><th class="text-end" data-en="Out"><?= e(t('money_out')) ?></th>
        <?php if ($running): ?><th class="text-end" data-en="Balance"><?= e(t('balance')) ?></th><?php endif; ?><th class="no-export"></th></tr></thead>
      <tbody>
      <?php if ($running): ?>
        <tr class="table-light"><td class="td-main" colspan="4" data-en="Opening balance"><b><?= e(t('opening_balance')) ?></b></td><td></td><td></td><td class="text-end fw-bold"><?= money($opening) ?></td><td class="no-export"></td></tr>
      <?php endif; ?>
      <?php if (!$rows): ?><tr><td colspan="8" class="text-center text-muted p-4"><?= e(t('nothing_here')) ?></td></tr><?php endif; ?>
      <?php foreach ($rows as $r):
          $isPay = $r['src'] === 'payment';
          $label = $r['type'] === 'transfer' ? t('acc_transfer') . ': ' . $r['account'] . ' → ' . $r['to_account'] : ($r['category'] ?? '–');
          $sub = trim($r['party'] . ($r['description'] !== '' ? ' · ' . $r['description'] : ''), ' ·'); ?>
        <tr>
          <td class="td-main"><span class="fw-semibold"><?= e(fdate($r['d'])) ?></span> <span class="d-md-none"><?= acc_type_badge($r['type']) ?></span></td>
          <td data-label="<?= e(t('voucher_no')) ?>"><?= $isPay ? 'R' : 'V' ?><?= (int)$r['no'] ?></td>
          <td data-label="<?= e(t('particulars')) ?>"><span class="fw-semibold"><?= e($label) ?></span><?= $sub !== '' ? '<br><span class="small-muted">' . e($sub) . '</span>' : '' ?></td>
          <td data-label="<?= e(t('account')) ?>"><?= e($r['type'] === 'transfer' ? '' : $r['account']) ?></td>
          <td data-label="<?= e(t('money_in')) ?>" class="text-end text-success fw-semibold"><?= $r['in'] ? money($r['in']) : '' ?></td>
          <td data-label="<?= e(t('money_out')) ?>" class="text-end text-danger fw-semibold"><?= $r['out'] ? money($r['out']) : '' ?></td>
          <?php if ($running): ?><td data-label="<?= e(t('balance')) ?>" class="text-end"><?= money($r['bal']) ?></td><?php endif; ?>
          <td class="td-actions text-end text-nowrap no-export">
            <?php if ($isPay): ?><a class="btn btn-sm btn-outline-primary" href="receipt.php?id=<?= (int)$r['id'] ?>" title="<?= e(t('receipt')) ?>"><i class="bi bi-receipt"></i></a>
            <?php else: ?>
              <a class="btn btn-sm btn-outline-secondary" href="voucher.php?id=<?= (int)$r['id'] ?>" title="<?= e(t('voucher')) ?>"><i class="bi bi-printer"></i></a>
              <a class="btn btn-sm btn-outline-primary" href="entry_edit.php?id=<?= (int)$r['id'] ?>" title="<?= e(t('edit')) ?>"><i class="bi bi-pencil"></i></a>
            <?php endif; ?>
          </td>
        </tr>
      <?php endforeach; ?>
      </tbody>
      <tfoot><tr class="fw-bold"><td colspan="4" data-en="Total"><?= e(t('total')) ?></td><td class="text-end"><?= money($in) ?></td><td class="text-end"><?= money($out) ?></td>
        <?php if ($running): ?><td class="text-end"><?= money($bal) ?></td><?php endif; ?><td class="no-export"></td></tr></tfoot>
    </table>
  </div>
</div>
<p class="small-muted mt-2"><i class="bi bi-info-circle"></i> <?= e(t('ledger_note')) ?></p>
<?php
$scripts = ['assets/vendor/jspdf.umd.min.js', 'assets/vendor/jspdf.plugin.autotable.min.js'];
require __DIR__ . '/includes/footer.php';
