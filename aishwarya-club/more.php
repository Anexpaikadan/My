<?php
// more.php — every page as an icon tile (the "More" tab on phones)
require_once __DIR__ . '/includes/config.php';
requireLogin();
$pageTitle = 'More';
require_once __DIR__ . '/includes/header.php';
$_groups = array();
foreach (app_modules() as $m) { $_groups[$m[4]][] = $m; }
if ($isAdmin) {
    foreach (admin_modules() as $m) {
        if ($m[0] === 'modules/settings.php' && !isSuperAdmin($user)) continue;
        if (in_array($m[0], array('modules/site.php','modules/enquiries.php'), true) && !isFullAdmin($user)) continue;
        $_groups['Admin'][] = $m;
    }
}
$_gname = array('Club' => 'Club', 'Activities' => 'Activities', 'Support' => 'Support', 'Me' => 'Me', 'Admin' => t('nav_admin'));
?>
<div class="app-wrap">
  <?php foreach ($_groups as $g => $items): ?>
  <h2 class="h-app"><?= h(isset($_gname[$g]) ? $_gname[$g] : $g) ?></h2>
  <div class="tiles">
    <?php foreach ($items as $m): $mm = app_meta($m[0]); ?>
    <a class="tile-l <?= $mm[1] ?>" href="<?= url($m[0]) ?>">
      <span class="ico" aria-hidden="true"><i class="bi bi-<?= $mm[0] ?>"></i></span>
      <?= h(app_label($m[0], $m[1])) ?>
      <?php if ($m[0] === 'admin.php' && $pendingBadge): ?><span class="badge rounded-pill text-bg-danger"><?= $pendingBadge ?> new</span><?php endif; ?>
    </a>
    <?php endforeach; ?>
  </div>
  <?php endforeach; ?>

  <h2 class="h-app"><?= h(t('nav_more')) ?></h2>
  <div class="tiles">
    <a class="tile-l c-slate" href="<?= url('index.php') ?>"><span class="ico" aria-hidden="true"><i class="bi bi-globe2"></i></span><?= h(t('nav_website')) ?></a>
    <a class="tile-l c-blue" href="<?= h(lang_url(lang_current() === 'ml' ? 'en' : 'ml')) ?>"><span class="ico" aria-hidden="true"><i class="bi bi-translate"></i></span><?= h(t('lang_switch')) ?></a>
    <button type="button" class="tile-l c-violet" id="pwaInstallBtn" style="display:none" onclick="if(window._pwaPrompt){window._pwaPrompt.prompt();}"><span class="ico" aria-hidden="true"><i class="bi bi-phone"></i></span>Install app</button>
    <a class="tile-l c-red" href="<?= url('logout.php') ?>"><span class="ico" aria-hidden="true"><i class="bi bi-box-arrow-right"></i></span><?= h(t('nav_logout')) ?></a>
  </div>
</div>
<?php require_once __DIR__ . '/includes/footer.php'; ?>
