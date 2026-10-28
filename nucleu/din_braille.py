"""Din Braille muzical (fișiere .brl / .brf în Braille ASCII) în partitură music21, deci în MusicXML.
Regulile sunt cele din manualul Krolick („Cum să citim muzica în Braille”) și din Instrucțiunile lui Răzvan,
aceleași pe care le folosește programul când scrie Braille (vezi braille.py).

Ce înțelege:
- titlul (rândul centrat de sus; mai multe piese în același fișier, despărțite prin titluri sau prin pagină nouă);
- armura și măsura (% diez, < bemol, apoi #C4 = 3/4, #D4 = 4/4; C = 46 14, C tăiat = 456 14);
- numerele de măsură de la începutul rândului (A = 1, C = 3, AA = 11), cratima muzicală (punctul 5 la capăt de rând);
- notele cu duratele lor, punctul de prelungire, alterațiile (ținute toată măsura), semnele de octavă și regula
  octavei (secundă și terță: cea mai apropiată; cvartă și cvintă: aceeași octavă; de la sextă: cu semn);
- pauzele, legato de prelungire (4 14), legato de expresie (14, se sare), trioletul (23),
  repetiția unei bucăți de măsură (2356), bara finală (126 13), repetițiile (126 2356 / 126 23);
- acordurile prin intervale (secundă 34 ... octavă 36);
- mâna dreaptă și mâna stângă la pian (46 345 / 456 345), în format bară pe bară.
Duratele care în Braille au aceeași formă (optime/128-ime, șaisprezecime/notă întreagă, gruparea șaisprezecimilor)
se aleg așa încât măsura să aibă exact timpii ei. Măsurile care tot nu se potrivesc se marchează „de verificat”.
"""
import itertools
import re

from music21 import bar, chord, clef, duration, key, meter, metadata, note, pitch, stream, tie, layout

PASI = 'CDEFGAB'
# litera notei -> (treapta 0..6, forma): forma 8 = optime/128-ime, 4 = pătrime/64-ime, 2 = doime/32-ime, 1 = întreagă/16-ime
NOTE = {}
for _i, _l in enumerate('DEFGHIJ'):
    NOTE[_l] = (_i, 8)
for _i, _l in enumerate('?:$]\\[W'):
    NOTE[_l] = (_i, 4)
for _i, _l in enumerate('NOPQRST'):
    NOTE[_l] = (_i, 2)
for _i, _l in enumerate('YZ&=(!)'):
    NOTE[_l] = (_i, 1)
