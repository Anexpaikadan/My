@echo off
setlocal EnableExtensions
REM ============================================================
REM  DayBill ERP - install the Python libraries (run from source)
REM ============================================================
cd /d "%~dp0"
title DayBill ERP - Install Requirements
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
  echo Python 3.10 or newer is not installed.
  echo Install Python 3.12 from python.org and tick "Add python.exe to PATH".
  start "" "https://www.python.org/downloads/release/python-3129/"
  pause
  exit /b 1
)
echo Installing DayBill ERP requirements with:
%PY% --version
echo.
%PY% install_requirements.py
pause
