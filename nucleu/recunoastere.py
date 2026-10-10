"""Partituri care nu sunt deja în format digital:
- PDF și imagini: recunoaștere optică cu Audiveris (program gratuit, se instalează separat);
- fișiere MuseScore (.mscz): conversie în MusicXML cu MuseScore, dacă e instalat.
"""
import glob
import os
import shutil
import subprocess
import tempfile

SETARI = {'audiveris': '', 'musescore': ''}   # căi alese manual (le completează fereastra din setări)

_PF = [os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
       os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')]


class LipsaProgram(Exception):
    """Lipsește programul extern; mesajul spune ce trebuie instalat."""


def _primul(cai):
    for c in cai:
        for g in glob.glob(c):
            if os.path.isfile(g):
                return g
    return None


def gaseste_audiveris():
    if SETARI['audiveris'] and os.path.isfile(SETARI['audiveris']):
        return SETARI['audiveris']
    cai = []
    for pf in _PF:
        cai += [os.path.join(pf, 'Audiveris', 'Audiveris.exe'), os.path.join(pf, 'Audiveris*', 'Audiveris.exe'),
                os.path.join(pf, 'Audiveris', 'bin', 'Audiveris.bat')]
    return _primul(cai) or shutil.which('Audiveris') or shutil.which('audiveris')


def gaseste_musescore():
    if SETARI['musescore'] and os.path.isfile(SETARI['musescore']):
        return SETARI['musescore']
    cai = []
    for pf in _PF:
        cai += [os.path.join(pf, 'MuseScore 4', 'bin', 'MuseScore4.exe'), os.path.join(pf, 'MuseScore 3', 'bin', 'MuseScore3.exe'),
                os.path.join(pf, 'MuseScore*', 'bin', 'MuseScore*.exe')]
    return _primul(cai) or shutil.which('mscore') or shutil.which('MuseScore4')


def _ruleaza(cmd, timeout):
    flags = 0x08000000 if os.name == 'nt' else 0   # fără fereastră neagră de consolă
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags)


def din_musescore(cale: str) -> str:
    exe = gaseste_musescore()
    if not exe:
        raise LipsaProgram('Pentru fișierele MuseScore trebuie instalat MuseScore (gratuit, de pe musescore.org). '
                           'Sau exportă partitura din MuseScore ca MusicXML și deschide fișierul acela.')
    out = os.path.join(tempfile.mkdtemp(prefix='regatul-partiturilor-'), 'partitura.musicxml')
    r = _ruleaza([exe, '-o', out, cale], 300)
    if not os.path.isfile(out):
        raise LipsaProgram('MuseScore nu a putut converti fișierul. ' + (r.stderr or '')[-300:])
    return out


def din_imagine(cale: str, progres=None) -> list:
    """Rulează Audiveris și întoarce lista fișierelor MXL obținute."""
    exe = gaseste_audiveris()
    if not exe:
        raise LipsaProgram('Pentru PDF-uri și poze trebuie instalat Audiveris, programul gratuit de recunoaștere a partiturilor '
                           '(de pe github.com/Audiveris/audiveris, secțiunea Releases, fișierul pentru Windows). '
                           'După instalare, deschide din nou partitura.')
    dest = os.path.join(os.path.dirname(os.path.abspath(cale)), 'Recunoscute')
    os.makedirs(dest, exist_ok=True)
    baza = os.path.splitext(os.path.basename(cale))[0]
    if progres:
        progres('Recunosc partitura. Poate dura câteva minute pentru fiecare pagină.')
    r = _ruleaza([exe, '-batch', '-export', '-output', dest, '--', cale], 3600)
    gasite = sorted(glob.glob(os.path.join(dest, baza + '*.mxl')) + glob.glob(os.path.join(dest, baza, baza + '*.mxl')),
                    key=os.path.getmtime, reverse=True)
    if not gasite:
        raise LipsaProgram('Audiveris nu a reușit să recunoască partitura. Încearcă un PDF mai clar sau o scanare la 300 dpi. '
                           + (r.stdout or '')[-300:])
    gasite.sort()
    return gasite
