; Inno Setup script for KherveCAD — per-user install, no admin rights.
;
; Not run by hand: packaging/build_installer.py freezes the app, drops the
; bundled OpenSCAD into the frozen folder and then calls
;
;   ISCC.exe /DAPP_VERSION=0.1.N /DSRC_DIR=...\dist\KherveCAD /DOUT_DIR=...\dist khervecad.iss
;
; Installs to %LOCALAPPDATA%\Programs\KherveCAD so no elevation prompt is
; needed, associates .kcad, and ships OpenSCAD in an openscad\ subfolder
; (engine.bundled_openscad() looks there first).

#ifndef APP_VERSION
  #define APP_VERSION "0.1.0"
#endif
#ifndef SRC_DIR
  #define SRC_DIR "..\dist\KherveCAD"
#endif
#ifndef OUT_DIR
  #define OUT_DIR "..\dist"
#endif

#define AppName "KherveCAD"
#define AppPublisher "Gwilherm Kerherve"
#define AppURL "https://khervetools.com/tools/khervecad"
#define AppExe "KherveCAD.exe"

[Setup]
AppId={{7A5C2E14-9D3B-4A6F-8C21-3F0B6D8E5A17}
AppName={#AppName}
AppVersion={#APP_VERSION}
AppVerName={#AppName} {#APP_VERSION}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
VersionInfoVersion={#APP_VERSION}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
SetupIconFile=khervecad.ico
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#OUT_DIR}
OutputBaseFilename={#AppName}-Setup-{#APP_VERSION}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; The whole frozen folder, including the bundled openscad\ subfolder and
; its GPL licence text, which build_installer.py has already placed there.
Source: "{#SRC_DIR}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Per-user .kcad association (HKCU — matches the per-user install).
Root: HKCU; Subkey: "Software\Classes\.kcad"; ValueType: string; ValueName: ""; ValueData: "KherveCAD.Document"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\KherveCAD.Document"; ValueType: string; ValueName: ""; ValueData: "KherveCAD document"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\KherveCAD.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"
Root: HKCU; Subkey: "Software\Classes\KherveCAD.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""

[Run]
; Interactive install: the usual "Launch KherveCAD" checkbox on the last page.
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
; Silent install: that is how Help > Check for Updates runs this installer
; (khervecad/updater.py) after closing the app, so bring the new build back
; up. The postinstall entry above is skipped in silent mode and this one is
; skipped in interactive mode, so neither path launches the app twice.
Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Flags: nowait runasoriginaluser; Check: WizardSilent
