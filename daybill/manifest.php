<?php
// Web app manifest – lets the customer page and the staff app be installed on phones/PCs.
// manifest.php?app=staff  -> staff/admin app (opens the job list)
// manifest.php            -> customer app (opens the upload page)

require __DIR__ . '/lib.php';

$staff = ($_GET['app'] ?? '') === 'staff';
$shop = setting('shop_name', 'Daybill Print');

header('Content-Type: application/manifest+json');
header('Cache-Control: no-cache');
echo json_encode([
    'id'               => $staff ? 'daybill-staff' : 'daybill-customer',
    'name'             => $staff ? $shop . ' – Staff' : $shop,
    'short_name'       => $staff ? 'Print Staff' : mb_substr($shop, 0, 12),
    'description'      => $staff ? 'Print orders, printing and settings' : 'Send files to print',
    'start_url'        => $staff ? 'staff.php?source=app' : 'index.php?source=app',
    'scope'            => './',
    'display'          => 'standalone',
    'orientation'      => 'portrait',
    'background_color' => '#f3f5f9',
    'theme_color'      => '#12233f',
    'icons'            => [
        ['src' => 'assets/icons/icon-192.png', 'sizes' => '192x192', 'type' => 'image/png'],
        ['src' => 'assets/icons/icon-512.png', 'sizes' => '512x512', 'type' => 'image/png'],
        ['src' => 'assets/icons/maskable-512.png', 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'maskable'],
    ],
], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
