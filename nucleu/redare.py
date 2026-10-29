"""Redarea cu sunet: din măsurile și portativele alese se face un fișier MIDI temporar,
care se cântă cu sintetizatorul din Windows (prin MCI, fără alte programe).
Se poate încetini sau grăbi tempoul, se poate repeta în buclă și se poate adăuga metronomul
(o pistă de percuție cu bătăile măsurii, deci merge mereu în tempoul melodiei)."""
import copy
import os
import tempfile
import threading
import time

from music21 import bar, meter, repeat, spanner, tempo

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
    """MIDI-ul partiturii la tempoul scris (100%), ca octeți, cu melodia mai tare (mai_tare).
    Se face o singură dată pentru o selecție; la schimbarea tempoului sau a metronomului
    se modifică doar octeții, fără music21."""
    cale = fa_midi(scor, 100)
    try:
        with open(cale, 'rb') as f:
            return mai_tare(f.read())
    finally:
        try:
            os.remove(cale)
        except OSError:
            pass


def batai(scor):
    """Bătăile metronomului pentru partitură: listă de (poziția în pătrimi, e_prima_din_masura).
    Repetițiile se desfac la fel ca la MIDI, ca bătăile să cadă pe muzică. La anacruză,
    bătăile se numără de la bara de măsură înapoi."""
    try:
        s = scor.expandRepeats()
    except Exception:
        s = scor
    prima = s.parts[0] if s.parts else s
    masuri = list(prima.getElementsByClass('Measure'))
    rez = []
    ts = None
    for i, m in enumerate(masuri):
        gasit = m.getElementsByClass(meter.TimeSignature)
        if gasit:
            ts = gasit[0]
        elif ts is None:
            ts = m.getContextByClass(meter.TimeSignature) or meter.TimeSignature('4/4')
        bata = float(ts.beatDuration.quarterLength) or 1.0
        plina = float(ts.barDuration.quarterLength)
        start = float(m.offset)
        lung = float(m.duration.quarterLength) or plina
        if lung < plina - 1e-6 and i == 0:
            # anacruza: bătăile sunt cele de la sfârșitul măsurii
            sfarsit = start + lung
            k = 1
            poz = []
            while sfarsit - k * bata >= start - 1e-6:
                poz.append(sfarsit - k * bata)
                k += 1
            rez.extend((max(start, p), False) for p in reversed(poz))
            continue
        k = 0
        while start + k * bata < start + lung - 1e-6:
            rez.append((start + k * bata, k == 0))
            k += 1
    return rez


def masuri(scor):
    """(poziția în pătrimi, numărul măsurii) pentru fiecare măsură, cu repetițiile desfăcute ca la MIDI și la metronom."""
    try:
        s = scor.expandRepeats()
    except Exception:
        s = scor
    prima = s.parts[0] if s.parts else s
    return [(float(m.offset), m.number) for m in prima.getElementsByClass('Measure')]


def milisecunde(date: bytes, patrimi):
    """Pentru fiecare poziție în pătrimi, momentul ei în milisecunde în MIDI-ul dat (după harta lui de tempo)."""
    _fmt, div, piste = _citeste(date)
    tempo_ = sorted((t, int.from_bytes(ev[3:6], 'big')) for p in piste for t, ev in p
                    if len(ev) >= 6 and ev[0] == 0xFF and ev[1] == 0x51)
    rez = []
    for q in patrimi:
        tinta = q * div
        ms, ultim, us = 0.0, 0, 500000
        for t, u in tempo_:
            if t >= tinta:
                break
            ms += (t - ultim) * us / div / 1000
            ultim, us = t, u
        ms += (tinta - ultim) * us / div / 1000
        rez.append(int(ms))
    return rez


