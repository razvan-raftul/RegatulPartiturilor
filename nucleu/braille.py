"""Braille muzical cu music21 și export în formatele folosite de imprimantele Braille.

Regulile după care iese partitura sunt cele din manualul „Cum să citim muzica în Braille”
(Bettye Krolick, traducere Mircea Bucur) și din Instrucțiunile lui Răzvan. Sunt scrise pe larg în
CITESTE-MA, la „Reguli de braille muzical”. Pe scurt, peste ce face music21:
1. Titlul și compozitorul se scriu sus, centrate, cu semnul de majusculă punctele 4 6, ca în
   partiturile braille românești. Nu mai apar etichetele englezești „Composer:”, „Title:”.
2. Ultima măsură a piesei se termină cu bara dublă finală (punctele 1 2 6, 1 3).
3. La pian, acordurile de la mâna dreaptă se scriu de la nota de sus în jos, iar cele de la
   mâna stângă de la nota de jos în sus, oricare ar fi cheia.
"""
import copy
import re
import unicodedata

from music21 import bar, metadata, spanner, stream
from music21.braille import basic, segment, text, translate
from .limba import _

# Unicode Braille (U+2800 + puncte) -> ASCII Braille (tabelul nord-american, folosit de fișierele .brf)
ASCII_BRF = " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)="


def la_brf(text: str) -> str:
    out = []
    for ch in text:
        c = ord(ch)
        if 0x2800 <= c <= 0x283F:
            out.append(ASCII_BRF[c - 0x2800])
        elif ch == '\n':
            out.append('\r\n')
        else:
            out.append(ch if ord(ch) < 128 else ' ')
    return ''.join(out)


def _din_ascii(s: str) -> str:
    return ''.join(chr(0x2800 + ASCII_BRF.index(c)) if c in ASCII_BRF else chr(0x2800) for c in s)


# ---------- Regula 3: acordurile după mână ----------
_original_atribute = segment.BrailleSegment.addGroupingAttributes


def _atribute_dupa_mana(self):
    _original_atribute(self)
    for cheie, grupare in self.items():
        mana = getattr(cheie, 'hand', None)
        if mana == 'right':
            grupare.descendingChords = True
        elif mana == 'left':
            grupare.descendingChords = False


segment.BrailleSegment.addGroupingAttributes = _atribute_dupa_mana


# ---------- Fără comprimarea măsurilor repetate ----------
# music21 strânge măsurile identice la rând într-una cu semn de repetiție. La pian, dacă se întâmplă doar la
# o mână (de exemplu mâna stângă cu aceeași măsură de 4 ori), măsurile celeilalte mâini din dreptul lor
# se pierdeau din Braille (Cramer, Studiul 46: lipseau măsurile 2-4). Răzvan citește totul scris întreg.
segment.areGroupingsIdentical = lambda a, b: False


# ---------- Semnul de triolet apare mereu ----------
# music21 scrie semnul de triolet (punctele 2 3) doar când grupul ar putea fi „legat” după regulile braille
# pentru note scurte; dacă după triolet urmează o optime, semnul se pierdea (Buciu, Canto 5, măsura 5).
_original_beamed = segment.prepareBeamedNotes


def _cu_semn_de_triolet(masura):
    _original_beamed(masura)
    for n in masura.notes:
        tuplete = n.duration.tuplets
        if tuplete and tuplete[0].type == 'start':
            n.beamStart = True


segment.prepareBeamedNotes = _cu_semn_de_triolet


# ---------- Semnele de repetiție și voltele ----------
# music21 scria bara de sfârșit de repetiție ca bară finală (⠣⠅) și nu scria deloc voltele.
# Acum: începutul repetiției ⠣⠆, sfârșitul ⠣⠶, iar prima notă a voltei primește ⠼⠂ (volta 1),
# ⠼⠆ (volta 2) etc., urmat de semnul de octavă.
_original_bara = basic.barlineToBraille
_CIFRE_JOS = {1: '\u2802', 2: '\u2806', 3: '\u2812', 4: '\u2832', 5: '\u2822'}


def _bara(b):
    if isinstance(b, bar.Repeat):
        return '\u2823\u2836' if b.direction == 'end' else '\u2823\u2806'
    return _original_bara(b)


basic.barlineToBraille = _bara
_original_nota = basic.noteToBraille
_original_pauza = basic.restToBraille


def _volta(obiect):
    nr = getattr(obiect.editorial, 'volta', None) if 'volta' in obiect.editorial else None
    return ('\u283c' + _CIFRE_JOS.get(nr, '\u2802')) if nr else ''


def _nota(n, **kw):
    v = _volta(n)
    if v:
        kw['showOctave'] = True
    return v + _original_nota(n, **kw)


def _pauza(r):
    return _volta(r) + _original_pauza(r)


basic.noteToBraille = _nota
basic.restToBraille = _pauza


def _marcheaza_voltele(scor):
    for paranteza in scor.recurse().getElementsByClass(spanner.RepeatBracket):
        masuri = paranteza.getSpannedElements()
        if not masuri:
            continue
        note_ = list(masuri[0].recurse().notesAndRests)
        if note_:
            try:
                nr = int(str(paranteza.number).split(',')[0].strip())
            except ValueError:
                nr = 1
            note_[0].editorial.volta = nr


