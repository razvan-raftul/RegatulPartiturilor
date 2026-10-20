"""Redarea cu sunet: din măsurile și portativele alese se face un fișier MIDI temporar,
care se cântă cu sintetizatorul din Windows (prin MCI, fără alte programe).
Se poate încetini sau grăbi tempoul și se poate repeta în buclă."""
import copy
import os
import tempfile
import threading
import time

from music21 import bar, repeat, spanner, tempo

TEMPO_IMPLICIT = 100       # dacă partitura nu are tempo scris
_ALIAS = 'regatulredare'


def fa_midi(scor, procent=100) -> str:
    """Scrie un MIDI temporar din partitura dată, cu tempoul înmulțit cu procent/100. Întoarce calea."""
    s = copy.deepcopy(scor)
    f = procent / 100.0
    marci = list(s.recurse().getElementsByClass(tempo.MetronomeMark))
    if marci:
        for mm in marci:
            # „Allegro” fără număr: music21 îi dă un număr implicit (de exemplu 132); îl scriem explicit și îl scalăm
            bpm = mm.getQuarterBPM() or TEMPO_IMPLICIT
            nou = max(10.0, bpm * f)
            mm.referent = 'quarter'
            mm.number = nou
            mm.numberSounding = nou
            mm.numberImplicit = False
    else:
        prima = s.parts[0] if s.parts else s
        masuri = list(prima.getElementsByClass('Measure'))
        tinta = masuri[0] if masuri else prima
        tinta.insert(0, tempo.MetronomeMark(number=max(10, round(TEMPO_IMPLICIT * f))))
    d = os.path.join(tempfile.gettempdir(), 'RegatulPartiturilor')
    os.makedirs(d, exist_ok=True)
    cale = os.path.join(d, f'redare-{int(time.time() * 1000)}.mid')
    try:
        s.write('midi', fp=cale)          # cu repetițiile cântate de două ori
    except Exception:
        # o bucată tăiată din mijlocul unei repetiții nu se poate „desface”: o cântăm fără repetiții
        for b in list(s.recurse().getElementsByClass(bar.Repeat)):
            b.activeSite.remove(b)
        for sp in list(s.recurse().getElementsByClass(spanner.RepeatBracket)):
            sp.activeSite.remove(sp)
        for ex in list(s.recurse().getElementsByClass(repeat.RepeatExpression)):
            ex.activeSite.remove(ex)
        s.write('midi', fp=cale)
    return cale


def midi_octeti(scor) -> bytes:
    """MIDI-ul partiturii la tempoul scris (100%), ca octeți. Se face o singură dată pentru o selecție;
    la schimbarea tempoului se modifică doar octeții (schimba_tempo_midi), fără music21."""
    cale = fa_midi(scor, 100)
    try:
        with open(cale, 'rb') as f:
            return f.read()
    finally:
        try:
            os.remove(cale)
        except OSError:
            pass


def _vlq(date, i):
    v = 0
    while True:
        b = date[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def schimba_tempo_midi(date: bytes, procent) -> bytes:
    """Înmulțește tempoul unui fișier MIDI cu procent/100: schimbă fiecare eveniment de tempo (FF 51 03).
    Durează câteva milisecunde."""
    if procent == 100:
        return date
    f = 100.0 / procent              # microsecunde pe pătrime: mai repede = mai puține
    b = bytearray(date)
    i = 0
    while i + 8 <= len(b):
        tip = bytes(b[i:i + 4])
        lung = int.from_bytes(b[i + 4:i + 8], 'big')
        start, sfarsit = i + 8, min(len(b), i + 8 + lung)
        if tip == b'MTrk':
            j, stare = start, 0
            while j < sfarsit:
                _, j = _vlq(b, j)                       # timpul de dinainte
                if j >= sfarsit:
                    break
                s = b[j]
                if s == 0xFF:                           # meta
                    t = b[j + 1]
                    n, k = _vlq(b, j + 2)
                    if t == 0x51 and n == 3:
                        us = int.from_bytes(b[k:k + 3], 'big')
                        us = max(1, min(0xFFFFFF, round(us * f)))
                        b[k:k + 3] = us.to_bytes(3, 'big')
                    j = k + n
                elif s in (0xF0, 0xF7):                 # sysex
                    n, k = _vlq(b, j + 1)
                    j = k + n
                else:
                    if s & 0x80:
                        stare = s
                        j += 1
                    j += 1 if (stare & 0xF0) in (0xC0, 0xD0) else 2
        i = sfarsit
    return bytes(b)


def scrie_temporar(date: bytes) -> str:
    d = os.path.join(tempfile.gettempdir(), 'RegatulPartiturilor')
    os.makedirs(d, exist_ok=True)
    cale = os.path.join(d, f'redare-{int(time.time() * 1000)}.mid')
    with open(cale, 'wb') as fh:
        fh.write(date)
    return cale


class Redare:
    """Un singur cântec la un moment dat. Pe alte sisteme decât Windows nu face nimic (pentru probe)."""

    def __init__(self):
        self.stare = 'oprit'        # oprit / canta / pauza
        self.bucla = False
        self._cale = None
        self._fir = None
        self._gen = 0
        self.la_sfarsit = None      # funcție chemată când se termină (nu și la buclă)

    def _mci(self, comanda: str) -> str:
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

    def pozitie(self) -> int:
        """Unde a ajuns redarea, în milisecunde (0 dacă nu se poate afla)."""
        if self.stare == 'oprit':
            return 0
        try:
            return int(self._mci(f'status {_ALIAS} position') or 0)
        except Exception:
            return 0

    def canta(self, cale_midi: str, de_la_ms: int = 0, in_pauza: bool = False):
        self.opreste()
        self._cale = cale_midi
        self._mci(f'open "{cale_midi}" type sequencer alias {_ALIAS}')
        self._mci(f'set {_ALIAS} time format milliseconds')
        if in_pauza:
            self._mci(f'seek {_ALIAS} to {max(0, int(de_la_ms))}')
            self.stare = 'pauza'
        else:
            self._mci(f'play {_ALIAS} from {max(0, int(de_la_ms))}')
            self.stare = 'canta'
        self._gen += 1
        gen = self._gen
        self._fir = threading.Thread(target=self._urmareste, args=(gen,), daemon=True)
        self._fir.start()

    def _urmareste(self, gen):
        while gen == self._gen and self.stare != 'oprit':
            time.sleep(0.25)
            if self.stare != 'canta' or os.name != 'nt':
                if os.name != 'nt':
                    return
                continue
            try:
                mod = self._mci(f'status {_ALIAS} mode')
            except Exception:
                return
            if gen != self._gen:
                return
            if mod == 'stopped':
                if self.bucla:
                    try:
                        self._mci(f'play {_ALIAS} from 0')
                    except Exception:
                        return
                else:
                    self.opreste()
                    if self.la_sfarsit:
                        self.la_sfarsit()
                    return

    def pauza_continua(self) -> str:
        if self.stare == 'canta':
            self._mci(f'pause {_ALIAS}')
            self.stare = 'pauza'
        elif self.stare == 'pauza':
            self._mci(f'play {_ALIAS}')          # merge și după „seek” (resume nu)
            self.stare = 'canta'
        return self.stare

    def opreste(self):
        self._gen += 1
        if self.stare != 'oprit':
            try:
                self._mci(f'stop {_ALIAS}')
            except Exception:
                pass
        try:
            self._mci(f'close {_ALIAS}')
        except Exception:
            pass
        self.stare = 'oprit'
        if self._cale:
            try:
                os.remove(self._cale)
            except OSError:
                pass
            self._cale = None
