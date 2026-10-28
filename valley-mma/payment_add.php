<?php
// Record a payment: admission fee, plan (renews the membership), other fee, paid amount and balance.

require __DIR__ . '/includes/init.php';
$me = require_admin();

$members = q('SELECT id, name, phone, adm_no, expiry_date, plan_id FROM members ORDER BY name')->fetchAll();
$plans = q('SELECT * FROM plans WHERE active = 1 ORDER BY sort_order, id')->fetchAll();
$plansById = array_column($plans, null, 'id');
$memberId = (int)($_POST['member_id'] ?? $_GET['member'] ?? 0);
$m = $memberId ? q('SELECT * FROM members WHERE id = ?', [$memberId])->fetch() : null;
$errors = [];

// Next period starts the day after the current expiry (or today when already expired).
$nextStart = function (?array $m): string {
    if ($m && $m['expiry_date'] && $m['expiry_date'] >= today()) {
        return date('Y-m-d', strtotime($m['expiry_date'] . ' +1 day'));
    }
    return today();
};

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!$m) {
        $errors[] = t('err_member');
    }
    $payDate = post('pay_date');
    if (!valid_date($payDate)) {
        $errors[] = t('err_date');
    }
    $planId = isset($plansById[(int)post('plan_id')]) ? (int)post('plan_id') : null;
    $start = post('period_start');
    $end = post('period_end');
    if ($planId) {
        if (!valid_date($start)) {
            $errors[] = t('err_date');
        } elseif (!valid_date($end)) {
            $p = $plansById[$planId];
            $end = plan_end($start, (int)$p['duration_value'], $p['duration_unit']);
        }
        if (valid_date($start) && valid_date($end) && $end < $start) {
            $errors[] = t('err_period');
        }
    }
    $adm = num(post('admission_fee'));
    $planFee = $planId ? num(post('plan_fee')) : 0;
    $other = num(post('other_fee'));
    $total = $adm + $planFee + $other;
    $paid = num(post('paid'));
    $method = in_array(post('method'), ['cash', 'upi', 'card', 'bank'], true) ? post('method') : 'cash';
    if ($total <= 0 && $paid <= 0) {
        $errors[] = t('err_amount');
    }
    if (!$errors) {
        $no = next_receipt_no();
        q('INSERT INTO payments (receipt_no, member_id, plan_id, pay_date, admission_fee, plan_fee, other_fee, other_note, total, paid,
               method, upi_ref, period_start, period_end, prev_plan_id, prev_start, prev_expiry, note, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [$no, $m['id'], $planId, $payDate, $adm, $planFee, $other, mb_substr(post('other_note'), 0, 100), $total, $paid,
                $method, mb_substr(post('upi_ref'), 0, 50), $planId ? $start : null, $planId ? $end : null,
                $m['plan_id'], $m['start_date'], $m['expiry_date'], mb_substr(post('note'), 0, 255), $me['id']]);
        $pid = (int)db()->lastInsertId();
        if ($planId) {
            sync_membership((int)$m['id']);
        }
        flash('success', t('payment_saved', $no));
        redirect('receipt.php?id=' . $pid . '&new=1');
    }
}

$balance = $m ? member_balance((int)$m['id']) : 0;
$isNew = get('new') === '1' || ($m && !q('SELECT COUNT(*) FROM payments WHERE member_id = ?', [$m['id']])->fetchColumn());
$defPlan = (int)($_POST['plan_id'] ?? ($m['plan_id'] ?? ($plans[0]['id'] ?? 0)));
$defStart = $_POST['period_start'] ?? $nextStart($m);

