<?php
// Settings menu (app-style list). Employees see their own items; admins see everything.

require __DIR__ . '/lib.php';
$user = require_login();
$admin = in_array($user['role'], ['admin', 'super'], true);

// Settings pages open as a sheet sliding up (the link still works as a normal page without JavaScript).
function item(string $href, string $icon, string $label, string $hint = '', bool $sheet = true): string
{
    return '<a class="menu-item" href="' . h($href) . '"' . ($sheet ? ' data-sheet-url="' . h($href) . '" data-sheet-title="' . h($label) . '"' : '')
        . '><span class="ic">' . $icon . '</span>'
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

<?php if (is_super($user)): ?>
  <h3 class="menu-title">All shops</h3>
  <div class="menu card">
    <?= item('shops.php', '🏬', 'Shops', 'Working in: ' . (shop()['name'] ?? '–') . ' · ' . count(all_shops()) . ' shop(s) · add shop, super admins') ?>
  </div>
<?php endif; ?>

<?php if ($admin && shop()): ?>
  <h3 class="menu-title">Shop: <?= h(shop()['name']) ?></h3>
  <div class="menu card">
    <?= item('admin.php?s=employees', '👥', 'Employees', 'Add staff, passwords, disable') ?>
    <?= item('admin.php?s=options', '📄', 'Customer options', 'Paper sizes, colour, sides: ' . implode(', ', enabled_papers())) ?>
    <?= item('admin.php?s=prices', '💰', 'Prices', 'Price rules in ' . setting('currency', 'SR')) ?>
    <?= item('admin.php?s=verify', '🔐', 'Order check', ['staff' => 'Staff check before printing', 'pin' => 'Customer PIN – staff enter it to print',
        'auto' => 'No check – uploads print at once'][verify_mode()]) ?>
    <?= item('admin.php?s=photo', '📷', 'Photo print', !photo_allowed() ? 'Not allowed for this shop (super admin)'
        : (photo_enabled() ? 'On · ' . photo_paper() . ' · ' . count(photo_sizes()) . ' size(s)' : 'Off – passport and photo sizes for customers')) ?>
    <?= item('admin.php?s=layouts', '🗂️', 'Layouts', count(enabled_layouts()) ? count(enabled_layouts()) . ' on: pages per sheet, photo sheets, passport' : 'Off – pages per sheet, photo sheets, passport') ?>
    <?= item('admin.php?s=printing', '🖨️', 'Printing', $modes[setting('print_mode', 'local')] ?? '') ?>
    <?= item('admin.php?s=shop', '🏪', 'Shop settings', setting('shop_name') . ' · language · file cleanup') ?>
    <?= item('admin.php?s=colors', '🎨', 'App colour', 'Theme colours for customers and staff') ?>
    <?= item('qr.php', '▦', 'QR code poster', 'Print the upload QR code') ?>
  </div>
<?php endif; ?>

<h3 class="menu-title">App</h3>
<div class="menu card">
  <?= item('account.php', '🔑', 'My account', 'Change your password') ?>
  <?= item(shop() ? shop_url('index.php') : 'index.php', '📤', 'Customer upload page', 'What customers see after scanning', false) ?>
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
