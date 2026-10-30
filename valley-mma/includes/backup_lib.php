<?php
// Backup helpers: make, list, prune and restore backups. Used by backup.php and the automatic daily backup.

require_once __DIR__ . '/sql_tools.php';

// Backup files: valley-mma-backup-… (made by hand) and valley-mma-auto-… (made automatically every day).
const BACKUP_PATTERN = '/^valley-mma-(backup|auto)-[\d-]+\.(sql|zip)$/';

function backup_dir(): string
{
    $dir = __DIR__ . '/../backups';
    if (!is_dir($dir)) {
        mkdir($dir, 0775, true);
    }
    return realpath($dir) ?: $dir;
}

function backup_name(string $ext, string $kind = 'backup'): string
{
    return 'valley-mma-' . $kind . '-' . date('Y-m-d-His') . '.' . $ext;
}

// Newest first.
function backup_files(): array
{
    $files = array_filter(scandir(backup_dir()) ?: [], fn($f) => preg_match(BACKUP_PATTERN, $f));
    usort($files, fn($a, $b) => filemtime(backup_dir() . "/$b") <=> filemtime(backup_dir() . "/$a"));
    return array_values($files);
}

function backup_file_ok(string $name): bool
{
    return preg_match(BACKUP_PATTERN, $name) === 1 && is_file(backup_dir() . '/' . $name);
}

// ZIP with database.sql and the member photos.
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
    foreach (array_merge(glob(__DIR__ . '/../media/*.jpg') ?: [], glob(__DIR__ . '/../media/products/*.jpg') ?: []) as $f) {
        $zip->addFile($f, 'media/' . (str_contains($f, '/products/') ? 'products/' : '') . basename($f)); // hero photo, shop photos
    }
    foreach (glob(cfg('photo_dir') . '/*.jpg') ?: [] as $f) {
        $zip->addFile($f, 'photos/' . basename($f));
    }
    return $zip->close();
}

// Saves a full backup in the backups folder (ZIP, or SQL when ZIP is not available). Returns the file name.
function save_backup(string $kind = 'backup'): string
{
    $sql = dump_sql(db());
    $name = backup_name('zip', $kind);
    if (!make_zip($sql, backup_dir() . '/' . $name)) {
        $name = backup_name('sql', $kind);
        file_put_contents(backup_dir() . '/' . $name, $sql);
    }
    return $name;
}

// Keeps only the newest $keep automatic backups.
function prune_auto_backups(int $keep): void
{
    $auto = array_values(array_filter(backup_files(), fn($f) => str_starts_with($f, 'valley-mma-auto-')));
    foreach (array_slice($auto, max(1, $keep)) as $f) {
        @unlink(backup_dir() . '/' . $f);
    }
}

// Once a day, the first time an admin opens a page: save a backup on the server.
function auto_backup_if_due(): void
{
    if (setting('auto_backup', '1') !== '1' || setting('last_auto_backup') === today()) {
        return;
    }
    set_setting('last_auto_backup', today()); // first, so two pages opened together make one backup
    try {
        save_backup('auto');
        prune_auto_backups((int)setting('backup_keep', '14'));
    } catch (Throwable $e) {
        error_log('Valley MMA auto backup failed: ' . $e->getMessage());
    }
}

// Reads a backup (.sql or .zip) and returns [sql, photos[name => data]] or null when it is not a backup.
function read_backup(string $path, string $name): ?array
{
    $photos = [];
    $sql = null;
    if (str_ends_with(strtolower($name), '.zip')) {
        if (!class_exists('ZipArchive')) {
            return null;
        }
        $zip = new ZipArchive();
        if ($zip->open($path) !== true) {
            return null;
        }
        $sql = $zip->getFromName('database.sql') ?: null;
        for ($i = 0; $i < $zip->numFiles; $i++) {
            if (preg_match('#^photos/([a-f0-9]{20}\.jpg)$#', (string)$zip->getNameIndex($i), $mm)) {
                $photos[$mm[1]] = $zip->getFromIndex($i);
            } elseif (preg_match('#^media/(?:products/)?[a-f0-9]{20}\.jpg$#', (string)$zip->getNameIndex($i))) {
                $photos[(string)$zip->getNameIndex($i)] = $zip->getFromIndex($i);
            }
        }
        $zip->close();
    } else {
        $sql = file_get_contents($path) ?: null;
    }
    if (!$sql || !str_contains($sql, 'CREATE TABLE') || !str_contains($sql, '`members`')) {
        return null;
    }
    return [$sql, $photos];
}

// Replaces all data with the backup. A copy of the current data is saved first and put back if it fails.
// Backups from older app versions are upgraded automatically on the next page load.
function restore_backup(string $sql, array $photos): void
{
    $before = save_backup('backup');
    $beforeSql = dump_sql(db());
    // Backup settings and dates stay as they are now (not the ones inside the old backup).
    $keep = q("SELECT k, v FROM settings WHERE k IN ('auto_backup', 'backup_keep', 'last_auto_backup', 'last_download')")->fetchAll(PDO::FETCH_KEY_PAIR);
    try {
        run_sql(db(), $sql);
        foreach ($photos as $name => $data) {
            if (str_starts_with($name, 'media/')) {
                @mkdir(dirname(__DIR__ . '/../' . $name), 0775, true);
                file_put_contents(__DIR__ . '/../' . $name, $data);
            } else {
                file_put_contents(cfg('photo_dir') . '/' . $name, $data);
            }
        }
    } catch (Throwable $e) {
        try {
            run_sql(db(), $beforeSql);
        } catch (Throwable $e2) {
        }
        throw new RuntimeException($e->getMessage() . ' (' . $before . ')');
    }
    foreach ($keep as $k => $v) {
        set_setting($k, (string)$v);
    }
    unset($GLOBALS['vm_settings']);
}

function send_download(string $path, string $name): void
{
    header('Content-Type: ' . (str_ends_with($name, '.zip') ? 'application/zip' : 'application/sql; charset=utf-8'));
    header('Content-Disposition: attachment; filename="' . $name . '"');
    header('Content-Length: ' . filesize($path));
    header('Cache-Control: no-store');
    readfile($path);
}
