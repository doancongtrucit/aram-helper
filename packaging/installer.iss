; Bộ cài Windows (Inno Setup 6). Không cần quyền admin: cài cho người dùng hiện tại.
; Build: python tools/build.py   (tự gọi ISCC với AppVersion / SourceDir / OutDir)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\ARAM Helper"
#endif
#ifndef OutDir
  #define OutDir "..\dist"
#endif

[Setup]
AppId={{6B1F3C2E-8E4A-4C1B-9A57-2D0C7E5A9F31}
AppName=ARAM Helper
AppVersion={#AppVersion}
AppVerName=ARAM Helper {#AppVersion}
AppPublisher=doancongtrucit
AppContact=doancongtrucit@gmail.com
AppCopyright=© 2026 doancongtrucit. All rights reserved.
LicenseFile=..\LICENSE
AppPublisherURL=https://github.com/doancongtrucit/aram-helper
AppSupportURL=https://github.com/doancongtrucit/aram-helper/issues
AppUpdatesURL=https://github.com/doancongtrucit/aram-helper/releases
DefaultDirName={localappdata}\Programs\ARAM Helper
DefaultGroupName=ARAM Helper
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutDir}
OutputBaseFilename=ARAM-Helper-{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\ARAM Helper.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Cài bản mới khi app đang chạy: đóng app trước rồi mở lại sau khi cài
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
en.DesktopIcon=Tạo biểu tượng ngoài Desktop
en.StartWithWindows=Mở ARAM Helper khi khởi động Windows
en.LaunchNow=Mở ARAM Helper
en.DeleteData=Xoá cả dữ liệu của ARAM Helper (cache, hiệu chỉnh, cài đặt)?%n%nChọn No nếu bạn sẽ cài lại.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"
Name: "startup"; Description: "{cm:StartWithWindows}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; bản cũ có thể còn file thư viện không dùng nữa
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\ARAM Helper"; Filename: "{app}\ARAM Helper.exe"
Name: "{autodesktop}\ARAM Helper"; Filename: "{app}\ARAM Helper.exe"; Tasks: desktopicon
Name: "{userstartup}\ARAM Helper"; Filename: "{app}\ARAM Helper.exe"; Tasks: startup

[Run]
Filename: "{app}\ARAM Helper.exe"; Description: "{cm:LaunchNow}"; Flags: nowait postinstall skipifsilent
; Tự cập nhật trong app: cài im lặng với /RELAUNCH=1 → mở lại app sau khi cài xong.
; GIỮ NGUYÊN tham số /RELAUNCH=1, tên ARAM-Helper-Setup.exe và SHA256SUMS.txt: mọi bản >= 1.7.0 đang cài dựa vào chúng.
Filename: "{app}\ARAM Helper.exe"; Flags: nowait; Check: RelaunchRequested

[Code]
function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\ARAM Helper');
    if DirExists(DataDir) and (not UninstallSilent) then
      if MsgBox(CustomMessage('DeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
