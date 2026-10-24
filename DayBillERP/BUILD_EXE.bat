@echo off
setlocal EnableExtensions
REM ============================================================
REM  DayBill ERP - one-click EXE builder  (Windows 10 / 11)
REM  Double-click this file. It makes:
REM     dist\DayBillERP.exe          (with the DayBill icon)
REM     "DayBill ERP" icon on the Desktop and in the Start menu
REM  Everything it does is also written to  build_log.txt
REM ============================================================
cd /d "%~dp0"
title DayBill ERP - Build EXE
set "HERE=%~dp0"
set "LOG=%~dp0build_log.txt"

echo.
echo  ==============================================
echo    DayBill ERP  -  building DayBillERP.exe
echo  ==============================================
echo.

if not exist "%HERE%main.py" goto :notunzipped
echo DayBill ERP build  %date% %time% > "%LOG%" 2>nul
if errorlevel 1 goto :readonly

REM ---- 1. find Python 3.10 or newer ---------------------------
set "PY="
for %%V in (3.12 3.13 3.11 3.14 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY goto :nopython
echo [1/5] Python found:
%PY% --version
%PY% --version >> "%LOG%" 2>&1
%PY% -c "import struct; print('Python bits:', struct.calcsize('P')*8)" >> "%LOG%" 2>&1

REM ---- 2. libraries -------------------------------------------
echo.
echo [2/5] Installing / checking libraries - please wait...
echo       (needs internet the first time)
%PY% -m pip --version >nul 2>&1
if errorlevel 1 %PY% -m ensurepip --upgrade >> "%LOG%" 2>&1
%PY% -m pip install --disable-pip-version-check --upgrade pip >> "%LOG%" 2>&1
%PY% -m pip install --disable-pip-version-check --upgrade pyinstaller pyinstaller-hooks-contrib >> "%LOG%" 2>&1
%PY% -m pip install --disable-pip-version-check -r "%HERE%requirements.txt" >> "%LOG%" 2>&1
%PY% -m pip install --disable-pip-version-check pyodbc pillow openpyxl reportlab qrcode bcrypt >> "%LOG%" 2>&1
for %%P in (python-barcode bcrypt cryptography lxml certifi requests arabic-reshaper python-bidi pywin32 pypdfium2) do (
  %PY% -m pip install --disable-pip-version-check %%P >> "%LOG%" 2>&1 || echo       - %%P could not be installed, skipped
)
%PY% -c "import PyInstaller, pyodbc, PIL, openpyxl, reportlab, qrcode, bcrypt" >> "%LOG%" 2>&1
if errorlevel 1 goto :nolibs
echo       Libraries OK.

REM ---- 3. build -----------------------------------------------
echo.
echo [3/5] Building DayBillERP.exe - this takes 1 to 5 minutes...
taskkill /f /im DayBillERP.exe >nul 2>&1
if exist "%HERE%build" rmdir /s /q "%HERE%build" >nul 2>&1
if exist "%HERE%dist\DayBillERP.exe" del /f /q "%HERE%dist\DayBillERP.exe" >nul 2>&1
if exist "%HERE%dist\DayBillERP.exe" goto :locked
%PY% -m PyInstaller --clean --noconfirm --distpath "%HERE%dist" --workpath "%HERE%build" "%HERE%DayBillERP.spec" >> "%LOG%" 2>&1
if not exist "%HERE%dist\DayBillERP.exe" goto :buildfail
echo       Built: dist\DayBillERP.exe
copy /y "%HERE%DayBill_Database_Tool.bat" "%HERE%dist\" >nul 2>&1
echo       Database Tool: dist\DayBill_Database_Tool.bat  (or DayBillERP.exe --dbtool)
echo       Checking the new exe can make invoices, QR and barcodes...
start "" /wait "%HERE%dist\DayBillERP.exe" --selftest
if errorlevel 1 (
  echo       ! Print check found a problem - see dist\logs\selftest.log
  type "%HERE%dist\logs\selftest.log" 2>nul
  type "%HERE%dist\logs\selftest.log" >> "%LOG%" 2>nul
) else (
  echo       Print check OK - invoices, QR, barcodes, Arabic.
)

REM ---- 4. icon + shortcuts --------------------------------------
echo.
echo [4/5] Making the "DayBill ERP" icon on the Desktop and Start menu...
copy /y "%HERE%assets\app.ico" "%HERE%dist\DayBillERP.ico" >nul 2>&1
if not exist "%HERE%dist\config" mkdir "%HERE%dist\config" >nul 2>&1
set "SC_TARGET=%HERE%dist\DayBillERP.exe"
set "SC_DIR=%HERE%dist"
set "SC_ICON=%HERE%dist\DayBillERP.ico"
if not exist "%SC_ICON%" set "SC_ICON=%SC_TARGET%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { if ($d) { $s = $w.CreateShortcut((Join-Path $d 'DayBill ERP.lnk')); $s.TargetPath = $env:SC_TARGET; $s.WorkingDirectory = $env:SC_DIR; $s.IconLocation = $env:SC_ICON + ',0'; $s.Description = 'DayBill ERP'; $s.Save(); Write-Output ('Shortcut: ' + $d) } }" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo       Could not make the shortcut - right-click dist\DayBillERP.exe, Send to, Desktop.
) else (
  echo       Desktop + Start menu icon made.
)
REM Windows keeps old icons in a cache - refresh it so the new icon shows
ie4uinit.exe -show >nul 2>&1
ie4uinit.exe -ClearIconCache >nul 2>&1

