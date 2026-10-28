<?php
// Sidebar on desktop, slide-out menu on phones.

$menu = [
    ['index.php', 'dashboard', 'bi-speedometer2', 'dashboard'],
    ['members.php', 'members', 'bi-people-fill', 'members'],
    ['member_edit.php', 'add_member', 'bi-person-plus-fill', 'add_member'],
    ['plans.php', 'plans', 'bi-card-checklist', 'plans'],
    ['payments.php', 'payments', 'bi-cash-coin', 'payments'],
    ['attendance.php', 'attendance', 'bi-qr-code-scan', 'attendance'],
    ['alerts.php', 'alerts', 'bi-bell-fill', 'alerts'],
    ['reports.php', 'reports', 'bi-bar-chart-fill', 'reports'],
    ['activities.php', 'daily_activity', 'bi-calendar-week', 'activities'],
    ['settings.php', 'settings', 'bi-gear-fill', 'settings'],
    ['backup.php', 'backup', 'bi-cloud-arrow-down-fill', 'backup'],
];
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
    <nav class="nav flex-column mt-3">
      <?php foreach ($menu as [$href, $key, $icon, $id]): ?>
        <a class="nav-link<?= $active === $id ? ' active' : '' ?>" href="<?= $href ?>"><i class="bi <?= $icon ?>"></i><span><?= e(t($key)) ?></span></a>
      <?php endforeach; ?>
    </nav>
    <div class="mt-auto pt-3">
      <div class="btn-group w-100 mb-2" role="group" aria-label="Language">
        <a href="lang.php?l=en" class="btn btn-sm <?= lang() === 'en' ? 'btn-light' : 'btn-outline-light' ?>">English</a>
        <a href="lang.php?l=ml" class="btn btn-sm <?= lang() === 'ml' ? 'btn-light' : 'btn-outline-light' ?>">മലയാളം</a>
      </div>
      <button type="button" class="btn btn-sm btn-accent w-100 mb-2 d-none" id="installBtn"><i class="bi bi-phone"></i> <?= e(t('install_app')) ?></button>
      <form method="post" action="logout.php"><?= csrf_field() ?>
        <button class="btn btn-sm btn-outline-light w-100"><i class="bi bi-box-arrow-right"></i> <?= e(t('logout')) ?> (<?= e(admin()['username'] ?? '') ?>)</button>
      </form>
      <div class="powered"><img src="assets/daybill-logo.png" alt="DAYbill Solution" width="90" height="90"></div>
    </div>
  </div>
</aside>
