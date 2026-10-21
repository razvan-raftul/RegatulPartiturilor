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

from . import limba
from .limba import _

NUME_NOTE = {'C': 'do', 'D': 're', 'E': 'mi', 'F': 'fa', 'G': 'sol', 'A': 'la', 'B': 'si'}
if limba.LIMBA == 'fr':
    NUME_NOTE = {'C': 'do', 'D': 'ré', 'E': 'mi', 'F': 'fa', 'G': 'sol', 'A': 'la', 'B': 'si'}
CU_LITERE = limba.LIMBA in ('en', 'de')     # engleza și germana spun notele cu litere (C, D, E...)
ALTERATII = {-2: _('dublu bemol'), -1: _('bemol'), 0: '', 1: _('diez'), 2: _('dublu diez')}
ALT_SCURT = {-2: 'bb', -1: 'b', 0: '', 1: '#', 2: '##'}
DURATE = {
    'breve': _('brevis'), 'whole': _('întreagă'), 'half': _('doime'), 'quarter': _('pătrime'), 'eighth': _('optime'),
    '16th': _('șaisprezecime'), '32nd': _('treizecidoime'), '64th': _('șaizecipătrime'), '128th': _('o sută douăzeci și optime'),
}
# octavele în denumirea românească (do central = do din octava întâi)
OCTAVE_NUME = {0: _('subcontra'), 1: _('contra'), 2: _('mare'), 3: _('mică'), 4: _('întâi'), 5: _('a doua'), 6: _('a treia'),
               7: _('a patra'), 8: _('a cincea')}
TONICE = {k: v.capitalize() for k, v in NUME_NOTE.items()}
NUANTE = {'ppp': 'pianississimo', 'pp': 'pianissimo', 'p': 'piano', 'mp': 'mezzopiano', 'mf': 'mezzoforte',
          'f': 'forte', 'ff': 'fortissimo', 'fff': 'fortississimo', 'sf': 'sforzando', 'sfz': 'sforzando', 'fp': 'forte-piano'}
ARTICULATII = {
    articulations.Staccato: 'staccato', articulations.Staccatissimo: 'staccatissimo', articulations.Accent: _('accent'),
    articulations.StrongAccent: _('accent puternic'), articulations.Tenuto: 'tenuto', articulations.DetachedLegato: 'portato',
}
CHEI = {'G': _('cheia sol'), 'F': _('cheia fa'), 'C': _('cheia do')}
ACORD = _('acord')
IMPREUNA = _('împreună')


def _germana(step, alt):
    """Numele german al notei: Cis, Es, B (si bemol), H (si), Fisis, Eses."""
    baza = 'H' if step == 'B' else step
    if alt == 0:
        return baza
    if step == 'B' and alt == -1:
        return 'B'
    if alt > 0:
        return baza + 'is' * alt
    if step in 'EA':
        return baza + 's' + 'es' * (-alt - 1)
    return baza + 'es' * (-alt)


def _baza_alteratie(step, alt):
    """Numele notei cu alterația, în limba aleasă: „fa diez”, „F sharp”, „Fis”."""
    if limba.LIMBA == 'de':
        return _germana(step, alt)
    baza = step if CU_LITERE else NUME_NOTE[step]
    return baza + (' ' + ALTERATII[alt] if ALTERATII.get(alt) else '')


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
    alt = int(p.accidental.alter) if p.accidental is not None else 0
    if opt.scurt:
        # alterația cu cuvântul („do diez4”), nu cu semnul #, ca screen reader-ul să spună „diez” (cerut de Răzvan)
        s = (p.step.lower() if CU_LITERE else NUME_NOTE[p.step]) + (' ' + ALTERATII[alt] if ALTERATII.get(alt) else '')
        return s + (str(p.octave) if opt.octava != 'fara' and p.octave is not None else '')
    s = _baza_alteratie(p.step, alt)
    if opt.octava == 'numere' and p.octave is not None:
        s += f' {p.octave}'
    elif opt.octava == 'nume' and p.octave is not None:
        n = OCTAVE_NUME.get(p.octave)
        if n:
            s += _(' din octava ') + n
    return s


