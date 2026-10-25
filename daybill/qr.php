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

// Staff QR code: the same address, but the staff login page (employees and admins scan it to log in).
$staffMode = ($_GET['for'] ?? '') === 'staff';
$base = preg_replace('#[^/]*\.php$#', '', preg_replace('/[?#].*$/', '', $url));
$staffUrl = rtrim($base, '/') . '/login.php';
$qrUrl = $staffMode ? $staffUrl : $url;
$tab = fn(bool $staff) => 'qr.php' . ($staff ? '?for=staff' : '') . (in_sheet() ? ($staff ? '&' : '?') . 'sheet=1' : '');

page_header('QR code', true);
?>
<nav class="tabs noprint">
  <a href="<?= h($tab(false)) ?>" class="<?= $staffMode ? '' : 'on' ?>">📤 Customers – upload</a>
  <a href="<?= h($tab(true)) ?>" class="<?= $staffMode ? 'on' : '' ?>">🔑 Staff – login</a>
</nav>
<div class="card noprint">
  <?php if ($staffMode): ?>
    <h2>Staff login QR code</h2>
    <p class="muted">Employees and admins scan this to open the staff <b>login page</b>, log in with their own username and password,
      and install the staff app (Add to Home Screen). Keep this poster behind the counter – not where customers see it.</p>
  <?php else: ?>
    <h2>Upload QR code</h2>
    <p class="muted">Customers scan this to open the upload page. Use your PC's Wi‑Fi/LAN address (e.g. <code>https://192.168.1.10/daybill/</code>), not <code>localhost</code>. Customers' phones must be on the shop Wi‑Fi.</p>
  <?php endif; ?>
  <form method="get" class="search">
    <?= sheet_field() ?>
    <?php if ($staffMode): ?><input type="hidden" name="for" value="staff"><?php endif; ?>
    <input name="url" value="<?= h($url) ?>" aria-label="Website address">
    <button class="btn">Update</button>
  </form>
  <p><button class="btn primary" onclick="window.print()">🖨 Print poster</button></p>
</div>

<?php if ($staffMode): ?>
<div class="poster">
  <img src="assets/logo.png" alt="DAYbill Solution" class="logo">
  <h1><?= h(setting('shop_name', 'Daybill Print')) ?></h1>
  <p class="lead">🔑 Staff login – employees &amp; admin</p>
  <div id="qr"></div>
  <p class="url"><?= h($staffUrl) ?></p>
  <ol>
    <li>Scan the QR code with your phone camera</li>
    <li>Log in with your username and password</li>
    <li>Install the app: <b>Add to Home Screen</b> / <b>Install app</b></li>
  </ol>
</div>
<?php else: ?>
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
<?php endif; ?>

<script src="assets/qrcode.js"></script>
<script>
  var qr = qrcode(0, 'M');
  qr.addData(<?= json_encode($qrUrl) ?>);
  qr.make();
  document.getElementById('qr').innerHTML = qr.createSvgTag({ cellSize: 8, margin: 2, scalable: true });
</script>
<?php page_footer(); ?>
