[Setup]
AppId={{D37F21F0-8B30-4C9D-9F31-5E2B9A1C8E50}}
AppName=Daily Tasks
#define MyAppVersion "1.4.1"
AppVersion={#MyAppVersion}
AppPublisher=Antigravity
DefaultDirName={autopf}\DailyTasks
DisableProgramGroupPage=yes
DisableWelcomePage=yes
DisableDirPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
OutputDir=E:\Programs\Projects\Code\Daily Tasks\Output
OutputBaseFilename=DailyTasksSetup
LicenseFile=license.txt
CloseApplications=no
Compression=lzma2/ultra64
SolidCompression=yes
LZMADictionarySize=65536
LZMANumFastBytes=273

[Messages]
WizardSelectTasks=Setup Options
SelectTasksDesc=
SelectTasksLabel1=
SelectTasksLabel2=Choose additional actions for this installation:
FinishedHeadingLabel=Installation Complete
FinishedLabel=Daily Tasks is ready to use, Click "Finish" to exit
ClickFinish=

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "E:\Programs\Projects\Code\Daily Tasks\dist\Daily Tasks\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "E:\Programs\Projects\Code\Daily Tasks\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Daily Tasks"; Filename: "{app}\Daily Tasks.exe"; IconFilename: "{app}\icon.ico"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Daily Tasks"; ValueData: """{app}\Daily Tasks.exe"""; Flags: uninsdeletevalue

[Tasks]

Name: "desktopicon"; Description: "Create Desktop Shortcut"; Flags: unchecked
Name: "clean_install_v2"; Description: "Clean Install (Reset all tasks and settings)"; Flags: unchecked dontinheritcheck

[Run]
Filename: "powershell.exe"; Parameters: "-Command ""$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.Environment]::GetFolderPath('Desktop') + '\Daily Tasks.lnk'); $s.TargetPath = '{app}\Daily Tasks.exe'; $s.IconLocation = '{app}\icon.ico'; $s.Save()"""; Flags: nowait skipifsilent runhidden; Tasks: desktopicon
Filename: "{app}\Daily Tasks.exe"; Description: "Launch Daily Tasks"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Daily Tasks.exe"; Flags: nowait skipifnotsilent


[Code]
function InitializeSetup(): Boolean;
var
  UninstPath: String;
  ResultCode: Integer;
begin
  Result := True;
  
  // Kill running app instantly (no waiting)
  Exec('taskkill.exe', '/F /IM "Daily Tasks.exe"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if WizardSilent() then
  begin
    Sleep(350);
  end;
  
  // Check if already installed and offer to uninstall (skip prompt during silent in-app updates)
  if not WizardSilent() then
  begin
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{D37F21F0-8B30-4C9D-9F31-5E2B9A1C8E50}_is1', 'UninstallString', UninstPath) then
    begin
      if MsgBox('Daily Tasks is already installed. Remove the old version first?', mbConfirmation, MB_YESNO) = IDYES then
      begin
        UninstPath := RemoveQuotes(UninstPath);
        Exec(UninstPath, '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
      end;
    end;
  end;
end;

procedure InitializeWizard;
begin
  WizardForm.PageDescriptionLabel.Visible := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDataPath: String;
begin
  if CurStep = ssInstall then
  begin
    if WizardIsTaskSelected('clean_install_v2') then
    begin
      AppDataPath := ExpandConstant('{userappdata}\DailyTasks');
      if DirExists(AppDataPath) then
      begin
        DelTree(AppDataPath, True, True, True);
      end;
    end;
  end;
end;
