<?php
// Accounts overview: balance in each account, this month's income / expense / profit, quick entry buttons.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/accounts.php';
require_admin();

$today = today();
$monthStart = date('Y-m-01');
$m = acc_totals($monthStart, $today);
$d = acc_totals($today, $today);
$accounts = acc_accounts();
$total = 0;
foreach ($accounts as &$a) {
    $a['balance'] = acc_balance((int)$a['id']);
    $total += $a['balance'];
}
unset($a);
$recent = array_reverse(acc_ledger(['from' => date('Y-m-d', strtotime('-30 day')), 'to' => $today]));
$recent = array_slice($recent, 0, 10);
$expCats = array_filter(acc_by_category($monthStart, $today), fn($r) => $r['type'] === 'expense');

$title = t('accounts');
$active = 'accounts';
$actions = '<a href="acc_settings.php" class="btn btn-outline-secondary"><i class="bi bi-sliders"></i> <span class="d-none d-sm-inline">' . e(t('acc_setup')) . '</span></a>';
require __DIR__ . '/includes/header.php';
?>
<div class="row g-2 g-md-3 mb-3">
  <div class="col-4"><a href="entry_edit.php?type=income" class="btn btn-accent big-btn w-100"><i class="bi bi-plus-circle-fill"></i><?= e(t('add_income')) ?></a></div>
  <div class="col-4"><a href="entry_edit.php?type=expense" class="btn btn-danger big-btn w-100"><i class="bi bi-dash-circle-fill"></i><?= e(t('add_expense')) ?></a></div>
  <div class="col-4"><a href="entry_edit.php?type=transfer" class="btn btn-dark big-btn w-100"><i class="bi bi-arrow-left-right"></i><?= e(t('acc_transfer')) ?></a></div>
</div>

<h2 class="section-head"><?= e(t('balances')) ?></h2>
<div class="row g-3 mb-3">
  <?php foreach ($accounts as $a): ?>
    <div class="col-6 col-md-4 col-xl-3">
      <a href="ledger.php?account=<?= $a['id'] ?>&from=<?= $monthStart ?>" class="card stat tap">
        <div class="ico <?= $a['kind'] === 'cash' ? 'ico-green' : 'ico-blue' ?>"><i class="bi <?= $a['kind'] === 'cash' ? 'bi-cash-stack' : 'bi-bank' ?>"></i></div>
        <div><div class="num <?= $a['balance'] < 0 ? 'text-danger' : '' ?>"><?= money($a['balance']) ?></div><div class="lbl"><?= e($a['name']) ?></div></div>
        <i class="bi bi-chevron-right go"></i>
      </a>
    </div>
  <?php endforeach; ?>
  <div class="col-6 col-md-4 col-xl-3">
    <a href="ledger.php?from=<?= $monthStart ?>" class="card stat tap" style="background:linear-gradient(135deg,#C8160E,#1A1A1A);color:#fff">
      <div class="ico" style="background:rgba(255,255,255,.15);color:#E8261C"><i class="bi bi-wallet2"></i></div>
      <div><div class="num"><?= money($total) ?></div><div class="lbl text-white-50"><?= e(t('total_balance')) ?></div></div>
      <i class="bi bi-chevron-right go"></i>
    </a>
  </div>
</div>

<h2 class="section-head"><?= e(t('this_month')) ?> · <?= e(date('M Y')) ?></h2>
<div class="row g-3 mb-3">
  <div class="col-4"><a href="ledger.php?type=income&from=<?= $monthStart ?>" class="card stat tap"><div><div class="lbl"><?= e(t('acc_income')) ?></div><div class="num text-success"><?= money($m['income']) ?></div><div class="small-muted"><?= e(t('today')) ?>: <?= money($d['income']) ?></div></div></a></div>
  <div class="col-4"><a href="ledger.php?type=expense&from=<?= $monthStart ?>" class="card stat tap"><div><div class="lbl"><?= e(t('acc_expense')) ?></div><div class="num text-danger"><?= money($m['expense']) ?></div><div class="small-muted"><?= e(t('today')) ?>: <?= money($d['expense']) ?></div></div></a></div>
  <div class="col-4"><a href="acc_reports.php?r=pl" class="card stat tap"><div><div class="lbl"><?= e($m['profit'] >= 0 ? t('profit') : t('loss')) ?></div><div class="num <?= $m['profit'] >= 0 ? 'text-primary' : 'text-danger' ?>"><?= money(abs($m['profit'])) ?></div><div class="small-muted"><?= e(t('income_minus_expense')) ?></div></div></a></div>
