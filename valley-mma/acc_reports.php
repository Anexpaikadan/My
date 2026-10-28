<?php
// Accounts reports: profit & loss (income and expense by category), monthly summary for a year,
// and the cash book (one account, one day or period, with opening and closing balance).

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/accounts.php';
require_admin();

$r = in_array(get('r'), ['pl', 'monthly', 'cashbook'], true) ? get('r') : 'pl';
$from = valid_date(get('from')) ? get('from') : ($r === 'cashbook' ? today() : date('Y-m-01'));
$to = valid_date(get('to')) ? get('to') : today();
$year = preg_match('/^\d{4}$/', get('year')) ? get('year') : date('Y');
$accounts = acc_accounts(true);
$acc = (int)get('account') ?: (int)($accounts[0]['id'] ?? 1);

$tabs = ['pl' => ['bi-graph-up-arrow', t('profit_loss')], 'monthly' => ['bi-calendar3', t('monthly_summary')], 'cashbook' => ['bi-book', t('cash_book')]];
$title = t('acc_reports');
$active = 'accounts';
$back = 'accounts.php';
require __DIR__ . '/includes/header.php';
$presets = [[today(), today(), t('today')], [date('Y-m-01'), today(), t('this_month')],
    [date('Y-m-01', strtotime('first day of last month')), date('Y-m-t', strtotime('first day of last month')), t('last_month')],
    [date('Y-01-01'), today(), t('this_year')]];
?>
<ul class="nav nav-pills mb-3 gap-1 flex-nowrap overflow-auto no-print">
  <?php foreach ($tabs as $k => [$icon, $label]): ?>
    <li class="nav-item"><a class="nav-link text-nowrap<?= $r === $k ? ' active' : '' ?>" href="?r=<?= $k ?>"><i class="bi <?= $icon ?>"></i> <?= e($label) ?></a></li>
  <?php endforeach; ?>
  <li class="nav-item"><a class="nav-link text-nowrap" href="ledger.php"><i class="bi bi-journal-text"></i> <?= e(t('ledger')) ?></a></li>
</ul>
<div class="print-only mb-2"><b><?= e(gym_title() . ' – ' . setting('gym_place')) ?></b></div>

<?php if ($r === 'monthly'):
  $rows = q("SELECT DATE_FORMAT(x.d, '%m') mo,
               COALESCE(SUM(CASE WHEN x.type = 'income' THEN x.amount END), 0) inc,
               COALESCE(SUM(CASE WHEN x.type = 'expense' THEN x.amount END), 0) exp
             FROM (" . acc_union_sql() . ") x WHERE x.d BETWEEN ? AND ? GROUP BY mo", [$year . '-01-01', $year . '-12-31'])->fetchAll();
  $byMonth = array_column($rows, null, 'mo');
  $ti = array_sum(array_column($rows, 'inc'));
  $te = array_sum(array_column($rows, 'exp'));
  ?>
  <form class="card card-body mb-3 filters" method="get"><input type="hidden" name="r" value="monthly">
    <div class="d-flex gap-2"><input class="form-control" style="max-width:140px" type="number" name="year" value="<?= e($year) ?>" min="2000" max="2100"><button class="btn btn-dark"><?= e(t('show')) ?></button></div>
  </form>
  <div class="row g-3 mb-3">
    <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('acc_income')) ?></div><div class="num text-success"><?= money($ti) ?></div></div></div></div>
    <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('acc_expense')) ?></div><div class="num text-danger"><?= money($te) ?></div></div></div></div>
    <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e($ti - $te >= 0 ? t('profit') : t('loss')) ?></div><div class="num text-primary"><?= money(abs($ti - $te)) ?></div></div></div></div>
  </div>
  <div class="card">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center"><span class="me-auto"><?= e(t('monthly_summary')) ?> <?= e($year) ?></span><?php require __DIR__ . '/includes/export_buttons.php'; ?></div>
    <div class="table-responsive">
      <table class="table table-cards" id="reportTable" data-title="Monthly summary <?= e($year) ?>">
        <thead><tr><th data-en="Month"><?= e(t('month')) ?></th><th class="text-end" data-en="Income"><?= e(t('acc_income')) ?></th><th class="text-end" data-en="Expense"><?= e(t('acc_expense')) ?></th><th class="text-end" data-en="Profit / loss"><?= e(t('profit')) ?> / <?= e(t('loss')) ?></th></tr></thead>
        <tbody>
        <?php for ($i = 1; $i <= 12; $i++): $mo = sprintf('%02d', $i); $x = $byMonth[$mo] ?? ['inc' => 0, 'exp' => 0]; $p = $x['inc'] - $x['exp'];
            if ("$year-$mo" > date('Y-m') && !$x['inc'] && !$x['exp']) continue; ?>
          <tr><td class="td-main fw-semibold"><a href="ledger.php?from=<?= "$year-$mo-01" ?>&to=<?= date('Y-m-t', strtotime("$year-$mo-01")) ?>"><?= e(date('F Y', strtotime("$year-$mo-01"))) ?></a></td>
            <td data-label="<?= e(t('acc_income')) ?>" class="text-end text-success"><?= money($x['inc']) ?></td>
            <td data-label="<?= e(t('acc_expense')) ?>" class="text-end text-danger"><?= money($x['exp']) ?></td>
            <td data-label="<?= e(t('profit')) ?>" class="text-end fw-bold <?= $p < 0 ? 'text-danger' : '' ?>"><?= $p < 0 ? '−' : '' ?><?= money(abs($p)) ?></td></tr>
        <?php endfor; ?>
        </tbody>
        <tfoot><tr class="fw-bold"><td data-en="Total"><?= e(t('total')) ?></td><td class="text-end"><?= money($ti) ?></td><td class="text-end"><?= money($te) ?></td><td class="text-end"><?= $ti - $te < 0 ? '−' : '' ?><?= money(abs($ti - $te)) ?></td></tr></tfoot>
      </table>
    </div>
  </div>

