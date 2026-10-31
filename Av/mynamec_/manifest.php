<?php
// Dynamic manifest — works on any domain automatically
require_once __DIR__ . '/includes/config.php';

$site = defined('SITE_URL') ? rtrim(SITE_URL,'/') : 'https://'.$_SERVER['HTTP_HOST'];
$name = defined('SITE_NAME') ? SITE_NAME : (function_exists('setting') ? setting('CLUB_NAME','Aishwarya Arts & Sports Club') : 'Aishwarya Arts & Sports Club');
$short = 'Aishwarya';

// Try to get short name from settings
try {
    if(function_exists('db')){
        $sn = db()->query("SELECT value FROM settings WHERE key_name='CLUB_SHORT_NAME' LIMIT 1")->fetchColumn();
        if($sn) $short = $sn;
        $fn = db()->query("SELECT value FROM settings WHERE key_name='CLUB_NAME' LIMIT 1")->fetchColumn();
        if($fn) $name = $fn;
    }
} catch(Exception $e){}

header('Content-Type: application/manifest+json');
header('Cache-Control: public, max-age=3600');

echo json_encode([
    'name'             => $name,
    'short_name'       => $short,
    'description'      => $name.' — Community App',
    'start_url'        => '/',
    'scope'            => '/',
    'display'          => 'standalone',
    'orientation'      => 'portrait-primary',
    'background_color' => '#07225c',
    'theme_color'      => '#07225c',
    'icons'            => [
        ['src'=>$site.'/assets/logo.jpg','sizes'=>'192x192','type'=>'image/jpeg','purpose'=>'any'],
        ['src'=>$site.'/assets/logo.jpg','sizes'=>'512x512','type'=>'image/jpeg','purpose'=>'any'],
    ],
    'categories'       => ['social','sports'],
    'lang'             => 'en',
], JSON_UNESCAPED_SLASHES|JSON_PRETTY_PRINT);
