@echo off
REM Stops the background agent and removes it from Windows start.
call "%~dp0stop-agent.bat" quiet
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DaybillPrintAgent.vbs" 2>nul
echo The print agent is stopped and will no longer start with Windows.
pause
