"""Încărcarea unei partituri și accesul la portative și măsuri."""
import copy
import os
from dataclasses import dataclass

from music21 import converter, instrument, key, layout, meter, stream, tempo

from . import cuvinte, recunoastere

FORMATE_DIRECTE = ('.musicxml', '.xml', '.mxl', '.mid', '.midi', '.abc', '.krn', '.mei')
FORMATE_MUSESCORE = ('.mscz', '.mscx')
FORMATE_IMAGINE = ('.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')
TOATE_FORMATELE = FORMATE_DIRECTE + FORMATE_MUSESCORE + FORMATE_IMAGINE


class EroarePartitura(Exception):
    pass


@dataclass
class Portativ:
    nume: str
    parte: stream.Part


def _e_pian(p) -> bool:
    ins = p.getInstrument(returnDefault=False)
    if ins is not None and isinstance(ins, (instrument.KeyboardInstrument,)):
        return True
    n = (p.partName or '').lower()
    return any(x in n for x in ('piano', 'pian', 'klavier', 'keyboard', 'organ', 'orgă', 'harpsichord', 'clavecin'))


def numeste_portative(scor) -> list:
    """Dă nume portativelor: la pian Mâna dreaptă / Mâna stângă, altfel numele partidei."""
    parti = list(scor.parts)
    rez = []
    grupuri = {}
    for sg in scor.getElementsByClass(layout.StaffGroup):
        membri = [p for p in parti if sg.hasSpannedElement(p)]
        for p in membri:
            grupuri[id(p)] = membri
    folosite = set()
    i = 0
    while i < len(parti):
        p = parti[i]
        grup = grupuri.get(id(p))
        if grup is None and isinstance(p, stream.PartStaff):
            # PartStaff consecutive fără StaffGroup: le tratăm ca un singur instrument
            grup = [p]
            j = i + 1
            while j < len(parti) and isinstance(parti[j], stream.PartStaff):
                grup.append(parti[j]); j += 1
        if grup is None and i == 0 and len(parti) == 2 and (all(_e_pian(x) for x in parti) or parti[0].partName == parti[1].partName):
            grup = parti   # de exemplu un MIDI de pian cu două piste
            if not all(isinstance(g, stream.PartStaff) for g in grup):
                rez = [Portativ('Mâna dreaptă', parti[0]), Portativ('Mâna stângă', parti[1])]
                break
        if grup and 2 <= len(grup) <= 3 and all(isinstance(g, stream.PartStaff) for g in grup) and id(p) not in folosite:
            nume_baza = '' if len(parti) == len(grup) else (p.partName or 'Pian') + ', '
            for k, g in enumerate(grup):
                if k == 0:
                    n = 'Mâna dreaptă'
                elif k == 1:
                    n = 'Mâna stângă'
                else:
                    n = f'Portativul {k + 1}'
                rez.append(Portativ(nume_baza + n, g)); folosite.add(id(g))
            i += len(grup)
            continue
        if id(p) in folosite:
            i += 1; continue
        n = p.partName or f'Partida {len(rez) + 1}'
        if len(parti) == 1 and not p.partName:
            n = 'Melodia'
        rez.append(Portativ(n, p)); folosite.add(id(p))
        i += 1
    return rez


