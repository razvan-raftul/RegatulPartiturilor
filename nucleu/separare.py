"""Piese audio: despărțirea unei piese (vocea, tobele, basul, chitara, pianul, restul, negativul)
și schimbarea tonalității. Lucrul îl face separare.exe (Demucs + ffmpeg), din folderul „componente\\Separare”
de lângă program. Prima dată când e folosit, programul de separare se descarcă singur de pe GitHub."""
import os
import subprocess
import tempfile
import threading
import urllib.request
import zipfile

from . import recunoastere
from .limba import _

VERSIUNE = 'demucs 4.0.1, htdemucs + htdemucs_6s, ffmpeg rubberband, v1'   # aceeași ca în separare.txt
URL = 'https://github.com/razvan-raftul/RegatulPartiturilor/releases/download/separare/separare.zip'
FARA_FEREASTRA = 0x08000000 if os.name == 'nt' else 0

# codul pentru separare.exe și numele spus de program, în ordinea din filă
ELEMENTE = [
    ('negativ', lambda: _('Negativ (totul fără voce)'), lambda: _('Negativ')),
    ('voce', lambda: _('Vocea'), lambda: _('Voce')),
    ('tobe', lambda: _('Tobele'), lambda: _('Tobe')),
    ('bas', lambda: _('Basul'), lambda: _('Bas')),
    ('chitara', lambda: _('Chitara'), lambda: _('Chitară')),
    ('pian', lambda: _('Pianul'), lambda: _('Pian')),
    ('restul', lambda: _('Restul instrumentelor'), lambda: _('Restul')),
]
EXTENSII = ('.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wma', '.aiff', '.aif', '.mp4', '.webm')


def folder():
    return os.path.join(recunoastere._componente(), 'Separare')


def exe():
    c = os.path.join(folder(), 'separare.exe')
    return c if os.path.isfile(c) else None


def instalat():
    try:
        with open(os.path.join(folder(), 'versiune.txt'), encoding='utf-8-sig') as f:
            return exe() is not None and f.read().strip() == VERSIUNE
    except OSError:
        return False


def descarca(progres=None, oprit=lambda: False):
    """Descarcă și despachetează programul de separare. progres(procent, mb_total) se cheamă pe parcurs."""
    radacina = recunoastere._componente()
    os.makedirs(radacina, exist_ok=True)
    zip_cale = os.path.join(tempfile.gettempdir(), f'MusicBox-separare-{os.getpid()}.zip')
    req = urllib.request.Request(URL, headers={'User-Agent': 'MusicBox'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(zip_cale, 'wb') as f:
            total = int(r.headers.get('Content-Length') or 0)
            mb = total // 1048576
            gata = 0
            while True:
                if oprit():
                    raise InterruptedError
                bucata = r.read(1024 * 1024)
                if not bucata:
                    break
                f.write(bucata)
                gata += len(bucata)
                if progres and total:
                    progres(gata * 90 // total, mb)
        if total and gata != total:
            raise IOError(_('Descărcarea nu s-a terminat întreagă.'))
        nou = folder() + '.nou'
        if os.path.isdir(nou):
            _sterge(nou)
        with zipfile.ZipFile(zip_cale) as z:
            membri = z.infolist()
            for i, m in enumerate(membri):
                if oprit():
                    raise InterruptedError
                z.extract(m, nou)
                if progres and i % 50 == 0:
                    progres(90 + 10 * i // max(1, len(membri)), mb)
        if os.path.isdir(folder()):
            _sterge(folder())
        os.replace(nou, folder())
        if progres:
            progres(100, mb)
    finally:
        try:
            os.remove(zip_cale)
        except OSError:
            pass


def _sterge(cale):
    import shutil
    shutil.rmtree(cale, ignore_errors=True)


class Lucrare:
    """Pornește separare.exe și urmărește ce spune. la_rand(tip, valoare) se cheamă din alt fir:
    ('progres', n), ('fisier', cale), ('eroare', text), ('gata', [fișiere])."""

    def __init__(self, intrare, iesire, elemente, impreuna=None, semitonuri=0, fmt='mp3', la_rand=None):
        self.cmd = [exe(), '--intrare', intrare, '--iesire', iesire, '--semitonuri', str(semitonuri), '--format', fmt]
        for cod, eticheta in elemente:
            self.cmd += ['--element', cod, eticheta]
        if impreuna:
            self.cmd += ['--impreuna', impreuna]
        self.la_rand = la_rand or (lambda *a: None)
        self.p = None
        self.oprita = False
        self.fisiere = []

    def porneste(self):
        threading.Thread(target=self._lucru, daemon=True).start()

    def opreste(self):
        self.oprita = True
        if self.p and self.p.poll() is None:
            try:
                self.p.kill()
            except Exception:
                pass

    def _lucru(self):
        eroare = ''
        try:
            self.p = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                      creationflags=FARA_FEREASTRA, encoding='utf-8', errors='replace', bufsize=1)
            for rand in self.p.stdout:
                rand = rand.strip()
                tip, _sp, rest = rand.partition(' ')
                if tip == 'PROGRES':
                    try:
                        self.la_rand('progres', int(rest))
                    except ValueError:
                        pass
                elif tip == 'FISIER':
                    self.fisiere.append(rest)
                    self.la_rand('fisier', rest)
                elif tip == 'EROARE':
                    eroare = rest
            self.p.wait()
        except Exception as ex:
            eroare = str(ex)
        if self.oprita:
            self.la_rand('oprita', None)
        elif eroare or not self.fisiere:
            self.la_rand('eroare', eroare or _('Programul de separare s-a oprit fără să termine.'))
        else:
            self.la_rand('gata', list(self.fisiere))
