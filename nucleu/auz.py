"""Exerciții de auz (după aplicația MusicalApp): programul cântă o notă, un interval sau un acord
și tu alegi ce ai auzit. Partea aceasta nu știe de ferestre; fereastra cântă pașii și arată întrebările."""
import random
from dataclasses import dataclass, field
from .limba import _

SOLFEGIU = [_('Do'), _('Do diez'), _('Re'), _('Mi bemol'), _('Mi'), _('Fa'), _('Fa diez'), _('Sol'), _('Sol diez'), _('La'), _('Si bemol'), _('Si')]
LITERE = [_('C'), _('C diez'), _('D'), _('E bemol'), _('E'), _('F'), _('F diez'), _('G'), _('G diez'), _('A'), _('B bemol'), _('B')]

INTERVALE = [_('Primă perfectă'), _('Secundă mică'), _('Secundă mare'), _('Terță mică'), _('Terță mare'), _('Cvartă perfectă'),
             _('Triton'), _('Cvintă perfectă'), _('Sextă mică'), _('Sextă mare'), _('Septimă mică'), _('Septimă mare'), _('Octavă perfectă')]
REDARE_INTERVAL = [_('Melodic ascendent'), _('Melodic descendent'), _('Armonic')]

ACORDURI = [(_('Major'), [0, 4, 7]), (_('Minor'), [0, 3, 7]), (_('Micșorat'), [0, 3, 6]), (_('Mărit'), [0, 4, 8]),
            (_('Major 7'), [0, 4, 7, 11]), (_('Dominant 7'), [0, 4, 7, 10]), (_('Minor 7'), [0, 3, 7, 10]),
            (_('Minor major 7'), [0, 3, 7, 11]), (_('Semidiminuat 7'), [0, 3, 6, 10]), (_('Diminuat 7'), [0, 3, 6, 9])]
RASTURNARI = [_('Poziție fundamentală'), _('Răsturnarea I'), _('Răsturnarea II'), _('Răsturnarea III')]

EXERCITII = [_('Note'), _('Intervale'), _('Acorduri')]
IZOLARE = [_('Toate la fel de des'), _('Mai des cele bifate'), _('Doar cele bifate')]


@dataclass
class Setari:
    exercitiu: int = 0                 # 0 note, 1 intervale, 2 acorduri
    litere: bool = False               # C D E în loc de Do Re Mi
    octave: list = field(default_factory=lambda: [3, 4, 5])
    izolare: int = 0
    note_bifate: list = field(default_factory=list)        # 0–11
    intervale_bifate: list = field(default_factory=list)   # 0–12 semitonuri
    redare_interval: int = 0
    acorduri_bifate: list = field(default_factory=list)    # indici în ACORDURI
    intreaba_tipul: bool = True        # la acorduri: ce întrebări se pun (cel puțin una)
    rasturnari: bool = False
    fundamentala: bool = False
    greseli_pana_la_raspuns: int = 2
    instrument: list = field(default_factory=lambda: [0, 0])   # (bancă, program); implicit pian


@dataclass
class Intrebare:
    text: str
    optiuni: list
    corect: int


@dataclass
class Exercitiu:
    """O întrebare (sau mai multe la rând, la acorduri) cu sunetul ei.
    pasi: listă de (note MIDI care sună împreună, durata în ms, pauza de după în ms)."""
    intrebari: list
    pasi: list
    descriere: str                     # ce s-a cântat, spus la răspunsul arătat


def nume_note(litere):
    return LITERE if litere else SOLFEGIU


def _alege(n, bifate, izolare, rnd):
    """Un indice din range(n), ținând cont de cele bifate (mai des sau doar ele)."""
    bifate = [b for b in bifate if 0 <= b < n]
    if bifate and izolare == 2:
        return rnd.choice(bifate)
    if bifate and izolare == 1 and rnd.random() < 0.7:
        return rnd.choice(bifate)
    return rnd.randrange(n)


def _optiuni(toate, bifate, izolare):
    """Lista de răspunsuri: la „doar cele bifate” apar doar ele. Întoarce (etichete, indicii originali)."""
    if izolare == 2 and bifate:
        idx = sorted(set(bifate))
    else:
        idx = list(range(len(toate)))
    return [toate[i] for i in idx], idx


