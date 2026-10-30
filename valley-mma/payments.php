<?php
// Payment history with date filter, totals and delete.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST' && post('action') === 'delete') {
    require_verify('payments.php');
    $p = q('SELECT * FROM payments WHERE id = ?', [(int)post('id')])->fetch();
    if ($p) {
        delete_payment($p);
        flash('success', t('payment_deleted', $p['receipt_no']));
    }
    redirect($p && post('back') === 'member' ? 'member_view.php?id=' . $p['member_id'] : 'payments.php');
}

$from = valid_date(get('from')) ? get('from') : date('Y-m-01');
$to = valid_date(get('to')) ? get('to') : today();
$s = get('s');
$method = get('method');
$where = 'p.pay_date BETWEEN ? AND ?';
$args = [$from, $to];
if ($s !== '') {
    $where .= ' AND (m.name LIKE ? OR m.phone LIKE ? OR m.adm_no LIKE ? OR p.receipt_no = ?)';
    array_push($args, "%$s%", "%$s%", "%$s%", (int)$s);
}
if (in_array($method, ['cash', 'upi', 'card', 'bank'], true)) {
    $where .= ' AND p.method = ?';
    $args[] = $method;
}
$rows = q("SELECT p.*, m.name, m.adm_no, pl.name plan_name FROM payments p JOIN members m ON m.id = p.member_id
           LEFT JOIN plans pl ON pl.id = p.plan_id WHERE $where ORDER BY p.pay_date DESC, p.id DESC LIMIT 1000", $args)->fetchAll();
$sum = ['total' => 0, 'paid' => 0];
foreach ($rows as $r) {
    $sum['total'] += $r['total'];
    $sum['paid'] += $r['paid'];
}

$title = t('payment_history');
$active = 'payments';
$back = 'index.php';
$actions = '<a href="payment_add.php" class="btn btn-accent"><i class="bi bi-plus-lg"></i> ' . e(t('record_payment')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<form class="card card-body mb-3 filters" method="get">
  <div class="row g-2">
    <div class="col-6 col-md-2"><input class="form-control" type="date" name="from" value="<?= e($from) ?>" aria-label="<?= e(t('from')) ?>"></div>
    <div class="col-6 col-md-2"><input class="form-control" type="date" name="to" value="<?= e($to) ?>" aria-label="<?= e(t('to')) ?>"></div>
    <div class="col-6 col-md-2"><select class="form-select" name="method"><option value=""><?= e(t('all_methods')) ?></option>
      <?php foreach (['cash', 'upi', 'card', 'bank'] as $k): ?><option value="<?= $k ?>"<?= $method === $k ? ' selected' : '' ?>><?= e(t('m_' . $k)) ?></option><?php endforeach; ?></select></div>
    <div class="col-6 col-md-4"><input class="form-control" type="search" name="s" value="<?= e($s) ?>" placeholder="<?= e(t('search_pay_ph')) ?>"></div>
    <div class="col-12 col-md-2"><button class="btn btn-dark w-100"><i class="bi bi-funnel"></i> <?= e(t('show')) ?></button></div>
  </div>
</form>

<div class="row g-3 mb-3">
  <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('payments')) ?></div><div class="num"><?= count($rows) ?></div></div></div></div>
  <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('received')) ?></div><div class="num text-success"><?= money($sum['paid']) ?></div></div></div></div>
  <div class="col-4"><div class="card stat"><div><div class="lbl"><?= e(t('billed')) ?></div><div class="num"><?= money($sum['total']) ?></div></div></div></div>
</div>

<div class="card">
  <div class="card-header d-flex flex-wrap gap-2 align-items-center no-print">
    <span class="me-auto"><?= e(fdate($from)) ?> – <?= e(fdate($to)) ?></span>
    <?php require __DIR__ . '/includes/export_buttons.php'; ?>
  </div>
  <div class="table-responsive">
    <table class="table table-hover table-cards" id="reportTable" data-title="<?= e(t_en('payment_history') . ' ' . fdate($from) . ' - ' . fdate($to)) ?>">
      <thead><tr>
        <th data-en="Receipt"><?= e(t('receipt_no')) ?></th><th data-en="Date"><?= e(t('date')) ?></th><th data-en="Member"><?= e(t('member')) ?></th>
        <th data-en="Particulars"><?= e(t('particulars')) ?></th><th data-en="Method"><?= e(t('payment_method')) ?></th>
        <th data-en="Total"><?= e(t('total')) ?></th><th data-en="Paid"><?= e(t('paid')) ?></th><th data-en="Balance"><?= e(t('balance')) ?></th><th class="no-export"></th>
      </tr></thead>
      <tbody>
      <?php if (!$rows): ?><tr><td colspan="9" class="text-center text-muted p-4"><?= e(t('no_payments')) ?></td></tr><?php endif; ?>
      <?php foreach ($rows as $p): $parts = array_filter([
          $p['admission_fee'] > 0 ? t_en('admission_fee') : '', $p['plan_name'] ?? '', $p['other_fee'] > 0 ? ($p['other_note'] ?: t_en('other_fee')) : '',
          $p['total'] == 0 ? ($p['note'] ?: t_en('balance_payment')) : '']); ?>
        <tr>
          <td class="td-main fw-semibold">#<?= $p['receipt_no'] ?></td>
          <td data-label="<?= e(t('date')) ?>"><?= e(fdate($p['pay_date'])) ?></td>
          <td data-label="<?= e(t('member')) ?>"><a href="member_view.php?id=<?= $p['member_id'] ?>"><?= e($p['name']) ?></a> <span class="small-muted"><?= e($p['adm_no']) ?></span></td>
          <td data-label="<?= e(t('particulars')) ?>"><?= e(implode(', ', $parts)) ?></td>
          <td data-label="<?= e(t('payment_method')) ?>" data-en="<?= e(t_en('m_' . $p['method'])) ?>"><?= e(t('m_' . $p['method'])) ?></td>
          <td data-label="<?= e(t('total')) ?>"><?= money($p['total']) ?></td>
          <td data-label="<?= e(t('paid')) ?>" class="text-success fw-bold"><?= money($p['paid']) ?></td>
          <td data-label="<?= e(t('balance')) ?>"><?= money($p['total'] - $p['paid']) ?></td>
          <td class="td-actions text-end text-nowrap no-export">
            <a class="btn btn-sm btn-outline-primary" href="receipt.php?id=<?= $p['id'] ?>" aria-label="<?= e(t('receipt')) ?>"><i class="bi bi-receipt"></i></a>
            <a class="btn btn-sm btn-outline-secondary" href="payment_add.php?edit=<?= $p['id'] ?>" aria-label="<?= e(t('edit')) ?>"><i class="bi bi-pencil"></i></a>
            <form method="post" class="d-inline" data-verify="<?= e(t('confirm_delete_payment')) ?>">
              <?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= $p['id'] ?>">
              <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button>
            </form>
          </td>
        </tr>
      <?php endforeach; ?>
      </tbody>
      <tfoot><tr class="fw-bold"><td colspan="5" data-en="Total"><?= e(t('total')) ?></td><td><?= money($sum['total']) ?></td><td><?= money($sum['paid']) ?></td><td><?= money($sum['total'] - $sum['paid']) ?></td><td class="no-export"></td></tr></tfoot>
    </table>
  </div>
</div>
<?php
$scripts = ['assets/vendor/jspdf.umd.min.js', 'assets/vendor/jspdf.plugin.autotable.min.js'];
require __DIR__ . '/includes/footer.php';
