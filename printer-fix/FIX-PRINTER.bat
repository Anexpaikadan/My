@echo off
:: ==========================================================================
::  FIX-PRINTER.bat  -  One-click fix for Windows shared (network) printers
::
::  Fixes:  0x0000011b  "Windows cannot connect to the printer"
::          0x00000709  "Operation could not be completed"
::          0x00000bcb  "Cannot connect to the printer" (driver install)
::          0x0000007c / access denied / printer offline on the network
::
::  Double-click it, or run from CMD:
::     FIX-PRINTER.bat                 menu: [1] Main PC  [2] Client PC
::     FIX-PRINTER.bat all             fix host + client settings
::     FIX-PRINTER.bat host            fix the PC the printer is plugged into
::     FIX-PRINTER.bat client          fix a PC that prints over the network
::     FIX-PRINTER.bat diag [PCNAME]   diagnostics report
::     FIX-PRINTER.bat add \\PC\Share  connect to a shared printer
:: ==========================================================================
setlocal EnableExtensions EnableDelayedExpansion
title Network Printer Fix - 0x0000011b / 0x00000709 / 0x00000bcb
color 1F

:: ---- Run as Administrator (asks once with UAC) --------------------------
net session >nul 2>&1
if not errorlevel 1 goto :admin_ok
echo Asking for Administrator rights...
if "%~1"=="" (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
) else (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
)
exit /b
:admin_ok

set "HERE=%~dp0"
set "LOG=%HERE%printer-fix-log.txt"
set "KPRINT=HKLM\SYSTEM\CurrentControlSet\Control\Print"
set "KRPC=HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\RPC"
set "KPNP=HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint"
echo ==== %DATE% %TIME%  %COMPUTERNAME%  args: %* >>"%LOG%"

:: ---- Command line mode --------------------------------------------------
set "AUTO="
if /i "%~1"=="all"    (set "AUTO=1" & call :fix_host & call :fix_client & call :restart_spooler & goto :done)
if /i "%~1"=="host"   (set "AUTO=1" & call :fix_host & call :restart_spooler & goto :done)
if /i "%~1"=="client" (set "AUTO=1" & call :fix_client & call :restart_spooler & goto :done)
if /i "%~1"=="diag"   (set "AUTO=1" & set "DHOST=%~2" & call :diag_report & goto :done)
if /i "%~1"=="add"    (set "AUTO=1" & set "PRN=%~2" & call :add_printer & goto :done)

:: ---- Menu ---------------------------------------------------------------
:menu
cls
echo.
echo  ==================================================================
echo     NETWORK PRINTER FIX        This PC: %COMPUTERNAME%
echo  ==================================================================
echo.
echo     [1] MAIN PC     - the printer cable is in THIS PC
echo     [2] CLIENT PC   - this PC prints to the Main PC's printer
echo.
echo     [3] Connect printer on Client PC   after restart
echo     [4] More tools
echo     [0] Exit
echo.
echo     Do [1] on the Main PC, [2] on every Client PC, restart all PCs,
echo     then do [3] on each Client PC.
echo.
choice /c 12340 /n /m "  Select: "
set "OPT=%errorlevel%"
if "%OPT%"=="5" goto :end
if "%OPT%"=="1" call :main_pc
if "%OPT%"=="2" call :client_pc
if "%OPT%"=="3" (set "PRN=" & call :add_printer)
if "%OPT%"=="4" goto :tools
echo.
pause
goto :menu

:tools
cls
echo.
echo  ==================================================================
echo     MORE TOOLS                 This PC: %COMPUTERNAME%
echo  ==================================================================
echo.
echo     [1] Connect via LOCAL PORT     Client PC - if [3] still fails
echo     [2] Share a printer            Main PC
echo     [3] Save Main PC login         Client PC - access denied / password
echo     [4] Set network to Private     both - sharing is blocked on Public
echo     [5] Diagnostics report         both
echo     [0] Back
echo.
choice /c 123450 /n /m "  Select: "
set "OPT=%errorlevel%"
if "%OPT%"=="6" goto :menu
if "%OPT%"=="1" call :add_localport
if "%OPT%"=="2" call :share_printer
if "%OPT%"=="3" call :save_login
if "%OPT%"=="4" call :set_private
if "%OPT%"=="5" (set "DHOST=" & call :diag_report)
echo.
pause
goto :tools

:: ==========================================================================
:main_pc
call :fix_host
call :fix_client
call :restart_spooler
echo.
choice /c YN /n /m "  Share a printer on this PC now? [Y/N] "
if not errorlevel 2 call :share_printer
echo.
echo  MAIN PC DONE. Now run [2] on every Client PC, then restart all PCs.
exit /b