REM ---- 5. installer (v6.0) - only when Inno Setup 6 is installed ----
set "ISCC="
for %%I in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do (
  if not defined ISCC if exist "%%~I" set "ISCC=%%~I"
)
if defined ISCC (
  echo       Making the one-file installer dist\DayBillERP_Setup_*.exe ...
  "%ISCC%" /Q "%HERE%tools\DayBillERP_Setup.iss" >> "%LOG%" 2>&1 && echo       Installer made. || echo       Installer not made - see build_log.txt
) else (
  echo       Tip: install Inno Setup 6 to also get a one-file Setup.exe.
)

REM ---- 6. done --------------------------------------------------
echo.
echo [5/5] Done!
echo.
echo  ==============================================
echo    Your app:  dist\DayBillERP.exe
echo    Desktop:   "DayBill ERP" icon
echo  ==============================================
echo.
echo  Copy the whole "dist" folder to the shop PC (e.g. C:\DayBill).
echo  DayBill keeps its settings in dist\config next to the exe.
echo  The shop PC also needs: SQL Server + ODBC Driver 17 or 18.
echo.
start "" explorer "%HERE%dist"
pause
exit /b 0

REM ================= problems =================================
:notunzipped
echo  This folder is not complete.
echo  Right-click the DayBill .zip file, choose "Extract All...", then
echo  open the extracted folder and double-click BUILD_EXE.bat there.
echo.
pause
exit /b 1

:readonly
echo  Can't write in this folder:
echo     %HERE%
echo  Copy the DayBill folder to C:\DayBill  - not inside Program Files -
echo  and run BUILD_EXE.bat from there.
echo.
pause
exit /b 1

:nopython
echo  Python is not installed on this PC.
echo.
echo  1. Install Python 3.12 from python.org - the page opens now.
echo  2. On the first screen TICK  "Add python.exe to PATH".
echo  3. Run BUILD_EXE.bat again.
echo.
echo Python not found >> "%LOG%"
start "" "https://www.python.org/downloads/release/python-3129/"
pause
exit /b 1

:nolibs
echo.
echo  The libraries could not be installed.
echo  - Check the internet connection and run BUILD_EXE.bat again.
echo  - Details: build_log.txt   last lines:
echo  ----------------------------------------------
powershell -NoProfile -Command "Get-Content -Path $env:LOG -Tail 20"
echo  ----------------------------------------------
pause
exit /b 1

:locked
echo.
echo  dist\DayBillERP.exe is open or locked.
echo  Close DayBill ERP (and any window showing that folder), then run again.
echo.
pause
exit /b 1

:buildfail
echo.
echo  The build did not make dist\DayBillERP.exe.
echo  - If your antivirus removed it: add this folder as an exclusion
echo    in Windows Security, then run BUILD_EXE.bat again.
echo  - Details: build_log.txt   last lines:
echo  ----------------------------------------------
powershell -NoProfile -Command "Get-Content -Path $env:LOG -Tail 30"
echo  ----------------------------------------------
pause
exit /b 1
