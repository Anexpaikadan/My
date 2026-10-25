<?php
// Web app manifest – lets the customer page and the staff app be installed on phones/PCs.
// manifest.php?app=staff  -> staff/admin app (opens the job list)
// manifest.php            -> customer app (opens the upload page)

require __DIR__ . '/lib.php';

$staff = ($_GET['app'] ?? '') === 'staff';
$row = !$staff && isset($_GET['shop']) ? shop_by_slug((string)$_GET['shop']) : null;
if ($row) {
    shop_id((int)$row['id']);
}
$shop = $row ? setting('shop_name', $row['name']) : 'DAYbill Print';
$q = $row ? 'shop=' . rawurlencode($row['slug']) . '&' : '';

header('Content-Type: application/manifest+json');
header('Cache-Control: no-cache');
echo json_encode([
    'id'               => $staff ? 'daybill-staff' : 'daybill-customer' . ($row ? '-' . $row['slug'] : ''),
    'name'             => $staff ? 'DAYbill Print – Staff' : $shop,
    'short_name'       => $staff ? 'Print Staff' : mb_substr($shop, 0, 12),
    'description'      => $staff ? 'Print orders, printing and settings' : 'Send files to print',
    'start_url'        => $staff ? 'staff.php?source=app' : 'index.php?' . $q . 'source=app',
    'scope'            => './',
    'display'          => 'standalone',
    'orientation'      => 'portrait',
    'background_color' => '#ffffff',
    'theme_color'      => '#ffffff',
    'icons'            => [
        ['src' => 'assets/icons/icon-192.png', 'sizes' => '192x192', 'type' => 'image/png'],
        ['src' => 'assets/icons/icon-512.png', 'sizes' => '512x512', 'type' => 'image/png'],
        ['src' => 'assets/icons/maskable-512.png', 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'maskable'],
    ],
], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
