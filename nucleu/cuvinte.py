"""Descrierea partiturii în cuvinte, în română, măsură cu măsură și mână cu mână.

Exemplu: „Măsura 3. Mâna dreaptă: mi 5 optime, sol 5 optime, do 6 pătrime.
Mâna stângă:
acord
do 3, mi 3, sol 3, doime.”
Cu un singur portativ ales, nu se mai spune a cui mână e.
"""
from dataclasses import dataclass, field

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
    voci: bool = True            # când o mână are două voci, le spune separat


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


def descrie_element(el, opt: Optiuni) -> str:
    """O notă, un acord sau o pauză."""
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
    if el.duration.isGrace:
        parti.insert(0, 'apogiatură')
    elif opt.ritm and el.duration.type not in ('zero', 'complex'):
        parti.append(text_durata(el.duration, opt))
    elif opt.ritm and el.duration.type == 'complex':
        parti.append('durată de ' + str(round(float(el.duration.quarterLength), 2)).replace('.', ',') + ' pătrimi')
    extra = []
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
    if el.tie is not None and el.tie.type in ('start', 'continue'):
        extra.append('legată de următoarea')
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
            t = []
            if el.text:
                t.append(str(el.text))
            if el.number:
                t.append(f'{int(el.number)} pe minut')
            if t:
                out.append('tempo ' + ', '.join(t))
        elif isinstance(el, tempo.TempoText) and opt.nuante:
            out.append('tempo ' + el.text)
    return out


def descrie_voce(elemente, opt: Optiuni, dinamici) -> str:
    """Notele una după alta, despărțite prin virgulă. Fiecare acord stă pe rândurile lui:
    „acord” pe un rând, notele lui pe rândul următor; notele simple de după el continuă pe rând nou."""
    bucati = []
    for el in elemente:
        if opt.nuante:
            for off, txt in list(dinamici):
                if off <= el.offset:
                    bucati.append(txt)
                    dinamici.remove((off, txt))
        bucati.append(descrie_element(el, opt))
    for _, txt in dinamici:
        bucati.append(txt)
    if opt.scurt:
        return ' '.join(bucati)
    linii = []
    rand = []
    for b in bucati:
        if b.startswith('acord\n'):
            if rand:
                linii.append(', '.join(rand))
                rand = []
            linii.append(b)
        else:
            rand.append(b)
    if rand:
        linii.append(', '.join(rand))
    return ',\n'.join(linii).replace('acord,\n', 'acord\n')


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
            parti.append(f'vocea {i}: ' + descrie_voce(el, opt, dinamici if i == 1 else []))
        return '; '.join(parti)
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