# ---------------- MIDI ca listă de evenimente ----------------
def _citeste(date: bytes):
    """(format, diviziune, piste); fiecare pistă e o listă de (tick absolut, octeții evenimentului)."""
    b = bytes(date)
    if b[:4] != b'MThd':
        raise ValueError('nu e MIDI')
    hl = int.from_bytes(b[4:8], 'big')
    fmt = int.from_bytes(b[8:10], 'big')
    div = int.from_bytes(b[12:14], 'big')
    i = 8 + hl
    piste = []
    while i + 8 <= len(b):
        tip = b[i:i + 4]
        lung = int.from_bytes(b[i + 4:i + 8], 'big')
        start, sfarsit = i + 8, min(len(b), i + 8 + lung)
        if tip == b'MTrk':
            ev, j, t, stare = [], start, 0, 0
            while j < sfarsit:
                d, j = _vlq(b, j)
                t += d
                if j >= sfarsit:
                    break
                s0 = b[j]
                if s0 == 0xFF:
                    n, k = _vlq(b, j + 2)
                    ev.append((t, b[j:k + n]))
                    j = k + n
                elif s0 in (0xF0, 0xF7):
                    n, k = _vlq(b, j + 1)
                    ev.append((t, b[j:k + n]))
                    j = k + n
                else:
                    if s0 & 0x80:
                        stare = s0
                        j += 1
                    n = 1 if (stare & 0xF0) in (0xC0, 0xD0) else 2
                    ev.append((t, bytes([stare]) + b[j:j + n]))
                    j += n
            piste.append(ev)
        i = sfarsit
    return fmt, div, piste


def _vlq_scrie(v):
    o = [v & 0x7F]
    v >>= 7
    while v:
        o.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(reversed(o))


def _scrie(fmt, div, piste) -> bytes:
    out = bytearray(b'MThd' + (6).to_bytes(4, 'big') + (1 if len(piste) > 1 else fmt).to_bytes(2, 'big')
                    + len(piste).to_bytes(2, 'big') + div.to_bytes(2, 'big'))
    for ev in piste:
        corp = bytearray()
        t0 = 0
        fin = False
        for t, e in ev:
            if e[:2] == b'\xff\x2f':
                fin = True
            corp += _vlq_scrie(max(0, t - t0)) + e
            t0 = max(t0, t)
        if not fin:
            corp += b'\x00\xff\x2f\x00'
        out += b'MTrk' + len(corp).to_bytes(4, 'big') + corp
    return bytes(out)


def _fara_sfarsit(ev):
    """Scoate „sfârșitul pistei” (se pune la loc la scriere, după ultimul eveniment)."""
    return [(t, e) for t, e in ev if e[:2] != b'\xff\x2f']


def mai_tare(date: bytes) -> bytes:
    """Melodia mai tare: volumul canalelor la maxim (controlerele 7 și 11) și notele lovite mai tare (cu 40%),
    fără să se piardă diferența dintre piano și forte."""
    try:
        fmt, div, piste = _citeste(date)
    except Exception:
        return date
    noi = []
    for ev in piste:
        canale = sorted({e[0] & 0x0F for _, e in ev if 0x80 <= e[0] < 0xF0})
        rez = []
        for c in canale:
            rez.append((0, bytes([0xB0 | c, 7, 127])))
            rez.append((0, bytes([0xB0 | c, 11, 127])))
        for t, e in _fara_sfarsit(ev):
            if (e[0] & 0xF0) == 0x90 and len(e) == 3 and e[2] > 0:
                e = bytes([e[0], e[1], min(127, round(e[2] * 1.4))])
            elif (e[0] & 0xF0) == 0xB0 and len(e) == 3 and e[1] in (7, 11):
                continue                       # volumul rămâne la maxim
            rez.append((t, e))
        rez.sort(key=lambda x: x[0])           # stabil: controlerele de la 0 rămân înaintea notelor
        noi.append(rez)
    return _scrie(fmt, div, noi)


NOTA_ACCENT = 76       # Hi Wood Block (prima bătaie din măsură)
NOTA_BATAIE = 77       # Low Wood Block


def vel_dublura(volum, prima=False) -> int:
    """Peste 100 la sută metronomul e mai tare: aceeași lovitură se mai trimite o dată, în același moment,
    cu tăria aceasta (0 = fără dublură). La 200 la sută sunt două lovituri întregi."""
    if volum <= 100:
        return 0
    v = max(1, min(127, round(127 * (volum - 100) / 100)))
    return min(127, v + 12) if prima else v


