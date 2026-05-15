[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=KeyOCR
AppVersion=1.0
AppPublisher=KeyOCR
DefaultDirName=D:\KeyOCR
DefaultGroupName=KeyOCR
OutputBaseFilename=KeyOCR_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=../assets/icon.ico
UninstallDisplayIcon={app}\KeyOCR.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："

[Files]
Source: "..\dist\KeyOCR.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "../assets/icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\cache"; Permissions: users-modify

[Icons]
Name: "{group}\KeyOCR"; Filename: "{app}\KeyOCR.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\卸载KeyOCR"; Filename: "{uninstallexe}"
Name: "{autodesktop}\KeyOCR"; Filename: "{app}\KeyOCR.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\KeyOCR.exe"; Description: "启动KeyOCR"; Flags: nowait postinstall skipifsilent
