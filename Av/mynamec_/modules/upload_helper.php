<?php
require_once __DIR__ . '/../includes/extras.php';
// modules/upload_helper.php — Shared photo upload utility
function handlePhotoUpload($field, $subdir) {
    if (!isset($_FILES[$field]) || $_FILES[$field]['error'] !== 0) return null;
    $ext = strtolower(pathinfo($_FILES[$field]['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, ['jpg','jpeg','png','webp','gif'])) return null;
    if ($_FILES[$field]['size'] > 5*1024*1024) return null;
    $dir = __DIR__ . '/../assets/uploads/' . $subdir . '/';
    if (!is_dir($dir)) mkdir($dir, 0755, true);
    $fname = $subdir . '_' . time() . '_' . mt_rand(1000,9999) . '.' . $ext;
    if (move_uploaded_file($_FILES[$field]['tmp_name'], $dir . $fname)) {
        img_optimize($dir . $fname);
        return $subdir . '/' . $fname;
    }
    return null;
}
function photoUrl($path) {
    return $path ? url('assets/uploads/' . $path) : null;
}
?>
