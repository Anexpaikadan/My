; ============================================================
; DayBill ERP - Windows installer (Inno Setup 6)          v6.0
; ------------------------------------------------------------
; BUILD_EXE.bat builds dist\DayBillERP.exe first, then — when Inno
; Setup 6 is installed (https://jrsoftware.org/isdl.php) — makes
;     dist\DayBillERP_Setup.exe
; One file to give to a shop: it installs DayBill in
; C:\DayBill (not Program Files: DayBill writes its settings next to
; the exe), makes the Desktop + Start menu icons and an uninstaller.
; Settings, database settings and the product key in C:\DayBill\config
; are NEVER removed or overwritten (update = run the new Setup).
; ============================================================
#define AppName "DayBill ERP"
#ifndef AppVersion
  #define AppVersion "7.9.3"
#endif

[Setup]
AppId={{6D3B1C2A-8E4F-4F7B-9B0E-5D1A7B3C6006}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=DayBill
DefaultDirName=C:\DayBill
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=DayBillERP_Setup_{#AppVersion}
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\DayBillERP.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop icon"; GroupDescription: "Icons:"

[Dirs]
Name: "{app}\config"; Flags: uninsneveruninstall
Name: "{app}\logs"
Name: "{app}\backups"; Flags: uninsneveruninstall

[Files]
Source: "..\dist\DayBillERP.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\app.ico"; DestDir: "{app}"; DestName: "DayBillERP.ico"; Flags: ignoreversion
Source: "..\database\INSTALL_DayBillERP_AllInOne.sql"; DestDir: "{app}\database"; Flags: ignoreversion
Source: "..\database\README_DATABASE.txt"; DestDir: "{app}\database"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\database\tools\RESET_user_password.sql"; DestDir: "{app}\database\tools"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\DayBill_Database_Tool.bat"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\DayBillERP.exe"; IconFilename: "{app}\DayBillERP.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\DayBillERP.exe"; IconFilename: "{app}\DayBillERP.ico"; Tasks: desktopicon
Name: "{autoprograms}\DayBill Database Tool"; Filename: "{app}\DayBillERP.exe"; Parameters: "--dbtool"; IconFilename: "{app}\DayBillERP.ico"; Comment: "Reset a password, convert another program's database into DayBill"

[Run]
Filename: "{app}\DayBillERP.exe"; Description: "Start DayBill ERP now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\update_staging"
