"""Playerul cu înregistrare: piesa întreagă se transformă o dată într-o înregistrare audio (FluidSynth cu banca
GeneralUser GS, fără placă de sunet, mult mai repede decât în timp real), iar playerul cântă înregistrarea.
Derularea e exactă, iar tempoul se schimbă pe loc, fără să se refacă înregistrarea: sunetul se întinde sau se strânge
în timp (WSOLA), fără să i se schimbe înălțimea. Metronomul e o pistă separată, amestecată în timp ce se cântă,
deci și el se pornește, se oprește și își schimbă volumul pe loc.

Ieșirea de sunet e cea a Windows (waveOut, prin ctypes), deschisă din nou la fiecare pornire, ca să meargă și
după ce treci pe căști. Fila 1 (K, I, J, L acolo) rămâne neschimbată: ea cântă ca înainte, prin MIDI."""
import ctypes
import os
import threading
import time

import numpy as np

RATA = 44100
FRAME = 2048          # fereastra WSOLA (cadre)
HOP = 1024            # cât sunet iese la un pas (~23 ms)
TOL = 512             # cât caută WSOLA înainte și înapoi
NR_BUFERE = 8         # ~190 ms în coada plăcii de sunet


# ---------------- înregistrarea ----------------
def _fluid(cale_dll=None):
    from . import sunete
    if cale_dll is None:
        d = sunete.folder_sunete()
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass
        cale_dll = os.path.join(d, sunete.DLL)
    f = ctypes.CDLL(cale_dll)
    vp, ci, cs, cd = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_double
    for nume, res, args in (('new_fluid_settings', vp, []), ('delete_fluid_settings', None, [vp]),
                            ('fluid_settings_setstr', ci, [vp, cs, cs]), ('fluid_settings_setint', ci, [vp, cs, ci]),
                            ('fluid_settings_setnum', ci, [vp, cs, cd]),
                            ('new_fluid_synth', vp, [vp]), ('delete_fluid_synth', None, [vp]),
                            ('fluid_synth_sfload', ci, [vp, cs, ci]),
                            ('new_fluid_player', vp, [vp]), ('delete_fluid_player', None, [vp]),
                            ('fluid_player_add_mem', ci, [vp, vp, ctypes.c_size_t]),
                            ('fluid_player_play', ci, [vp]), ('fluid_player_get_status', ci, [vp]),
                            ('fluid_synth_write_s16', ci, [vp, ci, vp, ci, ci, vp, ci, ci])):
        fn = getattr(f, nume)
        fn.restype = res
        fn.argtypes = args
    return f


def durata_midi_ms(date: bytes) -> int:
    """Cât ține MIDI-ul, după ultimul eveniment."""
    from . import redare
    _fmt, div, piste = redare._citeste(date)
    ultim = max((t for p in piste for t, _ev in p), default=0)
    return redare.milisecunde(date, [ultim / div])[0]


def randeaza(date: bytes, progres=None, cale_dll=None, cale_sf2=None, oprit=None, normalizeaza=True):
    """MIDI (octeți) -> înregistrare stereo, numpy int16 de forma (cadre, 2), la 44100 Hz.
    progres(0..100) se cheamă din când în când; oprit() adevărat întrerupe (întoarce None)."""
    from . import sunete
    f = _fluid(cale_dll)
    if cale_sf2 is None:
        cale_sf2 = os.path.join(sunete.folder_sunete(), sunete.SF2)
    s = f.new_fluid_settings()
    f.fluid_settings_setnum(s, b'synth.sample-rate', float(RATA))
    f.fluid_settings_setnum(s, b'synth.gain', 0.7)
    f.fluid_settings_setint(s, b'synth.polyphony', 256)
    f.fluid_settings_setstr(s, b'player.timing-source', b'sample')
    f.fluid_settings_setint(s, b'synth.lock-memory', 0)
    synth = f.new_fluid_synth(s)
    player = None
    try:
        if f.fluid_synth_sfload(synth, cale_sf2.encode('mbcs' if os.name == 'nt' else 'utf-8'), 1) < 0:
            raise RuntimeError('banca de sunete')
        player = f.new_fluid_player(synth)
        buf_midi = ctypes.create_string_buffer(bytes(date), len(date))
        if f.fluid_player_add_mem(player, buf_midi, len(date)) != 0:
            raise RuntimeError('MIDI')
        f.fluid_player_play(player)
        lung_ms = durata_midi_ms(date)
        maxim = int((lung_ms / 1000 + 10) * RATA)
        bloc = 4096
        bucati = []
        facut = 0
        buf = (ctypes.c_int16 * (bloc * 2))()
        ultim_procent = -1
        while f.fluid_player_get_status(player) in (1, 2) and facut < maxim:
            f.fluid_synth_write_s16(synth, bloc, buf, 0, 2, buf, 1, 2)
            bucati.append(np.frombuffer(buf, dtype=np.int16).copy())
            facut += bloc
            if progres and lung_ms:
                p = min(99, int(100 * facut / (lung_ms / 1000 * RATA)))
                if p != ultim_procent:
                    ultim_procent = p
                    progres(p)
            if oprit and oprit():
                return None
        for _i in range(int(1.5 * RATA / bloc)):            # coada: notele care încă sună
            f.fluid_synth_write_s16(synth, bloc, buf, 0, 2, buf, 1, 2)
            bucati.append(np.frombuffer(buf, dtype=np.int16).copy())
        sunet = np.concatenate(bucati).reshape(-1, 2) if bucati else np.zeros((0, 2), np.int16)
        varf = int(np.abs(sunet.astype(np.int32)).max()) if len(sunet) else 0
        if normalizeaza and 0 < varf < 24000:                  # mai tare, până aproape de maxim (cel mult de 4 ori)
            sunet = (sunet.astype(np.float32) * min(4.0, 24000 / varf)).astype(np.int16)
        if progres:
            progres(100)
        return sunet
    finally:
        if player:
            f.delete_fluid_player(player)
        f.delete_fluid_synth(synth)
        f.delete_fluid_settings(s)


