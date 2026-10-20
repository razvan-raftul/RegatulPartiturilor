"""Descrierea partiturii în cuvinte, în română, măsură cu măsură și mână cu mână.

Exemplu: „Măsura 3. Mâna dreaptă: mi 5 optime, sol 5 optime, do 6 pătrime.
Mâna stângă:
acord
do 3, mi 3, sol 3, doime.”
Cu un singur portativ ales, nu se mai spune a cui mână e.
"""
from dataclasses import dataclass, field

from music21 import duration as m21duration
from music21 import articulations, bar, chord, clef, dynamics, expressions, key, meter, note, spanner, tempo

NUME_NOTE = {'C': 'do', 'D': 're', 'E': 'mi', 'F': 'fa', 'G': 'sol', 'A': 'la', 'B': 'si'}
ALTERATII = {-2: 'dublu bemol', -1: 'bemol', 0: '', 1: 'diez', 2: 'dublu diez'}
ALT_SCURT = {-2: 'bb', -1: 'b', 0: '', 1: '#', 2: '##'}
DURATE = {
    'breve': 'brevis', 'whole': 'întreagă', 'half': 'doime', 'quarter': 'pătrime', 'eighth': 'optime',
    '16th': 'șaisprezecime', '32nd': 'treizecidoime', '64th': 'șaizecipătrime', '128th': 'o sută douăzeci și optime',
}
# octavele în denumirea românească (do central = do din octava întâi)
OCTAVE_NUME = {0: 'subcontra', 1: 'contra', 2: 'mare', 3: 'mică', 4: 'întâi', 5: 'a doua', 6: 'a treia', 7: 'a patra', 8: 'a cincea'}
TONICE = {'C': 'Do', 'D': 'Re', 'E': 'Mi', 'F': 'Fa', 'G': 'Sol', 'A': 'La', 'B': 'Si'}
NUANTE = {'ppp': 'pianississimo', 'pp': 'pianissimo', 'p': 'piano', 'mp': 'mezzopiano', 'mf': 'mezzoforte',
          'f': 'forte', 'ff': 'fortissimo', 'fff': 'fortississimo', 'sf': 'sforzando', 'sfz': 'sforzando', 'fp': 'forte-piano'}
ARTICULATII = {
    articulations.Staccato: 'staccato', articulations.Staccatissimo: 'staccatissimo', articulations.Accent: 'accent',
    articulations.StrongAccent: 'accent puternic', articulations.Tenuto: 'tenuto', articulations.DetachedLegato: 'portato',
}
CHEI = {'G': 'cheia sol', 'F': 'cheia fa', 'C': 'cheia do'}


@dataclass
class Optiuni:
    ritm: bool = True            # spune durata fiecărei note
    octava: str = 'numere'       # 'fara', 'numere' (do 4) sau 'nume' (do din octava întâi)
    scurt: bool = False          # scriere scurtă: do4 p, mi4 o (pentru citit repede)
    digitatie: bool = True
    nuante: bool = True          # nuanțe, articulații, legato, tempo
    voci: bool = False           # True: vocile dintr-o mână se spun separat; False: puse într-una, în ordinea în care sună


DURATE_SCURT = {'breve': 'B', 'whole': 'î', 'half': 'd', 'quarter': 'p', 'eighth': 'o', '16th': 's', '32nd': 't', '64th': '64'}


def nume_nota(p, opt: Optiuni) -> str:
    """O înălțime music21 -> „fa diez 4”, „fa diez din octava întâi” sau „fa#4”."""
    baza = NUME_NOTE[p.step]
    alt = int(p.accidental.alter) if p.accidental is not None else 0
    if opt.scurt:
        s = baza + ALT_SCURT.get(alt, '')
        return s + (str(p.octave) if opt.octava != 'fara' and p.octave is not None else '')
    s = baza + (' ' + ALTERATII[alt] if ALTERATII.get(alt) else '')
    if opt.octava == 'numere' and p.octave is not None:
        s += f' {p.octave}'
    elif opt.octava == 'nume' and p.octave is not None:
        n = OCTAVE_NUME.get(p.octave)
        if n:
            s += ' din octava ' + n
    return s


