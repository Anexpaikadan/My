  <footer class="dev-credit d-print-none">
    <img src="assets/daybill-logo.png" alt="" width="28" height="28"><span><?= e(t('developed_by')) ?> <b>DAYbill Solution</b></span>
  </footer>
</main>
<?php if (admin() && empty($bare)): ?>
<div class="modal fade" id="verifyModal" tabindex="-1" aria-labelledby="verifyTitle" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm"><form class="modal-content" id="verifyForm">
    <div class="modal-header"><h2 class="modal-title h6" id="verifyTitle"><i class="bi bi-shield-lock-fill text-primary"></i> <?= e(t('verify_title')) ?></h2>
      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
    <div class="modal-body">
      <p class="small mb-2" id="verifyMsg"></p>
      <label class="form-label small" for="verifyPass"><?= e(t('verify_enter', admin()['username'])) ?></label>
      <input class="form-control form-control-lg" type="password" id="verifyPass" autocomplete="current-password" required>
    </div>
    <div class="modal-footer"><button type="button" class="btn btn-light" data-bs-dismiss="modal"><?= e(t('cancel')) ?></button>
      <button class="btn btn-primary" id="verifyGo"><i class="bi bi-check2-circle"></i> <?= e(t('confirm')) ?></button></div>
  </form></div>
</div>
<?php endif; ?>
<script src="assets/vendor/bootstrap.bundle.min.js"></script>
<?php foreach ($scripts ?? [] as $src): ?>
<script src="<?= e($src) ?>"></script>
<?php endforeach; ?>
<script>window.VM = <?= json_encode([
    'lang' => lang(),
    'gym' => gym_title(),
    'place' => setting('gym_place', 'PANDIKKAD'),
    'phones' => trim(setting('phone1') . '  ' . setting('phone2')),
], JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) ?>;</script>
<script src="assets/app.js?v=<?= e(APP_VERSION) ?>"></script>
</body>
</html>
