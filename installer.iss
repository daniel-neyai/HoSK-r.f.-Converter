[Setup]
AppName=HoSK r.f. Bank Statement Converter
AppVersion=2.0
DefaultDirName={autopf}\HoSK Converter
DefaultGroupName=HoSK Converter
OutputDir=output
OutputBaseFilename=HoSK_Converter_Installer

[Files]
Source: "dist\main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\camt.053.001.02.xsd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\HoSK Converter"; Filename: "{app}\main.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,HoSK Converter}"; Flags: nowait postinstall