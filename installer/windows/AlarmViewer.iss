#define MyAppName "Alarm Viewer"
#define MyAppVersion "0.1.5"
#define MyAppPublisher "Orange"
#define MyAppExeName "AlarmViewer.exe"

[Setup]
AppId={{CCFB4C66-84C4-4A11-9CE2-3D9A48D9502C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Alarm Viewer
DefaultGroupName=Alarm Viewer
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=AlarmViewer-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\AlarmViewer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Alarm Viewer"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Alarm Viewer"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Alarm Viewer"; Flags: nowait postinstall skipifsilent
