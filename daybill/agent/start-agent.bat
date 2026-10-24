@echo off
REM Starts the Daybill print agent. Put a shortcut to this file in shell:startup to run it at login.
cd /d "%~dp0"
:loop
"C:\xampp\php\php.exe" print-agent.php
echo Agent stopped - restarting in 10 seconds...
timeout /t 10 >nul
goto loop
