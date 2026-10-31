<?php
require_once __DIR__.'/includes/config.php';
requireLogin();
$me = currentUser();
if(!isAdminRole($me['role'])) die('Admin only');

// Dummy phone numbers to delete (not real members)
$dummyPhones = [
    '+919876543211', '+919876543212', '+919876543213',
    '+919876543214', '+919876543215', '+919876543216',
    '+919876543217', '+919876543218', '+919876543219',
    '+919876543220',
];

$deleted = [];
foreach($dummyPhones as $ph) {
    $s = db()->prepare("SELECT id,name FROM users WHERE whatsapp_number=?");
    $s->execute([$ph]); $u = $s->fetch();
    if ($u && $u['id'] != $me['id']) {
        db()->prepare("DELETE FROM users WHERE id=?")->execute([$u['id']]);
        $deleted[] = $u['name'].' ('.$ph.')';
    }
}

echo '<pre style="background:#111;color:#0f0;padding:1rem;font:13px monospace">';
echo "Deleted ".count($deleted)." dummy users:\n";
foreach($deleted as $d) echo "  🗑 $d\n";
if(empty($deleted)) echo "None found (may already be deleted or different numbers)\n";
echo "\n<a href='".url('admin.php')."' style='color:#4fc3f7'>← Back to Admin</a>";
echo '</pre>';
