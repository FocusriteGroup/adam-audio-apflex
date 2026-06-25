; Inno Setup script for DataTools
; Build with: ISCC DataTools.iss

#define AppName "DataTools"
#ifndef AppVersion
	#define AppVersion "0.1.0"
#endif
#define AppPublisher "ADAM Audio"
#define AppExeName "DataTools.exe"
#define AppRoot "..\\.."
#define DistDir AppRoot + "\\dist\\DataTools"

[Setup]
AppId={{D8A4A668-2E72-45D4-97C0-8A7A9E307A2F}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
OutputDir=.
OutputBaseFilename=DataTools-Setup-{#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
