@echo off
rem DayBill Database Tool: reset a password, convert another program's database into DayBill
cd /d "%~dp0"
if exist "%~dp0DayBillERP.exe" (
  start "" "%~dp0DayBillERP.exe" --dbtool
) else (
  start "" pythonw "%~dp0dbtool.py"
)
