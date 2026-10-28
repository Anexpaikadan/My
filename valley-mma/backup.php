<?php
// Backup: download all data (ZIP with photos, or SQL), automatic daily backups on the server,
// restore from a saved backup or an uploaded file. Downloads, restore and delete ask for the admin password.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/backup_lib.php';
require_admin();

$dir = backup_dir();
$action = post('action');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if ($action === 'auto') {
        set_setting('auto_backup', post('auto_backup') === '1' ? '1' : '0');
        set_setting('backup_keep', (string)max(1, min(90, (int)post('backup_keep'))));
        flash('success', t('saved'));
        redirect('backup.php');
    }
    if ($action === 'save') {
        $name = save_backup();
        flash('success', t('backup_saved') . ' ' . $name);
        redirect('backup.php');
    }
    // Everything below gives out or replaces all data: password needed.
    require_verify('backup.php');

    if ($action === 'download') {
        $zip = post('type') !== 'sql';
        $tmp = tempnam(sys_get_temp_dir(), 'vmb');
        $sql = dump_sql(db());
        if ($zip && !make_zip($sql, $tmp)) {
            @unlink($tmp);
            flash('danger', t('zip_missing'));
            redirect('backup.php');
        }
        if (!$zip) {
            file_put_contents($tmp, $sql);
        }
        set_setting('last_download', date('Y-m-d H:i'));
        send_download($tmp, backup_name($zip ? 'zip' : 'sql'));
        unlink($tmp);
        exit;
    }
    if ($action === 'get') {
        $f = basename(post('f'));
        if (backup_file_ok($f)) {
            set_setting('last_download', date('Y-m-d H:i'));
            send_download("$dir/$f", $f);
            exit;
        }
        redirect('backup.php');
    }
    if ($action === 'delete') {
        $f = basename(post('f'));
        if (backup_file_ok($f)) {
            unlink("$dir/$f");
            flash('success', t('removed'));
        }
        redirect('backup.php');
    }
    if ($action === 'restore_saved' || $action === 'restore') {
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
            $data = read_backup($file['tmp_name'], (string)$file['name']);
        } else {
            $f = basename(post('f'));
            $data = backup_file_ok($f) ? read_backup("$dir/$f", $f) : null;
        }
        if (!$data) {
            flash('danger', t('restore_bad_file'));
            redirect('backup.php');
        }
        try {
            restore_backup($data[0], $data[1]);
            flash('success', t('restore_done'));
        } catch (Throwable $e) {
            flash('danger', t('restore_failed') . ' ' . $e->getMessage());
        }
        redirect('backup.php');
    }
    redirect('backup.php');
}

$files = backup_files();
$counts = [
    t('members') => q('SELECT COUNT(*) FROM members')->fetchColumn(),
    t('payments') => q('SELECT COUNT(*) FROM payments')->fetchColumn(),
    t('ledger') => q('SELECT COUNT(*) FROM acc_entries')->fetchColumn(),
    t('attendance') => q('SELECT COUNT(*) FROM attendance')->fetchColumn(),
    t('photo') => count(glob(cfg('photo_dir') . '/*.jpg') ?: []),
];
$lastDl = setting('last_download');
$dlDays = $lastDl !== '' ? (int)floor((time() - strtotime($lastDl)) / 86400) : null;
$size = array_sum(array_map(fn($f) => filesize("$dir/$f"), $files));