def pe_maini(sunete):
    """Înregistrările fiecărei mâini (sau portativ), nenormalizate -> (amestecul, [mâinile]), toate int16 de aceeași
    lungime și cu același câștig (ca o mână singură să sune la fel de tare ca în amestec)."""
    n = max(len(x) for x in sunete)
    lungi = []
    for x in sunete:
        y = np.zeros((n, 2), np.int32)
        y[:len(x)] = x
        lungi.append(y)
    mix = np.sum(lungi, axis=0)
    varf = int(np.abs(mix).max()) if n else 0
    castig = min(4.0, 24000 / varf) if varf else 1.0
    def la16(a):
        return np.clip(a.astype(np.float32) * castig, -32768, 32767).astype(np.int16)
    return la16(mix), [la16(y) for y in lungi]


def _clic(accent):
    """O lovitură scurtă, ca de wood block (fără înălțime muzicală clară)."""
    n = int(0.06 * RATA)
    t = np.arange(n) / RATA
    f1, f2 = (2100.0, 3300.0) if accent else (1500.0, 2450.0)
    s = (np.sin(2 * np.pi * f1 * t) + 0.6 * np.sin(2 * np.pi * f2 * t)) * np.exp(-t * 90)
    s[:20] *= np.linspace(0, 1, 20)
    return (s / np.max(np.abs(s))).astype(np.float32)


def pista_metronom(cadre, momente):
    """momente: (milisecunde, e_prima_din_masura). Pista mono float32, la volum 100%."""
    p = np.zeros(cadre, np.float32)
    clicuri = {True: _clic(True) * 0.9, False: _clic(False) * 0.7}
    for ms, prima in momente:
        i = int(ms * RATA / 1000)
        c = clicuri[bool(prima)]
        j = min(cadre, i + len(c))
        if 0 <= i < cadre:
            p[i:j] += c[:j - i]
    return p


# ---------------- tempoul fără schimbarea înălțimii (WSOLA) ----------------
class Intinzator:
    """Scoate sunetul bucată cu bucată (HOP cadre), la viteza dată, fără să schimbe înălțimea.
    sursa(a, b) întoarce cadrele [a, b) ca float32 (n, 2), cu zerouri în afara înregistrării."""

    def __init__(self, sursa, lungime):
        self.sursa = sursa
        self.lungime = lungime
        self.fereastra = np.hanning(FRAME + 1)[:FRAME].astype(np.float32)[:, None]   # periodică: suma pe 50% = 1
        self.reseteaza(0)

    def reseteaza(self, poz):
        self.poz = float(max(0, poz))
        self.prev = None
        self.coada = np.zeros((FRAME - HOP, 2), np.float32)

    def gata(self):
        return self.poz >= self.lungime

    def bloc(self, viteza):
        """(cadre float32 (HOP, 2), poziția în înregistrare unde începe bucata)."""
        nominal = int(round(self.poz))
        a = nominal
        if self.prev is not None and abs(viteza - 1.0) > 1e-3:
            ref = self.sursa(self.prev + HOP, self.prev + HOP + FRAME).mean(axis=1)
            zona = self.sursa(nominal - TOL, nominal + TOL + FRAME).mean(axis=1)
            n = 1 << int(np.ceil(np.log2(len(zona) + FRAME)))
            cor = np.fft.irfft(np.fft.rfft(zona, n) * np.conj(np.fft.rfft(ref, n)), n)[:2 * TOL + 1]
            a = nominal - TOL + int(np.argmax(cor))
        elif self.prev is not None:
            a = self.prev + HOP                          # la tempoul scris: exact înregistrarea, fără căutare
        seg = self.sursa(a, a + FRAME) * self.fereastra
        iesire = self.coada[:HOP] + seg[:HOP]            # FRAME = 2 * HOP: fiecare bucată se suprapune pe jumătate
        self.coada = seg[HOP:].copy()
        self.prev = a
        start = nominal
        self.poz = (a if abs(viteza - 1.0) <= 1e-3 else self.poz) + HOP * viteza
        return iesire, start


