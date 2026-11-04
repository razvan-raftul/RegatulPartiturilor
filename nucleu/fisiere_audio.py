"""Fila Fișiere audio: un folder de pe calculator, cu subfolderele lui ca într-un arbore, și fișierele audio
care se aud imediat ce ajungi pe ele cu săgețile. Sunetul trece prin MCI (mpegvideo, ce poate Windows să cânte:
mp3, wav, wma, m4a, aac; flac și ogg doar dacă Windows are codecurile lor)."""
import os
import re
import shutil
import subprocess
import threading
import time

import numpy as np

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
    return sorted(dirs, key=ordine_naturala), sorted(fis, key=ordine_naturala)


def ordine_naturala(cale):
    """Numerele din nume se compară ca numere: 1, 2, 3 … 10, 11, nu 1, 10, 11, 2."""
    nume = os.path.basename(cale).lower()
    return [(0, int(x), '') if x.isdigit() else (1, 0, x) for x in re.split(r'(\d+)', nume) if x != '']


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


class MelodieMCI:
    """Prin MCI (rămâne pentru fișierele MIDI și când lipsește ffmpeg). stare: oprit / canta / pauza."""

    def __init__(self):
        self.stare = 'oprit'
        self.cale = None
        self.la_sfarsit = None
        self.volum = 100                 # 0–100 la sută
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
            self._aplica_volum()
            self._mci(f'play {_ALIAS} from {max(0, int(de_la_ms))}')
            self.stare = 'canta'
            self._gen += 1
            gen = self._gen
        threading.Thread(target=self._urmareste, args=(gen,), daemon=True).start()

    def _urmareste(self, gen):
        ultima, pe_loc = -1, 0.0
        while gen == self._gen and self.stare != 'oprit':
            time.sleep(0.2)
            if self.stare != 'canta':
                pe_loc = 0.0
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
            # sfârșitul: MCI spune „stopped”, sau poziția a ajuns la capăt, sau poziția nu mai merge de o secundă
            pe_loc = pe_loc + 0.2 if poz == ultima else 0.0
            ultima = poz
            if mod == 'stopped' or (lung and poz >= lung - 250 and pe_loc >= 0.4) or (poz > 0 and pe_loc >= 1.5):
                if gen != self._gen:
                    return
                self.stare = 'oprit'
                if self.la_sfarsit:
                    self.la_sfarsit()
                return

    def _aplica_volum(self):
        try:
            self._mci(f'setaudio {_ALIAS} volume to {int(self.volum) * 10}')     # MCI: 0–1000
        except Exception:
            pass                          # MIDI (sequencer) nu are volum prin MCI

    def schimba_volum(self, pas):
        self.volum = max(0, min(100, self.volum + pas))
        if self.stare != 'oprit':
            with self._lacat:
                self._aplica_volum()
        return self.volum

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


# ---------------- redarea prin placa de sunet, cu tempo și înălțime ----------------
def cale_ffmpeg():
    """ffmpeg.exe: în folderul sunete (vine cu programul), altfel cel din PATH."""
    try:
        from . import sunete
        d = sunete.folder_sunete()
        for c in (os.path.join(d, 'ffmpeg', 'ffmpeg.exe'), os.path.join(d, 'ffmpeg.exe')):
            if os.path.isfile(c):
                return c
    except Exception:
        pass
    return shutil.which('ffmpeg')


def e_midi(cale):
    return cale.lower().endswith(('.mid', '.midi'))


