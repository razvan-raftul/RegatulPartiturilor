"""Probă pentru recunoaștere (rulată pe GitHub în workflow-ul componente și de Claude în containerul lui):
compară ce au citit homr și Audiveris cu partitura originală, apoi rezultatul combinat.
Folosire: python proba_recunoastere.py ORIGINAL.mxl HOMR.musicxml AUDIVERIS.mxl"""
import sys

from music21 import converter

from nucleu import verificare as V


def main():
    orig, homr, aud = sys.argv[1:4]
    O = converter.parse(orig)
    citite = {'homr': converter.parse(homr), 'Audiveris': converter.parse(aud)}
    for n, s in citite.items():
        r = V.compara_cu_originalul(O, s)
        print(f"{n}: masuri corecte {r['masuri_ok']} din {r['masuri']}, note corecte {r['note_ok']} din {r['note']}, "
              f"note in plus {r['note_in_plus']}")
    R = V.combina(citite)
    r = V.compara_cu_originalul(O, R.scor)
    nes = {nr for nr, _ in R.nesigure}
    nesemnalate = sorted(set(r['gresite']) - nes)
    print(f"Combinat: masuri corecte {r['masuri_ok']} din {r['masuri']}, note corecte {r['note_ok']} din {r['note']}; "
          f"masuri de verificat {len(nes)}; greseli nesemnalate: {nesemnalate}")
    if not nesemnalate:
        print('PROBA OK')


if __name__ == '__main__':
    main()