# ---------------- ieșirea de sunet (waveOut) ----------------
class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [('wFormatTag', ctypes.c_ushort), ('nChannels', ctypes.c_ushort), ('nSamplesPerSec', ctypes.c_uint),
                ('nAvgBytesPerSec', ctypes.c_uint), ('nBlockAlign', ctypes.c_ushort), ('wBitsPerSample', ctypes.c_ushort),
                ('cbSize', ctypes.c_ushort)]


class _WAVEHDR(ctypes.Structure):
    _fields_ = [('lpData', ctypes.c_void_p), ('dwBufferLength', ctypes.c_uint), ('dwBytesRecorded', ctypes.c_uint),
                ('dwUser', ctypes.c_size_t), ('dwFlags', ctypes.c_uint), ('dwLoops', ctypes.c_uint),
                ('lpNext', ctypes.c_void_p), ('reserved', ctypes.c_size_t)]


WHDR_DONE = 1


class IesireWaveOut:
    def __init__(self):
        w = ctypes.windll.winmm
        self.w = w
        fmt = _WAVEFORMATEX(1, 2, RATA, RATA * 4, 4, 16, 0)
        self.h = ctypes.c_void_p()
        err = w.waveOutOpen(ctypes.byref(self.h), ctypes.c_uint(0xFFFFFFFF), ctypes.byref(fmt), 0, 0, 0)
        if err:
            raise RuntimeError(f'waveOutOpen {err}')
        self.mem = [ctypes.create_string_buffer(HOP * 4) for _i in range(NR_BUFERE)]
        self.hdr = []
        for m in self.mem:
            h = _WAVEHDR()
            h.lpData = ctypes.cast(m, ctypes.c_void_p)
            h.dwBufferLength = HOP * 4
            w.waveOutPrepareHeader(self.h, ctypes.byref(h), ctypes.sizeof(h))
            h.dwFlags |= WHDR_DONE                          # liber de la început
            self.hdr.append(h)

    def liber(self, i):
        return bool(self.hdr[i].dwFlags & WHDR_DONE)

    def scrie(self, i, octeti):
        ctypes.memmove(self.mem[i], octeti, len(octeti))
        self.hdr[i].dwFlags &= ~WHDR_DONE
        self.w.waveOutWrite(self.h, ctypes.byref(self.hdr[i]), ctypes.sizeof(self.hdr[i]))

    def goleste(self):
        self.w.waveOutReset(self.h)

    def pauza(self):
        self.w.waveOutPause(self.h)

    def continua(self):
        self.w.waveOutRestart(self.h)

    def inchide(self):
        try:
            self.w.waveOutReset(self.h)
            for h in self.hdr:
                self.w.waveOutUnprepareHeader(self.h, ctypes.byref(h), ctypes.sizeof(h))
            self.w.waveOutClose(self.h)
        except Exception:
            pass


