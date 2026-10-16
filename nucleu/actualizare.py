"""Actualizare automată: la pornire citește version.txt din release-ul „latest” de pe GitHub;
dacă e o versiune mai nouă, descarcă programul de instalare, îl rulează fără ferestre și închide aplicația.
Programul de instalare redeschide singur aplicația."""
import os
import subprocess
import sys
import tempfile
import urllib.request

from . import VERSIUNE

DEPOZIT = 'razvan-raftul/RegatulPartiturilor'
BAZA = f'https://github.com/{DEPOZIT}/releases/download/latest/'
SETUP = 'RegatulPartiturilor-Setup.exe'


def instalat() -> bool:
    """Doar programul instalat (exe) se actualizează singur; codul rulat din Python nu."""
    return bool(getattr(sys, 'frozen', False))


def _v(t):
    try:
        return tuple(int(x) for x in t.strip().split('.'))
    except ValueError:
        return None


def _citeste(url, timeout=15) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'RegatulPartiturilor'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def versiune_noua():
    """Întoarce versiunea de pe internet dacă e mai nouă, altfel None. Aruncă excepție dacă nu e internet."""
    rem = _v(_citeste(BAZA + 'version.txt').decode('ascii', 'ignore'))
    cur = _v(VERSIUNE)
    if rem and cur and rem > cur:
        return '.'.join(map(str, rem))
    return None


def descarca_setup(versiune, progres=None) -> str:
    """Descarcă programul de instalare. progres(descarcat, total) se cheamă pe parcurs (total poate fi 0 dacă nu se știe)."""
    cale = os.path.join(tempfile.gettempdir(), f'RegatulPartiturilor-Setup-{versiune}.exe')
    req = urllib.request.Request(BAZA + SETUP, headers={'User-Agent': 'RegatulPartiturilor'})
    descarcat = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(cale + '.part', 'wb') as f:
        total = int(r.headers.get('Content-Length') or 0)
        if progres:
            progres(0, total)
        while True:
            bucata = r.read(256 * 1024)
            if not bucata:
                break
            f.write(bucata)
            descarcat += len(bucata)
            if progres:
                progres(descarcat, total)
    if descarcat < 1_000_000 or (total and descarcat != total):
        os.remove(cale + '.part')
        raise IOError('Descărcarea nu s-a terminat întreagă.')
    os.replace(cale + '.part', cale)
    return cale


def porneste_setup(cale):
    subprocess.Popen([cale, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/AUTOUPDATE'], close_fds=True)
