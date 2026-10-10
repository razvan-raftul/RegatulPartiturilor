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


def descarca_setup(versiune) -> str:
    cale = os.path.join(tempfile.gettempdir(), f'RegatulPartiturilor-Setup-{versiune}.exe')
    date = _citeste(BAZA + SETUP, timeout=300)
    if len(date) < 1_000_000:
        raise IOError('Fișierul descărcat e prea mic.')
    with open(cale, 'wb') as f:
        f.write(date)
    return cale


def porneste_setup(cale):
    subprocess.Popen([cale, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/AUTOUPDATE'], close_fds=True)