class MelodieFlux:
    """Fișierul e decodat de ffmpeg (în fundal, cât se cântă deja) și cântat prin waveOut.
    Tempoul se schimbă fără să se schimbe înălțimea (WSOLA, ca în Player), iar înălțimea în semitonuri
    fără să se schimbe tempoul (WSOLA plus reeșantionare). Pozițiile sunt în milisecunde ale fișierului."""

    def __init__(self):
        self.stare = 'oprit'
        self.cale = None
        self.la_sfarsit = None
        self.volum = 100
        self.viteza = 1.0
        self.semitonuri = 0
        self._gen = 0
        self._fir = None
        self._salt = None
        self._lacat = threading.Lock()
        self._coada = []
        self._poz = 0
        self._date = np.zeros((0, 2), np.int16)
        self._n = 0
        self._decodat = False
        self._eroare = ''
        self._durata_ms = 0
        self._proc = None
        self._gen_dec = 0

    # ---- decodarea ----
    def _opreste_decodarea(self):
        self._gen_dec += 1
        p, self._proc = self._proc, None
        if p:
            try:
                p.kill()
            except Exception:
                pass

    def _decodeaza(self, cale):
        from .inregistrare import RATA
        self._opreste_decodarea()
        gen = self._gen_dec
        self._date = np.zeros((RATA * 60, 2), np.int16)
        self._n, self._decodat, self._eroare, self._durata_ms = 0, False, '', 0
        ff = cale_ffmpeg()
        if not ff:
            raise RuntimeError('ffmpeg lipsește')
        flags = 0x08000000 if os.name == 'nt' else 0          # CREATE_NO_WINDOW
        p = subprocess.Popen([ff, '-hide_banner', '-nostdin', '-i', cale, '-vn', '-f', 's16le', '-acodec', 'pcm_s16le',
                              '-ac', '2', '-ar', str(RATA), '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, creationflags=flags)
        self._proc = p

        def err():
            txt = b''
            for linie in p.stderr:
                txt += linie
                m = re.search(rb'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', linie)
                if m and not self._durata_ms:
                    self._durata_ms = int((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) * 1000)
            linii = txt.decode('utf-8', 'replace').strip().splitlines()
            if gen == self._gen_dec and linii:
                self._eroare = linii[-1]

        def out():
            rest = b''
            try:
                while gen == self._gen_dec:
                    b = p.stdout.read(RATA)          # ~0,25 secunde
                    if not b:
                        break
                    b = rest + b
                    k = len(b) // 4 * 4
                    rest = b[k:]
                    a = np.frombuffer(b[:k], '<i2').reshape(-1, 2)
                    d, n = self._date, self._n
                    if n + len(a) > len(d):
                        nou = np.zeros((max(len(d) * 2, n + len(a)), 2), np.int16)
                        nou[:n] = d[:n]
                        d = nou
                    d[n:n + len(a)] = a
                    if gen != self._gen_dec:
                        break
                    self._date = d
                    self._n = n + len(a)
            finally:
                if gen == self._gen_dec:
                    self._decodat = True
        threading.Thread(target=err, daemon=True).start()
        threading.Thread(target=out, daemon=True).start()
        t0 = time.time()                       # așteptăm puțin primul sunet (sau eroarea)
        while time.time() - t0 < 4 and not self._decodat and self._n < RATA // 4:
            time.sleep(0.01)
        if self._decodat and self._n == 0:
            raise RuntimeError(self._eroare or 'fișierul nu are sunet')

    def _sursa(self, a, b):
        d, n = self._date, self._n
        out = np.zeros((b - a, 2), np.float32)
        i, j = max(0, a), min(n, b)
        if j > i:
            out[i - a:j - a] = d[i:j]
        return out

    # ---- comenzi ----
    def deschide_si_canta(self, cale, de_la_ms=0):
        self.opreste()
        if cale != self.cale or not (self._decodat or self._proc):
            self.cale = None
            self._decodeaza(cale)
            self.cale = cale
        self._porneste(de_la_ms)

    def _porneste(self, de_la_ms):
        from .inregistrare import RATA
        self._gen += 1
        self._poz = int(max(0, de_la_ms) * RATA / 1000)
        self._coada = []
        self._salt = None
        self.stare = 'canta'
        self._fir = threading.Thread(target=self._bucla, args=(self._gen,), daemon=True)
        self._fir.start()

    def pozitie(self):
        from .inregistrare import RATA
        if self.stare == 'oprit':
            return 0
        with self._lacat:
            p = self._coada[0][1] if self._coada else self._poz
        return int(p * 1000 / RATA)

    def lungime(self):
        from .inregistrare import RATA
        n = int(self._n * 1000 / RATA)
        return n if self._decodat else max(n, self._durata_ms)

    def pauza_continua(self):
        if self.stare == 'canta':
            self.stare = 'pauza'
        elif self.stare == 'pauza':
            self.stare = 'canta'
        return self.stare

    def sari(self, ms):
        from .inregistrare import RATA
        if self.stare == 'oprit':
            return
        self._salt = int(max(0, ms) * RATA / 1000)
        if self.stare == 'pauza':
            with self._lacat:
                self._poz = self._salt
                self._coada = []

    def de_la_capat(self):
        if not self.cale:
            return
        if self.stare != 'oprit':
            self.sari(0)
            self.stare = 'canta'
        else:
            self.deschide_si_canta(self.cale)

    def opreste(self):
        self._gen += 1
        self.stare = 'oprit'
        f = self._fir
        if f and f is not threading.current_thread():
            f.join(timeout=1.0)
        self._fir = None

    def inchide(self):
        self.opreste()
        self._opreste_decodarea()
        self.cale = None

    # ---- firul care hrănește placa de sunet ----
    def _generator(self):
        """Un generator de bucăți (HOP cadre float32, poziția în fișier); None = trebuie așteptat decodarea."""
        from .inregistrare import FRAME, HOP, TOL, Intinzator
        intins = Intinzator(self._sursa, 1 << 62)
        stare = {'y': np.zeros((0, 2), np.float32), 'yp': np.zeros(0), 'r': 0.0}

        def reset(poz):
            intins.reseteaza(poz)
            stare['y'] = np.zeros((0, 2), np.float32)
            stare['yp'] = np.zeros(0)
            stare['r'] = 0.0

        def poate(viteza):
            if self._decodat:
                return True
            return intins.poz + TOL + FRAME + HOP * viteza + 2 < self._n

        def gata():
            return self._decodat and intins.poz >= self._n

        def bloc():
            t = self.viteza
            p = 2.0 ** (self.semitonuri / 12.0)
            if abs(p - 1.0) < 1e-6:
                if len(stare['y']):
                    reset(int(stare['yp'][0]))
                if gata():
                    return 'gata'
                if not poate(t):
                    return None
                return intins.bloc(t)
            vw = t / p
            y, yp, r = stare['y'], stare['yp'], stare['r']
            nevoie = int(r + p * HOP) + 2
            while len(y) < nevoie:
                if gata():
                    return 'gata'
                if not poate(vw):
                    stare['y'], stare['yp'] = y, yp
                    return None
                d, s = intins.bloc(vw)
                y = np.concatenate([y, d])
                yp = np.concatenate([yp, s + np.arange(HOP) * vw])
            idx = r + p * np.arange(HOP)
            i0 = idx.astype(np.int64)
            fr = (idx - i0)[:, None].astype(np.float32)
            out = y[i0] * (1 - fr) + y[i0 + 1] * fr
            poz = int(yp[int(r)])
            r += p * HOP
            k = int(r)
            stare['y'], stare['yp'], stare['r'] = y[k:], yp[k:], r - k
            return out, poz
        return bloc, reset

    def _bucla(self, gen):
        if os.name != 'nt':
            return self._bucla_fara_placa(gen)
        from .inregistrare import NR_BUFERE, IesireWaveOut
        try:
            iesire = IesireWaveOut()
        except Exception:
            self.stare = 'oprit'
            return
        bloc, reset = self._generator()
        reset(self._poz)
        in_coada, ordine = {}, []
        era_pauza = sfarsit = False
        try:
            while gen == self._gen:
                if self._salt is not None:
                    salt, self._salt = self._salt, None
                    iesire.goleste()
                    in_coada.clear()
                    ordine.clear()
                    reset(salt)
                    sfarsit = False
                    if era_pauza:
                        iesire.pauza()
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
                while ordine and iesire.liber(ordine[0]):
                    in_coada.pop(ordine.pop(0), None)
                with self._lacat:
                    self._coada = [(i, in_coada[i]) for i in ordine]
                if sfarsit and not ordine:
                    self.stare = 'oprit'
                    if self.la_sfarsit:
                        self.la_sfarsit()
                    return
                umplut = False
                for i in range(NR_BUFERE):
                    if sfarsit or i in in_coada or not iesire.liber(i):
                        continue
                    b = bloc()
                    if b == 'gata':
                        sfarsit = True
                        break
                    if b is None:
                        break
                    date, poz = b
                    g = max(0, min(100, self.volum)) / 100.0
                    octeti = np.clip(date * g, -32768, 32767).astype('<i2').tobytes()
                    iesire.scrie(i, octeti)
                    in_coada[i] = poz
                    ordine.append(i)
                    umplut = True
                    with self._lacat:
                        self._poz = poz
                if not umplut:
                    time.sleep(0.005)
        finally:
            iesire.inchide()

    def _bucla_fara_placa(self, gen):
        """Pentru probe (fără Windows): aceeași generare, fără sunet."""
        bloc, reset = self._generator()
        reset(self._poz)
        self.iesire_proba = []
        while gen == self._gen:
            if self._salt is not None:
                salt, self._salt = self._salt, None
                reset(salt)
            if self.stare == 'pauza':
                time.sleep(0.01)
                continue
            b = bloc()
            if b == 'gata':
                self.stare = 'oprit'
                if self.la_sfarsit:
                    self.la_sfarsit()
                return
            if b is None:
                time.sleep(0.005)
                continue
            self.iesire_proba.append(b[0])
            with self._lacat:
                self._poz = b[1]


class Melodie:
    """Fila Muzică: un singur fișier la un moment dat. Fișierele audio merg prin MelodieFlux (tempo și înălțime),
    MIDI (și totul, dacă lipsește ffmpeg) prin MCI. stare: oprit / canta / pauza. la_sfarsit() se cheamă din alt fir."""
    TEMPO_MIN, TEMPO_MAX = 50, 200          # la sută din tempoul fișierului (intern)
    SEMITONURI_MAX = 12

    def __init__(self):
        self._mci = MelodieMCI()
        self._flux = MelodieFlux()
        self._act = self._flux
        self._volum = 100
        self.tempo = 100
        self.semitonuri = 0
        self._la_sfarsit = None

    @property
    def la_sfarsit(self):
        return self._la_sfarsit

    @la_sfarsit.setter
    def la_sfarsit(self, f):
        self._la_sfarsit = f
        self._mci.la_sfarsit = f
        self._flux.la_sfarsit = f

    @property
    def volum(self):
        return self._volum

    @volum.setter
    def volum(self, v):
        self._volum = int(v)
        self._mci.volum = self._volum
        self._flux.volum = self._volum

    @property
    def stare(self):
        return self._act.stare

    @property
    def cale(self):
        return self._act.cale

    def cu_flux(self):
        """True dacă fișierul de acum (sau următorul) poate avea tempo și înălțime schimbate."""
        return self._act is self._flux

    def deschide_si_canta(self, cale, de_la_ms=0):
        flux = not e_midi(cale) and bool(cale_ffmpeg())
        nou = self._flux if flux else self._mci
        vechi = self._mci if flux else self._flux
        vechi.opreste()
        if vechi is self._flux:
            self._flux.inchide()
        self._act = nou
        self._flux.viteza = self.tempo / 100.0
        self._flux.semitonuri = self.semitonuri
        nou.deschide_si_canta(cale, de_la_ms)

    def schimba_volum(self, pas):
        self.volum = max(0, min(100, self._volum + pas))
        if self._act is self._mci and self._mci.stare != 'oprit':
            with self._mci._lacat:
                self._mci._aplica_volum()
        return self._volum

    def schimba_tempo(self, pas):
        self.tempo = max(self.TEMPO_MIN, min(self.TEMPO_MAX, self.tempo + pas))
        self._flux.viteza = self.tempo / 100.0
        return self.tempo

    def schimba_inaltime(self, pas):
        self.semitonuri = max(-self.SEMITONURI_MAX, min(self.SEMITONURI_MAX, self.semitonuri + pas))
        self._flux.semitonuri = self.semitonuri
        return self.semitonuri

    def pozitie(self):
        return self._act.pozitie()

    def lungime(self):
        return self._act.lungime()

    def pauza_continua(self):
        return self._act.pauza_continua()

    def sari(self, ms):
        self._act.sari(ms)

    def de_la_capat(self):
        self._act.de_la_capat()

    def opreste(self):
        self._act.opreste()
        self._flux.inchide()          # oprește și ffmpeg, dacă încă decodează