DURATE_PLURAL = {'breve': 'brevis', 'whole': 'note întregi', 'half': 'doimi', 'quarter': 'pătrimi', 'eighth': 'optimi',
                 '16th': 'șaisprezecimi', '32nd': 'treizecidoimi'}


def text_tempo(mm) -> list:
    """Un semn de metronom -> [„Moderato”, „138 de optimi pe minut”]. Numărul se spune pe figura scrisă
    (optimea = 138 rămâne 138 de optimi, nu 138 de pătrimi); la pătrime doar „69 pe minut”.
    Numele de tempo pe care music21 îl ghicește singur din număr (de exemplu „allegrissimo”) nu se spune."""
    t = []
    if mm.text and not getattr(mm, 'textImplicit', False):
        t.append(str(mm.text))
    if mm.number and not getattr(mm, 'numberImplicit', False):
        n = int(round(mm.number))
        ref = getattr(mm, 'referent', None)
        tip, puncte = (ref.type, ref.dots) if ref is not None else ('quarter', 0)
        if tip == 'quarter' and puncte == 0:
            t.append(f'{n} pe minut')
        else:
            de = ' de' if (n % 100 >= 20 or (n >= 100 and n % 100 == 0)) else ''
            fig = DURATE_PLURAL.get(tip, DURATE.get(tip, tip)) + (' cu punct' if puncte == 1 else ' cu două puncte' if puncte == 2 else '')
            t.append(f'{n}{de} {fig} pe minut')
    return t


def text_durata(d, opt: Optiuni) -> str:
    if opt.scurt:
        s = DURATE_SCURT.get(d.type, d.type) + '.' * d.dots
        return s
    s = DURATE.get(d.type, d.type)
    if d.dots == 1:
        s += ' cu punct'
    elif d.dots == 2:
        s += ' cu două puncte'
    for tp in d.tuplets:
        if tp.numberNotesActual == 3 and tp.numberNotesNormal == 2:
            s += ' în triolet'
        else:
            s += f' în grup de {tp.numberNotesActual}'
        break
    return s


def text_digitatie(el) -> str:
    dg = [str(a.fingerNumber) for a in el.articulations if isinstance(a, articulations.Fingering) and a.fingerNumber is not None]
    if not dg:
        return ''
    return ('degetul ' if len(dg) == 1 else 'degetele ') + ', '.join(dg)


def descrie_element(el, opt: Optiuni, durata=None, legat=None) -> str:
    """O notă, un acord sau o pauză.
    durata: lungimea totală în pătrimi când notele legate cu legato de prelungire se spun o singură dată.
    legat: „ținut” / „ținut și în măsura următoare” pentru notele legate."""
    if isinstance(el, note.Rest):
        if el.fullMeasure in (True, 'always') or el.duration.type in ('complex', 'zero'):
            return 'pauză' if opt.scurt else 'pauză toată măsura'
        if opt.scurt:
            return 'pauză ' + text_durata(el.duration, opt)
        return 'pauză de ' + text_durata(el.duration, opt) if opt.ritm else 'pauză'
    parti = []
    if isinstance(el, chord.Chord):
        nn = [nume_nota(p, opt) for p in sorted(el.pitches, key=lambda x: x.ps)]
        if opt.scurt:
            parti.append('[' + ' '.join(nn) + ']')
        else:
            # „acord” pe rândul lui, notele pe rândul următor (cerut de Răzvan, mai ușor de urmărit)
            parti.append('acord\n' + ', '.join(nn) + (',' if opt.ritm and not el.duration.isGrace else ''))
    else:
        parti.append(nume_nota(el.pitch, opt))
    d = el.duration
    if durata is not None and not d.isGrace:
        d = m21duration.Duration(durata)
    if d.isGrace:
        parti.insert(0, 'apogiatură')
    elif opt.ritm and d.type not in ('zero', 'complex'):
        parti.append(text_durata(d, opt))
    elif opt.ritm and d.type == 'complex':
        parti.append('durată de ' + str(round(float(d.quarterLength), 2)).replace('.', ',') + ' pătrimi')
    extra = [legat] if legat else []
    if opt.nuante:
        for a in el.articulations:
            for cls, nume in ARTICULATII.items():
                if type(a) is cls:
                    extra.append(nume)
        for ex in el.expressions:
            if isinstance(ex, expressions.Fermata):
                extra.append('coroană')
            elif isinstance(ex, expressions.Trill):
                extra.append('tril')
            elif isinstance(ex, expressions.Mordent):
                extra.append('mordent')
            elif isinstance(ex, expressions.Turn):
                extra.append('grupet')
    if opt.digitatie:
        dg = text_digitatie(el)
        if dg:
            extra.append(dg)
    s = ' '.join(parti)
    if extra:
        s += ' (' + ', '.join(extra) + ')'
    return s


