<?php
// ================================================================
// extras.php — helpers added with the 2026 redesign.
// Kept out of config.php so the server's own config.php (with the real
// database password) never needs to be replaced. Pages that use these
// load this file themselves, right after config.php.
// ================================================================
require_once __DIR__ . '/config.php';

if (!function_exists('img_optimize')) {
// ── Photo optimiser: called after every upload ────────────────
// Shrinks big photos to max 1200px on the long side and re-saves JPG at 80% quality
// (PNG/WebP keep their format). Safe: if GD is missing or anything fails, the original file stays.
function img_optimize($path, $max = 1200, $quality = 80) {
    if (!is_file($path) || !function_exists('getimagesize') || !function_exists('imagecreatetruecolor')) return false;
    $info = @getimagesize($path); if (!$info) return false;
    list($w, $h) = $info; $type = $info[2];
    if (!in_array($type, array(IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_WEBP), true)) return false;
    if ($type === IMAGETYPE_JPEG && function_exists('exif_read_data')) { $exif = @exif_read_data($path); } else { $exif = null; }
    $src = $type === IMAGETYPE_JPEG ? @imagecreatefromjpeg($path) : ($type === IMAGETYPE_PNG ? @imagecreatefrompng($path) : (function_exists('imagecreatefromwebp') ? @imagecreatefromwebp($path) : false));
    if (!$src) return false;
    // phone photos: apply the camera rotation so they are not shown sideways
    if (!empty($exif['Orientation'])) {
        $o = (int)$exif['Orientation'];
        if ($o === 3) $src = imagerotate($src, 180, 0); elseif ($o === 6) $src = imagerotate($src, -90, 0); elseif ($o === 8) $src = imagerotate($src, 90, 0);
        $w = imagesx($src); $h = imagesy($src);
    }
    $scale = min(1, $max / max($w, $h));
    $nw = max(1, (int)round($w * $scale)); $nh = max(1, (int)round($h * $scale));
    $dst = imagecreatetruecolor($nw, $nh);
    if ($type !== IMAGETYPE_JPEG) { imagealphablending($dst, false); imagesavealpha($dst, true); }
    imagecopyresampled($dst, $src, 0, 0, 0, 0, $nw, $nh, $w, $h);
    $tmp = $path . '.tmp';
    $ok = $type === IMAGETYPE_JPEG ? imagejpeg($dst, $tmp, $quality) : ($type === IMAGETYPE_PNG ? imagepng($dst, $tmp, 7) : imagewebp($dst, $tmp, $quality));
    imagedestroy($src); imagedestroy($dst);
    if ($ok && filesize($tmp) > 0 && ($scale < 1 || filesize($tmp) < filesize($path) || !empty($exif['Orientation']))) { @rename($tmp, $path); return true; }
    @unlink($tmp); return false;
}
}

if (!function_exists('ensure_user_columns')) {
// Add member columns that some pages need, if an older database lacks them (runs once per request, only where called)
function ensure_user_columns() {
    static $done = false; if ($done) return; $done = true;
    try { $have = db()->query("SHOW COLUMNS FROM users")->fetchAll(PDO::FETCH_COLUMN); } catch (Exception $e) { return; }
    $want = array(
        'privacy_phone'    => "VARCHAR(10) DEFAULT 'members'",
        'privacy_photo'    => "VARCHAR(10) DEFAULT 'members'",
        'rejection_reason' => "VARCHAR(255) NULL",
        'approved_by'      => "INT NULL",
        'approved_at'      => "DATETIME NULL",
    );
    foreach ($want as $col => $def) {
        if (!in_array($col, $have, true)) { try { db()->exec("ALTER TABLE users ADD COLUMN $col $def"); } catch (Exception $e) {} }
    }
}
}