class PlayerAudio:
    """Cântă înregistrarea. Stările ca la redare.Redare: oprit / canta / pauza. Pozițiile sunt în milisecunde
    ale înregistrării (adică ale muzicii la tempoul scris)."""

    def __init__(self):
        self.muzica = None           # int16 (n, 2)
        self.metronom = None         # float32 (n,)
        self.volum_metronom = 0.0    # 0..1 (0 = oprit)
        self.viteza = 1.0            # 1.0 = tempoul scris; 0.5 = de două ori mai rar
        self.stare = 'oprit'
        self.la_sfarsit = None
        self._fir = None
        self._gen = 0
        self._salt = None
        self._lacat = threading.Lock()
        self._coada = []             # (bufer, poziția în înregistrare) în ordinea în care se aud
        self._poz = 0

    # ---- înregistrarea ----
    def incarca(self, muzica, metronom=None, piste=None):
        self.opreste()
        self.muzica = muzica
        self.metronom = metronom
        self.piste = piste or []      # fiecare mână (portativ) separat, de aceeași lungime ca amestecul
        self.alese = None             # None = toate; altfel indicele mâinii care se aude
        self._poz = 0

    def are(self):
        return self.muzica is not None and len(self.muzica) > 0

    def lungime(self):
        return int(len(self.muzica) * 1000 / RATA) if self.are() else 0

    def _sursa(self, a, b):
        n = len(self.muzica)
        out = np.zeros((b - a, 2), np.float32)
        i, j = max(0, a), min(n, b)
        if j > i:
            sursa = self.piste[self.alese] if self.alese is not None and self.alese < len(self.piste) else self.muzica
            out[i - a:j - a] = sursa[i:j]
            v = self.volum_metronom
            if v > 0 and self.metronom is not None:
                out[i - a:j - a] += (self.metronom[i:j] * (v * 22000.0))[:, None]
        return out

    # ---- comenzi ----
    def pozitie(self):
        if self.stare == 'oprit':
            return 0
        with self._lacat:
            p = self._coada[0][1] if self._coada else self._poz
        return int(p * 1000 / RATA)

    def canta(self, de_la_ms=0, in_pauza=False):
        self.opreste()
        if not self.are():
            return
        self._gen += 1
        gen = self._gen
        self._poz = int(max(0, de_la_ms) * RATA / 1000)
        self._coada = []
        self.stare = 'pauza' if in_pauza else 'canta'
        self._fir = threading.Thread(target=self._bucla, args=(gen,), daemon=True)
        self._fir.start()

    def sari(self, ms):
        self._salt = int(max(0, ms) * RATA / 1000)
        if self.stare == 'pauza':
            with self._lacat:
                self._poz = self._salt
                self._coada = []

    def pauza_continua(self):
        if self.stare == 'canta':
            self.stare = 'pauza'
        elif self.stare == 'pauza':
            self.stare = 'canta'
        return self.stare

    def terminat(self):
        return self.stare == 'oprit'

    def opreste(self):
        self._gen += 1
        self.stare = 'oprit'
        f = self._fir
        if f and f is not threading.current_thread():
            f.join(timeout=1.0)
        self._fir = None

    # ---- firul care hrănește placa de sunet ----
    def _bucla(self, gen):
        if os.name != 'nt':
            return
        try:
            iesire = IesireWaveOut()
        except Exception:
            self.stare = 'oprit'
            return
        intins = Intinzator(self._sursa, len(self.muzica))
        intins.reseteaza(self._poz)
        in_coada = {}                 # bufer -> poziția
        ordine = []
        era_pauza = False
        sfarsit = False
        try:
            while gen == self._gen:
                if self._salt is not None:
                    salt, self._salt = self._salt, None
                    iesire.goleste()
                    in_coada.clear()
                    ordine.clear()
                    intins.reseteaza(salt)
                    sfarsit = False
                    if era_pauza:
                        iesire.pauza()                   # golirea poate porni din nou placa; rămâne în pauză
                    with self._lacat:
                        self._poz = salt
                        self._coada = []
                if self.stare == 'pauza':
                    if not era_pauza:
                        iesire.pauza()
                        era_pauza = True
                    time.sleep(0.02)
                    continue
                if era_pauza:
                    iesire.continua()
                    era_pauza = False
                # bufere terminate
                while ordine and iesire.liber(ordine[0]):
                    i = ordine.pop(0)
                    in_coada.pop(i, None)
                with self._lacat:
                    self._coada = [(i, in_coada[i]) for i in ordine]
                    if not ordine:
                        self._coada = []
                if sfarsit and not ordine:
                    self.stare = 'oprit'
                    if self.la_sfarsit:
                        self.la_sfarsit()
                    return
                umplut = False
                for i in range(NR_BUFERE):
                    if sfarsit or i in in_coada or not iesire.liber(i):
                        continue
                    if intins.gata():
                        sfarsit = True
                        break
                    date, poz = intins.bloc(self.viteza)
                    octeti = np.clip(date, -32768, 32767).astype('<i2').tobytes()
                    iesire.scrie(i, octeti)
                    in_coada[i] = poz
                    ordine.append(i)
                    with self._lacat:
                        self._poz = poz
                    umplut = True
                if not umplut:
                    time.sleep(0.005)
        finally:
            iesire.inchide()