:client_pc
call :fix_client
call :restart_spooler
echo.
echo  CLIENT PC DONE. Restart this PC, open this file again and press [3].
exit /b

:: ==========================================================================
:fix_host
echo.
echo  ---- HOST FIX: PC that shares the printer ------------------------
echo  [*] Allow clients to connect (0x0000011b fix)
call :regdw "%KPRINT%" RpcAuthnLevelPrivacyEnabled 0
echo  [*] Accept printer RPC over named pipes and TCP (Windows 11 22H2+)
call :regdw "%KRPC%" RpcProtocols 7
call :regdw "%KRPC%" ForceKerberosForRpc 0
echo  [*] Services needed for sharing
for %%s in (Spooler LanmanServer LanmanWorkstation FDResPub fdPHost SSDPSRV upnphost) do call :svc %%s
call :firewall
echo  [*] Shared printers on this PC:
powershell -NoProfile -Command "$s=Get-Printer | Where-Object Shared; if($s){$s | ForEach-Object { '      \\' + $env:COMPUTERNAME + '\' + $_.ShareName + '   (' + $_.Name + ', ' + $_.PrinterStatus + ')' }} else {'      NONE - the next step shares the printer'}"
exit /b

:: ==========================================================================
:fix_client
echo.
echo  ---- CLIENT FIX: PC that prints to a shared printer --------------
call :regdw "%KPRINT%" RpcAuthnLevelPrivacyEnabled 0
echo  [*] Use named pipes for printer RPC (Windows 11 22H2 and newer)
call :regdw "%KRPC%" RpcUseNamedPipeProtocol 1
call :regdw "%KRPC%" RpcProtocols 7
call :regdw "%KRPC%" ForceKerberosForRpc 0
echo  [*] Allow printer driver install from the host (0x00000bcb fix)
call :regdw "%KPNP%" RestrictDriverInstallationToAdministrators 0
echo  [*] Services
for %%s in (Spooler LanmanWorkstation FDResPub fdPHost SSDPSRV) do call :svc %%s
call :firewall
ipconfig /flushdns >nul 2>&1
echo  [ OK ] DNS cache cleared
exit /b

:: ==========================================================================
:restart_spooler
echo.
echo  [*] Restarting Print Spooler and clearing stuck print jobs...
net stop spooler /y >nul 2>&1
del /q /f "%SystemRoot%\System32\spool\PRINTERS\*.*" >nul 2>&1
net start spooler >nul 2>&1
sc query spooler | find "RUNNING" >nul
if errorlevel 1 (echo  [FAIL] Print Spooler did not start) else (echo  [ OK ] Print Spooler running)
call :log "spooler restarted"
exit /b

:: ==========================================================================
:add_printer
echo.
if not defined PRN (
    echo  Type the shared printer path, example:  \\MYPC\EPSON TM-T20II
    echo  Tip: open \\HOSTNAME in File Explorer to see the exact share name.
    set /p "PRN=  Printer path: "
)
if not defined PRN exit /b
set "PRN=%PRN:"=%"
if not "%PRN:~0,2%"=="\\" (echo  [FAIL] Path must start with \\ & set "PRN=" & exit /b)
for /f "tokens=1 delims=\" %%h in ("%PRN%") do set "PHOST=%%h"
call :check_host "%PHOST%"
echo  [*] Connecting to %PRN% ...
rundll32 printui.dll,PrintUIEntry /in /n "%PRN%"
timeout /t 3 /nobreak >nul
powershell -NoProfile -Command "if(Get-Printer -Name '%PRN%' -ErrorAction SilentlyContinue){exit 0}else{exit 1}"
if errorlevel 1 (
    echo  [FAIL] Not connected. Do [1] on Main PC, [2] here, restart both, try again.
    echo         Still failing?  More tools - [1] Connect via LOCAL PORT.
    call :log "add FAILED %PRN%"
    set "PRN="
    exit /b
)
echo  [ OK ] Connected: %PRN%
call :log "added %PRN%"
call :after_add "%PRN%"
set "PRN="
exit /b