class Partitura:
    def __init__(self, scor, cale: str, avertismente=None):
        self.scor = scor
        self.cale = cale
        self.avertismente = list(avertismente or [])
        self.portative = numeste_portative(scor)
        if not self.portative:
            raise EroarePartitura('Partitura nu are nicio portativă cu note.')
        prima = self.portative[0].parte
        self.numere = []
        for m in prima.getElementsByClass(stream.Measure):
            if m.number not in self.numere:
                self.numere.append(m.number)
        if not self.numere:
            # MIDI sau ABC fără măsuri: le facem noi
            self.scor = scor.makeMeasures() if not scor.hasMeasures() else scor
            self.portative = numeste_portative(self.scor)
            prima = self.portative[0].parte
            self.numere = [m.number for m in prima.getElementsByClass(stream.Measure)]

    # ---------- informații generale ----------
    @property
    def titlu(self) -> str:
        md = self.scor.metadata
        t = (md.title or md.movementName) if md else None
        return t or os.path.splitext(os.path.basename(self.cale))[0]

    @property
    def compozitor(self) -> str:
        md = self.scor.metadata
        return (md.composer or '') if md else ''

    def descriere_generala(self) -> str:
        r = [self.titlu + '.']
        if self.compozitor:
            r.append('Compozitor: ' + self.compozitor + '.')
        prima = self.portative[0].parte
        ks = prima.recurse().getElementsByClass(key.KeySignature).first()
        if ks is not None:
            r.append('Tonalitatea: ' + cuvinte.nume_tonalitate(ks) + '.')
        try:
            est = self.scor.analyze('key')
            r.append('Tonalitatea estimată din note: ' + cuvinte.nume_tonalitate(est) + '.')
        except Exception:
            pass
        ts = prima.recurse().getElementsByClass(meter.TimeSignature).first()
        if ts is not None:
            r.append('Măsura de ' + cuvinte.text_masura_timp(ts) + '.')
        mm = self.scor.recurse().getElementsByClass(tempo.MetronomeMark).first()
        if mm is not None:
            t = [x for x in (mm.text, f'{int(mm.number)} pe minut' if mm.number else '') if x]
            if t:
                r.append('Tempo: ' + ', '.join(str(x) for x in t) + '.')
        n = len([x for x in self.numere if x])
        r.append(f'{n} măsuri' + (', cu măsură de anacruză' if 0 in self.numere else '') + '.')
        r.append('Portative: ' + ', '.join(p.nume for p in self.portative) + '.')
        for a in self.avertismente:
            r.append(a)
        return ' '.join(r)

    # ---------- în cuvinte ----------
    def descrie(self, prima: int, ultima: int, portative: list, opt: cuvinte.Optiuni) -> str:
        """Textul pentru măsurile de la `prima` la `ultima` (numere de măsură) și portativele alese (indici)."""
        linii = []
        for nr in self.numere:
            if nr < prima or nr > ultima:
                continue
            m0 = self.portative[portative[0]].parte.measure(nr) if portative else None
            cap = 'Anacruza.' if nr == 0 else f'Măsura {nr}.'
            ev = []
            if m0 is not None:
                ev = cuvinte._evenimente_masura(m0, opt)
                bl = cuvinte.text_barline(m0)
            else:
                bl = []
            if ev:
                t = ', '.join(ev)
                cap += ' ' + t[0].upper() + t[1:] + '.'
            linii.append(cap)
            for i in portative:
                pt = self.portative[i]
                m = pt.parte.measure(nr)
                if m is None:
                    continue
                linii.append(f'{pt.nume}: ' + cuvinte.descrie_masura_portativ(m, opt) + '.')
            if bl:
                linii.append(' '.join(x[0].upper() + x[1:] + '.' for x in bl))
            linii.append('')
        return '\n'.join(linii).strip()

    # ---------- Braille ----------
    def extrage(self, prima: int, ultima: int, portative: list):
        """O copie cu doar măsurile și portativele alese (pentru Braille și export)."""
        sc = stream.Score()
        if self.scor.metadata is not None:
            sc.metadata = copy.deepcopy(self.scor.metadata)
        for i in portative:
            p = self.portative[i].parte
            bucata = p.measures(prima, ultima)
            cls = stream.PartStaff if isinstance(p, stream.PartStaff) else stream.Part
            np_ = cls()
            np_.partName = p.partName
            for el in bucata.elements:
                np_.append(el)
            sc.insert(0, np_)
        return sc


def incarca(cale: str, progres=None) -> Partitura:
    ext = os.path.splitext(cale)[1].lower()
    avert = []
    if ext in FORMATE_MUSESCORE:
        cale_xml = recunoastere.din_musescore(cale)
        scor = converter.parse(cale_xml)
    elif ext in FORMATE_IMAGINE:
        fisiere = recunoastere.din_imagine(cale, progres)
        scor = converter.parse(fisiere[0])
        avert.append('Partitura a fost recunoscută dintr-o imagine sau un PDF, deci pot exista greșeli. Verifică pasajele care sună ciudat.')
        if len(fisiere) > 1:
            avert.append(f'Recunoașterea a găsit {len(fisiere)} părți separate; am deschis-o pe prima. Celelalte sunt în același folder cu partitura.')
    elif ext in FORMATE_DIRECTE:
        scor = converter.parse(cale)
    else:
        raise EroarePartitura('Formatul acesta nu e cunoscut. Merg: MusicXML, MXL, MIDI, MuseScore, PDF și imagini.')
    if isinstance(scor, stream.Opus):
        scor = scor.scores[0]
        avert.append('Fișierul are mai multe piese; am deschis-o pe prima.')
    if not isinstance(scor, stream.Score):
        s = stream.Score(); s.insert(0, scor); scor = s
    return Partitura(scor, cale, avert)