PAUZE = {'X': 8, 'V': 4, 'U': 2, 'M': 1}
OCTAVE = {'@': 1, '^': 2, '_': 3, '"': 4, '.': 5, ';': 6, ',': 7}
ALT = {'%': 1, '<': -1, '*': 0}
INTERVALE = {'/': 2, '+': 3, '#': 4, '9': 5, '0': 6, '3': 7, '-': 8}
# valorile mari și mici ale fiecărei forme, în pătrimi
MARE = {8: 0.5, 4: 1.0, 2: 2.0, 1: 4.0}
MIC = {8: 1 / 32, 4: 1 / 16, 2: 1 / 8, 1: 0.25}
NUMERE_SUS = {'A': '1', 'B': '2', 'C': '3', 'D': '4', 'E': '5', 'F': '6', 'G': '7', 'H': '8', 'I': '9', 'J': '0'}
NUMERE_JOS = {'1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '0': '0'}
# cifrele de jos în Braille ASCII: punctele 2, 23, 25, 256, 26, 235, 2356, 236, 35, 356
JOS = {'1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '0': '0'}


class Element:
    """O notă, un acord sau o pauză citită din Braille, înainte de a-i ști durata sigur."""
    def __init__(self, tip, forma, treapta=None, octava=None, alter=None, puncte=0):
        self.tip = tip                # 'nota' / 'pauza'
        self.forma = forma
        self.treapta = treapta
        self.octava = octava          # None = după regula octavei
        self.alter = alter
        self.puncte = puncte
        self.intervale = []           # acord: [(interval, octava sau None, alter)]
        self.legat = False            # legato de prelungire spre următoarea
        self.triolet = False
        self.mare = None              # alegerea duratei (None = încă nu)
        self.grupat = False           # șaisprezecime prin grupare (formă de optime)


class Masura:
    def __init__(self, numar):
        self.numar = numar
        self.elemente = []
        self.repetitie_inceput = False
        self.repetitie_sfarsit = False
        self.finala = False
        self.de_verificat = []


class Piesa:
    def __init__(self, titlu):
        self.titlu = titlu
        self.armura = 0
        self.masura = '4/4'
        self.maini = {'dreapta': [], 'stanga': []}
        self.pian = False


def _numar_sus(t):
    return int(''.join(NUMERE_SUS[c] for c in t)) if t and all(c in NUMERE_SUS for c in t) else None


def _antet(linie):
    """„%#C4” -> (armura, '3/4'); None dacă nu e rândul de armură și măsură."""
    m = re.fullmatch(r'\s*([%<]*)(?:#([A-J]))?([%<]?)\s*#([A-J]+)([0-9]+)\s*', linie)
    if m:
        alt = m.group(1) + m.group(3)
        n = len(alt) if not m.group(2) else _numar_sus(m.group(2))     # de la 4 alterații: cifra, apoi semnul
        semn = 1 if '%' in alt else -1 if '<' in alt else 0
        sus = _numar_sus(m.group(4))
        jos = ''.join(JOS.get(c, '') for c in m.group(5))
        return semn * n, f'{sus}/{jos}'
    m = re.fullmatch(r'\s*([%<]*)\s*([._])C\s*', linie)
    if m:
        alt = m.group(1)
        return (alt.count('%') - alt.count('<')), ('4/4' if m.group(2) == '.' else '2/2')
    return None


_MICI = str.maketrans({**{chr(c): chr(c - 32) for c in range(ord('a'), ord('z') + 1)},
                       '`': '@', '{': '[', '|': '\\', '}': ']', '~': '^'})


def citeste_text(text):
    """Textul Braille ASCII -> lista de piese (fiecare cu măsurile pe mâini)."""
    text = text.translate(_MICI)              # unele fișiere BRF sunt scrise cu litere mici: aceleași celule
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\f', '\n\f\n')
    piese = []
    p = None
    rand_continuat = ''
    for linie in text.split('\n'):
        l = linie.rstrip()
        if not l.strip() or l.strip() == '\f':
            continue
        if p is None or (re.match(r'^\s{3,}\S', l) and not rand_continuat and (_antet(l) is None) and not _e_muzica(l)):
            # titlu (centrat)
            if p is not None and not any(p.maini.values()) and _antet(l) is None:
                p.titlu += ' ' + _titlu(l)
                continue
            if _antet(l) is None:
                p = Piesa(_titlu(l))
                piese.append(p)
                continue
        a = _antet(l)
        if a is not None:
            if p is None:
                p = Piesa('')
                piese.append(p)
            p.armura, p.masura = a
            continue
        if l.endswith('"'):                 # cratima muzicală: măsura continuă pe rândul următor
            rand_continuat += (l.lstrip() if rand_continuat else l)[:-1]
            continue
        rand = rand_continuat + (l.lstrip() if rand_continuat else l)
        rand_continuat = ''
        _citeste_rand(p, rand)
    return piese


def _e_muzica(l):
    return bool(re.search(r'[DEFGHIJ?:$\]\\\[WNOPQRSTYZ&=(!)]', l)) and not re.match(r'^\s+[.,]?[A-Z ]+(\s#[A-J]+)?$', l)


def _titlu(l):
    t = l.strip()
    # majusculele (punctul 6 = „,”; 46 = „.” la Răzvan) și cifrele cu semn de număr
    t = re.sub(r'#([A-J]+)', lambda m: str(_numar_sus(m.group(1))), t)
    t = t.replace(',', '').replace('.', '')
    return t.title() if t.isupper() else t


def _citeste_rand(p, rand):
    """Un rând de muzică: numărul primei măsuri (fără semn de număr), apoi măsurile despărțite prin spații.
    La pian, 46 345 (.>) începe mâna dreaptă și 456 345 (_>) mâna stângă; amândouă pornesc de la numărul rândului."""
    m = re.match(r'^\s*([A-J]+)\s+(.*)$', rand)
    if m:
        p.rand = _numar_sus(m.group(1))
        rand = m.group(2)
        urm = {'dreapta': p.rand, 'stanga': p.rand}
        mana = 'dreapta'
    else:
        urm = {}
        mana = getattr(p, 'mana', 'dreapta')     # rând continuat: aceeași mână ca rândul de deasupra
    # cuvintele (tempo, nuanțe): semnul de cuvânt 345, literele, punctul 3 — nu sunt note
    rand = re.sub(r"'?>(?=[A-Z])[A-Z]+'?", ' ', rand.replace('.>', '\x01').replace('_>', '\x02'))
    rand = rand.replace('\x01', ' .>').replace('\x02', ' _>')
    for b in rand.split():
        if b.startswith('.>'):
            mana, b, p.pian = 'dreapta', b[2:], True
            urm[mana] = getattr(p, 'rand', None)
        elif b.startswith('_>'):
            mana, b, p.pian = 'stanga', b[2:], True
            urm[mana] = getattr(p, 'rand', None)
        p.mana = mana
        if not b:
            continue
        lista = p.maini[mana]
        nr = urm.get(mana)
        if nr is None:
            nr = (lista[-1].numar + 1) if lista else 1
        urm[mana] = nr + 1
        msr = Masura(nr)
        _citeste_masura(b, msr)
        lista.append(msr)


def _citeste_masura(t, msr):
    i = 0
    octava = alter = None
    triolet_ramase = 0
    while i < len(t):
        c = t[i]
        rest = t[i:]
        if rest.startswith('<K'):
            msr.finala = True
            i += 2
            continue
        if rest.startswith('<7'):
            msr.repetitie_inceput = True
            i += 2
            continue
        if rest.startswith('<2'):
            msr.repetitie_sfarsit = True
            i += 2
            continue
        if rest.startswith('@C'):
            if msr.elemente:
                msr.elemente[-1].legat = True
            i += 2
            continue
        if c == '7':                       # repetă bătaia de dinainte (o bucată de măsură)
            msr.elemente.append('repeta')
            i += 1
            continue
        if c == '2' and i + 1 < len(t) and (t[i + 1] in NOTE or t[i + 1] in OCTAVE or t[i + 1] in ALT or t[i + 1] in PAUZE):
            triolet_ramase = 3
            i += 1
            continue
        if c in ALT:
            alter = ALT[c] if alter is None else alter + ALT[c]
            i += 1
            continue
        if c in OCTAVE and i + 1 < len(t) and (t[i + 1] in NOTE or t[i + 1] in ALT or t[i + 1] in OCTAVE or t[i + 1] in INTERVALE):
            octava = OCTAVE[c]
            i += 1
            continue
        if c in NOTE:
            treapta, forma = NOTE[c]
            e = Element('nota', forma, treapta, octava, alter)
            octava = alter = None
            i += 1
            while i < len(t) and t[i] == "'":
                e.puncte += 1
                i += 1
            if triolet_ramase:
                e.triolet = True
                triolet_ramase -= 1
            msr.elemente.append(e)
            continue
        if c in PAUZE:
            e = Element('pauza', PAUZE[c])
            i += 1
            while i < len(t) and t[i] == "'":
                e.puncte += 1
                i += 1
            if triolet_ramase:
                e.triolet = True
                triolet_ramase -= 1
            msr.elemente.append(e)
            continue
        if c in INTERVALE and msr.elemente and isinstance(msr.elemente[-1], Element) and msr.elemente[-1].tip == 'nota':
            msr.elemente[-1].intervale.append((INTERVALE[c], octava, alter))
            octava = alter = None
            i += 1
            continue
        if c == 'C':                       # legato de expresie: nu schimbă sunetul
            i += 1
            continue
        msr.de_verificat.append(f'semn necunoscut „{c}”')
        i += 1


# ---------------- duratele ----------------
def _valoare(e, mare=True):
    if getattr(e, 'masura_intreaga', None):
        return e.masura_intreaga
    v = (MARE if mare else MIC)[e.forma]
    if e.grupat:
        v = 0.25
    v *= (2 - 0.5 ** e.puncte)
    if e.triolet:
        v *= 2 / 3
    return v


def _desface_repetitii(elemente, bata):
    """„7” (2356) repetă ultima bătaie: notele de la sfârșit care fac împreună o bătaie."""
    rez = []
    for e in elemente:
        if e != 'repeta':
            rez.append(e)
            continue
        total, k = 0.0, len(rez)
        while k > 0 and total + 1e-6 < bata:
            k -= 1
            total += _valoare(rez[k], rez[k].mare if rez[k].mare is not None else True)
        import copy
        for x in rez[k:]:
            y = copy.copy(x)
            y.intervale = list(x.intervale)
            y.legat = False
            y.octava = x.octava
            rez.append(y)
    return rez


def rezolva_durate(msr, plina, bata):
    """Alege duratele ambigue astfel încât măsura să aibă exact timpii ei."""
    el = [e for e in msr.elemente if e != 'repeta']
    for e in el:
        e.mare = True
    if len(el) == 1 and el[0].tip == 'pauza' and el[0].forma == 1 and not el[0].puncte:
        el[0].masura_intreaga = plina          # pauza „m” singură în măsură = toată măsura
        return True
    # gruparea: o formă de șaisprezecime urmată de 3 forme de optime = 4 șaisprezecimi
    grupuri = []
    for k, e in enumerate(el):
        if e.forma == 1 and k + 3 < len(el) and all(x.forma == 8 and x.tip == e.tip == 'nota' and not x.puncte
                                                    for x in el[k + 1:k + 4]):
            grupuri.append(k)
    ambigue = [k for k, e in enumerate(el) if e.forma == 1 or (e.forma == 2 and len(el) > 1)]
    cele_mai_bune = None
    optiuni_grup = list(itertools.product([False, True], repeat=min(len(grupuri), 8)))
    for og in optiuni_grup:
        for e in el:
            e.grupat = False
        for g, da in zip(grupuri, og):
            if da:
                for x in el[g + 1:g + 4]:
                    x.grupat = True
        for om in itertools.product([False, True], repeat=min(len(ambigue), 10)):
            for k, mare in zip(ambigue, om):
                el[k].mare = mare
            for k, e in enumerate(el):
                if k not in ambigue:
                    e.mare = True
            tot = _desface_repetitii(msr.elemente, bata)
            s = sum(_valoare(e, e.mare) for e in tot)
            # preferă: duratele obișnuite (întreaga doar dacă e singură), puține grupări neobișnuite
            cost = sum(1 for k, mare in zip(ambigue, om) if mare and el[k].forma == 1 and len(el) > 1) * 3 + \
                sum(1 for k, mare in zip(ambigue, om) if not mare and el[k].forma == 2) * 3 + \
                sum(1 for k, mare in zip(ambigue, om) if mare and el[k].forma == 1 and len(el) == 1) * -1
            if abs(s - plina) < 1e-6 and (cele_mai_bune is None or cost < cele_mai_bune[0]):
                cele_mai_bune = (cost, og, om)
    if cele_mai_bune is None:
        for e in el:
            e.grupat = False
            e.mare = not (e.forma == 1 and len(el) > 1)
        return False
    _c, og, om = cele_mai_bune
    for e in el:
        e.grupat = False
    for g, da in zip(grupuri, og):
        if da:
            for x in el[g + 1:g + 4]:
                x.grupat = True
    for k, mare in zip(ambigue, om):
        el[k].mare = mare
    for k, e in enumerate(el):
        if k not in ambigue:
            e.mare = True
    return True


# ---------------- înălțimile ----------------
def _armura_alter(fifths):
    ordine = 'FCGDAEB' if fifths > 0 else 'BEADGCF'
    return {p: (1 if fifths > 0 else -1) for p in ordine[:abs(fifths)]}


class _Inaltimi:
    def __init__(self, armura, octava_start):
        self.ultima = None            # (treapta absolută = octava*7 + treapta)
        self.octava_start = octava_start
        self.armura = _armura_alter(armura)

    def pune(self, e, alterate):
        if e.octava is not None:
            o = e.octava
        elif self.ultima is None:
            o = self.octava_start
        else:
            uo, ut = divmod(self.ultima, 7)
            d = e.treapta - ut
            if abs(d) <= 2:
                o = uo
            elif d >= 5:
                o = uo - 1
            elif d <= -5:
                o = uo + 1
            else:
                o = uo                 # cvartă și cvintă: aceeași octavă
        self.ultima = o * 7 + e.treapta
        pas = PASI[e.treapta]
        if e.alter is not None:
            alterate[(pas, o)] = e.alter
            alt = e.alter
        else:
            alt = alterate.get((pas, o), self.armura.get(pas, 0))
        p = pitch.Pitch(pas + str(o))
        if alt:
            p.accidental = pitch.Accidental({1: 'sharp', -1: 'flat', 2: 'double-sharp', -2: 'double-flat'}.get(alt, 'natural'))
        elif e.alter == 0:
            p.accidental = pitch.Accidental('natural')
        return p


def _acord(baza, intervale, mana, inalt, alterate):
    """Notele acordului: la mâna dreaptă intervalele merg în jos de la nota scrisă, la stânga în sus."""
    note_ = [baza]
    curent = baza                     # intervalele se numără toate de la nota scrisă
    for iv, oc, alt in intervale:
        pasi = (iv - 1) * (-1 if mana == 'dreapta' else 1)
        t = PASI.index(curent.step) + pasi
        o = curent.octave + t // 7
        st = PASI[t % 7]
        if oc is not None:
            o = oc
        p = pitch.Pitch(st + str(o))
        a = alt if alt is not None else alterate.get((st, o), inalt.armura.get(st, 0))
        if alt is not None:
            alterate[(st, o)] = alt
        if a:
            p.accidental = pitch.Accidental({1: 'sharp', -1: 'flat'}.get(a, 'natural'))
        note_.append(p)
    return note_


def scor(p: Piesa):
    """Piesa citită -> (partitură music21, {număr măsură: [motive]})."""
    sc = stream.Score()
    md = metadata.Metadata()
    md.title = p.titlu or 'Braille'
    sc.metadata = md
    ts = meter.TimeSignature(p.masura)
    plina = float(ts.barDuration.quarterLength)
    bata = float(ts.beatDuration.quarterLength)
    de_verificat = {}
    maini = [('dreapta', 4)] + ([('stanga', 3)] if p.pian and p.maini['stanga'] else [])
    # anacruza: dacă prima măsură e mai scurtă, ea devine măsura 0 (cum o arată programul: „Anacruza”)
    prima = p.maini['dreapta'][0] if p.maini['dreapta'] else None
    if prima is not None:
        rezolva_durate(prima, plina, bata)
        if sum(_valoare(e, e.mare) for e in _desface_repetitii(prima.elemente, bata)) < plina - 1e-6 and prima.numar == 1:
            for lista in p.maini.values():
                for x in lista:
                    x.numar -= 1
    parti = []
    for mana, oct0 in maini:
        parte = stream.PartStaff() if p.pian else stream.Part()
        inalt = _Inaltimi(p.armura, oct0)
        legat_urm = False
        for k, msr in enumerate(p.maini[mana]):
            m = stream.Measure(number=msr.numar)
            if k == 0:
                m.insert(0, clef.TrebleClef() if mana == 'dreapta' else clef.BassClef())
                m.insert(0, key.KeySignature(p.armura))
                m.insert(0, meter.TimeSignature(p.masura))
            ok = rezolva_durate(msr, plina, bata)
            motive = list(msr.de_verificat)
            prima = k == 0
            el = _desface_repetitii(msr.elemente, bata)
            total = sum(_valoare(e, e.mare) for e in el)
            ultima = k == len(p.maini[mana]) - 1
            if not ok and not ((prima or ultima) and total < plina):
                motive.append(f'are {total:g} pătrimi în loc de {plina:g}')
            alterate = {}
            for e in el:
                d = duration.Duration(_valoare(e, e.mare))
                if e.tip == 'pauza':
                    n = note.Rest()
                    n.duration = d
                else:
                    baza = inalt.pune(e, alterate)
                    if e.intervale:
                        n = chord.Chord(_acord(baza, e.intervale, mana, inalt, alterate))
                    else:
                        n = note.Note(baza)
                    n.duration = d
                    if legat_urm:
                        n.tie = tie.Tie('stop')
                    if e.legat:
                        n.tie = tie.Tie('continue' if legat_urm else 'start')
                    legat_urm = e.legat
                m.append(n)
            if prima and total < plina - 1e-6:
                m.paddingLeft = plina - total
            if msr.repetitie_inceput:
                m.leftBarline = bar.Repeat(direction='start')
            if msr.repetitie_sfarsit:
                m.rightBarline = bar.Repeat(direction='end')
            elif msr.finala:
                m.rightBarline = bar.Barline('final')
            if motive:
                de_verificat.setdefault(msr.numar, []).extend(f'mâna {mana}: {x}' if p.pian else x for x in motive)
            parte.append(m)
        parti.append(parte)
    for x in parti:
        sc.insert(0, x)
    if len(parti) == 2:
        sc.insert(0, layout.StaffGroup(parti, symbol='brace'))
    return sc, de_verificat


def din_fisier(cale):
    """Fișierul .brl/.brf -> [(titlu, partitură, de_verificat)]."""
    with open(cale, 'rb') as f:
        text = f.read().decode('latin-1')
    rez = []
    for p in citeste_text(text):
        if any(p.maini.values()):
            sc, dv = scor(p)
            rez.append((p.titlu, sc, dv))
    return rez


def titluri(cale):
    """Titlurile pieselor din fișier, fără să le facă partituri (pentru alegerea piesei)."""
    with open(cale, 'rb') as f:
        text = f.read().decode('latin-1')
    return [p.titlu or str(k + 1) for k, p in enumerate(citeste_text(text)) if any(p.maini.values())]