</div>

<div class="row g-3">
  <div class="col-lg-7">
    <div class="card">
      <div class="card-header d-flex align-items-center"><i class="bi bi-journal-text me-2 text-primary"></i><?= e(t('recent_entries')) ?>
        <a href="ledger.php" class="ms-auto small"><?= e(t('ledger')) ?></a></div>
      <div class="list-group list-group-flush">
        <?php if (!$recent): ?><div class="p-3 text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
        <?php foreach ($recent as $r): $href = $r['src'] === 'payment' ? 'receipt.php?id=' . $r['id'] : 'voucher.php?id=' . $r['id']; ?>
          <a href="<?= e($href) ?>" class="list-group-item list-group-item-action d-flex align-items-center gap-2">
            <i class="bi <?= ['income' => 'bi-arrow-down-left-circle-fill text-success', 'expense' => 'bi-arrow-up-right-circle-fill text-danger', 'transfer' => 'bi-arrow-left-right text-secondary'][$r['type']] ?> fs-4"></i>
            <div class="me-auto"><div class="fw-semibold"><?= e($r['type'] === 'transfer' ? $r['account'] . ' → ' . $r['to_account'] : ($r['category'] ?? '–')) ?></div>
              <div class="small-muted"><?= e(fdate($r['d'])) ?><?= $r['party'] !== '' ? ' · ' . e($r['party']) : '' ?></div></div>
            <b class="<?= $r['type'] === 'income' ? 'text-success' : ($r['type'] === 'expense' ? 'text-danger' : '') ?>"><?= $r['type'] === 'expense' ? '−' : '' ?><?= money($r['amount']) ?></b>
          </a>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
  <div class="col-lg-5">
    <div class="card mb-3">
      <div class="card-header"><i class="bi bi-pie-chart me-2 text-danger"></i><?= e(t('expense_by_category')) ?> · <?= e(date('M Y')) ?></div>
      <div class="card-body">
        <?php if (!$expCats): ?><div class="text-muted"><?= e(t('nothing_here')) ?></div><?php endif; ?>
        <?php foreach ($expCats as $c): $pct = $m['expense'] > 0 ? round($c['total'] / $m['expense'] * 100) : 0; ?>
          <a class="d-block text-decoration-none text-dark mb-2" href="ledger.php?category=<?= (int)$c['category_id'] ?>&from=<?= $monthStart ?>">
            <div class="d-flex small"><span class="me-auto"><?= e($c['category']) ?></span><b><?= money($c['total']) ?></b></div>
            <div class="progress" style="height:6px" role="progressbar" aria-valuenow="<?= $pct ?>" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar bg-danger" style="width:<?= $pct ?>%"></div></div>
          </a>
        <?php endforeach; ?>
      </div>
    </div>
    <div class="card"><div class="list-group list-group-flush">
      <a href="ledger.php" class="list-group-item list-group-item-action d-flex align-items-center gap-2"><i class="bi bi-journal-text text-primary"></i><span class="me-auto"><?= e(t('ledger')) ?></span><i class="bi bi-chevron-right"></i></a>
      <a href="acc_reports.php?r=pl" class="list-group-item list-group-item-action d-flex align-items-center gap-2"><i class="bi bi-graph-up-arrow text-success"></i><span class="me-auto"><?= e(t('profit_loss')) ?></span><i class="bi bi-chevron-right"></i></a>
      <a href="acc_reports.php?r=cashbook" class="list-group-item list-group-item-action d-flex align-items-center gap-2"><i class="bi bi-book text-dark"></i><span class="me-auto"><?= e(t('cash_book')) ?></span><i class="bi bi-chevron-right"></i></a>
      <a href="acc_reports.php?r=monthly" class="list-group-item list-group-item-action d-flex align-items-center gap-2"><i class="bi bi-calendar3 text-primary"></i><span class="me-auto"><?= e(t('monthly_summary')) ?></span><i class="bi bi-chevron-right"></i></a>
      <a href="acc_settings.php" class="list-group-item list-group-item-action d-flex align-items-center gap-2"><i class="bi bi-sliders text-secondary"></i><span class="me-auto"><?= e(t('acc_setup')) ?></span><i class="bi bi-chevron-right"></i></a>
    </div></div>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