DURATE_PLURAL = {'breve': _('brevis'), 'whole': _('note întregi'), 'half': _('doimi'), 'quarter': _('pătrimi'), 'eighth': _('optimi'),
                 '16th': _('șaisprezecimi'), '32nd': _('treizecidoimi')}


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
            t.append(_('{0} pe minut', n))
        else:
            fig = DURATE_PLURAL.get(tip, DURATE.get(tip, tip)) + (_(' cu punct') if puncte == 1 else _(' cu două puncte') if puncte == 2 else '')
            if limba.LIMBA == 'ro':
                de = ' de' if (n % 100 >= 20 or (n >= 100 and n % 100 == 0)) else ''
                t.append(f'{n}{de} {fig} pe minut')
            else:
                t.append(_('{0} {1} pe minut', n, fig))
    return t


def text_durata(d, opt: Optiuni) -> str:
    if opt.scurt:
        s = DURATE_SCURT.get(d.type, d.type) + '.' * d.dots
        return s
    s = DURATE.get(d.type, d.type)
    if d.dots == 1:
        s += _(' cu punct')
    elif d.dots == 2:
        s += _(' cu două puncte')
    for tp in d.tuplets:
        if tp.numberNotesActual == 3 and tp.numberNotesNormal == 2:
            s += _(' în triolet')
        else:
            s += _(' în grup de {0}', tp.numberNotesActual)
        break
    return s


def text_digitatie(el) -> str:
    dg = [str(a.fingerNumber) for a in el.articulations if isinstance(a, articulations.Fingering) and a.fingerNumber is not None]
    if not dg:
        return ''
    return _('degetul {0}', dg[0]) if len(dg) == 1 else _('degetele {0}', ', '.join(dg))


def descrie_element(el, opt: Optiuni, durata=None, legat=None) -> str:
    """O notă, un acord sau o pauză.
    durata: lungimea totală în pătrimi când notele legate cu legato de prelungire se spun o singură dată.
    legat: „ținut” / „ținut și în măsura următoare” pentru notele legate."""
    if isinstance(el, note.Rest):
        if el.fullMeasure in (True, 'always') or el.duration.type in ('complex', 'zero'):
            return _('pauză') if opt.scurt else _('pauză toată măsura')
        if opt.scurt:
            return _('pauză') + ' ' + text_durata(el.duration, opt)
        return _('pauză de {0}', text_durata(el.duration, opt)) if opt.ritm else _('pauză')
    parti = []
    if isinstance(el, chord.Chord):
        nn = [nume_nota(p, opt) for p in sorted(el.pitches, key=lambda x: x.ps)]
        if opt.scurt:
            parti.append('[' + ' '.join(nn) + ']')
        else:
            # „acord” pe rândul lui, notele pe rândul următor (cerut de Răzvan, mai ușor de urmărit)
            parti.append(ACORD + '\n' + ', '.join(nn) + (',' if opt.ritm and not el.duration.isGrace else ''))
    else:
        parti.append(nume_nota(el.pitch, opt))
    d = el.duration
    if durata is not None and not d.isGrace:
        d = m21duration.Duration(durata)
    if d.isGrace:
        parti.insert(0, _('apogiatură'))
    elif opt.ritm and d.type not in ('zero', 'complex'):
        parti.append(text_durata(d, opt))
    elif opt.ritm and d.type == 'complex':
        parti.append(_('durată de {0} pătrimi', str(round(float(d.quarterLength), 2)).replace('.', ',')))
    extra = [legat] if legat else []
    if opt.nuante:
        for a in el.articulations:
            for cls, nume in ARTICULATII.items():
                if type(a) is cls:
                    extra.append(nume)
        for ex in el.expressions:
            if isinstance(ex, expressions.Fermata):
                extra.append(_('coroană'))
            elif isinstance(ex, expressions.Trill):
                extra.append(_('tril'))
            elif isinstance(ex, expressions.Mordent):
                extra.append(_('mordent'))
            elif isinstance(ex, expressions.Turn):
                extra.append(_('grupet'))
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
        alt = int(k.tonic.accidental.alter) if k.tonic.accidental else 0
        t = _baza_alteratie(k.tonic.step, alt)
        t = t[:1].upper() + t[1:]
        return t + ' ' + (_('major') if k.mode == 'major' else _('minor'))
    if isinstance(k, key.KeySignature):
        n = k.sharps
        if n == 0:
            return _('fără alterații la cheie')
        if abs(n) == 1:
            return _('un diez la cheie') if n > 0 else _('un bemol la cheie')
        return _('{0} diezi la cheie', n) if n > 0 else _('{0} bemoli la cheie', -n)
    return ''


def text_masura_timp(ts) -> str:
    return _('{0} pe {1}', ts.numerator, ts.denominator)


