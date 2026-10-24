<?php
// Settings menu (app-style list). Employees see their own items; admins see everything.

require __DIR__ . '/lib.php';
$user = require_login();
$admin = $user['role'] === 'admin';

function item(string $href, string $icon, string $label, string $hint = ''): string
{
    return '<a class="menu-item" href="' . h($href) . '"><span class="ic">' . $icon . '</span>'
        . '<span class="txt"><b>' . h($label) . '</b>' . ($hint !== '' ? '<small>' . h($hint) . '</small>' : '') . '</span>'
        . '<span class="chev">›</span></a>';
}

$modes = ['local' => 'Local printing (XAMPP)', 'agent' => 'Cloud + print agent', 'browser' => 'Browser printing'];

page_header('Settings', true);
echo flash();
?>
<div class="profile card">
  <span class="avatar"><?= h(mb_strtoupper(mb_substr($user['full_name'] ?: $user['username'], 0, 1))) ?></span>
  <div><b><?= h($user['full_name'] ?: $user['username']) ?></b><div class="muted">@<?= h($user['username']) ?> · <?= h($user['role']) ?></div></div>
</div>

<?php if ($admin): ?>
  <h3 class="menu-title">Shop</h3>
  <div class="menu card">
    <?= item('admin.php?s=employees', '👥', 'Employees', 'Add staff, passwords, disable') ?>
    <?= item('admin.php?s=options', '📄', 'Customer options', 'Paper sizes, colour, sides: ' . implode(', ', enabled_papers())) ?>
    <?= item('admin.php?s=prices', '💰', 'Prices', 'Price rules in ' . setting('currency', 'SR')) ?>
    <?= item('admin.php?s=printing', '🖨️', 'Printing', $modes[setting('print_mode', 'local')] ?? '') ?>
    <?= item('admin.php?s=shop', '🏪', 'Shop settings', setting('shop_name') . ' · language · file cleanup') ?>
    <?= item('qr.php', '▦', 'QR code poster', 'Print the upload QR code') ?>
  </div>
<?php endif; ?>

<h3 class="menu-title">App</h3>
<div class="menu card">
  <?= item('account.php', '🔑', 'My account', 'Change your password') ?>
  <?= item('index.php', '📤', 'Customer upload page', 'What customers see after scanning') ?>
</div>

<h3 class="menu-title">Install on this device</h3>
<div class="card">
  <p class="muted">Install the staff app on this phone or PC – it opens full screen from its own icon, like a normal app.</p>
  <?= install_box() ?>
</div>

<div class="menu card">
  <a class="menu-item danger" href="logout.php"><span class="ic">⏻</span><span class="txt"><b>Log out</b></span></a>
</div>
<?php page_footer(); ?>
