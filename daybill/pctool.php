<?php
// Shop admin: downloads ONE file that sets up the shop PC for printing.
// The .bat contains the print agent (with this shop's address and key) and a PowerShell
// installer that downloads PHP, SumatraPDF and the certificate list, then starts the agent
// in the background and on every Windows start.

require __DIR__ . '/lib.php';
$user = require_admin();
// Super admins can download the tool of any shop from the Shops page.
if (is_super($user) && isset($_GET['shop'])) {
    $ids = array_map('intval', array_column(all_shops(), 'id'));
    if (in_array((int)$_GET['shop'], $ids, true)) {
        shop_id((int)$_GET['shop']);
    }
}
if (!shop()) {
    exit('Open a shop first.');
}
$key = setting('agent_key', '');
if ($key === '') {
    $key = bin2hex(random_bytes(20));
    save_setting('agent_key', $key);
}
$slug = shop()['slug'];
$url = base_url();

// Agent files, with agent-config.php filled in for this shop.
$files = [];
foreach (['print-agent.php', 'print-core.php', 'start-agent-background.vbs', 'start-agent.bat', 'stop-agent.bat',
          'autostart-on.bat', 'autostart-off.bat', 'tools/README.txt'] as $name) {
    $files[$name] = file_get_contents(__DIR__ . '/agent/' . $name);
}
$files['agent-config.php'] = str_replace(
    ["'https://yourdomain.com/daybill/'", "'PASTE-AGENT-KEY-HERE'"],
    [var_export($url, true), var_export($key, true)],
    file_get_contents(__DIR__ . '/agent/agent-config.php')
);
$writes = '';
foreach ($files as $name => $data) {
    $writes .= 'Put-File ' . "'" . str_replace('/', '\\', $name) . "' '" . base64_encode($data) . "'\r\n";
}

$ps = <<<'PS'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Say($t, $c = 'Gray') { Write-Host $t -ForegroundColor $c }
function Get-Url($urls, $out) {
  foreach ($u in $urls) {
    try { Say "  downloading $u"; Invoke-WebRequest -Uri $u -OutFile $out -UseBasicParsing -UserAgent 'DaybillSetup/1.0'; return $true }
    catch { Say "  (not available: $($_.Exception.Message))" DarkYellow }
  }
  return $false
}

Say ''
Say '=== DAYbill print agent setup - shop: __SLUG__ ===' Cyan
$dir = 'C:\DAYbill-Agent'
try { New-Item -ItemType Directory -Force -Path $dir | Out-Null } catch { $dir = Join-Path $env:LOCALAPPDATA 'DAYbill-Agent'; New-Item -ItemType Directory -Force -Path $dir | Out-Null }
New-Item -ItemType Directory -Force -Path (Join-Path $dir 'tools') | Out-Null
Say "Folder: $dir"

# 1. Stop an agent that is already running (update)
Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*start-agent-background.vbs*' -or $_.CommandLine -like '*print-agent.php*') } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 2. Agent files
function Put-File($name, $b64) { [IO.File]::WriteAllBytes((Join-Path $dir $name), [Convert]::FromBase64String($b64)) }
__FILES__
Say '[1/5] Print agent files written' Green

# 3. PHP (portable, only for the agent)
$php = Join-Path $dir 'php\php.exe'
if (-not (Test-Path $php)) {
  Say '[2/5] Downloading PHP ...'
  $zip = Join-Path $env:TEMP 'daybill-php.zip'
  $ok = Get-Url @('https://windows.php.net/downloads/releases/latest/php-8.3-nts-Win32-vs16-x64-latest.zip',
                  'https://windows.php.net/downloads/releases/latest/php-8.2-nts-Win32-vs16-x64-latest.zip',
                  'https://windows.php.net/downloads/releases/latest/php-8.4-nts-Win32-vs17-x64-latest.zip') $zip
  if (-not $ok) { throw 'Could not download PHP. Check the internet connection and run this file again.' }
  Expand-Archive -Path $zip -DestinationPath (Join-Path $dir 'php') -Force
  Remove-Item $zip -Force
}
$ini = Join-Path $dir 'php\php.ini'
$cfg = Get-Content (Join-Path $dir 'php\php.ini-production') -Raw
$cfg = $cfg -replace ';\s*extension_dir\s*=\s*"ext"', 'extension_dir = "ext"' -replace ';extension=openssl', 'extension=openssl' -replace ';extension=mbstring', 'extension=mbstring'
$cfg += "`r`nopenssl.cafile=`"$dir\cacert.pem`"`r`n"
[IO.File]::WriteAllText($ini, $cfg)
function Test-Php { $ErrorActionPreference = 'Continue'; $out = & $php -v 2>&1 | Out-String; return @($LASTEXITCODE, $out) }
$t = Test-Php
if ($t[0] -ne 0) {
  Say '  PHP needs the Microsoft Visual C++ runtime - installing it (Windows may ask for permission) ...' Yellow
  $vc = Join-Path $env:TEMP 'vc_redist.x64.exe'
  if (Get-Url @('https://aka.ms/vs/17/release/vc_redist.x64.exe') $vc) { Start-Process $vc -ArgumentList '/install','/quiet','/norestart' -Verb RunAs -Wait }
  $t = Test-Php
  if ($t[0] -ne 0) { throw "PHP does not start: $($t[1])" }
}
Say "[2/5] PHP ready: $(($t[1] -split "`n")[0])" Green

