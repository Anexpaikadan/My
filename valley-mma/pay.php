<?php
// Public UPI payment page (linked from WhatsApp messages): QR code, "Pay with UPI app" button and the UPI ID.

require __DIR__ . '/includes/init.php';

$amount = min(1000000, num(get('a')));
$link = upi_link($amount, gym_title());
$title = t('pay_by_upi');
$bare = true;
$memberApp = true;
require __DIR__ . '/includes/header.php';
?>
<div class="text-center pt-3">
  <?= brand_html('', 'mb-3') ?>
  <div class="card"><div class="card-body p-4">
    <?php if ($link === ''): ?>
      <p class="mb-0"><?= e(t('upi_not_set_public')) ?><br><b><?= e(setting('phone1')) ?></b></p>
    <?php else: ?>
      <h1 class="h5"><?= e(t('pay_by_upi')) ?></h1>
      <?php if ($amount > 0): ?><div class="display-6 fw-bold text-primary mb-2"><?= money($amount) ?></div><?php endif; ?>
      <div class="qr-box border mb-3" data-qr="<?= e($link) ?>"></div>
      <div class="alert alert-warning text-start small mb-3">
        <div class="fw-bold mb-1"><i class="bi bi-camera"></i> <?= e(t('pay_screenshot_title')) ?></div>
        <ol class="mb-0 ps-3"><li><?= e(t('pay_step1')) ?></li><li><?= e(t('pay_step2')) ?></li><li><?= e(t('pay_step3')) ?></li></ol>
      </div>
      <div class="small-muted"><?= e(t('upi_id')) ?></div>
      <div class="input-group mb-2">
        <input class="form-control text-center fw-bold" value="<?= e(setting('upi_id')) ?>" readonly id="upiId">
        <button class="btn btn-outline-primary" type="button" data-copy="#upiId"><i class="bi bi-copy"></i></button>
      </div>
      <?php if (setting('upi_phone') !== ''): ?><div class="small-muted"><?= e(t('upi_phone')) ?>: <b><?= e(setting('upi_phone')) ?></b></div><?php endif; ?>
      <div class="small-muted mt-1"><?= e(setting('upi_name')) ?></div>
      <p class="small mt-3 mb-2"><?= e(t('send_screenshot')) ?></p>
      <?php if (setting('phone1') !== ''): ?>
        <a class="btn btn-whatsapp w-100" target="_blank" rel="noopener" href="<?= e(wa_link(setting('phone1'), t('wa_paid_screenshot', gym_title(), $amount > 0 ? money($amount) : ''))) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('send_screenshot_btn')) ?></a>
      <?php endif; ?>
    <?php endif; ?>
  </div></div>
</div>
<?php
$scripts = ['assets/vendor/qrcode.js', 'assets/qr.js'];
require __DIR__ . '/includes/footer.php';
