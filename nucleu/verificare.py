"""Verificarea recunoașterii: compară ce au citit mai multe programe și caută măsurile greșite.

Ideea: un PDF e doar un desen, iar programele de recunoaștere ghicesc notele. Fiecare greșește în alte locuri.
- Aliniem măsurile citite de fiecare program (pot pierde sau adăuga o bară de măsură).
- Unde programele citesc la fel o măsură, e foarte probabil corectă.
- Unde nu sunt de acord, alegem varianta care trece verificarea de durată (notele umplu exact măsura)
  și, la trei programe, varianta cu care sunt de acord două; măsura rămâne marcată „nesigură”.
"""
import copy
from dataclasses import dataclass, field
from fractions import Fraction

from music21 import chord, meter, note, stream

# ---------------------------------------------------------------- note dintr-o măsură


def _fr(x):
    return Fraction(x).limit_denominator(48)


def evenimente_masura(m) -> tuple:
    """Notele unei măsuri ca (timp în măsură, înălțime MIDI, durată), sortate; pauzele nu contează aici."""
    ev = []
    for n in m.recurse().notes:
        if n.duration.isGrace:
            continue
        off = _fr(n.getOffsetInHierarchy(m))
        d = _fr(n.duration.quarterLength)
        pitches = n.pitches if isinstance(n, chord.Chord) else [n.pitch]
        for p in pitches:
            ev.append((off, int(round(p.ps)), d))
    return tuple(sorted(ev))


def masuri_portativ(p) -> list:
    return list(p.getElementsByClass(stream.Measure))


def portative_pian(scor) -> list:
    """Cele două portative ale pianului (dreapta, stânga) sau toate partidele, ca liste de măsuri."""
    parti = list(scor.parts)
    return [masuri_portativ(p) for p in parti]


@dataclass
class Masura:
    """O măsură „verticală”: aceeași măsură pe toate portativele."""
    portative: list            # listă de obiecte stream.Measure (unul pe portativ, sau None)
    ev: tuple = ()             # evenimentele pe fiecare portativ (tuplu de tupluri)
    durata_ok: bool = True
    probleme: list = field(default_factory=list)


def masuri_verticale(scor) -> list:
    port = portative_pian(scor)
    if not port:
        return []
    n = max(len(p) for p in port)
    rez = []
    for i in range(n):
        ms = [p[i] if i < len(p) else None for p in port]
        ev = tuple(evenimente_masura(m) if m is not None else () for m in ms)
        rez.append(Masura(ms, ev))
    _verifica_durate(rez)
    return rez


# ---------------------------------------------------------------- verificarea duratei


def _lungime_masura(m):
    ts = m.getContextByClass(meter.TimeSignature)
    return _fr(ts.barDuration.quarterLength) if ts else None


def _durata_voci(m) -> list:
    """Durata ocupată de fiecare voce a măsurii (sau de măsură, dacă nu are voci)."""
    voci = list(m.voices)
    if not voci:
        voci = [m]
    rez = []
    for v in voci:
        sfarsit = Fraction(0)
        for el in v.getElementsByClass((note.GeneralNote,)):
            if el.duration.isGrace:
                continue
            sfarsit = max(sfarsit, _fr(el.offset) + _fr(el.duration.quarterLength))
        rez.append(sfarsit)
    return rez


def _verifica_durate(masuri):
    """Marchează măsurile în care notele nu umplu exact măsura (în afară de prima și ultima, care pot fi incomplete)."""
    for i, M in enumerate(masuri):
        for k, m in enumerate(M.portative):
            if m is None:
                continue
            L = _lungime_masura(m)
            if L is None:
                continue
            for d in _durata_voci(m):
                if d == 0:
                    continue
                prea_scurta = d < L and 0 < i < len(masuri) - 1
                if d > L or prea_scurta:
                    M.durata_ok = False
                    M.probleme.append(f'portativul {k + 1}: notele dau {_text_durata(d)} în loc de {_text_durata(L)}')
                    break


