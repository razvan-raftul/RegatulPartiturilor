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

from music21 import bar, metadata, stream
from music21.braille import segment, translate

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
                bucati.append(f'[Braille indisponibil pentru {p.partName or "această partidă"}: {e}]')
        muzica = '\n\n'.join(bucati)
    return (sus + '\n\n' + muzica) if sus else muzica