def nume_tonalitate(k) -> str:
    if isinstance(k, key.Key):
        t = TONICE[k.tonic.step]
        alt = int(k.tonic.accidental.alter) if k.tonic.accidental else 0
        if alt:
            t += ' ' + ALTERATII[alt]
        return f"{t} {'major' if k.mode == 'major' else 'minor'}"
    if isinstance(k, key.KeySignature):
        n = k.sharps
        if n == 0:
            return 'fără alterații la cheie'
        return f"{abs(n)} {'diezi' if n > 0 else 'bemoli'} la cheie" if abs(n) > 1 else f"un {'diez' if n > 0 else 'bemol'} la cheie"
    return ''


def text_masura_timp(ts) -> str:
    return f'{ts.numerator} pe {ts.denominator}'


def _evenimente_masura(m, opt: Optiuni):
    """Schimbări din interiorul măsurii: tonalitate, măsură, cheie, tempo, nuanțe."""
    out = []
    for el in m.getElementsByClass([key.KeySignature, meter.TimeSignature, clef.Clef, tempo.MetronomeMark, tempo.TempoText]):
        if isinstance(el, key.KeySignature):
            out.append('tonalitatea: ' + nume_tonalitate(el))
        elif isinstance(el, meter.TimeSignature):
            out.append('măsura de ' + text_masura_timp(el))
        elif isinstance(el, clef.Clef) and opt.nuante:
            c = CHEI.get(getattr(el, 'sign', None))
            if c:
                out.append(c)
        elif isinstance(el, tempo.MetronomeMark) and opt.nuante:
            t = text_tempo(el)
            if t:
                out.append('tempo ' + ', '.join(t))
        elif isinstance(el, tempo.TempoText) and opt.nuante:
            out.append('tempo ' + el.text)
    return out


def _aceleasi_note(a, b) -> bool:
    try:
        return sorted(p.ps for p in a.pitches) == sorted(p.ps for p in b.pitches)
    except AttributeError:
        return False


def descrie_voce(elemente, opt: Optiuni, dinamici) -> str:
    """Notele una după alta, despărțite prin virgulă. Fiecare acord stă pe rândurile lui:
    „acord” pe un rând, notele lui pe rândul următor; notele simple de după el continuă pe rând nou."""
    bucati = []
    i = 0
    while i < len(elemente):
        el = elemente[i]
        if opt.nuante:
            for off, txt in list(dinamici):
                if off <= el.offset:
                    bucati.append(txt)
                    dinamici.remove((off, txt))
        tip = el.tie.type if getattr(el, 'tie', None) is not None else None
        if tip in ('start', 'continue'):
            # notele legate cu legato de prelungire se spun o singură dată, cu toată durata
            total = el.duration.quarterLength
            j = i + 1
            sfarsit = False
            while j < len(elemente) and getattr(elemente[j], 'tie', None) is not None \
                    and elemente[j].tie.type in ('continue', 'stop') and _aceleasi_note(el, elemente[j]):
                total += elemente[j].duration.quarterLength
                sfarsit = elemente[j].tie.type == 'stop'
                j += 1
            legat = 'ținut' if sfarsit else 'ținut și în măsura următoare'
            text = descrie_element(el, opt, durata=total, legat=legat)
            if tip == 'continue' and i == 0:
                text = 'se ține din măsura trecută: ' + text
            bucati.append(text)
            i = j
            continue
        text = descrie_element(el, opt)
        if tip == 'stop' and i == 0:
            text = 'se ține din măsura trecută: ' + text
        bucati.append(text)
        i += 1
    for _, txt in dinamici:
        bucati.append(txt)
    return _aranjeaza(bucati, opt)


