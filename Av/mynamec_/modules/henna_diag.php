<?php
$configFile = __DIR__ . '/../includes/config.php';
if (!file_exists($configFile)) { die("Config missing"); }
require_once $configFile;
if (!function_exists('db')) { die("db() missing"); }

header('Content-Type: text/plain');

echo "=== INDEXES ON henna_votes ===\n";
foreach (db()->query("SHOW INDEX FROM henna_votes")->fetchAll(PDO::FETCH_ASSOC) as $r) {
    echo "Key: {$r['Key_name']} | Col: {$r['Column_name']} | Unique: {$r['Non_unique']}\n";
}

echo "\n=== ALL VOTES ===\n";
foreach (db()->query("SELECT * FROM henna_votes ORDER BY id DESC LIMIT 20")->fetchAll(PDO::FETCH_ASSOC) as $r) {
    echo "id={$r['id']} fest={$r['fest_id']} voter={$r['voter_id']} entry={$r['entry_id']}\n";
}

echo "\n=== CURRENT USER ID ===\n";
if (!function_exists('currentUser')) { echo "currentUser() not defined\n"; }
else { $u=currentUser(); echo "id={$u['id']} name={$u['name']}\n"; }

echo "\n=== ENTRIES ===\n";
foreach (db()->query("SELECT id,member_id,vote_count FROM henna_entries ORDER BY id")->fetchAll(PDO::FETCH_ASSOC) as $r) {
    echo "entry_id={$r['id']} member={$r['member_id']} votes={$r['vote_count']}\n";
}
