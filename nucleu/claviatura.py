"""Claviatura: tastatura calculatorului devine pian, pe două etaje.
Jos: rândul de la Shift stânga la 3 de pe blocul numeric = tastele albe (do re mi fa sol la si do ... do, două octave),
rândul de deasupra lui, de la Caps Lock = tastele negre (do diez, re diez, gol, fa diez, sol diez, la diez, gol...).
Sus, la fel, cu o octavă mai jos: rândul de la Tab (până la 6 de pe blocul numeric) = albe,
rândul cifrelor, de la tasta de dinaintea lui 1 = negre.
Tastele se recunosc după codul fizic (scan code), deci nu contează aranjarea tastaturii.
Sunetul vine direct din sintetizatorul Windows (midiOut), notă cu notă, cât ții tasta apăsată."""
import os
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
ALBE_JOS = [0x2A, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x4F, 0x50, 0x51]
#           Shift st., Z, X,   C,    V,    B,    N,    M,  virgulă, punct, /, Shift dr., 1, 2, 3 (bloc numeric)
NEGRE_JOS = [0x3A, 0x1E, 0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2B]
#           Caps Lock, A, S(gol), D, F,    G,    H(gol), J,  K,    L(gol), ;,  ',    tasta de lângă Enter
# etajul de sus: o octavă mai jos
ALBE_SUS = [0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x4B, 0x4C, 0x4D]
#           Tab,  Q,    W,    E,    R,    T,    Y,    U,    I,    O,    P,    [,    ],    4, 5, 6 (bloc numeric)
NEGRE_SUS = [0x29, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D]
#           tasta dinaintea lui 1, 1, 2(gol), 3, 4, 5, 6(gol), 7, 8, 9(gol), 0, minus, egal

TASTE = {**_etaj(ALBE_JOS, NEGRE_JOS, 0), **_etaj(ALBE_SUS, NEGRE_SUS, -12)}
# tastele de pe blocul numeric care, fără Num Lock, sunt și săgeți sau Page Down (se deosebesc după bitul „extins”)
BLOC_NUMERIC = {0x4B, 0x4C, 0x4D, 0x4F, 0x50, 0x51}

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

    def ridica(self, nota):
        self._msg(0x80, max(0, min(127, nota)), 0)

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
