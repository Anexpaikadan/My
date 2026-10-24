<?php
// Server-side printing (used when print mode is "local", i.e. XAMPP on the shop PC).

require_once __DIR__ . '/agent/print-core.php';

function printer_for(array $f): string
{
    $printer = setting($f['color'] === 'color' ? 'printer_color' : 'printer_bw', '');
    return $printer !== '' ? $printer : setting('printer_bw', '');
}

/** @return string printer name used */
function print_file(array $f): string
{
    if ($f['stored_name'] === '') {
        throw new RuntimeException('File was already deleted from the server.');
    }
    if (!function_exists('exec')) {
        throw new RuntimeException('This server cannot print directly (exec disabled). Use print mode "agent" or "browser" in Admin.');
    }
    $printer = printer_for($f);
    print_with_options($f, cfg('upload_dir') . '/' . $f['stored_name'], $f['ext'], $printer, [
        'sumatra' => (string)cfg('sumatra_path'),
        'soffice' => (string)cfg('soffice_path'),
        'lp'      => (string)cfg('lp_path'),
    ], (bool)cfg('print_dry_run'));
    return $printer === '' ? 'default printer' : $printer;
}

function list_printers(): array
{
    return function_exists('exec') ? core_list_printers() : [];
}
