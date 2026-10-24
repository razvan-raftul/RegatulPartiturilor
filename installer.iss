; Program de instalare pentru Music Box (fostul Regatul Partiturilor) (Inno Setup 6)
; Se instalează doar pentru utilizatorul curent, fără drepturi de administrator,
; ca actualizarea automată să poată înlocui fișierele fără întrebări.

#define AppName "Music Box"
; numele vechi: scurtăturile cu el se șterg la actualizare
#define NumeVechi "Regatul Partiturilor"
#define AppExe "MusicBox.exe"
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
; mereu în folderul „Music Box”; folderul vechi „Regatul Partiturilor” se mută aici (vezi MutaFolderulVechi)
UsePreviousAppDir=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=.
OutputBaseFilename=MusicBox-Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
#if FileExists(AddBackslash(SourcePath) + "Romanian.isl")
Name: "ro"; MessagesFile: "Romanian.isl"
#endif

[CustomMessages]
en.ScurtaturaDesktop=Create a desktop shortcut
en.Scurtaturi=Shortcuts:
ro.ScurtaturaDesktop=Pune o scurtătură pe desktop
ro.Scurtaturi=Scurtături:

[Tasks]
Name: "desktopicon"; Description: "{cm:ScurtaturaDesktop}"; GroupDescription: "{cm:Scurtaturi}"

[Files]
Source: "dist\MusicBox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Exemple\*"; DestDir: "{userdocs}\{#AppName}\Exemple"; Flags: onlyifdoesntexist
Source: "componente.txt"; DestDir: "{app}"; Flags: ignoreversion
#ifdef AreVoce
Source: "nvdaControllerClient32.dll"; Flags: dontcopy
#endif

[InstallDelete]
; la actualizare se șterg fișierele vechi ale programului, ca să nu rămână biblioteci depășite
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{autoprograms}\{#NumeVechi}.lnk"
Type: files; Name: "{autodesktop}\{#NumeVechi}.lnk"
; programul se numea RegatulPartiturilor.exe; acum e MusicBox.exe
Type: files; Name: "{app}\RegatulPartiturilor.exe"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\componente"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Music Box"; Flags: nowait postinstall skipifsilent
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

{ Limba programului, din setari.json (cheia "limba"). Setari fara limba: engleza (implicita programului).
  Fara setari (prima instalare): limba programului de instalare. }
function LimbaProgram: String;
var
  S: AnsiString;
  T: String;
begin
  if LoadStringFromFile(ExpandConstant('{userappdata}\Music Box\setari.json'), S) or
     LoadStringFromFile(ExpandConstant('{userappdata}\Regatul Partiturilor\setari.json'), S) then
  begin
    T := String(S);
    Result := 'en';
    if Pos('"limba": "ro"', T) > 0 then Result := 'ro'
    else if Pos('"limba": "fr"', T) > 0 then Result := 'fr'
    else if Pos('"limba": "de"', T) > 0 then Result := 'de'
    else if Pos('"limba": "es"', T) > 0 then Result := 'es'
    else if Pos('"limba": "it"', T) > 0 then Result := 'it';
  end
  else if ActiveLanguage = 'ro' then
    Result := 'ro'
  else
    Result := 'en';
end;

function TextLimba(const En, Ro, Fr, De, Es, It: String): String;
var
  L: String;
begin
  L := LimbaProgram;
  if L = 'ro' then Result := Ro
  else if L = 'fr' then Result := Fr
  else if L = 'de' then Result := De
  else if L = 'es' then Result := Es
  else if L = 'it' then Result := It
  else Result := En;
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
    Spune(Format(TextLimba('%d percent.', '%d la sută.', '%d pour cent.', '%d Prozent.', '%d por ciento.', '%d per cento.'), [Zece]));
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

{ Programul stătea în folderul „Regatul Partiturilor”. Componentele (homr, Audiveris, MuseScore, sute de MB)
  se mută în folderul nou, ca să nu se descarce din nou; la final folderul vechi se șterge. }
procedure MutaFolderulVechi;
var
  Vechi, Nou: String;
begin
  Vechi := ExpandConstant('{autopf}\{#NumeVechi}');
  Nou := ExpandConstant('{app}');
  if (CompareText(Vechi, Nou) <> 0) and DirExists(Vechi + '\componente') and not DirExists(Nou + '\componente') then
  begin
    ForceDirectories(Nou);
    if not RenameFile(Vechi + '\componente', Nou + '\componente') then
      Log('Componentele nu s-au putut muta din folderul vechi.');
  end;
end;

procedure StergeFolderulVechi;
var
  Vechi: String;
begin
  Vechi := ExpandConstant('{autopf}\{#NumeVechi}');
  if (CompareText(Vechi, ExpandConstant('{app}')) <> 0) and DirExists(Vechi) then
    DelTree(Vechi, True, True, True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    MutaFolderulVechi;
    if IsAutoUpdate then
      Inceput := 50
    else
    begin
      Inceput := 0;
      Spune(TextLimba('Installing.', 'Se instalează.', 'Installation.', 'Wird installiert.', 'Instalando.', 'Installazione in corso.'));
    end;
    UltimulSpus := Inceput;
  end;
  if CurStep = ssPostInstall then
  begin
    StergeFolderulVechi;
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
    Spune(TextLimba('100 percent. Installation complete.', '100 la sută. Instalare terminată.', '100 pour cent. Installation terminée.',
                    '100 Prozent. Installation abgeschlossen.', '100 por ciento. Instalación terminada.', '100 per cento. Installazione completata.'));
end;