:: ==========================================================================
:add_localport
:: Prints to the share over SMB through a local port, so it does not use the
:: RPC printer connection that causes 0x0000011b.  Needs the driver on this PC.
echo.
echo  Connect via LOCAL PORT - works even when 0x0000011b is not fixed.
echo  Type the shared printer path, example:  \\MYPC\EPSON TM-T20II
set "LP="
set /p "LP=  Printer path: "
if not defined LP exit /b
set "LP=%LP:"=%"
if not "%LP:~0,2%"=="\\" (echo  [FAIL] Path must start with \\ & exit /b)
for /f "tokens=1 delims=\" %%h in ("%LP%") do set "PHOST=%%h"
call :check_host "%PHOST%"
echo.
echo  Printer drivers on this PC - pick the SAME model as the printer:
set n=0
for /f "usebackq delims=" %%d in (`powershell -NoProfile -Command "Get-PrinterDriver | Select-Object -ExpandProperty Name | Sort-Object -Unique"`) do (
    set /a n+=1
    set "DRV!n!=%%d"
    echo     [!n!] %%d
)
echo.
echo  Driver not in the list? Install the printer driver on this PC first,
echo  e.g. EPSON TM-T20II: install "Epson Advanced Printer Driver" APD.
set "SEL="
set /p "SEL=  Driver number: "
if not defined SEL exit /b
if not defined DRV%SEL% (echo  [FAIL] Wrong number & exit /b)
set "DRV=!DRV%SEL%!"
set "PNAME="
set /p "PNAME=  Name for the printer on this PC [Network Printer]: "
if not defined PNAME set "PNAME=Network Printer"
powershell -NoProfile -Command "$p='%LP%'; if(-not (Get-PrinterPort -Name $p -ErrorAction SilentlyContinue)){Add-PrinterPort -Name $p}; Add-Printer -Name '%PNAME%' -DriverName '%DRV%' -PortName $p -ErrorAction Stop"
if errorlevel 1 (
    echo  [FAIL] Could not add the printer. More tools - [3] Save Main PC login,
    echo         then try again.
    call :log "localport FAILED %LP%"
    exit /b
)
echo  [ OK ] Added "%PNAME%" on port %LP%
call :log "localport added %PNAME% -> %LP% (%DRV%)"
call :after_add "%PNAME%"
exit /b

:: ==========================================================================
:share_printer
echo.
echo  Printers on this PC:
powershell -NoProfile -Command "Get-Printer | Format-Table Name,Shared,ShareName,PrinterStatus -AutoSize | Out-String -Width 200"
set "SP="
set /p "SP=  Exact printer name to share: "
if not defined SP exit /b
set "SN=%SP: =%"
set "SN2="
set /p "SN2=  Share name, no spaces [%SN%]: "
if defined SN2 set "SN=%SN2%"
powershell -NoProfile -Command "Set-Printer -Name '%SP%' -Shared $true -ShareName '%SN%' -ErrorAction Stop"
if errorlevel 1 (echo  [FAIL] Could not share "%SP%" & exit /b)
echo  [ OK ] Shared. On other PCs use:   \\%COMPUTERNAME%\%SN%
call :log "shared %SP% as %SN%"
exit /b

:: ==========================================================================
:save_login
echo.
echo  Saves the HOST PC's Windows user name and password on THIS PC, so the
echo  share opens without "access denied". The host user must have a password.
set "CH=" & set "CU="
set /p "CH=  Host PC name (e.g. MYPC): "
if not defined CH exit /b
set "CH=%CH:\=%"
set /p "CU=  Host user name: "
if not defined CU exit /b
echo  Type the host password when asked - it is not shown on screen.
cmdkey /add:%CH% /user:%CH%\%CU% /pass
if errorlevel 1 (echo  [FAIL] Could not save login) else (echo  [ OK ] Login saved for %CH%)
call :log "saved login for %CH%"
exit /b

:: ==========================================================================
:set_private
echo.
echo  Changing Public networks to Private - only do this on your shop / home LAN.
powershell -NoProfile -Command "Get-NetConnectionProfile | Where-Object NetworkCategory -eq 'Public' | Set-NetConnectionProfile -NetworkCategory Private; Get-NetConnectionProfile | Format-Table Name,InterfaceAlias,NetworkCategory -AutoSize | Out-String"
call :firewall
call :log "network set private"
exit /b

:: ==========================================================================
:diag_report
if not defined DHOST if not defined AUTO set /p "DHOST=  Host PC name to test (Enter to skip): "
if defined DHOST set "DHOST=%DHOST:\=%"
set "REP=%HERE%printer-diagnostic-%COMPUTERNAME%.txt"
echo  [*] Collecting... please wait
call :diag > "%REP%" 2>&1
type "%REP%"
echo.
echo  Report saved: %REP%
exit /b

