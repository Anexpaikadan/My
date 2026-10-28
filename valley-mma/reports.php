<?php
// Reports: daily / monthly / yearly income, active and expired members, payment history and pending balances.
// Every report can be printed or exported to PDF and Excel (CSV).

require __DIR__ . '/includes/init.php';
require_admin();

$r = in_array(get('r'), ['income', 'active', 'expired', 'payments', 'balance'], true) ? get('r') : 'income';
$period = in_array(get('period'), ['daily', 'monthly', 'yearly'], true) ? get('period') : 'daily';
$date = valid_date(get('date')) ? get('date') : today();
$month = preg_match('/^\d{4}-\d{2}$/', get('month')) ? get('month') : date('Y-m');
$year = preg_match('/^\d{4}$/', get('year')) ? get('year') : date('Y');
$from = valid_date(get('from')) ? get('from') : date('Y-m-01');
$to = valid_date(get('to')) ? get('to') : today();
$today = today();

$tabs = [
    'income' => ['bi-graph-up-arrow', t('income')],
    'active' => ['bi-person-check', t('active_members')],
    'expired' => ['bi-person-x', t('expired_members')],
    'payments' => ['bi-receipt', t('payment_history')],
    'balance' => ['bi-exclamation-diamond', t('pending_balance')],
];

$title = t('reports');
$active = 'reports';
$back = 'index.php';
require __DIR__ . '/includes/header.php';
?>
<ul class="nav nav-pills mb-3 gap-1 flex-nowrap overflow-auto no-print">
  <?php foreach ($tabs as $k => [$icon, $label]): ?>
    <li class="nav-item"><a class="nav-link text-nowrap<?= $r === $k ? ' active' : '' ?>" href="?r=<?= $k ?>"><i class="bi <?= $icon ?>"></i> <?= e($label) ?></a></li>
  <?php endforeach; ?>
  <li class="nav-item"><a class="nav-link text-nowrap" href="attendance_monthly.php"><i class="bi bi-calendar3"></i> <?= e(t('attendance')) ?></a></li>
  <li class="nav-item"><a class="nav-link text-nowrap" href="acc_reports.php?r=pl"><i class="bi bi-wallet2"></i> <?= e(t('profit_loss')) ?></a></li>
  <li class="nav-item"><a class="nav-link text-nowrap" href="ledger.php"><i class="bi bi-journal-text"></i> <?= e(t('ledger')) ?></a></li>
</ul>
<div class="print-only mb-2"><b><?= e(gym_title() . ' – ' . setting('gym_place')) ?></b></div>

