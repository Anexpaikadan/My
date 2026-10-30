<?php
// One-time installer: creates the database tables, optional sample data and the first admin.
// Delete this file after installing.

declare(strict_types=1);

require __DIR__ . '/includes/sql_tools.php';
$c = require __DIR__ . '/config.php';
date_default_timezone_set($c['timezone'] ?? 'Asia/Kolkata');

function pdo_for(array $c, bool $withDb): PDO
{
    $dsn = sprintf('mysql:host=%s;port=%d;charset=utf8mb4', $c['db_host'], $c['db_port']) . ($withDb ? ';dbname=' . $c['db_name'] : '');
    return new PDO($dsn, $c['db_user'], $c['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
}

$msg = '';
$ok = false;
try {
    $installed = (int)pdo_for($c, true)->query('SELECT COUNT(*) FROM admins')->fetchColumn() > 0;
} catch (Throwable $e) {
    $installed = false;
}

if ($installed) {
    $msg = 'Already installed. Delete install.php from the server and open login.php.';
    $ok = true;
} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $user = trim((string)($_POST['username'] ?? ''));
    $pass = (string)($_POST['password'] ?? '');
    if (!preg_match('/^[A-Za-z0-9_.-]{3,50}$/', $user)) {
        $msg = 'Username: 3–50 letters, numbers, dot, dash or underscore.';
    } elseif (strlen($pass) < 6) {
        $msg = 'Password: at least 6 characters.';
    } elseif (!preg_match('/^[A-Za-z0-9_$-]{1,64}$/', $c['db_name'])) {
        $msg = 'Invalid db_name in config.php.';
    } else {
        try {
            try {
                $pdo = pdo_for($c, true);
            } catch (PDOException $e) { // XAMPP: create the database
                pdo_for($c, false)->exec('CREATE DATABASE IF NOT EXISTS `' . $c['db_name'] . '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
                $pdo = pdo_for($c, true);
            }
            $pdo->exec("SET time_zone = '" . (new DateTime())->format('P') . "'");
            run_sql($pdo, file_get_contents(__DIR__ . '/sql/schema.sql'));
            run_sql($pdo, file_get_contents(__DIR__ . '/sql/accounts.sql'));
            run_sql($pdo, file_get_contents(__DIR__ . '/sql/leaves.sql'));
            run_sql($pdo, file_get_contents(__DIR__ . '/sql/levels.sql'));
            run_sql($pdo, file_get_contents(__DIR__ . '/sql/shop.sql'));
            if (!empty($_POST['sample']) && !(int)$pdo->query('SELECT COUNT(*) FROM members')->fetchColumn()) {
                run_sql($pdo, file_get_contents(__DIR__ . '/sql/sample_data.sql'));
            }
            $pdo->prepare('INSERT INTO admins (username, full_name, password_hash) VALUES (?, ?, ?)')
                ->execute([$user, 'Admin', password_hash($pass, PASSWORD_DEFAULT)]);
            $pdo->prepare("INSERT INTO settings (k, v) VALUES ('app_secret', ?) ON DUPLICATE KEY UPDATE v = v")->execute([bin2hex(random_bytes(32))]);
            $ok = true;
            $msg = 'Installed! Delete install.php from the server, then log in.';
        } catch (Throwable $e) {
            $msg = 'Error: ' . $e->getMessage();
        }
    }
}
$h = fn($s) => htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Install · Valley MMA</title>
<link rel="stylesheet" href="assets/vendor/bootstrap.min.css">
<link rel="stylesheet" href="assets/style.css">
</head>
<body class="bare">
<main class="main-bare pt-4">
  <div class="brand-logo mb-3"><img src="assets/logo.png" alt="VALLEY MMA" width="612" height="106"><span class="l2">FIGHT CLUB</span><span class="l3">PANDIKKAD</span></div>
  <div class="card"><div class="card-body p-4">
    <h1 class="h5">Install</h1>
    <?php if ($msg): ?><div class="alert <?= $ok ? 'alert-success' : 'alert-danger' ?>"><?= $h($msg) ?></div><?php endif; ?>
    <?php if ($ok): ?>
      <a href="login.php" class="btn btn-primary btn-lg w-100">Open login</a>
    <?php else: ?>
      <p class="small text-muted">Database: <b><?= $h($c['db_name']) ?></b> on <?= $h($c['db_host']) ?> (edit config.php to change).</p>
      <form method="post">
        <div class="mb-3"><label class="form-label">Admin username</label><input class="form-control" name="username" required value="<?= $h($_POST['username'] ?? 'admin') ?>"></div>
        <div class="mb-3"><label class="form-label">Admin password</label><input class="form-control" type="password" name="password" minlength="6" required></div>
        <div class="form-check mb-3"><input class="form-check-input" type="checkbox" name="sample" value="1" id="s" checked><label class="form-check-label" for="s">Add sample members, payments and attendance for testing</label></div>
        <button class="btn btn-primary btn-lg w-100">Install</button>
      </form>
    <?php endif; ?>
  </div></div>
</main>
</body>
</html>
