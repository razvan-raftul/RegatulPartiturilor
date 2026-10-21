"""Scrierea partiturilor de mână, în text: fiecare rând e o măsură, pentru mâna dreaptă și pentru mâna stângă.

Cum se scrie (aceeași scriere ca „Scriere scurtă” din textul în cuvinte):
  nota:     do re mi fa sol la si, sau cu litere: c d e f g a b (c = do, b = si), apoi alterația
            (# diez, ## dublu diez, b bemol, bb dublu bemol, n becar), apoi octava (do4 sau c4 = do central).
            Exemple: do#4d sau c#4d = do diez 4 doime; sib4d sau bb4d = si bemol 4 doime.
            Fără octavă se ia cea mai apropiată de nota de dinainte.
  durata:   î întreagă, d doime, p pătrime, o optime, s șaisprezecime, t treizecidoime; cu punct: p. sau d..
            Se scrie după notă, lipit sau cu spațiu (do4 p, do4p). Fără durată rămâne cea de dinainte.
            Cu litere, doimea se scrie lipită (c4d), pentru că „d” singur e nota re (c d e = do re mi).
  pauza:    pauză p (sau pauza p, sau - p).
  acord:    [do4 mi4 sol4] d   (sau do4+mi4+sol4 d)
  legato de prelungire: ~ după notă (do4 d~ do4 p).
  triolet:  3( do4 o re4 o mi4 o )
Armura se aplică singură, ca pe partitură (în Sol major fa e fa diez); o alterație ține toată măsura.
Notele se pot despărți prin spații sau virgule. Un număr la începutul rândului, cu două puncte („3:”), se ignoră.
"""
import re

from music21 import (bar, chord, clef, duration, instrument, key, layout, metadata, meter, note, pitch, stream,
                     tempo, tie)
from .limba import _

TREPTE = {'do': 'C', 're': 'D', 'mi': 'E', 'fa': 'F', 'sol': 'G', 'la': 'A', 'si': 'B',
          'c': 'C', 'd': 'D', 'e': 'E', 'f': 'F', 'g': 'G', 'a': 'A', 'b': 'B'}
DURATE = {'î': 4.0, 'i': 4.0, 'd': 2.0, 'p': 1.0, 'o': 0.5, 's': 0.25, 't': 0.125}
ALTERATII = {'##': 2, '#': 1, 'bb': -2, 'b': -1, 'n': 0, '': None}

MASURI = ['4/4', '3/4', '2/4', '2/2', '3/8', '6/8', '9/8', '12/8', '5/4', '3/2']
TONALITATI = [  # (număr de alterații, nume)
    (0, _('Do major sau la minor, fără alterații')),
    (1, _('Sol major sau mi minor, 1 diez')), (2, _('Re major sau si minor, 2 diezi')), (3, _('La major sau fa diez minor, 3 diezi')),
    (4, _('Mi major sau do diez minor, 4 diezi')), (5, _('Si major sau sol diez minor, 5 diezi')),
    (6, _('Fa diez major sau re diez minor, 6 diezi')), (7, _('Do diez major sau la diez minor, 7 diezi')),
    (-1, _('Fa major sau re minor, 1 bemol')), (-2, _('Si bemol major sau sol minor, 2 bemoli')),
    (-3, _('Mi bemol major sau do minor, 3 bemoli')), (-4, _('La bemol major sau fa minor, 4 bemoli')),
    (-5, _('Re bemol major sau si bemol minor, 5 bemoli')), (-6, _('Sol bemol major sau mi bemol minor, 6 bemoli')),
    (-7, _('Do bemol major sau la bemol minor, 7 bemoli')),
]

_NOTA = re.compile(r'^(do|re|mi|fa|sol|la|si)(##|#|bb|b|n)?(\d)?(?:(î|i|d|p|o|s|t)(\.*))?(~)?$')
# cu litere: c d e f g a b; alterația, octava, durata lipită (bb4d = si bemol 4 doime)
_LITERA = re.compile(r'^([a-g])(##|#|bb|b|n)?(\d)?(?:(î|i|d|p|o|s|t)(\.*))?(~)?$')


