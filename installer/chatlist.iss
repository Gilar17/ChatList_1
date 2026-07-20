; Автоматически сгенерировано build_installer.py из version.py

#define MyAppName "ChatList"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "ChatList"
#define MyAppExeName "ChatList.exe"

[Setup]
AppId={{8F4E2A61-9C3D-4B17-A6E5-1D9F7C842B10}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
OutputDir=..\install
OutputBaseFilename=ChatList-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=C:\Work\ChatList_1\app.ico
UninstallDisplayIcon={app}\ChatList.exe
UninstallDisplayName={#MyAppName} {#MyAppVersion}
CreateUninstallRegKey=yes
Uninstallable=yes
VersionInfoVersion=1.0.1.0
VersionInfoProductVersion=1.0.1.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Установщик {#MyAppName}
VersionInfoProductName={#MyAppName}
VersionInfoProductTextVersion={#MyAppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "..\dist\ChatList.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "ChatList {#MyAppVersion}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "ChatList {#MyAppVersion}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
