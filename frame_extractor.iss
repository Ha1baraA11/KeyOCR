[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=帧提取工具
AppVersion=1.0
AppPublisher=ZhenTiqu
DefaultDirName={autopf}\帧提取工具
DefaultGroupName=帧提取工具
OutputBaseFilename=帧提取工具_安装程序
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\帧提取工具.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："

[Files]
Source: "dist\帧提取工具.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\帧提取工具"; Filename: "{app}\帧提取工具.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\卸载帧提取工具"; Filename: "{uninstallexe}"
Name: "{autodesktop}\帧提取工具"; Filename: "{app}\帧提取工具.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\帧提取工具.exe"; Description: "启动帧提取工具"; Flags: nowait postinstall skipifsilent
