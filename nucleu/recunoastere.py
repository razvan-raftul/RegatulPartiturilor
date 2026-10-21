"""Partituri care nu sunt deja în format digital:
- PDF și imagini: recunoaștere optică cu homr și Audiveris, comparate măsură cu măsură (verificare.py);
- fișiere MuseScore (.mscz): conversie în MusicXML cu MuseScore.
Toate vin odată cu programul de instalare, în folderul „componente” de lângă program.
Dacă lipsesc de acolo, se caută și în Program Files (dacă Răzvan le-a instalat separat).
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass

from . import verificare
from .limba import _

SETARI = {'audiveris': '', 'musescore': '', 'homr': ''}   # căi alese manual (le completează fereastra din setări)

_PF = [os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
       os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')]


def _componente():
    """Folderul „componente” de lângă program (unde le pune programul de instalare)."""
    if getattr(sys, 'frozen', False):
        baza = os.path.dirname(sys.executable)
    else:
        baza = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(baza, 'componente')


def _din_componente(nume, *exe):
    radacina = os.path.join(_componente(), nume)
    if not os.path.isdir(radacina):
        return None
    for e in exe:
        gasite = sorted(glob.glob(os.path.join(radacina, '**', e), recursive=True), key=len)
        if gasite:
            return gasite[0]
    return None


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
    c = _din_componente('Audiveris', 'Audiveris.exe')
    if c:
        return c
    cai = []
    for pf in _PF:
        cai += [os.path.join(pf, 'Audiveris', 'Audiveris.exe'), os.path.join(pf, 'Audiveris*', 'Audiveris.exe'),
                os.path.join(pf, 'Audiveris', 'bin', 'Audiveris.bat')]
    return _primul(cai) or shutil.which('Audiveris') or shutil.which('audiveris')


def gaseste_musescore():
    if SETARI['musescore'] and os.path.isfile(SETARI['musescore']):
        return SETARI['musescore']
    c = _din_componente('MuseScore', 'MuseScore4.exe', 'MuseScore*.exe')
    if c:
        return c
    cai = []
    for pf in _PF:
        cai += [os.path.join(pf, 'MuseScore 4', 'bin', 'MuseScore4.exe'), os.path.join(pf, 'MuseScore 3', 'bin', 'MuseScore3.exe'),
                os.path.join(pf, 'MuseScore*', 'bin', 'MuseScore*.exe')]
    return _primul(cai) or shutil.which('mscore') or shutil.which('MuseScore4')


def _ruleaza(cmd, timeout, env=None):
    flags = 0x08000000 if os.name == 'nt' else 0   # fără fereastră neagră de consolă
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags, env=env,
                          encoding='utf-8', errors='replace')


def din_musescore(cale: str) -> str:
    exe = gaseste_musescore()
    if not exe:
        raise LipsaProgram(_('Nu găsesc MuseScore, de care e nevoie pentru fișierele .mscz. De obicei vine odată cu programul; '
                           'reinstalează Music Box cu internetul pornit, sau alege MuseScore din fila Setări.'))
    out = os.path.join(tempfile.mkdtemp(prefix='regatul-partiturilor-'), 'partitura.musicxml')
    r = _ruleaza([exe, '-o', out, cale], 300)
    if not os.path.isfile(out):
        raise LipsaProgram(_('MuseScore nu a putut converti fișierul. ') + (r.stderr or '')[-300:])
    return out


def gaseste_homr():
    if SETARI.get('homr') and os.path.isfile(SETARI['homr']):
        return SETARI['homr']
    return _din_componente('homr', 'homr.exe') or shutil.which('homr')


def folder_rezultate(cale_sursa: str) -> str:
    """Tot ce face programul pentru un PDF (cuprins, piese recunoscute, Braille) stă în
    Recunoscute\\<numele PDF-ului>, lângă PDF, ca folderul cu PDF-uri să rămână curat."""
    d = os.path.dirname(os.path.abspath(cale_sursa))
    return os.path.join(d, 'Recunoscute', os.path.splitext(os.path.basename(cale_sursa))[0])


def nume_scurt(baza: str, cale_sursa: str) -> str:
    """În folderul cărții, piesele se numesc scurt („Studiul 13”), fără numele cărții în față."""
    carte = os.path.splitext(os.path.basename(cale_sursa))[0]
    return baza[len(carte) + 3:] if baza.startswith(carte + ' - ') and len(baza) > len(carte) + 3 else baza


@dataclass
class Recunoastere:
    scor: object                       # partitura finală (music21)
    nesigure: dict                     # {număr măsură: motiv}
    programe: list                     # programele care au reușit
    probleme: list                     # mesaje despre programele care n-au mers
    fisier: str = ''                   # unde s-a salvat rezultatul (gol dacă nu se păstrează)


def _audiveris(exe, cale, dest):
    baza = os.path.splitext(os.path.basename(cale))[0]
    env = None
    tess = os.path.join(os.path.dirname(exe), 'tessdata')
    if os.path.isdir(tess):          # limbile pentru text (Allegro, titluri), aduse odată cu Audiveris
        env = dict(os.environ, TESSDATA_PREFIX=tess)
    r = _ruleaza([exe, '-batch', '-export', '-output', dest, '--', cale], 3600, env=env)
    gasite = sorted(glob.glob(os.path.join(dest, baza + '*.mxl')) + glob.glob(os.path.join(dest, baza, baza + '*.mxl')))
    if not gasite:
        raise RuntimeError(_('Audiveris nu a recunoscut nimic. ') + (r.stdout or '')[-200:])
    from music21 import converter
    return verificare.uneste_pagini([converter.parse(f) for f in gasite])


def _homr(exe, cale, lucru):
    # homr scrie pozele paginilor lângă fișier, așa că lucrează pe o copie, într-un folder temporar
    d = tempfile.mkdtemp(prefix='homr-', dir=lucru)
    copie = os.path.join(d, 'pagina' + os.path.splitext(cale)[1].lower())
    shutil.copyfile(cale, copie)
    r = _ruleaza([exe, '--no-title', copie], 3600)
    gasite = sorted(glob.glob(os.path.join(d, '*.musicxml')))
    if not gasite:
        raise RuntimeError(_('homr nu a recunoscut nimic. ') + (r.stderr or '')[-200:])
    from music21 import converter
    return verificare.uneste_pagini([converter.parse(f) for f in gasite])


def din_imagine(cale: str, progres=None, pastreaza=True, baza=None, folder=None, original=None) -> Recunoastere:
    """Recunoaște un PDF sau o poză cu două programe (homr și Audiveris), le compară măsură cu măsură
    și întoarce partitura combinată, cu măsurile nesigure.
    pastreaza=False: nu rămâne nimic pe disc (pentru paginile citite din aplicațiile editurilor)."""
    from music21 import converter
    # baza/folder: când recunoaștem doar o piesă dintr-o carte, `cale` e un PDF temporar cu paginile ei,
    # iar rezultatul se salvează lângă carte, cu numele piesei
    baza = baza or os.path.splitext(os.path.basename(cale))[0]
    sursa = original or cale
    dest = folder_rezultate(sursa)
    scurt = nume_scurt(baza, sursa)
    final = os.path.join(dest, scurt + ' - verificat.musicxml')
    raport = os.path.join(dest, scurt + ' - de verificat.txt')
    # locul vechi (versiunile de dinainte de 16 oct. 2026): direct în Recunoscute, cu numele întreg
    vechi = os.path.join(folder or os.path.dirname(os.path.abspath(sursa)), 'Recunoscute')
    if pastreaza and not os.path.isfile(final) and os.path.isfile(os.path.join(vechi, baza + ' - verificat.musicxml')):
        try:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(os.path.join(vechi, baza + ' - verificat.musicxml'), final)
            if os.path.isfile(os.path.join(vechi, baza + ' - de verificat.txt')):
                shutil.copy2(os.path.join(vechi, baza + ' - de verificat.txt'), raport)
        except OSError:
            pass
    # recunoscută deja și PDF-ul nu s-a schimbat: nu mai așteptăm minute întregi
    if pastreaza and os.path.isfile(final) and os.path.getmtime(final) >= os.path.getmtime(original or cale):
        try:
            nes = _citeste_raport(raport)
            sc = converter.parse(final)
            _metadate(sc, baza)
            return Recunoastere(sc, nes, [], [], final)
        except Exception:
            pass
    motoare = [('homr', gaseste_homr(), _homr), ('Audiveris', gaseste_audiveris(), _audiveris)]
    motoare = [m for m in motoare if m[1]]
    if not motoare:
        raise LipsaProgram(_('Nu găsesc programele de recunoaștere (homr și Audiveris). De obicei vin odată cu programul; '
                           'reinstalează Music Box cu internetul pornit.'))
    lucru = tempfile.mkdtemp(prefix='regatul-partiturilor-')
    if progres:
        progres(_('Recunosc partitura cu {0}. Poate dura câteva minute pentru fiecare pagină.', " și ".join(m[0] for m in motoare)))
    rezultate, probleme = {}, []

    def ruleaza(nume, exe, f):
        try:
            d = os.path.join(lucru, nume)     # fiecare program în folderul lui temporar (fără fișiere vechi amestecate)
            os.makedirs(d, exist_ok=True)
            rezultate[nume] = f(exe, cale, d)
        except Exception as ex:
            probleme.append(f'{nume}: {ex}')

    fire = [threading.Thread(target=ruleaza, args=m) for m in motoare]
    for t in fire:
        t.start()
    for t in fire:
        t.join()
    try:
        if not rezultate:
            raise LipsaProgram(_('Programele de recunoaștere nu au reușit să citească partitura. Încearcă un PDF mai clar '
                               'sau o scanare la 300 dpi. ') + ' '.join(probleme)[-400:])
        ordine = {n: rezultate[n] for n, _, _ in motoare if n in rezultate}
        rez = verificare.combina(ordine)
        _metadate(rez.scor, baza)
        nes = dict(rez.nesigure)
        # mâna stângă scrisă pe portativul de sus (sau dreapta pe cel de jos): o despărțim de cealaltă mână
        mutate = verificare.imparte_mainile(rez.scor)
        for nr in mutate:
            motiv = (_('ambele mâini erau scrise pe același portativ; am dat mâinii drepte nota de sus '
                     'și mâinii stângi pe cea de jos'))
            nes[nr] = (nes[nr] + '; ' + motiv) if nr in nes else motiv
        if mutate:
            rez.sigure = max(0, rez.sigure - sum(1 for nr in mutate if nr not in dict(rez.nesigure)))
        nes = dict(sorted(nes.items()))
        fis = ''
        if pastreaza:
            os.makedirs(dest, exist_ok=True)
            rez.scor.write('musicxml', fp=final)
            _scrie_raport(raport, baza, nes, rez.programe, rez.sigure)
            fis = final
        return Recunoastere(rez.scor, nes, rez.programe, probleme, fis)
    finally:
        shutil.rmtree(lucru, ignore_errors=True)


def _metadate(scor, titlu):
    from music21 import metadata
    scor.metadata = metadata.Metadata()
    scor.metadata.title = titlu


def _scrie_raport(cale, baza, nes, programe, sigure):
    with open(cale, 'w', encoding='utf-8') as f:
        f.write(f'{baza}: recunoscută cu {", ".join(programe)}. Măsuri sigure: {sigure}. Măsuri de verificat: {len(nes)}.\n')
        for nr, motiv in nes.items():
            f.write(f'Măsura {nr}: {motiv}\n')


def _citeste_raport(cale) -> dict:
    nes = {}
    if os.path.isfile(cale):
        with open(cale, encoding='utf-8') as f:
            for linie in f:
                if linie.startswith('Măsura '):
                    nr, _x, motiv = linie[7:].partition(':')
                    nes[int(nr)] = motiv.strip()
    return nes
