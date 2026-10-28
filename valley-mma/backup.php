<?php
// Backup: download all data (SQL, or ZIP with member photos), keep copies on the server, restore a backup.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/sql_tools.php';
require_admin();

$dir = __DIR__ . '/backups';
if (!is_dir($dir)) {
    mkdir($dir, 0775, true);
}

function backup_name(string $ext): string
{
    return 'valley-mma-backup-' . date('Y-m-d-His') . '.' . $ext;
}

function make_zip(string $sql, string $path): bool
{
    if (!class_exists('ZipArchive')) {
        return false;
    }
    $zip = new ZipArchive();
    if ($zip->open($path, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
        return false;
    }
    $zip->addFromString('database.sql', $sql);
    foreach (glob(cfg('photo_dir') . '/*.jpg') ?: [] as $f) {
        $zip->addFile($f, 'photos/' . basename($f));
    }
    return $zip->close();
}

function send_file(string $path, string $name, string $type): void
{
    header('Content-Type: ' . $type);
    header('Content-Disposition: attachment; filename="' . $name . '"');
    header('Content-Length: ' . filesize($path));
    readfile($path);
}

$action = post('action') ?: get('action');

if ($action === 'download_sql') {
    $sql = dump_sql(db());
    header('Content-Type: application/sql; charset=utf-8');
    header('Content-Disposition: attachment; filename="' . backup_name('sql') . '"');
    echo $sql;
    exit;
}
if ($action === 'download_zip') {
    $tmp = tempnam(sys_get_temp_dir(), 'vmz');
    if (make_zip(dump_sql(db()), $tmp)) {
        send_file($tmp, backup_name('zip'), 'application/zip');
        unlink($tmp);
        exit;
    }
    flash('danger', t('zip_missing'));
    redirect('backup.php');
}
if ($action === 'save') {
    $sql = dump_sql(db());
    if (!make_zip($sql, $dir . '/' . backup_name('zip'))) {
        file_put_contents($dir . '/' . backup_name('sql'), $sql);
    }
    flash('success', t('backup_saved'));
    redirect('backup.php');
}
if ($action === 'get') {
    $f = basename(get('f'));
    if (preg_match('/^valley-mma-backup-[\d-]+\.(sql|zip)$/', $f) && is_file("$dir/$f")) {
        send_file("$dir/$f", $f, str_ends_with($f, '.zip') ? 'application/zip' : 'application/sql');
        exit;
    }
    redirect('backup.php');
}
if ($action === 'delete') {
    $f = basename(post('f'));
    if (preg_match('/^valley-mma-backup-[\d-]+\.(sql|zip)$/', $f) && is_file("$dir/$f")) {
        unlink("$dir/$f");
        flash('success', t('removed'));
    }
    redirect('backup.php');
}
if ($action === 'restore') {
    $file = $_FILES['file'] ?? null;
    if (post('confirm') !== 'RESTORE') {
        flash('danger', t('restore_confirm_wrong'));
        redirect('backup.php');
    }
    if (!$file || $file['error'] !== UPLOAD_ERR_OK) {
        flash('danger', t('restore_no_file'));
        redirect('backup.php');
    }
    $sql = null;
    $photos = [];
    $isZip = str_ends_with(strtolower($file['name']), '.zip');
    if ($isZip && class_exists('ZipArchive')) {
        $zip = new ZipArchive();
        if ($zip->open($file['tmp_name']) === true) {
            $sql = $zip->getFromName('database.sql') ?: null;
            for ($i = 0; $i < $zip->numFiles; $i++) {
                $n = $zip->getNameIndex($i);
                if (preg_match('#^photos/([a-f0-9]{20}\.jpg)$#', $n, $mm)) {
                    $photos[$mm[1]] = $zip->getFromIndex($i);
                }
            }
            $zip->close();
        }
    } elseif (!$isZip) {
        $sql = file_get_contents($file['tmp_name']);
    }
    if (!$sql || !str_contains($sql, 'CREATE TABLE')) {
        flash('danger', t('restore_bad_file'));
        redirect('backup.php');
    }
    // Keep a copy of the current data first.
    $before = dump_sql(db());
    file_put_contents($dir . '/valley-mma-backup-' . date('Y-m-d-His') . '-0.sql', $before);
    try {
        run_sql(db(), $sql);
        foreach ($photos as $name => $data) {
            file_put_contents(cfg('photo_dir') . '/' . $name, $data);
        }
        flash('success', t('restore_done'));
    } catch (Throwable $e) {
        try {
            run_sql(db(), $before);
        } catch (Throwable $e2) {
        }
        flash('danger', t('restore_failed') . ' ' . $e->getMessage());
    }
    redirect('backup.php');
}

$files = glob($dir . '/valley-mma-backup-*.{sql,zip}', GLOB_BRACE) ?: [];
rsort($files);
$counts = [
    t('members') => q('SELECT COUNT(*) FROM members')->fetchColumn(),
    t('payments') => q('SELECT COUNT(*) FROM payments')->fetchColumn(),
    t('attendance') => q('SELECT COUNT(*) FROM attendance')->fetchColumn(),
    t('photo') => count(glob(cfg('photo_dir') . '/*.jpg') ?: []),
];

$title = t('backup');
$active = 'backup';
require __DIR__ . '/includes/header.php';
?>
<div class="row g-3">
  <div class="col-lg-6">
    <div class="card mb-3"><div class="card-body">
      <h2 class="h5"><i class="bi bi-cloud-arrow-down text-primary"></i> <?= e(t('download_backup')) ?></h2>
      <p class="small-muted"><?php foreach ($counts as $k => $v): ?><span class="me-3"><?= e($k) ?>: <b><?= (int)$v ?></b></span><?php endforeach; ?></p>
      <div class="d-grid gap-2">
        <a href="?action=download_zip" class="btn btn-primary btn-lg"><i class="bi bi-file-earmark-zip"></i> <?= e(t('backup_zip')) ?></a>
        <a href="?action=download_sql" class="btn btn-outline-primary"><i class="bi bi-filetype-sql"></i> <?= e(t('backup_sql')) ?></a>
        <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="save"><button class="btn btn-outline-dark w-100"><i class="bi bi-hdd"></i> <?= e(t('backup_on_server')) ?></button></form>
      </div>
      <p class="small-muted mt-3 mb-0"><i class="bi bi-info-circle"></i> <?= e(t('backup_tip')) ?></p>
    </div></div>
    <div class="card mb-3"><div class="card-header"><?= e(t('saved_backups')) ?></div>
      <ul class="list-group list-group-flush">
        <?php if (!$files): ?><li class="list-group-item text-muted"><?= e(t('nothing_here')) ?></li><?php endif; ?>
        <?php foreach (array_slice($files, 0, 30) as $f): $n = basename($f); ?>
          <li class="list-group-item d-flex align-items-center gap-2">
            <i class="bi <?= str_ends_with($n, '.zip') ? 'bi-file-earmark-zip' : 'bi-filetype-sql' ?>"></i>
            <span class="me-auto small text-break"><?= e($n) ?><br><span class="small-muted"><?= round(filesize($f) / 1024) ?> KB</span></span>
            <a href="?action=get&f=<?= e(rawurlencode($n)) ?>" class="btn btn-sm btn-outline-primary"><i class="bi bi-download"></i></a>
            <form method="post" onsubmit="return confirm(<?= e(json_encode(t('confirm_delete'))) ?>)"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="f" value="<?= e($n) ?>">
              <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
          </li>
        <?php endforeach; ?>
      </ul>
    </div>
  </div>
  <div class="col-lg-6">
    <form method="post" enctype="multipart/form-data" class="card border border-danger"><?= csrf_field() ?><input type="hidden" name="action" value="restore">
      <div class="card-body">
        <h2 class="h5 text-danger"><i class="bi bi-arrow-counterclockwise"></i> <?= e(t('restore_backup')) ?></h2>
        <p class="small"><?= e(t('restore_warning')) ?></p>
        <input class="form-control mb-2" type="file" name="file" accept=".sql,.zip" required>
        <label class="form-label small" for="rc"><?= e(t('restore_type')) ?></label>
        <input class="form-control mb-3" id="rc" name="confirm" placeholder="RESTORE" autocomplete="off" required>
        <button class="btn btn-danger w-100"><?= e(t('restore_backup')) ?></button>
      </div>
    </form>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
