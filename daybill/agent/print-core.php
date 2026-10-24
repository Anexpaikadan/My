<?php
// Printer command building, shared by the server (local printing) and the
// shop-PC print agent (cloud hosting). Has no dependency on the rest of the app.

// Paper names SumatraPDF understands for "paper=".
const SUMATRA_PAPERS = ['A2', 'A3', 'A4', 'A5', 'A6', 'Letter', 'Legal', 'Tabloid', 'Statement'];

function core_is_windows(): bool
{
    return stripos(PHP_OS_FAMILY, 'Windows') === 0;
}

// Looks for SumatraPDF.exe: the configured path, a "tools" folder next to the app,
// then the usual install folders. Returns '' when it is not installed.
function find_sumatra(string $configured, string $appDir): string
{
    $candidates = [$configured, $appDir . '/tools/SumatraPDF.exe'];
    foreach (glob($appDir . '/tools/SumatraPDF*.exe') ?: [] as $f) {
        $candidates[] = $f; // portable download, e.g. SumatraPDF-3.5.2-64.exe
    }
    foreach (['ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432', 'LOCALAPPDATA'] as $env) {
        if (getenv($env)) {
            $candidates[] = getenv($env) . '\\SumatraPDF\\SumatraPDF.exe';
        }
    }
    $candidates[] = 'C:\\Program Files\\SumatraPDF\\SumatraPDF.exe';
    $candidates[] = 'C:\\Program Files (x86)\\SumatraPDF\\SumatraPDF.exe';
    foreach (glob('C:/Users/*/AppData/Local/SumatraPDF/SumatraPDF.exe') ?: [] as $f) {
        $candidates[] = $f; // per-user install (default for the Sumatra installer)
    }
    foreach ($candidates as $c) {
        if ($c !== '' && is_file($c)) {
            return $c;
        }
    }
    return '';
}

/**
 * @param array  $f       copies, paper, color, sides, orientation, page_range
 * @param string $path    file to print (PDF or image)
 * @param string $printer printer name, '' = system default
 * @param array  $tools   ['sumatra' => path, 'lp' => path]
 */
function build_print_command(array $f, string $path, string $printer, array $tools): string
{
    if (core_is_windows()) {
        $exe = (string)($tools['sumatra'] ?? '');
        if ($exe === '' || !is_file($exe)) {
            throw new RuntimeException('SumatraPDF is not installed. Download it from sumatrapdfreader.org and install it, '
                . 'or put SumatraPDF.exe in the "tools" folder of the app (see Admin → Printing).');
        }
        $settings = [(int)$f['copies'] . 'x', $f['orientation'],
            $f['color'] === 'color' ? 'color' : 'monochrome',
            $f['sides'] === 'double' ? 'duplexlong' : 'simplex', 'fit'];
        if (in_array($f['paper'], SUMATRA_PAPERS, true)) {
            $settings[] = 'paper=' . $f['paper'];
        }
        if ($f['page_range'] !== '') {
            $settings[] = $f['page_range'];
        }
        return escapeshellarg($exe)
            . ($printer === '' ? ' -print-to-default' : ' -print-to ' . escapeshellarg($printer))
            . ' -print-settings ' . escapeshellarg(implode(',', $settings))
            . ' -silent -exit-when-done ' . escapeshellarg(str_replace('/', '\\', $path));
    }
    return escapeshellarg((string)($tools['lp'] ?? 'lp'))
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

// Runs a command; a printer program that hangs (e.g. a stuck dialog) is stopped after $timeout seconds.
function core_run(string $cmd, bool $dryRun, int $timeout = 120): array
{
    if ($dryRun) {
        error_log('Daybill dry-run: ' . $cmd);
        return [0, 'dry run'];
    }
    $proc = proc_open($cmd, [1 => ['pipe', 'w'], 2 => ['redirect', 1]], $pipes);
    if (!is_resource($proc)) {
        return [-1, 'could not start: ' . $cmd];
    }
    stream_set_blocking($pipes[1], false);
    $out = '';
    $end = time() + $timeout;
    while (true) {
        $out .= (string)stream_get_contents($pipes[1]);
        $st = proc_get_status($proc);
        if (!$st['running']) {
            $out .= (string)stream_get_contents($pipes[1]);
            fclose($pipes[1]);
            proc_close($proc);
            return [$st['exitcode'], trim($out)];
        }
        if (time() > $end) {
            if (core_is_windows()) {
                exec('taskkill /T /F /PID ' . (int)$st['pid'] . ' 2>NUL');
            } else {
                proc_terminate($proc, 9);
            }
            fclose($pipes[1]);
            proc_close($proc);
            return [-2, 'timed out after ' . $timeout . ' s (is the printer on and not showing an error?)'];
        }
        usleep(100000);
    }
}

// Converts an Office/text file to PDF with LibreOffice; returns the PDF path.
function convert_to_pdf(string $src, string $dst, string $soffice, bool $dryRun = false): string
{
    if (is_file($dst)) {
        return $dst;
    }
    if ($soffice === '' || !is_file($soffice)) {
        throw new RuntimeException('LibreOffice is not installed – open the file and print it manually.');
    }
    $tmpDir = dirname($dst) . '/conv_' . bin2hex(random_bytes(4));
    mkdir($tmpDir);
    [, $out] = core_run(escapeshellarg($soffice) . ' --headless --convert-to pdf --outdir '
        . escapeshellarg($tmpDir) . ' ' . escapeshellarg($src), $dryRun);
    $made = glob($tmpDir . '/*.pdf');
    if ($made) {
        rename($made[0], $dst);
    }
    array_map('unlink', glob($tmpDir . '/*') ?: []);
    @rmdir($tmpDir);
    if (!is_file($dst)) {
        throw new RuntimeException('Could not convert to PDF: ' . $out);
    }
    return $dst;
}

// Prints one file; throws on error.
function print_with_options(array $f, string $path, string $ext, string $printer, array $tools, bool $dryRun): void
{
    if (!in_array($ext, ['pdf', 'jpg', 'jpeg', 'png'], true)) {
        $path = convert_to_pdf($path, $path . '.pdf', (string)($tools['soffice'] ?? ''), $dryRun);
    }
    [$code, $out] = core_run(build_print_command($f, $path, $printer, $tools), $dryRun);
    if ($code !== 0) {
        throw new RuntimeException('Printer error (' . $code . '): ' . mb_substr($out, 0, 300));
    }
}

function core_list_printers(): array
{
    $out = [];
    if (core_is_windows()) {
        exec('powershell -NoProfile -Command "Get-Printer | Select-Object -ExpandProperty Name" 2>NUL', $out);
    } else {
        exec('lpstat -e 2>/dev/null', $out);
    }
    return array_values(array_filter(array_map('trim', $out)));
}
