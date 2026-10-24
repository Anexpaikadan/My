@echo off
REM Stops a running print agent (background or window).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*start-agent-background.vbs*' -or $_.CommandLine -like '*start-agent.bat*' -or $_.CommandLine -like '*print-agent.php*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if not "%~1"=="quiet" (
  echo Print agent stopped.
  pause
)
