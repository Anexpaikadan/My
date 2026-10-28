<?php
// Sidebar on desktop (grouped in sections), slide-out menu and bottom navigation bar on phones.

$sections = nav_sections();
?>
<aside class="offcanvas-lg offcanvas-start sidebar d-print-none" tabindex="-1" id="sidebar" aria-label="<?= e(t('menu')) ?>">
  <div class="offcanvas-header pb-0">
    <button type="button" class="btn-close btn-close-white ms-auto d-lg-none" data-bs-dismiss="offcanvas" data-bs-target="#sidebar" aria-label="Close"></button>
  </div>
  <div class="sidebar-inner">
    <a href="index.php" class="logo-text">
      <span class="l1"><?= e(setting('gym_name', 'VALLEY MMA')) ?></span>
      <span class="l2"><?= e(setting('gym_tagline', 'FIGHT CLUB')) ?></span>
      <span class="l3"><?= e(setting('gym_place', 'PANDIKKAD')) ?></span>
    </a>
    <nav class="nav flex-column mt-2">
      <a class="nav-link<?= $active === 'dashboard' ? ' active' : '' ?>" href="index.php"><i class="bi bi-speedometer2"></i><span><?= e(t('dashboard')) ?></span></a>
      <?php foreach ($sections as $sec => $items): ?>
        <div class="nav-section"><?= e(t($sec)) ?></div>
        <?php foreach ($items as [$href, $key, $icon, $id]): ?>
          <a class="nav-link<?= $active === $id ? ' active' : '' ?>" href="<?= $href ?>"><i class="bi <?= $icon ?>"></i><span><?= e(t($key)) ?></span></a>
        <?php endforeach; ?>
      <?php endforeach; ?>
    </nav>
    <div class="mt-auto pt-3">
      <div class="btn-group w-100 mb-2" role="group" aria-label="Language">
        <a href="lang.php?l=en" class="btn btn-sm <?= lang() === 'en' ? 'btn-light' : 'btn-outline-light' ?>">English</a>
        <a href="lang.php?l=ml" class="btn btn-sm <?= lang() === 'ml' ? 'btn-light' : 'btn-outline-light' ?>">മലയാളം</a>
      </div>
      <button type="button" class="btn btn-sm btn-accent w-100 mb-2 d-none" data-install><i class="bi bi-phone"></i> <?= e(t('install_app')) ?></button>
      <form method="post" action="logout.php"><?= csrf_field() ?>
        <button class="btn btn-sm btn-outline-light w-100"><i class="bi bi-box-arrow-right"></i> <?= e(t('logout')) ?> (<?= e(admin()['username'] ?? '') ?>)</button>
      </form>
      <div class="powered"><img src="assets/daybill-logo.png" alt="DAYbill Solution" width="90" height="90"></div>
    </div>
  </div>
</aside>

<?php
$tab = ['dashboard' => 'home', 'members' => 'members', 'add_member' => 'members', 'plans' => 'members', 'alerts' => 'members',
    'attendance' => 'attendance', 'accounts' => 'money', 'payments' => 'money', 'reports' => 'money'][$active] ?? 'more';
$bottom = [
    ['index.php', 'home', 'bi-house-door', 'bi-house-door-fill', t('home')],
    ['members.php', 'members', 'bi-people', 'bi-people-fill', t('members')],
    ['attendance.php', 'attendance', 'bi-qr-code-scan', 'bi-qr-code-scan', t('attendance')],
    ['accounts.php', 'money', 'bi-wallet2', 'bi-wallet-fill', t('accounts')],
    ['more.php', 'more', 'bi-grid', 'bi-grid-fill', t('more')],
];
?>
<nav class="bottom-nav d-lg-none d-print-none" aria-label="<?= e(t('menu')) ?>">
  <?php foreach ($bottom as [$href, $id, $icon, $iconOn, $label]): ?>
    <a href="<?= $href ?>" class="<?= $tab === $id ? 'on' : '' ?><?= $id === 'attendance' ? ' center' : '' ?>"<?= $tab === $id ? ' aria-current="page"' : '' ?>>
      <span class="bn-ico"><i class="bi <?= $tab === $id ? $iconOn : $icon ?>"></i></span><span class="bn-lbl"><?= e($label) ?></span>
    </a>
  <?php endforeach; ?>
</nav>
