@echo off
chcp 65001 >nul
title DayBill ERP - Claude connector setup
cd /d "%~dp0"
echo.
echo  ============================================================
echo    DayBill ERP  -  Connect to Claude (read-only reports)
echo  ============================================================
echo.

REM --- find the same Python that runs DayBill -------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo  [X] Python was not found. Install Python 3.10+ from python.org
    echo      and tick "Add Python to PATH", then run this again.
    pause
    exit /b 1
)

echo  [1/4] Installing the MCP package (needs internet) ...
%PY% -m pip install --upgrade "mcp" pyodbc
if errorlevel 1 (
    echo  [X] pip install failed. Check the internet connection and try again.
    pause
    exit /b 1
)

echo.
echo  [2/4] Testing the DayBill database connection ...
%PY% daybill_mcp.py --test
if errorlevel 1 (
    echo.
    echo  [X] Could not reach the database. Open DayBill once and check
    echo      Login ^> Database Settings, or edit connector_config.json.
    pause
    exit /b 1
)

echo.
echo  [3/4] Registering DayBill in the Claude desktop app ...
%PY% register_claude.py
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo  [4/4] Done.
echo.
echo  NEXT: fully quit Claude (right-click the Claude icon near the clock
echo        ^> Quit), then open Claude again. Ask things like:
echo          "Show my sales this month from DayBill"
echo          "VAT return for July to September"
echo          "Which products are low on stock?"
echo          "What should I order this week?"
echo          "Which batches will expire before they sell?"
echo        Or pick a ready-made prompt: + ^> DayBill ERP ^> Daily stock check
echo.
pause
