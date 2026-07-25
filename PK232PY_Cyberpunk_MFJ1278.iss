#define MyAppName "PK232PY Cyberpunk MFJ-1278"
#define MyAppVersion "0.1.0-beta-cyberpunk"
#define MyAppPublisher "OE3GAS / Cyberpunk Windows skin"
#define MyAppExeName "pk232py.exe"

[Setup]
AppId={{D96B78CE-A8BE-4EA5-A056-2DD83BCBB43F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PK232PY Cyberpunk MFJ-1278
DefaultGroupName=PK232PY Cyberpunk MFJ-1278
PrivilegesRequired=admin
OutputDir=installer
OutputBaseFilename=PK232PY_Cyberpunk_MFJ1278_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=pk232py.ico

[Files]
Source: "dist\pk232py.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\PK232PY Cyberpunk MFJ-1278"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PK232PY Cyberpunk MFJ-1278"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PK232PY Cyberpunk MFJ-1278"; Flags: nowait postinstall skipifsilent