<?php elseif ($r === 'cashbook'):
  $rows = acc_ledger(['from' => $from, 'to' => $to, 'account' => $acc]);
  $open = acc_balance($acc, $from);
  $bal = $open;
  $in = $out = 0;
  $accName = array_column($accounts, 'name', 'id')[$acc] ?? '';
  ?>
  <form class="card card-body mb-3 filters" method="get"><input type="hidden" name="r" value="cashbook">
    <div class="row g-2">
      <div class="col-12 col-md-3"><select class="form-select" name="account"><?php foreach ($accounts as $a): ?><option value="<?= $a['id'] ?>"<?= $acc === (int)$a['id'] ? ' selected' : '' ?>><?= e($a['name']) ?></option><?php endforeach; ?></select></div>
      <div class="col-6 col-md-3"><input class="form-control" type="date" name="from" value="<?= e($from) ?>"></div>
      <div class="col-6 col-md-3"><input class="form-control" type="date" name="to" value="<?= e($to) ?>"></div>
      <div class="col-12 col-md-3"><button class="btn btn-dark w-100"><?= e(t('show')) ?></button></div>
      <div class="col-12 d-flex gap-2 flex-wrap"><?php foreach ($presets as [$a, $b, $l]): ?><a class="btn btn-sm btn-light" href="?r=cashbook&account=<?= $acc ?>&from=<?= $a ?>&to=<?= $b ?>"><?= e($l) ?></a><?php endforeach; ?></div>
    </div>
  </form>
  <div class="card">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center"><span class="me-auto"><?= e(t('cash_book')) ?> · <?= e($accName) ?> · <?= e(fdate($from)) ?><?= $from !== $to ? ' – ' . e(fdate($to)) : '' ?></span><?php require __DIR__ . '/includes/export_buttons.php'; ?></div>
    <div class="table-responsive">
      <table class="table table-cards" id="reportTable" data-title="Cash book <?= e($accName . ' ' . fdate($from) . ($from !== $to ? ' - ' . fdate($to) : '')) ?>">
        <thead><tr><th data-en="Date"><?= e(t('date')) ?></th><th data-en="Particulars"><?= e(t('particulars')) ?></th><th class="text-end" data-en="In"><?= e(t('money_in')) ?></th><th class="text-end" data-en="Out"><?= e(t('money_out')) ?></th><th class="text-end" data-en="Balance"><?= e(t('balance')) ?></th></tr></thead>
        <tbody>
          <tr class="table-light"><td class="td-main" colspan="4" data-en="Opening balance"><b><?= e(t('opening_balance')) ?></b></td><td class="text-end fw-bold"><?= money($open) ?></td></tr>
          <?php foreach ($rows as $x): $eff = acc_effect($x, $acc); $bal += $eff; $in += max(0, $eff); $out += max(0, -$eff);
              $label = $x['type'] === 'transfer' ? $x['account'] . ' → ' . $x['to_account'] : ($x['category'] ?? '–'); ?>
            <tr><td class="td-main"><?= e(fdate($x['d'])) ?></td>
              <td data-label="<?= e(t('particulars')) ?>"><?= e($label) ?><?= $x['party'] !== '' ? ' · <span class="small-muted">' . e($x['party']) . '</span>' : '' ?></td>
              <td data-label="<?= e(t('money_in')) ?>" class="text-end text-success"><?= $eff > 0 ? money($eff) : '' ?></td>
              <td data-label="<?= e(t('money_out')) ?>" class="text-end text-danger"><?= $eff < 0 ? money(-$eff) : '' ?></td>
              <td data-label="<?= e(t('balance')) ?>" class="text-end"><?= money($bal) ?></td></tr>
          <?php endforeach; ?>
        </tbody>
        <tfoot><tr class="fw-bold"><td colspan="2" data-en="Closing balance"><?= e(t('closing_balance')) ?></td><td class="text-end"><?= money($in) ?></td><td class="text-end"><?= money($out) ?></td><td class="text-end"><?= money($bal) ?></td></tr></tfoot>
      </table>
    </div>
  </div>