def cu_metronom(date: bytes, lista_batai, volum: int) -> bytes:
    """Adaugă pista metronomului (canalul 10, percuție). volum: 0–200 la sută (peste 100 lovitura se dublează).
    Tempoul vine din aceeași hartă de tempo ca melodia, deci metronomul merge mereu odată cu ea."""
    if not lista_batai or volum <= 0:
        return date
    fmt, div, piste = _citeste(date)
    vel = max(1, min(127, round(127 * volum / 100)))
    accent = min(127, vel + 12)
    scurt = max(1, div // 8)
    ev = [(0, bytes([0xB9, 7, 127])), (0, bytes([0xB9, 11, 127]))]
    for poz, prima in lista_batai:
        t = int(round(poz * div))
        ev.append((t, bytes([0x99, NOTA_ACCENT if prima else NOTA_BATAIE, accent if prima else vel])))
        dublu = vel_dublura(volum, prima)
        if dublu:
            ev.append((t, bytes([0x99, NOTA_ACCENT if prima else NOTA_BATAIE, dublu])))
        ev.append((t + scurt, bytes([0x89, NOTA_ACCENT if prima else NOTA_BATAIE, 0])))
    ev.sort(key=lambda x: x[0])
    return _scrie(1, div, piste + [ev])


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


def cu_program(date: bytes, prog) -> bytes:
    """Schimbă instrumentul (programul General MIDI și banca) pe toate canalele, afară de tobe (canalul 10)."""
    banca, program = (0, prog) if isinstance(prog, int) else (int(prog[0]), int(prog[1]))
    if banca >= 128:
        return date                       # setul de tobe nu se poate pune peste melodie
    fmt, div, piste = _citeste(date)
    noi = []
    for p in piste:
        ev = []
        for t, e in p:
            if len(e) == 2 and (e[0] & 0xF0) == 0xC0 and (e[0] & 0x0F) != 9:
                c = e[0] & 0x0F
                ev.append((t, bytes([0xB0 | c, 0, min(127, banca)])))
                ev.append((t, bytes([0xC0 | c, program & 0x7F])))
            else:
                ev.append((t, e))
        noi.append(ev)
    return _scrie(fmt, div, noi)


def fara_repetitii(s):
    """O copie fără repetiții și volte: măsurile se cântă o singură dată, în ordinea în care sunt scrise.
    (Copia e necesară: bucata din extrage() are aceleași măsuri ca partitura deschisă.)"""
    s = copy.deepcopy(s)
    for b in list(s.recurse().getElementsByClass(bar.Repeat)):
        m = b.activeSite
        if m is not None:
            if getattr(m, 'rightBarline', None) is b:
                m.rightBarline = None
            elif getattr(m, 'leftBarline', None) is b:
                m.leftBarline = None
            else:
                m.remove(b)
    for sp in list(s.recurse().getElementsByClass(spanner.RepeatBracket)):
        for loc in list(sp.sites.get()):
            try:
                loc.remove(sp)
            except Exception:
                pass
    for p in getattr(s, 'parts', []):
        for sp in list(p.spanners.getElementsByClass(spanner.RepeatBracket)):
            p.remove(sp)
    for ex in list(s.recurse().getElementsByClass(repeat.RepeatExpression)):
        if ex.activeSite is not None:
            ex.activeSite.remove(ex)
    return s


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

    def terminat(self) -> bool:
        """Adevărat dacă piesa a ajuns la sfârșit, chiar dacă urmărirea n-a observat încă (atunci K o ia de la capăt)."""
        if self.stare == 'oprit':
            return True
        if os.name != 'nt':
            return False
        try:
            mod = self._mci(f'status {_ALIAS} mode')
            poz = int(self._mci(f'status {_ALIAS} position') or 0)
            lung = int(self._mci(f'status {_ALIAS} length') or 0)
        except Exception:
            return True
        if self.stare == 'canta' and mod not in ('playing', 'seeking'):
            return True
        return lung > 0 and poz >= lung - 30

    def sari(self, ms: int):
        """Mută redarea la momentul dat (în milisecunde), fără s-o oprească; în pauză rămâne în pauză."""
        if self.stare == 'canta':
            self._mci(f'play {_ALIAS} from {max(0, int(ms))}')
        elif self.stare == 'pauza':
            self._mci(f'seek {_ALIAS} to {max(0, int(ms))}')

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