# ---------- Câte două măsuri într-o paralelă, numerotate 1, 3, 5... ----------
# Cerut de Răzvan (20 oct. 2026), ca în partiturile lui braille: fiecare paralelă are două măsuri, mâna
# dreaptă deasupra, mâna stângă dedesubt; numărul se scrie doar la începutul paralelei (1, 3, 5...), a doua
# măsură urmează pe același rând, după un spațiu. Paralela se scrie întâi pe un rând lung, fără limită;
# dacă un rând nu încape în lățimea paginii, _rupe_randuri îl continuă pe rândul următor (dreapta toată,
# apoi stânga toată), ca în partiturile transcrise de om.
MASURI_PE_PARALELA = 2
_FARA_LIMITA = 4000


def _fara_limita(linie):
    if linie.lineLength < _FARA_LIMITA:
        linie.allChars.extend([text.symbols['space']] * (_FARA_LIMITA - linie.lineLength))
        linie.lineLength = _FARA_LIMITA


def _adauga_masura(self, numar_braille, gr, gl):
    perechea = getattr(self, 'currentGroupingPair', None) or (None, None)
    cheie = perechea[0] or perechea[1]
    m = cheie.measure if cheie is not None else None
    if not hasattr(self, '_prima_masura'):
        self._prima_masura, self._masura_curenta = m, None
    noua = m != self._masura_curenta
    self._masura_curenta = m
    paralela_noua = (self.rightHandLine is None or
                     (noua and m is not None and self._prima_masura is not None
                      and (m - self._prima_masura) % MASURI_PE_PARALELA == 0))
    if paralela_noua:
        self.makeNewLines()
        _fara_limita(self.rightHandLine)
        _fara_limita(self.leftHandLine)
        self.rightHandLine.insert(self.highestMeasureNumberLength - len(numar_braille), numar_braille)
        self.leftHandLine.textLocation = self.rightHandLine.textLocation
        self.rightHandLine.append(text.symbols['rh_keyboard'], addSpace=True)
        self.leftHandLine.append(text.symbols['lh_keyboard'], addSpace=True)
        if gr:
            for punct in basic.yieldDots(gr[0]):
                self.rightHandLine.append(punct, addSpace=False)
            self.rightHandLine.append(gr, addSpace=False)
        if gl:
            for punct in basic.yieldDots(gl[0]):
                self.leftHandLine.append(punct, addSpace=False)
            self.leftHandLine.append(gl, addSpace=False)
    else:
        if gl:
            self.leftHandLine.append(gl, addSpace=True)
        if gr:
            self.rightHandLine.append(gr, addSpace=True)
    loc = max(self.rightHandLine.textLocation, self.leftHandLine.textLocation)
    self.rightHandLine.textLocation = self.leftHandLine.textLocation = loc
    self.rightHandLine.containsNoteGrouping = True
    self.leftHandLine.containsNoteGrouping = True


text.BrailleKeyboard.addNoteGroupings = _adauga_masura


def _recentreaza_titlurile(self):
    """Ca în music21, dar titlul de deasupra (măsura, armura) se centrează pe lățimea paginii,
    nu pe rândurile lungi ale paralelelor (care se rup abia după aceea)."""
    for (inceput, sfarsit) in self.allHeadings:
        lung = 0
        for i in range(sfarsit, len(self.allLines)):
            if self.allLines[i].isHeading:
                break
            lung = max(lung, self.allLines[i].textLocation)
        lung = min(lung, self.lineLength)
        for j in range(inceput, sfarsit):
            linie = self.allLines[j]
            t = str(linie).strip(text.symbols['space'])
            if lung > len(t):
                linie.insert(0, t.center(lung, text.symbols['space']))
                linie.textLocation = lung


text.BrailleText.recenterHeadings = _recentreaza_titlurile

_GOL = '\u2800'
_CRATIMA = '\u2810'
MD = text.symbols['rh_keyboard']   # semnul mâinii drepte
MS = text.symbols['lh_keyboard']   # semnul mâinii stângi      # cratima muzicală (punctul 5): măsura continuă pe rândul următor


def _inceput_muzica(rand: str) -> int:
    """Unde începe muzica pe rândul unei paralele: după numărul măsurii și semnul mâinii."""
    i = 0
    while i < len(rand) and rand[i] == _GOL:
        i += 1
    while i < len(rand) and rand[i] != _GOL:
        i += 1
    return i


def _strange(rand: str) -> str:
    i = _inceput_muzica(rand)
    return rand[:i] + re.sub(_GOL + '{2,}', _GOL, rand[i:])


