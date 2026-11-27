; Serapi 安装脚本（Inno Setup 6）
; 先执行：pyinstaller --noconfirm Serapi.spec
; 再编译：ISCC.exe /DMyAppVersion=1.0.0 installer\Serapi.iss

#ifndef MyAppVersion
  #define MyAppVersion "dev"
#endif

#ifndef MyAppOwner
  #define MyAppOwner "Mameko230"
#endif

[Setup]
AppId={{8E3B2C1A-5D4F-4A7E-9C1B-2F6D3A8B7C10}
AppName=Serapi
AppVersion={#MyAppVersion}
AppPublisher=Serapi contributors
AppPublisherURL=https://github.com/{#MyAppOwner}
DefaultDirName={autopf}\Serapi
DefaultGroupName=Serapi
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Serapi-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\Serapi.exe
ArchitecturesInstallIn64BitMode=x64compatible

[Types]
Name: "full"; Description: "完整安装（含可选词典）"
Name: "custom"; Description: "自定义安装"; Flags: iscustom

[Components]
Name: "dicts"; Description: "日语词典（StarDict，约 42 MB，可选）"; Types: full

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "..\dist\Serapi\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "..\dictionaries\THIRD_PARTY_NOTICES.md"; DestDir: "{app}\dictionaries"; Components: dicts; Flags: ignoreversion
Source: "..\dictionaries\ja-ja\*"; DestDir: "{app}\dictionaries\ja-ja"; Components: dicts; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\dictionaries\ja-zh\*"; DestDir: "{app}\dictionaries\ja-zh"; Components: dicts; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\dictionaries\zh-ja\*"; DestDir: "{app}\dictionaries\zh-ja"; Components: dicts; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Serapi"; Filename: "{app}\Serapi.exe"
Name: "{autodesktop}\Serapi"; Filename: "{app}\Serapi.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Serapi.exe"; Description: "立即运行 Serapi"; Flags: nowait postinstall skipifsilent