$title = t('backup');
$active = 'backup';
$back = 'more.php';
require __DIR__ . '/includes/header.php';
$verifyDl = e(t('verify_download'));
?>
<div class="row g-3">
  <div class="col-lg-6">
    <div class="card mb-3 <?= $dlDays === null || $dlDays >= 7 ? 'border border-warning' : '' ?>"><div class="card-body">
      <h2 class="h5"><i class="bi bi-cloud-arrow-down text-primary"></i> <?= e(t('download_backup')) ?></h2>
      <p class="small-muted mb-2"><?php foreach ($counts as $k => $v): ?><span class="me-3"><?= e($k) ?>: <b><?= (int)$v ?></b></span><?php endforeach; ?></p>
      <p class="small mb-3 <?= $dlDays === null || $dlDays >= 7 ? 'text-danger fw-semibold' : 'text-success' ?>"><i class="bi bi-clock-history"></i>
        <?= e($dlDays === null ? t('never_downloaded') : t('last_downloaded', fdate($lastDl), $dlDays)) ?></p>
      <div class="d-grid gap-2">
        <form method="post" data-verify="<?= $verifyDl ?>"><?= csrf_field() ?><input type="hidden" name="action" value="download"><input type="hidden" name="type" value="zip">
          <button class="btn btn-primary btn-lg w-100"><i class="bi bi-file-earmark-zip"></i> <?= e(t('backup_zip')) ?></button></form>
        <form method="post" data-verify="<?= $verifyDl ?>"><?= csrf_field() ?><input type="hidden" name="action" value="download"><input type="hidden" name="type" value="sql">
          <button class="btn btn-outline-primary w-100"><i class="bi bi-filetype-sql"></i> <?= e(t('backup_sql')) ?></button></form>
        <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="save"><button class="btn btn-outline-dark w-100"><i class="bi bi-hdd"></i> <?= e(t('backup_on_server')) ?></button></form>
      </div>
      <p class="small-muted mt-3 mb-0"><i class="bi bi-info-circle"></i> <?= e(t('backup_tip')) ?></p>
    </div></div>

    <form method="post" class="card mb-3" id="auto"><?= csrf_field() ?><input type="hidden" name="action" value="auto">
      <div class="card-body">
        <h2 class="h6"><i class="bi bi-arrow-repeat text-success"></i> <?= e(t('auto_backup')) ?></h2>
        <div class="form-check form-switch mb-2">
          <input class="form-check-input" type="checkbox" role="switch" name="auto_backup" value="1" id="ab"<?= setting('auto_backup', '1') === '1' ? ' checked' : '' ?>>
          <label class="form-check-label" for="ab"><?= e(t('auto_backup_label')) ?></label></div>
        <div class="d-flex align-items-center gap-2 mb-2"><label class="small" for="bk"><?= e(t('backup_keep_label')) ?></label>
          <input class="form-control form-control-sm" style="width:5rem" type="number" min="1" max="90" name="backup_keep" id="bk" value="<?= e(setting('backup_keep', '14')) ?>"></div>
        <p class="small-muted mb-2"><?= e(setting('last_auto_backup') !== '' ? t('last_auto_backup', fdate(setting('last_auto_backup'))) : t('auto_backup_none')) ?></p>
        <button class="btn btn-sm btn-primary"><?= e(t('save')) ?></button>
      </div>
    </form>
  </div>

  <div class="col-lg-6">
    <div class="card mb-3"><div class="card-header d-flex"><span class="me-auto"><?= e(t('saved_backups')) ?> (<?= count($files) ?>)</span><span class="small-muted"><?= round($size / 1048576, 1) ?> MB</span></div>
      <ul class="list-group list-group-flush" style="max-height:420px;overflow:auto">
        <?php if (!$files): ?><li class="list-group-item text-muted"><?= e(t('nothing_here')) ?></li><?php endif; ?>
        <?php foreach ($files as $n): $auto = str_starts_with($n, 'valley-mma-auto-'); $when = date('d-m-Y H:i', filemtime("$dir/$n")); ?>
          <li class="list-group-item d-flex flex-wrap align-items-center gap-2">
            <i class="bi <?= str_ends_with($n, '.zip') ? 'bi-file-earmark-zip' : 'bi-filetype-sql' ?> fs-5"></i>
            <span class="me-auto small text-nowrap"><b><?= e($when) ?></b>
              <span class="badge <?= $auto ? 'text-bg-success' : 'text-bg-light border' ?>"><?= e($auto ? t('auto') : t('manual')) ?></span><br>
              <span class="small-muted"><?= round(filesize("$dir/$n") / 1024) ?> KB</span></span>
            <div class="d-flex gap-1 flex-nowrap">
            <form method="post" data-verify="<?= $verifyDl ?>"><?= csrf_field() ?><input type="hidden" name="action" value="get"><input type="hidden" name="f" value="<?= e($n) ?>">
              <button class="btn btn-sm btn-outline-primary" title="<?= e(t('download_backup')) ?>" aria-label="<?= e(t('download_backup')) ?>"><i class="bi bi-download"></i></button></form>
            <form method="post" data-verify="<?= e(t('restore_saved_confirm', $when)) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="restore_saved"><input type="hidden" name="f" value="<?= e($n) ?>">
              <button class="btn btn-sm btn-outline-warning" title="<?= e(t('restore_backup')) ?>" aria-label="<?= e(t('restore_backup')) ?>"><i class="bi bi-arrow-counterclockwise"></i></button></form>
            <form method="post" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="f" value="<?= e($n) ?>">
              <button class="btn btn-sm btn-outline-danger" title="<?= e(t('delete')) ?>" aria-label="<?= e(t('delete')) ?>"><i class="bi bi-trash"></i></button></form>
            </div>
          </li>
        <?php endforeach; ?>
      </ul>
    </div>

    <form method="post" enctype="multipart/form-data" class="card border border-danger" data-verify="<?= e(t('restore_warning')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="restore">
      <div class="card-body">
        <h2 class="h5 text-danger"><i class="bi bi-upload"></i> <?= e(t('restore_from_file')) ?></h2>
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
