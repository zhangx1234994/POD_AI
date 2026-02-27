#define AppName "PODI ComfyUI 代理服务"
#define AppVersion "0.1.0"
#define AppPublisher "PODI"
#define AppExeName "podi-agent-gui.exe"

#ifndef CenterUrl
  #define CenterUrl "http://117.50.80.158:8099"
#endif

#ifndef InstallKey
  #define InstallKey ""
#endif

[Setup]
AppId={{8D9F04C7-9604-4D39-8F56-7D174B973880}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\PodiComfyuiAgent
DefaultGroupName={#AppName}
Compression=lzma
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=PODI-ComfyUI-Agent-Setup
PrivilegesRequired=admin

[Files]
Source: "podi-agent-server.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "podi-agent-gui.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_windows.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "uninstall_windows.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\installer\install_windows.ps1"" -InstallRoot ""{app}"" -CenterUrl ""{#CenterUrl}"" -InstallKey ""{#InstallKey}"" -SkipCopy"; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExeName}"; Description: "打开代理服务控制台"; Flags: postinstall nowait

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\installer\uninstall_windows.ps1"" -InstallRoot ""{app}"""; Flags: runhidden waituntilterminated
