"""Braille muzical cu music21 și export în formatele folosite de imprimantele Braille."""
from music21 import stream
from music21.braille import translate

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


def din_scor(scor: stream.Score, latime: int = 40) -> str:
    """Braille muzical pentru un scor: la pian cu două mâini iese măsură peste măsură (mâna dreaptă deasupra)."""
    parti = list(scor.parts)
    if len(parti) == 1:
        obiect = parti[0]
    else:
        obiect = scor
    try:
        return translate.objectToBraille(obiect, maxLineLength=latime)
    except Exception:
        # unele partituri complicate nu trec dintr-o bucată; le facem partidă cu partidă
        bucati = []
        for p in parti:
            try:
                bucati.append(translate.objectToBraille(p, maxLineLength=latime))
            except Exception as e:
                bucati.append(f'[Braille indisponibil pentru {p.partName or "această partidă"}: {e}]')
        return '\n\n'.join(bucati)
