<?php
require_once __DIR__ . '/../includes/config.php';
$me = currentUser();
if (!$me || !isSuperAdmin($me)) { exit('Developer only.'); }
header('Content-Type: text/plain; charset=utf-8');

echo "=== MODULE ADMIN DIAGNOSTIC ===\n\n";

echo "1) module_admins columns:\n";
try {
  foreach (db()->query("SHOW COLUMNS FROM module_admins")->fetchAll() as $c) {
    echo "   - {$c['Field']} ({$c['Type']})\n";
  }
} catch (Exception $e) { echo "   ERROR: ".$e->getMessage()."\n"; }

echo "\n2) Saved assignments (raw):\n";
try {
  $rows = db()->query("SELECT * FROM module_admins")->fetchAll();
  if (!$rows) echo "   (none saved)\n";
  foreach ($rows as $r) {
    echo "   user_id={$r['user_id']} | module='{$r['module']}' | expires_at=".($r['expires_at']??'NULL')."\n";
  }
} catch (Exception $e) { echo "   ERROR: ".$e->getMessage()."\n"; }

echo "\n3) Permission check per assignment:\n";
try {
  $rows = db()->query("SELECT DISTINCT user_id,module FROM module_admins")->fetchAll();
  foreach ($rows as $r) {
    $u = db()->prepare("SELECT * FROM users WHERE id=?"); $u->execute([$r['user_id']]); $u=$u->fetch();
    if (!$u) { echo "   user_id={$r['user_id']} NOT FOUND\n"; continue; }
    $res = isModuleAdmin($r['module'], $u) ? 'YES' : 'NO';
    echo "   {$u['name']} (role={$u['role']}) -> '{$r['module']}' -> isModuleAdmin=$res\n";
  }
} catch (Exception $e) { echo "   ERROR: ".$e->getMessage()."\n"; }

echo "\n=== END ===\n";