def _potrivire_nota(t):
    return _NOTA.match(t) or _LITERA.match(t)
_DURATA = re.compile(r'^(î|i|d|p|o|s|t)(\.*)(~)?$')
_PAUZA = re.compile(r'^(pauză|pauza|-)(?:(î|i|d|p|o|s|t)(\.*))?$')


class EroareScriere(Exception):
    pass


def _jetoane(rand: str):
    rand = re.sub(r'^\s*\d+\s*:', '', rand)
    rand = rand.replace(',', ' ').replace('[', ' [ ').replace(']', ' ] ').replace('(', '( ').replace(')', ' ) ')
    rand = re.sub(r'\s*\+\s*', '+', rand)
    rand = re.sub(r'(\S)~', r'\1 ~', rand)
    return [t for t in rand.lower().split() if t]


class _Stare:
    def __init__(self, octava_start):
        self.durata = 1.0
        self.puncte = 0
        self.ultima = pitch.Pitch(f'C{octava_start}')


def _alege_octava(treapta, stare: _Stare):
    """Octava cea mai apropiată de nota de dinainte (ca la braille: secundă și terță cea mai apropiată)."""
    best = None
    for o in range(stare.ultima.octave - 1, stare.ultima.octave + 2):
        p = pitch.Pitch(f'{treapta}{o}')
        dist = abs(p.diatonicNoteNum - stare.ultima.diatonicNoteNum)
        if best is None or dist < best[0]:
            best = (dist, o)
    return best[1]


def _inaltime(m, stare, armura, alterate):
    treapta = TREPTE[m.group(1)]
    alt = ALTERATII[m.group(2) or '']
    octava = int(m.group(3)) if m.group(3) else _alege_octava(treapta, stare)
    if alt is None:
        alt = alterate.get((treapta, octava), alterate.get(treapta, armura.get(treapta, 0)))
    else:
        alterate[(treapta, octava)] = alt
        alterate[treapta] = alt
    p = pitch.Pitch(f'{treapta}{octava}')
    if alt:
        p.accidental = pitch.Accidental(alt)
    elif m.group(2) == 'n':
        p.accidental = pitch.Accidental('natural')
    stare.ultima = p
    return p


def _durata(litera, puncte, stare):
    if litera:
        stare.durata = DURATE[litera]
        stare.puncte = len(puncte or '')
    return stare.durata, stare.puncte


def _armura(fifths):
    k = key.KeySignature(fifths)
    rez = {}
    for p in k.alteredPitches:
        rez[p.step] = int(p.alter)
    return rez