$title = t('record_payment');
$active = 'payments';
$back = 'payments.php';
require __DIR__ . '/includes/header.php';
$val = fn($k, $def = '') => e($_POST[$k] ?? $def);
?>
<?php if ($errors): ?><div class="alert alert-danger"><?= implode('<br>', array_map('e', array_unique($errors))) ?></div><?php endif; ?>
<form method="post" id="payForm" class="row g-3" data-balance="<?= e((string)$balance) ?>">
  <?= csrf_field() ?>
  <div class="col-lg-7">
    <div class="card mb-3"><div class="card-body row g-3">
      <div class="col-12"><label class="form-label" for="member_id"><?= e(t('member')) ?> *</label>
        <select class="form-select form-select-lg" id="member_id" name="member_id" required onchange="location.href='payment_add.php?member='+this.value">
          <option value=""><?= e(t('choose_member')) ?></option>
          <?php foreach ($members as $mm): ?>
            <option value="<?= $mm['id'] ?>"<?= $memberId === (int)$mm['id'] ? ' selected' : '' ?>><?= e($mm['name'] . ' – ' . $mm['adm_no'] . ' – ' . $mm['phone']) ?></option>
          <?php endforeach; ?>
        </select>
        <?php if ($m): ?>
          <div class="small-muted mt-2"><?= e(t('expiry_date')) ?>: <?= e(fdate($m['expiry_date'])) ?> <?= status_badge($m['expiry_date']) ?>
            · <?= e(t('old_balance')) ?>: <b class="<?= $balance > 0 ? 'text-danger' : '' ?>"><?= money($balance) ?></b></div>
        <?php endif; ?>
      </div>
      <div class="col-6"><label class="form-label" for="pay_date"><?= e(t('date')) ?></label>
        <input class="form-control" type="date" id="pay_date" name="pay_date" value="<?= $val('pay_date', today()) ?>" required></div>
      <div class="col-6"><label class="form-label" for="receipt"><?= e(t('receipt_no')) ?></label>
        <input class="form-control" id="receipt" value="<?= next_receipt_no() ?>" disabled></div>
    </div></div>

    <div class="card mb-3"><div class="card-body row g-3">
      <span class="section-title mb-0"><?= e(t('particulars')) ?></span>
      <div class="col-12"><label class="form-label" for="admission_fee"><?= e(t('admission_fee')) ?></label>
        <input class="form-control" type="number" min="0" step="0.01" id="admission_fee" name="admission_fee" value="<?= $val('admission_fee', $isNew ? setting('admission_fee', '0') : '0') ?>" data-sum></div>
      <div class="col-12">
        <label class="form-label d-block"><?= e(t('plan')) ?></label>
        <div class="d-flex flex-wrap gap-2" role="group">
          <input type="radio" class="btn-check" name="plan_id" id="pl0" value=""<?= !$defPlan ? ' checked' : '' ?> data-plan-radio data-price="0">
          <label class="btn btn-outline-secondary" for="pl0"><?= e(t('no_plan_renew')) ?></label>
          <?php foreach ($plans as $p): ?>
            <input type="radio" class="btn-check" name="plan_id" id="pl<?= $p['id'] ?>" value="<?= $p['id'] ?>"<?= $defPlan === (int)$p['id'] ? ' checked' : '' ?>
              data-plan-radio data-price="<?= e($p['price']) ?>" data-v="<?= (int)$p['duration_value'] ?>" data-u="<?= e($p['duration_unit']) ?>">
            <label class="btn btn-outline-primary" for="pl<?= $p['id'] ?>"><?= e($p['name']) ?><br><small><?= money($p['price']) ?></small></label>
          <?php endforeach; ?>
        </div>
      </div>
      <div class="col-12 plan-fields row g-3 m-0 p-0">
        <div class="col-12 col-sm-4"><label class="form-label" for="plan_fee"><?= e(t('plan_fee')) ?></label>
          <input class="form-control" type="number" min="0" step="0.01" id="plan_fee" name="plan_fee" value="<?= $val('plan_fee', (string)($plansById[$defPlan]['price'] ?? 0)) ?>" data-sum></div>
        <div class="col-6 col-sm-4"><label class="form-label" for="period_start"><?= e(t('from')) ?></label>
          <input class="form-control" type="date" id="period_start" name="period_start" value="<?= e($defStart) ?>" data-plan-start></div>
        <div class="col-6 col-sm-4"><label class="form-label" for="period_end"><?= e(t('to')) ?></label>
          <input class="form-control" type="date" id="period_end" name="period_end" value="<?= $val('period_end') ?>" data-plan-end></div>
      </div>
      <div class="col-5"><label class="form-label" for="other_fee"><?= e(t('other_fee')) ?></label>
        <input class="form-control" type="number" min="0" step="0.01" id="other_fee" name="other_fee" value="<?= $val('other_fee', '0') ?>" data-sum></div>
      <div class="col-7"><label class="form-label" for="other_note"><?= e(t('other_fee_for')) ?></label>
        <input class="form-control" id="other_note" name="other_note" value="<?= $val('other_note') ?>" maxlength="100" placeholder="<?= e(t('other_fee_ph')) ?>"></div>
    </div></div>
  </div>

  <div class="col-lg-5">
    <div class="card mb-3 position-sticky" style="top:1rem"><div class="card-body">
      <div class="d-flex justify-content-between fs-5 mb-2"><span><?= e(t('total')) ?></span><b id="sumTotal">₹0</b></div>
      <?php if ($balance > 0): ?>
        <div class="d-flex justify-content-between text-danger mb-2"><span><?= e(t('old_balance')) ?></span><b><?= money($balance) ?></b></div>
      <?php endif; ?>
      <label class="form-label" for="paid"><?= e(t('paid_amount')) ?></label>
      <div class="input-group input-group-lg mb-2"><span class="input-group-text">₹</span>
        <input class="form-control fw-bold" type="number" min="0" step="0.01" id="paid" name="paid" value="<?= $val('paid') ?>" required></div>
      <div class="d-flex gap-2 mb-3">
        <button type="button" class="btn btn-sm btn-light" data-fill="total"><?= e(t('pay_total')) ?></button>
        <?php if ($balance > 0): ?><button type="button" class="btn btn-sm btn-light" data-fill="all"><?= e(t('pay_with_balance')) ?></button><?php endif; ?>
      </div>
      <div class="d-flex justify-content-between fs-5 mb-3"><span><?= e(t('balance_after')) ?></span><b id="sumBalance">₹0</b></div>

      <label class="form-label d-block"><?= e(t('payment_method')) ?></label>
      <div class="btn-group w-100 mb-3" role="group">
        <?php foreach (['cash' => 'bi-cash', 'upi' => 'bi-phone', 'card' => 'bi-credit-card', 'bank' => 'bi-bank'] as $k => $ic): ?>
          <input type="radio" class="btn-check" name="method" id="me_<?= $k ?>" value="<?= $k ?>"<?= ($_POST['method'] ?? 'cash') === $k ? ' checked' : '' ?>>
          <label class="btn btn-outline-primary" for="me_<?= $k ?>"><i class="bi <?= $ic ?>"></i> <?= e(t('m_' . $k)) ?></label>
        <?php endforeach; ?>
      </div>
      <div id="upiBox" class="text-center mb-3 d-none">
        <?php if (setting('upi_id') !== ''): ?>
          <div class="qr-box border mb-2" id="upiQr" data-upi="<?= e(upi_link(0, gym_title())) ?>"></div>
          <div class="small fw-semibold"><?= e(setting('upi_id')) ?><?= setting('upi_phone') !== '' ? ' · ' . e(setting('upi_phone')) : '' ?></div>
        <?php else: ?>
          <div class="alert alert-warning small"><?= e(t('upi_not_set')) ?> <a href="settings.php"><?= e(t('settings')) ?></a></div>
        <?php endif; ?>
        <input class="form-control mt-2" name="upi_ref" value="<?= $val('upi_ref') ?>" maxlength="50" placeholder="<?= e(t('upi_ref')) ?>">
      </div>
      <label class="form-label" for="note"><?= e(t('note')) ?></label>
      <input class="form-control mb-3" id="note" name="note" value="<?= $val('note') ?>" maxlength="255">
      <button class="btn btn-primary btn-lg w-100"><i class="bi bi-check2-circle"></i> <?= e(t('save_print_receipt')) ?></button>
    </div></div>
  </div>
</form>
<?php
$scripts = ['assets/vendor/qrcode.js', 'assets/qr.js'];
require __DIR__ . '/includes/footer.php';
