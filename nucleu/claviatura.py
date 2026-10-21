"""Claviatura: tastatura calculatorului devine pian, pe două etaje.
Jos: rândul de la Z la 3 de pe blocul numeric = tastele albe (do re mi fa sol la si do ...),
rândul de deasupra, mutat cu o tastă la dreapta = negrele (S do diez, D re diez, F gol, G fa diez, H sol diez, J la diez, K gol...).
Sus, la fel, cu o octavă mai jos: rândul de la Tab (până la 6 de pe blocul numeric) = albe,
rândul cifrelor de la 1 = negre (1 do diez, 2 re diez, 3 gol, 4 fa diez, 5 sol diez, 6 la diez, 7 gol...).
Shift stânga e „bender”: cât îl ții apăsat, nota tremură (vibrato din pitch bend).
Tastele se recunosc după codul fizic (scan code), deci nu contează aranjarea tastaturii.
Sunetul vine din FluidSynth (sunete.py) sau, dacă lipsește, din sintetizatorul Windows (midiOut)."""
import os
import threading
import time
from .limba import _

_TREPTE = [0, 2, 4, 5, 7, 9, 11]      # do re mi fa sol la si, în semitonuri


def _etaj(albe, negre, baza):
    """Tastele unui etaj: albe pe trepte, negre între ele (după mi și după si rămâne gol)."""
    t = {}
    for i, sc in enumerate(albe):
        if sc is not None:
            t[sc] = baza + 12 * (i // 7) + _TREPTE[i % 7]
    for i, sc in enumerate(negre):
        if sc is not None and i % 7 not in (2, 6):
            t[sc] = baza + 12 * (i // 7) + _TREPTE[i % 7] + 1
    return t


# etajul de jos (do din setări, de obicei do 4)
ALBE_JOS = [0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x4F, 0x50, 0x51]
#           Z,    X,    C,    V,    B,    N,    M,  virgulă, punct, /, Shift dr., 1, 2, 3 (bloc numeric)
NEGRE_JOS = [0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2B, 0x1C]
#           S,    D,    F(gol), G,  H,    J,    K(gol), L,  ;,   '(gol), tasta de lângă Enter, Enter
# etajul de sus: o octavă mai jos
ALBE_SUS = [0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x4B, 0x4C, 0x4D]
#           Tab,  Q,    W,    E,    R,    T,    Y,    U,    I,    O,    P,    [,    ],    4, 5, 6 (bloc numeric)
NEGRE_SUS = [0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E]
#           1,    2,    3(gol), 4,  5,    6,    7(gol), 8,  9,    0(gol), minus, egal, Backspace

TASTE = {**_etaj(ALBE_JOS, NEGRE_JOS, 0), **_etaj(ALBE_SUS, NEGRE_SUS, -12)}
# tastele de pe blocul numeric care, fără Num Lock, sunt și săgeți sau Page Down (se deosebesc după bitul „extins”)
BLOC_NUMERIC = {0x4B, 0x4C, 0x4D, 0x4F, 0x50, 0x51}
TASTA_BENDER = 0x2A            # Shift stânga


class Vibrato:
    """Cât ține Shift stânga: înălțimea tremură ușor în sus și în jos (pitch bend, cam 6 pe secundă, ±40 de cenți)."""
    def __init__(self, sint):
        self.sint = sint
        self._gen = 0

    def porneste(self):
        self._gen += 1
        gen = self._gen

        def lucru():
            import math
            t0 = time.time()
            while gen == self._gen:
                faza = (time.time() - t0) * 6.0 * 2 * math.pi
                self.sint.pitch_bend(8192 + int(1638 * math.sin(faza)))
                time.sleep(0.012)
        threading.Thread(target=lucru, daemon=True).start()

    def opreste(self):
        self._gen += 1
        self.sint.pitch_bend(8192)



PROGRAM_CUTIE = 10      # General MIDI: Music Box
# melodia de rezervă de la pornire (dacă WAV-ul de celestă nu merge): (nota MIDI, după câte ms vine următoarea)
MELODIE_CUTIE = [(84, 170), (88, 170), (91, 170), (96, 340), (95, 170), (91, 170), (88, 170), (89, 170), (86, 170), (84, 700)]


def melodie_cutie(sint):
    """Cântă melodia scurtă de cutie muzicală pe sintetizatorul deschis, apoi pune la loc instrumentul."""
    if not sint.deschis():
        return
    sint.program_temporar(PROGRAM_CUTIE)
    pornite = []
    try:
        for nota, pas in MELODIE_CUTIE:
            sint.apasa(nota, 90)
            pornite.append(nota)
            time.sleep(pas / 1000)
        time.sleep(0.4)
    finally:
        for n in pornite:
            sint.ridica(n)
        sint.program_inapoi()


NUME_NOTE = ['do', _('do diez'), 're', _('re diez'), 'mi', 'fa', _('fa diez'), 'sol', _('sol diez'), 'la', _('la diez'), 'si']


def nume_octava(do_midi):
    """Numărul octavei lui do (do central = do 4)."""
    return do_midi // 12 - 1


class Sintetizator:
    """Note în timp real prin sintetizatorul Windows. Pe alte sisteme nu face nimic (pentru probe).
    E folosit doar dacă lipsește banca de sunete (vezi sunete.py). Îl poate folosi un singur program o dată,
    de aceea se închide (elibereaza) când nu mai e nevoie de el."""
    exclusiv = True

    def __init__(self):
        self._h = None
        self.program = (0, 0)

    def deschis(self):
        return self._h is not None

    def deschide(self):
        if self._h is not None or os.name != 'nt':
            return
        import ctypes
        from ctypes import wintypes
        w = ctypes.windll.winmm
        w.midiOutOpen.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
        w.midiOutShortMsg.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        w.midiOutReset.argtypes = [wintypes.HANDLE]
        w.midiOutClose.argtypes = [wintypes.HANDLE]
        h = wintypes.HANDLE()
        err = 1
        for dispozitiv in (0xFFFFFFFF, 0):            # întâi „MIDI mapper”, apoi primul sintetizator
            err = w.midiOutOpen(ctypes.byref(h), dispozitiv, 0, 0, 0)
            if err == 0:
                break
        if err:
            raise RuntimeError(_('Sintetizatorul Windows nu se poate deschide (eroare {0}). Poate îl folosește alt program.', err))
        self._w, self._h = w, h
        self._msg(0xB0, 7, 127)                        # volumul canalului la maxim
        self._msg(0xB0, 11, 127)
        self.schimba_instrument(self.program)

    def _msg(self, stare, a, b=0):
        if self._h is not None:
            self._w.midiOutShortMsg(self._h, stare | (a << 8) | (b << 16))

    def _selecteaza(self, prog):
        banca, program = (0, prog) if isinstance(prog, int) else prog
        if banca < 120:
            self._msg(0xB0, 0, banca)                  # variantele GS (bank select)
        self._msg(0xC0, program)

    def schimba_instrument(self, prog):
        self.program = (0, prog) if isinstance(prog, int) else tuple(prog)
        self._selecteaza(self.program)

    def program_temporar(self, prog):
        self._selecteaza(prog)

    def program_inapoi(self):
        self._selecteaza(self.program)

    def apasa(self, nota, tarie=110):
        self._msg(0x90, max(0, min(127, nota)), tarie)
        return 0

    def ridica(self, nota, canal=None):
        self._msg(0x80, max(0, min(127, nota)), 0)

    def cc(self, numar, valoare):
        self._msg(0xB0, numar & 0x7F, valoare & 0x7F)

    def pitch_bend(self, val):
        val = max(0, min(16383, int(val)))
        self._msg(0xE0, val & 0x7F, val >> 7)

    def liniste(self):
        self._msg(0xB0, 123, 0)                        # toate notele oprite

    def elibereaza(self):
        self.inchide()

    def inchide(self):
        if self._h is None:
            return
        try:
            self.liniste()
            self._w.midiOutReset(self._h)
            self._w.midiOutClose(self._h)
        except Exception:
            pass
        self._h = None
