"""Claviatura: tastatura calculatorului devine pian.
Rândul de jos (tastele albe), de la Shift stânga la 3 de pe blocul numeric: do re mi fa sol la si do ... do (două octave).
Rândul de deasupra (tastele negre), de la Tab: do diez, re diez, (gol), fa diez, sol diez, la diez, (gol), și tot așa.
Tastele se recunosc după codul fizic (scan code), deci nu contează aranjarea tastaturii.
Sunetul vine direct din sintetizatorul Windows (midiOut), notă cu notă, cât ții tasta apăsată."""
import os

# codul fizic al tastei -> câte semitonuri peste nota de început (do)
ALBE = [0x2A, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x4F, 0x50, 0x51]
#        Shift st., Z,  X,    C,    V,    B,    N,    M,    virgulă, punct, /, Shift dr., 1, 2, 3 (bloc numeric)
NEGRE = [0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x2B]
#        Tab,  Q,    W,    E,    R,    T,    Y,    U,    I,    O,    P,    [,    ],    backslash
_TREPTE = [0, 2, 4, 5, 7, 9, 11]      # do re mi fa sol la si, în semitonuri

TASTE = {}
for _i, _sc in enumerate(ALBE):
    TASTE[_sc] = 12 * (_i // 7) + _TREPTE[_i % 7]
for _i, _sc in enumerate(NEGRE):
    if _i % 7 not in (2, 6):           # după mi și după si nu e tastă neagră (mi diez, si diez): tasta rămâne goală
        TASTE[_sc] = 12 * (_i // 7) + _TREPTE[_i % 7] + 1
GOALE = {sc for i, sc in enumerate(NEGRE) if i % 7 in (2, 6)}

# instrumente General MIDI (numărul programului, de la 0)
INSTRUMENTE = [
    ('Pian', 0), ('Pian luminos', 1), ('Pian electric', 4), ('Clavecin', 6), ('Celestă', 8), ('Vibrafon', 11),
    ('Marimba', 12), ('Orgă', 16), ('Orgă de biserică', 19), ('Acordeon', 21), ('Muzicuță', 22),
    ('Chitară clasică', 24), ('Chitară electrică', 26), ('Chitară bas', 32), ('Vioară', 40), ('Violă', 41),
    ('Violoncel', 42), ('Contrabas', 43), ('Harpă', 46), ('Orchestră de coarde', 48), ('Cor', 52),
    ('Trompetă', 56), ('Trombon', 57), ('Corn', 60), ('Saxofon', 65), ('Oboi', 68), ('Fagot', 70),
    ('Clarinet', 71), ('Flaut', 73), ('Nai', 75), ('Sintetizator', 80),
]

NUME_NOTE = ['do', 'do diez', 're', 're diez', 'mi', 'fa', 'fa diez', 'sol', 'sol diez', 'la', 'la diez', 'si']


def nume_octava(do_midi):
    """Numărul octavei lui do (do central = do 4)."""
    return do_midi // 12 - 1


class Sintetizator:
    """Note în timp real prin sintetizatorul Windows. Pe alte sisteme nu face nimic (pentru probe)."""

    def __init__(self):
        self._h = None
        self.program = 0

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
            raise RuntimeError(f'Sintetizatorul Windows nu se poate deschide (eroare {err}). Poate îl folosește alt program.')
        self._w, self._h = w, h
        self._msg(0xB0, 7, 127)                        # volumul canalului la maxim
        self._msg(0xB0, 11, 127)
        self.schimba_instrument(self.program)

    def _msg(self, stare, a, b=0):
        if self._h is not None:
            self._w.midiOutShortMsg(self._h, stare | (a << 8) | (b << 16))

    def schimba_instrument(self, program):
        self.program = program
        self._msg(0xC0, program)

    def apasa(self, nota, tarie=110):
        self._msg(0x90, max(0, min(127, nota)), tarie)

    def ridica(self, nota):
        self._msg(0x80, max(0, min(127, nota)), 0)

    def liniste(self):
        self._msg(0xB0, 123, 0)                        # toate notele oprite

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
