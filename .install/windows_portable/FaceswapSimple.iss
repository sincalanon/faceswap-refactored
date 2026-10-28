; Faceswap 简易版 Windows 安装程序（Inno Setup 6）
; 由 .github/workflows/build-windows.yml 调用：ISCC /DAppVersion=x /DSourceDir=... /DOutputDir=...
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F1E2C3A-9B7D-4E21-A5C8-3D2F7B9E4A10}
AppName=Faceswap 简易版
AppVersion={#AppVersion}
AppVerName=Faceswap 简易版 {#AppVersion}（NVIDIA）
AppPublisher=sincalanon
AppPublisherURL=https://github.com/sincalanon/faceswap-refactored
DefaultDirName={sd}\FaceswapSimple
DefaultGroupName=Faceswap 简易版
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=FaceswapSimple-Setup
Compression=lzma2/fast
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
DiskSpanning=yes
DiskSliceSize=1900000000
UninstallDisplayName=Faceswap 简易版
UninstallDisplayIcon={app}\FaceswapSimple.exe
LicenseFile={#SourceDir}\faceswap\LICENSE
InfoBeforeFile={#SourceDir}\使用教程.txt
WizardStyle=modern

[Languages]
Name: "chs"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Faceswap 简易版"; Filename: "{app}\FaceswapSimple.exe"; WorkingDir: "{app}"
Name: "{group}\使用教程"; Filename: "{app}\使用教程.txt"
Name: "{group}\卸载 Faceswap 简易版"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Faceswap 简易版"; Filename: "{app}\FaceswapSimple.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\FaceswapSimple.exe"; Description: "立即启动 Faceswap 简易版"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\faceswap\.fs_cache"
Type: filesandordirs; Name: "{app}\faceswap\config"
Type: files; Name: "{app}\faceswap\training_preview.png"
Type: filesandordirs; Name: "{app}\python"

[Code]
function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Dir := Lowercase(WizardDirValue);
    if (Pos(Lowercase(ExpandConstant('{commonpf}')), Dir) = 1) or
       (Pos(Lowercase(ExpandConstant('{commonpf32}')), Dir) = 1) then
    begin
      MsgBox('请不要安装到 Program Files 目录：程序需要在安装目录里写入配置和训练预览。'#13#10 +
             '建议使用 C:\FaceswapSimple 或 D:\FaceswapSimple。', mbError, MB_OK);
      Result := False;
    end;
  end;
end;