<?php if ($r === 'income'): ?>
  <form class="card card-body mb-3 filters" method="get"><input type="hidden" name="r" value="income">
    <div class="row g-2 align-items-center">
      <div class="col-12 col-md-auto">
        <div class="btn-group w-100">
          <?php foreach (['daily', 'monthly', 'yearly'] as $p): ?>
            <a class="btn <?= $period === $p ? 'btn-primary' : 'btn-outline-primary' ?>" href="?r=income&period=<?= $p ?>"><?= e(t($p)) ?></a>
          <?php endforeach; ?>
        </div>
      </div>
      <input type="hidden" name="period" value="<?= $period ?>">
      <div class="col-8 col-md-3">
        <?php if ($period === 'daily'): ?><input class="form-control" type="date" name="date" value="<?= e($date) ?>" onchange="this.form.submit()">
        <?php elseif ($period === 'monthly'): ?><input class="form-control" type="month" name="month" value="<?= e($month) ?>" onchange="this.form.submit()">
        <?php else: ?><input class="form-control" type="number" name="year" value="<?= e($year) ?>" min="2000" max="2100" onchange="this.form.submit()"><?php endif; ?>
      </div>
      <div class="col-4 col-md-auto"><button class="btn btn-dark w-100"><?= e(t('show')) ?></button></div>
    </div>
  </form>
  <?php
  if ($period === 'daily') {
      $rows = q('SELECT p.*, m.name, m.adm_no FROM payments p JOIN members m ON m.id = p.member_id WHERE p.pay_date = ? ORDER BY p.id', [$date])->fetchAll();
      $label = fdate($date);
  } elseif ($period === 'monthly') {
      $rows = q("SELECT pay_date k, COUNT(*) c, SUM(paid) paid, SUM(CASE WHEN method = 'cash' THEN paid ELSE 0 END) cash,
                 SUM(CASE WHEN method <> 'cash' THEN paid ELSE 0 END) online, SUM(admission_fee) adm, SUM(plan_fee) plan, SUM(other_fee) other
                 FROM payments WHERE pay_date BETWEEN ? AND ? GROUP BY pay_date ORDER BY pay_date", [$month . '-01', date('Y-m-t', strtotime($month . '-01'))])->fetchAll();
      $label = date('F Y', strtotime($month . '-01'));
  } else {
      $rows = q("SELECT DATE_FORMAT(pay_date, '%Y-%m') k, COUNT(*) c, SUM(paid) paid, SUM(CASE WHEN method = 'cash' THEN paid ELSE 0 END) cash,
                 SUM(CASE WHEN method <> 'cash' THEN paid ELSE 0 END) online, SUM(admission_fee) adm, SUM(plan_fee) plan, SUM(other_fee) other
                 FROM payments WHERE pay_date BETWEEN ? AND ? GROUP BY k ORDER BY k", [$year . '-01-01', $year . '-12-31'])->fetchAll();
      $label = $year;
  }
  $total = array_sum(array_column($rows, 'paid'));
  $cash = $period === 'daily' ? array_sum(array_map(fn($p) => $p['method'] === 'cash' ? $p['paid'] : 0, $rows)) : array_sum(array_column($rows, 'cash'));
  ?>
  <div class="row g-3 mb-3">
    <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('income')) ?> · <?= e($label) ?></div><div class="num text-success"><?= money($total) ?></div></div></div></div>
    <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('m_cash')) ?></div><div class="num"><?= money($cash) ?></div></div></div></div>
    <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('m_upi')) ?> / <?= e(t('online')) ?></div><div class="num"><?= money($total - $cash) ?></div></div></div></div>
  </div>
  <div class="card">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center"><span class="me-auto"><?= e(t($period)) ?> <?= e(t('income')) ?> – <?= e($label) ?></span><?php require __DIR__ . '/includes/export_buttons.php'; ?></div>
    <div class="table-responsive">
      <?php if ($period === 'daily'): ?>
        <table class="table table-cards" id="reportTable" data-title="Daily income <?= e($label) ?>">
          <thead><tr><th data-en="Receipt"><?= e(t('receipt_no')) ?></th><th data-en="Member"><?= e(t('member')) ?></th><th data-en="Method"><?= e(t('payment_method')) ?></th><th data-en="Total"><?= e(t('total')) ?></th><th data-en="Paid"><?= e(t('paid')) ?></th></tr></thead>
          <tbody>
          <?php if (!$rows): ?><tr><td colspan="5" class="text-center text-muted p-4"><?= e(t('no_payments')) ?></td></tr><?php endif; ?>
          <?php foreach ($rows as $p): ?>
            <tr><td class="td-main"><a href="receipt.php?id=<?= $p['id'] ?>">#<?= $p['receipt_no'] ?></a></td><td data-label="<?= e(t('member')) ?>"><?= e($p['name']) ?> (<?= e($p['adm_no']) ?>)</td>
              <td data-label="<?= e(t('payment_method')) ?>" data-en="<?= e(t_en('m_' . $p['method'])) ?>"><?= e(t('m_' . $p['method'])) ?></td><td data-label="<?= e(t('total')) ?>"><?= money($p['total']) ?></td><td data-label="<?= e(t('paid')) ?>" class="fw-bold"><?= money($p['paid']) ?></td></tr>
          <?php endforeach; ?>
          </tbody>
          <tfoot><tr class="fw-bold"><td colspan="4" data-en="Total"><?= e(t('total')) ?></td><td><?= money($total) ?></td></tr></tfoot>
        </table>
      <?php else: ?>
        <table class="table table-cards" id="reportTable" data-title="<?= $period === 'monthly' ? 'Monthly' : 'Yearly' ?> income <?= e($label) ?>">
          <thead><tr><th data-en="<?= $period === 'monthly' ? 'Date' : 'Month' ?>"><?= e(t($period === 'monthly' ? 'date' : 'month')) ?></th><th data-en="Payments"><?= e(t('payments')) ?></th>
            <th data-en="Admission"><?= e(t('admission_fee')) ?></th><th data-en="Plans"><?= e(t('plan_fee')) ?></th><th data-en="Other"><?= e(t('other_fee')) ?></th>
            <th data-en="Cash"><?= e(t('m_cash')) ?></th><th data-en="UPI/Online"><?= e(t('m_upi')) ?>/<?= e(t('online')) ?></th><th data-en="Received"><?= e(t('received')) ?></th></tr></thead>
          <tbody>
          <?php if (!$rows): ?><tr><td colspan="8" class="text-center text-muted p-4"><?= e(t('no_payments')) ?></td></tr><?php endif; ?>
          <?php foreach ($rows as $x): $k = $period === 'monthly' ? fdate($x['k']) : date('M Y', strtotime($x['k'] . '-01')); ?>
            <tr><td class="td-main fw-semibold">
              <a href="?r=income&<?= $period === 'monthly' ? 'period=daily&date=' . e($x['k']) : 'period=monthly&month=' . e($x['k']) ?>"><?= e($k) ?></a></td>
              <td data-label="<?= e(t('payments')) ?>"><?= (int)$x['c'] ?></td><td data-label="<?= e(t('admission_fee')) ?>"><?= money($x['adm']) ?></td>
              <td data-label="<?= e(t('plan_fee')) ?>"><?= money($x['plan']) ?></td><td data-label="<?= e(t('other_fee')) ?>"><?= money($x['other']) ?></td>
              <td data-label="<?= e(t('m_cash')) ?>"><?= money($x['cash']) ?></td><td data-label="<?= e(t('m_upi')) ?>"><?= money($x['online']) ?></td>
              <td data-label="<?= e(t('received')) ?>" class="fw-bold text-success"><?= money($x['paid']) ?></td></tr>
          <?php endforeach; ?>
          </tbody>
          <tfoot><tr class="fw-bold"><td data-en="Total"><?= e(t('total')) ?></td><td><?= array_sum(array_column($rows, 'c')) ?></td><td><?= money(array_sum(array_column($rows, 'adm'))) ?></td>
            <td><?= money(array_sum(array_column($rows, 'plan'))) ?></td><td><?= money(array_sum(array_column($rows, 'other'))) ?></td><td><?= money($cash) ?></td><td><?= money($total - $cash) ?></td><td><?= money($total) ?></td></tr></tfoot>
        </table>
      <?php endif; ?>
    </div>
  </div>

