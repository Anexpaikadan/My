<?php
require_once __DIR__ . '/includes/config.php';
require_once __DIR__ . '/includes/whatsapp_otp.php';
requireLogin();
$me = currentUser();
header('Content-Type: text/plain');

$isAdmin = isSportsAdmin($me['role']);

echo "=== Live Test ===\n";
echo "Name: ".$me['name']."\n";
echo "Role: ".$me['role']."\n";
echo "isSportsAdmin(\"".$me['role']."\"): ".($isAdmin ? 'TRUE ✅' : 'FALSE ❌')."\n\n";

// Simulate exactly what prediction.php does
echo "=== Simulating prediction.php ===\n";
ob_start();
// Include just the isAdmin check from prediction.php
$pred = file_get_contents(__DIR__.'/modules/prediction.php');
// Find the isAdmin line
preg_match('/\$isAdmin\s*=\s*([^;]+);/', $pred, $m);
echo "isAdmin expression: ".($m[1]??'not found')."\n";

// Check if admin tab HTML exists
echo "Admin tab in file: ".(strpos($pred,"tab-admin")!==false ? 'YES ✅' : 'NO ❌')."\n";
echo "if(\$isAdmin) count: ".substr_count($pred,'if($isAdmin)')."\n";
echo "if (\$isAdmin) count: ".substr_count($pred,'if ($isAdmin)')."\n";
ob_end_clean();

echo "\nIf isSportsAdmin is TRUE but admin tab not showing,\n";
echo "the prediction.php on server may be CACHED or OLD version.\n";
echo "Try: Hard reload (Ctrl+Shift+R) on prediction page\n";
echo "\nPrediction.php last modified: ".date('Y-m-d H:i:s', filemtime(__DIR__.'/modules/prediction.php'))."\n";
echo "Config.php last modified: ".date('Y-m-d H:i:s', filemtime(__DIR__.'/includes/config.php'))."\n";