def _evenimente_masura(m, opt: Optiuni):
    """Schimbări din interiorul măsurii: tonalitate, măsură, cheie, tempo, nuanțe."""
    out = []
    for el in m.getElementsByClass([key.KeySignature, meter.TimeSignature, clef.Clef, tempo.MetronomeMark, tempo.TempoText]):
        if isinstance(el, key.KeySignature):
            out.append(_('tonalitatea: ') + nume_tonalitate(el))
        elif isinstance(el, meter.TimeSignature):
            out.append(_('măsura de ') + text_masura_timp(el))
        elif isinstance(el, clef.Clef) and opt.nuante:
            c = CHEI.get(getattr(el, 'sign', None))
            if c:
                out.append(c)
        elif isinstance(el, tempo.MetronomeMark) and opt.nuante:
            t = text_tempo(el)
            if t:
                out.append(_('tempo ') + ', '.join(t))
        elif isinstance(el, tempo.TempoText) and opt.nuante:
            out.append(_('tempo ') + el.text)
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
            legat = _('ținut') if sfarsit else _('ținut și în măsura următoare')
            text = descrie_element(el, opt, durata=total, legat=legat)
            if tip == 'continue' and i == 0:
                text = _('se ține din măsura trecută: ') + text
            bucati.append(text)
            i = j
            continue
        text = descrie_element(el, opt)
        if tip == 'stop' and i == 0:
            text = _('se ține din măsura trecută: ') + text
        bucati.append(text)
        i += 1
    for _x, txt in dinamici:
        bucati.append(txt)
    return _aranjeaza(bucati, opt)


def _aranjeaza(bucati, opt: Optiuni) -> str:
    if opt.scurt:
        return ' '.join(bucati)
    linii = []
    rand = []
    for b in bucati:
        if b.startswith((ACORD + '\n', IMPREUNA + '\n')):
            if rand:
                linii.append(', '.join(rand))
                rand = []
            linii.append(b)
        else:
            rand.append(b)
    if rand:
        linii.append(', '.join(rand))
    return ',\n'.join(linii).replace(ACORD + ',\n', ACORD + '\n').replace(IMPREUNA + ',\n', IMPREUNA + '\n')


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
            out.append((el, total, _('ținut') if sfarsit else _('ținut și în măsura următoare'), tip == 'continue' and i == 0))
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
        return descrie_element(note.Rest(quarterLength=lungime), opt) if lungime else _('gol')
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
            text = IMPREUNA + '\n' + ', '.join(descrie_element(e[1], opt, durata=e[2], legat=e[3]) for e in grup)
        if trecut:
            text = _('se ține din măsura trecută: ') + text
        elif off < sfarsit - 1e-6 and not opt.scurt:
            # începe cât încă ține nota de dinainte
            text = _('peste el ') + text
        bucati.append(text)
        sfarsit = max(sfarsit, max(e[0] + float(e[2]) for e in grup))
    lungime = float(m.barDuration.quarterLength) if m.barDuration else sfarsit
    if lungime > sfarsit + 1e-6 and not evenimente[-1][3]:
        bucati.append(descrie_element(note.Rest(quarterLength=lungime - sfarsit), opt))
    for _x, txt in dinamici:
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
        nume = {1: _('vocea de sus'), 2: _('vocea de jos')} if len(parti) == 2 else {}
        return ';\n'.join(f'{nume.get(k, _("vocea {0}", k))}: {t}' for k, t in parti)
    if voci and len([v for v in voci if v.notes]) > 1:
        return descrie_o_voce(m, opt, dinamici)
    el = list(m.recurse().notesAndRests)
    el.sort(key=lambda x: x.getOffsetInHierarchy(m))
    if not el:
        return _('gol')
    return descrie_voce(el, opt, dinamici)


def text_barline(m) -> list:
    out = []
    lb, rb = m.leftBarline, m.rightBarline
    if isinstance(lb, bar.Repeat) and lb.direction == 'start':
        out.append(_('începe repetiția'))
    if isinstance(rb, bar.Repeat) and rb.direction == 'end':
        out.append(_('se repetă de la semnul de repetiție') if not (rb.times and rb.times > 2) else _('se repetă de {0} ori', rb.times))
    elif rb is not None and getattr(rb, 'type', None) == 'final':
        out.append(_('bară finală'))
    elif rb is not None and getattr(rb, 'type', None) in ('light-light', 'double'):
        out.append(_('bară dublă'))
    for sp in m.getSpannerSites():
        if isinstance(sp, spanner.RepeatBracket) and sp.isFirst(m):
            out.insert(0, _('volta {0}', sp.number))
    return out
