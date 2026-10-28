<?php
// Web app manifest: lets the admin app and the member app be installed on phones ("Add to Home screen").

require __DIR__ . '/includes/init.php';

$member = get('app') === 'member';
$gym = setting('gym_name', 'VALLEY MMA');
header('Content-Type: application/manifest+json');
header('Cache-Control: no-cache');
echo json_encode([
    'id'               => $member ? 'valley-mma-member' : 'valley-mma-admin',
    'name'             => $member ? $gym . ' – ' . t('member_app') : $gym . ' ' . setting('gym_tagline', 'FIGHT CLUB'),
    'short_name'       => $member ? mb_substr($gym, 0, 12) : mb_substr($gym . ' Admin', 0, 16),
    'description'      => 'Fight club membership management',
    'start_url'        => $member ? 'me.php?source=app' : 'index.php?source=app',
    'scope'            => './',
    'display'          => 'standalone',
    'orientation'      => 'portrait',
    'background_color' => '#1A1A1A',
    'theme_color'      => '#360DD9',
    'icons'            => [
        ['src' => 'assets/icons/icon-192.png', 'sizes' => '192x192', 'type' => 'image/png'],
        ['src' => 'assets/icons/icon-512.png', 'sizes' => '512x512', 'type' => 'image/png'],
        ['src' => 'assets/icons/maskable-512.png', 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'maskable'],
    ],
], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
