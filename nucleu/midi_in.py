"""Clapa MIDI: notele de pe o claviatură MIDI legată la calculator se cântă cu sunetele programului
(instrumentul claviaturii). Prin winmm (midiInOpen) cu o funcție chemată de Windows la fiecare mesaj.
Notele, pedala (sustain), roata de modulație și pitch bend-ul merg direct la sintetizator;
canalul pe care trimite clapa nu contează."""
import ctypes
import os

MIM_DATA = 0x3C3
CALLBACK_FUNCTION = 0x30000


def dispozitive():
    """Numele clapelor MIDI legate acum (în ordinea Windows)."""
    if os.name != 'nt':
        return []
    from ctypes import wintypes

    class MIDIINCAPSW(ctypes.Structure):
        _fields_ = [('wMid', wintypes.WORD), ('wPid', wintypes.WORD), ('vDriverVersion', wintypes.UINT),
                    ('szPname', wintypes.WCHAR * 32), ('dwSupport', wintypes.DWORD)]
    w = ctypes.windll.winmm
    rez = []
    for i in range(w.midiInGetNumDevs()):
        c = MIDIINCAPSW()
        if w.midiInGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c)) == 0:
            rez.append(c.szPname)
    return rez


class IntrareMidi:
    """Deschide o clapă MIDI și trimite ce cânți la sint (SintetizatorFluid sau cel din Windows).
    transpunere() întoarce câte semitonuri se adaugă (aceeași transpunere ca la claviatura din program)."""

    def __init__(self, sint, transpunere=lambda: 0):
        self.sint = sint
        self.transpunere = transpunere
        self._h = None
        self._cb = None
        self.nume = ''
        self._tinute = {}             # nota de pe clapă -> (nota cântată, canalul)

    def deschisa(self):
        return self._h is not None

    def deschide(self, nume):
        """Deschide clapa cu numele dat (sau prima, dacă numele e gol). Întoarce numele deschis sau ''."""
        self.inchide()
        if os.name != 'nt':
            return ''
        nume_lista = dispozitive()
        if not nume_lista:
            return ''
        index = nume_lista.index(nume) if nume in nume_lista else 0
        from ctypes import wintypes
        w = ctypes.windll.winmm
        PROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t)
        self._cb = PROC(self._mesaj)
        w.midiInOpen.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.UINT, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
        w.midiInStart.argtypes = [wintypes.HANDLE]
        w.midiInStop.argtypes = [wintypes.HANDLE]
        w.midiInReset.argtypes = [wintypes.HANDLE]
        w.midiInClose.argtypes = [wintypes.HANDLE]
        h = wintypes.HANDLE()
        if w.midiInOpen(ctypes.byref(h), index, ctypes.cast(self._cb, ctypes.c_void_p), 0, CALLBACK_FUNCTION) != 0:
            self._cb = None
            return ''
        w.midiInStart(h)
        self._w, self._h = w, h
        self.nume = nume_lista[index]
        return self.nume

    def _mesaj(self, h, msg, instanta, p1, p2):
        if msg != MIM_DATA:
            return
        try:
            stare, d1, d2 = p1 & 0xFF, (p1 >> 8) & 0x7F, (p1 >> 16) & 0x7F
            tip = stare & 0xF0
            if tip == 0x90 and d2 > 0:
                n = d1 + self.transpunere()
                if 0 <= n <= 127:
                    self._tinute[d1] = (n, self.sint.apasa(n, d2))
            elif tip == 0x80 or (tip == 0x90 and d2 == 0):
                t = self._tinute.pop(d1, None)
                if t:
                    self.sint.ridica(*t)
            elif tip == 0xB0:
                self.sint.cc(d1, d2)                       # pedala (64), modulația (1), volumul (7)...
            elif tip == 0xE0:
                self.sint.pitch_bend(d1 | (d2 << 7))
        except Exception:
            pass

    def inchide(self):
        if self._h is None:
            return
        try:
            self._w.midiInStop(self._h)
            self._w.midiInReset(self._h)
            self._w.midiInClose(self._h)
        except Exception:
            pass
        self._h = None
        for n, c in list(self._tinute.values()):
            try:
                self.sint.ridica(n, c)
            except Exception:
                pass
        self._tinute.clear()
        self.nume = ''
