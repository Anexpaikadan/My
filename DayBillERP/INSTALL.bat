@echo off
setlocal EnableExtensions
REM ============================================================
REM  DayBill ERP - one-click install (run from source)   v6.9
REM    1. finds Python 3.10+            (opens python.org if missing)
REM    2. installs the libraries        (tested versions, requirements.txt)
REM    3. can create the database       (database\INSTALL_DayBillERP_AllInOne.sql)
REM    4. puts a DayBill icon on the desktop and can start DayBill
REM  Safe to run again: it only adds what is missing.
REM ============================================================
cd /d "%~dp0"
title DayBill ERP - Install
echo.
echo  ==========================================================
echo    DayBill ERP - Install
echo  ==========================================================
echo.

REM ---- 1. Python -------------------------------------------------
set "PY="
for %%V in (3.12 3.13 3.11 3.14 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo  Python 3.10 or newer is not installed.
  echo  Install Python 3.12 from python.org and tick "Add python.exe to PATH",
  echo  then run INSTALL.bat again.
  start "" "https://www.python.org/downloads/release/python-3129/"
  pause
  exit /b 1
)
echo  [1/4] Python found:
%PY% --version
echo.

REM ---- 2. libraries ----------------------------------------------
echo  [2/4] Installing the libraries (this can take a few minutes) ...
%PY% install_requirements.py --no-pause
if errorlevel 1 (
  echo.
  echo  Some REQUIRED libraries did not install - see the list above.
  echo  Check the internet connection and run INSTALL.bat again.
  pause
  exit /b 1
)
echo.

REM ---- 3. database -----------------------------------------------
echo  [3/4] Database
where sqlcmd >nul 2>&1
if errorlevel 1 goto :nosqlcmd
choice /c YN /n /m "       Create the DayBill database on this PC now? [Y/N] "
if errorlevel 2 goto :dbdone
set "SQLSRV=.\SQLEXPRESS"
set /p "SQLSRV=       SQL Server name [.\SQLEXPRESS]: "
if "%SQLSRV%"=="" set "SQLSRV=.\SQLEXPRESS"
echo       Running database\INSTALL_DayBillERP_AllInOne.sql on %SQLSRV% ...
sqlcmd -S "%SQLSRV%" -E -b -I -i "database\INSTALL_DayBillERP_AllInOne.sql" > "%~dp0install_database.log" 2>&1
if errorlevel 1 (
  echo       ! The database script stopped - see install_database.log.
  echo         You can also make it later: DayBill login ^> Database Settings ^>
  echo         Create New Database.
) else (
  echo       Database DayBillERP is ready.
)
goto :dbdone
:nosqlcmd
echo       sqlcmd is not on this PC - that is fine. Make the database the first
echo       time you open DayBill: login ^> Database Settings ^> Create New Database.
:dbdone
echo.

REM ---- 4. desktop icon + start -----------------------------------
echo  [4/4] Desktop icon
set "PYW="
for /f "usebackq delims=" %%P in (`%PY% -c "import sys,os;p=os.path.join(os.path.dirname(sys.executable),'pythonw.exe');print(p if os.path.exists(p) else sys.executable)"`) do set "PYW=%%P"
if defined PYW (
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\DayBill ERP.lnk');" ^
    "$s.TargetPath='%PYW%';$s.Arguments='\"%~dp0main.py\"';$s.WorkingDirectory='%~dp0';" ^
    "$s.IconLocation='%~dp0assets\app.ico';$s.Description='DayBill ERP';$s.Save()" >nul 2>&1
  if errorlevel 1 (
    echo       Could not make the icon - start DayBill with:  %PY% main.py
  ) else (
    echo       "DayBill ERP" icon is on the desktop.
  )
)
echo.
echo  ==========================================================
echo    ALL DONE.  Sign in as  admin  - you set the password at the
echo    first sign-in - then fill  Settings ^> Company.
echo  ==========================================================
echo.
choice /c YN /n /m "  Start DayBill now? [Y/N] "
if errorlevel 2 goto :end
if defined PYW (start "" "%PYW%" "%~dp0main.py") else (start "" %PY% "%~dp0main.py")
:end
endlocal