<?php elseif ($r === 'active' || $r === 'expired'):
  $rows = $r === 'active'
      ? q('SELECT m.*, p.name plan_name FROM members m LEFT JOIN plans p ON p.id = m.plan_id WHERE m.status = \'active\' AND m.expiry_date >= ? ORDER BY m.expiry_date', [$today])->fetchAll()
      : q('SELECT m.*, p.name plan_name FROM members m LEFT JOIN plans p ON p.id = m.plan_id WHERE m.status = \'active\' AND (m.expiry_date < ? OR m.expiry_date IS NULL) ORDER BY m.expiry_date DESC', [$today])->fetchAll();
  $label = t($r === 'active' ? 'active_members' : 'expired_members');
  ?>
  <div class="card">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center"><span class="me-auto"><?= e($label) ?> (<?= count($rows) ?>) · <?= e(fdate($today)) ?></span><?php require __DIR__ . '/includes/export_buttons.php'; ?></div>
    <div class="table-responsive">
      <table class="table table-cards" id="reportTable" data-title="<?= $r === 'active' ? 'Active' : 'Expired' ?> members <?= e(fdate($today)) ?>">
        <thead><tr><th data-en="Adm No"><?= e(t('adm_no')) ?></th><th data-en="Name"><?= e(t('name')) ?></th><th data-en="Phone"><?= e(t('phone')) ?></th><th data-en="Plan"><?= e(t('plan')) ?></th>
          <th data-en="Start"><?= e(t('start_date')) ?></th><th data-en="Expiry"><?= e(t('expiry_date')) ?></th><th data-en="Days"><?= e(t($r === 'active' ? 'days_left_label' : 'days_ago')) ?></th><th class="no-export"></th></tr></thead>
        <tbody>
        <?php if (!$rows): ?><tr><td colspan="8" class="text-center text-muted p-4"><?= e(t('nothing_here')) ?></td></tr><?php endif; ?>
        <?php foreach ($rows as $m): $dl = days_left($m['expiry_date']); ?>
          <tr class="<?= $r === 'expired' ? 'row-expired' : (member_status($m['expiry_date']) === 'expiring' ? 'row-expiring' : '') ?>">
            <td class="td-main fw-semibold"><?= e($m['adm_no']) ?></td>
            <td data-label="<?= e(t('name')) ?>"><a href="member_view.php?id=<?= $m['id'] ?>"><?= e($m['name']) ?></a></td>
            <td data-label="<?= e(t('phone')) ?>"><?= e($m['phone']) ?></td>
            <td data-label="<?= e(t('plan')) ?>"><?= e($m['plan_name'] ?? '–') ?></td>
            <td data-label="<?= e(t('start_date')) ?>"><?= e(fdate($m['start_date'])) ?></td>
            <td data-label="<?= e(t('expiry_date')) ?>"><?= e(fdate($m['expiry_date'])) ?></td>
            <td data-label="<?= e(t('days')) ?>"><?= $m['expiry_date'] ? abs($dl) : '–' ?></td>
            <td class="td-actions no-export text-end"><a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], $r === 'active' ? t('wa_hello', $m['name']) : reminder_text($m))) ?>"><i class="bi bi-whatsapp"></i></a></td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>
  </div>

