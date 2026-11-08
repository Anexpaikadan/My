<?php
// ================================================================
// og.php — link previews (WhatsApp / Facebook) for every page
// Admin → Public Website → "Link preview": on/off switch, title, text, photo.
// A page may pass its own title/description/image (e.g. one event).
// ================================================================
require_once __DIR__ . '/config.php';
if (!function_exists('og_tags')) {

function site_cfg($key, $default = '') {
    static $c = null;
    if ($c === null) {
        $c = array();
        try { foreach (db()->query("SELECT setting_key,setting_value FROM club_settings")->fetchAll() as $r) $c[$r['setting_key']] = $r['setting_value']; } catch (Exception $e) {}
    }
    return (isset($c[$key]) && $c[$key] !== '') ? $c[$key] : $default;
}
function site_img_url($path) {
    if ($path === '' || $path === null) return '';
    if (preg_match('#^https?://#', $path)) return $path;
    return rtrim(defined('SITE_URL') ? SITE_URL : '', '/') . '/' . ltrim($path, '/');
}

// $page = array('title'=>…, 'desc'=>…, 'image'=>…, 'url'=>…) — all optional
function og_tags($page = array()) {
    if (site_cfg('og_on', '1') !== '1') return '';
    $club  = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $title = !empty($page['title']) ? $page['title'] : site_cfg('og_title', $club . ' · ' . setting('CLUB_PLACE', 'Vettikkattiri'));
    $desc  = !empty($page['desc'])  ? $page['desc']  : site_cfg('og_desc', setting('CLUB_TAGLINE', 'Unity · Sports · Culture · Community'));
    $img   = !empty($page['image']) ? $page['image'] : site_img_url(site_cfg('og_image', 'assets/icons/app/icon-512.png'));
    $url   = !empty($page['url'])   ? $page['url']   : rtrim(defined('SITE_URL') ? SITE_URL : '', '/') . (isset($_SERVER['REQUEST_URI']) ? strtok($_SERVER['REQUEST_URI'], '#') : '/');
    $e = function ($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); };
    return '<meta property="og:type" content="website">' . "\n"
         . '<meta property="og:site_name" content="' . $e($club) . '">' . "\n"
         . '<meta property="og:title" content="' . $e($title) . '">' . "\n"
         . '<meta property="og:description" content="' . $e($desc) . '">' . "\n"
         . '<meta property="og:image" content="' . $e($img) . '">' . "\n"
         . '<meta property="og:url" content="' . $e($url) . '">' . "\n"
         . '<meta name="twitter:card" content="summary_large_image">' . "\n"
         . '<meta name="description" content="' . $e($desc) . '">' . "\n";
}

}
