' Daybill print agent - runs hidden in the background (no window to click by mistake).
' Restarts the agent automatically if it stops. Log: agent.log in this folder.
Option Explicit
Dim sh, fso, dir, php
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
php = dir & "\php\php.exe"
If Not fso.FileExists(php) Then php = "C:\xampp\php\php.exe"
If Not fso.FileExists(php) Then php = "php"
sh.CurrentDirectory = dir
Do
  ' 0 = hidden window, True = wait until the agent stops
  sh.Run """" & php & """ """ & dir & "\print-agent.php""", 0, True
  WScript.Sleep 10000
Loop
