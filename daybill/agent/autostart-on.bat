@echo off
REM Starts the print agent hidden now AND every time Windows starts.
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
> "%STARTUP%\DaybillPrintAgent.vbs" echo CreateObject("WScript.Shell").Run """%~dp0start-agent-background.vbs""", 0, False
call "%~dp0stop-agent.bat" quiet
start "" wscript "%~dp0start-agent-background.vbs"
echo.
echo Done! The print agent now runs in the background and starts with Windows.
echo Check Settings - Printing on the website: it should say "connected".
echo Log file: %~dp0agent.log
echo.
pause