def citeste_masura(rand: str, stare: _Stare, armura: dict, nr: int, mana: str) -> list:
    """Elementele music21 (note, acorduri, pauze) dintr-un rând."""
    jet = _jetoane(rand)
    alterate = {}
    elemente = []
    acord = None              # lista de înălțimi cât suntem între [ ]
    triolet = None            # elementele din tuplet
    i = 0

    def adauga(el):
        (triolet if triolet is not None else elemente).append(el)

    def eroare(t, motiv):
        raise EroareScriere(_('Măsura {0}, {1}: „{2}” {3}', nr, _(mana), t, motiv))

    while i < len(jet):
        t = jet[i]
        i += 1
        if t == '[':
            acord = []
            continue
        if t == ']':
            if not acord:
                eroare(t, _('închide un acord gol.'))
            lit, pct, leg = None, '', False
            if i < len(jet) and _DURATA.match(jet[i]):
                md = _DURATA.match(jet[i]); i += 1
                lit, pct, leg = md.group(1), md.group(2), bool(md.group(3))
            d, p = _durata(lit, pct, stare)
            c = chord.Chord(acord)
            c.duration = duration.Duration(d * (2 - 0.5 ** p))
            if leg:
                c.tie = tie.Tie('start')
            stare.ultima = sorted(acord, key=lambda x: x.ps)[0]
            adauga(c)
            acord = None
            continue
        if t in ('3(', '2(', '5(', '6('):
            triolet = []
            n_tuplet = int(t[0])
            continue
        if t == ')':
            if triolet is None:
                eroare(t, _('închide un triolet care nu a fost deschis.'))
            norm = {3: 2, 2: 3, 5: 4, 6: 4}[n_tuplet]
            for el in triolet:
                tp = duration.Tuplet(n_tuplet, norm)
                el.duration.appendTuplet(tp)
            if triolet:
                triolet[0].duration.tuplets[0].type = 'start'
                triolet[-1].duration.tuplets[0].type = 'stop'
            elemente.extend(triolet)
            triolet = None
            continue
        if t == '~':
            tinta = (triolet if triolet is not None else elemente)
            if not tinta:
                eroare(t, _('nu are notă înainte.'))
            tinta[-1].tie = tie.Tie('start')
            continue
        if '+' in t and acord is None:
            parti = t.split('+')
            pitches = []
            ultima_m = None
            for k, pt in enumerate(parti):
                mm = _potrivire_nota(pt)
                if not mm:
                    eroare(pt, _('nu e o notă (de exemplu do4, fa#, sib3).'))
                pitches.append(_inaltime(mm, stare, armura, alterate))
                ultima_m = mm
            lit, pct = ultima_m.group(4), ultima_m.group(5)
            if not lit and i < len(jet) and _DURATA.match(jet[i]) and not (_LITERA.match(parti[-1]) and _LITERA.match(jet[i])):
                md = _DURATA.match(jet[i]); i += 1
                lit, pct = md.group(1), md.group(2)
            d, p = _durata(lit, pct, stare)
            c = chord.Chord(pitches)
            c.duration = duration.Duration(d * (2 - 0.5 ** p))
            stare.ultima = sorted(pitches, key=lambda x: x.ps)[0]
            adauga(c)
            continue
        mp = _PAUZA.match(t)
        if mp:
            lit, pct = mp.group(2), mp.group(3)
            if not lit and i < len(jet) and _DURATA.match(jet[i]):
                md = _DURATA.match(jet[i]); i += 1
                lit, pct = md.group(1), md.group(2)
            d, p = _durata(lit, pct, stare)
            r = note.Rest()
            r.duration = duration.Duration(d * (2 - 0.5 ** p))
            adauga(r)
            continue
        mn = _NOTA.match(t)
        cu_litera = False
        if not mn:
            mn = _LITERA.match(t)
            cu_litera = mn is not None
        if mn:
            p_ = _inaltime(mn, stare, armura, alterate)
            if acord is not None:
                acord.append(p_)
                continue
            lit, pct, leg = mn.group(4), mn.group(5), bool(mn.group(6))
            # după o notă scrisă cu litere, „d” singur e nota re, nu doime (c d e = do re mi)
            if not lit and i < len(jet) and _DURATA.match(jet[i]) and not (cu_litera and _LITERA.match(jet[i])):
                md = _DURATA.match(jet[i]); i += 1
                lit, pct, leg = md.group(1), md.group(2), leg or bool(md.group(3))
            d, p = _durata(lit, pct, stare)
            n = note.Note(p_)
            n.duration = duration.Duration(d * (2 - 0.5 ** p))
            if leg:
                n.tie = tie.Tie('start')
            adauga(n)
            continue
        if _DURATA.match(t):
            eroare(t, _('e o durată fără notă înainte (cu litere, durata se scrie lipită: c4d).'))
        eroare(t, _('nu înțeleg ce e (o notă se scrie de exemplu do4 p).'))
    if acord is not None:
        raise EroareScriere(_('Măsura {0}, {1}: acordul nu e închis cu ].', nr, _(mana)))
    if triolet is not None:
        raise EroareScriere(_('Măsura {0}, {1}: trioletul nu e închis cu ).', nr, _(mana)))
    return elemente


