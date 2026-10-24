@echo off
title DayBill ERP - installing the update
echo Waiting for DayBill ERP to close...
:wait339
tasklist /fi "PID eq 339" | find "339" >nul && (timeout /t 1 /nobreak >nul & goto wait339)
echo Keeping a copy of the old version in /home/user/My/DayBillERP/update_backup_7_9_0
robocopy "/home/user/My/DayBillERP" "/home/user/My/DayBillERP/update_backup_7_9_0" /E /XD update_staging update_backup_* logs backups __pycache__ /NFL /NDL /NJH /NJS >nul
echo Copying the new version...
robocopy "/tmp/tmp_hv6q6kh/update_staging" "/home/user/My/DayBillERP" /E /R:20 /W:2 /XF "app_settings.json" "db_config.json" "license.json" "daybill_vault_recovery.dat" "table_layouts.json" "db_config.json" "license.json" /NFL /NDL /NJH /NJS
if errorlevel 8 goto failed
rmdir /s /q "/tmp/tmp_hv6q6kh/update_staging"
echo Done.
set PYINSTALLER_RESET_ENVIRONMENT=1
set _MEIPASS2=
set _PYI_APPLICATION_HOME_DIR=
set _PYI_ARCHIVE_FILE=
set _PYI_PARENT_PROCESS_LEVEL=
set _PYI_SPLASH_IPC=
set _PYI_LINUX_PROCESS_NAME=
start "" "C:\Python314\pythonw.exe" "/home/user/My/DayBillERP/main.py"
exit /b 0
:failed
echo The update could not be copied. The old version is in /home/user/My/DayBillERP/update_backup_7_9_0
pause
