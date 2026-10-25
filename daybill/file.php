<?php
// Serves an uploaded file to logged-in staff of the same shop (preview or download).
//   file.php?id=N          the file to print (inline: PDF, photo, text; other types download)
//   file.php?id=N&orig=1   the customer's original file when a layout made a print-ready PDF from it
//   file.php?id=N&pv=K     picture of sheet K of a photo order
//   &dl=1                  always download
// Built to work behind hosting that compresses or buffers PHP output: the file is sent untouched,
// and when something is wrong the reason is shown (as a picture for previews) instead of a black screen.

require __DIR__ . '/lib.php';
require_login();

$preview = isset($_GET['pv']);
$asImage = $preview || ($_SERVER['HTTP_SEC_FETCH_DEST'] ?? '') === 'image';

// Clear anything already written (spaces, BOM, notices) and switch off compression for this answer,
// so the browser receives exactly the bytes of the file.
function clean_output(): void
{
    while (ob_get_level() > 0) {
        @ob_end_clean();
    }
    @ini_set('zlib.output_compression', 'Off');
    if (function_exists('apache_setenv')) {
        @apache_setenv('no-gzip', '1');
    }
}

// Error for staff: a small picture inside the preview, or a short page when the file was opened.
function fail(int $code, string $msg, bool $asImage): void
{
    clean_output();
    http_response_code($code);
    header('Cache-Control: no-store');
    if ($asImage) {
        header('Content-Type: image/svg+xml; charset=utf-8');
        echo '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="848" viewBox="0 0 600 848">'
            . '<rect width="600" height="848" fill="#ffffff"/><rect x="1" y="1" width="598" height="846" fill="none" stroke="#c8ced8" stroke-width="2"/>'
            . '<text x="300" y="400" font-family="sans-serif" font-size="30" fill="#687387" text-anchor="middle">Preview not available</text>'
            . '<text x="300" y="450" font-family="sans-serif" font-size="22" fill="#9aa3b2" text-anchor="middle">' . h($msg) . '</text></svg>';
    } else {
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            . '<title>File</title><body style="font:16px system-ui,sans-serif;padding:24px;color:#141925;background:#f4f5fa">'
            . '<h2>Cannot show this file</h2><p>' . h($msg) . '</p><p><a href="staff.php">‹ Back to orders</a></p></body>';
    }
    exit;
}

$st = db()->prepare('SELECT f.original_name, f.stored_name, f.ext, f.orig_name, f.orig_ext, f.previews FROM job_files f
                     JOIN jobs j ON j.id = f.job_id WHERE f.id = ? AND j.shop_id = ?');
$st->execute([(int)($_GET['id'] ?? 0), shop_id()]);
$f = $st->fetch();
// The session is not needed any more: let the other sheet pictures load at the same time.
session_write_close();

if (!$f) {
    fail(404, 'This file is not in this shop.', $asImage);
}
if ($f['stored_name'] === '') {
    fail(404, 'The file was removed from the server (older than the keep time).', $asImage);
}
if ($preview) {
    $k = (int)$_GET['pv'];
    if ($k < 0 || $k >= (int)$f['previews']) {
        fail(404, 'This sheet has no picture.', true);
    }
    $f['stored_name'] .= '.p' . $k . '.jpg';
    $f['ext'] = 'jpg';
    $f['original_name'] = 'sheet-' . ($k + 1) . '.jpg';
} elseif (isset($_GET['orig']) && $f['orig_name'] !== '') {
    $f['stored_name'] = $f['orig_name'];
    $f['ext'] = $f['orig_ext'];
}
$path = cfg('upload_dir') . '/' . $f['stored_name'];
if (!is_file($path)) {
    fail(404, 'The file is missing in the uploads folder.', $asImage);
}
$size = (int)filesize($path);
$fh = @fopen($path, 'rb');
if (!$fh) {
    fail(500, 'The server cannot read the file (check the permissions of the uploads folder).', $asImage);
}

$types = [
    'pdf' => 'application/pdf', 'jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'png' => 'image/png',
    'txt' => 'text/plain; charset=utf-8',
];
$ext = strtolower((string)$f['ext']);
$inline = !isset($_GET['dl']) && isset($types[$ext]);
$name = str_replace(['"', "\r", "\n", '\\'], '', $f['original_name']);

// Part of the file only (phone PDF viewers ask for pieces): "Range: bytes=start-end"
$start = 0;
$end = $size - 1;
$partial = false;
if ($size > 0 && preg_match('/^bytes=(\d*)-(\d*)$/', trim($_SERVER['HTTP_RANGE'] ?? ''), $m) && ($m[1] !== '' || $m[2] !== '')) {
    if ($m[1] === '') {                 // last N bytes
        $start = max(0, $size - (int)$m[2]);
    } else {
        $start = (int)$m[1];
        $end = $m[2] !== '' ? min((int)$m[2], $size - 1) : $size - 1;
    }
    if ($start > $end || $start >= $size) {
        clean_output();
        http_response_code(416);
        header('Content-Range: bytes */' . $size);
        exit;
    }
    $partial = true;
}

clean_output();
if ($partial) {
    http_response_code(206);
    header('Content-Range: bytes ' . $start . '-' . $end . '/' . $size);
}
header('Content-Type: ' . ($types[$ext] ?? 'application/octet-stream'));
header('Content-Disposition: ' . ($inline ? 'inline' : 'attachment') . '; filename="' . $name
    . '"; filename*=UTF-8\'\'' . rawurlencode($f['original_name']));
header('Accept-Ranges: bytes');
header('X-Content-Type-Options: nosniff');
header('Content-Encoding: identity');
// Sheet pictures never change: the phone may keep them for a while. Customer files are not stored.
header($preview ? 'Cache-Control: private, max-age=86400' : 'Cache-Control: private, no-store');
// Only give the length when nothing on the server compresses the answer, otherwise browsers cut it off.
if (!filter_var(ini_get('zlib.output_compression'), FILTER_VALIDATE_BOOLEAN)) {
    header('Content-Length: ' . ($end - $start + 1));
}
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'HEAD') {
    exit;
}

// Send in pieces (works for big files and where readfile() is switched off).
@set_time_limit(0);
fseek($fh, $start);
$left = $end - $start + 1;
while ($left > 0 && !feof($fh) && !connection_aborted()) {
    $chunk = fread($fh, (int)min(262144, $left));
    if ($chunk === false || $chunk === '') {
        break;
    }
    echo $chunk;
    $left -= strlen($chunk);
    flush();
}
fclose($fh);
