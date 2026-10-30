<?php
// Valley Rules page (public link, sent to members on WhatsApp). The admin changes the rules in "Public page".

require_once __DIR__ . '/includes/init.php';

$title = pub('pub_rules_title');
$bare = true;
$publicPage = 'rules';
require __DIR__ . '/includes/header.php';
?>
<div class="pub-wrap pt-3">
  <div class="pub-page-head">
    <img src="assets/logo.png" alt="<?= e(gym_title()) ?>" width="612" height="106">
    <h1 class="pub-h mb-0"><?= e(pub('pub_rules_title')) ?></h1>
  </div>
  <?= rules_html() ?>
  <?php if (admin()): ?>
    <textarea class="visually-hidden" id="rulesText" tabindex="-1" aria-hidden="true"><?= e(rules_text()) ?></textarea>
    <div class="d-grid gap-2 my-3">
      <a class="btn btn-whatsapp btn-lg" href="<?= e(wa_link('', rules_text())) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(t('share_whatsapp_group')) ?></a>
      <button type="button" class="btn btn-outline-light" data-copy="#rulesText"><i class="bi bi-copy"></i> <?= e(t('copy_text')) ?></button>
      <a class="btn btn-outline-light" href="public_settings.php#rules"><i class="bi bi-pencil"></i> <?= e(t('edit_rules')) ?></a>
    </div>
  <?php endif; ?>
</div>
<?php require __DIR__ . '/includes/footer.php';
