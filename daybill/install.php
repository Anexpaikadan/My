<?php
// One-time installer: creates the database, tables and the first admin account.
// Delete or rename this file after installation.

declare(strict_types=1);

$CONFIG = require __DIR__ . '/config.php';
$msg = '';
$done = false;

function installer_pdo(array $c, bool $withDb): PDO
{
    $dsn = sprintf('mysql:host=%s;port=%d;charset=utf8mb4', $c['db_host'], $c['db_port']);
    if ($withDb) {
        $dsn .= ';dbname=' . $c['db_name'];
    }
    return new PDO($dsn, $c['db_user'], $c['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
}

// Refuse to run again once an admin exists.
try {
    $pdo = installer_pdo($CONFIG, true);
    $hasAdmin = (int)$pdo->query("SELECT COUNT(*) FROM users WHERE role = 'admin'")->fetchColumn() > 0;
} catch (Throwable $e) {
    $hasAdmin = false;
}

if ($hasAdmin) {
    $msg = 'Already installed. Delete install.php from the server.';
    $done = true;
} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $user = trim((string)($_POST['username'] ?? ''));
    $pass = (string)($_POST['password'] ?? '');
    if (!preg_match('/^[A-Za-z0-9_.-]{3,50}$/', $user)) {
        $msg = 'Username: 3–50 letters, numbers, dot, dash or underscore.';
    } elseif (strlen($pass) < 6) {
        $msg = 'Password must be at least 6 characters.';
    } else {
        try {
            if (!preg_match('/^[A-Za-z0-9_]+$/', $CONFIG['db_name'])) {
                throw new RuntimeException('Invalid db_name in config.php');
            }
            try {
                installer_pdo($CONFIG, false)->exec('CREATE DATABASE IF NOT EXISTS `' . $CONFIG['db_name']
                    . '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
            } catch (PDOException $e) {
                // Shared hosting (e.g. Hostinger): the database is created in the control panel instead.
            }
            $pdo = installer_pdo($CONFIG, true);
            $sql = preg_replace('/^--.*$/m', '', file_get_contents(__DIR__ . '/schema.sql'));
            foreach (array_filter(array_map('trim', explode(';', $sql))) as $stmt) {
                $pdo->exec($stmt);
            }
            $st = $pdo->prepare("INSERT INTO users (username, full_name, password_hash, role) VALUES (?, 'Administrator', ?, 'admin')");
            $st->execute([$user, password_hash($pass, PASSWORD_DEFAULT)]);
            if (!is_dir($CONFIG['upload_dir'])) {
                mkdir($CONFIG['upload_dir'], 0770, true);
            }
            $msg = 'Installed! Now delete install.php and log in.';
            $done = true;
        } catch (Throwable $e) {
            $msg = 'Error: ' . $e->getMessage();
        }
    }
}
?>
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Install – Daybill Print</title><link rel="stylesheet" href="assets/style.css"></head>
<body><main class="wrap narrow">
<div class="card">
  <h1>Daybill Print – Setup</h1>
  <?php if ($msg): ?><div class="alert <?= $done ? 'ok' : 'err' ?>"><?= htmlspecialchars($msg) ?></div><?php endif; ?>
  <?php if ($done): ?>
    <a class="btn primary block" href="login.php">Go to login</a>
  <?php else: ?>
    <p class="muted">Tables will be created in database <b><?= htmlspecialchars($CONFIG['db_name']) ?></b> on <?= htmlspecialchars($CONFIG['db_host']) ?>. Edit <code>config.php</code> first if needed. On cloud hosting, create the database in your hosting panel first.</p>
    <form method="post">
      <label>Admin username<input name="username" required value="admin"></label>
      <label>Admin password<input name="password" type="password" required minlength="6"></label>
      <button class="btn primary block">Install</button>
    </form>
  <?php endif; ?>
</div>
</main></body></html>
