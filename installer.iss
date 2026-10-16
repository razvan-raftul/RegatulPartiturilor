; Program de instalare pentru Regatul Partiturilor (Inno Setup 6)
; Se instalează doar pentru utilizatorul curent, fără drepturi de administrator,
; ca actualizarea automată să poată înlocui fișierele fără întrebări.

#define AppName "Regatul Partiturilor"
#define AppExe "RegatulPartiturilor.exe"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{3F8B2C71-9A4E-4D5B-8E2F-7C1A6B9D0E53}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Răzvan
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=.
OutputBaseFilename=RegatulPartiturilor-Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
CloseApplications=yes

[Languages]
#if FileExists(AddBackslash(SourcePath) + "Romanian.isl")
Name: "ro"; MessagesFile: "Romanian.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "Pune o scurtătură pe desktop"; GroupDescription: "Scurtături:"

[Files]
Source: "dist\RegatulPartiturilor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Exemple\*"; DestDir: "{userdocs}\{#AppName}\Exemple"; Flags: onlyifdoesntexist
Source: "componente.txt"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; la actualizare se șterg fișierele vechi ale programului, ca să nu rămână biblioteci depășite
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\componente"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Pornește Regatul Partiturilor acum"; Flags: nowait postinstall skipifsilent
; la actualizarea automată (instalare fără ferestre) aplicația se redeschide singură
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: IsAutoUpdate

[Code]
const
  ComponenteURL = 'https://github.com/razvan-raftul/RegatulPartiturilor/releases/download/componente/';

function IsAutoUpdate: Boolean;
begin
  Result := Pos('/AUTOUPDATE', Uppercase(GetCmdTail)) > 0;
end;

{ Versiunea dorita a unei componente, din componente.txt (linia "Nume = link"). }
function VersiuneDorita(const Nume: String): String;
var
  L: TArrayOfString;
  I, P: Integer;
  S: String;
begin
  Result := '';
  if LoadStringsFromFile(ExpandConstant('{app}\componente.txt'), L) then
    for I := 0 to GetArrayLength(L) - 1 do
    begin
      S := Trim(L[I]);
      P := Pos('=', S);
      if (P > 0) and (CompareText(Trim(Copy(S, 1, P - 1)), Nume) = 0) then
        Result := Trim(Copy(S, P + 1, Length(S)));
    end;
end;

{ Adevarat daca componenta lipseste sau e de alta versiune. }
function TrebuieComponenta(const Nume: String): Boolean;
var
  V: AnsiString;
begin
  Result := True;
  if LoadStringFromFile(ExpandConstant('{app}\componente\' + Nume + '\versiune.txt'), V) then
    Result := Trim(String(V)) <> VersiuneDorita(Nume);
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if ProgressMax > 0 then
    WizardForm.StatusLabel.Caption := Format('Se descarcă %s: %d din %d MB', [FileName, Integer(Progress div 1048576), Integer(ProgressMax div 1048576)]);
  Result := True;
end;

procedure InstaleazaComponenta(const Nume, Descriere: String);
var
  Zip, Dest: String;
  Cod: Integer;
begin
  if not TrebuieComponenta(Nume) then exit;
  WizardForm.StatusLabel.Caption := 'Se descarcă ' + Descriere + '...';
  try
    DownloadTemporaryFile(ComponenteURL + Nume + '.zip', Nume + '.zip', '', @OnDownloadProgress);
  except
    Log('Descarcarea a esuat: ' + GetExceptionMessage);
    if not WizardSilent then
      MsgBox('Nu am putut descărca ' + Descriere + '. Programul merge și fără, dar pentru asta trebuie internet. Instalează din nou mai târziu.', mbError, MB_OK);
    exit;
  end;
  Zip := ExpandConstant('{tmp}\' + Nume + '.zip');
  Dest := ExpandConstant('{app}\componente\' + Nume);
  DelTree(Dest, True, True, True);
  ForceDirectories(Dest);
  WizardForm.StatusLabel.Caption := 'Se despachetează ' + Descriere + '...';
  if not Exec(ExpandConstant('{sys}\tar.exe'), '-xf "' + Zip + '" -C "' + Dest + '"', '', SW_HIDE, ewWaitUntilTerminated, Cod) or (Cod <> 0) then
    Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath ''' + Zip + ''' -DestinationPath ''' + Dest + ''' -Force"', '', SW_HIDE, ewWaitUntilTerminated, Cod);
  DeleteFile(Zip);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    InstaleazaComponenta('homr', 'homr (recunoașterea partiturilor din PDF, primul program)');
    InstaleazaComponenta('Audiveris', 'Audiveris (recunoașterea partiturilor din PDF, al doilea program)');
    InstaleazaComponenta('MuseScore', 'MuseScore (fișierele .mscz)');
  end;
end;