def _rupe_randuri(muzica: str, latime: int) -> str:
    """Rândurile mai lungi decât pagina continuă pe rândul următor, aliniate sub muzică (dreapta toată,
    apoi stânga toată). Dacă o paralelă se rupe, alinierea măsurilor între mâini nu mai ține, deci la
    amândouă mâinile rămâne un singur spațiu între măsuri. Se rupe între măsuri; dacă o măsură singură
    nu încape, se rupe în ea, cu cratimă."""
    randuri = [r.rstrip(_GOL + ' ') for r in muzica.split('\n')]
    for k in range(len(randuri) - 1):
        if MD in randuri[k] and MS in randuri[k + 1] and max(len(randuri[k]), len(randuri[k + 1])) > latime:
            randuri[k], randuri[k + 1] = _strange(randuri[k]), _strange(randuri[k + 1])
    iesire = []
    for rand in randuri:
        if len(rand) <= latime:
            iesire.append(rand)
            continue
        rand = _strange(rand)
        retragere = min(_inceput_muzica(rand) + 1, latime // 4)
        primul = True
        while len(rand) > (latime if primul else latime - retragere):
            lat = latime if primul else latime - retragere
            taie = rand.rfind(_GOL, 0, lat + 1)
            if taie <= (retragere if primul else 0):
                bucata, rand = rand[:lat - 1] + _CRATIMA, rand[lat - 1:]
            else:
                bucata, rand = rand[:taie].rstrip(_GOL), rand[taie:].lstrip(_GOL)
            iesire.append(bucata if primul else _GOL * retragere + bucata)
            primul = False
        if rand:
            iesire.append(rand if primul else _GOL * retragere + rand)
    return '\n'.join(iesire)


# ---------- Regula 1: titlul ----------
def _text_braille(text: str) -> str:
    """Text obișnuit în braille ASCII: majusculă = punctele 4 6, cifrele cu semnul de număr.
    Diacriticele se scot (a în loc de ă), ca rândul să se citească sigur pe orice aparat."""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    cifre = '1234567890'
    litere_cifre = 'ABCDEFGHIJ'
    out = []
    in_numar = False
    for c in text:
        if c.isdigit():
            if not in_numar:
                out.append('#')
                in_numar = True
            out.append(litere_cifre[cifre.index(c)])
            continue
        in_numar = False if c not in '.,' else in_numar
        if c.isalpha() and c.isascii():
            if c.isupper():
                out.append('.')
            out.append(c.upper())
        elif c == ' ':
            out.append(' ')
        elif c == '.':
            out.append('4')
        elif c == ',':
            out.append('1')
        elif c == '-':
            out.append('-')
        elif c == ':':
            out.append('3')
        elif c in '()':
            out.append('7')
    return ''.join(out).strip()


def _centrat(s: str, latime: int) -> str:
    s = s[:latime]
    return ' ' * max(0, (latime - len(s)) // 2) + s


def titlu(scor: stream.Score, latime: int = 40) -> str:
    md = scor.metadata
    if md is None:
        return ''
    linii = []
    for valoare in (md.title or md.movementName, md.movementName if md.title and md.movementName != md.title else None,
                    md.composer):
        if valoare:
            valoare = re.sub(r'\.(mxl|musicxml|xml|mid|midi|mscz)$', '', str(valoare), flags=re.I)
            t = _text_braille(valoare)
            while len(t) > latime:
                taiere = t.rfind(' ', 0, latime)
                taiere = taiere if taiere > 0 else latime
                linii.append(_centrat(t[:taiere], latime))
                t = t[taiere:].strip()
            if t:
                linii.append(_centrat(t, latime))
    return '\n'.join(_din_ascii(l) for l in linii)


# ---------- Regula 2: bara finală ----------
def _cu_bara_finala(scor: stream.Score, final: bool):
    if not final:
        return
    for p in scor.parts:
        masuri = list(p.getElementsByClass(stream.Measure))
        if masuri and (masuri[-1].rightBarline is None or masuri[-1].rightBarline.type not in ('final', 'light-heavy')):
            if masuri[-1].rightBarline is None or masuri[-1].rightBarline.type == 'regular':
                masuri[-1].rightBarline = bar.Barline('final')


def din_scor(scor: stream.Score, latime: int = 40, final: bool = True) -> str:
    """Braille muzical pentru un scor: la pian cu două mâini iese măsură peste măsură (mâna dreaptă deasupra).
    final=True: bucata se termină odată cu piesa, deci primește bara dublă finală."""
    scor = copy.deepcopy(scor)
    sus = titlu(scor, latime)
    for md in list(scor.getElementsByClass(metadata.Metadata)):
        scor.remove(md)
    _cu_bara_finala(scor, final)
    _marcheaza_voltele(scor)
    parti = list(scor.parts)
    obiect = parti[0] if len(parti) == 1 else scor
    try:
        muzica = translate.objectToBraille(obiect, maxLineLength=latime)
    except Exception:
        # unele partituri complicate nu trec dintr-o bucată; le facem partidă cu partidă
        bucati = []
        for p in parti:
            try:
                bucati.append(translate.objectToBraille(p, maxLineLength=latime))
            except Exception as e:
                bucati.append(_('[Braille indisponibil pentru {0}: {1}]', p.partName or "această partidă", e))
        muzica = '\n\n'.join(bucati)
    muzica = _rupe_randuri(muzica, latime)
    return (sus + '\n\n' + muzica) if sus else muzica
