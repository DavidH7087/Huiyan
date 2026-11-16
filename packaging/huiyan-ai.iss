#define MyAppName "慧眼"
#define MyAppVersion "0.9.5-preview"
#define MyAppExe "Huiyan.exe"

[Setup]
AppId={{1A2CD64B-2AD9-421C-8259-5D7EBAEC2CE5}
AppName={#MyAppName}
AppVerName={#MyAppName} {#MyAppVersion}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Huiyan
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExe}
OutputDir=..\dist\installer
OutputBaseFilename=Huiyan-Setup-0.9.0-AI-preview
Compression=zip
SolidCompression=no
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes

[Tasks]
Name: desktopicon; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked

[Files]
Source: "..\dist\Huiyan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\慧眼"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\慧眼"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "启动慧眼"; Flags: nowait postinstall skipifsilent
