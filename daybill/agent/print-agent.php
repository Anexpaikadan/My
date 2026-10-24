<?php
// Daybill print agent – runs on the shop PC when the app is hosted in the cloud.
// It asks the website for print jobs, downloads each file and prints it locally.
//
//   Windows:  C:\xampp\php\php.exe print-agent.php      (or double-click start-agent.bat)
//   Linux:    php print-agent.php

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit('Run this from the command line on the shop PC.');
}

require __DIR__ . '/print-core.php';
$c = require __DIR__ . '/agent-config.php';
if (stripos($c['server_url'], 'https://') !== 0) {
    exit("server_url in agent-config.php must start with https:// (HTTPS is required).\n");
}
if (!extension_loaded('openssl')) {
    exit("PHP cannot use HTTPS: the openssl extension is off.\n"
        . 'Fix: open ' . (php_ini_loaded_file() ?: 'php.ini') . ", remove the ; before  extension=openssl  and start the agent again.\n");
}
// Windows PHP often has no list of trusted certificates; use one that ships with XAMPP if available.
if ($c['ca_file'] === '' && !ini_get('openssl.cafile')) {
    foreach (['C:\\xampp\\apache\\bin\\curl-ca-bundle.crt', 'C:\\xampp\\php\\extras\\ssl\\cacert.pem',
              __DIR__ . DIRECTORY_SEPARATOR . 'cacert.pem', dirname(PHP_BINARY) . DIRECTORY_SEPARATOR . 'extras\\ssl\\cacert.pem'] as $ca) {
        if (is_file($ca)) {
            $c['ca_file'] = $ca;
            break;
        }
    }
}
$base = rtrim($c['server_url'], '/') . '/api.php';
$tmpDir = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'daybill-agent';
if (!is_dir($tmpDir)) {
    mkdir($tmpDir, 0700, true);
}

function say(string $msg): void
{
    echo '[' . date('H:i:s') . '] ' . $msg . PHP_EOL;
}

function api(string $url, array $c, ?array $post = null, int $timeout = 30): array
{
    $ssl = ['verify_peer' => true, 'verify_peer_name' => true];
    if ($c['ca_file'] !== '') {
        $ssl['cafile'] = $c['ca_file'];
    }
    // A User-Agent is needed: many hosting firewalls block requests without one.
    $http = ['header' => 'X-Agent-Key: ' . $c['agent_key'] . "\r\nUser-Agent: DaybillPrintAgent/1.1 (PHP " . PHP_VERSION . ")\r\n",
        'timeout' => $timeout, 'ignore_errors' => true];
    if ($post !== null) {
        $http['method'] = 'POST';
        $http['header'] .= "Content-Type: application/x-www-form-urlencoded\r\n";
        $http['content'] = http_build_query($post);
    }
    $body = @file_get_contents($url, false, stream_context_create(['http' => $http, 'ssl' => $ssl]));
    if ($body === false) {
        $err = error_get_last()['message'] ?? 'connection failed';
        throw new RuntimeException($err);
    }
    $status = 0;
    foreach ($http_response_header ?? [] as $h) {
        if (preg_match('#^HTTP/\S+\s+(\d+)#', $h, $m)) {
            $status = (int)$m[1];
        }
    }
    return [$status, $body];
}

say('Daybill print agent starting – server ' . $c['server_url'] . ' (PHP ' . PHP_VERSION . ')');
if ($c['ca_file'] !== '') {
    say('Certificates: ' . $c['ca_file']);
}
try {
    [$status, $body] = api($base . '?action=ping', $c);
} catch (Throwable $e) {
    say('CANNOT CONNECT: ' . $e->getMessage());
    if (stripos($e->getMessage(), 'certificate') !== false || stripos($e->getMessage(), 'SSL') !== false) {
        say('Fix: download https://curl.se/ca/cacert.pem, save it in ' . __DIR__ . ' as cacert.pem, start again.');
    } elseif (stripos($e->getMessage(), 'getaddrinfo') !== false || stripos($e->getMessage(), 'resolve') !== false) {
        say('Fix: check the internet connection and the spelling of server_url in agent-config.php.');
    }
    exit(1);
}
if ($status !== 200) {
    $hint = [
        403 => strpos($body, 'Invalid agent key') !== false
            ? 'The agent key does not match: copy it again from Settings → Printing (no spaces).'
            : 'The hosting firewall blocked the agent. Ask the host to allow requests to api.php, or check .htaccess.',
        404 => 'api.php was not found: server_url must be the folder that contains api.php (the same address as the customer page, without index.php).',
        500 => 'Server error: open the website once in a browser to see the problem.',
    ][$status] ?? 'Check server_url and agent_key in agent-config.php.';
    say("Server answered $status: " . mb_substr(strip_tags($body), 0, 200));
    say('Fix: ' . $hint);
    exit(1);
}
say('Connected to "' . (json_decode($body, true)['shop'] ?? '?') . '". Waiting for print jobs… (Ctrl+C to stop)');

$tools = ['sumatra' => find_sumatra($c['sumatra_path'], __DIR__), 'soffice' => $c['soffice_path'], 'lp' => $c['lp_path']];
if (core_is_windows()) {
    say($tools['sumatra'] !== '' ? 'SumatraPDF: ' . $tools['sumatra']
        : 'WARNING: SumatraPDF not found – install it or put SumatraPDF.exe in ' . __DIR__ . DIRECTORY_SEPARATOR . 'tools');
}
$printers = core_list_printers();
say('Printers on this PC: ' . ($printers ? implode(', ', $printers) : 'none found'));
try {
    api($base . '?action=printers', $c, ['names' => $printers]);
} catch (Throwable $e) {
    say('Could not send printer list: ' . $e->getMessage());
}

while (true) {
    try {
        [$status, $body] = api($base . '?action=next', $c);
        $job = $status === 200 ? (json_decode($body, true)['job'] ?? null) : null;
        if ($status !== 200) {
            say("Server error $status");
        }
        if ($job) {
            $ext = preg_replace('/[^a-z0-9]/', '', strtolower((string)$job['ext']));
            $file = $tmpDir . DIRECTORY_SEPARATOR . 'job' . (int)$job['id'] . '.' . $ext;
            say('Printing "' . $job['name'] . '" – ' . $job['copies'] . 'x ' . $job['paper'] . ' ' . $job['color'] . ' ' . $job['sides']);
            try {
                [$s, $data] = api($base . '?action=file&id=' . (int)$job['id'], $c, null, 300);
                if ($s !== 200) {
                    throw new RuntimeException("download failed ($s)");
                }
                file_put_contents($file, $data);
                $printer = $c['printer_override'] !== '' ? $c['printer_override'] : (string)$job['printer'];
                print_with_options($job, $file, $ext, $printer, $tools, (bool)$c['dry_run']);
                api($base . '?action=result', $c, ['id' => $job['id'], 'ok' => '1']);
                say('  done');
            } catch (Throwable $e) {
                api($base . '?action=result', $c, ['id' => $job['id'], 'ok' => '0', 'error' => $e->getMessage()]);
                say('  FAILED: ' . $e->getMessage());
            }
            @unlink($file);
            @unlink($file . '.pdf');
            continue; // check for the next job straight away
        }
    } catch (Throwable $e) {
        say('Connection problem: ' . $e->getMessage());
    }
    sleep(max(1, (int)$c['poll_seconds']));
}