# 4. Certificates and SumatraPDF
Get-Url @('https://curl.se/ca/cacert.pem') (Join-Path $dir 'cacert.pem') | Out-Null
$sumatra = @("$env:ProgramFiles\SumatraPDF\SumatraPDF.exe", "${env:ProgramFiles(x86)}\SumatraPDF\SumatraPDF.exe",
             "$env:LOCALAPPDATA\SumatraPDF\SumatraPDF.exe", (Join-Path $dir 'tools\SumatraPDF.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $sumatra) {
  Say '[3/5] Downloading SumatraPDF (prints PDF and photos) ...'
  $zip = Join-Path $env:TEMP 'daybill-sumatra.zip'
  if (Get-Url @('https://www.sumatrapdfreader.org/dl/rel/3.5.2/SumatraPDF-3.5.2-64.zip',
                'https://www.sumatrapdfreader.org/dl/rel/3.5.1/SumatraPDF-3.5.1-64.zip') $zip) {
    $tmp = Join-Path $env:TEMP 'daybill-sumatra'; Expand-Archive -Path $zip -DestinationPath $tmp -Force
    Get-ChildItem $tmp -Filter 'SumatraPDF*.exe' | Select-Object -First 1 | Copy-Item -Destination (Join-Path $dir 'tools\SumatraPDF.exe') -Force
    Remove-Item $zip, $tmp -Recurse -Force
  } else { Say '  Could not download SumatraPDF - install it from sumatrapdfreader.org' Yellow }
}
Say '[3/5] SumatraPDF ready' Green

# 5. Test the connection to the website
try {
  $r = Invoke-WebRequest -Uri '__URL__api.php?action=ping' -Headers @{ 'X-Agent-Key' = '__KEY__' } -UseBasicParsing -UserAgent 'DaybillSetup/1.0'
  Say "[4/5] Website connection OK: $($r.Content)" Green
} catch { Say "[4/5] Website test failed: $($_.Exception.Message) - the agent will keep trying." Yellow }

# 6. Start now and with every Windows start (hidden, restarts itself)
$startup = [Environment]::GetFolderPath('Startup')
$vbs = Join-Path $dir 'start-agent-background.vbs'
[IO.File]::WriteAllText((Join-Path $startup 'DaybillPrintAgent.vbs'), "CreateObject(""WScript.Shell"").Run """"""$vbs"""""", 0, False")
Start-Process wscript.exe -ArgumentList "`"$vbs`""
Start-Sleep -Seconds 6
Say '[5/5] Print agent started in the background and set to start with Windows' Green
$log = Join-Path $dir 'agent.log'
if (Test-Path $log) { Say ''; Say 'Agent log:'; Get-Content $log -Tail 6 | ForEach-Object { Say "  $_" } }
Say ''
Say 'DONE. Printing now works automatically - you can close this window.' Cyan
Say "Tip: set Windows Power > Sleep to Never. Log file: $log"
PS;
$ps = str_replace(['__FILES__', '__SLUG__', '__URL__', '__KEY__'], [rtrim($writes), $slug, $url, $key], $ps);

$bat = "@echo off\r\n"
    . "title DAYbill print agent setup - $slug\r\n"
    . "REM One-file setup for the shop PC: double-click, wait until it says DONE.\r\n"
    . "set \"DAYBILL_SETUP=%~f0\"\r\n"
    . "powershell -NoProfile -ExecutionPolicy Bypass -Command \"\$s=[IO.File]::ReadAllText(\$env:DAYBILL_SETUP); "
    . "try { iex \$s.Substring(\$s.LastIndexOf('#DAYBILL-PS#') + 12) } catch { Write-Host ('ERROR: ' + \$_.Exception.Message) -ForegroundColor Red }\"\r\n"
    . "echo.\r\npause\r\nexit /b\r\n"
    . "#DAYBILL-PS#\r\n"
    . str_replace(["\r\n", "\n"], ["\n", "\r\n"], $ps) . "\r\n";

header('Content-Type: application/octet-stream');
header('Content-Disposition: attachment; filename="DAYbill-PC-Setup-' . $slug . '.bat"');
header('Content-Length: ' . strlen($bat));
header('Cache-Control: private, no-store');
echo $bat;