def _aranjeaza(bucati, opt: Optiuni) -> str:
    if opt.scurt:
        return ' '.join(bucati)
    linii = []
    rand = []
    for b in bucati:
        if b.startswith(('acord\n', 'împreună\n')):
            if rand:
                linii.append(', '.join(rand))
                rand = []
            linii.append(b)
        else:
            rand.append(b)
    if rand:
        linii.append(', '.join(rand))
    return ',\n'.join(linii).replace('acord,\n', 'acord\n').replace('împreună,\n', 'împreună\n')


def _lanturi(elemente):
    """Notele unei voci, cu notele legate (legato de prelungire) strânse într-una singură.
    Întoarce (element, durată totală, „ținut...” sau None, începe în măsura trecută)."""
    out = []
    i = 0
    while i < len(elemente):
        el = elemente[i]
        tip = el.tie.type if getattr(el, 'tie', None) is not None else None
        if tip in ('start', 'continue'):
            total = el.duration.quarterLength
            j = i + 1
            sfarsit = False
            while j < len(elemente) and getattr(elemente[j], 'tie', None) is not None \
                    and elemente[j].tie.type in ('continue', 'stop') and _aceleasi_note(el, elemente[j]):
                total += elemente[j].duration.quarterLength
                sfarsit = elemente[j].tie.type == 'stop'
                j += 1
            out.append((el, total, 'ținut' if sfarsit else 'ținut și în măsura următoare', tip == 'continue' and i == 0))
            i = j
            continue
        out.append((el, el.duration.quarterLength, None, tip == 'stop' and i == 0))
        i += 1
    return out


def descrie_o_voce(m, opt: Optiuni, dinamici) -> str:
    """Toate vocile unei mâini puse într-una singură, în ordinea în care sună notele (cerut de Răzvan:
    nu știe să citească pe două voci). Notele care încep în același timp se spun împreună;
    pauza se spune doar când nu sună nimic."""
    voci = list(m.voices) or [m]
    evenimente = []   # (offset, element, durată, legat, din măsura trecută)
    for v in voci:
        el = [x for x in v.notesAndRests if not isinstance(x, note.Rest)]
        el.sort(key=lambda x: x.getOffsetInHierarchy(m))
        for (x, total, legat, trecut) in _lanturi(el):
            evenimente.append((float(x.getOffsetInHierarchy(m)), x, total, legat, trecut))
    if not evenimente:
        lungime = m.duration.quarterLength or m.barDuration.quarterLength
        return descrie_element(note.Rest(quarterLength=lungime), opt) if lungime else 'gol'
    evenimente.sort(key=lambda e: (e[0], min(p.ps for p in e[1].pitches)))
    bucati = []
    sfarsit = 0.0
    k = 0
    while k < len(evenimente):
        off = evenimente[k][0]
        grup = [e for e in evenimente[k:] if abs(e[0] - off) < 1e-6]
        k += len(grup)
        if opt.nuante:
            for o, txt in list(dinamici):
                if o <= off + 1e-6:
                    bucati.append(txt)
                    dinamici.remove((o, txt))
        if off > sfarsit + 1e-6:
            bucati.append(descrie_element(note.Rest(quarterLength=off - sfarsit), opt))
        trecut = all(e[4] for e in grup)
        if len(grup) == 1:
            e = grup[0]
            text = descrie_element(e[1], opt, durata=e[2], legat=e[3])
        elif len({(e[2], e[3]) for e in grup}) == 1:
            # toate încep și se termină împreună: acord
            ac = chord.Chord([p for e in grup for p in e[1].pitches], quarterLength=grup[0][1].duration.quarterLength)
            ac.articulations = grup[0][1].articulations
            text = descrie_element(ac, opt, durata=grup[0][2], legat=grup[0][3])
        else:
            # încep împreună, dar țin diferit: fiecare cu durata lui
            text = 'împreună\n' + ', '.join(descrie_element(e[1], opt, durata=e[2], legat=e[3]) for e in grup)
        if trecut:
            text = 'se ține din măsura trecută: ' + text
        elif off < sfarsit - 1e-6 and not opt.scurt:
            # începe cât încă ține nota de dinainte
            text = 'peste el ' + text
        bucati.append(text)
        sfarsit = max(sfarsit, max(e[0] + float(e[2]) for e in grup))
    lungime = float(m.barDuration.quarterLength) if m.barDuration else sfarsit
    if lungime > sfarsit + 1e-6 and not evenimente[-1][3]:
        bucati.append(descrie_element(note.Rest(quarterLength=lungime - sfarsit), opt))
    for _, txt in dinamici:
        bucati.append(txt)
    return _aranjeaza(bucati, opt)


