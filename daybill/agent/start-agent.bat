@echo off
REM Starts the Daybill print agent. Put a shortcut to this file in shell:startup to run it at login.
title Daybill print agent
cd /d "%~dp0"
set "PHP=%~dp0php\php.exe"
if not exist "%PHP%" set "PHP=C:\xampp\php\php.exe"
if not exist "%PHP%" set "PHP=php"
"%PHP%" -v >nul 2>&1
if errorlevel 1 (
  echo PHP was not found. Install XAMPP in C:\xampp, or edit the PHP= line in this file.
  pause
  exit /b 1
)
:loop
echo  Do NOT click inside this window - Windows pauses the agent while text is selected.
echo  Better: run autostart-on.bat once, then the agent works hidden in the background.
echo.
"%PHP%" print-agent.php
echo.
echo Agent stopped - read the message above. Restarting in 15 seconds... (close this window to stop)
timeout /t 15 >nul
goto loop