<?php elseif ($r === 'payments'):
  $rows = q('SELECT p.*, m.name, m.adm_no, pl.name plan_name FROM payments p JOIN members m ON m.id = p.member_id LEFT JOIN plans pl ON pl.id = p.plan_id
             WHERE p.pay_date BETWEEN ? AND ? ORDER BY p.pay_date, p.id', [$from, $to])->fetchAll();
  ?>
  <form class="card card-body mb-3 filters" method="get"><input type="hidden" name="r" value="payments">
    <div class="row g-2">
      <div class="col-6 col-md-3"><input class="form-control" type="date" name="from" value="<?= e($from) ?>"></div>
      <div class="col-6 col-md-3"><input class="form-control" type="date" name="to" value="<?= e($to) ?>"></div>
      <div class="col-12 col-md-2"><button class="btn btn-dark w-100"><?= e(t('show')) ?></button></div>
    </div>
  </form>
  <div class="card">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center"><span class="me-auto"><?= e(fdate($from)) ?> – <?= e(fdate($to)) ?> (<?= count($rows) ?>)</span><?php require __DIR__ . '/includes/export_buttons.php'; ?></div>
    <div class="table-responsive">
      <table class="table table-cards" id="reportTable" data-title="Payments <?= e(fdate($from) . ' - ' . fdate($to)) ?>">
        <thead><tr><th data-en="Receipt"><?= e(t('receipt_no')) ?></th><th data-en="Date"><?= e(t('date')) ?></th><th data-en="Member"><?= e(t('member')) ?></th><th data-en="Plan"><?= e(t('plan')) ?></th>
          <th data-en="Method"><?= e(t('payment_method')) ?></th><th data-en="Total"><?= e(t('total')) ?></th><th data-en="Paid"><?= e(t('paid')) ?></th><th data-en="Balance"><?= e(t('balance')) ?></th></tr></thead>
        <tbody>
        <?php if (!$rows): ?><tr><td colspan="8" class="text-center text-muted p-4"><?= e(t('no_payments')) ?></td></tr><?php endif; ?>
        <?php foreach ($rows as $p): ?>
          <tr><td class="td-main"><a href="receipt.php?id=<?= $p['id'] ?>">#<?= $p['receipt_no'] ?></a></td><td data-label="<?= e(t('date')) ?>"><?= e(fdate($p['pay_date'])) ?></td>
            <td data-label="<?= e(t('member')) ?>"><?= e($p['name']) ?> (<?= e($p['adm_no']) ?>)</td><td data-label="<?= e(t('plan')) ?>"><?= e($p['plan_name'] ?? '–') ?></td>
            <td data-label="<?= e(t('payment_method')) ?>" data-en="<?= e(t_en('m_' . $p['method'])) ?>"><?= e(t('m_' . $p['method'])) ?></td><td data-label="<?= e(t('total')) ?>"><?= money($p['total']) ?></td>
            <td data-label="<?= e(t('paid')) ?>" class="fw-bold"><?= money($p['paid']) ?></td><td data-label="<?= e(t('balance')) ?>"><?= money($p['total'] - $p['paid']) ?></td></tr>
        <?php endforeach; ?>
        </tbody>
        <tfoot><tr class="fw-bold"><td colspan="5" data-en="Total"><?= e(t('total')) ?></td><td><?= money(array_sum(array_column($rows, 'total'))) ?></td>
          <td><?= money(array_sum(array_column($rows, 'paid'))) ?></td><td><?= money(array_sum(array_column($rows, 'total')) - array_sum(array_column($rows, 'paid'))) ?></td></tr></tfoot>
      </table>
    </div>
  </div>

<?php else:
  $rows = q('SELECT m.id, m.name, m.adm_no, m.phone, m.expiry_date, SUM(p.total - p.paid) balance
             FROM members m JOIN payments p ON p.member_id = m.id GROUP BY m.id HAVING balance > 0 ORDER BY balance DESC')->fetchAll();
  ?>
  <div class="card">
    <div class="card-header d-flex flex-wrap gap-2 align-items-center"><span class="me-auto"><?= e(t('pending_balance')) ?>: <b class="text-danger"><?= money(array_sum(array_column($rows, 'balance'))) ?></b></span><?php require __DIR__ . '/includes/export_buttons.php'; ?></div>
    <div class="table-responsive">
      <table class="table table-cards" id="reportTable" data-title="Pending balance <?= e(fdate($today)) ?>">
        <thead><tr><th data-en="Adm No"><?= e(t('adm_no')) ?></th><th data-en="Name"><?= e(t('name')) ?></th><th data-en="Phone"><?= e(t('phone')) ?></th><th data-en="Expiry"><?= e(t('expiry_date')) ?></th><th data-en="Balance"><?= e(t('balance')) ?></th><th class="no-export"></th></tr></thead>
        <tbody>
        <?php if (!$rows): ?><tr><td colspan="6" class="text-center text-muted p-4"><?= e(t('nothing_here')) ?></td></tr><?php endif; ?>
        <?php foreach ($rows as $m): ?>
          <tr><td class="td-main fw-semibold"><?= e($m['adm_no']) ?></td><td data-label="<?= e(t('name')) ?>"><a href="member_view.php?id=<?= $m['id'] ?>"><?= e($m['name']) ?></a></td>
            <td data-label="<?= e(t('phone')) ?>"><?= e($m['phone']) ?></td><td data-label="<?= e(t('expiry_date')) ?>"><?= e(fdate($m['expiry_date'])) ?></td>
            <td data-label="<?= e(t('balance')) ?>" class="fw-bold text-danger"><?= money($m['balance']) ?></td>
            <td class="td-actions no-export text-end text-nowrap">
              <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], t('wa_balance', $m['name'], money($m['balance']), gym_title()) . upi_text((float)$m['balance']))) ?>"><i class="bi bi-whatsapp"></i></a>
              <a class="btn btn-sm btn-accent" href="payment_add.php?member=<?= $m['id'] ?>"><i class="bi bi-cash-coin"></i></a></td></tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>
  </div>
<?php endif; ?>
<?php
$scripts = ['assets/vendor/jspdf.umd.min.js', 'assets/vendor/jspdf.plugin.autotable.min.js'];
require __DIR__ . '/includes/footer.php';
