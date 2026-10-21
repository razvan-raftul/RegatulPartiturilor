; Program de instalare pentru Regatul Partiturilor (Inno Setup 6)
; Se instalează doar pentru utilizatorul curent, fără drepturi de administrator,
; ca actualizarea automată să poată înlocui fișierele fără întrebări.

#define AppName "Regatul Partiturilor"
#define AppExe "RegatulPartiturilor.exe"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
; NVDA Controller Client (32 de biți, pentru programul de instalare): NVDA spune progresul instalării
#if FileExists(AddBackslash(SourcePath) + "nvdaControllerClient32.dll")
  #define AreVoce
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
#ifdef AreVoce
Source: "nvdaControllerClient32.dll"; Flags: dontcopy
#endif

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
Filename: "{app}\{#AppExe}"; Parameters: "--actualizat"; Flags: nowait; Check: IsAutoUpdate

[Code]
const
  ComponenteURL = 'https://github.com/razvan-raftul/RegatulPartiturilor/releases/download/componente/';

var
  { NVDA spune doar procentul total, din 10 in 10. La actualizarea automata programul a spus deja
    „Se actualizează” si procentele pana la 50 (descarcarea); aici se continua de la 50. }
  UltimulSpus: Integer;
  Inceput: Integer;
  PartiComponente, ParteaCurenta: Integer;

#ifdef AreVoce
function nvdaController_speakText(Text: String): Integer;
  external 'nvdaController_speakText@files:nvdaControllerClient32.dll stdcall delayload';
function nvdaController_testIfRunning: Integer;
  external 'nvdaController_testIfRunning@files:nvdaControllerClient32.dll stdcall delayload';
#endif

{ Spune textul prin NVDA, daca NVDA ruleaza; altfel nu face nimic. }
procedure Spune(const T: String);
begin
#ifdef AreVoce
  try
    if nvdaController_testIfRunning = 0 then
      nvdaController_speakText(T);
  except
    Log('NVDA nu a putut vorbi: ' + GetExceptionMessage);
  end;
#endif
  Log('Spune: ' + T);
end;

{ Spune procentul total (pana la 99), doar cand trece de un nou multiplu de 10. }
procedure SpuneProcent(Procent: Integer);
var
  Zece: Integer;
begin
  if Procent > 99 then Procent := 99;
  Zece := (Procent div 10) * 10;
  if (Zece > UltimulSpus) and (Zece > 0) then
  begin
    UltimulSpus := Zece;
    Spune(Format('%d la sută.', [Zece]));
  end;
end;

function IsAutoUpdate: Boolean;
begin
  Result := Pos('/AUTOUPDATE', Uppercase(GetCmdTail)) > 0;
end;

{ La actualizarea automata programul tocmai se inchide. Asteptam (cel mult 30 de secunde) sa se inchida de tot,
  altfel fisierele lui sunt inca folosite, instalarea fara ferestre renunta si la urmatoarea pornire
  actualizarea o ia de la capat. Programul tine semnul "RegatulPartiturilorRuleaza" cat e deschis. }
function InitializeSetup: Boolean;
var
  I: Integer;
begin
  if IsAutoUpdate then
  begin
    I := 0;
    while CheckForMutexes('RegatulPartiturilorRuleaza') and (I < 60) do
    begin
      Sleep(500);
      I := I + 1;
    end;
    Log(Format('Asteptat inchiderea programului: %d x 0,5 s', [I]));
  end;
  Result := True;
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
  begin
    WizardForm.StatusLabel.Caption := Format('Se descarcă %s: %d din %d MB', [FileName, Integer(Progress div 1048576), Integer(ProgressMax div 1048576)]);
    { componentele ocupa intervalul 80-99, impartit egal intre cele care se descarca }
    if PartiComponente > 0 then
      SpuneProcent(80 + (ParteaCurenta * 20 + Integer((Progress * 20) div ProgressMax)) div PartiComponente);
  end;
  Result := True;
end;

{ Copierea fisierelor programului: de la Inceput pana la 80. }
procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  if MaxProgress > 0 then
    SpuneProcent(Inceput + Integer((Int64(CurProgress) * (80 - Inceput)) div MaxProgress));
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
    ParteaCurenta := ParteaCurenta + 1;
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
  ParteaCurenta := ParteaCurenta + 1;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if IsAutoUpdate then
      Inceput := 50
    else
    begin
      Inceput := 0;
      Spune('Se instalează.');
    end;
    UltimulSpus := Inceput;
  end;
  if CurStep = ssPostInstall then
  begin
    SpuneProcent(80);
    PartiComponente := 0;
    ParteaCurenta := 0;
    if TrebuieComponenta('homr') then PartiComponente := PartiComponente + 1;
    if TrebuieComponenta('Audiveris') then PartiComponente := PartiComponente + 1;
    if TrebuieComponenta('MuseScore') then PartiComponente := PartiComponente + 1;
    InstaleazaComponenta('homr', 'homr (recunoașterea partiturilor din PDF, primul program)');
    InstaleazaComponenta('Audiveris', 'Audiveris (recunoașterea partiturilor din PDF, al doilea program)');
    InstaleazaComponenta('MuseScore', 'MuseScore (fișierele .mscz)');
  end;
  { la actualizarea automata, programul redeschis spune „100 la sută. Actualizare terminată.” }
  if (CurStep = ssDone) and not IsAutoUpdate then
    Spune('100 la sută. Instalare terminată.');
end;
