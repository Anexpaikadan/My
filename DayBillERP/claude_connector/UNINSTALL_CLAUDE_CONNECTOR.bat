@echo off
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% register_claude.py --remove
echo.
echo  DayBill removed from Claude. Quit and reopen Claude to finish.
pause
