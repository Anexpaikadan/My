<?php
// Member profile: details, membership, payments, attendance and WhatsApp messages.

require __DIR__ . '/includes/init.php';
require_admin();

$id = (int)get('id');
$m = q('SELECT m.*, p.name plan_name, p.price plan_price, p.duration_value, p.duration_unit, p.description
        FROM members m LEFT JOIN plans p ON p.id = m.plan_id WHERE m.id = ?', [$id])->fetch();
if (!$m) {
    redirect('members.php');
}
$payments = q('SELECT p.*, pl.name plan_name FROM payments p LEFT JOIN plans pl ON pl.id = p.plan_id WHERE member_id = ? ORDER BY pay_date DESC, id DESC', [$id])->fetchAll();
$balance = member_balance($id);
$month = date('Y-m');
$att = q("SELECT att_date, check_in, method FROM attendance WHERE member_id = ? AND att_date >= ? ORDER BY att_date DESC", [$id, date('Y-m-d', strtotime('-60 day'))])->fetchAll();
$attMonth = count(array_filter($att, fn($a) => substr($a['att_date'], 0, 7) === $month));
$st = member_status($m['expiry_date']);
$dl = days_left($m['expiry_date']);

$msgs = [];
if ($m['plan_name']) {
    $msgs['wa_send_plan'] = t('wa_hello', $m['name']) . "\n\n" . plan_text(['name' => $m['plan_name'], 'price' => $m['plan_price'],
        'duration_value' => $m['duration_value'], 'duration_unit' => $m['duration_unit'], 'description' => $m['description']])
        . "\n" . t('valid_till') . ': ' . fdate($m['expiry_date']);
}
$msgs['wa_send_reminder'] = reminder_text($m, $balance > 0 ? $balance : (float)($m['plan_price'] ?? 0));
if ($balance > 0) {
    $msgs['wa_send_balance'] = t('wa_balance', $m['name'], money($balance), gym_title()) . upi_text($balance);
}
$msgs['wa_send_login'] = t('wa_login', $m['name'], base_url() . 'me.php', $m['phone']);
if ($m['status'] === 'pending') { // not approved yet: only the join link and the app link
    $msgs = array_intersect_key($msgs, ['wa_send_login' => 1]);
    if ($m['invite_token']) {
        $msgs = ['wa_send_invite' => invite_text($m, (string)($_SESSION['invite_pass'][$id] ?? ''))] + $msgs;
    }
}
$attBlock = attendance_block($m);

$title = $m['name'];
$active = 'members';
$back = 'members.php';
$actions = '<a href="member_edit.php?id=' . $id . '" class="btn btn-outline-primary"><i class="bi bi-pencil"></i> ' . e(t('edit')) . '</a>'
    . '<a href="payment_add.php?member=' . $id . '" class="btn btn-accent"><i class="bi bi-cash-coin"></i> ' . e(t('record_payment')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<?php if ($m['status'] === 'pending'): ?>
  <div class="card mb-3 border border-info"><div class="card-body">
    <h3 class="h6"><i class="bi bi-hourglass-split text-info"></i> <?= e(t('waiting_approval')) ?></h3>
    <p class="small mb-2"><?= e($m['details_at'] ? t('details_filled_on', fdate($m['details_at'])) : t('details_not_filled')) ?></p>
    <?php if ($m['invite_token']): ?>
      <div class="input-group input-group-sm mb-3"><input class="form-control" id="invLink" value="<?= e(invite_link($m)) ?>" readonly>
        <button class="btn btn-outline-primary" type="button" data-copy="#invLink" aria-label="Copy"><i class="bi bi-copy"></i></button></div>
    <?php endif; ?>
    <div class="row g-2">
      <div class="col-md-6"><a href="payment_add.php?member=<?= $id ?>&new=1" class="btn btn-accent w-100 h-100 d-flex align-items-center justify-content-center gap-2"><i class="bi bi-cash-coin"></i> <?= e(t('approve_with_payment')) ?></a></div>
      <div class="col-md-6"><form method="post" action="member_action.php" class="input-group" data-verify="<?= e(t('verify_free_days')) ?>"><?= csrf_field() ?>
        <input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="activate_days">
        <input class="form-control" type="number" name="days" min="1" max="366" value="<?= e(setting('trial_days', '7')) ?>" aria-label="<?= e(t('days')) ?>">
        <button class="btn btn-primary"><?= e(t('activate_days')) ?></button></form></div>
    </div>
  </div></div>
<?php elseif ($m['status'] === 'inactive'): ?>
  <div class="alert alert-dark d-flex flex-wrap align-items-center gap-2">
    <i class="bi bi-slash-circle fs-4"></i><span class="me-auto"><?= e(t('member_is_inactive')) ?></span>
    <form method="post" action="member_action.php"><?= csrf_field() ?><input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="activate">
      <button class="btn btn-success"><i class="bi bi-check2-circle"></i> <?= e(t('activate')) ?></button></form>
  </div>
<?php endif; ?>
<div class="row g-3">
  <div class="col-lg-4">
    <div class="card mb-3"><div class="card-body text-center">
      <img src="<?= e(photo_url($m)) ?>" class="avatar-lg mb-2" alt="">
      <h2 class="h5 mb-0"><?= e($m['name']) ?></h2>
      <div class="small-muted mb-2"><?= e($m['adm_no']) ?> · <?= e(t('joined')) ?> <?= e(fdate($m['join_date'])) ?></div>
      <?= status_badge($m['expiry_date'], $m['status']) ?>
      <div class="mt-3 d-grid gap-2">
        <a href="tel:<?= e(clean_phone($m['phone'])) ?>" class="btn btn-light"><i class="bi bi-telephone-fill"></i> <?= e($m['phone']) ?></a>
        <?php if ($attBlock === ''): ?>
        <form method="post" action="attendance.php"><?= csrf_field() ?>
          <input type="hidden" name="action" value="manual"><input type="hidden" name="member_id" value="<?= $id ?>"><input type="hidden" name="back" value="member">
          <button class="btn btn-dark w-100"><i class="bi bi-calendar-check"></i> <?= e(t('mark_present_today')) ?></button>
        </form>
        <?php else: ?>
          <div class="alert alert-secondary py-2 small mb-0"><i class="bi bi-slash-circle"></i> <?= e(t($attBlock)) ?></div>
        <?php endif; ?>
        <?php if ($m['status'] === 'active'): ?>
          <div class="d-flex gap-2">
            <form method="post" action="member_action.php" class="input-group input-group-sm" data-verify="<?= e(t('verify_free_days')) ?>"><?= csrf_field() ?>
              <input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="activate_days">
              <input class="form-control" type="number" name="days" min="1" max="366" value="<?= e(setting('trial_days', '7')) ?>" aria-label="<?= e(t('days')) ?>">
              <button class="btn btn-outline-primary" title="<?= e(t('add_free_days_help')) ?>">+ <?= e(t('days')) ?></button></form>
            <form method="post" action="member_action.php" onsubmit="return confirm(<?= e(json_encode(t('confirm_deactivate', $m['name']))) ?>)"><?= csrf_field() ?>
              <input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="deactivate">
              <button class="btn btn-sm btn-outline-dark text-nowrap h-100"><i class="bi bi-slash-circle"></i> <?= e(t('deactivate')) ?></button></form>
          </div>
        <?php endif; ?>
        <div class="btn-group">
          <a href="member_print.php?id=<?= $id ?>" class="btn btn-outline-secondary" target="_blank"><i class="bi bi-printer"></i> <?= e(t('join_form')) ?></a>
          <a href="member_card.php?id=<?= $id ?>" class="btn btn-outline-secondary" target="_blank"><i class="bi bi-qr-code"></i> <?= e(t('id_card')) ?></a>
        </div>
      </div>
    </div></div>

    <div class="card mb-3"><div class="card-header"><i class="bi bi-whatsapp text-success"></i> WhatsApp</div>
      <div class="card-body d-grid gap-2">
        <?php foreach ($msgs as $key => $text): ?>
          <a class="btn btn-whatsapp text-start" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], $text)) ?>"><i class="bi bi-whatsapp"></i> <?= e(t($key)) ?></a>
        <?php endforeach; ?>
      </div>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="row g-3 mb-3">
      <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('plan')) ?></div><div class="fw-bold"><?= e($m['plan_name'] ?? '–') ?></div></div></div></div>
      <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('expiry_date')) ?></div><div class="fw-bold"><?= e(fdate($m['expiry_date'])) ?></div>
        <div class="small <?= $st === 'expired' ? 'text-danger' : 'text-muted' ?>"><?= $m['expiry_date'] ? e($dl < 0 ? t('expired_days_ago', -$dl) : left_text($dl)) : '' ?></div></div></div></div>
      <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('balance')) ?></div><div class="fw-bold <?= $balance > 0 ? 'text-danger' : 'text-success' ?>"><?= money($balance) ?></div></div></div></div>
      <div class="col-6 col-md-3"><div class="card stat"><div><div class="lbl"><?= e(t('attendance_this_month')) ?></div><div class="fw-bold"><?= $attMonth ?> <?= e(t('days')) ?></div></div></div></div>
    </div>

    <div class="card mb-3">
      <div class="card-header"><ul class="nav nav-pills card-header-pills" role="tablist">
        <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tPay" type="button"><?= e(t('payments')) ?></button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tAtt" type="button"><?= e(t('attendance')) ?></button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tInfo" type="button"><?= e(t('details')) ?></button></li>
      </ul></div>
      <div class="tab-content">
        <div class="tab-pane fade show active" id="tPay">
          <div class="table-responsive"><table class="table table-cards">
            <thead><tr><th><?= e(t('receipt_no')) ?></th><th><?= e(t('date')) ?></th><th><?= e(t('particulars')) ?></th><th><?= e(t('total')) ?></th><th><?= e(t('paid')) ?></th><th></th></tr></thead>
            <tbody>
            <?php if (!$payments): ?><tr><td colspan="6" class="text-center text-muted p-4"><?= e(t('no_payments')) ?></td></tr><?php endif; ?>
            <?php foreach ($payments as $p): ?>
              <tr>
                <td class="td-main fw-semibold">#<?= $p['receipt_no'] ?></td>
                <td data-label="<?= e(t('date')) ?>"><?= e(fdate($p['pay_date'])) ?></td>
                <td data-label="<?= e(t('particulars')) ?>"><?= e($p['plan_name'] ? $p['plan_name'] . ' (' . fdate($p['period_start']) . ' – ' . fdate($p['period_end']) . ')' : ($p['note'] ?: $p['other_note'] ?: t('other_fee'))) ?></td>
                <td data-label="<?= e(t('total')) ?>"><?= money($p['total']) ?></td>
                <td data-label="<?= e(t('paid')) ?>" class="text-success fw-bold"><?= money($p['paid']) ?> <span class="badge text-bg-light"><?= e(t('m_' . $p['method'])) ?></span></td>
                <td class="td-actions text-end"><a href="receipt.php?id=<?= $p['id'] ?>" class="btn btn-sm btn-outline-primary"><i class="bi bi-receipt"></i> <?= e(t('receipt')) ?></a></td>
              </tr>
            <?php endforeach; ?>
            </tbody>
          </table></div>
        </div>
        <div class="tab-pane fade" id="tAtt">
          <div class="p-3">
            <a href="attendance_monthly.php?month=<?= $month ?>&member=<?= $id ?>" class="btn btn-sm btn-outline-primary mb-2"><i class="bi bi-calendar3"></i> <?= e(t('monthly_attendance')) ?></a>
            <?php if (!$att): ?><div class="text-muted"><?= e(t('no_attendance')) ?></div><?php endif; ?>
            <div class="d-flex flex-wrap gap-2">
              <?php foreach ($att as $a): ?>
                <span class="badge text-bg-light border p-2"><?= e(fdate($a['att_date'])) ?> · <?= e(substr($a['check_in'], 0, 5)) ?></span>
              <?php endforeach; ?>
            </div>
          </div>
        </div>
        <div class="tab-pane fade" id="tInfo">
          <div class="p-3">
            <dl class="row mb-0">
              <?php
              $addr = implode(', ', array_filter([$m['address'], $m['place'], $m['city'], $m['post'] ? t('post') . ': ' . $m['post'] : '', $m['district'], $m['state'], $m['pin_code']]));
              $info = [
                  t('address') => $addr, t('occupation') => $m['occupation'], t('dob') => $m['dob'] ? fdate($m['dob']) : '',
                  t('age') => $m['age'], t('gender') => $m['gender'] === 'M' ? t('male') : ($m['gender'] === 'F' ? t('female') : ''),
                  t('height') => $m['height_cm'] ? $m['height_cm'] . ' cm' : '', t('weight') => $m['weight_kg'] ? $m['weight_kg'] . ' kg' : '',
                  'BMI' => $m['bmi'], t('blood_group') => $m['blood_group'], t('urea_creat_uric') => $m['urea_creat_uric'], 'HbA1c' => $m['hba1c'],
                  t('trainer_name') => $m['trainer_name'], t('start_date') => fdate($m['start_date']), t('notes') => $m['notes'],
                  t('member_login') => $m['password_hash'] ? t('login_enabled') : t('login_disabled'),
              ];
              foreach ($info as $k => $v): if ((string)$v === '') continue; ?>
                <dt class="col-5 col-md-4 small-muted fw-normal"><?= e($k) ?></dt><dd class="col-7 col-md-8"><?= e((string)$v) ?></dd>
              <?php endforeach; ?>
            </dl>
            <h3 class="h6 mt-3"><?= e(t('health_screening')) ?></h3>
            <ul class="list-unstyled small mb-0">
              <?php for ($i = 1; $i <= 8; $i++): $v = $m['hq' . $i]; ?>
                <li class="py-1 border-bottom d-flex gap-2"><span class="me-auto"><?= $i ?>. <?= e(t('hq' . $i)) ?></span>
                  <?php if ($v === null): ?><span class="text-muted">–</span><?php elseif ((int)$v === 1): ?><span class="badge bg-danger"><?= e(t('yes')) ?></span><?php else: ?><span class="badge bg-success"><?= e(t('no')) ?></span><?php endif; ?></li>
              <?php endfor; ?>
            </ul>
            <?php if ($m['health_notes'] !== ''): ?><p class="mt-2 mb-0"><strong><?= e(t('health_notes')) ?>:</strong> <?= e($m['health_notes']) ?></p><?php endif; ?>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
