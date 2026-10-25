<?php
// Printer selection, and server-side printing (print mode "local", i.e. XAMPP on the shop PC).

require_once __DIR__ . '/agent/print-core.php';

// Admin's printer per paper size and colour: {"A4": {"bw": "HP 1020", "color": "Epson L3150"}, ...}
function printer_map(): array
{
    $m = json_decode(setting('printer_map', '{}'), true);
    return is_array($m) ? $m : [];
}

// Printer chosen by the admin for these options ('' = Windows default printer).
function auto_printer(array $f): string
{
    if (($f['kind'] ?? '') === 'photo' && setting('photo_printer', '') !== '') {
        return setting('photo_printer');
    }
    $mapped = (string)(printer_map()[$f['paper']][$f['color']] ?? '');
    if ($mapped !== '') {
        return $mapped;
    }
    $printer = setting($f['color'] === 'color' ? 'printer_color' : 'printer_bw', '');
    return $printer !== '' ? $printer : setting('printer_bw', '');
}

// Printer to use: the one staff picked for this file, else the admin's choice.
function printer_for(array $f): string
{
    return ($f['printer'] ?? '') !== '' ? (string)$f['printer'] : auto_printer($f);
}

// Every printer name the shop uses, for the staff printer menu.
function known_printers(): array
{
    $names = csv_setting('printers_detected', '');
    $names[] = setting('printer_bw');
    $names[] = setting('printer_color');
    foreach (printer_map() as $byColor) {
        foreach ((array)$byColor as $name) {
            $names[] = (string)$name;
        }
    }
    $names = array_values(array_unique(array_filter(array_map('trim', $names), 'strlen')));
    sort($names, SORT_NATURAL | SORT_FLAG_CASE);
    return $names;
}

function sumatra_path(): string
{
    return find_sumatra(setting('sumatra_path', '') ?: (string)cfg('sumatra_path'), __DIR__);
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
    $f['scale'] = print_scale($f);
    print_with_options($f, cfg('upload_dir') . '/' . $f['stored_name'], $f['ext'], $printer, [
        'sumatra' => sumatra_path(),
        'soffice' => (string)cfg('soffice_path'),
        'lp'      => (string)cfg('lp_path'),
    ], (bool)cfg('print_dry_run'));
    return $printer === '' ? 'default printer' : $printer;
}

// Printers installed on this computer; remembered for the staff printer menu.
function list_printers(): array
{
    $found = function_exists('exec') ? core_list_printers() : [];
    if ($found) {
        save_setting('printers_detected', implode(',', str_replace(',', ' ', $found)));
    }
    return $found;
}