def genereaza(s: Setari, rnd=random) -> Exercitiu:
    octave = sorted(set(s.octave)) or [4]
    numele = nume_note(s.litere)
    if s.exercitiu == 0:
        pc = _alege(12, s.note_bifate, s.izolare, rnd)
        o = rnd.choice(octave)
        midi = 12 * (o + 1) + pc
        et, idx = _optiuni(numele, s.note_bifate, s.izolare)
        return Exercitiu([Intrebare(_('Ascultă nota și alege răspunsul corect.'), et, idx.index(pc))],
                         [([midi], 1200, 0)], _('Nota este {0} în octava {1}.', numele[pc], o))
    if s.exercitiu == 1:
        st = _alege(13, s.intervale_bifate, s.izolare, rnd)
        o = rnd.choice(octave)
        jos = 12 * (o + 1) + rnd.randrange(12)
        sus = jos + st
        if s.redare_interval == 0:
            pasi = [([jos], 900, 100), ([sus], 1100, 0)]
        elif s.redare_interval == 1:
            pasi = [([sus], 900, 100), ([jos], 1100, 0)]
        else:
            pasi = [([jos, sus], 1600, 0)]
        et, idx = _optiuni(INTERVALE, s.intervale_bifate, s.izolare)
        return Exercitiu([Intrebare(_('Ascultă intervalul și alege denumirea corectă.'), et, idx.index(st))], pasi,
                         _('Intervalul era {0}, de la {1}.', INTERVALE[st], numele[jos % 12]))
    # acorduri
    k = _alege(len(ACORDURI), s.acorduri_bifate, s.izolare, rnd)
    nume, structura = ACORDURI[k]
    o = rnd.choice(octave)
    rad_pc = rnd.randrange(12)
    rad = 12 * (o + 1) + rad_pc
    note_ = [rad + x for x in structura]
    inv = rnd.randrange(len(structura)) if s.rasturnari else 0
    for _x in range(inv):
        note_ = note_[1:] + [note_[0] + 12]
    et, idx = _optiuni([a[0] for a in ACORDURI], s.acorduri_bifate, s.izolare)
    intrebari = []
    tipul = s.intreaba_tipul or not (s.rasturnari or s.fundamentala)
    if tipul:
        intrebari.append(Intrebare(_('Ascultă acordul și alege tipul corect.'), et, idx.index(k)))
    if s.rasturnari:
        intrebari.append(Intrebare(_('Alege răsturnarea.') if intrebari else _('Ascultă acordul și alege răsturnarea.'),
                                   RASTURNARI[:len(structura)], inv))
    if s.fundamentala:
        intrebari.append(Intrebare(_('Alege fundamentala acordului.') if intrebari else _('Ascultă acordul și alege fundamentala.'),
                                   list(numele), rad_pc))
    pasi = [(note_, 1600, 250)] + [([n], 350, 0) for n in note_] + [(note_, 1400, 0)]
    descriere = _('Acordul era {0} pe {1}', nume, numele[rad_pc]) + (f', {RASTURNARI[inv]}' if s.rasturnari else '') + '.'
    return Exercitiu(intrebari, pasi, descriere)


class Scor:
    def __init__(self):
        self.corecte = self.gresite = self.serie = self.total = 0

    def text(self):
        return _('Corecte: {0}, greșite: {1}, serie: {2}, total: {3}.', self.corecte, self.gresite, self.serie, self.total)


class Sesiune:
    """Ține întrebarea curentă, greșelile și scorul."""

    def __init__(self, setari: Setari):
        self.setari = setari
        self.scor = Scor()
        self.ex = None
        self.pas = 0
        self.greseli = 0
        self.ultimul = ''           # ce a fost ultimul răspuns: corect, urmatoarea, gresit, aratat

    def nou(self, rnd=random):
        self.ex = genereaza(self.setari, rnd)
        self.pas = 0
        self.greseli = 0
        return self.ex

    @property
    def intrebare(self):
        if self.ex and self.pas < len(self.ex.intrebari):
            return self.ex.intrebari[self.pas]
        return None

    def raspunde(self, i):
        """Întoarce (mesaj, gata): gata = exercițiul s-a terminat (corect sau cu răspunsul arătat)."""
        q = self.intrebare
        if q is None:
            return _('Începe un exercițiu nou.'), True
        if i == q.corect:
            self.pas += 1
            if self.pas < len(self.ex.intrebari):
                self.ultimul = 'urmatoarea'
                return _('Corect. ') + self.intrebare.text, False
            if self.greseli == 0:
                self.scor.corecte += 1
                self.scor.serie += 1
            self.scor.total += 1
            self.ultimul = 'corect'
            return _('Răspuns corect.'), True
        self.greseli += 1
        if self.greseli == 1:
            self.scor.gresite += 1
            self.scor.serie = 0
        if self.greseli >= max(1, self.setari.greseli_pana_la_raspuns):
            corect = q.optiuni[q.corect]
            self.scor.total += 1
            self.pas = len(self.ex.intrebari)
            self.ultimul = 'aratat'
            return _('Răspuns greșit. Răspunsul corect era {0}. {1}', corect, self.ex.descriere), True
        self.ultimul = 'gresit'
        return _('Răspuns greșit. Mai încearcă.'), False
