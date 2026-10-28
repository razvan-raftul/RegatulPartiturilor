"""Fila Fișiere audio: un folder de pe calculator, cu subfolderele lui ca într-un arbore, și fișierele audio
care se aud imediat ce ajungi pe ele cu săgețile. Sunetul trece prin MCI (mpegvideo, ce poate Windows să cânte:
mp3, wav, wma, m4a, aac; flac și ogg doar dacă Windows are codecurile lor)."""
import os
import threading
import time

EXTENSII = ('.mp3', '.wav', '.wma', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.aif', '.aiff', '.mid', '.midi')
MODURI = ('urmatoarea', 'repeta', 'opreste')     # ce se întâmplă la sfârșitul piesei (R schimbă)
_ALIAS = 'musicboxfisier'


def continut(folder):
    """(subfoldere, fișiere audio) dintr-un folder, în ordine alfabetică (fără ascunse)."""
    try:
        nume = os.listdir(folder)
    except OSError:
        return [], []
    dirs, fis = [], []
    for n in nume:
        if n.startswith('.'):
            continue
        c = os.path.join(folder, n)
        if os.path.isdir(c):
            dirs.append(c)
        elif os.path.splitext(n)[1].lower() in EXTENSII:
            fis.append(c)
    k = lambda c: os.path.basename(c).lower()
    return sorted(dirs, key=k), sorted(fis, key=k)


def cu_subfoldere(folder):
    """Folderul și toate subfolderele lui (la orice adâncime), fiecare cu fișierele lui:
    [(nume, cale, fișiere)]. Numele subfolderelor e drumul de la folder, de ex. „X, Y”."""
    rez = []

    def mergi(d, nume):
        dirs, fis = continut(d)
        rez.append((nume, d, fis))
        for x in dirs:
            mergi(x, (nume + ', ' if d != folder else '') + os.path.basename(x))
    mergi(folder, os.path.basename(folder) or folder)
    return rez


class Melodie:
    """Un singur fișier la un moment dat. stare: oprit / canta / pauza. la_sfarsit() se cheamă din alt fir."""

    def __init__(self):
        self.stare = 'oprit'
        self.cale = None
        self.la_sfarsit = None
        self._gen = 0
        self._lacat = threading.Lock()

    def _mci(self, comanda):
        if os.name != 'nt':
            return ''
        import ctypes
        buf = ctypes.create_unicode_buffer(256)
        err = ctypes.windll.winmm.mciSendStringW(comanda, buf, 255, None)
        if err:
            eb = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(err, eb, 255)
            raise RuntimeError(eb.value or f'eroare MCI {err}')
        return buf.value

    def deschide_si_canta(self, cale, de_la_ms=0):
        with self._lacat:
            self._inchide()
            self.cale = cale
            tip = 'sequencer' if cale.lower().endswith(('.mid', '.midi')) else 'mpegvideo'
            self._mci(f'open "{cale}" type {tip} alias {_ALIAS}')
            self._mci(f'set {_ALIAS} time format milliseconds')
            self._mci(f'play {_ALIAS} from {max(0, int(de_la_ms))}')
            self.stare = 'canta'
            self._gen += 1
            gen = self._gen
        threading.Thread(target=self._urmareste, args=(gen,), daemon=True).start()

    def _urmareste(self, gen):
        while gen == self._gen and self.stare != 'oprit':
            time.sleep(0.2)
            if self.stare != 'canta':
                continue
            try:
                with self._lacat:
                    if gen != self._gen:
                        return
                    mod = self._mci(f'status {_ALIAS} mode')
                    poz = int(self._mci(f'status {_ALIAS} position') or 0)
                    lung = int(self._mci(f'status {_ALIAS} length') or 0)
            except Exception:
                return
            if mod == 'stopped' or (lung and poz >= lung - 20 and mod != 'playing'):
                if gen != self._gen:
                    return
                self.stare = 'oprit'
                if self.la_sfarsit:
                    self.la_sfarsit()
                return

    def pozitie(self):
        if self.stare == 'oprit' or not self.cale:
            return 0
        try:
            return int(self._mci(f'status {_ALIAS} position') or 0)
        except Exception:
            return 0

    def lungime(self):
        try:
            return int(self._mci(f'status {_ALIAS} length') or 0)
        except Exception:
            return 0

    def pauza_continua(self):
        if self.stare == 'canta':
            self._mci(f'pause {_ALIAS}')
            self.stare = 'pauza'
        elif self.stare == 'pauza':
            self._mci(f'play {_ALIAS}')
            self.stare = 'canta'
        return self.stare

    def sari(self, ms):
        if self.stare == 'canta':
            self._mci(f'play {_ALIAS} from {max(0, int(ms))}')
        elif self.stare == 'pauza':
            self._mci(f'seek {_ALIAS} to {max(0, int(ms))}')

    def de_la_capat(self):
        if self.cale and self.stare != 'oprit':
            self.stare = 'canta'
            self._mci(f'play {_ALIAS} from 0')
        elif self.cale:
            self.deschide_si_canta(self.cale)

    def _inchide(self):
        self._gen += 1
        self.stare = 'oprit'
        try:
            self._mci(f'stop {_ALIAS}')
        except Exception:
            pass
        try:
            self._mci(f'close {_ALIAS}')
        except Exception:
            pass

    def opreste(self):
        with self._lacat:
            self._inchide()