:diag
echo ===== PRINTER DIAGNOSTIC  %COMPUTERNAME%  %DATE% %TIME% =====
ver
echo.
echo --- Registry: 0x11b / RPC / Point and Print ---
reg query "%KPRINT%" /v RpcAuthnLevelPrivacyEnabled 2>nul || echo RpcAuthnLevelPrivacyEnabled : NOT SET
reg query "%KRPC%" 2>nul || echo Printers\RPC policy : NOT SET
reg query "%KPNP%" 2>nul || echo PointAndPrint policy : NOT SET
echo.
echo --- Services ---
for %%s in (Spooler LanmanServer LanmanWorkstation FDResPub fdPHost SSDPSRV) do (
    for /f "tokens=3,4" %%a in ('sc query %%s ^| find "STATE"') do echo %%s : %%b
)
echo.
echo --- Network profile (must be Private) ---
powershell -NoProfile -Command "Get-NetConnectionProfile | Format-Table Name,InterfaceAlias,NetworkCategory -AutoSize | Out-String -Width 200"
echo --- Firewall: File and Printer Sharing ---
powershell -NoProfile -Command "Get-NetFirewallRule -Group '@FirewallAPI.dll,-28502' | Group-Object Enabled | ForEach-Object { 'Enabled=' + $_.Name + ' rules: ' + $_.Count }"
echo.
echo --- Printers on this PC ---
powershell -NoProfile -Command "Get-Printer | Format-Table Name,Type,Shared,ShareName,PortName,DriverName,PrinterStatus -AutoSize | Out-String -Width 250"
echo --- Saved logins ---
cmdkey /list | find "Target"
echo.
echo --- Recent print updates ---
powershell -NoProfile -Command "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 5 HotFixID,InstalledOn | Format-Table -AutoSize | Out-String"
if not defined DHOST goto :diag_end
echo --- Connection to %DHOST% ---
ping -n 2 %DHOST%
powershell -NoProfile -Command "$t=Test-NetConnection -ComputerName '%DHOST%' -Port 445 -WarningAction SilentlyContinue; 'SMB port 445 open: ' + $t.TcpTestSucceeded"
echo.
net view \\%DHOST%
:diag_end
echo ===== END =====
exit /b

:: ==========================================================================
::  Helpers
:: ==========================================================================
:regdw
reg add "%~1" /v %~2 /t REG_DWORD /d %~3 /f >nul 2>&1
if errorlevel 1 (echo  [FAIL] %~2 = %~3) else (echo  [ OK ] %~2 = %~3)
call :log "reg %~1 %~2=%~3"
exit /b

:svc
sc config %1 start= auto >nul 2>&1
net start %1 >nul 2>&1
sc query %1 | find "RUNNING" >nul
if errorlevel 1 (echo  [WARN] Service %1 not running) else (echo  [ OK ] Service %1 running)
exit /b

:firewall
echo  [*] Firewall: allow File and Printer Sharing + Network Discovery
powershell -NoProfile -Command "Enable-NetFirewallRule -Group '@FirewallAPI.dll,-28502' -ErrorAction SilentlyContinue; Enable-NetFirewallRule -Group '@FirewallAPI.dll,-32752' -ErrorAction SilentlyContinue"
netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=Yes >nul 2>&1
echo  [ OK ] Firewall rules enabled
exit /b

:check_host
echo  [*] Checking host %~1 ...
ping -n 1 -w 1500 %~1 >nul 2>&1
if errorlevel 1 (echo  [WARN] %~1 does not answer ping - check name, cable/Wi-Fi, host PC is ON) else (echo  [ OK ] %~1 is reachable)
powershell -NoProfile -Command "if((Test-NetConnection -ComputerName '%~1' -Port 445 -WarningAction SilentlyContinue).TcpTestSucceeded){exit 0}else{exit 1}"
if errorlevel 1 (echo  [WARN] File sharing port 445 closed on %~1 - run FIX on the host PC) else (echo  [ OK ] File sharing port 445 open)
exit /b

:after_add
if defined AUTO exit /b
choice /c YN /n /m "  Set as DEFAULT printer? [Y/N] "
if not errorlevel 2 rundll32 printui.dll,PrintUIEntry /y /n "%~1"
choice /c YN /n /m "  Print a TEST PAGE? [Y/N] "
if not errorlevel 2 rundll32 printui.dll,PrintUIEntry /k /n "%~1"
exit /b

:log
>>"%LOG%" echo %TIME% %~1
exit /b

:: ==========================================================================
:done
echo.
echo  Log: %LOG%
:end
endlocal
exit /b