def _leaga(parte):
    """Legato de prelungire: nota de după una cu „~” primește sfârșitul legăturii."""
    note_ = list(parte.recurse().notes)
    for a, b in zip(note_, note_[1:]):
        if a.tie is not None and a.tie.type == 'start':
            if b.tie is None:
                b.tie = tie.Tie('stop')
            elif b.tie.type == 'start':
                b.tie = tie.Tie('continue')


def randuri(text: str) -> list:
    """Rândurile textului; rândurile goale de la sfârșit nu contează."""
    r = text.replace('\r\n', '\n').split('\n')
    while r and not r[-1].strip():
        r.pop()
    return r


def construieste(dreapta: str, stanga: str, titlu='', compozitor='', masura='4/4', alteratii=0, tempo_p=0,
                 anacruza=False):
    """Partitura music21 din textul celor două mâini. Întoarce (scor, probleme): probleme = lista măsurilor
    care nu au durata potrivită (nu oprește construirea). Aruncă EroareScriere pentru ce nu se poate citi."""
    rd, rs = randuri(dreapta), randuri(stanga)
    n = max(len(rd), len(rs))
    if n == 0:
        raise EroareScriere(_('Nu ai scris nicio notă.'))
    ts_text = masura
    armura = _armura(alteratii)
    plina = meter.TimeSignature(ts_text).barDuration.quarterLength
    scor = stream.Score()
    md = metadata.Metadata()
    md.title = titlu or _('Fără titlu')
    if compozitor:
        md.composer = compozitor
    scor.metadata = md
    doua = any(x.strip() for x in rs)
    probleme = []
    parti = []
    for mana, rr, cheie, oct0 in (('mâna dreaptă', rd, clef.TrebleClef(), 4), ('mâna stângă', rs, clef.BassClef(), 3)):
        if mana == 'mâna stângă' and not doua:
            continue
        parte = stream.PartStaff() if doua else stream.Part()
        parte.partName = _('Pian')
        parte.insert(0, instrument.Piano())
        stare = _Stare(oct0)
        for k in range(n):
            nr = k if anacruza else k + 1
            m = stream.Measure(number=nr)
            if k == 0:
                m.insert(0, cheie)
                m.insert(0, key.KeySignature(alteratii))
                m.insert(0, meter.TimeSignature(ts_text))
                if tempo_p and mana == 'mâna dreaptă':
                    m.insert(0, tempo.MetronomeMark(number=tempo_p, referent=duration.Duration(1.0)))
            text = rr[k] if k < len(rr) else ''
            el = citeste_masura(text, stare, armura, nr, mana)
            if not el:
                r = note.Rest()
                r.duration = duration.Duration(plina)
                r.fullMeasure = True
                el = [r]
            total = sum(e.duration.quarterLength for e in el)
            for e in el:
                m.append(e)
            if anacruza and k == 0 and total < plina:
                m.paddingLeft = plina - total
            elif abs(total - plina) > 1e-6:
                cum = _('prea multe') if total > plina else _('prea puține')
                probleme.append(_('Măsura {0}, {1}: {2} timpi ({3} în loc de {4}).', nr, _(mana), cum, _timpi(total), _timpi(plina)))
            if k == n - 1:
                m.rightBarline = bar.Barline('final')
            parte.append(m)
        _leaga(parte)
        parti.append(parte)
    for p in parti:
        scor.insert(0, p)
    if doua:
        scor.insert(0, layout.StaffGroup(parti, name=_('Pian'), symbol='brace', barTogether=True))
    return scor, probleme


def _timpi(q):
    """Durata în pătrimi, spusă cu cuvinte simple."""
    q = float(q)
    if abs(q - round(q)) < 1e-6:
        n = int(round(q))
        return _('1 pătrime') if n == 1 else _('{0} pătrimi', n)
    return _('{0:g} pătrimi', q).replace('.', ',')


AJUTOR = _(__doc__)
