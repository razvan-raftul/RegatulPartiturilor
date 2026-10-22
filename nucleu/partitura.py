"""Încărcarea unei partituri și accesul la portative și măsuri."""
import copy
import os
from dataclasses import dataclass

from music21 import converter, instrument, key, layout, meter, stream, tempo

from . import cuvinte, recunoastere
from .limba import _

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
                rez = [Portativ(_('Mâna dreaptă'), parti[0]), Portativ(_('Mâna stângă'), parti[1])]
                break
        if grup and 2 <= len(grup) <= 3 and all(isinstance(g, stream.PartStaff) for g in grup) and id(p) not in folosite:
            nume_baza = '' if len(parti) == len(grup) else (p.partName or _('Pian')) + ', '
            for k, g in enumerate(grup):
                if k == 0:
                    n = _('Mâna dreaptă')
                elif k == 1:
                    n = _('Mâna stângă')
                else:
                    n = _('Portativul {0}', k + 1)
                rez.append(Portativ(nume_baza + n, g)); folosite.add(id(g))
            i += len(grup)
            continue
        if id(p) in folosite:
            i += 1; continue
        n = p.partName or _('Partida {0}', len(rez) + 1)
        if len(parti) == 1 and not p.partName:
            n = _('Melodia')
        rez.append(Portativ(n, p)); folosite.add(id(p))
        i += 1
    return rez


class Partitura:
    def __init__(self, scor, cale: str, avertismente=None):
        self.scor = scor
        self.cale = cale
        self.avertismente = list(avertismente or [])
        self.nesigure = {}             # {număr măsură: motiv} la partiturile recunoscute din imagini
        self.portative = numeste_portative(scor)
        if not self.portative:
            raise EroarePartitura(_('Partitura nu are nicio portativă cu note.'))
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
            r.append(_('Compozitor: ') + self.compozitor + '.')
        prima = self.portative[0].parte
        ks = prima.recurse().getElementsByClass(key.KeySignature).first()
        if ks is not None:
            r.append(_('Tonalitatea: ') + cuvinte.nume_tonalitate(ks) + '.')
        try:
            est = self.scor.analyze('key')
            r.append(_('Tonalitatea estimată din note: ') + cuvinte.nume_tonalitate(est) + '.')
        except Exception:
            pass
        ts = prima.recurse().getElementsByClass(meter.TimeSignature).first()
        if ts is not None:
            r.append(_('Măsura de ') + cuvinte.text_masura_timp(ts) + '.')
        mm = self.scor.recurse().getElementsByClass(tempo.MetronomeMark).first()
        if mm is not None:
            t = cuvinte.text_tempo(mm)
            if t:
                r.append(_('Tempo: ') + ', '.join(str(x) for x in t) + '.')
        n = len([x for x in self.numere if x])
        r.append(_('{0} măsuri', n) + (_(', cu măsură de anacruză') if 0 in self.numere else '') + '.')
        r.append(_('Portative: ') + ', '.join(p.nume for p in self.portative) + '.')
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
            cap = _('Anacruza.') if nr == 0 else _('Măsura {0}.', nr)
            if nr in self.nesigure:
                cap += _(' Atenție, de verificat: {0}.', self.nesigure[nr])
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
                text = cuvinte.descrie_masura_portativ(m, opt) + '.'
                if len(portative) == 1:
                    # un singur portativ ales: nu mai spunem a cui mână e, se știe
                    linii.append(text)
                elif '\n' in text:
                    linii.append(f'{pt.nume}:\n' + text)
                else:
                    linii.append(f'{pt.nume}: ' + text)
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


def incarca(cale: str, progres=None, pastreaza=True, baza=None, folder=None, original=None) -> Partitura:
    """baza/folder/original: la o singură piesă dintr-o carte (cale = PDF temporar cu paginile ei)."""
    ext = os.path.splitext(cale)[1].lower()
    avert = []
    nesigure = {}
    if ext in FORMATE_MUSESCORE:
        cale_xml = recunoastere.din_musescore(cale)
        scor = converter.parse(cale_xml)
    elif ext in FORMATE_IMAGINE:
        r = recunoastere.din_imagine(cale, progres, pastreaza=pastreaza, baza=baza, folder=folder, original=original)
        scor = r.scor
        nesigure = r.nesigure
        if not r.programe:
            avert.append(_('Partitura a fost recunoscută mai devreme; am deschis rezultatul salvat în Documente, în folderul Music Box.'))
        elif len(r.programe) > 1:
            avert.append(_('Partitura a fost recunoscută din imagine de {0} programe ({1}), comparate măsură cu măsură.', len(r.programe), ", ".join(r.programe)))
        else:
            avert.append(_('Partitura a fost recunoscută din imagine cu {0}.', r.programe[0]))
        if nesigure:
            avert.append(_('Măsuri de verificat: {0}, marcate în listă cu „de verificat”. Control U duce la următoarea. Celelalte au fost citite la fel de toate programele.', len(nesigure)))
        else:
            avert.append(_('Toate măsurile au fost citite la fel și umplu corect timpii.'))
        if r.probleme:
            avert.append(_('Nu a mers: ') + '; '.join(r.probleme)[:300])
    elif ext in FORMATE_DIRECTE:
        scor = converter.parse(cale)
    else:
        raise EroarePartitura(_('Formatul acesta nu e cunoscut. Merg: MusicXML, MXL, MIDI, MuseScore, PDF și imagini.'))
    if isinstance(scor, stream.Opus):
        scor = scor.scores[0]
        avert.append(_('Fișierul are mai multe piese; am deschis-o pe prima.'))
    if not isinstance(scor, stream.Score):
        s = stream.Score(); s.insert(0, scor); scor = s
    P = Partitura(scor, cale, avert)
    P.nesigure = nesigure
    return P
