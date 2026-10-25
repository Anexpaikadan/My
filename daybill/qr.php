<?php
// Admin: printable QR code poster that opens the customer upload page.

require __DIR__ . '/lib.php';
require_admin();

// Phones cannot reach "localhost" – suggest the PC's network address instead.
$default = shop_url('index.php');
$host = preg_replace('/:\d+$/', '', $_SERVER['HTTP_HOST'] ?? '');
if (in_array($host, ['localhost', '127.0.0.1', '::1', '[::1]'], true)) {
    $lan = gethostbyname(gethostname());
    if ($lan && $lan !== gethostname() && strpos($lan, '127.') !== 0) {
        $default = str_replace('//' . $host, '//' . $lan, $default);
    }
}
$url = trim((string)($_GET['url'] ?? setting('upload_url', $default)));
// The QR code must always open the HTTPS address.
$url = preg_replace('#^http://#i', 'https://', $url);
if (!preg_match('#^https://#i', $url)) {
    $url = $url !== '' ? 'https://' . ltrim($url, '/') : $default;
}
// Each shop's QR code opens its own upload page.
if (shop() && strpos($url, 'shop=') === false) {
    $url .= (strpos($url, '?') === false ? '?' : '&') . 'shop=' . rawurlencode(shop()['slug']);
}
if (isset($_GET['url'])) {
    save_setting('upload_url', $url);
}

page_header('QR code', true);
?>
<div class="card noprint">
  <h2>Upload QR code</h2>
  <p class="muted">Customers scan this to open the upload page. Use your PC's Wi‑Fi/LAN address (e.g. <code>https://192.168.1.10/daybill/</code>), not <code>localhost</code>. Customers' phones must be on the shop Wi‑Fi.</p>
  <form method="get" class="search">
    <input name="url" value="<?= h($url) ?>">
    <button class="btn">Update</button>
  </form>
  <p><button class="btn primary" onclick="window.print()">🖨 Print poster</button></p>
</div>

<div class="poster">
  <img src="assets/logo.png" alt="DAYbill Solution" class="logo">
  <h1><?= h(setting('shop_name', 'Daybill Print')) ?></h1>
  <p class="lead">Scan to send your files for printing</p>
  <div id="qr"></div>
  <p class="url"><?= h($url) ?></p>
  <ol>
    <li>Scan the QR code with your phone camera</li>
    <li>Choose files, copies &amp; paper size</li>
    <li>Tap <b>Upload</b> and show your code at the counter</li>
  </ol>
</div>

<script src="assets/qrcode.js"></script>
<script>
  var qr = qrcode(0, 'M');
  qr.addData(<?= json_encode($url) ?>);
  qr.make();
  document.getElementById('qr').innerHTML = qr.createSvgTag({ cellSize: 8, margin: 2, scalable: true });
</script>
<?php page_footer(); ?>