<?php else:
  $cats = acc_by_category($from, $to);
  $tot = acc_totals($from, $to);
  ?>
  <form class="card card-body mb-3 filters" method="get"><input type="hidden" name="r" value="pl">
    <div class="row g-2">
      <div class="col-6 col-md-3"><input class="form-control" type="date" name="from" value="<?= e($from) ?>"></div>
      <div class="col-6 col-md-3"><input class="form-control" type="date" name="to" value="<?= e($to) ?>"></div>
      <div class="col-12 col-md-2"><button class="btn btn-dark w-100"><?= e(t('show')) ?></button></div>
      <div class="col-12 d-flex gap-2 flex-wrap"><?php foreach ($presets as [$a, $b, $l]): ?><a class="btn btn-sm btn-light" href="?r=pl&from=<?= $a ?>&to=<?= $b ?>"><?= e($l) ?></a><?php endforeach; ?></div>
    </div>
  </form>
  <div class="card">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center"><span class="me-auto"><?= e(t('profit_loss')) ?> · <?= e(fdate($from)) ?> – <?= e(fdate($to)) ?></span><?php require __DIR__ . '/includes/export_buttons.php'; ?></div>
    <div class="table-responsive">
      <table class="table mb-0" id="reportTable" data-title="Profit and loss <?= e(fdate($from) . ' - ' . fdate($to)) ?>">
        <thead><tr><th data-en="Particulars"><?= e(t('particulars')) ?></th><th class="text-end" data-en="Entries"><?= e(t('entries')) ?></th><th class="text-end" data-en="Amount"><?= e(t('amount')) ?></th></tr></thead>
        <tbody>
          <?php foreach (['income', 'expense'] as $type): ?>
            <tr class="table-<?= $type === 'income' ? 'success' : 'danger' ?>"><th colspan="3" data-en="<?= e(t_en('acc_' . $type)) ?>"><?= e(t('acc_' . $type)) ?></th></tr>
            <?php $any = false; foreach ($cats as $c): if ($c['type'] !== $type) continue; $any = true; ?>
              <tr><td class="ps-4"><a href="ledger.php?category=<?= (int)$c['category_id'] ?>&from=<?= e($from) ?>&to=<?= e($to) ?>"><?= e($c['category']) ?></a></td><td class="text-end"><?= (int)$c['n'] ?></td><td class="text-end"><?= money($c['total']) ?></td></tr>
            <?php endforeach; if (!$any): ?><tr><td class="ps-4 text-muted" colspan="3">–</td></tr><?php endif; ?>
            <tr class="fw-bold"><td data-en="Total <?= e(strtolower(t_en('acc_' . $type))) ?>"><?= e(t('total')) ?> <?= e(t('acc_' . $type)) ?></td><td></td><td class="text-end"><?= money($tot[$type]) ?></td></tr>
          <?php endforeach; ?>
        </tbody>
        <tfoot><tr class="fs-5 fw-bold <?= $tot['profit'] < 0 ? 'text-danger' : 'text-primary' ?>"><td data-en="<?= $tot['profit'] >= 0 ? 'Net profit' : 'Net loss' ?>"><?= e($tot['profit'] >= 0 ? t('net_profit') : t('net_loss')) ?></td><td></td><td class="text-end"><?= money(abs($tot['profit'])) ?></td></tr></tfoot>
      </table>
    </div>
  </div>
<?php endif; ?>
<?php
$scripts = ['assets/vendor/jspdf.umd.min.js', 'assets/vendor/jspdf.plugin.autotable.min.js'];
require __DIR__ . '/includes/footer.php';