def _text_durata(q: Fraction) -> str:
    patrimi = q
    if patrimi.denominator == 1:
        return f'{patrimi.numerator} pătrimi'
    return f'{float(patrimi):.2f} pătrimi'


# ---------------------------------------------------------------- comparare și aliniere


def asemanare(a: tuple, b: tuple) -> float:
    """Cât de asemănătoare sunt două măsuri verticale (0..1), după notele comune."""
    total = 0
    comune = 0
    for x, y in zip(a, b):
        sx, sy = list(x), list(y)
        total += max(len(sx), len(sy))
        rest = list(sy)
        for e in sx:
            if e in rest:
                rest.remove(e); comune += 1
    if total == 0:
        return 1.0
    return comune / total


def aliniaza(A: list, B: list):
    """Aliniere Needleman–Wunsch între două liste de măsuri; întoarce perechi (i sau None, j sau None)."""
    n, m = len(A), len(B)
    GOL = -0.6
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        S[i][0] = i * GOL
    for j in range(1, m + 1):
        S[0][j] = j * GOL
    sim = [[asemanare(A[i].ev, B[j].ev) for j in range(m)] for i in range(n)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            S[i][j] = max(S[i - 1][j - 1] + 2 * sim[i - 1][j - 1] - 1, S[i - 1][j] + GOL, S[i][j - 1] + GOL)
    i, j = n, m
    rez = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(S[i][j] - (S[i - 1][j - 1] + 2 * sim[i - 1][j - 1] - 1)) < 1e-9:
            rez.append((i - 1, j - 1)); i -= 1; j -= 1
        elif i > 0 and abs(S[i][j] - (S[i - 1][j] + GOL)) < 1e-9:
            rez.append((i - 1, None)); i -= 1
        else:
            rez.append((None, j - 1)); j -= 1
    rez.reverse()
    return rez


# ---------------------------------------------------------------- votul


@dataclass
class Rezultat:
    scor: object                 # partitura combinată (music21 Score)
    sigure: int                  # măsuri pe care programele le-au citit la fel
    nesigure: list               # (număr măsură, motiv) pentru măsurile de verificat
    programe: list               # numele programelor folosite


def combina(scoruri: dict) -> Rezultat:
    """scoruri: {nume program: music21 Score}, în ordinea încrederii (primul e „de bază”).
    Măsurile pe care le-a citit doar un program (celălalt a sărit un rând, de exemplu) se păstrează și ele."""
    nume = list(scoruri)
    vert = {n: masuri_verticale(scoruri[n]) for n in nume}
    baza = nume[0]
    B = vert[baza]
    nport = len(portative_pian(scoruri[baza]))
    # pozițiile finale: măsurile bazei, plus cele găsite doar de al doilea program, la locul lor
    pozitii = [{baza: M} for M in B]
    if len(nume) > 1:
        alt = nume[1]
        noi = []
        for i, j in aliniaza(B, vert[alt]):
            if i is not None:
                noi.append(pozitii[i])
                if j is not None:
                    noi[-1][alt] = vert[alt][j]
            elif len(vert[alt][j].portative) == nport:
                noi.append({alt: vert[alt][j]})
        pozitii = noi
        for alt in nume[2:]:          # al treilea program (dacă există) doar votează pe măsurile bazei
            for i, j in aliniaza(B, vert[alt]):
                if i is not None and j is not None:
                    for poz in pozitii:
                        if poz.get(baza) is B[i]:
                            poz[alt] = vert[alt][j]
    rezultat = copy.deepcopy(scoruri[baza])
    parti = list(rezultat.parts)
    for p in parti:
        for m in list(p.getElementsByClass(stream.Measure)):
            p.remove(m)
    prim = _numar(B[0], 0) if B else 1
    nr = prim if prim in (0, 1) else 1
    sigure, nesigure = 0, []
    copii = []
    for poz in pozitii:
        ales, motiv = _alege(poz, nume)
        M = poz[ales]
        cop = []
        for k, p in enumerate(parti):
            m = M.portative[k] if k < len(M.portative) else None
            m2 = copy.deepcopy(m) if m is not None else stream.Measure()
            m2.number = nr
            p.append(m2)
            cop.append(m2)
        copii.append((poz, M, cop))
        if motiv is None:
            sigure += 1
        else:
            nesigure.append((nr, motiv))
        nr += 1
    for alt in nume[1:]:
        _imbogateste(rezultat, copii, alt, scoruri[alt])
        _dubli_diezi(copii, alt)
    return Rezultat(rezultat, sigure, nesigure, nume)


def _dubli_diezi(copii, alt):
    """homr nu citește dublii diezi și dublii bemoli (fa dublu diez iese fa). Unde celălalt program are, pe aceeași
    treaptă, în același loc și cu aceeași durată, un dublu diez sau dublu bemol, îl luăm de la el."""
    from music21 import pitch as m21pitch
    for poz, M_ales, cop in copii:
        Ma = poz.get(alt)
        if Ma is None or Ma is M_ales:
            continue
        duble = {}
        for m in Ma.portative:
            if m is None:
                continue
            for n in m.recurse().notes:
                for p in n.pitches:
                    if p.accidental is not None and abs(p.accidental.alter) == 2:
                        duble[(_fr(n.getOffsetInHierarchy(m)), p.step, p.octave, _fr(n.duration.quarterLength))] = p.accidental.alter
        if not duble:
            continue
        for m in cop:
            for n in m.recurse().notes:
                for p in n.pitches:
                    k = (_fr(n.getOffsetInHierarchy(m)), p.step, p.octave, _fr(n.duration.quarterLength))
                    if k in duble and (p.accidental is None or abs(p.accidental.alter) != 2):
                        p.accidental = m21pitch.Accidental(duble[k])


# ---------------------------------------------------------------- semnele din jurul notelor
# Programele citesc diferit și semnele care nu sunt note: unul prinde legato-urile și nuanțele, altul nu.
# Unde notele unei măsuri sunt identice la două programe, adăugăm semnele pe care le-a prins doar celălalt.

def _note_ordonate(m):
    rez = []
    for n in m.recurse().notes:
        if n.duration.isGrace:
            continue
        cheie = (_fr(n.getOffsetInHierarchy(m)), tuple(sorted(int(round(p.ps)) for p in n.pitches)), _fr(n.duration.quarterLength))
        rez.append((cheie, n))
    rez.sort(key=lambda x: x[0])
    return rez


def _imbogateste(rezultat, copii, alt, scor_alt):
    from music21 import articulations, dynamics, expressions, spanner, tempo
    corespondenta = {}
    for poz, M_ales, cop in copii:
        Ma = poz.get(alt)
        if Ma is None or Ma.ev != M_ales.ev:
            continue
        for k, m_dest in enumerate(cop):
            if k >= len(Ma.portative) or Ma.portative[k] is None:
                continue
            m_src = Ma.portative[k]
            a, b = _note_ordonate(m_src), _note_ordonate(m_dest)
            if [x[0] for x in a] != [x[0] for x in b]:
                continue
            for (_, ns), (_, nd) in zip(a, b):
                corespondenta[id(ns)] = nd
                for art in ns.articulations:
                    if not any(type(x) is type(art) for x in nd.articulations):
                        nd.articulations.append(copy.deepcopy(art))
                for ex in ns.expressions:
                    if not any(type(x) is type(ex) for x in nd.expressions):
                        nd.expressions.append(copy.deepcopy(ex))
            # nuanțe, indicații de tempo și text scrise în măsură
            for el in m_src.recurse().getElementsByClass((dynamics.Dynamic, expressions.TextExpression, tempo.TempoIndication)):
                off = el.getOffsetInHierarchy(m_src)
                if not any(type(x) is type(el) and abs(x.getOffsetInHierarchy(m_dest) - off) < 1e-6
                           for x in m_dest.recurse().getElementsByClass(type(el))):
                    m_dest.insert(off, copy.deepcopy(el))
    if not corespondenta:
        return
    parti = list(rezultat.parts)
    existente = set()
    for sp in rezultat.recurse().getElementsByClass(spanner.Spanner):
        existente.add((type(sp).__name__, tuple(id(x) for x in sp.getSpannedElements())))
    for sp in scor_alt.recurse().getElementsByClass((spanner.Slur, dynamics.DynamicWedge)):
        el = sp.getSpannedElements()
        if not el or not all(id(x) in corespondenta for x in el):
            continue
        noi = [corespondenta[id(x)] for x in el]
        cheie = (type(sp).__name__, tuple(id(x) for x in noi))
        if cheie in existente:
            continue
        nou = type(sp)(noi)
        tinta = next((p for p in parti if noi[0] in p.recurse().notes), parti[0] if parti else rezultat)
        tinta.insert(0, nou)
        existente.add(cheie)


def _numar(M, i):
    for m in M.portative:
        if m is not None and m.number is not None:
            return m.number
    return i + 1


def _toate(M) -> tuple:
    """Toate notele măsurii verticale, de pe toate portativele, într-o singură listă."""
    return tuple(sorted(e for ev in M.ev for e in ev))


def _alege(var: dict, ordine: list):
    """Alege varianta unei măsuri. Întoarce (programul ales, motiv de nesiguranță sau None)."""
    prezente = [n for n in ordine if n in var]
    if len(prezente) == 1:
        M = var[prezente[0]]
        if not M.durata_ok:
            return prezente[0], 'notele nu umplu corect măsura (' + '; '.join(M.probleme) + ')'
        if len(ordine) > 1:
            return prezente[0], 'a citit-o doar ' + prezente[0]
        return prezente[0], None
    # grupuri de programe care au citit identic
    # aceleași note, chiar dacă un program le-a pus pe alt portativ (mâinile pe același portativ), înseamnă „la fel”
    grupuri = []
    for n in prezente:
        for g in grupuri:
            if var[g[0]].ev == var[n].ev or _toate(var[g[0]]) == _toate(var[n]):
                g.append(n); break
        else:
            grupuri.append([n])
    if len(grupuri) == 1:
        M = var[prezente[0]]
        if M.durata_ok:
            return prezente[0], None
        return prezente[0], 'toate programele au citit la fel, dar notele nu umplu corect măsura (' + '; '.join(M.probleme) + ')'
    # nu sunt de acord: majoritate, apoi verificarea de durată, apoi ordinea programelor
    grupuri.sort(key=lambda g: (-len(g), not var[g[0]].durata_ok, ordine.index(g[0])))
    cel_mai_bun = grupuri[0]
    if len(cel_mai_bun) > 1 and len(cel_mai_bun) > len(grupuri[1]):
        motiv = f'{", ".join(cel_mai_bun)} au citit la fel, {", ".join(n for g in grupuri[1:] for n in g)} altfel'
    else:
        motiv = 'programele au citit-o diferit'
        if var[cel_mai_bun[0]].durata_ok and not all(var[g[0]].durata_ok for g in grupuri[1:]):
            motiv += f'; am ales varianta lui {cel_mai_bun[0]}, singura care umple corect măsura'
    return cel_mai_bun[0], motiv


# ---------------------------------------------------------------- comparare cu originalul (pentru probe)


def compara_cu_originalul(original, citit) -> dict:
    """Câte măsuri și câte note au ieșit exact ca în original. Folosit la probe."""
    O, C = masuri_verticale(original), masuri_verticale(citit)
    perechi = aliniaza(O, C)
    masuri_ok = 0
    note_ok = note_orig = note_citite = 0
    gresite = []
    for i, j in perechi:
        if i is not None:
            note_orig += sum(len(x) for x in O[i].ev)
        if j is not None:
            note_citite += sum(len(x) for x in C[j].ev)
        if i is not None and j is not None:
            if O[i].ev == C[j].ev:
                masuri_ok += 1
            else:
                gresite.append(_numar(O[i], i))
            for x, y in zip(O[i].ev, C[j].ev):
                rest = list(y)
                for e in x:
                    if e in rest:
                        rest.remove(e); note_ok += 1
        elif i is not None:
            gresite.append(_numar(O[i], i))
    return {'masuri': len(O), 'masuri_ok': masuri_ok, 'note': note_orig, 'note_ok': note_ok,
            'note_in_plus': note_citite - note_ok, 'gresite': gresite}


def uneste_pagini(scoruri: list):
    """Lipește partiturile citite pagină cu pagină (homr citește fiecare pagină separat) într-una singură."""
    if len(scoruri) == 1:
        return scoruri[0]
    rez = copy.deepcopy(scoruri[0])
    parti = list(rez.parts)
    nr = max((m.number or 0) for m in parti[0].getElementsByClass(stream.Measure)) if parti else 0
    for s in scoruri[1:]:
        alte = list(s.parts)
        nou = max((len(list(p.getElementsByClass(stream.Measure))) for p in alte), default=0)
        for k, p in enumerate(parti):
            if k >= len(alte):
                continue
            for j, m in enumerate(alte[k].getElementsByClass(stream.Measure)):
                m2 = copy.deepcopy(m)
                m2.number = nr + j + 1
                p.append(m2)
        nr += nou
    return rez


# ---------------------------------------------------------------- mâinile pe același portativ
# La pian, uneori ambele mâini sunt scrise pe un singur portativ (de exemplu Cramer, Studiul 13: mâna stângă
# urcă pe portativul de sus, iar cel de jos rămâne gol). Programele de recunoaștere pun atunci toate notele
# la mâna de pe portativul acela. Le despărțim: din fiecare acord, nota de sus merge la mâna dreaptă,
# celelalte la mâna stângă.

def _are_note(m) -> bool:
    return m is not None and any(not n.duration.isGrace for n in m.recurse().notes)


def _goleste(m):
    for el in list(m.recurse().getElementsByClass((note.GeneralNote, stream.Voice))):
        try:
            el.activeSite.remove(el)
        except Exception:
            pass


def _tacere(m, L):
    """Intervalele (început, sfârșit) din măsură în care portativul nu are nicio notă care sună."""
    ocupat = []
    if m is not None:
        for n in m.recurse().notes:
            if n.duration.isGrace:
                continue
            a = _fr(n.getOffsetInHierarchy(m))
            ocupat.append((a, a + _fr(n.duration.quarterLength)))
    ocupat.sort()
    libere, t = [], Fraction(0)
    for a, b in ocupat:
        if a > t:
            libere.append((t, a))
        t = max(t, b)
    if t < L:
        libere.append((t, L))
    return libere


def _in(off, d, libere):
    return any(a <= off and off + d <= b for a, b in libere)


def _voci_care_suna(m):
    """Funcție: câte obiecte-notă diferite (din voci diferite) sună la un moment dat în măsură."""
    el = []
    for n in m.recurse().notes:
        if n.duration.isGrace:
            continue
        a = _fr(n.getOffsetInHierarchy(m))
        el.append((a, a + _fr(n.duration.quarterLength)))
    return lambda o: sum(1 for a, b in el if a <= o < b)


def _verticale(m):
    v = m.chordify()
    return [(_fr(e.getOffsetInHierarchy(v)), e) for e in v.recurse().notesAndRests]


def imparte_mainile(scor) -> list:
    """Unde un portativ al pianului tace cel puțin o jumătate de măsură, iar celălalt are acolo acorduri aproape
    peste tot, împarte notele între mâini (nota de sus la dreapta, restul la stânga).
    Întoarce numerele măsurilor schimbate."""
    parti = list(scor.parts)
    if len(parti) != 2:
        return []
    sus, jos = (masuri_portativ(p) for p in parti)
    schimbate = []
    for i in range(min(len(sus), len(jos))):
        ms, mj = sus[i], jos[i]
        L = _lungime_masura(ms) or _fr(ms.duration.quarterLength)
        facut = False
        for src, alt, sursa_sus in ((ms, mj, True), (mj, ms, False)):
            if facut or not _are_note(src):
                continue
            libere = _tacere(alt, L)
            # mâna stângă urcă sus: ajunge ca portativul de jos să tacă o jumătate de măsură;
            # mâna dreaptă coboară jos: doar dacă portativul de sus tace toată măsura
            # (altfel sunt de obicei două voci ale mâinii stângi)
            if sum(b - a for a, b in libere) < (L / 2 if sursa_sus else L):
                continue
            try:
                vs, va = _verticale(src), _verticale(alt)
            except Exception:
                continue
            in_liniste = [(o, e) for o, e in vs if not e.isRest and _in(o, _fr(e.duration.quarterLength), libere)]
            # doar sunetele din voci diferite (codițe în sus și în jos) pot fi ale celeilalte mâini;
            # un acord scris cu o singură codiță (de exemplu octavele mâinii drepte) rămâne la mâna lui
            voci = _voci_care_suna(src)
            duble = sum(1 for o, e in in_liniste if len(e.pitches) >= 2 and voci(o) >= 2)
            if not in_liniste or duble / len(in_liniste) < 0.6:
                continue
            noi_src, noi_alt = [], []
            for o, e in vs:
                d = e.duration.quarterLength
                if e.isRest or len(e.pitches) < 2 or not _in(o, _fr(d), libere):
                    noi_src.append((o, copy.deepcopy(e)))
                    continue
                p = sorted(e.pitches, key=lambda x: x.ps)
                pastrat, mutat = ([p[-1]], p[:-1]) if sursa_sus else (p[:-1], [p[-1]])
                for lst, ps in ((noi_src, pastrat), (noi_alt, mutat)):
                    n = note.Note(ps[0], quarterLength=d) if len(ps) == 1 else chord.Chord(ps, quarterLength=d)
                    n.tie = copy.deepcopy(e.tie)
                    lst.append((o, n))
            # pe portativul celălalt: ce era deja (în afara liniștii) plus notele mutate, iar pauze în rest
            for o, e in va:
                d = _fr(e.duration.quarterLength)
                if not e.isRest:
                    noi_alt.append((o, copy.deepcopy(e)))
            noi_alt.sort(key=lambda x: x[0])
            completat, t = [], Fraction(0)
            for o, e in noi_alt:
                if o > t:
                    completat.append((t, note.Rest(quarterLength=float(o - t))))
                completat.append((o, e))
                t = max(t, o + _fr(e.duration.quarterLength))
            if t < L:
                completat.append((t, note.Rest(quarterLength=float(L - t))))
            _goleste(src)
            _goleste(alt)
            for m, lista in ((src, noi_src), (alt, completat)):
                for off, el in _uneste_pauze(lista):
                    m.insert(float(off), el)
            schimbate.append(ms.number if ms.number is not None else i + 1)
            facut = True
    return schimbate


def _uneste_pauze(lista):
    """Pauzele vecine se unesc într-una singură (dacă dau o durată obișnuită)."""
    from music21 import duration as dur
    rez = []
    for off, el in lista:
        if el.isRest and rez and rez[-1][1].isRest:
            q = rez[-1][1].quarterLength + el.quarterLength
            try:
                d = dur.Duration(q)
                if d.type not in ('complex', 'inexpressible'):
                    rez[-1] = (rez[-1][0], note.Rest(quarterLength=q))
                    continue
            except Exception:
                pass
        rez.append((off, el))
    return rez