def descrie_masura_portativ(m, opt: Optiuni) -> str:
    """Conținutul unei măsuri dintr-un portativ (o mână), cu voci dacă sunt."""
    dinamici = []
    if opt.nuante:
        for d in m.recurse().getElementsByClass(dynamics.Dynamic):
            dinamici.append((d.getOffsetInHierarchy(m), NUANTE.get(d.value, d.value)))
        for d in m.recurse().getElementsByClass(dynamics.DynamicWedge):
            pass
        for te in m.recurse().getElementsByClass(expressions.TextExpression):
            if te.content and te.content.strip():
                dinamici.append((te.getOffsetInHierarchy(m), te.content.strip()))
        dinamici.sort(key=lambda x: x[0])
    voci = list(m.voices)
    if voci and opt.voci and len([v for v in voci if v.notes]) > 1:
        parti = []
        i = 0
        for v in voci:
            el = list(v.notesAndRests)
            if not el or all(isinstance(x, note.Rest) and getattr(x.style, 'hideObjectOnPrint', False) for x in el):
                continue
            i += 1
            parti.append((i, descrie_voce(el, opt, dinamici if i == 1 else [])))
        # fiecare voce pe rândul ei; la două voci: vocea de sus și vocea de jos
        nume = {1: 'vocea de sus', 2: 'vocea de jos'} if len(parti) == 2 else {}
        return ';\n'.join(f'{nume.get(k, f"vocea {k}")}: {t}' for k, t in parti)
    if voci and len([v for v in voci if v.notes]) > 1:
        return descrie_o_voce(m, opt, dinamici)
    el = list(m.recurse().notesAndRests)
    el.sort(key=lambda x: x.getOffsetInHierarchy(m))
    if not el:
        return 'gol'
    return descrie_voce(el, opt, dinamici)


def text_barline(m) -> list:
    out = []
    lb, rb = m.leftBarline, m.rightBarline
    if isinstance(lb, bar.Repeat) and lb.direction == 'start':
        out.append('începe repetiția')
    if isinstance(rb, bar.Repeat) and rb.direction == 'end':
        out.append('se repetă de la semnul de repetiție' if not (rb.times and rb.times > 2) else f'se repetă de {rb.times} ori')
    elif rb is not None and getattr(rb, 'type', None) == 'final':
        out.append('bară finală')
    elif rb is not None and getattr(rb, 'type', None) in ('light-light', 'double'):
        out.append('bară dublă')
    for sp in m.getSpannerSites():
        if isinstance(sp, spanner.RepeatBracket) and sp.isFirst(m):
            out.insert(0, f'volta {sp.number}')
    return out
