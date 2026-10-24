<?php
// Sends a file to the shop printer using the PC that runs XAMPP.
// Windows: SumatraPDF command line. Linux/macOS: CUPS "lp".
// Office files are converted to PDF with LibreOffice first (if configured).

function is_windows(): bool
{
    return stripos(PHP_OS_FAMILY, 'Windows') === 0;
}

function run_cmd(string $cmd): array
{
    if (cfg('print_dry_run')) {
        error_log('Daybill dry-run: ' . $cmd);
        return [0, 'dry run'];
    }
    $out = [];
    $code = 0;
    exec($cmd . ' 2>&1', $out, $code);
    return [$code, trim(implode("\n", $out))];
}

// Returns the path of a printable file (PDF/image), converting office docs if needed.
function printable_path(array $f): string
{
    $src = cfg('upload_dir') . '/' . $f['stored_name'];
    if (in_array($f['ext'], ['pdf', 'jpg', 'jpeg', 'png'], true)) {
        return $src;
    }
    $pdf = $src . '.pdf';
    if (is_file($pdf)) {
        return $pdf;
    }
    $soffice = (string)cfg('soffice_path');
    if ($soffice === '' || !is_file($soffice)) {
        throw new RuntimeException('LibreOffice is not installed – open the file and print it from the browser/Office instead.');
    }
    $tmpDir = cfg('upload_dir') . '/conv_' . bin2hex(random_bytes(4));
    mkdir($tmpDir);
    [$code, $out] = run_cmd(escapeshellarg($soffice) . ' --headless --convert-to pdf --outdir '
        . escapeshellarg($tmpDir) . ' ' . escapeshellarg($src));
    $made = glob($tmpDir . '/*.pdf');
    if ($made) {
        rename($made[0], $pdf);
    }
    @array_map('unlink', glob($tmpDir . '/*') ?: []);
    @rmdir($tmpDir);
    if (!is_file($pdf)) {
        throw new RuntimeException('Could not convert to PDF: ' . $out);
    }
    return $pdf;
}

/** @return string printer name used */
function print_file(array $f): string
{
    if ($f['stored_name'] === '') {
        throw new RuntimeException('File was already deleted from the server.');
    }
    $path = printable_path($f);
    $printer = setting($f['color'] === 'color' ? 'printer_color' : 'printer_bw', '');
    if ($printer === '') {
        $printer = setting('printer_bw', '');
    }

    if (is_windows()) {
        $path = str_replace('/', '\\', $path);
        $exe = (string)cfg('sumatra_path');
        if (!is_file($exe)) {
            throw new RuntimeException('SumatraPDF not found at ' . $exe . ' (see config.php).');
        }
        $settings = [$f['copies'] . 'x', 'paper=' . $f['paper'], $f['orientation'],
            $f['color'] === 'color' ? 'color' : 'monochrome',
            $f['sides'] === 'double' ? 'duplexlong' : 'simplex', 'fit'];
        if ($f['page_range'] !== '') {
            $settings[] = $f['page_range'];
        }
        $cmd = escapeshellarg($exe)
            . ($printer === '' ? ' -print-to-default' : ' -print-to ' . escapeshellarg($printer))
            . ' -print-settings ' . escapeshellarg(implode(',', $settings))
            . ' -silent -exit-when-done ' . escapeshellarg($path);
    } else {
        $cmd = escapeshellarg((string)cfg('lp_path'))
            . ($printer === '' ? '' : ' -d ' . escapeshellarg($printer))
            . ' -n ' . (int)$f['copies']
            . ' -o media=' . escapeshellarg($f['paper'])
            . ' -o sides=' . ($f['sides'] === 'double' ? 'two-sided-long-edge' : 'one-sided')
            . ($f['orientation'] === 'landscape' ? ' -o landscape' : '')
            . ($f['color'] === 'color' ? '' : ' -o ColorModel=Gray -o print-color-mode=monochrome')
            . ' -o fit-to-page'
            . ($f['page_range'] !== '' ? ' -o page-ranges=' . escapeshellarg($f['page_range']) : '')
            . ' ' . escapeshellarg($path);
    }

    [$code, $out] = run_cmd($cmd);
    if ($code !== 0) {
        throw new RuntimeException('Printer error (' . $code . '): ' . mb_substr($out, 0, 300));
    }
    return $printer === '' ? 'default printer' : $printer;
}

// List installed printers (for the admin settings page).
function list_printers(): array
{
    if (is_windows()) {
        exec('powershell -NoProfile -Command "Get-Printer | Select-Object -ExpandProperty Name" 2>NUL', $out);
    } else {
        exec('lpstat -e 2>/dev/null', $out);
    }
    return array_values(array_filter(array_map('trim', $out ?? [])));
}
