<?php
// "More" page: every part of the app as big tiles, grouped in sections (opened from the bottom bar on phones).

require __DIR__ . '/includes/init.php';
$me = require_admin();

$extra = [
    'sec_members' => [
        ['attendance_monthly.php', 'monthly_attendance', 'bi-calendar3', ''],
        ['alerts.php?tab=birthdays', 'birthdays', 'bi-cake2-fill', ''],
        ['alerts.php?tab=absent', 'absent_members', 'bi-person-dash-fill', ''],
        ['member_print.php', 'print_blank_form', 'bi-printer-fill', ''],
    ],
    'sec_money' => [
        ['payment_add.php', 'record_payment', 'bi-plus-circle-fill', ''],
        ['entry_edit.php?type=expense', 'add_expense', 'bi-dash-circle-fill', ''],
        ['entry_edit.php?type=income', 'add_income', 'bi-plus-square-fill', ''],
        ['ledger.php', 'ledger', 'bi-journal-text', ''],
        ['acc_reports.php?r=pl', 'profit_loss', 'bi-graph-up-arrow', ''],
        ['acc_reports.php?r=cashbook', 'cash_book', 'bi-book-fill', ''],
    ],
    'sec_gym' => [
        ['me.php', 'member_app', 'bi-phone-fill', ''],
    ],
];
$colors = ['sec_members' => 'ico-blue', 'sec_money' => 'ico-green', 'sec_gym' => 'ico-dark'];

$title = t('more');
$active = 'more';
require __DIR__ . '/includes/header.php';
?>
<form action="members.php" class="mb-3" role="search">
  <div class="input-group input-group-lg">
    <span class="input-group-text bg-white"><i class="bi bi-search"></i></span>
    <input class="form-control" type="search" name="s" placeholder="<?= e(t('search_ph')) ?>" aria-label="<?= e(t('search')) ?>">
  </div>
</form>

<?php foreach (nav_sections() as $sec => $items): ?>
  <h2 class="section-head"><?= e(t($sec)) ?></h2>
  <div class="tile-grid mb-4">
    <?php foreach (array_merge($items, $extra[$sec] ?? []) as [$href, $key, $icon]): ?>
      <a href="<?= e($href) ?>" class="tile tap"<?= $href === 'me.php' || $href === 'member_print.php' ? ' target="_blank"' : '' ?>>
        <span class="ico <?= $colors[$sec] ?>"><i class="bi <?= $icon ?>"></i></span>
        <span class="tl"><?= e(t($key)) ?></span>
      </a>
    <?php endforeach; ?>
  </div>
<?php endforeach; ?>

<h2 class="section-head"><?= e(t('app')) ?></h2>
<div class="card mb-4"><div class="list-group list-group-flush">
  <div class="list-group-item d-flex align-items-center gap-2"><i class="bi bi-translate text-primary"></i><span class="me-auto"><?= e(t('language')) ?></span>
    <div class="btn-group btn-group-sm"><a href="lang.php?l=en" class="btn <?= lang() === 'en' ? 'btn-primary' : 'btn-outline-primary' ?>">English</a><a href="lang.php?l=ml" class="btn <?= lang() === 'ml' ? 'btn-primary' : 'btn-outline-primary' ?>">മലയാളം</a></div></div>
  <button type="button" class="list-group-item list-group-item-action d-flex align-items-center gap-2 d-none" data-install><i class="bi bi-phone text-success"></i><span class="me-auto"><?= e(t('install_app')) ?></span><i class="bi bi-chevron-right"></i></button>
  <form method="post" action="logout.php" class="list-group-item p-0"><?= csrf_field() ?>
    <button class="btn w-100 text-start d-flex align-items-center gap-2 px-3 py-2 text-danger"><i class="bi bi-box-arrow-right"></i><span class="me-auto"><?= e(t('logout')) ?> (<?= e($me['username']) ?>)</span></button></form>
</div></div>
<div class="text-center mb-3"><img src="assets/daybill-logo.png" alt="DAYbill Solution" width="70" class="rounded"></div>
<?php require __DIR__ . '/includes/footer.php';
